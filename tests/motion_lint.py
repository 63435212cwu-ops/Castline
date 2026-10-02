#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星渊 G4 · 动效三层台账门禁。

动效宪法（总纲表 4-3）只认三层：
  仪式层 0.9–4s   一次性、叙事事件（聚焦 / 生长 / 解码 / 巡礼）
  氛围层 20–200s  循环、潜意识存在感（星云天象 / 进动 / 深渊之瞳 / 呼吸）
  反馈层 ≤300ms   操作确认

禁止带 = **0.3–20s 的循环**：既不够快到算反馈，又不够慢到沉入潜意识，
是「装饰性循环」的温床。逐条审判结论只有两种——升格为仪式（去掉 infinite，
改一次性）或降格入氛围（拉长到 ≥20s 并降亮）。

只扫 CSS 里带 `infinite` 的 animation 简写：非循环动效不受禁止带约束。
默认报告模式列清单；`--strict` 把禁止带内的循环升级为拦截。
豁免写法：同行注释 `G4 豁免:<理由>`（用于已审判并接受的历史资产）。
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_DIR = os.path.join(ROOT, 'css')

ANIM = re.compile(r'animation\s*:\s*([^;}]*)')
DUR = re.compile(r'(?<![\w.-])([0-9]*\.?[0-9]+)(m?s)(?![\w-])')
EXEMPT = re.compile(r'G4\s*豁免')

BAN_LO = 0.3     # 反馈层上界
BAN_HI = 20.0    # 氛围层下界


def seconds(value, unit):
    return float(value) / 1000.0 if unit == 'ms' else float(value)


def split_shorthand(decl):
    """按顶层逗号切分 animation 简写。

    教训：不能直接 `decl.split(',')`——`var(--abyss-dur-breath,21s)` 的回落值里
    也有逗号。而且简写可以挂多条动画（`a .9s forwards,b 3.4s infinite`），
    只有带 `infinite` 的那一段才受禁止带约束，取整条的第一个时长是错的。
    """
    parts, depth, cur = [], 0, ''
    for ch in decl:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def css_files():
    for name in sorted(os.listdir(CSS_DIR)):
        if name.endswith('.css'):
            yield os.path.join('css', name), os.path.join(CSS_DIR, name)


def scan():
    banned, exempt, atmos, ritual = [], [], [], []
    for rel, path in css_files():
        with open(path, encoding='utf-8') as f:
            for no, line in enumerate(f, 1):
                for m in ANIM.finditer(line):
                    decl = m.group(1)
                    # 只看挂了 infinite 的那几段；每段自己的第一个时长才是 duration。
                    durs = []
                    for seg in split_shorthand(decl):
                        if 'infinite' not in seg:
                            continue
                        hits = DUR.findall(seg)
                        if hits:
                            durs.append(seconds(*hits[0]))
                    if not durs:
                        continue
                    in_ban = [d for d in durs if BAN_LO < d < BAN_HI]
                    row = (rel, no, min(in_ban) if in_ban else min(durs), line.strip())
                    if in_ban:
                        if EXEMPT.search(line):
                            exempt.append(row)
                        else:
                            banned.append(row)
                    elif min(durs) >= BAN_HI:
                        atmos.append(row)
    return banned, exempt, atmos, ritual


def dump(title, rows, limit=60):
    if not rows:
        return
    print('%s（%d）' % (title, len(rows)))
    for rel, no, d, text in sorted(rows, key=lambda r: r[2])[:limit]:
        print('  %s:%d  %gs  %s' % (rel, no, d, text[:120]))
    if len(rows) > limit:
        print('  … 其余 %d 条省略' % (len(rows) - limit))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true', help='禁止带内的循环升级为失败门禁')
    args = ap.parse_args()

    banned, exempt, atmos, _ = scan()
    print('Castline · motion_lint · %s' % ('STRICT' if args.strict else 'REPORT'))
    print('禁止带循环 %g–%gs: %d · 已审判豁免: %d · 氛围层 ≥%gs: %d'
          % (BAN_LO, BAN_HI, len(banned), len(exempt), BAN_HI, len(atmos)))

    dump('禁止带 · 待审判的装饰性循环（升格为仪式 或 拉长到 ≥20s）', banned)
    dump('已审判豁免（G4 豁免注释）', exempt, limit=20)
    dump('氛围层 · 合规循环', atmos, limit=20)

    if args.strict and banned:
        print('MOTION LINT FAIL · %d 条循环落在禁止带' % len(banned))
        return 1
    print('MOTION LINT OK · %s' % ('报告完成' if not args.strict else '零违规'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
