#!/usr/bin/env python3
"""Native 4K layer cost / same-frame field candidate comparison.

Diagnostic hidden layers are restored immediately and are never accepted as
performance changes. Candidate and baseline preserve scene/data coordinates.
"""
import argparse
import os
import base64
import hashlib
import json
from pathlib import Path

from atlas_review_shots import Session
import headless
from scene_native4k_perf_browser import SAMPLE

ROOT = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get('CL_BASELINES','/tmp/castline-shots/wave4-baselines'))

DENSITY_OWNER = r"""new Promise(function(resolve,reject){
  var S=CLApp.scene(),R=S.renderer,render=R.render,found=null,info=S.skyInfo();
  R.render=function(scene,camera){
    if(scene!==S.scene&&camera.isOrthographicCamera)scene.traverse(function(o){
      if(o.isPoints&&o.geometry.getAttribute('aCloudAxis'))found={scene:scene,camera:camera,target:R.getRenderTarget(),material:o.material};
    });
    return render.apply(R,arguments);
  };
  var name=info&&info.sectors&&info.sectors[0]&&(info.sectors[0].name||info.sectors[0].key);
  CLSkyDeep.hoverCamp(name||CLApp.graph().camps[0].name,true);
  requestAnimationFrame(function(){CLSkyDeep.hoverCamp(null,true);requestAnimationFrame(function(){
    R.render=render;window.__fieldDensity=found;found?resolve(true):reject(Error('density owner not observed'));
  });});
})"""

SETUP = r"""(function(){
  var S=CLApp.scene(), field={cosmos:[],nebula:null,records:[],hidden:null};
  S.scene.traverse(function(o){
    var m=o.material,u=m&&m.uniforms;if(!u)return;
    if(o.name==='sky-nebula-volume')field.nebula=o;
    if(o.renderOrder>=-300&&o.renderOrder<=-280&&u.uDriftT)field.cosmos.push(o);
  });
  if(!field.nebula||field.cosmos.length!==4)throw Error('field layer owners missing');
  var shadow={CLSkyTokens:CLSkyTokens,THREE:THREE};
  (new Function('window',BASE_COSMOS))(shadow);(new Function('window',BASE_NEBULA))(shadow);
  field.cosmos.forEach(function(o){
    var names=o.renderOrder===-300?['VC','FC']:o.renderOrder===-290?['VS','FS']:o.renderOrder===-285?['VG','FG']:['VD','FD'];
    field.records.push({object:o,material:o.material,vs:o.material.vertexShader,fs:o.material.fragmentShader,
      oldVS:shadow.CLSkyCosmosGLSL[names[0]],oldFS:shadow.CLSkyCosmosGLSL[names[1]]});
  });
  var m=field.nebula.material,steps=+(m.fragmentShader.match(/#define STEPS (\d+)/)||[])[1],oct=+(m.fragmentShader.match(/#define OCT (\d+)/)||[])[1];
  field.records.push({object:field.nebula,material:m,vs:m.vertexShader,fs:m.fragmentShader,oldVS:m.vertexShader,
    oldFS:shadow.CLSkyNebulaGLSL.volFrag(oct,CLSkyTokens.VOL.jitter,steps)});
  var density=window.__fieldDensity,newSplat=density.material.fragmentShader,oldSplat=shadow.CLSkyNebulaGLSL.SPLAT_FS;
  field.set=function(current){field.records.forEach(function(r){r.material.vertexShader=current?r.vs:r.oldVS;r.material.fragmentShader=current?r.fs:r.oldFS;r.material.needsUpdate=true;});
    density.material.fragmentShader=current?newSplat:oldSplat;density.material.needsUpdate=true;
    var target=S.renderer.getRenderTarget(),color=S.renderer.getClearColor(new THREE.Color()),alpha=S.renderer.getClearAlpha(),auto=S.renderer.autoClear;
    try{S.renderer.setRenderTarget(density.target);S.renderer.setClearColor(0,0);S.renderer.autoClear=false;S.renderer.clear(true,true,false);S.renderer.render(density.scene,density.camera);}
    finally{S.renderer.setRenderTarget(target);S.renderer.setClearColor(color,alpha);S.renderer.autoClear=auto;}
    if(field.nebula.userData.cloudSampler)field.nebula.userData.cloudSampler.render();
  };
  field.hide=function(layer){if(field.hidden){field.hidden();field.hidden=null;}var list=layer==='nebula'?[field.nebula]:layer==='cosmos'?field.cosmos:[];
    var visible=list.map(function(o){return o.visible;});var dispose=S.core().registerFrameHook(function(){list.forEach(function(o){o.visible=false;});});
    field.hidden=function(){dispose();list.forEach(function(o,i){o.visible=visible[i];});};};
  field.restore=function(){if(field.hidden){field.hidden();field.hidden=null;}field.set(true);};
  window.__fieldProbe=field;
  return {cosmosObjects:field.cosmos.length,nebulaSteps:steps,nebulaOct:oct,quality:S.quality(),deep:CLSkyDeep.stats()};
})()"""

CAPTURE = r"""new Promise(function(resolve){requestAnimationFrame(function(){
  var S=CLApp.scene(),C=S.core().getComposer(),R=S.renderer,field=__fieldProbe,before=S.digest().tAnim,images=[];
  var positions=CLApp.graph().characters.map(function(c){var n=S.nodeOf('c:'+c.name),p=n&&n.g.getWorldPosition(new THREE.Vector3());
    if(!p)return null;var world=p.toArray();p.project(S.camera);return {name:c.name,camp:c.camp,world:world,pixel:[(p.x*.5+.5)*R.domElement.width,(.5-p.y*.5)*R.domElement.height]};}).filter(Boolean);
  try{[false,true].forEach(function(current){field.set(current);C.render();images.push({kind:current?'candidate':'baseline',png:R.domElement.toDataURL('image/png')});});
    resolve({sameAnimationTime:before===S.digest().tAnim,time:before,camera:S.camera.position.toArray(),images:images,quality:S.quality(),roleCenters:positions,
      roleCoordinatesUnchanged:positions.every(function(p){return JSON.stringify(p.world)===JSON.stringify(S.nodeOf('c:'+p.name).g.getWorldPosition(new THREE.Vector3()).toArray());})});
  }finally{field.restore();}
});})"""


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',default='http://127.0.0.1:8137')
    ap.add_argument('--out',default=os.path.join(os.environ.get('CL_SHOTS','/tmp/castline-shots'),'wave4-zero-work'))
    ap.add_argument('--seconds',type=float,default=6)
    ap.add_argument('--baseline-dir',default=str(BASE))
    ap.add_argument('--profile-layers',action='store_true')
    ap.add_argument('--hover',default='')
    args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    session=Session(3840,2160);report={'canvas':[3840,2160],'pump':False,'baselineDir':args.baseline_dir,'samples':[],'diagnostics':[],
      'candidateSources':{n:hashlib.sha256((ROOT/'js/sky'/n).read_bytes()).hexdigest() for n in ['sky-cosmos.js','sky-cosmos-glsl.js','sky-nebula.js','sky-nebula-glsl.js']}}
    def ev(text,wait=False):
        value=session.eval(text,wait)
        if isinstance(value,dict) and value.get('__evalError'):raise RuntimeError(value)
        return value
    def delay(seconds):ev('new Promise(function(r){setTimeout(r,'+str(round(seconds*1000))+');})',True)
    def sample(label):
        s=ev(SAMPLE.replace('DURATION',str(round(args.seconds*1000))),True);s['kind']=label
        assert s['canvas']==[3840,2160] and s['quality']['degrade']==0 and not s['calm'] and s['glError']==0
        print(json.dumps({'kind':label,'fps':s['fps'],'p95':s['p95'],'animationSeconds':s['animationSeconds']},ensure_ascii=False),flush=True)
        return s
    try:
        session.start();session.ws.call('Emulation.setDeviceMetricsOverride',width=3840,height=2160,deviceScaleFactor=1,mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument',source=headless.HEALTH_INIT_JS)
        session.navigate(args.base+'/?data=data/cache/d16db79a529a1727352091d5.json&sky=1')
        ready,_,last=session.wait_until('({ready:!!(window.CLSkyDeep&&CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99&&CLSkyDeep.stats().nebula.alpha>.01&&CLSkyDeep.stats().stars.ignite>.99&&!document.getElementById("clSigil"))})',50)
        if not ready:raise RuntimeError(last)
        ev('CLApp.scene().setBoost(true);CLApp.scene().setDegrade(0)');delay(6)
        ev(DENSITY_OWNER,True);delay(.2)
        baseline=Path(args.baseline_dir)
        setup=SETUP.replace('BASE_COSMOS',json.dumps((baseline/'sky-cosmos-glsl.js').read_text())).replace('BASE_NEBULA',json.dumps((baseline/'sky-nebula-glsl.js').read_text()))
        report['setup']=ev(setup)
        if args.hover:ev('CLSkyDeep.hoverCamp('+json.dumps(args.hover)+')');delay(2)
        if args.profile_layers:
            for layer in ['all','nebula','cosmos','all']:
                ev('__fieldProbe.hide('+json.dumps(layer)+')');delay(1)
                report['diagnostics'].append(sample('diagnostic-hide-'+layer))
            ev('__fieldProbe.restore()')
        for current in [False,True,False]:
            ev('__fieldProbe.set('+('true' if current else 'false')+')');delay(2)
            report['samples'].append(sample('candidate' if current else 'baseline'))
        cap=ev(CAPTURE,True);assert cap['sameAnimationTime'];report['sameFrame']={k:v for k,v in cap.items() if k!='images'}
        for image in cap['images']:(out/(image['kind']+'.png')).write_bytes(base64.b64decode(image['png'].split(',',1)[1]))
        report['sameFrame']['images']=[str(out/(image['kind']+'.png')) for image in cap['images']]
        manual=ev('CLApp.scene().manualCalm()')
        ev('CLApp.scene().setCalm(true)');delay(.2)
        phase=ev('CLApp.scene().digest().tAnim')
        try:
            for current,kind in [(False,'baseline'),(True,'candidate')]:
                ev('__fieldProbe.set('+('true' if current else 'false')+')');delay(.25)
                session.shot(str(out/('product-'+kind+'.png')))
            report['productArt']={'frozenForUntimedArtOnly':True,'phase':phase,'samePhase':phase==ev('CLApp.scene().digest().tAnim'),
              'images':[str(out/'product-baseline.png'),str(out/'product-candidate.png')]}
        finally:
            ev('__fieldProbe.restore();CLApp.scene().setCalm('+('true' if manual else 'false')+')')
        report['health']=ev(headless.POST_HEALTH_JS.replace('window.__cl && window.__cl.scene','window.CLApp && window.CLApp.scene()'),True)
        h=report['health'];report['ok']=not h['missing'] and not h['probeErrors'] and not h['shaderErrors'] and not any(h['errorCounts'].values()) and h['jserr']=='none' and h['jsrej']=='none'
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'saved':str(out/'report.json'),'ok':report['ok']},ensure_ascii=False),flush=True)
        assert report['ok']
    finally:session.close()


if __name__=='__main__':main()
