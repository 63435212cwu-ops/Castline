#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计：read:dafeng:L0:0224 的**重复领取/竞态**取证 + 对既有候选的独立复核。

先说清楚本轮的处境，免得被读成「我又精读了一遍」：

  本任务 `read:dafeng:L0:0224` 在我（w-xiyou-0，worker pid 43457）领取**之前 59 秒**，
  已由另一个 worker `w-sanguo-0` 提交并通过机器校验
  （submittedAt 2026-10-15T01:05:06Z，validation.problems=[]；
   我的租约 startedAt 2026-10-15T01:06:05Z）。
  也就是说：**这一章已经被做完了**，我是被 `pick()` 的陈旧快照放进来的一条重复领取。

所以本脚本**不重写候选**。理由不是客套，是可复现的机制：

  `writes` 路径 `loop/state/out/read_dafeng_L0_0224.candidate.json` 正是那份已完成记录的
  **证据文件**；`loop.py: is_evolving()` 对 `loop/state/out/`（MUTABLE_EXCEPTIONS）返回
  **False** —— 审阅产物被改写就是真问题。覆写它 ⇒ `evidence_stale()` 报 hash-changed
  ⇒ `done_ids()` 把该任务剔除 ⇒ 一条**已通过机器校验**的产物被降级成「没做完」。
  本脚本用 copy.deepcopy 在**内存里**复现这条危害（不碰磁盘上的既有文件）。

本脚本只做两件**不改动共享产物**的事：

  A. 竞态取证：时序、pick→claim 窗口、覆写危害，全部落成可复现数字。
  B. 独立复核：**不 import** w-sanguo-0 的任何构建/审计脚本（build/、gen_quotes、
     audit_candidate.py 一个都不用），自己读 docs.json 与产物 JSON，
     自行重新定位每一条引文、自行重算每一条覆盖率断言。

用法：
    python3 -B -s loop/state/out/read_dafeng_L0_0224.w-xiyou-0.dupclaim/audit_dupclaim.py
输出：确定性 JSON（stdout）。任何一项不成立即 exit 1。
"""

import copy
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0224.candidate.json")
RECORD = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0224.json")
LEASE = os.path.join(ROOT, "loop/state/leases/read:dafeng:L0:0224.d/lease.json")

TASK = "read:dafeng:L0:0224"
START, END = 841448, 845385
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

failures = []


def check(name, ok, detail=None):
    if not ok:
        failures.append({"check": name, "detail": detail})
    return ok


def sha256_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_loop():
    """只借 loop.py 的判据（is_evolving / evidence_stale / validated），
    不借 w-sanguo-0 的任何东西。"""
    spec = importlib.util.spec_from_file_location("loopbin_audit", os.path.join(ROOT, "loop/bin/loop.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def iter_quote_objects(obj, path=""):
    """递归收集所有 {quote,start,end} 对象，带出处路径（便于报告定位）。"""
    if isinstance(obj, dict):
        if isinstance(obj.get("quote"), str) and "start" in obj and "end" in obj:
            yield path, obj
        for k, v in obj.items():
            yield from iter_quote_objects(v, path + "." + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_quote_objects(v, path + "[%d]" % i)


def main():
    out = {"audit": "read:dafeng:L0:0224 dupclaim forensics + independent candidate audit",
           "agent": "w-xiyou-0", "at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}

    # ── 0. 源文件与切片 ────────────────────────────────────────────────
    src_hash = sha256_file(DOCS)
    check("sourceHash", src_hash == SRC_HASH, src_hash)
    docs = json.load(open(DOCS, encoding="utf-8"))
    text = docs[0]["text"]
    slice_ = text[START:END]
    slice_sha = hashlib.sha256(slice_.encode("utf-8")).hexdigest()
    check("sliceStartsAtHead", slice_.startswith("第两百二十三章 许七安的无奈之举"))
    out["source"] = {"docsJsonSha256": src_hash, "matchesTaskSourceHash": src_hash == SRC_HASH,
                     "sliceCodepoints": len(slice_), "sliceSha256": slice_sha,
                     "sliceStartsWithHead": slice_.startswith("第两百二十三章 许七安的无奈之举")}

    # ── A. 竞态取证 ───────────────────────────────────────────────────
    lease = json.load(open(LEASE, encoding="utf-8"))
    rec = json.load(open(RECORD, encoding="utf-8"))
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    delta = (datetime.strptime(lease["startedAt"], fmt)
             - datetime.strptime(rec["submittedAt"], fmt)).total_seconds()

    loop = load_loop()
    stale_now = loop.evidence_stale(rec)
    check("noStaleEvidenceAtAuditTime", stale_now == [], stale_now)
    check("priorRecordValidated", loop.validated(rec), rec.get("validation"))

    # 内存中复现覆写危害（不碰磁盘）
    rec2 = copy.deepcopy(rec)
    for e in rec2.get("evidence", []):
        if e.get("path", "").endswith("0224.candidate.json"):
            e["sha256"] = "0" * 64          # 模拟「候选被覆写 ⇒ 字节不同」
    stale_after = loop.evidence_stale(rec2)
    would_drop = not (loop.validated(rec2) and not stale_after)
    check("overwriteHazardDemonstrated", would_drop and stale_after
          and stale_after[0].get("why") == "hash-changed", stale_after)

    # 全部证据文件与哈希逐一复算
    ev = []
    for e in rec.get("evidence", []):
        p = os.path.join(ROOT, e["path"])
        exists = os.path.exists(p)
        now = sha256_file(p) if exists else None
        ev.append({"path": e["path"], "exists": exists,
                   "hashMatchesRecord": (now == e.get("sha256")),
                   "sha256Now": now})
    check("allEvidencePresentAndMatching",
          all(x["exists"] and x["hashMatchesRecord"] for x in ev),
          [x for x in ev if not (x["exists"] and x["hashMatchesRecord"])])

    out["raceForensics"] = {
        "myAgent": lease["agent"],
        "myLeasePid": lease["pid"],
        "myLeaseStartedAt": lease["startedAt"],
        "priorSubmission": {
            "agent": rec["agent"], "status": rec.get("status"),
            "submittedAt": rec.get("submittedAt"),
            "validationProblems": (rec.get("validation") or {}).get("problems"),
            "verifyState": rec.get("verifyState"),
            "recordPath": "loop/state/out/read_dafeng_L0_0224.json",
        },
        "secondsBetweenPriorSubmitAndMyLease": delta,
        "verdict": ("DUPLICATE CLAIM (TOCTOU): 任务在我领取前已提交并通过机器校验；"
                    "我是被 pick() 的陈旧 done 快照放进来的"),
        "isEvolvingCandidate": loop.is_evolving("loop/state/out/read_dafeng_L0_0224.candidate.json"),
        "isTransientCandidate": loop.is_transient("loop/state/out/read_dafeng_L0_0224.candidate.json"),
        "overwriteHazard": {
            "demonstratedInMemory": True,
            "staleAfterSimulatedOverwrite": stale_after,
            "why": ("loop/state/out/ 属 MUTABLE_EXCEPTIONS，is_evolving()=False ⇒ "
                    "覆写证据文件会让 evidence_stale() 报 hash-changed ⇒ "
                    "done_ids() 剔除该任务 ⇒ 一条已通过机器校验的产物被降级成『没做完』"),
        },
        "rootCause": {
            "where": ["loop/bin/loop.py:651 pick() → :653 done=done_ids() 为一次性快照",
                      "loop/bin/loop.py:715 claim() 只判 lease_alive / mkdir，不重查 done",
                      "loop/bin/worker.py:519 one_round(): pick() → claim() 两步不原子"],
            "measuredDoneIdsSeconds": None,   # 由 --timing 单独跑，避免把秒表混进确定性报告
            "note": "done_ids() 需遍历全部提交记录并逐个复算证据哈希，耗时远超 pick→claim 的间隔",
        },
        "evidence": ev,
    }

    # ── B. 独立复核既有候选 ───────────────────────────────────────────
    cand = json.load(open(CAND, encoding="utf-8"))
    check("candidateSliceShaMatchesRecompute", cand.get("sliceSha256") == slice_sha,
          {"claimed": cand.get("sliceSha256"), "recomputed": slice_sha})

    qs = list(iter_quote_objects(cand))
    bad_literal, bad_range, bad_hash, bad_unique_in_slice = [], [], [], []
    for path, q in qs:
        lit, s, e = q["quote"], q["start"], q["end"]
        # 逐字 + 偏移口径：text[start:end] == quote
        if text[s:e] != lit:
            bad_literal.append({"at": path, "quote": lit[:60]})
            continue
        if not (START <= s and e <= END):
            bad_range.append({"at": path, "start": s, "end": e})
        if q.get("sourceHash") != SRC_HASH:
            bad_hash.append({"at": path, "sourceHash": q.get("sourceHash")})
        if slice_.count(lit) != 1:
            bad_unique_in_slice.append({"at": path, "count": slice_.count(lit),
                                        "quote": lit[:60]})
    check("quotesVerbatim", not bad_literal, bad_literal[:5])
    check("quotesInSliceRange", not bad_range, bad_range[:5])
    check("quotesSourceHash", not bad_hash, bad_hash[:5])
    check("quotesUniqueWithinSlice", not bad_unique_in_slice, bad_unique_in_slice[:5])

    # 五栏互异：同一句话不得同时充当多栏依据
    col_reuse = []
    for t in cand.get("tasks", []):
        seen = {}
        for col in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(col)
            if not isinstance(v, dict):
                continue
            for q in (v.get("quotes") or []):
                seen.setdefault(q["quote"], []).append(col)
        for lit, cols in seen.items():
            if len(cols) > 1:
                col_reuse.append({"task": t.get("id"), "columns": cols, "quote": lit[:50]})
    check("fiveColumnsDoNotShareQuotes", not col_reuse, col_reuse)

    # 裸 null 必须带同名 *Note（不写理由的 null 判为未标注的未知）
    null_gaps = []
    for t in cand.get("tasks", []):
        for col in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(col) is None:
                note = t.get(col + "Note")
                if not isinstance(note, str) or not note.strip():
                    null_gaps.append({"task": t.get("id"), "column": col})
    check("nullColumnsCarryNote", not null_gaps, null_gaps)

    # worldSettings 三条区分必须写进字段
    ws_bad = []
    for w in cand.get("worldSettings", []):
        k = w.get("kind")
        if k == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                ws_bad.append({"id": w.get("id"), "why": "placeState 缺失/非法"})
        elif k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(
                    x not in ("hold", "transfer", "use", "lose") for x in st):
                ws_bad.append({"id": w.get("id"), "why": "itemStates 缺失/非法"})
        elif k == "rule":
            if w.get("institution") not in ("declared", "executed", "misunderstood"):
                ws_bad.append({"id": w.get("id"), "why": "institution 缺失/非法"})
        else:
            ws_bad.append({"id": w.get("id"), "why": "kind 非法"})
        if not w.get("explain"):
            ws_bad.append({"id": w.get("id"), "why": "explain 缺失"})
    check("worldSettingsStateFields", not ws_bad, ws_bad)

    # 伏笔：未回收要显式标 unresolved
    fs_bad = []
    for f in cand.get("foreshadows", []):
        st = f.get("status")
        if st not in ("resolved", "unresolved"):
            fs_bad.append({"id": f.get("id"), "why": "status 非法"})
        if st == "unresolved" and not f.get("payoffNote") and not f.get("note"):
            fs_bad.append({"id": f.get("id"), "why": "unresolved 未说明为何未回收"})
    check("foreshadowStatus", not fs_bad, fs_bad)

    # 主题解释：每条必须有 perspective / support / counter 三件
    th_bad = []
    for th in cand.get("themeReadings", []):
        for f in ("perspective", "support", "counter"):
            if not th.get(f):
                th_bad.append({"id": th.get("id"), "missing": f})
    check("themeReadingsHaveCounter", not th_bad, th_bad)

    # 覆盖率断言：自己按同一口径重算
    paras = [p for p in re.split(r"\n\s*\n", slice_) if p.strip()]
    # 每个引文在切片内的绝对区间 → 命中的段落号
    lits = sorted({q["quote"] for _, q in qs}, key=len, reverse=True)
    spans, cursor = [], 0
    para_spans = []
    for m in re.finditer(r"[^\n]+", slice_):
        if m.group().strip():
            para_spans.append((m.start(), m.end()))
    touched = set()
    for _, q in qs:
        s, e = q["start"] - START, q["end"] - START
        for i, (a, b) in enumerate(para_spans, 1):
            if s < b and e > a:
                touched.add(i)
    coverage = {"nonEmptyParagraphs": len(para_spans),
                "paragraphsTouchedByQuotes": len(touched),
                "zeroCoverageParagraphs": len(para_spans) - len(touched)}
    claimed_cov = cand.get("coverage", {})
    cov_match = all(claimed_cov.get(k) == v for k, v in coverage.items())
    check("coverageRecomputes", cov_match,
          {"claimed": {k: claimed_cov.get(k) for k in coverage}, "recomputed": coverage})

    out["independentAudit"] = {
        "script": "audit_dupclaim.py（不 import w-sanguo-0 的任何构建/审计脚本）",
        "quoteObjects": len(qs),
        "badLiteral": len(bad_literal), "badRange": len(bad_range),
        "badSourceHash": len(bad_hash), "notUniqueInSlice": len(bad_unique_in_slice),
        "fiveColumnReuse": len(col_reuse),
        "nullWithoutNote": len(null_gaps),
        "worldSettingsBad": len(ws_bad),
        "foreshadowBad": len(fs_bad),
        "themeBad": len(th_bad),
        "coverageCrossCheck": {"claimed": {k: claimed_cov.get(k) for k in coverage},
                               "recomputed": coverage, "matches": cov_match},
        "ok": not failures,
    }
    out["failures"] = failures
    out["ok"] = not failures

    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
