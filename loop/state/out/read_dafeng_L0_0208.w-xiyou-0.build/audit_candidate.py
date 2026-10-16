#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计 read_dafeng_L0_0208.candidate.json（只读，不 import content_core）。

与生成侧代码**不共享**任何定位逻辑：这里从产物本身出发，
用 docs[0].text 重新定位每条引文并复算判据。退出码即结论（0 = 全部成立）。

A1  产物 task/agent/role/unitHead 与任务定义一致
A2  sourceRange 与任务一致；切片以单元标题开头、长度与 sourceRange 相符
A3  sourceHash == 整个 docs.json 的 sha256；sliceSha256 可复算
A4  每一条引用对象都满足 text[start:end] == quote 且 sourceHash 正确
A5  每条引文的 start/end 落在 [start,end) 内（含边界检查）
A6  每条引文在本单元切片内唯一
A7  同一任务内五栏不得复用同一引文（红线：五栏共用一句）
A8  栏位 null ⇔ 有同名 <栏位>Note（两类都要查：null 无 Note、非 null 却有 Note）
A9  cost 栏不得含「待核/待验证/法律规定/禁令」
A10 semanticReview.status 不得为完成态
A11 六个顶层分区都存在且为数组
A12 place 有 placeState ∈ {arrived,mentioned}；item 有 itemStates ⊆ 四态；rule 有 institution
A13 所有 basis ∈ {explicit,inferred,derived,unverified}
A14 foreshadow: resolved 必须有 payoff；unresolved 必须有 payoffNote
A15 散文字段里「」内联引用必须逐字命中原文（『』为转述，不在此列）
A16 不得出现「结束即成功」型 result：result 文本里不得同时出现成功断言词与区间结束语
A17 actor 不得是原文里不存在的人物名（从产物自报的 actor 反查原文）
A18 coverage 的零覆盖清单与引文实际覆盖一致（不注水）
A19 crossSectionQuoteReuse 与产物内容一致（不隐藏复用）
"""
import hashlib
import json
import os
import re
import sys

ROOT = "/Users/carmen/Desktop/星系"
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0208.candidate.json")
TASK = os.path.join(ROOT, "loop/state/runs/task-read_dafeng_L0_0208.json")
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")

fails = []


def chk(cond, code, msg):
    if not cond:
        fails.append("%s: %s" % (code, msg))


cand = json.load(open(CAND, encoding="utf-8"))
task = json.load(open(TASK, encoding="utf-8"))
raw = open(DOCS, "rb").read()
TEXT = json.loads(raw.decode("utf-8"))[0]["text"]
S, E = task["sourceRange"]
SLICE = TEXT[S:E]
FILE_HASH = hashlib.sha256(raw).hexdigest()

# A1
chk(cand["task"] == task["id"], "A1", "task 不一致")
chk(cand["unitHead"] == task["unitHead"], "A1", "unitHead 不一致")
chk(cand["sourceRange"] == [S, E], "A2", "sourceRange 不一致")
chk(SLICE.startswith(task["unitHead"]), "A2", "切片不以标题开头")
chk(len(SLICE) == E - S, "A2", "切片长度不符")
# A3
chk(FILE_HASH == task["sourceHash"], "A3", "文件哈希与任务不符")
chk(hashlib.sha256(SLICE.encode()).hexdigest() == cand["sliceSha256"], "A3", "sliceSha256 不符")
chk(cand["sourceHash"] == FILE_HASH, "A3", "candidate.sourceHash 不符")

# ── 遍历所有引用对象 ─────────────────────────────────────────────────────
REFS = []


def walk(o, path=""):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            REFS.append((path, o))
            return
        for k, v in o.items():
            walk(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i))


walk(cand)
chk(len(REFS) > 0, "A4", "没有找到任何引用对象")

for path, r in REFS:
    q, a, b = r["quote"], r["start"], r["end"]
    chk(TEXT[a:b] == q, "A4", "%s text[start:end] != quote（%r）" % (path, q[:25]))
    chk(r.get("sourceHash") == FILE_HASH, "A4", "%s sourceHash 不符" % path)
    chk(S <= a and b <= E, "A5", "%s 引文越出单元区间 [%d,%d)：%d..%d" % (path, S, E, a, b))
    chk(SLICE.count(q) == 1, "A6", "%s 引文在切片内不唯一（%d 次）" % (path, SLICE.count(q)))

# ── A7 同任务五栏不复用 ──────────────────────────────────────────────────
FIELDS = ("objective", "obstacle", "action", "result", "cost")
for t in cand["tasks"]:
    seen = {}
    for f in FIELDS:
        v = t.get(f)
        if not v:
            continue
        for r in v.get("quotes", []):
            q = r["quote"]
            chk(q not in seen, "A7", "%s 的 %s 与 %s 共用引文 %r"
                % (t["id"], f, seen.get(q), q[:25]))
            seen[q] = f

# ── A8 null ⇔ Note ──────────────────────────────────────────────────────
for t in cand["tasks"]:
    for f in FIELDS:
        note = t.get(f + "Note")
        if t.get(f) is None:
            chk(bool(note and note.strip()), "A8", "%s.%s 为 null 但无 %sNote" % (t["id"], f, f))
        else:
            chk(not note, "A8", "%s.%s 非 null 却带 %sNote（口径混乱）" % (t["id"], f, f))
    # A9
    if t.get("cost"):
        blob = t["cost"]["text"] + "".join(r["quote"] for r in t["cost"]["quotes"])
        for kw in ("待核", "待验证", "法律规定", "禁令"):
            chk(kw not in blob, "A9", "%s.cost 含「%s」" % (t["id"], kw))

# ── A10 ─────────────────────────────────────────────────────────────────
chk(cand["semanticReview"]["status"] not in ("done", "complete", "performed"), "A10",
    "semanticReview 被标为完成")

# ── A11 ─────────────────────────────────────────────────────────────────
_missing = [k for k in ("tasks", "causeEdges", "states", "foreshadows",
                       "worldSettings", "themeReadings")
            if not isinstance(cand.get(k), list)]
for k in _missing:
    chk(False, "A11", "顶层分区 %s 缺失或非数组" % k)
if _missing:
    # 分区缺失时后续判据无从谈起：直接给结论，避免用 traceback 当判据
    for f in fails:
        print("FAIL " + f, file=sys.stderr)
    print("审计失败：缺分区 %s（后续判据跳过）" % _missing, file=sys.stderr)
    sys.exit(1)

# ── A12/A13/A14 ─────────────────────────────────────────────────────────
LEGAL_B = {"explicit", "inferred", "derived", "unverified"}
for w in cand["worldSettings"]:
    chk(w["basis"] in LEGAL_B, "A13", "%s.basis 非法" % w["id"])
    if w["kind"] == "rule":
        chk(w.get("institution") in {"declared", "executed", "misunderstood"}, "A12",
            "%s.institution 非法" % w["id"])
    elif w["kind"] == "place":
        chk(w.get("placeState") in {"arrived", "mentioned"}, "A12",
            "%s.placeState 非法" % w["id"])
    elif w["kind"] == "item":
        sts = w.get("itemStates") or []
        chk(sts and all(s in {"hold", "transfer", "use", "lose"} for s in sts), "A12",
            "%s.itemStates 非法：%r" % (w["id"], sts))
        sq = w.get("itemStateQuotes") or {}
        chk(all(s in sq for s in sts), "A12", "%s 缺逐态引文" % w["id"])
    else:
        chk(False, "A12", "%s.kind 非法：%r" % (w["id"], w["kind"]))

for coll in ("tasks", "causeEdges", "states", "foreshadows", "themeReadings"):
    for it in cand[coll]:
        if it.get("basis"):
            chk(it["basis"] in LEGAL_B, "A13", "%s.%s.basis 非法" % (coll, it["id"]))
for t in cand["tasks"]:
    for f in FIELDS:
        if t.get(f):
            chk(t[f]["basis"] in LEGAL_B, "A13", "%s.%s.basis 非法" % (t["id"], f))

for f in cand["foreshadows"]:
    if f["status"] == "resolved":
        chk(bool(f["payoff"]), "A14", "%s 标 resolved 但无 payoff" % f["id"])
    if f["status"] == "unresolved":
        chk(bool(f.get("payoffNote")), "A14", "%s 标 unresolved 但无 payoffNote" % f["id"])
    chk(bool(f["setup"]), "A14", "%s 无 setup，不构成伏笔" % f["id"])

# ── A15 内联「」必须逐字命中 ─────────────────────────────────────────────
INLINE = re.compile(r"「([^」]+)」")
inline_bad = []
def scan(o, path=""):
    if isinstance(o, dict):
        if "quote" in o and "start" in o:
            return
        for k, v in o.items():
            scan(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan(v, "%s[%d]" % (path, i))
    elif isinstance(o, str):
        for m in INLINE.finditer(o):
            f = m.group(1)
            if f not in TEXT:
                inline_bad.append((path, f))
scan(cand)
chk(not inline_bad, "A15", "内联「」引用未逐字命中：%s" % inline_bad[:3])

# ── A20 内部编号引用不得悬空（与构建侧 H19 呼应）─────────────────────────
_ids = set()
for sec in ("tasks", "causeEdges", "rejectedEdges", "states", "foreshadows",
            "notForeshadows", "worldSettings", "excludedSettings", "themeReadings",
            "unknowns", "rejectedTasks"):
    for it in cand.get(sec, []) or []:
        if isinstance(it, dict) and it.get("id"):
            _ids.add(it["id"])
_blob = json.dumps(cand, ensure_ascii=False)
_refs = set(re.findall(r"(?<![\w])((?:rt|th|t|e|r|s|f|n|w|x|i|u)\d+)(?![\w])", _blob))
_dangle = sorted(r for r in _refs
                 if r not in _ids and not any(i.startswith(r + "_") for i in _ids))
chk(not _dangle, "A20", "悬空的内部编号引用：%s" % _dangle)

# ── A21 语层披露必须是数据驱动且完整 ─────────────────────────────────────
# 判据：凡引文里含中文引号（“”）的**结构性引用**，都必须在 dispositionOfEach 里
# 出现（说明它是谁的话）。只报「披露几条」而不核对完整性 = 数字好看但无用。
_dispo = {d["quote"] for d in cand.get("speechLayerDisclosure", {}).get("dispositionOfEach", [])}
_quoted = {r["quote"] for _, r in REFS if ("“" in r["quote"] or "”" in r["quote"])}
_missing = sorted(_quoted - _dispo)
chk(not _missing, "A21", "含引号的语层引用未披露：%s" % [q[:18] for q in _missing][:3])
chk(cand.get("speechLayerDisclosure", {}).get("checkedCount") == len(_dispo), "A21",
    "speechLayerDisclosure.checkedCount 与实际条数不符")

# ── A16 结束≠成功 ───────────────────────────────────────────────────────
SUCCESS = ("成功", "达成", "得手", "办成了", "顺利")
for t in cand["tasks"]:
    if t.get("result"):
        txt = t["result"]["text"]
        for kw in SUCCESS:
            chk(kw not in txt, "A16", "%s.result 含成功断言「%s」" % (t["id"], kw))

# ── A17 actor 反查原文 ──────────────────────────────────────────────────
for t in cand["tasks"]:
    names = re.findall(r"[\u4e00-\u9fa5]{2,4}", t["actor"])
    hit = [n for n in names if n in SLICE]
    chk(bool(hit), "A17", "%s.actor 在原文里找不到任何片段：%r" % (t["id"], t["actor"]))

# ── A18 覆盖率不注水 ────────────────────────────────────────────────────
paras = []
off = S
for p in SLICE.split("\n"):
    if p.strip():
        paras.append((off, off + len(p)))
    off += len(p) + 1
spans = [(r["start"], r["end"]) for _, r in REFS]
touched = set()
for i, (a, b) in enumerate(paras):
    for x, y in spans:
        if x < b and y > a:
            touched.add(i)
            break
cov = cand["coverage"]
chk(cov["nonEmptyParagraphs"] == len(paras), "A18",
    "coverage.nonEmptyParagraphs 与实测不符：%d vs %d" % (cov["nonEmptyParagraphs"], len(paras)))
chk(cov["paragraphsTouchedByQuotes"] == len(touched), "A18",
    "coverage.paragraphsTouchedByQuotes 与实测不符：%d vs %d"
    % (cov["paragraphsTouchedByQuotes"], len(touched)))
chk(cov["zeroCoverageParagraphs"] == len(paras) - len(touched), "A18",
    "coverage.zeroCoverageParagraphs 与实测不符")
zero = [i for i in range(len(paras)) if i not in touched]
chk(cov["zeroCoverageList"] == zero[:40], "A18", "零覆盖清单与实测不符")

# ── A19 跨分区复用披露不隐藏 ────────────────────────────────────────────
# 判据是**同一引用对象（同 start/end）出现在多个分区**，不是字符串包含关系。
# 早先用 `q in blob` 判断，于是「赶在宵禁前离开驿站」被「赶在宵禁前离开驿站，
# 来到了黄伯街附近」包含而**误报**为未披露复用——子串包含不等于复用。
def _spans_in(sec):
    out = set()

    def w(o):
        if isinstance(o, dict):
            if "quote" in o and "start" in o:
                out.add((o["start"], o["end"]))
                return
            for v in o.values():
                w(v)
        elif isinstance(o, list):
            for v in o:
                w(v)
    w(sec)
    return out


sections = {sec: _spans_in(cand[sec])
            for sec in ("tasks", "causeEdges", "states", "foreshadows",
                        "worldSettings", "themeReadings")}
multi = set()
for key in {r["start"] for _, r in REFS}:
    n = sum(1 for s in sections.values() if any(a == key for a, _ in s))
    if n > 1:
        multi.add(key)
declared = {d["start"] for d in cand["crossSectionQuoteReuse"]}
chk(multi <= declared, "A19", "有跨分区复用未披露：%s"
    % [(TEXT[s:s + 20]) for s in sorted(multi - declared)][:3])
chk(declared <= {r["start"] for _, r in REFS}, "A19", "披露了不存在的引文")
for d in cand["crossSectionQuoteReuse"]:
    chk(TEXT[d["start"]:d["end"]] == d["quote"], "A19", "复用清单引文不符")
    chk(d.get("sourceHash") == FILE_HASH, "A19", "复用清单缺 sourceHash")

# ── 结论 ────────────────────────────────────────────────────────────────
if fails:
    for f in fails:
        print("FAIL " + f, file=sys.stderr)
    print("审计失败：%d 条" % len(fails), file=sys.stderr)
    sys.exit(1)

print("审计通过：A1–A21 全部成立")
print("  引用实例 %d 条 / 不同引文 %d 个" % (len(REFS), len({r['quote'] for _, r in REFS})))
print("  覆盖 %d/%d 非空段落；零覆盖 %d 段"
      % (len(touched), len(paras), len(paras) - len(touched)))
print("  跨分区复用披露 %d 条" % len(declared))
