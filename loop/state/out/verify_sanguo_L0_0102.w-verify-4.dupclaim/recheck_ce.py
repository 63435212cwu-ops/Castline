#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核复核者 —— w-verify-4 自写。对被复核者 w-sanguo-1 的三条核心指控逐条机器复算：
  CE1  T07.cost 散文把 action 的整句当唯一依据（同句跨栏）
  CE2  T16.objective 的『甘心受辱』落在 obstacle 引文区间内
  CE3  「审俘→定策取上方谷」这条因果边在 causeEdges 里不存在
  CE4  候选句级覆盖口径掩盖句内未引用片段（"11 个藏在已覆盖句内"）
并核验其自己声明的数字（23 个片段）在什么口径下成立。
不 import 候选或被复核者的任何脚本。
"""
import json, os, re

ROOT = "/Users/carmen/Desktop/星系"
text = json.loads(open(os.path.join(ROOT, "data/cache/fe42d01f3826fe8096f86614.docs.json"),
                       "rb").read().decode())[0]["text"]
S, E = 522662, 528484
SL = text[S:E]
cand = json.load(open(os.path.join(ROOT, "loop/state/out/read_sanguo_L0_0102.candidate.json")))
T = {t["id"]: t for t in cand["tasks"]}

print("=" * 78)
print("CE1  T07.cost 散文是否把 action 的整句当唯一依据（同句跨栏）")
print("=" * 78)
cost = T["T07"]["cost"]
act_quotes = [q["quote"] for q in T["T07"]["action"]["quotes"]]
print("T07.cost.text = %s" % cost["text"])
for aq in act_quotes:
    hit = aq in cost["text"]
    print("  action 引文 %r 出现在 cost 散文里？ %s" % (aq[:44], hit))
cost_q = [q["quote"] for q in cost["quotes"]]
print("  cost 自己登记的引文：%s" % [q[:40] for q in cost_q])
for cq in cost_q:
    print("     %r 支持『五百兵当诱饵』？ %s" % (cq[:40], "五百兵" in cq or "诱" in cq))
print("  判定：cost 散文的依据句 = %r" % "魏延引五百兵皆退入谷中去。")
print("        该句在 action.quotes 中的登记区间:",
      [(q["start"], q["end"]) for q in T["T07"]["action"]["quotes"] if "五百兵" in q["quote"]])
print("        cost.quotes 区间:", [(q["start"], q["end"]) for q in cost["quotes"]])

print()
print("=" * 78)
print("CE2  T16.objective 的『甘心受辱』是否落在 obstacle 引文区间内")
print("=" * 78)
frag = "甘心受辱"
obj = T["T16"]["objective"]
obs = T["T16"]["obstacle"]
print("objective.text = %s" % obj["text"])
fo = text.find(frag)
print("『%s』全文偏移 = %d，区间 [%d,%d)" % (frag, fo, fo, fo + len(frag)))
for q in obj["quotes"]:
    print("  objective.quotes: [%d,%d) %r  含该片段？ %s"
          % (q["start"], q["end"], q["quote"][:40], q["start"] <= fo and fo + len(frag) <= q["end"]))
for q in obs["quotes"]:
    contains = q["start"] <= fo and fo + len(frag) <= q["end"]
    print("  obstacle.quotes : [%d,%d) %r  含该片段？ %s"
          % (q["start"], q["end"], q["quote"][:40], contains))
    if contains:
        print("     >>> 该片段整个落在 obstacle 的引文区间内 ⇒ 「同句跨栏」成立")

print()
print("=" * 78)
print("CE3  「审俘→定策取上方谷」因果边是否存在")
print("=" * 78)
probe = ["孔明今在何处", "在上方谷西十里下营", "乃唤诸将分付曰", "取上方谷烧其粮草", "使彼首尾不接"]
blob = json.dumps(cand, ensure_ascii=False)
for p in probe:
    print("  全文出现 %-24r 次数 = %d" % (p, blob.count(p)))
print("  --- causeEdges 中 frm/to/trigger/mechanism 提到「上方谷」+「粮」的边 ---")
hit = 0
for ce in cand["causeEdges"]:
    s = json.dumps(ce, ensure_ascii=False)
    if "上方谷" in s and ("粮" in s or "烧" in s):
        hit += 1
        print("   %s : %s -> %s" % (ce["id"], ce["frm"][:60], ce["to"][:60]))
print("   命中 %d 条" % hit)
print("  --- 该情报句在 tasks 里出现在哪 ---")
for t in cand["tasks"]:
    s = json.dumps(t, ensure_ascii=False)
    if "孔明今在何处" in s or "上方谷西十里" in s:
        print("   %s (%s): %s" % (t["id"], t["character"], t["summary"][:90]))

print()
print("=" * 78)
print("CE4  候选句级覆盖口径的盲区 —— 独立复算「藏在已覆盖句内的未引用片段」")
print("=" * 78)


def walk(o):
    if isinstance(o, dict):
        if isinstance(o.get("quote"), str) and "start" in o:
            yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


refs = [(q["start"], q["end"]) for q in walk(cand)]
mask = [0] * len(SL)
for a, b in refs:
    for k in range(max(a, S), min(b, E)):
        mask[k - S] = 1

PUNCT = set("　 \n\t“”‘’『』「」（）()《》〈〉、，。；：！？—…·．,.;:!?\"'")
sents = [(m.start(), m.end(), m.group()) for m in re.finditer(r"[^。！？\n]*[。！？]", SL)]
hidden = []
for a, b, t in sents:
    if len(t.strip()) < 12:
        continue
    if not any(x < S + b and S + a < y for x, y in refs):
        continue          # 该句本身完全没引用 —— 不属"句内盲区"
    runs, k = [], a
    while k < b:
        if mask[k] == 0:
            m = k
            while m < b and mask[m] == 0:
                m += 1
            runs.append((k, m))
            k = m
        else:
            k += 1
    for x, y in runs:
        seg = SL[x:y]
        if len(seg.strip()) >= 12:
            hidden.append((S + x, S + y, seg, t.strip()[:50]))
print("  独立复算：藏在「已覆盖句」内部的未引用 >=12(去空白) 片段 = %d" % len(hidden))
for a, b, seg, sent in hidden:
    vis = len([c for c in seg if c not in PUNCT])
    print("    [%d,%d) 去空白%2d/去标点%2d :: %r" % (a, b, len(seg.strip()), vis, seg.strip()[:60]))
print()
print("  被复核者声明 23 个片段 / 其中 11 个藏在已覆盖句内。")
print("  本脚本复算：藏在已覆盖句内 = %d" % len(hidden))

# 口径对照：23 这个数字在哪种口径下成立
runs, i = [], 0
while i < len(mask):
    if mask[i] == 0:
        j = i
        while j < len(mask) and mask[j] == 0:
            j += 1
        runs.append((i, j))
        i = j
    else:
        i += 1
for label, fn in (("len(strip())>=12", lambda s: len(s.strip()) >= 12),
                  ("去标点可见字>=12", lambda s: len([c for c in s if c not in PUNCT]) >= 12)):
    n = sum(1 for a, b in runs if fn(SL[a:b]))
    print("  全部未引用片段中 %-20s 的个数 = %d" % (label, n))
