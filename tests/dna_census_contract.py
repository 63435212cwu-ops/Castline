#!/usr/bin/env python3
"""P06 DNA 普查契约：对账必须有判别力，且数值必须自洽。

背景（P13-wave3 独立复核缺陷）：`dna_census.py` 的章节对账原本是**同义反复** ——
`declared` 硬编码为 904/101/125，而它的定义（source-index 的 declaredSource）
正是 `distinct(events[].chapter)`，与左侧 `chapterLabels` 同一个量，
`!=` 恒为假 ⇒ `gaps` 结构上不可能产出。与 `dnaCarve` 的早退分支不可达同构。

本契约锁住修好后的性质：
  1. 对账的两侧**必须不同源**（正文解析 vs 图谱标签），否则退化为同义反复；
  2. 两侧不同时必须产出 gap（**证明判别力**，不是永远空数组）；
  3. 两侧相同时不得产出该 gap（**证明不虚报**）。

离线只读，不写任何文件。
    python3 tests/dna_census_contract.py
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIS = ROOT / "tests" / "fixtures" / "contracts" / "visual"

BOOKS = [
    ("dna-dafeng", "大奉打更人"),
    ("dna-xiyou", "西游记"),
    ("dna-sanguo", "三国演义"),
]


def load(name: str) -> dict:
    p = VIS / f"{name}.json"
    if not p.exists():
        raise AssertionError(f"required DNA fixture missing: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


class DnaCensusContract(unittest.TestCase):

    def test_reconciliation_uses_two_independent_paths(self):
        """两侧必须不同源：正文解析 vs 图谱事件标签。"""
        for name, title in BOOKS:
            d = load(name)
            i = d.get("inputs") or {}
            with self.subTest(book=title):
                self.assertIn("textChapterHeadings", i,
                              f"{title} 缺独立口径字段 —— 对账可能退化为同义反复")
                self.assertIn("chapterLabels", i)
                self.assertIn("declaredChapters", i)

    def test_gap_fires_when_paths_disagree(self):
        """判别力证明：两侧不同时必须产出 gap。

        这是本条契约的**核心** —— 修好之前 gaps 恒为空（同义反复）。
        """
        fired = 0
        for name, title in BOOKS:
            d = load(name)
            i = d["inputs"]
            a, b = i.get("textChapterHeadings"), i.get("chapterLabels")
            if a is None or b is None or a == b:
                continue
            gaps = d.get("gaps") or []
            with self.subTest(book=title):
                self.assertTrue(
                    any("不一致" in str(g) for g in gaps),
                    f"{title} 正文解析 {a} ≠ 图谱标签 {b}，却未产出 gap —— 对账没有判别力")
            fired += 1
        self.assertGreater(fired, 0,
                           "三书两侧全部相等 ⇒ 本契约无法证明判别力，需换样本")

    def test_no_gap_when_paths_agree(self):
        """不虚报：两侧相等时不得产出「不一致」类 gap。"""
        for name, title in BOOKS:
            d = load(name)
            i = d["inputs"]
            a, b = i.get("textChapterHeadings"), i.get("chapterLabels")
            with self.subTest(book=title):
                if a is not None and a == b:
                    gaps = [str(g) for g in (d.get("gaps") or [])]
                    self.assertFalse(any("不一致" in g for g in gaps),
                                     f"{title} 两侧相等却报了不一致：{gaps}")

    def test_gap_text_states_both_denominators(self):
        """gap 文案必须同时给出两个口径的数，供审计复核。"""
        for name, title in BOOKS:
            d = load(name)
            for g in d.get("gaps") or []:
                g = str(g)
                if "不一致" not in g:
                    continue
                with self.subTest(book=title, gap=g[:40]):
                    self.assertIn("口径", g,
                                  f"{title} 的 gap 未说明口径差异，无法审计：{g[:120]}")

    def test_dna_values_are_in_declared_ranges(self):
        """DNA 输出必须落在 sky-dna.js 声明的 RANGE 内（防越界夹取掩盖）。"""
        ranges = {"layerBands": (1, 3), "fray": (0.10, 0.62), "cut": (0.30, 0.66),
                  "bandThick": (0.050, 0.170), "bandTilt": (8, 34),
                  "avoidDeg": (24, 28), "dustN": (900, 2600)}
        for name, title in BOOKS:
            d = load(name)
            dna = d.get("dna") or {}
            for k, (lo, hi) in ranges.items():
                if k not in dna:
                    continue
                with self.subTest(book=title, key=k):
                    self.assertGreaterEqual(dna[k], lo, f"{title}.{k} 低于声明下限")
                    self.assertLessEqual(dna[k], hi, f"{title}.{k} 高于声明上限")


if __name__ == "__main__":
    unittest.main(verbosity=2)
