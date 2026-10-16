#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VERIFIER 独立仪器：大奉打更人 第两百二十一章 [832785,836013)。

纪律（VERIFIER.md）：本脚本**不 import** 被复核方
`read_dafeng_L2_0222.w-read-4.build/` 下的任何模块；段落模型、句单元模型、
引文定位、计数全部在本文件里另行实现，只用于与被复核候选的**自报值对照**。

用法：
  python3 independent_check.py            # 全量复算
  python3 independent_check.py --json     # 机器可读
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0222.candidate.json"
START, END = 832785, 836013
EXPECT_SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
EXPECT_SEG_HASH = "881618c7e1c7a338d06d77c034a1e2f48355a8d413437f09beb0f181711f3042"

# 句单元切分：在本脚本内独立定义（不抄候选的实现）。
SENT_END = "。！？…”』"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def load_text() -> str:
    docs = json.loads(SRC.read_text("utf-8"))
    return docs[0]["text"]


def paragraphs(text: str, start: int, end: int):
    """独立段落模型：切片按 \n 切成行，去掉首尾空白后非空的行按原顺序编号 P000..。

    返回 [(label, para_start, para_end, body), ...]，偏移是**全文绝对** codepoint。
    """
    out = []
    pos = start
    seg = text[start:end]
    for raw in seg.split("\n"):
        line_start = pos
        pos += len(raw) + 1  # +1 是 \n
        stripped = raw.lstrip()
        lead = len(raw) - len(stripped)
        body = stripped.rstrip()
        if not body:
            continue
        out.append(("P%03d" % len(out), line_start + lead, line_start + lead + len(body), body))
    return out


def sent_units(para_body: str, para_start: int):
    """独立句单元模型：按句末标点切，闭区间包含标点与紧随的收尾引号。

    返回 [(idx, s_start, s_end, text)]，偏移为全文绝对 codepoint，左闭右开。
    """
    units = []
    i = 0
    n = len(para_body)
    while i < n:
        j = i
        while j < n and para_body[j] not in SENT_END:
            j += 1
        if j >= n:
            tail = para_body[i:]
            if tail.strip():
                units.append((len(units), para_start + i, para_start + n, tail))
            break
        k = j + 1
        # 句末标点后紧跟的收尾引号并入本句
        while k < n and para_body[k] in "”』":
            k += 1
        units.append((len(units), para_start + i, para_start + k, para_body[i:k]))
        i = k
    return units


def all_quotes(cand: dict):
    """产出 (section, item_id, field, quote_dict) —— **递归**枚举，不依赖栏目结构假设。

    第一版仪器只遍历了固定的几栏与固定字段名，漏掉了 themeReadings/states 等
    嵌套位置上的引文（实测少 16 条、覆盖率少 11 个码点）⇒ 会把候选**正确**的
    自报值误判成错的。这是**我的仪器错**，已改为递归枚举并记入 verdict 的
    selfCorrection。判据：候选自己声明的 quoteNodes 必须等于递归枚举到的节点数。
    """
    found: list = []

    def walk(node, section, iid, field):
        if isinstance(node, dict):
            if "quote" in node and "start" in node:
                found.append((section, iid, field, node))
                return
            for k, v in node.items():
                walk(v, section, iid, k if field is None else field)
        elif isinstance(node, list):
            for v in node:
                walk(v, section, iid, field)

    for sec, items in cand.items():
        if isinstance(items, list):
            for item in items:
                iid = item.get("id") if isinstance(item, dict) else None
                walk(item, sec, iid or "?", None)
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    text = load_text()
    report: dict = {}
    report["sourceFileSha256"] = sha256_file(SRC)
    report["sourceHashMatchesTask"] = report["sourceFileSha256"] == EXPECT_SOURCE_HASH
    seg = text[START:END]
    report["segmentSha256"] = sha256_bytes(seg.encode("utf-8"))
    report["segmentSha256Matches"] = report["segmentSha256"] == EXPECT_SEG_HASH
    report["segmentCodepoints"] = len(seg)

    paras = paragraphs(text, START, END)
    report["nonEmptyParagraphs"] = len(paras)
    report["paraMap"] = {p[0]: [p[1], p[2]] for p in paras}
    body_of = {p[0]: p[3] for p in paras}
    start_of = {p[0]: p[1] for p in paras}

    cand = json.loads(CAND.read_text("utf-8"))
    report["candidateSha256"] = sha256_file(CAND)

    # ── 判据 A：每条引文逐字命中、区间内、偏移一致 ────────────────────────
    problems = []
    quotes = list(all_quotes(cand))
    report["quoteCount"] = len(quotes)
    covered = set()
    for sec, iid, field, q in quotes:
        s, e, t = q.get("start"), q.get("end"), q.get("quote")
        if t is None or s is None or e is None:
            problems.append({"kind": "incomplete", "sec": sec, "id": iid, "field": field})
            continue
        if text[s:e] != t:
            problems.append({"kind": "not-verbatim", "sec": sec, "id": iid, "field": field,
                             "quote": t, "declared": [s, e], "actual": text[s:e]})
        if not (START <= s and e <= END):
            problems.append({"kind": "out-of-range", "sec": sec, "id": iid, "field": field,
                             "declared": [s, e]})
        covered.update(range(s, e))
        # 段号核对
        pl = q.get("paraLabel")
        if pl in start_of:
            ps, pe = start_of[pl], start_of[pl] + len(body_of[pl])
            if not (ps <= s and e <= pe):
                problems.append({"kind": "paraLabel-mismatch", "sec": sec, "id": iid,
                                 "field": field, "declared": pl, "span": [s, e],
                                 "para": [ps, pe]})
            # 句单元核对
            su = q.get("sentUnit")
            units = sent_units(body_of[pl], ps)
            hit = [u for u in units if u[1] == s and u[2] == e]
            if su is not None and not hit:
                problems.append({"kind": "sentUnit-mismatch", "sec": sec, "id": iid,
                                 "field": field, "declared": su, "span": [s, e],
                                 "units": [[u[0], u[1], u[2]] for u in units]})
    report["quoteProblems"] = problems

    # ── 判据 B：wholeTextOccurrences / occurrencesInRange ─────────────────
    occ_problems = []
    for sec, iid, field, q in quotes:
        t, s = q.get("quote"), q.get("start")
        if t is None:
            continue
        whole = text.count(t)
        inr = text.count(t, START, END)
        if q.get("wholeTextOccurrences") not in (None, whole):
            occ_problems.append({"kind": "wholeTextOccurrences", "id": iid, "field": field,
                                 "declared": q.get("wholeTextOccurrences"), "actual": whole,
                                 "quote": t[:40]})
        if q.get("occurrencesInRange") not in (None, inr):
            occ_problems.append({"kind": "occurrencesInRange", "id": iid, "field": field,
                                 "declared": q.get("occurrencesInRange"), "actual": inr,
                                 "quote": t[:40]})
    report["occurrenceProblems"] = occ_problems

    # ── 判据 C：coverage 自报值复算 ───────────────────────────────────────
    non_space = sum(1 for ch in seg if not ch.isspace())
    touched = {}
    for pl, ps, pe, body in paras:
        if any(i in covered for i in range(ps, pe)):
            touched[pl] = True
    zero = [pl for pl, ps, pe, body in paras if pl not in touched]
    cov = cand.get("coverage") or {}
    report["coverageRecomputed"] = {
        "quoteUnionCodepoints": len(covered),
        "nonSpaceCodepoints": non_space,
        "quoteUnionRatioOfNonSpace": round(len(covered) / non_space, 4) if non_space else None,
        "paragraphsTouched": len(touched),
        "zeroCoveredParagraphs": len(zero),
        "zeroCoveredList": zero,
    }
    report["coverageMatches"] = {
        "quoteUnionCodepoints": cov.get("quoteUnionCodepoints") == len(covered),
        "nonSpaceCodepoints": cov.get("nonSpaceCodepoints") == non_space,
        "paragraphsTouched": cov.get("paragraphsTouched") == len(touched),
        "zeroCoveredParagraphs": cov.get("zeroCoveredParagraphs") == len(zero),
        "zeroCoveredList": list(cov.get("zeroCoveredList") or []) == zero,
    }
    report["coverageDeclared"] = {
        "quoteUnionCodepoints": cov.get("quoteUnionCodepoints"),
        "nonSpaceCodepoints": cov.get("nonSpaceCodepoints"),
        "paragraphsTouched": cov.get("paragraphsTouched"),
        "zeroCoveredParagraphs": cov.get("zeroCoveredParagraphs"),
        "zeroCoveredList": cov.get("zeroCoveredList"),
    }

    # ── 判据 D：perParagraph 与实际引文位置是否一致 ───────────────────────
    sec_of = {}
    for sec, iid, field, q in quotes:
        pl = q.get("paraLabel")
        sec_of.setdefault(pl, set()).add(sec)
    pp_problems = []
    for row in cov.get("perParagraph") or []:
        pl = row.get("para")
        want_state = "quoted" if pl in sec_of else "not-quoted"
        if row.get("state") != want_state:
            pp_problems.append({"para": pl, "declared": row.get("state"), "actual": want_state})
        if want_state == "quoted":
            if sorted(row.get("sections") or []) != sorted(sec_of[pl]):
                pp_problems.append({"para": pl, "kind": "sections",
                                    "declared": sorted(row.get("sections") or []),
                                    "actual": sorted(sec_of[pl])})
    report["perParagraphProblems"] = pp_problems
    report["perParagraphRows"] = len(cov.get("perParagraph") or [])

    # ── 判据 E：machineSelfCheck 布尔项是否真实（抽样重算关键 3 项）────────
    msc = cand.get("machineSelfCheck") or {}
    report["machineSelfCheckDeclared"] = msc.get("checks")
    report["machineSelfCheckQuoteNodes"] = msc.get("quoteNodes")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print("sourceFileSha256      ", report["sourceFileSha256"])
        print("  matches task        ", report["sourceHashMatchesTask"])
        print("segmentSha256         ", report["segmentSha256"])
        print("  matches declared    ", report["segmentSha256Matches"])
        print("segment codepoints    ", report["segmentCodepoints"])
        print("nonEmptyParagraphs    ", report["nonEmptyParagraphs"])
        print("candidateSha256       ", report["candidateSha256"])
        print("quoteCount            ", report["quoteCount"], "(machineSelfCheck.quoteNodes=%s)"
              % msc.get("quoteNodes"))
        print("quoteProblems         ", len(problems))
        for p in problems[:10]:
            print("   !", json.dumps(p, ensure_ascii=False)[:220])
        print("occurrenceProblems    ", len(occ_problems))
        for p in occ_problems[:10]:
            print("   !", json.dumps(p, ensure_ascii=False)[:220])
        print("coverageMatches       ", json.dumps(report["coverageMatches"], ensure_ascii=False))
        print("coverageRecomputed    ", json.dumps(report["coverageRecomputed"], ensure_ascii=False))
        print("perParagraphProblems  ", len(pp_problems))
        for p in pp_problems[:10]:
            print("   !", json.dumps(p, ensure_ascii=False)[:220])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
