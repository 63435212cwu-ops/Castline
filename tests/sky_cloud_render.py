#!/usr/bin/env python3
"""Real Metal GPU cloud readback, continuity, ownership and 180-rAF performance.

Run with the app server running: python3 -s tests/sky_cloud_render.py
--native/--force4k requests S.setBoost(true); it reports the same 50 fps target
without making native-resolution performance part of the default-mode gate.
Pixel detail metrics are diagnostics, not a claim of artistic approval.
"""
import argparse
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from atlas_review_shots import Session, headless

READY = r"""(()=>{
 const d=window.CLSkyDeep&&CLSkyDeep.stats();
 if(!d||!d.inited)return {ready:false,deep:d};
 const pending=[];
 function scan(o,path){if(!o||typeof o!=='object')return;
   if(o.state==='hidden'||o.state==='dim'||o.open===false)return;
   for(const [k,v] of Object.entries(o)){
     if(k==='ignite'&&!(v>.99))pending.push(path+'.'+k);
     if(k==='alpha'&&!(v>(path==='nebula'?.01:.99)))pending.push(path+'.'+k);
     if(v&&typeof v==='object'&&!Array.isArray(v))scan(v,path?path+'.'+k:k);
   }}
 scan(d,'');
 return {ready:d.mode==='constellation'&&d.stars.n>0&&d.stars.ignite>.99&&
   !!d.cosmos&&d.cosmos.alpha>.99&&d.nebula.alpha>.01&&!pending.length&&
   !document.getElementById('clSigil'),pending,deep:d};
})()"""

PERF = r"""(async()=>{
 const S=CLApp.scene(),c=S.controls,was=c.autoRotate,speed=c.autoRotateSpeed;
 const intervals=[],q0=S.quality(),p0=S.camera.position.clone(),f0=S.renderer.info.render.frame;
 const direction=p0.clone().sub(c.target).normalize();
 let last;
 try{
   c.autoRotate=ROTATE;c.autoRotateSpeed=.35;
   await new Promise(resolve=>{function tick(t){
     if(last!==undefined)intervals.push(t-last);last=t;
     if(intervals.length===180)resolve();else requestAnimationFrame(tick);
   }requestAnimationFrame(tick);});
   const sorted=intervals.slice().sort((a,b)=>a-b),mean=intervals.reduce((a,b)=>a+b,0)/180;
   return {frames:180,intervalsMs:intervals,meanMs:mean,p50Ms:sorted[89],p95Ms:sorted[170],
     fps:1000/mean,targetFps:50,targetMet:1000/mean>=50,qualityBefore:q0,qualityAfter:S.quality(),
     rendererFrames:S.renderer.info.render.frame-f0,cameraTravel:S.camera.position.distanceTo(p0),
     rotationRadians:direction.angleTo(S.camera.position.clone().sub(c.target).normalize())};
 }finally{c.autoRotate=was;c.autoRotateSpeed=speed;}
})()"""

READBACK = r"""(()=>{
 const S=CLApp.scene(),r=S.renderer,T=THREE;let source;
 S.scene.traverse(o=>{if(!source&&o.isMesh&&o.material.uniforms&&
   o.material.uniforms.tSplat&&o.material.uniforms.uCam)source=o;});
 if(!source)throw Error('cloud mesh missing');
 const material=source.material.clone();
 // Keep the owner's textures; ShaderMaterial.clone otherwise clones textures.
 for(const [k,u] of Object.entries(source.material.uniforms))
   if(u.value&&u.value.isTexture)material.uniforms[k].value=u.value;
 const copy=new T.Mesh(source.geometry,material),scene=new T.Scene(),camera=S.camera.clone();
 source.updateWorldMatrix(true,false);copy.matrix.copy(source.matrixWorld);
 copy.matrixAutoUpdate=false;copy.frustumCulled=false;scene.add(copy);
 const w=320,h=200,rt=new T.WebGLRenderTarget(w,h,{depthBuffer:false,stencilBuffer:false});
 const old={target:r.getRenderTarget(),face:r.getActiveCubeFace(),level:r.getActiveMipmapLevel(),
   color:r.getClearColor(new T.Color()).clone(),alpha:r.getClearAlpha(),auto:r.autoClear,
   viewport:r.getViewport(new T.Vector4()),scissor:r.getScissor(new T.Vector4()),test:r.getScissorTest()};
 function render(t){material.uniforms.uTime.value=t;r.setRenderTarget(rt);r.setClearColor(0,0);
   // setRenderTarget uses physical RT pixels; setViewport would multiply DPR again.
   r.setScissorTest(false);r.autoClear=true;r.render(scene,camera);
   const px=new Uint8Array(w*h*4);r.readRenderTargetPixels(rt,0,0,w,h,px);return px;}
 function delta(a,b){let sum=0,max=0,changed=0;for(let i=0;i<a.length;i++){
   const d=Math.abs(a[i]-b[i]);sum+=d;max=Math.max(max,d);if(d)changed++;}
   return {meanByte:sum/a.length,maxByte:max,changed};}
 function png(px){const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;
   const ctx=canvas.getContext('2d'),image=ctx.createImageData(w,h);
   for(let y=0;y<h;y++)for(let x=0;x<w;x++){
     const dst=(y*w+x)*4,src=((h-1-y)*w+x)*4;
     image.data.set(px.subarray(src,src+3),dst);image.data[dst+3]=255;}
   ctx.putImageData(image,0,0);return canvas.toDataURL('image/png');}
 try{
   const t=source.material.uniforms.uTime.value,a=render(t),same=render(t),frame=render(t+1/60),long=render(t+2);
   let lit=0,sum=0,sum2=0,edge=0,edges=0;const levels=new Set();
   for(let i=0;i<a.length;i+=4){const v=Math.max(a[i],a[i+1],a[i+2]);
     if(v>0){lit++;sum+=v;sum2+=v*v;levels.add(v);}
     if((i/4)%w&&v>0){edge+=Math.abs(v-Math.max(a[i-4],a[i-3],a[i-2]));edges++;}}
   const fixed=delta(a,same),near=delta(a,frame),far=delta(a,long),mean=sum/Math.max(1,lit);
   const detail={litPixels:lit,coverage:lit/(w*h),levels:levels.size,
     stdDev:Math.sqrt(Math.max(0,sum2/Math.max(1,lit)-mean*mean)),neighborGradient:edge/Math.max(1,edges)};
   return {size:[w,h],time:t,fixed,near,far,detail,shaderErrors:S.shaderErrors(),deterministic:fixed.maxByte===0,
     continuous:near.meanByte<far.meanByte&&far.changed>0,
     nonempty:lit>w*h*.005,details:levels.size>=8&&detail.stdDev>.5&&detail.neighborGradient>0,
     images:{cloud_t:png(a),cloud_next_frame:png(frame),cloud_two_seconds:png(long)}};
 }finally{scene.remove(copy);material.dispose();
   r.setClearColor(old.color,old.alpha);r.autoClear=old.auto;r.setViewport(old.viewport);
   r.setScissor(old.scissor);r.setScissorTest(old.test);
   r.setRenderTarget(old.target,old.face,old.level);rt.dispose();}
})()"""

OWNERSHIP = r"""(()=>{
 const r=CLApp.scene().renderer,rows=[],uuids=[];
 for(let i=0;i<3;i++){const before=r.info.memory.textures,t=CLSkyCloudNoise.create(THREE);
   let uploaded;try{r.initTexture(t);uploaded=r.info.memory.textures;uuids.push(t.uuid);}
   finally{t.dispose();}const after=r.info.memory.textures;
   rows.push({before,uploaded,after,ok:uploaded===before+1&&after===before});}
 return {cycles:rows,unique:new Set(uuids).size===3,ok:rows.every(x=>x.ok)&&new Set(uuids).size===3};
})()"""

MODES = r"""(async()=>{
 const S=CLApp.scene(),body=document.body,q=S.quality(),still=body.classList.contains('skylab-still');
 const calm=S.calm(),out={before:{quality:q,still,calm}};let raf=0;
 const frames=n=>new Promise(resolve=>{function tick(){raf++;if(--n)requestAnimationFrame(tick);else resolve();}requestAnimationFrame(tick);});
 function sample(){let m;S.scene.traverse(o=>{if(o.material&&o.material.uniforms&&o.material.uniforms.tSplat)m=o.material;});
   if(!m)throw Error('cloud missing during mode switch');
   const steps=m.fragmentShader.match(/#define STEPS (\d+)/);
   return {tier:CLSkyDeep.stats().tier,time:m.uniforms.uTime.value,steps:steps?+steps[1]:-1,
     reduced:CLSkyTokens.reduced(),shaderErrors:S.shaderErrors(),frame:S.renderer.info.render.frame,raf};}
 try{
   body.classList.remove('skylab-still');S.setCalm(false);S.setDegrade(0);await frames(12);out.high=sample();
   S.setDegrade(2);await frames(12);out.low=sample();await frames(18);out.lowLater=sample();
   S.setDegrade(0);await frames(2);out.lowResume2=sample();await frames(10);
   body.classList.add('skylab-still');await frames(4);out.reduced=sample();
   await frames(18);out.reducedLater=sample();body.classList.remove('skylab-still');
   await frames(2);out.reducedResume2=sample();await frames(10);out.resumed=sample();await frames(18);out.resumedLater=sample();
   out.phaseResume={lowDelta:out.lowResume2.time-out.lowLater.time,reducedDelta:out.reducedResume2.time-out.reducedLater.time,
     lowFrozenRafs:out.lowLater.raf-out.low.raf,reducedFrozenRafs:out.reducedLater.raf-out.reduced.raf,maxSeconds:.12};
   out.phaseResume.ok=[out.phaseResume.lowDelta,out.phaseResume.reducedDelta].every(x=>x>=0&&x<=.12)&&
     out.phaseResume.lowFrozenRafs>=18&&out.phaseResume.reducedFrozenRafs>=18&&
     [out.lowResume2,out.reducedResume2].every(x=>x.tier==='high'&&x.steps>0&&!x.reduced);
   out.ok=out.high.tier==='high'&&out.high.steps>0&&out.low.tier==='low'&&out.low.steps===0&&
     out.low.time===out.lowLater.time&&out.reduced.reduced&&out.reduced.steps===0&&
     out.reduced.time===out.reducedLater.time&&!out.resumed.reduced&&out.resumed.steps>0&&
     out.resumedLater.time>out.resumed.time&&out.phaseResume.ok&&
     [out.high,out.low,out.lowLater,out.lowResume2,out.reduced,out.reducedLater,out.reducedResume2,out.resumed,out.resumedLater]
       .every(x=>x.shaderErrors.length===0)&&out.lowLater.frame>out.low.frame&&out.reducedLater.frame>out.reduced.frame;
 }finally{body.classList.toggle('skylab-still',still);S.setCalm(calm);S.setDegrade(q.degrade);await frames(4);
   out.restored=S.quality().degrade===q.degrade&&body.classList.contains('skylab-still')===still&&S.calm()===calm;}
 out.ok=out.ok&&out.restored;return out;
})()"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765'))
    ap.add_argument('--size', choices=['1440x900', '1920x1080'], default='1440x900')
    ap.add_argument('--dpr', type=float, default=1)
    ap.add_argument('--native', '--force4k', action='store_true')
    ap.add_argument('--out', default='/tmp/castline-shots/cloud-render')
    ap.add_argument('--data', default='data/cache/d16db79a529a1727352091d5.json')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    session = Session(*map(int, a.size.split('x')))
    report = {'config': vars(a), 'ok': False, 'checks': {}}

    def ev(script):
        value = session.eval(script, await_promise=True)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(json.dumps(value, ensure_ascii=False))
        return value

    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=session.w, height=session.h,
                        deviceScaleFactor=a.dpr, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(a.base.rstrip('/')+'/?'+urlencode({'data': a.data, 'sky': 1, 'probe': 1}))
        ready, elapsed, detail = session.wait_until(READY, 60)
        report['readiness'] = {'ready': ready, 'elapsedSeconds': elapsed, 'last': detail}
        if not ready:
            raise RuntimeError('cloud opening did not settle')
        if a.native:
            ev('CLApp.scene().setBoost(true)')
        ev('new Promise(r=>{let n=60;function tick(){if(--n)requestAnimationFrame(tick);else r(true);}requestAnimationFrame(tick);})')
        report['screenshots'] = {'before': session.shot(str(out/'page_before.png'))}
        report['idle'] = ev(PERF.replace('ROTATE', 'false'))
        report['rotating'] = ev(PERF.replace('ROTATE', 'true'))
        report['screenshots']['after'] = session.shot(str(out/'page_after.png'))
        report['readback'] = ev(READBACK)
        report['readback']['artifacts'] = {}
        for name, url in report['readback'].pop('images').items():
            path = out/(name+'.png'); path.write_bytes(base64.b64decode(url.split(',', 1)[1]))
            report['readback']['artifacts'][name] = str(path)
        report['ownership'] = ev(OWNERSHIP)
        report['modes'] = ev(MODES)
        report['health'] = ev(headless.POST_HEALTH_JS)
        report['contextHealthy'] = ev('!CLApp.scene().renderer.getContext().isContextLost()')
        h, px = report['health'], report['readback']
        report['checks'] = {'ready': ready, 'pixels': all(px[k] for k in ('deterministic', 'continuous', 'nonempty', 'details')),
            'isolatedShader': px['shaderErrors'] == [], 'modes': report['modes']['ok'], 'phaseResume': report['modes']['phaseResume']['ok'],
            'ownership': report['ownership']['ok'], 'contextHealthy': report['contextHealthy'],
            'health': h.get('jserr') == 'none' and h.get('jsrej') == 'none' and h.get('shaderErrors') == []
                and not h.get('missing') and not h.get('probeErrors') and not any(h.get('errorCounts', {}).values()),
            'realRotation': report['rotating']['rotationRadians'] > .005,
            'rendered': all(report[k]['rendererFrames'] >= 180 for k in ('idle', 'rotating'))}
        report['performanceTargetMet'] = all(report[k]['targetMet'] for k in ('idle', 'rotating'))
        report['performanceGate'] = 'report-only native resolution' if a.native else '50 fps idle and rotation'
        if not a.native:
            report['checks']['performance'] = report['performanceTargetMet']
        report['ok'] = all(report['checks'].values())
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        session.close()
        (out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'ok': report['ok'], 'checks': report['checks'], 'performanceTargetMet': report.get('performanceTargetMet'),
                     'performanceGate': report.get('performanceGate'), 'report': str(out/'report.json')}, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
