#!/usr/bin/env python3
"""Long-run native-4K resource curve for the production sky scene.

Real Chrome (Metal GPU via the shared atlas Session), native 3840x2160 device
metrics, full animation, no pump/fixedDt/quality reduction. The scene runs for
--minutes (default 6) while a 1 Hz CDP sampler records per-second FPS (injected
rAF counter, same wall-clock family as scene_native4k_perf_browser), JS heap
(performance.memory; null when the UA does not expose it), WebGL context-lost
events, JS exceptions / unhandled rejections / console.error counts, and the
production renderer.info counters (S.renderer is the real THREE.WebGLRenderer
owned by js/core/scene-core.js; info.render.calls is the most recent render
pass only — three.js resets it per render call — while memory/programs are
cumulative; the report labels them accordingly).

Reports exactly what was measured: report.json carries requestedMinutes and
actualSampledSeconds; nothing here is a 60 fps guarantee for any duration
longer than the actual run. Exit discipline: non-zero on WebGL context loss,
uncaught JS exceptions/rejections or shader errors; heap-growth slope above
--max-heap-growth-mb-min fails only when --gate-growth is passed (kept out of
scripts/accept.sh — long evidence runs are not part of the offline gate).

Mode guard (docs/perf-mode-investigation-2026-10-07.md): this host flips
autonomously between whole-machine fps plateaus (~1/1.5/2 × 16.7 ms real frame
cost). Each 1 Hz sample is classified into the --mode-bands plateaus
(default fast:55-62 / mid:37-45 / slow:26-34), plateau transitions are logged,
each per-minute aggregate carries its platform composition (mixed:true when a
minute spans more than one plateau), and the report tail gains a modeGuard
section: observed plateaus, transition count/times, per-plateau total seconds
and mean fps. All additions are new fields — existing report keys unchanged.
"""
import argparse
import json
import os
import time
from pathlib import Path

from atlas_review_shots import Session
import headless

ROOT = Path(__file__).resolve().parents[1]

INSTALL = r"""(function(){
  var S=CLApp.scene(), canvas=S.renderer.domElement;
  window.__longrun={t0:performance.now(),frames:0,contextLost:0,consoleErrors:0,consoleMessages:[]};
  canvas.addEventListener('webglcontextlost',function(){__longrun.contextLost++;});
  var origError=console.error.bind(console);
  console.error=function(){__longrun.consoleErrors++;
    if(__longrun.consoleMessages.length<20)__longrun.consoleMessages.push(Array.prototype.map.call(arguments,String).join(' ').slice(0,300));
    return origError.apply(null,arguments);};
  (function tick(){__longrun.frames++;requestAnimationFrame(tick);})();
  return {installed:true,canvas:[canvas.width,canvas.height]};
})()"""

SNAPSHOT = r"""(function(){
  var S=CLApp.scene(), R=S.renderer, gl=R.getContext(), info=R.info, mem=window.performance&&performance.memory;
  var h=window.__headlessHealth||{jserr:[],jsrej:[]};
  return {t:performance.now(),frames:__longrun.frames,contextLost:__longrun.contextLost,
    contextLostLive:gl.isContextLost(),consoleErrors:__longrun.consoleErrors,
    jserr:h.jserr.length,jsrej:h.jsrej.length,shaderErrors:S.shaderErrors().length,
    heap:mem?{usedMB:+(mem.usedJSHeapSize/1048576).toFixed(3),totalMB:+(mem.totalJSHeapSize/1048576).toFixed(3)}:null,
    render:{calls:info.render.calls,triangles:info.render.triangles},
    memory:{geometries:info.memory.geometries,textures:info.memory.textures},
    programs:(info.programs||[]).length};
})()"""

TEARDOWN = r"""(function(){
  var h=window.__headlessHealth||{jserr:[],jsrej:[]}, S=CLApp.scene(), d=S.digest();
  return {jserr:h.jserr.slice(0,20),jsrej:h.jsrej.slice(0,20),shaderErrors:S.shaderErrors(),
    consoleMessages:__longrun.consoleMessages,
    frameHookErrors:d.frameHooks&&d.frameHooks.errors||0,frameHookLastError:d.frameHooks&&d.frameHooks.lastError||null};
})()"""


def parse_mode_bands(spec):
    """'fast:55:62,mid:37:45,slow:26:34' -> [(name, lo, hi), ...] (inclusive fps bounds)."""
    bands = []
    for part in spec.split(','):
        name, lo, hi = part.strip().split(':')
        bands.append((name.strip(), float(lo), float(hi)))
    return bands


def classify_fps(fps, bands):
    if fps is None:
        return None
    for name, lo, hi in bands:
        if lo <= fps <= hi:
            return name
    return 'unclassified'


def percentile(sorted_values, q):
    return sorted_values[min(len(sorted_values) - 1, max(0, int(len(sorted_values) * q)))]


def slope_mb_per_min(points):
    """Least-squares slope of heap MB over elapsed minutes; None without heap data."""
    pts = [(t / 60000.0, mb) for t, mb in points if mb is not None]
    n = len(pts)
    if n < 2:
        return None
    sx = sum(p[0] for p in pts); sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts); sxy = sum(p[0] * p[1] for p in pts)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return None
    return (n * sxy - sx * sy) / denom


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8123')
    ap.add_argument('--data', default='data/cache/d16db79a529a1727352091d5.json')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'longrun-resource'))
    ap.add_argument('--minutes', type=float, default=6)
    ap.add_argument('--settle', type=float, default=22)
    ap.add_argument('--motion', action='store_true')
    ap.add_argument('--max-heap-growth-mb-min', type=float, default=8)
    ap.add_argument('--gate-growth', action='store_true', help='Fail the run when the heap slope exceeds the threshold')
    ap.add_argument('--mode-bands', default='fast:55:62,mid:37:45,slow:26:34',
                    help='fps plateau bands for the mode guard: name:lo:hi comma-separated (inclusive)')
    args = ap.parse_args()
    bands = parse_mode_bands(args.mode_bands)
    band_names = [b[0] for b in bands]
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    session = Session(3840, 2160)
    report = {'data': args.data, 'viewport': [3840, 2160, 1], 'pump': False, 'motion': bool(args.motion),
              'requestedMinutes': args.minutes, 'maxHeapGrowthMbMin': args.max_heap_growth_mb_min,
              'gateGrowth': bool(args.gate_growth), 'modeBands': args.mode_bands, 'samples': [], 'sampleErrors': []}

    def evaluate(expression, wait=False):
        result = session.eval(expression, wait)
        if isinstance(result, dict) and result.get('__evalError'):
            raise RuntimeError(result)
        return result

    def delay(seconds):
        evaluate('new Promise(function(r){setTimeout(r,' + str(round(seconds * 1000)) + ');})', True)

    failures = []
    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=3840, height=2160, deviceScaleFactor=1, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base + '/?data=' + args.data + '&sky=1')
        ready, _, last = session.wait_until('({ready:!!(window.CLApp&&CLApp.scene()&&window.CLSkyDeep&&CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99)})', 45)
        if not ready:
            raise RuntimeError('scene not ready: ' + str(last))
        delay(args.settle)
        evaluate('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)')
        delay(4)
        report['ready'] = evaluate('({quality:CLApp.scene().quality(),perf:CLApp.scene().perf(),gpu:CLApp.scene().renderer.getContext().getParameter(CLApp.scene().renderer.getContext().RENDERER)})')
        assert report['ready']['quality']['drawW'] == 3840 and report['ready']['quality']['drawH'] == 2160
        if args.motion:
            evaluate('CLApp.scene().controls.autoRotate=true;CLApp.scene().controls.autoRotateSpeed=.35')
        report['install'] = evaluate(INSTALL)
        assert report['install']['canvas'] == [3840, 2160]

        total_seconds = int(round(args.minutes * 60))
        started = time.monotonic()
        prev = None
        for second in range(total_seconds):
            target = started + second + 1
            now = time.monotonic()
            if now < target:
                time.sleep(target - now)
            try:
                snap = evaluate(SNAPSHOT)
                if not isinstance(snap, dict) or 'frames' not in snap:
                    raise RuntimeError('bad snapshot: ' + repr(snap))
            except Exception as exc:
                report['sampleErrors'].append({'second': second + 1, 'error': str(exc)})
                continue
            fps = None
            if prev is not None:
                dt = (snap['t'] - prev['t']) / 1000.0
                if dt > 0:
                    fps = (snap['frames'] - prev['frames']) / dt
            row = {'second': second + 1, 't': snap['t'], 'fps': None if fps is None else round(fps, 2),
                   'mode': classify_fps(fps, bands),
                   'heap': snap['heap'], 'render': snap['render'], 'memory': snap['memory'], 'programs': snap['programs'],
                   'contextLost': snap['contextLost'] + (1 if snap['contextLostLive'] else 0),
                   'consoleErrors': snap['consoleErrors'], 'jserr': snap['jserr'], 'jsrej': snap['jsrej'],
                   'shaderErrors': snap['shaderErrors']}
            report['samples'].append(row)
            if second % 10 == 0 or second == total_seconds - 1:
                heap_used = snap['heap']['usedMB'] if snap['heap'] else None
                print(json.dumps({'second': second + 1, 'fps': row['fps'], 'heapUsedMB': heap_used,
                                  'contextLost': row['contextLost'], 'jserr': row['jserr'], 'jsrej': row['jsrej'],
                                  'consoleErrors': row['consoleErrors']}, ensure_ascii=False), flush=True)
            prev = snap
        if len(report['samples']) < 2:
            failures.append('sampler produced fewer than 2 snapshots (%d errors); no curve to report' % len(report['sampleErrors']))
            report['ok'] = False
            report['failures'] = failures
            (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps({'saved': str(out / 'report.json'), 'ok': False, 'failures': failures}, ensure_ascii=False), flush=True)
            return 1
        actual_seconds = (report['samples'][-1]['t'] - report['samples'][0]['t']) / 1000.0 if len(report['samples']) >= 2 else 0
        report['actualSampledSeconds'] = round(actual_seconds, 1)

        minutes = []
        minute_count = (max(s['second'] for s in report['samples']) + 59) // 60
        for m in range(minute_count):
            chunk = [s for s in report['samples'] if m * 60 < s['second'] <= (m + 1) * 60]
            fps_values = sorted(s['fps'] for s in chunk if s['fps'] is not None)
            heaps = [s['heap'] for s in chunk if s['heap']]
            platform_seconds = {}
            for s in chunk:
                if s['mode'] is not None:
                    platform_seconds[s['mode']] = platform_seconds.get(s['mode'], 0) + 1
            classified = {k: v for k, v in platform_seconds.items() if k != 'unclassified'}
            entry = {'minute': m + 1, 'seconds': len(chunk), 'partial': len(chunk) < 58,
                     'fps': {'n': len(fps_values),
                             'mean': round(sum(fps_values) / len(fps_values), 2) if fps_values else None,
                             'p5': round(percentile(fps_values, .05), 2) if fps_values else None},
                     'platforms': platform_seconds, 'mixed': len(classified) > 1,
                     'heapEndMB': heaps[-1]['usedMB'] if heaps else None,
                     'heapTotalEndMB': heaps[-1]['totalMB'] if heaps else None}
            if entry['mixed']:
                print(json.dumps({'warning': 'minute spans multiple fps plateaus', 'minute': m + 1,
                                  'platforms': platform_seconds}, ensure_ascii=False), flush=True)
            minutes.append(entry)
        report['minutes'] = minutes

        transitions = []
        prev_mode = None
        for s in report['samples']:
            if s['mode'] is None or s['mode'] == 'unclassified':
                continue
            if prev_mode is not None and s['mode'] != prev_mode:
                transitions.append({'second': s['second'], 'from': prev_mode, 'to': s['mode']})
            prev_mode = s['mode']
        guard_modes = {}
        for s in report['samples']:
            if s['mode'] and s['mode'] != 'unclassified':
                e = guard_modes.setdefault(s['mode'], {'seconds': 0, 'fpsSum': 0.0})
                e['seconds'] += 1
                e['fpsSum'] += s['fps']
        unclassified = sum(1 for s in report['samples'] if s['mode'] == 'unclassified')
        report['modeGuard'] = {
            'bands': [{'name': n, 'fpsLo': lo, 'fpsHi': hi} for n, lo, hi in bands],
            'transitions': transitions, 'transitionCount': len(transitions),
            'plateaus': {n: {'totalSeconds': e['seconds'], 'fpsMean': round(e['fpsSum'] / e['seconds'], 2)}
                         for n, e in guard_modes.items()},
            'unclassifiedSeconds': unclassified,
            'mixedMinutes': [mn['minute'] for mn in minutes if mn['mixed']]}
        heap_points = [(s['t'], s['heap']['usedMB'] if s['heap'] else None) for s in report['samples']]
        slope = slope_mb_per_min(heap_points)
        first, lastrow = report['samples'][0], report['samples'][-1]
        report['heap'] = {'supported': first['heap'] is not None,
                          'usedSlopeMBPerMin': round(slope, 3) if slope is not None else None,
                          'usedFirstMB': first['heap']['usedMB'] if first['heap'] else None,
                          'usedLastMB': lastrow['heap']['usedMB'] if lastrow['heap'] else None}
        report['renderResources'] = {
            'note': 'render.calls/triangles are the most recent render pass only (three.js resets per render call); memory/programs are cumulative',
            'programsFirst': first['programs'], 'programsLast': lastrow['programs'],
            'geometriesFirst': first['memory']['geometries'], 'geometriesLast': lastrow['memory']['geometries'],
            'texturesFirst': first['memory']['textures'], 'texturesLast': lastrow['memory']['textures'],
            'callsFirst': first['render']['calls'], 'callsLast': lastrow['render']['calls'],
            'trianglesFirst': first['render']['triangles'], 'trianglesLast': lastrow['render']['triangles']}
        report['errors'] = {'contextLost': lastrow['contextLost'], 'consoleErrors': lastrow['consoleErrors'],
                            'jserr': lastrow['jserr'], 'jsrej': lastrow['jsrej'], 'shaderErrors': lastrow['shaderErrors']}
        report['errorDetail'] = evaluate(TEARDOWN, True)

        if report['errors']['contextLost']:
            failures.append('webgl context lost: %d' % report['errors']['contextLost'])
        if report['errors']['jserr'] or report['errors']['jsrej']:
            failures.append('uncaught js exceptions/rejections: jserr=%d jsrej=%d' % (report['errors']['jserr'], report['errors']['jsrej']))
        if report['errors']['shaderErrors']:
            failures.append('shader errors: %d' % report['errors']['shaderErrors'])
        if args.gate_growth and slope is not None and slope > args.max_heap_growth_mb_min:
            failures.append('heap growth %.3f MB/min exceeds threshold %.3f' % (slope, args.max_heap_growth_mb_min))
        report['ok'] = not failures
        report['failures'] = failures
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'saved': str(out / 'report.json'), 'ok': report['ok'],
                          'actualSampledSeconds': report['actualSampledSeconds'],
                          'heapSlopeMBPerMin': report['heap']['usedSlopeMBPerMin'],
                          'errors': report['errors'], 'failures': failures,
                          'modeGuard': report['modeGuard'],
                          'minutes': report['minutes']}, ensure_ascii=False), flush=True)
        return 1 if failures else 0
    finally:
        session.close()


if __name__ == '__main__':
    raise SystemExit(main())
