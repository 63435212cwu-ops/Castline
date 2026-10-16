#!/usr/bin/env python3
"""DIAGNOSTIC ONLY (task design:v1-optical-composite:20261009b) — probe 3.

Corrects probe 2's material-selection error (probe 2 picked the first gem
material, which is the additive fire layer, and therefore read its *default*
uThk=1 / rad=(90,40,90) instead of the NormalBlending shell's real values).

What this measures, all from live production values:
  1. Which material actually consumes the thickness term (fragment shader contains
     the uLyrBackAtt / depthMetric anchor) -- and its real uThk, uCen, uRad.
  2. The real distribution of chord / opticalDepth / depthMetric / thk / alpha
     over every vertex of the real crown geometry.
  3. Whether the triangle draw order of the double-sided shell interleaves front
     and back faces (the structural cause of "front and back indistinguishable").
  4. How much of the background actually survives behind thick body vs thin
     girdle, measured through a structured checker backdrop.
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

OUT = Path('/tmp/castline-shots/review-20261009b/optics-composite-3')
OUT.mkdir(parents=True, exist_ok=True)
DATA = 'data/cache/ed3dc1255ca08fbdaae30bbd.json'
HERO = '孙悟空'

# ---- 1+2: the real thickness numbers, from the real consuming material.
MEASURE = r"""(()=>{
  var S=CLApp.scene(), T=THREE, out={shells:[]};
  var shells=[];
  S.scene.traverse(function(o){
    var m=o.material; if(!m||!m.fragmentShader) return;
    if(String(m.fragmentShader).indexOf('uLyrBackAtt')>=0 && String(m.fragmentShader).indexOf('depthMetric')>=0) shells.push(o);
  });
  if(!shells.length) return {error:'no CROWN_BASE_FS consumer'};
  S.camera.updateMatrixWorld(true);
  shells.forEach(function(shell){
    var u=shell.material.uniforms;
    shell.updateMatrixWorld(true);
    var camL=u.uCamL.value, cen=u.uCen.value, rad=u.uRad.value, thk=u.uThk.value;
    var pos=shell.geometry.attributes.position, idx=shell.geometry.index, n=pos.count;
    var dst=new T.Vector3(), Vl=new T.Vector3(), eo=new T.Vector3(), ed3=new T.Vector3();
    var rows=[], stride=Math.max(1,Math.floor(n/600));
    for(var i=0;i<n;i+=stride){
      dst.fromBufferAttribute(pos,i);
      Vl.copy(dst).sub(camL).normalize();
      eo.copy(dst).sub(cen).divide(rad); ed3.copy(Vl).divide(rad);
      var qb=eo.dot(ed3), qa=Math.max(1e-5,ed3.dot(ed3)), qc=eo.dot(eo)-1.0;
      var qd=qb*qb-qa*qc, chord= qd>0 ? Math.sqrt(qd)*2.0/qa : 0.0;
      var opticalDepth=Math.max(chord*thk,0.0), vH=pos.getY(i);
      var depthMetric=Math.min(2.0,Math.max(0.0,(opticalDepth+vH*0.40)*u.uLyrVolume.value));
      var th=Math.min(1.0,depthMetric);
      rows.push({chord:chord, od:opticalDepth, vH:vH, dm:depthMetric, th:th});
    }
    function st(k){var v=rows.map(function(r){return r[k];}).sort(function(a,b){return a-b;});
      var q=function(p){return +v[Math.min(v.length-1,Math.floor(v.length*p))].toFixed(4);};
      return {min:+v[0].toFixed(4), p05:q(0.05), med:q(0.5), p95:q(0.95), max:+v[v.length-1].toFixed(4)};}
    var num=rows.reduce(function(a,r){return a+r.od;},0);
    var den=rows.reduce(function(a,r){return a+r.od+Math.max(0,r.vH*0.40);},0);
    var atCap=rows.filter(function(r){return r.dm>=1.999;}).length;
    // ---- 3: does the draw order interleave front and back faces?
    var flips=0, prev=null, faceSigns=[], triCount=0;
    if(idx){
      var a=new T.Vector3(),b=new T.Vector3(),c=new T.Vector3();
      var ab=new T.Vector3(), ac=new T.Vector3(), nrm=new T.Vector3(), toCam=new T.Vector3();
      for(var t=0;t<idx.count;t+=3){
        a.fromBufferAttribute(pos,idx.getX(t)); b.fromBufferAttribute(pos,idx.getX(t+1)); c.fromBufferAttribute(pos,idx.getX(t+2));
        ab.subVectors(b,a); ac.subVectors(c,a); nrm.crossVectors(ab,ac);
        var mid=a.clone().add(b).add(c).multiplyScalar(1/3);
        toCam.copy(S.camera.position).sub(mid);
        var d=nrm.dot(toCam);
        if(Math.abs(d)<1e-9) continue;
        var s=d>0?1:-1; triCount++;
        if(prev!==null && s!==prev) flips++;
        prev=s;
      }
    }
    out.shells.push({
      name:shell.material.userData.gemName, order:shell.renderOrder,
      blending:shell.material.blending, side:shell.material.side,
      depthWrite:shell.material.depthWrite, transparent:shell.material.transparent,
      vertices:n, tris:triCount, drawOrderFaceFlips:flips,
      flipRate: triCount>1? +(flips/(triCount-1)).toFixed(4):null,
      chord:st('chord'), opticalDepth:st('od'), vH:st('vH'), depthMetric:st('dm'), thk:st('th'),
      pathShare: +(num/den).toFixed(4),
      fracDepthMetricAtCap: +(atCap/rows.length).toFixed(4),
      uniforms:{uThk:thk, uLyrVolume:u.uLyrVolume.value, uAbs:u.uAbs.value, uLyrTrans:u.uLyrTrans.value,
                uLyrBackAtt:u.uLyrBackAtt.value, uCen:cen.toArray(), uRad:rad.toArray(), uCamL:camL.toArray(),
                uIor:u.uIor.value}});
  });
  // the alpha the shader would compute, using the real production expression
  out.alphaNote = 'a = 0.14 + 0.64*thk + 0.34*fr + 0.04*caust + hl + needle; thk saturating => a saturating';
  return out;
})()"""

BACKDROP = r"""(()=>{
  var S=CLApp.scene(), T=THREE;
  var cv=document.createElement('canvas'); cv.width=512; cv.height=512;
  var c=cv.getContext('2d');
  for(var y=0;y<512;y+=16) for(var x=0;x<512;x+=16){
    c.fillStyle=((x/16)+(y/16))%2===0?'rgb(0,0,0)':'rgb(255,255,255)';
    c.fillRect(x,y,16,16);
  }
  var tex=new T.CanvasTexture(cv); tex.magFilter=T.NearestFilter; tex.minFilter=T.NearestFilter;
  var mesh=new T.Mesh(new T.PlaneGeometry(3000,3000),
    new T.MeshBasicMaterial({map:tex, side:T.DoubleSide, fog:false, toneMapped:false}));
  mesh.name='__bd3';
  var cen=new T.Vector3();
  S.scene.traverse(function(o){ if(o.material&&o.material.userData&&o.material.userData.gemName&&o.material.blending===THREE.NormalBlending) o.getWorldPosition(cen); });
  var cam=S.camera, dir=new T.Vector3(); cam.getWorldDirection(dir);
  mesh.position.copy(cen).addScaledVector(dir, 700); mesh.lookAt(cam.position); mesh.updateMatrixWorld(true);
  S.scene.add(mesh); window.__bd3=mesh;
  return {added:true, center:cen.toArray().map(function(v){return +v.toFixed(1);})};
})()"""

# Sample real pixels through the checker wall: readPixels is ground truth about
# what was actually composited.
SAMPLER = r"""(()=>{
  var S=CLApp.scene(), A=__layerAB, T=THREE;
  var gl=S.renderer.getContext(), w=gl.drawingBufferWidth, h=gl.drawingBufferHeight;
  function read(){ var px=new Uint8Array(w*h*4); gl.readPixels(0,0,w,h,gl.RGBA,gl.UNSIGNED_BYTE,px); return px; }
  // local contrast = mean |horizontal neighbour difference| inside a rect.
  // NOTE: readPixels origin is bottom-left; rects are given in that frame.
  function contrast(px, x0,y0,x1,y1){
    var s=0,n=0;
    for(var y=y0;y<y1;y++) for(var x=x0;x<x1-1;x++){
      var i=(y*w+x)*4, j=(y*w+x+1)*4;
      s+=Math.abs(px[i]-px[j]); n++;
    }
    return n? +(s/n).toFixed(3):null;
  }
  var b=S.crownScreenBounds();
  // readPixels y is flipped relative to the CSS/screen bounds returned above
  function flip(r){ return {x0:Math.max(0,Math.floor(r.left)), x1:Math.min(w,Math.ceil(r.right)),
                            y0:Math.max(0,h-Math.ceil(r.bottom)), y1:Math.min(h,h-Math.floor(r.top))}; }
  var R=flip(b);
  var cx=Math.floor((R.x0+R.x1)/2), cy=Math.floor((R.y0+R.y1)/2);
  var bw=Math.max(8,Math.floor((R.x1-R.x0)*0.22)), bh=Math.max(8,Math.floor((R.y1-R.y0)*0.22));
  function centred(fx,fy){ var x=Math.floor(R.x0+(R.x1-R.x0)*fx), y=Math.floor(R.y0+(R.y1-R.y0)*fy);
    return {x0:Math.max(0,x-bw),x1:Math.min(w,x+bw),y0:Math.max(0,y-bh),y1:Math.min(h,y+bh)}; }
  A.rollback(); A.freeze();
  var f=A.renderAndGrab(); var px=read();
  var whole=contrast(px,R.x0,R.y0,R.x1,R.y1);
  var regions={ upperBody:centred(0.5,0.78), lowerCone:centred(0.5,0.22),
                leftEdge:centred(0.06,0.5), rightEdge:centred(0.94,0.5) };
  var res={crystalBounds:R, whole:whole};
  Object.keys(regions).forEach(function(k){ res[k]=contrast(px,regions[k].x0,regions[k].y0,regions[k].x1,regions[k].y1); });
  // outside the crystal, far from it: the backdrop's own contrast
  var ox0=Math.max(0,R.x0-260), ox1=Math.max(1,R.x0-60);
  res.outsideLeft=contrast(px,ox0,cy-60,ox1,cy+60);
  res.meanRGB=(function(){var s=0,n=0;for(var i=0;i<px.length;i+=4){s+=(px[i]+px[i+1]+px[i+2])/3;n++;}return +(s/n).toFixed(4);})();
  res.frame={tAnim:f.frame.tAnim, rendererFrame:f.frame.rendererFrame, clockFrozen:f.frame.clockFrozen};
  return res;
})()"""

# Hide the crystal entirely; the backdrop contrast is then the transmission ceiling.
NOCRYSTAL = r"""(()=>{
  var S=CLApp.scene(), A=__layerAB, T=THREE;
  var gl=S.renderer.getContext(), w=gl.drawingBufferWidth, h=gl.drawingBufferHeight;
  window.__g3=[]; S.scene.traverse(function(o){ if(o.material&&o.material.userData&&o.material.userData.gemName){window.__g3.push([o,o.visible]);o.visible=false;} });
  A.rollback(); A.freeze(); A.renderAndGrab();
  var px=new Uint8Array(w*h*4); gl.readPixels(0,0,w,h,gl.RGBA,gl.UNSIGNED_BYTE,px);
  function contrast(x0,y0,x1,y1){var s=0,n=0;for(var y=y0;y<y1;y++)for(var x=x0;x<x1-1;x++){var i=(y*w+x)*4,j=(y*w+x+1)*4;s+=Math.abs(px[i]-px[j]);n++;}return n?+(s/n).toFixed(3):null;}
  var b=S.crownScreenBounds();
  var R={x0:Math.max(0,Math.floor(b.left)),x1:Math.min(w,Math.ceil(b.right)),y0:Math.max(0,h-Math.ceil(b.bottom)),y1:Math.min(h,h-Math.floor(b.top))};
  var cx=Math.floor((R.x0+R.x1)/2), cy=Math.floor((R.y0+R.y1)/2);
  var bw=Math.max(8,Math.floor((R.x1-R.x0)*0.22)), bh=Math.max(8,Math.floor((R.y1-R.y0)*0.22));
  function centred(fx,fy){var x=Math.floor(R.x0+(R.x1-R.x0)*fx),y=Math.floor(R.y0+(R.y1-R.y0)*fy);return {x0:Math.max(0,x-bw),x1:Math.min(w,x+bw),y0:Math.max(0,y-bh),y1:Math.min(h,y+bh)};}
  var res={whole:contrast(R.x0,R.y0,R.x1,R.y1)};
  var regions={upperBody:centred(0.5,0.78), lowerCone:centred(0.5,0.22), leftEdge:centred(0.06,0.5), rightEdge:centred(0.94,0.5)};
  Object.keys(regions).forEach(function(k){res[k]=contrast(regions[k].x0,regions[k].y0,regions[k].x1,regions[k].y1);});
  res.outsideLeft=contrast(Math.max(0,R.x0-260),cy-60,Math.max(1,R.x0-60),cy+60);
  window.__g3.forEach(function(p){p[0].visible=p[1];});
  A.rollback();
  return res;
})()"""


def save(frame, tag):
    for k in ('png', 'detail'):
        if k in frame:
            (OUT / (tag + ('-detail' if k == 'detail' else '') + '.png')).write_bytes(base64.b64decode(frame[k].split(',')[1]))


def main():
    assert os.environ.get('CL_GPU') == '1'
    rep = {'task': 'design:v1-optical-composite:20261009b', 'stage': 'probe3-real-thickness',
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

        rep['measure'] = b.ev(MEASURE)
        print('MEASURE ' + json.dumps(rep['measure'], ensure_ascii=False), flush=True)

        rep['backdrop'] = b.ev(BACKDROP); time.sleep(0.8)
        rep['transmission'] = b.ev(SAMPLER)
        print('TRANSMISSION ' + json.dumps(rep['transmission'], ensure_ascii=False), flush=True)
        rep['ceiling'] = b.ev(NOCRYSTAL)
        print('CEILING ' + json.dumps(rep['ceiling'], ensure_ascii=False), flush=True)

        f = b.ev('__layerAB.renderAndGrab()'); save(f, 'through-checker')
        rep['health'] = b.ev(HEALTH)
        b.ev("(function(){var S=CLApp.scene();if(window.__bd3){S.scene.remove(window.__bd3);window.__bd3=null;}return 1;})()")
    finally:
        try:
            b.close()
        except Exception:
            pass
    (OUT / 'probe3-report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2) + '\n')
    print('WROTE', OUT / 'probe3-report.json', flush=True)


if __name__ == '__main__':
    sys.exit(main())
