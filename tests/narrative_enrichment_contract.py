#!/usr/bin/env python3
"""Offline semantic/anchor/resume/revision negative controls. No real data."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve as S
import narrative as N

PROFILE = {"kind": "anthropic", "model": "offline-test", "base_url": "http://invalid.local", "api_key": "OFFLINE_ONLY"}


def fixture(count=3):
    quotes = ["😀北辰为救城中人寻找第%d枚钥匙。" % i for i in range(count)]
    docs = [{"name": "原文", "sourceId": "source-fixed", "text": "\n".join(quotes)}]
    graph = {"title": "拯救古城", "synopsis": "寻找钥匙恢复护盾。", "characters": [{"id": "ch-fixed", "name": "北辰", "aliases": []}],
             "events": [{"id": "ev-%d" % i, "order": i + 1, "chapter": "第%d章" % (i + 1), "title": "寻钥匙",
                         "summary": "北辰探索各处并借第%d枚钥匙解除屏障，目标并未因章节切换改变。" % i,
                         "characters": ["北辰"], "kind": "抉择", "quote": quote} for i, quote in enumerate(quotes)], "relations": []}
    return graph, docs


def part(**layers):
    value = {name: [] for name in N.LAYERS}
    value.update(layers)
    value["layerStatus"] = {name: "complete" for name in N.LAYERS}
    value["warnings"] = []
    return value


def task(events, ident="task-rescue", **extra):
    value = {"id": ident, "name": "恢复护盾", "character": "北辰", "goal": "找到钥匙救城中人", "obstacle": "钥匙散落各处",
             "action": "寻找钥匙", "outcome": "", "cost": "", "status": "active", "eventIds": [e["id"] for e in events],
             "quote": events[0]["quote"], "basis": "explicit"}
    value.update(extra)
    value.setdefault("outcomeEventId", events[-1]["id"] if value["status"] in ("completed", "failed", "abandoned") else "")
    return value


def line(events, ident="S1", **extra):
    value = {"id": ident, "name": "救城寻钥", "kind": "主线", "parent": "", "attachEventId": "", "eventIds": [e["id"] for e in events],
             "lead": "北辰", "cast": ["北辰"], "theme": "解除屏障", "goal": "找到钥匙救城中人", "obstacle": "钥匙散落各处",
             "stakes": "城中人的生命", "outcome": "", "resolution": "未定", "handoff_from": "", "handoff_reason": "",
             "parentRelation": "", "evidenceQuotes": [events[0]["quote"]], "basis": "explicit"}
    value.update(extra)
    return value


class NarrativeEnrichmentContract(unittest.TestCase):
    def setUp(self):
        self.graph, self.docs = fixture()
        self.tmp = tempfile.TemporaryDirectory(prefix="castline-narrative-test-")
        self.addCleanup(self.tmp.cleanup)
        self.network = patch.object(S.urllib.request, "urlopen", side_effect=AssertionError("NETWORK FORBIDDEN"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def rebuild(self, graph=None, docs=None):
        return S.rebuild_sources(graph or self.graph, docs or self.docs)

    def enrich(self, call, **kwargs):
        return N.enrich(self.graph, self.docs, call, S.source_specs, lambda specs: S.Corpus("", specs),
                        S.atomic_json, self.tmp.name, model_key="offline-model", **kwargs)

    def test_event_manifest_preserves_summary_quote_stable_id_and_refs(self):
        anchored = self.rebuild()
        row = json.loads(S._story_rows(anchored["events"])[0])
        self.assertEqual(row["summary"], self.graph["events"][0]["summary"])
        self.assertEqual(row["quote"], self.graph["events"][0]["quote"])
        self.assertEqual(row["id"], "ev-0")
        self.assertTrue(row["sourceRefs"][0]["verified"])
        self.assertIn("不设最低线数", S.STORYLINE_PROMPT)
        self.assertNotIn("{lo}-{hi}", S.STORYLINE_PROMPT)

    def test_model_manifest_keeps_known_quote_attribution_problems(self):
        event = dict(self.graph["events"][0], quoteReview="wrong-scene", reviewNotes=["引句存在，但属于另一件事"],
                     quoteVerified=False, claimVerified=False)
        row = json.loads(N.event_rows([event])[0])
        self.assertEqual(row["quoteReview"], event["quoteReview"])
        self.assertEqual(row["reviewNotes"], event["reviewNotes"])
        self.assertFalse(row["quoteVerified"])
        self.assertFalse(row["claimVerified"])

    def test_anchors_verify_raw_codepoints_and_do_not_verify_claim(self):
        untouched = copy.deepcopy(self.graph)
        result = self.rebuild()
        quote = self.graph["events"][0]["quote"]
        ref = result["events"][0]["quoteRef"]
        self.assertEqual(self.docs[0]["text"][ref["start"]:ref["end"]], quote)
        self.assertEqual(ref["end"] - ref["start"], len(quote))
        self.assertEqual(ref["textHash"], hashlib.sha256(self.docs[0]["text"].encode()).hexdigest())
        self.assertEqual(ref["offsetUnit"], "codepoint")
        self.assertTrue(result["events"][0]["quoteVerified"])
        self.assertFalse(result["events"][0]["claimVerified"])
        self.assertEqual(result["meta"]["sourceRebuild"]["claimVerification"], "not_performed")
        self.assertEqual(self.graph, untouched)

    def test_forged_missing_normalized_and_stale_refs_cannot_remain_verified(self):
        graph = copy.deepcopy(self.graph)
        graph["events"][0].update(quote="原文不存在的宣判。", verified=True, claimVerified=True,
             sourceRefs=[{"verified": True, "status": "verified", "sourceId": "source-fixed", "textHash": "fake",
                          "quote": "原文不存在的宣判。", "start": 0, "end": 10, "offsetUnit": "codepoint"}])
        graph["events"][1]["quote"] = graph["events"][1]["quote"].replace("。", ".")
        result = self.rebuild(graph)
        for event in result["events"][:2]:
            self.assertFalse(event["verified"])
            self.assertFalse(event["claimVerified"])
            self.assertNotIn("start", event["quoteRef"])

    def test_ambiguous_quote_requires_exact_existing_hash_and_location(self):
        graph, docs = fixture(1)
        quote = graph["events"][0]["quote"]
        docs[0]["text"] = quote + "\n" + quote
        self.assertFalse(self.rebuild(graph, docs)["events"][0]["verified"])
        start = len(quote) + 1
        ref = {"sourceId": "source-fixed", "textHash": hashlib.sha256(docs[0]["text"].encode()).hexdigest(),
               "start": start, "end": start + len(quote), "offsetUnit": "codepoint", "quote": quote}
        graph["events"][0]["sourceRefs"] = [ref]
        self.assertTrue(self.rebuild(graph, docs)["events"][0]["verified"])
        graph["events"][0]["sourceRefs"][0]["textHash"] = "stale"
        self.assertFalse(self.rebuild(graph, docs)["events"][0]["verified"])

    def test_duplicate_ids_and_conflicting_endpoint_declarations_do_not_resolve(self):
        graph = copy.deepcopy(self.graph)
        graph["causeEdges"] = [{"id": "edge", "fromEventId": "ev-0", "sourceId": "ev-1", "toEventId": "ev-2", "quote": graph["events"][0]["quote"]}]
        for _ in range(3):
            graph = self.rebuild(graph)
            self.assertFalse(graph["causeEdges"][0]["resolved"])
        graph["events"][1]["id"] = "ev-0"
        self.assertIsNone(N.References(graph).event("ev-0"))

    def test_unknown_cross_chapter_refs_are_not_silently_mapped_by_title(self):
        graph = copy.deepcopy(self.graph)
        graph["causeEdges"] = [{"id": "edge", "fromEventId": "missing", "fromTitle": "寻钥匙", "toEventId": "ev-2"}]
        graph["characterStates"] = [{"id": "state", "character": "北辰", "eventId": "missing", "summary": "存活"}]
        graph["tasks"] = [task(graph["events"], eventIds=["missing"])]
        result = self.rebuild(graph)
        for layer in ("causeEdges", "characterStates", "tasks"):
            self.assertFalse(result[layer][0]["resolved"])

    def test_source_only_plan_and_rebuild_do_not_call_a_model(self):
        call = unittest.mock.Mock(side_effect=AssertionError("MODEL FORBIDDEN"))
        result, info = self.enrich(call, source_only=True)
        call.assert_not_called()
        self.assertEqual(info["estimatedCalls"], 0)
        self.assertEqual(result["meta"]["enrichment"]["status"], "source_only")

    def test_single_main_is_valid_and_no_branch_is_fabricated(self):
        self.graph["storylines"] = [{"id": "auto-main", "name": "平均阶段", "kind": "主线", "events": [1, 2, 3]}]
        result, info = self.enrich(lambda *a, **k: part(storylines=[line(self.graph["events"])]), layers=["storylines"])
        self.assertEqual(len(result["storylines"]), 1)
        self.assertEqual(result["storylines"][0]["id"], "S1")
        self.assertEqual(result["storylines"][0]["events"], [1, 2, 3])
        self.assertEqual(result["meta"]["enrichment"]["calls"], 1)
        self.assertEqual(result["meta"]["enrichment"]["semanticCompleteness"], "unverified")
        self.assertTrue(result["storylines"][0]["quoteVerified"])
        self.assertFalse(result["storylines"][0]["claimVerified"])

    def test_branch_requires_semantic_parent_relation_and_owned_attach_event(self):
        main = line(self.graph["events"][:2])
        branch = line(self.graph["events"][2:], "S2", kind="支线", parent="S1", attachEventId="ev-2", parentRelation="获取主线资源")
        with self.assertRaisesRegex(N.InvalidResult, "attachment"):
            self.enrich(lambda *a, **k: part(storylines=[main, branch]), layers=["storylines"])
        branch.update(attachEventId="ev-1", parentRelation="")
        with self.assertRaisesRegex(N.InvalidResult, "parentRelation"):
            self.enrich(lambda *a, **k: part(storylines=[main, branch]), layers=["storylines"])

    def test_failed_batch_is_not_cached_as_success_and_resume_reuses_prior_batch(self):
        calls = []
        def failing(prompt, *a, **kwargs):
            payload = json.loads(prompt.split("===补析输入(JSON)===\n", 1)[1])
            calls.append(payload["batch"])
            if payload["batch"] == 2:
                raise S.ApiError("offline failed second batch")
            return part(tasks=[task(payload["events"])])
        with patch.object(N, "BATCH_EVENTS", 2):
            with self.assertRaisesRegex(S.ApiError, "second batch"):
                self.enrich(failing, layers=["tasks"])
            ledgers = list(Path(self.tmp.name).glob("narrative/*.stages.json"))
            self.assertEqual(len(ledgers), 1)
            self.assertEqual(list(json.loads(ledgers[0].read_text())["stages"]), ["0"])
            def resume(prompt, *a, **kwargs):
                payload = json.loads(prompt.split("===补析输入(JSON)===\n", 1)[1])
                self.assertEqual(payload["batch"], 2)
                self.assertEqual(payload["continuations"]["tasks"][0]["goal"], "找到钥匙救城中人")
                return part(tasks=[task(payload["events"], status="completed", outcome="护盾已恢复")])
            result, _ = self.enrich(resume, layers=["tasks"])
        self.assertEqual(result["meta"]["enrichment"]["resumedBatches"], 1)
        self.assertEqual(result["meta"]["enrichment"]["calls"], 1)
        self.assertEqual(result["tasks"][0]["eventIds"], ["ev-0", "ev-1", "ev-2"])
        self.assertEqual(result["tasks"][0]["status"], "completed")

    def test_cancellation_saves_completed_valid_batch_and_stops_new_calls(self):
        stopped = [False]
        calls = []
        def cancel_after_response(prompt, *a, **kwargs):
            payload = json.loads(prompt.split("===补析输入(JSON)===\n", 1)[1])
            calls.append(payload["batch"])
            stopped[0] = True
            return part(tasks=[task(payload["events"])])
        with patch.object(N, "BATCH_EVENTS", 1):
            with self.assertRaises(N.Cancelled):
                self.enrich(cancel_after_response, layers=["tasks"], cancel=lambda: stopped[0])
        self.assertEqual(calls, [1])
        stages = json.loads(next(Path(self.tmp.name).glob("narrative/*.stages.json")).read_text())["stages"]
        self.assertEqual(list(stages), ["0"])

    def test_invalid_model_refs_and_forged_explicit_quote_are_failures(self):
        for output in (part(tasks=[task(self.graph["events"], eventIds=["fake"])]),
                       part(tasks=[task(self.graph["events"], quote="模型编造的原文")]),
                       part(tasks=[task(self.graph["events"], id="")]), part()):
            with self.subTest(output=output), self.assertRaises(N.InvalidResult):
                self.enrich(lambda *a, **k: output, layers=["tasks"], force=True)
        self.assertFalse(list(Path(self.tmp.name).glob("narrative/*.stages.json")))

    def test_cross_chapter_cause_clue_task_and_character_state_ids_are_validated(self):
        events = self.graph["events"]
        output = part(tasks=[task(events)],
            causeEdges=[{"id": "cause", "fromEventId": "ev-0", "toEventId": "ev-2", "description": "第一枚开启最终入口", "quote": events[0]["quote"], "basis": "inferred"}],
            clues=[{"id": "clue", "name": "钥匙", "summary": "目标物件", "seedEventId": "ev-0", "payoffEventId": "ev-2", "seedQuote": events[0]["quote"], "payoffQuote": events[2]["quote"], "status": "resolved", "basis": "inferred"}],
            characterStates=[{"id": "state", "characterId": "ch-fixed", "character": "北辰", "eventId": "ev-2", "chapter": "", "summary": "找到第三枚钥匙", "quote": events[2]["quote"], "attributes": [{"name": "资源", "value": "第三枚钥匙", "quote": events[2]["quote"]}]}])
        result, _ = self.enrich(lambda *a, **k: output, layers=["tasks", "causeEdges", "clues", "characterStates"])
        self.assertTrue(all(result[layer][0]["resolved"] for layer in ("tasks", "causeEdges", "clues", "characterStates")))
        self.assertEqual(result["causeEdges"][0]["sourceId"], "ev-0")
        self.assertEqual(result["characterStates"][0]["chapter"], "第3章")
        self.assertTrue(result["characterStates"][0]["attributes"][0]["sourceRefs"][0]["verified"])

    def test_unverified_payoff_is_not_marked_resolved(self):
        self.graph["clues"] = [{"id": "c", "seedEventId": "ev-0", "payoffEventId": "ev-2", "seedQuote": self.graph["events"][0]["quote"],
                                "payoffQuote": "并不存在的兑现", "status": "resolved"}]
        self.assertEqual(self.rebuild()["clues"][0]["status"], "uncertain")

    def test_task_terminal_state_and_reversed_or_same_event_payoffs_are_rejected(self):
        for extra in ({"status": "completed", "outcome": ""},
                      {"status": "completed", "outcome": "已结束", "outcomeEventId": "missing"}):
            with self.subTest(extra=extra), self.assertRaisesRegex(N.InvalidResult, "terminal status"):
                self.enrich(lambda *a, **k: part(tasks=[task(self.graph["events"], **extra)]), layers=["tasks"])
        for seed_id, payoff_id in (("ev-2", "ev-0"), ("ev-0", "ev-0")):
            self.graph["clues"] = [{"id": "clue", "seedEventId": seed_id, "payoffEventId": payoff_id,
                      "seedQuote": self.graph["events"][2]["quote"], "payoffQuote": self.graph["events"][0]["quote"], "status": "resolved"}]
            self.assertEqual(self.rebuild()["clues"][0]["status"], "uncertain")

    def test_selected_event_scope_and_model_identity_change_stage_cache_key(self):
        first = N.plan(self.graph, self.docs, ["tasks"], ["ev-0"], model_key="one")
        self.assertEqual(first["events"], 1)
        self.assertEqual(first["estimatedCalls"], 1)
        self.assertNotEqual(first["key"], N.plan(self.graph, self.docs, ["tasks"], ["ev-1"], model_key="one")["key"])
        self.assertNotEqual(first["key"], N.plan(self.graph, self.docs, ["tasks"], ["ev-0"], model_key="two")["key"])
        with self.assertRaises(N.InvalidResult):
            N.plan(self.graph, self.docs, event_ids=["missing"])

    def test_partial_model_coverage_and_warnings_remain_explicit(self):
        output = part(tasks=[task(self.graph["events"])])
        output["layerStatus"]["tasks"] = "partial"
        output["warnings"] = ["局部窗口未展示任务最终结果"]
        result, _ = self.enrich(lambda *a, **k: output, layers=["tasks"], event_ids=["ev-0", "ev-1", "ev-2"])
        self.assertEqual(result["meta"]["enrichment"]["status"], "partial")
        self.assertEqual(result["meta"]["enrichment"]["scope"], "selected_events")
        self.assertIn("任务最终结果", result["meta"]["enrichment"]["warnings"][0])
        self.assertEqual(result["meta"]["coverage"]["tasks"]["batchStatuses"], ["partial"])
        input_coverage = result["meta"]["enrichment"]["sourceContext"]["coverage"]
        self.assertEqual(input_coverage["state"], "accepted_batches")
        self.assertEqual(input_coverage["includedChars"], len(self.docs[0]["text"]))
        self.assertEqual(input_coverage["semanticCompleteness"], "unverified")

    def test_incremental_job_preserves_original_bytes_and_publishes_new_version(self):
        cache = Path(self.tmp.name)
        key = "1234abcd"
        original = json.dumps(self.graph, ensure_ascii=False, indent=3).encode()
        (cache / (key + ".json")).write_bytes(original)
        (cache / (key + ".docs.json")).write_text(json.dumps(self.docs, ensure_ascii=False))
        with patch.multiple(S, CACHE_DIR=str(cache), HIST_PATH=str(cache / "index.json"), JOBS={}), \
             patch.object(S, "history_add") as history, patch.object(S, "cfg_history"), \
             patch.object(S, "call_llm", return_value=part(tasks=[task(self.graph["events"])])) as model:
            job, attached = S.run_enrichment(key, layers=["tasks"], profile=PROFILE)
            deadline = time.monotonic() + 3
            while not job.finished and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(job.finished)
            self.assertFalse(attached)
            self.assertEqual(job.events[-1][0], "done", job.events)
            done = job.events[-1][1]
            self.assertNotEqual(done["key"], key)
            self.assertTrue((cache / (done["key"] + ".json")).exists())
            self.assertTrue((cache / (done["key"] + ".docs.json")).exists())
            self.assertEqual((cache / (key + ".json")).read_bytes(), original)
            self.assertEqual(next((cache / "narrative/revisions").glob("*.graph.json")).read_bytes(), original)
            model.assert_called_once()
            history.assert_called_once()
            repeated, attached = S.run_enrichment(key, layers=["tasks"], profile=PROFILE, job_key=job.key)
            self.assertIs(repeated, job)
            self.assertTrue(attached)
            model.assert_called_once()

    def test_failed_job_never_emits_done_or_publishes_revision(self):
        cache = Path(self.tmp.name)
        key = "1234abcd"
        (cache / (key + ".json")).write_text(json.dumps(self.graph))
        (cache / (key + ".docs.json")).write_text(json.dumps(self.docs))
        with patch.multiple(S, CACHE_DIR=str(cache), JOBS={}), patch.object(S, "call_llm", side_effect=S.ApiError("offline model failure")):
            job, _ = S.run_enrichment(key, layers=["tasks"], profile=PROFILE)
            deadline = time.monotonic() + 3
            while not job.finished and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(job.events[-1][0], "error")
            self.assertFalse(any(event == "done" for event, _ in job.events))
            self.assertEqual(sorted(p.name for p in cache.glob("*.json")), [key + ".docs.json", key + ".json"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
