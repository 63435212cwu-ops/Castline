#!/usr/bin/env python3
"""REAL A/B for task design:v1-optical-composite:20261009b.

Mechanism under test (NOT a coefficient scan): explicit front/back light path.
The production crown shells are ONE DoubleSide transparent mesh with
depthWrite:false, so three.js submits their triangles in buffer order and front
and back facets of the same shell interleave. This A/B replaces that with an
explicit BackSide pass (renderOrder 1) then FrontSide pass (renderOrder 2), and
gives the shader an explicit `uPass` so the far surface's alpha comes from the
real Beer-Lambert light path instead of `gl_FrontFacing`.

Discipline (tests/material_layer_ab.py PAIR): baseline -> candidate -> restore,
all three inside ONE synchronous block so no animation tick can occur between
states. Restore must be pixel-exact.

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

OUT = Path('/tmp/castline-shots/review-20261009b/optics-composite')
OUT.mkdir(parents=True, exist_ok=True)
DATA = 'data/cache/ed3dc1255ca08fbdaae30bbd.json'
HERO = '孙悟空'
VIEWS = os.environ.get('CL_AB_VIEWS', 'full,oblique,dark,rotateA').split(',')

# Shader-level text edits (plain GLSL lines, exactly as they appear in
# CROWN_BASE_FS). Each is single-variable in the sense that only the front/back
# path identity changes; no colour, scale or noise coefficient is touched.
EDITS = [
    ["uniform float uLyrVolume; uniform float uLyrSurface;",
     "uniform float uPass; uniform float uLyrVolume; uniform float uLyrSurface;"],

    ["  vec3 V = normalize(cameraPosition - vW); vec3 N = normalize(vN); if (dot(N, V) < 0.0) N = -N;\n"
     "  float ndv = max(1e-4, dot(N, V));",
     "  vec3 V = normalize(cameraPosition - vW); vec3 N = normalize(vN); if (dot(N, V) < 0.0) N = -N;\n"
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
     "  float pathT = clamp(dot(transmission, vec3(0.2126, 0.7152, 0.0722)), 0.0, 1.0);\n"
     "  float glint = uLyrRefl * pow(max(0.0, dot(reflect(-L1, N), V)), 180.0);\n"
     "  float coverFar = (0.10 + 0.52 * thk) * pathT;\n"
     "  float coverNear = 0.10 + 0.28 * thk + 0.34 * fr + 0.55 * glint;\n"
     "  float a = mix(0.14 + 0.64 * thk + 0.34 * fr, mix(coverFar, coverNear, passFront), 1.0 - passLegacy)\n"
     "          + 0.04 * caust + hl * 0.12 + hlWave * 0.14 + needleV * (1.0 - fr) * 0.16;"],

    ["  if (!gl_FrontFacing) { a *= 1.0 + (clamp(dot(transmission, vec3(0.2126, 0.7152, 0.0722)), 0.35, 1.0) - 1.0) * uLyrBackAtt; }",
     "  a *= mix(1.0, 1.0 + (clamp(pathT, 0.35, 1.0) - 1.0) * uLyrBackAtt, 1.0 - frontness);"],
]

# The runtime A/B implementation. Uses window.AB_EDITS (injected below).
AB_IMPL = r"""function(mode){
  var S=CLApp.scene(), T=THREE, A=__layerAB;
  A.rollback(); A.freeze();
  if(!window.__fb){
    var shells=[];
    S.scene.traverse(function(o){ var m=o.material;
      if(m&&m.uniforms&&m.uniforms.uLyrVolume&&m.blending===T.NormalBlending) shells.push(o); });
    window.__fb={shells:[], meshes:[], shaders:[]};
    shells.forEach(function(o){
      var m=o.material;
      if(m.uniforms.uPass===undefined) m.uniforms.uPass={value:0.5};
      window.__fb.shells.push({orig:o, order:o.renderOrder, mat:m});
      window.__fb.shaders.push(m.fragmentShader);
      ['back','front'].forEach(function(which){
        var mesh=new T.Mesh(o.geometry, m);
        mesh.frustumCulled=false; mesh.visible=false; mesh.name='__frontback-'+which;
        mesh.position.copy(o.position); mesh.quaternion.copy(o.quaternion); mesh.scale.copy(o.scale);
        mesh.onBeforeRender=function(){
          m.side=(which==='back')?T.BackSide:T.FrontSide;
          m.uniforms.uPass.value=(which==='back')?0.0:1.0;
        };
        o.parent.add(mesh);
        window.__fb.meshes.push({which:which, mesh:mesh});
      });
    });
  }
  var fb=window.__fb;
  if(mode==='candidate'){
    fb.shells.forEach(function(s){
      var t=s.mat.fragmentShader;
      window.AB_EDITS.forEach(function(e,i){
        if(t.indexOf(e[0])<0) throw Error('edit '+i+' anchor not found in live shader');
        t=t.split(e[0]).join(e[1]);
      });
      s.mat.fragmentShader=t; s.mat.needsUpdate=true;
    });
    fb.shells.forEach(function(s,i){ s.orig.visible=false; });
    fb.meshes.forEach(function(x,i){
      var h=fb.shells[Math.floor(i/2)];
      x.mesh.visible=true;
      x.mesh.renderOrder=(x.which==='back')?h.order:h.order+1;
    });
  } else {
    fb.shells.forEach(function(s,i){
      s.mat.fragmentShader=fb.shaders[i]; s.mat.needsUpdate=true;
      s.mat.side=T.DoubleSide; s.orig.visible=true;
      if(s.mat.uniforms.uPass) s.mat.uniforms.uPass.value=0.5;
    });
    fb.meshes.forEach(function(x){ x.mesh.visible=false; });
  }
  return {mode:mode, shells:fb.shells.length, passes:fb.meshes.length};
}"""

TRIPLE = r"""new Promise(function(resolve,reject){requestAnimationFrame(function(){
  var A=__layerAB, out={}, problem;
  try{
    A.rollback(); A.freeze();
    out.baseline=A.renderAndGrab();
    window.__abImpl('candidate');  out.candidate=A.renderAndGrab();
    window.__abImpl('baseline');   out.restore=A.renderAndGrab();
  }catch(e){problem=e;}
  finally{try{window.__abImpl('baseline');}catch(e){problem=problem||e;}}
  if(problem)reject(problem); else resolve(out);
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
    assert os.environ.get('CL_GPU') == '1'
    rep = {'task': 'design:v1-optical-composite:20261009b', 'stage': 'real-ab-frontback',
           'data': DATA, 'hero': HERO, 'views': {},
           'mechanism': 'explicit BackSide(renderOrder1)->FrontSide(renderOrder2) passes + ray-path alpha via uPass',
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
        b.ev('window.AB_EDITS=%s;1' % json.dumps(EDITS, ensure_ascii=False))
        b.ev('window.__abImpl=(%s);1' % AB_IMPL)

        rep['productionStack'] = b.ev("""(()=>{var T=THREE,S=CLApp.scene(),o=[];
          S.scene.traverse(function(n){var m=n.material;if(m&&m.userData&&m.userData.gemName)
            o.push({name:m.userData.gemName,order:n.renderOrder,blending:m.blending,side:m.side,
                    depthWrite:m.depthWrite,transparent:m.transparent,visible:n.visible,
                    consumesDepthPath:String(m.fragmentShader).indexOf('depthMetric')>=0});});
          return o;})()""")
        print('STACK ' + json.dumps(rep['productionStack'], ensure_ascii=False), flush=True)

        for view in VIEWS:
            b.ev(POSE % POSES[view]); time.sleep(2.5)
            b.ev(PIN); time.sleep(1.2)
            trip = b.ev(TRIPLE, True)
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

        rep['health'] = b.ev(HEALTH)
        b.ev('(function(){var T=THREE,fb=window.__fb;if(!fb)return 1;'
             'fb.meshes.forEach(function(x){if(x.mesh.parent)x.mesh.parent.remove(x.mesh);});'
             'fb.shells.forEach(function(s){s.orig.visible=true;s.mat.side=T.DoubleSide;'
             'if(s.mat.uniforms.uPass)s.mat.uniforms.uPass.value=0.5;});fb.meshes=[];return 1;})()')
        rep['cleanupMeshes'] = b.ev('(function(){return window.__fb?window.__fb.meshes.length:-1;})()')
        print('HEALTH ' + json.dumps(rep['health'], ensure_ascii=False), flush=True)
    finally:
        try:
            b.close()
        except Exception:
            pass
    (OUT / 'ab-report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2) + '\n')
    print('WROTE', OUT / 'ab-report.json', flush=True)


if __name__ == '__main__':
    sys.exit(main())
