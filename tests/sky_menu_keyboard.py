#!/usr/bin/env python3
"""Real CDP menu ownership regression. Requires main's serial GPU slot.

Migrates to tests/; --root supports running this candidate against a served repo.
No keyboard handler is replaced. btnInfo.click is intercepted at its safe action
entry so Space traverses real chrome activation without opening a panel.
"""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
INPUTS = ['index.html', 'tests/script_manifest.json', 'tests/sky_chaos.py',
          'tests/headless.py', 'js/keys.js', 'js/sky/sky-shell.js',
          'js/sky/sky-shell-player.js', 'js/sky/sky-chrome.js',
          'js/sky/sky-deep.js', 'js/sky/sky-view.js', 'js/core/scene-core.js']
INSTALL = r"""(()=>{
 const S=CLApp.scene(),D=CLSkyDeep,src=document.getElementById('btnInfo');
 if(!src||src.disabled||src.getAttribute('aria-disabled')==='true')throw Error('Safe btnInfo unavailable');
 const old=[],count={nudge:0,setCalm:0,safeClick:0},calls=[];
 function wrap(o,k){if(typeof o[k]!=='function')throw Error('Missing API '+k);
 const f=o[k];old.push(()=>{o[k]=f;});o[k]=function(...a){count[k]++;calls.push({api:k,args:a,at:performance.now()});return f.apply(this,a);};}
 wrap(D,'nudge');wrap(S,'setCalm');
 const own=Object.prototype.hasOwnProperty.call(src,'click'),click=src.click;
 src.click=function(){count.safeClick++;calls.push({api:'btnInfo.click intercepted',at:performance.now()});};
 old.push(()=>{if(own)src.click=click;else delete src.click;});
 const events=[];function record(e){events.push({key:e.key,trusted:e.isTrusted,at:performance.now()});}
 window.addEventListener('keydown',record,true);
 old.push(()=>window.removeEventListener('keydown',record,true));
 window.__menuKeyboard={count,calls,events,restore(){old.reverse().forEach(f=>f());}};
 return true;
})()"""
SNAPSHOT = r"""(()=>{
 const S=CLApp.scene(),st=CLSky.state(),menu=document.getElementById('skyToolsMenu'),a=document.activeElement;
 const core=S&&S.core&&S.core(),frames=core&&core.getFrames?core.getFrames():null;
 const reduced=window.matchMedia?window.matchMedia('(prefers-reduced-motion: reduce)').matches:null;
 const all=menu?Array.from(menu.querySelectorAll('.stm-item')):[];
 const enabled=all.filter(b=>!b.hidden&&!b.disabled&&b.getAttribute('aria-disabled')!=='true');
 const r=menu&&menu.getBoundingClientRect(),cs=menu&&getComputedStyle(menu);
 return {count:{...__menuKeyboard.count},calls:__menuKeyboard.calls.slice(),events:__menuKeyboard.events.slice(),
 visibilityState:document.visibilityState,documentHidden:document.hidden,
 sceneFrames:frames,navigatorUserActivation:navigator.userActivation?navigator.userActivation.isActive:null,
 prefersReducedMotion:reduced,tokenReduced:window.CLSkyTokens&&window.CLSkyTokens.reduced?window.CLSkyTokens.reduced():null,
 position:S.camera.position.toArray(),target:S.controls.target.toArray(),
 finite:S.camera.position.toArray().concat(S.controls.target.toArray()).every(Number.isFinite),
 mode:st.mode,plot:st.plot,playing:st.playing,cursor:st.cursor,manualCalm:S.manualCalm(),
 menuOn:CLSkyChrome.menuOpen(),menuVisible:!!(menu&&!menu.hidden&&r.width>0&&r.height>0&&cs.display!=='none'&&cs.visibility!=='hidden'),
 focus:a&&a.getAttribute('data-for'),activeId:a&&a.id,focusIndex:enabled.indexOf(a),
 enabled:enabled.map(b=>b.getAttribute('data-for')),disabled:all.filter(b=>b.disabled||b.getAttribute('aria-disabled')==='true').map(b=>b.getAttribute('data-for'))};
})()"""


def held_key(browser, key, repeats=4):
    mapping = {' ': ('Space', 32, 0), 'Enter': ('Enter', 13, 0), 'ArrowDown': ('ArrowDown', 40, 0),
               'ArrowUp': ('ArrowUp', 38, 0), 'ArrowLeft': ('ArrowLeft', 37, 0),
               'ArrowRight': ('ArrowRight', 39, 0), '?': ('Slash', 191, 8)}
    if key in mapping:
        code, vk, modifiers = mapping[key]
    elif len(key) == 1:
        code, vk, modifiers = 'Key' + key.upper(), ord(key.upper()), 0
    else:
        raise ValueError('Unsupported held key: ' + repr(key))
    def send(kind, repeat=False):
        args = {'type': kind, 'key': key, 'code': code,
                'windowsVirtualKeyCode': vk, 'nativeVirtualKeyCode': vk}
        if modifiers: args['modifiers'] = modifiers
        if repeat: args['autoRepeat'] = True
        browser.ws.call('Input.dispatchKeyEvent', **args)
    send('keyDown')
    for _ in range(repeats): send('keyDown', True)
    send('keyUp')
    time.sleep(.18)
    return browser.ev(SNAPSHOT)

def distance(a, b):
    return sum((x-y)**2 for x, y in zip(a, b))**.5


def unchanged(a, b):
    return (a['count'] == b['count'] and a['plot'] == b['plot']
            and a['mode'] == b['mode'] and a['playing'] == b['playing']
            and a['cursor'] == b['cursor'] and a['manualCalm'] == b['manualCalm']
            and b['finite'] and distance(a['position'], b['position']) < .5
            and distance(a['target'], b['target']) < 1e-3)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--base', default='http://127.0.0.1:8765')
    p.add_argument('--books', default='saga,sanguo')
    p.add_argument('--size', default='1600x1000')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; execute only in main serial GPU slot')
    root = args.root.resolve()
    sys.path.insert(0, str(root/'tests'))
    import headless
    import sky_chaos as chaos
    books = args.books.split(',')
    available = dict(chaos.BOOKS)
    if len(set(books)) != len(books) or len(books) < 2 or any(b not in available for b in books):
        raise SystemExit('At least two distinct real books from sky_chaos.BOOKS required')
    w, h = map(int, args.size.split('x'))
    if w <= 900 or h < 500:
        raise SystemExit('Desktop viewport >900px and height >=500 required')
    args.out.mkdir(parents=True, exist_ok=False)
    paths = INPUTS + [available[b] for b in books]
    def hashes():
        return {s: hashlib.sha256((root/s).read_bytes()).hexdigest() for s in paths}
    source = hashes()
    checks, sessions = [], []
    def save():
        report = {'ok':bool(checks) and all(c['ok'] for c in checks)
                  and len(sessions)==len(books)*2 and all(s.get('ok') for s in sessions),
                  'complete':len(sessions)==len(books)*2 and all('ok' in s for s in sessions),
                  'root':str(root),'base':args.base,'books':books,'size':args.size,
                  'sourceHashes':source,'testHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'sessions':sessions,'checks':checks,'finishedAt':datetime.now(timezone.utc).isoformat(),
                  'boundary':'Actual CDP keys and UI pointer click; nudge/setCalm delegate. Only btnInfo.click intercepted. No keyboard logic replaced.'}
        tmp=args.out/'result.json.tmp'
        tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        os.replace(tmp,args.out/'result.json')
        return report['ok']
    def check(name, ok, before=None, after=None):
        checks.append({'name':name,'ok':bool(ok),'before':before,'after':after})
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        save()
    def health(b):
        output=io.StringIO()
        with redirect_stdout(output):
            code=headless.post_health(b.ws,[])
        rows=[s[13:] for s in output.getvalue().splitlines() if s.startswith('POST-HEALTH: ')]
        return {'code':code,'report':json.loads(rows[0]) if len(rows)==1 else None,'raw':output.getvalue()}
    for book in books:
        for mode in ('constellation','plot'):
            row={'book':book,'mode':mode,'data':available[book],'steps':[]}
            sessions.append(row)
            b=None
            try:
                b=chaos.Browser(w,h);b.start()
                b.ws.call('Page.navigate',url=args.base.rstrip('/')+'/?sky=1&probe=1&data='+available[book])
                if not b.until("document.readyState==='complete' && !!(window.CLApp&&CLApp.scene()&&CLApp.graph()&&CLApp.graph().characters.length&&window.CLSkyDeep&&CLSkyDeep.enabled()&&CLSkyDeep.stats().stars.ignite>.99&&window.CLSkyChrome)",60):
                    raise RuntimeError('Real book readiness timed out')
                b.ev("CLSky.stop();CLSky.setPlot("+str(mode=='plot').lower()+");CLApp.scene().setCalm(true);")
                time.sleep(3)
                if not b.ev(INSTALL):raise RuntimeError('Spy installation failed')
                def snap():return b.ev(SNAPSHOT)
                def key(k):
                    if k in ('Home','End','Tab'):
                        for typ in ('keyDown','keyUp'):
                            b.ws.call('Input.dispatchKeyEvent',type=typ,key=k,code=k,
                                      windowsVirtualKeyCode={'Home':36,'End':35,'Tab':9}[k])
                    else:b.key(k)
                    time.sleep(.18)
                    s=snap();row['steps'].append({'key':k,'snapshot':s});return s
                def open_menu():
                    rect=b.ev("(()=>{const e=document.getElementById('skyTools'),r=e.getBoundingClientRect();if(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)!==e&&!e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)))throw Error('Tools occluded');return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
                    b.mouse('mousePressed',rect['x'],rect['y']);b.mouse('mouseReleased',rect['x'],rect['y'])
                    if not b.until("CLSkyChrome.menuOpen()",3):raise RuntimeError('Tools pointer click did not open menu')
                    time.sleep(.35)
                    s=snap()
                    if not s['menuVisible'] or len(s['enabled'])<2 or s['focusIndex']!=0:
                        raise RuntimeError('Visible multi-item menu with first enabled focus required')
                    return s
                tag=book+' '+mode
                before=open_menu()
                after=held_key(b,'ArrowDown')
                expected_focus=(before['focusIndex']+5)%len(before['enabled'])
                check(tag+' held ArrowDown repeats five menu steps',unchanged(before,after)
                      and after['menuVisible'] and after['focusIndex']==expected_focus,before,after)
                before=after
                for k in ['ArrowDown','ArrowUp','End','ArrowDown','Home','ArrowUp']:
                    after=key(k);n=len(before['enabled']);i=before['focusIndex']
                    want=0 if k=='Home' else n-1 if k=='End' else (i+(1 if k=='ArrowDown' else -1))%n
                    check(tag+' menu '+k,unchanged(before,after) and after['menuVisible']
                          and after['enabled']==before['enabled'] and after['focusIndex']==want,before,after)
                    before=after
                for k in ['Escape','Tab']:
                    if not before['menuOn']:before=open_menu()
                    after=key(k)
                    check(tag+' '+k+' returns Tools',unchanged(before,after) and not after['menuOn']
                          and not after['menuVisible'] and after['activeId']=='skyTools',before,after)
                    before=after
                before=open_menu();before=key('Home')
                if 'btnInfo' not in before['enabled']:raise RuntimeError('Safe enabled menu action missing')
                for _ in range(before['enabled'].index('btnInfo')):before=key('ArrowDown')
                if before['focus']!='btnInfo':raise RuntimeError('CDP navigation did not reach safe action')
                after=held_key(b,' ')
                expected=dict(before['count']);expected['safeClick']+=1
                comparable=dict(after);comparable['count']=before['count']
                check(tag+' Space activates only safe entry',after['count']==expected and not after['menuOn']
                      and unchanged(before,comparable),before,after)
                before=open_menu();before=key('Home')
                for _ in range(before['enabled'].index('btnInfo')):before=key('ArrowDown')
                if before['focus']!='btnInfo':raise RuntimeError('Enter safe action focus failed')
                after=held_key(b,'Enter')
                expected=dict(before['count']);expected['safeClick']+=1
                comparable=dict(after);comparable['count']=before['count']
                check(tag+' held Enter activates safe entry once',after['count']==expected and not after['menuOn']
                      and unchanged(before,comparable),before,after)
                before=open_menu();after=key('Escape')
                check(tag+' activation recovery Esc',after['activeId']=='skyTools' and not after['menuOn'],before,after)
                before=after;after=key('ArrowDown');time.sleep(1.0);after=snap()
                check(tag+' closed menu direction rotates',after['count']['nudge']==before['count']['nudge']+1
                      and after['finite'] and distance(before['position'],after['position'])>.5
                      and after['playing']==before['playing'] and after['cursor']==before['cursor'],before,after)
                before=after;after=held_key(b,' ')
                if mode=='plot':
                    ok=not before['playing'] and after['playing'] and after['cursor'] is not None
                    ok=ok and after['count']==before['count']
                else:
                    ok=after['manualCalm']!=before['manualCalm'] and after['count']['setCalm']==before['count']['setCalm']+1
                    ok=ok and after['playing']==before['playing'] and after['cursor']==before['cursor']
                check(tag+' closed menu Space retains action',ok and after['finite'],before,after)
                after2=key(' ')
                check(tag+' second Space restores state',after2['playing']==before['playing'] if mode=='plot'
                      else after2['manualCalm']==before['manualCalm'],after,after2)
                was_help=b.ev('CLKeys.panelOn()')
                if was_help: b.ev('CLKeys.close()')
                held_key(b,'?',repeats=3)
                help_open=b.ev('CLKeys.panelOn()')
                check(tag+' held ? opens help once',not was_help and help_open,after,{'helpOpen':help_open})
                if help_open: key('Escape')
                evidence=snap()
                check(tag+' trusted CDP input evidence',bool(evidence['events']) and all(e['trusted'] for e in evidence['events']),after=evidence['events'])
                row['ok']=True
            except Exception as exc:
                row['ok']=False;row['error']=str(exc)
                check(book+' '+mode+' completed',False,after={'error':str(exc)})
                if b and b.ws:
                    try:row['failureSnapshot']=b.ev(SNAPSHOT)
                    except Exception as e:row['snapshotError']=str(e)
            finally:
                if b and b.ws:
                    try:
                        row['health']=health(b);hh=row['health']
                        good=hh['code']==0 and hh['report'] is not None and hh['report'].get('ok') is True and hh['report'].get('exitCode')==0
                        check(book+' '+mode+' page health',good,after=hh)
                        if not good:row['ok']=False
                    except Exception as e:row['healthError']=str(e);row['ok']=False;check(book+' '+mode+' health collected',False,after=str(e))
                    try:b.ev("CLSky.stop();if(window.__menuKeyboard)__menuKeyboard.restore();")
                    except Exception as e:row['restoreError']=str(e);row['ok']=False
                else:
                    row['healthUnavailable']='Browser/CDP never became available'
                if b:
                    try:b.close()
                    except Exception as e:row['closeError']=str(e);row['ok']=False
                save()
    try:check('Single unchanged source and data version',hashes()==source)
    except Exception as e:check('Source hash verification',False,after=str(e))
    ok=save()
    print('SKY-MENU-KEYBOARD '+('OK' if ok else 'FAIL')+' '+str(args.out/'result.json'),flush=True)
    return 0 if ok else 1


if __name__=='__main__':
    raise SystemExit(main())
