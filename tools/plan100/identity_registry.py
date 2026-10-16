#!/usr/bin/env python3
"""P00-W03 · 稳定 ID 注册表 + 别名冲突/孤立节点台账。

计划要求：「为章节、事件、人物、故事线和证据建立稳定ID，并记录别名冲突与孤立节点」。

硬性约束（计划第五节 A）：
  「角色别名归并遇到冲突进入待审队列；**不得以角色名字符串相等作为唯一身份依据**」
  「同场不能自动生成师徒、盟友或敌对」

本脚本只做**登记与检测**，不做归并决策：冲突一律进 reviewQueue，由人（或下游
带原文证据的流程）裁决。任何自动归并都会违反上述约束。

产出 artifacts/plan100/identity/<bookKey>.json 与 registry-summary.json
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT = artifact_path() / "plan100" / "identity"

BOOKS = [
    ("9b676d7031b1bcd3b8377a18", "大奉打更人"),
    ("df959d743e53206f56db2f92", "西游记"),
    ("152e2a6eed94f1075e7e7070", "三国演义"),
]

ID_NAMESPACES = {
    "character": "ch_",
    "event": "ev_",
    "relation": "rel_",
    "cause": "cause_",
    "state": "state_",
    "task": "task_",
    "issue": "issue_",
    "storyline": "sl_",
    "review": "entity-review_",
    "reviewEvent": "event-review_",
}

HONORIFIC_HINT = re.compile(
    r"^(丞相|太傅|主公|陛下|万岁|大王|将军|都督|太守|刺史|司徒|司空|尚书|侍郎|"
    r"菩萨|长老|师父|师兄|师弟|陛下|殿下|娘娘|贵妃|公主|太子|皇帝|道长|真人|"
    r"大人|老爷|公子|先生|夫人|老太太|太后|第[一二三四五六七八九十]+|.*号$)"
)


def collect_ids(records: list[dict]) -> list[str]:
    """收集稳定 ID。

    坑：每条记录同时有 `id` 和 `entityId`，两条**值完全相同**。早期版本把它们
    都收进来，导致每个 ID 都被判成「重复 2 次」，产出上千条假告警。
    这里按记录取**一个** ID（优先 id，回退 entityId）。
    """
    out = []
    for r in records:
        if not isinstance(r, dict):
            continue
        for k in ("id", "entityId"):
            v = r.get(k)
            if isinstance(v, str) and v:
                out.append(v)
                break
    return out


def audit_book(key: str, title: str) -> dict:
    graph = json.loads((ROOT / "data/cache" / f"{key}.json").read_text(encoding="utf-8"))

    report = {
        "bookKey": key,
        "title": title,
        "idNamespaces": ID_NAMESPACES,
        "collections": {},
        "aliasConflicts": [],
        "aliasShadowsCanonical": [],
        "isolatedNodes": {},
        "reviewQueue": [],
    }

    # ---- 1. ID 唯一性与稳定性
    for cname in ("characters", "events", "relations", "causeEdges",
                  "characterStates", "storylines", "tasks", "reviewIssues", "camps"):
        recs = graph.get(cname) or []
        if not isinstance(recs, list):
            continue
        ids = collect_ids(recs)
        ids = [i for i in ids if not i.startswith("auto-")]
        counter = Counter(ids)
        dup = {k: v for k, v in counter.items() if v > 1}
        bad_prefix = sorted({i.split("_")[0] + "_" for i in ids
                             if not any(i.startswith(p) for p in ID_NAMESPACES.values())})
        report["collections"][cname] = {
            "records": len(recs),
            "withId": len(ids),
            "uniqueIds": len(counter),
            "duplicateIds": dup,
            "prefixesSeen": dict(Counter(i.split("_")[0] + "_" for i in ids).most_common()),
            "unexpectedPrefixes": bad_prefix,
        }

    # ---- 2. 别名冲突（跨角色共用同一别名）
    chars = graph.get("characters") or []
    alias_owners: dict[str, set[str]] = defaultdict(set)
    name_owners: dict[str, str] = {}
    for c in chars:
        name = c.get("name")
        if name:
            name_owners[name] = c.get("id") or c.get("entityId")
        for a in c.get("aliases") or []:
            if isinstance(a, str) and a.strip():
                alias_owners[a.strip()].add(name)

    for alias, owners in sorted(alias_owners.items()):
        if len(owners) > 1:
            report["aliasConflicts"].append({
                "alias": alias,
                "owners": sorted(owners),
                "ownerCount": len(owners),
                "classification": "honorific-ambiguous" if HONORIFIC_HINT.match(alias) else "identity-conflict",
                "autoMerge": False,
                "note": "不得自动归并；需原文证据裁决" if not HONORIFIC_HINT.match(alias)
                        else "职务/尊称泛用，不作为身份依据",
            })

    # ---- 3. 别名遮蔽他角色主名（更危险：会把 A 的别名当成 B 本人）
    for c in chars:
        name = c.get("name")
        for a in c.get("aliases") or []:
            a = (a or "").strip()
            if a and a in name_owners and a != name:
                report["aliasShadowsCanonical"].append({
                    "alias": a,
                    "aliasOwner": name,
                    "shadowedCanonical": a,
                    "canonicalId": name_owners[a],
                    "severity": "high",
                    "note": "该别名与另一角色主名逐字相同，字符串相等不能作为身份依据",
                })

    # ---- 4. 孤立节点
    ev_ids = {e.get("id") or e.get("entityId") for e in graph.get("events") or []}
    ev_ids.discard(None)

    referenced: set[str] = set()
    for c in graph.get("causeEdges") or []:
        for k in ("fromEventId", "toEventId"):
            if c.get(k):
                referenced.add(c[k])
    for s in graph.get("storylines") or []:
        referenced.update(s.get("eventIds") or [])
    for t in graph.get("tasks") or []:
        referenced.update(t.get("eventIds") or [])

    orphan_events = sorted(ev_ids - referenced)
    dangling = sorted(referenced - ev_ids)

    ch_names = {c.get("name") for c in chars}
    ch_in_events: set[str] = set()
    for e in graph.get("events") or []:
        for n in e.get("characters") or []:
            ch_in_events.add(n)
    orphan_chars = sorted(n for n in ch_names if n and n not in ch_in_events)
    unknown_in_events = sorted(n for n in ch_in_events if n and n not in ch_names)

    report["isolatedNodes"] = {
        "events": {"total": len(ev_ids), "referenced": len(ev_ids & referenced),
                   "orphan": len(orphan_events), "orphanSample": orphan_events[:10]},
        "danglingEventRefs": {"count": len(dangling), "sample": dangling[:10]},
        "characters": {"total": len(ch_names), "appearingInEvents": len(ch_in_events),
                       "orphan": len(orphan_chars), "orphanSample": orphan_chars[:10]},
        "unknownSpeakersInEvents": {"count": len(unknown_in_events),
                                    "sample": unknown_in_events[:10]},
    }

    # ---- 5. 待审队列（合并已有 reviewIssues）
    for issue in graph.get("reviewIssues") or []:
        report["reviewQueue"].append({
            "source": "graph.reviewIssues",
            "id": issue.get("id"),
            "kind": issue.get("kind"),
            "identityStatus": issue.get("identityStatus"),
            "description": (issue.get("description") or "")[:240],
            "claimVerified": issue.get("claimVerified"),
        })
    for c in report["aliasConflicts"]:
        if c["classification"] == "identity-conflict":
            report["reviewQueue"].append({
                "source": "alias-audit",
                "kind": "identity",
                "alias": c["alias"],
                "owners": c["owners"],
                "autoMerge": False,
            })
    for s in report["aliasShadowsCanonical"]:
        report["reviewQueue"].append({
            "source": "alias-shadow-audit",
            "kind": "identity",
            "alias": s["alias"],
            "aliasOwner": s["aliasOwner"],
            "severity": "high",
            "autoMerge": False,
        })

    report["summary"] = {
        "characters": len(chars),
        "aliasConflicts": len(report["aliasConflicts"]),
        "identityConflicts": sum(1 for c in report["aliasConflicts"] if c["classification"] == "identity-conflict"),
        "honorificAmbiguous": sum(1 for c in report["aliasConflicts"] if c["classification"] == "honorific-ambiguous"),
        "aliasShadowsCanonical": len(report["aliasShadowsCanonical"]),
        "orphanEvents": len(orphan_events),
        "danglingEventRefs": len(dangling),
        "orphanCharacters": len(orphan_chars),
        "reviewQueue": len(report["reviewQueue"]),
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
        s = rep["summary"]
        print(f"\n=== {title} ===")
        print(f"  人物 {s['characters']} · 别名冲突 {s['aliasConflicts']} "
              f"(身份冲突 {s['identityConflicts']} · 泛称 {s['honorificAmbiguous']}) · "
              f"别名遮蔽主名 {s['aliasShadowsCanonical']}")
        print(f"  孤立事件 {s['orphanEvents']} · 悬空事件引用 {s['danglingEventRefs']} · "
              f"孤立人物 {s['orphanCharacters']} · 待审队列 {s['reviewQueue']}")
        dup = {k: v["duplicateIds"] for k, v in rep["collections"].items() if v["duplicateIds"]}
        print(f"  ID 重复: {dup or '无'}")
        bad = {k: v["unexpectedPrefixes"] for k, v in rep["collections"].items() if v["unexpectedPrefixes"]}
        print(f"  非预期 ID 前缀: {bad or '无'}")

    (OUT / "registry-summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n-> {artifact_rel(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
