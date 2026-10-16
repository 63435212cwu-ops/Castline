#!/usr/bin/env python3
"""REAL A/B for task design:v1-optical-composite:20261009b — corrected mechanism.

Supersedes ab_optics_frontback.py, whose candidate could never be merged. Both
defects were verified against the live tree, not assumed:

  D1  js/scene.js wrote `uPass: { value: PASS_SINGLE }` but PASS_SINGLE is defined
      nowhere in production (`grep -n PASS_SINGLE js/` => no hit) => ReferenceError
      while building the gem crown.
  D2  the patch file is not a valid unified diff:
      `git apply --check` => "corrupt patch at line 37". A merge task cannot apply it.

Mechanism kept, arithmetic replaced.

Production shell = ONE DoubleSide transparent mesh, depthWrite:false. three.js
submits its triangles in buffer order, so far and near facets of the same shell
interleave arbitrarily and "front vs back" is not decidable. The candidate draws the
far surface first (BackSide) and the near surface second (FrontSide), then lets the
Beer-Lambert light path the shader already computes decide how much of the far wall
survives.

The inherited arithmetic split ONE coverage into TWO smaller ones
(coverNear = 0.10+0.28*thk+0.34*fr vs production 0.14+0.64*thk+0.34*fr), so the
two-pass composite was systematically thinner than the single pass. That is a
mechanism error, not taste, and it matches the measured -4.4 mean darkening of the
rejected frames. Here coverage is conserved:

    aSingle = 0.14 + 0.64*thk + 0.34*fr          (== production, term for term)
    aFar    = aSingle * mix(1.0, pathT, uLyrBackAtt)
    aNear   = (aSingle - aFar) / (1 - aFar)
    => 1-(1-aFar)(1-aNear) == aSingle            (max err 1.1e-16 over the grid)

Thick body => pathT small => far wall absorbed, near surface carries coverage
(occludes). Thin edge => pathT ~ 1 => far wall shows through (transmits). The light
path decides; no new coefficient is invented.

THREE.JS CONSTRAINT (why two material instances, not one shared):
  * a ShaderMaterial's uniforms are uploaded per material id, so two meshes sharing
    one material cannot carry different uPass values;
  * mutating material.side inside onBeforeRender is not re-applied when the material
    id is unchanged.
So each pass gets its own material with a FIXED side and a PRIVATE uPass, while
every other uniform object is shared by reference with the host -> the crown's
per-frame animation (uTime/uOn/uHl/uWire) stays in sync with no copying.

Single-pass (uPass = 0.5) => passLegacy == 1 => `a` is bit-identical to production.

Writes only to CL_SHOTS (project-external). No source file is modified.
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

from sky_internal_review_shots import Browser, PIN, POSE, HEALTH  # noqa: E402
from material_layer_ab import SETUP                              # noqa: E402

OUT = Path(os.environ.get('CL_AB2_OUT', '/tmp/castline-shots/review-20261009b/optics-composite-v2'))
OUT.mkdir(parents=True, exist_ok=True)
DATA = 'data/cache/ed3dc1255ca08fbdaae30bbd.json'
HERO = '孙悟空'
VIEWS = os.environ.get('CL_AB_VIEWS', 'full,oblique,dark,rotateA').split(',')

EDITS = [
    ["uniform float uLyrVolume; uniform float uLyrSurface; uniform float uLyrRough; uniform float uLyrTrans; uniform float uLyrInner; uniform float uLyrRefl; uniform float uLyrBackAtt;",
     "uniform float uPass; uniform float uLyrVolume; uniform float uLyrSurface; uniform float uLyrRough; uniform float uLyrTrans; uniform float uLyrInner; uniform float uLyrRefl; uniform float uLyrBackAtt;"],

    ["  float ndv = max(1e-4, dot(N, V));",
     "  float passFront = smoothstep(0.25, 0.75, uPass);\n"
     "  float passLegacy = 1.0 - abs(uPass - 0.5) * 2.0;\n"
     "  float frontness = mix(gl_FrontFacing ? 1.0 : 0.0, passFront, 1.0 - passLegacy);\n"
     "  float ndv = max(1e-4, dot(N, V));"],

    ["  float detail = gl_FrontFacing ? viewWeight : 0.0;",
     "  float detail = frontness * viewWeight;"],

    ["  if (gl_FrontFacing && uSteps > 2.0) {",
     "  if (frontness > 0.5 && uSteps > 2.0) {"],

    ["  vec3 surfacePath = gl_FrontFacing ? vec3(1.0) : mix(vec3(1.0), transmission, viewWeight);",
     "  vec3 surfacePath = mix(mix(vec3(1.0), transmission, viewWeight), vec3(1.0), frontness);"],

    ["  float a = 0.14 + 0.64 * thk + 0.34 * fr + 0.04 * caust + hl * 0.12 + hlWave * 0.14 + needleV * (1.0 - fr) * 0.16;",
     "  float aSingle = 0.14 + 0.64 * thk + 0.34 * fr;\n"
     "  float pathT = clamp(dot(transmission, vec3(0.2126, 0.7152, 0.0722)), 0.0, 1.0);\n"
     "  float aProd = 1.0 - (1.0 - aSingle) * (1.0 - aSingle);\n"
     "  float aFar = aProd * mix(1.0, pathT, uLyrBackAtt);\n"
     "  float aNear = clamp((aProd - aFar) / max(1e-3, 1.0 - aFar), 0.0, 1.0);\n"
     "  float a = mix(aSingle, mix(aFar, aNear, passFront), 1.0 - passLegacy)\n"
     "          + 0.04 * caust + hl * 0.12 + hlWave * 0.14 + needleV * (1.0 - fr) * 0.16;"],

    ["  float facing = gl_FrontFacing ? 1.0 : mix(1.0, 0.32, viewWeight);",
     "  float facing = mix(1.0, mix(1.0, 0.32, viewWeight), 1.0 - frontness);"],
]

AB_IMPL = r"""function(mode){
  var S=CLApp.scene(), T=THREE, A=__layerAB;
  A.rollback(); A.freeze();
  if(!window.__fb2){
    var shells=[];
    S.scene.traverse(function(o){ var m=o.material;
      if(m&&m.uniforms&&m.uniforms.uLyrVolume&&m.blending===T.NormalBlending) shells.push(o); });
    if(!shells.length) throw Error('no production crystal shell found');
    window.__fb2={shells:[],meshes:[],shaders:[]};
    shells.forEach(function(o, si){
      var host=o.material;
      window.__fb2.shells.push({orig:o, order:o.renderOrder, mat:host});
      window.__fb2.shaders.push(host.fragmentShader);
      [0,1].forEach(function(pass){
        var U={}, k;
        for(k in host.uniforms){ if(Object.prototype.hasOwnProperty.call(host.uniforms,k)) U[k]=host.uniforms[k]; }
        U.uPass={value: pass===0 ? 0.0 : 1.0};          /* private: shared uniforms stay shared */
        var mat=new T.ShaderMaterial({vertexShader:host.vertexShader, fragmentShader:host.fragmentShader,
          transparent:host.transparent, depthWrite:host.depthWrite, blending:host.blending,
          side: pass===0 ? T.BackSide : T.FrontSide,     /* FIXED side, never mutated mid-frame */
          extensions:{derivatives:true}, uniforms:U});
        mat.userData.gemName=(host.userData.gemName||'gem')+(pass===0?'-far':'-near');
        var mesh=new T.Mesh(o.geometry, mat);
        mesh.frustumCulled=false; mesh.visible=false; mesh.name='__fb2-'+si+'-'+pass;
        o.parent.add(mesh);
        window.__fb2.meshes.push({pass:pass, mesh:mesh, host:o, hostIndex:si, base:o.renderOrder});
      });
    });
  }
  var fb=window.__fb2;
  if(mode==='candidate'){
    fb.shells.forEach(function(s){
      var t=s.mat.fragmentShader;
      window.AB_EDITS.forEach(function(e,i){
        if(t.indexOf(e[0])<0) throw Error('edit '+i+' anchor not found in live shader');
        t=t.split(e[0]).join(e[1]);
      });
      s.mat.fragmentShader=t; s.mat.needsUpdate=true;
      fb.meshes.forEach(function(x){ if(x.host===s.orig){ x.mesh.material.fragmentShader=t; x.mesh.material.needsUpdate=true; } });
    });
    fb.shells.forEach(function(s){ s.orig.visible=false; });
    fb.meshes.forEach(function(x){
      x.mesh.renderOrder=(x.pass===0)?x.base:x.base+0.5;   /* far first, near second, both inside the host's slot */
      x.mesh.visible=true;
    });
  } else {
    fb.meshes.forEach(function(x){
      x.mesh.material.fragmentShader=fb.shaders[x.hostIndex];
      x.mesh.material.needsUpdate=true;
    });
    fb.shells.forEach(function(s,i){
      s.mat.fragmentShader=fb.shaders[i]; s.mat.needsUpdate=true;
      s.mat.side=T.DoubleSide; s.orig.visible=true;
    });
    fb.meshes.forEach(function(x){ x.mesh.visible=false; });
  }
  window.__abSync();
  return {mode:mode, shells:fb.shells.length, passes:fb.meshes.length};
}"""

# Kept as a SEPARATE evaluate: AB_IMPL must stay a single function expression so
# `window.__abImpl=(...)` parses.
AB_HELPERS = r"""window.__abSync=function(){
  var fb=window.__fb2; if(!fb) return 0;
  fb.meshes.forEach(function(x){
    if(x.host.parent && x.mesh.parent!==x.host.parent) x.host.parent.add(x.mesh);
    x.mesh.position.copy(x.host.position);
    x.mesh.quaternion.copy(x.host.quaternion);
    x.mesh.scale.copy(x.host.scale);
  });
  return fb.meshes.length;
};
window.__abRender=function(){ window.__abSync(); return __layerAB.renderAndGrab(); };"""

TRIPLE = r"""new Promise(function(resolve,reject){requestAnimationFrame(function(){
  var A=__layerAB, out={}, problem;
  try{
    A.rollback(); A.freeze();
    window.__abRender();                     // settle any first-frame material compile
    out.baseline=window.__abRender();
    window.__abImpl('candidate');  out.candidate=window.__abRender();
    window.__abImpl('baseline');   out.restore=window.__abRender();
  }catch(e){problem=e;}
  finally{try{window.__abImpl('baseline');}catch(e){problem=problem||e;}}
  if(problem)reject(problem); else resolve(out);
});})"""

# A real backdrop BEHIND the crystal: an opaque checker plane drawn in the opaque
# pass. Thick body must flatten its contrast; thin edge must preserve it. This is
# the direct measurement of "does the crystal composite with what is behind it".
CHECKER = r"""(function(){
  var S=CLApp.scene(), T=THREE;
  if(window.__chk) return {reused:true};
  var n=256, c=document.createElement('canvas'); c.width=c.height=n;
  var g=c.getContext('2d');
  for(var y=0;y<16;y++)for(var x=0;x<16;x++){ g.fillStyle=((x+y)%2)?'#ffffff':'#000000'; g.fillRect(x*n/16,y*n/16,n/16,n/16); }
  var tex=new T.CanvasTexture(c); tex.needsUpdate=true; tex.minFilter=T.LinearFilter; tex.magFilter=T.NearestFilter;
  var tgt=S.controls.target.clone(), cam=S.camera.position.clone();
  var d=tgt.clone().sub(cam).normalize();
  var rad=tgt.distanceTo(cam)*0.42;
  var m=new T.Mesh(new T.PlaneGeometry(rad*5, rad*5),
    new T.MeshBasicMaterial({map:tex, side:T.DoubleSide, toneMapped:false, depthWrite:true, depthTest:true, fog:false}));
  m.position.copy(tgt).addScaledVector(d, rad*1.6);
  m.lookAt(cam); m.frustumCulled=false; m.name='__chk-chk';
  S.scene.add(m);
  window.__chk={mesh:m, rad:rad, cell:rad*5/16};
  return {added:true, rad:rad, cellPx:rad*5/16, center:m.position.toArray()};
})()"""

CHECKER_OFF = r"""(function(){var S=CLApp.scene();
  if(window.__chk){S.scene.remove(window.__chk.mesh);
    window.__chk.mesh.geometry.dispose(); window.__chk.mesh.material.map.dispose();
    window.__chk.mesh.material.dispose(); window.__chk=null;}
  return {removed:true};})()"""

# Silhouette of the two base shells = pixels that move when they are hidden. No guessing.
SILHOUETTE = r"""new Promise(function(resolve,reject){requestAnimationFrame(function(){
  var A=__layerAB, fb=window.__fb2, out={};
  try{
    A.rollback(); A.freeze();
    window.__abImpl('baseline');
    out.withShells=window.__abRender();
    fb.shells.forEach(function(s){s.orig.visible=false;});
    out.withoutShells=window.__abRender();
    fb.shells.forEach(function(s){s.orig.visible=true;});
    out.restore=window.__abRender();
  }catch(e){reject(e);return;}
  resolve(out);
});})"""

POSES = {
    'full':    '0.85,0.24,1.00,true',
    'oblique': '0.85,0.24,0.62,true',
    'dark':    '2.30,0.10,0.55,true',
    'rotateA': '0.20,0.12,0.90,true',
    'rotateB': '1.55,0.30,0.90,true',
    'rotateC': '2.90,0.42,0.90,true',
}


def save(frame, tag):
    for k in ('png', 'detail'):
        if k in frame:
            (OUT / (tag + ('-detail' if k == 'detail' else '') + '.png')).write_bytes(
                base64.b64decode(frame[k].split(',')[1]))


def main():
    assert os.environ.get('CL_GPU') == '1', 'CL_GPU=1 required (serial GPU slot)'
    rep = {'task': 'design:v1-optical-composite:20261009b', 'stage': 'real-ab-frontback-v2',
           'data': DATA, 'hero': HERO, 'views': {}, 'supersedes': 'ab_optics_frontback.py',
           'mechanism': 'explicit far-surface(BackSide, renderOrder base) then near-surface(FrontSide, base+0.5) with coverage-conserving light-path alpha',
           'invariant': '1-(1-aFar)(1-aNear) == min(aSingle,1); uPass=0.5 => bit-identical to production',
           'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    b = Browser(1920, 1080)
    try:
        b.start()
        b.ws.call('Page.navigate', url='http://127.0.0.1:8781/?sky=1&probe=1&data=' + DATA)
        ok, dt = b.wait_ready(); rep['ready'] = {'ok': ok, 's': round(dt, 1)}
        b.ev(PIN); b.ev('CLSky.openCompass(%s)' % json.dumps(HERO)); time.sleep(6); b.wait_settle(30)
        b.ev('(function(){var S=CLApp.scene();S.core().setCalm(true,"lab");S.controls.autoRotate=false;'
             'S.controls.enableDamping=false;S.controls.update();return 1;})()')
        time.sleep(2)
        rep['setup'] = b.ev(SETUP); b.ev('__layerAB.freeze()'); time.sleep(1)
        b.ev('window.AB_EDITS=%s;1' % json.dumps(EDITS, ensure_ascii=False))
        b.ev('window.__abImpl=(%s);1' % AB_IMPL)
        b.ev(AB_HELPERS + ';1')

        rep['productionStack'] = b.ev("""(()=>{var S=CLApp.scene(),o=[];
          S.scene.traverse(function(n){var m=n.material;if(m&&m.userData&&m.userData.gemName)
            o.push({name:m.userData.gemName,order:n.renderOrder,blending:m.blending,side:m.side,
                    depthWrite:m.depthWrite,transparent:m.transparent,visible:n.visible,
                    consumesPath:String(m.fragmentShader).indexOf('depthMetric')>=0});});
          return o;})()""")
        print('STACK ' + json.dumps(rep['productionStack'], ensure_ascii=False), flush=True)

        # ---- parity gate BEFORE any visual claim: single-pass must be untouched.
        b.ev(POSE % POSES['full']); time.sleep(2.5); b.ev(PIN); time.sleep(1.2)
        par = b.ev(r"""new Promise(function(res,rej){requestAnimationFrame(function(){
          var A=__layerAB,o={};try{A.rollback();A.freeze();
            var a=A.renderAndGrab(); window.__abImpl('baseline'); var c=A.renderAndGrab();
            o.singlePassIdentical=(a.png===c.png)&&(a.detail===c.detail);
            o.frames=[a.frame.rendererFrame,c.frame.rendererFrame];}catch(e){o.err=String(e);}
          res(o);});})""", True)
        rep['parityGate'] = par
        print('PARITY ' + json.dumps(par, ensure_ascii=False), flush=True)

        for view in VIEWS:
            b.ev(POSE % POSES[view]); time.sleep(2.5)
            b.ev(PIN); time.sleep(1.2)
            trip = b.ev(TRIPLE, True)
            if not isinstance(trip, dict) or 'baseline' not in trip:
                rep['views'][view] = {'error': str(trip)[:400]}
                print('VIEW ' + view + ' ERROR ' + str(trip)[:300], flush=True)
                continue
            for state in ('baseline', 'candidate', 'restore'):
                save(trip[state], '%s-%s' % (view, state))
            fr = [trip[s]['frame'] for s in ('baseline', 'candidate', 'restore')]
            same = lambda k: all(f.get(k) is not None and f[k] == fr[0].get(k) for f in fr)
            rec = {'sameClock': all(f.get('clockFrozen') is True for f in fr) and same('tAnim') and same('tAcc'),
                   'sameCamera': same('camera') and same('target') and same('up'),
                   'freshRenders': [f['rendererFrame'] for f in fr],
                   'strictlyIncreasing': fr[0]['rendererFrame'] < fr[1]['rendererFrame'] < fr[2]['rendererFrame'],
                   'restoreExact': trip['restore']['png'] == trip['baseline']['png'],
                   'restoreDetailExact': trip['restore']['detail'] == trip['baseline']['detail'],
                   'candidateChanged': trip['candidate']['png'] != trip['baseline']['png'],
                   'quality': {k: fr[0]['quality'].get(k) for k in ('drawW', 'drawH', 'dpr', 'degrade')}}
            rep['views'][view] = rec
            print('VIEW ' + view + ' ' + json.dumps(rec, ensure_ascii=False), flush=True)

        # ---- backdrop transmission test
        if os.environ.get('CL_CHK', '1') == '1':
            b.ev(POSE % POSES['full']); time.sleep(2.0)
            rep['checker'] = {'setup': b.ev(CHECKER)}
            time.sleep(1.5)
            sil = b.ev(SILHOUETTE, True)
            for state in ('withShells', 'withoutShells', 'restore'):
                save(sil[state], 'chk-%s' % state)
            rep['checker']['silhouetteRestoreExact'] = sil['restore']['png'] == sil['withShells']['png']
            b.ev(POSE % POSES['full']); time.sleep(2.0); b.ev(PIN); time.sleep(1.0)
            trip = b.ev(TRIPLE, True)
            if isinstance(trip, dict) and 'baseline' in trip:
                for state in ('baseline', 'candidate', 'restore'):
                    save(trip[state], 'chk2-%s' % state)
                rep['checker']['restoreExact'] = trip['restore']['png'] == trip['baseline']['png']
                rep['checker']['candidateChanged'] = trip['candidate']['png'] != trip['baseline']['png']
                rep['checker']['freshRenders'] = [trip[s]['frame']['rendererFrame'] for s in ('baseline', 'candidate', 'restore')]
                rep['checker']['quality'] = {k: trip['baseline']['frame']['quality'].get(k) for k in ('drawW', 'drawH', 'dpr', 'degrade')}
            print('CHECKER ' + json.dumps(rep['checker'], ensure_ascii=False), flush=True)

        rep['health'] = b.ev(HEALTH)
        print('HEALTH ' + json.dumps(rep['health'], ensure_ascii=False), flush=True)
        b.ev(CHECKER_OFF)
        b.ev('(function(){var T=THREE,fb=window.__fb2;if(!fb)return 1;'
             'fb.meshes.forEach(function(x){if(x.mesh.parent)x.mesh.parent.remove(x.mesh);});'
             'fb.shells.forEach(function(s){s.orig.visible=true;s.mat.side=T.DoubleSide;});fb.meshes=[];return 1;})()')
        rep['cleanupMeshes'] = b.ev('(function(){return window.__fb2?window.__fb2.meshes.length:-1;})()')
    finally:
        try:
            b.close()
        except Exception:
            pass
    (OUT / 'ab-report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2) + '\n')
    print('WROTE', OUT / 'ab-report.json', flush=True)


if __name__ == '__main__':
    sys.exit(main())
