#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1 来源去重：同 ID 同 hash 只建一份索引，冲突保留，不同 ID 不自动合并。

计划原文（docs/QUALITY.md:255-257）：
  「同ID同hash仅建一份索引；同ID异hash保持冲突；不同ID同文不自动合并。
    保留文档列表与映射。验收38字符场景：重复导入不得膨胀成3048字符整章，
    200字符预算仍应包含事件原句。再测空源、同路径不同文、同文不同版和异常编码。」

为什么必须单独有这一条：
  `tests/narrative_context_contract.py` 已经覆盖了重复导入的**单元行为**
  （40 项，含 38 字符场景）。本契约不重复它，只回答那个测试回答不了的问题：
  **这套去重是不是真的接在生产请求路径上。**
  实测（2026-10-08）：`NARRATIVE.plan` 由 `serve.py:5246 enrichment_plan()` 调用，
  而 `enrichment_plan` 由 HTTP 路由 `POST /api/enrich/plan`（serve.py:6951）暴露 ⇒
  是活路径。若哪天它退化成只有测试可达，本契约会红 —— 这正是本项目最贵的形态
  「机制存在、有产出、但不产生信息」。

判据（三层，逐层可被击穿）：
  ① **纯函数层**：四种情形各按计划处置（同ID同hash→1 份；同ID异hash→0 份且保留冲突；
     不同ID同文→2 份不合并；空源→0 份不抛异常）。
  ② **38 字符场景**：200 字符预算下窗口不得膨胀成整章，且事件原句必须仍在窗口里。
  ③ **生产路径层**：`serve.py` 必须真的调用 `NARRATIVE.plan`，且 HTTP 路由
     `/api/enrich/plan` 必须存在并返回带 `sourceContext.coverage` 的结构化字段
     （`sourceIdentityConflicts` / `missingSources` 必须如实出现，不能只在测试里）。

用法：
  python3 -B -s tests/p2_source_dedup_contract.py
  python3 -B -s tests/p2_source_dedup_contract.py --base http://127.0.0.1:8781  # 加跑 HTTP 层
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import narrative as N

QUOTE = "城门守卫把来访者带到议事厅里，认真核对名册上的姓名和来访缘由。"
LONG = "原文描写。" * 600
RAW = "第一回 长章\n\n" + LONG + "\n\n" + QUOTE + "\n\n本场结束。"
EVENT = {"id": "event-dup", "chapter": "第一回", "quote": QUOTE, "quoteVerified": False}

fails, passes = [], []


def ck(name, ok, detail=""):
    (passes if ok else fails).append({"name": name, "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + ("  · " + str(detail) if detail else ""), flush=True)


def index_of(docs):
    specs = N.context_sources(docs)
    return specs, N.ContextIndex(specs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--skip-http", action="store_true")
    ap.add_argument("--book", default="1063b17ca65ec1b76f30e460")
    args = ap.parse_args()

    # ---- ① 四种情形 ---------------------------------------------------------
    spec1, idx1 = index_of([{"sourceId": "s1", "text": RAW}, {"sourceId": "s1", "text": RAW}])
    ck("①a 同ID同hash只建一份索引（重复导入不产生第二处）",
       len(idx1.sources) == 1,
       "specs=%d index=%d" % (len(spec1), len(idx1.sources)))

    spec2, idx2 = index_of([{"sourceId": "s1", "text": RAW}, {"sourceId": "s1", "text": RAW + "\n改了一句。"}])
    ck("①b 同ID异hash保持冲突（不得静默择一）",
       len(idx2.sources) == 0 and len({s["id"] for s in spec2}) == 1,
       "specs=%d（同 id 两个 hash）index=%d ⇒ 冲突被排除而非任选" % (len(spec2), len(idx2.sources)))

    spec3, idx3 = index_of([{"sourceId": "s1", "text": RAW}, {"sourceId": "s2", "text": RAW}])
    ck("①c 不同ID同文不自动合并（两个来源各自保留）",
       len(idx3.sources) == 2,
       "index=%d，ids=%s" % (len(idx3.sources), sorted({s["id"] for s in spec3})))

    spec4, idx4 = index_of([])
    ck("①d 空源不抛异常且索引为空", len(idx4.sources) == 0,
       "specs=%d index=%d" % (len(spec4), len(idx4.sources)))

    ck("①e 负例 · 判据本身可击穿（同文不同ID 若被合并成 1 份则应判否）",
       len(idx3.sources) != 1,
       "实测 index=%d，若为 1 则本条会红" % len(idx3.sources))

    # ---- ② 38 字符场景（计划点名的验收） ------------------------------------
    import unittest.mock as mock
    with mock.patch.object(N, "SOURCE_CHARS", 200):
        windows, cov = N.source_windows([EVENT], spec1, details=True, context_index=idx1)
        lens = [len(w["text"]) for w in windows]
        ck("②a 重复导入不得把 38 字符场景膨胀成整章",
           bool(lens) and max(lens) < len(RAW),
           "窗口字数=%s（整章=%d）" % (lens, len(RAW)))
        ck("②b 200 字符预算下事件原句仍必须在窗口里",
           any(QUOTE in w["text"] for w in windows),
           "窗口数=%d" % len(windows))
        ck("②c 窗口必须是原文的**逐字切片**（不得重排/改写）",
           all(w["text"] == RAW[w["start"]:w["end"]] for w in windows),
           "逐字切片校验通过" if windows else "无窗口")

    # ---- ③ 生产路径 ---------------------------------------------------------
    serve = (ROOT / "serve.py").read_text(encoding="utf-8")
    ck("③a 生产入口必须真的调用 NARRATIVE.plan（不能只在测试里可达）",
       bool(re.search(r"NARRATIVE\.plan\(", serve)),
       "serve.py 出现 NARRATIVE.plan( 调用" if re.search(r"NARRATIVE\.plan\(", serve) else "未找到调用")
    ck("③b enrichment_plan 必须由 HTTP 路由暴露",
       "/api/enrich/plan" in serve and "enrichment_plan(" in serve,
       "serve.py 含 /api/enrich/plan 路由与 enrichment_plan()")

    if not args.skip_http:
        try:
            req = urllib.request.Request(
                args.base.rstrip("/") + "/api/enrich/plan",
                data=json.dumps({"key": args.book, "layers": ["tasks"], "sourceOnly": True}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as fh:
                live = json.loads(fh.read().decode("utf-8"))
            cov2 = ((live.get("sourceContext") or {}).get("coverage") or {})
            ck("③c 线上接口必须返回结构化覆盖字段（含冲突与缺源两项）",
               ("sourceIdentityConflicts" in cov2) and ("missingSources" in cov2)
               and isinstance(cov2.get("originalChars"), int) and cov2["originalChars"] > 0,
               "originalChars=%s conflicts=%s missingSources=%s"
               % (cov2.get("originalChars"), cov2.get("sourceIdentityConflicts"), cov2.get("missingSources")))
        except Exception as exc:
            ck("③c 线上接口必须返回结构化覆盖字段", False, "请求失败：%r" % (exc,))

    print()
    if fails:
        print("P2.1 FAILURES: %d  (%d passed)" % (len(fails), len(passes)))
        return 1
    print("P2.1 ALL PASS  (%d passed)" % len(passes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
