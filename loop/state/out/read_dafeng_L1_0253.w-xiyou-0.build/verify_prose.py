# -*- coding: utf-8 -*-
"""散文层审计（引用之外的第二种错误）。

为什么需要它：候选里除了结构化的 `quotes[]`，散文（text/note/why/explain…）
里还大量使用「……」来复述原文。**这一层不经过 quoteRef 校验**——
0249 的独立复核正是靠人读散文才发现「四个字」这类措辞错误，
纯引用层 188/188 全过也查不出来。

本脚本把散文里所有「……」片段抽出来，逐条要求它在**本单元切片内**逐字命中。
例外（白名单）另行列出并给出理由，不允许静默放过。

同时复查少量**可量化的断言**（出现次数、篇幅），因为它们最容易写飘。
"""
import json
import os
import re
import sys

ROOT = "/Users/carmen/Desktop/星系"
DOCS = ROOT + "/data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT + "/loop/state/out/read_dafeng_L1_0253.candidate.json"
TASK = ROOT + "/loop/state/runs/task-read_dafeng_L1_0253.json"

text = json.load(open(DOCS, encoding="utf-8"))[0]["text"]
S, E = json.load(open(TASK, encoding="utf-8"))["sourceRange"]
slice_txt = text[S:E]
cand = json.load(open(CAND, encoding="utf-8"))

# ── 约定（本候选遵守，并由本脚本强制）────────────────────────────────
#   「…」 = **逐字原文**。必须在本单元切片内 find 得到；
#           允许用 …… 表示截断，截断后每一段都必须逐字命中。
#   『…』 = **我自己的归纳、术语、字段名或转述**，不要求逐字。
# 这条约定是 0253 这一轮踩出来的：初版把两者混用同一种引号，
# 于是「殿下来都来了」（原文是「来都来了」）、「不许置喙皇后娘娘」
# （原文是「不得置喙皇后娘娘」）、「三天」（原文无此词）这类
# **误引**在纯 quoteRef 校验里完全隐身 —— quoteRef 全是结构化字段，
# 散文里的复述不经过它。所以散文层必须单独有判据。
problems = []
checked = 0
skipped = []


def audit_string(s, path):
    global checked
    for m in re.finditer(r"「([^」]*)」", s):
        frag = m.group(1)
        if not frag or not frag.strip():
            continue
        parts = [p for p in re.split(r"…+|\.\.\.\.+", frag) if p.strip()]
        for p in parts:
            p = p.strip()
            checked += 1
            if slice_txt.find(p) < 0:
                problems.append("PROSE %s 的「%s」不是逐字原文（约定：「」= 逐字，"
                                "自造词请用『』）" % (path, p[:50]))


def walk(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, path + "." + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + "[%d]" % i)
    elif isinstance(node, str):
        audit_string(node, path)


walk(cand, "cand")

# ── 可量化断言复查 ─────────────────────────────────────────────────────
def count(tok):
    n, p = 0, slice_txt.find(tok)
    while p >= 0:
        n += 1
        p = slice_txt.find(tok, p + 1)
    return n


quant = []
# n1 声称「许宁宴」出现 1 次
quant.append(("n1 许宁宴出现次数", count("许宁宴"), 1))
# n5 《春庭月》出现 1 次
quant.append(("n5 春庭月出现次数", count("《春庭月》"), 1))
# n3 云鹿书院 1 次
quant.append(("n3 云鹿书院出现次数", count("云鹿书院"), 1))
# f1 绿豆糕至少 3 次
gm = count("绿豆糕")
quant.append(("f1 绿豆糕出现次数>=3", gm, ">=3"))
# n6 作者附言段数（PS 2 段 + 更新公告区）
ps = count("PS：")
quant.append(("n6 PS 段数", ps, 2))
# u13 正文长度：到第一个 PS 为止
body = len(slice_txt[:slice_txt.find("PS：")])
quant.append(("u13 正文 codepoint", body, 6460))
quant.append(("切片总长", len(slice_txt), 6758))

# 候选自己声明的出现次数（notForeshadows[].occurrences）也要对账 ——
# 声明与实测不符就是「工作量/数字造假」这一类缺陷，必须由脚本抓。
for n in cand.get("notForeshadows", []):
    qtok = (n.get("quote") or {}).get("quote", "")
    # 从 why_not 里抽「全文实测出现 N 次」这类自陈
    mm = re.search(r"全文实测出现\s*(\d+)\s*次", n.get("why_not", ""))
    declared = n.get("occurrences")
    if mm and declared is not None:
        said = int(mm.group(1))
        if said != declared:
            problems.append("QUANT notForeshadows[%s] 散文说 %d 次、字段写 %s 次"
                            % (n.get("id"), said, declared))
    # 字段声明的次数与实际命中比对：用**该条自己给的引文**做锚定不可靠，
    # 所以只对可枚举的短词做核对 —— 这里核 n1/n3/n5 三个已确证的单次项。
    KEY = {"n1": "许宁宴", "n3": "云鹿书院", "n5": "《春庭月》"}
    if n.get("id") in KEY and declared is not None:
        real = count(KEY[n["id"]])
        if real != declared:
            problems.append("QUANT notForeshadows[%s].occurrences 声明 %s，实测 %d"
                            % (n.get("id"), declared, real))

for label, actual, expect in quant:
    ok = (actual >= 3) if expect == ">=3" else (actual == expect)
    print("  [%s] %-26s 实测=%s 期望=%s" % ("OK" if ok else "FAIL", label, actual, expect))
    if not ok:
        problems.append("QUANT %s 实测 %s != 期望 %s" % (label, actual, expect))

blob = json.dumps(cand, ensure_ascii=False)
n_own = len(re.findall(r"『[^』]*』", blob))
print("\n=== 散文层审计（read:dafeng:L1:0253）===")
print("  逐段核查的「」（= 必须逐字的原文引述）片段 =", checked)
print("  『』（= 我自己的归纳/术语，不要求逐字）片段 =", n_own)
if problems:
    print("\n失败 %d 条：" % len(problems))
    for p in problems:
        print("  [FAIL] " + p)
    sys.exit(1)
print("  全部散文引述在本单元切片内逐字命中；量化断言与实测一致。")
sys.exit(0)
