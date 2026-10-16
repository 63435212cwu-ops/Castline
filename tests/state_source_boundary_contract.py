#!/usr/bin/env python3
"""State journey preservation and citation trust gates; offline only."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve as S


class StateSourceBoundaryContract(unittest.TestCase):
    def setUp(self):
        self.docs = [{"id": "state-source", "name": "首章", "text": "😀她发现了密门。她仍不知钥匙所在。"}]
        self.graph = {"characters": [{"id": "c", "name": "她"}], "events": [{"id": "e", "order": 1}]}
        self.network = patch.object(S.urllib.request, "urlopen", side_effect=AssertionError("network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_top_level_journeys_keep_ids_payload_and_optional_scope(self):
        for field in ("stateTransitions", "characterTransitions"):
            with self.subTest(field=field):
                graph = copy.deepcopy(self.graph)
                graph[field] = [{"id": "journey", "before": "不知", "after": "知情", "quote": "她发现了密门。"}]
                before = copy.deepcopy(graph)
                out = S.rebuild_sources(graph, self.docs)
                self.assertEqual(graph, before)
                self.assertEqual(out[field][0]["id"], "journey")
                self.assertEqual(out[field][0]["before"], "不知")
                self.assertTrue(out[field][0]["quoteVerified"])
                self.assertTrue(out["meta"]["capabilities"]["optionalLayers"][field])
                self.assertNotIn(field, S.AUX_GRAPH_FIELDS)

    def test_every_nested_claim_reanchors_and_clears_forged_trust(self):
        fields = ("knowledge", "knowledgeGaps", "stateTransitions", "state_transitions", "transitions", "turning_points", "transition")
        for owner in ("characters", "characterStates"):
            for field in fields:
                with self.subTest(owner=owner, field=field):
                    graph = copy.deepcopy(self.graph)
                    claim = {"text": "密门", "before": "不知", "after": "知情", "quote": "她发现了密门。", "claimVerified": True,
                             "sourceRef": {"verified": True, "status": "verified", "quote": "伪造", "sourceId": "missing"}}
                    graph[owner] = [{"id": "owner", "name": "她", field: claim if field == "transition" else [claim]}]
                    out = S.rebuild_sources(graph, self.docs)[owner][0][field]
                    row = out if field == "transition" else out[0]
                    self.assertTrue(row["quoteVerified"])
                    self.assertFalse(row["claimVerified"])
                    self.assertNotIn("sourceRef", row)
                    self.assertEqual(row["sourceRefs"][0]["quote"], claim["quote"])

    def test_nested_review_remains_locator_only_after_repeated_rebuild(self):
        self.graph["characterStates"] = [{"id": "s", "knowledge": [{"text": "密门", "quote": "她发现了密门。", "quoteReview": "wrong-speaker"}]}]
        graph = self.graph
        for _ in range(2):
            graph = S.rebuild_sources(graph, self.docs)
            row = graph["characterStates"][0]["knowledge"][0]
            self.assertFalse(row["quoteVerified"])
            self.assertFalse(row["sourceRefs"][0]["verified"])
            self.assertTrue(row["sourceRefs"][0]["locatorOnly"])

    def test_absent_and_explicit_empty_journeys_remain_distinct(self):
        out = S.rebuild_sources(self.graph, self.docs)
        self.assertNotIn("stateTransitions", out)
        self.assertFalse(out["meta"]["coverage"]["stateTransitions"]["known"])
        self.graph.update(stateTransitions=[], meta={"coverage": {"stateTransitions": {"known": True, "scope": "首章"}}})
        out = S.rebuild_sources(self.graph, self.docs)
        self.assertEqual(out["stateTransitions"], [])
        self.assertTrue(out["meta"]["coverage"]["stateTransitions"]["known"])
        self.assertEqual(out["meta"]["coverage"]["stateTransitions"]["scope"], "首章")


if __name__ == "__main__":
    unittest.main(verbosity=2)
