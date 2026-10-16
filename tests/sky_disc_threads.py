#!/usr/bin/env python3
"""Q4.3：真实光丝像素、弧/星同源、参与者真实性、降级与无泄漏。

数据语义（2026-10-04 收口，与 tests/atlas_aggregate_browser.py 同族）：
e14f706 给大奉/三国/西游三本缓存写入 8 条 auto-main 占位来源线（全主线、无支线/末梢），
d7313df 时三本 storylines 为空走推导路径。v41 严格来源结构下，星盘模型 CLSkyModel 的
M.lines（支线车道）只收非主线——占位书上 lines=0、具名车道=0 是**数据契约**，不是引擎退化。
README「星盘」行的最高语义是『悬停一条线 → 参与者在星座里点亮并连线』（不分主/支），
实现上 disc.emph() 对任意 byId 线（含主线段）都挂参与者光丝。因此套件两相同源执行同一套
物理断言：有具名支线（saga 手工线：支线/末梢来源）悬停具名支线；无支线来源（sanguo/dafeng）
悬停参与者最多的真实主线段，README 语义必须同样成立；另加一条由数据文件推导的族系钉——
来源里有支线 ⇔ M.lines 非空且具名车道 >0、悬停对象为具名支线；无支线 ⇔ M.lines 为空、
具名车道 0、主线段数 == 数据里主线来源条数、悬停对象为主线段。"""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path('/Users/carmen/Desktop/星系')
BOOKS=[('saga','data/sample-saga.json'),('sanguo','data/cache/a935953b2678a80b352091d5.json'),('dafeng','data/cache/2ef47b2ecaa99a67352091d5.json')]
PROBE=r"""(async function(){
 var W=function(ms){return new Promise(function(r){setTimeout(r,ms);});},S=CLApp.scene(),D=CLSky.disc(),M=CLSky.model(),G=CLApp.graph(),T=CLApp.story(),out={};
 var named=M.lines.filter(function(l){return l.named&&l.cast.length;}).sort(function(a,b){return b.cast.length-a.cast.length;});
 var mains=M.mains.filter(function(l){return l.cast.length;}).sort(function(a,b){return b.cast.length-a.cast.length;});
 var line=named[0]||mains[0];
 out.contract={src:T&&T.src,strict:!!(T&&T.strictTopology),threads:T&&T.threads.length,mains:M.stats?M.stats.mains:M.mains.length,branchLines:M.lines.length,namedLanes:M.stats?M.stats.named:null,hover:named[0]?'named':'main'};
 if(!line)return JSON.stringify(out);
 await W(6000);CLSky.setPlot(true);await W(3200);S.setDegrade(0);CLSky.hoverLine(String(line.id));await W(400);
 function sample(){var st=D.tetherStats(),desc=D.desc(),an=D.anchor(),width=innerWidth,height=innerHeight,starErr=0,arcErr=0;st.routes.forEach(function(r){var n=S.nodeOf('c:'+r.name),v=new THREE.Vector3();n.g.getWorldPosition(v);v.project(S.camera);starErr=Math.max(starErr,Math.hypot(r.b[0]-(v.x*.5+.5)*width,r.b[1]-(-v.y*.5+.5)*height));var it=desc.items.filter(function(x){return x.id===r.line;})[0],near=Infinity,num=Math.max(2,Math.ceil(Math.abs(it.a1-it.a0)/(Math.PI/90))+1);for(var k=0;k<num;k++){var a=it.a0+(it.a1-it.a0)*k/(num-1),p=new THREE.Vector3(it.r*Math.cos(a),it.r*Math.sin(a),it.z);an.localToWorld(p);p.project(S.camera);near=Math.min(near,Math.hypot(r.a[0]-(p.x*.5+.5)*width,r.a[1]-(-p.y*.5+.5)*height));}arcErr=Math.max(arcErr,near);});return {state:st,starErr:starErr,arcErr:arcErr};}
 out.start=sample();out.realNames=out.start.state.routes.every(function(r){return line.cast.indexOf(r.name)>=0;});out.dom=D.el.querySelectorAll('.sd-tether').length;out.cast=line.cast.length;out.counts=[G.characters.length,G.relations.length,G.events.length];
 var R=S.renderer,target=S.scene.getObjectByName('sky-disc-threads'),rt=new THREE.WebGLRenderTarget(innerWidth,innerHeight),isolated=new THREE.Scene(),copy=new THREE.Mesh(target.geometry,target.material),pixels=new Uint8Array(innerWidth*innerHeight*4),oldRT=R.getRenderTarget(),color=R.getClearColor(new THREE.Color()).clone(),alpha=R.getClearAlpha();copy.frustumCulled=false;isolated.add(copy);
 try{R.setRenderTarget(rt);R.setClearColor(0,0);R.clear();R.render(isolated,S.camera);R.readRenderTargetPixels(rt,0,0,innerWidth,innerHeight,pixels);var peak=0,n=0;for(var i=0;i<pixels.length;i+=4){var v=Math.max(pixels[i],pixels[i+1],pixels[i+2]);peak=Math.max(peak,v);if(v>5)n++;}out.pixels={peak:peak,lit:n,glError:R.getContext().getError()};}finally{R.setRenderTarget(oldRT);R.setClearColor(color,alpha);rt.dispose();}
 S.controls.autoRotate=true;S.controls.autoRotateSpeed=6;await W(650);out.spin=sample();S.controls.autoRotate=false;
 var t0=out.spin.state.time;await W(250);out.flowAdvance=D.tetherStats().time-t0;
 document.body.classList.add('skylab-still');await W(150);out.reduced=D.tetherStats();document.body.classList.remove('skylab-still');S.setDegrade(2);await W(200);out.low=D.tetherStats();S.setDegrade(0);await W(150);out.high=D.tetherStats();
 var n0=Object.assign({},R.info.memory);for(var k=0;k<20;k++){CLSky.hoverLine(null);CLSky.hoverLine(String(line.id));}await W(150);out.memory={before:n0,after:Object.assign({},R.info.memory)};
 CLSky.hoverLine(null);await W(100);out.clear=D.tetherStats();CLSky.seek(Math.floor(M.nCh/2));await W(250);out.cursor=D.tetherStats();CLSky.setPlot(false);await W(1300);out.hidden=D.tetherStats();out.after=[G.characters.length,G.relations.length,G.events.length];return JSON.stringify(out);
})()"""
def main():
 p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8765');p.add_argument('--out',default='/tmp/xingxi-threads');p.add_argument('--books',default='saga,sanguo,dafeng');p.add_argument('--size',default='1440x900');p.add_argument('--dpr',default='1');a=p.parse_args();outdir=Path(a.out);outdir.mkdir(parents=True,exist_ok=True);passed=total=0
 if os.environ.get('CL_GPU')!='1':raise SystemExit('CL_GPU=1 required')
 for book,data in BOOKS:
  if book not in a.books.split(','):continue
  r=subprocess.run([sys.executable,'-s',str(ROOT/'tests/headless.py'),'sky=1&probe=1&data='+data,'--url',a.base+'/','--size',a.size,'--dpr',a.dpr,'--eval',PROBE],cwd=ROOT,env=os.environ,capture_output=True,text=True)
  (outdir/(book+'.log')).write_text(r.stdout+'\n'+r.stderr);o={};health=False
  for line in r.stdout.splitlines():
   if line.startswith('EVAL:'):v=json.loads(line[5:]);o=json.loads(v) if isinstance(v,str) else v
   if line.startswith('POST-HEALTH:'):health=json.loads(line.split(':',1)[1]).get('ok') is True
  st=o.get('start',{});state=st.get('state',{});sp=o.get('spin',{});px=o.get('pixels',{});mem=o.get('memory',{});lo=o.get('low',{});red=o.get('reduced',{})
  ct=o.get('contract',{});_sl=json.load(open(ROOT/data,encoding='utf-8')).get('storylines') or []
  branch_src=any(str(x.get('kind','')).strip() in ('支线','末梢') for x in _sl);main_src=sum(1 for x in _sl if str(x.get('kind','')).strip()=='主线')
  fam=(ct.get('src')=='model' and ct.get('strict') and ((branch_src and ct.get('branchLines',0)>0 and (ct.get('namedLanes') or 0)>0 and ct.get('hover')=='named') or (not branch_src and ct.get('branchLines')==0 and (ct.get('namedLanes') or 0)==0 and ct.get('mains')==main_src and ct.get('hover')=='main')))
  checks=[('health',r.returncode==0 and health),('bounded real participants and no animated SVG',state.get('shown',0)>0 and state['shown']<=8 and o.get('realNames') and o.get('dom')==0),('live ribbon reaches true arc and star',st.get('starErr',99)<=1 and st.get('arcErr',99)<=1.5 and sp.get('starErr',99)<=1 and sp.get('arcErr',99)<=1.5),('actual light-layer pixels',px.get('peak',0)>20 and px.get('lit',0)>100 and px.get('glError',-1)==0),('time flows from plot to star; reduced freezes',o.get('flowAdvance',0)>0.1 and state.get('flow')==1 and red.get('flow')==0 and red.get('time')==0),('low is two static threads; high recovers',lo.get('shown',0)>0 and lo['shown']<=2 and lo.get('flow')==0 and lo.get('drawcalls')==1 and o.get('high',{}).get('shown')==state.get('shown')),('hover cycles do not leak',mem.get('before')==mem.get('after') and bool(mem)),('clear and leave remove drawcalls',o.get('clear',{}).get('drawcalls')==0 and o.get('hidden',{}).get('drawcalls')==0),('original data intact',o.get('counts')==o.get('after') and bool(o.get('counts'))),('source-line-family pins hover target kind',fam)]
  print('DATA '+book+' '+json.dumps(o,ensure_ascii=False),flush=True)
  for name,ok in checks:total+=1;passed+=bool(ok);print(('PASS ' if ok else 'FAIL ')+book+' '+name,flush=True)
  if r.returncode:print(r.stdout[-1200:]+r.stderr[-500:])
 print('SKY-DISC-THREADS '+('OK' if total and total==passed else 'FAIL')+' · '+str(passed)+'/'+str(total));return 0 if total and total==passed else 1
if __name__=='__main__':raise SystemExit(main())
