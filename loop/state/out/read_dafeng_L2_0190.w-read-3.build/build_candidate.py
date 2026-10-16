#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 loop/state/out/read_dafeng_L2_0190.candidate.json。

**偏移从不手写**：内容模块只给 (段号, 原文子串)，start/end、出现次数、
段/句/分句归属全部由本脚本从 docs[0].text 现取。任一条引文出问题
（找不到、本段不唯一、越界）⇒ 立即 sys.exit(1) 且**不写盘**。

写盘前的硬断言（任一为假即不写盘）：
  H1 sourceHash == task.sourceHash
  H2 docs[0].text[S:E] 以 unitHead 开头、长度 == E-S
  Q1 每条引文 text[start:end] == quote
  Q2 每条引文落在 [S,E) 内
  Q3 每条引文本区间内命中唯一
  C1 同一任务五栏按**字符区间重叠**判零共用
  C2 同一任务五栏按**句单元**判零共用
  N1 空栏（null）全部带同名 <栏位>Note
  B1 行内「…」全部是本区间逐字子串
  P1 散文里的 P### 段号存在，且段号旁的引文确实在该段；人物名在区间内存在
  Z1 每个零覆盖非空段都在 zeroCoverageDisposition 里有处置说明
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import units                      # noqa: E402
import spec as spec_mod           # noqa: E402
import content_tasks as CT        # noqa: E402
import content_edges as CE        # noqa: E402
import content_more as CM         # noqa: E402
import content_theme as CX        # noqa: E402
import content_zero as CZ         # noqa: E402
import content_letters as CL      # noqa: E402

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
GRAPH = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"
OUT = ROOT / "loop/state/out/read_dafeng_L2_0190.candidate.json"

TASK_ID = "read:dafeng:L2:0190"
AGENT = "w-read-3"
BOOK = "dafeng"
BOOK_TITLE = "大奉打更人"
LANE = 2
UNIT_INDEX = 190
S, E = 691573, 697332
TASK_SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
GRAPH_SHA = "98370a39df4f8105063004d6bc8194e50aa8008e111a584ffec32f7ad14a14df"

BASIS_LEGEND = {
    "explicit": "原文直述（含叙述层记录下的言语动作；被记录的话本身不因被记录而成事实）",
    "inferred": "我的归纳（原文没有直接写出这一步）",
    "derived": "跨段推导（多段证据合成，单段不足以成立）",
    "unverified": "存疑（区间内无法判定，或存在互相矛盾的说法）",
}

# 人物名/称谓白名单：散文里出现即须在区间内出现过（P1 的第三道）
KNOWN_NAMES = [
    "许七安", "紫阳居士", "杨恭", "张行英", "魏渊", "谨言", "张慎", "怀庆", "临安",
    "采薇", "浮生", "浮香", "玲月", "铃音", "辞旧", "二叔", "婶婶", "院长", "首辅",
    "亚圣", "佛陀", "巫神教", "云鹿书院", "打更人", "教坊司", "驿站", "青州", "云州",
    "禹州", "豫州", "漳州", "南疆", "极渊", "亚圣学宫", "虎贲卫",
]


def main() -> int:
    raw = DOCS.read_bytes()
    got_hash = hashlib.sha256(raw).hexdigest()
    if got_hash != TASK_SOURCE_HASH:
        print("[FATAL] H1 源哈希不符：%s" % got_hash, file=sys.stderr)
        return 1
    doc = json.loads(raw.decode("utf-8"))
    if not isinstance(doc, list):
        print("[FATAL] docs.json 顶层不是 list：%r" % type(doc), file=sys.stderr)
        return 1
    text = doc[0]["text"]
    seg = text[S:E]
    if not seg.startswith(CT.TITLE):
        print("[FATAL] H2 切片不以 unitHead 开头：%r" % seg[:40], file=sys.stderr)
        return 1
    if len(seg) != E - S:
        print("[FATAL] H2 切片长度 %d != %d" % (len(seg), E - S), file=sys.stderr)
        return 1

    idx = units.unit_index(text, S, E)
    R = spec_mod.Resolver(text, S, E, idx)

    # ── 解析内容模块 ──────────────────────────────────────────────
    tasks = []
    for t in CT.TASKS:
        cols = {}
        for col in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(col)
            if v is None:
                cols[col] = None
                continue
            cols[col] = {
                "text": v["text"],
                "basis": v["basis"],
                "quotes": R.qs(v["quote_specs"], "%s.%s" % (t["id"], col)),
                "note": v["note"],
            }
        tasks.append({
            "id": t["id"], "who": t["who"], "label": t["label"], "note": t["note"],
            **cols,
            **{k: v for k, v in t.items() if k.endswith("Note")},
        })

    cause_edges = []
    for c in CE.CAUSE_EDGES:
        cause_edges.append({
            "id": c["id"], "from": c["from"], "to": c["to"],
            "mechanism": c["mechanism"], "basis": c["basis"], "note": c["note"],
            "quotes": R.qs(c["quote_specs"], c["id"]),
        })
    rejected = [{"id": r["id"], "candidate": r["candidate"], "why": r["why"],
                 "quotes": R.qs(r["quote_specs"], r["id"])} for r in CE.REJECTED_EDGES]
    states = [{"id": s["id"], "who": s["who"], "before": s["before"], "after": s["after"],
               "anchor": s["anchor"], "basis": s["basis"], "note": s["note"],
               "quotes": R.qs(s["quote_specs"], s["id"])} for s in CE.STATES]
    kdiffs = [{"id": k["id"], "what": k["what"], "whoKnows": k["whoKnows"],
               "whoDoesNotKnow": k["whoDoesNotKnow"], "basis": k["basis"], "note": k["note"],
               "quotes": R.qs(k["quote_specs"], k["id"])} for k in CE.KNOWLEDGE_DIFFS]

    fores = [{"id": f["id"], "name": f["name"], "setup": f["setup"], "payoff": f["payoff"],
              "status": f["status"], "unresolvedReason": f["unresolvedReason"],
              "basis": f["basis"], "note": f["note"],
              "quotes": R.qs(f["quote_specs"], f["id"])} for f in CM.FORESHADOWS]
    not_fores = [{"id": n["id"], "candidate": n["candidate"], "why": n["why"],
                  "quotes": R.qs(n["quote_specs"], n["id"])} for n in CM.NOT_FORESHADOWS]

    wsettings = []
    for w in CM.WORLD_SETTINGS:
        rec = {"id": w["id"], "kind": w["kind"], "name": w["name"], "explain": w["explain"],
               "basis": w["basis"], "quotes": R.qs(w["quote_specs"], w["id"])}
        if w["kind"] == "place":
            rec["placeState"] = w["placeState"]
        elif w["kind"] == "item":
            rec["itemStates"] = list(w["itemStates"])
        elif w["kind"] == "rule":
            rec["institution"] = w["institution"]
        wsettings.append(rec)
    not_wsettings = [{"id": n["id"], "candidate": n["candidate"], "why": n["why"],
                      "quotes": R.qs(n["quote_specs"], n["id"])} for n in CM.NOT_WORLD_SETTINGS]

    themes = []
    for th in CX.THEME_READINGS:
        themes.append({
            "id": th["id"], "perspective": th["perspective"], "basis": th["basis"],
            "note": th["note"],
            "support": [{"what": s["what"], "quotes": R.qs(s["quote_specs"], th["id"] + ".support")}
                        for s in th["support"]],
            "counter": [{"what": c["what"], "quotes": R.qs(c["quote_specs"], th["id"] + ".counter")}
                        for c in th["counter"]],
        })

    letters = [{"id": l["id"], "ordinal": l["ordinal"], "addressee": l["addressee"],
                "contentBrief": l["contentBrief"], "basis": l["basis"], "note": l["note"],
                "quotes": R.qs(l["quote_specs"], l["id"])} for l in CL.LETTERS]

    speech = [{"id": v["id"], "speaker": v["speaker"], "kind": v["kind"],
               "factStatus": v["factStatus"], "quote": R.qs(v["quote_specs"], v["id"])[0]}
              for v in CX.SPEECH_VS_NARRATION]
    beats = [{"id": b["id"], "range": b["range"], "what": b["what"],
              "quotes": R.qs(b["quote_specs"], b["id"])} for b in CX.SCENE_BEATS]
    nulls = [{"id": n["id"], "task": n["task"], "field": n["field"], "why": n["why"],
              "quotes": R.qs(n["quote_specs"], n["id"])} for n in CX.NULL_FIELD_CANDIDATES]

    candidate = {
        "schemaVersion": "castline-read-candidate/1",
        "task": TASK_ID,
        "agent": AGENT,
        "role": "READER（原文精读工作者）",
        "book": BOOK,
        "bookTitle": BOOK_TITLE,
        "lane": LANE,
        "unitIndex": UNIT_INDEX,
        "unitHead": CT.TITLE,
        "source": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
            "sourceHash": TASK_SOURCE_HASH,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
            "segmentSha256": hashlib.sha256(seg.encode("utf-8")).hexdigest(),
            "segmentSha256Scope": "docs[0].text[start:end] 的 UTF-8 字节 sha256（另起字段，未覆盖 sourceHash）",
            "range": [S, E],
            "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
            "sliceStartsWithUnitHead": True,
            "sliceChars": len(seg),
            "nonEmptyParagraphs": sum(1 for p in idx["paras"] if p[0] is not None),
            "sentenceUnits": len(idx["sents"]),
            "clauseUnits": len(idx["clauses"]),
            "docsJsonTopLevel": "list（不是 {docs:[...]}）——本候选按实测结构取 [0].text",
            "graphCache": {
                "path": "data/cache/1063b17ca65ec1b76f30e460.json",
                "sha256": GRAPH_SHA,
                "role": "只读对照，按任务 prompt **不算原文证据**；本候选没有从它搬运任何人物名或结论进正文。",
            },
            "note": "全部引文的 start/end 都是相对 docs[0].text 全文的绝对 codepoint 偏移，不是相对切片。"
                    "构建期对每条引文都断言了：text[start:end] == quote 逐字成立、落在 [S,E) 内、"
                    "区间内命中唯一、并现算段/句/分句归属。",
        },
        "semanticReview": "not-performed",
        "semanticReviewNote": "本候选只做引文定位的机器可复算（逐字/偏移/区间/全文出现次数/区间内命中数/"
                              "段号/句单元号）与本人通读后的语义判断；**不声称**任何 semanticReview 完成，"
                              "也不声称独立复核。引文定位正确 ≠ 语义已核验。",
        "basisLegend": BASIS_LEGEND,
        "quotePolicy": {
            "bracketConvention": "散文字段里的直角引号只允许包住 text 的逐字子串；"
                                 "凡我自己的标签／读法一律用『…』，不与原文混淆。"
                                 "构建期抽出全部直角引号内容逐个 find，结果记在 inlineQuoteAudit。",
            "withinTaskUniqueness": "同一任务五栏（objective/obstacle/action/result/cost）的引文互不重复；"
                                    "构建期按句单元与字符区间两套判据断言。",
            "acrossSectionsReuse": "允许跨分区复引同一句作为不同断言的证据；唯一的硬约束是任务内五栏不共用。",
        },
        "columnsIndependent": True,
        "tasks": tasks,
        "causeEdges": cause_edges,
        "rejectedEdges": rejected,
        "states": states,
        "knowledgeDiffs": kdiffs,
        "foreshadows": fores,
        "notForeshadows": not_fores,
        "worldSettings": wsettings,
        "notWorldSettings": not_wsettings,
        "themeReadings": themes,
        "letters": letters,
        "speechVsNarration": speech,
        "sceneBeats": beats,
        "nullFieldCandidates": nulls,
        "unknowns": CX.UNKNOWNS,
        "selfCritique": CX.SELF_CRITIQUE,
    }

    problems = []

    # ── Q1/Q2/Q3：引文逐字、区间内唯一（Resolver 已在解析期断言，这里复算登记）──
    all_quotes = []

    def collect(o, path="root"):
        if isinstance(o, dict):
            if "quote" in o and "start" in o and "end" in o:
                all_quotes.append((path, o))
            for k, v in o.items():
                collect(v, path + "." + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                collect(v, "%s[%d]" % (path, i))

    collect(candidate)
    for path, q in all_quotes:
        if text[q["start"]:q["end"]] != q["quote"]:
            problems.append("Q1 引文不逐字：%s %r" % (path, q["quote"][:30]))
        if not (S <= q["start"] and q["end"] <= E):
            problems.append("Q2 引文越界：%s" % path)
        if seg.count(q["quote"]) != 1:
            problems.append("Q3 区间内命中不唯一（%d）：%s" % (seg.count(q["quote"]), path))
        if q["sourceHash"] != TASK_SOURCE_HASH:
            problems.append("Q4 sourceHash 不符：%s" % path)

    # ── C1/C2：同一任务五栏不共用 ───────────────────────────────
    def span(q):
        return (q["start"], q["end"])

    col_overlaps = []
    shared_sents = []
    for t in tasks:
        cols = [(c, t[c]) for c in ("objective", "obstacle", "action", "result", "cost") if t.get(c)]
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                (n1, c1), (n2, c2) = cols[i], cols[j]
                for q1 in c1["quotes"]:
                    for q2 in c2["quotes"]:
                        a1, b1 = span(q1)
                        a2, b2 = span(q2)
                        if a1 < b2 and a2 < b1:
                            col_overlaps.append((t["id"], n1, n2, a1, b1, a2, b2))
                        if q1["sentUnit"] == q2["sentUnit"] and q1["sentUnit"] is not None:
                            shared_sents.append((t["id"], n1, n2, q1["sentUnit"]))
    if col_overlaps:
        problems.append("C1 任务五栏引文字符区间重叠 %d 处：%r" % (len(col_overlaps), col_overlaps[:3]))
    if shared_sents:
        problems.append("C2 任务五栏共用句单元 %d 处：%r" % (len(shared_sents), shared_sents[:3]))

    # ── N1：空栏必须有同名 Note ─────────────────────────────────
    for t in tasks:
        for col in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(col) is None:
                key = col + "Note"
                if not t.get(key):
                    problems.append("N1 %s.%s 为 null 但没有 %s" % (t["id"], col, key))

    # ── B1：行内「…」逐字审计 ───────────────────────────────────
    good, bad = R.inline_audit(candidate)
    if bad:
        problems.append("B1 行内「…」有 %d 处不是本区间逐字子串：%r" % (len(bad), bad[:5]))

    # ── P1：散文里的段号与人物名 ────────────────────────────────
    pa = R.prose_audit(candidate, KNOWN_NAMES)
    if pa["errors"]:
        problems.append("P1 散文引用审计 %d 处错：%r" % (len(pa["errors"]), pa["errors"][:5]))

    # ── 覆盖与零覆盖处置 ────────────────────────────────────────
    covered = set()
    for _, q in all_quotes:
        covered.update(range(q["start"], q["end"]))
    non_space = {i for i in range(S, E) if not text[i].isspace()}
    para_cov = {}
    for o, li, ls, le, cs, ce in idx["paras"]:
        if o is None:
            continue
        para_cov[o] = any(i in covered for i in range(cs, ce))
    zero_paras = sorted(o for o, c in para_cov.items() if not c)
    sent_cov = {sn: any(i in covered for i in range(s, e)) for sn, o, s, e in idx["sents"]}
    clause_cov = {cn: any(i in covered for i in range(s, e)) for cn, o, sn, s, e in idx["clauses"]}
    zero_sents = sorted(sn for sn, c in sent_cov.items() if not c)
    zero_clauses = sorted(cn for cn, c in clause_cov.items() if not c)

    coverage = {
        "nonEmptyParagraphs": len(para_cov),
        "sentenceUnits": len(idx["sents"]),
        "clauseUnits": len(idx["clauses"]),
        "quoteNodes": len(all_quotes),
        "quoteUnionCodepoints": len(covered),
        "nonSpaceCodepoints": len(non_space),
        "quoteUnionRatioOfNonSpace": round(len(covered & non_space) / max(1, len(non_space)), 4),
        "paragraphsTouchedByAtLeastOneQuote": sum(1 for c in para_cov.values() if c),
        "zeroCoveredParagraphs": [
            {"para": "P%03d" % o, "range": [cs, ce],
             "text": text[cs:ce]}
            for o, li, ls, le, cs, ce in idx["paras"] if o in zero_paras
        ],
        "zeroCoveredSentences": [
            {"sent": sn, "para": "P%03d" % next(o for sn2, o, s2, e2 in idx["sents"] if sn2 == sn),
             "range": [s, e], "text": text[s:e]}
            for sn, o, s, e in idx["sents"] if sn in zero_sents
        ],
        "zeroCoveredClauses": [
            {"clause": cn, "para": "P%03d" % o, "sent": sn, "range": [s, e], "text": text[s:e]}
            for cn, o, sn, s, e in idx["clauses"] if cn in zero_clauses
        ],
        "note": "覆盖只表示该单元至少有一个字符被某条引文引用过，不代表该段已被语义核验。"
                "段级会系统性放过『同段内一句被引、另一句从未被引』，故同时给句级与分句级零覆盖名单。",
    }
    candidate["coverage"] = coverage
    candidate["coverageDeclaration"] = dict(coverage)

    # ── Z1：零覆盖段处置完备性 ──────────────────────────────────
    disp = CZ.ZERO_DISPOSITION
    missing = [o for o in zero_paras if ("P%03d" % o) not in disp]
    extra = [k for k in disp if k not in {"P%03d" % o for o in zero_paras}]
    if missing:
        problems.append("Z1 零覆盖段未给处置：%r" % ["P%03d" % o for o in missing])
    if extra:
        problems.append("Z1b 处置表里有多余的段（该段其实有引文）：%r" % extra)

    # 零覆盖段处置里引用的原文片段也要逐字可查（用带段落号的形式登记）
    disp_rec = {}
    for k, v in disp.items():
        if isinstance(v, dict):
            rec = {"disposition": v["disposition"]}
            if v.get("quotes"):
                pn = int(k[1:])
                rec["quotes"] = R.qs([(pn, q) for q in v["quotes"]], "zero." + k)
            disp_rec[k] = rec
        else:
            disp_rec[k] = {"disposition": v}

    candidate["reverseValidation"] = {
        "method": "先通读切片（139 个非空段逐段读完），再按『还有哪些原文事实没有被任何分区接住』逐项反查；"
                  "另按段/句/分句三级零覆盖名单查漏。",
        "foundAndAdded": CZ.REVERSE_FOUND,
        "checkedAndJudgedNoContent": CZ.REVERSE_NO_CONTENT,
        "zeroCoverageDispositionNote": "**每个零覆盖段逐条给出处置**，而不是只写一句『其余为过场』。"
                                       "这张表由脚本在写盘前断言**完备**：任一非空白段若没有任何引文覆盖、"
                                       "又不在本表里 ⇒ 直接拒绝写盘。加这一道的理由：本通道 reviewer 明确要问"
                                       "『这一段里还漏了什么』，只查已写项结构性地发现不了遗漏。",
        "zeroCoverageDisposition": disp_rec,
        "note": "反向验证是我自己在同一区间内做的，不构成独立复核；独立复核要等 read-verify 通道换人来做。",
    }

    candidate["inlineQuoteAudit"] = {
        "verbatimCount": len(good),
        "nonVerbatimCount": len(bad),
        "verbatim": good,
        "nonVerbatim": bad,
        "note": "『…』是我自己的标签，不参与本审计；本审计只扫直角引号。"
                "nonVerbatim 非空即说明我把自己的话写进了引文括号——必须改。"
                "审计范围说明（独立校验脚本查出的边界）：本对象与 quotePolicy 自身是**描述约定**的元字段，"
                "写盘时在审计之后生成，故不在被扫范围内；正文分区全部在范围内。",
    }
    candidate["proseCitationAudit"] = {
        "paragraphRefs": pa["paragraphRefs"],
        "paragraphRefErrors": [e for e in pa["errors"] if e["kind"].startswith("para") or e["kind"].startswith("quote")],
        "personNameErrors": [e for e in pa["errors"] if e["kind"] == "name-not-in-range"],
        "note": "散文里的段号（P###）与人物称呼逐个回查本单元切片；段号不存在、"
                "或段号旁的引文片段不在该段、或称呼在本单元不存在 ⇒ 判错并拒绝写盘。",
    }

    mcheck = {
        "sourceHashMatchesTask": got_hash == TASK_SOURCE_HASH,
        "sliceStartsWithUnitHead": seg.startswith(CT.TITLE),
        "quoteObjectsResolved": len(all_quotes),
        "allQuotesVerbatim": not any(p.startswith("Q1") for p in problems),
        "allQuotesUniqueWithinRange": not any(p.startswith("Q3") for p in problems),
        "allQuotesInRange": not any(p.startswith("Q2") for p in problems),
        "uniqueQuoteStrings": len({q["quote"] for _, q in all_quotes}),
        "taskColumnsIndependentSentUnitLevel": not shared_sents,
        "taskColumnsIndependentCharSpanLevel": not col_overlaps,
        "taskColumnOverlaps": col_overlaps,
        "taskColumnSharedSentUnits": shared_sents,
        "nullColumnsAllHaveNotes": not any(p.startswith("N1") for p in problems),
        "note": "以上判据全部由 build_candidate.py 写盘前现算；任一为假即不写盘并以非零码退出。",
        "inlineBracketsAudited": not bad,
        "proseCitationsAudited": not pa["errors"],
        "zeroCoverageFullyDisposed": not missing and not extra,
        "zeroCoverageDispositionCount": len(disp_rec),
    }
    candidate["machineSelfCheck"] = mcheck
    candidate["machineAssertions"] = dict(mcheck)

    if problems:
        for p in problems:
            print("[FATAL] %s" % p, file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("已写盘：%s" % OUT)
    print("  引文对象 %d（唯一串 %d）｜任务 %d｜边 %d（拒绝 %d）｜状态 %d｜知识差 %d｜伏笔 %d（未回收 %d）｜"
          "世界设定 %d｜主题 %d｜信 %d｜人物话 %d｜场景 %d｜unknowns %d"
          % (len(all_quotes), mcheck["uniqueQuoteStrings"], len(tasks), len(cause_edges), len(rejected),
             len(states), len(kdiffs), len(fores), sum(1 for f in fores if f["status"] != "resolved-in-range"),
             len(wsettings), len(themes), len(letters), len(speech), len(beats), len(CX.UNKNOWNS)))
    print("  覆盖：段 %d/%d、句 %d/%d、分句 %d/%d"
          % (coverage["paragraphsTouchedByAtLeastOneQuote"], coverage["nonEmptyParagraphs"],
             coverage["sentenceUnits"] - len(zero_sents), coverage["sentenceUnits"],
             coverage["clauseUnits"] - len(zero_clauses), coverage["clauseUnits"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
