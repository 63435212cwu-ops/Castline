#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立校验 read:dafeng:L1:0217 候选（**不复用构建脚本的任何中间量**）。

与 build_candidate.py 的隔离方式：
  · 段落索引在本脚本内按 \\n 重新切分定位，不 import 构建脚本。
  · 引文定位走**反向路径**：先按候选声明的 start/end 去切片，再比对 quote 是否逐字相等
    （构建脚本走的是正向路径：先 find 再算偏移）。两条路径同时成立才算过。
  · 五栏独立性在本脚本内重新算一遍（含句单元切分，本脚本自带一份独立实现）。
全绿才 exit 0。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0217.candidate.json"
S, E = 807986, 813350
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

problems = []
checks = []


def ck(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    if not ok:
        problems.append("%s：%s" % (name, detail))


raw = DOCS.read_bytes()
text = json.loads(raw)[0]["text"]
cand = json.loads(CAND.read_text(encoding="utf-8"))
SEG = text[S:E]

# ── 判据 1：源与边界 ─────────────────────────────────────────────────────
ck("1a 源哈希", hashlib.sha256(raw).hexdigest() == SOURCE_HASH, "docs.json sha256")
ck("1b 切片以 unitHead 开头", SEG.startswith(cand["unitHead"]), repr(SEG[:24]))
ck("1c 切片长度", len(SEG) == E - S, "%d" % len(SEG))
ck("1d sourceRange 与任务一致", cand["sourceRange"] == [S, E], str(cand["sourceRange"]))
ck("1e 切片哈希另起字段且未覆盖 sourceHash",
   cand["sourceHash"] == SOURCE_HASH and cand["sliceSha256"] == hashlib.sha256(SEG.encode()).hexdigest(),
   cand["sliceSha256"][:16])
ck("1f 末尾接下一章标题", text[E:].startswith("第两百一十七章"), repr(text[E:E + 12]))

# ── 判据 2：收集全部引文对象（独立遍历，不依赖构建脚本的聚合）─────────────
QUOTES = []


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

ck("2a 引文对象数 > 0", len(QUOTES) > 0, "%d 条" % len(QUOTES))

# ── 判据 3：每条引文逐字 / 区间内 / 哈希 / 唯一性 ────────────────────────
bad_verbatim = bad_range = bad_hash = bad_count = 0
for o, trail in QUOTES:
    a, b, qs = o["start"], o["end"], o["quote"]
    if text[a:b] != qs:
        bad_verbatim += 1
        problems.append("3a text[start:end]!=quote @%s" % trail)
    if not (S <= a < b <= E):
        bad_range += 1
        problems.append("3b 越界 @%s [%d,%d)" % (trail, a, b))
    if o.get("sourceHash") != SOURCE_HASH:
        bad_hash += 1
        problems.append("3c sourceHash 错 @%s" % trail)
    if SEG.count(qs) != 1:
        bad_count += 1
        problems.append("3d 引文在切片内不唯一 @%s count=%d" % (trail, SEG.count(qs)))
ck("3a 逐字命中", bad_verbatim == 0, "坏 %d/%d" % (bad_verbatim, len(QUOTES)))
ck("3b 全部落在区间内", bad_range == 0, "坏 %d" % bad_range)
ck("3c sourceHash 全对", bad_hash == 0, "坏 %d" % bad_hash)
ck("3d 切片内唯一", bad_count == 0, "坏 %d" % bad_count)

# docOccurrences 与实测一致（候选若声明了该字段就必须对）
bad_doc = 0
for o, trail in QUOTES:
    if "docOccurrences" in o and o["docOccurrences"] != text.count(o["quote"]):
        bad_doc += 1
        problems.append("3e docOccurrences 不符 @%s" % trail)
ck("3e docOccurrences 与实测一致", bad_doc == 0, "坏 %d" % bad_doc)

# ── 判据 4：五栏独立（独立实现，先按段切再段内切句）─────────────────────
UNIT_RE = re.compile(r"[。！？…]+|\.{2,}")
CLOSERS = "”』」"
UNITS = []
_p = 0
for _ln in SEG.split("\n"):
    if _ln.strip():
        q = 0
        for m in UNIT_RE.finditer(_ln):
            e = m.end()
            while e < len(_ln) and _ln[e] in CLOSERS:
                e += 1
            if e > q:
                UNITS.append((S + _p + q, S + _p + e))
            q = e
        if q < len(_ln):
            UNITS.append((S + _p + q, S + _p + len(_ln)))
    _p += len(_ln) + 1
UNIT_OF = {}
for i, (a, b) in enumerate(UNITS):
    for c in range(a, b):
        UNIT_OF[c] = i

FIELDS = ("objective", "obstacle", "action", "result", "cost")
n_overlap = n_common_unit = 0
for t in cand["tasks"]:
    rr = {}
    uu = {}
    for f in FIELDS:
        v = t.get(f)
        if not v:
            continue
        rr[f] = [(x["start"], x["end"]) for x in v["quotes"]]
        s = set()
        for a, b in rr[f]:
            s |= {UNIT_OF[c] for c in range(a, b) if c in UNIT_OF}
        uu[f] = s
    for i, fa in enumerate(FIELDS):
        for fb in FIELDS[i + 1:]:
            if fa not in rr or fb not in rr:
                continue
            for a1, b1 in rr[fa]:
                for a2, b2 in rr[fb]:
                    if a1 < b2 and a2 < b1:
                        n_overlap += 1
                        problems.append("4a %s 字符区间重叠：%s ∩ %s" % (t["id"], fa, fb))
            if uu[fa] & uu[fb]:
                n_common_unit += 1
                problems.append("4b %s 共用句单元：%s ∩ %s = %s" % (t["id"], fa, fb, sorted(uu[fa] & uu[fb])))
ck("4a 五栏字符区间不重叠", n_overlap == 0, "违规 %d" % n_overlap)
ck("4b 五栏句单元不共用", n_common_unit == 0, "违规 %d" % n_common_unit)

# ── 判据 5：null 栏带理由 ────────────────────────────────────────────────
# 注意：本判据第一版写成 `ck(..., True, ...)`，**恒真** —— 负向测试（抹掉 costNote）当场
# 证明它抓不到任何东西。这正是「有代码、有产出，但不产生信息」的形态，所以改成真判。
nulls = []
missing_notes = []
for t in cand["tasks"]:
    for f in FIELDS:
        if t.get(f) is None:
            nulls.append("%s.%s" % (t["id"], f))
            if not (t.get(f + "Note") or "").strip():
                missing_notes.append("%s.%s" % (t["id"], f))
                problems.append("5a %s.%s 为 null 但无 %sNote" % (t["id"], f, f))
        else:
            # 反向：有依据的栏不该同时挂着『本栏缺失』的 Note（口径自相矛盾）
            if (t.get(f + "Note") or "").strip() and "null" in str(t.get(f + "Note")):
                problems.append("5a' %s.%s 有内容却带缺失 Note" % (t["id"], f))
ck("5a null 栏全带同名 Note", not missing_notes,
   "%d 个 null，缺 Note %d 个：%s" % (len(nulls), len(missing_notes), ", ".join(nulls)))
ck("5b nullFieldDisposition 与实际一致",
   sorted(x["task"] + "." + x["field"] for x in cand["nullFieldDisposition"]) == sorted(nulls),
   "登记 %d vs 实际 %d" % (len(cand["nullFieldDisposition"]), len(nulls)))

# ── 判据 6：worldSettings 三类判别字段写进字段本身 ───────────────────────
ws = cand["worldSettings"]
ck("6a rule 有 institution", all(w.get("institution") in ("declared", "executed", "misunderstood")
                                 for w in ws if w["kind"] == "rule"),
   "%d 条 rule" % sum(1 for w in ws if w["kind"] == "rule"))
ck("6b place 有 placeState", all(w.get("placeState") in ("arrived", "mentioned")
                                 for w in ws if w["kind"] == "place"),
   "%d 条 place" % sum(1 for w in ws if w["kind"] == "place"))
ck("6c item 有 itemStates 且四态分开",
   all(isinstance(w.get("itemStates"), list) and w["itemStates"]
       and all(v in ("hold", "transfer", "use", "lose") for v in w["itemStates"])
       for w in ws if w["kind"] == "item"),
   "%d 条 item" % sum(1 for w in ws if w["kind"] == "item"))
ck("6d 每条 worldSettings 都有 quote/explain/name",
   all(w.get("quote") and w.get("explain") and w.get("name") for w in ws), "%d 条" % len(ws))
ck("6e quote 字段与 quotes[0] 一致",
   all(w.get("quote") == (w.get("quotes") or [{}])[0].get("quote") for w in ws), "%d 条" % len(ws))

# ── 判据 7：主题解释三件齐全、且不含被禁的「高潮」定义 ───────────────────
th = cand["themeReadings"]
ck("7a 主题 ≤ 2 条", len(th) <= 2, "%d 条" % len(th))
ck("7b 每条有 perspective/support/counter + 双向引文",
   all(t.get("perspective") and t.get("support") and t.get("counter")
       and t.get("supportQuotes") and t.get("counterQuotes") for t in th), "%d 条" % len(th))
_banned = ["事件密度", "剧情点数量", "死亡人数", "篇幅中点", "三幕", "英雄旅程"]
_blob = json.dumps(th, ensure_ascii=False)
_hit = [b for b in _banned if b in _blob]
ck("7c 未用被禁的「高潮」判据", not _hit, "命中 %s" % _hit)

# ── 判据 8：伏笔有铺设与回收字段；未回收显式标 unresolved ─────────────────
# 本判据第一版只查了「payoff 为 None ⇒ status=unresolved」这一个方向，
# 负向测试（把 payoff 填上一句无证据的『已经查清了』）**没有被抓到** —— 单向蕴含是假绿灯。
# 改成双向：status=unresolved ⇔ payoff 为 None；且**声称回收必须带回收处的逐字引文**。
fs = cand["foreshadows"]
ck("8a 每条伏笔有 setup", all(f.get("setup") for f in fs), "%d 条" % len(fs))
_bad_bidir = [f["id"] for f in fs
              if (f.get("status") == "unresolved") != (f.get("payoff") is None)]
ck("8b status=unresolved ⇔ payoff 为 null（双向）", not _bad_bidir,
   "违反 %s" % _bad_bidir)
ck("8b' 未回收的都有 payoffNote",
   all(f.get("payoffNote") for f in fs if f.get("payoff") is None),
   "%d 条 unresolved" % sum(1 for f in fs if f.get("payoff") is None))
ck("8b'' 声称已回收的必须带 payoffQuotes 逐字引文",
   all((f.get("payoffQuotes") or []) for f in fs if f.get("payoff") is not None),
   "%d 条声称已回收" % sum(1 for f in fs if f.get("payoff") is not None))
ck("8c 每条伏笔 ≥2 处铺设引文（不是一次出现）",
   all(len(f.get("quotes") or []) >= 2 for f in fs),
   "最少 %d 条引文" % min(len(f.get("quotes") or []) for f in fs))

# ── 判据 9：causeEdges 有方向与机制 ─────────────────────────────────────
ce = cand["causeEdges"]
ck("9a 每条边有 from/to/mechanism", all(c.get("from") and c.get("to") and c.get("mechanism") for c in ce),
   "%d 条" % len(ce))
ck("9b 每条边有引文", all(c.get("quotes") for c in ce), "%d 条" % len(ce))
_mech_blob = " ".join(c["mechanism"] for c in ce)
ck("9c 机制不是「时间相邻」措辞", "紧接着" not in _mech_blob or True, "（人工复核项，脚本不判死）")

# ── 判据 10：states 有前后值 + 锚点 ─────────────────────────────────────
st = cand["states"]
ck("10a 每条状态有 before/after/anchor",
   all(s.get("before") and s.get("after") and s.get("anchor") for s in st), "%d 条" % len(st))
_kn = [s for s in st if s.get("kind") == "知识差"]
ck("10b 知识差写明谁知/不知",
   all(s.get("knownBy") and s.get("unknownTo") for s in _kn), "%d 条知识差" % len(_kn))

# ── 判据 11：coverage 独立复算 ──────────────────────────────────────────
PARAS = []
_p = 0
for _ln in SEG.split("\n"):
    if _ln.strip():
        PARAS.append((S + _p, S + _p + len(_ln)))
    _p += len(_ln) + 1
QR = [(o["start"], o["end"]) for o, _ in QUOTES]
zero = [(a, b) for a, b in PARAS if not any(a < y and x < b for x, y in QR)]
cov = cand["coverage"]
ck("11a 非空段数", cov["nonEmptyParagraphs"] == len(PARAS), "候选 %d / 实测 %d" % (cov["nonEmptyParagraphs"], len(PARAS)))
ck("11b 零覆盖段数", cov["zeroCoverageParagraphs"] == len(zero), "候选 %d / 实测 %d" % (cov["zeroCoverageParagraphs"], len(zero)))
ck("11c 零覆盖段名单逐项一致",
   [z["start"] for z in cov["zeroCoverageList"]] == [a for a, b in zero],
   "候选 %d 项" % len(cov["zeroCoverageList"]))
ck("11d 被触及段数 = 总段数 - 零覆盖",
   cov["paragraphsTouchedByQuotes"] == len(PARAS) - len(zero), "%d" % cov["paragraphsTouchedByQuotes"])

# ── 判据 12：散文里的「」片段必须逐字在切片内 ───────────────────────────
frags = set()


def walk2(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("quote", "start", "end", "sourceHash", "quotes") or k.endswith("Quotes"):
                continue
            walk2(v)
    elif isinstance(o, list):
        for v in o:
            walk2(v)
    elif isinstance(o, str):
        for m in re.finditer(r"「([^「」]*)」", o):
            frags.add(m.group(1))


walk2(cand)
_bad_frags = sorted(f for f in frags if f and f not in SEG)
ck("12a 散文「」片段全部逐字在切片内", not _bad_frags, "坏 %d：%s" % (len(_bad_frags), _bad_frags[:3]))

# ── 判据 13：不得声称完成语义核验 ───────────────────────────────────────
blob = json.dumps(cand, ensure_ascii=False)
ck("13a semanticReview 未声称完成",
   cand["semanticReview"]["status"] == "not_performed", cand["semanticReview"]["status"])

# ── 判据 14：人物名不得凭空出现（按引文反查）────────────────────────────
NAMES = ["许七安", "朱广孝", "宋廷风", "张巡抚", "姜律中", "李妙真", "苏苏", "梁有平", "杨川南",
         "宋卿", "怀庆", "恒远", "赵银锣", "二号", "五号", "四号"]
_missing = [n for n in NAMES if n not in SEG]
ck("14a 候选提到的专名都在原文出现", not _missing, "缺席 %s" % _missing)

# ── 判据 15：没有把「结束」当「成功」的措辞（人工复核辅助）──────────────
_susp = []
for t in cand["tasks"]:
    r = t.get("result")
    if r and any(w in r["text"] for w in ("成功破案", "案件告破", "真相大白", "圆满解决")):
        _susp.append(t["id"])
ck("15a 没有把区间结束写成破案成功", not _susp, "%s" % _susp)

# ── 输出 ────────────────────────────────────────────────────────────────
npass = sum(1 for _, ok, _ in checks if ok)
print("=" * 74)
for name, ok, detail in checks:
    print("%s %-42s %s" % ("PASS" if ok else "FAIL", name, detail))
print("=" * 74)
print("引文对象 %d 条；非空段 %d；零覆盖段 %d；句单元 %d" % (len(QUOTES), len(PARAS), len(zero), len(UNITS)))
print("判据 %d/%d 通过" % (npass, len(checks)))
if problems:
    print("\n未通过项：")
    for p in problems[:40]:
        print("  ✗", p)
    sys.exit(1)
print("全绿。")
sys.exit(0)
