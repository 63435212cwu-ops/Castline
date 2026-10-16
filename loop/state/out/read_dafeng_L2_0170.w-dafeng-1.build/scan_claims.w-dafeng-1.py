#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_claims：扫候选**散文层**里可用原文逐字证伪的断言。

0162/0166 被判 partial 的根因是**散文层计数/措辞错误而结构化字段全对**，
所以单列此脚本：对候选里出现的「出现 N 次 / 只出现一次 / 只出现在…」这类
计数断言，逐个用 docs[0].text 的切片独立复算。

A 规则：术语在**本区间**内的出现次数
B 规则：原文措辞（候选声称「叙述直述」的串必须 find 得到）
C 规则：段号归属（候选给的 para 与独立枚举一致 —— 由 verify_candidate 覆盖）
D 规则：源文本没有的字符
"""
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
TEXT = json.loads((ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json").read_bytes().decode("utf-8"))[0]["text"]
START, END = 611230, 615103
SLICE = TEXT[START:END]
CAND = json.loads((ROOT / "loop/state/out/read_dafeng_L2_0170.candidate.json").read_text(encoding="utf-8"))

PARAS = []
_pos = START
for _line in TEXT[START:END].split("\n"):
    _s = _line.strip()
    if _s:
        _lead = len(_line) - len(_line.lstrip())
        PARAS.append((len(PARAS) + 1, _pos + _lead, _s))
    _pos += len(_line) + 1

def where(term):
    """返回 term 在切片内出现的段号列表（全书计数另给）。"""
    out = []
    start = START
    while True:
        i = TEXT.find(term, start, END)
        if i < 0:
            break
        p = None
        for pi, ps, ptxt in PARAS:
            if ps <= i < ps + len(ptxt) + 2:
                p = pi
                break
        out.append((p, i))
        start = i + 1
    return out

A = []   # 计数断言
B = []   # 措辞断言
D = []   # 禁用字符

# ── A：逐条列出的计数断言（人读候选后登记，脚本复算）──────────────
# (名字, 术语, 候选里的声称, 脚本判定的期望区间内次数)
A_CLAIMS = [
    ("NF1 要还的", "要还的", "全区间只出现这一次", 1),
    ("NF2 匾额", "匾额", "区间内出现 2 次", 2),
    ("NF3 木箱", "木箱", "只作为取书的容器出现一次", 1),
    ("NF4 天地一刀斩", "天地一刀斩", "天地一刀斩 2 次", 2),
    ("NF4 炼神境", "炼神境", "炼神境 1 次", 1),
    ("NF4 观想图", "观想图", "观想图 2 次", 2),
    ("NF5 教坊司", "教坊司", "只在地名意义上出现一次", 1),
    ("W-place-4 八卦台", "八卦台", "全区间只出现这一次", 1),
    ("NW1 天地一刀斩", "天地一刀斩", "在本区间出现 2 次", 2),
    ("NW2 炼神境", "炼神境", "炼神境只出现在恒远的问句里", 1),
    ("U10 许白嫖", "许白嫖", "区间内只出现在许七安自己的心念里", 1),
    ("U11 恒慧", "恒慧", "只在恒远的自述里出现一次", 1),
    ("U14 力速双D", "力速双D", "区间内只此一次", 1),
    ("狗开口", "福如....东海，大吉....大利。", "区间内该狗只开口一次", 1),
    ("V6 只会说这八个字", "他只会说这八个字。", "区间内该狗只开口一次", 1),
]
DEFECTS = []
for name, term, claim, expect in A_CLAIMS:
    hits = where(term)
    rec = {"id": name, "term": term, "claim": claim, "expected": expect,
           "sliceCount": len(hits), "wholeBookCount": TEXT.count(term),
           "paras": [p for p, _ in hits]}
    rec["verdict"] = "pass" if len(hits) == expect else "FAIL"
    if rec["verdict"] == "FAIL":
        DEFECTS.append("%s：声称 %r，实测区间内 %d 次" % (name, claim, len(hits)))
    A.append(rec)

# ── B：候选声称是原文直述的关键串，必须 find 得到 ──────────────────
B_TERMS = [
    "他只会说这八个字。", "要还的", "匾额", "天地一刀斩", "教坊司", "八卦台",
    "福如....东海，大吉....大利。", "力速双D", "许白嫖", "恒慧", "炼神境", "观想图",
]
for term in B_TERMS:
    B.append({"term": term, "inSlice": SLICE.count(term), "inWholeBook": TEXT.count(term)})

# ── D：源文本没有的字符 ────────────────────────────────────────────
cand_text = (ROOT / "loop/state/out/read_dafeng_L2_0170.candidate.json").read_text(encoding="utf-8")
for ch in ("『", "』", "「", "」", "…"):
    D.append({"char": ch, "inCandidate": cand_text.count(ch), "inSlice": SLICE.count(ch)})

# ── 输出 ───────────────────────────────────────────────────────────
print("=== A 计数断言（区间内独立复算）===")
for a in A:
    flag = "OK " if a["sliceCount"] >= 1 else "ZERO"
    print("%-4s %-22s slice=%-3d book=%-5d paras=%-14s  声称：%s"
          % (flag, a["id"], a["sliceCount"], a["wholeBookCount"], a["paras"], a["claim"]))
print()
print("=== B 原文措辞 ===")
for b in B:
    print("inSlice=%-3d book=%-5d  %s" % (b["inSlice"], b["inWholeBook"], b["term"][:40]))
print()
print("=== D 禁用字符 ===")
for d in D:
    print("char=%s candidate=%d slice=%d" % (d["char"], d["inCandidate"], d["inSlice"]))

for b in B:
    if b["inSlice"] == 0:
        DEFECTS.append("措辞断言在区间内找不到：%r" % b["term"])
for d in D:
    if d["inCandidate"]:
        DEFECTS.append("候选出现源文本没有的字符 %s × %d" % (d["char"], d["inCandidate"]))

out = ROOT / "loop/state/out/read_dafeng_L2_0170.w-dafeng-1.build/scan_claims.w-dafeng-1.json"
out.write_text(json.dumps({"A_countClaims": A, "B_wording": B, "D_forbiddenChars": D,
                           "defects": DEFECTS, "verdict": "pass" if not DEFECTS else "fail"},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("\nDEFECTS:", len(DEFECTS))
for d in DEFECTS:
    print("  -", d)
print("写入", out)
sys.exit(0 if not DEFECTS else 1)
