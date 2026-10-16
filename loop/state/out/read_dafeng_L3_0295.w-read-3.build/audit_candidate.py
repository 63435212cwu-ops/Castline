# -*- coding: utf-8 -*-
"""独立审计：**只从磁盘重读**候选 JSON 与 docs.json，不 import 内容/引文模块。

与构建期的区别（这是本脚本存在的理由）：
  · build_candidate.py 在**内存里**用自己解析出的偏移断言 text[s:e]==quote；
    若解析逻辑本身有 bug，构建期与产物会一起错。
  · 本脚本把候选文件当**陌生输入**：重新解析其中每一个 {quote,start,end}，
    重新断言 text[start:end]==quote、落在源区间内、sourceHash 一致，
    并独立复核六个必需分区键、五元组 null/Note 配对、五栏共用句与区间重叠、
    因果边方向与触发、伏笔 resolved/payoff 一致、worldSettings 三态字段、
    主题三件齐、以及**引文不落在作者区**。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0295.candidate.json"
START, END = 1286538, 1295556
AUTHOR_START = 1295417
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
COLS = ["objective", "obstacle", "action", "result", "cost"]
BASIS = {"explicit", "inferred", "derived", "unverified"}
ITEM_STATES = {"hold", "transfer", "use", "lose"}
PLACE_STATES = {"arrived", "mentioned"}
INSTITUTIONS = {"declared", "executed", "misunderstood"}

problems = []


def bad(msg):
    problems.append(msg)


def main():
    text = json.load(open(DOCS, encoding="utf-8"))[0]["text"]
    sl = text[START:END]
    if not CAND.exists():
        print("候选不存在：%s" % CAND)
        return 1
    cand = json.load(open(CAND, encoding="utf-8"))

    # 1) 源与区间的真实性
    actual_hash = hashlib.sha256(open(DOCS, "rb").read()).hexdigest()
    if actual_hash != SOURCE_HASH:
        bad("docs.json 哈希与任务声明不符：%s" % actual_hash)
    src = cand.get("source") or {}
    if src.get("sourceHash") != SOURCE_HASH:
        bad("候选 source.sourceHash 不是整个 docs.json 的哈希")
    if src.get("range") != [START, END]:
        bad("候选 source.range 与任务区间不符：%r" % (src.get("range"),))
    if not sl.startswith(cand.get("unitHead", "")):
        bad("切片不以 unitHead 开头")
    if hashlib.sha256(sl.encode("utf-8")).hexdigest() != src.get("sliceSha256"):
        bad("切片 sha256 与候选声明不符")
    if not (cand.get("semanticReview") == "not-performed"):
        bad("候选不应声称 semanticReview 完成：%r" % cand.get("semanticReview"))

    # 2) 顶层必需分区键（缺的分区即使为空也必须存在）
    for k in SECTIONS:
        if k not in cand:
            bad("缺顶层分区键：%s" % k)
        elif not isinstance(cand[k], list):
            bad("分区 %s 不是数组" % k)

    # 3) 遍历全部引文对象：重新定位
    total = 0
    author_region_hits = []
    author_keys = {q["quote"] for q in cand.get("authorRegionEvidence", [])
                   for q in (q.get("quotes") or [])}

    def walk(o, path="$"):
        nonlocal total
        if isinstance(o, dict):
            if "quote" in o and "start" in o and "end" in o:
                total += 1
                q, s, e = o["quote"], o["start"], o["end"]
                if not isinstance(s, int) or not isinstance(e, int):
                    bad("%s 偏移非整数" % path)
                    return
                if e - s != len(q):
                    bad("%s 长度不符：end-start=%d len=%d" % (path, e - s, len(q)))
                if text[s:e] != q:
                    bad("%s text[start:end] != quote" % path)
                if not (START <= s and e <= END):
                    bad("%s 越出源区间" % path)
                if s != START + sl.find(q):
                    bad("%s start 不等于 START+slice.find(quote)" % path)
                if o.get("sourceHash") != SOURCE_HASH:
                    bad("%s sourceHash 不符" % path)
                if s >= AUTHOR_START and q not in author_keys:
                    author_region_hits.append(path)
            for k, v in o.items():
                walk(v, "%s.%s" % (path, k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, "%s[%d]" % (path, i))

    walk(cand)
    if author_region_hits:
        bad("叙事引文落进作者区：%s" % author_region_hits[:5])

    # 4) 任务五元组：五栏齐全、null 必带 Note、栏间不共用句/不重叠
    for t in cand.get("tasks") or []:
        tid = t.get("id")
        for c in COLS:
            if c not in t:
                bad("%s 缺栏 %s" % (tid, c))
                continue
            if t[c] is None:
                if not t.get(c + "Note"):
                    bad("%s.%s 为 null 但无 %sNote" % (tid, c, c))
                if t.get(c + "Quotes"):
                    bad("%s.%s 为 null 却带引文" % (tid, c))
            else:
                if t[c].get("basis") not in BASIS:
                    bad("%s.%s basis 非法" % (tid, c))
                qs = t.get(c + "Quotes") or []
                if not qs:
                    bad("%s.%s 非 null 却无引文" % (tid, c))
                if not t[c].get("text"):
                    bad("%s.%s 无断言文本" % (tid, c))
        seen, spans = {}, []
        for c in COLS:
            for q in t.get(c + "Quotes") or []:
                if q["quote"] in seen:
                    bad("%s 五栏共用同一句：%s 与 %s" % (tid, c, seen[q["quote"]]))
                seen[q["quote"]] = c
                spans.append((c, q["start"], q["end"]))
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                c1, s1, e1 = spans[i]
                c2, s2, e2 = spans[j]
                if s1 < e2 and s2 < e1:
                    bad("%s 栏间区间重叠：%s/%s" % (tid, c1, c2))

    # 5) 因果边：方向 + 触发 + 引文
    for e in cand.get("causeEdges") or []:
        if not e.get("from") or not e.get("to"):
            bad("%s 因果边缺方向" % e.get("id"))
        if not e.get("trigger"):
            bad("%s 因果边缺 trigger（无机制不得连边）" % e.get("id"))
        if not e.get("quotes"):
            bad("%s 因果边无引文" % e.get("id"))
        if e.get("basis") not in BASIS:
            bad("%s 因果边 basis 非法" % e.get("id"))
    for r in cand.get("rejectedEdges") or []:
        if not r.get("why"):
            bad("%s 被拒边缺 why" % r.get("id"))

    # 6) 状态：前值/后值/锚点
    for s in cand.get("states") or []:
        for f in ("before", "after", "anchor"):
            if not s.get(f):
                bad("%s 状态缺 %s" % (s.get("id"), f))
        if not s.get("quotes"):
            bad("%s 状态无引文" % s.get("id"))

    # 7) 知识差：谁知/不知
    for g in cand.get("knowledgeGaps") or []:
        if not g.get("knows") or not g.get("does_not_know"):
            bad("%s 知识差未写清谁知/不知" % g.get("id"))

    # 8) 伏笔：resolved 必须有 payoff；unresolved 显式
    for f in cand.get("foreshadows") or []:
        st = f.get("status")
        if st not in ("resolved", "unresolved"):
            bad("%s 伏笔 status 非法：%r" % (f.get("id"), st))
        if not f.get("setup"):
            bad("%s 伏笔缺 setup" % f.get("id"))
        if len(f.get("quotes") or []) < 2:
            bad("%s 伏笔引文不足（铺设+回收）" % f.get("id"))
        if st == "resolved" and not f.get("payoff"):
            bad("%s 标 resolved 但无 payoff" % f.get("id"))
        if st == "unresolved" and not str(f.get("payoff") or "").startswith("unresolved"):
            bad("%s 标 unresolved 却写了实质 payoff" % f.get("id"))

    # 9) worldSettings：三态分流写进字段
    for w in cand.get("worldSettings") or []:
        k = w.get("kind")
        if k not in ("rule", "place", "item"):
            bad("%s kind 非法：%r" % (w.get("id"), k))
            continue
        if not w.get("explain") or not w.get("quotes"):
            bad("%s 缺 explain 或引文" % w.get("id"))
        if k == "place" and w.get("placeState") not in PLACE_STATES:
            bad("%s place 缺合法 placeState" % w.get("id"))
        if k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(x not in ITEM_STATES for x in st):
                bad("%s item itemStates 非法：%r" % (w.get("id"), st))
        if k == "rule" and w.get("institution") not in INSTITUTIONS:
            bad("%s rule 缺合法 institution" % w.get("id"))

    # 10) 主题：三件齐 + 未用被禁判据
    banned = re.compile(r"(事件密度|剧情点|死亡人数|篇幅中点|时间中点|三幕|英雄旅程)")
    for th in cand.get("themeReadings") or []:
        for f in ("perspective", "support", "counter"):
            if not th.get(f):
                bad("%s 主题缺 %s" % (th.get("id"), f))
        if len(th.get("quotes") or []) < 3:
            bad("%s 主题引文过少" % th.get("id"))
        blob = json.dumps(th, ensure_ascii=False)
        if banned.search(blob):
            bad("%s 主题使用了被禁的「高潮」判据" % th.get("id"))

    # 11) unknowns / selfCritique 存在且非空
    if not cand.get("unknowns"):
        bad("unknowns 为空")
    if not cand.get("selfCritique"):
        bad("selfCritique 为空")
    if cand.get("task") != "read:dafeng:L3:0295":
        bad("候选 task 字段不符：%r" % cand.get("task"))

    print("引文对象 %d 条（独立重定位）；分区 %d 个；问题 %d 条"
          % (total, len(SECTIONS), len(problems)))
    for p in problems:
        print("  [问题]", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
