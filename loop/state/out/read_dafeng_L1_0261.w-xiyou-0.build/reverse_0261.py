#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反向验证：句级覆盖缺口扫描。

不看「已写项对不对」，只问「这一段里还漏了什么」——即列出全区间内
**没有任何引文触及**的实质句，供人工逐条判断该补还是可不补。

口径与 build_0261.py / audit_0261.py 一致：
  句界 = 。！？＋换行；收尾引号（”’」』）】〉》）归属前一句。
  实质句 = 去空白后 ≥6 字，且不是纯分隔线、不是作者附言。

用法：
  python3 -B -s loop/state/out/read_dafeng_L1_0261.w-xiyou-0.build/reverse_0261.py
"""
import json
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0261.candidate.json"

S, E = 1088909, 1094220
CLOSERS = "”’」』）】〉》"

TEXT = json.loads(DOCS.read_bytes().decode("utf-8"))[0]["text"]
C = json.loads(CAND.read_text(encoding="utf-8"))

refs = []


def walk(o):
    if isinstance(o, dict):
        if all(k in o for k in ("quote", "start", "end", "sourceHash")):
            refs.append(o)
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(C)

bounds, pos = [S], S
while True:
    hit = None
    for ch in "。！？\n":
        i = TEXT.find(ch, pos, E)
        if i >= 0 and (hit is None or i < hit):
            hit = i
    if hit is None:
        break
    bounds.append(hit + 1)
    pos = hit + 1
bounds.append(E)
spans = [list(x) for x in zip(bounds[:-1], bounds[1:])]
for i in range(1, len(spans)):
    a, b = spans[i]
    j = a
    while j < b and TEXT[j] in CLOSERS:
        j += 1
    if j > a:
        spans[i - 1][1] = j
        spans[i][0] = j
spans = [(a, b) for a, b in spans if b > a]

total, missed = 0, []
for a, b in spans:
    t = TEXT[a:b].strip()
    if len(t) < 6:
        continue
    if set(t) <= set(".·-— "):
        continue
    if t.startswith("PS：") or t.startswith("------------"):
        continue
    total += 1
    if not any(r["start"] < b and r["end"] > a for r in refs):
        missed.append((a, t))

print("区间 [%d,%d)，实质句 %d 句，其中未被任何引文触及 %d 句（%.1f%%）"
      % (S, E, total, len(missed), 100.0 * len(missed) / total))
print("引文总数 %d" % len(refs))
print()
for a, t in missed:
    print("@%d  %s" % (a, t[:78]))
