#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三十八章 五号的传书 —— 构建 loop/state/out/read_dafeng_L3_0267.candidate.json。

设计（每条都对应提示词/READER.md 的一条硬性要求）：

1. **偏移不手填**。内容模块只给 (段号, 逐字子串)。本脚本在 docs[0].text 上
   `.find(sub, para_start, para_end)` 求出 (start,end)，并现场断言
   `text[start:end] == sub`。find 不到 → 抛错退出（rc=1），绝不静默跳过。
2. **同段多处出现要歧义检测**。若同一子串在切片里出现多次，记录
   wholeTextOccurrences / occurrencesInRange / startIsFirstOccurrence / firstOccurrenceAt，
   并汇总进 coverage.ambiguousQuotes 供复核看哪些引文不是唯一命中。
3. **五栏区间独立**。构建完对每条任务的 objective/obstacle/action/result/cost
   引文区间两两求交，任何非空交集 → rc=1（提示词点名的 714/1664 缺陷）。
4. **null 必须带 Note**。缺栏写 null，同名 <栏>Note 必须非空，否则 rc=1。
5. **分区键必须存在**（required_sections 机器核对），即使为空数组。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BUILD_DIR))
import content_0267 as C  # noqa: E402

ROOT = BUILD_DIR.parents[3]          # …/星系
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
GRAPH = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"
OUT = ROOT / "loop/state/out/read_dafeng_L3_0267.candidate.json"

S, E = C.SLICE_START, C.SLICE_END
HASH = C.SOURCE_HASH

PROBLEMS: list[str] = []


def fail(msg: str) -> None:
    PROBLEMS.append(msg)


# ---------------------------------------------------------------------------
# 装载原文
# ---------------------------------------------------------------------------
def load_text() -> tuple[str, str]:
    raw = DOCS.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != HASH:
        sys.exit("源文件哈希不符：期望 %s，实际 %s" % (HASH, actual))
    docs = json.loads(raw.decode("utf-8"))
    text = docs[0]["text"]
    if text[S:E][:len("第三十八章 五号的传书")] != "第三十八章 五号的传书":
        sys.exit("切片不以单元标题开头，偏移口径错：%r" % (text[S:S + 30],))
    return text, actual


TEXT, _ = load_text()
SLICE = TEXT[S:E]

# 段落表：非空段，para 号 = 非空段序号（0 = 标题行）
PARA_RANGES: list[tuple[int, int]] = []
_off = S
for _ln in SLICE.split("\n"):
    _en = _off + len(_ln)
    if _ln.strip():
        PARA_RANGES.append((_off, _en))
    _off = _en + 1


def para_span(idx: int) -> tuple[int, int]:
    if not (0 <= idx < len(PARA_RANGES)):
        fail("段号越界：P%d（本区间非空段 0..%d）" % (idx, len(PARA_RANGES) - 1))
        return (S, S)
    return PARA_RANGES[idx]


def resolve(para: int, sub: str) -> dict:
    """在指定段内解析逐字子串 → 引文对象。解析不到即 fail（构建结束时 rc≠0）。"""
    ps, pe = para_span(para)
    if not (ps <= pe):
        return {}
    at = TEXT.find(sub, ps, pe)
    if at < 0:
        # 给出诊断信息：段内实际内容
        fail("引文在该段内找不到：P%d %r\n    段内实际：%r" % (para, sub, TEXT[ps:pe][:120]))
        return {}
    start, end = at, at + len(sub)
    if TEXT[start:end] != sub:
        fail("text[start:end] != quote：P%d %r" % (para, sub))
        return {}
    whole = TEXT.count(sub)
    in_range = SLICE.count(sub)
    first = TEXT.find(sub)
    return {
        "quote": sub,
        "start": start,
        "end": end,
        "sourceHash": HASH,
        "para": para,
        "wholeTextOccurrences": whole,
        "occurrencesInRange": in_range,
        "startIsFirstOccurrence": start == first,
        "firstOccurrenceAt": first,
    }


def rq(para: int, sub: str) -> dict:
    o = resolve(para, sub)
    if not o:
        return {"quote": sub, "start": None, "end": None, "sourceHash": HASH, "para": para}
    if not (S <= o["start"] and o["end"] <= E):
        fail("引文越出区间：P%d %r (%d,%d)" % (para, sub, o["start"], o["end"]))
    return o


QUOTES: list[dict] = []


def Q(para: int, sub: str) -> dict:
    o = rq(para, sub)
    QUOTES.append(o)
    return o


# ---------------------------------------------------------------------------
# 1. tasks[]
# ---------------------------------------------------------------------------
def build_field(task_id: str, field: str, spec):
    """spec = (text, basis, [(para,quote)…], note) 或 None。"""
    if spec is None:
        return None, None, [], ("%sNote" % field)
    body, basis, quotes, note = spec
    qs = [Q(p, s) for p, s in quotes]
    if not qs:
        fail("%s.%s 非空却没有任何引文" % (task_id, field))
    return body, basis, qs, note


TASKS_OUT = []
for t in C.TASKS:
    item = {"id": t["id"], "actor": t["actor"]}
    nulls = []
    for field in ("objective", "obstacle", "action", "result", "cost"):
        body, basis, qs, note = build_field(t["id"], field, t.get(field))
        item[field] = body
        item["%sBasis" % field] = basis
        item["%sQuotes" % field] = qs
        item["%sNote" % field] = note
        if body is None:
            nulls.append(field)
            if not (isinstance(note, str) and note.strip()):
                fail("%s.%s 是 null 但 %sNote 为空 —— 未标注的未知" % (t["id"], field, field))
    item["nullFields"] = nulls
    TASKS_OUT.append(item)

# 五栏区间独立性
TASK_INTERVAL_OVERLAPS = []
for item in TASKS_OUT:
    spans = []
    for field in ("objective", "obstacle", "action", "result", "cost"):
        for q in item["%sQuotes" % field]:
            if q.get("start") is not None:
                spans.append((q["start"], q["end"], field, q["quote"]))
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b = spans[i], spans[j]
            if a[2] == b[2]:
                continue          # 同一栏内部可以并列多句
            if max(a[0], b[0]) < min(a[1], b[1]):
                TASK_INTERVAL_OVERLAPS.append({
                    "task": item["id"], "fieldA": a[2], "fieldB": b[2],
                    "start": max(a[0], b[0]), "end": min(a[1], b[1]),
                    "quoteA": a[3], "quoteB": b[3],
                })
if TASK_INTERVAL_OVERLAPS:
    for o in TASK_INTERVAL_OVERLAPS:
        fail("任务五栏共用依据：%s %s/%s 区间重叠 [%d,%d)" % (o["task"], o["fieldA"], o["fieldB"], o["start"], o["end"]))

# ---------------------------------------------------------------------------
# 2. causeEdges[]
# ---------------------------------------------------------------------------
CAUSES_OUT = []
for c in C.CAUSE_EDGES:
    CAUSES_OUT.append({
        "id": c["id"], "from": c["frm"], "to": c["to"],
        "trigger": c["trigger"], "mechanism": c["mechanism"], "basis": c["basis"],
        "quotes": [Q(p, s) for p, s in c["quotes"]], "note": c["note"],
    })
    if len(c["quotes"]) < 2:
        fail("%s 因果边少于 2 条引文（方向与触发都要有依据）" % c["id"])

REJECTED_EDGES_OUT = []
for r in C.REJECTED_EDGES:
    REJECTED_EDGES_OUT.append({
        "id": r["id"], "candidate": r["candidate"], "whyNot": r["whyNot"],
        "basis": r["basis"], "quotes": [Q(p, s) for p, s in r["quotes"]],
    })

SPEECH_OUT = [{"id": s["id"], "quote": Q(*s["quote"]), "why": s["why"]} for s in C.SPEECH_AS_CLUE]

# ---------------------------------------------------------------------------
# 3. states[] / knowledgeGaps[]
# ---------------------------------------------------------------------------
def state_part(who_id, label, spec):
    body, basis, quotes = spec
    return {
        label: body, "%sBasis" % label: basis,
        "%sQuotes" % label: [Q(p, s) for p, s in quotes],
    }


STATES_OUT = []
for st in C.STATES:
    item = {"id": st["id"], "who": st["who"]}
    item.update(state_part(st["id"], "before", st["before"]))
    item.update(state_part(st["id"], "after", st["after"]))
    item.update(state_part(st["id"], "anchor", st["anchor"]))
    item["note"] = st["note"]
    for lbl in ("before", "after", "anchor"):
        if not item["%sQuotes" % lbl]:
            fail("%s.%s 缺引文（状态变化必须有事件锚点）" % (st["id"], lbl))
    # 前后值必须是不同区间（否则不叫变化）
    b = item["beforeQuotes"][0]
    a = item["afterQuotes"][-1]
    if b.get("start") is not None and a.get("start") is not None:
        if b["start"] == a["start"] and b["end"] == a["end"]:
            fail("%s 前后值引用了同一区间，不构成变化" % st["id"])
    STATES_OUT.append(item)

KNOWLEDGE_OUT = []
for k in C.KNOWLEDGE_GAPS:
    KNOWLEDGE_OUT.append({
        "id": k["id"], "proposition": k["proposition"],
        "knows": k["knows"], "doesNotKnow": k["doesNotKnow"],
        "unconfirmed": k["unconfirmed"], "basis": k["basis"],
        "quotes": [Q(p, s) for p, s in k["quotes"]], "note": k["note"],
    })

# ---------------------------------------------------------------------------
# 4. foreshadows[] / worldSettings[] / themeReadings[]
# ---------------------------------------------------------------------------
FORE_OUT = []
for f in C.FORESHADOWS:
    what, basis, quotes = f["setup"]
    payout = f["payoff"]
    status = f["status"]
    if status == "unresolved" and payout is not None:
        fail("%s 标 unresolved 却给了 payoff" % f["id"])
    if status == "resolved" and payout is None:
        fail("%s 标 resolved 却没有 payoff（有铺设与回收才算伏笔）" % f["id"])
    if status == "unresolved" and not (f.get("unresolvedWhat") or "").strip():
        fail("%s 标 unresolved 但没写 unresolvedWhat（缺什么要说清）" % f["id"])
    FORE_OUT.append({
        "id": f["id"], "name": f["name"],
        "setup": {"what": what, "quote": [Q(p, s) for p, s in quotes], "basis": basis},
        "payoff": payout, "status": status,
        "unresolvedWhat": f.get("unresolvedWhat"), "basis": f["basis"], "note": f["note"],
    })

NOT_FORE_OUT = [{
    "id": n["id"], "candidate": n["candidate"],
    "whyNot": n.get("whyNot") or n["why"],
    "basis": n["basis"], "quotes": [Q(p, s) for p, s in n["quotes"]],
} for n in C.NOT_FORESHADOWS]

WS_OUT = []
for w in C.WORLD_SETTINGS:
    kind = w["kind"]
    entry = {
        "id": w["id"], "kind": kind, "name": w["name"],
        "quote": Q(*w["quote"]),
        "extraQuotes": [Q(p, s) for p, s in w.get("extra", [])],
        "explain": w["explain"], "basis": w["basis"],
    }
    if kind == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            fail("%s 地点缺 placeState（arrived/mentioned 必须落字段）" % w["id"])
        entry["placeState"] = w["placeState"]
        entry["placeStateNote"] = w.get("placeStateNote", (
            "arrived 的判据是**有到达/进入动作**；mentioned 的判据是只被提到/议论/转述，"
            "本区间没有人前往或驻守。二者按原文动作区分，不按地名是否出现区分。"))
    elif kind == "item":
        states = w.get("itemStates")
        if not states or any(s not in ("hold", "transfer", "use", "lose") for s in states):
            fail("%s 物件 itemStates 非法或为空：%r（须从 hold/transfer/use/lose 多选）" % (w["id"], states))
        entry["itemStates"] = states
        entry["itemStatesNote"] = w.get("itemStatesNote", (
            "四态分开写，每个态都按原文动作判：hold＝持有、transfer＝交接、use＝使用、lose＝丢失。"
            "本条目未列出的态即本区间无依据，不用「物品链」把四态合成一条。"))
    elif kind == "rule":
        if w.get("institution") not in ("declared", "executed", "misunderstood"):
            fail("%s 规则缺 institution（declared/executed/misunderstood 必须落字段）" % w["id"])
        entry["institution"] = w["institution"]
        entry["institutionNote"] = w.get("institutionNote", "")
        if not entry["institutionNote"].strip():
            fail("%s 规则缺 institutionNote（要写清它如何解释人物能做/不能做什么）" % w["id"])
    else:
        fail("%s kind 非法：%r" % (w["id"], kind))
    WS_OUT.append(entry)

NOT_WS_OUT = [{
    "id": n["id"], "candidate": n["candidate"],
    "whyNot": n.get("whyNot") or n["why"],
    "basis": n["basis"], "quotes": [Q(p, s) for p, s in n["quotes"]],
} for n in C.NOT_WORLD_SETTINGS]

THEME_OUT = []
for th in C.THEME_READINGS:
    if not th.get("perspective") or not th.get("support") or not th.get("counter"):
        fail("%s 主题读法缺三件之一（perspective/support/counter）" % th["id"])
    THEME_OUT.append({
        "id": th["id"], "perspective": th["perspective"],
        "support": [{"text": s["text"], "quote": Q(*s["quote"])} for s in th["support"]],
        "counter": [{"text": s["text"], "quote": Q(*s["quote"])} for s in th["counter"]],
        "basis": th["basis"], "note": th["note"],
    })
if len(THEME_OUT) > 2:
    fail("themeReadings 超过 2 条（提示词上限 1–2）")

TN_OUT = [{
    "id": t["id"], "what": t["what"], "quote": Q(*t["quote"]),
    "extraQuotes": [Q(p, s) for p, s in t.get("extra", [])],
    "note": t["note"], "basis": t["basis"],
} for t in C.TEXTUAL_NOTES]

UNK_OUT = [{
    "id": u["id"], "what": u["what"], "why": u["why"], "basis": u["basis"],
    "quotes": [Q(p, s) for p, s in u["quotes"]],
} for u in C.UNKNOWNS]

SC_OUT = [{"id": s["id"], "risk": s["risk"], "whyStill": s["whyStill"],
           "howToOverturn": s["howToOverturn"]} for s in C.SELF_CRITIQUE]

# ---------------------------------------------------------------------------
# 机器自检
# ---------------------------------------------------------------------------
uniq = {}
for q in QUOTES:
    if q.get("start") is None:
        continue
    uniq.setdefault((q["start"], q["end"]), q["quote"])
ambiguous = [{
    "quote": q["quote"], "start": q["start"], "end": q["end"],
    "sourceHash": HASH,
    "wholeTextOccurrences": q["wholeTextOccurrences"],
    "occurrencesInRange": q["occurrencesInRange"],
    "startIsFirstOccurrence": q["startIsFirstOccurrence"],
} for q in QUOTES if q.get("start") is not None and q["occurrencesInRange"] > 1]
# 去重（同一引文可能被多处引用）
_seen = set()
_amb = []
for a in ambiguous:
    k = (a["quote"], a["start"], a["end"])
    if k not in _seen:
        _seen.add(k)
        _amb.append(a)

# 覆盖率
intervals = sorted(uniq.keys())
union = 0
merged = []
for st, en in intervals:
    if merged and st <= merged[-1][1]:
        merged[-1] = (merged[-1][0], max(merged[-1][1], en))
    else:
        merged.append((st, en))
for st, en in merged:
    union += en - st
non_space = sum(1 for ch in SLICE if not ch.isspace())

touched = set()
for st, en in intervals:
    for i, (ps, pe) in enumerate(PARA_RANGES):
        if max(st, ps) < min(en, pe):
            touched.add(i)
zero = [i for i in range(len(PARA_RANGES)) if i not in touched]

null_fields = []
for item in TASKS_OUT:
    for f in item["nullFields"]:
        null_fields.append("%s.%s" % (item["id"], f))
for item in TASKS_OUT:
    for f in ("objective", "obstacle", "action", "result", "cost"):
        if item[f] is None:
            n = item.get("%sNote" % f) or ""
            if not n.strip():
                fail("未标注的 null：%s.%s" % (item["id"], f))

CAND = {
    "schemaVersion": "castline/read-candidate/1",
    "task": "read:dafeng:L3:0267",
    "agent": "w-sanguo-0",
    "role": "READER（原文精读工作者）",
    "book": "dafeng",
    "bookTitle": "大奉打更人",
    "lane": 3,
    "unitIndex": 267,
    "unitHead": "第三十八章 五号的传书",
    "source": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "selector": "docs[0].text",
        "range": [S, E],
        "codepoints": len(SLICE),
        "sourceHash": HASH,
        "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
        "sliceSha256": hashlib.sha256(SLICE.encode("utf-8")).hexdigest(),
        "sliceSha256Scope": "切片 docs[0].text[start:end] 的 utf-8 字节 sha256（额外字段，不覆盖 sourceHash）",
        "offsetCaliber": "start/end 是相对 docs[0].text **全文** 的 codepoint 偏移，不是相对切片",
        "boundaryHead": SLICE[:len("第三十八章 五号的传书")],
        "boundaryHeadMatchesTitle": SLICE.startswith("第三十八章 五号的传书"),
        "boundaryTail": SLICE[-12:],
        "nonEmptyParagraphs": len(PARA_RANGES),
        "totalParagraphSlots": SLICE.count("\n") + 1,
        "graphCachePath": "data/cache/1063b17ca65ec1b76f30e460.json",
    },
    "provenanceNote": (
        "本候选由 loop/state/out/read_dafeng_L3_0267.w-sanguo-0.build/build_candidate.py 生成，"
        "内容模块是同目录的 content_0267.py。所有引文偏移都由构建脚本在 docs[0].text 上现场 "
        "`find(sub, para_start, para_end)` 解析，并立即断言 text[start:end]==sub —— 没有任何一个手填偏移；"
        "解析不到即抛错并以 rc=1 结束。接手时同路径已有一份未提交草稿（署 w-dafeng-0，sha256 d8f330a5…，"
        "无 submit 记录），其原字节已快照到同目录 prior_draft_unsubmitted.d8f330a5.json，未删除、未采信其语义判断。"
    ),
    "semanticReview": "not-performed",
    "semanticReviewNote": (
        "**没有做独立语义评审**（semanticReview=not-performed）。本候选完成的是：引文构造性逐字命中"
        "（find + text[start:end]==quote 自检）、五栏区间独立性机器自检、null 栏全部带非空 Note、"
        "每条断言带 basis、四态/三态字段落盘。引文定位正确 ≠ 语义已核验 —— 语义核验要由独立的 read-verify 复核者做。"
    ),
    "basisLegend": {"explicit": "原文直述", "inferred": "我的归纳", "derived": "跨段推导",
                    "unverified": "存疑"},
    "namingConvention": C.NAMING_NOTE,
    "nullFieldRule": (
        "缺项写 null，并在同名 <栏>Note 写明**为什么没有**；不写理由的 null 视为未标注的未知。"
        "本候选的 null 栏：%s。" % ("、".join(null_fields) if null_fields else "（无）")
    ),
    "speechAsClueNotFact": SPEECH_OUT,
    "speechQuotingFieldsNote": (
        "independent_audit.py 会列出「引文本身是台词/消息」的栏位供复核快筛（本候选 6 处，全部落在 "
        "T07.result 与 T10.result）。这 6 处是**成立**的用法，不是「把人物的话当叙述事实」："
        "这两栏要回答的是「他实际收到了什么」，而被收到的**正是那些消息的文字内容**——"
        "引文对象就是消息本身，不是借它断言世界状态。两处的 note 均已写明「本区间没有写他自己的回应」"
        "「不推断他听没听」。其余任何栏位若引用台词，都必须带说话人归属，见 speechAsClueNotFact。"
    ),
    "tasks": TASKS_OUT,
    "taskIntervalOverlaps": TASK_INTERVAL_OVERLAPS,
    "causeEdges": CAUSES_OUT,
    "rejectedEdges": REJECTED_EDGES_OUT,
    "states": STATES_OUT,
    "knowledgeGaps": KNOWLEDGE_OUT,
    "foreshadows": FORE_OUT,
    "notForeshadows": NOT_FORE_OUT,
    "worldSettings": WS_OUT,
    "notWorldSettings": NOT_WS_OUT,
    "themeReadings": THEME_OUT,
    "textualNotes": TN_OUT,
    "unknowns": UNK_OUT,
    "selfCritique": SC_OUT,
    "selfCritiqueNote": C.SELF_CRITIQUE_NOTE,
    "machineSelfCheck": {
        "buildScript": "loop/state/out/read_dafeng_L3_0267.w-sanguo-0.build/build_candidate.py",
        "contentModule": "loop/state/out/read_dafeng_L3_0267.w-sanguo-0.build/content_0267.py",
        "verifyScript": "loop/state/out/read_dafeng_L3_0267.w-sanguo-0.build/verify_candidate.py",
        "reproduceCommand": ("python3 -B -s loop/state/out/read_dafeng_L3_0267.w-sanguo-0.build/build_candidate.py"
                             " && python3 -B -s loop/state/out/read_dafeng_L3_0267.w-sanguo-0.build/verify_candidate.py"),
        "quoteObjectsResolved": sum(1 for q in QUOTES if q.get("start") is not None),
        "uniqueQuoteIntervals": len(uniq),
        "resolveFailures": sum(1 for q in QUOTES if q.get("start") is None),
        "resolveFailureDetail": [q["quote"] for q in QUOTES if q.get("start") is None],
        "taskFieldIntervalOverlap": len(TASK_INTERVAL_OVERLAPS),
        "nullFields": len(null_fields),
        "nullFieldList": null_fields,
        "requiredSections": ["tasks", "causeEdges", "states", "foreshadows", "worldSettings",
                             "themeReadings"],
    },
    "coverage": {
        "sliceCodepoints": len(SLICE),
        "nonSpaceCodepoints": non_space,
        "quoteUnionCodepoints": union,
        "quoteUnionRatioOfSlice": round(union / len(SLICE), 4),
        "quoteUnionRatioOfNonSpace": round(union / non_space, 4),
        "quoteIntervals": [{"start": a, "end": b} for a, b in merged],
        "paragraphs": len(PARA_RANGES),
        "paragraphsTouchedByAtLeastOneQuote": len(touched),
        "zeroCoveredParagraphs": zero,
        "ambiguousQuotes": _amb,
        "note": ("覆盖率**不作为质量分**，列出来只为让复核一眼看到哪些段没被引用。"
                 "ambiguousQuotes 是同一子串在切片内出现多次的引文（偏移仍逐字成立），供复核判断指代。"),
    },
}

# 必需分区键必须在（validate_sections 会机器核对）
for key in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    if key not in CAND:
        fail("缺内容分区键：%s" % key)

OUT.write_text(json.dumps(CAND, ensure_ascii=False, indent=1), encoding="utf-8")

print("引文对象解析：成功 %d / 失败 %d" % (CAND["machineSelfCheck"]["quoteObjectsResolved"],
                                          CAND["machineSelfCheck"]["resolveFailures"]))
print("唯一引文区间：%d；五栏重叠：%d；null 栏：%d"
      % (len(uniq), len(TASK_INTERVAL_OVERLAPS), len(null_fields)))
print("切片 %d 码点；引文并集覆盖 %d（%.1f%% / 非空白 %.1f%%）；零覆盖段 %d/%d"
      % (len(SLICE), union, 100 * union / len(SLICE), 100 * union / non_space,
         len(zero), len(PARA_RANGES)))
print("写出：%s" % OUT)
if PROBLEMS:
    print("\n构建期问题 %d 条：" % len(PROBLEMS), file=sys.stderr)
    for p in PROBLEMS:
        print(" - %s" % p, file=sys.stderr)
    sys.exit(1)
print("构建自检：全部通过")
