#!/usr/bin/env python3
"""Measure the REAL production thk / depthMetric distribution straight from the
live page, using the exact shader formula. Diagnostic, read-only."""
import json, os, sys, time
from pathlib import Path
ROOT = Path('/Users/carmen/Desktop/星系')
sys.path.insert(0, str(ROOT / 'tests')); sys.dont_write_bytecode = True
from sky_internal_review_shots import Browser, PIN, POSE  # noqa: E402

DATA='data/cache/ed3dc1255ca08fbdaae30bbd.json'; HERO='孙悟空'
M = r"""(()=>{
  var S=CLApp.scene(), T=THREE, out=[];
  S.camera.updateMatrixWorld(true);
  S.scene.traverse(function(o){
    var m=o.material;
    if(!m||!m.fragmentShader) return;
    if(String(m.fragmentShader).indexOf('depthMetric')<0) return;
    if(m.blending!==T.NormalBlending) return;
    var u=m.uniforms, pos=o.geometry.attributes.position;
    var camL=u.uCamL.value, cen=u.uCen.value, rad=u.uRad.value, thkU=u.uThk.value;
    var dst=new T.Vector3(), Vl=new T.Vector3(), eo=new T.Vector3(), ed3=new T.Vector3();
    var rows=[], stride=Math.max(1,Math.floor(pos.count/800));
    for(var i=0;i<pos.count;i+=stride){
      dst.fromBufferAttribute(pos,i);
      Vl.copy(dst).sub(camL).normalize();
      eo.copy(dst).sub(cen).divide(rad); ed3.copy(Vl).divide(rad);
      var qb=eo.dot(ed3), qa=Math.max(1e-5,ed3.dot(ed3)), qc=eo.dot(eo)-1.0;
      var qd=qb*qb-qa*qc, chord= qd>0 ? Math.sqrt(qd)*2.0/qa : 0.0;
      var od=Math.max(chord*thkU,0.0), vH=pos.getY(i);
      var raw=(od+vH*0.40)*u.uLyrVolume.value;
      rows.push({chord:chord, od:od, vH:vH, term_vH:vH*0.40, raw:raw,
                 dm:Math.min(2.0,Math.max(0.0,raw)), thk:Math.min(1.0,Math.min(2.0,Math.max(0.0,raw)))});
    }
    function st(k){var v=rows.map(function(r){return r[k];}).sort(function(a,b){return a-b;});
      var q=function(p){return +v[Math.min(v.length-1,Math.floor(v.length*p))].toFixed(3);};
      return {min:+v[0].toFixed(3),p05:q(.05),med:q(.5),p95:q(.95),max:+v[v.length-1].toFixed(3)};}
    out.push({name:m.userData.gemName, n:rows.length, uThk:thkU,
      chord:st('chord'), od:st('od'), vH:st('vH'), term_vH:st('term_vH'), rawDepthMetric:st('raw'),
      depthMetric:st('dm'), thk:st('thk'),
      fracRawNeg:+(rows.filter(function(r){return r.raw<0;}).length/rows.length).toFixed(3),
      fracRawOver2:+(rows.filter(function(r){return r.raw>2;}).length/rows.length).toFixed(3),
      fracThk0:+(rows.filter(function(r){return r.thk<0.02;}).length/rows.length).toFixed(3),
      fracThk1:+(rows.filter(function(r){return r.thk>0.98;}).length/rows.length).toFixed(3),
      alpha:[0.02,0.25,0.5,0.75,0.98].map(function(t){
        var a=0.14+0.64*t; return {thk:t, aNoFresnel:+a.toFixed(3)};})});
  });
  return out;})()"""

b=Browser(1280,720)
try:
    b.start()
    b.ws.call('Page.navigate', url='http://127.0.0.1:8781/?sky=1&probe=1&data='+DATA)
    ok,dt=b.wait_ready(); print('ready',ok,round(dt,1),flush=True)
    b.ev(PIN); b.ev('CLSky.openCompass(%s)'%json.dumps(HERO)); time.sleep(6); b.wait_settle(30)
    b.ev(POSE % '0.85,0.24,1.00,true'); time.sleep(2.5); b.ev(PIN); time.sleep(1)
    print(json.dumps(b.ev(M), ensure_ascii=False, indent=1))
finally:
    try: b.close()
    except Exception: pass
