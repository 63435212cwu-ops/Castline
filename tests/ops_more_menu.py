#!/usr/bin/env python3
"""Real CDP acceptance for the #ops "更多" menu contract (aria / ring / zoom persist).

Runs in the atlas workspace (?shell=atlas): the classic #ops row only lives
there (the sky shell keeps the row display:none and projects these actions
into the sky tools menu; opening "工具" reveals the overlay via #aphTools).
Every interaction is trusted CDP input — hover, trigger click, ring keys,
Escape, outside pointer, item click, zoom click, reload. The menu-item
activation probe targets #btnInfo end-to-end on purpose: the real dialog
opens, the end state is asserted, one Escape closes it again. The focus-out
close probe moves focus with element.focus() because programmatically moving
trusted focus has no input representation; everything else is trusted CDP
input. Zoom-overlay semantics: toggling the zoom checkbox deliberately closes
the tools overlay (pre-existing ops-bus rule "点选条目 = 用那个工具"—the box
itself is not the 更多 trigger, so the overlay re-hides on the click and
Chrome drops focus from the now-hidden checkbox); asserted via the durable
facts — checked / aria-checked / localStorage — not transient aria-expanded.
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
INPUTS = ['index.html', 'tests/script_manifest.json', 'tests/headless.py', 'tests/sky_chaos.py',
          'js/app.js', 'js/atlas/atlas-preview-session.js', 'js/information-architecture.js',
          'css/app-shell.css', 'css/atlas-workspace.css']
RING = ['btnDistill', 'btnPreview', 'btnDual', 'btnInfo', 'btnApi', 'btnFull', 'opsZoom']
KEYCODES = {'Escape': 27, 'Tab': 9, 'Home': 36, 'End': 35,
            'ArrowUp': 38, 'ArrowDown': 40, 'ArrowLeft': 37, 'ArrowRight': 39}

INSTALL = r"""(()=>{
 const events=[];
 function rec(e){if(e.isTrusted)window.__opsMoreProof.events.push({type:e.type,key:e.key||null,
   tag:e.target&&e.target.tagName||'',id:e.target&&e.target.id||'',trusted:!!e.isTrusted});}
 window.addEventListener('keydown',rec,true);
 window.__opsMoreProof={events:events};
 return true;
})()"""

SNAPSHOT = r"""(function(){
 var btn=document.getElementById('opsMoreBtn'),menu=document.getElementById('opsMoreMenu'),
     zoom=document.getElementById('opsZoom'),a=document.activeElement,store=null;
 try{store=localStorage.getItem('castline.opsZoom');}catch(e){store='ERR';}
 return {aria:btn.getAttribute('aria-expanded'),haspopup:btn.getAttribute('aria-haspopup'),
  controls:btn.getAttribute('aria-controls'),menuRole:menu.getAttribute('role'),
  menuLabel:menu.getAttribute('aria-label'),display:getComputedStyle(menu).display,
  toolsOpen:document.body.classList.contains('atlas-tools-open'),
  opsDisplay:getComputedStyle(document.getElementById('ops')).display,
  active:a?(a.id||a.className||a.tagName):null,inMore:!!(a&&a.closest&&a.closest('#ops .ops-more')),
  zoomChecked:zoom.checked,zoomAria:zoom.getAttribute('aria-checked'),stored:store,
  roles:[].slice.call(menu.querySelectorAll('[role="menuitem"],[role="menuitemcheckbox"]'))
        .map(function(x){return {id:x.id,role:x.getAttribute('role')};}),
  iaOpen:!!(window.CLInformationArchitecture&&CLInformationArchitecture.isOpen&&CLInformationArchitecture.isOpen()),
  events:window.__opsMoreProof.events.slice()};
})()"""

READY = ("!!(window.CLApp&&CLApp.scene()&&CLApp.graph()&&CLApp.graph().characters.length&&window.CLKeys"
         "&&window.CLAtlasPreview&&CLAtlasPreview.active())"
         "&&(!document.getElementById('loader')||document.getElementById('loader').classList.contains('off'))")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8765')
    p.add_argument('--book', default='saga')
    p.add_argument('--size', default='1600x1000')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; execute only in main serial GPU slot')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'tests'))
    import headless
    import sky_chaos as chaos
    books = dict(chaos.BOOKS)
    if args.book not in books:
        raise SystemExit('Unknown --book ' + args.book)
    w, h = map(int, args.size.split('x'))
    if w <= 900 or h < 500:
        raise SystemExit('Desktop viewport >900px and height >=500 required')
    args.out.mkdir(parents=True, exist_ok=False)

    def hashes():
        return {s: hashlib.sha256((root / s).read_bytes()).hexdigest() for s in INPUTS + [books[args.book]]}
    source = hashes()
    checks = []

    def save():
        report = {'ok': bool(checks) and all(c['ok'] for c in checks), 'book': args.book,
                  'base': args.base, 'size': args.size, 'sourceHashes': source,
                  'testHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'checks': checks, 'finishedAt': datetime.now(timezone.utc).isoformat(),
                  'boundary': 'Trusted CDP input throughout; menu item activation runs end-to-end through the real reference-index dialog (closed again by one trusted Escape); focus-out probe uses element.focus() solely to move document focus.'}
        tmp = args.out / 'result.json.tmp'
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        os.replace(tmp, args.out / 'result.json')
        return report['ok']

    def check(name, ok, after=None):
        checks.append({'name': name, 'ok': bool(ok), 'after': after})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        save()

    b = chaos.Browser(w, h)
    try:
        b.start()

        def navigate(tag):
            b.ws.call('Page.navigate', url=args.base.rstrip('/') + '/?shell=atlas&probe=1&data=' + books[args.book])
            if not b.until(READY, 60):
                raise RuntimeError(tag + ': atlas workspace did not become ready')
            time.sleep(1.5)
            if not b.ev(INSTALL):
                raise RuntimeError(tag + ': safe-action spy installation failed')

        def snap():
            return b.ev(SNAPSHOT)

        def key(k):
            code = KEYCODES[k]
            for typ in ('keyDown', 'keyUp'):
                b.ws.call('Input.dispatchKeyEvent', type=typ, key=k, code=k, windowsVirtualKeyCode=code)

        def point(sel):
            r = b.ev("(()=>{const e=document.querySelector(%s),r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);"
                     "if(!r.width||!r.height)throw Error('zero rect for '+%s);"
                     "if(!(h===e||e.contains(h)||(h&&h.contains&&h.contains(e))))throw Error('occluded '+%s+' hit='+(h&&(h.id||h.className)));"
                     "return {x:r.x+r.width/2,y:r.y+r.height/2};})()" % (json.dumps(sel), json.dumps(sel), json.dumps(sel)))
            return r['x'], r['y']

        def click(sel):
            x, y = point(sel)
            b.mouse('mousePressed', x, y)
            b.mouse('mouseReleased', x, y)
            time.sleep(.35)

        def open_overlay():
            if snap()['toolsOpen']:
                return
            click('#aphTools')
            if not b.until("document.body.classList.contains('atlas-tools-open')&&getComputedStyle(document.getElementById('ops')).display==='flex'", 4):
                raise RuntimeError('tools overlay did not open')

        def open_menu_via_click():
            open_overlay()
            click('#opsMoreBtn')
            if not b.until("getComputedStyle(document.getElementById('opsMoreMenu')).display==='flex'", 4):
                raise RuntimeError('menu did not open on trigger click')

        navigate('boot')
        s0 = snap()
        check('roles: menu + 6 menuitem + 1 menuitemcheckbox, labelled',
              s0['menuRole'] == 'menu' and bool(s0['menuLabel'])
              and s0['roles'] == [{'id': rid, 'role': 'menuitemcheckbox' if rid == 'opsZoom' else 'menuitem'} for rid in RING], s0['roles'])
        check('trigger aria contract: haspopup/controls/collapsed',
              s0['haspopup'] == 'menu' and s0['controls'] == 'opsMoreMenu' and s0['aria'] == 'false', s0)

        check('tools overlay opens through real 工具 click', not open_overlay() and snap()['opsDisplay'] == 'flex', snap())
        x, y = point('#opsMoreBtn'); b.mouse('mouseMoved', w * .5, h * .55); b.mouse('mouseMoved', x, y); time.sleep(.3)
        s = snap()
        check('hover opens menu and syncs aria-expanded', s['aria'] == 'true' and s['display'] == 'flex', s)
        b.mouse('mouseMoved', w * .5, h * .55); time.sleep(.35)
        s = snap()
        check('hover leave collapses menu (suppress reset)', s['aria'] == 'false' and s['display'] == 'none', s)
        open_menu_via_click()
        s = snap()
        check('trigger click opens menu, keeps overlay, focuses trigger',
              s['aria'] == 'true' and s['display'] == 'flex' and s['toolsOpen'] and s['active'] == 'opsMoreBtn', s)
        key('ArrowDown'); time.sleep(.3); s = snap()
        check('ArrowDown on trigger walks into first menu item', s['active'] == RING[0] and s['aria'] == 'true' and s['display'] == 'flex', s)
        walk = [s['active']]
        for _ in range(len(RING) - 1):
            key('ArrowDown'); time.sleep(.22); walk.append(snap()['active'])
        check('ArrowDown walks the entire menu ring in order', walk == RING, walk)
        key('ArrowDown'); time.sleep(.22); s = snap()
        check('ring wraps from last back to first', s['active'] == RING[0], s['active'])
        key('ArrowUp'); time.sleep(.22); up = snap()
        key('Home'); time.sleep(.22); home = snap()
        key('End'); time.sleep(.22); end = snap()
        check('ArrowUp wraps up; Home/End jump the ends',
              up['active'] == RING[-1] and home['active'] == RING[0] and end['active'] == RING[-1],
              [up['active'], home['active'], end['active']])
        key('Escape'); time.sleep(.35); s = snap()
        check('Escape collapses menu and hands focus back to the trigger (suppress held)',
              s['aria'] == 'false' and s['display'] == 'none' and s['active'] == 'opsMoreBtn' and s['inMore'], s)
        key('ArrowDown'); time.sleep(.3); s = snap()
        check('ArrowDown on refocused trigger explicitly re-opens into the ring',
              s['aria'] == 'true' and s['display'] == 'flex' and s['active'] == RING[0], s)
        key('Escape'); time.sleep(.3)
        open_menu_via_click()
        click('#btnInfo')
        s = snap()
        check('menu item real click activates end-to-end and closes menu + tools overlay',
              s['display'] == 'none' and s['aria'] == 'false'
              and not s['toolsOpen'] and s['iaOpen'] is True, s)
        key('Escape'); time.sleep(.5)
        s = snap()
        check('reference index exits one layer on Escape', s['iaOpen'] is False and s['aria'] == 'false', s)
        open_menu_via_click()
        ox, oy = w * .5, h * .55
        b.mouse('mousePressed', ox, oy); b.mouse('mouseReleased', ox, oy); time.sleep(.4)
        s = snap()
        check('outside pointer collapses menu but keeps tools overlay',
              s['aria'] == 'false' and s['display'] == 'none' and s['toolsOpen'] is True, s)
        open_menu_via_click()
        b.mouse('mouseMoved', w * .5, h * .55); time.sleep(.3)
        hold = snap()
        if not (hold['aria'] == 'true' and hold['display'] == 'flex'):
            raise RuntimeError('focus-held menu did not stay open after pointer left the trigger: ' + json.dumps(hold))
        b.ev("document.getElementById('aphTools').focus();")
        time.sleep(.35); s = snap()
        check('focus leaving the menu collapses it (focusout)',
              s['aria'] == 'false' and s['display'] == 'none' and s['toolsOpen'] is True, s)
        s = snap()
        check('zoom checkbox mirrors checked into aria-checked, storage untouched yet',
              s['zoomChecked'] is True and s['zoomAria'] == 'true' and s['stored'] is None, s)
        open_menu_via_click()
        click('#opsZoom')
        s = snap()
        check('zoom real click flips to off, aria-checked mirrors, persists 0',
              s['zoomChecked'] is False and s['zoomAria'] == 'false' and s['stored'] == '0', s)
        trust = snap()['events']
        navigate('after-reload')
        s = snap()
        check('after a real page reload zoom stays off with aria in sync, stored 0',
              s['zoomChecked'] is False and s['zoomAria'] == 'false' and s['stored'] == '0', s)
        open_menu_via_click()
        click('#opsZoom')
        s = snap()
        check('zoom restored on, aria in sync, stored 1',
              s['zoomChecked'] is True and s['zoomAria'] == 'true' and s['stored'] == '1', s)
        trust = trust + snap()['events']
        check('every recorded input event is trusted CDP input',
              bool(trust) and all(e['trusted'] for e in trust), trust)
        output = io.StringIO()
        with redirect_stdout(output):
            code = headless.post_health(b.ws, [])
        rows = [x[13:] for x in output.getvalue().splitlines() if x.startswith('POST-HEALTH: ')]
        hh = json.loads(rows[0]) if len(rows) == 1 else None
        check('page health after full contract', code == 0 and hh is not None and hh.get('ok') is True, hh)
        try:
            check('Single unchanged source and data version', hashes() == source)
        except Exception as e:
            check('Source hash verification', False, {'error': str(e)})
    except Exception as exc:
        check('ops_more_menu session completed', False, {'error': str(exc)})
    finally:
        try:
            b.close()
        except Exception:
            pass
    ok = save()
    print('OPS-MORE-MENU ' + ('OK' if ok else 'FAIL') + ' ' + str(args.out / 'result.json'), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
