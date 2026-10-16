# -*- coding: utf-8 -*-
"""read:dafeng:L2:0214 —— 重建候选（w-sanguo-0，本轮）。

为什么需要这一步（不是重写分析，而是修两处真实缺陷）：
  · 上一轮崩溃遗留的候选（agent 同为 w-sanguo-0，已留档
    read_dafeng_L2_0214.candidate.crashed-run-20261015T0530Z.json）在**引文定位**上
    经独立复算 0 缺陷（205 条 quote 全部 TEXT[start:end]==quote），但有两处记号层缺陷：
      1. machineSelfCheck.checks['7_proseBracketsAllVerbatim'] 扫的是 「」，而本文件
         「 出现 0 次、全部标签与引文都写 『』 —— **判据恒真，永远不可能变红**。
      2. quotePolicy.bracketConvention 声称 『』 只包逐字原文，实测 254 个 『』 跨度里
         47 个在 docs[0].text 里 find 不到（是候选自己的标签/转述），另有若干省略号截断形态。
         两类东西共用同一记号，读者无法区分。
本脚本做的：把非逐字的 『…』 一律改写成 〔…〕（该记号在原文 0 次出现），
『…』 只保留原文逐字；判据 7 改扫真正在用的 『』 并要求**匹配对数 > 0**（非恒真），
外加一个**内存变异自检**证明这条判据会变红。分析层内容沿用上一轮（含其 basis 标注），
本轮只做记号层与判据层的修复 + 提交前的现算复核。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L2_0214.candidate.json"
PRIOR = (ROOT / "loop/state/out/read_dafeng_L2_0214.w-sanguo-0.build"
         / "read_dafeng_L2_0214.candidate.crashed-run-20261015T0530Z.json")
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 796142, 799532
UNIT_HEAD = "第两百一十三章 惊愕"

RAW = DOCS.read_bytes()
if hashlib.sha256(RAW).hexdigest() != SOURCE_HASH:
    sys.exit("源文件哈希不符，停止")
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[S:E]
assert SLICE.startswith(UNIT_HEAD), "切片不以本单元标题开头"

# 段落索引（相对全文的绝对 codepoint）
PARAS = []
_off = S
for _line in SLICE.split("\n"):
    if _line.strip():
        PARAS.append((_line.strip(), _off + (len(_line) - len(_line.lstrip()))))
    _off += len(_line) + 1
PARA_TEXT = {("P%03d" % i): t for i, (t, _a) in enumerate(PARAS)}


def para_of(pos):
    for i, (t, a) in enumerate(PARAS):
        if a <= pos < a + len(t):
            return "P%03d" % i
    return None


cand = json.loads(PRIOR.read_text("utf-8"))

# ── 记号层变换：非逐字的 『…』 → 〔…〕 ───────────────────────────────────────
SPAN = re.compile(r"『([^『』]{1,400})』")
stats = {"keptVerbatim": 0, "relabeled": 0, "relabeledSamples": []}


def fix(s):
    out, last = [], 0
    for m in SPAN.finditer(s):
        inner = m.group(1)
        out.append(s[last:m.start()])
        if inner in SLICE:
            stats["keptVerbatim"] += 1
            out.append(m.group(0))
        else:
            stats["relabeled"] += 1
            if len(stats["relabeledSamples"]) < 60:
                stats["relabeledSamples"].append(inner)
            out.append("〔%s〕" % inner)
        last = m.end()
    out.append(s[last:])
    return "".join(out)


def walk_strings(node):
    if isinstance(node, dict):
        return {k: walk_strings(v) for k, v in node.items()}
    if isinstance(node, list):
        return [walk_strings(v) for v in node]
    if isinstance(node, str):
        return fix(node)
    return node


SECTIONS = ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeDiffs",
            "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
            "themeReadings", "unknowns", "selfCritique"]
for name in SECTIONS:
    cand[name] = walk_strings(cand[name])
cand["coverage"]["perParagraph"] = walk_strings(cand["coverage"]["perParagraph"])

# ── 现算判据 ────────────────────────────────────────────────────────────────
probs = []
nodes = []


def collect(o, path=""):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            nodes.append((path, o))
        for k, v in o.items():
            collect(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            collect(v, path + "[%d]" % i)


for name in SECTIONS:
    collect(cand[name], name)

for path, q in nodes:
    if TEXT[q["start"]:q["end"]] != q["quote"]:
        probs.append("偏移不成立 %s" % path)
    if not (S <= q["start"] and q["end"] <= E):
        probs.append("越界 %s" % path)
    if q.get("sourceHash") != SOURCE_HASH:
        probs.append("sourceHash %s" % path)
    if q.get("wholeTextOccurrences") != TEXT.count(q["quote"]):
        probs.append("全文次数 %s" % path)
    if q.get("occurrencesInRange") != SLICE.count(q["quote"]):
        probs.append("区间次数 %s" % path)
    if q.get("paraLabel") and q["paraLabel"] != para_of(q["start"]):
        probs.append("段号 %s" % path)

# 判据 7（修好后）：扫真正在用的 『』，要求逐字，且**必须匹配到东西**
blob = json.dumps({k: cand[k] for k in SECTIONS}, ensure_ascii=False)
corner = re.findall(r"『([^『』]{1,400})』", blob)
bracket_bad = [x for x in corner if x not in SLICE]
c7_ok = (not bracket_bad) and len(corner) > 0

# 五栏不共用（句单元级 + 字符区间级）
_SEP = re.compile(r"[。！？…]+")


def sent_units(t):
    o, last = [], 0
    for m in _SEP.finditer(t):
        o.append((last, m.end()))
        last = m.end()
    if last < len(t):
        o.append((last, len(t)))
    return o or [(0, len(t))]


SENT = {("P%03d" % i): sent_units(t) for i, (t, _a) in enumerate(PARAS)}


def sent_of(pos):
    p = para_of(pos)
    if not p:
        return None
    base = dict(PARAS and [("P%03d" % i, a) for i, (_t, a) in enumerate(PARAS)])[p]
    rel = pos - base
    for k, (a, b) in enumerate(SENT[p]):
        if a <= rel < b:
            return (p, k)
    return (p, 0)


conflicts = []
for t in cand["tasks"]:
    seen = {}
    for col in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(col)
        if not v:
            continue
        for q in v.get("quotes", []):
            k = (q["start"], q["end"])
            if k in seen:
                conflicts.append("%s %s/%s 区间共用" % (t["id"], seen[k], col))
            seen[k] = col
            sk = sent_of(q["start"])
            if sk in [x for x in seen.values()]:
                pass
    seen2 = {}
    for col in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(col)
        if not v:
            continue
        for q in v.get("quotes", []):
            sk = sent_of(q["start"])
            if sk in seen2 and seen2[sk] != col:
                conflicts.append("%s %s/%s 句单元共用 %s" % (t["id"], seen2[sk], col, sk))
            seen2[sk] = col
# cost=null 必须有 Note
nullprobs = [t["id"] for t in cand["tasks"]
             if t.get("cost") is None and not t.get("costNote")]

# 变异自检：把一处**确实存在**的逐字 『』 换成原文不存在的伪造串，判据 7 必须变红（只在内存做）。
# 第一版写死了一个带句号的锚（『果然还是纸做的。』），实测该串不存在 ⇒ replace 不生效、
# 变异恒不红，assert 当场把这次运行拦下。这正是「变异必须确认目标真的被改到」的价值。
MUT_TARGET = "『果然还是纸做的』"
MUT_FAKE = "『这段文字原文里绝对没有出现过纯属伪造』"
assert MUT_TARGET in blob, "变异目标不在正文里，变异无意义"
mut_blob = blob.replace(MUT_TARGET, MUT_FAKE, 1)
assert mut_blob != blob, "变异未生效"
mut_bad = [x for x in re.findall(r"『([^『』]{1,400})』", mut_blob) if x not in SLICE]
mut_red = bool(mut_bad)
# 反向对照：不改时判据 7 是绿的（非恒真也非恒假）
assert c7_ok and mut_red, "判据 7 的变异自检未按预期变红"

checks = {
    "1_sourceHashMatchesFile": hashlib.sha256(RAW).hexdigest() == SOURCE_HASH,
    "2_sliceStartsWithUnitHead": SLICE.startswith(UNIT_HEAD) and len(SLICE) == E - S,
    "3_taskColumnQuotesDisjoint": not conflicts,
    "4_allQuotesVerbatimAndInRange": not probs,
    "5_nullCostHasNote": not nullprobs,
    "7_proseCornerBracketsAllVerbatim_nonVacuous": c7_ok,
    "7b_mutationMakesCheck7Red": mut_red,
    "8_requiredSectionsPresent": all(
        k in cand for k in ["tasks", "causeEdges", "states", "foreshadows",
                            "worldSettings", "themeReadings"]),
}
failed = [k for k, v in checks.items() if not v]
if failed:
    print("判据未过，不写盘：%s" % failed)
    print("probs:", probs[:5], "conflicts:", conflicts[:5], "bracketBad:", bracket_bad[:5])
    sys.exit(1)

cand["quotePolicy"] = {
    "markerConvention": "『…』 只允许包住 docs[0].text 的**逐字子串**（判据 7 现算强制）；"
                        "候选自己的标签、转述、截断引文一律用 〔…〕（该记号在 docs[0].text 里出现 0 次）。"
                        "两类记号不再混用 —— 这是上一轮崩溃稿的真实缺陷（254 个 『』 里 47 个非逐字）。",
    "withinTaskUniqueness": "同一任务五栏的引文在字符区间级与句单元级两套判据下互不重复（判据 3 现算）。",
    "offsetUnit": "codepoint（Python 字符串下标口径），相对 docs[0].text 全文，左闭右开。",
}
cand["machineSelfCheck"] = {
    "quoteNodes": len(nodes),
    "checks": checks,
    "columnConflicts": conflicts,
    "nullProblems": nullprobs,
    "cornerBracketPairs": len(corner),
    "cornerBracketNonVerbatim": bracket_bad,
    "markerTransform": {"keptVerbatim": stats["keptVerbatim"],
                        "relabeledToCorner": stats["relabeled"],
                        "relabeledSamples": stats["relabeledSamples"][:12]},
    "how": "判据 7 扫的是真正在用的 『』（并要求匹配对数 > 0，避免「扫了 0 个所以恒真」）；"
           "7b 在内存里把一处逐字引文换成伪造串，确认判据 7 会变红（真候选文件哈希不受影响）。",
}
cand["reworkOf"] = ("loop/state/out/read_dafeng_L2_0214.w-sanguo-0.build/"
                    "read_dafeng_L2_0214.candidate.crashed-run-20261015T0530Z.json")
cand["reworkReason"] = ("上一轮 agent 进程在写盘后未完成提交（崩溃遗留稿，无提交记录、无 REJECTED）；"
                        "本轮接手后独立复算其 205 条引文定位 0 缺陷，但发现判据 7 恒真"
                        "（扫的 「」 在文件里出现 0 次）与 『』 记号混用 47 处非逐字，"
                        "故重建记号层与判据层后重新提交。")

OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("已写出 %s" % OUT)
print("引文节点 %d；『』 对数 %d（非逐字 %d）；改为 〔〕 %d 处"
      % (len(nodes), len(corner), len(bracket_bad), stats["relabeled"]))
print("自检：%s" % json.dumps(checks, ensure_ascii=False))
