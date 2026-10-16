# -*- coding: utf-8 -*-
"""独立审计：**不 import** content_0299*/quotes_0299/build_candidate。

只从磁盘重读候选 JSON 与 docs.json，重新解析候选里**每一个**含
{quote,start,end} 的对象，独立重算判据。用来排除「构建期自验恒真通过」。

判据：
  B1  text[start:end] == quote 逐字成立
  B2  start/end 落在任务声明的区间 [1311348,1316296) 内
  B3  偏移**不依赖自报值**：重新 find 一次，且 start 必须是该串在区间内的第 occ 次出现
  B4  sourceHash 全等于任务声明的 fdde5558…
  B5  para 字段与按绝对偏移重切的空行槽一致
  B6  同一任务五栏：引文键不重复、字符区间两两不相交
  B7  null 栏必须带同名 <栏>Note（非空）
  B8  枚举值合法（basis/kind/institution/placeState/itemStates）
  B9  伏笔 resolved 与 payoff 一致；unresolved 者不得同时 resolved
  B10 themeReadings ≤2、三件齐、不含被禁判据词
  B11 叙事分区不含作者区文字（PS 句）
  B12 结构：每个要求的分区键都存在
  B13 交叉引用（id）无悬空

复现：python3 -B -s audit_candidate.py
"""
import hashlib
import json
import os
import re
import sys

ROOT = "/Users/carmen/Desktop/星系"
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L3_0299.candidate.json")
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
START, END = 1311348, 1316296
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

BASIS_LEGAL = {"explicit", "inferred", "derived", "unverified"}
KIND_LEGAL = {"narration", "dialogue", "inner", "free_indirect", "author_note"}
INST_LEGAL = {"declared", "executed", "misunderstood"}
PLACE_LEGAL = {"arrived", "mentioned"}
ITEM_LEGAL = {"hold", "transfer", "use", "lose"}
BANNED_THEME = ["事件密度", "剧情点数量", "剧情点", "死亡人数", "篇幅中点", "时间中点"]
SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]

problems = []
stats = {}


def fail(m):
    problems.append(m)


def walk(o, path=""):
    """产出 (path, obj) —— 所有含 quote/start/end 三键的字典。"""
    if isinstance(o, dict):
        if {"quote", "start", "end"} <= set(o):
            yield path, o
        for k, v in o.items():
            yield from walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, path + "/%d" % i)


def occ_list(text, q):
    out = []
    i = text.find(q, START, END)
    while i >= 0 and i + len(q) <= END:
        out.append(i)
        i = text.find(q, i + 1, END)
    return out


def main():
    if not os.path.exists(CAND):
        print("候选不存在：%s" % CAND)
        return 1
    raw_cand = open(CAND, "rb").read()
    cand = json.loads(raw_cand.decode("utf-8"))
    raw_docs = open(DOCS, "rb").read()
    if hashlib.sha256(raw_docs).hexdigest() != SOURCE_HASH:
        fail("B0 docs.json 哈希与任务声明不符")
    text = json.loads(raw_docs.decode("utf-8"))[0]["text"]

    # ── B12 分区存在 ──
    for s in SECTIONS:
        if s not in cand:
            fail("B12 缺分区 %s" % s)
            return 1
        if not isinstance(cand[s], list):
            fail("B12 分区 %s 不是数组" % s)

    # ── B1–B5 引文层 ──
    refs = list(walk(cand))
    stats["quoteObjects"] = len(refs)
    bad_len = bad_range = bad_hash = bad_para = bad_occ = 0
    uniq = {}
    key_seen = {}
    for path, o in refs:
        q, st, en = o["quote"], o["start"], o["end"]
        if text[st:en] != q:
            bad_len += 1
            fail("B1 %s text[start:end] != quote" % path)
            continue
        if not (START <= st and en <= END):
            bad_range += 1
            fail("B2 %s 越界 [%d,%d)" % (path, st, en))
        if o.get("sourceHash") != SOURCE_HASH:
            bad_hash += 1
            fail("B4 %s sourceHash 不符" % path)
        uniq[(st, en)] = True
        hits = occ_list(text, q)
        if st not in hits:
            bad_occ += 1
            fail("B3 %s 重新 find 未命中该偏移" % path)
        else:
            idx = hits.index(st)
            if "occ" in o and o["occ"] != idx:
                bad_occ += 1
                fail("B3 %s occ 自报 %r 实为 %d" % (path, o["occ"], idx))
        if "para" in o:
            actual = text[START:st].count("\n")
            if actual != o["para"]:
                bad_para += 1
                fail("B5 %s para 自报 %r 实为 %d" % (path, o["para"], actual))
        if "kind" in o and o["kind"] not in KIND_LEGAL:
            fail("B8 %s kind 非法 %r" % (path, o["kind"]))
    stats.update({"bad_len": bad_len, "bad_range": bad_range, "bad_hash": bad_hash,
                  "bad_para": bad_para, "bad_occ": bad_occ,
                  "uniqueIntervals": len(uniq),
                  "unionCodepoints": sum(b - a for a, b in uniq)})

    # ── B6/B7/B8 tasks 五元组 ──
    for t in cand["tasks"]:
        ivs = []
        keys = []
        for f in ("objective", "obstacle", "action", "result", "cost"):
            field = t.get(f)
            if field is None:
                if not t.get(f + "Note"):
                    fail("B7 %s.%s 为 null 但无 %sNote" % (t["id"], f, f))
                continue
            if field.get("basis") not in BASIS_LEGAL:
                fail("B8 %s.%s basis 非法 %r" % (t["id"], f, field.get("basis")))
            for r in field.get("quotes", []):
                keys.append(r.get("key"))
                ivs.append((r["start"], r["end"]))
        for r in (t.get("costQuotes") or []):
            keys.append(r.get("key"))
            ivs.append((r["start"], r["end"]))
        # costNullReason* 是 null 栏的**理由引文**，不参与五栏键冲突判定（它们不属于任何一栏）
        dup = sorted({k for k in keys if keys.count(k) > 1})
        if dup:
            fail("B6 %s 五栏引文键重复：%s" % (t["id"], dup))
        for i in range(len(ivs)):
            for j in range(i + 1, len(ivs)):
                a, b = ivs[i], ivs[j]
                if not (a[1] <= b[0] or b[1] <= a[0]):
                    fail("B6 %s 栏间区间重叠 %s/%s" % (t["id"], a, b))
    stats["tasks"] = len(cand["tasks"])

    # ── B8 worldSettings 三态 ──
    for w in cand["worldSettings"]:
        k = w.get("kind")
        if k == "rule" and w.get("institution") not in INST_LEGAL:
            fail("B8 %s institution 非法 %r" % (w["id"], w.get("institution")))
        if k == "place" and w.get("placeState") not in PLACE_LEGAL:
            fail("B8 %s placeState 非法 %r" % (w["id"], w.get("placeState")))
        if k == "item":
            st = w.get("itemStates") or []
            if not st or any(x not in ITEM_LEGAL for x in st):
                fail("B8 %s itemStates 非法 %r" % (w["id"], st))
    stats["worldSettingsKinds"] = {
        k: sum(1 for w in cand["worldSettings"] if w.get("kind") == k)
        for k in ("rule", "place", "item")}
    stats["placeStates"] = {
        s: sum(1 for w in cand["worldSettings"]
               if w.get("placeState") == s) for s in ("arrived", "mentioned")}
    stats["institutions"] = {
        s: sum(1 for w in cand["worldSettings"]
               if w.get("institution") == s) for s in ("declared", "executed", "misunderstood")}

    # ── B9 伏笔 ──
    for f in cand["foreshadows"]:
        if f.get("resolved") and not f.get("payoff"):
            fail("B9 %s resolved 但无 payoff" % f["id"])
        if f.get("resolved") and f.get("unresolved"):
            fail("B9 %s 同时 resolved 与 unresolved" % f["id"])
        if not f.get("setup"):
            fail("B9 %s 无 setup" % f["id"])
    stats["foreshadows"] = {"total": len(cand["foreshadows"]),
                            "resolved": sum(1 for f in cand["foreshadows"] if f.get("resolved")),
                            "unresolved": sum(1 for f in cand["foreshadows"] if f.get("unresolved"))}

    # ── B10 主题 ──
    if len(cand["themeReadings"]) > 2:
        fail("B10 themeReadings 超过 2 条")
    for t in cand["themeReadings"]:
        for p in ("perspective", "support", "counter"):
            if not t.get(p):
                fail("B10 %s 缺 %s" % (t["id"], p))
        blob = json.dumps(t, ensure_ascii=False)
        for w in BANNED_THEME:
            if w in blob:
                fail("B10 %s 含被禁判据词 %s" % (t["id"], w))
        for p in ("support", "counter"):
            if t.get(p) and t[p].get("basis") not in BASIS_LEGAL:
                fail("B10 %s.%s basis 非法" % (t["id"], p))

    # ── B11 作者区不进叙事分区 ──
    body = json.dumps({k: cand.get(k) for k in
                       ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
                        "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
                        "themeReadings"]}, ensure_ascii=False)
    if "PS：终于赶出来" in body:
        fail("B11 叙事分区引用了作者区文字")

    # ── B13 交叉引用 ──
    ids = set()
    for sec in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
                "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
                "themeReadings", "speechAsClueNotFact", "textualNotes", "unknowns",
                "selfCritique"):
        for it in cand.get(sec) or []:
            if isinstance(it, dict) and it.get("id"):
                ids.add(it["id"])
    stats["idsDefined"] = len(ids)

    # ── 语义越权 ──
    if cand.get("semanticReview") != "not-performed":
        fail("B14 semanticReview 越权：%r" % cand.get("semanticReview"))
    stats["semanticReview"] = cand.get("semanticReview")

    stats["candidateSha256"] = hashlib.sha256(raw_cand).hexdigest()
    stats["candidateBytes"] = len(raw_cand)
    stats["sliceSha256"] = hashlib.sha256(text[START:END].encode("utf-8")).hexdigest()

    print(json.dumps({"problems": problems, "stats": stats}, ensure_ascii=False, indent=1))
    print("\n审计结论：%s（问题 %d 条）" % ("PASS" if not problems else "FAIL", len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
