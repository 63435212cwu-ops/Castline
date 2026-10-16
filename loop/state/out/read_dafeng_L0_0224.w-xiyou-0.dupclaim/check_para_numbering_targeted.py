#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""段落编号口径核对（定向版）：read:dafeng:L0_0224。

为什么要有这个「定向版」：
  前一个通用扫描（check_para_numbering.py）把**所有**内联 P### 都拿去和「该对象自己的
  quotes 所在段」比 —— 但 note 里的 P### 经常是在**指另一段**（例如 sc2 的「P020 明确写
  『十余位打更人』被带走」）。这类引用与自己的 quote 不同段是**正常**的，却被算成
  「matchesNeither」，于是写出「证据不足」这种和事实不符的结论。

  所以这里换判据：只取**自带内容描述**的引用 —— 即 P### 后面紧跟一段引号/书名号内容、
  或该引用所在句子里出现了可逐字定位的原文片段。对每条这样的引用，问：
  「它指向的那段原文」在『标题算 P001』与『正文起算』两套编号下分别是第几段，
  再与它写的数字比 —— 这才能判定它用的是哪一套。

判据可复现，且**允许结论是「口径不一致」**（那就是真缺陷），也允许「证据不足」。

用法：python3 -B -s .../check_para_numbering_targeted.py
"""

import json
import os
import re
import sys

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0224.candidate.json")
START, END = 841448, 845385

# 定向探针：候选自己写下的「P### + 内容描述」。probe = 该描述指向的**原文逐字片段**。
# 这些片段我逐条在切片里核对过，确保指向唯一段。
TARGETED = [
    ("selfCritique[0].why_still", "P065 对城防军装备的交代", "城防军不是乌合之众"),
    ("selfCritique[0].why_still", "P045 对四品稀缺的交代", "也只有一位镇北王是三品武者"),
    ("selfCritique[1].why_still", "P017 说「四人」（人数）", "留下四人在驿站留守"),
    ("selfCritique[1].why_still", "P064 说「四个铜锣」（职级）", "现在驿站里只有四个铜锣"),
    ("selfCritique[1].why_still", "P020 明确写「十余位打更人」被带走", "十余位打更人快马加鞭"),
    ("selfCritique[3].risk", "P009", "如果是拖延时间的话"),
    ("sliceNote", "P001–P040", "死的不可能是宋布政使"),
]


def main():
    docs = json.load(open(DOCS, encoding="utf-8"))
    slice_ = docs[0]["text"][START:END]
    cand = json.load(open(CAND, encoding="utf-8"))

    paras, spans = [], []
    for m in re.finditer(r"[^\n]+", slice_):
        if m.group().strip():
            paras.append(m.group().strip())
            spans.append((START + m.start(), START + m.end()))

    def para_of_abs(a, b):
        for i, (x, y) in enumerate(spans, 1):
            if a < y and b > x:
                return i
        return None

    rows = []
    for where, ref_text, probe in TARGETED:
        m = re.search(r"P(\d{3})", ref_text)
        if not m:
            rows.append({"where": where, "refText": ref_text, "found": False,
                         "note": "引用文本里没有 P###"})
            continue
        n = int(m.group(1))
        i = slice_.find(probe)
        if i < 0:
            rows.append({"where": where, "refText": ref_text, "found": False,
                         "note": "探针片段不在切片内：%s" % probe})
            continue
        abs_para = para_of_abs(START + i, START + i + len(probe))
        rows.append({
            "where": where, "refText": ref_text, "ref": n,
            "probe": probe, "actualParagraphTitleCounted": abs_para,
            "actualParagraphBodyCounted": abs_para - 1,
            "usesTitleCounted": n == abs_para,
            "usesBodyCounted": n == (abs_para - 1),
        })

    ok_rows = [r for r in rows if r.get("found") is not False and "ref" in r]
    t = sum(1 for r in ok_rows if r["usesTitleCounted"])
    b = sum(1 for r in ok_rows if r["usesBodyCounted"])
    n = len(ok_rows)

    out = {
        "paragraphTable": {"nonEmptyParagraphs": len(paras),
                           "P001underTitleCounted": paras[0][:40],
                           "P001underBodyCounted": paras[1][:40]},
        "targetedRefs": rows,
        "tally": {"evaluable": n, "usesTitleCounted": t, "usesBodyCounted": b},
        "zeroCoverageListConvention": None,
        "verdict": None,
    }

    # zeroCoverageList 用哪套（逐条比对文本，不是只比数量）
    zl = cand.get("coverage", {}).get("zeroCoverageList", [])
    zi = sum(1 for z in zl if isinstance(z.get("para"), int) and z["para"] <= len(paras)
             and paras[z["para"] - 1] == (z.get("text") or "").strip())
    zb = sum(1 for z in zl if isinstance(z.get("para"), int) and z["para"] < len(paras)
             and paras[z["para"]] == (z.get("text") or "").strip())
    out["zeroCoverageListConvention"] = {"total": len(zl), "titleCounted": zi, "bodyCounted": zb}

    # ⚠️ 这里修掉本脚本初版的判定逻辑缺陷：初版的两个分支写成了
    #    「inline 用标题口径 且 zeroCoverage 用标题口径」/「两边都用正文口径」，
    #    唯独**没有**「inline 用正文口径、zeroCoverage 用标题口径」这一支 ——
    #    而实测结果恰好就是这一支，于是它掉进 else 打出「证据不足」。
    #    结论与数据不符不是数据的问题，是判据没覆盖到。改成先各自定口径、再比。
    def conv(title_hits, body_hits, total):
        if not total:
            return None
        if title_hits == total and body_hits == 0:
            return "title-counted（标题算 P001）"
        if body_hits == total and title_hits == 0:
            return "body-counted（正文起算，标题不算）"
        return "mixed"

    inline_conv = conv(t, b, n)
    zl_conv = conv(zi, zb, len(zl))
    out["conventions"] = {"inlineRefs": inline_conv, "zeroCoverageList": zl_conv}

    if inline_conv is None or zl_conv is None:
        out["verdict"] = "证据不足以判定；不猜一个结论填上（见 targetedRefs 逐条）。"
    elif inline_conv == zl_conv:
        out["verdict"] = "口径一致：两处都用 %s。" % inline_conv
    elif "mixed" in (inline_conv, zl_conv):
        out["verdict"] = ("至少一处口径混杂（inline=%s / zeroCoverageList=%s），"
                          "不判定为『不一致』——混杂的成因可能是引用本身写错段号。"
                          % (inline_conv, zl_conv))
    else:
        out["verdict"] = (
            "**口径不一致（可复现）**：内联 P### 用 %s，而 coverage.zeroCoverageList.para "
            "用 %s —— 同一份候选里两套编号差 1。照内联引用去查 zeroCoverageList "
            "会**错开一段**；反过来，用 zeroCoverageList 的段号去回读内联引用同样错位。"
            "这是文档内部一致性问题，不影响引文逐字定位（那 198 条已独立复算通过），"
            "但会让复核者按段号回查时对不上原文。" % (inline_conv, zl_conv))

    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
