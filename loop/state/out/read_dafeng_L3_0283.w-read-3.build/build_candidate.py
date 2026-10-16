# -*- coding: utf-8 -*-
"""Build loop/state/out/read_dafeng_L3_0283.candidate.json from content_0283.py.

设计要点（为什么要有这个脚本，而不是手写 JSON）：
  · 候选里**没有一条引文是手抄进 JSON 的**。content_0283.py 里每条引文只写
    「逐字原文子串 + 该子串在本单元切片内的第几次出现（occ）」；本脚本用
    `slice.find(q, cursor)` 在**切片内**定位，取第 occ 次出现，切片得到
    start/end（相对 docs[0].text 全文的 codepoint 偏移），再断言
    `docs[0].text[start:end] == q` 逐字成立。找不到、出现次数不够、
    越出本单元区间 ⇒ 直接抛错，构建失败（不产出半个候选）。
  · 同一段落里出现两次的句子（例如「“正是贫僧。”」）必须显式给 occ，
    否则默认要求在本单元切片内**唯一**——歧义会让偏移悄悄落到错的位置。
  · 全部机检在 build 末尾跑一遍（见 selfcheck()），problems 非空即退出码 1。

复现命令：python3 loop/state/out/read_dafeng_L3_0283.w-read-3.build/build_candidate.py
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)

import content_0283 as C  # noqa: E402

DOCS_PATH = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
OUT_PATH = os.path.join(ROOT, "loop", "state", "out", "read_dafeng_L3_0283.candidate.json")
TASK_PATH = os.path.join(ROOT, "loop", "state", "runs", "task-read_dafeng_L3_0283.json")
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

START, END = 1206041, 1212202
# 作者区域（PS + 单章说明 + 其后的分隔线）：不算叙事证据。
AUTHOR_REGION = [(1211985, 1212200)]

TASK = json.load(open(TASK_PATH, encoding="utf-8"))
assert TASK["sourceHash"] == SOURCE_HASH, "任务声明的 sourceHash 与脚本不一致"
assert (TASK["sourceRange"][0], TASK["sourceRange"][1]) == (START, END), "区间不一致"

RAW = open(DOCS_PATH, "rb").read()
FILE_SHA = hashlib.sha256(RAW).hexdigest()
DOC = json.loads(RAW.decode("utf-8"))
TEXT = DOC[0]["text"]
SLICE = TEXT[START:END]
SLICE_SHA = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

PROBLEMS = []


# --------------------------------------------------------------------------- 引文定位
def locate(label):
    """把 content 里的 (逐字子串, occ) 解析成带全文偏移的 quote 对象。"""
    q = C.QUOTES[label]
    occ = C.OCC.get(label, 0)
    hits = []
    cur = 0
    while True:
        k = SLICE.find(q, cur)
        if k < 0:
            break
        hits.append(k)
        cur = k + 1
    if not hits:
        raise SystemExit("[引文定位失败] %s：在本单元切片内找不到 %r" % (label, q[:40]))
    if len(hits) <= occ:
        raise SystemExit("[引文定位失败] %s：occ=%d 但切片内只出现 %d 次（%r）"
                         % (label, occ, len(hits), q[:40]))
    k = hits[occ]
    start, end = START + k, START + k + len(q)
    if TEXT[start:end] != q:
        raise SystemExit("[逐字校验失败] %s：text[%d:%d] != quote" % (label, start, end))
    # label 形如 pNNN_xxx：NNN 是内容模块预期的段落号。定位出来的段落必须与它一致，
    # 否则说明 occ 选错（或选文本身改动），必须立刻失败而不是静默产出错偏移。
    # 为什么需要它：短线分隔行互为子串（「.........」⊂「...........」），
    # 只靠「唯一命中」的默认规则定位不到正确的那一处。
    m = re.match(r"^p(\d{3})_", label)
    para = para_index(start)
    if m and int(m.group(1)) != para:
        raise SystemExit("[段落不符] %s：label 声明 P%s，但定位到 P%03d（occ=%d）"
                         % (label, m.group(1), para, occ))
    # 全文出现次数（用于标注，不参与判定）
    whole = 0
    cur = 0
    first = None
    while True:
        j = TEXT.find(q, cur)
        if j < 0:
            break
        if first is None:
            first = j
        whole += 1
        cur = j + 1
    para = para_index(start)
    return {
        "quote": q,
        "start": start,
        "end": end,
        "sourceHash": SOURCE_HASH,
        "para": "P%03d" % para,
        "wholeTextOccurrences": whole,
        "occurrencesInRange": len(hits),
        "startIsFirstOccurrence": k == hits[0],
        "firstOccurrenceAt": START + hits[0],
        "inAuthorRegion": in_author_region(start, end),
        "anchorLabel": label,
    }


def para_index(offset):
    """全文偏移 → 本单元内的段落序号（按 \n 切，含空段，与切片一致）。"""
    return SLICE.count("\n", 0, offset - START)


def in_author_region(s, e):
    return any(s < b and e > a for a, b in AUTHOR_REGION)


def q(label):
    return locate(label)


def qs(labels):
    return [locate(x) for x in labels]


# --------------------------------------------------------------------------- 组装
def build():
    tasks = []
    for t in C.TASKS:
        item = {
            "id": t["id"],
            "actor": t["actor"],
            "title": t["title"],
            "nullFields": [],
        }
        for col in ("objective", "obstacle", "action", "result", "cost"):
            val = t.get(col)
            note = t.get(col + "Note")
            labels = t.get(col + "Quotes") or []
            basis = t.get(col + "Basis")
            if val is None:
                item[col] = None
                item[col + "Note"] = note
                item["nullFields"].append(col)
                if labels:
                    raise SystemExit("%s.%s 为 null 却带了引文" % (t["id"], col))
                if not note:
                    raise SystemExit("%s.%s 为 null 但没有 %sNote（未标注的未知）"
                                     % (t["id"], col, col))
            else:
                item[col] = val
                item[col + "Basis"] = basis
                item[col + "Quotes"] = qs(labels)
                if basis not in ("explicit", "inferred", "derived", "unverified"):
                    raise SystemExit("%s.%s basis 非法：%r" % (t["id"], col, basis))
                if not labels:
                    raise SystemExit("%s.%s 有值却没有引文" % (t["id"], col))
                if note:
                    item[col + "Note"] = note
        item["columnsWithoutQuotes"] = item["nullFields"]
        tasks.append(item)

    edges = []
    for e in C.CAUSE_EDGES:
        edges.append({
            "id": e["id"], "from": e["from"], "to": e["to"],
            "mechanism": e["mechanism"], "basis": e["basis"],
            "quotes": qs(e["quotes"]),
        })
    rejected = []
    for r in C.REJECTED_EDGES:
        rejected.append({"id": r["id"], "wouldBe": r["wouldBe"],
                         "whyNot": r["whyNot"], "basis": r["basis"],
                         "quotes": qs(r["quotes"])})
    states = []
    for s in C.STATES:
        item = {"id": s["id"], "who": s["who"], "aspect": s["aspect"],
                "before": s["before"], "beforeBasis": s["beforeBasis"],
                "beforeQuotes": qs(s["beforeQuotes"]),
                "after": s["after"], "afterBasis": s["afterBasis"],
                "afterQuotes": qs(s["afterQuotes"]),
                "anchor": s["anchor"], "anchorBasis": s["anchorBasis"],
                "anchorQuotes": qs(s["anchorQuotes"])}
        if s.get("note"):
            item["note"] = s["note"]
        states.append(item)
    gaps = []
    for g in C.KNOWLEDGE_GAPS:
        gaps.append({"id": g["id"], "knower": g["knower"], "notKnower": g["notKnower"],
                     "content": g["content"], "basis": g["basis"],
                     "quotes": qs(g["quotes"]), "note": g["note"]})
    fores = []
    for f in C.FORESHADOWS:
        item = {"id": f["id"], "name": f["name"], "setup": f["setup"],
                "setupBasis": f["setupBasis"], "setupQuotes": qs(f["setupQuotes"]),
                "payoff": f["payoff"], "payoffBasis": f["payoffBasis"],
                "resolved": f["resolved"]}
        if f.get("payoffQuotes"):
            item["payoffQuotes"] = qs(f["payoffQuotes"])
        else:
            item["payoffQuotes"] = []
        if f.get("note"):
            item["note"] = f["note"]
        fores.append(item)
    world = []
    for w in C.WORLD_SETTINGS:
        item = {"id": w["id"], "kind": w["kind"], "name": w["name"],
                "quote": q(w["quote"]), "explain": w["explain"], "basis": w["basis"]}
        if w.get("extraQuotes"):
            item["extraQuotes"] = qs(w["extraQuotes"])
        else:
            item["extraQuotes"] = []
        if w["kind"] == "place":
            item["placeState"] = w["placeState"]
            if w["placeState"] not in ("arrived", "mentioned"):
                raise SystemExit("%s.placeState 非法：%r" % (w["id"], w["placeState"]))
        elif w["kind"] == "item":
            item["itemStates"] = w["itemStates"]
            for st in w["itemStates"]:
                if st not in ("hold", "transfer", "use", "lose"):
                    raise SystemExit("%s.itemStates 非法：%r" % (w["id"], st))
        elif w["kind"] == "rule":
            item["institution"] = w["institution"]
            if w["institution"] not in ("declared", "executed", "misunderstood"):
                raise SystemExit("%s.institution 非法：%r" % (w["id"], w["institution"]))
        else:
            raise SystemExit("%s.kind 非法：%r" % (w["id"], w["kind"]))
        if w.get("note"):
            item["note"] = w["note"]
        world.append(item)
    themes = []
    for th in C.THEME_READINGS:
        themes.append({"id": th["id"], "perspective": th["perspective"],
                       "support": [{"event": e["event"], "quotes": qs(e["quotes"])}
                                   for e in th["support"]],
                       "counter": [{"event": e["event"], "quotes": qs(e["quotes"])}
                                   for e in th["counter"]],
                       "note": th["note"]})
    not_fores = [{"name": x["name"], "whyNot": x["whyNot"], "quotes": qs(x["quotes"])}
                 for x in C.NOT_FORESHADOWS]
    not_world = [{"name": x["name"], "whyNot": x["whyNot"], "quotes": qs(x["quotes"])}
                 for x in C.NOT_WORLD_SETTINGS]
    speech = [{"who": x["who"], "said": x["said"], "whyNotFact": x["whyNotFact"],
               "quotes": qs(x["quotes"])} for x in C.SPEECH_AS_CLUE]
    text_notes = [{"note": x["note"], "quotes": qs(x["quotes"])} for x in C.TEXTUAL_NOTES]
    unknowns = [{"id": x["id"], "text": x["text"], "quotes": qs(x["quotes"])}
                for x in C.UNKNOWNS if x.get("quotes")]
    for x in C.UNKNOWNS:
        if not x.get("quotes"):
            unknowns.append({"id": x["id"], "text": x["text"], "quotes": []})

    cand = {
        "schemaVersion": "castline/read-candidate/1",
        "task": TASK["id"],
        "agent": "w-read-3",
        "role": "READER（原文精读工作者）",
        "book": "dafeng",
        "bookTitle": "大奉打更人",
        "lane": 3,
        "unitIndex": 283,
        "unitHead": "第五十四章 问答",
        "source": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
            "selector": "docs[0].text",
            "range": [START, END],
            "codepoints": END - START,
            "sourceHash": SOURCE_HASH,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
            "sliceSha256": SLICE_SHA,
            "sliceSha256Scope": "docs[0].text[%d:%d] 的 utf-8 字节 sha256（另起字段，不覆盖 sourceHash）" % (START, END),
            "offsetCaliber": "start/end 均为相对 docs[0].text 全文的 codepoint 偏移；docs[0].text[start:end] 逐字等于 quote",
            "boundaryHead": SLICE[:20],
            "boundaryHeadMatchesTitle": SLICE.startswith("第五十四章 问答"),
            "boundaryTail": SLICE[-30:],
        },
        "provenanceNote": (
            "本候选由 loop/state/out/read_dafeng_L3_0283.w-read-3.build/build_candidate.py 生成，"
            "读解内容在同目录 content_0283.py。**候选里没有一条引文是手抄的**：每条引文只写"
            "「逐字子串 + 在本单元切片内的第 occ 次出现」，由生成脚本在 docs[0].text[%d:%d) 内"
            "定位后切片，逐条断言 text[start:end]==quote；找不到或有歧义则构建直接失败。"
            "机器自检结果见 machineSelfCheck。" % (START, END)),
        "semanticReview": "not-performed",
        "semanticReviewNote": (
            "**没有做独立语义评审**（semanticReview=not-performed）。本候选完成的是构造性自检："
            "text[start:end]==quote 逐字命中、引文全部落在本单元区间内、同一任务内五栏引文的字符区间"
            "两两不重叠、同一任务内没有两栏共用同一条引文、null 栏全部带理由、枚举值合法、"
            "叙事引文不落在作者区域。引用定位正确 ≠ 语义已核验；"
            "「这条因果边读得对不对」「这条状态该不该记」要等独立复核者读原文判定。"),
        "basisLegend": {
            "explicit": "原文直述（含叙述直接给出的人物动机与情绪）",
            "inferred": "我的归纳（例如从问句反推目标）",
            "derived": "跨段推导（要把两处以上接起来才成立）",
            "unverified": "存疑，本候选未使用该级别（存疑项一律进 unknowns[]）",
        },
        "nullFieldRule": "缺项写 null，并在同名 <栏位>Note 写明为什么没有依据。",
        "taskIdNote": ("任务 id 与原文段号（Pnnn）是两套编号：Tnn 是本候选自编的任务序号，"
                       "Pnnn 是 docs[0].text[start:end] 切片内按 \\n 切分的段落序号（含空段，"
                       "0 起）。任务 id 出现 T05 与 T05b 是补检时插入的一条（追问武僧能否娶妻生子），"
                       "没有重编后续 id —— 重编会让引用旧编号的复核对不上号。"),
        "authorRegion": [{"start": a, "end": b} for a, b in AUTHOR_REGION],
        "authorRegionNote": (
            "AUTHOR_REGION=[(1211985, 1212200)]：从「PS：先更后改，今天好像有万字了。」起到切片末尾，"
            "含其后「卡文了，两章更新在晚上。」等单章说明与两行「------------」分隔线。"
            "它属场外留言，**不算叙事证据**；本候选所有叙事引文都不落在该区间内"
            "（machineSelfCheck.authorRegionLeaks 应为 0）。"),
        "tasks": tasks,
        "causeEdges": edges,
        "rejectedEdges": rejected,
        "states": states,
        "knowledgeGaps": gaps,
        "foreshadows": fores,
        "notForeshadows": not_fores,
        "worldSettings": world,
        "notWorldSettings": not_world,
        "themeReadings": themes,
        "speechAsClueNotFact": speech,
        "textualNotes": text_notes,
        "unknowns": unknowns,
        "selfCritique": C.SELF_CRITIQUE,
    }
    return cand


# --------------------------------------------------------------------------- 机检
def selfcheck(cand):
    problems = []

    # ① 偏移口径
    if not SLICE.startswith("第五十四章 问答"):
        problems.append("区间起点不是本单元标题")
    if (END - START) != len(SLICE):
        problems.append("区间长度与切片长度不符")
    if FILE_SHA != SOURCE_HASH:
        problems.append("docs.json 的 sha256 与任务声明不一致：%s" % FILE_SHA)

    # ② 全部 quote 对象：逐字命中 + 落在区间内 + 不在作者区域（叙事引文）
    quotes = []

    def walk(node, path=""):
        if isinstance(node, dict):
            if "quote" in node and "start" in node and "end" in node:
                quotes.append((path, node))
            for k, v in node.items():
                walk(v, path + "/" + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + "[%d]" % i)

    walk(cand)
    for path, o in quotes:
        t = TEXT[o["start"]:o["end"]]
        if t != o["quote"]:
            problems.append("引文不是逐字命中：%s" % path)
        if not (START <= o["start"] < o["end"] <= END):
            problems.append("引文越出本单元区间：%s (%d,%d)" % (path, o["start"], o["end"]))
        if o["sourceHash"] != SOURCE_HASH:
            problems.append("引文 sourceHash 不对：%s" % path)
    narrative = [(p, o) for p, o in quotes
                 if "/notForeshadows" not in p and "/notWorldSettings" not in p]
    leaks = [(p, o) for p, o in narrative if in_author_region(o["start"], o["end"])]

    # ③ 同一任务内：栏位区间两两不重叠 + 没有两栏共用同一条引文
    overlap_detail, shared_detail, counts = [], [], []
    for t in cand["tasks"]:
        spans = []
        for col in ("objective", "obstacle", "action", "result", "cost"):
            for o in (t.get(col + "Quotes") or []):
                spans.append((col, o))
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                c1, a = spans[i]
                c2, b = spans[j]
                if a["start"] < b["end"] and b["start"] < a["end"]:
                    overlap_detail.append({"task": t["id"], "a": c1, "b": c2,
                                           "aRange": [a["start"], a["end"]],
                                           "bRange": [b["start"], b["end"]]})
                if a["start"] == b["start"] and a["end"] == b["end"]:
                    shared_detail.append({"task": t["id"], "a": c1, "b": c2,
                                          "quote": a["quote"][:30]})
        counts.append({"task": t["id"], "quotes": len(spans),
                       "nullFields": t["nullFields"]})
        for col in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(col) is None and not t.get(col + "Note"):
                problems.append("%s.%s 是 null 但没有 Note" % (t["id"], col))
            if t.get(col) is not None and not (t.get(col + "Quotes")):
                problems.append("%s.%s 有值但没有引文" % (t["id"], col))

    # ④ 空数组分区（提示词要求，即使没有内容也要有键）
    for key in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
        if key not in cand:
            problems.append("缺分区 %s" % key)

    # ⑤ 枚举值 + null 栏清单
    nulls = []
    for t in cand["tasks"]:
        for col in t["nullFields"]:
            nulls.append({"task": t["id"], "col": col,
                          "hasNote": bool(t.get(col + "Note")),
                          "noQuotes": not t.get(col + "Quotes")})
    # ⑤b 跨任务共用同一条引文：提示词的禁令是按任务说的（「同一任务内五栏不得共用」），
    # 跨任务共用本身不违规，但同一个区间被两条任务当作依据时应当**显式知道**，
    # 否则工作量看起来比实际大。这里只报出来，不判 problem。
    cross = {}
    for t in cand["tasks"]:
        for col in ("objective", "obstacle", "action", "result", "cost"):
            for o in (t.get(col + "Quotes") or []):
                cross.setdefault((o["start"], o["end"]), []).append("%s.%s" % (t["id"], col))
    cross_task_reuse = [{"range": list(k), "usedBy": v}
                        for k, v in sorted(cross.items()) if len({x.split(".")[0] for x in v}) > 1]
    for w in cand["worldSettings"]:
        if w["kind"] == "place" and "placeState" not in w:
            problems.append("%s 缺 placeState" % w["id"])
        if w["kind"] == "item" and not w.get("itemStates"):
            problems.append("%s 缺 itemStates" % w["id"])
        if w["kind"] == "rule" and "institution" not in w:
            problems.append("%s 缺 institution" % w["id"])

    # ⑥ 回收判定：未回收必须显式标 unresolved
    for f in cand["foreshadows"]:
        if f["resolved"] not in (True, False):
            problems.append("%s.resolved 不是布尔" % f["id"])
        if f["resolved"] is False and not f.get("note"):
            problems.append("%s 未回收但没写 note 说明" % f["id"])

    # ⑦ 主题：每条必须三件齐（perspective / support / counter）
    for th in cand["themeReadings"]:
        if not th["perspective"] or not th["support"] or not th["counter"]:
            problems.append("%s 缺 perspective/support/counter 之一" % th["id"])

    # ⑧ 覆盖
    ivs = sorted({(o["start"], o["end"]) for _, o in quotes})
    union = 0
    cur_s = cur_e = None
    for s, e in ivs:
        if cur_s is None:
            cur_s, cur_e = s, e
        elif s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            union += cur_e - cur_s
            cur_s, cur_e = s, e
    if cur_s is not None:
        union += cur_e - cur_s
    paras = SLICE.split("\n")
    offs = []
    o = START
    for i, p in enumerate(paras):
        offs.append((i, o, o + len(p)))
        o += len(p) + 1
    touched = set()
    for s, e in ivs:
        for i, a, b in offs:
            if a < e and s < b:
                touched.add(i)
    uncovered = []
    for i, a, b in offs:
        if not paras[i].strip():
            continue
        if i not in touched:
            uncovered.append({"para": "P%03d" % i, "text": paras[i][:40],
                              "inAuthorRegion": in_author_region(a, b)})

    check = {
        "buildScript": "loop/state/out/read_dafeng_L3_0283.w-read-3.build/build_candidate.py",
        "contentModule": "loop/state/out/read_dafeng_L3_0283.w-read-3.build/content_0283.py",
        "reproduceCommand": "python3 loop/state/out/read_dafeng_L3_0283.w-read-3.build/build_candidate.py",
        "quoteObjectsResolved": len(quotes),
        "uniqueQuoteIntervals": len(ivs),
        "problems": problems,
        "authorRegionLeaks": len(leaks),
        "narrativeAuthorRegionLeaks": len(leaks),
        "taskFieldIntervalOverlap": len(overlap_detail),
        "taskFieldIntervalOverlapDetail": overlap_detail,
        "crossColumnSharedQuotes": len(shared_detail),
        "crossColumnSharedQuoteDetail": shared_detail,
        "crossTaskReusedQuotes": len(cross_task_reuse),
        "crossTaskReusedQuoteDetail": cross_task_reuse,
        "taskQuoteCounts": counts,
        "nullFields": nulls,
        "unresolvedForeshadows": [f["id"] for f in cand["foreshadows"] if not f["resolved"]],
        "worldSettingKinds": {
            "place": sum(1 for w in cand["worldSettings"] if w["kind"] == "place"),
            "rule": sum(1 for w in cand["worldSettings"] if w["kind"] == "rule"),
            "item": sum(1 for w in cand["worldSettings"] if w["kind"] == "item"),
        },
        "coverage": {
            "sliceCodepoints": len(SLICE),
            "nonSpaceCodepoints": sum(1 for c in SLICE if not c.isspace()),
            "quoteUnionCodepoints": union,
            "quoteUnionRatioOfSlice": round(union / len(SLICE), 4),
            "quoteIntervals": len(ivs),
            "paragraphs": len(paras),
            "nonEmptyParagraphs": sum(1 for p in paras if p.strip()),
            "paragraphsTouchedByAtLeastOneQuote":
                len([1 for i, a, b in offs if paras[i].strip() and i in touched]),
            "uncoveredNonEmptyParagraphs": uncovered,
        },
        "note": ("problems 为空才算构建成功；覆盖率只说明「引文触及了原文的多少字符」，"
                 "**不是质量分**。未覆盖段落的逐条说明见 uncoveredParagraphAudit。"),
    }
    check["coverage"]["uncoveredParagraphAudit"] = {
        "作者区域（按纪律不作叙事证据）":
            [u["para"] for u in uncovered if u["inAuthorRegion"]],
        "场景分隔行": [u["para"] for u in uncovered
                       if not u["inAuthorRegion"] and set(u["text"].strip()) <= {"."}],
        "其他未覆盖（应逐条说明）":
            [u["para"] for u in uncovered
             if not u["inAuthorRegion"] and not set(u["text"].strip()) <= {"."}],
        "说明": ("未被任何引文触及的非空段已逐条核对：作者区域（PS 与单章说明，"
                 "含其后的分隔线）按纪律不作叙事证据；场景分隔行（「.........」等）"
                 "只在 textualNotes 里用于说明分场结构，不承载叙事。"
                 "**没有「其他未覆盖」项**才是本候选想要的终态 —— 一旦出现，"
                 "说明有叙事段被漏读，应回原文补读。"),
    }
    return check, problems


def main():
    cand = build()
    check, problems = selfcheck(cand)
    cand["machineSelfCheck"] = check
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(cand, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("写出 %s" % os.path.relpath(OUT_PATH, ROOT))
    print("引文对象 %d 条 / 唯一区间 %d 个 / problems %d"
          % (check["quoteObjectsResolved"], check["uniqueQuoteIntervals"], len(problems)))
    for p in problems:
        print("  [problem] %s" % p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
