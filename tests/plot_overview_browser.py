#!/usr/bin/env python3
"""Minimal owned-CDP runtime contract for plot HUD 390/1440 reader lifecycle."""
import json, os, signal, subprocess, sys, tempfile, time, urllib.request, shutil
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); sys.path.insert(0,HERE)
import headless
headless.reap_orphans=lambda:None
def run(size):
    w,h=map(int,size.split('x')); ud=tempfile.mkdtemp(prefix='plot-overview-')
    p=subprocess.Popen([headless.CH,'--headless=new','--use-angle=swiftshader','--window-size=%sx%s'%(w,h),'--user-data-dir='+ud,'--remote-debugging-port=0','about:blank'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    ws=None
    try:
      for _ in range(120):
        try:
          port=int(open(os.path.join(ud,'DevToolsActivePort')).read().splitlines()[0]); tabs=json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list'%port).read()); break
        except Exception: time.sleep(.1)
      ws=headless.WS([x for x in tabs if x.get('type')=='page'][0]['webSocketDebuggerUrl'],timeout=20); ws.call('Runtime.enable'); ws.call('Page.enable'); ws.call('Emulation.setDeviceMetricsOverride',width=w,height=h,deviceScaleFactor=1,mobile=False); ws.call('Page.navigate',url='http://127.0.0.1:8000/?demo=1&probe=1&pump=1')
      for _ in range(120):
        q=ws.call('Runtime.evaluate',expression='!!(window.CLPlotHud&&document.body)',returnByValue=True).get('result',{}).get('value')
        if q: break
        time.sleep(.25)
      fixture=open(os.path.join(ROOT,'tests/fixtures/plot-hud-synth.js'),encoding='utf-8').read()
      ws.call('Runtime.evaluate',expression=fixture,returnByValue=True)
      expr="""(function(){var H=window.CLPlotHud;if(!H)return {ok:false,why:'hud'};var t=H.__synth();H.setTree(t);H.open();var b=document.querySelector('.cp-read-line');if(!b)return {ok:false,why:'reader button'};b.click();var r=document.querySelector('.cp-reader'),back=r&&r.querySelector('.cp-reader-back'),a=document.activeElement===back,rw=r&&r.getBoundingClientRect().width,rr=r&&r.getBoundingClientRect().right;H.setTree(null);var cleared=!(r&&r.textContent);return {ok:true,readerWidth:rw,readerRight:rr,viewport:innerWidth,focusBack:a,cleared:cleared,scroll:document.body.scrollWidth<=innerWidth+1};})()"""
      v=ws.call('Runtime.evaluate',expression=expr,returnByValue=True).get('result',{}).get('value') or {}; return v
    finally:
      try:
        if ws: ws.call('Browser.close')
      except Exception: pass
      if p.poll() is None: os.killpg(p.pid,signal.SIGTERM)
      shutil.rmtree(ud,ignore_errors=True)
def main():
    out={}; fail=[]
    for s in ('390x844','1440x900'):
      try: out[s]=run(s)
      except Exception as e: out[s]={'ok':False,'error':str(e)}
      if not out[s].get('ok') or not out[s].get('cleared') or not out[s].get('focusBack') or out[s].get('readerRight',0)>out[s].get('viewport',0)+1: fail.append(s)
    print('PLOT_OVERVIEW_BROWSER %s · %s'%(('OK' if not fail else 'FAIL'),json.dumps(out,ensure_ascii=False))); return 0 if not fail else 1
if __name__=='__main__': sys.exit(main())
