#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立缺口图 —— w-verify-4 自写。不复用候选的 reverseCoverage，也不复用被复核者的
blindspot.py。做法：把所有引文区间并成一张**字符级**覆盖掩码，取未被覆盖的极大连续段，
按「可见字符」（排除空白与标点）计数，报出 >= 阈值 的片段及其归属段。

与候选口径的差别（这是关键）：
  候选按 。！？ 切句，句内**任一处**被引即判该句 covered ⇒ 对句内遗漏结构性不敏感。
  本图是**字符级**：一处没引就是一处没引，不存在"句内被代表"。
"""
import json, sys, re, os

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/fe42d01f3826fe8096f86614.docs.json")
S, E = 522662, 528484
THRESH = 12

# 标点/空白：不计入"可见字数"（与">=12 字"的直觉一致）
PUNCT = set("　 \n\t“”‘’『』「」（）()《》〈〉、，。；：！？—…·．,.;:!?\"'‘’")
def visible(s):
    return [ch for ch in s if ch not in PUNCT]


def main():
    text = json.loads(open(DOCS, "rb").read().decode("utf-8"))[0]["text"]
    sl = text[S:E]
    cand = json.load(open(os.path.join(ROOT, "loop/state/out/read_sanguo_L0_0102.candidate.json")))

    def walk(n):
        if isinstance(n, dict):
            if isinstance(n.get("quote"), str):
                yield n
            for v in n.values():
                yield from walk(v)
        elif isinstance(n, list):
            for v in n:
                yield from walk(v)

    mask = [False] * len(sl)
    nq = 0
    for item in walk(cand):
        st, en = item.get("start"), item.get("end")
        if not isinstance(st, int) or not isinstance(en, int):
            continue
        nq += 1
        # 用**真实长度**修正（若声明的 end 越界，也不让它吃掉后文空白）
        end = min(st + len(item["quote"]), len(text))
        for i in range(max(st, S), min(end, E)):
            mask[i - S] = True
    print("引文对象 %d，覆盖字符 %d/%d = %.1f%%" % (nq, sum(mask), len(mask), 100.0 * sum(mask) / len(mask)))

    # 极大未覆盖连续段
    runs, i = [], 0
    while i < len(mask):
        if not mask[i]:
            j = i
            while j < len(mask) and not mask[j]:
                j += 1
            runs.append((i + S, j + S))
            i = j
        else:
            i += 1

    big = []
    for (a, b) in runs:
        seg = text[a:b]
        v = visible(seg)
        if len(v) >= THRESH:
            # 该片段起点所属的正文段（按绝对偏移落在哪个非空行区间）
            big.append({"start": a, "end": b, "visible": len(v),
                        "quote": seg.strip()[:400]})
    print("未覆盖片段总数 %d，其中可见字数 >=%d 的 %d 个\n" % (len(runs), THRESH, len(big)))
    for k, f in enumerate(big, 1):
        print("[G%02d] [%d,%d) 可见%d字" % (k, f["start"], f["end"], f["visible"]))
        print("      %s" % f["quote"].replace("\n", "\\n"))
    out = os.path.join(os.environ["AGENT_ARTIFACTS"],
                       "verify-sanguo-0102-w-verify-4-dupclaim", "my_gaps.json")
    json.dump({"coveredChars": sum(mask), "totalChars": len(mask),
               "coveragePct": 100.0 * sum(mask) / len(mask),
               "uncoveredRuns": len(runs), "threshold": THRESH,
               "bigFragments": big}, open(out, "w"), ensure_ascii=False, indent=1)
    print("\n写出：%s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
