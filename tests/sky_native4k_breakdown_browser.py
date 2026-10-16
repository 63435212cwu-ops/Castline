#!/usr/bin/env python3
"""Component-level marginal-cost breakdown for the production sky scene at native 4K.

Same measurement family as tests/scene_native4k_perf_browser.py: real wall-clock
rAF counting, native 3840x2160 device metrics, quality tier pinned (boost on,
dip off, degrade 0), constellation lens, full animation. No pump/fixedDt/frozen
animation/reduced canvas.

Each condition is measured >= --seconds and sits between two interleaved
baseline windows so machine drift does not masquerade as a component's cost.
Marginal cost of a component = mean(fps of adjacent baselines) - fps(off).

Per-component isolation uses only read-only handles exposed for measurement
(CLSkyDeep.layers()) and runtime state toggles (setState / pass.enabled);
product behaviour and defaults are untouched and fully restored after each
condition.

Headless single-machine numbers: they describe THIS host's ANGLE Metal stack
only and are not a cross-device guarantee.
"""
import argparse
import json
import os
from pathlib import Path

from atlas_review_shots import Session
import headless

ROOT = Path(__file__).resolve().parents[1]

SETUP = r"""(function(){
  var S=CLApp.scene(), core=S.core(), C=core.getComposer(), L=CLSkyDeep.layers();
  function passBy(fn){for(var i=0;i<C.passes.length;i++){if(fn(C.passes[i]))return i;}return -1;}
  var iBloom=passBy(function(p){return p&&p.strength!==undefined&&(p.nMips!==undefined);});
  var iDisc=(L.post&&L.post.stats?L.post.stats().passIndex:-1);
  var iCine=passBy(function(p){return p&&p.uniforms&&p.uniforms.uExposure;});
  var iScene=passBy(function(p){return p&&(p.directResolve!==undefined);});
  var domEls=[].slice.call(document.querySelectorAll('#labels,.sky-disc,.sky-top,.sky-bottom,.sky-crumb'));
  if(domEls.some(function(e){return e===document.body||e===document.documentElement||e.contains(S.renderer.domElement);}))throw new Error('DOM probe must not hide the main canvas or its ancestors');
  var domSaved=domEls.map(function(e){return {node:e,value:e.style.getPropertyValue('visibility'),priority:e.style.getPropertyPriority('visibility')};});
  var glassNodes=[].slice.call(document.querySelectorAll('.sky-top,.sky-top *,.sky-bottom,.sky-bottom *,.sky-crumb')).filter(function(e){return getComputedStyle(e).backdropFilter!=='none';});
  var glassSaved=glassNodes.map(function(e){return {node:e,value:e.style.getPropertyValue('backdrop-filter'),priority:e.style.getPropertyPriority('backdrop-filter')};});
  var savedMsaa=core.getComposer().passes[iScene].samples;
  window.__bd={
    idx:{scene:iScene,disc:iDisc,bloom:iBloom,cine:iCine},
    msaa:savedMsaa,
    apply:function(name){
      this.restore();
      if(name==='baseline')return true;
      if(name==='msaa'){var p=C.passes[iScene];p.samples=0;p.setSize(3840,2160);return p.samples===0;}
      if(name==='discpass'){C.passes[iDisc].enabled=false;return !C.passes[iDisc].enabled;}
      if(name==='bloom'){C.passes[iBloom].enabled=false;return !C.passes[iBloom].enabled;}
      if(name==='cine'){C.passes[iCine].enabled=false;return !C.passes[iCine].enabled;}
      if(name==='nebula'){L.neb.setState('hidden',true);return L.neb.stats().alpha<=0.002||true;}
      if(name==='cosmos'){L.cosmos.setState('hidden',true);return true;}
      if(name==='stars'){L.stars.setState('hidden');if(L.trails)L.trails.setState('hidden');return L.stars.stats().state;}
      if(name==='bundles'){L.bun.setState('hidden');return true;}
      if(name==='rings'){L.rings.setState('hidden');return true;}
      if(name==='labels'||name==='discdom'||name==='chrome'){var selected=domEls.filter(function(e){return name==='labels'?e.id==='labels':name==='discdom'?e.classList.contains('sky-disc'):e.classList.contains('sky-top')||e.classList.contains('sky-bottom')||e.classList.contains('sky-crumb');});selected.forEach(function(e){e.style.visibility='hidden';});return selected.length;}
      if(name==='glass'){glassNodes.forEach(function(e){e.style.setProperty('backdrop-filter','none','important');});return glassNodes.length;}
      if(name==='domhud'){domEls.forEach(function(e){e.style.visibility='hidden';});return domEls.length;}
      return false;
    },
    restore:function(){
      var p=C.passes[iScene];if(p.samples!==savedMsaa){p.samples=savedMsaa;p.setSize(3840,2160);}
      if(iDisc>=0)C.passes[iDisc].enabled=true;
      if(iBloom>=0)C.passes[iBloom].enabled=true;
      if(iCine>=0)C.passes[iCine].enabled=true;
      L.neb.setState('show',true);
      L.cosmos.setState('show',true);
      L.stars.setState('show');if(L.trails)L.trails.setState('show');
      L.bun.setState('show');
      L.rings.setState('backdrop');
      domSaved.forEach(function(v){if(v.value)v.node.style.setProperty('visibility',v.value,v.priority);else v.node.style.removeProperty('visibility');});
      glassSaved.forEach(function(v){if(v.value)v.node.style.setProperty('backdrop-filter',v.value,v.priority);else v.node.style.removeProperty('backdrop-filter');});
    }
  };
  var gl=S.renderer.getContext(),ex=gl.getExtension('WEBGL_debug_renderer_info');
  return {idx:window.__bd.idx,msaa:savedMsaa,domEls:domEls.map(function(e){return {tag:e.tagName,id:e.id,className:e.className};}),glassNodes:glassNodes.length,
    renderer:gl.getParameter(gl.RENDERER),unmaskedRenderer:ex?gl.getParameter(ex.UNMASKED_RENDERER_WEBGL):null,
    ua:navigator.userAgent,dpr:window.devicePixelRatio};
})()"""

SAMPLE = r"""new Promise(function(resolve){
  var S=CLApp.scene(),start=performance.now(),last=start,deltas=[],animBefore=S.digest().tAnim;
  function finish(){
    var elapsed=performance.now()-start,sorted=deltas.slice().sort(function(a,b){return a-b;});
    function p(q){return sorted[Math.min(sorted.length-1,Math.floor(sorted.length*q))]||0;}
    resolve({elapsedMs:elapsed,frames:deltas.length,fps:deltas.length/elapsed*1000,p50:p(.5),p95:p(.95),max:p(1),
      over50:deltas.filter(function(d){return d>50;}).length,
      nebula:CLSkyDeep.stats().nebula&&{alpha:+CLSkyDeep.stats().nebula.alpha.toFixed(3),steps:CLSkyDeep.stats().nebula.steps,viewScale:CLSkyDeep.stats().nebula.viewScale},
      cosmos:{alpha:+CLSkyDeep.stats().cosmos.alpha.toFixed(3)},
      calm:S.calm(),anim:S.digest().tAnim-animBefore,
      presentation:{body:getComputedStyle(document.body).visibility,canvas:getComputedStyle(S.renderer.domElement).visibility,display:getComputedStyle(S.renderer.domElement).display,document:document.visibilityState},
      canvas:[S.renderer.domElement.width,S.renderer.domElement.height],
      degrade:S.quality().degrade,boost:S.quality().boost,
      render:{calls:S.renderer.info.render.calls,triangles:S.renderer.info.render.triangles},
      glError:S.renderer.getContext().getError()});
  }
  function frame(){var now=performance.now();deltas.push(now-last);last=now;if(now-start>=DURATION)finish();else requestAnimationFrame(frame);}
  requestAnimationFrame(frame);
})"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8123')
    ap.add_argument('--data', default='data/cache/d16db79a529a1727352091d5.json')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'native4k-breakdown'))
    ap.add_argument('--seconds', type=float, default=22)
    ap.add_argument('--settle', type=float, default=22)
    ap.add_argument('--conditions', default='discpass,bloom,cine,nebula,cosmos,stars,bundles,rings,msaa,domhud')
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    session = Session(3840, 2160)
    report = {'data': args.data, 'view': 'constellation', 'viewport': [3840, 2160, 1], 'pump': False,
              'secondsPerCondition': args.seconds, 'conditions': {}, 'baselines': []}

    def ev(expr, wait=False):
        r = session.eval(expr, wait)
        if isinstance(r, dict) and r.get('__evalError'):
            raise RuntimeError(r)
        return r

    def delay(seconds):
        ev('new Promise(function(r){setTimeout(r,' + str(round(seconds * 1000)) + ');})', True)

    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=3840, height=3840 // 16 * 9, deviceScaleFactor=1, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base + '/?data=' + args.data + '&sky=1')
        ready, _, last = session.wait_until('({ready:!!(window.CLApp&&CLApp.scene()&&window.CLSkyDeep&&CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99)})', 45)
        if not ready: raise RuntimeError('scene not ready: ' + str(last))
        delay(args.settle)
        ev('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)')
        delay(6)
        report['ready'] = ev('({quality:CLApp.scene().quality(),perf:CLApp.scene().perf()})')
        q = report['ready']['quality']
        assert q['drawW'] == 3840 and q['drawH'] == 2160, q
        report['environment'] = ev(SETUP)
        print(json.dumps({'environment': report['environment']}, ensure_ascii=False), flush=True)

        conditions = [c for c in args.conditions.split(',') if c]

        def sample(name):
            delay(3)
            s = ev(SAMPLE.replace('DURATION', str(round(args.seconds * 1000))), True)
            assert s['canvas'] == [3840, 2160] and s['degrade'] == 0 and s['boost'] in (0, 1), s
            assert not s['calm'] and s['glError'] == 0, s
            assert s['anim'] > args.seconds * .8, s
            assert s['presentation']['body']=='visible' and s['presentation']['canvas']=='visible' and s['presentation']['display']!='none', s
            print(json.dumps({'condition': name, 'fps': round(s['fps'], 2), 'p50': round(s['p50'], 1), 'p95': round(s['p95'], 1),
                              'frames': s['frames'], 'over50': s['over50']}, ensure_ascii=False), flush=True)
            return s

        baselines = []
        for i, name in enumerate(conditions):
            report['baselines'].append(sample('baseline'))
            ok = ev('window.__bd.apply(' + json.dumps(name) + ')')
            row = sample(name)
            row['appliedAs'] = ok
            report['conditions'][name] = row
            ev('window.__bd.restore()')
        report['baselines'].append(sample('baseline'))
        report['restore'] = ev('window.__bd.restore();({enabled:CLApp.scene().core().getComposer().passes.map(function(p){return !!p.enabled;}),nebula:+CLSkyDeep.stats().nebula.alpha.toFixed(3)})')
        b = [s['fps'] for s in report['baselines']]
        report['baselineStat'] = {'n': len(b), 'mean': round(sum(b) / len(b), 2), 'min': round(min(b), 2), 'max': round(max(b), 2)}
        table = []
        for i, name in enumerate(conditions):
            adjacent = (report['baselines'][i]['fps'] + report['baselines'][i + 1]['fps']) / 2
            fps = report['conditions'][name]['fps']
            table.append({'component': name, 'fpsOff': round(fps, 2), 'adjacentBaseline': round(adjacent, 2),
                          'marginalFps': round(adjacent - fps, 2), 'marginalPct': round((adjacent - fps) / adjacent * 100, 1)})
        report['marginal'] = sorted(table, key=lambda x: -x['marginalFps'])
        print(json.dumps({'baseline': report['baselineStat'], 'marginal': report['marginal'], 'restore': report['restore']}, ensure_ascii=False, indent=2), flush=True)
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'saved': str(out / 'report.json')}, ensure_ascii=False), flush=True)
    finally:
        session.close()


if __name__ == '__main__':
    main()
