#!/usr/bin/env python3
"""A real Chromium contract with WebGL disabled; deliberately no fake scene/shader API."""
import argparse
import base64
import json
import pathlib
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from headless import CH, WS

ROOT = pathlib.Path(__file__).resolve().parents[1]
INIT = """window.__fallbackProbe={errors:[],webglAttempts:0};
addEventListener('error',function(e){__fallbackProbe.errors.push(String(e.message))});
addEventListener('unhandledrejection',function(e){__fallbackProbe.errors.push(String(e.reason))});
var previousContext=HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext=function(kind){if(/webgl/i.test(kind)){__fallbackProbe.webglAttempts++;return null;}return previousContext.apply(this,arguments)};"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000/tests/atlas_fallback_harness.html?demo=1')
    parser.add_argument('--size', default='1100x800')
    parser.add_argument('--shots', help='Optional output directory for the three SVG stage screenshots')
    args = parser.parse_args()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    width, height = args.size.split('x')
    with tempfile.TemporaryDirectory(prefix='atlas-fallback-contract-') as profile:
        proc = subprocess.Popen([CH, '--headless=new', '--disable-webgl', '--disable-gpu',
                                 '--no-first-run', '--disable-background-networking',
                                 '--user-data-dir=' + profile, '--remote-debugging-port=' + str(port),
                                 '--window-size=' + width + ',' + height, 'about:blank'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
            ws.call('Page.addScriptToEvaluateOnNewDocument', source=INIT)
            ws.call('Emulation.setDeviceMetricsOverride', width=int(width), height=int(height), deviceScaleFactor=1, mobile=int(width) < 600)
            ws.call('Page.navigate', url=args.url)
            for _ in range(160):
                ready = ws.call('Runtime.evaluate', expression='window.CLAtlasFallback && CLAtlasFallback.stats().events===81', returnByValue=True)
                if ready.get('result', {}).get('value'):
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError('2D fallback did not load its explicit fixture')
            if args.shots:
                output = pathlib.Path(args.shots)
                output.mkdir(parents=True, exist_ok=True)
                for view in ('annulus', 'gem', 'domains'):
                    script = 'CLAtlasFallback.setView(%s);' % json.dumps(view)
                    if view == 'domains':
                        script += "document.querySelector('.afb-tools button').click();"
                    ws.call('Runtime.evaluate', expression=script)
                    shot = ws.call('Page.captureScreenshot', format='png')
                    (output / (view + '.png')).write_bytes(base64.b64decode(shot['data']))
                ws.call('Runtime.evaluate', expression="CLAtlasFallback.setView('annulus')")
            result = ws.call('Runtime.evaluate', expression=(ROOT / 'tests/atlas_fallback_browser.js').read_text(), awaitPromise=True, returnByValue=True)
            if 'exceptionDetails' in result:
                raise RuntimeError(json.dumps(result['exceptionDetails'], ensure_ascii=False))
            report = result['result']['value']; print(json.dumps(report, ensure_ascii=False))
            print('ATLAS-FALLBACK-BROWSER OK · %d contracts · WebGL disabled' % report['checks'])
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
    sys.exit(main())
