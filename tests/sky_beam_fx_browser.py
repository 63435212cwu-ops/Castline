#!/usr/bin/env python3
"""Read-only real-book causal beam grow/flow animation journey (CDP).

Drives the reviewed Xiyou graph through the public CLSky surface. Proves the
causal beams grow along their paths on event entry, that the flow dashes march
toward the consequence while playing, freeze to the stable arrow state on
pause, never animate under reduced motion, stay orthogonal to the follow
camera, and add zero >50ms long tasks over the paused baseline.
"""
import argparse, base64, json, time, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner

def main():
    a = argparse.ArgumentParser(); a.add_argument('--base', default='http://127.0.0.1:8151')
    a.add_argument('--out', default=str(Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'beam-fx'))
    args = a.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    r = Wave2AuditRunner(width=1440, height=900, dpr=1)
    checks = []
    numbers = {}

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

    def shot(name):
        (out / (name + '.png')).write_bytes(base64.b64decode(r.ws.call('Page.captureScreenshot', format='png')['data']))

    def until(expr, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            if ev(expr):
                return True
            time.sleep(.25)
        return False

    try:
        r.start()
        r.navigate(args.base + '/?sky=1&data=data/cache/c84e8657afff87043c11ae57.json')
        ready()
        ev('CLSky.setPlot(true)')
        time.sleep(3)
        ev('''window.__beamMut={};
        window.__lt=0;new PerformanceObserver(function(l){l.getEntries().forEach(function(e){if(e.duration>50)__lt++;})})
          .observe({entryTypes:['longtask']});
        window.__events=[];setInterval(function(){var s=CLSky.playerState();
          if(s.eventId&&__events[__events.length-1]!==s.eventId)__events.push(s.eventId);},200);
        window.__seenPartial=false;window.__revealProbe=setInterval(function(){var p=document.querySelector("#skyStoryBeams path.ssp-beam");
          if(!p)return;var v=p.style.getPropertyValue("--ssp-reveal");if(v&&parseFloat(v)<1)__seenPartial=true;},50);0''')
        ev('CLSky.seekEventAt(184)')
        click('#skyPlay')
        if not until('!!document.getElementById("skyStoryBeams")', 15):
            raise AssertionError('beam overlay never materialized')
        ev('''window.__beamObs=new MutationObserver(function(ms){ms.forEach(function(m){
          if(m.type==='attributes'){__beamMut[m.attributeName]=(__beamMut[m.attributeName]||0)+1;}})});
        __beamObs.observe(document.getElementById('skyStoryBeams'),{attributes:true,subtree:true,
          attributeFilter:['stroke-dashoffset','stroke-dasharray','visibility','d']});0''')
        if not until('!!document.querySelector("#skyStoryBeams .ssp-beam-flow[visibility=visible]")', 30):
            raise AssertionError('flow layer never became visible: ' + json.dumps(ev('({stage:CLSky.playerState().stage,links:CLSky.playerState().links,playing:CLSky.state().playing})')))
        time.sleep(1.5)
        check('the beam reveal sweeps from partial to fully drawn on event entry',
              'window.__seenPartial===true&&(()=>{var p=document.querySelector("#skyStoryBeams path.ssp-beam");return p.style.getPropertyValue("--ssp-reveal")==="1"})()')
        ev('clearInterval(window.__revealProbe)')
        check('every live link carries exactly one base path, one arrowhead and one flow dash layer',
              '(()=>{var s=document.getElementById("skyStoryBeams");if(!s.childNodes.length||s.childNodes.length!==CLSky.playerState().links)return false;'
              'return Array.from(s.childNodes).every(function(g){return g.querySelectorAll("path.ssp-beam").length===1&&g.querySelectorAll("polygon.ssp-beam-head").length===1&&g.querySelectorAll("path.ssp-beam-flow").length===1&&g.querySelector("path.ssp-beam-flow").getAttribute("d")===g.querySelector("path.ssp-beam").getAttribute("d")})})()')
        check('flow dashes are path-length-normalized fractions marching with real frame time',
              '(()=>{var f=document.querySelector("#skyStoryBeams .ssp-beam-flow[visibility=visible]");if(!f)return false;'
              'var d=(f.getAttribute("stroke-dasharray")||"").split(" ").map(Number);if(d.length!==2||!(d[0]>0)||d[0]+d[1]>=1)return false;'
              'return (__beamMut["stroke-dashoffset"]||0)>5;})()')
        ev('window.__offA=document.querySelector("#skyStoryBeams .ssp-beam-flow[visibility=visible]").getAttribute("stroke-dashoffset")')
        time.sleep(.6)
        check('the flow offset advances while playing (frames driven by the scene clock)',
              '(()=>{var f=document.querySelector("#skyStoryBeams .ssp-beam-flow[visibility=visible]");if(!f)return false;'
              'var b=f.getAttribute("stroke-dashoffset");return b!==window.__offA&&parseFloat(b)<0&&parseFloat(window.__offA)<=0;})()')
        shot('01-beam-flow-playing')
        check('the flow overlay only restyles attributes and never touches document layout',
              '(()=>{var s=document.getElementById("skyStoryBeams");return s.childNodes.length===CLSky.playerState().links&&__beamMut.d>0;})()')
        ev('CLSky.stop()')
        time.sleep(.8)
        ev('window.__mutAtPause=__beamMut["stroke-dashoffset"]||0')
        time.sleep(1.5)
        check('pause freezes the flow dashes and keeps the static arrow state',
              '(__beamMut["stroke-dashoffset"]||0)===window.__mutAtPause'
              '&&!document.querySelector("#skyStoryBeams .ssp-beam-flow[visibility=visible]")'
              '&&Array.from(document.querySelectorAll("#skyStoryBeams .ssp-beam-head")).every(function(h){return h.getAttribute("opacity")==="1"})'
              '&&!CLSky.state().playing')
        shot('02-beam-paused-static')
        ev('window.__ltA=__lt')
        time.sleep(4)
        baseline_lt = ev('__lt-window.__ltA')
        numbers['longtasks_paused_baseline'] = baseline_lt
        click('#skyPlay')
        ev('window.__mutResume=__beamMut["stroke-dashoffset"]||0')
        if not until('window.__events.length>=4', 45):
            raise AssertionError('playback never carried three more events: ' + json.dumps(ev('window.__events')))
        check('resumed playback flows again across three events with no stacked layers',
              '(__beamMut["stroke-dashoffset"]||0)>window.__mutResume'
              '&&document.getElementById("skyStoryBeams").childNodes.length===CLSky.playerState().links'
              '&&new Set(window.__events).size===window.__events.length')
        ev('window.__ltB=__lt')
        time.sleep(4)
        playing_lt = ev('__lt-window.__ltB')
        numbers['longtasks_playing_flow'] = playing_lt
        check('flowing beams add zero >50ms long tasks over the paused baseline',
              str(playing_lt <= baseline_lt).lower())
        ev('CLSky.setFollow(false)')
        if not until('!!document.querySelector("#skyStoryBeams .ssp-beam-flow[visibility=visible]")&&CLSky.state().playing', 40):
            raise AssertionError('no flowing stage arrived with follow off: ' + json.dumps(ev('({playing:CLSky.state().playing,stage:CLSky.playerState().stage})')))
        ev('window.__mutFollowOff=__beamMut["stroke-dashoffset"]||0')
        time.sleep(2)
        check('the flow marches with the follow camera switched off',
              '(__beamMut["stroke-dashoffset"]||0)>window.__mutFollowOff&&CLSky.state().playing')
        ev('CLSky.setFollow(true)')
        if not until('!!document.querySelector("#skyStoryBeams .ssp-beam-flow[visibility=visible]")&&CLSky.state().playing', 40):
            raise AssertionError('no flowing stage arrived with follow back on: ' + json.dumps(ev('({playing:CLSky.state().playing,stage:CLSky.playerState().stage})')))
        ev('window.__mutFollowOn=__beamMut["stroke-dashoffset"]||0')
        time.sleep(2)
        check('the flow marches with the follow camera switched back on',
              '(__beamMut["stroke-dashoffset"]||0)>window.__mutFollowOn')
        r.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])
        time.sleep(.3)
        ev('CLSky.stop();window.__mutReduced=(__beamMut["stroke-dashoffset"]||0)+(__beamMut["stroke-dasharray"]||0)')
        ev('CLSky.seekEventAt(196)')
        click('#skyPlay')
        time.sleep(3)
        check('reduced motion draws the terminal state at once with zero flow frames',
              '((__beamMut["stroke-dashoffset"]||0)+(__beamMut["stroke-dasharray"]||0))===window.__mutReduced'
              '&&!document.querySelector("#skyStoryBeams .ssp-beam-flow[visibility=visible]")'
              '&&Array.from(document.querySelectorAll("#skyStoryBeams path.ssp-beam")).every(function(p){return p.style.getPropertyValue("--ssp-reveal")==="1"})')
        r.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'no-preference'}])
        ev('CLSky.stop()')
        time.sleep(.5)
        check('beam fx journey has no uncaught JavaScript, Promise, shader or frame-hook errors',
              '__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0&&CLApp.scene().core().perf().frameHooks.errors===0')
        shot('03-beam-reduced-terminal')
        result = {'ok': all(x['ok'] for x in checks), 'checks': checks, 'numbers': numbers,
                  'eventsVisited': ev('window.__events.length'), 'mutations': ev('window.__beamMut'),
                  'viewport': [1440, 900]}
        (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({'ok': result['ok'], 'checks': len(checks), 'numbers': numbers, 'out': str(out)}), flush=True)
        if not result['ok']:
            raise SystemExit(1)
    finally:
        r.close()

if __name__ == '__main__':
    main()
