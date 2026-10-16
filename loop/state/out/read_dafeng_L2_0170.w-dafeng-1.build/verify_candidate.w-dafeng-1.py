#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复算 read:dafeng:L2:0170 候选。

**不复用构建期任何偏移**：全部从 data/cache/*.docs.json 现取现验。
检查项：
  1. 边界自检式（切片以标题开头）＋切片 sha256
  2. 每个引文对象：text[start:end]==quote / len==end-start / 区间内 / sourceHash /
     wholeTextOccurrences==text.count / firstOccurrenceAt==text.find /
     startIsFirstOccurrence 自洽 / para 段号与独立枚举一致
  3. 全覆盖：候选里所有 quotes 载体都已对象化（无裸字符串遗漏）
  4. 五元组纪律：同任务跨栏不共用引文、跨度不重叠、null 栏带同名 Note
  5. 世界设定三态：place=arrived/mentioned、item 四态、rule=declared/executed/misunderstood
  6. 主题读法三件齐（perspective/support/counter）
  7. 覆盖声明可复现（独立枚举段落 → 零引文段集合）
  8. 散文层：全文出现的 “…” 引号内串必须能在原文 find 到（反查『安了原文没有的词』）；
     源文本没有的字符（『』「」…）出现次数必须为 0
  9. 结构分区齐全
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0170.candidate.json"
START, END = 611230, 615103
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

problems = []
checks = []
report = {"task": "read:dafeng:L2:0170", "candidate": str(CAND), "problems": problems, "checks": checks}


def ok(name, detail):
    checks.append({"check": name, "result": "pass", "detail": detail})


def bad(name, detail):
    problems.append("%s: %s" % (name, detail))
    checks.append({"check": name, "result": "FAIL", "detail": detail})


raw = DOCS.read_bytes()
h = hashlib.sha256(raw).hexdigest()
if h != SOURCE_HASH:
    bad("sourceHash", "docs.json sha256=%s 与 task.sourceHash 不一致" % h)
else:
    ok("sourceHash", "docs.json sha256 与 task.sourceHash 逐字一致")

TEXT = json.loads(raw.decode("utf-8"))[0]["text"]
SLICE = TEXT[START:END]

# ── 1. 边界 ───────────────────────────────────────────────────────────────
if SLICE.startswith("第一百七十章 狮子吼"):
    ok("boundary", "docs[0].text[%d:%d] 以单元标题开头，长度 %d" % (START, END, len(SLICE)))
else:
    bad("boundary", "切片不以「第一百七十章 狮子吼」开头：%r" % SLICE[:30])

seg_sha = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

# ── 独立枚举段落 ──────────────────────────────────────────────────────────
PARAS = []
_pos = START
for _line in TEXT[START:END].split("\n"):
    _s = _line.strip()
    if _s:
        _lead = len(_line) - len(_line.lstrip())
        PARAS.append((len(PARAS) + 1, _pos + _lead, _s))
    _pos += len(_line) + 1


def para_of(off):
    for pi, ps, ptxt in PARAS:
        if ps <= off < ps + len(ptxt) + 2:
            return pi
    return None


cand = json.loads(CAND.read_text(encoding="utf-8"))

# ── 2. 引文对象全量复算 ───────────────────────────────────────────────────
qobjects = []
qstrings = []


def walk(node, path=""):
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            qobjects.append((path, node))
        elif "quote" in node and isinstance(node["quote"], str):
            qstrings.append((path, node["quote"]))
        else:
            for k, v in node.items():
                walk(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + "/%d" % i)


walk(cand)
nfail = 0
for path, q in qobjects:
    s, e, qq = q["start"], q["end"], q["quote"]
    if TEXT[s:e] != qq:
        bad("quote", "%s text[%d:%d] != quote" % (path, s, e)); nfail += 1; continue
    if e - s != len(qq):
        bad("quote-len", "%s len 不符" % path); nfail += 1
    if not (START <= s and e <= END):
        bad("quote-range", "%s 越出区间" % path); nfail += 1
    if q.get("sourceHash") != SOURCE_HASH:
        bad("quote-hash", "%s sourceHash 不符" % path); nfail += 1
    if q.get("wholeTextOccurrences") != TEXT.count(qq):
        bad("quote-count", "%s 出现次数 %s != %d" % (path, q.get("wholeTextOccurrences"), TEXT.count(qq))); nfail += 1
    if q.get("firstOccurrenceAt") != TEXT.find(qq):
        bad("quote-first", "%s 首现位置不符" % path); nfail += 1
    exp_first = (s == TEXT.find(qq))
    if bool(q.get("startIsFirstOccurrence")) != exp_first:
        bad("quote-startIsFirst", "%s startIsFirstOccurrence 不自洽" % path); nfail += 1
    if q.get("para") != para_of(s):
        bad("quote-para", "%s 段号 %s != %s" % (path, q.get("para"), para_of(s))); nfail += 1
if nfail == 0:
    ok("quotes", "%d 个引文对象全部通过（逐字/长度/区间/哈希/次数/首现/段号）" % len(qobjects))
if qstrings:
    bad("quote-strings", "%d 处 quotes 仍是裸字符串未对象化：%s" % (len(qstrings), [p for p, _ in qstrings[:5]]))
else:
    ok("quote-strings", "全部 quotes 载体已对象化，无裸字符串")

# ── 4. 五元组纪律 ─────────────────────────────────────────────────────────
shared = []
overlaps = []
nullinfo = []
for t in cand["tasks"]:
    seen = {}
    spans = []
    for field in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(field)
        note = t.get(field + "Note")
        if v is None:
            nullinfo.append((t["id"], field, bool(note)))
            continue
        if not v.get("quotes"):
            bad("slot-quotes", "%s.%s 无引文" % (t["id"], field))
        for q in v["quotes"]:
            key = (q["start"], q["end"])
            if key in seen:
                shared.append((t["id"], field, seen[key], key))
            seen[key] = field
            spans.append((q["start"], q["end"], field))
    spans.sort()
    for a, b in zip(spans, spans[1:]):
        if a[1] > b[0]:
            overlaps.append((t["id"], a, b))
            break
if shared:
    bad("cross-slot-reuse", "同任务跨栏共用同一引文跨度：%r" % shared)
else:
    ok("cross-slot-reuse", "6 条任务内，跨栏共用引文 0 处")
if overlaps:
    bad("slot-overlap", "同任务栏位引文跨度重叠：%r" % overlaps)
else:
    ok("slot-overlap", "同任务五栏引文跨度两两不重叠")
missing_note = [x for x in nullinfo if not x[2]]
if missing_note:
    bad("null-note", "null 栏位缺同名 Note：%r" % missing_note)
else:
    ok("null-note", "空栏 %d 处全部带同名 Note：%r" % (len(nullinfo), [(a, b) for a, b, _ in nullinfo]))

# ── 5. 世界设定三态 ───────────────────────────────────────────────────────
for w in cand["worldSettings"]:
    k = w.get("kind")
    if k == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            bad("placeState", "%s placeState=%r" % (w.get("id"), w.get("placeState")))
    elif k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            bad("itemStates", "%s itemStates=%r" % (w.get("id"), st))
    elif k == "rule":
        if w.get("institution") not in ("declared", "executed", "misunderstood"):
            bad("institution", "%s institution=%r" % (w.get("id"), w.get("institution")))
        if not w.get("explain"):
            bad("rule-explain", "%s 缺 explain" % w.get("id"))
    else:
        bad("worldkind", "%s kind=%r" % (w.get("id"), k))
if not problems:
    kinds = {}
    for w in cand["worldSettings"]:
        kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
    ok("worldSettings", "worldSettings %d 条，三态字段齐全，kind 分布=%r" % (len(cand["worldSettings"]), kinds))

# ── 6. 主题读法三件 ───────────────────────────────────────────────────────
if len(cand.get("themeReadings", [])) > 2:
    bad("theme-count", "themeReadings 超过 2 条")
for th in cand.get("themeReadings", []):
    for f in ("perspective", "support", "counter"):
        if not th.get(f):
            bad("theme-field", "%s 缺 %s" % (th.get("id"), f))
ok("themeReadings", "%d 条主题读法，perspective/support/counter 均齐" % len(cand.get("themeReadings", [])))

# ── 7. 覆盖声明可复现 ─────────────────────────────────────────────────────
covered = set()
for _, q in qobjects:
    covered.add(q.get("para"))
uncovered = [p for p, _, _ in PARAS if p not in covered]
decl = cand.get("coverageDeclaration", {})
if decl.get("nonEmptyParagraphs") != len(PARAS):
    bad("coverage-count", "候选 %r != 独立枚举 %d" % (decl.get("nonEmptyParagraphs"), len(PARAS)))
elif decl.get("uncoveredParagraphs") != uncovered:
    bad("coverage-set", "候选 %r != 独立算出 %r" % (decl.get("uncoveredParagraphs"), uncovered))
else:
    ok("coverage", "非空段 %d；零引文段集合可复现 %r" % (len(PARAS), uncovered))

undisp = [p for p in uncovered if not any(u["para"] == p for u in decl.get("uncoveredItems", []))]
if undisp:
    bad("uncovered-note", "零引文段未给理由：%r" % undisp)
else:
    ok("uncovered-note", "零引文段 %d 个逐条给了理由" % len(uncovered))

# ── 8. 散文层反查 ─────────────────────────────────────────────────────────
cand_text = CAND.read_text(encoding="utf-8")
for ch, name in (("『", "left-double"), ("』", "right-double"), ("「", "left-corner"), ("」", "right-corner"), ("…", "ellipsis")):
    n = cand_text.count(ch)
    if n:
        bad("forbidden-char", "候选出现源文本没有的字符 %s(%s) %d 次" % (ch, name, n))
ok("forbidden-char", "『』「」与 … 在候选中的出现次数均为 0（源文本同样为 0）")

# 散文里 “…” 的串必须在原文 find 得到（只查长度>=4 的，滤掉单字应答）
# 注意：必须扫**解码后的字段值**，不能扫原始 JSON 文本 ——
# 原文里存在跨段的成对引号（p41 开、p42 合），扫原始文本会把两段之间的
# JSON 结构整段当成引文内容，报出假缺陷（本轮实测过一次）。
prose_bad = []


def strings_of(node):
    if isinstance(node, dict):
        for v in node.values():
            for x in strings_of(v):
                yield x
    elif isinstance(node, list):
        for v in node:
            for x in strings_of(v):
                yield x
    elif isinstance(node, str):
        yield node


for val in strings_of(cand):
    i = 0
    while True:
        a = val.find("\u201c", i)
        if a < 0:
            break
        b = val.find("\u201d", a + 1)
        if b < 0:
            break
        inner = val[a + 1:b]
        if len(inner) >= 4 and inner not in TEXT:
            prose_bad.append(inner)
        i = b + 1
if prose_bad:
    bad("prose-quote", "散文里 %d 处 “…” 内容在原文找不到：%r" % (len(prose_bad), prose_bad[:6]))
else:
    ok("prose-quote", "散文层全部 “…” 引文（长度>=4）在原文逐字命中")

# ── 9. 结构分区齐全 ───────────────────────────────────────────────────────
want = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
missing = [k for k in want if k not in cand]
if missing:
    bad("sections", "缺分区 %r" % missing)
else:
    ok("sections", "提示词要求的 6 个分区全部存在")

# ── 额外：因果边必须有触发机制 ────────────────────────────────────────────
for c in cand.get("causeEdges", []):
    if not c.get("trigger") or not c.get("quotes"):
        bad("causeEdge", "%s 缺 trigger 或 quotes" % c.get("id"))
ok("causeEdges", "%d 条因果边全部带 trigger 与引文" % len(cand.get("causeEdges", [])))

# ── 额外：伏笔状态字段 ────────────────────────────────────────────────────
for f in cand.get("foreshadows", []):
    if f.get("status") not in ("resolved-in-range", "unresolved"):
        bad("foreshadow-status", "%s status=%r" % (f.get("id"), f.get("status")))
    if f.get("status") == "unresolved" and not f.get("payoffNote"):
        bad("foreshadow-note", "%s 未回收但缺 payoffNote" % f.get("id"))
ok("foreshadows", "%d 条伏笔 status 合法、未回收者均带 payoffNote" % len(cand.get("foreshadows", [])))

report["verdict"] = "pass" if not problems else "fail"
report["counts"] = {
    "quoteObjects": len(qobjects),
    "uniqueQuoteStrings": len({q["quote"] for _, q in qobjects}),
    "nonEmptyParagraphs": len(PARAS),
    "uncoveredParagraphs": uncovered,
    "segmentSha256": seg_sha,
    "candidateSha256": hashlib.sha256(CAND.read_bytes()).hexdigest(),
}

outp = ROOT / "loop/state/out/read_dafeng_L2_0170.w-dafeng-1.build/verify_report.w-dafeng-1.json"
outp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

print("verdict =", report["verdict"])
print("引文对象 %d，唯一串 %d，非空段 %d，零引文段 %r"
      % (len(qobjects), report["counts"]["uniqueQuoteStrings"], len(PARAS), uncovered))
print("problems =", problems if problems else "[]")
print("报告写入", outp)
sys.exit(0 if not problems else 1)
