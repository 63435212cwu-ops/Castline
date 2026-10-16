#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计：**不 import** content_0295 / quotes_0295，只从磁盘重读候选 JSON 与 docs.json。

与构建期的分工（这是本脚本存在的理由）：
  · 构建器在内存里持有它自己构造的对象，所以「构建期断言通过」不能排除
    「写盘的内容和内存里的不一致」或「某条引文其实来自另一个文件」这类问题；
  · 本脚本只认磁盘上的字节：重新解析候选里每一个 {quote,start,end}，
    独立地断言 text[start:end]==quote，并且必须等于 docs[0].text 在**该偏移处**的原文。

审计项：
  B1  候选 JSON 可解析；task/agent 归属正确
  B2  每个引文对象：text[start:end] == quote（逐字），且 start == START + 单元内相对位置
  B3  每个引文对象的 sourceHash 一致；kind 合法；occ 语义可复核（出现次数 > occ）
  B4  六个数出来的分区键全部存在（loop.py required_sections 口径，独立重算）
  B5  tasks 五栏：栏间引文键不重复、区间不重叠；null 栏必有 Note
  B6  伏笔 resolved 与 payoff 一致；未回收的必须显式 resolved=False
  B7  worldSettings 三态字段齐全（rule→institution / place→placeState / item→itemStates）
  B8  themeReadings 三件齐、且不含被禁判据词
  B9  叙事分区不含 author_note 引文；作者区引文只出现在允许的分区
  B10 候选里的引文全部能重新在原文里 find 到（反向：不依赖候选自报的偏移）
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0295.candidate.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L3_0295.json"

START, END = 1286538, 1295556
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
BASES = {"explicit", "inferred", "derived", "unverified"}
KINDS = {"narration", "dialogue", "inner", "free_indirect", "parable", "author_note"}
BANNED = ["事件密度", "剧情点", "死亡人数", "篇幅中点", "时间中点", "三幕", "英雄旅程"]
AUTHOR_OK = {"textualNotes", "authorRegionEvidence", "provenanceNote", "semanticReviewNote", "source"}

P = []


def bad(m):
    P.append(m)


def walk_quotes(o, path="root"):
    """产出 (path, 引文对象) —— 只认同时含 quote/start/end 的 dict。"""
    if isinstance(o, dict):
        if {"quote", "start", "end"} <= set(o):
            yield path, o
            return
        for k, v in o.items():
            yield from walk_quotes(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_quotes(v, "%s[%d]" % (path, i))


def keys_of(quotes):
    return [q.get("key") for q in quotes or []]


def main():
    text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    if not CAND.exists():
        print("候选不存在：%s" % CAND)
        return 1
    cand = json.loads(CAND.read_text(encoding="utf-8"))

    # B1
    if cand.get("task") != "read:dafeng:L3:0295":
        bad("B1 task 不符：%r" % cand.get("task"))
    if cand.get("agent") != "w-xiyou-1":
        bad("B1 agent 不符：%r" % cand.get("agent"))

    total = 0
    for path, q in walk_quotes(cand):
        total += 1
        quote, s, e = q["quote"], q["start"], q["end"]
        # B2
        if text[s:e] != quote:
            bad("B2 %s: text[%d:%d] != quote" % (path, s, e))
        if e - s != len(quote):
            bad("B2 %s: 长度不符" % path)
        if not (START <= s and e <= END):
            bad("B2 %s: 偏移越出单元" % path)
        # B10 反向：不依赖自报偏移，重新 find
        if quote not in text:
            bad("B10 %s: 原文里 find 不到 %r" % (path, quote[:40]))
        # B3
        if q.get("sourceHash") != SOURCE_HASH:
            bad("B3 %s: sourceHash 不符" % path)
        if q.get("kind") not in KINDS:
            bad("B3 %s: kind 非法 %r" % (path, q.get("kind")))
        occ = q.get("occ", 0)
        if text.count(quote) <= occ:
            bad("B3 %s: occ=%d 超出出现次数" % (path, occ))
        # B11：containsUtterance 必须与「引文里实际有没有引号」一致（机器可复核，不是自报）
        want_utt = ("\u201c" in quote or "\u300c" in quote)
        if q.get("containsUtterance") != want_utt:
            bad("B11 %s: containsUtterance=%r 与实际(%r)不符" % (path, q.get("containsUtterance"), want_utt))
        if not (START <= text.find(quote) and True):
            pass

    # B4：独立重算 loop.py 的 required_sections 口径
    task = json.loads(TASK.read_text(encoding="utf-8"))
    want = re.findall(r"(?m)^\s*\d+[a-z]?\.\s+`([A-Za-z][A-Za-z0-9_]*)\[\]`", task["prompt"])
    for m in re.finditer(r"产出(?:（)?写进[^\n]*?：", task["prompt"]):
        chunk = task["prompt"][m.end():m.end() + 500]
        for stop in ("\n\n", "。\n", "。"):
            k = chunk.find(stop)
            if k >= 0:
                chunk = chunk[:k]
        for mm in re.finditer(r"`([A-Za-z][A-Za-z0-9_]*)\[\]`", chunk):
            if mm.group(1) not in want:
                want.append(mm.group(1))
    missing = [k for k in want if k not in cand]
    if missing:
        bad("B4 内容分区缺失：%s" % missing)

    # B5：tasks 五栏
    for t in cand.get("tasks", []):
        used_keys, spans = [], []
        for col in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(col)
            note = t.get(col + "Note")
            if v is None:
                if not note:
                    bad("B5 %s.%s 为 null 但无 Note" % (t["id"], col))
                continue
            if v.get("basis") not in BASES:
                bad("B5 %s.%s basis 非法" % (t["id"], col))
            if not v.get("quotes"):
                bad("B5 %s.%s 无引文" % (t["id"], col))
            for q in v.get("quotes") or []:
                k = q.get("key")
                if k in used_keys:
                    bad("B5 %s 五栏复用引文键 %s" % (t["id"], k))
                for (s0, e0, k0) in spans:
                    if not (q["end"] <= s0 or q["start"] >= e0):
                        bad("B5 %s 栏间区间重叠 %s/%s" % (t["id"], k, k0))
                used_keys.append(k)
                spans.append((q["start"], q["end"], k))

    # B6：伏笔
    for f in cand.get("foreshadows", []):
        has_pay = bool(f.get("payoff"))
        if f.get("resolved") and not has_pay:
            bad("B6 %s resolved=True 但无 payoff" % f["id"])
        if not f.get("resolved") and has_pay:
            bad("B6 %s resolved=False 但有 payoff" % f["id"])
        if not f.get("setup"):
            bad("B6 %s 无 setup" % f["id"])
        if "unresolved" not in json.dumps(f, ensure_ascii=False) and not f.get("resolved"):
            bad("B6 %s 未回收却没显式标 unresolved" % f["id"])

    # B7：worldSettings 三态
    for w in cand.get("worldSettings", []):
        k = w.get("kind")
        if k == "rule" and w.get("institution") not in {"declared", "executed", "misunderstood"}:
            bad("B7 %s institution 缺失/非法" % w["id"])
        elif k == "place" and w.get("placeState") not in {"arrived", "mentioned"}:
            bad("B7 %s placeState 缺失/非法" % w["id"])
        elif k == "item":
            st = w.get("itemStates")
            if not st or any(x not in {"hold", "transfer", "use", "lose"} for x in st):
                bad("B7 %s itemStates 缺失/非法：%r" % (w["id"], st))
        if not w.get("explain"):
            bad("B7 %s 缺 explain" % w["id"])

    # B8：主题
    for t in cand.get("themeReadings", []):
        for part in ("perspective", "support", "counter"):
            if not t.get(part):
                bad("B8 %s 缺 %s" % (t["id"], part))
        blob = json.dumps(t, ensure_ascii=False)
        for b in BANNED:
            if b in blob:
                bad("B8 %s 含被禁判据词 %s" % (t["id"], b))

    # B9：作者区引文不得出现在叙事分区
    for path, q in walk_quotes(cand):
        if q.get("kind") == "author_note":
            top = path.split(".")[1].split("[")[0] if path.startswith("root.") else path
            if top not in AUTHOR_OK:
                bad("B9 作者区引文出现在 %s" % path)

    # 计数与基本完整性
    print("候选：%s" % CAND.relative_to(ROOT))
    print("引文对象（磁盘重读）：%d 条" % total)
    print("审计项 B1–B10；问题：%d 条" % len(P))
    for p in P:
        print("  !", p)
    return 1 if P else 0


if __name__ == "__main__":
    sys.exit(main())
