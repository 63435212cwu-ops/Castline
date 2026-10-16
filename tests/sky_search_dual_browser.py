#!/usr/bin/env python3
"""Native search disambiguation / pagination and unknown dual attributes.

The synthetic graph is loaded through the normal ?data URL (data: JSON), not
injected via a replacement graph getter. No model calls or data/cache writes.
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8123')
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=False)
    fixture = {'title': '搜索与未知属性验收', 'characters': [
        {'id': 'c-a', 'name': '共同甲', 'aliases': ['共同别名'], 'role': '主角', 'importance': 90, 'camp': '同组', 'attrs': {}},
        {'id': 'c-b', 'name': '共同乙', 'aliases': ['共同别名'], 'role': '核心配角', 'importance': 80, 'camp': '同组', 'attrs': {}}],
        'events': [{'id': 'e-' + str(i), 'order': i + 1, 'chapter': '第' + str(i + 1) + '章', 'title': '共同事件 ' + str(i).zfill(3), 'kind': '日常', 'summary': '可检索事件记录', 'characters': ['共同甲', '共同乙']} for i in range(125)],
        'relations': [], 'tasks': [{'id': 't-1', 'name': '共同任务已定位', 'character': '共同甲', 'goal': '查明真相', 'status': 'active', 'eventIds': ['e-100']},
                                   {'id': 't-2', 'name': '共同任务未知', 'character': '共同乙', 'goal': '不能按标题猜事件', 'status': 'unknown', 'eventIds': ['missing']}],
        'clues': [{'id': 'cl-1', 'name': '共同伏笔', 'seedEventId': 'e-5', 'summary': '待核对'}]}
    raw = json.dumps(fixture, ensure_ascii=False).encode()
    url = args.base.rstrip('/') + '/?data=' + urllib.parse.quote('data:application/json;base64,' + base64.b64encode(raw).decode(), safe='')
    sources = ['js/sky/sky-search.js', 'js/sky/sky-shell.js', 'js/sky/sky-shell-hud.js', 'js/app.js']
    hashes = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in sources}
    checks, sessions = [], []

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            raise AssertionError(name + ': ' + json.dumps(detail, ensure_ascii=False))

    def key(b, k, shift=False):
        codes = {'Tab': 9, 'Enter': 13, 'Escape': 27, ' ': 32, 'Home': 36, 'End': 35, 'ArrowUp': 38, 'ArrowDown': 40, '/': 191, 'd': 68}
        for typ in ('keyDown', 'keyUp'):
            data = {'type': typ, 'key': k, 'code': 'Space' if k == ' ' else 'Slash' if k == '/' else 'KeyD' if k == 'd' else k,
                    'windowsVirtualKeyCode': codes[k], 'modifiers': 8 if shift else 0}
            if typ == 'keyDown' and k in ('Enter', ' '):
                data.update(text='\r' if k == 'Enter' else ' ', unmodifiedText='\r' if k == 'Enter' else ' ')
            b.ws.call('Input.dispatchKeyEvent', **data)
        time.sleep(.18)

    def query(b, text):
        b.ws.call('Input.dispatchKeyEvent', type='rawKeyDown', key='a', code='KeyA', windowsVirtualKeyCode=65, modifiers=4, commands=['selectAll'])
        b.ws.call('Input.dispatchKeyEvent', type='keyUp', key='a', code='KeyA', windowsVirtualKeyCode=65, modifiers=4)
        b.ws.call('Input.insertText', text=text)
        time.sleep(.3)

    def tab_until(b, expression):
        for _ in range(80):
            if b.ev(expression):
                return True
            key(b, 'Tab')
        return False

    def snapshot(b):
        return b.ev("(()=>{const s=CLSkySearch.stats(),root=document.getElementById('skySearchPanel'),a=document.activeElement,active=document.getElementById(document.getElementById('skySearch').getAttribute('aria-activedescendant'));return {search:s,plot:CLSky.state().plot,compass:CLSky.state().compass,cursor:CLSky.state().cursor,focus:a&&(a.id||a.className),title:active&&active.querySelector('.sks-title').textContent,pos:active&&+active.getAttribute('aria-posinset'),size:active&&+active.getAttribute('aria-setsize'),count:document.getElementById('skySearchCount')&&document.getElementById('skySearchCount').textContent,detail:root&&root.querySelector('.sks-detail').textContent,rect:root&&(()=>{const r=root.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})(),events:window.__searchNativeEvents.slice(-30)}})()")

    def shot(b, name):
        (args.out / name).write_bytes(base64.b64decode(b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)['data']))

    for w, h, mobile in [(1600, 1000, False), (390, 844, True)]:
        tag = 'mobile' if mobile else 'desktop'
        b = chaos.Browser(w, h); row = {'size': [w, h], 'mobile': mobile}; sessions.append(row)
        try:
            b.start()
            if mobile:
                b.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=1, mobile=True)
                b.ws.call('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=1)
            b.ws.call('Page.navigate', url=url)
            if not b.until("(()=>{const s=window.CLSkyDeep&&CLSkyDeep.stats();return !!(window.__headlessHealth&&__headlessHealth.domContentLoaded&&window.CLApp&&CLApp.graph()&&CLApp.graph().events.length===125&&window.CLSky&&CLSky.enabled()&&CLSky.model()&&window.CLSkyChrome&&CLSkyChrome.enabled()&&window.CLSkySearch&&s&&s.stars&&s.stars.ignite>.99)})()", 60):
                raise RuntimeError('Normal fixture entry not ready; inspect data URL / script integration')
            b.ev("window.__searchNativeEvents=[];['keydown','keyup','click','input','change','touchstart'].forEach(t=>document.addEventListener(t,e=>__searchNativeEvents.push({type:t,key:e.key||null,trusted:e.isTrusted,target:e.target.id||e.target.className}),true));")
            key(b, '/')
            check(tag + ' slash shortcut reaches search input', b.ev("document.activeElement.id==='skySearch'"), b.ev('document.activeElement.id'))
            query(b, '共同别名')
            s = snapshot(b)
            check(tag + ' shared alias exposes two explicit candidates', s['search']['open'] and s['search']['filtered'] == 2 and s['search']['active'] == -1 and not s['plot'] and s['compass'] is None, s)
            key(b, 'Enter'); s = snapshot(b)
            check(tag + ' Enter without selection never jumps to first match', s['search']['open'] and s['compass'] is None and s['search']['active'] == -1, s)
            key(b, 'ArrowDown'); key(b, 'ArrowDown'); selected = snapshot(b)
            key(b, 'Enter')
            check(tag + ' explicit second candidate selects exact character', b.until('CLSky.state().compass===' + json.dumps(selected['title']), 4), {'selected': selected, 'after': snapshot(b)})
            query(b, '共同事件')
            check(tag + ' long results include every event before type filter', snapshot(b)['search']['filtered'] >= 125, snapshot(b))
            if mobile:
                check(tag + ' native Tab reaches entity filter', tab_until(b, "document.activeElement.matches('#skySearchPanel select[aria-label=\"筛选搜索实体类型\"]')"), snapshot(b))
                key(b, 'Home'); key(b, 'ArrowDown'); key(b, 'ArrowDown'); key(b, 'ArrowDown'); key(b, 'Enter')
                check(tag + ' native select filters events', snapshot(b)['search']['type'] == 'event' and snapshot(b)['search']['filtered'] == 125, snapshot(b))
            else:
                row['nativeSelectBoundary'] = 'macOS headless desktop native select does not change via CDP arrow input even on an independent minimal HTML page; mobile covers the trusted native change path. Desktop keeps all types and verifies full mixed-result navigation.'
            check(tag + ' native Tab reaches result list', tab_until(b, "document.activeElement.id==='skySearchResults'"), snapshot(b))
            key(b, 'End'); s = snapshot(b)
            check(tag + ' End reaches full final candidate in bounded DOM window', s['pos'] == s['size'] and s['size'] >= 125 and s['search']['rendered'] <= 50 and s['title'] == '共同事件 124', s)
            check(tag + ' candidate panel fits viewport', s['rect']['x'] >= 0 and s['rect']['x'] + s['rect']['w'] <= w + 1 and s['rect']['y'] >= 0 and s['rect']['y'] + s['rect']['h'] <= h + 1, s['rect'])
            shot(b, tag + '-search-last-page.png')
            key(b, 'Enter')
            check(tag + ' selected event locates exact final chapter', b.until('CLSky.state().plot&&CLSky.state().cursor===CLSky.model().nCh-1', 5), snapshot(b))
            query(b, '共同任务未知')
            if mobile:
                check(tag + ' filter can be changed with native Tab', tab_until(b, "document.activeElement.matches('#skySearchPanel select[aria-label=\"筛选搜索实体类型\"]')"), snapshot(b))
                key(b, 'Home'); key(b, 'Enter')
            check(tag + ' unlocated task is still searchable', snapshot(b)['search']['filtered'] == 1, snapshot(b))
            tab_until(b, "document.activeElement.id==='skySearchResults'")
            key(b, 'ArrowDown'); before = snapshot(b); key(b, 'Enter'); s = snapshot(b)
            check(tag + ' unknown task shows details without invented event jump', s['search']['open'] and '未提供可定位' in s['detail'] and s['cursor'] == before['cursor'], s)
            key(b, 'Escape')
            check(tag + ' Escape closes only search and restores input', not snapshot(b)['search']['open'] and snapshot(b)['focus'] == 'skySearch' and snapshot(b)['plot'], snapshot(b))
            key(b, 'Escape'); key(b, 'd', True)
            check(tag + ' normal shortcut opens dual demo', b.until('CLDualStage.active()', 3), b.ev('CLDualStage.active()'))
            d = b.ev("(()=>{const r=document.getElementById('dualStage');return {label:r.textContent,coverage:document.getElementById('dualConfidence').textContent,values:Array.from(r.querySelectorAll('.dual-bar-head b')).map(e=>e.textContent),fills:Array.from(r.querySelectorAll('.dual-bar-fill')).map(e=>e.hidden),persona:document.getElementById('dualPersonaValue').textContent,shadow:document.getElementById('dualShadowValue').textContent,log:document.getElementById('dualEventLog').textContent}})()")
            check(tag + ' missing scores remain unknown with no invented bars', d['coverage'] == '0 / 16' and d['values'] == ['未知'] * 8 and all(d['fills']) and d['persona'] == '未知' and d['shadow'] == '未知', d)
            check(tag + ' dual clearly marks decoration and contains no fake telemetry', '视觉演示' in d['label'] and '不表示置信度' in d['label'] and all(x not in d['label'] for x in ['MODEL CONFIDENCE', 'LATENCY', '98.4%', '18ms', 'MEMORY ECHO', 'VECTOR SHIFT', '+0.82']), d)
            shot(b, tag + '-dual-unknown.png')
            key(b, 'Escape')
            health = b.ev("(()=>{const h=__headlessHealth,S=CLApp.scene(),d=S.digest();return {errors:h.jserr,rejections:h.jsrej,shaders:S.shaderErrors(),frames:d.frameHooks&&d.frameHooks.errors||0,events:__searchNativeEvents}})()")
            check(tag + ' native inputs and runtime healthy', not health['errors'] and not health['rejections'] and not health['shaders'] and not health['frames'] and bool(health['events']) and all(e['trusted'] for e in health['events']), health)
            row.update(ok=True, final=snapshot(b), health=health)
        except Exception as exc:
            row.update(ok=False, error=str(exc)); print('FAIL ' + tag + ' session: ' + str(exc), flush=True)
            try:
                shot(b, tag + '-failure.png'); row['failure'] = snapshot(b)
            except Exception:
                pass
        finally:
            b.close()
    stable = hashes == {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in sources}
    ok = stable and bool(checks) and all(c['ok'] for c in checks) and all(s.get('ok') for s in sessions)
    report = {'ok': ok, 'complete': True, 'sourceStable': stable, 'sourceHashes': hashes, 'fixtureSHA256': hashlib.sha256(raw).hexdigest(), 'checks': checks, 'sessions': sessions,
              'finishedAt': datetime.now(timezone.utc).isoformat(), 'boundary': 'Synthetic unknown-score graph through normal data URL; fresh profile, no probe, actual native CDP events, no model or cache writes.'}
    (args.out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
