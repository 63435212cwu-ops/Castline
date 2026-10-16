#!/usr/bin/env python3
"""Real-clock native 4K sampling and same-frame MSAA visual comparison.

No pump/fixedDt, lower quality, frozen animation or reduced-size canvas is used
for performance samples. MSAA A/B changes only the live scene-pass target.
"""
import argparse
import os
import base64
import hashlib
import json
from pathlib import Path

from atlas_review_shots import Session
import headless

ROOT = Path(__file__).resolve().parents[1]

SAMPLE = r"""new Promise(function(resolve){
  var S=CLApp.scene(), core=S.core(), pass=core.getComposer().passes[0];
  var start=performance.now(), last=start, deltas=[], before=S.digest().tAnim, cameraBefore=S.camera.position.toArray();
  function finish(){
    var elapsed=performance.now()-start, sorted=deltas.slice().sort(function(a,b){return a-b;});
    function p(q){return sorted[Math.min(sorted.length-1,Math.floor(sorted.length*q))]||0;}
    var R=S.renderer, gl=R.getContext(), props=pass.rt&&R.properties.get(pass.rt);
    var saved=gl.getParameter(gl.RENDERBUFFER_BINDING), actualSamples=null;
    if(props&&props.__webglColorRenderbuffer){gl.bindRenderbuffer(gl.RENDERBUFFER,props.__webglColorRenderbuffer);actualSamples=gl.getRenderbufferParameter(gl.RENDERBUFFER,gl.RENDERBUFFER_SAMPLES);gl.bindRenderbuffer(gl.RENDERBUFFER,saved);}
    var segmentQuality=S.quality(), segmentPerf=S.perf(), segmentCalm=S.calm(), segmentCanvas=[R.domElement.width,R.domElement.height],
      segmentGlError=gl.getError(), segmentAnimationSeconds=S.digest().tAnim-before;
    var segmentState={layoutMode:core.getLayoutInfo()&&core.getLayoutInfo().mode,presentation:{body:getComputedStyle(document.body).visibility,canvas:getComputedStyle(R.domElement).visibility,display:getComputedStyle(R.domElement).display,document:document.visibilityState},canvas:segmentCanvas,quality:segmentQuality,perf:segmentPerf,calm:segmentCalm,glError:segmentGlError,
      animationSeconds:segmentAnimationSeconds,elapsedMs:elapsed,frames:deltas.length};
    resolve({elapsedMs:elapsed,frames:deltas.length,fps:deltas.length/elapsed*1000,p50:p(.5),p95:p(.95),p99:p(.99),max:p(1),
      /* `_deltas` 供**分段采样**在合并后重算分位数（不是把各段的分位数再平均——
         段间负载不同时那样会失真）。短窗口下它同样可用，不影响既有断言。 */
      _deltas:deltas,
      over50:deltas.filter(function(d){return d>50;}).length,quality:segmentQuality,perf:segmentPerf,requestedSamples:pass.samples,
      actualColorSamples:actualSamples,directResolve:pass.directResolve===true,directResolveCount:pass.directResolveCount||0,copyDrawCount:pass.copyDrawCount||0,
      glError:segmentGlError,canvas:segmentCanvas,calm:segmentCalm,animationSeconds:segmentAnimationSeconds,segmentState:segmentState,
      renderTargets:core.getComposer().passes.map(function(p){return {enabled:p.enabled,kind:p.constructor.name||'pass',msaa:p.samples||0};}),
      motion:S.controls.autoRotate,cameraBefore:cameraBefore,cameraAfter:S.camera.position.toArray()});
  }
  function frame(){var now=performance.now();deltas.push(now-last);last=now;if(now-start>=DURATION)finish();else requestAnimationFrame(frame);}
  requestAnimationFrame(frame);
})"""

SAME_FRAME = r"""new Promise(function(resolve){requestAnimationFrame(function(){
  var S=CLApp.scene(), core=S.core(), R=S.renderer, C=core.getComposer(), pass=C.passes[0], old=pass.samples, oldResolve=pass.directResolve;
  var before=S.digest().tAnim, images=[];
  try{
    COMPARISONS.forEach(function(variant){
      pass.samples=variant.samples;pass.directResolve=variant.directResolve;pass.setSize(R.domElement.width,R.domElement.height);C.render();
      images.push({samples:variant.samples,resolve:variant.directResolve?'blit':'shader',png:R.domElement.toDataURL('image/png')});
    });
    resolve({sameAnimationTime:before===S.digest().tAnim,animationTime:before,camera:S.camera.position.toArray(),images:images});
  }finally{pass.samples=old;pass.directResolve=oldResolve;pass.setSize(R.domElement.width,R.domElement.height);}
});})"""

NEGATIVE = r"""(function(){
  var S=CLApp.scene(), core=S.core(), deltas=[], dispose=core.registerFrameHook(function(dt){
    deltas.push(dt);var end=performance.now()+120;while(performance.now()<end){}
  });
  return new Promise(function(resolve){setTimeout(function(){
    var out={perf:S.perf(),frames:deltas.length,animationMaxMs:Math.max.apply(null,deltas)*1000,quality:S.quality()};
    dispose();resolve(out);
  },2200);});
})()"""


def _segment_problems(segment, expected_canvas=(3840, 2160)):
    problems = []
    state = segment.get("state") or {}
    quality = state.get("quality") or {}
    canvas = state.get("canvas")
    if state.get("layoutMode") != "sky":
        problems.append("parent layout is not the sky layout")
    presentation = state.get("presentation") or {}
    if presentation.get("body") != "visible" or presentation.get("canvas") != "visible" or presentation.get("display") == "none":
        problems.append("main canvas presentation is hidden or unreported")
    if list(canvas or []) != list(expected_canvas):
        problems.append("drawing buffer is not native 3840x2160")
    if quality.get("drawW") != expected_canvas[0] or quality.get("drawH") != expected_canvas[1]:
        problems.append("quality draw dimensions are not native 3840x2160")
    if quality.get("degrade") != 0:
        problems.append("quality degrade tier is not zero")
    if state.get("calm") is not False:
        problems.append("calm/reduced-motion is active or unreported")
    if state.get("glError") != 0:
        problems.append("WebGL error is nonzero or unreported")
    elapsed_ms = segment.get("elapsedMs") or 0
    animation_seconds = state.get("animationSeconds")
    if elapsed_ms <= 0 or not isinstance(animation_seconds, (int, float)):
        problems.append("real segment animation progress is missing")
    elif animation_seconds < (elapsed_ms / 1000.0) * 0.8:
        problems.append("animation progress is below 80% of real segment duration")
    intervals = segment.get("intervalsMs")
    if not isinstance(intervals, list) or len(intervals) != segment.get("frames"):
        problems.append("raw rAF interval count does not match frame count")
    elif any(not isinstance(value, (int, float)) or value < 0 for value in intervals):
        problems.append("raw rAF intervals are invalid")
    elif abs(sum(intervals) - elapsed_ms) > max(2.0, elapsed_ms * 0.005):
        problems.append("raw rAF intervals do not cover measured segment duration")
    return problems


def _native4k_summary(segments):
    failures = []
    for segment in segments:
        problems = _segment_problems(segment)
        if problems:
            failures.append({"index": segment.get("index"), "problems": problems})
    return {"ok": bool(segments) and not failures, "expectedCanvas": [3840, 2160],
            "segmentCount": len(segments), "failedSegments": failures}


def collect_segments(evaluate, total_seconds, segment_seconds):
    """Sample one continuous real-rAF window in CDP-sized segments and merge each interval once.

    Each segment keeps its own canvas, quality tier, calm state, GL error and real animation-time
    advance. A later degraded or resized segment cannot be hidden by the first segment.
    """
    total_ms = int(round(total_seconds * 1000))
    seg_ms = int(round((segment_seconds or total_seconds) * 1000))
    seg_ms = max(1000, min(seg_ms, 30000))
    got, deltas, segments, parts = 0, [], [], []
    frames = 0
    elapsed_ms = 0.0
    animation_seconds = 0.0
    while got < total_ms:
        want = min(seg_ms, total_ms - got)
        part = evaluate(SAMPLE.replace("DURATION", str(want)), True)
        state = part.get("segmentState") or {}
        part_deltas = list(part.get("_deltas") or [])
        segment = {"index": len(segments) + 1, "requestedMs": want,
                   "frames": int(part.get("frames") or 0), "elapsedMs": float(part.get("elapsedMs") or 0),
                   "fps": part.get("fps"), "state": state, "intervalsMs": part_deltas}
        segment["native4kProblems"] = _segment_problems(segment)
        segments.append(segment)
        parts.append(part)
        deltas.extend(part_deltas)
        frames += segment["frames"]
        elapsed_ms += segment["elapsedMs"]
        animation_seconds += float(state.get("animationSeconds") or 0)
        got += want

    stable_keys = ("requestedSamples", "actualColorSamples", "directResolve", "directResolveCount",
                   "copyDrawCount", "renderTargets", "motion", "cameraBefore", "cameraAfter")
    merged = {key: parts[-1][key] for key in stable_keys if key in parts[-1]}
    merged["frames"] = frames
    merged["elapsedMs"] = elapsed_ms
    merged["animationSeconds"] = animation_seconds
    merged["fps"] = frames / elapsed_ms * 1000 if elapsed_ms > 0 else None
    merged["segments"] = segments
    merged["segmented"] = len(segments)
    merged["native4k"] = _native4k_summary(segments)
    merged["deltas"] = list(deltas)
    state_index = (merged["native4k"]["failedSegments"][0]["index"] - 1
                   if merged["native4k"]["failedSegments"] else len(segments) - 1)
    state = segments[state_index]["state"]
    merged["stateSourceSegment"] = state_index + 1
    merged["canvas"] = state.get("canvas")
    merged["quality"] = state.get("quality")
    merged["perf"] = state.get("perf")
    merged["calm"] = state.get("calm")
    merged["glError"] = state.get("glError")
    allv = sorted(deltas)
    if allv:
        def _q(q):
            return allv[min(len(allv) - 1, int(len(allv) * q))]
        merged["p50"] = _q(.5)
        merged["p95"] = _q(.95)
        merged["p99"] = _q(.99)
        merged["max"] = allv[-1]
        merged["over50"] = sum(1 for value in allv if value > 50)
        merged["over334"] = sum(1 for value in allv if value > 33.4)
        merged["p95_ok"] = merged["p95"] <= 20
        merged["longFramePct"] = round(merged["over334"] / len(allv) * 100, 3)
    return merged


def _self_test_segment(frames, elapsed_ms, animation_seconds=None, **overrides):
    state = {"layoutMode":"sky", "presentation":{"body":"visible","canvas":"visible","display":"block","document":"visible"}, "canvas": [3840, 2160],
             "quality": {"drawW": 3840, "drawH": 2160, "degrade": 0},
             "perf": {"fps": int(frames / elapsed_ms * 1000), "fpsSampling": "wall-clock"},
             "calm": False, "glError": 0,
             "animationSeconds": elapsed_ms / 1000.0 if animation_seconds is None else animation_seconds}
    state.update(overrides)
    return {"frames": frames, "elapsedMs": elapsed_ms, "fps": frames / elapsed_ms * 1000,
            "_deltas": [float(elapsed_ms) / frames] * frames, "segmentState": state}


def run_self_test():
    parts = [_self_test_segment(30, 1000), _self_test_segment(60, 1000)]
    def evaluate(_expression, _wait):
        if not parts:
            raise AssertionError("self-test evaluator received too many segments")
        return parts.pop(0)
    merged = collect_segments(evaluate, 2, 1)
    assert merged["frames"] == 90, merged
    assert merged["elapsedMs"] == 2000, merged
    assert merged["fps"] == 45, merged
    assert merged["animationSeconds"] == 2, merged
    assert len(merged["deltas"]) == merged["frames"] == 90, merged
    assert abs(sum(merged["deltas"]) - merged["elapsedMs"]) < 1e-6, merged
    assert abs(merged["p95"] - (1000.0 / 30.0)) < 0.001, merged["p95"]
    assert merged["native4k"]["ok"], merged["native4k"]

    single_parts = [_self_test_segment(30, 1000)]
    def single_evaluate(_expression, _wait):
        return single_parts.pop(0)
    single = collect_segments(single_evaluate, 1, 1)
    assert single["frames"] == 30 and single["elapsedMs"] == 1000 and single["animationSeconds"] == 1, single
    assert len(single["deltas"]) == 30 and abs(sum(single["deltas"]) - 1000) < 1e-6, single

    for changed in ({"quality": {"drawW": 3840, "drawH": 2160, "degrade": 1}},
                    {"canvas": [1920, 1080]}, {"calm": True}, {"glError": 128}, {"animationSeconds": 0.2}):
        sequence = [_self_test_segment(30, 1000), _self_test_segment(30, 1000)]
        sequence[1]["segmentState"].update(changed)
        def changed_evaluate(_expression, _wait):
            return sequence.pop(0)
        result = collect_segments(changed_evaluate, 2, 1)
        assert not result["native4k"]["ok"], (changed, result["native4k"])
        assert result["native4k"]["failedSegments"][0]["index"] == 2, result["native4k"]
        assert result["stateSourceSegment"] == 2, result
        if "canvas" in changed:
            assert result["canvas"] == changed["canvas"], result
        if "quality" in changed:
            assert result["quality"]["degrade"] == 1, result
    print("SELFTEST PASS: 2 segments produce 45fps/2s/90frames; 1 segment counted once; later tier/canvas/calm/GL regressions rejected")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8123')
    ap.add_argument('--data', default='data/cache/d16db79a529a1727352091d5.json')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS','/tmp/castline-shots'),'native4k-ab'))
    ap.add_argument('--seconds', type=float, default=8)
    ap.add_argument('--segment', type=float, default=0,
                    help='把长窗口按此秒数分段采样并合并统计（0=不分段）。'
                         'WS 读取超时是 40 s，超过它的窗口必须分段；'
                         '分段之间不暂停渲染，故合并后的帧间隔仍属同一段连续时间。')
    ap.add_argument('--settle', type=float, default=22)
    ap.add_argument('--sequence', default='4,2,4')
    ap.add_argument('--resolve-sequence', default='shader', help='One mode, or one shader/blit mode per sample in sequence')
    ap.add_argument('--compare-resolve', action='store_true', help='Compare shader copy and direct resolve at the final requested MSAA')
    ap.add_argument('--negative-control', action='store_true')
    ap.add_argument('--motion', action='store_true')
    ap.add_argument('--skip-images', action='store_true')
    ap.add_argument('--view', choices=['constellation', 'plot', 'compass'], default='constellation')
    ap.add_argument('--resize-check', action='store_true')
    ap.add_argument('--self-test', action='store_true', help='CPU-only accumulator and native-4K segment checks')
    args = ap.parse_args()
    if args.self_test:
        run_self_test()
        return
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    session = Session(3840, 2160)
    report = {'data': args.data, 'view': args.view, 'viewport': [3840, 2160, 1], 'pump': False,
              'coreSha256': hashlib.sha256((ROOT / 'js/core/scene-core.js').read_bytes()).hexdigest(),
              'sceneSha256':hashlib.sha256((ROOT/'js/scene.js').read_bytes()).hexdigest(),
              'groupsShellSha256':hashlib.sha256((ROOT/'js/sky/sky-groups-shell.js').read_bytes()).hexdigest(),
              'samples': [], 'failures': []}

    def evaluate(expression, wait=False):
        result = session.eval(expression, wait)
        if isinstance(result, dict) and result.get('__evalError'):
            raise RuntimeError(result)
        return result

    def delay(seconds):
        evaluate('new Promise(function(r){setTimeout(r,' + str(round(seconds * 1000)) + ');})', True)

    def save_report():
        temp = out / 'report.json.tmp'
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        os.replace(temp, out / 'report.json')

    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=3840, height=2160, deviceScaleFactor=1, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base + '/?data=' + args.data + '&sky=1')
        ready, _, last = session.wait_until('({ready:!!(window.CLApp&&CLApp.scene()&&window.CLSkyDeep&&CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99)})', 45)
        if not ready: raise RuntimeError('scene not ready: ' + str(last))
        delay(args.settle)
        report['autoBeforePin'] = evaluate('CLApp.scene().quality()')
        if args.view == 'plot': evaluate('CLSky.setPlot(true)'); delay(4)
        elif args.view == 'compass': evaluate('CLSky.openCompass(CLApp.graph().characters[0].name)'); delay(5)
        evaluate('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)')
        delay(6)
        report['ready'] = evaluate('({quality:CLApp.scene().quality(),perf:CLApp.scene().perf(),gpu:CLApp.scene().renderer.getContext().getParameter(CLApp.scene().renderer.getContext().RENDERER)})')
        assert report['ready']['quality']['drawW'] == 3840 and report['ready']['quality']['drawH'] == 2160
        assert report['ready']['perf']['fpsSampling'] == 'wall-clock'
        if args.motion: evaluate('CLApp.scene().controls.autoRotate=true;CLApp.scene().controls.autoRotateSpeed=.35')
        sequence = args.sequence.split(',')
        modes = args.resolve_sequence.split(',')
        if len(modes) == 1: modes *= len(sequence)
        if len(modes) != len(sequence) or any(mode not in ('shader', 'blit') for mode in modes): raise ValueError('invalid resolve sequence')
        for value, mode in zip(sequence, modes):
            requested = int(value)
            evaluate('(function(){var S=CLApp.scene(),p=S.core().getComposer().passes[0];p.samples=' + str(requested) + ';p.directResolve=' + ('true' if mode == 'blit' else 'false') + ';p.setSize(3840,2160);})()')
            delay(2)
            sample = collect_segments(evaluate, args.seconds, args.segment)
            sample_failures = []
            if not sample['native4k']['ok']:
                sample_failures.append({'kind': 'native4k-contract', 'details': sample['native4k']})
            if sample['animationSeconds'] <= args.seconds * .8:
                sample_failures.append({'kind': 'total-animation-progress',
                                        'measuredSeconds': sample['animationSeconds'],
                                        'requiredAboveSeconds': args.seconds * .8})
            sample['validation'] = {'ok': not sample_failures, 'failures': sample_failures}
            report['samples'].append(sample)
            report['ok'] = not sample_failures
            if sample_failures:
                report['failures'].extend(sample_failures)
                save_report()
                raise AssertionError('native-4K sample failed after durable report: ' +
                                     json.dumps(sample_failures, ensure_ascii=False))
            save_report()
            print(json.dumps({'samples': requested, 'actual': sample['actualColorSamples'], 'resolve': mode, 'fps': sample['fps'], 'p95': sample['p95'], 'animationSeconds': sample['animationSeconds']}, ensure_ascii=False), flush=True)
        if not args.skip_images:
            comparisons = ([{'samples': requested, 'directResolve': False}, {'samples': requested, 'directResolve': True}]
                           if args.compare_resolve else [{'samples': 4, 'directResolve': False}, {'samples': 2, 'directResolve': False}])
            visual = evaluate(SAME_FRAME.replace('COMPARISONS', json.dumps(comparisons)), True)
            assert visual['sameAnimationTime']
            report['sameFrame'] = {k: v for k, v in visual.items() if k != 'images'}
            for entry in visual['images']:
                path = out / ('same-frame-msaa' + str(entry['samples']) + '-' + entry['resolve'] + '.png')
                path.write_bytes(base64.b64decode(entry['png'].split(',', 1)[1]))
            report['sameFrame']['images'] = [str(out / ('same-frame-msaa' + str(e['samples']) + '-' + e['resolve'] + '.png')) for e in visual['images']]
        if args.negative_control:
            negative = evaluate(NEGATIVE, True)
            report['longFrameNegativeControl'] = negative
            assert negative['perf']['fps'] < 12 and negative['perf']['wallDeltaMs'] > 100 and negative['animationMaxMs'] <= 50.001
            print(json.dumps({'longFrameNegativeControl': negative}, ensure_ascii=False), flush=True)
        if args.resize_check:
            report['resizeChecks'] = []
            for width, height in [(1440, 900), (3840, 2160)]:
                resolves_before = evaluate('CLApp.scene().core().getComposer().passes[0].directResolveCount')
                session.ws.call('Emulation.setDeviceMetricsOverride', width=width, height=height, deviceScaleFactor=1, mobile=False)
                evaluate('CLApp.scene().core().getComposer().passes[0].directResolve=true;CLApp.scene().setBoost(true);CLApp.scene().setDegrade(0);CLApp.scene().resize()')
                delay(2)
                resized = evaluate('(function(){var S=CLApp.scene(),C=S.core().getComposer(),p=C.passes[0],q=S.quality();return {quality:q,sceneRT:[p.rt.width,p.rt.height],composerRT:[C.readBuffer.width,C.readBuffer.height],directResolves:p.directResolveCount,glError:S.renderer.getContext().getError()};})()')
                assert resized['quality']['drawW'] == width and resized['quality']['drawH'] == height and resized['glError'] == 0
                assert resized['sceneRT'] == resized['composerRT'] and resized['sceneRT'] == [width, height]
                assert resized['directResolves'] > resolves_before
                report['resizeChecks'].append(resized)
        report['health'] = evaluate(headless.POST_HEALTH_JS.replace('window.__cl && window.__cl.scene', 'window.CLApp && window.CLApp.scene()'), True)
        health = report['health']
        report['ok'] = not health['missing'] and not health['probeErrors'] and not health['shaderErrors'] and not any(health['errorCounts'].values()) and health['jserr'] == 'none' and health['jsrej'] == 'none'
        save_report()
        print(json.dumps({'saved': str(out / 'report.json'), 'ok': report['ok']}, ensure_ascii=False), flush=True)
        if not report['ok']: raise AssertionError('post-interaction health failed')
    finally:
        session.close()


if __name__ == '__main__':
    main()
