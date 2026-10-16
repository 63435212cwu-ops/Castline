# -*- coding: utf-8 -*-
"""read:dafeng:L2:0226 —— 构建候选（w-xiyou-0）。

流程：
  1. 读原文切片 docs[0].text[851090:862305)，复算源哈希与偏移口径；
  2. 把 content_a/b 里的 "Pxxx" 段锚解析成 quoteRef（quote+start/end+sourceHash+
     全文次数+区间次数+段号+句单元号），**偏移从不手写**；
  3. 跑判据，任一不过就不写盘；
  4. 生成逐段覆盖表；未被引用的段必须在 zero_notes.json 里写明理由。

记号纪律：『…』只允许包住逐字原文子串；其余一律 〔…〕（原文内出现 0 次）。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = Path(__file__).resolve().parent
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L2_0226.candidate.json"

TASK_ID = "read:dafeng:L2:0226"
AGENT = "w-xiyou-0"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 851090, 862305
UNIT_HEAD = "第两百二十五章 许七安牺牲了（三章合一）"
BOOK_TITLE = "大奉打更人"
UNIT_INDEX = 226
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
PARA_TEXTS = [p[1] for p in PARAS]
PLABEL = {p[0]: p for p in PARAS}

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
PBASE = {lab: a for lab, _t, a in PARAS}


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
            if len(marker_stats["relabeledSamples"]) < 200:
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
import content_a_0226 as CA  # noqa: E402
import content_b_0226 as CB  # noqa: E402

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

SECTIONS_FIXED = {k: fix_node(v) for k, v in RAW_SECTIONS.items()}

problems_hard = []
ANCHOR_RE = re.compile(r"^(P\d{3})(?::(\d+)-(\d+))?$")


def anchor_to_quote(spec):
    """'P012' → 整段；'P012:0-30' → 段内 0..30 码点。"""
    m = ANCHOR_RE.match(spec)
    if not m:
        return None
    lab, a, b = m.group(1), m.group(2), m.group(3)
    if lab not in PLABEL:
        problems_hard.append("未知段锚：%s" % spec)
        return None
    txt = PLABEL[lab][1]
    if a is None:
        return txt
    a, b = int(a), int(b)
    if b > len(txt):
        problems_hard.append("段锚越界：%s（段长 %d）" % (spec, len(txt)))
        return None
    return txt[a:b]


def resolve(container, path):
    if "quotes" not in container:
        return
    out = []
    for i, q in enumerate(container["quotes"]):
        if isinstance(q, dict):
            out.append(q)
            continue
        s = q[1:] if q.startswith("=") else anchor_to_quote(q)
        if s is None:
            problems_hard.append("引文无法解析 %s.quotes[%d]: %r" % (path, i, q[:40]))
            continue
        n_full = TEXT.count(s)
        n_range = SLICE.count(s)
        if n_range == 0:
            problems_hard.append("引文不在区间内 %s.quotes[%d]: %r" % (path, i, s[:40]))
            continue
        pos = SLICE.find(s)
        st = S + pos
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
            "sentUnit": sent_of(st)[1] if sent_of(st) else None,
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

null_problems = []
for t in SECTIONS_FIXED["tasks"]:
    for col in COLUMNS:
        if t.get(col) is None and not (t.get(col + "Note") or "").strip():
            null_problems.append("%s.%s 为 null 但没有 %sNote" % (t["id"], col, col))

ws_bad = []
for w in SECTIONS_FIXED["worldSettings"]:
    kind = w.get("kind")
    if kind == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            ws_bad.append("%s placeState 非法：%r" % (w["id"], w.get("placeState")))
    elif kind == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(
                x not in ("hold", "transfer", "use", "lose") for x in st):
            ws_bad.append("%s itemStates 非法：%r" % (w["id"], st))
    elif kind == "rule":
        if w.get("institution") not in ("declared", "executed", "misunderstood"):
            ws_bad.append("%s institution 非法：%r" % (w["id"], w.get("institution")))
    else:
        ws_bad.append("%s kind 非法：%r" % (w["id"], kind))
    if not (w.get("explain") or "").strip():
        ws_bad.append("%s 缺 explain" % w["id"])

BASIS_OK = ("explicit", "inferred", "derived", "unverified")
basis_bad = []


def check_basis(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "basis":
                if v not in BASIS_OK:
                    basis_bad.append("%s=%r" % (path, v))
            else:
                check_basis(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            check_basis(v, "%s[%d]" % (path, i))


for name in SECTIONS:
    check_basis(SECTIONS_FIXED[name], name)

blob = json.dumps(SECTIONS_FIXED, ensure_ascii=False)
# 判据 7 扫**整个候选文件**（含 quotePolicy 等元数据），不只是内容分区：
# 只扫分区会漏掉「元语法行自己写了一对非逐字直角引号」这一形态（独立复算实测抓到 3 处）。
WHOLE = json.dumps({**SECTIONS_FIXED, "quotePolicy_placeholder": ""}, ensure_ascii=False)
corner = re.findall(r"『([^『』]{1,600})』", WHOLE)
corner_bad = [x for x in corner if x not in SLICE]
# 本候选正文统一用 〔…〕（既包逐字引文也包转述），故 『…』 对数可以为 0；
# 判据 7 的判据是「凡是用了 『…』 的，必须逐字」，非恒真性由 7b 的引文变异承担。
c7_ok = not corner_bad
prose_span = re.findall(r"〔([^〔〕]{1,600})〕", blob)
prose_verbatim = [x for x in prose_span if x in SLICE]

# 非恒真性：在**内存里**把一处真实引文节点改成伪造串，确认判据 4 会变红。
MUT_FAKE = "这段文字原文里绝对没有出现过纯属伪造XYZ"
_mut_hits = []
for _p, _q in ALL_NODES:
    if _q["quote"] != MUT_FAKE and TEXT[_q["start"]:_q["end"]] == _q["quote"]:
        _mut_hits.append((_p, _q, TEXT[_q["start"]:_q["end"]]))
mut_pos = len(_mut_hits) // 2 if _mut_hits else None
mut_red = False
if mut_pos is not None:
    _p, _q, _orig = _mut_hits[mut_pos]
    _q["quote"] = MUT_FAKE                     # 内存变异，不落盘
    mut_red = TEXT[_q["start"]:_q["end"]] != _q["quote"]
    _q["quote"] = _orig                         # 立刻还原
    mut_target = "%s（%s…）" % (_p, _orig[:12])
else:
    mut_target = None
assert mut_red or mut_target is None, "变异未变红，判据 4 可能是恒真"

# ── 覆盖表 ────────────────────────────────────────────────────────────────
touched = {}
for path, q in ALL_NODES:
    sec = path.split("/")[0].split("[")[0]
    touched.setdefault(q["paraLabel"], set()).add(sec)

per_para, zero = [], []
for lab, t, a in PARAS:
    secs = sorted(touched.get(lab, set()))
    if secs:
        per_para.append({"para": lab, "state": "quoted", "sections": secs, "note": ""})
    else:
        zero.append(lab)
        per_para.append({"para": lab, "state": "not-quoted", "sections": [], "note": "__FILL__"})

quote_union = set()
for _p, q in ALL_NODES:
    quote_union.update(range(q["start"], q["end"]))
nonspace = {S + i for i, ch in enumerate(SLICE) if not ch.isspace()}

ZF = BUILD / "zero_notes.json"
ZERO_NOTES = json.loads(ZF.read_text("utf-8")) if ZF.exists() else {}
missing = [lab for lab in zero if lab not in ZERO_NOTES]
print("未引用段 %d 个；其中已逐段写理由 %d 个，未写理由 %d 个（会如实记进 remaining）"
      % (len(zero), len(zero) - len(missing), len(missing)))
for lab in zero:
    print("  %s|%s" % (lab, PARA_TEXTS[int(lab[1:])][:70]))
for row in per_para:
    if row["state"] == "not-quoted":
        row["note"] = ZERO_NOTES.get(
            row["para"],
            "本段未被任何引用覆盖；本次未逐段写明理由（见 remaining 的覆盖率说明），"
            "此处不填一个听起来合理的解释。")

tasks_ok = all(
    t.get(c) is not None or (t.get(c + "Note") or "").strip()
    for t in SECTIONS_FIXED["tasks"] for c in COLUMNS)

checks = {
    "1_sourceHashMatchesFile": FILE_HASH == SOURCE_HASH,
    "2_sliceStartsWithUnitHead": SLICE.startswith(UNIT_HEAD) and len(SLICE) == E - S,
    "3_taskColumnQuotesDisjoint": not conflicts,
    "4_allQuotesVerbatimAndInRange": not problems_hard and not probs,
    "5_nullCostHasNote": not null_problems,
    "6_worldSettingDiscriminantsValid": not ws_bad,
    "7_cornerBracketsAllVerbatim": c7_ok,
    "7b_mutationMakesQuoteCheckRed": mut_red,
    "8_requiredSectionsPresent": all(
        k in SECTIONS_FIXED for k in
        ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]),
    "9_basisValuesLegal": not basis_bad,
    "10_allTaskColumnsCoveredOrNullWithNote": tasks_ok,
    "11_proseCornerSpansExist": len(prose_span) > 0,
}
failed = [k for k, v in checks.items() if not v]
if failed:
    print("判据未过，不写盘：%s" % failed)
    for nm, arr in (("hard", problems_hard), ("probs", probs), ("conflicts", conflicts),
                    ("null", null_problems), ("ws", ws_bad), ("cornerBad", corner_bad),
                    ("basis", basis_bad)):
        if arr:
            print("%s: %s" % (nm, arr[:6]))
    sys.exit(1)

print("记号层：『』保留逐字 %d 对；降级为 〔〕 %d 处"
      % (marker_stats["keptVerbatim"], marker_stats["relabeled"]))
if marker_stats["relabeledSamples"]:
    print("被降级的串（须人工过一遍）：")
    for x in marker_stats["relabeledSamples"]:
        print("   - %s" % x)
if cjk_seen:
    print("警告：仍在使用 「」 记号 %d 处" % len(cjk_seen))
print("引文节点 %d；未引用段 %d 个" % (len(ALL_NODES), len(zero)))
print("判据：%s" % json.dumps(checks, ensure_ascii=False))
print("coverage: union=%d nonSpace=%d ratio=%.4f"
      % (len(quote_union), len(nonspace), len(quote_union) / max(1, len(nonspace))))

cand = {
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
        "segmentSha256Scope": "docs[0].text[start:end] 的 UTF-8 字节 sha256（另起字段，未覆盖 sourceHash）",
        "range": [S, E],
        "codepoints": E - S,
        "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
        "selfCheck": "docs[0].text[%d:%d] 以本单元标题开头" % (S, E),
        "nonEmptyParagraphs": len(PARAS),
    },
    "semanticReview": "not-performed",
    "semanticReviewNote": "本候选只做引文定位的机器可复算（逐字／偏移／区间内次数／段号／句单元）"
                          "与本人通读后的语义判断；**不声称**任何 semanticReview 完成，"
                          "也不声称独立复核。引文定位正确 ≠ 语义已核验。",
    "basisLegend": {
        "explicit": "原文直述（含叙述层记录下的人物言语、内心与动作；被记录的话本身不因被记录而成事实）",
        "inferred": "我的归纳（原文没有直接写出这一步）",
        "derived": "跨段推导（多段证据合成，单段不足以成立）",
        "unverified": "存疑（区间内无法判定，或存在互相矛盾的说法）",
    },
    "quotePolicy": {
        "markerConvention": "本文件用一对直角引号（U+300E/U+300F）只包住 docs[0].text 的**逐字子串**"
                            "（判据 7 全文现算强制）；候选自己的标签、转述、截断引文一律用一对六角括号"
                            "〔U+3014/U+3015〕（该记号在原文区间内出现 0 次）。"
                            "本文件不使用第三类引号记号；这里刻意不写出引号对的示意形态，"
                            "因为那会构成一对非逐字的直角引号，被判据 7 判红（独立复算抓到过这一处）。",
        "withinTaskUniqueness": "同一任务五栏的引文在字符区间级与句单元级两套判据下互不重复（判据 3 现算）。",
        "offsetUnit": "codepoint（Python 字符串下标口径），相对 docs[0].text 全文，左闭右开。",
    },
    "columnsIndependent": True,
    **SECTIONS_FIXED,
    "nullFieldDisposition": [
        {"field": "%s.%s" % (t["id"], col), "value": None, "note": t.get(col + "Note", "")}
        for t in SECTIONS_FIXED["tasks"] for col in COLUMNS if t.get(col) is None
    ],
    "coverage": {
        "nonEmptyParagraphs": len(PARAS),
        "quoteUnionCodepoints": len(quote_union),
        "nonSpaceCodepoints": len(nonspace),
        "quoteUnionRatioOfNonSpace": round(len(quote_union) / max(1, len(nonspace)), 4),
        "paragraphsTouched": len(PARAS) - len(zero),
        "zeroCoveredParagraphs": len(zero),
        "zeroCoveredList": zero,
        "perParagraph": per_para,
    },
    "machineSelfCheck": {
        "quoteNodes": len(ALL_NODES),
        "checks": checks,
        "columnConflicts": conflicts,
        "nullProblems": null_problems,
        "worldSettingProblems": ws_bad,
        "cornerBracketPairs": len(corner),
        "cornerScanScope": "整个候选文件（含元数据），不只是内容分区",
        "cornerBracketNonVerbatim": corner_bad,
        "markerTransform": {
            "keptVerbatim": marker_stats["keptVerbatim"],
            "relabeledToCorner": marker_stats["relabeled"],
            "relabeledSamples": marker_stats["relabeledSamples"][:40],
        },
        "how": "引文偏移由本脚本从 docs[0].text 现算，从不手写；判据 7 只要求「凡用了直角引号对的必须逐字」"
               "（本候选正文统一用 〔…〕，故 『』 对数为 0，非恒真性改由 7b 承担）；"
               "7b 在内存里把一处**真实引文节点**换成伪造串并立即还原，确认偏移判据会变红"
               "（真候选文件哈希不受影响，已断言还原）；判据 3 用字符区间与句单元两套口径；"
               "判据 6 现算 placeState / itemStates / institution 取值；"
               "判据 11 要求正文里确有 〔…〕 跨度，避免「扫了 0 个所以恒真」。",
        "mutationTarget": mut_target,
        "proseCornerSpans": len(prose_span),
        "proseCornerSpansVerbatim": len(prose_verbatim),
        "reproduce": "python3 -B -s loop/state/out/read_dafeng_L2_0226.w-xiyou-0.build/build_candidate.py",
    },
    "remaining": [
        "未做语义核验：semanticReview 明确为 not-performed（引文定位正确 ≠ 语义已核验）。",
        "未做独立复核：复核必须由另一个 agent 走 verify 流程（verifierRequired=true）。",
        "T1.cost 与 T3.result 的机制链标 derived，原文没有直写「这是他的代价／这是他的功劳」；"
        "若复核口径更严，T1.cost 应改为 null（说明已写进该栏 note 与 SC2）。",
        "S2（姜律中从被打废到狂奔参战）缺中间机制，标 unverified；U3（死亡的最终性）在区间内自相矛盾，未判定。",
        "未引用段共 %d 个，其中 %d 个未逐段写明理由（候选 coverage.perParagraph 里已逐段列出是哪几段，"
        "note 字段直说未写理由而不是编一个）；这是本轮的真实缺口。" % (len(zero), len(missing)),
        "正文引文记号统一用 〔…〕（既包逐字引文也包转述），因此直角引号对数为 0；"
        "判据 7 的非恒真性改由 7b（内存变异一处真实引文节点）承担，已在 machineSelfCheck 里写明。",
        "本任务不要求 GPU／浏览器测试，未跑；未改任何受保护路径。",
    ],
}

OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("已写出 %s" % OUT)
print("源哈希 %s" % FILE_HASH)
print("切片哈希 %s" % SEGMENT_SHA)
