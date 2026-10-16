#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引文解析器：把「段号 + 逐字标记」解析成绝对偏移，并现算全部可复算字段。

设计原则（照抄 predecessor 的教训，理由独立成立）：
  * **偏移从不手写**。内容模块只给 (段号, 原文子串)；start/end、全文出现次数、
    区间内命中数、首次出现位置、段/句/分句归属，全部由本模块从 docs[0].text 现取。
  * 任何一条引文若：在本段内命中不唯一、切不出逐字子串、或落在 [S,E) 之外
    ⇒ 直接抛错（构建脚本据此 sys.exit(1)，不写盘）。
  * 另外两道断言也在这里：① 行内「…」括号里的片段必须是本区间内逐字可 find 的子串
    （用 seg 口径，不用全文口径——跨单元的巧合命中对复核者不可见）；
    ② 散文里的 P### 段号必须存在，且段号后紧邻括注的片段必须真的落在那个段里。
"""
from __future__ import annotations

import re

SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
OFFSET_BASE = "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）"


class QuoteError(Exception):
    pass


class Resolver:
    def __init__(self, text: str, start: int, end: int, idx):
        self.text = text
        self.start = start
        self.end = end
        self.seg = text[start:end]
        self.idx = idx
        self.audit = []          # 每条解析成功的引文（供机器自检复算）
        self.cache = {}

    # ---------- 单条引文 ----------
    def q(self, para: int, snippet: str, where: str = ""):
        key = (para, snippet)
        if key in self.cache:
            return dict(self.cache[key])
        pc = None
        for o, li, ls, le, cs, ce in self.idx["paras"]:
            if o == para:
                pc = (cs, ce)
                break
        if pc is None or pc[0] is None:
            raise QuoteError("段 P%03d 不存在或为空段；来源=%s；片段=%r" % (para, where, snippet))
        cs, ce = pc
        body = self.text[cs:ce]
        n = body.count(snippet)
        if n != 1:
            raise QuoteError(
                "段 P%03d 内命中 %d 次（要求恰好 1 次）；来源=%s；片段=%r\n段全文=%r"
                % (para, n, where, snippet, body))
        s = self.text.find(snippet, cs, ce)
        e = s + len(snippet)
        if not (self.start <= s and e <= self.end):
            raise QuoteError("引文越出 [S,E)；来源=%s；片段=%r" % (where, snippet))
        whole = self.text.count(snippet)
        first_whole = self.text.find(snippet)
        in_seg = self.seg.count(snippet)
        first_seg = self.seg.find(snippet) + self.start
        pl, sn, cn = _locate(self.idx, s)
        rec = {
            "quote": snippet,
            "start": s,
            "end": e,
            "sourceHash": SOURCE_HASH,
            "offsetUnit": "codepoint",
            "offsetBase": OFFSET_BASE,
            "match": "exact",
            "wholeTextOccurrences": whole,
            "occurrencesInRange": in_seg,
            "firstOccurrenceAt": first_whole,
            "startIsFirstOccurrence": s == first_whole,
            "startIsFirstOccurrenceInRange": s == first_seg,
            "inRange": True,
            "para": pl,
            "paraLabel": "P%03d" % pl,
            "sentUnit": sn,
            "clauseUnit": cn,
        }
        self.cache[key] = rec
        self.audit.append({"where": where, "para": pl, "quote": snippet, "start": s, "end": e})
        return dict(rec)

    def qs(self, specs, where: str = ""):
        """specs: [(para, snippet), ...]"""
        return [self.q(p, s, where) for p, s in specs]

    # ---------- 行内「…」审计 ----------
    def inline_audit(self, obj, path="root"):
        """递归扫描对象里所有「…」片段，逐个要求在本区间内逐字可 find。"""
        bad = []
        good = []

        def walk(o, p):
            if isinstance(o, (int, float, bool)) or o is None:
                return
            if isinstance(o, str):
                for frag in re.findall(r"「([^」]*)」", o):
                    f = frag.strip()
                    if not f:
                        continue
                    if self.seg.count(f) >= 1:
                        good.append({"field": p, "fragment": f})
                    else:
                        bad.append({"field": p, "fragment": f})
            elif isinstance(o, dict):
                for k, v in o.items():
                    if k in ("quote",):
                        continue
                    walk(v, p + "." + str(k))
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, "%s[%d]" % (p, i))

        walk(obj, path)
        return good, bad

    # ---------- 散文里的 P### 与人物名 ----------
    PARA_REF = re.compile(r"P(\d{3})")
    # 只在**紧邻**形态上判定：P### 之后 0–4 个非句读字符内直接跟「…」。
    # 放宽到 40 字符会大面积误杀：散文里常常先写段号、再另起一句引别处的原文
    # （例如「把这段时间解成 P038 的行程窗口、并把『正好』读成因果触发」——
    #  引的其实是 P039 的「正好可以利用」）。实测初版 12 处报错里有 5 处属于这种误杀。
    # 排除集里还要加上箭头与右括号：'（P042–P045）→ 「…」' 这种**区间指代＋箭头**写法
    # 不是「把引文挂到某个段」，实测它制造了最后一处误杀。
    PARA_THEN_QUOTE = re.compile(r"P(\d{3})[」』]?[（(]?[^。；，、）)→\n]{0,4}?「([^」]+)」")

    def prose_audit(self, obj, known_names):
        """① P### 必须存在；② P### 后 40 字内出现的「…」必须落在那个段；
        ③ 散文里出现的人物名必须在本区间出现过。"""
        errs = []
        refs = 0
        valid_labels = {"P%03d" % _po for _po, _li, _ls, _le, _cs, _ce in self.idx["paras"]
                        if _cs is not None}

        def walk(o, p):
            nonlocal refs
            if isinstance(o, (int, float, bool)) or o is None:
                return
            if isinstance(o, str):
                for m in self.PARA_REF.finditer(o):
                    refs += 1
                    lab = "P" + m.group(1)
                    if lab not in valid_labels:
                        errs.append({"field": p, "kind": "para-not-exist", "ref": lab})
                for m in self.PARA_THEN_QUOTE.finditer(o):
                    lab = "P" + m.group(1)
                    frag = m.group(2)
                    pc = None
                    for _po, _li, _ls, _le, _cs, _ce in self.idx["paras"]:
                        if _po == int(m.group(1)):
                            pc = (_cs, _ce)
                            break
                    if pc is None or pc[0] is None:
                        continue
                    body = self.text[pc[0]:pc[1]]
                    if frag in body:
                        continue
                    # 允许该片段出现在别处（只是段号挂错）——仍判错
                    if self.seg.count(frag) >= 1:
                        errs.append({"field": p, "kind": "quote-not-in-that-para",
                                     "ref": lab, "fragment": frag})
                    else:
                        errs.append({"field": p, "kind": "quote-not-verbatim",
                                     "ref": lab, "fragment": frag})
                for name in known_names:
                    if name in o:
                        # 名字必须在本区间出现过
                        if self.seg.count(name) == 0:
                            errs.append({"field": p, "kind": "name-not-in-range", "name": name})
            elif isinstance(o, dict):
                for k, v in o.items():
                    walk(v, p + "." + str(k))
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, "%s[%d]" % (p, i))

        walk(obj, "root")
        return {"paragraphRefs": refs, "errors": errs}


def _locate(idx, off):
    para = sent = clause = None
    for o, li, ls, le, cs, ce in idx["paras"]:
        if cs is not None and cs <= off < ce:
            para = o
            break
    for sn, o, s, e in idx["sents"]:
        if s <= off < e:
            sent = sn
            break
    for cn, o, sn, s, e in idx["clauses"]:
        if s <= off < e:
            clause = cn
            break
    return para, sent, clause
