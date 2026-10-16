#!/usr/bin/env python3
"""Offline v4 source/deep-extraction contract. Never calls a paid model."""
import copy
import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("castline_source_test", os.path.join(ROOT, "serve.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


class SourceContract(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(S.urllib.request, "urlopen", side_effect=AssertionError("network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.profile = {"kind": "anthropic", "model": "offline-contract", "base_url": "http://invalid.local", "api_key": ""}

    def process(self, graph, docs=None):
        corpus = S.Corpus("", S.source_specs(docs)) if docs else None
        return S.postprocess(copy.deepcopy(graph), profile=self.profile, corpus=corpus)

    def test_exact_anchor_is_replayable(self):
        raw = "  第一章\n😀北辰点亮了古塔。\n"
        ref = S.source_anchor(raw, "北辰点亮了古塔。", source_id="original-source")
        self.assertTrue(ref["verified"])
        self.assertEqual(raw[ref["start"]:ref["end"]], ref["quote"])
        self.assertEqual(ref["textHash"], hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual(ref["offsetUnit"], "codepoint")
        self.assertEqual(ref["sourceId"], "original-source")

    def test_normalized_quote_never_invents_offsets(self):
        ref = S.source_anchor("她推开古老的铁门，回头说道：走吧。", "她推开古老的铁门,回头说道:走吧。")
        self.assertFalse(ref["verified"])
        self.assertEqual(ref["match"], "normalized")
        self.assertNotIn("start", ref)
        self.assertNotIn("end", ref)

    def test_missing_and_repeated_quotes_remain_unverified(self):
        for raw, q in (("古塔倒塌。", "不存在"), ("门开了。门开了。", "门开了。")):
            ref = S.source_anchor(raw, q)
            self.assertFalse(ref["verified"])
            self.assertNotIn("start", ref)

    def test_exact_match_beats_normalized_match_in_earlier_source(self):
        refs = S.source_specs([{"name": "a", "text": "北辰来到这里，群星再次闪烁。"},
                               {"name": "b", "text": "北辰来到这里,群星再次闪烁。"}])
        ref = S.Corpus("", refs).anchor("北辰来到这里,群星再次闪烁。")
        self.assertTrue(ref["verified"])
        self.assertEqual(ref["sourceId"], refs[1]["id"])

    def test_original_source_identity_survives_normalization(self):
        raw = "\n  古塔倒塌。  \n"
        docs, _ = S.normalize_docs([{"id": "author-upload-17", "name": "章一", "text": raw}])
        source = S.source_specs(docs)[0]
        self.assertEqual(source["id"], "author-upload-17")
        self.assertEqual(source["text"], raw)
        self.assertEqual(source["textHash"], hashlib.sha256(raw.encode()).hexdigest())

    def test_world_event_is_not_deleted(self):
        g = self.process({"characters": [], "events": [{"order": 19, "chapter": "章一", "title": "星落", "summary": "星空熄灭。", "characters": []}]})
        self.assertEqual(len(g["events"]), 1)
        self.assertTrue(g["events"][0]["orphan"])
        self.assertEqual(g["events"][0]["rawOrder"], 19)
        self.assertEqual(g["meta"]["eventIndexMap"]["rawOrderToNormalized"], {"19": [0]})

    def test_storyline_references_follow_source_orders_after_sort_dedupe(self):
        g = self.process({"characters": [], "events": [
            {"id": "last", "order": 90, "title": "归来", "chapter": "终章"},
            {"id": "first", "order": 12, "title": "出发", "chapter": "首章"},
            {"id": "first", "order": 14, "title": "出发", "chapter": "首章"}],
            "storylines": [{"id": "main", "name": "归途", "kind": "主线", "events": [12, 90]}]})
        self.assertEqual([e["id"] for e in g["events"]], ["first", "last"])
        self.assertEqual(g["storylines"][0]["events"], [1, 2])
        self.assertEqual(g["meta"]["eventIndexMap"]["rawOrderToNormalized"]["14"], [0])

    def test_ambiguous_event_order_is_not_randomly_attached(self):
        g = self.process({"events": [{"order": 4, "title": "甲"}, {"order": 4, "title": "乙"}, {"order": 9, "title": "丙"}],
                          "storylines": [{"id": "s", "name": "线", "kind": "主线", "events": [4, 9]}]})
        self.assertEqual(g["storylines"][0]["events"], [3])
        self.assertTrue(g["meta"]["quality"]["event_mapping_warn"])

    def test_identical_prose_with_distinct_source_identity_is_preserved(self):
        g = self.process({"events": [{"id": "one", "title": "醒来", "quote": "他醒来。", "order": 1},
                                     {"id": "two", "title": "醒来", "quote": "他醒来。", "order": 2}]})
        self.assertEqual([e["id"] for e in g["events"]], ["one", "two"])

    def test_existing_ids_and_optional_payload_are_preserved(self):
        graph = {"characters": [{"id": "ch-authored", "name": "北辰"}],
                 "events": [{"id": "ev-authored", "order": 2, "title": "入塔", "characters": ["北辰"]}],
                 "locations": [{"id": "loc-authored", "name": "古塔", "floor": 9}],
                 "items": [], "characterStates": [{"id": "st-authored", "characterId": "ch-authored", "chapterRange": ["章一", "章二"], "attrs": {"意志": {"score": 81, "evidence": ["她没有退却。"]}}}]}
        g = self.process(graph)
        self.assertEqual(g["characters"][0]["id"], "ch-authored")
        self.assertEqual(g["events"][0]["id"], "ev-authored")
        self.assertEqual(g["locations"][0]["floor"], 9)
        self.assertEqual(g["characterStates"][0]["chapterRange"], ["章一", "章二"])
        self.assertFalse(g["meta"]["coverage"]["items"]["known"])
        self.assertNotIn("clues", g)

    def test_entity_id_zero_and_entityid_only_survive(self):
        g = self.process({"characters": [{"id": 0, "name": "零"}],
                          "events": [{"entityId": "writer-event", "title": "事件"}]})
        self.assertEqual(g["characters"][0]["id"], 0)
        self.assertEqual(g["events"][0]["id"], "writer-event")

    def test_missing_measurements_are_unknown(self):
        g = self.process({"characters": [{"name": "甲", "attrs": {"意志": {"score": 50, "evidence": []}}}, {"name": "乙"}],
                          "relations": [{"a": "甲", "b": "乙", "kind": "同伴", "evidence": "同行。", "arc": "相遇到同行"}]})
        self.assertIsNone(g["characters"][0]["importance"])
        self.assertIsNone(g["characters"][0]["attrs"]["意志"]["score"])
        self.assertIsNone(g["relations"][0]["strength"])
        self.assertEqual(g["relations"][0]["arc"], "相遇到同行")
        self.assertEqual(g["relations"][0]["evidence"], "同行。")

    def test_v4_contract_is_idempotent_and_ids_ignore_character_sort(self):
        graph = {"characters": [{"name": "甲"}, {"name": "乙"}], "events": [{"order": 8, "title": "无主事件"}]}
        a = self.process(graph)
        b = self.process(a)
        c = self.process(dict(graph, characters=list(reversed(graph["characters"]))))
        self.assertEqual(a["meta"]["migrations"], b["meta"]["migrations"])
        self.assertEqual(a["events"][0]["id"], b["events"][0]["id"])
        self.assertEqual({c["name"]: c["id"] for c in a["characters"]}, {c["name"]: c["id"] for c in c["characters"]})

    def test_source_refs_and_provenance_are_hash_only(self):
        docs = [{"name": "首章", "text": "北辰点亮古塔。"}]
        g = self.process({"events": [{"order": 1, "quote": "北辰点亮古塔。"}]}, docs)
        S._graph_contract(g, corpus=S.Corpus("", S.source_specs(docs)), docs=docs)
        self.assertTrue(g["events"][0]["sourceRefs"][0]["verified"])
        self.assertTrue(g["meta"]["provenance"]["known"])
        self.assertNotIn("text", g["meta"]["sources"][0])

    def test_deep_chunks_cover_submitted_text_without_overlap_or_drop(self):
        text = "第一章 起始\n" + "甲" * 9100 + "\n第二章 夜色\n" + "乙" * 7312
        with patch.object(S, "extraction_chunk_limit", return_value=1200):
            chunks = S.extraction_chunks(text, self.profile, "deep")
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(c) <= 1200 for c in chunks))
        self.assertGreater(len(chunks), 12)

    def test_summary_and_deep_cache_identities_are_isolated(self):
        self.assertNotEqual(S.result_key("材料", self.profile), S.result_key("材料", self.profile, "deep"))
        self.assertNotEqual(S._chunk_key("材料", self.profile), S._chunk_key("材料", self.profile, "deep"))

    def test_split_merge_preserves_six_entity_layers(self):
        a = {"characters": [], "events": [], "extractionComplete": True, "layerStatus": {f: "complete" for f in S.AUX_GRAPH_FIELDS}}
        b = copy.deepcopy(a)
        for f in S.AUX_GRAPH_FIELDS:
            a[f] = [{"id": f + "1"}]
            b[f] = [{"id": f + "2"}]
        merged = S._merge_extract(a, b)
        self.assertTrue(merged["extractionComplete"])
        self.assertTrue(all(len(merged[f]) == 2 for f in S.AUX_GRAPH_FIELDS))

    def test_storyline_data_is_not_cut_to_display_budget(self):
        events = [{"order": i + 1, "title": "点%d" % i} for i in range(70)]
        lines = [{"id": "S%d" % i, "name": "线%d" % i, "events": [i + 1], "kind": "主线"} for i in range(70)]
        out, warn = S.norm_storylines(lines, events, [])
        self.assertEqual(len(out), 70)
        self.assertTrue(any("全量保留" in w for w in warn))

    def test_reduce_preserves_world_events_and_optional_layers(self):
        result = {"characters": [], "events": [{"title": "星落", "chapter": "序章", "characters": []}],
                  "locations": [{"name": "星海"}], "layerStatus": {"locations": "complete"}}
        def fake(prompt, schema, **kwargs):
            if schema is S.CANON_SCHEMA:
                return {"title": "空星", "synopsis": "", "characters": [], "camps": [], "not_characters": []}
            if schema is S.RELATION_SCHEMA:
                return {"relations": []}
            self.fail("unexpected model pass")
        with patch.object(S, "call_llm", side_effect=fake):
            graph = S._reduce_graph([result], lambda *args: None, ck=lambda: None, profile=self.profile)
        self.assertEqual(len(graph["events"]), 1)
        self.assertEqual(graph["locations"][0]["name"], "星海")
        self.assertTrue(graph["meta"]["coverage"]["locations"]["known"])

    def test_deep_saturation_splits_source_and_never_claims_semantic_completeness(self):
        calls, done = [], []
        def fake_llm(prompt, schema, **kwargs):
            self.assertIs(schema, S.DEEP_EXTRACT_SCHEMA)
            calls.append(prompt)
            if len(calls) == 1:
                return {"characters": [], "events": [{"title": str(i)} for i in range(32)], "extractionComplete": True}
            return {"characters": [], "events": [{"title": "世界事件%d" % len(calls), "characters": [], "quote": "", "chapter": "首章"}],
                    "extractionComplete": True, "layerStatus": {f: "complete" for f in S.AUX_GRAPH_FIELDS},
                    **{f: [] for f in S.AUX_GRAPH_FIELDS}}
        def fake_reduce(results, *args, **kwargs):
            events = [e for r in results for e in r["events"]]
            return {"characters": [], "events": events, "relations": []}
        with tempfile.TemporaryDirectory(prefix="castline-source-contract-") as tmp:
            chunkdir = os.path.join(tmp, "chunks")
            os.mkdir(chunkdir)
            with patch.multiple(S, CACHE_DIR=tmp, CHUNK_DIR=chunkdir), \
                    patch.object(S, "call_llm", side_effect=fake_llm), \
                    patch.object(S, "reduce_graph", side_effect=fake_reduce), \
                    patch.object(S, "extract_storylines", return_value=0), \
                    patch.object(S, "caps_for", return_value={"class": "standard"}), \
                    patch.object(S, "caps_summary", return_value="offline"), \
                    patch.object(S, "stats_add"), patch.object(S, "history_add"), patch.object(S, "cfg_history"):
                S.analyze([{"name": "首章", "text": "星空。" * 500}], lambda ev, value: done.append((ev, value)),
                          profile=self.profile, mode="deep")
        self.assertEqual(len(calls), 3)
        graph = next(value["graph"] for ev, value in done if ev == "done")
        self.assertEqual(len(graph["events"]), 2)
        self.assertTrue(graph["meta"]["extraction"]["processedComplete"])
        self.assertIsNone(graph["meta"]["extraction"]["complete"])
        self.assertEqual(graph["meta"]["mode"], "deep")


if __name__ == "__main__":
    unittest.main(verbosity=2)
