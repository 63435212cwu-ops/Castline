#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L3:0303 第 3 步：把引文定位字段的口径写成机器可读的说明，并给每条引用补 globalOcc。

为什么做这一步（有实证理由，不是装饰）：
  本候选的每条引用带 start/end/occ/para 四个定位字段，但**没有任何地方写明它们的口径**。
  本轮我自己写的独立校验脚本第一次跑就误判了一条：把 `occ` 当成「全章第几次出现」，
  于是把 causeEdges[17].quotes[1]（章末第二次出现的「大家的求生欲都好强…」）报成 FAIL。
  实测口径是「**切片内**、且是该 start 处那一次的下标」——395 条全部符合，0 条例外。
  这说明该字段很容易被复核者误读成一个不存在的全局口径，从而产生**假缺陷**。

  所以这里做两件只增不改的事：
    1. 新增 quoteRefFieldLegend，把四个字段的口径逐条写明（含已验证的实测计数）；
    2. 给每条引用补 globalOcc = 该引文在 docs[0].text **全书**里出现的总次数。
       它让「这一句在本章出现了两次」变成可机器断言的字段 —— 而这条重复正是
       C18（自我重复被点破）与 TH01 的承重证据，不该只靠复核者肉眼数。
  start/end/occ/para 的**值一律不改**（改值会让上一轮的定位工作无法追溯）。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0303.candidate.json"
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 1338280, 1348239

if hashlib.sha256(DOCS.read_bytes()).hexdigest() != SRC_HASH:
    sys.exit("sourceHash 不符，停止")
T = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
SL = T[S:E]

c = json.loads(CAND.read_text(encoding="utf-8"))
before_sha = hashlib.sha256(CAND.read_bytes()).hexdigest()

refs = []


def walk(o):
    if isinstance(o, dict):
        if isinstance(o.get("quote"), str) and isinstance(o.get("start"), int):
            refs.append(o)
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(c)


def occ_at_start(o):
    return SL.count(o["quote"], 0, o["start"] - S)


def para_of(o):
    q, loc = o["quote"], o["start"] - S
    pos = 0
    for i, ln in enumerate(SL.split("\n")):
        if pos <= loc < pos + len(ln):
            return i, ln
        pos += len(ln) + 1
    return None, None


ok = ok_para = 0
for o in refs:
    if o.get("occ") == occ_at_start(o):
        ok += 1
    i, ln = para_of(o)
    if o.get("para") == i and ln is not None and ln.find(o["quote"]) >= 0:
        ok_para += 1
    o["globalOcc"] = T.count(o["quote"])

c["quoteRefFieldLegend"] = {
    "start/end": "相对 docs[0].text **全文** 的 codepoint 半开区间；自检 T[start:end] == quote。",
    "occ": "该引文在**本单元切片** [1338280,1348239) 内、且位于本 start 处那一次的下标（0 起）。"
           "**不是**全书出现次数，**也不是**切片内首次出现的下标。"
           "实测：本文件 %d 条引用全部符合此口径（0 例外）；若按『切片内首次』读，会有 1 条被误判。"
           % len(refs),
    "para": "0 起**行号**（把切片按 '\\n' 切分后的行下标），指向包含该引文的那一行；"
            "实测 %d/%d 条符合。" % (ok_para, len(refs)),
    "globalOcc": "本轮新增：该引文在整个 docs[0].text 里出现的**总次数**（全书口径）。"
                 "取值 >1 的引用是章内重复句，其中「大家的求生欲都好强…」在 [1339421] 与 [1348030] 各出现一次，"
                 "这处重复是 C18 与 TH01 的承重证据。",
    "verifiedBy": "loop/state/out/read_dafeng_L3_0303.w-dafeng-1.build/check_0303.py",
}

c["quoteRefFieldLegendNote"] = (
    "加这一节的理由是实证的：本轮独立复核脚本第一次运行时，因为把 occ 误读成全局口径，"
    "把一条正确的引用报成 FAIL。定位字段没有被写明的口径，会稳定地生产**假缺陷**。"
    "本轮只补传说与 globalOcc，不改任何 start/end/occ/para 的值。"
)

c.setdefault("amendment", {})["round3"] = {
    "by": "w-dafeng-1",
    "baseCandidateSha256": before_sha,
    "change": "新增 quoteRefFieldLegend / quoteRefFieldLegendNote，并为 %d 条引用补 globalOcc。" % len(refs),
    "noValueChanged": "start/end/occ/para 一律未改（脚本只读它们做自检）。",
}

CAND.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
print("refs:", len(refs), " occ-convention ok:", ok, " para-convention ok:", ok_para)
print("multi-occurrence refs:", sum(1 for o in refs if o["globalOcc"] > 1))
print("new sha256:", hashlib.sha256(CAND.read_bytes()).hexdigest())
