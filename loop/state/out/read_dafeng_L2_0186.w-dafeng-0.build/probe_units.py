#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：把本单元切片切成「段 / 句 / 分句」三级单元，打印绝对 codepoint 偏移。

偏移口径：docs[0].text 全文绝对 codepoint（0-based，左闭右开），**不是**相对切片。
本脚本只读源文件、只打印，不写任何东西。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
S, E = 676201, 679978


def main() -> int:
    text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    seg = text[S:E]
    print("slice starts with unit head:", seg.startswith("第一百八十六章 失之交臂"))
    print("slice len:", len(seg))
    # 段落：以 \n\n 分隔的非空块
    paras = []
    for m in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", seg):
        raw = m.group(0)
        if raw.strip():
            paras.append((S + m.start(), S + m.end(), raw))
    print("nonEmptyParagraphs:", len(paras))
    for i, (a, b, raw) in enumerate(paras, 1):
        body = raw.strip()
        # 段内去掉行首缩进后的正文偏移
        lead = len(raw) - len(raw.lstrip())
        s0 = a + lead
        print("P%03d [%d,%d) len=%d %s" % (i, s0, s0 + len(body), len(body), body[:70].replace("\n", "\\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
