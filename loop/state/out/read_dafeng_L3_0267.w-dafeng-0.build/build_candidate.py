# -*- coding: utf-8 -*-
"""构建 read:dafeng:L3:0267 候选。

设计原则（防我自己手滑）：
  1. **偏移一律现场解析**：内容模块只写引文子串，本脚本用
     `docs[0].text.find(quote)` 求 start/end；找不到就**抛错**，绝不回退到手填。
  2. **逐条自检 find**：每条引文都断言 `text[start:end] == quote`。
  3. **五栏独立性**：对每条 task，检查 objective/obstacle/action/result/cost
     五栏的引文区间两两不相交（同一句话不得当多栏依据）。
  4. **null 栏必须有 Note**：null 栏的 `<栏位>Note` 必须非空。
  5. **区间约束**：任何引文都必须落在 [1119820,1125007) 内。

跑法：
  python3 -B -s loop/state/out/read_dafeng_L3_0267.w-dafeng-0.build/build_candidate.py
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 1119820, 1125007
OUT = ROOT / "loop/state/out/read_dafeng_L3_0267.candidate.json"
HERE = Path(__file__).resolve().parent

FAIL = []


def load_docs():
    d = json.loads(DOCS.read_text(encoding="utf-8"))
    return d[0]["text"]


TEXT = load_docs()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ref(quote: str, where: str) -> dict:
    """把一个引文字符串解析成带偏移的引文对象。解析失败即记 FAIL。"""
    if not isinstance(quote, str) or not quote:
        FAIL.append("%s：空引文" % where)
        return {}
    first = TEXT.find(quote)
    if first < 0:
        FAIL.append("%s：find 失败（逐字不命中）：%r" % (where, quote[:60]))
        return {}
    if TEXT.find(quote, first + 1) >= 0:
        whole = TEXT.count(quote)
    else:
        whole = 1
    s, e = first, first + len(quote)
    if not (START <= s and e <= END):
        FAIL.append("%s：引文越界 [%d,%d) 不在 [%d,%d)：%r"
                    % (where, s, e, START, END, quote[:40]))
        return {}
    if TEXT[s:e] != quote:
        FAIL.append("%s：自检失败 text[s:e] != quote" % where)
        return {}
    in_range = 0
    pos = TEXT.find(quote)
    while pos >= 0:
        if START <= pos and pos + len(quote) <= END:
            in_range += 1
        pos = TEXT.find(quote, pos + 1)
    return {
        "quote": quote,
        "start": s,
        "end": e,
        "sourceHash": SOURCE_HASH,
        "wholeTextOccurrences": whole,
        "occurrencesInRange": in_range,
        "startIsFirstOccurrence": first == TEXT.find(quote),
    }


def refs(quotes, where):
    return [ref(q, "%s[%d]" % (where, i)) for i, q in enumerate(quotes)]


def load_content():
    spec = importlib.util.spec_from_file_location("content_0267", HERE / "content_0267.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ────────────────────────── tasks ──────────────────────────
SLOTS = ("objective", "obstacle", "action", "result", "cost")


def build_tasks(C):
    out = []
    for spec in C.TASK_SPECS:
        t = {"id": spec["id"], "actor": spec["actor"]}
        intervals = []
        for slot in SLOTS:
            cell = spec[slot]
            qs = refs(cell.get("quotes") or [], "%s.%s" % (spec["id"], slot))
            t[slot] = cell.get("text")
            t[slot + "Basis"] = cell.get("basis")
            t[slot + "Quotes"] = [q for q in qs if q]
            t[slot + "Note"] = cell.get("note")
            # 逐栏约束
            if cell.get("text") is None:
                if cell.get("basis") is not None:
                    FAIL.append("%s.%s：text=null 但 basis 非空" % (spec["id"], slot))
                if not cell.get("note"):
                    FAIL.append("%s.%s：null 栏没有 Note（判为未标注的未知）"
                                % (spec["id"], slot))
                if cell.get("quotes"):
                    FAIL.append("%s.%s：text=null 却带了引文" % (spec["id"], slot))
            else:
                if cell.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
                    FAIL.append("%s.%s：basis 非法 %r" % (spec["id"], slot, cell.get("basis")))
                if not cell.get("quotes"):
                    FAIL.append("%s.%s：非 null 栏没有引文" % (spec["id"], slot))
                if not cell.get("note"):
                    FAIL.append("%s.%s：非 null 栏没有 Note" % (spec["id"], slot))
            for q in t[slot + "Quotes"]:
                intervals.append((q["start"], q["end"], slot))
        # 五栏区间两两不相交
        for i in range(len(intervals)):
            for j in range(i + 1, len(intervals)):
                a, b = intervals[i], intervals[j]
                if a[2] == b[2]:
                    continue
                if a[0] < b[1] and b[0] < a[1]:
                    FAIL.append("%s：五栏共用同一句（%s 与 %s 区间重叠 [%d,%d)/[%d,%d)）"
                                % (spec["id"], a[2], b[2], a[0], a[1], b[0], b[1]))
        t["fiveSlotIntervalsDisjoint"] = not any(
            "五栏共用同一句" in f and f.startswith(spec["id"] + "：") for f in FAIL
        )
        out.append(t)
    return out


# ────────────────────────── causeEdges ──────────────────────────
def build_cause(C):
    out = []
    for spec in C.CAUSE_SPECS:
        qs = refs(spec["quotes"], "cause." + spec["id"])
        out.append({
            "id": spec["id"],
            "from": spec["from"],
            "to": spec["to"],
            "trigger": spec["trigger"],
            "mechanism": spec["mechanism"],
            "basis": spec["basis"],
            "quotes": qs,
        })
    return out


def build_rejected(C):
    out = []
    for spec in C.REJECTED_EDGE_SPECS:
        out.append({
            "id": spec["id"],
            "tempting": spec["tempting"],
            "verdict": spec["verdict"],
            "quotes": refs(spec["quotes"], "rejected." + spec["id"]),
        })
    return out


def build_speech(C):
    return [{
        "id": s["id"], "speaker": s["speaker"],
        "quote": ref(s["quote"], "speech." + s["id"]),
        "whatItIs": s["whatItIs"], "whyNotFact": s["whyNotFact"],
    } for s in C.SPEECH_SPECS]


def build_states(C):
    out = []
    for s in C.STATE_SPECS:
        out.append({
            "id": s["id"], "who": s["who"],
            "before": s["before"], "beforeBasis": s["beforeBasis"],
            "beforeQuotes": refs(s["beforeQuotes"], "state.%s.before" % s["id"]),
            "after": s["after"], "afterBasis": s["afterBasis"],
            "afterQuotes": refs(s["afterQuotes"], "state.%s.after" % s["id"]),
            "anchor": s["anchor"], "anchorBasis": s["anchorBasis"],
            "anchorQuotes": refs(s["anchorQuotes"], "state.%s.anchor" % s["id"]),
            "note": s["note"],
        })
    return out


def build_knowledge(C):
    return [{
        "id": k["id"], "proposition": k["proposition"],
        "knows": k["knows"], "doesNotKnow": k["doesNotKnow"],
        "unconfirmed": k["unconfirmed"], "basis": k["basis"],
        "quotes": refs(k["quotes"], "knowledge." + k["id"]),
        "note": k["note"],
    } for k in C.KNOWLEDGE_SPECS]


def build_foreshadows(C):
    out = []
    for f in C.FORESHADOW_SPECS:
        out.append({
            "id": f["id"], "name": f["name"],
            "setup": {
                "what": f["setup"]["what"],
                "quote": refs(f["setup"]["quote"], "foreshadow.%s.setup" % f["id"]),
                "basis": f["setup"]["basis"],
            },
            "payoff": f["payoff"],
            "status": f["status"],
            "unresolvedWhat": f["unresolvedWhat"],
            "basis": f["basis"],
            "note": f["note"],
        })
        if f["status"] == "unresolved" and not f.get("unresolvedWhat"):
            FAIL.append("%s：unresolved 却没写 unresolvedWhat" % f["id"])
    return out


def build_not_foreshadows(C):
    return [{
        "id": n["id"], "what": n["what"], "why": n["why"],
        "quote": refs(n["quote"], "notForeshadow." + n["id"]),
    } for n in C.NOT_FORESHADOW_SPECS]


def build_world(C):
    out = []
    for w in C.WORLD_SPECS:
        item = {
            "id": w["id"], "kind": w["kind"], "name": w["name"],
            "quote": ref(w["quote"], "world.%s.quote" % w["id"]),
            "extraQuotes": refs(w.get("extraQuotes") or [], "world.%s.extra" % w["id"]),
            "explain": w["explain"],
            "basis": w["basis"],
        }
        if w["kind"] == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                FAIL.append("%s：place 缺合法 placeState" % w["id"])
            item["placeState"] = w.get("placeState")
            item["placeStateNote"] = w.get("placeStateNote")
            if not w.get("placeStateNote"):
                FAIL.append("%s：place 没有 placeStateNote" % w["id"])
        elif w["kind"] == "item":
            st = w.get("itemStates") or []
            if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                FAIL.append("%s：itemStates 非法 %r" % (w["id"], st))
            item["itemStates"] = st
            item["itemStatesNote"] = w.get("itemStatesNote")
            if not w.get("itemStatesNote"):
                FAIL.append("%s：item 没有 itemStatesNote" % w["id"])
        elif w["kind"] == "rule":
            if w.get("institution") not in ("declared", "executed", "misunderstood"):
                FAIL.append("%s：rule 缺合法 institution" % w["id"])
            item["institution"] = w.get("institution")
            item["institutionNote"] = w.get("institutionNote")
            if not w.get("institutionNote"):
                FAIL.append("%s：rule 没有 institutionNote" % w["id"])
        else:
            FAIL.append("%s：kind 非法 %r" % (w["id"], w["kind"]))
        if not item["quote"]:
            FAIL.append("%s：主引文解析失败" % w["id"])
        out.append(item)
    return out


def build_not_world(C):
    return [{
        "id": n["id"], "what": n["what"], "why": n["why"],
        "quote": refs(n["quote"], "notWorld." + n["id"]),
    } for n in C.NOT_WORLD_SETTING_SPECS]


def build_themes(C):
    out = []
    for t in C.THEME_SPECS:
        sup = [{"text": s["text"],
                "quote": ref(s["quote"], "theme.%s.support" % t["id"])} for s in t["support"]]
        cnt = [{"text": s["text"],
                "quote": ref(s["quote"], "theme.%s.counter" % t["id"])} for s in t["counter"]]
        out.append({
            "id": t["id"], "perspective": t["perspective"],
            "support": sup, "counter": cnt, "note": t["note"],
        })
        if not sup:
            FAIL.append("%s：主题没有 support" % t["id"])
        if not cnt:
            FAIL.append("%s：主题没有 counter（只列支持的那叫论证）" % t["id"])
    return out


def build_textual(C):
    return [{
        "id": n["id"], "what": n["what"], "note": n["note"],
        "quote": refs(n["quote"], "textual." + n["id"]),
    } for n in C.TEXTUAL_NOTE_SPECS]


def build_unknowns(C):
    return [{
        "id": u["id"], "what": u["what"], "why": u["why"],
        "quote": refs(u["quote"], "unknown." + u["id"]),
    } for u in C.UNKNOWN_SPECS]


def build_self_critique(C):
    return [{
        "id": s["id"], "risk": s["risk"], "why": s["why"],
        "howToChange": s["howToChange"],
    } for s in C.SELF_CRITIQUE_SPECS]


def build_not_tasks(C):
    return [{
        "id": n["id"], "what": n["what"], "why": n["why"],
        "quote": refs(n["quote"], "notTask." + n["id"]),
    } for n in C.NOT_TASK_SPECS]


def collect_quote_objects(obj, acc):
    if isinstance(obj, dict):
        if "quote" in obj and "start" in obj and "end" in obj:
            acc.append(obj)
        for v in obj.values():
            collect_quote_objects(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            collect_quote_objects(v, acc)


def coverage(cand):
    acc = []
    collect_quote_objects(cand, acc)
    ivs = sorted({(q["start"], q["end"]) for q in acc})
    merged = []
    for s, e in ivs:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    union = sum(e - s for s, e in merged)
    seg = TEXT[START:END]
    nonspace = sum(1 for ch in seg if not ch.isspace())
    paras = [p for p in seg.split("\n\n") if p.strip()]
    touched = set()
    for i, p in enumerate(paras):
        ps = seg.find(p)
        # 段落绝对区间按出现顺序累计
    # 更稳的段落统计：按逐行扫描重建
    para_bounds = []
    pos = START
    for line in seg.split("\n"):
        pass
    # 简化：直接统计被任一引文覆盖到的非空行
    lines = []
    p = START
    for line in seg.split("\n"):
        if line.strip():
            lines.append((p, p + len(line)))
        p += len(line) + 1
    for s, e in merged:
        for ls, le in lines:
            if s < le and ls < e:
                touched.add((ls, le))
    return {
        "sliceCodepoints": END - START,
        "nonSpaceCodepoints": nonspace,
        "quoteObjects": len(acc),
        "quoteIntervals": len(ivs),
        "mergedIntervals": len(merged),
        "quoteUnionCodepoints": union,
        "quoteUnionRatioOfSlice": round(union / float(END - START), 4),
        "quoteUnionRatioOfNonSpace": round(union / float(nonspace), 4),
        "nonEmptyLines": len(lines),
        "nonEmptyLinesTouchedByAtLeastOneQuote": len(touched),
    }


def main():
    C = load_content()
    cand = {
        "schemaVersion": "castline/read-candidate/1",
        "task": "read:dafeng:L3:0267",
        "agent": "w-dafeng-0",
        "role": "READER（原文精读工作者）",
        "book": "dafeng",
        "bookTitle": "大奉打更人",
        "lane": 3,
        "unitIndex": 267,
        "unitHead": "第三十八章 五号的传书",
        "source": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
            "selector": "docs[0].text",
            "range": [START, END],
            "codepoints": END - START,
            "sourceHash": SOURCE_HASH,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
        },
        "provenanceNote": (
            "本候选由 loop/state/out/read_dafeng_L3_0267.w-dafeng-0.build/build_candidate.py 生成，"
            "内容模块是同目录的 content_0267.py。所有引文偏移都由构建脚本现场 "
            "`docs[0].text.find(quote)` 解析，解析不到即抛错——没有任何一个手填偏移。"
        ),
        "semanticReview": "not-performed",
        "semanticReviewNote": (
            "**没有做独立语义评审**（semanticReview = not-performed）。"
            "本候选完成的是：引文构造性逐字命中（find + text[s:e]==quote 自检）、"
            "五栏区间独立性机器自检、null 栏全部带非空 Note、"
            "每条断言带 basis。引文定位正确 ≠ 语义已核验——"
            "语义核验要由独立的 read-verify 复核者做，本候选不代它下结论。"
        ),
        "basisLegend": {
            "explicit": "原文直述",
            "inferred": "我的归纳",
            "derived": "跨段推导",
            "unverified": "存疑",
        },
        "nullFieldRule": C.NULL_FIELD_RULE,
        "speechAsClueNotFact": build_speech(C),
        "tasks": build_tasks(C),
        "notTasks": build_not_tasks(C),
        "causeEdges": build_cause(C),
        "rejectedEdges": build_rejected(C),
        "states": build_states(C),
        "knowledgeGaps": build_knowledge(C),
        "foreshadows": build_foreshadows(C),
        "notForeshadows": build_not_foreshadows(C),
        "worldSettings": build_world(C),
        "notWorldSettings": build_not_world(C),
        "themeReadings": build_themes(C),
        "textualNotes": build_textual(C),
        "unknowns": build_unknowns(C),
        "selfCritique": build_self_critique(C),
        "selfCritiqueNote": (
            "每条写成【风险 / 我为什么仍然这么判断 / 复核怎么改判】，"
            "每条都给可执行的改判路径（改哪个字段、移到哪个分区）。"
            "这些是我自己认为最可能读错的地方，不是走过场的免责声明。"
        ),
    }
    cand["coverage"] = coverage(cand)
    cand["machineSelfCheck"] = {
        "buildScript": "loop/state/out/read_dafeng_L3_0267.w-dafeng-0.build/build_candidate.py",
        "contentModule": "loop/state/out/read_dafeng_L3_0267.w-dafeng-0.build/content_0267.py",
        "reproduceCommand": "python3 -B -s loop/state/out/read_dafeng_L3_0267.w-dafeng-0.build/build_candidate.py",
        "sourceHash": SOURCE_HASH,
        "sourceRange": [START, END],
        "resolveFailures": len(FAIL),
        "resolveFailureDetail": FAIL[:50],
    }
    if FAIL:
        print("构建自检失败 %d 项：" % len(FAIL), file=sys.stderr)
        for f in FAIL[:60]:
            print("  -", f, file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已写出：%s" % OUT)
    print("sha256：%s" % sha256_file(OUT))
    print("coverage：%s" % json.dumps(cand["coverage"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
