#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引文规格 → 绝对偏移解析器。

**为什么引文不手写偏移**：手写 start/end 是这条流水线上最容易出错的一步
（实测过若干单元的偏移口径错、字符串非逐字）。本模块让内容层**只给段落号 + 定位标记**，
偏移一律由脚本从 docs[0].text 现取；找不到、越界、或切片内命中不唯一即 sys.exit(1)。

规格形态：
  Q("P038")                              → 整段
  Q("P038", "“不是说笑，”", "相好。”")     → 段内从 start 标记首次出现处起，到 end 标记
                                            （含）为止；两个标记都必须逐字存在且 end 在 start 之后。
"""
import sys

SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
DOCS = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
RANGE = (676201, 679978)
OFFSET_BASE = "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）"


def Q(para, start=None, end=None):
    return {"para": para, "start": start, "end": end}


class Resolver:
    def __init__(self, text, units):
        self.text = text
        self.paras, self.sents, self.cls, self.locate = units
        self.by_key = {("P%03d" % p[0]): p for p in self.paras}
        self.resolved = []

    def body(self, para_key):
        row = self.by_key.get(para_key)
        if row is None:
            sys.exit("未知段落号：%s" % para_key)
        return row

    def quote(self, spec):
        pidx, a, b, body = self.body(spec["para"])
        if spec["start"] is None:
            qa, qb, q = a, b, body
        else:
            i = body.find(spec["start"])
            if i < 0:
                sys.exit("start 标记在 %s 中不存在：%r" % (spec["para"], spec["start"]))
            j = body.find(spec["end"], i + len(spec["start"]))
            if j < 0:
                sys.exit("end 标记在 %s 中不存在（start 之后）：%r" % (spec["para"], spec["end"]))
            if j + len(spec["end"]) <= i:
                sys.exit("end 标记不在 start 之后：%s" % spec["para"])
            qa = a + i
            qb = a + j + len(spec["end"])
            q = self.text[qa:qb]
        if self.text[qa:qb] != q:
            sys.exit("内部错误：切片与引文不一致 %s" % spec["para"])
        S, E = RANGE
        if not (S <= qa < qb <= E):
            sys.exit("引文越出单元区间：%s [%d,%d)" % (spec["para"], qa, qb))
        seg = self.text[S:E]
        occ_range = seg.count(q)
        occ_doc = self.text.count(q)
        if occ_range != 1:
            sys.exit("引文在区间内命中 %d 次（要求唯一）：%s %r" % (occ_range, spec["para"], q[:40]))
        pidx2, sidx, cidx = self.locate[qa]
        qobj = {
            "quote": q,
            "start": qa,
            "end": qb,
            "sourceHash": SOURCE_HASH,
            "offsetUnit": "codepoint",
            "offsetBase": OFFSET_BASE,
            "match": "exact",
            "wholeTextOccurrences": occ_doc,
            "occurrencesInRange": occ_range,
            "firstOccurrenceAt": self.text.find(q),
            "startIsFirstOccurrence": self.text.find(q) == qa,
            "startIsFirstOccurrenceInRange": seg.find(q) + S == qa,
            "inRange": True,
            "para": pidx2,
            "sentUnit": sidx,
            "clauseUnit": cidx,
        }
        self.resolved.append(qobj)
        return qobj

    def quotes(self, specs):
        return [self.quote(s) for s in specs]
