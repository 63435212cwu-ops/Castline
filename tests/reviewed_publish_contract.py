#!/usr/bin/env python3
"""Reviewed publisher stays offline, versioned and source/identity validated."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import serve as S
spec = importlib.util.spec_from_file_location("reviewed_publisher_cli", ROOT / "tools/publish_reviewed.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


class ReviewedPublisherContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="castline-reviewed-pub-")
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)
        self.key = "1234abcd"
        self.quote = "甲打开古塔的门，终于救出了乙。"
        self.docs = [{"sourceId": "source-publish", "name": "原文", "text": self.quote}]
        self.graph = {"title": "审核测试", "characters": [{"id": "character", "name": "甲", "attrs": {"意志": {"score": 71}}},
                                                        {"id": "character-b", "name": "乙", "aliases": ["乙别名"]}],
                      "events": [{"id": "event", "order": 1, "chapter": "第一回", "quote": self.quote}],
                      "relations": [], "meta": {"model": "original-role-model"}}
        self.raw = json.dumps(self.graph, ensure_ascii=False, indent=3).encode()
        (self.cache / (self.key + ".json")).write_bytes(self.raw)
        (self.cache / (self.key + ".docs.json")).write_text(json.dumps(self.docs, ensure_ascii=False))
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        self.candidate = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
              "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
              "layers": {"tasks": [{"id": "reviewed-task", "name": "救乙", "character": "甲", "goal": "救出乙", "obstacle": "古塔门",
                      "action": "开门", "outcome": "乙获救", "cost": "未明示", "status": "completed", "outcomeEventId": "event",
                      "eventIds": ["event"], "quote": self.quote, "sourceRefs": [ref], "basis": "explicit", "claimVerified": False}]}}
        self.paths = patch.multiple(S, CACHE_DIR=str(self.cache), HIST_PATH=str(self.cache / "index.json"))
        self.paths.start(); self.addCleanup(self.paths.stop)
        self.network = patch.object(S.urllib.request, "urlopen", side_effect=AssertionError("NETWORK FORBIDDEN"))
        self.network.start(); self.addCleanup(self.network.stop)
        self.model = patch.object(S, "call_llm", side_effect=AssertionError("MODEL FORBIDDEN"))
        self.model.start(); self.addCleanup(self.model.stop)

    def publish(self, candidate=None, write=False):
        return S.publish_reviewed_graph(self.key, candidate or self.candidate, write=write, validator=P.validate)

    def relation_candidate(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["layers"] = {"relations": [{"id": "reviewed-relation", "a": "甲", "b": "乙", "kind": "救助", "line": "明线",
            "strength": 0.5, "desc": "甲救出了乙", "eventIds": ["event"], "quote": self.quote,
            "sourceRefs": copy.deepcopy(self.candidate["layers"]["tasks"][0]["sourceRefs"]), "claimVerified": False}]}
        return candidate

    def test_dry_run_validates_without_any_cache_write(self):
        before = sorted(path.name for path in self.cache.iterdir())
        result = self.publish()
        self.assertTrue(result["ok"])
        self.assertFalse(result["write"])
        self.assertEqual(sorted(path.name for path in self.cache.iterdir()), before)
        self.assertEqual((self.cache / (self.key + ".json")).read_bytes(), self.raw)

    def test_write_keeps_exact_original_and_old_role_model_and_records_manual_method(self):
        with patch.object(S, "history_add") as history:
            result = self.publish(write=True)
        self.assertTrue(result["write"])
        self.assertNotEqual(result["key"], self.key)
        stored = json.loads((self.cache / (result["key"] + ".json")).read_text())
        self.assertEqual(stored["meta"]["model"], "original-role-model")
        for name, values in self.graph["characters"][0]["attrs"].items():
            for field, value in values.items():
                self.assertEqual(stored["characters"][0]["attrs"][name][field], value)
        self.assertFalse(stored["characters"][0]["attrs"]["意志"]["claimVerified"])
        self.assertEqual(stored["meta"]["enrichment"]["method"], "assistant_source_review")
        self.assertIsNone(stored["meta"]["enrichment"]["model"])
        self.assertEqual(stored["meta"]["enrichment"]["modelCalls"], 0)
        self.assertFalse(stored["meta"]["enrichment"]["automaticModelQualityValidated"])
        self.assertFalse(stored["tasks"][0]["claimVerified"])
        self.assertEqual((self.cache / (self.key + ".json")).read_bytes(), self.raw)
        self.assertEqual(next((self.cache / "narrative/revisions").glob("*.graph.json")).read_bytes(), self.raw)
        history.assert_called_once()

    def test_fake_provenance_nonzero_model_count_or_missing_scope_cannot_publish(self):
        for changes in ({"provenance": "omen"}, {"modelCalls": 1}, {"scope": None}, {"sourceKey": "different"}, {"coverageGaps": {"fake": True}}):
            candidate = copy.deepcopy(self.candidate); candidate.update(changes)
            with self.subTest(changes=changes), self.assertRaises(S.ApiError):
                self.publish(candidate, write=True)
        self.assertFalse((self.cache / "narrative").exists())

    def test_review_history_keeps_each_scope_in_the_same_layer_and_repeated_publish_is_idempotent(self):
        first_candidate = copy.deepcopy(self.candidate)
        first_candidate["coverageGaps"] = ["只读第一处引句。"]
        with patch.object(S, "history_add"):
            first = self.publish(first_candidate, write=True)
            candidate = copy.deepcopy(self.candidate)
            candidate["sourceKey"] = first["key"]
            candidate["scope"]["name"] = "第二轮另一个声明范围"
            second = S.publish_reviewed_graph(first["key"], candidate, write=True, validator=P.validate)
            repeated = S.publish_reviewed_graph(first["key"], candidate, write=True, validator=P.validate)
        self.assertEqual(second["key"], repeated["key"])
        history = second["graph"]["meta"]["reviewHistory"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], first["graph"]["meta"]["reviewHistory"][0])
        self.assertEqual([entry["scope"] for entry in history], [first_candidate["scope"], candidate["scope"]])
        self.assertEqual([entry["layers"] for entry in history], [["tasks"], ["tasks"]])
        self.assertEqual(history[0]["coverageGaps"], first_candidate["coverageGaps"])
        self.assertEqual(history[1]["candidateDigest"], S.NARRATIVE.digest(candidate))
        self.assertEqual(history[1]["sourceKey"], first["key"])
        self.assertTrue(all(entry["applicability"] == "current" and entry["scopeVerification"] == "declared_only"
                            and entry["semanticCompleteness"] == "unverified" for entry in history))
        self.assertEqual(second["graph"]["meta"]["enrichment"]["scope"], candidate["scope"])
        self.assertEqual(second["graph"]["meta"]["coverage"]["tasks"]["scope"], candidate["scope"])

    def test_legacy_scope_merge_is_conservative_and_is_not_migrated_again(self):
        source = S.source_specs(self.docs)[0]
        bound = {"sourceId": source["id"], "textHash": source["textHash"], "chapters": [1], "wholeNovelVerbatimRead": False}
        unbound = {"fullEpisodeRead": ["某旧片段"], "wholeNovelVerbatimRead": False}
        graph = copy.deepcopy(self.graph)
        graph["meta"].update({"sources": [{"id": source["id"], "textHash": source["textHash"]}],
            "enrichment": {"method": "assistant_source_review", "layers": ["tasks"], "scope": bound,
                           "sourceAndIdentityContractValidated": True, "coverageGaps": ["旧声明未覆全文"]},
            "coverage": {"tasks": {"scope": bound}, "causeEdges": {"scope": bound},
                         "clues": {"scope": unbound}, "characterStates": {"scope": unbound}}})
        before = copy.deepcopy(graph)
        legacy = S.review_history(graph, self.docs, self.key)
        self.assertEqual(graph, before, "migration is a pure view and does not edit its graph")
        self.assertEqual(len(legacy), 2)
        self.assertEqual(legacy[0]["layers"], ["tasks", "causeEdges"])
        self.assertEqual(legacy[0]["legacyOrigins"], ["coverage.causeEdges", "coverage.tasks", "enrichment"])
        self.assertEqual(legacy[0]["applicability"], "current")
        self.assertEqual(legacy[1]["sources"], [])
        self.assertEqual(legacy[1]["applicability"], "source_unbound")
        self.assertTrue(all(entry["origin"] == "legacy_metadata" and entry["candidateDigest"] is None
                            and entry["sourceAndIdentityContractValidated"] is False for entry in legacy))
        (self.cache / (self.key + ".json")).write_text(json.dumps(graph, ensure_ascii=False))
        published = self.publish()["graph"]
        self.assertEqual(len(published["meta"]["reviewHistory"]), 3)
        self.assertEqual(S.review_history(published, self.docs, self.key), published["meta"]["reviewHistory"])
        published["meta"]["reviewHistory"].append(copy.deepcopy(legacy[0]))
        self.assertEqual(len(S.review_history(published, self.docs, self.key)), 3, "duplicate stored ID adds no review")

    def test_changed_source_hash_keeps_old_history_but_excludes_its_current_applicability(self):
        first = self.publish()["graph"]
        old = copy.deepcopy(first["meta"]["reviewHistory"][0])
        docs = copy.deepcopy(self.docs)
        docs[0]["text"] += "后加的句子改变了原文版本。"
        candidate = copy.deepcopy(self.candidate)
        ref = S.Corpus("", S.source_specs(docs)).anchor(self.quote)
        candidate["layers"]["tasks"][0]["sourceRefs"] = [ref]
        candidate["scope"].update(sourceId=ref["sourceId"], textHash=ref["textHash"])
        (self.cache / (self.key + ".json")).write_text(json.dumps(first, ensure_ascii=False))
        (self.cache / (self.key + ".docs.json")).write_text(json.dumps(docs, ensure_ascii=False))
        history = self.publish(candidate)["graph"]["meta"]["reviewHistory"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], dict(old, applicability="source_changed"))
        self.assertEqual(history[1]["applicability"], "current")
        self.assertNotEqual(history[0]["sources"], history[1]["sources"])
        changed_id = copy.deepcopy(self.docs)
        changed_id[0]["sourceId"] = "different-source-with-identical-text"
        self.assertEqual(S.review_history(first, changed_id, self.key)[0]["applicability"], "source_changed")

    def test_invalid_history_is_rejected_without_regeneration_or_source_repair(self):
        valid = self.publish()["graph"]["meta"]["reviewHistory"][0]
        damaged = [None, {}, [None], [{}]]
        for changes in ({"candidateDigest": "not-a-digest"}, {"id": "forged"}, {"layers": ["made-up"]},
                        {"scopeVerification": "independently_verified"}, {"semanticCompleteness": "complete"},
                        {"sourceAndIdentityContractValidated": False}, {"sources": []}, {"claimVerified": True},
                        {"sources": [{"sourceId": "source-publish", "textHash": "fake"}]}):
            damaged.append([dict(copy.deepcopy(valid), **changes)])
        recomputed = dict(copy.deepcopy(valid), semanticCompleteness="complete")
        recomputed["id"] = S._review_history_id(recomputed)
        damaged.append([recomputed])
        for history in damaged:
            graph = copy.deepcopy(self.graph)
            graph["meta"]["reviewHistory"] = history
            graph["meta"]["enrichment"] = {"method": "assistant_source_review", "scope": self.candidate["scope"], "layers": ["tasks"]}
            raw = json.dumps(graph, ensure_ascii=False).encode()
            (self.cache / (self.key + ".json")).write_bytes(raw)
            with self.subTest(history=history), self.assertRaisesRegex(S.ApiError, "reviewHistory"):
                self.publish(write=True)
            self.assertEqual((self.cache / (self.key + ".json")).read_bytes(), raw)
            self.assertFalse((self.cache / "narrative").exists())

    def test_scope_with_stale_or_partial_source_binding_cannot_be_rebound_to_current_text(self):
        source = S.source_specs(self.docs)[0]
        for binding in ({"sourceId": source["id"], "textHash": "0" * 64}, {"sourceId": "missing", "textHash": source["textHash"]},
                        {"sourceId": source["id"]}, {"textHash": source["textHash"]}):
            candidate = copy.deepcopy(self.candidate)
            candidate["scope"].update(binding)
            with self.subTest(binding=binding), self.assertRaisesRegex(S.ApiError, "scope原文版本"):
                self.publish(candidate, write=True)
        self.assertFalse((self.cache / "narrative").exists())

    def test_real_books_legacy_scopes_remain_declarations_without_parent_cache_reads(self):
        for key, count in (("f0b45e85aac6c95e584075a2", 1), ("df959d743e53206f56db2f92", 2), ("9b676d7031b1bcd3b8377a18", 1)):
            graph = json.loads((ROOT / "data/cache" / (key + ".json")).read_text())
            docs = json.loads((ROOT / "data/cache" / (key + ".docs.json")).read_text())
            with self.subTest(key=key), patch("builtins.open", side_effect=AssertionError("PARENT CACHE READ FORBIDDEN")):
                history = S.review_history(graph, docs, key)
            self.assertEqual(len(history), count)
            self.assertTrue(all(entry["scopeVerification"] == "declared_only" and entry["origin"] == "legacy_metadata" for entry in history))
            if key == "df959d743e53206f56db2f92":
                unbound = [entry for entry in history if entry["applicability"] == "source_unbound"]
                self.assertEqual(len(unbound), 1)
                self.assertEqual(set(unbound[0]["layers"]), {"storylines", "tasks", "causeEdges", "clues", "characterStates"})

    def test_no_validator_unknown_ids_fake_hash_and_wrong_quote_are_rejected(self):
        with self.assertRaises(S.ApiError):
            S.publish_reviewed_graph(self.key, self.candidate, write=True)
        for field, value in (("eventIds", ["missing"]), ("quote", "根本不存在的引句")):
            candidate = copy.deepcopy(self.candidate);candidate["layers"]["tasks"][0][field] = value
            with self.subTest(field=field), self.assertRaises(S.ApiError):
                self.publish(candidate, write=True)
        candidate = copy.deepcopy(self.candidate)
        candidate["layers"]["tasks"][0]["sourceRefs"][0]["textHash"] = "fake"
        with self.assertRaises(S.ApiError):
            self.publish(candidate, write=True)
        self.assertFalse((self.cache / "narrative").exists())

    def test_explicit_unresolved_or_declared_endpoint_conflict_never_writes(self):
        graph = copy.deepcopy(self.graph)
        graph["events"].append({"id": "event-two", "order": 2, "quote": self.quote})
        (self.cache / (self.key + ".json")).write_text(json.dumps(graph, ensure_ascii=False))
        candidate = copy.deepcopy(self.candidate)
        candidate["layers"]["causeEdges"] = [{"id": "cause", "fromEventId": "event", "toEventId": "event-two",
                   "declaredSourceId": "event-two", "sourceId": None, "referenceStatus": "unresolved", "resolved": True,
                   "description": "测试冲突", "quote": self.quote, "sourceRefs": candidate["layers"]["tasks"][0]["sourceRefs"]}]
        with self.assertRaises(S.ApiError):
            self.publish(candidate, write=True)
        self.assertFalse((self.cache / "narrative").exists())

    def test_original_changed_or_backup_mismatch_prevents_publication(self):
        original_raw = self.raw
        (self.cache / (self.key + ".json")).write_bytes(b"changed")
        with self.assertRaises(S.ApiError):
            S._publish_graph_revision(self.key, original_raw, self.graph, self.docs, "test")
        (self.cache / (self.key + ".json")).write_bytes(original_raw)
        import hashlib
        folder = self.cache / "narrative/revisions";folder.mkdir(parents=True)
        (folder / (self.key + "-" + hashlib.sha256(original_raw).hexdigest()[:20] + ".graph.json")).write_bytes(b"wrong backup")
        with self.assertRaises(S.ApiError):
            self.publish(write=True)
        self.assertFalse(any(path.name != self.key + ".json" and not path.name.endswith(".docs.json") for path in self.cache.glob("*.json")))

    def test_review_issues_and_units_are_preserved_without_rewriting_original_values(self):
        candidate = copy.deepcopy(self.candidate)
        source_ref = candidate["layers"]["tasks"][0]["sourceRefs"][0]
        candidate["narrativeUnits"] = [{"id": "unit", "eventIds": ["event"], "goal": "救乙", "sourceRefs": [source_ref]}]
        candidate["reviewIssues"] = [
            {"id": "identity-issue", "kind": "identity", "characterId": "character", "eventIds": ["event"],
             "status": "confirmed_issue", "description": "原人物有身份混并待分辨", "sourceRefs": [source_ref], "scope": {"eventIds": ["event"]}},
            {"id": "quote-issue", "kind": "quote", "eventId": "event", "eventIds": [],
             "status": "confirmed_issue", "description": "本测试保留误场景引用审核门", "quoteReview": "wrong-scene-and-speaker",
             "sourceRefs": [source_ref], "scope": {"eventIds": ["event"]}},
        ]
        result = self.publish(candidate)
        graph = result["graph"]
        self.assertEqual(len(graph["reviewIssues"]), 2)
        self.assertEqual(graph["narrativeUnits"][0]["id"], "unit")
        self.assertEqual(graph["characters"][0]["identityStatus"], "ambiguous")
        self.assertEqual(graph["characters"][0]["attrs"]["意志"]["score"], 71)
        self.assertEqual(graph["events"][0]["quote"], self.quote)
        self.assertEqual(graph["events"][0]["quoteReview"], "wrong-scene-and-speaker")
        self.assertFalse(graph["events"][0]["verified"])
        again = S.rebuild_sources(graph, self.docs)
        self.assertFalse(again["events"][0]["verified"])
        self.assertFalse(again["events"][0]["quoteRef"]["verified"])
        self.assertEqual(again["events"][0]["quote"], self.quote)

    def test_review_issue_unknown_entity_invalid_reference_or_duplicate_id_is_rejected(self):
        source_ref = self.candidate["layers"]["tasks"][0]["sourceRefs"][0]
        issue = {"id": "issue", "kind": "identity", "characterId": "character", "eventIds": ["event"],
                 "status": "confirmed_issue", "description": "需核身份", "sourceRefs": [source_ref], "scope": {"eventIds": ["event"]}}
        for patch_ in ({"characterId": "missing"}, {"eventIds": ["missing"]}, {"sourceRefs": []}):
            candidate = copy.deepcopy(self.candidate)
            candidate["reviewIssues"] = [dict(issue, **patch_)]
            with self.subTest(patch=patch_), self.assertRaises(S.ApiError):
                self.publish(candidate, write=True)
        candidate = copy.deepcopy(self.candidate);candidate["reviewIssues"] = [issue, issue]
        with self.assertRaises(S.ApiError):
            self.publish(candidate, write=True)

    def test_relation_endpoints_events_and_exact_sources_are_in_publication_statistics(self):
        result = self.publish(self.relation_candidate())
        report = result["validation"]
        self.assertTrue(result["ok"])
        self.assertEqual(report["layerCounts"]["relations"], {"scopedNodes": 1, "validReferenceNodes": 1})
        self.assertEqual(report["referencePrecision"], {"valid": 3, "declared": 3, "percent": 100.0})
        self.assertEqual(report["sourceAnchorCoverage"], {"exact": 1, "supplied": 1, "percent": 100.0})
        self.assertFalse(report["semanticClaimsAutomaticallyVerified"])

    def test_relation_unknown_self_or_ambiguous_characters_never_publish(self):
        for changes in ({"a": "不存在的人物"}, {"b": "甲"}):
            candidate = self.relation_candidate(); candidate["layers"]["relations"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(S.ApiError):
                self.publish(candidate, write=True)
        graph = copy.deepcopy(self.graph)
        graph["characters"].append({"id": "ambiguous", "name": "丙", "aliases": ["乙"]})
        (self.cache / (self.key + ".json")).write_text(json.dumps(graph, ensure_ascii=False))
        with self.assertRaises(S.ApiError):
            self.publish(self.relation_candidate(), write=True)
        self.assertFalse((self.cache / "narrative").exists())

    def test_relation_missing_or_invalid_event_ids_never_publish(self):
        for event_ids in ([], None, "event", ["missing"], ["event", "missing"]):
            candidate = self.relation_candidate(); candidate["layers"]["relations"][0]["eventIds"] = event_ids
            with self.subTest(event_ids=event_ids), self.assertRaises(S.ApiError):
                self.publish(candidate, write=True)
        self.assertFalse((self.cache / "narrative").exists())

    def test_relation_duplicate_ids_or_duplicate_pair_type_line_never_merge_silently(self):
        for same_id in (True, False):
            candidate = self.relation_candidate()
            duplicate = copy.deepcopy(candidate["layers"]["relations"][0])
            duplicate.update(a="乙", b="甲")
            if not same_id:
                duplicate["id"] = "different-id-same-relation"
            candidate["layers"]["relations"].append(duplicate)
            with self.subTest(same_id=same_id), self.assertRaises(S.ApiError):
                self.publish(candidate, write=True)
        self.assertFalse((self.cache / "narrative").exists())

    def test_relation_forged_source_refs_or_semantic_verified_claim_never_publish(self):
        for changes in ({"textHash": "forged"}, {"start": 1}, {"quote": "不存在的引用"},
                        {"sourceId": "missing"}, {"offsetUnit": "utf16"}):
            candidate = self.relation_candidate()
            candidate["layers"]["relations"][0]["sourceRefs"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(S.ApiError):
                self.publish(candidate, write=True)
        candidate = self.relation_candidate()
        relation = candidate["layers"]["relations"][0]
        relation["sourceRefs"].append(dict(relation["sourceRefs"][0], textHash="forged", verified=False, status="unverified"))
        with self.assertRaises(S.ApiError):
            self.publish(candidate, write=True)
        candidate = self.relation_candidate(); candidate["layers"]["relations"][0]["claimVerified"] = True
        with self.assertRaises(S.ApiError):
            self.publish(candidate, write=True)
        self.assertFalse((self.cache / "narrative").exists())

    def test_relation_invalid_ids_cannot_escape_validation_with_a_second_original_source(self):
        second = {"sourceId": "source-second", "name": "另一篇原文", "text": "甲曾经帮助过乙。"}
        docs = self.docs + [second]
        (self.cache / (self.key + ".docs.json")).write_text(json.dumps(docs, ensure_ascii=False))
        ref = S.Corpus("", S.source_specs(docs)).anchor(second["text"])
        candidate = self.relation_candidate()
        candidate["layers"]["relations"][0].update(eventIds=["missing"], quote=second["text"], sourceRefs=[ref])
        with self.assertRaises(S.ApiError):
            self.publish(candidate, write=True)
        self.assertFalse((self.cache / "narrative").exists())

    def supplementary_fixture(self):
        extra = "乙脱险后将密信交给甲，说明了古塔的来历。"
        docs = [{"sourceId": "source-publish", "name": "原文", "text": self.quote + "\n" + extra}]
        corpus = S.Corpus("", S.source_specs(docs))
        refs = [corpus.anchor(self.quote), corpus.anchor(extra)]
        graph = copy.deepcopy(self.graph)
        graph["events"][0]["sourceRefs"] = copy.deepcopy(refs)
        graph["events"].append({"id": "event-two", "order": 2, "quote": extra, "sourceRefs": copy.deepcopy(refs)})
        graph["characters"][0]["sourceRefs"] = copy.deepcopy(refs)
        graph["characters"][0]["attrs"]["意志"].update(evidence=[self.quote], sourceRefs=copy.deepcopy(refs))
        graph["storylines"] = [{"id": "existing-line", "name": "救乙", "kind": "主线", "eventIds": ["event", "event-two"],
                                "events": [1, 2], "evidenceQuotes": [self.quote], "sourceRefs": copy.deepcopy(refs)}]
        task = copy.deepcopy(self.candidate["layers"]["tasks"][0])
        task.update(id="existing-task", sourceRefs=copy.deepcopy(refs))
        graph["tasks"] = [task]
        graph["causeEdges"] = [{"id": "existing-cause", "fromEventId": "event", "toEventId": "event-two",
                               "description": "获救后交信", "quote": self.quote, "sourceRefs": copy.deepcopy(refs)}]
        graph["clues"] = [{"id": "existing-clue", "seedEventId": "event", "payoffEventId": "event-two",
                           "seedQuote": self.quote, "payoffQuote": extra, "status": "resolved", "sourceRefs": copy.deepcopy(refs)}]
        graph["characterStates"] = [{"id": "existing-state", "character": "甲", "characterId": "character", "eventId": "event-two",
                                     "quote": extra, "sourceRefs": copy.deepcopy(refs),
                                     "attributes": [{"name": "持物", "value": "密信", "quote": extra, "sourceRefs": copy.deepcopy(refs)}]}]
        graph["relations"] = [{"id": "existing-relation", "a": "甲", "b": "乙", "kind": "救助", "line": "明线",
                               "eventIds": ["event"], "quote": self.quote, "sourceRefs": copy.deepcopy(refs)}]
        for layer in ("locations", "items", "worldRules", "narrativeUnits", "reviewIssues"):
            graph[layer] = [{"id": "existing-" + layer, "quote": self.quote, "sourceRefs": copy.deepcopy(refs)}]
        return graph, docs, refs

    def valid_source_refs_by_node(self, graph, docs):
        sources = P.E.sources_for(docs)
        result = {}

        def walk(value, path=()):
            if isinstance(value, dict):
                refs = value.get("sourceRefs", [])
                valid = {tuple(ref.get(key) for key in ("sourceId", "textHash", "start", "end", "quote", "offsetUnit"))
                         for ref in refs if P.E.check_anchor(ref, sources)[0]}
                if valid:
                    result[path] = valid
                for key, item in value.items():
                    if key not in ("sourceRefs", "evidenceRefs", "quoteRef", "evidenceRef", "sourceRef", "meta"):
                        walk(item, path + (key,))
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, path + (index,))
        walk(graph)
        return result

    def test_rebuild_and_publication_preserve_every_nodes_valid_supplementary_reference(self):
        graph, docs, refs = self.supplementary_fixture()
        before = copy.deepcopy(graph)
        expected = self.valid_source_refs_by_node(graph, docs)
        rebuilt = S.rebuild_sources(graph, docs)
        self.assertEqual(graph, before)
        self.assertEqual(self.valid_source_refs_by_node(rebuilt, docs), expected)
        self.assertEqual(self.valid_source_refs_by_node(S.rebuild_sources(rebuilt, docs), docs), expected)
        self.assertGreater(rebuilt["meta"]["sourceRebuild"]["preservedSupplementaryRefs"], 0)
        raw = json.dumps(graph, ensure_ascii=False).encode()
        (self.cache / (self.key + ".json")).write_bytes(raw)
        (self.cache / (self.key + ".docs.json")).write_text(json.dumps(docs, ensure_ascii=False))
        candidate = copy.deepcopy(self.candidate)
        candidate["layers"]["tasks"][0]["sourceRefs"] = copy.deepcopy(refs)
        with patch.object(S, "history_add"):
            result = self.publish(candidate, write=True)
        published = json.loads((self.cache / (result["key"] + ".json")).read_text())
        actual = self.valid_source_refs_by_node(published, docs)
        for node, values in expected.items():
            self.assertEqual(actual[node], values, node)
        self.assertEqual(len(published["tasks"][-1]["sourceRefs"]), 2, "incoming candidate's supplement is also retained")
        self.assertEqual((self.cache / (self.key + ".json")).read_bytes(), raw)

    def test_invalid_supplementary_refs_are_never_researched_and_promoted(self):
        graph, docs, refs = self.supplementary_fixture()
        extra = refs[1]["quote"]
        mutations = ({"textHash": "forged-or-stale-hash"}, {"start": 0, "end": len(extra)},
                     {"sourceId": "missing-source"}, {"quote": "原文没有的补充证词"},
                     {"offsetUnit": "utf16"}, {"start": True}, {"verified": False, "status": "unverified"},
                     {"match": "normalized"})
        for change in mutations:
            sample = copy.deepcopy(graph)
            bad = dict(refs[1], **change)
            sample["tasks"][0]["sourceRefs"] = [refs[0], bad]
            sample["narrativeUnits"][0]["sourceRefs"] = [bad]
            sample["narrativeUnits"][0]["quoteRef"] = copy.deepcopy(bad)
            with self.subTest(change=change):
                rebuilt = S.rebuild_sources(sample, docs)
                task_refs = rebuilt["tasks"][0]["sourceRefs"]
                self.assertEqual([ref["quote"] for ref in task_refs], [self.quote])
                self.assertFalse(any(ref.get("verified") for ref in rebuilt["narrativeUnits"][0]["sourceRefs"]))
                self.assertFalse(rebuilt["narrativeUnits"][0]["quoteRef"]["verified"])
        changed_docs = copy.deepcopy(docs)
        changed_docs[0]["text"] = "文首新加入的一行。\n" + changed_docs[0]["text"]
        rebuilt = S.rebuild_sources(graph, changed_docs)
        self.assertFalse(any(ref.get("quote") == extra for ref in rebuilt["tasks"][0]["sourceRefs"]),
                         "the same supplementary sentence in a different source version is not silently relocated")

    def test_multiple_exact_locations_for_one_supplement_are_all_preserved(self):
        extra = "乙终于走出了古塔。"
        docs = [{"sourceId": "source-publish", "text": self.quote + extra + extra}]
        source = S.source_specs(docs)[0]
        supplements = [{"quote": extra, "sourceId": source["id"], "textHash": source["textHash"],
                        "start": start, "end": start + len(extra), "offsetUnit": "codepoint",
                        "match": "exact", "verified": True, "status": "verified"}
                       for start in (len(self.quote), len(self.quote) + len(extra))]
        graph = copy.deepcopy(self.graph)
        task = copy.deepcopy(self.candidate["layers"]["tasks"][0])
        task["sourceRefs"] = supplements
        graph["tasks"] = [task]
        restored = S.rebuild_sources(graph, docs)["tasks"][0]["sourceRefs"]
        self.assertEqual({ref["start"] for ref in restored if ref["quote"] == extra},
                         {ref["start"] for ref in supplements})

    def test_quote_review_blocks_primary_and_preserved_supplementary_refs(self):
        graph, docs, refs = self.supplementary_fixture()
        for layer in ("events", "tasks", "relations"):
            graph[layer][0]["quoteReview"] = "wrong-scene-and-speaker"
        rebuilt = S.rebuild_sources(graph, docs)
        for _ in range(2):
            for layer in ("events", "tasks", "relations"):
                item = rebuilt[layer][0]
                self.assertFalse(item["quoteVerified"], layer)
                self.assertFalse(item["claimVerified"], layer)
                self.assertEqual({ref["quote"] for ref in item["sourceRefs"]}, {ref["quote"] for ref in refs})
                self.assertTrue(all(ref["verified"] is False and ref["locatorOnly"] for ref in item["sourceRefs"]), layer)
            rebuilt = S.rebuild_sources(rebuilt, docs)

    def test_original_xiyou_supplementary_refs_survive_offline_rebuild(self):
        key = "c84e8657afff87043c11ae57"
        graph = json.loads((ROOT / "data/cache" / (key + ".json")).read_text())
        docs = json.loads((ROOT / "data/cache" / (key + ".docs.json")).read_text())
        expected = self.valid_source_refs_by_node(graph, docs)
        rebuilt = S.rebuild_sources(graph, docs)
        actual = self.valid_source_refs_by_node(rebuilt, docs)
        for node, refs in expected.items():
            self.assertTrue(refs <= actual.get(node, set()), node)
        for layer, node_id in (("tasks", "reviewed-task-rescue"), ("causeEdges", "reviewed-cause-guard-strategy")):
            node = next(node for node in rebuilt[layer] if node["id"] == node_id)
            self.assertEqual(len(node["sourceRefs"]), 3)

    def test_same_candidate_changed_rebuild_output_gets_new_immutable_revision(self):
        with patch.object(S, "history_add"):
            first = self.publish(write=True)
            first_path = self.cache / (first["key"] + ".json")
            first_raw = first_path.read_bytes()
            rebuild = S.rebuild_sources

            def changed_policy(graph, docs):
                value = rebuild(graph, docs)
                value["meta"]["sourceRebuild"]["supplementaryPolicy"] = "newly-reviewed-source-preservation-policy"
                return value

            with patch.object(S, "rebuild_sources", side_effect=changed_policy):
                second = self.publish(write=True)
        self.assertNotEqual(first["key"], second["key"])
        self.assertEqual(first_path.read_bytes(), first_raw)
        self.assertEqual((self.cache / (self.key + ".json")).read_bytes(), self.raw)
        stored = json.loads((self.cache / (second["key"] + ".json")).read_text())
        self.assertNotEqual(stored["meta"]["revision"]["outputHash"], first["graph"]["meta"]["revision"]["outputHash"])

    def test_same_output_is_idempotent_even_with_revision_metadata_already_attached(self):
        with patch.object(S, "history_add"):
            first = self.publish(write=True)
            path = self.cache / (first["key"] + ".json")
            original = path.read_bytes()
            modified_time = path.stat().st_mtime_ns
            second = self.publish(write=True)
            self.assertEqual(first["key"], second["key"])
            seed = {"reviewedCandidate": S.NARRATIVE.digest(self.candidate), "method": "assistant_source_review"}
            repeated = S._publish_graph_revision(self.key, self.raw, first["graph"], self.docs, seed)
        self.assertEqual(repeated, first["key"], "meta.revision is excluded from its own content identity")
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(path.stat().st_mtime_ns, modified_time, "idempotent publication does not rewrite the existing file")

    def test_existing_revision_with_conflicting_graph_or_docs_bytes_is_never_overwritten(self):
        with patch.object(S, "history_add"):
            first = self.publish(write=True)
        graph_path = self.cache / (first["key"] + ".json")
        docs_path = self.cache / (first["key"] + ".docs.json")
        graph_bytes, docs_bytes = graph_path.read_bytes(), docs_path.read_bytes()
        for path, other_path, expected_other in ((graph_path, docs_path, docs_bytes), (docs_path, graph_path, graph_bytes)):
            with self.subTest(path=path.name):
                graph_path.write_bytes(graph_bytes); docs_path.write_bytes(docs_bytes)
                path.write_bytes(b"conflicting-published-bytes")
                with patch.object(S, "history_add") as history, self.assertRaisesRegex(S.ApiError, "拒绝覆盖"):
                    self.publish(write=True)
                history.assert_not_called()
                self.assertEqual(path.read_bytes(), b"conflicting-published-bytes")
                self.assertEqual(other_path.read_bytes(), expected_other)



    def alias_candidate(self, quote, refs, remove=("乙别名",)):
        candidate = copy.deepcopy(self.candidate)
        candidate["characterAliasFixes"] = [{"characterId": "character-b", "removeAliases": list(remove),
                                              "quote": quote, "sourceRefs": refs}]
        return candidate

    def test_alias_fix_with_fabricated_quote_is_rejected(self):
        """原文中不存在的 quote 不得当作反证 —— 这是复评实测过的那条洞。"""
        fabricated = "这句话在原书里根本不存在完全是我编的"
        self.assertNotIn(fabricated, self.docs[0]["text"])
        with self.assertRaises(S.ApiError):
            self.publish(self.alias_candidate(fabricated, [{"quote": fabricated}]))

    def test_alias_fix_requires_a_real_exact_anchored_reference(self):
        """真 quote 但引用未锚定（无起止/hash/verified）也必须拒绝。"""
        with self.assertRaises(S.ApiError):
            self.publish(self.alias_candidate(self.quote, [{"quote": self.quote}]))
        with self.assertRaises(S.ApiError):
            self.publish(self.alias_candidate(self.quote, [{}]))

    def test_alias_fix_with_real_anchored_quote_is_accepted_and_logged(self):
        """正例：真 quote + 合法锚点 ⇒ 接受，移除别名，且留下可追溯的 identity issue。"""
        anchored = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        result = self.publish(self.alias_candidate(self.quote, [anchored]))
        self.assertTrue(result["ok"])
        issues = [i for i in result["graph"].get("reviewIssues", []) if i.get("kind") == "identity"]
        self.assertTrue(issues, "身份修正必须留下可追溯的 reviewIssue")
        self.assertEqual(issues[0].get("quote"), self.quote)


    def _pad_first_task(self, candidate, pad="    "):
        for node in candidate["layers"]["tasks"]:
            if node.get("id") == "reviewed-task":
                node["quote"] = pad + node["quote"]
        return candidate

    def quote_fix_candidate(self, node_id="reviewed-task", pad="    ", break_char=False):
        candidate = copy.deepcopy(self.candidate)
        candidate["quoteTextFixes"] = [{"layer": "tasks", "id": node_id}]
        if node_id == "reviewed-task" and not break_char:
            self._pad_first_task(candidate, pad)
        if break_char:
            for node in candidate["layers"]["tasks"]:
                if node.get("id") == "reviewed-task":
                    node["quote"] = node["quote"][:-1] + "错"
        return candidate

    def test_quote_fix_converges_padded_quote_to_the_reference_slice(self):
        """正例：quote 首部多出空白 ⇒ 收敛为 text[start:end]，并记账。"""
        result = self.publish(self.quote_fix_candidate(pad="    "))
        self.assertTrue(result["ok"], result.get("error"))
        tasks = {str(t.get("id")): t for t in result["graph"].get("tasks", [])}
        self.assertFalse(str(tasks["reviewed-task"].get("quote", "")).startswith("    "),
                         "引文的前导空白必须被收敛掉")
        self.assertEqual(result["graph"]["meta"].get("quoteTextFixCount"), 1)

    def test_quote_fix_rejects_a_diff_that_is_not_whitespace(self):
        """反例：差异**不只是空白** ⇒ 必须拒（可能是真引文问题，需人工审）。"""
        with self.assertRaises(S.ApiError):
            self.publish(self.quote_fix_candidate(break_char=True))

    def test_quote_fix_rejects_unknown_node_and_missing_reference(self):
        """反例：节点不存在 / 没有可用偏移 ⇒ 都必须拒。"""
        with self.assertRaises(S.ApiError):
            self.publish(self.quote_fix_candidate(node_id="reviewed-根本不存在"))
        candidate = self.quote_fix_candidate(pad="    ")
        for node in candidate["layers"]["tasks"]:
            if node.get("id") == "reviewed-task":
                node.pop("quoteRef", None)
                node["sourceRefs"] = [{"start": None, "end": None}]
        with self.assertRaises(S.ApiError):
            self.publish(candidate)

    def test_quote_fix_rejects_non_whitespace_diff_on_an_upstream_node(self):
        """**合并后**路径的反例：上游既有节点的引文若与切片差异不只是空白，必须拒。

        这条覆盖第二道闸门 —— 预归一阶段只动「候选自带层」，
        上游既有节点走的是合并后的检查；只测前者会让后者无人看守（变异实测逃逸过）。"""
        candidate = copy.deepcopy(self.candidate)
        self.graph["events"][0]["quote"] = self.quote
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        self.graph["events"][0]["quoteRef"] = ref
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        tampered = dict(self.graph["events"][0])
        tampered["quote"] = self.quote[:-1] + "错"
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(dict(self.graph, events=[tampered]), ensure_ascii=False, indent=3).encode())
        candidate["layers"] = {"events": [dict(tampered)]}
        candidate["quoteTextFixes"] = [{"layer": "events", "id": "event"}]
        with self.assertRaises(S.ApiError):
            self.publish(candidate)

    def test_layerless_fix_does_not_write_an_empty_layer_history_entry(self):
        """**空层历史会锁死整条发布链**（实测发生过）。

        `quoteTextFixes` 型候选不触碰任何叙事层 ⇒ `layers` 为空；
        而 `review_history()` 要求 `layers` 非空。若放任它落盘，
        **下一次**发布读回就报「无效reviewHistory记录；未清洗或发布」。
        本用例锁住：修完之后立刻再发一次普通批次，必须仍然成功。"""
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        self.graph["tasks"] = [{"id": "up-task", "name": "救乙", "character": "甲", "goal": "救出乙",
                                "obstacle": "古塔门", "action": "开门", "outcome": "乙获救", "cost": "未明示",
                                "status": "completed", "outcomeEventId": "event", "eventIds": ["event"],
                                "quote": "    " + self.quote, "quoteRef": ref, "sourceRefs": [ref]}]
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        candidate = copy.deepcopy(self.candidate)
        candidate.pop("layers", None)
        candidate["quoteTextFixes"] = [{"layer": "tasks", "id": "up-task"}]
        first = self.publish(candidate)
        self.assertTrue(first["ok"], first.get("error"))
        hist = (first["graph"].get("meta") or {}).get("reviewHistory") or []
        empty = [e for e in hist if isinstance(e, dict) and not e.get("layers")]
        self.assertEqual(empty, [], "不得写入空层历史条目")
        try:
            S.review_history(first["graph"], self.docs, self.key)
        except S.ApiError as exc:
            self.fail("读回历史失败，整条发布链会被锁死：" + str(exc))

    def test_normalized_ref_fix_never_writes_offsets(self):
        """补「归一化引用」**必须不带偏移** —— 这是既有安全设计的硬线。

        `Corpus._anchor` 的注释写明：归一化命中的引用要显式 `unverified` 且
        **没有 start/end**，否则调用方会把「推断位置」误当「源位置」。
        本用例锁住这条：补进去的引用必须 match=normalized、verified=false、且无 start。"""
        text = "甲打开古塔的门，终于救出了乙。"
        odd = "甲打开古塔的门,终于救出了乙。"
        self.docs[0]["text"] = text
        (self.cache / (self.key + ".docs.json")).write_text(json.dumps(self.docs, ensure_ascii=False))
        self.graph["tasks"] = [{"id": "up-norm", "name": "救乙", "character": "甲", "goal": "救出乙",
                                "obstacle": "古塔门", "action": "开门", "outcome": "乙获救", "cost": "未明示",
                                "status": "completed", "outcomeEventId": "event", "eventIds": ["event"],
                                "quote": odd}]
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        candidate = copy.deepcopy(self.candidate)
        candidate.pop("layers", None)
        candidate["normalizedRefFixes"] = [{"layer": "tasks", "id": "up-norm"}]
        result = self.publish(candidate)
        self.assertTrue(result["ok"], result.get("error"))
        tasks = {str(t.get("id")): t for t in result["graph"].get("tasks", [])}
        refs = [r for r in (tasks["up-norm"].get("sourceRefs") or []) if isinstance(r, dict)]
        added = [r for r in refs if r.get("match") == "normalized"]
        self.assertTrue(added, "应当补上一条 normalized 引用")
        for r in added:
            self.assertIsNot(r.get("verified"), True, "归一化引用不得标为已验证")
            self.assertNotIn("start", r, "**归一化引用绝不能带 start** —— 那会把推断位置冒充源位置")
            self.assertNotIn("end", r, "**归一化引用绝不能带 end**")

    def test_normalized_ref_fix_rejects_a_non_unique_match(self):
        """归一化命中**不唯一**时必须拒 —— 位置无意义，补了就是误导。"""
        dup = "甲打开古塔的门，终于救出了乙。"
        self.docs[0]["text"] = dup + "\n\n" + dup
        (self.cache / (self.key + ".docs.json")).write_text(json.dumps(self.docs, ensure_ascii=False))
        self.graph["tasks"] = [{"id": "up-dup", "name": "救乙", "character": "甲", "goal": "救出乙",
                                "obstacle": "古塔门", "action": "开门", "outcome": "乙获救", "cost": "未明示",
                                "status": "completed", "outcomeEventId": "event", "eventIds": ["event"],
                                "quote": "甲打开古塔的门,终于救出了乙。"}]
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        candidate = copy.deepcopy(self.candidate)
        candidate.pop("layers", None)
        candidate["normalizedRefFixes"] = [{"layer": "tasks", "id": "up-dup"}]
        with self.assertRaises(S.ApiError):
            self.publish(candidate)


    def _replacement_candidate(self, *, new_quote=None, declare=True, good_old=True):
        """构造一个「替换已发布事件」的候选：旧版坏（偏移错）、新版好。

        **关键**：旧版的坏必须是**真实那种坏** —— 引文带首部缩进、而偏移指向
        「不含缩进」的位置。实测这种矛盾 `rebuild_sources` **不会**自动修正
        （它只在引文不带首部空白时才把偏移拉回 0），所以它能真实复现那 47 条。
        """
        padded = "    " + self.quote
        self.docs[0]["text"] = padded
        (self.cache / (self.key + ".docs.json")).write_text(json.dumps(self.docs, ensure_ascii=False))
        _base = S.Corpus("", S.source_specs(self.docs)).anchor(padded)
        ref_good = dict(_base); ref_good["start"] = 0; ref_good["end"] = len(padded)
        ref_good["quote"] = padded
        bad = dict(_base); bad["quote"] = padded
        self.graph["events"][0]["quote"] = padded
        self.graph["events"][0]["quoteRef"] = bad if good_old else ref_good
        self.graph["events"][0]["sourceRefs"] = [bad if good_old else ref_good]
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        candidate = copy.deepcopy(self.candidate)
        candidate.pop("layers", None)
        fixed = {"id": "event", "order": 1, "chapter": "第一回",
                 "quote": padded if new_quote is None else new_quote,
                 "quoteRef": ref_good, "sourceRefs": [ref_good]}
        candidate["newEvents"] = [fixed]
        if declare:
            candidate["replaceEventIds"] = ["event"]
        return candidate

    def test_reanchor_repairs_a_leading_whitespace_offset_without_replacement(self):
        """**更好的一条路**：`reanchor_graph` 自己就该修好「引文带首部空白」的偏移错。

        病灶：它把引文 `strip()` 之后再拿去匹配，于是与 `sourceRefs[].quote`
        （未 strip）比对不上，回落到 anchor 的「不含缩进」位置 ⇒ **把正确的引用改坏**。
        实测已发布的 47 条 q2x 事件（`quoteRef.start` 比正确位置少 4）就是这么来的。
        修好后，**不需要**走替换通道 —— 发布时就会把偏移修回 `start=0`。
        """
        padded = "    " + self.quote
        self.docs[0]["text"] = padded
        (self.cache / (self.key + ".docs.json")).write_text(json.dumps(self.docs, ensure_ascii=False))
        th = S.source_specs(self.docs)[0]["textHash"]
        bad = {"start": 4, "end": len(padded), "quote": padded, "sourceId": self.docs[0]["sourceId"],
               "textHash": th, "offsetUnit": "codepoint", "status": "verified",
               "verified": True, "match": "exact"}
        self.graph["events"][0]["quote"] = padded
        self.graph["events"][0]["quoteRef"] = dict(bad)
        self.graph["events"][0]["sourceRefs"] = [dict(bad)]
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        candidate = copy.deepcopy(self.candidate)
        for _t in candidate["layers"]["tasks"]:
            _t["quote"] = padded
            _r = dict(_t["sourceRefs"][0]) if _t.get("sourceRefs") else {}
            _r.update({"quote": padded, "start": 0, "end": len(padded), "textHash": th})
            _t["sourceRefs"] = [_r]
        result = self.publish(candidate)
        self.assertTrue(result["ok"], result.get("error"))
        ev = [e for e in result["graph"]["events"] if str(e.get("id")) == "event"][0]
        refs = [r for r in (ev.get("sourceRefs") or []) if isinstance(r, dict) and isinstance(r.get("start"), int)]
        self.assertTrue(refs, "必须留下一条带偏移的引用")
        self.assertTrue(any(padded[r["start"]:r["end"]] == ev["quote"] for r in refs),
                        "重建后的引用必须**逐字**对得上引文；实际 quote=" + repr(ev.get("quote")) +
                        " refs=" + json.dumps(refs[:2], ensure_ascii=False))


    def _retract_candidate(self, *, target="event", quote=None, clean=None, drop_proof=False,
                           provenance="assistant-reviewed-source", reference_it=True):
        """撤回候选。`provenance` 写到**图里的事件**上（撤回只允许我方来源）。

        `reference_it=True` 时往**图里**放一条引用该事件的 task ——
        撤回候选自身不带 `layers`，所以「仍被引用层指向」这条守卫只有
        **图里本来就有引用**时才会触发（这正是真实场景：
        `black_dog_absent` 被一条因果边指着）。
        """
        self.graph["events"][0]["provenance"] = provenance
        if reference_it:
            ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
            self.graph["tasks"] = [{"id": "reviewed-task", "entityId": "reviewed-task",
                                    "name": "救乙", "character": "甲", "goal": "救出乙",
                                    "eventIds": [target if target != "event" else "event"],
                                    "quote": self.quote, "sourceRefs": [ref]}]
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"}}
        item = {"id": target, "reason": "测试"}
        if not drop_proof:
            item["quote"] = self.quote if quote is None else quote
        if clean is not None:
            item["cleanRefs"] = clean
        cand["retractEventIds"] = [item]
        return cand

    def test_replace_accepts_three_provable_beneficiaries(self):
        """补 `order` / 修 `order` / 补 `name` —— 三类收益各自放行，且**都需声明期望值**。

        实测来源（全是真的）：
          ① **补 order**：14351 条我方事件在文件里缺失 order，而 `storylines[].events`
             存的是 order ⇒ 发布校验解析不到 ⇒ 支线层发不出来。
          ② **修 order**：q2r 的 109 条写的是**章内局部序号**（1,2,3…），
             与 upstream 的 1..2990 **撞值** ⇒ 同一 order 对应多 id ⇒ 判歧义。
          ③ **补 name**：q2p/q2q 把事件名写在 `summary` 字段，而 `app.js:134` 只读
             `name`/`title` ⇒ 426 条在界面上显示为「 — 摘要」（标题为空）。
        """
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        self.graph["events"][0]["provenance"] = "assistant-reviewed-source"
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        for tag, chg, tgt_key, tgt_val in (
                ("补 order", {"order": 7}, "orderFixTarget", 7),
                ("补 name", {"name": "救出乙的那一晚"}, "nameFixTarget", "救出乙的那一晚"),
                ("修 order", {"order": 9}, "orderFixTarget", 9)):
            base = dict(self.graph["events"][0])
            base["order"] = 3 if tag == "修 order" else None
            if tag == "补 name":
                base["name"] = ""
            (self.cache / (self.key + ".json")).write_bytes(
                json.dumps(dict(self.graph, events=[base]), ensure_ascii=False, indent=3).encode())
            fixed = dict(base); fixed.update(chg)
            fixed["quote"] = self.quote; fixed["sourceRefs"] = [ref]
            cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                    "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                    "newEvents": [fixed], "replaceEventIds": ["event"],
                    tgt_key: {"event": tgt_val}}
            result = self.publish(cand)
            self.assertTrue(result["ok"], f"{tag} 应被放行；实际=" + str(result.get("error")))

    def test_character_rename_fix_is_verified_against_the_source(self):
        """角色**正名**修正：服务端自己数原文，新名必须显著更常见。

        实测病灶：角色表正名『许玉春』原文 **0** 次，别名『李玉春』**295** 次，
        92 条事件的引文里 43 条逐字写「李玉春」、0 条写「许玉春」
        ⇒ 界面显示的**人物名**是错的（别名解析生效，但显示名错）。
        """
        self.graph["characters"] = [{"id": "ch1", "name": "甲", "aliases": ["乙"]}]
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                "characterRenameFixes": [{"characterId": "ch1", "from": "甲", "to": "乙"}]}
        with self.assertRaises(S.ApiError) as e:
            self.publish(cand)
        self.assertIn("正名修正未被原文支持", str(e.exception))

    def test_character_rename_accepts_a_name_the_events_already_use(self):
        """**精化**：`to` 也接受「该人物的事件已经在用」的名字。

        实测触发：角色表正名『楚元禛』（原文 **1** 次），而 **415 条事件**早已用
        『楚元缜』（原文 **1176** 次）—— 那 1 次『楚元禛』反而是原文自身的笔误。
        若死守「`to` 必须先在该人物 aliases 里」，就会与「alias 通道只能移除」形成死锁。
        """
        self.graph["characters"] = [{"id": "ch1", "name": "甲甲", "aliases": []}]
        ev = dict(self.graph["events"][0])
        ev["characters"] = ["乙乙"]
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(dict(self.graph, events=[ev]), ensure_ascii=False, indent=3).encode())
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                "characterRenameFixes": [{"characterId": "ch1", "from": "甲甲", "to": "乙乙"}]}
        with self.assertRaises(S.ApiError) as e:
            self.publish(cand)
        self.assertIn("正名修正未被原文支持", str(e.exception))

    def test_character_rename_refuses_a_name_not_on_the_character(self):
        """反例：改成该人物**既非现名也非别名**的名字 ⇒ 拒（挡住凭空改名）。"""
        self.graph["characters"] = [{"id": "ch1", "name": "甲", "aliases": ["乙"]}]
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                "characterRenameFixes": [{"characterId": "ch1", "from": "甲", "to": "丙"}]}
        with self.assertRaises(S.ApiError) as e:
            self.publish(cand)
        self.assertIn("不能凭空改名", str(e.exception))

    def test_replace_allows_a_field_fix_when_the_quote_was_already_unlocated(self):
        """**精化判据**：若替换**没有改动 quote**，不得因「既有引文未定位」而拒绝。

        否则一条本来就未定位的引文会**永久封锁**该事件的其他字段修正。
        方向仍严格：**不得把引文改坏**（下方反例覆盖）。
        """
        base = dict(self.graph["events"][0])
        base.update({"provenance": "assistant-reviewed-source",
                     "quote": "这句话根本不在原文里", "characters": ["旧"]})
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(dict(self.graph, events=[base]), ensure_ascii=False, indent=3).encode())
        fixed = dict(base); fixed["characters"] = ["新"]
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                "newEvents": [fixed], "replaceEventIds": ["event"]}
        try:
            self.publish(cand)
        except S.ApiError as exc:
            self.assertNotIn("引文无法在原文逐字定位", str(exc))

    def test_replace_refuses_to_break_a_quote_into_something_unlocatable(self):
        """**反例（补）**：把已定位的引文**改成**一个原文没有的句子 ⇒ 必须拒。

        这条与上一条配对，共同钉死精化后的方向：
        **引文未变时放行；引文被改坏时拒绝。**
        （上一条变异曾从这里逃逸 —— 我只测了"未变放行"，没测"改坏仍拒"。）
        """
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        base = dict(self.graph["events"][0])
        base.update({"provenance": "assistant-reviewed-source", "quote": self.quote,
                     "sourceRefs": [ref], "characters": ["旧"]})
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(dict(self.graph, events=[base]), ensure_ascii=False, indent=3).encode())
        broken = dict(base)
        broken["quote"] = "这句话被改成了一个原文里根本没有的句子"
        broken["characters"] = ["新"]
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                "newEvents": [broken], "replaceEventIds": ["event"]}
        with self.assertRaises(S.ApiError) as e:
            self.publish(cand)
        self.assertIn("引文无法在原文逐字定位", str(e.exception))

    def test_character_name_fix_requires_the_source_to_favour_the_correct_name(self):
        """⑤ **改错字**：服务端**自己数原文**判「正名是否确实更常见」。

        实测来源：`characters` 写了「钟丽」，而原文 **588** 次作「钟璃」、
        角色表只有「钟璃」（5 个别名），「钟丽」仅 1 次（原文自身笔误）
        ⇒ **129 条事件**把这个错名当成了人物。
        """
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        base = dict(self.graph["events"][0])
        base.update({"provenance": "assistant-reviewed-source", "characters": ["钟丽"]})
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(dict(self.graph, events=[base]), ensure_ascii=False, indent=3).encode())
        fixed = dict(base); fixed["characters"] = ["钟璃"]
        fixed["quote"] = self.quote; fixed["sourceRefs"] = [ref]
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                "newEvents": [fixed], "replaceEventIds": ["event"],
                "characterNameFixes": {"钟丽": "钟璃"}}
        with self.assertRaises(S.ApiError) as e:
            self.publish(cand)
        self.assertIn("改错字未被原文支持", str(e.exception))

    def test_character_name_fix_cannot_invert_a_common_name_into_a_rare_one(self):
        """反例：拿一个原文里**更少见**的写法去"纠正"常见写法 ⇒ 必须拒绝。

        这条挡住「用改错字通道做任意改写」：正名必须在原文里≥10 倍且≥10 次。
        """
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        base = dict(self.graph["events"][0])
        base.update({"provenance": "assistant-reviewed-source", "characters": ["的"]})
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(dict(self.graph, events=[base]), ensure_ascii=False, indent=3).encode())
        fixed = dict(base); fixed["characters"] = ["乙"]
        fixed["quote"] = self.quote; fixed["sourceRefs"] = [ref]
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                "newEvents": [fixed], "replaceEventIds": ["event"],
                "characterNameFixes": {"的": "乙"}}
        with self.assertRaises(S.ApiError) as e:
            self.publish(cand)
        msg = str(e.exception)
        self.assertTrue("改错字未被原文支持" in msg or "替换无收益" in msg, msg)

    def test_restore_fields_retracts_a_proven_mistake(self):
        """④ **定向撤回**：撤销一个被证明为错的既有改动（不是整体回滚）。

        实测来源：我曾把 426 条事件的 `name` 用 `summary` 填上，而当前计划 **P1.1**
        明确「**不从摘要杜撰标题**」且「426 条确实缺 title/name，**不能强行刷0**」。
        ⇒ 必须定向撤回。契约要求：**声明要移除的字段**（`restoreFields`），
        且移除后该字段**确为空**、而**旧版确有值**。
        """
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        base = dict(self.graph["events"][0])
        base.update({"provenance": "assistant-reviewed-source", "name": "我从摘要抄来的标题"})
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(dict(self.graph, events=[base]), ensure_ascii=False, indent=3).encode())
        cleared = dict(base); cleared.pop("name", None)
        cleared["quote"] = self.quote; cleared["sourceRefs"] = [ref]
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                "newEvents": [cleared], "replaceEventIds": ["event"],
                "restoreFields": {"event": ["name"]}}
        result = self.publish(cand)
        self.assertTrue(result["ok"], result.get("error"))
        ev = [e for e in result["graph"]["events"] if str(e.get("id")) == "event"][0]
        self.assertFalse(str(ev.get("name") or "").strip(), "被撤回的字段必须为空")

    def test_restore_refuses_when_it_is_not_actually_removing_anything(self):
        """反例：声明移除某字段，但新版**并未把它清空**（相当于在改值而非撤回）⇒ 拒。"""
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        base = dict(self.graph["events"][0])
        base.update({"provenance": "assistant-reviewed-source", "name": "旧名"})
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(dict(self.graph, events=[base]), ensure_ascii=False, indent=3).encode())
        changed = dict(base); changed["name"] = "新名"
        changed["quote"] = self.quote; changed["sourceRefs"] = [ref]
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                "newEvents": [changed], "replaceEventIds": ["event"],
                "restoreFields": {"event": ["name"]}}
        with self.assertRaises(S.ApiError) as e:
            self.publish(cand)
        self.assertIn("替换无收益", str(e.exception))

    def test_name_fix_must_match_the_declared_source_verbatim(self):
        """反例：**补 name 但不声明来源**（或声明得不一样）⇒ 拒。

        这一条挡住「自由发挥写标题」：名字必须来自可追溯来源
        （实测是源文件的 `summary` 字段），并由候选**逐字声明**出来。
        """
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        base = dict(self.graph["events"][0])
        base.update({"provenance": "assistant-reviewed-source", "name": ""})
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(dict(self.graph, events=[base]), ensure_ascii=False, indent=3).encode())
        fixed = dict(base); fixed.update({"name": "我随手编的标题"})
        fixed["quote"] = self.quote; fixed["sourceRefs"] = [ref]
        for tgt, tag in (({}, "不声明 nameFixTarget"), ({"event": "另一个名字"}, "声明的值与实际不同")):
            cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                    "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                    "newEvents": [fixed], "replaceEventIds": ["event"]}
            if tgt:
                cand["nameFixTarget"] = tgt
            with self.assertRaises(S.ApiError) as e:
                self.publish(cand)
            self.assertIn("替换无收益", str(e.exception), tag)

    def test_replace_still_refuses_when_no_declared_benefit(self):
        """反例：**声明了期望值但改的不是那一项** ⇒ 仍按「无收益」拒。"""
        ref = S.Corpus("", S.source_specs(self.docs)).anchor(self.quote)
        base = dict(self.graph["events"][0]); base["provenance"] = "assistant-reviewed-source"
        base["order"] = 3; base["name"] = "旧名"
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(dict(self.graph, events=[base]), ensure_ascii=False, indent=3).encode())
        fixed = dict(base); fixed["order"] = 5; fixed["quote"] = self.quote; fixed["sourceRefs"] = [ref]
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {"events": ["event"], "originalRead": "selected_original_sentence_not_whole_novel"},
                "newEvents": [fixed], "replaceEventIds": ["event"],
                "orderFixTarget": {"event": 6}}
        with self.assertRaises(S.ApiError) as e:
            self.publish(cand)
        self.assertIn("替换无收益", str(e.exception))

    def test_retract_removes_a_proven_fabrication_and_its_dependent_edge(self):
        """正例：撤回一条我方事件，并连带清理依赖它的引用节点。

        注意：撤回候选**不带 `layers`**（它就是一次"只减"操作）。
        因此 `cleanRefs` 清的是**图里原有**的引用节点 —— 夹具里由 `self.graph["tasks"]` 提供。
        """
        cand = self._retract_candidate(clean=["reviewed-task"])
        result = self.publish(cand)
        self.assertTrue(result["ok"], result.get("error"))
        ids = [str(e.get("id")) for e in result["graph"]["events"]]
        self.assertNotIn("event", ids, "被撤回的事件必须不在图里")
        self.assertEqual(len(ids), len(set(ids)), "撤回后 id 仍须唯一")
        tids = [str(t.get("id")) for t in (result["graph"].get("tasks") or [])]
        self.assertNotIn("reviewed-task", tids, "声明清理的引用节点必须一并撤掉")
        self.assertEqual([r["id"] for r in result["graph"].get("retractedEvents") or []], ["event"])

    def test_retract_requires_a_grounded_proof_and_keeps_every_other_error_distinct(self):
        """反例：4 条边界**各自报自己的原因**（顺序错会让后面的守卫被前面遮住）。"""
        with self.assertRaises(S.ApiError) as e1:
            self.publish(self._retract_candidate(target="no-such-id", reference_it=False))
        self.assertIn("撤回目标不在图", str(e1.exception))
        with self.assertRaises(S.ApiError) as e2:
            self.publish(self._retract_candidate(drop_proof=True))
        self.assertIn("必须带逐字反证引文", str(e2.exception))
        with self.assertRaises(S.ApiError) as e3:
            self.publish(self._retract_candidate(quote="这句话在原文里根本不存在完全是我编的"))
        self.assertIn("无法在原文逐字定位", str(e3.exception))
        with self.assertRaises(S.ApiError) as e4:
            self.publish(self._retract_candidate())
        self.assertIn("仍被引用层指向", str(e4.exception))

    def test_retract_refuses_upstream_events(self):
        """反例：**只允许撤回我方（assistant-reviewed-source）**，不动上游记录。"""
        with self.assertRaises(S.ApiError) as e:
            self.publish(self._retract_candidate(clean=["reviewed-task"], provenance="upstream-author"))
        self.assertIn("只允许撤回 assistant-reviewed-source", str(e.exception))

    def test_retract_rejects_malformed_declaration(self):
        cand = {"provenance": "assistant-reviewed-source", "modelCalls": 0, "sourceKey": self.key,
                "scope": {}, "retractEventIds": "event"}
        with self.assertRaises(S.ApiError):
            self.publish(cand)

    def test_replace_same_id_fixes_a_published_bad_offset(self):
        """正例：旧版**根本无法定位**（引文与原文不符）、新版能定位 ⇒ 替换成功。

        注意：`_anchor` 修好后，「引文带首部空白」**不再**需要走替换 ——
        重建自己就能把它锚到含缩进的位置（见上一个用例）。
        所以这里构造的是**真正需要替换**的情形：旧版的引文在原文里**逐字找不到**
        （例如被改写过的引文），那种错误重建救不了，只能靠替换。
        """
        cand = self._replacement_candidate()
        self.graph["events"][0]["quote"] = "    " + self.quote + "（原文里没有这半句）"
        self.graph["events"][0]["sourceRefs"] = []
        self.graph["events"][0].pop("quoteRef", None)
        (self.cache / (self.key + ".json")).write_bytes(
            json.dumps(self.graph, ensure_ascii=False, indent=3).encode())
        result = self.publish(cand)
        self.assertTrue(result["ok"], result.get("error"))
        evs = [e for e in result["graph"]["events"] if str(e.get("id")) == "event"]
        self.assertEqual(len(evs), 1, "替换后同一 id 必须只有一条（否则索引判歧义）")
        self.assertEqual(evs[0]["quote"], "    " + self.quote)

    def test_replace_without_declaration_still_refuses_to_overwrite(self):
        """反例：**未声明** replaceEventIds 时，同 id 仍必须被拒（保住既有安全语义）。"""
        cand = self._replacement_candidate(declare=False)
        with self.assertRaises(S.ApiError):
            self.publish(cand)

    def test_replace_rejects_a_version_whose_quote_is_not_grounded(self):
        """反例：替换版的引文无法逐字定位 ⇒ 拒（挡住「用更差的版本替换好的版本」）。"""
        cand = self._replacement_candidate(new_quote="    这句话在原文里根本不存在完全是我编的")
        with self.assertRaises(S.ApiError):
            self.publish(cand)

    def test_replace_rejects_when_old_version_was_already_grounded(self):
        """反例：旧版本来就 grounded ⇒ 替换无收益 ⇒ 拒（防无谓改写）。"""
        cand = self._replacement_candidate(good_old=False)
        with self.assertRaises(S.ApiError):
            self.publish(cand)

    def test_replace_rejects_malformed_declaration(self):
        """反例：replaceEventIds 必须是**非空字符串数组**。"""
        for bad in ([], [123], "event", [""]):
            cand = self._replacement_candidate()
            cand["replaceEventIds"] = bad
            with self.assertRaises(S.ApiError):
                self.publish(cand)

    def test_quote_fix_is_idempotent_when_already_exact(self):
        """幂等：本来逐字一致时安静通过，不记修正数。"""
        result = self.publish(self.quote_fix_candidate(pad=""))
        self.assertTrue(result["ok"], result.get("error"))
        self.assertNotIn("quoteTextFixCount", result["graph"]["meta"])

    def test_new_event_without_readable_name_or_chapter_cannot_publish(self):
        """P1.6 发布者契约：新事件必须有至少一个可读名称、章节声明与类型。

        实测缺口（2026-10-08）：加这条检查之前，一条 title/name/chapter/summary
        全空的新事件在 dry-run 里拿到 `ok: true`、`contractProblems: []`。
        读模型会把「无名称」渲染成具名未知态，读者看到「未命名事件 · #hash」——
        但那是给**既有**无名字料的诚实兜底，不是让新内容这样进来的理由。
        """
        base = copy.deepcopy(self.candidate)
        base["newEvents"] = [{"id": "ev_nameless", "order": 9, "chapter": "", "title": "",
                              "name": "", "summary": "", "kind": "", "characters": []}]
        report = P.validate(base, self.graph, self.docs)
        self.assertFalse(report["ok"], "没有可读名称的新事件不该通过发布门")
        reasons = {p.get("reason") for p in report["contractProblems"]}
        self.assertIn("new_event_requires_readable_name", reasons)
        self.assertIn("new_event_requires_chapter", reasons)
        self.assertIn("new_event_requires_kind", reasons)
        named = [p for p in report["contractProblems"] if p.get("eventId") == "ev_nameless"]
        self.assertEqual(len(named), 3, "三条问题都要点名同一条事件")
        ok = copy.deepcopy(self.candidate)
        ok["newEvents"] = [{"id": "ev_named", "order": 9, "chapter": "第一回", "title": "",
                            "name": "乙获救", "kind": "转折", "characters": ["甲"]}]
        report2 = P.validate(ok, self.graph, self.docs)
        reasons2 = {p.get("reason") for p in (report2.get("contractProblems") or [])}
        self.assertNotIn("new_event_requires_readable_name", reasons2,
                         "只有 name 有效时也必须算有可读名称")
        legacy = copy.deepcopy(self.candidate)
        legacy["newEvents"] = []
        self.assertNotIn("new_event_requires_readable_name",
                         {p.get("reason") for p in (P.validate(legacy, self.graph, self.docs).get("contractProblems") or [])})

    def test_rejection_keeps_machine_readable_reason(self):
        """计划 P1.6：拒绝候选保留原因 —— 不能只剩一句泛化文案。

        实测：validator 算出的 contractProblems 原先在 serve.py 里被直接丢掉，
        发布报告里 `contractProblems: null`，无法知道哪条不合格。
        """
        bad = copy.deepcopy(self.candidate)
        bad["newEvents"] = [{"id": "ev_nameless2", "order": 9, "chapter": "", "title": "",
                             "name": "", "summary": "", "kind": "", "characters": []}]
        with self.assertRaises(S.ApiError) as ctx:
            self.publish(bad)
        message = str(ctx.exception)
        self.assertIn("new_event_requires_readable_name", message,
                      "拒绝信息里必须带机器可判定的原因")


if __name__ == "__main__":
    unittest.main(verbosity=2)
