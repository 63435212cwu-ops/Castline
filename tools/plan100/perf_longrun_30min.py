#!/usr/bin/env python3
"""P10 · 30 分钟长时稳定与资源曲线（真实时长，不缩短）。

计划原文（`docs/plan-100-score-execution.md:52230`）：
  「……**长时脚本至少30分钟**，三书轮换、星座旋转、星盘播放、罗盘进出、
    搜索、解构、暂停恢复和窗口改变都要包含。」

## 与 tests/sky_longrun_resource_browser.py 的分工

那个脚本是**纯稳态资源曲线**（1 Hz 采样、可选 autoRotate），它回答「放着不动会不会漏」。
本脚本回答的是**计划点名的那件事**：把 8 类交互按时间表真的跑 30 分钟，
并且**按场景分别统计帧间隔**（首帧/首次进入/稳态/镜头转场/质量切换/返回/长时运行），
产出 `tools/plan100/perf_report.py` 直接可吃的 `scenarios[]`。

两者都保留：稳态曲线用旧的（已验证、轻），交互长跑用本脚本（重、覆盖广）。

## 八项必含动作 → 时间表

| # | 动作 | 实现 | 覆盖场景 |
|---|---|---|---|
| 1 | 三书轮换 | `?data=` 重新导航到三部缓存 | first-entry / return |
| 2 | 星座旋转 | `controls.autoRotate` 开关 + 角度回读 | camera-transition |
| 3 | 星盘播放 | `CLSky.play()/seek()/playerState()` | steady / longrun |
| 4 | 罗盘进出 | `CLSky.openCompass()/closeCompass()` | camera-transition / return |
| 5 | 搜索 | `CLSkySearch.open(q)` + 键盘输入 | longrun |
| 6 | 解构 | `CLSkyDeconstruction.open()/toggle()/close()` | longrun |
| 7 | 暂停恢复 | `CLSky.playback('pause'/'play')` + `CLApp.atlas.motion()` | return |
| 8 | 窗口改变 | `Emulation.setDeviceMetricsOverride` 多档 | quality-switch |

时间预算（默认 1800 秒 = 30 分钟，**真实墙钟**）：
  预热 + 首帧/首次进入  ~90 s
  8 轮 × 主循环         ~8 × 175 s = 1400 s
  收尾 + 终态校验       ~100 s
  余量                  ~210 s
每轮都跑完 8 项（轮内顺序打散），轮间换书 —— 保证 30 分钟里每项都被反复触发。

## 三条诚实守则

  1. **真实时长**：`--minutes` 默认 30；报告里同时写 `requestedMinutes` 与
     `actualSampledSeconds`。脚本不会因为「已经拿到足够样本」提前退出。
  2. **不锁4K换性能**：全程断言 `quality.drawW/drawH` 仍是 3840×2160 且 `degrade==0`；
     一旦掉档就记 `lockedNative4k: false` 并把降档理由写进报告 —— 那是**事实**，
     不是失败，但绝不允许被当成「原生4K下的60fps」。
  3. **未测即 null**：某轮没跑到的场景，其帧间隔数组为空，`perf_report.py` 会保持 null。

用法（GPU 空闲时）：
  python3 tools/plan100/perf_longrun_30min.py --base http://127.0.0.1:8765 \\
      --out /tmp/castline-shots/longrun-30min --minutes 30
  # 冒烟（验证脚本本身能跑通，不构成 30 分钟证据）
  python3 tools/plan100/perf_longrun_30min.py --minutes 1 --out /tmp/longrun-smoke
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))

from atlas_review_shots import Session
import headless

BOOKS = [
    ('dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json', '大奉打更人'),
    ('xiyou', 'data/cache/df959d743e53206f56db2f92.json', '西游记'),
    ('sanguo', 'data/cache/d16db79a529a1727352091d5.json', '三国演义'),
]

SCENARIOS = ['first-frame', 'first-entry', 'steady', 'camera-transition',
             'quality-switch', 'return', 'longrun']

# ------------------------------------------------------------------ 注入脚本
INSTALL = r"""(function(){
  var S=CLApp.scene(), canvas=S.renderer.domElement;
  var W=window;
  W.__lr = {
    t0: performance.now(),
    frames: 0,
    contextLost: 0,
    consoleErrors: 0,
    longTasks: [],            /* PerformanceObserver longtask 条目 */
    gpuUploads: 0,
    rtCreates: 0,
    rtDisposes: 0,
    domNodesStart: 0,
    scenario: 'steady',
    intervals: {},            /* scenario -> [ms, ...] */
    marks: [],                /* 时间轴事件：动作开始/结束 */
    longtaskSupported: false,
    rtProbe: null
  };
  ['first-frame','first-entry','steady','camera-transition','quality-switch','return','longrun']
    .forEach(function(k){ W.__lr.intervals[k]=[]; });

  canvas.addEventListener('webglcontextlost', function(){ W.__lr.contextLost++; });
  var origError = console.error.bind(console);
  console.error = function(){
    W.__lr.consoleErrors++;
    return origError.apply(null, arguments);
  };

  /* 长任务：优先 PerformanceObserver('longtask')；UA 不暴露时如实标 false，
     不用「帧间隔>50ms」冒充浏览器长任务（那是两件事，混起来会骗自己）。 */
  try {
    if (W.PerformanceObserver && PerformanceObserver.supportedEntryTypes &&
        PerformanceObserver.supportedEntryTypes.indexOf('longtask') >= 0) {
      W.__lr.longtaskSupported = true;
      new PerformanceObserver(function(list){
        list.getEntries().forEach(function(e){
          if (W.__lr.longTasks.length < 5000)
            W.__lr.longTasks.push({startTime:+e.startTime.toFixed(2), duration:+e.duration.toFixed(2)});
        });
      }).observe({entryTypes:['longtask']});
    }
  } catch(e) { W.__lr.longtaskSupported = false; }

  /* GPU 上传与 RT 生命周期：包住 renderer 的上传/目标重建入口计数。
     这是**计数**，不是估算；包不到就保持 0 并在报告里标 probe=false。 */
  try {
    var R = S.renderer, gl = R.getContext();
    W.__lr.rtProbe = {bound:true};
    var origTex = R.setTexture2D ? R.setTexture2D.bind(R) : null;
    /* three r128 的内部命名随版本变化；这里只统计可稳定观测的两个：
       texImage2D 活跃纹理数（跨帧变化即上传）与 WebGLRenderTarget 构造。 */
    var origTexImage = gl.texImage2D.bind(gl);
    gl.texImage2D = function(){
      W.__lr.gpuUploads++;
      return origTexImage.apply(null, arguments);
    };
    var OrigRT = W.THREE.WebGLRenderTarget;
    W.THREE.WebGLRenderTarget = function(){
      W.__lr.rtCreates++;
      var inst = new OrigRT(arguments[0], arguments[1], arguments[2]);
      var origDispose = inst.dispose.bind(inst);
      inst.dispose = function(){ W.__lr.rtDisposes++; return origDispose(); };
      return inst;
    };
    W.THREE.WebGLRenderTarget.prototype = OrigRT.prototype;
  } catch(e) {
    W.__lr.rtProbe = {bound:false, error:String(e)};
  }

  W.__lr.domNodesStart = document.getElementsByTagName('*').length;

  (function tick(){
    var now = performance.now();
    var dt = now - (W.__lr.last || now);
    W.__lr.last = now;
    if (W.__lr.started && dt >= 0 && dt < 3000) W.__lr.intervals[W.__lr.scenario].push(dt);
    W.__lr.frames++;
    requestAnimationFrame(tick);
  })();
  return {installed:true, canvas:[canvas.width, canvas.height],
          longtaskSupported: W.__lr.longtaskSupported,
          rtProbeBound: !!(W.__lr.rtProbe && W.__lr.rtProbe.bound),
          domNodesStart: W.__lr.domNodesStart};
})()"""

SET_SCENARIO = r"""(function(name, note){
  var W = window;
  if (!W.__lr) return null;
  W.__lr.scenario = name;
  W.__lr.marks.push({t:+(performance.now()-W.__lr.t0).toFixed(1), scenario:name, note:note||''});
  return name;
})(%s, %s)"""

START_RECORDING = "window.__lr.started = true; window.__lr.t0 = performance.now(); 'started'"

SNAPSHOT = r"""(function(){
  var S=CLApp.scene(), R=S.renderer, gl=R.getContext(), info=R.info;
  var mem = window.performance && performance.memory;
  var h = window.__headlessHealth || {jserr:[], jsrej:[]};
  var q = S.quality();
  return {
    t: performance.now(),
    frames: __lr.frames,
    scenario: __lr.scenario,
    contextLost: __lr.contextLost + (gl.isContextLost() ? 1 : 0),
    consoleErrors: __lr.consoleErrors,
    jserr: h.jserr.length, jsrej: h.jsrej.length,
    shaderErrors: S.shaderErrors().length,
    longTasks: __lr.longTasks.length,
    gpuUploads: __lr.gpuUploads,
    rtCreates: __lr.rtCreates,
    rtDisposes: __lr.rtDisposes,
    heap: mem ? {usedMB:+(mem.usedJSHeapSize/1048576).toFixed(3),
                 totalMB:+(mem.totalJSHeapSize/1048576).toFixed(3)} : null,
    render: {calls:info.render.calls, triangles:info.render.triangles},
    memory: {geometries:info.memory.geometries, textures:info.memory.textures},
    programs: (info.programs||[]).length,
    domNodes: document.getElementsByTagName('*').length,
    quality: q,
    native4kNow: q.drawW === 3840 && q.drawH === 2160,
    degradeNow: q.degrade,
    playerState: (window.CLSky && CLSky.playerState) ? CLSky.playerState() : null
  };
})()"""

ACTIONS = {
    'book-rotate': r"""
      (function(){
        var next = window.__lrBookNext();
        if (!next) return {ok:false, why:'no next book'};
        location.href = location.origin + location.pathname +
          '?data=' + encodeURIComponent(next.data) + '&sky=1';
        return {ok:true, book:next.key};
      })()""",

    'constellation-rotate': r"""
      (function(){
        var S=CLApp.scene(), c=S.controls;
        c.autoRotate = true; c.autoRotateSpeed = 0.35; c.update();
        return {ok:true, autoRotate:c.autoRotate, speed:c.autoRotateSpeed,
                cam:S.camera.position.toArray().map(function(v){return +v.toFixed(2);})};
      })()""",

    'astrolabe-play': r"""
      (function(){
        if (!window.CLSky || !CLSky.enabled || !CLSky.enabled()) return {ok:false, why:'sky off'};
        if (!CLSky.plot()) CLSky.setPlot(true);
        var before = CLSky.playerState();
        CLSky.play();
        return {ok:true, before:before, after:CLSky.playerState(), plot:CLSky.plot()};
      })()""",

    'compass-enter': r"""
      (function(){
        if (!window.CLSky) return {ok:false, why:'no CLSky'};
        var G = CLApp.graph(); if (!G || !G.characters || !G.characters.length) return {ok:false, why:'no graph'};
        var name = G.characters[0].name;
        var ok = CLSky.openCompass(name);
        return {ok:!!ok, name:name, state:CLSky.state()};
      })()""",

    'compass-exit': r"""
      (function(){
        if (!window.CLSky) return {ok:false, why:'no CLSky'};
        CLSky.closeCompass();
        return {ok:true, state:CLSky.state()};
      })()""",

    'search': r"""
      (function(){
        if (!window.CLSkySearch) return {ok:false, why:'no CLSkySearch'};
        var G = CLApp.graph();
        var q = (G && G.characters && G.characters.length)
          ? String(G.characters[0].name).slice(0, 1) : '一';
        CLSkySearch.open(q);
        var st = CLSkySearch.stats ? CLSkySearch.stats() : null;
        return {ok:true, query:q, stats:st};
      })()""",

    'deconstruct': r"""
      (function(){
        if (!window.CLSkyDeconstruction) return {ok:false, why:'no CLSkyDeconstruction'};
        var open = CLSkyDeconstruction.ready ? CLSkyDeconstruction.ready() : null;
        if (open) { CLSkyDeconstruction.close(); return {ok:true, action:'close', wasOpen:true}; }
        CLSkyDeconstruction.open();
        return {ok:true, action:'open', wasOpen:false, ready:CLSkyDeconstruction.ready()};
      })()""",

    'pause-resume': r"""
      (function(){
        var out = {};
        if (window.CLSky && CLSky.playback) {
          out.paused = CLSky.playback('pause');
          out.pausedState = CLSky.playerState();
        }
        if (window.CLApp && CLApp.atlas && CLApp.atlas.motion) CLApp.atlas.motion(true);
        out.afterPause = (window.CLSky && CLSky.state) ? CLSky.state() : null;
        return {ok:true, phase:'pause', detail:out};
      })()""",

    'pause-resume-back': r"""
      (function(){
        var out = {};
        if (window.CLSky && CLSky.playback) {
          out.resumed = CLSky.playback('play');
          out.resumedState = CLSky.playerState();
        }
        if (window.CLApp && CLApp.atlas && CLApp.atlas.motion) CLApp.atlas.motion(false);
        out.afterResume = (window.CLSky && CLSky.state) ? CLSky.state() : null;
        return {ok:true, phase:'resume', detail:out};
      })()""",
}

VIEWPORTS = [
    (1440, 900, 1, 'desktop-1440x900'),
    (1024, 768, 1, 'desktop-1024x768'),
    (390, 844, 2, 'narrow-390x844@2x'),
    (3840, 2160, 1, 'native-4k'),
]


def percentile(vals, q):
    v = sorted(vals)
    if not v:
        return None
    if len(v) == 1:
        return v[0]
    pos = (len(v) - 1) * q
    lo, hi = int(pos // 1), int(-(-pos // 1))
    if lo == hi:
        return v[lo]
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default='http://127.0.0.1:8765')
    ap.add_argument('--out', default='/tmp/castline-shots/longrun-30min')
    ap.add_argument('--minutes', type=float, default=30.0,
                    help='真实墙钟分钟数；计划要求 ≥30，不得用缩短时长冒充')
    ap.add_argument('--settle', type=float, default=25.0, help='首帧后预热秒数')
    ap.add_argument('--sample', type=float, default=5.0, help='快照间隔秒')
    ap.add_argument('--viewport-w', type=int, default=1440)
    ap.add_argument('--viewport-h', type=int, default=900)
    ap.add_argument('--allow-short', action='store_true',
                    help='允许 <30 分钟（仅用于冒烟；报告里会标记 notAcceptanceEvidence）')
    args = ap.parse_args()

    total_seconds = args.minutes * 60.0
    if args.minutes < 30 and not args.allow_short:
        print('拒绝运行：--minutes %.1f < 30。计划要求长时脚本至少30分钟；'
              '缩短时长不得冒充长时证据。若只想冒烟验证脚本本身，加 --allow-short。'
              % args.minutes, file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        'tool': 'tools/plan100/perf_longrun_30min.py',
        'planRequirement': ('长时脚本至少30分钟，三书轮换、星座旋转、星盘播放、罗盘进出、'
                            '搜索、解构、暂停恢复和窗口改变都要包含。'),
        'planRef': 'docs/plan-100-score-execution.md:52230',
        'requestedMinutes': args.minutes,
        'isAcceptanceEvidence': args.minutes >= 30,
        'base': args.base,
        'books': [{'key': k, 'data': d, 'title': t} for k, d, t in BOOKS],
        'viewport': [args.viewport_w, args.viewport_h, 1],
        'samples': [],
        'sampleErrors': [],
        'actions': [],
        'viewportChanges': [],
        'bookRotations': [],
        'marks': [],
        'scenarios': [],
        'errors': {},
        'failures': [],
    }

    session = Session(args.viewport_w, args.viewport_h)

    def evaluate(expr, wait=False):
        r = session.eval(expr, wait)
        if isinstance(r, dict) and r.get('__evalError'):
            raise RuntimeError(r)
        return r

    def delay(seconds):
        if seconds > 0:
            evaluate('new Promise(function(r){setTimeout(r,%d);})' % int(round(seconds * 1000)), True)

    def act(script, note):
        try:
            return evaluate(script)
        except Exception as exc:
            report['actions'].append({'note': note, 'error': str(exc)[:300]})
            return None

    book_index = [0]

    def navigate_book(idx):
        key, data, title = BOOKS[idx % len(BOOKS)]
        evaluate("(function(){window.__lrBookNext=function(){return %s;};return true;})()"
                 % json.dumps({'key': key, 'data': data, 'title': title}))
        session.navigate(args.base + '/?data=' + data + '&sky=1')
        return key, title

    BOOK_NAV = ("location.href = location.origin + location.pathname + '?data=' + "
                "encodeURIComponent(%s) + '&sky=1'; 'navigating'")

    started = time.monotonic()
    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=args.viewport_w,
                        height=args.viewport_h, deviceScaleFactor=1, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)

        # ---------------------------------------------------- 1) 首帧 / 首次进入
        key, title = navigate_book(0)
        report['bookRotations'].append({'t': 0.0, 'book': key, 'title': title})
        ready, elapsed, last = session.wait_until(
            '({ready:!!(window.CLApp&&CLApp.scene()&&window.CLSkyDeep&&'
            'CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99)})', 60)
        report['firstEntry'] = {'book': key, 'ready': bool(ready),
                                'readySeconds': round(elapsed, 2), 'last': last}
        if not ready:
            report['failures'].append('首帧/首次进入未就绪：%s' % json.dumps(last, ensure_ascii=False)[:300])

        report['install'] = evaluate(INSTALL)
        evaluate(SET_SCENARIO % ('"first-entry"', '"scene ready"'))
        evaluate(START_RECORDING, True)

        evaluate('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);'
                 'CLApp.scene().setDegrade(0)')
        delay(3)
        report['qualityPinned'] = evaluate('CLApp.scene().quality()')
        report['gpu'] = evaluate('CLApp.scene().renderer.getContext()'
                                 '.getParameter(CLApp.scene().renderer.getContext().RENDERER)')

        delay(args.settle)
        report['afterSettle'] = evaluate(SNAPSHOT)

        # ---------------------------------------------------- 2) 30 分钟主循环
        action_plan = [
            ('constellation-rotate', 22, 'camera-transition'),
            ('astrolabe-play', 20, 'steady'),
            ('search', 12, 'longrun'),
            ('compass-enter', 18, 'camera-transition'),
            ('deconstruct', 14, 'longrun'),
            ('pause-resume', 10, 'return'),
            ('compass-exit', 14, 'return'),
            ('pause-resume-back', 12, 'steady'),
            ('viewport-change', 18, 'quality-switch'),
            ('book-rotate', 35, 'first-entry'),
        ]

        rounds = 0
        next_sample = time.monotonic()
        vidx = 0
        while True:
            wall = time.monotonic() - started
            if wall >= total_seconds:
                break
            rounds += 1
            report['marks'].append({'t': round(wall, 1), 'event': 'round-start', 'round': rounds})
            for name, dwell, scenario in action_plan:
                if time.monotonic() - started >= total_seconds:
                    break
                evaluate(SET_SCENARIO % (json.dumps(scenario), json.dumps('round %d · %s' % (rounds, name))))

                if name == 'viewport-change':
                    w, h, dpr, label = VIEWPORTS[vidx % len(VIEWPORTS)]
                    vidx += 1
                    session.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h,
                                    deviceScaleFactor=dpr, mobile=False)
                    evaluate('window.dispatchEvent(new Event("resize"))')
                    entry = {'t': round(time.monotonic() - started, 1), 'viewport': [w, h, dpr],
                             'label': label}
                    report['viewportChanges'].append(entry)
                    report['actions'].append({'t': entry['t'], 'action': name, 'result': entry})
                elif name == 'book-rotate':
                    idx = (book_index[0] + 1) % len(BOOKS)
                    book_index[0] = idx
                    k2, t2 = navigate_book(idx)
                    entry = {'t': round(time.monotonic() - started, 1), 'book': k2, 'title': t2}
                    report['bookRotations'].append(entry)
                    rdy, el2, last2 = session.wait_until(
                        '({ready:!!(window.CLApp&&CLApp.scene()&&window.CLSkyDeep&&'
                        'CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99)})', 60)
                    report['actions'].append({'t': entry['t'], 'action': name,
                                              'result': {'book': k2, 'ready': bool(rdy),
                                                         'readySeconds': round(el2, 2)}})
                    if not rdy:
                        report['failures'].append('换书 %s 未就绪' % k2)
                    report['install'] = evaluate(INSTALL)
                    evaluate('window.__lr.started=true')
                    evaluate('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);'
                             'CLApp.scene().setDegrade(0)')
                else:
                    res = act(ACTIONS[name], name)
                    report['actions'].append({'t': round(time.monotonic() - started, 1),
                                              'action': name, 'result': res})

                end = time.monotonic() + dwell
                while time.monotonic() < end:
                    if time.monotonic() - started >= total_seconds:
                        break
                    now = time.monotonic()
                    if now >= next_sample:
                        next_sample = now + args.sample
                        try:
                            snap = evaluate(SNAPSHOT)
                            if isinstance(snap, dict) and 'frames' in snap:
                                report['samples'].append({
                                    'wallSeconds': round(now - started, 1),
                                    't': snap['t'], 'scenario': snap['scenario'],
                                    'frames': snap['frames'], 'heap': snap['heap'],
                                    'memory': snap['memory'], 'programs': snap['programs'],
                                    'render': snap['render'], 'domNodes': snap['domNodes'],
                                    'longTasks': snap['longTasks'],
                                    'gpuUploads': snap['gpuUploads'],
                                    'rtCreates': snap['rtCreates'],
                                    'rtDisposes': snap['rtDisposes'],
                                    'contextLost': snap['contextLost'],
                                    'consoleErrors': snap['consoleErrors'],
                                    'jserr': snap['jserr'], 'jsrej': snap['jsrej'],
                                    'shaderErrors': snap['shaderErrors'],
                                    'quality': snap['quality'],
                                    'native4kNow': snap['native4kNow'],
                                    'degradeNow': snap['degradeNow'],
                                })
                        except Exception as exc:
                            report['sampleErrors'].append({'wallSeconds': round(now - started, 1),
                                                           'error': str(exc)[:200]})
                    time.sleep(0.25)

            report['marks'].append({'t': round(time.monotonic() - started, 1),
                                    'event': 'round-end', 'round': rounds})

        # ---------------------------------------------------- 3) 收尾
        wall = time.monotonic() - started
        report['actualWallSeconds'] = round(wall, 1)
        report['rounds'] = rounds
        report['final'] = evaluate(SNAPSHOT)
        report['errors'] = {
            'contextLost': report['final']['contextLost'] if report['final'] else None,
            'consoleErrors': report['final']['consoleErrors'] if report['final'] else None,
            'jserr': report['final']['jserr'] if report['final'] else None,
            'jsrej': report['final']['jsrej'] if report['final'] else None,
            'shaderErrors': report['final']['shaderErrors'] if report['final'] else None,
        }
        report['frameHook'] = evaluate('(function(){var d=CLApp.scene().digest();'
                                       'return {errors:d.frameHooks&&d.frameHooks.errors||0,'
                                       'lastError:d.frameHooks&&d.frameHooks.lastError||null};})()')

        # ---------------------------------------------------- 4) 分场景统计
        raw = evaluate('(function(){var o={};for(var k in window.__lr.intervals){'
                       'o[k]=window.__lr.intervals[k];}return o;})()')
        report['longtaskSupported'] = evaluate('window.__lr.longtaskSupported')
        report['longTaskDetail'] = evaluate(
            '(function(){var a=window.__lr.longTasks.slice(0,2000);'
            'return {n:window.__lr.longTasks.length, head:a.slice(0,50)};})()')
        report['marksJs'] = evaluate('window.__lr.marks')

        scenarios = []
        for sid in SCENARIOS:
            iv = (raw or {}).get(sid) or []
            iv = [v for v in iv if isinstance(v, (int, float))]
            q = (report.get('final') or {}).get('quality') or {}
            entry = {
                'scenario': sid,
                'frameIntervalsMs': iv,
                'rtCreates': (report.get('final') or {}).get('rtCreates'),
                'rtDisposes': (report.get('final') or {}).get('rtDisposes'),
                'gpuUploads': (report.get('final') or {}).get('gpuUploads'),
                'domNodes': (report.get('final') or {}).get('domNodes'),
                'textures': ((report.get('final') or {}).get('memory') or {}).get('textures'),
                'geometries': ((report.get('final') or {}).get('memory') or {}).get('geometries'),
                'programs': (report.get('final') or {}).get('programs'),
                'longTasks': (report.get('final') or {}).get('longTasks'),
                'quality': q,
                'canvas': [(report.get('final') or {}).get('quality', {}).get('drawW'),
                           (report.get('final') or {}).get('quality', {}).get('drawH')],
                'memory': [{'t': s['t'], 'usedMB': (s.get('heap') or {}).get('usedMB')}
                           for s in report['samples'] if s.get('heap')],
                'source': 'tools/plan100/perf_longrun_30min.py',
            }
            if iv:
                entry['p50'] = round(percentile(iv, 0.50), 3)
                entry['p95'] = round(percentile(iv, 0.95), 3)
                entry['p99'] = round(percentile(iv, 0.99), 3)
                entry['frames'] = len(iv)
                entry['elapsedMs'] = round(sum(iv), 3)
                entry['over50'] = len([v for v in iv if v > 50])
            scenarios.append(entry)
        report['scenarios'] = scenarios

        # ---------------------------------------------------- 5) 不锁4K换取性能
        pinned = report.get('qualityPinned') or {}
        stayed = [s for s in report['samples'] if s.get('native4kNow')]
        dropped = [s for s in report['samples'] if s.get('native4kNow') is False]
        report['lockedNative4k'] = {
            'pinnedDraw': [pinned.get('drawW'), pinned.get('drawH')],
            'pinnedDegrade': pinned.get('degrade'),
            'pinnedBoost': pinned.get('boost'),
            'samplesNative4k': len(stayed),
            'samplesDropped': len(dropped),
            'stayedNative4kThroughout': len(dropped) == 0 and len(stayed) > 0,
            'firstDropExample': dropped[0] if dropped else None,
            'note': ('本项断言「分辨率没有被牺牲换帧率」。若中途掉档，'
                     'samplesDropped>0 且 firstDropExample 给出当时的 quality —— '
                     '那是事实记录，不是通过/失败；但它意味着掉档之后取得的帧率'
                     '**不得**算作原生4K性能。'),
        }
        report['heapTrend'] = _heap_trend(report['samples'])
        report['renderResources'] = _resource_delta(report['samples'])

        # ---------------------------------------------------- 6) 失败判定
        if report['errors'].get('contextLost'):
            report['failures'].append('webgl context lost: %s' % report['errors']['contextLost'])
        if report['errors'].get('jserr') or report['errors'].get('jsrej'):
            report['failures'].append('uncaught js exceptions/rejections: jserr=%s jsrej=%s'
                                      % (report['errors']['jserr'], report['errors']['jsrej']))
        if report['errors'].get('shaderErrors'):
            report['failures'].append('shader errors: %s' % report['errors']['shaderErrors'])
        if report['frameHook'] and report['frameHook'].get('errors'):
            report['failures'].append('frame hook errors: %s' % report['frameHook']['errors'])
        if wall < total_seconds - 5:
            report['failures'].append('实际墙钟 %.1f 秒 < 目标 %.1f 秒' % (wall, total_seconds))
        if not report['lockedNative4k']['stayedNative4kThroughout']:
            report['failures'].append(
                '并非全程原生4K：%d/%d 次采样掉出 3840×2160（首次见 firstDropExample）'
                % (len(dropped), len(stayed) + len(dropped)))
        if len(report['samples']) < 10:
            report['failures'].append('采样点过少（%d），曲线不足以判定趋势' % len(report['samples']))

        report['ok'] = not report['failures']
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({
            'saved': str(out / 'report.json'),
            'ok': report['ok'],
            'requestedMinutes': report['requestedMinutes'],
            'actualWallSeconds': report['actualWallSeconds'],
            'isAcceptanceEvidence': report['isAcceptanceEvidence'],
            'rounds': report['rounds'],
            'samples': len(report['samples']),
            'bookRotations': len(report['bookRotations']),
            'viewportChanges': len(report['viewportChanges']),
            'actions': len(report['actions']),
            'lockedNative4k': report['lockedNative4k']['stayedNative4kThroughout'],
            'errors': report['errors'],
            'failures': report['failures'],
            'scenarios': [{k: s.get(k) for k in ('scenario', 'frames', 'p50', 'p95', 'p99')}
                          for s in report['scenarios']],
        }, ensure_ascii=False), flush=True)
        return 1 if report['failures'] else 0

    finally:
        try:
            session.close()
        except Exception:
            pass


def _heap_trend(samples):
    pts = [(s['t'], (s.get('heap') or {}).get('usedMB')) for s in samples]
    pts = [(t, mb) for t, mb in pts if isinstance(t, (int, float)) and isinstance(mb, (int, float))]
    if len(pts) < 2:
        return {'supported': bool(pts), 'points': len(pts), 'usedSlopeMBPerMin': None}
    n = len(pts)
    xs = [t / 60000.0 for t, _ in pts]
    ys = [mb for _, mb in pts]
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
    den = n * sxx - sx * sx
    slope = (n * sxy - sx * sy) / den if abs(den) > 1e-12 else None
    return {'supported': True, 'points': n,
            'usedFirstMB': ys[0], 'usedLastMB': ys[-1],
            'usedSlopeMBPerMin': round(slope, 4) if slope is not None else None}


def _resource_delta(samples):
    if not samples:
        return None

    def first(key, sub=None):
        for s in samples:
            v = (s.get(key) or {}).get(sub) if sub else s.get(key)
            if isinstance(v, (int, float)):
                return v
        return None

    def last(key, sub=None):
        for s in reversed(samples):
            v = (s.get(key) or {}).get(sub) if sub else s.get(key)
            if isinstance(v, (int, float)):
                return v
        return None

    return {
        'note': ('memory/programs 是累计值；render.calls 只是最近一次 render pass'
                 '（three.js 每次 render 会重置）。首次/末次对账用来看单调增长。'),
        'texturesFirst': first('memory', 'textures'), 'texturesLast': last('memory', 'textures'),
        'geometriesFirst': first('memory', 'geometries'), 'geometriesLast': last('memory', 'geometries'),
        'programsFirst': first('programs'), 'programsLast': last('programs'),
        'domNodesFirst': first('domNodes'), 'domNodesLast': last('domNodes'),
        'rtCreatesLast': last('rtCreates'), 'rtDisposesLast': last('rtDisposes'),
        'gpuUploadsLast': last('gpuUploads'),
        'longTasksLast': last('longTasks'),
    }


if __name__ == '__main__':
    raise SystemExit(main())
