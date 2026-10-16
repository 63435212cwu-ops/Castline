#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核 read:dafeng:L3:0259 的机械复算脚本（VERIFIER w-verify-4）。

纪律：
· **不 import** 候选作者的 build_candidate.py / content_0259.py / verify_candidate.py，
  也不读它们的任何中间产物；只读两件东西：原文 docs.json 与候选 JSON 本身。
· 段落表、覆盖统计、五栏区间重叠、出现次数自述、随机抽样全部在本脚本内重新实现。
· 每个判据都打印 PASS/FAIL；任一 FAIL 时退出码非 0。

复现：python3 -B -s loop/state/out/verify_dafeng_L3_0259.w-verify-4.verify/independent_check.py
"""
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0259.candidate.json"
S, E = 1077101, 1082611
DHash = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

fails = []


def check(name, ok, detail=""):
    print("%-6s %s%s" % ("PASS" if ok else "FAIL", name, ("  —— " + detail) if detail else ""))
    if not ok:
        fails.append(name)


text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
cand = json.loads(CAND.read_text(encoding="utf-8"))
sl = text[S:E]

# ── 0. 源身份 ────────────────────────────────────────────────────────────────
check("S00 docs.json sha256 == task.sourceHash",
      hashlib.sha256(DOCS.read_bytes()).hexdigest() == DHash)
check("S01 切片长度 5510 且以章题开头/以声明尾串结尾",
      len(sl) == 5510 and sl.startswith("第三十章 预言师")
      and sl.endswith(cand["source"]["boundaryTail"]))
check("S02 sliceSha256 自述与实算一致",
      hashlib.sha256(sl.encode()).hexdigest() == cand["source"]["sliceSha256"])
check("S03 range 与任务区间一致", cand["source"]["range"] == [S, E])
check("S04 候选声明的 path 存在且哈希相符",
      (ROOT / cand["source"]["path"]).exists()
      and hashlib.sha256((ROOT / cand["source"]["path"]).read_bytes()).hexdigest() == DHash)

# ── 1. 收集全部引文对象（含嵌套）────────────────────────────────────────────
quotes = []


def walk(node):
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node:
            quotes.append(node)
        for v in node.values():
            walk(v)
    elif isinstance(node, list):
        for v in node:
            walk(v)


walk(cand)

bad_off, bad_hash, bad_range, bad_occ, bad_para = [], [], [], [], []

PARTS = sl.split("\n\n")
PARA_OFF = []
_o = S
for _p in PARTS:
    PARA_OFF.append((_o, _o + len(_p)))
    _o += len(_p) + 2


def para_of(pos):
    for i, (a, b) in enumerate(PARA_OFF):
        if a <= pos < b:
            return i
    return None


for q in quotes:
    if text[q["start"]:q["end"]] != q["quote"]:
        bad_off.append(q["quote"][:30])
    if q.get("sourceHash") != DHash:
        bad_hash.append(q["quote"][:30])
    if not (S <= q["start"] and q["end"] <= E):
        bad_range.append(q["quote"][:30])
    if "wholeTextOccurrences" in q:
        occ = [m.start() for m in re.finditer(re.escape(q["quote"]), text)]
        inr = [o for o in occ if S <= o < E]
        if (q["wholeTextOccurrences"] != len(occ) or q["occurrencesInRange"] != len(inr)
                or q.get("firstOccurrenceAt") != (occ[0] if occ else None)
                or q.get("startIsFirstOccurrence") != (bool(occ) and occ[0] == q["start"])):
            bad_occ.append(q["quote"][:30])
    if "para" in q and para_of(q["start"]) != q["para"]:
        bad_para.append(q["quote"][:30])

check("V01 引文逐字命中 text[start:end]==quote（%d 条）" % len(quotes), not bad_off, str(bad_off[:5]))
check("V02 引文 sourceHash 全部一致", not bad_hash, str(bad_hash[:5]))
check("V03 引文全部落在任务区间内", not bad_range, str(bad_range[:5]))
check("V04 出现次数自述（wholeText/InRange/first/isFirst）全对", not bad_occ, str(bad_occ[:5]))
check("V05 para 段号与独立重建的段落表全对", not bad_para, str(bad_para[:5]))

# ── 2. 段落表与覆盖统计独立重算 ──────────────────────────────────────────────
nonempty = [i for i, p in enumerate(PARTS) if p.strip()]
check("C01 段落表：%d 槽 / %d 非空（自述 %d / %d）"
      % (len(PARTS), len(nonempty), cand["source"]["totalParagraphSlots"],
         cand["source"]["nonEmptyParagraphs"]),
      len(PARTS) == cand["source"]["totalParagraphSlots"]
      and len(nonempty) == cand["source"]["nonEmptyParagraphs"])

ivs = sorted({(q["start"], q["end"]) for q in quotes})
covset = set()
for a, b in ivs:
    covset.update(range(a, b))
ns = sum(1 for ch in sl if not ch.isspace())
cov = cand["coverage"]
check("C02 uniqueQuoteIntervals 自述 == 实算（%d）" % len(ivs),
      cov["quoteIntervals"] == [{"start": a, "end": b} for a, b in ivs])
check("C03 quoteUnionCodepoints 自述 == 实算（%d）" % len(covset),
      cov["quoteUnionCodepoints"] == len(covset))
check("C04 两个覆盖率自述 == 实算",
      abs(cov["quoteUnionRatioOfSlice"] - round(len(covset) / len(sl), 4)) < 1e-9
      and cov["nonSpaceCodepoints"] == ns
      and abs(cov["quoteUnionRatioOfNonSpace"] - round(len(covset) / ns, 4)) < 1e-9)

touched = sorted({para_of(a) for a, _ in ivs} | {para_of(b - 1) for _, b in ivs})
touched = [t for t in touched if t is not None and PARTS[t].strip()]
zc = [i for i in range(len(PARTS)) if i not in touched and PARTS[i].strip()]
check("C05 paragraphsTouched 自述 == 实算（%d）" % len(touched),
      cov["paragraphsTouchedByAtLeastOneQuote"] == len(touched))
check("C06 zeroCoveredParagraphs 自述 == 实算（%d 段）" % len(zc),
      cov["zeroCoveredParagraphs"] == zc)

# ── 3. 五栏区间独立性（自述 taskFieldIntervalOverlap=0）──────────────────────
FIELDS = ("objective", "obstacle", "action", "result", "cost")
ov = []
for t in cand["tasks"]:
    iv = [(f, q["start"], q["end"]) for f in FIELDS for q in (t.get(f + "Quotes") or [])]
    for i in range(len(iv)):
        for j in range(i + 1, len(iv)):
            a, b = iv[i], iv[j]
            if a[0] != b[0] and max(a[1], b[1]) < min(a[2], b[2]):
                ov.append((t["id"], a, b))
check("V06 同任务五栏引文区间两两不相交（自述 0 处）", not ov, str(ov[:4]))

nulls = [(t["id"], f) for t in cand["tasks"] for f in FIELDS
         if t.get(f) is None]
check("V07 null 栏 %d 个且每个都有非空 <栏>Note" % len(nulls),
      len(nulls) == cand["machineSelfCheck"]["nullFields"]
      and all((t.get(f + "Note") or "").strip()
              for t in cand["tasks"] for f in FIELDS if t.get(f) is None))

# ── 4. 三态/四态字段合法性 ──────────────────────────────────────────────────
ws = cand["worldSettings"]
ok_inst = all(w.get("institution") in ("declared", "executed", "misunderstood")
              for w in ws if w["kind"] == "rule")
ok_place = all(w.get("placeState") in ("arrived", "mentioned")
               for w in ws if w["kind"] == "place")
ok_item = all(set(w.get("itemStates") or []) <= {"hold", "transfer", "use", "lose"}
              and (w.get("itemStates") or [])
              for w in ws if w["kind"] == "item")
check("V08 worldSettings 三态/四态枚举合法", ok_inst and ok_place and ok_item)

# ── 5. 随机 5 条 quote 的 find 核验（角色契约第 6 条）────────────────────────
random.seed(20261010)
samp = random.sample(quotes, 5)
print("\n随机 5 条 quote 的 find 核验：")
spot_ok = True
for q in samp:
    idx = text.find(q["quote"])
    hit = (idx == q["start"]) and text[q["start"]:q["end"]] == q["quote"]
    spot_ok &= hit
    print("  %s  find=%s declared=%s  %s" % ("命中" if hit else "失配", idx, q["start"],
                                             q["quote"][:38]))
check("V09 随机 5 条 quote 逐字命中且偏移与 find 一致", spot_ok)

# ── 6. 编造检查：候选自述的专名是否都在原文里 ────────────────────────────────
names = set()
for t in cand["tasks"]:
    names.add(t["actor"])
for st in cand["states"]:
    names.add(re.split(r"[（(]", st["who"])[0])
invented = sorted(n for n in names if n and n not in text)
check("V10 候选 actor/who 专名全部在原文中存在（%d 个）" % len(names), not invented, str(invented))

# ── 7. 反向验证：零覆盖但原文明确存在的事实 ─────────────────────────────────
print("\n反向验证（零覆盖的实义段落，供 reverseChecks 引用）：")
REVERSE = [
    (1078381, "而皇后失去了唯一的胞弟，恐怕不会再佛系下去，元景帝后宫势必展开一番女人之间的腥风血雨。"),
    (1080282, "“不错，根基很扎实。”监正点评了一句。"),
    (1081376, "嗯，这是天机师的前置职业"),
    (1081927, "其实如果有准备的情况下，即使从观星楼跳下去，我也不会受伤"),
    (1077115, "许七安从云州复活回来，立了功，封了爵位，与临安和怀庆的关系突飞猛进。"),
]
for off, q in REVERSE:
    covered = bool(set(range(off, off + len(q))) & covset)
    print("  %-7s @%-9d %s" % ("已覆盖" if covered else "零覆盖", off, q[:44]))

# ── 8. 候选 coverage.note 的自我描述是否成立 ────────────────────────────────
SUBSTANTIVE = [31, 32, 33, 83, 112, 89, 43, 47, 54]
mis = [p for p in SUBSTANTIVE if p in zc and PARTS[p].strip()]
check("V11 coverage.note 称零覆盖段主要是『标题/作者话/隔断符/纯过场句』", not mis,
      "反例段号 %s" % mis)

# ── 9. 候选自述的 selfCritique 是否描述了真实产物 ───────────────────────────
sc7 = [s for s in cand["selfCritique"] if s["id"] == "SC07"][0]
tn7 = [t for t in cand["textualNotes"] if t["id"] == "TN07"][0]
claim = "「当面给出理由」" in sc7["risk"] or "当面给出理由" in tn7["note"]
actual = cand["tasks"][0]["action"]
check("V12 SC07/TN07 对 T01.action 的描述与产物一致", not (claim and "当面" not in actual),
      "产物实际写：%r；原文『当面』出现 %d 次" % (actual, sl.count("当面")))

# ── 10. 词级过读检查 ────────────────────────────────────────────────────────
raw = CAND.read_text(encoding="utf-8")
check("V13 T05.cost 的『垫钱』一词有原文依据", not ("垫钱" in raw and sl.count("垫") == 0),
      "原文区间『垫』出现 %d 次；原文用词是『托我买的』" % sl.count("垫"))

NCHECKS = 24
print("\n检查项合计 %d，FAIL %d" % (NCHECKS, len(fails)))
if fails:
    print("FAIL 列表：%s" % fails)
sys.exit(1 if fails else 0)
