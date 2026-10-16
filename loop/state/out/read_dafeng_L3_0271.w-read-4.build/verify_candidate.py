#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结构判据复算 —— **不 import** build_candidate.py / content_0271.py 的任何东西。

它只做一件事：把候选 JSON 里的每一条引用/每一个判据，拿原文与文件系统**重算一遍**。
判据（每条都能被复核用同一脚本复现）：
  1. 源文件 sha256 == 候选与任务声明的 sourceHash；
  2. 切片边界：text[S:E] 以章题开头、以声明的 boundaryTail 结尾；
  3. 每一个 quote 对象：text[start:end] == quote 逐字成立、start<end、落在 [S,E) 内、sourceHash 正确；
  4. quote 的 start 落在其自称的 para 段内（段号口径 = 切片内非空段下标，0 是章题）；
  5. 同一任务的五栏引文区间两两不相交（提示词点名的 714/1664 共用一句问题）；
  6. null 栏必须有非空 <栏>Note；unresolved 伏笔必须有 unresolvedWhat；
  7. 枚举值合法（institution / placeState / itemStates / status）；
  8. 内容分区齐全（tasks/causeEdges/states/foreshadows/worldSettings/themeReadings）；
  9. 叙事引文不落在作者 PS/更新说明区间。

输出 JSON 报告（--report），rc=0 表示全部通过。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND = ROOT / "loop/state/out/read_dafeng_L3_0271.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
S, E = 1140984, 1147047
HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
AUTHOR_REGION = (1146784, 1147047)
TASK_FIELDS = ("objective", "obstacle", "action", "result", "cost")


def paragraphs(text):
    out, off = [], S
    for line in text[S:E].split("\n"):
        if line.strip():
            out.append((off, off + len(line), line))
        off += len(line) + 1
    return out


def walk_quotes(obj, path="$", out=None, narrative=True):
    """收集所有形如 {"quote": str, "start": int, ...} 的引用对象。"""
    if out is None:
        out = []
    if isinstance(obj, dict):
        if isinstance(obj.get("quote"), str) and isinstance(obj.get("start"), int) \
                and isinstance(obj.get("end"), int):
            out.append((path, obj, narrative))
            return out
        node_is_author = False
        for k, v in obj.items():
            walk_quotes(v, "%s.%s" % (path, k), out, narrative and not node_is_author)
        return out
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_quotes(v, "%s[%d]" % (path, i), out, narrative)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default=str(CAND))
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    problems, checks = [], []
    cand_path = Path(args.candidate)
    cand = json.loads(cand_path.read_text(encoding="utf-8"))
    docs = json.loads(DOCS.read_text(encoding="utf-8"))
    text = docs[0]["text"]
    paras = paragraphs(text)

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            problems.append("%s：%s" % (name, detail))
        return ok

    # 1. 源哈希
    actual_hash = hashlib.sha256(DOCS.read_bytes()).hexdigest()
    check("sourceHash 与 docs.json 实际 sha256 一致", actual_hash == HASH,
          "实际 %s / 声明 %s" % (actual_hash[:16], HASH[:16]))
    check("候选 source.sourceHash 一致", cand["source"]["sourceHash"] == HASH, "")

    # 2. 切片边界
    sl = text[S:E]
    head_ok = sl.startswith(cand["source"]["boundaryHead"])
    check("切片以声明 boundaryHead 开头", head_ok, "实际头部 %r" % sl[:20])
    check("boundaryHeadMatchesTitle 与实算一致",
          cand["source"]["boundaryHeadMatchesTitle"] == head_ok, "")
    check("切片以声明 boundaryTail 结尾", sl.endswith(cand["source"]["boundaryTail"]),
          "实际尾部 %r" % sl[-20:])
    check("切片 codepoint 数与声明一致",
          cand["source"]["codepoints"] == len(sl) and len(sl) == E - S,
          "声明 %d / 实际 %d" % (cand["source"]["codepoints"], len(sl)))
    check("切片 sha256 与声明一致",
          cand["source"]["sliceSha256"] == hashlib.sha256(sl.encode("utf-8")).hexdigest(), "")

    # 3/4. 引用逐条复算
    quotes = walk_quotes(cand)
    # 作者区域内引用的**豁免**由候选自己声明（authorRegionExemptions），复核只核对豁免是否名副其实：
    # 豁免必须落在 textualNotes 里，且理由非空。不豁免任何其他分区。
    EXEMPT_SECTIONS = ("$.textualNotes", "$.authorRegionExemptions", "$.coverage.ambiguousQuotes")
    exempt_ivs = {(x["start"], x["end"]) for x in (cand.get("authorRegionExemptions") or [])}
    exempt_bad = []
    for path, q, _ in quotes:
        if (q["start"], q["end"]) in exempt_ivs and not path.startswith(EXEMPT_SECTIONS):
            exempt_bad.append({"path": path, "start": q["start"],
                               "why": "豁免只能用于 textualNotes／其豁免登记／coverage.ambiguousQuotes"})
    bad_text, bad_range, bad_hash, bad_para, author_violation = [], [], [], [], []
    for path, q, narrative in quotes:
        s, e, qs = q["start"], q["end"], q["quote"]
        if s >= e or text[s:e] != qs:
            bad_text.append({"path": path, "quote": qs[:30], "start": s, "end": e,
                             "actual": text[s:e][:30]})
            continue
        if not (S <= s and e <= E):
            bad_range.append({"path": path, "start": s, "end": e})
        if q.get("sourceHash") != HASH:
            bad_hash.append({"path": path, "sourceHash": q.get("sourceHash")})
        if "para" in q:
            p = q["para"]
            if not (0 <= p < len(paras)) or not (paras[p][0] <= s < paras[p][1]):
                bad_para.append({"path": path, "para": p, "start": s,
                                 "pRange": [paras[p][0], paras[p][1]] if 0 <= p < len(paras) else None})
        if AUTHOR_REGION[0] <= s < AUTHOR_REGION[1] and (s, e) not in exempt_ivs:
            author_violation.append({"path": path, "start": s, "quote": qs[:30]})

    check("每个引用逐字成立（text[start:end]==quote）", not bad_text,
          "%d 处失败 %s" % (len(bad_text), bad_text[:3]))
    check("每个引用落在任务区间内", not bad_range, "%d 处越界 %s" % (len(bad_range), bad_range[:3]))
    check("每个引用带正确 sourceHash", not bad_hash, "%d 处缺失/不符" % len(bad_hash))
    check("每个引用的 para 段号与实际位置一致", not bad_para,
          "%d 处不符 %s" % (len(bad_para), bad_para[:3]))
    check("叙事引用不落在作者区 [%d,%d)（豁免仅 textualNotes）" % AUTHOR_REGION,
          not author_violation and not exempt_bad,
          "%d 处越界 %s / %d 处豁免越权 %s"
          % (len(author_violation), author_violation[:3], len(exempt_bad), exempt_bad[:3]))

    # 3b. 全局出现次数/首现位置复算
    occ_bad = []
    for path, q, _ in quotes:
        if "wholeTextOccurrences" in q:
            if q["wholeTextOccurrences"] != text.count(q["quote"]):
                occ_bad.append({"path": path, "quote": q["quote"][:20],
                                "claimed": q["wholeTextOccurrences"],
                                "actual": text.count(q["quote"])})
        if "occurrencesInRange" in q:
            if q["occurrencesInRange"] != sl.count(q["quote"]):
                occ_bad.append({"path": path, "field": "occurrencesInRange",
                                "claimed": q["occurrencesInRange"], "actual": sl.count(q["quote"])})
        if "firstOccurrenceAt" in q:
            if q["firstOccurrenceAt"] != text.find(q["quote"]):
                occ_bad.append({"path": path, "field": "firstOccurrenceAt",
                                "claimed": q["firstOccurrenceAt"], "actual": text.find(q["quote"])})
        if "startIsFirstOccurrence" in q:
            want = text.find(q["quote"]) == q["start"]
            if q["startIsFirstOccurrence"] != want:
                occ_bad.append({"path": path, "field": "startIsFirstOccurrence",
                                "claimed": q["startIsFirstOccurrence"], "actual": want})
    check("引用的出现次数/首现位置声明与实算一致", not occ_bad,
          "%d 处不符 %s" % (len(occ_bad), occ_bad[:3]))

    # 5. 同一任务五栏区间两两不相交
    overlaps = []
    for t in cand["tasks"]:
        ivs = []
        for f in TASK_FIELDS:
            for q in (t.get(f + "Quotes") or []):
                ivs.append((f, q["start"], q["end"]))
        for i in range(len(ivs)):
            for j in range(i + 1, len(ivs)):
                f1, s1, e1 = ivs[i]
                f2, s2, e2 = ivs[j]
                if s1 < e2 and s2 < e1:
                    overlaps.append({"task": t["id"], "a": f1, "b": f2,
                                     "aRange": [s1, e1], "bRange": [s2, e2]})
    check("同一任务五栏引文区间两两不相交", not overlaps,
          "%d 处共用 %s" % (len(overlaps), overlaps[:3]))

    # 5b. 每栏引文非空（除 null 栏）
    empty_field = []
    for t in cand["tasks"]:
        for f in TASK_FIELDS:
            val = t.get(f)
            qs = t.get(f + "Quotes") or []
            if val is None:
                if qs:
                    empty_field.append("%s.%s 是 null 却带引文" % (t["id"], f))
                if not (t.get(f + "Note") or "").strip():
                    empty_field.append("%s.%s 是 null 却没有 Note" % (t["id"], f))
            else:
                if not qs:
                    empty_field.append("%s.%s 有值却没有引文" % (t["id"], f))
                if not (t.get(f + "Basis") or "").strip():
                    empty_field.append("%s.%s 缺 basis" % (t["id"], f))
    check("五栏「有值必有引文／null 必有 Note」", not empty_field,
          "%d 处 %s" % (len(empty_field), empty_field[:5]))

    # 6. 伏笔/边
    fs_problems = []
    for f in cand["foreshadows"]:
        if f["status"] == "unresolved" and not (f.get("unresolvedWhat") or "").strip():
            fs_problems.append("%s unresolved 无 unresolvedWhat" % f["id"])
        if f["payoff"] is None and f["status"] != "unresolved":
            fs_problems.append("%s 无 payoff 却非 unresolved" % f["id"])
        if not (f.get("setup") or {}).get("quotes"):
            fs_problems.append("%s 铺设无引文" % f["id"])
    check("伏笔：unresolved 必须写明缺什么", not fs_problems, "%s" % fs_problems[:4])

    edge_problems = []
    for e in cand["causeEdges"]:
        if not (e.get("trigger") or "").strip():
            edge_problems.append("%s 缺 trigger" % e["id"])
        if not (e.get("mechanism") or "").strip():
            edge_problems.append("%s 缺 mechanism" % e["id"])
        if not (e.get("from") and e.get("to")):
            edge_problems.append("%s 缺方向" % e["id"])
    check("因果边：每条有方向＋触发＋机制", not edge_problems, "%s" % edge_problems[:4])

    # 7. 枚举
    enum_bad = []
    for w in cand["worldSettings"]:
        if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            enum_bad.append("%s institution=%r" % (w["id"], w.get("institution")))
        if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            enum_bad.append("%s placeState=%r" % (w["id"], w.get("placeState")))
        if w["kind"] == "item":
            st = w.get("itemStates") or []
            if not st or [x for x in st if x not in ("hold", "transfer", "use", "lose")]:
                enum_bad.append("%s itemStates=%r" % (w["id"], st))
        if w["kind"] not in ("rule", "place", "item"):
            enum_bad.append("%s kind=%r" % (w["id"], w["kind"]))
        if not (w.get("explain") or "").strip():
            enum_bad.append("%s 缺 explain" % w["id"])
    check("worldSettings 枚举值与 explain 齐全", not enum_bad, "%s" % enum_bad[:5])

    # 8. 分区齐全 + 主题三件套
    want = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
    missing = [k for k in want if k not in cand]
    check("内容分区齐全", not missing, "缺 %s" % missing)
    th_bad = []
    for t in cand["themeReadings"]:
        if not (t.get("perspective") or "").strip():
            th_bad.append("%s 缺 perspective" % t["id"])
        if not t.get("support"):
            th_bad.append("%s 缺 support" % t["id"])
        if not t.get("counter"):
            th_bad.append("%s 缺 counter（只列支持不叫解释）" % t["id"])
    check("主题读法：perspective＋support＋counter 齐全", not th_bad, "%s" % th_bad)

    # 9. 覆盖统计独立重算
    ivs = sorted({(q["start"], q["end"]) for _, q, _ in quotes})
    union, cur = 0, None
    for s, e in ivs:
        if cur is None:
            cur = [s, e]
        elif s <= cur[1]:
            cur[1] = max(cur[1], e)
        else:
            union += cur[1] - cur[0]
            cur = [s, e]
    if cur:
        union += cur[1] - cur[0]
    cov = cand.get("coverage") or {}
    check("coverage 并集码点数与实算一致", cov.get("quoteUnionCodepoints") == union,
          "声明 %r / 实算 %d" % (cov.get("quoteUnionCodepoints"), union))
    check("coverage 唯一区间数与实算一致", cov.get("quoteIntervals") == len(ivs),
          "声明 %r / 实算 %d" % (cov.get("quoteIntervals"), len(ivs)))
    check("semanticReview 未被声称为完成",
          cand.get("semanticReview") == "not-performed", "实际 %r" % cand.get("semanticReview"))

    report = {
        "candidate": str(cand_path.relative_to(ROOT)),
        "candidateSha256": hashlib.sha256(cand_path.read_bytes()).hexdigest(),
        "quoteObjects": len(quotes),
        "uniqueIntervals": len(ivs),
        "unionCodepoints": union,
        "checks": checks,
        "problems": problems,
        "verdict": "pass" if not problems else "fail",
    }
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in checks:
        print("[%s] %s %s" % ("OK " if c["ok"] else "BAD", c["check"], c["detail"] or ""))
    print("引文对象 %d / 唯一区间 %d / 并集 %d 码点" % (len(quotes), len(ivs), union))
    print("判定：%s（%d 个问题）" % (report["verdict"], len(problems)))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
