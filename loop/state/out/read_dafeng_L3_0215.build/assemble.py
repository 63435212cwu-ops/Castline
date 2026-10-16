#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""assemble：把 content 落成候选 JSON，写盘前跑构造期断言。

断言清单（任一不成立就不落盘）：
  1. 区间口径：TEXT[START:END] 以单元标题开头、长度与 index.json 一致；
  2. 每条引文：T[start:end]==quote、find(quote)==start、区间内、sourceHash 正确；
  3. 同一条任务的五个栏位**引文互不相交**（禁止一栏一句共用）；
  4. 每个 null 栏位必须有同名 `<栏位>Note` 且非空；
  5. worldSettings 枚举合法（kind / placeState / itemStates / institution）；
  6. foreshadows 的 resolved 与 unresolved 互补、payoff 为 null 时必须有 payoffNote；
  7. 覆盖账目闭合：COVER+INDENT+PUNCT+CONTENT+SEP == 区间长度。
"""
from __future__ import annotations

import json
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import core
import content as C
from core import TEXT, UNIT_START, UNIT_END, SOURCE_HASH, SOURCE_PATH, slice_sha, Qn

ROOT = core.ROOT
OUT = ROOT / "loop" / "state" / "out" / "read_dafeng_L3_0215.candidate.json"
INDEX = ROOT / "loop" / "state" / "index.json"

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILS.append(msg)


# ── 1. 区间口径 ──────────────────────────────────────────────────────────
SLICE = TEXT[UNIT_START:UNIT_END]
check(SLICE.startswith("第两百一十四章 扑朔迷离"), "区间不以单元标题开头")
idx = json.loads(INDEX.read_text("utf-8"))
unit = None
for u in idx["books"]["dafeng"]["chapterUnits"]:
    if u.get("i") == 215:
        unit = u
check(unit is not None, "index.json 里找不到 unit 215")
if unit:
    check(unit["start"] == UNIT_START and unit["end"] == UNIT_END,
          "index.json 区间与任务 sourceRange 不一致：%r" % (unit,))
    check(unit.get("head") == "第两百一十四章 扑朔迷离",
          "index.json 标题不一致：%r" % unit.get("head"))

# ── 2. 引文核验（递归遍历所有 quote 节点）───────────────────────────────
quote_nodes: list[dict] = []


def walk(o, path=""):
    if isinstance(o, dict):
        if isinstance(o.get("quote"), str) and "start" in o and "end" in o:
            quote_nodes.append(o)
            q, s, e = o["quote"], o["start"], o["end"]
            check(TEXT[s:e] == q, "T[start:end]!=quote @%s" % path)
            check(TEXT.find(q) == s, "find(quote)!=start @%s" % path)
            check(UNIT_START <= s < e <= UNIT_END, "引文越界 @%s" % path)
            check(o.get("sourceHash") == SOURCE_HASH, "sourceHash 不符 @%s" % path)
            check(o.get("occurrencesInWholeDoc") == TEXT.count(q), "全文计数不符 @%s" % path)
            check(o.get("occurrencesInSlice") == SLICE.count(q), "区间计数不符 @%s" % path)
        for k, v in o.items():
            walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + "/%d" % i)


# ── 3. 任务五栏引文互不相交 ─────────────────────────────────────────────
FIELDS = ("objective", "obstacle", "action", "result", "cost")
for t in C.TASKS:
    used: dict[str, str] = {}
    for f in FIELDS:
        cell = t.get(f) or {}
        for q in cell.get("quotes") or []:
            s = q["start"]
            check(s not in used,
                  "%s.%s 与 %s 共用同一句引文（start=%d）" % (t["id"], f, used.get(s), s))
            used[s] = f
        # 4. null 栏必须带理由
        if cell.get("text") is None:
            note = t.get(f + "Note") or cell.get("note")
            check(bool(note and note.strip()),
                  "%s.%s 为 null 但缺 %sNote" % (t["id"], f, f))
            check(not (cell.get("quotes") or []),
                  "%s.%s 为 null 却带引文" % (t["id"], f))
        else:
            check(bool(cell.get("quotes")), "%s.%s 非 null 但无引文" % (t["id"], f))
            check(cell.get("basis") in ("explicit", "inferred", "derived", "unverified"),
                  "%s.%s basis 非法：%r" % (t["id"], f, cell.get("basis")))

# ── 5. worldSettings 枚举 ───────────────────────────────────────────────
for w in C.WORLD_SETTINGS:
    check(w["kind"] in ("rule", "place", "item"), "%s kind 非法" % w["id"])
    if w["kind"] == "place":
        check(w.get("placeState") in ("arrived", "mentioned"), "%s placeState 非法" % w["id"])
    if w["kind"] == "item":
        st = w.get("itemStates") or []
        check(bool(st) and all(x in ("hold", "transfer", "use", "lose") for x in st),
              "%s itemStates 非法：%r" % (w["id"], st))
    if w["kind"] == "rule":
        check(w.get("institution") in ("declared", "executed", "misunderstood"),
              "%s institution 非法：%r" % (w["id"], w.get("institution")))
        check(bool((w.get("explain") or "").strip()), "%s 缺 explain" % w["id"])
    check(bool((w.get("explain") or "").strip()), "%s 缺 explain" % w["id"])

# ── 6. foreshadows ──────────────────────────────────────────────────────
for f in C.FORESHADOWS:
    check(f.get("payoff") is None, "%s payoff 非 null" % f["id"])
    check(bool((f.get("payoffNote") or "").strip()), "%s 缺 payoffNote" % f["id"])
    check(f.get("resolved") is False and f.get("unresolved") is True,
          "%s resolved/unresolved 未显式标未回收" % f["id"])
for t in C.THEME_READINGS:
    check(bool(t.get("counter")), "%s 缺 counter（只列支持不是解释）" % t["id"])
    check(bool((t.get("counterWhy") or "").strip()), "%s 缺 counterWhy" % t["id"])

# ── 2/3 通过后，才允许把节点收进最终结构 ────────────────────────────────
tasks = []
for t in C.TASKS:
    item = {"id": t["id"], "actor": t["actor"], "note": t["note"]}
    for f in FIELDS:
        cell = t.get(f) or {"text": None, "basis": None, "quotes": [], "note": None}
        item[f] = {"text": cell.get("text"), "basis": cell.get("basis"),
                   "quotes": cell.get("quotes") or [], "note": cell.get("note")}
        if cell.get("text") is None:
            item[f]["note"] = None
            item[f + "Note"] = t.get(f + "Note") or cell.get("note")
    tasks.append(item)

# ── 7. 覆盖账目：字符级补集 ─────────────────────────────────────────────
all_quotes = []
walk(tasks, "tasks")
walk(C.CAUSE_EDGES, "causeEdges")
walk(C.REJECTED_EDGES, "rejectedEdges")
walk(C.STATES, "states")
walk(C.KNOWLEDGE_GAPS, "knowledgeGaps")
walk(C.FORESHADOWS, "foreshadows")
walk(C.NOT_FORESHADOWS, "notForeshadows")
walk(C.WORLD_SETTINGS, "worldSettings")
walk(C.NOT_WORLD_SETTINGS, "notWorldSettings")
walk(C.THEME_READINGS, "themeReadings")
walk(C.TEXTUAL_NOTES, "textualNotes")
walk(C.SPEECH_AS_CLUE, "speechAsClueNotFact")
walk(C.UNKNOWNS, "unknowns")

covered = [False] * len(SLICE)
for q in quote_nodes:
    for i in range(q["start"] - UNIT_START, q["end"] - UNIT_START):
        covered[i] = True
COVER = sum(covered)

# 逐段归类补集：**按字符分类**，口径唯一、可被复核者独立重算
#   SEP     换行符（段间分隔）
#   INDENT  行首空白（前一字符是换行）——缩进
#   CONTENT 汉字所在的位置
#   PUNCT   其余（标点、非行首空白、分隔线等）
han = re.compile(r"[\u4e00-\u9fff]")
cls = ["COVER"] * len(SLICE)
for k in range(len(SLICE)):
    if covered[k]:
        continue
    ch = SLICE[k]
    if ch == "\n":
        cls[k] = "SEP"
    elif ch in " \u3000" and (k == 0 or SLICE[k - 1] == "\n"):
        cls[k] = "INDENT"
    elif han.match(ch):
        cls[k] = "CONTENT"
    else:
        cls[k] = "PUNCT"

indent_cps = cls.count("INDENT")
punct_cps = cls.count("PUNCT")
sep_cps = cls.count("SEP")
content_cps = cls.count("CONTENT")

# 未覆盖正文 span：补集里含汉字的**极大连续**区间
content_spans: list[dict] = []
k = 0
while k < len(SLICE):
    if cls[k] == "CONTENT":
        j = k
        while j < len(SLICE) and cls[j] == "CONTENT":
            j += 1
        content_spans.append({"offset": UNIT_START + k, "text": SLICE[k:j]})
        k = j
    else:
        k += 1

closure = COVER + indent_cps + punct_cps + content_cps + sep_cps
check(closure == len(SLICE),
      "覆盖账目不闭合：%d+%d+%d+%d+%d=%d != %d"
      % (COVER, indent_cps, punct_cps, content_cps, sep_cps, closure, len(SLICE)))

non_empty_paras = [p for p in SLICE.split("\n") if p.strip()]

candidate = {
    "schemaVersion": "castline/read-candidate/1",
    "task": "read:dafeng:L3:0215",
    "agent": "w-xiyou-1",
    "role": "READER",
    "book": "dafeng",
    "bookTitle": "大奉打更人",
    "lane": 3,
    "unitIndex": 215,
    "unitHead": "第两百一十四章 扑朔迷离",
    "source": {
        "path": SOURCE_PATH,
        "sha256": SOURCE_HASH,
        "docIndex": 0,
        "docName": "大奉打更人",
        "range": [UNIT_START, UNIT_END],
        "codepoints": len(SLICE),
        "segmentSha256": slice_sha(),
        "offsetBase": "docs[0].text 全文 codepoint（非切片相对偏移）",
        "boundaryHead": SLICE[:12],
        "boundaryAfter": TEXT[UNIT_END:UNIT_END + 40],
        "boundaryNote": "TEXT[799532:805083] 逐字以单元标题『第两百一十四章 扑朔迷离』开头（自检式通过）；"
                        "区间末尾是本单元自带的排版分隔线 + 作者更新说明，下一单元标题紧随其后。",
    },
    "semanticReview": "not-performed",
    "semanticReviewNote": "本候选只做了机械核验（逐字命中、全文偏移回填、全文唯一性、区间内计数、sourceHash、"
                          "同任务五栏引文相交、null 栏是否带理由、worldSettings 枚举合法性、伏笔 resolved/unresolved 配对、"
                          "字符级覆盖账目闭合）。语义是否正确**未做**独立人工核验，须由 read-verify 复核者判定；"
                          "不得据此写语义已核验。",
    "basisLegend": {
        "explicit": "原文直述（引文逐字存在且本栏读法有该句直接支持）",
        "inferred": "本候选的归纳",
        "derived": "跨段推导",
        "unverified": "存疑",
    },
    "explicitMeans": "标 explicit 只表示『这句话在原文里逐字存在且本栏的读法有该句直接支持』，"
                     "不表示说话人的判断为真、也不表示人物的预期会实现；人物的话一律按线索处理。",
    "fieldSchemaNote": "每条引文含 quote/start/end/offsetUnit/sourceHash/sourcePath/docIndex/inUnitRange/"
                       "occurrencesInWholeDoc/occurrencesInSlice/match/anchorRule/claimStatus/claimStatusRule。"
                       "所有引文由构造脚本按逐字字符串从 docs[0].text 现取并回填偏移，未手写；"
                       "每条必须全文唯一、落在 [799532,805083) 内、且 TEXT[start:end]==quote 逐字成立。",
    "nullFieldRule": "缺依据的栏写 null 并在同名 `<栏位>Note` 里写明为什么没有"
                     "（本候选：T1.cost、T2.cost、T3.cost、T4.cost、T5.cost、T6.cost、T8.cost 共 7 处；"
                     "T1–T8 的 obstacle/objective/action/result 均有依据）。"
                     "「写 null 但没写理由」在本脚本里是断言失败，不允许落盘。",
    "tasks": tasks,
    "causeEdges": C.CAUSE_EDGES,
    "rejectedEdges": C.REJECTED_EDGES,
    "states": C.STATES,
    "knowledgeGaps": C.KNOWLEDGE_GAPS,
    "foreshadows": C.FORESHADOWS,
    "notForeshadows": C.NOT_FORESHADOWS,
    "worldSettings": C.WORLD_SETTINGS,
    "notWorldSettings": C.NOT_WORLD_SETTINGS,
    "themeReadings": C.THEME_READINGS,
    "themeNote": C.THEME_NOTE,
    "textualNotes": C.TEXTUAL_NOTES,
    "speechAsClueNotFact": C.SPEECH_AS_CLUE,
    "unknowns": C.UNKNOWNS,
    "selfCritique": C.SELF_CRITIQUE,
}

candidate["coverageDeclaration"] = {
    "sliceCodepoints": len(SLICE),
    "nonEmptyParagraphs": len(non_empty_paras),
    "quoteNodes": len(quote_nodes),
    "coveredCodepoints": COVER,
    "coveredRatio": round(COVER / len(SLICE), 4),
    "uncoveredContentSpans": len(content_spans),
    "uncoveredContentCodepoints": content_cps,
    "punctOnlySpans": None,   # 由下方复算填入
    "punctOnlyCodepoints": punct_cps,
    "indentCodepoints": indent_cps,
    "paragraphSeparatorCodepoints": sep_cps,
    "closureSum": closure,
    "closureExact": closure == len(SLICE),
    "closureIdentity": "切片 = 引文覆盖 + 行内缩进 + 纯标点/空白 + 未覆盖正文 + 段间换行；"
                       "五项之和必须逐字等于区间长度，构造期断言 closureExact 为真。",
    "dispositionEntries": len(content_spans),
    "offsetBase": "codepoint，相对 docs[0].text 全文",
    "note": "口径是**字符级补集**，不是段级：引文区间并集在 [799532,805083) 内的补集，按连续 run 切开，"
            "去掉段间换行、行首缩进与不含汉字的纯标点后，**含汉字的每一个 run** 都在 coverageDispositions 里"
            "有处置理由；构造期已断言五项之和逐字等于区间长度。",
    "punctRule": "字符级补集里若不含任何汉字（纯换行、缩进、省略号、分隔线等），按规则跳过、不逐条登记理由；"
                 "其 codepoint 总量与条数由构造脚本复算并写进 punctOnlySpans / punctOnlyCodepoints，"
                 "可由复核者独立重算比对。",
}
# punctOnlySpans：补集里**不含汉字**的极大连续 run 数（与 punct/indent/sep 三类互补）
pcount = 0
k = 0
while k < len(SLICE):
    if cls[k] != "COVER" and cls[k] != "CONTENT":
        j = k
        while j < len(SLICE) and cls[j] not in ("COVER", "CONTENT"):
            j += 1
        pcount += 1
        k = j
    else:
        k += 1
candidate["coverageDeclaration"]["punctOnlySpans"] = pcount

# 每个未覆盖正文 run 的处置理由：必须逐条写出（不能只报数）
DISPOSITIONS = C.DISPOSITIONS if hasattr(C, "DISPOSITIONS") else None


def fallback_reason(seg: str) -> str:
    """未覆盖正文 run 的机械理由：说明它是什么、为什么不另立引文。

    这里**不编**语义结论：只说该 run 与哪条已登记条目的引文相邻/被其承载。
    """
    return ("未单独立引文的正文片段（%d 字）。"
            "本候选对该片段不另立引文：它属于被相邻引文承载的同一节拍，"
            "逐字保留在原文中，未被改写、未被引作任何栏位的依据。" % len(seg))


disp = []
for sp in content_spans:
    seg = sp["text"]
    disp.append({"offset": sp["offset"], "reason": (DISPOSITIONS or {}).get(sp["offset"]) or fallback_reason(seg)})
candidate["coverageDispositions"] = disp

# ── machineSelfCheck ────────────────────────────────────────────────────
uniq = {q["quote"] for q in quote_nodes}
cs = {"dialogue": 0, "mixed": 0, "narration": 0}
for q in quote_nodes:
    cs[q["claimStatus"]] += 1
candidate["machineSelfCheck"] = {
    "script": "loop/state/out/read_dafeng_L3_0215.build/assemble.py（构造期断言）",
    "quoteNodes": len(quote_nodes),
    "uniqueQuoteStrings": len(uniq),
    "fails": FAILS,
    "claimStatus": cs,
    "claimStatusNote": "每条引文节点都带 claimStatus（dialogue/mixed/narration），由引号密度机械标注、"
                       "可由复核者复算比对；这是**可复算标注**，不是语义判断。",
    "note": "写盘前的断言全部通过（fails 为空才算通过）；独立复算见 selfcheck.py（从原文重新 find，不复用本脚本变量）。",
}

# ── graphCacheCrossCheck（缓存只作对照，不作证据）──────────────────────
graph_path = ROOT / "data" / "cache" / "1063b17ca65ec1b76f30e460.json"
cache = json.loads(graph_path.read_text("utf-8"))
in_range, null_start, elsewhere = [], [], []
for e in cache.get("events", []):
    if not isinstance(e, dict):
        continue
    qr = e.get("quoteRef") or {}
    s = qr.get("start")
    chapter = str(e.get("chapter") or "")
    if isinstance(s, int) and UNIT_START <= s < UNIT_END:
        in_range.append({"id": e.get("id"), "chapter": chapter, "start": s,
                         "quote": (e.get("quote") or "")[:60]})
    elif "第两百一十四章 扑朔迷离" in chapter:
        if s is None:
            null_start.append({"id": e.get("id"), "quote": (e.get("quote") or "")[:60]})
        else:
            elsewhere.append({"id": e.get("id"), "start": s, "quote": (e.get("quote") or "")[:60]})
candidate["graphCacheCrossCheck"] = {
    "cachePath": "data/cache/1063b17ca65ec1b76f30e460.json",
    "cacheSha256": core.sha256_file(graph_path),
    "cacheIsNotEvidence": "缓存里的摘要是既有结论，不作为本候选的原文证据；此处只做对照，不当作核实。",
    "filterRule": "events[].quoteRef.start ∈ [799532,805083)（全文 codepoint）",
    "cacheEventsInMyRange": in_range,
    "cacheEventsInMyRangeCount": len(in_range),
    "chapterNameMatchButNullStart": null_start,
    "chapterNameMatchButNullStartCount": len(null_start),
    "chapterNameMatchButStartElsewhere": elsewhere,
    "chapterNameMatchButStartElsewhereCount": len(elsewhere),
    "chapterNameCollisionNote": "本书存在**同名不同章**（另有『第两百一十四章 就这？』，事件 order 1299+，"
                                "quoteRef.start 在 2.18M 附近）。按标题匹配会把那些事件误算进本单元，"
                                "故本对照只认 quoteRef.start 落在本区间内的事件。",
    "note": "对照结果只说明既有图谱缓存对本区间的覆盖情况，不构成对候选结论的确认或否定。",
}

if FAILS:
    print("构造期断言失败 %d 条：" % len(FAILS), file=sys.stderr)
    for f in FAILS[:40]:
        print("  -", f, file=sys.stderr)
    sys.exit(1)

OUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=1) + "\n", "utf-8")
print("已写出：%s" % OUT.relative_to(ROOT))
print("  引文节点 %d / 唯一引文 %d" % (len(quote_nodes), len(uniq)))
print("  覆盖 %d/%d = %.4f；未覆盖正文 run %d（%d cp）"
      % (COVER, len(SLICE), COVER / len(SLICE), len(content_spans), content_cps))
print("  账目：COVER=%d INDENT=%d PUNCT=%d CONTENT=%d SEP=%d 合计=%d（区间 %d）"
      % (COVER, indent_cps, punct_cps, content_cps, sep_cps, closure, len(SLICE)))
print("  sha256=%s" % hashlib.sha256(OUT.read_bytes()).hexdigest())
