#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""段落编号口径核对：read:dafeng:L0_0224 的 **P### 内联引用** 用的是哪一套编号。

起因（我在写 C3 取证时撞上的）：
  候选里有两种「P###」用法 ——
    ① `coverage.zeroCoverageList` 的 `para` 字段；
    ② 结论文本里内联的 `P###`（例如 selfCritique sc1 的「P065 对城防军装备的交代」）。
  我怀疑两者**不是同一套编号**（差 1：一套把标题算作 P001，一套从正文第一段算起）。
  这是可复现、可判定的问题，不该靠印象 —— 所以单独成脚本。

判据（对每条内联 P-ref）：
  取该对象自己的 quotes（内联 P-ref 就在同一对象的 text 里，指的是它引的那段原文），
  问：这些 quote 落在哪一段？
    · 若落在「标题算 P001」的第 r 段  ⇒ 该 ref 用 INCLUDED 口径
    · 若落在「正文起算」的第 r 段    ⇒ 该 ref 用 EXCLUDED 口径
  只有当对象同时带 text（含 P-ref）与 quotes 时才可判定；其余跳过并计数。

输出每一种口径的命中数。**不自动判 fail** —— 编号口径不统一本身是文档缺陷，
但哪一套「对」要由复核者按任务 prompt 的口径定。

用法：python3 -B -s .../check_para_numbering.py
"""

import json
import os
import re
import sys

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0224.candidate.json")
START, END = 841448, 845385


def main():
    docs = json.load(open(DOCS, encoding="utf-8"))
    slice_ = docs[0]["text"][START:END]
    cand = json.load(open(CAND, encoding="utf-8"))

    # 段落表（按空行切分）：paras[i] 的绝对区间 [abs_start, abs_end)
    paras, spans = [], []
    for m in re.finditer(r"[^\n]+", slice_):
        if m.group().strip():
            paras.append(m.group().strip())
            spans.append((START + m.start(), START + m.end()))
    included_title = paras[0].startswith("第两百二十三章")

    def para_of(abs_start, abs_end):
        """quote 落在第几段（1-based，含标题）。"""
        for i, (a, b) in enumerate(spans, 1):
            if abs_start < b and abs_end > a:
                return i
        return None

    def walk(o, path=""):
        if isinstance(o, dict):
            yield path, o
            for k, v in o.items():
                yield from walk(v, path + "." + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from walk(v, path + "[%d]" % i)

    rows = []
    for path, o in walk(cand):
        if not isinstance(o, dict):
            continue
        qs = o.get("quotes")
        if not isinstance(qs, list) or not qs:
            continue
        # ⚠️ 初版只扫了 `text` 字段 ⇒ 内联 P-ref 命中 0 条，险些据此写下
        #    「证据不足」的假结论。实测 P-ref 也出现在 note / mechanism / why /
        #    actorNote / costNote / obstacleNote / resultNote 里 —— 所以扫描**全部**
        #    字符串字段（排除 quote 本身，那是原文，不是候选的编号）。
        for fld, val in o.items():
            if fld == "quote" or not isinstance(val, str):
                continue
            refs = [int(m.group(1)) for m in re.finditer(r"P(\d{3})", val)]
            if not refs:
                continue
            qparas = {para_of(q["start"], q["end"]) for q in qs
                      if isinstance(q.get("start"), int)}
            qparas.discard(None)
            for r in refs:
                rows.append({"at": path + "." + fld, "ref": r,
                             "quoteParasIncludedTitle": sorted(qparas),
                             "matchesIncluded": r in qparas,
                             "matchesExcluded": (r + 1) in qparas})

    inc = [r for r in rows if r["matchesIncluded"]]
    exc = [r for r in rows if r["matchesExcluded"]]
    both = [r for r in rows if r["matchesIncluded"] and r["matchesExcluded"]]
    neither = [r for r in rows if not r["matchesIncluded"] and not r["matchesExcluded"]]

    # zeroCoverageList 用的是哪一套
    zl = cand.get("coverage", {}).get("zeroCoverageList", [])
    zl_inc = zl_exc = zl_neither = 0
    for z in zl:
        n, t = z.get("para"), (z.get("text") or "").strip()
        if not isinstance(n, int) or not t:
            continue
        if 1 <= n <= len(paras) and paras[n - 1] == t:
            zl_inc += 1
        elif 1 <= n + 1 <= len(paras) and paras[n] == t:
            zl_exc += 1
        else:
            zl_neither += 1

    out = {
        "paragraphTable": {"nonEmpty": len(paras), "titleIsP001": included_title,
                           "firstPara": paras[0][:40]},
        "inlineRefs": {
            "total": len(rows),
            "matchesTitleIncluded": len(inc),
            "matchesTitleExcluded": len(exc),
            "matchesBoth": len(both),
            "matchesNeither": len(neither),
            "neitherSamples": [{"at": r["at"], "ref": r["ref"],
                                "quoteParas": r["quoteParasIncludedTitle"]}
                               for r in neither[:6]],
        },
        "zeroCoverageList": {
            "total": len(zl),
            "matchesTitleIncluded": zl_inc,
            "matchesTitleExcluded": zl_exc,
            "matchesNeither": zl_neither,
        },
        "verdict": None,
    }
    # 结论只在数据支持时才下
    if len(inc) and not len(exc) and zl_inc and not zl_exc:
        out["verdict"] = ("口径不统一（可复现）：内联 P### 用『正文起算』（EXCLUDED），"
                          "zeroCoverageList.para 用『标题算 P001』（INCLUDED）——两套差 1。"
                          "同一份文档里两种编号，照内联引用去查段落会**错开一段**。")
    elif len(inc) and not len(exc) and not zl_inc:
        out["verdict"] = "两处都用 INCLUDED，口径一致。"
    elif len(exc) and not len(inc) and zl_exc:
        out["verdict"] = "两处都用 EXCLUDED，口径一致。"
    else:
        out["verdict"] = ("证据不足以判定统一口径（见各计数）；"
                          "不猜一个结论填上。")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
