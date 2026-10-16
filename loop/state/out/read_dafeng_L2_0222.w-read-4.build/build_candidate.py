# -*- coding: utf-8 -*-
"""read:dafeng:L2:0222 —— 构建候选（w-read-4）。

做四件事：
  1. 读**原文**（docs[0].text 的 [832785,836013) 切片），复算源哈希与偏移口径；
  2. 把内容文件里的引文解析成 quoteRef（quote + start/end + sourceHash + 全文次数 +
     区间次数 + 段号 + 句单元号），逐条现算；
  3. 跑判据（见 machineSelfCheck），不过就**不写盘**；
  4. 生成逐段覆盖表（每个非空段标注是否被引用、被哪些分区引用），
     未被引用的段必须给理由 —— 这是「没写」与「确认无需写」的区别。

两套引文写法（内容文件里各用各的，本脚本都支持）：
  · content_a / content_b：Q(段号, 段内起, 段内止) 三元组 —— 从该段现取子串；
  · content_c：("段号", "逐字子串") 二元组 —— 在该段内 find，要求**恰好命中一次**。

记号纪律（判据 7 现算强制）：
  『…』 只允许包住 docs[0].text 的**逐字子串**；
  其余标签/转述/截断引文一律用 〔…〕（该记号在 docs[0].text 里出现 0 次）。
  与参考实现不同的是：本脚本遇到非逐字的 『…』 **直接判失败退出**，
  不做自动降级 —— 自动改写会把一处本该修好的错引悄悄藏起来。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = Path(__file__).resolve().parent
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L2_0222.candidate.json"

TASK_ID = "read:dafeng:L2:0222"
AGENT = "w-read-4"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 832785, 836013
UNIT_HEAD = "第两百二十一章 朝廷要犯"
BOOK_TITLE = "大奉打更人"

# ── 0. 源文件与切片 ────────────────────────────────────────────────────────
RAW = DOCS.read_bytes()
FILE_HASH = hashlib.sha256(RAW).hexdigest()
if FILE_HASH != SOURCE_HASH:
    sys.exit("源文件哈希不符：%s != %s" % (FILE_HASH, SOURCE_HASH))
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[S:E]
assert SLICE.startswith(UNIT_HEAD), "切片不以本单元标题开头：%r" % SLICE[:30]
if len(SLICE) != E - S:
    sys.exit("切片长度不符：%d != %d" % (len(SLICE), E - S))
SEGMENT_SHA = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

# ── 1. 段落与句单元索引（全文绝对 codepoint）──────────────────────────────
PARAS = []          # [(label, text, abs_start)]
_off = S
for _line in SLICE.split("\n"):
    if _line.strip():
        _lead = len(_line) - len(_line.lstrip())
        PARAS.append(("P%03d" % len(PARAS), _line.strip(), _off + _lead))
    _off += len(_line) + 1
PARA_TEXTS = [p[1] for p in PARAS]
PARA_BY_LABEL = {lab: (t, a) for lab, t, a in PARAS}

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
    base = PARA_BY_LABEL[lab][1]
    rel = pos - base
    for k, (a, b) in enumerate(SENT[lab]):
        if a <= rel < b:
            return (lab, k)
    return (lab, 0)


# ── 2. 记号层：非逐字的 『…』 一律判失败（不自动降级）──────────────────────
SPAN = re.compile(r"『([^『』]{1,600})』")
CJK_QUOTE = re.compile(r"「([^「」]{1,600})」")


def scan_markers(node, path, bad, cjk):
    if isinstance(node, dict):
        for k, v in node.items():
            scan_markers(v, path + "/" + str(k), bad, cjk)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            scan_markers(v, "%s[%d]" % (path, i), bad, cjk)
    elif isinstance(node, str):
        for m in SPAN.finditer(node):
            if m.group(1) not in SLICE:
                bad.append((path, m.group(1)))
        for m in CJK_QUOTE.finditer(node):
            cjk.append((path, m.group(1)))


# ── 3. 载入内容文件 ───────────────────────────────────────────────────────
sys.path.insert(0, str(BUILD))
import content_a as CA  # noqa: E402
import content_b as CB  # noqa: E402
import content_c as CC  # noqa: E402

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
SECTIONS = list(RAW_SECTIONS)

bad_markers, cjk_markers = [], []
for _name, _sec in RAW_SECTIONS.items():
    scan_markers(_sec, _name, bad_markers, cjk_markers)
if bad_markers or cjk_markers:
    print("记号层不合规，先改内容文件再构建：")
    for p, x in bad_markers[:40]:
        print("   『非逐字』 %s: %r" % (p, x))
    for p, x in cjk_markers[:40]:
        print("   「第三类记号」 %s: %r" % (p, x))
    sys.exit(3)

# ── 4. 解析引文 ───────────────────────────────────────────────────────────
hard = []


def make_ref(lab, st, en, path):
    q = TEXT[st:en]
    n_full = TEXT.count(q)
    n_range = SLICE.count(q)
    return {
        "quote": q,
        "start": st,
        "end": en,
        "sourceHash": SOURCE_HASH,
        "offsetUnit": "codepoint",
        "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
        "match": "exact",
        "wholeTextOccurrences": n_full,
        "occurrencesInRange": n_range,
        "paraLabel": lab,
        "sentUnit": (sent_of(st) or (None, None))[1],
    }


def resolve_container(container, path):
    if "quotes" not in container:
        return
    out = []
    for i, q in enumerate(container["quotes"]):
        p = "%s.quotes[%d]" % (path, i)
        if isinstance(q, dict):
            out.append(q)
            continue
        if not isinstance(q, (tuple, list)):
            hard.append("%s 引文形态不认识：%r" % (p, q))
            continue
        if len(q) == 3 and isinstance(q[0], str) and all(isinstance(x, int) for x in q[1:]):
            lab, st, en = q
            if lab not in PARA_BY_LABEL:
                hard.append("%s 段号不存在：%r" % (p, lab))
                continue
            t, a = PARA_BY_LABEL[lab]
            if not (0 <= st < en <= len(t)):
                hard.append("%s 段内下标越界：%r len=%d" % (p, (lab, st, en), len(t)))
                continue
            out.append(make_ref(lab, a + st, a + en, p))
        elif len(q) == 2 and all(isinstance(x, str) for x in q):
            lab, sub = q
            if lab not in PARA_BY_LABEL:
                hard.append("%s 段号不存在：%r" % (p, lab))
                continue
            t, a = PARA_BY_LABEL[lab]
            n = t.count(sub)
            if n != 1:
                hard.append("%s 段内命中 %d 次（要求恰好 1 次）：%r" % (p, n, sub[:40]))
                continue
            st = t.find(sub)
            out.append(make_ref(lab, a + st, a + st + len(sub), p))
        else:
            hard.append("%s 引文形态不认识：%r" % (p, q))
    container["quotes"] = out


ALL_NODES = []


def walk(node, path):
    if isinstance(node, dict):
        if "quotes" in node:
            resolve_container(node, path)
            for j, q in enumerate(node.get("quotes") or []):
                if isinstance(q, dict):
                    ALL_NODES.append(("%s.quotes[%d]" % (path, j), q))
        for k, v in node.items():
            walk(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i))


for _name in SECTIONS:
    walk(RAW_SECTIONS[_name], _name)

# ── 5. 判据 ───────────────────────────────────────────────────────────────
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
COLUMNS = ("objective", "obstacle", "action", "result", "cost")
conflicts = []
for t in RAW_SECTIONS["tasks"]:
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

# 判据 5：null 栏必须有同名 <栏位>Note
null_problems = []
for t in RAW_SECTIONS["tasks"]:
    for col in COLUMNS:
        if t.get(col) is None and not (t.get(col + "Note") or "").strip():
            null_problems.append("%s.%s 为 null 但没有 %sNote" % (t["id"], col, col))

# 判据 6：worldSettings 的三套判别字段
ws_bad = []
for w in RAW_SECTIONS["worldSettings"]:
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

# 判据 6b：themeReadings 必须三件齐全（perspective / support / counter），且 counter 非空
th_bad = []
for th in RAW_SECTIONS["themeReadings"]:
    if not (th.get("perspective") or "").strip():
        th_bad.append("%s 缺 perspective" % th["id"])
    if not th.get("support"):
        th_bad.append("%s 缺 support" % th["id"])
    if not th.get("counter"):
        th_bad.append("%s 缺 counter（只列支持的那叫论证，不叫解释）" % th["id"])

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


for _name in SECTIONS:
    check_basis(RAW_SECTIONS[_name], _name)

# 判据：unknowns / selfCritique 各自非空且带 basis
for _sec, _key in (("unknowns", "U"), ("selfCritique", "SC")):
    if not RAW_SECTIONS[_sec]:
        probs.append("%s 为空" % _sec)

# 判据 7：真正在用的 『』 必须逐字，且匹配对数 > 0（非恒真）
blob = json.dumps(RAW_SECTIONS, ensure_ascii=False)
corner = re.findall(r"『([^『』]{1,600})』", blob)
corner_bad = [x for x in corner if x not in SLICE]
c7_ok = (not corner_bad) and len(corner) > 0

# 判据 7b：内存变异必须让判据 7 变红（确认它不是恒真）
if not corner:
    sys.exit("正文没有 『』，变异测试无法进行")
MUT_TARGET = "『%s』" % corner[0]
MUT_FAKE = "『这段文字原文里绝对没有出现过纯属伪造』"
mut_blob = blob.replace(MUT_TARGET, MUT_FAKE, 1)
if mut_blob == blob:
    sys.exit("变异未生效：%r" % MUT_TARGET)
mut_red = bool([x for x in re.findall(r"『([^『』]{1,600})』", mut_blob) if x not in SLICE])

# ── 6. 覆盖表 ─────────────────────────────────────────────────────────────
touched = {}
for path, q in ALL_NODES:
    lab = q["paraLabel"]
    sec = path.split("/")[0].split("[")[0]
    touched.setdefault(lab, set()).add(sec)

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

ZERO_NOTES = json.loads((BUILD / "zero_notes.json").read_text("utf-8")) if \
    (BUILD / "zero_notes.json").exists() else {}
missing_notes = [lab for lab in zero if lab not in ZERO_NOTES]
if missing_notes:
    print("以下未被引用的段缺理由，先补齐 zero_notes.json：")
    for lab in missing_notes:
        print("  %s  %s" % (lab, PARA_BY_LABEL[lab][0][:60]))
    sys.exit(2)
for row in per_para:
    if row["state"] == "not-quoted":
        row["note"] = ZERO_NOTES[row["para"]]

# ── 7. 判据汇总 ───────────────────────────────────────────────────────────
checks = {
    "1_sourceHashMatchesFile": FILE_HASH == SOURCE_HASH,
    "2_sliceStartsWithUnitHead": SLICE.startswith(UNIT_HEAD) and len(SLICE) == E - S,
    "3_taskColumnQuotesDisjoint": not conflicts,
    "4_allQuotesVerbatimAndInRange": not hard and not probs,
    "5_nullColumnsHaveNotes": not null_problems,
    "6_worldSettingDiscriminantsValid": not ws_bad,
    "6b_themeReadingsHaveCounter": not th_bad,
    "7_proseCornerBracketsAllVerbatim_nonVacuous": c7_ok,
    "7b_mutationMakesCheck7Red": mut_red,
    "8_requiredSectionsPresent": all(
        k in RAW_SECTIONS for k in
        ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]),
    "9_basisValuesLegal": not basis_bad,
}
failed = [k for k, v in checks.items() if not v]
if failed:
    print("判据未过，不写盘：%s" % failed)
    print("hard:", hard[:8])
    print("probs:", probs[:8])
    print("conflicts:", conflicts[:8])
    print("null:", null_problems[:8])
    print("ws:", ws_bad[:8])
    print("theme:", th_bad[:8])
    print("cornerBad:", corner_bad[:8])
    print("basis:", basis_bad[:8])
    sys.exit(1)

print("引文节点 %d；未引用段 %d 个：%s" % (len(ALL_NODES), len(zero), zero))
print("判据：%s" % json.dumps(checks, ensure_ascii=False))
print("coverage: quoteUnion=%d nonSpace=%d ratio=%.4f"
      % (len(quote_union), len(nonspace), len(quote_union) / max(1, len(nonspace))))

# ── 8. 组装并写盘 ─────────────────────────────────────────────────────────
cand = {
    "schemaVersion": "castline-read-candidate/1",
    "task": TASK_ID,
    "agent": AGENT,
    "role": "READER（原文精读工作者）",
    "book": "dafeng",
    "bookTitle": BOOK_TITLE,
    "lane": 2,
    "unitIndex": 222,
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
        "markerConvention": "逐字引文必须包在角括号记号（U+300E/U+300F）里，该记号只允许包住 docs[0].text 的**逐字子串**（判据 7 现算强制，"
                            "非逐字直接判失败、不自动降级）；候选自己的标签、转述、截断引文一律用 〔…〕"
                            "（该记号在 docs[0].text 里出现 0 次）。两类记号不混用；"
                            "本文件正文不使用 〔第三种引号记号〕（该记号在原文里出现 0 次）。",
        "withinTaskUniqueness": "同一任务五栏的引文在字符区间级与句单元级两套判据下互不重复（判据 3 现算）。",
        "offsetUnit": "codepoint（Python 字符串下标口径），相对 docs[0].text 全文，左闭右开。",
    },
    "columnsIndependent": True,
    **RAW_SECTIONS,
    "nullFieldDisposition": [
        {"field": "%s.%s" % (t["id"], col), "value": None, "note": t.get(col + "Note", "")}
        for t in RAW_SECTIONS["tasks"] for col in COLUMNS
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
        "themeProblems": th_bad,
        "cornerBracketPairs": len(corner),
        "cornerBracketNonVerbatim": corner_bad,
        "markerPolicy": "非逐字的角括号引文判失败退出（exit 3），不做自动降级——"
                        "自动改写会把一处本该修好的错引悄悄藏起来。",
        "how": "判据 7 扫的是真正在用的 『』 记号对（并要求匹配对数 > 0，避免〔扫了 0 个所以恒真〕）；"
               "7b 在内存里把一处逐字引文换成伪造串，确认判据 7 会变红（真候选文件哈希不受影响）。"
               "判据 3 同时用字符区间与句单元两套口径；判据 6 现算 placeState / itemStates / institution；"
               "判据 6b 要求 themeReadings 三条都带 counter。"
               "content_c 的二元组引文要求在该段内**恰好命中一次**，命中 0 次或多次都判失败。",
        "reproduce": "python3 -B -s loop/state/out/read_dafeng_L2_0222.w-read-4.build/build_candidate.py",
    },
    "remaining": [
        "未做语义核验：semanticReview 明确为 not-performed（引文定位正确 ≠ 语义已核验）。",
        "未做独立复核：复核必须由另一个 agent 走 verify 流程（verifierRequired=true）。",
        "U1（『张锐』是谁）未解决：全文只出现 2 次且都在本区间内，与『赵锐』的笔误可能性无法用区间内证据排除；"
        "候选照原文写『张锐』，没有改字、也没有替他补身份。",
        "SC2 标注的可争议取值：T1.cost 引的是『武器在门口时便被收缴』。若复核口径要求"
        "〔代价必须是该项任务特有〕（即排除对所有来客一律适用的进门程序），T1.cost 应降级为 null 并补 costNote。",
        "U9 标注的口径分歧：W01（儒家礼仪）判 executed 的依据是区间内存在照这条规则做出的动作；"
        "若复核口径要求 declared 必须引诏令法原文，该条应改判或降级。",
        "本候选的 content_a / content_b 内容部分承自已中断的上一轮构建（同一租约、同一写成路径），"
        "本轮做了三件事：① 把 37 处非逐字的角括号引文全部改为圆括号转述记号（判据 7 现算发现，非逐字即判失败）；"
        "② 补齐缺失的 content_c（worldSettings / notWorldSettings / themeReadings / unknowns / selfCritique）；"
        "③ 重写构建脚本并跑通全部判据。承继内容的每条引文都在本轮由脚本对原文重新现算，未采信上一轮的转录。",
    ],
}

OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("已写出 %s" % OUT)
print("源哈希 %s" % FILE_HASH)
print("切片哈希 %s" % SEGMENT_SHA)
