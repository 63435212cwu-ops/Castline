# -*- coding: utf-8 -*-
"""引文探针：在**不产出候选**的前提下，把 quotes_0291.py 里的每条引文在本单元切片内定位一遍，
报出四类问题，供人工回原文核对后再修 content：

  1. not-found      —— 切片内 find 不到（抄错字 / 点串个数不对 / 标点全半角不一致）
  2. ambiguous      —— 切片内出现 >1 次且没有在 OCC 里登记取第几次
  3. para-mismatch  —— label 声明的段号与实际定位到的段号不一致（occ 选错的典型症状）
  4. occ-out-of-range —— OCC 给的序号超出实际出现次数

用法：python3 loop/state/out/read_dafeng_L3_0291.w-read-2.build/probe_quotes.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)

import quotes_0291 as Q  # noqa: E402

DOCS = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
START, END = 1254012, 1263192

TEXT = json.load(open(DOCS, encoding="utf-8"))[0]["text"]
SLICE = TEXT[START:END]


def para_index(offset):
    return SLICE.count("\n", 0, offset - START)


def main():
    bad = 0
    for label in sorted(Q.QUOTES):
        s = Q.QUOTES[label]
        hits = []
        cur = 0
        while True:
            k = SLICE.find(s, cur)
            if k < 0:
                break
            hits.append(k)
            cur = k + 1
        if not hits:
            print("[not-found]     %-18s %r" % (label, s[:40]))
            bad += 1
            continue
        occ = Q.OCC.get(label, 0)
        if len(hits) > 1 and label not in Q.OCC:
            print("[ambiguous]     %-18s 出现 %d 次，未登记 OCC：%s"
                  % (label, len(hits), [START + h for h in hits[:6]]))
            bad += 1
            continue
        if occ >= len(hits):
            print("[occ-range]     %-18s OCC=%d 但只出现 %d 次" % (label, occ, len(hits)))
            bad += 1
            continue
        k = hits[occ]
        start, end = START + k, START + k + len(s)
        if TEXT[start:end] != s:
            print("[verbatim-fail] %-18s text[%d:%d] != quote" % (label, start, end))
            bad += 1
            continue
        m = re.match(r"^p(\d{3})_", label)
        para = para_index(start)
        if m and int(m.group(1)) != para:
            print("[para-mismatch] %-18s label 说 P%s，实际 P%03d（occ=%d，%d 次出现）"
                  % (label, m.group(1), para, occ, len(hits)))
            bad += 1
            continue
        flag = "" if len(hits) == 1 else "  (occ=%d/%d)" % (occ, len(hits))
        print("[ok]            %-18s P%03d @%d len=%d%s"
              % (label, para, start, len(s), flag))

    print("\n引文 %d 条，问题 %d 条" % (len(Q.QUOTES), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
