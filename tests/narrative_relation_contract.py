#!/usr/bin/env python3
"""Incremental relationship evidence, continuation and invalid-reference gates."""
import copy
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import narrative as N
import serve as S


def fixture():
    quotes = ["北辰拜南辰为师，跟随他学习守城阵法。", "南辰将守城阵法传授北辰，嘱他谨守城门。"]
    graph = {"title": "守城", "characters": [{"id": "c1", "name": "北辰"}, {"id": "c2", "name": "南辰"}],
             "events": [{"id": "e" + str(i), "order": i + 1, "chapter": "第%d章" % (i + 1),
                         "title": "授艺", "summary": q, "quote": q, "characters": ["北辰", "南辰"]} for i, q in enumerate(quotes)],
             "relations": []}
    return graph, [{"name": "原文", "text": "\n".join(quotes)}]


def part(graph, index=0):
    value = {k: [] for k in N.LAYERS}
    value.update(layerStatus={k: "complete" for k in N.LAYERS}, warnings=[])
    value["relations"] = [{"id": "teacher", "a": "北辰", "b": "南辰", "kind": "师徒", "line": "明线", "hidden": "",
                            "desc": "南辰传授北辰阵法。", "strength": .8, "eventIds": ["e" + str(index)],
                            "quote": graph["events"][index]["quote"], "basis": "explicit"}]
    return value


class Relations(unittest.TestCase):
    def setUp(self):
        self.graph, self.docs = fixture()
        self.tmp = tempfile.TemporaryDirectory(prefix="castline-relations-")
        self.addCleanup(self.tmp.cleanup)
        network = patch.object(S.urllib.request, "urlopen", side_effect=AssertionError("NETWORK FORBIDDEN"))
        network.start(); self.addCleanup(network.stop)

    def run_enrich(self, callback, **kwargs):
        return N.enrich(self.graph, self.docs, callback, S.source_specs, lambda specs: S.Corpus("", specs),
                        S.atomic_json, self.tmp.name, layers=["relations"], model_key="offline", **kwargs)[0]

    def test_anchored_relation_preserves_graph_and_remains_semantically_unverified(self):
        before = copy.deepcopy(self.graph)
        result = self.run_enrich(lambda *a, **k: part(self.graph))
        edge = result["relations"][0]
        self.assertTrue(edge["resolved"])
        self.assertTrue(edge["quoteVerified"])
        self.assertFalse(edge["claimVerified"])
        self.assertEqual(result["events"][0]["summary"], self.graph["events"][0]["summary"])
        self.assertEqual(before, self.graph)

    def test_missing_ambiguous_or_self_endpoints_and_unknown_events_fail(self):
        for changes in [{"a": "不存在"}, {"b": "北辰"}, {"eventIds": ["missing"]}]:
            value = part(self.graph); value["relations"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(N.InvalidResult):
                N.validate_part(value, self.graph, ["relations"])
        self.graph["characters"].append({"id": "c3", "name": "北辰"})
        with self.assertRaises(N.InvalidResult): N.validate_part(part(self.graph), self.graph, ["relations"])

    def test_inferred_relation_still_requires_real_original_quote(self):
        value = part(self.graph); value["relations"][0].update(basis="inferred", quote="原文不存在的结拜誓言")
        with self.assertRaises(N.InvalidResult): self.run_enrich(lambda *a, **k: value)
        self.assertFalse(any(Path(self.tmp.name).rglob("*.json")))

    def test_hidden_line_and_strength_contract(self):
        for change in [{"line": "暗线"}, {"strength": 2}, {"strength": True}, {"strength": math.nan}, {"quote": ""}]:
            value = part(self.graph); value["relations"][0].update(change)
            with self.subTest(change=change), self.assertRaises(N.InvalidResult): N.validate_part(value, self.graph, ["relations"])

    def test_continuation_unions_events_and_keeps_all_quotes_and_cached_resume(self):
        calls = []
        def call(*args, **kwargs):
            calls.append(1)
            return part(self.graph, len(calls) - 1)
        with patch.object(N, "BATCH_EVENTS", 1):
            result = self.run_enrich(call)
            resumed = self.run_enrich(lambda *a, **k: self.fail("cached work repeated"))
        self.assertEqual(len(calls), 2)
        edge = result["relations"][0]
        self.assertEqual(edge["eventIds"], ["e0", "e1"])
        self.assertEqual(len(edge["sourceRefs"]), 2)
        self.assertTrue(edge["quoteVerified"])
        self.assertEqual(resumed["meta"]["enrichment"]["resumedBatches"], 2)

    def test_id_reuse_cannot_overwrite_another_relation(self):
        self.graph["relations"] = part(self.graph)["relations"]
        value = part(self.graph); value["relations"][0]["kind"] = "宿敌"
        with self.assertRaises(N.InvalidResult): N.validate_part(value, self.graph, ["relations"])

    def test_changed_prompt_or_context_policy_cannot_reuse_old_model_results(self):
        calls = []
        def call(*args, **kwargs):
            calls.append(1)
            return part(self.graph)
        original = self.run_enrich(call)
        with patch.object(N, "RULES", N.RULES + "\n新的关系审核要求"):
            changed_prompt = self.run_enrich(call)
        with patch.object(N, "SOURCE_CHARS", N.SOURCE_CHARS + 1):
            changed_context = self.run_enrich(call)
        self.assertEqual(len(calls), 3)
        self.assertNotEqual(original["meta"]["enrichment"]["key"], changed_prompt["meta"]["enrichment"]["key"])
        self.assertNotEqual(original["meta"]["enrichment"]["key"], changed_context["meta"]["enrichment"]["key"])

    def test_model_local_ids_do_not_duplicate_a_relation_across_batches(self):
        calls = []
        def call(*args, **kwargs):
            value = part(self.graph, len(calls))
            value["relations"][0]["id"] = "different-local-id-" + str(len(calls))
            calls.append(1)
            return value
        with patch.object(N, "BATCH_EVENTS", 1): result = self.run_enrich(call)
        self.assertEqual(len(result["relations"]), 1)
        self.assertEqual(result["relations"][0]["eventIds"], ["e0", "e1"])
        self.assertEqual(len(result["relations"][0]["sourceRefs"]), 2)

    def test_duplicate_pairs_in_one_response_fail_but_distinct_kinds_survive(self):
        value = part(self.graph)
        value["relations"].append(dict(value["relations"][0], id="second-model-id"))
        with self.assertRaises(N.InvalidResult): N.validate_part(value, self.graph, ["relations"])
        value["relations"][1]["kind"] = "同盟"
        accepted = N.validate_part(value, self.graph, ["relations"])
        self.assertEqual(len(accepted["relations"]), 2)


if __name__ == "__main__": unittest.main(verbosity=2)
