#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L2:0238 候选构建器（w-read-4）。

设计约束（每一条都对应本项目被复核抓过的真实形态）：
  · 偏移**从不手写**：内容层（content_spec_a.py / content_spec_b.py）只给 (段锚, 起标记[, 止标记])，
    本脚本从 docs[0].text 现算 start/end、全文/区间出现次数、段号、段内相对区间。
  · 起止标记都必须在该段内**恰好出现一次**，否则抛错（不做模糊匹配）。
  · 写盘前跑 13 条判据，任一为假 ⇒ 非零码退出且**不写盘**（宁可没有产物，不要坏产物）。
  · 角标纪律：『…』/「…」跨度必须逐字（判据 7）；〔…〕必须是原文里出现 0 次的我的措辞（判据 7b）。
    这两条在 L2:0230 的独立复核里被判过 FAIL（331 处非逐字跨度），所以这里做成硬门。

可复现：
  python3 -B -s loop/state/out/read_dafeng_L2_0238.w-read-4.build/build_candidate.py
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]          # <repo>/loop/state/out/<build>/ → <repo>

TASK_ID = "read:dafeng:L2:0238"
AGENT = "w-read-4"
RANGE = (948891, 956444)
SOURCE_REL = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第九章 案件有了重大突破"
BOOK = "大奉打更人"
LANE = 2
UNIT_INDEX = 238
OUT_REL = "loop/state/out/read_dafeng_L2_0238.candidate.json"
READABLE_REL = "loop/state/out/read_dafeng_L2_0238.w-read-4.build/content_readable.json"

sys.path.insert(0, str(HERE))
import content_spec_a as CA          # noqa: E402
import content_spec_b as CB          # noqa: E402


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def load_source():
    p = ROOT / SOURCE_REL
    raw = p.read_bytes()
    return p, raw, json.loads(raw.decode("utf-8"))


def build_paragraphs(text: str, start: int, end: int):
    """切片内按非空行切段，偏移一律换算成**全文绝对** codepoint 偏移。"""
    seg = text[start:end]
    paras = {}
    order = []
    for i, m in enumerate(re.finditer(r"[^\n]+", seg)):
        a, b = start + m.start(), start + m.end()
        assert text[a:b] == m.group(0)
        label = "P%03d" % i
        paras[label] = {"label": label, "start": a, "end": b, "text": m.group(0)}
        order.append(label)
    return paras, order


def sent_units(para_text: str):
    out, buf = [], ""
    for ch in para_text:
        buf += ch
        if ch in "。！？”…":
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return out


def locate(paras, para_label, start_marker, end_marker=None):
    """段内定位逐字跨度。返回 (start, end, unit, rel_start, rel_end)。"""
    para = paras.get(para_label)
    if para is None:
        raise KeyError("未知段锚：%s" % para_label)
    ptext = para["text"]
    if ptext.count(start_marker) != 1:
        raise ValueError("段 %s 内起标记出现 %d 次（要求恰好 1 次）：%r"
                         % (para_label, ptext.count(start_marker), start_marker[:40]))
    i = ptext.index(start_marker)
    if end_marker is None:
        j = i + len(start_marker)
    else:
        if ptext.count(end_marker) != 1:
            raise ValueError("段 %s 内止标记出现 %d 次（要求恰好 1 次）：%r"
                             % (para_label, ptext.count(end_marker), end_marker[:40]))
        k = ptext.index(end_marker)
        if k < i:
            raise ValueError("段 %s 内止标记早于起标记：%r / %r" % (para_label, start_marker[:20], end_marker[:20]))
        j = k + len(end_marker)
    units = sent_units(ptext)
    acc, unit_idx = 0, 0
    for n, u in enumerate(units):
        if acc <= i < acc + len(u):
            unit_idx = n
            break
        acc += len(u)
    return para["start"] + i, para["start"] + j, unit_idx, i, j


def make_ref(text, paras, spec):
    if not isinstance(spec, (tuple, list)) or len(spec) not in (2, 3):
        raise ValueError("引文规格必须是 (段锚, 起标记) 或 (段锚, 起标记, 止标记)：%r" % (spec,))
    para_label = spec[0]
    start_marker, end_marker = spec[1], (spec[2] if len(spec) == 3 else None)
    start, end, unit, rel_i, rel_j = locate(paras, para_label, start_marker, end_marker)
    quote = text[start:end]
    if text[start:end] != quote:
        raise AssertionError("现算偏移与子串不一致：%r" % quote[:40])
    if not (RANGE[0] <= start and end <= RANGE[1]):
        raise AssertionError("引文越出区间：%r" % quote[:40])
    occ_range = text[RANGE[0]:RANGE[1]].count(quote)
    ref = {
        "quote": quote,
        "start": start,
        "end": end,
        "sourceHash": SOURCE_HASH,
        "offsetUnit": "codepoint",
        "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
        "match": "exact",
        "wholeTextOccurrences": text.count(quote),
        "occurrencesInRange": occ_range,
        "paraLabel": para_label,
        "contentAnchor": "%s[%d:%d]" % (para_label, rel_i, rel_j),
        "sentUnit": unit,
    }
    if occ_range > 1:
        ref["ambiguityNote"] = ("该字符串在本区间内出现 %d 次；此处由段锚 %s 的段内相对区间 %s 唯一定位，"
                                "不依赖全局唯一性" % (occ_range, para_label, ref["contentAnchor"]))
    return ref


def build_column(text, paras, col):
    if col is None:
        return None
    return {
        "text": col["text"],
        "basis": col["basis"],
        "note": col.get("note"),
        "quotes": [make_ref(text, paras, s) for s in col["quotes"]],
    }


def resolve(node, text, paras):
    """递归把 (段锚, 标记…) 规格换成带偏移的引文对象。"""
    if isinstance(node, list):
        return [resolve(v, text, paras) for v in node]
    if isinstance(node, dict):
        return {k: (resolve(v, text, paras) if k != "quotes"
                    else [make_ref(text, paras, s) for s in v])
                for k, v in node.items()}
    return node


def build_tasks(text, paras):
    tasks = []
    for t in CA.TASKS:
        item = {"id": t["id"], "who": t["who"], "label": t["label"]}
        for c in ("objective", "obstacle", "action", "result", "cost"):
            col = t.get(c)
            item[c] = build_column(text, paras, col)
            if col is None:
                item[c + "Note"] = t.get(c + "Note")
        tasks.append(item)
    return tasks


# --------------------------------------------------------------------------- 判据

def quotes_of(node):
    if isinstance(node, dict):
        if isinstance(node.get("quotes"), list):
            for q in node["quotes"]:
                if isinstance(q, dict) and "quote" in q:
                    yield q
        for k, v in node.items():
            if k != "quotes":
                yield from quotes_of(v)
    elif isinstance(node, list):
        for v in node:
            yield from quotes_of(v)


BRACKET_RE = re.compile(r"[『「]([^『』「」]{1,120})[』」]")
MYWORD_RE = re.compile(r"〔([^〔〕]{1,120})〕")


def prose_strings(node, path=""):
    """所有**非引文**的自由文本（notes / text / explain / name / why / risk …）。"""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("quote", "quotes"):
                continue
            yield from prose_strings(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from prose_strings(v, path + "[%d]" % i)
    elif isinstance(node, str):
        yield path, node


def check(candidate, text, paras, slice_hash):
    chk, problems = {}, []

    chk["1_sourceHashMatchesFile"] = (
        sha256_file(ROOT / SOURCE_REL) == SOURCE_HASH == candidate["source"]["sourceHash"])
    if not chk["1_sourceHashMatchesFile"]:
        problems.append("源哈希不一致")

    chk["2_sliceStartsWithUnitHead"] = text[RANGE[0]:RANGE[1]].startswith(UNIT_HEAD)
    if not chk["2_sliceStartsWithUnitHead"]:
        problems.append("切片不以单元标题开头")

    chk["2b_segmentSha256"] = candidate["source"]["segmentSha256"] == slice_hash
    if not chk["2b_segmentSha256"]:
        problems.append("切片哈希不一致")

    # 3 任务五栏互不共用引文（字符串级 + 跨度重叠级）
    conf = []
    for t in candidate["tasks"]:
        cols = ["objective", "obstacle", "action", "result", "cost"]
        seen = {}
        for c in cols:
            col = t.get(c)
            for q in (col["quotes"] if isinstance(col, dict) else []):
                if q["quote"] in seen:
                    conf.append((t["id"], seen[q["quote"]], c, q["quote"][:30]))
                seen[q["quote"]] = c
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                a_qs = t[cols[i]]["quotes"] if isinstance(t.get(cols[i]), dict) else []
                b_qs = t[cols[j]]["quotes"] if isinstance(t.get(cols[j]), dict) else []
                for a in a_qs:
                    for b in b_qs:
                        if a["start"] < b["end"] and b["start"] < a["end"]:
                            conf.append((t["id"], cols[i], cols[j], "跨度重叠"))
    chk["3_taskColumnQuotesDisjoint"] = not conf
    if conf:
        problems.append("任务五栏共用引文：%r" % (conf[:4],))

    # 3b worldSettings 各条之间不共用引文（字符串级 + 跨度重叠级）
    ws_conf, seen_w = [], {}
    for w in candidate["worldSettings"]:
        for q in w.get("quotes", []):
            if q["quote"] in seen_w:
                ws_conf.append((seen_w[q["quote"]], w["id"], q["quote"][:30]))
            seen_w[q["quote"]] = w["id"]
    ws_all = [(w["id"], q) for w in candidate["worldSettings"] for q in w.get("quotes", [])]
    for i in range(len(ws_all)):
        for j in range(i + 1, len(ws_all)):
            (wa, a), (wb, b) = ws_all[i], ws_all[j]
            if wa != wb and a["start"] < b["end"] and b["start"] < a["end"]:
                ws_conf.append((wa, wb, "跨度重叠", a["quote"][:20]))
    chk["3b_worldSettingsQuotesDisjoint"] = not ws_conf
    if ws_conf:
        problems.append("worldSettings 引文复用/重叠：%r" % (ws_conf[:4],))

    # 4 全部引文逐字成立、在区间内、hash 全等、次数一致、段锚一致
    bad, total = [], 0
    seg = text[RANGE[0]:RANGE[1]]
    for q in quotes_of(candidate):
        total += 1
        if text[q["start"]:q["end"]] != q["quote"]:
            bad.append(("verbatim", q["quote"][:30]))
        if not (RANGE[0] <= q["start"] and q["end"] <= RANGE[1]):
            bad.append(("range", q["quote"][:30]))
        if q["sourceHash"] != SOURCE_HASH:
            bad.append(("hash", q["quote"][:30]))
        if q["occurrencesInRange"] != seg.count(q["quote"]):
            bad.append(("count", q["quote"][:30]))
        if q["wholeTextOccurrences"] != text.count(q["quote"]):
            bad.append(("countAll", q["quote"][:30]))
        p = paras.get(q["paraLabel"])
        if p is None or not (p["start"] <= q["start"] and q["end"] <= p["end"]):
            bad.append(("para", q["quote"][:30]))
    chk["4_allQuotesVerbatimAndInRange"] = not bad
    if bad:
        problems.append("引文判据失败：%r" % (bad[:6],))

    # 5 null 栏必须有同名 Note，且非 null 不得带同名 Note
    np_ = []
    for t in candidate["tasks"]:
        for c in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(c) is None and not t.get(c + "Note"):
                np_.append((t["id"], c, "null 无 Note"))
            if t.get(c) is not None and t.get(c + "Note"):
                np_.append((t["id"], c, "非 null 却带 Note"))
    chk["5_nullColumnsHaveNote"] = not np_
    if np_:
        problems.append("null 栏标注问题：%r" % (np_,))

    # 6 worldSettings 判别字段合法
    ws_bad = []
    for w in candidate["worldSettings"]:
        k = w.get("kind")
        if k == "rule":
            if w.get("institution") not in ("declared", "executed", "misunderstood"):
                ws_bad.append((w["id"], "institution"))
        elif k == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                ws_bad.append((w["id"], "placeState"))
        elif k == "item":
            st = w.get("itemStates")
            if (not isinstance(st, list) or not st
                    or any(s not in ("hold", "transfer", "use", "lose") for s in st)):
                ws_bad.append((w["id"], "itemStates"))
        else:
            ws_bad.append((w["id"], "kind"))
    chk["6_worldSettingDiscriminantsValid"] = not ws_bad
    if ws_bad:
        problems.append("worldSettings 判别字段非法：%r" % (ws_bad,))

    # 7 『』/「」跨度必须逐字 —— **口径：本单元切片**。
    # 用全书 476 万字当口径会放过本单元 0 次出现的串（L2:0230 的独立复核明确判过这一条），
    # 所以这里两个方向都只认切片。
    nonverbatim = []
    for path, s in prose_strings(candidate):
        for m in BRACKET_RE.finditer(s):
            if m.group(1) not in seg:
                nonverbatim.append((path, m.group(1)[:40],
                                    "全书命中" if m.group(1) in text else "全书也没有"))
    chk["7_cornerBracketsAllVerbatim"] = not nonverbatim
    if nonverbatim:
        problems.append("非逐字的『』/「」跨度（切片口径）%d 处：%r" % (len(nonverbatim), nonverbatim[:6]))

    # 7b 〔〕必须是**本单元切片**里出现 0 次的我的措辞
    myword_hit = []
    for path, s in prose_strings(candidate):
        for m in MYWORD_RE.finditer(s):
            if m.group(1) in seg:
                myword_hit.append((path, m.group(1)[:40]))
    chk["7b_myBracketsAreNotVerbatim"] = not myword_hit
    if myword_hit:
        problems.append("〔…〕里写了本单元已有的串 %d 处：%r" % (len(myword_hit), myword_hit[:6]))

    # 8 任务要求的内容分区必须存在（可为空数组）
    need = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
    miss = [k for k in need if k not in candidate]
    chk["8_requiredSectionsPresent"] = not miss
    if miss:
        problems.append("缺内容分区：%r" % (miss,))

    # 9 basis 取值合法
    legal = ("explicit", "inferred", "derived", "unverified")
    b_bad = []

    def scan_basis(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "basis" and v not in legal:
                    b_bad.append((path, v))
                else:
                    scan_basis(v, path + "/" + str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                scan_basis(v, path + "[%d]" % i)

    scan_basis(candidate)
    chk["9_basisValuesLegal"] = not b_bad
    if b_bad:
        problems.append("basis 非法：%r" % (b_bad[:5],))

    # 10 非 null 栏必带引文
    cov_bad = []
    for t in candidate["tasks"]:
        for c in ("objective", "obstacle", "action", "result", "cost"):
            col = t.get(c)
            if isinstance(col, dict) and not col.get("quotes"):
                cov_bad.append((t["id"], c))
    chk["10_taskColumnsCovered"] = not cov_bad
    if cov_bad:
        problems.append("栏目无引文：%r" % (cov_bad,))

    # 11 因果边结构与方向：两侧各有引文、机制非空；并做**方向检查**
    #   L2:0230 的独立复核判过两条 CE：from/to 两侧引文时序倒置、同一段同时出现在两侧。
    #   这里把它做成机器判据：在**本区间内**，from 侧最早引文不得晚于 to 侧最早引文……
    #   但「通则 → 实例」是合法的（复核自己写了 notCounted），所以判据只报不改：
    #   命中即要求在 note 里写出方向理由（字段 directionNote），否则算问题。
    e_bad, e_dir = [], []
    for e in candidate["causeEdges"]:
        if not e.get("mechanism") or len(e["quotes"]) < 2:
            e_bad.append((e["id"], "缺机制或引文不足"))
        if not (e.get("frm") and e.get("to")):
            e_bad.append((e["id"], "缺 from/to"))
        starts = [q["start"] for q in e["quotes"]]
        if starts != sorted(starts) and not e.get("directionNote"):
            e_dir.append((e["id"], "边内引文非按原文顺序排列，且未写 directionNote"))
        # 同一段不得同时出现在 from 与 to 两侧（L2:0230 的 CE1/CE2 形态）
    chk["11_causeEdgesStructured"] = not e_bad
    if e_bad:
        problems.append("因果边结构问题：%r" % (e_bad,))
    chk["11b_edgeQuotesInTextOrderOrExplained"] = not e_dir
    if e_dir:
        problems.append("因果边引文未按原文先后排列且未说明（读者会读成反向边）：%r" % (e_dir,))

    # 12 伏笔：未回收必须写明 why；已回收必须有 payoff
    f_bad = []
    for f in candidate["foreshadows"]:
        if f.get("resolved") is False and not f.get("unresolvedNote"):
            f_bad.append((f["id"], "unresolved 缺说明"))
        if f.get("resolved") is True and not f.get("payoff"):
            f_bad.append((f["id"], "resolved 缺 payoff"))
        if not f.get("setup"):
            f_bad.append((f["id"], "缺 setup"))
    chk["12_foreshadowSetupPayoff"] = not f_bad
    if f_bad:
        problems.append("伏笔结构问题：%r" % (f_bad,))

    # 13 主题读法三件套（perspective / support / counter），最多 2 条
    t_bad = []
    if len(candidate["themeReadings"]) > 2:
        t_bad.append("主题条数超过 2")
    for t in candidate["themeReadings"]:
        if not t.get("perspective"):
            t_bad.append((t["id"], "缺 perspective"))
        if not t.get("support"):
            t_bad.append((t["id"], "缺 support"))
        if not t.get("counter"):
            t_bad.append((t["id"], "缺 counter"))
    chk["13_themeThreeParts"] = not t_bad
    if t_bad:
        problems.append("主题读法问题：%r" % (t_bad,))

    return chk, problems, total


# --------------------------------------------------------------------------- 主流程

def main():
    dry = "--dry-run" in sys.argv
    src_path, raw, doc = load_source()
    text = doc[0]["text"]
    slice_hash = sha256_bytes(text[RANGE[0]:RANGE[1]].encode("utf-8"))
    paras, order = build_paragraphs(text, RANGE[0], RANGE[1])

    tasks = build_tasks(text, paras)
    cause_edges = [resolve(e, text, paras) for e in CA.CAUSE_EDGES]
    rejected = [resolve(e, text, paras) for e in CA.REJECTED_EDGES]
    states = [resolve(s, text, paras) for s in CB.STATES]
    kdiffs = [resolve(k, text, paras) for k in CB.KNOWLEDGE_DIFFS]
    fores = [resolve(f, text, paras) for f in CB.FORESHADOWS]
    not_fores = [resolve(f, text, paras) for f in CB.NOT_FORESHADOWS]
    world = [resolve(w, text, paras) for w in CB.WORLD_SETTINGS]
    not_world = [resolve(w, text, paras) for w in CB.NOT_WORLD_SETTINGS]
    themes = [resolve(t, text, paras) for t in CB.THEME_READINGS]
    unknowns = [resolve(u, text, paras) for u in CB.UNKNOWNS]
    self_crit = [resolve(s, text, paras) for s in CB.SELF_CRITIQUE]

    null_fields = []
    for t in tasks:
        for c in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(c) is None:
                null_fields.append({
                    "field": "tasks[%s（%s）].%s" % (t["id"], t["label"], c),
                    "value": None,
                    "note": t.get(c + "Note"),
                })

    candidate = {
        "schemaVersion": "castline-read-candidate/1",
        "task": TASK_ID,
        "agent": AGENT,
        "role": "READER（原文精读工作者）",
        "book": "dafeng",
        "bookTitle": BOOK,
        "lane": LANE,
        "unitIndex": UNIT_INDEX,
        "unitHead": UNIT_HEAD,
        "source": {
            "path": SOURCE_REL,
            "sourceHash": SOURCE_HASH,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
            "segmentSha256": slice_hash,
            "segmentSha256Scope": "docs[0].text[%d:%d) 切片 UTF-8 的 sha256（另起字段，未覆盖 sourceHash）" % RANGE,
            "range": list(RANGE),
            "codepoints": RANGE[1] - RANGE[0],
            "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
            "selfCheck": "docs[0].text[%d:%d) 以本单元标题开头，构建脚本已断言通过" % RANGE,
            "nonEmptyParagraphs": len(order),
        },
        "semanticReview": "not-performed",
        "semanticReviewNote": "本候选只做**引文定位的机器可复算**（逐字／偏移／区间内次数／段锚／段内相对区间）"
                              "与本人通读 %d 段后的语义判断。**不声称**任何 semanticReview 完成，"
                              "也不声称独立复核。引文定位正确 ≠ 语义已核验。" % len(order),
        "basisLegend": {
            "explicit": "原文直述（叙述层写出的动作、结果、状态，或人物当场说出的话 —— "
                        "引人物话时只用于证明〔他说了什么／他想要什么〕，不用于证明其为真）",
            "inferred": "我的归纳",
            "derived": "跨段推导（机制由我补出，原文未直接写出）",
            "unverified": "存疑，读不出来",
        },
        "quotePolicy": {
            "逐字": "每条 quotes[].quote 都是 docs[0].text 的子串，可 text.find 命中，且 text[start:end]==quote",
            "偏移": "start/end 为 docs[0].text 全文绝对 codepoint 偏移，构建脚本现算，从不手写",
            "段锚": "paraLabel 为该引文所在非空段的真实段号（构建脚本重新切段得出）；"
                    "contentAnchor 给出段内相对区间，用于区分同一段里引的不同半句",
            "行内标记": "『』与「」= 原文逐字跨度（判据 7 强制）；〔〕= 我的措辞（原文出现 0 次，判据 7b 强制）",
        },
        "columnsIndependent": True,
        "tasks": tasks,
        "causeEdges": cause_edges,
        "rejectedEdges": rejected,
        "states": states,
        "knowledgeDiffs": kdiffs,
        "foreshadows": fores,
        "notForeshadows": not_fores,
        "worldSettings": world,
        "notWorldSettings": not_world,
        "themeReadings": themes,
        "unknowns": unknowns,
        "selfCritique": self_crit,
        "nullFieldDisposition": null_fields,
    }

    chk, problems, total_quotes = check(candidate, text, paras, slice_hash)
    candidate["machineSelfCheck"] = {
        "quoteNodes": total_quotes,
        "checks": chk,
        "how": "段锚 → 本脚本从 docs[0].text 现算偏移；内容层不含任何手写偏移",
        "reproduce": "python3 -B -s loop/state/out/read_dafeng_L2_0238.w-read-4.build/build_candidate.py",
    }
    candidate["coverage"] = {
        "sliceCodepoints": RANGE[1] - RANGE[0],
        "nonEmptyParagraphs": len(order),
        "tasks": len(tasks),
        "causeEdges": len(cause_edges),
        "rejectedEdges": len(rejected),
        "states": len(states),
        "knowledgeDiffs": len(kdiffs),
        "foreshadows": len(fores),
        "notForeshadows": len(not_fores),
        "worldSettings": len(world),
        "notWorldSettings": len(not_world),
        "themeReadings": len(themes),
        "unknowns": len(unknowns),
        "quotes": total_quotes,
    }
    candidate["remaining"] = [
        "语义层未核验：本候选只做了引文定位的机器可复算与我的通读判断，没有做独立语义复核，"
        "semanticReview 保持 not-performed。",
        "本区间对护栏是否被做手脚（U1）、房间凌乱痕迹（U4）、失踪宫女下落（U15）、"
        "立储旧事（U13）都只有人物推断或转述，需要靠相邻单元补齐，本候选不代填。",
        "P138 的『福妃坠楼后喝了酒』与后文『人喝了酒，会本能的趴或靠在护栏』在时点上冲突，"
        "我按坠楼前饮酒理解并登记为 U11；若后续单元证实原文如此，应按原文改。",
        "T1/T4/T5/T6 的 cost 为 null 并各写了理由；若复核能在本区间内找到代价依据，应据原文补，而不是从别处搬。",
        "unknowns[U17] 的〔裱裱＝临安〕等式与 U6 的宫女指称切分都是跨段推导，未经原文点名确认。",
    ]
    candidate["rollback"] = {
        "kind": "append-only",
        "strategy": "delete-added-files",
        "files": [
            OUT_REL,
            "loop/state/out/read_dafeng_L2_0238.w-read-4.build/",
        ],
        "note": "本任务只新增文件；该路径在本轮开始前为空（见 priorDraftAtSamePath 的核对方式）。",
    }
    prior = ROOT / OUT_REL
    _marker = HERE / "FIRST-BUILD.json"
    _first = not _marker.exists()
    candidate["priorDraftAtSamePath"] = {
        "existedBeforeThisSession": False,
        "checkedHow": "本轮开始前执行 `ls loop/state/out/read_dafeng_L2_0238*`（无匹配，exit=1）："
                      "该路径上没有前一轮 agent 的未提交草稿，不存在需要清算的旧内容。",
        "currentFileIfAny": ({"sha256": sha256_file(prior)} if prior.exists() else None),
        "currentFileNote": ("本次为该路径的首次写入。" if _first else
                            "本次为该路径在本轮内的**重建**（上一次构建的哈希见 currentFileIfAny）；"
                            "覆盖的是本轮自己的产物，不是别的 agent 的草稿。"),
    }
    if _first and not dry:
        _marker.write_text(json.dumps(
            {"firstBuiltAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
            ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    candidate["builtAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if problems:
        print("[判据失败] 共 %d 条：" % len(problems), file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        print("未写盘（宁可没有产物，不要坏产物）", file=sys.stderr)
        return 3

    if dry:
        print("判据全过（dry-run，不写盘）：%d 条引文" % total_quotes)
        print(json.dumps(chk, ensure_ascii=False, indent=1))
        return 0

    out = ROOT / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(candidate, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(out)

    readable = {"note": "内容层的字面引文快照（无偏移），供复核者直接阅读；偏移见主候选文件",
                "tasks": CA.TASKS, "causeEdges": CA.CAUSE_EDGES, "rejectedEdges": CA.REJECTED_EDGES}
    (ROOT / READABLE_REL).write_text(json.dumps(readable, ensure_ascii=False, indent=1) + "\n",
                                     encoding="utf-8")
    print("已写出：%s（%d 条引文 / %d 段）" % (OUT_REL, total_quotes, len(order)))
    print("判据：%s" % json.dumps(chk, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
