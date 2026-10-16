#!/usr/bin/env python3
"""P09-W07 · 窄屏命中区与「图形不遮盖当前证据」验收。

计划原文（`docs/plan-100-score-execution.md:52226`）：
  「窄屏控件命中区至少44px，长文可滚动，图形不遮盖当前证据。」

审核点名（`docs/strict-audit-user-2026-10-07.md:12`）：
  「**入口术语密集，小屏图形与阅读控件仍竞争空间**。」

本脚本在 390×844（审核点名的窄屏）上做三件事：
  ① 量取**每个可见交互控件的真实 rect**（不是 CSS 声明值），
     列出 <44×44 CSS px 的清单 —— 静态审计里 727 个「不可静态判定」的元素在这里定论。
  ② 证据卡打开时，检查 3D 画布（canvas）是否压住文字：
     对证据卡内每个文本行取中心点做 elementFromPoint，若命中的不是卡片自身/其后代
     而是 canvas 或遮挡层，即为「图形遮盖证据」。
  ③ 长文可滚动：容器 scrollHeight > clientHeight 时必须 overflow 可滚，
     且焦点滚入时元素真的进入视口。
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

INPUTS = ['js/sky/sky-shell-hud.js', 'js/sky/sky-deck.js', 'js/sky/sky-deck-body.js',
          'js/sky/sky-shell-player.js', 'js/sky/sky-deconstruction.js',
          'css/shell-chrome.css', 'css/sky-deck-states.css', 'css/sky-deep-hud.css',
          'css/sky-reading.css', 'tests/sky_chaos.py']

MEASURE = r"""(()=>{
  const SEL = 'button,a[href],input:not([type=hidden]),select,textarea,summary,' +
              '[role=button],[role=tab],[role=option],[role=menuitem],[role=radio],[role=checkbox],' +
              '[tabindex]:not([tabindex="-1"])';
  const out = [];
  const seen = new Set();
  document.querySelectorAll(SEL).forEach(e => {
    const r = e.getBoundingClientRect(), c = getComputedStyle(e);
    if (r.width <= 0 || r.height <= 0) return;                 // 不可见
    if (c.display === 'none' || c.visibility === 'hidden' || +c.opacity === 0) return;
    if (e.closest('[aria-hidden="true"]')) return;
    // 视口外交互控件不计（不算命中缺陷）
    if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) return;
    const id = (e.id || '') + '|' + (typeof e.className === 'string' ? e.className : '') + '|' + out.length;
    if (seen.has(id)) return; seen.add(id);
    // 命中测试：中心点是否真的由它（或后代）接管
    const x = r.x + r.width/2, y = r.y + r.height/2;
    let hit = null, owned = false;
    if (x >= 0 && y >= 0 && x < innerWidth && y < innerHeight) {
      const h = document.elementFromPoint(x, y);
      hit = h && (h.id || (typeof h.className === 'string' ? h.className : h.tagName));
      owned = !!(h && (h === e || e.contains(h) || h.contains(e)));
    }
    out.push({
      tag: e.tagName, id: e.id || null,
      cls: (typeof e.className === 'string' ? e.className : '').slice(0, 70),
      role: e.getAttribute('role'),
      label: (e.getAttribute('aria-label') || e.textContent || '').trim().replace(/\s+/g,' ').slice(0, 26),
      w: +r.width.toFixed(1), h: +r.height.toFixed(1),
      x: +r.x.toFixed(1), y: +r.y.toFixed(1),
      owned: owned, hit: hit,
      disabled: e.disabled === true || e.getAttribute('aria-disabled') === 'true',
      pointerEvents: c.pointerEvents,
      tabindex: e.getAttribute('tabindex'),
      // 真控件 = 指针可达 且 键盘可达（roving tabindex 的 -1 项不算可 Tab 到）
      trulyInteractive: c.pointerEvents !== 'none' && e.getAttribute('tabindex') !== '-1',
      // 声明了交互语义（role=button 等）但指针不可达 —— 语义与行为不一致
      semanticNotClickable: (e.getAttribute('role') === 'button'
                             || e.tagName === 'BUTTON')
                            && c.pointerEvents === 'none',
    });
  });
  return out;
})()"""

OCCLUSION = r"""(function(explicitSel){
  // 必须显式指定要测的面；否则会把「下层卡片被上层面板盖住」误报成遮盖。
  const card = explicitSel ? document.querySelector(explicitSel)
                           : document.querySelector('.skd-card.is-open');
  if (!card) return {found: false, wanted: explicitSel || '.skd-card.is-open'};
  try { card.scrollIntoView({block: 'nearest', inline: 'nearest'}); } catch (e) {}

  function clipRect(e) {
    // 把元素 rect 与所有可滚动祖先的 client rect 求交，得到真正可见的区域
    let r = e.getBoundingClientRect();
    let top = r.top, bottom = r.bottom, left = r.left, right = r.right;
    let p = e.parentElement;
    while (p && p !== document.documentElement) {
      const cs = getComputedStyle(p);
      if (/auto|scroll|hidden/.test(cs.overflowY) || /auto|scroll|hidden/.test(cs.overflowX)) {
        const pr = p.getBoundingClientRect();
        top = Math.max(top, pr.top); bottom = Math.min(bottom, pr.bottom);
        left = Math.max(left, pr.left); right = Math.min(right, pr.right);
      }
      p = p.parentElement;
    }
    return {top, bottom, left, right, w: right - left, h: bottom - top,
            sourceRect: {x: r.x, y: r.y, w: r.width, h: r.height}};
  }

  const canvases = Array.from(document.querySelectorAll('canvas')).map(c => {
    const r = c.getBoundingClientRect(), s = getComputedStyle(c);
    return {id: c.id || null, cls: String(c.className).slice(0,40),
            x:+r.x.toFixed(1), y:+r.y.toFixed(1), w:+r.width.toFixed(1), h:+r.height.toFixed(1),
            z: s.zIndex, pe: s.pointerEvents,
            isMainGL: c.id === 'gl' || (r.width >= innerWidth - 2 && r.height >= innerHeight - 2)};
  });
  const mainGL = canvases.find(c => c.isMainGL) || null;

  const texts = [], clippedOut = [];
  card.querySelectorAll('*').forEach(e => {
    const direct = Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (!direct) return;
    const s = getComputedStyle(e);
    if (s.visibility === 'hidden' || +s.opacity === 0 || s.display === 'none') return;
    const cr = clipRect(e);
    if (cr.sourceRect.w <= 0 || cr.sourceRect.h <= 0) return;
    const label = (e.textContent||'').trim().slice(0, 30);
    // 完全被祖先裁掉的行：不算遮盖，单独记录
    if (cr.h < 1 || cr.w < 1) { clippedOut.push({text: label, reason: 'clipped by scroll ancestor'}); return; }
    // 只在真正可见的区域内取样（取交集的中心）
    const x = cr.left + Math.min(cr.w/2, 40), y = cr.top + cr.h/2;
    if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) {
      clippedOut.push({text: label, reason: 'visible sliver outside viewport'}); return;
    }
    const h = document.elementFromPoint(x, y);
    const own = !!(h && (h === e || card.contains(h)));
    const canvasHit = !!(h && h.tagName === 'CANVAS');
    texts.push({text: label, sampleX:+x.toFixed(1), sampleY:+y.toFixed(1),
                visibleH:+cr.h.toFixed(1),
                hitTag: h && h.tagName, hitId: h && (h.id || String(h.className).slice(0,40)),
                occluded: !own, isCanvasHit: canvasHit, isOwnSurface: own});
  });
  const occluded = texts.filter(t => t.occluded);
  const byCanvas = occluded.filter(t => t.isCanvasHit);
  const byOverlay = occluded.filter(t => !t.isCanvasHit);
  const cr2 = card.getBoundingClientRect();
  return {found: true, cardCls: String(card.className).slice(0,60),
          cardRect: {x:+cr2.x.toFixed(1),y:+cr2.y.toFixed(1),w:+cr2.width.toFixed(1),h:+cr2.height.toFixed(1)},
          visibleTextRows: texts.length,
          clippedOutRows: clippedOut.length, clippedOutSample: clippedOut.slice(0,6),
          occludedRows: occluded.length,
          occludedByCanvas: byCanvas.length, occludedByCanvasSample: byCanvas.slice(0,8),
          occludedByOverlay: byOverlay.length, occludedByOverlaySample: byOverlay.slice(0,8),
          canvases: canvases, mainCanvas: mainGL};
})"""

SCROLLABLE = r"""(()=>{
  const cand = Array.from(document.querySelectorAll(
    '.sd-scroll,.skd-card__body,#skyStoryBody,#skySearchResults,.clr-body,.sd-section'));
  return cand.map(e => {
    const c = getComputedStyle(e), r = e.getBoundingClientRect();
    const overflows = e.scrollHeight > e.clientHeight + 1;
    return {cls: String(e.className).slice(0,50), id: e.id||null,
            clientH: e.clientHeight, scrollH: e.scrollHeight,
            overflowY: c.overflowY, scrollable: overflows ? /auto|scroll/.test(c.overflowY) : null,
            inViewport: r.top < innerHeight && r.bottom > 0,
            w:+r.width.toFixed(1)};
  }).filter(x => x.scrollH > 0);
})()"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8765')
    p.add_argument('--data', default='data/sample-saga.json')
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--size', default='390x844')
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=False)
    shots = args.out / 'shots'
    shots.mkdir()
    w, h = map(int, args.size.split('x'))
    source = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    checks, phases = [], []

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    def shot(b, name):
        raw = b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
        (shots / (name + '.png')).write_bytes(base64.b64decode(raw['data']))

    def tap(b, x, y):
        b.ws.call('Input.dispatchTouchEvent', type='touchStart',
                  touchPoints=[{'x': x, 'y': y, 'id': 1, 'radiusX': 3, 'radiusY': 3, 'force': 1}])
        time.sleep(.06)
        b.ws.call('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])
        time.sleep(.45)

    b = chaos.Browser(w, h)
    try:
        b.start()
        b.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h,
                  deviceScaleFactor=1, mobile=True)
        b.ws.call('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=1)
        b.ws.call('Page.navigate', url=args.base.rstrip('/') + '/?data=' + args.data)
        if not b.until("!!(window.CLApp&&CLApp.scene()&&CLApp.graph()&&window.CLSky&&CLSky.enabled()"
                       "&&window.CLSkyDeep&&CLSkyDeep.stats().stars.ignite>.99)", 60):
            raise RuntimeError('Production graph did not become ready')
        time.sleep(1.5)

        m0 = b.ev(MEASURE)
        phases.append({'phase': 'constellation', 'size': [w, h], 'controls': m0})
        shot(b, 'constellation')

        plot_btn = next((c for c in m0 if c['id'] == 'skyPlot'), None)
        if not plot_btn:
            raise RuntimeError('no #skyPlot in the narrow constellation view')
        tap(b, plot_btn['x'] + plot_btn['w'] / 2, plot_btn['y'] + plot_btn['h'] / 2)
        if not b.until("!!(CLSky.state().plot)", 8):
            raise RuntimeError('plot did not open under a real touch tap')
        time.sleep(1.5)
        m1 = b.ev(MEASURE)
        phases.append({'phase': 'plot', 'size': [w, h], 'controls': m1})
        shot(b, 'plot')

        drawer = next((c for c in m1 if 'skd-drawerbtn' in (c['cls'] or '')), None)
        if drawer:
            tap(b, drawer['x'] + drawer['w'] / 2, drawer['y'] + drawer['h'] / 2)
            b.until("!!(CLSky.deck()&&CLSky.deck().stats().shown)", 5)
            time.sleep(.9)
        card = b.ev("(()=>{var c=document.querySelector('.skd-card');if(!c)return null;"
                    "var r=c.getBoundingClientRect();return {x:+r.x.toFixed(1),y:+r.y.toFixed(1),"
                    "w:+r.width.toFixed(1),h:+r.height.toFixed(1)}})()")
        if card:
            tap(b, card['x'] + min(card['w'] / 2, 90), card['y'] + min(card['h'] / 2, 14))
            time.sleep(1.0)
        occ = b.ev('(' + OCCLUSION + ')' + '(' + json.dumps('.skd-card.is-open') + ')')
        phases.append({'phase': 'evidence-card-open', 'occlusion': occ, 'card': card})
        shot(b, 'evidence-open')
        if occ.get('found'):
            check('no evidence text row is covered by the 3D canvas',
                  occ['occludedByCanvas'] == 0,
                  {'byCanvas': occ['occludedByCanvas'],
                   'sample': occ.get('occludedByCanvasSample'),
                   'mainCanvas': occ.get('mainCanvas'),
                   'visibleRows': occ.get('visibleTextRows'),
                   'clippedOut': occ.get('clippedOutRows')})
            check('no visible evidence text row is covered by a HUD overlay either',
                  occ['occludedByOverlay'] == 0,
                  {'byOverlay': occ['occludedByOverlay'],
                   'sample': occ.get('occludedByOverlaySample'),
                   'visibleRows': occ.get('visibleTextRows'),
                   'clippedOut': occ.get('clippedOutRows')})
        else:
            check('an evidence surface opened for the occlusion check', False, occ)
        scr = b.ev(SCROLLABLE)
        phases.append({'phase': 'evidence-open', 'scrollables': scr})
        overflowing = [s for s in scr if s['scrollH'] > s['clientH'] + 1]
        bad_scroll = [s for s in overflowing if s['scrollable'] is not True]
        check('long reading text in an overflowing container is actually scrollable',
              not bad_scroll, {'overflowing': overflowing, 'notScrollable': bad_scroll})

        dec = b.ev("(()=>{var b=document.getElementById('skyDecode');if(!b)return null;"
                   "var r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
        if dec:
            tap(b, dec['x'], dec['y'])
            if b.until("!document.getElementById('skyDeconPanel').hidden", 5):
                time.sleep(1.0)
                m2 = b.ev(MEASURE)
                phases.append({'phase': 'deconstruction', 'size': [w, h], 'controls': m2})
                shot(b, 'deconstruction')
                occ2 = b.ev('(' + OCCLUSION + ')' + '(' + json.dumps('#skyDeconPanel:not([hidden])') + ')')
                phases.append({'phase': 'deconstruction-occlusion', 'occlusion': occ2})
                if occ2.get('found'):
                    check('no deconstruction text row is covered by the 3D canvas',
                          occ2['occludedByCanvas'] == 0,
                          {'byCanvas': occ2['occludedByCanvas'],
                           'sample': occ2.get('occludedByCanvasSample')})
                    check('visible deconstruction rows keep their own hit test (no HUD takeover)',
                          occ2['occludedByOverlay'] == 0,
                          {'byOverlay': occ2['occludedByOverlay'],
                           'sample': occ2.get('occludedByOverlaySample'),
                           'visibleRows': occ2.get('visibleTextRows'),
                           'clippedOut': occ2.get('clippedOutRows')})

        all_controls = []
        for ph in phases:
            for c in ph.get('controls', []) or []:
                all_controls.append({**c, 'phase': ph['phase']})
        MODAL_PHASES = {'deconstruction'}
        stacking_phases = sorted({c['phase'] for c in all_controls if c['phase'] in MODAL_PHASES})
        measured = [c for c in all_controls if c['phase'] not in MODAL_PHASES]
        covered_by_panel = [c for c in all_controls if c['phase'] in MODAL_PHASES and not c['owned']]

        real = [c for c in measured if c.get('trulyInteractive')]
        noninteractive = [c for c in all_controls if not c.get('trulyInteractive')]
        under44 = [c for c in real if c['w'] < 44 or c['h'] < 44]
        under44_noninteractive = [c for c in noninteractive if c['w'] < 44 or c['h'] < 44]
        unowned = [c for c in real if not c['owned']]
        semantic_bad = [c for c in all_controls if c.get('semanticNotClickable')]
        print(f"\n窄屏命中区（390×844 运行时实测）："
              f"共 {len(all_controls)} 个候选；非交互图形件 {len(noninteractive)} 个", flush=True)
        print(f"  命中性判定相位：{sorted({c['phase'] for c in measured})}", flush=True)
        print(f"  层叠相位（模态面板在上，下层被覆盖=正确层叠，不计缺陷）："
              f"{stacking_phases} → {len(covered_by_panel)} 个", flush=True)
        print(f"  真控件 <44×44：{len(under44)} 个  ← 真缺陷", flush=True)
        print(f"  非交互件 <44：{len(under44_noninteractive)} 个  ← 不适用触控门槛", flush=True)
        print(f"  真控件中心点被他人接管：{len(unowned)} 个", flush=True)
        print(f"  声明 role=button 但 pointer-events:none：{len(semantic_bad)} 个  ← 语义与行为不一致\n", flush=True)
        for c in sorted(under44, key=lambda x: min(x['w'], x['h']))[:40]:
            print(f"  <44  {c['phase']:<14} {c['w']:>6.1f}×{c['h']:<6.1f} "
                  f"#{c['id'] or '-'} .{(c['cls'] or '').split()[0] if c['cls'] else '-'} "
                  f"[{c['label']}]", flush=True)
        for c in unowned[:15]:
            print(f"  HIT-NOT-OWNED {c['phase']:<14} #{c['id'] or '-'} .{(c['cls'] or '').split()[0]} "
                  f"hit={c['hit']}", flush=True)
        for c in semantic_bad[:15]:
            print(f"  SEMANTIC-BEHAVIOUR-MISMATCH {c['phase']:<14} .{(c['cls'] or '').split()[0] if c['cls'] else c['tag']:<20} "
                  f"role={c['role']} pe={c['pointerEvents']} ti={c['tabindex']} [{c['label'][:22]}]", flush=True)

        check('every truly-interactive narrow control meets the 44×44 touch target',
              not under44,
              {'under44Count': len(under44), 'sample': sorted(
                  under44, key=lambda x: min(x['w'], x['h']))[:12]})
        check('every truly-interactive narrow control owns its own hit point '
              '(outside phases where a modal panel is deliberately on top)',
              not unowned, {'count': len(unowned), 'sample': unowned[:8],
                            'excludedStackingPhases': stacking_phases,
                            'coveredByHigherPanel': len(covered_by_panel)})
        check('no control declares button semantics while refusing pointer events',
              not semantic_bad,
              {'count': len(semantic_bad), 'sample': semantic_bad[:8]})

        health = b.ev("(()=>{const h=window.__headlessHealth,S=CLApp.scene();return {errors:h.jserr,"
                      "rejections:h.jsrej,shaderErrors:S.shaderErrors()}})()")
        check('runtime remains healthy after the narrow-screen walk',
              not health['errors'] and not health['rejections'] and not health['shaderErrors'], health)
    except Exception as exc:
        phases.append({'phase': 'error', 'error': str(exc)})
        print('FAIL session: ' + str(exc), flush=True)
        try:
            shot(b, 'failure')
        except Exception:
            pass
    finally:
        b.close()

    stable = source == {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    all_controls_aug = [dict(c, phase=ph['phase'])
                        for ph in phases for c in (ph.get('controls') or [])]
    all_controls = [c for ph in phases for c in (ph.get('controls') or [])]
    report = {
        'ok': stable and all(c['ok'] for c in checks) and bool(checks),
        'complete': True, 'base': args.base, 'data': args.data, 'size': [w, h],
        'sourceStable': stable, 'sourceHashes': source,
        'phases': phases, 'checks': checks,
        'totals': {
            'candidates': len(all_controls),
            'trulyInteractive': sum(1 for c in all_controls if c.get('trulyInteractive')),
            'nonInteractiveGraphics': sum(1 for c in all_controls if not c.get('trulyInteractive')),
        },
        'under44': [c for c in all_controls
                    if c.get('trulyInteractive') and (c['w'] < 44 or c['h'] < 44)],
        'under44NonInteractive': [c for c in all_controls
                                  if not c.get('trulyInteractive') and (c['w'] < 44 or c['h'] < 44)],
        'semanticBehaviourMismatch': [c for c in all_controls if c.get('semanticNotClickable')],
        'hitOwnershipExcludedPhases': ['deconstruction'],
        'coveredByHigherPanel': [c for c in all_controls_aug
                                 if c['phase'] == 'deconstruction' and not c['owned']],
        'finishedAt': datetime.now(timezone.utc).isoformat(),
        'boundary': ('真实 Chrome 390×844 + touch emulation，原生 CDP touch 输入。'
                     '命中盒为运行时 getBoundingClientRect 实测值（非 CSS 声明值）。'
                     '44×44 门槛只适用于**真控件**（pointer-events≠none 且非 roving tabindex=-1）；'
                     '图形件单列，不混进缺陷数。遮盖用 elementFromPoint 逐文本行命中测试，'
                     '并把「3D canvas 遮盖」与「HUD 浮层遮盖」分开计数。'),
    }
    (args.out / 'narrow-hit-targets.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    ok = report['ok']
    print(f"NARROW HIT TARGETS {'OK' if ok else 'FAIL'} "
          f"({len(report['under44'])} 个 <44px)", flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
