#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""角标纪律纠正（程序化，逐条可复算）。

判据（由 L2:0230 的独立复核抓出，本轮做成硬门）：
  · 『…』/「…」跨度必须是**本单元切片**的逐字子串 —— 不是「全书里找得到」就算过。
  · 〔…〕必须是**本单元切片**里出现 0 次的、我自己的措辞。

本脚本按上述判据扫描内容层源码里的所有角标跨度，做两类改写并报告：
  A. 逐字的 〔x〕 → 『x』
  B. 非逐字的 『x』 → 〔x〕
通用词（如〔是〕〔无〕〔知道〕）不自动改写 —— 自动把它们变成『是』虽然合法但读起来像噪声，
所以列入 GENERIC 后**必须人工改写**，脚本会把它们单独报出来并以非零码提示。

可复现：
  python3 -B -s loop/state/out/read_dafeng_L2_0238.w-read-4.build/fix_brackets.py --check
  python3 -B -s loop/state/out/read_dafeng_L2_0238.w-read-4.build/fix_brackets.py --write
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FILES = [HERE / "content_spec_a.py", HERE / "content_spec_b.py"]
SOURCE_REL = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
RANGE = (948891, 956444)

VERBATIM_RE = re.compile(r"[『「]([^『』「」\n]{1,120})[』」]")
MYWORD_RE = re.compile(r"〔([^〔〕\n]{1,120})〕")

# 通用词：出现在原文里但语义上不该被当成「引用」；
# 遇到它们时不自动改写，而是报出来让人工改句子。
GENERIC = {"是", "无", "有", "知道", "知道？", "不说", "后果", "谁干的", "实话"}


def load_slice():
    doc = json.loads((ROOT / SOURCE_REL).read_text(encoding="utf-8"))
    return doc[0]["text"][RANGE[0]:RANGE[1]]


def main():
    write = "--write" in sys.argv
    sl = load_slice()
    changed = {"verbatim_myword": 0, "myword_verbatim": 0}
    manual = []
    report = []
    for path in FILES:
        s = path.read_text(encoding="utf-8")

        def to_verbatim(m):
            inner = m.group(1)
            if inner in sl and inner not in GENERIC:
                changed["myword_verbatim"] += 1
                report.append(("〔→『", path.name, inner))
                return "『%s』" % inner
            if inner in sl:
                manual.append((path.name, "〔…〕里是原文串（通用词，需人工改写）", inner))
            return m.group(0)

        def to_myword(m):
            inner = m.group(1)
            if inner not in sl:
                changed["verbatim_myword"] += 1
                report.append(("『→〔", path.name, inner))
                return "〔%s〕" % inner
            return m.group(0)

        s2 = MYWORD_RE.sub(to_verbatim, s)
        s2 = VERBATIM_RE.sub(to_myword, s2)
        if write and s2 != s:
            path.write_text(s2, encoding="utf-8")

    for kind, fn, inner in report:
        print("%s %s | %s" % (kind, fn, inner))
    print("\n自动改写：逐字〔〕→『』 %d 处；非逐字『』→〔〕 %d 处"
          % (changed["myword_verbatim"], changed["verbatim_myword"]))
    if manual:
        print("\n需要人工改写（通用词，不自动替换）：%d 处" % len(manual), file=sys.stderr)
        for fn, why, inner in manual:
            print("  - %s | %s | %r" % (fn, why, inner), file=sys.stderr)
    print("模式：%s" % ("已写盘" if write else "仅检查（--check）"))
    return 1 if manual else 0


if __name__ == "__main__":
    sys.exit(main())
