#!/usr/bin/env python3
"""PERF-02: real-time cold/warm compass entry diagnostics, with automatic quality.

Run serially with other GPU work. Default captures rAF, long tasks and the nebula
GPU query. --detail adds CPU/GL wrappers; --trace adds a Chrome trace. Those two
modes add overhead and are for attribution, not acceptance FPS. No score/quality
threshold is changed. 'Cold' means first compass entry after normal app prewarm,
not a cold browser shader cache. Every invocation uses a fresh browser profile.

python3 -s tests/compass_entry_profile.py --out /tmp/compass-entry --detail --trace
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from atlas_review_shots import Session, headless


PROBE = r'''(async function(cfg){
 const S=CLApp.scene(),R=S.renderer,gl=R.getContext(),rows=[],gpu=[],long=[],loaf=[],cpu=[],pending=[],restore=[],totals={};
 const ext=gl.getExtension('EXT_disjoint_timer_query_webgl2'),hero=cfg.hero;
 let cloud=null;S.scene.traverse(o=>{if(o.material&&o.material.uniforms&&o.material.uniforms.tSplat&&o.material.uniforms.uCam)cloud=o;});
 if(!cloud)throw Error('Nebula mesh not found');
 const oldBefore=cloud.onBeforeRender,oldAfter=cloud.onAfterRender,observers=[],firstDraw=new Set();
 let active=null,last=null,t0=performance.now(),frameIndex=-1,directContext=null,skippedQueries=0;
 function snap(){return {quality:S.quality(),cache:S.crownCacheInfo?S.crownCacheInfo(true):null,
   memory:{...R.info.memory},programs:R.info.programs.length,camera:S.camera.position.toArray(),target:S.controls.target.toArray(),
   mode:CLSky.state(),nebula:CLSkyDeep.stats().nebula};}
 function emit(entries,key){entries.forEach(x=>{
   if(key==='longtask')long.push({at:x.startTime-t0,ms:x.duration});
   else loaf.push({at:x.startTime-t0,ms:x.duration,blocking:x.blockingDuration,renderStart:x.renderStart-t0,
     styleAndLayoutStart:x.styleAndLayoutStart-t0,scripts:Array.from(x.scripts||[]).map(s=>({at:s.startTime-t0,ms:s.duration,
       function:s.sourceFunctionName,url:s.sourceURL,line:s.sourceCharPosition,invoker:s.invoker,
       forcedStyleAndLayout:s.forcedStyleAndLayoutDuration}))});
 });}
 function observe(key){if(window.PerformanceObserver&&PerformanceObserver.supportedEntryTypes.includes(key)){
   const obs=new PerformanceObserver(xs=>emit(xs.getEntries(),key));obs.observe({type:key});observers.push({obs,key});}}
 function record(name,at,ms,meta,keep){
   let b=totals[name];if(!b)b=totals[name]={count:0,ms:0,max:0};b.count++;b.ms+=ms;b.max=Math.max(b.max,ms);
   if(typeof meta.bytes==='number')b.bytes=(b.bytes||0)+meta.bytes;
   if(keep||ms>=1)cpu.push({name,at:at-t0,ms,frame:frameIndex,...meta});
 }
 function wrap(obj,key,name,meta){const old=obj&&obj[key];if(typeof old!=='function')return;
   const wrapped=function(){const start=performance.now(),m=meta?meta(arguments):{};
     try{return old.apply(this,arguments);}finally{record(name,start,performance.now()-start,m,
       name.indexOf('render.')===0||key==='bufferData'||key==='texImage2D'||key==='texStorage2D');}};
   obj[key]=wrapped;if(obj[key]!==wrapped)throw Error('Cannot instrument '+name);restore.push(()=>{obj[key]=old;});}
 function dataBytes(v){return typeof v==='number'?v:v&&typeof v.byteLength==='number'?v.byteLength:null;}
 if(cfg.detail){
   // scene.js already captures core.buildSpines in a closure: Chrome's trace
   // attributes that builder; patching the public property cannot observe it.
   wrap(CLApp.atlas,'view','atlas.view');wrap(CLApp.atlas,'syncLabels','atlas.syncLabels');
   wrap(window.CLSkyCompass,'open','compass.open');wrap(CLSkyDeep,'setMode','deep.setMode');
   const render=R.render;R.render=function(sc){const start=performance.now();
     try{return render.apply(this,arguments);}finally{record(sc===S.scene?'render.main':'render.offscreen',start,performance.now()-start,
       {sceneId:sc.id,calls:R.info.render.calls},true);}};restore.push(()=>{R.render=render;});
   const direct=R.renderBufferDirect;R.renderBufferDirect=function(cam,sc,geo,mat,obj){
     const start=performance.now(),key=geo.id+':'+mat.id,first=!firstDraw.has(key),prev=directContext;
     directContext={geometry:geo.id,material:mat.id,object:obj.id,name:obj.name||'',type:obj.type};firstDraw.add(key);
     try{return direct.apply(this,arguments);}finally{
       record('renderBufferDirect',start,performance.now()-start,{...directContext,first},first);directContext=prev;}
   };restore.push(()=>{R.renderBufferDirect=direct;});
   ['bufferData','bufferSubData','texImage2D','texSubImage2D','texStorage2D','compileShader','linkProgram','getProgramParameter','getShaderParameter'].forEach(key=>{
     wrap(gl,key,'gl.'+key,args=>({...(directContext||{}),bytes:key==='bufferData'?dataBytes(args[1]):key==='bufferSubData'?dataBytes(args[2]):null}));
   });
 }
 function poll(){for(let i=pending.length-1;i>=0;i--){const p=pending[i];if(gl.getQueryParameter(p.q,gl.QUERY_RESULT_AVAILABLE)){
   gpu.push({at:p.at,alpha:p.alpha,ms:gl.getQueryParameter(p.q,gl.QUERY_RESULT)/1e6,disjoint:!!gl.getParameter(ext.GPU_DISJOINT_EXT)});
   gl.deleteQuery(p.q);pending.splice(i,1);}}}
 if(ext){cloud.onBeforeRender=function(){oldBefore.apply(this,arguments);
   if(gl.getQuery(ext.TIME_ELAPSED_EXT,gl.CURRENT_QUERY)){skippedQueries++;return;}
   active=gl.createQuery();gl.beginQuery(ext.TIME_ELAPSED_EXT,active);};
   cloud.onAfterRender=function(){oldAfter.apply(this,arguments);if(!active)return;
     gl.endQuery(ext.TIME_ELAPSED_EXT);pending.push({q:active,at:performance.now()-t0,alpha:cloud.material.uniforms.uAlpha.value});active=null;};}
 let before,after,openMs,ok,unresolvedQueries=0;
 try{
   before=snap();t0=performance.now();observe('longtask');if(cfg.detail)observe('long-animation-frame');
   performance.mark('compass-entry-'+cfg.label+'-start');
   const start=performance.now();ok=CLSky.openCompass(hero);openMs=performance.now()-start;
   if(!ok)throw Error('openCompass failed for '+hero);
   await new Promise(resolve=>{function frame(t){
     frameIndex++;const q=S.quality();rows.push({at:t-t0,callbackAt:performance.now()-t0,dt:last===null?0:t-last,
       w:q.drawW,h:q.drawH,boost:q.boost,degrade:q.degrade,steps:CLSkyDeep.stats().nebula.steps,
       visible:cloud.visible,alpha:cloud.material.uniforms.uAlpha.value,programs:R.info.programs.length});last=t;
     if(ext)poll();if(t-t0>=cfg.seconds*1000)resolve();else requestAnimationFrame(frame);
   }requestAnimationFrame(frame);});
   performance.mark('compass-entry-'+cfg.label+'-end');after=snap();
 }finally{
   observers.forEach(({obs,key})=>{emit(obs.takeRecords(),key);obs.disconnect();});
   cloud.onBeforeRender=oldBefore;cloud.onAfterRender=oldAfter;
   if(active){gl.endQuery(ext.TIME_ELAPSED_EXT);gl.deleteQuery(active);}
   if(ext)poll();unresolvedQueries=pending.length;pending.forEach(p=>gl.deleteQuery(p.q));
   restore.reverse().forEach(fn=>fn());
 }
 return {hero,label:cfg.label,detail:cfg.detail,before,after,openMs,ok,rows,gpu,long,loaf,cpu,totals,
   timerSupported:!!ext,skippedQueries,unresolvedQueries,error:gl.getError()};
})(__CONFIG__)'''


def distribution(values):
    a = sorted(values)
    if not a:
        return {'n': 0}
    return {'n': len(a), 'mean': statistics.mean(a), 'p50': a[len(a) // 2],
            'p95': a[min(len(a) - 1, int(len(a) * .95))], 'max': a[-1]}


def summarize(p):
    windows = []
    for lo, hi in ((0, 250), (250, 500), (500, 900), (900, 1000), (1000, 4000), (4000, 7000)):
        windows.append({'from': lo, 'to': hi,
                        'frameMs': distribution([r['dt'] for r in p['rows'] if lo <= r['at'] < hi and r['dt'] > 0]),
                        'cloudGpuMs': distribution([r['ms'] for r in p['gpu'] if lo <= r['at'] < hi and not r['disjoint']])})
    return {'hero': p['hero'], 'openMs': p['openMs'], 'long': p['long'],
            'firstCallbackMs': p['rows'][0]['callbackAt'] if p['rows'] else None,
            'windows': windows, 'sizes': sorted({(r['w'], r['h']) for r in p['rows']}),
            'programs': sorted({r['programs'] for r in p['rows']}), 'error': p['error']}


class Events:
    """Route optional Fetch overlays and preserve trace completion events."""
    def __init__(self, ws, snapshot, report):
        self.ws, self.raw_recv, self.complete = ws, ws.recv, None
        self.overlay = {}
        if snapshot:
            for p in snapshot.rglob('*'):
                key = str(p.relative_to(snapshot))
                if p.is_file() and p.suffix in ('.js', '.css') and not key.startswith('tests/') and 'extra-' not in key:
                    self.overlay[key] = base64.b64encode(p.read_bytes()).decode()
        self.report = report
        ws.recv = self.recv
        if self.overlay:
            ws.call('Fetch.enable', patterns=[{'urlPattern': '*/' + k + '*', 'requestStage': 'Request'} for k in self.overlay])

    def recv(self):
        while True:
            m = self.raw_recv()
            if m.get('method') == 'Fetch.requestPaused':
                q = m['params']; key = urllib.parse.unquote(urllib.parse.urlparse(q['request']['url']).path).lstrip('/')
                self.ws.id += 1
                if key in self.overlay:
                    params = {'requestId': q['requestId'], 'responseCode': 200,
                              'responseHeaders': [{'name': 'Content-Type', 'value': 'text/css' if key.endswith('.css') else 'application/javascript'},
                                                  {'name': 'Cache-Control', 'value': 'no-store'}], 'body': self.overlay[key]}
                    self.ws.send({'id': self.ws.id, 'method': 'Fetch.fulfillRequest', 'params': params})
                    self.report['overlay'].append(key)
                else:
                    self.ws.send({'id': self.ws.id, 'method': 'Fetch.continueRequest', 'params': {'requestId': q['requestId']}})
                continue
            if m.get('method') == 'Tracing.tracingComplete':
                self.complete = m['params']
            return m

    def trace_start(self):
        self.complete = None
        self.ws.call('Tracing.start', transferMode='ReturnAsStream',
                     categories='devtools.timeline,v8,blink.user_timing,disabled-by-default-devtools.timeline,disabled-by-default-devtools.timeline.stack,disabled-by-default-v8.cpu_profiler')

    def trace_end(self, path):
        self.ws.call('Tracing.end')
        while self.complete is None:
            self.recv()
        handle = self.complete['stream']
        try:
            with path.open('wb') as f:
                while True:
                    part = self.ws.call('IO.read', handle=handle, size=1024 * 1024)
                    f.write(base64.b64decode(part['data']) if part.get('base64Encoded') else part['data'].encode())
                    if part.get('eof'):
                        break
        finally:
            self.ws.call('IO.close', handle=handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--base', default='http://127.0.0.1:8765/')
    parser.add_argument('--book', default='data/cache/a935953b2678a80b352091d5.json')
    parser.add_argument('--hero', help='defaults to the book\'s most important character')
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--dpr', type=float, default=2)
    parser.add_argument('--seconds', type=float, default=7)
    parser.add_argument('--settle', type=float, default=8)
    parser.add_argument('--detail', action='store_true', help='add CPU/GL instrumentation; affects timings')
    parser.add_argument('--trace', action='store_true', help='save cold/warm Chrome traces; affects timings')
    args = parser.parse_args()
    if args.seconds < 2 or args.settle < 0 or min(args.width, args.height, args.dpr) <= 0:
        parser.error('seconds must be >=2; settle >=0; viewport and DPR positive')
    if args.snapshot and not args.snapshot.is_dir():
        parser.error('snapshot directory does not exist')
    args.out.mkdir(parents=True, exist_ok=True)
    urllib.request.urlopen(args.base, timeout=5).close()
    report = {'config': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              'overlay': [], 'profiles': {}, 'summaries': {}, 'sha256': {},
              'notes': ['No quality pinning, S.step, screenshots or artificial pauses within entry.',
                        'CPU wrapper/Chrome trace overhead applies only when requested.',
                        'GPU measurements cover the nebula draw only, not the full frame.',
                        'Cold is the first compass entry after normal loader prewarm; warm reopens the same character.']}
    for folder in ('js', 'css'):
        for p in (ROOT / folder).rglob('*'):
            if p.is_file() and p.suffix in ('.js', '.css'):
                key = str(p.relative_to(ROOT)); source = args.snapshot / key if args.snapshot and (args.snapshot / key).is_file() else p
                report['sha256'][key] = hashlib.sha256(source.read_bytes()).hexdigest()
    report['sha256'][str(Path(__file__).relative_to(ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    session = Session(args.width, args.height)
    def ev(code, wait=False):
        value = session.eval(code, await_promise=wait)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(value)
        return value
    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=args.width, height=args.height, deviceScaleFactor=args.dpr, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        events = Events(session.ws, args.snapshot, report)
        session.navigate(args.base.rstrip('/') + '/?' + urllib.parse.urlencode({'sky': 1, 'probe': 1, 'data': args.book}))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if ev('!!(window.CLSkyDeep&&CLSkyDeep.stats().inited&&CLSkyDeep.stats().stars.ignite>.99&&!document.getElementById("clSigil"))'):
                break
            time.sleep(.2)
        else:
            raise RuntimeError('Scene did not become ready within 60 seconds')
        hero = args.hero or ev('CLApp.graph().characters.slice().sort((a,b)=>(b.importance||0)-(a.importance||0))[0].name')
        for label in ('cold', 'warm'):
            if label == 'warm':
                ev('CLSky.closeCompass()')
            ev('new Promise(r=>setTimeout(r,%d))' % round(args.settle * 1000), True)
            if args.trace:
                events.trace_start()
            try:
                cfg = {'hero': hero, 'label': label, 'seconds': args.seconds, 'detail': args.detail}
                p = ev(PROBE.replace('__CONFIG__', json.dumps(cfg, ensure_ascii=False)), True)
                report['profiles'][label] = p
                report['summaries'][label] = summarize(p)
                print(json.dumps({label: report['summaries'][label]}, ensure_ascii=False), flush=True)
            finally:
                if args.trace:
                    events.trace_end(args.out / ('trace-' + label + '.json'))
            (args.out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        report['health'] = headless.post_health(session.ws, [])
    except Exception as exc:
        report['failure'] = repr(exc)
        raise
    finally:
        (args.out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        session.close()
    return 0 if report.get('health') == 0 and all(p['error'] == 0 for p in report['profiles'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
