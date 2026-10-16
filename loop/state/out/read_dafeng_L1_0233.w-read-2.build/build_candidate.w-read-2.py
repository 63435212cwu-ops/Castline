#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L1:0233 构建脚本。

职责：把 content_core.py 里的**引文字符串**解析成 docs[0].text 全文 codepoint 偏移，
跑完全部硬判据，通过才写盘。

设计要点（与相邻单元的 builder 同源，但判据按本单元的提示词增补）：
· content_core 里不出现任何手写偏移；偏移一律由本脚本在切片内 find 后 +916516 换算。
· find 不到 / 切片内不唯一 / 越界 / 全文偏移取回不一致 / 引文串在全部引文里重复出现于
  同一条任务的两个栏位 ⇒ 直接 exit 1 且**不写盘**。
· 判据不满足时的行为是「不产出」，不是「产出一个带瑕疵的版本」。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]          # loop/state/out/<build>/ → 仓库根
sys.path.insert(0, str(HERE))

import content_core as C  # noqa: E402

DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
GRAPH = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"
OUT = ROOT / "loop/state/out/read_dafeng_L1_0233.candidate.json"

TASK_ID = "read:dafeng:L1:0233"
AGENT = "w-read-2"
EXPECTED_SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第四章 请陛下赐死"
S, E = 916516, 923035

VALID_BASIS = {"explicit", "inferred", "derived", "unverified"}
VALID_INSTITUTION = {"declared", "executed", "misunderstood"}
VALID_PLACE = {"arrived", "mentioned"}
VALID_ITEM = {"hold", "transfer", "use", "lose"}
FIVE = ("objective", "obstacle", "action", "result", "cost")
ITEM_VERBS = ("匿", "不见了", "获得", "献与", "夺")

problems: list[str] = []
def bad(msg: str) -> None:
    problems.append(msg)


def load() -> tuple[str, str]:
    raw = DOCS.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != EXPECTED_SOURCE_HASH:
        bad(f"docs.json sha256 不符：{got} != {EXPECTED_SOURCE_HASH}")
    doc = json.loads(raw.decode("utf-8"))
    text = doc[0]["text"]
    if text[S:E][: len(UNIT_HEAD)] != UNIT_HEAD:
        bad(f"切片未以单元标题开头：{text[S:S+20]!r}")
    if E - S != 6519:
        bad(f"切片长度不是 6519：{E-S}")
    return text, got


TEXT, SOURCE_HASH = load()
SLICE = TEXT[S:E]


def locate(q: str, where: str) -> dict:
    """把一个引文串换算成带 start/end/sourceHash 的引用对象。"""
    if not isinstance(q, str) or not q:
        bad(f"{where}: 引文串为空或非字符串")
        return {}
    n = SLICE.count(q)
    if n == 0:
        bad(f"{where}: 引文在切片内找不到：{q[:40]!r}")
        return {}
    if n > 1:
        bad(f"{where}: 引文在切片内不唯一（{n} 次）：{q[:40]!r}")
        return {}
    i = SLICE.index(q)
    start, end = S + i, S + i + len(q)
    if not (S <= start < end <= E):
        bad(f"{where}: 引文越界 [{start},{end})")
        return {}
    if TEXT[start:end] != q:
        bad(f"{where}: 全文偏移取回不一致 {q[:40]!r}")
        return {}
    return {"quote": q, "start": start, "end": end, "sourceHash": SOURCE_HASH}


def resolve(node, where: str):
    """递归把 {"q": ...} 换成引用对象；返回 (新节点, 本子树引文串列表)。"""
    if isinstance(node, dict):
        if set(node.keys()) == {"q"}:
            obj = locate(node["q"], where)
            return obj, ([node["q"]] if obj else [])
        out, qs = {}, []
        for k, v in node.items():
            out[k], sub = resolve(v, f"{where}.{k}")
            qs += sub
        return out, qs
    if isinstance(node, list):
        out, qs = [], []
        for i, v in enumerate(node):
            r, sub = resolve(v, f"{where}[{i}]")
            out.append(r)
            qs += sub
        return out, qs
    return node, []


def scan_own_text(node, where: str, hits: list) -> None:
    """我自己的分析文字里不许出现用于标记逐字原文的符号。"""
    if isinstance(node, dict):
        for k, v in node.items():
            scan_own_text(v, f"{where}.{k}", hits)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            scan_own_text(v, f"{where}[{i}]", hits)
    elif isinstance(node, str):
        for tok in ("「", "」"):
            if tok in node:
                hits.append(f"{where}: 自撰文字里出现 {tok}：{node[:40]!r}")


# ── 解析各分区 ───────────────────────────────────────────────────────────────
tasks, tq = resolve(C.TASKS, "tasks")
edges, eq = resolve(C.CAUSE_EDGES, "causeEdges")
rej, rq = resolve(C.REJECTED_EDGES, "rejectedEdges")
states, sq = resolve(C.STATES, "states")
fores, fq = resolve(C.FORESHADOWS, "foreshadows")
world, wq = resolve(C.WORLD_SETTINGS, "worldSettings")

# ── 判据 #10a：worldSettings 的引文必须**条目级**可定位 ─────────────────────
# 相邻单元的独立审计抓出过这一形态：引文只藏在嵌套结构里、条目本身没有
# quote/start/end，复核者无法直接核验。这里把解析好的引文提升到条目级。
for w in world:
    node = w.pop("q", None)
    if isinstance(node, str):                 # content_core 里写成裸串，这里换算
        node = locate(node, f"{w.get('id')}.q")
    if not isinstance(node, dict) or "start" not in node:
        bad(f"{w.get('id')}: worldSettings 条目缺条目级引文（quote/start/end）")
        continue
    w["quote"] = node["quote"]
    w["start"] = node["start"]
    w["end"] = node["end"]
    w["sourceHash"] = node["sourceHash"]
    # 裸串没被 resolve 收进 wq，这里补上，否则覆盖率／复用披露会漏掉它们。
    if node["quote"] not in wq:
        wq.append(node["quote"])
excl, xq = resolve(C.EXCLUDED_SETTINGS, "excludedSettings")
theme, hq = resolve(C.THEME_READINGS, "themeReadings")
selfc, cq = resolve(C.SELF_CRITIQUE, "selfCritique")

# ── 判据 #2：自撰文字不得伪装成引文 ────────────────────────────────────────
own_hits: list[str] = []
for name in ("TASKS", "TASKS_NOTE", "CAUSE_EDGES", "CAUSE_EDGES_NOTE", "REJECTED_EDGES",
             "REJECTED_EDGES_NOTE", "STATES", "STATES_NOTE", "FORESHADOWS", "FORESHADOWS_NOTE",
             "NOT_FORESHADOWS", "WORLD_SETTINGS", "WORLD_SETTINGS_NOTE", "EXCLUDED_SETTINGS",
             "EXCLUDED_SETTINGS_NOTE", "THEME_READINGS", "THEME_READINGS_NOTE",
             "UNKNOWNS", "UNKNOWNS_NOTE", "SELF_CRITIQUE", "SELF_CRITIQUE_NOTE"):
    obj, _ = resolve(getattr(C, name), name)
    scan_own_text(obj, name, own_hits)
for h in own_hits:
    bad(h)

# ── 判据 #3：basis 取值合法 ─────────────────────────────────────────────────
def check_basis(node, where: str) -> None:
    if isinstance(node, dict):
        if "basis" in node and node["basis"] not in VALID_BASIS:
            bad(f"{where}: basis 非法 {node.get('basis')!r}")
        for k, v in node.items():
            check_basis(v, f"{where}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            check_basis(v, f"{where}[{i}]")

check_basis(tasks, "tasks")
check_basis(edges, "causeEdges")
check_basis(states, "states")
check_basis(fores, "foreshadows")
check_basis(world, "worldSettings")
check_basis(theme, "themeReadings")

# ── 判据 #4/#5：任务五元组 —— 每栏各自有依据、同一任务不得两栏共用一句 ──────
for t in tasks:
    tid = t.get("id", "?")
    if t.get("cost") is None and not t.get("costNote"):
        bad(f"{tid}: cost 为 null 但没有 costNote")
    per_field: dict[str, list[str]] = {}
    for f in FIVE:
        v = t.get(f)
        if v is None:
            if not t.get(f + "Note"):
                bad(f"{tid}.{f}: 裸 null 没有 {f}Note")
            continue
        if not isinstance(v, dict):
            bad(f"{tid}.{f}: 栏位结构不是对象")
            continue
        if v.get("basis") not in VALID_BASIS:
            bad(f"{tid}.{f}: 栏位缺合法 basis")
        qs = [x.get("quote") for x in (v.get("quotes") or [])]
        if not qs or any(not q for q in qs):
            bad(f"{tid}.{f}: 栏位没有可用引文")
        if t.get(f + "Note") and f != "cost":
            pass
        per_field[f] = qs
    seen: dict[str, str] = {}
    for f, qs in per_field.items():
        for q in qs:
            if q in seen:
                bad(f"{tid}: 栏位 {seen[q]} 与 {f} 共用同一句原文：{q[:34]!r}")
            seen[q] = f
    # 栏位 basis 与内容一致性的抽查：null 栏位不得同时给出依据
    for f in FIVE:
        if t.get(f) is None and (t.get(f + "Note") or "").strip() == "":
            bad(f"{tid}.{f}: null 栏位的 Note 为空")

# ── 判据 #6：cost 不得是待核/禁令/威胁 ──────────────────────────────────────
BANNED_COST = ("待验证", "待核", "法律规定", "禁令", "严惩不贷是威胁")
for t in tasks:
    cn = t.get("costNote") or ""
    for b in BANNED_COST:
        if b in cn and "不是" not in cn and "不是已执行" not in cn:
            bad(f"{t.get('id')}: costNote 含被禁口径 {b!r} 且未显式排除")

# ── 判据 #7：causeEdges 必须有方向与机制 ────────────────────────────────────
for e in edges:
    if not e.get("from") or not e.get("to"):
        bad(f"{e.get('id')}: causeEdge 缺 from/to")
    if not (e.get("mechanism") or "").strip():
        bad(f"{e.get('id')}: causeEdge 缺 mechanism（禁止以时间相邻连边）")
    if not (e.get("quotes") or []):
        bad(f"{e.get('id')}: causeEdge 没有引文")

# ── 判据 #8：states 前值/后值/锚点 ──────────────────────────────────────────
for s in states:
    if s.get("kind") == "change":
        for f in ("before", "after", "anchor"):
            v = s.get(f)
            if not isinstance(v, dict) or not v.get("quotes") or not v.get("text"):
                bad(f"{s.get('id')}: change 缺 {f}（前值/后值/锚点）")
    elif s.get("kind") == "knowledge_gap":
        if "knownBy" not in s or "notKnownBy" not in s:
            bad(f"{s.get('id')}: knowledge_gap 缺 knownBy/notKnownBy")
        if not isinstance(s.get("knownBy"), list) or not isinstance(s.get("notKnownBy"), list):
            bad(f"{s.get('id')}: knownBy/notKnownBy 必须是数组（可为有依据的空数组）")
        if not s.get("evidence"):
            bad(f"{s.get('id')}: knowledge_gap 缺 evidence")
    else:
        bad(f"{s.get('id')}: states.kind 非法 {s.get('kind')!r}")

# ── 判据 #9：foreshadows 铺设/回收 ──────────────────────────────────────────
for f in fores:
    if f.get("status") not in ("resolved", "unresolved"):
        bad(f"{f.get('id')}: status 非法 {f.get('status')!r}")
    if not f.get("setup"):
        bad(f"{f.get('id')}: 缺 setup（没有铺设不算伏笔）")
    if f.get("status") == "unresolved" and not f.get("payoffNote"):
        bad(f"{f.get('id')}: unresolved 但没有 payoffNote")
    if f.get("status") == "resolved" and not f.get("payoff"):
        bad(f"{f.get('id')}: resolved 但没有 payoff")

# ── 判据 #10：worldSettings 三态字段 ────────────────────────────────────────
for w in world:
    k = w.get("kind")
    if k == "place":
        if w.get("placeState") not in VALID_PLACE:
            bad(f"{w.get('id')}: place 缺合法 placeState")
        for f in ("institution", "itemStates"):
            if f in w:
                bad(f"{w.get('id')}: place 不该带 {f}")
        # arrived 必须有到达/驻守动作作依据，不能只靠标题或方位词。
        if w.get("placeState") == "arrived" and not w.get("arrivalEvidence"):
            bad(f"{w.get('id')}: placeState=arrived 但没有 arrivalEvidence（到达动作）")
        if w.get("placeState") == "mentioned" and w.get("arrivalEvidence"):
            bad(f"{w.get('id')}: placeState=mentioned 却带 arrivalEvidence")
    elif k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(x not in VALID_ITEM for x in st):
            bad(f"{w.get('id')}: item 的 itemStates 非法 {st!r}")
        if "placeState" in w or "institution" in w:
            bad(f"{w.get('id')}: item 不该带 placeState/institution")
        if not w.get("stateEvidence"):
            bad(f"{w.get('id')}: item 缺 stateEvidence（四态分开写的依据）")
        for x in (st or []):
            if x not in (w.get("stateEvidence") or {}):
                bad(f"{w.get('id')}: itemStates 里的 {x} 没有对应 stateEvidence")
    elif k == "rule":
        if w.get("institution") not in VALID_INSTITUTION:
            bad(f"{w.get('id')}: rule 缺合法 institution")
        if not (w.get("explain") or "").strip():
            bad(f"{w.get('id')}: rule 缺 explain")
        if "placeState" in w or "itemStates" in w:
            bad(f"{w.get('id')}: rule 不该带 placeState/itemStates")
    else:
        bad(f"{w.get('id')}: worldSettings.kind 非法 {k!r}")

# ── 判据 #11：themeReadings 三件齐全 ────────────────────────────────────────
if len(theme) > 2:
    bad(f"themeReadings 超过 2 条：{len(theme)}")
for th in theme:
    for f in ("perspective", "support", "counter"):
        if not th.get(f):
            bad(f"{th.get('id')}: themeReading 缺 {f}")
    blob = json.dumps(th, ensure_ascii=False)
    for banned in ("事件密度", "剧情点", "死亡人数", "篇幅中点", "三幕", "英雄旅程"):
        if banned in blob and "不使用" not in blob and "没有" not in blob and "不要" not in blob:
            bad(f"{th.get('id')}: themeReading 使用了被禁的高潮定义 {banned!r}")

# ── 判据 #12：unknowns / selfCritique 结构 ──────────────────────────────────
unknowns, uq = resolve(C.UNKNOWNS, "unknowns")
for u in unknowns:
    if not u.get("text") or not u.get("why"):
        bad(f"{u.get('id')}: unknown 缺 text/why")
if len(selfc) != 3:
    bad(f"selfCritique 应为 3 条，实为 {len(selfc)}")
for sc in selfc:
    for f in ("where", "risk", "why_still"):
        if not sc.get(f):
            bad(f"selfCritique 缺 {f}")

# ── 判据 #13：覆盖率（反向清单）──────────────────────────────────────────────
paras = []
off = S
for p in SLICE.split("\n"):
    if p.strip():
        paras.append({"start": off, "end": off + len(p), "text": p})
    off += len(p) + 1

all_quotes = sorted({q for q in (tq + eq + rq + sq + fq + wq + xq + hq + cq + uq) if q})
covered = set()
for p in paras:
    for q in all_quotes:
        if q in p["text"]:
            covered.add(p["start"])
zero = [p for p in paras if p["start"] not in covered]

# ── 判据 #14：跨分区复用如实披露 ────────────────────────────────────────────
reuse: dict[str, list[str]] = {}
for sec, qs in (("tasks", tq), ("causeEdges", eq), ("rejectedEdges", rq), ("states", sq),
                ("foreshadows", fq), ("worldSettings", wq), ("excludedSettings", xq),
                ("themeReadings", hq), ("selfCritique", cq), ("unknowns", uq)):
    for q in set(qs):
        reuse.setdefault(q, [])
        if sec not in reuse[q]:
            reuse[q].append(sec)
cross = [{"quote": q, "start": locate(q, "reuse")["start"], "end": locate(q, "reuse")["end"],
          "sourceHash": SOURCE_HASH, "sections": sorted(s)}
         for q, s in sorted(reuse.items()) if len(s) > 1]

# ── 判据 #15：构建期自检不通过就不写盘 ──────────────────────────────────────
if problems:
    print("构建失败，未写盘。问题如下：", file=sys.stderr)
    for p in problems:
        print("  - " + p, file=sys.stderr)
    sys.exit(1)

slice_sha = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

# ── 判据 #16：话语层披露**由数据生成**，不是手写 ────────────────────────────
# 本区间是对话密集章（31 段顶层对白）。凡引文落在 “ ” 区间内的，只用于证明
# 「谁说了什么」；凡涉及世界事实的结论都必须另有叙述句支撑。这里机械地把
# 落在话语层内的引文逐条列出来，让复核者能直接检查有没有把话当事实。
speech_spans: list[tuple[int, int]] = []
_depth = 0
_cur = None
for _i, _ch in enumerate(SLICE):
    if _ch == "\u201c":
        _depth += 1
        if _depth == 1:
            _cur = _i
    elif _ch == "\u201d" and _depth > 0:
        _depth -= 1
        if _depth == 0 and _cur is not None:
            speech_spans.append((_cur, _i + 1))
            _cur = None

def in_speech(q: str) -> bool:
    i = SLICE.find(q)
    if i < 0:
        return False
    a, b = i, i + len(q)
    return any(a < y and x < b for x, y in speech_spans)

_sec_quotes = (("tasks", tq), ("causeEdges", eq), ("states", sq), ("foreshadows", fq),
               ("worldSettings", wq), ("themeReadings", hq), ("selfCritique", cq))
_speech_disp = []
for q in all_quotes:
    if not in_speech(q):
        continue
    secs = sorted({s for s, qs in _sec_quotes if q in qs})
    _speech_disp.append({
        "quote": q, "start": locate(q, "speech")["start"], "end": locate(q, "speech")["end"],
        "sourceHash": SOURCE_HASH, "sections": secs,
        "usedFor": "只证明这句话被说出（或被告知），不作为『事情就是如此』的事实依据；"
                   "凡由它引出的世界事实结论，均另引叙述句。",
    })
_speech_disp.sort(key=lambda x: x["start"])

candidate = {
    "task": TASK_ID,
    "agent": AGENT,
    "role": "READER",
    "book": "dafeng",
    "lane": 1,
    "unitIndex": 233,
    "unitHead": UNIT_HEAD,
    "sourceRange": [S, E],
    "sourceHash": SOURCE_HASH,
    "sliceCodepoints": E - S,
    "sliceSha256": slice_sha,
    "readSource": f"data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[{S}:{E})",

    "tasks": tasks,
    "tasksNote": C.TASKS_NOTE,
    "causeEdges": edges,
    "causeEdgesNote": C.CAUSE_EDGES_NOTE,
    "rejectedEdges": rej,
    "rejectedEdgesNote": C.REJECTED_EDGES_NOTE,
    "states": states,
    "statesNote": C.STATES_NOTE,
    "foreshadows": fores,
    "foreshadowsNote": C.FORESHADOWS_NOTE,
    "notForeshadows": resolve(C.NOT_FORESHADOWS, "notForeshadows")[0],
    "worldSettings": world,
    "worldSettingsNote": C.WORLD_SETTINGS_NOTE,
    "excludedSettings": excl,
    "excludedSettingsNote": C.EXCLUDED_SETTINGS_NOTE,
    "themeReadings": theme,
    "themeReadingsNote": C.THEME_READINGS_NOTE,
    "unknowns": unknowns,
    "unknownsNote": C.UNKNOWNS_NOTE,
    "selfCritique": selfc,
    "selfCritiqueNote": C.SELF_CRITIQUE_NOTE,

    "semanticReview": {
        "status": "not_performed",
        "note": "本候选只做了引用定位与逐字核验（构建脚本 + 独立审计脚本，命令与哈希见提交记录），"
                "没有做语义评审。每条结论是否成立，必须由 read-verify 通道的独立复核者对着原文判断。"
                "『引文定位正确』不等于『语义已核验』。",
    },
    "citationConvention": {
        "verbatim": "所有逐字引文都放在各自条目下的 quotes / quote / setup / payoff / stateEvidence 数组里。",
        "ownWords": "分析文字里用『』包住的片段一律是**我的用语**（不是原文）；"
                    "原文一律放在 quote 字段里。构建脚本会断言我的分析文字里不出现 「 」 这两个符号。",
        "metaNote": "“ ” 在本文件里只出现在原文引文字符串内部（原文本身的对白引号），"
                    "不用于标记我自己的话。",
    },
    "offsetCaliber": "所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；"
                     "自检式：text[start:end] == quote 逐字成立。",
    "sourceHashScope": f"所有引用的 sourceHash 均为整个 docs.json 文件的 sha256（{SOURCE_HASH}，构建时实测复算一致）。",
    "sliceSha256Scope": "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。",
    "coverage": {
        "nonEmptyParagraphs": len(paras),
        "paragraphsTouchedByQuotes": len(paras) - len(zero),
        "zeroCoverageParagraphs": len(zero),
        "zeroCoverageList": [{"start": p["start"], "end": p["end"], "text": p["text"]} for p in zero[:40]],
        "zeroCoverageListTruncated": len(zero) > 40,
        "zeroCoverageNote": "零覆盖段落大多是过场句、礼仪过程、内心吐槽与作者按语。"
                            "我把它们列出来，是为了让复核者能**反向**检查我漏了什么，"
                            "而不是只呈现已写的部分（清单超过 40 条时截断并标注）。",
    },
    "graphCacheNotUsedAsEvidence": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.json",
        "note": "图谱缓存只用于对照已有结论（本区间内它共有 4 条 events 与 1 条 character 命中），"
                "本候选没有任何一条断言以它的摘要为依据。",
    },
    "buildDisclosure": {
        "builder": "loop/state/out/read_dafeng_L1_0233.w-read-2.build/build_candidate.w-read-2.py",
        "contentCore": "loop/state/out/read_dafeng_L1_0233.w-read-2.build/content_core.py",
        "howOffsetsWereMade": "content_core.py 里不出现任何手写偏移：每条引文只给字符串，"
                              "偏移由构建脚本在切片内 find 后 +916516 换算；"
                              "find 不到、切片内不唯一、越界、或全文偏移取回不一致 ⇒ 直接 exit 1 且不写盘。",
    },
    "speechLayerDisclosure": {
        "policy": "带 “” 的引文 = 人物话语（或叙述对其话语的转述）。它们只用于证明『谁说了什么』，"
                  "不作为『事情就是如此』的事实依据；凡涉及世界事实的结论，我都另找了叙述句作依据。",
        "speechSpans": len(speech_spans),
        "checkedCount": len(_speech_disp),
        "dispositionOfEach": _speech_disp,
        "note": "本区间对白密集（顶层 “ ” 区间 31 段）。清单由构建脚本从数据生成："
                "凡引文区间与某个对白区间相交即列入，逐条给出它被用在哪些分区。"
                "最容易把话当事实的两处我已在正文另行处理："
                "福妃案情全部来自魏渊的转述、另有隐情是皇帝的定性（见 k3 与 u7）；"
                "太子凌辱后妃是许七安的疑问句，不是叙述事实。",
    },
    "crossSectionQuoteReuse": cross,
    "crossSectionQuoteReuseNote": "跨分区复用如实披露：同一句原文出现在两个以上分区时逐条列出"
                                  f"（{len(cross)} 条，**由构建脚本从数据生成**，不是手写计数）。"
                                  "判据是同一任务内五栏不得共用一句；跨分区复用说明同一句被用于不同用途，"
                                  "这类复用我没有隐藏，请复核者判断是否恰当。",
}

OUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

# 计数**从写盘后的产物本身**重算，不用中间变量 —— 中间变量会把裸串 q 与
# 已被 resolve 的嵌套引用各算一次，报出比产物实际更大的数字（本轮实测踩过）。
#
# 计数口径（与 audit_candidate.py 完全一致，两脚本必须报同一个数）：
#   「引文定位点」= 产物里**任何**带 quote/start/end 的对象，包括条目级引文与
#   它下面用于分开四态的嵌套依据（arrivalEvidence / stateEvidence）。
#   这些都是独立可核验的定位点，所以都要算；不采用「遇到父节点就跳过子节点」的
#   早退口径，那会让两个脚本报出 140 与 150 两个数而无法对账。
_final = json.loads(OUT.read_bytes().decode("utf-8"))

def _count(node) -> int:
    n = 0
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node:
            n += 1
        for v in node.values():
            n += _count(v)
    elif isinstance(node, list):
        for v in node:
            n += _count(v)
    return n

_core_secs = ("tasks", "causeEdges", "rejectedEdges", "states", "foreshadows",
              "notForeshadows", "worldSettings", "excludedSettings", "themeReadings",
              "unknowns", "selfCritique")
_core = sum(_count(_final[s]) for s in _core_secs)
_speech = _count(_final["speechLayerDisclosure"])
_cross = _count(_final["crossSectionQuoteReuse"])
_distinct = set()

def _collect(node) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node:
            _distinct.add(node["quote"])
        for v in node.values():
            _collect(v)
    elif isinstance(node, list):
        for v in node:
            _collect(v)

for _s in _core_secs:
    _collect(_final[_s])

print(f"已写盘：{OUT}")
print(f"内容分区引用实例 {_core} 条 / 不同串 {len(_distinct)} 个")
print(f"话语层披露 {_speech} 条、跨分区复用披露 {_cross} 条（披露层不计入内容分区计数）")
print(f"覆盖率 {len(paras)-len(zero)}/{len(paras)} 个非空段落；零覆盖 {len(zero)}")
print(f"candidate sha256 = {hashlib.sha256(OUT.read_bytes()).hexdigest()}")
