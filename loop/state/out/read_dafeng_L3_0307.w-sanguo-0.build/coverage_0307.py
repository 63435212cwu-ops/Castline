#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反向验证：候选**没有覆盖**的原文事实有哪些？

只查「已写项对不对」是结构性地发现不了遗漏的（计划100 最有价值的教训）。
本脚本换一个方向：把切片切成自然段，逐段问「这段有没有被候选的任何引文覆盖」，
把**未被覆盖的段落**全部列出来，再由人逐段判断是真遗漏还是合理排除。

用法：
  python3 -B -s loop/state/out/read_dafeng_L3_0307.w-sanguo-0.build/coverage_0307.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0307.candidate.json"
REPORT = Path(__file__).resolve().parent / "coverage_report.json"

START, END = 1366953, 1373655
text = json.loads(DOCS.read_text("utf-8"))[0]["text"]
cand = json.loads(CAND.read_text("utf-8"))

quotes: list[dict] = []


def walk(node) -> None:
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            quotes.append(node)
        for v in node.values():
            walk(v)
    elif isinstance(node, list):
        for v in node:
            walk(v)


walk(cand)

# 段落切分（与 build 期的 paras.txt 同一口径：以空行分段）
paras: list[tuple[int, int, str]] = []
i = 0
sl = text[START:END]
while i < len(sl):
    j = sl.find("\n\n", i)
    if j == -1:
        j = len(sl)
    paras.append((START + i, START + j, sl[i:j]))
    i = j + 2

author_range = (cand.get("authorRegion") or {}).get("range") or [END, END]

uncovered = []
for n, (a, b, body) in enumerate(paras):
    if a >= author_range[0]:
        continue  # 作者附言区单独处理，不作为叙事内容
    hit = [q["key"] for q in quotes if not (q["end"] <= a or q["start"] >= b)]
    if not hit:
        uncovered.append({"para": n, "range": [a, b], "text": body.strip()[:80]})

# 哪些段只被「非叙事分区」（世界设定/主题）引到，没有进 tasks/causeEdges/states
core_keys = set()
for layer in ("tasks", "causeEdges", "states", "foreshadows", "knowledgeGaps"):
    for node in cand.get(layer, []):
        blob = json.dumps(node, ensure_ascii=False)
        for q in quotes:
            if q["key"] in blob:
                core_keys.add(q["key"])

weak = []
for n, (a, b, body) in enumerate(paras):
    if a >= author_range[0]:
        continue
    hit = [q["key"] for q in quotes if not (q["end"] <= a or q["start"] >= b)]
    if hit and not any(k in core_keys for k in hit):
        weak.append({"para": n, "range": [a, b], "text": body.strip()[:80], "onlyIn": hit})

report = {
    "sliceRange": [START, END],
    "paragraphCount": len(paras),
    "narrativeParagraphs": len([1 for a, b, _ in paras if a < author_range[0]]),
    "coveredParagraphs": len([1 for a, b, _ in paras if a < author_range[0]
                              and any(not (q["end"] <= a or q["start"] >= b) for q in quotes)]),
    "uncoveredParagraphs": uncovered,
    "coveredOnlyByNonNarrativeSections": weak,
}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")

print("叙事段 %d / 被引文覆盖 %d / 未覆盖 %d"
      % (report["narrativeParagraphs"], report["coveredParagraphs"], len(uncovered)))
for u in uncovered:
    print("  [%04d] %s" % (u["para"], u["text"]))
print("--- 只被非叙事分区（世界设定/主题）覆盖的段：%d" % len(weak))
for w in weak:
    print("  [%04d] %s  ← %s" % (w["para"], w["text"], ",".join(w["onlyIn"])))
