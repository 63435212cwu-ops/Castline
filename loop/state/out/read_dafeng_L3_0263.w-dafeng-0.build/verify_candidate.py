#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立校验 read:dafeng:L3:0263 的候选文件。

**刻意不 import build_candidate.py / content_0263.py 的任何函数**：
本脚本自己重新切一遍段落表、自己重新算哈希、自己重新 find 每条引文。
理由：如果校验脚本复用构建脚本的解析函数，两者会**同错**——
引用偏移写错时构建与校验一起错，校验就退化成自我确认。

校验项（逐条打印 PASS/FAIL，任一 FAIL 则退出码 1）：
  V01 源文件哈希 == 任务声明；切片起点是本单元标题；切片长度 == 5036。
  V02 候选 source.sliceSha256 == 现场重算的切片 sha256。
  V03 候选里**每一个**引文对象（递归收集，含 textualNotes.quote /
      worldSettings.quote / themeReadings.support[].quote 等所有嵌套层）
      满足 text[start:end] == quote、end-start == len(quote)、
      落在 [S,E) 内、sourceHash == 任务声明。
  V04 tasks 五元组：非空栏必须有引文、null 栏必须有非空 <栏>Note；
      同一任务内五栏引文区间**两两不相交**（提示词点名的 714/1664 缺陷）。
  V05 worldSettings 枚举字段合法（kind/placeState/itemStates/institution），
      且 place/item/rule 各自带了要求的说明字段。
  V06 themeReadings 每条都有 perspective / support / counter（counter 非空）。
  V07 foreshadows：有铺设引文；unresolved 必须有 unresolvedWhat 且不得同时给 payoff。
  V08 悬空 id 引用：散文里提到的 C##/S##/F##… 必须真的被定义过。
  V09 覆盖度自洽：候选 coverage.quoteUnionCodepoints 与现场重算一致。

用法：python3 -B -s verify_candidate.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS_REL = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK_PATH = ROOT / "loop/state/runs/task-read_dafeng_L3_0263.json"
CAND_PATH = ROOT / "loop/state/out/read_dafeng_L3_0263.candidate.json"

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print("%-6s %s%s" % ("PASS" if ok else "FAIL", name, ("  — " + detail) if detail else ""))
    return ok


task = json.loads(TASK_PATH.read_text(encoding="utf-8"))
S, E = task["sourceRange"]
DECLARED = task["sourceHash"]

docs_path = ROOT / DOCS_REL
raw = docs_path.read_bytes()
file_sha = hashlib.sha256(raw).hexdigest()
text = json.loads(raw.decode("utf-8"))[0]["text"]
slice_text = text[S:E]
slice_sha = hashlib.sha256(slice_text.encode("utf-8")).hexdigest()

if not CAND_PATH.exists():
    print("FAIL 候选文件不存在：%s" % CAND_PATH)
    sys.exit(1)
cand = json.loads(CAND_PATH.read_text(encoding="utf-8"))

TITLE = "第三十四章 四号：兄弟俩都一表人才"

# ── V01 ──────────────────────────────────────────────────────────────
check("V01a 源文件 sha256 == 任务声明", file_sha == DECLARED, file_sha[:16])
check("V01b 切片以单元标题开头", slice_text.startswith(TITLE), repr(slice_text[:24]))
check("V01c 切片长度 == 5036", len(slice_text) == 5036, "len=%d" % len(slice_text))

# ── V02 ──────────────────────────────────────────────────────────────
src = cand.get("source") or {}
check("V02 候选 sliceSha256 == 现场重算",
      src.get("sliceSha256") == slice_sha,
      "%s vs %s" % (str(src.get("sliceSha256"))[:16], slice_sha[:16]))
check("V02b 候选 source.range == 任务 sourceRange", list(src.get("range") or []) == [S, E],
      str(src.get("range")))

# ── V03 全部引文对象逐字核验 ──────────────────────────────────────────
quotes = []          # 带 sourceHash 的引文对象
loose = []           # 只有 quote/start/end 没有 sourceHash 的（如 coverage.ambiguousQuotes）


def walk(node, path):
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
            (quotes if node.get("sourceHash") else loose).append((path, node))
        for k, v in node.items():
            walk(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i))


walk(cand, "$")

bad_lit = [(p, q["quote"][:30]) for p, q in quotes if text[q["start"]:q["end"]] != q["quote"]]
bad_len = [(p, q["end"] - q["start"], len(q["quote"])) for p, q in quotes
           if q["end"] - q["start"] != len(q["quote"])]
bad_rng = [(p, q["start"], q["end"]) for p, q in quotes
           if not (S <= q["start"] < q["end"] <= E)]
bad_hsh = [(p, q["sourceHash"]) for p, q in quotes if q["sourceHash"] != DECLARED]

check("V03a 引文 text[start:end]==quote（%d 条）" % len(quotes), not bad_lit, str(bad_lit[:3]))
check("V03b end-start==len(quote)", not bad_len, str(bad_len[:3]))
check("V03c 引文全部落在区间内", not bad_rng, str(bad_rng[:3]))
check("V03d sourceHash 全部与任务一致", not bad_hsh, str(bad_hsh[:3]))
# 宽松对象（无 sourceHash）也逐字核验，只是不计入 sourceHash 检查
loose_bad = [(p, q["quote"][:20]) for p, q in loose if text[q["start"]:q["end"]] != q["quote"]]
check("V03e 无 sourceHash 的引文对象也逐字命中（%d 条）" % len(loose), not loose_bad,
      str(loose_bad[:3]))

# ── V04 tasks ────────────────────────────────────────────────────────
FIELDS = ("objective", "obstacle", "action", "result", "cost")
null_problems, collisions, tasks_n = [], [], 0
for t in cand.get("tasks") or []:
    tasks_n += 1
    tid = t.get("id")
    spans = []
    for f in FIELDS:
        qs = t.get(f + "Quotes") or []
        ivs = [(q["start"], q["end"], f) for q in qs
               if isinstance(q, dict) and isinstance(q.get("start"), int)]
        spans.extend(ivs)
        if t.get(f) is None:
            n = t.get(f + "Note")
            if not (isinstance(n, str) and n.strip()):
                null_problems.append("%s.%s 为 null 但无 Note" % (tid, f))
        elif not ivs:
            null_problems.append("%s.%s 非空但无引文" % (tid, f))
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b = spans[i], spans[j]
            if a[2] != b[2] and a[0] < b[1] and b[0] < a[1]:
                collisions.append("%s %s∩%s" % (tid, a[2], b[2]))

check("V04a 非空栏有引文 / null 栏有理由（%d 条任务）" % tasks_n, not null_problems,
      str(null_problems[:3]))
check("V04b 同一任务五栏引文区间两两不相交", not collisions, str(collisions[:3]))

# ── V05 worldSettings ────────────────────────────────────────────────
ws_problems = []
ws_counts = {"rule": 0, "place": 0, "item": 0}
for w in cand.get("worldSettings") or []:
    wid, kind = w.get("id"), w.get("kind")
    if kind not in ws_counts:
        ws_problems.append("%s 非法 kind=%r" % (wid, kind))
        continue
    ws_counts[kind] += 1
    if not (w.get("quote") or {}).get("quote"):
        ws_problems.append("%s 缺 quote" % wid)
    if not (isinstance(w.get("explain"), str) and w["explain"].strip()):
        ws_problems.append("%s 缺 explain" % wid)
    if kind == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        ws_problems.append("%s placeState=%r" % (wid, w.get("placeState")))
    if kind == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or set(st) - {"hold", "transfer", "use", "lose"}:
            ws_problems.append("%s itemStates=%r" % (wid, st))
    if kind == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        ws_problems.append("%s institution=%r" % (wid, w.get("institution")))

check("V05 worldSettings 枚举与必备字段（rule %d / place %d / item %d）"
      % (ws_counts["rule"], ws_counts["place"], ws_counts["item"]),
      not ws_problems, str(ws_problems[:3]))

# ── V06 themeReadings ────────────────────────────────────────────────
th_problems = []
for t in cand.get("themeReadings") or []:
    tid = t.get("id")
    if not (isinstance(t.get("perspective"), str) and t["perspective"].strip()):
        th_problems.append("%s 缺 perspective" % tid)
    for key in ("support", "counter"):
        v = t.get(key)
        if not isinstance(v, list) or not v:
            th_problems.append("%s 缺 %s" % (tid, key))
        else:
            for i, item in enumerate(v):
                if not (isinstance(item, dict) and (item.get("quote") or {}).get("quote")):
                    th_problems.append("%s.%s[%d] 缺引文" % (tid, key, i))
check("V06 themeReadings 三件齐全（perspective/support/counter）", not th_problems,
      str(th_problems[:3]))

# ── V07 foreshadows ──────────────────────────────────────────────────
fs_problems = []
for f in cand.get("foreshadows") or []:
    fid, status = f.get("id"), f.get("status")
    setup = f.get("setup") or {}
    if not (setup.get("quote") or []):
        fs_problems.append("%s 缺铺设引文" % fid)
    if status == "unresolved":
        if not (isinstance(f.get("unresolvedWhat"), str) and f["unresolvedWhat"].strip()):
            fs_problems.append("%s unresolved 但无 unresolvedWhat" % fid)
        if f.get("payoff"):
            fs_problems.append("%s 标 unresolved 却给了 payoff" % fid)
check("V07 foreshadows 铺设/回收/未回收说明", not fs_problems, str(fs_problems[:3]))

# ── V08 悬空引用 ─────────────────────────────────────────────────────
ID_KEYS = ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
           "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
           "themeReadings", "textualNotes", "unknowns", "selfCritique"]
defined = set()
for k in ID_KEYS:
    for it in cand.get(k) or []:
        if isinstance(it, dict) and it.get("id"):
            defined.add(it["id"])

REF_RE = re.compile(r"(?<![A-Za-z0-9])(?:TH|TN|NF|NW|SC|CE|RE|C|S|F|K|T|U|R|W)\d{2}(?![0-9])")
refs = {}
def collect_prose(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "quote":
                continue
            collect_prose(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect_prose(v, "%s[%d]" % (path, i))
    elif isinstance(node, str):
        for m in REF_RE.finditer(node):
            refs.setdefault(m.group(0), set()).add(path)
collect_prose(cand, "$")
dangling = sorted(r for r in refs if r not in defined)
check("V08 无悬空 id 引用（已定义 %d 个）" % len(defined), not dangling,
      "%s ← %s" % (dangling[:3], [sorted(refs[d])[:1] for d in dangling[:3]]) if dangling else "")

# ── V09 覆盖度自洽 ───────────────────────────────────────────────────
cov = cand.get("coverage") or {}
union = set()
for _path, q in quotes:
    union.update(range(q["start"], q["end"]))
recomputed = len(union)
check("V09 coverage.quoteUnionCodepoints 与现场重算一致",
      cov.get("quoteUnionCodepoints") == recomputed,
      "declared=%s recomputed=%d" % (cov.get("quoteUnionCodepoints"), recomputed))
check("V09b coverage.sliceCodepoints == E-S", cov.get("sliceCodepoints") == E - S,
      str(cov.get("sliceCodepoints")))

# ── 汇总 ─────────────────────────────────────────────────────────────
fails = [r for r in results if not r[1]]
print("\n" + "=" * 64)
print("引文对象（带 sourceHash）%d 条；无 sourceHash 的引文对象 %d 条；唯一区间 %d 个"
      % (len(quotes), len(loose), len({(q["start"], q["end"]) for _, q in quotes})))
print("检查项 %d 个，FAIL %d 个" % (len(results), len(fails)))
if fails:
    for n, _, d in fails:
        print("  FAIL %s %s" % (n, d))
    sys.exit(1)
print("全部通过。注意：本脚本只证明**引用定位与结构判据**可复现，")
print("不证明语义判断正确 —— semanticReview 仍是 not-performed。")
sys.exit(0)
