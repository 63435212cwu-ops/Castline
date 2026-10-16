#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核 read:dafeng:L2:0158 候选：**不复用构建期的定位结果**。

与 build_candidate.py 的分工：构建脚本按 (段号, 子串) 生成偏移；本脚本从候选文件里
读出**已成文的 quote/start/end**，全部用 text.find() 重新定位、重算切片，逐项对照。
另外复算：区间口径、源哈希、同任务跨栏共用/重叠、空栏 Note、worldSettings 标签、
覆盖声明、以及构建脚本自报的 machineSelfCheck 数字。

用法：python3 -B -s loop/state/out/read_dafeng_L2_0158.w-sanguo-0.build/verify_candidate.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data" / "cache" / "1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop" / "state" / "out" / "read_dafeng_L2_0158.candidate.json"
EXPECT_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 563238, 567007

problems: list[str] = []
note: list[str] = []

raw = DOCS.read_bytes()
actual_hash = hashlib.sha256(raw).hexdigest()
if actual_hash != EXPECT_HASH:
    problems.append("源哈希不符：%s" % actual_hash)
TEXT = json.loads(raw.decode("utf-8"))[0]["text"]
SEG = TEXT[START:END]
cand = json.loads(CAND.read_text("utf-8"))


def walk(node, path, acc):
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            acc.append((path, node))
        for k, v in node.items():
            walk(v, "%s.%s" % (path, k), acc)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i), acc)


# ---- A. 口径 ---------------------------------------------------------------
if not SEG.startswith(cand["unitHead"]):
    problems.append("A: 切片不以 unitHead 开头")
if cand["source"]["sourceHash"] != actual_hash:
    problems.append("A: 候选 sourceHash 与实测不符")
if cand["source"]["range"] != [START, END]:
    problems.append("A: 候选 range 与任务不符")
if cand["source"]["sliceChars"] != len(SEG):
    problems.append("A: sliceChars 不符")
seg_sha = hashlib.sha256(SEG.encode("utf-8")).hexdigest()
if cand["source"]["segmentSha256"] != seg_sha:
    problems.append("A: segmentSha256 不符")
note.append("A 段 A 通过：切片 %d 字、以「%s」开头、源哈希 %s…、segmentSha256 %s…"
            % (len(SEG), cand["unitHead"], actual_hash[:12], seg_sha[:12]))

# ---- B. 引文逐字 + 偏移 + 哈希 + 唯一 + 首现 -------------------------------
refs: list[tuple[str, dict]] = []
for key in ("tasks", "causeEdges", "states", "knowledgeDiffs", "foreshadows",
            "notForeshadows", "worldSettings", "notWorldSettings", "themeReadings",
            "speechVsNarration", "sceneBeats", "unknowns"):
    walk(cand[key], key, refs)

bad_slice, bad_range, bad_hash, bad_unique, bad_first = [], [], [], [], []
for path, r in refs:
    q, a, b = r["quote"], r["start"], r["end"]
    if TEXT[a:b] != q:
        bad_slice.append(path)
    if not (START <= a and b <= END):
        bad_range.append(path)
    if r.get("sourceHash") != actual_hash:
        bad_hash.append(path)
    n = TEXT.count(q)
    if n != 1:
        bad_unique.append((path, n, q[:24]))
    if TEXT.find(q) != a:
        bad_first.append((path, TEXT.find(q), a))
problems += ["B: 切片≠引文 %s" % p for p in bad_slice]
problems += ["B: 越界 %s" % p for p in bad_range]
problems += ["B: 哈希不符 %s" % p for p in bad_hash]
problems += ["B: 非唯一 %r" % (x,) for x in bad_unique]
problems += ["B: start 非首现 %r" % (x,) for x in bad_first]
note.append("B 段通过：%d 个引文节点全部 text.find() 命中且 text[start:end]==quote、"
            "落在 [%d,%d) 内、sourceHash 一致、全书唯一、start 为首现（0 处不符）"
            % (len(refs), START, END))

# ---- C. 同任务跨栏不共用 / 不重叠 ------------------------------------------
FIELDS = ("objective", "obstacle", "action", "result", "cost")
same, overlap, null_missing = [], [], []
for t in cand["tasks"]:
    seen = {}
    spans = []
    for f in FIELDS:
        v = t.get(f)
        if v is None:
            if not t.get(f + "Note"):
                null_missing.append("%s.%s" % (t["id"], f))
            continue
        for r in v["quotes"]:
            if r["quote"] in seen:
                same.append((t["id"], f, seen[r["quote"]]))
            seen[r["quote"]] = f
            spans.append((r["start"], r["end"], f))
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            if spans[i][0] < spans[j][1] and spans[j][0] < spans[i][1]:
                overlap.append((t["id"], spans[i], spans[j]))
problems += ["C: 跨栏共用引文 %r" % (x,) for x in same]
problems += ["C: 跨栏跨度重叠 %r" % (x,) for x in overlap]
problems += ["C: 空栏缺 Note %s" % x for x in null_missing]
n_null = sum(1 for t in cand["tasks"] for f in FIELDS if t.get(f) is None)
note.append("C 段通过：%d 条任务 × 5 栏，跨栏共用 0、跨度重叠 0；%d 个 null 栏位全部带同名 Note"
            % (len(cand["tasks"]), n_null))

# ---- D. worldSettings 标签合法性 -------------------------------------------
bad_ws = []
for w in cand["worldSettings"]:
    if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        bad_ws.append(w["id"])
    if w["kind"] == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or any(s not in ("hold", "transfer", "use", "lose") for s in st):
            bad_ws.append(w["id"])
    if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        bad_ws.append(w["id"])
    if not w.get("explain"):
        bad_ws.append(w["id"] + ":no-explain")
    if "quoteRef" not in w:
        bad_ws.append(w["id"] + ":no-quoteRef")
problems += ["D: %s" % x for x in bad_ws]
kinds = {}
for w in cand["worldSettings"]:
    kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
note.append("D 段通过：worldSettings %d 条（%r），placeState/itemStates/institution 标签全部合法"
            % (len(cand["worldSettings"]), kinds))

# ---- E. themeReadings / foreshadows ---------------------------------------
bad_theme = [t["id"] for t in cand["themeReadings"]
             if not (t.get("perspective") and t.get("support") and t.get("counter"))]
bad_fs = [f["id"] for f in cand["foreshadows"]
          if f.get("status") == "unresolved" and not f.get("payoffNote")]
resolved = [f["id"] for f in cand["foreshadows"] if f.get("status") == "resolved"]
for f in cand["foreshadows"]:
    if f.get("status") == "resolved" and not f.get("payoff"):
        bad_fs.append(f["id"] + ":resolved-without-payoff")
problems += ["E: %s" % x for x in bad_theme + bad_fs]
note.append("E 段通过：themeReadings %d 条（perspective/support/counter 齐全）、"
            "foreshadows %d 条（resolved %r，未回收 %r 均带 payoffNote）"
            % (len(cand["themeReadings"]), len(cand["foreshadows"]), resolved,
               [f["id"] for f in cand["foreshadows"] if f["status"] == "unresolved"]))

# ---- F. 覆盖声明复算 -------------------------------------------------------
PARA_SPANS, _i, _n = {}, 0, 0
for _line in SEG.split("\n"):
    if _line.strip():
        _n += 1
        PARA_SPANS[_n] = (START + _i, START + _i + len(_line))
    _i += len(_line) + 1
spans = [(r["start"], r["end"]) for _, r in refs]
covered = [n for n, (a, b) in PARA_SPANS.items() if any(a < e and s < b for s, e in spans)]
uncovered = [n for n in PARA_SPANS if n not in covered]
cov = cand["coverageDeclaration"]
if cov["nonEmptyParagraphs"] != len(PARA_SPANS):
    problems.append("F: nonEmptyParagraphs 不符")
if cov["coveredParagraphs"] != len(covered):
    problems.append("F: coveredParagraphs 声明 %s 实测 %s" % (cov["coveredParagraphs"], len(covered)))
if cov["uncoveredItems"] != uncovered:
    problems.append("F: uncoveredItems 不符（声明 %r 实测 %r）" % (cov["uncoveredItems"], uncovered))
disp = [d["paragraph"] for d in cand["paragraphDisposition"]]
if sorted(disp) != sorted(uncovered):
    problems.append("F: paragraphDisposition 未逐段解释未覆盖段")
note.append("F 段通过：反向覆盖 %d/%d，未覆盖 %r 与声明一致且逐段有理由"
            % (len(covered), len(PARA_SPANS), uncovered))

# ---- G. 自报机检数字对照 ---------------------------------------------------
ms = cand["machineSelfCheck"]
if ms["quoteRefs"] != len(refs):
    problems.append("G: machineSelfCheck.quoteRefs 声明 %s 实测 %s" % (ms["quoteRefs"], len(refs)))
if ms["uniqueQuoteStrings"] != len({r["quote"] for _, r in refs}):
    problems.append("G: uniqueQuoteStrings 不符")
for k, v in ms.items():
    if isinstance(v, list) and v and k not in ("note",):
        problems.append("G: 自报 %s 非空" % k)
note.append("G 段通过：自报 quoteRefs=%d / unique=%d 与实测一致；五关列表全空"
            % (ms["quoteRefs"], ms["uniqueQuoteStrings"]))

# ---- H. 越权/红线抽查 ------------------------------------------------------
if cand.get("semanticReview") != "not-performed":
    problems.append("H: semanticReview 必须为 not-performed")
blob = json.dumps(cand, ensure_ascii=False)
for word in ("午门外", "取荆州"):     # 上一单元被复核抓到的跨章用词污染，本单元同样不得出现
    if word in blob:
        problems.append("H: 出现区间外/易污染用词 %s" % word)
problems += ["H: 越界用词 %s" % w for w in ("第一件事",) if w in blob]
note.append("H 段通过：semanticReview=not-performed；未出现「午门外」等跨章污染词")

# ---- 输出 ------------------------------------------------------------------
print("候选：%s" % CAND)
print("候选 sha256：%s" % hashlib.sha256(CAND.read_bytes()).hexdigest())
for n in note:
    print("  " + n)
if problems:
    print("\n发现 %d 处问题：" % len(problems))
    for p in problems:
        print("  - " + p)
    sys.exit(1)
print("\n全部通过：0 处问题")
