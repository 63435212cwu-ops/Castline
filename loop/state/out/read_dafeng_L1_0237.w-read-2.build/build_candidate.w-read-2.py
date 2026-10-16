#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 content_core.py 生成 read_dafeng_L1_0237.candidate.json。

设计原则（与上一单元 w-read-2 的构建器同源）：
  · content_core.py 里**不出现任何手写偏移**：每条引文只给字符串，
    本脚本在 docs[0].text[S:E] 切片内 find() 后 +S 换算成全文偏移。
  · find 不到 / 切片内不唯一 / 越界 / 引文跨出切片 —— 一律**构建失败**，
    不产出一个带瑕疵的候选。
  · 所有计数（覆盖率、四态统计、引文实例数）**从数据生成**，不手写。
  · 构建前先跑一组判据（B1–B14），判据不过就不写文件。

用法（从仓库根）：
  python3 -B -s loop/state/out/read_dafeng_L1_0237.w-read-2.build/build_candidate.w-read-2.py
"""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]          # …/loop/state/out/<build> → 仓库根（星系）
sys.path.insert(0, str(HERE))

import content_core as CC  # noqa: E402

DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
GRAPH = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"
OUT = ROOT / "loop/state/out/read_dafeng_L1_0237.candidate.json"
S, E = 943450, 948891
EXPECT_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

problems: list[str] = []
notes: list[str] = []


def bad(tag, msg):
    problems.append(f"[{tag}] {msg}")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ── 原文 ────────────────────────────────────────────────────────────────
raw = DOCS.read_bytes()
file_hash = sha256_bytes(raw)
if file_hash != EXPECT_HASH:
    bad("B1", f"docs.json sha256 {file_hash} != {EXPECT_HASH}")
text = json.loads(raw.decode("utf-8"))[0]["text"]
SLICE = text[S:E]
if SLICE[: len(CC.UNIT_HEAD)] != CC.UNIT_HEAD:
    bad("B2", f"切片未以单元标题开头：{SLICE[:20]!r}")
slice_sha = sha256_bytes(SLICE.encode("utf-8"))

# ── 引文登记表：字符串 → 偏移。任何引用都经这里，杜绝手写偏移 ───────────
REG: dict[str, tuple[int, int]] = {}
ALLOWED_REUSE: set[str] = set()


def ref(q: str, *, allow_reuse: bool = False) -> dict:
    """把一个引文字符串解析成 {quote,start,end,sourceHash}。"""
    if q not in REG:
        n = SLICE.count(q)
        if n == 0:
            bad("B3", f"引文在切片内找不到：{q[:60]!r}")
            return {"quote": q, "start": -1, "end": -1, "sourceHash": EXPECT_HASH}
        if n > 1:
            bad("B3", f"引文在切片内不唯一（{n} 次）：{q[:60]!r}")
            return {"quote": q, "start": -1, "end": -1, "sourceHash": EXPECT_HASH}
        i = SLICE.index(q)
        REG[q] = (S + i, S + i + len(q))
    if allow_reuse:
        ALLOWED_REUSE.add(q)
    return {"quote": q, "start": REG[q][0], "end": REG[q][1], "sourceHash": EXPECT_HASH}


def rule(text_s: str) -> str:
    """把自述里的 {占位符} 换成从数据实算的计数。"""
    def sub(m):
        key = m.group(1)
        return str(COUNTS.get(key, m.group(0)))
    return re.sub(r"\{([a-z_]+)\}", sub, text_s)


# ── 组装：tasks ─────────────────────────────────────────────────────────
FIVE = ("objective", "obstacle", "action", "result", "cost")
tasks_out = []
for t in CC.TASKS:
    o = {"id": t["id"], "name": t["name"], "actor": t["actor"], "actorBasis": t["actorBasis"],
         "actorNote": t["actorNote"]}
    for f in FIVE:
        v = t.get(f)
        if v is None:
            o[f] = None
            o[f + "Note"] = t[f + "Note"]
        else:
            # 静默丢字段是真实缺陷形态（内容写了、产物里没有）：这里显式枚举允许的键，
            # 出现未消费的键就让构建失败，而不是装作没写。
            unknown = set(v) - {"text", "basis", "quotes", "note"}
            if unknown:
                bad("B16", f"{t['id']}.{f} 有未消费的键 {sorted(unknown)}（会被静默丢掉）")
            o[f] = {"text": v["text"], "basis": v["basis"],
                    "quotes": [ref(q) for q in v["quotes"]]}
            if v.get("note"):
                o[f]["note"] = v["note"]
    if t.get("note"):
        o["note"] = t["note"]
    tasks_out.append(o)

# ── causeEdges ──────────────────────────────────────────────────────────
edges_out = []
EDGE_KEYS = {"id", "from", "to", "mechanism", "basis", "quotes", "note"}
for e in CC.CAUSE_EDGES:
    _u = set(e) - EDGE_KEYS
    if _u:
        bad("B16", f"causeEdge {e.get('id')} 有未消费的键 {sorted(_u)}")
    d = {"id": e["id"], "from": e["from"], "to": e["to"], "mechanism": e["mechanism"],
         "basis": e["basis"], "quotes": [ref(q) for q in e["quotes"]]}
    if e.get("note"):
        d["note"] = e["note"]
    edges_out.append(d)

rejected_out = [dict(r) for r in CC.REJECTED_EDGES]

# ── states ──────────────────────────────────────────────────────────────
states_out = []
ST_KEYS = {"id", "kind", "who", "basis", "before", "after", "anchor", "knownBy",
           "notKnownBy", "evidence", "note"}
for s in CC.STATES:
    _u = set(s) - ST_KEYS
    if _u:
        bad("B16", f"state {s.get('id')} 有未消费的键 {sorted(_u)}")
    d = {"id": s["id"], "kind": s["kind"], "who": s["who"], "basis": s["basis"]}
    if s["kind"] == "change":
        for f in ("before", "after", "anchor"):
            d[f] = {"text": s[f]["text"], "quotes": [ref(q) for q in s[f]["quotes"]]}
    else:
        d["knownBy"] = list(s["knownBy"])
        d["notKnownBy"] = list(s["notKnownBy"])
        d["evidence"] = {k: [ref(q) for q in v] for k, v in s["evidence"].items()}
    if s.get("note"):
        d["note"] = s["note"]
    states_out.append(d)

# ── foreshadows ─────────────────────────────────────────────────────────
fores_out = []
FORE_KEYS = {"id", "name", "setup", "payoff", "status", "basis", "payoffNote"}
for f in CC.FORESHADOWS:
    _u = set(f) - FORE_KEYS
    if _u:
        bad("B16", f"foreshadow {f.get('id')} 有未消费的键 {sorted(_u)}")
    d = {"id": f["id"], "name": f["name"],
         "setup": [ref(q) for q in f["setup"]],
         "payoff": [ref(q) for q in f["payoff"]],
         "status": f["status"], "basis": f["basis"], "payoffNote": f["payoffNote"]}
    fores_out.append(d)

not_fores_out = [dict(x) for x in CC.NOT_FORESHADOWS]

# ── worldSettings ───────────────────────────────────────────────────────
world_out = []
WS_KEYS = {"id", "kind", "name", "institution", "explain", "placeState", "arrivalEvidence",
           "itemStates", "stateEvidence", "basis", "quote", "extraQuotes", "counterEvidence",
           "note", "tagNote"}
for w in CC.WORLD_SETTINGS:
    _u = set(w) - WS_KEYS
    if _u:
        bad("B16", f"worldSetting {w.get('id')} 有未消费的键 {sorted(_u)}")
    d = {"id": w["id"], "kind": w["kind"], "name": w["name"]}
    if w["kind"] == "rule":
        d["institution"] = w["institution"]
        d["explain"] = w["explain"]
    elif w["kind"] == "place":
        d["placeState"] = w["placeState"]
        d["explain"] = w["explain"]
        if w.get("arrivalEvidence"):
            d["arrivalEvidence"] = [ref(q, allow_reuse=True) for q in w["arrivalEvidence"]]
    else:
        d["itemStates"] = list(w["itemStates"])
        d["stateEvidence"] = {k: [ref(q, allow_reuse=True) for q in v]
                              for k, v in w["stateEvidence"].items()}
        d["explain"] = w["explain"]
    d["basis"] = w["basis"]
    d["quote"] = w["quote"]
    d.update(ref(w["quote"], allow_reuse=True))
    for extra in ("extraQuotes", "counterEvidence"):
        if w.get(extra):
            d[extra] = [ref(q, allow_reuse=True) for q in w[extra]]
    for k in ("note", "tagNote"):
        if w.get(k):
            d[k] = w[k]
    world_out.append(d)

excluded_out = []
for x in CC.EXCLUDED_SETTINGS:
    d = {k: v for k, v in x.items() if k != "quotes"}
    if x.get("quotes"):
        # 被排除项也可能引用原文；照样走 ref() 解析，避免出现『无法核验的裸引文串』。
        d["quotes"] = [ref(q, allow_reuse=True) for q in x["quotes"]]
    excluded_out.append(d)

# ── themeReadings ───────────────────────────────────────────────────────
themes_out = []
for th in CC.THEME_READINGS:
    themes_out.append({"id": th["id"], "perspective": th["perspective"],
                       "support": [ref(q) for q in th["support"]],
                       "counter": th["counter"], "basis": th["basis"]})

unknowns_out = [dict(u) for u in CC.UNKNOWNS]
sc_out = [dict(s) for s in CC.SELF_CRITIQUE]

# ── 计数（从数据生成，供自述占位符使用）──────────────────────────────────
COUNTS = {
    "p_arr": sum(1 for w in world_out if w["kind"] == "place" and w["placeState"] == "arrived"),
    "p_men": sum(1 for w in world_out if w["kind"] == "place" and w["placeState"] == "mentioned"),
    "r_exec": sum(1 for w in world_out if w["kind"] == "rule" and w["institution"] == "executed"),
    "r_mis": sum(1 for w in world_out if w["kind"] == "rule" and w["institution"] == "misunderstood"),
    "r_dec": sum(1 for w in world_out if w["kind"] == "rule" and w["institution"] == "declared"),
    "i_hold": sum(1 for w in world_out if w["kind"] == "item" and "hold" in w["itemStates"]),
    "i_transfer": sum(1 for w in world_out if w["kind"] == "item" and "transfer" in w["itemStates"]),
    "i_use": sum(1 for w in world_out if w["kind"] == "item" and "use" in w["itemStates"]),
    "i_lose": sum(1 for w in world_out if w["kind"] == "item" and "lose" in w["itemStates"]),
}
COUNTS["w_total"] = len(world_out)
COUNTS["p_total"] = COUNTS["p_arr"] + COUNTS["p_men"]
COUNTS["i_total"] = sum(1 for w in world_out if w["kind"] == "item")
COUNTS["r_total"] = sum(1 for w in world_out if w["kind"] == "rule")
_null_list = [f"{t['id']}.{f}" for t in tasks_out for f in FIVE if t[f] is None]
COUNTS["t_n"] = len(tasks_out)
COUNTS["t_f"] = len(tasks_out) * len(FIVE)
COUNTS["t_null"] = len(_null_list)
COUNTS["t_null_list"] = "、".join(_null_list)

# ── B17 自述里的条数必须等于产物实际条数（防手写数字注水/漏改）────────
_NOTE_SAMPLES = {"causeEdges": CC.CAUSE_EDGES_NOTE, "unknowns": CC.UNKNOWNS_NOTE,
                 "foreshadows": CC.FORESHADOWS_NOTE, "selfCritique": CC.SELF_CRITIQUE_NOTE}
for key, pat, real in (("causeEdges", r"^(\d+)\s*条边", len(edges_out)),
                       ("unknowns", r"^(\d+)\s*条 unknowns", len(unknowns_out)),
                       ("foreshadows", r"^(\d+)\s*条伏笔", len(fores_out)),
                       ("selfCritique", r"^(\d+)\s*条", len(sc_out))):
    m = re.match(pat, rule(_NOTE_SAMPLES[key]).lstrip())
    if not m:
        bad("B17", f"{key} 的 note 开头找不到条数自述（无法对账）")
    elif int(m.group(1)) != real:
        bad("B17", f"{key} 的 note 自报 {m.group(1)} != 实际 {real}")

# ── 覆盖率（从数据生成）────────────────────────────────────────────────
paras, pos = [], S
for line in SLICE.split("\n"):
    if line.strip():
        paras.append({"start": pos, "end": pos + len(line), "text": line})
    pos += len(line) + 1


def walk(node, path="$"):
    """全深度遍历，**不早退**（父节点既可能有条目级 quote，也可能有嵌套依据）。"""
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
            yield path, node
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


SECS = ("tasks", "causeEdges", "rejectedEdges", "states", "foreshadows", "notForeshadows",
        "worldSettings", "excludedSettings", "themeReadings", "unknowns", "selfCritique")

cand = {
    "task": CC.TASK_ID, "agent": CC.AGENT, "role": "READER", "book": "dafeng",
    "lane": 1, "unitIndex": 237, "unitHead": CC.UNIT_HEAD,
    "sourceRange": [S, E], "sourceHash": EXPECT_HASH,
    "sliceCodepoints": len(SLICE), "sliceSha256": slice_sha,
    "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[943450:948891)",
    "tasks": tasks_out, "tasksNote": rule(CC.TASKS_NOTE),
    "causeEdges": edges_out, "causeEdgesNote": rule(CC.CAUSE_EDGES_NOTE),
    "rejectedEdges": rejected_out, "rejectedEdgesNote": CC.REJECTED_EDGES_NOTE,
    "states": states_out, "statesNote": rule(CC.STATES_NOTE),
    "foreshadows": fores_out, "foreshadowsNote": rule(CC.FORESHADOWS_NOTE),
    "notForeshadows": not_fores_out,
    "worldSettings": world_out, "worldSettingsNote": rule(CC.WORLD_SETTINGS_NOTE),
    "placesNote": rule(CC.PLACES_NOTE),
    "itemsNote": rule(CC.ITEMS_NOTE),
    "excludedSettings": excluded_out, "excludedSettingsNote": CC.EXCLUDED_SETTINGS_NOTE,
    "themeReadings": themes_out, "themeReadingsNote": rule(CC.THEME_READINGS_NOTE),
    "unknowns": unknowns_out, "unknownsNote": rule(CC.UNKNOWNS_NOTE),
    "selfCritique": sc_out, "selfCritiqueNote": CC.SELF_CRITIQUE_NOTE,
    "semanticReview": CC.SEMANTIC_REVIEW,
    "citationConvention": CC.CITATION_CONVENTION,
    "offsetCaliber": CC.OFFSET_CALIBER,
    "sourceHashScope": CC.SOURCE_HASH_SCOPE,
    "sliceSha256Scope": CC.SLICE_SHA_SCOPE,
    "graphCacheNotUsedAsEvidence": CC.GRAPH_CACHE_NOTE,
}

# ── B4 逐字 / 越界 / sourceHash ─────────────────────────────────────────
n_inst, distinct = 0, set()
for sec in SECS:
    for p, q in walk(cand.get(sec), sec):
        n_inst += 1
        distinct.add(q["quote"])
        if text[q["start"]:q["end"]] != q["quote"]:
            bad("B4", f"{p} 逐字不符")
        if not (S <= q["start"] and q["end"] <= E):
            bad("B4", f"{p} 越界 [{q['start']},{q['end']})")
        if q.get("sourceHash") != EXPECT_HASH:
            bad("B4", f"{p} sourceHash 不符")

# ── B5 五栏不得共用同一句 ───────────────────────────────────────────────
for t in tasks_out:
    seen = {}
    for f in FIVE:
        v = t.get(f)
        if isinstance(v, dict):
            for q in v["quotes"]:
                if q["quote"] in seen:
                    bad("B8", f"{t['id']}: {seen[q['quote']]} 与 {f} 共用 {q['quote'][:30]!r}")
                seen[q["quote"]] = f

# ── B6 null 必须带 Note；有值栏位必须带引文与合法 basis ─────────────────
VALID_BASIS = {"explicit", "inferred", "derived", "unverified"}
for t in tasks_out:
    for f in FIVE:
        if f not in t:
            bad("B6", f"{t['id']} 缺栏位 {f}")
        elif t[f] is None:
            if not (t.get(f + "Note") or "").strip():
                bad("B6", f"{t['id']}.{f} 裸 null 无 Note")
        else:
            if not t[f]["quotes"]:
                bad("B6", f"{t['id']}.{f} 有结论无引文")
            if t[f]["basis"] not in VALID_BASIS:
                bad("B6", f"{t['id']}.{f} basis 非法")

# ── B7 分析文字里不得出现原文用的引号符号（防把自己的话伪装成原文）────
def scan_own_words(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "quote" or k == "sourceHash":
                continue
            yield from scan_own_words(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from scan_own_words(v, f"{path}[{i}]")
    elif isinstance(node, str):
        if "「" in node or "」" in node or "“" in node or "”" in node:
            yield path, node


for p, s in scan_own_words(cand):
    bad("B7", f"{p} 分析文字里出现原文引号符号：{s[:60]!r}")

# ── B9 顺序判据 ─────────────────────────────────────────────────────────
ORDER_RE = re.compile(r"先[^。；]{0,40}?[，,、]?\s*(?:随后|再|然后|才|紧接着)|紧接着|下一段")
for e in edges_out:
    o = [q["start"] for q in e["quotes"]]
    if o != sorted(o):
        bad("B9", f"causeEdge {e['id']} 引文非升序 {o}")
for t in tasks_out:
    ac = [q["start"] for q in (t.get("action") or {}).get("quotes", [])] if isinstance(t.get("action"), dict) else []
    r = [q["start"] for q in (t.get("result") or {}).get("quotes", [])] if isinstance(t.get("result"), dict) else []
    if ac and r and max(ac) > max(r):
        bad("B9", f"task {t['id']} action@max{max(ac)} 晚于 result@max{max(r)}")
for s in states_out:
    if s["kind"] != "change":
        continue
    b = [q["start"] for q in s["before"]["quotes"]]
    a = [q["start"] for q in s["after"]["quotes"]]
    an = [q["start"] for q in s["anchor"]["quotes"]]
    if min(b) > max(a):
        bad("B9", f"state {s['id']} before 晚于 after")
    if not (min(b) <= min(an) <= max(a)):
        bad("B9", f"state {s['id']} 锚点@{min(an)} 不在 [{min(b)},{max(a)}]")
for f in fores_out:
    su = [q["start"] for q in f["setup"]]
    pa = [q["start"] for q in f["payoff"]]
    if su and pa and max(su) > min(pa):
        bad("B9", f"foreshadow {f['id']} setup 晚于 payoff")

# ── B10 跨分区复用披露（从数据生成）────────────────────────────────────
where: dict[str, set] = {}
for sec in SECS:
    for _, q in walk(cand.get(sec), sec):
        where.setdefault(q["quote"], set()).add(sec)
reuse = [{"quote": q, "start": REG[q][0], "end": REG[q][1], "sourceHash": EXPECT_HASH,
          "sections": sorted(v)} for q, v in where.items() if len(v) > 1]
reuse.sort(key=lambda x: x["start"])
cand["crossSectionQuoteReuse"] = reuse
cand["crossSectionQuoteReuseNote"] = (
    f"跨分区复用如实披露：同一句原文出现在两个以上分区时逐条列出（{len(reuse)} 条，"
    "**由构建脚本从数据生成**，不是手写计数）。判据是同一任务内五栏不得共用一句；"
    "跨分区复用说明同一句被用于不同用途，这类复用我没有隐藏，请复核者判断是否恰当。"
)

# ── 语音层披露（带 “” 的引文 = 人物话语）──────────────────────────────
speech = []
for sec in SECS:
    for p, q in walk(cand.get(sec), sec):
        if "“" in q["quote"] or "”" in q["quote"]:
            speech.append((q["quote"], q["start"], q["end"], sec))
speech_spans = len(speech)
speech_note = {
    "policy": "带 U+201C/U+201D（弯引号）的引文 = 人物话语（或叙述对其话语的转述）。"
              "它们只用于证明『谁说了什么』，不作为『事情就是如此』的事实依据；"
              "凡涉及世界事实的结论，我都另找了叙述句作依据。"
              "本字段用码位而不是字符本身来指称该符号，以便审计脚本那条"
              "『分析文字里不得出现原文引号』的断言保持全树无豁免。",
    "speechSpans": speech_spans,
    "checkedCount": len({s[0] for s in speech}),
    "dispositionOfEach": [
        {"quote": q, "start": st, "end": en, "sourceHash": EXPECT_HASH, "sections": [sec],
         "usedFor": "只证明这句话被说出（或被告知），不作为『事情就是如此』的事实依据；"
                    "凡由它引出的世界事实结论，均另引叙述句。"}
        for q, st, en, sec in speech
    ],
}
cand["speechLayerDisclosure"] = speech_note

# ── 覆盖率（从数据生成）────────────────────────────────────────────────
touched = set()
for sec in SECS:
    for _, q in walk(cand.get(sec), sec):
        for p in paras:
            if q["start"] < p["end"] and p["start"] < q["end"]:
                touched.add(p["start"])
zero = [p for p in paras if p["start"] not in touched]
cand["coverage"] = {
    "nonEmptyParagraphs": len(paras),
    "paragraphsTouchedByQuotes": len(touched),
    "zeroCoverageParagraphs": len(zero),
    "zeroCoverageList": [{"start": p["start"], "end": p["end"], "text": p["text"]} for p in zero],
    "zeroCoverageListNote": "zeroCoverageList[].text 是**原文段落原样拷贝**（供复核者直接比对，"
                            "不是我写的分析文字），所以它里面会出现原文的对白引号；"
                            "本条目的其余字段都是我的用语。审计脚本据此把该字段排除在"
                            "『分析文字不得出现原文引号』的判据之外，排除范围在审计侧显式声明。",
}

cand["buildDisclosure"] = {
    "builder": "loop/state/out/read_dafeng_L1_0237.w-read-2.build/build_candidate.w-read-2.py",
    "contentCore": "loop/state/out/read_dafeng_L1_0237.w-read-2.build/content_core.py",
    "howOffsetsWereMade": "content_core.py 里不出现任何手写偏移：每条引文只给字符串，"
                          "偏移由本脚本在切片内 find() 后 +943450 换算；find 不到、切片内不唯一、越界"
                          "一律让构建失败。",
    "countsAreGenerated": "worldSettingsNote / placesNote / itemsNote / coverage / "
                          "crossSectionQuoteReuse 里的数字全部由本脚本从产物数据生成，不手写。",
}

# ── B15 不许出现『无法核验的裸引文串』────────────────────────────────
def bare_quote_lists(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("quotes", "setup", "payoff", "support", "arrivalEvidence", "counterEvidence"):
                if isinstance(v, list) and any(isinstance(x, str) for x in v):
                    yield f"{path}.{k}"
            yield from bare_quote_lists(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from bare_quote_lists(v, f"{path}[{i}]")


def state_evidence_bare(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "stateEvidence" and isinstance(v, dict):
                for st, arr in v.items():
                    if isinstance(arr, list) and any(isinstance(x, str) for x in arr):
                        yield f"{path}.stateEvidence.{st}"
            yield from state_evidence_bare(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from state_evidence_bare(v, f"{path}[{i}]")


for p in list(bare_quote_lists(cand)) + list(state_evidence_bare(cand)):
    bad("B15", f"{p} 里存在未解析的裸引文串（无法核验偏移与哈希）")

# ── B11 自述计数对账（用产物自身重算）──────────────────────────────────
if cand["coverage"]["paragraphsTouchedByQuotes"] != len(touched):
    bad("B11", "coverage 自述与重算不一致")

# ── B12 提示词要求的顶层分区必须存在 ───────────────────────────────────
for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
          "themeReadings", "unknowns", "selfCritique"):
    if k not in cand:
        bad("B12", f"缺分区 {k}")

# ── B13 结构判据 ────────────────────────────────────────────────────────
for e in edges_out:
    if not e["from"] or not e["to"] or not e["mechanism"].strip() or not e["quotes"]:
        bad("B13", f"edge {e['id']} 结构不完整")
for s in states_out:
    if s["kind"] == "change":
        for f in ("before", "after", "anchor"):
            if not s[f]["quotes"] or not s[f]["text"]:
                bad("B13", f"state {s['id']} 缺 {f}")
    else:
        if not isinstance(s["knownBy"], list) or not isinstance(s["notKnownBy"], list):
            bad("B13", f"state {s['id']} knownBy/notKnownBy 非数组")
        if not s["evidence"]:
            bad("B13", f"state {s['id']} 缺 evidence")
for f in fores_out:
    if not f["setup"]:
        bad("B13", f"foreshadow {f['id']} 缺 setup")
    if f["status"] == "unresolved" and not f["payoffNote"]:
        bad("B13", f"foreshadow {f['id']} unresolved 缺 payoffNote")
    if f["status"] == "resolved" and not f["payoff"]:
        bad("B13", f"foreshadow {f['id']} resolved 缺 payoff")
for w in world_out:
    if w["kind"] == "rule" and (w["institution"] not in ("declared", "executed", "misunderstood")
                                or not w["explain"].strip()):
        bad("B13", f"worldSetting {w['id']} rule 字段不全")
    if w["kind"] == "place" and w["placeState"] not in ("arrived", "mentioned"):
        bad("B13", f"worldSetting {w['id']} placeState 非法")
    if w["kind"] == "item":
        if any(x not in ("hold", "transfer", "use", "lose") for x in w["itemStates"]):
            bad("B13", f"worldSetting {w['id']} itemStates 非法")
        for x in w["itemStates"]:
            if not w["stateEvidence"].get(x):
                bad("B13", f"worldSetting {w['id']} 状态 {x} 无 stateEvidence")
        for x in w["stateEvidence"]:
            if x not in w["itemStates"]:
                bad("B13", f"worldSetting {w['id']} stateEvidence 有未登记态 {x}")
if len(themes_out) > 2:
    bad("B13", f"themeReadings {len(themes_out)} 条 > 2")
for th in themes_out:
    for f in ("perspective", "support", "counter"):
        if not th.get(f):
            bad("B13", f"theme {th['id']} 缺 {f}")
if len(sc_out) != 3:
    bad("B13", f"selfCritique {len(sc_out)} 条 != 3")
for x in sc_out:
    for f in ("where", "risk", "why_still"):
        if not x.get(f):
            bad("B13", f"selfCritique 缺 {f}")
if (cand["semanticReview"] or {}).get("status") == "performed":
    bad("B13", "semanticReview 声称 performed")

# ── B14 身份词必须在切片内出现（防带入区间外官衔）────────────────────
TOK = ("巡抚", "布政使", "御史", "首辅", "尚书", "侍郎", "金锣", "银锣", "铜锣",
       "太子", "公主", "国师", "监正", "义子", "长公主", "县子")
idb = json.dumps([t.get("actor") for t in tasks_out] + [s.get("who") for s in states_out],
                 ensure_ascii=False)
for tok in TOK:
    if tok in idb and SLICE.count(tok) == 0:
        bad("B14", f"人物身份字段用了切片内零次出现的词 {tok!r}")

# ── 输出 ────────────────────────────────────────────────────────────────
print(f"切片 codepoint = {len(SLICE)}，UTF-8 sha256 = {slice_sha}")
print(f"引文实例 = {n_inst}，不同引文串 = {len(distinct)}")
print(f"跨分区复用 = {len(reuse)} 条；人物话语引文 = {speech_spans} 条")
print(f"覆盖率 = {len(touched)}/{len(paras)} 非空段落")
if problems:
    print(f"\n构建失败：{len(problems)} 个问题")
    for p in problems:
        print("  ✗", p)
    sys.exit(1)

OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"\n已写出 {OUT.relative_to(ROOT)}")
print(f"sha256 = {sha256_bytes(OUT.read_bytes())}")
