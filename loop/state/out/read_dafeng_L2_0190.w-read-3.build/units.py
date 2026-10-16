#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三级切分：段（非空行）/ 句 / 分句。规则明写，供复核者用同一规则复算。

为什么把规则写死在这里而不是各分区自己数：coverage 的段/句/分句分母、
以及「同一任务五栏不共用一句」这条纪律的判据，都必须能被复核者**独立复算**。
规则一旦含糊（例如「句」按什么切），复核就只能相信我的数字。

绝对偏移口径：全部是 docs[0].text 全文的 codepoint 偏移（0-based，左闭右开）。
段号 `para` 采用**原始行号（0-based，按 '\\n' 切）**，与候选里 P### 标签一一对应；
空行也占一个行号，但不计入「非空段」分母。
"""
from __future__ import annotations

SENT_TERMINATORS = "。！？"
CLAUSE_SEPARATORS = "，、；："
ELLIPSIS_CHARS = ".…"


def paragraphs(text: str, start: int, end: int):
    """返回 [(line_index, abs_start, abs_end, content_start, content_end)]。

    line_index：原始行号（按 '\\n' 切分全文后，落在 [start,end) 内的那些行）。
    content_*：去掉首尾空白后的区间；空行返回 None。
    """
    out = []
    # 找到 start 所在行号
    line_index = text.count("\n", 0, start)
    pos = start
    while pos < end:
        nl = text.find("\n", pos, end)
        line_end = end if nl == -1 else nl
        raw = text[pos:line_end]
        stripped = raw.strip()
        if stripped:
            lead = len(raw) - len(raw.lstrip())
            cs = pos + lead
            ce = cs + len(stripped)
            out.append((line_index, pos, line_end, cs, ce))
        else:
            out.append((line_index, pos, line_end, None, None))
        pos = line_end + 1
        line_index += 1
    return out


def _cut(text: str, start: int, end: int, terminators: str, run_chars: str = ""):
    """按终止符切分 [start,end)，终止符归入前一个单元。连续同类终止符合为一个。"""
    spans = []
    i = start
    cur = start
    while i < end:
        ch = text[i]
        if ch in terminators or (run_chars and ch in run_chars):
            j = i
            if run_chars and ch in run_chars:
                while j + 1 < end and text[j + 1] in run_chars:
                    j += 1
            else:
                while j + 1 < end and text[j + 1] == ch:
                    j += 1
            spans.append((cur, j + 1))
            cur = j + 1
            i = j + 1
            continue
        i += 1
    if cur < end:
        spans.append((cur, end))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def sentences(text: str, cstart: int, cend: int):
    return _cut(text, cstart, cend, SENT_TERMINATORS, ELLIPSIS_CHARS)


def clauses(text: str, sstart: int, send: int):
    return _cut(text, sstart, send, CLAUSE_SEPARATORS, "")


def unit_index(text: str, start: int, end: int):
    """构建段/句/分句三级台账。

    段号口径（与复核者可见的 P### 标签一致）：**本切片内非空段的 1-based 序号**，
    标题行是 P001。同时保留原始行号 line_index 供反查。
      paras:   [(para_ordinal, line_index, line_start, line_end, content_start, content_end)]
      sents:   [(sent_no(1-based), para_ordinal, s, e)]
      clauses: [(clause_no(1-based), para_ordinal, sent_no, s, e)]
    """
    paras = [p for p in paragraphs(text, start, end)]
    out_paras = []
    ordinal = 0
    for line_index, ls, le, cs, ce in paras:
        if cs is None:
            out_paras.append((None, line_index, ls, le, None, None))
        else:
            ordinal += 1
            out_paras.append((ordinal, line_index, ls, le, cs, ce))
    sents = []
    clause_list = []
    sn = 0
    cn = 0
    for ordinal, line_index, ls, le, cs, ce in out_paras:
        if cs is None:
            continue
        for s, e in sentences(text, cs, ce):
            sn += 1
            sents.append((sn, ordinal, s, e))
            for a, b in clauses(text, s, e):
                cn += 1
                clause_list.append((cn, ordinal, sn, a, b))
    return {"paras": out_paras, "sents": sents, "clauses": clause_list}


def locate(idx, text: str, off: int):
    """给定绝对偏移，回查它属于哪个段（P### 序号）/句/分句。"""
    para = None
    for ordinal, line_index, ls, le, cs, ce in idx["paras"]:
        if cs is not None and cs <= off < ce:
            para = ordinal
            break
    sent = None
    for sn, ordinal, s, e in idx["sents"]:
        if s <= off < e:
            sent = sn
            break
    clause = None
    for cn, ordinal, sn, s, e in idx["clauses"]:
        if s <= off < e:
            clause = cn
            break
    return para, sent, clause


def para_content(idx, ordinal):
    for o, line_index, ls, le, cs, ce in idx["paras"]:
        if o == ordinal:
            return None if cs is None else (cs, ce)
    return None
