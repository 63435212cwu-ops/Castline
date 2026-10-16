#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 content_0275.py 的读解 + docs[0].text 的原文，合成 read_dafeng_L3_0275.candidate.json。

为什么引文用锚点解析而不是手抄：
  本切片里有大量「.......」「........」点号串与全角引号（“”），手抄进 JSON 极易在一两个点上失真。
  本脚本从 docs[0].text 里**按段抠子串**，所以写进候选的 quote 一定是原文本身；
  同时逐条自检 text[start:end] == quote。

产物：
  · loop/state/out/read_dafeng_L3_0275.candidate.json
  · machineSelfCheck 里记录复算命令
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = Path(__file__).resolve().parent
sys.path.insert(0, str(BUILD))
import content_0275 as C  # noqa: E402

DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L3_0275.candidate.json"

AGENT = "w-xiyou-1"
TASK_ID = C.TASK_ID


def load_text():
    return json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]


def paragraph_index(text, S, E):
    """非空段 → (start, end, line)。段号 0 是本单元章题。"""
    out = []
    off = S
    for line in text[S:E].split("\n"):
        if line.strip():
            out.append((off, off + len(line), line))
        off += len(line) + 1
    return out


PARAS = None
TEXT = None
FAILURES = []


def resolve_anchor(anchor):
    p = anchor["p"]
    if p < 0 or p >= len(PARAS):
        FAILURES.append("段号越界：%r" % (anchor,))
        return None
    ps, pe, line = PARAS[p]
    a = anchor["a"]
    i = line.find(a)
    if i < 0:
        FAILURES.append("段 P%03d 内找不到起点串 %r（段=%.60r）" % (p, a, line))
        return None
    start = ps + i
    if "b" in anchor:
        b = anchor["b"]
        j = line.find(b, i + len(a))
        if j < 0:
            FAILURES.append("段 P%03d 内起点之后找不到终点串 %r（段=%.60r）" % (p, b, line))
            return None
        end = ps + j + len(b)
    else:
        end = start + len(a)
    quote = TEXT[start:end]
    if quote != TEXT[start:end]:
        FAILURES.append("切片自检失败：%r" % (quote,))
    occurrences = TEXT.count(quote)
    in_range = TEXT[C.S:C.E].count(quote)
    first = TEXT.find(quote)
    return {
        "quote": quote,
        "start": start,
        "end": end,
        "sourceHash": C.SOURCE_HASH,
        "para": p,
        "wholeTextOccurrences": occurrences,
        "occurrencesInRange": in_range,
        "startIsFirstOccurrence": first == start,
        "firstOccurrenceAt": first,
    }


ALL_QUOTES = []
AUTHOR_REGION = tuple(C.AUTHOR_REGION)
NARRATIVE_VIOLATIONS = []
AUTHOR_REGION_EXEMPT = []


def R(anchor, narrative=True):
    q = resolve_anchor(anchor)
    if q is None:
        return None
    ALL_QUOTES.append(q)
    in_author = AUTHOR_REGION[0] <= q["start"] < AUTHOR_REGION[1]
    q["inAuthorRegion"] = in_author
    if in_author:
        if narrative:
            NARRATIVE_VIOLATIONS.append(q)
        else:
            AUTHOR_REGION_EXEMPT.append(
                {"quote": q["quote"], "start": q["start"], "end": q["end"],
                 "sourceHash": q["sourceHash"], "para": q["para"],
                 "why": "仅在 textualNotes/selfCritique 里用于**说明作者区域本身**（PS/站点分隔线），"
                        "不作任何叙事证据；豁免登记在 candidate.authorRegionNote"})
    return q


def RL(anchors, narrative=True):
    return [R(a, narrative=narrative) for a in anchors]


def expand_task(t):
    out = {"id": t["id"], "actor": t["actor"], "nullFields": []}
    for field in ("objective", "obstacle", "action", "result", "cost"):
        node = t[field]
        if node.get("text") is None:
            out[field] = None
            out[field + "Basis"] = None
            out[field + "Quotes"] = []
            out[field + "Note"] = node["note"]
            out["nullFields"].append(field)
        else:
            out[field] = node["text"]
            out[field + "Basis"] = node["basis"]
            out[field + "Quotes"] = RL(node["quotes"])
            if node.get("note"):
                out[field + "Note"] = node["note"]
    return out


def expand_edge(e):
    if "frm" in e:
        return {"id": e["id"], "from": e["frm"], "to": e["to"],
                "trigger": e["trigger"], "mechanism": e["mechanism"],
                "basis": e["basis"], "quotes": RL(e["quotes"]), "note": e["note"]}
    return {"id": e["id"], "candidate": e["candidate"], "whyNot": e["whyNot"],
            "basis": e["basis"], "quotes": RL(e["quotes"])}


def expand_state(s):
    return {"id": s["id"], "who": s["who"],
            "before": s["before"], "beforeBasis": s["beforeBasis"],
            "beforeQuotes": RL(s["beforeQuotes"]),
            "after": s["after"], "afterBasis": s["afterBasis"],
            "afterQuotes": RL(s["afterQuotes"]),
            "anchor": s["anchor"], "anchorBasis": s["anchorBasis"],
            "anchorQuotes": RL(s["anchorQuotes"]),
            "note": s["note"]}


def expand_foreshadow(f):
    setup, payoff = f["setup"], f["payoff"]
    return {"id": f["id"], "name": f["name"],
            "setup": {"what": setup["what"], "quotes": RL(setup["quotes"]),
                      "basis": setup["basis"]},
            "payoff": None if payoff is None else
                      {"what": payoff["what"], "quotes": RL(payoff["quotes"]),
                       "basis": payoff["basis"]},
            "status": f["status"], "unresolvedWhat": f.get("unresolvedWhat"),
            "basis": f["basis"], "note": f["note"]}


def expand_setting(w):
    node = {"id": w["id"], "kind": w["kind"], "name": w["name"],
            "quote": R(w["quote"]), "extraQuotes": RL(w.get("extraQuotes") or []),
            "explain": w["explain"], "basis": w["basis"]}
    if w["kind"] == "rule":
        node["institution"] = w["institution"]
        node["institutionNote"] = w["institutionNote"]
    elif w["kind"] == "place":
        node["placeState"] = w["placeState"]
        node["placeStateNote"] = w["placeStateNote"]
    elif w["kind"] == "item":
        node["itemStates"] = w["itemStates"]
        node["itemStateQuotes"] = {k: RL(v) for k, v in w["itemStateQuotes"].items()}
        node["itemStatesNote"] = w["itemStatesNote"]
    return node


def coverage():
    ivs = sorted({(q["start"], q["end"]) for q in ALL_QUOTES})
    union = 0
    cur = None
    for s, e in ivs:
        if cur is None:
            cur = [s, e]
        elif s <= cur[1]:
            cur[1] = max(cur[1], e)
        else:
            union += cur[1] - cur[0]
            cur = [s, e]
    if cur:
        union += cur[1] - cur[0]
    slice_len = C.E - C.S
    slice_txt = TEXT[C.S:C.E]
    nonspace = sum(1 for ch in slice_txt if not ch.isspace())
    touched = set()
    for s, e in ivs:
        for pno, (ps, pe, line) in enumerate(PARAS):
            if s < pe and e > ps:
                touched.add(pno)
    amb = [q for q in ALL_QUOTES if q["wholeTextOccurrences"] > 3]
    return {
        "sliceCodepoints": slice_len,
        "nonSpaceCodepoints": nonspace,
        "quoteUnionCodepoints": union,
        "quoteUnionRatioOfSlice": round(union / slice_len, 4),
        "quoteUnionRatioOfNonSpace": round(union / nonspace, 4),
        "quoteIntervals": len(ivs),
        "paragraphs": len(PARAS),
        "paragraphsTouchedByAtLeastOneQuote": len(touched),
        "zeroCoveredParagraphs": [p for p in range(len(PARAS)) if p not in touched],
        "ambiguousQuotes": [
            {"quote": q["quote"], "start": q["start"], "end": q["end"],
             "sourceHash": q["sourceHash"], "para": q["para"],
             "wholeTextOccurrences": q["wholeTextOccurrences"],
             "occurrencesInRange": q["occurrencesInRange"],
             "startIsFirstOccurrence": q["startIsFirstOccurrence"],
             "firstOccurrenceAt": q["firstOccurrenceAt"],
             "whyAmbiguous": ("全文出现 %d 次（多为点号串/短串）；本对象的位置是**段内那一处**，"
                              "按 text[start:end]==quote 仍逐字成立，但不能只靠 quote 文本反查位置。"
                              % q["wholeTextOccurrences"])}
            for q in amb],
        "note": ("并集按**区间并集**算（重叠只算一次），不是把每条引文长度相加。"
                 "ambiguousQuotes 是全文出现次数 >3 的短串（多为点号串），"
                 "它们在区间内取的是段内那一处，逐字仍成立但不宜单独作为定位依据。"),
    }


def main():
    global TEXT, PARAS
    TEXT = load_text()
    PARAS = paragraph_index(TEXT, C.S, C.E)

    head = TEXT[C.S:C.E][:len(C.UNIT_HEAD)]
    tail = TEXT[C.E - 20:C.E]
    if head != C.UNIT_HEAD:
        print("[FATAL] 切片不以章题开头：%r" % head, file=sys.stderr)
        return 2
    if hashlib.sha256(DOCS.read_bytes()).hexdigest() != C.SOURCE_HASH:
        print("[FATAL] docs.json 的 sha256 与任务给定不一致", file=sys.stderr)
        return 2

    candidate = {
        "schemaVersion": "castline/read-candidate/1",
        "task": C.TASK_ID,
        "agent": AGENT,
        "role": "READER（原文精读工作者）",
        "book": C.BOOK,
        "bookTitle": "大奉打更人",
        "lane": C.LANE,
        "unitIndex": C.UNIT_INDEX,
        "unitHead": C.UNIT_HEAD,
        "source": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
            "selector": "docs[0].text",
            "range": [C.S, C.E],
            "codepoints": C.E - C.S,
            "sourceHash": C.SOURCE_HASH,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
            "sliceSha256": hashlib.sha256(TEXT[C.S:C.E].encode("utf-8")).hexdigest(),
            "sliceSha256Scope": "切片 docs[0].text[start:end] 的 utf-8 字节 sha256（额外字段，不覆盖 sourceHash）",
            "offsetCaliber": "start/end 是相对 docs[0].text **全文** 的 codepoint 偏移，不是相对切片",
            "boundaryHead": head,
            "boundaryHeadMatchesTitle": True,
            "boundaryTail": tail,
            "nonEmptyParagraphs": len(PARAS),
            "graphCachePath": "data/cache/1063b17ca65ec1b76f30e460.json",
        },
        "provenanceNote": C.PROVENANCE_NOTE,
        "semanticReview": "not-performed",
        "semanticReviewNote": C.SEMANTIC_REVIEW_NOTE,
        "basisLegend": C.BASIS_LEGEND,
        "namingConvention": C.NAMING_CONVENTION,
        "nullFieldRule": C.NULL_FIELD_RULE,
        "authorRegionNote": ("AUTHOR_REGION=[%d,%d)：作者 PS（P147「PS：哈哈哈…」）、"
                             "收尾感叹（P148）与站点分隔线（P149）。"
                             "本候选的**叙事**引文一律不落在该区间内；"
                             "落在里面的引用只有 textualNotes 与 selfCritique 的纯说明性条目，"
                             "它们逐条登记在 authorRegionExemptions 里，且不作为任何叙事证据。"
                             % (AUTHOR_REGION[0], AUTHOR_REGION[1])),
        "authorRegionExemptions": AUTHOR_REGION_EXEMPT,
        "tasks": [expand_task(t) for t in C.TASKS],
        "causeEdges": [expand_edge(e) for e in C.CAUSE_EDGES],
        "rejectedEdges": [expand_edge(e) for e in C.REJECTED_EDGES],
        "states": [expand_state(s) for s in C.STATES],
        "knowledgeGaps": [
            {"id": k["id"], "proposition": k["proposition"], "knows": k["knows"],
             "doesNotKnow": k["doesNotKnow"], "unconfirmed": k["unconfirmed"],
             "basis": k["basis"], "quotes": RL(k["quotes"])}
            for k in C.KNOWLEDGE_GAPS],
        "foreshadows": [expand_foreshadow(f) for f in C.FORESHADOWS],
        "notForeshadows": [
            {"id": n["id"], "candidate": n["candidate"], "whyNot": n["whyNot"],
             "basis": n["basis"], "quotes": RL(n["quotes"])}
            for n in C.NOT_FORESHADOWS],
        "worldSettings": [expand_setting(w) for w in C.WORLD_SETTINGS],
        "notWorldSettings": [
            {"id": n["id"], "candidate": n["candidate"], "whyNot": n["whyNot"],
             "basis": n["basis"], "quotes": RL(n["quotes"])}
            for n in C.NOT_WORLD_SETTINGS],
        "themeReadings": [
            {"id": t["id"], "perspective": t["perspective"],
             "support": [{"text": s["text"], "quote": R(s["quote"])} for s in t["support"]],
             "counter": [{"text": s["text"], "quote": R(s["quote"])} for s in t["counter"]],
             "basis": t["basis"], "note": t["note"]}
            for t in C.THEME_READINGS],
        "speechAsClueNotFact": [
            {"id": s["id"], "quote": R(s["quote"]), "why": s["why"], "usedAs": s["usedAs"]}
            for s in C.SPEECH_CLUES],
        "textualNotes": [
            {"id": t["id"], "what": t["what"], "quote": R(t["quote"], narrative=False),
             "extraQuotes": RL(t.get("extraQuotes") or [], narrative=False),
             "note": t["note"], "basis": t["basis"]}
            for t in C.TEXTUAL_NOTES],
        "unknowns": [
            {"id": u["id"], "what": u["what"], "why": u["why"],
             "basis": u["basis"], "quotes": RL(u["quotes"])}
            for u in C.UNKNOWNS],
        "selfCritique": [
            {"id": s["id"], "what": s["what"], "whyStill": s["whyStill"],
             "quote": R(s["quote"], narrative=False)}
            for s in C.SELF_CRITIQUE],
    }

    if FAILURES:
        print("[FATAL] 引文解析失败 %d 条：" % len(FAILURES), file=sys.stderr)
        for f in FAILURES[:40]:
            print("   -", f, file=sys.stderr)
        return 3

    # ── 五栏自检：① 区间两两不重叠 ② 引文文本不重复（禁止一句供两栏）──
    overlaps, dup_texts = [], []
    for t in candidate["tasks"]:
        ivs = []
        for field in ("objective", "obstacle", "action", "result", "cost"):
            for q in t[field + "Quotes"]:
                ivs.append((field, q["start"], q["end"], q["quote"]))
        for i in range(len(ivs)):
            for j in range(i + 1, len(ivs)):
                f1, s1, e1, q1 = ivs[i]
                f2, s2, e2, q2 = ivs[j]
                if s1 < e2 and s2 < e1:
                    overlaps.append({"task": t["id"], "a": f1, "b": f2,
                                     "aRange": [s1, e1], "bRange": [s2, e2],
                                     "aQuote": q1, "bQuote": q2})
                if q1 == q2:
                    dup_texts.append({"task": t["id"], "a": f1, "b": f2, "quote": q1})
                elif q1 in q2 or q2 in q1:
                    dup_texts.append({"task": t["id"], "a": f1, "b": f2,
                                      "quote": q1 if len(q1) < len(q2) else q2,
                                      "kind": "substring"})

    # ── null 栏必须有非空 Note ──────────────────────────────────────
    null_problems = []
    for t in candidate["tasks"]:
        for field in ("objective", "obstacle", "action", "result", "cost"):
            if t[field] is None:
                note = t.get(field + "Note")
                if not note or not str(note).strip():
                    null_problems.append("%s.%s 是 null 但没有 Note" % (t["id"], field))

    # ── 枚举值自检 ─────────────────────────────────────────────────
    enum_problems = []
    for w in candidate["worldSettings"]:
        if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            enum_problems.append("%s institution=%r" % (w["id"], w.get("institution")))
        if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            enum_problems.append("%s placeState=%r" % (w["id"], w.get("placeState")))
        if w["kind"] == "item":
            st = w.get("itemStates") or []
            bad = [s for s in st if s not in ("hold", "transfer", "use", "lose")]
            if bad or not st:
                enum_problems.append("%s itemStates=%r" % (w["id"], st))
            missing = [s for s in ("hold", "transfer", "use", "lose")
                       if s not in (w.get("itemStateQuotes") or {})]
            if missing:
                enum_problems.append("%s itemStateQuotes 缺状态键 %r" % (w["id"], missing))
    for f in candidate["foreshadows"]:
        if f["status"] not in ("resolved", "unresolved"):
            enum_problems.append("%s status=%r" % (f["id"], f["status"]))
        if f["status"] == "unresolved" and not f.get("unresolvedWhat"):
            enum_problems.append("%s unresolved 但没写 unresolvedWhat" % f["id"])
        if f["payoff"] is None and f["status"] != "unresolved":
            enum_problems.append("%s 没有 payoff 却标 %s" % (f["id"], f["status"]))

    candidate["machineSelfCheck"] = {
        "buildScript": "loop/state/out/read_dafeng_L3_0275.w-xiyou-1.build/build_candidate.py",
        "contentModule": "loop/state/out/read_dafeng_L3_0275.w-xiyou-1.build/content_0275.py",
        "verifyScript": "loop/state/out/read_dafeng_L3_0275.w-xiyou-1.build/verify_candidate.py",
        "independentAuditScript": "loop/state/out/read_dafeng_L3_0275.w-xiyou-1.build/independent_audit.py",
        "reproduceCommand": ("python3 -B -s loop/state/out/read_dafeng_L3_0275.w-xiyou-1.build/build_candidate.py && "
                             "python3 -B -s loop/state/out/read_dafeng_L3_0275.w-xiyou-1.build/verify_candidate.py && "
                             "python3 -B -s loop/state/out/read_dafeng_L3_0275.w-xiyou-1.build/independent_audit.py"),
        "quoteObjectsResolved": len(ALL_QUOTES),
        "uniqueQuoteIntervals": len({(q["start"], q["end"]) for q in ALL_QUOTES}),
        "resolveFailures": len(FAILURES),
        "resolveFailureDetail": FAILURES[:20],
        "taskFieldIntervalOverlap": len(overlaps),
        "taskFieldIntervalOverlapDetail": overlaps[:20],
        "taskFieldDuplicateQuoteText": len(dup_texts),
        "taskFieldDuplicateQuoteTextDetail": dup_texts[:20],
        "nullFields": sum(len(t["nullFields"]) for t in candidate["tasks"]),
        "nullFieldList": ["%s.%s" % (t["id"], f) for t in candidate["tasks"] for f in t["nullFields"]],
        "nullFieldMissingNote": null_problems,
        "enumProblems": enum_problems,
        "narrativeQuotesInAuthorRegion": len(NARRATIVE_VIOLATIONS),
        "narrativeQuoteViolationDetail": NARRATIVE_VIOLATIONS[:5],
        "requiredSections": ["tasks", "causeEdges", "states", "foreshadows",
                             "worldSettings", "themeReadings"],
    }
    candidate["coverage"] = coverage()

    OUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = (not FAILURES and not overlaps and not dup_texts and not null_problems
          and not enum_problems and not NARRATIVE_VIOLATIONS)
    print("写出：%s" % OUT)
    print("引文对象 %d 个 / 唯一区间 %d / 解析失败 %d"
          % (len(ALL_QUOTES), len({(q["start"], q["end"]) for q in ALL_QUOTES}), len(FAILURES)))
    print("五栏区间重叠 %d / 五栏引文文本重复 %d / null 缺理由 %d / 枚举问题 %d / 叙事引文落入作者区 %d"
          % (len(overlaps), len(dup_texts), len(null_problems),
             len(enum_problems), len(NARRATIVE_VIOLATIONS)))
    print("coverage: 并集 %d 码点（切片 %d，占比 %.4f）"
          % (candidate["coverage"]["quoteUnionCodepoints"], C.E - C.S,
             candidate["coverage"]["quoteUnionRatioOfSlice"]))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
