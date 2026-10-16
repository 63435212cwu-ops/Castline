#!/usr/bin/env python3
"""Native mobile enrichment UI with mock HTTP/SSE; never calls a model.

All POST requests are intercepted before page code loads. Existing graph files
are read-only. Success fixtures exercise the actual revision mounting bridge.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import sky_chaos as chaos

MOCK = r"""(()=>{
 const original=window.fetch.bind(window),enc=new TextEncoder(),streams={};let count=0;
 window.__enrichFixture={mode:'success',requests:[],forbidden:[],jobs:[],semanticCalls:0,configReads:0};
 const F=__enrichFixture,config={current:'fixture',profiles:[{id:'fixture',name:'Offline fixture',kind:'openai',base_url:'https://fixture.invalid',model:'offline-only',has_key:true,key:true,last_used:'unchanged'}],history:[],presets:[]};
 const json=(d,status=200)=>Promise.resolve(new Response(JSON.stringify(d),{status,headers:{'content-type':'application/json'}}));
 const frame=(e,d)=>enc.encode('event: '+e+'\ndata: '+JSON.stringify(d)+'\n\n');
 function ids(){return (window.CLApp&&CLApp.graph()?CLApp.graph().events:[]).map((e,i)=>e.id||'server-fixture-'+i);}
 function plan(p){const eventIds=p.eventIds||ids();return {key:p.sourceOnly?'111111111111111111111111':'222222222222222222222222',sourceKey:p.key,originalHash:'a'.repeat(64),writePolicy:'new_version_original_unchanged',layers:p.layers,events:eventIds.length,batches:Math.ceil(eventIds.length/80),estimatedCalls:p.sourceOnly?0:Math.ceil(eventIds.length/80),sourceContext:{batches:[{contextComplete:true}]},scope:p.eventIds?'selected_events':'existing_event_manifest',identity:{eventIds,sourceOnly:p.sourceOnly}};}
 function complete(p){const key='ab'.repeat(12),graph=JSON.parse(JSON.stringify(CLApp.graph()));graph.meta=graph.meta||{};graph.meta.revision={key,parentKey:p.key,originalPreserved:true};graph.meta.enrichment={status:'source_only',calls:0,resumedBatches:0};
  return {key,parentKey:p.key,originalPreserved:true,sourceOnly:p.sourceOnly,enrichment:graph.meta.enrichment,graph};}
 window.fetch=function(url,opt={}){
  const path=new URL(typeof url==='string'?url:url.url,location.href).pathname,method=(opt.method||'GET').toUpperCase();let p={};try{p=JSON.parse(opt.body||'{}')}catch(e){}
  if(path==='/api/health')return json({configured:false,key:false,model:'',profiles:0});
  if(path==='/api/llm-config'){if(method!=='GET'){F.forbidden.push(path);return Promise.reject(Error('Config mutation forbidden'));}F.configReads++;return json(config);}
  if(path==='/api/jobs')return json({jobs:F.jobs});
  if(path==='/api/history'&&method==='POST')return original('/api/history');
  if(path==='/api/enrich/plan'){F.requests.push({path,p});return json(plan(p));}
  if(path==='/api/cancel'){F.requests.push({path,p});const c=streams[p.job];if(c){c.enqueue(frame('cancelled',{message:'已取消 · 离线fixture'}));c.close();delete streams[p.job];}return json({ok:!!c});}
  if(path==='/api/enrich'){
   F.requests.push({path,p});const job=p.job||'Efixture-'+(++count);
   if(!p.sourceOnly)F.semanticCalls++;
   return Promise.resolve(new Response(new ReadableStream({start(c){
    c.enqueue(frame('hello',{job,kind:'enrich',attached:!!p.job,model:'offline-only'}));
    if(F.mode==='403'){c.enqueue(frame('error',{message:'模型 HTTP 403 Forbidden'}));c.enqueue(frame('done',complete(p)));c.close();return;}
    if(F.mode==='cancel'){streams[job]=c;c.enqueue(frame('stage',{stage:'narrative-sources',text:'来源核对'}));return;}
    if(F.mode==='interrupt'){c.enqueue(frame('stage',{stage:'narrative-sources'}));c.close();return;}
    c.enqueue(frame('progress',{done:1,n:1,calls:0,resumed:0}));c.enqueue(frame('done',complete(p)));c.close();
   }}),{headers:{'content-type':'text/event-stream'}}));
  }
  if(method==='POST'){F.forbidden.push(path);return Promise.reject(Error('Real POST forbidden by enrichment regression: '+path));}
  return original(url,opt);
 };
})()"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8137')
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=False)
    data = 'data/cache/d16db79a529a1727352091d5.json'
    original_hash = hashlib.sha256((ROOT / data).read_bytes()).hexdigest()
    checks = []
    b = chaos.Browser(390, 844)

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            raise AssertionError(name + ': ' + json.dumps(detail, ensure_ascii=False)[:2500])

    def key(k):
        code = {'Tab': 9, 'ArrowDown': 40, 'ArrowUp': 38, 'Home': 36, 'Enter': 13, 'Escape': 27}[k]
        for typ in ('keyDown', 'keyUp'):
            kwargs = {'type': typ, 'key': k, 'code': k, 'windowsVirtualKeyCode': code}
            if typ == 'keyDown' and k == 'Enter':
                kwargs.update(text='\r', unmodifiedText='\r')
            b.ws.call('Input.dispatchKeyEvent', **kwargs)
        time.sleep(.15)

    def tap(selector):
        b.ev("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");if(e)e.scrollIntoView({block:'nearest'});})()")
        b.until("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");if(!e)return false;const r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return !!(h&&(h===e||e.contains(h)));})()", 12)
        pos = b.ev("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");if(!e)throw Error('Missing '+" + json.dumps(selector) + ");e.scrollIntoView({block:'nearest'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,h=document.elementFromPoint(x,y);return {x,y,owned:!!(h&&(h===e||e.contains(h))),hit:h&&(h.id||h.getAttribute('class'))};})()")
        check('touch target owns ' + selector, pos['owned'], pos)
        b.ws.call('Input.dispatchTouchEvent', type='touchStart', touchPoints=[{'x': pos['x'], 'y': pos['y'], 'id': 1, 'radiusX': 3, 'radiusY': 3, 'force': 1}])
        time.sleep(.04)
        b.ws.call('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])
        time.sleep(.25)

    def open_panel():
        tap('#skyTools'); tap('#skyToolsMenu [data-for=btnEnrich]')
        check('structure enrichment menu opens real panel', b.until("!!(CLSkyEnrich.state()&&!document.getElementById('skyEnrichPanel').hidden)", 3), state())
        check('relationship enrichment has its own labeled scope control', b.ev("(()=>{const c=document.querySelector('#skyEnrichPanel input[data-layer=relations]');return !!c&&c.parentElement.textContent.includes('人物关系');})()"), state())

    def state():
        return b.ev("(()=>{const r=document.getElementById('skyEnrichPanel');return {key:CLApp.key(),enrich:CLSkyEnrich.state(),text:r&&r.textContent,status:r&&r.querySelector('.ske-status').textContent,error:r&&r.querySelector('.ske-error').textContent,startDisabled:r&&r.querySelector('[data-action=start]').disabled,apiVisible:r&&!r.querySelector('[data-action=api]').hidden,originalVisible:r&&!r.querySelector('[data-action=original-version]').hidden,fixture:__enrichFixture};})()")

    def feedback_visible(selectors):
        return b.until("(()=>{const body=document.querySelector('#skyEnrichPanel .ske-body'),clip=body.getBoundingClientRect();return " + json.dumps(selectors) + ".every(s=>{const e=document.querySelector('#skyEnrichPanel '+s);if(!e||e.hidden)return false;const r=e.getBoundingClientRect(),style=getComputedStyle(e),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return r.width>0&&r.height>0&&style.display!=='none'&&style.visibility!=='hidden'&&r.top>=Math.max(clip.top,0)-1&&r.bottom<=Math.min(clip.bottom,innerHeight)+1&&r.left>=0&&r.right<=innerWidth&&!!hit&&(hit===e||e.contains(hit));});})()", 3)

    def shot(name):
        (args.out / name).write_bytes(base64.b64decode(b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)['data']))

    def preview_start():
        tap('#skyEnrichPanel [data-action=plan]')
        check('readonly plan is ready before execution', b.until('!!CLSkyEnrich.state().plan', 3), state())
        tap('#skyEnrichPanel [data-action=start]')

    report = {}
    try:
        b.start(); b.ws.call('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=1, mobile=True)
        b.ws.call('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=1)
        b.ws.call('Page.addScriptToEvaluateOnNewDocument', source=MOCK)
        b.ws.call('Page.navigate', url=args.base.rstrip('/') + '/?data=' + data)
        if not b.until("!!(window.CLSkyEnrich&&CLApp.graph()&&CLSkyDeep.stats().stars.ignite>.99)", 60):
            raise RuntimeError('Module/book readiness failed')
        b.ev("window.__enrichNative=[];['touchstart','click','keydown','change'].forEach(t=>document.addEventListener(t,e=>__enrichNative.push({type:t,trusted:e.isTrusted,target:e.target.id||e.target.className}),true));")
        original_key = b.ev('CLApp.key()')
        check('unconfigured startup leaves the cached book readable', b.ev("!document.getElementById('apiPanel').classList.contains('on')&&!CLApp.apiOk()"), b.ev('window.__apiTrace'))
        b.ev('CLApp.openApi()')
        tap('#apiClose')
        check('setup closes without a key and keeps the current book', b.ev("!document.getElementById('apiPanel').classList.contains('on')") and b.ev('CLApp.key()') == original_key, b.ev('window.__apiTrace'))
        open_panel()
        check('default is zero model source check', state()['enrich']['sourceOnly'], state())
        check('local source check hides irrelevant layer and event choices', b.ev("document.querySelector('#skyEnrichPanel .ske-layers').hidden&&document.querySelector('#skyEnrichPanel .ske-scope').hidden"), state())
        config_reads = state()['fixture']['configReads']
        preview_start()
        check('source check produces revision without a semantic call', b.until("CLSkyEnrich.state().phase==='done'", 4) and state()['fixture']['semanticCalls'] == 0, state())
        check('local source check does not depend on API profile reads', state()['fixture']['configReads'] == config_reads, state())
        check('completion and new-version action are visible without test scrolling', feedback_visible(['.ske-status', '[data-action=new-version]']), state())
        shot('source-complete.png')
        tap('#skyEnrichPanel [data-action=new-version]')
        check('actual stagedMount bridge enters new version', b.until("CLApp.key()==='abababababababababababab'", 6), b.ev('CLApp.key()'))
        time.sleep(2)
        open_panel()
        check('parent version remains visibly reachable after mounting', state()['originalVisible'], state())
        tap('#skyEnrichPanel [data-action=original-version]')
        check('actual library bridge returns to original', b.until('CLApp.key()===' + json.dumps(original_key), 6), b.ev('CLApp.key()'))
        time.sleep(2); open_panel()
        for _ in range(25):
            if b.ev("document.activeElement.matches('#skyEnrichPanel select[aria-label=\"补析方式\"]')"):
                break
            key('Tab')
        key('ArrowDown'); key('Enter')
        check('native select chooses semantic enrichment', not state()['enrich']['sourceOnly'], state())
        check('semantic mode restores meaningful layer and range choices', b.ev("!document.querySelector('#skyEnrichPanel .ske-layers').hidden&&!document.querySelector('#skyEnrichPanel .ske-scope').hidden"), state())
        b.ev("__enrichFixture.mode='403'")
        preview_start()
        check('403 is failure with API entry, no fake done or mounted version', b.until("CLSkyEnrich.state().phase==='failed'", 3) and state()['apiVisible'] and not state()['enrich']['resultKey'] and state()['key'] == original_key, state())
        check('403 explanation and local recovery are visible without test scrolling', feedback_visible(['.ske-error', '[data-action=local]']), state())
        shot('semantic-403-immediate.png')
        first_count = state()['fixture']['semanticCalls'];
        tap('#skyEnrichPanel [data-action=plan]')
        check('same rejected configuration is not retried', b.until("!!CLSkyEnrich.state().plan", 3) and state()['startDisabled'] and state()['fixture']['semanticCalls'] == first_count, state())
        check('rechecking blocked plan retains visible explanation and recovery', bool(state()['error']) and feedback_visible(['.ske-error', '[data-action=local]']), state())
        shot('semantic-403.png')
        tap('#skyEnrichPanel [data-action=local]')
        check('zero model option remains usable after auth failure', state()['enrich']['sourceOnly'], state())
        check('local fallback only changes choice and waits for review', state()['enrich']['phase'] == 'idle' and not state()['enrich']['plan'] and state()['fixture']['semanticCalls'] == first_count and not state()['error'], state())
        b.ev("__enrichFixture.mode='cancel'"); preview_start()
        check('running operation has a confirmed job', b.until("CLSkyEnrich.state().busy&&!!CLSkyEnrich.state().job", 3), state())
        tap('#skyEnrichPanel [data-action=cancel]')
        check('cancel terminates only this operation without success', b.until("CLSkyEnrich.state().phase==='cancelled'", 3) and not state()['enrich']['resultKey'], state())
        check('cancellation status stays visible without test scrolling', feedback_visible(['.ske-status']), state())
        b.ev("__enrichFixture.mode='interrupt'"); preview_start()
        check('disconnection stops after same-job bounded recovery', b.until("CLSkyEnrich.state().phase==='interrupted'", 6), state())
        check('interruption status and resume action are visible without test scrolling', feedback_visible(['.ske-status', '[data-action=resume]']), state())
        requests = state()['fixture']['requests']; runs = [r['p'] for r in requests if r['path'] == '/api/enrich'][-3:]
        check('automatic reconnect requests attach the confirmed same job', len(runs) == 3 and bool(runs[1].get('job')) and runs[1]['job'] == runs[2]['job'], runs)
        b.ev("__enrichFixture.mode='success'")
        tap('#skyEnrichPanel [data-action=resume]')
        check('explicit recovery resumes and completes the existing job', b.until("CLSkyEnrich.state().phase==='done'", 4), state())
        native = b.ev('__enrichNative')
        health = b.ev("({errors:__headlessHealth.jserr,rejections:__headlessHealth.jsrej,shaders:CLApp.scene().shaderErrors()})")
        check('all UI events trusted and runtime healthy', bool(native) and all(e['trusted'] for e in native) and not health['errors'] and not health['rejections'] and not health['shaders'], {'native': native, 'health': health})
        check('fixture blocks every real POST/model/write', not state()['fixture']['forbidden'], state()['fixture']['forbidden'])
        report.update(ok=True, final=state(), native=native, health=health)
    except Exception as exc:
        report.update(ok=False, error=str(exc)); print('FAIL session: ' + str(exc), flush=True)
        try:
            shot('failure.png'); report['failure'] = state()
        except Exception:
            pass
    finally:
        b.close()
    unchanged = hashlib.sha256((ROOT / data).read_bytes()).hexdigest() == original_hash
    report.update(checks=checks, originalGraphUnchanged=unchanged, boundary='Native mobile UI, actual mounting/library bridge; mock plan/SSE/config/cancel. All real POST/model calls blocked before page initialization.')
    report['ok'] = report.get('ok', False) and unchanged and all(c['ok'] for c in checks)
    (args.out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
