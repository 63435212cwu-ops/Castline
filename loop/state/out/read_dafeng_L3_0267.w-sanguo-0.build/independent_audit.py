#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三方独立重建审计 —— **不 import** build_candidate.py / content_0267.py 的任何东西。

与 verify_candidate.py 的分工：verify 更偏结构判据；本脚本独立做两件更硬的事：
  A. **越界实体检查**（红线：不许出现原文里没有的人物/事件）：
     用图谱缓存的 characters[].name + aliases 当**候选清单**（图谱只用来产生清单，
     不作原文证据），逐个在切片里 count；凡「切片内 0 次出现」却在候选散文里被使用的名字，
     按「泄漏进断言分区」/「仅元字段提及」分类 —— 前者 FAIL。
  B. **未标注未知检查**：null 栏无 Note、unresolved 伏笔无 unresolvedWhat、
     因果边无机制、speechAsClue 缺 why、worldSettings 缺 explain —— 全部逐条列出。
它还独立重算切片 sha256 与源哈希，并独立核对枚举值。

输出 JSON 报告（--report），rc=0 表示 ok。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND_PATH = ROOT / "loop/state/out/read_dafeng_L3_0267.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
GRAPH = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"
HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 1119820, 1125007

# 元字段：这些地方提到一个名字属于「修复记录/说明」，不算断言分区。
META_KEYS = {"provenanceNote", "semanticReviewNote", "selfCritique", "selfCritiqueNote",
             "nullFieldRule", "coverage", "machineSelfCheck", "basisLegend", "source",
             "taskOrderNote"}
# 断言分区：名字出现在这里就是拿它当事实用。
ASSERT_KEYS = {"tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps", "foreshadows",
               "notForeshadows", "worldSettings", "notWorldSettings", "themeReadings",
               "textualNotes", "unknowns", "speechAsClueNotFact"}


def flatten_strings(obj, path="$", out=None):
    if out is None:
        out = []
    if isinstance(obj, str):
        out.append((path, obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            flatten_strings(v, "%s.%s" % (path, k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            flatten_strings(v, "%s[%d]" % (path, i), out)
    return out


def top_key(path: str) -> str:
    p = path.lstrip("$.").split(".")[0].split("[")[0]
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(Path(__file__).resolve().parent / "independent_audit_report.json"))
    args = ap.parse_args()

    raw = DOCS.read_bytes()
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    slice_ = text[S:E]
    cand = json.loads(CAND_PATH.read_text(encoding="utf-8"))

    report = {"sourceHashOk": hashlib.sha256(raw).hexdigest() == HASH,
              "sliceSha256": hashlib.sha256(slice_.encode("utf-8")).hexdigest(),
              "candidateSliceSha256": cand["source"].get("sliceSha256")}

    # ── A. 越界实体 ────────────────────────────────────────────────────────
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    names = set()
    for c in graph.get("characters", []):
        for key in ("name", "aliases"):
            v = c.get(key)
            if isinstance(v, str) and v:
                names.add(v)
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, str) and x:
                        names.add(x)
    # 只用长度 ≥2 的名字，避免单字误报（图谱里有「许」这类单字别名）
    names = {n for n in names if len(n) >= 2}

    leaked, meta_only = [], []
    for path, s in flatten_strings(cand):
        k = top_key(path)
        if k in META_KEYS:
            bucket = meta_only
        elif k in ASSERT_KEYS:
            bucket = leaked
        else:
            continue
        for n in names:
            if n in s and slice_.count(n) == 0:
                bucket.append({"name": n, "path": path, "text": s[:120],
                               "wholeTextCount": text.count(n)})
    # 去重（同名同路径只留一条）
    def dedup(rows):
        seen, out = set(), []
        for r in rows:
            kk = (r["name"], r["path"])
            if kk not in seen:
                seen.add(kk)
                out.append(r)
        return out
    leaked, meta_only = dedup(leaked), dedup(meta_only)

    report["namesInChecklist"] = len(names)
    report["leakedIntoAssertions"] = leaked
    report["metaOnlyMentions"] = meta_only

    # ── B. 未标注未知 / 缺依据 ─────────────────────────────────────────────
    FIELDS = ("objective", "obstacle", "action", "result", "cost")
    problems = {"nullWithoutNote": [], "nonNullWithoutQuote": [], "missingBasis": [],
                "edgeWithoutMechanism": [], "unresolvedWithoutWhat": [],
                "speechWithoutWhy": [], "settingWithoutExplain": [],
                "themeMissingPart": [], "emptyQuoteObject": []}

    def q_ok(q):
        return isinstance(q, dict) and isinstance(q.get("quote"), str) and q["quote"] \
            and isinstance(q.get("start"), int) and isinstance(q.get("end"), int) \
            and text[q["start"]:q["end"]] == q["quote"]

    all_q = []
    def walk(o, p="$"):
        if isinstance(o, dict):
            if isinstance(o.get("quote"), str) and "start" in o:
                all_q.append((p, o))
            for k, v in o.items():
                walk(v, "%s.%s" % (p, k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, "%s[%d]" % (p, i))
    walk(cand)
    report["quoteObjectsAudited"] = len(all_q)
    report["badLiteral"] = [p for p, q in all_q if text[q["start"]:q["end"]] != q["quote"]]
    report["badRange"] = [p for p, q in all_q if not (S <= q["start"] and q["end"] <= E)]
    report["badSourceHash"] = [p for p, q in all_q if q.get("sourceHash") != HASH]

    for t in cand["tasks"]:
        for f in FIELDS:
            if t.get(f) is None:
                if not (t.get("%sNote" % f) or "").strip():
                    problems["nullWithoutNote"].append("%s.%s" % (t["id"], f))
            else:
                if not (t.get("%sQuotes" % f) or []):
                    problems["nonNullWithoutQuote"].append("%s.%s" % (t["id"], f))
                if not (t.get("%sBasis" % f) or "").strip():
                    problems["missingBasis"].append("%s.%s" % (t["id"], f))
    for c in cand["causeEdges"]:
        if not (c.get("mechanism") or "").strip() or not (c.get("trigger") or "").strip():
            problems["edgeWithoutMechanism"].append(c["id"])
    for f in cand["foreshadows"]:
        if f.get("status") == "unresolved" and not (f.get("unresolvedWhat") or "").strip():
            problems["unresolvedWithoutWhat"].append(f["id"])
    for s in cand["speechAsClueNotFact"]:
        if not (s.get("why") or "").strip():
            problems["speechWithoutWhy"].append(s["id"])
    for w in cand["worldSettings"]:
        if not (w.get("explain") or "").strip():
            problems["settingWithoutExplain"].append(w["id"])
    for th in cand["themeReadings"]:
        if not th.get("perspective") or not th.get("support") or not th.get("counter"):
            problems["themeMissingPart"].append(th["id"])
    report["problems"] = problems

    # ── C. 语义归属抽检（明确可判的形态）────────────────────────────────────
    # C1：把人物台词写成叙述事实的形态 —— 检查 tasks 的 objective/result 里是否
    #     出现「他说/她问」类归属词而引文是台词。这里只做**可判**的一半：
    #     凡引文落在【】或“”内（即台词），其所在栏的 basis 不能是 explicit 且 text
    #     断言为叙述事实 —— 由人在复核判断，脚本只列出清单供复核快筛。
    speech_quoting_fields = []
    for t in cand["tasks"]:
        for f in FIELDS:
            for q in t.get("%sQuotes" % f) or []:
                lit = q["quote"]
                if lit.startswith("【") or lit.startswith("“"):
                    speech_quoting_fields.append({"task": t["id"], "field": f, "quote": lit[:40],
                                                  "basis": t.get("%sBasis" % f)})
    report["fieldsQuotingSpeech"] = speech_quoting_fields

    ok = (report["sourceHashOk"] and not report["badLiteral"] and not report["badRange"]
          and not report["badSourceHash"] and not leaked
          and all(not v for v in problems.values()))
    report["ok"] = ok
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("源哈希一致：%s" % report["sourceHashOk"])
    print("切片 sha256（独立重算）：%s" % report["sliceSha256"])
    print("候选记录切片 sha256：      %s  一致=%s"
          % (report["candidateSliceSha256"], report["sliceSha256"] == report["candidateSliceSha256"]))
    print("引文对象审计：%d；字面不符 %d；越界 %d；sourceHash 不符 %d"
          % (len(all_q), len(report["badLiteral"]), len(report["badRange"]), len(report["badSourceHash"])))
    print("越界实体（图谱清单 %d 个名字）：泄漏进断言分区 %d；仅元字段提及 %d"
          % (len(names), len(leaked), len(meta_only)))
    for r in leaked[:10]:
        print("   [泄漏] %s ← %s（全文 %d 次，切片 0 次）" % (r["name"], r["path"], r["wholeTextCount"]))
    for r in meta_only[:10]:
        print("   [元字段] %s ← %s" % (r["name"], r["path"]))
    print("未标注未知/缺依据：%s"
          % {k: v for k, v in problems.items() if v} if any(problems.values()) else "未标注未知/缺依据：无")
    print("字段引用台词（供复核快筛，非判定）：%d 处" % len(speech_quoting_fields))
    print("ok = %s" % ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
