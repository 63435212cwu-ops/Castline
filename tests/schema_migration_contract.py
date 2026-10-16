#!/usr/bin/env python3
"""P01 server schema/migration contract; fully offline, never writes data/.

Covers the server half of the v4 -> v5 hop: a castline/4 cache must still be
readable, missing fields must stay explicitly unknown, chapter/alias identity
must be measured rather than guessed, and a published revision must never be
migrated in place.
"""
import copy
import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("castline_schema_migration", os.path.join(ROOT, "serve.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

REAL_CACHES = ("9b676d7031b1bcd3b8377a18", "df959d743e53206f56db2f92", "152e2a6eed94f1075e7e7070")


def v4_graph(**extra):
    graph = {
        "title": "契约样本",
        "characters": [
            {"id": "ch_a", "name": "甲", "aliases": ["阿甲"], "importance": None,
             "attrs": {"意志": {"score": 71, "evidence": ["他仍不放弃。"]}}},
            {"id": "ch_b", "name": "乙", "aliases": ["阿甲"]},
        ],
        "events": [
            {"id": "ev_2", "order": 2, "chapter": "第二章 归途", "title": "归来", "quote": "他终究归来。"},
            {"id": "ev_1", "order": 1, "chapter": "第一章  出发", "title": "出发", "quote": "他离开家。"},
        ],
        "relations": [{"id": "rel_1", "a": "甲", "b": "乙", "kind": "同行", "line": "明线"}],
        "storylines": [{"id": "sl_1", "name": "归途", "eventIds": ["ev_1", "ev_2"]}],
        "meta": {"schema": "castline/4", "schemaVersion": "castline/4"},
    }
    graph.update(extra)
    return graph


class SchemaMigrationContract(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(S.urllib.request, "urlopen", side_effect=AssertionError("network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def cache(self, key):
        with open(os.path.join(ROOT, "data", "cache", key + ".json"), encoding="utf-8") as handle:
            return json.load(handle)

    def test_every_legacy_schema_still_opens_and_reports_its_origin(self):
        for schema in ("castline/4", "castline/3", "v3-universal", None):
            with self.subTest(schema=schema):
                graph = v4_graph()
                if schema is None:
                    graph["meta"] = {}
                else:
                    graph["meta"] = {"schema": schema, "schemaVersion": schema}
                out = S._graph_contract(copy.deepcopy(graph))
                self.assertEqual(out["meta"]["schemaVersion"], S.GRAPH_SCHEMA_VERSION)
                self.assertEqual(out["meta"]["schemaCompat"]["inputSchema"], schema or "legacy")
                self.assertTrue(out["meta"]["schemaCompat"]["additive"])
                self.assertFalse(out["meta"]["schemaCompat"]["rewritesInput"])
                self.assertEqual(len(out["events"]), 2)
                self.assertEqual(len(out["characters"]), 2)
        for legacy in ("castline/4", "castline/3", "v3-universal", "legacy"):
            self.assertIn(legacy, S.GRAPH_SCHEMA_READS)

    def test_apply_migration_never_mutates_the_graph_it_was_handed(self):
        graph = v4_graph()
        before = json.dumps(graph, ensure_ascii=False, sort_keys=True)
        S.apply_migration(graph)
        self.assertEqual(json.dumps(graph, ensure_ascii=False, sort_keys=True), before)

    def test_migration_plan_refuses_a_published_revision(self):
        published = v4_graph(meta={"schema": "castline/4", "schemaVersion": "castline/4",
                                  "revision": {"key": "abc123", "parentKey": "parent", "originalPreserved": True}})
        plan = S.migration_plan(published)
        self.assertEqual(plan["published"]["key"], "abc123")
        self.assertFalse(plan["inPlaceAllowed"])
        self.assertEqual(plan["hops"], ["castline/4>castline/5"])
        refused = S.apply_migration(published)
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["reason"], "published_revision_not_migrated_in_place")
        self.assertTrue(S.apply_migration(published, allow_published=True)["ok"])

    def test_migration_is_additive_and_input_is_not_mutated(self):
        graph = v4_graph(customLegacyField={"keep": 1})
        before = json.dumps(graph, ensure_ascii=False, sort_keys=True)
        result = S.apply_migration(graph)
        self.assertTrue(result["ok"])
        self.assertTrue(result["legacyFieldsPreserved"])
        self.assertEqual(result["graph"]["customLegacyField"], {"keep": 1})
        self.assertEqual(json.dumps(graph, ensure_ascii=False, sort_keys=True), before)

    def test_rollback_removes_only_contract_fields(self):
        snapshot = v4_graph()
        before = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        migrated = S.apply_migration(snapshot, allow_published=True)["graph"]
        self.assertIn("identity", migrated["meta"])
        back = S.rollback_migration(snapshot)
        self.assertTrue(back["ok"])
        self.assertFalse(back["rewroteLegacyFields"])
        self.assertEqual(back["restoredFields"], [])
        self.assertEqual(json.dumps(back["graph"], ensure_ascii=False, sort_keys=True), before)
        self.assertNotIn("identity", back["graph"]["meta"])

    def test_chapter_ids_are_content_addressed_and_order_independent(self):
        first = S._graph_contract(copy.deepcopy(v4_graph()))
        shuffled = v4_graph()
        shuffled["events"] = list(reversed(shuffled["events"]))
        second = S._graph_contract(copy.deepcopy(shuffled))
        ids_a = sorted(first["meta"]["identity"]["chapters"]["ids"].values())
        ids_b = sorted(second["meta"]["identity"]["chapters"]["ids"].values())
        self.assertEqual(ids_a, ids_b)
        self.assertEqual(len(ids_a), 2, "whitespace runs collapse; distinct labels stay distinct")
        self.assertEqual(S._chapter_id("第一章  出发"), S._chapter_id("第一章 出发"))
        self.assertNotEqual(S._chapter_id("第一章 出发"), S._chapter_id("第二章 出发"))

    def test_unlabelled_events_are_counted_and_never_given_an_ordinal(self):
        graph = v4_graph()
        graph["events"].append({"id": "ev_3", "order": 3, "title": "无章节"})
        out = S._graph_contract(copy.deepcopy(graph))
        ledger = out["meta"]["identity"]
        self.assertEqual(ledger["chapters"]["unlabelledEvents"], 1)
        self.assertEqual(ledger["chapters"]["count"], 2)

    def test_alias_conflicts_are_queued_and_never_merged(self):
        out = S._graph_contract(copy.deepcopy(v4_graph()))
        ledger = out["meta"]["identity"]
        self.assertEqual(ledger["aliases"]["autoMerged"], 0)
        self.assertEqual(ledger["aliases"]["conflictedTokens"], 1)
        row = ledger["aliases"]["queue"][0]
        self.assertEqual(row["token"], "阿甲")
        self.assertFalse(row["autoMerged"])
        self.assertEqual(row["attribution"], "review_required")
        self.assertEqual(len(row["nodeIds"]), 2)
        self.assertEqual(out["characters"][0]["aliases"], ["阿甲"])
        self.assertEqual(out["characters"][1]["aliases"], ["阿甲"])

    def test_reviewed_identity_conflict_keeps_scores_pending(self):
        graph = v4_graph()
        graph["reviewIssues"] = [{"id": "issue_1", "kind": "identity", "status": "confirmed_issue",
                                 "characterId": "ch_a", "identityStatus": "canonical_name_conflict_in_reviewed_scope",
                                 "description": "主名与别名冲突"}]
        out = S._graph_contract(copy.deepcopy(graph))
        queue = out["meta"]["identity"]["reviewQueue"]
        self.assertTrue(any(row["kind"] == "reviewed_identity_issue" and row["nodeIds"] == ["ch_a"] for row in queue))
        self.assertEqual(out["meta"]["identity"]["aliases"]["autoMerged"], 0)
        rebuilt = S.rebuild_sources(out, [{"id": "s", "name": "n", "text": "他仍不放弃。"}])
        self.assertTrue(any(row["kind"] == "reviewed_identity_issue" for row in rebuilt["meta"]["identity"]["reviewQueue"]))

    def test_missing_measurements_stay_unknown_and_no_default_is_invented(self):
        graph = {"characters": [{"id": "ch_a", "name": "甲", "attrs": {"意志": {}}}],
                 "events": [{"id": "ev_1", "order": 1, "title": "无证据事件"}],
                 "relations": [{"id": "rel_1", "a": "甲", "b": "甲", "kind": "自指"}],
                 "meta": {"schema": "castline/4"}}
        out = S._graph_contract(copy.deepcopy(graph))
        ledger = out["meta"]["identity"]
        self.assertIsNone(out["characters"][0].get("importance"))
        self.assertIsNone(out["characters"][0]["attrs"]["意志"].get("score"))
        self.assertEqual(ledger["unknown"]["fabricatedDefaults"], 0)
        self.assertEqual(ledger["unknown"]["pendingAttributes"], 1)
        self.assertEqual(ledger["unknown"]["scoredAttributes"], 0)
        self.assertEqual(ledger["orphans"]["relations"], 1)
        profile = {"kind": "anthropic", "model": "offline-contract", "base_url": "http://invalid.local", "api_key": ""}
        processed = S.postprocess(copy.deepcopy(graph), profile=profile)
        attr = processed["characters"][0]["attrs"]["意志"]
        self.assertIsNone(attr["score"])
        self.assertTrue(attr["pending"], "a missing score must be explicitly pending")
        self.assertEqual(processed["meta"]["identity"]["unknown"]["fabricatedDefaults"], 0)

    def test_optional_layer_coverage_stays_unknown(self):
        out = S._graph_contract(copy.deepcopy(v4_graph()))
        for field in ("clues", "causeEdges", "characterStates", "locations"):
            self.assertFalse(out["meta"]["coverage"][field]["known"], field)
        self.assertFalse(out["meta"]["capabilities"]["optionalLayers"]["clues"])

    def test_real_v4_caches_still_open_with_measured_ledgers(self):
        for key in REAL_CACHES:
            with self.subTest(key=key):
                graph = self.cache(key)
                self.assertEqual(graph["meta"]["schemaVersion"], "castline/4", "%s must stay v4 on disk" % key)
                before = json.dumps(graph, ensure_ascii=False, sort_keys=True)
                out = S._graph_contract(copy.deepcopy(graph))
                self.assertEqual(json.dumps(graph, ensure_ascii=False, sort_keys=True), before)
                self.assertEqual(out["meta"]["schemaCompat"]["inputSchema"], "castline/4")
                ledger = out["meta"]["identity"]
                self.assertGreater(ledger["chapters"]["count"], 90, key)
                self.assertEqual(ledger["chapters"]["unlabelledEvents"], 0, key)
                self.assertEqual(ledger["aliases"]["autoMerged"], 0, key)
                self.assertFalse(S.migration_plan(graph)["inPlaceAllowed"], key)

    def test_dafeng_collision_and_review_issue_are_in_the_queue(self):
        graph = self.cache("9b676d7031b1bcd3b8377a18")
        out = S._graph_contract(copy.deepcopy(graph))
        ledger = out["meta"]["identity"]
        shared = ledger["aliases"]["shared"]
        self.assertIn("初代监正", shared)
        self.assertEqual(sorted(shared["初代监正"]), ["ch_45b2bc1e3bbde2b4", "ch_d50998c6c5bc7460"])
        identity_issues = [row for row in ledger["reviewQueue"] if row["kind"] == "reviewed_identity_issue"]
        self.assertTrue(any("ch_4a7125503b2d7b30" in row["nodeIds"] for row in identity_issues),
                        "许玉春/李玉春 conflict must be queued")

    def test_identity_ledger_does_not_grow_on_repeated_contract(self):
        once = S._graph_contract(copy.deepcopy(v4_graph()))
        twice = S._graph_contract(copy.deepcopy(once))
        self.assertEqual(once["meta"]["identity"]["aliases"]["queue"], twice["meta"]["identity"]["aliases"]["queue"])
        self.assertEqual(once["meta"]["migrations"], twice["meta"]["migrations"])
        self.assertEqual(once["meta"]["identity"]["chapters"]["ids"], twice["meta"]["identity"]["chapters"]["ids"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
