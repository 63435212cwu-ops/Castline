#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立核验 read_dafeng_L3_0219.candidate.json。

与 build_candidate.py 的**关键区别**：本脚本不复用构建期算出的任何偏移作为输入，
而是把候选里每条 quote 当字符串，重新用 `text.find` 在全文里定位，再比对候选声明的
start/end 是否一致。构建脚本的 bug（例如偏移算错、区间口径写成切片相对）会在这一步暴露。

同时核验：
  · sourceHash = 整个 docs.json 的 sha256
  · 切片 sha256（附加字段）
  · 每条引文在**本区间内**唯一（防「引了同名但别处的句子」）
  · 任务五栏引文两两不相交
  · null 栏位都带同名 Note
  · 六个必需分区都在
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0219.candidate.json"
S_START, S_END = 817425, 821142
EXPECT_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

problems = []
checks = []


def ok(name, detail=""):
    checks.append({"check": name, "result": "pass", "detail": detail})


def bad(name, detail):
    problems.append({"check": name, "detail": detail})
    checks.append({"check": name, "result": "fail", "detail": detail})


raw = DOCS.read_bytes()
h = hashlib.sha256(raw).hexdigest()
if h != EXPECT_HASH:
    bad("sourceHash", "%s != %s" % (h, EXPECT_HASH))
else:
    ok("sourceHash", h)

TEXT = json.loads(raw)[0]["text"]
SLICE = TEXT[S_START:S_END]

cand = json.load(open(CAND, encoding="utf-8"))

# 1) 候选自己声明的 sourceHash
decl = cand["source"]["sha256"]
if decl != h:
    bad("candidate.source.sha256", "%s != %s" % (decl, h))
else:
    ok("candidate.source.sha256", decl)

seg = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()
if cand["source"].get("segmentSha256") != seg:
    bad("segmentSha256", "声明 %s 实际 %s" % (cand["source"].get("segmentSha256"), seg))
else:
    ok("segmentSha256", seg)

# 2) 边界：切片以单元标题开头
if not SLICE.startswith(cand["unitHead"]):
    bad("sliceHead", "切片开头 %r 不以 %r 开头" % (SLICE[:30], cand["unitHead"]))
else:
    ok("sliceHead", SLICE[:30])

# 3) 逐条引文：用 find 重新定位，比对声明偏移
nodes = []


def walk(node, path="root"):
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            nodes.append((path, node))
        for k, v in node.items():
            walk(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i))


walk({k: v for k, v in cand.items() if k != "source"})

n_found = n_off = n_range = n_unique = n_hash = n_declared = 0
globally_unique = 0
for path, node in nodes:
    lit, st, en = node["quote"], node["start"], node["end"]
    found = TEXT.find(lit)
    if found < 0:
        bad("quote-find", "%s 找不到：%r" % (path, lit[:40]))
        continue
    n_found += 1
    # 偏移口径（本轮修正）：只有当引文**全书唯一**时，find==start 才是必然要求。
    # 不唯一的串（如分隔线 `------------`，全书 1031 次）必须自报定位强度，
    # 否则下游无法区分「偏移错了」与「这句本来就到处都有」。
    occ = len(re.findall(re.escape(lit), TEXT))
    if occ == 1:
        globally_unique += 1
        if found != st:
            bad("quote-offset", "%s find=%d 但候选声明 start=%d" % (path, found, st))
        else:
            n_off += 1
    else:
        # 非唯一：要求候选显式声明，且声明与实际一致
        if node.get("wholeTextOccurrences") != occ:
            bad("quote-occurrence-declared",
                "%s 全书 %d 次，候选声明 %r" % (path, occ, node.get("wholeTextOccurrences")))
        if node.get("inRangeOccurrences") != 1:
            bad("quote-inrange-declared",
                "%s 区间内出现次数声明 %r（应为 1）" % (path, node.get("inRangeOccurrences")))
        if not str(node.get("locatorStrength") or "").startswith("unique-within-range-only"):
            bad("quote-locator-strength",
                "%s 全书 %d 次却没有声明定位强度：%r" % (path, occ, node.get("locatorStrength")))
        if TEXT[st:en] == lit:
            n_off += 1
    if TEXT[st:en] != lit:
        bad("quote-slice", "%s text[start:end]!=quote" % path)
    if not (S_START <= st and en <= S_END):
        bad("quote-range", "%s [%d,%d) 超区间" % (path, st, en))
    else:
        n_range += 1
    if node.get("sourceHash") != h:
        bad("quote-hash", "%s sourceHash 不符" % path)
    else:
        n_hash += 1
    # 区间内唯一性
    cnt = 0
    p = TEXT.find(lit, S_START)
    while p >= 0 and p + len(lit) <= S_END:
        cnt += 1
        p = TEXT.find(lit, p + 1)
    if cnt != 1:
        bad("quote-inrange-unique", "%s 在区间内出现 %d 次：%r" % (path, cnt, lit[:40]))
    else:
        n_unique += 1

if n_found == len(nodes):
    ok("all-quotes-findable", "%d/%d" % (n_found, len(nodes)))
if n_off == len(nodes) and n_found == len(nodes):
    ok("all-offsets-consistent",
       "%d/%d（其中 %d 条全书唯一、按 find==start 严格校验；其余按「区间内唯一 + 显式声明定位强度」校验）"
       % (n_off, len(nodes), globally_unique))
if n_range == len(nodes):
    ok("all-quotes-in-range", "%d/%d" % (n_range, len(nodes)))
if n_unique == len(nodes):
    ok("all-quotes-unique-in-range", "%d/%d" % (n_unique, len(nodes)))
if n_hash == len(nodes):
    ok("all-quote-sourceHash", "%d/%d" % (n_hash, len(nodes)))

# 4) 任务五栏互斥
FIELDS = ("objective", "obstacle", "action", "result", "cost")
coll = []
for t in cand.get("tasks") or []:
    seen = {}
    ivs = []
    for f in FIELDS:
        for nd in t.get(f + "Quotes") or []:
            if nd["quote"] in seen:
                coll.append({"task": t["id"], "quote": nd["quote"][:30],
                             "fields": [seen[nd["quote"]], f]})
            seen[nd["quote"]] = f
            ivs.append((nd["start"], nd["end"], f))
    ivs.sort()
    for i in range(len(ivs)):
        for j in range(i + 1, len(ivs)):
            if ivs[i][1] > ivs[j][0] and ivs[i][0] < ivs[j][1]:
                coll.append({"task": t["id"], "overlap": [ivs[i][2], ivs[j][2]]})
if coll:
    bad("task-field-mutex", str(coll[:5]))
else:
    ok("task-field-mutex", "五栏引文无复用、无区间重叠（%d 条任务）" % len(cand.get("tasks") or []))

# 5) null 栏带 Note
nn = []
for t in cand.get("tasks") or []:
    for f in FIELDS:
        if t.get(f) is None and not (t.get(f + "Note") or "").strip():
            nn.append({"task": t["id"], "field": f})
if nn:
    bad("null-with-note", str(nn))
else:
    ok("null-with-note", "所有 null 栏位都有同名 Note")

# 6) 必需分区
REQ = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
miss = [k for k in REQ if k not in cand]
if miss:
    bad("required-sections", "缺 %s" % miss)
else:
    ok("required-sections", ",".join(REQ))

# 7) worldSettings 三态字段
wsp = []
for w in cand.get("worldSettings") or []:
    k = w.get("kind")
    if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        wsp.append(w.get("id"))
    elif k == "item" and not w.get("itemStates"):
        wsp.append(w.get("id"))
    elif k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        wsp.append(w.get("id"))
    elif k not in ("place", "item", "rule"):
        wsp.append(w.get("id"))
if wsp:
    bad("worldSettings-shape", str(wsp))
else:
    ok("worldSettings-shape", "%d 条三态区分齐全" % len(cand.get("worldSettings") or []))

# 8) semanticReview 不得写成已完成
sr = cand.get("semanticReview")
if sr != "not-performed":
    bad("semanticReview-honest", "semanticReview=%r（READER 不得声称完成语义复核）" % sr)
else:
    ok("semanticReview-honest", "not-performed")

# 9) foreshadows：无回收必须显式 unresolved
fsp = []
for f in cand.get("foreshadows") or []:
    if f.get("payoff") in (None, "") and "unresolved" not in str(f.get("status", "")):
        fsp.append({"id": f.get("id"), "status": f.get("status")})
if fsp:
    bad("foreshadow-unresolved-marked", str(fsp))
else:
    ok("foreshadow-unresolved-marked", "%d 条" % len(cand.get("foreshadows") or []))

result = {
    "verifier": "loop/state/out/read_dafeng_L3_0219.w-xiyou-0.build/verify_candidate.py",
    "candidate": str(CAND.relative_to(ROOT)),
    "candidateSha256": hashlib.sha256(CAND.read_bytes()).hexdigest(),
    "quoteNodesChecked": len(nodes),
    "checks": checks,
    "problems": problems,
    "verdict": "pass" if not problems else "fail",
}

outp = ROOT / "loop/state/out/read_dafeng_L3_0219.w-xiyou-0.build/verify_report.json"
outp.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

for c in checks:
    print("[%s] %s %s" % (c["result"], c["check"], c["detail"][:90]))
print()
print("quoteNodes=%d problems=%d verdict=%s" % (len(nodes), len(problems), result["verdict"]))
print("report -> %s" % outp)
sys.exit(1 if problems else 0)
