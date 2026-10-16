# -*- coding: utf-8 -*-
"""read:dafeng:L3:0235 候选的独立复核脚本（无第三方依赖）。
用法：python3 -B -s /tmp/cl0235/verify_candidate.py
逐条把候选里的 quote 拿去 docs[0].text 里核对：text[start:end]==quote、
区间落在 [929759,934756) 内、sourceHash 等于 docs.json 的 sha256、
任务五栏不共用同一句引用、null 栏必须带同名 Note、六个必需分区都在。
"""
import hashlib
import json
import sys

ROOT = "/Users/carmen/Desktop/星系"
DOCS = ROOT + "/data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT + "/loop/state/out/read_dafeng_L3_0235.candidate.json"
START, END = 929759, 934756
EXPECT_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
REQUIRED_SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
FIELDS = ("objective", "obstacle", "action", "result", "cost")

problems = []

actual_hash = hashlib.sha256(open(DOCS, "rb").read()).hexdigest()
if actual_hash != EXPECT_HASH:
    problems.append("SOURCE_HASH_MISMATCH docs.json=%s expect=%s" % (actual_hash, EXPECT_HASH))

TEXT = json.load(open(DOCS, encoding="utf-8"))[0]["text"]
SLICE = TEXT[START:END]
if not SLICE.startswith("第六章 验尸"):
    problems.append("UNIT_HEAD_MISMATCH slice starts with %r" % SLICE[:20])

cand = json.load(open(CAND, encoding="utf-8"))
for sec in REQUIRED_SECTIONS:
    if sec not in cand:
        problems.append("MISSING_SECTION %s" % sec)

quotes = []


def walk(node, path):
    if isinstance(node, dict):
        if {"quote", "start", "end", "sourceHash"} <= set(node):
            quotes.append((path, node))
        for k, v in node.items():
            walk(v, path + "." + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + "[%d]" % i)


walk(cand, "$")

for path, q in quotes:
    s, e, txt = q["start"], q["end"], q["quote"]
    if TEXT[s:e] != txt:
        problems.append("QUOTE_MISMATCH %s text[%d:%d]=%r quote=%r" % (path, s, e, TEXT[s:e][:40], txt[:40]))
    if TEXT.find(txt) < 0:
        problems.append("QUOTE_NOT_FOUND %s %r" % (path, txt[:40]))
    if not (START <= s < e <= END):
        problems.append("QUOTE_OUT_OF_RANGE %s [%d,%d)" % (path, s, e))
    if q["sourceHash"] != EXPECT_HASH:
        problems.append("QUOTE_HASH_MISMATCH %s" % path)

for t in cand.get("tasks", []):
    seen = {}
    for f in FIELDS:
        for q in t.get(f + "Quotes") or []:
            if q["quote"] in seen:
                problems.append("FIELD_QUOTE_COLLISION %s %s/%s %r" % (t["id"], seen[q["quote"]], f, q["quote"][:30]))
            seen[q["quote"]] = f
        if t.get(f) is None and not (t.get(f + "Note") or "").strip():
            problems.append("NULL_WITHOUT_NOTE %s.%s" % (t["id"], f))
    spans = sorted((q["start"], q["end"], f) for f in FIELDS for q in (t.get(f + "Quotes") or []))
    for i in range(len(spans) - 1):
        if spans[i][1] > spans[i + 1][0] and spans[i][2] != spans[i + 1][2]:
            problems.append("FIELD_SPAN_OVERLAP %s %s/%s" % (t["id"], spans[i][2], spans[i + 1][2]))

# 跨任务引文复用（自设的比提示词更严的标准）
per_task = {}
for t in cand.get("tasks", []):
    per_task[t["id"]] = {q["quote"] for f in FIELDS for q in (t.get(f + "Quotes") or [])}
ids = sorted(per_task)
for i in range(len(ids)):
    for j in range(i + 1, len(ids)):
        shared = per_task[ids[i]] & per_task[ids[j]]
        if shared:
            problems.append("CROSS_TASK_QUOTE_REUSE %s/%s %r" % (ids[i], ids[j], sorted(shared)[0][:30]))

for t in cand.get("worldSettings", []):
    if t["kind"] == "place" and t.get("placeState") not in ("arrived", "mentioned"):
        problems.append("PLACE_STATE_BAD %s" % t["id"])
    if t["kind"] == "item":
        st = t.get("itemStates") or []
        if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            problems.append("ITEM_STATES_BAD %s %r" % (t["id"], st))
    if t["kind"] == "rule" and t.get("institution") not in ("declared", "executed", "misunderstood"):
        problems.append("INSTITUTION_BAD %s" % t["id"])

print("引文节点：%d，唯一引文串：%d" % (len(quotes), len({q[1]["quote"] for q in quotes})))
print("worldSettings：rule=%d place=%d item=%d" % (
    sum(1 for w in cand.get("worldSettings", []) if w["kind"] == "rule"),
    sum(1 for w in cand.get("worldSettings", []) if w["kind"] == "place"),
    sum(1 for w in cand.get("worldSettings", []) if w["kind"] == "item")))
if problems:
    for p in problems:
        print("[FAIL]", p)
    print("总计 %d 个问题" % len(problems))
    sys.exit(1)
print("ALL CHECKS PASS")
