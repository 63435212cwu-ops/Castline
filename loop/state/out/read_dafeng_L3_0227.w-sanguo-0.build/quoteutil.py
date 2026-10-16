#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L3:0227 的引用定位工具。

口径（与任务 prompt 一致，2026-10-13）：
  · START/END 是相对 docs[0].text **全文** 的 codepoint 偏移；
  · 每条 quote 的 start/end 用 TEXT.find(quote, START, END) 现算，绝手写；
  · sourceHash 是**整个 docs.json 文件**的 sha256（不是切片）；
  · 切片哈希另起 sliceSha256 字段，不覆盖 sourceHash。
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DOCS = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
TASKF = os.path.join(ROOT, "loop", "state", "runs", "task-read_dafeng_L3_0227.json")

TASK = json.load(open(TASKF, encoding="utf-8"))
START, END = TASK["sourceRange"]
UNIT_HEAD = TASK["unitHead"]
EXPECT = TASK["sourceHash"]

with open(DOCS, "rb") as fh:
    RAW = fh.read()
FILE_SHA256 = hashlib.sha256(RAW).hexdigest()
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[START:END]
SLICE_SHA256 = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

_errors = []


def errors():
    return list(_errors)


def Q(s):
    """定位一条逐字引文。

    找不到时**不抛异常**而是登记错误并返回一个带 `_unlocated` 标记的占位 dict：
    一次运行就能看到全部失败引文（逐条修），而不是改一条跑一次。
    占位 dict 缺 start/end，会让构建脚本末尾的自检必然失败 ⇒ 仍然拒绝写出。
    """
    if not isinstance(s, str) or not s:
        _errors.append("空引文")
        return {"quote": s, "_unlocated": True}
    pos = TEXT.find(s, START, END)
    if pos < 0:
        _errors.append("区间内找不到引文：%r%s" % (s[:60], _nearest(s)))
        return {"quote": s, "_unlocated": True}
    end = pos + len(s)
    if TEXT[pos:end] != s:
        _errors.append("回填不一致：%r" % s[:60])
        return {"quote": s, "_unlocated": True}
    whole = TEXT.count(s)
    inrange = TEXT.count(s, START, END)
    return {
        "quote": s,
        "start": pos,
        "end": end,
        "sourceHash": EXPECT,
        "wholeTextOccurrences": whole,
        "inRangeOccurrences": inrange,
        "firstGlobalOffset": TEXT.find(s),
        "startIsFirstGlobalOccurrence": TEXT.find(s) == pos,
        "locatorStrength": ("globally-unique" if whole == 1
                            else ("range-unique" if inrange == 1 else "range-ambiguous")),
    }


def _nearest(s):
    """给失败引文找一段最像的原文，方便改错。"""
    import difflib
    probe = s[:24]
    idx = SLICE.find(probe[:12])
    if idx < 0:
        return ""
    cand = SLICE[max(0, idx - 40): idx + len(s) + 40]
    ratio = difflib.SequenceMatcher(None, s, cand).ratio()
    return "（最近似片段 %.2f：%r）" % (ratio, cand)


def where(d):
    """把一个 quote dict 变成 (start,end) 区间的短标记，便于查重叠。"""
    return (d["start"], d["end"])


def check_docs():
    """开工前自检：源文件哈希 + 切片边界。"""
    out = {}
    out["docsSha256"] = FILE_SHA256
    out["docsSha256MatchesTask"] = FILE_SHA256 == EXPECT
    out["sliceCodepoints"] = len(SLICE)
    out["sliceMatchesRange"] = len(SLICE) == END - START
    out["sliceStartsWithUnitHead"] = SLICE.startswith(UNIT_HEAD)
    out["sliceSha256"] = SLICE_SHA256
    out["unitHead"] = UNIT_HEAD
    out["range"] = [START, END]
    return out
