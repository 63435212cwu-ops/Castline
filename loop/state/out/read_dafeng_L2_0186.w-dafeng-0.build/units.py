#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三级单元切分（段 / 句 / 分句），偏移一律为 docs[0].text 全文绝对 codepoint。

切分规则是**明写**的，供复核用同一规则复算：
  · 段：切片内以空行分隔的非空块，行首缩进剥掉；
  · 句：段内按终止符 。！？… 切（终止符后若紧跟收尾引号/括号，一并并入本句）；
  · 分句：句内再按 ，、；： 切（分隔符归前一个分句）。
"""
import re

TERM = "。！？…"
CLOSERS = "”』）)》"
SUB = "，、；："


def paragraphs(text, S, E):
    """返回 [(para_index, start, end, body)]，para_index 从 1 开始。"""
    out = []
    seg = text[S:E]
    for m in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", seg):
        raw = m.group(0)
        if not raw.strip():
            continue
        lead = len(raw) - len(raw.lstrip())
        body = raw.strip()
        a = S + m.start() + lead
        out.append((len(out) + 1, a, a + len(body), body))
    return out


def sentences(body, base):
    """把一段切成句，返回 [(start, end, text)]（绝对偏移）。"""
    out, cur = [], 0
    i = 0
    while i < len(body):
        ch = body[i]
        if ch in TERM:
            j = i + 1
            while j < len(body) and body[j] in CLOSERS:
                j += 1
            out.append((base + cur, base + j, body[cur:j]))
            cur = j
            i = j
            continue
        i += 1
    if cur < len(body):
        out.append((base + cur, base + len(body), body[cur:]))
    return [(a, b, s) for (a, b, s) in out if s.strip()]


def clauses(sent, base):
    out, cur = [], 0
    i = 0
    while i < len(sent):
        if sent[i] in SUB:
            out.append((base + cur, base + i + 1, sent[cur:i + 1]))
            cur = i + 1
        i += 1
    if cur < len(sent):
        out.append((base + cur, base + len(sent), sent[cur:]))
    return [(a, b, s) for (a, b, s) in out if s.strip()]


def build_units(text, S, E):
    """返回 (paras, sents, cls, locate)，locate(offset) -> (para, sent, clause)。"""
    paras = paragraphs(text, S, E)
    sents, cls, locate = [], [], {}
    for pidx, a, b, body in paras:
        for sa, sb, stext in sentences(body, a):
            sidx = len(sents) + 1
            sents.append((sidx, pidx, sa, sb, stext))
            for ca, cb, ctext in clauses(stext, sa):
                cidx = len(cls) + 1
                cls.append((cidx, pidx, sidx, ca, cb, ctext))
                for off in range(ca, cb):
                    locate.setdefault(off, (pidx, sidx, cidx))
    return paras, sents, cls, locate
