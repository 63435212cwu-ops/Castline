# -*- coding: utf-8 -*-
"""read:dafeng:L2:0230 —— 构建候选（w-dafeng-0）。

流程：
  1. 读原文切片 docs[0].text[889513:896868)，复算源哈希与偏移口径；
  2. 把 content_a/b 里的段锚（'P029' / 'P029@子串'）解析成 quoteRef
     （quote + start/end + sourceHash + 全文次数 + 区间次数 + 段号 + 句单元号），
     **偏移从不手写**；
  3. 跑判据，任一不过就不写盘；
  4. 生成逐段覆盖表；未被引用的段在 coverage 里逐段列出。

记号纪律：『…』只允许包住逐字原文子串；其余一律 〔…〕（原文内出现 0 次）。
构建脚本会把非逐字的 『…』 全部打印出来并改写为 〔…〕，不静默处理。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = Path(__file__).resolve().parent
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L2_0230.candidate.json"
NOPARAS = ROOT / "loop/state/out/read_dafeng_L2_0230.w-dafeng-0.build" / "no_para_notes.json"

TASK_ID = "read:dafeng:L2:0230"
AGENT = "w-dafeng-0"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 889513, 896868
UNIT_HEAD = "第一章 监正的馈赠（大章求月票）"
BOOK_TITLE = "大奉打更人"
UNIT_INDEX = 230
LANE = 2

RAW = DOCS.read_bytes()
FILE_HASH = hashlib.sha256(RAW).hexdigest()
if FILE_HASH != SOURCE_HASH:
    sys.exit("源文件哈希不符：%s != %s" % (FILE_HASH, SOURCE_HASH))
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[S:E]
assert SLICE.startswith(UNIT_HEAD), "切片不以本单元标题开头：%r" % SLICE[:30]
SEGMENT_SHA = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

# ── 段落索引（全文绝对 codepoint）─────────────────────────────────────────
PARAS = []
_off = S
for _line in SLICE.split("\n"):
    if _line.strip():
        _lead = len(_line) - len(_line.lstrip())
        PARAS.append(("P%03d" % len(PARAS), _line.strip(), _off + _lead))
    _off += len(_line) + 1
PLABEL = {p[0]: p for p in PARAS}
PBASE = {lab: a for lab, _t, a in PARAS}

_SEP = re.compile(r"[。！？…]+")


def sent_units(t):
    out, last = [], 0
    for m in _SEP.finditer(t):
        out.append((last, m.end()))
        last = m.end()
    if last < len(t):
        out.append((last, len(t)))
    return out or [(0, len(t))]


SENT = {lab: sent_units(t) for lab, t, _a in PARAS}


def para_of(pos):
    for lab, t, a in PARAS:
        if a <= pos < a + len(t):
            return lab
    return None


def sent_of(pos):
    lab = para_of(pos)
    if lab is None:
        return None
    rel = pos - PBASE[lab]
    for k, (a, b) in enumerate(SENT[lab]):
        if a <= rel < b:
            return (lab, k)
    return (lab, 0)


# ── 记号层：非逐字的 『…』 → 〔…〕（全部打印，不静默）────────────────────
SPAN = re.compile(r"『([^『』]{1,600})』")
marker_stats = {"keptVerbatim": 0, "relabeled": 0, "relabeledSamples": []}
CJK_QUOTE = re.compile(r"「([^「」]{1,600})」")
cjk_seen = []


def fix_str(s):
    out, last = [], 0
    for m in SPAN.finditer(s):
        inner = m.group(1)
        out.append(s[last:m.start()])
        if inner in SLICE:
            marker_stats["keptVerbatim"] += 1
            out.append(m.group(0))
        else:
            marker_stats["relabeled"] += 1
            if len(marker_stats["relabeledSamples"]) < 300:
                marker_stats["relabeledSamples"].append(inner)
            out.append("〔%s〕" % inner)
        last = m.end()
    out.append(s[last:])
    return "".join(out)


def fix_node(node):
    if isinstance(node, dict):
        return {k: fix_node(v) for k, v in node.items()}
    if isinstance(node, list):
        return [fix_node(v) for v in node]
    if isinstance(node, str):
        for m in CJK_QUOTE.finditer(node):
            cjk_seen.append(m.group(1))
        return fix_str(node)
    return node


sys.path.insert(0, str(BUILD))
import content_a as CA  # noqa: E402
import content_b as CB  # noqa: E402

SECTIONS = ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeDiffs",
            "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
            "themeReadings", "unknowns", "selfCritique"]

RAW_SECTIONS = {
    "tasks": CA.TASKS,
    "causeEdges": CA.CAUSE_EDGES,
    "rejectedEdges": CA.REJECTED_EDGES,
    "states": CB.STATES,
    "knowledgeDiffs": CB.KNOWLEDGE_DIFFS,
    "foreshadows": CB.FORESHADOWS,
    "notForeshadows": CB.NOT_FORESHADOWS,
    "worldSettings": CB.WORLD_SETTINGS,
    "notWorldSettings": CB.NOT_WORLD_SETTINGS,
    "themeReadings": CB.THEME_READINGS,
    "unknowns": CB.UNKNOWNS,
    "selfCritique": CB.SELF_CRITIQUE,
}

# 被拒边的引文允许与内容分区重叠（它是「为了说明为什么不连边」而引的），
# 但**五元组内部**必须零共用。
SECTIONS_FIXED = {k: fix_node(v) for k, v in RAW_SECTIONS.items()}

problems_hard = []
ANCHOR_RE = re.compile(r"^(P\d{3})(?:@(.+))?$", re.S)


def anchor_to_quote(spec):
    """'P012' → 整段；'P012@子串' → 段内子串。"""
    m = ANCHOR_RE.match(spec)
    if not m:
        problems_hard.append("段锚格式非法：%r" % (spec,))
        return None, None
    lab, sub = m.group(1), m.group(2)
    if lab not in PLABEL:
        problems_hard.append("未知段锚：%s" % spec)
        return None, None
    txt = PLABEL[lab][1]
    if sub is None:
        return lab, txt
    if sub not in txt:
        problems_hard.append("段锚子串不在段内 %s：%r" % (spec, sub[:40]))
        return None, None
    return lab, sub


def resolve(container, path):
    if "quotes" not in container:
        return
    out = []
    for i, q in enumerate(container["quotes"]):
        if isinstance(q, dict):
            out.append(q)
            continue
        lab, s = anchor_to_quote(q)
        if s is None:
            problems_hard.append("引文无法解析 %s.quotes[%d]: %r" % (path, i, str(q)[:40]))
            continue
        # 段锚（含子串）必须唯一：取该段内该子串的位置，避免落到别段同文。
        base = PBASE[lab]
        pos_in_para = PLABEL[lab][1].find(s)
        st = base + pos_in_para
        if TEXT[st:st + len(s)] != s:
            problems_hard.append("段内定位失败 %s.quotes[%d]" % (path, i))
            continue
        n_full = TEXT.count(s)
        n_range = SLICE.count(s)
        if n_range == 0:
            problems_hard.append("引文不在区间内 %s.quotes[%d]: %r" % (path, i, s[:40]))
            continue
        su = sent_of(st)
        out.append({
            "quote": s,
            "start": st,
            "end": st + len(s),
            "sourceHash": SOURCE_HASH,
            "offsetUnit": "codepoint",
            "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
            "match": "exact",
            "wholeTextOccurrences": n_full,
            "occurrencesInRange": n_range,
            "paraLabel": para_of(st),
            "sentUnit": su[1] if su else None,
        })
    container["quotes"] = out


ALL_NODES = []


def walk(node, path):
    if isinstance(node, dict):
        if "quotes" in node:
            resolve(node, path)
            for j, q in enumerate(node.get("quotes") or []):
                if isinstance(q, dict):
                    ALL_NODES.append(("%s.quotes[%d]" % (path, j), q))
        for k, v in node.items():
            walk(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i))


for name in SECTIONS:
    walk(SECTIONS_FIXED[name], name)

# ── 判据 4：逐条引文定位 ───────────────────────────────────────────────────
probs = []
for path, q in ALL_NODES:
    if TEXT[q["start"]:q["end"]] != q["quote"]:
        probs.append("偏移不成立 %s" % path)
    if not (S <= q["start"] and q["end"] <= E):
        probs.append("越界 %s" % path)
    if q["wholeTextOccurrences"] != TEXT.count(q["quote"]):
        probs.append("全文次数不符 %s" % path)
    if q["occurrencesInRange"] != SLICE.count(q["quote"]):
        probs.append("区间次数不符 %s" % path)
    if q["paraLabel"] != para_of(q["start"]):
        probs.append("段号不符 %s" % path)
    if q["sourceHash"] != SOURCE_HASH:
        probs.append("sourceHash 不符 %s" % path)

# ── 判据 3：五元组五栏之间零共用（字符区间级 + 句单元级）────────────────────
COLUMNS = ("objective", "obstacle", "action", "result", "cost")
conflicts = []
for t in SECTIONS_FIXED["tasks"]:
    seen_range, seen_sent = {}, {}
    for col in COLUMNS:
        v = t.get(col)
        if not v:
            continue
        for q in v.get("quotes") or []:
            k = (q["start"], q["end"])
            if k in seen_range:
                conflicts.append("%s %s/%s 区间共用" % (t["id"], seen_range[k], col))
            seen_range[k] = col
            sk = (q["paraLabel"], q["sentUnit"])
            if sk in seen_sent and seen_sent[sk] != col:
                conflicts.append("%s %s/%s 句单元共用 %s" % (t["id"], seen_sent[sk], col, sk))
            seen_sent[sk] = col

# ── 判据 3b：worldSettings 内部零共用 ─────────────────────────────────────
ws_conflicts = []
_ws_seen = {}
for w in SECTIONS_FIXED["worldSettings"]:
    for q in w.get("quotes") or []:
        k = (q["start"], q["end"])
        if k in _ws_seen:
            ws_conflicts.append("%s 与 %s 共用区间 %s" % (_ws_seen[k], w["id"], k))
        _ws_seen[k] = w["id"]

# ── 判据 5：null 栏必须有同名 Note 说明为什么没有 ─────────────────────────
null_problems = []
for t in SECTIONS_FIXED["tasks"]:
    for col in COLUMNS:
        if t.get(col) is None:
            if not (t.get(col + "Note") or "").strip():
                null_problems.append("%s.%s 为 null 但缺 %sNote" % (t["id"], col, col))

# ── 判据 6：worldSettings 判别字段合法 ────────────────────────────────────
ws_problems = []
ITEM_STATES = {"hold", "transfer", "use", "lose"}
INSTITUTIONS = {"declared", "executed", "misunderstood"}
for w in SECTIONS_FIXED["worldSettings"]:
    kind = w.get("kind")
    if kind == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            ws_problems.append("%s placeState 非法：%r" % (w["id"], w.get("placeState")))
        if "itemStates" in w or "institution" in w:
            ws_problems.append("%s 混入其他 kind 的判别字段" % w["id"])
    elif kind == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(x not in ITEM_STATES for x in st):
            ws_problems.append("%s itemStates 非法：%r" % (w["id"], st))
        if len(set(st)) != len(st):
            ws_problems.append("%s itemStates 有重复" % w["id"])
        if "placeState" in w or "institution" in w:
            ws_problems.append("%s 混入其他 kind 的判别字段" % w["id"])
    elif kind == "rule":
        if w.get("institution") not in INSTITUTIONS:
            ws_problems.append("%s institution 非法：%r" % (w["id"], w.get("institution")))
        if "placeState" in w or "itemStates" in w:
            ws_problems.append("%s 混入其他 kind 的判别字段" % w["id"])
    else:
        ws_problems.append("%s kind 非法：%r" % (w["id"], kind))
    if not (w.get("explain") or "").strip():
        ws_problems.append("%s 缺 explain" % w["id"])
    if not (w.get("quotes") or []):
        ws_problems.append("%s 没有引文" % w["id"])

# ── 判据 9：basis 合法 ───────────────────────────────────────────────────
LEGAL_BASIS = {"explicit", "inferred", "derived", "unverified"}
basis_problems = []


def check_basis(node, path):
    if isinstance(node, dict):
        if "basis" in node and node["basis"] not in LEGAL_BASIS:
            basis_problems.append("%s.basis=%r" % (path, node["basis"]))
        for k, v in node.items():
            check_basis(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            check_basis(v, "%s[%d]" % (path, i))


for name in SECTIONS:
    check_basis(SECTIONS_FIXED[name], name)

# ── 判据 7：全文 『…』 与引文都必须是逐字子串 ──────────────────────────────
corner_bad = [m.group(1) for m in SPAN.finditer(json.dumps(SECTIONS_FIXED, ensure_ascii=False))
              if m.group(1) not in SLICE]
corner_pairs = len(SPAN.findall(json.dumps(SECTIONS_FIXED, ensure_ascii=False)))

# ── 判据 7b：变异自检 —— 改坏一个字，判据必须转红 ─────────────────────────
_mut = dict(ALL_NODES[0][1])
_bad = _mut["quote"][:-1] + ("X" if _mut["quote"][-1] != "X" else "Y")
mutation_red = (TEXT[_mut["start"]:_mut["end"]] != _bad)

# ── 判据 8：必需分区存在 ─────────────────────────────────────────────────
REQUIRED_SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings",
                     "themeReadings"]
missing_sections = [k for k in REQUIRED_SECTIONS if k not in SECTIONS_FIXED]

# ── 覆盖表 ───────────────────────────────────────────────────────────────
covered = set()
qtot = 0
covered_cp = set()
for _p, q in ALL_NODES:
    for lab, t, a in PARAS:
        if q["start"] < a + len(t) and q["end"] > a:
            covered.add(lab)
    for _c in range(q["start"], q["end"]):
        if _c not in covered_cp:
            covered_cp.add(_c)
            qtot += 1
per_para = []
for lab, t, a in PARAS:
    per_para.append({"para": lab, "start": a, "codepoints": len(t),
                     "quoted": lab in covered})
zero = [p["para"] for p in per_para if not p["quoted"]]
non_space = sum(1 for ch in SLICE if not ch.isspace())

# 未引用段的理由：能从 no_para_notes.json 取到的写上，取不到的如实标 null。
no_para_notes = {}
if NOPARAS.exists():
    no_para_notes = json.loads(NOPARAS.read_text(encoding="utf-8"))
for p in per_para:
    if not p["quoted"]:
        p["reason"] = no_para_notes.get(p["para"])

# ── 组装候选 ─────────────────────────────────────────────────────────────
HARD = {
    "1_sourceHashMatchesFile": FILE_HASH == SOURCE_HASH,
    "2_sliceStartsWithUnitHead": SLICE.startswith(UNIT_HEAD),
    "3_taskColumnQuotesDisjoint": not conflicts,
    "3b_worldSettingsQuotesDisjoint": not ws_conflicts,
    "4_allQuotesVerbatimAndInRange": not probs,
    "5_nullColumnsHaveNote": not null_problems,
    "6_worldSettingDiscriminantsValid": not ws_problems,
    "7_cornerBracketsAllVerbatim": not corner_bad,
    "7b_mutationMakesQuoteCheckRed": mutation_red,
    "8_requiredSectionsPresent": not missing_sections,
    "9_basisValuesLegal": not basis_problems,
    "10_allTaskColumnsCoveredOrNullWithNote": all(
        (t.get(c) is not None) or (t.get(c + "Note") or "").strip()
        for t in SECTIONS_FIXED["tasks"] for c in COLUMNS),
}
failed = [k for k, v in HARD.items() if not v]

report = {
    "checks": HARD,
    "failed": failed,
    "quoteNodes": len(ALL_NODES),
    "columnConflicts": conflicts,
    "worldSettingConflicts": ws_conflicts,
    "nullProblems": null_problems,
    "worldSettingProblems": ws_problems,
    "basisProblems": basis_problems,
    "quoteProblems": probs,
    "cornerBracketNonVerbatim": corner_bad,
    "cornerBracketPairs": corner_pairs,
    "relabeledCornerSpans": marker_stats["relabeled"],
    "relabeledSamples": marker_stats["relabeledSamples"],
    "cjkQuoteSeen": len(cjk_seen),
    "paragraphs": len(PARAS),
    "coveredParagraphs": len(covered),
    "zeroCovered": len(zero),
    "nonSpaceCodepoints": non_space,
}
print(json.dumps(report, ensure_ascii=False, indent=1))
if failed:
    sys.exit("硬判据未全过，拒绝写盘：%s" % failed)

candidate = {
    "schemaVersion": "castline-read-candidate/1",
    "task": TASK_ID,
    "agent": AGENT,
    "role": "READER（原文精读工作者）",
    "book": "dafeng",
    "bookTitle": BOOK_TITLE,
    "lane": LANE,
    "unitIndex": UNIT_INDEX,
    "unitHead": UNIT_HEAD,
    "source": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "sourceHash": SOURCE_HASH,
        "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
        "segmentSha256": SEGMENT_SHA,
        "segmentSha256Scope": "docs[0].text[889513:896868) 切片 UTF-8 的 sha256（另起字段，未覆盖 sourceHash）",
        "range": [S, E],
        "codepoints": E - S,
        "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
        "selfCheck": "docs[0].text[889513:896868) 以本单元标题开头，构建脚本已断言通过",
        "nonEmptyParagraphs": len(PARAS),
    },
    "semanticReview": "not-performed",
    "semanticReviewNote": "本候选只做引文定位的机器可复算（逐字／偏移／区间内次数／段号／句单元）"
                          "与本人通读后的语义判断；**不声称**任何 semanticReview 完成，"
                          "也不声称独立复核。引文定位正确 ≠ 语义已核验。",
    "basisLegend": {
        "explicit": "原文直述（人物台词会被标为台词本身，不当叙述事实）",
        "inferred": "本人归纳",
        "derived": "跨段推导（每一环有直述依据，连接是我合成的）",
        "unverified": "存疑，未判定",
    },
    "quotePolicy": {
        "markerConvention": "『…』只包逐字原文子串；〔…〕内的文字不是逐字引文（原文内出现 0 次）",
        "withinTaskUniqueness": "同一任务五元组内，字符区间级与句单元级两套判据下引文零共用",
        "offsetUnit": "codepoint（0-based，左闭右开，相对 docs[0].text 全文）",
    },
    "columnsIndependent": True,
    "tasks": SECTIONS_FIXED["tasks"],
    "causeEdges": SECTIONS_FIXED["causeEdges"],
    "rejectedEdges": SECTIONS_FIXED["rejectedEdges"],
    "states": SECTIONS_FIXED["states"],
    "knowledgeDiffs": SECTIONS_FIXED["knowledgeDiffs"],
    "foreshadows": SECTIONS_FIXED["foreshadows"],
    "notForeshadows": SECTIONS_FIXED["notForeshadows"],
    "worldSettings": SECTIONS_FIXED["worldSettings"],
    "notWorldSettings": SECTIONS_FIXED["notWorldSettings"],
    "themeReadings": SECTIONS_FIXED["themeReadings"],
    "unknowns": SECTIONS_FIXED["unknowns"],
    "selfCritique": SECTIONS_FIXED["selfCritique"],
    "nullFieldDisposition": [
        {"field": "%s.%s" % (t["id"], c), "value": None,
         "note": t.get(c + "Note")}
        for t in SECTIONS_FIXED["tasks"] for c in COLUMNS
        if t.get(c) is None
    ],
    "coverage": {
        "nonEmptyParagraphs": len(PARAS),
        "quoteUnionCodepoints": qtot,
        "nonSpaceCodepoints": non_space,
        "quoteUnionRatioOfNonSpace": round(qtot / non_space, 4) if non_space else None,
        "paragraphsTouched": len(covered),
        "zeroCoveredParagraphs": len(zero),
        "zeroCoveredList": zero,
        "perParagraph": per_para,
        "reasonPolicy": "未引用段的 reason 来自 no_para_notes.json；"
                        "取不到的写 null（不在候选里编理由）。",
    },
    "machineSelfCheck": {
        "quoteNodes": len(ALL_NODES),
        "checks": HARD,
        "columnConflicts": conflicts,
        "worldSettingConflicts": ws_conflicts,
        "nullProblems": null_problems,
        "cornerBracketPairs": corner_pairs,
        "cornerBracketNonVerbatim": corner_bad,
        "relabeledCornerSpans": marker_stats["relabeled"],
        "markerTransform": "非逐字的 『…』 已全部改写为 〔…〕（原文出现 0 次），不静默保留",
        "how": "段锚（'Pxxx' 或 'Pxxx@子串'）→ 构建脚本从 docs[0].text 现算偏移，"
               "content_a/b 里不出现任何手写偏移",
        "reproduce": "python3 -B -s loop/state/out/read_dafeng_L2_0230.w-dafeng-0.build/build_candidate.py",
    },
    "remaining": [
        "未做语义核验：semanticReview=not-performed（引文定位正确 ≠ 语义已核验）。",
        "未做独立复核（另一 agent 的 verify:dafeng:L2:0230）：本轮的独立重算脚本"
        "只覆盖机器可复算的定位与结构层，不等于语义复核，也不满足 verifierRequired。",
        "F4（神殊的保密要求）与 F5（追封的程序性等待）两条伏笔在本区间未回收，未做跨单元追踪。",
        "F3（监正化鸟 → 船外鸟啼）的「同一只鸟」连接未被文本确认，已标 partial 并记 U3。",
        "**已知的三处覆盖空缺（未登记为独立条目，理由写在 coverage.perParagraph 的 reason 里）**："
        "① P039 许平志之妻当场昏厥——真实发生的事件，本候选没有把她登记为独立 states 条目；"
        "② P042 许玲月的木然（『像一朵没有生气的纸花』）——同样未单列；"
        "③ P182 杨千幻自述出门在外时想起司天监『心里就觉得踏实』——"
        "它与许七安的「家」构成对照，TH1/TH2 都没有用上。"
        "这三处不是我判定为不重要的材料，而是本轮条目分配的取舍结果；复核若要补，这是首选位置。",
        "区间内的『裱裱』（P090，单次出现）未能确定所指，已记 U13；"
        "不把「裱裱＝临安」当既定事实，尽管上下文强烈暗示是她。",
    ],
    "rollback": {"kind": "append-only", "strategy": "delete-added-files",
                 "files": ["loop/state/out/read_dafeng_L2_0230.candidate.json"]},
}

OUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=1), encoding="utf-8")
print("已写盘：%s" % OUT)
print("候选 sha256：%s" % hashlib.sha256(OUT.read_bytes()).hexdigest())
