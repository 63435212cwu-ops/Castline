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
ROOT = Path(os.environ.get('CL_PROJECT_ROOT', '/Users/carmen/Desktop/星系'))
sys.path.insert(0, str(ROOT / 'tests'))
import headless

BOOT = "!!(window.__shellRegression && !__shellRegression.navigationStale && __shellRegression.ctx && __shellRegression.ctx.loader && window.CLSky && CLSky.model() && window.CLSkyDeep && CLSkyDeep.stats().stars && CLSkyDeep.stats().stars.ignite>.99 && !Array.prototype.some.call(document.querySelectorAll('.skd-loader'), function(e){return !e.hidden;}))"
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
        self.ws.call('Emulation.setDeviceMetricsOverride', width=1440, height=900, deviceScaleFactor=1, mobile=False)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=INIT)
    def ev(self, expression):
        r=self.ws.call('Runtime.evaluate', expression=expression, returnByValue=True, awaitPromise=True)
        if r.get('exceptionDetails'): raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:1200])
        return r.get('result',{}).get('value')
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
    def mouse(self, kind, x, y, down=False):
        self.ws.call('Input.dispatchMouseEvent', type=kind, x=x, y=y, button='left' if down or kind!='mouseMoved' else 'none', buttons=1 if down else 0, clickCount=1 if kind in ('mousePressed','mouseReleased') else 0)
    def click(self, x, y):
        self.mouse('mouseMoved',x,y); self.mouse('mousePressed',x,y,True); self.mouse('mouseReleased',x,y)
    def key(self, key='p'):
        for kind in ('keyDown','keyUp'):
            self.ws.call('Input.dispatchKeyEvent', type=kind, key=key, code='KeyP' if key=='p' else key, windowsVirtualKeyCode=80 if key=='p' else 13)
    def close(self):
        try:
            if self.ws: self.ws.call('Browser.close')
        except Exception: pass
        try:
            if self.proc and self.proc.poll() is None: os.killpg(self.proc.pid,signal.SIGTERM)
        except Exception: pass
        shutil.rmtree(self.profile,ignore_errors=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--base',default='http://127.0.0.1:8765'); ap.add_argument('--only',choices=('all','loader','state'),default='all'); ap.add_argument('--self-test',action='store_true'); a=ap.parse_args()
    if a.self_test:
        for f in ['sky_shell_lifecycle_init.js','sky_shell_lifecycle_loader.js','sky_shell_lifecycle_state.js']:
            subprocess.run(['/Users/carmen/.workbuddy/binaries/node/versions/22.22.2-3/bin/node','--check',str(HERE/f)],check=True)
        compile(Path(__file__).read_text(),str(__file__),'exec')
        print('SHELL-LIFECYCLE source smoke OK; no browser/GPU started'); return 0
    results=[]
    def check(name,ok,detail=None):
        results.append((name,bool(ok))); print(('PASS ' if ok else 'FAIL ')+name+('' if ok else ' '+json.dumps(detail,ensure_ascii=False)[:1400]),flush=True)
    b=Browser()
    try:
        b.start()
        if a.only in ('all','loader'):
            b.navigate(a.base); report=b.ev(LOADER)
            rows=report.get('rows',[]) if isinstance(report,dict) else []
            for row in rows: check(row['name'],row['ok'],row.get('detail'))
            check('all loader race/native experiments returned the complete matrix',len(rows)==15,report)
            check('loader race/native health',headless.post_health(b.ws,[])==0)
            # Native skip: arm actual DOM, then click the real skip text with trusted input.
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
            check('native skip health',headless.post_health(b.ws,[])==0)
            b.ev("if(window.__shellRegression)__shellRegression.navigationStale=true")
            b.ws.call('Page.navigate', url=a.base.rstrip('/')+'/?sky=1&probe=1&data=data/cache/does-not-exist.json')
            missing_hidden=b.until("!!(window.__shellRegression && !__shellRegression.navigationStale && __shellRegression.ctx && window.CLLoadStage===null && (!document.querySelector('.skd-loader') || __shellRegression.read().hidden===true))",15,.05)
            check('native missing-file app path releases the real loading curtain',missing_hidden,b.ev('__shellRegression.read()'))
            check('native missing-file health',headless.post_health(b.ws,[])==0)

        if a.only in ('all','state'):
            for case in ('line','card'):
                b.navigate(a.base); b.ev(STATE); b.ev('CLSky.setPlot(true)'); time.sleep(3.0)
                choice=b.ev('__shellStateCase.%s()'%case)
                if case=='line': b.click(choice['x'],choice['y'])
                else: b.mouse('mouseMoved',choice['x'],choice['y'])
                entered=b.until("__shellStateCase.state().%s===%s"%('focused' if case=='line' else 'cardHover',json.dumps(choice['id'])),2,.03)
                before=b.ev('__shellStateCase.state()'); check(case+' actual pointer reaches the chosen real line/card',entered,{'choice':choice,'state':before})
                # Keep pointer over the card while P hides it; its leave callback sees plot=false.
                b.key('p'); closed=b.until('!CLSky.plot()',1); time.sleep(.12); after_close=b.ev('__shellStateCase.state()')
                check(case+' closing clears every shell/disc/deck selection',closed and after_close['focused'] is None and after_close['selected'] is None and after_close['cardHover'] is None and after_close['arcHover'] is None and after_close['deck']['open'] is None and after_close['deck']['hot'] is None,after_close)
                b.mouse('mouseMoved',8,892); b.key('p'); reopened=b.until('CLSky.plot()',1); time.sleep(1.6)
                b.ev('CLSky.seek(%d)'%choice['chapter']); time.sleep(.2); final=b.ev('__shellStateCase.state()')
                check(case+' reopening/seek really lights the current chapter cast',reopened and final['cursor']==choice['chapter'] and sorted(set(final['search'] or []))==sorted(set(choice['want'])),{'choice':choice,'state':final})
                check(case+' state health',headless.post_health(b.ws,[])==0)
    except Exception as e:
        check('runner completed every required real experiment',False,str(e))
    finally: b.close()
    passed=sum(ok for _,ok in results);ok=bool(results) and passed==len(results)
    print(('SHELL-LIFECYCLE OK' if ok else 'SHELL-LIFECYCLE FAIL')+' %d/%d'%(passed,len(results)))
    return 0 if ok else 1

if __name__=='__main__': sys.exit(main())
