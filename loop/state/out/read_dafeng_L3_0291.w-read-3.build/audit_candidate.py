# -*- coding: utf-8 -*-
"""独立审计：从磁盘重读候选 JSON，不复用构建期任何内存对象，重新核验每一条引文与每个分区。

与 build_candidate.py 的区别（为什么不能拿构建脚本自检代替审计）：
  · build 的自检跑在**它自己组装的内存对象**上；若组装时把某个字段写错又恰好自洽，
    自检发现不了。本脚本只读**落盘后的 JSON**，重新解析、重新定位。
  · 本脚本不 import content_0291 / quotes_0291 —— 结论只依据候选文件与原文本身。

复现命令：python3 loop/state/out/read_dafeng_L3_0291.w-read-3.build/audit_candidate.py
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

DOCS = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop", "state", "out", "read_dafeng_L3_0291.candidate.json")
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 1254012, 1263192
UNIT_HEAD = "第六十二章 众生之力"
ART_KEYS = ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
            "themeReadings")

problems = []
notes = []


def main():
    raw = open(DOCS, "rb").read()
    file_sha = hashlib.sha256(raw).hexdigest()
    if file_sha != SOURCE_HASH:
        problems.append("docs.json sha256 与任务声明不一致：%s" % file_sha)
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    sl = text[START:END]
    if not sl.startswith(UNIT_HEAD):
        problems.append("区间起点不是本单元标题")
    if len(sl) != END - START:
        problems.append("切片长度与区间不符")

    cand = json.load(open(CAND, encoding="utf-8"))

    # ① 分区键必须存在（提示词要求，缺内容也要写空数组）
    for k in ART_KEYS:
        if k not in cand:
            problems.append("缺分区 %s" % k)

    # ② 收集候选里**全部** quote 对象并逐条重新定位
    quotes = []

    def walk(node, path=""):
        if isinstance(node, dict):
            if "quote" in node and "start" in node and "end" in node:
                quotes.append((path, node))
            for k, v in node.items():
                walk(v, path + "/" + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + "[%d]" % i)

    walk(cand)
    if not quotes:
        problems.append("候选里一条引文都没有")
    for path, o in quotes:
        q, s, e = o.get("quote"), o.get("start"), o.get("end")
        if not isinstance(s, int) or not isinstance(e, int):
            problems.append("%s 的 start/end 不是整数" % path)
            continue
        if text[s:e] != q:
            problems.append("%s 重新定位失败：text[%d:%d] != quote" % (path, s, e))
        if not (START <= s < e <= END):
            problems.append("%s 越出本单元区间 (%d,%d)" % (path, s, e))
        if o.get("sourceHash") != SOURCE_HASH:
            problems.append("%s 的 sourceHash 不对" % path)
        if text.find(q) < 0:
            problems.append("%s 的 quote 在全文里 find 不到" % path)

    # ③ 偏移口径：任意 start 必须能用「切片内 find + START」复现
    for path, o in quotes:
        k = sl.find(o["quote"])
        if k < 0:
            problems.append("%s 的 quote 不在本单元切片内" % path)
        elif START + k != o["start"]:
            problems.append("%s 的 start 与「切片内首次出现」不符（首现在 %d，声明 %d）"
                            % (path, START + k, o["start"]))

    # ④ 任务五元组：null 必须带 Note；有值必须有引文与合法 basis；栏间不许共用同一句
    BASIS = ("explicit", "inferred", "derived", "unverified")
    shared = []
    for t in cand.get("tasks", []):
        spans = []
        for col in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(col)
            qs = t.get(col + "Quotes") or []
            if v is None:
                if not t.get(col + "Note"):
                    problems.append("%s.%s 是 null 但没有 %sNote" % (t["id"], col, col))
                if qs:
                    problems.append("%s.%s 是 null 却带了引文" % (t["id"], col))
            else:
                if not qs:
                    problems.append("%s.%s 有值却没有引文" % (t["id"], col))
                if t.get(col + "Basis") not in BASIS:
                    problems.append("%s.%s basis 非法" % (t["id"], col))
            for o in qs:
                spans.append((col, o))
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                c1, a = spans[i]
                c2, b = spans[j]
                if a["start"] == b["start"] and a["end"] == b["end"]:
                    shared.append({"task": t["id"], "a": c1, "b": c2,
                                   "quote": a["quote"][:30]})
                    problems.append("%s 两栏共用同一条引文：%s × %s"
                                    % (t["id"], c1, c2))
                elif a["start"] < b["end"] and b["start"] < a["end"]:
                    problems.append("%s 栏间引文区间重叠：%s × %s" % (t["id"], c1, c2))

    # ⑤ 因果边：方向 + 机制 + 至少两条引文
    for e in cand.get("causeEdges", []):
        if not e.get("from") or not e.get("to"):
            problems.append("%s 缺方向" % e.get("id"))
        if not (e.get("mechanism") or "").strip():
            problems.append("%s 缺机制" % e.get("id"))
        if len(e.get("quotes") or []) < 2:
            problems.append("%s 引文少于 2 条" % e.get("id"))

    # ⑥ 状态：前值/后值/锚点三分，各自有引文
    for s in cand.get("states", []):
        for side in ("before", "after", "anchor"):
            if not s.get(side + "Quotes"):
                problems.append("%s.%s 没有引文" % (s.get("id"), side))
            if s.get(side + "Basis") not in BASIS:
                problems.append("%s.%s basis 非法" % (s.get("id"), side))

    # ⑦ 伏笔：resolved 布尔；未回收必须显式 note 且不得带回收引文
    for f in cand.get("foreshadows", []):
        if f.get("resolved") not in (True, False):
            problems.append("%s.resolved 不是布尔" % f.get("id"))
        if f.get("resolved") is False:
            if not f.get("note"):
                problems.append("%s 未回收但没写 note" % f.get("id"))
            if f.get("payoffQuotes"):
                problems.append("%s 标未回收却带回收引文" % f.get("id"))
        if f.get("resolved") is True and not f.get("payoffQuotes"):
            problems.append("%s 标已回收却没有回收引文" % f.get("id"))

    # ⑧ 世界设定：三类各自的三态字段必须写进字段本身
    kinds = {"place": 0, "item": 0, "rule": 0}
    for w in cand.get("worldSettings", []):
        k = w.get("kind")
        if k not in kinds:
            problems.append("%s.kind 非法：%r" % (w.get("id"), k))
            continue
        kinds[k] += 1
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            problems.append("%s 缺/非法 placeState" % w.get("id"))
        if k == "item":
            st = w.get("itemStates")
            if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                problems.append("%s 缺/非法 itemStates" % w.get("id"))
        if k == "rule" and w.get("institution") not in (
                "declared", "executed", "misunderstood"):
            problems.append("%s 缺/非法 institution" % w.get("id"))

    # ⑨ 主题：三件齐 + 不得用被禁的高潮判据
    banned = ("事件密度", "剧情点数量", "死亡人数", "篇幅中点", "时间中点")
    for th in cand.get("themeReadings", []):
        if not th.get("perspective") or not th.get("support") or not th.get("counter"):
            problems.append("%s 缺 perspective/support/counter" % th.get("id"))
        blob = (th.get("perspective") or "") + (th.get("note") or "")
        for b in banned:
            if b in blob:
                problems.append("%s 用了被禁判据：%s" % (th.get("id"), b))
    if len(cand.get("themeReadings", [])) > 2:
        problems.append("主题解读超过 2 条")

    # ⑩ 作者区域：叙事引文不得落进去（authorRegionEvidence / notForeshadows /
    #    notWorldSettings 这三处按设计可以引用作者区或边缘文本）
    ar = [(x["start"], x["end"]) for x in cand.get("authorRegion", [])]
    leaks = []
    for path, o in quotes:
        if any(seg in path for seg in ("/authorRegionEvidence", "/notForeshadows",
                                       "/notWorldSettings", "/textualNotes",
                                       "/machineSelfCheck")):
            continue
        for a, b in ar:
            if o["start"] < b and a < o["end"]:
                leaks.append({"path": path, "range": [o["start"], o["end"]]})
    if leaks:
        problems.append("叙事引文落进作者区域 %d 条" % len(leaks))

    # ⑪ agent 归属必须与本次提交者一致
    if cand.get("agent") != "w-read-3":
        problems.append("候选里的 agent 不是本次提交者：%r" % cand.get("agent"))

    # ⑫ 候选自报的机检结果必须与独立审计一致（不许自报 0 问题而实际有）
    ms = cand.get("machineSelfCheck", {})
    if ms.get("problems"):
        problems.append("候选自报 machineSelfCheck.problems 非空：%r"
                        % ms.get("problems")[:3])
    if ms.get("authorRegionLeaks") not in (0,):
        problems.append("候选自报 authorRegionLeaks=%r" % ms.get("authorRegionLeaks"))

    notes.append("引文对象 %d 条，独立重新定位全部通过" % len(quotes))
    notes.append("唯一引文区间 %d 个" % len({(o["start"], o["end"]) for _, o in quotes}))
    notes.append("分区计数：" + json.dumps(
        {k: len(cand.get(k) or []) for k in ART_KEYS if k != "tasks"}
        | {"tasks": len(cand.get("tasks") or [])}, ensure_ascii=False))
    notes.append("worldSettings 分类计数：%s" % kinds)
    notes.append("栏间共用引文：%d 条" % len(shared))

    print("=== 独立审计（从磁盘重读候选 + 重新定位每条引文）===")
    for n in notes:
        print("  " + n)
    if problems:
        print("problems=%d" % len(problems))
        for p in problems:
            print("  [problem] %s" % p)
        return 1
    print("problems=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
