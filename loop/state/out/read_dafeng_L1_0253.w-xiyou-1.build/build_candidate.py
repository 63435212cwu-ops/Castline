# -*- coding: utf-8 -*-
"""从 content_0253.py + quotes_0253.py 构建 read_dafeng_L1_0253.candidate.json。

为什么要有这个脚本，而不是手写 JSON（与 L3_0291 同一套纪律，本轮独立重写）：
  · 候选里**没有一条引文是手抄进 JSON 的**。每条引文只写「P 段号 + 起始锚 + 结束锚」，
    由本脚本在该段内定位并切片，逐条断言 docs[0].text[start:end] == quote 逐字成立。
  · 锚必须在该段内**各自唯一**；否则构建失败（歧义会产生静默错偏移）。
  · 同一任务内五栏引文的字符区间**两两不重叠**、且没有两栏共用同一条引文。
  · null 栏必须带同名 <栏位>Note，否则构建失败。
  · 叙事引文不得落进 AUTHOR_REGION（作者场外留言）。
  · 全部机检在 build 末尾跑一遍，problems 非空即退出码 1。

用法：
  python3 .../build_candidate.py            # 构建 + 自检 + 写盘
  python3 .../build_candidate.py --probe    # 只解析引文并打印定位表，不写盘
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)

import content_0253 as C  # noqa: E402
import quotes_0253 as Q  # noqa: E402

DOCS_PATH = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
OUT_PATH = os.path.join(ROOT, "loop", "state", "out", "read_dafeng_L1_0253.candidate.json")
TASK_PATH = os.path.join(ROOT, "loop", "state", "runs", "task-read_dafeng_L1_0253.json")
SOURCE_HASH_EXPECT = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

START, END = 1041765, 1048523
UNIT_HEAD = "第二十四章 没有说谎"
AGENT = "w-xiyou-1"
BOOK, BOOK_TITLE, LANE, UNIT_INDEX = "dafeng", "大奉打更人", 1, 253

# 作者区域：从 P169「PS：感谢盟主…」起到切片末尾（含文末分隔线）。
# 它属场外留言，**不算叙事证据**。P168 的「............」是正文分隔符，不在此区间内。
AUTHOR_REGION = [(1048221, 1048523)]

TASK = json.load(open(TASK_PATH, encoding="utf-8"))
assert TASK["sourceHash"] == SOURCE_HASH_EXPECT, "任务声明的 sourceHash 与脚本不一致"
assert tuple(TASK["sourceRange"]) == (START, END), "任务区间与脚本不一致"

RAW = open(DOCS_PATH, "rb").read()
FILE_SHA = hashlib.sha256(RAW).hexdigest()
DOC = json.loads(RAW.decode("utf-8"))
TEXT = DOC[0]["text"]
SLICE = TEXT[START:END]
SLICE_SHA = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

# 段落表：只取**非空**行，编号 P001 起（与探针表一致，便于人工核对）
PARAS = []          # [(no, text, start_offset)]
_o = START
for _line in SLICE.split("\n"):
    if _line.strip():
        PARAS.append((len(PARAS) + 1, _line, _o))
    _o += len(_line) + 1
PARA_BY_NO = {no: (txt, off) for no, txt, off in PARAS}

PROBLEMS = []


def in_author_region(s, e):
    return any(s < b and e > a for a, b in AUTHOR_REGION)


def resolve_span(para_no, start_anchor, end_anchor):
    """在指定段内用两个锚定位一个逐字区间。锚不唯一/顺序不对 ⇒ 抛错。"""
    if para_no not in PARA_BY_NO:
        raise SystemExit("[定位失败] P%03d 不在本单元段落表内" % para_no)
    txt, off = PARA_BY_NO[para_no]
    a = txt.find(start_anchor)
    if a < 0:
        raise SystemExit("[定位失败] P%03d 找不到起始锚 %r" % (para_no, start_anchor))
    if txt.find(start_anchor, a + 1) >= 0:
        raise SystemExit("[锚不唯一] P%03d 起始锚 %r 出现多次" % (para_no, start_anchor))
    b = txt.find(end_anchor, a)
    if b < 0:
        raise SystemExit("[定位失败] P%03d 起始锚之后找不到结束锚 %r" % (para_no, end_anchor))
    if txt.find(end_anchor, b + 1) >= 0:
        raise SystemExit("[锚不唯一] P%03d 结束锚 %r 出现多次" % (para_no, end_anchor))
    b += len(end_anchor)
    return txt[a:b], off + a, off + b


def locate(label, table=None):
    tbl = Q.QUOTES if table is None else table
    if label not in tbl:
        raise SystemExit("[定位失败] 引文库没有 label %s" % label)
    para_no, sa, ea = tbl[label]
    q, start, end = resolve_span(para_no, sa, ea)
    if TEXT[start:end] != q:
        raise SystemExit("[逐字校验失败] %s：text[%d:%d] != quote" % (label, start, end))
    if not (START <= start < end <= END):
        raise SystemExit("[越界] %s 落在区间外 (%d,%d)" % (label, start, end))
    return {
        "quote": q,
        "start": start,
        "end": end,
        "sourceHash": SOURCE_HASH_EXPECT,
        "para": "P%03d" % para_no,
        "occurrencesInRange": SLICE.count(q),
        "wholeTextOccurrences": TEXT.count(q),
        "startIsFirstOccurrence": SLICE.find(q) == start - START,
        "firstOccurrenceAt": START + SLICE.find(q),
        "inAuthorRegion": in_author_region(start, end),
        "anchorLabel": label,
    }


def q(label):
    return locate(label)


def qs(labels):
    return [locate(x) for x in labels]


def qx(label):
    return locate(label, Q.EXTRA)


def qxs(labels):
    return [locate(x, Q.EXTRA) for x in labels]


# --------------------------------------------------------------------------- 组装
def build():
    tasks = []
    for t in C.TASKS:
        item = {"id": t["id"], "actor": t["actor"], "title": t["title"],
                "nullFields": [], "basisLegend": C.BASIS_LEGEND_SHORT}
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
                    raise SystemExit("%s.%s 为 null 但没有 %sNote" % (t["id"], col, col))
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
        tasks.append(item)

    edges = [{"id": e["id"], "from": e["from"], "to": e["to"],
              "mechanism": e["mechanism"], "basis": e["basis"],
              "quotes": qs(e["quotes"]), **({"note": e["note"]} if e.get("note") else {})}
             for e in C.CAUSE_EDGES]
    rejected = [{"id": r["id"], "wouldBe": r["wouldBe"], "whyNot": r["whyNot"],
                 "basis": r["basis"], "quotes": qs(r["quotes"])}
                for r in C.REJECTED_EDGES]
    states = [{"id": s["id"], "who": s["who"], "aspect": s["aspect"],
               "before": s["before"], "beforeBasis": s["beforeBasis"],
               "beforeQuotes": qs(s["beforeQuotes"]),
               "after": s["after"], "afterBasis": s["afterBasis"],
               "afterQuotes": qs(s["afterQuotes"]),
               "anchor": s["anchor"], "anchorBasis": s["anchorBasis"],
               "anchorQuotes": qs(s["anchorQuotes"]),
               **({"note": s["note"]} if s.get("note") else {})}
              for s in C.STATES]
    gaps = [{"id": g["id"], "who": g["who"], "aspect": g["aspect"],
             "before": g["before"], "beforeBasis": g["beforeBasis"],
             "beforeQuotes": qs(g["beforeQuotes"]),
             "after": g["after"], "afterBasis": g["afterBasis"],
             "afterQuotes": qs(g["afterQuotes"]),
             "anchor": g["anchor"], "anchorBasis": g["anchorBasis"],
             "anchorQuotes": qs(g["anchorQuotes"]),
             **({"note": g["note"]} if g.get("note") else {})}
            for g in C.KNOWLEDGE_STATES]
    fores = []
    for f in C.FORESHADOWS:
        item = {"id": f["id"], "name": f["name"], "setup": f["setup"],
                "setupBasis": f["setupBasis"], "setupQuotes": qs(f["setupQuotes"]),
                "payoff": f["payoff"], "payoffBasis": f["payoffBasis"],
                "payoffQuotes": qs(f["payoffQuotes"]) if f.get("payoffQuotes") else [],
                "resolved": f["resolved"]}
        if f.get("note"):
            item["note"] = f["note"]
        fores.append(item)
    world = []
    for w in C.WORLD_SETTINGS:
        item = {"id": w["id"], "kind": w["kind"], "name": w["name"],
                "quote": q(w["quote"]), "explain": w["explain"], "basis": w["basis"],
                "extraQuotes": qs(w["extraQuotes"]) if w.get("extraQuotes") else []}
        if w["kind"] == "place":
            item["placeState"] = w["placeState"]
            if w["placeState"] not in ("arrived", "mentioned"):
                raise SystemExit("%s.placeState 非法" % w["id"])
        elif w["kind"] == "item":
            item["itemStates"] = w["itemStates"]
            for st in w["itemStates"]:
                if st not in ("hold", "transfer", "use", "lose"):
                    raise SystemExit("%s.itemStates 非法：%r" % (w["id"], st))
        elif w["kind"] == "rule":
            item["institution"] = w["institution"]
            if w["institution"] not in ("declared", "executed", "misunderstood"):
                raise SystemExit("%s.institution 非法" % w["id"])
        else:
            raise SystemExit("%s.kind 非法" % w["id"])
        if w.get("note"):
            item["note"] = w["note"]
        world.append(item)
    themes = [{"id": th["id"], "perspective": th["perspective"],
               "support": [{"event": e["event"], "quotes": qs(e["quotes"])}
                           for e in th["support"]],
               "counter": [{"event": e["event"], "quotes": qs(e["quotes"])}
                           for e in th["counter"]],
               "note": th["note"]}
              for th in C.THEME_READINGS]
    not_fores = [{"name": x["name"], "whyNot": x["whyNot"], "quotes": qs(x["quotes"])}
                 for x in C.NOT_FORESHADOWS]
    not_world = [{"name": x["name"], "whyNot": x["whyNot"], "quotes": qs(x["quotes"])}
                 for x in C.NOT_WORLD_SETTINGS]
    speech = [{"who": x["who"], "said": x["said"], "whyNotFact": x["whyNotFact"],
               "quotes": qs(x["quotes"])} for x in C.SPEECH_AS_CLUE]
    text_notes = [{"note": x["note"], "quotes": qxs(x["quotes"])} for x in C.TEXTUAL_NOTES]
    author_ev = [{"note": x["note"], "quotes": qxs(x["quotes"])}
                 for x in C.AUTHOR_REGION_EVIDENCE]
    unknowns = [{"id": x["id"], "text": x["text"], "quotes": qs(x["quotes"])}
                for x in C.UNKNOWNS]

    legend = {}
    for t in tasks:
        for col in ("objective", "obstacle", "action", "result", "cost"):
            for o in (t.get(col + "Quotes") or []):
                legend.setdefault(o["anchorLabel"], o["quote"])
    for bucket in (edges, rejected, states, gaps, fores, world, not_fores, not_world,
                   speech, text_notes, unknowns):
        def walk(n):
            if isinstance(n, dict):
                if "quote" in n and "anchorLabel" in n:
                    legend.setdefault(n["anchorLabel"], n["quote"])
                for v in n.values():
                    walk(v)
            elif isinstance(n, list):
                for v in n:
                    walk(v)
        walk(bucket)
    for th in themes:
        for side in ("support", "counter"):
            for e in th[side]:
                for o in e["quotes"]:
                    legend.setdefault(o["anchorLabel"], o["quote"])
    for e in author_ev:
        for o in e["quotes"]:
            legend.setdefault(o["anchorLabel"], o["quote"])

    return {
        "schemaVersion": "castline/read-candidate/1",
        "task": TASK["id"],
        "agent": AGENT,
        "role": "READER（原文精读工作者）",
        "book": BOOK,
        "bookTitle": BOOK_TITLE,
        "lane": LANE,
        "unitIndex": UNIT_INDEX,
        "unitHead": UNIT_HEAD,
        "source": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
            "selector": "docs[0].text",
            "range": [START, END],
            "codepoints": END - START,
            "sourceHash": SOURCE_HASH_EXPECT,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片的）",
            "sliceSha256": SLICE_SHA,
            "sliceSha256Scope": "docs[0].text[%d:%d] 的 utf-8 字节 sha256（另起字段，不覆盖 sourceHash）"
                                % (START, END),
            "offsetCaliber": "start/end 均为相对 docs[0].text 全文的 codepoint 偏移；docs[0].text[start:end] 逐字等于 quote",
            "boundaryHead": SLICE[:20],
            "boundaryHeadMatchesTitle": SLICE.startswith(UNIT_HEAD),
            "boundaryTail": SLICE[-30:],
        },
        "provenanceNote": (
            "本候选由 loop/state/out/read_dafeng_L1_0253.w-xiyou-1.build/build_candidate.py 生成，"
            "读解内容在同目录 content_0253.py，逐字引文库在 quotes_0253.py。**候选里没有一条引文是手抄的**："
            "每条引文只写「P 段号 + 起始锚 + 结束锚」，由生成脚本在 docs[0].text[%d:%d) 内定位后切片，"
            "逐条断言 text[start:end]==quote；锚不唯一或找不到则构建直接失败。"
            "机器自检结果见 machineSelfCheck。" % (START, END)),
        "semanticReview": "not-performed",
        "semanticReviewNote": (
            "**没有做独立语义评审**（semanticReview=not-performed）。本候选完成的是构造性自检："
            "text[start:end]==quote 逐字命中、引文全部落在本单元区间内、同一任务内五栏引文的字符区间"
            "两两不重叠、同一任务内没有两栏共用同一条引文、null 栏全部带理由、枚举值合法、"
            "叙事引文不落进作者区域。引用定位正确 ≠ 语义已核验；"
            "「这条因果边读得对不对」「这条状态该不该记」要等独立复核者读原文判定。"),
        "basisLegend": C.BASIS_LEGEND,
        "nullFieldRule": "缺项写 null，并在同名 <栏位>Note 写明为什么没有依据；不写理由的 null 视为未标注的未知。",
        "taskIdNote": ("Tnn 是本候选自编的任务序号；Pnnn 是 docs[0].text[start:end] 切片内按 \\n 切分后"
                       "**非空段落**的序号（1 起），与 quotes_0253.py 的段号一致。两者是不同编号。"),
        "authorRegion": [{"start": a, "end": b} for a, b in AUTHOR_REGION],
        "authorRegionNote": (
            "AUTHOR_REGION=[(%d,%d)]：从 P169「PS：感谢盟主…」起到切片末尾，含两条 PS、"
            "「晚点更新，跟大家打个招呼」「这一章比较重要…五点前肯定更新。」与两处 ------------ 分隔线。"
            "它属**场外留言**，不算叙事证据；本候选所有叙事引文都不落在该区间内"
            "（machineSelfCheck.narrativeAuthorRegionLeaks 应为 0）。该区间的引文只出现在 authorRegionEvidence 一节。"
            % (AUTHOR_REGION[0][0], AUTHOR_REGION[0][1])),
        "tasks": tasks,
        "causeEdges": edges,
        "rejectedEdges": rejected,
        "states": states,
        "knowledgeStates": gaps,
        "foreshadows": fores,
        "notForeshadows": not_fores,
        "worldSettings": world,
        "notWorldSettings": not_world,
        "themeReadings": themes,
        "speechAsClueNotFact": speech,
        "textualNotes": text_notes,
        "authorRegionEvidence": author_ev,
        "unknowns": unknowns,
        "selfCritique": C.SELF_CRITIQUE,
        "verbatimQuotes": {k: {"quote": legend[k], "chars": len(legend[k]),
                               "sourceHash": SOURCE_HASH_EXPECT} for k in sorted(legend)},
    }


# --------------------------------------------------------------------------- 机检
def selfcheck(cand):
    problems = []

    if not SLICE.startswith(UNIT_HEAD):
        problems.append("区间起点不是本单元标题")
    if not cand["source"]["boundaryHeadMatchesTitle"]:
        problems.append("boundaryHeadMatchesTitle 非真")
    if FILE_SHA != SOURCE_HASH_EXPECT:
        problems.append("docs.json 的 sha256 与任务声明不一致：%s" % FILE_SHA)
    if SLICE_SHA != cand["source"]["sliceSha256"]:
        problems.append("切片哈希不一致")

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
        if TEXT[o["start"]:o["end"]] != o["quote"]:
            problems.append("引文不是逐字命中：%s" % path)
        if not (START <= o["start"] < o["end"] <= END):
            problems.append("引文越出本单元区间：%s" % path)
        if o["sourceHash"] != SOURCE_HASH_EXPECT:
            problems.append("引文 sourceHash 不对：%s" % path)
        if SLICE[o["start"] - START:o["end"] - START] != o["quote"]:
            problems.append("切片内再切与全文切片不一致：%s" % path)

    narrative = [(p, o) for p, o in quotes
                 if "/authorRegionEvidence" not in p
                 and "/notForeshadows" not in p and "/notWorldSettings" not in p]
    leaks = [(p, o) for p, o in narrative if in_author_region(o["start"], o["end"])]
    if leaks:
        problems.append("叙事引文落进作者区域 %d 条：%s"
                        % (len(leaks), [p for p, _ in leaks][:3]))
    # textualNotes 允许引用作者区域（它本来就是记原文形貌的），但必须显式标 inAuthorRegion
    for p, o in quotes:
        if in_author_region(o["start"], o["end"]) and not o["inAuthorRegion"]:
            problems.append("作者区域引文没标 inAuthorRegion：%s" % p)

    # ③ 同一任务内：栏间区间不重叠 + 没有两栏共用同一条引文
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
                    problems.append("%s 栏间引文区间重叠：%s × %s" % (t["id"], c1, c2))
                if a["start"] == b["start"] and a["end"] == b["end"]:
                    shared_detail.append({"task": t["id"], "a": c1, "b": c2,
                                          "quote": a["quote"][:30]})
                    problems.append("%s 两栏共用同一条引文：%s × %s" % (t["id"], c1, c2))
        counts.append({"task": t["id"], "quotes": len(spans),
                       "nullFields": t["nullFields"]})
        for col in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(col) is None and not t.get(col + "Note"):
                problems.append("%s.%s 是 null 但没有 Note" % (t["id"], col))
            if t.get(col) is not None and not t.get(col + "Quotes"):
                problems.append("%s.%s 有值但没有引文" % (t["id"], col))
            if t.get(col) is not None and t.get(col + "Basis") not in (
                    "explicit", "inferred", "derived", "unverified"):
                problems.append("%s.%s basis 非法" % (t["id"], col))

    # ③b 同一段内两栏各引一段：允许；但同一段被同一条任务的两栏同时引用时**区间必须不同**
    #     （上面的重叠检查已经覆盖）。

    # ④ 分区存在性
    for key in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
                "themeReadings"):
        if key not in cand:
            problems.append("缺分区 %s" % key)

    # ⑤ worldSettings 枚举
    for w in cand["worldSettings"]:
        if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            problems.append("%s 缺/非法 placeState" % w["id"])
        if w["kind"] == "item" and not w.get("itemStates"):
            problems.append("%s 缺 itemStates" % w["id"])
        if w["kind"] == "rule" and w.get("institution") not in (
                "declared", "executed", "misunderstood"):
            problems.append("%s 缺/非法 institution" % w["id"])

    # ⑥ 伏笔：未回收必须显式 unresolved 并写 note；已回收必须有回收引文
    for f in cand["foreshadows"]:
        if f["resolved"] not in (True, False):
            problems.append("%s.resolved 不是布尔" % f["id"])
        if f["resolved"] is False and not f.get("note"):
            problems.append("%s 未回收但没写 note 说明" % f["id"])
        if f["resolved"] is True and not f.get("payoffQuotes"):
            problems.append("%s 标了已回收却没有回收引文" % f["id"])
        if f["resolved"] is False and f.get("payoffQuotes"):
            problems.append("%s 标了未回收却带了回收引文" % f["id"])

    # ⑦ 主题：三件齐 + 禁用判据
    for th in cand["themeReadings"]:
        if not th["perspective"] or not th["support"] or not th["counter"]:
            problems.append("%s 缺 perspective/support/counter 之一" % th["id"])
        banned = ("事件密度", "剧情点数量", "死亡人数", "篇幅中点", "时间中点")
        blob = th["perspective"] + th["note"]
        for b in banned:
            if b in blob:
                problems.append("%s 用了被禁的高潮判据：%s" % (th["id"], b))

    # ⑦b 状态与知识差：before/after/anchor 各自必须有引文与合法 basis
    for s in cand["states"]:
        for side in ("before", "after", "anchor"):
            if not s.get(side + "Quotes"):
                problems.append("%s.%s 没有引文" % (s["id"], side))
            if s.get(side + "Basis") not in ("explicit", "inferred", "derived", "unverified"):
                problems.append("%s.%s basis 非法" % (s["id"], side))
    for g in cand["knowledgeStates"]:
        for side in ("before", "after", "anchor"):
            if not g.get(side + "Quotes"):
                problems.append("%s.%s 没有引文" % (g["id"], side))
            if g.get(side + "Basis") not in ("explicit", "inferred", "derived", "unverified"):
                problems.append("%s.%s basis 非法" % (g["id"], side))

    # ⑦c 因果边：方向 + 机制 + 至少两条引文
    for e in cand["causeEdges"]:
        if not e.get("from") or not e.get("to"):
            problems.append("%s 缺方向（from/to）" % e["id"])
        if not (e.get("mechanism") or "").strip():
            problems.append("%s 缺触发机制" % e["id"])
        if len(e.get("quotes") or []) < 2:
            problems.append("%s 引文少于 2 条" % e["id"])

    # ⑧ 覆盖统计
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
    covered = set()
    for _, o in quotes:
        covered.add(o["para"])
    all_paras = ["P%03d" % no for no, _, _ in PARAS]
    zero = [p for p in all_paras if p not in covered]

    # 自报计数：只用**一个**自然定义（带偏移的引文对象数），避免 L3_0291 那种三口径互不相等
    fcounts = {
        "quoteObjects": len(quotes),
        "uniqueQuoteIntervals": len({(o["start"], o["end"]) for _, o in quotes}),
        "uniqueQuoteStrings": len({o["quote"] for _, o in quotes}),
        "verbatimLegend": len(cand["verbatimQuotes"]),
        "paras": len(PARAS),
        "parasCovered": len(covered),
        "charsCoveredUnion": union,
        "tasks": len(cand["tasks"]),
        "nullFields": sum(len(t["nullFields"]) for t in cand["tasks"]),
        "causeEdges": len(cand["causeEdges"]),
        "rejectedEdges": len(cand["rejectedEdges"]),
        "states": len(cand["states"]),
        "knowledgeStates": len(cand["knowledgeStates"]),
        "foreshadows": len(cand["foreshadows"]),
        "foreshadowsResolved": sum(1 for f in cand["foreshadows"] if f["resolved"]),
        "notForeshadows": len(cand["notForeshadows"]),
        "worldSettings": len(cand["worldSettings"]),
        "notWorldSettings": len(cand["notWorldSettings"]),
        "themeReadings": len(cand["themeReadings"]),
        "unknowns": len(cand["unknowns"]),
        "selfCritique": len(cand["selfCritique"]),
    }
    if fcounts["verbatimLegend"] != fcounts["uniqueQuoteStrings"]:
        problems.append("verbatimQuotes 条目数与不同引文串数不一致：%d vs %d"
                        % (fcounts["verbatimLegend"], fcounts["uniqueQuoteStrings"]))

    cross = {}
    for t in cand["tasks"]:
        for col in ("objective", "obstacle", "action", "result", "cost"):
            for o in (t.get(col + "Quotes") or []):
                cross.setdefault((o["start"], o["end"]), []).append("%s.%s" % (t["id"], col))
    cross_task_reuse = [{"range": list(k), "usedBy": v}
                        for k, v in sorted(cross.items())
                        if len({x.split(".")[0] for x in v}) > 1]

    return problems, {
        "taskFieldIntervalOverlap": len(overlap_detail),
        "taskFieldIntervalOverlapDetail": overlap_detail,
        "crossColumnSharedQuotes": len(shared_detail),
        "crossColumnSharedQuoteDetail": shared_detail,
        "taskQuoteCounts": counts,
        "crossTaskReusedQuotes": len(cross_task_reuse),
        "crossTaskReusedQuoteDetail": cross_task_reuse,
        "authorRegionLeaks": len([1 for _, o in quotes if o["inAuthorRegion"]]),
        "narrativeAuthorRegionLeaks": len(leaks),
        "zeroCoveredParas": zero,
        "zeroCoveredParasTruncated": len(zero) > 40,
        "fieldCounts": fcounts,
        "problems": list(problems),
    }


def main():
    cand = build()
    if "--probe" in sys.argv:
        for t in cand["tasks"]:
            for col in ("objective", "obstacle", "action", "result", "cost"):
                for o in (t.get(col + "Quotes") or []):
                    print("%s.%-9s %-16s [%d,%d) %s" % (t["id"], col, o["anchorLabel"],
                                                        o["start"], o["end"],
                                                        o["quote"][:34]))
        for name, lab in (("EXTRA", Q.EXTRA),):
            for k in lab:
                o = qx(k)
                print("%-9s %-16s [%d,%d) %s" % ("", k, o["start"], o["end"], o["quote"][:34]))
        return 0

    problems, machine = selfcheck(cand)
    cand["machineSelfCheck"] = {
        "buildScript": "loop/state/out/read_dafeng_L1_0253.w-xiyou-1.build/build_candidate.py",
        "contentModule": "loop/state/out/read_dafeng_L1_0253.w-xiyou-1.build/content_0253.py",
        "quoteModule": "loop/state/out/read_dafeng_L1_0253.w-xiyou-1.build/quotes_0253.py",
        "reproduceCommand": "python3 loop/state/out/read_dafeng_L1_0253.w-xiyou-1.build/build_candidate.py",
        **machine,
    }
    if problems:
        for p in problems:
            print("[机检失败] %s" % p, file=sys.stderr)
        return 1
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cand, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT_PATH)
    print("已写出 %s" % OUT_PATH)
    print("引文对象 %d / 不同引文串 %d / 覆盖段落 %d/%d / 区间覆盖 %d 字符"
          % (machine["fieldCounts"]["quoteObjects"],
             machine["fieldCounts"]["uniqueQuoteStrings"],
             machine["fieldCounts"]["parasCovered"],
             machine["fieldCounts"]["paras"],
             machine["fieldCounts"]["charsCoveredUnion"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
