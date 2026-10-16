#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VERIFIER 反向验证仪器：找出「原文明确存在、但候选一条引文都没覆盖」的字符区间。

不 import 候选的任何构建模块。段落模型在本文件内独立重实现（与 independent_check.py 同口径）。
输出按段列出未被任何候选引文覆盖的**连续原文片段**（逐字，可直接 quote）。

用法：python3 uncovered_scan.py [--min-chars 4]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0222.candidate.json"
START, END = 832785, 836013


def paragraphs(text, start, end):
    out, pos = [], start
    for raw in text[start:end].split("\n"):
        line_start = pos
        pos += len(raw) + 1
        stripped = raw.lstrip()
        lead = len(raw) - len(stripped)
        body = stripped.rstrip()
        if body:
            out.append(("P%03d" % len(out), line_start + lead, body))
    return out


def candidate_quotes(cand):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "quote" in node and "start" in node and "end" in node:
                found.append((node["start"], node["end"], node["quote"]))
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(cand)
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-chars", type=int, default=4)
    args = ap.parse_args()

    text = json.loads(SRC.read_text("utf-8"))[0]["text"]
    cand = json.loads(CAND.read_text("utf-8"))
    qs = candidate_quotes(cand)
    cov = set()
    for s, e, _ in qs:
        cov.update(range(s, e))

    total_uncovered = 0
    for lab, ps, body in paragraphs(text, START, END):
        hole, runs = [], []
        for i, _ch in enumerate(body):
            if (ps + i) not in cov:
                hole.append(i)
            else:
                if hole:
                    runs.append((hole[0], hole[-1] + 1))
                    hole = []
        if hole:
            runs.append((hole[0], hole[-1] + 1))
        runs = [r for r in runs if r[1] - r[0] >= args.min_chars]
        runs = [r for r in runs if body[r[0]:r[1]].strip()]
        if not runs:
            continue
        print("%s  [%d uncovered runs]" % (lab, len(runs)))
        for a, b in runs:
            frag = body[a:b]
            total_uncovered += len(frag)
            print("    [%d,%d] %r" % (ps + a, ps + b, frag))
    print("\ntotal uncovered chars in listed runs: %d" % total_uncovered)
    print("quoteUnion=%d  nonSpace=%d" % (len(cov), sum(1 for c in text[START:END] if not c.isspace())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
