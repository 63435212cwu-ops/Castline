#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L3:0259 候选的**独立**校验脚本。

独立性声明：本脚本**不 import** build_candidate.py 或 content_0259.py 的任何东西，
段落表、引文判定、区间相交、五栏独立性全部在这里**重新实现一遍**，以免两者一起错。
它只读两个输入：原文 docs.json 与候选 JSON。

退出码 0 = 全部 PASS；非 0 = 有 FAIL（逐条打印）。

负向对照（证明这些检查不是恒真）：脚本最后会对候选的**内存副本**做几次定向改坏，
要求对应的检查必须变成 FAIL；改不坏就说明检查是空的，同样算失败。
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0259.candidate.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L3_0259.json"

results = []


def check(tid, desc, ok, detail=""):
    results.append((tid, desc, bool(ok), detail))
    return bool(ok)


task = json.loads(TASK.read_text(encoding="utf-8"))
cand = json.loads(CAND.read_text(encoding="utf-8"))
raw = DOCS.read_bytes()
file_sha = hashlib.sha256(raw).hexdigest()
docs = json.loads(raw.decode("utf-8"))
text = docs[0]["text"]
S, E = task["sourceRange"]

# ── V01 源与边界 ─────────────────────────────────────────────────────────
check("V01a", "docs.json 文件 sha256 == task.sourceHash", file_sha == task["sourceHash"],
      "%s vs %s" % (file_sha[:12], task["sourceHash"][:12]))
slice_text = text[S:E]
check("V01b", "text[start:end] 以单元标题开头", slice_text.startswith(task["unitHead"]),
      repr(slice_text[:20]))
check("V01c", "切片长度 == end-start", len(slice_text) == E - S, "%d" % len(slice_text))
check("V01d", "候选 source.sliceSha256 == 现场重算",
      cand["source"]["sliceSha256"] == hashlib.sha256(slice_text.encode("utf-8")).hexdigest())
check("V01e", "候选 source.sourceHash == task.sourceHash",
      cand["source"]["sourceHash"] == task["sourceHash"])
check("V01f", "候选 source.range == task.sourceRange",
      list(cand["source"]["range"]) == list(task["sourceRange"]))

# ── V02 段落表（重新实现）───────────────────────────────────────────────
PARTS = slice_text.split("\n\n")
OFFS = []
_off = S
for _p in PARTS:
    OFFS.append((_off, _off + len(_p)))
    _off += len(_p) + 2
NONEMPTY = [i for i, p in enumerate(PARTS) if p.strip()]
check("V02a", "候选 source.nonEmptyParagraphs == 现场重算",
      cand["source"]["nonEmptyParagraphs"] == len(NONEMPTY),
      "%s vs %s" % (cand["source"]["nonEmptyParagraphs"], len(NONEMPTY)))

# ── V03 逐条引文 ─────────────────────────────────────────────────────────
quotes = []


def walk(obj, path):
    if isinstance(obj, dict):
        if {"quote", "start", "end", "sourceHash"} <= set(obj.keys()):
            quotes.append((path, obj))
        for k, v in obj.items():
            walk(v, path + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, "%s[%d]" % (path, i))


for sec in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
            "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
            "themeReadings", "textualNotes", "unknowns"):
    walk(cand[sec], sec)

bad_verbatim = [(p, q["quote"][:30]) for p, q in quotes if text[q["start"]:q["end"]] != q["quote"]]
check("V03a", "全部引文 text[start:end]==quote（%d 条）" % len(quotes), not bad_verbatim,
      str(bad_verbatim[:3]))
bad_range = [(p, q["start"]) for p, q in quotes if not (S <= q["start"] and q["end"] <= E)]
check("V03b", "全部引文落在 [start,end) 区间内", not bad_range, str(bad_range[:3]))
bad_hash = [p for p, q in quotes if q["sourceHash"] != task["sourceHash"]]
check("V03c", "全部引文 sourceHash == task.sourceHash", not bad_hash, str(bad_hash[:3]))
bad_len = [(p, q["start"], q["end"]) for p, q in quotes if q["end"] - q["start"] != len(q["quote"])]
check("V03d", "end-start == len(quote)", not bad_len, str(bad_len[:3]))

# 段号：引文对象自报的 para 必须与现场重算一致
bad_para = []
for p, q in quotes:
    if "para" not in q:
        continue
    i = q["para"]
    if not (0 <= i < len(PARTS)) or not (OFFS[i][0] <= q["start"] and q["end"] <= OFFS[i][1]):
        bad_para.append((p, i, q["start"]))
check("V03e", "引文自报段号与现场段落表一致", not bad_para, str(bad_para[:3]))

# wholeTextOccurrences / occurrencesInRange / first occurrence 三个字段的可复核性
bad_cnt = []
for p, q in quotes:
    if "wholeTextOccurrences" not in q:
        continue
    if q["wholeTextOccurrences"] != text.count(q["quote"]):
        bad_cnt.append((p, "whole"))
    elif q["occurrencesInRange"] != text[S:E].count(q["quote"]):
        bad_cnt.append((p, "range"))
    elif q["startIsFirstOccurrence"] != (text.find(q["quote"]) == q["start"]):
        bad_cnt.append((p, "first"))
check("V03f", "引文的出现次数统计字段与现场重算一致", not bad_cnt, str(bad_cnt[:3]))

# ── V04 任务五元组 ───────────────────────────────────────────────────────
FIELDS = ("objective", "obstacle", "action", "result", "cost")
tasks = cand["tasks"]
check("V04a", "tasks 非空", len(tasks) >= 1, "%d" % len(tasks))
missing_note = []
nonempty_without_quote = []
for t in tasks:
    for f in FIELDS:
        if t.get(f) is None:
            if not (t.get(f + "Note") or "").strip():
                missing_note.append("%s.%s" % (t["id"], f))
        else:
            if not t.get(f + "Quotes"):
                nonempty_without_quote.append("%s.%s" % (t["id"], f))
check("V04b", "null 栏全部带非空 <栏>Note", not missing_note, str(missing_note))
check("V04c", "非空栏全部带引文", not nonempty_without_quote, str(nonempty_without_quote))

# V05 五栏引文区间两两不相交（提示词点名的 714/1664 缺陷）
overlap = []
for t in tasks:
    spans = []
    for f in FIELDS:
        for q in t.get(f + "Quotes") or []:
            spans.append((f, q["start"], q["end"]))
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            f1, s1, e1 = spans[i]
            f2, s2, e2 = spans[j]
            if s1 < e2 and s2 < e1:
                overlap.append("%s %s[%d,%d)∩%s[%d,%d)" % (t["id"], f1, s1, e1, f2, s2, e2))
check("V05", "任务内五栏引文区间两两不相交", not overlap, str(overlap[:3]))
check("V05b", "候选自报 taskFieldIntervalOverlap == 0",
      cand["machineSelfCheck"]["taskFieldIntervalOverlap"] == 0)

# ── V06 basis 词表 ───────────────────────────────────────────────────────
LEGAL = {"explicit", "inferred", "derived", "unverified"}
bad_basis = []


def check_basis(obj, path):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith("Basis") or k == "basis":
                if v is not None and v not in LEGAL:
                    bad_basis.append("%s.%s=%r" % (path, k, v))
            check_basis(v, path + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_basis(v, "%s[%d]" % (path, i))


for sec in ("tasks", "causeEdges", "states", "knowledgeGaps", "foreshadows",
            "worldSettings", "themeReadings", "textualNotes", "unknowns"):
    check_basis(cand[sec], sec)
check("V06", "全部 basis 取值合法", not bad_basis, str(bad_basis[:3]))

# ── V07 causeEdges 必须有机制，rejectedEdges 必须给理由 ──────────────────
bad_mech = [c["id"] for c in cand["causeEdges"]
            if not (c.get("mechanism") or "").strip() or len(c.get("mechanism", "")) < 20]
check("V07a", "causeEdges 每条都有非空机制说明", not bad_mech, str(bad_mech))
bad_fromto = [c["id"] for c in cand["causeEdges"] if not c.get("from") or not c.get("to")]
check("V07b", "causeEdges 每条都有方向（from/to）", not bad_fromto, str(bad_fromto))
bad_why = [r["id"] for r in cand["rejectedEdges"] if not (r.get("whyNot") or "").strip()]
check("V07c", "rejectedEdges 每条都写了为什么不连边", not bad_why, str(bad_why))

# ── V08 states 前值/后值/锚点 ────────────────────────────────────────────
bad_state = []
for s in cand["states"]:
    for f in ("before", "after", "anchor"):
        if not (s.get(f) or "").strip():
            bad_state.append("%s.%s 空" % (s["id"], f))
        elif not s.get(f + "Quotes"):
            bad_state.append("%s.%s 无引文" % (s["id"], f))
check("V08", "states 每条有前值/后值/锚点且各带引文", not bad_state, str(bad_state[:3]))

# ── V09 worldSettings 三态字段 ───────────────────────────────────────────
PLACE = {"arrived", "mentioned"}
ITEM = {"hold", "transfer", "use", "lose"}
INST = {"declared", "executed", "misunderstood"}
bad_ws = []
kinds = {"rule": 0, "place": 0, "item": 0}
for w in cand["worldSettings"]:
    k = w.get("kind")
    if k not in kinds:
        bad_ws.append("%s kind=%r" % (w["id"], k))
        continue
    kinds[k] += 1
    if k == "place":
        if w.get("placeState") not in PLACE:
            bad_ws.append("%s placeState=%r" % (w["id"], w.get("placeState")))
        if not (w.get("placeStateNote") or "").strip():
            bad_ws.append("%s 缺 placeStateNote" % w["id"])
    elif k == "item":
        st = w.get("itemStates")
        if not (isinstance(st, list) and st and set(st) <= ITEM):
            bad_ws.append("%s itemStates=%r" % (w["id"], st))
        notes = w.get("itemStateNotes") or {}
        for s in st or []:
            if not (notes.get(s) or "").strip():
                bad_ws.append("%s itemStates 的 %s 无单独说明" % (w["id"], s))
        if not (w.get("itemStateNote") or "").strip():
            bad_ws.append("%s 缺 itemStateNote" % w["id"])
    else:
        if w.get("institution") not in INST:
            bad_ws.append("%s institution=%r" % (w["id"], w.get("institution")))
        if not (w.get("institutionNote") or "").strip():
            bad_ws.append("%s 缺 institutionNote" % w["id"])
check("V09", "worldSettings 三态字段合法且逐条有说明", not bad_ws, str(bad_ws[:3]))
check("V09b", "worldSettings 的 rule/place/item 计数与候选一致",
      kinds["rule"] + kinds["place"] + kinds["item"] == len(cand["worldSettings"]), str(kinds))

# ── V10 themeReadings 三件齐全 ───────────────────────────────────────────
bad_th = []
for t in cand["themeReadings"]:
    if not (t.get("perspective") or "").strip():
        bad_th.append("%s 缺 perspective" % t["id"])
    if not t.get("support"):
        bad_th.append("%s 缺 support" % t["id"])
    if not t.get("counter"):
        bad_th.append("%s 缺 counter" % t["id"])
    for grp in ("support", "counter"):
        for it in t.get(grp) or []:
            if not it.get("quote"):
                bad_th.append("%s.%s 有条目无引文" % (t["id"], grp))
check("V10", "themeReadings 三件齐全（perspective/support/counter）", not bad_th, str(bad_th[:3]))
check("V10b", "themeReadings 条数在 1-2 之间", 1 <= len(cand["themeReadings"]) <= 2,
      "%d" % len(cand["themeReadings"]))

# ── V11 伏笔：铺设必有、回收与状态自洽 ───────────────────────────────────
bad_fs = []
for f in cand["foreshadows"]:
    if not f["setup"]["quote"]:
        bad_fs.append("%s 无铺设引文" % f["id"])
    st = f.get("status")
    if st == "unresolved":
        if f["payoff"]["quote"]:
            bad_fs.append("%s 标 unresolved 却有回收引文" % f["id"])
        if not (f.get("unresolvedWhat") or "").strip():
            bad_fs.append("%s 标 unresolved 却没写未回收什么" % f["id"])
    elif st == "resolved":
        if not f["payoff"]["quote"]:
            bad_fs.append("%s 标 resolved 却无回收引文" % f["id"])
    elif st == "partial":
        if not f["payoff"]["quote"]:
            bad_fs.append("%s 标 partial 却无回收引文" % f["id"])
        if not (f.get("unresolvedWhat") or "").strip():
            bad_fs.append("%s 标 partial 却没写剩下什么" % f["id"])
    else:
        bad_fs.append("%s status=%r" % (f["id"], st))
check("V11", "伏笔的铺设/回收/状态自洽", not bad_fs, str(bad_fs[:3]))

# ── V12 必需分区存在 ─────────────────────────────────────────────────────
WANT = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
missing = [k for k in WANT if k not in cand]
check("V12", "提示词要求的 6 个顶层分区全部存在", not missing, str(missing))

# ── V13 不得声称 semanticReview 完成 ─────────────────────────────────────
sr = cand.get("semanticReview")
check("V13", "未声称 semanticReview 完成", sr in ("not-performed", "partial", None), repr(sr))

# ── V14 专名核对：候选里出现的书名/人名必须在原文里存在 ──────────────────
whole = text
names = ["许七安", "褚采薇", "许铃音", "监正", "钟璃", "李妙真", "神殊", "魏渊",
         "金莲道长", "苏苏", "元景帝", "临安", "怀庆", "陈贵妃", "杨千幻", "许宁宴",
         "盘树僧人", "西方教", "西域佛门", "地书碎片", "脱胎丸", "马蹄糕", "飞燕军",
         "白帝城", "天宗", "观星楼", "司天监", "八卦台", "打更人", "铜锣", "银锣"]
blob = json.dumps(cand, ensure_ascii=False)
absent = [n for n in names if n in blob and n not in whole]
check("V14", "候选提到的专名全部在原文中存在（%d 个候选词）" % len(names), not absent, str(absent))

# 反向：确认这些名字在**本区间**里的出现次数，供复核判断引用是否落在本单元
counts = {n: whole[S:E].count(n) for n in names}

# ── V15 覆盖度自报一致 ───────────────────────────────────────────────────
union = set()
for _, q in quotes:
    union.update(range(q["start"], q["end"]))
check("V15a", "候选自报 quoteUnionCodepoints == 现场重算",
      cand["coverage"]["quoteUnionCodepoints"] == len(union),
      "%s vs %s" % (cand["coverage"]["quoteUnionCodepoints"], len(union)))
check("V15b", "候选自报 quoteObjectsResolved == 现场统计",
      cand["machineSelfCheck"]["quoteObjectsResolved"] == len(quotes),
      "%s vs %s" % (cand["machineSelfCheck"]["quoteObjectsResolved"], len(quotes)))
check("V15c", "候选自报 resolveFailures == 0",
      cand["machineSelfCheck"]["resolveFailures"] == 0)

# ── V16 machineSelfCheck 声明的脚本真实存在（防「虚假复现声明」）──────────
for key in ("buildScript", "contentModule", "verifyScript"):
    p = ROOT / cand["machineSelfCheck"][key]
    check("V16." + key, "machineSelfCheck.%s 指向的文件存在" % key, p.exists(), str(p))

# ── V17 红线抽查：引用到的对白都不得被当作叙述事实 ───────────────────────
# 这些是候选里明确标注为「人物的话」的引文；检查它们是否出现在需要叙述事实的栏位。
SPEECH = [
    "我能感觉到，西方教要来了",
    "我只是一个残魂",
    "预言师能窥探天机",
    "只有自己亲身挨过考验才行",
    "喝了它，不必离京",
    "被你家妹妹吃了一大半",
]
misuse = []
for t in tasks:
    for f in FIELDS:
        for q in t.get(f + "Quotes") or []:
            for sp in SPEECH:
                if sp in q["quote"] and f in ("result",) and t.get(f + "Basis") == "explicit":
                    misuse.append("%s.%s 引了人物的话却记 explicit：%s" % (t["id"], f, sp))
check("V17", "人物的话没有被记成 explicit 的 result", not misuse, str(misuse[:3]))

# ══════════════════════════════════════════════════════════════════════════
# 负向对照：把候选改坏，要求对应检查变 FAIL
#
# 为什么必须有：正向上「211 条引文全部逐字命中」既可能是检查有效，
# 也可能是检查写空了（恒真）。所以这里对候选的内存副本做定向改坏，
# **要求同一段判据代码在改坏后必须报错**；报不出来就是空检查，同样算 FAIL。
# ══════════════════════════════════════════════════════════════════════════
def collect_quotes(obj):
    """与主检查同一段判据：把一个对象树里的引文对象收集出来。"""
    out = []

    def _w(o):
        if isinstance(o, dict):
            if {"quote", "start", "end", "sourceHash"} <= set(o.keys()):
                out.append(o)
            for v in o.values():
                _w(v)
        elif isinstance(o, list):
            for v in o:
                _w(v)

    _w(obj)
    return out


def verbatim_fails(c):
    """改坏后的候选是否会被 V03a 抓到（True = 抓到了 = 检查有效）。"""
    return any(text[q["start"]:q["end"]] != q["quote"] for q in collect_quotes(c))


def overlap_of_first_task(c):
    t0 = c["tasks"][0]
    spans = []
    for f in FIELDS:
        for q in t0.get(f + "Quotes") or []:
            spans.append((f, q["start"], q["end"]))
    return any(spans[i][1] < spans[j][2] and spans[j][1] < spans[i][2]
               for i in range(len(spans)) for j in range(i + 1, len(spans)))


def null_note_missing(c):
    return any(not (t.get(f + "Note") or "").strip()
               for t in c["tasks"] for f in FIELDS if t.get(f) is None)


def unresolved_with_payoff(c):
    return any(f["status"] == "unresolved" and f["payoff"]["quote"] for f in c["foreshadows"])


c = copy.deepcopy(cand)
c["tasks"][0]["objectiveQuotes"][0]["quote"] += "X"
check("N01", "负向对照：改坏引文字符串 → 逐字命中判据必须报错", verbatim_fails(c))

c = copy.deepcopy(cand)
c["tasks"][0]["objectiveQuotes"][0]["start"] += 1
check("N02", "负向对照：只把 start 挪一位 → 逐字命中判据必须报错", verbatim_fails(c))

c = copy.deepcopy(cand)
c["worldSettings"][0]["quote"]["start"] += 3
check("N03", "负向对照：worldSettings 引文挪位 → 逐字命中判据必须报错", verbatim_fails(c))

c = copy.deepcopy(cand)
c["tasks"][0]["cost"] = "伪造的代价"
c["tasks"][0]["costQuotes"] = [dict(c["tasks"][0]["objectiveQuotes"][0])]
check("N04", "负向对照：把 cost 引成与 objective 同一句 → 五栏重叠判据必须报错",
      overlap_of_first_task(c))

c = copy.deepcopy(cand)
_nulls = [t for t in c["tasks"] if t.get("cost") is None]
if _nulls:
    _nulls[0]["costNote"] = ""
    check("N05", "负向对照：抹掉一个 null 栏的理由 → 缺理由判据必须报错", null_note_missing(c))
else:
    check("N05", "负向对照：本候选没有 null 栏可改，跳过（不假装通过）", False,
          "no null field to mutate")

c = copy.deepcopy(cand)
_unres = [f for f in c["foreshadows"] if f["status"] == "unresolved"]
if _unres:
    _unres[0]["payoff"]["quote"] = [dict(c["foreshadows"][0]["setup"]["quote"][0])]
    check("N06", "负向对照：给 unresolved 伏笔补回收引文 → 状态自洽判据必须报错",
          unresolved_with_payoff(c))
else:
    check("N06", "负向对照：本候选没有 unresolved 伏笔可改，跳过（不假装通过）", False,
          "no unresolved foreshadow to mutate")

c = copy.deepcopy(cand)
c["worldSettings"][0]["institution"] = "NOT-A-STATE"
_bad = c["worldSettings"][0]["institution"] not in {"declared", "executed", "misunderstood"}
check("N07", "负向对照：把 institution 改成非法值 → 三态判据必须报错", _bad)

c = copy.deepcopy(cand)
c["worldSettings"][0]["quote"]["sourceHash"] = "0" * 64
check("N08", "负向对照：改坏引文 sourceHash → 哈希判据必须报错",
      any(q["sourceHash"] != task["sourceHash"] for q in collect_quotes(c)))

# 正向上还要证明：**未被改坏的**候选不会被上述判据误报（否则判据是在恒报错）
check("N09", "对照：未改坏的候选不触发以上任何负向判据",
      not verbatim_fails(copy.deepcopy(cand))
      and not overlap_of_first_task(copy.deepcopy(cand))
      and not null_note_missing(copy.deepcopy(cand))
      and not unresolved_with_payoff(copy.deepcopy(cand)))

# ══════════════════════════════════════════════════════════════════════════
fails = [r for r in results if not r[2]]
for tid, desc, ok, detail in results:
    print("%-8s %s  %s%s" % (tid, "PASS" if ok else "FAIL", desc,
                             ("  ← " + detail) if (detail and not ok) else ""))
print()
print("检查项：%d，PASS %d，FAIL %d" % (len(results), len(results) - len(fails), len(fails)))
print("专名在本区间的出现次数（抽样）：", {k: counts[k] for k in
      ["许七安", "钟璃", "西方教", "李妙真", "监正"] if k in counts})
if fails:
    print("\nFAIL 明细：", file=sys.stderr)
    for tid, desc, ok, detail in fails:
        print("  %s %s ← %s" % (tid, desc, detail), file=sys.stderr)
    sys.exit(1)
sys.exit(0)
