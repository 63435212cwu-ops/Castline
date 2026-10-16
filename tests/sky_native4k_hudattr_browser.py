#!/usr/bin/env python3
"""Precise attribution of the #skyHud compositing cost (chromeshell condition in
tests/sky_native4k_domhud_browser.py): per-element visibility probes and
backdrop-filter removal via inline !important (stylesheet specificity beat the
earlier blanket probe, so that one was inconclusive by construction).

DIAGNOSTIC only: visibility/backdrop probes change rendered output; they are
restored after each window. Headless Apple M4 numbers only.
"""
import argparse, json, os
from pathlib import Path
from atlas_review_shots import Session
import headless

SETUP = r"""(function(){
  var hud=document.getElementById('skyHud');
  function q(s){return document.querySelector(s);}
  function bdOff(els){els.forEach(function(e){if(e){e.style.setProperty('backdrop-filter','none','important');e.style.setProperty('-webkit-backdrop-filter','none','important');}});}
  function hide(els){els.forEach(function(e){if(e)e.style.visibility='hidden';});}
  window.__ha={
    all:function(){var out=[],w=hud?hud.querySelectorAll('*'):[];for(var i=0;i<w.length;i++){var cs=getComputedStyle(w[i]);if(cs.backdropFilter&&cs.backdropFilter!=='none')out.push(w[i]);}return out;},
    apply:function(n){
      this.restore();
      if(n==='hudoff'){hud.style.visibility='hidden';return true;}
      if(n==='bdskytop'){bdOff([q('.sky-top')]);return 1;}
      if(n==='bddeck'){bdOff([].slice.call(hud.querySelectorAll('.skg-deck')));return 1;}
      if(n==='bdviews'){bdOff([].slice.call(hud.querySelectorAll('.skd-views')));return 1;}
      if(n==='bdaudio'){bdOff([q('#skyAudioToggle')]);return 1;}
      if(n==='bdallhud'){var e=this.all();bdOff(e);return e.length;}
      if(n==='tophide'){hide([q('.sky-top')]);return 1;}
      if(n==='deckhide'){hide([].slice.call(hud.querySelectorAll('.skg-deck')));return 1;}
      if(n==='bothhide'){hide([q('.sky-top')].concat([].slice.call(hud.querySelectorAll('.skg-deck'))));return 2;}
      return false;
    },
    restore:function(){
      if(!hud)return;
      hud.style.visibility='';
      var w=hud.querySelectorAll('*');
      w.forEach(function(e){e.style.removeProperty('backdrop-filter');e.style.removeProperty('-webkit-backdrop-filter');e.style.visibility='';});
    }
  };
  return {hud:!!hud,bdCount:window.__ha.all().length};
})()"""

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

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8123')
    ap.add_argument('--data', default='data/cache/d16db79a529a1727352091d5.json')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'native4k-hudattr'))
    ap.add_argument('--seconds', type=float, default=22)
    ap.add_argument('--settle', type=float, default=24)
    ap.add_argument('--conditions', default='bdskytop,bddeck,bdviews,bdaudio,bdallhud,tophide,deckhide,bothhide')
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    session = Session(3840, 2160)
    report = {'viewport': [3840, 2160, 1], 'secondsPerCondition': args.seconds, 'conditions': {}, 'baselines': []}
    def ev(expr, wait=False):
        r = session.eval(expr, wait)
        if isinstance(r, dict) and r.get('__evalError'): raise RuntimeError(r)
        return r
    def delay(s): ev('new Promise(function(r){setTimeout(r,'+str(round(s*1000))+');})', True)
    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=3840, height=2160, deviceScaleFactor=1, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base + '/?data=' + args.data + '&sky=1')
        ready, _, last = session.wait_until('({ready:!!(window.CLApp&&CLApp.scene()&&window.CLSkyDeep&&CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99)})', 45)
        if not ready: raise RuntimeError(str(last))
        delay(args.settle)
        ev('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)')
        delay(6)
        report['setup'] = ev(SETUP)
        print(json.dumps({'setup': report['setup']}, ensure_ascii=False), flush=True)
        conditions = [c for c in args.conditions.split(',') if c]
        def sample(name):
            delay(3)
            s = ev(SAMPLE.replace('DURATION', str(round(args.seconds*1000))), True)
            assert s['canvas'] == [3840, 2160] and s['degraded'] == 0 and s['glError'] == 0
            print(json.dumps({'condition': name, 'fps': round(s['fps'], 2), 'p50': round(s['p50'], 1), 'p95': round(s['p95'], 1)}, ensure_ascii=False), flush=True)
            return s
        for i, name in enumerate(conditions):
            report['baselines'].append(sample('baseline'))
            ok = ev('window.__ha.apply(' + json.dumps(name) + ')')
            row = sample(name); row['appliedAs'] = ok
            report['conditions'][name] = row
            ev('window.__ha.restore()')
        report['baselines'].append(sample('baseline'))
        b = [s['fps'] for s in report['baselines']]
        report['baselineStat'] = {'n': len(b), 'mean': round(sum(b)/len(b), 2), 'min': round(min(b), 2), 'max': round(max(b), 2)}
        table = []
        for i, name in enumerate(conditions):
            adjacent = (report['baselines'][i]['fps'] + report['baselines'][i+1]['fps']) / 2
            fps = report['conditions'][name]['fps']
            table.append({'component': name, 'fpsOff': round(fps, 2), 'adjacentBaseline': round(adjacent, 2),
                          'marginalFps': round(adjacent - fps, 2), 'marginalPct': round((adjacent-fps)/adjacent*100, 1)})
        report['marginal'] = sorted(table, key=lambda x: -x['marginalFps'])
        print(json.dumps({'baseline': report['baselineStat'], 'marginal': report['marginal']}, ensure_ascii=False, indent=2), flush=True)
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'saved': str(out / 'report.json')}, ensure_ascii=False), flush=True)
    finally:
        session.close()

if __name__ == '__main__':
    main()
