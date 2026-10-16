#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 content_core.py 里**不是原文逐字**的「」片段改成〔〕。

为什么要这一步（本单元的一处真实自纠）：
  B18 判据是「note 里「」括起、长度 >=5 的片段必须能在切片里逐字找到」。
  第一次构建时有 110 个片段不命中 —— 它们全都是**我自己的措辞**
  （例如「夺舍真的发生了」「他因此改口」），却和真正引原文的「」用了同一对括号。
  这会让复核者无法区分「我引了原文」与「我在说自己的话」，正是契约里
  「引用定位正确 ≠ 语义已核验」要防的形态。

约定（写进候选的 quotePolicy）：
  「…」 = 原文逐字，必须能在 docs[0].text[910067,916516) 里 find 到
  〔…〕 = 我自己的措辞／我给某条边起的名字，不声称是原文
  『…』 = 原文里的引号嵌套（保留原文写法）

本脚本幂等：改完之后重跑不会再有可改的片段。
"""
import json
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parents[3]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CORE = BUILD / "content_core.py"
START, END = 910067, 916516


def main():
    text = json.loads(DOCS.read_bytes())[0]["text"]
    seg = text[START:END]
    src = CORE.read_text(encoding="utf-8")

    # 只扫 content_core.py 里的普通字符串字面量即可：本文件不用 f-string 拼「」
    frags = sorted({m.group(1) for m in re.finditer(r"「([^」]+)」", src)})
    bad = [f for f in frags if len(f) >= 5 and f not in seg]
    n = 0
    for f in bad:
        old = "「%s」" % f
        new = "〔%s〕" % f
        c = src.count(old)
        src = src.replace(old, new)
        n += c
    if n:
        CORE.write_text(src, encoding="utf-8")
    print("改写的「」片段：%d 处 / %d 个不同片段" % (n, len(bad)))
    # 复验
    left = [f for f in {m.group(1) for m in re.finditer(r"「([^」]+)」", src)}
            if len(f) >= 5 and f not in seg]
    if left:
        print("[FAIL] 仍有不可回查片段：%r" % (left[:5],), file=sys.stderr)
        return 1
    print("OK content_core.py 里的「」片段全部可在切片内逐字回查")
    return 0


if __name__ == "__main__":
    sys.exit(main())
