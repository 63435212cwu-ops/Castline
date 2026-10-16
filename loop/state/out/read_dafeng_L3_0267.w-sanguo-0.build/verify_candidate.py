#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立校验 read_dafeng_L3_0267.candidate.json（不 import 内容模块）。

它只读**产物**与**原文**，重新做全部硬性判据：
  V01 源哈希 / 切片边界 / 长度
  V02 range 与 sliceSha256
  V03 递归收集**所有**引文对象 → 逐字命中、长度、落在区间内、sourceHash 一致
  V04 任务五栏（含 null 栏 Note）与区间两两不重叠
  V05 枚举合法性：kind / placeState / itemStates / institution
  V06 分区键存在（== loop.py required_sections 抽出来的 6 个）
  V07 伏笔状态与 payoff/unresolvedWhat 的一致性
  V08 id 引用完整性（散文里引用的 T##/C##/F##/W##/S##/K##/U##/SP## 等必须已定义）
  V09 主题读法三件齐全且 ≤2 条
  V10 因果边/状态/知识差的必备字段
  V11 负向对照（可选 --selftest）：注入错误必须被抓住
退出码 0 = 全过；1 = 有 FAIL。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND_PATH = ROOT / "loop/state/out/read_dafeng_L3_0267.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 1119820, 1125007

RESULTS: list[tuple[str, bool, str]] = []


def chk(cid: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((cid, bool(ok), detail))
    return bool(ok)


def collect_quotes(obj, path="$", out=None):
    """递归收集所有形如 {quote:str, start:int, end:int, sourceHash:str} 的对象。"""
    if out is None:
        out = []
    if isinstance(obj, dict):
        if (isinstance(obj.get("quote"), str) and isinstance(obj.get("start"), int)
                and isinstance(obj.get("end"), int)):
            out.append((path, obj))
        else:
            for k, v in obj.items():
                collect_quotes(v, "%s.%s" % (path, k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            collect_quotes(v, "%s[%d]" % (path, i), out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="跑负向对照（注入错误必须被抓）")
    args = ap.parse_args()

    raw = DOCS.read_bytes()
    docs = json.loads(raw.decode("utf-8"))
    text = docs[0]["text"]
    slice_ = text[S:E]

    cand = json.loads(CAND_PATH.read_text(encoding="utf-8"))

    # V01 源哈希与边界
    chk("V01a", hashlib.sha256(raw).hexdigest() == HASH,
        "docs.json sha256 = %s" % hashlib.sha256(raw).hexdigest())
    chk("V01b", slice_.startswith("第三十八章 五号的传书"),
        "docs[0].text[%d:%d] 开头 = %r" % (S, E, slice_[:20]))
    chk("V01c", len(slice_) == 5187, "len(slice) = %d" % len(slice_))
    chk("V01d", cand["source"]["range"] == [S, E], "candidate range = %r" % (cand["source"]["range"],))
    chk("V01e", cand["source"]["sourceHash"] == HASH, "candidate sourceHash 一致")

    # V02 切片哈希
    chk("V02", cand["source"].get("sliceSha256") == hashlib.sha256(slice_.encode("utf-8")).hexdigest(),
        "sliceSha256 = %s" % cand["source"].get("sliceSha256"))

    # V03 全部引文
    quotes = collect_quotes(cand)
    bad_lit = bad_len = bad_range = bad_hash = 0
    details = []
    for path, q in quotes:
        s, e, lit = q["start"], q["end"], q["quote"]
        if text[s:e] != lit:
            bad_lit += 1
            details.append("字面不符 %s: %r != %r" % (path, text[s:e][:40], lit[:40]))
        if e - s != len(lit):
            bad_len += 1
            details.append("长度不符 %s" % path)
        if not (S <= s and e <= E):
            bad_range += 1
            details.append("越界 %s (%d,%d)" % (path, s, e))
        if q.get("sourceHash") != HASH:
            bad_hash += 1
            details.append("sourceHash 不符 %s" % path)
    chk("V03a", bad_lit == 0, "逐字命中：%d 个引文对象，不符 %d" % (len(quotes), bad_lit))
    chk("V03b", bad_len == 0, "长度自洽：不符 %d" % bad_len)
    chk("V03c", bad_range == 0, "区间内：越界 %d" % bad_range)
    chk("V03d", bad_hash == 0, "sourceHash：不符 %d" % bad_hash)
    if details:
        for d in details[:10]:
            print("   ", d, file=sys.stderr)

    # V03e 引用对象类型
    typed = all(isinstance(q["start"], int) and isinstance(q["end"], int)
                and isinstance(q["quote"], str) for _, q in quotes)
    chk("V03e", typed, "start/end/quote 类型正确")

    # V04 五栏独立性 + null Note
    FIELDS = ("objective", "obstacle", "action", "result", "cost")
    overlaps = []
    nullprob = []
    for t in cand["tasks"]:
        spans = []
        for f in FIELDS:
            qs = t.get("%sQuotes" % f) or []
            if t.get(f) is None:
                note = t.get("%sNote" % f) or ""
                if not note.strip():
                    nullprob.append("%s.%s" % (t["id"], f))
                if qs:
                    nullprob.append("%s.%s 为 null 却有引文" % (t["id"], f))
            else:
                if not qs:
                    nullprob.append("%s.%s 非空却无引文" % (t["id"], f))
                if not (t.get("%sBasis" % f) or "").strip():
                    nullprob.append("%s.%s 缺 basis" % (t["id"], f))
            for q in qs:
                spans.append((q["start"], q["end"], f))
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                a, b = spans[i], spans[j]
                if a[2] == b[2]:
                    continue
                if max(a[0], b[0]) < min(a[1], b[1]):
                    overlaps.append("%s %s/%s [%d,%d)" % (t["id"], a[2], b[2],
                                                          max(a[0], b[0]), min(a[1], b[1])))
    chk("V04a", not nullprob, "null 栏标注/引文齐备：问题 %d %s" % (len(nullprob), nullprob[:5]))
    chk("V04b", not overlaps, "五栏区间两两不重叠：重叠 %d %s" % (len(overlaps), overlaps[:5]))
    chk("V04c", cand.get("taskIntervalOverlaps") == [],
        "候选自报 taskIntervalOverlaps == []")
    chk("V04d", all(len(t["nullFields"]) == sum(1 for f in FIELDS if t.get(f) is None)
                    for t in cand["tasks"]), "nullFields 与各栏一致")

    # V05 枚举
    enum_prob = []
    for w in cand["worldSettings"]:
        k = w.get("kind")
        if k not in ("rule", "place", "item"):
            enum_prob.append("%s kind=%r" % (w["id"], k))
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            enum_prob.append("%s placeState=%r" % (w["id"], w.get("placeState")))
        if k == "item":
            st = w.get("itemStates")
            if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                enum_prob.append("%s itemStates=%r" % (w["id"], st))
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            enum_prob.append("%s institution=%r" % (w["id"], w.get("institution")))
    chk("V05", not enum_prob, "枚举合法：问题 %d %s" % (len(enum_prob), enum_prob[:5]))

    # V06 分区键
    want = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
    missing = [k for k in want if k not in cand]
    chk("V06", not missing, "内容分区键齐备，缺 %r" % missing)

    # V07 伏笔状态
    fprob = []
    for f in cand["foreshadows"]:
        if f["status"] == "unresolved":
            if f.get("payoff") is not None:
                fprob.append("%s unresolved 却有 payoff" % f["id"])
            if not (f.get("unresolvedWhat") or "").strip():
                fprob.append("%s unresolved 缺 unresolvedWhat" % f["id"])
        elif f["status"] == "resolved" and f.get("payoff") is None:
            fprob.append("%s resolved 却无 payoff" % f["id"])
        if not f.get("setup", {}).get("quote"):
            fprob.append("%s setup 无引文" % f["id"])
    chk("V07", not fprob, "伏笔状态一致：问题 %d %s" % (len(fprob), fprob[:5]))

    # V08 id 引用完整性
    defined = set()
    for key, pre in (("tasks", "T"), ("causeEdges", "C"), ("states", "S"), ("foreshadows", "F"),
                     ("worldSettings", "W"), ("unknowns", "U"), ("textualNotes", "TN"),
                     ("notForeshadows", "NF"), ("notWorldSettings", "NW"), ("rejectedEdges", "RE"),
                     ("speechAsClueNotFact", "SP"), ("knowledgeGaps", "K"), ("selfCritique", "SC"),
                     ("themeReadings", "TH")):
        for it in cand.get(key, []):
            if isinstance(it, dict) and it.get("id"):
                defined.add(it["id"])
    body = json.dumps({k: v for k, v in cand.items()
                       if k not in ("coverage", "machineSelfCheck", "source", "provenanceNote")},
                      ensure_ascii=False)
    refs = set(re.findall(r"\b(?:T|C|S|F|W|U|TN|NF|NW|RE|SP|K|SC|TH)\d{2}\b", body))
    dangling = sorted(r for r in refs if r not in defined)
    chk("V08", not dangling, "id 引用完整性：定义 %d，悬空 %r" % (len(defined), dangling[:8]))

    # V09 主题读法
    tprob = []
    if len(cand["themeReadings"]) > 2:
        tprob.append("超过 2 条：%d" % len(cand["themeReadings"]))
    for th in cand["themeReadings"]:
        if not th.get("perspective") or not th.get("support") or not th.get("counter"):
            tprob.append("%s 缺三件之一" % th["id"])
    chk("V09", not tprob, "主题读法三件齐备且 ≤2 条：问题 %r" % tprob)

    # V10 因果边/状态/知识差
    gprob = []
    for c in cand["causeEdges"]:
        for k in ("from", "to", "trigger", "mechanism", "basis"):
            if not (c.get(k) or "").strip():
                gprob.append("%s 缺 %s" % (c["id"], k))
        if len(c.get("quotes") or []) < 2:
            gprob.append("%s 引文少于 2" % c["id"])
    for s in cand["states"]:
        for lbl in ("before", "after", "anchor"):
            if not (s.get(lbl) or "").strip() or not (s.get("%sQuotes" % lbl) or []):
                gprob.append("%s 缺 %s 或引文" % (s["id"], lbl))
    for k in cand["knowledgeGaps"]:
        for f in ("proposition", "knows", "doesNotKnow"):
            if not (k.get(f) or "").strip():
                gprob.append("%s 缺 %s" % (k["id"], f))
    chk("V10", not gprob, "因果边/状态/知识差齐备：问题 %d %s" % (len(gprob), gprob[:5]))

    # 统计输出
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("引文对象（递归全量）：%d" % len(quotes))
    print("校验项：%d，PASS %d，FAIL %d" % (len(RESULTS), passed, len(RESULTS) - passed))
    for cid, ok, detail in RESULTS:
        print("  [%s] %-6s %s" % ("PASS" if ok else "FAIL", cid, detail))

    if args.selftest:
        print("\n== 负向对照（注入错误必须被抓）==")
        st_fail = 0
        # 注入 1：篡改一条引文的最后一个字
        bad = copy.deepcopy(cand)
        t0 = bad["tasks"][0]
        q0 = t0["objectiveQuotes"][0]
        q0["quote"] = q0["quote"] + "X"
        qs2 = collect_quotes(bad)
        hit = any(text[q["start"]:q["end"]] != q["quote"] for _, q in qs2)
        print("  注入1 引文加字符 → 被抓：%s" % hit)
        st_fail += 0 if hit else 1
        # 注入 2：五栏共用同一区间
        bad2 = copy.deepcopy(cand)
        t1 = bad2["tasks"][0]
        t1["costQuotes"] = copy.deepcopy(t1["objectiveQuotes"])
        sp = []
        for f in FIELDS:
            for q in t1.get("%sQuotes" % f) or []:
                sp.append((q["start"], q["end"], f))
        ov = any(max(sp[i][0], sp[j][0]) < min(sp[i][1], sp[j][1]) and sp[i][2] != sp[j][2]
                 for i in range(len(sp)) for j in range(i + 1, len(sp)))
        print("  注入2 五栏共用一句 → 被抓：%s" % ov)
        st_fail += 0 if ov else 1
        # 注入 3：把 null 栏的 Note 清空
        bad3 = copy.deepcopy(cand)
        for t in bad3["tasks"]:
            if t["cost"] is None:
                t["costNote"] = ""
                break
        empty = any(t.get(f) is None and not (t.get("%sNote" % f) or "").strip()
                    for t in bad3["tasks"] for f in FIELDS)
        print("  注入3 空 Note 的 null → 被抓：%s" % empty)
        st_fail += 0 if empty else 1
        # 注入 4：非法枚举
        bad4 = copy.deepcopy(cand)
        for w in bad4["worldSettings"]:
            if w["kind"] == "place":
                w["placeState"] = "取荆州"
                break
        bad5 = copy.deepcopy(cand)
        for w in bad5["worldSettings"]:
            if w["kind"] == "item":
                w["itemStates"] = ["hold", "transfer", "use", "lose", "chain"]
                break
        enum_bad = any(w.get("placeState") not in ("arrived", "mentioned")
                       for w in bad4["worldSettings"] if w["kind"] == "place") or \
                   any(x not in ("hold", "transfer", "use", "lose")
                       for w in bad5["worldSettings"] if w["kind"] == "item"
                       for x in w.get("itemStates") or [])
        print("  注入4 非法枚举 → 被抓：%s" % enum_bad)
        st_fail += 0 if enum_bad else 1
        # 注入 5：悬空 id 引用
        bad6 = copy.deepcopy(cand)
        bad6["states"][0]["note"] = "见 F99 的说明"
        b6 = json.dumps({k: v for k, v in bad6.items()
                         if k not in ("coverage", "machineSelfCheck", "source", "provenanceNote")},
                        ensure_ascii=False)
        d6 = [r for r in set(re.findall(r"\b(?:T|C|S|F|W|U|TN|NF|NW|RE|SP|K|SC|TH)\d{2}\b", b6))
              if r not in defined]
        print("  注入5 悬空引用 F99 → 被抓：%s" % bool(d6))
        st_fail += 0 if d6 else 1
        print("负向对照：%d 项注入，未被抓 %d" % (5, st_fail))
        if st_fail:
            return 1

    return 1 if any(not ok for _, ok, _ in RESULTS) else 0


if __name__ == "__main__":
    sys.exit(main())
