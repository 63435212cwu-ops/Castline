#!/usr/bin/env python3
"""Original-context retrieval never turns edited/spliced quotes into evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import serve as S
import narrative as N


class NarrativeContextContract(unittest.TestCase):
    def make(self, raw, quotes, chapters=None):
        docs = [{"sourceId": "source-context", "name": "原文", "text": raw}]
        graph = {"characters": [{"id": "character", "name": "甲", "aliases": []}],
                 "events": [{"id": "event-%d" % i, "order": i + 1,
                             "chapter": chapters[i] if chapters else "第一回", "quote": quote,
                             "summary": "仅用于定位测试，不能视为原文", "title": "测试事件", "characters": ["甲"]}
                            for i, quote in enumerate(quotes)]}
        return S.rebuild_sources(graph, docs), docs

    def test_volume_summary_prose_is_not_a_volume_boundary(self):
        """卷尾感言里的正文句子「第一卷是京察风云！」不得被当成卷边界。

        实测（大奉 @909362，文本 19.1% 处）：该句被收成 key='第1卷'、number=1，
        与真正的第一卷**撞键**。根因是 `context_chapter_spans` 的 `n == 1` 放行
        分支没有约束位置。本测试锁住「正文句不得成边界」。

        同时锁住反例：**无空格标题**（`第七十八章熟悉的气息`）属于真标题，
        必须仍然被接受 —— 修这个缺陷不能把真标题一起挡掉。
        """
        prose = ("第一卷结束了，想一想，还是写一章总结吧。\n\n"
                 "第一卷是京察风云！\n\n"
                 "主题就是政治斗争和连环案件。\n\n"
                 "第二卷，国士无双。\n\n")
        raw = "第一章 起\n\n正文甲。\n\n第二章 承\n\n正文乙。\n\n" + prose + \
              "第七十七章 前\n\n正文丙。\n\n" \
              "第七十八章熟悉的气息\n\n正文丁，这一章是连续编号里的真标题。\n\n" \
              "第七十九章 续\n\n正文戊。\n\n"
        spans = N.context_chapter_spans(raw)
        titles = [str(s.get("title") or "") for s in spans]
        keys = [str(s.get("key") or "") for s in spans]
        for t in titles:
            self.assertNotIn("京察风云", t,
                             "卷尾感言的正文句被当成了卷边界：" + t)
            self.assertNotIn("第一卷结束了", t, "卷尾感言被判成边界：" + t)
        self.assertTrue(any("熟悉的气息" in t for t in titles),
                        "无空格真标题被误挡：" + repr(titles))
        vol1 = [s for s in spans if str(s.get("key") or "") == "第1卷"]
        self.assertLessEqual(
            len(vol1), 1,
            "「第1卷」由多个边界产生（撞键）：" + repr([str(s.get("title")) for s in vol1]))
        for s in vol1:
            title = str(s.get("title") or "")
            self.assertNotIn("京察风云", title, "正文句产生了 key='第1卷' 的边界：" + title)
            self.assertNotIn("结束了", title, "卷尾感言产生了 key='第1卷' 的边界：" + title)

    def test_spliced_quote_locates_context_but_never_gets_verified_quote_ref(self):
        first, second = "甲打开古塔的密门并救出身后的同伴。", "乙带着钥匙回到城墙之外报告消息。"
        raw = "第一回\n\n" + first + "\n\n真实中间动作不能被省略成连续引句。\n\n" + second + "\n\n本场结束。"
        edited = first + "……" + second
        graph, docs = self.make(raw, [edited])
        self.assertFalse(graph["events"][0]["quoteRef"]["verified"])
        context = N.ContextIndex(S.source_specs(docs))
        refs = context.context_refs(graph["events"][0])
        self.assertTrue(refs)
        self.assertFalse(refs[0]["verified"])
        self.assertEqual(refs[0]["status"], "located_context")
        windows = N.source_windows(graph["events"], S.source_specs(docs), context_index=context)
        self.assertTrue(all(window["text"] == raw[window["start"]:window["end"]] for window in windows))
        self.assertNotIn(edited, "".join(window["text"] for window in windows))
        self.assertFalse(graph["events"][0]["quoteRef"]["verified"])

    def test_punctuation_edit_is_not_promoted_by_a_unique_substring(self):
        raw = "第一回\n\n甲对乙说道：“古塔里的门终于打开了，我们可以进去。”\n\n二人走近查看。"
        graph, docs = self.make(raw, ["甲对乙说道：古塔里的门终于打开了，我们可以进去。"])
        context = N.ContextIndex(S.source_specs(docs))
        self.assertEqual(context.locate(graph["events"][0])["method"], "unique_verbatim_fragment_in_chapter")
        self.assertFalse(graph["events"][0]["verified"])
        self.assertFalse(context.context_refs(graph["events"][0])[0]["verified"])

    def test_ambiguous_fragment_falls_back_to_chapter_without_claiming_found_event(self):
        quote = "甲打开古塔的密门并救出身后的同伴。"
        raw = "第一回\n\n" + quote + "\n\n" + quote + "\n\n章尾。"
        graph, docs = self.make(raw, [quote])
        context = N.ContextIndex(S.source_specs(docs))
        self.assertEqual(context.locate(graph["events"][0])["method"], "chapter_only")
        windows, coverage = N.source_windows(graph["events"], S.source_specs(docs), True, context)
        self.assertEqual(coverage["chapterOnlyEventIds"], ["event-0"])
        self.assertFalse(graph["events"][0]["verified"])
        self.assertIn(quote, windows[0]["text"])

    def test_fabricated_quote_in_named_chapter_remains_unverified_with_chapter_only_scope(self):
        raw = "第一回\n\n甲打开了城门，大家仍在等候。\n\n第二回\n\n乙并没有回城。"
        graph, docs = self.make(raw, ["本章根本没有这句话，而且它足够长。"])
        windows, coverage = N.source_windows(graph["events"], S.source_specs(docs), details=True)
        self.assertEqual(coverage["chapterOnlyEventIds"], ["event-0"])
        self.assertFalse(graph["events"][0]["verified"])
        self.assertNotIn("本章根本没有", windows[0]["text"])

    def test_unknown_chapter_and_unlocatable_quote_expose_missing_context(self):
        graph, docs = self.make("第一回\n\n真实原文。", ["没有这句足够长的伪造引文。"], ["不存在章"])
        windows, coverage = N.source_windows(graph["events"], S.source_specs(docs), details=True)
        self.assertEqual(windows, [])
        self.assertFalse(coverage["complete"])
        self.assertEqual(coverage["missingEventIds"], ["event-0"])

    def test_duplicate_source_identity_keeps_the_event_inside_the_bounded_input(self):
        quote = "城门守卫把来访者带到议事厅里，认真核对名册上的姓名和来访缘由。"
        raw = "第一回 长章\n\n" + "原文描写。" * 600 + "\n\n" + quote + "\n\n本场结束。"
        event = {"id": "event-duplicate", "chapter": "第一回", "quote": quote, "quoteVerified": False}
        graph = {"events": [event], "characters": []}
        for doc in [{"sourceId": "shared-original", "text": raw}, {"name": "同一原文", "text": raw}]:
            docs = [doc, dict(doc)]
            before = copy.deepcopy((graph, docs))
            specs = N.context_sources(docs)
            context = N.ContextIndex(specs)
            with self.subTest(explicit="sourceId" in doc), patch.object(N, "SOURCE_CHARS", 200):
                windows, coverage = N.source_windows([event], specs, details=True, context_index=context)
                self.assertEqual(len(context.sources), 1)
                self.assertEqual(context.locate(event)["method"], "unique_verbatim_fragment_in_chapter")
                self.assertTrue(coverage["complete"])
                self.assertEqual(coverage["chapterOnlyEventIds"], [])
                self.assertTrue(any(quote in window["text"] for window in windows))
                self.assertTrue(all(window["text"] == raw[window["start"]:window["end"]] for window in windows))
                plan_coverage = N.plan(graph, docs, layers=["tasks"])["sourceContext"]["coverage"]
                self.assertEqual(plan_coverage["originalChars"], len(raw))
                self.assertEqual(plan_coverage["includedChars"], coverage["providedChars"])
                self.assertFalse(context.context_refs(event)[0]["verified"])
            self.assertEqual((graph, docs), before)

    def test_duplicate_import_does_not_erase_real_source_conflicts_or_other_identities(self):
        quote = "城门守卫把来访者带到议事厅里，认真核对名册上的姓名和来访缘由。"
        raw = "第一回\n\n" + quote
        event = {"id": "event-conflict", "chapter": "第一回", "quote": quote}
        first = {"sourceId": "shared", "text": raw}
        conflict = dict(first, text=raw + "\n\n另一版本有额外的文字。")
        for docs in ([first, dict(first), conflict], [conflict, first, dict(first)]):
            specs = N.context_sources(docs)
            context = N.ContextIndex(specs)
            self.assertEqual(context.sources, [])
            self.assertIsNone(context.locate(event))
            coverage = N.plan({"events": [event]}, docs, layers=["tasks"])["sourceContext"]["coverage"]
            self.assertEqual(coverage["sourceIdentityConflicts"], ["shared"])
            self.assertEqual(coverage["includedChars"], 0)
        other_identity = N.ContextIndex(N.context_sources([first, dict(first), dict(first, sourceId="other")]))
        self.assertEqual(len(other_identity.sources), 2)
        self.assertIsNone(other_identity.locate(event))

    def test_duplicate_import_keeps_repeated_occurrences_ambiguous(self):
        quote = "甲打开古塔的密门并救出身后的同伴。"
        raw = "第一回\n\n" + quote + "\n\n" + quote + "\n\n章尾。"
        doc = {"sourceId": "repeated-source", "text": raw}
        event = {"id": "event-repeated", "chapter": "第一回", "quote": quote}
        context = N.ContextIndex(N.context_sources([doc, dict(doc)]))
        self.assertEqual(len(context.sources), 1)
        self.assertEqual(context.locate(event)["method"], "chapter_only")
        self.assertFalse(context.context_refs(event)[0]["verified"])

    def test_full_title_resolves_repeated_chapter_number_without_verifying_quote(self):
        raw = "第一章 风雪来客\n\n甲入城避雪。\n\n第二章\n\n甲启程。\n\n第一章 故人归来\n\n乙与甲重逢。"
        graph, docs = self.make(raw, ["无法匹配的转述，不是原句。"], ["第一章　故人归来"])
        context = N.ContextIndex(S.source_specs(docs))
        found = context.locate(graph["events"][0])
        self.assertEqual(found["method"], "chapter_only")
        self.assertEqual(found["start"], raw.index("第一章 故人归来"))
        self.assertFalse(graph["events"][0]["verified"])
        self.assertFalse(context.context_refs(graph["events"][0])[0]["verified"])

    def test_number_only_or_duplicate_full_title_remains_ambiguous(self):
        for label, second in [("第一章", "第一章 故人归来"), ("第一章 风雪来客", "第一章 风雪来客")]:
            raw = "第一章 风雪来客\n\n甲入城。\n\n第二章\n\n甲离城。\n\n" + second + "\n\n乙入城。"
            graph, docs = self.make(raw, ["无法匹配的转述，不是原句。"], [label])
            with self.subTest(label=label):
                self.assertIsNone(N.ContextIndex(S.source_specs(docs)).locate(graph["events"][0]))

    def test_publication_suffixes_do_not_hide_the_unique_original_chapter(self):
        for suffix in ["（感谢“山河墨韵”的白银盟）", "（为盟主加更）", "（7400）", "（万字大章，求月票）", "........."]:
            raw = "第一章 城门\n\n甲守城。\n\n第二章\n\n甲启程。\n\n第一章 故人归来" + suffix + "\n\n乙与甲重逢。"
            graph, docs = self.make(raw, ["无法匹配的转述，不是原句。"], ["第一章 故人归来"])
            index = N.ContextIndex(S.source_specs(docs))
            with self.subTest(suffix=suffix):
                found = index.locate(graph["events"][0])
                self.assertEqual(found["method"], "chapter_only")
                self.assertEqual(found["start"], raw.index("第一章 故人归来"))
                self.assertFalse(graph["events"][0]["verified"])
                self.assertFalse(index.context_refs(graph["events"][0])[0]["verified"])

    def test_narrative_subtitles_and_publication_key_collisions_stay_distinct(self):
        self.assertNotEqual(N._heading_key("第一章 故人（一）"), N._heading_key("第一章 故人（二）"))
        raw = "第一章 故人（求月票）\n\n甲回城。\n\n第二章\n\n甲离城。\n\n第一章 故人（7400）\n\n乙回城。"
        graph, docs = self.make(raw, ["无法匹配的转述，不是原句。"], ["第一章 故人"])
        self.assertIsNone(N.ContextIndex(S.source_specs(docs)).locate(graph["events"][0]))

    def test_update_schedule_prose_never_splits_a_real_chapter(self):
        raw = "第一章 城门\n\n甲守城。\n\n第二章 诈尸\n\n甲回城。\n\n    第二章更新时间是晚上8点——23点。\n\n乙也回城。\n\n第三章 归途\n\n丙回城。"
        graph, docs = self.make(raw, ["无法匹配的转述，不是原句。"], ["第二章 诈尸"])
        index = N.ContextIndex(S.source_specs(docs))
        self.assertEqual(len(index.sources[0]["chapterSpans"]), 3)
        found = index.locate(graph["events"][0])
        self.assertEqual(found["end"], raw.index("第三章 归途"))
        self.assertIn("乙也回城。", raw[found["start"]:found["end"]])

    def test_compact_headings_keep_real_boundaries_when_numbers_continue(self):
        raw = "第七十七章 前夜\n\n甲守城。\n\n第七十八章熟悉的气息\n\n乙抵达。\n\n第七十九章神魔终结的秘密\n\n丙抵达。\n\n第八十章 归来\n\n众人团聚。"
        graph, docs = self.make(raw, ["未提供原句"], ["第七十八章 熟悉的气息"])
        index = N.ContextIndex(S.source_specs(docs))
        found = index.locate(graph["events"][0])
        self.assertEqual(found["start"], raw.index("第七十八章"))
        self.assertEqual(found["end"], raw.index("第七十九章"))

    def test_navigation_prefixed_headings_share_canonical_source_boundaries(self):
        raw = ("第一回 开篇\n\n甲离城。\n\n回首页后一页前一页回目录第二回 来访\n\n"
               "乙带着钥匙回到城墙之外报告消息。\n\n回首页回目录第三回 团聚\n\n丙抵达。")
        graph, docs = self.make(raw, ["这是一句不存在的引用。"], ["第二回"])
        before = copy.deepcopy(graph)
        context = N.ContextIndex(S.source_specs(docs))
        self.assertEqual([span["number"] for span in context.sources[0]["chapterSpans"]], [1, 2, 3])
        found = context.locate(graph["events"][0])
        self.assertEqual(found["start"], raw.index("第二回"))
        self.assertEqual(found["end"], raw.index("第三回"))
        self.assertEqual(found["method"], "chapter_only")
        self.assertFalse(context.context_refs(graph["events"][0])[0]["verified"])
        self.assertEqual(graph, before)
        prose = "第一回 开篇\n甲说：回目录第二回 这是一段正文而非目录\n乙回城。"
        self.assertEqual(len(N.context_chapter_spans(prose)), 1)

    def test_sanguo_navigation_repair_restores_context_without_verifying_quotes(self):
        key = "f0b45e85aac6c95e584075a2"
        docs = json.loads((ROOT / "data/cache" / (key + ".docs.json")).read_text())
        graph = json.loads((ROOT / "data/cache" / (key + ".json")).read_text())
        before = copy.deepcopy(graph["events"])
        context = N.ContextIndex(S.source_specs(docs))
        spans = context.sources[0]["chapterSpans"]
        self.assertEqual(len(spans), 120)
        self.assertEqual([span["number"] for span in spans], list(range(1, 121)))
        missing = [event["id"] for event in graph["events"] if context.locate(event) is None]
        self.assertEqual(missing, [])
        for event in graph["events"]:
            for ref in context.context_refs(event):
                self.assertFalse(ref["verified"])
        self.assertEqual(graph["events"], before)

    def test_numeric_chapter_spelling_is_retrieval_only_and_keeps_volume_ambiguity(self):
        raw = "第一百九回 城门\n\n甲守城。\n\n第一百十回 出发\n\n乙离城。"
        graph, docs = self.make(raw, ["这个引句并没有出现。"], ["第一百零九回"])
        context = N.ContextIndex(S.source_specs(docs))
        found = context.locate(graph["events"][0])
        self.assertEqual(found["method"], "chapter_only")
        self.assertEqual(found["start"], 0)
        self.assertEqual(graph["events"][0]["chapter"], "第一百零九回")
        self.assertFalse(context.context_refs(graph["events"][0])[0]["verified"])
        repeated = raw + "\n\n第一百零九回 后卷\n\n丙归来。"
        docs[0]["text"] = repeated
        self.assertIsNone(N.ContextIndex(S.source_specs(docs)).locate(graph["events"][0]))

    def test_missing_unit_requires_both_neighbors_and_preserves_raw_heading(self):
        raw = "第一百零一章 前夜\n\n甲守城。\n\n第一百零二 万事俱备（20000/10万）\n\n乙抵达。\n\n第一百零三章 归来\n\n众人团聚。"
        graph, docs = self.make(raw, ["未提供原句"], ["第一百零二章 万事俱备"])
        index = N.ContextIndex(S.source_specs(docs))
        found = index.locate(graph["events"][0])
        self.assertEqual(found["start"], raw.index("第一百零二"))
        self.assertTrue(index.sources[0]["chapterSpans"][1]["missingUnit"])
        self.assertNotIn("第一百零二章", raw[found["start"]:found["end"]])
        self.assertFalse(index.context_refs(graph["events"][0])[0]["verified"])
        broken = raw.replace("第一百零三章", "第五章")
        self.assertFalse(any(span["missingUnit"] for span in N.context_chapter_spans(broken)))

    def test_formatted_verse_returns_original_span_not_a_reassembled_quote(self):
        raw = "第一章 春日\n\n疏影横斜水清浅，\n    暗香浮动月黄昏。\n\n第二章\n\n甲离城。\n\n第一章 冬日\n\n乙回城。"
        quoted = "疏影横斜水清浅，暗香浮动月黄昏。"
        graph, docs = self.make(raw, [quoted], ["第一章"])
        index = N.ContextIndex(S.source_specs(docs)); found = index.locate(graph["events"][0])
        self.assertEqual(found["method"], "ordered_verbatim_clauses_in_chapter")
        self.assertEqual(found["quote"], raw[found["start"]:found["end"]])
        self.assertIn("\n", found["quote"])
        self.assertNotEqual(found["quote"], quoted)
        self.assertFalse(graph["events"][0]["verified"])
        self.assertFalse(index.context_refs(graph["events"][0])[0]["verified"])

    def test_clause_retrieval_rejects_reordered_distant_duplicate_or_forged_fragments(self):
        a, b = "疏影横斜水清浅", "暗香浮动月黄昏"
        for content in [b + "，" + a, a + "。" * 950 + b, a + "，" + b + "，" + a, a + "，完全不存在的句子"]:
            raw = "第一章 春日\n\n" + content + "。\n\n第二章\n\n甲离城。\n\n第一章 冬日\n\n乙回城。"
            graph, docs = self.make(raw, [a + "，\n" + b], ["第一章"])
            with self.subTest(content=content[:35]):
                self.assertIsNone(N.ContextIndex(S.source_specs(docs)).locate(graph["events"][0]))

    def test_punctuation_only_match_keeps_raw_offsets_and_unverified_quotes(self):
        raw = "第一章 春日\n\n🌸甲说道：“城门已开。”乙立即转身。\n\n第二章 离城\n\n甲启程。\n\n第一章 冬日\n\n乙回城。"
        quoted = "城门已开。乙立即转身"
        graph, docs = self.make(raw, [quoted], ["第一章"])
        index = N.ContextIndex(S.source_specs(docs))
        event = graph["events"][0]; before = copy.deepcopy(event)
        found = index.locate(event)
        self.assertEqual(found["method"], "punctuation_normalized_context_in_chapter")
        self.assertEqual(found["start"], raw.index("城门已开"))
        self.assertEqual(found["quote"], "城门已开。”乙立即转身")
        self.assertEqual(raw[found["start"]:found["end"]], found["quote"])
        self.assertFalse(index.context_refs(event)[0]["verified"])
        self.assertFalse(event["verified"])
        self.assertEqual(event, before)

    def test_repetitions_in_one_named_chapter_supply_only_that_chapter(self):
        quote = "故人已回到城中。"
        raw = "第一章 春日\n\n" + quote + "\n\n" + quote + "\n\n第二章 离城\n\n甲启程。\n\n第一章 冬日\n\n乙回城。"
        graph, docs = self.make(raw, [quote], ["第一章"])
        index = N.ContextIndex(S.source_specs(docs)); found = index.locate(graph["events"][0])
        self.assertEqual(found["method"], "chapter_only")
        self.assertEqual(found["start"], 0)
        self.assertEqual(found["end"], raw.index("第二章"))
        self.assertEqual(found["quote"], "")
        _, coverage = N.source_windows(graph["events"], S.source_specs(docs), True, index)
        self.assertEqual(coverage["chapterOnlyEventIds"], ["event-0"])
        self.assertFalse(index.context_refs(graph["events"][0])[0]["verified"])

    def test_formatting_match_does_not_cross_chapters_or_remove_words(self):
        for content, quote, other in [
                ("甲回城中。乙来相见。", "甲回城中，丙来相见", "乙回城。"),
                ("甲回城中。乙来相见。", "甲回城，乙来相见", "乙回城。"),
                ("甲回城中。", "甲回城中，乙来相见", "乙回城。"),
                ("故人已回城。", "故人已回城！", "乙回城。"),
                ("甲回城中" + "。" * 950 + "乙来相见", "甲回城中，乙来相见", "乙回城。"),
                ("甲回城中。乙来相见。", "甲回城中乙来相见", "甲回城中。乙来相见。")]:
            raw = "第一章 春日\n\n" + content + "\n\n第二章 离城\n\n乙来相见。\n\n第一章 冬日\n\n" + other
            graph, docs = self.make(raw, [quote], ["第一章"])
            with self.subTest(content=content[:20], quote=quote):
                self.assertIsNone(N.ContextIndex(S.source_specs(docs)).locate(graph["events"][0]))

    def test_wrong_chapter_can_retrieve_only_long_globally_unique_verbatim_text(self):
        fragment = "城门守卫把来访者带到议事厅里，认真核对名册上的姓名和来访缘由"
        raw = "第一章 春日\n\n甲入城。\n\n第二章 接待\n\n" + fragment + "，然后向管事禀报。\n\n第一章 冬日\n\n乙回城。"
        quote = fragment + "。这句经过编辑，不能标成原文。"
        graph, docs = self.make(raw, [quote], ["第一章"])
        index = N.ContextIndex(S.source_specs(docs)); found = index.locate(graph["events"][0])
        self.assertEqual(found["method"], "unique_verbatim_fragment_in_source")
        self.assertEqual(found["start"], raw.index(fragment))
        self.assertEqual(found["quote"], raw[found["start"]:found["end"]])
        self.assertFalse(graph["events"][0]["verified"])
        self.assertFalse(index.context_refs(graph["events"][0])[0]["verified"])
        duplicate = raw + "\n\n第三章 回访\n\n" + fragment + "，然后向管事禀报。"
        graph, docs = self.make(duplicate, [quote], ["第一章"])
        self.assertIsNone(N.ContextIndex(S.source_specs(docs)).locate(graph["events"][0]))
        graph, docs = self.make(raw, ["认真核对名册上的姓名！"], ["第一章"])
        self.assertIsNone(N.ContextIndex(S.source_specs(docs)).locate(graph["events"][0]))

    def test_global_fragment_cannot_verify_negation_edit_or_choose_between_sources(self):
        fragment = "城门守卫把来访者带到议事厅里，认真核对名册上的姓名和来访缘由"
        raw = "第一章 春日\n\n甲入城。\n\n第二章 接待\n\n" + fragment + "，然后向管事禀报。\n\n第一章 冬日\n\n乙回城。"
        quote = "城门守卫没有" + fragment[4:] + "。"
        graph, docs = self.make(raw, [quote], ["第一章"])
        index = N.ContextIndex(S.source_specs(docs)); event = graph["events"][0]
        found = index.locate(event)
        self.assertEqual(found["method"], "unique_verbatim_fragment_in_source")
        self.assertNotEqual(found["quote"], quote)
        self.assertFalse(index.context_refs(event)[0]["verified"])
        self.assertFalse(event["quoteVerified"])
        self.assertFalse(event["claimVerified"])
        other = {"sourceId": "other-source", "name": "另一原文", "text": "第三章 回访\n\n" + fragment}
        self.assertIsNone(N.ContextIndex(S.source_specs(docs + [other])).locate(event))

    def test_formatting_retrieval_preserves_numeric_punctuation_and_math(self):
        for original, edited in [("1.5", "15"), ("-15", "15"), ("1/5", "15"),
                                 ("15%", "15"), ("1:5", "15"), ("1 5", "15"),
                                 ("1\n  5", "15"), ("1+5", "15"), ("1−5", "15")]:
            raw = "第一章 春日\n账簿登记" + original + "两税银。\n第二章 归途\n甲离城。\n第一章 冬日\n乙回城。"
            graph, docs = self.make(raw, ["账簿登记" + edited + "两税银。"], ["第一章"])
            before = copy.deepcopy(graph["events"][0])
            with self.subTest(original=original):
                index = N.ContextIndex(S.source_specs(docs))
                self.assertIsNone(index.locate(graph["events"][0]))
                self.assertEqual(index.context_refs(graph["events"][0]), [])
                self.assertEqual(graph["events"][0], before)

    def test_spliced_long_fragments_from_multiple_sources_remain_missing(self):
        first = "城门守卫把来访者带到议事厅里，认真核对名册上的姓名和来访缘由"
        second = "远方使者连夜赶到山顶的大殿，向众人说明洪水即将淹没南面的村落"
        docs = [{"sourceId": "first", "text": "第一章 开篇\n门开了。\n第二章 接待\n" + first},
                {"sourceId": "second", "text": "第一章 开篇\n门关了。\n第二章 来使\n" + second}]
        for parts, chapter in [((first, second), "第一章"), ((second, first), "第一章"),
                               ((first, second), "第二章"), ((first, second), "不存在章")]:
            graph = S.rebuild_sources({"characters": [], "events": [{"id": "event-spliced", "chapter": "第一章",
                                      "title": "合成测试", "order": 1, "quote": "……".join(parts)}]}, docs)
            graph["events"][0]["chapter"] = chapter
            before = copy.deepcopy(graph["events"][0])
            index = N.ContextIndex(S.source_specs(docs))
            self.assertIsNone(index.locate(graph["events"][0]))
            windows, coverage = N.source_windows(graph["events"], S.source_specs(docs), True, index)
            self.assertEqual(windows, [])
            self.assertFalse(coverage["complete"])
            self.assertEqual(coverage["missingEventIds"], ["event-spliced"])
            self.assertEqual(graph["events"][0], before)

    def test_dafeng_missing_context_repairs_keep_source_text_and_quote_trust(self):
        key = "2ef47b2ecaa99a67352091d5"
        docs = json.loads((ROOT / "data/cache" / (key + ".docs.json")).read_text())
        cached = json.loads((ROOT / "data/cache" / (key + ".json")).read_text())
        positions = [63, 97, 101, 363, 368, 450, 451, 454, 456, 458, 462, 1955]
        graph = S.rebuild_sources({"characters": [], "events": [cached["events"][i] for i in positions]}, docs)
        before = copy.deepcopy(graph["events"])
        specs = S.source_specs(docs); index = N.ContextIndex(specs)
        missing, chapter_only = [], []
        for position, event in zip(positions, graph["events"]):
            found = index.locate(event)
            if not found:
                missing.append(position)
                continue
            if found["method"] == "chapter_only":
                chapter_only.append(position)
            else:
                self.assertEqual(found["quote"], docs[0]["text"][found["start"]:found["end"]])
            refs = index.context_refs(event)
            self.assertFalse(refs[0]["verified"])
            self.assertEqual(refs[0]["eventQuoteVerification"], "not_promoted")
        self.assertEqual(missing, [63, 450, 458, 1955])
        self.assertEqual(chapter_only, [97, 368])
        self.assertEqual(graph["events"], before)

    def test_large_original_spans_split_model_batches_and_preserve_real_text(self):
        quotes = ["甲在第%d处门前停下，决定等候同伴到来。" % i for i in range(3)]
        raw = "\n\n".join("第%s回\n\n%s%s\n\n本场收束。" % (name, quote, "真实原文描写" * 130)
                              for name, quote in zip(("一", "二", "三"), quotes))
        graph, docs = self.make(raw, quotes, ["第一回", "第二回", "第三回"])
        with patch.object(N, "SOURCE_CHARS", 1500):
            info = N.plan(graph, docs, layers=["tasks"])
            self.assertGreater(info["estimatedCalls"], 1)
            index = N.ContextIndex(S.source_specs(docs))
            groups = N.context_groups_for(graph["events"], S.source_specs(docs), index)
            self.assertEqual(len(groups), info["estimatedCalls"])
            for group in groups:
                windows, coverage = N.source_windows(group, S.source_specs(docs), details=True, context_index=index)
                self.assertLessEqual(sum(len(window["text"]) for window in windows), 1500)
                self.assertTrue(coverage["complete"])
                self.assertTrue(all(window["text"] == raw[window["start"]:window["end"]] for window in windows))

    def test_single_oversized_chapter_is_explicitly_partial_not_silently_complete(self):
        raw = "第一回\n\n" + "长章原文内容" * 500
        graph, docs = self.make(raw, ["无法定位的伪引句，但是章节标签有效。"])
        with patch.object(N, "SOURCE_CHARS", 500):
            windows, coverage = N.source_windows(graph["events"], S.source_specs(docs), details=True)
        self.assertFalse(coverage["complete"])
        self.assertEqual(coverage["providedChars"], 500)
        self.assertGreater(coverage["requiredChars"], 500)
        self.assertFalse(graph["events"][0]["verified"])

    def test_source_only_cannot_misreport_partial_event_scope(self):
        graph, docs = self.make("第一回\n\n甲打开古塔的密门并救出身后的同伴。", ["甲打开古塔的密门并救出身后的同伴。"])
        with self.assertRaisesRegex(N.InvalidResult, "full graph"):
            N.plan(graph, docs, event_ids=["event-0"], source_only=True)

    def test_source_input_union_deduplicates_overlap_and_keeps_exact_gaps(self):
        specs = N.context_sources([{"sourceId": "source", "text": "😀abcdefghij"}])
        def window(start, end):
            return {"sourceId": "source", "textHash": specs[0]["textHash"], "start": start, "end": end}
        coverage = N.source_context_coverage(specs + specs, [window(1, 4), window(3, 6), window(1, 4), window(8, 10)])
        self.assertEqual(coverage["originalChars"], 11)
        self.assertEqual(coverage["includedChars"], 7)
        self.assertEqual(coverage["notIncludedChars"], 4)
        self.assertEqual(coverage["sources"][0]["notIncludedRanges"], [
            {"start": 0, "end": 1, "chars": 1}, {"start": 6, "end": 8, "chars": 2}, {"start": 10, "end": 11, "chars": 1}])
        self.assertFalse(coverage["allOriginalIncluded"])
        self.assertEqual(coverage["eventRecall"], "unknown")

    def test_plan_coverage_counts_bounded_input_not_requested_long_chapter(self):
        raw = "第一回\n\n" + "长章原文内容" * 500
        graph, docs = self.make(raw, ["本句无法定位，但章名可定位。"])
        before = copy.deepcopy(graph)
        with patch.object(N, "SOURCE_CHARS", 500):
            info = N.plan(graph, docs, layers=["tasks"])
        coverage = info["sourceContext"]["coverage"]
        self.assertEqual(coverage["includedChars"], 500)
        self.assertEqual(coverage["notIncludedChars"], len(raw) - 500)
        self.assertEqual(coverage["sources"][0]["notIncludedRanges"][0]["start"], 500)
        self.assertGreater(info["sourceContext"]["batches"][0]["requiredChars"], 500)
        self.assertEqual(info["identity"]["contextHash"], N.digest(info["sourceContext"]["batches"]))
        self.assertEqual(graph, before)

    def test_all_event_contexts_do_not_claim_all_original_or_semantic_coverage(self):
        quote = "甲打开古塔的密门并救出身后的同伴。"
        raw = "第一回\n\n" + quote + "\n\n同伴离开。\n\n第二回\n\n" + "这一整章没有进入事件清单。" * 3
        graph, docs = self.make(raw, [quote])
        info = N.plan(graph, docs, layers=["tasks"])
        coverage = info["sourceContext"]["coverage"]
        self.assertEqual(info["sourceContext"]["completeSceneBatches"], info["batches"])
        self.assertFalse(coverage["allOriginalIncluded"])
        self.assertGreater(coverage["notIncludedChars"], 0)
        self.assertEqual(coverage["state"], "scheduled")
        self.assertEqual(coverage["semanticCompleteness"], "unverified")

    def test_source_only_and_absent_sources_cannot_report_model_reading(self):
        graph, docs = self.make("第一回\n\n甲已回到城中。", ["甲已回到城中。"])
        coverage = N.plan(graph, docs, source_only=True)["sourceContext"]["coverage"]
        self.assertEqual(coverage["includedChars"], 0)
        self.assertEqual(coverage["state"], "not_requested")
        self.assertEqual(coverage["notIncludedChars"], len(docs[0]["text"]))
        absent = N.plan(graph, [], layers=["tasks"])["sourceContext"]["coverage"]
        self.assertIsNone(absent["includedRatio"])
        self.assertTrue(absent["missingSources"])
        self.assertFalse(absent["allOriginalIncluded"])

    def test_stale_ambiguous_and_invalid_source_ranges_never_hide_gaps(self):
        specs = N.context_sources([{"sourceId": "same", "text": "原文一"}, {"sourceId": "same", "text": "原文二"},
                                   {"sourceId": "unique", "text": "第三份原文"}])
        def window(spec, start, end, **extra):
            return dict({"sourceId": spec["id"], "textHash": spec["textHash"], "start": start, "end": end}, **extra)
        ranges = [window(specs[0], 0, 3), window(specs[2], 0, 2, textHash="stale"),
                  window(specs[2], True, 2), window(specs[2], -1, 2), window(specs[2], 1, 99)]
        coverage = N.source_context_coverage(specs, ranges)
        self.assertEqual(coverage["sourceIdentityConflicts"], ["same"])
        self.assertEqual(coverage["rejectedRangeCount"], 5)
        self.assertEqual(coverage["includedChars"], 0)
        self.assertEqual(coverage["originalChars"], coverage["notIncludedChars"])

    def test_complete_source_input_still_does_not_verify_semantics(self):
        specs = N.context_sources([{"sourceId": "source", "text": "全部原文"}])
        coverage = N.source_context_coverage(specs, [{"sourceId": "source", "textHash": specs[0]["textHash"], "start": 0, "end": 4}],
                                             state="accepted_batches")
        self.assertTrue(coverage["allOriginalIncluded"])
        self.assertEqual(coverage["includedRatio"], 1)
        self.assertEqual(coverage["sources"][0]["notIncludedRanges"], [])
        self.assertEqual(coverage["semanticCompleteness"], "unverified")

    def test_jobs_snapshot_exposes_exact_enrichment_plan_and_source_only(self):
        profile = {"kind": "anthropic", "model": "offline", "base_url": "http://invalid.local", "api_key": "OFFLINE"}
        job = S.Job("job-offline", base_key="1234abcd", profile=profile, kind="enrich")
        job.enrichment_plan = {"key": "plan-identity", "sourceOnly": True}
        with patch.object(S, "JOBS", {job.key: job}):
            snapshot = S.jobs_list()[0]
        self.assertEqual(snapshot["enrichmentPlanKey"], "plan-identity")
        self.assertTrue(snapshot["sourceOnly"])

    def test_redboy_original_scene_covers_all_gold_quotes_without_promoting_legacy_quotes(self):
        key = "d16db79a529a1727352091d5"
        docs = json.loads((ROOT / "data/cache" / (key + ".docs.json")).read_text())
        graph = S.rebuild_sources(json.loads((ROOT / "data/cache" / (key + ".json")).read_text()), docs)
        events = graph["events"][178:199]
        old_flags = [event["verified"] for event in events]
        specs = S.source_specs(docs)
        windows, coverage = N.source_windows(events, specs, details=True)
        self.assertTrue(coverage["complete"])
        self.assertEqual(len(windows), 1)
        self.assertLessEqual(coverage["providedChars"], 24000)
        self.assertGreater(coverage["providedChars"], 23000)
        gold = json.loads((ROOT / "tests/fixtures/narrative-gold-xiyou.json").read_text())
        refs = []
        def visit(value):
            if isinstance(value, dict):
                if value.get("match") == "exact" and value.get("textHash"):
                    refs.append(value)
                for nested in value.values():
                    visit(nested)
            elif isinstance(value, list):
                for nested in value:
                    visit(nested)
        visit(gold)
        for ref in refs:
            self.assertTrue(any(window["sourceId"] == ref["sourceId"] and window["start"] <= ref["start"]
                                and window["end"] >= ref["end"] for window in windows), ref["quote"])
        self.assertEqual([event["verified"] for event in events], old_flags)
        self.assertEqual(sum(old_flags), 6)
        self.assertEqual(N.plan(graph, docs, event_ids=gold["eventIds"])["estimatedCalls"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
