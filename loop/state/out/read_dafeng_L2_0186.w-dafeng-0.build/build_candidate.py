#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组装 loop/state/out/read_dafeng_L2_0186.candidate.json。

设计原则（沿用本通道前序单元的做法，都是被真实事故逼出来的）：
  · **偏移从不手写**：内容层只给段落号＋定位标记，start/end/出现次数/段句分句号由
    spec.Resolver 现取；找不到、越界、区间内命中不唯一 → sys.exit(1)，不写盘。
  · **写完即自检**：本脚本末尾对成品跑一遍不变量（五栏引文不共用、null 有 Note、
    哈希与区间一致）；任何一条不过就 sys.exit(1) 且不留半成品。
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import units  # noqa: E402
import spec  # noqa: E402
from spec import Q  # noqa: E402
import content_tasks  # noqa: E402
import content_edges  # noqa: E402
import content_more as M  # noqa: E402

ROOT = HERE.parents[3]
DOCS = ROOT / spec.DOCS
OUT = ROOT / "loop/state/out/read_dafeng_L2_0186.candidate.json"
TASK_ID = "read:dafeng:L2:0186"
AGENT = "w-dafeng-0"
S, E = spec.RANGE
COLUMNS = ("objective", "obstacle", "action", "result", "cost")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    return sha256_bytes(Path(p).read_bytes())


def main():
    raw = DOCS.read_bytes()
    file_hash = sha256_bytes(raw)
    if file_hash != spec.SOURCE_HASH:
        sys.exit("源文件哈希与任务声明不符：%s" % file_hash)
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    if not text[S:E].startswith("第一百八十六章 失之交臂"):
        sys.exit("切片不以单元标题开头，偏移口径可能错了")
    u = units.build_units(text, S, E)
    R = spec.Resolver(text, u)

    # ---- tasks
    tasks = []
    for t in content_tasks.TASKS:
        item = {"id": t["id"], "who": t["who"], "label": t["label"], "note": t["note"]}
        for col in COLUMNS:
            v = t.get(col)
            if v is None:
                item[col] = None
                item[col + "Note"] = t[col + "Note"]
            else:
                item[col] = {
                    "text": v["text"],
                    "basis": v["basis"],
                    "quotes": R.quotes(v["quotes"]),
                    "note": v["note"],
                }
        tasks.append(item)

    # ---- cause edges / rejected
    def edges(rows):
        out = []
        for e in rows:
            o = {k: v for k, v in e.items() if k != "quotes"}
            o["quotes"] = R.quotes(e["quotes"])
            out.append(o)
        return out

    cause_edges = edges(content_edges.CAUSE_EDGES)
    rejected_edges = edges(content_edges.REJECTED_EDGES)

    # ---- states / knowledge
    states = []
    for s in M.STATES:
        o = {k: v for k, v in s.items() if k != "quotes"}
        o["quotes"] = R.quotes(s["quotes"])
        states.append(o)

    kds = []
    for k in M.KNOWLEDGE_DIFFS:
        o = {k2: v for k2, v in k.items() if k2 != "quotes"}
        o["quotes"] = R.quotes(k["quotes"])
        kds.append(o)

    # ---- foreshadows / notForeshadows
    fs = []
    for f in M.FORESHADOWS:
        o = {k: v for k, v in f.items() if k != "quotes"}
        o["quotes"] = R.quotes(f["quotes"])
        fs.append(o)

    nfs = []
    for f in M.NOT_FORESHADOWS:
        o = {k: v for k, v in f.items() if k != "quotes"}
        o["quotes"] = R.quotes(f["quotes"])
        nfs.append(o)

    # ---- worldSettings / notWorldSettings
    ws = []
    for w in M.WORLD_SETTINGS:
        o = {k: v for k, v in w.items() if k != "quotes"}
        o["quotes"] = R.quotes(w["quotes"])
        if w["kind"] == "place":
            o["placeState"] = w["placeState"]
        elif w["kind"] == "item":
            o["itemStates"] = list(w["itemStates"])
        elif w["kind"] == "rule":
            o["institution"] = w["institution"]
        else:
            sys.exit("未知 kind：%s" % w["kind"])
        ws.append(o)

    nws = []
    for w in M.NOT_WORLD_SETTINGS:
        o = {k: v for k, v in w.items() if k != "quotes"}
        o["quotes"] = R.quotes(w["quotes"])
        nws.append(o)

    # ---- themeReadings
    ths = []
    for th in M.THEME_READINGS:
        o = {"id": th["id"], "perspective": th["perspective"], "basis": th["basis"], "note": th["note"]}
        sup = []
        for x in th["support"]:
            sup.append({"what": x["what"], "quotes": R.quotes(x["quotes"])})
        ctr = []
        for x in th["counter"]:
            ctr.append({"what": x["what"], "quotes": R.quotes(x["quotes"])})
        o["support"], o["counter"] = sup, ctr
        ths.append(o)

    # ---- speech ledger / beats
    ledger = []
    for v in M.SPEECH_LEDGER:
        o = {k: val for k, val in v.items() if k != "quote"}
        o["quote"] = R.quote(v["quote"])
        ledger.append(o)

    beats = []
    for b in M.SCENE_BEATS:
        o = {k: val for k, val in b.items() if k != "quotes"}
        o["quotes"] = R.quotes(b["quotes"])
        beats.append(o)

    nulls = []
    for n in M.NULL_FIELD_CANDIDATES:
        o = {k: val for k, val in n.items() if k != "quotes"}
        o["quotes"] = R.quotes(n["quotes"])
        nulls.append(o)

    # ---- coverage（引文并集对非空白码点的覆盖）
    covered = set()
    for q in R.resolved:
        covered.update(range(q["start"], q["end"]))
    seg = text[S:E]
    for i, ch in enumerate(seg):
        if ch.isspace():
            covered.discard(S + i)
    nonspace = sum(1 for ch in seg if not ch.isspace())
    paras = u[0]
    para_cov, sent_cov, clause_cov = {}, {}, {}
    for pidx, a, b, body in paras:
        n = sum(1 for i in range(a, b) if (i in covered))
        para_cov[pidx] = n
    for sidx, pidx, a, b, stext in u[1]:
        sent_cov[sidx] = sum(1 for i in range(a, b) if i in covered)
    for cidx, pidx, sidx, a, b, ctext in u[2]:
        clause_cov[cidx] = sum(1 for i in range(a, b) if i in covered)
    zero_paras = [{"para": p, "range": [a, b], "text": (body if len(body) <= 60 else body[:57] + "...")}
                  for p, a, b, body in paras if para_cov[p] == 0]
    zero_sents = [{"sent": i, "para": p, "range": [a, b], "text": s}
                  for i, p, a, b, s in u[1] if sent_cov[i] == 0]
    zero_cls = [{"clause": i, "para": p, "sent": si, "range": [a, b], "text": s}
                for i, p, si, a, b, s in u[2] if clause_cov[i] == 0]

    coverage = {
        "nonEmptyParagraphs": len(paras),
        "sentenceUnits": len(u[1]),
        "clauseUnits": len(u[2]),
        "quoteNodes": len(R.resolved),
        "quoteUnionCodepoints": len(covered),
        "nonSpaceCodepoints": nonspace,
        "quoteUnionRatioOfNonSpace": round(len(covered) / nonspace, 4),
        "paragraphsTouchedByAtLeastOneQuote": sum(1 for p in paras if para_cov[p[0]] > 0),
        "zeroCoveredParagraphs": zero_paras,
        "zeroCoveredSentences": zero_sents,
        "zeroCoveredClauses": zero_cls,
        "note": "覆盖只表示该单元至少有一个字符被某条引文引用过，不代表该段已被语义核验。"
                "段级会系统性放过『同段内一句被引、另一句从未被引』，故同时给句级与分句级零覆盖名单。",
    }

    # ---- machine assertions（成品自检）
    def q_ranges(col):
        return [(x["start"], x["end"]) for x in col["quotes"]] if col else []

    overlaps = []
    sent_shared = []
    for t in tasks:
        seen = []
        for col in COLUMNS:
            c = t[col]
            if not c:
                continue
            for x in c["quotes"]:
                for a, b, other in seen:
                    if not (x["end"] <= a or x["start"] >= b):
                        overlaps.append({"task": t["id"], "units": [other, col],
                                         "range": [max(a, x["start"]), min(b, x["end"])]})
                seen.append((x["start"], x["end"], col))
        for i in range(len(COLUMNS)):
            for j in range(i + 1, len(COLUMNS)):
                a, b = t[COLUMNS[i]], t[COLUMNS[j]]
                if not a or not b:
                    continue
                sa = {x["sentUnit"] for x in a["quotes"]}
                sb = {x["sentUnit"] for x in b["quotes"]}
                if sa & sb:
                    sent_shared.append({"task": t["id"], "units": [COLUMNS[i], COLUMNS[j]],
                                        "sentUnits": sorted(sa & sb)})

    null_notes_ok = all(t.get(col + "Note") for t in tasks for col in COLUMNS if t[col] is None)
    all_quotes = R.resolved
    verbatim = all(text[q["start"]:q["end"]] == q["quote"] for q in all_quotes)
    unique_in_range = all(seg.count(q["quote"]) == 1 for q in all_quotes)
    in_range = all(S <= q["start"] < q["end"] <= E for q in all_quotes)
    uniq_strings = len({q["quote"] for q in all_quotes})

    mself = {
        "sourceHashMatchesTask": file_hash == spec.SOURCE_HASH,
        "sliceStartsWithUnitHead": text[S:E].startswith("第一百八十六章 失之交臂"),
        "quoteObjectsResolved": len(all_quotes),
        "allQuotesVerbatim": verbatim,
        "allQuotesUniqueWithinRange": unique_in_range,
        "allQuotesInRange": in_range,
        "uniqueQuoteStrings": uniq_strings,
        "taskColumnsIndependentSentUnitLevel": not sent_shared,
        "taskColumnsIndependentCharSpanLevel": not overlaps,
        "taskColumnOverlaps": overlaps,
        "taskColumnSharedSentUnits": sent_shared,
        "nullColumnsAllHaveNotes": null_notes_ok,
        "note": "以上判据全部由 build_candidate.py 写盘前现算；任一为假即不写盘并以非零码退出。",
    }
    problems = [k for k in ("sourceHashMatchesTask", "sliceStartsWithUnitHead", "allQuotesVerbatim",
                            "allQuotesUniqueWithinRange", "allQuotesInRange",
                            "taskColumnsIndependentSentUnitLevel",
                            "taskColumnsIndependentCharSpanLevel",
                            "nullColumnsAllHaveNotes") if not mself[k]]
    if problems:
        sys.exit("成品自检未通过：%s\n%s" % (problems, json.dumps(
            {"overlaps": overlaps, "sentShared": sent_shared}, ensure_ascii=False)))

    cand = {
        "schemaVersion": "castline-read-candidate/1",
        "task": TASK_ID,
        "agent": AGENT,
        "role": "READER（原文精读工作者）",
        "book": "dafeng",
        "bookTitle": "大奉打更人",
        "lane": 2,
        "unitIndex": 186,
        "unitHead": "第一百八十六章 失之交臂",
        "source": {
            "path": spec.DOCS,
            "sourceHash": file_hash,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
            "segmentSha256": sha256_bytes(seg.encode("utf-8")),
            "segmentSha256Scope": "docs[0].text[start:end] 的 UTF-8 字节 sha256（另起字段，未覆盖 sourceHash）",
            "range": [S, E],
            "offsetBase": spec.OFFSET_BASE,
            "sliceStartsWithUnitHead": True,
            "sliceChars": len(seg),
            "nonEmptyParagraphs": len(paras),
            "sentenceUnits": len(u[1]),
            "clauseUnits": len(u[2]),
            "docsJsonTopLevel": "list（不是 {docs:[...]}）——本候选按实测结构取 [0].text",
            "graphCache": {
                "path": "data/cache/1063b17ca65ec1b76f30e460.json",
                "role": "只读对照，按任务 prompt **不算原文证据**；本候选没有从它搬运任何人物名或结论进正文。",
            },
            "note": "全部引文的 start/end 都是相对 docs[0].text 全文的绝对 codepoint 偏移，不是相对切片。"
                    "构建期对每条引文都断言了：text[start:end] == quote 逐字成立、落在 [S,E) 内、区间内命中唯一。",
        },
        "semanticReview": "not-performed",
        "semanticReviewNote": "本候选只做引文定位的机器可复算（逐字/偏移/区间/全文出现次数/区间内命中数/段号/句单元号）"
                              "与本人通读后的语义判断；**不声称**任何 semanticReview 完成，也不声称独立复核。引文定位正确 ≠ 语义已核验。",
        "basisLegend": {
            "explicit": "原文直述（含叙述层记录下的言语动作；被记录的话本身不因被记录而成事实）",
            "inferred": "我的归纳（原文没有直接写出这一步）",
            "derived": "跨段推导（多段证据合成，单段不足以成立）",
            "unverified": "存疑（区间内无法判定，或存在互相矛盾的说法）",
        },
        "quotePolicy": {
            "bracketConvention": "散文字段里的「…」只允许是 text 的逐字子串；凡我自己的标签／读法一律用『…』，不与原文混淆。"
                                 "构建期抽出全部「…」逐个 find，结果记在 inlineQuoteAudit。",
            "withinTaskUniqueness": "同一任务五栏（objective/obstacle/action/result/cost）的引文互不重复；构建期按句单元与字符区间两套判据断言。",
            "acrossSectionsReuse": "允许跨分区复引同一句作为不同断言的证据；唯一的硬约束是任务内五栏不共用。",
        },
        "columnsIndependent": True,
        "tasks": tasks,
        "causeEdges": cause_edges,
        "rejectedEdges": rejected_edges,
        "states": states,
        "knowledgeDiffs": kds,
        "foreshadows": fs,
        "notForeshadows": nfs,
        "worldSettings": ws,
        "notWorldSettings": nws,
        "themeReadings": ths,
        "speechVsNarration": ledger,
        "sceneBeats": beats,
        "nullFieldCandidates": nulls,
        "unknowns": M.UNKNOWNS,
        "coverage": coverage,
        "selfCritique": M.SELF_CRITIQUE,
        "machineSelfCheck": mself,
        "reverseValidation": {
            "method": "先通读切片，再按『还有哪些原文事实没有被任何分区接住』逐项反查；另按段/句/分句三级零覆盖名单查漏。",
            "foundAndAdded": [
                "河边（W2）：三人在岸边解决膀胱的膨胀，是两场戏之间的实际分隔点，初稿没有登记。",
                "第二处诗引（「莫愁前路无知己，天下谁人不识君」，NF3）：初稿只在成因链里带过，未按『不是伏笔』显式登记。",
                "作者附言与三段图形玩笑（NF4/NF5）：原文实有，初稿没有处置，导致 coverage 里出现无说明的空段。",
                "曹运衙门官员的『责怪的眼神』（P046）：初稿只记了他的恼怒，漏了他当面制止的动作，已补进 T2.action 与 C07。",
                "『赶去河边』一段的转场次序（C10）：初稿把提议与动身写成一条无中间环节的边，补入许七安的赞同句（P057）作为同意环节。",
                "U9（杯碎是否被注意到）与 U10（金步摇等物件后续）：初稿没有把手上的疑点写下来，补入 unknowns。",
            ],
            "checkedAndJudgedNoContent": [
                "「许七安：8====D」三段：形态特殊（图形），但它是作者插入的玩笑，不是情节；登记进 NF4/NW5 而不是忽略。",
                "章首题引两句（P002/P003）：不是情节，但确实与本章人物描写呼应；登记为 F5 并自陈可能过宽。",
                "「人言否？」（P035）：作者对许七安那句排名的吐槽式旁白，无独立事实，已并入 B5 的引文簇。",
                "分隔符「------------」：非语义内容；它已被 B14 作为节拍收尾引用（因此不在零覆盖名单里），空行不参与段级统计。",
            ],
            "zeroCoverageDispositionNote": (
                "**每个零覆盖段逐条给出处置**，而不是只写一句『其余为过场』。"
                "这张表由脚本在写盘前断言**完备**：任一非空白段若没有任何引文覆盖、"
                "又不在本表里 ⇒ 直接拒绝写盘。加这一道的理由：本通道 reviewer 明确要问"
                "『这一段里还漏了什么』，而段级零覆盖名单只能列出编号，看不出我是**判断过**"
                "还是**没读到**——两者在产物上长得一样。"),
            "zeroCoverageDisposition": {
                "P001": "标题行「第一百八十六章 失之交臂」，非正文；标题本身是本候选的 unitHead，已在 source 与 unitHeadCheck 里逐字登记。",
                "P011": "「这是他当年留下来的职业病。」——对 P010（他爱观察微表情）的一句补注，没有新的人物、动作或物件；职业病的具体所指原文未写，已进 U 类不予补全，故不单独引。",
                "P016": "「说话总是带着“呀”“呢”之类的尾音，软濡软濡的，跟谁说过都像是在与情郎交谈。」——对红袖说话方式的旁写。它不改变任何行动或结果，且本候选已在 T1.objective 用她的好恶（P044）与向往（P073）承担她的偏好，此句只是语气细节，故不引。",
                "P017": "「“奴家为几位老爷弹奏一曲吧。”红袖温婉笑道。」——她弹曲的提议。**这是本段唯一一处我犹豫过的漏引**：它是 P018 官员吹捧的直接触发（没有提议就没有吹捧），我在 causeEdges 里没有为它单列边。理由：本候选的 C04 处理的是『宋廷风把话头引到浮香』这一环，若再加一条『她提议弹曲→官员吹捧』，属于把礼节性动作也串成因果链；但它的确是一个动作，故在此显式登记为『判断过而不采纳』，并在 U 类之外单列。",
                "P023": "「浮香的琴技和她的口技一样高超。」——许七安的内心比较，属人物判断（他的相好滤镜），不是对琴技的叙述层定论；本候选在 K2 已处理『叙述层认这层关系』这一点，此句不再另引以免与 K2 重复。",
                "P027": "「“正是。”宋廷风道。」——两字应答，确认官员问的就是浮香花魁。它是 C04 链条上的确认动作，信息量为零（对象已由 P024 的问句给出），不单列。",
                "P035": "「人言否？」——作者对许七安那句排名的吐槽式旁白，无独立事实；已在 checkedAndJudgedNoContent 与 B5 的引文簇里处置。",
                "P036": "「众人忍不住看了许七安几眼。」——众人对他那句排名的反应（侧目）。它是 P033 的即时反应，不含新的行动后果，本候选在 B5 里以场景形式承接，不单引。",
                "P037": "「“真会说笑，大人真会说笑。”漕运衙门的官员干笑道。」——官员打圆场的话，与 P037 后的 P038（朱广孝替同僚解释）构成一组；本候选已在 T2.action 用他两次端杯的动作承担『把场面往回收』，此处是同一功能的第三次重复，不另引。",
                "P039": "「...漕运衙门的官员脸色差点没崩住，努力管理表情，才让自己没有嘲笑出来。」——他忍住笑的表情描写。**这是我第二处犹豫的漏引**：它与 P042「心里不屑，表面依旧笑呵呵」是同一心理的两次描写，本候选在 T2.result 与 C06 里用的是 P042，此处不再重复登记以免同一断言引两段近似文字。",
                "P040": "「浮香是他的相好？堂堂京城第一名妓，会看上你们这种粗鄙的武夫？」——官员的内心反问（自由间接引语），是 P038 之后的心理反应；本候选在 K2.whoDoesNotKnow 与 C06 里已处理『席上没人信』这一层，此句为其具体措辞，不另引。",
                "P043": "「粗俗的男人....红袖花魁眼里的不屑已经不加掩饰，只是她很好的低头饮酒，没让其他人看见。」——她掩藏不屑的动作。**第三处犹豫的漏引**：它是 S1（她对武夫的处置）的一个可观察动作。本候选 S1 用的是散席时的提前离席与不留茶（更硬的两个动作），此处作为同一状态的过程描写不再重复；但若复核认为状态变化应含此动作，S1.after 可补。",
                "P050": "「打茶围结束了。」——场景结束的过渡句，非语义内容。",
                "P075": "「“竟有人说，京城的浮香花魁是他的相好。”」——红袖在第二场席上转述第一场的事（她当笑话讲出来）。**第四处犹豫的漏引**：它是两场席之间唯一的显式连接动作。本候选在 B9.what 里以场景语言写了『席间她把方才的事当笑话说出来』并引了 P071/P072，此句是同一动作的引语本身；若要更严，可把它补进 B9 的引文簇或单列一条 causeEdge。",
                "P079": "「“暗香浮动月黄昏....人如其名，倾国倾城。”」——魏公子对浮香容貌的痴迷评价，人物话。本候选已在 V8 与 T6.obstacle 用相邻的 P078 承担『他见过但见得不多』这一点；此句是他对浮香的形容，不构成新的事实或行动，故不引。",
            },
            "note": "反向验证是我自己在同一区间内做的，不构成独立复核；独立复核要等 read-verify 通道换人来做。",
        },
        "inlineQuoteAudit": None,  # 稍后由 verify_candidate.py 重扫后回填
        "coverageDeclaration": coverage,
        "machineAssertions": mself,
        "unknowns": M.UNKNOWNS,
    }
    # 行内「…」审计：抽出所有字符串字段里的「…」片段，逐个 find
    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from walk(v, path + "." + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from walk(v, path + "[%d]" % i)
        elif isinstance(o, str):
            yield path, o

    inline = {"verbatim": [], "nonVerbatim": []}
    for path, s in walk(cand):
        if path.count(".quote"):
            continue
        for m in __import__("re").finditer(r"「[^」]*」", s):
            frag = m.group(0)[1:-1]
            if len(frag) < 2:
                continue
            # ── 判据必须是**本单元区间内**命中，不是全文命中（2026-10-14 实测修）──
            # 初版只查 `frag in text`（全文 476 万码点），于是我自己写的口语标签
            # （『她后悔』『解释』『紧接着』）因为**别处**恰好有同样两个字而被判为逐字引文，
            # 留在「」里冒充原文。这与本通道的硬红线「引文必须能在原文里 find 到」不同：
            # 复核者按**本单元**读，跨单元命中对他不可见。故改为 seg.count(frag) > 0。
            hit = seg.count(frag) > 0
            rec = {"field": path, "fragment": frag}
            (inline["verbatim"] if hit else inline["nonVerbatim"]).append(rec)
    inline["note"] = ("『…』是我自己的标签，不参与本审计；本审计只扫「…」。"
                      "nonVerbatim 非空即说明我把自己的话写进了引文括号——必须改。")
    if inline["nonVerbatim"]:
        sys.exit("行内引文括号里有非逐字片段：%s" % json.dumps(inline["nonVerbatim"][:5], ensure_ascii=False))
    cand["inlineQuoteAudit"] = {
        "verbatimCount": len(inline["verbatim"]),
        "nonVerbatimCount": 0,
        "verbatim": inline["verbatim"],
        "nonVerbatim": [],
        "note": inline["note"],
    }
    cand["machineSelfCheck"]["inlineBracketsAudited"] = True

    # ── 散文里的段号引用（"P044"）与人物称呼审计 ──────────────────────────
    # 为什么加这一道（2026-10-14 实测）：上一道只检查「」里的片段是否逐字，
    # 但**散文里写着「…（P044）」这种段号引用**从未被机器核对过。实测抓到两处真错：
    #   · R08 写「读书人之间书信往来…（P032）」，而该句实际在 P025，P032 是宋廷风推给许七安；
    #   · R03 写「四个人物（丫鬟、魏公子、李公子等）」，**李公子在全文只出现 3 次且都在
    #     别单元**（平州东方婉蓉、柴府李灵素两处），本单元根本没有这个人。
    # 两条都是「看起来像证据、实际指错」的形态，复核者按本单元读会直接判编造。
    para_by_key = {"P%03d" % pidx: body for pidx, _a, _b, body in paras}
    para_ref_errors, name_errors = [], []
    STOP = set("与和是的了在把被这那等写成给对从到向说听看来去有无不就也都还又而且或及以为上下中后前里外时")
    for path, strv in walk(cand):
        if ".quote" in path:
            continue
        for m in __import__("re").finditer(r"(P\d{3})", strv):
            if m.group(1) not in para_by_key:
                para_ref_errors.append({"field": path, "para": m.group(1), "why": "段号不存在"})
        # 只有**真正把片段挂到某个段号上**的四种写法才检查，避免把相邻两句误配成一对：
        #   A 「frag」（P###）        B P###（…「frag」…）
        #   C （…frag…，P###）        D 「frag」P###
        pairs = []
        for m in __import__("re").finditer(r"[「『]([^」』]{2,})[」』]\s*[（(]\s*(P\d{3})", strv):
            pairs.append((m.group(2), m.group(1)))
        for m in __import__("re").finditer(r"(P\d{3})\s*[（(]([^）)]*)[）)]", strv):
            for f in __import__("re").finditer(r"[「『]([^」』]{2,})[」』]", m.group(2)):
                pairs.append((m.group(1), f.group(1)))
        for m in __import__("re").finditer(r"[（(]([^）)]*?)(P\d{3})\s*[）)]", strv):
            for f in __import__("re").finditer(r"[「『]([^」』]{2,})[」』]", m.group(1)):
                pairs.append((m.group(2), f.group(1)))
        for m in __import__("re").finditer(r"[「『]([^」』]{2,})[」』]\s*(P\d{3})", strv):
            pairs.append((m.group(2), m.group(1)))
        for pk, frag in pairs:
            body = para_by_key.get(pk)
            if body is not None and frag not in body:
                para_ref_errors.append({"field": path, "para": pk, "fragment": frag,
                                        "why": "片段不在它被挂上的那一段里"})
    # 人物称呼：散文里出现「X公子／X娘子／…」而该称呼在本单元不存在 ⇒ 疑似编造人名。
    # 前缀允许被多截一个常用虚字（「与魏公子」→「魏公子」），只要**任一**截法在本单元成立即放行。
    for path, strv in walk(cand):
        if ".quote" in path:
            continue
        # 负向先行断言排除「公子哥们」这种称谓被当作更长名词的一部分的形态；
        # 实测：「原文把它写成公子哥们」会误配出「成公子」，而真正要抓的是
        # 「（丫鬟、魏公子、李公子等）」这种人名并列。
        for m in __import__("re").finditer(r"([\u4e00-\u9fa5])(公子|娘子|姑娘|花魁|老爷|大人)(?![们哥姐弟])", strv):
            tok = m.group(0)
            # 只查**紧邻一个汉字前缀**的称呼（如「李公子」「魏公子」「浮香花魁」）。
            # 放宽到 2 个前缀会大量误配（「写成公子」「或公子」这种跨词边界），
            # 而真编造的人名一定表现为「姓/名 + 称谓」这一个汉字前缀的形态。
            if tok in seg:
                continue
            # 前缀汉字本身在本单元不存在 ⇒ 该姓氏／名字根本没出现过，强证据
            if m.group(1) not in seg:
                name_errors.append({"field": path, "token": tok,
                                    "why": "称呼中的 %r 在本单元区间内一次都没出现（全文 %d 次）"
                                           % (m.group(1), text.count(m.group(1)))})
    cand["proseCitationAudit"] = {
        "paragraphRefs": sum(1 for _p, _s in walk(cand) if ".quote" not in _p for _ in __import__("re").finditer(r"P\d{3}", _s)),
        "paragraphRefErrors": para_ref_errors,
        "personNameErrors": name_errors,
        "note": "散文里的段号（P###）与人物称呼逐个回查本单元切片；段号不存在、或段号旁的引文片段不在该段、"
                "或称呼在本单元不存在 ⇒ 判错并拒绝写盘。这一道补的是『引文逐字』查不到的那类错："
                "引文本身没问题，但**指给它作为依据的那一段**是错的。",
    }
    cand["machineSelfCheck"]["proseCitationsAudited"] = True
    if para_ref_errors or name_errors:
        sys.exit("散文引用审计未通过：%s" % json.dumps(
            {"paraRefErrors": para_ref_errors[:6], "nameErrors": name_errors[:6]}, ensure_ascii=False))

    # ── 零覆盖段处置表必须**完备** ─────────────────────────────────────────
    # 零覆盖名单只说明「这段没被引」，不说明「我判断过它」。两者在产物上长得一样，
    # 而 reviewer 要问的恰恰是『这一段里还漏了什么』。所以要求：**每一个**零覆盖段
    # 都必须在 zeroCoverageDisposition 里有名字，否则拒绝写盘。
    disp = cand["reverseValidation"]["zeroCoverageDisposition"]
    zero_keys = ["P%03d" % z["para"] for z in zero_paras]
    undisposed = [k for k in zero_keys if k not in disp]
    stale = [k for k in disp if k not in zero_keys]
    cand["machineSelfCheck"]["zeroCoverageFullyDisposed"] = not undisposed
    cand["machineSelfCheck"]["zeroCoverageDispositionCount"] = len(disp)
    if undisposed or stale:
        sys.exit("零覆盖段处置表不完备：未处置=%s 多余（该段其实有引文）=%s"
                 % (undisposed, stale))

    OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
    print("写出：%s" % OUT)
    print("sha256：%s" % sha256_file(OUT))
    print("引文节点 %d / 唯一字符串 %d / 覆盖非空白 %.2f%%" %
          (len(all_quotes), uniq_strings, 100.0 * len(covered) / nonspace))
    return 0


if __name__ == "__main__":
    sys.exit(main())
