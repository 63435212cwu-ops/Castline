#!/usr/bin/env python3
"""Deep mode lifecycle + existing regressions, fully offline and cache-isolated.

This runner executes tests/dryrun.py and tests/control.py with an explicit
offline profile and temporary config/output directories. It must never write
the user's data/llm-config.json or contact a model.
"""
import contextlib
import copy
import io
import os
import runpy
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import serve as S

PROFILE = {"kind": "anthropic", "model": "offline-deep-contract", "base_url": "http://invalid.local", "api_key": ""}


@contextlib.contextmanager
def sandbox():
    with tempfile.TemporaryDirectory(prefix="castline-deep-contract-") as folder:
        chunks = os.path.join(folder, "chunks")
        os.mkdir(chunks)
        original_mkdtemp = tempfile.mkdtemp
        def inside_temp(suffix=None, prefix=None, dir=None):
            return original_mkdtemp(suffix=suffix, prefix=prefix, dir=dir or folder)
        with patch.object(tempfile, "mkdtemp", side_effect=inside_temp), \
                patch.multiple(S, CACHE_DIR=folder, CHUNK_DIR=chunks, HIST_PATH=os.path.join(folder, "history.json"),
                            STATS_PATH=os.path.join(folder, "stats.json"), LLM_CFG_PATH=os.path.join(folder, "config.json")), \
                patch.object(S, "current", return_value=copy.deepcopy(PROFILE)), \
                patch.object(S, "cfg_history"), \
                patch.object(S.urllib.request, "urlopen", side_effect=AssertionError("NETWORK FORBIDDEN")):
            yield folder


class DeepLifecycleContract(unittest.TestCase):
    def test_legacy_dryrun_uses_real_assertions_in_isolated_environment(self):
        with sandbox() as folder:
            before = dict(S.__dict__)
            transcript = io.StringIO()
            try:
                with contextlib.redirect_stdout(transcript), contextlib.redirect_stderr(transcript):
                    loaded = runpy.run_path(os.path.join(ROOT, "tests", "dryrun.py"), run_name="offline_dryrun")
                    loaded["main"].__globals__["OUT"] = folder
                    with self.assertRaises(SystemExit) as outcome:
                        loaded["main"]()
                self.assertEqual(outcome.exception.code, 0, transcript.getvalue())
            finally:
                for key, value in before.items():
                    if not key.startswith("__"):
                        setattr(S, key, value)
            print(transcript.getvalue())

    def test_legacy_control_uses_real_assertions_in_isolated_environment(self):
        with sandbox():
            before = dict(S.__dict__)
            transcript = io.StringIO()
            try:
                with contextlib.redirect_stdout(transcript), contextlib.redirect_stderr(transcript):
                    loaded = runpy.run_path(os.path.join(ROOT, "tests", "control.py"), run_name="offline_control")
                    status = loaded["main"]()
                self.assertEqual(status, 0, transcript.getvalue())
            finally:
                for key, value in before.items():
                    if not key.startswith("__"):
                        setattr(S, key, value)
            print(transcript.getvalue())

    def test_completed_force_job_reconnect_replays_without_restarting(self):
        calls = []
        docs = [{"name": "首章", "text": "深空里的故事。"}]
        def fake_analyze(ds, emit, **kwargs):
            calls.append(kwargs)
            emit("done", {"graph": {"meta": {"mode": kwargs.get("mode", "summary")}}, "key": "offline"})
        with sandbox(), patch.object(S, "JOBS", {}), patch.object(S, "analyze", side_effect=fake_analyze):
            job, attached = S.run_job(docs, True, mode="deep")
            deadline = time.monotonic() + 1
            while not job.finished and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertTrue(job.finished)
            same, attached = S.run_job(docs, True, mode="deep", job_key=job.key)
            self.assertIs(same, job)
            self.assertTrue(attached)
            self.assertEqual(len(calls), 1)
            self.assertEqual(S.jobs_list()[0]["mode"], "deep")
            with self.assertRaises(S.ApiError):
                S.run_job(docs, True, mode="summary", job_key=job.key)
            with self.assertRaises(S.ApiError):
                S.run_job(docs, True, mode="deep", job_key="expired-job")
            self.assertEqual(len(calls), 1)

    def test_live_summary_and_deep_jobs_do_not_cross_attach(self):
        entered, release = [], threading.Event()
        docs = [{"name": "首章", "text": "深空里的故事。"}]
        def fake_analyze(ds, emit, **kwargs):
            entered.append(kwargs.get("mode", "summary"))
            release.wait(1)
            emit("done", {"graph": {"meta": {"mode": kwargs.get("mode", "summary")}}})
        with sandbox(), patch.object(S, "JOBS", {}), patch.object(S, "analyze", side_effect=fake_analyze):
            try:
                summary, _ = S.run_job(docs, False)
                deep, attached = S.run_job(docs, False, mode="deep")
                same, deep_attached = S.run_job(docs, False, mode="deep")
                self.assertIsNot(summary, deep)
                self.assertFalse(attached)
                self.assertTrue(deep_attached)
                self.assertIs(same, deep)
                self.assertEqual({j["mode"] for j in S.jobs_list()}, {"summary", "deep"})
            finally:
                release.set()
                deadline = time.monotonic() + 1
                while any(not j.finished for j in (summary, deep)) and time.monotonic() < deadline:
                    time.sleep(0.005)
            self.assertCountEqual(entered, ["summary", "deep"])

    def test_failed_segment_and_resume_never_claim_full_semantic_completion(self):
        fail, calls = [True], []
        sections = ["第%d章\n材料%d。" % (i, i) for i in range(1, 5)]
        docs = [{"name": "全书", "text": "".join(sections)}]
        def fake_llm(prompt, schema, **kwargs):
            self.assertIs(schema, S.DEEP_EXTRACT_SCHEMA)
            chunk = prompt.split("=== 材料开始 ===\n", 1)[1].split("\n=== 材料结束 ===", 1)[0]
            calls.append(chunk)
            if "材料4。" in chunk and fail[0]:
                raise S.ApiError("401 offline simulated failure")
            return {"characters": [], "events": [{"chapter": chunk.split("\n")[0], "title": chunk[-4:], "quote": chunk[-4:], "characters": []}],
                    "extractionComplete": True, "layerStatus": {f: "complete" for f in S.AUX_GRAPH_FIELDS},
                    **{f: [] for f in S.AUX_GRAPH_FIELDS}}
        def fake_reduce(results, *args, **kwargs):
            return {"characters": [], "events": [e for r in results for e in r["events"]], "relations": []}
        with sandbox(), patch.object(S, "extraction_chunks", return_value=sections), \
                patch.object(S, "call_llm", side_effect=fake_llm), patch.object(S, "reduce_graph", side_effect=fake_reduce), \
                patch.object(S, "extract_storylines", return_value=0), \
                patch.object(S, "caps_for", return_value={"class": "standard"}), \
                patch.object(S, "caps_summary", return_value="offline"), \
                patch.object(S, "stats_add"), patch.object(S, "history_add"):
            def run(**kwargs):
                events = []
                S.analyze(docs, lambda ev, value: events.append((ev, value)), profile=PROFILE, mode="deep", **kwargs)
                return next(value["graph"] for ev, value in events if ev == "done")
            partial = run()
            self.assertFalse(partial["meta"]["extraction"]["processedComplete"])
            self.assertIs(partial["meta"]["extraction"]["complete"], False)
            self.assertEqual(partial["meta"]["extraction"]["failedSegments"], 1)
            self.assertEqual(len(calls), 4)
            cached = run()
            self.assertIs(cached["meta"]["extraction"]["complete"], False)
            self.assertEqual(len(calls), 4)
            fail[0] = False
            resumed = run(refresh=True)
            self.assertEqual(len(calls), 5, "resume should reuse three complete cached source segments")
            self.assertEqual(len(resumed["events"]), 4)
            self.assertTrue(resumed["meta"]["extraction"]["processedComplete"])
            self.assertIsNone(resumed["meta"]["extraction"]["complete"])
            self.assertEqual(resumed["meta"]["extraction"]["semanticCompleteness"], "unverified")

    def test_planning_cannot_reuse_summary_results_as_deep_cache(self):
        docs = [{"name": "首章", "text": "深空里的故事。"}]
        with sandbox() as folder, patch.object(S, "caps_for", return_value={"class": "standard"}), \
                patch.object(S, "caps_summary", return_value="offline"):
            normalized, _ = S.normalize_docs(docs)
            text = S.assemble(normalized)
            S.atomic_json(os.path.join(folder, S.result_key(text, PROFILE) + ".json"), {"meta": {"mode": "summary"}})
            summary = S.make_plan(docs, profile=PROFILE, mode="summary")
            deep = S.make_plan(docs, profile=PROFILE, mode="deep")
            self.assertTrue(summary["graph_cached"])
            self.assertFalse(deep["graph_cached"])
            self.assertNotEqual(summary["key"], deep["key"])
            self.assertFalse(deep["single"])

    def test_incomplete_or_malformed_deep_segments_are_not_resumable_successes(self):
        missing_status = {"characters": [], "events": [], "extractionComplete": True}
        incomplete = {"characters": [], "events": [], "extractionComplete": False, "layerStatus": {}}
        malformed = {"characters": None, "events": []}
        complete = {"characters": [], "events": [], "extractionComplete": True, "layerStatus": {}}
        self.assertFalse(S._extract_cache_valid(missing_status, "deep"))
        self.assertFalse(S._extract_cache_valid(incomplete, "deep"))
        self.assertFalse(S._extract_cache_valid(malformed, "deep"))
        self.assertTrue(S._extract_cache_valid(complete, "deep"))

    def test_all_segments_processed_does_not_hide_failed_profile_relation_or_storyline_pass(self):
        result = {"characters": [], "events": [], "extractionComplete": True,
                  "layerStatus": {f: "complete" for f in S.AUX_GRAPH_FIELDS}, **{f: [] for f in S.AUX_GRAPH_FIELDS}}
        graph = {"characters": [], "events": [], "relations": [],
                 "meta": {"pipeline": {"profile_failed": 2, "relation_failed": 1}, "storylines": {"failedSegments": 3}}}
        with sandbox(), patch.object(S, "call_llm", return_value=result), \
                patch.object(S, "reduce_graph", return_value=graph), patch.object(S, "extract_storylines", return_value=0), \
                patch.object(S, "caps_for", return_value={"class": "standard"}), \
                patch.object(S, "caps_summary", return_value="offline"), patch.object(S, "stats_add"), patch.object(S, "history_add"):
            events = []
            S.analyze([{"name": "设定", "text": "空星设定。"}], lambda ev, value: events.append((ev, value)), profile=PROFILE, mode="deep")
            final = next(value["graph"] for ev, value in events if ev == "done")
            info = final["meta"]["extraction"]
            self.assertTrue(info["processedComplete"])
            self.assertIs(info["complete"], False)
            self.assertEqual(info["failedProfiles"], 2)
            self.assertEqual(info["failedRelationBatches"], 1)
            self.assertEqual(info["failedStorylineSegments"], 3)
            self.assertEqual(info["reason"], "pipeline_gaps")


if __name__ == "__main__":
    unittest.main(verbosity=2)
