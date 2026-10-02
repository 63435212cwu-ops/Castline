#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星渊 G1 · 语义色门禁 v2（裸色普查 + 回落值漂移 + 棘轮）。

v1 只做一件事：数裸 hex，多到数不完就永远转不了 --strict（当前可迁移面 812 条）。
v2 把「数不完」拆成三类，并只对其中一类动手：

  A. **漂移**（drift）—— `var(--abyss-x, #fallback)` 的回落值与 token 真值不一致。
     这是真缺陷：token 改了、回落值没跟，浏览器一不支持 var() 或该变量被覆盖，
     同一个语义就在两处长得不一样。**一条即失败**，与总纲「语义唯一真相」直接对齐。
     真值来源是把整棵 `--abyss-*` 变量图按 index.html 的加载顺序解析出来的具体色值，
     不是某一行的字面量（token 本身就常写成 var(--mint,#7af0c8) 这种链式回落）。
  B. **重复**（dup）—— 字面量与某个语义色真值相同，但没走 token。
  C. **裸色**（bare）—— 其余可迁移裸 hex（一次性材质/渐变端点色多属此类）。

门禁分两档：
  `--strict`   A 类必须为 0，且 B/C 类必须为 0（现状远未达到，作为最终目标保留）。
  `--ratchet`  A 类必须为 0，且 B/C 类的**分模块计数不得高于基线**（tests/palette_baseline.json）。
               这是今天就能生效的档：禁止新增，允许存量按模块慢慢烧。
  `--update-baseline` 重写基线（只在**盘点口径变化**或**迁移了一整块**时才用；
               日常跑门禁不要用它，否则棘轮就白装了）。

用法：
  python3 -s tests/palette_lint.py                 # 报告
  python3 -s tests/palette_lint.py --ratchet       # 棘轮门禁（runall 用的就是这一档）
  python3 -s tests/palette_lint.py --update-baseline
硬约束：Python 标准库 only · 不启浏览器 · 秒级返回。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASELINE = os.path.join(HERE, 'palette_baseline.json')
SCAN_DIRS = ('js', 'css')

# 按 index.html 的 <link> 顺序：同特异性的 :root 声明**后者胜**，解析变量图必须用这个顺序。
# 未列出的 css 排在末尾（当前只有 scene-radar-hud.css —— 它没有被 index.html 引用，见文件尾注）。
# P0/S1（2026-09-16）：css/abyss-tokens.css 由 radar-theme.css 的 :root 块升格而来，
# 位置紧随 css/app.css。**必须登记在这里**，否则变量图少掉整层 --abyss-*，
# 下游所有 var(--abyss-x,#hex) 的回落值会被判成「引用了并不存在的 token」→ 批量假漂移。
LOAD_ORDER = ['css/app.css', 'css/abyss-tokens.css', 'css/arcana.css', 'css/oracle.css', 'css/plot.css',
              'css/peer.css', 'css/tree-tip.css', 'css/tree-twig-tip.css', 'css/radar-theme.css',
              'css/plot-orbit.css', 'css/orbit3d.css', 'css/tree-narrate.css']

HEX = re.compile(r'(?<![A-Za-z0-9_-])(?:#|0x)([0-9a-fA-F]{6})(?![0-9a-fA-F])')
VAR_DEF = re.compile(r'(--[a-z0-9-]+)\s*:\s*([^;}]+)[;}]', re.I)
VAR_REF = re.compile(r'var\(\s*(--[a-z0-9-]+)\s*(?:,([^)]*))?\)')
FALLBACK = re.compile(r'var\(\s*(--[a-z0-9-]+)\s*,\s*(#[0-9a-fA-F]{6})\s*\)')
# 变量声明行：这一条 var() 就是 token 的定义本身（`--abyss-obsidian:var(--bg,#07060d)`）。
# 定义里的回落值是**宪法声明**——`--bg` 万一没了，深渊 0 就是 G1 色板写死的 #07060d——
# 不能按「跟随上游真值」处理，否则等于让下游改上游。漂移检查只作用于消费端。
VAR_DECL = re.compile(r'--[a-z0-9-]+\s*:\s*$')

# 拥有明确的非 CSS-token 职责、按模块逐批迁移的文件（v1 的 REPORT_ONLY 原样保留）
REPORT_ONLY = {
    'js/scene.js', 'js/scene-crown-shading.js', 'js/core/scene-crown-motion.js',
    'js/orbit3d/orbit3d-shaders.js', 'js/orbit3d/orbit3d-layer.js', 'js/orbit3d/orbit3d-geom.js',
    'js/tree/tree-shape.js', 'js/tree/tree-ghost.js', 'js/tree/tree-legend.js',
    'js/tree/plot-tree.js', 'js/hud/plot-hud.js', 'js/tree/storylines.js',
    'js/palette.js',
}


def norm_hex(v):
    """把 #abc / #aabbcc / 0xaabbcc 统一成 6 位小写（无 #）。非法返回 None。"""
    v = v.strip().lower()
    if v.startswith('0x'):
        v = v[2:]
    if v.startswith('#'):
        v = v[1:]
    if len(v) == 3:
        v = ''.join(c * 2 for c in v)
    return v if re.fullmatch(r'[0-9a-f]{6}', v) else None


def rgba_to_hex(v):
    m = re.fullmatch(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)', v.strip())
    if not m:
        return None
    r, g, b = (int(m.group(i)) for i in (1, 2, 3))
    a = m.group(4)
    if a is not None and float(a) < 1:
        return None          # 半透明色不与不透明 hex 比
    return '%02x%02x%02x' % (r, g, b)


def css_files():
    have = []
    for d in SCAN_DIRS:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if name.endswith(('.js', '.css')):
                have.append(os.path.relpath(os.path.join(base, name), ROOT))
    return have


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def css_blocks(s):
    """粗粒度块扫描（括号配平）：产出 (选择器, 块体)。注释先剥掉，免得注释里的 { } 搅局。"""
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    out, i, n = [], 0, len(s)
    while True:
        j = s.find('{', i)
        if j < 0:
            break
        sel = s[i:j].strip().splitlines()[-1].strip() if s[i:j].strip() else ''
        d, k = 1, j + 1
        while k < n and d:
            if s[k] == '{':
                d += 1
            elif s[k] == '}':
                d -= 1
            k += 1
        out.append((sel, s[j + 1:k - 1]))
        i = k
    return out


def build_token_graph():
    """解析全仓 :root 变量（按 LOAD_ORDER，后者覆盖前者），再递归求值成具体色值。

    只认**选择器里含 :root 的块**：组件内部 `--x:#hex` 是局部覆写（例如某个条自己调暗），
    把它当全局真值会让整张表被污染 —— 本函数第一版就吃过这个亏，
    「真值」一度取自后来又被局部块改写过的值，于是报出一批假漂移。
    """
    decls = {}          # name -> raw value（后定义者胜）
    order = [p for p in LOAD_ORDER if os.path.basename(p)] + \
            [p for p in css_files() if p.endswith('.css') and p not in LOAD_ORDER]
    for rel in order:
        try:
            s = read(rel)
        except OSError:
            continue
        for block_sel, block_body in css_blocks(s):
            if ':root' not in block_sel:
                continue
            for m in VAR_DEF.finditer(block_body):
                decls[m.group(1).lower()] = m.group(2).strip()

    cache = {}

    def resolve(name, depth=0, seen=None):
        name = name.lower()
        if name in cache:
            return cache[name]
        if depth > 12:
            return None
        seen = seen or set()
        if name in seen:
            return None
        seen = seen | {name}
        raw = decls.get(name)
        if raw is None:
            return None
        h = norm_hex(raw) or rgba_to_hex(raw)
        if h:
            cache[name] = h
            return h
        m = VAR_REF.search(raw)
        if not m:
            cache[name] = None
            return None
        inner = resolve(m.group(1), depth + 1, seen)
        if inner:
            cache[name] = inner
            return inner
        tail = (m.group(2) or '').strip()
        h2 = norm_hex(tail) or rgba_to_hex(tail)
        cache[name] = h2
        return h2

    return decls, resolve


def strip_comments(src):
    """把 CSS/JS 的 `/* … */` 注释内容替换成等量空白（**保留换行**，行号不变）。

    R5-C §3 修正：旧版 `scan_rows()` 对**每一行原文**直接跑 `HEX.finditer`，于是
    「注释里提到的色值」被当成裸色计数。实测一次假红：`css/radar-theme.css:498` 的
    说明文字 `tier-mid 分值色 (#e4dcff) 撞色的 --warm。` 让该文件凭空多出 1 条裸色，
    并因「基线中不存在的新文件」把 `--ratchet` 打成 FAIL —— 而该文件本轮**根本没被改动**
    （mtime 早于本批）。
    注释不是活体样式，任何门禁都不该把它计入。已量化影响面：全仓 39 个受扫文件里只有
    3 个文件的计数下降（`js/palette.js` −3 · `css/abyss-tokens.css` −11 · `css/radar-theme.css` −1），
    **无一上涨** ⇒ 棘轮只会更紧，不会放松。
    """
    out, i, n = [], 0, len(src)
    while i < n:
        j = src.find('/*', i)
        if j < 0:
            out.append(src[i:])
            break
        out.append(src[i:j])
        k = src.find('*/', j + 2)
        end = n if k < 0 else k + 2
        out.append(re.sub(r'[^\n]', ' ', src[j:end]))
        i = end
    return ''.join(out)


def scan_rows():
    rows = []
    for rel in css_files():
        for no, line in enumerate(strip_comments(read(rel)).splitlines(), 1):
            for m in HEX.finditer(line):
                rows.append({'file': rel, 'line': no, 'value': norm_hex(m.group(0)),
                             'raw': m.group(0).lower(), 'text': line.strip()})
    return rows


def classify(rows, decls, resolve):
    """把每条裸色归档；同时把 `var(--abyss-x,#hex)` 的回落值单列出来查漂移。"""
    drift, fallbacks = [], []
    for rel in css_files():
        for no, line in enumerate(strip_comments(read(rel)).splitlines(), 1):
            for m in FALLBACK.finditer(line):
                tok, fb = m.group(1).lower(), norm_hex(m.group(2))
                is_decl = bool(VAR_DECL.search(line[:m.start()]))
                # 定义行也记进 fallbacks（否则它的 hex 会被算成「可迁移裸色」，凭空多出几十条），
                # 只是不参与漂移判定。
                fallbacks.append((rel, no, tok, fb))
                if is_decl:
                    continue
                if tok not in decls:
                    drift.append({'file': rel, 'line': no, 'token': tok, 'truth': '(未定义)',
                                  'fallback': fb, 'why': '回落值引用了并不存在的 token'})
                    continue
                truth = resolve(tok)
                if truth and truth != fb:
                    drift.append({'file': rel, 'line': no, 'token': tok, 'truth': truth,
                                  'fallback': fb, 'why': '回落值与 token 真值不一致'})
    # 语义色真值集合（palette.js 的写法不能 import，直接读它导出的 CSS 表）
    sem = set()
    try:
        pj = read('js/palette.js')
        for v in re.findall(r"'#([0-9a-fA-F]{6})'", pj):
            sem.add(v.lower())
    except OSError:
        pass
    for m in re.finditer(r'(--abyss-(?:mint|signal|violet|hot|ink|crimson|gold)[a-z0-9-]*)\s*:',
                         read('css/abyss-tokens.css')):
        t = resolve(m.group(1))
        if t:
            sem.add(t)

    dup, bare = [], []
    fallback_spots = {(f, l, v) for f, l, _t, v in fallbacks}
    for r in rows:
        if r['file'] in REPORT_ONLY:
            continue
        if (r['file'], r['line'], r['value']) in fallback_spots:
            continue      # 已经由漂移检查覆盖，不重复计数
        (dup if r['value'] in sem else bare).append(r)
    return drift, dup, bare, fallbacks


def counts(dup, bare):
    per = {}
    for r in dup + bare:
        per[r['file']] = per.get(r['file'], 0) + 1
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true', help='全部三类都必须为 0（最终目标）')
    ap.add_argument('--ratchet', action='store_true', help='漂移必须为 0，且分模块计数不得高于基线')
    ap.add_argument('--update-baseline', action='store_true', help='重写 tests/palette_baseline.json')
    ap.add_argument('--top', type=int, default=14, help='报告里列出的模块数')
    args = ap.parse_args()

    decls, resolve = build_token_graph()
    rows = scan_rows()
    drift, dup, bare, fallbacks = classify(rows, decls, resolve)
    per = counts(dup, bare)

    print('Castline · palette_lint v2 · %s' % ('STRICT' if args.strict else 'RATCHET' if args.ratchet else 'REPORT'))
    print('token 图 %d 条 · var() 回落点 %d 处 · 裸色 %d 条（重复 %d · 其他 %d）'
          % (len(decls), len(fallbacks), len(rows), len(dup), len(bare)))
    print('  A 漂移 %d · B 重复 %d · C 裸色 %d · 豁免文件内 %d'
          % (len(drift), len(dup), len(bare), len(rows) - len(dup) - len(bare)))

    if drift:
        print('\n[A 漂移] 回落值与 token 真值不一致（改 token 没跟着改回落值）：')
        for d in drift[:40]:
            print('  %s:%d  %s  真值 #%s · 回落 #%s  —— %s'
                  % (d['file'], d['line'], d['token'], d['truth'], d['fallback'], d['why']))
        if len(drift) > 40:
            print('  … 其余 %d 条省略' % (len(drift) - 40))

    print('\n[分模块存量] 可迁移裸色（B+C）：')
    for f, c in sorted(per.items(), key=lambda kv: -kv[1])[:args.top]:
        print('  %-34s %4d' % (f, c))
    if len(per) > args.top:
        print('  … 其余 %d 个文件合计 %d 条' % (len(per) - args.top, sum(sorted(per.values())[:-args.top])))
    print('  %-34s %4d' % ('合计', sum(per.values())))

    if args.update_baseline:
        with open(BASELINE, 'w', encoding='utf-8') as f:
            json.dump({'note': 'palette_lint --ratchet 的基线：分模块 B+C 计数上限。'
                               '只在盘点口径变化或整块迁移后更新。',
                       'total': sum(per.values()), 'files': dict(sorted(per.items()))},
                      f, ensure_ascii=False, indent=2, sort_keys=False)
        print('\n已写入 %s（合计 %d）' % (os.path.relpath(BASELINE, ROOT), sum(per.values())))
        return 0

    if args.strict:
        bad = bool(drift or dup or bare)
        print('\nPALETTE LINT FAIL · 漂移 %d · 可迁移裸色 %d' % (len(drift), len(dup) + len(bare)) if bad
              else '\nPALETTE LINT OK · 零违规')
        return 1 if bad else 0

    if args.ratchet:
        if not os.path.exists(BASELINE):
            print('\nPALETTE LINT FAIL · 缺基线 %s（先跑 --update-baseline 冻结一次）'
                  % os.path.relpath(BASELINE, ROOT))
            return 1
        with open(BASELINE, encoding='utf-8') as f:
            base = json.load(f)
        grown = [(f_, c, base['files'].get(f_, 0)) for f_, c in per.items()
                 if c > base['files'].get(f_, 0)]
        newf = [f_ for f_ in per if f_ not in base['files']]
        if drift or grown or newf:
            for f_, c, b in sorted(grown, key=lambda kv: -(kv[1] - kv[2])):
                print('  新增裸色 %s：%d → %d（+%d）' % (f_, b, c, c - b))
            for f_ in newf:
                print('  出现基线中不存在的新文件：%s（%d 条）' % (f_, per[f_]))
            print('\nPALETTE LINT FAIL · 漂移 %d · 计数上涨文件 %d · 新文件 %d'
                  % (len(drift), len(grown), len(newf)))
            return 1
        burn = base['total'] - sum(per.values())
        print('\nPALETTE LINT OK · 漂移 0 · 存量 %d（基线 %d，已烧掉 %d）'
              % (sum(per.values()), base['total'], burn))
        return 0

    print('\nPALETTE LINT OK · 报告完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
