import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path('/Users/carmen/Desktop/星系')
BOOKS=[('saga','data/sample-saga.json'),('sanguo','data/cache/a935953b2678a80b352091d5.json'),('dafeng','data/cache/2ef47b2ecaa99a67352091d5.json')]
PROBE=r"""(async function(){
 var W=function(ms){return new Promise(function(r){setTimeout(r,ms);});},S=CLApp.scene(),out={size:[innerWidth,innerHeight],dpr:devicePixelRatio,samples:[]};
 function measure(tag){
  var names=[],glyphs=[],steep=[],outside=[],worst=0,expected={},arcHits=[],arcPts=[],byId={};
  CLSky.disc().desc().items.forEach(function(it){byId[it.id]=it;});
  document.querySelectorAll('.sky-disc .sd-hit').forEach(function(path){var it=byId[path.getAttribute('data-id')];if(!it||it.kind==='quiet')return;var L=path.getTotalLength(),pts=[];for(var d=0;d<=L;d+=3){var p=path.getPointAtLength(d);pts.push([p.x,p.y]);}arcPts.push({pts:pts,w:it.w,name:CLSky.disc().lineInfo(it.id).label});});
  CLSky.model().mains.concat(CLSky.model().lines).forEach(function(l){expected[l.label]=1;});
  Array.prototype.forEach.call(document.querySelectorAll('.sky-disc .sd-label'),function(el,li){
   if(+getComputedStyle(el).opacity<.05)return;var n=el.getNumberOfChars();if(n<2)return;
   var a=el.getStartPositionOfChar(0),b=el.getEndPositionOfChar(n-1),angle=Math.atan2(b.y-a.y,b.x-a.x)*180/Math.PI;
   names.push(el.textContent);if(Math.abs(angle)>30)steep.push({name:el.textContent,angle:angle});
   for(var k=0;k<n;k++){var e=el.getExtentOfChar(k);if(!e.width)continue;glyphs.push({id:li,x0:e.x+e.width*.2,y0:e.y+e.height*.2,x1:e.x+e.width*.8,y1:e.y+e.height*.8});if(e.x<0||e.y<0||e.x+e.width>innerWidth||e.y+e.height>innerHeight)outside.push(el.textContent);var cx=e.x+e.width/2,cy=e.y+e.height/2;arcPts.forEach(function(arc){var rr=Math.min(e.width,e.height)*.25+arc.w/2;for(var ai=0;ai<arc.pts.length;ai++){var p=arc.pts[ai],dx=p[0]-cx,dy=p[1]-cy;if(dx*dx+dy*dy<rr*rr){arcHits.push({label:el.textContent,arc:arc.name});break;}}});}
  });
  for(var i=0;i<glyphs.length;i++)for(var j=i+1;j<glyphs.length;j++){var a=glyphs[i],b=glyphs[j];if(a.id===b.id)continue;var x=Math.max(0,Math.min(a.x1,b.x1)-Math.max(a.x0,b.x0)),y=Math.max(0,Math.min(a.y1,b.y1)-Math.max(a.y0,b.y0)),area=Math.min((a.x1-a.x0)*(a.y1-a.y0),(b.x1-b.x0)*(b.y1-b.y0))||1;worst=Math.max(worst,x*y/area);}
  return {tag:tag,arcHits:arcHits,n:names.length,steep:steep,outside:outside,wrong:names.filter(function(n){return !expected[n];}),worst:worst};
 }
 await W(6500);CLSky.setPlot(true);await W(3500);out.samples.push(measure('standard'));
 for(var i=0;i<4;i++){CLSkyDeep.nudge(.65,i===0?1.15:0);await W(1600);out.samples.push(measure('tilt-'+i));}
 CLSkyDeep.resetView();await W(1800);var top=CLSky.model().lines.filter(function(l){return l.named;})[0];if(top){CLSky.hoverLine(top.id);await W(600);out.samples.push(measure('hover'));CLSkyDeep.nudge(.4,.7);await W(1600);out.samples.push(measure('hover-tilt'));CLSky.hoverLine(null);CLSkyDeep.resetView();await W(1600);}
 S.setCalm(true);await W(300);out.samples.push(measure('calm'));
 return JSON.stringify(out);
})()"""
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--base',default='http://127.0.0.1:8765');ap.add_argument('--books',default='saga,sanguo,dafeng');ap.add_argument('--sizes',default='1440x900,390x844');ap.add_argument('--dpr',default='1');ap.add_argument('--out',default='/tmp/xingxi-upright-check');a=ap.parse_args();assert os.environ.get('CL_GPU')=='1','CL_GPU=1 required';outdir=Path(a.out);outdir.mkdir(exist_ok=True,parents=True);passed=total=0
 for book,data in BOOKS:
  if book not in a.books.split(','):continue
  for size in a.sizes.split(','):
   r=subprocess.run([sys.executable,'-s',str(ROOT/'tests/headless.py'),'sky=1&probe=1&data='+data,'--url',a.base+'/','--size',size,'--dpr',a.dpr,'--timeout','180','--eval',PROBE],cwd=ROOT,capture_output=True,text=True)
   (outdir/(book+'-'+size+'.log')).write_text(r.stdout+'\n'+r.stderr);o={};health=False
   for l in r.stdout.splitlines():
    if l.startswith('EVAL:'):v=json.loads(l[5:]);o=json.loads(v) if isinstance(v,str) else v
    if l.startswith('POST-HEALTH:'):health=json.loads(l.split(':',1)[1]).get('ok') is True
   checks=[('health and viewport',r.returncode==0 and health and o.get('size')==list(map(int,size.split('x'))) and abs(o.get('dpr',0)-float(a.dpr))<.01),('visible names present',len(o.get('samples',[]))>=6 and o.get('samples',[{}])[0].get('n',0)>=3 and all(s['n']>0 for s in o.get('samples',[]))),('names upright',bool(o) and all(not s['steep'] for s in o.get('samples',[]))),('names do not overlap',bool(o) and all(s['worst']<=.15 for s in o.get('samples',[]))),('names do not cross colored arcs',bool(o) and all(not s['arcHits'] for s in o.get('samples',[]))),('names keep real text and stay onscreen',bool(o) and all(not s['wrong'] and not s['outside'] for s in o.get('samples',[])))]
   print('DATA '+book+' '+size+' '+json.dumps(o,ensure_ascii=False),flush=True)
   for name,ok in checks:total+=1;passed+=bool(ok);print(('PASS ' if ok else 'FAIL ')+book+' '+size+' '+name,flush=True)
 print('UPRIGHT',passed,total);return 0 if total and passed==total else 1
if __name__=='__main__':raise SystemExit(main())
