#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""顺序性复核：把候选里**所有涉及时序的断言**从原文重算。

为什么需要这个脚本：机械审计只证明「引文逐字、偏移对得上」，
但一条边可以引文全对、方向却写反。实测同一份产物里就有多处：
  e4「原文先给出她认定的常识，再给出她的反应」——原文反应在前；
  e5「守卫先问姓名、再听来历」——原文来历在前；
  e6「魏渊先摆出他所知道的，随后才是许七安的巨细无遗」——原文交底在前；
  e13「下一段紧接着写这一等就是一个时辰」——该句在原文里更早。
本脚本对 states 的 before/anchor/after 与 foreshadows 的 setup/payoff 做同样的检查。

用法：python3 -B -s <本文件>
"""
import json
import re
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
CAND_PATH = ROOT / "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/PRIOR-candidate.w-read-2.json.bak"
t = json.load(open(ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"))[0]["text"]
CAND = json.load(open(CAND_PATH))

# 顺序语境词：机制句里出现这些词时，声称了一个「谁先谁后」
ORDER_RE = re.compile(r"先[^。；]{0,40}?[，,、]?\s*(?:随后|再|然后|才|紧接着)|紧接着|下一段")

bad = []


def span(q):
    i = t.find(q)
    return i, i + len(q)


print("=" * 96)
print("1) causeEdges：机制里若声称先后，则引文偏移必须支持该先后")
print("=" * 96)
for e in CAND["causeEdges"]:
    m = e.get("mechanism", "")
    qs = e.get("quotes", [])
    offs = [q["start"] for q in qs]
    claim = ORDER_RE.search(m)
    status = "—"
    detail = ""
    if claim and len(qs) >= 2:
        # 机制声称的先后，通常按引文出现次序叙述；检查引文是否按偏移升序排列
        if offs != sorted(offs):
            status = "✗ 反转"
            detail = f"引文偏移 {offs} 非升序，机制句声称「{claim.group(0)}」"
            bad.append((e["id"], detail))
    print(f"[{e['id']:4}] 引文偏移 {str(offs):32} 机制声称={claim.group(0) if claim else '（无先后词）':12} {status} {detail}")

print()
print("=" * 96)
print("2) states.change：before < anchor <= after 应当成立（锚点是触发事件）")
print("=" * 96)


def node_off(node):
    qs = (node or {}).get("quotes") or []
    return min([q["start"] for q in qs]) if qs else None


for s in CAND["states"]:
    if s.get("kind") != "change":
        continue
    b, a, an = node_off(s.get("before")), node_off(s.get("after")), node_off(s.get("anchor"))
    ok = (b is not None and a is not None and an is not None and b <= a)
    anchor_ok = (an is not None and b is not None and a is not None and b <= an <= a)
    flag = ""
    if not ok:
        flag = "✗ before/after 倒置"
        bad.append((s["id"], f"before@{b} > after@{a}"))
    elif not anchor_ok:
        flag = "✗ 锚点落在变化区间之外"
        bad.append((s["id"], f"anchor@{an} 不在 [{b},{a}]"))
    print(f"[{s['id']:4}] before@{b}  anchor@{an}  after@{a}   {flag}")

print()
print("=" * 96)
print("3) foreshadows：setup 必须早于 payoff")
print("=" * 96)
for f in CAND["foreshadows"]:
    su = [q["start"] for q in f.get("setup", [])]
    pa = [q["start"] for q in f.get("payoff", [])]
    flag = ""
    if su and pa and max(su) > min(pa):
        flag = "✗ 回收早于铺设"
        bad.append((f["id"], f"setup max@{max(su)} > payoff min@{min(pa)}"))
    print(f"[{f['id']:4}] setup max@{max(su) if su else None}  payoff min@{min(pa) if pa else None}  status={f['status']:10} {flag}")

print()
print("=" * 96)
print("4) tasks：action 应当不晚于 result")
print("=" * 96)
for tk in CAND["tasks"]:
    def off(slot):
        v = tk.get(slot)
        if not isinstance(v, dict):
            return None
        qs = v.get("quotes") or []
        return max(q["start"] for q in qs) if qs else None
    o, ac, r = off("objective"), off("action"), off("result")
    flag = ""
    if ac is not None and r is not None and ac > r:
        flag = "✗ action 晚于 result（时序倒置）"
        bad.append((tk["id"], f"action@{ac} > result@{r}"))
    print(f"[{tk['id'][:34]:34}] objective@{o}  action@{ac}  result@{r}  {flag}")

print()
print("=" * 96)
print("结论")
print("=" * 96)
if bad:
    print(f"发现 {len(bad)} 处顺序性问题：")
    for i, d in bad:
        print(f"  ✗ [{i}] {d}")
else:
    print("未发现顺序性问题")

Path(ROOT / "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/audit_order.result.txt").write_text(
    "\n".join(f"[{i}] {d}" for i, d in bad) or "OK", encoding="utf-8")
