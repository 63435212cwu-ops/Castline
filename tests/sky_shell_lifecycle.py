#!/usr/bin/env python3
"""Real Chrome regression: loader A→B timer races, native normal/skip/error, line/card→close→reopen→seek.

Only loader-owned callbacks are controllably reordered in race cases; production code, real DOM/scene,
and graph data are used. Normal/skip/error use native timers; line/card interaction uses CDP input.
No data or server history writes. Run after the candidate production fixes are applied.
"""
import argparse, json, os, signal, subprocess, sys, tempfile, time, urllib.request, shutil
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent

def _node_exe():
    """找 Node 可执行文件。**不写死版本号**（2026-10-09 实测事故）。

    这里原先是 `…/node/versions/22.22.2-3/bin/node`，而 workbuddy 把 Node 换成
    `22.22.2-6` 并删掉旧目录 ⇒ 本脚本在该分支直接 FileNotFoundError。
    解析顺序：ATLAS_NODE → PATH → versions/ 下最高版本。
    """
    p = os.environ.get('ATLAS_NODE')
    if p and Path(p).is_file():
        return p
    from shutil import which
    w = which('node')
    if w:
        return w
    base = Path('/Users/carmen/.workbuddy/binaries/node/versions')
    if base.is_dir():
        cands = sorted([d for d in base.iterdir() if d.is_dir() and d.name[:1].isdigit()],
                       key=lambda d: [int(x) for x in d.name.split('.') if x.isdigit()] or [0])
        if cands and (cands[-1] / 'bin' / 'node').is_file():
            return str(cands[-1] / 'bin' / 'node')
    return 'node'

ROOT = Path(os.environ.get('CL_PROJECT_ROOT', '/Users/carmen/Desktop/星系'))
sys.path.insert(0, str(ROOT / 'tests'))
import headless

BOOT = "!!(window.__shellRegression && !__shellRegression.navigationStale && document.readyState==='complete' && window.CLSkyChrome && __shellRegression.ctx && window.CLSky && CLSky.model() && window.CLSkyDeep && CLSkyDeep.stats().stars && CLSkyDeep.stats().stars.ignite>.99 && !Array.prototype.some.call(document.querySelectorAll('.skd-loader'), function(e){return !e.hidden;}))"
INIT = (HERE / 'sky_shell_lifecycle_init.js').read_text()
LOADER = (HERE / 'sky_shell_lifecycle_loader.js').read_text()
STATE = (HERE / 'sky_shell_lifecycle_state.js').read_text()

class Browser:
    def __init__(self):
        self.profile = tempfile.mkdtemp(prefix='cl-shell-lifecycle-'); self.proc = self.ws = None
    def start(self):
        gpu = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization'] if os.environ.get('CL_GPU') == '1' else ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
        self.proc = subprocess.Popen([headless.CH, '--headless=new'] + gpu + ['--hide-scrollbars', '--window-size=1440,900', '--user-data-dir='+self.profile, '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        tabs = None
        for _ in range(200):
            try:
                port = int((Path(self.profile)/'DevToolsActivePort').read_text().splitlines()[0]); tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list'%port, timeout=2).read()); break
            except Exception: time.sleep(.1)
        if not tabs: raise RuntimeError('Chrome DevTools not reachable')
        self.ws = headless.WS(next(t['webSocketDebuggerUrl'] for t in tabs if t.get('type')=='page'), timeout=180)
        self.ws.call('Runtime.enable'); self.ws.call('Page.enable')
        self.events=[]
        raw_recv=self.ws.recv
        def recv_and_keep_fetch_events():
            message=raw_recv()
            if message.get('method')=='Fetch.requestPaused': self.events.append(message)
            return message
        self.ws.recv=recv_and_keep_fetch_events
        self.ws.call('Emulation.setDeviceMetricsOverride', width=1440, height=900, deviceScaleFactor=1, mobile=False)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=INIT)
    def ev(self, expression):
        r=self.ws.call('Runtime.evaluate', expression=expression, returnByValue=True, awaitPromise=True)
        if r.get('exceptionDetails'): raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:1200])
        return r.get('result',{}).get('value')
    def health(self):
        expression = """new Promise(function(resolve){setTimeout(function(){
          var h=window.__headlessHealth,S=window.CLApp&&CLApp.scene&&CLApp.scene(),errors=null,rejections=null,shader=null,frame=null,missing=[];
          if(!h||!Array.isArray(h.jserr))missing.push('__headlessHealth.jserr');else errors=h.jserr.slice();
          if(!h||!Array.isArray(h.jsrej))missing.push('__headlessHealth.jsrej');else rejections=h.jsrej.slice();
          try { if(!S||typeof S.shaderErrors!=='function')missing.push('CLApp.scene().shaderErrors');else shader=S.shaderErrors();
            var d=S&&typeof S.digest==='function'?S.digest():null;
            if(d&&d.frameHooks)frame=d.frameHooks.errors||0;else missing.push('digest.frameHooks');
          } catch(e){missing.push(String(e&&e.message||e));}
          resolve({ok:!missing.length&&!errors.length&&!rejections.length&&Array.isArray(shader)&&!shader.length&&frame===0,
            jserr:errors,jsrej:rejections,shaderErrors:shader,frameHooks:frame,missing:missing});
        },0);})"""
        return self.ev(expression)
    def until(self, expression, timeout=90, step=.05):
        at=time.monotonic()
        while time.monotonic()-at<timeout:
            if self.ev(expression) is True: return True
            time.sleep(step)
        return False
    def navigate(self, base):
        self.ev("if(window.__shellRegression)__shellRegression.navigationStale=true")
        self.ws.call('Page.navigate', url=base.rstrip('/')+'/?sky=1&probe=1&data=data/sample-saga.json')
        if not self.until(BOOT): raise RuntimeError('real graph/loader boot never became ready')
    def navigate_with_shell_held(self, base, query='sky=1&probe=1&data=data/sample-saga.json', timeout=30):
        """Make the late-shell race observable even after a cached navigation."""
        self.ws.call('Network.enable')
        self.ws.call('Network.setCacheDisabled', cacheDisabled=True)
        self.ws.call('Fetch.enable', patterns=[{'urlPattern':'*/js/sky/sky-shell.js*','requestStage':'Request'}])
        request_id = None
        expected = base.rstrip('/') + '/?' + query
        try:
            self.ev("if(window.__shellRegression)__shellRegression.navigationStale=true")
            self.ws.call('Page.navigate', url=expected)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    early_event = bool(self.ev("!!(location.href===%s && window.__shellRegression && !__shellRegression.navigationStale && __shellRegression.bootOrder.graphReady.length && __shellRegression.bootOrder.shellAt===null)" % json.dumps(expected)))
                except Exception:
                    early_event = False
                for i, message in enumerate(self.events):
                    params = message.get('params') or {}; request = params.get('request') or {}
                    if 'js/sky/sky-shell.js' in str(request.get('url', '')):
                        request_id = params.get('requestId'); self.events.pop(i); break
                if request_id and early_event:
                    self.held_early_state = self.ev("({graphReady:__shellRegression.bootOrder.graphReady.length,exported:!!window.CLSky,legacy:!!(window.CLAtlasPreview&&CLAtlasPreview.active()),hud:!!document.querySelector('#atlasPreviewHUD.on'),stale:__shellRegression.navigationStale})")
                    self.ws.call('Fetch.continueRequest', requestId=request_id); request_id = None
                    self.ws.call('Fetch.disable')
                    if not self.until(BOOT):
                        raise RuntimeError('shell did not recover the deliberately missed initial graph-ready event')
                    return True
                time.sleep(.025)
            details = self.ev("({href:location.href,ready:document.readyState,bootOrder:window.__shellRegression&&__shellRegression.bootOrder,stale:window.__shellRegression&&__shellRegression.navigationStale,stage:window.CLLoadStage,error:window.CLLoadError,graph:!!(window.CLApp&&CLApp.graph())})")
            raise RuntimeError('required held-shell race setup not reached: ' + json.dumps({'heldRequest':bool(request_id),'state':details},ensure_ascii=False))
        finally:
            if request_id:
                self.ws.call('Fetch.continueRequest', requestId=request_id)
            self.ws.call('Fetch.disable')
            self.ws.call('Network.setCacheDisabled', cacheDisabled=False)
    def mouse(self, kind, x, y, down=False):
        self.ws.call('Input.dispatchMouseEvent', type=kind, x=x, y=y, button='left' if down or kind!='mouseMoved' else 'none', buttons=1 if down else 0, clickCount=1 if kind in ('mousePressed','mouseReleased') else 0)
    def click(self, x, y):
        self.mouse('mouseMoved',x,y); self.mouse('mousePressed',x,y,True); self.mouse('mouseReleased',x,y)
    def key(self, key='p'):
        code = {' ': 'Space', 'Escape': 'Escape', 'p': 'KeyP', 'P': 'KeyP'}.get(key, key)
        virtual = {' ': 32, 'Escape': 27, 'p': 80, 'P': 80}.get(key, 0)
        for kind in ('keyDown','keyUp'):
            self.ws.call('Input.dispatchKeyEvent', type=kind, key=key, code=code, windowsVirtualKeyCode=virtual)
    def close(self):
        try:
            if self.ws: self.ws.call('Browser.close')
        except Exception: pass
        try:
            if self.proc and self.proc.poll() is None: os.killpg(self.proc.pid,signal.SIGTERM)
        except Exception: pass
        shutil.rmtree(self.profile,ignore_errors=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--base',default='http://127.0.0.1:8765'); ap.add_argument('--only',choices=('all','startup','loader','state'),default='all'); ap.add_argument('--self-test',action='store_true'); a=ap.parse_args()
    if a.self_test:
        for f in ['sky_shell_lifecycle_init.js','sky_shell_lifecycle_loader.js','sky_shell_lifecycle_state.js']:
            subprocess.run([_node_exe(), '--check', str(HERE / f)], check=True)
        compile(Path(__file__).read_text(),str(__file__),'exec')
        print('SHELL-LIFECYCLE source smoke OK; no browser/GPU started'); return 0
    results=[]
    def check(name,ok,detail=None):
        results.append((name,bool(ok))); print(('PASS ' if ok else 'FAIL ')+name+('' if ok else ' '+json.dumps(detail,ensure_ascii=False)[:1400]),flush=True)
    b=Browser()
    try:
        b.start()
        if a.only in ('all','startup'):
            early=b.navigate_with_shell_held(a.base)
            early_state=b.held_early_state
            check('early graph-ready does not activate legacy workspace before CLSky export',
                  early_state['graphReady']>0 and not early_state['exported'] and not early_state['legacy'] and not early_state['hud'],early_state)
            sky_ok=b.ev("!!(CLSky&&CLSky.enabled())")
            check('released sky shell initializes and owns startup',early and sky_ok,b.ev("({enabled:CLSky&&CLSky.enabled(),legacy:CLAtlasPreview&&CLAtlasPreview.active(),boot:__shellRegression.bootOrder})"))
            setup=b.ev("(function(){var last=CLApp.graph().events.length-1;return {last:last,opened:CLSky.seekEventAt(last),state:CLSky.playerState()};})()")
            panel_ready=b.until("!!(CLSky.playerState().panel && document.querySelector('#skyStoryPanel [data-story=previous]') && !document.querySelector('#skyStoryPanel [data-story=previous]').disabled)",5,.025)
            before_event=b.ev("CLSky.playerState().eventIndex")
            target_event=before_event-1 if isinstance(before_event,int) else -1
            if panel_ready:
                b.ev("document.querySelector('#skyStoryPanel [data-story=previous]').focus()")
                b.key(' ')
            moved=panel_ready and b.until("CLSky.playerState().eventIndex==="+str(target_event),2,.025)
            after_space=b.ev("({state:CLSky.playerState(),focus:document.activeElement&&document.activeElement.getAttribute('data-story')})")
            check('native Space activates the previous event in the visible sky story panel',
                  bool(setup and setup['opened'] and panel_ready and moved and after_space['state']['eventIndex']==before_event-1),{'setup':setup,'before':before_event,'after':after_space})
            b.key('Escape')
            closed=b.until("!CLSky.playerState().panel && document.activeElement && document.activeElement.id==='skyPlay'",2,.025)
            check('native Escape closes the sky story panel and restores skyPlay focus',closed,
                  b.ev("({panel:CLSky.playerState().panel,focus:document.activeElement&&document.activeElement.id,legacy:CLAtlasPreview&&CLAtlasPreview.active()})"))
            key_trace=b.ev("__shellRegression.keyboard.filter(function(e){return e.key===' '||e.key==='Escape'})")
            seen_keys=[row['key'] for row in key_trace]
            check('native Space/Escape trace stays owned by sky with legacy inactive',
                  ' ' in seen_keys and 'Escape' in seen_keys and all((not row['legacy']) and row['skyEnabled'] for row in key_trace),key_trace)
            check('startup keyboard health',b.health()['ok'])
            for query,label,want_legacy in (
                    ('shell=atlas&data=data/sample-saga.json','explicit shell=atlas',True),
                    ('shell=atlas&sky=1&data=data/sample-saga.json','atlas overrides sky',True),
                    ('probe=1&data=data/sample-saga.json','probe-only legacy',True),
                    ('shell=sky&probe=1&data=data/sample-saga.json','shell=sky overrides probe',False),
                    ('data=data/sample-saga.json','default sky shell',False)):
                b.ev("if(window.__shellRegression)__shellRegression.navigationStale=true")
                expected=a.base.rstrip('/')+'/?'+query
                b.ws.call('Page.navigate',url=expected)
                landed=b.until("!!(window.__shellRegression && !__shellRegression.navigationStale && document.readyState==='complete' && location.href===%s)"%json.dumps(expected),15,.05)
                owner_ready="(CLAtlasPreview&&CLAtlasPreview.active())" if want_legacy else "(CLSky&&CLSky.enabled()&&CLSky.model())"
                owned=landed and b.until("!!(CLApp&&CLApp.graph&&CLApp.graph()&&"+owner_ready+")",15,.05)
                state=b.ev("({legacy:CLAtlasPreview&&CLAtlasPreview.active(),enabled:CLSky&&CLSky.enabled(),stale:__shellRegression&&__shellRegression.navigationStale,ready:document.readyState,href:location.href,graph:!!(CLApp&&CLApp.graph&&CLApp.graph()),loadError:window.CLLoadError||null,bootOrder:__shellRegression&&__shellRegression.bootOrder,at:performance.now()})")
                check(label+' follows shell URL priority',owned and bool(state['legacy'])==want_legacy,state)
                check(label+' health',b.health()['ok'])

        if a.only in ('all','loader'):
            early=b.navigate_with_shell_held(a.base)
            boot=b.ev('__shellRegression.bootOrder')
            dcl=boot.get('afterDomContentLoaded') if isinstance(boot,dict) else None
            check('controlled graph-ready-before-shell event is recovered after DOMContentLoaded',
                  bool(early and dcl and dcl.get('graphReadyBeforeShell') and dcl.get('model')),boot)
            ready=b.until('!!(CLSky&&CLSky.model&&CLSky.model()&&CLSkyDeconstruction&&CLSkyDeconstruction.ready&&CLSkyDeconstruction.ready())',10,.025)
            check('initial app graph eventually initializes the model and deconstruction reader',ready,b.ev('({model:!!(CLSky&&CLSky.model&&CLSky.model()),reader:!!(CLSkyDeconstruction&&CLSkyDeconstruction.ready&&CLSkyDeconstruction.ready()),boot:__shellRegression.bootOrder})'))
            report=b.ev(LOADER)
            rows=report.get('rows',[]) if isinstance(report,dict) else []
            for row in rows: check(row['name'],row['ok'],row.get('detail'))
            check('all loader race/native experiments returned the complete matrix',len(rows)==15,report)
            check('loader race/native health',b.health()['ok'])
            b.navigate(a.base)
            b.ev("(async function(){var g=await fetch('data/sample-saga.json').then(function(r){return r.json();});document.dispatchEvent(new CustomEvent('cl:graph-loading',{detail:{stage:'fetch',frac:.08,title:g.title}}));CLApp.internal().mount(g);return true;})()")
            armed=b.until("__shellRegression.read().loader.stage==='reveal' && !!__shellRegression.ctx.revealT",10,.02)
            check('native skip reaches a live reveal/skip window',armed)
            if armed:
                before=b.ev('__shellRegression.read()')
                point=b.ev("(function(){var e=document.querySelector('.skd-loader__skip.is-on');if(!e)throw Error('real skip text absent');var r=e.getBoundingClientRect();if(!r.width||!r.height)throw Error('skip text not laid out');return [r.left+r.width/2,r.top+r.height/2];})()")
                b.click(*point)
                skipped=b.until("__shellRegression.read().loader.stage==='done'",1,.02); gone=b.until("__shellRegression.read().hidden===true",3,.025); after=b.ev('__shellRegression.read()')
                check('native trusted click skips once and the real curtain leaves',skipped and gone and after['reveals']==before['reveals']+1,{'before':before,'after':after})
            check('native skip health',b.health()['ok'])
            b.ev("if(window.__shellRegression)__shellRegression.navigationStale=true")
            b.ws.call('Page.navigate', url=a.base.rstrip('/')+'/?sky=1&probe=1&data=data/cache/does-not-exist.json')
            missing_hidden=b.until("!!(window.__shellRegression && !__shellRegression.navigationStale && __shellRegression.ctx && window.CLLoadStage===null && (!document.querySelector('.skd-loader') || __shellRegression.read().hidden===true))",15,.05)
            check('native missing-file app path releases the real loading curtain',missing_hidden,b.ev('__shellRegression.read()'))
            check('native missing-file health',b.health()['ok'])

        if a.only in ('all','state'):
            for case in ('line','card'):
                b.navigate(a.base); b.ev(STATE); b.ev('CLSky.setPlot(true)'); time.sleep(3.0)
                choice=b.ev('__shellStateCase.%s()'%case)
                if case=='line': b.click(choice['x'],choice['y'])
                else: b.mouse('mouseMoved',choice['x'],choice['y'])
                entered=b.until("__shellStateCase.state().%s===%s"%('focused' if case=='line' else 'cardHover',json.dumps(choice['id'])),2,.03)
                before=b.ev('__shellStateCase.state()'); check(case+' actual pointer reaches the chosen real line/card',entered,{'choice':choice,'state':before})
                b.key('p'); closed=b.until('!CLSky.plot()',1); time.sleep(.12); after_close=b.ev('__shellStateCase.state()')
                check(case+' closing clears every shell/disc/deck selection',closed and after_close['focused'] is None and after_close['selected'] is None and after_close['cardHover'] is None and after_close['arcHover'] is None and after_close['deck']['open'] is None and after_close['deck']['hot'] is None,after_close)
                b.mouse('mouseMoved',8,892); b.key('p'); reopened=b.until('CLSky.plot()',1); time.sleep(1.6)
                b.ev('CLSky.seek(%d)'%choice['chapter']); time.sleep(.2); final=b.ev('__shellStateCase.state()')
                check(case+' reopening/seek really lights the current chapter cast',reopened and final['cursor']==choice['chapter'] and sorted(set(final['search'] or []))==sorted(set(choice['want'])),{'choice':choice,'state':final})
                check(case+' state health',b.health()['ok'])
    except Exception as e:
        check('runner completed every required real experiment',False,str(e))
    finally: b.close()
    passed=sum(ok for _,ok in results);ok=bool(results) and passed==len(results)
    print(('SHELL-LIFECYCLE OK' if ok else 'SHELL-LIFECYCLE FAIL')+' %d/%d'%(passed,len(results)))
    return 0 if ok else 1

if __name__=='__main__': sys.exit(main())
