# -*- coding: utf-8 -*-
"""独立审计：**不 import 生成侧任何模块**，只读 docs.json + 产物 JSON，重新复算一遍。

为什么单独写：生成脚本自己检查自己，结构上查不出「我以为我展开了其实没展开」这类问题
（本轮实测就出过一次：36 个条目只写了引文键名，H3–H5 遍历不到它们，产物里那一片依据
是不可核验的）。审计脚本按**产物字节**独立复算，与生成侧零共享代码。

判据：
  A1  docs.json sha256 == 任务 sourceHash；切片以单元标题开头
  A2  穷举产物里每个 {quote,start,end,sourceHash}：text[start:end]==quote、find 首次命中==start、
      落在本单元区间内、sourceHash == 整文件哈希
  A3  任何只写 keys/quoteKeys 却没有 quotes 的条目 == 0（依据必须可核验）
  A4  五栏不得共用同一句原文（字面量级）
  A5  每个 null 栏位必须有同名 <栏位>Note
  A6  散文字段「」内联片段必须逐字命中本单元切片
  A7  worldSettings 判别字段合法（place/rule/item）
  A8  foreshadows：resolved 有 payoff，unresolved 有 payoffNote
  A9  coverage 数字可从产物复算
"""
import hashlib
import json
import re
import sys
from pathlib import Path


def _root(start):
    for p in [start] + list(start.parents):
        if (p / "data" / "cache").is_dir() and (p / "loop" / "bin" / "loop.py").is_file():
            return p
    raise SystemExit("找不到仓库根")


ROOT = _root(Path(__file__).resolve().parent)
DOCS = ROOT / "data" / "cache" / "1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop" / "state" / "runs" / "task-read_dafeng_L0_0216.json"
CAND = ROOT / "loop" / "state" / "out" / "read_dafeng_L0_0216.candidate.json"

fails = []


def f(code, msg):
    fails.append("%s %s" % (code, msg))
    print("[FAIL] %s %s" % (code, msg))


raw = DOCS.read_bytes()
sha = hashlib.sha256(raw).hexdigest()
TEXT = json.loads(raw)[0]["text"]
task = json.loads(TASK.read_text(encoding="utf-8"))
START, END = task["sourceRange"]
SLICE = TEXT[START:END]
cand = json.loads(CAND.read_text(encoding="utf-8"))

# ── A1 ─────────────────────────────────────────────────────────────────────
if sha != task["sourceHash"]:
    f("A1", "docs sha256 != 任务 sourceHash")
if not SLICE.startswith(task["unitHead"]):
    f("A1", "切片不以单元标题开头：%r" % SLICE[:20])
if cand.get("sourceHash") != sha:
    f("A1", "产物 sourceHash != 实测")
if cand.get("sourceRange") != [START, END]:
    f("A1", "产物 sourceRange != 任务")

# ── A2/A3 ──────────────────────────────────────────────────────────────────
refs, keyonly = [], []


def walk(o, path):
    if isinstance(o, dict):
        if {"quote", "start", "end", "sourceHash"} <= set(o):
            refs.append((path, o))
        if ("keys" in o or "quoteKeys" in o) and "quotes" not in o:
            keyonly.append(path)
        for k, v in o.items():
            walk(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i))


walk(cand, "$")
for path, r in refs:
    s, e, q = r.get("start"), r.get("end"), r.get("quote")
    if not isinstance(s, int) or not isinstance(e, int):
        f("A2", "%s 缺 start/end" % path)
        continue
    if TEXT[s:e] != q:
        f("A2", "%s text[start:end] != quote" % path)
    # 口径：偏移必须是**本单元切片内**的定位，不要求等于全书 find 的首次命中
    # （短句在全书里会先于本单元出现，如『不行。』全书 51 次）。
    if SLICE.find(q) < 0:
        f("A2", "%s 引文在切片内找不到" % path)
    elif SLICE.find(q) != s - START:
        f("A2", "%s 偏移不是切片内首次命中（%d vs %d）" % (path, s, START + SLICE.find(q)))
    if SLICE.count(q) != 1:
        f("A2", "%s 引文在切片内出现 %d 次（非唯一）" % (path, SLICE.count(q)))
    if not (START <= s and e <= END):
        f("A2", "%s 越出单元区间" % path)
    if r.get("sourceHash") != sha:
        f("A2", "%s sourceHash 不是整文件哈希" % path)
if keyonly:
    f("A3", "%d 个条目只写了引文键却没有展开 quotes：%s" % (len(keyonly), keyonly[:5]))

# ── A2b 跨分区复用/全书重复清单的偏移也必须落在区间内 ─────────────────────
for sec in ("crossSectionQuoteReuse",):
    for row in cand.get(sec) or []:
        s, e = row.get("start"), row.get("end")
        if not (isinstance(s, int) and isinstance(e, int) and START <= s and e <= END):
            f("A2b", "%s 偏移越界：%r start=%r" % (sec, row.get("quote", "")[:20], s))
        elif TEXT[s:e] != row.get("quote"):
            f("A2b", "%s 偏移与引文不符：%r" % (sec, row.get("quote", "")[:20]))
for row in (cand.get("bookLevelDuplicateQuotes") or {}).get("items") or []:
    s, e = row.get("start"), row.get("end")
    if not (isinstance(s, int) and isinstance(e, int) and START <= s and e <= END):
        f("A2b", "bookLevelDuplicateQuotes 偏移越界：%r" % row.get("quote", "")[:20])

# ── A4 五栏不得共用同一句 ──────────────────────────────────────────────────
SLOTS = ["objective", "obstacle", "action", "result", "cost"]
for t in cand["tasks"]:
    seen = {}
    for s in SLOTS:
        v = t.get(s)
        if not v:
            continue
        for qq in v.get("quotes") or []:
            if qq["quote"] in seen:
                f("A4", "%s 的 %s 与 %s 共用同一句原文" % (t["id"], s, seen[qq["quote"]]))
            seen[qq["quote"]] = s

# ── A5 null 必须带 Note ───────────────────────────────────────────────────
for t in cand["tasks"]:
    for s in SLOTS:
        if t.get(s) is None and not t.get(s + "Note"):
            f("A5", "%s.%s 是 null 但缺 %sNote" % (t["id"], s, s))

# ── A6 内联「」必须逐字命中 ────────────────────────────────────────────────
INLINE = re.compile(r"「([^」]*)」")
inline_n = [0]


def check_inline(o, path):
    if isinstance(o, dict):
        for k, v in o.items():
            check_inline(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            check_inline(v, "%s[%d]" % (path, i))
    elif isinstance(o, str):
        for m in INLINE.finditer(o):
            frag = m.group(1)
            if frag:
                inline_n[0] += 1
                if frag not in SLICE:
                    f("A6", "%s 内联引用找不到：%r" % (path, frag[:40]))


check_inline(cand, "$")

# ── A7 worldSettings ──────────────────────────────────────────────────────
for w in cand["worldSettings"]:
    k = w.get("kind")
    if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        f("A7", "%s placeState 非法" % w["id"])
    if k == "item":
        if not isinstance(w.get("itemStates"), list) or any(
                x not in ("hold", "transfer", "use", "lose") for x in w["itemStates"]):
            f("A7", "%s itemStates 非法" % w["id"])
    if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        f("A7", "%s institution 非法" % w["id"])

# ── A8 foreshadows ────────────────────────────────────────────────────────
for fs in cand["foreshadows"]:
    if fs.get("status") == "resolved" and not fs.get("payoff"):
        f("A8", "%s resolved 但没有 payoff" % fs["id"])
    if fs.get("status") == "unresolved" and not fs.get("payoffNote"):
        f("A8", "%s unresolved 但没有 payoffNote" % fs["id"])

# ── A9 coverage 复算 ──────────────────────────────────────────────────────
lits = []


def collect(o):
    if isinstance(o, dict):
        if isinstance(o.get("quote"), str):
            lits.append(o["quote"])
        for v in o.values():
            collect(v)
    elif isinstance(o, list):
        for v in o:
            collect(v)


collect(cand)
# 段号口径：引文起始偏移**落在**哪一段区间内（包含判断）。
# 审计脚本**故意**不复制生成侧早先那条「数前面有几个非空段」的公式 ——
# 复制同一个公式的审计等于没有审计（实测那条公式有 off-by-one，
# 会把 13 个已引用段落误报成零覆盖）。这里按段落的 [起,止) 区间重新判定。
para_spans = []
_off = 0
for _line in SLICE.split("\n"):
    if _line.strip():
        para_spans.append((_off, _off + len(_line), _line))
    _off += len(_line) + 1


def para_of(off):
    for i, (a, b, _t) in enumerate(para_spans, 1):
        if a <= off < b:
            return i
    return None


covered = set()
for q in lits:
    st = SLICE.find(q)
    while st >= 0:
        n = para_of(st)
        if n is not None:
            covered.add(n)
        st = SLICE.find(q, st + 1)
para_total = len(para_spans)
cov = cand.get("coverage") or {}
if cov.get("nonEmptyParagraphs") != para_total:
    f("A9", "coverage.nonEmptyParagraphs=%r != 复算 %d" % (cov.get("nonEmptyParagraphs"), para_total))
if cov.get("paragraphsTouchedByQuotes") != len(covered):
    f("A9", "coverage.paragraphsTouchedByQuotes=%r != 复算 %d"
      % (cov.get("paragraphsTouchedByQuotes"), len(covered)))
if cov.get("zeroCoverageParagraphs") != para_total - len(covered):
    f("A9", "coverage.zeroCoverageParagraphs 与复算不符")

# ── A10 零覆盖清单必须**真的**没被引用（防 off-by-one 这类假清单）──────────
listed = {it["para"] for it in (cov.get("zeroCoverageList") or []) if isinstance(it, dict)}
false_zero = sorted(listed & covered)
if false_zero:
    f("A10", "零覆盖清单里有 %d 段其实被引用了：%s" % (len(false_zero), false_zero))
missing_zero = sorted(set(range(1, para_total + 1)) - covered - listed)
if missing_zero:
    f("A10", "有 %d 段既没被引用又没进零覆盖清单：%s" % (len(missing_zero), missing_zero))
for it in (cov.get("zeroCoverageList") or []):
    n = it.get("para")
    if not isinstance(n, int) or not (1 <= n <= para_total):
        f("A10", "零覆盖清单段号越界：%r" % (n,))
    elif not para_spans[n - 1][2].startswith(it.get("text", "")[:20]):
        f("A10", "第 %s 段的摘要文字与切片不符" % n)

print()
print("审计：引用实例 %d 条 / 内联片段 %d 处 / 只写键名条目 %d 个"
      % (len(refs), inline_n[0], len(keyonly)))
print("审计：非空段 %d / 被引文触及 %d / 零覆盖 %d"
      % (para_total, len(covered), para_total - len(covered)))
if fails:
    print("\n审计不通过：%d 项" % len(fails))
    sys.exit(1)
print("审计通过：A1–A9 全成立（独立复算，未 import 生成侧模块）")
