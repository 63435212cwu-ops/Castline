#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核 loop/state/out/read_sanguo_L0_0116.candidate.json 的**机器可核验层**。

这个脚本**不 import** 产出方的构建器/复算器（w-dafeng-1 声明的
build_0116.py / verify_0116.py / content_0116.py），也不读它的内容源；
只读候选 JSON 与原文 docs.json，其余判据在本脚本内**重新实现**。

它**不做**语义复核（那是 read-verify 通道换 agent 的活），也不给质量分。

用法:
    python3 -B -s loop/state/out/read_sanguo_L0_0116.w-sanguo-0.dupclaim/audit_0116.py
输出: 人类可读报告 + audit_0116_report.json（同目录）
"""
import collections
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
CAND = ROOT / "loop/state/out/read_sanguo_L0_0116.candidate.json"
DOCS = ROOT / "data/cache/fe42d01f3826fe8096f86614.docs.json"
TASK = ROOT / "loop/state/runs/task-read_sanguo_L0_0116.json"
RECORD = ROOT / "loop/state/out/read_sanguo_L0_0116.json"
SLICE = (586983, 591664)

# 本脚本从任务文件**独立读出**区间，而不是照抄候选自报的 source.sliceStart/End
TASKFILE_RANGE = tuple(json.loads(TASK.read_text("utf-8"))["sourceRange"])

R = collections.OrderedDict()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_quote_objects(obj, path="$"):
    """产出候选里**全部**带 quote/start/end 的对象（不预设分区名单）。"""
    if isinstance(obj, dict):
        if "quote" in obj and "start" in obj and "end" in obj:
            yield path, obj
        for k, v in obj.items():
            yield from walk_quote_objects(v, "%s.%s" % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_quote_objects(v, "%s[%d]" % (path, i))


def main():
    fails, warns, notes = [], [], []
    text = json.loads(DOCS.read_text("utf-8"))[0]["text"]
    docs_sha = sha256_file(DOCS)
    cand = json.loads(CAND.read_text("utf-8"))
    s, e = SLICE
    slice_text = text[s:e]

    # ── B0 区间与哈希口径 ────────────────────────────────────────────────
    R["B0_slice"] = {
        "docs_sha256": docs_sha,
        "task_sourceRange": list(TASKFILE_RANGE),
        "my_slice": [s, e],
        "range_matches_taskfile": list(TASKFILE_RANGE) == [s, e],
        "slice_len": len(slice_text),
        "slice_starts_with_unit_head": slice_text.startswith(cand["unitHead"]),
        "slice_sha256_utf8": hashlib.sha256(slice_text.encode("utf-8")).hexdigest(),
    }
    if not R["B0_slice"]["range_matches_taskfile"]:
        fails.append("B0 我读的区间与任务文件不一致")
    if not R["B0_slice"]["slice_starts_with_unit_head"]:
        fails.append("B0 切片不以本单元标题开头 —— 偏移口径错了")
    if docs_sha != cand["source"]["sourceHash"]:
        fails.append("B0 候选 source.sourceHash 与实测 docs.json 不符")

    quotes = list(walk_quote_objects(cand))
    bad = collections.Counter()
    bad_reverse, bad_range, bad_hash, bad_len, bad_eq = [], [], [], [], []
    for path, q in quotes:
        qs, qe, qt = q["start"], q["end"], q["quote"]
        if not (isinstance(qs, int) and isinstance(qe, int)):
            bad["nonint"] += 1
            continue
        if text[qs:qe] != qt:
            bad_eq.append(path)
            continue
        if not (s <= qs < qe <= e):
            bad_range.append(path)
        if qe - qs != len(qt):
            bad_len.append(path)
        if q.get("sourceHash") != docs_sha:
            bad_hash.append(path)
        # 反向：不轻信自报偏移，从切片内独立 find
        got = text.find(qt, s, e)
        if got != qs:
            bad_reverse.append({"path": path, "declared": qs, "found": got})
    R["B1_quotes"] = {
        "total": len(quotes),
        "equality_fail": len(bad_eq),
        "out_of_slice": len(bad_range),
        "sourceHash_mismatch": len(bad_hash),
        "length_mismatch": len(bad_len),
        "reverse_find_mismatch": len(bad_reverse),
        "reverse_find_note": "text.find(quote, sliceStart, sliceEnd) 必须等于自报 start",
    }
    for k in ("equality_fail", "out_of_slice", "sourceHash_mismatch",
              "length_mismatch", "reverse_find_mismatch"):
        if R["B1_quotes"][k]:
            fails.append("B1 %s = %d" % (k, R["B1_quotes"][k]))
    if len(quotes) != cand["counts"]["quoteObjects"]:
        warns.append("B1 候选自报 quoteObjects=%d，我扫到 %d"
                     % (cand["counts"]["quoteObjects"], len(quotes)))

    # ── B2 五栏「同一句话不得当多栏依据」 ───────────────────────────────
    # 切句两条规则（第二条是我第一版漏掉的，见下）：
    #   ① 句末标点断句；句末标点常落在引号内，故闭合引号后也要断；
    #   ② **换行也断句**。本回标题行「第一百十七回　…　诸葛瞻战死绵竹」**没有**句末标点，
    #      只按标点切会把它与紧随的正文粘成一个单元，于是 T01 的 objective 引文
    #      （起于标题之后）和 obstacle 引文被判成"同一句" —— 实测报出 1 处**假冲突**。
    #      这是**我这个复核脚本**的缺陷，不是被复核候选的缺陷；我改的是判据实现，
    #      没有改"同一句话不得当多栏依据"这条纪律本身。
    END = "。！？…”』」"
    def split_spans(t, base):
        """切句并**直接产出每句的真实绝对区间**。

        不能让调用方用「累加句长」去复原偏移：换行被丢弃后就不再与切片逐字对齐，
        累加会把后续所有句子的区间整体前移 —— 那样得到的"冲突"全是假的。
        """
        out, start = [], 0
        i = 0
        depth = 0
        while i < len(t):
            ch = t[i]
            if ch in "“‘":
                depth += 1
            elif ch in "”’":
                depth = max(0, depth - 1)
            if ch == "\n":                      # ② 换行是硬边界
                seg = t[start:i]
                if seg.strip():
                    out.append((base + start, base + i, seg))
                i += 1
                start = i
                continue
            if ch in END and (depth == 0 or ch in "”’"):
                seg = t[start:i + 1]
                if seg.strip():
                    out.append((base + start, base + i + 1, seg))
                start = i + 1
            i += 1
        seg = t[start:]
        if seg.strip():
            out.append((base + start, base + len(t), seg))
        return out

    spans = split_spans(slice_text, s)
    sents = [x[2] for x in spans]

    def unit_of(abs_pos):
        for i, (a, b, _) in enumerate(spans):
            if a <= abs_pos < b:
                return i
        return None

    cols = ("objective", "obstacle", "action", "result", "cost")
    conflicts = []
    for t in cand["tasks"]:
        used = {}
        for c in cols:
            for q in (t.get(c + "Quotes") or []):
                u = unit_of(q["start"])
                if u is None:
                    continue
                if u in used and used[u] != c:
                    conflicts.append({"task": t["id"], "sentence": u,
                                      "cols": [used[u], c]})
                used.setdefault(u, c)
    R["B2_five_column"] = {"sentences": len(sents), "conflicts": len(conflicts),
                           "detail": conflicts[:10]}
    if conflicts:
        fails.append("B2 同一句读单元被同任务两栏共用：%d 处" % len(conflicts))

    # ── B3 null 栏必须带理由 Note ───────────────────────────────────────
    nulls = [{"task": t["id"], "col": c,
              "note": (t.get(c + "Note") or "")}
             for t in cand["tasks"] for c in cols if t.get(c) is None]
    no_reason = [n for n in nulls if len(n["note"].strip()) < 8]
    R["B3_nulls"] = {"count": len(nulls), "without_reason": len(no_reason),
                     "declared_nullColumns": len(cand.get("nullColumns") or []),
                     "detail": no_reason[:8]}
    if no_reason:
        fails.append("B3 %d 个 null 栏没有写明理由" % len(no_reason))

    # ── B4 worldSettings 三态字段 ───────────────────────────────────────
    ws = collections.Counter()
    bad_ws = []
    for w in cand["worldSettings"]:
        k = w.get("kind")
        ws[k] += 1
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            bad_ws.append((w.get("name"), "placeState", w.get("placeState")))
        elif k == "item":
            st = w.get("itemStates") or []
            if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                bad_ws.append((w.get("name"), "itemStates", st))
        elif k == "rule" and w.get("institution") not in ("declared", "executed",
                                                          "misunderstood"):
            bad_ws.append((w.get("name"), "institution", w.get("institution")))
        elif k not in ("place", "item", "rule"):
            bad_ws.append((w.get("name"), "kind", k))
    R["B4_worldSettings"] = {"by_kind": dict(ws), "illegal": bad_ws}
    if bad_ws:
        fails.append("B4 worldSettings 三态字段非法：%d 条" % len(bad_ws))

    # ── B5 foreshadow: resolved 必须有 payoff ──────────────────────────
    fs_bad = []
    for f in cand["foreshadows"]:
        st = f.get("status")
        if st == "resolved" and not (f.get("payoff") or []):
            fs_bad.append((f["id"], "resolved 但无 payoff"))
        if st == "unresolved" and (f.get("payoff") or []):
            fs_bad.append((f["id"], "unresolved 却有 payoff"))
        if st not in ("resolved", "unresolved"):
            fs_bad.append((f["id"], "status 非法 %r" % st))
    R["B5_foreshadows"] = {
        "count": len(cand["foreshadows"]),
        "resolved": sum(1 for f in cand["foreshadows"] if f.get("status") == "resolved"),
        "unresolved": sum(1 for f in cand["foreshadows"] if f.get("status") == "unresolved"),
        "illegal": fs_bad,
    }
    if fs_bad:
        fails.append("B5 伏笔自洽性失败：%d 条" % len(fs_bad))

    # ── B6 主题解读三件套 ──────────────────────────────────────────────
    th_bad = []
    for t in cand["themeReadings"]:
        if not t.get("perspective") or not t.get("support") or not t.get("counter"):
            th_bad.append(t.get("id"))
    R["B6_theme"] = {"count": len(cand["themeReadings"]), "missing_part": th_bad}
    if th_bad:
        fails.append("B6 主题解读缺 perspective/support/counter：%s" % th_bad)

    # ── B7 不得自称语义已核验 ──────────────────────────────────────────
    sr = cand.get("semanticReview") or {}
    R["B7_semantic"] = {"performed": sr.get("performed")}
    if sr.get("performed") is not False:
        fails.append("B7 候选声称语义已核验（performed=%r）" % sr.get("performed"))

    # ── B8 反向覆盖：自己重算，不采信候选自报的 175/198 ─────────────────
    covered = set()
    for _, q in quotes:
        for i, (a, b, _) in enumerate(spans):
            if q["start"] < b and a < q["end"]:
                covered.add(i)
    unc = [{"i": i, "absStart": spans[i][0], "text": sents[i][:60]}
           for i in range(len(sents)) if i not in covered]
    R["B8_reverseCoverage"] = {
        "my_splitter": {"sentences": len(sents), "covered": len(covered),
                        "uncovered": len(unc),
                        "rule": "句末标点断句（含闭合引号后）+ 换行为硬边界"},
        "candidate_claimed": {"sentences": cand["reverseCoverage"]["sentences"],
                              "covered": cand["reverseCoverage"]["coveredSentences"],
                              "uncovered": cand["reverseCoverage"]["uncoveredSentences"],
                              "rule": cand["reverseCoverage"]["method"]},
        "uncovered_detail": unc,
        "agreement": "两套切句口径不同（我按换行也断句，候选未说明是否断），"
                     "故句数不同属预期；判据是**未覆盖项是否与候选列出的一致或更少**",
    }
    # 我数出的未覆盖句子在候选的未覆盖清单里是否也出现（按文本前缀比对）
    cand_unc = {u["text"].strip()[:40] for u in cand["reverseCoverage"]["uncovered"]}
    mine = {u["text"].strip()[:40] for u in unc}
    extra = sorted(mine - cand_unc)
    R["B8_reverseCoverage"]["my_extra_uncovered_not_in_candidate_list"] = extra
    if extra:
        warns.append("B8 我数出 %d 句未被任何引文覆盖、而候选的未覆盖清单里没有逐字对应项：%s"
                     % (len(extra), extra[:5]))

    # ── B9 保护区：记录与候选是否仍未被我触碰 ──────────────────────────
    rec = json.loads(RECORD.read_text("utf-8"))
    R["B9_untouched"] = {
        "record_sha256": sha256_file(RECORD),
        "record_agent": rec.get("agent"),
        "record_submittedAt": rec.get("submittedAt"),
        "record_validation_problems": (rec.get("validation") or {}).get("problems"),
        "candidate_sha256": sha256_file(CAND),
        "candidate_agent": cand.get("agent"),
    }

    R["fails"], R["warns"], R["notes"] = fails, warns, notes
    R["verdict"] = "FAIL" if fails else ("WARN" if warns else "OK")
    return R


if __name__ == "__main__":
    rep = main()
    out = pathlib.Path(__file__).resolve().parent / "audit_0116_report.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print("\n== verdict: %s (fails=%d warns=%d) -> %s"
          % (rep["verdict"], len(rep["fails"]), len(rep["warns"]), out))
    sys.exit(1 if rep["fails"] else 0)
