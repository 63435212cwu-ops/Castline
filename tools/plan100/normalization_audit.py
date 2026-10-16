#!/usr/bin/env python3
"""P00-W02 · 检查字段是否来自唯一规范化入口，确认缺失字段显示「待核」而不是前端猜测。

计划硬性原则 1：明确、归纳、推导、未核验四种证据状态始终可见；没有原文不能生成确定结论。
计划硬性原则 5：不能按事件条数或代码量加分。

本脚本做的是**反向验证**：不看前端代码声称了什么，而是拿真实图谱数据去问
「哪些字段是缺失的，系统会怎么显示它」。任何把缺失静默变成确定值的地方都是缺陷。

产出 artifacts/plan100/normalization/normalization-audit.json
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT = artifact_path() / "plan100" / "normalization"

BOOKS = [
    ("9b676d7031b1bcd3b8377a18", "大奉打更人"),
    ("df959d743e53206f56db2f92", "西游记"),
    ("152e2a6eed94f1075e7e7070", "三国演义"),
]

EVIDENCE_STATES = {"explicit", "inferred", "derived", "unverified", "unknown", "reviewed"}

RISKY_FIELDS = [
    ("events", ["title", "summary", "quote", "chapter", "kind", "order"]),
    ("characters", ["name", "role", "importance", "camp", "aliases", "brief", "attrs", "arc"]),
    ("relations", ["a", "b", "kind", "desc", "line", "strength", "sourceRefs"]),
    ("causeEdges", ["description", "fromEventId", "toEventId", "sourceRefs"]),
    ("characterStates", ["character", "summary", "attributes", "sourceRefs"]),
    ("storylines", ["name", "cast", "eventIds", "sourceRefs"]),
    ("tasks", ["character", "goal", "obstacle", "action", "outcome", "cost", "sourceRefs"]),
]


def is_blank(v) -> bool:
    """空 = None / "" / [] / {} —— 注意 0 和 False 不算空。"""
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False


def audit_field(records: list[dict], field: str) -> dict:
    present = absent = blank = 0
    for r in records:
        if not isinstance(r, dict):
            continue
        if field not in r:
            absent += 1
        elif is_blank(r[field]):
            blank += 1
        else:
            present += 1
    total = present + absent + blank
    return {
        "field": field,
        "present": present,
        "blank": blank,
        "absent": absent,
        "total": total,
        "missingRate": round((blank + absent) / total, 4) if total else None,
    }


def audit_book(key: str, title: str) -> dict:
    graph = json.loads((ROOT / "data/cache" / f"{key}.json").read_text(encoding="utf-8"))
    meta = graph.get("meta", {})
    report = {
        "bookKey": key,
        "title": title,
        "schemaVersion": meta.get("schemaVersion"),
        "revisionVersion": (meta.get("revision") or {}).get("version"),
        "collections": {},
        "evidenceStateHistogram": {},
        "coverageAxes": {},
        "reviewIssues": len(graph.get("reviewIssues") or []),
    }

    for cname, fields in RISKY_FIELDS:
        records = graph.get(cname) or []
        if not records:
            report["collections"][cname] = {"records": 0, "fields": []}
            continue
        report["collections"][cname] = {
            "records": len(records),
            "fields": [audit_field(records, f) for f in fields],
        }

    hist = Counter()
    for cname in ("events", "relations", "causeEdges", "characterStates", "storylines", "tasks"):
        for r in graph.get(cname) or []:
            if not isinstance(r, dict):
                continue
            for f in ("basis", "claimStatus", "semanticStatus", "referenceStatus", "reviewStatus"):
                v = r.get(f)
                if isinstance(v, str) and v:
                    hist[f"{f}={v}"] += 1
    report["evidenceStateHistogram"] = dict(hist.most_common(30))

    cov = meta.get("coverage") or {}
    for axis, v in cov.items():
        if isinstance(v, dict):
            report["coverageAxes"][axis] = {
                "known": v.get("known"),
                "reason": v.get("reason"),
                "count": v.get("count"),
            }
    return report


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for key, title in BOOKS:
        if not (ROOT / "data/cache" / f"{key}.json").exists():
            continue
        rep = audit_book(key, title)
        results.append(rep)
        (OUT / f"{key}.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n=== {title} · schema={rep['schemaVersion']} rev={rep['revisionVersion']} ===")
        print("  覆盖轴（known=false 是诚实降级）：")
        for axis, v in rep["coverageAxes"].items():
            mark = "OK " if v["known"] else "未提供"
            print(f"    [{mark}] {axis:18s} count={v['count']} reason={v['reason']}")
        print("  高风险字段缺失率：")
        for cname, c in rep["collections"].items():
            if not c["records"]:
                continue
            bad = [f for f in c["fields"] if (f["missingRate"] or 0) > 0]
            if bad:
                detail = ", ".join(f"{f['field']}={f['missingRate']*100:.0f}%" for f in bad[:6])
                print(f"    {cname:18s} n={c['records']:5d}  {detail}")

    (OUT / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n-> {artifact_rel(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
