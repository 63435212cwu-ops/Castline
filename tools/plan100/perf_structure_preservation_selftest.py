#!/usr/bin/env python3
"""P10 · perf_structure_preservation.py 的负向自检：证明验证器不是「永远 PASS」。

**为什么必须有这个文件**：一个把所有断言都写成 `return True` 的验证器也能让
结构保留报告全绿。本自检用**变异测试**证明验证器真的会 FAIL：

  变异 1  把 astrolabe 的 `structure: true` 改成 `false`   → 必须命中 S1
  变异 2  把 QSPEC 低画质档改成 `labels: 'none'` + `glow: 0` → 必须命中 S2
  变异 3  让 `applyDetail` 在 d0 时 `n.el.remove()`          → 必须命中 S4
  基线    不做任何变异                                      → 必须 0 违例

**安全约束**：所有变异只改内存里的字符串副本，**不写盘**。
既不触碰 `js/` 下的文件（其中多个是他人独占），也不留临时文件。

用法：python3 tools/plan100/perf_structure_preservation_selftest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'plan100'))

import perf_structure_preservation as SP

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  — ' + detail) if detail and not cond else ''))


# ------------------------------------------------------------------ 变异算子
def mutate_astrolabe_not_structural(s):
    """结构位被撤：astrolabe 从 structure:true 变 false。"""
    old = "uniform: 'uLyrAstro', on: 1, off: 0, structure: true,"
    new = "uniform: 'uLyrAstro', on: 1, off: 0, structure: false,"
    if old not in s:
        raise AssertionError('变异锚点未找到（astrolabe structure 行）：源码可能已改动')
    return s.replace(old, new, 1)


def mutate_qspec_low_broken(s):
    """低画质档结构规格坏掉：labels 非法 + glow 归零。"""
    old = "{ steps: 1, dof: 0, ghost: 0, caust: 0, glow: 4,  labels: 'd0' }"
    new = "{ steps: 1, dof: 0, ghost: 0, caust: 0, glow: 0,  labels: 'none' }"
    if old not in s:
        raise AssertionError('变异锚点未找到（QSPEC 低画质行）：源码可能已改动')
    return s.replace(old, new, 1)


def mutate_apply_detail_removes(s):
    """档位切换时删节点：结构从「只降密度」变成「真的删」。"""
    old = "function applyDetail(n, d) {\n      if (n._d === d) return;"
    new = ("function applyDetail(n, d) {\n      if (n._d === d) return;\n"
           "      if (d === 0) { n.el.remove(); return; }")
    if old not in s:
        raise AssertionError('变异锚点未找到（applyDetail 开头）：源码可能已改动')
    return s.replace(old, new, 1)


def run_with_mutations(muts):
    """在内存里替换 read_src 的返回值，跑一遍完整判定链。"""
    orig = SP.read_src

    def fake_read(rel):
        raw, clean, sha = orig(rel)
        if rel in muts:
            raw = muts[rel](raw)
            clean = SP.strip_comments(raw)
        return raw, clean, sha

    SP.read_src = fake_read
    try:
        s1 = SP.parse_layer_registry()
        s2 = SP.parse_qspec()
        s3 = SP.parse_abyss_tiers()
        s4 = SP.parse_label_details()
        s5 = SP.parse_webgl_fallback()
        res, viol = SP.evaluate(SP.MODES, s1, s2, s3, s4, s5)
        return res, viol
    finally:
        SP.read_src = orig


def main():
    print('=' * 84)
    print('structure_preservation.py 负向自检（变异测试）')
    print('=' * 84)

    cases = [
        ('变异1 astrolabe structure:true→false（结构位被撤）',
         {'js/core/material-layers.js': mutate_astrolabe_not_structural}, {'S1'}),
        ('变异2 QSPEC 低画质 labels=none + glow=0（规格坏）',
         {'js/core/scene-core.js': mutate_qspec_low_broken}, {'S2'}),
        ('变异3 applyDetail 在 d0 时删节点（结构被删）',
         {'js/core/scene-lod-labels.js': mutate_apply_detail_removes}, {'S4'}),
    ]

    print()
    for name, muts, expect in cases:
        try:
            res, viol = run_with_mutations(muts)
        except AssertionError as exc:
            check(name, False, str(exc))
            continue
        ids = sorted({v['structureId'] for v in viol})
        ok = bool(viol) and expect <= set(ids)
        check(name, ok, '期望命中 %s，实得违例 %d 条 / 结构位 %s'
              % (sorted(expect), len(viol), ids))

    print()
    res, viol = run_with_mutations({})
    check('基线（无变异）0 违例', not viol,
          '实得 %d 条：%s' % (len(viol), [v['structureId'] for v in viol]))

    print()
    print('=' * 84)
    print('负向自检：PASS %d · FAIL %d' % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print('  FAILED: %s' % f)
        return 1
    print('验证器非空转：三类结构破坏都能被检出，基线不被误伤。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
