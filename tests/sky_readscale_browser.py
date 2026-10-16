#!/usr/bin/env python3
"""CDP reading font-scale journey: three real button steps take effect in the
same task with no horizontal scroll, the step persists across reload, reset
returns to 1.0, corruption self-heals, and the extreme steps hold layout in a
four-cell viewport matrix (390x844 and 1440x900 at 1.4x and 0.85x) with the
story/decon panels fitting, sticky headers keeping close exposed and the scrub
still usable. Runs in the serial GPU slot (CL_GPU=1) against a real reviewed
work; the castline.readscale key lives only in the test browser profile."""
import argparse, base64, json, os, time, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner


def main():
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    a = argparse.ArgumentParser()
    a.add_argument('--base', default='http://127.0.0.1:8156')
    a.add_argument('--out', default=str(Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'sky-readscale'))
    args = a.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    r = Wave2AuditRunner(width=1440, height=900, dpr=1); checks = []

    def ev(expr, wait=False):
        value = r.eval(expr, await_promise=wait)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(str(value)[:400])
        return value

    def wait(expr, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            if ev(expr):
                return True
            time.sleep(.3)
        raise RuntimeError('wait timeout: ' + expr[:110])

    def check(name, expr):
        value = ev(expr); ok = value is True
        checks.append({'name': name, 'ok': ok, 'actual': value})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    def shot(name):
        (out / (name + '.png')).write_bytes(base64.b64decode(r.ws.call('Page.captureScreenshot', format='png')['data']))

    def size(w, h):
        r.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=1, mobile=False)
        time.sleep(.8)

    def sweep():
        ev("(function(){try{localStorage.removeItem('castline.readscale');}catch(e){}})()")

    def ready():
        wait('!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))', 90)
        time.sleep(3)

    def story():
        ev('CLSkyDeconstruction&&CLSkyDeconstruction.close();CLSky.setPlot(true);CLSky.seekEventAt(178)')
        time.sleep(1.2)

    PANEL_FIT = ("(()=>{const e=document.querySelector('%s');if(!e||e.hidden)return false;"
                 "const r=e.getBoundingClientRect();return r.x>=-1&&r.y>=-1&&r.right<=innerWidth+1&&"
                 "r.bottom<=innerHeight+1&&r.width>0&&r.height>0&&e.scrollWidth<=e.clientWidth+1})()")
    NO_HSCROLL = "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"
    CLOSE_EXPOSED = ("(()=>{const e=document.querySelector('%s');if(!e)return false;"
                     "const r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);"
                     "return r.height>=%d&&h&&(e===h||e.contains(h))})()")
    CLOSE_36 = CLOSE_EXPOSED % ('%s', 28)
    CLOSE_44 = CLOSE_EXPOSED % ('%s', 38)

    try:
        r.start()
        r.navigate(args.base + '/')
        wait('window.CLSkyChrome&&CLSkyChrome.home()==="home"&&CLSkyChrome.recent().length>=1', 60)
        A = ev('CLSkyChrome.recent()[0].key')
        r.navigate(args.base + '/?sky=1&data=data/cache/' + A + '.json')
        sweep()
        ready()
        check('readscale module ships with the shell and sees working storage',
              '!!window.CLSkyReadScale&&CLSkyReadScale.stats().storage===true&&CLSkyReadScale.current()===1')

        story()
        check('player bar exposes the three-button group at 44px with Chinese labels and current step',
              '(()=>{var w=document.querySelector("#skyPlayer .cl-rs");if(!w)return false;'
              'var d=document.getElementById("clRsDown"),n=document.getElementById("clRsReset"),u=document.getElementById("clRsUp");'
              'if(!d||!n||!u)return false;'
              'var ok=[d,n,u].every(function(b){var r=b.getBoundingClientRect();return r.height>=44&&r.width>=44;});'
              'return ok&&d.getAttribute("aria-label").includes("当前 100%")&&n.getAttribute("aria-label").includes("100%")'
              '&&u.getAttribute("aria-label").includes("当前 100%")&&n.textContent==="100%";})()')
        check('story panel prose uses the base token before scaling and body carries scale 1',
              '(()=>{var p=document.querySelector("#skyStoryPanel .ssp-body p");if(!p)return false;'
              'window.__rsBasePx=parseFloat(getComputedStyle(p).fontSize);'
              'return __rsBasePx>10&&document.body.style.getPropertyValue("--cl-reading-scale")==="1";})()')
        check('reading group stays reachable with the story panel open',
              '(()=>{var b=document.getElementById("clRsUp");var r=b.getBoundingClientRect();'
              'return r.x>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1;})()')
        ev('window.__rsChromeBase=(()=>{var h=document.querySelector("#skyStoryPanel .ssp-head h2"),'
           't=document.querySelector("#skyStoryPanel .ssp-actions button");'
           'return parseFloat(getComputedStyle(h).fontSize)+"/"+parseFloat(getComputedStyle(t).fontSize);})()')

        ev('document.getElementById("clRsUp").click()')
        check('A+ takes effect immediately: body var, prose px x1.15, storage, live announcement',
              '(()=>{var p=document.querySelector("#skyStoryPanel .ssp-body p");'
              'var px=parseFloat(getComputedStyle(p).fontSize);'
              'return CLSkyReadScale.current()===1.15&&Math.abs(px-__rsBasePx*1.15)<1.1'
              '&&document.body.style.getPropertyValue("--cl-reading-scale")==="1.15"'
              '&&localStorage.getItem("castline.readscale")==="1.15"'
              '&&document.getElementById("clRsLive").textContent==="阅读字号 115%";})()')
        check('no horizontal scroll after the first step up', NO_HSCROLL)
        ev('document.getElementById("clRsUp").click()')
        check('second step lands on 130% and the reset button shows it', 
              'CLSkyReadScale.current()===1.3&&document.getElementById("clRsReset").textContent==="130%"')
        ev('document.getElementById("clRsUp").click()')
        check('third step reaches the 140% top step and disables A+',
              '(()=>{var u=document.getElementById("clRsUp");return CLSkyReadScale.current()===1.4&&u.disabled===true'
              '&&u.getAttribute("aria-label").includes("已是最大档");})()')
        check('story panel keeps its width contract at 140% on desktop',
              PANEL_FIT % '#skyStoryPanel')
        ev('window.__rsChrome1=(()=>{var h=document.querySelector("#skyStoryPanel .ssp-head h2"),'
           't=document.querySelector("#skyStoryPanel .ssp-actions button");'
           'return parseFloat(getComputedStyle(h).fontSize)+"/"+parseFloat(getComputedStyle(t).fontSize);})()')
        check('non-reading text (panel head, action buttons) is byte-identical across 1.0 vs 1.4',
              '__rsChromeBase===__rsChrome1')

        ev('document.getElementById("clRsReset").click()')
        check('reset returns to 100% with the baseline pixel size stored',
              '(()=>{var p=document.querySelector("#skyStoryPanel .ssp-body p");'
              'return CLSkyReadScale.current()===1'
              '&&Math.abs(parseFloat(getComputedStyle(p).fontSize)-__rsBasePx)<0.6'
              '&&localStorage.getItem("castline.readscale")==="1"&&!document.getElementById("clRsUp").disabled;})()')
        ev('document.getElementById("clRsDown").click()')
        check('A- reaches the 85% floor step and disables A-',
              '(()=>{var d=document.getElementById("clRsDown");return CLSkyReadScale.current()===0.85&&d.disabled===true'
              '&&d.getAttribute("aria-label").includes("已是最小档");})()')
        check('smaller prose stays readable above the lint floor at 85%',
              '(()=>{var p=document.querySelector("#skyStoryPanel .ssp-body p");'
              'var px=parseFloat(getComputedStyle(p).fontSize);return px>=10&&px<__rsBasePx;})()')

        ev('document.getElementById("clRsUp").click();document.getElementById("clRsUp").click()')
        check('climbed back to 115% before the reload', 'CLSkyReadScale.current()===1.15')
        r.navigate(args.base + '/?sky=1&data=data/cache/' + A + '.json')
        ready()
        check('the stored step survives the reload and repaints prose at 115%',
              '(()=>{if(CLSkyReadScale.current()!==1.15)return false;'
              'return document.body.style.getPropertyValue("--cl-reading-scale")==="1.15"'
              '&&document.getElementById("clRsReset").textContent==="115%"'
              '&&getComputedStyle(document.body).getPropertyValue("--cl-reading-scale")==="1.15";})()')
        story()
        ev('window.__rs115px=parseFloat(getComputedStyle(document.querySelector("#skyStoryPanel .ssp-body p")).fontSize);'
           'CLSkyReadScale.set(1)')
        check('reloaded 115% prose derives exactly from this page\'s 100% base',
              '(()=>{var p=document.querySelector("#skyStoryPanel .ssp-body p");'
              'return Math.abs(__rs115px-parseFloat(getComputedStyle(p).fontSize)*1.15)<1.1;})()')

        ev('localStorage.setItem("castline.readscale","broken-json{not-a-number")')
        r.navigate(args.base + '/?sky=1&data=data/cache/' + A + '.json')
        ready()
        check('corrupt key heals to 100%, removes the bad key and counts the heal',
              'CLSkyReadScale.current()===1&&!localStorage.getItem("castline.readscale")'
              '&&CLSkyReadScale.stats().selfHeals>=1&&document.getElementById("clRsReset").textContent==="100%"')

        def matrix_cell(w, h, scale, tag):
            size(w, h)
            close_tpl = CLOSE_44 if w < 900 else CLOSE_36
            ev('CLSkyReadScale.reset()')
            ev('CLSkyReadScale.set(' + str(scale) + ')')
            check(tag + ' scale applied at the extreme step', 'CLSkyReadScale.current()===' + str(scale))
            story()
            check(tag + ' story panel fits the viewport without horizontal scroll', PANEL_FIT % '#skyStoryPanel')
            check(tag + ' document has no horizontal scroll', NO_HSCROLL)
            check(tag + ' story close stays exposed', close_tpl % '#skyStoryPanel [data-story=close]')
            ev('(()=>{const p=document.getElementById("skyStoryPanel");p.scrollTop=p.scrollHeight;'
               'const b=document.querySelector("#skyStoryPanel .ssp-body");if(b)b.scrollTop=b.scrollHeight;})()')
            check(tag + ' sticky close survives scrolling to the end',
                  close_tpl % '#skyStoryPanel [data-story=close]')
            check(tag + ' scrub and scale buttons remain visible controls',
                  '(()=>{function vis(s){const e=document.querySelector(s);if(!e)return false;'
                  'const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.y<innerHeight'
                  '&&r.right>0&&r.x<innerWidth;}'
                  'return vis("#skyStoryScrub")&&vis("#clRsDown")&&vis("#clRsUp")&&vis("#clRsReset");})()')
            ev('CLSkyDeconstruction.open();CLSkyDeconstruction.setMode("evidence")')
            time.sleep(.8)
            check(tag + ' deconstruction evidence tab fits the viewport', PANEL_FIT % '#skyDeconPanel')
            check(tag + ' deconstruction close stays exposed', close_tpl % '#skyDeconPanel .sd-close')
            check(tag + ' evidence body actually carries the scaled token',
                  '(()=>{var b=document.querySelector("#skyDeconPanel .sd-scroll");if(!b)return false;'
                  'var v=getComputedStyle(b).getPropertyValue("--cl-reading-scale");'
                  'return Math.abs(parseFloat(v)-' + str(scale) + ')<0.01;})()')
            ev('CLSkyDeconstruction.close()')

        matrix_cell(390, 844, 1.4, '390x844@140%')
        shot('01-narrow-140')
        matrix_cell(390, 844, 0.85, '390x844@85%')
        matrix_cell(1440, 900, 1.4, '1440x900@140%')
        shot('02-desktop-140')
        matrix_cell(1440, 900, 0.85, '1440x900@85%')
        size(1440, 900)

        ev('CLSkyReadScale.set(1.4)')
        story()
        rect = ev('(()=>{const e=document.getElementById("skyStoryScrub");const r=e.getBoundingClientRect();'
                  'return {x:r.x,y:r.y+r.height/2};})()')
        before = ev('CLSky.playerState().eventIndex')
        x0 = rect['x'] + 20; y0 = rect['y']; x1 = rect['x'] + 200
        r.ws.call('Input.dispatchMouseEvent', type='mousePressed', x=x0, y=y0, button='left', clickCount=1)
        r.ws.call('Input.dispatchMouseEvent', type='mouseMoved', x=x1, y=y0, button='left')
        r.ws.call('Input.dispatchMouseEvent', type='mouseReleased', x=x1, y=y0, button='left', clickCount=1)
        time.sleep(.8)
        after = ev('CLSky.playerState().eventIndex')
        ok = before != after
        checks.append({'name': 'scrub drag commits a new event at 140%', 'ok': ok, 'actual': [before, after]})
        print(('PASS ' if ok else 'FAIL ') + 'scrub drag commits a new event at 140%', flush=True)

        ev('CLSkyReadScale.reset()')
        sweep()
        check('whole journey ends with zero uncaught JavaScript or shader errors',
              '__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0')
        result = {'ok': all(x['ok'] for x in checks), 'checks': checks, 'modelsCalled': 0,
                  'work': A, 'matrix': [[390, 844, 1.4], [390, 844, 0.85], [1440, 900, 1.4], [1440, 900, 0.85]],
                  'boundary': 'headless Chromium at CSS viewport equivalence; not a claim of native device behavior.'}
        (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({'ok': result['ok'], 'checks': len(checks), 'out': str(out)}), flush=True)
        if not result['ok']:
            raise SystemExit(1)
    finally:
        r.close()


if __name__ == '__main__':
    raise SystemExit(main())
