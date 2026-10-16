# -*- coding: utf-8 -*-
"""引文解析器（build-only，不属于候选产物本身）。

口径（与任务提示词一致，全部**现算**，不手抄偏移）：
  · start/end 是相对 docs[0].text **全文**的绝对 codepoint 偏移，0-based，左闭右开。
  · quote 必须满足 text[start:end] == quote；否则抛异常，构建失败。
  · occ（切片内出现次数）与 globalOcc（全文出现次数）现算。
  · 额外给出 paraLabel / contentAnchor / sentenceIdx 作为**定位辅助字段**，
    它们不是判据；判据只有 start/end 的逐字成立。
"""

import json
import re

DOCS = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
RANGE = (934756, 943450)

_TEXT = None
_PARAS = None


def text():
    global _TEXT
    if _TEXT is None:
        with open(DOCS, encoding="utf-8") as fh:
            _TEXT = json.load(fh)[0]["text"]
    return _TEXT


def paragraphs():
    """切片内非空行的 (label, start, end)，P001 起编号。"""
    global _PARAS
    if _PARAS is None:
        t = text()
        out = []
        n = 0
        for m in re.finditer(r"[^\n]+", t[RANGE[0]:RANGE[1]]):
            if m.group(0).strip():
                n += 1
                out.append(("P%03d" % n, RANGE[0] + m.start(), RANGE[0] + m.end()))
        _PARAS = out
    return _PARAS


def _para_of(start, end):
    for lab, a, b in paragraphs():
        if a <= start and end <= b:
            return lab, a, b
    return None, None, None


def _sentence_bounds(a, b):
    """把一段切成句子（句末标点 + 引号尾），返回 [(s,e)]。"""
    seg = text()[a:b]
    bounds = []
    last = 0
    for m in re.finditer(r"[。！？…”]+|[.…]{2,}", seg):
        bounds.append((a + last, a + m.end()))
        last = m.end()
    if last < len(seg):
        bounds.append((a + last, b))
    return bounds


def _sentence_idx(start, end):
    t = text()
    out = []
    for lab, a, b in paragraphs():
        if b <= start:
            continue
        if a >= end:
            break
        for i, (sa, sb) in enumerate(_sentence_bounds(a, b)):
            if sa < end and sb > start:
                # 句子下标按**切片内**累计会更稳，但这里保留段内下标 + 段标签，
                # 与同目录 L0:0232 候选的口径一致（sentenceIdx 是段内下标）。
                out.append(i)
    return out


def q(quote, *, unique_in_slice=True):
    """解析一条引文；返回带全部定位字段的 dict。

    定位口径：在**本单元区间内**找第一处命中（不是我手写的偏移）。
    全文别处出现同样的句子不算错 —— `wholeTextOccurrences` 照实记下来，
    复核者据此知道这条引文在全文中并不唯一，唯一性只在**单元区间**内成立
    （实测踩坑：`“等等！”` 在全文里第一处出现在偏移 3026，属别的章节）。
    """
    t = text()
    seg = t[RANGE[0]:RANGE[1]]
    k = seg.find(quote)
    if k < 0:
        raise SystemExit("引文在本单元区间内找不到（逐字不符）：%r" % quote[:60])
    start = RANGE[0] + k
    end = start + len(quote)
    if not (RANGE[0] <= start and end <= RANGE[1]):
        raise SystemExit("引文越出本单元区间：%r @[%d,%d)" % (quote[:40], start, end))
    if t[start:end] != quote:
        raise SystemExit("自检失败 text[start:end] != quote：%r" % quote[:40])
    occ = t.count(quote)
    in_slice = t[RANGE[0]:RANGE[1]].count(quote)
    if unique_in_slice and in_slice != 1:
        raise SystemExit("引文在切片内出现 %d 次（要求 1）：%r" % (in_slice, quote[:40]))
    lab, a, b = _para_of(start, end)
    if lab is None:
        raise SystemExit("引文跨段，无法给段锚：%r" % quote[:40])
    return {
        "quote": quote,
        "start": start,
        "end": end,
        "sourceHash": SRC_HASH,
        "offsetUnit": "codepoint",
        "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
        "match": "exact",
        "wholeTextOccurrences": occ,
        "occurrencesInRange": in_slice,
        "paraLabel": lab,
        "contentAnchor": "%s[%d:%d]" % (lab, start - a, end - a),
        "sentenceIdx": _sentence_idx(start, end),
    }
