# -*- coding: utf-8 -*-
"""独立复算：不 import build_candidate.py，从零重验候选里的每一条硬约束。

为什么另写一份：build_candidate.py 的机检和它自己的定位逻辑共用同一段代码，
共用代码的错误会同时骗过两边。这里改用 `re.finditer` 从原文里**重新**找引文、
重新算偏移，逐条与候选里声明的 start/end 对齐。

复现：python3 loop/state/out/read_dafeng_L3_0287.w-read-2.build/verify_independent.py
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

DOCS = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop", "state", "out", "read_dafeng_L3_0287.candidate.json")
START, END = 1230135, 1234614
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
AUTHOR_REGION = [(1234517, 1234614)]
UNIT_HEAD = "第五十八章 五百年前的交易"

fail = []


def check(cond, msg):
    if not cond:
        fail.append(msg)


RAW = open(DOCS, "rb").read()
check(hashlib.sha256(RAW).hexdigest() == SOURCE_HASH, "docs.json 文件哈希与任务声明不符")
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[START:END]
check(SLICE.startswith(UNIT_HEAD), "切片不以本单元标题开头")
check(len(SLICE) == END - START, "切片长度与区间不符")

cand = json.load(open(CAND, encoding="utf-8"))
check(cand["source"]["sourceHash"] == SOURCE_HASH, "候选 sourceHash 不符")
check(hashlib.sha256(SLICE.encode("utf-8")).hexdigest() == cand["source"]["sliceSha256"],
      "候选 sliceSha256 与独立复算不符")
check(cand["source"]["range"] == [START, END], "候选 range 不符")
check(cand["machineSelfCheck"]["problems"] == [], "候选自检 problems 非空")

# ── 遍历每个含 quote/start/end 的对象，用 finditer 独立重定位
quotes = []


def walk(n, path=""):
    if isinstance(n, dict):
        if "quote" in n and "start" in n and "end" in n:
            quotes.append((path, n))
        for k, v in n.items():
            walk(v, path + "/" + k)
    elif isinstance(n, list):
        for i, v in enumerate(n):
            walk(v, path + "[%d]" % i)


walk(cand)
bad_verbatim = bad_range = bad_hash = bad_occ = 0
for path, o in quotes:
    if TEXT[o["start"]:o["end"]] != o["quote"]:
        bad_verbatim += 1
        fail.append("逐字不符：%s" % path)
    if not (START <= o["start"] < o["end"] <= END):
        bad_range += 1
        fail.append("越界：%s" % path)
    if o["sourceHash"] != SOURCE_HASH:
        bad_hash += 1
    # 独立重定位：这条引文在切片内出现的所有位置，必须包含声明的那一处
    hits = [m.start() + START for m in
            __import__("re").finditer(__import__("re").escape(o["quote"]), SLICE)]
    if o["start"] not in hits:
        bad_occ += 1
        fail.append("finditer 重定位失败：%s" % path)
    if o.get("occurrencesInRange") != len(hits):
        fail.append("occurrencesInRange 不符：%s 声明%s 实得%d"
                    % (path, o.get("occurrencesInRange"), len(hits)))

check(bad_verbatim == 0, "有引文不是逐字命中")
check(bad_range == 0, "有引文越出区间")
check(bad_hash == 0, "有引文 sourceHash 不对")
check(bad_occ == 0, "有引文无法独立重定位")

# ── 叙事引文不得落在作者区域
leaks = [(p, o) for p, o in quotes
         if "/authorRegionEvidence" not in p and "/notForeshadows" not in p
         and "/notWorldSettings" not in p
         and any(o["start"] < b and o["end"] > a for a, b in AUTHOR_REGION)]
check(not leaks, "叙事引文落进作者区域：%s" % leaks[:3])

# ── 任务五元组：栏间区间不重叠、不共用
overlaps = shared = 0
for t in cand["tasks"]:
    spans = []
    for col in ("objective", "obstacle", "action", "result", "cost"):
        for o in (t.get(col + "Quotes") or []):
            spans.append((col, o))
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            c1, a = spans[i]
            c2, b = spans[j]
            if a["start"] < b["end"] and b["start"] < a["end"]:
                overlaps += 1
                fail.append("%s 栏间重叠 %s×%s" % (t["id"], c1, c2))
            if (a["start"], a["end"]) == (b["start"], b["end"]):
                shared += 1
                fail.append("%s 栏间共用 %s×%s" % (t["id"], c1, c2))
    for col in ("objective", "obstacle", "action", "result", "cost"):
        if t.get(col) is None:
            check(bool(t.get(col + "Note")), "%s.%s null 无 Note" % (t["id"], col))
            check(not (t.get(col + "Quotes")), "%s.%s null 却带引文" % (t["id"], col))
        else:
            check(bool(t.get(col + "Quotes")), "%s.%s 有值无引文" % (t["id"], col))
            check(t.get(col + "Basis") in ("explicit", "inferred", "derived", "unverified"),
                  "%s.%s basis 非法" % (t["id"], col))

# ── 枚举值
for w in cand["worldSettings"]:
    if w["kind"] == "place":
        check(w.get("placeState") in ("arrived", "mentioned"), "%s placeState 非法" % w["id"])
    elif w["kind"] == "item":
        check(bool(w.get("itemStates")), "%s 缺 itemStates" % w["id"])
        for st in w["itemStates"]:
            check(st in ("hold", "transfer", "use", "lose"), "%s itemState 非法 %s" % (w["id"], st))
    elif w["kind"] == "rule":
        check(w.get("institution") in ("declared", "executed", "misunderstood"),
              "%s institution 非法" % w["id"])
    else:
        fail.append("%s kind 非法 %s" % (w["id"], w["kind"]))

# ── 伏笔：未回收必须有 note 且无回收引文
for f in cand["foreshadows"]:
    if f["resolved"] is False:
        check(bool(f.get("note")), "%s 未回收无 note" % f["id"])
        check(not f.get("payoffQuotes"), "%s 未回收却带回收引文" % f["id"])
    else:
        check(bool(f.get("payoffQuotes")), "%s 已回收但无回收引文" % f["id"])

# ── 主题三件齐
for th in cand["themeReadings"]:
    check(bool(th["perspective"] and th["support"] and th["counter"]),
          "%s 缺 perspective/support/counter" % th["id"])

# ── 受保护路径：候选里不得声明改动（本任务只写 loop/state/out/）
check(cand["semanticReview"] == "not-performed", "semanticReview 被写成了完成态")
check(cand["agent"] == "w-read-2", "agent 字段不符")
check(cand["task"] == "read:dafeng:L3:0287", "task 字段不符")

print("引文对象 %d 条（finditer 独立重定位）" % len(quotes))
print("任务 %d 条 / 因果边 %d / 被拒边 %d / 状态 %d / 知识差 %d / 伏笔 %d / 设定 %d / 主题 %d"
      % (len(cand["tasks"]), len(cand["causeEdges"]), len(cand["rejectedEdges"]),
         len(cand["states"]), len(cand["knowledgeGaps"]), len(cand["foreshadows"]),
         len(cand["worldSettings"]), len(cand["themeReadings"])))
print("栏间重叠 %d / 栏间共用 %d / 作者区域泄漏 %d" % (overlaps, shared, len(leaks)))
print("FAILURES: %d" % len(fail))
for f in fail:
    print("  [fail] %s" % f)
sys.exit(1 if fail else 0)
