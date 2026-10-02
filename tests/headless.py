#!/usr/bin/env python3
"""无头验收驾驭器（零依赖 · CDP over WebSocket）。

Chrome 152 的 `--headless=new --dump-dom` 在 rAF 静止页面上不退出，且在 load 事件就 dump，
拿不到异步自测结果；这里改用 DevTools 协议：起 Chrome → 打开页面 → 轮询
`document.body.dataset.cltest` → 可选截图 → 杀进程。

用法：
  python3 -s tests/headless.py "demo=1&probe=1&pump=1&warm=140&autotest=1"
  python3 -s tests/headless.py "demo=1&probe=1&pump=1&warm=60&sel=昭阳" --shot /tmp/castline-shots/focus.png --wait 4
  python3 -s tests/headless.py "<query>" --eval "JSON.stringify(__cl.scene.crown())"
选项：--timeout 秒（默认 240，可用 CL_TIMEOUT 覆盖）· --size 1440x900 · --dpr 2（模拟 Retina）· --shot 文件 · --wait 秒（截图前额外等待）· --eval 表达式（自测完成后求值）· --url 覆盖地址
收尾：READY 格式不变；所有 eval/shot 后输出 POST 与 POST-HEALTH JSON。
健康退出 0；实际 JS/Promise/shader/eval 异常退出 1；健康检测缺失/失败退出 2。
"""
import sys, os, json, time, socket, base64, struct, subprocess, shutil, argparse, html, re, signal, glob
import urllib.request

CH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# --eval 返回体的上限：只防真正的失控，不做常规截断（详见下方打印处注释）。
EVAL_MAX = 2000000

# 驱动自带监听：页面未安装 dataset 错误钩子时，也能捕获交互后的异常。
# 不修改页面 dataset，保留 READY 行及既有探针的语义。
HEALTH_INIT_JS = r"""(function () {
    var h = {jserr: [], jsrej: []};
    window.__headlessHealth = h;
    function describe(e) { return String(e && (e.stack || e.message) || e); }
    window.addEventListener('error', function (e) {
        h.jserr.push(describe(e.error || e.message || 'unknown error'));
    });
    window.addEventListener('unhandledrejection', function (e) {
        h.jsrej.push(describe(e.reason));
    });
})();"""

# 等一个事件循环任务，让最后一次 eval 的未处理 Promise 拒绝有机会报告。
POST_HEALTH_JS = r"""new Promise(function (resolve) {
    setTimeout(function () {
        var out = {jserr: null, jsrej: null, shaderErrors: null, missing: [], probeErrors: [], errorCounts: {}};
        var h = window.__headlessHealth, ds = document.body && document.body.dataset;
        if (!ds) out.missing.push('document.body.dataset');
        ['jserr', 'jsrej'].forEach(function (key) {
            var messages = h && Array.isArray(h[key]) ? h[key].slice() : null;
            if (!messages) { out.missing.push('error-listener.' + key); messages = []; }
            if (ds && ds[key] && ds[key] !== 'none') messages.push(String(ds[key]));
            out.errorCounts[key] = messages.length;
            if (messages.length) out[key] = messages.join('\n');
            else if (h && Array.isArray(h[key])) out[key] = 'none';
        });
        try {
            var scene = window.__cl && window.__cl.scene;
            if (!scene || typeof scene.shaderErrors !== 'function') {
                out.missing.push('scene.shaderErrors');
            } else {
                var errors = scene.shaderErrors();
                if (Array.isArray(errors)) out.shaderErrors = errors;
                else out.probeErrors.push('scene.shaderErrors() did not return an array');
                var digest = typeof scene.digest === 'function' ? scene.digest() : null;
                if (digest && digest.frameHooks) {
                    out.errorCounts.frameHooks = digest.frameHooks.errors || 0;
                    out.frameHookLastError = digest.frameHooks.lastError || null;
                }
            }
        } catch (e) { out.probeErrors.push(String(e && (e.stack || e.message) || e)); }
        resolve(out);
    }, 0);
})"""


def health_evaluate(ws, errors, label, expression, **params):
    """CDP 求值异常未必触发 window.error，必须独立保留，不能被末拍健康覆盖。"""
    result = ws.call('Runtime.evaluate', expression=expression, returnByValue=True, **params)
    if 'exceptionDetails' in result:
        errors.append({'phase': label, 'exceptionDetails': result['exceptionDetails']})
    return result


def post_health(ws, eval_errors):
    """POST-HEALTH 是机器可读 JSON；0=健康，1=实际异常，2=检测缺失/失败。"""
    health = {'jserr': None, 'jsrej': None, 'shaderErrors': None,
              'missing': [], 'probeErrors': [], 'errorCounts': {}}
    try:
        result = ws.call('Runtime.evaluate', expression=POST_HEALTH_JS,
                         returnByValue=True, awaitPromise=True)
        if 'exceptionDetails' in result:
            raise ValueError('POST evaluate: ' + json.dumps(result['exceptionDetails'], ensure_ascii=False))
        value = result.get('result', {}).get('value')
        if not isinstance(value, dict):
            raise ValueError('POST health did not return an object')
        for key in ('jserr', 'jsrej', 'shaderErrors'):
            expected = list if key == 'shaderErrors' else str
            if isinstance(value.get(key), expected):
                health[key] = value[key]
            elif value.get(key) is not None:
                health['probeErrors'].append('invalid POST field: ' + key)
        for key in ('missing', 'probeErrors'):
            if isinstance(value.get(key), list):
                health[key].extend(value[key])
            else:
                health['probeErrors'].append('invalid POST field: ' + key)
        counts = value.get('errorCounts')
        for key in ('jserr', 'jsrej'):
            count = counts.get(key) if isinstance(counts, dict) else None
            if type(count) is int and count >= 0:
                health['errorCounts'][key] = count
            else:
                health['probeErrors'].append('invalid POST field: errorCounts.' + key)
        if isinstance(counts, dict) and 'frameHooks' in counts:
            if type(counts['frameHooks']) is int and counts['frameHooks'] >= 0:
                health['errorCounts']['frameHooks'] = counts['frameHooks']
                health['frameHookLastError'] = value.get('frameHookLastError')
            else:
                health['probeErrors'].append('invalid POST field: errorCounts.frameHooks')
    except Exception as exc:
        health['probeErrors'].append(str(exc))
    for key in ('jserr', 'jsrej', 'shaderErrors'):
        if health[key] is None and key not in health['missing']:
            health['missing'].append(key)
    health['evalErrors'] = list(eval_errors)
    # Promise.reject('none') / Promise.reject('') 也是真异常，不能与健康哨兵混淆。
    actual = bool(eval_errors or health['shaderErrors'] or any(health['errorCounts'].values()) or any(
        health[key] not in (None, '', 'none') for key in ('jserr', 'jsrej')))
    code = 1 if actual else (2 if health['missing'] or health['probeErrors'] else 0)
    health['ok'] = code == 0
    health['exitCode'] = code
    # 单行显示：错误里的换行转义，避免破坏调用方的逐行解析。
    def display(value):
        if value is None: return 'MISSING'
        if value in ('', 'none'): return 'none'
        return json.dumps(value, ensure_ascii=False)
    print('POST jserr/jsrej: %s | %s · shaderErrors: %s · status: %s' % (
        display(health['jserr']), display(health['jsrej']), display(health['shaderErrors']),
        'OK' if code == 0 else ('FAIL' if code == 1 else 'INCOMPLETE')))
    print('POST-HEALTH: ' + json.dumps(health, ensure_ascii=False), flush=True)
    return code

class WS:
    def __init__(self, url, timeout=None):
        m = re.match(r'ws://([^:/]+):(\d+)(/.*)', url); host, port, path = m.group(1), int(m.group(2)), m.group(3)
        # 这个超时是「一次 Runtime.evaluate 最长等多久」，不是「页面最长跑多久」。
        # 旧值硬编码 30 s：聚焦态 + pump/warm 会把主线程连续同步阻塞更久（建晶冠 + 逐帧 pump 都是同步的），
        # 于是 evaluate 迟迟不返回、socket 先超时，抛出来的是一串 recv() traceback ——
        # 看起来像「页面崩了」，其实是「页面还在忙」。这两种情况必须能分辨，否则会去查根本不存在的 bug。
        # 默认改为跟随 --timeout（下限 60 s）；CL_CDP_TIMEOUT 仍可显式覆盖。
        self.timeout = timeout or float(os.environ.get('CL_CDP_TIMEOUT', '30'))
        self.s = socket.create_connection((host, port), timeout=self.timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(('GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (path, host, port, key)).encode())
        buf = b''
        while b'\r\n\r\n' not in buf: buf += self.s.recv(4096)
        assert b' 101 ' in buf.split(b'\r\n')[0], buf[:200]
        self.buf = buf.split(b'\r\n\r\n', 1)[1]; self.id = 0
    def _read(self, n):
        while len(self.buf) < n:
            d = self.s.recv(65536)
            if not d: raise IOError('ws closed')
            self.buf += d
        out, self.buf = self.buf[:n], self.buf[n:]; return out
    def send(self, obj):
        data = json.dumps(obj).encode(); mask = os.urandom(4)
        hdr = bytes([0x81])
        L = len(data)
        if L < 126: hdr += bytes([0x80 | L])
        elif L < 65536: hdr += bytes([0x80 | 126]) + struct.pack('>H', L)
        else: hdr += bytes([0x80 | 127]) + struct.pack('>Q', L)
        self.s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
    def recv(self):
        while True:
            b0, b1 = self._read(2); op = b0 & 0x0f; L = b1 & 0x7f
            if L == 126: L = struct.unpack('>H', self._read(2))[0]
            elif L == 127: L = struct.unpack('>Q', self._read(8))[0]
            if b1 & 0x80: self._read(4)
            payload = self._read(L)
            if op == 8: raise IOError('ws close')
            if op == 9: continue
            if op in (1, 2, 0): return json.loads(payload.decode('utf-8', 'replace'))
    def call(self, method, **params):
        self.id += 1; my = self.id; self.send({'id': my, 'method': method, 'params': params})
        while True:
            m = self.recv()
            if m.get('id') == my:
                if 'error' in m: raise RuntimeError(m['error'])
                return m.get('result', {})

def reap_orphans():
    """开机自愈：收割「属主已死」的 castline 无头孤儿（Q7 修 · 2026-09-18）。

    为什么需要它：下面的 finally 清理只在**本进程能跑到 finally** 时生效。但本仓约 40 个
    套件（perf_budget / legend_tip / abyss_p6-8 / twig_phase …）是用**裸
    `subprocess.run(..., timeout=)`** 调本脚本的 —— 一旦超时，`subprocess.run` 只
    SIGKILL 掉**本进程**（Python 包装层），Chrome 与它的 SwiftShader GPU helper 会被
    orphan 到 launchd（ppid=1）**继续烧满一整核**，而 finally 永远不会执行。

    这会形成正反馈：泄漏越多 → 机器越慢 → 越多套件超时 → 泄漏越多。实测一次会话累积
    **8 只**、约 **760% CPU**、load 顶到 70+，直接导致 `perf_budget` 的 `R14.Q5 plot render`
    从 240~450ms 漂到 984ms（预算 600）→ 报 FAIL，**是一次假回归**：清掉孤儿后连跑两次
    同为 OK。

    解法：每次启动前先扫 `/tmp/castline-cdp-<pid>`，**只收割属主 python 已死的那批**。
    属主存活即视为并发兄弟（`runall -j 4`）→ 跳过不碰；非数字后缀（如手工 `-diag`）→ 跳过。
    """
    for d in glob.glob('/tmp/castline-cdp-*'):
        owner = os.path.basename(d)[len('castline-cdp-'):]
        if not owner.isdigit():
            continue
        pid = int(owner)
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, 0)          # 属主仍在 → 并发兄弟，保留
            continue
        except PermissionError:
            continue                 # 非本用户 → 不碰
        except ProcessLookupError:
            pass                     # 属主已死 → 孤儿，收割
        try:
            subprocess.run(['pkill', '-9', '-f', '--', '--user-data-dir=' + d],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except Exception:
            pass
        shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('query'); ap.add_argument('--timeout', type=float, default=float(os.environ.get('CL_TIMEOUT', '240'))); ap.add_argument('--size', default='1440x900')
    ap.add_argument('--shot'); ap.add_argument('--wait', type=float, default=0); ap.add_argument('--eval', dest='ev'); ap.add_argument('--url', default=os.environ.get('CL_URL', 'http://127.0.0.1:8000/'))
    # 同进程二次求值 + 二次截图。为什么要它：两次**独立**进程出图之间天然有 ~4.9% 的
    # 像素噪声地板（摇曳相位 / 星尘自转 / 微光闪烁各差几帧），而「聚焦是否看得见」这类信号
    # 只有 2~5% —— 信号埋在噪声里，断言必然假灵敏。同进程连拍把两个变量压到只剩「被测的那一个」。
    ap.add_argument('--eval2', dest='ev2'); ap.add_argument('--shot2'); ap.add_argument('--wait2', type=float, default=None)
    ap.add_argument('--eval3', dest='ev3'); ap.add_argument('--shot3'); ap.add_argument('--wait3', type=float, default=None)
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--dpr', type=float, default=0, help='设备像素比（默认 1，如 2 = Retina），截图按设备像素输出')
    ap.add_argument('--reduce', action='store_true',
                    help='模拟 prefers-reduced-motion: reduce（树下各层会跳过生长/呼吸动效）。'
                         '只能在页面导航前设好，因为各层是在 build 时读 matchMedia 的。')
    a = ap.parse_args()
    # 开机自愈：先收割上一批「属主已死」的孤儿，别让历史泄漏污染本次的计时类断言。
    reap_orphans()
    w, h = a.size.split('x'); port = 9400 + os.getpid() % 500; ud = '/tmp/castline-cdp-%d' % os.getpid()
    # CL_GPU=1 时走 Metal 真 GPU（做性能剖析用；默认仍 SwiftShader 保证像素门禁可复现）
    gl = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization'] if os.environ.get('CL_GPU') == '1' else ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
    # CL_WINDOWED=1：不加 --headless，弹真窗口（诊断真机渲染路径用；默认无头）
    head = [] if os.environ.get('CL_WINDOWED') == '1' else ['--headless=new']
    cmd = [CH] + head + gl + ['--hide-scrollbars', '--window-size=%s,%s' % (w, h),
           '--user-data-dir=' + ud, '--remote-debugging-port=%d' % port, '--no-first-run', '--disable-background-networking', 'about:blank']
    # Q7 修（2026-09-18）：**不要** start_new_session —— 让 Chrome 留在调用者的进程组里。
    # 原实现只 `proc.kill()` 浏览器主进程，SwiftShader GPU helper 会被 reparent 到
    # launchd（ppid=1）继续活着：实测一次 runall 泄漏 97 只，单只吃到 120% CPU，
    # 把 load 顶到 115，反向污染后续所有计时类断言（「假红洪水」的真正来源）。
    # 但若在此处另开会话组，runall 超时 killpg 就杀不到 Chrome（形成新的泄漏）。
    # 正解：**继承**调用者进程组 → 上层 killpg 能连坐收割；再配 per-ud 兜底扫尾。
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time(); ws = None
    health_armed = False; health_rc = 0; eval_errors = []
    sockto = float(os.environ.get('CL_CDP_TIMEOUT') or 0) or max(60.0, a.timeout)
    try:
        for _ in range(200):
            try:
                tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2).read()); break
            except Exception: time.sleep(0.15)
        else: raise SystemExit('chrome devtools not reachable')
        page = [t for t in tabs if t.get('type') == 'page'][0]
        ws = WS(page['webSocketDebuggerUrl'], timeout=sockto)
        ws.call('Page.enable'); ws.call('Runtime.enable')
        ws.call('Page.addScriptToEvaluateOnNewDocument', source=HEALTH_INIT_JS)
        health_armed = True
        # 窗口尺寸包含浏览器边框，Chrome 也会把窄窗口扩到 500 px。
        # --size 指定页面视口，必须在导航前显式设置，不能依赖窗口尺寸。
        ws.call('Emulation.setDeviceMetricsOverride', width=int(w), height=int(h), deviceScaleFactor=a.dpr or 1, mobile=False)
        # 降低动效必须在 Page.navigate **之前**设：树层（ghost/veil/clones）是在各自 build
        # 里读一次 matchMedia 的，导航后再设就只能影响"下一次 build"，等于没测。
        if a.reduce:
            ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])
        url = a.url + ('?' + a.query if a.query else '')
        ws.call('Page.navigate', url=url)
        res = None; expr = "document.body && document.body.dataset.cltest || ''"
        want_test = 'autotest=' in a.query
        while time.time() - t0 < a.timeout:
            time.sleep(0.5)
            r = ws.call('Runtime.evaluate', expression=expr, returnByValue=True)
            v = r.get('result', {}).get('value') or ''
            if v: res = v; break
            if not want_test:
                want_graph = bool(re.search(r'(demo=|data=)', a.query or ''))
                # P0 修（2026-09-18 Q7）：原实现在 `demo=`/`data=` 且**不带 `probe=1`** 时走
                # `!!(window.__cl && __cl.graph())` —— 但 app.js 只在 `probe=1` 分支里往
                # `window.__cl` 挂 `graph`（app.js:3156 `if (qs.get('probe') === '1')`）。
                # 此时 `__cl.graph` 是 undefined，`__cl.graph()` 抛 TypeError → CDP 返回
                # exceptionDetails 而非 value → ready 恒为 None → **每次都吃满 --timeout**
                # （实测 READY 240.0s，带 probe=1 仅 13.5s）。这不是页面慢，是探针抛异常。
                # 修法：安全调用 + 统一 `#loader.off` 兜底；只影响「等多久」，不参与任何功能断言。
                READY_EXPR = ("!!(window.__cl && ((window.__cl.graph ? window.__cl.graph() : null)"
                              " || document.querySelector('#loader.off')))")
                if want_graph:
                    ready = ws.call('Runtime.evaluate', expression=READY_EXPR, returnByValue=True).get('result', {}).get('value')
                else:
                    ready = ws.call('Runtime.evaluate', expression=READY_EXPR, returnByValue=True).get('result', {}).get('value')
                if ready and time.time() - t0 > 3: break
        el = time.time() - t0
        if want_test:
            if not res:
                je = ws.call('Runtime.evaluate', expression="(document.body.dataset.jserr||'')+' | '+(document.body.dataset.jsrej||'')", returnByValue=True).get('result', {}).get('value')
                print('TIMEOUT %.1fs · no cltest · jserr/jsrej: %s' % (el, je)); 
            else:
                d = json.loads(res)
                print('OK %.1fs · ms %s · jserr %s · jsrej %s' % (el, d.get('ms'), d.get('jserr'), d.get('jsrej')))
                if not a.quiet:
                    for st in d.get('steps', []): print('  ' + st)
        else:
            je = ws.call('Runtime.evaluate', expression="(document.body.dataset.jserr||'none')+' | '+(document.body.dataset.jsrej||'none')", returnByValue=True).get('result', {}).get('value')
            print('READY %.1fs · jserr/jsrej: %s' % (el, je))
        if a.ev:
            r = health_evaluate(ws, eval_errors, 'EVAL', a.ev, awaitPromise=True)
            if 'value' in r.get('result', {}):
                s = json.dumps(r.get('result', {}).get('value'), ensure_ascii=False)
                # 探针读数**不能截断**：调用方（tree_qc / visual）一律 json.loads 这一行，
                # 截断只会变成 "Unterminated string starting at char 0" 这种认不出根因的
                # 基础设施故障（PROBE 曾因此涨过 4KB）。
                # 上限只用来防真正的失控，触发时打的是**明确标记**而不是半截 JSON。
                if len(s) > EVAL_MAX:
                    print('EVAL-TOO-BIG %d chars (>%d)：探针返回体超限，读数不完整' % (len(s), EVAL_MAX))
                else:
                    print('EVAL:', s)
            else:
                print('EVAL:', r)
        if a.shot:
            if a.wait: time.sleep(a.wait)
            health_evaluate(ws, eval_errors, 'SHOT step', "window.__cl && __cl.scene.step(2)")
            shot = ws.call('Page.captureScreenshot', format='png')
            with open(a.shot, 'wb') as f: f.write(base64.b64decode(shot['data']))
            print('SHOT', a.shot, os.path.getsize(a.shot), 'bytes')
        # 第二段：同一页面、同一帧序列下再求值一次并再截一张（见 --shot2 的参数说明）。
        # 第一张与第二张之间只允许有「被测的那一个变量」变化，所以调用方要自己把动效冻住
        # （CLTreeSway.freeze）并在 ev2 里只步进固定帧数。
        if a.ev2:
            r2 = health_evaluate(ws, eval_errors, 'EVAL2', a.ev2, awaitPromise=True)
            if 'value' in r2.get('result', {}):
                s2 = json.dumps(r2.get('result', {}).get('value'), ensure_ascii=False)
                if len(s2) > EVAL_MAX:
                    print('EVAL2-TOO-BIG %d chars (>%d)' % (len(s2), EVAL_MAX))
                else:
                    print('EVAL2:', s2)
            else:
                print('EVAL2:', r2)
        if a.shot2:
            w2 = a.wait if a.wait2 is None else a.wait2
            if w2: time.sleep(w2)
            health_evaluate(ws, eval_errors, 'SHOT2 step', "window.__cl && __cl.scene.step(2)")
            shot2 = ws.call('Page.captureScreenshot', format='png')
            with open(a.shot2, 'wb') as f: f.write(base64.b64decode(shot2['data']))
            print('SHOT2', a.shot2, os.path.getsize(a.shot2), 'bytes')
        # 第三段：A/B/A 三拍门禁的收口拍。场址、机位、帧序列与前两拍完全同进程
        # （跨进程噪声地板在这里被彻底消掉），所以第三拍只用来度量
        # 残余漂移 d(A,A')，供调用方做 signal = d(A,B) − d(A,A') 的差分扣除。
        if a.ev3:
            r3 = health_evaluate(ws, eval_errors, 'EVAL3', a.ev3, awaitPromise=True)
            if 'value' in r3.get('result', {}):
                s3 = json.dumps(r3.get('result', {}).get('value'), ensure_ascii=False)
                if len(s3) > EVAL_MAX:
                    print('EVAL3-TOO-BIG %d chars (>%d)' % (len(s3), EVAL_MAX))
                else:
                    print('EVAL3:', s3)
            else:
                print('EVAL3:', r3)
        if a.shot3:
            w3 = a.wait if a.wait3 is None else a.wait3
            if w3: time.sleep(w3)
            health_evaluate(ws, eval_errors, 'SHOT3 step', "window.__cl && __cl.scene.step(2)")
            shot3 = ws.call('Page.captureScreenshot', format='png')
            with open(a.shot3, 'wb') as f: f.write(base64.b64decode(shot3['data']))
            print('SHOT3', a.shot3, os.path.getsize(a.shot3), 'bytes')
    except socket.timeout:
        # 明说是哪一种失败：CDP 调用等不到回音 ≠ 页面挂了。
        print('CDP-BUSY %.1fs · 一次 CDP 调用超过 %.0fs 没有返回：页面主线程仍被同步阻塞（聚焦态 + pump/warm 常见），'
              '不是页面崩溃。抬高 --timeout，或用 CL_CDP_TIMEOUT 显式指定。' % (time.time() - t0, sockto))
        raise SystemExit(3)
    finally:
        if ws and health_armed:
            health_rc = post_health(ws, eval_errors)
        try:
            if ws: ws.call('Browser.close')
        except Exception: pass
        time.sleep(0.3)
        # 1) 先杀浏览器主进程（正常路径足够）
        try: proc.kill()
        except Exception: pass
        try: proc.wait(timeout=5)
        except Exception: pass
        # 2) 兜底扫尾：只按**本次自己的** user-data-dir 指纹抓逃逸孤儿。
        #    注意必须带 ud 限定 —— 全局 pkill 会误杀 -j 4 下并发兄弟套件的 Chrome。
        #
        #    ⚠ Q7 二次修（2026-09-18）：这里的模式**必须以 `--` 与选项隔开**。
        #    原写法 `pkill -9 -f --user-data-dir=<ud>` 会被 pkill 当成**选项**解析：
        #        pkill: -9: illegal option -- -   (rc=2)
        #    而 rc 又被下面 `except Exception: pass` 吞掉 —— 于是这条兜底**从未生效过一次**，
        #    每跑一次无头就漏一只 SwiftShader GPU helper（各烧满一核）→ 正反馈 →
        #    load 顶到 70+、计时类断言假红（perf_budget R14.Q5 曾因此假 FAIL）。
        #    修法：加 `--` 分隔符，并让 rc≠0/1（用法错误）显式报警而非静默。
        try:
            rc = subprocess.run(['pkill', '-9', '-f', '--', '--user-data-dir=' + ud],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode
            # 0=已收割；1=无匹配（正常，说明主进程 kill 已够）；其余=用法/系统错误，必须可见。
            if rc not in (0, 1):
                print('WARN headless: 兜底 pkill 返回 rc=%d（非 0/1），本次可能有孤儿逃逸' % rc,
                      file=sys.stderr)
        except Exception as e:
            print('WARN headless: 兜底 pkill 调用失败：%r' % (e,), file=sys.stderr)
        shutil.rmtree(ud, ignore_errors=True)
    return health_rc

if __name__ == '__main__': sys.exit(main())
