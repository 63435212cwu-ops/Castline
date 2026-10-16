#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VERIFIER 对抗仪器：在「机器层已复算」之外，做反向验证与一致性检查。

包含（全部现算，不读候选自报值）：
  1. 固定种子随机抽 5 条 quote，逐条 t.find() 与 t[start:end] 双口径核对
  2. 任务内五栏引文是否互不重复（候选 machineSelfCheck.check3 的独立复算）
  3. 『…』记号是否全部逐字、〔…〕记号是否确实不在原文中（记号层独立复算）
  4. 候选正文里出现的、疑似**区间外**的专名/断言（云州案 / 司天监 / 收下 …）在区间内出现几次
  5. 未覆盖片段的清单（配合 uncovered_scan.py）

用法：python3 adversarial_checks.py
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0222.candidate.json"
START, END = 832785, 836013
SEED = 20261015


def walk_quotes(node):
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            yield node
            return
        for v in node.values():
            yield from walk_quotes(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk_quotes(v)


def main() -> int:
    text = json.loads(SRC.read_text("utf-8"))[0]["text"]
    seg = text[START:END]
    cand = json.loads(CAND.read_text("utf-8"))
    allq = list(walk_quotes(cand))

    print("=" * 72)
    print("1) 固定种子随机 5 条 quote：find() 与 t[start:end] 双口径")
    print("=" * 72)
    rng = random.Random(SEED)
    picked = rng.sample(allq, 5)
    ok = 0
    for q in picked:
        s, e, t = q["start"], q["end"], q["quote"]
        slice_hit = text[s:e] == t
        f = text.find(t)
        # 区间内首次出现
        fin = text.find(t, START, END)
        verdict = "逐字命中" if slice_hit else "**不命中**"
        ok += slice_hit
        print("  q[%d:%d] %s" % (s, e, verdict))
        print("      quote=%r" % (t[:48],))
        print("      全文 find()=%s  区间内 find()=%s  声明 start=%d  一致=%s"
              % (f, fin, s, (fin == s)))
        print("      wholeTextOccurrences(声明)=%s 实际=%d   occurrencesInRange(声明)=%s 实际=%d"
              % (q.get("wholeTextOccurrences"), text.count(t),
                 q.get("occurrencesInRange"), seg.count(t)))
    print("  → 5/5 逐字命中" if ok == 5 else "  → %d/5 命中" % ok)

    print()
    print("=" * 72)
    print("2) 任务内五栏引文互不重复（独立复算 check3）")
    print("=" * 72)
    FIVE = ["objective", "obstacle", "action", "result", "cost"]
    conflicts = []
    for t in cand["tasks"]:
        seen = {}
        for f in FIVE:
            blk = t.get(f)
            if not isinstance(blk, dict):
                continue
            for q in blk.get("quotes") or []:
                key = (q["start"], q["end"])
                if key in seen:
                    conflicts.append((t["id"], seen[key], f, key))
                seen[key] = f
    print("  任务内跨栏重复引文：%d 处 %s" % (len(conflicts), conflicts[:5]))

    print()
    print("=" * 72)
    print("3) 记号层：『…』必须逐字；〔…〕与「…」是否真的不在原文")
    print("=" * 72)
    raw = CAND.read_text("utf-8")
    spans = re.findall(r"『([^『』]{1,600})』", raw)
    bad = [x for x in spans if x not in seg]
    print("  『』引文对：%d 对；非逐字：%d %s" % (len(spans), len(bad), [b[:30] for b in bad[:5]]))
    cjk = re.findall(r"「([^「」]{1,600})」", raw)
    print("  「」中文引号对（政策禁用）：%d" % len(cjk))
    print("  〔 在 docs[0].text 全文出现次数：%d" % text.count("〔"))
    print("  〔…〕在候选里的对数（应为转述记号，不是原文）：%d" % len(re.findall(r"〔[^〔〕]{1,600}〕", raw)))

    print()
    print("=" * 72)
    print("4) 候选正文里疑似**区间外**的专名/断言，在区间内出现次数")
    print("=" * 72)
    for term in ["云州案", "司天监", "收下", "接收", "收受", "笑纳", "接下", "驿站",
                 "新任当家", "逼王", "杨千幻", "齐党", "宋廷风", "杨川南", "打更人",
                 "虎贲卫", "铜锣", "银锣", "术士", "儒家", "炼神境", "练气境", "炼精境"]:
        print("  %-6s 区间内 %2d 次 | 全文 %4d 次" % (term, seg.count(term), text.count(term)))

    print()
    print("=" * 72)
    print("5) K1 时间窗核对：K1.what 声称『麻袋摘下之前』，其 whoKnows 依据的偏移")
    print("=" * 72)
    k1 = [x for x in cand["knowledgeDiffs"] if x.get("id") == "K1"][0]
    print("  K1.what = %s" % k1["what"])
    for q in k1["quotes"]:
        print("  依据 q[%d] %r" % (q["start"], q["quote"][:44]))
    bad_offset = 0
    for x in cand["knowledgeDiffs"]:
        if x.get("id") != "K1":
            continue
        bad_offset = len(x.get("whoKnows") or [])
    print("  whoKnows 条数 = %d（note 声称『两个人名』）" % bad_offset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
