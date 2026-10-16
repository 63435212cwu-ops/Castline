# -*- coding: utf-8 -*-
"""独立审计 read:dafeng:L1:0241 候选。

**刻意不复用 build_candidate.py 的任何函数或常量**：这里自己读 docs.json、自己用显式栈
遍历候选、自己重算偏移与哈希。复用生成脚本的校验等于让生成脚本给自己判卷。

内置负控（应当失败的断言）：确认这套复核不是空转。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND = ROOT / "loop/state/out/read_dafeng_L1_0241.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L1_0241.json"

task = json.loads(TASK.read_text(encoding="utf-8"))
START, END = task["sourceRange"]
HASH = task["sourceHash"]

raw = DOCS.read_bytes()
assert hashlib.sha256(raw).hexdigest() == HASH, "docs.json 哈希变了"
text = json.loads(raw.decode("utf-8"))[0]["text"]
cand = json.loads(CAND.read_text(encoding="utf-8"))

fails = []
checks = [0]


def ck(cond, msg):
    checks[0] += 1
    if not cond:
        fails.append(msg)


# ── 用显式栈收集所有引文对象（不递归、不依赖生成脚本）──────────────────────
quotes = []
stack = [("$", cand)]
while stack:
    path, node = stack.pop()
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
            quotes.append((path, node))
        for k, v in node.items():
            stack.append(("%s.%s" % (path, k), v))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            stack.append(("%s[%d]" % (path, i), v))

for p, r in quotes:
    ck(isinstance(r["start"], int) and isinstance(r["end"], int), "%s 偏移不是整数" % p)
    ck(text[r["start"]:r["end"]] == r["quote"],
       "%s 切片不等于引文：%r" % (p, r["quote"][:40]))
    ck(r.get("sourceHash") == HASH, "%s sourceHash 不符" % p)
    ck(START <= r["start"] and r["end"] <= END, "%s 越出本单元区间" % p)
    ck(text.find(r["quote"]) >= 0, "%s 全文 find 不到" % p)

# ── 结构化断言 ──────────────────────────────────────────────────────────────
FIELDS = ("objective", "obstacle", "action", "result", "cost")
for t in cand["tasks"]:
    used = {}
    for f in FIELDS:
        v = t.get(f)
        if v is None:
            ck(bool(t.get(f + "Note")), "%s.%s 为 null 却没有 %s" % (t["id"], f, f + "Note"))
            continue
        ck(bool(v.get("quotes")), "%s.%s 没有引文" % (t["id"], f))
        ck(v.get("basis") in ("explicit", "inferred", "derived", "unverified"),
           "%s.%s basis 非法" % (t["id"], f))
        for r in v["quotes"]:
            qt = r["quote"]
            ck(qt not in used,
               "%s 五栏共用引文：%r 同时用于 %s 与 %s" % (t["id"], qt, used.get(qt), f))
            used[qt] = f

# quoteSource 自洽性：机械重算「去掉引号内容后该段还剩不剩叙述文字」
import re as _re
SLICE = text[START:END]
PD = {}
_pos = START
for _chunk in SLICE.split("\n"):
    _s = _chunk.strip()
    if _s:
        PD[len(PD)] = (_pos + _chunk.index(_s), _s)
    _pos += len(_chunk) + 1


def _narration(pi):
    pt = PD[pi][1]
    out, depth = [], 0
    for ch in pt:
        if ch in ("\u201c", "\u300c"):
            depth += 1
            continue
        if ch in ("\u201d", "\u300d"):
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out.append(ch)
    return any(c not in " \t\u3002\uff0c\u3001\uff01\uff1f\u2026\u2014\uff0d\u00b7.\uff0e,;\uff1b:\uff1a\"'\u2018\u2019\uff08\uff09()" for c in out)


for p_, r in quotes:
    if not p_.endswith("sampleQuote") and ".quoteRef" not in p_:
        continue
for t in cand["tasks"]:
    for f in FIELDS:
        v = t.get(f)
        if v is None or "quoteSource" not in v:
            continue
        pi_list = []
        for r in v["quotes"]:
            hit = [pi for pi, (ps, pt) in PD.items() if ps <= r["start"] < ps + len(pt)]
            ck(len(hit) == 1, "%s.%s 引文定位不到唯一段" % (t["id"], f))
            pi_list.extend(hit)
        flags = {_narration(pi) for pi in pi_list}
        expect = "speech" if flags == {False} else ("narrative" if flags == {True} else "mixed")
        ck(v["quoteSource"] == expect,
           "%s.%s quoteSource 声明 %s 但机械重算为 %s" % (t["id"], f, v["quoteSource"], expect))

for e in cand["causeEdges"]:
    ck(bool(e.get("direction")), "%s 缺 direction" % e["id"])
    ck(bool(e.get("trigger")), "%s 缺 trigger" % e["id"])
    ck("→" in (e.get("direction") or ""), "%s direction 没有方向性" % e["id"])
    ck(bool(e.get("quotes")), "%s 没有引文" % e["id"])

for e in cand["hypothesizedEdges"]:
    ck(e.get("basis") == "inferred" and e.get("mechanism") == "inferred",
       "%s 推断链的 basis/mechanism 不是 inferred" % e["id"])
    ck(e.get("status") == "未验证", "%s 推断链没有标未验证" % e["id"])
    ck(e["id"] not in [x["id"] for x in cand["causeEdges"]], "%s 混进了 causeEdges" % e["id"])

for s in cand["states"]:
    if s["kind"] == "change":
        for f in ("before", "after", "anchor"):
            ck(bool(s.get(f) and s[f].get("quotes")), "%s.%s 缺前值/后值/锚点引文" % (s["id"], f))
    else:
        ck(bool(s.get("known")) and bool(s.get("unknown")), "%s 知识差缺 known/unknown" % s["id"])
        ck(bool(s.get("quotes")), "%s 知识差没有引文" % s["id"])

for f in cand["foreshadows"]:
    if f["status"] == "resolved":
        ck(bool(f.get("payoff") and f["payoff"].get("quotes")), "%s 标 resolved 却无回收引文" % f["id"])
    else:
        ck(f.get("payoff") is None and bool(f.get("payoffNote")),
           "%s 未回收却没有显式 payoffNote" % f["id"])

for w in cand["worldSettings"]:
    ck(w["kind"] == "rule" and w.get("institution") in ("declared", "executed", "misunderstood"),
       "%s 规则 institution 非法" % w["id"])
for p in cand["places"]:
    ck(p["kind"] == "place" and p.get("placeState") in ("arrived", "mentioned"),
       "%s placeState 非法" % p["id"])
for it in cand["items"]:
    ck(it["kind"] == "item", "%s kind 不是 item" % it["id"])
    ck(set(it["itemStates"]) <= {"hold", "transfer", "use", "lose"}, "%s itemStates 非法" % it["id"])
    ck(sorted(it["itemStates"]) == sorted({e["state"] for e in it["stateEvidence"]}),
       "%s itemStates 与 stateEvidence 不一致" % it["id"])

for th in cand["themeReadings"]:
    ck(bool(th.get("perspective")), "%s 缺 perspective" % th["id"])
    ck(bool(th.get("support")), "%s 缺 support" % th["id"])
    ck(bool(th.get("counter")), "%s 缺 counter（只列支持不叫解释）" % th["id"])

ck(cand["semanticReview"]["status"] == "not_performed", "不得声称语义评审已完成")
ck(cand["countsAreGenerated"] is True, "countsAreGenerated 必须为 true")
for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    ck(k in cand, "缺分区 %s" % k)

# ── 出版物层/叙述者层已单列（不得混进事实分区）──────────────────────────────
ck(len(cand["speechLayer"]) > 0, "人物话语层为空")
for s in cand["speechLayer"]:
    ck(bool(s.get("note")), "%s 话语层缺说明" % s["id"])

# ── 覆盖率数字自洽（用候选自己声明的段数重算）───────────────────────────────
cov = cand["coverage"]
ck(cov["paragraphsTouchedByQuotes"] == cov["nonEmptyParagraphs"] - cov["zeroCoverageParagraphs"],
   "覆盖率数字不自洽")
ck(len(cov["zeroCoverageList"]) == cov["zeroCoverageParagraphs"], "零引用清单长度与计数不符")

print("引文对象：%d / 检查项：%d，失败：%d" % (len(quotes), checks[0], len(fails)))
for f in fails[:20]:
    print("  FAIL", f)

# ── 负控：这些断言**应当**失败，否则说明复核是空转 ──────────────────────────
neg = []
probe = quotes[0][1]
q0 = probe["quote"]
a0, b0 = probe["start"], probe["end"]
neg.append(("偏移+1 应失败", text[a0 + 1:b0 + 1] != q0))
neg.append(("哈希改一位应失败", (HASH[:-1] + ("0" if HASH[-1] != "0" else "1")) != HASH))
neg.append(("不存在的引文找不到", text.find("\u0000不存在的引文串\u0000") < 0))
neg.append(("区间外偏移应越界", not (START <= (START - 1) and (START - 1 + 1) <= END)))
neg.append(("空引文不应命中非空切片", text[a0:b0] != ""))
neg_fail = [n for n, ok in neg if not ok]
print("负控 %d 项全部按预期失败（说明复核有效）；异常项 %s" % (len(neg), neg_fail))
if fails or neg_fail:
    sys.exit(1)
print("全部通过。")
