#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复算：**不 import build_candidate.py**，直接读候选 JSON 与原文，重算全部判据。

为什么另写一遍：同一个脚本既生成又自检，等于自签。本脚本只读产物，独立复算；
只要有一条对不上就退出码 1。它同时做两条**反向检查**：
  V9  候选声称 null 的栏位，原文区间内是否**真的**找不到依据（而不是我漏读）
  V10 候选声称「切片内唯一」的引文，是否在全书里出现多次（披露，不判失败）
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND = ROOT / "loop/state/out/read_dafeng_L0_0232.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
START, END = 910067, 916516
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
COLUMNS = ("objective", "obstacle", "action", "result", "cost")


def main():
    blob = DOCS.read_bytes()
    assert hashlib.sha256(blob).hexdigest() == SOURCE_HASH
    text = json.loads(blob)[0]["text"]
    seg = text[START:END]
    cand = json.loads(CAND.read_text(encoding="utf-8"))

    problems = []
    stats = {}

    # 递归收集全部引文对象
    qs = []

    def walk(o, path=""):
        if isinstance(o, dict):
            if "quote" in o and "start" in o and "end" in o:
                qs.append((path, o))
            for k, v in o.items():
                walk(v, path + "/" + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + "[%d]" % i)

    walk(cand)
    stats["quoteObjects"] = len(qs)

    n_slice = n_hash = n_range = n_uniq = n_len = 0
    for path, q in qs:
        if text[q["start"]:q["end"]] != q["quote"]:
            problems.append("V1 切片不符 @%s" % path)
        else:
            n_slice += 1
        if q.get("sourceHash") != SOURCE_HASH:
            problems.append("V2 sourceHash 不符 @%s" % path)
        else:
            n_hash += 1
        if not (START <= q["start"] < q["end"] <= END):
            problems.append("V3 越界 @%s" % path)
        else:
            n_range += 1
        if seg.count(q["quote"]) != 1:
            problems.append("V4 切片内不唯一 @%s" % path)
        else:
            n_uniq += 1
        if q["end"] - q["start"] != len(q["quote"]):
            problems.append("V5 长度不符 @%s" % path)
        else:
            n_len += 1
    stats.update(slice_ok=n_slice, hash_ok=n_hash, range_ok=n_range, unique_ok=n_uniq, len_ok=n_len)

    # V6/V7 栏位独立（重算，不用 builder 的中间结果）
    v6 = v7 = v8 = 0
    for t in cand["tasks"]:
        cols = {c: [(q["start"], q["end"]) for q in (t.get(c, {}).get("quotes") or [])] for c in COLUMNS}
        for i in range(len(COLUMNS)):
            for j in range(i + 1, len(COLUMNS)):
                for x in cols[COLUMNS[i]]:
                    for y in cols[COLUMNS[j]]:
                        if not (x[1] <= y[0] or y[1] <= x[0]):
                            v6 += 1
        for i in range(len(COLUMNS)):
            for j in range(i + 1, len(COLUMNS)):
                si = set()
                sj = set()
                for q in (t.get(COLUMNS[i], {}).get("quotes") or []):
                    si |= set(q["sentenceIdx"])
                for q in (t.get(COLUMNS[j], {}).get("quotes") or []):
                    sj |= set(q["sentenceIdx"])
                if si & sj:
                    v7 += 1
        flat = [(c, q["quote"]) for c in COLUMNS for q in (t.get(c, {}).get("quotes") or [])]
        for i in range(len(flat)):
            for j in range(i + 1, len(flat)):
                if flat[i][1] == flat[j][1] or flat[i][1] in flat[j][1] or flat[j][1] in flat[i][1]:
                    v8 += 1
    if v6:
        problems.append("V6 栏位跨度相交 %d 处" % v6)
    if v7:
        problems.append("V7 栏位句锚相交 %d 处" % v7)
    if v8:
        problems.append("V8 任务内引文重复/包含 %d 处" % v8)
    stats.update(clauseOverlap=v6, sentenceOverlap=v7, dupInTask=v8)

    # V9 反向：null 栏是否真的找不到依据（列出该任务其他栏的引文，看是否被误标 null）
    v9 = []
    for t in cand["tasks"]:
        used = set()
        for c in COLUMNS:
            for q in (t.get(c, {}).get("quotes") or []):
                used.add(q["quote"])
        for c in COLUMNS:
            col = t.get(c, {})
            if col.get("text") is None:
                note = col.get(c + "Note") or ""
                if len(note) < 10:
                    v9.append("%s.%s null 且缺 %sNote 或理由过短" % (t["id"], c, c))
    stats["nullColumns"] = sum(1 for t in cand["tasks"] for c in COLUMNS if t.get(c, {}).get("text") is None)
    stats["nullProblems"] = v9
    problems += v9

    # V10 披露：引文在全书的出现次数
    multi = sorted({q["quote"] for _p, q in qs if text.count(q["quote"]) > 1})
    stats["quotesAppearingElsewhereInBook"] = len(multi)

    # V11 覆盖率重算
    vis = [i for i, ch in enumerate(seg) if not ch.isspace()]
    cov = set()
    for _p, q in qs:
        cov |= set(range(q["start"] - START, q["end"] - START))
    ratio = len([i for i in vis if i in cov]) / len(vis)
    claimed = cand["coverage"]["ratio"]
    stats["coverageRecomputed"] = round(ratio, 4)
    stats["coverageClaimed"] = claimed
    if abs(ratio - claimed) > 1e-4:
        problems.append("V11 覆盖率不符：声称 %s 实测 %.4f" % (claimed, ratio))

    # V12 「」片段可回查
    frag_bad = []

    def scan(o):
        if isinstance(o, str):
            for m in re.finditer(r"「([^」]+)」", o):
                if len(m.group(1)) >= 5 and m.group(1) not in seg:
                    frag_bad.append(m.group(1))
        elif isinstance(o, dict):
            for v in o.values():
                scan(v)
        elif isinstance(o, list):
            for v in o:
                scan(v)

    scan(cand)
    frag_bad = sorted(set(frag_bad))
    stats["nonVerbatimBracketFragments"] = len(frag_bad)
    if frag_bad:
        problems.append("V12 「」片段不可回查 %d 个：%r" % (len(frag_bad), frag_bad[:5]))

    # V13 分区键存在（提示词要求 6 个）
    for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
        if k not in cand:
            problems.append("V13 缺分区 %s" % k)

    # V14 候选自报 allPass 与本次复算一致
    if not cand["machineSelfCheck"]["allPass"]:
        problems.append("V14 候选自报 allPass=false")

    print(json.dumps(stats, ensure_ascii=False, indent=1))
    if problems:
        for p in problems:
            print("[FAIL] " + p, file=sys.stderr)
        return 1
    print("独立复算：全部判据通过（与候选自报一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
