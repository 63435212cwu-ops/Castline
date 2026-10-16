#!/usr/bin/env python3
"""A/B evidence for the nebula occupancy-probe mip read (PROBE_LOD in
js/sky/sky-nebula-glsl.js, default 2.0; probeLod=0 reproduces the old
level-0 probe reads).

Visual equivalence: same-animation-time screenshot pairs (calm-pinned phase)
at three camera phases — face-on, grazing tilt, grazing + later drift phase.
Python side diffs the PNGs: changed-pixel counts, max abs diff, PSNR.

Performance: serial same-scene rounds (candidate/baseline interleaved, >=
--rounds each side, --seconds per window) plus whole-frame GPU time measured
with EXT_disjoint_timer_query_webgl2 around composer.render() (the rAF rate
is vsync-saturated on this host and cannot resolve small deltas; a prior
gl.finish() bench was dropped — Chromium flushes instead of blocking).

Headless Apple M4 / ANGLE Metal only; numbers are single-machine facts.
"""
import argparse
import base64
import json
import os
from pathlib import Path

from atlas_review_shots import Session
import headless

SETUP = r"""(function(){
  var S=CLApp.scene(),m=null;
  S.scene.traverse(function(x){if(!m&&x.material&&x.material.uniforms&&x.material.uniforms.uCam&&x.material.uniforms.tSplat)m=x;});
  if(!m)return {err:'nebula mesh not found'};
  var T=CLSkyTokens,Tier=T.TIER&&T.TIER.high||{},GL=CLSkyNebulaGLSL;
  var steps=+(m.material.fragmentShader.match(/#define STEPS (\d+)/)||[])[1]||24;
  var bands=+(m.material.fragmentShader.match(/#define BANDS (\d+)/)||[])[1]||1;
  var oct=Tier.fbm|0,jitter=T.VOL?T.VOL.jitter:0.12;
  window.__pab={
    mesh:m,
    baseline:m.material.fragmentShader,
    candidate:GL.volFrag(oct,jitter,steps,2,bands),
    mode:'baseline',
    use:function(k){var f=k==='candidate'?this.candidate:this.baseline;if(m.material.fragmentShader!==f){m.material.fragmentShader=f;m.material.needsUpdate=true;}this.mode=k;return this.mode+':'+(m.material.fragmentShader.match(/PROBE_LOD (\d\.\d)/)||['','none'])[1];},
    bench:function(n){
      var gl=S.renderer.getContext(),ext=gl.getExtension('EXT_disjoint_timer_query_webgl2'),C=S.core().getComposer();
      if(!ext)return null;
      return new Promise(function(resolve){
        var pending=[],results=[],guard=0;
        C.render();
        function frame(){
          var q=gl.createQuery();
          gl.beginQuery(ext.TIME_ELAPSED_EXT,q);C.render();gl.endQuery(q);
          pending.push(q);
          guard++;
          while(pending.length&&gl.getQueryParameter(pending[0],gl.QUERY_RESULT_AVAILABLE)){
            if(!gl.getParameter(ext.GPU_DISJOINT_EXT))results.push(gl.getQueryParameter(pending[0],gl.QUERY_RESULT)/1e6);
            gl.deleteQuery(pending.shift());
          }
          if(results.length>=n||guard>3*n+60){while(pending.length)gl.deleteQuery(pending.shift());resolve(results);}
          else requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
      });
    }
  };
  var out={ok:true,steps:steps,oct:oct,bands:bands,
    candidateUsesProbeMip:window.__pab.candidate.indexOf('vec4 test=probe(')>=0&&(window.__pab.candidate.match(/PROBE_LOD (\d\.\d)/)||[])[1]==='2.0',
    baselineNoProbeMip:window.__pab.baseline.indexOf('vec4 test=probe(')<0,
    nebula:CLSkyDeep.stats().nebula};
  if(!out.candidateUsesProbeMip||!out.baselineNoProbeMip)out.ok=false;
  return out;
})()"""

PAIR = r"""new Promise(function(resolve){requestAnimationFrame(function(){
  var S=CLApp.scene(),C=S.core().getComposer(),time=S.digest().tAnim,images=[];
  ['candidate','baseline'].forEach(function(mode){
    __pab.use(mode);C.render();C.render();
    images.push({mode:mode,png:S.renderer.domElement.toDataURL('image/png')});
  });
  resolve({sameAnimationTime:time===S.digest().tAnim,animationTime:time,images:images});
});})"""

SAMPLE = r"""new Promise(function(resolve){
  var S=CLApp.scene(),start=performance.now(),last=start,deltas=[];
  function finish(){
    var elapsed=performance.now()-start,sorted=deltas.slice().sort(function(a,b){return a-b;});
    function p(q){return sorted[Math.min(sorted.length-1,Math.floor(sorted.length*q))]||0;}
    resolve({frames:deltas.length,fps:deltas.length/elapsed*1000,p50:p(.5),p95:p(.95),
      degraded:S.quality().degrade,anim:S.digest().tAnim,
      canvas:[S.renderer.domElement.width,S.renderer.domElement.height],glError:S.renderer.getContext().getError()});
  }
  function frame(){var now=performance.now();deltas.push(now-last);last=now;if(now-start>=DURATION)finish();else requestAnimationFrame(frame);}
  requestAnimationFrame(frame);
})"""


def diff_pngs(pa, pb):
    from PIL import Image
    import io, math
    a = Image.open(io.BytesIO(pa)).convert('RGB')
    b = Image.open(io.BytesIO(pb)).convert('RGB')
    if a.size != b.size:
        return {'err': 'size mismatch %s vs %s' % (a.size, b.size)}
    w, h = a.size
    px_a, px_b = a.tobytes(), b.tobytes()
    changed = changed2 = changed8 = 0
    maxd = 0
    se = 0.0
    hot = None
    stride = 997 * 3
    for o in range(0, w * h * 3, 3):
        d0 = abs(px_a[o] - px_b[o]); d1 = abs(px_a[o + 1] - px_b[o + 1]); d2 = abs(px_a[o + 2] - px_b[o + 2])
        d = max(d0, d1, d2)
        if d:
            changed += 1
            se += d0 * d0 + d1 * d1 + d2 * d2
            if d >= 2: changed2 += 1
            if d >= 8: changed8 += 1
            if d > maxd:
                maxd = d
    mse = se / (w * h * 3)
    psnr = 99.0 if mse == 0 else 10 * math.log10(255 * 255 / mse)
    return {'pixels': w * h, 'changed': changed, 'changedGe2': changed2, 'changedGe8': changed8,
            'maxDiff': maxd, 'psnr': round(psnr, 2),
            'changedPct': round(changed / (w * h) * 100, 4)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8123')
    ap.add_argument('--data', default='data/cache/d16db79a529a1727352091d5.json')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'nebula-probe-ab'))
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--settle', type=float, default=22)
    ap.add_argument('--rounds', type=int, default=4)
    ap.add_argument('--skip-fps', action='store_true')
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    session = Session(3840, 2160)
    report = {'data': args.data, 'viewport': [3840, 2160, 1], 'pump': False, 'diffs': {}, 'bench': {}, 'fps': []}

    def ev(expr, wait=False):
        r = session.eval(expr, wait)
        if isinstance(r, dict) and r.get('__evalError'):
            raise RuntimeError(r)
        return r

    def delay(s):
        ev('new Promise(function(r){setTimeout(r,' + str(round(s * 1000)) + ');})', True)

    try:
        session.start()
        session.ws.s.settimeout(max(60, args.seconds + 15))
        session.ws.call('Emulation.setDeviceMetricsOverride', width=3840, height=2160, deviceScaleFactor=1, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base + '/?data=' + args.data + '&sky=1')
        ready, _, last = session.wait_until('({ready:!!(window.CLApp&&CLApp.scene()&&window.CLSkyDeep&&CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99)})', 45)
        if not ready: raise RuntimeError(str(last))
        delay(args.settle)
        ev('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)')
        delay(6)
        report['setup'] = ev(SETUP)
        assert report['setup'].get('ok'), report['setup']
        print(json.dumps({'setup': report['setup']}, ensure_ascii=False), flush=True)

        phases = [
            ('faceon', None),
            ('grazing', 'CLSkyDeep.nudge(0,0.55);'),
            ('grazing-later', None),
        ]
        ev('CLApp.scene().setCalm(true,"lab")')
        delay(1)
        for name, prep in phases:
            if prep:
                ev('CLApp.scene().setCalm(false,"lab");' + prep)
                delay(2.5)
                ev('CLApp.scene().setCalm(true,"lab")')
                delay(1)
            elif name == 'grazing-later':
                ev('CLApp.scene().setCalm(false,"lab")')
                delay(6)
                ev('CLApp.scene().setCalm(true,"lab")')
                delay(1)
            pair = ev(PAIR, True)
            assert pair['sameAnimationTime']
            pngs = {}
            for im in pair['images']:
                raw = base64.b64decode(im['png'].split(',', 1)[1])
                pngs[im['mode']] = raw
                (out / ('%s-%s.png' % (name, im['mode']))).write_bytes(raw)
            d = diff_pngs(pngs['candidate'], pngs['baseline'])
            d['animationTime'] = pair['animationTime']
            report['diffs'][name] = d
            print(json.dumps({'phase': name, 'diff': d}, ensure_ascii=False), flush=True)
        ev('CLApp.scene().setCalm(false,"lab")')
        delay(2)

        report['benchNote'] = 'EXT_disjoint_timer_query marks every frame disjoint on ANGLE Metal headless — no GPU timer data; quantification uses the MSAA-4 proxy rAF rounds below (load raised to push fps below the 60 Hz cap, identical on both sides).'
        report['proxy'] = {'msaa': 4, 'rounds': [], 'nebulaOff': None}
        ev('(function(){var p=CLApp.scene().core().getComposer().passes[0];p.samples=4;p.directResolve=true;p.setSize(3840,2160);})()')
        delay(2)
        for mode in ['candidate', 'baseline'] * args.rounds:
            ev('window.__pab.use(' + json.dumps(mode) + ')')
            delay(2)
            s = ev(SAMPLE.replace('DURATION', str(round(args.seconds * 1000))), True)
            report['proxy']['rounds'].append({'mode': mode, 'fps': round(s['fps'], 2), 'p50': round(s['p50'], 1)})
            print(json.dumps({'proxy-round': mode, 'fps': round(s['fps'], 2), 'p50': round(s['p50'], 1)}, ensure_ascii=False), flush=True)
        ev('CLSkyDeep.layers().neb.setState("hidden",true)')
        delay(2)
        s = ev(SAMPLE.replace('DURATION', str(round(args.seconds * 1000))), True)
        report['proxy']['nebulaOff'] = {'fps': round(s['fps'], 2), 'p50': round(s['p50'], 1)}
        print(json.dumps({'proxy-nebulaOff': report['proxy']['nebulaOff']}, ensure_ascii=False), flush=True)
        ev('CLSkyDeep.layers().neb.setState("show",true);window.__pab.use("candidate")')
        ev('(function(){var p=CLApp.scene().core().getComposer().passes[0];p.samples=2;p.setSize(3840,2160);})()')
        delay(2)
        by = {}
        for row in report['proxy']['rounds']:
            by.setdefault(row['mode'], []).append(row['fps'])
        report['proxy']['summary'] = {m: {'n': len(v), 'mean': round(sum(v) / len(v), 2)} for m, v in by.items()}
        if 'candidate' in by and 'baseline' in by:
            report['proxy']['summary']['deltaMean'] = round(report['proxy']['summary']['candidate']['mean'] - report['proxy']['summary']['baseline']['mean'], 2)
        report['bench'] = {}

        if not args.skip_fps:
            seq = ['candidate', 'baseline'] * args.rounds
            for mode in seq:
                ev('window.__pab.use(' + json.dumps(mode) + ')')
                delay(2.5)
                s = ev(SAMPLE.replace('DURATION', str(round(args.seconds * 1000))), True)
                assert s['canvas'] == [3840, 2160] and s['degraded'] == 0 and s['glError'] == 0
                s['mode'] = mode
                report['fps'].append({k: s[k] for k in ('mode', 'fps', 'p50', 'p95', 'frames')})
                print(json.dumps({'fps-round': mode, 'fps': round(s['fps'], 2), 'p50': round(s['p50'], 1)}, ensure_ascii=False), flush=True)
        ev('window.__pab.use("candidate")')

        fps_by = {}
        for row in report['fps']:
            fps_by.setdefault(row['mode'], []).append(row['fps'])
        report['fpsSummary'] = {m: {'n': len(v), 'mean': round(sum(v) / len(v), 2)} for m, v in fps_by.items()}
        if 'candidate' in fps_by and 'baseline' in fps_by:
            report['fpsSummary']['deltaMean'] = round(report['fpsSummary']['candidate']['mean'] - report['fpsSummary']['baseline']['mean'], 2)
        print(json.dumps({'fpsSummary': report.get('fpsSummary'), 'proxySummary': report.get('proxy', {}).get('summary'), 'proxyNebulaOff': report.get('proxy', {}).get('nebulaOff')}, ensure_ascii=False, indent=2), flush=True)
        report['health'] = ev(headless.POST_HEALTH_JS.replace('window.__cl && window.__cl.scene', 'window.CLApp && window.CLApp.scene()'), True)
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'saved': str(out / 'report.json')}, ensure_ascii=False), flush=True)
    finally:
        session.close()


if __name__ == '__main__':
    main()
