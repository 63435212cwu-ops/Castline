#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core：从 docs[0].text 现取引文、回填偏移、构造期断言。

设计理由（与上一轮 0211 复核口径一致）：
  * 引文一律**由标记对 (前文, 后文) 现取**，不手写 start/end —— 手写偏移是
    「定位看似正确、实为巧合」的主要来源；
  * 取出的每一条必须满足 T[start:end]==quote 且 T.find(quote)==start
    （全文唯一），否则构造期直接抛错，不落盘；
  * quote 必须落在本单元区间内；
  * claimStatus 由引号密度**机械标注**，不由人工判断。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data" / "cache" / "1063b17ca65ec1b76f30e460.docs.json"
GRAPH = ROOT / "data" / "cache" / "1063b17ca65ec1b76f30e460.json"

UNIT_START = 799532
UNIT_END = 805083
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
SOURCE_PATH = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
ANCHOR_RULE = "marker-derived-substring-of-docs[0].text"
CLAIM_RULE = "quoted-char-ratio>0.85→dialogue, 0<ratio≤0.85→mixed, 无引号→narration"


def load_text() -> str:
    d = json.loads(DOCS.read_text("utf-8"))
    return d[0]["text"]


TEXT = load_text()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


assert sha256_file(DOCS) == SOURCE_HASH, "docs.json 哈希与任务声明不符"
assert TEXT[UNIT_START:UNIT_END].startswith("第两百一十四章 扑朔迷离"), "区间不以标题开头"


def claim_status(q: str) -> str:
    """引号密度机械标注：不透语义，只看引号字符占比。"""
    if "“" not in q:
        return "narration"
    # 引号包裹的字符数 / 总字符数
    quoted = sum(len(m.group(1)) for m in re.finditer(r"“([^”]*)”", q))
    ratio = quoted / max(1, len(q))
    return "dialogue" if ratio > 0.85 else "mixed"


class QuoteError(RuntimeError):
    pass


def Q(head: str, tail: str, occurrence: int = 0) -> dict:
    """按 (头标记, 尾标记) 在全文里**现取**一段引文并回填偏移。

    head 是引文的开头片段，tail 是引文的结尾片段；本函数取「第一次出现
    head…tail（含）」的整段。找到后逐项断言，任一不成立即抛错。
    """
    hi = TEXT.find(head)
    if hi < 0:
        raise QuoteError("头标记在全文找不到：%r" % head[:40])
    if occurrence:
        for _ in range(occurrence):
            hi = TEXT.find(head, hi + 1)
            if hi < 0:
                raise QuoteError("头标记第 %d 次出现找不到：%r" % (occurrence, head[:40]))
    ti = TEXT.find(tail, hi)
    if ti < 0:
        raise QuoteError("尾标记在头标记之后找不到：%r → %r" % (head[:30], tail[:30]))
    end = ti + len(tail)
    q = TEXT[hi:end]
    return quote_node(q, hi, end)


def quote_node(q: str, start: int, end: int) -> dict:
    if TEXT[start:end] != q:
        raise QuoteError("T[start:end] != quote：%r" % q[:40])
    if TEXT.find(q) != start:
        raise QuoteError("引文在全文不唯一（find=%d，声明=%d）：%r"
                         % (TEXT.find(q), start, q[:40]))
    if not (UNIT_START <= start < end <= UNIT_END):
        raise QuoteError("引文越出本单元区间：%d,%d %r" % (start, end, q[:40]))
    return {
        "quote": q,
        "start": start,
        "end": end,
        "offsetUnit": "absolute-doc-codepoint",
        "sourceHash": SOURCE_HASH,
        "sourcePath": SOURCE_PATH,
        "docIndex": 0,
        "inUnitRange": True,
        "occurrencesInWholeDoc": TEXT.count(q),
        "occurrencesInSlice": TEXT[UNIT_START:UNIT_END].count(q),
        "match": "exact",
        "anchorRule": ANCHOR_RULE,
        "claimStatus": claim_status(q),
        "claimStatusRule": CLAIM_RULE,
    }


def Qn(q: str) -> dict:
    """已知逐字字符串，直接定位（仅用于无歧义、可 find 的整句）。"""
    i = TEXT.find(q)
    if i < 0:
        raise QuoteError("引文在全文找不到：%r" % q[:40])
    return quote_node(q, i, i + len(q))


def slice_sha() -> str:
    return hashlib.sha256(TEXT[UNIT_START:UNIT_END].encode("utf-8")).hexdigest()
