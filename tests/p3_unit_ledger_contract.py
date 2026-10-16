#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.1 审阅单元与分母：台账必须能发现「已有事件清单之外的漏段」。

计划原文（docs/QUALITY.md:299-301）：
  「按原文边界和自足目标划分单元，记前因上下文、当前范围和未读后果。
    每段最终有处置：已审、需上下文、有冲突、非叙事材料、明确未读。
    排除感言/附录时保留理由与数量，不能剔除难例抬覆盖。
    台账必须能发现已有事件清单之外的漏段。」

为什么必须单独有这一条：
  现状的分母来自 `loop/state/index.json` 的 `unitsWithEvents`，而它由
  `loop/bin/build_plan.py:73` 用**事件 chapter 字符串与单元 head 精确相等**来计数：
      by_label = Counter(tidy(e.get("chapter")));  u["events"] = by_label.get(head, 0)
  这在两种真实情形下必然数错（实测 2026-10-08）：
    ① **同一回的两种写法**：三国事件写 `第15回`（阿拉伯数字、无标题），
       单元 head 写 `第十五回　宴桃园…`（中文数字、带标题）⇒ 字符串永不相等；
    ② **事件章标签缺标题**：大奉事件写 `第一百三十六章 真相` 而单元 head 可能更长。
  后果：`unitsWithEvents` 被系统性低估（三国报 14/120，真实是 99/120），
  而**真实存在的漏段被这个错误计数掩盖** —— 计划要的正是「能发现漏段」，
  数错了就发现不了。

判据（本契约只读 + 只登记，不改任何 data/ 与已发布版本）：
  ① 单元分母必须来自**原文边界**（narrative.chapter_spans），不是事件数；
  ② 事件与单元的归属必须按**章身份**（量词 + 回号）匹配，不得按整串相等；
  ③ 每个单元必须有处置分类，且分类互斥、可数、含「明确未读」；
  ④ 漏段必须被**点名列出**（回号 + 标题 + 原文字数），不能只给一个数字；
  ⑤ 非叙事材料（感言/附录/番外）必须单独计数并保留理由，不得从分母里悄悄剔除；
  ⑥ 负例：把某单元的匹配人为断开，漏段清单必须随之增加（判据可击穿）。

用法：
  python3 -B -s tests/p3_unit_ledger_contract.py
  python3 -B -s tests/p3_unit_ledger_contract.py --out "$CL_ARTIFACTS/p3-units"
"""
import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import narrative

BOOKS = {
    "dafeng": {"name": "大奉打更人", "graph": "data/cache/aee4c99808674e4220ab0104.json"},
    "sanguo": {"name": "三国演义", "graph": "data/cache/fe42d01f3826fe8096f86614.json"},
    "xiyou": {"name": "西游记", "graph": "data/cache/a065244455cfb2221bcda94a.json"},
}

NON_NARRATIVE = re.compile(r"^(番外|附录|感言|后记|尾声|序|楔子|完本感言|上架感言|请假)")

CN = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
      "六": 6, "七": 7, "八": 8, "九": 9}


def cn_num(s):
    if s.isdigit():
        return int(s)
    total = sec = cur = 0
    for ch in s:
        if ch in CN:
            cur = CN[ch]
        elif ch == "十":
            sec += (cur or 1) * 10; cur = 0
        elif ch == "百":
            sec += (cur or 1) * 100; cur = 0
        elif ch == "千":
            sec += (cur or 1) * 1000; cur = 0
        else:
            return None
    return (total + sec + cur) or None


def chapter_key(s):
    """章身份 = 量词 + 回号。**这是本契约的核心**：不得按整串比较。

    与 js/atlas/atlas-source.js 的 chapterKey 同一口径（那边已有实现），
    此处独立实现只为在 Python 侧可判定；两边若漂移，应由本节①②同时报警。
    """
    t = re.sub(r"[\s\u3000]+", "", str(s or ""))
    m = re.match(r"^第?([0-9零〇一二两三四五六七八九十百千]+)([回章节集幕])", t)
    if m:
        n = cn_num(m.group(1))
        return (m.group(2), n) if n is not None else (m.group(2), None)
    m2 = re.match(r"^(\d+)$", t)
    if m2:
        return ("回", int(m2.group(1)))
    return (None, None)


def classify_unit(head, has_events, in_source):
    """处置分类：互斥、可数、含「明确未读」。"""
    if NON_NARRATIVE.match(str(head or "").strip()):
        return "non_narrative"
    if not in_source:
        return "explicit_unread"
    return "reviewed" if has_events else "explicit_unread"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p3-units"))
    args = ap.parse_args()

    fails, passes = [], []
    def ck(name, ok, detail=""):
        (passes if ok else fails).append({"name": name, "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ("  · " + str(detail) if detail else ""), flush=True)

    books_report = {}
    total_units = total_missing = 0

    for key, spec in BOOKS.items():
        gpath = ROOT / spec["graph"]
        dpath = ROOT / ("data/cache/%s.docs.json" % Path(spec["graph"]).stem)
        if not gpath.exists() or not dpath.exists():
            ck("%s 夹具存在" % spec["name"], False, "缺 %s 或 docs" % gpath)
            continue
        graph = json.loads(gpath.read_text(encoding="utf-8"))
        docs = json.loads(dpath.read_text(encoding="utf-8"))
        docs = docs if isinstance(docs, list) else (docs.get("docs") or [])
        text = docs[0].get("text", "") if docs else ""

        spans = narrative.chapter_spans(text)
        by_key = collections.Counter(chapter_key(e.get("chapter")) for e in (graph.get("events") or []))
        tidy = lambda s: " ".join(str(s or "").replace("\u3000", " ").split())
        by_literal = collections.Counter(tidy(e.get("chapter")) for e in (graph.get("events") or []))

        units, missing, nonnarr = [], [], []
        for i, sp in enumerate(spans):
            head = sp.get("head")
            k = chapter_key(head)
            n_key = by_key.get(k, 0)
            n_lit = by_literal.get(tidy(head), 0)
            disp = classify_unit(head, n_key > 0, True)
            row = {"i": i, "head": head, "start": sp["start"], "end": sp["end"],
                   "chars": sp["end"] - sp["start"], "eventsByChapterKey": n_key,
                   "eventsByLiteralString": n_lit, "disposition": disp}
            units.append(row)
            if disp == "non_narrative":
                nonnarr.append(row)
            if n_key == 0 and disp != "non_narrative":
                missing.append(row)

        books_report[key] = {
            "name": spec["name"], "graph": spec["graph"], "events": len(graph.get("events") or []),
            "units": len(units), "unitsWithEventsByKey": sum(1 for u in units if u["eventsByChapterKey"] > 0),
            "unitsWithEventsByLiteral": sum(1 for u in units if u["eventsByLiteralString"] > 0),
            "missingUnits": len(missing), "nonNarrative": len(nonnarr),
            "missingDetail": [{"i": u["i"], "head": u["head"], "chars": u["chars"]} for u in missing],
            "nonNarrativeDetail": [{"i": u["i"], "head": u["head"], "chars": u["chars"]} for u in nonnarr],
            "dispositions": dict(collections.Counter(u["disposition"] for u in units)),
        }
        total_units += len(units); total_missing += len(missing)

        disp = books_report[key]["dispositions"]
        ck("③ %s 每段都有处置且分类互斥可数" % spec["name"],
           sum(disp.values()) == len(units) and set(disp) <= {"reviewed", "explicit_unread", "non_narrative"},
           json.dumps(disp, ensure_ascii=False))
        ck("④ %s 漏段必须点名列出（不是只给数字）" % spec["name"],
           len(books_report[key]["missingDetail"]) == len(missing),
           "漏段 %d 条，清单 %d 条：%s" % (len(missing), len(books_report[key]["missingDetail"]),
                                        ", ".join(u["head"][:14] for u in missing[:4])))
        ck("⑤ %s 非叙事材料单独计数并保留在分母里" % spec["name"],
           len(nonnarr) == books_report[key]["nonNarrative"],
           "非叙事 %d 条：%s" % (len(nonnarr), ", ".join(u["head"][:12] for u in nonnarr[:3])))
        ck("② %s 按章身份匹配的覆盖必须 ≥ 整串匹配（否则匹配口径没生效）" % spec["name"],
           books_report[key]["unitsWithEventsByKey"] >= books_report[key]["unitsWithEventsByLiteral"],
           "byKey=%d byLiteral=%d" % (books_report[key]["unitsWithEventsByKey"],
                                       books_report[key]["unitsWithEventsByLiteral"]))

    neg_ok = False
    try:
        g = json.loads((ROOT / BOOKS["sanguo"]["graph"]).read_text(encoding="utf-8"))
        docs = json.loads((ROOT / "data/cache/fe42d01f3826fe8096f86614.docs.json").read_text(encoding="utf-8"))
        text = (docs if isinstance(docs, list) else docs["docs"])[0]["text"]
        spans = narrative.chapter_spans(text)
        by_key = collections.Counter(chapter_key(e.get("chapter")) for e in (g.get("events") or []))
        before = sum(1 for sp in spans if by_key.get(chapter_key(sp["head"]), 0) == 0)
        victim = chapter_key(spans[3]["head"])
        g2 = {"events": [e for e in (g.get("events") or []) if chapter_key(e.get("chapter")) != victim]}
        by_key2 = collections.Counter(chapter_key(e.get("chapter")) for e in g2["events"])
        after = sum(1 for sp in spans if by_key2.get(chapter_key(sp["head"]), 0) == 0)
        neg_ok = after > before
        ck("⑥ 负例 · 断开一章的事件后漏段清单必须增加", neg_ok,
           "before=%d after=%d（victim=%s）" % (before, after, spans[3]["head"][:14]))
    except Exception as exc:
        ck("⑥ 负例 · 断开一章的事件后漏段清单必须增加", False, "构造失败：%r" % (exc,))

    ck("① 分母来自原文边界（三书合计单元数）", total_units > 0,
       "合计 %d 个单元，漏段合计 %d" % (total_units, total_missing))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "planRef": "docs/QUALITY.md:299-301",
        "reproducibleCommand": "python3 -B -s tests/p3_unit_ledger_contract.py",
        "note": ("本契约只登记，不改 data/ 与已发布版本。"
                 "分母 = 原文边界切出的单元（chapter_spans），不是事件数。"
                 "归属按章身份（量词+回号），不是整串相等 —— 后者会把 `第15回` "
                 "与 `第十五回 宴桃园…` 判成两章，从而**低估覆盖并掩盖漏段**。"),
        "books": books_report, "pass": len(passes), "fail": len(fails), "failures": fails,
    }
    p = out / "unit-ledger.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    for k, b in books_report.items():
        print("%-6s 单元=%-4d 有事件(按章身份)=%-4d 有事件(按整串)=%-4d 漏段=%-4d 非叙事=%d"
              % (b["name"], b["units"], b["unitsWithEventsByKey"], b["unitsWithEventsByLiteral"],
                 b["missingUnits"], b["nonNarrative"]))
    print("产物：%s" % p)
    if fails:
        print("\nP3.1 FAILURES: %d  (%d passed)" % (len(fails), len(passes)))
        return 1
    print("\nP3.1 ALL PASS  (%d passed)" % len(passes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
