#!/usr/bin/env python3
"""CDP resume-memory journey: record while reading work A, return to the
library/home, resume from the explicit entry, and assert the restored stable
state is byte-identical to the from-scratch-plus-manual-seek path.
The coordinator runs browser jobs serially (CL_GPU=1). Reads history only;
localStorage records live in the test browser profile."""
import argparse,base64,json,os,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner

def main():
 if os.environ.get('CL_GPU')!='1':raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
 a=argparse.ArgumentParser();a.add_argument('--base',default='http://127.0.0.1:8140');a.add_argument('--out',default=str(Path(os.environ.get('CL_SHOTS','/tmp/castline-shots'))/'sky-resume'));args=a.parse_args()
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True);r=Wave2AuditRunner(width=1440,height=900,dpr=1);checks=[]
 def ev(expr,wait=False):
  value=r.eval(expr,await_promise=wait)
  if isinstance(value,dict) and value.get('__evalError'):raise RuntimeError(value)
  return value
 def wait(expr,timeout=30):
  end=time.time()+timeout
  while time.time()<end:
   if ev(expr):return True
   time.sleep(.3)
  raise RuntimeError('wait timeout: '+expr[:110])
 def check(name,expr):
  value=ev(expr);ok=value is True;checks.append({'name':name,'ok':ok,'actual':value});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 def shot(name):
  (out/(name+'.png')).write_bytes(base64.b64decode(r.ws.call('Page.captureScreenshot',format='png')['data']))
 def ready():
  ev("(function(){try{Object.keys(localStorage).filter(function(k){return k.indexOf('castline.resume.')===0;}).forEach(function(k){localStorage.removeItem(k);});}catch(e){}})()")
  wait('!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))',90)
  time.sleep(4)
 try:
  r.start()
  r.navigate(args.base+'/')
  wait('window.CLSkyChrome&&CLSkyChrome.home()==="home"&&CLSkyChrome.recent().length>=2',60)
  ev('window.__resumeA=CLSkyChrome.recent()[0].key;window.__resumeB=CLSkyChrome.recent()[1].key')
  A,B=ev('__resumeA'),ev('__resumeB')
  r.navigate(args.base+'/?sky=1&data=data/cache/'+A+'.json');ready()
  ev('window.__resumeA='+json.dumps(A)+';window.__resumeB='+json.dumps(B))
  check('resume module ships with the shell and sees working storage','!!window.CLSkyResume&&CLSkyResume.stats().storage===true')
  check('no resume record exists for a freshly opened work','CLSkyResume.read(__resumeA)===null&&CLSkyResume.read(__resumeB)===null')
  ev('CLSky.setPlot(true);CLSky.seekEventAt(178)');time.sleep(1.5)
  ev('window.__resumeTitle=CLApp.graph().events[178].title||"";CLSkyResume.flush()')
  check('reading records the last view, event cursor and timestamp under the work key',
        '(()=>{var r=CLSkyResume.read(__resumeA);return !!r&&r.view==="plot"&&r.eventIndex===178&&r.cursor===CLSky.state().cursor&&typeof r.at==="number"&&r.label.includes(__resumeTitle);})()')
  check('one work keeps a compact record within the 2KB discipline','localStorage.getItem(CLSkyResume.keyFor(__resumeA)).length<=2048')
  check('storage keys are isolated per work','!!localStorage.getItem(CLSkyResume.keyFor(__resumeA))&&!localStorage.getItem(CLSkyResume.keyFor(__resumeB))')
  ev('window.__resumeBaseline=JSON.stringify(CLSkyResume.probe())')
  check('baseline probe captured the manual seek reading state','!!__resumeBaseline&&JSON.parse(__resumeBaseline).player.eventIndex===178')
  shot('01-recorded-reading')
  ev('CLSky.seekEventAt(180);CLSkyResume.flush()')
  ev('var w0=CLSkyResume.stats().writes,t0=CLSkyResume.stats().lastWriteAt;CLSky.seekEventAt(179);CLSky.seekEventAt(180);CLSky.seekEventAt(181);window.__resumeW0=w0;window.__resumeT0=t0')
  time.sleep(1.0)
  check('rapid seeks inside the throttle window do not write per state change','CLSkyResume.stats().writes===__resumeW0')
  time.sleep(3.0)
  check('trailing write after the gap lands exactly the last real state, at least 2s after the previous write','(()=>{var r=CLSkyResume.read(__resumeA);return !!r&&r.eventIndex===181&&CLSkyResume.stats().writes===__resumeW0+1&&CLSkyResume.stats().lastWriteAt-__resumeT0>=2000;})()')
  ev('CLSky.seekEventAt(178)');time.sleep(1.2);ev('CLSkyResume.flush()')
  ev('document.getElementById("btnLib").click()')
  wait('!!document.querySelector("#libList .lbc[data-key=\\""+__resumeA+"\\"] .cl-resume")',15)
  check('library card of work A exposes a continue entry naming the event',
        '(()=>{var b=document.querySelector("#libList .lbc[data-key=\\""+__resumeA+"\\"] .cl-resume");return !!b&&b.textContent.includes("继续上次")&&b.textContent.includes(__resumeTitle)&&b.getAttribute("aria-label").includes(__resumeTitle);})()')
  check('continue entry keeps the 44px hit target','(()=>{var b=document.querySelector("#libList .lbc[data-key=\\""+__resumeA+"\\"] .cl-resume");return b.getBoundingClientRect().height>=44&&b.getBoundingClientRect().width>=44;})()')
  check('work B without a record shows no entry','!document.querySelector("#libList .lbc[data-key=\\""+__resumeB+"\\"] .cl-resume")')
  shot('02-library-entry')
  ev('window.__resumeSaved=JSON.stringify(CLSkyResume.read(__resumeA))')
  ev('CLSkyResume.clear(__resumeA);CLSkyResume.refresh()')
  check('clearing the record removes the entry immediately','!document.querySelector("#libList .lbc[data-key=\\""+__resumeA+"\\"] .cl-resume")')
  ev('localStorage.setItem(CLSkyResume.keyFor(__resumeA),"{broken json");CLSkyResume.refresh()')
  check('a corrupted record self-heals to no entry without errors','(()=>{var bad=CLSkyResume.read(__resumeA);var gone=!document.querySelector("#libList .lbc[data-key=\\""+__resumeA+"\\"] .cl-resume");var cleaned=!localStorage.getItem(CLSkyResume.keyFor(__resumeA));return bad===null&&gone&&cleaned;})()')
  check('work B still shows no entry after self-heal pass','!document.querySelector("#libList .lbc[data-key=\\""+__resumeB+"\\"] .cl-resume")')
  ev('CLSkyResume.write(__resumeA,JSON.parse(__resumeSaved));CLSkyResume.refresh()')
  wait('!!document.querySelector("#libList .lbc[data-key=\\""+__resumeA+"\\"] .cl-resume")',15)
  ev('document.querySelector("#libList .lbc[data-key=\\""+__resumeA+"\\"] .cl-resume").focus()')
  check('continue entry is keyboard reachable (native focus)','document.activeElement&&document.activeElement.classList.contains("cl-resume")')
  for typ in ('keyDown','keyUp'):r.ws.call('Input.dispatchKeyEvent',type=typ,key='Enter',code='Enter',windowsVirtualKeyCode=13,text='\r')
  wait('CLSky.state().plot===true&&CLSky.playerState().eventIndex===178',30)
  time.sleep(1.5)
  print('BASELINE '+str(ev('__resumeBaseline')),flush=True)
  print('RESTORED '+str(ev('JSON.stringify(CLSkyResume.probe())')),flush=True)
  check('keyboard resume restores the exact manual path state byte for byte','JSON.stringify(CLSkyResume.probe())===__resumeBaseline')
  shot('03-resumed-event')
  ev('document.getElementById("btnLib").click()')
  wait('!!document.querySelector("#libList .lbc[data-key=\\""+__resumeA+"\\"] .cl-resume")',15)
  ev('document.querySelector("#libList .lbc[data-key=\\""+__resumeA+"\\"] .acts [data-act=open]").click()')
  wait('CLSky.state().cursor===null&&!CLSky.state().plot',30)
  check('default open keeps the from-scratch behavior: a present record never auto-jumps','CLSky.state().plot===false&&CLSky.state().cursor===null&&CLSkyResume.pending()===null')
  title=ev('__resumeTitle');baseline=ev('__resumeBaseline')
  r.navigate(args.base+'/')
  wait('window.CLSkyChrome&&CLSkyChrome.home()==="home"&&!!document.querySelector(".cl-resume-star")',60)
  ev('window.__resumeA='+json.dumps(A)+';window.__resumeB='+json.dumps(B)+';window.__resumeTitle='+json.dumps(title)+';window.__resumeBaseline='+json.dumps(baseline))
  check('home first screen shows the continue entry under the recorded work only',
        '(()=>{var b=document.querySelector(".sh-li .cl-resume-star");var b2n=document.querySelectorAll(".cl-resume-star").length;return !!b&&b.getAttribute("data-key")===__resumeA&&b.textContent.includes("继续上次")&&b.textContent.includes(__resumeTitle)&&b.getAttribute("aria-label").includes(__resumeTitle)&&b2n===1;})()')
  check('home entry keeps the 44px hit target','(()=>{var b=document.querySelector(".cl-resume-star");var r=b.getBoundingClientRect();return r.height>=44&&r.width>=44;})()')
  shot('04-home-entry')
  ev('document.querySelector(".cl-resume-star").click()')
  wait('CLSky.state().plot===true&&CLSky.playerState().eventIndex===178',60)
  time.sleep(1.5)
  check('home resume restores the identical stable state again','JSON.stringify(CLSkyResume.probe())===__resumeBaseline')
  check('every resume flow ends with zero uncaught JavaScript or shader errors','__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0')
  result={'ok':all(x['ok']for x in checks),'checks':checks,'modelsCalled':0,'sourceFilesChanged':False,'viewport':[1440,900]};(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({'ok':result['ok'],'checks':len(checks),'out':str(out)}),flush=True)
  if not result['ok']:raise SystemExit(1)
 finally:r.close()
if __name__=='__main__':main()
