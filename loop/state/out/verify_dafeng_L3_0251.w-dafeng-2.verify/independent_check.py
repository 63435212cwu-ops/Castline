#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立反向复核 read:dafeng:L3:0251 —— 复核者 w-dafeng-2 自写，**不 import**
候选作者的 build_candidate.py / verify_candidate.py，也不读其任何中间产物。
段落表、覆盖统计、区间重叠、内部指针、sentence-level 残差全部在本脚本内重新实现。

运行：python3 -B -s loop/state/out/verify_dafeng_L3_0251.w-dafeng-2.verify/independent_check.py
"""
import json, re, sys, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0251.candidate.json"
S, E = 1032194, 1038254
EXPECT_DOC_SHA = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
EXPECT_SLICE_SHA = "836bf4c1e3eddf236d4183694e4a0d73bdc8938dbf2bb8972919f8a11ad47535"

results = []
def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    return ok

doc = json.loads(SRC.read_text(encoding="utf-8"))
text = doc[0]["text"]
cand = json.loads(CAND.read_text(encoding="utf-8"))
sl = text[S:E]

# ── 1. 源身份 ────────────────────────────────────────────────────────────
doc_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
check("doc sha256 == task.sourceHash", doc_sha == EXPECT_DOC_SHA, doc_sha)
slice_sha = hashlib.sha256(sl.encode("utf-8")).hexdigest()
check("slice sha256 == candidate.sliceSha256", slice_sha == EXPECT_SLICE_SHA, slice_sha)
check("slice starts with unitHead", sl.startswith("第二十二章 真相"), repr(sl[:12]))
check("slice codepoints == task range length", len(sl) == E - S, "%d" % len(sl))

# ── 2. 段落表（自建：按 \n 切，记非空段的绝对起点）─────────────────────
paras = []          # [(abs_start, text)]
off = S
for line in sl.split("\n"):
    if line.strip():
        paras.append((off, line))
    off += len(line) + 1
check("non-empty paragraph count", len(paras) == 138, "%d" % len(paras))
by_start = {}
for i, (o, p) in enumerate(paras, 1):
    by_start[o] = (i, p)
def para_of(pos):
    for i, (o, p) in enumerate(paras, 1):
        if o <= pos < o + len(p):
            return i
    return None

# ── 3. 引文层：逐字 / 偏移 / 落区间 / 哈希 / 次数元数据 / 段号 ───────────
quotes = []
def walk(node, path=""):
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
            quotes.append((path, node))
            return
        for k, v in node.items():
            walk(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + "/" + str(i))
walk(cand)

mismatch = oob = badhash = cnt_err = para_err = first_err = 0
nonunique = []
for path, q in quotes:
    qs, qe, qt = q["start"], q["end"], q["quote"]
    if text[qs:qe] != qt:
        mismatch += 1
    if not (S <= qs and qe <= E):
        oob += 1
    if q.get("sourceHash") != EXPECT_DOC_SHA:
        badhash += 1
    if q.get("wholeTextOccurrences") is not None and q["wholeTextOccurrences"] != text.count(qt):
        cnt_err += 1
    if q.get("occurrencesInRange") is not None and q["occurrencesInRange"] != sl.count(qt):
        cnt_err += 1
    if q.get("declaredPara") is not None and para_of(qs) != q["declaredPara"]:
        para_err += 1
    if q.get("startIsFirstOccurrence") is not None:
        fi = text.find(qt)
        if q["startIsFirstOccurrence"] != (fi == qs) or q.get("firstOccurrenceAt") != fi:
            first_err += 1
    if text.count(qt) > 1:
        nonunique.append({"path": path, "n": text.count(qt), "declared": q.get("startIsFirstOccurrence") is False})

check("quote objects", len(quotes) == 278, "%d" % len(quotes))
check("t[start:end] == quote", mismatch == 0, "%d mismatch" % mismatch)
check("quotes inside task range", oob == 0, "%d out of range" % oob)
check("sourceHash uniform", badhash == 0, "%d bad" % badhash)
check("occurrence metadata (whole/in-range)", cnt_err == 0, "%d wrong" % cnt_err)
check("declaredPara vs my own table", para_err == 0, "%d wrong" % para_err)
check("startIsFirstOccurrence / firstOccurrenceAt", first_err == 0, "%d wrong" % first_err)
check("non-unique strings are self-declared", all(x["declared"] for x in nonunique), json.dumps(nonunique, ensure_ascii=False))

# ── 4. 五栏区间两两不相交（按字段名正确实现，确认判据实跑非空转）─────────
spans_collected = 0
overlaps = []
for tk in cand.get("tasks", []):
    fields = ["objectiveQuotes", "obstacleQuotes", "actionQuotes", "resultQuotes", "costQuotes"]
    per = {f: [(q["start"], q["end"]) for q in (tk.get(f) or [])] for f in fields}
    spans_collected += sum(len(v) for v in per.values())
    keys = [f for f in fields if per[f]]
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            for a in per[keys[i]]:
                for b in per[keys[j]]:
                    if a[0] < b[1] and b[0] < a[1]:
                        overlaps.append([tk["id"], keys[i], a, keys[j], b])
check("task five-field refs actually collected (judge not idle)", spans_collected > 0, "%d spans" % spans_collected)
check("task five-field intervals disjoint", not overlaps, json.dumps(overlaps, ensure_ascii=False))

# ── 5. 覆盖统计复算 ─────────────────────────────────────────────────────
cov = bytearray(E - S)
for _, q in quotes:
    for i in range(q["start"] - S, q["end"] - S):
        cov[i] = 1
union = sum(cov)
nonspace = sum(1 for ch in sl if not ch.isspace())
zero_paras = [i for i, (o, p) in enumerate(paras, 1) if not any(s < o + len(p) and o < e for s, e in
                                                                ((q["start"], q["end"]) for _, q in quotes))]
decl = (cand.get("coverage") or {})
check("union codepoints vs candidate claim", union == decl.get("quoteUnionCodepoints"), "%d vs %s" % (union, decl.get("quoteUnionCodepoints")))
check("non-space codepoints vs candidate claim", nonspace == decl.get("nonSpaceCodepoints"), "%d vs %s" % (nonspace, decl.get("nonSpaceCodepoints")))
check("ratio of slice reproduced", abs(union / (E - S) - decl.get("quoteUnionRatioOfSlice", -1)) < 5e-5, "%.4f" % (union / (E - S)))
check("ratio of non-space reproduced", abs(union / nonspace - decl.get("quoteUnionRatioOfNonSpace", -1)) < 5e-5, "%.4f" % (union / nonspace))
check("zero-covered paragraph list reproduced", zero_paras == decl.get("zeroCoveredParagraphs"), json.dumps(zero_paras))

# ── 6. sentence-level 残差（我的反向验证核心：段级覆盖 ≠ 句级覆盖）───────
sents = []
for line in re.split(r"(?<=[。！？])", sl):
    pass
# 用绝对偏移切句：以 。！？ 为界，累计到非空句
buf, start = "", None
for i, ch in enumerate(sl):
    if start is None and not ch.isspace() and ch != "\n":
        start = S + i
    if ch in "。！？":
        seg = sl[start - S:i + 1] if start else ""
        if start is not None:
            sents.append((start, S + i + 1, seg))
        start = None
    elif ch == "\n":
        if start is not None:
            seg = sl[start - S:i]
            if seg.strip():
                sents.append((start, S + i, seg))
        start = None
if start is not None:
    sents.append((start, E, sl[start - S:]))

zero_sents = []
for s0, s1, seg in sents:
    if len([c for c in seg if not c.isspace()]) < 12:
        continue
    if not any(s < s1 and s0 < e for _, q in quotes for s, e in [(q["start"], q["end"])]):
        zero_sents.append({"start": s0, "end": s1, "para": para_of(s0), "text": seg})
check("sentence-level zero-covered substantive sentences found", len(zero_sents) >= 3,
      "%d sentences" % len(zero_sents))

# ── 7. 内部 id 指针 ─────────────────────────────────────────────────────
raw = CAND.read_text(encoding="utf-8")
defined = set()
for key in ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
            "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
            "themeReadings", "textualNotes", "unknowns", "selfCritique", "speechAsClueNotFact"]:
    for x in cand.get(key, []) or []:
        if isinstance(x, dict) and x.get("id"):
            defined.add(x["id"])
refs = re.findall(r"见\s*([A-Z]{1,3}\d+)", raw)
dangling = sorted({r for r in refs if r not in defined})
zero_pad_mismatch = sorted({r for r in refs if r not in defined and re.fullmatch(r"[A-Z]\d", r) and (r[0] + "0" + r[1]) in defined})
check("internal id refs resolve as written", not dangling, "dangling=%s" % dangling)
check("single-digit refs that only resolve after zero-padding", not zero_pad_mismatch, "%s" % zero_pad_mismatch)

# ── 8. 实体扫描：候选提到的人名是否都在区间内 ────────────────────────────
names = ["许七安", "怀庆", "皇后", "国舅", "元景帝", "黄小柔", "魏渊", "上官青", "荷儿",
         "福妃", "太子", "四皇子", "小宦官", "长公主", "上官", "教坊司", "御药房",
         "凤栖宫", "东宫", "冰窖", "打更人", "望气术"]
absent = [n for n in names if n in raw and sl.count(n) == 0]
check("no entity mentioned by candidate is absent from slice", not absent, "%s" % absent)

# ── 9. 引文层之外：候选文件自身的形态缺陷 ──────────────────────────────
check("selfCritiqueNote literal %d placeholder", raw.count("%d 条自评") == 0,
      "count=%d" % raw.count("%d 条自评"))

# ── 输出 ────────────────────────────────────────────────────────────────
out = {
    "sourceFileSha256": doc_sha,
    "candidateSha256": hashlib.sha256(CAND.read_bytes()).hexdigest(),
    "sliceSha256": slice_sha,
    "sliceCodepoints": len(sl),
    "nonEmptyParagraphs": len(paras),
    "quoteObjects": len(quotes),
    "quoteLayer": {"sliceMismatch": mismatch, "outOfRange": oob, "hashMismatch": badhash,
                   "occurrenceMetadataErrors": cnt_err, "declaredParaMismatch": para_err,
                   "firstOccurrenceErrors": first_err, "nonUnique": nonunique},
    "taskFieldSpansCollected": spans_collected,
    "taskFieldIntervalOverlap": len(overlaps),
    "coverage": {"unionCodepoints": union, "nonSpaceCodepoints": nonspace,
                 "ratioSlice": round(union / (E - S), 4), "ratioNonSpace": round(union / nonspace, 4),
                 "zeroCoveredParagraphs": zero_paras},
    "sentenceLevelZeroCovered": {"count": len(zero_sents), "items": zero_sents},
    "idRefs": {"defined": sorted(defined), "referenced": sorted(set(refs)),
               "dangling": dangling, "singleDigitUnresolved": zero_pad_mismatch},
    "entityAbsentFromSlice": absent,
    "checks": results,
    "failed": [r for r in results if not r["ok"]],
    "ok": all(r["ok"] for r in results),
}
outp = Path(__file__).resolve().parent / "independent-check-output.json"
outp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("独立复算：%d 条判据" % len(results))
print("通过 %d / %d" % (sum(1 for r in results if r["ok"]), len(results)))
for r in results:
    print(("  PASS " if r["ok"] else "  FAIL ") + r["name"] + ("  " + r["detail"] if r["detail"] else ""))
print()
print("sentence-level 完全未引的实质句：%d" % len(zero_sents))
for s in zero_sents:
    print("  [P%03d %d-%d] %s" % (s["para"], s["start"], s["end"], s["text"][:64]))
print()
print("输出：%s" % outp)
sys.exit(0 if out["ok"] else 1)
