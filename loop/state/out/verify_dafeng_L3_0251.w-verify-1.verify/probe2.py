#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify:dafeng:L3:0251 · 第三探针（w-verify-1 自写）：候选形态判据的**更严版本**。

候选自报「五栏区间两两不相交」。区间不相交比提示词要求的「同一句话不得当多栏依据」
更严 —— 但只在**字符**层更严。反方向存在一个漏洞：
两个字段各引**同一句里互不重叠的两段子串**时，区间判据通过，而提示词要防的
「同一句话同时充当多栏依据」依然成立。本探针按**句级**重算。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
text = json.loads((ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json").read_text("utf-8"))[0]["text"]
cand = json.loads((ROOT / "loop/state/out/read_dafeng_L3_0251.candidate.json").read_text("utf-8"))
START, END = 1032194, 1038254

problems = []

# ── 独立句子表：按 。！？… 与换行切，保留绝对偏移 ─────────────────────────
sents = []
for m in re.finditer(r"[^\n]+", text[START:END]):
    raw, base = m.group(0), START + m.start()
    if not raw.strip():
        continue
    for sm in re.finditer(r"[^。！？]*[。！？]|[^。！？]+$", raw):
        if sm.group(0).strip():
            sents.append((base + sm.start(), base + sm.end(), sm.group(0)))


def sidx(a: int, b: int):
    hit = [i for i, (s, e, _) in enumerate(sents) if s <= a < e or s < b <= e]
    return hit[0] if hit else None


FIELDS = ("objective", "obstacle", "action", "result", "cost")
print("=" * 100)
print("A. 句级五栏独立性（区间不相交以外的更严判据）")
same_sent = 0
for ti, t in enumerate(cand["tasks"]):
    per = {}
    for f in FIELDS:
        per[f] = {sidx(q["start"], q["end"]) for q in (t.get(f + "Quotes") or [])}
    for i, fa in enumerate(FIELDS):
        for fb in FIELDS[i + 1:]:
            both = {s for s in (per[fa] & per[fb]) if s is not None}
            if both:
                same_sent += 1
                for s in both:
                    print("  tasks[%d].%s × %s 共用句 #%d：%r"
                          % (ti, fa, fb, s, sents[s][2][:80]))
print("  句级跨栏共用 = %d" % same_sent)

print("=" * 100)
print("B. 每个非空栏是否都带可解析引文（候选 C7 声称）")
missing = []
for ti, t in enumerate(cand["tasks"]):
    for f in FIELDS:
        v = t.get(f)
        qs = t.get(f + "Quotes") or []
        if v is None:
            if qs:
                missing.append("tasks[%d].%s 值为 null 却有 %d 条引文" % (ti, f, len(qs)))
            if not (t.get(f + "Note") or "").strip():
                missing.append("tasks[%d].%s 为 null 且无 Note" % (ti, f))
        else:
            if not qs:
                missing.append("tasks[%d].%s 非空但无引文" % (ti, f))
print("  问题：%s" % (missing or "无"))
problems += missing

print("=" * 100)
print("C. 13 个 null 栏的清单是否与候选自报一致")
nulls = ["T%02d.%s" % (ti + 1, f) for ti, t in enumerate(cand["tasks"])
         for f in FIELDS if t.get(f) is None]
declared = cand["machineSelfCheck"]["nullFieldList"]
print("  实测：", nulls)
print("  自报：", declared)
print("  一致：", nulls == declared)
if nulls != declared:
    problems.append("null 清单不符")

print("=" * 100)
print("D. worldSettings 形状（我独立核，不用候选脚本）")
ws = cand["worldSettings"]
shape = []
for w in ws:
    k = w.get("kind")
    if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        shape.append("%s placeState=%r" % (w["id"], w.get("placeState")))
    if k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or not set(st) <= {"hold", "transfer", "use", "lose"}:
            shape.append("%s itemStates=%r" % (w["id"], st))
    if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        shape.append("%s institution=%r" % (w["id"], w.get("institution")))
    if not (w.get("explain") or "").strip():
        shape.append("%s 无 explain" % w["id"])
print("  形状问题：%s" % (shape or "无"))
problems += shape
from collections import Counter
print("  kind 分布：", dict(Counter(w["kind"] for w in ws)))
print("  placeState：", dict(Counter(w.get("placeState") for w in ws if w["kind"] == "place")))
print("  institution：", dict(Counter(w.get("institution") for w in ws if w["kind"] == "rule")))

print("=" * 100)
print("E. 先出现的 P 号乱序检查（候选正文里 Pnn 的引用是否与真实段号一致）")
# 抓「P<数字>」形式的引用，看该数字段的文本是否包含所引内容的关键词（弱判据，只报可疑）
para_text = {}
for i, m in enumerate(re.finditer(r"[^\n]+", text[START:END])):
    if m.group(0).strip():
        para_text[len(para_text) + 1] = m.group(0)
bad_para_ref = []
blob = json.dumps(cand, ensure_ascii=False)
for m in re.finditer(r"（?P(\d{1,3})[）)]?", blob):
    n = int(m.group(1))
    if n not in para_text:
        bad_para_ref.append("P%d 越界（本区间只有 %d 个非空段）" % (n, len(para_text)))
print("  越界 P 号：%s" % (sorted(set(bad_para_ref)) or "无"))
problems += sorted(set(bad_para_ref))

print("=" * 100)
print("F. sentence index 表大小")
print("  句子数 =", len(sents))

print("=" * 100)
print("PROBLEMS(%d): %s" % (len(problems), problems))
sys.exit(0)
