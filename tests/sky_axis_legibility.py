#!/usr/bin/env python3
"""Native axis opacity ownership and literal evidence-status regression; serial GPU."""
from pathlib import Path
import argparse,json,time
from atlas_review_shots import Session,headless
ap=argparse.ArgumentParser();ap.add_argument('--base',default='http://127.0.0.1:8765');ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
s=Session(1280,800);report={'samples':[],'checks':{}}
READ="""(()=>{const S=CLApp.scene();return Array.from(document.querySelectorAll('#labels .cl-lab.attr.on,#labels .cl-lab.meta.on')).filter(e=>getComputedStyle(e).visibility!=='hidden'&&e.getBoundingClientRect().width>0).map(e=>{const key=(e.classList.contains('attr')?'a:':'m:')+e.querySelector('.ln').textContent.trim(),n=S.nodeOf(key),cs=getComputedStyle(e);return {key,known:e.getAttribute('data-known'),confidence:e.getAttribute('data-confidence'),score:e.getAttribute('data-score'),nodeAlpha:n.alpha,inline:+e.style.opacity,computed:+cs.opacity,filter:cs.filter,animations:e.getAnimations().map(x=>({name:x.animationName||'',state:x.playState}))};})})()"""
def ev(code,wait=False):
 r=s.eval(code,await_promise=wait)
 if isinstance(r,dict) and r.get('__evalError'):raise RuntimeError(r)
 return r
def delay(ms):ev('new Promise(r=>setTimeout(r,%d))'%ms,True)
def sample(name):
 rows=ev(READ);report['samples'].append({'name':name,'rows':rows});report['checks'][name+'-opacity-owned']=bool(rows) and all(abs(x['computed']-x['inline'])<.001 for x in rows);return rows
try:
 s.start();s.ws.call('Page.addScriptToEvaluateOnNewDocument',source=headless.HEALTH_INIT_JS);s.navigate(a.base.rstrip('/')+'/?sky=1&probe=1&data=data/cache/d16db79a529a1727352091d5.json')
 deadline=time.monotonic()+45
 while time.monotonic()<deadline:
  if ev('!!(window.CLSkyDeep&&CLSkyDeep.stats().inited&&CLSkyDeep.stats().stars.ignite>.99&&!document.getElementById("clSigil"))'):break
  time.sleep(.2)
 else:raise RuntimeError('not ready')
 delay(4000);ev('CLSky.openCompass("孙悟空")');delay(4000);ev('CLApp.scene().setCalm(true)');delay(700);ev('window.__axisGraph=JSON.stringify(CLApp.graph())')
 report['documentFocusBefore']=ev('document.hasFocus()');s.ws.call('Emulation.setFocusEmulationEnabled',enabled=True);delay(100)
 rows=sample('normal');by={x['key']:x for x in rows}
 report['checks']['confidence-order']=by['a:实力']['confidence']=='low' and by['a:智谋']['confidence']=='supported' and by['a:实力']['nodeAlpha']<by['a:实力']['computed']<by['a:智谋']['computed']
 for key,unverified in [('实力',True),('智谋',False)]:
  ev('CLApp.scene().nodeOf('+json.dumps('a:'+key)+').el.focus({preventScroll:true})');delay(350)
  card=ev("Array.from(document.querySelectorAll('#skyCard .skd-card__title small')).map(e=>e.textContent)");report[key+'Card']=card;report[key+'Diagnostic']=ev("({debug:window.__axisDebug||null,hasFocus:document.hasFocus(),state:CLSky.state().compass,active:document.activeElement.outerHTML.slice(0,1200),card:document.querySelector('#skyCard').outerHTML.slice(0,2000),mode:CLSkyDeep.stats().mode})");report['checks'][key+'-verification-tag']=('未核验' in card)==unverified
  raw=ev('CLApp.graph().characters.find(x=>x.name==="孙悟空").attrs['+json.dumps(key)+']');report['checks'][key+'-low-tag']=('证据不足' in card)==bool(raw.get('low'))
 ev('document.activeElement.blur()');s.ws.call('Emulation.setDeviceMetricsOverride',width=390,height=844,deviceScaleFactor=2,mobile=False);delay(1000);sample('narrow')
 ev('CLApp.scene().setDegrade(2)');delay(600);sample('low')
 s.ws.call('Emulation.setEmulatedMedia',features=[{'name':'prefers-reduced-motion','value':'reduce'}]);delay(600);sample('reduced')
 report['checks']['source-graph-unchanged']=ev('JSON.stringify(CLApp.graph())===__axisGraph');report['health']=headless.post_health(s.ws,[]);report['ok']=report['health']==0 and all(report['checks'].values());print(json.dumps({'ok':report['ok'],'checks':report['checks']},ensure_ascii=False),flush=True)
finally:
 (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));s.close()
raise SystemExit(0 if report.get('ok') else 1)
