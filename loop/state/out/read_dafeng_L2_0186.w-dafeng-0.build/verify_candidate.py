#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核候选：**不复用** build_candidate.py / units.py / spec.py 的任何逻辑。

为什么要另写一份而不是 import 构建期模块（本通道 0178/0182 的复核教训）：
  · 复用切句规则去验「五栏不共用引文」，等于用同一把尺子量自己 —— 切句规则错了，
    两边一起错，判据还过。所以这里五栏独立性改用**字符区间重叠**这个与切分无关的判据。
  · 复用 resolver 去验偏移，等于验「我用我的方法得到了我的结果」。这里从候选里读出
    quote 字符串，**自己重新 find**，再与候选声明的 start/end 比对。

判据分组：H 源/边界、Q 引文、C 五栏独立、N 空栏、S 分区与 basis、B 括号约定、
        P 散文引用与人名、M 元数据自洽。任一不过 ⇒ 退出码 1。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0186.candidate.json"
S, E = 676201, 679978
HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
HEAD = "第一百八十六章 失之交臂"
COLUMNS = ("objective", "obstacle", "action", "result", "cost")
SECTIONS = ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings")

results = []


def check(tag, ok, detail=""):
    results.append((tag, bool(ok), detail))
    return ok


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, "%s[%d]" % (path, i))
    elif isinstance(o, str):
        yield path, o


def main():
    raw = DOCS.read_bytes()
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    seg = text[S:E]
    cand = json.loads(CAND.read_text(encoding="utf-8"))

    # ---- H 源与边界
    check("H1 源文件 sha256 与任务声明一致",
          hashlib.sha256(raw).hexdigest() == HASH, HASH[:16])
    check("H2 候选声明的 sourceHash 与任务一致",
          cand["source"]["sourceHash"] == HASH)
    check("H3 切片以单元标题开头", seg.startswith(HEAD), repr(seg[:16]))
    check("H4 切片长度 == end-start", len(seg) == E - S, "%d" % len(seg))
    check("H5 切片 sha256 可复算（另起字段，未覆盖 sourceHash）",
          hashlib.sha256(seg.encode("utf-8")).hexdigest() == cand["source"]["segmentSha256"])
    check("H6 sourceHash 与 segmentSha256 是两个不同字段",
          cand["source"]["sourceHash"] != cand["source"]["segmentSha256"])

    # ---- Q 引文：自己重新 find
    qobjs = []

    def collect(o, path=""):
        if isinstance(o, dict):
            if {"quote", "start", "end"} <= set(o):
                qobjs.append((path, o))
            for k, v in o.items():
                collect(v, "%s.%s" % (path, k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                collect(v, "%s[%d]" % (path, i))

    collect(cand)
    bad_slice = [p for p, q in qobjs if text[q["start"]:q["end"]] != q["quote"]]
    bad_range = [p for p, q in qobjs if not (S <= q["start"] < q["end"] <= E)]
    bad_hash = [p for p, q in qobjs if q.get("sourceHash") != HASH]
    bad_uniq = [(p, seg.count(q["quote"])) for p, q in qobjs if seg.count(q["quote"]) != 1]
    bad_find = [p for p, q in qobjs if text.find(q["quote"]) != q["start"]]
    # 判据不是「偏移必须是全文首次命中」：本单元里的纯分隔符（'.....'、'------------'）
    # 在全书出现上万次，取哪一次都合法，硬要它等于全文首次命中是**过严**的 ——
    # 初版就在这里误报了两条（sceneBeats[6]/[13] 的分隔符）。
    # 真正要防的是「偏移指到别处却仍宣称是首次」，故判据改为：
    # 要么偏移==全文首次命中，要么候选**如实标注** startIsFirstOccurrence=False
    # （该标注的真伪另由 M1 逐条复算）。
    bad_find_strict = [(p, q["start"], text.find(q["quote"])) for p, q in qobjs
                       if text.find(q["quote"]) != q["start"]
                       and q.get("startIsFirstOccurrence") is not False]
    check("Q1 全部 text[start:end]==quote（逐字回切）", not bad_slice, str(bad_slice[:3]))
    check("Q2 全部落在 [%d,%d)" % (S, E), not bad_range, str(bad_range[:3]))
    check("Q3 全部 sourceHash 正确", not bad_hash, str(bad_hash[:3]))
    check("Q4 全部在区间内命中唯一", not bad_uniq, str(bad_uniq[:3]))
    check("Q5 偏移==全文首次命中，或已如实标注非首次", not bad_find_strict,
          "非首次 %d 条（均已标注，且 Q4 已保证区间内唯一）" % len(bad_find))
    check("Q6 引文对象数 > 0", len(qobjs) > 0, "%d" % len(qobjs))

    # ---- C 五栏独立（用字符区间重叠，与切句规则无关）
    overlaps = []
    for t in cand.get("tasks", []):
        seen = []
        for c in COLUMNS:
            v = t.get(c)
            if not v:
                continue
            for q in v["quotes"]:
                for a, b, other in seen:
                    if not (q["end"] <= a or q["start"] >= b):
                        overlaps.append((t["id"], other, c, q["start"], q["end"]))
                seen.append((q["start"], q["end"], c))
    check("C1 同任务五栏引文字符区间零重叠", not overlaps, str(overlaps[:3]))

    # ---- N 空栏必须带理由
    missing_note = [(t["id"], c) for t in cand.get("tasks", [])
                    for c in COLUMNS if t.get(c) is None and not t.get(c + "Note")]
    n_null = sum(1 for t in cand.get("tasks", []) for c in COLUMNS if t.get(c) is None)
    check("N1 每个 null 栏都有同名的 <栏位>Note", not missing_note, str(missing_note[:3]))
    check("N2 空栏确实存在（不是靠全填满规避）", n_null > 0, "%d 个" % n_null)

    # ---- S 分区与 basis
    check("S1 六个必需分区键全部存在",
          all(k in cand for k in SECTIONS),
          str([k for k in SECTIONS if k not in cand]))
    check("S2 tasks/causeEdges/states/worldSettings 非空（本区间确有内容）",
          all(len(cand.get(k) or []) > 0 for k in ("tasks", "causeEdges", "states", "worldSettings")))
    nobasis = []
    def chk_basis(o, path=""):
        if isinstance(o, dict):
            if isinstance(o.get("text"), str) and "quotes" in o and "basis" not in o:
                nobasis.append(path)
            for k, v in o.items():
                chk_basis(v, "%s.%s" % (path, k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                chk_basis(v, "%s[%d]" % (path, i))
    chk_basis(cand)
    check("S3 每条带引文的断言都有 basis", not nobasis, str(nobasis[:3]))
    check("S4 semanticReview 未声称完成",
          str(cand.get("semanticReview")) in ("not-performed", "False", "false"))
    for k in ("causeEdges", "worldSettings", "foreshadows"):
        for item in cand.get(k) or []:
            if not item.get("basis"):
                check("S5 %s 每条都有 basis" % k, False, item.get("id", "?"))
                break
        else:
            check("S5 %s 每条都有 basis" % k, True)

    # ---- B 括号约定：「」只允许本单元逐字，『』是我的标签
    nonverb = []
    for path, s in walk(cand):
        if path.endswith(".quote"):
            continue
        for m in re.finditer(r"「([^」]*)」", s):
            f = m.group(1)
            if len(f) >= 2 and seg.count(f) == 0:
                nonverb.append((path, f[:34], text.count(f)))
    check("B1 散文里「…」全部在本单元逐字命中", not nonverb, str(nonverb[:4]))

    # ---- P 散文里的段号引用与人名（构建期新加的一道，这里独立重算）
    def paragraphs(text_, s_, e_):
        out = []
        for m in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", text_[s_:e_]):
            r = m.group(0)
            if r.strip():
                lead = len(r) - len(r.lstrip())
                a = s_ + m.start() + lead
                out.append((len(out) + 1, a, a + len(r.strip()), r.strip()))
        return out

    paras = paragraphs(text, S, E)
    by = {"P%03d" % p[0]: p[3] for p in paras}
    para_bad, name_bad = [], []
    for path, s in walk(cand):
        if path.endswith(".quote"):
            continue
        for m in re.finditer(r"(P\d{3})", s):
            if m.group(1) not in by:
                para_bad.append((path, m.group(1), "段号不存在"))
        pairs = []
        for m in re.finditer(r"[「『]([^」』]{2,})[」』]\s*[（(]\s*(P\d{3})", s):
            pairs.append((m.group(2), m.group(1)))
        for m in re.finditer(r"(P\d{3})\s*[（(]([^）)]*)[）)]", s):
            for f in re.finditer(r"[「『]([^」』]{2,})[」』]", m.group(2)):
                pairs.append((m.group(1), f.group(1)))
        for m in re.finditer(r"[（(]([^）)]*?)(P\d{3})\s*[）)]", s):
            for f in re.finditer(r"[「『]([^」』]{2,})[」』]", m.group(1)):
                pairs.append((m.group(2), f.group(1)))
        for m in re.finditer(r"[「『]([^」』]{2,})[」』]\s*(P\d{3})", s):
            pairs.append((m.group(2), m.group(1)))
        for pk, frag in pairs:
            if pk in by and frag not in by[pk]:
                para_bad.append((path, pk, frag[:26]))
        for m in re.finditer(r"([\u4e00-\u9fa5])(公子|娘子|姑娘|花魁|老爷|大人)(?![们哥姐弟])", s):
            if m.group(0) not in seg and m.group(1) not in seg:
                name_bad.append((path, m.group(0)))
    check("P1 散文里每个段号都存在", not [x for x in para_bad if x[2] == "段号不存在"],
          str(para_bad[:3]))
    check("P2 段号旁挂的引文片段确实在该段内", not para_bad, str(para_bad[:4]))
    check("P3 散文里的称呼在本单元存在（未编人名）", not name_bad, str(name_bad[:4]))

    # ---- M 元数据自洽
    occ_bad = []
    for p, q in qobjs:
        if q.get("wholeTextOccurrences") != text.count(q["quote"]):
            occ_bad.append((p, "wholeTextOccurrences"))
        if q.get("occurrencesInRange") != seg.count(q["quote"]):
            occ_bad.append((p, "occurrencesInRange"))
        if q.get("firstOccurrenceAt") != text.find(q["quote"]):
            occ_bad.append((p, "firstOccurrenceAt"))
        if q.get("startIsFirstOccurrence") != (text.find(q["quote"]) == q["start"]):
            occ_bad.append((p, "startIsFirstOccurrence"))
    check("M1 occurrence 元数据逐条可复算", not occ_bad, str(occ_bad[:4]))
    check("M2 machineSelfCheck 声称的项与本次独立复算一致",
          cand["machineSelfCheck"]["allQuotesVerbatim"] is True
          and cand["machineSelfCheck"]["allQuotesInRange"] is True
          and cand["machineSelfCheck"]["taskColumnsIndependentCharSpanLevel"] is True)
    # 覆盖声明复算
    covered = set()
    for p, q in qobjs:
        covered.update(range(q["start"], q["end"]))
    nonspace = {S + i for i, ch in enumerate(seg) if not ch.isspace()}
    ratio = round(len(covered & nonspace) / len(nonspace), 4)
    check("M3 coverage 比例可复算",
          abs(ratio - cand["coverage"]["quoteUnionRatioOfNonSpace"]) < 1e-9,
          "独立 %s vs 声明 %s" % (ratio, cand["coverage"]["quoteUnionRatioOfNonSpace"]))
    check("M4 引文对象数与 machineSelfCheck 声明一致",
          len(qobjs) == cand["machineSelfCheck"]["quoteObjectsResolved"],
          "%d vs %s" % (len(qobjs), cand["machineSelfCheck"]["quoteObjectsResolved"]))

    # ---- Z 零覆盖段处置表完备（自己重算零覆盖集合，不用候选的 coverage 字段）
    cov2 = set()
    for _p, q in qobjs:
        cov2.update(range(q["start"], q["end"]))
    zero2 = ["P%03d" % p[0] for p in paras
             if not any(i in cov2 for i in range(p[1], p[2]) if not text[i].isspace())]
    disp = (cand.get("reverseValidation") or {}).get("zeroCoverageDisposition") or {}
    check("Z1 每个零覆盖段都有处置说明（独立重算零覆盖集合）",
          not [k for k in zero2 if k not in disp],
          "零覆盖 %d 段；未处置 %s" % (len(zero2), [k for k in zero2 if k not in disp][:5]))
    check("Z2 处置表没有多余项（列了其实有引文的段）",
          not [k for k in disp if k not in zero2],
          str([k for k in disp if k not in zero2][:5]))
    check("Z3 处置说明非空且不是占位符",
          all(isinstance(v, str) and len(v) >= 12 for v in disp.values()),
          str([k for k, v in disp.items() if not isinstance(v, str) or len(v) < 12][:5]))

    npass = sum(1 for _t, ok, _d in results if ok)
    for tag, ok, detail in results:
        print("%s %s%s" % ("PASS" if ok else "FAIL", tag, ("  " + detail) if detail else ""))
    print("\n%d/%d 判据通过" % (npass, len(results)))
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
