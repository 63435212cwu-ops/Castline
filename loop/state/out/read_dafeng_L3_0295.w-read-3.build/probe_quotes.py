# -*- coding: utf-8 -*-
"""引文探针：在任何内容撰写之前，先证明每个 literal 能被逐字定位。

判据（任一非空即退出非零）：
  not_found     literal 不在切片里
  ambiguous     在切片里出现不止一次（唯一区间不成立）
  out_of_range  find 到的位置落在 [START,END) 之外（含落在作者区）

只做定位，不判断语义。定位正确 ≠ 语义已核验。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
START, END = 1286538, 1295556
AUTHOR_START = 1295417  # 「    PS：感谢…」起，作者区（非叙事）

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quotes_0295 as Q  # noqa: E402


def main():
    text = json.load(open(DOCS, encoding="utf-8"))[0]["text"]
    sl = text[START:END]
    problems = []
    seen = {}
    for key, lit in Q.QUOTES.items():
        if not isinstance(lit, str) or not lit:
            problems.append(("bad-literal", key, repr(lit)))
            continue
        cnt = sl.count(lit)
        if cnt == 0:
            problems.append(("not_found", key, lit[:60]))
            continue
        if cnt > 1:
            problems.append(("ambiguous", key, "count=%d %s" % (cnt, lit[:60])))
            continue
        pos = sl.find(lit)
        if not (0 <= pos and pos + len(lit) <= len(sl)):
            problems.append(("out_of_range", key, lit[:60]))
            continue
        if pos >= AUTHOR_START:
            problems.append(("in-author-region", key, lit[:60]))
            continue
        seen[key] = (START + pos, START + pos + len(lit))

    # 叙事引文之间的区间重叠提示（不算问题，但报告出来供人工确认）
    items = sorted(seen.items(), key=lambda kv: kv[1])
    overlaps = []
    for (k1, (s1, e1)), (k2, (s2, e2)) in zip(items, items[1:]):
        if s2 < e1:
            overlaps.append((k1, k2, e1 - s2))

    print("引文 %d 条，问题 %d 条；唯一区间 %d 个" % (len(Q.QUOTES), len(problems), len(seen)))
    print("区间重叠对 %d（仅提示，不判错）" % len(overlaps))
    for p in problems:
        print("  [问题]", p[0], p[1], p[2])
    for o in overlaps[:12]:
        print("  [重叠]", o)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
