#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星渊 G3 · 字号阶梯门禁。

八级阶梯（总纲表 4-2）：
  T0 22–28px 标题 / 聚焦角色名     T1 16px 面板标题 / 大分值
  T2 13px 正文 / 标签主行          T3 12px HUD 正文 / 胶囊次行
  T4 11px 图谱内最小标签（mono）   T5 10px 仅限刻度数字 / 图例徽记

判定分三档：
  FATAL  <10px —— 任何模式下都失败，废除 10px 以下一切用途。
  GATED  =10px 且同行没有 `T5 刻度豁免` 注释 —— T5 是白名单档，不是默认档。
  DRIFT  10–13px 之间的非阶梯值（10.5 / 11.5 / 12.5 …）—— 阶梯外的漂移值。

v-var：var 链解析档。只扫字面量时 `font-size:var(--abyss-fs-2xs)` 这类引用对门禁
完全隐形——把 10px 令牌喂给语义文本（旧 --cl-ann-fs-label 就是这么绕过 G3 的）。
本档先把 css/ 全部自定义属性解析成 var 图（`--x: 10px` / `--y: var(--x)` 链，
环安全、最多 12 跳、支持 `var(--x, 回落px)` 尾值），再对 font-size / font 简写里的
var() 求值后按同一套阶梯规则判定。默认模式只报告不拦截（atlas-tokens.css §4
契约档 9.5px 等存量是登记债），`--strict` 一并升级为拦截。

默认报告模式只列清单；`--strict` 把 GATED / DRIFT 一并升级为拦截。
JS 内联字号（radar.js 生成的 SVG 等）单列一节，只报告不拦截。
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_DIR = os.path.join(ROOT, 'css')
JS_DIR = os.path.join(ROOT, 'js')

CSS_FS = re.compile(r'font-size\s*:\s*([0-9]+(?:\.[0-9]+)?)px')
CSS_FONT_SH = re.compile(r'(?<!-)\bfont\s*:\s*[^;{}]*?(?<![\w.-])([0-9]+(?:\.[0-9]+)?)px(?=\s*[/\s])')
JS_FS = re.compile(r'font-size\s*[:=]\s*"?\'?\s*([0-9]+(?:\.[0-9]+)?)px')
EXEMPT = re.compile(r'T5\s*刻度豁免')

CSS_FS_VAL = re.compile(r'(?<!-)\bfont-size\s*:\s*([^;!}]+)')
CSS_FONT_VAL = re.compile(r'(?<!-)\bfont\s*:\s*([^;!}]+)')
VAR_DEF_ANY = re.compile(r'(--[a-zA-Z0-9_-]+)\s*:\s*([^;}]+)[;}]')
VAR_REF_ANY = re.compile(r'var\(\s*(--[a-zA-Z0-9_-]+)\s*(?:,([^)]*))?\)')
PX_ONLY = re.compile(r'^\s*([0-9]+(?:\.[0-9]+)?)px\s*$')
PX_TAIL = re.compile(r'([0-9]+(?:\.[0-9]+)?)px\s*$')
SANE_LO, SANE_HI = 6.0, 60.0


def strip_css_comments(text):
    """剥掉 /* ... */ 注释（保留换行，行号对齐），免得注释里的假定义混进 var 图。"""
    def repl(m):
        s = m.group(0)
        return '\n' * s.count('\n') + ' ' * (len(s) - s.count('\n'))
    return re.sub(r'/\*.*?\*/', repl, text, flags=re.DOTALL)


def collect_var_declarations():
    """扫全仓 css 自定义属性定义，构造 name → 原始值 的 var 图（后定义者胜）。"""
    decls = {}
    for _rel, path in css_files():
        with open(path, encoding='utf-8') as f:
            text = strip_css_comments(f.read())
        for m in VAR_DEF_ANY.finditer(text):
            decls[m.group(1).lower()] = m.group(2).strip()
    return decls


def resolve_font_px(name, decls, depth=0, seen=None):
    """把 --x 解析成字号 px：Npx 字面量 → 取数；var() 链 → 递归；解析失败 → None。"""
    if depth > 12:
        return None
    seen = seen or set()
    key = name.lower()
    if key in seen:
        return None
    raw = decls.get(key)
    if raw is None:
        return None
    m = PX_ONLY.match(raw)
    if m:
        return float(m.group(1))
    r = VAR_REF_ANY.search(raw)
    if not r:
        return None
    inner = resolve_font_px(r.group(1), decls, depth + 1, seen | {key})
    if inner is not None:
        return inner
    tail = PX_TAIL.search((r.group(2) or '').strip())
    return float(tail.group(1)) if tail else None


def resolve_consumer_var(var_name, fallback, decls):
    """消费端 var(--x, 回落)：先查 var 图；图里没有再吃同行的 px 回落。"""
    px = resolve_font_px(var_name, decls)
    if px is not None:
        return px
    tail = PX_TAIL.search((fallback or '').strip())
    return float(tail.group(1)) if tail else None


def scan_var_chain():
    """对 font-size / font 简写里的 var() 求值并按 G3 阶梯判定。"""
    decls = collect_var_declarations()
    hits = {'FATAL': [], 'GATED': [], 'DRIFT': []}
    seen_rows = set()
    for rel, path in css_files():
        with open(path, encoding='utf-8') as f:
            raw_lines = f.read().splitlines()
        clean_lines = strip_css_comments('\n'.join(raw_lines)).splitlines()
        for no, raw_line in enumerate(raw_lines, 1):
            line = clean_lines[no - 1] if no - 1 < len(clean_lines) else ''
            candidates = []
            for m in CSS_FS_VAL.finditer(line):
                candidates.append(list(VAR_REF_ANY.findall(m.group(1))))
            for m in CSS_FONT_VAL.finditer(line):
                refs = VAR_REF_ANY.findall(m.group(1))
                candidates.append([r for r in refs if '-fs-' in r[0].lower()])
            for group in candidates:
                for var_name, fallback in group:
                    px = resolve_consumer_var(var_name, fallback, decls)
                    if px is None or not (SANE_LO <= px <= SANE_HI):
                        continue
                    kind = classify(px, raw_line)
                    if not kind:
                        continue
                    row_key = (var_name.lower(), px) if kind == 'DRIFT' else (rel, no, px)
                    if row_key in seen_rows:
                        continue
                    seen_rows.add(row_key)
                    text = raw_line.strip() if kind != 'DRIFT' else \
                        '%s → %gpx（例：%s:%d %s）' % (var_name, px, rel, no, raw_line.strip()[:90])
                    hits[kind].append((rel, no, px, text))
    return hits

LADDER = (10.0, 11.0, 12.0, 13.0, 16.0)
DRIFT_HI = 13.0


def css_files():
    for name in sorted(os.listdir(CSS_DIR)):
        if name.endswith('.css'):
            yield os.path.join('css', name), os.path.join(CSS_DIR, name)


def js_files():
    for name in sorted(os.listdir(JS_DIR)):
        if name.endswith('.js'):
            yield os.path.join('js', name), os.path.join(JS_DIR, name)


def classify(px, line):
    if px < 10.0:
        return 'FATAL'
    if px == 10.0:
        return None if EXEMPT.search(line) else 'GATED'
    if px <= DRIFT_HI and px not in LADDER:
        return 'DRIFT'
    return None


def scan_css():
    hits = {'FATAL': [], 'GATED': [], 'DRIFT': []}
    for rel, path in css_files():
        with open(path, encoding='utf-8') as f:
            for no, line in enumerate(f, 1):
                for pat in (CSS_FS, CSS_FONT_SH):
                    for m in pat.finditer(line):
                        px = float(m.group(1))
                        kind = classify(px, line)
                        if kind:
                            hits[kind].append((rel, no, px, line.strip()))
    return hits


def scan_js():
    rows = []
    for rel, path in js_files():
        with open(path, encoding='utf-8') as f:
            for no, line in enumerate(f, 1):
                for m in JS_FS.finditer(line):
                    px = float(m.group(1))
                    if px < 11.0:
                        rows.append((rel, no, px, line.strip()))
    return rows


def dump(title, rows, limit=60):
    if not rows:
        return
    print('%s（%d）' % (title, len(rows)))
    for rel, no, px, text in rows[:limit]:
        print('  %s:%d  %gpx  %s' % (rel, no, px, text[:120]))
    if len(rows) > limit:
        print('  … 其余 %d 条省略' % (len(rows) - limit))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true', help='GATED / DRIFT 一并升级为失败门禁')
    args = ap.parse_args()

    hits = scan_css()
    var_hits = scan_var_chain()
    inline = scan_js()
    print('Castline · type_lint · %s' % ('STRICT' if args.strict else 'REPORT'))
    print('FATAL <10px: %d · GATED 10px 无豁免: %d · DRIFT 阶梯外: %d · JS 内联 <11px: %d'
          % (len(hits['FATAL']), len(hits['GATED']), len(hits['DRIFT']), len(inline)))
    print('var 链解析档：FATAL %d · GATED %d · DRIFT %d（默认只报告，--strict 一并拦截）'
          % (len(var_hits['FATAL']), len(var_hits['GATED']), len(var_hits['DRIFT'])))

    dump('FATAL · 10px 以下（阶梯已废除）', hits['FATAL'])
    dump('GATED · 10px 缺 T5 刻度豁免注释', hits['GATED'])
    dump('DRIFT · 10–13px 阶梯外漂移值', hits['DRIFT'])
    dump('VAR-FATAL · var 链解出 <10px', var_hits['FATAL'])
    dump('VAR-GATED · var 链解出 10px 缺 T5 刻度豁免注释', var_hits['GATED'])
    dump('VAR-DRIFT · var 链解出 10–13px 阶梯外漂移值', var_hits['DRIFT'])
    dump('JS 内联字号 <11px（报告，不拦截）', inline, limit=40)

    fail = list(hits['FATAL'])
    if args.strict:
        fail += hits['GATED'] + hits['DRIFT']
        fail += var_hits['FATAL'] + var_hits['GATED'] + var_hits['DRIFT']
    if fail:
        print('TYPE LINT FAIL · %d 条违规' % len(fail))
        return 1
    print('TYPE LINT OK · %s' % ('零违规' if args.strict else '报告完成'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
