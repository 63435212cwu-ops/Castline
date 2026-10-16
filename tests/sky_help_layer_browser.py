#!/usr/bin/env python3
"""Help layer (? overlay) acceptance for the sky shell — real Chrome via CDP.

Normal data-URL entry, no probe parameter. Native CDP keyboard (Shift+/ and
Escape) and native mouse for the toolbar button path; the public CLSky /
CLKeys surfaces are used only to reach a state (compass) the same way the
existing a11y story test does — no monkeypatching, no synthetic DOM events.

Covers: dialog semantics (role / aria-modal / named heading), focus entering
the dialog on open and returning to the trigger on Escape, the three content
sections being driven by the live registry (row parity + disabled keys not
listed), view-specific paragraphs across constellation / plot / compass,
the narrow-viewport (<=560px) layout, and no transitions under reduced motion.
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
import urllib.parse

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import sky_chaos as chaos

INPUTS = ['js/keys.js', 'js/sky/sky-shell.js']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8123')
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=False)
    source = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    checks = []

    def check(name, expression):
        value = b.ev(expression)
        ok = value is True
        checks.append({'name': name, 'ok': ok, 'actual': value})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            raise AssertionError(name + ': ' + json.dumps(value, ensure_ascii=False))

    def key_event(k, code, vk, text=None):
        for typ in ('keyDown', 'keyUp'):
            data = {'type': typ, 'key': k, 'code': code, 'windowsVirtualKeyCode': vk}
            if typ == 'keyDown' and text is not None:
                data.update(text=text, unmodifiedText=text)
                if text == '?':
                    data.update(modifiers=8)
            b.ws.call('Input.dispatchKeyEvent', **data)
        time.sleep(.25)

    def shift_question():
        key_event('?', 'Slash', 191, text='?')

    def escape():
        key_event('Escape', 'Escape', 27)

    def point(selector):
        return b.ev("(()=>{const e=document.querySelector(" + json.dumps(selector) + "),r=e&&e.getBoundingClientRect();"
                    "if(!r||r.width<=0||r.height<=0)throw Error('No visible target: '+" + json.dumps(selector) + ");"
                    "const x=r.x+r.width/2,y=r.y+r.height/2,h=document.elementFromPoint(x,y);"
                    "return {x:x,y:y,owned:!!(h&&(h===e||e.contains(h)))};})()")

    def activate(selector, tag):
        pt = point(selector)
        if not pt['owned']:
            raise AssertionError(tag + ' does not own its hit point: ' + json.dumps(pt, ensure_ascii=False))
        b.mouse('mouseMoved', pt['x'], pt['y'])
        b.mouse('mousePressed', pt['x'], pt['y'])
        b.mouse('mouseReleased', pt['x'], pt['y'])
        time.sleep(.4)

    open_ready = "!!(window.CLKeys&&CLKeys.panelOn())"
    help_open = "(()=>{const p=document.getElementById('clKeys');return p.getAttribute('role')==='dialog'" \
                "&&p.getAttribute('aria-modal')==='true'" \
                "&&(t=>!!t&&t.tagName==='H2'&&t.textContent.length>2)(document.getElementById(p.getAttribute('aria-labelledby')))" \
                "&&p.contains(document.activeElement)})()"
    registry_parity = "(()=>{const m=CLKeys.helpModel(),rows=document.querySelectorAll('#clKeys .kr').length," \
                      "n=m.groups.reduce((a,g)=>a+g.entries.length,0);return rows===n&&n>10})()"
    disabled_absent = "(()=>{const dead=CLKeys.map.filter(m=>!CLKeys.alive(m))," \
                      "names=Array.from(document.querySelectorAll('#clKeys .kn')).map(n=>n.textContent);" \
                      "return dead.every(m=>!names.some(t=>t.indexOf(m.label)>=0))})()"
    panels_parity = "(()=>{const m=CLKeys.helpModel();return m.panels.length>=3" \
                    "&&document.querySelectorAll('#clKeys .kp li').length===m.panels.length})()"

    graph = {'title': '帮助层验收', 'characters': [
        {'id': 'c-a', 'name': '测试甲', 'role': '主角', 'importance': 90, 'camp': '同组', 'attrs': {}},
        {'id': 'c-b', 'name': '测试乙', 'role': '配角', 'importance': 70, 'camp': '同组', 'attrs': {}}],
        'events': [
            {'id': 'a', 'order': 1, 'chapter': '第一章', 'title': '发现锁门', 'summary': '门已锁住，需要找到钥匙。', 'kind': '日常', 'characters': ['测试甲']},
            {'id': 'b', 'order': 2, 'chapter': '第一章', 'title': '找到钥匙', 'summary': '测试甲找到钥匙并交给测试乙。', 'kind': '转折', 'characters': ['测试甲', '测试乙']},
            {'id': 'c', 'order': 3, 'chapter': '第二章', 'title': '开门救人', 'summary': '测试乙用钥匙打开门。', 'kind': '高燃', 'characters': ['测试乙']}],
        'causeEdges': [{'id': 'e-ab', 'fromEventId': 'a', 'toEventId': 'b', 'resolved': True, 'description': '因为门锁住了才会找钥匙'}],
        'relations': [], 'tasks': []}
    raw = json.dumps(graph, ensure_ascii=False).encode()
    url = args.base.rstrip('/') + '/?data=' + urllib.parse.quote('data:application/json;base64,' + base64.b64encode(raw).decode(), safe='')
    b = chaos.Browser(1440, 900)
    session = {'ok': False, 'checks': 0}
    try:
        b.start()
        b.ws.call('Page.navigate', url=url)
        if not b.until("!!(window.CLApp&&CLApp.graph()&&CLApp.graph().events.length===3&&window.CLSky&&CLSky.enabled()"
                       "&&CLSky.model()&&CLSky.model().ok&&window.CLKeys&&document.querySelector('#loader.off')&&document.getElementById('skyHelp'))", 60):
            raise RuntimeError('Normal graph entry failed')
        time.sleep(2)
        b.ev("window.__helpInput=[];['keydown','keyup','click'].forEach(t=>document.addEventListener(t,e=>__helpInput.push({type:t,key:e.key||null,trusted:e.isTrusted}),true))")
        check('normal entry carries no probe parameter', "!new URLSearchParams(location.search).has('probe')")
        check('a real toolbar help button is mounted inside the top-bar actions',
              "(()=>{const b=document.getElementById('skyHelp');return b.tagName==='BUTTON'" \
              "&&b.closest('.sky-actions')!==null&&b.getAttribute('aria-label').length>4})()")

        b.ev("document.activeElement&&document.activeElement.blur&&document.activeElement.blur()")
        shift_question()
        if not b.until(open_ready, 4):
            raise AssertionError('Shift+/ did not open the help layer through a real keypress')
        if not b.until(help_open, 4):
            raise AssertionError('help layer semantics/focus incomplete: ' + json.dumps(b.ev(
                "({role:document.getElementById('clKeys').getAttribute('role'),modal:document.getElementById('clKeys').getAttribute('aria-modal'),"
                "focus:document.activeElement&&(document.activeElement.id||document.activeElement.className)})"), ensure_ascii=False))
        check('Shift+/ opens a labelled modal dialog and focus lands inside it', help_open)
        check('constellation section is visible and driven by the live view state',
              "document.querySelector('#clKeys .kv').dataset.view==='constellation'")
        check('every shortcut row mirrors an alive registry entry', registry_parity)
        check('disabled shortcuts are not listed', disabled_absent)
        check('panel-reachability lines match the live DOM probes', panels_parity)
        constellation_lines = b.ev("Array.from(document.querySelectorAll('#clKeys .kv li')).map(li=>li.textContent).join('|')")
        escape()
        if not b.until("!CLKeys.panelOn()&&document.activeElement===document.body", 4):
            raise AssertionError('Escape did not close the layer and return focus to the page (body)')
        check('Escape closes the layer and focus returns to where the key was pressed',
              "!CLKeys.panelOn()&&document.activeElement===document.body")

        activate('#skyHelp', 'toolbar help button')
        if not b.until(open_ready, 4):
            raise AssertionError('toolbar help button did not open the layer')
        check('the button path lands focus inside the dialog', help_open)
        escape()
        if not b.until("!CLKeys.panelOn()&&document.activeElement.id==='skyHelp'", 4):
            raise AssertionError('focus was not returned to the help button: ' + json.dumps(b.ev(
                "document.activeElement&&(document.activeElement.id||String(document.activeElement.className))"), ensure_ascii=False))
        check('Escape returns focus to the toolbar button that opened the layer',
              "!CLKeys.panelOn()&&document.activeElement.id==='skyHelp'")

        activate('#skyPlot', 'plot button')
        if not b.until('CLSky.state().plot===true', 5):
            raise AssertionError('plot mode did not engage')
        shift_question()
        if not b.until(open_ready, 4):
            raise AssertionError('help layer did not reopen in plot mode')
        check('plot mode shows a different view paragraph',
              "(()=>{const v=document.querySelector('#clKeys .kv');return v.dataset.view==='plot'"
              "&&Array.from(v.querySelectorAll('li')).some(li=>/播放/.test(li.textContent))})()")
        plot_lines = b.ev("Array.from(document.querySelectorAll('#clKeys .kv li')).map(li=>li.textContent).join('|')")
        check('the plot paragraph really differs from the constellation one',
              json.dumps(plot_lines != constellation_lines and '||' not in plot_lines))
        escape()
        if not b.until("!CLKeys.panelOn()&&CLSky.state().plot===true", 4):
            raise AssertionError('Escape tore down more than the help layer (plot must stay on)')
        check('Escape closes only the help layer — plot mode survives',
              "!CLKeys.panelOn()&&CLSky.state().plot===true")

        b.ev("CLSky.openCompass('测试甲')")
        if not b.until("CLSky.state().mode==='compass'", 10):
            raise AssertionError('compass did not open through the public CLSky surface')
        shift_question()
        if not b.until(open_ready, 4):
            raise AssertionError('help layer did not reopen in compass mode')
        check('compass mode names the real character and offers compass-only moves',
              "(()=>{const v=document.querySelector('#clKeys .kv');return v.dataset.view==='compass'"
              "&&v.querySelector('h3').textContent.indexOf('测试甲')>=0"
              "&&Array.from(v.querySelectorAll('li')).some(li=>/返回星座/.test(li.textContent))})()")
        compass_lines = b.ev("Array.from(document.querySelectorAll('#clKeys .kv li')).map(li=>li.textContent).join('|')")
        check('the compass paragraph differs from both earlier paragraphs',
              json.dumps(compass_lines != constellation_lines and compass_lines != plot_lines))
        check('registry parity still holds after view switches', registry_parity)
        escape()
        if not b.until("!CLKeys.panelOn()", 4):
            raise AssertionError('help layer did not close in compass mode')
        b.ev('CLSky.closeCompass()')
        if not b.until("CLSky.state().mode!=='compass'", 10):
            raise AssertionError('did not return from compass')

        b.size(390, 760)
        time.sleep(.6)
        shift_question()
        if not b.until(open_ready, 4):
            raise AssertionError('help layer did not open at 390px')
        check('at 390px the dialog stays inside the viewport without horizontal overflow',
              "(()=>{const r=document.querySelector('#clKeys .kx').getBoundingClientRect();" \
              "return r.x>=-0.5&&r.right<=innerWidth+0.5&&document.scrollingElement.scrollWidth<=innerWidth+1})()")
        check('at 390px the three sections are all present in a single column',
              "(()=>{const m=CLKeys.helpModel();return document.querySelectorAll('#clKeys .kr').length>10" \
              "&&document.querySelectorAll('#clKeys .kp li').length===m.panels.length" \
              "&&document.querySelector('#clKeys .kv li')!==null})()")
        escape()

        check('by default the layer animates its transition',
              "getComputedStyle(document.getElementById('clKeys')).transitionDuration!=='0s'")
        b.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])
        shift_question()
        if not b.until(open_ready, 4):
            raise AssertionError('help layer did not open under reduced motion')
        check('under prefers-reduced-motion the layer has no transition at all',
              "getComputedStyle(document.getElementById('clKeys')).transitionDuration==='0s'" \
              "&&getComputedStyle(document.querySelector('#clKeys .kx')).transitionDuration==='0s'")
        escape()
        b.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': ''}])

        check('input evidence uses trusted browser events', "__helpInput.length>0&&__helpInput.every(e=>e.trusted)")
        check('runtime remains healthy after the full help walk',
              "__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0")
        session.update({'ok': True, 'checks': len(checks)})
    except Exception as exc:
        session['error'] = str(exc)
        try:
            raw = b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
            (args.out / 'failure.png').write_bytes(base64.b64decode(raw['data']))
        except Exception:
            pass
        print('FAIL session: ' + str(exc), flush=True)
    finally:
        b.close()
    stable = source == {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    ok = stable and session['ok'] and all(c['ok'] for c in checks)
    report = {'ok': ok, 'complete': True, 'base': args.base, 'sourceStable': stable, 'sourceHashes': source,
              'checks': checks, 'finishedAt': datetime.now(timezone.utc).isoformat(),
              'boundary': 'Normal entry, no probe. Native CDP keyboard/mouse for all help-layer interactions; '
                          'public CLSky API only for reach-the-state setup (compass).'}
    (args.out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('SKY HELP LAYER ' + ('PASS' if ok else 'FAIL'), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
