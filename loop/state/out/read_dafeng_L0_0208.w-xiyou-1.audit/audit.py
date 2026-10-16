# -*- coding: utf-8 -*-
"""w-xiyou-1 独立机械复核 + 重复派发取证（**只读他人产物，只写本目录**）。

背景：本轮任务 read:dafeng:L0:0208 在领取前 16 秒已被 w-xiyou-0 完成并通过校验
（loop/state/out/read_dafeng_L0_0208.json，submittedAt 2026-10-14T19:42:14Z）。
本脚本不覆盖 loop/state/out/read_dafeng_L0_0208.candidate.json 的任何字节，
只对**现存**候选做独立复算，并记录可复现的调度根因证据。

自纠错留痕（重要，避免把尺子的错记成产物的错）：
  v1 版脚本用「全部分区 + 全部节点」统计覆盖，得 touched=81 / zero=68，
  并据此判候选 coverage 自述（79/70）「不一致」。复算候选的实际口径后确认
  **是 v1 的规则错**：候选口径 = 全部节点，但排除 worldSettings[].itemStateQuotes
  （itemStates 的四态分列引用不计入段落覆盖）。按该口径复算 = touched 79 / zero 70，
  与候选自述**逐位一致**（79+70=149）。v1 的结论已作废，不写入缺陷清单。
"""
import json, hashlib, os, re, sys, time, subprocess

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0208.candidate.json")
REC = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0208.json")
START, END = 769296, 775009
TASK_SHA = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

raw = open(DOCS, "rb").read()
file_sha = hashlib.sha256(raw).hexdigest()
TEXT = json.loads(raw)[0]["text"]
cand = json.load(open(CAND, encoding="utf-8"))
cand_sha = hashlib.sha256(open(CAND, "rb").read()).hexdigest()

out = {"auditBy": "w-xiyou-1", "role": "READER", "task": "read:dafeng:L0:0208",
       "targetCandidate": CAND, "targetCandidateSha256": cand_sha,
       "docsSha256": file_sha, "docsSha256MatchesTaskSourceHash": file_sha == TASK_SHA,
       "sliceCodepoints": len(TEXT[START:END]), "unitHeadFromSlice": TEXT[START:END][:32],
       "sliceSha256": hashlib.sha256(TEXT[START:END].encode()).hexdigest()}

# ---- A. 引文逐字 / 偏移 / 哈希全量复算 ----
refs = []
def walk(n, p):
    if isinstance(n, dict):
        if isinstance(n.get("quote"), str) and n.get("start") is not None:
            refs.append((p, n))
        for k, v in n.items():
            walk(v, p + "." + k)
    elif isinstance(n, list):
        for i, v in enumerate(n):
            walk(v, "%s[%d]" % (p, i))
walk(cand, "$")

A = {"quoteNodes": len(refs), "sliceExact": 0, "sliceMismatch": [], "findNeStart": [],
     "outOfRange": [], "sourceHashMismatch": [], "notUniqueInSlice": [],
     "notUniqueInFullText": []}
for p, n in refs:
    q, s, e = n["quote"], n["start"], n["end"]
    if TEXT[s:e] == q:
        A["sliceExact"] += 1
    else:
        A["sliceMismatch"].append({"path": p, "head": q[:40]})
    if TEXT.find(q) != s:
        A["findNeStart"].append({"path": p, "head": q[:40], "find": TEXT.find(q), "start": s})
    if not (START <= s < END and START < e <= END):
        A["outOfRange"].append({"path": p, "start": s, "end": e})
    if n.get("sourceHash") and n["sourceHash"] != file_sha:
        A["sourceHashMismatch"].append({"path": p})
    if TEXT[START:END].count(q) != 1:
        A["notUniqueInSlice"].append({"path": p, "head": q[:40]})
    if TEXT.count(q) != 1:
        A["notUniqueInFullText"].append({"path": p, "head": q[:40], "occurrences": TEXT.count(q)})
out["A_citation"] = A
out["A_note_fullTextNonUnique"] = (
    "notUniqueInFullText 不是缺陷：任务判据是 docs[0].text[start:end]==quote 且落在本单元内，"
    "候选自述的口径是「切片内唯一」——切片内实测均唯一。跨全书重复（如「影梅小阁。」全书 10 次）"
    "只说明该串短，不是引文错误。")

# ---- B. 同一任务五栏共用引文（提示词点名的旧图谱缺陷）----
FIELDS = ("objective", "obstacle", "action", "result", "cost")
reuse, cross = [], []
for i, t in enumerate(cand.get("tasks") or []):
    seen = {}
    for f in FIELDS:
        v = t.get(f)
        if not isinstance(v, dict):
            continue
        for q in (v.get("quotes") or []):
            seen.setdefault((q.get("start"), q.get("end")), []).append(f)
    for sp, fs in seen.items():
        if len(fs) > 1:
            reuse.append({"taskIndex": i, "span": sp, "fields": fs})
out["B_fiveFieldReuse_exactSpan"] = reuse
out["B_fiveFieldReuseCount"] = len(reuse)

# ---- C. 裸 null 栏位是否都带同名 <栏位>Note ----
nulls = []
for i, t in enumerate(cand.get("tasks") or []):
    for f in FIELDS:
        if t.get(f) is None:
            note = t.get(f + "Note")
            nulls.append({"taskIndex": i, "field": f, "hasNote": bool(note and str(note).strip())})
out["C_nullFields"] = nulls
out["C_nullFieldsMissingNote"] = [n for n in nulls if not n["hasNote"]]

# ---- D. 覆盖口径复算（含 v1 自纠错）----
paras = [m for m in re.finditer(r"[^\n]+", TEXT[START:END]) if m.group().strip()]
def collect(skip):
    acc = []
    def w(n):
        if isinstance(n, dict):
            if isinstance(n.get("quote"), str) and n.get("start") is not None:
                acc.append((n["start"], n["end"]))
            for k, v in n.items():
                if k in skip:
                    continue
                w(v)
        elif isinstance(n, list):
            for v in n:
                w(v)
    w(cand)
    return sorted(set(acc))
def zero_of(sp):
    return sorted(i for i, m in enumerate(paras)
                  if not any(s < START + m.end() and START + m.start() < e for s, e in sp))
cov = cand.get("coverage") or {}
v1 = zero_of(collect(()))
v2 = zero_of(collect(("itemStateQuotes",)))
out["D_coverage"] = {
    "candidateClaim": {"touched": cov.get("paragraphsTouchedByQuotes"),
                       "zero": cov.get("zeroCoverageParagraphs"),
                       "nonEmpty": cov.get("nonEmptyParagraphs")},
    "v1_rule_allNodes": {"zero": len(v1), "matchesCandidate": (len(v1) == cov.get("zeroCoverageParagraphs"))},
    "v2_rule_exclude_itemStateQuotes": {"zero": len(v2), "touched": len(paras) - len(v2),
                                        "touchedMatchesCandidate": (len(paras) - len(v2)) == cov.get("paragraphsTouchedByQuotes"),
                                        "zeroMatchesCandidate": len(v2) == cov.get("zeroCoverageParagraphs"),
                                        "first40EqualsCandidateList": v2[:40] == cov.get("zeroCoverageList")},
    "v1_conclusion": "作废：v1 的 81/68 是**我的规则错**，不是候选的缺陷。候选口径自洽（79+70=149）。",
    "nonEmptyParagraphsRecomputed": len(paras),
    "zeroCoverageListTruncatedInCandidate": cov.get("zeroCoverageListTruncated"),
}
out["D_zeroCoverageAll_independent"] = v2

# ---- E. 分区齐备 ----
need = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
out["E_sections"] = {k: (k in cand) for k in need}
out["E_sectionSizes"] = {k: (len(cand[k]) if isinstance(cand.get(k), list) else None) for k in need}
out["E_semanticReviewField"] = cand.get("semanticReview")

# ---- F. 现存记录的校验态（决定本轮该不该写盘）----
rec = json.load(open(REC, encoding="utf-8"))
ev = []
for item in rec.get("evidence") or []:
    p = item["path"]
    ap = p if os.path.isabs(p) else os.path.join(ROOT, p)
    ok = os.path.exists(ap)
    h = hashlib.sha256(open(ap, "rb").read()).hexdigest() if ok else None
    ev.append({"path": p, "exists": ok, "declared": (item.get("sha256") or "")[:16],
               "actual": (h or "")[:16], "match": h == item.get("sha256")})
out["F_existingRecord"] = {
    "recordAgent": rec.get("agent"), "status": rec.get("status"),
    "submittedAt": rec.get("submittedAt"), "wallClockSeconds": rec.get("wallClockSeconds"),
    "validationProblems": (rec.get("validation") or {}).get("problems"),
    "verifyState": rec.get("verifyState"), "evidence": ev,
    "allEvidenceHashesMatch": all(e["match"] for e in ev),
}
print(json.dumps(out, ensure_ascii=False, indent=1))
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_result.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
