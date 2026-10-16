#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""w-read-4 独立复算：对已存在的候选 read_dafeng_L3_0243.candidate.json 做逐条对抗性复算。

纪律：
  * **不 import** 候选作者的任何构建/校验代码（w-xiyou-0.build/ 下的东西一律不读），
    本脚本自己切段、自己 find 偏移、自己重算哈希。
  * 只读，不写候选文件：本脚本的存在就是为了决定「该不该覆盖它」。
  * 判据不过就打印明细，不做静默通过。

用法：python3 -B -s loop/state/out/read_dafeng_L3_0243.w-read-4.verify/independent_check.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0243.candidate.json"
START, END = 983109, 988086
DECLARED_SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

FAILS: list[str] = []
NOTES: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)


def note(msg: str) -> None:
    NOTES.append(msg)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def walk_quote_objects(node, path="$"):
    """递归找出所有「引文对象」：同时含 quote / start / end 的 dict。"""
    if isinstance(node, dict):
        if {"quote", "start", "end"} <= set(node):
            yield path, node
        for k, v in node.items():
            yield from walk_quote_objects(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quote_objects(v, "%s[%d]" % (path, i))


def main() -> int:
    text = json.loads(DOCS.read_text("utf-8"))[0]["text"]
    cand = json.loads(CAND.read_text("utf-8"))

    # ── 0. 源哈希与切片口径 ────────────────────────────────────────────────
    actual_src = sha256_file(DOCS)
    if actual_src != DECLARED_SRC_HASH:
        fail("源文件 sha256 与任务声明不符：%s" % actual_src)
    sl = text[START:END]
    if not sl.startswith("第十四章 女尸"):
        fail("切片不以标题开头：%r" % sl[:40])
    if len(sl) != END - START:
        fail("切片长度 %d != %d" % (len(sl), END - START))
    note("源哈希一致；切片 %d 码点，以标题开头" % len(sl))

    # ── 1. 引文定位层：全量 226 条 ─────────────────────────────────────────
    quotes = list(walk_quote_objects(cand))
    n_ok = 0
    seen_intervals = set()
    occ_counter = Counter()
    for path, o in quotes:
        q, s, e = o["quote"], o["start"], o["end"]
        if text[s:e] != q:
            fail("[%s] text[start:end] != quote" % path)
            continue
        if e - s != len(q):
            fail("[%s] end-start=%d != len(quote)=%d" % (path, e - s, len(q)))
            continue
        # 注：**不能**要求 find(quote)==start。原文里有大量重复短句
        # （「“是！”」全文 57 次、「------------」1031 次），引文指向的是**本区间内**
        # 的那一次出现，而不是全文首次出现。候选对这两种情形都**如实**标了
        # startIsFirstOccurrence=false 与真实的 firstOccurrenceAt。
        # 第一版脚本在这里要求 find==start，报出 3 条假缺陷 —— 是**尺子**错了，不是候选错了。
        # 正确判据：start 必须是该 quote 的一次**真实**出现，且自报的
        # firstOccurrenceAt / startIsFirstOccurrence 与实测一致。
        first = text.find(q)
        if first == -1:
            fail("[%s] 原文里找不到该 quote" % path)
            continue
        if o.get("firstOccurrenceAt") is not None and o["firstOccurrenceAt"] != first:
            fail("[%s] firstOccurrenceAt 声明 %s 实测 %d" % (path, o["firstOccurrenceAt"], first))
            continue
        if o.get("startIsFirstOccurrence") is not None and o["startIsFirstOccurrence"] != (first == s):
            fail("[%s] startIsFirstOccurrence 声明 %s 实测 %s"
                 % (path, o["startIsFirstOccurrence"], first == s))
            continue
        if not (START <= s < e <= END):
            fail("[%s] 区间外：%d..%d" % (path, s, e))
            continue
        if o.get("sourceHash") != actual_src:
            fail("[%s] sourceHash 不符" % path)
            continue
        if o.get("wholeTextOccurrences") is not None:
            real = text.count(q)
            if real != o["wholeTextOccurrences"]:
                fail("[%s] wholeTextOccurrences 声明 %s 实测 %d" % (path, o["wholeTextOccurrences"], real))
                continue
            occ_counter[q] += 1
        # 区间内出现次数：按不重叠计数
        inr = len(re.findall(re.escape(q), sl))
        if o.get("occurrencesInRange") is not None and inr != o["occurrencesInRange"]:
            fail("[%s] occurrencesInRange 声明 %s 实测 %d" % (path, o["occurrencesInRange"], inr))
            continue
        n_ok += 1
        seen_intervals.add((s, e))
    note("引文对象 %d 条，逐字/偏移/唯一/区间/哈希全部通过 %d 条" % (len(quotes), n_ok))

    # ── 2. 五栏独立依据：同一任务内不得共用一句、区间不得相交 ────────────────
    FIVE = ("objective", "obstacle", "action", "result", "cost")
    shared_same_sentence = 0
    overlapping = 0
    null_without_note = 0
    task_n = 0
    for t in cand.get("tasks") or []:
        task_n += 1
        tid = t.get("id")
        col_iv: dict[str, list[tuple[int, int]]] = {}
        col_q: dict[str, set[str]] = {}
        for col in FIVE:
            qs = t.get(col + "Quotes") or []
            col_iv[col] = [(o["start"], o["end"]) for o in qs if {"start", "end"} <= set(o)]
            col_q[col] = {o["quote"] for o in qs if "quote" in o}
            if t.get(col) is None and not (t.get(col + "Note") or "").strip():
                null_without_note += 1
                fail("[%s] %s 为 null 但没有 %sNote" % (tid, col, col))
        cols = [c for c in FIVE if col_q[c]]
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                a, b = cols[i], cols[j]
                if col_q[a] & col_q[b]:
                    shared_same_sentence += 1
                    fail("[%s] %s 与 %s 共用同一句引文" % (tid, a, b))
                for (s1, e1) in col_iv[a]:
                    for (s2, e2) in col_iv[b]:
                        if s1 < e2 and s2 < e1:
                            overlapping += 1
                            fail("[%s] %s 与 %s 引文区间相交 (%d,%d)/(%d,%d)" % (tid, a, b, s1, e1, s2, e2))
    note("任务 %d 条；跨栏共用句 %d 处；跨栏区间相交 %d 处；裸 null（无 Note）%d 处"
         % (task_n, shared_same_sentence, overlapping, null_without_note))

    # ── 3. 六分区齐全 ──────────────────────────────────────────────────────
    for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
        if k not in cand:
            fail("缺分区 %s" % k)
        elif not isinstance(cand[k], list):
            fail("分区 %s 不是数组" % k)

    # ── 4. worldSettings 三区分字段合法 ────────────────────────────────────
    ws_kind = Counter()
    for i, w in enumerate(cand.get("worldSettings") or []):
        k = w.get("kind")
        ws_kind[k] += 1
        if k == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                fail("worldSettings[%d] place 缺/非法 placeState=%r" % (i, w.get("placeState")))
        elif k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st:
                fail("worldSettings[%d] item 缺 itemStates" % i)
            else:
                bad = [x for x in st if x not in ("hold", "transfer", "use", "lose")]
                if bad:
                    fail("worldSettings[%d] itemStates 非法值 %r" % (i, bad))
        elif k == "rule":
            if w.get("institution") not in ("declared", "executed", "misunderstood"):
                fail("worldSettings[%d] rule 缺/非法 institution=%r" % (i, w.get("institution")))
        else:
            fail("worldSettings[%d] kind 非法：%r" % (i, k))
        # quote 在本候选里是**引文对象**（dict，带 start/end），不是裸字符串；
        # 两种形态都接受，但都必须非空（第一版脚本在这里 AttributeError，已修）。
        q = w.get("quote")
        if isinstance(q, dict):
            if not (q.get("quote") or "").strip():
                fail("worldSettings[%d].quote 对象为空" % i)
        elif not (q or "").strip() if isinstance(q, str) else True:
            fail("worldSettings[%d] 无 quote（%r）" % (i, type(q).__name__))
        ex = w.get("explain")
        if not isinstance(ex, str) or not ex.strip():
            fail("worldSettings[%d] 无 explain（%r）" % (i, type(ex).__name__))
    note("worldSettings %d 条：%s" % (sum(ws_kind.values()), dict(ws_kind)))

    # ── 5. themeReadings：≤2 且三件齐全 ────────────────────────────────────
    th = cand.get("themeReadings") or []
    if len(th) > 2:
        fail("themeReadings 超过 2 条：%d" % len(th))
    for i, x in enumerate(th):
        for k in ("perspective", "support", "counter"):
            if not x.get(k):
                fail("themeReadings[%d] 缺 %s" % (i, k))
    note("themeReadings %d 条，perspective/support/counter 齐全" % len(th))

    # ── 6. causeEdges 有方向与触发 ─────────────────────────────────────────
    for i, e in enumerate(cand.get("causeEdges") or []):
        blob = json.dumps(e, ensure_ascii=False)
        if not any(k in e for k in ("from", "cause", "trigger", "direction")):
            fail("causeEdges[%d] 无方向字段" % i)
        if not any(k in e for k in ("mechanism", "trigger", "how", "why")):
            fail("causeEdges[%d] 无机制/触发字段" % i)
        if len(blob) < 40:
            fail("causeEdges[%d] 内容过短，疑似空壳" % i)

    # ── 7. foreshadows 状态显式 ────────────────────────────────────────────
    fs_state = Counter()
    for i, f in enumerate(cand.get("foreshadows") or []):
        st = f.get("status")
        fs_state[st] += 1
        if not st:
            fail("foreshadows[%d] 缺 status" % i)
        elif "unresolved" in str(st) and not f.get("payoff", None) is not None:
            pass  # unresolved 允许 payoff=null
    note("foreshadows %d 条：%s" % (sum(fs_state.values()), dict(fs_state)))

    # ── 8. 不得声称语义已核验 ──────────────────────────────────────────────
    if cand.get("semanticReview") not in (None, "not-performed", False):
        fail("候选声称 semanticReview=%r（红线：定位正确≠语义已核验）" % cand.get("semanticReview"))
    note("semanticReview=%r（未越权声称）" % cand.get("semanticReview"))

    # ── 9. quote 覆盖度复算（对候选自报 coverage 做独立复算）───────────────
    union = set()
    for (s, e) in seen_intervals:
        union.update(range(s, e))
    cov = cand.get("coverage") or {}
    if cov.get("quoteUnionCodepoints") is not None and cov["quoteUnionCodepoints"] != len(union):
        fail("coverage.quoteUnionCodepoints 声明 %s 实测 %d" % (cov["quoteUnionCodepoints"], len(union)))
    non_space = sum(1 for ch in sl if not ch.isspace())
    if cov.get("nonSpaceCodepoints") is not None and cov["nonSpaceCodepoints"] != non_space:
        fail("coverage.nonSpaceCodepoints 声明 %s 实测 %d" % (cov["nonSpaceCodepoints"], non_space))
    note("引文并集 %d 码点；非空白 %d；候选自报并集 %s / 非空白 %s"
         % (len(union), non_space, cov.get("quoteUnionCodepoints"), cov.get("nonSpaceCodepoints")))

    # ── 输出 ───────────────────────────────────────────────────────────────
    print("=" * 72)
    for n in NOTES:
        print("  · " + n)
    print("=" * 72)
    if FAILS:
        print("复算失败 %d 条：" % len(FAILS))
        for f in FAILS[:60]:
            print("  ✗ " + f)
        return 1
    print("全部通过：0 处不符。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
