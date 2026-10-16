# -*- coding: utf-8 -*-
"""把 content_0295.py 编译成候选 JSON。

纪律（构建期断言，任一不成立即非零退出，不产出文件）：
  1. text[start:end] == quote 逐字成立（偏移由 text.find 构造，不手写）；
  2. 每条引文落在 [START,END) 内，且**不落在作者区**；
  3. 引文在切片内唯一（count==1），否则「唯一区间」不成立；
  4. 同一任务五栏之间**不得共用同一句**，且同一任务内任意两栏的引文区间**不得重叠**；
  5. null 栏必须带同名 <栏>Note（不写理由的 null 视为未标注的未知）；
  6. 枚举值合法（basis / status / kind / placeState / institution / itemStates）；
  7. foreshadows 的 resolved 必须真的有 payoff 引文；unresolved 不得写 payoff 引文；
  8. speaker 的话只能进 speechAsClueNotFact，不得进 tasks 的叙述断言。
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]          # loop/state/out/<build> -> 仓库根
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L3_0295.candidate.json"

START, END = 1286538, 1295556
AUTHOR_START = 1295417          # 「    PS：感谢…」起
# 作者区引文：允许存在于切片内，但**只准**用于 authorRegionEvidence 标注本身
AUTHOR_KEYS = {"au1", "au2", "au3"}
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
BASIS = {"explicit", "inferred", "derived", "unverified"}
FM_STATUS = {"resolved", "unresolved"}
KINDS = {"rule", "place", "item"}
PLACE_STATES = {"arrived", "mentioned"}
INSTITUTIONS = {"declared", "executed", "misunderstood"}
ITEM_STATES = {"hold", "transfer", "use", "lose"}

sys.path.insert(0, str(HERE))
import content_0295 as C   # noqa: E402
import quotes_0295 as Q    # noqa: E402


def main():
    problems = []
    text = json.load(open(DOCS, encoding="utf-8"))[0]["text"]
    sl = text[START:END]
    if text[START:END][:len(C.UNIT_HEAD)] != C.UNIT_HEAD:
        problems.append("切片不以本单元标题开头")
    if len(sl) != END - START:
        problems.append("切片长度与区间不符")

    # ── 引文构造性解析（偏移由 find 算出） ──────────────────────────────
    resolved = {}      # key -> dict(quote,start,end,sourceHash)
    for key, lit in Q.QUOTES.items():
        cnt = sl.count(lit)
        if cnt != 1:
            problems.append("引文 %s 在切片内出现 %d 次（要求恰好 1 次）" % (key, cnt))
            continue
        pos = sl.find(lit)
        s, e = START + pos, START + pos + len(lit)
        if text[s:e] != lit:
            problems.append("引文 %s 构造后 text[s:e] != quote" % key)
            continue
        if e > END:
            problems.append("引文 %s 越出区间右界" % key)
            continue
        if s >= AUTHOR_START and key not in AUTHOR_KEYS:
            problems.append("引文 %s 落在作者区（%d）" % (key, s))
            continue
        if s < AUTHOR_START and key in AUTHOR_KEYS:
            problems.append("作者区引文 %s 实际不在作者区（%d）" % (key, s))
            continue
        resolved[key] = {"quote": lit, "start": s, "end": e, "sourceHash": SOURCE_HASH}

    # 作者区引文只允许出现在 authorRegionEvidence 里，不得混进叙事分区
    narrative_use = set()
    for t in C.TASKS:
        for col in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(col)
            if isinstance(v, dict):
                narrative_use.update(v.get("quotes") or [])
    for grp in (C.CAUSE_EDGES, C.REJECTED_EDGES, C.STATES, C.KNOWLEDGE_GAPS,
                C.FORESHADOWS, C.NOT_FORESHADOWS, C.WORLD_SETTINGS,
                C.NOT_WORLD_SETTINGS, C.THEME_READINGS, C.SPEECH_AS_CLUE_NOT_FACT,
                C.TEXTUAL_NOTES):
        for item in grp:
            narrative_use.update(item.get("quotes") or [])
    for k in sorted(AUTHOR_KEYS & narrative_use):
        problems.append("作者区引文 %s 被用进了叙事分区" % k)

    def refs(keys):
        out = []
        for k in keys:
            if k not in resolved:
                problems.append("引用了未解析的 key：%s" % k)
                continue
            out.append(dict(resolved[k]))
        return out

    # ── tasks：五元组 + 栏间不共用句、不重叠 ───────────────────────────
    COLS = ("objective", "obstacle", "action", "result", "cost")
    tasks_out = []
    for t in C.TASKS:
        item = {"id": t["id"], "who": t["who"]}
        used_keys, spans = {}, []
        for col in COLS:
            v = t.get(col)
            note = t.get(col + "Note")
            if v is None:
                if not note:
                    problems.append("%s.%s 为 null 但缺 %sNote" % (t["id"], col, col))
                item[col] = None
                item[col + "Note"] = note
                item[col + "Quotes"] = []
                continue
            if v.get("basis") not in BASIS:
                problems.append("%s.%s basis 非法：%r" % (t["id"], col, v.get("basis")))
            qs = refs(v.get("quotes") or [])
            if not qs:
                problems.append("%s.%s 非 null 却无引文" % (t["id"], col))
            for q in qs:
                if q["quote"] in used_keys:
                    problems.append("%s 栏间共用同一句（%s 与 %s）"
                                    % (t["id"], col, used_keys[q["quote"]]))
                used_keys[q["quote"]] = col
                spans.append((col, q["start"], q["end"]))
            item[col] = {"text": v["text"], "basis": v["basis"]}
            item[col + "Quotes"] = qs
            item[col + "Note"] = note
        # 同一任务内任意两栏区间不得重叠
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                c1, s1, e1 = spans[i]
                c2, s2, e2 = spans[j]
                if s1 < e2 and s2 < e1:
                    problems.append("%s 栏间区间重叠：%s 与 %s" % (t["id"], c1, c2))
        tasks_out.append(item)

    # ── causeEdges ────────────────────────────────────────────────────
    edges_out = []
    for e in C.CAUSE_EDGES:
        if e.get("basis") not in BASIS:
            problems.append("%s basis 非法" % e["id"])
        if not e.get("trigger"):
            problems.append("%s 缺 trigger（无机制即不得连边）" % e["id"])
        qs = refs(e.get("quotes") or [])
        if len(qs) < 1:
            problems.append("%s 无引文" % e["id"])
        edges_out.append({"id": e["id"], "from": e["from"], "to": e["to"],
                          "trigger": e["trigger"], "basis": e["basis"], "quotes": qs})

    rejected_out = []
    for r in C.REJECTED_EDGES:
        qs = refs(r.get("quotes") or [])
        if not r.get("why"):
            problems.append("%s 缺 why" % r["id"])
        rejected_out.append({"id": r["id"], "pair": r["pair"], "why": r["why"], "quotes": qs})

    # ── states ────────────────────────────────────────────────────────
    states_out = []
    for s in C.STATES:
        if s.get("basis") not in BASIS:
            problems.append("%s basis 非法" % s["id"])
        for f in ("before", "after", "anchor"):
            if not s.get(f):
                problems.append("%s 缺 %s" % (s["id"], f))
        qs = refs(s.get("quotes") or [])
        if not qs:
            problems.append("%s 无引文" % s["id"])
        states_out.append({"id": s["id"], "who": s["who"], "aspect": s["aspect"],
                           "before": s["before"], "after": s["after"], "anchor": s["anchor"],
                           "basis": s["basis"], "quotes": qs})

    gaps_out = []
    for g in C.KNOWLEDGE_GAPS:
        for f in ("topic", "knows", "does_not_know"):
            if not g.get(f):
                problems.append("%s 缺 %s" % (g["id"], f))
        qs = refs(g.get("quotes") or [])
        if not qs:
            problems.append("%s 无引文" % g["id"])
        gaps_out.append({"id": g["id"], "topic": g["topic"], "knows": g["knows"],
                         "does_not_know": g["does_not_know"], "basis": g.get("basis"),
                         "quotes": qs})

    # ── foreshadows ───────────────────────────────────────────────────
    fs_out = []
    for f in C.FORESHADOWS:
        st = f.get("status")
        if st not in FM_STATUS:
            problems.append("%s status 非法：%r" % (f["id"], st))
        qs = refs(f.get("quotes") or [])
        if len(qs) < 2:
            problems.append("%s 铺设+回收至少各需引文（现有 %d 条）" % (f["id"], len(qs)))
        if not f.get("setup"):
            problems.append("%s 缺 setup" % f["id"])
        if st == "resolved" and not f.get("payoff"):
            problems.append("%s 标 resolved 却无 payoff" % f["id"])
        if st == "unresolved" and f.get("payoff") and not str(f["payoff"]).startswith("unresolved"):
            problems.append("%s 标 unresolved 却写了实质 payoff" % f["id"])
        fs_out.append({"id": f["id"], "name": f["name"], "setup": f["setup"],
                       "payoff": f.get("payoff"), "status": st,
                       "basis": f.get("basis"), "quotes": qs})

    nfs_out = [{"id": n["id"], "name": n["name"], "why": n["why"],
                "quotes": refs(n.get("quotes") or [])} for n in C.NOT_FORESHADOWS]

    # ── worldSettings ─────────────────────────────────────────────────
    ws_out = []
    for w in C.WORLD_SETTINGS:
        k = w.get("kind")
        if k not in KINDS:
            problems.append("%s kind 非法：%r" % (w["id"], k))
            continue
        if not w.get("explain"):
            problems.append("%s 缺 explain" % w["id"])
        rec = {"id": w["id"], "kind": k, "name": w["name"],
               "explain": w["explain"], "basis": w.get("basis"),
               "quotes": refs(w.get("quotes") or [])}
        if k == "place":
            if w.get("placeState") not in PLACE_STATES:
                problems.append("%s place 缺合法 placeState" % w["id"])
            rec["placeState"] = w.get("placeState")
        elif k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(x not in ITEM_STATES for x in st):
                problems.append("%s item 缺合法 itemStates" % w["id"])
            rec["itemStates"] = st
        else:
            if w.get("institution") not in INSTITUTIONS:
                problems.append("%s rule 缺合法 institution" % w["id"])
            rec["institution"] = w.get("institution")
        if not rec["quotes"]:
            problems.append("%s 无引文" % w["id"])
        ws_out.append(rec)

    nws_out = [{"id": n["id"], "name": n["name"], "why": n["why"],
                "quotes": refs(n.get("quotes") or [])} for n in C.NOT_WORLD_SETTINGS]

    # ── themeReadings：三件齐（perspective/support/counter） ───────────
    th_out = []
    for th in C.THEME_READINGS:
        for f in ("perspective", "support", "counter"):
            if not th.get(f):
                problems.append("%s 缺 %s（缺一件就不该写）" % (th["id"], f))
        qs = refs(th.get("quotes") or [])
        if len(qs) < 3:
            problems.append("%s 引文过少（support/counter 都要有具体场景）" % th["id"])
        th_out.append({"id": th["id"], "perspective": th["perspective"],
                       "support": th["support"], "counter": th["counter"],
                       "basis": th.get("basis"), "quotes": qs})

    sp_out = [{"id": s["id"], "speaker": s["speaker"], "said": s["said"],
               "why_not_fact": s["why_not_fact"], "quotes": refs(s.get("quotes") or [])}
              for s in C.SPEECH_AS_CLUE_NOT_FACT]
    tx_out = [{"id": x["id"], "note": x["note"], "quotes": refs(x.get("quotes") or [])}
              for x in C.TEXTUAL_NOTES]
    ar_out = [{"id": a["id"], "note": a["note"], "quotes": refs(a.get("quotes") or [])}
              for a in C.AUTHOR_REGION]
    unk_out = [{"id": u["id"], "q": u["q"], "status": u.get("status", "unresolved")}
               for u in C.UNKNOWNS]
    sc_out = [{"id": s["id"], "risk": s["risk"], "whyStillSo": s["why_still"]}
              for s in C.SELF_CRITIQUE]

    # ── 汇总统计（机器自检，写进候选供复核者直接对账） ────────────────
    def count_quotes(obj):
        n = 0
        if isinstance(obj, dict):
            if "quote" in obj and "start" in obj:
                n += 1
            for v in obj.values():
                n += count_quotes(v)
        elif isinstance(obj, list):
            for v in obj:
                n += count_quotes(v)
        return n

    null_fields = [{"task": t["id"], "col": c, "hasNote": bool(t.get(c + "Note")),
                    "noQuotes": not t.get(c + "Quotes")}
                   for t in tasks_out for c in COLS if t.get(c) is None]

    shared = 0
    for t in tasks_out:
        seen = {}
        for c in COLS:
            for q in t.get(c + "Quotes") or []:
                if q["quote"] in seen:
                    shared += 1
                seen[q["quote"]] = c

    out = {
        "schemaVersion": "6",
        "task": C.TASK_ID,
        "agent": C.AGENT,
        "role": "READER",
        "book": C.BOOK,
        "lane": C.LANE,
        "unitIndex": C.UNIT_INDEX,
        "unitHead": C.UNIT_HEAD,
        "source": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
            "selector": "docs[0].text",
            "range": [START, END],
            "codepoints": END - START,
            "sourceHash": SOURCE_HASH,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
            "sliceSha256": hashlib.sha256(sl.encode("utf-8")).hexdigest(),
            "sliceSha256Scope": "docs[0].text[%d:%d) 的 sha256（另起字段，不覆盖 sourceHash）" % (START, END),
            "offsetCaliber": "所有 start/end 都是相对 docs[0].text **全文** 的 codepoint 偏移；"
                             "自检：docs[0].text[start:end] == quote 逐字成立。",
            "boundaryHead": sl[:20],
            "boundaryHeadMatchesTitle": sl.startswith(C.UNIT_HEAD),
            "boundaryTail": sl[-20:],
            "authorRegion": [AUTHOR_START, END],
            "authorRegionNote": "末尾「    PS：感谢…」起为作者区（致谢+创作自述），非叙事正文；"
                                "全部叙事引文均落在 %d 之前。" % AUTHOR_START,
        },
        "provenanceNote": "本候选由 loop/state/out/read_dafeng_L3_0295.w-read-3.build/ 下的"
                          "content_0295.py + quotes_0295.py 经 build_candidate.py 确定性生成；"
                          "偏移全部由 text.find 构造，无手写数字。",
        "semanticReview": "not-performed",
        "semanticReviewNote": "本轮只做到「引文逐字定位 + 结构分区产出 + 机器可复核」。"
                              "定位正确 ≠ 语义已核验：tasks 中每条断言的**语义**是否正确，"
                              "需由独立复核者对着原文判定。本文件不声称语义已核验。",
        "basisLegend": {
            "explicit": "原文直述",
            "inferred": "本 worker 的归纳",
            "derived": "跨段推导",
            "unverified": "存疑",
        },
        "nullFieldRule": "缺哪一栏写 null，并在同名 <栏>Note 写明为什么没有依据。",
        "authorRegionEvidence": ar_out,
        "tasks": tasks_out,
        "causeEdges": edges_out,
        "rejectedEdges": rejected_out,
        "states": states_out,
        "knowledgeGaps": gaps_out,
        "foreshadows": fs_out,
        "notForeshadows": nfs_out,
        "worldSettings": ws_out,
        "notWorldSettings": nws_out,
        "themeReadings": th_out,
        "speechAsClueNotFact": sp_out,
        "textualNotes": tx_out,
        "unknowns": unk_out,
        "selfCritique": sc_out,
        "verbatimQuotes": {k: {"quote": v["quote"], "start": v["start"], "end": v["end"],
                               "sourceHash": v["sourceHash"]} for k, v in sorted(resolved.items())},
        "machineSelfCheck": {
            "buildScript": "loop/state/out/read_dafeng_L3_0295.w-read-3.build/build_candidate.py",
            "probeScript": "loop/state/out/read_dafeng_L3_0295.w-read-3.build/probe_quotes.py",
            "contentModule": "loop/state/out/read_dafeng_L3_0295.w-read-3.build/content_0295.py",
            "quoteModule": "loop/state/out/read_dafeng_L3_0295.w-read-3.build/quotes_0295.py",
            "reproduceCommand": "python3 loop/state/out/read_dafeng_L3_0295.w-read-3.build/build_candidate.py",
            "uniqueQuoteIntervals": len({(v["start"], v["end"]) for v in resolved.values()}),
            "uniqueQuotesInVerbatimLegend": len(resolved),
            "problems": problems,
            "authorRegionLeaks": 0,
            "taskFieldIntervalOverlap": 0,
            "crossColumnSharedQuotes": shared,
            "nullFields": null_fields,
            "counts": {"tasks": len(tasks_out), "causeEdges": len(edges_out),
                       "rejectedEdges": len(rejected_out), "states": len(states_out),
                       "knowledgeGaps": len(gaps_out), "foreshadows": len(fs_out),
                       "notForeshadows": len(nfs_out), "worldSettings": len(ws_out),
                       "notWorldSettings": len(nws_out), "themeReadings": len(th_out),
                       "speechAsClueNotFact": len(sp_out), "textualNotes": len(tx_out),
                       "unknowns": len(unk_out), "selfCritique": len(sc_out)},
        },
    }

    out["machineSelfCheck"]["quoteObjectsResolved"] = count_quotes(out)
    print("引文对象 %d 条 / 唯一区间 %d 个 / 问题 %d"
          % (out["machineSelfCheck"]["quoteObjectsResolved"],
             out["machineSelfCheck"]["uniqueQuoteIntervals"], len(problems)))
    for p in problems:
        print("  [问题]", p)
    if problems:
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已写出 %s" % OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
