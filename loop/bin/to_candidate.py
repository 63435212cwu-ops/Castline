#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 READER/VERIFIER 的产出转成 `tools/publish_reviewed.py` 认得的**候选**。

为什么必须要有这一层（环境建成后发现的真实断链，不修就会在几十小时后集体卡住）：
  READER 按角色契约自由产出 `tasks[] / causeEdges[] / states[] / foreshadows[]`；
  发布工具要的是另一套契约：
    {provenance: "assistant-reviewed-source",
     scope: {sourceId, textHash, start, end, offsetUnit, chapters, eventIds, method},
     layers: {tasks|causeEdges|clues|characterStates|relations|storylines: [节点…]}}
  节点还必须带 `sourceRefs[]`，每条的 start/end 要能**逐字**切出 quote。
  第一次拿真实候选跑 dry-run 被直接拒绝：
    `候选必须明确provenance=assistant-reviewed-source` → 补上后仍
    `候选source/ID校验未通过`。

参考实现取自归档里那次**真正发布成功**的候选：
  ~/Desktop/星系-audit-archive-20261007/content-candidate/dafeng-kangping-ch11-15.candidate.json
  其节点键为 name/goal/obstacle/action/outcome/cost/eventIds/quote/sourceRefs/fieldEvidence。

本脚本只做**格式转换 + 保守过滤**，不做任何语义加工：
  * 只搬运引证**能在原文逐字切出**的条目；
  * 引证不成立的条目丢弃并记账，不猜不补；
  * 复核 verdict=fail 的单元整条跳过；
  * 一律写 claimVerified=false，并在 coverageGaps 声明语义未经人工认证。

用法：
  python3 -B -s loop/bin/to_candidate.py --task read:dafeng:L0:0000
  python3 -B -s loop/bin/to_candidate.py --batch publish:dafeng:B000
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def stable_node_id(layer: str, node: dict) -> str:
    """内容寻址的稳定 ID：同一内容重复发布得到同一个 id，不同内容不会撞车。

    为什么不用随机 id：发布要可重放、可去重；随机 id 会让同一章重复审阅时
    产生"看起来是新内容"的重复节点。
    """
    basis = json.dumps({k: v for k, v in sorted(node.items())
                        if k not in ("provenance", "claimVerified", "semanticStatus", "reviewNotes")},
                       ensure_ascii=False, sort_keys=True)
    return "%s_review_%s" % (layer.rstrip("s") or layer,
                             hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20])

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
LOOP = ROOT / "loop"
OUT = LOOP / "state" / "out"
CAND = LOOP / "state" / "candidates"

BOOKS = {
    "dafeng": {"graph": "data/cache/9b676d7031b1bcd3b8377a18.json",
               "docs": "data/cache/9b676d7031b1bcd3b8377a18.docs.json"},
    "xiyou": {"graph": "data/cache/df959d743e53206f56db2f92.json",
              "docs": "data/cache/df959d743e53206f56db2f92.docs.json"},
    "sanguo": {"graph": "data/cache/152e2a6eed94f1075e7e7070.json",
               "docs": "data/cache/152e2a6eed94f1075e7e7070.docs.json"},
}


def task_result_status(item: dict, outcome: str, event_ids: list) -> dict:
    """透传无冲突的结构化结果声明；自由文本永不产生成功/失败终态。

    文本含否定、转折或范围保留时只退回待复核，不试图解释其语义。
    这会保守扣留部分真实成功；不能把此拦截器当作语义验证器。
    """
    def signal(value):
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        token = str(value).strip().lower()
        if token in ("true", "yes", "1", "成功", "达成", "met"):
            return True
        if token in ("false", "no", "0", "失败", "未达成", "not_met"):
            return False
        return None

    signals, reservations = [], []
    for key in ("resultIsSuccess", "objectiveMet", "success", "achieved"):
        value = item.get(key)
        parsed = signal(value)
        if parsed is not None:
            signals.append(parsed)
        elif value is not None and str(value).strip():
            reservations.append(key)
    for key in ("status", "state", "resultStatus", "outcomeStatus"):
        value = item.get(key)
        if value is None or not str(value).strip():
            continue
        token = str(value).strip().lower()
        if token in ("completed", "succeeded", "success"):
            signals.append(True)
        elif token in ("failed", "failure"):
            signals.append(False)
        else:
            reservations.append(key)
    negative = item.get("notSuccess")
    parsed_negative = signal(negative)
    if parsed_negative is not None:
        if parsed_negative:
            reservations.append("notSuccess")
    elif negative is not None and str(negative).strip():
        reservations.append("notSuccess")

    status, basis = "unknown", "not_evidenced"
    note = "缺少明确且无冲突的结构化结果声明；保留结果描述，等待语义复核"
    outcome_id = item.get("outcomeEventId")
    if not outcome or not isinstance(outcome_id, str) or outcome_id not in event_ids:
        note = "缺结果描述或原条目明确且属于本节点的 outcomeEventId，不能发布终态"
    elif True in signals and False in signals:
        basis, note = "reader_signal_conflict", "结构化结果声明互相冲突，等待语义复核"
    elif reservations:
        basis, note = "reader_signal_requires_review", "结果含部分、未定或否定保留：" + ", ".join(reservations)
    elif signals:
        caveat = re.search(r"[不未没无否]|但是|然而|是否|未知|部分|尚|待|只|仅|\b(?:not|no|never|failed|failure|unknown|partial|pending|unresolved)\b",
                           outcome, re.IGNORECASE)
        opposite = False in signals and re.search(r"成功|达成|得手|奏效|\b(?:success|achieved|completed)\b", outcome, re.IGNORECASE)
        if caveat or opposite:
            basis, note = "reader_signal_text_requires_review", "结构化结果与含否定、转折或范围保留的描述并存；不自动裁定终态"
        else:
            status = "completed" if signals[0] else "failed"
            basis, note = "reader_signal", None
    result = {"status": status, "statusBasis": basis}
    if note:
        result["resultNote"] = note
    if status in ("completed", "failed"):
        result["outcomeEventId"] = outcome_id
    return result


def graph_target(book: str, index: dict) -> dict:
    """本批次应当发布的**父版本**：页面默认打开的那一版。

    为什么必须这样（结构性发现 IDENT-HARDCODED-KEY，2026-10-09 实测）：
      BOOKS 里写死的键是 `9b676d70`（原文基线），而页面默认打开的是历史索引
      第一条（当时是 1063b17c）。发布工具是**纯追加式**的：它把候选合并进
      `--source-key` 指向的那一版并生成新键。于是写死旧键的后果是
      每个批次都变成页面默认版本的**兄弟分支**，而不是它的更新 ——
      读者不切版本就看不到，批次之间也**不累积**。

    判据（两级，优先级明确）：
      ① **页面真实的默认来源**：`data/cache/index.json` 里该书标题的第一条
         （`/api/history` 就是读它、并按同一顺序返回，页面据此默认打开）。
         这才是「读者实际看到哪一版」的权威。
      ② 回退 `loop/state/index.json` 的 `graphKey`（selftest 第 15 条把两者钉在一起）。
    两级都要求 .json/.docs.json 真实存在；否则回退到基线键并**在产物里标明**
    （不假装用的是默认版本 —— 静默回退正是把「发到旁支」藏起来的原因）。
    """
    BOOK_TITLES = {"dafeng": "大奉打更人", "xiyou": "西游记", "sanguo": "三国演义"}
    title = BOOK_TITLES.get(book)
    cands = []
    try:
        hist = load_json(ROOT / "data" / "cache" / "index.json")
        hist = hist if isinstance(hist, list) else (hist.get("items") or [])
        for e in hist:
            if not isinstance(e, dict):
                continue
            if title and str(e.get("display") or e.get("title") or "") == title and e.get("key"):
                cands.append(str(e["key"]))
    except Exception:
        pass
    try:
        gk = (index.get("books", {}).get(book) or {}).get("graphKey")
        if gk:
            cands.append(str(gk))
    except Exception:
        pass
    for gk in cands:
        g = ROOT / "data" / "cache" / (gk + ".json")
        d = ROOT / "data" / "cache" / (gk + ".docs.json")
        if g.exists() and d.exists():
            return {"graph": str(g.relative_to(ROOT)), "docs": str(d.relative_to(ROOT)), "key": gk}
    base = BOOKS[book]
    return {"graph": base["graph"], "docs": base["docs"],
            "key": base["graph"].split("/")[-1].replace(".json", ""),
            "_fallbackReason": "页面索引与 loop 索引都取不到可用默认键；已回退到基线键"
                               "（发布目标可能不是页面默认版本，发布前必须人工确认）"}


LAYER_MAP = {
    "tasks": "tasks", "causeEdges": "causeEdges", "clues": "clues",
    "foreshadows": "clues", "states": "characterStates", "characterStates": "characterStates",
    "relations": "relations", "storylines": "storylines",
}
SUBFIELDS = ("objective", "obstacle", "action", "result", "cost")
REF_KEYS = ("quotes", "quoteRefs", "sourceRefs", "refs", "evidence")


def load_json(p: Path):
    return json.loads(Path(p).read_text("utf-8"))


def collect_refs(item: dict, text: str, src_id: str, src_path: str, text_hash: str) -> list:
    """该条目里**能在原文逐字切出**的引用。切不出来的不算证据。

    坑（实测报错换来的）：只给 start/end/quote 不够，校验器要求每条引用都能唯一
    绑定到来源 —— 缺 `sourceId`/`sourcePath` 会整批报
    `missing_or_ambiguous_source_id`（我第一次跑就是 52 条全挂在这个上）。
    """
    raw = []
    for key in REF_KEYS:
        for r in (item.get(key) or []):
            if isinstance(r, dict):
                raw.append(r)
    def _harvest(node, depth=0):
        if depth > 3 or not isinstance(node, dict):
            return
        for key in REF_KEYS:
            for r in (node.get(key) or []):
                if isinstance(r, dict):
                    raw.append(r)
        for v in node.values():
            if isinstance(v, dict):
                _harvest(v, depth + 1)
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, dict):
                        _harvest(x, depth + 1)

    for key in list(item.keys()):
        v = item.get(key)
        if isinstance(v, dict) and key not in REF_KEYS:
            _harvest(v)
    if isinstance(item.get("quote"), str):
        raw.append(item)

    good, seen = [], set()
    for r in raw:
        q, a, b = r.get("quote"), r.get("start"), r.get("end")
        if not isinstance(q, str) or not isinstance(a, int) or not isinstance(b, int):
            continue
        if a < 0 or b > len(text) or a >= b or text[a:b] != q:
            continue
        if (a, b) in seen:
            continue
        seen.add((a, b))
        good.append({
            "sourceId": src_id, "sourcePath": src_path, "textHash": text_hash,
            "start": a, "end": b, "offsetUnit": "codepoint", "quote": q,
            "match": "exact", "status": "verified", "verified": True,
        })
    return good


def anchor_events(refs: list, events: list) -> list:
    """把引文偏移映射到**真实 eventId**：取所有「事件区间包含该偏移」的事件。

    校验器要求节点能解析到图里既有事件（`missing_or_ambiguous_event_reference`），
    光有引文偏移不够。这里用事件自带的 quoteRef.start/end 做区间包含判断 ——
    是**机械映射**，不是语义猜测；映不到就不给 eventId，让该节点落选而不是编一个。
    """
    spans = []
    for e in events:
        r = e.get("quoteRef") or {}
        a, b = r.get("start"), r.get("end")
        if isinstance(a, int) and isinstance(b, int) and a < b:
            spans.append((a, b, str(e.get("id"))))
    out = []
    for ref in refs:
        a, b = ref["start"], ref["end"]
        for sa, sb, eid in spans:
            if a < sb and sa < b:
                if eid not in out:
                    out.append(eid)
    return out


def _txt(v):
    """子字段取值：兼容 `text` 与 `value` 两种 READER 写法（D-B）。"""
    if isinstance(v, dict):
        t = v.get("text")
        return t if t is not None else v.get("value")
    return v


def char_index(graph: dict) -> dict:
    """人物名/别名 → 候选 id 集合。与校验器 `index.character()` **同一口径**：

    校验器认的是 `character` 字段能否唯一解析到图里的人物（名字或别名）。
    桥必须用同一把尺子，否则会出现「桥以为能发、校验器整批判否」的分裂 ——
    而一批被否 = 整批发不出去（B001/B002 实测如此）。
    """
    idx = {}
    for c in (graph.get("characters") or []):
        ident = str(c.get("id") or c.get("name") or "")
        for nm in [c.get("name")] + list(c.get("aliases") or []):
            if isinstance(nm, str) and nm.strip():
                idx.setdefault(nm.strip(), set()).add(ident)
    return idx


def resolve_character(item: dict, cidx: dict, keys=("who", "character", "actor")):
    """解析出**唯一**可机检的人物名；解析不出返回 None。

    为什么必须返回 None 而不是空串：校验器要求身份非空且唯一。
    空身份曾经**静默通过桥**、然后让整个批次被判否（B001 6 个 tasks、
    B002 2 个 states）——「逐步都像对的，最后整批发不出去」。
    这里如实返回 None，由调用方丢弃并记账。

    ── 第三种写法：带注解的姓名（实测占丢弃量的大头）────────────────────
    READER 常把身份写成「正名（注解）」或并列多个称呼，例如：
        李玉春（中年男人/中年人）   许新年（许二郎）   张角（太平道人 / 大贤良师）
        刘备（并关羽、张飞）        汉朝廷 / 帝         玉皇大帝 / 天庭众仙
    桥如果只做「整串精确匹配」，这些条目**全部被静默丢弃**。全语料实测：
    tasks 约 512 条 + states 约 263 条因此发布不了 —— 而它们本可发布。

    这里只做**保守的字符串规范化**，不做任何语义猜测：
      * 剥掉括号内的注解（全/半角），得到正名；
      * 按并列分隔符（·、/、与、并）切开，逐段再剥注解；
      * 把所有候选名拿去图谱里查，**只有恰好解析到同一个 id 时才接受**。
    解析到 0 个或 ≥2 个不同 id（真·多人条目）一律返回 None ——
    把多人条目硬塞给其中一人，就是身份错并（本计划明令禁止）。
    """
    for k in keys:
        v = item.get(k)
        if not isinstance(v, str) or not v.strip():
            continue
        raw = v.strip()
        if len(cidx.get(raw, ())) == 1:
            return raw
        ids = set()
        for cand in _character_candidates(raw):
            ids |= set(cidx.get(cand, ()))
            if len(ids) > 1:
                break
        if len(ids) == 1:
            only = next(iter(ids))
            for cand in _character_candidates(raw):
                if cidx.get(cand) == {only}:
                    return cand
            return raw
    return None


def _character_candidates(raw: str) -> list:
    """把一个身份串拆成**可能的单人名**候选（保守、只做字符串处理）。"""
    out = []

    def add(s: str) -> None:
        s = s.strip().strip("·、/，,;；:：").strip()
        if s and s not in out:
            out.append(s)

    add(raw)
    no_paren = re.sub(r"[（(][^）)]*[）)]", "", raw)
    add(no_paren)
    for part in re.split(r"[·、/]|与|并|↔|vs|VS", no_paren):
        add(part)
        add(re.sub(r"[（(][^）)]*[）)]", "", part))
    return out


def flat_text(parts: dict) -> str:
    out = []
    for name in SUBFIELDS:
        t = _txt(parts.get(name))
        out.append("%s：%s" % (name, t if t else "（原文未提供）"))
    return "；".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task")
    ap.add_argument("--batch")
    args = ap.parse_args()

    CAND.mkdir(parents=True, exist_ok=True)
    index = load_json(LOOP / "state" / "index.json")

    if args.task:
        targets = [args.task]
    elif args.batch:
        _, book, batch = args.batch.split(":")
        units = index["books"][book]["chapterUnits"]
        lo = int(batch[1:]) * 20
        targets = ["read:%s:L%d:%04d" % (book, u["lane"], u["i"]) for u in units[lo:lo + 20]]
    else:
        print("需要 --task 或 --batch", file=sys.stderr)
        return 2

    cache, produced, skipped = {}, [], []
    targets_info = {}
    for tid in targets:
        cand_path = OUT / (tid.replace(":", "_") + ".candidate.json")
        if not cand_path.exists():
            skipped.append({"task": tid, "reason": "候选不存在"})
            continue
        vrec_path = OUT / (("verify" + tid[4:]).replace(":", "_") + ".json")
        side_path = OUT / (("verify" + tid[4:]).replace(":", "_") + ".verdict.json")
        verdict, must_fix, src_notes = None, [], []
        for tag, path in (("record", vrec_path), ("sidecar", side_path)):
            if not path.exists():
                continue
            try:
                rec = load_json(path)
            except Exception:
                src_notes.append("%s 无法解析" % tag)
                continue
            v = rec.get("verdict") or rec.get("candidateVerdict")
            ces = [" ".join(str(ce.get(k) or "") for k in sorted(ce))
                   for ce in (rec.get("counterExamples") or []) if isinstance(ce, dict)]
            src_notes.append("%s: verdict=%s counterExamples=%d" % (tag, v, len(ces)))
            if v and verdict is None:
                verdict = v
            elif v and verdict and v != verdict:
                src_notes.append("**两处裁决不一致（%s vs %s），取更严的**" % (verdict, v))
                verdict = "fail" if "fail" in (verdict, v) else "partial"
            must_fix.extend(ces)
        must_fix = list(dict.fromkeys(must_fix))
        if src_notes:
            skipped.append({"task": tid, "reason": "复核来源：" + "；".join(src_notes)})
        if verdict == "fail":
            skipped.append({"task": tid, "reason": "复核 verdict=fail"})
            continue

        raw = load_json(cand_path)
        book = raw.get("book") or "dafeng"
        if book not in cache:
            tgt = graph_target(book, index)
            targets_info[book] = tgt
            docs = load_json(ROOT / tgt["docs"])
            graph = load_json(ROOT / tgt["graph"])
            names = {str(c.get("name") or "").strip() for c in (graph.get("characters") or [])}
            cache[book] = (docs[0]["text"], graph, names)
        tgt = targets_info.get(book) or graph_target(book, index)
        targets_info[book] = tgt
        text, graph, char_names = cache[book]
        cidx = char_index(graph)
        src = (graph.get("meta") or {}).get("sources", [{}])[0]
        src_obj = raw.get("source") or {}
        rng = src_obj.get("range")
        lo = hi = None
        if isinstance(rng, list) and len(rng) == 2 and all(isinstance(x, int) for x in rng):
            lo, hi = rng
        else:
            sel = str(src_obj.get("segmentSelector") or "")
            m_sel = re.search(r"text\[(\d+):(\d+)\]", sel)
            if m_sel:
                lo, hi = int(m_sel.group(1)), int(m_sel.group(2))
            elif isinstance(src_obj.get("start"), int) and isinstance(src_obj.get("end"), int):
                lo, hi = src_obj["start"], src_obj["end"]
        declared = [lo, hi]
        auth_lo = auth_hi = None
        try:
            uidx = raw.get("unitIndex")
            units_all = index["books"][book]["chapterUnits"]
            if isinstance(uidx, int) and 0 <= uidx < len(units_all):
                u = units_all[uidx]
                if str(u.get("lane")) == str(raw.get("lane")):
                    auth_lo, auth_hi = int(u["start"]), int(u["end"])
        except Exception:
            pass
        if auth_lo is None:
            skipped.append({"task": tid,
                            "reason": "no_authoritative_range（index 里找不到 unitIndex=%s/lane=%s 的单元；"
                                      "声明的区间=%s 不作证据）" % (raw.get("unitIndex"), raw.get("lane"),
                                                                  json.dumps(declared, ensure_ascii=False))})
            continue
        range_mismatch = None
        if lo is None:
            range_mismatch = "候选未声明区间，采用索引权威区间"
        elif [lo, hi] != [auth_lo, auth_hi]:
            range_mismatch = "候选声明 %s ≠ 索引权威 %s（以索引为准）" % (declared, [auth_lo, auth_hi])
        lo, hi = auth_lo, auth_hi
        if range_mismatch:
            skipped.append({"task": tid, "reason": "range_reconciled：" + range_mismatch})

        head = str(raw.get("unitHead") or "").strip()
        lo0, hi0 = lo, hi
        unit_events = []
        for e in (graph.get("events") or []):
            r = e.get("quoteRef") or {}
            a, b = r.get("start"), r.get("end")
            if isinstance(a, int) and isinstance(b, int) and a < hi0 and lo0 < b:
                unit_events.append(e)
        chapter_events = [str(e.get("id")) for e in unit_events]

        import re as _re
        fix_idx, fix_ids = {}, set()
        for c in must_fix:
            for m in _re.finditer(r"([A-Za-z_]+)\[(\d+)\]", c):
                fix_idx.setdefault(m.group(1), set()).add(int(m.group(2)))
            for m in _re.finditer(r"\b([TCSF]\d+)\b", c):
                fix_ids.add(m.group(1))
        if verdict == "partial" and (fix_idx or fix_ids):
            skipped.append({"task": tid, "reason": "复核 partial：排除被点名条目 索引=%s id=%s" % (
                json.dumps({k: sorted(v) for k, v in fix_idx.items()}, ensure_ascii=False),
                sorted(fix_ids))})

        layers, dropped = {}, []
        for key, payload in raw.items():
            if not isinstance(payload, list) or key not in LAYER_MAP:
                continue
            target = LAYER_MAP[key]
            layers.setdefault(target, [])
            for idx, item in enumerate(payload):
                if not isinstance(item, dict):
                    continue
                if idx in fix_idx.get(key, set()) or str(item.get("id") or "") in fix_ids:
                    dropped.append({"layer": key, "index": idx, "id": item.get("id"),
                                    "reason": "verifier_flagged（复核者点名须修正，未修正前不发布）"})
                    continue
                refs = collect_refs(item, text, src.get("id") or "",
                                    src.get("path") or "", src.get("textHash") or "")
                if not refs:
                    dropped.append({"layer": key, "id": item.get("id"),
                                    "reason": "no_verbatim_quote（引证无法在原文逐字切出，不予发布）"})
                    continue
                node = {
                    "id": stable_node_id(target, item),
                    "provenance": "assistant-reviewed-source",
                    "claimVerified": False,
                    "semanticStatus": "assistant-reviewed-source",
                    "sourceRefs": refs[:12],
                    "quote": refs[0]["quote"],
                    "basis": item.get("basis") or (item.get("objective") or {}).get("basis") or "inferred",
                    "reviewNotes": "loop READER 产出经 publish bridge 转换；语义未经人工认证。",
                }
                if key == "tasks" and not unit_events:
                    dropped.append({"layer": key, "id": item.get("id"),
                                    "reason": "unit_has_no_anchorable_event（本章图谱零事件，"
                                              "需先补事件锚点，不是精读问题）"})
                    continue
                if key == "tasks":
                    who = resolve_character(item, cidx)
                    if who is None:
                        raw_who = next((str(item.get(k)).strip() for k in ("who", "character", "actor")
                                        if isinstance(item.get(k), str) and item.get(k).strip()), "")
                        dropped.append({"layer": key, "id": item.get("id"),
                                        "reason": ("no_resolvable_character（%s）"
                                                   % ("字段=%r 不在图谱人物表或非唯一" % raw_who if raw_who
                                                      else "条目未声明身份（叙述者/群体状态不能充当某人的任务）"))})
                        continue
                node_events = anchor_events(refs, unit_events)
                if key == "causeEdges":
                    if len(node_events) >= 2:
                        node["fromEventId"], node["toEventId"] = node_events[0], node_events[-1]
                    else:
                        dropped.append({"layer": key, "id": item.get("id"),
                                        "reason": "no_two_distinct_events（因果边两端无法锚定到不同真实事件）"})
                        continue
                else:
                    ev = node_events or chapter_events
                    if ev:
                        node["eventIds"] = ev[:12]
                if key == "tasks":
                    def _t(name):
                        v = item.get(name)
                        if isinstance(v, dict):
                            t = v.get("text")
                            if t is None:
                                t = v.get("value")
                            return t or None
                        return v or None
                    fields = {k: _t(k) for k in ("objective", "obstacle", "action", "result", "cost")}
                    if not any(fields.values()):
                        dropped.append({"layer": key, "id": item.get("id"),
                                        "reason": "empty_task_shell（objective/obstacle/action/result/cost "
                                                  "全空：桥没搬到内容，不是语义未核验）"})
                        continue
                    node.update({
                        "name": item.get("summary") or item.get("name") or "（未命名任务）",
                        "character": who,
                        "goal": fields["objective"], "obstacle": fields["obstacle"],
                        "action": fields["action"], "outcome": fields["result"], "cost": fields["cost"],
                    })
                    node.update(task_result_status(item, fields["result"] or "", node.get("eventIds") or []))
                elif key == "causeEdges":
                    node.update({"description": item.get("mechanism") or "",
                                 "fromText": item.get("from") or "", "toText": item.get("to") or ""})
                elif key in ("states", "characterStates"):
                    b, a = item.get("before"), item.get("after")
                    st_events = anchor_events(refs, unit_events)
                    if not st_events:
                        dropped.append({"layer": key, "id": item.get("id"),
                                        "reason": "no_anchored_event（状态变化锚不到真实事件，无法机检）"})
                        continue
                    who = resolve_character(item, cidx)
                    if who is None:
                        raw_who = next((str(item.get(k)).strip() for k in ("who", "character", "actor", "subject")
                                        if isinstance(item.get(k), str) and item.get(k).strip()), "")
                        dropped.append({"layer": key, "id": item.get("id"),
                                        "reason": ("no_resolvable_character（%s）"
                                                   % ("字段=%r 不在图谱人物表或非唯一" % raw_who if raw_who
                                                      else "状态变化未声明可解析的人物"))})
                        continue
                    node.update({
                        "eventId": st_events[0],
                        "character": who,
                        "attribute": item.get("attribute") or item.get("dimension") or "",
                        "before": _txt(b), "after": _txt(a),
                    })
                elif target == "clues":
                    seed_ev = anchor_events(refs, unit_events)
                    if not seed_ev:
                        dropped.append({"layer": key, "id": item.get("id"),
                                        "reason": "no_anchored_event（伏笔锚不到真实事件，无法机检）"})
                        continue
                    node["seedEventId"] = seed_ev[0]
                    node["seedQuote"] = refs[0]["quote"]
                    node["status"] = "unresolved"
                    setup = item.get("setup")
                    setup_text = setup.get("text") if isinstance(setup, dict) else setup
                    node["description"] = "%s：%s" % (item.get("name") or "", setup_text or "（未提供）")
                else:
                    node.update({k: v for k, v in item.items() if k not in ("id",) + REF_KEYS})
                layers[target].append(node)
        layers = {k: v for k, v in layers.items() if v}

        scope = {
            "name": head or tid,
            "sourceId": src.get("id") or "",
            "textHash": src.get("textHash") or "",
            "start": lo, "end": hi, "offsetUnit": "codepoint",
            "chapters": [head],
            "eventIds": chapter_events[:20],
            "method": "loop_reader_verified_by_independent_agent",
            "verdict": verdict or "unverified",
        }
        cand = {
            "schemaVersion": "reviewed-candidate/1",
            "sourceKey": tgt["key"],
            "publishTargetNote": ("父版本取自 loop/state/index.json 的 graphKey；"
                                  + ("（回退：%s）" % tgt["_fallbackReason"] if tgt.get("_fallbackReason") else "")),
            "provenance": "assistant-reviewed-source",
            "modelCalls": 0, "automaticModelCalls": 0,
            "scope": scope, "replaceLayers": [], "layers": layers,
            "coverageGaps": [
                {"kind": "range_scoped_review",
                 "description": "只审了 scope 声明的原文区间 [%d,%d)；区间外未审。" % (lo, hi)},
                {"kind": "semantic_review_not_performed",
                 "description": "引用定位与身份合同由工具机检；语义正确性未经人工认证。"},
            ] + [{"kind": "dropped_item", "description": json.dumps(d, ensure_ascii=False)} for d in dropped],
            "_bridge": {"from": str(cand_path.relative_to(ROOT)),
                        "kept": sum(len(v) for v in layers.values()), "dropped": len(dropped)},
        }
        out = CAND / (tid.replace(":", "_") + ".candidate.json")
        out.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", "utf-8")
        produced.append({"task": tid, "out": str(out.relative_to(ROOT)),
                         "kept": cand["_bridge"]["kept"], "dropped": cand["_bridge"]["dropped"],
                         "verdict": verdict or "unverified"})

    # ---- 批次合并 ----------------------------------------------------------
    merged_path = None
    if args.batch:
        import hashlib as _hl
        layers_m, allgaps = {}, []
        seen_ids = set()
        for item in produced:
            c = load_json(Path(item["out"]))
            for k, v in (c.get("layers") or {}).items():
                for node in v:
                    if node.get("id") in seen_ids:
                        continue
                    seen_ids.add(node.get("id"))
                    layers_m.setdefault(k, []).append(node)
            for g in (c.get("coverageGaps") or []):
                if g.get("kind") == "dropped_item":
                    allgaps.append(g)
        _, _book, _batch = args.batch.split(":")
        _units = index["books"][_book]["chapterUnits"]
        _lo = int(_batch[1:]) * 20
        _slice = _units[_lo:_lo + 20]
        if not _slice:
            print("批次 %s 超出索引范围（共 %d 单元）" % (args.batch, len(_units)), file=sys.stderr)
            return 2
        scope_m = {
            "name": "%s（%s）" % (_slice[0]["head"], args.batch),
            "start": int(_slice[0]["start"]),
            "end": int(_slice[-1]["end"]),
            "chapters": [u["head"] for u in _slice],
            "eventIds": list(dict.fromkeys(
                eid for item in produced
                for eid in ((load_json(Path(item["out"])).get("scope") or {}).get("eventIds") or [])))[:200],
            "sourceKey": _book,
            "parentKey": (targets_info.get(_book) or graph_target(_book, index))["key"],
            "units": len(_slice),
            "unitsWithNodes": len(produced),
            "rangeAuthority": "loop/state/index.json chapterUnits[%d:%d]" % (_lo, _lo + 20),
        }
        digest = _hl.sha256(json.dumps(sorted(seen_ids), ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
        _merged_target = (targets_info.get(_book) or graph_target(_book, index))["key"]
        merged = {
            "schemaVersion": "reviewed-candidate/1",
            "sourceKey": _merged_target,
            "provenance": "assistant-reviewed-source",
            "modelCalls": 0, "automaticModelCalls": 0,
            "scope": scope_m, "replaceLayers": [], "layers": layers_m,
            "coverageGaps": [
                {"kind": "range_scoped_review",
                 "description": "只审了 scope 声明的原文区间 [%d,%d)；区间外未审。" % (scope_m["start"], scope_m["end"])},
                {"kind": "semantic_review_not_performed",
                 "description": "引用定位与身份合同由工具机检；语义正确性未经人工认证。"},
            ] + allgaps,
            "_bridge": {"batch": args.batch, "units": len(_slice), "unitsWithNodes": len(produced),
                        "kept": sum(len(v) for v in layers_m.values()),
                        "dropped": sum(p["dropped"] for p in produced), "digest": digest},
        }
        merged_path = CAND / ("BATCH-%s.candidate.json" % args.batch.replace(":", "-"))
        merged_path.write_text(json.dumps(merged, ensure_ascii=False, indent=1) + "\n", "utf-8")

    print(json.dumps({"produced": produced, "skipped": skipped,
                      "batch": str(merged_path.relative_to(ROOT)) if merged_path else None},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
