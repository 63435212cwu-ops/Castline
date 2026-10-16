#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立校验 read_sanguo_L0_0004.candidate.json。

不 import 生成器：重新读原文、重新算哈希、重新扫引号，全部从磁盘现读。
"""
import hashlib
import json
import re
import subprocess
import sys

ROOT = "/Users/carmen/Desktop/星系"
P = ROOT + "/loop/state/out/read_sanguo_L0_0004.candidate.json"
DOCS = ROOT + "/data/cache/152e2a6eed94f1075e7e7070.docs.json"
SRC_HASH = "2988ce6e36c80c4effc81f73a65221adf779631682da848bb67ef6f52a5a97ff"
S, E = 20054, 25766

d = json.load(open(P, encoding="utf-8"))
T = json.load(open(DOCS, encoding="utf-8"))[0]["text"]
fails = []

h = subprocess.run(["shasum", "-a", "256", "data/cache/152e2a6eed94f1075e7e7070.docs.json"],
                   capture_output=True, text=True, cwd=ROOT).stdout.split()[0]
if h != SRC_HASH:
    fails.append("docs.json 哈希不符：%s" % h)
if d["source"]["sourceHash"] != SRC_HASH:
    fails.append("candidate source.sourceHash 不符")
if d["source"]["sliceSha256"] != hashlib.sha256(T[S:E].encode()).hexdigest():
    fails.append("sliceSha256 不符")
if len(T[S:E]) != d["source"]["rangeChars"]:
    fails.append("rangeChars 不符")
if d["task"] != "read:sanguo:L0:0004":
    fails.append("task 字段不符")

if T[S:S + 21] != "第五回　发矫诏诸镇应曹公　破关兵三英战吕布":
    fails.append("左边界不符")
if T[E:E + 19] != "第六回　焚金阙董卓行凶　匿玉玺孙坚背约":
    fails.append("右边界不符")

refs = []


def walk(n):
    if isinstance(n, dict):
        if "quote" in n and "start" in n and "end" in n:
            refs.append(n)
        for v in n.values():
            walk(v)
    elif isinstance(n, list):
        for v in n:
            walk(v)


walk(d)
if [r for r in refs if T[r["start"]:r["end"]] != r["quote"]]:
    fails.append("有引文与原文不逐字相符")
if [r for r in refs if r["sourceHash"] != SRC_HASH]:
    fails.append("有 quoteRef 的 sourceHash 不符")
if [r for r in refs if not (S <= r["start"] < r["end"] <= E)]:
    fails.append("有 quoteRef 偏移越出本单元区间")
if [r for r in refs if "offsetUnit" not in r or r["offsetUnit"] != "codepoint"]:
    fails.append("有 quoteRef 缺 offsetUnit")

spans = []
i = S
while True:
    a = T.find("\u201c", i, E)
    if a == -1:
        break
    b = T.find("\u201d", a + 1)
    spans.append((a, b + 1))
    i = b + 1
if len(spans) != len(d["speechInventory"]):
    fails.append("引语数不符：扫描 %d vs 清单 %d" % (len(spans), len(d["speechInventory"])))
if [s for s in d["speechInventory"] if T[s["spanStart"]:s["spanEnd"]] != s["spanText"]]:
    fails.append("引语清单 span 与原文不符")
unc = [s for s in d["speechInventory"]
       if not any(s["spanText"] in r["quote"] or r["quote"] in s["spanText"] for r in refs)]
if unc:
    fails.append("有引语未被任何断言引文覆盖：%d" % len(unc))

bs = set()


def wb(n):
    if isinstance(n, dict):
        for k, v in n.items():
            if k == "basis":
                bs.add(v)
            wb(v)
    elif isinstance(n, list):
        for v in n:
            wb(v)


wb(d)
if not bs <= {"explicit", "inferred", "derived", "unverified"}:
    fails.append("非法 basis：%r" % bs)
for t in d["tasks"]:
    if not all(k in t for k in ("objective", "obstacle", "action", "result", "cost")):
        fails.append("tasks[%s] 五元组键不全" % t["id"])
    for k in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(k)
        if isinstance(v, dict):
            if "basis" not in v:
                fails.append("tasks[%s].%s 缺 basis" % (t["id"], k))
            if v.get("text") is None and not (v.get("nullReason") or t.get(k + "Note")):
                fails.append("tasks[%s].%s 为 null 但无说明" % (t["id"], k))
for e in d["causeEdges"]:
    if "→" not in e.get("direction", ""):
        fails.append("causeEdge %s 未标方向" % e.get("id"))
    if not e.get("mechanism"):
        fails.append("causeEdge %s 无机制" % e.get("id"))
for f in d["foreshadows"]:
    if f.get("status") not in ("resolved_in_unit", "resolved_later", "unresolved"):
        fails.append("foreshadow %s status 非法" % f.get("id"))
    if not f.get("setup") or "payoff" not in f:
        fails.append("foreshadow %s 缺铺设/回收" % f.get("id"))
if len(d.get("selfCritique") or []) < 3:
    fails.append("selfCritique 少于 3 条")
if d.get("semanticReview") != "not_performed":
    fails.append("semanticReview 不得声称完成")
if d.get("claimVerification") != "not_performed":
    fails.append("claimVerification 不得声称完成")

print("引文处数        :", len(refs))
print("去重区间        :", len({(r["start"], r["end"]) for r in refs}))
print("引语数          :", len(spans))
print("tasks           :", len(d["tasks"]))
print("causeEdges      :", len(d["causeEdges"]))
print("states          :", len(d["states"]))
print("foreshadows     :", len(d["foreshadows"]),
      "(resolved %d / unresolved %d)" % (
          sum(1 for f in d["foreshadows"] if f["status"] == "resolved_in_unit"),
          sum(1 for f in d["foreshadows"] if f["status"] == "unresolved")))
print("notForeshadows  :", len(d["notForeshadows"]))
print("unknowns        :", len(d["unknowns"]))
print("rejectedEdges   :", len(d["rejectedEdges"]))
print("selfCritique    :", len(d["selfCritique"]))
print("charCoverage    :", d["machineSelfCheck"]["charCoverage"], "%")
print("notQuoteCovered :", len(d["notQuoteCovered"]))
print("FAILS:", fails if fails else "NONE")
sys.exit(1 if fails else 0)
