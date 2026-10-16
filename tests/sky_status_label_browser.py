#!/usr/bin/env python3
"""CDP spot-check: localized status-code copy on real books (Xiyou/Sanguo).

Every user-facing status badge on the foreshadow and causal reading surfaces
must render Chinese copy through the single-point STATUS_TEXT map, while the
raw machine code stays in data-status-code / data-stage. Raw English codes
never leak into visible text."""
import argparse,base64,json,time,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner

BOOKS={'西游':'data/cache/c84e8657afff87043c11ae57.json','三国':'data/cache/f0b45e85aac6c95e584075a2.json'}
RAW_CODES=['resolved','pending','seeded','unresolved','unresolved_or_conflicting','unlinked','linked']
def main():
 a=argparse.ArgumentParser();a.add_argument('--base',default='http://127.0.0.1:8137');a.add_argument('--out',default=str(Path(os.environ.get('CL_SHOTS','/tmp/castline-shots'))/'status-label-browser'));args=a.parse_args()
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
 raw=json.dumps(RAW_CODES)
 localized='(()=>{var b=document.getElementById("skyDeconBody"),spans=b.querySelectorAll(".sd-status-text"),cards=b.querySelectorAll(".sd-fore-card"),codes='+raw+';'\
  'if(!cards.length)return "no-cards";'\
  'for(var i=0;i<cards.length;i++){if(!cards[i].getAttribute("data-stage"))return "missing-data-stage";}'\
  'for(var i=0;i<spans.length;i++){var code=spans[i].getAttribute("data-status-code");if(!code)return "missing-data-status-code";'\
  'var text=spans[i].textContent;if(codes.indexOf(code)>=0&&text.indexOf(code)>=0)return "raw-code-visible:"+text;}'\
  'if(cards[0].getAttribute("data-status-code")==null&&!spans.length)return "no-declared";'\
  'return true})()'
 try:
  r.start()
  for name,url in BOOKS.items():
   r.navigate(args.base+'/?sky=1&data='+url);ready()
   ev('CLSkyDeconstruction.open();CLSkyDeconstruction.setMode("foreshadow")');time.sleep(.3)
   check(name+' 伏笔卡片声明状态中文在场、原文码仅留在 data 属性',localized)
   check(name+' 已知码文案命中（已兑现声明＋含义短句）','document.getElementById("skyDeconBody").textContent.includes("声明状态：已兑现声明（来源声明此伏笔已兑现）")')
   check(name+' 阶段徽章中文且 data-stage 保留原码','(()=>{var L=CLSky.model().narrative.foreshadowLifecycles,b=document.getElementById("skyDeconBody");return Array.from(b.querySelectorAll(".sd-fore-stage")).every(function(e,i){return e.getAttribute("data-stage")===L[i].stage&&/^[\\u4e00-\\u9fa5]/.test(e.textContent)})})()')
   ev('CLSkyDeconstruction.setMode("causal")');time.sleep(.3)
   check(name+' 因果页依据与未解析引用全部中文，无英文码裸露','(()=>{var t=document.getElementById("skyDeconBody").textContent,codes='+raw+';'
    'if(!t.includes("原文明确声明")&&!t.includes("材料归纳")&&!t.includes("未核验"))return "missing-basis-cn";'
    'var bs=document.querySelectorAll("#skyDeconBody .sd-unresolved li b");'
    'for(var i=0;i<bs.length;i++){if(/^[a-z_]+$/.test(bs[i].textContent))return "raw-reason:"+bs[i].textContent;}return true})()')
   check(name+' 未解析引用原因文案命中映射表','(()=>{var L=CLSky.model().narrative.unresolved,t=document.getElementById("skyDeconBody").textContent;return !L.length||L.every(function(x){return x.reason==null?t.indexOf("状态未提供")>=0:t.indexOf(window.CLSkyStatusText.label("causalReason",x.reason))>=0})})()')
  check('no uncaught JavaScript, Promise, shader or frame-hook errors across both books','__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0&&CLApp.scene().core().perf().frameHooks.errors===0')
  result={'ok':all(x['ok']for x in checks),'checks':checks,'modelsCalled':0,'sourceFilesChanged':False,'viewport':[1440,900]};(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({'ok':result['ok'],'checks':len(checks),'out':str(out)}),flush=True)
  if not result['ok']:raise SystemExit(1)
 finally:r.close()
if __name__=='__main__':main()
