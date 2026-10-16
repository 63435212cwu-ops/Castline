#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引文探针：构建前把每条引文在 docs[0].text 里定位一次，报告问题。

检查的问题（任一非空 ⇒ 非零退出）：
  · not-found          引文在全文里找不到（附「最相近的原文片段」建议，便于改正笔误）
  · occ-out-of-range   声明的 occ 超出实际出现次数
  · too-long-cross-para 跨段引文超过 CROSS_PARA_MAX 字（防止用超长引文掩盖「其实没定位」）
  · out-of-unit        引文落在本单元 [1286538,1295556) 之外
  · too-short          引文短于 MIN_LEN，无法作为定位证据
  · kind-invalid       kind 不在允许集合内
  · slice-mismatch     text[start:end] != quote（理论不该发生）

单独报告（不算问题）：
  · ambiguous          同一引文在全文出现多次（候选里用 occ 消歧，必须写明）
  · cross-paragraph    引文跨空行（候选里必须显式写 spansParagraphs=true，不许静默）
  · negative-control   故意埋的、预期找不到的引文，用来证明 find 不是恒真
"""
import difflib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
START, END = 1286538, 1295556
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
MIN_LEN = 6
CROSS_PARA_MAX = 40  # 跨段引文允许，但必须短：它只用来说明「两段紧邻」，不是叙事证据
KINDS = {"narration", "dialogue", "inner", "free_indirect", "parable", "author_note"}
NEGATIVE_CONTROL = {"nm_net_a"}  # 故意过短：必须被 too-short 或 not-found 挡下

sys.path.insert(0, str(HERE))
from quotes_0295 import QUOTES  # noqa: E402


def locate(text, quote, occ):
    """按 occ 取第 occ 次出现，返回 (start, end) 或 None。"""
    pos = -1
    for _ in range(occ + 1):
        pos = text.find(quote, pos + 1)
        if pos < 0:
            return None
    return pos, pos + len(quote)


def suggest(text, quote, lo, hi):
    """在单元附近滑动窗口，找与 quote 最相近的等长片段，用于改笔误。"""
    best = (0.0, None, None)
    n = len(quote)
    step = max(1, n // 8)
    for p in range(lo, max(lo + 1, hi - n), step):
        cand = text[p:p + n]
        r = difflib.SequenceMatcher(None, quote, cand).ratio()
        if r > best[0]:
            best = (r, p, cand)
    return best


def main():
    text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    problems, ambiguous, neg_ok = [], [], []
    cross_para = []
    in_unit = 0
    rows = []

    for key, (quote, occ, kind) in sorted(QUOTES.items()):
        if key in NEGATIVE_CONTROL:
            hit = locate(text, quote, occ)
            if hit is None or len(quote) < MIN_LEN:
                neg_ok.append(key)
            else:
                problems.append("%s: 负对照竟然通过了（len=%d）" % (key, len(quote)))
            continue

        if kind not in KINDS:
            problems.append("%s: kind-invalid %r" % (key, kind))
        if len(quote) < MIN_LEN:
            problems.append("%s: too-short len=%d %r" % (key, len(quote), quote))
            continue

        n = text.count(quote)
        hit = locate(text, quote, occ)
        if hit is None:
            r, p, cand = suggest(text, quote, START, END)
            problems.append("%s: not-found count=%d occ=%d quote=%r\n        → 最相近(%.2f) @%s: %r"
                            % (key, n, occ, quote[:60], r, p, (cand or "")[:60]))
            continue

        start, end = hit
        if text[start:end] != quote:
            problems.append("%s: slice-mismatch" % key)
        if "\n\n" in quote:
            if len(quote) > CROSS_PARA_MAX:
                problems.append("%s: too-long-cross-para len=%d > %d" % (key, len(quote), CROSS_PARA_MAX))
            else:
                cross_para.append("%s: 跨 1 个空行，len=%d" % (key, len(quote)))
        if not (START <= start and end <= END):
            problems.append("%s: out-of-unit [%d,%d) 不在 [%d,%d)" % (key, start, end, START, END))
        else:
            in_unit += 1
        if n > 1:
            ambiguous.append("%s: 全文 %d 次，取 occ=%d @%d" % (key, n, occ, start))
        rows.append((start, key, end, kind, quote.replace("\n", "\\n")))

    print("引文 %d 条；落在本单元内 %d 条" % (len(QUOTES), in_unit))
    print("多义引文（occ 消歧）：%d 条" % len(ambiguous))
    for a in ambiguous:
        print("    ~", a)
    print("负对照按预期被挡下：%s" % (neg_ok,))
    print("跨段引文：%d 条" % len(cross_para))
    for c in cross_para:
        print("    ¶", c)
    print("问题：%d 条" % len(problems))
    for p in problems:
        print("    !", p)

    (HERE / "probe_located.tsv").write_text(
        "\n".join("%d\t%s\t%d\t%s\t%s" % r for r in sorted(rows)) + "\n", encoding="utf-8")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
