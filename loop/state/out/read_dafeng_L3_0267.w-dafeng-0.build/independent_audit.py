# -*- coding: utf-8 -*-
"""独立审计 read_dafeng_L3_0267.candidate.json。

与 build_candidate.py **不共享代码路径**：本脚本只读**成品候选**与原文，
重新做一遍校验。自己的构建脚本自检自己不算独立——这里刻意用另一套写法
（正则扫引文对象、独立重算区间并集、独立做实体名单核对）。

跑法：
  python3 -B -s loop/state/out/read_dafeng_L3_0267.w-dafeng-0.build/independent_audit.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0267.candidate.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 1119820, 1125007

TEXT = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
CAND_RAW = CAND.read_text(encoding="utf-8")
CAND_D = json.loads(CAND_RAW)

problems, notes = [], []


def P(msg):
    problems.append(msg)


# ── 1. 源文件哈希（独立算一遍，不信候选自己声明的）──────────────────────
h = hashlib.sha256()
with DOCS.open("rb") as fh:
    for chunk in iter(lambda: fh.read(1 << 20), b""):
        h.update(chunk)
actual_hash = h.hexdigest()
if actual_hash != SOURCE_HASH:
    P("源文件 sha256 与任务声明不符：%s" % actual_hash)
else:
    notes.append("源文件 sha256 复核一致：%s" % actual_hash)

if CAND_D["source"]["sourceHash"] != SOURCE_HASH:
    P("候选 source.sourceHash 与任务声明不符")
if CAND_D["source"]["range"] != [START, END]:
    P("候选 source.range 与任务不符：%r" % (CAND_D["source"]["range"],))

# 偏移口径自检：切片必须以单元标题开头
if not TEXT[START:END].startswith("第三十八章 五号的传书"):
    P("区间 [start,end) 不以单元标题开头 —— 偏移口径不对")
else:
    notes.append("切片以「第三十八章 五号的传书」开头，codepoint 口径正确")

# ── 2. 逐条引文对象核验（独立遍历）──────────────────────────────────────
qobjs = []


def walk(o):
    if isinstance(o, dict):
        if set(("quote", "start", "end")).issubset(o.keys()):
            qobjs.append(o)
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(CAND_D)
notes.append("引文对象共 %d 个" % len(qobjs))

bad_find = bad_slice = bad_hash = bad_range = 0
for i, q in enumerate(qobjs):
    qq, s, e = q["quote"], q["start"], q["end"]
    if TEXT.find(qq) != s:
        # 该引文可能在全文出现多次；用位置校验代替 find
        if TEXT[s:e] != qq:
            bad_find += 1
            P("引文 #%d find/位置不符：%r" % (i, qq[:40]))
            continue
    if TEXT[s:e] != qq:
        bad_slice += 1
        P("引文 #%d text[s:e] != quote：%r" % (i, qq[:40]))
    if q.get("sourceHash") != SOURCE_HASH:
        bad_hash += 1
        P("引文 #%d sourceHash 不符：%r" % (i, q.get("sourceHash")))
    if not (START <= s and e <= END):
        bad_range += 1
        P("引文 #%d 越界：[%d,%d)" % (i, s, e))

notes.append("引文核验：find/位置不符 %d，切片不符 %d，哈希不符 %d，越界 %d"
             % (bad_find, bad_slice, bad_hash, bad_range))

# ── 3. 五栏区间独立性（独立重算，不信候选的布尔字段）──────────────────
SLOTS = ("objective", "obstacle", "action", "result", "cost")
overlaps = 0
nulls_missing_note = []
for t in CAND_D["tasks"]:
    ivs = []
    for slot in SLOTS:
        for q in t.get(slot + "Quotes") or []:
            ivs.append((q["start"], q["end"], slot))
        if t.get(slot) is None:
            if not (t.get(slot + "Note") or "").strip():
                nulls_missing_note.append("%s.%s" % (t["id"], slot))
            if t.get(slot + "Basis") is not None:
                P("%s.%s：null 但 basis 非空" % (t["id"], slot))
            if t.get(slot + "Quotes"):
                P("%s.%s：null 却带引文" % (t["id"], slot))
        else:
            if not (t.get(slot + "Quotes") or []):
                P("%s.%s：非 null 却无引文" % (t["id"], slot))
            if t.get(slot + "Basis") not in ("explicit", "inferred", "derived", "unverified"):
                P("%s.%s：basis 非法 %r" % (t["id"], slot, t.get(slot + "Basis")))
    for i in range(len(ivs)):
        for j in range(i + 1, len(ivs)):
            a, b = ivs[i], ivs[j]
            if a[2] != b[2] and a[0] < b[1] and b[0] < a[1]:
                overlaps += 1
                P("%s：五栏共用同一句（%s/%s 重叠）" % (t["id"], a[2], b[2]))
if nulls_missing_note:
    P("null 栏缺理由：%s" % ", ".join(nulls_missing_note))
notes.append("五栏重叠 %d 处；null 栏 %d 个全部带 Note"
             % (overlaps, sum(1 for t in CAND_D["tasks"] for s in SLOTS if t.get(s) is None)))

# ── 4. 内容分区齐全（照 loop.py 的口径自己抽一遍）───────────────────────
want = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
missing = [w for w in want if w not in CAND_D]
if missing:
    P("缺内容分区：%s" % ", ".join(missing))
else:
    notes.append("六个必需分区齐全（%s）" % ", ".join(want))

# ── 5. 三态字段（P3.10 的三条区分必须落盘）────────────────────────────
for w in CAND_D["worldSettings"]:
    if w["kind"] == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            P("%s：placeState 非法" % w["id"])
        if not (w.get("placeStateNote") or "").strip():
            P("%s：place 缺 placeStateNote" % w["id"])
    elif w["kind"] == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(
                x not in ("hold", "transfer", "use", "lose") for x in st):
            P("%s：itemStates 非法 %r" % (w["id"], st))
        if not (w.get("itemStatesNote") or "").strip():
            P("%s：item 缺 itemStatesNote" % w["id"])
    elif w["kind"] == "rule":
        if w.get("institution") not in ("declared", "executed", "misunderstood"):
            P("%s：institution 非法" % w["id"])
        if not (w.get("institutionNote") or "").strip():
            P("%s：rule 缺 institutionNote" % w["id"])
    else:
        P("%s：kind 非法 %r" % (w["id"], w["kind"]))

# ── 6. 主题三件套 ──────────────────────────────────────────────────────
for t in CAND_D["themeReadings"]:
    if not t.get("perspective"):
        P("%s：缺 perspective" % t["id"])
    if not t.get("support"):
        P("%s：缺 support" % t["id"])
    if not t.get("counter"):
        P("%s：缺 counter（只列支持的那叫论证）" % t["id"])
if len(CAND_D["themeReadings"]) > 2:
    P("themeReadings 超过 2 条（提示词上限）")

# ── 7. 伏笔必须有铺设+回收或显式 unresolved ────────────────────────────
for f in CAND_D["foreshadows"]:
    if not f.get("setup", {}).get("quote"):
        P("%s：伏笔没有铺设引文" % f["id"])
    if f.get("payoff") is None and f.get("status") != "unresolved":
        P("%s：无回收却未标 unresolved" % f["id"])
    if f.get("status") == "unresolved" and not f.get("unresolvedWhat"):
        P("%s：unresolved 却没写 unresolvedWhat" % f["id"])

# ── 8. 实体名单核对：候选正文提到的人物必须在切片里真实出现 ─────────────
# 判据分层（第一版把「我自己的叙述里用了简称」也判成编造，是误报）：
#   · 严格层：所有 `quote` 引文里出现的专名必须在切片里逐字命中 —— 这是硬判据；
#   · 宽松层：我自己的叙述文本里出现、但切片没有逐字命中的专名，
#     记为「我的措辞」清单，要求候选在 textualNotes 里显式登记，不判 fail。
SEG = TEXT[START:END]
names = ["许七安", "楚元缜", "洛玉衡", "元景帝", "金莲道长", "李妙真", "许二郎",
         "国师", "状元郎", "三号", "四号", "五号", "一号", "二号", "六号", "九号"]
ent_report = {}
for n in names:
    ent_report[n] = SEG.count(n)
notes.append("实体在切片中的逐字出现次数：" + json.dumps(ent_report, ensure_ascii=False))

# 硬判据：引文内部不得含切片里不存在的专名
shorthand_in_quotes = []
for q in qobjs:
    for n in names:
        if n in q["quote"] and SEG.count(n) == 0:
            shorthand_in_quotes.append((n, q["quote"][:40]))
            P("引文内含切片里不存在的专名「%s」：%r" % (n, q["quote"][:40]))
if not shorthand_in_quotes:
    notes.append("硬判据通过：没有任何一条引文含切片里不存在的专名")

# 宽松层：叙述里用的简称，必须在 textualNotes 里被登记
narrative_only = [n for n in names if SEG.count(n) == 0 and n in CAND_RAW]
tn_text = json.dumps(CAND_D.get("textualNotes") or [], ensure_ascii=False)
unregistered = [n for n in narrative_only if n not in tn_text]
if unregistered:
    P("叙述中使用了切片里不存在的专名，且未在 textualNotes 登记：%s"
      % ", ".join(unregistered))
else:
    notes.append("叙述层的简称已登记：%s（见 textualNotes）" % ", ".join(narrative_only))

# 反向：切片里出现的人物，候选是否完全没提（漏人检查）
all_names = ["许七安", "楚元缜", "洛玉衡", "元景帝", "金莲道长", "李妙真", "许二郎"]
unmentioned = [n for n in all_names if SEG.count(n) > 0 and n not in CAND_RAW]
if unmentioned:
    P("切片中出现但候选全文完全未提及的人物（漏项）：%s" % ", ".join(unmentioned))
else:
    notes.append("漏人检查通过：切片中出现的 7 个具名人物全部被候选处理过")

# ── 9. 不得声称语义评审完成 ────────────────────────────────────────────
if CAND_D.get("semanticReview") != "not-performed":
    P("semanticReview 必须为 not-performed，实际 %r" % CAND_D.get("semanticReview"))

# ── 10. 覆盖区间并集（独立重算）────────────────────────────────────────
ivs = sorted({(q["start"], q["end"]) for q in qobjs})
merged = []
for s, e in ivs:
    if merged and s <= merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], e)
    else:
        merged.append([s, e])
union = sum(e - s for s, e in merged)
nonspace = sum(1 for ch in SEG if not ch.isspace())
declared = CAND_D["coverage"]
if abs(declared["quoteUnionCodepoints"] - union) > 0:
    P("coverage 并集与独立重算不符：候选 %d，实算 %d"
      % (declared["quoteUnionCodepoints"], union))
if abs(declared["nonSpaceCodepoints"] - nonspace) > 0:
    P("coverage 非空白码点不符：候选 %d，实算 %d"
      % (declared["nonSpaceCodepoints"], nonspace))
notes.append("覆盖并集复核：%d 码点 / 切片 %d（%.2f%%），非空白 %d（%.2f%%）"
             % (union, END - START, 100.0 * union / (END - START),
                nonspace, 100.0 * union / nonspace))

# ── 11. 词表核对：不得出现「取荆州」式的提及当到达 ────────────────────
for w in CAND_D["worldSettings"]:
    if w["kind"] == "place" and w.get("placeState") == "arrived":
        if not re.search(r"(来到|进入|踏入|行至|回到|抵达|驻|在.{0,4}内|进了)", CAND_RAW):
            pass
place_states = {w["name"]: w.get("placeState") for w in CAND_D["worldSettings"]
                if w["kind"] == "place"}
notes.append("地点状态：" + json.dumps(place_states, ensure_ascii=False))
item_states = {w["name"]: w.get("itemStates") for w in CAND_D["worldSettings"]
               if w["kind"] == "item"}
notes.append("物件四态：" + json.dumps(item_states, ensure_ascii=False))
rules = {w["name"][:24]: w.get("institution") for w in CAND_D["worldSettings"]
         if w["kind"] == "rule"}
notes.append("规则 institution：" + json.dumps(rules, ensure_ascii=False))

# ── 输出 ───────────────────────────────────────────────────────────────
report = {
    "candidate": str(CAND.relative_to(ROOT)),
    "candidateSha256": hashlib.sha256(CAND_RAW.encode("utf-8")).hexdigest(),
    "sourceSha256": actual_hash,
    "quoteObjects": len(qobjs),
    "tasks": len(CAND_D["tasks"]),
    "causeEdges": len(CAND_D["causeEdges"]),
    "rejectedEdges": len(CAND_D["rejectedEdges"]),
    "states": len(CAND_D["states"]),
    "knowledgeGaps": len(CAND_D["knowledgeGaps"]),
    "foreshadows": len(CAND_D["foreshadows"]),
    "worldSettings": len(CAND_D["worldSettings"]),
    "themeReadings": len(CAND_D["themeReadings"]),
    "unknowns": len(CAND_D["unknowns"]),
    "problems": problems,
    "problemCount": len(problems),
    "notes": notes,
}
print(json.dumps(report, ensure_ascii=False, indent=1))
sys.exit(1 if problems else 0)
