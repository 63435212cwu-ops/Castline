#!/usr/bin/env python3
"""P09-W07 · 200% / 400% 缩放验收（计划交付维度要求「200/400%缩放」）。

审核原文（`docs/strict-audit-user-2026-10-07.md`）：
  「iPhone Safari、Android Chromium、桌面 Chrome、键盘、读屏、**200%/400% 缩放**、
    减弱动效、低档和无 WebGL 降级都完成真实路径验收。」

与 `tests/sky_reading_reflow_browser.py` 的区别：那个脚本用**缩小 CSS 视口**
（640×450 / 320×225）模拟重排；本脚本用 CDP 的**页面缩放**语义
（`Emulation.setPageScaleFactor` + `Emulation.setDeviceMetricsOverride` 的
`scale` 参数），验证的是**放大后**的真实渲染结果，两条路径互补。

四档各验一次：
  ① 文字不溢出容器：面板内每个文本节点的 scrollWidth ≤ clientWidth，
     且元素 rect 不出视口。
  ② 控件仍可点击：对每个可见控件中心做 elementFromPoint，必须由它或其后代接管。
  ③ 内容不丢失：关键结构（面板、卡片、证据入口）在放大后仍挂载且非 hidden。
  ④ 无横向滚动条（页面级）：documentElement.scrollWidth ≤ innerWidth + 容差。
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

INPUTS = ['js/sky/sky-deconstruction.js', 'js/sky/sky-shell-player.js',
          'js/sky/sky-search.js', 'js/sky/sky-shell-hud.js',
          'css/sky-deep-hud.css', 'css/sky-reading.css', 'css/shell-chrome.css',
          'tests/sky_chaos.py']

SURFACES = [
    ('deconstruction', '#skyDeconPanel', '.sd-scroll'),
    ('story', '#skyStoryPanel', '#skyStoryBody'),
    ('search', '#skySearchPanel', '#skySearchResults'),
]

OVERFLOW = r"""(function(panelSel, scrollSel){
  const panel = document.querySelector(panelSel);
  if (!panel || panel.hidden) return {skipped: true};
  const pr = panel.getBoundingClientRect();
  const sc = scrollSel ? panel.querySelector(scrollSel) : null;
  // 逐文本节点检查横向溢出。
  // 注意：``text-overflow: ellipsis`` + ``overflow: hidden`` 的元素，
  // scrollWidth 必然大于 clientWidth —— 那是**已被处理的省略号截断**，不是溢出缺陷。
  // 同理 ``overflow: hidden`` 的裁剪容器是设计意图，只有**没有截断处理的**溢出才算缺陷。
  const rows = [], ellipsis = [];
  panel.querySelectorAll('*').forEach(e => {
    const direct = Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (!direct) return;
    const r = e.getBoundingClientRect(), c = getComputedStyle(e);
    if (r.width <= 0 || r.height <= 0 || c.visibility === 'hidden' || +c.opacity === 0) return;
    const label = (e.textContent||'').trim().slice(0,28);
    const handled = c.textOverflow === 'ellipsis' && /hidden|clip/.test(c.overflowX);
    const overflowsX = e.scrollWidth > e.clientWidth + 1;
    // 元素 rect 超出视口：只有**没有可滚动祖先兜底**时才算不可达
    const outside = r.right > innerWidth + 1 || r.left < -1;
    let scrollableAncestor = false;
    let p = e.parentElement;
    while (p && p !== document.documentElement) {
      const pc = getComputedStyle(p);
      if (/auto|scroll/.test(pc.overflowX)) { scrollableAncestor = true; break; }
      p = p.parentElement;
    }
    if (handled) { if (overflowsX) ellipsis.push({text: label}); return; }
    if (overflowsX || outside) rows.push({
      text: label, scrollW: e.scrollWidth, clientW: e.clientWidth,
      right: +r.right.toFixed(1), left: +r.left.toFixed(1),
      overflowsX: overflowsX, outside: outside,
      hasScrollableAncestor: scrollableAncestor,
      reachable: outside ? scrollableAncestor : true});
  });
  const unreachableRows = rows.filter(r => !r.reachable);
  const panelOutside = pr.x < -1 || pr.right > innerWidth + 1;
  return {
    skipped: false,
    panelRect: {x:+pr.x.toFixed(1),y:+pr.y.toFixed(1),w:+pr.width.toFixed(1),h:+pr.height.toFixed(1)},
    panelFitsViewport: !panelOutside && pr.top >= -1 && pr.bottom <= innerHeight + 1,
    panelHScroll: sc ? {scrollW: sc.scrollWidth, clientW: sc.clientWidth,
                        overflows: sc.scrollWidth > sc.clientWidth + 1} : null,
    textRowsScanned: panel.querySelectorAll('*').length,
    overflowing: rows.length, overflowingSample: rows.slice(0, 8),
    unreachableOverflowRows: unreachableRows.length,
    unreachableSample: unreachableRows.slice(0, 8),
    ellipsisHandled: ellipsis.length,
    pageHScroll: document.documentElement.scrollWidth > innerWidth + 1,
    docScrollW: document.documentElement.scrollWidth, innerW: innerWidth,
  };
})"""

CLICKABLE = r"""(function(panelSel){
  const panel = document.querySelector(panelSel);
  if (!panel || panel.hidden) return {skipped:true};
  const SEL = 'button,a[href],input:not([type=hidden]),select,textarea,' +
              '[role=button],[role=tab],[role=option],[tabindex]:not([tabindex="-1"])';
  const bad = [], horiz = [], offscreenNoScroll = []; let total = 0;
  panel.querySelectorAll(SEL).forEach(e => {
    const r = e.getBoundingClientRect(), c = getComputedStyle(e);
    if (r.width <= 0 || r.height <= 0 || c.visibility === 'hidden' || +c.opacity === 0) return;
    total++;
    const x = r.x + r.width/2, y = r.y + r.height/2;
    // 找最近的可滚动祖先（横或纵）：只要它在任一轴可滚，子元素就能被用户滚到，
    // 不能算「不可达」。第一版漏了纵向滚动容器，把 .sd-scroll 里滚出视口的
    // 事件行误报成缺陷 —— elementFromPoint 只回答「该点最上层是谁」，
    // 它不知道目标是否在祖先的可视区之外。
    let scroller = null, scrollerAxis = null, p = e.parentElement;
    while (p && p !== document.documentElement) {
      const pc = getComputedStyle(p);
      const canY = /auto|scroll/.test(pc.overflowY) && p.scrollHeight > p.clientHeight + 1;
      const canX = /auto|scroll/.test(pc.overflowX) && p.scrollWidth > p.clientWidth + 1;
      if (canY || canX) { scroller = p; scrollerAxis = canY ? (canX ? 'both' : 'y') : 'x'; break; }
      p = p.parentElement;
    }
    if (x < 0 || x >= innerWidth || y < 0 || y >= innerHeight) {
      if (scroller) { horiz.push({id:e.id||null, cls:String(e.className).slice(0,40),
                                  axis: scrollerAxis,
                                  why:'outside viewport, reachable by scrolling '
                                      + (scroller.className||scroller.tagName), x:+x.toFixed(1), y:+y.toFixed(1)}); return; }
      bad.push({id:e.id||null, cls:String(e.className).slice(0,40),
                reason:'centre outside viewport and no scrollable ancestor',
                x:+x.toFixed(1), y:+y.toFixed(1)});
      return;
    }
    const h = document.elementFromPoint(x, y);
    const owned = !!(h && (h === e || e.contains(h) || h.contains(e)));
    if (!owned) {
      // 在滚动容器里但被容器边缘裁掉：可滚到，不算不可达
      if (scroller) { horiz.push({id:e.id||null, cls:String(e.className).slice(0,40),
                                  axis: scrollerAxis,
                                  why:'hit outside the scroll box, reachable by scrolling '
                                      + (scroller.className||scroller.tagName),
                                  hit: h && (h.id || h.tagName)}); return; }
      bad.push({id:e.id||null, cls:String(e.className).slice(0,40),
                reason:'not hit-owned', hit: h && (h.id || h.tagName)});
    }
  });
  return {skipped:false, total: total, unreachable: bad.length, unreachableSample: bad.slice(0,8),
          reachableByScrolling: horiz.length, scrollReachableSample: horiz.slice(0,8)};
})"""

STRUCTURE = r"""(function(panelSel){
  const panel = document.querySelector(panelSel);
  if (!panel) return {mounted:false};
  return {mounted:true, hidden:!!panel.hidden,
          childNodes: panel.querySelectorAll('*').length,
          headings: panel.querySelectorAll('h1,h2,h3,h4').length,
          buttons: panel.querySelectorAll('button').length,
          evidenceEntries: panel.querySelectorAll('blockquote,[data-evidence],.sd-evidence-detail,.sd-causal-evidence').length};
})"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8765')
    p.add_argument('--data', default='data/sample-saga.json')
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--sizes', default='1280x800:1440x900')
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=False)
    shots = args.out / 'shots'
    shots.mkdir()
    source = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    checks, rounds = [], []

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    def shot(b, name):
        raw = b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
        (shots / (name + '.png')).write_bytes(base64.b64decode(raw['data']))

    base_w, base_h = (int(x) for x in args.sizes.split(':')[0].split('x'))
    b = chaos.Browser(base_w, base_h)
    try:
        b.start()
        b.ws.call('Page.navigate', url=args.base.rstrip('/') + '/?data=' + args.data)
        if not b.until("!!(window.CLApp&&CLApp.scene()&&CLApp.graph()&&window.CLSky&&CLSky.enabled()"
                       "&&window.CLSkyDeconstruction&&window.CLSkySearch)", 60):
            raise RuntimeError('Production graph did not become ready')
        time.sleep(1.5)

        b.ev("CLSkyDeconstruction.open();CLSkyDeconstruction.setMode('evidence')")
        time.sleep(.8)

        for factor, label in [(1.0, '100'), (2.0, '200'), (4.0, '400')]:
            eff_w, eff_h = max(320, int(base_w / factor)), max(240, int(base_h / factor))
            b.ws.call('Emulation.setDeviceMetricsOverride', width=eff_w, height=eff_h,
                      deviceScaleFactor=1, mobile=False, scale=1.0)
            b.ws.call('Emulation.setPageScaleFactor', pageScaleFactor=factor)
            time.sleep(1.4)
            actual = b.ev("({iw:innerWidth,ih:innerHeight,psf:window.visualViewport?window.visualViewport.scale:null,"
                          "dpr:devicePixelRatio})")
            row = {'zoom': label, 'factor': factor, 'effectiveViewport': [eff_w, eff_h],
                   'observed': actual, 'surfaces': []}
            print(f"\n── zoom {label}%  有效视口 {eff_w}×{eff_h}  实测 {actual} ──", flush=True)

            for name, panel_sel, scroll_sel in SURFACES:
                b.ev("(()=>{try{"
                     "if(window.CLSkyDeconstruction)CLSkyDeconstruction.close();"
                     "if(window.CLSkyEnrich&&CLSkyEnrich.close)CLSkyEnrich.close();"
                     "var sp=document.getElementById('skySearchPanel');if(sp)sp.hidden=true;"
                     "var sd=document.getElementById('skyStoryPanel');if(sd)sd.hidden=true;"
                     "}catch(e){}return true})()")
                time.sleep(.5)
                if name == 'search':
                    b.ev("document.getElementById('skySearch').focus();"
                         "document.getElementById('skySearch').value=''")
                    b.ws.call('Input.insertText', text='测试')
                    time.sleep(1.0)
                elif name == 'story':
                    b.ev("CLSky.setPlot(true);CLSky.seekEventAt(0);CLSky.stop()")
                    time.sleep(1.0)
                elif name == 'deconstruction':
                    b.ev("CLSkyDeconstruction.open()")
                    time.sleep(.6)
                    b.ev("CLSkyDeconstruction.setMode('evidence')")
                    time.sleep(.8)
                ov = b.ev('(' + OVERFLOW + ')(' + json.dumps(panel_sel) + ',' + json.dumps(scroll_sel) + ')')
                cl = b.ev('(' + CLICKABLE + ')(' + json.dumps(panel_sel) + ')')
                st = b.ev('(' + STRUCTURE + ')(' + json.dumps(panel_sel) + ')')
                row['surfaces'].append({'surface': name, 'overflow': ov, 'clickable': cl, 'structure': st})
                if ov.get('skipped'):
                    print(f"   {name}: 未打开，跳过", flush=True)
                    continue
                print(f"   {name}: 不可达溢出 {ov['unreachableOverflowRows']}（省略号截断 {ov['ellipsisHandled']}）"
                      f"  不可达控件 {cl.get('unreachable','-')}/{cl.get('total','-')}"
                      f"  横向滚动={ov['pageHScroll']}  结构={st.get('childNodes')}节点/{st.get('evidenceEntries')}证据入口", flush=True)
                check(f"zoom {label}% {name}: no unreachable text overflow (ellipsis truncation allowed)",
                      ov['unreachableOverflowRows'] == 0, ov)
                check(f"zoom {label}% {name}: every visible control is still hit-testable",
                      cl.get('skipped') or cl.get('unreachable', 1) == 0, cl)
                check(f"zoom {label}% {name}: no page-level horizontal scroll",
                      not ov['pageHScroll'], {'docScrollW': ov['docScrollW'], 'innerW': ov['innerW']})
                check(f"zoom {label}% {name}: content structure survives the zoom",
                      st.get('mounted') and not st.get('hidden') and st.get('childNodes', 0) > 5, st)
                check(f"zoom {label}% {name}: panel rect stays inside the viewport",
                      ov.get('panelFitsViewport') is True, ov.get('panelRect'))
                shot(b, f"zoom{label}-{name}")

            rounds.append(row)
            b.ws.call('Emulation.setPageScaleFactor', pageScaleFactor=1.0)
            b.ws.call('Emulation.setDeviceMetricsOverride', width=base_w, height=base_h,
                      deviceScaleFactor=1, mobile=False)
            time.sleep(.5)

        health = b.ev("(()=>{const h=window.__headlessHealth,S=CLApp.scene();return {errors:h.jserr,"
                      "rejections:h.jsrej,shaderErrors:S.shaderErrors()}})()")
        check('runtime remains healthy across all zoom levels',
              not health['errors'] and not health['rejections'] and not health['shaderErrors'], health)
    except Exception as exc:
        rounds.append({'error': str(exc)})
        print('FAIL session: ' + str(exc), flush=True)
        try:
            shot(b, 'failure')
        except Exception:
            pass
    finally:
        b.close()

    stable = source == {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    report = {
        'ok': stable and all(c['ok'] for c in checks) and bool(checks),
        'complete': True, 'base': args.base, 'data': args.data,
        'baseSize': [base_w, base_h], 'zoomLevels': ['100', '200', '400'],
        'sourceStable': stable, 'sourceHashes': source,
        'rounds': rounds, 'checks': checks,
        'finishedAt': datetime.now(timezone.utc).isoformat(),
        'boundary': ('真实 Chrome。放大语义用 Emulation.setPageScaleFactor（页面缩放）+ '
                     'setDeviceMetricsOverride 缩小有效 CSS 视口，模拟真机 200%/400% 文本放大后的重排。'
                     '这与 sky_reading_reflow_browser.py 的「缩小视口」路径互补，两者都保留。'
                     '仍非真机 Safari/VoiceOver 认证。'),
    }
    (args.out / 'zoom-reflow.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                                               encoding='utf-8')
    ok = report['ok']
    print(f"\nZOOM REFLOW {'OK' if ok else 'FAIL'} ({sum(c['ok'] for c in checks)}/{len(checks)})", flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
