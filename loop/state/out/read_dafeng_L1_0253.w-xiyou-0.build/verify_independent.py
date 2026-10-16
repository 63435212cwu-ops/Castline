# -*- coding: utf-8 -*-
"""独立验证：从磁盘候选重新读起，源文件重开、哈希重算。

与构建脚本**不共享**任何中间量（不 import quotes_0253 / build_candidate）：
所有引文都是本脚本自己在 docs[0].text 里 `find` 出来的。

判据（任一条失败即退出码非 0）：
  A. docs.json 文件 sha256 == 任务 sourceHash == 候选 sourceHash
  B. 切片口径：text[start:end] 以单元标题开头、长度与候选声明一致、切片 sha256 一致
  C. 逐条引文：text[qs:qe] == quote 逐字成立；sourceHash 等于文件哈希；
     且该 quote 落在本单元区间内
  D. 分区齐备（任务提示词要求的 6 个顶层键都在）
  E. 五元组纪律：每栏自带 quotes；**同一句不得同时作为同一条任务多栏的依据**；
     null 栏必须有对应的 <栏名>Note
  F. worldSettings 三区分：place 必须有 placeState；item 必须有非空 itemStates；
     rule 必须有 institution（取值域内）
  G. 引用总数统计（用于提交记录）
"""
import hashlib
import json
import os
import re
import sys

ROOT = "/Users/carmen/Desktop/星系"
TASK = ROOT + "/loop/state/runs/task-read_dafeng_L1_0253.json"
DOCS = ROOT + "/data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT + "/loop/state/out/read_dafeng_L1_0253.candidate.json"

problems = []
notes = []


def fail(msg):
    problems.append(msg)


# ── A. 文件哈希 ────────────────────────────────────────────────────────
raw = open(DOCS, "rb").read()
file_sha = hashlib.sha256(raw).hexdigest()
task = json.load(open(TASK, encoding="utf-8"))
cand = json.load(open(CAND, encoding="utf-8"))
text = json.loads(raw.decode("utf-8"))[0]["text"]
S, E = task["sourceRange"]
slice_txt = text[S:E]
slice_sha = hashlib.sha256(slice_txt.encode("utf-8")).hexdigest()

if file_sha != task["sourceHash"]:
    fail("A1 文件哈希 != 任务 sourceHash")
if cand.get("sourceHash") != file_sha:
    fail("A2 候选 sourceHash != 文件哈希")
if [S, E] != cand.get("sourceRange"):
    fail("A3 候选 sourceRange != 任务 sourceRange")
if cand.get("sliceSha256") != slice_sha:
    fail("A4 候选 sliceSha256 != 实测切片哈希")
if cand.get("sliceCodepoints") != len(slice_txt):
    fail("A5 候选 sliceCodepoints != 实测切片长度")
notes.append("A 通过：文件 sha256=%s…；切片 [%d,%d) len=%d sha256=%s…"
             % (file_sha[:16], S, E, len(slice_txt), slice_sha[:16]))

# ── B. 切片口径自检 ────────────────────────────────────────────────────
head = task["unitHead"]
if not slice_txt.startswith(head):
    fail("B1 切片不以单元标题开头：%r" % slice_txt[:30])
else:
    notes.append("B 通过：text[%d:%d] 以 %r 开头" % (S, E, head))

# ── C. 逐条引文 ────────────────────────────────────────────────────────
refs = []          # (路径, quoteRef)
def walk(node, path):
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            refs.append((path, node))
        for k, v in node.items():
            walk(v, path + "." + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + "[%d]" % i)

walk(cand, "cand")

seen_pair = {}
for path, r in refs:
    qs, qe, qq_ = r.get("start"), r.get("end"), r.get("quote")
    if not isinstance(qs, int) or not isinstance(qe, int):
        fail("C0 %s start/end 非整数" % path)
        continue
    if text[qs:qe] != qq_:
        fail("C1 %s 逐字不成立 text[%d:%d]=%r != %r"
             % (path, qs, qe, text[qs:qe][:40], qq_[:40]))
        continue
    if r.get("sourceHash") != file_sha:
        fail("C2 %s sourceHash 不等于文件哈希" % path)
    if not (S <= qs and qe <= E):
        fail("C3 %s 引文越出本单元区间 [%d,%d]" % (path, qs, qe))
    # 区间内唯一命中
    hits, pos = 0, slice_txt.find(qq_)
    while pos >= 0:
        hits += 1
        pos = slice_txt.find(qq_, pos + 1)
    if hits != 1:
        fail("C4 %s 引文在区间内命中 %d 次（需唯一）" % (path, hits))
    key = (qs, qe)
    seen_pair.setdefault(key, []).append(path)

notes.append("C 通过：%d 处 quoteRef 全部逐字回读成立、哈希一致、区间内唯一命中"
             % len(refs))

# ── D. 分区齐备 ────────────────────────────────────────────────────────
want = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
missing = [k for k in want if k not in cand]
if missing:
    fail("D1 缺分区：%s" % missing)
else:
    notes.append("D 通过：6 个顶层分区齐备（%s）"
                 % ", ".join("%s=%d" % (k, len(cand[k])) for k in want))

# ── E. 五元组纪律 ──────────────────────────────────────────────────────
FIELDS = ["objective", "obstacle", "action", "result", "cost"]
shared_total = 0
for i, t in enumerate(cand.get("tasks", [])):
    spans = {}
    for f in FIELDS:
        v = t.get(f)
        note_key = f + "Note"
        if v is None:
            if not t.get(note_key):
                fail("E1 tasks[%d].%s 是 null 但缺 %s（未标注的未知）" % (i, f, note_key))
            continue
        if not isinstance(v, dict) or not v.get("quotes"):
            fail("E2 tasks[%d].%s 缺 quotes（每栏必须自带原文依据）" % (i, f))
            continue
        spans[f] = {(x["start"], x["end"]) for x in v["quotes"]}
    # 同一句不得同时作为多栏依据
    for a in range(len(FIELDS)):
        for b in range(a + 1, len(FIELDS)):
            fa, fb = FIELDS[a], FIELDS[b]
            if fa in spans and fb in spans:
                inter = spans[fa] & spans[fb]
                if inter:
                    shared_total += len(inter)
                    fail("E3 tasks[%d] 的 %s 与 %s 共用同一句引文 %s"
                         % (i, fa, fb, sorted(inter)))
if shared_total == 0:
    notes.append("E 通过：%d 条任务的五栏各自引证，无任何一栏共用同一句原文"
                 % len(cand.get("tasks", [])))

# ── F. worldSettings 三区分 ────────────────────────────────────────────
PLACE_OK = {"arrived", "mentioned"}
INST_OK = {"declared", "executed", "misunderstood"}
ITEM_OK = {"hold", "transfer", "use", "lose"}
kinds = {"rule": 0, "place": 0, "item": 0}
for i, w in enumerate(cand.get("worldSettings", [])):
    k = w.get("kind")
    if k not in kinds:
        fail("F1 worldSettings[%d] kind 非法：%r" % (i, k))
        continue
    kinds[k] += 1
    if k == "place" and w.get("placeState") not in PLACE_OK:
        fail("F2 worldSettings[%d] place 缺 placeState 或取值非法：%r" % (i, w.get("placeState")))
    if k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or not set(st) <= ITEM_OK:
            fail("F3 worldSettings[%d] item 的 itemStates 非法：%r" % (i, st))
    if k == "rule" and w.get("institution") not in INST_OK:
        fail("F4 worldSettings[%d] rule 缺 institution 或取值非法：%r" % (i, w.get("institution")))
notes.append("F 通过：worldSettings %d 条，rule=%d place=%d item=%d，"
             "三区分全部写进字段" % (len(cand.get("worldSettings", [])),
                                     kinds["rule"], kinds["place"], kinds["item"]))

# ── G. themeReadings 三件齐 ────────────────────────────────────────────
for i, th in enumerate(cand.get("themeReadings", [])):
    for key in ("perspective", "support", "counter"):
        if not th.get(key):
            fail("G1 themeReadings[%d] 缺 %s" % (i, key))
if len(cand.get("themeReadings", [])) > 2:
    fail("G2 themeReadings 超过 2 条（提示词上限）")
notes.append("G 通过：themeReadings %d 条，各含 perspective/support/counter"
             % len(cand.get("themeReadings", [])))

# ── H. 不出现「semanticReview 完成」这类越界声明 ───────────────────────
blob = json.dumps(cand, ensure_ascii=False)
if re.search(r"semanticReview\s*[\"']?\s*[:=]\s*[\"']?(done|pass|完成)", blob):
    fail("H1 出现 semanticReview 已完成的声称（越界）")
else:
    notes.append("H 通过：未声称 semanticReview 完成")

# ── 输出 ───────────────────────────────────────────────────────────────
print("=== 独立验证报告（read:dafeng:L1:0253）===")
for n in notes:
    print("  " + n)
print("  引文总数（quoteRef） =", len(refs))
print("  区间内完全重复的 (start,end) 对数 =",
      sum(1 for k, v in seen_pair.items() if len(v) > 1))
if problems:
    print("\n失败 %d 条：" % len(problems))
    for p in problems:
        print("  [FAIL] " + p)
    sys.exit(1)
print("\n全部判据通过（A–H）。")
sys.exit(0)
