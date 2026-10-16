#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""w-sanguo-1 独立反向后复核：对 read:dafeng:L3:0243 的候选做对抗性复算。

纪律：
  * **不 import** 候选作者的任何构建/校验代码（w-xiyou-0.build/ 下的东西一律不读），
    本脚本自己切段、自己 find 偏移、自己算哈希。
  * 只读，不写候选文件。
  * 判据不过就打印明细，不做静默通过。

用法：python3 -B -s loop/state/out/verify_dafeng_L3_0243.w-sanguo-1.verify/independent_check.py
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0243.candidate.json"
START, END = 983109, 988086
DECLARED_SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
DECLARED_CAND_HASH = "16af92322605edfcef0d0d265c32f3b563508e0cbf1700030470b4f731f1bdfe"

FAILS: list[str] = []
NOTES: list[str] = []


def fail(m: str) -> None:
    FAILS.append(m)


def note(m: str) -> None:
    NOTES.append(m)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def walk_quotes(node, path="$"):
    if isinstance(node, dict):
        if {"quote", "start", "end"} <= set(node):
            yield path, node
        for k, v in node.items():
            yield from walk_quotes(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quotes(v, "%s[%d]" % (path, i))


def walk_strings(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str):
                yield "%s.%s" % (path, k), v
            else:
                yield from walk_strings(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, "%s[%d]" % (path, i))


def main() -> int:
    if sha256_file(DOCS) != DECLARED_SRC_HASH:
        fail("docs.json sha256 与任务声明不符")
    if sha256_file(CAND) != DECLARED_CAND_HASH:
        fail("候选 sha256 与提交记录不符（候选已被改动？）")

    docs = json.loads(DOCS.read_text(encoding="utf-8"))
    text = docs[0]["text"]
    sl = text[START:END]
    cand = json.loads(CAND.read_text(encoding="utf-8"))

    # ── 自切段落表（不读候选的 para 字段）──────────────────────────────
    paras, off = [], START
    for ln in sl.split("\n"):
        st, en = off, off + len(ln)
        if ln.strip():
            paras.append((len(paras) + 1, ln, st, en))
        off = en + 1

    def para_of(pos):
        for n, _ln, st, en in paras:
            if st <= pos < en:
                return n
        return None

    ck = lambda name, ok, detail="": (
        None if ok else fail("%s：%s" % (name, detail)),
        print("  [%s] %s %s" % ("OK" if ok else "FAIL", name, detail if not ok else "")),
    )

    print("== 1. 边界与哈希 ==")
    ck("selfcheck head", sl.startswith("第十四章 女尸"), repr(sl[:20]))
    ck("slice length", len(sl) == 4977, str(len(sl)))

    # ── 2. 引文逐字 / 偏移 / 段号 / 哈希 / 出现次数 ─────────────────────
    print("== 2. 引文定位（%d 个对象）==" % len(list(walk_quotes(cand))))
    n_q = n_bad = n_off = n_para = n_hash = n_occ = 0
    for path, q in walk_quotes(cand):
        n_q += 1
        s, e, t = q["start"], q["end"], q["quote"]
        if text[s:e] != t:
            n_bad += 1
            fail("引文不符 %s" % path)
        if text.find(t) != s:
            n_off += 1  # 允许：候选须已声明 firstOccurrenceAt
            if q.get("startIsFirstOccurrence") is not False:
                fail("偏移非首次出现却未声明 %s" % path)
        if q.get("declaredPara") is not None and para_of(s) != q["declaredPara"]:
            n_para += 1
            fail("段号不符 %s" % path)
        if q.get("sourceHash") != DECLARED_SRC_HASH:
            n_hash += 1
            fail("sourceHash 不符 %s" % path)
        if q.get("wholeTextOccurrences") is not None:
            if text.count(t) != q["wholeTextOccurrences"]:
                n_occ += 1
                fail("全文出现次数不符 %s" % path)
        if not (START <= s and e <= END):
            fail("引文越界 %s" % path)
    print("  引文 %d；逐字不符 %d；偏移非首次 %d；段号不符 %d；哈希不符 %d；次数不符 %d"
          % (n_q, n_bad, n_off, n_para, n_hash, n_occ))
    note("偏移非首次出现的 %d 处均为全书高频短句，候选已标 startIsFirstOccurrence=false" % n_off)

    # ── 3. 五栏独立性（**用正确字段名**，这是候选脚本空转之处）─────────
    print("== 3. 五栏/三栏区间独立性（正确字段名）==")
    FIVE = ("objective", "obstacle", "action", "result", "cost")
    real_overlap, shared_str, same_para = [], [], []
    for t in cand["tasks"]:
        cols = {f: (t.get(f + "Quotes") or []) for f in FIVE}
        cols = {k: v for k, v in cols.items() if v}
        names = list(cols)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                for a in cols[names[i]]:
                    for b in cols[names[j]]:
                        if a["start"] < b["end"] and b["start"] < a["end"]:
                            real_overlap.append((t["id"], names[i], names[j]))
                        if a["quote"] == b["quote"]:
                            shared_str.append((t["id"], names[i], names[j]))
        byp = {}
        for f, v in cols.items():
            for q in v:
                byp.setdefault(para_of(q["start"]), set()).add(f)
        for p, fs in sorted(byp.items()):
            if len(fs) > 1:
                same_para.append((t["id"], p, sorted(fs)))
    ck("五栏字符区间无重叠", not real_overlap, str(real_overlap[:4]))
    ck("无同句跨栏复用", not shared_str, str(shared_str[:4]))
    print("  同段多栏（如实报数，非失败）：%d 条 %s" % (len(same_para), same_para))

    # states 三栏 —— 候选所有脚本都没查这一层
    s_overlap = []
    for s in cand["states"]:
        cols = {k: (s.get(k + "Quotes") or []) for k in ("before", "after", "anchor")}
        cols = {k: v for k, v in cols.items() if v}
        names = list(cols)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                for a in cols[names[i]]:
                    for b in cols[names[j]]:
                        if a["start"] <= b["start"] and b["end"] <= a["end"] and \
                           (a["end"] - a["start"]) > (b["end"] - b["start"]):
                            s_overlap.append((s["id"], names[i], names[j], b["quote"][:28]))
                        elif a["start"] < b["end"] and b["start"] < a["end"]:
                            s_overlap.append((s["id"], names[i], names[j], b["quote"][:28]))
    ck("states 三栏无包含/重叠", not s_overlap, str(s_overlap))

    # ── 4. null 栏必须带 Note ─────────────────────────────────────────
    print("== 4. null 栏与 Note ==")
    nulls, nonote = [], []
    for t in cand["tasks"]:
        for f in FIVE:
            if t.get(f) is None:
                nulls.append((t["id"], f))
                if not t.get(f + "Note"):
                    nonote.append((t["id"], f))
    ck("null 栏全部带 Note", not nonote, str(nonote))
    print("  null 栏 %d：%s" % (len(nulls), sorted(nulls)))

    # ── 5. worldSettings 形状 ─────────────────────────────────────────
    print("== 5. worldSettings 形状 ==")
    probs = []
    for w in cand["worldSettings"]:
        if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            probs.append((w["id"], "placeState"))
        if w["kind"] == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or not set(st) <= {"hold", "transfer", "use", "lose"}:
                probs.append((w["id"], "itemStates", st))
        if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            probs.append((w["id"], "institution"))
    ck("worldSettings 形状合法", not probs, str(probs))

    # ── 6. 行内「」必须逐字；散文里的 P/Q 引用必须存在 ─────────────────
    print("== 6. 行内引用与 P/Q 交叉引用 ==")
    bad_inline = []
    for p, v in walk_strings(cand):
        for frag in re.findall(r"「([^」]{4,})」", v):
            if frag not in text:
                bad_inline.append((p, frag[:40]))
    ck("行内「」全部逐字", not bad_inline, str(bad_inline[:4]))

    bad_ref, unreg = [], []
    reg = set(q["quote"] for _p, q in walk_quotes(cand))
    for p, v in walk_strings(cand):
        for m in re.findall(r"(?<![A-Za-z])[PQ](\d{1,3})(?!\d)", v):
            if not (1 <= int(m) <= len(paras)):
                bad_ref.append((p, m))
    ck("P/Q 引用段落均存在", not bad_ref, str(bad_ref[:4]))

    # ── 7. 随机 5 条 quote 复核（契约第 6 条）─────────────────────────
    print("== 7. 随机 5 条 quote 全文 find ==")
    qs = list(walk_quotes(cand))
    random.seed(20261012 + 243)
    for p, q in random.sample(qs, 5):
        s, e = q["start"], q["end"]
        ok = text[s:e] == q["quote"] and text.find(q["quote"]) == s
        print("  %s %s start=%d end=%d" % ("OK " if ok else "FAIL", p, s, e))
        if not ok:
            fail("随机抽样不一致 %s" % p)

    # ── 8. 反向验证：候选未覆盖的原文事实 ─────────────────────────────
    print("== 8. 反向验证（候选 blob 中是否存在这些原文事实）==")
    blob = json.dumps(cand, ensure_ascii=False)
    reverse = [
        ("P44", "巧妙的利用妹妹和母亲。"),
        ("P10", "整个浩气楼风平浪静，倒是楼内的吏员此刻陷入了慌乱。"),
        ("P52", "我要和人开发两座山峰，一条峡谷，投资几十亿金子........许七安心说。"),
        ("P50", "“啊，对了，我今晚有事，不回家了。”"),
        ("P101", "三个丫鬟应声离开。"),
        ("P110", "经门房小厮传话，得知许七安大驾光临"),
        ("P26", "恍然大悟！"),
        ("P133", "“呦，小公公今日格外客气。”"),
        ("P23", "这份天资，委实有些惊人了。"),
    ]
    for tag, q in reverse:
        i = text.find(q)
        present = q in blob
        print("  %-5s [%d,%d) exact=%s inCandidate=%s" % (tag, i, i + len(q), text[i:i + len(q)] == q, present))
        if not present:
            note("反向发现：候选未覆盖 %s" % tag)

    # ── 9. CE-A：CE03 方向断言与原文顺序 ──────────────────────────────
    print("== 9. CE03 方向断言核对 ==")
    i_q = text.find("“刚才是不是你在搞鬼。”")
    i_k = text.find("南宫倩柔知道许七安不是一般的炼神境。")
    print("  质问 at %d；她知道 at %d -> 质问在前 = %s" % (i_q, i_k, i_q < i_k))
    ce03 = cand["causeEdges"][2]
    if "紧接在质问之前" in ce03["counter"] and i_q < i_k:
        fail("CE03.counter 称『紧接在质问之前』，原文顺序相反（质问 %d < 她知道 %d）" % (i_q, i_k))

    # ── 10. CE-B：复现候选脚本的空转 ─────────────────────────────────
    print("== 10. 候选 taskFieldIntervalOverlap 判据是否空转 ==")
    vacuous = []
    for t in cand["tasks"]:
        col = t.get("objective")            # 候选脚本用的字段名
        if not isinstance(col, list):
            vacuous.append(t["id"])
    print("  t.get('objective') 不是 list 的任务数：%d/%d" % (len(vacuous), len(cand["tasks"])))
    if vacuous:
        note("候选 build/verify 脚本用 t.get('objective') 取栏位，真实字段为 objectiveQuotes ⇒ "
             "taskFieldIntervalOverlap=0 与 sameParagraphDistinctClauseSpans=[] 为真空成立")
    # 用正确字段名给出应有值
    print("  正确字段名下 sameParagraphDistinctClauseSpans 应为 %d 条 %s" % (len(same_para), same_para))
    if same_para and cand["machineSelfCheck"]["sameParagraphDistinctClauseSpans"] == []:
        fail("machineSelfCheck.sameParagraphDistinctClauseSpans 声明 []，实为 %d 条（判据空转）" % len(same_para))

    # ── 11. 覆盖率复算 ────────────────────────────────────────────────
    print("== 11. 覆盖率复算 ==")
    iv = sorted(set((q["start"], q["end"]) for _p, q in qs))
    merged = []
    for a, b in iv:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    union = sum(b - a for a, b in merged)
    nonspace = sum(1 for ch in sl if not ch.isspace())
    cov = cand["coverage"]
    ck("union cp", union == cov["quoteUnionCodepoints"], "%d vs %d" % (union, cov["quoteUnionCodepoints"]))
    ck("ratio slice", round(union / len(sl), 4) == cov["quoteUnionRatioOfSlice"], "")
    ck("ratio nonspace", round(union / nonspace, 4) == cov["quoteUnionRatioOfNonSpace"], "")
    touched = set()
    for a, b in merged:
        for n, _ln, st, en in paras:
            if a < en and b > st:
                touched.add(n)
    zero = [n for n, _ln, _st, _en in paras if n not in touched]
    ck("zero-covered 段号一致", zero == cov["zeroCoveredParagraphs"], "%s" % zero)
    ck("nonEmptyParagraphs", len(paras) == cov["paragraphs"], "%d vs %d" % (len(paras), cov["paragraphs"]))

    print()
    if FAILS:
        print("✗ 未通过 %d 条：" % len(FAILS))
        for f in FAILS:
            print("   -", f)
        return 1
    print("✓ 全部判据通过（%d 项说明见 notes）" % len(NOTES))
    for n in NOTES:
        print("   note:", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
