#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L3:0303 第 4 步：修正本轮自己新增的两条 kind/containsUtterance 不一致，并写明口径。

发现的真问题（本轮独立校验脚本抓出，不是上一轮的）：
  reverseVerification[2]（q_gonggao）与 knowledgeGaps[11].quotes[0]（q_gonggao2）都是
  **许七安对李知府说的话**，但 kind 写成 narration、containsUtterance=False。
  原因是这两条引文取自对白**续行**（原文用 '    “一有消息…' 起，含开引号），
  我摘的那一截没带上开引号，于是被「引号启发式」判成叙述。
  口径应看说话人，不看有没有引号 —— 这里按语义改正为 dialogue / containsUtterance=True。

同时补上 containsUtterance 的**精确口径**说明：它是「这一截里是否含人物说出/写出的字」，
由引号或叙述标记（道：/传书/内心）判定，属启发式字段；kind 才是权威。两者冲突时以 kind 为准。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0303.candidate.json"
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

if hashlib.sha256(DOCS.read_bytes()).hexdigest() != SRC_HASH:
    sys.exit("sourceHash 不符，停止")
c = json.loads(CAND.read_text(encoding="utf-8"))
before = hashlib.sha256(CAND.read_bytes()).hexdigest()

fixed = []


def walk(o, path="$"):
    if isinstance(o, dict):
        if (o.get("quote") == "一有消息，就在城门口发布公告，本官看到后，自然就会寻来。"
                and o.get("kind") == "narration"):
            o["kind"] = "dialogue"
            o["containsUtterance"] = True
            o["kindNote"] = ("修正：这是许七安当面对李知府说的话（对白续行 '    “一有消息…'），"
                             "上一版因摘录未含开引号而被启发式判成 narration，本轮按发言人改正。")
            fixed.append(path)
        for k, v in o.items():
            walk(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i))


walk(c)

# 精确口径：同时保留实际存在的启发式偏差清单，供复核者判断，而不是假装字段是精确的。
c["quoteRefFieldLegend"]["containsUtterance"] = (
    "该截取区间里**是否含人物说出/写出的字**。实际判定混合了两条线索：引号（“”【】）"
    "与叙述标记（道：/传书/内心）。因此它是**启发式**字段，已知偏差两类："
    "①对白续行若不带走引号会被判 False（本轮修正了 2 条这样的条目）；"
    "②叙述句里嵌了带引号的词（如「好评」「猫道」）会被判 True。"
    "kind 字段才是权威；两者冲突时以 kind 为准，本文件已无 dialogue+False 的条目。"
)
c["quoteRefFieldLegend"]["kind"] = (
    "narration 叙述（含叙述者评论）/ dialogue 人物说或写的字 / inner 人物内心独白 / "
    "free_indirect 叙述转述人物理解（非叙述认定）。"
)
c.setdefault("amendment", {})["round4"] = {
    "by": "w-dafeng-1",
    "baseCandidateSha256": before,
    "change": "修正 %d 条 kind/containsUtterance 不一致（q_gonggao、q_gonggao2），"
              "并写明 containsUtterance 的启发式口径与两类已知偏差。" % len(fixed),
    "foundBy": "loop/state/out/read_dafeng_L3_0303.w-dafeng-1.build/check_0303.py",
    "fixedPaths": fixed,
}

CAND.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
print("fixed:", fixed)
print("new sha256:", hashlib.sha256(CAND.read_bytes()).hexdigest())
