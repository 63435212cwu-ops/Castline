#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L3:0303 第 5 步：修正两条 dialogue+containsUtterance=False，并让 legend 的说法为真。

第 4 步的脚本条件写错了（找 kind=='narration'），所以一条也没改，却在 amendment.round4 里
写了「修正 N 条」与「本文件已无 dialogue+False 的条目」——那句当时是**假的**。
本步：①按正确条件真正修掉那两条；②把该说法改写成与事实一致（修完为 0 条）；
③在 amendment 里如实登记第 4 步的失误，不掩盖。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0303.candidate.json"
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
Q = "一有消息，就在城门口发布公告，本官看到后，自然就会寻来。"

if hashlib.sha256(DOCS.read_bytes()).hexdigest() != SRC_HASH:
    sys.exit("sourceHash 不符，停止")
c = json.loads(CAND.read_text(encoding="utf-8"))
before = hashlib.sha256(CAND.read_bytes()).hexdigest()

fixed = []


def walk(o, path="$"):
    if isinstance(o, dict):
        if o.get("quote") == Q and o.get("kind") == "dialogue" and o.get("containsUtterance") is False:
            o["containsUtterance"] = True
            o["kindNote"] = (
                "修正：这是许七安当面对李知府说的话，原文以对白续行 '    “一有消息…' 起。"
                "我摘的这一截没带上开引号，于是被引号启发式判成「不含人物说的话」，"
                "上一版据此写成 containsUtterance=False。口径应看发言人，不看引号，本轮改正。"
            )
            fixed.append(path)
        for k, v in o.items():
            walk(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i))


walk(c)

remaining = []


def scan(o, path="$"):
    if isinstance(o, dict):
        if (isinstance(o.get("quote"), str) and o.get("kind") == "dialogue"
                and o.get("containsUtterance") is False):
            remaining.append(path)
        for k, v in o.items():
            scan(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan(v, "%s[%d]" % (path, i))


scan(c)

c["quoteRefFieldLegend"]["containsUtterance"] = (
    "该截取区间里**是否含人物说出/写出的字**。实际判定混合了两条线索：引号（“”【】）"
    "与叙述标记（道：/传书/内心），因此它是**启发式**字段，有两类已知偏差："
    "①对白续行若不带走引号会被判 False（本轮修掉了 2 条这样的条目，"
    "现文件中 kind=dialogue 且 containsUtterance=False 的条目数：%d）；"
    "②叙述句里嵌了带引号的词（如「好评」「猫道」）会被判 True。"
    "kind 字段才是权威，两者冲突时以 kind 为准。" % len(remaining)
)
c["quoteRefFieldLegend"]["kind"] = (
    "narration 叙述（含叙述者评论）/ dialogue 人物说或写的字 / inner 人物内心独白 / "
    "free_indirect 叙述转述人物理解（非叙述认定）。"
)
am = c.setdefault("amendment", {})
am["round4Note"] = (
    "round4 的条件写错（按 kind=='narration' 找），实际修正 0 条，而它同时写下了"
    "「本文件已无 dialogue+False 的条目」——那句话在 round4 提交时是**假的**。"
    "round5 已按正确条件修掉那 2 条，并把该说法改成与事实一致。保留本条记录，不删改 round4。"
)
am["round5"] = {
    "by": "w-dafeng-1",
    "baseCandidateSha256": before,
    "change": "修正 %d 条 kind=dialogue 却 containsUtterance=False 的条目（均为「一有消息…」那句）。"
              % len(fixed),
    "fixedPaths": fixed,
    "remainingDialogueFalse": remaining,
    "note": "本步只改 containsUtterance 与新增 kindNote，不动 start/end/occ/para/globalOcc。",
}

CAND.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
print("fixed:", len(fixed), fixed)
print("remaining dialogue+False:", remaining)
print("new sha256:", hashlib.sha256(CAND.read_bytes()).hexdigest())
