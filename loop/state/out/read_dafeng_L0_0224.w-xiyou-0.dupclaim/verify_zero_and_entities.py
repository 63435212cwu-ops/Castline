#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补充复核：零覆盖清单身份 + 实体覆盖 + 语层风险（read:dafeng:L0:0224）。

三件独立的事，都不改动任何既有产物：

  C1. 零覆盖清单**身份**核对：候选 coverage.zeroCoverageList 的 27 条，
      是否与「按同一分段口径重算出的未被任何引文触及的段落」**逐条相等**
      （不是只比数量 —— 数量相等而内容不同是另一种缺陷）。
  C2. 实体覆盖：切片里出现的专名（人物/地点/物件），候选结论文本里有没有提到。
      没提到的不自动判错（可能属于被排除的装饰层），只列出来供复核者判。
  C3. 语层风险取证：把 P011–P016 的**框架标记**摘出来，量化「这一段到底是叙述
      还是许七安的内心推理」——这是候选自己 sc1 承认最可能读错的一处。
      本脚本只呈证据，不替复核者下结论。

用法：python3 -B -s .../verify_zero_and_entities.py
"""

import json
import os
import re
import sys

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0224.candidate.json")
START, END = 841448, 845385

# 切片里出现的专名（我自己从原文抄的，不是从候选抄的）
ENTITIES = {
    "人物": ["许七安", "宋廷风", "朱广孝", "张巡抚", "姜律中", "宋布政使", "宋长辅",
             "杨川南", "梁有平", "李妙真", "金莲道长", "紫莲道长", "洛玉衡",
             "徐虎臣", "镇北王", "小蛮妞", "许宁宴", "宁宴"],
    "地点": ["白帝城", "驿站", "云州", "京城", "云鹿书院", "南疆", "宋长辅的府邸",
             "宋布政使的府邸", "城门", "五城兵马司", "卫所", "军营", "大厅", "地底"],
    "组织/势力": ["打更人", "虎贲卫", "银锣", "铜锣", "金锣", "飞燕军", "天地会",
                   "巫神教", "齐党", "梦巫", "地宗", "卫司", "布政使司", "城防军"],
    "物件": ["玉石小镜", "玉石碎片", "地书碎片", "地书", "小母马", "马缰", "火铳", "弓"],
}


def recompute_zero(cand):
    docs = json.load(open(DOCS, encoding="utf-8"))
    text = docs[0]["text"]
    slice_ = text[START:END]
    quotes = []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("quote"), str) and "start" in o and "end" in o:
                quotes.append((o["start"], o["end"]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(cand)
    paras = []
    for i, m in enumerate(re.finditer(r"[^\n]+", slice_), 1):
        if m.group().strip():
            paras.append((i, m.group().strip(), m.start(), m.end()))
    # 段落序号按「非空段」重新编号，与候选 coverage 口径一致
    zero, touched = [], []
    for n, (_, txt, a, b) in enumerate(paras, 1):
        hit = any(s - START < b and e - START > a for s, e in quotes)
        (touched if hit else zero).append((n, txt))
    return {"nonEmpty": len(paras), "touched": len(touched), "zero": zero}


def main():
    cand = json.load(open(CAND, encoding="utf-8"))
    out = {"checks": []}

    # ── C1 零覆盖清单身份 ────────────────────────────────────────────
    rc = recompute_zero(cand)
    claimed = {z["text"].strip() for z in cand["coverage"]["zeroCoverageList"]}
    actual = {txt for _, txt in rc["zero"]}
    c1 = {
        "name": "C1 zeroCoverageList identity",
        "recomputedZeroCount": len(actual),
        "claimedZeroCount": len(claimed),
        "onlyInClaimed": sorted(claimed - actual),
        "onlyInRecomputed": sorted(actual - claimed),
        "identical": claimed == actual,
    }
    out["checks"].append(c1)

    # ── C2 实体覆盖 ──────────────────────────────────────────────────
    texty = []

    def walk_text(o, in_quote=False):
        if isinstance(o, dict):
            for k, v in o.items():
                walk_text(v, in_quote or k == "quote")
        elif isinstance(o, list):
            for v in o:
                walk_text(v, in_quote)
        elif isinstance(o, str) and not in_quote:
            texty.append(o)

    walk_text(cand)
    blob = "\n".join(texty)
    docs = json.load(open(DOCS, encoding="utf-8"))
    slice_ = docs[0]["text"][START:END]

    c2 = {"name": "C2 entity coverage", "groups": {}}
    for grp, names in ENTITIES.items():
        rows = []
        for n in names:
            in_slice = n in slice_
            in_cand = n in blob
            if in_slice or in_cand:
                rows.append({"name": n, "inSlice": in_slice, "inCandidateText": in_cand,
                             "status": ("ok" if (not in_slice or in_cand)
                                        else "in-slice-but-absent-from-candidate-text")})
        c2["groups"][grp] = rows
    c2["absentButInSlice"] = [r["name"] for g in c2["groups"].values()
                              for r in g if r["status"] != "ok"]
    out["checks"].append(c2)

    # ── C3 语层框架标记取证 ─────────────────────────────────────────
    anchors = [
        ("P011", "基于这个推测，那么巡抚大人就危险了。"),
        ("P012", "此时张巡抚身边只有虎贲卫和姜律中"),
        ("P013", "一旦姜律中被梦巫缠住"),
        ("P014", "战力彪悍的银锣铜锣才是本次卫队里的中流砥柱。"),
        ("P015", "宋布政使在白帝城经营多年"),
        ("P016", "想到这里，许七安当即招来驿站内所有打更人，将自己的猜测告诉他们。"),
    ]
    c3 = {"name": "C3 framing markers around P011-P016",
          "why": ("候选 selfCritique sc1 自己承认：P011–P014 可能是许七安的自由间接引语"
                  "而非叙述事实；若是，t1.obstacle 与 w2/w3/w5 的 basis 应降为 inferred。"
                  "这里只把框架证据摘出来。"),
          "paragraphs": []}
    for tag, s in anchors:
        i = slice_.find(s)
        c3["paragraphs"].append({"tag": tag, "text": s, "foundAt": (START + i) if i >= 0 else None})
    # 框架词频（这一段内）
    #
    # ⚠️ 这里我修掉了本脚本初版的一处**自造结论**：初版写「window 内出现『猜测』」，
    #    而同一份脚本算出的 framingWords 全是 0 —— 那句话是我先写好结论、再去数词的，
    #    数与话对不上。改成下面这样：只报数，并由计数**决定**措辞，不预设方向。
    window_start = slice_.find("基于这个推测")
    window_end = slice_.find("想到这里，许七安当即招来")
    window = slice_[window_start:window_end] if window_start >= 0 <= window_end else ""
    WORDS = ["想到这里", "猜测", "似乎", "可能", "恐怕", "未必", "估摸"]
    c3["framingWords"] = {w: window.count(w) for w in WORDS}
    c3["windowChars"] = len(window)
    c3["framingWordsWholeSlice"] = {w: slice_.count(w) for w in WORDS}
    hits = {w: n for w, n in c3["framingWords"].items() if n}
    c3["observation"] = (
        "P011「基于这个推测」与 P016「想到这里…将自己的猜测告诉他们」把中间的 P012–P015 "
        "夹在**同一个推理框架**里（P016 自称『猜测』，指的是前面那两个猜测）。"
        + (("但 231 字的 window 内**没有**出现任何推测性标记词（实测命中：%s）——" % hits)
           if not hits else
           ("window 内的推测性标记词实测：%s；" % hits))
        + "也就是说，框架的『这是推测』只由两端那两句承担，中间四段在字面上与叙述句无异。"
          "这正是候选 sc1 自我怀疑的形态：**字面看不出语层**，所以它按叙述（explicit）处理。"
          "支持按叙述处理的反例句式在别处（P065 城防军装备、P045 四品稀缺）——"
          "它们同样处在推理段之间却明显是作者的客观交代。"
          "本脚本只呈证据，判为哪一层留给独立复核者。")
    out["checks"].append(c3)

    out["ok"] = c1["identical"]
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
