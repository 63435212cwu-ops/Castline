# -*- coding: utf-8 -*-
"""独立审计 read:dafeng:L1:0229 候选。

与生成侧完全独立：**不 import content_core**，也不复用构建脚本的任何函数。
输入只有两个：产物 JSON + 原文 docs.json。退出码即判据（0=全过）。

用法：python3 -B -s loop/state/out/read_dafeng_L1_0229.w-xiyou-1.build/audit_candidate.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
CAND = ROOT / "loop/state/out/read_dafeng_L1_0229.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"

EXPECT_SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 879573, 889513

fails = []
checks = []


def ck(name, ok, detail=""):
    checks.append((name, ok, detail))
    if not ok:
        fails.append("%s %s" % (name, detail))


raw = DOCS.read_bytes()
src_sha = hashlib.sha256(raw).hexdigest()
text = json.loads(raw.decode("utf-8"))[0]["text"]
slice_text = text[START:END]
cand = json.loads(CAND.read_text(encoding="utf-8"))

# ── A1 来源哈希（从产物自己声明的路径重算，不信产物里的值）────────
ck("A1 sourceHash", src_sha == EXPECT_SOURCE_HASH, "实测 %s" % src_sha[:16])
ck("A1b 产物声明一致", cand.get("sourceHash") == EXPECT_SOURCE_HASH)

# ── A2 切片口径 ────────────────────────────────────────────────
ck("A2 切片以标题开头", slice_text.startswith(cand["unitHead"]), repr(slice_text[:20]))
ck("A2b sourceRange 一致", list(cand["sourceRange"]) == [START, END])
ck("A2c 切片长度自报可复算", cand.get("sliceCodepoints") == len(slice_text))
ck("A2d 切片哈希可复算",
   cand.get("sliceSha256") == hashlib.sha256(slice_text.encode("utf-8")).hexdigest())

# ── 遍历产物，收集所有 (quote, start, end) 引用 ────────────────
refs = []          # (path, quote, start, end, declared_hash)
quote_string_fields = []   # (path, raw string) —— 用来核对「该带偏移的引文」


def walk(o, path=""):
    if isinstance(o, dict):
        if "quote" in o and isinstance(o["quote"], str):
            refs.append((path, o["quote"], o.get("start"), o.get("end"), o.get("sourceHash")))
        for k, v in o.items():
            walk(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i))


walk(cand)

# ── A3 每条引用：全文偏移取回必须逐字相等 ──────────────────────
bad = [(p, q, s, e) for (p, q, s, e, _h) in refs
       if not isinstance(s, int) or not isinstance(e, int) or text[s:e] != q]
ck("A3 全文偏移取回逐字相等", not bad, "违例 %d 条：%r" % (len(bad), bad[:2]))

# ── A4 引用必须落在本单元区间内 ────────────────────────────────
out_of_range = [(p, q, s, e) for (p, q, s, e, _h) in refs
                if isinstance(s, int) and (s < START or e > END)]
ck("A4 引用落在 [%d,%d) 内" % (START, END), not out_of_range,
   "越界 %d 条：%r" % (len(out_of_range), out_of_range[:2]))

# ── A5 每条引用声明的 sourceHash 必须是整文件 sha256 ────────────
wrong_hash = [p for (p, q, s, e, h) in refs if h != EXPECT_SOURCE_HASH]
ck("A5 引用的 sourceHash 统一", not wrong_hash, "违例 %d 条" % len(wrong_hash))

# ── A6 引文可 find（与偏移无关的独立核对）───────────────────────
not_found = [q for (_p, q, _s, _e, _h) in refs if q not in text]
ck("A6 引文可在原文 find", not not_found, "找不到 %d 条：%r" % (len(not_found), not_found[:2]))

# ── A7 同一任务五栏不得共用同一句 ──────────────────────────────
SLOTS = ["objective", "obstacle", "action", "result", "cost"]
shared = []
for t in cand.get("tasks", []):
    used = {}
    for s in SLOTS:
        v = t.get(s)
        if not isinstance(v, dict):
            continue
        for q in {r["quote"] for r in (v.get("quotes") or [])}:
            if q in used:
                shared.append((t["id"], used[q], s, q[:24]))
            used[q] = s
ck("A7 同任务五栏不共用引文", not shared, "%r" % (shared[:3],))

# ── A8 null 栏位必须带同名 Note 写明理由 ───────────────────────
missing_note = []
for t in cand.get("tasks", []):
    for s in SLOTS:
        if t.get(s) is None and not (t.get(s + "Note") or "").strip():
            missing_note.append("%s.%s" % (t["id"], s))
ck("A8 null 栏位带 Note", not missing_note, "%r" % (missing_note,))


def count_null_slots(c):
    return sum(1 for t in c.get("tasks", []) for s in SLOTS if t.get(s) is None)


# ── A9 自述计数可复算 ──────────────────────────────────────────
tn = cand.get("tasksNote") or ""
m = re.search(r"(\d+) 个裸 null", tn)
ck("A9 tasksNote 的 null 数可复算",
   m and int(m.group(1)) == count_null_slots(cand),
   "自述 %s 实际 %d" % (m.group(1) if m else None, count_null_slots(cand)))
m2 = re.search(r"(\d+) 条任务", tn)
ck("A9b tasksNote 的任务数可复算",
   m2 and int(m2.group(1)) == len(cand.get("tasks", [])), tn[:40])

# ── A10 place 必须有 placeState；取值合法 ──────────────────────
bad_place = []
for s in cand.get("worldSettings", []):
    if s.get("kind") == "place" and s.get("placeState") not in ("arrived", "mentioned"):
        bad_place.append(s.get("id"))
ck("A10 place.placeState 合法", not bad_place, "%r" % (bad_place,))

# ── A11 item 必须有 itemStates（四态多选）；无 item 时该为 0 条 ──
bad_item = []
for s in cand.get("worldSettings", []):
    if s.get("kind") == "item":
        st = s.get("itemStates") or []
        if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            bad_item.append(s.get("id"))
ck("A11 item.itemStates 合法", not bad_item, "%r" % (bad_item,))

# ── A12 rule 必须有 institution；取值合法 ──────────────────────
bad_rule = []
for s in cand.get("worldSettings", []):
    if s.get("kind") == "rule":
        if s.get("institution") not in ("declared", "executed", "misunderstood"):
            bad_rule.append(s.get("id"))
ck("A12 rule.institution 合法", not bad_rule, "%r" % (bad_rule,))

# ── A13 unresolved 伏笔必须带 payoffNote；resolved 必须有回收 ──
bad_f = []
for f in cand.get("foreshadows", []):
    if f.get("status") == "unresolved" and not (f.get("payoffNote") or "").strip():
        bad_f.append(f.get("id"))
    if f.get("status") == "resolved" and not f.get("payoff"):
        bad_f.append(f.get("id"))
ck("A13 伏笔回收状态自洽", not bad_f, "%r" % (bad_f,))

# ── A14 semanticReview 不得写成完成 ────────────────────────────
sr = (cand.get("semanticReview") or {}).get("status")
ck("A14 semanticReview 未完成", sr == "not_performed", "实际 %r" % sr)

# ── A15 cost 不得含「待核/待验证」或把纸面规定当结果 ────────────
bad_cost = []
for t in cand.get("tasks", []):
    c = t.get("cost")
    if isinstance(c, dict):
        blob = json.dumps(c, ensure_ascii=False)
        if any(w in blob for w in ("待验证", "待核", "法律", "规定", "禁令")):
            bad_cost.append(t["id"])
ck("A15 cost 不含禁用表述", not bad_cost, "%r" % (bad_cost,))

# ── A16 每条断言 basis 合法 ────────────────────────────────────
LEGAL = {"explicit", "inferred", "derived", "unverified"}
bad_basis = []


def check_basis(o, path=""):
    if isinstance(o, dict):
        if "basis" in o and o["basis"] not in LEGAL:
            bad_basis.append((path, o["basis"]))
        for k, v in o.items():
            check_basis(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            check_basis(v, "%s[%d]" % (path, i))


check_basis(cand)
ck("A16 basis 取值合法", not bad_basis, "%r" % (bad_basis[:3],))

# ── A17 覆盖率自报可复算（独立重算，不用产物里的段落清单）───────
paras, pos = [], START
for para in slice_text.split("\n"):
    if para.strip():
        paras.append((pos, pos + len(para)))
    pos += len(para) + 1
covered = set()
for (_p, q, s, e, _h) in refs:
    if not isinstance(s, int):
        continue
    for i, (ps, pe) in enumerate(paras):
        if s >= ps and e <= pe:
            covered.add(i)
            break
cv = cand.get("coverage") or {}
ck("A17 覆盖率自报可复算",
   cv.get("nonEmptyParagraphs") == len(paras) and cv.get("paragraphsTouchedByQuotes") == len(covered),
   "自报 %s/%s 实测 %d/%d" % (cv.get("nonEmptyParagraphs"), cv.get("paragraphsTouchedByQuotes"),
                              len(covered), len(paras)))
ck("A17b 零覆盖清单与自报数一致",
   len(cv.get("zeroCoverageList") or []) == min(40, len(paras) - len(covered)),
   "清单 %d 条" % len(cv.get("zeroCoverageList") or []))

# ── A18 反向：产物里的「」片段必须是逐字原文 ────────────────────
brk = []


def scan(o, path=""):
    if isinstance(o, str):
        for frag in re.findall("\u300c([^\u300c\u300d]*)\u300d", o):
            if frag and frag not in text:
                brk.append((path, frag))
        for frag in re.findall("\u300e([^\u300e\u300f]*)\u300f", o):
            if frag and frag in text:
                brk.append((path, frag + " (『』里其实是原文)"))
    elif isinstance(o, dict):
        for k, v in o.items():
            scan(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan(v, "%s[%d]" % (path, i))


scan(cand)
ck("A18 「」=原文且『』≠原文", not brk, "违例 %d：%r" % (len(brk), brk[:3]))

# ── 跨分区复用如实统计（不是失败项，是披露项）───────────────────
by_quote = {}
for (p, q, s, e, _h) in refs:
    top = p.split(".")[1] if "." in p else p
    by_quote.setdefault(q, set()).add(top)
reused = {q: sorted(v) for q, v in by_quote.items() if len(v) > 1}
disclosed = {d.get("quote") for d in (cand.get("crossSectionQuoteReuse") or [])}
undisclosed = {q: v for q, v in reused.items() if q not in disclosed}
ck("A19 跨分区复用已如实披露", not undisclosed,
   "未披露 %d 条：%r" % (len(undisclosed), list(undisclosed.items())[:2]))

# ── 输出 ───────────────────────────────────────────────────────
n_inst = len(refs)
n_uniq = len({q for (_p, q, _s, _e, _h) in refs})
print("审计对象：%s" % CAND)
print("产物 sha256：%s" % hashlib.sha256(CAND.read_bytes()).hexdigest())
print("引文实例 %d 条 / 不同串 %d 个 / 覆盖 %d/%d 个非空段落" % (n_inst, n_uniq, len(covered), len(paras)))
print("跨分区复用 %d 条（已披露）" % len(reused))
print("-" * 62)
for name, ok, detail in checks:
    print("  %s %s%s" % ("✓" if ok else "✗", name, ("  ← " + detail) if (detail and not ok) else ""))
print("-" * 62)
if fails:
    print("审计不通过：%d 条判据（A1–A19）" % len(fails))
    sys.exit(1)
print("审计通过：A1–A19 全部成立")
sys.exit(0)
