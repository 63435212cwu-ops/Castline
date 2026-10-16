#!/usr/bin/env python3
"""无头验收驾驭器（零依赖 · CDP over WebSocket）。

Chrome 152 的 `--headless=new --dump-dom` 在 rAF 静止页面上不退出，且在 load 事件就 dump，
拿不到异步自测结果；这里改用 DevTools 协议：起 Chrome → 打开页面 → 轮询
`document.body.dataset.cltest` → 可选截图 → 杀进程。

用法：
  python3 -s tests/headless.py "demo=1&probe=1&pump=1&warm=140&autotest=1"
  python3 -s tests/headless.py "demo=1&probe=1&pump=1&warm=60&sel=沈曜" --shot /tmp/castline-shots/focus.png --wait 4
  python3 -s tests/headless.py "<query>" --eval "JSON.stringify(__cl.scene.crown())"
选项：--timeout 秒（默认 240，可用 CL_TIMEOUT 覆盖）· --size 1440x900 · --dpr 2（模拟 Retina）· --shot 文件 · --wait 秒（截图前额外等待）· --eval 表达式（自测完成后求值）· --url 覆盖地址
收尾：READY 格式不变；所有 eval/shot 后输出 POST 与 POST-HEALTH JSON。
健康退出 0；实际 JS/Promise/shader/eval 异常退出 1；健康检测缺失/失败退出 2。
"""
import sys, os, json, time, socket, base64, struct, subprocess, shutil, argparse, html, re, signal, tempfile
import urllib.request

CH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BROWSER_PROFILE_FLAGS = ['--password-store=basic', '--use-mock-keychain']

EVAL_MAX = 2000000

HEALTH_INIT_JS = r"""(function () {
    var h = {jserr: [], jsrej: [], domContentLoaded: document.readyState === 'complete'};
    window.__headlessHealth = h;
    document.addEventListener('DOMContentLoaded', function () { h.domContentLoaded = true; }, {once: true});
    function describe(e) { return String(e && (e.stack || e.message) || e); }
    window.addEventListener('error', function (e) {
        h.jserr.push(describe(e.error || e.message || 'unknown error'));
    });
    window.addEventListener('unhandledrejection', function (e) {
        h.jsrej.push(describe(e.reason));
    });
})();"""

READINESS_JS = r"""(function () {
    var out = {ready: false, missing: [], documentState: document.readyState};
    var h = window.__headlessHealth, q = new URLSearchParams(location.search);
    var graphWanted = !!q.get('data') || q.get('demo') === '1';
    var probeWanted = q.get('probe') === '1';
    var skyWanted = q.get('shell') !== 'atlas' &&
        (q.get('shell') === 'sky' || !!q.get('sky') || q.get('probe') !== '1');
    out.graphWanted = graphWanted; out.probeWanted = probeWanted; out.skyWanted = skyWanted;
    if (!h || h.domContentLoaded !== true) out.missing.push('DOMContentLoaded');
    if (!document.body) out.missing.push('document.body');
    var A = window.CLApp, scene = A && typeof A.scene === 'function' ? A.scene() : null;
    if (!scene || typeof scene.shaderErrors !== 'function') out.missing.push('CLApp.scene().shaderErrors');
    if (graphWanted) {
        if (!A || typeof A.graph !== 'function' || !A.graph()) out.missing.push('CLApp.graph()');
        if (!document.querySelector('#loader.off')) out.missing.push('#loader.off');
    }
    if (skyWanted) {
        var sky = window.CLSky, chrome = window.CLSkyChrome;
        if (!sky || typeof sky.enabled !== 'function' || !sky.enabled()) out.missing.push('CLSky.enabled()');
        if (graphWanted && (!sky || typeof sky.model !== 'function' || !sky.model())) out.missing.push('CLSky.model()');
        if (!chrome || typeof chrome.enabled !== 'function' || !chrome.enabled()) out.missing.push('CLSkyChrome.enabled()');
    }
    if (probeWanted && (!window.__cl || !window.__cl.scene ||
        typeof window.__cl.scene.shaderErrors !== 'function')) out.missing.push('__cl.scene.shaderErrors');
    out.ready = !out.missing.length;
    return out;
})()"""

SHOT_STEP_JS = "window.CLApp && typeof CLApp.scene === 'function' && CLApp.scene().step(2)"


class ReadinessTimeout(Exception):
    """The expected page entry never completed; eval and shots must not run."""


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
            var probeWanted = new URLSearchParams(location.search).get('probe') === '1';
            var app = window.CLApp;
            var scene = probeWanted ? window.__cl && window.__cl.scene :
                app && typeof app.scene === 'function' ? app.scene() : null;
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
    actual = bool(eval_errors or health['shaderErrors'] or any(health['errorCounts'].values()) or any(
        health[key] not in (None, '', 'none') for key in ('jserr', 'jsrej')))
    code = 1 if actual else (2 if health['missing'] or health['probeErrors'] else 0)
    health['ok'] = code == 0
    health['exitCode'] = code
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
        if method == 'Page.navigate' or method.startswith('Input.dispatch'):
            self.call('Page.bringToFront')
        self.id += 1; my = self.id; self.send({'id': my, 'method': method, 'params': params})
        while True:
            m = self.recv()
            if m.get('id') == my:
                if 'error' in m: raise RuntimeError(m['error'])
                return m.get('result', {})

RAF_CAPACITY_JS = r"""(async()=>{
  /* 每帧画一笔 8 px 画布再读间隔：纯空页（零绘制）下 headless 对 BeginFrame 欠发，
     rAF 会被钳到 ~57 Hz 造成「机器不足」假象（实测：无绘制 57.3 / 微绘制 17445 fps 同机）。
     微绘制让探测读到真实的供给上限，同时负载可忽略。 */
  var cv=document.createElement('canvas'); cv.width=cv.height=8;
  (document.body||document.documentElement).appendChild(cv);
  var g2=cv.getContext('2d'), F=%d, iv=[], last, i;
  last=await new Promise(function(r){requestAnimationFrame(r);});
  for(i=0;i<F;i++){ g2.fillStyle='rgb('+(i&255)+',0,0)'; g2.fillRect(0,0,8,8);
    var n=await new Promise(function(r){requestAnimationFrame(r);}); iv.push(n-last); last=n; }
  cv.parentNode && cv.parentNode.removeChild(cv);
  /* 首帧是启动追赶帧，剔除——与 sky_dial C_RUN(iv.shift())/sky_opening o8(g1=gaps.slice(1))同一口径 */
  iv.shift();
  var s=iv.slice().sort(function(a,b){return a-b;});
  return {n:iv.length, fps:+(1000*iv.length/iv.reduce(function(a,b){return a+b;},0)).toFixed(1),
    p95:+s[Math.floor(s.length*0.95)].toFixed(2), max:+s[s.length-1].toFixed(2),
    over50:iv.filter(function(x){return x>50;}).length};
})()"""


def raf_capacity(ws, frames=180):
    """机器 rAF 供给自测（环境能力护栏的探测器一：同供给探测）：在**当前页**（约定调用方在
    about:blank 空页上调用）跑 n 帧微绘制空循环，读帧间隔。口径与被护栏的断言一致——空页
    微绘制都喂不满阈值时，该断言量到的是机器供给，不是产品；这时调用方应显式 REPORT，而不是
    判红或暗松阈值。注意它只证「整机饿死」；「该负载本身在本机塞不进一个 vsync」属负载可达性，
    由调用方用套件自己的负载读数证（如 sky_dial 用不锁帧兄弟跑的 p95）——两者互不替代。
    探针本身失败返回 None：调用方必须按「无法证明环境不足」处理——照常按原阈值判（宁严不松）。"""
    try:
        r = ws.call('Runtime.evaluate', expression=RAF_CAPACITY_JS % frames,
                    awaitPromise=True, returnByValue=True)
        v = r.get('result', {}).get('value')
        return v if isinstance(v, dict) and isinstance(v.get('fps'), (int, float)) else None
    except Exception:
        return None


def _orphan_user_data_dirs():
    """从**进程表**列出所有 `--user-data-dir=...castline-cdp-<pid>`，返回 {属主pid: 目录}。

    为什么不沿用「扫 `tempfile.gettempdir()`」那个写法（2026-09-18 Q7 的原实现）：它假定
    本次运行的 TMPDIR 就是历次运行的 TMPDIR。但本仓约定测试一律经 `run-with-storage.py`
    运行，而**它给每一次运行开一个全新的运行目录并把它设成 TMPDIR**
    （形如 `.../20261016-140642-310342-41310/临时/`）。于是下一次运行 glob 到的是**它自己**
    的空 TMPDIR，上一次运行漏下的 `castline-cdp-41310` 永远扫不到。
    2026-10-16 实测正是这样漏下两只孤儿（合计 ~850% CPU、load 顶到 22.8），
    而不是它们「属主还活着」——原先的判据没错，错的是**发现渠道**。
    改从 `ps` 发现：无论 TMPDIR 怎么轮换，正在烧 CPU 的 Chrome 一定在进程表里。
    """
    try:
        out = subprocess.run(['ps', '-Aww', '-o', 'pid=,command='],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return {}
    found = {}
    for line in out.splitlines():
        m = re.search(r'--user-data-dir=(\S*?/castline-cdp-(\d+))(?=\s|$)', line)
        if m:
            found[int(m.group(2))] = m.group(1)
    return found


def reap_orphans():
    """开机自愈：收割「属主已死」的 castline 无头孤儿（Q7 修 · 2026-09-18；2026-10-16 改为进程表发现）。

    为什么需要它：下面的 finally 清理只在**本进程能跑到 finally** 时生效。但本仓约 40 个
    套件（perf_budget / legend_tip / abyss_p6-8 / twig_phase …）是用**裸
    `subprocess.run(..., timeout=)`** 调本脚本的 —— 一旦超时，`subprocess.run` 只
    SIGKILL 掉**本进程**（Python 包装层），Chrome 与它的 SwiftShader GPU helper 会被
    orphan 到 launchd（ppid=1）**继续烧满一整核**，而 finally 永远不会执行。

    这会形成正反馈：泄漏越多 → 机器越慢 → 越多套件超时 → 泄漏越多。实测一次会话累积
    **8 只**、约 **760% CPU**、load 顶到 70+，直接导致 `perf_budget` 的 `R14.Q5 plot render`
    从 240~450ms 漂到 984ms（预算 600）→ 报 FAIL，**是一次假回归**：清掉孤儿后连跑两次
    同为 OK。2026-10-16 再次实测同形态：两只孤儿 ~850% CPU、load 22.8，全部「就绪预算超时 /
    单次 CDP 调用 >100s」现象都由它而来，**不是产品回归**。

    判据不变：只收割**属主 python 已死**的那批；属主存活即视为并发兄弟（`runall -j 4`）→ 跳过不碰。
    """
    for pid, d in _orphan_user_data_dirs().items():
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, 0)
            continue
        except PermissionError:
            continue
        except ProcessLookupError:
            pass
        try:
            subprocess.run(['pkill', '-9', '-f', '--', '--user-data-dir=' + d],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except Exception:
            pass
        shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('query'); ap.add_argument('--timeout', type=float, default=float(os.environ.get('CL_TIMEOUT', '240'))); ap.add_argument('--size', default='1440x900')
    ap.add_argument('--shot'); ap.add_argument('--wait', type=float, default=0); ap.add_argument('--eval', dest='ev'); ap.add_argument('--url', default=os.environ.get('CL_URL', 'http://127.0.0.1:8000/'))
    ap.add_argument('--eval2', dest='ev2'); ap.add_argument('--shot2'); ap.add_argument('--wait2', type=float, default=None)
    ap.add_argument('--eval3', dest='ev3'); ap.add_argument('--shot3'); ap.add_argument('--wait3', type=float, default=None)
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--dpr', type=float, default=0, help='设备像素比（默认 1，如 2 = Retina），截图按设备像素输出')
    ap.add_argument('--reduce', action='store_true',
                    help='模拟 prefers-reduced-motion: reduce（树下各层会跳过生长/呼吸动效）。'
                         '只能在页面导航前设好，因为各层是在 build 时读 matchMedia 的。')
    a = ap.parse_args()
    reap_orphans()
    w, h = a.size.split('x'); port = 9400 + os.getpid() % 500; ud = os.path.join(tempfile.gettempdir(), 'castline-cdp-%d' % os.getpid())
    gl = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization'] if os.environ.get('CL_GPU') == '1' else ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
    head = [] if os.environ.get('CL_WINDOWED') == '1' else ['--headless=new']
    cmd = [CH] + head + gl + BROWSER_PROFILE_FLAGS + ['--hide-scrollbars', '--window-size=%s,%s' % (w, h),
           '--user-data-dir=' + ud, '--remote-debugging-port=%d' % port, '--no-first-run', '--disable-background-networking', 'about:blank']
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
        ws.call('Emulation.setDeviceMetricsOverride', width=int(w), height=int(h), deviceScaleFactor=a.dpr or 1, mobile=False)
        if a.reduce:
            ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])
        url = a.url + ('?' + a.query if a.query else '')
        ws.call('Page.navigate', url=url)
        res = None; expr = "document.body && document.body.dataset.cltest || ''"
        want_test = 'autotest=' in a.query
        ready_status = {'ready': False, 'missing': ['readiness was not evaluated']}
        while time.time() - t0 < a.timeout:
            time.sleep(0.5)
            r = ws.call('Runtime.evaluate', expression=expr, returnByValue=True)
            v = r.get('result', {}).get('value') or ''
            if v: res = v
            r = health_evaluate(ws, eval_errors, 'READY', READINESS_JS)
            value = r.get('result', {}).get('value')
            if isinstance(value, dict):
                ready_status = value
            else:
                ready_status = {'ready': False, 'missing': ['readiness result missing or malformed']}
            if ready_status.get('ready') is True and (not want_test or res):
                break
        if ready_status.get('ready') is not True or want_test and not res:
            if want_test and not res: ready_status.setdefault('missing', []).append('dataset.cltest')
            print('TIMEOUT %.1fs · NOT-READY: %s' % (
                time.time() - t0, json.dumps(ready_status, ensure_ascii=False)), flush=True)
            raise ReadinessTimeout()
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
                if len(s) > EVAL_MAX:
                    print('EVAL-TOO-BIG %d chars (>%d)：探针返回体超限，读数不完整' % (len(s), EVAL_MAX))
                else:
                    print('EVAL:', s)
            else:
                print('EVAL:', r)
        if a.shot:
            if a.wait: time.sleep(a.wait)
            health_evaluate(ws, eval_errors, 'SHOT step', SHOT_STEP_JS)
            shot = ws.call('Page.captureScreenshot', format='png')
            with open(a.shot, 'wb') as f: f.write(base64.b64decode(shot['data']))
            print('SHOT', a.shot, os.path.getsize(a.shot), 'bytes')
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
            health_evaluate(ws, eval_errors, 'SHOT2 step', SHOT_STEP_JS)
            shot2 = ws.call('Page.captureScreenshot', format='png')
            with open(a.shot2, 'wb') as f: f.write(base64.b64decode(shot2['data']))
            print('SHOT2', a.shot2, os.path.getsize(a.shot2), 'bytes')
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
            health_evaluate(ws, eval_errors, 'SHOT3 step', SHOT_STEP_JS)
            shot3 = ws.call('Page.captureScreenshot', format='png')
            with open(a.shot3, 'wb') as f: f.write(base64.b64decode(shot3['data']))
            print('SHOT3', a.shot3, os.path.getsize(a.shot3), 'bytes')
    except ReadinessTimeout:
        health_rc = 2
    except socket.timeout:
        print('CDP-BUSY %.1fs · 一次 CDP 调用超过 %.0fs 没有返回：页面主线程仍被同步阻塞（聚焦态 + pump/warm 常见），'
              '不是页面崩溃。抬高 --timeout，或用 CL_CDP_TIMEOUT 显式指定。' % (time.time() - t0, sockto))
        raise SystemExit(3)
    finally:
        if ws and health_armed:
            post_rc = post_health(ws, eval_errors)
            health_rc = 1 if post_rc == 1 else max(health_rc, post_rc)
        try:
            if ws: ws.call('Browser.close')
        except Exception: pass
        time.sleep(0.3)
        try: proc.kill()
        except Exception: pass
        try: proc.wait(timeout=5)
        except Exception: pass
        try:
            rc = subprocess.run(['pkill', '-9', '-f', '--', '--user-data-dir=' + ud],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode
            if rc not in (0, 1):
                print('WARN headless: 兜底 pkill 返回 rc=%d（非 0/1），本次可能有孤儿逃逸' % rc,
                      file=sys.stderr)
        except Exception as e:
            print('WARN headless: 兜底 pkill 调用失败：%r' % (e,), file=sys.stderr)
        shutil.rmtree(ud, ignore_errors=True)
    return health_rc

if __name__ == '__main__': sys.exit(main())
