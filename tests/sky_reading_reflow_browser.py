#!/usr/bin/env python3
"""Native keyboard reading at 200/400% equivalent CSS viewports.

Loads a synthetic graph through the normal data URL. Does not call a model,
write source data, synthesize DOM events or replace production handlers.
"""
import argparse
import base64
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8830')
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; use serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=False)
    prose = '材料需要逐字阅读，不能以摘要替代动机、行动、后果与原文依据。' * 3
    graph = {'title': '阅读重排验收', 'characters': [
        {'id': 'c-a', 'name': '测试甲', 'role': '主角', 'importance': 90, 'camp': '同组', 'attrs': {}},
        {'id': 'c-b', 'name': '测试乙', 'role': '配角', 'importance': 70, 'camp': '同组', 'attrs': {}}],
        'events': [{'id': 'e-' + str(i), 'order': i + 1, 'chapter': '第' + str(i + 1) + '章',
                    'title': '事件 ' + str(i), 'summary': '事件记录含人物动机与原文依据。', 'kind': '日常', 'characters': ['测试甲', '测试乙']} for i in range(4)],
        'relations': [], 'tasks': [{'id': 't-unlocated', 'name': '未知任务', 'goal': prose, 'eventIds': ['missing']}],
        'worldRules': [{'id': 'r-1', 'name': '未知规则', 'rule': prose}]}
    raw = json.dumps(graph, ensure_ascii=False).encode()
    url = args.base.rstrip('/') + '/?data=' + urllib.parse.quote('data:application/json;base64,' + base64.b64encode(raw).decode(), safe='')
    b = chaos.Browser(1440, 900)
    checks = []

    def check(name, expression):
        result = b.ev(expression)
        ok = result is True
        checks.append({'name': name, 'ok': ok, 'actual': result})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            raise AssertionError(name + ': ' + json.dumps(result, ensure_ascii=False))

    def key(k, shift=False):
        codes = {'Tab': 9, 'Enter': 13, 'Escape': 27, ' ': 32, 'Home': 36, 'End': 35, 'ArrowUp': 38, 'ArrowDown': 40, 'ArrowLeft': 37, 'ArrowRight': 39}
        for typ in ('keyDown', 'keyUp'):
            data = {'type': typ, 'key': k, 'code': 'Space' if k == ' ' else k,
                    'windowsVirtualKeyCode': codes[k], 'modifiers': 8 if shift else 0}
            if typ == 'keyDown' and k in ('Enter', ' '):
                data.update(text='\r' if k == 'Enter' else ' ', unmodifiedText='\r' if k == 'Enter' else ' ')
            b.ws.call('Input.dispatchKeyEvent', **data)
        time.sleep(.1)

    def shot(name):
        (args.out / (name + '.png')).write_bytes(base64.b64decode(b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)['data']))

    def panel_check(tag, selector, header, close):
        check(tag + ' panel fits CSS viewport', "(()=>{const e=document.querySelector(" + json.dumps(selector) + "),r=e.getBoundingClientRect();return r.x>=0&&r.y>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1&&r.width>0&&r.height>0&&e.scrollWidth<=e.clientWidth+1})()")
        check(tag + ' header close remains exposed', "(()=>{const e=document.querySelector(" + json.dumps(close) + "),r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);const ok=r.height>=38&&h&&(e===h||e.contains(h));return ok?true:{h:r.height,y:r.y,vh:innerHeight,hit:h?(h.className||h.tagName):null,sel:" + json.dumps(close) + "}})()")
        b.ev("(()=>{const p=document.querySelector(" + json.dumps(selector) + ");p.scrollTop=p.scrollHeight})()")
        check(tag + ' sticky close survives end scroll', "(()=>{const e=document.querySelector(" + json.dumps(close) + "),r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return h&&(e===h||e.contains(h))})()")
        b.ev("document.querySelector(" + json.dumps(close) + ").focus()")
        for i in range(6):
            key('Tab')
            if not b.ev("document.querySelector(" + json.dumps(selector) + ").contains(document.activeElement)"):
                break
            check(tag + ' Tab focus visible ' + str(i), "(()=>{const e=document.activeElement,r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,Math.min(innerHeight-1,r.y+r.height/2));return r.x>=0&&r.right<=innerWidth+1&&r.bottom>0&&r.y<innerHeight&&h&&(e===h||e.contains(h))})()")
        b.ev("document.querySelector(" + json.dumps(close) + ").focus()")
        key('Escape')

    try:
        b.start()
        b.ws.call('Page.navigate', url=url)
        if not b.until("!!(window.__headlessHealth&&__headlessHealth.domContentLoaded&&window.CLApp&&CLApp.graph()&&CLApp.graph().events.length===4&&window.CLSky&&CLSky.enabled()&&CLSky.model()&&window.CLSkyChrome&&CLSkyChrome.enabled()&&window.CLSkyDeconstruction&&window.CLSkyEnrich&&window.CLSkySearch&&document.querySelector('#loader.off'))", 60):
            raise RuntimeError('Normal graph entry failed')
        time.sleep(3)
        b.ev("window.__reflowInput=[];['keydown','input','click'].forEach(t=>document.addEventListener(t,e=>__reflowInput.push({type:t,trusted:e.isTrusted}),true))")
        for w, h in [(640, 450), (320, 225), (320, 640)]:
            tag = str(w) + 'x' + str(h)
            b.size(w, h); time.sleep(.7)
            b.ev('CLSkyDeconstruction.open();CLSkyDeconstruction.setMode("evidence")')
            panel_check(tag + ' deconstruction', '#skyDeconPanel', '.sd-head', '#skyDeconPanel .sd-close')
            b.ev('CLSkyDeconstruction.close();CLSky.setPlot(true);CLSky.seekEventAt(0);CLSky.stop()')
            panel_check(tag + ' story', '#skyStoryPanel', '.ssp-head', '#skyStoryPanel [data-story=close]')
            b.ev('CLSkyEnrich.open()')
            panel_check(tag + ' enrich', '#skyEnrichPanel', '.ske-head', '#skyEnrichPanel [data-action=close]')
            b.ev('document.getElementById("skySearch").focus();document.getElementById("skySearch").value=""')
            b.ws.call('Input.insertText', text='未知任务'); time.sleep(.3)
            check(tag + ' search preserves a visible editable query', "(()=>{const e=document.activeElement,r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return /^(skySearch|skySearchQuery)$/.test(e.id)&&e.value==='未知任务'&&h===e})()")
            if h <= 500:
                check(tag + ' short view transfers to in-panel combobox', "document.activeElement.id==='skySearchQuery'")
                key('ArrowLeft'); key(' ')
                check(tag + ' query keeps native caret and Space editing', "document.activeElement.value==='未知任 务'")
                b.ev('document.activeElement.select()'); b.ws.call('Input.insertText', text='未知任务'); time.sleep(.3)
            key('ArrowDown'); key('Enter')
            check(tag + ' unlocated detail is focused named reading region', "(()=>{const e=document.querySelector('.sks-detail');return document.activeElement===e&&!e.hidden&&e.getAttribute('role')==='region'&&document.getElementById(e.getAttribute('aria-labelledby')).textContent.length>0&&e.textContent.includes('未提供可定位')})()")
            check(tag + ' detail appears below sticky header', "(()=>{const e=document.querySelector('.sks-detail-head'),r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return r.y>=document.querySelector('.sks-head').getBoundingClientRect().bottom-1&&r.y<innerHeight&&h&&(e===h||e.contains(h))})()")
            key('Tab')
            check(tag + ' Tab reaches detail return action', "document.activeElement.matches('.sks-detail-back')")
            key('Enter')
            check(tag + ' return restores selected candidate and list focus', "document.activeElement.id==='skySearchResults'&&document.querySelector('.sks-detail').hidden&&CLSkySearch.stats().active===0")
            shot(tag + '-reading')
            key('Escape')
            check(tag + ' Escape returns original query focus', "document.getElementById('skySearchPanel').hidden&&document.activeElement.id==='skySearch'")
        check('trusted input path and healthy runtime', "__reflowInput.length>0&&__reflowInput.every(e=>e.trusted)&&__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0&&CLApp.scene().core().perf().frameHooks.errors===0")
        report = {'ok': True, 'checks': checks, 'viewports': [[640, 450], [320, 225], [320, 640]], 'modelsCalled': 0, 'boundary': 'CSS viewport equivalence, not a claim of native Safari or screen-reader certification.'}
    except Exception as exc:
        report = {'ok': False, 'checks': checks, 'error': str(exc)}
        try:
            shot('failure')
            report['focus'] = b.ev("(()=>{const e=document.activeElement,r=e.getBoundingClientRect();return {html:e.outerHTML,rect:{x:r.x,y:r.y,w:r.width,h:r.height},search:CLSkySearch.stats()}})()")
        except Exception:
            pass
    finally:
        b.close()
    (args.out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'ok': report['ok'], 'checks': len(checks), 'out': str(args.out)}), flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
