#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify:dafeng:L3:0251 第二轮独立复核 · 反向验证探针（w-verify-1 自写）。

与 audit.py 分开：这里做的是**语义层**的对抗性检查 ——
  * 更细的句子切分（把「.......」也当分隔），重算零覆盖；
  * 任意绝对偏移 → 哪些引文覆盖它（用来判断某句是否真的有引文依据）；
  * 候选自由文本里出现、但原文没有的**断言**（章号等）；
  * 引文与其所挂命题是否对应（逐条把 claim 与 quote 对读的辅助）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0251.candidate.json"
START, END = 1032194, 1038254

text = json.loads(DOCS.read_text("utf-8"))[0]["text"]
cand = json.loads(CAND.read_text("utf-8"))
sl = text[START:END]


def walk_quotes(node, path="$"):
    if isinstance(node, dict):
        if "quote" in node and isinstance(node["quote"], str) and "start" in node:
            yield path, node
        for k, v in node.items():
            yield from walk_quotes(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quotes(v, "%s[%d]" % (path, i))


QUOTES = list(walk_quotes(cand))
IVS = sorted({(q["start"], q["end"]) for _, q in QUOTES})


def covering(s: int, e: int):
    return [(q["start"], q["end"], p) for p, q in QUOTES if q["start"] < e and s < q["end"]]


def where(tok: str):
    out = []
    for p, q in QUOTES:
        if tok in q["quote"]:
            out.append((p, q["start"], q["quote"][:50]))
    return out


print("=" * 100)
print("A. 细分句零覆盖（分隔符 = 。！？ 以及连续 ≥3 个点）")
paras = []
for m in re.finditer(r"[^\n]+", sl):
    if m.group(0).strip():
        paras.append((len(paras) + 1, START + m.start(), m.group(0)))

zero = []
for idx, a, raw in paras:
    for sm in re.finditer(r"[^。！？.]*[。！？]|[^。！？.]{4,}(?=\.{3,})|[^。！？.]{4,}$", raw):
        core = sm.group(0).strip()
        if len(re.sub(r"\s", "", core)) < 10:
            continue
        gs, ge = a + sm.start(), a + sm.end()
        if covering(gs, ge):
            continue
        zero.append({"para": idx, "start": gs, "end": ge, "text": core})
print("细分句零覆盖：%d 条" % len(zero))
for z in zero:
    print("   [P%03d %d,%d) %s" % (z["para"], z["start"], z["end"], z["text"][:110]))

print("=" * 100)
print("B. 关键短语：是否被引文覆盖 / 是否只在自由文本里出现")
for tok in ["三十七年才刚开始", "已经死了，死无对证", "救了黄小柔一命", "没见过元景帝",
            "元景二十八年", "不学无术", "纵情声色", "第十八章", "支走四皇子",
            "门口的侍卫不敢拦", "对我们调查的结果", "通道只有这一条", "唯一"]:
    cov = [c for c in covering(*(lambda f: (f, f + len(tok)))(text.find(tok)))
           if text.find(tok) >= 0]
    hits = where(tok)
    print("%-16s 原文出现=%-3d 引文命中=%-2d 自由文本提及=%s"
          % (tok, text.count(tok), len(hits),
             "是" if tok in json.dumps(cand, ensure_ascii=False) and not hits else
             ("是(含引文)" if tok in json.dumps(cand, ensure_ascii=False) else "否")))

print("=" * 100)
print("C. 候选里所有对【区间外】的指称（章号 / 区间外事件）")
blob = json.dumps(cand, ensure_ascii=False)
for m in re.finditer(r"第[一二三四五六七八九十百]+章", blob):
    s = max(0, m.start() - 90)
    print("   ...", blob[s:m.end() + 90].replace("\\n", " "))

print("=" * 100)
print("D. V08.extraQuotes 与 V08 命题的相关性")
v08 = [x for x in cand["speechAsClueNotFact"] if x["id"] == "V08"][0]
print("V08.quote          :", v08["quote"]["quote"])
print("V08.whatItProves   :", v08["whatItProves"][:90])
for q in v08.get("extraQuotes") or []:
    print("   extra [%d,%d) %s" % (q["start"], q["end"], q["quote"]))
print("其它 V 条目是否也有 extraQuotes：",
      {x["id"]: bool(x.get("extraQuotes")) for x in cand["speechAsClueNotFact"]})

print("=" * 100)
print("E. K01 的 whoKnows 与 P134 原文的对撞")
k01 = [x for x in cand["knowledgeGaps"] if x["id"] == "K01"][0]
print("K01.whoKnows   :", k01["whoKnows"])
print("K01.whoDoesNot :", k01["whoDoesNot"])
for tok, at in [("救了黄小柔一命", 1038003), ("黄小柔已经死了，死无对证", 1038140)]:
    print("   原文[%d] %s" % (at, text[at:at + len(tok)]))
print("   T13.objectiveQuotes:", [q["quote"][:40] for q in cand["tasks"][12]["objectiveQuotes"]])

print("=" * 100)
print("F. W01.explain 的排他性措辞")
w01 = cand["worldSettings"][0]
print(w01["explain"][:400])

print("=" * 100)
print("G. S04.before 的 claim 与唯一引文")
s04 = cand["states"][3]
print("before      :", s04["before"])
print("beforeQuotes:", [q["quote"] for q in s04["beforeQuotes"]])

sys.exit(0)
