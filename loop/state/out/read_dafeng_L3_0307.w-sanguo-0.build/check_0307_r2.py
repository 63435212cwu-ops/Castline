#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 2 轮独立复核 read:dafeng:L3:0307 的候选（**从盘上读回**，不信任构建期内存）。

与既有两个脚本的分工
--------------------
· `build_0307.py`（上一轮）：构造期自检。
· `check_0307.py`（上一轮）：只复核 225 条 quoteRef 的逐字性与 sourceHash。
  ——它**不**校验散文里的自检式区间、**不**校验 `para` 段号、
  **不**检查预置引文是否被引用；本轮实测这三类里各藏着一个真问题
  （见 check_report_r2.json 的 problems 为空、以及 patch_0307.py 的 classA_fixed）。
· 本脚本（本轮新增）：另写一遍判据，并补上上面三类。保留 check_0307.py 不动，
  两份报告可互相对账（同一条引文在两套实现下都要成立）。

用法：
  python3 -B -s loop/state/out/read_dafeng_L3_0307.w-sanguo-0.build/check_0307_r2.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0307.candidate.json"
BUILD = HERE / "build_0307.py"
SNAP = HERE / "orphan_snapshot_before_patch.json"
REPORT = HERE / "check_report_r2.json"

START, END = 1366953, 1373655
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
ORPHAN_SHA = "5c0a0045c8e4408fde34bedec01f81641da7d8ce19586ee4f4e780f4b088906c"

problems: list[str] = []
stats: dict = {}


def bad(msg: str) -> None:
    problems.append(msg)


doc = json.loads(DOCS.read_bytes().decode("utf-8"))
text = doc[0]["text"]
sl = text[START:END]
cand = json.loads(CAND.read_bytes().decode("utf-8"))

# ── 0. 源与口径 ────────────────────────────────────────────────────────────
if hashlib.sha256(DOCS.read_bytes()).hexdigest() != SOURCE_HASH:
    bad("docs.json 的 sha256 与任务声明不符")
stats["sourceHash"] = 1
if len(sl) != END - START:
    bad("切片长度不符：%d" % len(sl))
if sl[:9] != "第七十八章 你来啦":
    bad("切片未以本单元标题开头：%r" % sl[:20])

src = cand.get("source") or {}
if src.get("sourceHash") != SOURCE_HASH:
    bad("候选 source.sourceHash 不符：%r" % src.get("sourceHash"))
if tuple(src.get("range") or ()) != (START, END):
    bad("候选 source.range 不符：%r" % (src.get("range"),))
if src.get("codepoints") != END - START:
    bad("候选 source.codepoints 不符：%r" % src.get("codepoints"))
if src.get("sliceSha256") != hashlib.sha256(sl.encode("utf-8")).hexdigest():
    bad("候选 source.sliceSha256 不符")

# 孤儿快照：证明本文件是「在上一轮产物之上修订」，不是重写
if SNAP.exists():
    snap_sha = hashlib.sha256(SNAP.read_bytes()).hexdigest()
    stats["orphanSnapshotMatches"] = int(snap_sha == ORPHAN_SHA)
    if snap_sha != ORPHAN_SHA:
        bad("孤儿快照 sha256 与上一轮产物登记值不符：%s" % snap_sha)
else:
    bad("缺孤儿快照：%s" % SNAP)

# ── 1. 递归收集全部 quoteRef 并逐条复核 ────────────────────────────────────
refs: list[tuple[str, dict]] = []
prose: list[tuple[str, str]] = []


def walk(node, path: str, collect: bool = True) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node:
            if collect:
                refs.append((path, node))
            return
        for k, v in node.items():
            walk(v, "%s.%s" % (path, k), collect)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i), collect)
    elif isinstance(node, str) and not collect:
        prose.append((path, node))


walk(cand, "$")
stats["quotes"] = len(refs)
for path, node in refs:
    q, s, e = node["quote"], node.get("start"), node.get("end")
    if not isinstance(s, int) or not isinstance(e, int):
        bad("引文缺整数 start/end：%s" % path)
        continue
    if text[s:e] != q:
        bad("引文与原文切片不等：%s（原文 %r）" % (path, text[s:e][:40]))
    if node.get("sourceHash") != SOURCE_HASH:
        bad("引文 sourceHash 不符：%s" % path)
    if sl.count(q) < 1:
        bad("引文不在本区间内：%s" % path)
    if node.get("globalOcc") is not None and text.count(q) != node["globalOcc"]:
        bad("globalOcc 不符：%s（声明 %s 实为 %d）" % (path, node["globalOcc"], text.count(q)))
    if node.get("occ") is not None and node["occ"] != s - START:
        bad("occ 与 start-START 不符：%s" % path)

# ── 2. 段落号全量复算（独立实现，并与 build 目录的 paras.txt 交叉核对）─────
paras: list[tuple[int, int, str]] = []
_pos = START
for _line in sl.split("\n"):
    if _line.strip():
        paras.append((_pos, _pos + len(_line), _line))
    _pos += len(_line) + 1
stats["paragraphs"] = len(paras)


def para_of(off: int):
    for i, (a, b, _t) in enumerate(paras):
        if a <= off < b:
            return i
    return None


para_bad, seen = [], set()
for path, node in refs:
    k = node.get("key")
    if k in seen:
        continue
    seen.add(k)
    p = para_of(node["start"])
    if node.get("para") != p:
        para_bad.append((k, node.get("para"), p))
if para_bad:
    bad("para 段号不符 %d 条：%r" % (len(para_bad), para_bad[:6]))
stats["uniqueQuoteKeys"] = len(seen)

ptxt = HERE / "paras.txt"
if ptxt.exists():
    tab = []
    for line in ptxt.read_text(encoding="utf-8").split("\n"):
        m = re.match(r"^(\d{4}) \[(\d+),(\d+)\) (.*)$", line)
        if m:
            tab.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    if len(tab) != len(paras):
        bad("paras.txt 段数 %d 与独立重算 %d 不符" % (len(tab), len(paras)))
    else:
        for i, (a, b, _t) in enumerate(paras):
            if (tab[i][1], tab[i][2]) != (a, b):
                bad("paras.txt 第 %d 段区间与独立重算不符" % i)
                break

# ── 3. 散文里的自检式区间逐条现算（上一轮 check 漏掉的一类）────────────────
prose.clear()
walk(cand, "$", collect=False)
stats["proseStrings"] = len(prose)
n_assert = 0
for path, s in prose:
    for m in re.finditer(r"TEXT\[(\d+):(\d+)\]\s*==\s*'([^']*)'", s):
        a, b, lit = int(m.group(1)), int(m.group(2)), m.group(3)
        n_assert += 1
        if text[a:b] != lit:
            bad("散文自检式为假：%s —— TEXT[%d:%d] 实为 %r，声明为 %r"
                % (path, a, b, text[a:b][:30], lit[:30]))
    for m in re.finditer(r"len\(TEXT\[(\d+):(\d+)\]\)\s*==\s*(\d+)", s):
        a, b, n = int(m.group(1)), int(m.group(2)), int(m.group(3))
        n_assert += 1
        if len(text[a:b]) != n:
            bad("散文长度自检式为假：%s —— len(TEXT[%d:%d])==%d 实为 %d"
                % (path, a, b, n, len(text[a:b])))
stats["proseSelfChecks"] = n_assert

# ── 4. 五栏纪律：null 必带同名 Note；不得跨栏共用一句 ─────────────────────
SLOTS = ("objective", "obstacle", "action", "result", "cost")
tasks = cand.get("tasks") or []
stats["tasks"] = len(tasks)
shared = []
for t in tasks:
    used: dict[str, list[str]] = {}
    for s in SLOTS:
        v = t.get(s)
        if v is None:
            if not (t.get(s + "Note") or "").strip():
                bad("任务 %s 的 %s 为 null 却没有 %sNote（未标注的未知）" % (t.get("id"), s, s))
            continue
        qs_ = v.get("quotes") or []
        if not qs_:
            bad("任务 %s 的 %s 有值却没有 quotes" % (t.get("id"), s))
        for q in qs_:
            used.setdefault(q.get("quote", ""), []).append(s)
    for q, where in used.items():
        if len(where) > 1:
            shared.append((t.get("id"), where, q[:40]))
if shared:
    bad("任务五栏跨栏共用同一句 %d 处：%r" % (len(shared), shared[:4]))
stats["slotSharedQuotes"] = len(shared)

# ── 5. 分区存在性（与机器校验器 validate_sections 同款判据）────────────────
for sec in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    if sec not in cand:
        bad("内容分区缺失：%s" % sec)
    else:
        stats[sec] = len(cand[sec]) if isinstance(cand[sec], list) else -1

# ── 6. 预置引文 vs 被引用 key 的差集（上一轮 check 漏掉的另一类）───────────
used_keys = {n.get("key") for _p, n in refs if n.get("key")}
stats["usedKeys"] = len(used_keys)
if BUILD.exists():
    bt = BUILD.read_text(encoding="utf-8")
    defined = set(re.findall(r'"(q_[a-z0-9_]+)":\s*\(', bt))
    orphan = sorted(defined - used_keys)
    stats["definedKeys"] = len(defined)
    stats["unusedKeys"] = len(orphan)
    print("预置引文 %d 个，被引用 %d 个，未引用 %d 个（不判 fail，供复核者反查）"
          % (len(defined), len(used_keys & defined), len(orphan)))

# ── 7. 本轮修订的可复核性 ──────────────────────────────────────────────────
tn0 = (cand.get("textualNotes") or [{}])[0].get("text", "")
if "TEXT[1366953:1366962] == '第七十八章 你来啦'" not in tn0:
    bad("A1 修订未落实：textualNotes[0] 里找不到修订后的自检式")
if "TEXT[1366953:1366965]" in tn0:
    bad("A1 修订未落实：textualNotes[0] 里仍留着旧的假区间")

t13 = next((t for t in tasks if t.get("id") == "T13"), None)
if t13 is None:
    bad("找不到 T13")
else:
    qc = (t13.get("result") or {}).get("quotes") or []
    if not qc or qc[0].get("key") != "q_candles_along":
        bad("T13.result 的首条引文不是 q_candles_along：%r"
            % (qc[0].get("key") if qc else None))
    elif qc[0].get("para") != 129:
        bad("A2 修订未落实：T13.result 引文 para 应为 129，实为 %r" % qc[0].get("para"))

rv = cand.get("reverseVerification")
if not isinstance(rv, list) or len(rv) < 9:
    bad("reverseVerification 缺失或过少：%r" % (len(rv) if isinstance(rv, list) else rv))
else:
    stats["reverseVerification"] = len(rv)
    for item in rv:
        q = item.get("quote")
        if q is None:
            continue
        if text[q["start"]:q["end"]] != q["quote"]:
            bad("RV %s 的引文不逐字" % item.get("id"))
    stats["rvExtras"] = sum(len([k for k in ("quote2",) if item.get(k)]) for item in rv)

am = cand.get("amendment")
if not isinstance(am, dict):
    bad("缺 amendment 字段")
else:
    if am.get("baseCandidateSha256") != ORPHAN_SHA:
        bad("amendment.baseCandidateSha256 与孤儿快照不符：%r" % am.get("baseCandidateSha256"))
    if len(am.get("classA_fixed") or []) != 2:
        bad("amendment.classA_fixed 应为 2 条")

# ── 8. 红线自检 ────────────────────────────────────────────────────────────
if cand.get("semanticReview") != "not-performed":
    bad("semanticReview 必须是 not-performed（定位正确 ≠ 语义已核验）")

# ── 落盘报告 ───────────────────────────────────────────────────────────────
report = {
    "task": "read:dafeng:L3:0307",
    "round": 2,
    "candidate": str(CAND.relative_to(ROOT)),
    "candidateSha256": hashlib.sha256(CAND.read_bytes()).hexdigest(),
    "orphanSnapshotSha256": ORPHAN_SHA,
    "sourceHash": SOURCE_HASH,
    "sliceSha256": hashlib.sha256(sl.encode("utf-8")).hexdigest(),
    "stats": stats,
    "problemCount": len(problems),
    "problems": problems,
}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if problems:
    print("\n".join("✗ " + p for p in problems), file=sys.stderr)
    print("复核未通过：%d 个问题" % len(problems), file=sys.stderr)
    sys.exit(1)

print("复核通过（第 2 轮）：引文 %d 条全部逐字命中且落在区间内；"
      "段落号 %d 个 key 全量复算一致；散文自检式 %d 条全为真；"
      "任务 %d / 因果 %d / 状态 %d / 伏笔 %d / 世界设定 %d / 主题 %d；反向验证 %d 条"
      % (stats["quotes"], stats["uniqueQuoteKeys"], stats["proseSelfChecks"],
         stats.get("tasks", 0), stats.get("causeEdges", 0), stats.get("states", 0),
         stats.get("foreshadows", 0), stats.get("worldSettings", 0),
         stats.get("themeReadings", 0), stats.get("reverseVerification", 0)))
print("候选 sha256 = %s" % report["candidateSha256"])
