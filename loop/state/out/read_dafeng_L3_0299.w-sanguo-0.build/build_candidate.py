# -*- coding: utf-8 -*-
"""构造 loop/state/out/read_dafeng_L3_0299.candidate.json。

**本脚本没有手写偏移数字**：每个 start/end 都由 (quote, occ) 在 docs[0].text 的
本单元切片内 find 后现场算出，并当场断言 text[start:end] == quote。

构建期断言（任一失败即非零退出，不产出候选）：
  A1  切片以本单元标题开头、长度与任务声明一致
  A2  每个引文键都存在，且每条引文在切片内的出现次数与 occ 自洽
  A3  每个引文对象满足 start/end 落在区间内、text[start:end]==quote、sourceHash 一致
  A4  同一任务五栏的引文键两两不重复，且字符区间两两不相交
  A5  null 栏必须带同名 <栏>Note（不写理由的 null 判为未标注的未知）
  A6  枚举值合法（basis / kind / institution / placeState / itemStates）
  A7  伏笔 resolved 与 payoff 一致（resolved=true 必须有 payoff；unresolved 必须为 false）
  A8  causeEdges 每条 ≥2 条引文且有 trigger；tasks 每条非 null 栏都有 basis
  A9  themeReadings ≤2 且三件齐（perspective/support/counter），
      且不得使用被禁判据（事件密度/剧情点数量/死亡人数/篇幅中点）
  A10 叙事分区不得引用作者区引文（q_ps）
  A11 states 每条的 before/after/anchor 各自带引文或显式 null + Note
  A12 引文键总表里所有键都被用到（没有写了不用的引文）

复现：python3 -B -s build_candidate.py
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
OUT = os.path.join(ROOT, "loop/state/out/read_dafeng_L3_0299.candidate.json")

START, END = 1311348, 1316296
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
TASK_ID = "read:dafeng:L3:0299"

from quotes_0299 import QUOTES                      # noqa: E402
from content_0299a import TASKS, CAUSE_EDGES, REJECTED_EDGES        # noqa: E402
from content_0299b import (                          # noqa: E402
    STATES, KNOWLEDGE_GAPS, FORESHADOWS, NOT_FORESHADOWS,
    WORLD_SETTINGS, NOT_WORLD_SETTINGS, THEME_READINGS,
)
from content_0299c import (                          # noqa: E402
    SPEECH_AS_CLUE_NOT_FACT, TEXTUAL_NOTES, UNKNOWNS, SELF_CRITIQUE,
)

PROBLEMS = []
USED_KEYS = set()

KIND_LEGAL = {"narration", "dialogue", "inner", "free_indirect", "author_note"}
BASIS_LEGAL = {"explicit", "inferred", "derived", "unverified"}
INST_LEGAL = {"declared", "executed", "misunderstood"}
PLACE_LEGAL = {"arrived", "mentioned"}
ITEM_LEGAL = {"hold", "transfer", "use", "lose"}
BANNED_THEME = ["事件密度", "剧情点数量", "剧情点", "死亡人数", "篇幅中点", "时间中点"]


def fail(msg):
    PROBLEMS.append(msg)


def occ_in_slice(text, q):
    out = []
    i = text.find(q, START, END)
    while i >= 0 and i + len(q) <= END:
        out.append(i)
        i = text.find(q, i + 1, END)
    return out


def para_index(text, pos):
    """本单元内的空行槽编号（0 基）：标题行是 0。"""
    return text[START:pos].count("\n")


def mkref(text, key):
    """把一个引文键解析成完整的引文对象（现场算偏移）。"""
    if key not in QUOTES:
        fail("引文键不存在：%s" % key)
        return None
    q, kind, occ = QUOTES[key]
    USED_KEYS.add(key)
    hits = occ_in_slice(text, q)
    if not hits:
        fail("%s 在切片内找不到：%r" % (key, q[:30]))
        return None
    if occ is None:
        if len(hits) != 1:
            fail("%s 要求唯一，实际 %d 次" % (key, len(hits)))
            return None
        st = hits[0]
    else:
        if occ >= len(hits):
            fail("%s occ 越界" % key)
            return None
        st = hits[occ]
    en = st + len(q)
    if text[st:en] != q:
        fail("%s text[start:end] != quote" % key)
        return None
    if not (START <= st and en <= END):
        fail("%s 越界" % key)
        return None
    return {
        "key": key,
        "quote": q,
        "start": st,
        "end": en,
        "sourceHash": SOURCE_HASH,
        "kind": kind,
        "occ": occ if occ is not None else 0,
        "para": para_index(text, st),
        "spansParagraphs": "\n" in q,
        "containsUtterance": ("“" in q or "”" in q),
    }


def mkfield(text, field, check_basis=True):
    """把 {text, basis, quotes[]} 形态的栏位展开成带引文对象的结构。

    check_basis=False 用于**纯引文展开**（例如把 costQuotes / costNullReasonQuotes
    这两组键解析成引文对象）：那些容器不是五元组栏位，没有 basis 可言，
    不该被 basis 合法性断言误伤。
    """
    if field is None:
        return None
    refs = [mkref(text, k) for k in field.get("quotes", [])]
    refs = [r for r in refs if r]
    if check_basis and field.get("basis") not in BASIS_LEGAL:
        fail("basis 非法：%r" % field.get("basis"))
    return {"text": field["text"], "basis": field.get("basis"), "quotes": refs}


def intervals(refs):
    return [(r["start"], r["end"]) for r in refs]


def overlap(a, b):
    return not (a[1] <= b[0] or b[1] <= a[0])


def main():
    raw = open(DOCS, "rb").read()
    if hashlib.sha256(raw).hexdigest() != SOURCE_HASH:
        fail("docs.json 的 sha256 与任务声明不符")
    text = json.loads(raw.decode("utf-8"))[0]["text"]

    # A1
    seg = text[START:END]
    if not seg.startswith("第七十章 赴会"):
        fail("A1 切片不以本单元标题开头：%r" % seg[:20])
    if len(seg) != END - START:
        fail("A1 切片长度异常")

    cand = {
        "schemaVersion": "6",
        "task": TASK_ID,
        "agent": "w-sanguo-0",
        "role": "READER",
        "book": "dafeng",
        "lane": 3,
        "unitIndex": 299,
        "unitHead": "第七十章 赴会",
        "provenanceNote": (
            "本候选由 %s 下的 content_0299a/b/c.py（人工精读结论）＋ quotes_0299.py（引文字符串）"
            "经 build_candidate.py 确定性生成。候选里**没有任何手写偏移数字**："
            "每个 start/end 都由 (quote, occ) 在本单元切片内 find 后现场算出，"
            "并当场断言 text[start:end] == quote。"
            "**接手说明（w-sanguo-0）：**本单元的租约原由 worker w-dafeng-0 持有，"
            "其 agent 进程在该候选落盘后、提交前死亡（租约被回收，本 worker 于 "
            "2026-10-15T05:47:41Z 领到同一任务）。本轮的工作是**独立复读原文 + 复核并修正**该候选，"
            "不是重写：前任的 307 个引文对象经复算全部逐字命中、机器自检数字可复现（见 "
            "audit_candidate.py），本轮只改了 4 处**语义**问题并逐一留档（见 selfCritique SC06 与 U14）："
            "①F01 收束写成「一个也没随行／没有人去成」，与原文收束句「二哥和姐姐已经走了」方向相反；"
            "②F03 setup[2] 的 why 引用「务必穿的体面些」，而它挂的引文是另一句；"
            "③K03 同步改为不裁决妹妹去留；④S05.afterNote 加边界，只断到「当场拒绝」这一时点。"
            "未改任何偏移、未删任何分区、未新增无据条目。" % os.path.relpath(HERE, ROOT)),
        "semanticReview": "not-performed",
        "semanticReviewNote": (
            "本轮只做到「引文逐字定位 + 结构分区产出 + 机器可复核」。"
            "定位正确 ≠ 语义已核验：本文件每条断言的**语义**是否正确，"
            "需由独立复核者对着原文判定。本文件不声称语义已核验。"),
        "basisLegend": {
            "explicit": "原文直述", "inferred": "我的归纳",
            "derived": "跨段推导", "unverified": "存疑"},
        "kindLegend": {
            "narration": "叙述（含叙述者评论）",
            "dialogue": "人物说的话（不是叙述事实）",
            "inner": "人物内心独白",
            "free_indirect": "叙述转述人物理解（非叙述认定）",
            "author_note": "作者区（致谢/自述；本候选叙事分区不引用）"},
        "nullFieldRule": "缺哪一栏写 null，并在同名 <栏>Note 写明为什么没有依据。",
        "source": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
            "selector": "docs[0].text",
            "range": [START, END],
            "codepoints": END - START,
            "sourceHash": SOURCE_HASH,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
            "sliceSha256": hashlib.sha256(seg.encode("utf-8")).hexdigest(),
            "sliceSha256Scope": "docs[0].text[%d:%d) 的 sha256（另起字段，不覆盖 sourceHash）"
                                % (START, END),
            "offsetCaliber": ("所有 start/end 都是相对 docs[0].text **全文** 的 codepoint 偏移；"
                              "自检：docs[0].text[start:end] == quote 逐字成立。"),
            "boundaryBefore": "的东西。\n\n    (本章完)\n------------\n\n",
            "boundaryAfter": "第七十一章 勾心斗角（大章）",
        },
        "authorRegion": {
            "regionStart": None,   # 现场算
            "regionEnd": END,
            "note": "末尾作者区自「    PS：终于赶出来……」起到片末的分隔线为止；"
                    "叙事正文在「春日融融的阳光里，马车抵达王府。」之后的场景分隔符处结束。"
                    "本候选的叙事分区不引用作者区文字（构建期断言 A10）。",
        },
    }
    # 单元标题：现场定位并断言切片以它开头（A1 的第二重证据）
    title_ref = mkref(text, "q_title")
    if title_ref is None or title_ref["start"] != START:
        fail("A1 单元标题引文的 start 不等于任务声明的区间起点")
    else:
        cand["source"]["headQuote"] = title_ref
        cand["source"]["headQuoteNote"] = (
            "docs[0].text[%d:%d] == %r 逐字成立，且它正是任务声明的 start，"
            "这是「切片以本单元标题开头」这一自检的机器证据。"
            % (title_ref["start"], title_ref["end"], title_ref["quote"]))

    # 作者区起点现场定位
    ps = mkref(text, "q_ps")
    if ps:
        cand["authorRegion"]["regionStart"] = ps["start"]
        cand["authorRegion"]["boundaryTail"] = text[ps["start"] - 8:END]

    # ── tasks ──────────────────────────────────────────────────────────────
    tasks_out = []
    for t in TASKS:
        obj = {"id": t["id"], "who": t["who"]}
        per_task_intervals = []
        used_keys_task = []
        for f in ("objective", "obstacle", "action", "result", "cost"):
            field = t.get(f)
            expanded = mkfield(text, field)
            obj[f] = expanded
            obj[f + "Note"] = t.get(f + "Note")
            cq = t.get("costQuotes") if f == "cost" else None
            if f == "cost":
                # cost 栏：quotes 从 costQuotes 键解析（cost 本体恒为 None 或带引文）
                if t.get("costQuotes"):
                    expanded2 = mkfield(text, {"text": (field or {}).get("text"),
                                               "quotes": t["costQuotes"]},
                                        check_basis=False)
                    obj["costQuotes"] = expanded2["quotes"] if expanded2 else []
                    per_task_intervals += intervals(obj["costQuotes"])
                    used_keys_task += list(t["costQuotes"])
                else:
                    obj["costQuotes"] = []
                for extra in ("costNullReasonQuotes", "costNullReasonNote"):
                    if extra in t:
                        if extra.endswith("Quotes"):
                            ex = mkfield(text, {"text": "", "quotes": t[extra]},
                                         check_basis=False)
                            obj[extra] = ex["quotes"] if ex else []
                            per_task_intervals += intervals(obj[extra])
                            used_keys_task += list(t[extra])
                        else:
                            obj[extra] = t[extra]
            if expanded:
                per_task_intervals += intervals(expanded["quotes"])
                used_keys_task += list(field.get("quotes", []))
            else:
                if not t.get(f + "Note"):
                    fail("A5 %s.%s 为 null 但没有 %sNote" % (t["id"], f, f))
        # A4 键不重复
        dup = [k for k in set(used_keys_task) if used_keys_task.count(k) > 1]
        if dup:
            fail("A4 %s 五栏引文键重复：%s" % (t["id"], dup))
        # A4 区间两两不相交
        for i in range(len(per_task_intervals)):
            for j in range(i + 1, len(per_task_intervals)):
                if overlap(per_task_intervals[i], per_task_intervals[j]):
                    fail("A4 %s 栏间区间重叠：%s vs %s"
                         % (t["id"], per_task_intervals[i], per_task_intervals[j]))
        tasks_out.append(obj)
    cand["tasks"] = tasks_out

    # ── causeEdges ────────────────────────────────────────────────────────
    ce_out = []
    for e in CAUSE_EDGES:
        refs = [mkref(text, k) for k in e["quotes"]]
        refs = [r for r in refs if r]
        if len(refs) < 2:
            fail("A8 %s 引文少于 2 条" % e["id"])
        if not e.get("trigger"):
            fail("A8 %s 没有 trigger" % e["id"])
        ce_out.append({"id": e["id"], "from": e["from"], "to": e["to"],
                       "trigger": e["trigger"], "basis": e["basis"],
                       "claimKind": e.get("claimKind"),
                       "claimKindNote": e.get("claimKindNote"),
                       "quotes": refs})
    cand["causeEdges"] = ce_out

    rej_out = []
    for e in REJECTED_EDGES:
        refs = [mkref(text, k) for k in e["quotes"]]
        rej_out.append({"id": e["id"], "from": e["from"], "to": e["to"],
                        "why": e["why"], "quotes": [r for r in refs if r]})
    cand["rejectedEdges"] = rej_out

    # ── states ────────────────────────────────────────────────────────────
    st_out = []
    for s in STATES:
        o = {"id": s["id"], "who": s["who"]}
        for f in ("before", "after", "anchor"):
            o[f] = mkfield(text, s.get(f))
            o[f + "Note"] = s.get(f + "Note")
            if o[f] is None and not s.get(f + "Note"):
                fail("A11 %s.%s 为 null 但无 Note" % (s["id"], f))
        st_out.append(o)
    cand["states"] = st_out

    kg_out = []
    for k in KNOWLEDGE_GAPS:
        refs = [mkref(text, x) for x in k["quotes"]]
        kg_out.append({"id": k["id"], "about": k["about"], "whoKnows": k["whoKnows"],
                       "whoDoesNot": k["whoDoesNot"], "basis": k["basis"],
                       "keep": k.get("keep"), "quotes": [r for r in refs if r]})
    cand["knowledgeGaps"] = kg_out

    # ── foreshadows ───────────────────────────────────────────────────────
    fs_out = []
    for f in FORESHADOWS:
        setup = []
        for it in f["setup"]:
            r = mkref(text, it["key"])
            if r:
                r["why"] = it["why"]
                setup.append(r)
        payoff = []
        for it in f["payoff"]:
            r = mkref(text, it["key"])
            if r:
                r["why"] = it["why"]
                payoff.append(r)
        if f["resolved"] and not payoff:
            fail("A7 %s resolved=true 但没有 payoff" % f["id"])
        if f.get("unresolved") and f["resolved"]:
            fail("A7 %s 同时标 resolved 与 unresolved" % f["id"])
        fs_out.append({"id": f["id"], "name": f["name"], "resolved": f["resolved"],
                       "unresolved": bool(f.get("unresolved")), "basis": f["basis"],
                       "setup": setup, "payoff": payoff, "note": f["note"]})
    cand["foreshadows"] = fs_out

    nf_out = []
    for f in NOT_FORESHADOWS:
        nf_out.append({"id": f["id"], "name": f["name"], "why": f["why"],
                       "quotes": [r for r in (mkref(text, k) for k in f["quotes"]) if r]})
    cand["notForeshadows"] = nf_out

    # ── worldSettings ─────────────────────────────────────────────────────
    ws_out = []
    for w in WORLD_SETTINGS:
        o = {"id": w["id"], "kind": w["kind"], "name": w["name"], "basis": w["basis"],
             "explain": w["explain"],
             "quotes": [r for r in (mkref(text, k) for k in w["quotes"]) if r]}
        if w["kind"] == "rule":
            if w.get("institution") not in INST_LEGAL:
                fail("A6 %s institution 非法：%r" % (w["id"], w.get("institution")))
            o["institution"] = w.get("institution")
            o["institutionNote"] = w.get("institutionNote")
        elif w["kind"] == "place":
            if w.get("placeState") not in PLACE_LEGAL:
                fail("A6 %s placeState 非法：%r" % (w["id"], w.get("placeState")))
            o["placeState"] = w.get("placeState")
            o["placeStateNote"] = w.get("placeStateNote")
        elif w["kind"] == "item":
            st = w.get("itemStates") or []
            if not st or any(x not in ITEM_LEGAL for x in st):
                fail("A6 %s itemStates 非法：%r" % (w["id"], st))
            o["itemStates"] = st
            o["itemVerbs"] = w.get("itemVerbs")
            o["itemStatesNote"] = w.get("itemStatesNote")
        else:
            fail("A6 %s kind 非法" % w["id"])
        ws_out.append(o)
    cand["worldSettings"] = ws_out

    nws_out = []
    for w in NOT_WORLD_SETTINGS:
        nws_out.append({"id": w["id"], "name": w["name"], "why": w["why"],
                        "quotes": [r for r in (mkref(text, k) for k in w["quotes"]) if r]})
    cand["notWorldSettings"] = nws_out

    # ── themeReadings ─────────────────────────────────────────────────────
    th_out = []
    if len(THEME_READINGS) > 2:
        fail("A9 themeReadings 超过 2 条")
    for t in THEME_READINGS:
        for part in ("perspective", "support", "counter"):
            if not t.get(part):
                fail("A9 %s 缺 %s" % (t["id"], part))
        blob = json.dumps(t, ensure_ascii=False)
        for w in BANNED_THEME:
            if w in blob:
                fail("A9 %s 使用了被禁判据词：%s" % (t["id"], w))
        o = {"id": t["id"], "perspective": t["perspective"], "note": t.get("note")}
        for part in ("support", "counter"):
            src = t[part]
            o[part] = {"text": src["text"], "basis": src["basis"],
                       "quotes": [r for r in (mkref(text, k) for k in src["quotes"]) if r]}
        th_out.append(o)
    cand["themeReadings"] = th_out

    # ── 其余分区 ──────────────────────────────────────────────────────────
    cand["speechAsClueNotFact"] = [
        {"id": s["id"], "speaker": s["speaker"], "said": s["said"],
         "whyNotFact": s["whyNotFact"], "clueSupports": s["clueSupports"],
         "quote": mkref(text, s["quoteKey"])}
        for s in SPEECH_AS_CLUE_NOT_FACT]

    cand["textualNotes"] = [
        {"id": t["id"], "about": t["about"], "note": t["note"],
         "quotes": [r for r in (mkref(text, k) for k in t["quotes"]) if r]}
        for t in TEXTUAL_NOTES]

    cand["unknowns"] = UNKNOWNS
    cand["selfCritique"] = SELF_CRITIQUE

    # A10 叙事分区不得引用作者区引文
    body = json.dumps({k: cand[k] for k in
                       ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
                        "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
                        "themeReadings")}, ensure_ascii=False)
    if "PS：终于赶出来" in body:
        fail("A10 叙事分区引用了作者区文字")

    # A2/A12 引文键覆盖面
    all_keys = set(QUOTES) - {"q_negative_control"}
    unused = all_keys - USED_KEYS
    if unused:
        fail("A12 有引文写了但没用到：%s" % sorted(unused))
    missing = USED_KEYS - set(QUOTES)
    if missing:
        fail("A2 用到了不存在的引文键：%s" % sorted(missing))

    # ── 机器自检摘要 ──────────────────────────────────────────────────────
    def count_refs(o):
        n = 0
        if isinstance(o, dict):
            if "quote" in o and "start" in o and "end" in o:
                n += 1
            for v in o.values():
                n += count_refs(v)
        elif isinstance(o, list):
            for v in o:
                n += count_refs(v)
        return n

    total_refs = count_refs(cand)
    uniq = {}
    for k in USED_KEYS:
        q, kind, occ = QUOTES[k]
        for h in occ_in_slice(text, q):
            uniq[(h, h + len(q))] = True
    union_cp = sum(b - a for a, b in uniq)
    cand["machineSelfCheck"] = {
        "quoteObjects": total_refs,
        "uniqueQuoteIntervals": len(uniq),
        "unionCodepoints": union_cp,
        "sliceCodepoints": END - START,
        "coverageRatio": round(union_cp / float(END - START), 4),
        "negativeControl": "quotes_0299.py 的 q_negative_control（『许七安带着许铃音一起去了文会。』）"
                           "在探针里被断言 not-found，用来证明定位不是恒真通过；"
                           "它不计入本候选任何分区。",
        "assertionsRun": "A1–A12 全部在构建期执行；problems 见 validation.problems。",
        "semanticReviewClaimed": False,
    }
    cand["validation"] = {"problems": PROBLEMS, "at": "build-time"}

    if PROBLEMS:
        print("构建失败，%d 条问题（不产出候选）：" % len(PROBLEMS))
        for p in PROBLEMS:
            print("  [!]", p)
        return 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(cand, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("已写出：%s" % OUT)
    print("引文对象 %d 条；去重区间 %d 个；覆盖 %d/%d 码点（%.2f%%）"
          % (total_refs, len(uniq), union_cp, END - START, 100.0 * union_cp / (END - START)))
    print("分区：tasks=%d causeEdges=%d rejectedEdges=%d states=%d knowledgeGaps=%d "
          "foreshadows=%d notForeshadows=%d worldSettings=%d notWorldSettings=%d "
          "themeReadings=%d speechAsClue=%d textualNotes=%d unknowns=%d selfCritique=%d"
          % (len(cand["tasks"]), len(cand["causeEdges"]), len(cand["rejectedEdges"]),
             len(cand["states"]), len(cand["knowledgeGaps"]), len(cand["foreshadows"]),
             len(cand["notForeshadows"]), len(cand["worldSettings"]),
             len(cand["notWorldSettings"]), len(cand["themeReadings"]),
             len(cand["speechAsClueNotFact"]), len(cand["textualNotes"]),
             len(cand["unknowns"]), len(cand["selfCritique"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
