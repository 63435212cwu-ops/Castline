#!/usr/bin/env python3
"""Native-4K same-scene A/B for derivative-filtered crystal microdetail.

Performance is report-only: real animation and auto-rotation, no pump/fixedDt,
3840x2160, six crystal steps and the production MSAA resolve. Records the actual
unmasked renderer rather than assuming a GPU backend from launch flags.
"""
import argparse
import base64
import json
from pathlib import Path

from atlas_review_shots import Session
from scene_native4k_perf_browser import SAMPLE
import headless

SETUP = r"""(function(){
 var S=CLApp.scene(),C=S.core().getComposer(),current=CLSceneMats.CROWN_BASE_FS;
 var start=current.indexOf('    vec3 microDx ='),end=current.indexOf('    float ndl =',start);
 if(start<0||end<start)throw Error('missing microdetail filter');
 var prior=current.slice(0,start)+
 '    float str1 = sin(pm.y * 46.0 + vn3(pm * 0.14) * 3.2);\n'+
 '    float str2 = sin((pm.x * 0.707 + pm.z * 0.707) * 118.0 + pm.y * 26.0);\n'+
 '    float str3 = cos((pm.x * -0.5 + pm.z * 0.866) * 250.0 + sin(pm.y * 64.0) * 0.7);\n'+
 '    float microNeedle = pow(max(0.0, str1 * 0.36 + str2 * 0.38 + str3 * 0.26), 4.5);\n'+current.slice(end);
 var entries=[];S.scene.traverse(function(o){if(o.material&&o.material.fragmentShader===current)entries.push(o);});
 if(entries.length!==2)throw Error('expected two base crystal layers: '+entries.length);
 var geometries=entries.map(function(o){return o.geometry.uuid;}),model=JSON.stringify(S.gemModel());
 var position=S.camera.position.clone(),target=S.controls.target.clone();
 window.__microAB={
  use:function(mode){entries.forEach(function(o){var s=mode==='baseline'?prior:current;if(o.material.fragmentShader!==s){o.material.fragmentShader=s;o.material.needsUpdate=true;}});C.render();},
  reset:function(){S.controls.autoRotate=false;S.camera.position.copy(position);S.controls.target.copy(target);S.camera.lookAt(target);S.controls.update();},
  integrity:function(){return {geometryUnchanged:JSON.stringify(geometries)===JSON.stringify(entries.map(function(o){return o.geometry.uuid;})),modelUnchanged:model===JSON.stringify(S.gemModel()),steps:entries.map(function(o){return o.material.uniforms.uSteps.value;}),shaderErrors:S.shaderErrors(),glError:S.renderer.getContext().getError()};}
 };
 var gl=S.renderer.getContext(),ex=gl.getExtension('WEBGL_debug_renderer_info');
 return {renderer:gl.getParameter(gl.RENDERER),vendor:gl.getParameter(gl.VENDOR),version:gl.getParameter(gl.VERSION),unmaskedRenderer:ex?gl.getParameter(ex.UNMASKED_RENDERER_WEBGL):null,unmaskedVendor:ex?gl.getParameter(ex.UNMASKED_VENDOR_WEBGL):null,userAgent:navigator.userAgent,hardwareConcurrency:navigator.hardwareConcurrency,devicePixelRatio:devicePixelRatio};
})()"""

PAIR = r"""new Promise(function(resolve){requestAnimationFrame(function(){
 var S=CLApp.scene(),time=S.digest().tAnim,images=[],b=S.crownScreenBounds();
 var crop=[Math.max(0,Math.floor(b.left)-25),Math.max(0,Math.floor(b.top)-25),Math.min(3840,Math.ceil(b.right)+25),Math.min(2160,Math.ceil(b.bottom)+25)];
 var canvas=document.createElement('canvas');canvas.width=crop[2]-crop[0];canvas.height=crop[3]-crop[1];var ctx=canvas.getContext('2d');
 ['baseline','candidate'].forEach(function(mode){__microAB.use(mode);ctx.drawImage(S.renderer.domElement,crop[0],crop[1],canvas.width,canvas.height,0,0,canvas.width,canvas.height);images.push({mode:mode,detail:canvas.toDataURL('image/png')});});
 resolve({sameAnimationTime:time===S.digest().tAnim,crop:crop,images:images});
});})"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8821')
    ap.add_argument('--data', default='data/cache/d16db79a529a1727352091d5.json')
    ap.add_argument('--out', default='/tmp/castline-shots/gem-microdetail-ab')
    ap.add_argument('--seconds', type=float, default=4)
    args = ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    session=Session(3840,2160)
    report={'viewport':[3840,2160,1],'pump':False,'samples':[]}
    def ev(expr,wait=False):
        result=session.eval(expr,wait)
        if isinstance(result,dict) and result.get('__evalError'):raise RuntimeError(result)
        return result
    def delay(seconds):ev('new Promise(function(r){setTimeout(r,'+str(round(seconds*1000))+');})',True)
    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride',width=3840,height=2160,deviceScaleFactor=1,mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument',source=headless.HEALTH_INIT_JS)
        session.navigate(args.base+'/?sky=1&data='+args.data)
        ready,_,state=session.wait_until('({ready:!!(window.CLApp&&CLApp.graph()&&CLApp.scene()&&window.CLSky&&document.querySelector("#loader.off"))})',45)
        if not ready:raise RuntimeError(state)
        delay(6);ev('CLSky.openCompass(CLApp.graph().characters[0].name)');delay(5)
        ev('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)');delay(4)
        report['environment']=ev(SETUP)
        ev('CLApp.scene().setCalm(true);__microAB.use("baseline")');delay(1)
        ev('__microAB.use("candidate")');delay(1)
        pair=ev(PAIR,True)
        assert pair['sameAnimationTime']
        for image in pair.pop('images'):
            (out/(image['mode']+'-detail.png')).write_bytes(base64.b64decode(image['detail'].split(',',1)[1]))
        report['sameFrame']=pair
        ev('CLApp.scene().setCalm(false)');delay(2)
        for mode in ['baseline','candidate','baseline','candidate']:
            ev('__microAB.use('+json.dumps(mode)+');__microAB.reset();CLApp.scene().controls.autoRotate=true;CLApp.scene().controls.autoRotateSpeed=.35')
            delay(2)
            sample=ev(SAMPLE.replace('DURATION',str(round(args.seconds*1000))),True)
            integrity=ev('__microAB.integrity()')
            assert sample['canvas']==[3840,2160] and sample['quality']['degrade']==0 and not sample['calm']
            assert sample['requestedSamples']==2 and sample['directResolve'] and sample['glError']==0
            assert sample['animationSeconds']>args.seconds*.8 and sample['cameraBefore']!=sample['cameraAfter']
            assert integrity['geometryUnchanged'] and integrity['modelUnchanged'] and integrity['steps']==[6,6] and not integrity['shaderErrors'] and integrity['glError']==0
            sample['mode']=mode;report['samples'].append(sample)
            print(json.dumps({'mode':mode,'fps':sample['fps'],'p95':sample['p95'],'integrity':integrity}),flush=True)
        ev('__microAB.use("candidate")')
        report['integrity']=ev('__microAB.integrity()')
        report['health']=ev('({errors:__headlessHealth.jserr,rejections:__headlessHealth.jsrej,frameErrors:CLApp.scene().core().perf().frameHooks.errors})')
        report['ok']=not report['health']['errors'] and not report['health']['rejections'] and report['health']['frameErrors']==0
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'ok':report['ok'],'environment':report['environment'],'report':str(out/'report.json')},ensure_ascii=False),flush=True)
        assert report['ok']
    finally:session.close()


if __name__=='__main__':main()
