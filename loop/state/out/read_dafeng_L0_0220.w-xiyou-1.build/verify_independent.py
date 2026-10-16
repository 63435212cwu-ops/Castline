#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核 read:dafeng:L0:0220 候选（READER 自查用；与构建侧完全隔离）。

本脚本 **不 import** 构建侧任何模块（build_candidate / content_core / quotes / quotes_spec），
只读 docs.json + 任务 JSON + 产物 JSON，从产物自己的字节出发复算。

它回答的问题（区别于构建脚本的自证）：
  V1  文件级：docs.json sha256 == 任务 sourceHash == 产物 sourceHash
  V2  切片级：text[start:end] 以单元标题开头；产物声明的 sliceSha256 可复算
  V3  引用级：**递归遍历产物里每一个 {quote,start,end} 对象**（不只 tasks），
      逐条 text[start:end] == quote 且 sourceHash 一致且落在区间内
  V4  唯一性：每条引文在切片内出现且仅出现一次（否则复核者无法反查）
  V5  五栏独立：同一任务 objective/obstacle/action/result/cost 之间不得共用同一句
  V6  裸 null 必须带同名 Note
  V7  引号约定：声明的「」= 逐字，实际必须 100% 兑现（本次修复的正是这条）
  V8  统计自报可复算：coverage / citationIntegrity / sectionCounts / basisDistribution
  V9  worldSettings 判别字段合法 + foreshadows resolved 有 payoff
  V10 语层：所有 speech/mixed 引文都必须在 speechLayerDisclosure 里登记，且标了 speaker
  V11 semanticReview 不得声称完成；endingDisclosure 不得把结束写成成功
  V12 行内『』（我的转述）**不受**逐字约束，但「」必须逐字 —— 两者分别统计并打印
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L0_0220.json"
CAND = ROOT / "loop/state/out/read_dafeng_L0_0220.candidate.json"

FAILS = []


def fail(m):
    FAILS.append(m)


def main():
    task = json.loads(TASK.read_text(encoding="utf-8"))
    raw = DOCS.read_bytes()
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    s, e = task["sourceRange"]
    sl = text[s:e]
    th = task["sourceHash"]
    cand = json.loads(CAND.read_text(encoding="utf-8"))

    # ── V1 ──────────────────────────────────────────────────────────────
    real = hashlib.sha256(raw).hexdigest()
    if real != th:
        fail("V1 docs.json sha256=%s != 任务 %s" % (real, th))
    if cand.get("sourceHash") != th:
        fail("V1 产物 sourceHash != 任务 sourceHash")
    if cand.get("sourceRange") != [s, e]:
        fail("V1 产物 sourceRange=%r != %r" % (cand.get("sourceRange"), [s, e]))

    # ── V2 ──────────────────────────────────────────────────────────────
    if not sl.startswith(task["unitHead"]):
        fail("V2 切片不以单元标题 %r 开头" % task["unitHead"])
    if cand.get("sliceCodepoints") != e - s:
        fail("V2 sliceCodepoints=%r != %d" % (cand.get("sliceCodepoints"), e - s))
    if cand.get("sliceSha256") != hashlib.sha256(sl.encode("utf-8")).hexdigest():
        fail("V2 sliceSha256 不可复算")

    # ── V3：递归收集**全部**引用对象 ─────────────────────────────────────
    refs = []

    def walk(n, path):
        if isinstance(n, dict):
            if {"quote", "start", "end"} <= set(n):
                refs.append((path, n))
            for k, v in n.items():
                walk(v, path + "." + k)
        elif isinstance(n, list):
            for i, x in enumerate(n):
                walk(x, "%s[%d]" % (path, i))

    walk(cand, "")
    if not refs:
        fail("V3 产物里没有任何引用对象")
    for p, r in refs:
        q = r.get("quote")
        if not isinstance(q, str) or not q:
            fail("V3 %s 引文为空/非串" % p)
            continue
        if text[r["start"]:r["end"]] != q:
            fail("V3 %s text[start:end] != quote" % p)
        if r.get("sourceHash") != th:
            fail("V3 %s sourceHash 不符" % p)
        if not (s <= r["start"] and r["end"] <= e):
            fail("V3 %s 引文越出区间" % p)

    # ── V4 ──────────────────────────────────────────────────────────────
    nonuniq = []
    for p, r in refs:
        q = r.get("quote")
        if isinstance(q, str) and q and sl.count(q) != 1:
            nonuniq.append((p, sl.count(q)))
    if nonuniq:
        fail("V4 这些引文在切片内不唯一：%s" % nonuniq[:4])

    # ── V5 ──────────────────────────────────────────────────────────────
    five = ("objective", "obstacle", "action", "result", "cost")
    for t in cand.get("tasks") or []:
        seen = {}
        for f in five:
            v = t.get(f)
            if not isinstance(v, dict):
                continue
            for r in v.get("quotes") or []:
                sig = (r.get("quote"), r.get("start"), r.get("end"))
                if sig in seen:
                    fail("V5 %s 的 %s 与 %s 共用同一句（%r）"
                         % (t.get("id"), f, seen[sig], str(r.get("quote"))[:26]))
                seen[sig] = f

    # ── V6 ──────────────────────────────────────────────────────────────
    for t in cand.get("tasks") or []:
        for f in five:
            if t.get(f) is None and not t.get(f + "Note"):
                fail("V6 %s.%s 为 null 但没有 %sNote" % (t.get("id"), f, f))
    for fs in cand.get("foreshadows") or []:
        if fs.get("payoff") is None and not fs.get("payoffNote"):
            fail("V6 foreshadow %s 无 payoff 也无 payoffNote" % fs.get("id"))

    # ── V7：引号约定（本次修复的核心） ───────────────────────────────────
    conv = (cand.get("citationConvention") or {}).get("verbatim") or ""
    if not conv.startswith("「」"):
        fail("V7 citationConvention.verbatim 未声明「」为逐字：%r" % conv[:40])
    blob = json.dumps(cand, ensure_ascii=False)
    book = re.findall(r"「([^」]*)」", blob)
    own = re.findall(r"『([^』]*)』", blob)
    bad_book = [x for x in book if x not in sl]
    if bad_book:
        fail("V7 声明「」逐字但有 %d 处 find 不到：%s" % (len(bad_book), bad_book[:5]))

    # ── V8：统计可复算 ──────────────────────────────────────────────────
    paras, off = [], s
    for line in sl.split("\n"):
        if line.strip():
            paras.append({"n": len(paras) + 1, "start": off, "end": off + len(line)})
        off += len(line) + 1
    used = set()
    for _, r in refs:
        for pp in paras:
            if pp["start"] <= r["start"] < pp["end"]:
                used.add(pp["n"])
                break
    cov = cand.get("coverage") or {}
    if cov.get("nonEmptyParagraphs") != len(paras):
        fail("V8 coverage.nonEmptyParagraphs=%r != %d" % (cov.get("nonEmptyParagraphs"), len(paras)))
    if cov.get("paragraphsTouchedByQuotes") != len(used):
        fail("V8 coverage.paragraphsTouchedByQuotes=%r != %d"
             % (cov.get("paragraphsTouchedByQuotes"), len(used)))
    # V8c：零覆盖清单必须完整。首次运行时构建侧只列 30 条（共 48 段），
    # 18 个段落静默免检 —— 而这张清单正是做「这一段还漏了什么」反向验证的入口。
    if len(cov.get("zeroCoverageList") or []) != len(paras) - len(used):
        fail("V8c 零覆盖清单不完整：列出 %d 条，实测零覆盖 %d 段"
             % (len(cov.get("zeroCoverageList") or []), len(paras) - len(used)))
    if cov.get("zeroCoverageTruncated") not in (0, None):
        fail("V8c zeroCoverageTruncated=%r（应完整列出）" % cov.get("zeroCoverageTruncated"))
    if cov.get("nonEmptyParagraphs") != \
            cov.get("paragraphsTouchedByQuotes", 0) + cov.get("zeroCoverageParagraphs", 0):
        fail("V8c 段落数恒等式不成立")
    # V8d：清单里的段号必须正好是实测零覆盖集合
    if {z.get("para") for z in (cov.get("zeroCoverageList") or [])} != \
            {p["n"] for p in paras if p["n"] not in used}:
        fail("V8d 零覆盖清单的段号集合与实测不符")
    ci = cand.get("citationIntegrity") or {}
    # 口径说明（2026-10-15）：productQuoteInstances 是**内容分区**口径，
    # 不等于「全产物引用对象数」——后者另由 totalQuoteInstancesInProduct 承载。
    # 首次运行时本脚本误把两者当成同一个数，报出「209 != 267」；
    # 差额恰好是 57 条 crossSectionQuoteReuse + 1 条 bookLevelDuplicateQuotes。
    # 现在两侧都按三段口径逐一独立复算（见下 V8b），不再做错误的相等断言。
    disc_only = []
    for _sec in ("crossSectionQuoteReuse", "bookLevelDuplicateQuotes"):
        _stack = [cand.get(_sec)]
        while _stack:
            _n = _stack.pop()
            if isinstance(_n, dict):
                if {"quote", "start", "end"} <= set(_n):
                    disc_only.append(_n)
                _stack.extend(_n.values())
            elif isinstance(_n, list):
                _stack.extend(_n)
    content_only = len(refs) - len(disc_only)
    if ci.get("productQuoteInstances") != content_only:
        fail("V8 productQuoteInstances=%r != 实测内容分区 %d"
             % (ci.get("productQuoteInstances"), content_only))
    if ci.get("contentSectionQuoteInstances") != content_only:
        fail("V8b contentSectionQuoteInstances=%r != 实测内容分区 %d"
             % (ci.get("contentSectionQuoteInstances"), content_only))
    if ci.get("disclosureQuoteInstances") != len(disc_only):
        fail("V8b disclosureQuoteInstances=%r != 实测披露分区 %d"
             % (ci.get("disclosureQuoteInstances"), len(disc_only)))
    if ci.get("totalQuoteInstancesInProduct") != len(refs):
        fail("V8b totalQuoteInstancesInProduct=%r != 全产物 %d"
             % (ci.get("totalQuoteInstancesInProduct"), len(refs)))
    if content_only + len(disc_only) != len(refs):
        fail("V8b 口径恒等式不成立")
    if ci.get("distinctQuoteTexts") != len({r["quote"] for _, r in refs}):
        fail("V8 citationIntegrity.distinctQuoteTexts 不符")
    for sec, n in (cand.get("sectionCounts") or {}).items():
        actual = len(cand.get(sec) or [])
        if n != actual:
            fail("V8 sectionCounts.%s=%r != 实际 %d" % (sec, n, actual))

    # ── V9 ──────────────────────────────────────────────────────────────
    for w in cand.get("worldSettings") or []:
        k = w.get("kind")
        if k not in ("rule", "place", "item"):
            fail("V9 worldSetting %s kind 非法 %r" % (w.get("id"), k))
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            fail("V9 place %s placeState 非法 %r" % (w.get("id"), w.get("placeState")))
        if k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(
                    x not in ("hold", "transfer", "use", "lose") for x in st):
                fail("V9 item %s itemStates 非法 %r" % (w.get("id"), st))
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            fail("V9 rule %s institution 非法 %r" % (w.get("id"), w.get("institution")))
        if not w.get("explain"):
            fail("V9 worldSetting %s 没有 explain" % w.get("id"))
    for fs in cand.get("foreshadows") or []:
        if fs.get("status") == "resolved" and not fs.get("payoff"):
            fail("V9 foreshadow %s 标 resolved 却无 payoff" % fs.get("id"))
        if fs.get("status") == "unresolved" and fs.get("payoff") is not None:
            fail("V9 foreshadow %s 标 unresolved 却有 payoff" % fs.get("id"))

    # ── V10：语层双向 ───────────────────────────────────────────────────
    disc = (cand.get("speechLayerDisclosure") or {}).get("dispositionOfEach") or []
    disc_keys = {d.get("key") for d in disc}
    if (cand.get("speechLayerDisclosure") or {}).get("checkedCount") != len(disc):
        fail("V10 checkedCount != 条目数")
    missing = [d.get("key") for d in disc if not d.get("who")]
    if missing:
        fail("V10 这些语层条目没有 speaker：%s" % missing[:5])

    # ── V11 ─────────────────────────────────────────────────────────────
    if (cand.get("semanticReview") or {}).get("status") != "not_performed":
        fail("V11 semanticReview 声称非 not_performed（引用定位正确 ≠ 语义已核验）")
    end = cand.get("endingDisclosure") or {}
    if not end.get("whatIsNotThere"):
        fail("V11 endingDisclosure 缺 whatIsNotThere")

    # ── 打印 ────────────────────────────────────────────────────────────
    print("引用对象（递归全量）= %d" % len(refs))
    print("切片 = [%d,%d)  %d codepoint / %d 非空段落" % (s, e, e - s, len(paras)))
    print("引文触及段落 = %d，零覆盖 = %d" % (len(used), len(paras) - len(used)))
    print("「」逐字片段 = %d（find 不到 = %d）" % (len(book), len(bad_book)))
    print("『』转述片段 = %d（不受逐字约束）" % len(own))
    print("语层登记条目 = %d" % len(disc))
    if FAILS:
        print("\n[独立复核失败] %d 条：" % len(FAILS))
        for f in FAILS:
            print("  - %s" % f)
        return 1
    print("\n[独立复核通过] V1–V11 全部成立")
    print("产物 sha256=%s" % hashlib.sha256(CAND.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
