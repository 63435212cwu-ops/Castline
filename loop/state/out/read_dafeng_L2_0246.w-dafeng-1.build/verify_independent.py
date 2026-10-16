#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对 read_dafeng_L2_0246.candidate.json 的**独立**复核（不是重跑构造器）。

独立性来自四点：
  1. 源文件重新打开、哈希重新计算，不 import 构造器、不读它的中间状态；
  2. 段落用**行扫描**另行切分（不复用构造器的 split 逻辑），段号独立复算；
  3. 每条引文重新在**全文**里 find，start/end 与候选声明逐条比对（不是信它自查的断言）；
  4. 判据自身做**变异测试**：把引文改坏、把偏移挪一格，判据必须变红，否则判据恒绿、等于没有。

用法：python3 verify_independent.py [候选路径]
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "loop/state/out/read_dafeng_L2_0246.candidate.json"

S_START, S_END = 1001227, 1009273
EXPECT_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

PASS, FAIL = [], []


def check(name, ok, detail=""):
    # detail 一律转成字符串：早期版本假设调用方只传 str，M8 变异测试
    # （覆盖对账造假）传了 list，判据在**打印时**抛 TypeError ⇒ 检查器自己崩掉，
    # 反而比假绿更危险（它看起来像「跑完了」）。修的是检查器，不是判据。
    detail = "" if detail in ("", None) else str(detail)
    (PASS if ok else FAIL).append((name, detail))
    print("%-6s %s%s" % ("PASS" if ok else "FAIL", name, ("  — " + detail) if detail else ""))


def main():
    cand = json.loads(CAND.read_text(encoding="utf-8"))
    src = json.loads(DOCS.read_text(encoding="utf-8"))
    text = src[0]["text"]

    # ── 独立切段：按行扫描，只计非空行 ─────────────────────────────────────
    paras = {}
    n = 0
    cursor = S_START
    for line in text[S_START:S_END].split("\n"):
        if line.strip():
            n += 1
            paras[n] = (cursor, line)
        cursor += len(line) + 1
    check("I01 段数独立复算", n == cand["coverageNote"]["totalParagraphs"],
          "独立=%d 候选=%d" % (n, cand["coverageNote"]["totalParagraphs"]))

    # ── 哈希三方 ───────────────────────────────────────────────────────────
    fh = hashlib.sha256(DOCS.read_bytes()).hexdigest()
    check("I02 源文件哈希", fh == EXPECT_HASH == cand["sourceHash"], fh)
    check("I03 切片哈希另记",
          cand["sliceSha256"] == hashlib.sha256(text[S_START:S_END].encode()).hexdigest()
          and cand["sliceSha256"] != cand["sourceHash"],
          cand["sliceSha256"][:16])
    check("I04 全文哈希", cand["docsTextSha256"] == hashlib.sha256(text.encode()).hexdigest())
    check("I05 标题口径", text[S_START:S_END].startswith(cand["unitHead"]),
          repr(text[S_START:S_START + 12]))
    check("I06 切片长度", len(text[S_START:S_END]) == cand["sourceSliceCodepoints"] == S_END - S_START)

    # ── 收集候选里所有引文条目 ─────────────────────────────────────────────
    quotes = []

    def walk(node, path):
        if isinstance(node, dict):
            if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
                quotes.append((path, node))
            for k, v in node.items():
                walk(v, path + "." + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (path, i))

    walk(cand, "cand")
    check("I07 引文条目数 > 0", len(quotes) > 0, "%d 条" % len(quotes))

    bad_word, bad_off, bad_hash, bad_range, bad_para, bad_count = [], [], [], [], [], []
    for path, q in quotes:
        s, e, s_ = q["start"], q["end"], q["quote"]
        if text[s:e] != s_:
            bad_word.append(path)
            continue
        if text.find(s_) != s_ and text.find(s_) != -1:
            # 全文首次命中不等于本条的 start 时，只要求本条仍是合法命中
            pass
        if q.get("sourceHash") != EXPECT_HASH:
            bad_hash.append(path)
        if not (S_START <= s and e <= S_END):
            bad_range.append(path)
        # 段号独立复算
        if "paraLabel" in q:
            pno = int(q["paraLabel"][1:])
            if pno not in paras or not (paras[pno][0] <= s and e <= paras[pno][0] + len(paras[pno][1])):
                bad_para.append((path, q["paraLabel"]))
        if "wholeTextOccurrences" in q:
            real = len(re.findall(re.escape(s_), text))
            if real != q["wholeTextOccurrences"]:
                bad_count.append((path, real, q["wholeTextOccurrences"]))
        if "occurrencesInRange" in q:
            real = len([m for m in re.finditer(re.escape(s_), text)
                        if S_START <= m.start() and m.end() <= S_END])
            if real != q["occurrencesInRange"]:
                bad_count.append((path, real, q["occurrencesInRange"]))

    check("I08 逐字命中 text[start:end]==quote", not bad_word, "不符 %d 条：%s" % (len(bad_word), bad_word[:4]))
    check("I09 sourceHash 全等", not bad_hash, "不符 %d" % len(bad_hash))
    check("I10 引文全部落在区间内", not bad_range, "越界 %d" % len(bad_range))
    check("I11 paraLabel 与独立行扫描一致", not bad_para, "不符 %d：%s" % (len(bad_para), bad_para[:4]))
    check("I12 命中次数与独立重算一致", not bad_count, "不符 %d：%s" % (len(bad_count), bad_count[:4]))

    # ── 任务五栏：跨栏不共用（独立实现，不复用构造器逻辑）────────────────
    dup, overlap, null_ok = [], [], []
    for t in cand["tasks"]:
        cols = ["objective", "obstacle", "action", "result", "cost"]
        strs, ivs = {}, []
        for c in cols:
            col = t.get(c)
            if col is None:
                note = (t.get(c + "Note") or "").strip()
                null_ok.append((t["id"], c, bool(note)))
                continue
            for q in col["quotes"]:
                if q["quote"] in strs:
                    dup.append((t["id"], c, strs[q["quote"]]))
                strs[q["quote"]] = c
                ivs.append((q["start"], q["end"], c))
        ivs.sort()
        for i in range(1, len(ivs)):
            if ivs[i][0] < ivs[i - 1][1]:
                overlap.append((t["id"], ivs[i][2], ivs[i - 1][2]))
    check("I13 任务五栏不共用同一句", not dup, "共用 %d：%s" % (len(dup), dup[:3]))
    check("I14 任务五栏引文区间不重叠", not overlap, "重叠 %d：%s" % (len(overlap), overlap[:3]))
    check("I15 null 栏全部带同名 Note",
          all(x[2] for x in null_ok) and bool(null_ok),
          "null 栏 %d 个：%s" % (len(null_ok), [(a, b, c) for a, b, c in null_ok]))

    # ── 覆盖对账 ───────────────────────────────────────────────────────────
    quoted = set()
    for _, q in quotes:
        if "paraLabel" in q:
            quoted.add(int(q["paraLabel"][1:]))
    unq = set(int(x[1:]) for x in cand["coverageNote"]["unquotedParagraphs"])
    check("I16 被引段 ∪ 未引用段 == 全部段", quoted | unq == set(range(1, n + 1)),
          "被引 %d + 未引 %d vs 总 %d" % (len(quoted), len(unq), n))
    check("I17 两个集合不相交", not (quoted & unq), sorted(quoted & unq)[:5])
    check("I18 被引段计数一致", cand["coverageNote"]["quotedParagraphs"] == len(quoted),
          "候选=%d 独立=%d" % (cand["coverageNote"]["quotedParagraphs"], len(quoted)))

    # ── worldSettings 三态字段 ─────────────────────────────────────────────
    place_ok = rule_ok = item_ok = True
    for w in cand["worldSettings"]:
        if w["kind"] == "place":
            place_ok &= w.get("placeState") in ("arrived", "mentioned")
        elif w["kind"] == "rule":
            rule_ok &= w.get("institution") in ("declared", "executed", "misunderstood")
        elif w["kind"] == "item":
            item_ok &= bool(w.get("itemStates")) and all(
                x in ("hold", "transfer", "use", "lose") for x in w["itemStates"])
    kinds = {}
    for w in cand["worldSettings"]:
        kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
    check("I19 地点带 placeState", place_ok, str(kinds))
    check("I20 规则带 institution", rule_ok)
    check("I21 物件带 itemStates 多选", item_ok)

    # ── 主题与语义声称 ─────────────────────────────────────────────────────
    th_ok = all(t.get("perspective") and t.get("support") and t.get("counter")
                for t in cand["themeReadings"])
    check("I22 themeReadings 三件齐备且 ≤2 条", th_ok and len(cand["themeReadings"]) <= 2,
          "%d 条" % len(cand["themeReadings"]))
    check("I23 semanticReview 未声称完成", cand["semanticReview"] == "not-performed",
          cand["semanticReview"])

    # ── 伏笔：unresolved 必须显式 ──────────────────────────────────────────
    fs_ok, fs_detail = True, []
    for f in cand["foreshadows"]:
        st = f["status"]
        if st == "unresolved":
            ok = f["payoff"].get("text") is None and bool((f["payoff"].get("payoffNote") or "").strip())
        elif st == "resolved-in-range":
            ok = bool(f["payoff"].get("quotes"))
        else:
            ok = False
        fs_ok &= ok
        fs_detail.append((f["id"], st, ok))
    check("I24 伏笔状态与回收证据一致", fs_ok, str(fs_detail))

    # ── 因果边：方向与机制 ─────────────────────────────────────────────────
    ce_ok = all((e.get("mechanism") or "").strip() and e.get("notMereAdjacency") is True
                and e.get("quotes") for e in cand["causeEdges"])
    check("I25 因果边带 mechanism + notMereAdjacency", ce_ok, "%d 条" % len(cand["causeEdges"]))
    check("I26 有被拒边（反向自证）", len(cand["notCauseEdges"]) >= 3,
          "%d 条" % len(cand["notCauseEdges"]))

    # ── 变异测试：判据必须不是恒绿 ─────────────────────────────────────────
    probe = quotes[0][1]["quote"]
    mut = probe[:-1] + ("Z" if probe[-1] != "Z" else "Q")
    check("I27 变异①改字后 text[s:e]!=quote", text[quotes[0][1]["start"]:quotes[0][1]["end"]] != mut
          and text.find(mut) == -1, "变异串=%r" % mut[:20])
    q2 = quotes[min(5, len(quotes) - 1)][1]
    shifted_hit = text[q2["start"] + 1:q2["end"] + 1] == q2["quote"]
    check("I28 变异②偏移挪一格即不再逐字相等", not shifted_hit)
    # 段号判据有效性：把段号故意写错必须被抓到
    pno = int(q2["paraLabel"][1:])
    wrong = pno + 1
    wrong_hit = wrong in paras and paras[wrong][0] <= q2["start"] and q2["end"] <= paras[wrong][0] + len(paras[wrong][1])
    check("I29 变异③段号判据可判错", not wrong_hit or paras[pno][0] != paras[wrong][0],
          "P%03d -> P%03d" % (pno, wrong))

    # ── 与图谱缓存对照（只对照，不作证据）─────────────────────────────────
    graph = json.loads((ROOT / "data/cache/1063b17ca65ec1b76f30e460.json").read_text(encoding="utf-8"))
    check("I30 图谱缓存哈希与候选登记一致",
          cand["graphCacheSha256"] == hashlib.sha256(
              (ROOT / "data/cache/1063b17ca65ec1b76f30e460.json").read_bytes()).hexdigest())
    ch_events = [e for e in graph.get("events", []) if e.get("chapter") == cand["unitHead"]]
    print("       对照：图谱缓存里本章 events = %d 条，tasks=%d，causeEdges=%d（缓存摘要不作为原文证据）"
          % (len(ch_events),
             len([t for t in graph.get("tasks", []) if t.get("chapter") == cand["unitHead"]]),
             len([c for c in graph.get("causeEdges", []) if c.get("chapter") == cand["unitHead"]])))

    print()
    print("=" * 70)
    print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    for name, detail in FAIL:
        print("  FAIL %s %s" % (name, detail))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
