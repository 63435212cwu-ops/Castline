#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行时对比度扫描（C2 第十一轮）：真实渲染 DOM 收敛静态审计的「未配对」与玻璃假设。

静态 tests/contrast_audit.py 的选择器平铺命名无法证明 DOM 嵌套（1189 条未配对），
玻璃拟态只能按两档舞台底做保守假设。本扫描用真实 Chrome（CDP，CL_GPU=1 串行槽位）
加载三部作品，在真实打开状态逐一走 DOM：

  每个可见文本节点（getClientRects 非空、可见、字号 ≥9px）取 computed color/fill、
  font-size/weight（大字判定按 WCAG：≥18.66px 粗体或 ≥24px → 阈值 3.0，否则 4.5），
  沿祖先链（≤64 层）取每层 backgroundColor / 渐变色原子 / opacity / backdrop-filter，
  在 Python 侧按 tests/contrast_audit.py 同一套色科学（linear-sRGB · WCAG 相对亮度 ·
  alpha-over 合成 · opacity 视作组透明度向上敷底 · 舞台底两档保守）求
  conservative（全候选最小）/optimistic（最大）对比度并复用同一 classify 三档判定。

与静态基线对齐：运行时匹配到的静态 FAIL/WARN 条目按「全通过→冤案建议、仍不过→确认」
分表；运行时新发（匹配不到任何静态条目的）FAIL/WARN 单独成表。

如实局限（写入报告）：
  - backdrop-filter 的真实模糊（尤其 WebGL 星空底）无法经 computedStyle 还原：
    玻璃底仍按其叠加深底的合成色 + 两档舞台底计——量化上是抽样人工判断（截图局部
    取色亲眼看），不写成全量合格；
  - WebGL/canvas 内绘制的文本（星空标签、刻度）不在 DOM，不在本扫描域；
  - 打开状态覆盖星座 / 悬停卡 / 星盘+卡片叠 / 剧情阅读 / 旅程播放字幕 / 搜索 /
    解构两页签 / 罗盘，未覆盖以登入口径如实列出。

用法：CL_GPU=1 python3 -s tests/sky_contrast_runtime_browser.py [--books saga,sanguo,dafeng]
      [--base http://127.0.0.1:8765] [--out /tmp/castline-shots/sky-contrast-runtime]
"""
import argparse
import base64
from datetime import datetime, timezone
import itertools
import json
import os
import sys
import time

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import sky_chaos as chaos
import contrast_audit as ca

BOOKS = [('saga', 'data/sample-saga.json'),
         ('sanguo', 'data/cache/a935953b2678a80b352091d5.json'),
         ('dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json')]

SCAN_JS = r"""
(function(){
  function toksOf(e){
    var t=[];
    if(e.id)t.push('#'+e.id);
    var cls=e.getAttribute&&e.getAttribute('class');
    if(cls)String(cls).trim().split(/\s+/).slice(0,10).forEach(function(c){if(c)t.push('.'+c);});
    var tag=(e.tagName||'').toLowerCase();
    if(tag&&tag!=='*')t.push(tag);
    return t;
  }
  var out=[],walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,null,null),node;
  while((node=walker.nextNode())){
    var v=node.nodeValue;
    if(!v||!/\S/.test(v))continue;
    var el=node.parentElement;
    if(!el)continue;
    var tag=(el.tagName||'').toLowerCase();
    if(tag==='script'||tag==='style'||tag==='noscript'||tag==='template')continue;
    var cs=getComputedStyle(el);
    if(cs.visibility!=='visible'||cs.display==='none')continue;
    var fs=parseFloat(cs.fontSize);
    if(!(fs>=9))continue;
    var r=document.createRange(); r.selectNodeContents(node);
    var b=r.getBoundingClientRect();
    if(r.detach)r.detach();
    if(!(b.width>0&&b.height>0))continue;
    if(b.right<0||b.bottom<0||b.left>innerWidth||b.top>innerHeight)continue;
    var svg=!!(el.namespaceURI&&el.namespaceURI.indexOf('svg')>=0);
    var chain=[],e=el;
    while(e&&chain.length<64){
      var s=getComputedStyle(e);
      var bi=s.backgroundImage;
      if(bi==='none')bi='';
      else if(bi.indexOf('gradient')>=0)bi=bi.slice(0,400);
      else bi='other';
      chain.push({t:toksOf(e),bg:s.backgroundColor,bi:bi,
                  op:parseFloat(s.opacity),bd:(s.backdropFilter||s.webkitBackdropFilter||'none')!=='none'});
      e=e.parentElement;
    }
    out.push({x:Math.round(b.left+b.width/2),y:Math.round(b.top+b.height/2),
              w:Math.round(b.width),h:Math.round(b.height),
              txt:v.trim().replace(/\s+/g,' ').slice(0,42),
              fs:fs,fw:parseFloat(cs.fontWeight)||400,svg:svg,
              fg:svg?cs.fill:cs.color,chain:chain});
  }
  return JSON.stringify({nodes:out,w:innerWidth,h:innerHeight,body:document.body.className});
})()
"""

FAMILY_RE_SKD = ('sky-', 'sd-', 'skd', 'skc', 'ssp', 'sks', 'ske', 'sd_', 'sky_story', 'skydecon')
FAMILY_RE_COSMIC = ('ia-', 'info-arch', 'cosmic')


def detect_family(chain):
    text = ' '.join(t for hop in chain for t in hop['t']).lower()
    if any(k in text for k in FAMILY_RE_COSMIC):
        return 'cosmic'
    if any(k in text for k in FAMILY_RE_SKD):
        return 'skd'
    return 'abyss'


def layer_candidates(hop):
    """一层背景的候选 linear-sRGB 色：backgroundColor + 渐变色原子（同静态口径全保留）。"""
    cols = []
    for raw in ([hop['bg']] if not hop['bi'] else [hop['bg'], hop['bi']]):
        if raw in ('', 'other'):
            continue
        try:
            cols.extend(ca.eval_colors(raw, None))
        except Exception:
            cols.extend([c for c in (ca.parse_plain_color(x)
                                     for x in ca._scan_color_atoms(raw)) if c])
    seen, ded = set(), []
    for c in cols:
        key = tuple(round(v, 4) for v in c)
        if key not in seen:
            seen.add(key)
            ded.append(c)
    return ded[:3]


def compose_pair(row, underlays):
    """→ (lo, hi)。全部（背景候选 × 两档舞台底）组合的最小 / 最大对比度。"""
    family = row['family']
    under_pair = underlays[family]
    ops = []
    for hop in row['chain']:
        v = hop['op']
        ops.append(1.0 if v != v else max(0.0, min(1.0, v)))
    accum = []
    acc = 1.0
    for i, _ in enumerate(row['chain']):
        acc *= ops[i]
        accum.append(acc)
    fg_cols = layer_candidates({'bg': row['fg'], 'bi': ''})
    if not fg_cols:
        return None
    layer_sets = []
    for i, hop in enumerate(row['chain']):
        cs = layer_candidates(hop)
        layer_sets.append([(c[0], c[1], c[2], c[3] * accum[i]) for c in cs])
    lo, hi = None, None
    combos = 1
    for cs in layer_sets:
        combos *= max(1, len(cs))
    capped = [cs[:2] if combos > 512 else cs for cs in layer_sets]
    for under in under_pair:
        for fc in fg_cols[:3]:
            f_layer = (fc[0], fc[1], fc[2], fc[3] * (accum[-1] if accum else 1.0))
            for picks in itertools.product(*[cs or [None] for cs in capped]):
                layers = [p for p in picks if p]
                bg_flat = ca.flatten(layers + [under])
                fg_flat = ca.alpha_over(f_layer, bg_flat)
                r = ca.contrast(fg_flat, bg_flat)
                lo = r if lo is None else min(lo, r)
                hi = r if hi is None else max(hi, r)
    return (round(lo, 2), round(hi, 2)) if lo is not None else None


def classify_row(row, pair):
    ent = {'size_px': row['fs'], 'weight': row['fw'],
           'selector': ' '.join(row['chain'][0]['t']),
           'ratio_conservative': pair[0], 'ratio_optimistic': pair[1]}
    verdict, threshold = ca.classify(ent)
    return verdict, threshold, bool(pair[0] >= threshold)


def static_entries(entries):
    """静态 audit 实体 + 判定，附基线标注。"""
    base = {}
    try:
        base = json.load(open(ca.BASELINE, encoding='utf-8')).get('fails', {})
    except (OSError, ValueError):
        pass
    out = []
    for e in entries:
        if e.get('bucket') != 'audit' or e.get('verdict') not in ('FAIL', 'WARN'):
            continue
        sel_comps = ca.compounds(e['selector'])
        out.append({'id': ca.entry_id(e), 'file': e['file'], 'line': e['line'],
                    'selector': e['selector'], 'verdict': e['verdict'],
                    'ratio_c': e.get('ratio_conservative'), 'ratio_o': e.get('ratio_optimistic'),
                    'comps': sel_comps, 'inBaseline': ca.entry_id(e) in base,
                    'note': base.get(ca.entry_id(e), {}).get('note', '')})
    return out, [e for e in entries if e.get('bucket') == 'unpaired']


def match_static(sel_comps, path):
    """静态归一化 selector 的 compounds 是否以子序列匹配运行时祖先链。

    path 从文本元素自身（chain[0]）向外到 body；sel_comps 从外向内，末段须落在文本元素上。"""
    if not sel_comps or not path:
        return False
    if not sel_comps[-1] <= set(path[0]):
        return False
    idx = 0
    for comp in reversed(sel_comps[:-1]):
        found = False
        while idx + 1 < len(path):
            idx += 1
            if comp <= set(path[idx]):
                found = True
                break
        if not found:
            return False
    return True


def click(b, selector, tag):
    pt = b.ev("(()=>{const e=document.querySelector(" + json.dumps(selector) + "),r=e&&e.getBoundingClientRect();"
              "if(!r||r.width<=0||r.height<=0)throw Error('No visible target: '+" + json.dumps(selector) + ");"
              "return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
    b.mouse('mouseMoved', pt['x'], pt['y'])
    b.mouse('mousePressed', pt['x'], pt['y'])
    b.mouse('mouseReleased', pt['x'], pt['y'])
    time.sleep(.4)


def press_escape(b):
    b.ev("document.activeElement && document.activeElement.blur && document.activeElement.blur()")
    b.key('Escape')
    time.sleep(.5)


def run_book(b, base, tag, data, out_dir):
    rows, states = [], []
    b.ws.call('Page.navigate', url=base + '/?data=%s&sky=1&probe=1' % data)
    t0 = time.monotonic()
    ready = False
    while time.monotonic() - t0 < 180:
        time.sleep(0.5)
        try:
            if b.ev("!!(window.CLSky && CLSky.model() && window.CLSkyDeep && CLSkyDeep.enabled() && CLSkyDeep.stats().stars.ignite > 0.99)"):
                ready = True
                break
        except Exception:
            pass
    if not ready:
        raise RuntimeError('book did not become ready within 180 seconds')
    if not b.until("!document.querySelector('.skd-loader.is-on')", 60):
        raise RuntimeError('loader curtain never left')
    time.sleep(2)
    meta = json.loads(b.ev("JSON.stringify({names:CLApp.graph().characters.slice().sort((a,b)=>(b.importance||0)-(a.importance||0)).slice(0,30).map(c=>c.name),"
                           "rel:CLApp.graph().characters.filter(c=>CLApp.graph().relations.some(r=>r.a===c.name||r.b===c.name)).sort((a,b)=>(b.importance||0)-(a.importance||0)).slice(0,6).map(c=>c.name)})"))

    SETTLE_JS = ("(function(){var els=document.querySelectorAll('.skd-type__c');"
                 "for(var i=0;i<els.length;i++){var e=els[i],cs=getComputedStyle(e);"
                 "if(cs.visibility!=='visible'||cs.display==='none')continue;"
                 "var r=e.getBoundingClientRect();if(!(r.width>0&&r.height>0))continue;"
                 "if(r.right<0||r.bottom<0||r.left>innerWidth||r.top>innerHeight)continue;"
                 "if(parseFloat(cs.opacity)<0.99)return false;}return true;})()")

    def scan_state(name, note=''):
        b.until(SETTLE_JS, 8)
        payload = json.loads(b.ev(SCAN_JS))
        shot = b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)['data']
        path = os.path.join(out_dir, '%s-%s.png' % (tag, name))
        with open(path, 'wb') as f:
            f.write(base64.b64decode(shot))
        states.append({'state': name, 'note': note, 'nodes': len(payload['nodes']),
                       'body': payload['body'][:200], 'shot': os.path.basename(path)})
        print('    %s state %-16s nodes=%d' % (tag, name, len(payload['nodes'])), flush=True)
        for n in payload['nodes']:
            rows.append({'book': tag, 'state': name, **n})

    scan_state('constellation')
    b.ev("CLSkyDeep.hoverStar(%s)" % json.dumps(meta['names'][0]))
    time.sleep(1.2)
    scan_state('hover-card', 'hoverStar 顶角色')
    b.ev("CLSkyDeep.hoverStar(null)")
    time.sleep(.6)
    click(b, '#skyPlot', 'plot')
    if not b.until("CLSky.state().plot===true", 8):
        raise RuntimeError('plot mode did not open from a real toolbar click')
    time.sleep(2)
    scan_state('plot-disc', '星盘态 + 卡片叠 + 刻度拨盘')
    b.ev('CLSky.seekEventAt(1)')
    if not b.until("!document.getElementById('skyStoryPanel').hidden", 8):
        raise RuntimeError('story reading panel did not open')
    time.sleep(1.2)
    scan_state('story-reading', '事件阅读面板')
    b.ev('CLSky.play()')
    if not b.until("CLSky.state().playing===true", 8):
        raise RuntimeError('playback did not start')
    time.sleep(2.5)
    scan_state('journey-playing', '播放条字幕')
    b.ev('CLSky.stop()')
    time.sleep(1)
    press_escape(b)
    click(b, '#skySearch', 'search')
    b.ws.call('Input.insertText', text=meta['names'][0][:2])
    if not b.until("!document.getElementById('skySearchPanel').hidden", 6):
        raise RuntimeError('search results did not open from real typing')
    time.sleep(1)
    scan_state('search-open', '真实键入候选人名前两字')
    press_escape(b)
    click(b, '#skyDecode', 'decon')
    if not b.until("!document.getElementById('skyDeconPanel').hidden", 8):
        raise RuntimeError('deconstruction panel did not open')
    time.sleep(1.4)
    scan_state('decon-overview', '解构 · 总览页签')
    click(b, '#skyDeconTabCausal', 'causal tab')
    time.sleep(1.2)
    scan_state('decon-causal', '解构 · 因果页签')
    press_escape(b)
    who = (meta['rel'] or meta['names'])[0]
    b.ev("if(CLSky.plot())CLSky.setPlot(false)")
    time.sleep(1.5)
    b.ev("CLSky.openCompass(%s)" % json.dumps(who))
    if not b.until("CLSky.state().compass===%s && CLSkyCompass.stats().open" % json.dumps(who), 20):
        raise RuntimeError('relation compass did not open')
    time.sleep(3)
    scan_state('compass', '关系罗盘 · %s' % who)
    b.ev('CLSky.closeCompass()')
    time.sleep(1.5)
    health = b.ev("({js:__headlessHealth.jserr.slice(0,3),rej:__headlessHealth.jsrej.slice(0,3)})")
    return rows, states, health


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8765')
    ap.add_argument('--books', default='saga,sanguo,dafeng')
    ap.add_argument('--out', default='/tmp/castline-shots/sky-contrast-runtime')
    args = ap.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    os.makedirs(args.out, exist_ok=True)
    selected = [x for x in BOOKS if x[0] in args.books.split(',')]
    if not selected:
        ap.error('unknown/empty --books')

    audit_entries, underlays = ca.audit()
    static_fail_warn, unpaired_static = static_entries(audit_entries)

    all_rows, all_states, healths = [], [], {}
    for tag, data in selected:
        b = chaos.Browser(1440, 900)
        try:
            b.start()
            print('BOOK %s · %s' % (tag, data), flush=True)
            rows, states, health = run_book(b, args.base, tag, data, args.out)
            all_rows.extend(rows)
            all_states.extend([{'book': tag, **s} for s in states])
            healths[tag] = health
        finally:
            b.close()

    OPACITY_FLOOR = 0.35
    scanned, unresolved, faded = [], [], {}
    for row in all_rows:
        eff = 1.0
        for hop in row['chain']:
            v = hop['op']
            eff *= 1.0 if v != v else max(0.0, min(1.0, v))
        if eff < OPACITY_FLOOR:
            key = (' '.join(row['chain'][0]['t'][:6]), row['state'])
            g = faded.setdefault(key, {'sel': key[0], 'state': key[1], 'count': 0,
                                       'sample': row['txt'], 'effOpacity': eff})
            g['count'] += 1
            continue
        row['family'] = detect_family(row['chain'])
        pair = compose_pair(row, underlays)
        if pair is None:
            unresolved.append(row)
            continue
        verdict, threshold, ok = classify_row(row, pair)
        path = [hop['t'] for hop in row['chain']]
        hits = [s['id'] for s in static_fail_warn if match_static(s['comps'], path)]
        scanned.append({'book': row['book'], 'state': row['state'], 'txt': row['txt'],
                        'sel': ' '.join(row['chain'][0]['t'][:6]), 'family': row['family'],
                        'fg': row['fg'], 'fs': row['fs'], 'fw': row['fw'], 'svg': row['svg'],
                        'lo': pair[0], 'hi': pair[1], 'threshold': threshold, 'verdict': verdict,
                        'x': row['x'], 'y': row['y'], 'w': row['w'], 'h': row['h'],
                        'staticHits': hits,
                        'bgChain': [[h['bg'], (h['bi'] or '')[:60], h['op'], h['bd']]
                                    for h in row['chain'] if h['bg'] != 'rgba(0, 0, 0, 0)' or h['bi'] or h['op'] != 1],
                        'backdrop': any(h['bd'] for h in row['chain'])})

    by_static = {}
    for s in static_fail_warn:
        by_static[s['id']] = {**{k: s[k] for k in ('id', 'file', 'line', 'selector', 'verdict',
                                                   'ratio_c', 'ratio_o', 'inBaseline', 'note')},
                              'observed': []}
    for r in scanned:
        for sid in r['staticHits']:
            by_static[sid]['observed'].append(r)
    exonerated, confirmed, unobserved = [], [], []
    for s in by_static.values():
        obs = s['observed']
        if not obs:
            unobserved.append(s)
            continue
        worst = min(o['lo'] for o in obs)
        best = max(o['lo'] for o in obs)
        states_seen = sorted({o['state'] for o in obs})
        row = {**{k: s[k] for k in ('id', 'file', 'line', 'selector', 'verdict', 'ratio_c', 'note')},
               'runtime_lo': round(worst, 2), 'runtime_hi': round(best, 2),
               'instances': len(obs), 'states': states_seen}
        t = obs[0]['threshold']
        if all(o['lo'] >= o['threshold'] for o in obs):
            row['basis'] = '全部 %d 处运行时实例 conservative ≥ 阈值' % len(obs)
            exonerated.append(row)
        else:
            row['basis'] = '最差实例 conservative=%.2f < 阈值 %.1f（%d 处实例）' % (worst, t, len(obs))
            row['worst'] = min(obs, key=lambda o: o['lo'])
            confirmed.append(row)

    fresh = [r for r in scanned if r['verdict'] in ('FAIL', 'WARN') and not r['staticHits']]
    fresh_grouped = {}
    for r in fresh:
        key = (r['sel'], r['fg'], r['family'])
        g = fresh_grouped.setdefault(key, {'sel': r['sel'], 'fg': r['fg'], 'family': r['family'],
                                           'verdict': r['verdict'], 'lo': r['lo'], 'hi': r['hi'],
                                           'threshold': r['threshold'], 'count': 0,
                                           'states': set(), 'sample': r['txt'], 'backdrop': r['backdrop'],
                                           'at': None})
        g['count'] += 1
        g['states'].add(r['state'])
        if r['lo'] < g['lo']:
            g['lo'] = r['lo']
            g['sample'] = r['txt']
            g['at'] = {'book': r['book'], 'state': r['state'], 'x': r['x'], 'y': r['y'], 'w': r['w'], 'h': r['h']}
        elif g['at'] is None:
            g['at'] = {'book': r['book'], 'state': r['state'], 'x': r['x'], 'y': r['y'], 'w': r['w'], 'h': r['h']}
    fresh_rows = [{**g, 'states': sorted(g['states'])} for g in fresh_grouped.values()]
    fresh_rows.sort(key=lambda g: (g['verdict'] != 'FAIL', g['lo']))

    stats = {'textNodes': len(all_rows), 'scanned': len(scanned),
             'fadedOut': sum(g['count'] for g in faded.values()), 'unresolved': len(unresolved),
             'books': len(selected), 'states': len(all_states),
             'staticEntries': len(static_fail_warn),
             'staticObserved': len(exonerated) + len(confirmed),
             'exonerated': len(exonerated), 'confirmed': len(confirmed),
             'unobserved': len(unobserved),
             'runtimeFail': sum(1 for r in scanned if r['verdict'] == 'FAIL'),
             'runtimeWarn': sum(1 for r in scanned if r['verdict'] == 'WARN'),
             'runtimePass': sum(1 for r in scanned if r['verdict'] == 'PASS')}
    path_cache = [[hop['t'] for hop in row['chain']] for row in all_rows]
    unpaired_hit = 0
    for e in unpaired_static:
        comps = ca.compounds(e['selector'])
        if any(match_static(comps, p) for p in path_cache):
            unpaired_hit += 1

    report = {
        'tool': 'sky_contrast_runtime_browser（真实渲染 DOM · WCAG AA · 与 tests/contrast_audit.py 同一色科学）',
        'finishedAt': datetime.now(timezone.utc).isoformat(),
        'base': args.base, 'books': [b[0] for b in selected],
        'states': all_states, 'health': healths,
        'stats': {**stats, 'unpairedStatic': len(unpaired_static),
                  'unpairedRuntimeEvidenced': unpaired_hit},
        'exonerated': exonerated,
        'confirmed': [{k: v for k, v in c.items() if k != 'worst'} |
                      {'worst': {k: c['worst'][k] for k in
                                 ('book', 'state', 'sel', 'txt', 'fg', 'fs', 'fw', 'lo', 'hi',
                                  'threshold', 'verdict', 'x', 'y', 'backdrop')}}
                      for c in confirmed],
        'unobserved': unobserved,
        'freshDynamic': fresh_rows,
        'runtimeFails': [r for r in scanned if r['verdict'] == 'FAIL'],
        'fadedOut': sorted(faded.values(), key=lambda g: -g['count'])[:30],
        'opacityFloor': OPACITY_FLOOR,
        'limitations': [
            'backdrop-filter 模糊（尤其 WebGL 星空底）无法经 computedStyle 还原；玻璃底按其叠加深底合成 + 两档舞台底估测，量化外部分为截图局部取色的抽样人工判断',
            'WebGL/canvas 绘制文本（星名标签、刻度）不在 DOM，不在本扫描域',
            '状态覆盖：' + ' / '.join(sorted({s['state'] for s in all_states})),
        ],
    }
    out_json = os.path.join(args.out, 'result.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(stats, ensure_ascii=False), flush=True)
    print('EXONERATED %d · CONFIRMED %d · UNOBSERVED %d · FRESH groups %d' %
          (len(exonerated), len(confirmed), len(unobserved), len(fresh_rows)), flush=True)
    print('SKY-CONTRAST-RUNTIME OK · %s' % out_json, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
