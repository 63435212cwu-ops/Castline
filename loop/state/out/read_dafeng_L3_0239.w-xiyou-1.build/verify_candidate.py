# -*- coding: utf-8 -*-
"""read:dafeng:L3:0239 候选的独立复核脚本（无第三方依赖）。
用法：python3 -B -s loop/state/out/read_dafeng_L3_0239.w-xiyou-1.build/verify_candidate.py
逐条把候选里的 quote 拿去 docs[0].text 里核对：text[start:end]==quote、
区间落在 [956444,961678) 内、sourceHash 等于 docs.json 的 sha256、
任务五栏不共用同一句引用、null 栏必须带同名 Note、六个必需分区都在。
"""
import hashlib
import json
import sys

ROOT = "/Users/carmen/Desktop/星系"
DOCS = ROOT + "/data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT + "/loop/state/out/read_dafeng_L3_0239.candidate.json"
START, END = 956444, 961678
EXPECT_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
REQUIRED_SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
FIELDS = ("objective", "obstacle", "action", "result", "cost")

problems = []

actual_hash = hashlib.sha256(open(DOCS, "rb").read()).hexdigest()
if actual_hash != EXPECT_HASH:
    problems.append("SOURCE_HASH_MISMATCH docs.json=%s expect=%s" % (actual_hash, EXPECT_HASH))

TEXT = json.load(open(DOCS, encoding="utf-8"))[0]["text"]
SLICE = TEXT[START:END]
if not SLICE.startswith("第十章 许平志：你俩给我等着"):
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

# ── stateEvidence：placeState / itemStates 的判定必须有锚定证据 ──────────
# 这一条是本轮自查抓出的真实缺陷（见 build.py self_check 注释）：
# 判定依据原本只写在 explain 散文里，复核者无法用脚本验证「arrived 凭哪句」。
import re as _re

for t in cand.get("worldSettings", []):
    own = set()

    def _acc(node):
        if isinstance(node, dict):
            if {"quote", "start", "end", "sourceHash"} <= set(node):
                own.add(node["quote"])
            for v in node.values():
                _acc(v)
        elif isinstance(node, list):
            for v in node:
                _acc(v)

    _acc(t)
    if t["kind"] == "place":
        se = t.get("stateEvidence")
        if not se:
            problems.append("PLACE_NO_STATE_EVIDENCE %s（placeState 判定无锚定依据）" % t["id"])
    elif t["kind"] == "item":
        se = t.get("stateEvidence") or {}
        for st in ("hold", "transfer", "use", "lose"):
            if st not in se:
                problems.append("ITEM_STATE_EVIDENCE_MISSING_KEY %s.%s（无证据也要写 null）" % (t["id"], st))
        for st in t.get("itemStates") or []:
            if not se.get(st):
                problems.append("ITEM_STATE_NO_EVIDENCE %s 声明了 %s 但没有锚定证据" % (t["id"], st))
    # 散文里引的真原文必须在本条目锚定（否则读者会以为它已被逐字核验）
    for k, v in t.items():
        if not isinstance(v, str):
            continue
        for m in _re.findall(r"「([^」]+)」", v):
            if m in TEXT and not any(m in a for a in own):
                problems.append("UNANCHORED_REAL_QUOTE %s.%s %r" % (t["id"], k, m[:24]))

# states[] 前值/后值 + 锚点；null 前值必须带 Note
for s in cand.get("states", []):
    for k in ("who", "after", "anchor"):
        if not s.get(k):
            problems.append("STATE_MISSING_%s %s" % (k.upper(), s.get("id")))
    if s.get("before") is None and not (s.get("beforeNote") or "").strip():
        problems.append("STATE_NULL_BEFORE_WITHOUT_NOTE %s" % s.get("id"))

# themeReadings 三件套
for th in cand.get("themeReadings", []):
    for k in ("perspective", "support", "counter"):
        if not th.get(k):
            problems.append("THEME_MISSING_%s %s" % (k.upper(), th.get("id")))
if len(cand.get("themeReadings", [])) > 2:
    problems.append("THEME_TOO_MANY")

# foreshadows：必须有 setup；unresolved 必须写 unresolvedWhat
for f in cand.get("foreshadows", []):
    if not f.get("setup"):
        problems.append("FORESHADOW_NO_SETUP %s" % f.get("id"))
    if f.get("status") == "unresolved" and not (f.get("unresolvedWhat") or "").strip():
        problems.append("FORESHADOW_UNRESOLVED_NO_WHAT %s" % f.get("id"))

# 不得声称语义评审完成
if cand.get("semanticReview") != "not-performed":
    problems.append("SEMANTIC_REVIEW_CLAIMED %r" % cand.get("semanticReview"))

print("引文节点：%d，唯一引文串：%d" % (len(quotes), len({q[1]["quote"] for q in quotes})))
print("worldSettings：rule=%d place=%d item=%d" % (
    sum(1 for w in cand.get("worldSettings", []) if w["kind"] == "rule"),
    sum(1 for w in cand.get("worldSettings", []) if w["kind"] == "place"),
    sum(1 for w in cand.get("worldSettings", []) if w["kind"] == "item")))
print("tasks=%d causeEdges=%d rejectedEdges=%d states=%d knowledgeGaps=%d foreshadows=%d themeReadings=%d unknowns=%d selfCritique=%d" % (
    len(cand.get("tasks", [])), len(cand.get("causeEdges", [])), len(cand.get("rejectedEdges", [])),
    len(cand.get("states", [])), len(cand.get("knowledgeGaps", [])), len(cand.get("foreshadows", [])),
    len(cand.get("themeReadings", [])), len(cand.get("unknowns", [])), len(cand.get("selfCritique", []))))
if problems:
    for p in problems:
        print("[FAIL]", p)
    print("总计 %d 个问题" % len(problems))
    sys.exit(1)
print("ALL CHECKS PASS")
