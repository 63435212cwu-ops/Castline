#!/usr/bin/env python3
"""Real MQL/manual/Lab pause and crown reuse regression. Run in serial GPU slot.
The initialization hook only observes the actual crown; no clocks are pumped.
Snapshot overlays are optional; default reads the current product.
"""
from pathlib import Path
import sys,time,json,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from atlas_review_shots import Session,headless
from compass_entry_profile import Events
ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path);ap.add_argument('--base',default='http://127.0.0.1:8765');ap.add_argument('--out',type=Path,required=True);ap.add_argument('--initial-reduced',action='store_true');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
s=Session(1280,800);report={'samples':[],'checks':{},'overlay':[],'snapshot':str(a.snapshot),'initialReduced':a.initial_reduced}
HOOK='''(()=>{let lib;Object.defineProperty(window,'CLSceneLodLabels',{configurable:true,get(){return lib},set(v){const create=v.create;v.create=function(o){window.__crownRead=o.getCrown;return create.apply(this,arguments)};lib=v}})})()'''
STATE='''(()=>{const S=CLApp.scene(),C=S.core(),cr=__crownRead(),b=[];S.scene.traverse(o=>{const m=o.material;if(m&&m.userData&&['薄荷绿柱','紫晶'].includes(m.userData.gemName))b.push({name:m.userData.gemName,time:m.uniforms.uTime.value,on:m.uniforms.uOn.value,wire:m.uniforms.uWire.value});});return {calm:S.calm(),manual:S.manualCalm?S.manualCalm():null,system:matchMedia('(prefers-reduced-motion: reduce)').matches,tAcc:C.getTAcc(),tAnim:C.getTAnim(),model:S.gemModel(),base:b,scan:cr?[cr.scan.position.y,cr.scan2.position.y,cr.scan2.scale.x]:null,mode:CLSky.state().mode,lab:CLSkyLab.modes().still,errors:S.shaderErrors()}})()'''
def ev(js,wait=False):
 v=s.eval(js,await_promise=wait)
 if isinstance(v,dict) and v.get('__evalError'):raise RuntimeError(v)
 return v
def delay(ms):ev('new Promise(r=>setTimeout(r,%d))'%ms,True)
def sample(name):
 v=ev(STATE);v['name']=name;report['samples'].append(v);return v
def media(reduce):s.ws.call('Emulation.setEmulatedMedia',features=[{'name':'prefers-reduced-motion','value':'reduce' if reduce else 'no-preference'}])
BASE_NAMES={'薄荷绿柱','紫晶'}
def base_targets_ok(state):
 return isinstance(state['base'],list) and len(state['base'])==2 and set(m['name'] for m in state['base'])==BASE_NAMES
def quiet_pair(name):
 delay(600);x=sample(name+'-a');delay(900);y=sample(name+'-b');report['checks'][name]=bool(base_targets_ok(x) and base_targets_ok(y) and x['calm'] and y['calm'] and x['tAnim']==y['tAnim'] and isinstance(x['scan'],list) and x['scan']==y['scan'] and [m['time'] for m in x['base']]==[m['time'] for m in y['base']] and y['tAcc']>x['tAcc']+.2);return y
try:
 s.start()
 if a.snapshot:Events(s.ws,a.snapshot,report)
 s.ws.call('Page.addScriptToEvaluateOnNewDocument',source=headless.HEALTH_INIT_JS+'\n'+HOOK)
 if a.initial_reduced:media(True)
 s.navigate(a.base.rstrip('/')+'/?sky=1&probe=1&data=data/cache/d16db79a529a1727352091d5.json')
 until=time.monotonic()+45
 while time.monotonic()<until:
  if ev('!!(window.CLSkyDeep&&CLSkyDeep.stats().inited&&CLSkyDeep.stats().stars.ignite>.99&&!document.getElementById("clSigil"))'):break
  time.sleep(.2)
 else:raise RuntimeError('not ready')
 delay(3000);ev('CLSky.openCompass("孙悟空")');delay(3300);ref=sample('entry');report['checks']['base-probe-targets']=base_targets_ok(ref)
 if a.initial_reduced:quiet_pair('initial-system');media(False);delay(300)
 media(True);frozen=quiet_pair('dynamic-system')
 ev('window.__firstResume=null;window.__motionRead='+ '()=>'+STATE+';window.__motionQuery=matchMedia("(prefers-reduced-motion: reduce)");window.__resumeListener=()=>{if(!__motionQuery.matches)requestAnimationFrame(()=>window.__firstResume=__motionRead())};__motionQuery.addEventListener("change",__resumeListener)')
 media(False);delay(300);res=ev('__firstResume');report['resumeFirst']=res;report['checks']['continuous-resume']=bool(res and not res['calm'] and 0<=res['tAnim']-frozen['tAnim']<=.100001);ev('__motionQuery.removeEventListener("change",__resumeListener)')
 ev('CLApp.scene().setCalm(true)');media(True);quiet_pair('manual-plus-system');media(False);quiet_pair('manual-retained');ev('CLApp.scene().setCalm(false)');delay(300);report['checks']['manual-release']=not sample('manual-released')['calm']
 media(True);ev('CLSkyLab.setMode("still",true)');quiet_pair('lab-plus-system');ev('CLSkyLab.setMode("still",false)');quiet_pair('system-after-lab');media(False);delay(300);report['checks']['system-release-after-lab']=not sample('lab-closed-system-released')['calm']
 ev('CLSkyLab.setMode("still",true)');ev('CLApp.scene().setCalm(true)');ev('CLSkyLab.setMode("still",false)');quiet_pair('manual-after-lab');ev('CLApp.scene().setCalm(false);CLSkyLab.open(false)');delay(200)
 media(True);delay(400);ev('window.__savedBridge=CLApp.atlas.state();CLApp.atlas.restore(__savedBridge)');delay(300);media(False);delay(300);snap=sample('snapshot-restored');report['checks']['snapshot-not-stuck']=not snap['calm'] and snap['manual'] is False
 media(True);delay(1300);ev('CLSky.closeCompass()');delay(600);ev('CLSky.openCompass("猪八戒")');delay(3000);born=quiet_pair('new-crown-while-quiet');report['checks']['new-content-visible']=born['mode']=='compass' and len(born['base'])==2 and all(m['on']>.5 and m['wire']==0 for m in born['base'])
 media(False);delay(500);ev('CLSky.openCompass("孙悟空")');delay(3000);last=sample('reused-crown');report['checks']['reuse-model-stable']={k:v for k,v in last['model'].items() if k!='stats'}=={k:v for k,v in ref['model'].items() if k!='stats'};report['checks']['no-shader-errors']=all(not x['errors'] for x in report['samples']);report['health']=headless.post_health(s.ws,[]);report['ok']=report['health']==0 and all(report['checks'].values());print(json.dumps({'ok':report['ok'],'checks':report['checks']}),flush=True)
finally:
 (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));s.close()
raise SystemExit(0 if report.get('ok') else 1)
