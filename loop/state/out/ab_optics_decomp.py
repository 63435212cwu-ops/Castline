#!/usr/bin/env python3
"""DECOMPOSITION A/B for task design:v1-optical-composite:20261009b.

The front/back candidate bundles two changes. This run separates them so the
report can state which one actually produces the visible result:

  baseline   production: one DoubleSide pass, legacy alpha
  order-only split into BackSide(1) + FrontSide(2) but uPass left at 0.5, so the
             shader's `frontness` still falls back to gl_FrontFacing and the
             legacy alpha formula is used verbatim. => isolates DRAW ORDER alone.
  path-only  one DoubleSide pass (no split), but uPass driven from gl_FrontFacing
             through a tiny injected variant is not possible without splitting,
             so this arm instead evaluates the new alpha formula with the real
             pass identity taken from the geometry: uPass is set per-triangle via
             the existing gl_FrontFacing by forcing uPass = 0.5 and reading the
             new formula's `pathT` term only through `transmission`, i.e. the
             BackAtt replacement is applied on the single pass.
  full       split order + new path alpha (the real candidate)

All states are rendered inside ONE synchronous block; restore must be pixel-exact.
Writes only to CL_SHOTS (project-external).
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

OUT = Path('/tmp/castline-shots/review-20261009b/optics-composite-decomp')
OUT.mkdir(parents=True, exist_ok=True)
DATA = 'data/cache/ed3dc1255ca08fbdaae30bbd.json'
HERO = '孙悟空'
VIEWS = os.environ.get('CL_AB_VIEWS', 'full,oblique,dark').split(',')

# Same edit list as the real candidate, but the alpha/backatt edits are optional
# so the "order-only" arm can use the draw-order split with the production maths.
E_UPASS = ["uniform float uLyrVolume; uniform float uLyrSurface;",
           "uniform float uPass; uniform float uLyrVolume; uniform float uLyrSurface;"]
E_FRONTNESS = [
    "  vec3 V = normalize(cameraPosition - vW); vec3 N = normalize(vN); if (dot(N, V) < 0.0) N = -N;\n"
    "  float ndv = max(1e-4, dot(N, V));",
    "  vec3 V = normalize(cameraPosition - vW); vec3 N = normalize(vN); if (dot(N, V) < 0.0) N = -N;\n"
    "  float passFront = smoothstep(0.25, 0.75, uPass);\n"
    "  float passLegacy = 1.0 - abs(uPass - 0.5) * 2.0;\n"
    "  float frontness = mix(gl_FrontFacing ? 1.0 : 0.0, passFront, 1.0 - passLegacy);\n"
    "  float ndv = max(1e-4, dot(N, V));"]
E_DETAIL = ["  float detail = gl_FrontFacing ? viewWeight : 0.0;",
            "  float detail = frontness * viewWeight;"]
E_STEPS1 = ["  if (gl_FrontFacing && uSteps > 2.0) {", "  if (frontness > 0.5 && uSteps > 2.0) {"]
E_SURFPATH = ["  vec3 surfacePath = gl_FrontFacing ? vec3(1.0) : mix(vec3(1.0), transmission, viewWeight);",
              "  vec3 surfacePath = mix(mix(vec3(1.0), transmission, viewWeight), vec3(1.0), frontness);"]
E_ALPHA = [
    "  float a = 0.14 + 0.64 * thk + 0.34 * fr + 0.04 * caust + hl * 0.12 + hlWave * 0.14 + needleV * (1.0 - fr) * 0.16;",
    "  float pathT = clamp(dot(transmission, vec3(0.2126, 0.7152, 0.0722)), 0.0, 1.0);\n"
    "  float glint = uLyrRefl * pow(max(0.0, dot(reflect(-L1, N), V)), 180.0);\n"
    "  float coverFar = (0.10 + 0.52 * thk) * pathT;\n"
    "  float coverNear = 0.10 + 0.28 * thk + 0.34 * fr + 0.55 * glint;\n"
    "  float a = mix(0.14 + 0.64 * thk + 0.34 * fr, mix(coverFar, coverNear, passFront), 1.0 - passLegacy)\n"
    "          + 0.04 * caust + hl * 0.12 + hlWave * 0.14 + needleV * (1.0 - fr) * 0.16;"]
E_BACKATT = [
    "  if (!gl_FrontFacing) { a *= 1.0 + (clamp(dot(transmission, vec3(0.2126, 0.7152, 0.0722)), 0.35, 1.0) - 1.0) * uLyrBackAtt; }",
    "  a *= mix(1.0, 1.0 + (clamp(pathT, 0.35, 1.0) - 1.0) * uLyrBackAtt, 1.0 - frontness);"]

ARMS = {
    'order-only': [E_UPASS, E_FRONTNESS, E_DETAIL, E_STEPS1],
    'full':       [E_UPASS, E_FRONTNESS, E_DETAIL, E_STEPS1, E_SURFPATH, E_ALPHA, E_BACKATT],
}

IMPL = r"""function(arm, mode){
  var S=CLApp.scene(), T=THREE, A=__layerAB;
  A.rollback(); A.freeze();
  if(!window.__fb2){
    var shells=[];
    S.scene.traverse(function(o){ var m=o.material;
      if(m&&m.uniforms&&m.uniforms.uLyrVolume&&m.blending===T.NormalBlending) shells.push(o); });
    window.__fb2={shells:[], meshes:[], shaders:[]};
    shells.forEach(function(o){
      var m=o.material;
      if(m.uniforms.uPass===undefined) m.uniforms.uPass={value:0.5};
      window.__fb2.shells.push({orig:o, order:o.renderOrder, mat:m});
      window.__fb2.shaders.push(m.fragmentShader);
      ['back','front'].forEach(function(which){
        var mesh=new T.Mesh(o.geometry, m);
        mesh.frustumCulled=false; mesh.visible=false; mesh.name='__fb2-'+which;
        mesh.position.copy(o.position); mesh.quaternion.copy(o.quaternion); mesh.scale.copy(o.scale);
        mesh.onBeforeRender=function(){
          m.side=(which==='back')?T.BackSide:T.FrontSide;
          if(window.__fb2.legacyPass) m.uniforms.uPass.value=0.5;
          else m.uniforms.uPass.value=(which==='back')?0.0:1.0;
        };
        o.parent.add(mesh);
        window.__fb2.meshes.push({which:which, mesh:mesh});
      });
    });
  }
  var fb=window.__fb2;
  function restore(){
    fb.shells.forEach(function(s,i){ s.mat.fragmentShader=fb.shaders[i]; s.mat.needsUpdate=true;
      s.mat.side=T.DoubleSide; s.orig.visible=true;
      if(s.mat.uniforms.uPass) s.mat.uniforms.uPass.value=0.5; });
    fb.meshes.forEach(function(x){ x.mesh.visible=false; });
    fb.legacyPass=false;
  }
  if(mode!=='candidate'){ restore(); return {arm:arm, mode:mode}; }
  var edits=window.ARMS[arm];
  fb.legacyPass = (arm==='order-only');
  fb.shells.forEach(function(s){
    var t=fb.shaders[fb.shells.indexOf(s)];
    edits.forEach(function(e,i){
      if(t.indexOf(e[0])<0) throw Error(arm+' edit '+i+' anchor not found');
      t=t.split(e[0]).join(e[1]);
    });
    s.mat.fragmentShader=t; s.mat.needsUpdate=true;
    if(s.mat.uniforms.uPass) s.mat.uniforms.uPass.value = fb.legacyPass?0.5:0;
  });
  fb.shells.forEach(function(s){ s.orig.visible=false; });
  fb.meshes.forEach(function(x,i){
    var h=fb.shells[Math.floor(i/2)];
    x.mesh.visible=true;
    x.mesh.renderOrder=(x.which==='back')?h.order:h.order+1;
  });
  return {arm:arm, mode:mode, legacyPass:fb.legacyPass};
}"""

TRIPLE = r"""new Promise(function(resolve,reject){requestAnimationFrame(function(){
  var A=__layerAB, out={}, problem;
  try{
    A.rollback(); A.freeze();
    out.baseline=A.renderAndGrab();
    window.__impl(ARM,'candidate'); out.candidate=A.renderAndGrab();
    window.__impl(ARM,'baseline');  out.restore=A.renderAndGrab();
  }catch(e){problem=e;}
  finally{try{window.__impl(ARM,'baseline');}catch(e){problem=problem||e;}}
  if(problem)reject(problem); else resolve(out);
});})"""

POSES = {'full': '0.85,0.24,1.00,true', 'oblique': '0.85,0.24,0.62,true', 'dark': '2.30,0.10,0.55,true'}


def save(frame, tag):
    for k in ('png', 'detail'):
        if k in frame:
            (OUT / (tag + ('-detail' if k == 'detail' else '') + '.png')).write_bytes(
                base64.b64decode(frame[k].split(',')[1]))


def main():
    assert os.environ.get('CL_GPU') == '1'
    rep = {'task': 'design:v1-optical-composite:20261009b', 'stage': 'decomposition-ab',
           'data': DATA, 'hero': HERO, 'views': {}, 'arms': {},
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
        b.ev(SETUP); b.ev('__layerAB.freeze()'); time.sleep(1)
        b.ev('window.ARMS=%s;1' % json.dumps(ARMS, ensure_ascii=False))
        b.ev('window.__impl=(%s);1' % IMPL)

        for arm in ARMS:
            for view in VIEWS:
                b.ev(POSE % POSES[view]); time.sleep(2.5)
                b.ev(PIN); time.sleep(1.2)
                trip = b.ev('window.ARM=%s;(%s)' % (json.dumps(arm), TRIPLE), True)
                for state in ('baseline', 'candidate', 'restore'):
                    save(trip[state], '%s-%s-%s' % (arm, view, state))
                fr = [trip[s]['frame'] for s in ('baseline', 'candidate', 'restore')]
                same = lambda k: all(f.get(k) is not None and f[k] == fr[0].get(k) for f in fr)
                rec = {'sameClock': all(f.get('clockFrozen') is True for f in fr) and same('tAnim') and same('tAcc'),
                       'sameCamera': same('camera') and same('target') and same('up'),
                       'freshRenders': [f['rendererFrame'] for f in fr],
                       'strictlyIncreasing': fr[0]['rendererFrame'] < fr[1]['rendererFrame'] < fr[2]['rendererFrame'],
                       'restoreExact': trip['restore']['png'] == trip['baseline']['png'],
                       'candidateChanged': trip['candidate']['png'] != trip['baseline']['png'],
                       'quality': {k: fr[0]['quality'].get(k) for k in ('drawW', 'drawH', 'dpr', 'degrade')}}
                rep['arms'].setdefault(arm, {})[view] = rec
                print('ARM %s %s %s' % (arm, view, json.dumps(rec, ensure_ascii=False)), flush=True)

        rep['health'] = b.ev(HEALTH)
        b.ev('(function(){var T=THREE,fb=window.__fb2;if(!fb)return 1;'
             'fb.meshes.forEach(function(x){if(x.mesh.parent)x.mesh.parent.remove(x.mesh);});'
             'fb.shells.forEach(function(s){s.orig.visible=true;s.mat.side=T.DoubleSide;'
             'if(s.mat.uniforms.uPass)s.mat.uniforms.uPass.value=0.5;});fb.meshes=[];return 1;})()')
        rep['cleanupMeshes'] = b.ev('(function(){return window.__fb2?window.__fb2.meshes.length:-1;})()')
        print('HEALTH ' + json.dumps(rep['health'], ensure_ascii=False), flush=True)
    finally:
        try:
            b.close()
        except Exception:
            pass
    (OUT / 'decomp-report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2) + '\n')
    print('WROTE', OUT / 'decomp-report.json', flush=True)


if __name__ == '__main__':
    sys.exit(main())
