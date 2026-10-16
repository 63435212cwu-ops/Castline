#!/usr/bin/env python3
"""Native CDP touch / Tab / Enter / Space regression for sky reading controls.

Fresh profiles, normal entry without probe, actual production handlers. No model
requests, source changes, monkeypatches, synthetic DOM clicks or keydown events.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import sky_chaos as chaos

INPUTS = ['js/sky/sky-deck.js', 'js/sky/sky-deck-body.js',
          'js/sky/sky-shell-deck.js', 'js/sky/sky-field.js', 'css/views-status.css']
RECORD = r"""(()=>{
 window.__interactionAccessEvents=[];
 for(const type of ['keydown','keyup','pointerdown','pointerup','click','touchstart','touchend']){
  document.addEventListener(type,e=>{
   const t=e.target,owner=t&&t.closest&&t.closest('.skd-deck,.skd-drawerbtn,.sf-name,#skyPlot,#skyPlay,#runbar');
   if(!owner&&type!=='keydown'&&type!=='keyup')return;
   __interactionAccessEvents.push({type,key:e.key||null,trusted:e.isTrusted,target:t&&t.id||t&&t.className&&String(t.className)||'',
    owner:owner&&owner.id||owner&&owner.getAttribute('class')||null,at:performance.now()});
  },true);
 }
 return true;
})()"""
SNAP = r"""(()=>{
 const st=CLSky.state(),d=CLSky.deck(),vp=document.querySelector('.skd-deck__viewport'),root=vp&&vp.closest('.skd-deck'),
 a=document.activeElement,active=vp&&document.getElementById(vp.getAttribute('aria-activedescendant')),
 op=root&&root.querySelector('.skd-card.is-open'),body=op&&op.querySelector('.skd-card__body'),run=document.getElementById('runbar'),rp=run&&run.querySelector('.panel'),
 btn=document.querySelector('.skd-drawerbtn'),r=btn&&btn.getBoundingClientRect(),hit=r&&document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
 function visible(e){if(!e)return false;const r=e.getBoundingClientRect(),s=getComputedStyle(e);return !e.hidden&&r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&+s.opacity>0;}
 return {mode:st.mode,plot:st.plot,playing:st.playing,cursor:st.cursor,deck:d&&d.stats(),rootVisible:visible(root),bodyVisible:visible(body),
  focus:a&&a.id||a&&a.getAttribute('data-act')||a&&a.getAttribute('class'),focusInViewport:!!(vp&&a===vp),
  activeId:active&&active.id,activeMounted:!!(active&&vp.contains(active)),activeKey:active&&active.dataset.key,
  position:active&&+active.getAttribute('aria-posinset'),size:active&&+active.getAttribute('aria-setsize'),selected:active&&active.getAttribute('aria-selected'),
  options:root?Array.from(root.querySelectorAll('[role=option]')).map(e=>({id:e.id,key:e.dataset.key,pos:+e.getAttribute('aria-posinset'),size:+e.getAttribute('aria-setsize'),selected:e.getAttribute('aria-selected')})):[],
  drawerExpanded:btn&&btn.getAttribute('aria-expanded'),drawerHit:hit&&(hit.id||hit.getAttribute('class')),drawerHitOwned:!!(btn&&hit&&(hit===btn||btn.contains(hit))),
  runbar:{on:run&&run.classList.contains('on'),opacity:run&&getComputedStyle(run).opacity,visibility:run&&getComputedStyle(run).visibility,panelPointer:rp&&getComputedStyle(rp).pointerEvents},
  nativeEvents:__interactionAccessEvents.slice(-40)};
})()"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8123')
    p.add_argument('--data', default='data/sample-saga.json')
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--mobile-only', action='store_true')
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=False)
    source = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    checks, sessions = [], []

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            raise AssertionError(name + ': ' + json.dumps(detail, ensure_ascii=False))

    def key(b, k, shift=False):
        if k in ('Tab', 'Home', 'End', 'Enter', ' '):
            for typ in ('keyDown', 'keyUp'):
                params = {'type': typ, 'key': k, 'code': 'Space' if k == ' ' else k,
                          'windowsVirtualKeyCode': {'Tab': 9, 'Home': 36, 'End': 35, 'Enter': 13, ' ': 32}[k], 'modifiers': 8 if shift else 0}
                if typ == 'keyDown' and k in ('Enter', ' '):
                    params.update(text='\r' if k == 'Enter' else ' ', unmodifiedText='\r' if k == 'Enter' else ' ')
                b.ws.call('Input.dispatchKeyEvent', **params)
        else:
            b.key(k, shift)
        time.sleep(.15)

    def point(b, selector):
        return b.ev("(()=>{const e=document.querySelector(" + json.dumps(selector) + r"""),r=e&&e.getBoundingClientRect();
         if(!r||r.width<=0||r.height<=0)throw Error('No visible target');
         const x=r.x+r.width/2,y=r.y+r.height/2,h=document.elementFromPoint(x,y);
         return {x,y,owned:!!(h&&(h===e||e.contains(h))),hit:h&&(h.id||h.getAttribute('class')),rect:{x:r.x,y:r.y,w:r.width,h:r.height}};
        })()""")

    def activate(b, selector, mobile, tag):
        pt = point(b, selector)
        check(tag + ' target owns hit point', pt['owned'], pt)
        if mobile:
            b.ws.call('Input.dispatchTouchEvent', type='touchStart', touchPoints=[{'x': pt['x'], 'y': pt['y'], 'id': 1, 'radiusX': 3, 'radiusY': 3, 'force': 1}])
            time.sleep(.06)
            b.ws.call('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])
        else:
            b.mouse('mouseMoved', pt['x'], pt['y'])
            b.mouse('mousePressed', pt['x'], pt['y'])
            b.mouse('mouseReleased', pt['x'], pt['y'])
        time.sleep(.35)

    def tab_until(b, predicate, limit=80):
        for _ in range(limit):
            if b.ev(predicate):
                return True
            key(b, 'Tab')
        return False

    def shot(b, filename):
        raw = b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
        (args.out / filename).write_bytes(base64.b64decode(raw['data']))

    def accessibility_node(b, selector):
        b.ws.call('Accessibility.enable')
        doc = b.ws.call('DOM.getDocument')
        n = b.ws.call('DOM.querySelector', nodeId=doc['root']['nodeId'], selector=selector)
        if not n.get('nodeId'):
            raise RuntimeError('No accessibility target: ' + selector)
        return b.ws.call('Accessibility.getPartialAXTree', nodeId=n['nodeId'], fetchRelatives=False)['nodes']

    sizes = [(390, 844, True)] if args.mobile_only else [(1600, 1000, False), (390, 844, True)]
    for w, h, mobile in sizes:
        tag = 'mobile' if mobile else 'desktop'
        b = chaos.Browser(w, h)
        row = {'size': [w, h], 'mobile': mobile, 'data': args.data}
        sessions.append(row)
        try:
            b.start()
            if mobile:
                b.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=1, mobile=True)
                b.ws.call('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=1)
            b.ws.call('Page.navigate', url=args.base.rstrip('/') + '/?data=' + args.data)
            if not b.until("!!(window.CLApp&&CLApp.scene()&&CLApp.graph()&&window.CLSky&&CLSky.enabled()&&window.CLSkyDeep&&CLSkyDeep.enabled()&&CLSkyDeep.stats().stars.ignite>.99)", 60):
                raise RuntimeError('Production graph did not become ready')
            time.sleep(1)
            b.ev(RECORD)
            entry = b.ev("({query:location.search,probe:new URLSearchParams(location.search).has('probe')})")
            check(tag + ' normal entry has no probe parameter', not entry['probe'], entry)

            if not mobile:
                camp_selector = '.sky-field .sf-name[tabindex="0"][aria-hidden="false"]'
                check('camp keyboard focus is reachable', tab_until(b, "!!(document.activeElement&&document.activeElement.matches(" + json.dumps(camp_selector) + '))'), b.ev('document.activeElement&&document.activeElement.outerHTML'))
                camp = b.ev("document.activeElement.querySelector('.sf-n').textContent")
                ax = accessibility_node(b, camp_selector + ':focus')
                check('camp is an exposed named accessibility button', bool(ax) and not ax[0].get('ignored') and ax[0].get('role', {}).get('value') == 'button' and camp in ax[0].get('name', {}).get('value', ''), ax)
                key(b, 'Enter')
                check('camp Enter selects the actual group', b.ev('CLApp.scene().campSel()') == camp, {'camp': camp, 'selection': b.ev('CLApp.scene().campSel()')})
                key(b, 'Enter')

            activate(b, '#skyPlot', mobile, tag + ' plot button')
            check(tag + ' plot opens', b.until('CLSky.state().plot && !!CLSky.deck()', 5), b.ev('CLSky.state()'))
            time.sleep(1)
            hidden_names = b.ev("Array.from(document.querySelectorAll('.sky-field .sf-name')).every(e=>e.getAttribute('tabindex')==='-1'&&e.getAttribute('aria-hidden')==='true')")
            check(tag + ' hidden camp controls leave keyboard tree', hidden_names, True)
            if mobile:
                before = b.ev(SNAP)
                check('hidden runbar does not intercept drawer', before['drawerHitOwned'] and before['runbar']['visibility'] == 'hidden' and before['runbar']['panelPointer'] == 'none', before)
                activate(b, '.skd-drawerbtn', True, 'mobile drawer button')
                check('touch opens the real mobile drawer', b.until('CLSky.deck().stats().shown', 3), b.ev(SNAP))
            time.sleep(.5)
            activate(b, '.skd-deck .skd-card__bar', mobile, tag + ' card title')
            snap = b.ev(SNAP)
            check(tag + ' selected card remains readable', snap['rootVisible'] and snap['bodyVisible'] and bool(snap['deck']['open']) and (not mobile or snap['drawerExpanded'] == 'true'), snap)
            shot(b, tag + '-readable-card.png')

            check(tag + ' native Tab reaches playback button', tab_until(b, "document.activeElement&&document.activeElement.matches('.skd-card.is-open [data-act=play]')"), b.ev(SNAP))
            playback_ax = accessibility_node(b, '.skd-card.is-open [data-act=play]')
            check(tag + ' playback action is an exposed accessibility button', bool(playback_ax) and not playback_ax[0].get('ignored') and playback_ax[0].get('role', {}).get('value') == 'button' and '播放' in playback_ax[0].get('name', {}).get('value', ''), playback_ax)
            before = b.ev(SNAP)
            key(b, 'Enter')
            after = b.ev(SNAP)
            check(tag + ' Enter on playback button plays without closing card', after['playing'] and after['deck']['open'] == before['deck']['open'] and after['rootVisible'] and after['bodyVisible'], after)
            key(b, 'Tab')
            check(tag + ' next Tab reaches seek button', b.ev("document.activeElement&&document.activeElement.matches('.skd-card.is-open [data-act=seek]')"), b.ev(SNAP))
            key(b, ' ')
            after = b.ev(SNAP)
            check(tag + ' Space on seek button seeks and stops without closing card', not after['playing'] and after['cursor'] is not None and after['deck']['open'] == before['deck']['open'] and after['bodyVisible'], after)
            key(b, 'Escape')
            snap = b.ev(SNAP)
            check(tag + ' Escape closes card and returns list focus', snap['deck']['open'] is None and snap['focusInViewport'] and snap['rootVisible'], snap)

            key(b, 'Home')
            first = b.ev(SNAP)
            key(b, 'ArrowDown')
            second = b.ev(SNAP)
            check(tag + ' active descendant follows real arrow navigation', first['activeMounted'] and first['position'] == 1 and second['activeMounted'] and second['position'] == 2 and second['activeId'] != first['activeId'], {'first': first, 'second': second})
            key(b, 'End')
            last = b.ev(SNAP)
            check(tag + ' virtual final option remains mounted with full position', last['activeMounted'] and last['position'] == last['size'] and last['size'] > 2, last)
            key(b, 'Home')
            key(b, 'Enter')
            selected = b.ev(SNAP)
            check(tag + ' selected option has accessible single selection', selected['selected'] == 'true' and sum(o['selected'] == 'true' for o in selected['options']) == 1 and all(o['size'] == selected['size'] and 1 <= o['pos'] <= o['size'] for o in selected['options']), selected)
            key(b, 'Escape')
            activate(b, '.skd-deck__filter [data-f=main]', mobile, tag + ' main filter')
            filtered = b.ev(SNAP)
            check(tag + ' filtered virtual positions use filtered total', filtered['activeMounted'] and filtered['position'] == 1 and filtered['size'] == filtered['deck']['mains'] and all(o['size'] == filtered['size'] for o in filtered['options']), filtered)
            activate(b, '.skd-deck__filter [data-f=all]', mobile, tag + ' all filter')
            if mobile:
                key(b, 'Escape')
                closed = b.ev(SNAP)
                check('second Escape closes drawer and returns handle focus', not closed['rootVisible'] and closed['focus'] == 'skd-drawerbtn' and closed['plot'], closed)

            b.ev("CLRunbar.set({type:'analysis',stage:'离线交互回归',meta:'仅显示界面',percent:.5})")
            time.sleep(.5)
            run_on = b.ev("(()=>{const e=document.getElementById('runbar'),p=e.querySelector('.panel');return {on:e.classList.contains('on'),visibility:getComputedStyle(e).visibility,pointer:getComputedStyle(p).pointerEvents}})()")
            check(tag + ' running HUD remains interactive when shown', run_on['on'] and run_on['visibility'] == 'visible' and run_on['pointer'] == 'auto', run_on)
            b.ev("CLRunbar.close('analysis')")
            time.sleep(.5)
            end = b.ev(SNAP)
            check(tag + ' closed HUD has no invisible interactive descendants', end['runbar']['visibility'] == 'hidden' and end['runbar']['panelPointer'] == 'none', end)
            check(tag + ' input evidence uses trusted browser events', bool(end['nativeEvents']) and all(e['trusted'] for e in end['nativeEvents']), end['nativeEvents'])
            health = b.ev("(()=>{const h=window.__headlessHealth,S=CLApp.scene(),d=S.digest();return {errors:h.jserr,rejections:h.jsrej,shaderErrors:S.shaderErrors(),frameErrors:d.frameHooks&&d.frameHooks.errors||0}})()")
            check(tag + ' runtime remains healthy', not health['errors'] and not health['rejections'] and not health['shaderErrors'] and not health['frameErrors'], health)
            row.update({'ok': True, 'final': end, 'health': health})
        except Exception as exc:
            row.update({'ok': False, 'error': str(exc)})
            print('FAIL ' + tag + ' session: ' + str(exc), flush=True)
            try:
                shot(b, tag + '-failure.png')
                row['failureState'] = b.ev(SNAP)
            except Exception:
                pass
        finally:
            b.close()

    stable = source == {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    ok = stable and all(s.get('ok') for s in sessions) and bool(checks) and all(c['ok'] for c in checks)
    report = {'ok': ok, 'complete': True, 'base': args.base, 'sourceStable': stable, 'sourceHashes': source,
              'checks': checks, 'sessions': sessions, 'finishedAt': datetime.now(timezone.utc).isoformat(),
              'boundary': 'Fresh profiles, no probe. Native CDP touch/mouse/Tab/Enter/Space; no DOM event synthesis or handler replacement. HUD set/close only displays UI; no model request.'}
    (args.out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('SKY INTERACTION ACCESS ' + ('PASS' if ok else 'FAIL'), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
