#!/usr/bin/env python3
"""Read-only real-book story-playback follow camera journey (CDP).

Drives the reviewed Xiyou graph through the public CLSky surface plus trusted
CDP input. Instruments scene flyTo (read-only wrapper) to prove the camera
actually moves with playback: per-event goals, bead visibility, toggle off
freeze, wheel-gesture interrupt, stop-restore, scrub one-shot alignment and
reduced-motion instant cuts.
"""
import argparse, base64, json, time, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner

def main():
    a = argparse.ArgumentParser(); a.add_argument('--base', default='http://127.0.0.1:8137')
    a.add_argument('--out', default=str(Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'follow-camera'))
    args = a.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    r = Wave2AuditRunner(width=1440, height=900, dpr=1)
    checks = []

    def ev(expr, wait=False):
        value = r.eval(expr, await_promise=wait)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(str(value) + ' :: ' + expr[:160])
        return value

    def check(name, expr):
        value = ev(expr)
        ok = value is True
        checks.append({'name': name, 'ok': ok, 'actual': value})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    def ready():
        end = time.time() + 90
        while time.time() < end:
            if ev('!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))'):
                break
            time.sleep(.3)
        else:
            raise RuntimeError('graph readiness timeout')
        time.sleep(4)

    def click(selector):
        point = ev('(()=>{var e=document.querySelector(' + json.dumps(selector) + ');if(!e)throw Error("missing target");var b=e.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2]})()')
        for typ in ['mouseMoved', 'mousePressed', 'mouseReleased']:
            r.ws.call('Input.dispatchMouseEvent', type=typ, x=point[0], y=point[1], button='left', clickCount=1)
        time.sleep(.2)

    def key(k, code, vk, text=None):
        payload = {'type': 'keyDown', 'key': k, 'code': code, 'windowsVirtualKeyCode': vk}
        if text is not None:
            payload.update(text=text, unmodifiedText=text)
        r.ws.call('Input.dispatchKeyEvent', **payload)
        r.ws.call('Input.dispatchKeyEvent', type='keyUp', key=k, code=code, windowsVirtualKeyCode=vk)
        time.sleep(.2)

    def shot(name):
        (out / (name + '.png')).write_bytes(base64.b64decode(r.ws.call('Page.captureScreenshot', format='png')['data']))

    def until_event(want_count, timeout=45):
        end = time.time() + timeout
        while time.time() < end:
            if ev('window.__followEvents.length') >= want_count:
                return True
            time.sleep(.5)
        return False

    try:
        r.start()
        r.navigate(args.base + '/?sky=1&data=data/cache/c84e8657afff87043c11ae57.json')
        ready()
        ev('CLSky.setPlot(true)')
        time.sleep(3)
        check('follow toggle is a 44px pressed-by-default accessible switch in the plot toolbar',
              '(()=>{var b=document.getElementById("skyFollow");if(!b)return false;var r=b.getBoundingClientRect();'
              'return r.width>=44&&r.height>=44&&b.getAttribute("aria-pressed")==="true"&&b.getAttribute("aria-label").length>0&&b.tagName==="BUTTON"})()')
        ev('''window.__fly=[];window.__followEvents=[];(function(){
          var S=CLApp.scene(),orig=S.flyTo;
          S.flyTo=function(p,t,d){__fly.push({p:[p.x,p.y,p.z],t:[t.x,t.y,t.z],d:d});return orig(p,t,d);};
          var last=CLSky.playerState().eventId;
          setInterval(function(){var s=CLSky.playerState();if(s.eventId&&s.eventId!==last){last=s.eventId;
            var pt=CLSky.disc().eventPoint(s.eventIndex);
            __followEvents.push({id:s.eventId,bead:pt?[pt.x,pt.y]:null,
              cam:{p:[CLApp.scene().camera.position.x,CLApp.scene().camera.position.y,CLApp.scene().camera.position.z],
                   t:[CLApp.scene().controls.target.x,CLApp.scene().controls.target.y,CLApp.scene().controls.target.z],
                   d:CLApp.scene().camera.position.distanceTo(CLApp.scene().controls.target)}});}},250);
        })()''')
        ev('''window.__startIdx=(function(){var d=CLSky.disc(),G=CLApp.graph(),found=-1;
          function dist2(i,j){var a=d.eventWorld(i),b=d.eventWorld(j);if(!a||!b)return 0;return Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z);}
          for(var i=0;i<G.events.length-2;i++){if(dist2(i,i+1)>3&&dist2(i+1,i+2)>3&&dist2(i,i+2)>3){found=i;break;}}
          return found;})()''')
        start = ev('window.__startIdx')
        if not (isinstance(start, int) and start >= 0):
            raise AssertionError('no distinct-bead event triple in this book')
        ev('CLSky.seekEventAt(window.__startIdx)')
        time.sleep(.4)
        check('a paused seek aligns the camera in exactly one flight', 'window.__fly.length===1')
        ev('window.__alignGoal=__fly[0];CLSky.seekEventAt(window.__startIdx)')
        time.sleep(.3)
        check('repeating the same seek is a no-op rather than a refly', 'window.__fly.length===1')
        click('#skySpeed'); click('#skySpeed')
        click('#skyPlay')
        if not until_event(3):
            raise AssertionError('playback never advanced three events: ' + json.dumps(ev('window.__followEvents')))
        ev('CLSky.stop()')
        debug_goals = ev('JSON.stringify(__followEvents.slice(0,4))')
        check('camera goal moves with every one of the first three playback events',
              '(()=>{var seen=__followEvents.slice(0,3).map(e=>e.cam);if(seen.length<3)return false;'
              'for(var i=1;i<seen.length;i++){var a=seen[i-1].t,b=seen[i].t;if(Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2])<1)return false;}return true})()')
        print('  sampled goals: ' + str(debug_goals), flush=True)
        check('camera distance from target genuinely adapts while following',
              '(()=>{var ds=__followEvents.slice(0,3).map(e=>e.cam.d);return ds.length>=3&&(Math.max.apply(null,ds)-Math.min.apply(null,ds))>1})()')
        check('every played event bead lands inside the viewport',
              '(()=>{return __followEvents.slice(0,3).every(function(e){return e.bead&&e.bead[0]>=0&&e.bead[0]<=innerWidth&&e.bead[1]>=0&&e.bead[1]<=innerHeight})})()')
        check('non-reduced follow flights tween rather than cut',
              '__fly.length>=3&&__fly.every(function(f){return f.d>0.4})')
        shot('01-follow-three-events')
        ev('CLSky.stop()')
        ev('window.__flyN=__fly.length')
        time.sleep(1.5)
        check('pause never adds a flight', 'window.__fly.length===window.__flyN&&!CLSky.state().playing')
        ev('window.__entry__=CLSky.playerState().follow.entry')
        click('#skyPlay')
        time.sleep(.3)
        ev('window.__flyN=__fly.length')
        key('Escape', 'Escape', 27)
        check('Escape stops playback and starts exactly one restore flight',
              '!CLSky.state().playing&&window.__fly.length===window.__flyN+1')
        time.sleep(1.2)
        check('the restored camera lands back on the memorized pre-follow pose',
              '(()=>{var e=window.__entry__;if(!e)return false;var S=CLApp.scene();'
              'function near(a,b){for(var i=0;i<3;i++)if(Math.abs(a[i]-b[i])>40)return false;return true;}'
              'return near([S.camera.position.x,S.camera.position.y,S.camera.position.z],e.p)'
              '&&near([S.controls.target.x,S.controls.target.y,S.controls.target.z],e.t)})()')
        shot('02-restore-entry-pose')
        click('#skyFollow')
        check('the toggle reflects its off state through aria-pressed',
              'document.getElementById("skyFollow").getAttribute("aria-pressed")==="false"&&!CLSky.playerState().follow.enabled')
        ev('window.__flyN=__fly.length;CLSky.seekEventAt(182)')
        time.sleep(.5)
        check('with follow off even explicit seeks leave the camera alone', 'window.__fly.length===window.__flyN')
        click('#skyPlay'); time.sleep(2)
        check('playback with the toggle off never retakes the camera', 'window.__fly.length===window.__flyN')
        ev('CLSky.stop()')
        click('#skyFollow')
        check('re-enabling reports through aria-pressed', 'document.getElementById("skyFollow").getAttribute("aria-pressed")==="true"')
        ev('window.__flyN=__fly.length;document.getElementById("skyStoryScrub").focus()')
        key('ArrowRight', 'ArrowRight', 39)
        check('a scrub keyboard commit aligns in exactly one flight', 'window.__fly.length===window.__flyN+1')
        time.sleep(1.2)
        check('no second flight tails the committed scrub seek', 'window.__fly.length===window.__flyN+1')
        click('#skyPlay')
        ev('window.__flyN=__fly.length')
        r.ws.call('Input.dispatchMouseEvent', type='mouseWheel', x=720, y=430, deltaX=0, deltaY=-220)
        time.sleep(.5)
        check('a real wheel gesture marks the interrupt but keeps the toggle on',
              'CLSky.playerState().follow.interrupted===true&&CLSky.playerState().follow.enabled===true')
        if not until_event(len(ev('window.__followEvents')) + 1, 30):
            raise AssertionError('playback stalled after wheel')
        ev('CLSky.stop()')
        check('after the wheel interrupt the follow camera never retakes the shot',
              'window.__fly.length===window.__flyN')
        click('#skyPlay')
        time.sleep(.8)
        check('replaying restores follow with a fresh alignment',
              'CLSky.playerState().follow.interrupted===false&&window.__fly.length>window.__flyN')
        ev('CLSky.stop()')
        r.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])
        time.sleep(.3)
        ev('window.__flyN=__fly.length;CLSky.seekEventAt(CLSky.playerState().eventIndex+7)')
        check('reduced-motion follow lands as an instant cut with no tween',
              'window.__fly.length===window.__flyN+1&&__fly[__fly.length-1].d<=0.01')
        r.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'no-preference'}])
        time.sleep(.3)
        check('real-book follow journey has no uncaught JavaScript, Promise, shader or frame-hook errors',
              '__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0&&CLApp.scene().core().perf().frameHooks.errors===0')
        result = {'ok': all(x['ok'] for x in checks), 'checks': checks,
                  'flights': ev('window.__fly.length'), 'eventsFollowed': ev('window.__followEvents.length'),
                  'viewport': [1440, 900]}
        (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({'ok': result['ok'], 'checks': len(checks), 'out': str(out)}), flush=True)
        if not result['ok']:
            raise SystemExit(1)
    finally:
        r.close()

if __name__ == '__main__':
    main()
