#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三方独立重建审计 —— **不 import** build_candidate.py / content_0271.py 的任何东西。

与 verify_candidate.py 的分工：verify 查「账目」（引文逐字、区间、枚举、五栏不共用）；
本脚本查**提示词点名的红线**，这些是结构性判据查不出来的：

  A. **越界实体**：用图谱缓存的 characters[].name + aliases 当候选清单（图谱只用来产生名单，
     **不作原文证据**），逐个在切片里 count；凡「切片内 0 次出现」却在候选**断言分区**里被使用的
     名字 ⇒ FAIL（编造原文里没有的人物）。
  B. **未标注的未知**：null 栏无 Note、unresolved 伏笔无 unresolvedWhat、因果边无机制、
     speechAsClue 缺 why、worldSettings 缺 explain、themeReadings 缺 counter ⇒ 逐条列出。
  C. **cost 栏的口径抽查**：cost 非 null 的条目必须带引文（代价要有原文依据）；
     cost 为 null 的必须有理由（红线：「不写理由的 null 会被判为未标注的未知」）。
  D. **「结束≠成功」抽查**：列出所有 result 栏为 null 或含失败措辞的条目，供人复核有没有把
     任务结束/播放到结尾写成成功。
  E. **作者区域**：统计叙事引文落在 AUTHOR_REGION 的数量（豁免必须来自 textualNotes）。
  F. **五栏依据是否共用同一句**：独立重算（不读候选的 machineSelfCheck）。

输出 JSON 报告（--report），rc=0 表示 ok。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND_PATH = ROOT / "loop/state/out/read_dafeng_L3_0271.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
GRAPH = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"
HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 1140984, 1147047
AUTHOR_REGION = (1146784, 1147047)

# 元字段：这里提到一个名字属于「说明/记录」，不算断言。
META_KEYS = {"provenanceNote", "semanticReviewNote", "selfCritique", "selfCritiqueNote",
             "nullFieldRule", "coverage", "machineSelfCheck", "basisLegend", "source",
             "namingConvention", "authorRegionNote", "authorRegionExemptions", "speechQuotingFieldsNote"}
# 断言分区：名字出现在这里就是拿它当事实用。
ASSERT_KEYS = {"tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps", "foreshadows",
               "notForeshadows", "worldSettings", "notWorldSettings", "themeReadings",
               "textualNotes", "unknowns", "speechAsClueNotFact"}

TASK_FIELDS = ("objective", "obstacle", "action", "result", "cost")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    cand = json.loads(CAND_PATH.read_text(encoding="utf-8"))
    text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    sl = text[S:E]
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))

    findings, fails = [], []

    # ── A. 越界实体 ────────────────────────────────────────────────
    names = set()
    for c in graph.get("characters") or []:
        if c.get("name"):
            names.add(c["name"])
        for a in c.get("aliases") or []:
            if a:
                names.add(a)
    # 只测「长度 >= 2 且是中文人名形态」的名字，避免单词误报（如「风」「辰」）
    suspects = sorted({n for n in names if len(n) >= 2 and n not in sl})
    leaked = []
    for path, s in flatten_strings(cand):
        top = path.split(".")[1].split("[")[0] if path.startswith("$.") else ""
        if top in META_KEYS or top not in ASSERT_KEYS:
            continue
        for n in suspects:
            if n in s:
                leaked.append({"path": path, "name": n, "text": s[:80]})
    if leaked:
        fails.append("越界实体：断言分区里出现了切片中不存在的名字 %d 处" % len(leaked))
    findings.append({"check": "越界实体（断言分区不得使用切片外的图谱人名）",
                     "ok": not leaked, "detail": leaked[:10],
                     "note": "候选清单来自图谱 characters[].name+aliases（%d 个），只作名单、不作证据"
                             % len(names)})

    # ── B. 未标注的未知 ────────────────────────────────────────────
    unlabeled = []
    for t in cand["tasks"]:
        for f in TASK_FIELDS:
            if t.get(f) is None and not (t.get(f + "Note") or "").strip():
                unlabeled.append("%s.%s 是 null 且无 Note" % (t["id"], f))
    for f in cand["foreshadows"]:
        if f["status"] == "unresolved" and not (f.get("unresolvedWhat") or "").strip():
            unlabeled.append("%s unresolved 无 unresolvedWhat" % f["id"])
    for e in cand["causeEdges"]:
        if not (e.get("mechanism") or "").strip():
            unlabeled.append("%s 因果边无 mechanism" % e["id"])
    for s in cand["speechAsClueNotFact"]:
        if not (s.get("why") or "").strip():
            unlabeled.append("%s 台词条目缺 why" % s["id"])
    for w in cand["worldSettings"]:
        if not (w.get("explain") or "").strip():
            unlabeled.append("%s worldSetting 缺 explain" % w["id"])
    for t in cand["themeReadings"]:
        if not t.get("counter"):
            unlabeled.append("%s 主题读法缺 counter" % t["id"])
    if unlabeled:
        fails.append("未标注的未知 %d 处" % len(unlabeled))
    findings.append({"check": "未标注的未知（null/悬置处必须有理由）",
                     "ok": not unlabeled, "detail": unlabeled[:10]})

    # ── C. cost 口径抽查 ──────────────────────────────────────────
    cost_bad = []
    for t in cand["tasks"]:
        if t.get("cost") is None:
            if not (t.get("costNote") or "").strip():
                cost_bad.append("%s cost=null 无理由" % t["id"])
        else:
            if not (t.get("costQuotes") or []):
                cost_bad.append("%s cost 有值却无引文" % t["id"])
    findings.append({"check": "cost 栏：有值必有引文／null 必有理由",
                     "ok": not cost_bad, "detail": cost_bad})
    if cost_bad:
        fails.append("cost 口径问题 %d 处" % len(cost_bad))
    costs = [{"task": t["id"], "cost": t.get("cost"), "note": t.get("costNote")} for t in cand["tasks"]]

    # ── D. 结束≠成功 抽查 ─────────────────────────────────────────
    results = []
    for t in cand["tasks"]:
        results.append({"task": t["id"], "actor": t["actor"],
                        "result": t.get("result"), "resultNote": t.get("resultNote")})
    null_results = [r["task"] for r in results if r["result"] is None]
    findings.append({"check": "result 栏（人工复核用：null 或失败措辞不得写成成功）",
                     "ok": True, "detail": {"nullResults": null_results,
                                            "note": "本检查只列清单供复核，不做自动判定"}})

    # ── E. 作者区域 ────────────────────────────────────────────────
    exempt = {(x["start"], x["end"]) for x in (cand.get("authorRegionExemptions") or [])}
    def walk(obj, path="$"):
        out = []
        if isinstance(obj, dict):
            if isinstance(obj.get("quote"), str) and isinstance(obj.get("start"), int):
                out.append((path, obj))
                return out
            for k, v in obj.items():
                out += walk(v, "%s.%s" % (path, k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                out += walk(v, "%s[%d]" % (path, i))
        return out
    in_author = [{"path": p, "quote": q["quote"][:20]} for p, q in walk(cand)
                 if AUTHOR_REGION[0] <= q["start"] < AUTHOR_REGION[1]]
    bad_author = [x for x in in_author if (x["path"],) and not x["path"].startswith("$.textualNotes")
                  and not x["path"].startswith("$.authorRegionExemptions")
                  and not x["path"].startswith("$.coverage")]
    findings.append({"check": "作者区域 [%d,%d) 内的引用只出现在 textualNotes/豁免登记"
                     % AUTHOR_REGION, "ok": not bad_author,
                     "detail": {"inAuthorRegion": in_author, "illegal": bad_author}})
    if bad_author:
        fails.append("作者区域引用越权 %d 处" % len(bad_author))

    # ── F. 五栏依据共用同一句（独立重算）──────────────────────────
    reuse = []
    for t in cand["tasks"]:
        seen = {}
        for f in TASK_FIELDS:
            for q in (t.get(f + "Quotes") or []):
                key = (q["start"], q["end"])
                if key in seen:
                    reuse.append({"task": t["id"], "a": seen[key], "b": f, "range": key})
                seen[key] = f
    findings.append({"check": "同一任务五栏不共用同一引文区间（独立重算）",
                     "ok": not reuse, "detail": reuse[:10]})
    if reuse:
        fails.append("五栏共用依据 %d 处" % len(reuse))

    # ── G. 哈希与切片（独立重算，不读候选的 machineSelfCheck）────
    real = hashlib.sha256(DOCS.read_bytes()).hexdigest()
    findings.append({"check": "源文件 sha256 独立重算", "ok": real == HASH, "detail": real})
    if real != HASH:
        fails.append("源哈希不符")
    findings.append({"check": "切片长度独立重算", "ok": len(sl) == E - S, "detail": len(sl)})
    findings.append({"check": "semanticReview 未被声称完成",
                     "ok": cand.get("semanticReview") == "not-performed",
                     "detail": cand.get("semanticReview")})

    report = {
        "candidateSha256": hashlib.sha256(CAND_PATH.read_bytes()).hexdigest(),
        "findings": findings,
        "costs": costs,
        "results": results,
        "fails": fails,
        "verdict": "ok" if not fails else "fail",
    }
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for f in findings:
        print("[%s] %s" % ("OK " if f["ok"] else "BAD", f["check"]))
        if not f["ok"]:
            print("     ", json.dumps(f["detail"], ensure_ascii=False)[:400])
    print("独立审计：%s（%d 个问题）" % (report["verdict"], len(fails)))
    for x in fails:
        print("  -", x)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
