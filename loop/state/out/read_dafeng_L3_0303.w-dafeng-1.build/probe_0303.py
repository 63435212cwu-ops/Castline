# -*- coding: utf-8 -*-
"""第七十四章 引文定位探针（构建期）。

做什么：
  1. 读 data/cache/1063b17ca65ec1b76f30e460.docs.json 的 docs[0].text（全文）。
  2. 对 quotes_0303.py 里每条 quote 用 str.find 现算**全文 codepoint 偏移**，
     断言 docs[0].text[start:end] == quote 逐字成立、且 start/end 落在本单元区间内。
  3. 记录 occ（该引文在**整个 docs[0].text** 里第几次出现）与 para（切片内段号）。
     值可以是 str（取区间内第 0 次出现）或 {"q": str, "occ": N}（取区间内第 N 次出现）。
     ——「同一句在本章出现两次」本身就是证据（C18），必须能指定取哪一次。
  4. 负控：NEGATIVE_CONTROL 必须 not-found，否则探针是恒真通过。

输出：refs_0303.json（key → ref 对象）。候选里每条 quotes[] 的唯一来源，
候选构建脚本不手写任何 start/end。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from quotes_0303 import QUOTES, NEGATIVE_CONTROL  # noqa: E402

DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 1338280, 1348239
OUT = Path(__file__).resolve().parent / "refs_0303.json"

text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
slice_ = text[START:END]

para_at = {}
cur = START
for i, p in enumerate(slice_.split("\n")):
    if p.strip():
        para_at[cur] = i
    cur += len(p) + 1


def para_of(pos):
    best = None
    for off, idx in para_at.items():
        if off <= pos:
            best = idx
        else:
            break
    return best


def all_occ(q):
    out, p = [], text.find(q)
    while p != -1:
        out.append(p)
        p = text.find(q, p + 1)
    return out


refs, problems, multi = {}, [], {}
for key, spec in QUOTES.items():
    if isinstance(spec, dict):
        q, want = spec["q"], spec.get("occ", 0)
    else:
        q, want = spec, 0
    assert isinstance(q, str) and q, key
    hits = [p for p in all_occ(q) if START <= p and p + len(q) <= END]
    if not hits:
        problems.append("引文不在本区间内：%s %r" % (key, q[:40]))
        continue
    if want >= len(hits):
        problems.append("指定的第 %d 次出现不存在（区间内只有 %d 次）：%s" % (want, len(hits), key))
        continue
    s = hits[want]
    e = s + len(q)
    if text[s:e] != q:
        problems.append("逐字不成立：%s" % key)
        continue
    refs[key] = {"key": key, "quote": q, "start": s, "end": e,
                 "sourceHash": SOURCE_HASH, "occ": want,
                 "occInSlice": len(hits), "para": para_of(s)}
    multi.setdefault((s, e), []).append(key)

neg_hits, p = [], text.find(NEGATIVE_CONTROL)
while p != -1:
    neg_hits.append(p)
    p = text.find(NEGATIVE_CONTROL, p + 1)

OUT.write_text(json.dumps(refs, ensure_ascii=False, indent=1), encoding="utf-8")

print("引文条数：%d / %d" % (len(refs), len(QUOTES)))
print("负控命中数：%d（必须为 0）" % len(neg_hits))
if problems:
    print("问题：")
    for x in problems:
        print("  -", x)
dups = {k: v for k, v in multi.items() if len(v) > 1}
if dups:
    print("同一区间被多个 key 引用（应只在「重复本身即证据」时出现）：")
    for k, v in dups.items():
        print("  ", k, v, "occInSlice=", refs[v[0]]["occInSlice"])
repeat = {k: r for k, r in refs.items() if r["occInSlice"] > 1}
if repeat:
    print("区间内重复出现的引文（可支撑「重复」类断言）：")
    for k, r in repeat.items():
        print("   %s occ=%d/%d @%d" % (k, r["occ"], r["occInSlice"], r["start"]))
print("唯一区间：%d" % len(multi))
print("覆盖字符数（并集）：%d" % len(set().union(*[set(range(r["start"], r["end"])) for r in refs.values()])))
print("切片字符数：%d" % len(slice_))
sys.exit(1 if (problems or neg_hits) else 0)
