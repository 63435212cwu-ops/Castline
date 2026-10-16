#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立校验 read:dafeng:L2:0198 候选。作者：w-dafeng-0。

**不复用构建期任何中间量**：源文件重新读、哈希重新算、段落索引在本脚本内
按换行另行切分、句单元另行切分、引文逐条重新 find。构建脚本里的
ALL_QUOTES / PARAS / SENTS / COVER 在本文件里都不存在。

它要能独立地抓住的缺陷形态（正是本轮从 w-read-4 草稿里抓出来的那些）：
  A. 引文不逐字 / 越界 / 区间内不唯一 / 偏移取到区间外的首次出现
  B. 引文对象 sourceHash 不是整个 docs.json 的 sha256
  C. 五栏共用同一句（字符区间级 + 句单元级）
  D. null 栏没有 <栏位>Note
  E. worldSettings 三类判别字段（placeState / institution / itemStates）缺失或非法
  F. 零覆盖处置表与实测覆盖不一致（漏段 / 多段）
  G. 散文里的悬空 ID（引用了不存在的条目）
  H. 散文把 Pnnn 与逐字片段配错（片段不在该段）
  I. 散文用了本区间 0 次出现的词当事实
  J. 内容分区缺失（任务要求的 6 个分区）
用法：python3 verify_candidate.w-dafeng-0.py [--candidate <path>]
退出码 0 = 全绿。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND_PATH = ROOT / "loop/state/out/read_dafeng_L2_0198.candidate.json"
S, E = 724528, 728317
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第一百九十七章 晚宴和枇杷"
REQUIRED_SECTIONS = ("tasks", "causeEdges", "states", "foreshadows",
                     "worldSettings", "themeReadings")
COLNAMES = ("objective", "obstacle", "action", "result", "cost")
BASIS = ("explicit", "inferred", "derived", "unverified")

FAILS, WARNS, CHECKS = [], [], []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    if not ok:
        FAILS.append("%s%s" % (name, ("： " + detail) if detail else ""))
    return bool(ok)


if "--candidate" in sys.argv:
    CAND_PATH = Path(sys.argv[sys.argv.index("--candidate") + 1])

# ── 1. 源文件：重新读、重新算哈希 ──────────────────────────────────────────
RAW = DOCS.read_bytes()
FILE_HASH = hashlib.sha256(RAW).hexdigest()
check("1.1 sourceHash == task.sourceHash", FILE_HASH == SRC_HASH, FILE_HASH)
DOC = json.loads(RAW.decode("utf-8"))
TEXT = DOC[0]["text"] if isinstance(DOC, list) else DOC["docs"][0]["text"]
check("1.2 切片以 unitHead 开头", TEXT[S:S + len(UNIT_HEAD)] == UNIT_HEAD,
      repr(TEXT[S:S + len(UNIT_HEAD)]))
SEG = TEXT[S:E]
SEG_HASH = hashlib.sha256(SEG.encode("utf-8")).hexdigest()

# ── 2. 段落索引：本脚本内另行切分（不用构建期的 PARAS）──────────────────────
PARAS, pos = [], S
for line in SEG.split("\n"):
    if line.strip():
        i = TEXT.find(line, pos)
        assert i >= 0, line[:20]
        PARAS.append((i, i + len(line), line))
        pos = i + len(line)
NPARA = len(PARAS)


def para_of(p):
    for n, (a, b, _t) in enumerate(PARAS, 1):
        if a <= p < b:
            return n
    return None


CAND = json.loads(CAND_PATH.read_text(encoding="utf-8"))

# ── 3. 内容分区必须存在 ────────────────────────────────────────────────────
for k in REQUIRED_SECTIONS:
    check("3 分区存在 %s" % k, k in CAND)

# ── 4. 收集全部引文对象（含 tasks 五栏与其余分区）───────────────────────────
QOBJS = []


def collect(o):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            QOBJS.append(o)
        for v in o.values():
            collect(v)
    elif isinstance(o, list):
        for v in o:
            collect(v)


collect(CAND)
check("4.1 引文对象数 > 0", len(QOBJS) > 0, str(len(QOBJS)))

verbatim = inrange = uniq = hashok = offok = 0
for qo in QOBJS:
    q, a, b = qo["quote"], qo["start"], qo["end"]
    if TEXT[a:b] == q:
        verbatim += 1
    if S <= a and b <= E:
        inrange += 1
    if SEG.count(q) == 1:
        uniq += 1
    if qo.get("sourceHash") == SRC_HASH:
        hashok += 1
    # 锚点必须是**区间内**那一处出现，不是全文首次出现。
    # 反例（本区间实测）：『“怎么说？”』全文首见在 265466（司天监那段），
    # 若用 TEXT.find 取偏移，会把本区间的引文指到十万字符之外的别人段上。
    if SEG.find(q) >= 0 and a == S + SEG.find(q):
        offok += 1
check("4.2 引文逐字 text[start:end]==quote", verbatim == len(QOBJS),
      "%d/%d" % (verbatim, len(QOBJS)))
check("4.3 引文全落在区间内", inrange == len(QOBJS), "%d/%d" % (inrange, len(QOBJS)))
check("4.4 引文在区间内唯一（无偏移歧义）", uniq == len(QOBJS),
      "%d/%d" % (uniq, len(QOBJS)))
check("4.5 每对象 sourceHash 正确", hashok == len(QOBJS),
      "%d/%d" % (hashok, len(QOBJS)))
check("4.6 偏移锚定在区间内出现处（== S+SEG.find(quote)）", offok == len(QOBJS),
      "%d/%d" % (offok, len(QOBJS)))

# 4.7 每条引文的 paraLabel / sentUnit 必须与现算一致
sent_spans = []
for (a, b, _t) in PARAS:
    cur = a
    for m in re.finditer(r"[。！？…]+|\.{2,}", TEXT[a:b]):
        end = a + m.end()
        if end > cur:
            sent_spans.append((cur, end))
        cur = end
    if cur < b:
        sent_spans.append((cur, b))


def sent_of(p):
    for i, (a, b) in enumerate(sent_spans, 1):
        if a <= p < b:
            return i
    return None


pl_bad = st_bad = 0
for qo in QOBJS:
    if qo.get("paraLabel") != ("P%03d" % para_of(qo["start"])):
        pl_bad += 1
    if qo.get("sentUnit") != sent_of(qo["start"]):
        st_bad += 1
check("4.7 paraLabel 与现算一致", pl_bad == 0, "%d 条不符" % pl_bad)
check("4.8 sentUnit 与现算一致", st_bad == 0, "%d 条不符" % st_bad)

# ── 5. 五栏独立性 ──────────────────────────────────────────────────────────
dup_q = dup_span = dup_sent = miss_basis = 0
for t in CAND.get("tasks", []):
    seen_q, seen_sp, seen_st = [], [], []
    for cn in COLNAMES:
        c = t.get(cn)
        if c is None:
            if not (t.get(cn + "Note") or "").strip():
                WARNS.append("%s.%s 为 null 且无 %sNote" % (t["id"], cn, cn))
            continue
        if isinstance(c, dict) and c.get("basis") not in BASIS:
            miss_basis += 1
        for qo in (c.get("quotes") or []) if isinstance(c, dict) else []:
            if qo is None:
                continue
            if qo["quote"] in seen_q:
                dup_q += 1
            seen_q.append(qo["quote"])
            for (a, b) in seen_sp:
                if not (qo["end"] <= a or qo["start"] >= b):
                    dup_span += 1
            seen_sp.append((qo["start"], qo["end"]))
            if qo.get("sentUnit") in seen_st:
                dup_sent += 1
            seen_st.append(qo.get("sentUnit"))
check("5.1 同任务五栏不共用同一句", dup_q == 0, "%d 处" % dup_q)
check("5.2 同任务五栏字符区间不重叠", dup_span == 0, "%d 处" % dup_span)
check("5.3 同任务五栏不共用句单元", dup_sent == 0, "%d 处" % dup_sent)
check("5.4 非 null 栏都有合法 basis", miss_basis == 0, "%d 处" % miss_basis)

# ── 6. worldSettings 判别字段 ──────────────────────────────────────────────
ws_bad = 0
for w in CAND.get("worldSettings", []):
    k = w.get("kind")
    if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        ws_bad += 1
    if k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(
                x not in ("hold", "transfer", "use", "lose") for x in st):
            ws_bad += 1
    if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        ws_bad += 1
    if k not in ("place", "item", "rule"):
        ws_bad += 1
check("6 worldSettings 三类判别字段合法", ws_bad == 0, "%d 条非法" % ws_bad)

# ── 7. 零覆盖处置表与实测覆盖对齐 ──────────────────────────────────────────
COVER = set()
for qo in QOBJS:
    COVER.update(range(qo["start"], qo["end"]))
measured_zero = [("P%03d" % n) for n, (a, b, _t) in enumerate(PARAS, 1)
                 if not any(x in COVER for x in range(a, b))]
rv = CAND.get("reverseValidation") or {}
disp = {d["para"]: d.get("disposition") for d in (rv.get("zeroDisposition") or [])}
check("7.1 处置表覆盖全部零覆盖段",
      set(disp) == set(measured_zero),
      "漏 %s / 多 %s" % (sorted(set(measured_zero) - set(disp)),
                         sorted(set(disp) - set(measured_zero))))
check("7.2 每条处置非空", all((v or "").strip() for v in disp.values()),
      "%d 条空" % sum(1 for v in disp.values() if not (v or "").strip()))

# 7.3 处置里『已并入 X』必须 X 真的引用到该段
merged_bad = []
ids_by_section = {}
for key in ("tasks", "causeEdges", "states", "knowledgeDiffs", "foreshadows",
            "worldSettings", "themeReadings", "unknowns", "selfCritique",
            "rejectedEdges", "notForeshadows", "notWorldSettings"):
    for item in CAND.get(key, []) or []:
        if isinstance(item, dict) and item.get("id"):
            ids_by_section[item["id"]] = item
for lab, why in disp.items():
    for m in re.finditer(r"已并入 ([A-Z]{1,3}\d+)", why or ""):
        tid = m.group(1)
        item = ids_by_section.get(tid)
        if item is None:
            merged_bad.append("%s→%s(不存在)" % (lab, tid))
            continue
        blob = json.dumps(item, ensure_ascii=False)
        n = int(lab[1:])
        a, b, txt = PARAS[n - 1]
        if txt not in blob:
            merged_bad.append("%s→%s(该条未引用本段)" % (lab, tid))
check("7.3 『已并入 X』可核验", not merged_bad, "; ".join(merged_bad))

# ── 8. 散文里的悬空 ID ─────────────────────────────────────────────────────
ALL_IDS = set(ids_by_section)
SKIP = {"L2"}
dangling = []


def walk(o, where="cand"):
    if isinstance(o, dict):
        for k, v in o.items():
            walk(v, "%s.%s" % (where, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (where, i))
    elif isinstance(o, str):
        if where.endswith(".id"):
            return
        for m in re.finditer(r"(?<![A-Za-z0-9])([A-Z]{1,3}\d{1,3})(?![A-Za-z0-9])", o):
            tok = m.group(1)
            if tok in SKIP or tok in ALL_IDS:
                continue
            if re.fullmatch(r"P\d{3}", tok):
                if not (1 <= int(tok[1:]) <= NPARA):
                    dangling.append("%s:%s(段号越界)" % (where, tok))
                continue
            dangling.append("%s:%s" % (where, tok))


walk(CAND)
check("8 无悬空条目 ID / 段号", not dangling, "; ".join(dangling[:6]))

# ── 9. Pnnn『片段』归属 ────────────────────────────────────────────────────
misattr = []


def walk2(o, where="cand"):
    if isinstance(o, dict):
        for k, v in o.items():
            walk2(v, "%s.%s" % (where, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk2(v, "%s[%d]" % (where, i))
    elif isinstance(o, str):
        for m in re.finditer(r"P(\d{3})[『「]([^』」]{4,})[』」]", o):
            n, frag = int(m.group(1)), m.group(2)
            if not (1 <= n <= NPARA):
                misattr.append("%s:P%03d 越界" % (where, n))
                continue
            if frag not in PARAS[n - 1][2]:
                misattr.append("%s:P%03d『%s』" % (where, n, frag[:20]))


walk2(CAND)
check("9 Pnnn 与片段归属一致", not misattr, "; ".join(misattr[:6]))

# ── 10. 区间内零出现的词不得当事实 ─────────────────────────────────────────
FORBID = ["查案", "调查", "办案", "缉凶", "命案", "凶手"]
used_bad = []


def walk3(o, where="cand"):
    if isinstance(o, dict):
        for k, v in o.items():
            walk3(v, "%s.%s" % (where, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk3(v, "%s[%d]" % (where, i))
    elif isinstance(o, str):
        for w in FORBID:
            if w in o and SEG.count(w) == 0:
                used_bad.append("%s:%s" % (where, w))


walk3(CAND)
check("10 未用区间内零出现的词当事实", not used_bad, "; ".join(used_bad[:6]))

# ── 11. 不得声称语义复核完成 ───────────────────────────────────────────────
sr = CAND.get("semanticReview")
check("11 semanticReview 未声称完成", sr in (None, "not-performed", "none"), repr(sr))

# ── 12. 源哈希口径没被切片哈希覆盖 ─────────────────────────────────────────
check("12 source.sourceHash 是整个 docs.json 的哈希",
      (CAND.get("source") or {}).get("sourceHash") == SRC_HASH)
check("12b 切片哈希另起字段（未覆盖 sourceHash）",
      (CAND.get("source") or {}).get("segmentSha256") == SEG_HASH,
      "%s" % (CAND.get("source") or {}).get("segmentSha256"))

# ── 13. 引文覆盖统计（只报数，不换算质量分）────────────────────────────────
nonspace = sum(1 for ch in SEG if not ch.isspace())
touched = [n for n, (a, b, _t) in enumerate(PARAS, 1)
           if any(x in COVER for x in range(a, b))]

print("=" * 74)
print("独立校验 read:dafeng:L2:0198（不复用构建期中间量）")
print("候选：%s" % CAND_PATH)
print("候选 sha256 = %s" % hashlib.sha256(CAND_PATH.read_bytes()).hexdigest())
print("源哈希 = %s" % FILE_HASH)
print("切片 sha256 = %s" % SEG_HASH)
print("非空段 = %d；引文对象 = %d；零覆盖段 = %d；被引段 = %d"
      % (NPARA, len(QOBJS), len(measured_zero), len(touched)))
print("引文并集 codepoint = %d / 非空白 %d = %.4f（只是覆盖面，不是理解程度）"
      % (len(COVER), nonspace, len(COVER) / float(nonspace)))
print("-" * 74)
for name, ok, detail in CHECKS:
    print("%s %s%s" % ("PASS" if ok else "FAIL", name, ("  | " + detail) if detail else ""))
print("-" * 74)
if WARNS:
    print("WARN（不判失败，但复核应看到）：")
    for w in WARNS:
        print("   -", w)
print("判据 %d 条：PASS %d / FAIL %d"
      % (len(CHECKS), sum(1 for _n, ok, _d in CHECKS if ok), len(FAILS)))
if FAILS:
    print("\n失败明细：")
    for f in FAILS:
        print("   [FAIL]", f)
    sys.exit(1)
print("\n全绿（退出码 0）。")
sys.exit(0)
