#!/usr/bin/env python3
"""Read-only real-book foreshadow lifecycle reading journeys (CDP)."""
import argparse,base64,json,time,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner

STAGES=('resolved','pending','broken','conflicted')
def main():
 a=argparse.ArgumentParser();a.add_argument('--base',default='http://127.0.0.1:8137');a.add_argument('--out',default=str(Path(os.environ.get('CL_SHOTS','/tmp/castline-shots'))/'foreshadow-browser'));args=a.parse_args()
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True);r=Wave2AuditRunner(width=1440,height=900,dpr=1);checks=[]
 def ev(expr,wait=False):
  value=r.eval(expr,await_promise=wait)
  if isinstance(value,dict) and value.get('__evalError'):raise RuntimeError(value)
  return value
 def check(name,expr):
  value=ev(expr);ok=value is True;checks.append({'name':name,'ok':ok,'actual':value});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 def ready():
  end=time.time()+90
  while time.time()<end:
   if ev('!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))'):break
   time.sleep(.3)
  else:raise RuntimeError('graph readiness timeout')
  time.sleep(4)
 def click(selector):
  ev('(()=>{var e=document.querySelector('+json.dumps(selector)+');if(!e)throw Error("missing target");e.scrollIntoView({block:"center",behavior:"instant"});return 1})()')
  time.sleep(.35)
  point=ev('(()=>{var e=document.querySelector('+json.dumps(selector)+'),b=e.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2]})()')
  for typ in ['mouseMoved','mousePressed','mouseReleased']:r.ws.call('Input.dispatchMouseEvent',type=typ,x=point[0],y=point[1],button='left',clickCount=1)
  time.sleep(.4)
 def shot(name):
  (out/(name+'.png')).write_bytes(base64.b64decode(r.ws.call('Page.captureScreenshot',format='png')['data']))
 stages_js=json.dumps(list(STAGES))
 consistent='(()=>{var L=CLSky.model().narrative.foreshadowLifecycles,counts={},dom={},stages='+stages_js+';'\
  'L.forEach(x=>{counts[x.stage]=(counts[x.stage]||0)+1});'\
  'stages.forEach(k=>{dom[k]=document.querySelectorAll("#skyDeconBody .sd-fore-stage.is-"+k).length});'\
  'return stages.every(k=>(dom[k]||0)===(counts[k]||0));})()'
 try:
  r.start();r.navigate(args.base+'/?sky=1&data=data/cache/c84e8657afff87043c11ae57.json');ready()
  check('foreshadow lifecycle tab exists in the deconstruction tablist','!!document.querySelector("#skyDeconTabForeshadow")&&document.querySelector("#skyDeconTabForeshadow").getAttribute("role")==="tab"')
  ev('CLSkyDeconstruction.open();CLSkyDeconstruction.setMode("foreshadow")');time.sleep(.3)
  check('lifecycle view opens with one card per explicit declaration','document.querySelectorAll("#skyDeconBody .sd-fore-card").length===CLSky.model().narrative.foreshadowLifecycles.length&&CLSky.model().narrative.foreshadowLifecycles.length>=7')
  check('stage badges agree with the model projection counts',consistent)
  check('stats strip and basis badges match projection totals','(()=>{var s=CLSky.model().narrative.architecture.stats.foreshadow,b=document.getElementById("skyDeconBody"),t=b.textContent;return b.querySelector(".sd-stats").textContent.includes(String(s.total))&&t.includes("已兑现")&&t.includes("原文明确声明");})()')
  ev('window.__foreSeed=document.querySelector("#skyDeconBody .sd-fore-card [data-action=select-event]");window.__foreSeedIdx=+__foreSeed.getAttribute("data-event-index")')
  click('#skyDeconBody .sd-fore-card [data-action="select-event"]')
  check('clicking a seed event returns to the evidence layer on the same event','document.querySelector("#skyDeconTabEvidence").getAttribute("aria-selected")==="true"&&!!document.querySelector("#skyDeconBody .sd-evidence-detail")&&document.querySelector("#skyDeconBody").textContent.includes(CLApp.graph().events[__foreSeedIdx].title)')
  shot('01-seed-back-to-evidence')
  ev('CLSkyDeconstruction.setMode("foreshadow")');time.sleep(.3)
  ev('window.__foreClue=CLApp.graph().clues.find(c=>String(c.payoffEventId||"").length>0);window.__foreName=__foreClue.name')
  click('#skyDeconBody [data-action="read-record"][data-record-layer="clues"]')
  check('declaration link opens the full clue record with payoff reading','document.querySelector("#skyDeconTabMechanics").getAttribute("aria-selected")==="true"&&document.getElementById("skyDeconBody").textContent.includes("兑现状态")&&document.getElementById("skyDeconBody").textContent.includes(__foreName)')
  ev('CLSkyDeconstruction.setMode("foreshadow");var s=document.querySelector("#skyDeconBody [data-filter=foreshadow]");s.value="resolved";s.dispatchEvent(new Event("change",{bubbles:true}))');time.sleep(.3)
  check('stage filter keeps only resolved badges and stays searchable','document.querySelectorAll("#skyDeconBody .sd-fore-stage").length>0&&Array.from(document.querySelectorAll("#skyDeconBody .sd-fore-stage")).every(b=>b.classList.contains("is-resolved"))')
  ev('var s=document.querySelector("#skyDeconBody [data-search=foreshadow]");s.value="五行";s.dispatchEvent(new Event("input",{bubbles:true}))');time.sleep(.5)
  check('search reaches the seed and payoff quotes of the declaration','document.querySelectorAll("#skyDeconBody .sd-fore-card").length===1&&document.getElementById("skyDeconBody").textContent.includes("五行小车的场内铺垫")')
  shot('02-foreshadow-filtered')
  r.navigate(args.base+'/?sky=1&data=data/cache/f0b45e85aac6c95e584075a2.json');ready()
  ev('CLSkyDeconstruction.open();CLSkyDeconstruction.setMode("foreshadow")');time.sleep(.3)
  check('Sanguo lifecycle view opens with one card per declared clue','document.querySelectorAll("#skyDeconBody .sd-fore-card").length===CLSky.model().narrative.foreshadowLifecycles.length&&CLSky.model().narrative.foreshadowLifecycles.length===4')
  check('Sanguo stage badges agree with the model projection counts',consistent)
  ev('window.__foreSeed2=document.querySelector("#skyDeconBody .sd-fore-card [data-action=select-event]");window.__foreSeed2Idx=+__foreSeed2.getAttribute("data-event-index")')
  click('#skyDeconBody .sd-fore-card [data-action="select-event"]')
  check('Sanguo seed event returns to the evidence layer on the same event','document.querySelector("#skyDeconTabEvidence").getAttribute("aria-selected")==="true"&&document.querySelector("#skyDeconBody").textContent.includes(CLApp.graph().events[__foreSeed2Idx].title)')
  shot('03-foreshadow-sanguo')
  check('foreshadow journeys have no uncaught JavaScript, Promise, shader or frame-hook errors','__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0&&CLApp.scene().core().perf().frameHooks.errors===0')
  result={'ok':all(x['ok']for x in checks),'checks':checks,'modelsCalled':0,'sourceFilesChanged':False,'viewport':[1440,900]};(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({'ok':result['ok'],'checks':len(checks),'out':str(out)}),flush=True)
  if not result['ok']:raise SystemExit(1)
 finally:r.close()
if __name__=='__main__':main()
