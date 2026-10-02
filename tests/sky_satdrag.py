#!/usr/bin/env python3
"""罗盘关系星拖拽（Q3.1 · 判据 T6 / T7）与关键事件扇出（Q9.4）验收——真指针（CDP Input），三书 × 1440 / 390 + 减弱动效。

拖拽（关系星 = 罗盘读层 SVG 上的卫星）：
  D1 跟手：按住拖出 d px → 星落在指针处（偏差 ≤ max(3, 0.15·d)，位移 ≥ 0.85·d）；连线端点跟着星（离星心 = 星半径 + 4，±1 px）；
     连线伸长 → is-taut、--skc-k > 0.1、描边变粗 / 变色，辉光同路径；拖动中不转镜头（方位 / 俯仰变化 < 0.2°，轨道中心不动）、不换人。
  D2 让位：拖着星靠近同侧（窄屏同一行）的邻星 → 邻星被推开（离拖动星更远，位移 1 … yieldPx + 1.5 px），沿轨道椭圆（外推余量不变，±0.6 px）
     / 沿行（竖直不动）；另一侧的星不动（< 0.5 px）；松手后全部回家位。
  D3 松手回弹：欠阻尼（越过家位 ≥ 1 px）；≤ 1 s 回到家位（≤ 0.5 px）并睡眠（phase idle、此后不再写属性）；拖过的松手不当点击（不换人）。
  D4 拖进晶体（松手落在 S.crownScreenBounds 内）：途中就位（skc-armed）→ 吸入（星缩小、向晶体心靠拢）→ 进入他的罗盘。
  D5 slop 内松手 = 点击 → 照旧进入其罗盘。
  D7 罗盘态空白处左键拖仍是旋转（方位变、轨道中心不动、不起拖拽 / 牵引、不换人）。
  D6 减弱动效：跟手照常；松手下一帧即在家位（无回弹帧）；拖进晶体直接切换（无吸入帧）；扇出无动画。
扇出：
  F1 悬停事件最多的珠 → 扇出条数 = 该回事件数（或 条数 + N = 事件数，带「+N」）；短名都是该角色该回的真实事件名。
  F2 短名互不重叠；不压因果链标题与两侧细线；不压密度带 / 链身（isPointInFill / isPointInStroke 逐点采样）；不出屏。
  F3 离开收回（0.45 s 后无可见短名）。
  F4 密度带：悬停带上没有珠的回 → 扇出这一回。
  F5 键盘：聚焦珠 → 展开；→ 下一回（镜头不转）；Esc 收回（仍在罗盘）；Enter 再展开；Tab 到下一颗珠；Esc ×2 退出罗盘。
  F7 停在珠上不动：罗盘重排不让扇面重建 / 重放入场。
  F6 全珠扫描：每颗可见珠 + 密度带抽样约 20 回逐个悬停，短名不互叠、不压标题细线 / 关系星 / 轴签 / HUD / 其它珠 / 带子链身 / 悬停卡片、不出屏，条数守恒。
仲裁：罗盘态拖关系星（含拖过晶体）不唤起星座牵引（CLSkyTug idle、grabs 不增、场景无牵引键）。
大书 4K 视口（1920×1080 × dpr 2）：F6 扫描 + 拖拽跟手 / 回家。

用法：CL_GPU=1 python3 -s tests/sky_satdrag.py [--base http://127.0.0.1:8765] [--shots /tmp/castline-shots/sky-satdrag] [--only saga]
"""
import argparse, base64, json, math, os, shutil, signal, subprocess, sys, tempfile, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import headless  # noqa: E402

BOOKS = [('saga', 'data/sample-saga.json'), ('sanguo', 'data/cache/a935953b2678a80b352091d5.json'), ('dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json')]
READY_JS = ("!!(window.CLSky && CLSky.model() && window.CLSkyCompass && window.CLSkyCompassDrag && window.CLSkyCompassFan && "
            "!Array.prototype.some.call(document.querySelectorAll('.skd-loader'), function (e) { return !e.hidden; }))")
HELP = r"""(function(){ if (window.__sd) return true;
  var S = CLApp.scene();
  function top(){ return CLApp.graph().characters.slice().sort(function(a,b){ return (b.importance||0)-(a.importance||0); })[0].name; }
  function sat(i){ return document.querySelector('.sky-compass .skc-sat[data-sat="'+i+'"]'); }
  function tf(el){ var m = /translate\(([-\d.]+) ([-\d.]+)\)(?: scale\(([-\d.]+)\))?/.exec(el && el.getAttribute('transform') || ''); return m ? [+m[1], +m[2], m[3] ? +m[3] : 1] : null; }
  function home(i){ var L = CLSkyCompass._layout(true); return L ? L.sats.filter(function(s){ return s.i === i; })[0] || null : null; }
  function link(i){ return document.querySelectorAll('.sky-compass .skc-links .skc-link')[i]; }
  function ends(d){ var n = (d || '').match(/-?\d+(?:\.\d+)?/g); return n && n.length >= 4 ? n.map(Number) : null; }
  function cam(){ var c = S.camera.position, t = S.controls.target, o = c.clone().sub(t), r = o.length();
    return { az: Math.atan2(o.x, o.z) * 180 / Math.PI, pol: Math.acos(Math.max(-1, Math.min(1, o.y / r))) * 180 / Math.PI, r: r, t: [t.x, t.y, t.z] }; }
  function anchor(){ var v = new THREE.Vector3(); S.crownAnchor().getWorldPosition(v); v.project(S.camera); return [(v.x + 1) * innerWidth / 2, (1 - v.y) * innerHeight / 2]; }
  function crown(){ var b = S.crownScreenBounds(); return b ? [b.left, b.top, b.right, b.bottom] : null; }
  function tier(){ var c = S.core ? S.core() : null; return CLSkyTokens.tierOf(c && c.getDegrade ? c.getDegrade() : 0); }
  /* 逐帧采样一颗关系星：[t ms, 渲染 x, y, 缩放, 家位 x, y, 拖拽阶段, 星点实际屏幕心 x, y（含 CSS 过渡）] */
  function sample(i, ms){ return new Promise(function(res){ var out = [], t0 = performance.now(), off = null;
    off = S.registerFrameHook(function(){ var t = performance.now() - t0, p = tf(sat(i)), h = home(i), c = sat(i) && sat(i).querySelector('.skc-sat-star'), q = c ? c.getBoundingClientRect() : null;
      out.push([Math.round(t), p ? p[0] : null, p ? p[1] : null, p ? p[2] : 1, h ? h.x : null, h ? h.y : null, CLSkyCompassDrag.stats().phase, q ? (q.left + q.right) / 2 : null, q ? (q.top + q.bottom) / 2 : null]);
      if (t > ms) { off(); res(out); } }); }); }
  /* 框 + 实际不透明度（沿祖先连乘到读层 SVG：扇面收起时淡的是整组） */
  function rects(sel){ return [].map.call(document.querySelectorAll(sel), function(e){ var r = e.getBoundingClientRect(), o = 1, n = e;
    while (n && n.nodeType === 1 && n.tagName.toLowerCase() !== 'body') { o *= +getComputedStyle(n).opacity; if (n.classList && n.classList.contains('sky-compass')) break; n = n.parentNode; }
    return [r.left, r.top, r.right, r.bottom, e.textContent, o]; }); }
  /* 短名框是否压到带子 / 链身：框内 7×3 个点逐个问 isPointInFill / isPointInStroke */
  function onBand(b){ var hits = 0, bands = [].slice.call(document.querySelectorAll('.sky-compass .skc-band:not(.is-sel)')), line = document.querySelector('.sky-compass .skc-chain-line');
    for (var ix = 0; ix < 7; ix++) for (var iy = 0; iy < 3; iy++) { var p = new DOMPoint(b[0] + (b[2] - b[0]) * (ix + 0.5) / 7, b[1] + (b[3] - b[1]) * (iy + 0.5) / 3);
      bands.forEach(function(e){ if (e.getAttribute('d') && e.isPointInFill(p)) hits++; });
      if (line && line.getAttribute('d') && getComputedStyle(line).visibility !== 'hidden' && line.isPointInStroke(p)) hits++; }
    return hits; }
  window.__sd = { tier: tier, top: top, sat: sat, tf: tf, home: home, link: link, ends: ends, cam: cam, anchor: anchor, crown: crown, sample: sample, rects: rects, onBand: onBand };
  return true; })()"""

TUG_JS = ("(function(){ var T = window.CLSkyTug, S = CLApp.scene(), i = S.tugInfo ? S.tugInfo() : null;"
          " return T ? { on: T.state().on, phase: T.stats().phase, grabs: T.stats().grabs, keys: i ? i.keys : 0 } : null; })()")


def tug_quiet(t0, t1):
    """罗盘这一侧的拖拽不得唤起星座牵引：无 CLSkyTug 视为通过（未加载），否则 idle、grabs 不增、场景无牵引键"""
    if t0 is None or t1 is None:
        return t0 is None and t1 is None
    return (not t1['on']) and t1['phase'] == PH_IDLE and t1['grabs'] == t0['grabs'] and not t1['keys']


PH_IDLE = 'idle'

# F6 全珠扫描：每颗可见珠 + 密度带上抽样约 20 回，程序化悬停、动画 finish 后量——短名互叠 / 出屏 / 压标题细线 / 关系星 / 轴签 / HUD / 其它珠 / 带子链身 / 悬停卡片；
# 条数守恒（shown + N = 该回事件数）。返回有问题的回。
SWEEP_JS = r"""(function(){
  var L = CLSkyCompass._layout(), ks = [], band = CLSkyCompass.stats().band;
  L.dots.forEach(function(d, k){ if (d.r > 0) ks.push(k); });
  if (band) { var hid = []; L.dots.forEach(function(d, k){ if (d.r === 0 && d.count >= 2) hid.push(k); }); var sp = Math.max(1, Math.floor(hid.length / 20)); for (var i = 0; i < hid.length; i += sp) ks.push(hid[i]); }
  function R(e){ var r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }
  function ov(a, b, p){ return a[0] < b[2] - p && a[2] > b[0] + p && a[1] < b[3] - p && a[3] > b[1] + p; }
  function vis(e){ var cs = getComputedStyle(e); return cs.display !== 'none' && cs.visibility !== 'hidden' && e.getAttribute('visibility') !== 'hidden'; }
  function live(b){ return b[2] > b[0] && b[3] > b[1]; }
  var sats = [], axis, fixed, hud, bad = [], n = 0, more = 0;
  [].filter.call(document.querySelectorAll('.sky-compass .skc-sat'), vis).forEach(function(g){ [].forEach.call(g.querySelectorAll('text, circle'), function(e){ var b = R(e); if (live(b)) sats.push(b); }); });
  axis = [].filter.call(document.querySelectorAll('#labels .cl-lab.attr.on, #labels .cl-lab.meta.on'), vis).map(R).filter(live);
  fixed = [].map.call(document.querySelectorAll('.skc-chain-title'), R).concat([].map.call(document.querySelectorAll('.skc-rule'), function(e){ var r = R(e); return [r[0], r[1] - 1, r[2], r[3] + 1]; })).filter(function(b){ return b[2] > b[0]; });
  hud = [].filter.call(document.querySelectorAll('.sky-top, .sky-bottom > *:not([hidden]), .sky-lab:not([hidden]), #skyCrumb > *'), vis).map(R).filter(live);
  ks.forEach(function(k){
    CLSkyCompass.hoverEvent(k);
    /* 落定态：扇面入场动画与悬停卡片的入场 / 过渡都 finish 掉再量（减弱动效下全局仍有 .12s 过渡，见 app-shell.css） */
    document.querySelectorAll('.skc-fan *, .skc-card').forEach(function(e){ (e.getAnimations ? e.getAnimations() : []).forEach(function(a){ a.finish(); }); });
    var f = CLSkyCompassFan.stats(), info = CLSkyCompass.eventInfo(k), iss = [], j;
    var labs = [].map.call(document.querySelectorAll('.skc-fan .skc-fan-t, .skc-fan .skc-fan-more'), function(e){ var b = R(e); b.push(e.textContent); return b; });
    var beads = CLSkyCompass._layout().dots.filter(function(x, q){ return q !== k && x.r > 0; }).map(function(x){ return [x.x - x.r, x.y - x.r, x.x + x.r, x.y + x.r]; });
    var card = document.querySelector('.skc-card'), cr = card && !card.hidden ? R(card) : null;
    n++; if (f.more) more++;
    if (!f.open || f.k !== k) iss.push('not open');
    if (f.shown + f.more !== info.count || labs.length !== f.shown + (f.more ? 1 : 0)) iss.push('count ' + f.shown + '+' + f.more + '/' + info.count);
    labs.forEach(function(a, i){
      if (a[0] < 0 || a[1] < 0 || a[2] > innerWidth || a[3] > innerHeight) iss.push('out ' + a[4]);
      for (j = i + 1; j < labs.length; j++) if (ov(a, labs[j], 0.5)) iss.push('label×label ' + a[4] + '|' + labs[j][4]);
      [['title', fixed], ['sat', sats], ['axis', axis], ['hud', hud], ['bead', beads]].forEach(function(o){ if (o[1].some(function(b){ return ov(a, b, 0.5); })) iss.push(o[0] + ' ' + a[4]); });
      if (__sd.onBand(a)) iss.push('band ' + a[4]);
      if (cr && ov(a, cr, 0)) iss.push('card ' + a[4] + ' ' + a.slice(0, 4).map(Math.round) + ' × ' + cr.map(Math.round) + ' fan ' + f.box);
    });
    if (iss.length) bad.push({ k: k, no: info.no, count: info.count, iss: iss.slice(0, 4) });
  });
  CLSkyCompass.unhover();
  return { n: n, more: more, bad: bad, obst: [sats.length, axis.length, fixed.length, hud.length] };
})()"""


def sweep(b, tag, check):
    """F6：全珠扫描（三书 × 各视口）；障碍表不能是空的（否则判据恒真）"""
    b.mouse('mouseMoved', 5, b.h - 5); time.sleep(0.2)
    Z = b.ev(SWEEP_JS)
    check(tag + ' F6 every bead (+ ~20 band chapters): fan labels never overlap each other / title / relation stars / axis labels / HUD / other beads / band / card, never off-screen, shown + N = count',
          Z['n'] >= 3 and Z['obst'][0] > 0 and Z['obst'][1] > 0 and Z['obst'][2] > 0 and not Z['bad'], {'n': Z['n'], 'more': Z['more'], 'obst': Z['obst'], 'bad': Z['bad'][:6]})
    return Z


class Browser:
    def __init__(self, w, h, reduce=False, dpr=1):
        self.w, self.h, self.reduce, self.dpr = w, h, reduce, dpr
        self.ud = tempfile.mkdtemp(prefix='cl-satdrag-')
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
        self.ws.call('Emulation.setDeviceMetricsOverride', width=self.w, height=self.h, deviceScaleFactor=self.dpr, mobile=False)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        if self.reduce:
            self.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])

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
            raise RuntimeError('eval failed: %s :: %s' % (expr[:140], json.dumps(r['exceptionDetails'], ensure_ascii=False)[:600]))
        res = r.get('result', {})
        return res.get('value') if 'value' in res else None

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

    def mouse(self, kind, x, y, down=False):
        self.ws.call('Input.dispatchMouseEvent', type=kind, x=x, y=y, button='left' if kind != 'mouseMoved' or down else 'none',
                     buttons=1 if down else 0, clickCount=1 if kind in ('mousePressed', 'mouseReleased') else 0)

    def key(self, k):
        code = {'ArrowLeft': 37, 'ArrowUp': 38, 'ArrowRight': 39, 'ArrowDown': 40, 'Escape': 27, 'Enter': 13, 'Tab': 9}.get(k, 0)
        for t in ('keyDown', 'keyUp'):
            self.ws.call('Input.dispatchKeyEvent', type=t, key=k, code=k, windowsVirtualKeyCode=code)

    def shot(self, path):
        snap = self.ws.call('Page.captureScreenshot', format='png')
        with open(path, 'wb') as f:
            f.write(base64.b64decode(snap['data']))


def press_move(b, x0, y0, x1, y1, steps=12, dt=0.016):
    b.mouse('mouseMoved', x0, y0); time.sleep(0.04)
    b.mouse('mousePressed', x0, y0, down=True)
    for i in range(1, steps + 1):
        b.mouse('mouseMoved', x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps, down=True); time.sleep(dt)


def dist(a, b):
    a = (a['x'], a['y']) if isinstance(a, dict) else a
    b = (b['x'], b['y']) if isinstance(b, dict) else b
    return math.hypot(a[0] - b[0], a[1] - b[1])


def overlap(a, b, pad=0.0):
    return a[0] < b[2] - pad and a[2] > b[0] + pad and a[1] < b[3] - pad and a[3] > b[1] + pad


def reopen(b, who):
    b.ev("CLSky.openCompass(%s)" % json.dumps(who, ensure_ascii=False))
    ok = b.until("CLSky.state().compass === %s && CLSkyCompass.stats().open && CLSkyCompassDrag.stats().phase === 'idle'" % json.dumps(who, ensure_ascii=False), 20)
    time.sleep(3.4)   # 晶体飞入 + 入场点燃落定
    return ok


def run_session(a, book, data, w, h, check, shots, reduce=False):
    tag = '%s-%d%s' % (book, w, '-reduced' if reduce else '')
    b = Browser(w, h, reduce)
    b.start()
    try:
        b.ws.call('Page.navigate', url=a.base.rstrip('/') + '/?sky=1&probe=1&data=' + data)
        ok = b.until(READY_JS, 180)
        check(tag + ' page ready (loader curtain lifted)', ok)
        if not ok:
            return
        time.sleep(1.2)
        b.ev(HELP)
        who = b.ev("__sd.top()")
        check(tag + ' compass opens for the top character', reopen(b, who), who)
        L = b.ev("CLSkyCompass._layout(true)")
        sats, mode, E = L['sats'], L['mode'], L['B']
        cx, cy = E['cx'], E['cy']
        if len(sats) < 3:
            check(tag + ' at least 3 relation stars to drag', False, len(sats)); return

        # ── D1 跟手 + 张力 + 不转镜头 ──
        s = sats[0]
        ux, uy = s['x'] - cx, s['y'] - cy
        if mode != 'orbit':
            ux, uy = (1 if s['x'] > cx else -1) * 0.6, 0.8
        n = math.hypot(ux, uy) or 1
        d = 110 if mode == 'orbit' else 80
        tx, ty = s['x'] + ux / n * d, s['y'] + uy / n * d
        tx, ty = min(w - 24, max(24, tx)), min(h - 24, max(70, ty))
        d = math.hypot(tx - s['x'], ty - s['y'])
        rest = b.ev("(function(){ var l = __sd.link(%d), cs = getComputedStyle(l); return { sw: parseFloat(cs.strokeWidth), stroke: cs.stroke }; })()" % s['i'])
        cam0 = b.ev("__sd.cam()")
        tug0 = b.ev(TUG_JS)
        press_move(b, s['x'], s['y'], tx, ty)
        time.sleep(0.4)
        R = b.ev("""(function(){ var i = %d, p = __sd.tf(__sd.sat(i)), l = __sd.link(i), cs = getComputedStyle(l), e = __sd.ends(l.getAttribute('d')), st = CLSkyCompassDrag.stats();
          var r = +__sd.sat(i).querySelector('.skc-sat-star').getAttribute('r');
          return { p: p, end: e ? [e[e.length - 2], e[e.length - 1]] : null, rr: r, cls: l.getAttribute('class'), k: +(l.style.getPropertyValue('--skc-k') || 0), sw: parseFloat(cs.strokeWidth), stroke: cs.stroke,
            halo: document.querySelector('.skc-drag-halo').getAttribute('d') === l.getAttribute('d'), haloEmpty: !document.querySelector('.skc-drag-halo').getAttribute('d'), tier: __sd.tier(), st: st, comp: CLSky.state().compass, cam: __sd.cam(), tug: %s }; })()""" % (s['i'], TUG_JS))
        p = R['p']
        dev = dist(p, (tx, ty)) if p else 999
        moved = dist(p, (s['x'], s['y'])) if p else 0
        check(tag + ' D1 dragged star follows the pointer (≥ 0.85·d, off ≤ max(3, 0.15·d))', p and moved >= 0.85 * d and dev <= max(3, 0.15 * d) and R['st']['phase'] == 'drag',
              {'d': round(d, 1), 'moved': round(moved, 1), 'dev': round(dev, 1), 'st': R['st']})
        ed = dist(R['end'], p) if R['end'] and p else 999
        check(tag + ' D1 its line follows the star (end at star radius + 4 ± 1 px)', abs(ed - (R['rr'] + 4)) <= 1.0, {'endDist': round(ed, 2), 'rr': R['rr']})
        glow = R['halo'] if R['tier'] != 'low' else R['haloEmpty']   # low 档：不画辉光
        check(tag + ' D1 stretched line is taut: --skc-k > 0.1, thicker, recoloured, glow on the same path (none on the low tier)',
              'is-taut' in (R['cls'] or '') and R['k'] > 0.1 and R['sw'] > rest['sw'] + 0.2 and R['stroke'] != rest['stroke'] and glow,
              {'k': R['k'], 'sw': [rest['sw'], R['sw']], 'stroke': [rest['stroke'], R['stroke']], 'cls': R['cls'], 'halo': R['halo'], 'tier': R['tier']})
        c1 = R['cam']
        check(tag + ' D1 dragging does not rotate the camera or switch the compass (Δaz/Δpol < 0.2°)',
              abs(c1['az'] - cam0['az']) < 0.2 and abs(c1['pol'] - cam0['pol']) < 0.2 and dist(c1['t'], cam0['t']) < 1e-3 and R['comp'] == who, {'cam0': cam0, 'cam1': c1, 'comp': R['comp']})
        check(tag + ' D1 compass-side drag never engages the constellation tug (CLSkyTug idle, grabs unchanged, no scene tug keys)',
              tug_quiet(tug0, R['tug']), {'before': tug0, 'during': R['tug']})
        if shots:
            b.shot(os.path.join(shots, tag + '-drag.png'))

        # ── D3 松手回弹 ──
        b.ev("window.__smp = null; __sd.sample(%d, 1500).then(function(o){ window.__smp = o; }); true" % s['i'])
        b.mouse('mouseReleased', tx, ty)
        b.until("!!window.__smp", 10, 0.1)
        smp = b.ev("window.__smp") or []
        rel = [x for x in smp if x[1] is not None and x[4] is not None]
        over, t_last = 0.0, 0
        if rel:
            r0 = rel[0]
            vx, vy = r0[1] - r0[4], r0[2] - r0[5]
            vn = math.hypot(vx, vy) or 1
            for x in rel:
                proj = ((x[1] - x[4]) * vx + (x[2] - x[5]) * vy) / vn
                over = min(over, proj)
                if math.hypot(x[1] - x[4], x[2] - x[5]) > 0.5 or x[6] != 'idle':
                    t_last = x[0]
        time.sleep(0.2)
        after = b.ev("(function(){ var i = %d, a = __sd.tf(__sd.sat(i)), h = __sd.home(i); return { a: a, h: h ? [h.x, h.y] : null, st: CLSkyCompassDrag.stats(), comp: CLSky.state().compass }; })()" % s['i'])
        time.sleep(0.25)
        after2 = b.ev("(function(){ var i = %d, a = __sd.tf(__sd.sat(i)), h = __sd.home(i); return { a: a, h: h ? [h.x, h.y] : null, phase: CLSkyCompassDrag.stats().phase }; })()" % s['i'])
        if not reduce:
            check(tag + ' D3 release: underdamped rebound (crosses home by ≥ 1 px)', over <= -1.0, {'overshoot': round(over, 2), 'n': len(rel)})
        check(tag + ' D3 release: back home (≤ 0.5 px) within 1 s, then asleep (idle; later frames = home even when the layout re-flows)',
              rel and t_last <= 1000 and after['st']['phase'] == 'idle' and after['a'] and after['h'] and dist(after['a'], after['h']) <= 0.5 and after2['phase'] == 'idle' and dist(after2['a'], after2['h']) <= 0.5,
              {'settleMs': t_last, 'selfSettle': after['st'].get('settle'), 'a': after['a'], 'h': after['h'], 'a2': after2})
        check(tag + ' D3 a real drag released outside is not a click (compass unchanged)', after['comp'] == who, after['comp'])

        # ── D2 让位 ──
        L = b.ev("CLSkyCompass._layout(true)")
        sats, orb = L['sats'], L['orb']
        pair = None
        for j in sats:
            for k in sats:
                if j is k:
                    continue
                same = (mode == 'orbit' and j['side'] == k['side'] and j['side'] != 0) or (mode != 'orbit' and abs(j['y'] - k['y']) < 1)
                if same and dist(j, k) <= 150 and (pair is None or dist(j, k) < dist(pair[0], pair[1])):
                    pair = (j, k)
        if pair:
            j, k = pair
            far = [f for f in sats if f is not j and f is not k and dist(f, j) > 300]
            gx, gy = j['x'] + (k['x'] - j['x']) * 0.6, j['y'] + (k['y'] - j['y']) * 0.6
            press_move(b, j['x'], j['y'], gx, gy)
            time.sleep(0.45)
            # 家位与位置同一刻读：轴签随晶体翻转漂移时罗盘会重排（家位挪 1–2 px），拿按下前的家位比会把重排误算成让位 / 远星移动
            Y = b.ev("(function(){ var L = CLSkyCompass._layout(true), o = { tier: __sd.tier(), orb: L.orb, h: {} }; L.sats.forEach(function(s){ o.h[s.i] = [s.x, s.y]; }); [%d, %d%s].forEach(function(i){ o[i] = __sd.tf(__sd.sat(i)); }); return o; })()" % (j['i'], k['i'], ''.join(', %d' % f['i'] for f in far[:2])))
            pk, pj = Y[str(k['i'])], Y[str(j['i'])]
            hk_ = Y['h'][str(k['i'])]
            orb = Y['orb'] or orb
            disp = dist(pk, hk_)
            away = dist(pk, pj) > dist(hk_, pj)
            if mode == 'orbit' and orb:
                def extra(x, y, side):
                    t = max(-0.99, min(0.99, (y - orb['cy']) / orb['ry']))
                    return side * (x - orb['cx']) - orb['rx'] * math.sqrt(1 - t * t)
                along = abs(extra(pk[0], pk[1], k['side']) - extra(hk_[0], hk_[1], k['side']))
                track = along <= 0.6
            else:
                along = abs(pk[1] - hk_[1])
                track = along <= 0.5
            farOff = max([dist(Y[str(f['i'])], Y['h'][str(f['i'])]) for f in far[:2]] or [0])
            if reduce or Y['tier'] == 'low':
                check(tag + ' D6 reduced motion / low tier: neighbours do not yield (< 0.5 px)', disp < 0.5, {'drag': j['name'], 'nb': k['name'], 'disp': round(disp, 3), 'tier': Y['tier']})
            else:
                check(tag + ' D2 neighbour yields: pushed away, 1 … 23.5 px, along its orbit / row', 1.0 <= disp <= 23.5 and away and track,
                      {'drag': j['name'], 'nb': k['name'], 'disp': round(disp, 2), 'away': away, 'offTrack': round(along, 2)})
            check(tag + ' D2 stars on the other side stay put (< 0.5 px)', farOff < 0.5, {'farOff': round(farOff, 3), 'far': [f['name'] for f in far[:2]]})
            b.mouse('mouseReleased', gx, gy)
            time.sleep(1.2)
            back = b.ev("(function(){ var L = CLSkyCompass._layout(true), w = 0; L.sats.forEach(function(s){ var p = __sd.tf(__sd.sat(s.i)); w = Math.max(w, Math.hypot(p[0] - s.x, p[1] - s.y)); }); return { worst: w, st: CLSkyCompassDrag.stats() }; })()")
            check(tag + ' D2 after release every star is back home (≤ 0.5 px), drag asleep', back['worst'] <= 0.5 and back['st']['phase'] == 'idle', back)
        else:
            check(tag + ' D2 found a neighbouring pair to test yielding', False, [(x['name'], round(x['x']), round(x['y'])) for x in sats])

        # ── D6 low 档（钉住 degrade = 2）：只动拖动星，不让位、不画辉光；松手照样回家 ──
        if pair and book == 'saga' and w == 1440 and not reduce:
            j, k = pair
            # 自适应环：帧率连续 5 s > 54 就退一档（highRun ≥ 10）——第一下 setDegrade(2) 会被立刻退回并清零计数，再钉一次就能稳住约 5 s
            b.ev("CLApp.scene().setDegrade(2)"); time.sleep(0.7); b.ev("CLApp.scene().setDegrade(2)"); time.sleep(0.2)
            gx, gy = j['x'] + (k['x'] - j['x']) * 0.6, j['y'] + (k['y'] - j['y']) * 0.6
            press_move(b, j['x'], j['y'], gx, gy)
            time.sleep(0.4)
            Lo = b.ev("(function(){ var p = __sd.tf(__sd.sat(%d)), q = __sd.tf(__sd.sat(%d)), h = __sd.home(%d); return { tier: __sd.tier(), pj: p, pk: q, hk: [h.x, h.y], halo: document.querySelector('.skc-drag-halo').getAttribute('d') || '' }; })()" % (j['i'], k['i'], k['i']))
            b.mouse('mouseReleased', gx, gy)
            time.sleep(1.2)
            back = b.ev("(function(){ var L = CLSkyCompass._layout(true), w = 0; L.sats.forEach(function(s){ var p = __sd.tf(__sd.sat(s.i)); w = Math.max(w, Math.hypot(p[0] - s.x, p[1] - s.y)); }); return { worst: w, phase: CLSkyCompassDrag.stats().phase }; })()")
            b.ev("CLApp.scene().setDegrade(0)"); time.sleep(0.3)
            check(tag + ' D6 low tier: dragged star follows, neighbours do not yield, no glow; release returns home',
                  Lo['tier'] == 'low' and dist(Lo['pj'], (gx, gy)) <= 4 and dist(Lo['pk'], Lo['hk']) < 0.5 and not Lo['halo'] and back['worst'] <= 0.5 and back['phase'] == 'idle',
                  {'lo': Lo, 'back': back})

        # ── D5 点击（slop 内）照旧进罗盘 ──
        L = b.ev("CLSkyCompass._layout(true)")
        c = L['sats'][1]
        b.mouse('mouseMoved', c['x'], c['y']); time.sleep(0.05)
        b.mouse('mousePressed', c['x'], c['y'], down=True); time.sleep(0.04)
        b.mouse('mouseMoved', c['x'] + 2, c['y'] + 1, down=True); time.sleep(0.03)
        b.mouse('mouseReleased', c['x'] + 2, c['y'] + 1)
        hop = b.until("CLSky.state().compass === %s" % json.dumps(c['name'], ensure_ascii=False), 4)
        check(tag + ' D5 press + release within the slop = click: enters that star\'s compass', hop, {'want': c['name'], 'got': b.ev("CLSky.state().compass")})
        reopen(b, who)

        # ── D4 拖进晶体 = 吸入后进入他的罗盘 ──
        L = b.ev("CLSkyCompass._layout(true)")
        s = L['sats'][2]
        A = b.ev("__sd.anchor()")
        press_move(b, s['x'], s['y'], A[0], A[1], steps=16)
        time.sleep(0.35)
        arm = b.ev("({ st: CLSkyCompassDrag.stats(), cls: document.querySelector('.sky-compass').getAttribute('class'), box: __sd.crown(), a: __sd.anchor(), tug: %s })" % TUG_JS)
        if shots and not reduce:
            b.shot(os.path.join(shots, tag + '-armed.png'))
        b.ev("window.__smp = null; __sd.sample(%d, 700).then(function(o){ window.__smp = o; }); true" % s['i'])
        b.mouse('mouseReleased', A[0], A[1])
        t_rel = time.time()
        if reduce:
            instant = b.until("CLSky.state().compass === %s" % json.dumps(s['name'], ensure_ascii=False), 1, 0.05)
            t_sw = time.time() - t_rel
        b.until("!!window.__smp", 10, 0.1)
        smp = b.ev("window.__smp") or []
        sucked = [x for x in smp if x[6] == 'suck']
        entered = b.until("CLSky.state().compass === %s" % json.dumps(s['name'], ensure_ascii=False), 4)
        inb = arm['box'] and arm['box'][0] <= A[0] <= arm['box'][2] and arm['box'][1] <= A[1] <= arm['box'][3]
        check(tag + ' D4 dragged over the crystal box: armed (skc-armed)', inb and arm['st']['armed'] and 'skc-armed' in arm['cls'], arm)
        check(tag + ' D4 dragging over the crystal (stars hidden behind it) does not wake the constellation tug', tug_quiet(tug0, arm['tug']), {'before': tug0, 'armed': arm['tug']})
        if reduce:
            check(tag + ' D6 reduced motion: drop switches at once, no suck-in frames', instant and not sucked and t_sw < 0.6, {'switchS': round(t_sw, 3), 'suckFrames': len(sucked)})
        else:
            dd = [math.hypot(x[1] - arm['a'][0], x[2] - arm['a'][1]) for x in sucked if x[1] is not None]
            shrink = [x[3] for x in sucked]
            check(tag + ' D4 suck-in: star shrinks and closes in on the crystal heart',
                  len(sucked) >= 3 and min(shrink) < 0.9 and dd and dd[-1] < dd[0] and all(dd[q + 1] <= dd[q] + 1.5 for q in range(len(dd) - 1)),
                  {'frames': len(sucked), 'scale': [round(min(shrink or [1]), 3)], 'dist': [round(x, 1) for x in dd[:3] + dd[-2:]]})
        check(tag + ' D4 dropped into the crystal → enters his compass', entered, {'want': s['name'], 'got': b.ev("CLSky.state().compass")})
        reopen(b, who)

        # ── 减弱动效：跟手照常，松手一帧到位 ──
        if reduce:
            L = b.ev("CLSkyCompass._layout(true)")
            s = L['sats'][0]
            ux, uy = s['x'] - cx, s['y'] - cy
            n = math.hypot(ux, uy) or 1
            tx, ty = min(w - 24, max(24, s['x'] + ux / n * 100)), min(h - 24, max(70, s['y'] + uy / n * 100))
            d = math.hypot(tx - s['x'], ty - s['y'])
            press_move(b, s['x'], s['y'], tx, ty)
            time.sleep(0.4)
            p = b.ev("__sd.tf(__sd.sat(%d))" % s['i'])
            moved = dist(p, (s['x'], s['y']))
            check(tag + ' D6 reduced motion: dragging still follows (≥ 0.85·d)', moved >= 0.85 * d, {'d': round(d, 1), 'moved': round(moved, 1)})
            b.ev("window.__smp = null; __sd.sample(%d, 300).then(function(o){ window.__smp = o; }); true" % s['i'])
            b.mouse('mouseReleased', tx, ty)
            b.until("!!window.__smp", 10, 0.1)
            smp = b.ev("window.__smp") or []
            first = smp[0] if smp else None
            bad = [x for x in smp if x[1] is None or math.hypot(x[1] - x[4], x[2] - x[5]) > 0.5 or x[6] != 'idle' or x[7] is None or math.hypot(x[7] - x[4], x[8] - x[5]) > 0.5]
            check(tag + ' D6 reduced motion: released star is home on the very next frame, as drawn too (no rebound / no CSS slide)', smp and not bad, {'first': first, 'bad': bad[:3]})

        # ── F 扇出 ──
        D = b.ev("CLSkyCompass._layout().dots.map(function(d, k){ return [k, d.x, d.y, d.r, d.count]; })")
        band = b.ev("CLSkyCompass.stats().band")
        shown = [x for x in D if x[3] > 0]
        big = max(shown, key=lambda x: (x[4], -x[0]))
        b.mouse('mouseMoved', big[1], big[2])
        time.sleep(0.75)
        F = b.ev("""(function(){ var k = %d, f = CLSkyCompassFan.stats(), info = CLSkyCompass.eventInfo(f.k), who = CLSky.state().compass;
          var labs = __sd.rects('.skc-fan .skc-fan-i:not(.is-more) .skc-fan-t'), more = __sd.rects('.skc-fan .skc-fan-more');
          var titles = CLApp.graph().events.filter(function(e){ return (e.characters || []).indexOf(who) >= 0; }).map(function(e){ return e.title || ''; });
          var real = labs.every(function(l){ var t = l[4].replace(/…$/, ''); return titles.some(function(x){ return x.indexOf(t) === 0; }); });
          var fixed = __sd.rects('.skc-chain-title').concat([].map.call(document.querySelectorAll('.skc-rule'), function(e){ var r = e.getBoundingClientRect(); return [r.left, r.top - 1, r.right, r.bottom + 1]; }));
          return { f: f, k: k, count: info ? info.count : null, labs: labs, more: more, real: real, fixed: fixed,
            band: labs.concat(more).map(function(l){ return __sd.onBand(l); }), W: innerWidth, H: innerHeight }; })()""" % big[0])
        labs = F['labs'] + F['more']
        nshown = len(F['labs'])
        nmore = int(F['more'][0][4][1:]) if F['more'] else 0
        check(tag + ' F1 hover the busiest bead: fan lists every event of that chapter (shown + N = count)',
              F['f']['open'] and F['f']['k'] == big[0] and F['count'] == big[4] and nshown + nmore == F['count'] and (nmore == 0 or nshown >= 1) and F['real'],
              {'k': F['f']['k'], 'want': big[0], 'count': F['count'], 'shown': nshown, 'more': nmore, 'real': F['real'], 'labels': [x[4] for x in labs]})
        ov = sum(1 for i1 in range(len(labs)) for i2 in range(i1 + 1, len(labs)) if overlap(labs[i1], labs[i2], 0.5))
        ovf = sum(1 for l in labs for fx in F['fixed'] if fx[2] > fx[0] and overlap(l, fx, 0.5))
        out = [l[4] for l in labs if l[0] < 0 or l[1] < 0 or l[2] > F['W'] or l[3] > F['H']]
        check(tag + ' F2 fan labels: no overlap with each other, the chain title / rules, the band / chain; inside the viewport',
              ov == 0 and ovf == 0 and not any(F['band']) and not out, {'overlap': ov, 'title': ovf, 'band': F['band'], 'outside': out})
        if shots and not reduce:
            b.shot(os.path.join(shots, tag + '-fan.png'))
        # 悬停不动：罗盘每秒会因晶体 / 轴签重排几次（链身随晶体包络左右挪 1–2 px），扇面跟着珠走，但不得重放入场动画（原先每 ~1 s 闪一次）
        b.ev("""(function(){ window.__fanS = { n: 0, anim: 0, rel: 0, labs: [] }; var S = CLApp.scene(), t0 = performance.now(), off = null;
          var r0 = CLSkyCompassFan.relayout; if (!r0.__w) { CLSkyCompassFan.relayout = function(){ __fanS.rel++; return r0.apply(this, arguments); }; CLSkyCompassFan.relayout.__w = 1; }
          off = S.registerFrameHook(function(){ if (performance.now() - t0 > 2200) { off(); __fanS.done = true; return; } __fanS.n++;
            [].forEach.call(document.querySelectorAll('.skc-fan *'), function(e){ e.getAnimations().forEach(function(a){ if (a.playState === 'running') __fanS.anim++; }); });
            var k = document.querySelectorAll('.skc-fan .skc-fan-t').length; if (__fanS.labs.indexOf(k) < 0) __fanS.labs.push(k); }); return true; })()""")
        b.until("!!(window.__fanS && __fanS.done)", 6, 0.1)
        FM = b.ev("({ s: __fanS, open: CLSkyCompassFan.stats().open, cls: document.querySelector('.skc-fan').getAttribute('class') })")
        check(tag + ' F7 resting on a bead for 2.2 s: the fan follows re-layouts without replaying its entry (0 running animations, label count steady)',
              FM['open'] and FM['s']['n'] >= 20 and FM['s']['anim'] == 0 and len(FM['s']['labs']) == 1, FM)
        b.mouse('mouseMoved', 12, h * 0.5)
        time.sleep(0.45)
        G = b.ev("({ f: CLSkyCompassFan.stats(), vis: __sd.rects('.skc-fan text').filter(function(x){ return x[5] > 0.05; }).length })")
        check(tag + ' F3 leaving the bead folds the fan back (no visible labels after 0.45 s)', not G['f']['open'] and G['vis'] == 0, G)
        sweep(b, tag, check)
        if band:
            hid = [x for x in D if x[3] == 0 and x[4] >= 2]
            if hid:
                hb = hid[len(hid) // 2]
                b.mouse('mouseMoved', hb[1], hb[2])
                time.sleep(0.5)
                H = b.ev("(function(){ var f = CLSkyCompassFan.stats(), L = CLSkyCompass._layout(), d = L.dots[f.k]; return { f: f, x: d ? d.x : null, count: f.k >= 0 ? CLSkyCompass.eventInfo(f.k).count : null }; })()")
                check(tag + ' F4 band: hovering a chapter without a bead fans out that chapter', H['f']['open'] and H['x'] is not None and abs(H['x'] - hb[1]) <= 2.0 and H['f']['shown'] + H['f']['more'] == H['count'],
                      {'want': hb[:1] + [round(hb[1], 1)], 'got': H})
                b.mouse('mouseMoved', 12, h * 0.5)
                time.sleep(0.3)
        if reduce:
            b.mouse('mouseMoved', big[1], big[2])
            time.sleep(0.4)
            an = b.ev("[].map.call(document.querySelectorAll('.skc-fan .skc-fan-t, .skc-fan .skc-fan-rib'), function(e){ return getComputedStyle(e).animationName; })")
            check(tag + ' D6 reduced motion: fan opens without animation', an and all(x == 'none' for x in an), an[:4])
            b.mouse('mouseMoved', 12, h * 0.5)
            time.sleep(0.3)

        # ── F5 键盘 ──
        K0 = b.ev("(function(){ var e = [].filter.call(document.querySelectorAll('.sky-compass .skc-ev[tabindex=\"0\"]'), function(x){ return x.getAttribute('visibility') !== 'hidden'; })[0]; e.focus(); return +e.getAttribute('data-ev'); })()")
        time.sleep(0.4)
        k0 = b.ev("({ f: CLSkyCompassFan.stats(), cam: __sd.cam() })")
        b.key('ArrowRight'); time.sleep(0.35)
        k1 = b.ev("({ f: CLSkyCompassFan.stats(), act: document.activeElement.getAttribute('data-ev') || document.activeElement.getAttribute('data-band'), cam: __sd.cam(), mode: CLSky.state().mode })")
        b.key('Escape'); time.sleep(0.3)
        k2 = b.ev("({ open: CLSkyCompassFan.stats().open, mode: CLSky.state().mode })")
        b.key('Enter'); time.sleep(0.3)
        k3 = b.ev("({ f: CLSkyCompassFan.stats() })")
        b.key('Tab'); time.sleep(0.35)
        k4 = b.ev("({ f: CLSkyCompassFan.stats(), act: +document.activeElement.getAttribute('data-ev'), tag: document.activeElement.getAttribute('class') })")
        b.key('Escape'); time.sleep(0.25)
        k5 = b.ev("({ open: CLSkyCompassFan.stats().open, mode: CLSky.state().mode })")
        b.key('Escape'); time.sleep(0.9)
        k6 = b.ev("CLSky.state().mode")
        rot = abs(k1['cam']['az'] - k0['cam']['az']) + abs(k1['cam']['pol'] - k0['cam']['pol'])
        check(tag + ' F5 focus a bead opens its fan; → moves to the next chapter without rotating the camera',
              k0['f']['open'] and k0['f']['k'] == K0 and k1['f']['open'] and k1['f']['k'] == K0 + 1 and k1['mode'] == 'compass' and rot < 0.2 and k1['act'] is not None,
              {'k0': k0['f'], 'k1': k1['f'], 'act': k1['act'], 'rot': round(rot, 4)})
        check(tag + ' F5 Esc folds (still in the compass); Enter re-opens; Tab reaches another bead with its fan',
              not k2['open'] and k2['mode'] == 'compass' and k3['f']['open'] and k3['f']['k'] == K0 + 1 and k4['f']['open'] and k4['act'] > K0 + 1 and k4['f']['k'] == k4['act'],
              {'esc': k2, 'enter': k3['f'], 'tab': k4})
        check(tag + ' F5 Esc folds again, a second Esc hands over to the shell (leaves the compass)', not k5['open'] and k5['mode'] == 'compass' and k6 == 'constellation', {'k5': k5, 'k6': k6})

        # ── D7 罗盘态空白处左键拖 = 旋转（不平移、不换人、不起拖拽 / 牵引） ──
        if reopen(b, who):
            L = b.ev("CLSkyCompass._layout(true)")
            E = L['B']
            def room(p):
                if abs(p[0] - E['cx']) < E['cw'] / 2 + 60 and abs(p[1] - E['cy']) < E['chh'] / 2 + 60:
                    return 0
                return min(math.hypot(p[0] - q['x'], p[1] - q['y']) for q in L['sats'])
            bp = max([(x, y) for x in range(40, w - 40, 30) for y in range(140, int(h * 0.7), 30)], key=room)
            c0, t0 = b.ev("__sd.cam()"), b.ev(TUG_JS)
            dx = 120 if bp[0] < w / 2 else -120
            press_move(b, bp[0], bp[1], bp[0] + dx, bp[1] + 10, steps=14)
            time.sleep(0.15)
            c1, st1, t1 = b.ev("__sd.cam()"), b.ev("CLSkyCompassDrag.stats().phase"), b.ev(TUG_JS)
            b.mouse('mouseReleased', bp[0] + dx, bp[1] + 10)
            time.sleep(0.6)
            check(tag + ' D7 in the compass, a left-drag on empty space still rotates (|Δaz| > 2°), target fixed, no star drag / tug, same compass',
                  abs(c1['az'] - c0['az']) > 2 and dist(c1['t'], c0['t']) < 1e-3 and st1 == 'idle' and tug_quiet(t0, t1) and b.ev("CLSky.state().compass") == who,
                  {'pt': bp, 'daz': round(c1['az'] - c0['az'], 2), 'dt': round(dist(c1['t'], c0['t']), 5), 'drag': st1, 'tug': t1})

        hl = b.ev(headless.POST_HEALTH_JS)
        errs = [x for x in (hl.get('jserr'), hl.get('jsrej')) if x not in (None, 'none')]
        check(tag + ' no JS errors / rejections / shader errors / frame-hook errors', not errs and not hl.get('shaderErrors') and not (hl.get('errorCounts') or {}).get('frameHooks'),
              {'errs': errs, 'shader': hl.get('shaderErrors'), 'counts': hl.get('errorCounts'), 'last': hl.get('frameHookLastError')})
    finally:
        b.close()


def run_4k(a, book, data, check):
    """大书 4K 视口（1920×1080 × dpr 2）：扇出全珠扫描 + 一次拖拽跟手 / 回家（不截图：dpr 2 截图会合成半坐标 mousemove）"""
    tag = '%s-4k' % book
    b = Browser(1920, 1080, dpr=2)
    b.start()
    try:
        b.ws.call('Page.navigate', url=a.base.rstrip('/') + '/?sky=1&probe=1&data=' + data)
        ok = b.until(READY_JS, 180)
        check(tag + ' page ready (loader curtain lifted)', ok)
        if not ok:
            return
        time.sleep(1.2)
        b.ev(HELP)
        who = b.ev("__sd.top()")
        check(tag + ' compass opens for the top character', reopen(b, who), who)
        sweep(b, tag, check)
        L = b.ev("CLSkyCompass._layout(true)")
        s, E = L['sats'][0], L['B']
        ux, uy = s['x'] - E['cx'], s['y'] - E['cy']
        n = math.hypot(ux, uy) or 1
        tx, ty = min(1896, max(24, s['x'] + ux / n * 120)), min(1056, max(70, s['y'] + uy / n * 120))
        d = math.hypot(tx - s['x'], ty - s['y'])
        tug0 = b.ev(TUG_JS)
        press_move(b, s['x'], s['y'], tx, ty)
        time.sleep(0.4)
        R = b.ev("({ p: __sd.tf(__sd.sat(%d)), st: CLSkyCompassDrag.stats(), tug: %s })" % (s['i'], TUG_JS))
        moved = dist(R['p'], (s['x'], s['y'])) if R['p'] else 0
        dev = dist(R['p'], (tx, ty)) if R['p'] else 999
        check(tag + ' D1 dragged star follows the pointer at dpr 2; tug stays idle', R['st']['phase'] == 'drag' and moved >= 0.85 * d and dev <= max(3, 0.15 * d) and tug_quiet(tug0, R['tug']),
              {'d': round(d, 1), 'moved': round(moved, 1), 'dev': round(dev, 1), 'st': R['st'], 'tug': R['tug']})
        b.mouse('mouseReleased', tx, ty)
        time.sleep(1.3)
        back = b.ev("(function(){ var L = CLSkyCompass._layout(true), w = 0; L.sats.forEach(function(s){ var p = __sd.tf(__sd.sat(s.i)); w = Math.max(w, Math.hypot(p[0] - s.x, p[1] - s.y)); }); return { worst: w, st: CLSkyCompassDrag.stats(), comp: CLSky.state().compass }; })()")
        check(tag + ' D3 released at dpr 2: all stars home (≤ 0.5 px), asleep, same compass', back['worst'] <= 0.5 and back['st']['phase'] == 'idle' and back['comp'] == who, back)
        hl = b.ev(headless.POST_HEALTH_JS)
        errs = [x for x in (hl.get('jserr'), hl.get('jsrej')) if x not in (None, 'none')]
        check(tag + ' no JS errors / rejections / shader errors / frame-hook errors', not errs and not hl.get('shaderErrors') and not (hl.get('errorCounts') or {}).get('frameHooks'),
              {'errs': errs, 'shader': hl.get('shaderErrors'), 'counts': hl.get('errorCounts')})
    finally:
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--shots', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'sky-satdrag'))
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    os.makedirs(a.shots, exist_ok=True)
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False, default=str)[:900]), flush=True)

    for book, data in BOOKS:
        if a.only and book not in a.only.split(','):
            continue
        for w, h in ((1440, 900), (390, 844)):
            run_session(a, book, data, w, h, check, a.shots)
    if not a.only or 'saga' in a.only.split(','):
        run_session(a, 'saga', BOOKS[0][1], 1440, 900, check, a.shots, reduce=True)
    if not a.only or 'dafeng' in a.only.split(','):
        run_4k(a, 'dafeng', BOOKS[2][1], check)

    ok = sum(1 for _, x in res if x)
    print(('SKY-SATDRAG OK' if ok == len(res) else 'SKY-SATDRAG FAIL') + ' · %d/%d' % (ok, len(res)))
    sys.exit(0 if ok == len(res) else 1)


if __name__ == '__main__':
    main()
