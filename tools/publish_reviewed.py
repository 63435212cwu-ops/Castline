#!/usr/bin/env python3
"""Publish a locally reviewed candidate after independent source/ID checks.

Default is a dry run. --write makes a private exact original backup and a new
hex graph version; it never contacts a model or overwrites the original graph.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import serve as S

spec = importlib.util.spec_from_file_location("reviewed_source_checker", ROOT / "tests/gold-eval.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def validate(candidate, graph, docs):
    sources = S.source_specs(docs)
    if not sources:
        return {"ok": False, "reason": "no_original_sources"}
    _by_id = {}
    _order = []
    for e in graph.get("events", []):
        if isinstance(e, dict):
            k = str(e.get("id"))
            _by_id[k] = e; _order.append(k)
    for e in (candidate.get("newEvents") or []):
        if isinstance(e, dict):
            k = str(e.get("id"))
            if k not in _by_id:
                _order.append(k)
            _by_id[k] = e
    contract_events = [_by_id[k] for k in _order]
    span_end = sum(len(source["text"]) for source in sources)
    identities = [{"eventId": str(event.get("id")), "order": event.get("order"),
                   "scopeStart": 0, "scopeEnd": span_end}
                  for event in contract_events]
    contract = {"benchmarkVersion": "reviewed-publication-source-id/1", "source": {"textHash": sources[0]["textHash"]},
         "episode": {"start": 0, "end": sum(len(source["text"]) for source in sources)},
         "eventIds": [event["eventId"] for event in identities], "events": identities,
         "tasks": [], "causeEdges": [], "clues": [], "missingFacts": [], "cannotJudge": ["semantic_entailment_and_completeness"],
         "evaluationLimits": "Full source/ID contract only; semantic review belongs to reviewers and is not automatically certified."}
    report = E.evaluate(candidate, contract, docs, graph)
    source_index = E.sources_for(docs)
    incoming_ids = candidate.get("reviewedNodeIds") or {}
    citation_errors = []
    cannot_judge = []
    normalized_decl = {(str(_f.get("id")), str(_f.get("layer")))
                       for _f in (candidate.get("normalizedRefFixes") or []) if isinstance(_f, dict)}
    for layer in S.NARRATIVE.LAYERS:
        for node in candidate.get("layers", {}).get(layer, []):
            if not isinstance(node, dict):
                continue
            enforce = node.get("provenance") == "assistant-reviewed-source" or str(node.get("id")) in incoming_ids.get(layer, [])
            if not enforce:
                continue
            if layer == "storylines":
                quotes = node.get("evidenceQuotes") if isinstance(node.get("evidenceQuotes"), list) else []
            elif layer == "clues":
                quotes = [node.get("seedQuote")]
                if node.get("status") == "resolved":
                    quotes.append(node.get("payoffQuote"))
            else:
                quotes = [node.get("quote")]
            refs = E.refs_in(node)
            if not quotes or any(not isinstance(quote, str) or not quote or not any(
                    ref.get("quote") == quote and E.check_anchor(ref, source_index)[0] for ref in refs) for quote in quotes):
                if (str(node.get("id")), layer) in normalized_decl:
                    cannot_judge.append({"id": node.get("id"), "layer": layer,
                                         "reason": "normalized_reference_declared_not_exact"})
                    continue
                citation_errors.append({"id": node.get("id"), "layer": layer, "reason": "reviewed_quote_not_grounded_by_valid_exact_reference"})
    for fix in (candidate.get("characterAliasFixes") or []):
        if not isinstance(fix, dict):
            citation_errors.append({"id": None, "layer": "characterAliasFixes", "reason": "alias_fix_not_object"})
            continue
        quote = fix.get("quote")
        refs = [r for r in (fix.get("sourceRefs") or []) if isinstance(r, dict)]
        if not isinstance(quote, str) or not quote or not any(
                r.get("quote") == quote and E.check_anchor(r, source_index)[0] for r in refs):
            citation_errors.append({"id": fix.get("characterId"), "layer": "characterAliasFixes",
                                    "reason": "alias_fix_quote_not_grounded_by_valid_exact_reference"})
    if cannot_judge:
        report["cannotJudge"].extend(cannot_judge)
    if citation_errors:
        report["ok"] = False
        report["contractProblems"].extend(citation_errors)
    issues = []
    for field in ("reviewIssues", "entityIssues", "eventIssues"):
        if isinstance(candidate.get(field), list):
            issues.extend((field, issue) for issue in candidate[field])
    identity = E.IdentityIndex(graph, contract)
    issue_errors = []
    issue_ids = [str(issue.get("id")) for _, issue in issues if isinstance(issue, dict) and issue.get("id")]
    if len(issue_ids) != len(set(issue_ids)):
        issue_errors.append({"reason": "duplicate_review_issue_id"})
    for field, issue in issues:
        if not isinstance(issue, dict):
            issue_errors.append({"reason": "review_issue_not_object"}); continue
        kind = issue.get("kind") or ("identity" if field == "entityIssues" else "quote")
        if not issue.get("id") or kind not in ("identity", "quote", "attribution", "summary", "source_integrity"):
            issue_errors.append({"id": issue.get("id"), "reason": "invalid_review_issue_identity_or_kind"})
        if issue.get("status", "confirmed_issue") not in ("confirmed_issue", "unresolved"):
            issue_errors.append({"id": issue.get("id"), "reason": "invalid_review_issue_status"})
        if issue.get("characterId") and len(identity.character_ids.get(str(issue["characterId"]), [])) != 1:
            issue_errors.append({"id": issue.get("id"), "reason": "unknown_or_ambiguous_issue_character_id"})
        if kind == "identity" and not issue.get("characterId"):
            issue_errors.append({"id": issue.get("id"), "reason": "identity_issue_requires_character_id"})
        event_ids = list(issue.get("eventIds") or [])
        if issue.get("eventId"):
            event_ids.append(issue["eventId"])
        if kind in ("quote", "attribution", "summary") and not event_ids:
            issue_errors.append({"id": issue.get("id"), "reason": "event_issue_requires_event_reference"})
        for assignment in issue.get("confirmedAssignments", []) if isinstance(issue.get("confirmedAssignments"), list) else []:
            if isinstance(assignment, dict):
                event_ids.extend(assignment.get("eventIds") or [])
        if any(identity.resolve(value) is None for value in event_ids):
            issue_errors.append({"id": issue.get("id"), "reason": "unknown_or_ambiguous_issue_event_id"})
        refs = E.refs_in(issue)
        if not refs or any(not E.check_anchor(ref, source_index)[0] for ref in refs):
            issue_errors.append({"id": issue.get("id"), "reason": "review_issue_has_no_valid_original_source_reference"})
        if not issue.get("description") and not issue.get("reviewNotes"):
            issue_errors.append({"id": issue.get("id"), "reason": "review_issue_missing_description"})
    if issue_errors:
        report["ok"] = False
        report["contractProblems"].extend(issue_errors)
    for span in candidate.get("excludedSourceRanges", []):
        matches = source_index.get(str(span.get("sourceId") or ""), []) if isinstance(span, dict) else []
        start, end = (span.get("start"), span.get("end")) if isinstance(span, dict) else (None, None)
        valid = len(matches) == 1 and type(start) is int and type(end) is int and 0 <= start < end <= len(matches[0]["text"]) and span.get("textHash") == matches[0]["textHash"] and span.get("reason")
        if not valid:
            report["ok"] = False
            report["contractProblems"].append({"reason": "invalid_excluded_source_range"})
    _baseline_ids = {str(e.get("id")) for e in graph.get("events", []) if isinstance(e, dict)}
    name_problems = []
    for event in (candidate.get("newEvents") or []):
        if not isinstance(event, dict):
            name_problems.append({"reason": "new_event_not_object", "eventId": None})
            continue
        eid = str(event.get("id") or "") or None
        if eid is not None and eid in _baseline_ids:
            continue
        readable = [k for k in ("title", "name") if str(event.get(k) or "").strip()]
        if not readable:
            name_problems.append({"reason": "new_event_requires_readable_name", "eventId": eid,
                                  "detail": "title 与 name 皆为空白；计划 P1.6 要求至少一个可读名称"})
        if not str(event.get("chapter") or "").strip():
            name_problems.append({"reason": "new_event_requires_chapter", "eventId": eid,
                                  "detail": "缺章节声明，读者无法回到原文定位"})
        if not str(event.get("kind") or "").strip():
            name_problems.append({"reason": "new_event_requires_kind", "eventId": eid,
                                  "detail": "缺事件类型"})
    if name_problems:
        report["ok"] = False
        report["contractProblems"].extend(name_problems)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-key", required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--write", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        candidate = json.loads(args.candidate.read_text())
        result = S.publish_reviewed_graph(args.source_key, candidate, write=args.write, validator=validate)
        result.pop("graph", None)
    except (ValueError, OSError, S.ApiError) as error:
        result = {"ok": False, "write": False, "error": str(error), "modelCalls": 0, "originalPreserved": True}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {key: value for key, value in result.items() if key != "validation"}
    if result.get("validation"):
        summary["referencePrecision"] = result["validation"]["referencePrecision"]
        summary["claimedVerifiedAnchorPrecision"] = result["validation"]["claimedVerifiedAnchorPrecision"]
        summary["contractProblems"] = result["validation"]["contractProblems"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
