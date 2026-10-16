#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计**本轮产物** loop/state/out/read_dafeng_L1_0237.candidate.json。

与生成侧的关系：本脚本**不 import** content_core / 构建脚本，判据全部从
docs.json 原文与产物本身重算。凡生成侧自称的东西（计数、覆盖率、复用披露、
四态统计）一律重算后对账；对不上即报错。

判据（C1–C23）：
  C1  docs.json sha256 == 任务 sourceHash
  C2  切片以单元标题开头、长度 5441
  C3  产物 sourceRange / sourceHash / sliceSha256 / sliceCodepoints / task / agent 自述正确
  C4  每条引文 text[start:end]==quote（逐字）
  C5  每条引文落在 [943450,948891) 内
  C6  每条引文在切片内唯一
  C7  每条引文 sourceHash == 整文件 sha256
  C8  同一任务五栏不得共用同一句
  C9  null 栏位必须有同名 Note 且非空
  C10 有值栏位必须有引文与合法 basis
  C11 basis 取值合法（全树）
  C12 causeEdges 每条有 from/to/mechanism/quotes；与 from/to 非空且机制非空
  C13 states.change 有 before/after/anchor；knowledge_gap 有 knownBy/notKnownBy/evidence
  C14 foreshadows: setup 非空；unresolved 有 payoffNote；resolved 有 payoff
  C15 worldSettings 三态字段（rule=institution+explain；place=placeState；
      item=itemStates+stateEvidence，且 itemStates 每态都有依据、stateEvidence 无未登记态）
  C16 themeReadings ≤2，每条 perspective/support/counter 齐全
  C17 selfCritique == 3 条，每条 where/risk/why_still
  C18 semanticReview 不得声称完成
  C19 顶层分区齐全
  C20 **顺序判据**：机制声称的先后与引文偏移一致；tasks action 不晚于 result；
      states 锚点在 before→after 内；foreshadows setup 早于 payoff
  C21 人物身份字段（actor/who）里的身份词必须在切片内出现（防带入区间外官衔）
  C22 产物自报的计数/覆盖率与重算一致（防自述注水）
  C23 **分析文字层判据**：我的分析文字里不得出现原文用的引号（U+201C/U+201D/U+300C/U+300D）；
      带弯引号的引文必须逐条出现在 speechLayerDisclosure 里

用法：python3 -B -s loop/state/out/read_dafeng_L1_0237.w-read-2.build/audit_candidate.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0237.candidate.json"
START, END = 943450, 948891
EXPECT = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第八章 案发现场"

problems: list[str] = []
checks: list[str] = []


def ok(tag, msg):
    checks.append(f"  ✓ {tag} {msg}")


def bad(tag, msg):
    problems.append(f"[{tag}] {msg}")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    return sha256_bytes(Path(p).read_bytes())


# ── C1/C2 原文 ──────────────────────────────────────────────────────────
raw = DOCS.read_bytes()
src = sha256_bytes(raw)
if src != EXPECT:
    bad("C1", f"docs.json sha256 {src} != {EXPECT}")
else:
    ok("C1", f"docs.json sha256 一致 {src[:12]}…")

text = json.loads(raw.decode("utf-8"))[0]["text"]
sl = text[START:END]
if sl[: len(UNIT_HEAD)] != UNIT_HEAD:
    bad("C2", f"切片未以单元标题开头：{sl[:20]!r}")
elif len(sl) != 5441:
    bad("C2", f"切片长度 {len(sl)} != 5441")
else:
    ok("C2", f"切片以标题开头、长度 {len(sl)}")

cand = json.loads(CAND.read_bytes())
slice_sha = sha256_bytes(sl.encode("utf-8"))

# ── C3 自述 ─────────────────────────────────────────────────────────────
if cand.get("sourceRange") != [START, END]:
    bad("C3", f"sourceRange 自述 {cand.get('sourceRange')}")
if cand.get("sourceHash") != EXPECT:
    bad("C3", "sourceHash 自述不符")
if cand.get("sliceSha256") != slice_sha:
    bad("C3", f"sliceSha256 自述 {cand.get('sliceSha256')} != 实算 {slice_sha}")
if cand.get("sliceCodepoints") != len(sl):
    bad("C3", "sliceCodepoints 自述不符")
if cand.get("task") != "read:dafeng:L1:0237":
    bad("C3", f"task 自述 {cand.get('task')}")
if cand.get("agent") != "w-read-2":
    bad("C3", f"agent 自述 {cand.get('agent')}")
if cand.get("unitHead") != UNIT_HEAD:
    bad("C3", f"unitHead 自述 {cand.get('unitHead')}")
if not any(p.startswith("[C3]") for p in problems):
    ok("C3", "产物自述字段与重算一致（含 sliceSha256）")


# ── 引文遍历 ────────────────────────────────────────────────────────────
def walk(node, path="$"):
    """全深度遍历：**不早退**。

    父节点同时带条目级 quote 与用于分开各态的 stateEvidence / arrivalEvidence，
    父节点一旦 return，嵌套依据就整片漏掉。计数口径 = 任何带 quote/start/end
    的对象都是一个定位点。
    """
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
            yield path, node
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


SECS = ("tasks", "causeEdges", "rejectedEdges", "states", "foreshadows",
        "notForeshadows", "worldSettings", "excludedSettings", "themeReadings",
        "unknowns", "selfCritique")

n_inst = 0
distinct = set()
for sec in SECS:
    for p, q in walk(cand.get(sec), sec):
        n_inst += 1
        distinct.add(q["quote"])
        qq, s, e = q["quote"], q["start"], q["end"]
        if not isinstance(s, int) or not isinstance(e, int):
            bad("C4", f"{p} 偏移非整数")
            continue
        if text[s:e] != qq:
            bad("C4", f"{p} 逐字不符 text[{s}:{e}]={text[s:e][:40]!r} != {qq[:40]!r}")
        if not (START <= s and e <= END):
            bad("C5", f"{p} 越界 [{s},{e})")
        if sl.count(qq) == 0:
            bad("C6", f"{p} 引文不在切片内")
        elif sl.count(qq) > 1:
            bad("C6", f"{p} 引文切片内不唯一（{sl.count(qq)} 次）")
        if q.get("sourceHash") != EXPECT:
            bad("C7", f"{p} sourceHash 不符")
if not any(p.startswith(("[C4]", "[C5]", "[C6]", "[C7]")) for p in problems):
    ok("C4", f"{n_inst} 条引文实例逐字成立")
    ok("C5", "全部落在区间内")
    ok("C6", "全部切片内唯一")
    ok("C7", "全部 sourceHash 正确")

# ── C8 五栏共用 ─────────────────────────────────────────────────────────
FIVE = ("objective", "obstacle", "action", "result", "cost")
for t in cand.get("tasks", []):
    seen = {}
    for f in FIVE:
        v = t.get(f)
        if isinstance(v, dict):
            for q in v.get("quotes") or []:
                if q["quote"] in seen:
                    bad("C8", f"{t.get('id')}: {seen[q['quote']]} 与 {f} 共用 {q['quote'][:30]!r}")
                seen[q["quote"]] = f
    for f in FIVE:
        if f not in t:
            bad("C9", f"{t.get('id')} 缺栏位 {f}")
        elif t[f] is None and not (t.get(f + "Note") or "").strip():
            bad("C9", f"{t.get('id')}.{f} 裸 null 无 Note")
        elif isinstance(t[f], dict):
            if not (t[f].get("quotes") or []):
                bad("C10", f"{t.get('id')}.{f} 有结论无引文")
            if t[f].get("basis") not in {"explicit", "inferred", "derived", "unverified"}:
                bad("C10", f"{t.get('id')}.{f} basis 非法 {t[f].get('basis')!r}")
if not any(p.startswith(("[C8]", "[C9]", "[C10]")) for p in problems):
    ok("C8", f"{len(cand.get('tasks', []))} 条任务五栏无共用引文")
    ok("C9", "null 栏位全部带 Note")
    ok("C10", "有值栏位全部带引文与合法 basis")

# ── C11 basis 全树 ──────────────────────────────────────────────────────
VALID = {"explicit", "inferred", "derived", "unverified"}


def chk_basis(node, path):
    if isinstance(node, dict):
        if "basis" in node and node["basis"] not in VALID:
            bad("C11", f"{path} basis 非法 {node['basis']!r}")
        for k, v in node.items():
            chk_basis(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            chk_basis(v, f"{path}[{i}]")


chk_basis(cand, "$")
if not any(p.startswith("[C11]") for p in problems):
    ok("C11", "全树 basis 取值合法")

# ── C12 causeEdges ──────────────────────────────────────────────────────
for e in cand.get("causeEdges", []):
    if not e.get("from") or not e.get("to"):
        bad("C12", f"{e.get('id')} 缺 from/to")
    if not (e.get("mechanism") or "").strip():
        bad("C12", f"{e.get('id')} 缺 mechanism")
    if not (e.get("quotes") or []):
        bad("C12", f"{e.get('id')} 无引文")
if not any(p.startswith("[C12]") for p in problems):
    ok("C12", f"{len(cand.get('causeEdges', []))} 条边结构完整")

# ── C13 states ──────────────────────────────────────────────────────────
for s in cand.get("states", []):
    k = s.get("kind")
    if k == "change":
        for f in ("before", "after", "anchor"):
            v = s.get(f)
            if not isinstance(v, dict) or not v.get("quotes") or not v.get("text"):
                bad("C13", f"{s.get('id')} change 缺 {f}")
    elif k == "knowledge_gap":
        if not isinstance(s.get("knownBy"), list) or not isinstance(s.get("notKnownBy"), list):
            bad("C13", f"{s.get('id')} knownBy/notKnownBy 非数组")
        if not s.get("evidence"):
            bad("C13", f"{s.get('id')} knowledge_gap 缺 evidence")
    else:
        bad("C13", f"{s.get('id')} kind 非法 {k!r}")
if not any(p.startswith("[C13]") for p in problems):
    ok("C13", f"{len(cand.get('states', []))} 条状态结构完整")

# ── C14 foreshadows ─────────────────────────────────────────────────────
for f in cand.get("foreshadows", []):
    if not f.get("setup"):
        bad("C14", f"{f.get('id')} 缺 setup")
    if f.get("status") == "unresolved" and not f.get("payoffNote"):
        bad("C14", f"{f.get('id')} unresolved 缺 payoffNote")
    if f.get("status") == "resolved" and not f.get("payoff"):
        bad("C14", f"{f.get('id')} resolved 缺 payoff")
    if f.get("status") not in ("resolved", "unresolved"):
        bad("C14", f"{f.get('id')} status 非法")
if not any(p.startswith("[C14]") for p in problems):
    ok("C14", f"{len(cand.get('foreshadows', []))} 条伏笔结构完整")

# ── C15 worldSettings ───────────────────────────────────────────────────
for w in cand.get("worldSettings", []):
    k = w.get("kind")
    if k == "rule":
        if w.get("institution") not in ("declared", "executed", "misunderstood"):
            bad("C15", f"{w.get('id')} institution 非法 {w.get('institution')!r}")
        if not (w.get("explain") or "").strip():
            bad("C15", f"{w.get('id')} rule 缺 explain")
    elif k == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            bad("C15", f"{w.get('id')} placeState 非法 {w.get('placeState')!r}")
        if "explain" not in w:
            bad("C15", f"{w.get('id')} place 缺 explain")
    elif k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            bad("C15", f"{w.get('id')} itemStates 非法 {st!r}")
        se = w.get("stateEvidence") or {}
        for x in (st or []):
            if x not in se or not se[x]:
                bad("C15", f"{w.get('id')} 状态 {x} 无 stateEvidence")
        for x in se:
            if x not in (st or []):
                bad("C15", f"{w.get('id')} stateEvidence 有未登记态 {x!r}")
    else:
        bad("C15", f"{w.get('id')} kind 非法 {k!r}")
    if not w.get("quote"):
        bad("C15", f"{w.get('id')} 缺条目级引文")
if not any(p.startswith("[C15]") for p in problems):
    _ws = cand.get("worldSettings") or []
    kinds = {}
    for w in _ws:
        kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
    ok("C15", f"{len(_ws)} 条设定三态字段合法 {kinds}")

# ── C16 themeReadings ───────────────────────────────────────────────────
th = cand.get("themeReadings", [])
if len(th) > 2:
    bad("C16", f"themeReadings {len(th)} 条 > 2")
for x in th:
    for f in ("perspective", "support", "counter"):
        if not x.get(f):
            bad("C16", f"{x.get('id')} 缺 {f}")
if not any(p.startswith("[C16]") for p in problems):
    ok("C16", f"{len(th)} 条主题解读三件齐全")

# ── C17 selfCritique ────────────────────────────────────────────────────
sc = cand.get("selfCritique", [])
if len(sc) != 3:
    bad("C17", f"selfCritique {len(sc)} 条 != 3")
for x in sc:
    for f in ("where", "risk", "why_still"):
        if not x.get(f):
            bad("C17", f"selfCritique 缺 {f}")
if not any(p.startswith("[C17]") for p in problems):
    ok("C17", "3 条自我批评结构完整")

# ── C18 semanticReview ──────────────────────────────────────────────────
sr = cand.get("semanticReview") or {}
if sr.get("status") == "performed":
    bad("C18", "semanticReview 声称 performed")
else:
    ok("C18", f"semanticReview 保持 {sr.get('status')!r}（未越权）")

# ── C19 分区齐全 ────────────────────────────────────────────────────────
need = ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
        "themeReadings", "unknowns", "selfCritique")
miss = [k for k in need if k not in cand]
if miss:
    bad("C19", f"缺分区 {miss}")
else:
    ok("C19", "提示词要求的 8 个分区全部存在")

# ── C20 顺序判据 ────────────────────────────────────────────────────────
ORDER_RE = re.compile(r"先[^。；]{0,40}?[，,、]?\s*(?:随后|再|然后|才|紧接着)|紧接着|下一段")


def offs_of(node):
    qs = (node or {}).get("quotes") or []
    return [q["start"] for q in qs]


def span_of(items):
    return [q["start"] for q in (items or [])]


a20 = []
for e in cand.get("causeEdges", []):
    o = offs_of(e)
    declared = "顺序更正" in (e.get("mechanism") or "") or "方向更正" in (e.get("mechanism") or "")
    if ORDER_RE.search(e.get("mechanism", "")) and len(o) >= 2 and o != sorted(o) and not declared:
        a20.append(f"causeEdge {e.get('id')} 机制声称先后但引文非升序 {o}")
    if o != sorted(o):
        a20.append(f"causeEdge {e.get('id')} 引文非升序 {o}（本条未登记顺序更正）")
for t in cand.get("tasks", []):
    ac, r = offs_of(t.get("action")), offs_of(t.get("result"))
    if ac and r and max(ac) > max(r):
        a20.append(f"task {t.get('id')} action@max{max(ac)} 晚于 result@max{max(r)}")
for s in cand.get("states", []):
    if s.get("kind") != "change":
        continue
    b, a, an = offs_of(s.get("before")), offs_of(s.get("after")), offs_of(s.get("anchor"))
    if not (b and a and an):
        continue
    B, A, AN = min(b), max(a), min(an)
    if B > A:
        a20.append(f"state {s.get('id')} before@{B} 晚于 after@{A}")
    if not (B <= AN <= A) and s.get("narrationOrder") != "flashback":
        a20.append(f"state {s.get('id')} 锚点@{AN} 不在 [{B},{A}] 且未登记 flashback")
for f in cand.get("foreshadows", []):
    su, pa = span_of(f.get("setup")), span_of(f.get("payoff"))
    if su and pa and max(su) > min(pa):
        a20.append(f"foreshadow {f.get('id')} setup 晚于 payoff")
if a20:
    for x in a20:
        bad("C20", x)
else:
    ok("C20", "顺序判据全部成立（边引文升序/task 五元组/state 锚点/伏笔铺设回收）")

# ── C21 身份词必须在切片内出现 ──────────────────────────────────────────
TOK = ("巡抚", "布政使", "御史", "首辅", "尚书", "侍郎", "金锣", "银锣", "铜锣",
       "太子", "公主", "国师", "监正", "义子", "长公主", "县子", "娘娘", "宦官",
       "打更人", "侍卫")
idb = json.dumps([t.get("actor") for t in cand.get("tasks", [])] +
                 [s.get("who") for s in cand.get("states", [])], ensure_ascii=False)
a21 = [tok for tok in TOK if tok in idb and sl.count(tok) == 0]
if a21:
    for tok in a21:
        bad("C21", f"人物身份字段用了切片内零次出现的词 {tok!r}")
else:
    ok("C21", "人物身份字段的身份词均在切片内出现")

# ── C22 自述计数对账 ────────────────────────────────────────────────────
cov = cand.get("coverage") or {}
paras, pos = [], START
for line in sl.split("\n"):
    if line.strip():
        paras.append({"start": pos, "end": pos + len(line), "text": line})
    pos += len(line) + 1
if cov.get("nonEmptyParagraphs") != len(paras):
    bad("C22", f"coverage.nonEmptyParagraphs 自述 {cov.get('nonEmptyParagraphs')} != 实算 {len(paras)}")
touched = set()
for sec in SECS:
    for _, q in walk(cand.get(sec), sec):
        for p in paras:
            if q["start"] < p["end"] and p["start"] < q["end"]:
                touched.add(p["start"])
if cov.get("paragraphsTouchedByQuotes") != len(touched):
    bad("C22", f"coverage.paragraphsTouchedByQuotes 自述 {cov.get('paragraphsTouchedByQuotes')} "
               f"!= 实算 {len(touched)}")
if cov.get("zeroCoverageParagraphs") != len(paras) - len(touched):
    bad("C22", f"coverage.zeroCoverageParagraphs 自述 {cov.get('zeroCoverageParagraphs')} "
               f"!= 实算 {len(paras) - len(touched)}")

# 自述里的四态/三态计数与实算对账（从 note 文本里抓数字）
_ws = cand.get("worldSettings") or []
_r = [w for w in _ws if w["kind"] == "rule"]
_p = [w for w in _ws if w["kind"] == "place"]
_i = [w for w in _ws if w["kind"] == "item"]
real = {
    "rule": len(_r), "place": len(_p), "item": len(_i),
    "executed": sum(1 for w in _r if w["institution"] == "executed"),
    "misunderstood": sum(1 for w in _r if w["institution"] == "misunderstood"),
    "declared": sum(1 for w in _r if w["institution"] == "declared"),
    "arrived": sum(1 for w in _p if w["placeState"] == "arrived"),
    "mentioned": sum(1 for w in _p if w["placeState"] == "mentioned"),
    "hold": sum(1 for w in _i if "hold" in w["itemStates"]),
    "transfer": sum(1 for w in _i if "transfer" in w["itemStates"]),
    "use": sum(1 for w in _i if "use" in w["itemStates"]),
    "lose": sum(1 for w in _i if "lose" in w["itemStates"]),
}
note = cand.get("worldSettingsNote") or ""
for key, pat in (("rule", r"(\d+)\s*条规则"), ("place", r"(\d+)\s*条地点"), ("item", r"(\d+)\s*条物件"),
                 ("executed", r"executed\s*(\d+)"), ("misunderstood", r"misunderstood\s*(\d+)"),
                 ("declared", r"declared\s*(\d+)"), ("arrived", r"arrived\s*(\d+)"),
                 ("mentioned", r"mentioned\s*(\d+)"), ("hold", r"hold\s*(\d+)"),
                 ("transfer", r"transfer\s*(\d+)"), ("use", r"use\s*(\d+)"), ("lose", r"lose\s*(\d+)")):
    m = re.search(pat, note)
    if not m:
        bad("C22", f"worldSettingsNote 里找不到 {key} 的自报数字（无法对账）")
    elif int(m.group(1)) != real[key]:
        bad("C22", f"worldSettingsNote 自报 {key}={m.group(1)} != 实算 {real[key]}")

# 跨分区复用披露对账
where = {}
for sec in SECS:
    for _, q in walk(cand.get(sec), sec):
        where.setdefault(q["quote"], set()).add(sec)
real_reuse = sorted(q for q, v in where.items() if len(v) > 1)
disclosed = sorted(x["quote"] for x in (cand.get("crossSectionQuoteReuse") or []))
if real_reuse != disclosed:
    bad("C22", f"跨分区复用披露与实算不符：实算 {len(real_reuse)} 条 / 披露 {len(disclosed)} 条")
m = re.search(r"（(\d+)\s*条", cand.get("crossSectionQuoteReuseNote") or "")
if not m or int(m.group(1)) != len(real_reuse):
    bad("C22", f"crossSectionQuoteReuseNote 自报条数与实算 {len(real_reuse)} 不符")

if not any(p.startswith("[C22]") for p in problems):
    ok("C22", f"覆盖率与设定计数自述全部与重算一致（{len(touched)}/{len(paras)} 非空段落被引文触及；"
              f"复用披露 {len(real_reuse)} 条）")

# ── C23 分析文字层判据 ──────────────────────────────────────────────────
BANNED = ("\u300c", "\u300d", "\u201c", "\u201d")


# 显式豁免：整个子树都是**原文拷贝**而不是我的分析文字。
# coverage.zeroCoverageList[].text 由构建器原样拷贝原文段落（供复核者比对），
# 所以它必然含原文的对白引号 —— 这不是「把自己的话伪装成原文」。
RAW_TEXT_SUBTREES = ("$.coverage.zeroCoverageList",)


def own_words(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("quote", "sourceHash"):
                continue
            yield from own_words(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from own_words(v, f"{path}[{i}]")
    elif isinstance(node, str):
        if any(path.startswith(t) for t in RAW_TEXT_SUBTREES):
            return
        if any(b in node for b in BANNED):
            yield path, node


leaks = list(own_words(cand))
if leaks:
    for p, s in leaks:
        bad("C23", f"{p} 分析文字里出现原文引号符号：{s[:50]!r}")
else:
    ok("C23", "分析文字里没有出现原文引号符号（我的转述与原文可机械区分）")

# 带弯引号的引文必须逐条披露
speech = sorted({q["quote"] for sec in SECS for _, q in walk(cand.get(sec), sec)
                 if "\u201c" in q["quote"] or "\u201d" in q["quote"]})
disp = cand.get("speechLayerDisclosure") or {}
listed = sorted({d["quote"] for d in disp.get("dispositionOfEach") or []})
if speech != listed:
    bad("C23", f"人物话语披露不完整：实算 {len(speech)} 条 / 披露 {len(listed)} 条；"
               f"缺 {[x[:20] for x in speech if x not in listed][:3]}")
if disp.get("speechSpans") != sum(1 for sec in SECS for _, q in walk(cand.get(sec), sec)
                                  if "\u201c" in q["quote"] or "\u201d" in q["quote"]):
    bad("C23", "speechLayerDisclosure.speechSpans 自报与实算不符")
if not any(p.startswith("[C23]") for p in problems):
    ok("C23", f"人物话语披露完整（{len(speech)} 条不同引文）")

# ── 输出 ────────────────────────────────────────────────────────────────
print(f"候选 = {CAND}")
print(f"sha256 = {sha256_file(CAND)}")
print(f"引文实例 = {n_inst}，不同引文串 = {len(distinct)}")
print()
for c in checks:
    print(c)
print()
if problems:
    print(f"审计不通过：{len(problems)} 个问题")
    for p in problems:
        print("  ✗", p)
    sys.exit(1)
print(f"审计通过：C1–C23 全部成立（{n_inst} 条引文实例 / {len(distinct)} 个不同串）")
