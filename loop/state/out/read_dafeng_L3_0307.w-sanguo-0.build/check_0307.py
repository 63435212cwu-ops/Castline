#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核 read:dafeng:L3:0307 的候选文件（**从盘上读回**，不信任构建期内存）。

与 build_0307.py 的分工：build 脚本在写盘前自检；本脚本只读已落盘的
`read_dafeng_L3_0307.candidate.json`，用**另写一遍**的判据复核，所以
构建脚本里的一个共同 bug 不会同时骗过两边（例如把区间写错口径、
把 hash 抄错、把引文写成近似而非逐字）。

用法：
  python3 -B -s loop/state/out/read_dafeng_L3_0307.w-sanguo-0.build/check_0307.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0307.candidate.json"
REPORT = Path(__file__).resolve().parent / "check_report.json"

START, END = 1366953, 1373655
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
SLICE_SHA = "6b67dd884d3f134b74ac4fa03e18818afc91aaae8d25082585dbfa2d0cfadd77"

problems: list[str] = []
stats: dict[str, int] = {}


def bad(msg: str) -> None:
    problems.append(msg)


doc = json.loads(DOCS.read_text("utf-8"))
text = doc[0]["text"]
sl = text[START:END]
cand = json.loads(CAND.read_text("utf-8"))

# ── 0. 源与口径 ────────────────────────────────────────────────────────────
actual_src = hashlib.sha256(DOCS.read_bytes()).hexdigest()
if actual_src != SOURCE_HASH:
    bad("docs.json 的 sha256 与任务声明不符：%s" % actual_src)
    stats["sourceHash"] = 0
else:
    stats["sourceHash"] = 1
if hashlib.sha256(sl.encode("utf-8")).hexdigest() != SLICE_SHA:
    bad("切片 sha256 与构建期不一致（全文被改过？）")
if text[START:START + 9] != "第七十八章 你来啦":
    bad("切片不以单元标题开头：%r" % text[START:START + 9])
if len(sl) != 6702:
    bad("切片长度不是 6702：%d" % len(sl))
src = cand.get("source", {})
if src.get("range") != [START, END]:
    bad("source.range 与任务区间不符：%r" % (src.get("range"),))
if src.get("sourceHash") != SOURCE_HASH:
    bad("source.sourceHash 写错")
if src.get("sliceSha256") != SLICE_SHA:
    bad("source.sliceSha256 写错")

# ── 1. 分区齐全 ────────────────────────────────────────────────────────────
for key in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    if key not in cand:
        bad("缺分区 %s" % key)
    elif not isinstance(cand[key], list):
        bad("分区 %s 不是数组" % key)
stats["tasks"] = len(cand.get("tasks", []))
stats["causeEdges"] = len(cand.get("causeEdges", []))
stats["states"] = len(cand.get("states", []))
stats["foreshadows"] = len(cand.get("foreshadows", []))
stats["worldSettings"] = len(cand.get("worldSettings", []))
stats["themeReadings"] = len(cand.get("themeReadings", []))

# ── 2. 全部引文：逐字 + 落在区间内 + hash ───────────────────────────────────
quotes: list[dict] = []


def walk(node) -> None:
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            quotes.append(node)
        for v in node.values():
            walk(v)
    elif isinstance(node, list):
        for v in node:
            walk(v)


walk(cand)
stats["quotes"] = len(quotes)
if len(quotes) < 40:
    bad("引文总数偏少：%d" % len(quotes))
for q in quotes:
    tag = q.get("key") or q.get("quote", "")[:12]
    if not isinstance(q.get("start"), int) or not isinstance(q.get("end"), int):
        bad("引文 %s 的 start/end 不是整数" % tag)
        continue
    if not (START <= q["start"] < q["end"] <= END):
        bad("引文 %s 越出切片 [%d,%d)：[%d,%d)" % (tag, START, END, q["start"], q["end"]))
    if text[q["start"]:q["end"]] != q["quote"]:
        bad("引文 %s 不逐字命中：期望 %r 实际 %r"
            % (tag, q["quote"][:24], text[q["start"]:q["end"]][:24]))
    if q["quote"] not in sl:
        bad("引文 %s 在切片里 find 不到" % tag)
    if q.get("sourceHash") != SOURCE_HASH:
        bad("引文 %s 的 sourceHash 不符" % tag)

# 同一 key 必须始终指向同一区间（防止 key 复用导致证据漂移）
by_key: dict[str, set[tuple[int, int]]] = {}
for q in quotes:
    if q.get("key"):
        by_key.setdefault(q["key"], set()).add((q["start"], q["end"]))
for k, spans in by_key.items():
    if len(spans) > 1:
        bad("引文 key %s 指向多个区间：%s" % (k, sorted(spans)))
stats["uniqueQuoteKeys"] = len(by_key)

# ── 3. 任务五栏 ────────────────────────────────────────────────────────────
COLS = ("objective", "obstacle", "action", "result", "cost")
for t in cand.get("tasks", []):
    tid = t.get("id")
    if not t.get("who"):
        bad("%s 缺 who" % tid)
    spans: list[tuple[int, int, str]] = []
    for col in COLS:
        entry = t.get(col)
        note = t.get(col + "Note")
        if entry is None:
            if not (isinstance(note, str) and len(note.strip()) >= 10):
                bad("%s.%s 为 null 但缺少说明性的 Note" % (tid, col))
            continue
        if not isinstance(note, str) or not note.strip():
            bad("%s.%s 非 null 却无 Note" % (tid, col))
        if entry.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
            bad("%s.%s 的 basis 非法：%r" % (tid, col, entry.get("basis")))
        qlist = entry.get("quotes") or []
        if not qlist:
            bad("%s.%s 没有任何引文" % (tid, col))
        for q in qlist:
            spans.append((q["start"], q["end"], "%s:%s" % (col, q.get("key"))))
    # 区间两两不重叠
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b = spans[i], spans[j]
            if not (a[1] <= b[0] or a[0] >= b[1]):
                bad("%s 五栏区间重叠：%s 与 %s" % (tid, a[2], b[2]))
    # 句级：同一自然句不得被两栏引用
    sent_of: dict[tuple[int, int], set[str]] = {}
    for a, b, tag in spans:
        col = tag.split(":", 1)[0]
        chunk = text[a:b]
        cur = 0
        for m in re.finditer(r"[。！？…”]+", chunk):
            if m.end() > cur:
                sent_of.setdefault((a + cur, a + m.end()), set()).add(col)
                cur = m.end()
        if cur < len(chunk):
            sent_of.setdefault((a + cur, b), set()).add(col)
    for sid, cols in sent_of.items():
        if len(cols) > 1:
            bad("%s 同一句话被多栏共用：%s ← %s" % (tid, text[sid[0]:sid[1]][:26], "/".join(sorted(cols))))
    filled = sum(1 for c in COLS if t.get(c) is not None)
    if filled < 3:
        bad("%s 只有 %d 栏有依据" % (tid, filled))

# ── 4. 因果边必须有方向与触发 ──────────────────────────────────────────────
for e in cand.get("causeEdges", []):
    if not e.get("from") or not e.get("to"):
        bad("%s 因果边缺 from/to" % e.get("id"))
    if len((e.get("trigger") or "").strip()) < 20:
        bad("%s 的 trigger 太短/缺失，无法看出机制" % e.get("id"))
    if not (e.get("quotes") or []):
        bad("%s 因果边没有引文" % e.get("id"))

# ── 5. 状态必须有前值/后值/锚点 ────────────────────────────────────────────
for s in cand.get("states", []):
    spans: list[tuple[int, int, str]] = []
    for part in ("before", "after", "anchor"):
        entry = s.get(part)
        if entry is None:
            bad("%s 缺 %s" % (s.get("id"), part))
            continue
        if not (entry.get("quotes") or []):
            bad("%s.%s 没有引文" % (s.get("id"), part))
        for q in entry.get("quotes") or []:
            spans.append((q["start"], q["end"], "%s:%s" % (part, q.get("key"))))
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b = spans[i], spans[j]
            if not (a[1] <= b[0] or a[0] >= b[1]):
                # 同一 part 内部允许（一段里引两条），跨 part 重叠必须报出来
                if a[2].split(":", 1)[0] != b[2].split(":", 1)[0]:
                    bad("%s 前值/后值/锚点的引文区间重叠：%s 与 %s" % (s.get("id"), a[2], b[2]))

# ── 6. 伏笔：铺设 + 回收，或显式 unresolved ────────────────────────────────
for f in cand.get("foreshadows", []):
    setup = (f.get("setup") or {}).get("quotes") or []
    payoff = (f.get("payoff") or {}).get("quotes") or []
    if not setup:
        bad("%s 没有铺设引文" % f.get("id"))
    if not payoff and f.get("unresolved") is not True:
        bad("%s 既没有回收引文，也没标 unresolved" % f.get("id"))
    if f.get("resolved") is True and not payoff:
        bad("%s 声称 resolved 却没有回收引文" % f.get("id"))

# ── 7. 世界设定的三区分 ────────────────────────────────────────────────────
for w in cand.get("worldSettings", []):
    wid, kind = w.get("id"), w.get("kind")
    if not (w.get("quotes") or []):
        bad("%s 世界设定没有引文" % wid)
    if len((w.get("explain") or "").strip()) < 10:
        bad("%s 缺 explain" % wid)
    if kind == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            bad("%s placeState 非法：%r" % (wid, w.get("placeState")))
        if not (w.get("placeStateNote") or "").strip():
            bad("%s 缺 placeStateNote" % wid)
    elif kind == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            bad("%s itemStates 非法：%r" % (wid, st))
        if not (w.get("itemStateNote") or "").strip():
            bad("%s 缺 itemStateNote" % wid)
    elif kind == "rule":
        if "institution" not in w:
            bad("%s 是 rule 却没有 institution 字段" % wid)
        elif w["institution"] is None:
            if not (w.get("institutionNote") or "").strip():
                bad("%s institution=null 却没写理由" % wid)
        elif w["institution"] not in ("declared", "executed", "misunderstood"):
            bad("%s institution 取值非法：%r" % (wid, w["institution"]))
    else:
        bad("%s 的 kind 非法：%r" % (wid, kind))

# ── 8. 主题解读 ────────────────────────────────────────────────────────────
ths = cand.get("themeReadings", [])
if len(ths) > 2:
    bad("themeReadings 超过 2 条：%d" % len(ths))
for th in ths:
    if not (th.get("perspective") or "").strip():
        bad("%s 缺 perspective" % th.get("id"))
    if not ((th.get("support") or {}).get("quotes")):
        bad("%s 缺 support 引文" % th.get("id"))
    if not ((th.get("counter") or {}).get("quotes")):
        bad("%s 缺 counter（只列支持的叫论证，不叫解释）" % th.get("id"))
    blob = json.dumps(th, ensure_ascii=False)
    for forbidden in ("事件密度", "剧情点数量", "死亡人数", "篇幅中点", "三幕", "英雄旅程"):
        if forbidden in blob and "可选" not in blob:
            bad("%s 疑似用 %s 定义高潮且未标为可选视角" % (th.get("id"), forbidden))

# ── 9. 纪律字段 ────────────────────────────────────────────────────────────
if cand.get("semanticReview") != "not-performed":
    bad("semanticReview 不是 not-performed：不得声称语义已核验")
if not cand.get("semanticReviewNote"):
    bad("缺 semanticReviewNote")
if len(cand.get("unknowns") or []) < 3:
    bad("unknowns 少于 3 条")
if len(cand.get("selfCritique") or []) < 3:
    bad("selfCritique 少于 3 条")
for u in cand.get("unknowns", []):
    if not (u.get("why") or "").strip():
        bad("%s 没有写为什么是未知" % u.get("id"))
for sc in cand.get("selfCritique", []):
    if not (sc.get("whyStillJudged") or "").strip():
        bad("%s 没有写「为什么仍然这么判断」" % sc.get("id"))

# 作者附言区不得被当作证据：任何引文都不应落在该区间
author = cand.get("authorRegion") or {}
arange = author.get("range")
if not arange:
    bad("缺 authorRegion.range")
else:
    if text[arange[0]:arange[1]] != author.get("text"):
        bad("authorRegion.text 与其 range 不逐字一致")
    for q in quotes:
        if not (q["end"] <= arange[0] or q["start"] >= arange[1]):
            bad("引文 %s 落在作者附言区里（不得作为叙事证据）" % q.get("key"))

report = {
    "task": "read:dafeng:L3:0307",
    "candidate": str(CAND.relative_to(ROOT)),
    "candidateSha256": hashlib.sha256(CAND.read_bytes()).hexdigest(),
    "sourceHash": SOURCE_HASH,
    "sliceSha256": SLICE_SHA,
    "stats": stats,
    "problemCount": len(problems),
    "problems": problems,
}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")

if problems:
    print("复核失败 %d 项：" % len(problems))
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("复核通过：引文 %d 条全部逐字命中且落在区间内；任务 %d / 因果 %d / 状态 %d / 伏笔 %d / 世界设定 %d / 主题 %d"
      % (stats["quotes"], stats["tasks"], stats["causeEdges"], stats["states"],
         stats["foreshadows"], stats["worldSettings"], stats["themeReadings"]))
print("候选 sha256 = %s" % report["candidateSha256"])
