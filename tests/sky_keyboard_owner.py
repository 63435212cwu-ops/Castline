#!/usr/bin/env python3
"""Real CDP keyboard ownership regression; sky decks and retained atlas R."""
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
ROOT = Path('/Users/carmen/Desktop/星系')
sys.path.insert(0, str(ROOT / 'tests'))
import headless
import sky_chaos as chaos

BOOKS = dict(chaos.BOOKS)
INPUTS = ['tests/sky_chaos.py', 'tests/headless.py', 'js/keys.js', 'js/sky/sky-shell.js',
          'js/sky/sky-deck.js', 'js/sky/sky-groups.js', 'js/sky/sky-view.js',
          'js/sky/sky-deep.js', 'js/core/scene-stage.js', 'index.html', 'tests/script_manifest.json']

INSTALL = r"""(function(){
  var S=CLApp.scene(), D=window.CLSkyDeep, E=window.CLTreeEvents, old=[], count={legacyHome:0,skyReset:0,eventNext:0,eventPrev:0};
  function wrap(o,key,name){if(!o||typeof o[key]!=='function')return false;var f=o[key];old.push([o,key,f]);o[key]=function(){count[name]++;return f.apply(this,arguments);};return true;}
  var available={home:wrap(S,'home','legacyHome'),reset:wrap(D,'resetView','skyReset'),
    next:wrap(E,'next','eventNext'),prev:wrap(E,'prev','eventPrev'),pick:!!(E&&typeof E.pick==='function')};
  window.__keyOwner={count:count,available:available,restore:function(){old.forEach(function(x){x[0][x[1]]=x[2];});}};
  return available;
})()"""

SNAPSHOT = r"""(function(){
  var S=CLApp.scene(), st=window.CLSky?CLSky.state():{}, a=document.activeElement, sel=window.__keyOwnerSelector, v=sel?document.querySelector(sel):null;
  var deck=window.__keyOwnerKind==='plot'?CLSky.deck():window.CLSkyGroupsShell&&CLSkyGroupsShell.deck(), root=v&&v.closest('.skd-deck, .skg-deck');
  var vr=v&&v.getBoundingClientRect(), vs=v&&getComputedStyle(v), rs=root&&getComputedStyle(root);
  var viewVisible=!!(v&&root&&!root.hidden&&vr.width>20&&vr.height>20&&vs.display!=='none'&&vs.visibility!=='hidden'&&rs.display!=='none'&&rs.visibility!=='hidden'&&+rs.opacity>0);
  var f=v&&v.querySelector('.is-focus'), d=CLSky.disc&&CLSky.disc(), p=new THREE.Vector3(), R=S.rimInfo&&S.rimInfo();
  if(d&&d.anchor&&d.anchor())d.anchor().getWorldPosition(p);
  return {count:__keyOwner.count,available:__keyOwner.available,target:S.controls.target.toArray(),
    position:S.camera.position.toArray(),toDisc:S.controls.target.distanceTo(p),R:R&&R.R||400,
    shellEnabled:!!(window.CLSky&&CLSky.enabled()),mode:st.mode,plot:st.plot,cursor:st.cursor,
    active:a&&a.className,viewportFocused:a===v,viewVisible:viewVisible,deckRoot:root&&root.className,focus:f&&f.getAttribute('data-key'),
    deck:deck?deck.stats():null,playing:st.playing,
    finite:S.camera.position.toArray().concat(S.controls.target.toArray()).every(isFinite)};
})()"""


def hashes():
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in INPUTS}


def distance(a,b):
    return sum((x-y)**2 for x,y in zip(a,b))**.5


def healthy(browser):
    output=io.StringIO()
    with redirect_stdout(output):
        code=headless.post_health(browser.ws,[])
    rows=[s[13:] for s in output.getvalue().splitlines() if s.startswith('POST-HEALTH: ')]
    if len(rows)!=1:raise RuntimeError('Missing POST-HEALTH JSON')
    h=json.loads(rows[0])
    if code!=0 or h.get('ok') is not True or h.get('exitCode')!=0:raise RuntimeError('Actual page unhealthy: '+json.dumps(h))
    return h


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default='http://127.0.0.1:8765')
    parser.add_argument('--books',default='saga,sanguo,dafeng')
    parser.add_argument('--size',default='1600x1000')
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    if os.environ.get('CL_GPU')!='1':raise SystemExit('CL_GPU=1 required')
    books=args.books.split(',')
    if not books or any(b not in BOOKS for b in books) or len(set(books))!=len(books):raise SystemExit('Invalid/duplicate books')
    w,h=map(int,args.size.split('x'))
    if w<=900 or h<300:raise SystemExit('Desktop >900px is required for both deck ownership cases')
    args.out.mkdir(parents=True,exist_ok=False)
    source=hashes();checks=[];sessions=[]

    def check(name,ok,detail):
        checks.append({'name':name,'ok':bool(ok),'detail':detail})
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)

    for book in books:
        for shell in ('sky','atlas'):
            b=chaos.Browser(w,h);row={'book':book,'shell':shell};sessions.append(row)
            try:
                b.start()
                query='sky=1&probe=1' if shell=='sky' else 'shell=atlas&probe=1'
                b.ws.call('Page.navigate',url=args.base.rstrip('/')+'/?'+query+'&data='+BOOKS[book])
                ready="!!(window.CLApp&&CLApp.scene()&&CLApp.graph()&&CLApp.graph().characters.length&&window.CLKeys)"
                if shell=='sky':ready+=" && !!(window.CLSkyDeep&&CLSkyDeep.enabled()&&CLSkyDeep.stats().stars.ignite>.99)"
                else:ready+=" && (!document.getElementById('loader')||document.getElementById('loader').classList.contains('off'))"
                if not b.until(ready,60):raise RuntimeError('Actual book did not become ready')
                time.sleep(2.2)
                available=b.ev(INSTALL)
                if not available.get('home'):raise RuntimeError('Actual scene.home spy is unavailable')
                if shell=='atlas':
                    b.ev("window.__keyOwnerSelector=null;window.__keyOwnerKind=null;document.activeElement&&document.activeElement.blur&&document.activeElement.blur();")
                    before=b.ev(SNAPSHOT);b.key('r');time.sleep(1.6);after=b.ev(SNAPSHOT)
                    check(book+' atlas legacy R retained',not after['shellEnabled'] and after['finite']
                          and after['count']['legacyHome']==before['count']['legacyHome']+1
                          and after['count']['skyReset']==before['count']['skyReset'],{'before':before,'after':after})
                else:
                    if not all(available.get(k) for k in ('reset','next','prev','pick')):raise RuntimeError('Actual legacy event navigation/sky reset spies are unavailable')
                    for kind,selector in [('plot','.skd-deck:not(.skg-deck) .skd-deck__viewport'),('group','.skg-deck .skg-viewport')]:
                        b.ev("CLSky.stop();if(CLSky.state().mode==='compass')CLSky.closeCompass();CLSky.setPlot("+('true' if kind=='plot' else 'false')+");")
                        time.sleep(2.6)
                        if kind=='group':b.ev("CLSkyGroupsShell.deck().fold(false);CLSkyGroupsShell.deck().open(null);")
                        else:b.ev("CLSky.deck().open(null);")
                        b.ev("window.__keyOwnerKind="+json.dumps(kind)+";window.__keyOwnerSelector="+json.dumps(selector)+";")
                        if not b.until("(function(){var v=document.querySelector(__keyOwnerSelector),r=v&&v.closest('.skd-deck, .skg-deck'),b=v&&v.getBoundingClientRect(),s=v&&getComputedStyle(v),rs=r&&getComputedStyle(r);return !!(v&&r&&!r.hidden&&b.width>20&&b.height>20&&s.display!=='none'&&s.visibility!=='hidden'&&rs.display!=='none'&&rs.visibility!=='hidden'&&+rs.opacity>0);})()",5):
                            raise RuntimeError('Actual '+kind+' viewport is not shown')
                        b.ev("document.querySelector(__keyOwnerSelector).focus();")
                        before=b.ev(SNAPSHOT)
                        if not before['viewVisible'] or not before['viewportFocused'] or not before['deck'] or before['deck']['cards']<2:raise RuntimeError('No real visible focused multi-card deck')
                        b.key('r');time.sleep(1.6);after=b.ev(SNAPSHOT)
                        limit=.03*before['R']
                        check(book+' '+kind+' focused R belongs to sky home',after['finite'] and after['viewportFocused'] and after['viewVisible']
                              and after['count']['legacyHome']==before['count']['legacyHome']
                              and after['count']['skyReset']==before['count']['skyReset']+1
                              and distance(after['target'],before['target'])<=limit
                              and abs(after['toDisc']-before['toDisc'])<=limit,
                              {'before':before,'after':after,'unchangedI2Limit':limit})
                        before=b.ev(SNAPSHOT);b.key('ArrowLeft');b.key('ArrowRight');time.sleep(.4);after=b.ev(SNAPSHOT)
                        check(book+' '+kind+' left/right never navigate legacy events',after['count']==before['count']
                              and after['cursor']==before['cursor'] and after['viewportFocused']
                              and distance(after['target'],before['target'])<1e-3
                              and distance(after['position'],before['position'])<.5,{'before':before,'after':after})
                        b.key('Home');time.sleep(.4);first=b.ev(SNAPSHOT)
                        b.key('ArrowDown');time.sleep(.4);second=b.ev(SNAPSHOT)
                        b.key('ArrowUp');time.sleep(.4);up=b.ev(SNAPSHOT)
                        check(book+' '+kind+' up/down remain card navigation',first['focus'] is not None
                              and second['focus'] is not None and second['focus']!=first['focus']
                              and up['focus']==first['focus'] and up['viewportFocused']
                              and up['count']==first['count'] and distance(up['position'],first['position'])<.5,
                              {'first':first,'second':second,'up':up})
                        b.key('Enter');time.sleep(.5);opened=b.ev(SNAPSHOT)
                        b.key('Escape');time.sleep(.5);closed=b.ev(SNAPSHOT)
                        check(book+' '+kind+' Enter opens and Esc closes its real card',opened['deck']['open']==up['focus']
                              and closed['deck']['open'] is None and closed['viewportFocused']
                              and opened['count']==up['count'] and closed['count']==up['count']
                              and closed['mode']==up['mode'] and closed['plot']==up['plot'],
                              {'before':up,'opened':opened,'closed':closed})
                row['health']=healthy(b);row['ok']=True
            except Exception as exc:
                row['ok']=False;row['error']=str(exc)
                check(book+' '+shell+' session completed',False,str(exc))
            finally:
                try:b.ev("if(window.__keyOwner)__keyOwner.restore();")
                except Exception:pass
                b.close()
    stable=hashes()==source
    if not stable:check('Single unchanged source version',False,'Code changed during the run')
    ok=stable and len(sessions)==len(books)*2 and all(r.get('ok') for r in sessions) and bool(checks) and all(r['ok'] for r in checks)
    report={'ok':ok,'complete':True,'sourceHashes':source,'books':books,'size':args.size,'sessions':sessions,'checks':checks,
            'finishedAt':datetime.now(timezone.utc).isoformat(),'boundary':'Real CDP input and actual production APIs; wrappers only count and delegate, no fake state/physics.'}
    temp=args.out/'result.json.tmp';temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');os.replace(temp,args.out/'result.json')
    print('SKY-KEYBOARD-OWNER '+('OK' if ok else 'FAIL')+' '+str(sum(r['ok'] for r in checks))+'/'+str(len(checks)),flush=True)
    return 0 if ok else 1


if __name__=='__main__':raise SystemExit(main())
