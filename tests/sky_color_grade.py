#!/usr/bin/env python3
"""Same-input GPU grade comparison: restore colour without raising luminance contrast.

Capture the real cinema-pass input after opening the Journey to the West book.
Render current and prior print grades against that exact texture and uniforms;
scene animation cannot explain the measured colour/luminance differences.
"""
import argparse
import base64
import json
from pathlib import Path
from atlas_review_shots import Session
import headless

OLD_GRADE = '''vec3 printGrade(vec3 x){
  float y=luma(x); vec3 chroma=x-max(y,0.0);
  y=pow(max(y,0.0),0.965); y=y/(y+0.18); y=pow(y,0.965);
  x=vec3(y)+chroma*(0.82+0.18*uGrade);
  x=mix(vec3(luma(x)),x,0.92+0.08*uGrade);
  x+=vec3(0.004,0.001,0.010)*(1.0-smoothstep(0.08,0.38,y));
  x+=vec3(0.010,0.006,0.001)*smoothstep(0.64,1.0,y);
  return x;
}'''

CAPTURE = r'''(function(){
var S=CLApp.scene(),R=S.renderer,C=S.core().getComposer();
var pass=C.passes.filter(function(p){return p.uniforms&&p.uniforms.uGrade;})[0];
if(!pass||!pass.uniforms.tDiffuse.value)throw new Error('cinema input missing');
var fs=pass.material.fragmentShader,start=fs.indexOf('vec3 printGrade('),end=fs.indexOf('void main()',start);
if(start<0||end<0)throw new Error('grade function missing');
var previous=R.getRenderTarget(),size=R.getDrawingBufferSize(new THREE.Vector2());
var input=new THREE.WebGLRenderTarget(size.x,size.y,{depthBuffer:false});
var material=new THREE.ShaderMaterial({depthTest:false,depthWrite:false,
  uniforms:{tDiffuse:{value:pass.uniforms.tDiffuse.value}},
  vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
  fragmentShader:'uniform sampler2D tDiffuse;varying vec2 vUv;void main(){gl_FragColor=texture2D(tDiffuse,vUv);}'});
var quad=new THREE.FullScreenQuad(material),out=[],pixels=[],gl=R.getContext();
try{
  R.setRenderTarget(input);quad.render(R);
  material.uniforms=THREE.UniformsUtils.clone(pass.uniforms);
  material.uniforms.tDiffuse.value=input.texture;
  [fs.slice(0,start)+OLD_GRADE+'\n'+fs.slice(end),fs].forEach(function(shader){
    material.fragmentShader=shader;material.needsUpdate=true;
    R.setRenderTarget(null);quad.render(R);
    var px=new Uint8Array(size.x*size.y*4);
    gl.readPixels(0,0,size.x,size.y,gl.RGBA,gl.UNSIGNED_BYTE,px);pixels.push(px);
    out.push(R.domElement.toDataURL('image/png'));
  });
  var gains=[],delta=0,black=0,blackN=0,ha=new Uint32Array(4096),hb=new Uint32Array(4096);
  for(var y=0;y<size.y;y++)for(var x=0;x<size.x;x++){
    var i=(y*size.x+x)*4,a=pixels[0],b=pixels[1];
    var ya=(a[i]*.2126+a[i+1]*.7152+a[i+2]*.0722)/255;
    var yb=(b[i]*.2126+b[i+1]*.7152+b[i+2]*.0722)/255;
    var ca=(Math.max(a[i],a[i+1],a[i+2])-Math.min(a[i],a[i+1],a[i+2]))/255;
    var cb=(Math.max(b[i],b[i+1],b[i+2])-Math.min(b[i],b[i+1],b[i+2]))/255;
    delta+=Math.abs(yb-ya);ha[Math.min(4095,Math.floor(ya*4095))]++;hb[Math.min(4095,Math.floor(yb*4095))]++;
    if(ya<.02){black+=yb-ya;blackN++;}
    var dx=(x/size.x-.5)/.31,dy=(y/size.y-.5)/.40;
    if(dx*dx+dy*dy<1&&ya>.08&&ya<.60&&ca>.015)gains.push(cb/ca);
  }
  gains.sort(function(a,b){return a-b;});
  function quantile(h,q){var s=0;for(var j=0;j<h.length;j++){s+=h[j];if(s>=size.x*size.y*q)return j/4095;}return 1;}
  return {images:out,quality:S.quality(),errors:S.shaderErrors(),metrics:{samples:gains.length,
    meanLumaChange:delta/(size.x*size.y),midtoneChromaGain:gains[Math.floor(gains.length/2)]||0,
    blackLift:black/Math.max(1,blackN),lumaSpreadBefore:quantile(ha,.95)-quantile(ha,.05),
    lumaSpreadAfter:quantile(hb,.95)-quantile(hb,.05)}};
}finally{R.setRenderTarget(previous);input.dispose();material.dispose();}
})()'''

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',default='http://127.0.0.1:8765')
    ap.add_argument('--out',default='/tmp/castline-shots/soft-color')
    ap.add_argument('--hover',default='',help='Also evaluate the chosen faction highlight')
    args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    s=Session(1440,900)
    try:
        s.start()
        s.ws.call('Emulation.setDeviceMetricsOverride',width=1440,height=900,deviceScaleFactor=1,mobile=False)
        s.ws.call('Page.addScriptToEvaluateOnNewDocument',source=headless.HEALTH_INIT_JS)
        s.navigate(args.base+'/?data=data/cache/d16db79a529a1727352091d5.json&probe=1&sky=1')
        ready,_,last=s.wait_until("({ready:!!(window.CLSkyDeep&&CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99&&CLSkyDeep.stats().stars.ignite>.99)})",40)
        if not ready: raise RuntimeError('opening did not settle: '+str(last))
        if args.hover:
            s.eval('CLSkyDeep.hoverCamp('+json.dumps(args.hover)+');')
            s.eval('new Promise(function(r){setTimeout(r,800);})',await_promise=True)
        value=s.eval('var OLD_GRADE='+json.dumps(OLD_GRADE)+';'+CAPTURE)
        if not isinstance(value,dict) or 'images' not in value: raise RuntimeError(str(value))
        for name,url in zip(('before','after'),value.pop('images')):
            (out/(name+'.png')).write_bytes(base64.b64decode(url.split(',',1)[1]))
        s.shot(str(out/'page-after.png'))
        value['health']=s.eval(headless.POST_HEALTH_JS,await_promise=True)
    finally: s.close()
    metrics=value['metrics']
    value['ok']=(metrics['samples']>1000 and metrics['meanLumaChange']<.006
      and 1.2<metrics['midtoneChromaGain']<2.3 and abs(metrics['blackLift'])<.003
      and abs(metrics['lumaSpreadAfter']-metrics['lumaSpreadBefore'])<.012
      and not value['errors'] and value['health']['jserr']=='none'
      and value['health']['jsrej']=='none' and not value['health']['shaderErrors'])
    (out/'report.json').write_text(json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps(value,ensure_ascii=False),flush=True)
    return 0 if value['ok'] else 1

if __name__=='__main__': raise SystemExit(main())
