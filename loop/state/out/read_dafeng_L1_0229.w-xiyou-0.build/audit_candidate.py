# -*- coding: utf-8 -*-
"""独立审计：只读产物 + 原文，**不 import 生成侧 content_core**，退出码即判据。

与构建脚本的分工：构建脚本保证「写盘前全部断言通过」，本脚本从**产物本身**出发
重新定位每条引文并复算，能抓到构建脚本结构上抓不到的一类问题
（例如：产物被事后改动、构建脚本与产物不同步、字段在序列化中丢失/被改写）。

判据（每条失败即 exit 1）：
  A1  sourceHash 与盘上 docs.json 实测 sha256 一致
  A2  sliceSha256 与按 sourceRange 切片的实测 sha256 一致，且切片以 unitHead 开头
  A3  深度遍历产物，**每一条** quotes[] 条目：text[start:end] == quote（全文偏移口径）
  A4  每条 quote 在切片内只出现一次（否则偏移不可复现）
  A5  每条 quote 的 sourceHash 都等于整文件 sha256
  A6  每条引文区间都落在 sourceRange 内
  A7  分析文字里的 {q 占位符残留检查（用与构建脚本同一套正则）
  A8  同一任务内五栏引文区间互不重叠
  A9  六个必需分区键都存在，且类型是 list
  A10 cost 栏不含「待验证/待核」类措辞与纸面规定当结果
  A11 semanticReview.status == not_performed
  A12 覆盖率字段与实测一致（重新按产物引文统计，不信产物自报的数）
  A13 每个 null 栏位都有同名 <栏位>Note 非空
  A14 place 有 placeState、rule 有 institution、item 有 itemStates
  A15 foreshadows：unresolved 有 payoffNote、resolved 有 payoff
  A16 courseEdges 每条有 from/to/mechanism（长度 > 30）
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0229.candidate.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]

FAIL = []
NQ = {"quotes": 0}


def fail(m):
    FAIL.append(m)
    print("[FAIL] " + m, file=sys.stderr)


QUOTE_KEYS = ("quotes", "supportQuotes", "counterQuotes")


def walk_quotes(node, path="root"):
    """递归产出所有引文条目（含带 path 便于定位）。

    **必须覆盖 supportQuotes / counterQuotes**：首版只认 `quotes` 键，
    于是 themeReadings 的引文**一条都没被 A3–A6 检查**，而覆盖率却因此少算 5 段
    （审计自报 95/254、构建自报 100/254，差的就是这几条）。
    这是审计器自己的漏洞，不是产物的：修法是补齐被检查的键集合，
    而不是去改产物里的自报数字。
    """
    if isinstance(node, dict):
        for k, v in node.items():
            if k in QUOTE_KEYS and isinstance(v, list):
                for i, q in enumerate(v):
                    yield "%s.%s[%d]" % (path, k, i), q
            else:
                yield from walk_quotes(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quotes(v, "%s[%d]" % (path, i))


def main():
    raw = DOCS.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != SOURCE_HASH:
        fail("A1 docs.json sha256 不符：%s" % got)
        return 1
    text = json.loads(raw)[0]["text"]
    cand = json.loads(CAND.read_bytes())
    S, E = cand["sourceRange"]
    slice_ = text[S:E]

    if cand["sourceHash"] != SOURCE_HASH:
        fail("A1 产物 sourceHash 字段与实测不符")
    if cand["unitHead"] not in slice_[:60]:
        fail("A2 切片不以 unitHead 开头")
    if hashlib.sha256(slice_.encode("utf-8")).hexdigest() != cand["sliceSha256"]:
        fail("A2 sliceSha256 与实测不符")

    # A3–A6
    starts = []
    for where, q in walk_quotes(cand):
        NQ["quotes"] += 1
        if not isinstance(q, dict):
            fail("A3 %s 不是对象" % where)
            continue
        if "quote" not in q or "start" not in q or "end" not in q:
            fail("A3 %s 缺 quote/start/end" % where)
            continue
        s, e, quote = q["start"], q["end"], q["quote"]
        if not isinstance(s, int) or not isinstance(e, int):
            fail("A3 %s 偏移不是整数" % where)
            continue
        if text[s:e] != quote:                                   # A3
            fail("A3 %s 偏移取回不等于 quote：%r != %r" % (where, text[s:e][:40], quote[:40]))
            continue
        if s < S or e > E:                                       # A6
            fail("A6 %s 引文区间越出 sourceRange：[%d,%d)" % (where, s, e))
        if slice_.count(quote) != 1:                             # A4
            fail("A4 %s 引文在切片内出现 %d 次（偏移不可复现）" % (where, slice_.count(quote)))
        if q.get("sourceHash") != SOURCE_HASH:                   # A5
            fail("A5 %s sourceHash 不是整文件 sha256：%r" % (where, q.get("sourceHash")))
        starts.append((s, e))

    # A7 占位符残留（与构建脚本同一套正则）
    blob = json.dumps(cand, ensure_ascii=False)
    if re.search(r"\{q\d+\}", blob):
        fail("A7 产物里仍有未替换的 {qN} 占位符")
    if re.search(r"偏移\s*\d+", blob):
        nums = {int(m) for m in re.findall(r"偏移\s*(\d+)", blob)}
        real = {s for s, _ in starts}
        bad = sorted(nums - real)
        if bad:
            fail("A7 分析文字里的手写偏移不是任何引文起点：%s" % bad)

    # A8 同一任务内五栏不重叠
    for t in cand["tasks"]:
        seen = []
        for f in ("objective", "obstacle", "action", "result", "cost"):
            cell = t.get(f)
            if not isinstance(cell, dict):
                continue
            for q in cell.get("quotes") or []:
                a, b = q["start"], q["end"]
                for a2, b2, f2 in seen:
                    if a < b2 and a2 < b:
                        fail("A8 %s：%s 与 %s 引文区间重叠" % (t["id"], f2, f))
                seen.append((a, b, f))

    # A9 分区键
    for k in SECTIONS:
        v = cand.get(k)
        if k not in cand:
            fail("A9 缺分区键 %s" % k)
        elif not isinstance(v, list):
            fail("A9 分区 %s 不是数组（本区间没有内容也应写空数组）" % k)

    # A10 cost
    for t in cand["tasks"]:
        cell = t.get("cost")
        if isinstance(cell, dict):
            s = json.dumps(cell, ensure_ascii=False)
            for bad in ("待验证", "待核", "待确认"):
                if bad in s:
                    fail("A10 %s.cost 含「%s」" % (t["id"], bad))
            if re.search(r"(法律规定|禁令)", s):
                fail("A10 %s.cost 把纸面规定当已执行结果" % t["id"])

    # A11
    if (cand.get("semanticReview") or {}).get("status") != "not_performed":
        fail("A11 semanticReview 被写成已完成")

    # A12 覆盖率复算（不信自报数）
    paras, off = [], S
    for chunk in slice_.split("\n"):
        paras.append((off, off + len(chunk), chunk))
        off += len(chunk) + 1
    nonempty = [p for p in paras if p[2].strip()]
    spans = sorted(set(starts))
    touched = sum(1 for a, b, t in nonempty if any(a < e and s < b for s, e in spans))
    cov = cand.get("coverage") or {}
    if cov.get("nonEmptyParagraphs") != len(nonempty):
        fail("A12 coverage.nonEmptyParagraphs 自报 %r，实测 %d" % (cov.get("nonEmptyParagraphs"), len(nonempty)))
    if cov.get("paragraphsTouchedByQuotes") != touched:
        fail("A12 coverage.paragraphsTouchedByQuotes 自报 %r，实测 %d"
             % (cov.get("paragraphsTouchedByQuotes"), touched))
    if cov.get("zeroCoverageParagraphs") != len(nonempty) - touched:
        fail("A12 coverage.zeroCoverageParagraphs 自报 %r，实测 %d"
             % (cov.get("zeroCoverageParagraphs"), len(nonempty) - touched))

    # A13 null 栏位必须有非空 note
    for t in cand["tasks"]:
        for f in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(f) is None and not (t.get(f + "Note") or "").strip():
                fail("A13 %s.%s 为 null 但 %sNote 缺失或为空" % (t["id"], f, f))

    # A14 worldSettings 三态字段
    for w in cand["worldSettings"]:
        if w.get("kind") == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            fail("A14 %s place 缺 placeState" % w.get("id"))
        if w.get("kind") == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            fail("A14 %s rule 缺 institution" % w.get("id"))
        if w.get("kind") == "item" and not w.get("itemStates"):
            fail("A14 %s item 缺 itemStates" % w.get("id"))

    # A15 foreshadows
    for f in cand["foreshadows"]:
        if not f.get("setup"):
            fail("A15 %s 缺 setup" % f.get("id"))
        if f.get("status") == "unresolved" and not f.get("payoffNote"):
            fail("A15 %s unresolved 缺 payoffNote" % f.get("id"))
        if f.get("status") == "resolved" and not f.get("payoff"):
            fail("A15 %s resolved 缺 payoff" % f.get("id"))

    # A16 causeEdges
    for e in cand["causeEdges"]:
        if not e.get("from") or not e.get("to") or len(e.get("mechanism") or "") <= 30:
            fail("A16 %s 缺 from/to/mechanism 或 mechanism 过短" % e.get("id"))

    print("审计引文实例：%d 条" % NQ["quotes"])
    print("不同引文串：%d 条" % len(set(starts)))
    print("覆盖非空段落：%d/%d" % (touched, len(nonempty)))
    if FAIL:
        print("\n审计失败：%d 条判据不通过" % len(FAIL), file=sys.stderr)
        return 1
    print("\n审计通过：A1–A16 全部成立")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
