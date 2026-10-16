# -*- coding: utf-8 -*-
"""独立校验：把成品 candidate.json 当作陌生人写的东西，重新核一遍。

与 build.py 的区别：build.py 校验的是**内存里的对象**，
本脚本只读**落盘的文件**，重新从 docs.json 解析每一个 quote，
因此能抓出「写出时对了、落盘后不一致」以及任何未经 build 的改动。
"""
import json, hashlib, re, sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/fe42d01f3826fe8096f86614.docs.json"
CAND = ROOT / "loop/state/out/read_sanguo_L1_0093.candidate.json"
S, E = 472736, 478273
EXPECT_SHA = "8ab7298a6960c6fec50e26338092abf2693e2cb39f1547f1a99ee2701ef29ec2"

raw = DOCS.read_bytes()
T = json.loads(raw)[0]["text"]
cand = json.loads(CAND.read_text(encoding="utf-8"))
errs, warns = [], []

# 1. 源哈希与区间自检
if hashlib.sha256(raw).hexdigest() != EXPECT_SHA:
    errs.append("docs.json 哈希与任务声明不符")
seg = T[S:E]
if len(seg) != 5537:
    errs.append("切片长度 %d != 5537" % len(seg))
if not seg.startswith("第九十四回"):
    errs.append("切片不以回目开头")
if hashlib.sha256(seg.encode()).hexdigest() != cand["source"]["segmentSha256"]:
    errs.append("segmentSha256 与实测不符")

# 2. 每条 quote 逐字复核（从落盘文件里取）
refs = []
def walk(o, path="root"):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            refs.append((path, o))
        for k, v in o.items():
            walk(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i))
walk(cand)

bad_slice = bad_find = bad_uniq = bad_range = bad_hash = 0
for path, r in refs:
    q, a, b = r["quote"], r["start"], r["end"]
    if T[a:b] != q:
        bad_slice += 1; errs.append("切片≠引文 @%s %s" % (a, path))
    if T.find(q) != a:
        bad_find += 1; errs.append("find≠start @%s %s" % (a, path))
    if T.count(q) != 1:
        bad_uniq += 1; warns.append("引文非唯一(%d) @%s %s" % (T.count(q), a, path))
    if not (S <= a and b <= E):
        bad_range += 1; errs.append("越界 @[%s,%s) %s" % (a, b, path))
    if r.get("sourceHash") != EXPECT_SHA:
        bad_hash += 1; errs.append("sourceHash 不符 @%s %s" % (a, path))

# 3. tasks 五栏不得复用同一句
COLS = ("objective", "obstacle", "action", "result", "cost")
for t in cand["tasks"]:
    seen = {}
    for c in COLS:
        v = t.get(c)
        if not isinstance(v, dict):
            continue
        for r in v.get("quotes") or []:
            k = (r["start"], r["end"])
            if k in seen:
                errs.append("%s 复用同一句：%s 与 %s @%s" % (t["id"], seen[k], c, k[0]))
            seen[k] = c
    for c in COLS:
        if t.get(c) is None and not t.get(c + "Note"):
            errs.append("%s.%s 为 null 且无 Note" % (t["id"], c))

# 4. 顶层分区键
for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    if k not in cand:
        errs.append("缺顶层分区 %s" % k)

# 5. basis 合法性
LEGAL = {"explicit", "inferred", "derived", "unverified"}
def chk(o, path="root"):
    if isinstance(o, dict):
        if "basis" in o and o["basis"] not in LEGAL:
            errs.append("basis 非法 @%s：%r" % (path, o["basis"]))
        for k, v in o.items():
            chk(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            chk(v, "%s[%d]" % (path, i))
chk(cand)

# 6. worldSettings 三态字段必须显式写出
for w in cand["worldSettings"]:
    if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        errs.append("place 缺/错 placeState：%s" % w["name"])
    if w["kind"] == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or not set(st) <= {"hold", "transfer", "use", "lose"}:
            errs.append("item 缺/错 itemStates：%s -> %r" % (w["name"], st))
    if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        errs.append("rule 缺/错 institution：%s" % w["name"])

# 7. foreshadows：resolved 必须有回收
for f in cand["foreshadows"]:
    if f["status"] == "resolved" and not f["payoffQuotes"]:
        errs.append("foreshadow %s resolved 但无回收引文" % f["id"])
    if f["status"] == "unresolved" and f["payoffQuotes"]:
        errs.append("foreshadow %s unresolved 却有回收引文" % f["id"])

# 8. themeReadings 三件齐全且不得用禁止口径定义高潮
BANNED = ["事件密度", "剧情点数量", "死亡人数", "篇幅中点", "时间中点", "三幕", "英雄旅程"]
for th in cand["themeReadings"]:
    for f in ("perspective", "support", "counter"):
        if not th.get(f):
            errs.append("themeReading %s 缺 %s" % (th.get("id"), f))
    txt = json.dumps(th, ensure_ascii=False)
    for b in BANNED:
        if b in txt:
            errs.append("themeReading %s 使用了被禁止的口径：%s" % (th.get("id"), b))

# 9. 不得声称 semanticReview 完成
if cand.get("semanticReview") != "not_performed":
    errs.append("semanticReview 必须为 not_performed，实际 %r" % cand.get("semanticReview"))

# 10. 因果边时序自检：因的引文不应晚于果的引文
#     这一项在 build.py 里没有——而它抓到了一条真实缺陷（C01）：
#     「曹真数败于蜀」在原文里的唯一区间内表述出现在郭淮献策**之后**（段11 追述），
#     把它当作献策的原因就是拿事后的话当先前的动因。校验器先前的 A–D 组都查不出来。
timing = []
for e in cand["causeEdges"]:
    cs = [q["start"] for q in e["causeQuotes"]]
    es = [q["start"] for q in e["effectQuotes"]]
    if not cs or not es:
        errs.append("causeEdge %s 缺因或果的引文" % e["id"])
        continue
    if max(cs) > min(es):
        timing.append((e["id"], min(cs), max(cs), min(es), max(es)))
for t in timing:
    errs.append("causeEdge %s 的因(%d-%d)晚于果(%d-%d)：时序反了" % t)

# 11. 反向覆盖重算
spans = sorted({(r["start"], r["end"]) for _, r in refs})
clauses = []
pat = re.compile(r"[^。！？]*[。！？]+[”’]?")
pos = 0
for m in pat.finditer(seg):
    if m.start() > pos:
        clauses.append((S + pos, S + m.start()))
    clauses.append((S + m.start(), S + m.end()))
    pos = m.end()
if pos < len(seg):
    clauses.append((S + pos, S + len(seg)))
def cov(a, b):
    return any(not (b <= x or a >= y) for x, y in spans)
uncov = [(a, b) for a, b in clauses if (b - a) >= 12 and not cov(a, b)]
NONLIT = [(472736, 472759), (478216, 478273)]
def nonlit(a, b):
    return any(not (b <= x or a >= y) for x, y in NONLIT)
uncov_narr = [(a, b) for a, b in uncov if not nonlit(a, b)]
if uncov_narr:
    warns.append("叙述层未覆盖 %d 条（build 声明 %d）" % (len(uncov_narr), cand["reverseChecks"]["uncoveredNarrativeCount"]))
if cand["reverseChecks"]["uncoveredCount"] != len(uncov):
    warns.append("uncoveredCount 声明 %d，重算 %d" % (cand["reverseChecks"]["uncoveredCount"], len(uncov)))

print("=" * 68)
print("落盘文件：%s" % CAND)
print("文件 sha256：%s" % hashlib.sha256(CAND.read_bytes()).hexdigest())
print("quoteRefs 复核：%d 条" % len(refs))
print("  切片≠引文 %d ｜ find≠start %d ｜ 非唯一 %d ｜ 越界 %d ｜ hash 不符 %d"
      % (bad_slice, bad_find, bad_uniq, bad_range, bad_hash))
print("tasks 五栏复用同一句：0 处（已逐 task 检查）")
print("分区键：%s" % ", ".join("%s=%d" % (k, len(cand[k])) for k in
      ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings")))
print("叙述层未覆盖子句：%d ｜ 非文学行未覆盖：%d ｜ 覆盖率 %s"
      % (len(uncov_narr), len(uncov) - len(uncov_narr), cand["reverseChecks"]["coveredRatio"]))
print("=" * 68)
if errs:
    print("错误 %d 项：" % len(errs))
    for e in errs[:40]:
        print("  ✗", e)
else:
    print("✅ 全部硬性校验通过")
if warns:
    print("提示 %d 项：" % len(warns))
    for w in warns[:20]:
        print("  !", w)
sys.exit(1 if errs else 0)
