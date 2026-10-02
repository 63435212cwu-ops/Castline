#!/usr/bin/env python3
"""Q4.7：两面轴签内容、旋转/缩放中真实文字框、首尾刻度可读性。

CL_GPU=1 python3 -s tests/sky_axis_layout.py --base http://127.0.0.1:8765
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
BOOKS = [('saga','data/sample-saga.json'),('sanguo','data/cache/a935953b2678a80b352091d5.json'),('dafeng','data/cache/2ef47b2ecaa99a67352091d5.json')]
PROBE = r"""(async function(){
  var W=function(ms){return new Promise(function(r){setTimeout(r,ms);});},S=CLApp.scene(),out={size:[innerWidth,innerHeight]};
  function rect(el){var b=el.getBoundingClientRect();return [b.left,b.top,b.right,b.bottom];}
  function visible(el){var c=getComputedStyle(el),o=+c.opacity,m=/opacity\(([\d.]+)\)/.exec(c.filter);return el.classList.contains('on')&&o*(m?+m[1]:1)>.05;}
  function labels(){
    var list=Array.prototype.filter.call(document.querySelectorAll('#labels .cl-lab.gem-slot'),visible).map(function(el){return {name:el.querySelector('.ln').textContent,kind:el.classList.contains('attr')?'attr':'meta',box:rect(el)};}),clash=[],outside=[];
    list.forEach(function(a,i){if(a.box[0]<-1||a.box[1]<-1||a.box[2]>innerWidth+1||a.box[3]>innerHeight+1)outside.push(a.name);list.slice(i+1).forEach(function(b){if(Math.min(a.box[2],b.box[2])-Math.max(a.box[0],b.box[0])>1&&Math.min(a.box[3],b.box[3])-Math.max(a.box[1],b.box[1])>1)clash.push([a.name,b.name]);});});
    return {n:list.length,attr:list.filter(function(a){return a.kind==='attr';}).length,meta:list.filter(function(a){return a.kind==='meta';}).length,clash:clash,outside:outside};
  }
  function content(){
    var model=S.gemModel(),bad=[],n=0;
    [['attr','a:',model.attr],['meta','m:',model.meta]].forEach(function(f){f[2].forEach(function(d){n++;var nd=S.nodeOf(f[1]+d.key),el=nd&&nd.el,lv=el&&el.querySelector('.lv');if(!el||el.querySelector('.ln').textContent!==d.key||el.getAttribute('data-known')!==String(d.known)||(d.known?(el.getAttribute('data-score')!==String(d.score)||!lv||+lv.textContent!==Math.round(d.score)):(el.hasAttribute('data-score')||!!lv||el.textContent.indexOf('待建档')<0)))bad.push(d.key);});});
    return {n:n,bad:bad};
  }
  function ticks(){
    var els=Array.prototype.filter.call(document.querySelectorAll('.sky-disc .sd-num'),function(el){return +getComputedStyle(el).opacity>.05;}),rows=els.map(function(el){return {text:el.textContent,box:rect(el)};}),bad=[],seam=null;
    rows.forEach(function(a,i){rows.slice(i+1).forEach(function(b){var dy=Math.min(a.box[3],b.box[3])-Math.max(a.box[1],b.box[1]),gap=Math.max(b.box[0]-a.box[2],a.box[0]-b.box[2]);if(dy>1&&gap<6)bad.push([a.text,b.text,gap]);});});
    var first=rows.filter(function(a){return a.text==='1';})[0],last=rows.filter(function(a){return a.text==='900';})[0];if(first&&last)seam=Math.max(first.box[0]-last.box[2],last.box[0]-first.box[2]);
    return {n:rows.length,bad:bad,seam:seam,values:rows.map(function(a){return a.text;})};
  }
  await W(6500);var G=CLApp.graph(),hero=G.characters.slice().sort(function(a,b){return (b.importance||0)-(a.importance||0);})[0].name;out.book=G.title;
  CLSky.setPlot(true);await W(3300);out.plot=[ticks()];
  CLSkyDeep.nudge(.6,.25);await W(1300);out.plot.push(ticks());
  CLSkyDeep.resetView();await W(1400);CLSky.setPlot(false);await W(1300);
  CLSky.openCompass(hero);await W(4000);out.content=content();out.front=labels();out.turns=[];out.motion=[];
  for(var i=0;i<8;i++){
    CLSkyDeep.nudge(Math.PI/4,0);
    for(var f=0;f<5;f++){await W(100);out.motion.push(labels());}
    await W(600);out.turns.push(labels());
  }
  var center=S.controls.target.clone(),home=S.camera.position.clone(),dir=home.clone().sub(center);out.zoom=[];
  for(var k=0;k<2;k++){S.flyTo(center.clone().add(dir.clone().multiplyScalar(k?.8:1.2)),center,.5);await W(1600);out.zoom.push(labels());}
  S.flyTo(home,center,.5);await W(1400);S.setFace('under');await W(3000);out.under=labels();out.contentUnder=content();
  S.setCalm(true);await W(1000);out.calm=labels();out.face=S.face();out.mode=CLSky.state().mode;
  return JSON.stringify(out);
})()"""


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',default='http://127.0.0.1:8765')
    ap.add_argument('--books',default='saga,sanguo,dafeng')
    ap.add_argument('--sizes',default='1440x900,390x844')
    ap.add_argument('--out',default='/tmp/xingxi-axis-layout')
    args=ap.parse_args();outdir=Path(args.out);outdir.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ);env.setdefault('CL_GPU','1');passed=total=0
    for book,data in BOOKS:
        if book not in args.books.split(','):continue
        for size in args.sizes.split(','):
            result=subprocess.run([sys.executable,'-s',str(ROOT/'tests/headless.py'),'sky=1&probe=1&data='+data,'--url',args.base+'/','--size',size,'--timeout','240','--eval',PROBE],cwd=ROOT,env=env,text=True,capture_output=True)
            (outdir/(book+'-'+size+'.log')).write_text(result.stdout+'\n'+result.stderr)
            value={};healthy=False
            for line in result.stdout.splitlines():
                if line.startswith('EVAL:'):
                    raw=json.loads(line[5:]);value=json.loads(raw) if isinstance(raw,str) else raw
                if line.startswith('POST-HEALTH:'):healthy=json.loads(line.split(':',1)[1]).get('ok') is True
            width,height=map(int,size.split('x'));narrow=width<=900;want=8 if narrow else 16
            still=[value.get('front',{})]+value.get('turns',[])+value.get('zoom',[])+[value.get('under',{}),value.get('calm',{})]
            moving=value.get('motion',[])
            checks=[('exact viewport and health',result.returncode==0 and healthy and value.get('size')==[width,height]),('all 16 dimensions match model',all(value.get(k,{}).get('n')==16 and not value.get(k,{}).get('bad') for k in ('content','contentUnder'))),('axes all present after turns and zoom',len(still)==13 and all(s.get('n')==want for s in still)),('visible axes stay inside screen',bool(still) and all(not s.get('outside') for s in still+moving)),('actual text boxes never overlap',len(moving)==40 and all(not s.get('clash') for s in still+moving)),('both faces available',value.get('face')=='under' and value.get('mode')=='compass' and value.get('front',{}).get('attr')==8 and value.get('under',{}).get('meta')==8),('chapter numbers separated',len(value.get('plot',[]))==2 and all(s.get('n',0)>0 and not s.get('bad') for s in value.get('plot',[])))]
            if book=='dafeng':checks.append(('chapter 1 and 900 remain readable',all(s.get('seam',-1)>=6 and '1' in s.get('values',[]) and '900' in s.get('values',[]) for s in value.get('plot',[]))))
            print('DATA '+book+' '+size+' '+json.dumps({'front':value.get('front'),'under':value.get('under'),'zoom':value.get('zoom'),'plot':value.get('plot'),'collisionFrames':[i for i,s in enumerate(moving) if s.get('clash')],'counts':[s.get('n') for s in still]},ensure_ascii=False),flush=True)
            for name,ok in checks:
                total+=1;passed+=bool(ok);print(('PASS ' if ok else 'FAIL ')+book+' '+size+' '+name,flush=True)
            if result.returncode:print(result.stdout[-2000:]+result.stderr[-1000:])
    print('SKY-AXIS-LAYOUT '+('OK' if total and passed==total else 'FAIL')+' · '+str(passed)+'/'+str(total))
    return 0 if total and passed==total else 1


if __name__=='__main__':raise SystemExit(main())
