#!/usr/bin/env python3
"""CDP journey for in-book work switching (CL_GPU=1 serial slot, own server on
8158, stopped after use). Real path: open the tools menu → 换作品 → real click on
another work → the switched-to stable state must be byte-identical to opening
that same work from scratch (?data= deep link, the same openHistory pipeline the
library uses). Reverse switch back. Then Fetch-domain failure injection:
target cache 404 → the honest list marks the work unavailable (listed, not
hidden) and on switch-attempt the CLBootErrors failure surface appears →
「返回原作品」 brings the original work back with state intact (probe byte-equal).
Resume/readscale state integrity across the round trip. No model calls."""
import argparse, base64, json, os, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import sky_chaos as chaos

SERVER_PORT = 8158


class GuardWS:
    """failure_modes 同款包装：响应等待途中读到的 CDP 事件进队列，requestPaused 不丢。"""
    def __init__(self, ws):
        self.ws = ws
        self.events = []
        self.unmatched_paused = []

    def call(self, method, **params):
        if method == 'Page.navigate' or method.startswith('Input.dispatch'):
            self.call('Page.bringToFront')
        ws = self.ws
        ws.id += 1
        my = ws.id
        ws.send({'id': my, 'method': method, 'params': params})
        while True:
            m = ws.recv()
            if m.get('id') == my:
                if 'error' in m:
                    raise RuntimeError(m['error'])
                return m.get('result', {})
            self.events.append(m)

    def ev(self, expr, wait=True):
        r = self.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=wait)
        if r.get('exceptionDetails'):
            raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:500])
        return r.get('result', {}).get('value')

    def until(self, expr, timeout=10, step=0.25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.ev(expr):
                    return True
            except Exception:
                pass
            time.sleep(step)
        return False

    def pump_paused(self, match, timeout=20, seen=(), method=None):
        """Take only the requested HTTP method; continue same-URL probes of other methods."""
        deadline = time.monotonic() + timeout
        import socket
        old = self.ws.s.gettimeout()
        try:
            while time.monotonic() < deadline:
                i = 0
                while i < len(self.events):
                    m = self.events[i]
                    if m.get('method') != 'Fetch.requestPaused':
                        i += 1
                        continue
                    params = m.get('params') or {}
                    req = params.get('request') or {}
                    rid = params.get('requestId')
                    if match not in str(req.get('url', '')) or rid in seen:
                        i += 1
                        continue
                    self.events.pop(i)
                    if method and req.get('method') != method:
                        detail = {'requestId': rid, 'method': req.get('method'),
                                  'url': req.get('url'), 'expectedMethod': method}
                        try:
                            self.call('Fetch.continueRequest', requestId=rid)
                            detail['continued'] = True
                        except Exception as exc:
                            detail['continueError'] = str(exc)[:160]
                        self.unmatched_paused.append(detail)
                        continue
                    return params
                self.ws.s.settimeout(min(0.5, max(0.05, deadline - time.monotonic())))
                try:
                    self.events.append(self.ws.recv())
                except socket.timeout:
                    pass
        finally:
            self.ws.s.settimeout(old)
        return None

    def wait_network_response(self, match, method, since=0, timeout=20, terminal_grace=0.75):
        """Wait for actual response headers; bodyless HEAD may abort after a valid response."""
        deadline = time.monotonic() + timeout
        cursor = since
        requests = {}
        observed = []
        pump_error = None
        while time.monotonic() < deadline:
            batch = self.events[cursor:]
            cursor = len(self.events)
            for event in batch:
                if event.get('method') not in ('Network.requestWillBeSent', 'Network.responseReceived',
                                               'Network.loadingFinished', 'Network.loadingFailed'):
                    continue
                p = event.get('params') or {}
                rid = p.get('requestId')
                kind = event.get('method')
                if kind == 'Network.requestWillBeSent':
                    req = p.get('request') or {}
                    url = str(req.get('url') or '')
                    if match not in url:
                        continue
                    detail = {'requestId': rid, 'method': req.get('method'), 'url': url,
                              'status': None, 'responseReceived': False, 'finished': False, 'error': None}
                    if req.get('method') == method:
                        requests[rid] = detail
                    else:
                        observed.append(detail)
                elif rid in requests and kind == 'Network.responseReceived':
                    response = p.get('response') or {}
                    requests[rid]['status'] = response.get('status')
                    requests[rid]['responseUrl'] = response.get('url')
                    requests[rid]['responseReceived'] = True
                    requests[rid]['responseAt'] = time.monotonic()
                elif rid in requests and kind == 'Network.loadingFinished':
                    requests[rid]['finished'] = True
                elif rid in requests and kind == 'Network.loadingFailed':
                    requests[rid]['error'] = p.get('errorText') or 'loading failed'
            for detail in requests.values():
                if detail['responseReceived'] and (detail['finished'] or detail['error'] or
                        time.monotonic() - detail['responseAt'] >= terminal_grace):
                    return detail
                if detail['error'] and not detail['responseReceived']:
                    return detail
            try:
                self.ev('true')
            except Exception as exc:
                pump_error = str(exc)[:160]
            time.sleep(0.05)
        return {'expectedMatch': match, 'expectedMethod': method,
                'requests': list(requests.values()), 'otherMethods': observed[-5:],
                'pumpError': pump_error, 'timeout': timeout}


def fulfill(g, paused, status, body_bytes, content_type='application/json'):
    g.call('Fetch.fulfillRequest', requestId=paused['requestId'], responseCode=status,
           responseHeaders=[{'name': 'content-type', 'value': content_type},
                            {'name': 'content-length', 'value': str(len(body_bytes))},
                            {'name': 'cache-control', 'value': 'no-store'},
                            {'name': 'x-content-type-options', 'value': 'nosniff'}],
           body=base64.b64encode(body_bytes).decode())


def probe_state_expr():
    return ("(()=>{var li=Array.prototype.slice.call(document.querySelectorAll('.sws-item'));"
            "return {n:li.length, down:document.querySelectorAll('.sws-item.is-down').length,"
            "ok:document.querySelectorAll('.sws-item:not(.is-down)').length};})()")


def work_b_probe_expr():
    return ("(()=>{var es=CLSkySwitcher.entries(),i=-1;"
            "es.forEach(function(e,j){if(e.key===__swB)i=j;});"
            "var e=i<0?null:es[i],b=i<0?null:document.querySelector('.sws-item[data-i=\"'+i+'\"]');"
            "return {entries:es.length,index:i,probe:e&&e.probe,button:!!b,"
            "down:!!(b&&b.classList.contains('is-down')),key:e&&e.key};})()")


def work_b_ready_expr():
    return ("(()=>{var s=" + work_b_probe_expr() + ";"
            "return s.index>=0&&s.key===__swB&&s.probe==='ok'&&s.button&&!s.down;})()")


def main():
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:%d' % SERVER_PORT)
    ap.add_argument('--out', default=str(Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'sky-switcher'))
    args = ap.parse_args()
    base = args.base.rstrip('/')
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(name, ok, detail=None):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:500]), flush=True)

    server = subprocess.Popen([sys.executable, str(ROOT / 'serve.py'), str(SERVER_PORT)],
                              cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    b = chaos.Browser(1440, 900)
    try:
        for _ in range(60):
            try:
                import urllib.request
                urllib.request.urlopen(base + '/api/health', timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        b.start()
        g = GuardWS(b.ws)

        g.call('Page.navigate', url=base + '/')
        ok = g.until('!!(window.CLSkyChrome && CLSkyChrome.home()==="home" && CLSkyChrome.recent().length >= 2)', 60)
        check('home lists at least two real works from /api/history', ok)
        A = g.ev('CLSkyChrome.recent()[0].key')
        B = g.ev('CLSkyChrome.recent()[1].key')
        __swa_key = A
        __swb_key = B
        titleA = g.ev('CLSkyChrome.recent()[0].title')
        titleB = g.ev('CLSkyChrome.recent()[1].title')
        MATCH_B = '/data/cache/%s.json' % B
        PATTERN_B = '*://*/data/cache/%s.json*' % B

        def open_clean(key, timeout=90):
            g.call('Page.navigate', url=base + '/?sky=1&data=data/cache/%s.json' % key)
            g.ev("(function(){try{Object.keys(localStorage).filter(function(k){return k.indexOf('castline.resume.')===0;}).forEach(function(k){localStorage.removeItem(k);});}catch(e){}})()")
            rdy = g.until('!!(window.CLApp && CLApp.graph() && CLSky.model() && document.querySelector("#loader.off"))', timeout)
            time.sleep(3.5)
            return rdy

        check('work B opens clean for the baseline', open_clean(B))
        g.ev('window.__swBaseB = JSON.stringify({key: CLApp.key(), probe: CLSkyResume.probe()})')
        g.ev('window.__swA = %s; window.__swB = %s' % (json.dumps(A), json.dumps(B)))
        check('baseline B probe captured with the default starting state',
              g.ev('(()=>{var p = JSON.parse(__swBaseB); return p.key === __swB && p.probe.plot === false && p.probe.cursor === null;})()'))
        baseB = g.ev('__swBaseB')

        def click_work(key):
            """真实点击面板里 data-key == key 的那一项（同名作品存在，按标题匹配会点错）。"""
            return g.ev('(()=>{var es = CLSkySwitcher.entries(); var i = -1; es.forEach(function(e, j){ if (e.key === %s) i = j; });'
                        'if (i < 0) return false; var b = document.querySelector(".sws-item[data-i=\\"" + i + "\\"]");'
                        'if (!b || b.classList.contains("is-down")) return false; b.click(); return true;})()' % json.dumps(key))

        def same_as(base_json):
            return g.ev('(()=>{var a = JSON.parse(%s); var b = {key: CLApp.key(), probe: CLSkyResume.probe()};'
                        'var ba = JSON.stringify(b.probe), aa = JSON.stringify(a.probe); var i = 0;'
                        'while (i < Math.max(ba.length, aa.length) && ba[i] === aa[i]) i++;'
                        'return {probe: ba === aa, keyMatch: b.key === a.key, diffAt: i,'
                        ' aSlice: ba.slice(Math.max(0, i - 40), i + 60), bSlice: aa.slice(Math.max(0, i - 40), i + 60)};})()' % json.dumps(base_json))

        check('work A opens clean', open_clean(A))
        g.ev('window.__swA = %s; window.__swB = %s; window.__swTA = %s; window.__swTB = %s'
              % (json.dumps(A), json.dumps(B), json.dumps(titleA), json.dumps(titleB)))
        check('resume records cleared; work A at its default starting state',
              g.ev('CLApp.key() === __swA && CLSky.state().plot === false && CLSky.state().cursor === null'))
        baseA = g.ev('JSON.stringify({key: CLApp.key(), probe: CLSkyResume.probe()})')
        g.ev('document.getElementById("skyTools").click()')
        check('tools menu opens and the 换作品 item sits in the 作品 group',
              g.ev('(()=>{var b = document.querySelector(".stm-item[data-for=skySwitch]");'
                   'if (!b) return false;'
                   'return window.CLSkyChrome.menuOpen() && !b.hidden && b.getAttribute("aria-disabled") === "false"'
                   ' && b.closest(".stm-group").getAttribute("data-group") === "work";})()'))
        g.ev('document.querySelector(".stm-item[data-for=skySwitch]").click()')
        ok = g.until('!!(document.getElementById("skySwitcher") && !document.getElementById("skySwitcher").hidden'
                     ' && document.querySelectorAll(".sws-item").length >= 2)', 15)
        check('the in-book panel lists every available work', ok and g.ev('document.querySelectorAll(".sws-item").length') >= 2,
              g.ev('(function(){var p=document.getElementById("skySwitcher"); return p ? p.innerText.slice(0,160) : null})()'))
        check('availability probe finishes without taking down any real work',
              g.until('(()=>{var b=document.querySelector(".sws-item");'
                      'return !!b && document.querySelectorAll(".sws-item.is-down").length === 0;})()', 15),
              g.ev(probe_state_expr()))
        check('current work marked aria-current and reads 当前',
              g.ev('(()=>{var c = document.querySelector(".sws-item[aria-current=\\"true\\"]");'
                   'if (!c) return false;'
                   'return c.classList.contains("is-current") && c.textContent.indexOf("当前") >= 0;})()'))
        check('menu item hidden on panel open path leaves the tools menu closed',
              g.ev('!CLSkyChrome.menuOpen()'))
        check('panel entries carry exact work keys (title-duplicates included) matching the home recent order',
              g.ev('(()=>{var es = CLSkySwitcher.entries(); var r = CLSkyChrome.recent();'
                   'var keys = es.map(function(e){return e.key;});'
                   'if (keys.length < 2) return false;'
                   'if (keys[0] !== r[0].key) return false;'
                   'return keys.indexOf(__swA) >= 0 && keys.indexOf(__swB) >= 0 && es.some(function(e){return e.current && e.key === __swA;});})()') is True)

        check('clicked the exact work B item in the panel', click_work(__swb_key) is True)
        ok = g.until('CLApp.key() === __swB && !!(CLSky.model()) && !!document.querySelector("#loader.off")', 90)
        check('switch click lands in work B through the real open path', ok)
        time.sleep(3.5)
        a_from_b = same_as(baseB)
        check('switched-to-B state is byte-identical to opening B from scratch', a_from_b and a_from_b.get('probe') and a_from_b.get('keyMatch'), a_from_b)
        check('switch lands at the default starting state (no auto-resume jump)',
              g.ev('CLSky.state().plot === false && CLSky.state().cursor === null'))
        check('a resume record present for B does not auto-jump either', g.ev('CLSkyResume.read(__swB)') is None or
              g.ev('CLSky.state().plot === false && CLSky.state().cursor === null'))

        g.ev('document.getElementById("skyTools").click()')
        g.until('!!document.querySelector(".stm-item[data-for=skySwitch]")', 10)
        g.ev('document.querySelector(".stm-item[data-for=skySwitch]").click()')
        g.until('!!(document.getElementById("skySwitcher") && !document.getElementById("skySwitcher").hidden && document.querySelectorAll(".sws-item").length >= 2)', 15)
        g.until('document.querySelectorAll(".sws-item.is-down").length === 0', 15)
        check('clicked the exact work A item in the panel', click_work(__swa_key) is True)
        ok = g.until('CLApp.key() === __swA && !!(CLSky.model()) && !!document.querySelector("#loader.off")', 90)
        check('reverse switch lands back in work A', ok)
        time.sleep(3.5)
        back = same_as(baseA)
        check('reverse-switched-to-A state is byte-identical to A baseline', back and back.get('probe') and back.get('keyMatch'), back)

        g.ev('CLSky.setPlot(true); CLSky.seekEventAt(2)')
        time.sleep(1.2)
        g.ev('CLSkyResume.flush()')
        check('reading state recorded under work A before the switch round trip',
              g.ev('(()=>{var r = CLSkyResume.read(__swA); return !!(r && r.view === "plot");})()'))
        g.ev('(()=>{var b = document.querySelector("#skyPlayer .cl-rs button:nth-child(3)");'
             'if (b) b.click();})()')
        scale_before = g.ev('getComputedStyle(document.body).getPropertyValue("--cl-reading-scale").trim()')
        check('reading font scale stored as the reader preference', bool(scale_before) and scale_before != '1')

        g.call('Fetch.enable', patterns=[{'urlPattern': PATTERN_B}])
        g.ev('document.getElementById("skyTools").click()')
        g.ev('document.querySelector(".stm-item[data-for=skySwitch]").click()')
        paused = g.pump_paused(MATCH_B, timeout=25, method='HEAD')
        head_request = (paused or {}).get('request') or {}
        check('availability probe HEAD for work B intercepted',
              bool(paused) and head_request.get('method') == 'HEAD'
              and MATCH_B in str(head_request.get('url', '')),
              {'requestId': (paused or {}).get('requestId'), 'method': head_request.get('method'),
               'url': head_request.get('url'), 'otherPaused': g.unmatched_paused[-5:]})
        if paused:
            fulfill(g, paused, 404, b'Not Found')
        ok = g.until('document.querySelectorAll(".sws-item.is-down").length === 1', 15)
        check('injected 404 marks exactly the missing work as unavailable — listed, not hidden',
              ok and g.ev('(()=>{var es = CLSkySwitcher.entries(); var idx = -1; es.forEach(function(e, j){ if (e.key === __swB) idx = j; });'
                          'var b = document.querySelector(".sws-item[data-i=\\"" + idx + "\\"]");'
                          'return !!b && b.classList.contains("is-down") && b.getAttribute("aria-disabled") === "true" &&'
                          ' b.textContent.indexOf("数据不可用") >= 0;})()') is True,
              g.ev('(function(){var b=document.querySelector(".sws-item.is-down"); return b ? b.innerText : null})()'))
        g.call('Fetch.disable')
        for m in list(g.events):
            if m.get('method') == 'Fetch.requestPaused':
                try:
                    g.call('Fetch.continueRequest', requestId=(m.get('params') or {}).get('requestId'))
                except Exception:
                    pass
        g.events = [m for m in g.events if m.get('method') != 'Fetch.requestPaused']
        g.ev('CLSkySwitcher.close(false)')

        preFailA = g.ev('JSON.stringify({key: CLApp.key(), probe: CLSkyResume.probe()})')
        g.call('Network.enable')
        network_cursor = len(g.events)
        g.ev('document.getElementById("skyTools").click()')
        g.ev('document.querySelector(".stm-item[data-for=skySwitch]").click()')
        reopened = g.until('!!(document.getElementById("skySwitcher") && !document.getElementById("skySwitcher").hidden'
                           ' && document.querySelectorAll(".sws-item").length >= 2 && ' + work_b_ready_expr() + ')', 20)
        check('switcher reopens with the exact work B entry ready after the availability 404 window',
              reopened, g.ev(work_b_probe_expr()))
        head_response = g.wait_network_response(MATCH_B, 'HEAD', since=network_cursor, timeout=20)
        head_ok = (head_response.get('method') == 'HEAD' and head_response.get('status') == 200
                   and head_response.get('responseReceived') is True)
        check('real availability HEAD for work B received HTTP 200 before GET injection',
              head_ok, head_response)
        target_ready = g.until(work_b_ready_expr(), 10)
        target_state = g.ev(work_b_probe_expr())
        check('work B target entry is present and available after its real HEAD 200',
              target_ready and target_state.get('key') == g.ev('__swB')
              and target_state.get('probe') == 'ok' and target_state.get('button')
              and not target_state.get('down'), target_state)
        g.call('Fetch.enable', patterns=[{'urlPattern': PATTERN_B}])
        check('clicked the exact work B item (switch attempt under injection)', click_work(__swb_key) is True)
        paused = g.pump_paused(MATCH_B, timeout=25, method='GET')
        get_request = (paused or {}).get('request') or {}
        check('switch GET for work B intercepted',
              bool(paused) and get_request.get('method') == 'GET'
              and MATCH_B in str(get_request.get('url', '')),
              {'requestId': (paused or {}).get('requestId'), 'method': get_request.get('method'),
               'url': get_request.get('url'), 'otherPaused': g.unmatched_paused[-5:]})
        if paused:
            fulfill(g, paused, 404, b'Not Found')
        ok = g.until('!!(document.getElementById("skySwitchFail") && !document.getElementById("skySwitchFail").hidden)', 15)
        check('CLBootErrors failure surface appears on the switch 404', ok)
        check('failure text names the missing file honestly (CLBootErrors http/404 wording)',
              g.ev('(()=>{var w = document.getElementById("skySwitchFailWhy");'
                   'return !!w && w.textContent.indexOf("找不到") >= 0;})()'))
        check('failure surface keeps the retryable technical detail expandable',
              g.ev('(()=>{var t = document.getElementById("skySwitchFailTech");'
                   'return !!t && !t.hidden && document.getElementById("skySwitchFailDetail").textContent.indexOf("http") >= 0;})()'))
        check('structured event carried the target key and status',
              g.ev('(()=>{var f = CLSkySwitcher.lastFail(); return !!f && f.to === __swB && f.from === __swA && f.kind === "http" && f.status === 404;})()'))
        g.call('Fetch.disable')
        for m in list(g.events):
            if m.get('method') == 'Fetch.requestPaused':
                try:
                    g.call('Fetch.continueRequest', requestId=(m.get('params') or {}).get('requestId'))
                except Exception:
                    pass
        g.events = [m for m in g.events if m.get('method') != 'Fetch.requestPaused']

        g.ev('document.getElementById("skySwitchFailBack").click()')
        ok = g.until('!!(document.getElementById("skySwitchFail") === null || document.getElementById("skySwitchFail").hidden)', 10)
        intact = same_as(preFailA)
        check('「返回原作品」dismisses to the original work with byte-identical state (fetch 404 never unmounted it)',
              ok and intact and intact.get('keyMatch') and intact.get('probe'), intact)
        check('resume record for A survived the failed switch',
              g.ev('(()=>{var r = CLSkyResume.read(__swA); return !!(r && r.view === "plot");})()'))
        check('reading font scale preference survived the failed switch',
              g.ev('getComputedStyle(document.body).getPropertyValue("--cl-reading-scale").trim() === %s' % json.dumps(scale_before)))

        g.call('Fetch.disable')
        retry_cursor = len(g.events)
        g.ev('document.getElementById("skyTools").click()')
        g.ev('document.querySelector(".stm-item[data-for=skySwitch]").click()')
        reopened = g.until('!!(document.getElementById("skySwitcher") && !document.getElementById("skySwitcher").hidden'
                           ' && document.querySelectorAll(".sws-item").length >= 2 && ' + work_b_ready_expr() + ')', 30)
        check('retry switcher reopens with the exact work B entry ready', reopened,
              g.ev(work_b_probe_expr()))
        retry_head = g.wait_network_response(MATCH_B, 'HEAD', since=retry_cursor, timeout=30)
        retry_head_ok = (retry_head.get('method') == 'HEAD' and retry_head.get('status') == 200
                         and retry_head.get('responseReceived') is True)
        check('retry availability HEAD for work B received HTTP 200', retry_head_ok, retry_head)
        retry_ready = g.until(work_b_ready_expr(), 10)
        retry_state = g.ev(work_b_probe_expr())
        check('retry target B entry remains present and available after real HEAD 200',
              retry_ready and retry_state.get('key') == g.ev('__swB')
              and retry_state.get('probe') == 'ok' and retry_state.get('button')
              and not retry_state.get('down'), retry_state)
        check('clicked the exact work B item after the fault window', click_work(__swb_key) is True)
        ok = g.until('CLApp.key() === __swB && !!(CLSky.model()) && !!document.querySelector("#loader.off")', 90)
        time.sleep(3.5)
        again = same_as(baseB)
        check('after the 404 window closes the same switch succeeds and matches the B baseline byte for byte',
              ok and again and again.get('probe'), again)
        check('work A resume record intact after the whole round trip',
              g.ev('(()=>{var r = CLSkyResume.read(__swA); return !!(r && r.view === "plot");})()'))
        check('every switch flow ends with zero uncaught JavaScript or shader errors',
              g.ev('__headlessHealth.jserr.length === 0 && __headlessHealth.jsrej.length === 0 && CLApp.scene().shaderErrors().length === 0'))

        result = {'ok': all(x['ok'] for x in checks), 'checks': checks, 'modelsCalled': 0,
                  'sourceFilesChanged': False, 'viewport': [1440, 900]}
        (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({'ok': result['ok'], 'checks': len(checks), 'out': str(out)}), flush=True)
        if not result['ok']:
            raise SystemExit(1)
    finally:
        b.close()
        server.terminate()
        try:
            server.wait(5)
        except Exception:
            server.kill()


if __name__ == '__main__':
    main()
