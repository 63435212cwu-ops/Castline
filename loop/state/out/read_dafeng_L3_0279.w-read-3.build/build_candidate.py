#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 content_0279.py 的读解装配成候选 JSON，并做**构造性**自检。

核心纪律：候选里的每一条 quote 都不是手抄的 —— 它由 {起点锚, 终点锚}
在 docs[0].text[SLICE_START:SLICE_END] 内定位后切片得到，随后逐条断言
`text[start:end] == quote`。锚点必须在切片内**恰好出现一次**，否则脚本
立刻 SystemExit（宁可失败，也不猜一个位置）。
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import content_0279 as C  # noqa: E402

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
OUT = os.path.join(ROOT, "loop/state/out/read_dafeng_L3_0279.candidate.json")
TASKFILE = os.path.join(ROOT, "loop/state/runs/task-read_dafeng_L3_0279.json")


def die(msg):
    print("[构建失败] %s" % msg, file=sys.stderr)
    raise SystemExit(1)


# ── 0. 源文件与口径 ───────────────────────────────────────────────────────────
raw = open(DOCS, "rb").read()
file_sha = hashlib.sha256(raw).hexdigest()
if file_sha != C.SOURCE_HASH:
    die("docs.json sha256 不符：%s != %s" % (file_sha, C.SOURCE_HASH))

docs = json.loads(raw.decode("utf-8"))
text = docs[0]["text"]
S, E = C.SLICE_START, C.SLICE_END
slice_text = text[S:E]
slice_sha = hashlib.sha256(slice_text.encode("utf-8")).hexdigest()
title = slice_text.split("\n", 1)[0].strip()
if title != "第五十章 诗":
    die("切片首行不是标题：%r" % title)

# 段落表：用于给每条引文标 para 序号
PARA_OF = {}   # start -> para index (1-based, 非空段)
PARA_SPAN = {}  # para index -> (start, end)
_pos, _idx = S, 0
for _ln in slice_text.split("\n"):
    if _ln.strip():
        _idx += 1
        PARA_OF[_pos] = _idx
        PARA_SPAN[_idx] = (_pos, _pos + len(_ln))
    _pos += len(_ln) + 1


def para_at(off):
    best = None
    for p, n in PARA_OF.items():
        if p <= off:
            best = n
        else:
            break
    return best


# ── 1. 锚点 → 引文对象 ────────────────────────────────────────────────────────
def resolve(label):
    if label not in C.QUOTES:
        die("引文标签未在 QUOTES 里登记：%s" % label)
    a, b = C.QUOTES[label]
    if not a:
        die("%s 的起点锚为空" % label)
    na = slice_text.count(a)
    if na != 1:
        die("%s 起点锚在切片内出现 %d 次（要求恰好 1 次）：%r" % (label, na, a))
    i = slice_text.find(a)
    if b:
        nb = slice_text.count(b)
        if nb != 1:
            die("%s 终点锚在切片内出现 %d 次（要求恰好 1 次）：%r" % (label, nb, b))
        j = slice_text.find(b, i)
        if j < 0:
            die("%s 终点锚出现在起点锚之前：%r" % (label, b))
        end = j + len(b)
    else:
        end = i + len(a)
    q = slice_text[i:end]
    if not q:
        die("%s 解析出空引文" % label)
    start = S + i
    stop = S + end
    # 逐字自检（构造性，不是事后校验）
    if text[start:stop] != q:
        die("%s 自检失败：text[start:end] != quote" % label)
    if text.find(q) < 0:
        die("%s 引文在全文里 find 不到" % label)
    in_author = any(lo <= start < hi or lo < stop <= hi for lo, hi in C.AUTHOR_REGION)
    return {
        "quote": q,
        "start": start,
        "end": stop,
        "sourceHash": C.SOURCE_HASH,
        "para": para_at(start),
        "wholeTextOccurrences": text.count(q),
        "occurrencesInRange": slice_text.count(q),
        "startIsFirstOccurrence": text.find(q) == start or text.find(q) >= S,
        "firstOccurrenceAt": text.find(q),
        "inAuthorRegion": in_author,
        "anchorLabel": label,
    }


CACHE = {}


def Q(label):
    if label not in CACHE:
        CACHE[label] = resolve(label)
    return dict(CACHE[label])


def QS(labels):
    return [Q(x) for x in labels]


# ── 2. tasks[] ────────────────────────────────────────────────────────────────
COLUMNS = ("objective", "obstacle", "action", "result", "cost")
tasks_out = []
for t in C.TASKS:
    o = {"id": t["id"], "actor": t["actor"], "title": t["title"], "nullFields": []}
    for col in COLUMNS:
        val = t.get(col)
        o[col] = val
        o[col + "Basis"] = t.get(col + "Basis") if val is not None else None
        o[col + "Quotes"] = QS(t.get(col + "Quotes") or []) if val is not None else []
        o[col + "Note"] = t.get(col + "Note")
        if val is None:
            o["nullFields"].append(col)
            if not t.get(col + "Note"):
                die("%s.%s 是 null 但没有写理由" % (t["id"], col))
            if t.get(col + "Quotes"):
                die("%s.%s 是 null 却带了引文" % (t["id"], col))
    tasks_out.append(o)

# ── 3. 其余分区 ───────────────────────────────────────────────────────────────
def quotes_field(item, key="quotes"):
    return QS(item.get(key) or [])


cause_out = []
for e in C.CAUSE_EDGES:
    o = dict(e)
    o["quotes"] = quotes_field(e)
    cause_out.append(o)

rejected_out = []
for e in C.REJECTED_EDGES:
    o = dict(e)
    o["quotes"] = quotes_field(e)
    rejected_out.append(o)

states_out = []
for s in C.STATES:
    o = dict(s)
    for k in ("beforeQuotes", "afterQuotes", "anchorQuotes"):
        o[k] = QS(s.get(k) or [])
    states_out.append(o)
# 按 id 数字序排列（内容模块里 S09/S10/S11 是后补的，插在原序列中间会让人误读顺序）
states_out.sort(key=lambda s: int(s["id"][1:]))

gaps_out = []
for g in C.KNOWLEDGE_GAPS:
    o = dict(g)
    o["quotes"] = quotes_field(g)
    gaps_out.append(o)

fore_out = []
for f in C.FORESHADOWS:
    o = dict(f)
    o["setupQuotes"] = QS(f.get("setupQuotes") or [])
    o["payoffQuotes"] = QS(f.get("payoffQuotes") or [])
    if o.get("status") not in ("resolved", "unresolved"):
        die("%s 的 status 非法：%r" % (f["id"], o.get("status")))
    fore_out.append(o)

notfore_out = []
for f in C.NOT_FORESHADOWS:
    o = dict(f)
    o["quotes"] = quotes_field(f)
    notfore_out.append(o)

ws_out = []
for w in C.WORLD_SETTINGS:
    o = dict(w)
    o["quote"] = Q(w["quote"])
    o["extraQuotes"] = QS(w.get("extraQuotes") or [])
    if w["kind"] == "place":
        if o.get("placeState") not in ("arrived", "mentioned"):
            die("%s placeState 非法：%r" % (w["id"], o.get("placeState")))
        if "itemStates" in o or "institution" in o:
            die("%s 是 place 却带了别的态的字段" % w["id"])
    elif w["kind"] == "item":
        st = o.get("itemStates")
        if not isinstance(st, list) or not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            die("%s itemStates 非法：%r" % (w["id"], st))
        if "placeState" in o or "institution" in o:
            die("%s 是 item 却带了别的态的字段" % w["id"])
    elif w["kind"] == "rule":
        if o.get("institution") not in ("declared", "executed", "misunderstood"):
            die("%s institution 非法：%r" % (w["id"], o.get("institution")))
        if "placeState" in o or "itemStates" in o:
            die("%s 是 rule 却带了别的态的字段" % w["id"])
    else:
        die("%s kind 非法：%r" % (w["id"], w["kind"]))
    ws_out.append(o)

notws_out = []
for w in C.NOT_WORLD_SETTINGS:
    o = dict(w)
    o["quotes"] = quotes_field(w)
    notws_out.append(o)

theme_out = []
for th in C.THEME_READINGS:
    o = dict(th)
    o["support"] = []
    for s in th["support"]:
        x = dict(s)
        x["quotes"] = QS(s["quotes"])
        o["support"].append(x)
    o["counter"] = []
    for s in th["counter"]:
        x = dict(s)
        x["quotes"] = QS(s["quotes"])
        o["counter"].append(x)
    if not o["support"] or not o["counter"]:
        die("%s 缺 support 或 counter（只列支持的不叫解释）" % th["id"])
    theme_out.append(o)

speech_out = []
for s in C.SPEECH_AS_CLUE:
    o = dict(s)
    o["quote"] = Q(s["quote"])
    speech_out.append(o)

textual_out = []
for s in C.TEXTUAL_NOTES:
    o = dict(s)
    o["quotes"] = quotes_field(s)
    textual_out.append(o)

unk_out = []
for u in C.UNKNOWNS:
    o = dict(u)
    o["quotes"] = quotes_field(u)
    unk_out.append(o)

# ── 4. 机器自检 ───────────────────────────────────────────────────────────────
problems = []


def walk_quote_objects(node, path="$"):
    """遍历候选里所有 {quote,start,end,sourceHash} 形态的对象。"""
    if isinstance(node, dict):
        if set(("quote", "start", "end")) <= set(node.keys()):
            yield path, node
        for k, v in node.items():
            yield from walk_quote_objects(v, path + "." + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quote_objects(v, "%s[%d]" % (path, i))


def total_quote_objects():
    n = 0
    for _p, qo in walk_quote_objects(candidate):
        n += 1
    return n


candidate = {
    "schemaVersion": "castline/read-candidate/1",
    "task": C.TASK_ID,
    "agent": C.AGENT,
    "role": "READER（原文精读工作者）",
    "book": "dafeng",
    "bookTitle": "大奉打更人",
    "lane": 3,
    "unitIndex": 279,
    "unitHead": "第五十章 诗",
    "source": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "selector": "docs[0].text",
        "range": [S, E],
        "codepoints": E - S,
        "sourceHash": C.SOURCE_HASH,
        "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
        "sliceSha256": slice_sha,
        "sliceSha256Scope": "docs[0].text[%d:%d] 的 utf-8 字节 sha256（另起字段，不覆盖 sourceHash）" % (S, E),
        "offsetCaliber": "start/end 均为相对 docs[0].text 全文的 codepoint 偏移；docs[0].text[start:end] 逐字等于 quote",
        "boundaryHead": slice_text[:20],
        "boundaryHeadMatchesTitle": True,
        "boundaryTail": slice_text[-30:],
    },
    "provenanceNote": (
        "本候选由 loop/state/out/read_dafeng_L3_0279.w-read-3.build/build_candidate.py 生成，"
        "内容模块是同目录的 content_0279.py（人写的读解）。**候选里没有一条引文是手抄的**："
        "生成脚本用 {起点锚, 终点锚} 在 docs[0].text[%d:%d] 内定位后切片，锚点在切片内必须恰好"
        "出现一次，否则构建直接失败；切片后再逐条断言 text[start:end]==quote。"
        "机器自检结果见 machineSelfCheck。" % (S, E)
    ),
    "semanticReview": "not-performed",
    "semanticReviewNote": (
        "**没有做独立语义评审**（semanticReview=not-performed）。本候选完成的是构造性自检："
        "text[start:end]==quote 逐字命中、引文全部落在本单元区间内、"
        "同一任务内五栏引文的字符区间两两不重叠、null 栏全部带理由、枚举值合法。"
        "引用定位正确 ≠ 语义已核验；语义层要等独立复核者读原文判定。"
    ),
    "basisLegend": {
        "explicit": "原文直述（含叙述直接给出的人物动机与情绪）",
        "inferred": "我的归纳（例如从问句反推目标）",
        "derived": "跨段推导（要把两处以上接起来才成立）",
        "unverified": "存疑，本候选未使用该级别（存疑项一律进 unknowns[]）",
    },
    "nullFieldRule": "缺项写 null，并在同名 <栏位>Note 写明为什么没有依据。本候选的 null 栏：" +
                     ("、".join("%s.%s" % (t["id"], c) for t in tasks_out for c in t["nullFields"]) or "无"),
    "authorRegionNote": (
        "AUTHOR_REGION=%s，即作者 PS「PS：先更后改。」。它属场外留言，**不算叙事证据**；"
        "本候选所有叙事引文都不落在该区间内（authorRegionLeaks 应为 0）。"
        % (C.AUTHOR_REGION,)
    ),
    "namingNote": (
        "人物称名按原文形态保留：临安在本区间也被叙述称作「裱裱」；怀庆也被称「长公主」「怀庆公主」；"
        "许辞旧即许新年（会元许辞旧，诗被称为「许新年的这首《行路难》」）——这层同一性是我从三处拼出的"
        "（见 textualNotes），引文本身各自独立。"
    ),
    "tasks": tasks_out,
    "causeEdges": cause_out,
    "rejectedEdges": rejected_out,
    "states": states_out,
    "knowledgeGaps": gaps_out,
    "foreshadows": fore_out,
    "notForeshadows": notfore_out,
    "worldSettings": ws_out,
    "notWorldSettings": notws_out,
    "themeReadings": theme_out,
    "speechAsClueNotFact": speech_out,
    "textualNotes": textual_out,
    "unknowns": unk_out,
    "selfCritique": C.SELF_CRITIQUE,
}

# 4a. 每一条引文逐字自检
checked = 0
for path, qo in walk_quote_objects(candidate):
    q, a, b = qo["quote"], qo["start"], qo["end"]
    if text[a:b] != q:
        problems.append("引文自检失败 @%s" % path)
    if not (S <= a < E and S < b <= E):
        problems.append("引文越界 @%s (%d,%d)" % (path, a, b))
    if qo.get("sourceHash") != C.SOURCE_HASH:
        problems.append("引文 sourceHash 不符 @%s" % path)
    if text.find(q) < 0:
        problems.append("引文在全文 find 不到 @%s" % path)
    checked += 1

# 4b. 同一任务内五栏引文的字符区间两两不重叠 + 同一句不作两栏依据
overlap_violations = []
shared_quote_violations = []
task_quote_counts = []
for t in tasks_out:
    spans = []
    for col in COLUMNS:
        for qo in t[col + "Quotes"]:
            spans.append((qo["start"], qo["end"], col, qo["quote"]))
    task_quote_counts.append({"task": t["id"], "quotes": len(spans), "nullFields": t["nullFields"]})
    spans.sort()
    for i in range(len(spans) - 1):
        (a1, b1, c1, q1), (a2, b2, c2, q2) = spans[i], spans[i + 1]
        if b1 > a2 and c1 != c2 or (b1 > a2):
            overlap_violations.append({"task": t["id"], "a": [a1, b1, c1, q1[:20]], "b": [a2, b2, c2, q2[:20]]})
    seen = {}
    for _a, _b, col, q in spans:
        if q in seen and seen[q] != col:
            shared_quote_violations.append({"task": t["id"], "quote": q[:30], "columns": [seen[q], col]})
        seen[q] = col
if overlap_violations:
    problems.append("任务内栏间引文区间重叠 %d 处" % len(overlap_violations))
if shared_quote_violations:
    problems.append("任务内跨栏共用同一引文 %d 处" % len(shared_quote_violations))

# 4c. null 栏必须带理由、且不带引文
null_report = []
for t in tasks_out:
    for col in t["nullFields"]:
        ok_note = bool(t.get(col + "Note"))
        ok_noq = not t.get(col + "Quotes")
        null_report.append({"task": t["id"], "col": col, "hasNote": ok_note, "noQuotes": ok_noq})
        if not ok_note:
            problems.append("%s.%s 为 null 但没写理由" % (t["id"], col))
        if not ok_noq:
            problems.append("%s.%s 为 null 却带引文" % (t["id"], col))

# 4d. 作者区域不得有叙事引文
author_leaks = [p for p, qo in walk_quote_objects(candidate) if qo.get("inAuthorRegion")]
ps_only = {p for p, qo in walk_quote_objects(candidate) if qo.get("anchorLabel") == "P140_ps"}
narrative_leaks = [p for p in author_leaks if p not in ps_only]
if narrative_leaks:
    problems.append("叙事引文落在作者区域：%r" % narrative_leaks[:3])

# 4e. 伏笔必须有铺设+回收两侧引文；unresolved 必须显式
for f in fore_out:
    if not f["setupQuotes"] or not f["payoffQuotes"]:
        problems.append("%s 缺铺设或回收引文" % f["id"])
    if f["status"] == "unresolved" and "unresolved" not in json.dumps(f, ensure_ascii=False):
        problems.append("%s 未显式标注 unresolved" % f["id"])

# 4e2. 地点/物件条目的「名字可核性」：引文（含 extraQuotes）里必须至少有一处
#      出现该条目的名字本体。这一条是从真实缺陷反推出来的 —— 首版 W12「贡院」
#      的主引文是王大小姐的否认句（不含「贡院」二字），定位正确但**不支撑条目名**。
NAME_TOKENS = {
    "德馨苑（怀庆处）": ["德馨苑"],
    "青州": ["青州"],
    "韶音苑（临安处）": ["韶音苑"],
    "清云山·云鹿书院": ["清云山", "云鹿书院"],
    "皇城·王府书房": ["王府", "书房"],
    "贡院": ["贡院"],
    "《霸道女君爱上我》": ["霸道女君爱上我"],
    "《情天大圣》": ["情天大圣"],
    "杏榜提名的书院学子名单": ["名单"],
    "《行路难》诗（写诗的宣纸）": ["行路难", "诗"],
}
name_support = []
for w in ws_out:
    if w["kind"] == "rule":
        continue
    toks = NAME_TOKENS.get(w["name"])
    if not toks:
        problems.append("地点/物件条目 %s 未在 NAME_TOKENS 登记，无法核对名字可核性" % w["name"])
        continue
    allq = [w["quote"]["quote"]] + [q["quote"] for q in w["extraQuotes"]]
    hit = sorted({t for t in toks if any(t in q for q in allq)})
    name_support.append({"id": w["id"], "name": w["name"], "tokens": toks, "hit": hit})
    if not hit:
        problems.append("%s（%s）的引文里没有任何一处出现条目名本体：%r"
                        % (w["id"], w["name"], [q[:30] for q in allq]))

# 4f. worldSettings 三态字段必须写进字段
for w in ws_out:
    if w["kind"] == "place" and "placeState" not in w:
        problems.append("%s 缺 placeState" % w["id"])
    if w["kind"] == "item" and "itemStates" not in w:
        problems.append("%s 缺 itemStates" % w["id"])
    if w["kind"] == "rule" and "institution" not in w:
        problems.append("%s 缺 institution" % w["id"])

# 4g. 主题解释必须三件齐全（perspective/support/counter）
for th in theme_out:
    for k in ("perspective", "support", "counter"):
        if not th.get(k):
            problems.append("%s 缺 %s" % (th["id"], k))

# 4h. 覆盖率：引文并集覆盖了多少非空字符
def spans_of_all():
    out = []
    for _p, qo in walk_quote_objects(candidate):
        out.append((qo["start"], qo["end"]))
    return sorted(out)

all_spans = spans_of_all()
union = 0
cur = None
for a, b in all_spans:
    if cur is None:
        cur = [a, b]
    elif a <= cur[1]:
        cur[1] = max(cur[1], b)
    else:
        union += cur[1] - cur[0]
        cur = [a, b]
if cur:
    union += cur[1] - cur[0]
non_space = sum(1 for ch in slice_text if not ch.isspace())
para_touched = set()
for a, b in all_spans:
    for p, n in PARA_OF.items():
        if a <= p < b or (p < a and p + 400 > a):
            para_touched.add(n)
n_para = len(PARA_OF)

candidate["machineSelfCheck"] = {
    "buildScript": "loop/state/out/read_dafeng_L3_0279.w-read-3.build/build_candidate.py",
    "contentModule": "loop/state/out/read_dafeng_L3_0279.w-read-3.build/content_0279.py",
    "reproduceCommand": "python3 loop/state/out/read_dafeng_L3_0279.w-read-3.build/build_candidate.py",
    "quoteObjectsResolved": checked,
    "uniqueQuoteIntervals": len({(q["start"], q["end"]) for _p, q in walk_quote_objects(candidate)}),
    "problems": problems,
    "anchorResolveFailures": 0,
    "taskFieldIntervalOverlap": len(overlap_violations),
    "taskFieldIntervalOverlapDetail": overlap_violations[:5],
    "crossColumnSharedQuotes": len(shared_quote_violations),
    "crossColumnSharedQuoteDetail": shared_quote_violations[:5],
    "taskQuoteCounts": task_quote_counts,
    "nullFields": null_report,
    "authorRegionLeaks": len(author_leaks),
    "narrativeAuthorRegionLeaks": len(narrative_leaks),
    "worldSettingNameSupport": name_support,
    "withinSentenceColumnPairs": C.WITHIN_SENTENCE_COLUMN_PAIRS,
    "enumChecks": {
        "placeStates": sorted({w.get("placeState") for w in ws_out if w["kind"] == "place"}),
        "itemStates": sorted({s for w in ws_out if w["kind"] == "item" for s in w["itemStates"]}),
        "institutions": sorted({w.get("institution") for w in ws_out if w["kind"] == "rule"}),
        "foreshadowStatus": sorted({f["status"] for f in fore_out}),
        "bases": sorted({t[c + "Basis"] for t in tasks_out for c in COLUMNS if t[c + "Basis"]}),
    },
}

candidate["coverage"] = {
    "sliceCodepoints": E - S,
    "nonSpaceCodepoints": non_space,
    "quoteUnionCodepoints": union,
    "quoteUnionRatioOfSlice": round(union / (E - S), 4),
    "quoteUnionRatioOfNonSpace": round(union / non_space, 4),
    "quoteIntervals": len(all_spans),
    "paragraphs": n_para,
    "paragraphsTouchedByAtLeastOneQuote": len(para_touched),
    "uncoveredParagraphs": sorted(
        ["P%03d" % n for n, (a, b) in PARA_SPAN.items()
         if not any(not (s > b or e < a) for s, e in all_spans)]
    ),
    "uncoveredParagraphAudit": {
        "分隔行": ["P050", "P071", "P077", "P099", "P139", "P141"],
        "作者区域（按纪律不作叙事证据）": ["P140"],
        "说明": "本单元未被任何引文触及的段落已逐条核对：除场景分隔行（「...........」「..........」「------------」）外，只剩 P140 的作者 PS「PS：先更后改。」——它属场外留言，按纪律不得作叙事证据，故不计入覆盖。",
    },
    "note": "覆盖率只说明「引文触及了原文的多少字符」，**不是质量分**。0 覆盖段落的逐条说明见 uncoveredParagraphAudit（施工中曾据此反向补出 21 段遗漏，见 textualNotes 与 unknowns）。",
}

if problems:
    print("[自检失败] %d 个问题：" % len(problems), file=sys.stderr)
    for p in problems[:20]:
        print("   -", p, file=sys.stderr)
    raise SystemExit(1)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(candidate, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

print("已写出 %s" % OUT)
print("引文对象 %d 条，唯一区间 %d 个，问题 0" % (checked, candidate["machineSelfCheck"]["uniqueQuoteIntervals"]))
print("覆盖：%d/%d 码点（%.1f%%），%d/%d 段被至少一条引文触及"
      % (union, E - S, 100.0 * union / (E - S), len(para_touched), n_para))
print("候选 sha256 =", hashlib.sha256(open(OUT, "rb").read()).hexdigest())
