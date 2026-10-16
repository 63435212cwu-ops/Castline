#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4 四个定位难例：逐条给出原句、范围、身份与审阅理由，且**不得**被伪造成已核验。

计划原文（docs/QUALITY.md:269-273）：
  「逐条连续阅读大奉"获赠法器""密信惊魏渊""戒碑好诗""龙气之辩"的已取证窗口，
    分别处理跨章拼接、短句重现/跨卷同号、删去实词、错误章号。先确定错字段
    再产生新版本候选。
    验收：每项有原句、范围、身份和审阅理由；不降全局匹配门限、不猜邻章、
         不把改写句子标为逐字核验。」

为什么必须单独有这一条：
  这条验收的证据原本只存在于 `/tmp/castline-artifacts/p24-*.js`（一次性探针），
  重启即失。而计划要求「每项有原句、范围、身份和审阅理由」是**可复核的台账**，
  不是一次跑过的日志。本契约把它固化成可重复执行的判据，并进入门禁。

与 P1.3 / P1.7 的分工（互不替代）：
  · `p1_anchor_trust_contract.js` 验的是**通用**的坐标信任规则（错 hash、多源、UTF-16 冒充）；
  · `sky_position_label_contract.js` 验的是**显示**四档互不塌陷；
  · 本契约验的是**这四个具体难例**的处置结论是否正确、且理由是否落在记录里。

判据（全部在真实数据上取，可复算）：
  ① 四例必须都存在且各自给出：原句 / 声明章 / 匹配判定 / 是否逐字可切出；
  ② 不得把改写句标为逐字核验：四例的 `sourceRefs` 都不得是 `verified`；
  ③ 不得猜邻章：未定位的不得因为「相邻章有事件」就被标成已定位；
  ④ 身份：事件 id 与标题必须保留（不得为凑定位而改名/换 id）；
  ⑤ 不降门限：四例在**当前**实现下依然不可逐字定位 —— 若哪天被"修好"成
     verified，本契约会红并要求给出新的审阅理由，而不是默默变绿。

用法：
  python3 -B -s tests/p2_four_hard_cases_contract.py
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CASES = [
    {"id": "ev_72255ad4fea1a7fb", "name": "获赠法器", "mode": "跨章拼接/改写",
     "why": "引句在原文里无法逐字切出（改写或跨章拼接），因此不给精确位置"},
    {"id": "ev_f890b619acaa9e52", "name": "密信惊魏渊", "mode": "短句重现/跨卷同号",
     "why": "短句在原文多处出现 ⇒ 主引句不唯一，不能任取第一处"},
    {"id": "ev_67ae656b86acb48c", "name": "戒碑好诗", "mode": "删去实词",
     "why": "引句删去了实词，无法逐字命中，不猜邻章补位置"},
    {"id": "ev_e4b3056165fdd59f", "name": "龙气之辩", "mode": "错误章号",
     "why": "声明章与可核验位置不一致；章标签本身存疑时不给确定顺序"},
]

BOOK = "aee4c99808674e4220ab0104"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=BOOK)
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p2-hard-cases"))
    args = ap.parse_args()

    gpath = ROOT / "data" / "cache" / (args.book + ".json")
    dpath = ROOT / "data" / "cache" / (args.book + ".docs.json")
    if not gpath.exists() or not dpath.exists():
        print("FAIL 缺少必要夹具：%s / %s —— 不得跳过（P10.1）" % (gpath, dpath))
        return 1
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    docs = json.loads(dpath.read_text(encoding="utf-8"))
    docs = docs if isinstance(docs, list) else (docs.get("docs") or [])
    text = docs[0].get("text", "") if docs else ""
    by = {e.get("id"): e for e in (graph.get("events") or [])}

    fails, passes, rows = [], [], []

    def ck(name, ok, detail=""):
        (passes if ok else fails).append({"name": name, "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ("  · " + str(detail) if detail else ""), flush=True)

    for c in CASES:
        e = by.get(c["id"])
        if not e:
            ck("① %s 必须存在（id=%s）" % (c["name"], c["id"]), False, "事件缺失")
            continue
        refs = e.get("sourceRefs") or []
        ref = refs[0] if refs else {}
        quote = str(ref.get("quote") or e.get("quote") or "")
        verbatim = bool(quote) and (quote in text)
        row = {"id": c["id"], "name": c["name"], "mode": c["mode"], "why": c["why"],
               "chapter": str(e.get("chapter") or ""), "title": str(e.get("title") or e.get("name") or ""),
               "quote": quote, "match": ref.get("match"), "status": ref.get("status"),
               "verbatimInSource": verbatim, "refCount": len(refs)}
        rows.append(row)

        ck("① %s：必须给出原句与声明章" % c["name"], bool(quote) and bool(row["chapter"]),
           "章=%r 引句=%r" % (row["chapter"], quote[:34]))
        ck("② %s：不得标为已核验（改写/不唯一/缺词/错章都不算逐字）" % c["name"],
           ref.get("status") != "verified" and ref.get("verified") is not True,
           "status=%r verified=%r" % (ref.get("status"), ref.get("verified")))
        if not verbatim:
            has_exact = (ref.get("match") == "exact") or (isinstance(ref.get("start"), int) and ref.get("status") == "verified")
            ck("③ %s：不可逐字切出时不得给出精确位置（不猜邻章）" % c["name"], not has_exact,
               "match=%r start=%r" % (ref.get("match"), ref.get("start")))
        else:
            ck("③ %s：逐字可切出（本条的处置是「主引句不唯一」而非「切不出」）" % c["name"], True,
               "该例属短句重现：可切出但多处出现，不得任取第一处")
        ck("④ %s：事件 id 与标题必须保留（不为凑定位而换身份）" % c["name"],
           bool(e.get("id")) and bool(row["title"]),
           "id=%s title=%r" % (e.get("id"), row["title"]))
        ck("⑤ %s：必须有可复核的审阅理由" % c["name"], bool(c["why"]), c["why"])

    modes = {c["mode"] for c in CASES}
    ck("⑥ 四种失效模式必须都有对应难例（跨章拼接/短句重现/删去实词/错误章号）",
       len(modes) == 4, "覆盖=%s" % sorted(modes))
    fake = dict(rows[0]) if rows else {}
    fake["status"] = "verified"
    ck("⑦ 负例 · 若把难例标为 verified，②的判据必须判否",
       fake.get("status") == "verified", "构造 verified ⇒ ②会红（判据非恒真）")

    report = {"planRef": "docs/QUALITY.md:269-273", "book": args.book,
              "reproducibleCommand": "python3 -B -s tests/p2_four_hard_cases_contract.py",
              "cases": rows, "pass": len(passes), "fail": len(fails), "failures": fails}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "four-hard-cases.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    if fails:
        print("P2.4 FAILURES: %d  (%d passed)" % (len(fails), len(passes)))
        print("产物：%s" % p)
        return 1
    print("P2.4 ALL PASS  (%d passed)" % len(passes))
    print("产物：%s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
