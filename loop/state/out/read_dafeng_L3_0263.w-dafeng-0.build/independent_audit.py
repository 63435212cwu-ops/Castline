#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计 read_dafeng_L3_0263 的候选（不复用其构建脚本的任何函数）。

职责（与候选构建脚本分离）：
  A. 收集候选里**所有** quoteRef 形态的引文对象（递归遍历，不按分区分支硬编码）。
  B. 逐条核验 docs[0].text[start:end] == quote、end-start == len(quote)、
     引文落在 [S,E)、sourceHash 与任务声明一致。
  C. 独立重算切片 sha256，与候选 source.sliceSha256 对账。
  D. 任务五元组五栏**两两区间不相交**（提示词禁止同一句同时当多栏依据）。
  E. null 栏必须有非空 <栏>Note。
  F. 机器可查的枚举合法性：worldSettings.kind / placeState / itemStates / institution。
  G. 统计各分区条数，输出 JSON 供提交记录引用。

用法：python3 -B -s independent_audit.py [候选路径] [--json 输出路径]
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L3_0263.json"
DEFAULT_CAND = ROOT / "loop/state/out/read_dafeng_L3_0263.candidate.json"

argv = [a for a in sys.argv[1:] if not a.startswith("--")]
json_out = None
if "--json" in sys.argv:
    json_out = sys.argv[sys.argv.index("--json") + 1]
cand_path = Path(argv[0]) if argv else DEFAULT_CAND

task = json.loads(TASK.read_text(encoding="utf-8"))
S, E = task["sourceRange"]
DECLARED_HASH = task["sourceHash"]

raw = DOCS.read_bytes()
file_sha = hashlib.sha256(raw).hexdigest()
docs = json.loads(raw.decode("utf-8"))
text = docs[0]["text"]
slice_text = text[S:E]
slice_sha = hashlib.sha256(slice_text.encode("utf-8")).hexdigest()

cand = json.loads(cand_path.read_text(encoding="utf-8"))

fails = []
quotes = []          # (jsonpath, quote, start, end, declared_hash)


def walk(node, path):
    """递归收集所有形如 {quote, start, end, sourceHash} 的引文对象。"""
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
            quotes.append((path, node))
        for k, v in node.items():
            walk(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i))


walk(cand, "$")

# ── A/B 引文逐字核验 ───────────────────────────────────────────────
bad_literal, bad_len, bad_range, bad_hash, bad_type = [], [], [], [], []
for path, q in quotes:
    s, e, qq = q.get("start"), q.get("end"), q["quote"]
    if not isinstance(s, int) or not isinstance(e, int):
        bad_type.append((path, repr(s), repr(e)))
        continue
    if s < 0 or e > len(text) or s >= e:
        bad_range.append((path, s, e))
        continue
    if text[s:e] != qq:
        bad_literal.append((path, qq[:40], text[s:e][:40]))
    if e - s != len(qq):
        bad_len.append((path, e - s, len(qq)))
    if s < S or e > E:
        bad_range.append((path, s, e))
    if q.get("sourceHash") and q["sourceHash"] != DECLARED_HASH:
        bad_hash.append((path, q["sourceHash"]))

# ── C 切片哈希对账 ────────────────────────────────────────────────
src = cand.get("source") or {}
slice_declared = src.get("sliceSha256")
slice_ok = (slice_declared == slice_sha) if slice_declared else None

# ── D 任务五栏区间不相交 ──────────────────────────────────────────
FIELDS = ["objective", "obstacle", "action", "result", "cost"]
collisions, null_without_note, field_stats = [], [], []
for t in cand.get("tasks", []):
    tid = t.get("id", "?")
    spans = {}
    for f in FIELDS:
        ints = []
        for q in (t.get(f + "Quotes") or []):
            if isinstance(q, dict) and isinstance(q.get("start"), int) and isinstance(q.get("end"), int):
                ints.append((q["start"], q["end"], f))
        spans[f] = ints
        val = t.get(f)
        if val is None:
            note = t.get(f + "Note")
            if not (isinstance(note, str) and note.strip()):
                null_without_note.append("%s.%s" % (tid, f))
        else:
            if not ints:
                null_without_note.append("%s.%s（非空但无引文）" % (tid, f))
    # 两两相交检查
    flat = [iv for f in FIELDS for iv in spans[f]]
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            a, b = flat[i], flat[j]
            if a[2] != b[2] and a[0] < b[1] and b[0] < a[1]:
                collisions.append("%s: %s[%d,%d) ∩ %s[%d,%d)" % (tid, a[2], a[0], a[1], b[2], b[0], b[1]))
    field_stats.append({"id": tid, "nulls": [f for f in FIELDS if t.get(f) is None],
                        "quoteCounts": {f: len(spans[f]) for f in FIELDS}})

# ── F 枚举合法性 ──────────────────────────────────────────────────
enum_bad = []
for w in cand.get("worldSettings", []):
    kind = w.get("kind")
    if kind not in ("rule", "place", "item"):
        enum_bad.append("worldSettings %s: kind=%r" % (w.get("id"), kind))
    if kind == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        enum_bad.append("worldSettings %s: placeState=%r" % (w.get("id"), w.get("placeState")))
    if kind == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            enum_bad.append("worldSettings %s: itemStates=%r" % (w.get("id"), st))
    if kind == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        enum_bad.append("worldSettings %s: institution=%r" % (w.get("id"), w.get("institution")))

# ── G 分区计数 ────────────────────────────────────────────────────
counts = {k: (len(v) if isinstance(v, (list, dict)) else None) for k, v in cand.items()}

report = {
    "candidate": str(cand_path.relative_to(ROOT)),
    "candidateSha256": hashlib.sha256(cand_path.read_bytes()).hexdigest(),
    "sourceFile": str(DOCS.relative_to(ROOT)),
    "sourceHashActual": file_sha,
    "sourceHashMatchesTask": file_sha == DECLARED_HASH,
    "sliceRange": [S, E],
    "sliceCodepoints": len(slice_text),
    "sliceStartsWithTitle": slice_text.startswith("第三十四章 四号：兄弟俩都一表人才"),
    "sliceSha256Actual": slice_sha,
    "sliceSha256Declared": slice_declared,
    "sliceSha256Matches": slice_ok,
    "quoteObjectsAudited": len(quotes),
    "badLiteral": bad_literal,
    "badLength": bad_len,
    "badRange": bad_range,
    "badSourceHash": bad_hash,
    "badType": bad_type,
    "taskFieldCollisions": collisions,
    "nullOrEmptyFieldProblems": null_without_note,
    "enumProblems": enum_bad,
    "taskFieldStats": field_stats,
    "sectionCounts": counts,
}
report["ok"] = not (bad_literal or bad_len or bad_range or bad_hash or bad_type
                    or collisions or null_without_note or enum_bad
                    or not report["sourceHashMatchesTask"] or slice_ok is False
                    or not report["sliceStartsWithTitle"])

print(json.dumps(report, ensure_ascii=False, indent=1))
if json_out:
    Path(json_out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
sys.exit(0 if report["ok"] else 1)
