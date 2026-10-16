#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立核验 read:dafeng:L3:0223 的**成品**（从磁盘重读，不依赖构建脚本的内存状态）。

用法：python3 -B -s loop/state/out/read_dafeng_L3_0223.w-dafeng-1.build/verify_candidate.py

核验项（逐条报数，不概括成「已通过」）：
  1. sourceHash == task.sourceHash（重算整份 docs.json 的 sha256）
  2. docs[0].text[START:END] 以 unitHead 开头
  3. 遍历成品里**每一个** quote 对象（含嵌套）：text[find] 逐字命中、text[start:end]==quote、
     落在区间内、start/end 是 int、sourceHash 字段正确
  4. 同一任务五栏：引文字符串互不相同、区间互不重叠
  5. null 栏位必须有同名 <栏位>Note
  6. 六个必需分区存在
  7. worldSettings 形状
  8. themeReadings 形状
  9. 散文里的专名逐个在区间原文 find 命中
 10. 把反例（fails）逐条打印，退出码 0=全过 / 1=有失败
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DOCS = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop", "state", "out", "read_dafeng_L3_0223.candidate.json")
TASKF = os.path.join(ROOT, "loop", "state", "runs", "task-read_dafeng_L3_0223.json")

fails = []
stats = {}


def bad(m):
    fails.append(m)


task = json.load(open(TASKF, encoding="utf-8"))
START, END = task["sourceRange"]
UNIT_HEAD = task["unitHead"]
EXPECT = task["sourceHash"]

with open(DOCS, "rb") as fh:
    raw = fh.read()
got = hashlib.sha256(raw).hexdigest()
stats["docsSha256"] = got
if got != EXPECT:
    bad("docs.json sha256=%s != task.sourceHash=%s" % (got, EXPECT))

TEXT = json.loads(raw.decode("utf-8"))[0]["text"]
SLICE = TEXT[START:END]
if not SLICE.startswith(UNIT_HEAD):
    bad("区间不以 unitHead 开头：%r" % SLICE[:40])
stats["sliceCodepoints"] = len(SLICE)
stats["sliceSha256"] = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

cand = json.load(open(CAND, encoding="utf-8"))

# ── 3. 遍历每一个 quote 对象 ──────────────────────────────────────────────
quotes = []
paths = []


def walk(o, path=""):
    if isinstance(o, dict):
        if isinstance(o.get("quote"), str) and "start" in o and "end" in o:
            quotes.append((o, path))
        for k, v in o.items():
            walk(v, path + "/" + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + "[%d]" % i)


walk(cand)
stats["quoteObjects"] = len(quotes)

uniq_ok = 0
for q, path in quotes:
    s, e, t = q["start"], q["end"], q["quote"]
    if not isinstance(s, int) or not isinstance(e, int):
        bad("%s：start/end 非 int" % path)
        continue
    if TEXT[s:e] != t:
        bad("%s：text[start:end] != quote (%r vs %r)" % (path, TEXT[s:e][:30], t[:30]))
        continue
    if TEXT.find(t) == -1:
        bad("%s：quote 在全文 find 不到" % path)
        continue
    if not (START <= s and e <= END):
        bad("%s：quote [%d,%d) 越出区间" % (path, s, e))
        continue
    if q.get("sourceHash") != EXPECT:
        bad("%s：quote.sourceHash 不等于整文件哈希" % path)
        continue
    uniq_ok += 1
stats["quotesFullyVerified"] = uniq_ok

# ── 4. 同一任务五栏 ───────────────────────────────────────────────────────
FIVE = ["objective", "obstacle", "action", "result", "cost"]
stats["tasks"] = len(cand.get("tasks") or [])
for t in cand.get("tasks") or []:
    seen = {}
    ivs = []
    for f in FIVE:
        for q in (t.get(f + "Quotes") or []):
            if q.get("quote") is None:
                continue
            s, e = q["start"], q["end"]
            if q["quote"] in seen and seen[q["quote"]] != f:
                bad("%s：五栏共用同一句（%s/%s）" % (t["id"], seen[q["quote"]], f))
            seen[q["quote"]] = f
            ivs.append((s, e, f))
    for i in range(len(ivs)):
        for j in range(i + 1, len(ivs)):
            a, b = ivs[i], ivs[j]
            if a[2] != b[2] and a[0] < b[1] and b[0] < a[1]:
                bad("%s：五栏引文区间重叠 %s[%d,%d) %s[%d,%d)"
                    % (t["id"], a[2], a[0], a[1], b[2], b[0], b[1]))
    for f in FIVE:
        if t.get(f) is None and not t.get(f + "Note"):
            bad("%s：%s 为 null 但没有 %sNote" % (t["id"], f, f))
        if t.get(f) is not None and not (t.get(f + "Quotes") or []):
            bad("%s：%s 非空却无引文" % (t["id"], f))
stats["nullFields"] = sum(1 for t in (cand.get("tasks") or []) for f in FIVE if t.get(f) is None)
stats["nullFieldsWithNote"] = sum(1 for t in (cand.get("tasks") or []) for f in FIVE
                                  if t.get(f) is None and t.get(f + "Note"))

# ── 6. 必需分区 ───────────────────────────────────────────────────────────
REQ = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
for r in REQ:
    if r not in cand:
        bad("缺分区 %s" % r)
stats["sectionsPresent"] = sum(1 for r in REQ if r in cand)

# ── 7/8. 形状 ─────────────────────────────────────────────────────────────
stats["worldSettings"] = len(cand.get("worldSettings") or [])
for w in cand.get("worldSettings") or []:
    k = w.get("kind")
    if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        bad("worldSettings %s：placeState 非法" % w.get("id"))
    if k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(
                x not in ("hold", "transfer", "use", "lose") for x in st):
            bad("worldSettings %s：itemStates 非法 %r" % (w.get("id"), st))
    if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        bad("worldSettings %s：institution 非法" % w.get("id"))
    if k not in ("place", "item", "rule"):
        bad("worldSettings %s：kind 非法" % w.get("id"))
    if not w.get("explain"):
        bad("worldSettings %s：缺 explain" % w.get("id"))
stats["worldSettingsKinds"] = sorted(set((w.get("kind") or "?")
                                        for w in (cand.get("worldSettings") or [])))

stats["themeReadings"] = len(cand.get("themeReadings") or [])
for th in cand.get("themeReadings") or []:
    for k in ("perspective", "support", "counter"):
        if not th.get(k):
            bad("themeReadings %s：缺 %s" % (th.get("id"), k))

# ── 9. 专名防编造 ─────────────────────────────────────────────────────────
PROPER = ["宋长辅", "梁有平", "张巡抚", "姜律中", "许七安", "杨川南", "周旻",
          "南宫倩柔", "杨千幻", "云州", "白帝城", "驿站", "布政使", "都指挥使",
          "经历司", "齐党", "打更人", "巫神教", "梦巫", "望气术", "气数",
          "丁15号", "狗肉铺", "黄伯街", "福顺镖局", "仵作", "知府",
          "刑法大典", "站刑", "四号", "银锣", "铜锣", "虎贲卫",
          "宁宴", "暗子", "账簿", "麻袋", "匕首", "小黑屋", "布政使司衙门"]
for nm in PROPER:
    if SLICE.find(nm) == -1:
        bad("专名不在本区间：%s" % nm)
stats["properNounsChecked"] = len(PROPER)

# ── 语义红旗：把人物话语当叙述事实的自查（只报可疑，不自动判死）──────
flags = []
for t in cand.get("tasks") or []:
    for f in FIVE:
        for q in (t.get(f + "Quotes") or []):
            tq = q.get("quote") or ""
            if tq.startswith("\u201c") and t.get(f + "Basis") == "explicit" \
                    and "陈述" not in (t.get(f + "Note") or ""):
                flags.append("%s.%s 引的是引号内话语但 Note 没标「人物陈述」" % (t["id"], f))
stats["speechFlags"] = flags

out = {
    "candidate": "loop/state/out/read_dafeng_L3_0223.candidate.json",
    "candidateSha256": hashlib.sha256(open(CAND, "rb").read()).hexdigest(),
    "task": task["id"],
    "stats": stats,
    "fails": fails,
    "speechFlags": flags,
    "verdict": "pass" if not fails else "fail",
}
print(json.dumps(out, ensure_ascii=False, indent=1))
sys.exit(0 if not fails else 1)
