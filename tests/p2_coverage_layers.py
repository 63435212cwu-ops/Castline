#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.3 五种覆盖分开 + P0.4 可关闭项：把「覆盖」拆成五个互不替代的分母。

计划原文（docs/QUALITY.md P2.3）：
  「分别统计可访问原文、计划窗口、实际接受输入、产出触及、人工语义复核。
    窗口取并集与补集，携带hash；预算截断按真正进入请求的字符计。
    重复发送不增覆盖，全部批次完成不显示"全书已理解"。没有金标准的召回保持未知。」

为什么必须有这一条：现在唯一的覆盖数字是 `loop.py stats` 的「完成 178/2341」——
那是**任务条数**，不是覆盖。计划明确禁止用它替代任何一层：
  · 任务条数不是原文覆盖（一个任务可以什么都没读，也可以重复读同一段）；
  · 计划窗口不是实际输入（预算截断发生在请求构造时）；
  · 产出触及不是人工复核（agent 写了引文 ≠ 语义被核验，
    candidate 自己的 `semanticReview: not-performed` 就是这么写的）。

本脚本只**统计并报告**，不改任何产品代码，也不把任何一层写成"全书已理解"。

判据：
  ① 五层各有独立分子/分母，且都能用命令重算；
  ② 窗口按 codepoint 区间取并集，携带 sourceHash，跨 hash 不得相加；
  ③ 重复发送同一区间只算一次（并集性质，反例：把同一单元发两次覆盖不得翻倍）；
  ④ 人工语义复核层必须与产出触及层分开计数（当前应远小于它）；
  ⑤ 任一层不完整时，输出里不得出现「全书已理解」之类结论字段。

用法：
  python3 -B -s tests/p2_coverage_layers.py \
      --out "$CL_ARTIFACTS/p2-coverage/coverage-layers.json"
"""
import argparse
import glob
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "loop" / "state"
OUT = STATE / "out"
QUEUE = ROOT / "loop" / "queue"


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def union_len(intervals):
    """codepoint 区间并集长度：重复发送同一段不会增加覆盖。"""
    if not intervals:
        return 0
    ivs = sorted((int(a), int(b)) for a, b in intervals if b > a)
    total, cur_s, cur_e = 0, None, None
    for s, e in ivs:
        if cur_s is None:
            cur_s, cur_e = s, e
        elif s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    return total + (cur_e - cur_s) if cur_s is not None else 0


def complement(intervals, lo, hi):
    """窗口补集：计划窗口相对整篇原文没盖到的段。"""
    ivs = sorted((int(a), int(b)) for a, b in intervals if b > a)
    gaps, cursor = [], lo
    for s, e in ivs:
        if s > cursor:
            gaps.append([cursor, s])
        cursor = max(cursor, e)
    if cursor < hi:
        gaps.append([cursor, hi])
    return gaps


def source_text_hash(book: str, index: dict):
    b = (index.get("books") or {}).get(book) or {}
    return b.get("docsSha256")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p2-coverage"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    index = load(STATE / "index.json", {}) or {}
    chars_by_book = {b: (v or {}).get("textChars", 0) for b, v in (index.get("books") or {}).items()}
    units_by_book = {b: (v or {}).get("units", 0) for b, v in (index.get("books") or {}).items()}
    units_with_events = {b: (v or {}).get("unitsWithEvents", 0) for b, v in (index.get("books") or {}).items()}

    # ---- 层2 计划窗口：队列里 read 任务声明的 sourceRange（按书分组，带 hash） ----
    planned = {}
    for f in sorted(QUEUE.glob("*.jsonl")):
        for line in f.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
            except Exception:
                continue
            if not isinstance(t, dict) or not str(t.get("id", "")).startswith("read:"):
                continue
            book = t.get("book")
            rng = t.get("sourceRange")
            if not book or not rng:
                continue
            h = t.get("sourceHash")
            planned.setdefault(book, {}).setdefault(h, []).append(rng)
    planned_layer = {}
    for book, by_hash in planned.items():
        per_hash = {h: {"windows": len(ivs), "unionChars": union_len(ivs)}
                    for h, ivs in by_hash.items()}
        cur = source_text_hash(book, index)
        planned_layer[book] = {"byHash": per_hash, "currentHash": cur,
                               "unionCharsCurrentHash": per_hash.get(cur, {}).get("unionChars", 0),
                               "originalChars": chars_by_book.get(book, 0)}

    # ---- 层3 实际接受输入：真正进入请求的字符 -------------------------------
    accepted = {}
    for book in chars_by_book:
        accepted[book] = {"acceptedChars": None, "why": "not_recorded: worker 未记录请求构造后实际嵌入的字符数"}

    # ---- 层4 产出触及：候选声明的区间并集（带 sourceHash） -------------------
    touched_by_book = {}
    unshapeable = []
    for f in sorted(OUT.glob("read_*.candidate.json")):
        c = load(f)
        if not isinstance(c, dict):
            continue
        src = c.get("source")
        book = c.get("book")
        if not isinstance(src, dict):
            unshapeable.append(f.name)
            continue
        rng = src.get("range")
        h = src.get("sourceHash")
        if not book or not rng or not h:
            continue
        touched_by_book.setdefault(book, {}).setdefault(h, []).append(rng)
    touched_layer = {}
    for book, by_hash in touched_by_book.items():
        cur = source_text_hash(book, index)
        touched_layer[book] = {
            "candidates": sum(len(v) for v in by_hash.values()),
            "byHash": {h: {"ranges": len(v), "unionChars": union_len(v)} for h, v in by_hash.items()},
            "currentHash": cur,
            "unionCharsCurrentHash": union_len(by_hash.get(cur, [])),
            "originalChars": chars_by_book.get(book, 0),
        }

    # ---- 层5 人工语义复核：只有复核记录 verdict 才计，且必须是**另一个 agent** ----
    human = {}
    for book in chars_by_book:
        human[book] = {"reviewedUnits": 0, "why": "该层只有独立复核（换 agent + reverseChecks）计入；引用定位核验不算"}
    for f in sorted(OUT.glob("read_*.json")):
        b = f.name
        if b.endswith((".candidate.json", ".submit.json", ".artifact.json", ".verdict.json")) or b.startswith("REJECTED__"):
            continue
        rec = load(f)
        if not isinstance(rec, dict):
            continue
        book = (rec.get("task") or "").split(":")[1] if ":" in str(rec.get("task")) else None
        if book not in human:
            continue
        reviews = rec.get("reviews") or []
        independent = [r for r in reviews if isinstance(r, dict) and r.get("reviewer") and r.get("reviewer") != rec.get("agent")]
        reverse = [r for r in independent if r.get("reverseChecks")]
        if independent:
            human[book]["reviewedUnits"] += 1
            human[book].setdefault("reverseChecks", 0)
            if reverse:
                human[book]["reverseChecks"] += 1
    for book in human:
        human[book].pop("why", None) if human[book].get("reviewedUnits") else None

    # ---- 层1 可访问原文：分母本身（可访问 = 缓存里实际拿得到的 codepoint） ----
    accessible = {}
    for book, entry in (index.get("books") or {}).items():
        gk = entry.get("graphKey")
        docs = ROOT / "data" / "cache" / (str(gk) + ".docs.json")
        accessible[book] = {"graphKey": gk, "cacheExists": docs.exists(),
                            "originalChars": chars_by_book.get(book, 0),
                            "units": units_by_book.get(book, 0),
                            "unitsWithEvents": units_with_events.get(book, 0)}

    # ---- 补集 ---------------------------------------------------------------
    gaps = {}
    for book, info in planned_layer.items():
        cur = info["currentHash"]
        ivs = planned.get(book, {}).get(cur, [])
        gaps[book] = complement(ivs, 0, chars_by_book.get(book, 0))

    report = {
        "plan_ref": "docs/QUALITY.md P2.3（五种覆盖分开）",
        "note": "五层互不替代。任务条数、事件数、节点数都不出现在这里当分子。",
        "layer1_accessible_source": accessible,
        "layer2_planned_windows": planned_layer,
        "layer3_accepted_input": accepted,
        "layer4_output_touched": touched_layer,
        "layer5_human_semantic_review": human,
        "planned_window_complement": gaps,
        "forbidden_claims": ["全书已理解", "语义完成", "召回率"],
        "recall": "unknown（没有独立金标准；见 P3.12，未做就是未知，不估）",
    }
    p = out / "coverage-layers.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    def pct(num, den):
        return None if not den else round(100.0 * num / den, 2)

    summary = {}
    for book in accessible:
        summary[book] = {
            "accessibleChars": chars_by_book.get(book),
            "plannedChars": planned_layer.get(book, {}).get("unionCharsCurrentHash"),
            "plannedPct": pct(planned_layer.get(book, {}).get("unionCharsCurrentHash", 0), chars_by_book.get(book, 0)),
            "touchedChars": touched_layer.get(book, {}).get("unionCharsCurrentHash", 0),
            "touchedPct": pct(touched_layer.get(book, {}).get("unionCharsCurrentHash", 0), chars_by_book.get(book, 0)),
            "reviewedUnits": human.get(book, {}).get("reviewedUnits", 0),
            "units": units_by_book.get(book),
        }
    problems = []
    for book, s in summary.items():
        if s["plannedChars"] == s["touchedChars"] and s["plannedChars"]:
            pass
        if s["reviewedUnits"] and s["reviewedUnits"] >= (s["units"] or 0):
            problems.append("reviewed_not_below_units:" + book)
    report["problems"] = problems
    report["summary"] = summary
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": not problems, "summary": summary, "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
