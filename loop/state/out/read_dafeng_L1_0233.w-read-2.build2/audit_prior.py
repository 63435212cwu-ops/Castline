#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计 w-read-2 上一轮留在 writes 路径上的候选（21:15Z 那版，sha 6b8a3f58…）。

这个脚本**不信任候选里的任何自述**：所有偏移、逐字性、
栏位复用、null 注释、区间越界，全部从原文重算。
用法：
    python3 -B -s loop/state/out/read_dafeng_L1_0233.w-read-2.build2/audit_prior.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/PRIOR-candidate.w-read-2.json.bak"
START, END = 916516, 923035
EXPECT_SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

problems = []
notes = []


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_quotes(obj, path="$"):
    """产出 (json路径, quote dict) —— 任何带 quote/start/end 的对象。"""
    if isinstance(obj, dict):
        if "quote" in obj and "start" in obj and "end" in obj:
            yield path, obj
            return
        for k, v in obj.items():
            yield from walk_quotes(v, "%s.%s" % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_quotes(v, "%s[%d]" % (path, i))


# ── 原文 ────────────────────────────────────────────────────────────────
docs = json.loads(DOCS.read_text(encoding="utf-8"))
text = docs[0]["text"]
src_hash = sha256_file(DOCS)
print("docs.json sha256 =", src_hash)
if src_hash != EXPECT_SRC_HASH:
    problems.append("docs.json 哈希与任务 sourceHash 不符：%s" % src_hash)

slice_text = text[START:END]
print("slice len =", len(slice_text))
print("slice starts with title:", slice_text.startswith("第四章 请陛下赐死"))

cand = json.loads(CAND.read_text(encoding="utf-8"))
print("candidate agent =", cand.get("agent"), "| task =", cand.get("task"))

# ── 1. 每条引文：逐字 + 偏移 + sourceHash + 区间内 + 切片内唯一 ─────────
total = uniq = 0
seen = {}
for jpath, q in walk_quotes(cand):
    total += 1
    quote, s, e = q["quote"], q["start"], q["end"]
    if not isinstance(s, int) or not isinstance(e, int):
        problems.append("%s 偏移非整数" % jpath)
        continue
    got = text[s:e]
    if got != quote:
        problems.append("%s 逐字不符 text[%d:%d]=%r != %r" % (jpath, s, e, got[:60], quote[:60]))
    if not (START <= s and e <= END):
        problems.append("%s 越界 [%d,%d) 不在 [%d,%d)" % (jpath, s, e, START, END))
    if quote not in slice_text:
        problems.append("%s 引文不在切片内" % jpath)
    elif slice_text.count(quote) > 1:
        problems.append("%s 引文在切片内不唯一（%d 次）" % (jpath, slice_text.count(quote)))
    if q.get("sourceHash") != EXPECT_SRC_HASH:
        problems.append("%s sourceHash 不符：%r" % (jpath, q.get("sourceHash")))
    seen.setdefault(quote, []).append(jpath)

uniq = len(seen)
print("\n引文实例 = %d，不同引文串 = %d" % (total, uniq))

# ── 2. 五栏共用同一句（提示词点名的旧图谱缺陷）──────────────────────────
FIVE = ("objective", "obstacle", "action", "result", "cost")
tasks = cand.get("tasks") or []
print("tasks =", len(tasks))
for t in tasks:
    tid = t.get("id")
    slot_quotes = {}
    for slot in FIVE:
        v = t.get(slot)
        if isinstance(v, dict):
            qs = {x.get("quote") for x in (v.get("quotes") or [])}
            if qs:
                slot_quotes[slot] = qs
    names = list(slot_quotes)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            shared = slot_quotes[names[i]] & slot_quotes[names[j]]
            if shared:
                problems.append("%s 五栏共用同一句：%s ∩ %s = %s"
                                % (tid, names[i], names[j], list(shared)[:2]))

# ── 3. null 栏位是否都有 <栏位>Note ────────────────────────────────────
for t in tasks:
    tid = t.get("id")
    for slot in FIVE:
        if slot in t and t.get(slot) is None:
            note = t.get(slot + "Note")
            if not note or not str(note).strip():
                problems.append("%s.%s 是 null 但没有 %sNote" % (tid, slot, slot))
        elif slot not in t:
            problems.append("%s 缺栏位 %s（应显式写 null）" % (tid, slot))

# ── 4. 有值的栏位必须有引文 ────────────────────────────────────────────
for t in tasks:
    tid = t.get("id")
    for slot in FIVE:
        v = t.get(slot)
        if isinstance(v, dict) and not (v.get("quotes") or []):
            problems.append("%s.%s 有结论却零引文" % (tid, slot))
        if isinstance(v, dict) and not v.get("basis"):
            problems.append("%s.%s 缺 basis" % (tid, slot))

# ── 5. basis 枚举 ──────────────────────────────────────────────────────
OK_BASIS = {"explicit", "inferred", "derived", "unverified"}
def check_basis(obj, jpath="$"):
    if isinstance(obj, dict):
        if "basis" in obj and obj["basis"] not in OK_BASIS:
            problems.append("%s basis 非法：%r" % (jpath, obj["basis"]))
        for k, v in obj.items():
            check_basis(v, "%s.%s" % (jpath, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_basis(v, "%s[%d]" % (jpath, i))
check_basis(cand)

# ── 6. semanticReview 不得声称完成 ─────────────────────────────────────
sr = cand.get("semanticReview") or {}
if sr.get("status") == "performed":
    problems.append("semanticReview 声称 performed（越权）")

# ── 7. 顶层分区齐全 ────────────────────────────────────────────────────
for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
          "themeReadings", "unknowns", "selfCritique"):
    if k not in cand:
        problems.append("缺分区 %s" % k)

# ── 8. 五栏各自引文是否真的指向该栏（结构检查：引文不得完全相同于他栏引文）──
#     这是上一条的加强版：跨任务复用不做判罚，只登记。
print("\n==== 结果 ====")
if problems:
    print("发现 %d 个问题：" % len(problems))
    for p in problems:
        print("  ✗", p)
else:
    print("机械审计：全部通过（%d 条引文实例、%d 条不同引文）" % (total, uniq))

Path(ROOT / "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/audit_prior.result.txt").write_text(
    "\n".join(problems) if problems else "OK: %d quote instances, %d unique" % (total, uniq),
    encoding="utf-8")
sys.exit(1 if problems else 0)
