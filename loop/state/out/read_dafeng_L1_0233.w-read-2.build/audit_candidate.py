#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L1:0233 独立审计脚本。

与构建脚本**分离**：本脚本不 import content_core，只读产物本身，
从产物里重新取出每条引文并回到原文复核。退出码即判据（0 = 全部成立）。

A1  docs.json sha256 == 任务 sourceHash
A2  切片以单元标题开头、长度与 sourceRange 一致
A3  每条引文 start/end 落在 sourceRange 内
A4  text[start:end] == quote 逐字成立
A5  每条引文的 sourceHash == 整文件 sha256
A6  同一任务内五栏不得共用同一句原文
A7  栏位为 null 时必须带同名 <栏位>Note
A8  cost 不得由「待核／禁令／威胁」充当
A9  causeEdges 每条有 from/to/mechanism/quotes
A10 states: change 有 before/after/anchor；knowledge_gap 有 knownBy/notKnownBy
A11 foreshadows: resolved 必有 payoff；unresolved 必有 payoffNote
A12 worldSettings: kind 对应的三态字段齐全且合法
A13 themeReadings ≤2 且 perspective/support/counter 齐全
A14 没有把话语当事实的结构性痕迹：speechLayerDisclosure 非空且条目可定位
A15 没有语义评审越权声明（semanticReview 必须 not_performed）
A16 自撰文字不伪装成引文（分析文字里不得用 「 」 标记）
A17 覆盖率的自报数字与实际零覆盖清单一致
A18 跨分区复用清单与实际数据一致（不是手写计数）
A19 basis 取值合法
A20 note 里自报的计数必须与产物实际数据一致（本轮靠它抓出两处真漂移）
A21 placeState=mentioned 不得用肯定语气写成到达（否定语境除外）
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
# 默认审计正式产物；阴性对照通过 CL_AUDIT_CAND 指向改坏的临时副本。
CAND = Path(os.environ.get("CL_AUDIT_CAND") or (ROOT / "loop/state/out/read_dafeng_L1_0233.candidate.json"))

EXPECTED_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第四章 请陛下赐死"
FIVE = ("objective", "obstacle", "action", "result", "cost")
VALID_BASIS = {"explicit", "inferred", "derived", "unverified"}

fails: list[str] = []
def chk(cond: bool, label: str, detail: str = "") -> None:
    if not cond:
        fails.append(f"{label}: {detail}")


raw = DOCS.read_bytes()
text = json.loads(raw.decode("utf-8"))[0]["text"]
cand = json.loads(CAND.read_bytes().decode("utf-8"))
S, E = cand["sourceRange"]
SLICE = text[S:E]

# A1 / A2
chk(hashlib.sha256(raw).hexdigest() == EXPECTED_HASH, "A1", "docs.json sha256 不符")
chk(SLICE.startswith(UNIT_HEAD) and E - S == cand["sliceCodepoints"], "A2", "切片边界不符")

# 收集全部引用对象。口径与构建脚本一致：**任何**带 quote/start/end 的对象都算一个
# 定位点，包括条目级引文与它下面用于分开四态的嵌套依据；不早退。
refs: list[tuple[str, dict]] = []
def walk(node, sec: str) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
            refs.append((sec, node))
        for k, v in node.items():
            walk(v, sec)
    elif isinstance(node, list):
        for v in node:
            walk(v, sec)

SECTIONS = ("tasks", "causeEdges", "rejectedEdges", "states", "foreshadows",
            "notForeshadows", "worldSettings", "excludedSettings", "themeReadings",
            "unknowns", "selfCritique", "speechLayerDisclosure", "crossSectionQuoteReuse")
CORE = SECTIONS[:11]          # 内容分区；后面两个是**披露层**，不计入内容计数
for sec in SECTIONS:
    walk(cand.get(sec), sec)

# A3 / A4 / A5
for sec, r in refs:
    a, b, q = r["start"], r["end"], r["quote"]
    chk(isinstance(a, int) and isinstance(b, int) and S <= a < b <= E, "A3",
        f"[{sec}] 引文越界 {a},{b} {q[:24]!r}")
    chk(text[a:b] == q, "A4", f"[{sec}] 逐字不符 {q[:24]!r}")
    chk(r.get("sourceHash") == EXPECTED_HASH, "A5", f"[{sec}] sourceHash 不符 {q[:24]!r}")

# A6 / A7 / A8
for t in cand["tasks"]:
    tid = t["id"]
    seen: dict[str, str] = {}
    for f in FIVE:
        v = t.get(f)
        if v is None:
            chk(bool((t.get(f + "Note") or "").strip()), "A7", f"{tid}.{f} 裸 null 无 Note")
            continue
        for x in v.get("quotes") or []:
            q = x["quote"]
            chk(q not in seen, "A6", f"{tid}: {seen.get(q)} 与 {f} 共用 {q[:26]!r}")
            seen[q] = f
    if t.get("cost") is None:
        cn = t.get("costNote") or ""
        for banned in ("待核", "待验证"):
            chk(banned not in cn, "A8", f"{tid}.costNote 含 {banned}")

# A9
for e in cand["causeEdges"]:
    chk(bool(e.get("from")) and bool(e.get("to")), "A9", f"{e['id']} 缺 from/to")
    chk(bool((e.get("mechanism") or "").strip()), "A9", f"{e['id']} 缺 mechanism")
    chk(bool(e.get("quotes")), "A9", f"{e['id']} 缺 quotes")

# A10
for s in cand["states"]:
    if s["kind"] == "change":
        for f in ("before", "after", "anchor"):
            chk(isinstance(s.get(f), dict) and bool(s[f].get("quotes")), "A10",
                f"{s['id']} 缺 {f}")
    else:
        chk("knownBy" in s and "notKnownBy" in s and bool(s.get("evidence")), "A10",
            f"{s['id']} knowledge_gap 结构不全")

# A11
for f in cand["foreshadows"]:
    if f["status"] == "resolved":
        chk(bool(f.get("payoff")), "A11", f"{f['id']} resolved 无 payoff")
    else:
        chk(bool(f.get("payoffNote")), "A11", f"{f['id']} unresolved 无 payoffNote")

# A12
for w in cand["worldSettings"]:
    k = w["kind"]
    chk(bool(w.get("quote")) and "start" in w and "end" in w, "A12",
        f"{w['id']} 缺条目级引文")
    if k == "rule":
        chk(w.get("institution") in {"declared", "executed", "misunderstood"}, "A12",
            f"{w['id']} institution 非法")
    elif k == "place":
        chk(w.get("placeState") in {"arrived", "mentioned"}, "A12",
            f"{w['id']} placeState 非法")
        if w["placeState"] == "arrived":
            chk(bool(w.get("arrivalEvidence")), "A12", f"{w['id']} arrived 无到达依据")
    elif k == "item":
        st = w.get("itemStates")
        chk(isinstance(st, list) and st and all(
            x in {"hold", "transfer", "use", "lose"} for x in st), "A12",
            f"{w['id']} itemStates 非法")

# A13
th = cand["themeReadings"]
chk(len(th) <= 2, "A13", f"themeReadings {len(th)} 条 > 2")
for x in th:
    for f in ("perspective", "support", "counter"):
        chk(bool(x.get(f)), "A13", f"{x['id']} 缺 {f}")

# A14
sd = cand["speechLayerDisclosure"]
chk(sd.get("speechSpans", 0) > 0, "A14", "speechSpans 为 0（本区间是对话密集章）")
chk(sd.get("checkedCount", 0) > 0 and bool(sd.get("dispositionOfEach")), "A14",
    "话语层处置清单为空")
for d in sd.get("dispositionOfEach") or []:
    chk(text[d["start"]:d["end"]] == d["quote"], "A14", f"话语层条目定位不符 {d['quote'][:22]!r}")

# A15
chk(cand["semanticReview"]["status"] == "not_performed", "A15", "越权声明语义评审完成")

# A16：分析文字（非引用字段）里不得出现 「 」
def scan_own(node, where: str) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node:
            return
        for k, v in node.items():
            scan_own(v, f"{where}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            scan_own(v, f"{where}[{i}]")
    elif isinstance(node, str):
        for tok in ("「", "」"):
            chk(tok not in node, "A16", f"{where}: 自撰文字含 {tok} {node[:34]!r}")
for sec in SECTIONS:
    scan_own(cand.get(sec), sec)

# A17：覆盖率自报与实际一致
paras, off = [], S
for p in SLICE.split("\n"):
    if p.strip():
        paras.append((off, off + len(p), p))
    off += len(p) + 1
qs = {r["quote"] for _, r in refs}
covered = {a for a, b, p in paras if any(q in p for q in qs)}
cov = cand["coverage"]
chk(cov["nonEmptyParagraphs"] == len(paras), "A17",
    f"非空段落自报 {cov['nonEmptyParagraphs']} 实为 {len(paras)}")
chk(cov["zeroCoverageParagraphs"] == len(paras) - len(covered), "A17",
    f"零覆盖自报 {cov['zeroCoverageParagraphs']} 实为 {len(paras)-len(covered)}")
chk(cov["paragraphsTouchedByQuotes"] == len(covered), "A17", "覆盖段落数不符")
# 零覆盖条目必须真的是**零覆盖段落本身**：既要在定位上逐字成立，
# 也要与任何已覆盖段落**不重叠**。
# 这里用区间相交判定，不是拿偏移去比对段落起点集合 —— 后者会让
# 「把某个已覆盖段落内部的一句塞进零覆盖清单」这种改坏漏过去（阴性对照实测踩过）。
covered_spans = [(a, b) for a, b, p in paras if a in covered]
for z in cov["zeroCoverageList"]:
    chk(text[z["start"]:z["end"]] == z["text"], "A17", f"零覆盖清单定位不符 {z['text'][:20]!r}")
    chk(not any(z["start"] < b and a < z["end"] for a, b in covered_spans), "A17",
        f"零覆盖清单里混入已覆盖内容 {z['text'][:20]!r}")

# A18：跨分区复用清单与实际一致
by_q: dict[str, set] = {}
for sec, r in refs:
    if sec in ("speechLayerDisclosure", "crossSectionQuoteReuse"):
        continue
    by_q.setdefault(r["quote"], set()).add(sec)
expect = {q: sorted(s) for q, s in by_q.items() if len(s) > 1}
actual = {d["quote"]: d["sections"] for d in cand["crossSectionQuoteReuse"]}
chk(set(expect) == set(actual), "A18",
    f"复用清单不一致：缺 {len(set(expect)-set(actual))}、多 {len(set(actual)-set(expect))}")
for q in set(expect) & set(actual):
    chk(expect[q] == actual[q], "A18", f"复用分区不符 {q[:24]!r}")

# A19
def basis_scan(node, where: str) -> None:
    if isinstance(node, dict):
        if "basis" in node:
            chk(node["basis"] in VALID_BASIS, "A19", f"{where}: {node['basis']!r}")
        for k, v in node.items():
            basis_scan(v, f"{where}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            basis_scan(v, f"{where}[{i}]")
for sec in SECTIONS:
    basis_scan(cand.get(sec), sec)

# A20：note 里自报的数字必须与产物实际数据一致。
# 这条判据来自本轮的一个真实形态：自报计数是人写的，产物是脚本生成的，
# 两者会各自漂移而没人发现。这里只机械核对「N 条 X」这种可计算的声明。
import re as _re

def _actual_nulls() -> int:
    n = 0
    for t in cand["tasks"]:
        for f in FIVE:
            if t.get(f) is None:
                n += 1
    return n

_claims = [
    ("tasksNote", r"(\d+)\s*条任务", len(cand["tasks"])),
    ("tasksNote", r"(\d+)\s*个栏位", len(cand["tasks"]) * len(FIVE)),
    ("tasksNote", r"其中\s*(\d+)\s*个裸 null", _actual_nulls()),
    ("causeEdgesNote", r"(\d+)\s*条边", len(cand["causeEdges"])),
    ("rejectedEdgesNote", r"(\d+)\s*条被我拒绝的边", len(cand["rejectedEdges"])),
    ("statesNote", r"(\d+)\s*条状态", len(cand["states"])),
    ("statesNote", r"(\d+)\s*条 change",
     sum(1 for s in cand["states"] if s["kind"] == "change")),
    ("statesNote", r"(\d+)\s*条 knowledge_gap",
     sum(1 for s in cand["states"] if s["kind"] == "knowledge_gap")),
    ("foreshadowsNote", r"(\d+)\s*条伏笔", len(cand["foreshadows"])),
    ("foreshadowsNote", r"(\d+)\s*条完整回收",
     sum(1 for f in cand["foreshadows"] if f["status"] == "resolved")),
    ("foreshadowsNote", r"(\d+)\s*条显式 unresolved",
     sum(1 for f in cand["foreshadows"] if f["status"] == "unresolved")),
    ("worldSettingsNote", r"(\d+)\s*条设定", len(cand["worldSettings"])),
    ("worldSettingsNote", r"rule\s*(\d+)\s*条",
     sum(1 for w in cand["worldSettings"] if w["kind"] == "rule")),
    ("worldSettingsNote", r"place\s*(\d+)\s*条",
     sum(1 for w in cand["worldSettings"] if w["kind"] == "place")),
    ("worldSettingsNote", r"item\s*(\d+)\s*条",
     sum(1 for w in cand["worldSettings"] if w["kind"] == "item")),
    ("excludedSettingsNote", r"(\d+)\s*条排除项", len(cand["excludedSettings"])),
    ("themeReadingsNote", r"(\d+)\s*条主题解读", len(cand["themeReadings"])),
    ("unknownsNote", r"(\d+)\s*条 unknowns", len(cand["unknowns"])),
    ("selfCritiqueNote", r"(\d+)\s*条自我批评", len(cand["selfCritique"])),
    ("crossSectionQuoteReuseNote", r"(\d+)\s*条", len(actual)),
]
for key, pat, real in _claims:
    blob = cand.get(key) or ""
    for m in _re.finditer(pat, blob):
        got = int(m.group(1))
        chk(got == real, "A20",
            f"{key}: 自报 {got} 与实际的 {real} 不符（模式 {pat!r}）")

# A21：placeState=mentioned 的条目**不得**把提及写成到达。
# 判据要看**否定语境**：本单元的 p4/p5 正是用「没有任何人抵达」来显式否掉到达，
# 那是正确的写法。第一版只看动词不看否定，把这两条误判成缺陷
# （阴性对照没抓到它，因为它是**误报**而不是漏报；误报与漏报同属判据缺陷）。
ARRIVE_VERBS = ("抵达", "进入", "登上", "驻守", "来到", "前往", "赶到", "进了")
NEGATIONS = ("没有任何人", "无人", "没有人", "未曾", "并非", "不是", "没有出现", "未出现")
for w in cand["worldSettings"]:
    if w["kind"] == "place" and w.get("placeState") == "mentioned":
        ex = w["explain"]
        for v in ARRIVE_VERBS:
            i = ex.find(v)
            while i >= 0:
                window = ex[max(0, i - 12):i]
                if not any(neg in window for neg in NEGATIONS):
                    chk(False, "A21",
                        f"{w['id']}: mentioned 的 explain 用肯定语气出现到达动词 {v!r}")
                i = ex.find(v, i + 1)

if fails:
    print(f"审计未通过：{len(fails)} 条", file=sys.stderr)
    for f in fails[:60]:
        print("  - " + f, file=sys.stderr)
    sys.exit(1)

print(f"审计通过：A1–A21 全部成立")
_core_refs = [r for s, r in refs if s in CORE]
print(f"  内容分区引用实例 {len(_core_refs)} 条 / 不同串 {len({r['quote'] for r in _core_refs})} 个")
print(f"  披露层另有 话语层 {len(sd['dispositionOfEach'])} 条、跨分区复用 {len(actual)} 条（不计入上面）")
print(f"  覆盖 {len(covered)}/{len(paras)} 个非空段落")
print(f"  跨分区复用 {len(actual)} 条（与实际数据一致）")
print(f"  话语层条目 {len(sd['dispositionOfEach'])} 条 / 对白区间 {sd['speechSpans']} 段")
sys.exit(0)
