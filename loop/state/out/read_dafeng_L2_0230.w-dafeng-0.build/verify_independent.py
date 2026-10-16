# -*- coding: utf-8 -*-
"""read:dafeng:L2:0230 —— **独立**重算（w-dafeng-0）。

与 build_candidate.py 的关系：**不 import 它、不复用它的任何中间量**。
本脚本从磁盘上的候选文件重新读起，源 docs.json 重新打开、哈希重算，
段落与句单元在本脚本内**另外切分一遍**，全部引文逐条重新 find。

它检查的 13 条判据：
  C01 源文件哈希 == 候选 source.sourceHash == 任务 sourceHash
  C02 docs[0].text[S:E] 以本单元标题开头；切片哈希与候选一致
  C03 候选 source.range == [S,E] 且与任务 sourceRange 一致
  C04 每条引文 text[start:end] == quote（逐字）
  C05 每条引文落在 [S,E) 内
  C06 每条引文的 sourceHash 全等
  C07 wholeTextOccurrences / occurrencesInRange 与现算相等
  C08 paraLabel 由本脚本独立切分的段索引重新判定
  C09 五元组五栏之间零共用（字符区间级 + 句单元级两套）
  C10 worldSettings 三套判别字段合法（kind/placeState/itemStates/institution 匹配）
  C11 null 栏必须有同名 Note
  C12 全文 『…』跨度必须是逐字子串（非逐字的必须已在 〔…〕里）
  C13 四个必需语义分区存在

用法：
  python3 -B -s verify_independent.py            # 正常核验
  python3 -B -s verify_independent.py --mutate   # 变异自检：把一条引文改坏一个字，
                                                 # C04/C12 必须转 FAIL（证明判据不是恒真）
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND = ROOT / "loop/state/out/read_dafeng_L2_0230.candidate.json"
TASKFILE = ROOT / "loop/state/runs/task-read_dafeng_L2_0230.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"

MUTATE = "--mutate" in sys.argv

cand = json.loads(CAND.read_text(encoding="utf-8"))
task = json.loads(TASKFILE.read_text(encoding="utf-8"))

# ── C01：源哈希（重新打开文件、重新算）─────────────────────────────────────
raw = DOCS.read_bytes()
file_hash = hashlib.sha256(raw).hexdigest()
text = json.loads(raw.decode("utf-8"))[0]["text"]

S, E = task["sourceRange"]
c01 = (file_hash == cand["source"]["sourceHash"] == task["sourceHash"])

# ── C02 / C03：区间口径 ───────────────────────────────────────────────────
slice_text = text[S:E]
c02 = (slice_text.startswith(task["unitHead"])
       and hashlib.sha256(slice_text.encode("utf-8")).hexdigest() == cand["source"]["segmentSha256"])
c03 = (list(cand["source"]["range"]) == [S, E] and list(cand["source"]["range"]) == list(task["sourceRange"]))

# ── 段落索引：本脚本**重新切分一遍**（不读构建脚本的 paras）────────────────
paras = []
off = S
for line in slice_text.split("\n"):
    if line.strip():
        lead = len(line) - len(line.lstrip())
        paras.append(("P%03d" % len(paras), line.strip(), off + lead))
    off += len(line) + 1
PLABEL = {p[0]: p for p in paras}
PBASE = {lab: a for lab, _t, a in paras}
_sep = re.compile(r"[。！？…]+")


def sent_units(t):
    out, last = [], 0
    for m in _sep.finditer(t):
        out.append((last, m.end()))
        last = m.end()
    if last < len(t):
        out.append((last, len(t)))
    return out or [(0, len(t))]


SENT = {lab: sent_units(t) for lab, t, _a in paras}


def para_of(pos):
    for lab, t, a in paras:
        if a <= pos < a + len(t):
            return lab
    return None


def sent_of(pos):
    lab = para_of(pos)
    if lab is None:
        return None
    rel = pos - PBASE[lab]
    for k, (a, b) in enumerate(SENT[lab]):
        if a <= rel < b:
            return k
    return 0


# ── 递归收集引文 ─────────────────────────────────────────────────────────
NODES = []


def walk(node, path):
    if isinstance(node, dict):
        for j, q in enumerate(node.get("quotes") or []):
            if isinstance(q, dict) and "quote" in q:
                NODES.append(("%s.quotes[%d]" % (path, j), q))
        for k, v in node.items():
            walk(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i))


for k, v in cand.items():
    if isinstance(v, (list, dict)):
        walk(v, k)

if MUTATE:
    # 故意改坏第一条引文的最后一个字：C04 必须转 FAIL
    p, q = NODES[0]
    bad_last = "X" if q["quote"][-1] != "X" else "Y"
    q["quote"] = q["quote"][:-1] + bad_last
    print("[变异] 已把 %s 的最后 1 字改为 %r（引文不再逐字）" % (p, bad_last))

c04 = c05 = c06 = c07 = c08 = True
bad = []
for path, q in NODES:
    if text[q["start"]:q["end"]] != q["quote"]:
        c04 = False
        bad.append("C04 %s" % path)
    if not (S <= q["start"] < q["end"] <= E):
        c05 = False
        bad.append("C05 %s" % path)
    if q.get("sourceHash") != task["sourceHash"]:
        c06 = False
        bad.append("C06 %s" % path)
    if q.get("wholeTextOccurrences") != text.count(q["quote"]):
        c07 = False
        bad.append("C07 whole %s" % path)
    if q.get("occurrencesInRange") != slice_text.count(q["quote"]):
        c07 = False
        bad.append("C07 range %s" % path)
    if q.get("paraLabel") != para_of(q["start"]):
        c08 = False
        bad.append("C08 %s" % path)
    if q.get("sentUnit") != sent_of(q["start"]):
        c08 = False
        bad.append("C08 sent %s" % path)

# ── C09：五栏零共用 ──────────────────────────────────────────────────────
COLUMNS = ("objective", "obstacle", "action", "result", "cost")
conf = []
for t in cand["tasks"]:
    seen_r, seen_s = {}, {}
    for col in COLUMNS:
        v = t.get(col)
        if not v:
            continue
        for q in v.get("quotes") or []:
            k = (q["start"], q["end"])
            if k in seen_r:
                conf.append("%s %s/%s" % (t["id"], seen_r[k], col))
            seen_r[k] = col
            sk = (q["paraLabel"], q["sentUnit"])
            if sk in seen_s and seen_s[sk] != col:
                conf.append("%s %s/%s %s" % (t["id"], seen_s[sk], col, sk))
            seen_s[sk] = col
c09 = not conf

# ── C10：worldSettings 判别字段 ──────────────────────────────────────────
wsp = []
for w in cand["worldSettings"]:
    kind = w.get("kind")
    if kind == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        wsp.append(w["id"])
    elif kind == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(
                x not in ("hold", "transfer", "use", "lose") for x in st):
            wsp.append(w["id"])
    elif kind == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        wsp.append(w["id"])
    elif kind not in ("place", "item", "rule"):
        wsp.append(w["id"])
c10 = not wsp

# ── C11：null 栏有 Note ─────────────────────────────────────────────────
np_ = [("%s.%s" % (t["id"], c)) for t in cand["tasks"] for c in COLUMNS
       if t.get(c) is None and not (t.get(c + "Note") or "").strip()]
c11 = not np_

# ── C12：全文 『…』必须是逐字子串 ────────────────────────────────────────
blob = json.dumps(cand, ensure_ascii=False)
spans = [m.group(1) for m in re.finditer(r"『([^『』]{1,600})』", blob)]
nonverbatim = [s for s in spans if s not in slice_text]
c12 = not nonverbatim

# ── C13：必需分区存在 ───────────────────────────────────────────────────
req = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
c13 = all(k in cand for k in req)

CHECKS = [
    ("C01_sourceHash", c01, "源文件/候选/任务三方哈希一致"),
    ("C02_sliceStartsWithUnitHead", c02, "切片以本单元标题开头且切片哈希一致"),
    ("C03_rangeMatchesTask", c03, "候选 source.range == 任务 sourceRange"),
    ("C04_quotesVerbatim", c04, "%d 条引文逐字成立" % len(NODES)),
    ("C05_quotesInRange", c05, "全部落在 [%d,%d)" % (S, E)),
    ("C06_sourceHashPerQuote", c06, "每条引文 sourceHash 全等"),
    ("C07_occurrenceCounts", c07, "全文/区间次数与现算相等"),
    ("C08_paragraphAndSentUnit", c08, "段号与句单元由本脚本独立切分判定"),
    ("C09_taskColumnsDisjoint", c09, "五元组五栏零共用（区间级+句单元级）"),
    ("C10_worldSettingDiscriminants", c10, "kind/placeState/itemStates/institution 合法"),
    ("C11_nullColumnsHaveNote", c11, "null 栏均有同名 Note"),
    ("C12_cornerSpansVerbatim", c12, "%d 处 『…』全部逐字（非逐字已用 〔…〕）" % len(spans)),
    ("C13_requiredSections", c13, "六个必需分区存在"),
]

print("=" * 72)
print("read:dafeng:L2:0230 独立重算%s" % ("（变异自检模式）" if MUTATE else ""))
print("=" * 72)
print("引文节点：%d" % len(NODES))
print("非空段：%d（本脚本独立切分）" % len(paras))
print()
allpass = True
for name, ok, desc in CHECKS:
    print("  %-34s %s   %s" % (name, "PASS" if ok else "FAIL", desc))
    if not ok:
        allpass = False
if bad:
    print()
    print("失败明细（前 40 条）：")
    for b in bad[:40]:
        print("   ", b)
if conf:
    print("跨栏共用明细：", conf[:20])
if wsp:
    print("判别字段问题：", wsp[:20])
if np_:
    print("null 缺 Note：", np_[:20])
if nonverbatim:
    print("非逐字 『…』：", nonverbatim[:20])

print()
if MUTATE:
    # 变异模式下：C04 应当 FAIL（并且只有它该 FAIL）
    if not c04:
        print("变异自检通过：改坏一个字后 C04 确实转 FAIL —— 判据不是恒真。")
        sys.exit(0)
    print("变异自检失败：改坏一个字后 C04 仍然 PASS —— 判据是恒真的，不可信。")
    sys.exit(1)

print("总结论：%s" % ("13/13 通过" if allpass else "存在 FAIL，见上"))
sys.exit(0 if allpass else 1)
