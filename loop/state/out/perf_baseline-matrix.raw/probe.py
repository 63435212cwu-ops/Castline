#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""perf:baseline-matrix 的实测探针（只读复用 tests/ 的既有 CDP 驾驭器，不改受保护路径）。

用法：
  python3 loop/state/out/perf_baseline-matrix.raw/probe.py --book dafeng
  python3 loop/state/out/perf_baseline-matrix.raw/probe.py --book dafeng --long-windows 6 --long-seconds 120

分路径（每个路径单独记档位，禁止混报）：
  startup    1440x900 dsf=1（冷启动首帧 / 有意义内容 / 首次可交互）
  steady     原生 3840x2160 dsf=1（boost 钉住、degrade 0、dip off）
  transition 同 steady 档位（进入/退出/视图/质量切换/resize/返回 各 20 次）
  long       同 steady 档位（连续 2 分钟窗口 × N，每窗单独记，不合并成一次短测）
"""
import argparse, base64, json, os, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]   # …/星系/loop/state/out/<dir> → 仓库根
sys.path.insert(0, str(ROOT / 'tests'))
from atlas_review_shots import Session          # noqa: E402  （真 GPU：--use-angle=metal）
import headless                                  # noqa: E402
headless.reap_orphans = lambda: None             # 由本探针自己管生命周期，不收割并发兄弟

BOOKS = {
    'dafeng': ('大奉打更人', '9b676d7031b1bcd3b8377a18'),
    'xiyou':  ('西游记',     'df959d743e53206f56db2f92'),
    'sanguo': ('三国演义',   '152e2a6eed94f1075e7e7070'),
}

INIT = r"""(function(){
  var pf = window.__pf = {t0: performance.now(), firstRaf: null, sceneCreated: null, sceneFrame: null,
                          contentReady: null, loaderOff: null, controlEnabled: null};
  (function loop(){
    var now = performance.now();
    if (pf.firstRaf === null) pf.firstRaf = now;
    try {
      var S = window.CLApp && window.CLApp.scene && window.CLApp.scene();
      if (S) {
        if (pf.sceneCreated === null) pf.sceneCreated = now;
        var d = S.digest();
        if (d.frames > 0 && pf.sceneFrame === null) pf.sceneFrame = now;
        // 「有意义内容」= 场景已在渲染 且 图谱已有节点（不是空舞台）。
        // 注意：nodes 在 perf() 里，不在 digest() 里。
        if (pf.contentReady === null && d.frames > 0 && S.perf().nodes > 0 &&
            window.CLApp.graph && window.CLApp.graph()) pf.contentReady = now;
      }
      // 兼容幕布：app.js 的 #loader（class 'off' 转场 .8s）与 sky-shell 的幕布都算
      var L = document.getElementById('loader');
      var gone = false;
      if (L) {
        var cs = getComputedStyle(L);
        gone = L.classList.contains('off') || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.05;
      }
      if (L && gone && pf.loaderOff === null) pf.loaderOff = now;
      var btn = document.getElementById('btnStage');
      if (btn && !btn.disabled && pf.controlEnabled === null) pf.controlEnabled = now;
    } catch (e) { pf.err = String(e && (e.stack || e.message) || e); }
    requestAnimationFrame(loop);
  })();
})();"""

STARTUP = r"""(function(){
  var pf = window.__pf || {}, S = window.CLApp && window.CLApp.scene && window.CLApp.scene();
  var nav = (performance.getEntriesByType('navigation') || [])[0] || {};
  var paints = {};
  (performance.getEntriesByType('paint') || []).forEach(function(e){ paints[e.name] = +e.startTime.toFixed(2); });
  var out = {now: +performance.now().toFixed(2), firstRaf: pf.firstRaf, sceneCreated: pf.sceneCreated,
             sceneFrame: pf.sceneFrame, contentReady: pf.contentReady, loaderOff: pf.loaderOff,
             controlEnabled: pf.controlEnabled, err: pf.err || null, paints: paints,
             nav: {responseStart: nav.responseStart, domInteractive: nav.domInteractive,
                   domContentLoaded: nav.domContentLoadedEventEnd, loadEnd: nav.loadEventEnd,
                   transferSize: nav.transferSize, decodedBodySize: nav.decodedBodySize},
             graphReady: !!(window.CLApp && CLApp.graph && CLApp.graph()),
             dom: document.getElementsByTagName('*').length};
  if (S) { var d = S.digest(); out.frames = d.frames; out.fps = S.perf().fps; out.quality = S.quality();
           out.nodes = S.perf().nodes; out.fibers = S.perf().fibers;
           out.canvas = [S.renderer.domElement.width, S.renderer.domElement.height]; }
  out.ready = !!(out.sceneFrame !== null && out.graphReady);
  return out;})()"""

INTERACT = r"""new Promise(function(resolve){
  var t0 = performance.now(), res = {armed: true}, S = CLApp.scene();
  var el = document.getElementById('btnStage');
  if (!el) { res.err = 'no #btnStage'; return resolve(res); }
  var before = document.body.dataset.atlasView || '', pressed = el.getAttribute('aria-pressed');
  el.click();
  var blocked = performance.now() - t0;
  requestAnimationFrame(function(){ requestAnimationFrame(function(){
    res.syncMs = +blocked.toFixed(2); res.servedMs = +(performance.now() - t0).toFixed(2);
    res.viewBefore = before; res.viewAfter = document.body.dataset.atlasView || '';
    res.pressedBefore = pressed; res.pressedAfter = el.getAttribute('aria-pressed');
    resolve(res); }); });})"""

SAMPLE = r"""new Promise(function(resolve){
  var S = CLApp.scene(), R = S.renderer, gl = R.getContext();
  var start = performance.now(), last = start, deltas = [], lt = [], obs = null;
  try {
    obs = new PerformanceObserver(function(list){ list.getEntries().forEach(function(e){ lt.push([+e.startTime.toFixed(2), +e.duration.toFixed(2)]); }); });
    obs.observe({entryTypes: ['longtask']});
  } catch (e) {}
  function counters(){
    /* three.js 的 renderer.info 每次 render() 会 reset；主 composer 内部有多个 pass，
       所以必须在**一帧的边界**累积，否则读到的是最后一个 pass 的残值（实测 calls=1）。
       用一次 rAF 取样并累加整个 composer 本帧的全部 pass。 */
    return new Promise(function(res){
      var before = R.info.autoReset; R.info.autoReset = false;
      requestAnimationFrame(function(){
        var snap = {calls: R.info.render.calls, triangles: R.info.render.triangles, lines: R.info.render.lines,
                    points: R.info.render.points, geometries: R.info.memory.geometries, textures: R.info.memory.textures,
                    programs: (R.info.programs||[]).length};
        R.info.autoReset = before; R.info.reset();
        res(snap);
      });
    });
  }
  function fin(){
    try { if (obs) obs.disconnect(); } catch (e) {}
    var end = performance.now(), s = deltas.slice().sort(function(a,b){return a-b;});
    function q(p){ return s.length ? s[Math.min(s.length-1, Math.floor(s.length*p))] : null; }
    var d = S.digest(), p = S.perf();
    counters().then(function(rc){
    resolve({elapsedMs: +(end-start).toFixed(1), frames: deltas.length, fps: +(deltas.length/(end-start)*1000).toFixed(3),
      p50: q(.5), p95: q(.95), p99: q(.99), max: s.length ? s[s.length-1] : null,
      over334: deltas.filter(function(x){return x>33.4;}).length, over50: deltas.filter(function(x){return x>50;}).length,
      over100: deltas.filter(function(x){return x>100;}).length,
      longTasks: lt, longTaskMax: lt.reduce(function(a,b){return Math.max(a,b[1]);},0), longTaskTotal: lt.reduce(function(a,b){return a+b[1];},0),
      dom: document.getElementsByTagName('*').length,
      heapMB: (performance.memory && performance.memory.usedJSHeapSize) ? +(performance.memory.usedJSHeapSize/1048576).toFixed(1) : null,
      quality: S.quality(), perf: p, degrade: d.degrade, calm: d.calm, nodes: p.nodes, fibers: p.fibers, tAnim: d.tAnim,
      renderer: rc,
      gl: {drawingBufferWidth: gl.drawingBufferWidth, drawingBufferHeight: gl.drawingBufferHeight,
           renderer: gl.getParameter(gl.RENDERER), vendor: gl.getParameter(gl.VENDOR), error: gl.getError()},
      view: document.body.dataset.atlasView || '', cssViewport: [window.innerWidth, window.innerHeight], dpr: window.devicePixelRatio,
      _deltas: deltas.map(function(x){ return +x.toFixed(2); })});
    });
  }
  function frame(){
    var now = performance.now(); deltas.push(now-last); last = now;
    if (now-start >= DURATION) fin(); else requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);})"""

# 每种转场一次调用 + 同步阻塞时长 + 之后两帧的帧间隔（抓主线程冻结）。REPS 次取分位。
TRANSITION = r"""new Promise(function(resolve){
  var out = [], i = 0;
  function one(){
    var t0 = performance.now(), err = null;
    try { KIND_JS } catch (e) { err = String(e && (e.stack || e.message) || e); }
    var sync = performance.now() - t0;
    requestAnimationFrame(function(){ var f1 = performance.now() - t0;
      requestAnimationFrame(function(){
        out.push({sync: +sync.toFixed(2), f1: +f1.toFixed(2), f2: +(performance.now()-t0).toFixed(2), err: err,
                  view: document.body.dataset.atlasView || '', degrade: CLApp.scene().quality().degrade});
        if (++i < REPS) one(); else resolve({kind: KIND, reps: out.length, samples: out});
      }); });
  }
  one();})"""

# 注意：open()/close()/view('domains') 都是**幂等**操作 —— 同一个状态连调 20 次，
# 只有第一次是真转场，其余是空操作，会把分位数稀释成「没有成本」。故这里显式交替。
KINDS = {
    'enter':    "(window.__alt = !window.__alt) ? CLAtlasStage.close() : CLAtlasStage.open()",
    'exit':     "(window.__alt2 = !window.__alt2) ? CLAtlasStage.open() : CLAtlasStage.close()",
    'view':     "CLApp.atlas.view(document.body.dataset.atlasView === 'annulus' ? 'domains' : 'annulus')",
    'plot':     "CLPlot.toggle()",
    'quality':  "CLApp.scene().setDegrade(CLApp.scene().quality().degrade === 0 ? 2 : 0)",
    'return':   "CLApp.atlas.view(document.body.dataset.atlasView === 'domains' ? 'annulus' : 'domains')",
}


def summarise(vals):
    if not vals:
        return None
    s = sorted(vals)
    def q(p):
        return round(s[min(len(s)-1, int(len(s)*p))], 2)
    return {'n': len(s), 'p50': q(.5), 'p95': q(.95), 'p99': q(.99), 'max': round(s[-1], 2), 'mean': round(statistics.fmean(s), 2)}


def pin_native4k(session, settle=6.0):
    """把会话钉在原生 3840x2160 / dsf=1 / degrade0 / boost1，并**回读校验**。

    真实事故（本次实测踩到）：转场阶段最后一步 resize 会把视口留在 1440x900，
    若之后直接开长时窗口，长测就跑在 1440x900 上 —— 正是任务明令禁止的「混用分辨率」，
    而且因为 fps 好看（60fps）极易被当成「长时也达标」。故每个阶段前都必须重新钉一次。
    """
    session.ws.call('Emulation.setDeviceMetricsOverride', width=3840, height=2160,
                    deviceScaleFactor=1, mobile=False)
    time.sleep(1.5)
    session.eval('CLApp.scene().resize()', False)
    time.sleep(0.5)
    session.eval('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)', False)
    time.sleep(settle)
    return session.eval("(function(){var S=CLApp.scene(),q=S.quality(),gl=S.renderer.getContext();"
                        "return {quality:q,perf:S.perf(),gl:{renderer:gl.getParameter(gl.RENDERER),"
                        "dbw:gl.drawingBufferWidth,dbh:gl.drawingBufferHeight}};})()")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--book', required=True, choices=list(BOOKS))
    ap.add_argument('--base', default='http://127.0.0.1:8123')
    ap.add_argument('--out', default=str(HERE))
    ap.add_argument('--startup-size', default='1440x900')
    ap.add_argument('--steady-seconds', type=float, default=20)
    ap.add_argument('--reps', type=int, default=20)
    ap.add_argument('--long-windows', type=int, default=0)
    ap.add_argument('--long-seconds', type=float, default=120)
    ap.add_argument('--startup-timeout', type=float, default=120)
    ap.add_argument('--deadline-epoch', type=float, default=0,
                    help='硬墙钟上限（epoch 秒）。到点后不再开始新的长时窗口，并如实记录 remaining_wall。')
    args = ap.parse_args()
    name, key = BOOKS[args.book]
    data = 'data/cache/%s.json' % key
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    sw, sh = (int(x) for x in args.startup_size.split('x'))
    rec = {'book': args.book, 'bookName': name, 'graphKey': key, 'data': data,
           'base': args.base, 'startedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'startupViewport': [sw, sh, 1], 'steadyViewport': [3840, 2160, 1]}

    s = Session(sw, sh)
    t_start = time.time()
    try:
        s.start()
        s.ws.call('Emulation.setDeviceMetricsOverride', width=sw, height=sh, deviceScaleFactor=1, mobile=False)
        s.ws.call('Page.addScriptToEvaluateOnNewDocument', source=INIT)
        nav_t0 = time.time()
        s.navigate(args.base + '/?data=' + data + '&sky=1')
        ready = None
        last = None
        milestones = None
        while time.time() - nav_t0 < args.startup_timeout:
            try:
                cur = s.eval(STARTUP)
            except Exception as exc:
                cur = {'evalError': str(exc)}
            last = cur
            if isinstance(cur, dict) and cur.get('ready'):
                # 阶段 A：场景已在渲染 + 图谱已建 = 首帧/有意义内容可达
                ready = cur
                break
            time.sleep(0.05)
        # 阶段 B：继续等幕布淡出与控件可用（首次可交互的客观里程碑），最多再等 8 s；
        # 等不到就如实记 null，不假装等到。
        if ready is not None:
            t_b = time.time()
            while time.time() - t_b < 8.0:
                cur = s.eval(STARTUP)
                last = cur
                if cur.get('contentReady') is not None and cur.get('loaderOff') is not None and cur.get('controlEnabled') is not None:
                    break
                time.sleep(0.05)
            milestones = cur
        rec['startup'] = {'navigateEpoch': nav_t0, 'wallSecondsToReady': round(time.time()-nav_t0, 2),
                          'ready': bool(ready), 'sample': ready or last, 'milestones': milestones}
        if ready:
            rec['interaction'] = s.eval(INTERACT, True)
        # 抬到原生 4K（dsf=1）并钉住最高档：boost on、degrade 0、dip off
        # （顺序很关键：先设视口，**再 resize**，最后才钉档位——反过来 resize 会重算 dpr 把档位打回去）
        rec['pinned'] = pin_native4k(s)
        # 稳态（分段采样后合并，WS 读超时 40s）
        seg = min(25.0, args.steady_seconds)
        rec['steady'] = collect(s, args.steady_seconds, seg)
        # 转场：每种 REPS 次
        rec['transitions'] = {}
        for kind in ('enter', 'exit', 'view', 'plot', 'quality', 'return'):
            js = TRANSITION.replace('KIND_JS', KINDS[kind]).replace('KIND', repr(kind)).replace('REPS', str(args.reps))
            r = s.eval(js, True)
            if isinstance(r, dict) and r.get('samples'):
                sm = r['samples']
                rec['transitions'][kind] = {
                    'reps': r['reps'], 'errors': [x['err'] for x in sm if x.get('err')],
                    'syncMs': summarise([x['sync'] for x in sm]), 'nextFrameMs': summarise([x['f1'] for x in sm]),
                    'settle2Ms': summarise([x['f2'] for x in sm]),
                    'freezesOver100': sum(1 for x in sm if x['f1'] > 100 or x['f2'] > 100),
                    'samples': sm}
            else:
                rec['transitions'][kind] = {'error': str(r)}
        # resize 转场（必须由 CDP 驱动，Python 侧计时）
        resize = []
        for i in range(args.reps):
            w, h = (1440, 900) if i % 2 == 0 else (3840, 2160)
            t0 = time.time()
            s.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=1, mobile=False)
            s.eval('CLApp.scene().setBoost(true);CLApp.scene().setDegrade(0);CLApp.scene().resize()', False)
            r = s.eval("(function(){var q=CLApp.scene().quality();return [q.drawW,q.drawH,CLApp.scene().renderer.getContext().getError()];})()")
            resize.append({'to': [w, h], 'ms': round((time.time()-t0)*1000, 2), 'after': r})
        rec['transitions']['resize'] = {'reps': len(resize), 'wallMs': summarise([x['ms'] for x in resize]),
                                        'wrongSize': [x for x in resize if x['after'][0] != x['to'][0]],
                                        'glErrors': [x for x in resize if x['after'][2] != 0], 'samples': resize}
        # resize 阶段会把视口留在最后一次的尺寸上（实测踩到：长时窗口曾在 1440x900 上跑），
        # 因此这里显式恢复到原生 4K 并记录回读结果，供长时阶段与复核者核对。
        rec['afterTransitions'] = pin_native4k(s, settle=3.0)
        # 长时窗口：每个窗口单独采样（不合并），用来出「每 N 分钟」曲线
        if args.long_windows:
            rec['long'] = {'windowSeconds': args.long_seconds, 'windows': [], 'deadlineEpoch': args.deadline_epoch}
            for i in range(args.long_windows):
                if args.deadline_epoch and time.time() + args.long_seconds + 20 > args.deadline_epoch:
                    rec['long']['stoppedEarly'] = {'plannedWindows': args.long_windows, 'doneWindows': i,
                                                   'why': '硬墙钟上限（任务超时 2700s）前放不下下一个 %ss 窗口' % args.long_seconds}
                    break
                # 每个窗口都重新钉档 + 回读校验：任何一次视口/档位漂移都必须被发现，
                # 而不是把降档或小视口的读数混进「原生 4K 长时」结论里。
                pin = pin_native4k(s, settle=4.0)
                q = (pin or {}).get('quality') or {}
                w = collect(s, args.long_seconds, 25.0)
                w['windowIndex'] = i
                w['pinnedTier'] = pin
                w['tierOk'] = (q.get('drawW') == 3840 and q.get('drawH') == 2160 and q.get('degrade') == 0
                               and q.get('boost') == 1)
                if not w['tierOk']:
                    w['tierMismatch'] = {'drawW': q.get('drawW'), 'drawH': q.get('drawH'),
                                         'degrade': q.get('degrade'), 'boost': q.get('boost'),
                                         'why': '档位回读不符原生4K最高档：本窗读数不得用于原生4K结论'}
                rec['long']['windows'].append(w)
                (out / ('long-%s-w%d.json' % (args.book, i))).write_text(json.dumps(w, ensure_ascii=False, indent=2) + '\n', 'utf-8')
                print(json.dumps({'book': args.book, 'longWindow': i, 'fps': w.get('fps'), 'p95': w.get('p95'),
                                  'longTaskMax': w.get('longTaskMax'), 'textures': (w.get('renderer') or {}).get('textures')},
                                 ensure_ascii=False), flush=True)
        rec['health'] = s.eval(headless.POST_HEALTH_JS.replace('window.__cl && window.__cl.scene', 'window.CLApp && window.CLApp.scene()'), True)
    finally:
        try:
            s.close()
        except Exception:
            pass
    rec['finishedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    rec['wallSeconds'] = round(time.time() - t_start, 1)
    path = out / ('book-%s.json' % args.book)
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps({'saved': str(path), 'steadyFps': (rec.get('steady') or {}).get('fps'),
                      'startup': {k: (rec.get('startup', {}).get('sample') or {}).get(k) for k in ('firstRaf', 'sceneFrame', 'loaderOff')},
                      'wallSeconds': rec['wallSeconds']}, ensure_ascii=False), flush=True)


def collect(session, total_seconds, segment_seconds):
    """把长窗口拆成 <=25s 的段（WS 读超时 40s），用**合并后的原始帧间隔**重算分位数。"""
    total_ms, seg_ms = int(total_seconds*1000), int(max(1.0, min(segment_seconds, 25.0))*1000)
    got, merged, allv = 0, None, []
    while got < total_ms:
        want = min(seg_ms, total_ms-got)
        part = session.eval(SAMPLE.replace('DURATION', str(want)), True)
        if not isinstance(part, dict) or part.get('__evalError'):
            return {'error': str(part), 'partial': merged}
        if merged is None:
            merged = {k: v for k, v in part.items() if k != '_deltas'}
            merged['segments'] = []
        merged['segments'].append({'fps': part.get('fps'), 'p95': part.get('p95'), 'frames': part.get('frames'),
                                   'longTaskMax': part.get('longTaskMax'), 'textures': (part.get('renderer') or {}).get('textures'),
                                   'geometries': (part.get('renderer') or {}).get('geometries')})
        allv.extend(part.get('_deltas') or [])
        merged['longTasks'] = (merged.get('longTasks') or []) + (part.get('longTasks') or [])
        got += want
    s = sorted(allv)
    if s:
        def q(p): return round(s[min(len(s)-1, int(len(s)*p))], 2)
        merged['frames'] = len(s); merged['p50'] = q(.5); merged['p95'] = q(.95); merged['p99'] = q(.99); merged['max'] = round(s[-1], 2)
        merged['over334'] = sum(1 for x in s if x > 33.4); merged['over50'] = sum(1 for x in s if x > 50); merged['over100'] = sum(1 for x in s if x > 100)
        merged['elapsedMs'] = round(sum(s), 1); merged['fps'] = round(len(s)/sum(s)*1000, 3)
        merged['longTaskMax'] = max([x[1] for x in merged['longTasks']] or [0])
        merged['longTaskTotal'] = round(sum(x[1] for x in merged['longTasks']), 1)
    return merged


if __name__ == '__main__':
    main()
