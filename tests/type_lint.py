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
# `font:` 简写同样定义字号，且藏得更深——T7 实测里 6.5px–9.5px 全部躲在这里，
# 只 grep font-size 会漏报。简写语法中字号是 `/line-height` 之前的那个长度值。
CSS_FONT_SH = re.compile(r'(?<!-)\bfont\s*:\s*[^;{}]*?(?<![\w.-])([0-9]+(?:\.[0-9]+)?)px(?=\s*[/\s])')
JS_FS = re.compile(r'font-size\s*[:=]\s*"?\'?\s*([0-9]+(?:\.[0-9]+)?)px')
EXEMPT = re.compile(r'T5\s*刻度豁免')

LADDER = (10.0, 11.0, 12.0, 13.0, 16.0)
DRIFT_HI = 13.0          # 13px 以上归标题域，不做阶梯收口


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
    inline = scan_js()
    print('Castline · type_lint · %s' % ('STRICT' if args.strict else 'REPORT'))
    print('FATAL <10px: %d · GATED 10px 无豁免: %d · DRIFT 阶梯外: %d · JS 内联 <11px: %d'
          % (len(hits['FATAL']), len(hits['GATED']), len(hits['DRIFT']), len(inline)))

    dump('FATAL · 10px 以下（阶梯已废除）', hits['FATAL'])
    dump('GATED · 10px 缺 T5 刻度豁免注释', hits['GATED'])
    dump('DRIFT · 10–13px 阶梯外漂移值', hits['DRIFT'])
    dump('JS 内联字号 <11px（报告，不拦截）', inline, limit=40)

    fail = list(hits['FATAL'])
    if args.strict:
        fail += hits['GATED'] + hits['DRIFT']
    if fail:
        print('TYPE LINT FAIL · %d 条违规' % len(fail))
        return 1
    print('TYPE LINT OK · %s' % ('零违规' if args.strict else '报告完成'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
