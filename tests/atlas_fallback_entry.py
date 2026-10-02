#!/usr/bin/env python3
"""Main entry proof: explicit 2D and caught WebGL failure, desktop and touch viewport."""
import argparse
import json
import pathlib
import socket
import subprocess
import tempfile
import time
import urllib.request

from headless import CH, WS
from atlas_fallback_browser import INIT

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000/')
    args = parser.parse_args()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    report = []
    with tempfile.TemporaryDirectory(prefix='atlas-fallback-entry-') as profile:
        proc = subprocess.Popen([CH, '--headless=new', '--disable-webgl', '--disable-gpu',
                                 '--no-first-run', '--disable-background-networking',
                                 '--user-data-dir=' + profile, '--remote-debugging-port=' + str(port),
                                 '--window-size=1440,900', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws = None
        try:
            for _ in range(100):
                try:
                    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=1).read())
                    break
                except OSError:
                    time.sleep(0.1)
            ws = WS(next(t['webSocketDebuggerUrl'] for t in tabs if t['type'] == 'page'), timeout=30)
            ws.call('Page.enable'); ws.call('Runtime.enable')
            ws.call('Page.addScriptToEvaluateOnNewDocument', source=INIT + '\nwindow.__fallbackMainEntry=true;')
            for mode in ('explicit', 'caught-error'):
                for width, height in ((1440, 900), (390, 844)):
                    ws.call('Emulation.setDeviceMetricsOverride', width=width, height=height, deviceScaleFactor=1, mobile=width < 600)
                    ws.call('Emulation.setTouchEmulationEnabled', enabled=width < 600, maxTouchPoints=1)
                    query = '?data=data/sample-saga.json' + ('&renderer=2d' if mode == 'explicit' else '')
                    ws.call('Page.navigate', url=args.url.rstrip('/') + '/' + query)
                    for _ in range(200):
                        readiness = ws.call('Runtime.evaluate', expression='window.CLAtlasFallback && CLAtlasFallback.stats().events===81', returnByValue=True)
                        if readiness.get('result', {}).get('value'):
                            break
                        time.sleep(0.1)
                    else:
                        state = ws.call('Runtime.evaluate', expression='JSON.stringify({probe:window.__fallbackProbe,fallback:window.CLAtlasFallback&&CLAtlasFallback.stats()})', returnByValue=True)
                        raise RuntimeError('%s %dx%d did not enter fallback: %s' % (mode, width, height, state))
                    # Hit the actual visible controls through CDP input, not a synthetic click.
                    for view in ('gem', 'annulus'):
                        box = ws.call('Runtime.evaluate', expression="(function(){var r=document.querySelector('.afb-nav [data-view=%s]').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()" % view, returnByValue=True)['result']['value']
                        if width < 600:
                            ws.call('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=1)
                            ws.call('Input.dispatchTouchEvent', type='touchStart', touchPoints=[box])
                            ws.call('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])
                        else:
                            ws.call('Input.dispatchMouseEvent', type='mousePressed', x=box['x'], y=box['y'], button='left', clickCount=1)
                            ws.call('Input.dispatchMouseEvent', type='mouseReleased', x=box['x'], y=box['y'], button='left', clickCount=1)
                        for _ in range(20):
                            current = ws.call('Runtime.evaluate', expression='CLAtlasFallback.stats().view', returnByValue=True)['result']['value']
                            if current == view:
                                break
                            time.sleep(0.05)
                        assert current == view, 'real pointer could not select ' + view
                    result = ws.call('Runtime.evaluate', expression=(ROOT / 'tests/atlas_fallback_browser.js').read_text(), awaitPromise=True, returnByValue=True)
                    if 'exceptionDetails' in result:
                        raise RuntimeError('%s %dx%d: %s' % (mode, width, height, json.dumps(result['exceptionDetails'], ensure_ascii=False)))
                    value = result['result']['value']
                    assert value['webgl'] == 0 if mode == 'explicit' else value['webgl'] > 0, 'entry path did not match intended WebGL lifecycle'
                    report.append({'mode': mode, 'size': [width, height], 'checks': value['checks'], 'realPointer': 'touch' if width < 600 else 'mouse', 'expectedGLAttempts': value['webgl'], 'ok': value['ok']})
            print(json.dumps(report, ensure_ascii=False))
            print('ATLAS-FALLBACK-ENTRY OK · %d contracts · 4 main-entry cases' % sum(r['checks'] for r in report))
            return 0
        finally:
            if ws:
                try:
                    ws.call('Browser.close')
                except (OSError, IOError):
                    pass
                ws.s.close()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.terminate(); proc.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
