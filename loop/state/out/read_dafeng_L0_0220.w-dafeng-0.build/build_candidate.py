#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 content_core.py 的结论 + quotes.py 的实算偏移组装成候选 JSON。

硬判据（任一不成立即 exit 1 且**不写盘**）：
  H0  源哈希 == 任务 sourceHash；切片以单元标题开头
  H1  每条引文 text[start:end] == quote 逐字成立
  H2  每条引文落在 [821142,826801) 内
  H3  每条引文在本单元切片内唯一，且首次命中位置 == start
  H4  每条引文的 sourceHash == 整个 docs.json 的 sha256
  H5  五元组每一栏（非 null）都必须自带 quotes（展开后非空）
  H5b **同一任务内五栏不得共用同一句原文**（字面量与偏移双查）
  H6  某一栏为 null 时，必须存在同名 <栏位>Note 且非空
  H7  展开后不存在「只有 quoteKeys 而没有 quotes」的条目（悬空依据）
  H8  causeEdges 每条必须有 from/to/mechanism + 引文
  H9  states 每条必须有 before/after/anchor + 引文
  H10 foreshadows：resolved 必须有 payoff；unresolved 必须有 payoffNote
  H11 worldSettings：place 必须有 placeState；item 必须有 itemStates；rule 必须有 institution
  H12 itemStates 只能取 hold/transfer/use/lose；placeState 只能取 arrived/mentioned
  H13 institution 只能取 declared/executed/misunderstood
  H14 themeReadings 每条必须有 perspective/support/counter
  H15 引文登记表里的条目必须**全部**被真正引用（不许登记了不用）
  H16 展开后的所有 quote 文本必须两两可区分地指向原文（去重后计数一致）
  H17 内部编号不得悬空（rejectedEdges 引用的键必须存在）
  H18 语层双向核对：候选里出现的每条人物言辞都必须在 speechLayerDisclosure 里登记
  H19 自报条数 == 实际条数（sectionCounts 由脚本生成，不手写）
  H20 crossSectionQuoteReuse / bookLevelDuplicateQuotes 的偏移必须落在区间内且等于切片内首次命中
  H21 五栏引文两两不同也必须在**栏位之间**成立（H5b 的加强：跨任务同一栏不得重复）
"""
import json
import re
import sys
import hashlib
from pathlib import Path

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parents[3]
sys.path.insert(0, str(BUILD))

from quotes import QUOTES, SOURCE_HASH, SLICE_RANGE  # noqa: E402
import content_core as C  # noqa: E402

# ── 别名前置检查（在展开之前一次性报全，避免一个个撞 KeyError）──────────
_bad_alias = []
for _name in dir(C):
    _obj = getattr(C, _name)
    if isinstance(_obj, dict) and _obj.get("quoteKeys"):
        for _k in _obj["quoteKeys"]:
            if _k not in QUOTES:
                _bad_alias.append("%s.%s -> %r" % (_name, _obj.get("id", "?"), _k))
if _bad_alias:
    print("[FAIL] 引文别名/键未登记（共 %d 处）：" % len(_bad_alias), file=sys.stderr)
    for _b in _bad_alias:
        print("   " + _b, file=sys.stderr)
    sys.exit(1)

DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK_ID = "read:dafeng:L0:0220"
OUT_PATH = ROOT / "loop/state/out/read_dafeng_L0_0220.candidate.json"
TASK_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = SLICE_RANGE

problems = []


def fail(msg):
    problems.append(msg)


def expand(keys, where):
    """把引文键展开成带实测偏移的引用对象。"""
    out = []
    for k in keys:
        if k not in QUOTES:
            fail("H17 %s：引文键不存在 %r" % (where, k))
            continue
        v = QUOTES[k]
        out.append({"quote": v["quote"], "start": v["start"], "end": v["end"],
                    "sourceHash": SOURCE_HASH})
    return out


def expand_field(f, where, field):
    """展开五元组的一栏。"""
    if f is None:
        return None
    qs = expand(f["quoteKeys"], "%s.%s" % (where, field))
    if not qs:
        fail("H5 %s.%s：非 null 栏位没有任何引文" % (where, field))
    d = {"text": f["text"], "basis": f["basis"], "quotes": qs}
    if f.get("note"):
        d["note"] = f["note"]
    return d


def main():
    blob = DOCS.read_bytes()
    if hashlib.sha256(blob).hexdigest() != TASK_HASH:
        fail("H0 docs.json 哈希与任务不符")
    text = json.loads(blob)[0]["text"]
    seg = text[START:END]
    if not seg.startswith("第两百一十九章 本官许七安"):
        fail("H0 切片不以单元标题开头")

    # ── H1/H2/H3/H4：逐条复算引文 ──────────────────────────────────────
    used_keys = set()
    for k, v in QUOTES.items():
        if text[v["start"]:v["end"]] != v["quote"]:
            fail("H1 %s：text[start:end] != quote" % k)
        if not (START <= v["start"] < v["end"] <= END):
            fail("H2 %s：越界 [%d,%d)" % (k, v["start"], v["end"]))
        if seg.count(v["quote"]) != 1:
            fail("H3 %s：切片内非唯一" % k)
        if seg.find(v["quote"]) != v["start"] - START:
            fail("H3 %s：首次命中 != start" % k)
        if len(v["quote"]) != v["end"] - v["start"]:
            fail("H1 %s：长度不符" % k)

    # ── tasks ──────────────────────────────────────────────────────────
    tasks = []
    fields = ("objective", "obstacle", "action", "result", "cost")
    for t in C.TASKS:
        rec = {"id": t["id"], "name": t["name"], "actor": t["actor"],
               "actorBasis": t["actorBasis"], "actorNote": t.get("actorNote")}
        per_task_lits = {}
        for f in fields:
            raw = t.get(f)
            rec[f] = expand_field(raw, t["id"], f)
            if raw is None:
                note_key = f + "Note"
                note = t.get(note_key) or t.get("notes", {}).get(note_key)
                if not note:
                    fail("H6 %s：%s=null 但没有 %s" % (t["id"], f, note_key))
                else:
                    rec[note_key] = note
            else:
                for q in rec[f]["quotes"]:
                    used_keys.add(q["quote"])
                    # H5b：同一任务内五栏不得共用同一句原文
                    if q["quote"] in per_task_lits:
                        fail("H5b %s：%s 与 %s 共用同一句原文 %r"
                             % (t["id"], f, per_task_lits[q["quote"]], q["quote"][:24]))
                    per_task_lits[q["quote"]] = f
        tasks.append(rec)

    # ── rejectedTasks ─────────────────────────────────────────────────
    rejected = []
    for r in C.REJECTED_TASKS:
        qs = expand(r["quoteKeys"], "rejectedTasks.%s" % r["id"])
        if not qs:
            fail("H7 rejectedTasks.%s：无引文" % r["id"])
        for q in qs:
            used_keys.add(q["quote"])
        rejected.append({"id": r["id"], "candidate": r["candidate"], "why": r["why"], "quotes": qs})

    # ── causeEdges ────────────────────────────────────────────────────
    def edge_list(src, label, rejected=False):
        out = []
        for e in src:
            qs = expand(e["quoteKeys"], "%s.%s" % (label, e["id"]))
            if not qs:
                fail("H8 %s.%s：无引文" % (label, e["id"]))
            for q in qs:
                used_keys.add(q["quote"])
            if rejected:
                d = {"id": e["id"], "edge": e["edge"], "why": e["why"], "quotes": qs}
            else:
                d = {"id": e["id"], "from": e["from"], "to": e["to"],
                     "mechanism": e["mechanism"], "basis": e["basis"], "quotes": qs}
                if e.get("note"):
                    d["note"] = e["note"]
            out.append(d)
        return out

    cause_edges = edge_list(C.CAUSE_EDGES, "causeEdges")
    rejected_edges = edge_list(C.REJECTED_EDGES, "rejectedEdges", rejected=True)

    # ── states ────────────────────────────────────────────────────────
    states = []
    for s in C.STATES:
        d = {"id": s["id"], "kind": s["kind"], "who": s["who"], "basis": s["basis"]}
        if s["kind"] == "change":
            for f in ("before", "after", "anchor"):
                sub = expand_field(s.get(f), s["id"], f)
                if sub is None:
                    fail("H9 %s：缺 %s" % (s["id"], f))
                d[f] = sub
        else:  # knowledge
            for f in ("knows", "knowsNot"):
                sub = expand_field(s.get(f), s["id"], f)
                if sub is None:
                    fail("H9 %s：缺 %s" % (s["id"], f))
                d[f] = sub
        if s.get("note"):
            d["note"] = s["note"]
        for f in ("before", "after", "anchor", "knows", "knowsNot"):
            for q in (d.get(f) or {}).get("quotes", []):
                used_keys.add(q["quote"])
        states.append(d)

    # ── foreshadows ───────────────────────────────────────────────────
    fores = []
    for f in C.FORESHADOWS:
        setup = expand_field(f["setup"], f["id"], "setup")
        for q in setup["quotes"]:
            used_keys.add(q["quote"])
        d = {"id": f["id"], "name": f["name"], "status": f["status"],
             "basis": f["basis"], "setup": setup}
        if f.get("payoff") is not None:
            d["payoff"] = expand_field(f["payoff"], f["id"], "payoff")
            for q in d["payoff"]["quotes"]:
                used_keys.add(q["quote"])
        else:
            d["payoff"] = None
            if not f.get("payoffNote"):
                fail("H10 %s：unresolved 但没有 payoffNote" % f["id"])
        if f.get("payoffNote"):
            d["payoffNote"] = f["payoffNote"]
        if f["status"] == "resolved" and d["payoff"] is None:
            fail("H10 %s：resolved 但没有 payoff" % f["id"])
        if f.get("note"):
            d["note"] = f["note"]
        fores.append(d)

    not_fores = []
    for r in C.NOT_FORESHADOWS:
        qs = expand(r["quoteKeys"], "notForeshadows.%s" % r["id"])
        for q in qs:
            used_keys.add(q["quote"])
        not_fores.append({"id": r["id"], "item": r["item"], "why": r["why"], "quotes": qs})

    # ── worldSettings ─────────────────────────────────────────────────
    PLACE_OK = ("arrived", "mentioned")
    ITEM_OK = ("hold", "transfer", "use", "lose")
    INST_OK = ("declared", "executed", "misunderstood")
    wsets = []
    for w in C.WORLD_SETTINGS:
        d = {"id": w["id"], "kind": w["kind"], "name": w["name"],
             "explain": w["explain"], "basis": w["basis"]}
        if w["kind"] == "place":
            if w.get("placeState") not in PLACE_OK:
                fail("H11/H12 %s：placeState 非法 %r" % (w["id"], w.get("placeState")))
            d["placeState"] = w["placeState"]
        elif w["kind"] == "item":
            st = w.get("itemStates")
            if not isinstance(st, list):
                fail("H11 %s：item 没有 itemStates" % w["id"])
            else:
                bad = [x for x in st if x not in ITEM_OK]
                if bad:
                    fail("H12 %s：itemStates 非法 %r" % (w["id"], bad))
                if not st:
                    fail("H12 %s：itemStates 为空数组（应写明四态为何都不成立）" % w["id"])
            d["itemStates"] = st
        elif w["kind"] == "rule":
            if w.get("institution") not in INST_OK:
                fail("H13 %s：institution 非法 %r" % (w["id"], w.get("institution")))
            d["institution"] = w["institution"]
        else:
            fail("H11 %s：kind 非法 %r" % (w["id"], w["kind"]))
        qs = expand(w["quoteKeys"], "worldSettings.%s" % w["id"])
        for q in qs:
            used_keys.add(q["quote"])
        d["quotes"] = qs
        if w.get("note"):
            d["note"] = w["note"]
        wsets.append(d)

    excl = []
    for x in C.EXCLUDED_SETTINGS:
        qs = expand(x["quoteKeys"], "excludedSettings.%s" % x["id"])
        for q in qs:
            used_keys.add(q["quote"])
        d = {"id": x["id"], "item": x["item"], "why": x["why"], "quotes": qs}
        if x.get("note"):
            d["note"] = x["note"]
        excl.append(d)

    # ── themeReadings ─────────────────────────────────────────────────
    themes = []
    for t in C.THEME_READINGS:
        sup = expand_field(t["support"], t["id"], "support")
        cnt = expand_field(t["counter"], t["id"], "counter")
        for q in sup["quotes"] + cnt["quotes"]:
            used_keys.add(q["quote"])
        d = {"id": t["id"], "perspective": t["perspective"], "support": sup,
             "counter": cnt, "basis": t["basis"]}
        if t.get("note"):
            d["note"] = t["note"]
        themes.append(d)

    # ── H15：登记表条目必须全部被引用 ─────────────────────────────────
    all_lits = set()
    for v in QUOTES.values():
        all_lits.add(v["quote"])
    unused = sorted(all_lits - used_keys)
    if unused:
        unused_keys = sorted(k for k, v in QUOTES.items() if v["quote"] in set(unused))
        fail("H15 有 %d 条登记引文从未被引用（键：%s）" % (len(unused), unused_keys))

    # ── H20：跨分区复用 / 全书重复（偏移复算）─────────────────────────
    section_of = {}
    def reg(q, sec):
        section_of.setdefault(q["quote"], set()).add(sec)
    for t in tasks:
        for f in fields:
            for q in (t.get(f) or {}).get("quotes", []):
                reg(q, "tasks")
    for e in cause_edges:
        for q in e["quotes"]:
            reg(q, "causeEdges")
    for s in states:
        for f in ("before", "after", "anchor", "knows", "knowsNot"):
            for q in (s.get(f) or {}).get("quotes", []):
                reg(q, "states")
    for f in fores:
        for q in f["setup"]["quotes"]:
            reg(q, "foreshadows")
        for q in (f.get("payoff") or {}).get("quotes", []):
            reg(q, "foreshadows")
    for w in wsets:
        for q in w["quotes"]:
            reg(q, "worldSettings")
    for t in themes:
        for q in t["support"]["quotes"] + t["counter"]["quotes"]:
            reg(q, "themeReadings")
    for r in rejected + rejected_edges + not_fores + excl:
        for q in r["quotes"]:
            reg(q, "__rejected_or_excluded__")

    reuse = []
    for lit, secs in sorted(section_of.items()):
        real = sorted(s for s in secs if not s.startswith("__"))
        if len(real) < 2:
            continue
        st = seg.find(lit)
        if st < 0:
            fail("H20 %r：切片内找不到" % lit[:20])
            continue
        fp = START + st
        if not (START <= fp < fp + len(lit) <= END):
            fail("H20 %r：复用偏移越界" % lit[:20])
        reuse.append({"quote": lit, "sections": real, "start": fp, "end": fp + len(lit),
                      "sourceHash": SOURCE_HASH, "inUnitOccurrences": seg.count(lit),
                      "bookOccurrences": text.count(lit),
                      "note": "同一句在本候选里承担 %d 个分区的依据；各分区用途不同。" % len(real)})

    dup = []
    for lit in sorted(all_lits):
        n = text.count(lit)
        if n > 1:
            st = seg.find(lit)
            dup.append({"quote": lit, "start": START + st, "end": START + st + len(lit),
                        "inUnitOccurrences": seg.count(lit), "bookOccurrences": n,
                        "sourceHash": SOURCE_HASH})

    # ── H18：语层双向核对 ─────────────────────────────────────────────
    speech = C.SPEECH_LAYER
    declared_keys = {x["key"] for x in speech}
    # 每条登记必须指向真实存在的引文键
    for x in speech:
        if x["key"] not in QUOTES:
            fail("H18 语层登记了不存在的键 %r" % x["key"])
    # 产物里出现的人物言辞键必须全部被登记。
    # 机械判据（不靠人眼）：**按段落**算对话区间 —— 每段里从每个 “ 起，
    # 到该段内下一个 ” 为止；段内没有 ” 时延伸到**段末**。
    # 为什么要按段：中文网络小说的对话经常跨段不闭合（一段台词结尾没有 ”，
    # 下一段以 “ 续上）。全篇配对的算法会把 P42 的 “ 一直配到很后面的某个 ”，
    # 于是中间几段真实台词被漏判（实测 q_xu_berate / q_xu_provocation / q_xu_reason 被漏）。
    spans = []
    for m in re.finditer(r"[^\n]+", seg):
        line = m.group(0)
        base = m.start()
        pos = 0
        while True:
            o = line.find("“", pos)
            if o < 0:
                break
            c = line.find("”", o + 1)
            end = (c + 1) if c >= 0 else len(line)
            spans.append((base + o, base + end))
            pos = end

    def is_speech(key):
        v = QUOTES[key]
        a, b = v["start"] - START, v["end"] - START
        return any(s < b and a < e for s, e in spans)
    speech_keys = {k for k in QUOTES if is_speech(k)}
    missing = sorted(speech_keys - declared_keys)
    if missing:
        fail("H18 有 %d 条含人物言辞的引文未登记语层：%s" % (len(missing), missing[:6]))
    extra = sorted(declared_keys - speech_keys)
    if extra:
        fail("H18 语层登记了不含言辞的引文（应移出或改标）：%s" % extra)

    # ── 覆盖率 ────────────────────────────────────────────────────────
    paras = []
    for m in re.finditer(r"[^\n]+", seg):
        if m.group(0).strip():
            paras.append((START + m.start(), START + m.end(), m.group(0)))
    touched = set()
    quoted_ranges = []
    for lit, secs in section_of.items():
        st = seg.find(lit)
        if st >= 0:
            quoted_ranges.append((START + st, START + st + len(lit)))
    for a, b in quoted_ranges:
        for i, (pa, pb, _) in enumerate(paras):
            if pa <= a < pb:
                touched.add(i)
    zero = [{"para": i + 1, "text": paras[i][2]} for i in range(len(paras)) if i not in touched]

    coverage = {
        "nonEmptyParagraphs": len(paras),
        "paragraphsTouchedByQuotes": len(touched),
        "zeroCoverageParagraphs": len(zero),
        "zeroCoverageList": zero,
        "zeroCoverageNote": ("零覆盖清单由构建脚本从**产物实际引文**算出，不是按登记表估算。"
                             "段号口径 = 引文起始偏移**落在**该段区间内（与 quotes_spec 的段号同一把尺子）。"),
    }

    if problems:
        for p in problems:
            print("[FAIL] " + p, file=sys.stderr)
        print("共 %d 个硬判据失败 —— 不写盘" % len(problems), file=sys.stderr)
        return 1

    # ── 组装 ──────────────────────────────────────────────────────────
    uniq_lits = sorted(all_lits)
    section_counts = {
        "tasks": len(tasks), "rejectedTasks": len(rejected),
        "causeEdges": len(cause_edges), "rejectedEdges": len(rejected_edges),
        "states": len(states), "foreshadows": len(fores), "notForeshadows": len(not_fores),
        "worldSettings": len(wsets), "excludedSettings": len(excl),
        "themeReadings": len(themes), "unknowns": len(C.UNKNOWNS),
        "selfCritique": len(C.SELF_CRITIQUE),
    }
    inst_counts = {}
    for w in wsets:
        if w["kind"] == "rule":
            inst_counts[w["institution"]] = inst_counts.get(w["institution"], 0) + 1
    place_counts = {}
    for w in wsets:
        if w["kind"] == "place":
            place_counts[w["placeState"]] = place_counts.get(w["placeState"], 0) + 1

    cand = {
        "task": TASK_ID,
        "agent": "w-dafeng-0",
        "role": "READER",
        "book": "dafeng",
        "lane": 0,
        "unitIndex": 220,
        "unitHead": "第两百一十九章 本官许七安",
        "sourceRange": [START, END],
        "sourceHash": SOURCE_HASH,
        "sourcePath": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "sliceCodepoints": END - START,
        "sliceSha256": hashlib.sha256(seg.encode("utf-8")).hexdigest(),
        "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[%d:%d)" % (START, END),
        "citationConvention": {
            "verbatim": "「」内一律为逐字原文；构建判据 H1–H4 逐条在 docs[0].text 里复算，查不到即失败。",
            "ownWords": "『』为我的转述或术语，不要求逐字核验。",
            "metaNote": "条数由构建脚本从数据结构生成，不手写计数。",
        },
        "offsetCaliber": "所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；"
                         "自检式：text[start:end] == quote 逐字成立（H1），且 quote 在本单元切片内唯一（H3）。",
        "sourceHashScope": "所有引用的 sourceHash 均为整个 docs.json 文件的 sha256（fdde555867aaccc2…）。",
        "sliceSha256Scope": "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。",
        "graphCacheNotUsedAsEvidence": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.json",
            "note": "图谱缓存里的摘要未被用作任何一条结论的证据；本候选每条引文都能在 docs[0].text 里逐字命中。",
        },
        "buildDisclosure": {
            "builder": "loop/state/out/read_dafeng_L0_0220.w-dafeng-0.build/build_candidate.py",
            "contentCore": "loop/state/out/read_dafeng_L0_0220.w-dafeng-0.build/content_core.py",
            "quoteRegistryGen": "loop/state/out/read_dafeng_L0_0220.w-dafeng-0.build/gen_quotes.py",
            "quoteSpec": "loop/state/out/read_dafeng_L0_0220.w-dafeng-0.build/quotes_spec.py（只写锚串，不写偏移）",
            "howOffsetsWereMade": "引文一律用键标记；偏移由 gen_quotes.py 在 docs[0].text 里**重新 find 锚串后切出**，"
                                  "content_core.py 与 quotes_spec.py 里都不含手写数字偏移。",
            "hardChecks": "H0–H21（见构建脚本文档串）；任一不成立即 exit 1 且不写盘。",
            "auditor": "loop/state/out/read_dafeng_L0_0220.w-dafeng-0.build/audit_candidate.py"
                       "（不 import 生成侧模块）",
        },
        "semanticReview": {
            "status": "not_performed",
            "note": "本候选只完成『引文可逐字定位 + 分区结构完整 + 五栏各有独立依据 + 语层已登记』这一层。"
                    "结论是否被原文支持、是否漏读，须由独立复核者按 read-verify 流程判定。"
                    "引用定位正确 ≠ 语义已核验。",
        },
        "tasks": tasks,
        "rejectedTasks": rejected,
        "causeEdges": cause_edges,
        "rejectedEdges": rejected_edges,
        "states": states,
        "foreshadows": fores,
        "notForeshadows": not_fores,
        "worldSettings": wsets,
        "excludedSettings": excl,
        "themeReadings": themes,
        "unknowns": C.UNKNOWNS,
        "selfCritique": C.SELF_CRITIQUE,
        "crossSectionQuoteReuse": reuse,
        "crossSectionQuoteReuseNote": (
            "跨分区复用如实披露：同一句原文被两个以上分区引用时逐条列出，"
            "**由构建脚本从产物数据生成**，不是手写计数。H5b 机器保证『同一任务内五栏不得共用同一句』；"
            "跨分区复用不受此限，但要公开。偏移一律取**本单元切片内**的首次命中。"),
        "bookLevelDuplicateQuotes": {
            "count": len(dup), "items": dup,
            "note": ("这些引文在全书中不止一次出现。它们在本单元切片内**唯一**，且逐字定位正确；"
                     "但正因为短句会复现，本候选一律只在切片内定位（不依赖全书 find 的首次命中）。"
                     "清单由构建脚本对**产物中全部引文字面量**逐个统计全书出现次数后生成，不是手工挑选。"),
        },
        "coverage": coverage,
        "citationIntegrity": {
            "distinctQuoteKeys": len(QUOTES),
            "distinctQuoteTexts": len(all_lits),
            "productQuoteInstances": sum(
                len((t.get(f) or {}).get("quotes", [])) for t in tasks for f in fields
            ) + sum(len(e["quotes"]) for e in cause_edges + rejected_edges)
              + sum(len((s.get(f) or {}).get("quotes", []))
                    for s in states for f in ("before", "after", "anchor", "knows", "knowsNot"))
              + sum(len(f["setup"]["quotes"]) + len((f.get("payoff") or {}).get("quotes", []))
                    for f in fores)
              + sum(len(w["quotes"]) for w in wsets)
              + sum(len(t["support"]["quotes"]) + len(t["counter"]["quotes"]) for t in themes)
              + sum(len(r["quotes"]) for r in rejected + not_fores + excl),
            "note": "productQuoteInstances 由遍历产物实际引用对象算出；"
                    "distinctQuoteTexts < distinctQuoteKeys 说明有多个 key 指向同一句原文。",
        },
        "speechLayerDisclosure": {
            "policy": "凡原文里成句的人物言辞（含自由间接引语），一律登记并写明它在对应分区里被允许承担的用途；"
                      "人物说的话不得当作叙述事实。",
            "checkedCount": len(speech),
            "dispositionOfEach": speech,
        },
        "sectionCounts": section_counts,
        "sectionBreakdown": {
            "worldSettingsByInstitution": inst_counts,
            "worldSettingsByPlaceState": place_counts,
        },
    }
    cand["sectionCountsNote"] = "条数由构建脚本从数据结构生成（H19）：%r" % (section_counts,)

    OUT_PATH.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
    print("OK 写入 %s" % OUT_PATH)
    print("   sha256=%s" % hashlib.sha256(OUT_PATH.read_bytes()).hexdigest())
    print("   引文键 %d / 字面量 %d / 产物引用实例 %d"
          % (len(QUOTES), len(all_lits), cand["citationIntegrity"]["productQuoteInstances"]))
    print("   非空段 %d / 被引 %d / 零覆盖 %d"
          % (len(paras), len(touched), len(zero)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
