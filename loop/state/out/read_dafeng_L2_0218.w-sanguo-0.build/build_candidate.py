# -*- coding: utf-8 -*-
"""read:dafeng:L2:0218 —— 构建候选（w-sanguo-0）。

做四件事：
  1. 读**原文**（docs[0].text 的 [813350,817425) 切片），复算源哈希与偏移口径；
  2. 把内容文件（content_a/b/c）里的引文串解析成 quoteRef（quote + start/end +
     sourceHash + 全文次数 + 区间次数 + 段号 + 句单元号），逐条现算；
  3. 跑 8 条判据（见 machineSelfCheck），不过就不写盘；
  4. 生成逐段覆盖表（每个非空段标注是否被引用、被哪些分区引用），
     未被引用的段必须给理由 —— 这是「没写」与「确认无需写」的区别。

记号纪律（判据 7 现算强制）：
  『…』 只允许包住 docs[0].text 的**逐字子串**；
  其余标签/转述/截断引文一律用 〔…〕（该记号在 docs[0].text 里出现 0 次）。
  本脚本会把弄错的 『…』 自动降级为 〔…〕 并**全部打印出来**，
  免得「自动改写」把一处本该修好的错引悄悄藏起来。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = Path(__file__).resolve().parent
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L2_0218.candidate.json"

TASK_ID = "read:dafeng:L2:0218"
AGENT = "w-sanguo-0"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 813350, 817425
UNIT_HEAD = "第两百一十七章 许七安：我爽了"
BOOK_TITLE = "大奉打更人"

# ── 0. 源文件与切片 ────────────────────────────────────────────────────────
RAW = DOCS.read_bytes()
FILE_HASH = hashlib.sha256(RAW).hexdigest()
if FILE_HASH != SOURCE_HASH:
    sys.exit("源文件哈希不符：%s != %s" % (FILE_HASH, SOURCE_HASH))
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[S:E]
assert SLICE.startswith(UNIT_HEAD), "切片不以本单元标题开头：%r" % SLICE[:30]
SEGMENT_SHA = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

# ── 1. 段落与句单元索引（全文绝对 codepoint）──────────────────────────────
PARAS = []          # [(label, text, abs_start)]
_off = S
for _i, _line in enumerate(SLICE.split("\n")):
    if _line.strip():
        _lead = len(_line) - len(_line.lstrip())
        PARAS.append(("P%03d" % len(PARAS), _line.strip(), _off + _lead))
    _off += len(_line) + 1
PARA_TEXTS = [p[1] for p in PARAS]

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
    base = {l: a for l, _t, a in PARAS}[lab]
    rel = pos - base
    for k, (a, b) in enumerate(SENT[lab]):
        if a <= rel < b:
            return (lab, k)
    return (lab, 0)


# ── 2. 记号层：非逐字的 『…』 → 〔…〕（并全部打印）────────────────────────
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


# ── 3. 载入内容文件 ───────────────────────────────────────────────────────
sys.path.insert(0, str(BUILD))
import content_a_0218 as CA  # noqa: E402
import content_b_0218 as CB  # noqa: E402
import content_c_0218 as CC  # noqa: E402

SECTIONS = ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeDiffs",
            "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
            "themeReadings", "unknowns", "selfCritique"]

RAW_SECTIONS = {
    "tasks": CA.TASKS,
    "causeEdges": CB.CAUSE_EDGES,
    "rejectedEdges": CB.REJECTED_EDGES,
    "states": CB.STATES,
    "knowledgeDiffs": CB.KNOWLEDGE_DIFFS,
    "foreshadows": CB.FORESHADOWS,
    "notForeshadows": CB.NOT_FORESHADOWS,
    "worldSettings": CC.WORLD_SETTINGS,
    "notWorldSettings": CC.NOT_WORLD_SETTINGS,
    "themeReadings": CC.THEME_READINGS,
    "unknowns": CC.UNKNOWNS,
    "selfCritique": CC.SELF_CRITIQUE,
}

# 先做记号层变换
SECTIONS_FIXED = {k: fix_node(v) for k, v in RAW_SECTIONS.items()}

# quote 字段名 → 该层的引文来源统一收在 "quotes"
problems_hard = []


def resolve(container, path):
    """把 quotes 里的字符串解析成 quoteRef 列表（原地替换）。"""
    if "quotes" not in container:
        return []
    out = []
    for i, q in enumerate(container["quotes"]):
        if not isinstance(q, str):
            out.append(q)
            continue
        n_full = TEXT.count(q)
        n_range = SLICE.count(q)
        if n_range == 0:
            problems_hard.append("引文不在区间内 %s.quotes[%d]: %r" % (path, i, q[:40]))
            continue
        pos = SLICE.find(q)
        st, en = S + pos, S + pos + len(q)
        out.append({
            "quote": q,
            "start": st,
            "end": en,
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
    return out


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

# ── 4. 判据 ───────────────────────────────────────────────────────────────
probs = []
for path, q in ALL_NODES:
    if TEXT[q["start"]:q["end"]] != q["quote"]:
        probs.append("偏移不成立 %s" % path)
    if not (S <= q["start"] and q["end"] <= E):
        probs.append("越界 %s" % path)
    if q["sourceHash"] != SOURCE_HASH:
        probs.append("sourceHash 不符 %s" % path)
    if q["wholeTextOccurrences"] != TEXT.count(q["quote"]):
        probs.append("全文次数不符 %s" % path)
    if q["occurrencesInRange"] != SLICE.count(q["quote"]):
        probs.append("区间次数不符 %s" % path)
    if q["paraLabel"] != para_of(q["start"]):
        probs.append("段号不符 %s" % path)

# 判据 3：同一任务五栏引文不共用（字符区间级 + 句单元级）
conflicts = []
COLUMNS = ("objective", "obstacle", "action", "result", "cost")
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

# 判据 5：cost=null 必须有 costNote
null_problems = []
for t in SECTIONS_FIXED["tasks"]:
    for col in COLUMNS:
        if t.get(col) is None and not (t.get(col + "Note") or "").strip():
            null_problems.append("%s.%s 为 null 但没有 %sNote" % (t["id"], col, col))

# 判据 6：worldSettings 的三套判别字段
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

# 判据：basis 取值合法
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

# 判据 7：真正在用的 『』 必须逐字，且匹配对数 > 0（非恒真）
blob = json.dumps(SECTIONS_FIXED, ensure_ascii=False)
corner = re.findall(r"『([^『』]{1,600})』", blob)
corner_bad = [x for x in corner if x not in SLICE]
c7_ok = (not corner_bad) and len(corner) > 0

# 判据 7b：内存变异必须让判据 7 变红（确认它不是恒真）
MUT_TARGET = "『许七安开小号为自己装逼。』"
MUT_FAKE = "『这段文字原文里绝对没有出现过纯属伪造』"
if MUT_TARGET not in blob:
    sys.exit("变异目标不在正文里，变异无意义：%s" % MUT_TARGET)
mut_blob = blob.replace(MUT_TARGET, MUT_FAKE, 1)
assert mut_blob != blob, "变异未生效"
mut_red = bool([x for x in re.findall(r"『([^『』]{1,600})』", mut_blob) if x not in SLICE])

# ── 5. 覆盖表 ─────────────────────────────────────────────────────────────
touched = {}
for path, q in ALL_NODES:
    lab = q["paraLabel"]
    sec = path.split("/")[0].split("[")[0]
    touched.setdefault(lab, set()).add(sec)

per_para = []
zero = []
for lab, t, a in PARAS:
    secs = sorted(touched.get(lab, set()))
    if secs:
        per_para.append({"para": lab, "state": "quoted", "sections": secs, "note": ""})
    else:
        zero.append(lab)
        per_para.append({"para": lab, "state": "not-quoted", "sections": [],
                         "note": "__FILL__"})

quote_union = set()
for _p, q in ALL_NODES:
    quote_union.update(range(q["start"], q["end"]))
nonspace = {S + i for i, ch in enumerate(SLICE) if not ch.isspace()}

# 未引用段的理由（由人写；缺一个就不写盘）
ZERO_NOTES = json.loads((BUILD / "zero_notes.json").read_text("utf-8")) if \
    (BUILD / "zero_notes.json").exists() else {}
missing_notes = [lab for lab in zero if lab not in ZERO_NOTES]
if missing_notes:
    print("以下未被引用的段缺理由，先补齐 zero_notes.json：")
    for lab in missing_notes:
        t = PARA_TEXTS[int(lab[1:])]
        print("  %s  %s" % (lab, t[:60]))
    sys.exit(2)
for row in per_para:
    if row["state"] == "not-quoted":
        row["note"] = ZERO_NOTES[row["para"]]

# ── 6. 判据汇总 ───────────────────────────────────────────────────────────
checks = {
    "1_sourceHashMatchesFile": FILE_HASH == SOURCE_HASH,
    "2_sliceStartsWithUnitHead": SLICE.startswith(UNIT_HEAD) and len(SLICE) == E - S,
    "3_taskColumnQuotesDisjoint": not conflicts,
    "4_allQuotesVerbatimAndInRange": not problems_hard and not probs,
    "5_nullCostHasNote": not null_problems,
    "6_worldSettingDiscriminantsValid": not ws_bad,
    "7_proseCornerBracketsAllVerbatim_nonVacuous": c7_ok,
    "7b_mutationMakesCheck7Red": mut_red,
    "8_requiredSectionsPresent": all(
        k in SECTIONS_FIXED for k in
        ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]),
    "9_basisValuesLegal": not basis_bad,
}
failed = [k for k, v in checks.items() if not v]
if failed:
    print("判据未过，不写盘：%s" % failed)
    print("hard:", problems_hard[:6])
    print("probs:", probs[:6])
    print("conflicts:", conflicts[:6])
    print("null:", null_problems[:6])
    print("ws:", ws_bad[:6])
    print("cornerBad:", corner_bad[:6])
    print("basis:", basis_bad[:6])
    sys.exit(1)

print("记号层：『』 保留逐字 %d 对；自动降级为 〔〕 %d 处"
      % (marker_stats["keptVerbatim"], marker_stats["relabeled"]))
if marker_stats["relabeledSamples"]:
    print("被降级的串（请人工过一遍，若是笔误应回去改内容文件）：")
    for x in marker_stats["relabeledSamples"]:
        print("   - %s" % x)
if cjk_seen:
    print("警告：仍在使用 「」 记号 %d 处（应统一为 『』/〔〕）：" % len(cjk_seen))
    for x in cjk_seen[:20]:
        print("   - %s" % x)
print("引文节点 %d；未引用段 %d 个：%s" % (len(ALL_NODES), len(zero), zero))
print("判据：%s" % json.dumps(checks, ensure_ascii=False))
print("coverage: quoteUnion=%d nonSpace=%d ratio=%.4f"
      % (len(quote_union), len(nonspace), len(quote_union) / max(1, len(nonspace))))

# ── 7. 组装并写盘 ─────────────────────────────────────────────────────────
cand = {
    "schemaVersion": "castline-read-candidate/1",
    "task": TASK_ID,
    "agent": AGENT,
    "role": "READER（原文精读工作者）",
    "book": "dafeng",
    "bookTitle": BOOK_TITLE,
    "lane": 2,
    "unitIndex": 218,
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
        "markerConvention": "『…』 只允许包住 docs[0].text 的**逐字子串**（判据 7 现算强制）；"
                            "候选自己的标签、转述、截断引文一律用 〔…〕（该记号在 docs[0].text 里出现 0 次）。"
                            "两类记号不混用；本文件正文不再使用 「」 作第三类记号（该记号在原文里出现 0 次）。",
        "withinTaskUniqueness": "同一任务五栏的引文在字符区间级与句单元级两套判据下互不重复（判据 3 现算）。",
        "offsetUnit": "codepoint（Python 字符串下标口径），相对 docs[0].text 全文，左闭右开。",
    },
    "columnsIndependent": True,
    **SECTIONS_FIXED,
    "nullFieldDisposition": [
        {"field": "%s.%s" % (t["id"], col), "value": None,
         "note": t.get(col + "Note", "")}
        for t in SECTIONS_FIXED["tasks"] for col in COLUMNS
        if t.get(col) is None
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
        "cornerBracketNonVerbatim": corner_bad,
        "markerTransform": {
            "keptVerbatim": marker_stats["keptVerbatim"],
            "relabeledToCorner": marker_stats["relabeled"],
            "relabeledSamples": marker_stats["relabeledSamples"][:40],
        },
        "how": "判据 7 扫的是真正在用的 『』（并要求匹配对数 > 0，避免「扫了 0 个所以恒真」）；"
               "7b 在内存里把一处逐字引文换成伪造串，确认判据 7 会变红（真候选文件哈希不受影响）。"
               "判据 3 同时用字符区间与句单元两套口径；判据 6 现算 placeState / itemStates / institution 的取值。",
        "reproduce": "python3 -B -s loop/state/out/read_dafeng_L2_0218.w-sanguo-0.build/build_candidate.py",
    },
    "remaining": [
        "未做语义核验：semanticReview 明确为 not-performed（引文定位正确 ≠ 语义已核验）。",
        "未做独立复核：复核必须由另一个 agent 走 verify 流程（verifierRequired=true）。",
        "S4（宋廷风与朱广孝背过身去）严格说缺可确认的前值，已标 inferred 并在 note 里写明；"
        "若复核口径要求状态条目必须有前值，此条应降级为状态快照或删除。",
        "T1.objective / T4.objective / T5 的 label 属归纳（inferred），原文没有对应自述。",
    ],
}

OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("已写出 %s" % OUT)
print("源哈希 %s" % FILE_HASH)
print("切片哈希 %s" % SEGMENT_SHA)
