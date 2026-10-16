#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立校验 loop/state/out/read_dafeng_L3_0303.candidate.json（不依赖生成脚本）。

复核命令：
  python3 -B -s loop/state/out/read_dafeng_L3_0303.w-dafeng-1.build/check_0303.py

检查项（任一失败 => 非零退出）：
  1. sourceHash == 整个 docs.json 的 sha256；sliceSha256 == 切片 sha256
  2. 每条 quote：T[start:end] == quote 逐字成立；区间落在 [1338280,1348239) 内
  3. 每条 quote：occ 与切片内第几次出现一致；para 指向含该引文的行
  4. 五栏依据不共用同一区间（同任务内两两不重叠）
  5. 内容分区键齐全（tasks/causeEdges/states/foreshadows/worldSettings/themeReadings）
  6. 每个 null 栏位都有同名 <栏>Note
  7. worldSettings 的 kind 专属字段齐全；item 的 itemStates 是四态子集
  8. foreshadows 有 setup 与 payoff；未回收的显式标 unresolved
  9. themeReadings 每条都有 perspective/support/counter
 10. 没有引文落在作者区 [1348131,1348239)
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0303.candidate.json"
S, E = 1338280, 1348239
AUTHOR_START = 1348131
FIVE = ("objective", "obstacle", "action", "result", "cost")
fails = []


def bad(msg):
    fails.append(msg)
    print("  FAIL", msg)


T = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
SL = T[S:E]
LINES = SL.split("\n")
c = json.loads(CAND.read_text(encoding="utf-8"))

print("== 1. 哈希 ==")
fh = hashlib.sha256(DOCS.read_bytes()).hexdigest()
sh = hashlib.sha256(SL.encode()).hexdigest()
print("  file sha256  :", fh)
print("  slice sha256 :", sh)
if c["source"]["sourceHash"] != fh:
    bad("sourceHash 与 docs.json 实际哈希不符")
if c["source"]["sliceSha256"] != sh:
    bad("sliceSha256 与切片实际哈希不符")
if fh != "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839":
    bad("docs.json 哈希与任务声明不符（源文件被改过？）")

print("== 2-3. 引文定位 ==")
refs = []


def walk(o, path="$"):
    if isinstance(o, dict):
        if isinstance(o.get("quote"), str) and isinstance(o.get("start"), int):
            refs.append((path, o))
        for k, v in o.items():
            walk(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i))


walk(c)
print("  quote 引用总数:", len(refs))
for path, o in refs:
    q, st, en = o["quote"], o["start"], o["end"]
    if T[st:en] != q:
        bad("%s: T[start:end] != quote" % path)
    if not (S <= st and en <= E):
        bad("%s: 越出本单元区间" % path)
    if st >= AUTHOR_START:
        bad("%s: 引文落在作者区" % path)
    if o.get("sourceHash") != fh:
        bad("%s: 条目 sourceHash 与文件哈希不符" % path)
    loc = SL.find(q)
    if loc < 0:
        bad("%s: 引文不在切片内" % path)
        continue
    # occ 口径：**切片内**、且位于本 start 处那一次的下标（不是首次、不是全书）。
    # 这条口径由 quoteRefFieldLegend 声明；此处按它校验。
    if o.get("occ") != SL.count(q, 0, st - S):
        bad("%s: occ 声明 %r 实际 %d" % (path, o.get("occ"), SL.count(q, 0, st - S)))
    if "globalOcc" in o and o["globalOcc"] != T.count(q):
        bad("%s: globalOcc 声明 %r 实际 %d" % (path, o["globalOcc"], T.count(q)))
    p = o.get("para")
    if not isinstance(p, int) or not (0 <= p < len(LINES)) or LINES[p].find(q) < 0:
        bad("%s: para 声明 %r 不指向含引文的行" % (path, p))

print("== 4. 五栏区间不重叠 ==")
for tk in c["tasks"]:
    iv = {}
    for f in FIVE:
        v = tk.get(f)
        if isinstance(v, dict):
            for q in v.get("quotes") or []:
                iv.setdefault(f, []).append((q["start"], q["end"], q.get("key")))
    ks = list(iv)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            for a in iv[ks[i]]:
                for b in iv[ks[j]]:
                    if a[0] < b[1] and b[0] < a[1]:
                        bad("%s: %s(%s) 与 %s(%s) 区间重叠" % (tk["id"], ks[i], a[2], ks[j], b[2]))
print("  tasks:", len(c["tasks"]), " 重叠: 见上（无 FAIL 即通过）")

print("== 5. 内容分区键 ==")
for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    if k not in c:
        bad("缺分区 %s" % k)
    else:
        print("  %-16s %d 条" % (k, len(c[k])))

print("== 6. null 栏位必须有 Note ==")
nnull = 0
for tk in c["tasks"]:
    for f in FIVE:
        if tk.get(f) is None:
            nnull += 1
            if not (tk.get(f + "Note") or "").strip():
                bad("%s.%s 为 null 但没有 %sNote" % (tk["id"], f, f))
print("  null 栏位数:", nnull)

print("== 7. worldSettings 字段 ==")
STATES = {"hold", "transfer", "use", "lose"}
for w in c["worldSettings"]:
    for k in ("kind", "name", "explain", "quotes"):
        if not w.get(k):
            bad("%s 缺 %s" % (w.get("id"), k))
    if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        bad("%s: placeState 非法 %r" % (w["id"], w.get("placeState")))
    if w["kind"] == "item":
        ist = w.get("itemStates")
        if not isinstance(ist, list) or any(x not in STATES for x in ist):
            bad("%s: itemStates 非法 %r" % (w["id"], ist))
    if w["kind"] == "rule":
        if w.get("institution") not in ("declared", "executed", "misunderstood", None):
            bad("%s: institution 非法 %r" % (w["id"], w.get("institution")))
        if w.get("institution") is None and not (w.get("institutionNote") or "").strip():
            bad("%s: institution 为 null 但没有 institutionNote" % w["id"])
print("  worldSettings:", len(c["worldSettings"]), " place/item/rule =",
      sum(1 for w in c["worldSettings"] if w["kind"] == "place"),
      sum(1 for w in c["worldSettings"] if w["kind"] == "item"),
      sum(1 for w in c["worldSettings"] if w["kind"] == "rule"))

print("== 8. foreshadows ==")
for f in c["foreshadows"]:
    if not f.get("setup"):
        bad("%s 无 setup" % f.get("id"))
    if not f.get("payoff"):
        bad("%s 无 payoff" % f.get("id"))
    if f.get("resolved") is False and f.get("unresolved") is not True:
        bad("%s: 未回收却没显式标 unresolved" % f.get("id"))
print("  foreshadows:", len(c["foreshadows"]),
      " unresolved:", sum(1 for f in c["foreshadows"] if f.get("unresolved")))

print("== 9. themeReadings ==")
for t in c["themeReadings"]:
    for k in ("perspective", "support", "counter"):
        if not t.get(k):
            bad("%s 缺 %s" % (t.get("id"), k))
print("  themeReadings:", len(c["themeReadings"]))

print("== 10. 语义纪律自查 ==")
if c.get("semanticReview") != "not-performed":
    bad("semanticReview 被写成非 not-performed（定位正确 != 语义已核验）")
print("  semanticReview:", c.get("semanticReview"))

print()
if fails:
    print("结果：FAIL（%d 项）" % len(fails))
    sys.exit(1)
print("结果：全部检查通过（0 FAIL）")
