#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VERIFIER 结构仪器：独立复算候选 machineSelfCheck 里可由磁盘现算的判据。

复算项（全部本文件另行实现，不 import 候选的 build 模块）：
  · 1 源哈希与文件一致
  · 2 切片以单元标题开头
  · 3 任务五栏引文互不重复（字符区间级 + 句单元级）
  · 4 全部引文逐字且落在区间内
  · 5 null 栏必须有同名 <field>Note
  · 6 worldSettings 判别字段合法（rule→institution / place→placeState / item→itemStates）
  · 6b themeReadings 必须同时有 support 与 counter
  · 9 basis 取值合法（explicit/inferred/derived/unverified）
  · 引文节点数 == 候选自报 quoteNodes
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0222.candidate.json"
START, END = 832785, 836013
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
FIVE = ["objective", "obstacle", "action", "result", "cost"]
BASIS = {"explicit", "inferred", "derived", "unverified"}
SEP = re.compile(r"[。！？…]+")


def walk_quotes(node):
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            yield node
            return
        for v in node.values():
            yield from walk_quotes(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk_quotes(v)


def sent_units(t):
    out, last = [], 0
    for m in SEP.finditer(t):
        out.append((last, m.end()))
        last = m.end()
    if last < len(t):
        out.append((last, len(t)))
    return out or [(0, len(t))]


def main() -> int:
    text = json.loads(SRC.read_text("utf-8"))[0]["text"]
    seg = text[START:END]
    cand = json.loads(CAND.read_text("utf-8"))
    qs = list(walk_quotes(cand))
    res = {}

    res["1_sourceHashMatchesFile"] = (
        hashlib.sha256(SRC.read_bytes()).hexdigest() == SOURCE_HASH
        and cand["source"]["sourceHash"] == SOURCE_HASH)
    res["2_sliceStartsWithUnitHead"] = seg.startswith(cand["unitHead"])

    # 段落模型（与候选同口径：切片按 \n 分行、strip、记 lead）
    paras, off = [], START
    for line in seg.split("\n"):
        if line.strip():
            lead = len(line) - len(line.lstrip())
            paras.append((line.strip(), off + lead))
        off += len(line) + 1

    def sent_key(pos):
        for body, ps in paras:
            if ps <= pos < ps + len(body):
                rel = pos - ps
                for k, (a, b) in enumerate(sent_units(body)):
                    if a <= rel < b:
                        return (ps, k)
                return (ps, 0)
        return None

    conf_char, conf_sent = [], []
    for t in cand["tasks"]:
        seen_c, seen_s = {}, {}
        for f in FIVE:
            blk = t.get(f)
            if not isinstance(blk, dict):
                continue
            for q in blk.get("quotes") or []:
                kc = (q["start"], q["end"])
                ks = sent_key(q["start"])
                if kc in seen_c:
                    conf_char.append((t["id"], seen_c[kc], f, kc))
                if ks in seen_s:
                    conf_sent.append((t["id"], seen_s[ks], f, ks))
                seen_c[kc] = f
                seen_s[ks] = f
    res["3_taskColumnQuotesDisjoint"] = (not conf_char) and (not conf_sent)
    res["3_conflicts_char"] = conf_char
    res["3_conflicts_sent"] = conf_sent

    bad_q = [q for q in qs if text[q["start"]:q["end"]] != q["quote"]
             or not (START <= q["start"] and q["end"] <= END)]
    res["4_allQuotesVerbatimAndInRange"] = not bad_q
    res["4_badQuoteCount"] = len(bad_q)

    null_bad = []
    for t in cand["tasks"]:
        for f in FIVE:
            if t.get(f) is None and not t.get(f + "Note"):
                null_bad.append((t["id"], f))
    res["5_nullColumnsHaveNotes"] = not null_bad
    res["5_nullProblems"] = null_bad

    ws_bad = []
    for w in cand["worldSettings"]:
        k = w.get("kind")
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            ws_bad.append((w.get("name"), "institution", w.get("institution")))
        elif k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            ws_bad.append((w.get("name"), "placeState", w.get("placeState")))
        elif k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(
                    x not in ("hold", "transfer", "use", "lose") for x in st):
                ws_bad.append((w.get("name"), "itemStates", st))
        elif k not in ("rule", "place", "item"):
            ws_bad.append((w.get("name"), "kind", k))
    res["6_worldSettingDiscriminantsValid"] = not ws_bad
    res["6_worldSettingProblems"] = ws_bad

    th_bad = [th.get("id") for th in cand["themeReadings"]
              if not (th.get("support") and th.get("counter"))]
    res["6b_themeReadingsHaveCounter"] = not th_bad
    res["6b_themeProblems"] = th_bad

    basis_bad = []
    for sec, items in cand.items():
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict) and it.get("basis") and it["basis"] not in BASIS:
                basis_bad.append((sec, it.get("id"), it["basis"]))
            if isinstance(it, dict):
                for f in FIVE:
                    blk = it.get(f)
                    if isinstance(blk, dict) and blk.get("basis") and blk["basis"] not in BASIS:
                        basis_bad.append((sec, it.get("id"), f, blk["basis"]))
    # 顶层 basisLegend 是图例，不是取值
    basis_bad = [b for b in basis_bad if b[0] != "basisLegend"]
    res["9_basisValuesLegal"] = not basis_bad
    res["9_basisProblems"] = basis_bad

    declared = (cand.get("machineSelfCheck") or {}).get("quoteNodes")
    res["quoteNodes_declared"] = declared
    res["quoteNodes_recounted"] = len(qs)
    res["quoteNodes_match"] = declared == len(qs)

    res["requiredSectionsPresent"] = all(
        k in cand for k in ("tasks", "causeEdges", "states", "foreshadows",
                            "worldSettings", "themeReadings"))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
