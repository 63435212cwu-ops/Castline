#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核 read:sanguo:L0:0112 既有候选（w-read-3 的产物）。

独立性声明：本脚本**不 import** 产出方的构建/自检脚本（build_0112.py、
verify_0112.py），也不读它们的 content_*.json；只读两个输入，其余全部在本脚本内重算：
  1. loop/state/out/read_sanguo_L0_0112.candidate.json   —— 被审对象
  2. data/cache/fe42d01f3826fe8096f86614.docs.json       —— 原文（docs[0].text）

覆盖范围：**定位层与结构层**（机器可复算）。
  A. 每个引文对象：text[start:end]==quote、区间 ⊆ 切片、sourceHash、长度一致、
     并用 text.find(quote, start) 做**反向**验证（不只信自报偏移）、
     globalOccurrences == text.count(quote)。
  B. 任务五栏「不许同一句话当多栏依据」：按**精确区间**与**句读单元**
     （。！？；\n 切分）两种口径分别判，两种都报。
  C. null 栏是否带同名 <栏>Note 且理由非空、非字段名占位符。
  D. worldSettings 三态字段取值合法性（placeState / itemStates / institution），
     另加一条**启发式探针**：placeState=arrived 但引文里没有任何到达/驻守动词的条目
     —— 该探针只产出**待人工裁决队列**，不自行判缺陷（命中≠错误）。
  E. themeReadings 三要素（perspective / support / counter）齐不齐。
  F. 反向覆盖率：逐自然段是否有引文落点；切片内出现的人名是否至少被建模一次。
  G. 自报计数（candidate.counts）与独立重算是否一致；basis 取值是否合法。

**本脚本不裁决语义** —— 引文定位正确 ≠ 语义已核验。B/D 的启发式命中项与
「某栏引这句话是否真的支持该栏」都属语义判断，须由 read-verify 通道换 agent 复核。

用法： python3 -B audit_0112.py
输出： audit_0112_report.json （同目录）
"""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                      # loop/state/out/<dir> -> 仓库根
CAND = ROOT / "loop/state/out/read_sanguo_L0_0112.candidate.json"
DOCS = ROOT / "data/cache/fe42d01f3826fe8096f86614.docs.json"
OUTP = HERE / "audit_0112_report.json"

SLICE_START, SLICE_END = 569822, 574413
DECLARED_SOURCE_HASH = "8ab7298a6960c6fec50e26338092abf2693e2cb39f1547f1a99ee2701ef29ec2"
COLUMNS = ("objective", "obstacle", "action", "result", "cost")
LEGAL_BASIS = {"explicit", "inferred", "derived", "unverified"}
PLACE_STATES = {"arrived", "mentioned"}
ITEM_STATES = {"hold", "transfer", "use", "lose"}
INSTITUTIONS = {"declared", "executed", "misunderstood"}
# 到达/驻守语义的文言标记（只用于把条目排进人工裁决队列，不用于判缺陷）
ARRIVAL_MARKERS = ("入", "至", "到", "屯", "驻", "守", "宿卫", "下寨", "进兵",
                   "回", "退", "奔", "来", "往", "拔", "围", "据", "夺", "取")


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def walk_quotes(obj, trail, out):
    """递归收集所有引文对象（含 quote/start/end 三键的 dict）。"""
    if isinstance(obj, dict):
        if "quote" in obj and "start" in obj and "end" in obj:
            out.append((trail, obj))
        for k, v in obj.items():
            walk_quotes(v, trail + "/" + str(k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_quotes(v, trail + "[%d]" % i, out)


def collect_basis(obj, trail, out):
    """收集所有 basis 字段的取值与出处。"""
    if isinstance(obj, dict):
        if "basis" in obj and isinstance(obj["basis"], str):
            out.append((trail + "/basis", obj["basis"]))
        for k, v in obj.items():
            collect_basis(v, trail + "/" + str(k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            collect_basis(v, trail + "[%d]" % i, out)


def build_units(sl):
    """把切片切成**自然句**：以 。！？ 与换行为界，并把随后的收尾引号/括号
    吸进同一句。

    ⚠ 本函数的第一版是错的，值得记下来：它把 `；` 也当边界、且不吸收收尾引号，
    于是句末的 `”` 会**单独成为一个「句子」**。那个孤立的 `”` 会与相邻句的引文
    区间相交，产出 16 条「同句跨栏」假阳性 —— 而真相是那 16 对的**字符区间相交为 0**，
    共享的只是句末标点。判据错在「把标点当内容」。修正后重算：
    精确区间重叠 0、自然句共享 0，与被审候选自报的 0 一致。
    这正是 MF05 形态（探针错、被审对象没错），故保留此注。
    """
    ends, start = [], 0
    for m in re.finditer(r"[。！？\n]", sl):
        end = m.end()
        while end < len(sl) and sl[end] in "”』」）)":
            end += 1
        ends.append(end)
    units = []
    for b in ends:
        if b > start:
            units.append((start, b))
            start = b
    if start < len(sl):
        units.append((start, len(sl)))
    return units


def units_covered(units, a, b):
    """[a,b)（切片相对偏移）覆盖到的自然句下标集合。"""
    return {i for i, (us, ue) in enumerate(units) if us < b and ue > a}


def main():
    rep = {"auditor": "w-dafeng-0",
           "kind": "independent audit of an already-submitted candidate (dupclaim)",
           "reproduce": "python3 -B -s loop/state/out/read_sanguo_L0_0112.w-dafeng-0.dupclaim/audit_0112.py"}

    cand_sha = sha256_file(CAND)
    docs_sha = sha256_file(DOCS)
    cand = json.loads(CAND.read_text(encoding="utf-8"))
    text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    sl = text[SLICE_START:SLICE_END]

    rep["inputs"] = {
        "candidate": str(CAND.relative_to(ROOT)),
        "candidateSha256": cand_sha,
        "docsJson": str(DOCS.relative_to(ROOT)),
        "docsSha256": docs_sha,
        "declaredSourceHashMatchesFile": docs_sha == DECLARED_SOURCE_HASH,
        "sliceStart": SLICE_START, "sliceEnd": SLICE_END, "sliceLen": len(sl),
        "sliceSha256": hashlib.sha256(sl.encode("utf-8")).hexdigest(),
        "sliceHead": sl[:24],
        "independence": "未 import 产出方构建/自检脚本；仅读候选 JSON 与原文 docs[0].text",
    }

    # ── A. 引文定位完整性 ────────────────────────────────────────────────
    quotes = []
    walk_quotes(cand, "", quotes)
    bad_eq, bad_range, bad_hash, bad_len, bad_find, bad_occ = [], [], [], [], [], []
    for trail, q in quotes:
        s, e = q.get("start"), q.get("end")
        if not isinstance(s, int) or not isinstance(e, int):
            bad_range.append({"at": trail, "why": "start/end 非整数", "start": s, "end": e})
            continue
        if text[s:e] != q["quote"]:
            bad_eq.append({"at": trail, "start": s, "end": e,
                           "quote": q["quote"][:40], "actual": text[s:e][:40]})
        if not (SLICE_START <= s < e <= SLICE_END):
            bad_range.append({"at": trail, "start": s, "end": e})
        if q.get("sourceHash") != DECLARED_SOURCE_HASH:
            bad_hash.append({"at": trail, "sourceHash": q.get("sourceHash")})
        if e - s != len(q["quote"]):
            bad_len.append({"at": trail, "start": s, "end": e, "lenQuote": len(q["quote"])})
        if text.find(q["quote"], s) != s:
            bad_find.append({"at": trail, "start": s, "findAt": text.find(q["quote"], s)})
        if q.get("globalOccurrences") is not None:
            if text.count(q["quote"]) != q["globalOccurrences"]:
                bad_occ.append({"at": trail, "declared": q["globalOccurrences"],
                                "actual": text.count(q["quote"])})
    rep["A_quoteIntegrity"] = {
        "quoteObjects": len(quotes),
        "textSliceEqualsQuote": len(quotes) - len(bad_eq),
        "badEquality": bad_eq[:20], "badEqualityCount": len(bad_eq),
        "badRange": bad_range[:20], "badRangeCount": len(bad_range),
        "badSourceHash": bad_hash[:20], "badSourceHashCount": len(bad_hash),
        "badLength": bad_len[:20], "badLengthCount": len(bad_len),
        "badReverseFind": bad_find[:20], "badReverseFindCount": len(bad_find),
        "badGlobalOccurrences": bad_occ[:20], "badGlobalOccurrencesCount": len(bad_occ),
        "allEqual": not (bad_eq or bad_range or bad_hash or bad_len or bad_find or bad_occ),
    }

    # ── B. 五栏独立性：同句跨栏 ──────────────────────────────────────────
    units = build_units(sl)
    b_overlap, b_unitshare, b_cols = [], [], []
    for t in cand.get("tasks", []):
        per = {}
        for col in COLUMNS:
            cell = t.get(col)
            if not isinstance(cell, dict):
                continue
            ivs = []
            for q in cell.get("quotes") or []:
                s, e = q.get("start"), q.get("end")
                if isinstance(s, int) and isinstance(e, int):
                    ivs.append((s, e, q.get("quote", "")[:24], s - SLICE_START, e - SLICE_START))
            per[col] = ivs
        cols = [c for c in COLUMNS if per.get(c)]
        b_cols.append({"task": t.get("id"), "columnsWithQuotes": len(cols)})
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                ca, cb = cols[i], cols[j]
                for (s1, e1, q1, r1, r2) in per[ca]:
                    for (s2, e2, q2, t1, t2) in per[cb]:
                        if s1 < e2 and s2 < e1:
                            b_overlap.append({"task": t.get("id"), "colA": ca, "colB": cb,
                                              "intervalA": [s1, e1], "intervalB": [s2, e2],
                                              "quoteA": q1, "quoteB": q2})
                        ua = units_covered(units, r1, r2)
                        ub = units_covered(units, t1, t2)
                        if ua & ub:
                            b_unitshare.append({"task": t.get("id"), "colA": ca, "colB": cb,
                                                "sharedUnits": sorted(ua & ub),
                                                "quoteA": q1, "quoteB": q2})
    rep["B_columnIndependence"] = {
        "tasks": len(cand.get("tasks", [])),
        "exactIntervalOverlaps": b_overlap, "exactIntervalOverlapCount": len(b_overlap),
        "sharedSentenceUnits": b_unitshare, "sharedSentenceUnitCount": len(b_unitshare),
        "perTaskColumnsWithQuotes": b_cols,
        "ok": not b_overlap and not b_unitshare,
        "note": "两种口径都判：精确区间重叠（严）与句读单元共享（宽）。任一非空即违反提示词的「禁止同句跨栏」。",
    }

    # ── C. null 栏必须带同名 Note 且理由非空 ─────────────────────────────
    nulls, bad_notes = [], []
    for t in cand.get("tasks", []):
        for col in COLUMNS:
            if t.get(col) is None:
                nk = col + "Note"
                note = t.get(nk)
                nulls.append({"task": t.get("id"), "column": col})
                if not isinstance(note, str) or len(note.strip()) < 8:
                    bad_notes.append({"task": t.get("id"), "column": col, "note": note})
                elif note.strip().rstrip("：:") == nk:
                    bad_notes.append({"task": t.get("id"), "column": col,
                                      "note": note, "why": "只有字段名占位"})
    rep["C_nullColumns"] = {
        "count": len(nulls), "items": nulls,
        "notesMissingOrPlaceholder": bad_notes, "notesMissingOrPlaceholderCount": len(bad_notes),
        "ok": not bad_notes,
        "note": "「不写理由的 null」与「已确认无」不是一回事 —— 提示词明令 null 必须带同名 Note。",
    }

    # ── D. worldSettings 三态字段 ────────────────────────────────────────
    ws = cand.get("worldSettings", [])
    viol, probes = [], []
    kinds = {}
    for w in ws:
        k = w.get("kind")
        kinds[k] = kinds.get(k, 0) + 1
        if k == "place":
            if w.get("placeState") not in PLACE_STATES:
                viol.append({"id": w.get("id"), "why": "placeState 非法", "v": w.get("placeState")})
            if w.get("placeState") == "arrived":
                q = (w.get("quoteRef") or {}).get("quote", "")
                if not any(mk in q for mk in ARRIVAL_MARKERS):
                    probes.append({"id": w.get("id"), "name": w.get("name"),
                                   "quote": q[:48],
                                   "why": "启发式：arrived 但引文无到达/驻守动词，需人工裁决"})
        elif k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or not set(st) <= ITEM_STATES:
                viol.append({"id": w.get("id"), "why": "itemStates 非法", "v": st})
        elif k == "rule":
            if w.get("institution") not in INSTITUTIONS:
                viol.append({"id": w.get("id"), "why": "institution 非法", "v": w.get("institution")})
        else:
            viol.append({"id": w.get("id"), "why": "kind 非法", "v": k})
    rep["D_worldSettings"] = {
        "count": len(ws), "kinds": kinds,
        "violations": viol, "violationCount": len(viol),
        "arrivedHeuristicProbes": probes, "arrivedHeuristicProbeCount": len(probes),
        "ok": not viol,
        "probeCaveat": "probes 只是**待人工裁决队列**：句子可以不含标记词仍真是到达（如以官职任命表驻守），命中不等于缺陷。",
    }

    # ── E. themeReadings 三要素 ──────────────────────────────────────────
    tr_bad = []
    for tr in cand.get("themeReadings", []):
        miss = [k for k in ("perspective", "support", "counter") if not tr.get(k)]
        if miss:
            tr_bad.append({"id": tr.get("id"), "missing": miss})
    rep["E_themeReadings"] = {
        "count": len(cand.get("themeReadings", [])),
        "missing": tr_bad, "missingCount": len(tr_bad), "ok": not tr_bad,
        "note": "提示词：只列支持的那叫论证不叫解释 —— counter 缺失即不合格。",
    }

    # ── F. 反向覆盖率 ────────────────────────────────────────────────────
    covered = [False] * len(sl)
    for _, q in quotes:
        s, e = q.get("start"), q.get("end")
        if isinstance(s, int) and isinstance(e, int):
            for i in range(max(0, s - SLICE_START), min(len(sl), e - SLICE_START)):
                covered[i] = True
    paras, pstart = [], 0
    for m in re.finditer(r"\n", sl):
        paras.append((pstart, m.end()))
        pstart = m.end()
    if pstart < len(sl):
        paras.append((pstart, len(sl)))
    zero = [{"paraIndex": i, "start": SLICE_START + a, "end": SLICE_START + b,
             "head": sl[a:b][:32]}
            for i, (a, b) in enumerate(paras)
            if not any(covered[a:b])]
    longest, run, best = 0, 0, 0
    for c in covered:
        run = 0 if c else run + 1
        best = max(best, run)
    longest = best
    rep["F_reverseCoverage"] = {
        "sliceCodepoints": len(sl),
        "coveredCodepoints": sum(covered),
        "codepointCoverage": round(sum(covered) / len(sl), 4),
        "longestUncoveredRun": longest,
        "paragraphs": len(paras),
        "zeroCoveredParagraphs": zero, "zeroCoveredCount": len(zero),
        "coverageIsNotCorrectness": "逐码点覆盖只说明「有引文落点」，不说明引文用对了地方。",
    }

    # ── G. 自报计数 / basis 合法性 ───────────────────────────────────────
    basis_vals = []
    collect_basis(cand, "", basis_vals)
    illegal = [(t, v) for t, v in basis_vals if v not in LEGAL_BASIS]
    recomputed = {
        "tasks": len(cand.get("tasks", [])),
        "causeEdges": len(cand.get("causeEdges", [])),
        "states": len(cand.get("states", [])),
        "foreshadows": len(cand.get("foreshadows", [])),
        "worldSettings": len(ws),
        "themeReadings": len(cand.get("themeReadings", [])),
        "quoteObjects": len(quotes),
        "nullColumns": len(nulls),
    }
    declared = cand.get("counts", {}) or {}
    mism = {k: {"declared": declared.get(k), "recomputed": v}
            for k, v in recomputed.items()
            if k in declared and declared.get(k) != v}
    rep["G_countsAndBasis"] = {
        "recomputed": recomputed, "declared": declared,
        "declaredMismatches": mism, "declaredMismatchCount": len(mism),
        "basisValuesUsed": sorted({v for _, v in basis_vals}),
        "illegalBasis": illegal[:20], "illegalBasisCount": len(illegal),
        "ok": not mism and not illegal,
    }

    # ── H. causeEdges / states / foreshadows 结构 ────────────────────────
    ce_bad, trig_bad = [], []
    for ce in cand.get("causeEdges", []):
        miss = [k for k in ("frm", "to", "trigger", "mechanism") if not ce.get(k)]
        if miss:
            ce_bad.append({"id": ce.get("id"), "missing": miss})
        tg = ce.get("trigger")
        if isinstance(tg, str) and tg and tg not in text:
            trig_bad.append({"id": ce.get("id"), "trigger": tg[:40]})
    st_bad = [{"id": s.get("id"), "missing": [k for k in ("before", "after", "anchor") if not s.get(k)]}
              for s in cand.get("states", [])
              if [k for k in ("before", "after", "anchor") if not s.get(k)]]
    fs_bad = []
    for f in cand.get("foreshadows", []):
        miss = [k for k in ("setup", "payoff") if not f.get(k)]
        if miss:
            fs_bad.append({"id": f.get("id"), "missing": miss})
        if f.get("resolved") is False and not f.get("unresolvedNote"):
            fs_bad.append({"id": f.get("id"), "why": "未回收但缺 unresolvedNote"})
    rep["H_structures"] = {
        "causeEdgesMissingCore": ce_bad, "causeEdgesMissingCoreCount": len(ce_bad),
        "causeEdgesTriggerNotInText": trig_bad, "causeEdgesTriggerNotInTextCount": len(trig_bad),
        "statesMissingCore": st_bad, "statesMissingCoreCount": len(st_bad),
        "foreshadowsMissingCore": fs_bad, "foreshadowsMissingCoreCount": len(fs_bad),
        "ok": not (ce_bad or trig_bad or st_bad or fs_bad),
    }

    # ── I. 散文层自检（MF01 / MF02）──────────────────────────────────────
    # I1: 未替换的 printf 占位符 —— 机器校验（B1–B16）只查引文对象，查不出这个。
    conv = cand.get("quotationConvention", {}) or {}
    placeholder_hits = []

    def scan_placeholders(o, trail):
        if isinstance(o, dict):
            for k, v in o.items():
                scan_placeholders(v, trail + "/" + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                scan_placeholders(v, trail + "[%d]" % i)
        elif isinstance(o, str) and re.search(r"%[dsrf]\b", o):
            placeholder_hits.append({"at": trail, "text": o[:120]})

    scan_placeholders(conv, "/quotationConvention")

    # I2: 粗口径「散文定义 vs 代码实现」对照。
    # 产出方 columnRuleSensitivity.coarseRuleDefinition 声称「不切引语边界」，
    # 但它实际调用的 units_of(text, False) 在 “ 与 ” 处**无条件**切边界。
    # 两种解释都算一遍，让复核者看到口径差多少。
    def units_impl(text, cut_inside_quotes):
        """产出方 units_of() 的逐行照抄（build_0112.py:130-151）。"""
        marks, in_q = [], False
        for i, ch in enumerate(text):
            if ch == "“":
                marks.append(i); in_q = True
            elif ch == "”":
                marks.append(i + 1); in_q = False
            elif ch == "\n":
                marks.append(i)
            elif ch in "。！？" and (cut_inside_quotes or not in_q):
                marks.append(i + 1)
        b = sorted(set([0] + marks + [len(text)]))
        return [(b[i], b[i + 1]) for i in range(len(b) - 1) if b[i] < b[i + 1]]

    def units_written_def(text):
        """按其**散文定义**实现：只在引号外的句末标点与换行处切，不切引语边界。"""
        marks, in_q = [], False
        for i, ch in enumerate(text):
            if ch == "“":
                in_q = True
            elif ch == "”":
                in_q = False
            elif ch == "\n":
                marks.append(i)
            elif ch in "。！？" and not in_q:
                marks.append(i + 1)
        b = sorted(set([0] + marks + [len(text)]))
        return [(b[i], b[i + 1]) for i in range(len(b) - 1) if b[i] < b[i + 1]]

    def collision_set(U):
        def hit(sp):
            return [u for u in U if not (sp[1] <= u[0] or sp[0] >= u[1])]
        found = set()
        for t in cand.get("tasks", []):
            per = {}
            for col in COLUMNS:
                cell = t.get(col)
                if isinstance(cell, dict):
                    u = set()
                    for q in cell.get("quotes") or []:
                        u |= set(hit((q["start"] - SLICE_START, q["end"] - SLICE_START)))
                    per[col] = u
            cols = [k for k in per if per[k]]
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    for u in per[cols[i]] & per[cols[j]]:
                        found.add((t.get("id"), cols[i], cols[j], u))
        return found

    U_code = units_impl(sl, False)
    U_doc = units_written_def(sl)
    col_code, col_doc = collision_set(U_code), collision_set(U_doc)
    declared_count = ((conv.get("columnRuleSensitivity") or {})
                      .get("coarseRuleCollisionCount"))
    rep["I_proseLayer"] = {
        "I1_unsubstitutedPlaceholders": {
            "hits": placeholder_hits, "count": len(placeholder_hits),
            "scope": "只扫 quotationConvention 子树（散文层）。引文对象里不应出现占位符。",
            "note": "命中即缺陷：读者会看到一个未被替换的 %d。",
        },
        "I2_coarseRuleDefinitionVsImpl": {
            "asImplemented_cutInsideQuotesFalse_units": len(U_code),
            "asImplemented_distinctCollisions": len(col_code),
            "asWrittenDef_noQuoteBoundaryCuts_units": len(U_doc),
            "asWrittenDef_distinctCollisions": len(col_doc),
            "declaredCoarseRuleCollisionCount": declared_count,
            "matchesImplementation": declared_count == len(col_code),
            "matchesWrittenDefinition": declared_count == len(col_doc),
            "verdict": ("definition-vs-implementation split：declared 与**代码**一致、与**散文定义**不一致"
                        if declared_count == len(col_code) != len(col_doc) else "一致或另有情形"),
            "sampleCollisionsUnderWrittenDef": [
                {"task": a, "columns": [b, c], "sliceRange": [u[0], u[1]],
                 "globalRange": [u[0] + SLICE_START, u[1] + SLICE_START],
                 "fragment": sl[u[0]:u[1]][:100]}
                for (a, b, c, u) in sorted(col_doc)[:10]
            ],
        },
    }

    # ── 总结（**只覆盖定位/结构层**）──────────────────────────────────────
    hard = []
    if not rep["A_quoteIntegrity"]["allEqual"]:
        hard.append("A 引文定位层有可复现缺陷")
    if not rep["B_columnIndependence"]["ok"]:
        hard.append("B 存在同句跨栏")
    if not rep["C_nullColumns"]["ok"]:
        hard.append("C null 栏缺理由")
    if not rep["D_worldSettings"]["ok"]:
        hard.append("D worldSettings 三态字段非法")
    if not rep["E_themeReadings"]["ok"]:
        hard.append("E themeReadings 三要素不全")
    if not rep["G_countsAndBasis"]["ok"]:
        hard.append("G 自报计数不符或 basis 非法")
    if not rep["H_structures"]["ok"]:
        hard.append("H 结构缺核心字段")
    prose = rep["I_proseLayer"]
    if prose["I1_unsubstitutedPlaceholders"]["count"]:
        hard.append("I1 散文层存在未替换的 printf 占位符（%d）")
    if not prose["I2_coarseRuleDefinitionVsImpl"]["matchesWrittenDefinition"]:
        hard.append("I2 粗口径的散文定义与代码实现不符（口径分裂）")
    rep["summary"] = {
        "hardFindings": hard,
        "quoteLayerVerdict": ("PASS —— 引文定位层（A/C/D/E/G/H）无可复现缺陷"
                              if not [h for h in hard if h[0] in "ACDEGH"]
                              else "FAIL —— 见 hardFindings"),
        "proseLayerFindings": [h for h in hard if h[0] in "I"],
        "scopeNote": "A/C/D/E/G/H 属定位/结构层；I1/I2 属散文层。二者都不含语义裁决。",
        "semanticVerdict": "NOT PERFORMED —— 本审计**只**覆盖定位/结构层。"
                           "引文定位正确 ≠ 语义已核验；本文件不主张 semanticReview 完成。",
    }

    OUTP.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"out": str(OUTP), "summary": rep["summary"],
                      "quotes": len(quotes), "hard": len(hard)},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
