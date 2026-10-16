#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把内容层里的角标跨度按「逐字/非逐字」纠正到正确形态（w-xiyou-0）。

背景（这是上一轮真被独立复核判 FAIL 的同一形态，C12：331 处非逐字跨度）：
  · 『…』/「…」**只能**用于原文逐字跨度（docs[0].text 里能 find 到）；
  · 〔…〕**只能**用于我自己的措辞（原文里出现 0 次）。
本脚本按这两条判据逐串纠正，并把每一处改动打印出来（可复核、可回滚）。

用法：
  python3 -B -s fix_brackets.py            # 只报告
  python3 -B -s fix_brackets.py --write    # 就地改（仅改 content_a.py / content_b.py）
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
FILES = [HERE / "content_a.py", HERE / "content_b.py"]

VERBATIM_RE = re.compile(r"[『「]([^『』「」\n]{1,120})[』」]")
MYWORD_RE = re.compile(r"〔([^〔〕\n]{1,120})〕")
# 约定说明行（docstring 里的元语法，如「『…』= 原文逐字跨度」）不是内容，跳过。
# 上一版没跳，于是把说明文字也当成跨度去改 —— 与「只扫内容、漏掉元数据」是同一类错误的镜像。
META_MARKERS = ("『…』", "〔…〕")


def _process_line(line, text):
    if any(mk in line for mk in META_MARKERS):
        return line, [], []
    opened = [m.group(1) for m in VERBATIM_RE.finditer(line) if m.group(1) not in text]
    new = VERBATIM_RE.sub(lambda m: "〔" + m.group(1) + "〕" if m.group(1) not in text else m.group(0), line)
    closed = [m.group(1) for m in MYWORD_RE.finditer(new) if m.group(1) in text]
    new = MYWORD_RE.sub(lambda m: "『" + m.group(1) + "』" if m.group(1) in text else m.group(0), new)
    return new, opened, closed


def main():
    write = "--write" in sys.argv
    text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    total_open = total_close = 0
    for f in FILES:
        src = f.read_text(encoding="utf-8")
        lines = src.split("\n")
        out_lines = []
        hits_open, hits_close = [], []
        for line in lines:
            new, o, c = _process_line(line, text)
            out_lines.append(new)
            hits_open += o
            hits_close += c
        new_src = "\n".join(out_lines)

        print("== %s" % f.name)
        print("   非逐字『』/「」→〔〕：%d 处" % len(hits_open))
        for h in hits_open:
            print("      · %s" % h[:60])
        print("   逐字〔〕→『』：%d 处" % len(hits_close))
        for h in hits_close:
            print("      · %s" % h[:60])
        total_open += len(hits_open)
        total_close += len(hits_close)
        if write and new_src != src:
            f.write_text(new_src, encoding="utf-8")
            print("   已写回")
    # 复查（同样跳过约定说明行）
    bad = good = 0
    for f in FILES:
        for line in f.read_text(encoding="utf-8").split("\n"):
            if any(mk in line for mk in META_MARKERS):
                continue
            bad += sum(1 for m in VERBATIM_RE.finditer(line) if m.group(1) not in text)
            good += sum(1 for m in MYWORD_RE.finditer(line) if m.group(1) in text)
    print("== 复查：非逐字『』/「」=%d，误标〔〕=%d" % (bad, good))
    return 1 if (bad or good) else 0


if __name__ == "__main__":
    sys.exit(main())
