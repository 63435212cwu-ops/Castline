#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify:dafeng:L3:0251 · 第四探针：把我要写进 verdict 的每条引文做**逐字 + 覆盖**核验。

对每条待用引文报告：
  1. text[start:end] == quote（逐字）
  2. text.find(quote) 是否等于 start
  3. 是否有**任何**候选引文区间与它相交（未相交 = 候选确实没引到）
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
text = json.loads((ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json").read_text("utf-8"))[0]["text"]
cand = json.loads((ROOT / "loop/state/out/read_dafeng_L3_0251.candidate.json").read_text("utf-8"))


def walk(node, path="$"):
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node:
            yield path, node
        for k, v in node.items():
            yield from walk(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, "%s[%d]" % (path, i))


Q = list(walk(cand))

CASES = [
    ("CE1a T04 objective/obstacle 同句(P32) 前半",
     "元景三十一年春，应该是宫女黄小柔失身的时间"),
    ("CE1a' T04 objective 引文（候选）",
     "元景三十一年春，应该是宫女黄小柔失身的时间"),
    ("CE1b T04 obstacle 引文（候选）",
     "黄小柔自尽是四年前，元景三十一年是五年前"),
    ("CE1c T06 objective/obstacle 同句(P56) 全句",
     "国舅府在皇城中，许七安和长公主抵达国舅府，问了守卫，才知道国舅不在皇城里，而在内城的老宅。"),
    ("CE1d T06 result/cost 同句(P61)",
     "用了半个多时辰才抵达上官氏祖宅"),
    ("CE2 W01.explain 排他措辞的反证（探视规则）",
     "除了宗室之外，皇后、皇贵妃、贵妃的家人，也可以进宫探望她们，只需要提前向宫里报备。"),
    ("CE3 S04.before 声称的『搂美人/食客』原文",
     "左手搂一个美人，右手搂一个美人。"),
    ("CE3' S04.before 实际挂的引文",
     "主位坐着一个皮肤白皙，皮相极好的中年男人"),
    ("CE3'' 食客句",
     "两侧坐着几名食客，好不快活。"),
    ("CE4 V08.extraQuotes[0]",
     "国舅呆住了。"),
    ("CE4 V08.extraQuotes[1]",
     "他竟朝着怀庆公主大吼起来。"),
    ("CE4' V08 主引文",
     "“她既然认了，说明除了黄小柔之外，你还有一个把柄在别人手里。”"),
    ("RC1 P008 国舅定性（候选未引）",
     "一个纵情声色的纨绔子弟，不学无术，耽于美色。"),
    ("RC1' P009（候选未引）",
     "言语之中，似乎对那位亲舅舅极为厌恶、嫌弃。"),
    ("RC2 P022 怀庆定性后半（候选未引）",
     "怀庆是个能成大事的女人，这一点我可以确认。"),
    ("RC3 P032 年份保留句（候选未引）",
     "元景三十七年才刚开始，咱们先不算。"),
    ("RC4 P126 假冒得逞的前提（候选未引）",
     "黄小柔是元景二十八年进宫的，那时陛下已经沉迷修道，不再去后宫了"),
    ("RC4' P126b（候选未引）",
     "一个小小的宫女，根本没见过元景帝长什么样"),
    ("RC5 P129 长期幽会（候选未引）",
     "后来，我食髓知味，常借着探望皇后的名义，与黄小柔幽会"),
    ("RC5' P124 国舅自认逻辑（候选未引）",
     "她是后宫之主，只要她同意，谁又能阻止？"),
    ("RC6 P131 动机链（候选未引）",
     "等她后来知道自己被骗，原来那个诱奸她的人不是皇帝，而是你这个国舅爷"),
    ("RC6' P131b（候选未引）",
     "她又惹不起皇后，羞怒之下，自尽了"),
    ("RC7 P118 心软确认句（候选未引）",
     "怀庆说的没错，皇后太过心慈手软"),
    ("RC7' P118b（候选未引）",
     "许七安侧头看了眼长公主。"),
]

print("%-46s %-6s %-6s %-7s %s" % ("case", "逐字", "find", "被引?", "覆盖它的候选引文"))
for name, q in CASES:
    s = text.find(q)
    verbatim = s >= 0
    e = s + len(q)
    hit = [(p, x["start"], x["end"], x["quote"][:34]) for p, x in Q
           if verbatim and x["start"] < e and s < x["end"]]
    print("%-46s %-6s %-6s %-7s %s" % (
        name[:45], verbatim, "OK" if verbatim else "N/A",
        "是" if hit else "否",
        ("; ".join("%s[%d,%d) %s" % h for h in hit[:2]) if hit else "-")))
