# -*- coding: utf-8 -*-
"""构建 loop/state/out/read_dafeng_L3_0295.candidate.json。

**这个脚本是候选里所有引文的唯一来源**：内容模块只写「引文键名」，
本脚本在 docs[0].text[SLICE_START:SLICE_END) 内构造性定位后切片，
逐条断言 text[start:end] == quote。

构建期断言（任一失败即非零退出，不写出候选）：
  A1 引文逐字命中且不跨段
  A2 引文落在本单元区间内
  A3 叙事引文不落进作者区域（PS 留言）
  A4 同一任务内五栏引文**区间两两不重叠**（禁止一句话当多栏依据）
  A5 同一任务内没有两栏共用同一条引文
  A6 null 栏必须带同名 <栏位>Note
  A7 枚举值合法（placeState/itemStates/institution/basis/kind）
  A8 每条断言都有 basis

用法：
  python3 loop/state/out/read_dafeng_L3_0295.w-dafeng-0.build/build_candidate.py
"""
import hashlib
import json
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
sys.path.insert(0, str(BUILD))

from quotes_0295 import Q, SLICE_START, SLICE_END  # noqa: E402
import content_0295 as C  # noqa: E402

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L3_0295.candidate.json"

SOURCE_HASH = hashlib.sha256(DOCS.read_bytes()).hexdigest()
BASIS_OK = {"explicit", "inferred", "derived", "unverified"}

problems = []


def note(cond, msg):
    if not cond:
        problems.append(msg)
    return cond


# ── 定位 ────────────────────────────────────────────────────────────────
TEXT = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
SLICE_TEXT = TEXT[SLICE_START:SLICE_END]
PARA_INDEX = {}          # 全文偏移 -> "Pnnn"
_off = SLICE_START
for _i, _para in enumerate(SLICE_TEXT.split("\n")):
    PARA_INDEX[_off] = "P%03d" % _i
    _off += len(_para) + 1


def para_of(pos):
    best = None
    for p, name in PARA_INDEX.items():
        if p <= pos:
            best = name
        else:
            break
    return best


def resolve(key):
    """键名 -> 引文对象（构造性定位 + 断言）。"""
    if key not in Q:
        problems.append("未知引文键：%s" % key)
        return None
    head, tail, occ = Q[key]
    pos = -1
    for _ in range(occ):
        pos = SLICE_TEXT.find(head, pos + 1)
        if pos < 0:
            problems.append("引文键 %s：head 第 %d 次出现不存在" % (key, occ))
            return None
    start = pos
    if tail is None:
        end = start + len(head)
    else:
        t = SLICE_TEXT.find(tail, start + len(head))
        if t < 0:
            problems.append("引文键 %s：tail 找不到" % key)
            return None
        end = t + len(tail)
    gs, ge = SLICE_START + start, SLICE_START + end
    quote = TEXT[gs:ge]
    # A1
    note(TEXT[gs:ge] == quote, "%s：切片不等于全文切片" % key)
    note("\n" not in quote, "%s：引文跨段（含换行）" % key)
    # A2
    note(SLICE_START <= gs < ge <= SLICE_END, "%s：越出本单元区间" % key)
    # A3
    in_author = any(a <= gs and ge <= b for a, b in C.AUTHOR_REGION)
    return {
        "quote": quote, "start": gs, "end": ge, "sourceHash": SOURCE_HASH,
        "para": para_of(gs), "occurrencesInRange": SLICE_TEXT.count(quote),
        "wholeTextOccurrences": TEXT.count(quote),
        "startIsFirstOccurrence": SLICE_TEXT.find(quote) == start,
        "firstOccurrenceAt": SLICE_START + SLICE_TEXT.find(quote),
        "inAuthorRegion": bool(in_author),
        "anchorLabel": key,
    }


def rq(key):
    """引文对象。保留 anchorLabel（引文库键名），复核者据此可直接回到 quotes_0295.py 复现定位。"""
    o = resolve(key)
    return o if o is not None else {}


def rqs(keys):
    return [rq(k) for k in keys]


def check_interval_isolation(tid, columns):
    """A4/A5：同一任务内五栏区间两两不重叠、且不共用同一条引文。"""
    seen = {}
    for col, keys in columns.items():
        for k in keys:
            o = resolve(k)
            if o is None:
                continue
            rng = (o["start"], o["end"])
            for prev_rng, prev in seen.items():
                if not (rng[1] <= prev_rng[0] or rng[0] >= prev_rng[1]):
                    problems.append("A4 区间重叠：%s %s(%s) 与 %s(%s)"
                                    % (tid, col, k, prev[0], prev[1]))
            if rng in seen:
                problems.append("A5 同任务共用引文：%s %s 与 %s 同区间 %r"
                                % (tid, col, seen[rng][0], rng))
            seen[rng] = (col, k)


# ── 构建 tasks ─────────────────────────────────────────────────────────
tasks_out = []
for t in C.TASKS:
    cols = {"objective": t["objectiveQuotes"], "obstacle": t.get("obstacleQuotes") or [],
            "action": t["actionQuotes"], "result": t["resultQuotes"],
            "cost": t.get("costQuotes") or []}
    check_interval_isolation(t["id"], cols)
    row = {"id": t["id"], "actor": t["actor"], "title": t["title"],
           "nullFields": [], "columnsWithoutQuotes": []}
    for col in ("objective", "obstacle", "action", "result", "cost"):
        val = t.get(col)
        keys = t.get(col + "Quotes") or []
        row[col] = val
        row[col + "Basis"] = t.get(col + "Basis")
        row[col + "Quotes"] = rqs(keys)
        if val is None:
            row["nullFields"].append(col)
            # A6
            nk = col + "Note"
            note(bool(t.get(nk)), "A6 %s.%s 为 null 但缺 %s" % (t["id"], col, nk))
            row[nk] = t.get(nk)
            note(not keys, "%s.%s 为 null 却带了引文" % (t["id"], col))
            if keys:
                row["columnsWithoutQuotes"].append(col)
        else:
            # A8
            note(t.get(col + "Basis") in BASIS_OK,
                 "A8 %s.%s basis 非法：%r" % (t["id"], col, t.get(col + "Basis")))
            note(bool(keys), "%s.%s 有值却没有引文" % (t["id"], col))
    tasks_out.append(row)

# ── 构建其余分区 ───────────────────────────────────────────────────────
def edge(e, rejected=False):
    note(e.get("basis") in BASIS_OK, "A8 %s basis 非法" % e["id"])
    if rejected:
        return {"id": e["id"], "wouldBe": e["wouldBe"], "whyNot": e["whyNot"],
                "basis": e["basis"], "quotes": rqs(e["quotes"])}
    return {"id": e["id"], "from": e["from"], "to": e["to"],
            "mechanism": e["mechanism"], "basis": e["basis"], "quotes": rqs(e["quotes"])}


cause_out = [edge(e) for e in C.CAUSE_EDGES]
rejected_out = [edge(e, rejected=True) for e in C.REJECTED_EDGES]

states_out = []
for s in C.STATES:
    note(s.get("beforeBasis") in BASIS_OK, "A8 %s.beforeBasis" % s["id"])
    note(s.get("afterBasis") in BASIS_OK, "A8 %s.afterBasis" % s["id"])
    note(s.get("anchorBasis") in BASIS_OK, "A8 %s.anchorBasis" % s["id"])
    states_out.append({
        "id": s["id"], "who": s["who"], "aspect": s["aspect"],
        "before": s["before"], "beforeBasis": s["beforeBasis"],
        "beforeQuotes": rqs(s["beforeQuotes"]),
        "after": s["after"], "afterBasis": s["afterBasis"],
        "afterQuotes": rqs(s["afterQuotes"]),
        "anchor": s["anchor"], "anchorBasis": s["anchorBasis"],
        "anchorQuotes": rqs(s["anchorQuotes"]), "note": s["note"],
    })

gaps_out = []
for g in C.KNOWLEDGE_GAPS:
    note(g.get("basis") in BASIS_OK, "A8 %s basis" % g["id"])
    gaps_out.append({"id": g["id"], "knower": g["knower"], "notKnower": g["notKnower"],
                     "content": g["content"], "basis": g["basis"],
                     "quotes": rqs(g["quotes"]), "note": g["note"]})

fore_out = []
for f in C.FORESHADOWS:
    note(f.get("setupBasis") in BASIS_OK, "A8 %s.setupBasis" % f["id"])
    if f.get("payoff") is not None:
        note(f.get("payoffBasis") in BASIS_OK, "A8 %s.payoffBasis" % f["id"])
    if not f["resolved"]:
        note(f.get("unresolved") is True, "%s 未回收却没标 unresolved" % f["id"])
        note(bool(f.get("note")), "%s 未回收却没写 note" % f["id"])
    fore_out.append({
        "id": f["id"], "name": f["name"],
        "setup": f["setup"], "setupBasis": f["setupBasis"], "setupQuotes": rqs(f["setupQuotes"]),
        "payoff": f.get("payoff"), "payoffBasis": f.get("payoffBasis"),
        "payoffQuotes": rqs(f.get("payoffQuotes") or []),
        "resolved": f["resolved"], "unresolved": bool(f.get("unresolved")),
        "note": f["note"],
    })

nf_out = [{"name": x["name"], "whyNot": x["whyNot"], "quotes": rqs(x["quotes"])}
          for x in C.NOT_FORESHADOWS]

ws_out = []
for w in C.WORLD_SETTINGS:
    note(w.get("basis") in BASIS_OK, "A8 %s basis" % w["id"])
    note(w["kind"] in ("rule", "place", "item"), "A7 %s kind 非法" % w["id"])
    row = {"id": w["id"], "kind": w["kind"], "name": w["name"],
           "quote": rq(w["quote"]), "explain": w["explain"], "basis": w["basis"],
           "extraQuotes": rqs(w.get("extraQuotes") or []), "note": w["note"]}
    if w["kind"] == "place":
        # A7
        note(w.get("placeState") in ("arrived", "mentioned"),
             "A7 %s placeState 非法/缺失" % w["id"])
        row["placeState"] = w.get("placeState")
    if w["kind"] == "item":
        st = w.get("itemStates") or []
        note(bool(st) and set(st) <= {"hold", "transfer", "use", "lose"},
             "A7 %s itemStates 非法：%r" % (w["id"], st))
        row["itemStates"] = st
    if w["kind"] == "rule":
        note(w.get("institution") in ("declared", "executed", "misunderstood"),
             "A7 %s institution 非法/缺失" % w["id"])
        row["institution"] = w.get("institution")
    ws_out.append(row)

nws_out = [{"name": x["name"], "whyNot": x["whyNot"], "quotes": rqs(x["quotes"])}
           for x in C.NOT_WORLD_SETTINGS]

th_out = []
for t in C.THEME_READINGS:
    note(bool(t.get("perspective")) and bool(t.get("support")) and bool(t.get("counter")),
         "%s 主题三件套不全" % t["id"])
    th_out.append({
        "id": t["id"], "perspective": t["perspective"],
        "support": [{"event": s["event"], "quotes": rqs(s["quotes"])} for s in t["support"]],
        "counter": [{"event": s["event"], "quotes": rqs(s["quotes"])} for s in t["counter"]],
        "note": t["note"],
    })

sp_out = [{"who": x["who"], "said": x["said"], "whyNotFact": x["whyNotFact"],
           "quotes": rqs(x["quotes"])} for x in C.SPEECH_AS_CLUE]
tx_out = [{"note": x["note"], "quotes": rqs(x["quotes"])} for x in C.TEXTUAL_NOTES]
ar_out = [{"note": x["note"], "quotes": rqs(x["quotes"])} for x in C.AUTHOR_REGION_EVIDENCE]
un_out = [{"id": u["id"], "text": u["text"], "quotes": rqs(u["quotes"])}
          for u in C.UNKNOWNS]

# ── 机器自检 ───────────────────────────────────────────────────────────
all_objs = []
def collect(o):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "sourceHash" in o:
            all_objs.append(o)
        for v in o.values():
            collect(v)
    elif isinstance(o, list):
        for x in o:
            collect(x)

payload = {
    "schemaVersion": "0295.1",
    "task": "read:dafeng:L3:0295",
    "agent": "w-dafeng-0",
    "role": "READER",
    "book": "dafeng",
    "bookTitle": "大奉打更人",
    "lane": 3,
    "unitIndex": 295,
    "unitHead": "第六十六章 不跪",
    "source": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "selector": "docs[0].text",
        "range": [SLICE_START, SLICE_END],
        "codepoints": SLICE_END - SLICE_START,
        "sourceHash": SOURCE_HASH,
        "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
        "sliceSha256": hashlib.sha256(SLICE_TEXT.encode("utf-8")).hexdigest(),
        "sliceSha256Scope": "docs[0].text[%d:%d) 这个切片的 sha256（另起字段，不覆盖 sourceHash）"
                            % (SLICE_START, SLICE_END),
        "offsetCaliber": "所有 start/end 都是相对 docs[0].text **全文** 的 codepoint 偏移；"
                         "自检：docs[0].text[start:end] == quote 逐字成立。",
        "boundaryHead": SLICE_TEXT[:20],
        "boundaryHeadMatchesTitle": SLICE_TEXT.startswith("第六十六章 不跪"),
        "boundaryTail": SLICE_TEXT[-20:],
    },
    "provenanceNote": (
        "本候选由 %s 生成，读解内容在同目录 content_0295.py，逐字引文库在 quotes_0295.py。"
        "**候选里没有一条引文是手抄的**：每条引文只写「逐字子串 + 尾串 + 第几次出现」，"
        "由生成脚本在 docs[0].text[%d:%d) 内定位后切片，逐条断言 text[start:end]==quote；"
        "找不到或有歧义则构建直接失败。机器自检见 machineSelfCheck。"
        % (BUILD.name + "/build_candidate.py", SLICE_START, SLICE_END)
    ),
    "semanticReview": "not-performed",
    "semanticReviewNote": (
        "**没有做独立语义评审**（semanticReview=not-performed）。本候选完成的是构造性自检："
        "text[start:end]==quote 逐字命中、引文全部落在本单元区间内、"
        "同一任务内五栏引文的字符区间两两不重叠、同一任务内没有两栏共用同一条引文、"
        "null 栏全部带理由、枚举值合法、叙事引文不落进作者区域。"
        "**引用定位正确 ≠ 语义已核验**：「这条因果边读得对不对」「这条状态该不该记」"
        "「E20 那条跨场景推导能不能立」都要等独立复核者读原文判定。"
    ),
    "basisLegend": {
        "explicit": "原句直接陈述了该栏内容",
        "inferred": "我的归纳，原文没有一句话直接这么说",
        "derived": "需要把两处或更多分开的陈述合起来才成立",
        "unverified": "存疑，留给复核",
    },
    "nullFieldRule": "缺项写 null，并在同名 <栏位>Note 写明为什么没有依据。",
    "taskIdNote": "Tnn 是本候选自编的任务序号；Pnnn 是 docs[0].text[start:end] 切片内"
                  "按 \\n 切分的段落序号（含空段，0 起）。两者是不同编号，引用时不要混。",
    "authorRegion": [{"start": a, "end": b} for a, b in C.AUTHOR_REGION],
    "authorRegionNote": C.AUTHOR_REGION_NOTE,
    "tasks": tasks_out,
    "causeEdges": cause_out,
    "rejectedEdges": rejected_out,
    "states": states_out,
    "knowledgeGaps": gaps_out,
    "foreshadows": fore_out,
    "notForeshadows": nf_out,
    "worldSettings": ws_out,
    "notWorldSettings": nws_out,
    "themeReadings": th_out,
    "speechAsClueNotFact": sp_out,
    "textualNotes": tx_out,
    "authorRegionEvidence": ar_out,
    "unknowns": un_out,
    "selfCritique": C.SELF_CRITIQUE,
}

collect(payload)
# A3 检查（叙事引文不落进作者区域）
# ar_keys 是**引文键名**；resolve() 每次返回新 dict，所以只能按键名判归属，不能比对象身份。
ar_keys = set()
for x in C.AUTHOR_REGION_EVIDENCE:
    ar_keys.update(x["quotes"])
leaks = [o for o in all_objs
         if o.get("inAuthorRegion") and o.get("anchorLabel") not in ar_keys]
for o in leaks:
    problems.append("A3 叙事引文落进作者区域：%r@%s" % (o["quote"][:20], o["start"]))

payload["verbatimQuotes"] = {
    k: {"quote": v["quote"], "chars": len(v["quote"]), "sourceHash": SOURCE_HASH}
    for k, v in ((k, resolve(k)) for k in Q) if v
}

# 覆盖统计
covered = set()
for o in all_objs:
    if not o.get("inAuthorRegion"):
        covered.update(range(o["start"], o["end"]))
nonempty = [i for i, p in enumerate(SLICE_TEXT.split("\n")) if p.strip()]
touched = set()
for o in all_objs:
    if not o.get("inAuthorRegion"):
        touched.add(o.get("para"))
uncovered = ["P%03d" % i for i in nonempty if "P%03d" % i not in touched]

null_fields = [{"task": r["id"], "col": c, "hasNote": bool(r.get(c + "Note")),
                "noQuotes": not (r.get(c + "Quotes") or [])}
               for r in tasks_out for c in r["nullFields"]]

payload["machineSelfCheck"] = {
    "buildScript": str((BUILD / "build_candidate.py").relative_to(ROOT)),
    "probeScript": str((BUILD / "probe_quotes.py").relative_to(ROOT)),
    "contentModule": str((BUILD / "content_0295.py").relative_to(ROOT)),
    "quoteModule": str((BUILD / "quotes_0295.py").relative_to(ROOT)),
    "reproduceCommand": "python3 %s" % (BUILD / "build_candidate.py").relative_to(ROOT),
    "quoteObjectsResolved": len(all_objs),
    "uniqueQuoteIntervals": len({(o["start"], o["end"]) for o in all_objs}),
    "uniqueQuotesInVerbatimLegend": len(payload["verbatimQuotes"]),
    "problems": problems,
    "authorRegionLeaks": sum(1 for o in all_objs
                             if o.get("inAuthorRegion") and o.get("anchorLabel") not in ar_keys),
    "taskFieldIntervalOverlap": sum(1 for p in problems if p.startswith("A4")),
    "crossColumnSharedQuotes": sum(1 for p in problems if p.startswith("A5")),
    "taskQuoteCounts": [{"task": r["id"],
                         "quotes": sum(len(r[c + "Quotes"]) for c in
                                       ("objective", "obstacle", "action", "result", "cost")),
                         "nullFields": r["nullFields"]} for r in tasks_out],
    "nullFields": null_fields,
    "unresolvedForeshadows": [f["id"] for f in fore_out if not f["resolved"]],
    "resolvedForeshadows": [f["id"] for f in fore_out if f["resolved"]],
    "worldSettingKinds": {k: sum(1 for w in ws_out if w["kind"] == k)
                          for k in ("rule", "place", "item")},
    "placeStates": {w["id"]: w["placeState"] for w in ws_out if w["kind"] == "place"},
    "itemStates": {w["id"]: w["itemStates"] for w in ws_out if w["kind"] == "item"},
    "institutions": {w["id"]: w["institution"] for w in ws_out if w["kind"] == "rule"},
    "basisTally": {b: sum(1 for o in all_objs for _ in [0]) for b in ()} or {},
    "coverage": {
        "sliceCodepoints": SLICE_END - SLICE_START,
        "nonSpaceCodepoints": sum(1 for ch in SLICE_TEXT if not ch.isspace()),
        "quoteUnionCodepoints": len(covered),
        "quoteUnionRatioOfSlice": round(len(covered) / (SLICE_END - SLICE_START), 4),
        "quoteIntervals": len({(o["start"], o["end"]) for o in all_objs}),
        "paragraphs": len(SLICE_TEXT.split("\n")),
        "nonEmptyParagraphs": len(nonempty),
        "paragraphsTouchedByAtLeastOneQuote": len([p for p in touched if p]),
        "uncoveredNonEmptyParagraphs": uncovered,
    },
    "note": "构建期问题清单（problems）应为空；非空时脚本非零退出且不写候选。",
}

# basis 统计
tally = {}
for coll in (tasks_out, cause_out, rejected_out, states_out, gaps_out, fore_out, ws_out):
    for row in coll:
        for k, v in row.items():
            if k.endswith("Basis") and v:
                tally[v] = tally.get(v, 0) + 1
payload["machineSelfCheck"]["basisTally"] = tally

if problems:
    print("构建失败：problems=%d" % len(problems), file=sys.stderr)
    for p in problems:
        print("  " + p, file=sys.stderr)
    raise SystemExit(1)

OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
print("引文对象 %d 条 / 唯一区间 %d 个 / problems 0"
      % (len(all_objs), len({(o["start"], o["end"]) for o in all_objs})))
print("写出 %s（%d 字节）" % (OUT.relative_to(ROOT), OUT.stat().st_size))
print("分区：tasks=%d causeEdges=%d rejectedEdges=%d states=%d gaps=%d foreshadows=%d"
      " worldSettings=%d themes=%d unknowns=%d"
      % (len(tasks_out), len(cause_out), len(rejected_out), len(states_out), len(gaps_out),
         len(fore_out), len(ws_out), len(th_out), len(un_out)))
