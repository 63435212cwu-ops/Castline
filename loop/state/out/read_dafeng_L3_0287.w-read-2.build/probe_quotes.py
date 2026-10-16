# -*- coding: utf-8 -*-
"""引文体检：把我打算用的每条引文在切片里定位一遍，报告全部问题（不 fail-fast）。

为什么要先跑这个：build_candidate.py 遇到第一条坏引文就退出，一轮只能修一条。
这个探针一次列出「找不到 / 出现多次 / label 声明段落与实际不符」的全部条目，
并在找不到时打印片段末尾的原文，便于照抄修正。

复现：python3 loop/state/out/read_dafeng_L3_0287.w-read-2.build/probe_quotes.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

sys.path.insert(0, HERE)
from content_0287 import QUOTES, OCC  # noqa: E402

START, END = 1230135, 1234614
DOCS = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
DOC = json.loads(open(DOCS, "rb").read().decode("utf-8"))
TEXT = DOC[0]["text"]
SLICE = TEXT[START:END]

bad = []
for label in sorted(QUOTES):
    q = QUOTES[label]
    occ = OCC.get(label, 0)
    hits = []
    cur = 0
    while True:
        k = SLICE.find(q, cur)
        if k < 0:
            break
        hits.append(k)
        cur = k + 1
    if not hits:
        bad.append((label, "NOT_FOUND", q))
        continue
    if len(hits) <= occ:
        bad.append((label, "OCC_TOO_BIG(%d hits, occ=%d)" % (len(hits), occ), q))
        continue
    k = hits[occ]
    para = SLICE.count("\n", 0, k)
    m = re.match(r"^p(\d{3})_", label)
    if m and int(m.group(1)) != para:
        bad.append((label, "PARA_MISMATCH(label P%s, actual P%03d)" % (m.group(1), para), q))
    if len(hits) > 1 and label not in OCC:
        bad.append((label, "AMBIGUOUS(%d hits, no OCC)" % len(hits), q))

print("引文 %d 条，问题 %d 条" % (len(QUOTES), len(bad)))
for label, why, q in bad:
    print("\n[%s] %s" % (why, label))
    print("  声明: %r" % q)
    # 把该 label 声明段落附近的原文打出来，便于照抄
    m = re.match(r"^p(\d{3})_", label)
    if m:
        paras = SLICE.split("\n")
        i = int(m.group(1))
        if i < len(paras):
            print("  P%03d 原文: %r" % (i, paras[i]))
print("\nAMBIGUOUS 但已给 OCC 的：%s"
      % sorted(l for l in QUOTES if l in OCC))
sys.exit(1 if bad else 0)
