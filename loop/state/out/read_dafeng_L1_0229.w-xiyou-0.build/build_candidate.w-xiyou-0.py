# -*- coding: utf-8 -*-
"""构建 read:dafeng:L1:0229 候选：把 content_core.py 的引文字符串在切片内定位，
逐条硬校验后写出 loop/state/out/read_dafeng_L1_0229.candidate.json。

不满足任何一条判据 → exit 1，**不写盘**（保证盘上的产物一定通过了全部断言）。

判据（每条都对应一次真实踩坑或提示词的硬性要求）：
  #1  每条引文 text.find(quote) 必须命中，且**切片内唯一**（不唯一即失败，不用「取第一次」糊过去）
  #2  全文偏移自检：docs_text[start:end] == quote，且落在 [S,E) 内
  #3  分析文字里成对出现的 U+300C…U+300D 片段（声明为逐字原文的片段）必须出现在切片内
  #4  {qN} 占位符必须被替换为本条目 quotes[] 第 N 条的**真实起点**；替换后不得有残留占位符
  #5  同一任务内五栏的引文区间**互不重叠**（提示词点名禁止一栏共用一句）
  #6  每条断言必须有 basis，且取值合法
  #7  每个 null 栏位必须有同名的 <栏位>Note（不写理由的 null 判为未标注的未知）
  #8  cost 栏不许出现「待验证/待核」，也不许把纸面规定当已执行结果
  #9  causeEdges 每条必须有 from/to/mechanism 且 mechanism 长度足够（不能是「时间相邻」）
  #10 states 必须有 before/after/anchor（知识差用 known/unknown）
  #11 foreshadows 必须有 setup；unresolved 必须有 payoffNote，resolved 必须有 payoff
  #12 worldSettings：kind 合法；place 必须有 placeState；rule 必须有 institution；每条必须有 explain
  #13 themeReadings：必须有 perspective/support/counter（缺一件不写）
  #14 unknowns 每条必须有 what/why
  #15 产物路径在写盘前必须**不存在**（本轮是新建；若存在则拒绝覆盖并报出）
  #16 semanticReview 不得写成完成
  #17 每个 null 栏位必须同时出现在 nullFieldDisposition 里（两处口径不能各说各话）
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import content_core as C  # noqa: E402

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L1_0229.candidate.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
TASK_ID = "read:dafeng:L1:0229"

FAIL = []


def fail(msg):
    FAIL.append(msg)
    print("[FAIL] " + msg, file=sys.stderr)


# ── 占位符替换（判据 #4）────────────────────────────────────────────────────
PLACEHOLDER = re.compile(r"\{q(\d+)\}")


def subst(text, refs, where):
    """把 {qN} 换成 refs[N] 的真实起点。索引越界/无引文/残留 → 判失败。"""
    if not isinstance(text, str):
        return text
    if "{q" not in text:
        return text

    def rep(m):
        i = int(m.group(1))
        if not refs or i >= len(refs) or refs[i] is None:
            fail("%s：占位符 {q%d} 指向不存在的引文（本条目只有 %d 条）" % (where, i, len(refs or [])))
            return m.group(0)
        return str(refs[i]["start"])

    out = PLACEHOLDER.sub(rep, text)
    if PLACEHOLDER.search(out):
        fail("%s：替换后仍有未处理的占位符" % where)
    return out


def main():
    raw = DOCS.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != SOURCE_HASH:
        fail("docs.json sha256 与任务声明不符：%s != %s" % (got, SOURCE_HASH))
        return 1
    docs = json.loads(raw)
    text = docs[0]["text"]
    S, E = C.SOURCE_RANGE
    slice_ = text[S:E]
    if not slice_.startswith(C.UNIT_HEAD):
        fail("切片不以单元标题开头：%r" % slice_[:40])
        return 1
    slice_sha = hashlib.sha256(slice_.encode("utf-8")).hexdigest()

    if OUT.exists():
        fail("产物已存在，本构建拒绝覆盖：%s（本轮是新建；若为返工应改判据并写明）" % OUT)
        return 1

    quote_index = {}
    order = []

    def locate(quote, where):
        if not isinstance(quote, str) or not quote:
            fail("%s：引文为空" % where)
            return None
        if quote in quote_index:
            return quote_index[quote]
        n_slice = slice_.count(quote)
        if n_slice == 0:
            fail("%s：引文在切片内找不到 → %r" % (where, quote[:60]))
            return None
        if n_slice > 1:
            fail("%s：引文在切片内出现 %d 次（不唯一，拒绝取第一次）→ %r" % (where, n_slice, quote[:60]))
            return None
        k = slice_.find(quote)
        start, end = S + k, S + k + len(quote)
        if text[start:end] != quote:
            fail("%s：全文偏移取回不一致 → %r" % (where, quote[:60]))
            return None
        if not (S <= start < end <= E):
            fail("%s：偏移越界 [%d,%d)" % (where, start, end))
            return None
        rec = {"quote": quote, "start": start, "end": end,
               "docOccurrences": text.count(quote), "sliceOccurrences": n_slice,
               "sourceHash": SOURCE_HASH}
        quote_index[quote] = rec
        order.append(quote)
        return rec

    def ref(quote, where):
        r = locate(quote, where)
        return dict(r) if r else None

    # ── tasks ─────────────────────────────────────────────────────────────
    tasks_out = []
    null_fields = []
    for t in C.TASKS:
        tid = t["id"]
        spans = []
        entry = {"id": tid, "name": t["name"], "actor": t["actor"],
                 "actorBasis": t.get("actorBasis", "explicit"),
                 "actorNote": t.get("actorNote")}
        for field in ("objective", "obstacle", "action", "result", "cost"):
            cell = t.get(field, None)
            note = t.get(field + "Note")
            if cell is None:
                if not note:
                    fail("%s.%s 为 null 却没有 %sNote（不写理由的 null 判为未标注的未知）"
                         % (tid, field, field))
                    continue
                entry[field] = None
                entry[field + "Note"] = note
                null_fields.append((tid, field))
                continue
            if not isinstance(cell, dict) or "text" not in cell or "basis" not in cell:
                fail("%s.%s 结构不合法：缺 text/basis" % (tid, field))
                continue
            if cell["basis"] not in ("explicit", "inferred", "derived", "unverified"):
                fail("%s.%s basis 非法：%r" % (tid, field, cell["basis"]))
            if not cell.get("quotes"):
                fail("%s.%s 没有引文（每栏必须引用各自的原文依据）" % (tid, field))
            refs = [ref(q, "%s.%s" % (tid, field)) for q in cell.get("quotes") or []]
            if field == "cost":                                    # 判据 #8
                blob = json.dumps(cell, ensure_ascii=False)
                for bad in ("待验证", "待核", "待确认"):
                    if bad in blob:
                        fail("%s.cost 含「%s」——那不是代价" % (tid, bad))
                if re.search(r"(法律规定|禁令)", blob):
                    fail("%s.cost 把纸面规定/禁令当已执行结果" % (tid,))
            out_cell = {"text": subst(cell["text"], refs, "%s.%s.text" % (tid, field)),
                        "basis": cell["basis"], "quotes": refs,
                        "note": subst(cell.get("note"), refs, "%s.%s.note" % (tid, field))}
            entry[field] = out_cell
            spans += [(r["start"], r["end"], field) for r in refs if r]
        entry["actorNote"] = subst(entry["actorNote"], [], tid)
        seen = []
        for a, b, fld in spans:
            for a2, b2, fld2 in seen:
                if a < b2 and a2 < b:                              # 判据 #5
                    fail("%s：%s 与 %s 的引文区间重叠 [%d,%d)×[%d,%d)（禁止一栏共用一句）"
                         % (tid, fld2, fld, a2, b2, a, b))
            seen.append((a, b, fld))
        tasks_out.append(entry)

    # ── causeEdges ────────────────────────────────────────────────────────
    edges_out = []
    for e in C.CAUSE_EDGES:
        if not e.get("from") or not e.get("to") or not e.get("mechanism"):
            fail("%s：causeEdge 缺 from/to/mechanism" % e.get("id"))
            continue
        if len(e["mechanism"]) < 30:
            fail("%s：mechanism 太短，疑似以时间相邻充因果" % e["id"])
        if e.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
            fail("%s：causeEdge basis 非法" % e["id"])
        refs = [ref(q, "causeEdge %s" % e["id"]) for q in e.get("quotes") or []]
        if not refs:
            fail("%s：causeEdge 没有引文" % e["id"])
        out = {k: e[k] for k in ("id", "from", "to", "mechanism", "basis") if k in e}
        out["to"] = subst(e["to"], refs, "causeEdge %s.to" % e["id"])
        out["from"] = subst(e["from"], refs, "causeEdge %s.from" % e["id"])
        out["mechanism"] = subst(e["mechanism"], refs, "causeEdge %s.mechanism" % e["id"])
        out["quotes"] = refs
        out["note"] = subst(e.get("note"), refs, "causeEdge %s.note" % e["id"])
        edges_out.append(out)

    rejected_out = []
    for r in C.REJECTED_EDGES:
        if not r.get("wouldBe") or not r.get("whyRejected"):
            fail("%s：rejectedEdge 缺 wouldBe/whyRejected" % r.get("id"))
        rejected_out.append(dict(r))

    # ── states ────────────────────────────────────────────────────────────
    states_out = []
    for s in C.STATES:
        refs = [ref(q, "state %s" % s["id"]) for q in s.get("quotes") or []]
        if not refs:
            fail("%s：state 没有引文" % s["id"])
        if s.get("kind") == "知识差":
            if not s.get("known") or not s.get("unknown"):
                fail("%s：知识差必须写清 known/unknown 两端" % s["id"])
        else:
            for k in ("before", "after", "anchor"):
                if not s.get(k):
                    fail("%s：state 缺 %s（前值/后值/事件锚点）" % (s["id"], k))
        if s.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
            fail("%s：state basis 非法" % s["id"])
        out = {k: s[k] for k in ("id", "who", "kind") if k in s}
        for k in ("before", "after", "known", "unknown", "anchor", "note"):
            if s.get(k):
                out[k] = subst(s[k], refs, "state %s.%s" % (s["id"], k))
        out["basis"] = s["basis"]
        out["quotes"] = refs
        states_out.append(out)

    # ── foreshadows ───────────────────────────────────────────────────────
    fore_out = []
    for f in C.FORESHADOWS:
        if not f.get("setup"):
            fail("%s：伏笔缺 setup（没有铺设不叫伏笔）" % f["id"])
        st = f.get("status")
        if st not in ("resolved", "unresolved", "partial"):
            fail("%s：status 非法或缺失：%r" % (f["id"], st))
        if st == "unresolved" and not f.get("payoffNote"):
            fail("%s：unresolved 必须显式给 payoffNote 说明未回收" % f["id"])
        if st == "resolved" and not f.get("payoff"):
            fail("%s：resolved 必须有 payoff" % f["id"])
        if st == "partial" and not (f.get("payoff") and f.get("payoffNote")):
            fail("%s：partial 必须同时有 payoff 与 payoffNote" % f["id"])
        if f.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
            fail("%s：foreshadow basis 非法" % f["id"])
        refs = [ref(q, "foreshadow %s" % f["id"]) for q in f.get("quotes") or []]
        if not refs:
            fail("%s：伏笔没有引文" % f["id"])
        out = {"id": f["id"], "name": f["name"],
               "setup": subst(f["setup"], refs, "foreshadow %s.setup" % f["id"]),
               "payoff": subst(f.get("payoff"), refs, "foreshadow %s.payoff" % f["id"]),
               "status": st, "basis": f["basis"], "quotes": refs,
               "note": subst(f.get("note"), refs, "foreshadow %s.note" % f["id"])}
        if f.get("payoffNote"):
            out["payoffNote"] = subst(f["payoffNote"], refs, "foreshadow %s.payoffNote" % f["id"])
        fore_out.append(out)

    # ── worldSettings ─────────────────────────────────────────────────────
    ws_out = []
    for w in C.WORLD_SETTINGS:
        if w.get("kind") not in ("rule", "place", "item"):
            fail("%s：worldSettings.kind 非法：%r" % (w.get("id"), w.get("kind")))
            continue
        if not w.get("explain") or len(w["explain"]) < 40:
            fail("%s：worldSettings.explain 缺失或太短（必须写清它如何影响行动/约束/后果）" % w["id"])
        if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            fail("%s：place 必须给 placeState=arrived/mentioned" % w["id"])
        if w["kind"] == "item" and not w.get("itemStates"):
            fail("%s：item 必须给 itemStates 多选" % w["id"])
        if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            fail("%s：rule 必须给 institution=declared/executed/misunderstood" % w["id"])
        quotes = w.get("quotes") or ([w["quote"]] if w.get("quote") else [])
        refs = [ref(q, "worldSetting %s" % w["id"]) for q in quotes]
        if not refs:
            fail("%s：worldSetting 没有引文" % w["id"])
        out = {k: w[k] for k in ("id", "kind", "name") if k in w}
        for k in ("placeState", "itemStates", "institution"):
            if w.get(k):
                out[k] = w[k]
        out["quote"] = refs[0]["quote"] if refs else None
        out["start"] = refs[0]["start"] if refs else None
        out["end"] = refs[0]["end"] if refs else None
        out["sourceHash"] = SOURCE_HASH
        out["quotes"] = refs
        out["explain"] = subst(w["explain"], refs, "worldSetting %s.explain" % w["id"])
        out["basis"] = w.get("basis", "explicit")
        ws_out.append(out)

    # ── themeReadings ─────────────────────────────────────────────────────
    th_out = []
    for t in C.THEME_READINGS:
        for k in ("perspective", "support", "counter"):
            if not t.get(k):
                fail("%s：themeReading 缺 %s（缺一件就不要写）" % (t["id"], k))
        sq = [ref(q, "theme %s support" % t["id"]) for q in t.get("supportQuotes") or []]
        cq = [ref(q, "theme %s counter" % t["id"]) for q in t.get("counterQuotes") or []]
        if not sq or not cq:
            fail("%s：themeReading 必须给 support/counter 的逐字引文" % t["id"])
        allrefs = [r for r in (sq + cq) if r]
        out = {"id": t["id"],
               "perspective": subst(t["perspective"], allrefs, "theme %s.perspective" % t["id"]),
               "support": subst(t["support"], allrefs, "theme %s.support" % t["id"]),
               "supportQuotes": sq,
               "counter": subst(t["counter"], allrefs, "theme %s.counter" % t["id"]),
               "counterQuotes": cq,
               "basis": t.get("basis"),
               "note": subst(t.get("note"), allrefs, "theme %s.note" % t["id"])}
        th_out.append(out)

    # ── unknowns ──────────────────────────────────────────────────────────
    unk_out = []
    for u in C.UNKNOWNS:
        if not u.get("what") or not u.get("why"):
            fail("%s：unknown 缺 what/why" % u.get("id"))
        unk_out.append(dict(u))

    nf_out = [dict(x) for x in C.NOT_FORESHADOWS]
    for x in nf_out:
        if not x.get("item") or not x.get("whyNot"):
            fail("%s：notForeshadows 缺 item/whyNot" % x.get("id"))
    for x in C.EXCLUDED_SETTINGS:
        if not x.get("candidate") or not x.get("whyExcluded"):
            fail("%s：excludedSettings 缺 candidate/whyExcluded" % x.get("id"))

    cand = {
        "task": TASK_ID,
        "agent": "w-xiyou-0",
        "role": "READER",
        "book": "dafeng",
        "lane": 1,
        "unitIndex": 229,
        "unitHead": C.UNIT_HEAD,
        "sourceRange": [S, E],
        "sourceHash": SOURCE_HASH,
        "sliceCodepoints": len(slice_),
        "sliceSha256": slice_sha,
        "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[%d:%d)" % (S, E),
        "tasks": tasks_out,
        "tasksNote": C.TASKS_NOTE,
        "causeEdges": edges_out,
        "causeEdgesNote": C.CAUSE_EDGES_NOTE,
        "rejectedEdges": rejected_out,
        "rejectedEdgesNote": C.REJECTED_EDGES_NOTE,
        "states": states_out,
        "statesNote": C.STATES_NOTE,
        "foreshadows": fore_out,
        "foreshadowsNote": C.FORESHADOWS_NOTE,
        "notForeshadows": nf_out,
        "notForeshadowsNote": C.NOT_FORESHADOWS_NOTE,
        "worldSettings": ws_out,
        "worldSettingsNote": C.WORLD_SETTINGS_NOTE,
        "excludedSettings": [dict(x) for x in C.EXCLUDED_SETTINGS],
        "excludedSettingsNote": C.EXCLUDED_SETTINGS_NOTE,
        "themeReadings": th_out,
        "themeReadingsNote": C.THEME_READINGS_NOTE,
        "unknowns": unk_out,
        "unknownsNote": C.UNKNOWNS_NOTE,
        "selfCritique": [dict(x) for x in C.SELF_CRITIQUE],
        "selfCritiqueNote": C.SELF_CRITIQUE_NOTE,
        "semanticReview": C.SEMANTIC_REVIEW,
        "citationConvention": C.CITATION_CONVENTION,
        "offsetCaliber": C.OFFSET_CALIBER,
        "sourceHashScope": C.SOURCE_HASH_SCOPE,
        "sliceSha256Scope": C.SLICE_SHA_SCOPE,
        "graphCacheNotUsedAsEvidence": C.GRAPH_CACHE_NOT_USED_AS_EVIDENCE,
        "nullFieldDisposition": [dict(x) for x in C.NULL_FIELD_DISPOSITION],
        "nullFieldDispositionNote": C.NULL_FIELD_DISPOSITION_NOTE,
        "predecessorDisclosure": C.PREDECESSOR_DISCLOSURE,
        "priorArtifactDisclosure": C.PRIOR_ARTIFACT_DISCLOSURE,
        "buildDisclosure": C.BUILD_DISCLOSURE,
    }

    if cand["semanticReview"].get("status") != "not_performed":     # 判据 #16
        fail("semanticReview 不得写成已完成（定位正确 ≠ 语义已核验）")

    # 判据 #17：null 栏位与 nullFieldDisposition 必须一一对应
    listed = {(d.get("task"), d.get("field")) for d in C.NULL_FIELD_DISPOSITION}
    for tf in null_fields:
        if tf not in listed:
            fail("%s.%s 是 null 但不在 nullFieldDisposition 清单里（两处口径不一致）" % tf)
    for tf in sorted(listed - set(null_fields)):
        fail("nullFieldDisposition 里列了 %s.%s，但正文该栏不是 null（清单与数据不一致）" % tf)
    print("[info] 裸 null 栏位 %d 个，与 nullFieldDisposition 清单一一对应" % len(null_fields))

    # 判据 #18：自述计数必须与正文数据一致（把 d4 那类自查升级成机器检查）
    # 事故背景：初版 tasksNote 写「8 个 null」而正文只有 5 个 —— 自述与数据不一致，
    # 下游若引用这个数字会直接失真。这里只查「N 个 null」这一类句式，不假装能查所有自述。
    claims = re.findall(r"(\d+)\s*个(?:裸\s*)?null", C.TASKS_NOTE)
    if not claims:
        fail("tasksNote 没有写明 null 栏位数量（自述计数缺失，无法与正文对账）")
    for n in claims:
        if int(n) != len(null_fields):
            fail("tasksNote 自述 %s 个 null，正文实际 %d 个（自述与数据不一致）" % (n, len(null_fields)))
    print("[info] tasksNote 自述的 null 计数 %s 与正文一致" % claims)

    blob = json.dumps(cand, ensure_ascii=False)

    # 判据 #3：分析文字里成对角括号的逐字片段必须出现在切片内
    frags = re.findall("\u300c([^\u300c\u300d]+)\u300d", blob)
    for fr in frags:
        if fr not in slice_:
            fail("分析文字里声明的逐字片段不在切片内：%r" % fr[:60])
    print("[info] 分析文字里的逐字片段（角括号）：%d 个，全部在切片内" % len(frags))

    # 判据 #4 复验：分析文字里的裸数字偏移若出现，必须是某条引文起点
    starts = {r["start"] for r in quote_index.values()}
    nums = {int(m) for m in re.findall(r"偏移\s*(\d+)", blob)}
    bad = sorted(n for n in nums if n not in starts)
    if bad:
        fail("分析文字里出现的手写偏移不是任何引文的起点：%s" % bad)
    if PLACEHOLDER.search(blob):
        fail("产物里仍有未替换的占位符")
    # 注意：**不**用裸的 "{q" 子串判断残留 —— 披露文字里会说明占位符写法本身
    # （{qN} 这种非数字形式不是占位符）。判据与被判对象必须是同一套正则。
    print("[info] 手写偏移 %d 个，全部等于某条引文的真实起点；无残留占位符" % len(nums))

    # 覆盖率
    paras = []
    off = S
    for chunk in slice_.split("\n"):
        paras.append((off, off + len(chunk), chunk))
        off += len(chunk) + 1
    nonempty = [p for p in paras if p[2].strip()]
    spans = sorted((r["start"], r["end"]) for r in quote_index.values())
    touched, zero = 0, []
    for a, b, txt in nonempty:
        if any(a < e and s < b for s, e in spans):
            touched += 1
        else:
            zero.append({"start": a, "end": b, "text": txt})
    cand["coverage"] = {"nonEmptyParagraphs": len(nonempty),
                        "paragraphsTouchedByQuotes": touched,
                        "zeroCoverageParagraphs": len(zero),
                        "zeroCoverageList": zero[:40],
                        "zeroCoverageListTruncated": len(zero) > 40,
                        "zeroCoverageNote": C.COVERAGE_NOTE}

    # 跨分区引用复用（如实披露）
    sections = [("tasks", [q for t in C.TASKS
                           for f in ("objective", "obstacle", "action", "result", "cost")
                           if isinstance(t.get(f), dict) for q in (t[f].get("quotes") or [])]),
                ("causeEdges", [q for e in C.CAUSE_EDGES for q in (e.get("quotes") or [])]),
                ("states", [q for s in C.STATES for q in (s.get("quotes") or [])]),
                ("foreshadows", [q for f in C.FORESHADOWS for q in (f.get("quotes") or [])]),
                ("worldSettings", [q for w in C.WORLD_SETTINGS
                                   for q in (w.get("quotes") or ([w["quote"]] if w.get("quote") else []))]),
                ("themeReadings", [q for t in C.THEME_READINGS
                                   for q in ((t.get("supportQuotes") or []) + (t.get("counterQuotes") or []))])]
    owner = {}
    for name, qs in sections:
        for q in qs:
            owner.setdefault(q, set()).add(name)
    cross = [{"quote": q, "sections": sorted(v)} for q, v in owner.items() if len(v) > 1]
    cand["crossSectionQuoteReuse"] = cross
    cand["crossSectionQuoteReuseNote"] = (
        "跨分区复用如实披露：同一句原文出现在两个不同分区时逐条列出（%d 条）。"
        "判据是同一任务内五栏不得共用一句（判据 #5 已机器检查）；"
        "跨分区说明同一句被用于不同用途，这类复用我没有隐藏，请复核者按用途逐条判断是否成立。" % len(cross))

    if FAIL:
        print("\n构建失败：%d 条判据不通过，**未写盘**。" % len(FAIL), file=sys.stderr)
        return 1

    OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("已写出 %s" % OUT)
    print("sha256 %s" % hashlib.sha256(OUT.read_bytes()).hexdigest())
    # 引文实例数（每条 quotes[] 条目算一次，含跨分区复用）与不同引文串数分开报，
    # 避免把同一个数印两遍造成「引文很多」的错觉（工作量冒充质量）。
    n_inst = sum(len(v) for v in owner.values())
    print("不同引文串 %d 条 / 引文实例 %d 次（跨分区复用 %d 条） / 覆盖非空段落 %d/%d"
          % (len(order), n_inst, len(cross), touched, len(nonempty)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
