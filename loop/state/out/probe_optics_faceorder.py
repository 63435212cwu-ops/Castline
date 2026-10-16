#!/usr/bin/env python3
"""DIAGNOSTIC ONLY (task design:v1-optical-composite:20261009b) — probe 2 (corrected).

Two questions, answered from real pixels and real shader intermediates:

  Q1  Does the production double-sided single-pass compositing of the two
      NormalBlending crown shells draw BACK faces after FRONT faces?
      (If yes, that is a structural cause of "front and back are
      indistinguishable" that no alpha/normal parameter can fix.)

  Q2  What is the actual numeric range of the thickness term the shader uses,
      i.e. does `depthMetric` carry ray-path information or just height?

Method discipline (same as tests/material_layer_ab.py PAIR): every state is
rendered inside ONE synchronous block, so no animation tick can occur between
states. Nothing is written to the source tree.
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

OUT = Path('/tmp/castline-shots/review-20261009b/optics-composite-2')
OUT.mkdir(parents=True, exist_ok=True)
DATA = 'data/cache/ed3dc1255ca08fbdaae30bbd.json'
HERO = '孙悟空'

BACKDROP = r"""(()=>{
  var S=CLApp.scene(), T=THREE;
  var cv=document.createElement('canvas'); cv.width=512; cv.height=512;
  var c=cv.getContext('2d');
  for(var y=0;y<512;y+=16) for(var x=0;x<512;x+=16){
    var on=((x/16)+(y/16))%2===0;
    c.fillStyle= on? 'rgb(0,0,0)' : 'rgb(255,255,255)';
    c.fillRect(x,y,16,16);
  }
  var tex=new T.CanvasTexture(cv); tex.magFilter=T.NearestFilter; tex.minFilter=T.NearestFilter;
  var mat=new T.MeshBasicMaterial({map:tex, side:T.DoubleSide, fog:false, toneMapped:false});
  var mesh=new T.Mesh(new T.PlaneGeometry(3000,3000), mat); mesh.name='__probeBackdrop2';
  var cen=new T.Vector3();
  S.scene.traverse(function(o){ if(o.material&&o.material.userData&&o.material.userData.gemName&&o.material.blending===THREE.NormalBlending) o.getWorldPosition(cen); });
  var cam=S.camera, dir=new T.Vector3(); cam.getWorldDirection(dir);
  mesh.position.copy(cen).addScaledVector(dir, 700);
  mesh.lookAt(cam.position); mesh.updateMatrixWorld(true);
  S.scene.add(mesh); window.__bd2=mesh;
  return {center:cen.toArray().map(function(v){return +v.toFixed(1);})};
})()"""

# Build the split passes once (structural, no pixels produced yet).
SPLIT = r"""(()=>{
  var S=CLApp.scene(), T=THREE;
  var gems=[]; S.scene.traverse(function(o){ if(o.material&&o.material.userData&&o.material.userData.gemName) gems.push(o); });
  var shells=gems.filter(function(o){ return o.material.blending===T.NormalBlending; });
  window.__split=[];
  shells.forEach(function(o){
    var m=o.material, holder={orig:o, baseOrder:o.renderOrder, meshes:[]};
    ['back','front'].forEach(function(which){
      var mesh=new T.Mesh(o.geometry, m);
      mesh.frustumCulled=false; mesh.visible=false;
      mesh.name='__facepass-'+which+'-'+(m.userData.gemName||'');
      mesh.position.copy(o.position); mesh.quaternion.copy(o.quaternion); mesh.scale.copy(o.scale);
      mesh.onBeforeRender=function(){ m.side = (which==='back') ? T.BackSide : T.FrontSide; };
      o.parent.add(mesh); holder.meshes.push({which:which, mesh:mesh});
    });
    window.__split.push(holder);
  });
  return {shells:shells.map(function(o){return {name:o.material.userData.gemName, order:o.renderOrder};}),
          meshes:window.__split.reduce(function(a,h){return a+h.meshes.length;},0)};
})()"""

# ONE synchronous block: 5 states, no rAF yield between them.
SWEEP = r"""(function(){
  var T=THREE, A=__layerAB, sp=window.__split||[], i;
  A.rollback(); A.freeze();
  // remember the production renderOrder of every non-base crystal layer so the
  // additive / core / ghost stack keeps its relative order in both modes.
  var gems=[]; A.S.scene.traverse(function(o){ if(o.material&&o.material.userData&&o.material.userData.gemName) gems.push(o); });
  var others=gems.filter(function(o){ return o.material.blending!==T.NormalBlending; });
  var savedOthers=others.map(function(o){return o.renderOrder;});
  var maxBase=0; sp.forEach(function(h){ maxBase=Math.max(maxBase,h.baseOrder); });

  function setMode(mode){
    sp.forEach(function(h){
      var o=h.orig;
      if(mode==='baseline'){ o.visible=true; o.material.side=T.DoubleSide;
        h.meshes.forEach(function(x){x.mesh.visible=false;}); }
      else { o.visible=false;
        h.meshes.forEach(function(x){ x.mesh.visible=true;
          var back=(x.which==='back');
          x.mesh.renderOrder = (mode==='candidate') ? (back?h.baseOrder:h.baseOrder+1)
                                                    : (back?h.baseOrder+1:h.baseOrder); }); }
    });
    others.forEach(function(o,k){ o.renderOrder = (mode==='baseline') ? savedOthers[k] : savedOthers[k]+1; });
  }
  function pull(tag){ var f=A.renderAndGrab(); return {tag:tag, png:f.png, detail:f.detail,
    frame:{tAnim:f.frame.tAnim, rendererFrame:f.frame.rendererFrame, coreFrame:f.frame.coreFrame,
           clockFrozen:f.frame.clockFrozen, camera:f.frame.camera}}; }

  var frames=[];
  setMode('baseline');   frames.push(pull('baseline'));
  setMode('candidate');  frames.push(pull('candidate'));
  setMode('negative');   frames.push(pull('negative'));
  setMode('baseline');   frames.push(pull('baseline-restore'));
  setMode('candidate');  frames.push(pull('candidate-repeat'));
  setMode('baseline');
  var finalRestore=pull('restore-final');
  return {frames:frames, finalRestore:finalRestore,
          allSameClock:frames.concat([finalRestore]).every(function(f){return f.frame.clockFrozen===true;}),
          sameTAnim:frames.concat([finalRestore]).every(function(f){return f.frame.tAnim===frames[0].frame.tAnim;}),
          restoreExact:finalRestore.png===frames[0].png,
          baselineRepeatExact:frames[3].png===frames[0].png,
          candidateRepeatExact:frames[4].png===frames[1].png};
})()"""

# Q2: sample the shader's own intermediates by re-deriving them in JS with the
# exact production formulas and the exact production uniforms, over the real
# vertex set of the crown geometry. This is arithmetic on real values, not a
# re-implementation guess: every constant is read from the live material.
MEASURE = r"""(()=>{
  var S=CLApp.scene(), T=THREE, out={};
  var shell=null;
  S.scene.traverse(function(o){ if(!shell&&o.material&&o.material.uniforms&&o.material.uniforms.uLyrVolume) shell=o; });
  if(!shell) return {error:'no CROWN_BASE_FS shell'};
  var u=shell.material.uniforms;
  var camL=u.uCamL.value, cen=u.uCen.value, rad=u.uRad.value, thk=u.uThk.value;
  S.camera.updateMatrixWorld(); shell.updateMatrixWorld(true);
  var inv=new T.Matrix4().copy(shell.matrixWorld).invert();
  var camLocal=camL.clone ? camL.clone() : new T.Vector3();
  var pos=shell.geometry.attributes.position, n=pos.count;
  var samples=[], dst=new T.Vector3(), Vl=new T.Vector3(), eo=new T.Vector3(), ed3=new T.Vector3();
  var stride=Math.max(1,Math.floor(n/400));
  for(var i=0;i<n;i+=stride){
    dst.fromBufferAttribute(pos,i);
    Vl.copy(dst).sub(camLocal); Vl.normalize();
    eo.copy(dst).sub(cen).divide(rad);
    ed3.copy(Vl).divide(rad);
    var qb=eo.dot(ed3), qa=Math.max(1e-5,ed3.dot(ed3)), qc=eo.dot(eo)-1.0;
    var qd=qb*qb-qa*qc;
    var chord= qd>0 ? Math.sqrt(qd)*2.0/qa : 0.0;
    var opticalDepth=Math.max(chord*thk,0.0);
    var vH=pos.getY(i);
    var depthMetric=Math.min(2.0, Math.max(0.0,(opticalDepth+vH*0.40)*u.uLyrVolume.value));
    samples.push({chord:+chord.toFixed(4), opticalDepth:+opticalDepth.toFixed(5), vH:+vH.toFixed(4),
                  depthMetric:+depthMetric.toFixed(4), thk:Math.min(1,Math.max(0,depthMetric))});
  }
  function stat(key){ var v=samples.map(function(s){return s[key];}).sort(function(a,b){return a-b;});
    return {min:v[0], p05:v[Math.floor(v.length*0.05)], med:v[Math.floor(v.length*0.5)],
            p95:v[Math.floor(v.length*0.95)], max:v[v.length-1]}; }
  out.samples=samples.length;
  out.chord=stat('chord'); out.opticalDepth=stat('opticalDepth'); out.vH=stat('vH');
  out.depthMetric=stat('depthMetric'); out.thk=stat('thk');
  // How much of depthMetric is ray path vs height?
  var num=samples.reduce(function(a,s){return a+s.opticalDepth;},0);
  var den=samples.reduce(function(a,s){return a+s.opticalDepth+Math.max(0,s.vH*0.40);},0);
  out.pathShare=+(num/den).toFixed(4);
  out.uniforms={uThk:thk, uLyrVolume:u.uLyrVolume.value, uAbs:+u.uAbs.value.toFixed(3),
                uLyrTrans:u.uLyrTrans.value, uLyrBackAtt:u.uLyrBackAtt.value,
                rad:rad.toArray(), cen:cen.toArray(), camL:camL.toArray()};
  return out;
})()"""


def save(frame, tag):
    for k in ('png', 'detail'):
        if k in frame:
            p = OUT / (tag + ('-detail' if k == 'detail' else '') + '.png')
            p.write_bytes(base64.b64decode(frame[k].split(',')[1]))


def main():
    assert os.environ.get('CL_GPU') == '1'
    rep = {'task': 'design:v1-optical-composite:20261009b', 'stage': 'probe2-face-order-corrected',
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
        b.ev(PIN); time.sleep(1.5)

        rep['measure'] = b.ev(MEASURE)
        print('MEASURE ' + json.dumps(rep['measure'], ensure_ascii=False), flush=True)

        rep['backdrop'] = b.ev(BACKDROP)
        rep['split'] = b.ev(SPLIT)
        print('SPLIT ' + json.dumps(rep['split'], ensure_ascii=False), flush=True)

        # reference: backdrop visible, no crystal -> contrast ceiling
        b.ev("(function(){var S=CLApp.scene();window.__allG=[];S.scene.traverse(function(o){"
             "if(o.material&&o.material.userData&&o.material.userData.gemName){window.__allG.push([o,o.visible]);o.visible=false;}});return 1;})()")
        ref = b.ev('__layerAB.renderAndGrab()'); save(ref, 'ref-nocrystal')
        b.ev("(function(){window.__allG.forEach(function(p){p[0].visible=p[1];});return 1;})()")

        sweep = b.ev(SWEEP)
        for f in sweep['frames']:
            save(f, 'sweep-' + f['tag'])
        save(sweep['finalRestore'], 'sweep-restore-final')
        rep['sweep'] = {'tags': [f['tag'] for f in sweep['frames']],
                        'frames': [f['frame'] for f in sweep['frames']],
                        'allSameClock': sweep['allSameClock'], 'sameTAnim': sweep['sameTAnim'],
                        'restoreExact': sweep['restoreExact'],
                        'baselineRepeatExact': sweep['baselineRepeatExact'],
                        'candidateRepeatExact': sweep['candidateRepeatExact'],
                        'refFrame': ref['frame']['rendererFrame'],
                        'finalRestoreFrame': sweep['finalRestore']['frame']['rendererFrame']}
        print('SWEEP ' + json.dumps({k: v for k, v in rep['sweep'].items() if k != 'frames'}, ensure_ascii=False), flush=True)

        # cleanup
        b.ev("(function(){var T=THREE,sp=window.__split||[];sp.forEach(function(h){h.meshes.forEach(function(x){"
             "if(x.mesh.parent)x.mesh.parent.remove(x.mesh);});h.orig.visible=true;h.orig.material.side=T.DoubleSide;});"
             "window.__split=null;var S=CLApp.scene();if(window.__bd2){S.scene.remove(window.__bd2);window.__bd2=null;}return 1;})()")
        rep['health'] = b.ev(HEALTH)
        rep['quality'] = b.ev('CLApp.scene().quality()')
    finally:
        try:
            b.close()
        except Exception:
            pass
    (OUT / 'probe2-report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2) + '\n')
    print('WROTE', OUT / 'probe2-report.json', flush=True)


if __name__ == '__main__':
    sys.exit(main())
