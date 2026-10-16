#!/usr/bin/env python3
"""ROOT-CAUSE PROBE for design:v1-optical-composite:20261009b (corrected).

WHY THIS EXISTS
  The first probe measured `position.y` and called it vH. That is WRONG: the shader's
  `vH` varying is fed from the `aH` vertex attribute (CROWN_VS: `vH = aH;`), which is a
  normalised height, not the geometry's y. Any conclusion drawn from position.y about
  `depthMetric` / `thk` is therefore void. This probe reads the REAL attribute.

WHAT IT MEASURES (all from the live page, production values only, read-only)
  For each material that actually consumes the thickness path:
    chord, opticalDepth, the vH term, the raw depthMetric, and the clamped
    depthMetric / thk -- plus how much of the surface sits at the clamp.
  Then the resulting alpha curve, so the claim "the alpha formula cannot occlude"
  is arithmetic over measured inputs rather than an opinion.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
sys.path.insert(0, str(ROOT / 'tests'))
sys.dont_write_bytecode = True

from sky_internal_review_shots import Browser, PIN, POSE  # noqa: E402

DATA = 'data/cache/ed3dc1255ca08fbdaae30bbd.json'
HERO = '孙悟空'

M = r"""(()=>{
  var S=CLApp.scene(), T=THREE, out=[];
  S.camera.updateMatrixWorld(true);
  S.scene.traverse(function(o){
    var m=o.material;
    if(!m||!m.fragmentShader) return;
    if(String(m.fragmentShader).indexOf('depthMetric')<0) return;
    if(m.blending!==T.NormalBlending) return;          /* the absorbing shell, not the additive fire */
    var u=m.uniforms, pos=o.geometry.attributes.position, aH=o.geometry.attributes.aH;
    if(!aH) { out.push({name:m.userData.gemName, error:'no aH attribute'}); return; }
    var camL=u.uCamL.value, cen=u.uCen.value, rad=u.uRad.value, thkU=u.uThk.value, vol=u.uLyrVolume.value;
    var dst=new T.Vector3(), Vl=new T.Vector3(), eo=new T.Vector3(), ed3=new T.Vector3();
    var rows=[], stride=Math.max(1,Math.floor(pos.count/1200));
    for(var i=0;i<pos.count;i+=stride){
      dst.fromBufferAttribute(pos,i);
      Vl.copy(dst).sub(camL).normalize();
      eo.copy(dst).sub(cen).divide(rad); ed3.copy(Vl).divide(rad);
      var qb=eo.dot(ed3), qa=Math.max(1e-5,ed3.dot(ed3)), qc=eo.dot(eo)-1.0;
      var qd=qb*qb-qa*qc, chord= qd>0 ? Math.sqrt(qd)*2.0/qa : 0.0;
      var od=Math.max(chord*thkU,0.0);
      var vH=aH.getX(i);                                /* THE REAL vH, not position.y */
      var raw=(od+vH*0.40)*vol;
      var dm=Math.min(2.0,Math.max(0.0,raw));
      rows.push({chord:chord, od:od, vH:vH, vHterm:vH*0.40, raw:raw, dm:dm, thk:Math.min(1.0,dm)});
    }
    function st(k){var v=rows.map(function(r){return r[k];}).sort(function(a,b){return a-b;});
      var q=function(p){return +v[Math.min(v.length-1,Math.floor(v.length*p))].toFixed(4);};
      return {min:+v[0].toFixed(4),p05:q(.05),med:q(.5),p95:q(.95),max:+v[v.length-1].toFixed(4)};}
    var n=rows.length;
    var f=function(pred){return +(rows.filter(pred).length/n).toFixed(3);};
    out.push({name:m.userData.gemName, n:n, uThk:thkU, uLyrVolume:vol, uAbs:u.uAbs.value,
      chord:st('chord'), opticalDepth:st('od'), vH:st('vH'), vHterm:st('vHterm'),
      rawDepthMetric:st('raw'), depthMetric:st('dm'), thk:st('thk'),
      frac_raw_negative:  f(function(r){return r.raw<0;}),
      frac_raw_above_2:   f(function(r){return r.raw>2;}),
      frac_thk_zero:      f(function(r){return r.thk<0.02;}),
      frac_thk_one:       f(function(r){return r.thk>0.98;}),
      /* production alpha at the two extremes of fr (Fresnel term), no other contributions */
      alpha_ceiling: {at_thk1_fr0:+(0.14+0.64*1+0.34*0).toFixed(3),
                      at_thk1_fr1:+(0.14+0.64*1+0.34*1).toFixed(3),
                      at_thk_med:+(0.14+0.64*st('thk').med+0.34*0.0).toFixed(3)}});
  });
  return out;})()"""


def main():
    assert os.environ.get('CL_GPU') == '1'
    rep = {'task': 'design:v1-optical-composite:20261009b', 'stage': 'rootcause-real-vH',
           'note': 'vH read from the aH attribute (CROWN_VS: vH = aH); NOT position.y',
           'data': DATA, 'hero': HERO,
           'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    b = Browser(1280, 720)
    try:
        b.start()
        b.ws.call('Page.navigate', url='http://127.0.0.1:8781/?sky=1&probe=1&data=' + DATA)
        ok, dt = b.wait_ready(); rep['ready'] = {'ok': ok, 's': round(dt, 1)}
        b.ev(PIN); b.ev('CLSky.openCompass(%s)' % json.dumps(HERO)); time.sleep(6); b.wait_settle(30)
        b.ev(POSE % '0.85,0.24,1.00,true'); time.sleep(2.5); b.ev(PIN); time.sleep(1)
        rep['shells'] = b.ev(M)
    finally:
        try:
            b.close()
        except Exception:
            pass
    out = Path('/tmp/castline-artifacts/review-20261009b/rootcause-vH.json')
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    print('WROTE', out)


if __name__ == '__main__':
    sys.exit(main())
