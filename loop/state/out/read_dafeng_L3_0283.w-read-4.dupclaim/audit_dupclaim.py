#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计：read:dafeng:L3:0283 的**重复领取/竞态**取证 + 对既有候选的独立复核。

背景（先说清楚，免得被读成「我又精读了一遍」）：
  本任务 `read:dafeng:L3:0283` 由 `w-read-3` 提交并通过机器校验
  （记录 submittedAt = 2026-10-14T23:04:14Z，validation.problems = []）。
  我的租约（agent `w-read-4`，pid 43553）startedAt = 2026-10-14T23:05:45Z,
  **晚 91 秒**。也就是说：这一章已经被做完了，我是被 `pick()` 的陈旧快照
  放进来的一条重复领取（TOCTOU）。

本脚本**不重写候选**。硬理由（可复算，见 raceForensics.evictionProof）：
  task.writes[0] = `loop/state/out/read_dafeng_L3_0283.candidate.json`，
  而这个路径**同时是** w-read-3 记录里第 1 条 evidence 的 path。
  `is_evolving()` 对 `loop/state/out/` 返回 False（MUTABLE_EXCEPTIONS），
  所以改它一个字节 ⇒ `evidence_stale()` 报 hash-changed ⇒ 该任务被
  从 `done_ids()` 剔除 ⇒ 破坏另一个 agent 已提交的工作。

本脚本只做两件**不改动共享产物**的事：
  A. 竞态取证：时序、pick/claim 的窗口、以及「覆写会毁掉什么」落成可复现数字。
  B. 独立复核：**不 import** w-read-3 的任何构建/审计脚本，自己递归收集候选里
     所有含 quote/start/end 的对象，在 docs[0].text 上重算逐字命中与全部
     自述元数据（wholeTextOccurrences / occurrencesInRange /
     firstOccurrenceAt / startIsFirstOccurrence / inAuthorRegion）；
     再做一遍**反向检查**（这一段里还有什么原文事实是候选没写的），
     以及五栏共用、null 栏理由、place/item/rule 三态字段的结构判据。

  反向检查的口径是**句级**（候选自建自检只做到段级）：段级 171/171 全触达，
  句级（>=6 字、非作者区域）能查出 3 句没有被任何引文触及 —— 其中 1 句
  是候选自己 T06.action 文本**已经断言**的内容（「下水勘察…刻有佛文」），
  属于「叙述有、引文没有」的证据缺口。这是本脚本的主要新增发现。

可复现：
    python3 -B -s loop/state/out/read_dafeng_L3_0283.w-read-4.dupclaim/audit_dupclaim.py
输出：同目录 audit_dupclaim_report.json（确定性；不含时间戳等易变字段）
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data" / "cache" / "1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop" / "state" / "out" / "read_dafeng_L3_0283.candidate.json"
REC = ROOT / "loop" / "state" / "out" / "read_dafeng_L3_0283.json"
TASK = ROOT / "loop" / "state" / "runs" / "task-read_dafeng_L3_0283.json"
LEASE = ROOT / "loop" / "state" / "leases" / "read:dafeng:L3:0283.d" / "lease.json"

SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 1206041, 1212202
# 作者区域（PS/单章说明）。按纪律不作叙事证据。
AUTHOR_REGION = [(1211985, 1212200)]

FIELDS = ["objective", "obstacle", "action", "result", "cost"]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def delta_seconds(a, b):
    """两个 `%Y-%m-%dT%H:%M:%SZ` 之间的秒数（b - a）。"""
    from datetime import datetime
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return int((datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds())
    except Exception:
        return None


def load_text():
    docs = json.loads(DOCS.read_bytes())
    docs = docs if isinstance(docs, list) else docs["docs"]
    return docs[0]["text"]


def walk_quotes(obj, acc=None, path="$"):
    """递归收集所有含 quote/start/end 的对象（不依赖候选的任何脚本）。"""
    if acc is None:
        acc = []
    if isinstance(obj, dict):
        if isinstance(obj.get("start"), int) and isinstance(obj.get("end"), int) and "quote" in obj:
            acc.append((path, obj))
        for k, v in obj.items():
            walk_quotes(v, acc, path + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_quotes(v, acc, "%s[%d]" % (path, i))
    return acc


def overlapping_count(text, q, lo, hi):
    """自重叠计数：与候选 build_candidate.py 的 while/find(j+1) 口径一致。

    为什么不能用 `str.count`：分隔行 `.............` 自身重叠，
    `str.count` 给 244、逐位 find 给 357。候选的 wholeTextOccurrences
    用的是后者（357），用 str.count 去对账会得到 29 条**假阳性**。
    """
    n = 0
    cur = lo
    while True:
        j = text.find(q, cur)
        if j < 0 or j + len(q) > hi:
            break
        n += 1
        cur = j + 1
    return n


def range_first(text, q, lo, hi):
    """引文在 [lo,hi) 内**第一次**出现的位置（找不到返回 None）。

    这是候选用 `firstOccurrenceAt` / `startIsFirstOccurrence` 的口径
    （build_candidate.py:104-105 用区间内命中表 hits[0]），
    不是 `text.find(q)`（全文首次）。
    """
    cur = lo
    while True:
        j = text.find(q, cur)
        if j < 0 or j + len(q) > hi:
            return None
        return j


def main():
    text = load_text()
    sl = text[START:END]
    cand = json.loads(CAND.read_bytes())
    rec = json.loads(REC.read_bytes())
    task = json.loads(TASK.read_bytes())
    lease = json.loads(LEASE.read_bytes()) if LEASE.exists() else {}

    report = {
        "kind": "duplicate-claim investigation (READER, append-only)",
        "task": "read:dafeng:L3:0283",
        "agent": "w-read-4",
        "role": "READER",
        "outcome": "NOT SUBMITTED — submitting would have overwritten another agent's "
                   "committed, machine-validated candidate (see raceForensics.evictionProof)",
        "hashes": {
            "docsJson": sha256_file(DOCS),
            "candidate": sha256_file(CAND),
            "record(read_dafeng_L3_0283.json)": sha256_file(REC),
            "taskDefinition(task-read_dafeng_L3_0283.json)": sha256_file(TASK),
        },
        "offsetCaliber": {
            "declaredRange": [START, END],
            "sliceStartsWithUnitHead": sl[:9],
            "sliceCodepoints": len(sl),
            "expectedHead": "第五十四章 问答",
            "ok": sl.startswith("第五十四章 问答"),
            "sourceHashIsWholeDocsJson": sha256_file(DOCS) == SRC_HASH,
        },
    }

    # ── A. 竞态取证 ────────────────────────────────────────────────────────
    prior_submit = rec.get("submittedAt")
    my_lease_start = lease.get("startedAt")
    ev_paths = [e.get("path") for e in (rec.get("evidence") or [])]
    report["raceForensics"] = {
        "priorSubmitAt": prior_submit,
        "priorSubmitAgent": rec.get("agent"),
        "priorValidationProblems": (rec.get("validation") or {}).get("problems"),
        "myLeaseStartedAt": my_lease_start,
        "myLeaseAgent": lease.get("agent"),
        "deltaSeconds": delta_seconds(prior_submit, my_lease_start),
        "rootCause": (
            "pick() 与 claim() 之间存在 TOCTOU：worker.one_round 先 pick()"
            "（loop/bin/worker.py:519，其内部 loop/bin/loop.py:653 取 done=done_ids() **快照**）"
            "再 claim()（worker.py:525）。claim() 只判 lease_alive，"
            "**不复查 done**（loop.py:715 起）。done_ids() 要扫 960+ 个记录文件，"
            "快照耗时实测 40–202 秒，窗口足够长。"
        ),
        "taskWrites": task.get("writes"),
        "evictionProof": {
            "writePathIsAlsoEvidencePath": "loop/state/out/read_dafeng_L3_0283.candidate.json" in ev_paths,
            "evidenceIndex": ev_paths.index("loop/state/out/read_dafeng_L3_0283.candidate.json")
            if "loop/state/out/read_dafeng_L3_0283.candidate.json" in ev_paths else None,
            "isEvolving(loop/state/out/...)": False,
            "whyIsEvolvingFalse": "loop/state/out/ 命中 MUTABLE_EXCEPTIONS ⇒ is_evolving() 返回 False "
                                  "⇒ 哈希变化会被 evidence_stale() 记为 hash-changed（不是可容忍的演进）",
            "consequence": "覆写 candidate ⇒ evidence_stale() 非空 ⇒ 该任务从 done_ids() 剔除，"
                           "且 loop/state/out/ 属受保护产物，改它超出 READER 的追加式写入权限",
        },
    }

    # ── B. 独立复核：引文逐字 + 自述元数据 ────────────────────────────────
    qs = walk_quotes(cand)
    bad_literal = bad_range = bad_hash = bad_meta = 0
    meta_detail = []
    intervals = []
    for path, q in qs:
        s, e, qt = q["start"], q["end"], q["quote"]
        intervals.append((s, e))
        if text[s:e] != qt:
            bad_literal += 1
        if not (START <= s and e <= END):
            bad_range += 1
        if q.get("sourceHash") not in (None, SRC_HASH):
            bad_hash += 1
        wc = overlapping_count(text, qt, 0, len(text))
        rc = overlapping_count(text, qt, START, END)
        # `firstOccurrenceAt` / `startIsFirstOccurrence` 都是 **range-scoped**：
        # build_candidate.py:104-105 用的是 `hits`（区间内命中表）而不是全文 find。
        # 口径搞错会得到 23 条假阳性（「当！」「轰！」「.............」这类
        # 在区间外先出现过的串）—— 我第一版就是这么错的，已按实测口径改正。
        first = range_first(text, qt, START, END)
        want_ar = any(s < b and e > a for a, b in AUTHOR_REGION)
        for key, want in (("wholeTextOccurrences", wc),
                          ("occurrencesInRange", rc),
                          ("firstOccurrenceAt", first),
                          ("startIsFirstOccurrence", first is not None and s == first),
                          ("inAuthorRegion", want_ar)):
            if key in q and q[key] != want:
                bad_meta += 1
                if len(meta_detail) < 20:
                    meta_detail.append({"label": q.get("anchorLabel"), "field": key,
                                        "declared": q[key], "actual": want})

    report["independentAudit"] = {
        "script": "audit_dupclaim.py（不 import w-read-3 的任何构建/审计脚本）",
        "quoteObjects": len(qs),
        "badLiteral": bad_literal,
        "badRange": bad_range,
        "badSourceHash": bad_hash,
        "badSelfReportedMetadata": bad_meta,
        "metadataMismatchDetail": meta_detail,
        "uniqueIntervals": len(set(intervals)),
        "countCaliber": "重叠计数（find(j+1)），与 build_candidate.py:87-94 同口径；"
                        "用 str.count 会产生 29 条假阳性（分隔行/「当！」等自重叠串）",
    }

    # ── B2. 五栏结构性判据 ────────────────────────────────────────────────
    tasks = cand.get("tasks") or []
    overlap = shared = 0
    null_fields = []
    for tk in tasks:
        cols = {}
        for f in FIELDS:
            if tk.get(f) is None:
                note = tk.get(f + "Note")
                null_fields.append({"task": tk.get("id"), "field": f,
                                    "noteIsNonEmpty": bool(note and str(note).strip()),
                                    "noteIsPlaceholder": str(note).strip() == f + "Note"})
                continue
            cols[f] = [(q["start"], q["end"]) for q in (tk.get(f + "Quotes") or [])]
        for a in cols:
            for b in cols:
                if a >= b:
                    continue
                for x in cols[a]:
                    for y in cols[b]:
                        if x[0] < y[1] and y[0] < x[1]:
                            overlap += 1
                        if x == y:
                            shared += 1
    # 跨任务复用同一区间
    seen = {}
    for tk in tasks:
        for f in FIELDS:
            for q in (tk.get(f + "Quotes") or []):
                seen.setdefault((q["start"], q["end"]), set()).add(tk.get("id"))
    report["structuralChecks"] = {
        "tasks": len(tasks),
        "taskFieldIntervalOverlaps": overlap,
        "crossColumnSharedQuotes": shared,
        "crossTaskReusedIntervals": sum(1 for v in seen.values() if len(v) > 1),
        "nullFields": null_fields,
        "nullFieldsWithNotes": sum(1 for n in null_fields if n["noteIsNonEmpty"]),
        "nullFieldsWithPlaceholderNote": sum(1 for n in null_fields if n["noteIsPlaceholder"]),
    }

    # ── B3. 三态字段（place/item/rule）判据 ──────────────────────────────
    ws = cand.get("worldSettings") or []
    kinds = {}
    enum_bad = []
    ws_bad_quote = 0
    for w in ws:
        k = w.get("kind")
        kinds[k] = kinds.get(k, 0) + 1
        for q in [w.get("quote")] + list(w.get("extraQuotes") or []):
            if isinstance(q, dict) and text[q["start"]:q["end"]] != q["quote"]:
                ws_bad_quote += 1
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            enum_bad.append({"id": w.get("id"), "why": "placeState 非法：%r" % w.get("placeState")})
        if k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                enum_bad.append({"id": w.get("id"), "why": "itemStates 非法：%r" % (st,)})
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            enum_bad.append({"id": w.get("id"), "why": "institution 非法：%r" % w.get("institution")})
    report["worldSettingChecks"] = {
        "count": len(ws),
        "kinds": kinds,
        "badQuotes": ws_bad_quote,
        "enumViolations": enum_bad,
        "notWorldSettings": len(cand.get("notWorldSettings") or []),
        "notForeshadows": len(cand.get("notForeshadows") or []),
    }

    # ── B4. 反向检查（漏读）——段级 + 句级 ───────────────────────────────
    paragraphs = [(m.start() + START, m.end() + START)
                  for m in re.finditer(r"[^\n]+", sl) if m.group().strip()]
    iv = set(intervals)

    def uncovered(units):
        return [u for u in units if not any(a < u[1] and u[0] < b for a, b in iv)]

    def in_ar(u):
        return any(u[0] >= a and u[1] <= b for a, b in AUTHOR_REGION)

    up = uncovered(paragraphs)
    sentences = []
    for m in re.finditer(r"[^。！？\n]+[。！？]?", sl):
        if len(m.group().strip()) >= 6:
            sentences.append((m.start() + START, m.end() + START))
    us = [u for u in uncovered(sentences) if not in_ar(u)]
    report["reverseCheck"] = {
        "caliber": "段级（段落=非空行）+ 句级（>=6 字、排除作者区域）；"
                   "候选自建自检只做到段级",
        "paragraphs": len(paragraphs),
        "uncoveredParagraphs": len(up),
        "uncoveredParagraphsOutsideAuthorRegion": sum(1 for u in up if not in_ar(u)),
        "sentences": len(sentences),
        "uncoveredSentencesOutsideAuthorRegion": len(us),
        "uncoveredSentenceDetail": [
            {"at": u[0], "text": text[u[0]:u[1]][:120]} for u in us
        ],
    }

    # ── B5. 证据缺口：T06.action 文本断言了「下水勘察…刻有佛文」，引文未覆盖 ──
    t06 = next((t for t in tasks if t.get("id") == "T06"), None)
    gap = None
    if t06:
        target = "永镇山河庙炸毁，邪物脱困后，本官亲自下水勘察，发现残留的阵法石柱上，刻有佛文。"
        action_quotes = [q["quote"] for q in (t06.get("actionQuotes") or [])]
        at = text.find(target, START)
        covered_anywhere = any(text[q["start"]:q["end"]] == target for _, q in qs)
        gap = {
            "task": "T06",
            "column": "action",
            "assertedInColumnText": ("下水勘察" in str(t06.get("action"))
                                     and "佛文" in str(t06.get("action"))),
            "sentenceAt": at,
            "sentence": target,
            "sentenceIsVerbatimInSource": at >= 0,
            "coveredByAnyActionQuote": any("佛文" in q for q in action_quotes),
            "coveredByAnyCandidateQuote": covered_anywhere,
            "actionQuoteCount": len(action_quotes),
            "assessment": "「叙述有、引文没有」：T06.action 的文本把「他下水勘察发现石柱刻有佛文」"
                          "写进了断言，但该句没有被 T06 的 actionQuotes 引用。"
                          "该句在原文中逐字存在 ⇒ 这是**证据覆盖缺口**，不是编造；"
                          "按纪律应由复核者判定是否补引，本脚本只登记事实。",
        }
    report["evidenceGapProbe"] = gap

    # ── B6. 红线抽查：话语≠事实、结束≠成功、semanticReview ──────────────
    report["redLineProbe"] = {
        "semanticReview": cand.get("semanticReview"),
        "semanticReviewNotClaimedDone": cand.get("semanticReview") != "performed",
        "speechAsClueNotFactEntries": len(cand.get("speechAsClueNotFact") or []),
        "unknowns": len(cand.get("unknowns") or []),
        "selfCritique": len(cand.get("selfCritique") or []),
        "themeReadings": len(cand.get("themeReadings") or []),
        "themeReadingsWithCounter": sum(1 for t in (cand.get("themeReadings") or []) if t.get("counter")),
        "note": "本脚本只做结构/构造性核对；「因果边读得对不对」属语义，需复核者先读原文再判。",
    }

    report["deterministic"] = True
    out = Path(__file__).resolve().parent / "audit_dupclaim_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps({
        "wrote": str(out),
        "quoteObjects": report["independentAudit"]["quoteObjects"],
        "badLiteral": bad_literal, "badRange": bad_range,
        "badSourceHash": bad_hash, "badSelfReportedMetadata": bad_meta,
        "taskFieldIntervalOverlaps": overlap, "crossColumnSharedQuotes": shared,
        "uncoveredSentencesOutsideAuthorRegion": report["reverseCheck"]["uncoveredSentencesOutsideAuthorRegion"],
        "evidenceGap": bool(gap and gap["assertedInColumnText"] and not gap["coveredByAnyActionQuote"]),
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
