#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核 read:sanguo:L0:0108 既有候选（w-xiyou-0 的产物）。

独立性声明：本脚本**不 import** 产出方的任何构建脚本（build_0108.py 等），
只读两个输入，其余全部在本脚本内重算：
  1. loop/state/out/read_sanguo_L0_0108.candidate.json   —— 被审对象
  2. data/cache/fe42d01f3826fe8096f86614.docs.json       —— 原文（docs[0].text）

复核内容（都是**机器可复算**的定位/结构层，不含语义裁决）：
  A. 每个引文对象：text[start:end] == quote、区间 ⊆ 切片、sourceHash、长度一致、
     find() 命中次数与声明的 globalOccurrences 是否一致。
  B. 任务五栏「不许同一句话当多栏依据」：按**句读单元**（。！？；\n 切分）判，
     同时给出精确区间重叠数。两种口径都报。
  C. null 栏是否带同名 <栏>Note 且理由非空、非字段名占位符。
  D. worldSettings 三态字段取值合法性（placeState / itemStates / institution）。
  E. themeReadings 三要素（perspective / support / counter）齐不齐。
  F. 反向覆盖率：逐自然段是否有引文落点；本回出现的人物是否至少被引用一次。

用法： python3 -B audit_dupclaim.py
输出： audit_dupclaim_report.json （同目录）
"""
import json
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # loop/state/out/<dir> -> 仓库根
CAND = ROOT / "loop/state/out/read_sanguo_L0_0108.candidate.json"
DOCS = ROOT / "data/cache/fe42d01f3826fe8096f86614.docs.json"
OUTP = HERE / "audit_dupclaim_report.json"

SLICE_START, SLICE_END = 552680, 557148
DECLARED_SOURCE_HASH = "8ab7298a6960c6fec50e26338092abf2693e2cb39f1547f1a99ee2701ef29ec2"
COLUMNS = ("objective", "obstacle", "action", "result", "cost")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_text():
    d = json.loads(DOCS.read_text(encoding="utf-8"))
    return d[0]["text"]


def sentence_spans(text, lo, hi):
    """把 [lo,hi) 切成句读单元。分隔符取 。！？；与换行（含其本身，附在前句尾）。"""
    spans, s = [], lo
    for i in range(lo, hi):
        if text[i] in "。！？；\n":
            spans.append((s, i + 1))
            s = i + 1
    if s < hi:
        spans.append((s, hi))
    return [sp for sp in spans if text[sp[0]:sp[1]].strip()]


def collect_quotes(node, path="", acc=None):
    """递归收集候选里**所有**引文对象（含 quote/start/end 的 dict）。"""
    if acc is None:
        acc = []
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
            acc.append((path, node))
        for k, v in node.items():
            collect_quotes(v, path + "/" + str(k), acc)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect_quotes(v, path + "/%d" % i, acc)
    return acc


def main():
    text = load_text()
    real_hash = sha256_file(DOCS)
    cand = json.loads(CAND.read_text(encoding="utf-8"))
    slice_text = text[SLICE_START:SLICE_END]

    rep = {
        "auditor": "w-xiyou-1",
        "kind": "independent audit of an already-submitted candidate (dupclaim)",
        "inputs": {
            "candidate": str(CAND.relative_to(ROOT)),
            "candidateSha256": sha256_file(CAND),
            "docsJson": str(DOCS.relative_to(ROOT)),
            "docsSha256": real_hash,
            "declaredSourceHashMatchesFile": real_hash == DECLARED_SOURCE_HASH,
            "sliceStart": SLICE_START, "sliceEnd": SLICE_END, "sliceLen": len(slice_text),
            "independence": "未 import 产出方构建脚本；仅读候选 JSON 与原文",
        },
    }

    # ---- A. 引文完整性（全局） ----
    quotes = collect_quotes(cand)
    bad_eq, bad_range, bad_hash, bad_len, bad_occ, ok = [], [], [], [], [], 0
    for path, q in quotes:
        s, e, qt = q.get("start"), q.get("end"), q["quote"]
        if not isinstance(s, int) or not isinstance(e, int):
            bad_range.append({"at": path, "why": "start/end 非整数", "start": s, "end": e})
            continue
        if text[s:e] != qt:
            bad_eq.append({"at": path, "start": s, "end": e,
                           "quote": qt[:60], "text": text[s:e][:60]})
            continue
        if not (SLICE_START <= s and e <= SLICE_END):
            bad_range.append({"at": path, "start": s, "end": e,
                              "why": "越出切片 [%d,%d)" % (SLICE_START, SLICE_END)})
        if e - s != len(qt):
            bad_len.append({"at": path, "start": s, "end": e, "lenQuote": len(qt)})
        if q.get("sourceHash") != DECLARED_SOURCE_HASH:
            bad_hash.append({"at": path, "sourceHash": q.get("sourceHash")})
        decl = q.get("globalOccurrences")
        real_occ = text.count(qt)
        if decl is not None and decl != real_occ:
            bad_occ.append({"at": path, "declared": decl, "real": real_occ, "quote": qt[:40]})
        ok += 1
    rep["A_quoteIntegrity"] = {
        "quoteObjects": len(quotes),
        "textSliceEqualsQuote": ok,
        "badEquality": bad_eq, "badRange": bad_range,
        "badSourceHash": bad_hash, "badLength": bad_len,
        "badGlobalOccurrences": bad_occ,
        "allEqual": not (bad_eq or bad_range or bad_hash or bad_len),
    }

    # ---- B. 任务五栏句子级互斥 ----
    overlap_exact, overlap_sentence, null_cols, bad_notes = [], [], [], []
    for t in cand.get("tasks", []):
        tid = t.get("id")
        per_col_sent, per_col_int = {}, {}
        for col in COLUMNS:
            v = t.get(col)
            if v is None:
                note = t.get(col + "Note")
                null_cols.append({"task": tid, "column": col})
                if not isinstance(note, str) or not note.strip():
                    bad_notes.append({"task": tid, "column": col, "why": "缺 %sNote 或为空" % col})
                elif note.strip() == col + "Note":
                    bad_notes.append({"task": tid, "column": col, "why": "理由是字段名占位符"})
                continue
            qs = (v or {}).get("quotes") or []
            sent, ints = set(), []
            for q in qs:
                s, e = q.get("start"), q.get("end")
                if not isinstance(s, int) or not isinstance(e, int):
                    continue
                ints.append((s, e))
                for i, (a, b) in enumerate(sentence_spans(text, SLICE_START, SLICE_END)):
                    if s < b and a < e:
                        sent.add(i)
            per_col_sent[col] = sent
            per_col_int[col] = ints
        cols = list(per_col_sent)
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                a, b = cols[i], cols[j]
                sh = per_col_sent[a] & per_col_sent[b]
                if sh:
                    overlap_sentence.append({"task": tid, "cols": [a, b],
                                             "sharedSentenceIdx": sorted(sh)})
                for (s1, e1) in per_col_int[a]:
                    for (s2, e2) in per_col_int[b]:
                        if s1 < e2 and s2 < e1:
                            overlap_exact.append({"task": tid, "cols": [a, b],
                                                  "a": [s1, e1], "b": [s2, e2]})
    rep["B_columnIndependence"] = {
        "tasks": len(cand.get("tasks", [])),
        "exactIntervalOverlaps": overlap_exact,
        "sharedSentenceUnits": overlap_sentence,
        "ok": not (overlap_exact or overlap_sentence),
    }
    rep["C_nullColumns"] = {"count": len(null_cols), "items": null_cols,
                            "notesMissingOrPlaceholder": bad_notes}

    # ---- D. worldSettings 三态取值 ----
    ws = cand.get("worldSettings", [])
    PLACE = {"arrived", "mentioned"}
    ITEM = {"hold", "transfer", "use", "lose"}
    INST = {"declared", "executed", "misunderstood"}
    ws_bad, ws_kinds = [], {}
    for w in ws:
        k = w.get("kind")
        ws_kinds[k] = ws_kinds.get(k, 0) + 1
        if k == "place":
            if w.get("placeState") not in PLACE:
                ws_bad.append({"id": w.get("id"), "why": "placeState 非法", "v": w.get("placeState")})
        elif k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or not set(st) <= ITEM:
                ws_bad.append({"id": w.get("id"), "why": "itemStates 非法", "v": st})
        elif k == "rule":
            if w.get("institution") not in INST:
                ws_bad.append({"id": w.get("id"), "why": "institution 非法", "v": w.get("institution")})
        else:
            ws_bad.append({"id": w.get("id"), "why": "kind 非法", "v": k})
        if not (w.get("explain") or "").strip():
            ws_bad.append({"id": w.get("id"), "why": "explain 为空"})
    rep["D_worldSettings"] = {"count": len(ws), "kinds": ws_kinds, "violations": ws_bad,
                              "ok": not ws_bad}

    # ---- E. themeReadings 三要素 ----
    tr_bad = []
    for r in cand.get("themeReadings", []):
        for f in ("perspective", "support", "counter"):
            if not r.get(f):
                tr_bad.append({"id": r.get("id"), "missing": f})
    rep["E_themeReadings"] = {"count": len(cand.get("themeReadings", [])),
                              "missing": tr_bad, "ok": not tr_bad}

    # ---- F. 反向覆盖 ----
    # F1: 逐自然段（非空行）是否有引文落点
    all_int = []
    for _, q in quotes:
        s, e = q.get("start"), q.get("end")
        if isinstance(s, int) and isinstance(e, int):
            all_int.append((s, e))
    paras, off = [], SLICE_START
    for line in slice_text.split("\n"):
        if line.strip():
            paras.append((off, off + len(line), line))
        off += len(line) + 1
    zero = []
    for i, (a, b, line) in enumerate(paras):
        if not any(s < b and a < e for s, e in all_int):
            zero.append({"paraIndex": i, "start": a, "end": b, "head": line[:50]})
    # F2: 本回人物是否被**建模**（提到），而不是「是否被引文引用」。
    #
    # ⚠️ 本探针的第一版判据是错的，记在这里以免复核者重犯：
    #   第一版只查「人名是否出现在**引文串**里」，于是把 王韬／李丰／王肃 报成
    #   「在切片里但从未被引用」。复查发现三人都已建模（王韬在 T04 的 action、
    #   李丰在 T11 的 objective、王肃在 S1x 的 before 叙述里），只是他们的名字
    #   出现在**解释文字**而非引文里 —— 引文本身不必包含人名。
    #   正确判据是「整个候选 JSON（含 explain/summary/note）是否提到该人」。
    #   这条假阳性记在报告里，作为「我的探针也会错」的证据。
    names = ["姜维", "夏侯霸", "郤正", "迷当", "俄何烧戈", "郭淮", "陈泰", "司马师",
             "司马昭", "徐质", "廖化", "张翼", "张嶷", "王韬", "曹芳", "夏侯玄",
             "李丰", "张缉", "张皇后", "曹髦", "司马孚", "王肃", "毋丘俭", "文钦",
             "董承", "伊尹", "霍光", "耿恭"]
    blob_all = json.dumps(cand, ensure_ascii=False)
    quoted_blob = "".join(q["quote"] for _, q in quotes)
    name_rep = []
    for n in names:
        in_slice = n in slice_text
        name_rep.append({
            "name": n,
            "inSlice": in_slice,
            "mentionedInCandidate": n in blob_all,
            "inQuoteText": n in quoted_blob,
        })
    never_modeled = [x["name"] for x in name_rep if x["inSlice"] and not x["mentionedInCandidate"]]
    in_slice_but_not_in_any_quote = [x["name"] for x in name_rep
                                     if x["inSlice"] and not x["inQuoteText"]]
    rep["F_reverseCoverage"] = {
        "paragraphs": len(paras),
        "zeroCoveredParagraphs": zero,
        "zeroCoveredCount": len(zero),
        "namesInSliceNeverModeled": never_modeled,
        "namesInSliceNotInsideAnyQuote": in_slice_but_not_in_any_quote,
        "namesInSliceNotInsideAnyQuoteNote": (
            "人名不必出现在引文里（引文是原文子串，解释文字才承载人物名）——"
            "该列表**不是**缺陷，只是让复核者一眼看到哪些人靠解释层而非引文层被建模。"),
        "names": name_rep,
    }

    rep["summary"] = {
        "quoteObjects": len(quotes),
        "quoteLayerOK": rep["A_quoteIntegrity"]["allEqual"],
        "columnIndependenceOK": rep["B_columnIndependence"]["ok"],
        "nullColumnsAllNoted": not rep["C_nullColumns"]["notesMissingOrPlaceholder"],
        "worldSettingsOK": rep["D_worldSettings"]["ok"],
        "themeReadingsOK": rep["E_themeReadings"]["ok"],
        "zeroCoveredParagraphs": len(zero),
        "semanticReview": "NOT PERFORMED —— 本审计只覆盖定位/结构层；引文定位正确≠语义已核验",
    }

    # ---- G. 声明计数 vs 实际计数（「数字放大」是计划记录过的 6 次虚假声称之一）----
    declared = cand.get("counts") or {}
    real_counts = {
        "tasks": len(cand.get("tasks", [])),
        "causeEdges": len(cand.get("causeEdges", [])),
        "rejectedCauseEdges": len(cand.get("rejectedCauseEdges", [])),
        "states": len(cand.get("states", [])),
        "foreshadows": len(cand.get("foreshadows", [])),
        "worldSettings": len(cand.get("worldSettings", [])),
        "themeReadings": len(cand.get("themeReadings", [])),
        "unknowns": len(cand.get("unknowns", [])),
        "notModeled": len(cand.get("notModeled", [])),
        "selfCritique": len(cand.get("selfCritique", [])),
        "quoteObjects": len(quotes),
    }
    mism = {k: {"declared": declared.get(k), "real": v}
            for k, v in real_counts.items() if k in declared and declared[k] != v}
    rep["G_countHonesty"] = {"declared": declared, "real": real_counts,
                             "mismatches": mism, "ok": not mism}

    # ---- H. 断言声明 vs 实际（basis / evidenceType 是否落在允许集合内）----
    BASIS = {"explicit", "inferred", "derived", "unverified"}
    bad_basis = []

    def walk_basis(n, path=""):
        if isinstance(n, dict):
            if "basis" in n and n["basis"] not in BASIS:
                bad_basis.append({"at": path, "basis": n["basis"]})
            for k, v in n.items():
                walk_basis(v, path + "/" + str(k))
        elif isinstance(n, list):
            for i, v in enumerate(n):
                walk_basis(v, path + "/%d" % i)

    walk_basis(cand)
    rep["H_basisValues"] = {"violations": bad_basis, "ok": not bad_basis}

    # ---- I. 本次审计的**反向发现**（我自己探针的假阳性，如实登记）----
    rep["I_ownAuditCorrections"] = [
        {"probe": "F2 第一版（人名是否出现在**引文串**里）",
         "falsePositive": ["王韬", "李丰", "王肃"],
         "why": ("第一版判据过窄：引文是原文子串，人名通常出现在解释文字里。"
                 "复查确认三人都已建模——王韬见 T04.action、李丰见 T11.objective、"
                 "王肃见 states 里曹髦的 before。已改用「整个候选 JSON 是否提到」。"),
         "lesson": "「我的探针报红」不等于「被审对象有缺陷」；先验证探针自身。"},
        {"probe": "A.globalOccurrences",
         "finding": "有 1 条引文的 globalOccurrences=118（页脚样板文字），不是 1。",
         "verdict": ("**不是缺陷**：该条位于 notModeled，声明值与 text.count() 一致，"
                     "且切片内唯一命中（count in slice == 1）。构建器如实登记了全文重复次数。"),
         "lesson": "「切片内唯一」与「全文唯一」是两个判据，不能混用。"},
    ]

    OUTP.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep["summary"], ensure_ascii=False, indent=1))
    print("countsOk:", rep["G_countHonesty"]["ok"], "| basisOk:", rep["H_basisValues"]["ok"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
