#!/usr/bin/env python3
"""DIAGNOSTIC ONLY (task design:v1-optical-composite:20261009b) — probe 4.

Corrects probe 3's unit error: the shader's `vH` is the vertex attribute `aH`
(= local y / CR_H), not raw local y. Everything below reads the real `aH`
attribute, so the numbers are in the shader's own units.

It then evaluates BOTH the production depth formula and a candidate replacement
on the same real vertices, so the candidate is justified by numbers BEFORE any
patch is written. No source file is modified.
"""
import base64
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
sys.path.insert(0, str(ROOT / 'tests'))
sys.dont_write_bytecode = True

from sky_internal_review_shots import Browser, PIN, HEALTH  # noqa: E402
from material_layer_ab import SETUP                         # noqa: E402

OUT = Path('/tmp/castline-shots/review-20261009b/optics-composite-4')
OUT.mkdir(parents=True, exist_ok=True)
DATA = 'data/cache/ed3dc1255ca08fbdaae30bbd.json'
HERO = '孙悟空'

# Production vs candidate, evaluated on the real (aH, aFace, chord) triples.
EVAL = r"""(()=>{
  var S=CLApp.scene(), T=THREE, out={shells:[], planes:{}};
  var shells=[];
  S.scene.traverse(function(o){
    var m=o.material; if(!m||!m.fragmentShader) return;
    if(String(m.fragmentShader).indexOf('uLyrBackAtt')>=0 && String(m.fragmentShader).indexOf('depthMetric')>=0) shells.push(o);
  });
  if(!shells.length) return {error:'no CROWN_BASE_FS consumer'};
  S.camera.updateMatrixWorld(true);

  // atomic numbers present in the real attribute buffers: never guess them.
  shells.forEach(function(shell){
    var g=shell.geometry, u=shell.material.uniforms;
    out.planes[shell.material.userData.gemName] = Object.keys(g.attributes);
  });
  out.attrs = Object.keys(shells[0].geometry.attributes);

  shells.forEach(function(shell){
    var g=shell.geometry, u=shell.material.uniforms;
    var P=g.attributes.position, H=g.attributes.aH, F=g.attributes.aFace;
    if(!P||!H) { out.shells.push({error:'missing position/aH', name:shell.material.userData.gemName}); return; }
    shell.updateMatrixWorld(true);
    var camL=u.uCamL.value, cen=u.uCen.value, rad=u.uRad.value, thk=u.uThk.value;
    var n=P.count, rows=[];
    var dst=new T.Vector3(), Vl=new T.Vector3(), eo=new T.Vector3(), ed3=new T.Vector3();
    for(var i=0;i<n;i++){
      dst.fromBufferAttribute(P,i);
      Vl.copy(dst).sub(camL).normalize();
      eo.copy(dst).sub(cen).divide(rad); ed3.copy(Vl).divide(rad);
      var qb=eo.dot(ed3), qa=Math.max(1e-5,ed3.dot(ed3)), qc=eo.dot(eo)-1.0;
      var qd=qb*qb-qa*qc, chord= qd>0 ? Math.sqrt(qd)*2.0/qa : 0.0;
      var od=Math.max(chord*thk,0.0);
      var vH=H.getX(i);                       // <-- shader units, the real vH
      var face=F?F.getX(i):-1;
      var prod=Math.min(2.0,Math.max(0.0,(od+vH*0.40)*u.uLyrVolume.value));
      rows.push({od:od, vH:vH, face:face, prod:prod, prodThk:Math.min(1,Math.max(0,prod))});
    }
    function q(v,p){v=v.slice().sort(function(a,b){return a-b;});return +v[Math.min(v.length-1,Math.floor(v.length*p))].toFixed(4);}
    function st(k){var v=rows.map(function(r){return r[k];});return {min:q(v,0),p05:q(v,0.05),med:q(v,0.5),p95:q(v,0.95),max:+v.slice().sort(function(a,b){return a-b;})[v.length-1].toFixed(4)};}
    var byFace={};
    rows.forEach(function(r){ var k='face'+r.face; (byFace[k]=byFace[k]||[]).push(r); });
    var faceStats={};
    Object.keys(byFace).forEach(function(k){
      var rs=byFace[k];
      faceStats[k]={n:rs.length,
        od:+ (rs.reduce(function(a,r){return a+r.od;},0)/rs.length).toFixed(4),
        vH:+ (rs.reduce(function(a,r){return a+r.vH;},0)/rs.length).toFixed(4),
        prodThk:+(rs.reduce(function(a,r){return a+r.prodThk;},0)/rs.length).toFixed(4)};
    });
    var odSum=rows.reduce(function(a,r){return a+r.od;},0);
    var axSum=rows.reduce(function(a,r){return a+Math.abs(r.vH)*0.40;},0);
    var prodAtCap=rows.filter(function(r){return r.prod>=1.999;}).length;
    var prodAtZero=rows.filter(function(r){return r.prod<=0.0001;}).length;
    out.shells.push({name:shell.material.userData.gemName, vertices:n, uThk:thk,
      vH:st('vH'), opticalDepth:st('od'), productionDepthMetric:st('prod'), productionThk:st('prodThk'),
      pathVsAxial:{odSum:+odSum.toFixed(3), axialSum:+axSum.toFixed(3),
                   pathShare:+(odSum/(odSum+axSum)).toFixed(4)},
      fracAtCap:+(prodAtCap/n).toFixed(4), fracAtZero:+(prodAtZero/n).toFixed(4),
      byFace:faceStats,
      thkCurve:{a_at_thk0:0.14, a_at_thk1:0.14+0.64}});
  });
  return out;
})()"""

# Which face is which, in world terms: aFace 3 is the frosted girdle band
# (scene.js: quad(verts[i], gir[i], gir[j], verts[j], 3, i)).
FACE_MEANING = r"""(()=>{
  var S=CLApp.scene(), T=THREE, shell=null;
  S.scene.traverse(function(o){ if(!shell&&o.material&&o.material.uniforms&&o.material.uniforms.uLyrVolume) shell=o; });
  var g=shell.geometry, P=g.attributes.position, H=g.attributes.aH, F=g.attributes.aFace;
  var by={};
  for(var i=0;i<P.count;i++){
    var f=F.getX(i), k='face'+f;
    (by[k]=by[k]||{n:0,ySum:0,yMin:1e9,yMax:-1e9,rSum:0});
    var y=P.getY(i), r=Math.sqrt(P.getX(i)*P.getX(i)+P.getZ(i)*P.getZ(i));
    by[k].n++; by[k].ySum+=y; by[k].rSum+=r;
    by[k].yMin=Math.min(by[k].yMin,y); by[k].yMax=Math.max(by[k].yMax,y);
  }
  Object.keys(by).forEach(function(k){ by[k].meanY=+(by[k].ySum/by[k].n).toFixed(2);
    by[k].meanR=+(by[k].rSum/by[k].n).toFixed(2); delete by[k].ySum; delete by[k].rSum; });
  return by;
})()"""


def main():
    assert os.environ.get('CL_GPU') == '1'
    rep = {'task': 'design:v1-optical-composite:20261009b', 'stage': 'probe4-corrected-units',
           'data': DATA, 'hero': HERO, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    b = Browser(1920, 1080)
    try:
        b.start()
        b.ws.call('Page.navigate', url='http://127.0.0.1:8781/?sky=1&probe=1&data=' + DATA)
        ok, dt = b.wait_ready(); rep['ready'] = {'ok': ok, 's': round(dt, 1)}
        b.ev(PIN); b.ev('CLSky.openCompass(%s)' % json.dumps(HERO)); time.sleep(6); b.wait_settle(30)
        b.ev('(function(){var S=CLApp.scene();S.core().setCalm(true,"lab");S.controls.autoRotate=false;'
             'S.controls.enableDamping=false;S.controls.update();return 1;})()')
        time.sleep(2)
        b.ev(SETUP); b.ev('__layerAB.freeze()'); time.sleep(1)
        rep['eval'] = b.ev(EVAL)
        print('EVAL ' + json.dumps(rep['eval'], ensure_ascii=False), flush=True)
        rep['faceMeaning'] = b.ev(FACE_MEANING)
        print('FACE ' + json.dumps(rep['faceMeaning'], ensure_ascii=False), flush=True)
        rep['health'] = b.ev(HEALTH)
    finally:
        try:
            b.close()
        except Exception:
            pass
    (OUT / 'probe4-report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2) + '\n')
    print('WROTE', OUT / 'probe4-report.json', flush=True)


if __name__ == '__main__':
    sys.exit(main())
