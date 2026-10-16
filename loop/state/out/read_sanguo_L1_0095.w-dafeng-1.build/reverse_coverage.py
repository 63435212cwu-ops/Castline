# -*- coding: utf-8 -*-
"""反向验证：这一段里**还漏了什么**（而不是「已写项对不对」）。

做法：把本单元原文切成子句（按 ，、；。！？ 等标点切分），逐条检查它是否被
候选里任何一条引文覆盖（引文区间包含该子句区间）。未被覆盖的子句全部列出，
由人工逐条归位（补进 states/worldSettings 或明确登记为「无需处理」）。

这与 READER 的第二轮反向覆盖自检同法；只查已写项是结构性地发现不了遗漏的。
"""

import json
import re
import sys

SEP = "，、；。！？：“”\n　"
MIN_LEN = 6
# 古籍整理者的页脚/版权行，非小说内容
NON_LITERARY = ("枫林晚", "------------------", "整理校对", "回目录", "回首页", "后一页", "前一页")


def clauses(text, S, E):
    out = []
    buf = ""
    start = S
    for i in range(S, E):
        ch = text[i]
        if ch in SEP:
            if buf.strip():
                out.append((start, start + len(buf), buf))
            buf = ""
            start = i + 1
        else:
            if not buf:
                start = i
            buf += ch
    if buf.strip():
        out.append((start, start + len(buf), buf))
    return out


def main():
    text = json.load(open("data/cache/fe42d01f3826fe8096f86614.docs.json"))[0]["text"]
    S, E = 484338, 489034
    cand_path = sys.argv[1] if len(sys.argv) > 1 else \
        "loop/state/out/read_sanguo_L1_0095.candidate.json"
    cand = json.load(open(cand_path))

    spans = []

    def walk(n):
        if isinstance(n, dict):
            if "start" in n and "end" in n:
                spans.append((n["start"], n["end"]))
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(cand)
    spans.sort()

    cls = [c for c in clauses(text, S, E) if len(c[2].strip()) >= MIN_LEN]
    uncovered = []
    covered_chars = 0
    for a, b, s in cls:
        if any(x <= a and b <= y for x, y in spans):
            covered_chars += b - a
        else:
            uncovered.append((a, b, s))

    total = sum(b - a for a, b, _ in cls)
    lit = [c for c in uncovered if not any(k in c[2] for k in NON_LITERARY)]
    nonlit = [c for c in uncovered if any(k in c[2] for k in NON_LITERARY)]

    print("子句总数=%d 覆盖=%d 未覆盖=%d (其中非文学 %d)"
          % (len(cls), len(cls) - len(uncovered), len(uncovered), len(nonlit)))
    print("字符覆盖率 = %d/%d = %.4f" % (covered_chars, total, covered_chars / total))
    print()
    print("== 未覆盖子句（文学内容）==")
    for a, b, s in lit:
        print("  @%d-%d  %s" % (a, b, s))
    print()
    print("== 未覆盖子句（整理者页脚）==")
    for a, b, s in nonlit:
        print("  @%d-%d  %r" % (a, b, s[:40]))

    json.dump({
        "clauseCount": len(cls),
        "minClauseLen": MIN_LEN,
        "coveredChars": covered_chars,
        "totalClauseChars": total,
        "coveredRatio": round(covered_chars / total, 4),
        "uncoveredLiterary": [{"start": a, "end": b, "text": s} for a, b, s in lit],
        "uncoveredNonLiterary": [{"start": a, "end": b, "text": s} for a, b, s in nonlit],
        "uncoveredCount": len(uncovered),
        "uncoveredLiteraryCount": len(lit),
        "uncoveredNonLiteraryCount": len(nonlit),
    }, open("loop/state/out/read_sanguo_L1_0095.w-dafeng-1.build/reverse_coverage.json", "w"),
        ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
