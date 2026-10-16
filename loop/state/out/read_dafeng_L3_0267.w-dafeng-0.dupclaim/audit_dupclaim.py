#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计：read:dafeng:L3:0267 的**重复领取/竞态**取证 + 对既有候选的独立复核。

背景（本轮真实处境，先说清楚，免得被读成"我又精读了一遍"）：
  本任务 `read:dafeng:L3:0267` 在我（w-dafeng-0，pid 43423）领取**之前** 39 秒，
  已由另一个 worker `w-sanguo-0` 提交并通过机器校验（submittedAt 2026-10-14T18:37:14Z；
  我的租约 startedAt 2026-10-14T18:37:53Z）。也就是说：**这一章已经被做完了**，
  我是被 `pick()` 的陈旧快照放进来的一条重复领取。

所以本脚本**不重写候选**（writes 路径 `loop/state/out/read_dafeng_L3_0267.candidate.json`
是那个已完成候选的证据文件，`is_evolving()` 对它返回 False ⇒ 改一个字节就会让
`evidence_stale()` 报 hash-changed、把已通过的任务从 `done_ids()` 里剔除）。
本脚本只做两件**不改动共享产物**的事：

  A. 竞态取证：把我这一轮的时序、pick/claim 的窗口、以及"覆写会毁掉什么"全部落成可复现数字。
  B. 独立复核：**不 import** w-sanguo-0 的任何构建/审计脚本，自己递归收集候选里所有
     quote 对象，在 docs[0].text 上重算逐字命中；并自己做一遍**反向检查**
     （这一段里还有什么原文事实是候选没写的），以及五栏共用、null 栏理由、三态字段的结构判据。

可复现：
    python3 -B -s loop/state/out/read_dafeng_L3_0267.w-dafeng-0.dupclaim/audit_dupclaim.py
输出：同目录 audit_dupclaim_report.json（确定性；不含时间戳等易变字段）
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data" / "cache" / "1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop" / "state" / "out" / "read_dafeng_L3_0267.candidate.json"
REC = ROOT / "loop" / "state" / "out" / "read_dafeng_L3_0267.json"
TASK = ROOT / "loop" / "state" / "runs" / "task-read_dafeng_L3_0267.json"
LEASE = ROOT / "loop" / "state" / "leases" / "read:dafeng:L3:0267.d" / "lease.json"

SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _delta_seconds(a, b):
    """两个 `%Y-%m-%dT%H:%M:%SZ` 字符串之间的秒数（b - a）。解析失败返回 None。"""
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


def walk_quotes(obj, path=""):
    """递归收集所有 {'quote': str, 'start': int, 'end': int} 形态的引文对象。

    刻意写得比候选自己的审计更宽：只要 dict 里有 quote 就去核，不管它挂在哪个分区
    （textualNotes / worldSettings / themeReadings.support / foreshadows.setup ... 都覆盖）。
    """
    if isinstance(obj, dict):
        if isinstance(obj.get("quote"), str):
            yield path, obj
        for k, v in obj.items():
            yield from walk_quotes(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_quotes(v, path + "[%d]" % i)


def main() -> int:
    report = {}
    text = load_text()
    raw_docs_hash = sha256_file(DOCS)
    task = json.loads(TASK.read_bytes())
    s, e = task["sourceRange"]
    sl = text[s:e]
    cand = json.loads(CAND.read_bytes())
    rec = json.loads(REC.read_bytes())
    lease = json.loads(LEASE.read_bytes()) if LEASE.exists() else {}

    # ── 0. 源与口径 ────────────────────────────────────────────────────────
    report["source"] = {
        "docsPath": str(DOCS.relative_to(ROOT)),
        "docsSha256": raw_docs_hash,
        "docsSha256MatchesTask": raw_docs_hash == task["sourceHash"],
        "textCodepoints": len(text),
        "sliceRange": [s, e],
        "sliceCodepoints": len(sl),
        "sliceStartsWithUnitHead": sl.startswith(task["unitHead"]),
        "sliceSha256": hashlib.sha256(sl.encode("utf-8")).hexdigest(),
    }

    # ── A. 竞态取证 ────────────────────────────────────────────────────────
    cand_hash = sha256_file(CAND)
    declared = [ev for ev in rec.get("evidence", []) if ev.get("path", "").endswith("candidate.json")]
    ev_ok = all(sha256_file(ROOT / ev["path"]) == ev.get("sha256") for ev in rec.get("evidence", [])
                if (ROOT / ev["path"]).exists())
    ev_missing = [ev["path"] for ev in rec.get("evidence", []) if not (ROOT / ev["path"]).exists()]

    report["raceForensics"] = {
        "taskId": task["id"],
        "myAgent": lease.get("agent"),
        "myLeaseStartedAt": lease.get("startedAt"),
        "priorSubmission": {
            "recordPath": str(REC.relative_to(ROOT)),
            "agent": rec.get("agent"),
            "status": rec.get("status"),
            "submittedAt": rec.get("submittedAt"),
            "validationProblems": (rec.get("validation") or {}).get("problems"),
            "wallClockSeconds": rec.get("wallClockSeconds"),
            "candidateSha256Declared": (declared[0].get("sha256") if declared else None),
        },
        "candidateSha256Now": cand_hash,
        "candidateHashStillMatchesRecord": bool(declared) and declared[0].get("sha256") == cand_hash,
        "allEvidenceFilesPresent": not ev_missing,
        "missingEvidence": ev_missing,
        "allEvidenceHashesMatch": ev_ok,
        # 时序差：两个时间戳都是同一格式的 UTC（Z 结尾）字符串，直接按同一格式解析，
        # 不引入本地时区假设。解析不了就留 null 并写明，不估一个数字填上。
        "secondsBetweenPriorSubmitAndMyLease": _delta_seconds(
            rec.get("submittedAt"), lease.get("startedAt")),
        "note": ("两个时间戳都取自文件中的 UTC 字符串，按同一个格式 %Y-%m-%dT%H:%M:%SZ 解析相减；"
                 "解析失败则为 null"),
    }

    # 「覆写 writes 路径」的后果：纯内存推演，不落盘、不改共享产物
    report["overwriteHazard"] = {
        "writesPath": task["writes"][0],
        "isEvolving": False,
        "isTransient": False,
        "why": ("loop/state/out/ 是 MUTABLE_EXCEPTIONS（审阅产物）：被改写就是真问题。"
                "既有记录把该文件的 sha256 列为证据，覆写会让 evidence_stale() 报 "
                "hash-changed ⇒ validated()且不stale 不成立 ⇒ done_ids() 剔除该任务，"
                "一条**已通过机器校验**的产物被降级成『没做完』。"),
        "demonstratedInRecord": ("build/verify 脚本里用 copy.deepcopy 在内存中改哈希复现，"
                                 "实测 evidence_stale() 返回 [{'why': 'hash-changed'}]"),
    }

    # ── B1. 引文逐字复核（独立重算） ───────────────────────────────────────
    total = bad_literal = bad_range = bad_hash = no_offset = 0
    bad_samples = []
    for p, o in walk_quotes(cand):
        total += 1
        st, en, q = o.get("start"), o.get("end"), o["quote"]
        if o.get("sourceHash") != SRC_HASH:
            bad_hash += 1
        if not isinstance(st, int) or not isinstance(en, int):
            no_offset += 1
            bad_samples.append({"at": p, "why": "no-start/end"})
            continue
        if text[st:en] != q:
            bad_literal += 1
            bad_samples.append({"at": p, "why": "literal-mismatch", "quote": q[:40]})
        elif not (s <= st and en <= e):
            bad_range += 1
            bad_samples.append({"at": p, "why": "out-of-range", "start": st, "end": en})
    report["quoteAudit"] = {
        "quoteObjects": total,
        "badLiteral": bad_literal,
        "badRange": bad_range,
        "badSourceHash": bad_hash,
        "missingOffset": no_offset,
        "samples": bad_samples[:10],
        "ok": (bad_literal == bad_range == bad_hash == no_offset == 0),
    }

    # ── B2. 任务五栏：区间共用检测 + null 栏理由 ────────────────────────────
    FIELDS = ["objective", "obstacle", "action", "result", "cost"]
    shared, null_bad, null_total = [], [], 0
    for t in cand["tasks"]:
        ivs = []
        for f in FIELDS:
            v = t.get(f)
            if v is None:
                null_total += 1
                note = t.get(f + "Note")
                if not (isinstance(note, str) and note.strip()):
                    null_bad.append({"task": t.get("id"), "field": f})
                continue
            for q in (t.get(f + "Quotes") or []):
                ivs.append((f, q.get("start"), q.get("end")))
        for i in range(len(ivs)):
            for j in range(i + 1, len(ivs)):
                f1, s1, e1 = ivs[i]
                f2, s2, e2 = ivs[j]
                if s1 < e2 and s2 < e1:
                    shared.append({"task": t.get("id"), "a": f1, "b": f2})
    report["taskFieldIndependence"] = {
        "tasks": len(cand["tasks"]),
        "overlappingFieldPairs": len(shared),
        "samples": shared[:5],
        "nullFields": null_total,
        "nullFieldsWithoutNote": len(null_bad),
        "nullSamples": null_bad[:5],
        "ok": not shared and not null_bad,
    }

    # ── B3. worldSettings 三态字段合法性 ───────────────────────────────────
    wbad = []
    kinds = {"rule": 0, "place": 0, "item": 0}
    for w in cand.get("worldSettings", []):
        k = w.get("kind")
        kinds[k] = kinds.get(k, 0) + 1
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            wbad.append({"name": w.get("name"), "why": "placeState 非法", "v": w.get("placeState")})
        if k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                wbad.append({"name": w.get("name"), "why": "itemStates 非法", "v": st})
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            wbad.append({"name": w.get("name"), "why": "institution 非法", "v": w.get("institution")})
    report["worldSettingStates"] = {"kinds": kinds, "illegal": len(wbad), "samples": wbad[:5],
                                   "ok": not wbad}

    # ── B4. 反向检查：本区间原文事实里，候选**没有**覆盖的 ──────────────────
    # 做法：用我自己的段落切分（不读候选的 paras 字段），逐段看是否有任何引文落在段内。
    import re
    para_spans = []
    pos = s
    for line in sl.split("\n"):
        if line.strip():
            st = text.find(line, pos)
            para_spans.append((st, st + len(line), line.strip()))
            pos = st + len(line)
    covered = set()
    for p, o in walk_quotes(cand):
        st, en = o.get("start"), o.get("end")
        if isinstance(st, int) and isinstance(en, int):
            for i, (a, b, _) in enumerate(para_spans):
                if st < b and a < en:
                    covered.add(i)
    zero = [(i, para_spans[i][2][:60]) for i in range(len(para_spans)) if i not in covered]

    # 我自己读出来的、候选未覆盖的**具体事实**（逐条给原文子串，构建时现场 find 校验）
    reverse_facts = []
    for q, why in [
        ("他这是预防楚元缜接了一刀后，挥手反击，把他捅成刺猬",
         "已覆盖（对照项，确认反向清单不是空转）"),
        ("元景帝一直想与国师双修，来达到长生久视的愿望",
         "候选 WS04 已覆盖为 rule/misunderstood"),
        ("楚元缜一口茶喷了出来，喷到许七安脸上",
         "候选正文引文层未见：这是 P083 的**动作结果**（喷茶到脸上），"
         "与 P084 的追问是两个不同事实；候选 U 段未列"),
        ("你为什么会产生这样的猜测",
         "P084 的问句；候选未把它与 P083 组成『误解→喷茶』的因果"),
        ("女王成为国王之后，广纳后宫，将她的女儿们都召入自己的后宫里",
         "P087：人首鱼身种族的性别转化机制。候选只把它当人物见闻（U05），"
         "未登记为任何条目——按『没有依据不扩设定层』这是**可接受**的取舍，"
         "但它确实是本区间一个完整的原文事实"),
        ("许七安拍桌叫好",
         "P060：许七安对楚元缜辞官自述的**反应动作**；候选未立条目"),
        # 勘误（本轮自捕）：我第一版把这里写成「握住茶杯」，原文是「握着茶杯」——
        # 是本脚本自己的 foundInSlice 检查把它抓出来的（MISS @None）。
        # 我**没有**把探针改成"能命中"的近似串了事，而是照原文改正后重跑。
        ("楚元缜握着茶杯，一口都没喝，听的万分专注",
         "P097：听案时的状态细节；候选 S 段未收"),
        ("洛玉衡做了一个请的手势",
         "P036：候选 S07 的 after 层引到了这一步，属已覆盖"),
    ]:
        idx = sl.find(q)
        reverse_facts.append({
            "quote": q,
            "foundInSlice": idx >= 0,
            "absStart": (s + idx) if idx >= 0 else None,
            "assessment": why,
        })
    report["reverseCheck"] = {
        "paragraphs": len(para_spans),
        "paragraphsZeroCovered": len(zero),
        "zeroCoveredSamples": zero[:12],
        "factsProbed": len(reverse_facts),
        "factsNotFound": [f["quote"] for f in reverse_facts if not f["foundInSlice"]],
        "facts": reverse_facts,
        "note": ("反向检查只列**我确实在原文找到**的字符串；assessment 里区分"
                 "『候选已覆盖』与『候选按取舍未收』，不把后者一律判成遗漏。"),
    }

    # ── B5. 记录 vs 产物一致性 ─────────────────────────────────────────────
    report["recordConsistency"] = {
        "recordTaskMatches": rec.get("task") == task["id"],
        "recordAgent": rec.get("agent"),
        "recordStatus": rec.get("status"),
        "sectionKeysRequired": ["tasks", "causeEdges", "states", "foreshadows",
                                "worldSettings", "themeReadings"],
        "sectionKeysPresent": [k for k in ["tasks", "causeEdges", "states", "foreshadows",
                                           "worldSettings", "themeReadings"] if k in cand],
        "semanticReview": cand.get("semanticReview"),
        "semanticReviewClaimedDone": cand.get("semanticReview") == "performed",
        "counts": {k: len(cand.get(k) or []) for k in
                   ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
                    "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
                    "themeReadings", "textualNotes", "unknowns", "selfCritique"]},
    }

    report["ok"] = (report["quoteAudit"]["ok"] and report["taskFieldIndependence"]["ok"]
                    and report["worldSettingStates"]["ok"]
                    and report["recordConsistency"]["recordTaskMatches"]
                    and report["raceForensics"]["candidateHashStillMatchesRecord"])

    out = Path(__file__).with_name("audit_dupclaim_report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ["ok", "quoteAudit", "taskFieldIndependence", "worldSettingStates"]},
                     ensure_ascii=False, indent=2)[:1800])
    print("\n→", out)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
