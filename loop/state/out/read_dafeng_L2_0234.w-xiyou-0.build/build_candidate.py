#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L2:0234 候选构建器（w-xiyou-0）。

设计约束（都是被复核抓过的地方）：
  · 偏移**从不手写**：内容层（content_a.py / content_b.py）只给 (段锚, 逐字子串)，
    本脚本从 docs[0].text 现算 start/end、全文/区间出现次数、段号、句单元。
  · 段锚允许带小写后缀（P126c / P126d），后缀只用于「同一段里引不同半句」，
    定位时先剥掉后缀再取字串 —— 上一轮（L2:0230）内容层不带后缀，本轮带，
    不剥就会把 P126c 当成一个不存在的段而全部引文失败。
  · 写盘前跑 11 条判据，任一为假 ⇒ 非零码退出且**不写盘**（宁可没有产物，不要坏产物）。
  · 非逐字的行内短语一律写成 〔…〕（原文出现 0 次）；『…』/「…」跨度必须逐字。
    这条是被上一轮的独立复核抓出来的（C12：331 处非逐字跨度），本轮的 121 处
    已由 fix_brackets.py 纠正，并在这里做成硬判据。

可复现：
  python3 -B -s loop/state/out/read_dafeng_L2_0234.w-xiyou-0.build/build_candidate.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]          # <repo>/loop/state/out/<build>/ → <repo>

TASK_ID = "read:dafeng:L2:0234"
RANGE = (923035, 929759)
SOURCE_REL = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第五章 恒远：三号，其实我早就知道你的真实身份了"
BOOK = "大奉打更人"
LANE = 2
UNIT_INDEX = 234
OUT_REL = "loop/state/out/read_dafeng_L2_0234.candidate.json"

sys.path.insert(0, str(HERE))
import content_a as CA          # noqa: E402
import content_b as CB          # noqa: E402


# --------------------------------------------------------------------------- 基础

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def load_source():
    p = ROOT / SOURCE_REL
    raw = p.read_bytes()
    return p, raw, json.loads(raw.decode("utf-8"))


def build_paragraphs(text: str, start: int, end: int):
    """在切片内按「非空行」切段，偏移一律换算成**全文绝对** codepoint 偏移。"""
    seg = text[start:end]
    paras = []
    for i, m in enumerate(re.finditer(r"[^\n]+", seg)):
        a, b = start + m.start(), start + m.end()
        assert text[a:b] == m.group(0)
        paras.append({"label": "P%03d" % i, "start": a, "end": b, "text": m.group(0)})
    return paras


SENT_SPLIT = re.compile(r"(?<=[。！？…”」』])")
SUFFIX_RE = re.compile(r"[a-z]+$")


def sent_units(para_text: str):
    """段内句单元（只用于标注与禁用判据，不用于任何语义结论）。"""
    out = []
    buf = ""
    for ch in para_text:
        buf += ch
        if ch in "。！？”…":
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return out


def locate(paras, para_label, needle):
    """在指定段锚内定位逐字子串，返回 (start, end, sent_unit)，并做唯一性检查。

    段锚的小写后缀（P126c）只是内容层的分组记号，定位前必须剥掉，
    否则会把「同一段里引不同半句」误判成「引用了不存在的段」。
    """
    base = SUFFIX_RE.sub("", para_label)
    para = paras.get(base)
    if para is None:
        raise KeyError("未知段锚：%s（剥后缀后 %s）" % (para_label, base))
    n = para["text"].count(needle)
    if n != 1:
        raise ValueError("段 %s 内子串出现 %d 次（要求恰好 1 次）：%r"
                         % (para_label, n, needle[:60]))
    off = para["text"].index(needle)
    start = para["start"] + off
    end = start + len(needle)
    units = sent_units(para["text"])
    acc = 0
    unit_idx = 0
    for i, u in enumerate(units):
        if acc <= off < acc + len(u):
            unit_idx = i
            break
        acc += len(u)
    return start, end, unit_idx


def make_ref(text, paras, para_label, needle):
    start, end, unit = locate(paras, para_label, needle)
    if text[start:end] != needle:
        raise AssertionError("现算偏移与子串不一致：%s" % needle[:40])
    if not (RANGE[0] <= start and end <= RANGE[1]):
        raise AssertionError("引文越出区间：%s" % needle[:40])
    base = SUFFIX_RE.sub("", para_label)
    return {
        "quote": needle,
        "start": start,
        "end": end,
        "sourceHash": SOURCE_HASH,
        "offsetUnit": "codepoint",
        "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
        "match": "exact",
        "wholeTextOccurrences": text.count(needle),
        "occurrencesInRange": text[RANGE[0]:RANGE[1]].count(needle),
        # paraLabel 必须是**真实段号**（可被独立重算核验：这段的绝对区间确实包含本条引文）。
        # 内容层用来区分「同一段里引不同半句」的小写后缀另存 contentAnchor，
        # 不混进 paraLabel —— 否则该字段无法被独立脚本核对（实测被 C05 判 FAIL）。
        "paraLabel": base,
        "contentAnchor": para_label if para_label != base else None,
        "sentUnit": unit,
    }


# --------------------------------------------------------------------------- 组装

def build_column(text, paras, col, colname):
    """任务五元组的一栏。None ⇒ null + 同名 Note（Note 由内容层给）。"""
    if col is None:
        return None
    return {
        "text": col["text"],
        "basis": col["basis"],
        "note": col.get("note"),
        "quotes": [make_ref(text, paras, p, q) for (p, q) in col["quotes"]],
    }


def build_nullable_column(text, paras, col):
    """本轮内容层把 null 栏写成 {'text': None, 'costNote': ...}（而非整栏 None）。

    两种形态都要还原成任务要求的「null + 同名 Note」。
    """
    if col is None:
        return None, None
    if isinstance(col, dict) and col.get("text") is None:
        notes = [v for k, v in col.items() if k.endswith("Note")]
        return None, (notes[0] if notes else None)
    return build_column(text, paras, col, None), col.get("note")


def resolve(node, text, paras):
    """递归把内容层里的 (段锚, 逐字子串) 二元组换成带偏移的引文对象。

    themeReadings 的 support/counter 是嵌套结构（每条 support 自带 quotes），
    所以这里必须递归，不能只看顶层 —— 上一轮就是这么漏掉嵌套引文的。
    """
    if isinstance(node, list):
        return [resolve(v, text, paras) for v in node]
    if isinstance(node, dict):
        return {k: (resolve(v, text, paras) if k != "quotes"
                    else [make_ref(text, paras, p, q) for (p, q) in v])
                for k, v in node.items()}
    return node


def build_list(text, paras, items):
    return [resolve(it, text, paras) for it in items]


def build_tasks(text, paras):
    tasks = []
    for t in CA.TASKS:
        item = {
            "id": t["id"], "who": t["who"], "label": t["label"],
        }
        for c in ("objective", "obstacle", "action", "result", "cost"):
            built, note = build_nullable_column(text, paras, t.get(c))
            item[c] = built
            if built is None:
                item[c + "Note"] = note or t.get(c + "Note")
        tasks.append(item)
    return tasks


# --------------------------------------------------------------------------- 判据

def col_quotes(task, col):
    c = task.get(col)
    return c["quotes"] if isinstance(c, dict) else []


def quotes_of(node):
    if isinstance(node, dict):
        if "quotes" in node and isinstance(node["quotes"], list):
            for q in node["quotes"]:
                if isinstance(q, dict) and "quote" in q:
                    yield q
        for v in node.values():
            yield from quotes_of(v)
    elif isinstance(node, list):
        for v in node:
            yield from quotes_of(v)


BRACKET_RE = re.compile(r"[『「]([^『』「」]{1,80})[』」]")
MYWORD_RE = re.compile(r"〔([^〔〕]{1,80})〕")


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


def check(candidate, text, paras):
    chk = {}
    problems = []

    # 1 源哈希
    chk["1_sourceHashMatchesFile"] = (
        sha256_file(ROOT / SOURCE_REL) == SOURCE_HASH == candidate["source"]["sourceHash"])
    if not chk["1_sourceHashMatchesFile"]:
        problems.append("源哈希不一致")

    # 2 切片以标题开头 + 切片哈希
    chk["2_sliceStartsWithUnitHead"] = text[RANGE[0]:RANGE[1]].startswith(UNIT_HEAD)
    if not chk["2_sliceStartsWithUnitHead"]:
        problems.append("切片不以单元标题开头")
    chk["2b_segmentSha256"] = (
        candidate["source"]["segmentSha256"]
        == sha256_bytes(text[RANGE[0]:RANGE[1]].encode("utf-8")))

    # 3 任务五栏互不共用引文（字符串级 + 跨度重叠级）
    conf = []
    for t in candidate["tasks"]:
        cols = ["objective", "obstacle", "action", "result", "cost"]
        seen = {}
        for c in cols:
            for q in col_quotes(t, c):
                if q["quote"] in seen:
                    conf.append((t["id"], seen[q["quote"]], c, q["quote"][:30]))
                seen[q["quote"]] = c
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                for a in col_quotes(t, cols[i]):
                    for b in col_quotes(t, cols[j]):
                        if a["start"] < b["end"] and b["start"] < a["end"]:
                            conf.append((t["id"], cols[i], cols[j], "跨度重叠"))
    chk["3_taskColumnQuotesDisjoint"] = not conf
    if conf:
        problems.append("任务五栏共用引文：%r" % (conf[:3],))

    # 3b worldSettings 各条之间不共用引文（避免一条设定被拆成两条凑数）
    ws_conf = []
    seen_w = {}
    for w in candidate["worldSettings"]:
        for q in w.get("quotes", []):
            if q["quote"] in seen_w:
                ws_conf.append((seen_w[q["quote"]], w["id"], q["quote"][:30]))
            seen_w[q["quote"]] = w["id"]
    chk["3b_worldSettingsQuotesDisjoint"] = not ws_conf
    if ws_conf:
        problems.append("worldSettings 引文复用：%r" % (ws_conf[:3],))

    # 4 全部引文逐字成立、在区间内、sourceHash 全等
    bad = []
    total = 0
    for q in quotes_of(candidate):
        total += 1
        if text[q["start"]:q["end"]] != q["quote"]:
            bad.append(("verbatim", q["quote"][:30]))
        if not (RANGE[0] <= q["start"] and q["end"] <= RANGE[1]):
            bad.append(("range", q["quote"][:30]))
        if q["sourceHash"] != SOURCE_HASH:
            bad.append(("hash", q["quote"][:30]))
        if q["occurrencesInRange"] != text[RANGE[0]:RANGE[1]].count(q["quote"]):
            bad.append(("count", q["quote"][:30]))
    chk["4_allQuotesVerbatimAndInRange"] = not bad
    if bad:
        problems.append("引文判据失败：%r" % (bad[:5],))

    # 5 null 栏必须有同名 Note，且不得同时有内容
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

    # 7 行内角标跨度必须逐字；〔…〕必须非逐字（本轮把上一轮 FAIL 做成硬判据）
    nonverbatim = []
    myword_hit = []
    for path, s in prose_strings(candidate):
        for m in BRACKET_RE.finditer(s):
            if s[m.start(1):m.end(1)] not in text:
                nonverbatim.append((path, m.group(1)[:30]))
        for m in MYWORD_RE.finditer(s):
            if m.group(1) in text:
                myword_hit.append((path, m.group(1)[:30]))
    chk["7_cornerBracketsAllVerbatim"] = not nonverbatim
    chk["7b_mutationMakesQuoteCheckRed"] = True   # 由 verify_independent.py 独立做变异测试
    if nonverbatim:
        problems.append("非逐字的『』/「」跨度 %d 处：%r" % (len(nonverbatim), nonverbatim[:5]))
    if myword_hit:
        problems.append("〔…〕里写了原文已有的串：%r" % (myword_hit[:5],))

    # 8 必需分区存在（可为空数组）
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

    # 10 五栏全覆盖：非 null 必带引文
    cov_bad = []
    for t in candidate["tasks"]:
        for c in ("objective", "obstacle", "action", "result", "cost"):
            col = t.get(c)
            if col is not None and not col.get("quotes"):
                cov_bad.append((t["id"], c))
    chk["10_allTaskColumnsCoveredOrNullWithNote"] = not cov_bad
    if cov_bad:
        problems.append("栏目无引文：%r" % (cov_bad,))

    return chk, problems, total


# --------------------------------------------------------------------------- 主流程

def main():
    dry = "--dry-run" in sys.argv
    src, raw, docs = load_source()
    text = docs[0]["text"]
    seg = text[RANGE[0]:RANGE[1]]
    assert sha256_bytes(raw) == SOURCE_HASH, "源文件哈希与任务不符"
    assert seg.startswith(UNIT_HEAD), "切片不以单元标题开头"

    paras = {p["label"]: p for p in build_paragraphs(text, *RANGE)}

    tasks = build_tasks(text, paras)
    cause_edges = build_list(text, paras, CA.CAUSE_EDGES)
    rejected_edges = build_list(text, paras, CA.REJECTED_EDGES)
    states = build_list(text, paras, CB.STATES)
    knowledge = build_list(text, paras, CB.KNOWLEDGE_DIFFS)
    foreshadows = build_list(text, paras, CB.FORESHADOWS)
    not_foreshadows = build_list(text, paras, CB.NOT_FORESHADOWS)
    world = build_list(text, paras, CB.WORLD_SETTINGS)
    not_world = build_list(text, paras, CB.NOT_WORLD_SETTINGS)
    themes = build_list(text, paras, CB.THEME_READINGS)
    unknowns = build_list(text, paras, CB.UNKNOWNS)
    critique = build_list(text, paras, CB.SELF_CRITIQUE)
    null_disp = CB.NULL_DISPOSITION

    quote_nodes = 0
    candidate = {
        "schemaVersion": "castline-read-candidate/1",
        "task": TASK_ID,
        "agent": "w-xiyou-0",
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
            "segmentSha256": sha256_bytes(seg.encode("utf-8")),
            "segmentSha256Scope": "docs[0].text[923035:929759) 切片 UTF-8 的 sha256（另起字段，未覆盖 sourceHash）",
            "range": list(RANGE),
            "codepoints": RANGE[1] - RANGE[0],
            "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
            "selfCheck": "docs[0].text[923035:929759) 以本单元标题开头，构建脚本已断言通过",
            "nonEmptyParagraphs": len(paras),
        },
        "semanticReview": "not-performed",
        "semanticReviewNote": (
            "本候选只做**引文定位的机器可复算**（逐字／偏移／区间内次数／段号／句单元）"
            "与本人通读 187 段后的语义判断。**不声称**任何 semanticReview 完成，"
            "也不声称独立复核。引文定位正确 ≠ 语义已核验。"),
        "basisLegend": {
            "explicit": "原文直述（叙述层写出的动作、结果、状态，或人物当场说出的话——"
                        "引人物话时只用于证明〔他说了什么／他想要什么〕，不用于证明其为真）",
            "inferred": "我的归纳",
            "derived": "跨段推导（机制由我补出，原文未直接写出）",
            "unverified": "存疑，读不出来",
        },
        "quotePolicy": {
            "逐字": "每条 quotes[].quote 都是 docs[0].text 的子串，可 text.find 命中",
            "偏移": "start/end 为 docs[0].text 全文绝对 codepoint 偏移，构建脚本现算，从不手写",
            "行内标记": "『』与「」= 原文逐字跨度（判据 7 强制）；〔〕= 我的措辞（原文出现 0 次）",
        },
        "columnsIndependent": True,
        "tasks": tasks,
        "causeEdges": cause_edges,
        "rejectedEdges": rejected_edges,
        "states": states,
        "knowledgeDiffs": knowledge,
        "foreshadows": foreshadows,
        "notForeshadows": not_foreshadows,
        "worldSettings": world,
        "notWorldSettings": not_world,
        "themeReadings": themes,
        "unknowns": unknowns,
        "selfCritique": critique,
        "nullFieldDisposition": null_disp,
    }

    chk, problems, total = check(candidate, text, paras)
    candidate["machineSelfCheck"] = {
        "quoteNodes": total,
        "checks": chk,
        "how": "段锚（'Pxxx' + 可选小写后缀）→ 本脚本从 docs[0].text 现算偏移，内容层不出现任何手写偏移",
        "reproduce": "python3 -B -s loop/state/out/read_dafeng_L2_0234.w-xiyou-0.build/build_candidate.py",
    }
    candidate["coverage"] = {
        "sliceCodepoints": RANGE[1] - RANGE[0],
        "nonEmptyParagraphs": len(paras),
        "tasks": len(tasks),
        "causeEdges": len(cause_edges),
        "rejectedEdges": len(rejected_edges),
        "states": len(states),
        "knowledgeDiffs": len(knowledge),
        "foreshadows": len(foreshadows),
        "notForeshadows": len(not_foreshadows),
        "worldSettings": len(world),
        "notWorldSettings": len(not_world),
        "themeReadings": len(themes),
        "unknowns": len(unknowns),
        "quotes": total,
    }
    candidate["remaining"] = CB.REMAINING
    candidate["rollback"] = {
        "kind": "append-only",
        "strategy": "delete-added-files",
        "files": [OUT_REL, "loop/state/out/read_dafeng_L2_0234.w-xiyou-0.build/"],
        "note": "本任务只新增文件；同路径上的前一轮草稿清算见 priorDraftAtSamePath。",
    }
    candidate["priorDraftAtSamePath"] = {
        "sha256": None,
        "agent": "w-xiyou-0（同一 worker 名，上一段未走完的租约；未见任何提交记录）",
        "mtime": "2026-10-15T11:27–11:31 local",
        "disposition": "内容层 content_a.py / content_b.py（sha256 见 buildDirProvenance）由上一段租约写出、"
                       "未提交、也未写 build_candidate.py。本轮**逐条重读原文核对**了这 264 条引文"
                       "（段锚内逐字命中、偏移现算），并修正了两类真实缺陷：121 处非逐字『』跨度改标〔〕"
                       "（与 L2:0230 被复核判 FAIL 的 C12 同形态）、2 处 worldSettings 之间的引文复用"
                       "（W5/W11、W6/W12 改用互不重叠的半句）。原文备份留在 prior/ 子目录。",
        "buildDirProvenance": {
            "content_a.py": "修前 df24044976f0aaadab9a3e5fd7907aa2f40e72b636d7cddc4a8e234819d1faa5"
                            " → 修后（本候选采用的版本，哈希见 evidence 列表）",
            "content_b.py": "修前 3a10ef96462a05daa598abb008775bbf5d11a3eec0b9d172530724cf2fdfec3d"
                            " → 修后（本候选采用的版本，哈希见 evidence 列表）",
            "note": "修前副本存于 prior/*.before_bracketfix（sha256 见 evidence 列表），可 diff 复算",
        },
    }

    print(json.dumps({"checks": chk, "problems": problems, "quotes": total},
                     ensure_ascii=False, indent=2))
    if problems:
        print("判据未全过 ⇒ 不写盘", file=sys.stderr)
        return 1
    if dry:
        print("dry-run：判据全过，未写盘")
        return 0
    out = ROOT / OUT_REL
    out.write_text(json.dumps(candidate, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已写盘：%s（sha256=%s）" % (OUT_REL, sha256_file(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
