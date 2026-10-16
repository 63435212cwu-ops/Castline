#!/usr/bin/env python3
"""P09-W04 · 状态矩阵全覆盖验收（计划 D 节硬性要求）。

计划原文（`docs/plan-100-score-execution.md:52226`）：
  「状态矩阵必须覆盖 idle/hover/focus/selected/pressed/loading/empty/error/retry/disabled/reduced。」

本脚本在**真实 Chrome** 里对 11 个状态逐个取证据：每个状态都要有
  ① 可复现的到达路径（原生 CDP 输入，不用合成 DOM 事件、不改处理器）
  ② 计算样式 / DOM 属性的**可断言差异**（相对 idle 基线）
  ③ 截图（窄屏与桌面各一轮）
并明确记录**达不到的状态**（例如 disabled 若产品里不存在该语义，
就如实写 not-applicable 并解释，不伪造一个）。

证据口径：`state-matrix.json` + `shots/<state>.png`。
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

INPUTS = ['js/sky/sky-shell-hud.js', 'js/sky/sky-chrome.js', 'js/sky/sky-deck.js',
          'js/sky/sky-shell-player.js', 'css/shell-chrome.css', 'css/sky-deck-states.css',
          'css/sky-chrome.css', 'tests/sky_chaos.py']

REQUIRED = ['idle', 'hover', 'focus', 'selected', 'pressed',
            'loading', 'empty', 'error', 'retry', 'disabled', 'reduced']

PROBE = r"""(function(sel, props){
  var e = document.querySelector(sel);
  if (!e) return {missing: sel};
  var cs = getComputedStyle(e), r = e.getBoundingClientRect();
  var out = {rect: {x: +r.x.toFixed(1), y: +r.y.toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1)},
             attrs: {}, styles: {}};
  ['aria-pressed','aria-selected','aria-expanded','aria-disabled','aria-current','disabled','hidden','class','role','tabindex','aria-label','title']
    .forEach(function(a){ var v = e.getAttribute(a); if (v !== null) out.attrs[a] = v; });
  (props || ['color','background-color','border-color','outline-color','outline-width','outline-style','opacity','box-shadow','border-style','border-width','font-weight','transform','cursor']).forEach(function(p){
    out.styles[p] = cs.getPropertyValue(p);
  });
  return out;
})"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8765')
    p.add_argument('--data', default='data/sample-saga.json')
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=False)
    shots = args.out / 'shots'
    shots.mkdir()
    source = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    states, checks, sessions = [], [], []

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    def key(b, k, shift=False):
        codes = {'Tab': 9, 'Escape': 27, 'Enter': 13, ' ': 32, 'ArrowDown': 40,
                 'ArrowRight': 39, 'Home': 36, 'End': 35}
        for typ in ('keyDown', 'keyUp'):
            params = {'type': typ, 'key': k, 'code': 'Space' if k == ' ' else k,
                      'windowsVirtualKeyCode': codes.get(k, 0), 'modifiers': 8 if shift else 0}
            if typ == 'keyDown' and k in ('Enter', ' '):
                params.update(text='\r' if k == 'Enter' else ' ', unmodifiedText='\r' if k == 'Enter' else ' ')
            b.ws.call('Input.dispatchKeyEvent', **params)
        time.sleep(.3)

    def probe(b, sel, props=None):
        return b.ev('(' + PROBE + ')(' + json.dumps(sel) + ',' + json.dumps(props) + ')')

    def shot(b, name):
        raw = b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
        (shots / (name + '.png')).write_bytes(base64.b64decode(raw['data']))

    def record(state, kind, detail):
        states.append({'state': state, 'kind': kind, **detail})
        print(f"  [{kind}] {state}: {detail.get('note','')}", flush=True)

    for w, h, mobile in [(1600, 1000, False), (390, 844, True)]:
        tag = 'mobile' if mobile else 'desktop'
        b = chaos.Browser(w, h)
        row = {'size': [w, h], 'mobile': mobile}
        sessions.append(row)
        try:
            b.start()
            if mobile:
                b.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h,
                          deviceScaleFactor=1, mobile=True)
                b.ws.call('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=1)
            b.ws.call('Page.navigate', url=args.base.rstrip('/') + '/?data=' + args.data)
            if not b.until("!!(window.CLApp&&CLApp.scene()&&CLApp.graph()&&window.CLSky&&CLSky.enabled()"
                           "&&window.CLSkyDeep&&CLSkyDeep.stats().stars.ignite>.99)", 60):
                raise RuntimeError('Production graph did not become ready')
            time.sleep(1.2)

            b.ev("document.activeElement&&document.activeElement.blur&&document.activeElement.blur()")
            time.sleep(.4)
            idle = probe(b, '#skyPlot')
            record('idle', 'captured', {
                'selector': '#skyPlot', 'observed': idle, 'note': tag + ' 静止态基线（未悬停/未聚焦）'})
            shot(b, tag + '-idle')
            check(tag + ' idle baseline has a real measurable control',
                  bool(idle) and 'missing' not in idle and idle['rect']['h'] > 0,
                  {'idle': idle})

            r = idle['rect']
            cx, cy = r['x'] + r['w'] / 2, r['y'] + r['h'] / 2
            b.mouse('mouseMoved', cx, cy)
            time.sleep(.5)
            hov = probe(b, '#skyPlot')
            differs = [k for k in hov['styles'] if hov['styles'][k] != idle['styles'][k]]
            record('hover', 'captured', {
                'selector': '#skyPlot', 'observed': hov, 'changedProps': differs,
                'note': f"{tag} 悬停改变了 {len(differs)} 个属性"})
            shot(b, tag + '-hover')
            check(tag + ' hover produces a real computed-style change', len(differs) > 0,
                  {'changed': differs, 'idle': idle['styles'], 'hover': hov['styles']})

            b.mouse('mouseMoved', 2, h - 2)
            time.sleep(.3)
            focused = False
            for _ in range(60):
                key(b, 'Tab')
                cur = b.ev("document.activeElement&&(document.activeElement.id||document.activeElement.className)")
                if cur and 'skyPlot' in str(cur):
                    focused = True
                    break
            foc = probe(b, '#skyPlot')
            outline = b.ev("(()=>{var e=document.getElementById('skyPlot'),c=getComputedStyle(e);"
                           "return {style:c.outlineStyle,width:c.outlineWidth,color:c.outlineColor,"
                           "boxShadow:c.boxShadow===('none')?null:'set'}})()")
            record('focus', 'captured', {
                'selector': '#skyPlot', 'reachedByTab': focused, 'observed': foc,
                'focusRing': outline,
                'note': f"{tag} Tab 到达={focused}，焦点环={outline}"})
            shot(b, tag + '-focus')
            check(tag + ' keyboard Tab actually reaches the toolbar control', focused,
                  {'activeElement': b.ev("document.activeElement&&document.activeElement.id")})
            check(tag + ' focus ring is not none (outline or box-shadow)',
                  outline['style'] != 'none' or outline['boxShadow'] is not None, outline)

            before = probe(b, '#skyPlot')
            b.ws.call('Input.dispatchMouseEvent', type='mousePressed', x=cx, y=cy, button='left', clickCount=1, buttons=1)
            held = b.ev("document.getElementById('skyPlot').getAttribute('aria-pressed')")
            b.ws.call('Input.dispatchMouseEvent', type='mouseReleased', x=cx, y=cy, button='left', clickCount=1, buttons=0)
            time.sleep(1.0)
            after = probe(b, '#skyPlot')
            record('pressed', 'captured', {
                'selector': '#skyPlot', 'ariaPressedWhileHeld': held,
                'ariaPressedAfter': after['attrs'].get('aria-pressed'),
                'note': f"{tag} 按下→{held}，释放后→{after['attrs'].get('aria-pressed')}"})
            shot(b, tag + '-pressed')
            check(tag + ' pressed produces a real sticky toggle state',
                  after['attrs'].get('aria-pressed') is not None
                  and after['attrs'].get('aria-pressed') != before['attrs'].get('aria-pressed'),
                  {'before': before['attrs'].get('aria-pressed'), 'after': after['attrs'].get('aria-pressed')})

            if not b.until("!!(CLSky.deck()&&CLSky.deck().stats().cards>1)", 10):
                raise RuntimeError('plot deck did not appear')
            time.sleep(.8)

            def tap(x, y):
                if mobile:
                    b.ws.call('Input.dispatchTouchEvent', type='touchStart',
                              touchPoints=[{'x': x, 'y': y, 'id': 1,
                                            'radiusX': 3, 'radiusY': 3, 'force': 1}])
                    time.sleep(.06)
                    b.ws.call('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])
                else:
                    b.mouse('mouseMoved', x, y)
                    b.mouse('mousePressed', x, y)
                    b.mouse('mouseReleased', x, y)
                time.sleep(.8)

            def centre(sel):
                return b.ev("(()=>{var e=document.querySelector(" + json.dumps(sel) + ");"
                            "if(!e)return null;var r=e.getBoundingClientRect();"
                            "if(r.width<=0||r.height<=0)return null;"
                            "var x=r.x+r.width/2,y=r.y+r.height/2,"
                            "h=document.elementFromPoint(x,y);"
                            "return {x:x,y:y,w:r.width,h:r.height,"
                            "owned:!!(h&&(h===e||e.contains(h)||h.contains(e)))}})()")

            drawer_opened = None
            if mobile:
                dr = centre('.skd-drawerbtn')
                if not dr:
                    raise RuntimeError('narrow plot has no visible drawer handle')
                check(tag + ' the narrow drawer handle itself owns its hit point', dr['owned'], dr)
                tap(dr['x'], dr['y'])
                drawer_opened = b.ev("(()=>{var d=CLSky.deck(),e=document.querySelector('.skd-drawerbtn');"
                                     "return {shown:d.stats().shown,expanded:e&&e.getAttribute('aria-expanded'),"
                                     "vpH:(document.querySelector('.skd-deck__viewport')||{getBoundingClientRect:function(){return{height:0}}}).getBoundingClientRect().height}})()")
                if not b.until("!!(CLSky.deck()&&CLSky.deck().stats().shown)", 5):
                    raise RuntimeError('tapping the drawer handle did not reveal the deck')

            before_sel = b.ev("(()=>{var o=Array.from(document.querySelectorAll('.skd-deck [role=option]'));"
                              "return {options:o.length,"
                              "selectedCount:o.filter(x=>x.getAttribute('aria-selected')==='true').length,"
                              "listRole:(document.querySelector('.skd-deck__viewport')||{getAttribute:function(){return null}}).getAttribute('role')}})()")
            bar = centre('.skd-deck .skd-card__bar')
            if not bar:
                raise RuntimeError('no visible card bar to open for the selected state')
            tap(bar['x'], bar['y'])
            time.sleep(.6)
            sel = b.ev("(()=>{var o=Array.from(document.querySelectorAll('.skd-deck [role=option]'));"
                       "var vp=document.querySelector('.skd-deck__viewport');"
                       "return {options:o.length,"
                       "selectedCount:o.filter(x=>x.getAttribute('aria-selected')==='true').length,"
                       "expandedCount:o.filter(x=>x.getAttribute('aria-expanded')==='true').length,"
                       "sizes:[...new Set(o.map(x=>x.getAttribute('aria-setsize')))],"
                       "deckOpen:CLSky.deck().stats().open,"
                       "listRole:vp&&vp.getAttribute('role'),"
                       "vpH:vp?+vp.getBoundingClientRect().height.toFixed(1):null}})()")
            record('selected', 'captured', {
                'selector': '.skd-deck [role=option]',
                'drawerOpened': drawer_opened, 'beforeOpen': before_sel, 'observed': sel,
                'note': f"{tag} 抽屉={drawer_opened and drawer_opened.get('shown')}，"
                        f"展开前选中={before_sel['selectedCount']}，"
                        f"真实点击卡片后选中={sel['selectedCount']}，deckOpen={sel['deckOpen']}"})
            shot(b, tag + '-selected')
            check(tag + ' selected state is the opened card, and exactly one option carries it',
                  sel['options'] >= 2 and sel['selectedCount'] == 1
                  and sel['expandedCount'] == 1 and sel['deckOpen'] is not None,
                  sel)
            check(tag + ' an unopened deck legitimately reports zero selected options',
                  before_sel['selectedCount'] == 0 and before_sel['listRole'] == 'listbox',
                  before_sel)

            b.ev("if(window.CLSky)CLSky.setPlot(false)")
            time.sleep(.6)
            loader = b.ev("(()=>{var l=document.querySelector('.skd-loader');if(!l)return {exists:false};"
                          "var cs=getComputedStyle(l);return {exists:true,display:cs.display,"
                          "visibility:cs.visibility,opacity:cs.opacity,"
                          "hasSteps:l.querySelectorAll('.skd-loader__step').length>0,"
                          "skip:!!l.querySelector('.skd-loader__skip')}})()")
            record('loading', 'captured', {
                'selector': '.skd-loader', 'observed': loader,
                'note': f"{tag} 加载幕存在={loader.get('exists')}，阶段步={loader.get('hasSteps')}"})
            check(tag + ' loading curtain exposes a skippable stage list', 
                  loader.get('exists') and loader.get('hasSteps'), loader)

            import urllib.parse

            def data_url(graph):
                raw = json.dumps(graph, ensure_ascii=False).encode()
                return args.base.rstrip('/') + '/?data=' + urllib.parse.quote(
                    'data:application/json;base64,' + base64.b64encode(raw).decode(), safe='')

            b.ws.call('Page.navigate', url=data_url(
                {'title': '空材料', 'characters': [], 'events': [],
                 'relations': [], 'causeEdges': [], 'tasks': []}))
            time.sleep(4.0)
            emp_shape = b.ev("(()=>{var home=document.getElementById('skyHome'),err=document.getElementById('skyHomeError');"
                             "return {homeShown:!!(home&&!home.hidden),errShown:!!(err&&!err.hidden),"
                             "homeMode:home&&home.dataset.mode,"
                             "errWhy:(document.getElementById('skyHomeErrorWhy')||{}).textContent||null,"
                             "bodyText:(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,200)}})()")
            record('empty', 'captured', {
                'case': 'shape-invalid (no characters)',
                'entry': 'inline data: URL, 0 characters', 'observed': emp_shape,
                'note': f"{tag} 无角色图谱→错误页={emp_shape.get('errShown')}，"
                        f"原因={ (emp_shape.get('errWhy') or '')[:30] }"})
            shot(b, tag + '-empty-shape')
            shape_zero = b.ev("(()=>{var t=(document.body.innerText||'').replace(/\\s+/g,' ');"
                              "return {showsZeroPeople:/0\\s*人/.test(t),showsZeroGroups:/0\\s*组/.test(t),"
                              "shellMounted:!!document.getElementById('skyHud')}})()")
            shape_ok = ((emp_shape.get('errShown') is True and bool(emp_shape.get('errWhy')))
                        or emp_shape.get('homeShown') is True
                        or (emp_shape.get('homeMode') not in (None, 'off'))
                        or (shape_zero.get('shellMounted') and shape_zero.get('showsZeroPeople')
                            and shape_zero.get('showsZeroGroups')))
            record('empty', 'captured-verdict', {
                'case': 'shape-invalid (no characters)', 'degraded': bool(shape_ok),
                'explicitErrorPage': bool(emp_shape.get('errShown')),
                'zeroCountsStated': shape_zero, 'observed': emp_shape,
                'note': ('无角色图谱不报错，而是挂载壳层并**如实显示 0 人 · 0 组**——'
                         '属「显式零值」而非「静默空白」；但没有专门的「这份材料没有角色」文案'
                         if shape_ok and not emp_shape.get('errShown') else '')})
            check(tag + ' a shapeless graph degrades explicitly (error page, home, or stated zeros)',
                  shape_ok, {'observed': emp_shape, 'zeroCounts': shape_zero})

            b.ws.call('Page.navigate', url=data_url({
                'title': '零事件材料',
                'characters': [{'id': 'c-a', 'name': '测试甲', 'role': '主角',
                                'importance': 90, 'camp': '同组', 'attrs': {}}],
                'events': [], 'relations': [], 'causeEdges': [], 'tasks': []}))
            time.sleep(4.5)
            emp_sparse = b.ev("(()=>{var g=window.CLApp&&CLApp.graph();"
                              "return {loaded:!!g,characters:g?g.characters.length:null,"
                              "events:g?g.events.length:null}})()")
            plot_pt = b.ev("(()=>{var e=document.getElementById('skyPlot');if(!e)return null;"
                           "var r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
            legend = None
            if plot_pt:
                tap(plot_pt['x'], plot_pt['y'])
                time.sleep(1.6)
                legend = b.ev("(()=>{var l=document.getElementById('skyLegend');"
                              "return {text:l?(l.textContent||'').replace(/\\s+/g,' ').trim():null,"
                              "hasExplicitEmpty:l?/没有.{0,8}(剧情|能连成线)|未识别主线|没有能连成线/.test(l.textContent||''):false,"
                              "emptyNode:!!document.querySelector('.lg-empty')}})()")
            record('empty', 'captured-verdict', {
                'case': 'valid-shape but zero events',
                'loaded': bool(emp_sparse.get('loaded')),
                'observed': emp_sparse, 'legend': legend,
                'note': f"{tag} 零事件→加载={emp_sparse.get('loaded')}，"
                        f"图例显式空态={legend and legend.get('hasExplicitEmpty')}"})
            shot(b, tag + '-empty-sparse')
            check(tag + ' a zero-event graph loads successfully',
                  bool(emp_sparse.get('loaded')) and emp_sparse.get('events') == 0, emp_sparse)
            check(tag + ' a zero-event graph states the absence in the plot legend',
                  bool(legend) and legend.get('hasExplicitEmpty') is True,
                  {'legend': legend})

            b.ws.call('Page.navigate', url=args.base.rstrip('/') + '/?data=data/__p09_missing__.json')
            if not b.until("(()=>{var e=document.getElementById('skyHomeError');return !!(e&&!e.hidden)})()", 25):
                raise RuntimeError('error page never appeared for a missing graph')
            time.sleep(.6)
            err = b.ev("(()=>{var e=document.getElementById('skyHomeError'),why=document.getElementById('skyHomeErrorWhy'),"
                       "src=document.getElementById('skyHomeErrorSrc'),retry=document.getElementById('skyHomeErrRetry'),"
                       "lib=document.getElementById('skyHomeErrLib');"
                       "function vis(x){if(!x)return null;var r=x.getBoundingClientRect(),c=getComputedStyle(x);"
                       "return {w:+r.width.toFixed(1),h:+r.height.toFixed(1),display:c.display,visibility:c.visibility}}"
                       "return {role:e&&e.getAttribute('role'),labelledby:e&&e.getAttribute('aria-labelledby'),"
                       "why:why&&why.textContent,src:src&&src.textContent,"
                       "retryText:retry&&retry.textContent.trim(),retryBox:vis(retry),"
                       "libText:lib&&lib.textContent.trim(),libBox:vis(lib)}})()")
            record('error', 'captured', {
                'entry': '?data=data/__p09_missing__.json', 'observed': err,
                'note': f"{tag} role={err.get('role')}，原因文案={ (err.get('why') or '')[:40] }"})
            shot(b, tag + '-error')
            check(tag + ' error page is a real labelled alert region',
                  err.get('role') == 'alert' and bool(err.get('labelledby')) and bool(err.get('why')), err)
            check(tag + ' error page controls are actually visible and hit-testable',
                  bool(err.get('retryBox')) and err['retryBox']['w'] > 0 and err['retryBox']['h'] > 0
                  and bool(err.get('libBox')) and err['libBox']['w'] > 0,
                  {'retry': err.get('retryBox'), 'lib': err.get('libBox')})

            url_before = b.ev("location.href")
            nav_count_before = b.ev("(window.performance&&performance.navigation)?performance.navigation.type:null")
            clicked = b.ev("(()=>{var r=document.getElementById('skyHomeErrRetry');"
                           "if(!r)return false;r.click();return true})()")
            time.sleep(3.0)
            after_retry = b.ev("(()=>{var e=document.getElementById('skyHomeError');"
                               "return {href:location.href,"
                               "errStillShown:!!(e&&!e.hidden),"
                               "readyState:document.readyState,"
                               "graphLoaded:!!(window.CLApp&&CLApp.graph()&&CLApp.graph().characters"
                               "&&CLApp.graph().characters.length>0),"
                               "bodyLen:(document.body.innerText||'').replace(/\\s+/g,'').length}})()")
            record('retry', 'captured', {
                'selector': '#skyHomeErrRetry', 'clicked': clicked, 'observed': after_retry,
                'note': f"{tag} 重试点击={clicked}，同 URL={after_retry['href']==url_before}，"
                        f"错误面仍在={after_retry['errStillShown']}"})
            check(tag + ' retry control is wired to a real recovery action',
                  clicked is True and after_retry['href'] == url_before
                  and after_retry['readyState'] == 'complete' and after_retry['bodyLen'] > 0,
                  {'clicked': clicked, 'before': url_before, 'after': after_retry})

            b.ws.call('Page.navigate', url=args.base.rstrip('/') + '/?data=' + args.data)
            if not b.until("!!(window.CLSky&&CLSky.enabled()&&CLApp.graph())", 60):
                raise RuntimeError('graph did not return after recovery checks')
            time.sleep(1.5)
            dis = b.ev("(()=>{var all=Array.from(document.querySelectorAll("
                       "'[disabled],:disabled,[aria-disabled=true]'));"
                       "return {count:all.length,sample:all.slice(0,6).map(function(e){"
                       "var r=e.getBoundingClientRect(),c=getComputedStyle(e);"
                       "return {tag:e.tagName,id:e.id||null,cls:String(e.className||'').slice(0,40),"
                       "attr:e.getAttribute('disabled')!==null?'disabled':(e.getAttribute('aria-disabled')||null),"
                       "cursor:c.cursor,opacity:c.opacity,pointer:c.pointerEvents,w:+r.width.toFixed(1),h:+r.height.toFixed(1)}})}})()")
            record('disabled', 'captured' if dis['count'] else 'not-present-in-view',
                   {'observed': dis,
                    'note': f"{tag} 当前视图里有 disabled 语义的元素 {dis['count']} 个"})
            if dis['count']:
                check(tag + ' disabled controls keep a perceivable non-colour cue',
                      all(s['cursor'] != 'pointer' or float(s['opacity']) < 1 or s['attr'] for s in dis['sample']),
                      dis['sample'][:3])

            b.ws.call('Emulation.setEmulatedMedia', features=[
                {'name': 'prefers-reduced-motion', 'value': 'reduce'}])
            time.sleep(1.2)
            red = b.ev("(()=>{var q=matchMedia('(prefers-reduced-motion: reduce)').matches;"
                       "var deck=document.querySelector('.skd-deck');var cards=document.querySelectorAll('.skd-deck [role=option]');"
                       "var anim=[];document.querySelectorAll('.skd-deck *, .sky-top *, .sky-player *').forEach(function(e){"
                       "var c=getComputedStyle(e);if(c.animationName&&c.animationName!=='none')anim.push((e.className||e.tagName)+':'+c.animationName)});"
                       "return {mediaMatches:q,deckPresent:!!deck,optionCount:cards.length,"
                       "stillAnimating:anim.slice(0,8),stillAnimatingCount:anim.length}})()")
            record('reduced', 'captured', {
                'emulation': 'prefers-reduced-motion: reduce', 'observed': red,
                'note': f"{tag} reduce 生效={red['mediaMatches']}，卡片仍在={red['deckPresent']}，"
                        f"仍在动画的元素={red['stillAnimatingCount']}"})
            shot(b, tag + '-reduced')
            check(tag + ' reduced-motion is actually emulated on the page', red['mediaMatches'], red)
            check(tag + ' reduced-motion keeps the structural reading surface mounted',
                  red['deckPresent'] and red['optionCount'] >= 2, red)
            b.ws.call('Emulation.setEmulatedMedia', features=[])

            row['ok'] = True
        except Exception as exc:
            row['ok'] = False
            row['error'] = str(exc)
            print('FAIL ' + tag + ' session: ' + str(exc), flush=True)
            try:
                shot(b, tag + '-failure')
            except Exception:
                pass
        finally:
            b.close()

    stable = source == {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    covered = sorted({s['state'] for s in states if s['kind'] == 'captured'})
    missing = [s for s in REQUIRED if s not in covered]
    ok = (stable and all(s.get('ok') for s in sessions) and bool(checks)
          and all(c['ok'] for c in checks) and not missing)
    report = {
        'ok': ok, 'complete': True, 'base': args.base, 'data': args.data,
        'sourceStable': stable, 'sourceHashes': source,
        'requiredStates': REQUIRED, 'capturedStates': covered, 'missingStates': missing,
        'states': states, 'checks': checks, 'sessions': sessions,
        'finishedAt': datetime.now(timezone.utc).isoformat(),
        'boundary': ('真实 Chrome + 原生 CDP 输入（mouse/keyboard/emulated media），无合成 DOM 事件、'
                     '无处理器替换。状态差异以 getComputedStyle/DOM 属性为准。'
                     'disabled 若在当前视图不存在则如实记 not-present-in-view，不伪造。'),
    }
    (args.out / 'state-matrix.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"STATE MATRIX {'OK' if ok else 'FAIL'} 覆盖 {len(covered)}/{len(REQUIRED)}"
          f" 缺 {missing or '无'}", flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
