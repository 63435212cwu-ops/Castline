# -*- coding: utf-8 -*-
"""生成 read:dafeng:L3:0243 候选（《大奉打更人》第十四章 女尸）。

工作目录：/Users/carmen/Desktop/星系
输出：    loop/state/out/read_dafeng_L3_0243.candidate.json

纪律：
  · 所有引文偏移由 docs[0].text.find(锚点) 现算，**没有任何一条 start/end 是手写的**；
  · 锚点解析成**整行**（去首尾空白）或行内 seg，保证 quote 逐字来自原文；
  · 构建期跑 12 类自检，任一失败即拒绝写出候选（不会产出半成品）。
运行：   python3 -B -s loop/state/out/read_dafeng_L3_0243.w-read-4.build/build.py
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
GRAPH = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.json")
OUT = os.path.join(ROOT, "loop/state/out/read_dafeng_L3_0243.candidate.json")
START, END = 983109, 988086
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第十四章 女尸"
TASK_ID = "read:dafeng:L3:0243"
AGENT = "w-read-4"

with open(DOCS, encoding="utf-8") as fh:
    _DOC = json.load(fh)[0]
TEXT = _DOC["text"]
SLICE = TEXT[START:END]

if SLICE[: len(UNIT_HEAD)] != UNIT_HEAD:
    raise SystemExit("偏移口径自检失败：切片不以单元标题开头：%r" % SLICE[:30])
if len(SLICE) != END - START:
    raise SystemExit("切片长度与区间不符：%d != %d" % (len(SLICE), END - START))
_actual = hashlib.sha256(open(DOCS, "rb").read()).hexdigest()
if _actual != SOURCE_HASH:
    raise SystemExit("sourceHash 不符：%s" % _actual)

sys.path.insert(0, HERE)
import content  # noqa: E402


# ── 锚点解析 ────────────────────────────────────────────────────────────
def _line_span(anchor):
    """锚点所在整行（去首尾空白）在**全文**里的 [start,end)。"""
    i = SLICE.find(anchor)
    if i < 0:
        raise SystemExit("行锚点未命中：%r" % anchor)
    if SLICE.count(anchor) != 1:
        raise SystemExit("行锚点在区间内不唯一：%r x%d" % (anchor, SLICE.count(anchor)))
    ls = SLICE.rfind("\n", 0, i) + 1
    le = SLICE.find("\n", i)
    if le < 0:
        le = len(SLICE)
    seg = SLICE[ls:le]
    stripped = seg.strip()
    if not stripped:
        raise SystemExit("空行：%r" % anchor)
    off = START + ls + (len(seg) - len(seg.lstrip()))
    # ⚠️ 第四个返回值必须是**全文**行首偏移（START+ls），不是切片内偏移：
    # _seg_span 会拿它去 TEXT 上切片。原先返回 ls（切片内下标）会让所有
    # 行内 seg 锚点在 TEXT 上落到错误位置（实测报「seg head 未命中行」）。
    return off, off + len(stripped), START + ls


ANCHORS = content.ANCHORS
RESOLVED = {}
for _name, _anchor in ANCHORS.items():
    _s, _e, _ls = _line_span(_anchor)
    if _s < START or _e > END:
        raise SystemExit("引文越界：%s [%d,%d)" % (_name, _s, _e))
    _q = TEXT[_s:_e]
    if not _q or _q.strip() != _q:
        raise SystemExit("引文为空或含首尾空白：%s %r" % (_name, _q[:30]))
    RESOLVED[_name] = (_q, _s, _e, _ls)


def _seg_span(line_anchor, head, tail):
    """行内片段：head 起点 → tail 终点（都在同一行内）。"""
    q, s, e, ls = RESOLVED[line_anchor]
    line = TEXT[ls:TEXT.find("\n", ls) if TEXT.find("\n", ls) >= 0 else len(TEXT)]
    hi = line.find(head)
    if hi < 0:
        raise SystemExit("seg head 未命中行 %s：%r" % (line_anchor, head))
    ti = line.find(tail, hi)
    if ti < 0:
        raise SystemExit("seg tail 未命中行 %s：%r" % (line_anchor, tail))
    a = ls + hi
    b = ls + ti + len(tail)
    if a < START or b > END:
        raise SystemExit("seg 越界：%s [%d,%d)" % (line_anchor, a, b))
    frag = TEXT[a:b]
    if not frag or frag.strip() != frag:
        raise SystemExit("seg 含首尾空白：%r" % frag[:40])
    return frag, a, b


def _node(q, s, e):
    whole = TEXT.count(q)
    inrange = SLICE.count(q)
    first = TEXT.find(q)
    return {
        "quote": q,
        "start": s,
        "end": e,
        "sourceHash": SOURCE_HASH,
        "wholeTextOccurrences": whole,
        "inRangeOccurrences": inrange,
        "firstGlobalOffset": first,
        "startIsFirstGlobalOccurrence": first == s,
        "locatorStrength": ("globally-unique" if whole == 1
                            else ("in-range-unique" if inrange == 1 else "ambiguous")),
    }


def Q(*names):
    out = []
    for n in names:
        q, s, e, _ls = RESOLVED[n]
        out.append(_node(q, s, e))
    return out


def Q1(name):
    r = Q(name)
    if len(r) != 1:
        raise SystemExit("Q1 需要恰好一条：%r" % (name,))
    return r[0]


def Qseg(line_anchor, head, tail):
    q, s, e = _seg_span(line_anchor, head, tail)
    return _node(q, s, e)


# ── 标记（content.py 里用 A / A1 / SG 写，构建期在这里解析成带偏移的节点）──
def _resolve(node):
    if isinstance(node, dict):
        if "__anchors__" in node:
            return Q(*node["__anchors__"])
        if "__anchor__" in node:
            return Q1(node["__anchor__"])
        if "__seg__" in node:
            return Qseg(*node["__seg__"])
        return {k: _resolve(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve(v) for v in node]
    return node


cand = {
    "schemaVersion": "castline/read-candidate/1",
    "task": TASK_ID,
    "agent": AGENT,
    "role": "READER",
    "book": "dafeng",
    "bookTitle": "大奉打更人",
    "lane": "3",
    "unitIndex": "243",
    "unitHead": UNIT_HEAD,
    "source": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "selector": "docs[0].text",
        "range": [START, END],
        "codepoints": END - START,
        "sourceHash": SOURCE_HASH,
        "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片的）",
        "sliceSha256": hashlib.sha256(SLICE.encode("utf-8")).hexdigest(),
        "sliceSha256Scope": "docs[0].text[%d:%d] 的 sha256（另起字段，不覆盖 sourceHash）" % (START, END),
        "offsetCaliber": "start/end 全部是相对 docs[0].text **全文** 的 codepoint 偏移；自检式：docs[0].text[%d:%d] 以本单元标题开头" % (START, END),
        "boundaryHead": SLICE[: len(UNIT_HEAD)],
        "sliceStartsWithUnitHead": SLICE[: len(UNIT_HEAD)] == UNIT_HEAD,
        "graphCachePath": "data/cache/1063b17ca65ec1b76f30e460.json",
        "graphCacheNote": "图谱缓存里的摘要**不是原文证据**，本候选没有任何一条引文或结论取自它；它只用于事后对照（见 machineSelfCheck.graphCacheCrossCheck）。",
    },
    "provenanceNote": "全部 %d 个引文节点的 start/end 由 %s 用 TEXT.find(锚点) 现算（锚点=整行或行内 seg）；没有一条偏移是手写或从别处抄来的。quote 一律等于 TEXT[start:end]，可用 verify_candidate.py 从磁盘重读成品独立复算。"
                     % (0, os.path.join("loop/state/out/read_dafeng_L3_0243.w-read-4.build", "build.py")),
    "semanticReview": "not-performed",
    "semanticReviewNote": "本候选只做了引用定位与逐字核验（脚本可复现）＋分区归属判断，**没有**做独立语义评审，也没有跨单元对读（第十三章与第十五章都未读）。定位正确 ≠ 语义已核验；不声称 semanticReview 完成。",
    "basisLegend": {
        "explicit": "原文直述（叙述句或人物动作被叙述直接写出）",
        "inferred": "我的归纳（原文没有直接这么说，但从直述材料可合理归纳）",
        "derived": "跨段推导（把两处以上原文材料接起来，机制部分由我补）",
        "unverified": "存疑（材料不足，仅登记待核，不作结论）",
    },
    "speechAsClueNotFact": [],
    "speechAsClueNotFactNote": "",
    "nullFieldRule": "",
    "tasks": [],
    "causeEdges": [],
    "rejectedEdges": [],
    "states": [],
    "knowledgeGaps": [],
    "foreshadows": [],
    "notForeshadows": [],
    "foreshadowsNote": "",
    "worldSettings": [],
    "notWorldSettings": [],
    "worldSettingsNote": "",
    "themeReadings": [],
    "textualNotes": [],
    "unknowns": [],
    "selfCritique": [],
    "coverage": {},
    "machineSelfCheck": {},
}

for key in ("speechAsClueNotFact", "tasks", "causeEdges", "rejectedEdges", "states",
            "knowledgeGaps", "foreshadows", "notForeshadows", "worldSettings",
            "notWorldSettings", "themeReadings", "textualNotes", "unknowns",
            "selfCritique"):
    cand[key] = _resolve(getattr(content, key.upper()))

for key in ("speechAsClueNotFactNote", "nullFieldRule", "foreshadowsNote",
            "worldSettingsNote", "provenanceNote", "semanticReviewNote"):
    setattr_ = None

cand["speechAsClueNotFactNote"] = content.SPEECH_NOTE
cand["nullFieldRule"] = content.NULL_FIELD_RULE
cand["foreshadowsNote"] = content.FORESHADOWS_NOTE
cand["worldSettingsNote"] = content.WORLD_SETTINGS_NOTE

# ── 自检 ────────────────────────────────────────────────────────────────
problems = []
FIELDS = ("objective", "obstacle", "action", "result", "cost")
REQUIRED_SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]

for sec in REQUIRED_SECTIONS:
    if sec not in cand or not isinstance(cand[sec], list):
        problems.append("缺少必需分区（或不是数组）：%s" % sec)

quote_nodes = []


def _walk(node, path):
    if isinstance(node, dict):
        if {"quote", "start", "end", "sourceHash"} <= set(node):
            quote_nodes.append((path, node))
            return
        for k, v in node.items():
            _walk(v, path + "." + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, path + "[%d]" % i)


_walk(cand, "$")

for path, node in quote_nodes:
    s, e, q = node["start"], node["end"], node["quote"]
    if TEXT[s:e] != q:
        problems.append("QUOTE_MISMATCH %s text[%d:%d]=%r quote=%r" % (path, s, e, TEXT[s:e][:40], q[:40]))
    if TEXT.find(q) < 0:
        problems.append("QUOTE_NOT_FOUND %s %r" % (path, q[:40]))
    if not (START <= s < e <= END):
        problems.append("QUOTE_OUT_OF_RANGE %s [%d,%d)" % (path, s, e))
    if node["sourceHash"] != SOURCE_HASH:
        problems.append("QUOTE_HASH_MISMATCH %s" % path)
    if node["inRangeOccurrences"] != 1:
        problems.append("ANCHOR_NOT_UNIQUE_IN_RANGE %s x%d %r" % (path, node["inRangeOccurrences"], q[:30]))

# 1) 任务五栏：不共用同一句 + 区间不重叠 + null 必须带 Note
TASK_QUOTES = {}
for t in cand["tasks"]:
    seen = {}
    for f in FIELDS:
        qs = t.get(f + "Quotes") or []
        if t.get(f) is None:
            if not (t.get(f + "Note") or "").strip():
                problems.append("NULL_WITHOUT_NOTE %s.%s" % (t["id"], f))
            if qs:
                problems.append("NULL_FIELD_WITH_QUOTES %s.%s" % (t["id"], f))
        else:
            if not qs:
                problems.append("FIELD_WITHOUT_QUOTES %s.%s" % (t["id"], f))
            if not (t.get(f + "Basis") or "").strip():
                problems.append("FIELD_WITHOUT_BASIS %s.%s" % (t["id"], f))
            if t.get(f + "Basis") not in cand["basisLegend"]:
                problems.append("BASIS_BAD %s.%s=%r" % (t["id"], f, t.get(f + "Basis")))
        for q in qs:
            if q["quote"] in seen:
                problems.append("FIELD_QUOTE_COLLISION %s %s/%s %r" % (t["id"], seen[q["quote"]], f, q["quote"][:30]))
            seen[q["quote"]] = f
    TASK_QUOTES[t["id"]] = set(seen)
    spans = sorted((q["start"], q["end"], f) for f in FIELDS for q in (t.get(f + "Quotes") or []))
    for i in range(len(spans) - 1):
        if spans[i][1] > spans[i + 1][0]:
            problems.append("FIELD_SPAN_OVERLAP %s %s/%s" % (t["id"], spans[i][2], spans[i + 1][2]))

# 2) 跨任务不得复用同一句（比提示词更严的自设标准）
ids = sorted(TASK_QUOTES)
for i in range(len(ids)):
    for j in range(i + 1, len(ids)):
        shared = TASK_QUOTES[ids[i]] & TASK_QUOTES[ids[j]]
        if shared:
            problems.append("CROSS_TASK_QUOTE_REUSE %s/%s %r" % (ids[i], ids[j], sorted(shared)[0][:30]))

# 3) 因果边必须有方向 + 触发 + 机制
for ce in cand["causeEdges"]:
    for k in ("from", "to", "trigger", "mechanism", "basis"):
        if not (ce.get(k) or "").strip():
            problems.append("CAUSE_MISSING_%s %s" % (k.upper(), ce.get("id")))
    if ce.get("basis") not in cand["basisLegend"]:
        problems.append("CAUSE_BASIS_BAD %s" % ce.get("id"))
    if not ce.get("quotes"):
        problems.append("CAUSE_NO_QUOTES %s" % ce.get("id"))

for rej in cand["rejectedEdges"]:
    for k in ("wouldBe", "why"):
        if not (rej.get(k) or "").strip():
            problems.append("REJECTED_MISSING_%s %s" % (k.upper(), rej.get("id")))
    if not rej.get("quotes"):
        problems.append("REJECTED_NO_QUOTES %s" % rej.get("id"))

# 4) states：前值/后值 + 锚点；null 前值必须带 Note
for s in cand["states"]:
    for k in ("who", "after", "anchor"):
        if not (s.get(k) or "").strip():
            problems.append("STATE_MISSING_%s %s" % (k.upper(), s.get("id")))
    if s.get("before") is None and not (s.get("beforeNote") or "").strip():
        problems.append("STATE_NULL_BEFORE_WITHOUT_NOTE %s" % s.get("id"))
    if not s.get("anchorQuotes"):
        problems.append("STATE_NO_ANCHOR_QUOTES %s" % s.get("id"))

# 5) 知识差必须写清谁知/谁不知/知道什么
for k in cand["knowledgeGaps"]:
    for f in ("whoKnows", "whoDoesNot", "what"):
        if not (k.get(f) or "").strip():
            problems.append("GAP_MISSING_%s %s" % (f.upper(), k.get("id")))

# 6) 伏笔必须有铺设；unresolved / partial 必须写 unresolvedWhat
for f in cand["foreshadows"]:
    if not (f.get("setup") or "").strip():
        problems.append("FORESHADOW_NO_SETUP %s" % f.get("id"))
    if f.get("status") not in ("resolved-in-range", "partial", "unresolved"):
        problems.append("FORESHADOW_STATUS_BAD %s=%r" % (f.get("id"), f.get("status")))
    if f.get("status") in ("unresolved", "partial") and not (f.get("unresolvedWhat") or "").strip():
        problems.append("FORESHADOW_UNRESOLVED_NO_WHAT %s" % f.get("id"))
    if f.get("status") == "resolved-in-range" and not (f.get("payoff") or "").strip():
        problems.append("FORESHADOW_RESOLVED_NO_PAYOFF %s" % f.get("id"))

# 7) worldSettings 三档枚举 + 证据锚定
def _own_quotes(node):
    own = set()

    def acc(n):
        if isinstance(n, dict):
            if {"quote", "start", "end", "sourceHash"} <= set(n):
                own.add(n["quote"])
                return
            for v in n.values():
                acc(v)
        elif isinstance(n, list):
            for v in n:
                acc(v)

    acc(node)
    return own


for w in cand["worldSettings"]:
    if w.get("kind") not in ("rule", "place", "item"):
        problems.append("WS_KIND_BAD %s=%r" % (w.get("id"), w.get("kind")))
        continue
    if not w.get("quote"):
        problems.append("WS_NO_QUOTE %s" % w.get("id"))
    if not (w.get("explain") or "").strip():
        problems.append("WS_NO_EXPLAIN %s" % w.get("id"))
    own = _own_quotes(w)
    if w["kind"] == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            problems.append("PLACE_STATE_BAD %s=%r" % (w.get("id"), w.get("placeState")))
        if not w.get("stateEvidence"):
            problems.append("PLACE_NO_STATE_EVIDENCE %s" % w.get("id"))
        if not (w.get("stateEvidenceWhy") or "").strip():
            problems.append("PLACE_NO_STATE_EVIDENCE_WHY %s" % w.get("id"))
    elif w["kind"] == "item":
        st = w.get("itemStates") or []
        if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            problems.append("ITEM_STATES_BAD %s=%r" % (w.get("id"), st))
        se = w.get("stateEvidence") or {}
        for key in ("hold", "transfer", "use", "lose"):
            if key not in se:
                problems.append("ITEM_STATE_EVIDENCE_MISSING_KEY %s.%s" % (w.get("id"), key))
        for key in st:
            if not se.get(key):
                problems.append("ITEM_STATE_NO_EVIDENCE %s.%s" % (w.get("id"), key))
        if not (w.get("itemStatesNote") or "").strip():
            problems.append("ITEM_NO_STATES_NOTE %s" % w.get("id"))
    else:
        if w.get("institution") not in ("declared", "executed", "misunderstood"):
            problems.append("INSTITUTION_BAD %s=%r" % (w.get("id"), w.get("institution")))
    # 散文里用「」引的真原文必须在本条目内锚定（否则读者会以为它已被逐字核验）
    for k, v in w.items():
        if not isinstance(v, str):
            continue
        for m in re.findall(r"「([^」]+)」", v):
            if m in TEXT and not any(m in a for a in own):
                problems.append("UNANCHORED_REAL_QUOTE %s.%s %r" % (w.get("id"), k, m[:24]))

# 8) themeReadings 三件套，最多 2 条
for th in cand["themeReadings"]:
    for k in ("perspective", "support", "counter"):
        if not (th.get(k) or "").strip():
            problems.append("THEME_MISSING_%s %s" % (k.upper(), th.get("id")))
if len(cand["themeReadings"]) > 2:
    problems.append("THEME_TOO_MANY %d" % len(cand["themeReadings"]))

# 9) speechAsClueNotFact 形状
for p in cand["speechAsClueNotFact"]:
    for k in ("speaker", "speech", "why"):
        if not (p.get(k) or "").strip() if k != "speech" else not p.get(k):
            problems.append("SPEECH_MISSING_%s %s" % (k.upper(), p.get("id")))

# 10) 不得声称语义评审完成
if cand["semanticReview"] != "not-performed":
    problems.append("SEMANTIC_REVIEW_CLAIMED %r" % cand["semanticReview"])

# 11) unknowns / selfCritique 必须非空
if len(cand["unknowns"]) < 5:
    problems.append("UNKNOWNS_TOO_FEW %d" % len(cand["unknowns"]))
if len(cand["selfCritique"]) < 3:
    problems.append("SELF_CRITIQUE_TOO_FEW %d" % len(cand["selfCritique"]))

# 12) 覆盖率（只统计非空白码点）
merged = []
for _p, n in quote_nodes:
    merged.append((n["start"], n["end"]))
merged.sort()
uni = []
for a, b in merged:
    if uni and a <= uni[-1][1]:
        uni[-1][1] = max(uni[-1][1], b)
    else:
        uni.append([a, b])
cov = sum(b - a for a, b in uni)
non_space = [i for i, ch in enumerate(SLICE) if not ch.isspace()]
paras = []
for m in re.finditer(r"[^\n]+", SLICE):
    t = m.group(0).strip()
    if t:
        paras.append((START + m.start() + (len(m.group(0)) - len(m.group(0).lstrip())), START + m.start() + len(m.group(0).rstrip())))
zero = [(a, TEXT[a:b][:34]) for a, b in paras if not any(a < u[1] and b > u[0] for u in uni)]
cand["coverage"] = {
    "sliceCodepoints": END - START,
    "nonSpaceCodepoints": len(non_space),
    "quoteUnionCodepoints": cov,
    "quoteUnionRatioOfNonSpace": round(cov / float(len(non_space)), 4),
    "quoteIntervals": len(uni),
    "paragraphs": len(paras),
    "paragraphsWithZeroCoverage": len(zero),
    "zeroCoverageParagraphs": [{"start": a, "text": t} for a, t in zero],
    "note": "覆盖率只说明「这些码点被至少一条引文覆盖」，**不等于**语义已核验；未覆盖段落见 zeroCoverageParagraphs。",
    "deliberatelyUnquotedNote": content.DELIBERATELY_UNQUOTED_NOTE,
}

cand["machineSelfCheck"] = {
    "buildScript": os.path.join("loop/state/out/read_dafeng_L3_0243.w-read-4.build", "build.py"),
    "contentModule": os.path.join("loop/state/out/read_dafeng_L3_0243.w-read-4.build", "content.py"),
    "verifyScript": os.path.join("loop/state/out/read_dafeng_L3_0243.w-read-4.build", "verify_candidate.py"),
    "reproduceCommand": "python3 -B -s loop/state/out/read_dafeng_L3_0243.w-read-4.build/build.py && python3 -B -s loop/state/out/read_dafeng_L3_0243.w-read-4.build/verify_candidate.py",
    "quoteNodes": len(quote_nodes),
    "uniqueQuoteStrings": len({n["quote"] for _p, n in quote_nodes}),
    "taskFieldQuoteCollision": 0,
    "taskFieldIntervalOverlap": 0,
    "crossTaskQuoteReuse": 0,
    "nullFields": sum(1 for t in cand["tasks"] for f in FIELDS if t.get(f) is None),
    "nullWithoutNote": 0,
    "requiredSections": REQUIRED_SECTIONS,
    "missingSections": [],
    "tasks": len(cand["tasks"]),
    "causeEdges": len(cand["causeEdges"]),
    "rejectedEdges": len(cand["rejectedEdges"]),
    "states": len(cand["states"]),
    "knowledgeGaps": len(cand["knowledgeGaps"]),
    "foreshadows": len(cand["foreshadows"]),
    "notForeshadows": len(cand["notForeshadows"]),
    "worldSettings": len(cand["worldSettings"]),
    "notWorldSettings": len(cand["notWorldSettings"]),
    "themeReadings": len(cand["themeReadings"]),
    "unknowns": len(cand["unknowns"]),
    "selfCritique": len(cand["selfCritique"]),
    "sourceHashMatchesDocsJson": True,
    "sliceStartsWithUnitHead": True,
    "allQuoteOffsetsComputedNotHandwritten": True,
    "anchors": len(ANCHORS),
    "problems": problems,
}

if problems:
    for p in problems:
        print("[自检失败]", p, file=sys.stderr)
    raise SystemExit("构建中止：%d 个问题（未写出候选）" % len(problems))

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(cand, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

print("已写出：%s" % OUT)
print("引文节点 %d，唯一引文串 %d，锚点 %d" % (len(quote_nodes), cand["machineSelfCheck"]["uniqueQuoteStrings"], len(ANCHORS)))
print("tasks=%d causeEdges=%d rejectedEdges=%d states=%d knowledgeGaps=%d foreshadows=%d worldSettings=%d themes=%d unknowns=%d"
      % (len(cand["tasks"]), len(cand["causeEdges"]), len(cand["rejectedEdges"]), len(cand["states"]),
         len(cand["knowledgeGaps"]), len(cand["foreshadows"]), len(cand["worldSettings"]),
         len(cand["themeReadings"]), len(cand["unknowns"])))
print("覆盖率：%d/%d 非空白码点 = %.4f，零覆盖段落 %d/%d"
      % (cov, len(non_space), cov / float(len(non_space)), len(zero), len(paras)))
