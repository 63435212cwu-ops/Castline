#!/usr/bin/env python3
"""P03 核心交付：把 tasks 变成「目标—阻碍—行动—结果—代价」五元组状态机，
并把 storylines 从"按事件数等分"换成"真实章节/卷边界 + 原文证据"的挂接。

计划原话（P03 目标）：
  「把故事线和任务从条目变成可验证的状态机，禁止以时间相邻替代因果」
验收断言原文：
  「动画和卡片显示的目标/障碍/行动/结果/代价都能跳到事件及原文；播放完成不自动标记任务成功。」

本脚本的六条不可谈判规则
────────────────────────────────────────────────────────────────────────
R1 不虚构。字段缺就是缺：原文没有支撑的维度写 basis="unverified"、text 保留源值（可为 ""）、
   sourceRefs=[]。**绝不填默认值、绝不把推导升格为原文。**
R2 四态证据标记：explicit（原文直述）/ inferred（归纳）/ derived（推导）/ unverified（未核验）。
R3 引文必须是原文子串：用 text[start:end] == quote 复核，并把复核结果写进 match 字段。
R4 禁止以时间相邻替代因果：同一条任务里相邻的两个事件，只有在 causeEdges 里有真实边时
   才标 relation="causal-evidence"；否则一律标 relation="sequence-only"，
   并在 reverseEvidence 里记录"仅为时间相邻"的条数。
R5 结束≠成功：终态不得因为"事件序列排完了"就判 resolved。successClaim 只有拿到
   原文中明确的成功措辞才可标 explicit；否则 endNotSuccess=true。
R6 只读 data/，只写 artifacts/plan100/narrative/。

用法：
  python3 tools/plan100/build_task_state_machines.py            # 三书全跑
  python3 tools/plan100/build_task_state_machines.py --book 9b6… # 单本
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT = artifact_path() / "plan100" / "narrative"
SOURCE_INDEX = ROOT / "tests" / "fixtures" / "contracts" / "source-index"

sys.path.insert(0, str(ROOT / "tools" / "plan100"))
from evidence_audit import build_chapter_index

BOOKS = [
    ("9b676d7031b1bcd3b8377a18", "大奉打更人"),
    ("df959d743e53206f56db2f92", "西游记"),
    ("152e2a6eed94f1075e7e7070", "三国演义"),
]

ASPECTS = ("goal", "obstacle", "action", "outcome", "cost")
BASIS_STATES = ("explicit", "inferred", "derived", "unverified")
STATES = ("open", "blocked", "advanced", "resolved", "failed")

STATUS_TO_STATE = {
    "completed": "resolved", "resolved": "resolved", "success": "resolved",
    "failed": "failed", "abandoned": "failed",
    "blocked": "blocked", "open": "open", "ongoing": "advanced",
    "unknown": "advanced", "uncertain": "advanced",
}
TERMINAL_STATES = ("resolved", "failed")

SUCCESS_LEXEMES = (
    "获释", "获救", "追回", "破案", "破了", "拿下", "取得", "成功", "获授", "拜相",
    "解绳", "出洞", "获释", "夺回", "收复", "平定", "归降", "归顺", "成真", "功成",
    "脱身", "逃出", "解开", "查明", "洗清", "复位", "登基", "称帝", "结义", "凯旋",
)
FAILURE_LEXEMES = (
    "被捕", "被擒", "被囚", "被绑", "阵亡", "身死", "身亡", "被杀", "被斩", "自刎",
    "败亡", "溃败", "失守", "陷落", "投降", "放弃", "行不通", "失败", "遭捕",
)
TEMPORAL_HANDOFF = ("时间顺序承接", "时间顺序", "承接上一阶段", "顺序承接", "上一阶段",
                    "按时间", "时间线", "紧随其后", "时间上")

VOLUME_BOUNDARY_MARKERS = [
    {"volume": 1, "name": "京察风云", "nameQuote": "第一卷是京察风云！",
     "endAnchor": "第一卷结束了",
     "authorNote": "第二卷，国士无双。", "sourceOfName": "作者卷尾单章"},
    {"volume": 2, "name": "国士无双", "nameQuote": "这一卷的名称：国士无双！",
     "endAnchor": "第二卷结束了",
     "authorNote": "第三卷结束了。", "sourceOfName": "作者卷尾单章"},
    {"volume": 3, "name": "少年羁旅", "nameQuote": "第三卷《少年羁旅》",
     "endAnchor": "第三卷结束了。",
     "authorNote": "第四卷叫《逐鹿中原》。", "sourceOfName": "作者卷尾单章"},
    {"volume": 4, "name": "逐鹿中原", "nameQuote": "第四卷叫《逐鹿中原》。",
     "endAnchor": "第四卷——逐鹿中原，写到这里就结束了。",
     "authorNote": "第四卷——逐鹿中原，写到这里就结束了。", "sourceOfName": "作者卷尾单章"},
]
FINAL_VOLUME = {"volume": 5, "name": None, "nameQuote": None,
                "sourceOfName": "原文仅称『最后一卷』，卷名未在正文出现",
                "authorNote": "到了最后一卷"}


def norm(s: str) -> str:
    return re.sub(r"[\s\u3000]+", "", s or "")


def load_chapters(book_key: str, text: str) -> tuple[list[dict], dict]:
    p = SOURCE_INDEX / f"{book_key}.json"
    if p.exists():
        try:
            idx = json.loads(p.read_text(encoding="utf-8"))
            chs = idx.get("chapters") or []
            if chs:
                return ([{"heading": c.get("heading") or c.get("label") or "", "start": c["start"]}
                         for c in chs],
                        {"source": "artifacts/plan100/source-index",
                         "path": str(p.relative_to(ROOT)), "note": "P02 共享接口"})
        except Exception as exc:
            print(f"  ! source-index {p.name} 读取失败({exc})，回落 build_chapter_index", file=sys.stderr)
    return ([{"heading": c["heading"], "start": c["start"]} for c in build_chapter_index(text)],
            {"source": "tools/plan100/evidence_audit.py::build_chapter_index",
             "path": "tools/plan100/evidence_audit.py",
             "note": "P02 source-index 未就绪；已解决全角空格/抓取站导航垃圾/重号章三个坑"})


def locate(chapters: list[dict], off: int) -> dict | None:
    lo, hi, found = 0, len(chapters) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if chapters[mid]["start"] <= off:
            found = chapters[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return found


class Verifier:
    """原文子串复核。任何引文都必须过这一关，没过就不算锚点。"""

    def __init__(self, text: str, text_hash: str, source_id: str, source_path: str,
                 chapters: list[dict], declared_hash: str | None):
        self.text = text
        self.text_hash = text_hash
        self.source_id = source_id
        self.source_path = source_path
        self.chapters = chapters
        self.declared_hash = declared_hash
        self.stats = Counter()

    def verify(self, quote: str, start=None, end=None) -> dict:
        """返回规范锚点。定位不到就如实给 match=unmatched，绝不硬凑。"""
        q = quote or ""
        if isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(self.text):
            actual = self.text[start:end]
            if actual == q:
                m = "exact"
            elif norm(actual) == norm(q):
                m = "normalized"
            else:
                m = "unmatched"
        else:
            if q:
                i = self.text.find(q)
                if i >= 0 and self.text.find(q, i + 1) < 0:
                    start, end, m = i, i + len(q), "exact"
                elif i >= 0:
                    start, end, m = i, i + len(q), "ambiguous"
                else:
                    m = "unmatched"
            else:
                m = "missing"
        anchor = {
            "sourceId": self.source_id, "sourcePath": self.source_path,
            "offsetUnit": "codepoint", "textHash": self.text_hash,
            "start": start, "end": end, "quote": q, "match": m,
            "verifies": "verbatim-substring-only",
        }
        ch = locate(self.chapters, start) if isinstance(start, int) else None
        if ch:
            anchor["chapterHeading"] = ch["heading"]
        self.stats[m] += 1
        return anchor

    def chapter_of(self, off) -> str:
        ch = locate(self.chapters, off) if isinstance(off, int) else None
        return ch["heading"] if ch else ""



def build_aspect(graph: dict, task: dict, name: str, verifier: Verifier,
                 aspect_refs: dict) -> dict:
    """把源记录的文本字段 + fieldEvidence 变成带证据的四态标记维度。

    四态判据（本文件的口径，写死在代码里以便复核）：
      explicit   文本本身就是原文子串，且该维度有逐字命中的锚点 —— 命题在原文里直述。
      inferred   文本不是原文子串（是分析者的归纳），但该维度有逐字命中的锚点。
      derived    文本非空、该维度无逐字锚点，但有真实因果边支撑（由 build_task_machine 补）。
      unverified 以上都不成立 —— 没有原文支撑；缺就是缺。
    """
    raw = task.get(name)
    text = raw if isinstance(raw, str) else ""
    present = bool(text.strip())
    refs = [r for r in (aspect_refs.get(name) or []) if isinstance(r, dict)]
    anchors = [verifier.verify(r.get("quote"), r.get("start"), r.get("end")) for r in refs]
    exact = [a for a in anchors if a["match"] == "exact"]

    verbatim = present and text.count(text) > 0 and verifier.text.count(text) > 0

    if not present:
        basis = "unverified"
        note = "源记录此维度为空字符串；不填默认值，按未核验处理。"
    elif verbatim and exact:
        basis = "explicit"
        note = (f"维度文本本身是原文子串，且 {len(exact)} 条引句逐字命中；"
                "逐字命中只固定文本位置，不自动证明解释正确。")
    elif exact:
        basis = "inferred"
        note = (f"维度文本是分析者归纳、**不是**原文子串；该维度有 {len(exact)} 条逐字命中原文的引句，"
                "因此可作归纳，但不得读作原文直述。")
    else:
        basis = "unverified"
        note = ("维度文本非空但该维度没有任何定位记录（fieldEvidence 缺该维度）；"
                "按未核验处理，不升格为原文，也不按位置猜测归属。")
    return {"text": text, "basis": basis, "sourceRefs": anchors,
            "exactRefCount": len(exact),
            "textVerbatimInSource": verbatim,
            "textIsAnalystSummary": present and not verbatim,
            "basisNote": note,
            "causalBasis": "unverified", "causeEdges": [],
            "causeEdgeHintBasis": "heuristic-keyword-match"}


def terminal_evidence(task: dict, aspects: dict, state: str) -> dict:
    """R5：终态的证据来源与"成功"读数的四态标记。

    核心纪律（审核原话「播放完成不自动标记任务成功」）：
      · `status: completed`、事件序列排完、存在 outcomeEventId —— 三者都**不是**成功证据。
      · 唯一能拿到 successClaim="explicit" 的路径，是结果维度的引句**逐字命中原文**
        且其中出现明确的成功措辞、同时不出现任何失败措辞。
      · 连这条路径也只能证明"原文在说成功"，不能证明解释正确；故 claimVerified 恒为 false。
    """
    outcome = aspects["outcome"]
    outcome_anchors = outcome["sourceRefs"]
    exact_outcome = [a for a in outcome_anchors if a["match"] == "exact"]
    joined = " ".join(a["quote"] for a in exact_outcome)

    hits_success = [w for w in SUCCESS_LEXEMES if w in joined]
    hits_failure = [w for w in FAILURE_LEXEMES if w in joined]

    status_in_source = str(task.get("status") or "")
    outcome_event_id = task.get("outcomeEventId") or None
    claimed_terminal = status_in_source in ("completed", "failed", "resolved", "success")

    if state == "resolved" and exact_outcome and hits_success and not hits_failure:
        claim = "explicit"
        why = (f"结果维度有 {len(exact_outcome)} 条逐字命中原文的引句，且含成功措辞 "
               f"{hits_success}；未出现失败措辞。逐字命中只固定文本位置，不证明解释正确。")
    elif state == "resolved" and exact_outcome:
        claim = "derived"
        why = ("结果维度引句逐字命中，但未含明确成功措辞"
               + (f"，且出现失败措辞 {hits_failure}" if hits_failure else "")
               + "；成功读数只能是推导，不升格为明确。")
    elif state == "resolved":
        claim = "unverified"
        why = ("终态由源记录 status 给出，但结果维度无逐字命中原文的引句；"
               "事件序列排完不构成成功证据，成功与否未核验。")
    elif state == "failed":
        if exact_outcome and hits_success and not hits_failure:
            claim = "explicit"
            why = (f"源记录 status 为失败，但结果维度 {len(exact_outcome)} 条逐字引句含成功措辞 "
                   f"{hits_success} 且无失败措辞；两者矛盾，按原文措辞给 explicit，"
                   "需人工复核源记录 status 是否滞后。逐字命中只固定文本位置，不证明解释正确。")
        elif exact_outcome:
            claim = "derived"
            why = ("源记录 status 为失败，结果维度有逐字锚点"
                   + (f"，并出现失败措辞 {hits_failure}" if hits_failure
                      else "，但未含明确成功措辞")
                   + "；失败被原文锚定，成功不得升格为明确。")
        else:
            claim = "unverified"
            why = "源记录 status 为失败；结果维度无逐字锚点，失败判据未核验。"
    else:
        claim = "unverified"
        why = f"当前状态 {state} 不是终态，成功/失败均未核验。"

    return {
        "state": state,
        "statusInSourceRecord": status_in_source,
        "sourceRecordClaimsTerminal": claimed_terminal,
        "outcomeEventId": outcome_event_id,
        "outcomeAnchoredInText": bool(exact_outcome),
        "outcomeQuote": exact_outcome[0]["quote"] if exact_outcome else None,
        "successLexemeHits": hits_success,
        "failureLexemeHits": hits_failure,
        "successClaim": claim,
        "claimVerified": False,
        "successClaimNote": why,
        "endNotSuccess": claim != "explicit",
        "rule": ("END_IS_NOT_SUCCESS：status=completed / 事件序列排完 / outcomeEventId 存在，"
                 "三者都不构成成功证据；只有结果维度的逐字原文引句含成功措辞且无失败措辞才允许 "
                 "explicit。state=failed 时同样适用——「有逐字锚点」只锚定结果，不确认成功。"),
    }


ASPECT_EDGE_HINTS = {
    "obstacle": ("阻", "难", "被", "拒", "威胁", "失败", "不能", "无法", "陷", "困", "敌"),
    "action": ("后", "才", "于是", "遂", "以", "用", "借", "请", "要求", "提出", "索", "写"),
    "outcome": ("结果", "终", "获", "成", "破", "追回", "宣布", "释放", "交"),
    "goal": ("为了", "欲", "求", "想", "图", "意图", "目的"),
}


def causal_refs_for_aspect(aspect: str, ev_ids: list, by_id: dict, cause_edges: list) -> dict:
    """把任务事件序列里**真实存在的因果边**挂到某个维度上。"""
    if not ev_ids:
        return {"edgeIds": [], "anchors": [], "causalBasis": "unverified",
                "causeEdgeHintBasis": "heuristic-keyword-match",
                "note": "任务没有事件序列，无法挂因果边。"}
    pos = {eid: i for i, eid in enumerate(ev_ids)}
    in_set = set(ev_ids)
    edges = [c for c in cause_edges
             if c.get("fromEventId") in in_set and c.get("toEventId") in in_set]
    if not edges:
        return {"edgeIds": [], "anchors": [], "causalBasis": "unverified",
                "causeEdgeHintBasis": "heuristic-keyword-match",
                "note": ("该任务的 %d 个事件之间在 causeEdges 里没有任何真实因果边；"
                         "任务内相邻事件只是时间相邻，不得读作因果。" % len(ev_ids))}
    keywords = ASPECT_EDGE_HINTS.get(aspect, ())
    picked, anchors = [], []
    for c in edges:
        desc = c.get("description") or ""
        if not any(k in desc for k in keywords):
            continue
        picked.append(c.get("id"))
        for r in (c.get("sourceRefs") or []):
            if isinstance(r, dict):
                anchors.append({"quote": r.get("quote"), "start": r.get("start"),
                                "end": r.get("end"),
                                "match": r.get("match") or "unverified",
                                "eventPair": [c.get("fromEventId"), c.get("toEventId")],
                                "description": desc})
    if not picked:
        return {"edgeIds": [], "anchors": [], "causalBasis": "unverified",
                "causeEdgeHintBasis": "heuristic-keyword-match",
                "note": (f"任务内有 {len(edges)} 条真实因果边，但没有一条的 description "
                         f"命中 {aspect} 的关键词；不强行挂载。")}
    return {"edgeIds": picked, "anchors": anchors, "causalBasis": "inferred",
            "causeEdgeHintBasis": "heuristic-keyword-match",
            "note": (f"命中 {len(picked)} 条真实因果边（关键词启发式）。"
                     "因果边的维度归属未经原文核验，故最高只到 inferred。")}


def build_task_machine(task: dict, graph: dict, verifier: Verifier, by_id: dict,
                       cause_pairs: set, characters: dict, cause_edges: list) -> dict:
    aspect_refs = task.get("fieldEvidence") if isinstance(task.get("fieldEvidence"), dict) else {}
    aspects = {a: build_aspect(graph, task, a, verifier, aspect_refs) for a in ASPECTS}

    status = str(task.get("status") or "")
    state = STATUS_TO_STATE.get(status, "advanced")

    ev_ids = [i for i in (task.get("eventIds") or []) if i in by_id]
    ev_ids.sort(key=lambda i: by_id[i].get("order", 0))

    for a in ASPECTS:
        c = causal_refs_for_aspect(a, ev_ids, by_id, cause_edges)
        asp = aspects[a]
        asp["causalBasis"] = c["causalBasis"]
        asp["causeEdges"] = c["edgeIds"]
        asp["causeEdgeHintBasis"] = c["causeEdgeHintBasis"]
        asp["causeEdgeNote"] = c["note"]
        if asp["basis"] == "unverified" and asp["text"].strip() and c["causalBasis"] != "unverified":
            asp["basis"] = "derived"
            asp["basisNote"] += " 该维度有真实因果边支撑（维度归属为启发式，未经原文核验），按推导处理。"

    anchors = [verifier.verify(r.get("quote"), r.get("start"), r.get("end"))
               for r in (task.get("sourceRefs") or []) if isinstance(r, dict)]
    top = []
    seen = set()
    for a in anchors + [a for asp in aspects.values() for a in asp["sourceRefs"]]:
        key = (a.get("start"), a.get("end"), a.get("quote"))
        if key in seen:
            continue
        seen.add(key)
        top.append(a)
    exact_top = [a for a in top if a["match"] == "exact"]

    dim_anchored = [a for a in ASPECTS if aspects[a]["exactRefCount"]]
    task_level_only = [a for a in ASPECTS if not aspects[a]["exactRefCount"]]
    has_field_evidence = any(isinstance(v, list) and v for v in aspect_refs.values())
    aspect_gap = None
    if task_level_only:
        aspect_gap = (
            f"{len(task_level_only)} 个维度（{task_level_only}）没有维度级原文锚点。"
            + ("源记录的 fieldEvidence 未覆盖这些维度。"
               if has_field_evidence else
               "源记录只提供任务级 sourceRefs/evidenceQuotes，未给维度标记；"
               "不按顺序或位置猜测归属。")
            + " 任务级 evidence 仍可用于跳转原文。")

    outcome_event = task.get("outcomeEventId")
    transitions = []
    seq_only = 0
    for idx, eid in enumerate(ev_ids):
        e = by_id[eid]
        prev = ev_ids[idx - 1] if idx else None
        nxt = ev_ids[idx + 1] if idx + 1 < len(ev_ids) else None
        if eid == outcome_event:
            to = state if state in TERMINAL_STATES else "advanced"
            role = "outcome"
        elif idx == 0:
            to, role = "open", "onset"
        else:
            to, role = "advanced", "progress"

        in_edge = (prev, eid) in cause_pairs
        out_edge = (eid, nxt) in cause_pairs if nxt else False
        if in_edge or out_edge:
            relation = "causal-evidence"
        else:
            relation = "sequence-only"
            seq_only += 1

        ref = e.get("quoteRef") if isinstance(e.get("quoteRef"), dict) else {}
        qref = verifier.verify(ref.get("quote") or e.get("quote"), ref.get("start"), ref.get("end"))
        transitions.append({
            "at": {"chapter": e.get("chapter"), "order": e.get("order"),
                   "offset": qref.get("start")},
            "from": None if idx == 0 else None,
            "to": to,
            "role": role,
            "eventId": eid,
            "eventTitle": e.get("title") or "",
            "sourceRefs": [qref],
            "relation": relation,
            "relationNote": ("causeEdges 中存在真实因果边" if relation == "causal-evidence"
                             else "同任务内仅时间相邻；无因果边，不得读作因果"),
        })
    chain_state = "open"
    for t in transitions:
        t["from"] = chain_state
        chain_state = t["to"]

    char_name = task.get("character") or ""
    char_id = task.get("characterId") or ""
    if not char_id and char_name:
        c = characters.get(char_name)
        char_id = c["id"] if c else ""
        if c and not char_name:
            char_name = c["name"]

    return {
        "taskId": task.get("id") or task.get("entityId"),
        "sourceEntityId": task.get("entityId") or task.get("id"),
        "name": task.get("name") or "",
        "character": char_name,
        "characterId": char_id,
        "characterResolved": bool(char_id) and char_id in {c["id"] for c in characters.values()},
        "goal": aspects["goal"],
        "obstacle": aspects["obstacle"],
        "action": aspects["action"],
        "outcome": aspects["outcome"],
        "cost": aspects["cost"],
        "state": state,
        "stateBasis": ("source-record-status" if status in STATUS_TO_STATE
                       else "unmapped-status→advanced"),
        "statusInSourceRecord": status or None,
        "transitions": transitions,
        "endNotSuccess": False,
        "terminalEvidence": terminal_evidence(task, aspects, state),
        "eventIds": ev_ids,
        "sourceRefs": top,
        "claimVerified": False,
        "semanticStatus": "unreviewed",
        "provenance": task.get("provenance") or "source-graph",
        "reviewNotes": task.get("reviewNotes") or "",
        "coverage": {
            "aspectsWithExactAnchors": dim_anchored,
            "aspectsWithoutExactAnchor": task_level_only,
            "aspectAnchorHonestGap": aspect_gap,
            "aspectsEmpty": [a for a in ASPECTS if not aspects[a]["text"].strip()],
            "aspectsUnverified": [a for a in ASPECTS if aspects[a]["basis"] == "unverified"],
            "events": len(ev_ids),
            "eventsLinkedByRealCause": sum(1 for t in transitions
                                           if t["relation"] == "causal-evidence"),
            "eventsSequenceOnly": seq_only,
            "taskLevelExactRefs": len(exact_top),
            "taskLevelAnchorNavigationOnly": True,
        },
        "reverseEvidence": {
            "whyNotResolved": ("终态只由源记录 status 给出；结果维度无逐字原文锚点。"
                               if state == "resolved" and not any(
                                   a["match"] == "exact" for a in aspects["outcome"]["sourceRefs"])
                               else None),
            "sequenceOnlyTransitionCount": seq_only,
            "note": "sequence-only 的相邻事件只是时间相邻；本文件不把它当因果。",
        },
    }



def derive_volume_boundaries(graph: dict, text: str, verifier: Verifier, chapters: list[dict]):
    """从正文抽取的作者卷边界，映射到事件 order。全部带可复核 quote。"""
    events = sorted([e for e in graph["events"] if isinstance(e, dict)],
                    key=lambda e: e.get("order", 0))
    offs = []
    for e in events:
        r = e.get("quoteRef") if isinstance(e.get("quoteRef"), dict) else {}
        if isinstance(r.get("start"), int):
            offs.append((r["start"], e.get("order")))
    offs.sort()

    def order_at(off):
        lo, hi, best = 0, len(offs) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if offs[mid][0] <= off:
                best = offs[mid][1]
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    out = []
    for spec in VOLUME_BOUNDARY_MARKERS:
        anchor = spec["endAnchor"]
        occurrences = [m.start() for m in re.finditer(re.escape(anchor), text)]
        unique = len(occurrences) == 1
        i = occurrences[0] if unique else None
        name_q = spec["nameQuote"]
        out.append({
            "volume": spec["volume"], "name": spec["name"],
            "nameVerified": bool(name_q) and name_q in text,
            "nameQuote": name_q,
            "nameQuoteFound": bool(name_q) and name_q in text,
            "nameQuoteOccurrences": ([m.start() for m in re.finditer(re.escape(name_q), text)]
                                     if name_q else []),
            "endMarkerQuote": anchor,
            "endMarkerFound": unique,
            "endMarkerOccurrences": occurrences,
            "endMarkerRejectReason": None if unique else
            f"标记在正文出现 {len(occurrences)} 次，不唯一，无法作为边界证据",
            "endMarkerOffset": i,
            "endMarkerChapter": verifier.chapter_of(i) if unique else None,
            "endOrder": order_at(i) if unique else None,
            "authorNoteQuote": spec["authorNote"],
            "authorNoteFound": spec["authorNote"] in text,
            "sourceOfName": spec["sourceOfName"],
        })
    last_anchor = FINAL_VOLUME["authorNote"]
    last_occ = [m.start() for m in re.finditer(re.escape(last_anchor), text)]
    last = dict(FINAL_VOLUME)
    last.update({"nameQuoteFound": False, "endMarkerFound": len(last_occ) == 1,
                 "endMarkerQuote": last_anchor,
                 "endMarkerOccurrences": last_occ,
                 "endMarkerRejectReason": None if len(last_occ) == 1 else "不唯一",
                 "endMarkerOffset": last_occ[0] if len(last_occ) == 1 else None,
                 "endMarkerChapter": verifier.chapter_of(last_occ[0]) if len(last_occ) == 1 else None,
                 "endOrder": len(events), "authorNoteFound": bool(last_occ)})
    out.append(last)
    return out


def storyline_source_refs(ev_ids: list[str], by_id: dict, verifier: Verifier, cap: int = 12):
    """把窗口内事件的原文引句变成锚点。定位失败的不计入。"""
    refs, seen = [], set()
    for eid in ev_ids:
        e = by_id.get(eid)
        if not e:
            continue
        r = e.get("quoteRef") if isinstance(e.get("quoteRef"), dict) else {}
        a = verifier.verify(r.get("quote") or e.get("quote"), r.get("start"), r.get("end"))
        if a["match"] != "exact":
            continue
        key = (a["start"], a["end"])
        if key in seen:
            continue
        seen.add(key)
        a = dict(a, eventId=eid, chapter=e.get("chapter"), order=e.get("order"))
        refs.append(a)
    refs.sort(key=lambda a: a["start"])
    if len(refs) > cap:
        step = (len(refs) - 1) / (cap - 1)
        refs = [refs[round(i * step)] for i in range(cap)]
    return refs


def rebuild_dafeng_storylines(graph: dict, text: str, verifier: Verifier, by_id: dict,
                              chapters: list[dict]) -> tuple[list[dict], dict]:
    """把大奉 8 条机械等分线替换成由真实卷边界 + 章节边界划定、逐条带原文锚点的线。"""
    events = sorted([e for e in graph["events"] if isinstance(e, dict)],
                    key=lambda e: e.get("order", 0))
    n = len(events)
    volumes = derive_volume_boundaries(graph, text, verifier, chapters)

    cuts = [1]
    for v in volumes[:-1]:
        if isinstance(v.get("endOrder"), int) and v["endOrder"] + 1 > cuts[-1]:
            cuts.append(v["endOrder"] + 1)
    if cuts[-1] <= n:
        cuts.append(n + 1)

    old = [s for s in graph.get("storylines") or [] if isinstance(s, dict)]
    out = []
    for i in range(len(cuts) - 1):
        start, end = cuts[i], cuts[i + 1] - 1
        window_ids = [e["id"] for e in events if start <= e.get("order", 0) <= end]
        vol = next((v for v in volumes if v["volume"] == i + 1), None)
        first, last = by_id[window_ids[0]], by_id[window_ids[-1]]

        boundary_anchor = None
        if vol and vol.get("endMarkerFound"):
            boundary_anchor = verifier.verify(vol["endMarkerQuote"], vol["endMarkerOffset"],
                                              vol["endMarkerOffset"] + len(vol["endMarkerQuote"]))
            boundary_anchor["role"] = "volume-boundary-evidence"
            boundary_anchor["chapter"] = vol.get("endMarkerChapter")

        refs = storyline_source_refs(window_ids, by_id, verifier, cap=12)
        if boundary_anchor and all(r["start"] != boundary_anchor["start"] for r in refs):
            refs = refs + [boundary_anchor]
            refs.sort(key=lambda a: a["start"])

        cast_cnt: Counter[str] = Counter()
        for eid in window_ids:
            for c in by_id[eid].get("characters") or []:
                cast_cnt[c] += 1

        old_line = old[i] if i < len(old) else {}
        name = (f"第{vol['volume']}卷" + (f"·{vol['name']}" if vol and vol.get("name") else "")
                + f"（事件 {start}–{end}）") if vol else f"事件 {start}–{end}"
        hr = old_line.get("handoff_reason") or ""
        out.append({
            "id": f"vol-bounded-{i+1}",
            "replacesId": old_line.get("id"),
            "replacesVerdict": "mechanical-equal-split",
            "name": name,
            "kind": "主线",
            "lead": old_line.get("lead") or "",
            "attach_order": start,
            "window": [start, end],
            "eventIds": window_ids,
            "events": [e["order"] for e in events if start <= e.get("order", 0) <= end],
            "cast": [c for c, _ in cast_cnt.most_common(24)],
            "castDerivation": "窗口内事件 characters 的真实频次聚合（不是等分切片里的首现）",
            "boundaryBasis": "volume-end-marker-in-source-text",
            "boundaryEvidence": boundary_anchor,
            "volume": {"index": vol["volume"], "name": vol["name"],
                       "nameVerifiedInText": vol.get("nameQuoteFound", False),
                       "nameQuote": vol.get("nameQuote"),
                       "nameSource": vol.get("sourceOfName")} if vol else None,
            "startChapter": first.get("chapter"),
            "endChapter": last.get("chapter"),
            "handoff_from": (out[-1]["id"] if out else ""),
            "handoff_reason": (f"第{i}卷在原文以『{vol['endMarkerQuote']}』收束，第{i+1}卷由此开始；"
                               f"边界由原文标记决定，不是按事件数切分。"
                               if vol and vol.get("endMarkerFound") else ""),
            "handoffReasonKind": "source-text-volume-boundary" if vol and vol.get("endMarkerFound")
            else "unverified",
            "supersededHandoffReason": hr or None,
            "supersededHandoffReasonIsTemporalOnly": bool(hr) and any(t in hr for t in TEMPORAL_HANDOFF),
            "sourceRefs": refs,
            "resolution": "收束" if i == len(cuts) - 2 else "悬置",
            "resolved": None,
            "resolvedBasis": "unverified",
            "claimVerified": False,
            "semanticStatus": "unreviewed",
            "provenance": "p03-volume-bounded-from-source-text",
            "goal": old_line.get("goal") or "",
            "goalBasis": old_line.get("goal") and "unverified" or "unverified",
            "theme": old_line.get("theme") or "",
            "reviewNotes": ("本条替换机械等分切片。窗口边界来自作者卷尾单章的原文标记；"
                            "目标/主题沿用源记录文本并按未核验处理，未私自改写语义。"),
        })

    summary = {
        "replaced": len(out),
        "boundariesFromSourceText": sum(1 for v in volumes if v.get("endMarkerFound")),
        "volumeNamesVerified": sum(1 for v in volumes if v.get("nameQuoteFound")),
        "finalVolumeNameMissing": FINAL_VOLUME["name"] is None,
        "anchorRate": round(sum(1 for s in out if s["sourceRefs"]) / len(out), 4) if out else None,
        "volumes": [{k: v.get(k) for k in ("volume", "name", "nameQuoteFound", "endMarkerQuote",
                                           "endMarkerFound", "endMarkerChapter", "endOrder")}
                    for v in volumes],
    }
    return out, summary


def keep_storylines(graph: dict, by_id: dict, verifier: Verifier) -> tuple[list[dict], dict]:
    """西游/三国：结构不动，只做证据补齐与自洽性检查。"""
    out = []
    for s in graph.get("storylines") or []:
        if not isinstance(s, dict):
            continue
        ev_ids = [i for i in (s.get("eventIds") or []) if i in by_id]
        ev_ids.sort(key=lambda i: by_id[i].get("order", 0))
        refs = [verifier.verify(r.get("quote"), r.get("start"), r.get("end"))
                for r in (s.get("sourceRefs") or []) if isinstance(r, dict)]
        exact = [r for r in refs if r["match"] == "exact"]
        hr = s.get("handoff_reason") or ""
        hf = s.get("handoff_from") or ""
        ids = {str(x.get("id") or x.get("entityId"))
               for x in (graph.get("storylines") or []) if isinstance(x, dict)}
        hf_ok = (not hf) or (str(hf) in ids and str(hf) != str(s.get("id")))
        out.append({
            "id": s.get("id") or s.get("entityId"),
            "name": s.get("name") or "",
            "kind": s.get("kind") or "",
            "lead": s.get("lead") or "",
            "attach_order": s.get("attach_order"),
            "window": [ev_ids and by_id[ev_ids[0]].get("order"),
                       ev_ids and by_id[ev_ids[-1]].get("order")] if ev_ids else None,
            "eventIds": ev_ids,
            "cast": s.get("cast") or [],
            "boundaryBasis": "source-record",
            "handoff_from": hf,
            "handoff_reason": hr,
            "handoffReasonKind": ("" if not hr else
                                  "temporal-adjacency-only" if any(t in hr for t in TEMPORAL_HANDOFF)
                                  else "narrative"),
            "handoffSelfConsistent": hf_ok,
            "sourceRefs": refs,
            "exactRefCount": len(exact),
            "resolution": s.get("resolution") or "",
            "resolved": None if s.get("resolved") is not True else True,
            "resolvedBasis": "source-record-flag-unverified",
            "claimVerified": False,
            "semanticStatus": "unreviewed",
            "provenance": s.get("provenance") or "source-graph",
            "goal": s.get("goal") or "",
            "theme": s.get("theme") or "",
        })
    summary = {
        "kept": len(out),
        "anchorRate": round(sum(1 for s in out if any(r["match"] == "exact" for r in s["sourceRefs"]))
                            / len(out), 4) if out else None,
        "handoffInconsistent": sum(1 for s in out if not s["handoffSelfConsistent"]),
        "handoffTemporalOnly": sum(1 for s in out if s["handoffReasonKind"] == "temporal-adjacency-only"),
        "resolvedAutoTrueCount": sum(1 for s in out if s["resolved"] is True),
    }
    return out, summary



def process(key: str, title: str) -> dict:
    graph = json.loads((ROOT / "data" / "cache" / f"{key}.json").read_text(encoding="utf-8"))
    text = json.loads((ROOT / "data" / "cache" / f"{key}.docs.json").read_text(encoding="utf-8"))[0]["text"]
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    meta_src = ((graph.get("meta") or {}).get("sources") or [{}])[0]
    chapters, chap_prov = load_chapters(key, text)
    verifier = Verifier(text, text_hash, meta_src.get("id") or "", meta_src.get("path") or "",
                        chapters, meta_src.get("textHash"))

    events = [e for e in graph.get("events") or [] if isinstance(e, dict)]
    by_id = {e["id"]: e for e in events}
    characters = {}
    for c in graph.get("characters") or []:
        if isinstance(c, dict) and c.get("name"):
            characters[c["name"]] = c

    cause_edges = [c for c in (graph.get("causeEdges") or []) if isinstance(c, dict)]
    cause_pairs = {(c.get("fromEventId"), c.get("toEventId")) for c in cause_edges}

    tasks = [build_task_machine(t, graph, verifier, by_id, cause_pairs, characters, cause_edges)
             for t in (graph.get("tasks") or []) if isinstance(t, dict)]
    for t in tasks:
        t["endNotSuccess"] = t["terminalEvidence"]["endNotSuccess"]

    if key == "9b676d7031b1bcd3b8377a18":
        lines, line_summary = rebuild_dafeng_storylines(graph, text, verifier, by_id, chapters)
    else:
        lines, line_summary = keep_storylines(graph, by_id, verifier)

    task_summary = {
        "tasks": len(tasks),
        "states": dict(Counter(t["state"] for t in tasks)),
        "endNotSuccessCount": sum(1 for t in tasks if t["endNotSuccess"]),
        "successClaimExplicit": sum(1 for t in tasks if t["terminalEvidence"]["successClaim"] == "explicit"),
        "tasksWithAllFiveAspectsNonEmpty": sum(
            1 for t in tasks if all(t[a]["text"].strip() for a in ASPECTS)),
        "aspectBasis": {a: dict(Counter(t[a]["basis"] for t in tasks)) for a in ASPECTS},
        "aspectTextVerbatim": {a: sum(1 for t in tasks if t[a]["textVerbatimInSource"])
                               for a in ASPECTS},
        "aspectTextIsAnalystSummary": {a: sum(1 for t in tasks if t[a]["textIsAnalystSummary"])
                                       for a in ASPECTS},
        "emptyAspects": {a: sum(1 for t in tasks if not t[a]["text"].strip()) for a in ASPECTS},
        "tasksWithExactAnchor": sum(1 for t in tasks if any(r["match"] == "exact" for r in t["sourceRefs"])),
        "tasksWithExactAspectAnchor": sum(
            1 for t in tasks if any(t[a]["exactRefCount"] for a in ASPECTS)),
        "aspectsCoveredByExactAnchor": {
            a: sum(1 for t in tasks if t[a]["exactRefCount"]) for a in ASPECTS},
        "totalExactRefs": sum(sum(1 for r in t["sourceRefs"] if r["match"] == "exact") for t in tasks),
        "totalSequenceOnlyTransitions": sum(t["reverseEvidence"]["sequenceOnlyTransitionCount"]

                                            for t in tasks),
        "totalCausalTransitions": sum(t["coverage"]["eventsLinkedByRealCause"] for t in tasks),
        "tasksWithCharacterResolved": sum(1 for t in tasks if t["characterResolved"]),
        "aspectCausalBasis": {a: dict(Counter(t[a]["causalBasis"] for t in tasks)) for a in ASPECTS},
        "aspectsWithCauseEdge": {a: sum(1 for t in tasks if t[a]["causeEdges"]) for a in ASPECTS},
        "tasksWithAnyCauseEdge": sum(
            1 for t in tasks if any(t[a]["causeEdges"] for a in ASPECTS)),
        "causeClaimCeiling": "inferred（因果边的维度归属未经原文核验）",
    }
    verify_stats = dict(verifier.stats)

    tasks_doc = {
        "schema": "castline/p03-task-state-machine/1",
        "bookKey": key, "title": title,
        "sourceId": meta_src.get("id"), "sourcePath": meta_src.get("path"),
        "textHash": text_hash, "textHashMatchesMeta": meta_src.get("textHash") == text_hash,
        "offsetUnit": "codepoint",
        "chapterIndexProvenance": chap_prov,
        "aspectOrder": list(ASPECTS),
        "basisVocabulary": list(BASIS_STATES),
        "stateVocabulary": list(STATES),
        "rules": {
            "R1_no_fabrication": "字段缺即缺；不填默认值。",
            "R2_four_state_basis": list(BASIS_STATES),
            "R3_quote_must_be_verbatim": "text[start:end] == quote 才计 exact。",
            "R4_no_temporal_as_causal": "同任务相邻事件无 causeEdges 边时标 sequence-only。",
            "R5_end_is_not_success": "终态不因播放/序列结束而判成功；见 terminalEvidence。",
        },
        "summary": task_summary,
        "anchorStats": verify_stats,
        "tasks": tasks,
    }

    lines_doc = {
        "schema": "castline/p03-storyline-attachment/1",
        "bookKey": key, "title": title,
        "sourceId": meta_src.get("id"), "sourcePath": meta_src.get("path"),
        "textHash": text_hash, "offsetUnit": "codepoint",
        "chapterIndexProvenance": chap_prov,
        "attachmentMode": ("volume-boundary-from-source-text"
                           if key == "9b676d7031b1bcd3b8377a18" else "source-record-preserved"),
        "summary": line_summary,
        "storylines": lines,
    }
    return {"tasks": tasks_doc, "storylines": lines_doc, "taskSummary": task_summary,
            "lineSummary": line_summary}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=None, help="只跑指定 bookKey")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for key, title in BOOKS:
        if args.book and key != args.book:
            continue
        res = process(key, title)
        (OUT / f"{key}.tasks.json").write_text(
            json.dumps(res["tasks"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (OUT / f"{key}.storylines.json").write_text(
            json.dumps(res["storylines"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ts, ls = res["taskSummary"], res["lineSummary"]
        print(f"\n=== {title} ({key}) ===")
        print(f"  tasks {ts['tasks']} · states {ts['states']}")
        print(f"    五元组全非空 {ts['tasksWithAllFiveAspectsNonEmpty']}/{ts['tasks']}"
              f" · 空维度 {ts['emptyAspects']}")
        print(f"    维度证据标记 {ts['aspectBasis']}")
        print(f"    有 exact 锚点的任务 {ts['tasksWithExactAnchor']}/{ts['tasks']}"
              f" · 维度级 exact 任务 {ts['tasksWithExactAspectAnchor']}"
              f" · exact 锚点总数 {ts['totalExactRefs']}")
        print(f"    endNotSuccess {ts['endNotSuccessCount']}/{ts['tasks']}"
              f" · successClaim=explicit {ts['successClaimExplicit']}")
        print(f"    transitions: causal {ts['totalCausalTransitions']}"
              f" · sequence-only {ts['totalSequenceOnlyTransitions']}")
        print(f"  storylines {ls.get('kept') or ls.get('replaced')} · mode "
              f"{'rebuilt' if 'replaced' in ls else 'kept'} · anchorRate {ls.get('anchorRate')}")
        if "volumes" in ls:
            for v in ls["volumes"]:
                print(f"    卷{v['volume']} {v['name'] or '(原文未命名)'} "
                      f"nameOK={v['nameQuoteFound']} end@order={v['endOrder']} "
                      f"marker={v['endMarkerQuote']!r}")
        index.append({"bookKey": key, "title": title,
                      "tasks": res["tasks"]["summary"], "storylines": res["storylines"]["summary"]})
    (OUT / "P03-build-index.json").write_text(
        json.dumps({"generatedBy": "tools/plan100/build_task_state_machines.py",
                    "books": index}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n-> {artifact_rel(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
