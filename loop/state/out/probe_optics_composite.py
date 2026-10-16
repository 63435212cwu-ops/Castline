#!/usr/bin/env python3
"""DIAGNOSTIC ONLY (task design:v1-optical-composite:20261009b).

Ground-truth probe for the real compositing relationship between
  - the two NormalBlending crystal shells (renderOrder 1, both written onto the SAME geometry),
  - the additive fire layers (renderOrder 2, 3),
  - the dispersive ghosts (renderOrder 4),
  - and the background (sky backdrop / nebula / ring ribbons) behind them.

Nothing here is written back to the source tree. Writes only into
CL_SHOTS/review-20261009b/optics-composite/ (project-external, per task).
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

from sky_internal_review_shots import Browser, POSE, PIN, HEALTH  # noqa: E402
from material_layer_ab import SETUP                          # noqa: E402

OUT = Path('/tmp/castline-shots/review-20261009b/optics-composite')
OUT.mkdir(parents=True, exist_ok=True)
DATA = 'data/cache/ed3dc1255ca08fbdaae30bbd.json'   # 西游 corrected default
HERO = '孙悟空'

# ---- probe 1: enumerate everything that draws the crystal, with its real
#             material state: blending, depthWrite, depthTest, side, renderOrder,
#             transparent, and the parent chain's renderOrder.
INSPECT = r"""(()=>{
  var S=CLApp.scene(), out={mats:[],ancestors:[]};
  var gems=[];
  S.scene.traverse(function(o){ if(o.material&&o.material.userData&&o.material.userData.gemName) gems.push(o); });
  gems.forEach(function(o){
    var m=o.material, u=m.uniforms||{};
    var ro=[], p=o; while(p){ if(p.renderOrder!==undefined&&p.renderOrder!==0) ro.push((p.name||p.type)+':'+p.renderOrder); p=p.parent; }
    out.mats.push({name:m.userData.gemName, uuid:m.uuid, order:o.renderOrder, parentOrder:o.parent?o.parent.renderOrder:null,
      chain:ro, blending:m.blending, depthWrite:m.depthWrite, depthTest:m.depthTest, side:m.side,
      transparent:m.transparent, visible:o.visible,
      shader:(String(m.fragmentShader).indexOf('uLyrBackAtt')>=0?'CROWN_BASE_FS':(String(m.fragmentShader).indexOf('vBary')>=0||String(m.fragmentShader).indexOf('gemEdge')>=0?'CROWN_FS/other':'?')),
      uOn:u.uOn?u.uOn.value:null, uThk:u.uThk?+u.uThk.value.toFixed(5):null,
      uAbs:u.uAbs?+u.uAbs.value.toFixed(3):null, uCa:u.uCa?u.uCa.value.getHexString():null,
      uCb:u.uCb?u.uCb.value.getHexString():null});
  });
  // The exact render sequence the renderer will use for transparent, double-sided
  // objects: sorted by renderOrder, then by depth. Read from the live render list.
  var R=S.renderer, scene=S.scene, cam=S.camera;
  scene.updateMatrixWorld(); cam.updateMatrixWorld();
  R.sortObjects=true; R.info.autoReset=false; R.info.reset();
  var list=[], old=R.render;
  R.render=function(sc,c){ var g=R.info.render; R.info.reset();
    sc.traverseVisible(function(o){
      if(!o.isMesh&&!o.isLine&&!o.isPoints&&!o.isSprite) return;
      var m=o.material; if(!m) return;
      list.push({name:m.userData&&m.userData.gemName?m.userData.gemName:(o.name||o.type),
        order:o.renderOrder, transparent:!!m.transparent,
        group:(m.transparent?1:0), blending:m.blending, depthWrite:!!m.depthWrite,
        drawRange:o.geometry&&o.geometry.index?o.geometry.index.count:(o.geometry&&o.geometry.attributes.position?o.geometry.attributes.position.count:0)});
    });
    R.render=old; };
  R.render(scene,cam);
  out.drawList=list.slice();
  R.info.autoReset=true;
  return out;
})()"""

# ---- probe 2: what does each crystal layer actually contribute to the pixel?
#             Isolate by toggling ONLY the real production material visibility
#             (not uniforms), three states, same frame clock.
ISO = r"""(()=>{
  var S=CLApp.scene(); var A=__layerAB; A.rollback(); A.freeze();
  var gems=[]; S.scene.traverse(function(o){ if(o.material&&o.material.userData&&o.material.userData.gemName) gems.push(o); });
  var base=gems.map(function(o){return o.visible;});
  function grab(){ var f=A.renderAndGrab(); return {png:f.png, frame:{tAnim:f.frame.tAnim,rendererFrame:f.frame.rendererFrame}}; }
  var frames=[], labels=[];
  function snap(tag){ frames.push(grab()); labels.push(tag); }
  snap('all');
  // only the two NormalBlending shells (the real "crystal body")
  gems.forEach(function(o){ o.visible = (o.material.blending===THREE.NormalBlending); });
  snap('normal-shells-only');
  // only the additive fire layers
  gems.forEach(function(o){ o.visible = (o.material.blending===THREE.AdditiveBlending); });
  snap('additive-only');
  // nothing at all
  gems.forEach(function(o){ o.visible = false; });
  snap('none');
  gems.forEach(function(o,i){ o.visible=base[i]; });
  snap('restored');
  return {labels:labels, frames:frames, restoreExact: (frames[0].png===frames[4].png),
          gems:gems.map(function(o){return {name:o.material.userData.gemName, blending:o.material.blending, order:o.renderOrder};})};
})()"""

# ---- probe 3: real compositing evidence. Put a structured backdrop exactly behind
#             the crystal (a high-contrast checker wall in world space) and read the
#             pixel column through the thick body and through the thin girdle.
#             This proves thick-blocks-background vs thin-transmits, or the reverse.
BACKDROP = r"""(()=>{
  var S=CLApp.scene(), T=THREE;
  var grp=new T.Group(); grp.name='__probeBackdrop';
  var g=new T.PlaneGeometry(2400,1400,1,1);
  var cv=document.createElement('canvas'); cv.width=256; cv.height=128;
  var c=cv.getContext('2d');
  for(var y=0;y<128;y+=8) for(var x=0;x<256;x+=8){
    var on=((x/8)+(y/8))%2===0;
    c.fillStyle= on? 'rgb(0,0,0)' : 'rgb(255,255,255)';
    c.fillRect(x,y,8,8);
  }
  var tex=new T.CanvasTexture(cv); tex.magFilter=T.NearestFilter; tex.minFilter=T.NearestFilter;
  var mat=new T.MeshBasicMaterial({map:tex, side:T.DoubleSide, depthWrite:true, depthTest:true, fog:false, toneMapped:false});
  var mesh=new T.Mesh(g,mat);
  // park it directly behind the crown along the current view direction
  var b=S.crownScreenBounds();
  var cam=S.camera, dir=new T.Vector3(); cam.getWorldDirection(dir);
  var cen=new T.Vector3();
  S.scene.traverse(function(o){ if(o.material&&o.material.userData&&o.material.userData.gemName&&o.material.blending===THREE.NormalBlending)
    { o.getWorldPosition(cen); } });
  mesh.position.copy(cen).addScaledVector(dir, 420);
  mesh.lookAt(cam.position);
  grp.add(mesh);
  S.scene.add(grp);
  window.__probeBackdrop=grp;
  return {added:true, center:cen.toArray().map(function(v){return +v.toFixed(1);}),
          bounds:b?{l:+b.left.toFixed(1),t:+b.top.toFixed(1),r:+b.right.toFixed(1),b:+b.bottom.toFixed(1)}:null};
})()"""

# ---- probe 4: measure, in the real frame, alpha coverage of the crystal by
#             rendering the crystal group twice: once normal, once with the
#             background removed -- the difference isolates where the crystal
#             actually occludes.
ALPHA = r"""(()=>{
  var S=CLApp.scene(), A=__layerAB; A.freeze();
  var gems=[]; S.scene.traverse(function(o){ if(o.material&&o.material.userData&&o.material.userData.gemName) gems.push(o); });
  // Sample the drawing buffer directly: readPixels is the only ground truth about
  // what was composited, not what the shader intended.
  var gl=S.renderer.getContext(), w=gl.drawingBufferWidth, h=gl.drawingBufferHeight;
  function readRGB(){
    var px=new Uint8Array(w*h*4);
    gl.readPixels(0,0,w,h,gl.RGBA,gl.UNSIGNED_BYTE,px);
    var sum=0, n=0, maxv=0;
    for(var i=0;i<px.length;i+=4){ var v=(px[i]+px[i+1]+px[i+2])/3; sum+=v; n++; if(v>maxv)maxv=v; }
    return {mean:+(sum/n).toFixed(4), max:maxv, w:w, h:h};
  }
  A.rollback(); var f0=A.renderAndGrab(); var r0=readRGB();
  var bd=window.__probeBackdrop; var was=bd?bd.visible:null; if(bd) bd.visible=false;
  var f1=A.renderAndGrab(); var r1=readRGB();
  if(bd) bd.visible=was;
  return {withBackdrop:r0, withoutBackdrop:r1, delta:+(r0.mean-r1.mean).toFixed(4), restored:(r0.mean===readRGB().mean)};
})()"""


def save(frame, tag, keys=('png', 'detail')):
    out = {}
    for k in keys:
        if k not in frame:
            continue
        p = OUT / (tag + ('-detail' if k == 'detail' else '') + '.png')
        p.write_bytes(base64.b64decode(frame[k].split(',')[1]))
        out[k] = str(p)
    return out


def main():
    assert os.environ.get('CL_GPU') == '1', 'CL_GPU=1 required, serial GPU slot'
    report = {'task': 'design:v1-optical-composite:20261009b', 'stage': 'diagnostic-probe',
              'data': DATA, 'hero': HERO, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    b = Browser(1920, 1080)
    try:
        b.start()
        b.ws.call('Page.navigate', url='http://127.0.0.1:8781/?sky=1&probe=1&data=' + DATA)
        ok, dt = b.wait_ready()
        report['ready'] = {'ok': ok, 'seconds': round(dt, 1)}
        b.ev(PIN)
        b.ev('CLSky.openCompass(%s)' % json.dumps(HERO))
        time.sleep(6)
        b.wait_settle(30)
        b.ev('(function(){var S=CLApp.scene();S.core().setCalm(true,"lab");S.controls.autoRotate=false;S.controls.enableDamping=false;S.controls.update();return 1;})()')
        time.sleep(2)
        b.ev(SETUP)
        b.ev('__layerAB.freeze()')
        time.sleep(1)

        report['inspect'] = b.ev(INSPECT)
        print(json.dumps({'inspect': report['inspect']}, ensure_ascii=False)[:4000], flush=True)

        iso = b.ev(ISO)
        report['isolation'] = {'labels': iso['labels'], 'restoreExact': iso['restoreExact'],
                               'gems': iso['gems'],
                               'frames': [f['frame'] for f in iso['frames']]}
        for tag, frame in zip(iso['labels'], iso['frames']):
            save(frame, 'iso-' + tag)
        print(json.dumps({'isolation': report['isolation']['labels'],
                          'restoreExact': iso['restoreExact'],
                          'frames': report['isolation']['frames']}, ensure_ascii=False), flush=True)

        report['backdrop'] = b.ev(BACKDROP)
        time.sleep(1)
        frames = []
        for tag, expr in [('backdrop-raw', None)]:
            f = b.ev('__layerAB.renderAndGrab()')
            save(f, tag)
            frames.append(f)
        report['alpha'] = b.ev(ALPHA)
        print(json.dumps({'backdrop': report['backdrop'], 'alpha': report['alpha']}, ensure_ascii=False), flush=True)

        # with the structured backdrop in place, shoot the composite + the two shell
        # states so a human/independent reviewer can see real occlusion.
        trio = b.ev(ISO)
        for tag, frame in zip(trio['labels'], trio['frames']):
            save(frame, 'backdrop-iso-' + tag)
        report['backdrop_isolation'] = {'labels': trio['labels'], 'restoreExact': trio['restoreExact']}

        report['health'] = b.ev(HEALTH)
        report['quality'] = b.ev('CLApp.scene().quality()')
        print(json.dumps({'health': report['health'], 'quality': report['quality']}, ensure_ascii=False), flush=True)
        # cleanup the probe backdrop
        b.ev('(function(){var S=CLApp.scene();if(window.__probeBackdrop){S.scene.remove(window.__probeBackdrop);window.__probeBackdrop=null;}return 1;})()')
    finally:
        try:
            b.close()
        except Exception:
            pass
    (OUT / 'probe-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('WROTE', OUT / 'probe-report.json', flush=True)


if __name__ == '__main__':
    sys.exit(main())
