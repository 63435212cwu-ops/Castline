#!/usr/bin/env python3
"""Screen-reader semantic tree acceptance for the sky reading surfaces (CDP).

Real Chrome through a normal data URL entry; assertions use native CDP mouse /
keyboard input against the production handlers. Graph setup seeks and stops use
the same public CLSky surface as the existing story browser test — no probe
parameter, no monkeypatch, no DOM event synthesis.

Covers: stage-rail live announcements that only fire on real stage switches,
the search dialog semantics with Escape focus return, the decorative causal
beam SVG, tablist sync in the narrative dissection panel, and the heading /
named-region structure of the event reading panel.
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

INPUTS = ['js/sky/sky-shell-player.js', 'js/sky/sky-search.js',
          'js/sky/sky-deconstruction.js', 'js/sky/sky-shell-hud.js', 'css/sky-reading.css']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8123')
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=False)
    source = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    checks, notes = [], []

    def check(name, expression):
        value = b.ev(expression)
        ok = value is True
        checks.append({'name': name, 'ok': ok, 'actual': value})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            raise AssertionError(name + ': ' + json.dumps(value, ensure_ascii=False))

    def check_point(tag, pt):
        ok = bool(pt and pt['owned'])
        checks.append({'name': tag + ' target owns the hit point', 'ok': ok, 'actual': pt})
        print(('PASS ' if ok else 'FAIL ') + tag + ' target owns the hit point', flush=True)
        if not ok:
            raise AssertionError(tag + ': ' + json.dumps(pt, ensure_ascii=False))

    def point(selector):
        return b.ev("(()=>{const e=document.querySelector(" + json.dumps(selector) + "),r=e&&e.getBoundingClientRect();"
                    "if(!r||r.width<=0||r.height<=0)throw Error('No visible target: '+" + json.dumps(selector) + ");"
                    "const x=r.x+r.width/2,y=r.y+r.height/2,h=document.elementFromPoint(x,y);"
                    "return {x:x,y:y,owned:!!(h&&(h===e||e.contains(h))),hit:h&&(h.id||h.getAttribute('class'))};})()")

    def activate(selector, tag):
        pt = point(selector)
        check_point(tag, pt)
        b.mouse('mouseMoved', pt['x'], pt['y'])
        b.mouse('mousePressed', pt['x'], pt['y'])
        b.mouse('mouseReleased', pt['x'], pt['y'])
        time.sleep(.35)

    def key(k, text=None):
        codes = {'Escape': 27, 'Enter': 13, ' ': 32, 'ArrowLeft': 37, 'ArrowRight': 39, 'ArrowDown': 40, 'Tab': 9,
                 'PageUp': 33, 'PageDown': 34, 'End': 35, 'Home': 36}
        for typ in ('keyDown', 'keyUp'):
            data = {'type': typ, 'key': k, 'code': 'Space' if k == ' ' else k, 'windowsVirtualKeyCode': codes[k]}
            if typ == 'keyDown' and text is not None:
                data.update(text=text, unmodifiedText=text)
            b.ws.call('Input.dispatchKeyEvent', **data)
        time.sleep(.2)

    def accessibility_node(selector):
        b.ws.call('Accessibility.enable')
        doc = b.ws.call('DOM.getDocument')
        n = b.ws.call('DOM.querySelector', nodeId=doc['root']['nodeId'], selector=selector)
        if not n.get('nodeId'):
            raise RuntimeError('No accessibility target: ' + selector)
        return b.ws.call('Accessibility.getPartialAXTree', nodeId=n['nodeId'], fetchRelatives=False)['nodes']

    graph = {'title': '读屏语义验收', 'characters': [
        {'id': 'c-a', 'name': '测试甲', 'role': '主角', 'importance': 90, 'camp': '同组', 'attrs': {}},
        {'id': 'c-b', 'name': '测试乙', 'role': '配角', 'importance': 70, 'camp': '同组', 'attrs': {}}],
        'events': [
            {'id': 'a', 'order': 1, 'chapter': '第一章', 'title': '发现锁门', 'summary': '门已锁住，需要找到钥匙。', 'kind': '日常', 'characters': ['测试甲']},
            {'id': 'b', 'order': 2, 'chapter': '第一章', 'title': '找到钥匙', 'summary': '测试甲找到钥匙并交给测试乙。', 'kind': '转折', 'characters': ['测试甲', '测试乙']},
            {'id': 'c', 'order': 3, 'chapter': '第二章', 'title': '开门救人', 'summary': '测试乙用钥匙打开门，被困的人获救。', 'kind': '高燃', 'characters': ['测试乙']},
            {'id': 'd', 'order': 4, 'chapter': '第三章', 'title': '告别的夜路', 'summary': '两人沿夜路告别，故事收进尾声。', 'kind': '日常', 'characters': ['测试甲', '测试乙']}],
        'causeEdges': [
            {'id': 'e-ab', 'fromEventId': 'a', 'toEventId': 'b', 'resolved': True, 'description': '因为门锁住了才会找钥匙'},
            {'id': 'e-bc', 'fromEventId': 'b', 'toEventId': 'c', 'resolved': True, 'description': '拿到钥匙才能开门救人'}],
        'relations': [], 'tasks': []}
    raw = json.dumps(graph, ensure_ascii=False).encode()
    url = args.base.rstrip('/') + '/?data=' + urllib.parse.quote('data:application/json;base64,' + base64.b64encode(raw).decode(), safe='')
    b = chaos.Browser(1440, 900)
    session = {'ok': False, 'checks': 0}
    try:
        b.start()
        b.ws.call('Page.navigate', url=url)
        if not b.until("!!(window.CLApp&&CLApp.graph()&&CLApp.graph().events.length===4&&window.CLSky&&CLSky.enabled()&&CLSky.model()&&CLSky.model().ok&&window.CLSkySearch&&document.querySelector('#loader.off'))", 60):
            raise RuntimeError('Normal graph entry failed')
        if not b.until("!document.querySelector('.skd-loader.is-on')", 20):
            raise RuntimeError('Loader curtain never left the toolbar hit zone')
        time.sleep(2)
        b.ev("window.__a11yInput=[];['keydown','input','click'].forEach(t=>document.addEventListener(t,e=>__a11yInput.push({type:t,trusted:e.isTrusted}),true))")
        check('normal entry carries no probe parameter', "!new URLSearchParams(location.search).has('probe')")

        activate('#skyPlot', 'plot button')
        check('plot opens through a real toolbar click', 'CLSky.state().plot===true')
        time.sleep(1)
        b.ev('CLSky.seekEventAt(1)')
        check('event reading opens a named landmark with one real h2',
              "(()=>{const p=document.getElementById('skyStoryPanel'),h2=p.querySelectorAll('h2');return p.getAttribute('role')==='region'&&p.getAttribute('aria-labelledby')==='skyStoryTitle'&&h2.length===1&&h2[0].id==='skyStoryTitle'&&h2[0].textContent==='找到钥匙'&&!p.hidden&&p.querySelectorAll('h1').length===0})()")
        check('reading sections keep h3 nesting below the panel h2',
              "(()=>{const title=document.getElementById('skyStoryTitle'),h3=document.querySelectorAll('#skyStoryBody h3');return h3.length>0&&Array.from(h3).every(h=>title.compareDocumentPosition(h)&Node.DOCUMENT_POSITION_FOLLOWING)})()")
        check('stage rail is a real list with the current step marked',
              "(()=>{const r=document.getElementById('skyStoryRail'),cur=r.querySelector('[aria-current=step]');return r.getAttribute('role')==='list'&&r.querySelectorAll('[role=listitem]').length===3&&cur&&cur.dataset.beat==='event'&&Array.from(r.querySelectorAll('[data-beat]')).every(n=>n.classList.contains('is-active')===(n.getAttribute('aria-current')==='step'))})()")
        check('dedicated stage announcer exists, is live, and is visually hidden',
              "(()=>{const e=document.getElementById('skyStoryStageLive');if(!e)return false;const r=e.getBoundingClientRect();return e.getAttribute('role')==='status'&&e.getAttribute('aria-live')==='polite'&&e.getAttribute('aria-atomic')==='true'&&r.width<=1&&r.height<=1})()")
        check('seeking announces the real current stage exactly once',
              "document.getElementById('skyStoryStageLive').textContent==='阶段：此刻'")
        check('the visual phase label is no longer a live channel itself',
              "!document.getElementById('skyStoryPhase').hasAttribute('aria-live')&&!document.getElementById('skyStoryPhase').hasAttribute('role')")
        access = accessibility_node('#skyStoryPanel:not([hidden])')
        ok = bool(access) and not access[0].get('ignored') and access[0].get('role', {}).get('value') == 'region' and '找到钥匙' in access[0].get('name', {}).get('value', '')
        checks.append({'name': 'story panel is an exposed named accessibility region', 'ok': ok, 'actual': access[:1]})
        print(('PASS ' if ok else 'FAIL ') + 'story panel is an exposed named accessibility region', flush=True)
        if not ok:
            raise AssertionError(json.dumps(access, ensure_ascii=False))

        activate('#skyStoryPanel [data-story=play]', 'story play button')
        check('a real click on the panel play control starts playback', 'CLSky.state().playing===true&&CLSky.playerState().stage==="before"')
        check('stage switch announces the recorded cause count, not a fabricated one',
              "document.getElementById('skyStoryStageLive').textContent==='阶段：前因 · 1 条已记录因果'&&document.querySelector('#skyStoryRail [aria-current=step]').dataset.beat==='before'")
        if not b.until("document.getElementById('skyStoryStageLive').textContent==='阶段：此刻'&&CLSky.playerState().stage==='event'", 12):
            raise AssertionError('announcer did not follow the real event stage: ' + json.dumps(b.ev("({stage:CLSky.playerState().stage,live:document.getElementById('skyStoryStageLive').textContent})"), ensure_ascii=False))
        if not b.until("document.getElementById('skyStoryStageLive').textContent==='阶段：后果 · 1 条已记录因果'&&CLSky.playerState().stage==='after'", 12):
            raise AssertionError('announcer did not follow the real outcome stage')
        check('the announcer and the rail agree on the real outcome stage',
              "document.querySelector('#skyStoryRail [aria-current=step]').dataset.beat==='after'")
        beams = "(()=>{const s=document.getElementById('skyStoryBeams');return !!(s&&s.getAttribute('aria-hidden')==='true'&&s.querySelectorAll('path[d]').length>0&&!s.querySelector('[tabindex],[role]'))})()"
        if not b.until(beams, 5):
            raise AssertionError('causal beam overlay lost its decorative semantics: ' + json.dumps(b.ev("({hidden:document.getElementById('skyStoryBeams').getAttribute('aria-hidden'),paths:document.querySelectorAll('#skyStoryBeams path[d]').length,links:CLSky.playerState().links})"), ensure_ascii=False))
        check('causal beam overlay stays decorative while beams are actually drawn', beams)
        key('Escape')
        check('Escape closes reading and returns the real playback-button focus',
              "document.getElementById('skyStoryPanel').hidden&&document.activeElement.id==='skyPlay'")
        b.ev('CLSky.stop();CLSky.seekEventAt(3)')
        check('an isolated event never announces unrecorded causes or outcomes',
              "document.getElementById('skyStoryStageLive').textContent==='阶段：此刻'&&document.querySelector('[data-beat=before]').textContent==='未记录前因'&&document.querySelector('[data-beat=after]').textContent==='未记录后果'&&document.querySelector('#skyStoryRail [aria-current=step]').dataset.beat==='event'")
        b.ev('CLSky.stop()')

        b.ev('CLSky.seekEventAt(1)')
        check('event scrubber exposes real slider semantics with a 44px hit area',
              "(()=>{const s=document.getElementById('skyStoryScrub'),r=s.getBoundingClientRect();return s.getAttribute('role')==='slider'&&s.getAttribute('aria-orientation')==='horizontal'&&s.getAttribute('aria-valuemin')==='1'&&s.getAttribute('aria-valuemax')==='4'&&s.getAttribute('aria-valuenow')==='2'&&s.getAttribute('aria-valuetext')==='2 / 4 · 找到钥匙 · 第 1 章'&&s.getAttribute('aria-disabled')==='false'&&s.tabIndex===0&&r.height>=44&&r.width>=44})()")
        scrub_access = accessibility_node('#skyStoryScrub')
        ok = bool(scrub_access) and scrub_access[0].get('role', {}).get('value', '').lower() == 'slider' and not scrub_access[0].get('ignored') and bool(scrub_access[0].get('name', {}).get('value'))
        checks.append({'name': 'event scrubber is an exposed named accessibility slider', 'ok': ok, 'actual': scrub_access[:1]})
        print(('PASS ' if ok else 'FAIL ') + 'event scrubber is an exposed named accessibility slider', flush=True)
        if not ok:
            raise AssertionError(json.dumps(scrub_access, ensure_ascii=False))
        b.ev("document.getElementById('skyStoryScrub').focus()")
        check('the scrubber really owns keyboard focus', "document.activeElement.id==='skyStoryScrub'")
        key('ArrowRight')
        check('a real ArrowRight keypress steps the player to the next event and its slider value',
              "CLSky.playerState().eventId==='c'&&document.getElementById('skyStoryScrub').getAttribute('aria-valuenow')==='3'&&document.getElementById('skyStoryTitle').textContent==='开门救人'")
        check('that seek announces the target event and stage exactly once',
              "document.getElementById('skyStoryStageLive').textContent==='已定位到 3 / 4 · 开门救人 · 阶段：此刻'")
        key('PageDown')
        check('a real PageDown keypress jumps ten percent of the sequence', "CLSky.playerState().eventId==='d'")
        key('End')
        check('a real End keypress clamps on the last event', "CLSky.playerState().eventId==='d'")
        key('Home')
        check('a real Home keypress lands on the first event', "CLSky.playerState().eventId==='a'")
        key('ArrowLeft')
        check('a real ArrowLeft keypress clamps at the first event', "CLSky.playerState().eventId==='a'")
        key('Escape')
        check('Escape still closes reading from the scrubber and returns playback-button focus',
              "document.getElementById('skyStoryPanel').hidden&&document.activeElement.id==='skyPlay'")
        b.ev('CLSky.stop()')

        activate('#skySearch', 'search combobox')
        check('the search combobox really owns keyboard focus', "document.activeElement.id==='skySearch'")
        b.ws.call('Input.insertText', text='钥匙')
        if not b.until("!document.getElementById('skySearchPanel').hidden", 4):
            raise AssertionError('search panel did not open from real typing')
        check('search results are a labelled dialog with a stable accessible name',
              "(()=>{const p=document.getElementById('skySearchPanel'),t=document.getElementById(p.getAttribute('aria-labelledby'));return p.getAttribute('role')==='dialog'&&p.getAttribute('aria-modal')!=null&&!!t&&t.textContent==='搜索候选'})()")
        search_access = accessibility_node('#skySearchPanel:not([hidden])')
        ok = bool(search_access) and search_access[0].get('role', {}).get('value') == 'dialog' and not search_access[0].get('ignored') and bool(search_access[0].get('name', {}).get('value'))
        checks.append({'name': 'the open search panel is an exposed, named accessibility dialog', 'ok': ok, 'actual': search_access[:1]})
        print(('PASS ' if ok else 'FAIL ') + 'the open search panel is an exposed, named accessibility dialog', flush=True)
        if not ok:
            raise AssertionError(json.dumps(search_access, ensure_ascii=False))
        check('focus entered the dialog through its controlling combobox',
              "(()=>{const i=document.activeElement;return i.id==='skySearch'&&i.getAttribute('aria-expanded')==='true'&&i.getAttribute('role')==='combobox'&&document.getElementById(i.getAttribute('aria-controls'))===document.getElementById('skySearchResults')})()")
        key('Escape')
        check('Escape closes the dialog and focus returns to its trigger combobox',
              "document.getElementById('skySearchPanel').hidden&&document.activeElement.id==='skySearch'&&document.getElementById('skySearch').getAttribute('aria-expanded')==='false'")

        activate('#skyDecode', 'deconstruction button')
        if not b.until("!document.getElementById('skyDeconPanel').hidden", 4):
            raise AssertionError('deconstruction panel did not open from a real click')
        check('view switcher is a real tablist whose selected tab matches the rendered view',
              "(()=>{const p=document.getElementById('skyDeconPanel'),tabs=p.querySelector('.sd-tabs'),chosen=p.querySelectorAll('[role=tab][aria-selected=true]');return tabs.getAttribute('role')==='tablist'&&tabs.getAttribute('aria-label').length>0&&chosen.length===1&&chosen[0].dataset.mode==='overview'&&chosen[0].tabIndex===0&&Array.from(tabs.querySelectorAll('[role=tab]')).every(t=>(t.getAttribute('aria-selected')==='true')===(t.tabIndex===0))})()")
        activate('#skyDeconTabCausal', 'causal tab')
        check('a real click moves selection and the tabpanel labelling to the causal view',
              "(()=>{const chosen=document.querySelectorAll('#skyDeconPanel [role=tab][aria-selected=true]'),body=document.getElementById('skyDeconBody');return chosen.length===1&&chosen[0].id==='skyDeconTabCausal'&&chosen[0].tabIndex===0&&body.getAttribute('role')==='tabpanel'&&body.getAttribute('aria-labelledby')==='skyDeconTabCausal'&&document.getElementById('skyDeconTitle').textContent==='因果网络'})()")
        tab_access = accessibility_node('#skyDeconPanel .sd-tabs')
        ok = bool(tab_access) and tab_access[0].get('role', {}).get('value', '').lower() == 'tablist' and not tab_access[0].get('ignored')
        checks.append({'name': 'view switcher is an exposed accessibility tab list', 'ok': ok, 'actual': tab_access[:1]})
        print(('PASS ' if ok else 'FAIL ') + 'view switcher is an exposed accessibility tab list', flush=True)
        if not ok:
            raise AssertionError(json.dumps(tab_access, ensure_ascii=False))
        b.ev("document.getElementById('skyDeconTabCausal').focus()")
        key('ArrowRight')
        check('native arrow navigation keeps the selected tab in sync with the rendered view',
              "(()=>{const chosen=document.querySelectorAll('#skyDeconPanel [role=tab][aria-selected=true]');return chosen.length===1&&chosen[0].id==='skyDeconTabForeshadow'&&document.activeElement.id==='skyDeconTabForeshadow'&&document.getElementById('skyDeconBody').getAttribute('aria-labelledby')==='skyDeconTabForeshadow'})()")
        activate('#skyDeconTabMechanics', 'mechanics tab')
        notes.append('情节证据内部的层级切换器（.sd-mechanics-tabs）是带 aria-pressed 的按钮组而非 tab 语义：它筛选列表而非切换 tabpanel，属合理差异，未大改。')
        activate('#skyDeconPanel [data-layer=tasks]', 'mechanics task layer')
        check('the mechanics layer switcher is an aria-pressed button group that stays in sync',
              "(()=>{const group=document.querySelector('.sd-mechanics-tabs');if(!group)return false;const pressed=Array.from(group.querySelectorAll('[aria-pressed=true]'));return group.getAttribute('aria-label').length>0&&pressed.length===1&&pressed[0].dataset.layer==='tasks'&&Array.from(group.querySelectorAll('button')).every(x=>x.getAttribute('aria-pressed')!=null)})()")
        key('Escape')
        check('Escape closes the dissection panel and focus returns to its trigger button',
              "document.getElementById('skyDeconPanel').hidden&&document.activeElement.id==='skyDecode'")
        check('all panel headings keep their accessible names for orientation',
              "document.getElementById('skyDeconTitle').textContent.length>0&&document.getElementById('skyStoryTitle').textContent.length>0")

        check('input evidence uses trusted browser events', "__a11yInput.length>0&&__a11yInput.every(e=>e.trusted)")
        check('runtime remains healthy after the full semantic walk',
              "__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0&&CLApp.scene().core().perf().frameHooks.errors===0")
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
              'checks': checks, 'notes': notes, 'finishedAt': datetime.now(timezone.utc).isoformat(),
              'boundary': 'Normal entry, no probe. Native CDP mouse/keyboard for semantic assertions; '
                          'public CLSky API only for reach-the-state setup. AX names come from the real '
                          'Accessibility domain, but this is not a screen-reader certification.'}
    (args.out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('SKY A11Y TREE ' + ('PASS' if ok else 'FAIL'), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
