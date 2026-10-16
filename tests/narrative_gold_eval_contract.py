#!/usr/bin/env python3
"""Independent evaluator negative controls. Synthetic sources, zero model calls."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("narrative_gold_evaluator", Path(__file__).with_name("gold-eval.py"))
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


class GoldEvaluatorContract(unittest.TestCase):
    def setUp(self):
        self.first, self.second = "😀甲打开大门。", "乙穿门走入。"
        self.text = self.first + self.second
        digest = hashlib.sha256(self.text.encode()).hexdigest()
        self.docs = [{"sourceId": "source-test", "name": "synthetic", "text": self.text}]
        self.ref = {"status": "verified", "verified": True, "match": "exact", "sourceId": "source-test",
                    "textHash": digest, "start": 0, "end": len(self.first), "offsetUnit": "codepoint", "quote": self.first}
        self.gold = {"benchmarkVersion": "synthetic-gold/1", "source": {"textHash": digest},
                     "episode": {"start": 0, "end": len(self.text)}, "eventIds": ["e1", "e2"],
                     "events": [{"eventId": "e1", "order": 1, "scopeStart": 0, "scopeEnd": len(self.first), "sourceRefs": [self.ref]},
                                {"eventId": "e2", "order": 2, "scopeStart": len(self.first), "scopeEnd": len(self.text)}],
                     "tasks": [], "causeEdges": [{"fromEventId": "e1", "toEventId": "e2"}], "clues": [],
                     "missingFacts": [], "cannotJudge": [], "evaluationLimits": "source span is not semantic entailment"}
        self.graph = {"events": [{"id": "e1", "order": 1}, {"id": "e2", "order": 2}],
                      "characters": [{"id": "ch1", "name": "甲", "aliases": []}],
                      "causeEdges": [{"id": "edge", "fromEventId": "e1", "toEventId": "e2",
                                      "description": "开门提供进入条件", "quote": self.first, "sourceRefs": [self.ref],
                                      "referenceStatus": "resolved", "resolved": True, "claimVerified": False}]}

    def evaluate(self, graph=None, docs=None):
        return E.evaluate(graph or self.graph, self.gold, docs or self.docs)

    def test_exact_unicode_codepoint_anchor_and_unique_refs_pass_without_semantic_certification(self):
        result = self.evaluate()
        self.assertTrue(result["ok"])
        self.assertEqual(result["claimedVerifiedAnchorPrecision"]["percent"], 100)
        self.assertFalse(result["semanticClaimsAutomaticallyVerified"])
        self.assertFalse(result["automaticModelQualityValidated"])
        self.assertFalse(result["goldCausePairCoverage"]["semanticEntailmentVerified"])

    def test_utf16_span_fake_hash_and_nonverbatim_quote_cannot_pass(self):
        for patch in ({"end": len(self.first) + 1}, {"offsetUnit": "utf16"},
                      {"textHash": "forged"}, {"quote": "原文没有的文字。"}, {"match": "normalized"}):
            graph = copy.deepcopy(self.graph)
            graph["causeEdges"][0]["sourceRefs"][0].update(patch)
            with self.subTest(patch=patch):
                self.assertFalse(self.evaluate(graph)["ok"])

    def test_missing_hash_offsets_or_source_id_are_invalid_even_with_verified_flag(self):
        graph = copy.deepcopy(self.graph)
        graph["causeEdges"][0]["sourceRefs"] = [{"quote": self.first, "verified": True, "status": "verified", "sourceId": "source-test"}]
        result = self.evaluate(graph)
        self.assertFalse(result["ok"])
        self.assertEqual(result["claimedVerifiedAnchorPrecision"]["claimed"], 1)
        self.assertEqual(result["claimedVerifiedAnchorPrecision"]["valid"], 0)

    def test_original_source_hash_change_is_not_hidden_by_same_quote(self):
        docs = copy.deepcopy(self.docs)
        docs[0]["text"] += "新修订。"
        result = self.evaluate(docs=docs)
        self.assertFalse(result["ok"])
        self.assertFalse(result["sourceFingerprintMatches"])

    def test_duplicate_event_id_and_unknown_id_do_not_resolve(self):
        for graph in (dict(self.graph, events=[{"id": "e1", "order": 1}, {"id": "e1", "order": 2}, {"id": "e2", "order": 3}]),
                      dict(self.graph, causeEdges=[dict(self.graph["causeEdges"][0], fromEventId="missing")])):
            self.assertFalse(self.evaluate(graph)["ok"])

    def test_declared_endpoint_conflict_survives_repeated_evaluation(self):
        graph = copy.deepcopy(self.graph)
        graph["causeEdges"][0].update(sourceId=None, declaredSourceId="e2", referenceStatus="unresolved", resolved=True)
        original = copy.deepcopy(graph)
        for _ in range(3):
            result = self.evaluate(graph)
            self.assertFalse(result["ok"])
            self.assertEqual(result["goldCausePairCoverage"]["matching"], 0)
            self.assertTrue(any(problem["reason"] == "conflicting_endpoint_declarations" for problem in result["contractProblems"]))
        self.assertEqual(graph, original)

    def test_server_unresolved_gate_cannot_be_overridden_by_good_looking_ids(self):
        graph = copy.deepcopy(self.graph)
        graph["causeEdges"][0]["referenceStatus"] = "unresolved"
        result = self.evaluate(graph)
        self.assertFalse(result["ok"])
        self.assertEqual(result["goldCausePairCoverage"]["matching"], 0)

    def test_task_null_refs_wrong_actor_and_terminal_without_outcome_are_invalid(self):
        for task in ({"id": "task", "eventIds": None, "character": "甲", "sourceRefs": [self.ref]},
                     {"id": "task", "eventIds": ["e1"], "character": "虚构人物", "sourceRefs": [self.ref]},
                     {"id": "task", "eventIds": ["e1"], "character": "甲", "status": "completed", "outcome": "", "outcomeEventId": "e1", "sourceRefs": [self.ref]}):
            self.assertFalse(self.evaluate(dict(self.graph, tasks=[task]))["ok"])

    def test_quote_ownership_is_a_review_hint_and_does_not_prove_entailment(self):
        state = {"id": "state", "character": "甲", "eventId": "e2", "sourceRefs": [self.ref], "summary": "回顾事件一发生的状态"}
        result = self.evaluate(dict(self.graph, characterStates=[state]))
        self.assertTrue(result["ok"])
        self.assertTrue(result["quoteSceneOwnership"]["reviewNeeded"])
        self.assertFalse(result["semanticClaimsAutomaticallyVerified"])

    def test_supplied_model_windows_are_measured_as_input_coverage(self):
        window = {"sourceId": "source-test", "textHash": self.ref["textHash"], "start": 0,
                  "end": len(self.first), "text": self.first}
        result = E.evaluate(self.graph, self.gold, self.docs, input_windows=[window])
        self.assertEqual(result["modelInputGoldEvidenceCoverage"]["percent"], 100)
        window["text"] = "fake"
        result = E.evaluate(self.graph, self.gold, self.docs, input_windows=[window])
        self.assertEqual(result["modelInputGoldEvidenceCoverage"]["visible"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
