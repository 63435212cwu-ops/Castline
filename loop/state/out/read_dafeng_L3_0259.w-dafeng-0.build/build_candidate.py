#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 content_0259.py 的内容模块编译成候选 JSON（read:dafeng:L3:0259）。

设计要点（都是为了「引用必须可复核」这一条）：
· 偏移**不手写**：内容模块只给 (段号, 逐字子串)，本脚本在 docs[0].text 现场 find 出偏移。
  find 用段落的绝对起止做边界约束，所以既保证逐字命中，也保证落在正确的段里。
· 同一子串在全文出现多次时，取**段内**那一次；并把 wholeTextOccurrences / occurrencesInRange
  / startIsFirstOccurrence 一并记录下来，供复核判断引用是否有歧义。
· 段落表由 text[S:E].split("\n\n") 现场重建，段号即该表的 0 基下标（与上一单元口径一致）。
· 输出前自检：五栏引文区间两两不相交、非空栏必有引文、null 栏必有 <栏>Note。
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BUILD_DIR))

spec = importlib.util.spec_from_file_location("content_0259", BUILD_DIR / "content_0259.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

docs_path = ROOT / C.DOCS_PATH
out_path = ROOT / "loop/state/out/read_dafeng_L3_0259.candidate.json"

file_sha = hashlib.sha256(docs_path.read_bytes()).hexdigest()
assert file_sha == C.SOURCE_HASH, "docs.json 哈希与任务声明不符：%s" % file_sha

docs = json.loads(docs_path.read_text(encoding="utf-8"))
text = docs[0]["text"]
S, E = C.SLICE
assert file_sha == C.SOURCE_HASH

slice_text = text[S:E]
assert slice_text.startswith("第三十章 预言师"), "切片未以单元标题开头"
PARTS = slice_text.split("\n\n")
PARA_OFFSETS = []
_off = S
for _p in PARTS:
    PARA_OFFSETS.append((_off, _off + len(_p)))
    _off += len(_p) + 2
PARA_TEXT = PARTS

problems = []


def resolve(spec_pair, where):
    """(段号, 逐字子串) → 引文对象。所有偏移由现场 find 得出。"""
    if not (isinstance(spec_pair, (tuple, list)) and len(spec_pair) == 2):
        problems.append("%s: 引文规格不是 (段号, 子串)：%r" % (where, spec_pair))
        return None
    para, quote = spec_pair
    if not isinstance(para, int) or not (0 <= para < len(PARTS)):
        problems.append("%s: 段号越界 %r" % (where, para))
        return None
    if not isinstance(quote, str) or not quote:
        problems.append("%s: 引文为空" % where)
        return None
    p_start, p_end = PARA_OFFSETS[para]
    seg = text[p_start:p_end]
    pos = seg.find(quote)
    if pos < 0:
        problems.append("%s: 引文不在第 %d 段内：%r" % (where, para, quote[:40]))
        return None
    start = p_start + pos
    end = start + len(quote)
    if not (S <= start and end <= E):
        problems.append("%s: 引文越出区间：%r" % (where, quote[:40]))
        return None
    if text[start:end] != quote:
        problems.append("%s: text[start:end] != quote：%r" % (where, quote[:40]))
        return None
    occurrences = text.count(quote)
    first = text.find(quote)
    return {
        "quote": quote,
        "start": start,
        "end": end,
        "sourceHash": C.SOURCE_HASH,
        "para": para,
        "wholeTextOccurrences": occurrences,
        "occurrencesInRange": text[S:E].count(quote),
        "startIsFirstOccurrence": first == start,
        "firstOccurrenceAt": first,
    }


def resolve_list(specs, where, field):
    out = []
    for i, sp in enumerate(specs or []):
        q = resolve(sp, "%s.%s[%d]" % (where, field, i))
        if q is not None:
            out.append(q)
    return out


# ── 1. tasks：五元组 + 每栏独立引文 ──────────────────────────────────────
FIELDS = ("objective", "obstacle", "action", "result", "cost")
tasks_out = []
null_fields = []
for t in C.TASKS:
    item = {"id": t["id"], "actor": t["actor"]}
    for f in FIELDS:
        val = t.get(f)
        item[f] = val
        item[f + "Basis"] = t.get(f + "Basis") if val is not None else None
        quotes = resolve_list(t.get(f + "Quotes") or [], t["id"], f + "Quotes")
        item[f + "Quotes"] = quotes
        note = t.get(f + "Note")
        if val is None:
            null_fields.append("%s.%s" % (t["id"], f))
            if not (isinstance(note, str) and note.strip()):
                problems.append("%s.%s 是 null 但没有写理由" % (t["id"], f))
        if val is not None and not quotes:
            problems.append("%s.%s 非空但没有引文" % (t["id"], f))
        item[f + "Note"] = note
    tasks_out.append(item)

# 五栏引文区间两两不相交（提示词点名的 714/1664 缺陷）
overlaps = []
for it in tasks_out:
    spans = []
    for f in FIELDS:
        for q in it[f + "Quotes"]:
            spans.append((f, q["start"], q["end"]))
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            f1, s1, e1 = spans[i]
            f2, s2, e2 = spans[j]
            if s1 < e2 and s2 < e1:
                overlaps.append("%s: %s[%d,%d) ∩ %s[%d,%d)" % (it["id"], f1, s1, e1, f2, s2, e2))
if overlaps:
    problems.extend("五栏引文区间重叠：" + o for o in overlaps)

# ── 2. causeEdges ────────────────────────────────────────────────────────
cause_out = []
for ce in C.CAUSE_EDGES:
    cause_out.append({
        "id": ce["id"],
        "from": ce["from"],
        "to": ce["to"],
        "mechanism": ce["mechanism"],
        "basis": ce["basis"],
        "quotes": resolve_list(ce["quotes"], ce["id"], "quotes"),
        "note": ce.get("note"),
    })

rejected_out = []
for re_ in C.REJECTED_EDGES:
    rejected_out.append({
        "id": re_["id"],
        "candidate": re_["candidate"],
        "whyNot": re_["whyNot"],
        "basis": re_["basis"],
        "quotes": resolve_list(re_["quotes"], re_["id"], "quotes"),
    })

# ── 3. states ────────────────────────────────────────────────────────────
states_out = []
for st in C.STATES:
    states_out.append({
        "id": st["id"],
        "who": st["who"],
        "before": st["before"],
        "beforeBasis": st["beforeBasis"],
        "beforeQuotes": resolve_list(st["beforeQuotes"], st["id"], "beforeQuotes"),
        "after": st["after"],
        "afterBasis": st["afterBasis"],
        "afterQuotes": resolve_list(st["afterQuotes"], st["id"], "afterQuotes"),
        "anchor": st["anchor"],
        "anchorBasis": st["anchorBasis"],
        "anchorQuotes": resolve_list(st["anchorQuotes"], st["id"], "anchorQuotes"),
        "note": st.get("note"),
    })

# ── 4. knowledgeGaps ─────────────────────────────────────────────────────
kg_out = []
for k in C.KNOWLEDGE_GAPS:
    kg_out.append({
        "id": k["id"],
        "proposition": k["proposition"],
        "knows": k["knows"],
        "doesNotKnow": k["doesNotKnow"],
        "unconfirmed": k.get("unconfirmed") or [],
        "basis": k["basis"],
        "quotes": resolve_list(k["quotes"], k["id"], "quotes"),
        "note": k.get("note"),
    })

# ── 5. foreshadows ───────────────────────────────────────────────────────
def resolve_fs(fs, where):
    return {
        "what": fs["what"],
        "quote": resolve_list(fs["quote"], where, "quote"),
        "basis": fs["basis"],
    }


fs_out = []
for f in C.FORESHADOWS:
    fs_out.append({
        "id": f["id"],
        "name": f["name"],
        "setup": resolve_fs(f["setup"], f["id"] + ".setup"),
        "payoff": resolve_fs(f["payoff"], f["id"] + ".payoff"),
        "status": f["status"],
        "unresolvedWhat": f.get("unresolvedWhat"),
        "basis": f["basis"],
        "note": f.get("note"),
    })
    if f["status"] == "unresolved":
        if not (isinstance(f.get("unresolvedWhat"), str) and f["unresolvedWhat"].strip()):
            problems.append("%s: unresolved 但没有写 unresolvedWhat" % f["id"])
        if f["payoff"]["quote"]:
            problems.append("%s: 标 unresolved 却给了回收引文" % f["id"])
    if not f["setup"]["quote"]:
        problems.append("%s: 伏笔没有铺设引文" % f["id"])

nf_out = []
for nf in C.NOT_FORESHADOWS:
    nf_out.append({
        "id": nf["id"],
        "candidate": nf["candidate"],
        "whyNot": nf["whyNot"],
        "basis": nf["basis"],
        "quotes": resolve_list(nf["quotes"], nf["id"], "quotes"),
    })

# ── 6. worldSettings（三态字段必须写进字段）──────────────────────────────
PLACE_STATES = {"arrived", "mentioned"}
ITEM_STATES = {"hold", "transfer", "use", "lose"}
INSTITUTIONS = {"declared", "executed", "misunderstood"}
ws_out = []
for w in C.WORLD_SETTINGS:
    item = {
        "id": w["id"],
        "kind": w["kind"],
        "name": w["name"],
        "quote": resolve(w["quote"], w["id"] + ".quote"),
        "extraQuotes": resolve_list(w.get("extraQuotes") or [], w["id"], "extraQuotes"),
        "explain": w["explain"],
        "basis": w["basis"],
    }
    if w["kind"] == "place":
        assert w["placeState"] in PLACE_STATES, w["id"]
        item["placeState"] = w["placeState"]
        item["placeStateNote"] = w.get("placeStateNote")
        if not (isinstance(item["placeStateNote"], str) and item["placeStateNote"].strip()):
            problems.append("%s: place 缺 placeStateNote" % w["id"])
    elif w["kind"] == "item":
        st = w.get("itemStates") or []
        assert st and set(st) <= ITEM_STATES, w["id"]
        item["itemStates"] = list(st)
        item["itemStateNotes"] = w.get("itemStateNotes") or {}
        item["itemStateNote"] = w.get("itemStateNote")
        missing_note = [s for s in st if not (item["itemStateNotes"].get(s) or "").strip()]
        if missing_note:
            problems.append("%s: 这些态没有单独说明：%s" % (w["id"], missing_note))
        if not (isinstance(item["itemStateNote"], str) and item["itemStateNote"].strip()):
            problems.append("%s: item 缺 itemStateNote（四态为何取/不取）" % w["id"])
    elif w["kind"] == "rule":
        assert w["institution"] in INSTITUTIONS, w["id"]
        item["institution"] = w["institution"]
        item["institutionNote"] = w.get("institutionNote")
        if not (isinstance(item["institutionNote"], str) and item["institutionNote"].strip()):
            problems.append("%s: rule 缺 institutionNote" % w["id"])
    else:
        problems.append("%s: 非法 kind %r" % (w["id"], w["kind"]))
    ws_out.append(item)

nw_out = []
for nw in C.NOT_WORLD_SETTINGS:
    nw_out.append({
        "id": nw["id"],
        "candidate": nw["candidate"],
        "whyNot": nw["whyNot"],
        "basis": nw["basis"],
        "quotes": resolve_list(nw["quotes"], nw["id"], "quotes"),
    })

# ── 7. themeReadings：三件齐全 ───────────────────────────────────────────
th_out = []
for t in C.THEME_READINGS:
    support = [{"text": s["text"], "quote": resolve(s["quote"], t["id"] + ".support")} for s in t["support"]]
    counter = [{"text": s["text"], "quote": resolve(s["quote"], t["id"] + ".counter")} for s in t["counter"]]
    if not support or not counter:
        problems.append("%s: themeReading 缺 support 或 counter" % t["id"])
    th_out.append({
        "id": t["id"],
        "perspective": t["perspective"],
        "support": support,
        "counter": counter,
        "basis": t["basis"],
        "note": t.get("note"),
    })

tn_out = []
for tn in C.TEXTUAL_NOTES:
    tn_out.append({
        "id": tn["id"],
        "what": tn["what"],
        "quote": resolve(tn["quote"], tn["id"] + ".quote"),
        "extraQuotes": resolve_list(tn.get("extraQuotes") or [], tn["id"], "extraQuotes"),
        "note": tn["note"],
        "basis": tn["basis"],
    })

un_out = []
for u in C.UNKNOWNS:
    un_out.append({
        "id": u["id"],
        "what": u["what"],
        "why": u["why"],
        "basis": u["basis"],
        "quotes": resolve_list(u["quotes"], u["id"], "quotes"),
    })

# ── 8. 覆盖度统计 ────────────────────────────────────────────────────────
all_quotes = []


def collect(obj):
    if isinstance(obj, dict):
        if set(obj.keys()) >= {"quote", "start", "end", "sourceHash"}:
            all_quotes.append(obj)
        for v in obj.values():
            collect(v)
    elif isinstance(obj, list):
        for v in obj:
            collect(v)


sections = {
    "tasks": tasks_out, "causeEdges": cause_out, "rejectedEdges": rejected_out,
    "states": states_out, "knowledgeGaps": kg_out, "foreshadows": fs_out,
    "notForeshadows": nf_out, "worldSettings": ws_out, "notWorldSettings": nw_out,
    "themeReadings": th_out, "textualNotes": tn_out, "unknowns": un_out,
}
for v in sections.values():
    collect(v)

intervals = sorted({(q["start"], q["end"]) for q in all_quotes})
union = set()
for s, e in intervals:
    union.update(range(s, e))
nonempty_paras = [i for i, p in enumerate(PARTS) if p.strip()]
covered_paras = set()
for q in all_quotes:
    for i in nonempty_paras:
        ps, pe = PARA_OFFSETS[i]
        if q["start"] < pe and ps < q["end"]:
            covered_paras.add(i)

cand = {
    "schemaVersion": "castline/read-candidate/1",
    "task": "read:dafeng:L3:0259",
    "agent": "w-dafeng-0",
    "role": "READER（原文精读工作者）",
    "book": "dafeng",
    "bookTitle": "大奉打更人",
    "lane": 3,
    "unitIndex": 259,
    "unitHead": "第三十章 预言师",
    "source": {
        "path": C.DOCS_PATH,
        "selector": "docs[0].text",
        "range": [S, E],
        "codepoints": E - S,
        "sourceHash": C.SOURCE_HASH,
        "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片的）",
        "sliceSha256": hashlib.sha256(slice_text.encode("utf-8")).hexdigest(),
        "sliceSha256Scope": "docs[0].text[%d:%d] 这一段切片的 sha256（额外字段，不覆盖 sourceHash）" % (S, E),
        "offsetCaliber": "start/end 均相对 docs[0].text 全文的 codepoint 偏移；自检：text[start:end] == quote 逐字成立",
        "boundaryHead": slice_text[:len("第三十章 预言师")],
        "boundaryHeadMatchesTitle": slice_text.startswith("第三十章 预言师"),
        "boundaryTail": slice_text[-40:],
        "nonEmptyParagraphs": len(nonempty_paras),
        "totalParagraphSlots": len(PARTS),
        "graphCachePath": C.GRAPH_PATH + "（摘要，仅用于对照已有结论，不作原文证据）",
    },
    "provenanceNote": C.PROVENANCE_NOTE,
    "semanticReview": "not-performed",
    "semanticReviewNote": (
        "**没有做独立语义评审**（semanticReview = not-performed）。本候选完成的是："
        "偏移由构建脚本现场 find 得出（构造性逐字命中）、机器自检五栏区间独立性、"
        "null 栏全部带理由、worldSettings 三态字段落盘、themeReadings 三件齐全、"
        "伏笔的铺设/回收分离。**定位正确不等于语义已核验**——"
        "每条断言的语义判断仍待独立复核（read-verify）另做一轮。"
    ),
    "basisLegend": {
        "explicit": "原文直述（叙述层或人物原话被明确标出说话人）",
        "inferred": "本候选的归纳（例如把人物的话读成他的动机）",
        "derived": "跨段推导（需要两句以上合起来才成立）",
        "unverified": "存疑：原文只给猜测/听说的形式，未被叙述确认",
    },
    "nullFieldRule": (
        "缺依据的栏写 null，并在同名 `<栏位>Note` 里写明为什么没有。"
        "本候选共 %d 个 null 栏：%s。"
        % (len(null_fields), " / ".join(null_fields))
    ),
    "speechAsClueNotFact": [
        "P8「我能感觉到，西方教要来了」——神殊的感知，不作「佛门已到」的事实（W10 记 mentioned）。",
        "P11「这么说，佛门的人过来兴师问罪了？」——带问号的推断，登记在 U13 而非因果图。",
        "P12「万一给西方的大光头发现神殊在我身体里」——条件句，不是已发生的事。",
        "P18「我只是一个残魂」——他拒绝时的自陈，不作能力判定（T02.obstacle 只记「他这么说」）。",
        "P110-P111「三千六百劫」「大气运」——钟璃口述的规则，记 misunderstood（W02）。",
        "P129「只有自己亲身挨过考验才行」——同上，且与监正实际出手救她构成张力（W04）。",
        "P134「喝了它，不必离京」——传音内容，其效果未被叙述确认（W05、U04）。",
        "P135「他果然知道神殊和尚在我身体了」——他自己的判断，记入 K02.unconfirmed。",
        "P65「那些糕点是五师姐托我买的，结果被你家妹妹吃了一大半」——她本人的主张，记入 U09。",
    ],
    "tasks": tasks_out,
    "causeEdges": cause_out,
    "rejectedEdges": rejected_out,
    "states": states_out,
    "knowledgeGaps": kg_out,
    "foreshadows": fs_out,
    "notForeshadows": nf_out,
    "worldSettings": ws_out,
    "notWorldSettings": nw_out,
    "themeReadings": th_out,
    "textualNotes": tn_out,
    "unknowns": un_out,
    "selfCritique": [
        {
            "id": sc["id"],
            "risk": sc["risk"],
            "whyStill": sc["whyStill"],
            "howToOverturn": sc["howToOverturn"],
        }
        for sc in C.SELF_CRITIQUE
    ],
    "selfCritiqueNote": (
        "六条自评，每条写成【风险 / 我为什么仍然这么判断 / 复核怎么改判】，"
        "其中 SC01、SC03、SC04、SC05、SC06 都直接给了可执行的改判路径（改哪个字段、改成什么）。"
        "没有写「本候选可能存在不足」这类套话。"
    ),
    "taskOrderNote": C.TASK_ORDER_NOTE,
    "machineSelfCheck": {
        "buildScript": "loop/state/out/read_dafeng_L3_0259.w-dafeng-0.build/build_candidate.py",
        "contentModule": "loop/state/out/read_dafeng_L3_0259.w-dafeng-0.build/content_0259.py",
        "verifyScript": "loop/state/out/read_dafeng_L3_0259.w-dafeng-0.build/verify_candidate.py",
        "reproduceCommand": (
            "python3 -B -s loop/state/out/read_dafeng_L3_0259.w-dafeng-0.build/build_candidate.py && "
            "python3 -B -s loop/state/out/read_dafeng_L3_0259.w-dafeng-0.build/verify_candidate.py"
        ),
        "quoteObjectsResolved": len(all_quotes),
        "uniqueQuoteIntervals": len(intervals),
        "resolveFailures": len(problems),
        "resolveFailureDetail": problems[:20],
        "taskFieldIntervalOverlap": len(overlaps),
        "nullFields": len(null_fields),
        "nullFieldList": null_fields,
        "requiredSections": ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"],
    },
    "coverage": {
        "sliceCodepoints": E - S,
        "nonSpaceCodepoints": sum(1 for ch in slice_text if not ch.isspace()),
        "quoteUnionCodepoints": len(union),
        "quoteUnionRatioOfSlice": round(len(union) / (E - S), 4),
        "quoteUnionRatioOfNonSpace": round(
            len(union) / max(1, sum(1 for ch in slice_text if not ch.isspace())), 4
        ),
        "quoteIntervals": [{"start": s, "end": e} for s, e in intervals],
        "paragraphs": len(nonempty_paras),
        "paragraphsTouchedByAtLeastOneQuote": len(covered_paras),
        "zeroCoveredParagraphs": [i for i in nonempty_paras if i not in covered_paras],
        "note": (
            "覆盖度只为让复核一眼看到哪些段没被引用，**不作为质量分**。"
            "未引用的段落主要是：标题行、作者的话（P143-P147）、隔断符、以及若干纯过场句。"
        ),
    },
}

if problems:
    print("构建自检失败，%d 项：" % len(problems), file=sys.stderr)
    for p in problems:
        print("  -", p, file=sys.stderr)
    sys.exit(1)

out_path.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("写出 %s" % out_path)
print("  引文对象 %d 个，唯一区间 %d 个，null 栏 %d 个" % (len(all_quotes), len(intervals), len(null_fields)))
print("  未覆盖非空段：%d / %d" % (len(cand["coverage"]["zeroCoveredParagraphs"]), len(nonempty_paras)))
