#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立核验 read:dafeng:L3:0227 的**成品**（从磁盘重读，不复用构建脚本的内存状态）。

与构建脚本的关系：构建脚本用 Q() 自己定位偏移；本脚本**不复用**任何偏移，
一律用 docs[0].text.find(quote, START, END) 在自己算出的区间窗口内重新定位，
再比对成品里写的 start/end。任何不一致都算 fails。

核验项（逐条报数，不概括成一句「已通过」）：
  1. docs.json sha256 == task.sourceHash（重算整份文件）
  2. docs[0].text[START:END] 以 unitHead 开头；长度 == end-start
  3. 遍历成品里**每一个** quote 对象：find 命中、text[start:end]==quote、
     落在区间内、sourceHash 字段正确、start/end 是 int 且 start<end
  4. 同一任务五栏：引文字符串互不相同、引用区间互不重叠
  5. null 栏位必须有同名 <栏位>Note；有值栏必须有引文
  6. 六个必需分区存在（键存在即可，允许空数组）
  7. worldSettings 形状：kind / placeState / itemStates / institution / explain
  8. themeReadings 形状：perspective + support + counter 齐备，且 ≤2 条
  9. foreshadows：status 合法、unresolved/partial 必须有 unresolvedWhat
 10. 越界人物名探针：本区间**不存在**的专名（太平刀/守门人/佛陀/怀庆/监正/梁有平/
     慕南栀/斩断规则等）不得出现在任何引文里 —— 这是本轮真实踩过的坑
     （初稿有 6 条引文取自区间之外，因为读原文时越过了 end）。
 11. 反例（fails）逐条打印；退出码 0=全过 / 1=有失败
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DOCS = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop", "state", "out", "read_dafeng_L3_0227.candidate.json")
TASKF = os.path.join(ROOT, "loop", "state", "runs", "task-read_dafeng_L3_0227.json")

fails = []
stats = {}


def bad(m):
    fails.append(m)


task = json.load(open(TASKF, encoding="utf-8"))
START, END = task["sourceRange"]
UNIT_HEAD = task["unitHead"]
EXPECT = task["sourceHash"]

raw = open(DOCS, "rb").read()
got = hashlib.sha256(raw).hexdigest()
stats["docsSha256"] = got
if got != EXPECT:
    bad("docs.json sha256=%s != task.sourceHash=%s" % (got, EXPECT))

TEXT = json.loads(raw.decode("utf-8"))[0]["text"]
SLICE = TEXT[START:END]
if not SLICE.startswith(UNIT_HEAD):
    bad("区间不以 unitHead 开头：%r" % SLICE[:40])
if len(SLICE) != END - START:
    bad("切片长度 %d != end-start %d" % (len(SLICE), END - START))
stats["sliceCodepoints"] = len(SLICE)
stats["sliceSha256"] = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

cand = json.load(open(CAND, encoding="utf-8"))

# ── 3. 遍历每一个 quote 对象 ──────────────────────────────────────────────
quote_objs = []


def walk(node, path):
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str):
            quote_objs.append((path, node))
        for k, v in node.items():
            walk(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i))


walk(cand, "$")
stats["quoteObjects"] = len(quote_objs)

verified = 0
for path, q in quote_objs:
    s = q.get("start")
    e = q.get("end")
    t = q["quote"]
    if not isinstance(s, int) or not isinstance(e, int):
        bad("%s start/end 不是 int：%r/%r（该引文未被定位）" % (path, s, e))
        continue
    if not (s < e):
        bad("%s start>=end：%d/%d" % (path, s, e))
        continue
    if e - s != len(t):
        bad("%s end-start=%d != len(quote)=%d" % (path, e - s, len(t)))
    if TEXT[s:e] != t:
        bad("%s text[start:end] != quote（%r vs %r）" % (path, TEXT[s:e][:40], t[:40]))
        continue
    if not (s >= START and e <= END):
        bad("%s 越出区间：%d/%d" % (path, s, e))
        continue
    loc = TEXT.find(t, START, END)
    if loc < 0:
        bad("%s 在区间窗口内 find 不到：%r" % (path, t[:40]))
        continue
    if loc != s:
        bad("%s find 命中位置 %d != 记录 start %d：%r" % (path, loc, s, t[:40]))
        continue
    declared = q.get("sourceHash")
    if declared is not None and declared != EXPECT:
        bad("%s sourceHash 字段不符：%r" % (path, declared))
        continue
    verified += 1
stats["quotesFullyVerified"] = verified
stats["quoteObjectsWithSourceHash"] = sum(1 for _, q in quote_objs if q.get("sourceHash"))
stats["unlocatedQuoteObjects"] = sum(
    1 for _, q in quote_objs if not isinstance(q.get("start"), int))

# ── 10. 越界专名探针（本轮真实踩过的坑） ──────────────────────────────────
OUT_OF_RANGE_NAMES = [
    "太平刀", "守门人", "斩断规则", "佛陀", "蛊神", "荒", "怀庆", "监正", "天尊",
    "慕南栀", "临安", "许铃音", "白姬", "洛玉衡", "楚元缜", "李灵素", "阿苏罗",
    "梁有平", "萨伦阿古", "大日轮回", "无色琉璃", "靖山城", "桑泊", "地书聊天群",
]
present_in_slice = {n for n in OUT_OF_RANGE_NAMES if n in SLICE}
should_be_absent = [n for n in OUT_OF_RANGE_NAMES if n not in SLICE]
leaks = []
for path, q in quote_objs:
    for n in should_be_absent:
        if n in q["quote"]:
            leaks.append({"path": path, "name": n, "quote": q["quote"][:50]})
stats["outOfRangeNameProbe"] = {
    "probed": len(OUT_OF_RANGE_NAMES),
    "absentFromSliceEnforced": len(should_be_absent),
    "presentInSliceNotEnforced": sorted(present_in_slice),
    "leaks": leaks,
}
if leaks:
    bad("引文里出现本区间不存在的专名（越界内容）：%d 处 %r"
        % (len(leaks), [l["name"] for l in leaks[:6]]))

# 兜底：任何引文都必须能在区间内 find（上面已逐条做），再断言
# 「引文所覆盖的码点全部落在 [START,END)」—— 汇总口径，防止边界半开错误。
summed = sum(q["end"] - q["start"] for _, q in quote_objs if isinstance(q.get("start"), int))
stats["summedQuoteCodepoints"] = summed

# ── 4. 同一任务五栏 ───────────────────────────────────────────────────────
FIELDS = ["objective", "obstacle", "action", "result", "cost"]
collisions = []
overlaps = []
for t in cand.get("tasks", []):
    seen = {}
    ivs = []
    for f in FIELDS:
        for q in (t.get(f + "Quotes") or []):
            key = q.get("quote")
            if key in seen and seen[key] != f:
                collisions.append({"task": t.get("id"), "quote": key[:40],
                                   "fields": sorted([seen[key], f])})
            seen.setdefault(key, f)
            if isinstance(q.get("start"), int):
                ivs.append((q["start"], q["end"], f))
    for i in range(len(ivs)):
        for j in range(i + 1, len(ivs)):
            a, b = ivs[i], ivs[j]
            if a[0] < b[1] and b[0] < a[1]:
                overlaps.append({"task": t.get("id"), "a": list(a), "b": list(b)})
stats["taskFieldQuoteCollision"] = collisions
stats["taskFieldIntervalOverlap"] = overlaps
if collisions:
    bad("任务五栏引文碰撞：%d 处" % len(collisions))
if overlaps:
    bad("任务五栏区间重叠：%d 处" % len(overlaps))

# ── 5. null 栏位必须有 Note ───────────────────────────────────────────────
null_without_note = []
for t in cand.get("tasks", []):
    for f in FIELDS:
        if t.get(f) is None:
            if not (t.get(f + "Note") or "").strip():
                null_without_note.append("%s.%s" % (t.get("id"), f))
        else:
            if not (t.get(f + "Quotes") or []):
                bad("%s.%s 有值但无引文" % (t.get("id"), f))
stats["nullFields"] = sum(1 for t in cand.get("tasks", []) for f in FIELDS
                          if t.get(f) is None)
stats["nullWithoutNote"] = null_without_note
if null_without_note:
    bad("null 栏缺 Note：%r" % null_without_note)

# ── 6. 六个必需分区 ───────────────────────────────────────────────────────
REQ = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
missing = [k for k in REQ if k not in cand]
stats["requiredSections"] = REQ
stats["missingSections"] = missing
if missing:
    bad("缺分区：%r" % missing)

# ── 7. worldSettings 形状 ─────────────────────────────────────────────────
ws_problems = []
for w in cand.get("worldSettings", []):
    if w.get("kind") not in ("rule", "place", "item"):
        ws_problems.append("%s kind=%r" % (w.get("id"), w.get("kind")))
    if w.get("kind") == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        ws_problems.append("%s placeState=%r" % (w.get("id"), w.get("placeState")))
    if w.get("kind") == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or any(
                x not in ("hold", "transfer", "use", "lose") for x in st):
            ws_problems.append("%s itemStates=%r" % (w.get("id"), st))
    if w.get("kind") == "rule" and w.get("institution") not in (
            "declared", "executed", "misunderstood"):
        ws_problems.append("%s institution=%r" % (w.get("id"), w.get("institution")))
    if not (w.get("explain") or "").strip():
        ws_problems.append("%s 缺 explain" % w.get("id"))
    if not isinstance(w.get("quote"), dict) or not w["quote"].get("quote"):
        ws_problems.append("%s 缺 quote" % w.get("id"))
stats["worldSettingsKinds"] = sorted({w.get("kind") for w in cand.get("worldSettings", [])})
stats["worldSettingsShapeProblems"] = ws_problems
if ws_problems:
    bad("worldSettings 形状问题：%d" % len(ws_problems))

# ── 8. themeReadings 形状 ─────────────────────────────────────────────────
th_problems = []
ths = cand.get("themeReadings", [])
if len(ths) > 2:
    th_problems.append("themeReadings %d 条 > 2" % len(ths))
for th in ths:
    for k in ("perspective", "support", "counter"):
        if not th.get(k):
            th_problems.append("%s 缺 %s" % (th.get("id"), k))
    if not isinstance(th.get("support"), list):
        th_problems.append("%s support 非列表" % th.get("id"))
stats["themeReadings"] = len(ths)
stats["themeReadingProblems"] = th_problems
if th_problems:
    bad("themeReadings 形状问题：%d" % len(th_problems))

# ── 9. foreshadows ────────────────────────────────────────────────────────
fs_problems = []
for f in cand.get("foreshadows", []):
    if f.get("status") not in ("resolved-in-range", "unresolved", "partial-in-range"):
        fs_problems.append("%s status=%r" % (f.get("id"), f.get("status")))
    if f.get("status") in ("unresolved", "partial-in-range") and not (
            f.get("unresolvedWhat") or "").strip():
        fs_problems.append("%s %s 无 unresolvedWhat" % (f.get("id"), f.get("status")))
    for k in ("setup", "payoff"):
        if not isinstance(f.get(k), dict) or not f[k].get("quote"):
            fs_problems.append("%s %s 不完整" % (f.get("id"), k))
stats["foreshadows"] = len(cand.get("foreshadows", []))
stats["foreshadowProblems"] = fs_problems
if fs_problems:
    bad("foreshadows 形状问题：%d" % len(fs_problems))

# ── 额外：固定抽样探针 ────────────────────────────────────────────────────
located = [(p, q) for p, q in quote_objs if isinstance(q.get("start"), int)]
probe = located[::max(1, len(located) // 5)][:5]
stats["fixedProbe"] = []
for p, q in probe:
    ok = TEXT[q["start"]:q["end"]] == q["quote"]
    stats["fixedProbe"].append({"path": p, "start": q["start"], "ok": ok})
    if not ok:
        bad("固定抽样失败：%s %r" % (p, q["quote"][:40]))

# ── 额外：same-quote 跨任务复用报数（不是失败，只报数） ───────────────────
per_task = {}
for t in cand.get("tasks", []):
    for f in FIELDS:
        for q in (t.get(f + "Quotes") or []):
            per_task.setdefault(q["quote"], []).append("%s.%s" % (t["id"], f))
cross = {k: v for k, v in per_task.items() if len({x.split(".")[0] for x in v}) > 1}
stats["crossTaskQuoteReuse"] = {
    "strings": len(cross),
    "detail": {k[:34]: v for k, v in list(cross.items())[:6]},
}

stats["fails"] = fails
stats["verdict"] = "pass" if not fails else "fail"

print(json.dumps(stats, ensure_ascii=False, indent=1))
sys.exit(0 if not fails else 1)
