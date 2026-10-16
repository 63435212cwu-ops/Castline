#!/usr/bin/env python3
"""P03-W06/W07 故事线「机械等分」量化诊断。

审核点名的大奉缺陷原文：
  「大奉 904 章中深层语义目前仅覆盖开篇 6 章，8 条全书线仍是机械分段。」
  「8 条全书线为机械等分」

本脚本不"感觉"是不是机械等分，而是把它变成可复算的数字：

  ① 等距性      每个 storyline 的 attach_order 步长序列是否恒定
                 —— 判据：步长唯一值数 == 1（完全等距）、步长方差、变异系数 CV。
  ② 覆盖完整性  windows 是否恰好无缝铺满 [1, N] 且互不重叠（等分切片的最强指纹：
                 真实剧情线必然共享事件、或留下无归属区间，不会既不重叠又全覆盖）。
  ③ 边界对齐    attach_order 是否落在真实章节边界 / 卷边界上。
                 —— 判据：该 order 的事件与前一事件是否同章；是否与作者自述的卷结尾同章。
                 这一条是"禁止以时间相邻替代因果"的直接检验：等分点若落在章中间，
                 说明它不是剧情理解的产物。
  ④ 换手理由    handoff_reason 是否只是"时间顺序承接上一阶段"（时间相邻冒充叙事承接）。
  ⑤ cast 来源   cast 是否等于 windows 内事件人物的真实聚合（一致性检验）。
  ⑥ 锚点率     sourceRefs 有效锚点数（match==exact 且 quote 是原文子串且 textHash 相符）。

输出 artifacts/plan100/narrative/storyline-diagnosis.json。
**绝不为让数字好看而调参**：等分就是等分，如实报。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter
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

TEMPORAL_HANDOFF = [
    "时间顺序承接", "时间顺序", "承接上一阶段", "顺序承接", "上一阶段",
    "按时间", "时间线", "紧随其后", "时间上",
]
VOLUME_END_RE = re.compile(
    r"本卷终|卷尾总结|卷尾感言|卷尾总结兼请假|(第[一二三四五六七八九十]+卷[^。\n]{0,6}结束)"
)


def norm(s: str) -> str:
    return re.sub(r"[\s\u3000]+", "", s or "")


def load_text(path: Path) -> str:
    return json.loads(path.read_text(encoding="utf-8"))[0]["text"]


def load_chapters(book_key: str, text: str) -> tuple[list[dict], dict]:
    """优先用 P02 的 source-index；未就绪时回落到 evidence_audit.build_chapter_index。

    返回 (chapters, provenance)。
    """
    p = SOURCE_INDEX / f"{book_key}.json"
    if p.exists():
        try:
            idx = json.loads(p.read_text(encoding="utf-8"))
            chs = idx.get("chapters") or []
            if chs:
                return ([{"heading": c.get("heading") or c.get("label") or "",
                          "start": c["start"]} for c in chs],
                        {"source": "artifacts/plan100/source-index", "path": str(p.relative_to(ROOT)),
                         "note": "P02 共享接口"})
        except Exception as exc:
            print(f"  ! source-index {p.name} 读取失败({exc})，回落 build_chapter_index", file=sys.stderr)
    chs = build_chapter_index(text)
    return ([{"heading": c["heading"], "start": c["start"]} for c in chs],
            {"source": "tools/plan100/evidence_audit.py::build_chapter_index",
             "path": "tools/plan100/evidence_audit.py",
             "note": "P02 source-index 未就绪时的回落实现；已解决全角空格/抓取站导航垃圾/重号章三个坑"})


def audit_anchor(ref: dict, text: str, text_hash: str) -> str:
    """锚点定位结果。与 evidence_audit 同一口径。"""
    quote = ref.get("quote") or ""
    start, end = ref.get("start"), ref.get("end")
    if ref.get("textHash") and text_hash and ref["textHash"] != text_hash:
        return "hash_mismatch"
    if not (isinstance(start, int) and isinstance(end, int)):
        return {"ambiguous": "ambiguous", "normalized": "normalized", "none": "not_found"}.get(
            ref.get("match") or ref.get("status") or "", "no_offset")
    if not (0 <= start <= end <= len(text)):
        return "missing"
    actual = text[start:end]
    if actual == quote:
        return "exact"
    if norm(actual) == norm(quote):
        return "normalized"
    lo = max(0, start - 200)
    idx = text.find(quote, lo, min(len(text), end + 200)) if quote else -1
    return "fuzzy" if idx >= 0 else "unmatched"


def find_volume_ends(text: str, chapters: list[dict]) -> list[dict]:
    """从正文抽取作者自述的卷尾位置（真实卷边界证据，不是插值）。"""
    out = []
    for m in VOLUME_END_RE.finditer(text):
        off = m.start()
        loc = locate(chapters, off)
        out.append({"offset": off, "quote": text[max(0, off - 12):off + len(m.group(0)) + 12],
                    "marker": m.group(0),
                    "chapter": loc["heading"] if loc else None})
    seen, uniq = set(), []
    for v in out:
        key = (v["chapter"], v["marker"][:6])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(v)
    return uniq


def locate(chapters: list[dict], offset: int) -> dict | None:
    lo, hi, found = 0, len(chapters) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if chapters[mid]["start"] <= offset:
            found = chapters[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return found


def cv(steps: list[int]) -> float | None:
    if len(steps) < 2:
        return None
    mean = sum(steps) / len(steps)
    if mean == 0:
        return 0.0
    var = sum((s - mean) ** 2 for s in steps) / len(steps)
    return math.sqrt(var) / mean


def diagnose(book_key: str, title: str) -> dict:
    graph = json.loads((ROOT / "data" / "cache" / f"{book_key}.json").read_text(encoding="utf-8"))
    text = load_text(ROOT / "data" / "cache" / f"{book_key}.docs.json")
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    declared_hash = ((graph.get("meta") or {}).get("sources") or [{}])[0].get("textHash")
    chapters, chap_prov = load_chapters(book_key, text)

    events = [e for e in graph.get("events") or [] if isinstance(e, dict)]
    by_id = {e["id"]: e for e in events}
    by_order = {e.get("order"): e for e in events}
    n_events = len(events)
    source_id = ((graph.get("meta") or {}).get("sources") or [{}])[0].get("id")
    source_path = ((graph.get("meta") or {}).get("sources") or [{}])[0].get("path")

    lines = [s for s in graph.get("storylines") or [] if isinstance(s, dict)]

    chapter_counts = {
        "extracted": len(chapters),
        "eventLabels": len({e.get("chapter") for e in events if e.get("chapter")}),
        "declared": (graph.get("meta", {}).get("index") or {}).get("chapters"),
    }
    per_line: list[dict] = []
    for s in lines:
        ev_ids = s.get("eventIds") or []
        orders = sorted(int(by_id[i]["order"]) for i in ev_ids
                        if i in by_id and isinstance(by_id[i].get("order"), int))
        window = ([orders[0], orders[-1]] if orders else None)
        gaps = len(orders) - (orders[-1] - orders[0] + 1) if orders else 0

        steps = [window[1] - window[0]] if window else []

        first = by_order.get(window[0]) if window else None
        last = by_order.get(window[1]) if window else None
        prev_ev = by_order.get(window[0] - 1) if window and window[0] > 1 else None
        next_ev = by_order.get(window[1] + 1) if window and window[1] < n_events else None

        def chap_head(e):
            return (e or {}).get("chapter")
        start_at_chapter_head = bool(first) and (prev_ev is None or chap_head(first) != chap_head(prev_ev))
        end_at_chapter_tail = bool(last) and (next_ev is None or chap_head(last) != chap_head(next_ev))

        hr = s.get("handoff_reason") or ""
        temporal_only = bool(hr) and any(t in hr for t in TEMPORAL_HANDOFF)

        cnt: Counter[str] = Counter()
        for i in ev_ids:
            e = by_id.get(i)
            if not e:
                continue
            for c in e.get("characters") or []:
                cnt[c] += 1
        cast = [c for c in (s.get("cast") or [])]
        cast_missing_from_window = [c for c in cast if c not in cnt]

        refs = s.get("sourceRefs") or []
        refs = refs if isinstance(refs, list) else [refs]
        matches = [audit_anchor(r, text, text_hash) for r in refs if isinstance(r, dict)]

        per_line.append({
            "storylineId": s.get("id") or s.get("entityId"),
            "name": s.get("name") or "",
            "kind": s.get("kind") or "",
            "lead": s.get("lead") or "",
            "attachOrder": s.get("attach_order"),
            "window": window,
            "eventCount": len(orders),
            "windowSpanGaps": gaps,
            "isContiguousWindow": gaps == 0 and bool(orders),
            "startsAtChapterHead": start_at_chapter_head,
            "endsAtChapterTail": end_at_chapter_tail,
            "startChapter": chap_head(first),
            "endChapter": chap_head(last),
            "previousEventChapter": chap_head(prev_ev),
            "nextEventChapter": chap_head(next_ev),
            "handoffFrom": s.get("handoff_from") or "",
            "handoffReason": hr,
            "handoffIsTemporalOnly": temporal_only,
            "castSize": len(cast),
            "castMissingFromWindow": cast_missing_from_window,
            "castDerivableFromWindow": not cast_missing_from_window,
            "resolution": s.get("resolution") or "",
            "resolved": bool(s.get("resolved")),
            "sourceRefCount": len(refs),
            "anchorMatches": dict(Counter(matches)),
            "hasExactAnchor": matches.count("exact") > 0,
            "theme": s.get("theme") or "",
            "goal": s.get("goal") or "",
        })

    ordered = sorted([p for p in per_line if isinstance(p.get("attachOrder"), int)],
                     key=lambda p: p["attachOrder"])
    attach = [p["attachOrder"] for p in ordered]
    gaps_between = [attach[i + 1] - attach[i] for i in range(len(attach) - 1)]

    spans = sorted([tuple(p["window"]) for p in per_line if p["window"]], key=lambda t: t[0])
    tiling = bool(spans) and spans[0][0] == 1 and spans[-1][1] == n_events
    for a, b in zip(spans, spans[1:]):
        if b[0] != a[1] + 1:
            tiling = False
            break
    covered = sum(b - a + 1 for a, b in spans)
    overlaps = covered - len(set().union(*[set(range(a, b + 1)) for a, b in spans])) if spans else 0

    vol_ends = find_volume_ends(text, chapters)
    vol_end_chapters = {v["chapter"] for v in vol_ends}
    boundary_hits = []
    for p in ordered[:-1]:
        w = p.get("window")
        if not w:
            continue
        nxt = by_order.get(w[1] + 1)
        boundary_hits.append({
            "afterStoryline": p["storylineId"],
            "attachOrder": p["attachOrder"],
            "nextChapter": (nxt or {}).get("chapter"),
            "endsAtChapterTail": p["endsAtChapterTail"],
            "coincidesWithVolumeEnd": (nxt or {}).get("chapter") in vol_end_chapters,
        })

    total_lines = len(per_line)
    anchored = sum(1 for p in per_line if p["hasExactAnchor"])
    summary = {
        "bookKey": book_key,
        "title": title,
        "events": n_events,
        "chaptersExtracted": len(chapters),
        "chaptersDeclared": chapter_counts["declared"] or chapter_counts["eventLabels"],
        "chapterCounts": chapter_counts,
        "chapterCountGap": chapter_counts["extracted"] - chapter_counts["eventLabels"],
        "chapterIndexProvenance": chap_prov,
        "textHashMatchesMeta": (declared_hash == text_hash) if declared_hash else None,
        "storylines": total_lines,
        "attachOrders": attach,
        "attachStepSizes": gaps_between,
        "attachStepDistinct": len(set(gaps_between)),
        "attachStepMean": (sum(gaps_between) / len(gaps_between)) if gaps_between else None,
        "attachStepVariance": (
            sum((g - sum(gaps_between) / len(gaps_between)) ** 2 for g in gaps_between) / len(gaps_between)
            if gaps_between else None),
        "attachStepCV": cv(gaps_between),
        "windowSizes": [p["eventCount"] for p in ordered],
        "windowsAreContiguous": all(p["isContiguousWindow"] for p in per_line),
        "windowsTileAllEvents": tiling,
        "windowCoverage": round(covered / n_events, 4) if n_events else None,
        "windowOverlapEvents": overlaps,
        "boundariesAtChapterTail": sum(1 for b in boundary_hits if b["endsAtChapterTail"]),
        "boundariesCoincidingWithVolumeEnd": sum(1 for b in boundary_hits if b["coincidesWithVolumeEnd"]),
        "boundaryCount": len(boundary_hits),
        "storylinesWithExactAnchor": anchored,
        "anchorRate": round(anchored / total_lines, 4) if total_lines else None,        "storylinesWithNonTemporalHandoffReason": sum(
            1 for p in per_line if p["handoffReason"] and not p["handoffIsTemporalOnly"]),
        "storylinesWithTemporalOnlyHandoffReason": sum(p["handoffIsTemporalOnly"] for p in per_line),
        "storylinesWithCastDerivableFromWindow": sum(p["castDerivableFromWindow"] for p in per_line),
        "resolvedTrueCount": sum(1 for p in per_line if p["resolved"]),
    }

    equal_steps = summary["attachStepDistinct"] <= 1 and len(gaps_between) >= 2
    same_size = len(set(summary["windowSizes"])) <= 2 and total_lines >= 4
    verdict_reasons = []
    if equal_steps:
        verdict_reasons.append(f"attach_order 步长完全等距（唯一步长 {set(gaps_between)}）")
    if same_size:
        verdict_reasons.append(f"窗口大小几乎一致 {sorted(set(summary['windowSizes']))}")
    if tiling and not overlaps:
        verdict_reasons.append(f"{total_lines} 条线无缝铺满全部 {n_events} 个事件且两两不重叠")
    if summary["boundariesAtChapterTail"] == 0 and summary["boundaryCount"]:
        verdict_reasons.append("全部 %d 个边界都不在章节收束处" % summary["boundaryCount"])
    if summary["storylinesWithExactAnchor"] == 0:
        verdict_reasons.append("sourceRefs 有效锚点数为 0")
    mechanical = bool(verdict_reasons) and equal_steps and (same_size or tiling)

    return {
        "bookKey": book_key,
        "title": title,
        "summary": summary,
        "verdict": "mechanical_equal_split" if mechanical else "evidence_bounded",
        "verdictReasons": verdict_reasons,
        "volumeEndEvidence": vol_ends[:20],
        "volumeEndChapters": sorted(v for v in vol_end_chapters if v),
        "temporalHandoffPatterns": TEMPORAL_HANDOFF,
        "boundaries": boundary_hits,
        "storylineDetails": per_line,
        "sourceId": source_id,
        "sourcePath": source_path,
        "notes": [
            "等距性判据只看 attach_order 步长，不做任何平滑或剔除。",
            "『边界在章节收束处』是必要条件而非充分条件：真实剧情线边界也可能落在章中间，"
            "但全部边界同时落在章中间且步长恒定，只能是按事件数切分。",
            "cast 一致性检验只判断 cast 是否为窗口内事件人物的子集，不评价 cast 选择是否合理。",
        ],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    reports = []
    for key, title in BOOKS:
        rep = diagnose(key, title)
        reports.append(rep)
        s = rep["summary"]
        print(f"\n=== {title} ({key}) ===")
        print(f"  事件 {s['events']} · 章节 {s['chaptersExtracted']}（声明 {s['chaptersDeclared']}）")
        print(f"  attach_order 步长 {s['attachStepSizes']} · 唯一值 {s['attachStepDistinct']} "
              f"· CV {'n/a' if s['attachStepCV'] is None else round(s['attachStepCV'], 4)}")
        print(f"  窗口大小 {s['windowSizes']} · 连续窗口={s['windowsAreContiguous']} "
              f"· 铺满全书={s['windowsTileAllEvents']} · 重叠事件={s['windowOverlapEvents']}")
        print(f"  边界落在章节收束处 {s['boundariesAtChapterTail']}/{s['boundaryCount']} "
              f"· 与卷尾同章 {s['boundariesCoincidingWithVolumeEnd']}")
        print(f"  有效锚点 {s['storylinesWithExactAnchor']}/{s['storylines']} "
              f"({0 if s['anchorRate'] is None else round(s['anchorRate']*100,1)}%)")
        print(f"  换手理由仅时间相邻 {s['storylinesWithTemporalOnlyHandoffReason']}")
        print(f"  判决: {rep['verdict']}")
        for r in rep["verdictReasons"]:
            print(f"    · {r}")
    (OUT / "storyline-diagnosis.json").write_text(
        json.dumps({"generatedBy": "tools/plan100/storyline_diagnosis.py",
                    "chapterIndexProvenance": reports[0]["summary"]["chapterIndexProvenance"],
                    "books": reports}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"\n-> {artifact_rel(OUT / 'storyline-diagnosis.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
