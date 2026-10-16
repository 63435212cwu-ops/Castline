# -*- coding: utf-8 -*-
"""引文定位器：把 quotes_0253.py 里的「锚」解析成带全文 codepoint 偏移的 quoteRef。

设计要点（为什么这么做）：
  · 手写 start/end 会因 off-by-one 静默出错 ⇒ 偏移由 index() 现算。
  · 手抄整句会有错别字 ⇒ quote 由切片现场生成，不手抄。
  · 锚必须在本区间内**唯一**，否则报错退出（不产出候选）。
"""
import hashlib
import json
import os
import sys

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
TASK = os.path.join(ROOT, "loop/state/runs/task-read_dafeng_L1_0253.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quotes_0253 import QUOTES  # noqa: E402


class ResolveError(Exception):
    pass


def load():
    task = json.load(open(TASK, encoding="utf-8"))
    raw = open(DOCS, "rb").read()
    file_sha = hashlib.sha256(raw).hexdigest()
    docs = json.loads(raw.decode("utf-8"))
    text = docs[0]["text"]
    s, e = task["sourceRange"]
    return task, file_sha, text, s, e


def build_index(text, s, e):
    """返回 {label: quoteRef}；每条附带区间内命中数（必须 == 1）。"""
    sl = text[s:e]
    out = {}
    problems = []
    for label, (a_anchor, b_anchor) in QUOTES.items():
        na = sl.count(a_anchor)
        if na != 1:
            problems.append("%s: 起始锚 %r 在区间内命中 %d 次（要求 1）" % (label, a_anchor, na))
            continue
        a = sl.index(a_anchor)
        if a_anchor == b_anchor:
            b = a + len(a_anchor)
        else:
            nb = sl.count(b_anchor)
            if nb != 1:
                problems.append("%s: 结束锚 %r 在区间内命中 %d 次（要求 1）" % (label, b_anchor, nb))
                continue
            b2 = sl.index(b_anchor, a)
            if b2 < a:
                problems.append("%s: 结束锚位于起始锚之前" % label)
                continue
            b = b2 + len(b_anchor)
        if b <= a:
            problems.append("%s: 空区间" % label)
            continue
        quote = sl[a:b]
        # 回读自检（同一口径）
        assert text[s + a:s + b] == quote
        out[label] = {
            "quote": quote,
            "start": s + a,
            "end": s + b,
            "sourceHash": None,  # 由调用方填
            "_hitsInSlice": sl.count(quote),
        }
    if problems:
        raise ResolveError("\n".join(problems))
    return out


if __name__ == "__main__":
    task, file_sha, text, s, e = load()
    assert file_sha == task["sourceHash"], "docs.json sha256 与任务声明不符"
    idx = build_index(text, s, e)
    for label, r in idx.items():
        print("%-16s hits=%d len=%4d  %s" % (label, r["_hitsInSlice"], len(r["quote"]), r["quote"][:70].replace("\n", "\\n")))
    print("共 %d 条" % len(idx))
