#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L3:0231 的**独立核验**脚本。

与 build_candidate.py 分离的要点：
  · 只读磁盘上的成品 candidate.json，**不复用**构建期内存里的任何偏移；
  · 自己重新读 docs.json，重新算 sha256，重新 find 每一条 quote；
  · 额外做构建期没做的检查：越界专名探针、五栏区间重叠复算、
    null-Note 复算、分区形状复算、交叉引用悬空复算、覆盖率复算。
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DOCS = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
TASKF = os.path.join(ROOT, "loop", "state", "runs", "task-read_dafeng_L3_0231.json")
CAND = os.path.join(ROOT, "loop", "state", "out", "read_dafeng_L3_0231.candidate.json")
REPORT = os.path.join(HERE, "verify_report.json")

TASK = json.load(open(TASKF, encoding="utf-8"))
START, END = TASK["sourceRange"]
EXPECT = TASK["sourceHash"]

RAW = open(DOCS, "rb").read()
FILE_SHA = hashlib.sha256(RAW).hexdigest()
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[START:END]

CAND_DOC = json.load(open(CAND, encoding="utf-8"))

problems = []


def note(msg):
    problems.append(msg)


def walk_quote_objects(node, path="$"):
    """产出 (path, quoteObj) —— 只认同时带 quote/start/end 的 dict。"""
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
            yield path, node
        for k, v in node.items():
            yield from walk_quote_objects(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quote_objects(v, "%s[%d]" % (path, i))


# ---- 1. 源与切片 -----------------------------------------------------------
report = {
    "docsSha256": FILE_SHA,
    "docsSha256MatchesTask": FILE_SHA == EXPECT,
    "sliceCodepoints": len(SLICE),
    "sliceSha256": hashlib.sha256(SLICE.encode("utf-8")).hexdigest(),
    "candidateSliceSha256": CAND_DOC.get("source", {}).get("sliceSha256"),
    "candidateSourceHash": CAND_DOC.get("source", {}).get("sourceHash"),
    # 把被核验的成品哈希写进报告，让「报告 ↔ 成品」的对应关系可独立复核
    "verifiedCandidatePath": os.path.relpath(CAND, ROOT),
    "verifiedCandidateSha256": hashlib.sha256(open(CAND, "rb").read()).hexdigest(),
}
if not report["docsSha256MatchesTask"]:
    note("docs.json 哈希与 task.sourceHash 不一致")
if not SLICE.startswith(TASK["unitHead"]):
    note("切片不以 unitHead 开头")
if report["sliceSha256"] != report["candidateSliceSha256"]:
    note("候选声明的 sliceSha256 与实算不符")
if report["candidateSourceHash"] != EXPECT:
    note("候选声明的 sourceHash 与 task 不符")

# ---- 2. 逐条引文复算 -------------------------------------------------------
quotes = list(walk_quote_objects(CAND_DOC))
bad = []
for path, q in quotes:
    s, e, txt = q.get("start"), q.get("end"), q["quote"]
    if not isinstance(s, int) or not isinstance(e, int):
        bad.append({"path": path, "why": "start/end 非整数"})
        continue
    if TEXT[s:e] != txt:
        bad.append({"path": path, "why": "text[start:end] != quote"})
        continue
    if TEXT.find(txt, START, END) != s:
        bad.append({"path": path, "why": "find(quote, START, END) != start"})
        continue
    if not (START <= s and e <= END):
        bad.append({"path": path, "why": "越出区间"})
        continue
    if q.get("sourceHash") != EXPECT:
        bad.append({"path": path, "why": "sourceHash 不符"})
        continue
report["quoteObjects"] = len(quotes)
report["quotesFullyVerified"] = len(quotes) - len(bad)
report["quoteObjectsWithSourceHash"] = sum(
    1 for _, q in quotes if q.get("sourceHash") == EXPECT)
report["unlocatedQuoteObjects"] = len(bad)
report["badQuotes"] = bad[:20]
for b in bad[:5]:
    note("引文核验失败：%s %s" % (b["path"], b["why"]))

# ---- 3. 越界专名探针（构建期没有的独立探针）--------------------------------
NAMES = ["宋廷风", "朱广孝", "李玉春", "杨砚", "姜律中", "梦巫", "李妙真",
         "地宗", "天地会", "春祭日", "太平刀", "白帝城", "邢台", "瓮城",
         "驿站", "梁有平", "宋长辅", "守门人", "靖山", "楚元缜", "赵守",
         "玄诚道长", "张奉", "刘伯温", "云鹿书院", "打更人衙门", "元景帝"]
probe = {"probed": len(NAMES), "absentFromSliceEnforced": 0,
         "presentInSliceNotEnforced": [], "leaks": []}
for n in NAMES:
    if SLICE.count(n) == 0:
        probe["absentFromSliceEnforced"] += 1
    else:
        probe["presentInSliceNotEnforced"].append(n)
for path, q in quotes:
    for n in NAMES:
        if SLICE.count(n) == 0 and n in q["quote"]:
            probe["leaks"].append({"path": path, "name": n})
report["outOfRangeNameProbe"] = probe
if probe["leaks"]:
    note("引文里出现区间外专名：%s" % probe["leaks"][:5])

# ---- 4. 五栏碰撞 / 区间重叠复算 --------------------------------------------
FIELD = ("objective", "obstacle", "action", "result", "cost")
collisions, overlaps = [], []
for t in CAND_DOC.get("tasks", []):
    seen = {}
    for f in FIELD:
        for q in t.get(f + "Quotes") or []:
            s = q["quote"]
            if s in seen:
                collisions.append({"task": t["id"], "quote": s[:30],
                                   "fields": [seen[s], f]})
            seen[s] = f
    for i, fa in enumerate(FIELD):
        for fb in FIELD[i + 1:]:
            for a in t.get(fa + "Quotes") or []:
                for b in t.get(fb + "Quotes") or []:
                    if a["start"] < b["end"] and b["start"] < a["end"]:
                        overlaps.append({"task": t["id"], "fields": [fa, fb],
                                         "a": [a["start"], a["end"]],
                                         "b": [b["start"], b["end"]]})
report["taskFieldQuoteCollision"] = collisions
report["taskFieldIntervalOverlap"] = overlaps
if collisions:
    note("同任务五栏共用引文：%d 处" % len(collisions))
if overlaps:
    note("同任务五栏引用区间重叠：%d 处" % len(overlaps))

# ---- 5. null 必须有 Note ---------------------------------------------------
nulls, null_no_note = [], []
for t in CAND_DOC.get("tasks", []):
    for f in FIELD:
        if t.get(f) is None:
            nulls.append("%s.%s" % (t["id"], f))
            if not t.get(f + "Note"):
                null_no_note.append("%s.%s" % (t["id"], f))
report["nullFields"] = nulls
report["nullWithoutNote"] = null_no_note
if null_no_note:
    note("值为 null 但没有 <栏位>Note：%s" % null_no_note)

# ---- 6. 分区存在与形状 -----------------------------------------------------
REQ = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings",
       "themeReadings"]
report["requiredSections"] = REQ
report["missingSections"] = [k for k in REQ if k not in CAND_DOC]
if report["missingSections"]:
    note("缺分区：%s" % report["missingSections"])

shape = []
kinds = {}
for w in CAND_DOC.get("worldSettings", []):
    k = w.get("kind")
    kinds[k] = kinds.get(k, 0) + 1
    if k == "rule":
        if w.get("institution") not in ("declared", "executed", "misunderstood"):
            shape.append("%s institution=%r" % (w.get("id"), w.get("institution")))
        if not w.get("explain"):
            shape.append("%s 缺 explain" % w.get("id"))
    elif k == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            shape.append("%s placeState=%r" % (w.get("id"), w.get("placeState")))
        if not w.get("explain"):
            shape.append("%s 缺 explain" % w.get("id"))
    elif k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(
                x not in ("hold", "transfer", "use", "lose") for x in st):
            shape.append("%s itemStates=%r" % (w.get("id"), st))
        if not w.get("explain"):
            shape.append("%s 缺 explain" % w.get("id"))
    else:
        shape.append("%s kind=%r" % (w.get("id"), k))
report["worldSettingsKinds"] = kinds
report["worldSettingsShapeProblems"] = shape
if shape:
    note("worldSettings 形状问题：%s" % shape[:5])

theme_prob = []
for t in CAND_DOC.get("themeReadings", []):
    if not t.get("perspective"):
        theme_prob.append("%s 缺 perspective" % t.get("id"))
    if not t.get("support"):
        theme_prob.append("%s 缺 support" % t.get("id"))
    if not t.get("counter"):
        theme_prob.append("%s 缺 counter" % t.get("id"))
report["themeReadings"] = len(CAND_DOC.get("themeReadings", []))
report["themeReadingProblems"] = theme_prob
if theme_prob:
    note("themeReadings 问题：%s" % theme_prob)
if len(CAND_DOC.get("themeReadings", [])) > 2:
    note("themeReadings 超过 2 条")

fh_prob = []
for f in CAND_DOC.get("foreshadows", []):
    if f.get("status") in ("unresolved", "partial") and not f.get("unresolvedWhat"):
        fh_prob.append("%s status=%s 缺 unresolvedWhat" % (f.get("id"), f.get("status")))
    if f.get("status") == "resolved-in-range" and not f.get("payoff"):
        fh_prob.append("%s 判 resolved 但缺 payoff" % f.get("id"))
report["foreshadows"] = len(CAND_DOC.get("foreshadows", []))
report["foreshadowProblems"] = fh_prob
if fh_prob:
    note("foreshadows 问题：%s" % fh_prob)

# ---- 7. 悬空交叉引用复算 ---------------------------------------------------
ids = set()
for sec in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
            "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
            "themeReadings", "textualNotes", "unknowns", "selfCritique",
            "speechAsClueNotFact"):
    for item in CAND_DOC.get(sec) or []:
        if isinstance(item, dict) and item.get("id"):
            ids.add(item["id"])
dangling = []
for sec in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
            "foreshadows", "worldSettings"):
    for item in CAND_DOC.get(sec) or []:
        blob = json.dumps(item, ensure_ascii=False)
        for ref in re.findall(r"\b([A-Z]{1,3}\d{2})\b", blob):
            if ref not in ids and ref != item.get("id"):
                dangling.append({"in": item.get("id"), "ref": ref})
report["danglingCrossReferences"] = dangling
if dangling:
    note("悬空交叉引用：%s" % dangling[:5])

# ---- 8. 覆盖率复算 ---------------------------------------------------------
intervals = sorted((q["start"], q["end"]) for _, q in quotes)
merged = []
for s, e in intervals:
    if merged and s <= merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], e)
    else:
        merged.append([s, e])
union = sum(e - s for s, e in merged)
nonspace = sum(1 for ch in SLICE if not ch.isspace())
report["summedQuoteCodepoints"] = union
report["nonSpaceCodepoints"] = nonspace
report["quoteUnionRatioOfNonSpace"] = round(union / nonspace, 4) if nonspace else None
report["candidateCoverage"] = CAND_DOC.get("coverage", {}).get(
    "quoteUnionCodepoints")
if CAND_DOC.get("coverage", {}).get("quoteUnionCodepoints") != union:
    note("候选 coverage.quoteUnionCodepoints 与独立复算不符")

# ---- 9. 语义越权关键词探针 -------------------------------------------------
banned = []
for path, q in quotes:
    txt = q["quote"]
    # 只有这些「结论性」措辞出现在引文里才可疑（引文本身来自原文，故只在
    # 候选自己的叙述性字段里查）
for sec in ("tasks", "causeEdges", "states", "knowledgeGaps", "foreshadows",
            "worldSettings", "themeReadings"):
    blob = json.dumps(CAND_DOC.get(sec), ensure_ascii=False)
    for kw in ("semanticReview 完成", "已验证语义", "语义已核验"):
        if kw in blob:
            banned.append({"section": sec, "kw": kw})
report["semanticOverclaimProbe"] = banned
if banned:
    note("出现语义完成声称：%s" % banned)

report["problems"] = problems
report["verdict"] = "pass" if not problems else "fail"
report["crossSectionQuoteReuse"] = CAND_DOC.get("machineSelfCheck", {}).get(
    "crossSectionQuoteReuse")

with open(REPORT, "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

print(json.dumps({k: v for k, v in report.items() if k != "badQuotes"},
                 ensure_ascii=False, indent=1))
sys.exit(0 if report["verdict"] == "pass" else 1)
