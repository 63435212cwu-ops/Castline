#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""确定性构建 loop/state/out/read_dafeng_L3_0295.candidate.json。

原则：
  · 候选里的每一个 {quote,start,end} 都由 quotes_0295.py 的字符串 + text.find 现场构造，
    **没有任何手写偏移数字**；
  · 构建期做硬断言，任一条不成立即非零退出、不写文件（宁可没有产出，也不产出半成品）。

构建期断言：
  A1  text[start:end] == quote 逐字成立
  A2  引文落在本单元 [1286538,1295556) 内（作者区引文除外，另立 authorRegion 记录）
  A3  同一任务五栏之间：引文键不重复（禁止一栏的句子顶五栏用）
  A4  同一任务五栏之间：字节区间两两不重叠（连同一句话的不同片段也算复用）
  A5  每个 null 栏必须有同名 <栏>Note 且非空
  A6  枚举合法：basis / kind / institution / placeState / itemStates
  A7  伏笔 resolved=True 必须有 payoff；resolved=False 必须 payoff 为空
  A8  themeReadings 每条三件齐（perspective/support/counter），且不得使用被禁判据词
  A9  叙事分区不得引用作者区（kind=author_note）的引文
  A10 sourceHash 与任务声明一致；切片哈希另起字段
  A11 causeEdges 每条必须有 trigger（机制）且引文 >= 2
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L3_0295.candidate.json"

TASK_ID = "read:dafeng:L3:0295"
AGENT = "w-xiyou-1"
START, END = 1286538, 1295556
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

BASES = {"explicit", "inferred", "derived", "unverified"}
KINDS = {"narration", "dialogue", "inner", "free_indirect", "parable", "author_note"}
INSTITUTIONS = {"declared", "executed", "misunderstood"}
PLACE_STATES = {"arrived", "mentioned"}
ITEM_STATES = {"hold", "transfer", "use", "lose"}
BANNED_THEME_WORDS = ["事件密度", "剧情点", "死亡人数", "篇幅中点", "时间中点", "三幕", "英雄旅程"]

sys.path.insert(0, str(HERE))
from quotes_0295 import QUOTES  # noqa: E402
import content_0295 as C  # noqa: E402

PROBLEMS = []


def bad(msg):
    PROBLEMS.append(msg)


def resolve(key, text, in_author_ok=False):
    """把引文键解析成 {key,quote,start,end,sourceHash,kind,occ,spansParagraphs}。"""
    if key not in QUOTES:
        bad("引文键不存在：%s" % key)
        return None
    quote, occ, kind = QUOTES[key]
    pos = -1
    for _ in range(occ + 1):
        pos = text.find(quote, pos + 1)
        if pos < 0:
            bad("引文定位失败：%s occ=%d" % (key, occ))
            return None
    s, e = pos, pos + len(quote)
    if text[s:e] != quote:                                   # A1
        bad("A1 text[start:end]!=quote：%s" % key)
        return None
    if kind != "author_note" and not (START <= s and e <= END):  # A2
        bad("A2 引文越出本单元：%s [%d,%d)" % (key, s, e))
        return None
    if kind == "author_note" and not in_author_ok:
        bad("A9 叙事分区引用了作者区引文：%s" % key)
        return None
    return dict(key=key, quote=quote, start=s, end=e, sourceHash=SOURCE_HASH, kind=kind,
                occ=occ, spansParagraphs=("\n\n" in quote),
                # 机器可算的提示：引文里是否**嵌着人物说的话**。很多叙述句里带引号对白
                # （如「王首辅站了起身，朗声道：“大奉武者，不跪。”」），
                # 复核者需要一眼看出「这句话里哪部分是谁说的」，而不是自己去数引号。
                containsUtterance=("\u201c" in quote or "\u300c" in quote))


def resolve_many(keys, text, in_author_ok=False):
    out = []
    for k in keys or []:
        r = resolve(k, text, in_author_ok)
        if r:
            out.append(r)
    return out


def check_basis(where, basis):
    if basis not in BASES:                                   # A6
        bad("A6 basis 非法：%s = %r" % (where, basis))


def build():
    raw = DOCS.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    text = doc[0]["text"]
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != SOURCE_HASH:                            # A10
        bad("A10 sourceHash 不符：%s" % actual_hash)
    slice_sha = hashlib.sha256(text[START:END].encode("utf-8")).hexdigest()

    # ── tasks ───────────────────────────────────────────────────────────
    tasks_out = []
    for t in C.TASKS:
        item = dict(id=t["id"], who=t["who"])
        used_keys, used_spans = [], []
        for col in ("objective", "obstacle", "action", "result", "cost"):
            val = t.get(col)
            note = t.get(col + "Note")
            if val is None:
                if not note:                                  # A5
                    bad("A5 %s.%s 为 null 但无 %sNote" % (t["id"], col, col))
                item[col] = None
                item[col + "Note"] = note
                item[col + "Quotes"] = []
                continue
            check_basis("%s.%s" % (t["id"], col), val["basis"])
            qs = resolve_many(val["quotes"], text)
            if not qs:
                bad("%s.%s 无有效引文" % (t["id"], col))
            for q in qs:
                if q["key"] in used_keys:                     # A3
                    bad("A3 %s 五栏复用同一引文键：%s" % (t["id"], q["key"]))
                for (s0, e0, k0) in used_spans:               # A4
                    if not (q["end"] <= s0 or q["start"] >= e0):
                        bad("A4 %s 栏间区间重叠：%s 与 %s" % (t["id"], q["key"], k0))
                used_keys.append(q["key"])
                used_spans.append((q["start"], q["end"], q["key"]))
            item[col] = dict(text=val["text"], basis=val["basis"], quotes=qs)
            item[col + "Note"] = None
        tasks_out.append(item)

    # ── causeEdges ──────────────────────────────────────────────────────
    ce_out = []
    for c in C.CAUSE_EDGES:
        check_basis(c["id"], c["basis"])
        if not c.get("trigger"):
            bad("A11 %s 缺 trigger" % c["id"])
        qs = resolve_many(c["quotes"], text)
        if len(qs) < 2:                                       # A11
            bad("A11 %s 引文少于 2 条" % c["id"])
        ce_out.append(dict(id=c["id"], **{"from": c["from"], "to": c["to"], "basis": c["basis"],
                                          "trigger": c["trigger"], "quotes": qs}))

    rej_out = []
    for r in C.REJECTED_EDGES:
        check_basis(r["id"], r["basis"])
        rej_out.append(dict(id=r["id"], pair=r["pair"], basis=r["basis"], why=r["why"],
                            quotes=resolve_many(r["quotes"], text)))

    # ── states ──────────────────────────────────────────────────────────
    st_out = []
    for s in C.STATES:
        item = dict(id=s["id"], who=s["who"])
        for col in ("before", "after", "anchor"):
            v = s.get(col)
            note = s.get(col + "Note")
            if v is None:
                if not note:
                    bad("A5 %s.%s 为 null 但无 Note" % (s["id"], col))
                item[col] = None
                item[col + "Note"] = note
                item[col + "Quotes"] = []
                continue
            check_basis("%s.%s" % (s["id"], col), v["basis"])
            item[col] = dict(text=v["text"], basis=v["basis"], quotes=resolve_many(v["quotes"], text))
            item[col + "Note"] = None
        st_out.append(item)

    # ── knowledgeGaps / foreshadows / notForeshadows ────────────────────
    kg_out = []
    for k in C.KNOWLEDGE_GAPS:
        check_basis(k["id"], k["basis"])
        kg_out.append(dict(id=k["id"], knower=k["knower"], knows=k["knows"], about=k["about"],
                           basis=k["basis"], note=k["note"], quotes=resolve_many(k["quotes"], text)))

    fs_out = []
    for f in C.FORESHADOWS:
        check_basis(f["id"], f["basis"])
        setup = resolve_many(f["setup"], text)
        payoff = resolve_many(f["payoff"], text)
        if f["resolved"] and not payoff:                      # A7
            bad("A7 %s resolved=True 但无 payoff" % f["id"])
        if not f["resolved"] and payoff:
            bad("A7 %s resolved=False 但有 payoff" % f["id"])
        fs_out.append(dict(id=f["id"], name=f["name"], resolved=f["resolved"], basis=f["basis"],
                           setup=setup, payoff=payoff, note=f["note"]))

    nf_out = [dict(id=n["id"], name=n["name"], why=n["why"], quotes=resolve_many(n["quotes"], text))
              for n in C.NOT_FORESHADOWS]

    # ── worldSettings / notWorldSettings ────────────────────────────────
    ws_out = []
    for w in C.WORLD_SETTINGS:
        check_basis(w["id"], w["basis"])
        entry = dict(id=w["id"], kind=w["kind"], name=w["name"], basis=w["basis"],
                     explain=w["explain"], quotes=resolve_many(w["quotes"], text))
        if w["kind"] == "rule":
            if w.get("institution") not in INSTITUTIONS:
                bad("A6 %s institution 非法：%r" % (w["id"], w.get("institution")))
            entry["institution"] = w.get("institution")
            entry["institutionNote"] = w.get("institutionNote")
        elif w["kind"] == "place":
            if w.get("placeState") not in PLACE_STATES:
                bad("A6 %s placeState 非法：%r" % (w["id"], w.get("placeState")))
            entry["placeState"] = w.get("placeState")
            entry["placeStateNote"] = w.get("placeStateNote")
        elif w["kind"] == "item":
            st = w.get("itemStates") or []
            if not st or any(x not in ITEM_STATES for x in st):
                bad("A6 %s itemStates 非法：%r" % (w["id"], st))
            entry["itemStates"] = st
            entry["itemVerbs"] = w.get("itemVerbs")
            entry["itemStatesNote"] = w.get("itemStatesNote")
        else:
            bad("A6 %s kind 非法：%r" % (w["id"], w["kind"]))
        ws_out.append(entry)

    nw_out = [dict(id=n["id"], name=n["name"], why=n["why"], quotes=resolve_many(n["quotes"], text))
              for n in C.NOT_WORLD_SETTINGS]

    # ── themeReadings ───────────────────────────────────────────────────
    th_out = []
    for t in C.THEME_READINGS:
        for part in ("perspective", "support", "counter"):     # A8
            if not t.get(part):
                bad("A8 %s 缺 %s" % (t["id"], part))
        support, counter = t["support"], t["counter"]
        check_basis("%s.support" % t["id"], support["basis"])
        check_basis("%s.counter" % t["id"], counter["basis"])
        blob = json.dumps([t["perspective"], support["text"], counter["text"], t.get("note")],
                          ensure_ascii=False)
        for w in BANNED_THEME_WORDS:                           # A8
            if w in blob:
                bad("A8 %s 使用了被禁判据词：%s" % (t["id"], w))
        th_out.append(dict(id=t["id"], perspective=t["perspective"],
                           support=dict(text=support["text"], basis=support["basis"],
                                        quotes=resolve_many(support["quotes"], text)),
                           counter=dict(text=counter["text"], basis=counter["basis"],
                                        quotes=resolve_many(counter["quotes"], text)),
                           note=t.get("note")))

    sp_out = []
    for s in C.SPEECH_AS_CLUE:
        e = dict(id=s["id"], speaker=s["speaker"], claim=s["claim"], whyNotFact=s["whyNotFact"],
                 quotes=resolve_many(s["quotes"], text))
        if s.get("note"):
            e["note"] = s["note"]
        sp_out.append(e)

    tx_out = [dict(id=t["id"], topic=t["topic"], basis=t["basis"], note=t["note"],
                   quotes=resolve_many(t["quotes"], text, in_author_ok=True))
              for t in C.TEXTUAL_NOTES]

    un_out = [dict(id=u["id"], about=u["about"], why=u["why"], keep=u["keep"]) for u in C.UNKNOWNS]
    sc_out = [dict(id=s["id"], risk=s["risk"], why=s["why"], mitigation=s["mitigation"])
              for s in C.SELF_CRITIQUE]

    ar = C.AUTHOR_REGION
    ar_quotes = resolve_many(ar["quotes"], text, in_author_ok=True)
    author_region = dict(quotes=ar_quotes, note=ar["note"],
                         regionStart=min(q["start"] for q in ar_quotes),
                         regionEnd=END,
                         boundaryTail=text[END - 40:END],
                         boundaryNextHead=text[END:END + 12])

    # ── 统计 ────────────────────────────────────────────────────────────
    def count_quotes(o):
        n = 0
        if isinstance(o, dict):
            if "quote" in o and "start" in o:
                return 1
            for v in o.values():
                n += count_quotes(v)
        elif isinstance(o, list):
            for v in o:
                n += count_quotes(v)
        return n

    cand = dict(
        schemaVersion="6",
        task=TASK_ID, agent=AGENT, role="READER", book="dafeng", lane=3, unitIndex=295,
        unitHead="第六十六章 不跪",
        provenanceNote=("本候选由 loop/state/out/read_dafeng_L3_0295.w-xiyou-1.build/ 下的 "
                        "content_0295.py（人工精读结论）+ quotes_0295.py（引文字符串）经 "
                        "build_candidate.py 确定性生成；候选里**没有任何手写偏移数字**，"
                        "每个 start/end 都由 text.find 现场构造并断言 text[start:end]==quote。"),
        semanticReview="not-performed",
        semanticReviewNote=("本轮只做到「引文逐字定位 + 结构分区产出 + 机器可复核」。"
                            "定位正确 ≠ 语义已核验：本文件每条断言的**语义**是否正确，"
                            "需由独立复核者对着原文判定。本文件不声称语义已核验。"),
        basisLegend={"explicit": "原文直述", "inferred": "我的归纳", "derived": "跨段推导",
                     "unverified": "存疑"},
        kindLegend={"narration": "叙述（含叙述者评论）", "dialogue": "人物说的话（不是叙述事实）",
                    "inner": "人物内心独白", "free_indirect": "叙述转述众人推断（非叙述认定）",
                    "parable": "人物讲述的典故/传说（非本场事实）", "author_note": "作者区（致谢/自述）"},
        kindCaveat=("kind 是对**这段引文整体**的归类，不代表引文里每一句都是该类。"
                    "很多叙述句里嵌着人物说的话（例如 nk_wang_a「王首辅站了起身，朗声道："
                    "『大奉武者，不跪。』」是 narration，但那句台词本身是人物说的）。"
                    "为免复核者逐条数引号，每个引文对象都带机器算出的 containsUtterance 布尔字段；"
                    "凡 containsUtterance=true 的引文，其中的对白都不得被当作叙述事实使用。"),
        nullFieldRule="缺哪一栏写 null，并在同名 <栏>Note 写明为什么没有依据。",
        source=dict(path="data/cache/1063b17ca65ec1b76f30e460.docs.json", selector="docs[0].text",
                    range=[START, END], codepoints=END - START, sourceHash=SOURCE_HASH,
                    sourceHashScope="整个 docs.json 文件的 sha256（不是切片）",
                    sliceSha256=slice_sha,
                    sliceSha256Scope="docs[0].text[1286538:1295556) 的 sha256（另起字段，不覆盖 sourceHash）",
                    offsetCaliber=("所有 start/end 都是相对 docs[0].text **全文** 的 codepoint 偏移；"
                                   "自检：docs[0].text[start:end] == quote 逐字成立。"),
                    boundaryHead=text[START:START + 11],
                    boundaryHeadIsTitle=(text[START:START + 11] == "第六十六章 不跪"),
                    boundaryTail=text[END - 40:END]),
        authorRegionEvidence=[author_region],
        tasks=tasks_out, causeEdges=ce_out, rejectedEdges=rej_out, states=st_out,
        knowledgeGaps=kg_out, foreshadows=fs_out, notForeshadows=nf_out,
        worldSettings=ws_out, notWorldSettings=nw_out, themeReadings=th_out,
        speechAsClueNotFact=sp_out, textualNotes=tx_out, unknowns=un_out, selfCritique=sc_out,
        machineSelfCheck=dict(
            quoteObjects=count_quotes(dict(tasks=tasks_out, causeEdges=ce_out, rejectedEdges=rej_out,
                                           states=st_out, knowledgeGaps=kg_out, foreshadows=fs_out,
                                           notForeshadows=nf_out, worldSettings=ws_out,
                                           notWorldSettings=nw_out, themeReadings=th_out,
                                           speechAsClueNotFact=sp_out, textualNotes=tx_out,
                                           authorRegionEvidence=[author_region])),
            problems=list(PROBLEMS),
            counts={k: len(v) for k, v in dict(tasks=tasks_out, causeEdges=ce_out,
                                               rejectedEdges=rej_out, states=st_out,
                                               knowledgeGaps=kg_out, foreshadows=fs_out,
                                               notForeshadows=nf_out, worldSettings=ws_out,
                                               notWorldSettings=nw_out, themeReadings=th_out,
                                               speechAsClueNotFact=sp_out, textualNotes=tx_out,
                                               unknowns=un_out, selfCritique=sc_out).items()},
            reproduceCommand="python3 loop/state/out/read_dafeng_L3_0295.w-xiyou-1.build/build_candidate.py",
        ),
    )
    return cand


def main():
    cand = build()
    if PROBLEMS:
        print("构建失败，%d 条问题：" % len(PROBLEMS))
        for p in PROBLEMS:
            print("  !", p)
        return 1
    OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("已写出 %s" % OUT.relative_to(ROOT))
    print("引文对象 %d 条" % cand["machineSelfCheck"]["quoteObjects"])
    print("分区计数：%s" % json.dumps(cand["machineSelfCheck"]["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
