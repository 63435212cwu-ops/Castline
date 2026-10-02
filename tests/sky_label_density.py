#!/usr/bin/env python3
"""Q9.2：大书真实字框、推近增名、远景主星、静置稳定、反复推拉、低档和减弱动效。"""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BOOKS=[('sanguo','data/cache/a935953b2678a80b352091d5.json'),('dafeng','data/cache/2ef47b2ecaa99a67352091d5.json')]
PROBE=r"""(async function(){var W=function(t){return new Promise(function(r){setTimeout(r,t);});},S=CLApp.scene(),G=CLApp.graph(),C=S.controls,base=null,out={samples:[]};await W(6500);base=S.camera.position.clone().sub(C.target);var count=[G.characters.length,G.relations.length,G.events.length],leads={};S.skyInfo().sectors.forEach(function(s){leads[s.lead]=1;});
function measure(){var names=[],boxes=[],overlap=[];[].forEach.call(document.querySelectorAll('#labels .cl-lab.char.on'),function(e){var st=getComputedStyle(e),b=e.getBoundingClientRect(),name=e.querySelector('.ln').textContent;if(st.visibility==='hidden'||+st.opacity<.1||b.width<=0)return;names.push(name);boxes.push({name:name,x:b.left,y:b.top,w:b.width,h:b.height});});for(var i=0;i<boxes.length;i++)for(var j=i+1;j<boxes.length;j++){var a=boxes[i],b=boxes[j];if(a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y)overlap.push([a.name,b.name]);}names.sort();return {names:names,overlap:overlap,policy:CLSkyLabels.stats(),lod:S.lod()};}
async function zoom(k){S.camera.position.copy(C.target).add(base.clone().multiplyScalar(k));C.update();await W(2300);return measure();}
out.far=await zoom(1.5);out.near=await zoom(.55);for(var i=0;i<6;i++){await W(300);out.samples.push(measure());}
out.repeated=[];for(var i=0;i<3;i++){out.repeated.push({far:await zoom(1.5),near:await zoom(.55)});}
out.rotation=[];C.autoRotate=true;C.autoRotateSpeed=2;await W(250);for(var i=0;i<12;i++){await W(100);out.rotation.push(measure());}C.autoRotate=false;await W(500);S.setDegrade(2);await W(200);out.low=measure();S.setDegrade(0);document.body.classList.add('skylab-still');out.reducedFar=await zoom(1.5);out.reducedNear=await zoom(.55);out.truth=G.characters.map(function(c){return c.name;});out.leads=Object.keys(leads);out.count=count;out.after=[G.characters.length,G.relations.length,G.events.length];out.size=[innerWidth,innerHeight];return JSON.stringify(out);})()"""
def main():
 p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8765');p.add_argument('--books',default='sanguo,dafeng');p.add_argument('--size',default='1440x900');p.add_argument('--dpr',default='1');p.add_argument('--out',default='/tmp/xingxi-label-density');a=p.parse_args();folder=Path(a.out);folder.mkdir(parents=True,exist_ok=True);passed=total=0
 if os.environ.get('CL_GPU')!='1':raise SystemExit('CL_GPU=1 required')
 for book,data in BOOKS:
  if book not in a.books.split(','):continue
  r=subprocess.run([sys.executable,'-s',str(ROOT/'tests/headless.py'),'sky=1&probe=1&data='+data,'--url',a.base+'/','--size',a.size,'--dpr',a.dpr,'--eval',PROBE],cwd=ROOT,env=os.environ,capture_output=True,text=True);(folder/(book+'.log')).write_text(r.stdout+'\n'+r.stderr);o={};healthy=False
  for line in r.stdout.splitlines():
   if line.startswith('EVAL:'):v=json.loads(line[5:]);o=json.loads(v) if isinstance(v,str) else v
   if line.startswith('POST-HEALTH:'):healthy=json.loads(line.split(':',1)[1]).get('ok') is True
  far=o.get('far',{}).get('names',[]);near=o.get('near',{}).get('names',[]);truth=set(o.get('truth',[]));leads=set(o.get('leads',[]));samples=o.get('samples',[]);repeated=o.get('repeated',[]);allsets=[o.get(k,{}) for k in ['far','near','low','reducedFar','reducedNear']]+samples+o.get('rotation',[])+[s for pair in repeated for s in [pair['far'],pair['near']]]
  checks=[('health and viewport',r.returncode==0 and healthy and o.get('size')==list(map(int,a.size.split('x')))),('far view only real group leads',bool(far) and set(far)<=leads),('zooming in reveals more real names',len(near)>len(far)+4 and set(near)<=truth),('actual label rectangles never overlap',bool(o) and all(not s.get('overlap') for s in allsets)),('resting name set stays stable',len(samples)==6 and all(s['names']==samples[0]['names'] for s in samples)),('repeated far/near cycles keep the policy',len(repeated)==3 and all(set(p['far']['names'])<=leads and len(p['near']['names'])>len(p['far']['names'])+4 for p in repeated)),('rotating does not admit new labels into the moving view',len(o.get('rotation',[]))==12 and all(set(s['names'])<=set(repeated[-1]['near']['names']) for s in o.get('rotation',[]))),('low tier and reduced motion preserve real names',bool(o.get('low',{}).get('names')) and set(o['low']['names'])<=truth and len(o.get('reducedNear',{}).get('names',[]))>len(o.get('reducedFar',{}).get('names',[]))+4),('graph counts stay intact',bool(o.get('count')) and o['count']==o.get('after'))]
  print('DATA '+book+' '+json.dumps({'far':len(far),'near':len(near),'stable':[len(s['names']) for s in samples],'cycles':[[len(x['far']['names']),len(x['near']['names'])] for x in repeated],'farWrong':list(set(far)-leads)},ensure_ascii=False),flush=True)
  for name,ok in checks:total+=1;passed+=bool(ok);print(('PASS ' if ok else 'FAIL ')+book+' '+name,flush=True)
  if r.returncode:print(r.stdout[-1200:]+r.stderr[-400:])
 print('SKY-LABEL-DENSITY '+('OK' if total and passed==total else 'FAIL')+' · '+str(passed)+'/'+str(total));return 0 if total and passed==total else 1
if __name__=='__main__':raise SystemExit(main())
