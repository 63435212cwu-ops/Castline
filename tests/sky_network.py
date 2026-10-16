#!/usr/bin/env python3
"""Q4.2：默认骨架、一跳关系/拖拽同步、状态往返与背景残弧真实像素。
CL_GPU=1 python3 -s tests/sky_network.py --base http://127.0.0.1:8765
"""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BOOKS=[('saga','data/sample-saga.json'),('sanguo','data/cache/a935953b2678a80b352091d5.json'),('dafeng','data/cache/2ef47b2ecaa99a67352091d5.json')]
PROBE=r"""(async function(){
 var W=function(ms){return new Promise(function(r){setTimeout(r,ms);});},S=CLApp.scene(),out={};
 await W(6500);var G=CLApp.graph(),hero=G.characters.slice().sort(function(a,b){return (b.importance||0)-(a.importance||0);})[0].name;
 function state(){return {layer:S.infoLayer(),lit:S.relationFocus().lit.filter(function(f){return f.kind==='rel';}).length,glyph:S.glyph().segs,bundles:CLSkyDeep.stats().bundles};}
 out.book=G.title;out.count=[G.characters.length,G.relations.length,G.events.length];out.default=state();
 var neighbors={};neighbors['c:'+hero]=1;(CLApp.atlas.skyView().relations||[]).forEach(function(r){if(r.a===hero)neighbors['c:'+r.b]=1;if(r.b===hero)neighbors['c:'+r.a]=1;});
 CLSkyDeep.hoverStar(hero,true);await W(350);var lit=S.relationFocus().lit.filter(function(f){return f.kind==='rel';}),dist=S._pilgrimage||{};
 out.hover={n:lit.length,direct:lit.filter(function(f){return f.a==='c:'+hero||f.b==='c:'+hero;}).length,foreign:lit.filter(function(f){return !neighbors[f.a]||!neighbors[f.b];}),depth:Math.max.apply(null,Object.keys(dist).map(function(k){return dist[k];})),same:S.hoverName()===hero,bundleLit:CLSkyDeep.stats().bundles.lit};
 CLSkyDeep.hoverStar(null,true);await W(200);out.clear=state();
 var gp=CLSky.model().groupings.filter(function(g){return g.key!=='camp';})[0];if(gp){CLSky.regroup(gp.key);await W(2300);out.regroup=state();CLSky.regroup('camp');await W(2300);}
 CLSky.setPlot(true);await W(3000);CLSky.setPlot(false);await W(2200);out.plotBack=state();
 CLSky.openCompass(hero);await W(3000);CLSky.closeCompass();await W(2200);out.compassBack=state();
 var target=null;S.scene.traverse(function(o){if(o.isLineSegments&&o.material&&o.material.uniforms&&o.material.uniforms.uABezel&&o.material.uniforms.uBackdrop)target=o;});if(!target)throw new Error('bezel mesh missing');
 var renderer=S.renderer,mat=target.material,geo=target.geometry,oldTarget=renderer.getRenderTarget(),oldColor=renderer.getClearColor(new THREE.Color()).clone(),oldAlpha=renderer.getClearAlpha();
 /* 固定正交机位覆盖真实几何；宿主星座机位的外围环可能超出画面，不能把采样缺失当残弧。 */
 var width=1024,height=1024,desc=CLSky.disc().desc(),bound=desc.rBez*1.12;
 var rt=new THREE.WebGLRenderTarget(width,height),single=new THREE.Scene(),copy=new THREE.LineSegments(geo,mat),pixels=new Uint8Array(width*height*4),cam=new THREE.OrthographicCamera(-bound,bound,bound,-bound,.1,20);
 cam.position.z=10;cam.lookAt(0,0,0);cam.layers.set(3);copy.frustumCulled=false;copy.layers.set(3);single.add(copy);
 out.attributes=Object.keys(geo.attributes).map(function(k){return {name:k,count:geo.attributes[k].count};});
 function read(){renderer.setRenderTarget(rt);renderer.setClearColor(0,0);renderer.clear();renderer.render(single,cam);renderer.readRenderTargetPixels(rt,0,0,width,height,pixels);var values=[],peak=0;
  for(var pi=0;pi<pixels.length;pi+=4)peak=Math.max(peak,pixels[pi],pixels[pi+1],pixels[pi+2]);
  for(var i=0;i<180;i++){var a=i/180*Math.PI*2,v=new THREE.Vector3(desc.rBez*Math.cos(a),desc.rBez*Math.sin(a),desc.zBez||0);v.project(cam);var x=Math.round((v.x*.5+.5)*width),y=Math.round((v.y*.5+.5)*height),mx=0;
   for(var dy=-2;dy<=2;dy++)for(var dx=-2;dx<=2;dx++){var xx=x+dx,yy=y+dy;if(xx<0||yy<0||xx>=width||yy>=height)continue;var at=(yy*width+xx)*4;mx=Math.max(mx,pixels[at],pixels[at+1],pixels[at+2]);}values.push(mx);
  }return {mask:mat.uniforms.uBackdrop.value,lit:values.filter(function(v){return v>2;}).length,samples:values.length,max:Math.max.apply(null,values),peak:peak,glError:renderer.getContext().getError()};}
 try{var saved=mat.uniforms.uBackdrop.value,alpha=mat.uniforms.uABezel.value;mat.uniforms.uABezel.value=.5;mat.uniforms.uBackdrop.value=1;out.residual=read();mat.uniforms.uBackdrop.value=0;out.full=read();mat.uniforms.uBackdrop.value=saved;mat.uniforms.uABezel.value=alpha;}
 finally{renderer.setClearColor(oldColor,oldAlpha);renderer.setRenderTarget(oldTarget);rt.dispose();}
 out.after=[G.characters.length,G.relations.length,G.events.length];return JSON.stringify(out);
})()"""
def main():
 p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8765');p.add_argument('--out',default='/tmp/xingxi-network');a=p.parse_args();outdir=Path(a.out);outdir.mkdir(parents=True,exist_ok=True);env=dict(os.environ);env.setdefault('CL_GPU','1');passed=total=0
 for book,data in BOOKS:
  r=subprocess.run([sys.executable,'-s',str(ROOT/'tests/headless.py'),'sky=1&probe=1&data='+data,'--url',a.base+'/','--size','1440x900','--timeout','240','--eval',PROBE],cwd=ROOT,env=env,capture_output=True,text=True)
  (outdir/(book+'.log')).write_text(r.stdout+'\n'+r.stderr);o={};healthy=False
  for line in r.stdout.splitlines():
   if line.startswith('EVAL:'):v=json.loads(line[5:]);o=json.loads(v) if isinstance(v,str) else v
   if line.startswith('POST-HEALTH:'):healthy=json.loads(line.split(':',1)[1]).get('ok') is True
  states=[o.get(k,{}) for k in ('default','clear','plotBack','compassBack')];h=o.get('hover',{});res=o.get('residual',{});full=o.get('full',{})
  checks=[('health',r.returncode==0 and healthy),('default/restored overview and no dense relations',all(s.get('layer')=='overview' and s.get('lit')==0 for s in states)),('skeleton remains',o.get('default',{}).get('glyph',0)>0),('hover and quiet-drag path reach true one-hop relations',h.get('direct',0)>0 and not h.get('foreign') and h.get('depth')==1 and h.get('same')),('regroup keeps denoised layer',not o.get('regroup') or o['regroup']['layer']=='overview' and o['regroup']['lit']==0),('data counts preserved',bool(o.get('count')) and o.get('count')==o.get('after')),('all tick attributes cover both vertices',bool(o.get('attributes')) and len({x['count'] for x in o['attributes']})==1),('real pixels show residual arcs and full plot ring',full.get('lit',0)>=160 and full.get('peak',0)>20 and full.get('glError',-1)==0 and res.get('glError',-1)==0 and 40<=res.get('lit',0)<=130 and res.get('lit',0)<full.get('lit',0)*.8)]
  print('DATA '+book+' '+json.dumps(o,ensure_ascii=False),flush=True)
  for name,ok in checks:total+=1;passed+=bool(ok);print(('PASS ' if ok else 'FAIL ')+book+' '+name,flush=True)
  if r.returncode:print(r.stdout[-1500:]+r.stderr[-800:])
 print('SKY-NETWORK '+('OK' if total and total==passed else 'FAIL')+' · '+str(passed)+'/'+str(total));return 0 if total and total==passed else 1
if __name__=='__main__':raise SystemExit(main())
