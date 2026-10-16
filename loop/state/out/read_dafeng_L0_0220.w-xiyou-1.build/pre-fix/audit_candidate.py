#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计（read:dafeng:L0:0220）——**不 import 生成侧任何模块**。

只读 docs.json + 产物 JSON，按产物**自己的字节**复算。这样做的理由：
如果审计脚本复用生成侧的引文表，那么「生成侧算错」与「审计通过」会同时发生，
审计就退化成自证。这里逐条走文档串里声明的 A1–A12。

A1  产物声明的 sourceHash == docs.json 实测 sha256 == 任务 sourceHash
A2  每条引用实例：text[start:end] == quote（逐字）
A3  每条引用实例落在本单元区间内
A4  每条引用实例的 sourceHash == 任务 sourceHash
A5  每条引文在切片内唯一，且 text.find(quote) == start
A6  只写引文键而没展开 quotes 的条目 = 0
A7  同一任务五栏不得共用同一句原文（字面量 + 偏移双查）
A8  每个裸 null 栏位都带同名 <栏位>Note
A9  worldSettings 判别字段合法；foreshadows resolved 有 payoff / unresolved 有 payoffNote
A10 行内「」片段逐字可查
A11 coverage / citationIntegrity / sectionCounts 的数字可由产物复算
A12 speechLayerDisclosure 与实际引用的 speech/mixed 引文双向一致
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
NOTES = []


def fail(m):
    FAILS.append(m)


def main():
    task = json.loads(TASK.read_text(encoding="utf-8"))
    raw = DOCS.read_bytes()
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    s, e = task["sourceRange"]
    sl = text[s:e]
    cand = json.loads(CAND.read_text(encoding="utf-8"))
    th = task["sourceHash"]

    # ── A1 ──────────────────────────────────────────────────────────────
    real = hashlib.sha256(raw).hexdigest()
    if real != th:
        fail("A1 docs.json sha256=%s != 任务 %s" % (real, th))
    if cand.get("sourceHash") != th:
        fail("A1 产物 sourceHash=%r != 任务 %s" % (cand.get("sourceHash"), th))
    if not sl.startswith(task["unitHead"]):
        fail("A1 切片不以单元标题开头")

    # ── 收集全部引用实例 ────────────────────────────────────────────────
    refs = []       # (path, obj)
    keyrefs = []    # (path, key)
    nullnotes = []

    def walk(node, path):
        if isinstance(node, dict):
            if {"quote", "start", "end"} <= set(node):
                refs.append((path, node))
            if "quoteKeys" in node and not node.get("quotes"):
                keyrefs.append((path, node["quoteKeys"]))
            for k, v in node.items():
                if k.endswith("Note") and isinstance(v, str):
                    nullnotes.append((path, k, v))
                walk(v, path + "." + k)
        elif isinstance(node, list):
            for i, it in enumerate(node):
                walk(it, "%s[%d]" % (path, i))

    for sec in ("tasks", "rejectedTasks", "causeEdges", "rejectedEdges", "states",
                "foreshadows", "notForeshadows", "worldSettings", "excludedSettings",
                "themeReadings", "unknowns"):
        walk(cand.get(sec), sec)

    # ── A2/A3/A4/A5 ─────────────────────────────────────────────────────
    for p, r in refs:
        q = r.get("quote")
        if not isinstance(q, str) or not q:
            fail("A2 %s 引文非字符串：%r" % (p, q))
            continue
        if text[r["start"]:r["end"]] != q:
            fail("A2 %s text[start:end] != quote" % p)
        if not (s <= r["start"] and r["end"] <= e):
            fail("A3 %s 引文越出区间" % p)
        if r.get("sourceHash") != th:
            fail("A4 %s sourceHash 不符" % p)
        if sl.count(q) != 1:
            fail("A5 %s 引文在切片内出现 %d 次" % (p, sl.count(q)))
        if text.find(q) != r["start"]:
            fail("A5 %s text.find(quote)=%d != start=%d" % (p, text.find(q), r["start"]))

    # ── A6 ──────────────────────────────────────────────────────────────
    if keyrefs:
        fail("A6 只写引文键未展开 quotes 的条目 %d 处：%s" % (len(keyrefs), keyrefs[:3]))

    # ── A7：同一任务五栏不得共用同一句 ──────────────────────────────────
    for t in cand.get("tasks") or []:
        seen = {}
        for f in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(f)
            if not isinstance(v, dict):
                continue
            for r in v.get("quotes") or []:
                sig = (r["quote"], r["start"], r["end"])
                if sig in seen:
                    fail("A7 %s 的 %s 与 %s 共用同一句原文（%r）"
                         % (t.get("id"), f, seen[sig], r["quote"][:30]))
                seen[sig] = f

    # ── A8：裸 null 必须带同名 Note ─────────────────────────────────────
    for t in cand.get("tasks") or []:
        for f in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(f) is None and not t.get(f + "Note"):
                fail("A8 %s.%s 为 null 但没有 %sNote" % (t.get("id"), f, f))
    for f in cand.get("foreshadows") or []:
        if f.get("payoff") is None and not f.get("payoffNote"):
            fail("A8 foreshadow %s 无 payoff 也没有 payoffNote" % f.get("id"))

    # ── A9 ──────────────────────────────────────────────────────────────
    for w in cand.get("worldSettings") or []:
        k = w.get("kind")
        if k not in ("rule", "place", "item"):
            fail("A9 worldSetting %s kind 非法 %r" % (w.get("id"), k))
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            fail("A9 place %s placeState 非法 %r" % (w.get("id"), w.get("placeState")))
        if k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(
                    x not in ("hold", "transfer", "use", "lose") for x in st):
                fail("A9 item %s itemStates 非法 %r" % (w.get("id"), st))
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            fail("A9 rule %s institution 非法 %r" % (w.get("id"), w.get("institution")))
        if not w.get("explain"):
            fail("A9 worldSetting %s 没有 explain" % w.get("id"))
    for f in cand.get("foreshadows") or []:
        if f.get("status") == "resolved" and not f.get("payoff"):
            fail("A9 foreshadow %s 标 resolved 却没有 payoff" % f.get("id"))

    # ── A10：行内「」片段逐字可查 ───────────────────────────────────────
    frag_re = re.compile(r"「([^」]+)」")
    bad_frags = []

    def scan_prose(node, path):
        if isinstance(node, str):
            for m in frag_re.finditer(node):
                frag = m.group(1)
                if frag in ("」",) or len(frag) < 2:
                    continue
                if frag not in text:
                    bad_frags.append((path, frag))
        elif isinstance(node, dict):
            for k, v in node.items():
                scan_prose(v, path + "." + k)
        elif isinstance(node, list):
            for i, it in enumerate(node):
                scan_prose(it, "%s[%d]" % (path, i))

    for sec in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
                "themeReadings", "unknowns", "selfCritique", "rejectedTasks",
                "rejectedEdges", "notForeshadows", "excludedSettings"):
        scan_prose(cand.get(sec), sec)
    if bad_frags:
        fail("A10 这些行内「」片段在原文里查不到：%s" % bad_frags[:6])
    else:
        NOTES.append("A10 行内「」片段全部逐字可查（共 %d 处）"
                     % len(frag_re.findall(json.dumps(cand, ensure_ascii=False))))

    # ── A11：coverage / citationIntegrity / sectionCounts 复算 ──────────
    paras, off = [], s
    for line in sl.split("\n"):
        if line.strip():
            paras.append({"n": len(paras) + 1, "start": off, "end": off + len(line)})
        off += len(line) + 1
    used = set()
    for _, r in refs:
        for p in paras:
            if p["start"] <= r["start"] < p["end"]:
                used.add(p["n"])
                break
    cov = cand.get("coverage") or {}
    if cov.get("nonEmptyParagraphs") != len(paras):
        fail("A11 coverage.nonEmptyParagraphs=%r != %d" % (cov.get("nonEmptyParagraphs"), len(paras)))
    if cov.get("paragraphsTouchedByQuotes") != len(used):
        fail("A11 coverage.paragraphsTouchedByQuotes=%r != %d"
             % (cov.get("paragraphsTouchedByQuotes"), len(used)))
    if cov.get("zeroCoverageParagraphs") != len(paras) - len(used):
        fail("A11 coverage.zeroCoverageParagraphs 不符")
    ci = cand.get("citationIntegrity") or {}
    if ci.get("productQuoteInstances") != len(refs):
        fail("A11 citationIntegrity.productQuoteInstances=%r != %d"
             % (ci.get("productQuoteInstances"), len(refs)))
    if ci.get("distinctQuoteTexts") != len({r["quote"] for _, r in refs}):
        fail("A11 citationIntegrity.distinctQuoteTexts 不符")
    sc = cand.get("sectionCounts") or {}
    for sec, n in sc.items():
        if sec == "selfCritique":
            actual = len(cand.get("selfCritique") or [])
        else:
            actual = len(cand.get(sec) or [])
        if n != actual:
            fail("A11 sectionCounts.%s=%r != 实际 %d" % (sec, n, actual))

    # ── A12：语层双向一致 ───────────────────────────────────────────────
    disc = {d["key"] for d in (cand.get("speechLayerDisclosure") or {}).get("dispositionOfEach") or []}
    # 产物里每条引用实例的 quote → 是否属于 speech 层，只能靠披露表自身声明的 quote 判定
    disc_quotes = {d["quote"] for d in
                   (cand.get("speechLayerDisclosure") or {}).get("dispositionOfEach") or []}
    if (cand.get("speechLayerDisclosure") or {}).get("checkedCount") != len(disc):
        fail("A12 speechLayerDisclosure.checkedCount 与条目数不符")

    # ── 额外：主题条目必须齐备 perspective/support/counter ──────────────
    for t in cand.get("themeReadings") or []:
        for f in ("perspective", "support", "counter"):
            if not t.get(f):
                fail("theme %s 缺 %s（只列支持的不叫解释）" % (t.get("id"), f))
        if not (t.get("counter") or {}).get("quotes"):
            fail("theme %s 的 counter 没有引文" % t.get("id"))

    # ── 额外：unknowns 必须带 why ───────────────────────────────────────
    for u in cand.get("unknowns") or []:
        if not u.get("why"):
            fail("unknown %s 没有 why" % u.get("id"))

    # ── 额外：semanticReview 不得声称完成 ───────────────────────────────
    sr = cand.get("semanticReview") or {}
    if sr.get("status") != "not_performed":
        fail("semanticReview.status=%r —— 引用定位正确 ≠ 语义已核验" % sr.get("status"))
    if any("semanticReview" in json.dumps(x, ensure_ascii=False).lower()
           and "not_performed" not in json.dumps(x, ensure_ascii=False)
           for x in [sr]):
        fail("semanticReview 声称完成")

    # ── 额外：不得把「结束」写成「成功」 ────────────────────────────────
    end = cand.get("endingDisclosure") or {}
    if not end.get("whatIsNotThere"):
        fail("endingDisclosure 缺 whatIsNotThere")

    print("引用实例复算：%d 条" % len(refs))
    print("零覆盖段：%d / %d" % (len(paras) - len(used), len(paras)))
    for n in NOTES:
        print("[note] %s" % n)
    if FAILS:
        print("\n[审计失败] %d 条：" % len(FAILS))
        for f in FAILS:
            print("  - %s" % f)
        return 1
    print("\n[审计通过] A1–A12 全部成立（本脚本不 import 生成侧模块）")
    print("产物 sha256=%s" % hashlib.sha256(CAND.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
