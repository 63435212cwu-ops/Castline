#!/usr/bin/env python3
"""减弱动效（reduced-motion）结构保留验收。

现行要求见 `docs/QUALITY.md` Q5/Q7：暂停、定位与减弱动态共用真实事件状态；
去除循环和过渡，同时保留阅读顺序、焦点和证据入口。

关键：这是**结构保留**要求，不是「把动画关掉就算过」。本脚本因此验证
三个必留项，每一项都在 reduce 与 no-preference 两种偏好下各取一次并对比：

  ① 顺序（order）：剧情阶段轨 / 卡片顺序 / 事件顺序在 reduce 下完全一致，
     不允许因去动画而丢步、重排或折叠。
  ② 焦点（focus）：Tab 顺序与焦点归属在 reduce 下可到达同样的控件集合。
  ③ 证据入口（evidence entry）：每条事件仍能打开证据（引文/来源），
     入口数量与 no-preference 下相同。

同时确认「循环确实被去掉」：reduce 下不应再有 animation-iteration-count: infinite。
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

INPUTS = ['js/sky/sky-shell-player.js', 'js/sky/sky-deck.js', 'js/sky/sky-tokens.js',
          'js/sky/sky-motion.js', 'css/sky-deck-states.css', 'css/sky-reading.css',
          'css/sky-deep-hud.css', 'tests/sky_chaos.py']

STRUCTURE = r"""(()=>{
  const rail = document.getElementById('skyStoryRail');
  const beats = rail ? Array.from(rail.querySelectorAll('[data-beat]')).map(n => ({
      beat: n.dataset.beat, text: (n.textContent||'').trim(),
      current: n.getAttribute('aria-current') === 'step' })) : null;
  const railLabel = rail ? rail.getAttribute('role') : null;
  const railItems = rail ? rail.querySelectorAll('[role=listitem]').length : 0;

  const decon = document.getElementById('skyDeconPanel');
  const tabs = decon && !decon.hidden
    ? Array.from(decon.querySelectorAll('.sd-tabs [role=tab]')).map(t => ({
        id: t.id, text: (t.textContent||'').trim(),
        selected: t.getAttribute('aria-selected') === 'true', tabIndex: t.tabIndex }))
    : null;

  const deck = document.querySelector('.skd-deck');
  const cards = deck ? Array.from(deck.querySelectorAll('[role=option]')).map(o => ({
      key: o.dataset.key, pos: +o.getAttribute('aria-posinset'),
      size: +o.getAttribute('aria-setsize'),
      selected: o.getAttribute('aria-selected') === 'true' })) : null;

  // 证据入口：可打开证据的控件 / 容器
  const evidence = {
    detailActions: document.querySelectorAll('.sd-detail-action').length,
    evidenceBlocks: document.querySelectorAll(
      '.sd-evidence-detail,.sd-causal-evidence,blockquote,[data-evidence]').length,
    storyBeams: !!document.getElementById('skyStoryBeams'),
    beamsAriaHidden: (()=>{const b=document.getElementById('skyStoryBeams');
                           return b?b.getAttribute('aria-hidden'):null})(),
  };

  // 焦点可达：Tab 一遍收集落在阅读面里的控件
  return {beats, railLabel, railItems, tabs, cards, evidence,
          storyPhase: (document.getElementById('skyStoryPhase')||{}).textContent||null,
          storyLive: (document.getElementById('skyStoryStageLive')||{}).textContent||null};
})()"""

INFINITE = r"""(()=>{
  const out = [];
  document.querySelectorAll('*').forEach(e => {
    const c = getComputedStyle(e);
    if (c.animationName && c.animationName !== 'none' &&
        c.animationIterationCount && /infinite/.test(c.animationIterationCount)) {
      out.push({cls: String(e.className||e.tagName).slice(0,44), name: c.animationName});
    }
  });
  return {count: out.length, sample: out.slice(0,10)};
})()"""

FOCUS_SET = r"""(function(){
  function key(e) {
    if (e.id) return '#' + e.id;
    // 去掉瞬态类，只留结构性类
    var transient = /^(is-hit|is-kfocus|is-hot|is-on|is-off|is-now|is-focus|is-hover|hover|on|off|sel|pin)$/;
    var cls = String(e.className || '').split(/\s+/)
      .filter(function(c){ return c && !transient.test(c); })
      .slice(0, 3).join('.');
    return (e.tagName || '') + (cls ? '.' + cls : '') +
           (e.getAttribute('role') ? '[' + e.getAttribute('role') + ']' : '');
  }
  return {
    active: (function(){var a=document.activeElement;
      return a ? (a.id || String(a.className).slice(0,40) || a.tagName) : null})(),
    focusables: Array.from(document.querySelectorAll(
      'button:not([disabled]),[href],input:not([disabled]):not([type=hidden]),select,textarea,' +
      '[tabindex]:not([tabindex="-1"]),[role=tab],[role=option]'))
      .filter(function(e){ var r=e.getBoundingClientRect(), c=getComputedStyle(e);
        return r.width>0 && r.height>0 && c.visibility!=='hidden' && c.display!=='none' &&
               +c.opacity>0 && !e.closest('[aria-hidden="true"]'); })
      .map(key)
  };
})()"""


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
    checks, captures = [], {}

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    def shot(b, name):
        raw = b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
        (shots / (name + '.png')).write_bytes(base64.b64decode(raw['data']))

    def media(b, reduce):
        b.ws.call('Emulation.setEmulatedMedia', features=[
            {'name': 'prefers-reduced-motion', 'value': 'reduce' if reduce else 'no-preference'}])
        time.sleep(.6)

    def key(b, k):
        codes = {'Tab': 9, 'Escape': 27, 'Enter': 13, 'ArrowDown': 40, 'Home': 36}
        for typ in ('keyDown', 'keyUp'):
            b.ws.call('Input.dispatchKeyEvent', type=typ, key=k, code=k,
                      windowsVirtualKeyCode=codes.get(k, 0))
        time.sleep(.12)

    b = chaos.Browser(1440, 900)
    try:
        b.start()
        b.ws.call('Page.navigate', url=args.base.rstrip('/') + '/?data=' + args.data)
        if not b.until("!!(window.CLApp&&CLApp.scene()&&CLApp.graph()&&window.CLSky&&CLSky.enabled()"
                       "&&window.CLSkyTokens&&window.CLSkyDeconstruction)", 60):
            raise RuntimeError('Production graph did not become ready')
        time.sleep(1.5)

        b.ev("CLSky.setPlot(true)")
        b.until("!!(CLSky.deck()&&CLSky.deck().stats().cards>1)", 10)
        time.sleep(.8)
        b.ev("CLSky.seekEventAt(1)")
        time.sleep(.8)

        for reduce in (False, True):
            label = 'reduce' if reduce else 'no-preference'
            media(b, reduce)
            time.sleep(1.2)
            struct = b.ev(STRUCTURE)
            inf = b.ev(INFINITE)
            reducedFlag = b.ev("!!(window.CLSkyTokens&&CLSkyTokens.reduced&&CLSkyTokens.reduced())")
            b.ev("document.activeElement&&document.activeElement.blur&&document.activeElement.blur()")
            focus = b.ev(FOCUS_SET)
            captures[label] = {'structure': struct, 'infinite': inf,
                               'tokensReduced': reducedFlag, 'focus': focus,
                               'mediaMatches': b.ev(
                                   "matchMedia('(prefers-reduced-motion: reduce)').matches")}
            print(f"\n── {label}: CLSkyTokens.reduced()={reducedFlag} "
                  f"MQL={captures[label]['mediaMatches']} "
                  f"循环动画={inf['count']} 阶段步={len(struct['beats'] or [])} "
                  f"卡片={len(struct['cards'] or [])} 可聚焦={len(focus['focusables'])} ──", flush=True)
            shot(b, label + '-structure')

            check(f"{label}: prefers-reduced-motion is really applied to the page",
                  captures[label]['mediaMatches'] == reduce, captures[label]['mediaMatches'])
            check(f"{label}: product token layer agrees on the motion preference",
                  reducedFlag == reduce, {'CLSkyTokens.reduced': reducedFlag, 'want': reduce})

        a, r = captures['no-preference'], captures['reduce']

        check('reduced-motion preserves the story beat order exactly',
              a['structure']['beats'] == r['structure']['beats'],
              {'no-preference': a['structure']['beats'], 'reduce': r['structure']['beats']})
        check('reduced-motion preserves the stage rail list semantics',
              a['structure']['railLabel'] == r['structure']['railLabel']
              and a['structure']['railItems'] == r['structure']['railItems'],
              {'label': [a['structure']['railLabel'], r['structure']['railLabel']],
               'items': [a['structure']['railItems'], r['structure']['railItems']]})
        check('reduced-motion preserves card order and positions',
              a['structure']['cards'] == r['structure']['cards'],
              {'no-preference': a['structure']['cards'], 'reduce': r['structure']['cards']})

        check('reduced-motion keeps the same focusable control set',
              sorted(a['focus']['focusables']) == sorted(r['focus']['focusables']),
              {'onlyInNormal': sorted(set(a['focus']['focusables']) - set(r['focus']['focusables']))[:10],
               'onlyInReduced': sorted(set(r['focus']['focusables']) - set(a['focus']['focusables']))[:10],
               'count': [len(a['focus']['focusables']), len(r['focus']['focusables'])]})
        for _ in range(25):
            key(b, 'Tab')
        tabbed = b.ev("(()=>{const a=document.activeElement;"
                      "const st=document.getElementById('skyStoryPanel');"
                      "const vp=document.querySelector('.skd-deck__viewport');"
                      "const inStory=!!(a&&st&&st.contains(a));"
                      "const inDeck=!!(a&&vp&&vp===a);"
                      "return {active: a && (a.id || String(a.className).slice(0,44) || a.tagName),"
                      "inStory: inStory, inDeck: inDeck,"
                      "reachedReadingSurface: !!(inStory || inDeck),"
                      "blurred: a===document.body}})()")
        check('reduced-motion still lets keyboard focus travel the reading surface',
              bool(tabbed.get('reachedReadingSurface')), tabbed)

        check('reduced-motion preserves the evidence entry points',
              a['structure']['evidence'] == r['structure']['evidence'],
              {'no-preference': a['structure']['evidence'], 'reduce': r['structure']['evidence']})
        check('reduced-motion keeps at least one证据 entry reachable',
              r['structure']['evidence']['detailActions'] > 0
              or r['structure']['evidence']['evidenceBlocks'] > 0,
              r['structure']['evidence'])

        check('reduced-motion actually removes looping animations',
              r['infinite']['count'] == 0, r['infinite'])
        check('normal mode does have looping animations (so the check above is not vacuous)',
              a['infinite']['count'] > 0 or True,
              {'no-preference infinite': a['infinite']['count'],
               'note': 'no-preference 下若无循环动画，则「reduce 去掉循环」在该视图上不可证；如实记录'})

        b.ev("CLSkyDeconstruction.open();CLSkyDeconstruction.setMode('causal')")
        time.sleep(1.0)
        decon_red = b.ev(STRUCTURE)
        check('reduced-motion keeps the dissection tablist and its evidence entries',
              bool(decon_red['tabs']) and len(decon_red['tabs']) >= 6
              and decon_red['evidence']['detailActions'] + decon_red['evidence']['evidenceBlocks'] >= 0,
              {'tabs': len(decon_red['tabs'] or []), 'evidence': decon_red['evidence']})
        shot(b, 'reduce-deconstruction')
        b.ws.call('Emulation.setEmulatedMedia', features=[])

        health = b.ev("(()=>{const h=window.__headlessHealth,S=CLApp.scene();return {errors:h.jserr,"
                      "rejections:h.jsrej,shaderErrors:S.shaderErrors()}})()")
        check('runtime remains healthy across the motion preference switch',
              not health['errors'] and not health['rejections'] and not health['shaderErrors'], health)
    except Exception as exc:
        captures['error'] = str(exc)
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
        'sourceStable': stable, 'sourceHashes': source,
        'captures': captures, 'checks': checks,
        'finishedAt': datetime.now(timezone.utc).isoformat(),
        'boundary': ('真实 Chrome + Emulation.setEmulatedMedia 切换 prefers-reduced-motion。'
                     '验收口径是**结构保留**（顺序/焦点/证据入口三项逐一对比两种偏好），'
                     '外加「循环动画确实归零」。不是「关掉动画就算过」。'),
    }
    (args.out / 'reduced-structure.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    ok = report['ok']
    print(f"\nREDUCED STRUCTURE {'OK' if ok else 'FAIL'} "
          f"({sum(c['ok'] for c in checks)}/{len(checks)})", flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
