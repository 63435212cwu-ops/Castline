#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 read:dafeng:L1:0221 的候选（第两百二十章 安抚和翻脸（大章））。

纪律（与 READER.md / 任务 prompt 对齐，全部由脚本强制，不靠自觉）：
  · 偏移**从不手写**：内容模块里只给 Q("…") 字符串，本脚本在 docs[0].text 的切片内
    find 一次，再 +S 换算全文 codepoint 偏移，现取 start/end/docOccurrences。
  · 找不到 / 切片内不唯一 / 越界 / 五栏共用引文或句单元 / null 栏缺同名 Note /
    worldSettings 判别字段缺失 / 伏笔 status 与 payoff 不自洽 / 散文「」片段非逐字 ——
    任一为真即 exit 1，**不写盘**。
  · 一律不声称语义已核验（semanticReview.status = not_performed）。

用法：python3 -B -s build_candidate.py            # 校验并写盘
      python3 -B -s build_candidate.py --dry-run  # 只校验
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L1_0221.candidate.json"

S, E = 826801, 832785
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第两百二十章 安抚和翻脸（大章）"

import content_core as CC          # noqa: E402
import content_relations as CR     # noqa: E402
import content_world as CW         # noqa: E402
from content_core import Q         # noqa: E402

PROBLEMS: list[str] = []
CHECKS: list[tuple[str, bool, str]] = []


def ck(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    if not ok:
        PROBLEMS.append("%s：%s" % (name, detail))


# ── 源与边界 ────────────────────────────────────────────────────────────────
raw = DOCS.read_bytes()
ck("1a 源哈希", hashlib.sha256(raw).hexdigest() == SOURCE_HASH, "docs.json sha256")
TEXT = json.loads(raw)[0]["text"]
SEG = TEXT[S:E]
ck("1b 切片以 unitHead 开头", SEG.startswith(UNIT_HEAD), repr(SEG[:24]))
ck("1c 切片长度 == end-start", len(SEG) == E - S, "%d" % len(SEG))
ck("1d 末尾紧接下一章标题", TEXT[E:].startswith("第两百二十一章"), repr(TEXT[E:E + 14]))

SLICE_SHA = hashlib.sha256(SEG.encode("utf-8")).hexdigest()

# ── 引文解析（正向：find → 偏移）──────────────────────────────────────────
REFS: list[dict] = []
BAD_QUOTES: list[str] = []


def mref(s: str) -> dict:
    if not isinstance(s, str) or not s:
        BAD_QUOTES.append("空引文")
        return {"quote": s, "start": -1, "end": -1}
    n = SEG.count(s)
    if n != 1:
        BAD_QUOTES.append("切片内 count=%d：%r" % (n, s[:60]))
        i = SEG.find(s)
        if i < 0:
            # 给一个近似提示，便于定位是哪个字打错了
            for cut in (s[:20], s[:12], s[-20:], s[-12:]):
                j = SEG.find(cut)
                if j >= 0:
                    BAD_QUOTES.append("  近似片段命中 @%d：%r" % (S + j, SEG[j:j + 80]))
                    break
        return {"quote": s, "start": S + (i if i >= 0 else 0), "end": S + (i if i >= 0 else 0) + len(s)}
    i = SEG.find(s)
    ref = {"quote": s, "start": S + i, "end": S + i + len(s),
           "docOccurrences": TEXT.count(s), "sourceHash": SOURCE_HASH}
    REFS.append(ref)
    return ref


def resolve(o):
    if isinstance(o, Q):
        return mref(str(o))
    if isinstance(o, dict):
        return {k: resolve(v) for k, v in o.items()}
    if isinstance(o, list):
        return [resolve(v) for v in o]
    return o


cand = resolve(CC.build_meta(S, E, SOURCE_HASH, SLICE_SHA))
ck("2a 引文解析无失败", not BAD_QUOTES, "坏 %d：%s" % (len(BAD_QUOTES), BAD_QUOTES[:6]))

# ── 引文逐条复算（反向：start/end → 切片 → 比对）────────────────────────────
QUOTES: list[tuple[dict, str]] = []


def walk(o, trail):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            QUOTES.append((o, trail))
        for k, v in o.items():
            walk(v, trail + "/" + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, trail + "[%d]" % i)


walk(cand, "")
ck("2b 引文对象数 > 0", len(QUOTES) > 0, "%d 条" % len(QUOTES))
b_v = b_r = b_h = b_c = 0
for o, trail in QUOTES:
    a, b, qs = o["start"], o["end"], o["quote"]
    if TEXT[a:b] != qs:
        b_v += 1
        PROBLEMS.append("3a 逐字不符 @%s" % trail)
    if not (S <= a < b <= E):
        b_r += 1
        PROBLEMS.append("3b 越界 @%s [%d,%d)" % (trail, a, b))
    if o.get("sourceHash") != SOURCE_HASH:
        b_h += 1
        PROBLEMS.append("3c sourceHash 错 @%s" % trail)
    if SEG.count(qs) != 1:
        b_c += 1
        PROBLEMS.append("3d 切片内不唯一 @%s" % trail)
ck("3a 逐字命中", b_v == 0, "坏 %d/%d" % (b_v, len(QUOTES)))
ck("3b 全部落在区间内", b_r == 0, "坏 %d" % b_r)
ck("3c sourceHash 全对", b_h == 0, "坏 %d" % b_h)
ck("3d 切片内唯一", b_c == 0, "坏 %d" % b_c)

# ── 句单元切分（先按段切，再段内切句；引号收尾并入前句）────────────────────
UNIT_RE = re.compile(r"[。！？…]+|\.{2,}")
CLOSERS = "”』」"


def sentence_units(seg: str, base: int):
    units = []
    p = 0
    for line in seg.split("\n"):
        if line.strip():
            q = 0
            for m in UNIT_RE.finditer(line):
                e = m.end()
                while e < len(line) and line[e] in CLOSERS:
                    e += 1
                if e > q:
                    units.append((base + p + q, base + p + e))
                q = e
            if q < len(line):
                units.append((base + p + q, base + p + len(line)))
        p += len(line) + 1
    return units


UNITS = sentence_units(SEG, S)
UNIT_OF = {}
for i, (a, b) in enumerate(UNITS):
    for c in range(a, b):
        UNIT_OF[c] = i


def units_of(quotes):
    s = set()
    for q in quotes:
        for c in range(q["start"], q["end"]):
            if c in UNIT_OF:
                s.add(UNIT_OF[c])
    return s


# ── tasks：五栏独立性 + null 栏带理由 ──────────────────────────────────────
FIELDS = ("objective", "obstacle", "action", "result", "cost")
BASES = ("explicit", "inferred", "derived", "unverified")
n_overlap = n_common = n_same_quote = 0
nulls = []
missing_notes = []
bad_basis = []
for t in cand["tasks"]:
    if t.get("actorBasis") not in BASES:
        bad_basis.append("%s.actorBasis=%r" % (t["id"], t.get("actorBasis")))
    for f in FIELDS:
        v = t.get(f)
        if v is None:
            nulls.append("%s.%s" % (t["id"], f))
            if not (t.get(f + "Note") or "").strip():
                missing_notes.append("%s.%s" % (t["id"], f))
            continue
        if v.get("basis") not in BASES:
            bad_basis.append("%s.%s.basis=%r" % (t["id"], f, v.get("basis")))
        if not v.get("quotes"):
            PROBLEMS.append("4c %s.%s 有内容却无引文" % (t["id"], f))
    present = {f: t[f] for f in FIELDS if t.get(f)}
    for i, fa in enumerate(FIELDS):
        for fb in FIELDS[i + 1:]:
            if fa not in present or fb not in present:
                continue
            qa, qb = present[fa]["quotes"], present[fb]["quotes"]
            for x in qa:
                for y in qb:
                    if x["start"] < y["end"] and y["start"] < x["end"]:
                        n_overlap += 1
                        PROBLEMS.append("4a %s 字符区间重叠 %s∩%s" % (t["id"], fa, fb))
            if units_of(qa) & units_of(qb):
                n_common += 1
                PROBLEMS.append("4b %s 共用句单元 %s∩%s" % (t["id"], fa, fb))
            sa = {x["quote"] for x in qa}
            sb = {y["quote"] for y in qb}
            if sa & sb:
                n_same_quote += 1
                PROBLEMS.append("4d %s 两栏引同一句 %s∩%s" % (t["id"], fa, fb))
    for f in FIELDS:
        if t.get(f + "Note") and t.get(f) is not None:
            PROBLEMS.append("5b %s.%s 有内容却挂缺失 Note" % (t["id"], f))
ck("4a 五栏字符区间不重叠", n_overlap == 0, "违规 %d" % n_overlap)
ck("4b 五栏句单元不共用", n_common == 0, "违规 %d" % n_common)
ck("4d 五栏不引同一句", n_same_quote == 0, "违规 %d" % n_same_quote)
ck("4e 所有 basis 合法", not bad_basis, "%s" % bad_basis[:4])
ck("5a null 栏全带同名 Note", not missing_notes,
   "%d 个 null，缺 Note %d：%s" % (len(nulls), len(missing_notes), ", ".join(missing_notes)))
dispo = sorted(x["task"] + "." + x["field"] for x in cand["nullFieldDisposition"])
ck("5c nullFieldDisposition 与实际一致", dispo == sorted(nulls),
   "登记 %d vs 实际 %d" % (len(dispo), len(nulls)))

# ── causeEdges / states / foreshadows ─────────────────────────────────────
for c in cand["causeEdges"]:
    if not (c.get("from") and c.get("to") and c.get("mechanism") and c.get("quotes")):
        PROBLEMS.append("6a 因果边字段不全 %s" % c.get("id"))
    if c.get("basis") not in BASES:
        PROBLEMS.append("6b 因果边 basis 非法 %s" % c.get("id"))
ck("6a 因果边 from/to/mechanism/引文齐全",
   all(c.get("from") and c.get("to") and c.get("mechanism") and c.get("quotes") for c in cand["causeEdges"]),
   "%d 条" % len(cand["causeEdges"]))
ck("6b 因果边都有 basis", all(c.get("basis") in BASES for c in cand["causeEdges"]),
   "%d 条" % len(cand["causeEdges"]))

for s in cand["states"]:
    if not (s.get("who") and s.get("before") and s.get("after") and s.get("anchor") and s.get("quotes")):
        PROBLEMS.append("7a 状态字段不全 %s" % s.get("id"))
    if s.get("kind") == "知识差" and not (s.get("knownBy") and s.get("unknownTo")):
        PROBLEMS.append("7b 知识差未写明知者/不知者 %s" % s.get("id"))
ck("7a 状态 before/after/anchor/引文齐全",
   all(s.get("who") and s.get("before") and s.get("after") and s.get("anchor") and s.get("quotes") for s in cand["states"]),
   "%d 条" % len(cand["states"]))
ck("7b 知识差写明知者/不知者",
   all(s.get("knownBy") and s.get("unknownTo") for s in cand["states"] if s.get("kind") == "知识差"),
   "%d 条知识差" % sum(1 for s in cand["states"] if s.get("kind") == "知识差"))

bad_bidir = [f["id"] for f in cand["foreshadows"]
             if (f.get("status") == "unresolved") != (f.get("payoff") is None)]
ck("8a 伏笔 status=unresolved ⇔ payoff 为 null（双向）", not bad_bidir, "%s" % bad_bidir)
ck("8b 未回收的都有 payoffNote",
   all(f.get("payoffNote") for f in cand["foreshadows"] if f.get("payoff") is None),
   "%d 条 unresolved" % sum(1 for f in cand["foreshadows"] if f.get("payoff") is None))
ck("8c 声称回收的必须带 payoffQuotes",
   all(f.get("payoffQuotes") for f in cand["foreshadows"] if f.get("payoff") is not None),
   "%d 条声称回收" % sum(1 for f in cand["foreshadows"] if f.get("payoff") is not None))
ck("8d 每条伏笔 ≥2 处铺设引文（一次出现不算伏笔）",
   all(len(f.get("quotes") or []) >= 2 for f in cand["foreshadows"]),
   "最少 %d 条引文" % min(len(f.get("quotes") or []) for f in cand["foreshadows"]))

# ── worldSettings 三类判别字段 ────────────────────────────────────────────
ws = cand["worldSettings"]
ck("9a rule 必须有 institution∈{declared,executed,misunderstood}",
   all(w.get("institution") in ("declared", "executed", "misunderstood") for w in ws if w["kind"] == "rule"),
   "%d 条 rule" % sum(1 for w in ws if w["kind"] == "rule"))
ck("9b place 必须有 placeState∈{arrived,mentioned}",
   all(w.get("placeState") in ("arrived", "mentioned") for w in ws if w["kind"] == "place"),
   "%d 条 place" % sum(1 for w in ws if w["kind"] == "place"))
ck("9c item 必须有非空 itemStates（四态多选）",
   all(isinstance(w.get("itemStates"), list) and w["itemStates"]
       and all(v in ("hold", "transfer", "use", "lose") for v in w["itemStates"])
       for w in ws if w["kind"] == "item"),
   "%d 条 item" % sum(1 for w in ws if w["kind"] == "item"))
ck("9d 每条 worldSettings 都有 kind/name/quote/explain",
   all(w.get("kind") in ("rule", "place", "item") and w.get("name") and w.get("quote") and w.get("explain")
       for w in ws), "%d 条" % len(ws))
ck("9e quote 字段与 quotes[0].quote 一致",
   all(w.get("quote") == (w.get("quotes") or [{}])[0].get("quote") for w in ws), "%d 条" % len(ws))
ck("9f 每条 worldSettings 都给了 quotes[]",
   all(w.get("quotes") for w in ws), "%d 条" % len(ws))

# ── themeReadings ────────────────────────────────────────────────────────
th = cand["themeReadings"]
ck("10a 主题解释 ≤2 条", len(th) <= 2, "%d 条" % len(th))
ck("10b 每条有 perspective/support/counter 与两侧引文",
   all(t.get("perspective") and t.get("support") and t.get("counter")
       and t.get("supportQuotes") and t.get("counterQuotes") for t in th), "%d 条" % len(th))
_banned = ["事件密度", "剧情点数量", "死亡人数", "篇幅中点", "三幕", "英雄旅程", "起承转合"]
_hit = [b for b in _banned if b in json.dumps(th, ensure_ascii=False)]
ck("10c 未使用被禁的「高潮」判据", not _hit, "命中 %s" % _hit)

# ── 散文「」片段必须逐字在切片内 ─────────────────────────────────────────
FRAGS = set()


def walk_frag(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("quote", "start", "end", "sourceHash", "quotes") or k.endswith("Quotes"):
                continue
            walk_frag(v)
    elif isinstance(o, list):
        for v in o:
            walk_frag(v)
    elif isinstance(o, str):
        for m in re.finditer(r"「([^「」]*)」", o):
            FRAGS.add(m.group(1))


walk_frag(cand)
_bad_frags = sorted(f for f in FRAGS if f and f not in SEG)
ck("11a 散文「」片段全部逐字在切片内", not _bad_frags,
   "坏 %d：%s" % (len(_bad_frags), _bad_frags[:3]))

# ── 不得声称完成语义核验；专名必须有原文出处 ──────────────────────────────
ck("12a semanticReview 未声称完成",
   cand["semanticReview"]["status"] == "not_performed", cand["semanticReview"]["status"])
NAMES = ["许七安", "许宁宴", "徐虎臣", "李妙真", "张巡抚", "姜律中", "杨川南", "宋布政使",
         "云州知府", "梁有平", "都指挥使", "金锣", "银锣", "铜锣", "虎贲卫", "卫指挥使",
         "飞燕军", "五城兵马司", "三司会审", "白帝城", "福顺镖局", "驿站", "长槊", "军需"]
_missing_names = [n for n in NAMES if n not in SEG]
ck("12b 候选提到的专名都在原文出现", not _missing_names, "缺席 %s" % _missing_names)

# ── 跨任务复用登记（允许但要报出来）──────────────────────────────────────
owner = {}
for t in cand["tasks"]:
    for f in FIELDS:
        for q in (t[f]["quotes"] if t.get(f) else []):
            owner.setdefault(q["quote"], []).append("%s.%s" % (t["id"], f))
cross = {k: v for k, v in owner.items() if len(v) > 1}
ck("13a 跨任务复用已在 crossTaskQuoteReuse 登记",
   sorted(cross) == sorted(x["quote"] for x in cand["crossTaskQuoteReuse"]),
   "%d 处复用" % len(cross))

# ── coverage（谁被引到、谁没被引到）──────────────────────────────────────
PARAS = []
p = 0
for line in SEG.split("\n"):
    if line.strip():
        PARAS.append((S + p, S + p + len(line), line))
    p += len(line) + 1
QR = [(o["start"], o["end"]) for o, _ in QUOTES]
zero = [(a, b, s) for a, b, s in PARAS if not any(a < y and x < b for x, y in QR)]
cov = cand["coverage"]
ck("14a 非空段数", cov["nonEmptyParagraphs"] == len(PARAS),
   "候选 %d / 实测 %d" % (cov["nonEmptyParagraphs"], len(PARAS)))
ck("14b 零覆盖段数", cov["zeroCoverageParagraphs"] == len(zero),
   "候选 %d / 实测 %d" % (cov["zeroCoverageParagraphs"], len(zero)))
ck("14c 零覆盖名单与实测一致",
   [z["start"] for z in cov["zeroCoverageList"]] == [a for a, b, s in zero],
   "候选 %d / 实测 %d" % (len(cov["zeroCoverageList"]), len(zero)))
ck("14d 被引段数 = 总段数 - 零覆盖",
   cov["paragraphsTouchedByQuotes"] == len(PARAS) - len(zero), "%d" % cov["paragraphsTouchedByQuotes"])

# ── 输出 ────────────────────────────────────────────────────────────────
npass = sum(1 for _, ok, _ in CHECKS if ok)
print("=" * 78)
for name, ok, detail in CHECKS:
    print("%s %-44s %s" % ("PASS" if ok else "FAIL", name, detail))
print("=" * 78)
print("引文对象 %d 条；非空段 %d；零覆盖段 %d；句单元 %d；任务 %d；因果边 %d；状态 %d；伏笔 %d；设定 %d"
      % (len(QUOTES), len(PARAS), len(zero), len(UNITS), len(cand["tasks"]), len(cand["causeEdges"]),
         len(cand["states"]), len(cand["foreshadows"]), len(ws)))
print("判据 %d/%d 通过" % (npass, len(CHECKS)))
if PROBLEMS:
    print("\n未通过项：")
    for x in PROBLEMS[:60]:
        print("  ✗", x)
    sys.exit(1)
print("全绿。")

if "--dry-run" not in sys.argv:
    OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("已写盘：%s（sha256=%s）" % (OUT.relative_to(ROOT),
                                    hashlib.sha256(OUT.read_bytes()).hexdigest()))
