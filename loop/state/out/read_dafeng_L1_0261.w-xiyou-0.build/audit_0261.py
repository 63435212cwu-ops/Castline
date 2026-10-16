#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计：只读 loop/state/out/read_dafeng_L1_0261.candidate.json，
   用与构建脚本**不同的代码路径**复算全部引文与结构约束。

与 build_0261.py 的差别（避免「自己验自己」）：
- 直接遍历 JSON 树，不依赖构建时的内存对象；
- 用 text.count() 与逐字符比对两条独立路径核对唯一性/逐字；
- 句界用 text.find 逐个标点扫描，而不是构建脚本里的 re.finditer 切分；
- 分区字段的枚举合法性单独判。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0261.candidate.json"

S, E = 1088909, 1094220
EXPECT = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

raw = DOCS.read_bytes()
full_sha = hashlib.sha256(raw).hexdigest()
TEXT = json.loads(raw.decode("utf-8"))[0]["text"]
SLICE = TEXT[S:E]
C = json.loads(CAND.read_text(encoding="utf-8"))

fails = []
notes = []


def fail(msg):
    fails.append(msg)


# ── 句界：find 扫描 ────────────────────────────────────────────────────────
# **独立实现**（不是 import 构建脚本）：逐标点 find 扫描。
# 收尾引号归属前一句 —— 这条归一化必须与构建脚本一致，否则两侧的
# 「共句」判定口径不同，审计会报出构建脚本并不存在的冲突（或反之）。
CLOSERS = "”’」』）】〉》"
bounds = [S]
pos = S
while True:
    hit = None
    for ch in "。！？\n":
        i = TEXT.find(ch, pos, E)
        if i >= 0 and (hit is None or i < hit):
            hit = i
    if hit is None:
        break
    bounds.append(hit + 1)
    pos = hit + 1
bounds.append(E)
SENTS = [list(x) for x in zip(bounds[:-1], bounds[1:])]
for i in range(1, len(SENTS)):
    a, b = SENTS[i]
    j = a
    while j < b and TEXT[j] in CLOSERS:
        j += 1
    if j > a:
        SENTS[i - 1][1] = j
        SENTS[i][0] = j
SENTS = [(a, b) for a, b in SENTS if b > a]


def sents_of(ref):
    return {i for i, (a, b) in enumerate(SENTS) if ref["start"] < b and ref["end"] > a}


# ── 引文全量复算 ───────────────────────────────────────────────────────────
refs = []


def walk(o, path):
    if isinstance(o, dict):
        if all(k in o for k in ("quote", "start", "end", "sourceHash")):
            refs.append((path, o))
        for k, v in o.items():
            walk(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i))


walk(C, "$")

verbatim = range_bad = hash_bad = uniq_bad = 0
for path, r in refs:
    if TEXT[r["start"]:r["end"]] != r["quote"]:
        verbatim += 1
        fail("逐字不符 @%s start=%d" % (path, r["start"]))
    if not (S <= r["start"] and r["end"] <= E):
        range_bad += 1
        fail("越界 @%s" % path)
    if r["sourceHash"] != EXPECT or r["sourceHash"] != full_sha:
        hash_bad += 1
        fail("sourceHash 不符 @%s" % path)
    if SLICE.count(r["quote"]) != 1:
        uniq_bad += 1
        fail("切片内不唯一(%d) @%s" % (SLICE.count(r["quote"]), path))

notes.append("引文复算：%d 条；逐字失败 %d，越界 %d，哈希失败 %d，切片内非唯一 %d"
             % (len(refs), verbatim, range_bad, hash_bad, uniq_bad))

# ── 五栏独立（区间不重叠 + 不共句）────────────────────────────────────────
COLS = ["objective", "obstacle", "action", "result", "cost"]
overlap_hits, sent_hits = 0, 0
for t in C["tasks"]:
    by_col = {}
    for col in COLS:
        blk = t.get(col)
        if not isinstance(blk, dict):
            continue
        by_col[col] = blk.get("quotes", [])
    flat = [(c, r) for c, rs in by_col.items() for r in rs]
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            (c1, r1), (c2, r2) = flat[i], flat[j]
            if r1["start"] < r2["end"] and r2["start"] < r1["end"]:
                overlap_hits += 1
                fail("五栏区间重叠 %s %s/%s" % (t["id"], c1, c2))
    cols = list(by_col)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            shared = set().union(*[sents_of(r) for r in by_col[cols[i]]]) & \
                     set().union(*[sents_of(r) for r in by_col[cols[j]]])
            if shared:
                sent_hits += 1
                fail("五栏共句 %s %s/%s 句=%s" % (t["id"], cols[i], cols[j], sorted(shared)))

notes.append("五栏独立：区间重叠 %d，共句 %d" % (overlap_hits, sent_hits))

# ── null 栏必须带 Note ────────────────────────────────────────────────────
null_total = null_ok = 0
for t in C["tasks"]:
    for col in COLS:
        if t.get(col) is None:
            null_total += 1
            n = t.get(col + "Note")
            if isinstance(n, str) and len(n.strip()) >= 20:
                null_ok += 1
            else:
                fail("null 栏缺理由 %s.%s" % (t["id"], col))
# 顶层 null（如 foreshadows.payoff）
for f in C["foreshadows"]:
    if f.get("payoff") is None:
        null_total += 1
        n = f.get("payoffNote")
        if isinstance(n, str) and len(n.strip()) >= 20:
            null_ok += 1
        else:
            fail("foreshadow payoff 为 null 但缺 payoffNote %s" % f["id"])
notes.append("null 栏：%d 个，带理由 %d 个" % (null_total, null_ok))

# ── basis 合法性 ──────────────────────────────────────────────────────────
LEGAL = {"explicit", "inferred", "derived", "unverified"}
bad_basis = 0


def check_basis(o, path):
    global bad_basis
    if isinstance(o, dict):
        if "basis" in o:
            if o["basis"] not in LEGAL:
                bad_basis += 1
                fail("非法 basis=%r @%s" % (o["basis"], path))
        for k, v in o.items():
            check_basis(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            check_basis(v, "%s[%d]" % (path, i))


check_basis(C, "$")
notes.append("basis 非法值：%d" % bad_basis)

# ── 分区字段枚举合法性 ────────────────────────────────────────────────────
for w in C["worldSettings"]:
    k = w.get("kind")
    if k == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            fail("place 缺/非法 placeState：%s" % w.get("id"))
    elif k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or set(st) - {"hold", "transfer", "use", "lose"}:
            fail("item 缺/非法 itemStates：%s -> %r" % (w.get("id"), st))
    elif k == "rule":
        if w.get("institution") not in ("declared", "executed", "misunderstood"):
            fail("rule 缺/非法 institution：%s" % w.get("id"))
    else:
        fail("未知 kind：%r" % k)
    if not (w.get("explain") or "").strip():
        fail("worldSetting 缺 explain：%s" % w.get("id"))
notes.append("worldSettings：rule %d / place %d / item %d"
             % (sum(1 for w in C["worldSettings"] if w["kind"] == "rule"),
                sum(1 for w in C["worldSettings"] if w["kind"] == "place"),
                sum(1 for w in C["worldSettings"] if w["kind"] == "item")))

# ── themeReadings 三件套 ──────────────────────────────────────────────────
if len(C["themeReadings"]) > 2:
    fail("themeReadings 超过 2 条")
for th in C["themeReadings"]:
    for k in ("perspective", "support", "counter"):
        if not th.get(k):
            fail("themeReading %s 缺 %s" % (th["id"], k))
    for c in th.get("counter", []):
        if not c.get("quoteRefs"):
            fail("themeReading %s 的 counter 无引文" % th["id"])
notes.append("themeReadings：%d 条，三件套齐全" % len(C["themeReadings"]))

# ── 结论不得是 semanticReview 完成 ────────────────────────────────────────
if C.get("semanticReview") is not False:
    fail("semanticReview 必须为 false")
if "未完成" not in C.get("semanticReviewNote", ""):
    fail("semanticReviewNote 未声明未完成")

# ── 声明的自检数字必须与实际一致 ──────────────────────────────────────────
m = C["machineSelfCheck"]
if m["quoteRefTotal"] != len(refs):
    fail("自检引文数不符：声明 %d 实际 %d" % (m["quoteRefTotal"], len(refs)))
if m["sourceHashRecomputed"] != full_sha:
    fail("自检 sourceHash 与实际不符")
if m["sliceSha256"] != hashlib.sha256(SLICE.encode()).hexdigest():
    fail("自检 sliceSha256 与实际不符")
if not m["sliceStartsWithUnitHead"]:
    fail("切片未以单元标题开头")
if m["taskColumnQuoteCollisions"] != overlap_hits:
    fail("自检区间重叠数不符：声明 %d 实际 %d" % (m["taskColumnQuoteCollisions"], overlap_hits))
if m["taskColumnSentenceCollisions"] != sent_hits:
    fail("自检共句数不符：声明 %d 实际 %d" % (m["taskColumnSentenceCollisions"], sent_hits))
if m["nullColumnsTotal"] != null_total:
    fail("自检 null 栏数不符：声明 %d 实际 %d" % (m["nullColumnsTotal"], null_total))

# 复用披露如实
counts = {}
for _, r in refs:
    counts[(r["start"], r["end"])] = counts.get((r["start"], r["end"]), 0) + 1
actual_reused = sum(1 for v in counts.values() if v > 1)
d = C["quoteReuseDisclosure"]
if d["spansUsedMoreThanOnce"] != actual_reused:
    fail("复用披露不符：声明 %d 实际 %d" % (d["spansUsedMoreThanOnce"], actual_reused))
if d["distinctSpans"] != len(counts):
    fail("去重 span 数不符：声明 %d 实际 %d" % (d["distinctSpans"], len(counts)))

# ── 反向自查：本区间里最容易被漏掉的几件事是否至少有落点 ──────────────────
must_touch = [
    ("橘子皮致伤", "橘子皮"),
    ("大光头", "大光头"),
    ("抓阄两题", "咏志"),
    ("两首诗交付", "阅后即焚"),
    ("厄运机制", "厄运是时刻影响着身边人"),
    ("会试九天", "历时九天"),
    ("云鹿书院天花板", "无缘状元"),
    ("糊名誊抄失效", "糊名和誊抄"),
    ("国子监禁锢", "禁锢在了四书五经里"),
    ("预言师守秘", "预言师更要懂得守秘"),
    ("蛊族处境", "蛊族人的身份"),
    ("四号回京", "我已经回京了"),
    ("五号游历", "南疆去京城游历"),
    ("生死自负", "生死自负"),
    ("会试送考", "送许新年去贡院"),
    ("婶婶黑眼圈", "黑眼圈"),
]
blob = json.dumps(C, ensure_ascii=False)
missing = [name for name, key in must_touch if key not in blob]
if missing:
    fail("反向自查：以下区间事实在产物中无落点：%s" % missing)
notes.append("反向自查落点：%d/%d" % (len(must_touch) - len(missing), len(must_touch)))

# ── 覆盖分段必须恰好铺满区间（相邻段 end == 下段 start）──────────────────
seg_txt = C["coverage"]["segments"]
seg_nums = []
import re as _re
for s in seg_txt:
    m = _re.search(r"（(\d+)[–-](\d+)", s)
    if not m:
        fail("覆盖分段无法解析：%r" % s)
        continue
    seg_nums.append((int(m.group(1)), int(m.group(2))))
if seg_nums[0][0] != S or seg_nums[-1][1] != E:
    fail("覆盖分段未覆盖到区间端点")
for i in range(len(seg_nums) - 1):
    if seg_nums[i][1] != seg_nums[i + 1][0]:
        fail("覆盖分段不连续：%d != %d" % (seg_nums[i][1], seg_nums[i + 1][0]))
if sum(b - a for a, b in seg_nums) != E - S:
    fail("覆盖分段总长 %d != 区间长 %d" % (sum(b - a for a, b in seg_nums), E - S))
for a, b in seg_nums:
    if not (S <= a < b <= E):
        fail("覆盖分段越界：%d-%d" % (a, b))
notes.append("覆盖分段：%d 段，恰好铺满 [%d,%d)" % (len(seg_nums), S, E))

# ── 声称的机器可数数字必须与原文一致 ──────────────────────────────────────
tr = C["coverage"].get("transmissions")
if tr:
    if tr["paragraphsOpening"] != len([p for p in SLICE.split("\n") if "【" in p]):
        fail("transmissions.paragraphsOpening 声明 %d，实际 %d"
             % (tr["paragraphsOpening"], len([p for p in SLICE.split("\n") if "【" in p])))
    if tr["closingMarkers"] != SLICE.count("】"):
        fail("transmissions.closingMarkers 声明 %d，实际 %d"
             % (tr["closingMarkers"], SLICE.count("】")))
    notes.append("传书标记：【 段 %d，】 %d（不相等已由原文解释：一号三条跨段续写）"
                 % (tr["paragraphsOpening"], tr["closingMarkers"]))

# ── t5 的 null 理由所依赖的「同句」判断必须成立 ───────────────────────────
# 口径同构建脚本：收尾引号归属前一句（审计早期版本漏了这条归一化，
# 曾据此误判 t9 的 action 应记 null；修正后 t9 已改为实证引文）。
CLOSERS = "”’」』）】〉》"


def sentence_units(s, e):
    spans, start = [], s
    pos = s
    while pos < e:
        hit = None
        for ch in "。！？\n":
            i = TEXT.find(ch, pos, e)
            if i >= 0 and (hit is None or i < hit):
                hit = i
        if hit is None:
            break
        spans.append([start, hit + 1])
        start = pos = hit + 1
    if start < e:
        spans.append([start, e])
    for i in range(1, len(spans)):
        a, b = spans[i]
        j = a
        while j < b and TEXT[j] in CLOSERS:
            j += 1
        if j > a:
            spans[i - 1][1] = j
            spans[i][0] = j
    return [(a, b) for a, b in spans if b > a]


UNITS = sentence_units(S, E)

t5 = next(x for x in C["tasks"] if x["id"] == "t5_limiaozhen_warn_lina")
if t5.get("action") is not None:
    fail("t5.action 应为 null（其理由依赖同句判断）")
else:
    oref = t5["objective"]["quotes"][0]
    u = next((a, b) for a, b in UNITS if a <= oref["start"] < b)
    if "加入话题" not in TEXT[u[0]:u[1]]:
        fail("t5.action 的「同句」理由不成立：提示语不在 objective 所在句内")
    else:
        notes.append("t5 的 null 理由（同句复用提示语）：成立")

# t9 的 action 已改为实证引文：必须与 objective 不同句，否则是共句违规
t9 = next(x for x in C["tasks"] if x["id"] == "t9_xuqian_hand_over_poems")
if t9.get("action") is None:
    fail("t9.action 不应为 null（审计已判定递纸条是独立句）")
else:
    aref = t9["action"]["quotes"][0]
    oref = t9["objective"]["quotes"][0]
    ua = next((a, b) for a, b in UNITS if a <= aref["start"] < b)
    uo = next((a, b) for a, b in UNITS if a <= oref["start"] < b)
    if ua == uo:
        fail("t9.action 与 objective 同句 —— 违反栏位独立")
    else:
        notes.append("t9.action 与 objective 分属不同句：成立")

print("=== 独立审计结果 ===")
for n in notes:
    print(" ·", n)
print(" 引文总数 %d，去重 span %d，跨分区复用 %d" % (len(refs), len(counts), actual_reused))
if fails:
    print("\n不通过项 %d：" % len(fails))
    for f in fails:
        print("  ✗", f)
    sys.exit(1)
print("\n全部通过：0 项不通过。")
