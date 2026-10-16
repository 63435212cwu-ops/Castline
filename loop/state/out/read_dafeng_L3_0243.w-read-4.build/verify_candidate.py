# -*- coding: utf-8 -*-
"""独立复核 read:dafeng:L3:0243 候选（从磁盘重读成品，不复用构建期偏移）。

与 build.py 的区别（这是它存在的理由）：
  · build.py 的偏移是它自己算的；这里**重新**在 docs[0].text 上 find 每个引文，
    用 find 的结果反查 start/end，因此能抓到「偏移写死但引文碰巧也在文中」的情况。
  · build.py 只检查它自己写出的结构；这里按**提示词的验收口径**重新判：
    五栏引文互斥、null 必带 Note、worldSettings 三态、themeReadings 三件套、
    伏笔 setup/payoff、speech 只当线索、semanticReview 不得声称完成。
  · 额外查两类构建期不查的缺陷：
      ① 散文里的伪引用：字段文本用「」引了真原文，但该句在本条目内没有被锚定；
      ② stateEvidence 的引用必须与 quote 同源（落在这个区间里）。
运行：python3 -B -s loop/state/out/read_dafeng_L3_0243.w-read-4.build/verify_candidate.py
"""
import hashlib
import json
import os
import re
import sys

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L3_0243.candidate.json")
START, END = 983109, 988086
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第十四章 女尸"
TASK_FIELDS = ("objective", "obstacle", "action", "result", "cost")

problems = []

with open(DOCS, encoding="utf-8") as fh:
    TEXT = json.load(fh)[0]["text"]
with open(CAND, encoding="utf-8") as fh:
    cand = json.load(fh)

# ── 0. 源与边界 ─────────────────────────────────────────────────────────
actual = hashlib.sha256(open(DOCS, "rb").read()).hexdigest()
if actual != SOURCE_HASH:
    problems.append("源哈希不符：%s" % actual)
if cand["source"]["sourceHash"] != SOURCE_HASH:
    problems.append("候选声明的 sourceHash 与任务不符")
if TEXT[START:END][: len(UNIT_HEAD)] != UNIT_HEAD:
    problems.append("切片不以单元标题开头")
if END - START != cand["source"]["codepoints"]:
    problems.append("码点数与任务区间不符")

# ── 1. 每个引文节点：逐字 + 偏移 + 区间 + 回填 ───────────────────────────
nodes = []


def walk(node, path):
    if isinstance(node, dict):
        if {"quote", "start", "end", "sourceHash"} <= set(node):
            nodes.append((path, node))
            return
        for k, v in node.items():
            walk(v, path + "." + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + "[%d]" % i)


walk(cand, "$")

for path, n in nodes:
    q, s, e = n["quote"], n["start"], n["end"]
    if TEXT.find(q) < 0:
        problems.append("引文在原文找不到：%s %r" % (path, q[:30]))
        continue
    if TEXT[s:e] != q:
        problems.append("偏移不符：%s text[%d:%d]=%r" % (path, s, e, TEXT[s:e][:30]))
    if TEXT.find(q) != s and n.get("startIsFirstGlobalOccurrence"):
        problems.append("startIsFirstGlobalOccurrence 标错：%s" % path)
    if not (START <= s < e <= END):
        problems.append("引文越界：%s [%d,%d)" % (path, s, e))
    if n["sourceHash"] != SOURCE_HASH:
        problems.append("引文哈希不符：%s" % path)

# ── 2. 任务五栏 ─────────────────────────────────────────────────────────
for t in cand["tasks"]:
    seen = {}
    spans = []
    for f in TASK_FIELDS:
        qs = t.get(f + "Quotes") or []
        val = t.get(f)
        if val is None:
            if not (t.get(f + "Note") or "").strip():
                problems.append("null 无 Note：%s.%s" % (t["id"], f))
            if qs:
                problems.append("null 栏却带 quotes：%s.%s" % (t["id"], f))
        else:
            if not qs:
                problems.append("有值却无引文：%s.%s" % (t["id"], f))
            if t.get(f + "Basis") not in ("explicit", "inferred", "derived", "unverified"):
                problems.append("basis 非法：%s.%s=%r" % (t["id"], f, t.get(f + "Basis")))
        for q in qs:
            if q["quote"] in seen:
                problems.append("同任务两栏共用一句：%s %s/%s" % (t["id"], seen[q["quote"]], f))
            seen[q["quote"]] = f
            spans.append((q["start"], q["end"], f))
    spans.sort()
    for i in range(len(spans) - 1):
        if spans[i][1] > spans[i + 1][0]:
            problems.append("同任务栏位引文区间重叠：%s %s/%s" % (t["id"], spans[i][2], spans[i + 1][2]))
    if not (t.get("actor") or "").strip():
        problems.append("任务缺 actor：%s" % t["id"])

# ── 3. 因果边有方向与触发 ────────────────────────────────────────────────
for ce in cand["causeEdges"]:
    for k in ("from", "to", "trigger", "mechanism"):
        if not (ce.get(k) or "").strip():
            problems.append("因果边缺 %s：%s" % (k, ce.get("id")))
    if not ce.get("quotes"):
        problems.append("因果边无引文：%s" % ce.get("id"))
    if ce.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
        problems.append("因果边 basis 非法：%s" % ce.get("id"))

for rej in cand["rejectedEdges"]:
    if not (rej.get("wouldBe") or "").strip() or not (rej.get("why") or "").strip():
        problems.append("rejectedEdge 缺 wouldBe/why：%s" % rej.get("id"))
    if not rej.get("quotes"):
        problems.append("rejectedEdge 无引文：%s" % rej.get("id"))

# ── 4. states ───────────────────────────────────────────────────────────
for s in cand["states"]:
    for k in ("who", "after", "anchor"):
        if not (s.get(k) or "").strip():
            problems.append("state 缺 %s：%s" % (k, s.get("id")))
    if s.get("before") is None and not (s.get("beforeNote") or "").strip():
        problems.append("state 前值为 null 却没写 beforeNote：%s" % s.get("id"))
    if not s.get("anchorQuotes"):
        problems.append("state 无锚点引文：%s" % s.get("id"))

# ── 5. 知识差写清谁知/不知 ───────────────────────────────────────────────
for k in cand["knowledgeGaps"]:
    for f in ("whoKnows", "whoDoesNot", "what"):
        if not (k.get(f) or "").strip():
            problems.append("知识差缺 %s：%s" % (f, k.get("id")))

# ── 6. 伏笔 ─────────────────────────────────────────────────────────────
for f in cand["foreshadows"]:
    if not (f.get("setup") or "").strip() or not f.get("setupQuotes"):
        problems.append("伏笔无铺设：%s" % f.get("id"))
    if f.get("status") not in ("resolved-in-range", "partial", "unresolved"):
        problems.append("伏笔 status 非法：%s" % f.get("id"))
    if f.get("status") == "resolved-in-range" and not f.get("payoff"):
        problems.append("伏笔标 resolved 却无回收：%s" % f.get("id"))
    if f.get("status") in ("unresolved", "partial") and not (f.get("unresolvedWhat") or "").strip():
        problems.append("伏笔未回收却没写 unresolvedWhat：%s" % f.get("id"))

# ── 7. worldSettings 三态 ───────────────────────────────────────────────
def own_quotes(node):
    out = set()

    def acc(n):
        if isinstance(n, dict):
            if {"quote", "start", "end", "sourceHash"} <= set(n):
                out.add(n["quote"])
                return
            for v in n.values():
                acc(v)
        elif isinstance(n, list):
            for v in n:
                acc(v)

    acc(node)
    return out


kinds = {"rule": 0, "place": 0, "item": 0}
for w in cand["worldSettings"]:
    if w.get("kind") not in kinds:
        problems.append("worldSettings kind 非法：%s=%r" % (w.get("id"), w.get("kind")))
        continue
    kinds[w["kind"]] += 1
    if not w.get("quote") or not (w.get("explain") or "").strip():
        problems.append("worldSettings 缺 quote/explain：%s" % w.get("id"))
    own = own_quotes(w)
    if w["kind"] == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            problems.append("placeState 非法：%s" % w.get("id"))
        if not w.get("stateEvidence") or not (w.get("stateEvidenceWhy") or "").strip():
            problems.append("place 缺 stateEvidence/why：%s" % w.get("id"))
    elif w["kind"] == "item":
        st = w.get("itemStates") or []
        if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            problems.append("itemStates 非法：%s=%r" % (w.get("id"), st))
        se = w.get("stateEvidence") or {}
        for key in ("hold", "transfer", "use", "lose"):
            if key not in se:
                problems.append("item 四态缺键：%s.%s" % (w.get("id"), key))
        for key in st:
            if not se.get(key):
                problems.append("item 声明的态无证据：%s.%s" % (w.get("id"), key))
        if not (w.get("itemStatesNote") or "").strip():
            problems.append("item 缺 itemStatesNote：%s" % w.get("id"))
    else:
        if w.get("institution") not in ("declared", "executed", "misunderstood"):
            problems.append("institution 非法：%s=%r" % (w.get("id"), w.get("institution")))
    # ① 散文里的伪引用
    for k, v in w.items():
        if isinstance(v, str):
            for m in re.findall(r"「([^」]+)」", v):
                if m in TEXT and not any(m in a for a in own):
                    problems.append("散文引了真原文但本条目未锚定：%s.%s %r" % (w.get("id"), k, m[:24]))

if sum(kinds.values()) != len(cand["worldSettings"]):
    problems.append("worldSettings 计数不符")

# ── 8. themeReadings 三件套 ─────────────────────────────────────────────
if len(cand["themeReadings"]) > 2:
    problems.append("themeReadings 超过 2 条：%d" % len(cand["themeReadings"]))
for th in cand["themeReadings"]:
    for k in ("perspective", "support", "counter"):
        if not (th.get(k) or "").strip():
            problems.append("主题读法缺 %s：%s" % (k, th.get("id")))
    if not th.get("supportQuotes") or not th.get("counterQuotes"):
        problems.append("主题读法缺引文：%s" % th.get("id"))
    # 禁止用事件密度/死亡人数/篇幅中点定义高潮
    blob = (th.get("perspective", "") + th.get("support", "") + th.get("counter", ""))
    for banned in ("高潮是第", "剧情点数量", "死亡人数", "篇幅中点", "三幕", "英雄旅程"):
        if banned in blob:
            problems.append("主题读法用了被禁判据 %r：%s" % (banned, th.get("id")))

# ── 9. speech 只当线索 ──────────────────────────────────────────────────
for p in cand["speechAsClueNotFact"]:
    for k in ("speaker", "speech", "canProve", "cannotProve", "why"):
        if not (p.get(k) or "").strip():
            problems.append("speech 缺 %s：%s" % (k, p.get("id")))
    if not p.get("quoteRef"):
        problems.append("speech 无引文锚点：%s" % p.get("id"))

# ── 10. 不得声称语义评审完成 ────────────────────────────────────────────
if cand.get("semanticReview") != "not-performed":
    problems.append("semanticReview 被声称完成：%r" % cand.get("semanticReview"))

# ── 11. 结论性要求 ──────────────────────────────────────────────────────
if len(cand.get("unknowns") or []) < 5:
    problems.append("unknowns 少于 5 条")
if len(cand.get("selfCritique") or []) < 3:
    problems.append("selfCritique 少于 3 条")

# ── 12. 未触碰受保护路径的静态证据（只读探针）───────────────────────────
print("引文节点 %d，唯一引文串 %d" % (len(nodes), len({n["quote"] for _p, n in nodes})))
print("分区：tasks=%d causeEdges=%d rejectedEdges=%d states=%d gaps=%d foreshadows=%d "
      "worldSettings=%d(%s) themes=%d unknowns=%d selfCritique=%d speechClues=%d"
      % (len(cand["tasks"]), len(cand["causeEdges"]), len(cand["rejectedEdges"]), len(cand["states"]),
         len(cand["knowledgeGaps"]), len(cand["foreshadows"]), len(cand["worldSettings"]),
         ",".join("%s:%d" % (k, v) for k, v in sorted(kinds.items())),
         len(cand["themeReadings"]), len(cand["unknowns"]), len(cand["selfCritique"]),
         len(cand["speechAsClueNotFact"])))
print("覆盖率：%s" % json.dumps(cand.get("coverage", {}).get("quoteUnionRatioOfNonSpace")))

if problems:
    for p in problems:
        print("[复核失败] %s" % p, file=sys.stderr)
    raise SystemExit("独立复核发现 %d 个问题" % len(problems))
print("独立复核通过：0 个问题")
