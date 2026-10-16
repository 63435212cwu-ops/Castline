#!/usr/bin/env python3
"""Real camera-home regression: plot resize, compass return, same-size preset/R.

Uses project headless/chaos driver and public product actions only. Camera, orbit
lock and disc positions are read-only; no pose or layout writes, no model calls.
Default matrix is saga/sanguo/dafeng × 390/820/1440, always reached from 1920 role.
"""
import argparse,base64,hashlib,io,json,math,os,re,signal,struct,subprocess,sys,time,traceback,zlib
from contextlib import redirect_stdout
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('CL_PROJECT_ROOT',str(HERE.parent if (HERE.parent/'index.html').is_file() else Path('/Users/carmen/Desktop/星系')))).resolve()
sys.path.insert(0,str(ROOT/'tests'))
import headless
import sky_chaos as chaos
BOOKS=dict(chaos.BOOKS)
FULL_BOOKS=('saga','sanguo','dafeng')
FULL_SIZES=('390x844','820x900','1440x900')
READY="!!(window.CLSky&&CLSky.model()&&window.CLSkyDeep&&CLSkyDeep.enabled()&&CLSkyDeep.stats().stars&&CLSkyDeep.stats().stars.ignite>.99&&!Array.prototype.some.call(document.querySelectorAll('.skd-loader'),function(e){return !e.hidden;}))"
SETTLED="!!(window.CLApp&&CLApp.scene()&&CLApp.scene().settleT&&CLApp.scene().settleT().settled)"
SNAPSHOT=r"""(function(){
 var S=CLApp.scene(),st=CLSky.state(),D=CLSkyDeep.stats(),disc=CLSky.disc(),a=disc&&disc.anchor&&disc.anchor(),anchor=new THREE.Vector3(),centre=new THREE.Vector3(),lock=S.orbitLockInfo(),info=S.skyInfo(),body=document.body.classList;
 if(!a)throw Error('Actual disc anchor missing');a.getWorldPosition(anchor);S.group.getWorldPosition(centre);
 return {mode:st.mode,plot:st.plot,compass:st.compass,group:st.group,deepMode:D.mode,view:D.view,
  viewport:[innerWidth,innerHeight,devicePixelRatio],target:S.controls.target.toArray(),camera:S.camera.position.toArray(),anchor:anchor.toArray(),centre:centre.toArray(),
  toDisc:S.controls.target.distanceTo(anchor),R:info&&info.R,lock:lock,pan:S.controls.enablePan,
  bodyPlot:body.contains('sky-plot-on'),bodyCompass:body.contains('sky-compass-on'),discState:disc.state(),
  settle:S.settleT(),cameraFar:S.camera.far,quality:S.quality()};
})()"""
HERO=r"""(function(){var G=CLApp.graph(),L=G.relations||[],related=G.characters.filter(function(c){return L.some(function(r){return r.a===c.name||r.b===c.name;});}).sort(function(a,b){return(b.importance||0)-(a.importance||0);});
 if(!related.length)throw Error('Actual book lacks a relation-bearing character');
 var known=G.characters.filter(function(c){return c.name==='李妙真'&&related.some(function(r){return r.name===c.name;});})[0],c=known||related[0];
 return {name:c.name,actualCharacter:true,relationCount:L.filter(function(r){return r.a===c.name||r.b===c.name;}).length,groupings:CLSky.model().groupings.map(function(x){return x.key;})};})()"""

def require(ok,message):
 if not ok:raise RuntimeError(message)
def numeric(x):return type(x) in (int,float) and math.isfinite(x)
def vector(v):return isinstance(v,list) and len(v)==3 and all(numeric(x) for x in v)
def distance(a,b):return math.dist(a,b)
def source_hashes():
 paths={'index.html','tests/script_manifest.json','tests/headless.py','tests/sky_chaos.py','scripts/accept.sh'}
 paths.update(re.findall(r'(?:src|href)=["\']((?:js|css)/[^"\'?]+)',(ROOT/'index.html').read_text()))
 paths.update(BOOKS.values())
 result={str((ROOT/p).resolve()):hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths)}
 result[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();return result

def png_size(data):
 require(data.startswith(b'\x89PNG\r\n\x1a\n'),'Not a PNG');at=8;size=None;image=False;ended=False
 while at<len(data):
  require(at+12<=len(data),'Truncated PNG chunk');n=struct.unpack('>I',data[at:at+4])[0];kind=data[at+4:at+8];end=at+12+n
  require(end<=len(data),'Truncated PNG payload');body=data[at+8:at+8+n];crc=struct.unpack('>I',data[at+8+n:end])[0]
  require(zlib.crc32(kind+body)&0xffffffff==crc,'PNG CRC mismatch')
  if size is None:require(kind==b'IHDR' and n==13,'Missing IHDR');size=struct.unpack('>II',body[:8]);require(all(v>0 for v in size),'Invalid PNG dimensions')
  if kind==b'IDAT':image=True
  if kind==b'IEND':require(n==0 and end==len(data),'Invalid PNG end');ended=True;break
  at=end
 require(image and ended,'Incomplete PNG');return size

def healthy(b):
 stream=io.StringIO()
 with redirect_stdout(stream):code=headless.post_health(b.ws,b.errors)
 rows=[s[13:] for s in stream.getvalue().splitlines() if s.startswith('POST-HEALTH: ')]
 require(type(code) is int and len(rows)==1,'Missing POST-HEALTH evidence');h=json.loads(rows[0])
 require(h.get('ok') is True and type(h.get('exitCode')) is int and code==h.get('exitCode')==0 and h.get('jserr')==h.get('jsrej')=='none'
  and all(h.get(k)==[] for k in ('shaderErrors','missing','probeErrors','evalErrors'))
  and all(type(h.get('errorCounts',{}).get(k)) is int and h['errorCounts'][k]==0 for k in ('jserr','jsrej','frameHooks'))
  and not h.get('frameHookLastError'),'Actual POST health failed: '+json.dumps(h,ensure_ascii=False));return h

class Browser(chaos.Browser):
 def __init__(self):super().__init__(1920,1080);self.errors=[];self.chromeArgv=None
 def ev(self,expr):
  r=headless.health_evaluate(self.ws,self.errors,'home-frame',expr,awaitPromise=True)
  if r.get('exceptionDetails'):raise RuntimeError(json.dumps(r['exceptionDetails'],ensure_ascii=False))
  return r.get('result',{}).get('value')
 def until(self,expr,timeout=10,step=.04):
  deadline=time.monotonic()+timeout;sock=getattr(self.ws,'s',None);old=sock.gettimeout() if sock else None
  try:
   while time.monotonic()<deadline:
    if sock:sock.settimeout(max(.01,min(old or 55,deadline-time.monotonic())))
    if self.ev(expr) is True:return time.monotonic()<=deadline
    time.sleep(min(step,max(0,deadline-time.monotonic())))
   return False
  finally:
   if sock:sock.settimeout(old)
 def close(self):
  facts={'ok':False,'errors':[]}
  try:
   if self.ws and getattr(self.ws,'s',None):self.ws.s.settimeout(2)
  except Exception as exc:facts['errors'].append('Closing socket timeout: '+str(exc))
  try:
   if self.ws:self.ws.call('Browser.close')
  except Exception:pass
  if self.proc:
   try:os.killpg(self.proc.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   except Exception as exc:facts['errors'].append('Chrome TERM: '+str(exc))
   try:self.proc.wait(timeout=4)
   except subprocess.TimeoutExpired:
    try:os.killpg(self.proc.pid,signal.SIGKILL);self.proc.wait(timeout=2)
    except ProcessLookupError:pass
    except Exception as exc:facts['errors'].append('Chrome KILL/wait: '+str(exc))
   except Exception as exc:facts['errors'].append('Chrome wait: '+str(exc))
   try:os.killpg(self.proc.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   except Exception as exc:facts['errors'].append('Remaining group: '+str(exc))
  try:
   rc=subprocess.run(['pkill','-9','-f','--','--user-data-dir='+self.ud],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3).returncode
   if rc not in (0,1):facts['errors'].append('Own profile cleanup exit '+str(rc))
  except Exception as exc:facts['errors'].append('Own profile cleanup: '+str(exc))
  try:
   import shutil
   shutil.rmtree(self.ud)
  except FileNotFoundError:pass
  except Exception as exc:facts['errors'].append('Profile cleanup: '+str(exc))
  facts['ok']=not facts['errors'];return facts

def observed_ok(o,mode,plot,size,hero=None,group="role"):
 w,h=map(int,size.split('x'))
 if not isinstance(o,dict) or o.get('viewport')!=[w,h,1] or not numeric(o.get('R')) or o['R']<=0:return False
 if not all(vector(o.get(k)) for k in ('camera','target','anchor','centre')) or not numeric(o.get('toDisc')):return False
 if abs(o['toDisc']-distance(o['target'],o['anchor']))>1e-6:return False
 if o.get('group')!=group:return False
 if o.get('mode')!=mode or o.get('plot') is not plot or o.get('bodyPlot') is not plot or o.get('bodyCompass') is not (mode=='compass'):return False
 if o.get('deepMode')!=('compass' if mode=='compass' else 'plot' if plot else 'constellation'):return False
 if o.get('discState')!=('hidden' if mode=='compass' else 'plot' if plot else 'backdrop'):return False
 if mode=='compass' and o.get('compass')!=hero:return False
 if mode!='compass' and o.get('compass') is not None:return False
 lock=o.get('lock') or {}
 if lock.get('on') is not True or lock.get('pan') is not False or o.get('pan') is not False or not vector(lock.get('target')):return False
 return distance(o['target'],lock['target'])<=.001*o['R'] and isinstance(o.get('settle'),dict) and o['settle'].get('settled') is True

def same_frame(base,after):
 if not isinstance(base,dict) or not isinstance(after,dict) or base.get('viewport')!=after.get('viewport'):return False
 R=base.get('R')
 if not numeric(R) or R<=0 or not numeric(after.get('R')) or abs(after['R']-R)>1e-6:return False
 if not all(vector(o.get(k)) for o in (base,after) for k in ('target','centre','anchor')) or not all(numeric(o.get('toDisc')) for o in (base,after)):return False
 return (abs(after['toDisc']-base['toDisc'])<=.03*R and distance(base['target'],after['target'])<=.001*R
  and distance(base['centre'],after['centre'])<=.001*R and distance(base['anchor'],after['anchor'])<=.001*R)

def atomic_json(path,value):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(tmp,path)

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',default='http://127.0.0.1:8765');ap.add_argument('--books',default=','.join(FULL_BOOKS));ap.add_argument('--sizes',default=','.join(FULL_SIZES));ap.add_argument('--out',type=Path)
 a=ap.parse_args();books=a.books.split(',');sizes=a.sizes.split(',')
 require(os.environ.get('CL_GPU')=='1','CL_GPU=1 required')
 require(books and len(set(books))==len(books) and all(x in BOOKS for x in books),'Invalid/duplicate books')
 require(sizes and len(set(sizes))==len(sizes) and all(x in FULL_SIZES for x in sizes),'Sizes must be unique members of 390x844,820x900,1440x900')
 out=a.out or Path(os.environ.get('CL_SHOTS','/tmp/castline-shots'))/('home-frame-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
 require(out.resolve()!=ROOT and ROOT not in out.resolve().parents,'Evidence must remain outside the workspace');out.mkdir(parents=True,exist_ok=False)
 def cancelled(signum,frame):raise SystemExit(128+signum)
 for sig in (signal.SIGTERM,signal.SIGHUP):signal.signal(sig,cancelled)
 inputs=source_hashes();sessions=[];checks=[]
 report={'ok':False,'complete':False,'fullMatrix':tuple(books)==FULL_BOOKS and tuple(sizes)==FULL_SIZES,'books':books,'sizes':sizes,'sourceHashes':inputs,'sourceUnchanged':False,'sessions':sessions,'checks':checks,'argv':sys.argv,'startedAt':datetime.now(timezone.utc).isoformat(),'budgets':{'discDistanceDriftR':.03,'targetDriftR':.001,'centreDriftR':.001,'lockOffsetR':.001}}
 def publish():atomic_json(out/'result.json',report)
 def check(name,ok,detail):
  checks.append({'name':name,'ok':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
 publish()
 try:
  for book in books:
   for size in sizes:
    row={'book':book,'size':size,'data':BOOKS[book],'ok':False,'marks':[],'images':[]};sessions.append(row);b=Browser();prefix=book+'-'+size
    try:
     b.start();row['chromeArgv']=b.proc.args;b.ws.call('Page.navigate',url=a.base.rstrip('/')+'/?sky=1&probe=1&data='+BOOKS[book]);require(b.until(READY,90),'Actual book/loader never ready');time.sleep(1.8);require(b.until(SETTLED,8),'Initial camera never settled')
     row['gpu']=b.ev("(function(){var g=CLApp.scene().renderer.getContext(),d=g.getExtension('WEBGL_debug_renderer_info');return {unmasked:!!d,renderer:d?g.getParameter(d.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER)};})()")
     require(row['gpu'].get('unmasked') is True and isinstance(row['gpu'].get('renderer'),str) and bool(row['gpu']['renderer']) and not any(x in row['gpu']['renderer'].lower() for x in ('swiftshader','llvmpipe','software')),'Actual hardware GPU missing/software')
     hero=b.ev(HERO);row['hero']=hero;require(hero.get('actualCharacter') is True and hero.get('relationCount',0)>0 and 'role' in hero.get('groupings',[]),'Real relation hero/role grouping missing')
     def mark(label,mode='constellation',plot=False,current='1920x1080',picture=False):
      observed=b.ev(SNAPSHOT);health=healthy(b);entry={'name':label,'observed':observed,'health':health};row['marks'].append(entry)
      check(prefix+' '+label+' actual mode/viewport/finite/lock/health',observed_ok(observed,mode,plot,current,hero['name'],'camp' if label=='initial' else 'role'),entry)
      if picture:
       pixels=base64.b64decode(b.ws.call('Page.captureScreenshot',format='png')['data'],validate=True);w,h=map(int,current.split('x'));require(png_size(pixels)==(w,h),'Actual PNG viewport differs')
       path=out/(prefix+'-'+label+'.png');path.write_bytes(pixels);image={'name':label,'file':str(path),'sha256':hashlib.sha256(pixels).hexdigest(),'bytes':len(pixels),'pixelSize':[w,h],'before':observed,'healthBefore':health,'after':b.ev(SNAPSHOT),'healthAfter':healthy(b)};row['images'].append(image)
       check(prefix+' '+label+' screenshot kept the same frame/mode',same_frame(observed,image['after']) and observed_ok(image['after'],mode,plot,current,hero['name']),image)
      publish();return observed
     def action(label,expr,mode='constellation',plot=False,current='1920x1080',picture=False,wait=1.8):
      b.ev(expr);time.sleep(wait);require(b.until(SETTLED,8),label+' camera did not settle');return mark(label,mode,plot,current,picture)
     initial=mark('initial');wide=action('role','CLSky.regroup("role")',wait=2.6);check(prefix+' role leaves graph centre fixed',distance(initial['centre'],wide['centre'])<=.001*wide['R'],{'before':initial,'after':wide})
     plot=action('plot-on','CLSky.setPlot(true)',plot=True);check(prefix+' wide plot preserves centre and target',same_frame(wide,plot),{'before':wide,'after':plot})
     top=action('plot-top','CLSkyDeep.preset("top")',plot=True);check(prefix+' plot top preserves centre and target',same_frame(plot,top) and top.get('view',{}).get('preset')=='top',{'before':plot,'after':top})
     w,h=map(int,size.split('x'));b.size(w,h);time.sleep(3.2);require(b.until(SETTLED,8),'Plot resize never settled');resized=mark('plot-resize',plot=True,current=size)
     baseline=action('baseline','CLSky.setPlot(false)',current=size,picture=True);check(prefix+' plot close keeps resized target',same_frame(resized,baseline),{'before':resized,'after':baseline})
     compass=action('compass','CLSky.openCompass('+json.dumps(hero['name'],ensure_ascii=False)+')',mode='compass',current=size,wait=3.4);check(prefix+' entering real compass leaves graph centre fixed',distance(compass['centre'],baseline['centre'])<=.001*baseline['R'],{'before':baseline,'after':compass})
     back=action('compass-return','CLSky.closeCompass()',current=size,picture=True);check(prefix+' compass return preserves original I2 and target',same_frame(baseline,back),{'before':baseline,'after':back})
     b.size(w,h);time.sleep(2.4);require(b.until(SETTLED,8),'Repeated viewport never settled');same=mark('same-size',current=size);check(prefix+' same-size preserves original I2 and target',same_frame(baseline,same),{'before':baseline,'after':same})
     top=action('constellation-top','CLSkyDeep.preset("top")',current=size,picture=True);check(prefix+' top after compass preserves original I2 and target',same_frame(baseline,top) and top.get('view',{}).get('preset')=='top',{'before':baseline,'after':top})
     b.ev('if(document.activeElement&&document.activeElement.blur)document.activeElement.blur()');b.key('r');time.sleep(1.8);require(b.until(SETTLED,8),'Real R reset never settled');reset=mark('R-reset',current=size,picture=True)
     check(prefix+' real CDP R preserves original I2 and target',same_frame(baseline,reset) and reset.get('view',{}).get('preset')=='top',{'before':baseline,'after':reset})
     row['health']=healthy(b);row['ok']=all(c['ok'] for c in checks if c['name'].startswith(prefix+' '))
    except Exception as exc:
     row['error']=str(exc);row['traceback']=traceback.format_exc();row['evalErrors']=b.errors;check(prefix+' session completed',False,{'error':row['error'],'traceback':row['traceback']})
     try:
      if b.ws:row['failureSnapshot']=b.ev(SNAPSHOT);row['failureHealth']=healthy(b)
     except Exception as error:row['failureProbeError']=str(error)
     try:
      if b.ws:
       pixels=base64.b64decode(b.ws.call('Page.captureScreenshot',format='png')['data'],validate=True);dimensions=png_size(pixels);path=out/(prefix+'-failure.png');path.write_bytes(pixels)
       row['failureImage']={'file':str(path),'pixelSize':list(dimensions),'bytes':len(pixels),'sha256':hashlib.sha256(pixels).hexdigest()}
     except Exception as error:row['failureImageError']=str(error)
    finally:
     try:row['cleanup']=b.close()
     except Exception as error:row['cleanup']={'ok':False,'error':str(error),'traceback':traceback.format_exc()}
     row['ok']=row['ok'] and row['cleanup'].get('ok') is True;publish()
  stable=source_hashes()==inputs;report['sourceUnchanged']=stable
  check('Single unchanged source version',stable,{'sourceHashes':inputs})
  expected={(book,size) for book in books for size in sizes};actual={(r['book'],r['size']) for r in sessions}
  ok=stable and len(sessions)==len(expected) and actual==expected and bool(checks) and all(c['ok'] for c in checks) and all(r.get('ok') is True and len(r['images'])==4 for r in sessions)
  for row in sessions:
   for image in row['images']:
    pixels=Path(image['file']).read_bytes();ok=ok and len(pixels)==image['bytes'] and hashlib.sha256(pixels).hexdigest()==image['sha256'] and list(png_size(pixels))==image['pixelSize']
  report['ok']=report['complete']=bool(ok);report['finishedAt']=datetime.now(timezone.utc).isoformat();publish()
  print('SKY-HOME-FRAME '+('PASS' if ok else 'FAIL')+' '+str(sum(c['ok'] for c in checks))+'/'+str(len(checks))+' cells='+str(len(sessions))+' out='+str(out),flush=True);return 0 if ok else 1
 finally:publish()
if __name__=='__main__':raise SystemExit(main())
