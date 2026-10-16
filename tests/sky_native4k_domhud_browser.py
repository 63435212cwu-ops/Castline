#!/usr/bin/env python3
"""Follow-up drill-down of the DOM/HUD compositing cost found by
tests/sky_native4k_breakdown_browser.py (domhud condition).

Same rAF wall-clock protocol at native 3840x2160, constellation lens, pinned
quality. Baseline windows interleave every condition. Conditions marked
DIAGNOSTIC change rendered output (shadow/backdrop/animations stripped); they
identify the cost mechanism only and are reverted on the spot — nothing here
is a product change.

Also records a MutationObserver diagnostic: how many attribute/text mutations
the page performs per second inside #labels and on the rest of body, so DOM
write volume is measured rather than guessed.
"""
import argparse
import json
import os
from pathlib import Path

from atlas_review_shots import Session
import headless

DIAG = r"""new Promise(function(resolve){
  var labels=document.getElementById('labels');
  var mut={labels:0,body:0};
  var mo1=new MutationObserver(function(recs){mut.labels+=recs.length;});
  if(labels)mo1.observe(labels,{attributes:true,childList:true,subtree:true,characterData:true});
  var mo2=new MutationObserver(function(recs){mut.body+=recs.length;});
  mo2.observe(document.body,{attributes:true,childList:true,subtree:true,characterData:true});
  function featureAudit(){
    function vis(e){var s=getComputedStyle(e);return s.visibility!=='hidden'&&s.display!=='none'&&+s.opacity>0.001;}
    var feats={backdrop:[],filter:[],blend:[],anim:0,transition:0},n=0;
    var all=document.querySelectorAll('body *');
    for(var i=0;i<all.length&&n<6000;i++){var e=all[i];if(!vis(e))continue;n++;
      var s=getComputedStyle(e);
      if(s.backdropFilter&&s.backdropFilter!=='none'&&feats.backdrop.length<12)feats.backdrop.push(e.tagName+'#'+(e.id||'')+'.'+String(e.className).slice(0,40)+' '+s.backdropFilter);
      if(s.filter&&s.filter!=='none'&&feats.filter.length<12)feats.filter.push(e.tagName+'#'+(e.id||'')+'.'+String(e.className).slice(0,40)+' '+s.filter.slice(0,50));
      if(s.mixBlendMode&&s.mixBlendMode!=='normal'&&feats.blend.length<8)feats.blend.push(e.tagName+'#'+(e.id||'')+'.'+String(e.className).slice(0,40));
    }
    feats.anim=document.getAnimations().length;
    return feats;
  }
  var audit=featureAudit();
  var labN=labels?labels.querySelectorAll('*').length:0;
  setTimeout(function(){
    mo1.disconnect();mo2.disconnect();
    resolve({mutLabelsPerSec:+(mut.labels/3).toFixed(1),mutBodyPerSec:+(mut.body/3).toFixed(1),
      labelDomNodes:labN,animations:audit.anim,backdrop:audit.backdrop,filter:audit.filter,blend:audit.blend,
      bodyChildren:[].slice.call(document.body.children).map(function(e){return e.tagName+'#'+(e.id||e.className&&String(e.className).split(' ')[0]||'');}).slice(0,40)});
  },3000);
})"""

SETUP = r"""(function(){
  function sheet(css){var s=document.createElement('style');s.textContent=css;document.head.appendChild(s);return s;}
  var labels=document.getElementById('labels');
  var disc=document.querySelector('.sky-disc');
  window.__dh={
    applied:null,
    apply:function(name){
      this.restore();this.applied=name;
      if(name==='labels'&&labels){labels.style.visibility='hidden';return true;}
      if(name==='discsvg'&&disc){disc.style.visibility='hidden';return true;}
      if(name==='eldindex'){this.s=sheet('#labels::before,#labels::after{display:none!important}');return true;}
      if(name==='animpause'){this.a=document.getAnimations();this.a.forEach(function(x){x.pause();});return this.a.length;}
      if(name==='shadowoff'){this.s=sheet('body *{text-shadow:none!important}');return true;}
      if(name==='backdropoff'){this.s=sheet('body *{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}');return true;}
      if(name==='filteroff'){this.s=sheet('body *{filter:none!important}');return true;}
      if(name==='blendoff'){this.s=sheet('body *{mix-blend-mode:normal!important}');return true;}
      if(name==='chromeshell'){var keep={STAGE:1,SCRIPT:1,STYLE:1,LINK:1,TEMPLATE:1},n=0;this.hidden=[];
        [].slice.call(document.body.children).forEach(function(e){if(!keep[e.tagName]&&getComputedStyle(e).display!=='none'){e.style.visibility='hidden';n++;this.hidden.push(e);}},this);return n;}
      this.applied=null;return false;
    },
    restore:function(){
      if(labels)labels.style.visibility='';
      if(disc)disc.style.visibility='';
      if(this.s){this.s.remove();this.s=null;}
      if(this.a){this.a.forEach(function(x){try{x.play();}catch(e){}});this.a=null;}
      if(this.hidden){this.hidden.forEach(function(e){e.style.visibility='';});this.hidden=null;}
      this.applied=null;
    }
  };
  return {labels:!!labels,disc:!!disc,animations:document.getAnimations().length};
})()"""

SAMPLE = r"""new Promise(function(resolve){
  var S=CLApp.scene(),start=performance.now(),last=start,deltas=[];
  function finish(){
    var elapsed=performance.now()-start,sorted=deltas.slice().sort(function(a,b){return a-b;});
    function p(q){return sorted[Math.min(sorted.length-1,Math.floor(sorted.length*q))]||0;}
    resolve({elapsedMs:elapsed,frames:deltas.length,fps:deltas.length/elapsed*1000,p50:p(.5),p95:p(.95),
      over50:deltas.filter(function(d){return d>50;}).length,
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
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'native4k-domhud'))
    ap.add_argument('--seconds', type=float, default=22)
    ap.add_argument('--settle', type=float, default=24)
    ap.add_argument('--conditions', default='labels,discsvg,eldindex,animpause,shadowoff,backdropoff,filteroff,chromeshell')
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    session = Session(3840, 2160)
    report = {'data': args.data, 'viewport': [3840, 2160, 1], 'secondsPerCondition': args.seconds,
              'conditions': {}, 'baselines': [], 'note': 'conditions except labels/discsvg are DIAGNOSTIC only (they change rendered output); mechanism probes, not candidates'}

    def ev(expr, wait=False):
        r = session.eval(expr, wait)
        if isinstance(r, dict) and r.get('__evalError'):
            raise RuntimeError(r)
        return r

    def delay(seconds):
        ev('new Promise(function(r){setTimeout(r,' + str(round(seconds * 1000)) + ');})', True)

    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=3840, height=2160, deviceScaleFactor=1, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base + '/?data=' + args.data + '&sky=1')
        ready, _, last = session.wait_until('({ready:!!(window.CLApp&&CLApp.scene()&&window.CLSkyDeep&&CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99)})', 45)
        if not ready: raise RuntimeError('scene not ready: ' + str(last))
        delay(args.settle)
        ev('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)')
        delay(6)
        report['setup'] = ev(SETUP)
        report['diag'] = ev(DIAG, True)
        print(json.dumps({'diag': report['diag']}, ensure_ascii=False), flush=True)

        conditions = [c for c in args.conditions.split(',') if c]

        def sample(name):
            delay(3)
            s = ev(SAMPLE.replace('DURATION', str(round(args.seconds * 1000))), True)
            assert s['canvas'] == [3840, 2160] and s['degraded'] == 0, s
            assert s['glError'] == 0 and s['anim'] > args.seconds * .5, s
            print(json.dumps({'condition': name, 'fps': round(s['fps'], 2), 'p50': round(s['p50'], 1), 'p95': round(s['p95'], 1),
                              'frames': s['frames'], 'over50': s['over50']}, ensure_ascii=False), flush=True)
            return s

        for i, name in enumerate(conditions):
            report['baselines'].append(sample('baseline'))
            ok = ev('window.__dh.apply(' + json.dumps(name) + ')')
            row = sample(name)
            row['appliedAs'] = ok
            report['conditions'][name] = row
            ev('window.__dh.restore()')
        report['baselines'].append(sample('baseline'))
        ev('window.__dh.restore()')
        b = [s['fps'] for s in report['baselines']]
        report['baselineStat'] = {'n': len(b), 'mean': round(sum(b) / len(b), 2), 'min': round(min(b), 2), 'max': round(max(b), 2)}
        table = []
        for i, name in enumerate(conditions):
            adjacent = (report['baselines'][i]['fps'] + report['baselines'][i + 1]['fps']) / 2
            fps = report['conditions'][name]['fps']
            table.append({'component': name, 'fpsOff': round(fps, 2), 'adjacentBaseline': round(adjacent, 2),
                          'marginalFps': round(adjacent - fps, 2), 'marginalPct': round((adjacent - fps) / adjacent * 100, 1)})
        report['marginal'] = sorted(table, key=lambda x: -x['marginalFps'])
        print(json.dumps({'baseline': report['baselineStat'], 'marginal': report['marginal']}, ensure_ascii=False, indent=2), flush=True)
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'saved': str(out / 'report.json')}, ensure_ascii=False), flush=True)
    finally:
        session.close()


if __name__ == '__main__':
    main()
