#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星空预演实验室验收：9 帧故事板 · 中断 · 读图模式 · 深链往返 · 样例往返 · 栏位不遮挡 · 三视口截图。

真实页面 + 真实渲染器（CL_GPU=1 走 Metal 真 GPU，否则 SwiftShader），断言全部来自页面 DOM / 几何 / 状态；
期望值由页面内独立重算（不读实验室自己的 frames()）；不调用模型、不写 data/（前后逐文件核对 mtime）。
URL 一律带 sky=1&probe=1（只带 probe=1 会进入旧壳回归）。

用法：
  CL_GPU=1 python3 -s tests/sky_lab.py --base http://127.0.0.1:8782 [--shots /tmp/castline-shots/sky-lab] [--only saga,xiyou,820,390,reduce]
末行：SKY-LAB OK · 通过数/总数 ，或 SKY-LAB FAIL 与失败明细；退出码非零即失败。
"""
import argparse
import base64
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import headless  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ['C0', 'C1', 'P0', 'P1', 'P2', 'P3', 'K0', 'K1', 'K2']
SAGA = 'data/sample-saga.json'
MID = 'data/sample-mid.json'
XIYOU = 'data/cache/d16db79a529a1727352091d5.json'


def q(data, extra=''):
    return '?data=%s&sky=1&probe=1%s' % (data, extra)


# 记录本页所有网络请求的方法与地址（测试探针，不进产品代码）：样例往返中不得出现写入 / 分析请求。
NET_INIT_JS = r"""(function () {
  var log = []; window.__l1net = log;
  var of = window.fetch;
  if (of) window.fetch = function (u, o) { try { log.push([String(o && o.method || (u && u.method) || 'GET').toUpperCase(), String(u && u.url || u)]); } catch (e) {} return of.apply(this, arguments); };
  var oo = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (m, u) { try { log.push([String(m || 'GET').toUpperCase(), String(u)]); } catch (e) {} return oo.apply(this, arguments); };
  if (navigator.sendBeacon) { var ob = navigator.sendBeacon.bind(navigator); navigator.sendBeacon = function (u, d) { log.push(['BEACON', String(u)]); return ob(u, d); }; }
})();"""

# 页面内独立重算每帧应取的对象（与实验室的实现无关，只读 CLSky.model() / CLApp.graph()）
EXPECT_JS = r"""(function(){
  var M = CLSky.model(), G = CLApp.graph();
  var g2 = (M.groupings || []).filter(function(x){ return x.key !== 'camp'; })[0] || null;
  var main = null; M.mains.forEach(function(m){ if (!main || m.n > main.n) main = m; });
  var br = M.lines.filter(function(l){ return l.rank === 0 && l.named; })[0] || null;
  var top = null; G.characters.forEach(function(c){ if (c.importanceKnown === false || typeof c.importance !== 'number') return; if (!top || c.importance > top.importance) top = c; });
  return { group2: g2 ? g2.key : null, group2Label: g2 ? g2.label : null, main: main ? String(main.id) : null, mainLabel: main ? main.label : null, mainN: main ? main.n : null,
    branch: br ? String(br.id) : null, branchLabel: br ? br.label : null, branchCast: br ? br.cast.length : null, mid: Math.floor(M.nCh / 2), nCh: M.nCh,
    top: top ? top.name : null, title: G.title, chars: G.characters.length, lines: M.total };
})()"""

PROBE_JS = r"""(function(){
  var s = CLSky.state(), d = CLSky.disc(), ds = d.stats(), C = CLSkyCompass, cs = C.stats();
  var litEv = [].map.call(document.querySelectorAll('.sky-compass .skc-ev.is-on'), function(e){ return e.getAttribute('data-ev'); });
  var fr = CLSkyLab.frames(), ans = {}; fr.forEach(function(f){ ans[f.id] = f.answer; });
  return { mode: s.mode, plot: s.plot, compass: s.compass, group: s.group, cursor: s.cursor, playing: s.playing, discState: ds.state, hover: d.hover(), focused: d.focused(),
    tethers: ds.tethers, lines: ds.lines, cstats: cs, sats: cs.open ? C.satellites().map(function(x){ return x.name; }) : [], keys: cs.open ? C.keyEvents() : [],
    litEv: litEv, litSat: document.querySelectorAll('.sky-compass .skc-sat.is-lit').length, frame: CLSkyLab.current(), lab: CLSkyLab.stats(), snap: CLSky.snapshot(), answers: ans,
    card: { id: document.querySelector('#skyLab .skl-card-id').textContent, q: document.querySelector('#skyLab .skl-q').textContent, a: document.querySelector('#skyLab .skl-a').textContent } };
})()"""

# 主体外接盒（星座：投影星点；星盘：刻度环；罗盘：晶体 + 关系对象 + 事件链）与实验室各部件的交叠比例
BOX_JS = r"""(function(){
  var s = CLSky.state(), box = null, W = innerWidth, H = innerHeight;
  function r2(r){ return { l: r.left, t: r.top, r: r.right, b: r.bottom }; }
  function grow(b, x, y){ if (!b) return { l: x, t: y, r: x, b: y }; b.l = Math.min(b.l, x); b.t = Math.min(b.t, y); b.r = Math.max(b.r, x); b.b = Math.max(b.b, y); return b; }
  if (s.mode === 'compass') {
    var cb = CLApp.scene().crownScreenBounds && CLApp.scene().crownScreenBounds(); if (cb && isFinite(cb.left)) { box = grow(box, cb.left, cb.top); box = grow(box, cb.right, cb.bottom); }
    var L = CLSkyCompass._layout(); if (L) { L.sats.forEach(function(p){ if (isFinite(p.x)) box = grow(box, p.x, p.y); }); L.dots.forEach(function(p){ if (isFinite(p.x)) box = grow(box, p.x, p.y); }); }
  } else if (s.plot) {
    var ring = document.querySelector('.sky-disc .sd-ring'); if (ring) box = r2(ring.getBoundingClientRect());
  } else {
    var sc = CLApp.scene(), cam = sc.camera, v3 = new THREE.Vector3();
    CLApp.graph().characters.forEach(function(ch){ var nd = sc.nodeOf('c:' + ch.name); if (!nd || !nd.g || !nd.g.visible) return; nd.g.getWorldPosition(v3); v3.project(cam); if (v3.z > 1) return;
      box = grow(box, (v3.x + 1) * W / 2, (1 - v3.y) * H / 2); });
  }
  if (box) { box.l = Math.max(0, box.l); box.t = Math.max(0, box.t); box.r = Math.min(W, box.r); box.b = Math.min(H, box.b); }
  var lab = document.getElementById('skyLab'), parts = [];
  if (lab && !lab.hidden) lab.querySelectorAll('.skl-tag,.skl-panel').forEach(function(e){ if (getComputedStyle(e).display === 'none') return; parts.push(r2(e.getBoundingClientRect())); });
  var area = box ? Math.max(1, (box.r - box.l) * (box.b - box.t)) : 0, inter = 0, hmax = 0;
  parts.forEach(function(p){ hmax = Math.max(hmax, p.b - p.t); if (!box) return; var w = Math.max(0, Math.min(p.r, box.r) - Math.max(p.l, box.l)), h = Math.max(0, Math.min(p.b, box.b) - Math.max(p.t, box.t)); inter += w * h; });
  return { mode: s.mode, plot: s.plot, box: box, parts: parts, ratio: box ? +(inter / area).toFixed(4) : null, heightRatio: +(hmax / H).toFixed(4), open: CLSkyLab.stats().open, layout: CLSkyLab.stats().layout,
    sw: document.documentElement.scrollWidth, W: W, H: H };
})()"""

# 读取幕（开篇）离场之前，文档级捕获的「点击 / 按键跳过揭幕」会吃掉第一下点击：就绪 = 图谱建好且幕已收起
READY_JS = "!!(window.CLSky && CLSky.model() && window.CLSkyLab && CLSkyLab.stats().built && document.getElementById('skyLabBtn') && window.CLSkyCompass && !Array.prototype.some.call(document.querySelectorAll('.skd-loader'), function (e) { return !e.hidden; }))"
LINK_DONE_JS = "!!(window.CLSkyLab && CLSkyLab.stats().link !== null && !CLSkyLab.stats().running)"
SNAP_KEYS = ['v', 'group', 'plot', 'compass', 'cursor', 'line']


class Browser:
    """一条 Chrome 生命周期；CL_GPU=1 与 headless.py 同口径走 Metal；视口用设备度量覆盖，窄屏宽度才是真 390。"""

    def __init__(self, w, h, reduce=False):
        self.w, self.h, self.reduce = w, h, reduce
        self.ud = tempfile.mkdtemp(prefix='l1-skylab-')
        self.proc = self.ws = None

    def start(self):
        gl = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization'] if os.environ.get('CL_GPU') == '1' else ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
        cmd = [headless.CH, '--headless=new'] + gl + ['--hide-scrollbars', '--window-size=%d,%d' % (max(self.w, 500), self.h), '--user-data-dir=' + self.ud,
                                                      '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking', 'about:blank']
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        tabs = None
        for _ in range(200):
            try:
                port = int(open(os.path.join(self.ud, 'DevToolsActivePort')).read().splitlines()[0])
                tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2).read())
                break
            except Exception:
                time.sleep(0.1)
        if not tabs:
            raise RuntimeError('devtools not reachable')
        page = [t for t in tabs if t.get('type') == 'page'][0]
        self.ws = headless.WS(page['webSocketDebuggerUrl'], timeout=150)
        self.ws.call('Runtime.enable'); self.ws.call('Page.enable')
        self.ws.call('Emulation.setDeviceMetricsOverride', width=self.w, height=self.h, deviceScaleFactor=1, mobile=False)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=NET_INIT_JS)
        if self.reduce:
            self.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])
        try:
            self.ws.call('Browser.grantPermissions', permissions=['clipboardReadWrite', 'clipboardSanitizedWrite'])
        except Exception:
            pass

    def close(self):
        try:
            if self.ws:
                self.ws.call('Browser.close')
        except Exception:
            pass
        try:
            if self.proc and self.proc.poll() is None:
                os.killpg(self.proc.pid, signal.SIGTERM)
        except Exception:
            pass
        shutil.rmtree(self.ud, ignore_errors=True)

    def ev(self, expr, wait=True):
        r = self.ws.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=wait)
        if r.get('exceptionDetails'):
            raise RuntimeError('eval failed: %s :: %s' % (expr[:140], json.dumps(r['exceptionDetails'], ensure_ascii=False)[:900]))
        res = r.get('result', {})
        return res.get('value') if 'value' in res else None

    def nav(self, url):
        self.ws.call('Page.navigate', url=url)

    def until(self, expr, timeout=90, step=0.25):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.ev(expr) is True:
                    return True
            except Exception:
                pass
            time.sleep(step)
        return False

    def ready(self, timeout=120):
        ok = self.until(READY_JS, timeout)
        time.sleep(1.2)
        return ok

    def shot(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        snap = self.ws.call('Page.captureScreenshot', format='png')
        path.write_bytes(base64.b64decode(snap['data']))

    def health(self):
        return self.ev(headless.POST_HEALTH_JS)


def data_mtimes():
    out = {}
    for p in sorted((ROOT / 'data').rglob('*')):
        if p.is_file():
            out[str(p.relative_to(ROOT))] = p.stat().st_mtime_ns
    return out


class Suite:
    def __init__(self, shots):
        self.checks = []
        self.shots = Path(shots) if shots else None

    def check(self, name, ok, actual=None):
        ok = bool(ok)
        self.checks.append({'name': name, 'ok': ok, 'actual': actual})
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  :: ' + json.dumps(actual, ensure_ascii=False)[:1200]), flush=True)
        return ok

    def info(self, name, value):
        print('INFO ' + name + ' ' + json.dumps(value, ensure_ascii=False)[:600], flush=True)

    def shot(self, b, name):
        if self.shots:
            b.shot(self.shots / (name + '.png'))


def slim(p):
    keys = ['mode', 'plot', 'compass', 'group', 'cursor', 'playing', 'discState', 'hover', 'focused', 'tethers', 'litEv', 'litSat', 'frame']
    return {k: p.get(k) for k in keys}


def frame_expect(fid, p, E, ctx):
    ok, why = True, []

    def need(cond, label):
        nonlocal ok
        if not cond:
            ok = False
            why.append(label)
    need(p['frame'] == fid and p['lab']['running'] is None, 'current-frame')
    need(not p['playing'], 'not-playing')
    need((p['answers'].get(fid) or '') != '' and p['card']['id'].startswith(fid), 'answer-shown')
    if fid in ('C0', 'C1'):
        need(p['mode'] == 'constellation' and not p['plot'] and p['compass'] is None and p['discState'] == 'backdrop', 'constellation')
        need(p['group'] == ('camp' if fid == 'C0' else E['group2']), 'group')
        need(p['cursor'] is None and p['hover'] is None, 'clean')
    elif fid[0] == 'P':
        need(p['mode'] == 'constellation' and p['plot'] and p['discState'] == 'plot' and p['group'] == 'camp' and p['compass'] is None, 'plot-on')
        if fid == 'P0':
            need(p['cursor'] is None and p['hover'] is None and p['focused'] is None, 'no-hover')
        if fid == 'P1':
            need(p['hover'] == E['main'] and p['cursor'] is None, 'main-hovered')
            need(p['tethers'] > 0 or ctx.get('narrowTetherBug'), 'tethers')
            need(E['mainLabel'] in p['answers']['P1'], 'answer-has-label')
        if fid == 'P2':
            need(p['hover'] == E['branch'] and p['cursor'] is None, 'branch-hovered')
            need(p['tethers'] > 0 or ctx.get('narrowTetherBug'), 'tethers')
            need(E['branchLabel'] in p['answers']['P2'] and (' %d 人' % E['branchCast']) in p['answers']['P2'], 'answer-has-label-cast')
        if fid == 'P3':
            need(p['cursor'] == E['mid'] and p['hover'] is None, 'cursor-mid')
    else:
        need(p['mode'] == 'compass' and not p['plot'] and p['discState'] == 'hidden' and p['cstats'].get('open'), 'compass-on')
        if fid == 'K0':
            need(p['compass'] == E['top'] and p['cstats'].get('name') == E['top'], 'top')
            need(not p['litEv'], 'no-hover')
        if fid == 'K1':
            need(ctx.get('sat0') and p['compass'] == ctx['sat0'] and p['cstats'].get('name') == ctx['sat0'], 'first-satellite-of-top')
        if fid == 'K2':
            want = str(ctx['keys0'][0]) if ctx.get('keys0') else '0'
            need(p['compass'] == E['top'] and p['litEv'] == [want], 'first-key-event-lit')
    return ok, why


def open_lab(b):
    return b.ev("(function(){ if (!CLSkyLab.stats().on) document.getElementById('skyLabBtn').click(); return CLSkyLab.stats().on; })()")


def run_frames(b, S, E, prefix, suffix, ctx):
    for fid in FRAMES:
        t0 = time.time()
        r = b.ev("CLSkyLab.go('%s')" % fid)
        dt = time.time() - t0
        time.sleep(0.5)
        p = b.ev(PROBE_JS)
        if fid == 'K0':
            ctx['sat0'] = p['sats'][0] if p['sats'] else None
            ctx['keys0'] = p['keys']
        ok, why = frame_expect(fid, p, E, ctx)
        S.check('%sframe-%s-state' % (prefix, fid), r and r.get('ok') and ok, {'why': why, 'go': r and {k: r.get(k) for k in ('ok', 'reason', 'cancelled', 'error')}, 'probe': slim(p), 'answer': p['answers'].get(fid)})
        S.info('%s%s answer (%.1fs)' % (prefix, fid, dt), p['answers'].get(fid))
        S.shot(b, '%sframe-%s-%s' % (prefix, fid, suffix))
        if fid == 'K2':
            S.info(prefix + 'K2 lit satellites', p['litSat'])
    st = b.ev("CLSkyLab.stats()")
    S.check(prefix + 'no-errors-no-false-interrupts', not st['errors'] and st['interrupts'] == 0, st)


def run_1440(base, S, data, prefix, full):
    b = Browser(1440, 900)
    try:
        b.start()
        b.nav(base + '/' + q(data))
        S.check(prefix + '1440-ready', b.ready())
        entry = b.ev("(function(){ var b = document.getElementById('skyLabBtn'), t = document.getElementById('skyTools'); return { inActions: !!(b && b.parentNode && b.parentNode.classList.contains('sky-actions')), beforeTools: !!(b && b.nextElementSibling === t), cls: b ? b.className : null, pressed: b ? b.getAttribute('aria-pressed') : null, text: b ? b.textContent.trim() : null, glyph: !!(b && b.querySelector('svg')), labHidden: document.getElementById('skyLab').hidden }; })()")
        S.check(prefix + 'entry-glyph-before-tools', entry['inActions'] and entry['beforeTools'] and 'sky-icon' in entry['cls'] and entry['pressed'] == 'false' and entry['text'] == '预演' and entry['glyph'] and entry['labHidden'], entry)
        b.ev("document.getElementById('skyLabBtn').click()"); time.sleep(0.5)
        opened = b.ev("(function(){ var l = document.getElementById('skyLab'), p = l.querySelector('.skl-panel'), cs = getComputedStyle(p), root = getComputedStyle(document.documentElement); return { on: CLSkyLab.stats().on, open: CLSkyLab.stats().open, layout: CLSkyLab.stats().layout, hidden: l.hidden, pressed: document.getElementById('skyLabBtn').getAttribute('aria-pressed'), ticks: l.querySelectorAll('.skl-tick').length, modes: l.querySelectorAll('.skl-mode').length, copy: !!l.querySelector('.skl-copy'), bg: cs.backgroundColor, border: cs.borderTopColor, right: innerWidth - p.getBoundingClientRect().right, topBarRight: innerWidth - document.querySelector('.sky-top').getBoundingClientRect().right, line: root.getPropertyValue('--abyss-line').trim(), gold: root.getPropertyValue('--abyss-gold').trim(), dur: root.getPropertyValue('--cl-atlas-dur-2').trim(), mint: root.getPropertyValue('--abyss-mint-bright').trim() }; })()")
        S.check(prefix + 'lab-opens-right-panel', opened['on'] and opened['open'] and opened['layout'] == 'side' and not opened['hidden'] and opened['pressed'] == 'true' and opened['ticks'] == 9 and opened['modes'] == 4 and opened['copy'], opened)
        S.check(prefix + 'tokens-resolve-and-align', opened['line'] and opened['gold'] and opened['dur'] and opened['mint'] and opened['bg'] not in ('', 'rgba(0, 0, 0, 0)') and abs(opened['right'] - opened['topBarRight']) < 1.5, opened)
        E = b.ev(EXPECT_JS)
        S.info(prefix + 'expect', E)
        fr = {f['id']: f for f in b.ev("CLSkyLab.frames()")}
        S.check(prefix + 'rules-match-independent-recompute',
                all(f['available'] for f in fr.values()) and fr['C1']['target']['group'] == E['group2'] and fr['P1']['target']['hover'] == E['main'] and
                fr['P2']['target']['hover'] == E['branch'] and fr['P3']['target']['cursor'] == E['mid'] and fr['K0']['target']['compass'] == E['top'], {'E': E, 'frames': fr})
        ctx = {}
        run_frames(b, S, E, prefix, '1440', ctx)
        if not full:
            # 深链往返（西游：罗盘 K1）
            b.ev("CLSkyLab.go('K1')"); time.sleep(0.4)
            sa = b.ev("CLSky.snapshot()"); la = b.ev("CLSkyLab.link()")
            b.nav('about:blank'); time.sleep(0.3); b.nav(la)
            S.check(prefix + 'deeplink-K1-ready', b.ready() and b.until(LINK_DONE_JS, 60))
            time.sleep(0.6)
            sb = b.ev("CLSky.snapshot()"); cur = b.ev("CLSkyLab.current()")
            S.check(prefix + 'deeplink-K1-roundtrip', all(sa.get(k) == sb.get(k) for k in SNAP_KEYS) and cur == 'K1', {'a': sa, 'b': sb, 'frame': cur, 'link': b.ev("CLSkyLab.stats().link")})
            h = b.health()
            S.check(prefix + '1440-health', h and h.get('jserr') == 'none' and h.get('jsrej') == 'none' and not h.get('shaderErrors'), h)
            return
        # ── 中断：P2 刚开始就切 K0，2s 后终态仍是 K0 ──
        b.ev("CLSkyLab.go('C0')"); time.sleep(0.5)
        rr = b.ev("(function(){ var a = CLSkyLab.go('P2'), k = CLSkyLab.go('K0'); return Promise.all([a, k]).then(function(x){ return { a: x[0], k: { ok: x[1].ok, id: x[1].id } }; }); })()")
        p1 = b.ev(PROBE_JS); time.sleep(2.0); p2 = b.ev(PROBE_JS)
        S.check('interrupt-P2-cancelled-K0-final', rr['a'].get('cancelled') and rr['k']['ok'] and p1['frame'] == 'K0' and p1['compass'] == E['top'] and p1['mode'] == 'compass' and not p1['plot'], {'r': rr, 'p1': slim(p1)})
        S.check('interrupt-stable-after-2s', slim(p1) == slim(p2) and p2['frame'] == 'K0' and p2['hover'] is None and p2['discState'] == 'hidden', {'p1': slim(p1), 'p2': slim(p2)})
        # ── 用户在等待中动手：未完成的帧步骤作废，不被旧回调拉回 ──
        b.ev("CLSkyLab.go('P1')"); time.sleep(0.3)
        n0 = b.ev("CLSkyLab.stats().interrupts")
        rc = b.ev("(function(){ var r = CLSkyLab.go('K1'); setTimeout(function(){ document.getElementById('stage').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); }, 300); return r; })()")
        time.sleep(2.2)
        pc = b.ev(PROBE_JS)
        S.check('user-pointerdown-cancels-pending-steps', rc and rc.get('cancelled') and pc['mode'] != 'compass' and pc['compass'] is None and pc['frame'] is None and pc['lab']['interrupts'] == n0 + 1, {'r': rc, 'probe': slim(pc), 'interrupts': pc['lab']['interrupts']})
        # ── 读图模式 ──
        b.ev("CLSkyLab.go('P0')"); time.sleep(0.8)
        pre = b.ev("(function(){ var sc = CLApp.scene(); return { bloom: sc.digest().bloom, glow: sc.glow(), calm: sc.calm(), cls: document.body.className }; })()")
        b.ev("CLSkyLab.setMode('notext', true)"); time.sleep(0.4)
        NT_JS = r"""(function(){
          function vis(e){ if (!e) return false; var cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return false; var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; }
          function lit(e){ var o = 1; for (var x = e; x && x !== document.body; x = x.parentElement) o *= +getComputedStyle(x).opacity; return o > 0.05; }
          var named = [].slice.call(document.querySelectorAll('.sky-disc .sd-label:not(.is-main)')), mains = [].slice.call(document.querySelectorAll('.sky-disc .sd-label.is-main.is-fit'));
          var camps = [].slice.call(document.querySelectorAll('.cl-camp-halo__name')).filter(function(e){ return vis(e) && lit(e); }).length +
            [].slice.call(document.querySelectorAll('#labels .cl-lab.camp')).filter(function(l){ return lit(l) && vis(l.querySelector('.ln')); }).length +
            [].slice.call(document.querySelectorAll('.sky-field .sf-name .sf-n')).filter(function(e){ return vis(e) && lit(e); }).length;   /* 平面天球：团名在星域层 */
          var chars = [].slice.call(document.querySelectorAll('#labels .cl-lab.char')).filter(function(l){ return getComputedStyle(l).display !== 'none' && getComputedStyle(l).visibility !== 'hidden' && lit(l); });
          return { cls: document.body.classList.contains('skylab-notext'), plot: CLSky.plot(), named: named.length, namedHidden: named.filter(function(e){ return getComputedStyle(e).visibility === 'hidden'; }).length,
            mainsFit: mains.length, mainsVisible: mains.filter(function(e){ return getComputedStyle(e).visibility === 'visible' && +getComputedStyle(e).opacity > 0.5; }).length,
            nums: [].slice.call(document.querySelectorAll('.sky-disc .sd-num')).filter(function(e){ return getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none'; }).length,
            camps: camps, charNames: chars.filter(function(l){ return vis(l.querySelector('.ln')); }).length, charSubs: chars.filter(function(l){ return vis(l.querySelector('.ls')) || vis(l.querySelector('.lx')); }).length,
            hint: vis(document.querySelector('.sky-legend .lg-hint')), legendNote: vis(document.querySelector('.cl-dom-legend__note')), question: vis(document.querySelector('#skyLab .skl-q')), answer: vis(document.querySelector('#skyLab .skl-a')) };
        })()"""
        nt = b.ev(NT_JS)
        S.check('notext-P0-hides-arc-names-keeps-mains-numbers', nt['cls'] and nt['plot'] and nt['named'] > 0 and nt['namedHidden'] == nt['named'] and nt['mainsFit'] > 0 and nt['mainsVisible'] == nt['mainsFit'] and nt['nums'] > 0 and not nt['hint'] and not nt['question'] and nt['answer'], nt)
        b.ev("CLSkyLab.go('C0')"); time.sleep(0.8)
        nc = b.ev(NT_JS)
        S.check('notext-C0-keeps-camp-and-entity-names-hides-subrows-hints', nc['cls'] and not nc['plot'] and nc['camps'] > 0 and nc['charNames'] > 0 and nc['charSubs'] == 0 and not nc['hint'] and not nc['legendNote'] and not nc['question'] and nc['answer'], nc)
        S.shot(b, 'mode-notext-C0-1440')
        b.ev("CLSkyLab.go('P2')"); time.sleep(0.5)
        cd = b.ev("(function(){ var c = document.getElementById('skyCard'); return { hiddenAttr: c.hidden, display: getComputedStyle(c).display, frame: CLSkyLab.current() }; })()")
        S.check('notext-hides-hover-card', cd['hiddenAttr'] is False and cd['display'] == 'none' and cd['frame'] == 'P2', cd)
        b.ev("CLSkyLab.setMode('noglow', true)"); time.sleep(0.4)
        ng = b.ev("(function(){ var sc = CLApp.scene(), l = document.querySelector('#labels .cl-lab.char .ln'); return { cls: document.body.classList.contains('skylab-noglow'), bloom: sc.digest().bloom, glow: sc.glow(), text: l ? getComputedStyle(l).textShadow : 'none' }; })()")
        S.check('noglow-bloom-zero-and-no-text-glow', ng['cls'] and ng['bloom'] == 0 and ng['glow'] == 0 and ng['text'] == 'none', ng)
        badge0 = b.ev("(function(){ var e = document.querySelector('.cl-camp-halo__badge'); if (!e) return null; var r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)]; })()")
        b.ev("CLSkyLab.setMode('gray', true)"); time.sleep(0.4)
        gy = b.ev("(function(){ function f(s){ var e = document.querySelector(s); return e ? getComputedStyle(e).filter : null; } var e = document.querySelector('.cl-camp-halo__badge'), r = e ? e.getBoundingClientRect() : null; return { cls: document.body.classList.contains('skylab-gray'), stage: f('#stage'), compass: f('.sky-compass'), top: f('.sky-top'), halo: f('.cl-camp-halo-labels'), lab: f('#skyLab'), panel: f('#skyLab .skl-panel'), badge: r ? [Math.round(r.left), Math.round(r.top)] : null }; })()")
        S.check('gray-filters-stage-and-svg-layers', gy['cls'] and 'grayscale' in (gy['stage'] or '') and 'grayscale' in (gy['compass'] or '') and 'grayscale' in (gy['top'] or '') and gy['lab'] == 'none' and gy['panel'] == 'none', gy)
        S.check('gray-does-not-move-fixed-layers', gy['badge'] == badge0, {'before': badge0, 'after': gy['badge']})
        b.ev("CLSkyLab.setMode('still', true)"); time.sleep(0.4)
        sl = b.ev("({ calm: CLApp.scene().calm(), playing: CLSky.state().playing, modes: CLSkyLab.modes(), pressed: [].map.call(document.querySelectorAll('#skyLab .skl-mode'), function(e){ return e.getAttribute('aria-pressed'); }) })")
        S.check('still-calms-and-all-modes-stack', sl['calm'] is True and not sl['playing'] and sl['modes'] == {'notext': True, 'noglow': True, 'gray': True, 'still': True} and sl['pressed'] == ['true'] * 4, sl)
        S.shot(b, 'modes-all-P2-1440')
        b.ev("CLSkyLab.go('K2')"); time.sleep(0.6)
        S.shot(b, 'modes-all-K2-1440')
        b.ev("document.getElementById('skyLabBtn').click()"); time.sleep(0.8)
        post = b.ev("(function(){ var sc = CLApp.scene(); return { bloom: sc.digest().bloom, glow: sc.glow(), calm: sc.calm(), skylab: /skylab-/.test(document.body.className), hidden: document.getElementById('skyLab').hidden, pressed: document.getElementById('skyLabBtn').getAttribute('aria-pressed'), modes: CLSkyLab.modes(), stage: getComputedStyle(document.getElementById('stage')).filter, compassFilter: getComputedStyle(document.querySelector('.sky-compass')).filter, lit: document.querySelectorAll('.sky-compass .skc-ev.is-on').length, card: getComputedStyle(document.querySelector('.skc-card')).display }; })()")
        S.check('close-lab-restores-everything', post['bloom'] > 0 and post['glow'] == pre['glow'] and post['calm'] == pre['calm'] and not post['skylab'] and post['hidden'] and post['pressed'] == 'false' and
                not any(post['modes'].values()) and 'grayscale' not in post['stage'] and 'grayscale' not in post['compassFilter'] and post['lit'] == 0 and post['card'] == 'none', {'pre': pre, 'post': post})
        # 实验室关着，由用户自己回到星盘：支线弧名重新可见（收字已随关闭撤销）
        b.ev("(function(){ CLSky.closeCompass(); if (!CLSky.plot()) CLSky.setPlot(true); return true; })()"); time.sleep(2.8)
        rv = b.ev("(function(){ var named = [].slice.call(document.querySelectorAll('.sky-disc .sd-label:not(.is-main).is-fit')); return { fit: named.length, shown: named.filter(function(e){ return getComputedStyle(e).visibility === 'visible' && +getComputedStyle(e).opacity > 0.5; }).length, hint: getComputedStyle(document.querySelector('.sky-legend .lg-hint')).display }; })()")
        S.check('close-lab-arc-names-and-hints-back', rv['fit'] > 0 and rv['shown'] == rv['fit'] and rv['hint'] != 'none', rv)
        # ── 深链往返 ──
        open_lab(b)
        b.ev("CLSkyLab.go('P3')"); b.ev("CLSkyLab.setMode('gray', true)")
        sa = b.ev("CLSky.snapshot()"); ma = b.ev("CLSkyLab.modes()"); la = b.ev("CLSkyLab.link()")
        S.check('link-format', la.startswith(b.ev("location.href.split('#')[0]") + '#sky=') and b.ev("CLSkyLab.current()") == 'P3', la[:160])
        copied = b.ev("(function(){ document.querySelector('#skyLab .skl-copy').click(); return new Promise(function(r){ setTimeout(function(){ r({ copy: document.getElementById('skyLab').getAttribute('data-copy'), url: document.querySelector('#skyLab .skl-url').value, shown: !document.querySelector('#skyLab .skl-url').hidden }); }, 500); }); })()")
        S.check('copy-link-button', copied['url'] == la and (copied['copy'] == 'ok' or (copied['copy'] == 'manual' and copied['shown'])), copied)
        b.nav('about:blank'); time.sleep(0.3); b.nav(la)
        S.check('deeplink-P3-page-ready', b.ready() and b.until(LINK_DONE_JS, 60))
        time.sleep(0.5)
        sb = b.ev("CLSky.snapshot()"); mb = b.ev("CLSkyLab.modes()"); st = b.ev("CLSkyLab.stats()")
        S.check('deeplink-frame-roundtrip-snapshot-equal', all(sa.get(k) == sb.get(k) for k in SNAP_KEYS) and ma == mb and st['frame'] == 'P3' and st['on'] and st['link'].get('ok'), {'a': sa, 'b': sb, 'ma': ma, 'mb': mb, 'stats': st})
        S.shot(b, 'deeplink-P3-restored-1440')
        b.ev("CLSkyLab.setMode('gray', false)")
        # 自由态：立场分类 + 剧情 + 回目 + 选中支线（不在任何帧上）
        b.ev("CLSkyLab.go('P0')")
        b.ev("(function(){ CLSky.regroup('%s'); CLSky.seek(3); CLSky.focusLine('%s'); return true; })()" % (E['group2'], E['branch'])); time.sleep(0.6)
        sa2 = b.ev("CLSky.snapshot()"); la2 = b.ev("CLSkyLab.link()"); f2 = b.ev("CLSkyLab.current()")
        b.nav('about:blank'); time.sleep(0.3); b.nav(la2)
        b.ready(); b.until(LINK_DONE_JS, 60); time.sleep(0.5)
        sb2 = b.ev("CLSky.snapshot()"); lk2 = b.ev("CLSkyLab.stats().link")
        S.check('deeplink-free-state-roundtrip', f2 is None and all(sa2.get(k) == sb2.get(k) for k in SNAP_KEYS) and lk2.get('ok') and lk2.get('via') == 'state' and sb2['line'] == E['branch'] and sb2['group'] == E['group2'], {'a': sa2, 'b': sb2, 'link': lk2})
        # 伪造：不存在的人物 / 不存在的线 → 停在星座全景 + 提示，绝不按下标替换
        for tag, snap in (('character', {'v': 1, 'group': 'camp', 'plot': False, 'compass': '无此人', 'cursor': None, 'line': None}),
                          ('line', {'v': 1, 'group': 'camp', 'plot': True, 'compass': None, 'cursor': 2, 'line': 'T_does_not_exist'})):
            forged = b.ev("(function(s){ var j = new TextEncoder().encode(JSON.stringify({ v: 1, frame: 'K0', snap: s, modes: { notext: false, noglow: false, gray: false, still: false } })), bin = ''; j.forEach(function(x){ bin += String.fromCharCode(x); }); return location.href.split('#')[0] + '#sky=' + btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); })(%s)" % json.dumps(snap, ensure_ascii=False))
            b.nav('about:blank'); time.sleep(0.3); b.nav(forged)
            b.ready(); b.until(LINK_DONE_JS, 60); time.sleep(0.5)
            fg = b.ev("({ link: CLSkyLab.stats().link, noteShown: document.querySelector('#skyLab .skl-note').textContent, s: CLSky.state(), frame: CLSkyLab.current() })")
            s = fg['s']
            S.check('forged-%s-stops-at-panorama-with-notice' % tag, fg['link'] and fg['link'].get('reason') == 'missing' and '深链对象不在当前作品' in (fg['noteShown'] or '') and
                    s['mode'] == 'constellation' and not s['plot'] and s['compass'] is None and s['group'] == 'camp' and fg['frame'] == 'C0', {'link': fg['link'], 'note': fg['noteShown'], 'frame': fg['frame'], 'mode': s['mode'], 'plot': s['plot'], 'compass': s['compass']})
            if tag == 'character':
                S.shot(b, 'deeplink-forged-1440')
        # ── 样例往返：saga → mid → 回 saga ──
        before = data_mtimes()
        b.nav('about:blank'); time.sleep(0.3); b.nav(base + '/' + q(SAGA))
        S.check('sample-origin-ready', b.ready())
        open_lab(b)
        b.ev("CLSkyLab.go('P2')"); time.sleep(0.3)
        s_saga = b.ev("({ snap: CLSky.snapshot(), frame: CLSkyLab.current(), modes: CLSkyLab.modes() })")
        net0 = b.ev("window.__l1net.slice()")
        b.ev("document.querySelector('#skyLab .skl-disclose').click()"); time.sleep(0.3)
        lst = b.ev("[].map.call(document.querySelectorAll('#skyLab .skl-srow'), function(r){ return r.textContent; })")
        S.check('sample-list-labels', len(lst) == 5 and '当前' in lst[0] and all('样例' in x for x in lst[1:]) and b.ev("document.querySelector('#skyLab [data-file=\"data/sample-saga.json\"]').getAttribute('aria-disabled')") == 'true', lst)
        S.shot(b, 'samples-open-1440')
        b.ev("document.querySelector('#skyLab [data-file=\"data/sample-mid.json\"]').click()")
        time.sleep(1.0)
        S.check('sample-mid-page-ready', b.until("location.search.indexOf('sample-mid') >= 0 && " + READY_JS, 90) and b.until(LINK_DONE_JS, 60))
        time.sleep(0.6)
        mid = b.ev("({ title: CLApp.graph().title, ret: !document.querySelector('#skyLab .skl-return').hidden, retText: document.querySelector('#skyLab .skl-return').textContent, rp: !!sessionStorage.getItem('castline.skylab.return'), frame: CLSkyLab.current(), link: CLSkyLab.stats().link, sample: CLSkyLab.stats().sample, on: CLSkyLab.stats().on, hash: location.hash.slice(0, 5) })")
        S.check('sample-mid-loaded-with-return-row', mid['on'] and mid['ret'] and '样例' in mid['retText'] and '回到原作品' in mid['retText'] and mid['rp'] and mid['sample']['page'] and mid['hash'] == '#sky=', mid)
        S.check('sample-link-applies-same-frame-rule', mid['frame'] == s_saga['frame'] or (mid['link'] or {}).get('reason') == 'frame-unavailable', mid)
        S.shot(b, 'sample-mid-1440')
        net1 = b.ev("window.__l1net.slice()")
        b.ev("document.querySelector('#skyLab .skl-return').click()")
        time.sleep(1.0)
        S.check('return-page-ready', b.until("location.search.indexOf('sample-saga') >= 0 && " + READY_JS, 90) and b.until(LINK_DONE_JS, 60))
        time.sleep(0.6)
        s_back = b.ev("({ snap: CLSky.snapshot(), frame: CLSkyLab.current(), modes: CLSkyLab.modes() })")
        back = b.ev("({ rp: !!sessionStorage.getItem('castline.skylab.return'), ret: !document.querySelector('#skyLab .skl-return').hidden, title: CLApp.graph().title, hover: CLSky.disc().hover() })")
        S.check('sample-return-restores-original-state', all(s_saga['snap'].get(k) == s_back['snap'].get(k) for k in SNAP_KEYS) and s_saga['frame'] == s_back['frame'] and s_saga['modes'] == s_back['modes'] and
                not back['rp'] and not back['ret'] and back['title'] == E['title'] and back['hover'] == E['branch'], {'saga': s_saga, 'back': s_back, 'page': back})
        net2 = b.ev("window.__l1net.slice()")
        # 页面自身的只读轮询（GET /api/health · history · jobs）不算；任何非 GET/HEAD 或分析 / 蒸馏 / 规划 / 取源接口都算
        writes = [x for x in (net0 or []) + (net1 or []) + (net2 or []) if x[0] not in ('GET', 'HEAD') or any(k in x[1] for k in ('/api/analyze', '/api/distill', '/api/plan', '/api/source', '/api/cancel'))]
        S.info('sample-switch-requests', sorted(set(x[0] + ' ' + x[1].split('?')[0] for x in (net1 or []) + (net2 or []))))
        S.check('sample-switch-no-write-or-analysis-requests', not writes, writes)
        after = data_mtimes()
        changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
        if 'data/cache/index.json' in changed:
            S.info('sample-window-shared-history-touched-by-other-session', ['data/cache/index.json'])
        S.check('data-dir-mtimes-unchanged', not [k for k in changed if k != 'data/cache/index.json'] and not writes, changed)
        h = b.health()
        S.check(prefix + '1440-health', h and h.get('jserr') == 'none' and h.get('jsrej') == 'none' and not h.get('shaderErrors'), h)
    finally:
        b.close()


def run_820(base, S):
    b = Browser(820, 1180)
    try:
        b.start()
        b.nav(base + '/' + q(XIYOU))
        S.check('820-ready', b.ready())
        open_lab(b)
        st = b.ev("CLSkyLab.stats()")
        S.check('820-side-panel-opens', st['on'] and st['open'] and st['layout'] == 'side', st)
        b.ev("CLSkyLab.go('P2')"); time.sleep(0.5)
        bx0 = b.ev(BOX_JS)
        S.info('820-P2-panel-open-overlap', {'ratio': bx0['ratio'], 'box': bx0['box']})
        S.shot(b, 'lab-open-P2-820')
        # 用户从栏里点一帧：中屏自动收成竖签，把舞台让出来
        b.ev("document.querySelector('#skyLab [data-frame=K0]').click()")
        S.check('820-ui-K0-reached', b.until("CLSkyLab.current() === 'K0'", 20))
        time.sleep(0.6)
        bx = b.ev(BOX_JS); tag = b.ev("document.querySelector('#skyLab .skl-tag').textContent")
        S.check('820-ui-click-folds-to-vertical-tag', not bx['open'] and 'K0' in tag and bx['ratio'] is not None and bx['ratio'] <= 0.03 and bx['sw'] <= bx['W'], {'box': bx, 'tag': tag})
        S.shot(b, 'frame-K0-820')
        b.ev("document.querySelector('#skyLab .skl-tag').click()"); time.sleep(0.4)
        S.check('820-tag-reopens-panel', b.ev("CLSkyLab.stats().open && getComputedStyle(document.querySelector('#skyLab .skl-panel')).display !== 'none'"))
        b.ev("document.querySelector('#skyLab [data-frame=P2]').click()")
        S.check('820-ui-P2-reached', b.until("CLSkyLab.current() === 'P2'", 20))
        time.sleep(0.6)
        bx2 = b.ev(BOX_JS); p = b.ev(PROBE_JS)
        S.check('820-P2-folded-overlap<=3%', not bx2['open'] and bx2['ratio'] is not None and bx2['ratio'] <= 0.03, bx2)
        S.info('820-P2-tethers (host H6: portrait plot camera beyond far plane)', p['tethers'])
        S.shot(b, 'frame-P2-820')
        # 不可寻址（demo=1，不是 ?data= 打开）：样例切换禁用并写明原因，点了也不导航
        b.nav('about:blank'); time.sleep(0.3); b.nav(base + '/?demo=1&sky=1&probe=1')
        S.check('820-unaddressable-ready', b.ready())
        open_lab(b)
        b.ev("document.querySelector('#skyLab .skl-disclose').click()"); time.sleep(0.3)
        href0 = b.ev("location.href")
        ua = b.ev("({ dis: [].map.call(document.querySelectorAll('#skyLab .skl-sample'), function(e){ return e.getAttribute('aria-disabled'); }), reason: (document.querySelector('#skyLab .skl-sreason') || {}).textContent || '', addr: CLSkyLab.stats().address })")
        b.ev("document.querySelector('#skyLab [data-file=\"data/sample-mid.json\"]').click()"); time.sleep(1.0)
        S.check('820-unaddressable-samples-disabled-with-reason', ua['dis'] == ['true'] * 4 and '?data=' in ua['reason'] and not ua['addr']['ok'] and b.ev("location.href") == href0, ua)
        S.shot(b, 'samples-disabled-820')
        h = b.health()
        S.check('820-health', h and h.get('jserr') == 'none' and h.get('jsrej') == 'none' and not h.get('shaderErrors'), h)
    finally:
        b.close()


def run_390(base, S):
    b = Browser(390, 844)
    try:
        b.start()
        b.nav(base + '/' + q(XIYOU))
        S.check('390-ready', b.ready())
        bar = b.ev("(function(){ return [].map.call(document.querySelectorAll('.sky-actions > *'), function(e){ var r = e.getBoundingClientRect(); return [e.id, Math.round(r.left), Math.round(r.right)]; }).concat([['W', innerWidth, document.documentElement.scrollWidth]]); })()")
        S.check('390-top-bar-fits-with-lab-glyph', all(x[2] <= 390 - 8 for x in bar[:-1]) and bar[-1][2] <= 390 and any(x[0] == 'skyLabBtn' for x in bar), bar)
        open_lab(b)
        b.ev("CLSkyLab.go('P2')"); time.sleep(0.6)
        bx = b.ev(BOX_JS); p = b.ev(PROBE_JS)
        S.check('390-drawer-layout-height<=40%', bx['layout'] == 'drawer' and bx['open'] and bx['heightRatio'] <= 0.40 and bx['sw'] <= 390, bx)
        S.check('390-drawer-P2-overlap<=40%', bx['ratio'] is not None and bx['ratio'] <= 0.40, bx)
        S.info('390-P2-tethers (host: plot camera beyond far plane at narrow portrait)', p['tethers'])
        S.shot(b, 'drawer-P2-390')
        b.ev("CLSkyLab.go('K0')"); time.sleep(0.6)
        bxk = b.ev(BOX_JS)
        S.info('390-K0-drawer-open-overlap', {'ratio': bxk['ratio'], 'cover': b.ev("CLSkyLab.stats().cover")})
        S.shot(b, 'drawer-K0-390')
        # 用户从抽屉点一帧：收成带读数的药丸签
        b.ev("document.querySelector('#skyLab [data-frame=P2]').click()")
        S.check('390-ui-P2-reached', b.until("CLSkyLab.current() === 'P2'", 20))
        time.sleep(0.6)
        bx2 = b.ev(BOX_JS); pill = b.ev("document.querySelector('#skyLab .skl-tag').textContent")
        S.check('390-ui-click-folds-to-pill-with-reading', not bx2['open'] and 'P2' in pill and len(pill) > 6 and bx2['ratio'] is not None and bx2['ratio'] <= 0.05, {'box': bx2, 'pill': pill})
        dock = b.ev("(function(){ var t = document.querySelector('#skyLab .skl-tag').getBoundingClientRect(), c = document.getElementById('skyCard'), r = c && !c.hidden ? c.getBoundingClientRect() : null, bb = [].map.call(document.querySelectorAll('.sky-bottom > *'), function(e){ return e.getBoundingClientRect(); }).filter(function(q){ return q.height > 0; }); function x(a, q){ return Math.max(0, Math.min(a.right, q.right) - Math.max(a.left, q.left)) * Math.max(0, Math.min(a.bottom, q.bottom) - Math.max(a.top, q.top)); } return { card: r ? x(t, r) : 0, bottom: bb.reduce(function(s, q){ return s + x(t, q); }, 0), cardShown: !!r }; })()")
        S.check('390-pill-clear-of-docked-card-and-player', dock['card'] == 0 and dock['bottom'] == 0, dock)
        S.shot(b, 'frame-P2-390')
        b.ev("document.querySelector('#skyLab .skl-tag').click()"); time.sleep(0.4)
        b.ev("document.querySelector('#skyLab [data-frame=K0]').click()")
        S.check('390-ui-K0-reached', b.until("CLSkyLab.current() === 'K0'", 20))
        time.sleep(0.6)
        bx3 = b.ev(BOX_JS); pill3 = b.ev("document.querySelector('#skyLab .skl-tag').textContent")
        S.check('390-K0-pill-overlap<=5%', not bx3['open'] and 'K0' in pill3 and bx3['ratio'] is not None and bx3['ratio'] <= 0.05, {'box': bx3, 'pill': pill3})
        S.shot(b, 'frame-K0-390')
        h = b.health()
        S.check('390-health', h and h.get('jserr') == 'none' and h.get('jsrej') == 'none' and not h.get('shaderErrors'), h)
    finally:
        b.close()


def run_reduce(base, S):
    """prefers-reduced-motion：帧直接落终态，终态与常规一致。"""
    b = Browser(1440, 900, reduce=True)
    try:
        b.start()
        b.nav(base + '/' + q(SAGA))
        S.check('reduce-ready', b.ready())
        open_lab(b)
        E = b.ev(EXPECT_JS); ctx = {}
        for fid in FRAMES:
            t0 = time.time(); r = b.ev("CLSkyLab.go('%s')" % fid); dt = time.time() - t0
            p = b.ev(PROBE_JS)
            if fid == 'K0':
                ctx['sat0'] = p['sats'][0] if p['sats'] else None
                ctx['keys0'] = p['keys']
            ok, why = frame_expect(fid, p, E, ctx)
            S.check('reduce-frame-%s-fast-and-correct' % fid, r and r.get('ok') and ok and dt < 1.0, {'why': why, 'seconds': round(dt, 2), 'probe': slim(p)})
        h = b.health()
        S.check('reduce-health', h and h.get('jserr') == 'none' and h.get('jsrej') == 'none' and not h.get('shaderErrors'), h)
    finally:
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8782').rstrip('/'))
    ap.add_argument('--shots', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'sky-lab'))
    ap.add_argument('--only', default='saga,xiyou,820,390,reduce')
    a = ap.parse_args()
    base = a.base.rstrip('/')
    only = set(a.only.split(','))
    S = Suite(a.shots)
    if S.shots:
        S.shots.mkdir(parents=True, exist_ok=True)
    headless.reap_orphans()
    before = data_mtimes()
    steps = [('saga', lambda: run_1440(base, S, SAGA, '', True)), ('xiyou', lambda: run_1440(base, S, XIYOU, 'xiyou-', False)),
             ('820', lambda: run_820(base, S)), ('390', lambda: run_390(base, S)), ('reduce', lambda: run_reduce(base, S))]
    for name, fn in steps:
        if name not in only:
            continue
        try:
            fn()
        except Exception as e:  # 一段崩了记一条失败，其余段照跑
            S.check('%s-suite-crashed' % name, False, repr(e)[:800])
    after = data_mtimes()
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    # data/cache/index.json 是作品库历史：同机其他会话（别的端口）打开作品时服务端会 POST /api/history 记一次打开。
    # 本套件的页面只发 GET（样例往返段逐条核对网络日志），所以整段只把它记 INFO，其余文件一律不许变。
    shared = [k for k in changed if k == 'data/cache/index.json']
    if shared:
        S.info('suite-data-shared-history-touched-by-other-session', shared)
    S.check('suite-data-dir-untouched', not [k for k in changed if k not in shared], changed)
    n_ok = sum(1 for c in S.checks if c['ok'])
    fails = [c for c in S.checks if not c['ok']]
    if fails:
        print('SKY-LAB FAIL · %d/%d · %s' % (n_ok, len(S.checks), ', '.join(c['name'] for c in fails)))
        sys.exit(1)
    print('SKY-LAB OK · %d/%d' % (n_ok, len(S.checks)))


if __name__ == '__main__':
    main()
