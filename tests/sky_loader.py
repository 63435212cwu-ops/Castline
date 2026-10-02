#!/usr/bin/env python3
"""读取幕验收（开书：读取材料 → 推演剧情线 → 排布星座 → 点亮光层 → 揭幕）。

L1 开机（数据链接）：第一次出现就是不透明的幕（is-instant），旧外围不从幕后透出；读完材料后书名写上。
L2 阶段按序推进、进度只增不减并到 1；图谱就绪后幕在 3 s 内离场并收起（hidden）。
L3 揭幕编排：幕开始离场之前星没有点亮（ignite≈0），离场后开始点亮、几秒内点满；深空在幕收起后才浮现（开书时 hidden）。
L4 换书（作品库里点另一部）：幕淡入（非 instant），淡到不透明之后才重建（mount 晚于幕出现 ≥ 350 ms），书名换成新书，最后揭幕。
L5 出错：数据链接指向不存在的文件 → 幕收起，不卡在屏幕上。
L6 减弱动效：幕不做离场动画，图谱就绪后直接收起。

用法：CL_GPU=1 python3 -s tests/sky_loader.py [--base http://127.0.0.1:8765]
"""
import argparse, json, os, subprocess, sys, tempfile, shutil, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import headless  # noqa: E402

SANGUO_KEY = 'a935953b2678a80b352091d5'

REC_JS = r"""(function(){
  var log = window.__ldLog = [], t0 = performance.now(), last = '';
  function now(){ return Math.round(performance.now() - t0); }
  document.addEventListener('cl:graph-loading', function(e){ var d = e.detail || {}; log.push({ t: now(), ev: 'stage', stage: d.stage, frac: d.frac }); });
  document.addEventListener('cl:graph-ready', function(){ log.push({ t: now(), ev: 'ready', title: window.CLApp && CLApp.graph() ? CLApp.graph().title : '' }); });
  /* 30 ms 轮询幕的状态（类名 / 可见 / 阶段 / 书名）与星、深空的状态，变了就记一条 */
  setInterval(function(){
    var el = document.querySelector('.skd-loader'); if (!el) return;
    var st = window.CLSkyDeep && CLSkyDeep.enabled() ? CLSkyDeep.stats() : null;
    var rec = { cls: el.className, hidden: el.hidden, stage: (el.querySelector('.skd-loader__stage') || {}).textContent, title: (el.querySelector('.skd-loader__title') || {}).textContent };
    var key = JSON.stringify(rec); if (key === last) return; last = key;
    rec.t = now(); rec.ev = 'cls'; rec.op = getComputedStyle(el).opacity; rec.p = +(el.style.getPropertyValue('--p') || 0);
    rec.ignite = st && st.stars ? st.stars.ignite : null; rec.cosmos = st && st.cosmos ? st.cosmos.state : null;
    log.push(rec);
  }, 30);
})();"""


class Browser:
    def __init__(self, w=1440, h=900, reduce=False):
        self.w, self.h, self.reduce = w, h, reduce
        self.ud = tempfile.mkdtemp(prefix='cl-loader-')
        self.proc = self.ws = None

    def start(self):
        gl = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization'] if os.environ.get('CL_GPU') == '1' else ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
        self.proc = subprocess.Popen([headless.CH, '--headless=new'] + gl + ['--hide-scrollbars', '--window-size=%d,%d' % (self.w, self.h), '--user-data-dir=' + self.ud,
                                      '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking', 'about:blank'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        tabs = None
        for _ in range(200):
            try:
                port = int(open(os.path.join(self.ud, 'DevToolsActivePort')).read().splitlines()[0])
                tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2).read())
                break
            except Exception:
                time.sleep(0.1)
        page = [t for t in tabs if t.get('type') == 'page'][0]
        self.ws = headless.WS(page['webSocketDebuggerUrl'], timeout=150)
        self.ws.call('Runtime.enable'); self.ws.call('Page.enable')
        self.ws.call('Emulation.setDeviceMetricsOverride', width=self.w, height=self.h, deviceScaleFactor=1, mobile=False)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=REC_JS)
        if self.reduce:
            self.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])

    def ev(self, expr):
        r = self.ws.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        if r.get('exceptionDetails'):
            raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:600])
        return r.get('result', {}).get('value')

    def close(self):
        try:
            self.ws.call('Browser.close')
        except Exception:
            pass
        try:
            if self.proc and self.proc.poll() is None:
                os.killpg(self.proc.pid, 15)
        except Exception:
            pass
        shutil.rmtree(self.ud, ignore_errors=True)


def first(log, pred):
    for x in log:
        if pred(x):
            return x
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    a = ap.parse_args()
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:800]))

    # ---- L1–L3 开机 + L4 换书
    b = Browser(); b.start()
    try:
        b.ws.call('Page.navigate', url=a.base + '/?data=data/sample-saga.json&sky=1&probe=1')
        time.sleep(8)
        log = b.ev('JSON.stringify(window.__ldLog)'); log = json.loads(log or '[]')
        cls = [x for x in log if x['ev'] == 'cls']
        st = [x for x in log if x['ev'] == 'stage']
        rd = first(log, lambda x: x['ev'] == 'ready')
        c0 = cls[0] if cls else {}
        # 30 ms 轮询可能错过很短的「推演剧情线」：取读取材料之后的第一条记录（此时数据已解析、书名已知）
        titled = first(cls, lambda x: x.get('stage') in ('推演剧情线', '排布星座', '点亮光层', '揭幕'))
        check('L1 boot curtain is opaque from its first frame (is-instant); the book title is on it once the material is read', 'is-instant' in (c0.get('cls') or '') and float(c0.get('op') or 0) > 0.99 and titled and titled.get('title'), {'first': c0, 'titled': titled})
        order = ['读取材料', '推演剧情线', '排布星座', '点亮光层', '揭幕']
        seq = []
        for x in cls:
            if x.get('stage') in order and (not seq or seq[-1] != x['stage']):
                seq.append(x['stage'])
        fr = [x['p'] for x in cls]
        ok_order = len(seq) >= 3 and seq[-1] == '揭幕' and all(order.index(seq[i]) < order.index(seq[i + 1]) for i in range(len(seq) - 1)) and all(fr[i] <= fr[i + 1] + 1e-6 for i in range(len(fr) - 1))
        info = b.ev("JSON.stringify({L: document.querySelector('.skd-loader') ? { hidden: document.querySelector('.skd-loader').hidden, frac: +(document.querySelector('.skd-loader').style.getPropertyValue('--p') || 0) } : null, deep: CLSkyDeep.stats().cosmos.state, ign: CLSkyDeep.stats().stars.ignite })")
        info = json.loads(info or '{}')
        leave = first(cls, lambda x: 'is-leaving' in (x.get('cls') or ''))
        gone = first(cls, lambda x: x.get('hidden'))
        check('L2 stages in order, progress reaches 1, curtain leaves and hides within 3 s of graph-ready', ok_order and (info.get('L') or {}).get('hidden') is True and (info.get('L') or {}).get('frac') == 1 and rd and gone and gone['t'] - rd['t'] < 3000,
              {'seq': seq, 'fr': fr, 'ready': rd, 'gone': gone, 'info': info})
        check('L3 stars stay dark until the curtain starts leaving, then ignite; deep sky hidden during the curtain, shown after', leave is not None and (leave.get('ignite') is None or leave.get('ignite') < 0.3) and info.get('ign', 0) > 0.95 and
              (leave.get('cosmos') in (None, 'hidden')) and info.get('deep') == 'show', {'leave': leave, 'info': info})
        # L4 换书
        b.ev("window.__ldLog.length = 0")
        clicked = b.ev("(async()=>{ CLApp.internal().openLib(); await new Promise(r=>setTimeout(r,1500)); var c = document.querySelector('[data-key=\"%s\"]'); if (!c) return false; c.click(); return true; })()" % SANGUO_KEY)
        time.sleep(7)
        log = json.loads(b.ev('JSON.stringify(window.__ldLog)') or '[]')
        cls = [x for x in log if x['ev'] == 'cls']
        shown = first(cls, lambda x: not x.get('hidden') and 'skd-loader' in (x.get('cls') or ''))
        rd = first(log, lambda x: x['ev'] == 'ready')
        fin = b.ev("JSON.stringify({ title: CLApp.graph().title, L: document.querySelector('.skd-loader').hidden, deep: CLSkyDeep.stats().cosmos.state })")
        fin = json.loads(fin or '{}')
        check('L4 library switch: curtain fades in (not instant), rebuild waits until it is opaque, new title, then reveal', clicked and shown and 'is-instant' not in (shown.get('cls') or '') and rd and rd['t'] - shown['t'] >= 350 and fin.get('title') == '三国演义' and fin.get('L') is True and fin.get('deep') == 'show',
              {'clicked': clicked, 'shown': shown, 'ready': rd, 'fin': fin, 'titles': [x.get('title') for x in cls][:3]})
        h = b.ev(headless.POST_HEALTH_JS)
        check('health (boot + switch)', h and h.get('jserr') == 'none' and h.get('jsrej') == 'none' and not h.get('shaderErrors') and not h.get('missing'), h)
    finally:
        b.close()

    # ---- L5 出错
    b = Browser(); b.start()
    try:
        b.ws.call('Page.navigate', url=a.base + '/?data=data/cache/does-not-exist.json&sky=1&probe=1')
        time.sleep(4)
        v = json.loads(b.ev("JSON.stringify({ L: document.querySelector('.skd-loader') ? document.querySelector('.skd-loader').hidden : 'none' })") or '{}')
        check('L5 missing data file: curtain does not stay on screen', v.get('L') in (True, 'none'), v)
    finally:
        b.close()

    # ---- L6 减弱动效
    b = Browser(reduce=True); b.start()
    try:
        b.ws.call('Page.navigate', url=a.base + '/?data=data/sample-saga.json&sky=1&probe=1')
        time.sleep(6)
        log = json.loads(b.ev('JSON.stringify(window.__ldLog)') or '[]')
        cls = [x for x in log if x['ev'] == 'cls']
        v = json.loads(b.ev("JSON.stringify({ L: document.querySelector('.skd-loader') ? document.querySelector('.skd-loader').hidden : 'none', ign: CLSkyDeep.stats().stars.ignite })") or '{}')
        check('L6 reduced motion: no leaving animation, curtain hidden, stars lit', not any('is-leaving' in (x.get('cls') or '') for x in cls) and v.get('L') in (True, 'none') and v.get('ign', 0) > 0.95, {'cls': [x.get('cls') for x in cls], 'v': v})
    finally:
        b.close()

    n = sum(1 for _, x in res if x)
    print(('SKY-LOADER OK' if n == len(res) else 'SKY-LOADER FAIL') + ' · %d/%d' % (n, len(res)))
    sys.exit(0 if n == len(res) else 1)


if __name__ == '__main__':
    main()
