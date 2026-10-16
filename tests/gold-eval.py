#!/usr/bin/env python3
"""Offline gold evaluator: exact provenance + identity, semantic review queue.

No model calls. A valid source span does not certify the associated claim.
Run --validate-gold first, then --graph a graph or raw reviewed candidate.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = ROOT / "tests/fixtures/narrative-gold-xiyou.json"
DEFAULT_DOCS = ROOT / "data/cache/d16db79a529a1727352091d5.docs.json"
DEFAULT_BASELINE = ROOT / "data/cache/d16db79a529a1727352091d5.json"
LAYERS = ("storylines", "tasks", "causeEdges", "clues", "characterStates", "relations")


def sources_for(docs):
    result = collections.defaultdict(list)
    for index, doc in enumerate(docs if isinstance(docs, list) else []):
        if not isinstance(doc, dict):
            continue
        raw = doc.get("sourceText") if isinstance(doc.get("sourceText"), str) else doc.get("text")
        if not isinstance(raw, str) or not raw:
            continue
        text_hash = hashlib.sha256(raw.encode()).hexdigest()
        label = str(doc.get("path") or doc.get("name") or ("source-%d" % (index + 1)))
        source_id = str(doc.get("sourceId") or doc.get("id") or "src_" + hashlib.sha1((label + "\0" + text_hash).encode()).hexdigest()[:20])
        result[source_id].append({"text": raw, "textHash": text_hash})
    return result


def check_anchor(ref, sources):
    if not isinstance(ref, dict):
        return False, "not_object"
    quote = ref.get("quote")
    if not isinstance(quote, str) or not quote:
        return False, "empty_quote"
    if ref.get("verified") is not True or ref.get("status") != "verified" or ref.get("match") != "exact":
        return False, "not_exact_verified_contract"
    if ref.get("offsetUnit") != "codepoint":
        return False, "unsupported_offset_unit"
    start, end = ref.get("start"), ref.get("end")
    if type(start) is not int or type(end) is not int or start < 0 or end <= start or end - start != len(quote):
        return False, "invalid_span"
    entries = sources.get(str(ref.get("sourceId") or ""), [])
    hashes = {entry["textHash"] for entry in entries}
    if not entries or len(hashes) != 1:
        return False, "missing_or_ambiguous_source_id"
    source = entries[0]
    if not ref.get("textHash") or ref["textHash"] != source["textHash"]:
        return False, "source_hash_mismatch"
    if end > len(source["text"]) or source["text"][start:end] != quote:
        return False, "verbatim_span_mismatch"
    return True, "exact_hash_offset_quote"


def refs_in(value):
    """Find refs without counting duplicate quoteRef/sourceRefs aliases twice."""
    found = []
    def walk(item, ref_context=False):
        if isinstance(item, dict):
            if "quote" in item:
                if ref_context or "textHash" in item or "offsetUnit" in item:
                    found.append(item)
                    return
            for key, nested in item.items():
                walk(nested, str(key).endswith("Ref") or str(key).endswith("Refs"))
        elif isinstance(item, list):
            for nested in item:
                walk(nested, ref_context)
    walk(value)
    unique = {}
    for ref in found:
        key = tuple(str(ref.get(name)) for name in ("sourceId", "textHash", "start", "end", "quote", "offsetUnit"))
        unique[key] = ref
    return list(unique.values())


def fallback_id(kind, item):
    existing = item.get("id") if item.get("id") is not None else item.get("entityId")
    if existing is not None and str(existing) != "":
        return str(existing)
    if kind == "ev":
        key = {"chapter": item.get("chapter"), "title": item.get("title"), "summary": item.get("summary"),
               "quote": item.get("quote"), "rawOrder": item.get("rawOrder", item.get("order"))}
    else:
        key = {"name": item.get("name")}
    encoded = json.dumps(key, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return kind + "_" + hashlib.sha1(encoded.encode()).hexdigest()[:16]


class IdentityIndex:
    def __init__(self, graph, gold, reviewed_events=None):
        events = graph.get("events") if isinstance(graph.get("events"), list) else []
        if not events:
            events = [{"id": event["eventId"], "order": event["order"]} for event in gold["events"]]
        self.ids = collections.defaultdict(list)
        self.orders = collections.defaultdict(list)
        extra_events = [e for e in (reviewed_events or []) if isinstance(e, dict)]
        _dedup = {}
        _dedup_order = []
        for event in events:
            if not isinstance(event, dict):
                continue
            ident0 = fallback_id("ev", event)
            if ident0 not in _dedup:
                _dedup_order.append(ident0)
            _dedup[ident0] = event
        _graph_dups = collections.Counter(fallback_id("ev", e) for e in events if isinstance(e, dict))
        for event in extra_events:
            if not isinstance(event, dict):
                continue
            ident0 = fallback_id("ev", event)
            if ident0 not in _dedup:
                _dedup_order.append(ident0)
            _dedup[ident0] = event
        for ident in _dedup_order:
            event = _dedup[ident]
            self.ids[ident].append(event)
            if _graph_dups.get(ident, 0) > 1:
                for _ in range(_graph_dups[ident] - 1):
                    self.ids[ident].append(event)
            for value in dict.fromkeys([event.get("order"), event.get("rawOrder", event.get("order"))]):
                if value is not None:
                    self.orders[str(value)].append(ident)
        self.characters = collections.defaultdict(list)
        self.character_ids = collections.defaultdict(list)
        for character in graph.get("characters", []) if isinstance(graph.get("characters"), list) else []:
            ident = fallback_id("ch", character)
            self.character_ids[ident].append(character)
            for name in [character.get("name")] + (character.get("aliases") if isinstance(character.get("aliases"), list) else []):
                if name:
                    self.characters[str(name)].append(ident)

    def resolve(self, value, allow_order=False):
        if value is None or value == "":
            return None
        value = str(value)
        if value in self.ids:
            return value if len(self.ids[value]) == 1 else None
        if allow_order:
            options = self.orders.get(value, [])
            return options[0] if len(options) == 1 and len(self.ids[options[0]]) == 1 else None
        return None

    def character(self, item):
        claims = []
        if item.get("characterId"):
            options = self.character_ids.get(str(item["characterId"]), [])
            if len(options) != 1:
                return False
            claims.append(fallback_id("ch", options[0]))
        if item.get("character"):
            options = self.characters.get(str(item["character"]), [])
            if len(set(options)) != 1:
                return False
            claims.append(options[0])
        return bool(claims) and len(set(claims)) == 1


def percent(numerator, denominator):
    return round(100 * numerator / denominator, 2) if denominator else None


def evaluate(candidate, gold, docs, baseline=None, input_windows=None):
    sources = sources_for(docs)
    gold_refs = refs_in(gold)
    gold_invalid = []
    for ref in gold_refs:
        valid, reason = check_anchor(ref, sources)
        if not valid:
            gold_invalid.append({"quote": ref.get("quote"), "reason": reason})
    expected_hash = gold["source"]["textHash"]
    source_match = any(source["textHash"] == expected_hash for entries in sources.values() for source in entries)
    result = {"benchmarkVersion": gold["benchmarkVersion"], "sourceFingerprintMatches": source_match,
              "goldAnchors": {"unique": len(gold_refs), "valid": len(gold_refs) - len(gold_invalid), "invalid": gold_invalid},
              "semanticClaimsAutomaticallyVerified": False, "automaticModelQualityValidated": False,
              "limitations": gold["evaluationLimits"]}
    if not candidate:
        result["ok"] = source_match and not gold_invalid
        return result
    graph = candidate.get("graph") if isinstance(candidate.get("graph"), dict) else candidate
    layers = candidate.get("layers") if isinstance(candidate.get("layers"), dict) else graph
    index_graph = graph if isinstance(graph.get("events"), list) else baseline or {}
    index = IdentityIndex(index_graph, gold, reviewed_events=candidate.get("newEvents"))
    selected = set(gold["eventIds"])
    scope_by_id = {event["eventId"]: (event["scopeStart"], event["scopeEnd"]) for event in gold["events"]}
    approved_causes = {(item["fromEventId"], item["toEventId"]) for item in gold["causeEdges"]}
    approved_clues = {(item["seedEventId"], item["payoffEventId"]) for item in gold["clues"]}
    candidate_causes, candidate_clues = set(), set()
    reference_total = reference_valid = 0
    anchor_total = anchor_valid = verified_total = verified_valid = 0
    ownership_total = ownership_valid = 0
    problems, ownership_review, unknown_causes, review_tasks = [], [], [], []
    layer_counts, scoped_nodes = {}, []

    def resolve_claim(item, names, allow_order=False):
        nonlocal reference_total, reference_valid
        declared = [(name, item[name]) for name in names if item.get(name) is not None and item.get(name) != ""]
        if not declared:
            reference_total += 1
            return None
        resolved = []
        valid_all = True
        for name, value in declared:
            ident = index.resolve(value, allow_order)
            reference_total += 1
            reference_valid += int(ident is not None)
            if ident is None:
                problems.append({"id": item.get("id"), "field": name, "value": value, "reason": "missing_or_ambiguous_event_reference"})
                valid_all = False
            else:
                resolved.append(ident)
        if not valid_all:
            return None
        if len(set(resolved)) != 1:
            problems.append({"id": item.get("id"), "reason": "conflicting_endpoint_declarations", "declarations": declared})
            return None
        return resolved[0]

    for layer in LAYERS:
        items = layers.get(layer, []) if isinstance(layers.get(layer), list) else []
        reviewed_ids = set((candidate.get("reviewedNodeIds") or {}).get(layer, []))
        relation_ids = collections.Counter(str(item.get("id")) for item in items
                                           if isinstance(item, dict) and item.get("id")) if layer == "relations" else {}
        relation_keys = set()
        kept, valid_nodes = 0, 0
        for item in items:
            if not isinstance(item, dict):
                continue
            declared_ids = set(str(value) for key in ("eventIds", "evidenceEventIds")
                               for value in (item.get(key) if isinstance(item.get(key), list) else []))
            for key in ("eventId", "fromEventId", "toEventId", "sourceId", "targetId", "declaredSourceId", "declaredTargetId", "seedEventId", "payoffEventId"):
                if item.get(key):
                    declared_ids.add(str(item[key]))
            order_ids = {index.resolve(value, True) for value in item.get("events", [])} if isinstance(item.get("events"), list) else set()
            node_refs = refs_in(item)
            in_episode = any(ref.get("textHash") == expected_hash and type(ref.get("start")) is int and
                             gold["episode"]["start"] <= ref["start"] < gold["episode"]["end"] for ref in node_refs)
            reviewed = item.get("provenance") == "assistant-reviewed-source" or str(item.get("id")) in reviewed_ids
            if not (reviewed or declared_ids & selected or order_ids & selected or in_episode):
                continue
            kept += 1
            owned, valid, pending_pair = set(), True, None
            if layer == "causeEdges":
                source = resolve_claim(item, ["fromEventId", "from", "sourceId", "declaredSourceId"], True)
                target = resolve_claim(item, ["toEventId", "to", "targetId", "declaredTargetId"], True)
                valid = source is not None and target is not None and source != target
                owned.update(value for value in (source, target) if value)
                if valid:
                    pending_pair = source, target
            elif layer == "clues":
                seed = resolve_claim(item, ["seedEventId"])
                payoff = resolve_claim(item, ["payoffEventId"]) if item.get("payoffEventId") else None
                valid = seed is not None and (not item.get("payoffEventId") or payoff is not None)
                owned.update(value for value in (seed, payoff) if value)
                if item.get("status") == "resolved":
                    valid = valid and payoff is not None and seed != payoff
                    if valid:
                        seed_order = next(event["order"] for event in gold["events"] if event["eventId"] == seed) if seed in selected else None
                        payoff_order = next(event["order"] for event in gold["events"] if event["eventId"] == payoff) if payoff in selected else None
                        valid = seed_order is None or payoff_order is None or seed_order < payoff_order
                    if valid:
                        pending_pair = seed, payoff
            elif layer == "characterStates":
                event = resolve_claim(item, ["eventId"])
                valid = event is not None and index.character(item)
                if event:
                    owned.add(event)
            else:
                sets = []
                for field, allow_order in (("eventIds", False), ("evidenceEventIds", False), ("events", True)):
                    values = item.get(field)
                    if not isinstance(values, list) or not values:
                        continue
                    resolved = []
                    for value in values:
                        reference_total += 1
                        ident = index.resolve(value, allow_order)
                        reference_valid += int(ident is not None)
                        valid = valid and ident is not None
                        if ident:
                            resolved.append(ident)
                    sets.append(set(resolved))
                valid = valid and bool(sets) and all(group == sets[0] for group in sets)
                owned = sets[0] if sets else set()
                if layer == "tasks":
                    valid = valid and index.character(item)
                    if item.get("status") in ("completed", "failed", "abandoned"):
                        outcome = resolve_claim(item, ["outcomeEventId"])
                        valid = valid and bool(item.get("outcome")) and outcome in owned
                    review_tasks.append({"id": item.get("id"), "eventIds": list(owned), "name": item.get("name"),
                                         "goal": item.get("goal"), "status": item.get("status"), "outcome": item.get("outcome"), "cost": item.get("cost")})
                elif layer == "relations":
                    endpoints = []
                    for field in ("a", "b"):
                        options = set(index.characters.get(str(item.get(field) or ""), []))
                        endpoint = next(iter(options)) if len(options) == 1 else None
                        good = endpoint is not None and len(index.character_ids[endpoint]) == 1
                        reference_total += 1
                        reference_valid += int(good)
                        valid = valid and good
                        endpoints.append(endpoint if good else None)
                        if not good:
                            problems.append({"id": item.get("id"), "field": field, "reason": "missing_or_ambiguous_character_reference"})
                    valid = valid and all(endpoints) and endpoints[0] != endpoints[1]
                    valid = valid and isinstance(item.get("eventIds"), list) and bool(item["eventIds"])
                    ident = str(item.get("id") or "").strip()
                    if not ident or relation_ids.get(ident, 0) != 1:
                        valid = False
                        problems.append({"id": item.get("id"), "reason": "missing_or_duplicate_relation_id"})
                    kind, line = str(item.get("kind") or "").strip(), item.get("line")
                    strength = item.get("strength")
                    valid = valid and bool(kind) and line in ("明线", "暗线")
                    valid = valid and bool(str(item.get("desc") or "").strip())
                    valid = valid and (line != "暗线" or bool(str(item.get("hidden") or "").strip()))
                    valid = valid and type(strength) in (int, float) and 0 <= strength <= 1
                    if all(endpoints):
                        key = (tuple(sorted(endpoints)), kind, str(line))
                        if key in relation_keys:
                            valid = False
                            problems.append({"id": item.get("id"), "reason": "duplicate_relation_identity"})
                        relation_keys.add(key)
                    if (not isinstance(item.get("quote"), str) or not item["quote"] or not node_refs
                            or any(not check_anchor(ref, sources)[0] for ref in node_refs)
                            or not any(ref.get("quote") == item["quote"] for ref in node_refs)):
                        valid = False
                        problems.append({"id": item.get("id"), "reason": "relation_quote_requires_valid_exact_source_references"})
            forced_unresolved = item.get("referenceStatus") in ("unresolved", "unresolved_or_conflicting", "unknown", "invalid")
            endpoint_status = item.get("endpointResolution")
            if isinstance(endpoint_status, dict) and any(value in ("unresolved", "unresolved_or_conflicting", "missing") for value in endpoint_status.values()):
                forced_unresolved = True
            if forced_unresolved:
                valid = False
                problems.append({"id": item.get("id"), "reason": "server_unresolved_status_must_not_be_overridden"})
            if item.get("resolved") is True and not valid:
                problems.append({"id": item.get("id"), "reason": "false_resolved_declaration"})
            if not valid:
                problems.append({"id": item.get("id"), "layer": layer, "reason": "node_reference_contract_failed"})
            if valid and pending_pair:
                if layer == "causeEdges":
                    candidate_causes.add(pending_pair)
                    if pending_pair not in approved_causes:
                        unknown_causes.append({"id": item.get("id"), "fromEventId": pending_pair[0], "toEventId": pending_pair[1],
                            "description": item.get("description"), "reason": "not_adjudicated_by_this_gold_requires_semantic_review"})
                elif layer == "clues":
                    candidate_clues.add(pending_pair)
            valid_nodes += int(valid)
            for ref in node_refs:
                anchor_total += 1
                exact, reason = check_anchor(ref, sources)
                anchor_valid += int(exact)
                claimed = ref.get("verified") is True or ref.get("status") == "verified"
                verified_total += int(claimed)
                verified_valid += int(claimed and exact)
                if claimed and not exact:
                    problems.append({"id": item.get("id"), "quote": ref.get("quote"), "reason": reason})
                if exact and owned:
                    ownership_total += 1
                    in_owned_scene = any(ident in scope_by_id and ref["start"] < scope_by_id[ident][1]
                                         and ref["end"] > scope_by_id[ident][0] for ident in owned)
                    ownership_valid += int(in_owned_scene)
                    if not in_owned_scene:
                        ownership_review.append({"id": item.get("id"), "eventIds": list(owned), "quote": ref["quote"],
                                                 "reason": "quote_outside_owned_scene_may_be_retrospective_requires_review"})
            if item.get("claimVerified") is True:
                problems.append({"id": item.get("id"), "reason": "source_span_cannot_certify_semantic_claim"})
            scoped_nodes.append((layer, item))
        layer_counts[layer] = {"scopedNodes": kept, "validReferenceNodes": valid_nodes}

    preserved = sum(index.resolve(ident) is not None for ident in selected)
    result.update({"scope": gold["episode"], "provenance": candidate.get("provenance") or graph.get("meta", {}).get("enrichment", {}).get("version"),
        "layerCounts": layer_counts, "eventIdentityCoverage": {"present": preserved, "gold": len(selected), "percent": percent(preserved, len(selected))},
        "referencePrecision": {"valid": reference_valid, "declared": reference_total, "percent": percent(reference_valid, reference_total)},
        "sourceAnchorCoverage": {"exact": anchor_valid, "supplied": anchor_total, "percent": percent(anchor_valid, anchor_total)},
        "claimedVerifiedAnchorPrecision": {"valid": verified_valid, "claimed": verified_total, "percent": percent(verified_valid, verified_total)},
        "quoteSceneOwnership": {"inOwnedScenes": ownership_valid, "anchoredWithEventRefs": ownership_total,
                                "percent": percent(ownership_valid, ownership_total), "reviewNeeded": ownership_review},
        "goldCausePairCoverage": {"matching": len(candidate_causes & approved_causes), "gold": len(approved_causes),
                                  "percent": percent(len(candidate_causes & approved_causes), len(approved_causes)), "semanticEntailmentVerified": False},
        "goldCluePairCoverage": {"matching": len(candidate_clues & approved_clues), "gold": len(approved_clues),
                                 "percent": percent(len(candidate_clues & approved_clues), len(approved_clues)), "authorialIntentVerified": False},
        "unadjudicatedCauseClaims": unknown_causes, "contractProblems": problems,
        "missingManifestFacts": gold["missingFacts"], "cannotJudge": gold["cannotJudge"],
        "semanticReviewQueue": [{"goldFactId": task["factId"], "expected": {k:task[k] for k in ("goal", "obstacle", "action", "outcome", "cost", "acceptableStatuses")},
                                 "candidateTasks": [item for item in review_tasks if set(item["eventIds"]) & set(task["eventIds"])],
                                 "reviewStatus": "human_or_independent_semantic_review_required"} for task in gold["tasks"]]})
    if input_windows is not None:
        windows = input_windows.get("sourceWindows", []) if isinstance(input_windows, dict) else input_windows
        valid_windows = []
        for window in windows if isinstance(windows, list) else []:
            if not isinstance(window, dict):
                continue
            entries = sources.get(str(window.get("sourceId")), [])
            a, b = window.get("start"), window.get("end")
            if len(entries) == 1 and type(a) is int and type(b) is int and entries[0]["textHash"] == window.get("textHash") and entries[0]["text"][a:b] == window.get("text"):
                valid_windows.append(window)
        visible = sum(any(window["sourceId"] == ref["sourceId"] and window["start"] <= ref["start"] and window["end"] >= ref["end"] for window in valid_windows) for ref in gold_refs)
        result["modelInputGoldEvidenceCoverage"] = {"visible": visible, "goldQuotes": len(gold_refs), "percent": percent(visible, len(gold_refs)), "validWindows": len(valid_windows)}
    result["ok"] = source_match and not gold_invalid and not problems and preserved == len(selected)
    result["okMeaning"] = "reference_and_verbatim_contract_only_not_semantic_or_world_class_quality"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--input-windows", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--validate-gold", action="store_true")
    args = parser.parse_args()
    gold, docs = json.loads(args.gold.read_text()), json.loads(args.docs.read_text())
    candidate = json.loads(args.graph.read_text()) if args.graph else None
    baseline = json.loads(args.baseline.read_text()) if candidate and args.baseline.exists() else None
    windows = json.loads(args.input_windows.read_text()) if args.input_windows else None
    result = evaluate(candidate, gold, docs, baseline, windows)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded)
    summary = {key: result[key] for key in ("ok", "sourceFingerprintMatches", "goldAnchors", "semanticClaimsAutomaticallyVerified")}
    if candidate:
        summary.update({key: result[key] for key in ("layerCounts", "referencePrecision", "claimedVerifiedAnchorPrecision", "goldCausePairCoverage", "goldCluePairCoverage")})
        summary["contractProblems"] = result["contractProblems"]
        summary["quoteSceneOwnershipReviewCount"] = len(result["quoteSceneOwnership"]["reviewNeeded"])
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
