#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计：**从磁盘重新读候选**，不复用构建期的任何内存对象。

构建脚本的自检跑在「它自己刚装配好的对象」上；本脚本跑在**落盘的 JSON** 上，
并额外做构建脚本没做的反向检查：
  · 每条引文重新在 docs[0].text 里定位一次（不信任候选里的 start/end）
  · 名字可核性（地点/物件条目的引文里有没有该条目的名字）
  · 抄写一致性：候选里的 quote 必须能在原文 find 到（防手抄错字）
  · 同一任务五栏引文区间两两不重叠（按落盘内容重算）
  · null 栏带理由、不带引文
"""
import hashlib
import json
import sys

ROOT = "/Users/carmen/Desktop/星系"
CAND = ROOT + "/loop/state/out/read_dafeng_L3_0279.candidate.json"
DOCS = ROOT + "/data/cache/1063b17ca65ec1b76f30e460.docs.json"
EXPECT_SHA = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

problems = []
audit = {}

raw = open(DOCS, "rb").read()
docs_sha = hashlib.sha256(raw).hexdigest()
if docs_sha != EXPECT_SHA:
    problems.append("docs.json sha256 变了：%s" % docs_sha)
text = json.loads(raw.decode("utf-8"))[0]["text"]

cand = json.load(open(CAND, encoding="utf-8"))
S, E = cand["source"]["range"]
slice_text = text[S:E]
if slice_text.split("\n", 1)[0].strip() != "第五十章 诗":
    problems.append("切片首行不是标题")
if cand["source"]["sourceHash"] != EXPECT_SHA:
    problems.append("候选声明的 sourceHash 与文件不符")
if hashlib.sha256(slice_text.encode("utf-8")).hexdigest() != cand["source"]["sliceSha256"]:
    problems.append("sliceSha256 不符")

COLUMNS = ("objective", "obstacle", "action", "result", "cost")


def walk(node, path="$"):
    if isinstance(node, dict):
        if {"quote", "start", "end"} <= set(node):
            yield path, node
        for k, v in node.items():
            yield from walk(v, path + "." + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, "%s[%d]" % (path, i))


n_checked = 0
mismatch = []
out_of_range = []
notfound = []
for path, qo in walk(cand):
    n_checked += 1
    q, a, b = qo["quote"], qo["start"], qo["end"]
    # 不信任 start/end：重新定位
    if text[a:b] != q:
        mismatch.append({"path": path, "start": a, "end": b, "quote": q[:40]})
    if not (S <= a < E and S < b <= E):
        out_of_range.append({"path": path, "start": a, "end": b})
    if text.find(q) < 0:
        notfound.append({"path": path, "quote": q[:40]})
    if qo.get("sourceHash") != EXPECT_SHA:
        problems.append("sourceHash 不符 @%s" % path)
if mismatch:
    problems.append("text[start:end]!=quote 共 %d 处" % len(mismatch))
if out_of_range:
    problems.append("引文越界 %d 处" % len(out_of_range))
if notfound:
    problems.append("引文在全文 find 不到 %d 处" % len(notfound))

# 同一任务五栏区间不重叠
overlaps = []
shared = []
for t in cand["tasks"]:
    spans = []
    for col in COLUMNS:
        for qo in t.get(col + "Quotes") or []:
            spans.append((qo["start"], qo["end"], col, qo["quote"]))
    spans.sort()
    for i in range(len(spans) - 1):
        (a1, b1, c1, _), (a2, b2, c2, _) = spans[i], spans[i + 1]
        if b1 > a2:
            overlaps.append({"task": t["id"], "cols": [c1, c2], "a": [a1, b1], "b": [a2, b2]})
    seen = {}
    for _a, _b, col, q in spans:
        if q in seen and seen[q] != col:
            shared.append({"task": t["id"], "cols": [seen[q], col], "q": q[:30]})
        seen[q] = col
if overlaps:
    problems.append("栏间区间重叠 %d 处：%r" % (len(overlaps), overlaps[:3]))
if shared:
    problems.append("跨栏共用引文 %d 处：%r" % (len(shared), shared[:3]))

# null 栏
null_bad = []
for t in cand["tasks"]:
    for col in t["nullFields"]:
        note = t.get(col + "Note")
        qs = t.get(col + "Quotes") or []
        if not note or qs:
            null_bad.append({"task": t["id"], "col": col, "hasNote": bool(note), "nQuotes": len(qs)})
if null_bad:
    problems.append("null 栏不合规：%r" % null_bad)

# 名字可核性（反向检查：条目名必须在引文里出现）
NAME_TOKENS = {
    "德馨苑（怀庆处）": ["德馨苑"], "青州": ["青州"], "韶音苑（临安处）": ["韶音苑"],
    "清云山·云鹿书院": ["清云山", "云鹿书院"], "皇城·王府书房": ["王府", "书房"],
    "贡院": ["贡院"], "《霸道女君爱上我》": ["霸道女君爱上我"], "《情天大圣》": ["情天大圣"],
    "杏榜提名的书院学子名单": ["名单"], "《行路难》诗（写诗的宣纸）": ["行路难", "诗"],
}
name_rows = []
for w in cand["worldSettings"]:
    if w["kind"] == "rule":
        continue
    toks = NAME_TOKENS.get(w["name"], [])
    allq = [w["quote"]["quote"]] + [q["quote"] for q in w.get("extraQuotes") or []]
    hit = sorted({t for t in toks if any(t in q for q in allq)})
    name_rows.append({"id": w["id"], "name": w["name"], "hit": hit})
    if not hit:
        problems.append("%s(%s) 引文不含条目名" % (w["id"], w["name"]))

# 枚举合法性
for w in cand["worldSettings"]:
    if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        problems.append("%s placeState 非法" % w["id"])
    if w["kind"] == "item":
        st = w.get("itemStates") or []
        if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            problems.append("%s itemStates 非法" % w["id"])
    if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        problems.append("%s institution 非法" % w["id"])

# 主题三件
for th in cand["themeReadings"]:
    for k in ("perspective", "support", "counter"):
        if not th.get(k):
            problems.append("%s 缺 %s" % (th["id"], k))

# 伏笔
for f in cand["foreshadows"]:
    if not f.get("setupQuotes") or not f.get("payoffQuotes"):
        problems.append("%s 缺铺设/回收" % f["id"])
    if f.get("status") not in ("resolved", "unresolved"):
        problems.append("%s status 非法" % f["id"])

# 作者区域
leaks = [p for p, qo in walk(cand) if qo.get("inAuthorRegion")]

audit = {
    "auditedFile": "loop/state/out/read_dafeng_L3_0279.candidate.json",
    "candidateSha256": hashlib.sha256(open(CAND, "rb").read()).hexdigest(),
    "docsSha256": docs_sha,
    "quoteObjectsReverified": n_checked,
    "reverifyMode": "从磁盘读候选，逐条用 text[start:end]==quote 复核，并独立 text.find(quote) 定位一次",
    "mismatch": mismatch[:5], "outOfRange": out_of_range[:5], "notFound": notfound[:5],
    "columnOverlaps": overlaps[:5], "crossColumnShared": shared[:5],
    "nullViolations": null_bad,
    "worldSettingNameSupport": name_rows,
    "authorRegionLeaks": len(leaks),
    "counts": {
        "tasks": len(cand["tasks"]), "causeEdges": len(cand["causeEdges"]),
        "rejectedEdges": len(cand["rejectedEdges"]), "states": len(cand["states"]),
        "knowledgeGaps": len(cand["knowledgeGaps"]), "foreshadows": len(cand["foreshadows"]),
        "notForeshadows": len(cand["notForeshadows"]), "worldSettings": len(cand["worldSettings"]),
        "notWorldSettings": len(cand["notWorldSettings"]), "themeReadings": len(cand["themeReadings"]),
        "speechAsClueNotFact": len(cand["speechAsClueNotFact"]),
        "textualNotes": len(cand["textualNotes"]), "unknowns": len(cand["unknowns"]),
        "selfCritique": len(cand["selfCritique"]),
    },
    "problems": problems,
}
print(json.dumps(audit, ensure_ascii=False, indent=1))
print("\n[审计] 问题 %d 个" % len(problems), file=sys.stderr)
sys.exit(1 if problems else 0)
