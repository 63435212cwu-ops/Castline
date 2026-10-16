#!/usr/bin/env python3
"""P04 叙事层契约测试：因果 / 伏笔 / 状态 / 关系产物必须可回到原文、四态合法、无未标记环。

断言分组（对应计划硬性要求）：
  A 引文可回到原文   —— 每条 quote 必须逐字是原文子串（text.find(quote) >= 0），
                        且 sourceRefs 里的 start/end 必须真的取出这段文字。
  B 四态标记合法     —— evidenceState ∈ {explicit, inferred, derived, unverified}，
                        且 basis 与 evidenceState 的映射一致（不把归纳写成明确）。
  C 无环或环被标记   —— propagationGraph.cycles 与实际边一致；有环必须已登记。
  D 同场未被升格     —— 无事件级断言的关系必须 claimTier=co_presence_only 且带
                        「无事件级锚点」说明；不得出现 evidenceState=explicit。
  E 身份冲突不归并   —— reviewIssues 涉及的人物不出确定性因果/关系结论。
  F 定位口径不混同   —— match != exact 的锚点不得计入「已核验引句」。
  G 不删除既有声明   —— 基线 causeEdges/clues/characterStates 必须全部出现在产物的
                        carriedFromBaseline 里（要么保留要么降级，不能消失）。

离线运行，只读 tests/fixtures/contracts/ 与 data/，不写任何文件。
    python3 tests/narrative_layers_contract.py
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NARR = ROOT / "tests" / "fixtures" / "contracts" / "narrative"
CACHE = ROOT / "data" / "cache"

BOOKS = [
    ("9b676d7031b1bcd3b8377a18", "大奉打更人"),
    ("df959d743e53206f56db2f92", "西游记"),
    ("152e2a6eed94f1075e7e7070", "三国演义"),
]

BASIS_OF_STATE = {
    "explicit": "explicit",
    "inferred": "synthesis",
    "derived": "inference",
    "unverified": "unverified",
}
EVIDENCE_STATES = tuple(BASIS_OF_STATE)

REQUIRED_DOCS = {
    "causal": ("edges", "propagationGraph", "extractionReport"),
    "clues": ("clues", "unresolvedClues"),
    "states": ("states", "transitions", "knowledge"),
    "relations": ("relations", "tierCounts"),
}


def load_doc(book_key: str, layer: str) -> dict:
    path = NARR / f"{book_key}.{layer}.json"
    if not path.exists():
        raise AssertionError(f"required narrative fixture missing: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_text(book_key: str) -> str:
    return json.loads((CACHE / f"{book_key}.docs.json").read_text(encoding="utf-8"))[0]["text"]


def load_graph(book_key: str) -> dict:
    return json.loads((CACHE / f"{book_key}.json").read_text(encoding="utf-8"))


def iter_anchors(record: dict):
    for field in ("sourceRefs", "quoteRef", "seedRef", "payoffRef"):
        value = record.get(field)
        if isinstance(value, dict):
            yield field, value
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield field, item


class NarrativeLayersContract(unittest.TestCase):
    """三书四层产物的通用契约。"""

    maxDiff = None

    # ---------------------------------------------------------------- A 引文可回到原文

    def test_every_quote_is_a_verbatim_substring(self):
        for key, title in BOOKS:
            text = load_text(key)
            for layer in ("causal", "clues", "states"):
                doc = load_doc(key, layer)
                records = []
                for field in REQUIRED_DOCS[layer]:
                    value = doc.get(field)
                    if isinstance(value, list):
                        records.extend(x for x in value if isinstance(x, dict))
                with self.subTest(book=title, layer=layer):
                    self.assertTrue(records, f"{title}/{layer} 产物为空")
                    for rec in records:
                        quote = rec.get("quote")
                        if not isinstance(quote, str) or not quote.strip():
                            continue
                        q = quote.strip()
                        self.assertIn(
                            q, text,
                            f"{title}/{layer} id={rec.get('id')} 的引文不是原文子串：{q[:60]!r}",
                        )

    def test_anchor_offsets_resolve_to_their_quote(self):
        for key, title in BOOKS:
            text = load_text(key)
            for layer in ("causal", "clues", "states", "relations"):
                doc = load_doc(key, layer)
                for field in REQUIRED_DOCS[layer]:
                    value = doc.get(field)
                    if not isinstance(value, list):
                        continue
                    for rec in value:
                        if not isinstance(rec, dict):
                            continue
                        for name, ref in iter_anchors(rec):
                            start, end, quote = ref.get("start"), ref.get("end"), ref.get("quote")
                            if not isinstance(start, int) or not isinstance(end, int):
                                continue
                            with self.subTest(book=title, layer=layer, ref=name):
                                self.assertTrue(
                                    0 <= start < end <= len(text),
                                    f"{title}/{layer} id={rec.get('id')} 的 {name} 偏移越界",
                                )
                                self.assertEqual(
                                    text[start:end], quote,
                                    f"{title}/{layer} id={rec.get('id')} 的 {name} "
                                    f"偏移取出的文字与 quote 不一致",
                                )

    # ---------------------------------------------------------------- B 四态标记

    def test_evidence_states_are_legal_and_basis_consistent(self):
        seen = 0
        for key, title in BOOKS:
            for layer in ("causal", "clues", "states", "relations"):
                doc = load_doc(key, layer)
                for field in REQUIRED_DOCS[layer]:
                    value = doc.get(field)
                    if not isinstance(value, list):
                        continue
                    for rec in value:
                        if not isinstance(rec, dict):
                            continue
                        state = rec.get("evidenceState")
                        if state is None:
                            continue
                        seen += 1
                        with self.subTest(book=title, layer=layer, id=rec.get("id")):
                            self.assertIn(state, EVIDENCE_STATES,
                                          f"{title}/{layer} 出现非法四态标记 {state!r}")
                            self.assertEqual(
                                rec.get("basis"), BASIS_OF_STATE[state],
                                f"{title}/{layer} id={rec.get('id')} 的 basis 与 "
                                f"evidenceState={state} 不匹配（会把归纳写成明确）",
                            )
        self.assertGreater(seen, 0, "四态标记一个都没有，契约没有真正执行")

    def test_explicit_requires_a_verified_quote(self):
        """explicit 必须有逐字可定位的引句；没有就不能自称原文明示。"""
        for key, title in BOOKS:
            text = load_text(key)
            for layer in ("causal", "clues", "states", "relations"):
                doc = load_doc(key, layer)
                for field in REQUIRED_DOCS[layer]:
                    value = doc.get(field)
                    if not isinstance(value, list):
                        continue
                    for rec in value:
                        if not isinstance(rec, dict) or rec.get("evidenceState") != "explicit":
                            continue
                        quote = rec.get("quote") or rec.get("seedQuote") or ""
                        with self.subTest(book=title, layer=layer, id=rec.get("id")):
                            self.assertTrue(
                                quote and quote.strip() in text,
                                f"{title}/{layer} id={rec.get('id')} 标 explicit 但引句无法逐字定位",
                            )

    # ---------------------------------------------------------------- C 环检测

    def test_propagation_graph_cycles_are_reported(self):
        for key, title in BOOKS:
            doc = load_doc(key, "causal")
            graph = doc.get("propagationGraph") or {}
            edges = doc.get("edges") or []
            with self.subTest(book=title):
                self.assertIn("cycles", graph)
                self.assertIn("cycleCount", graph)
                self.assertEqual(graph["cycleCount"], len(graph["cycles"]))
                adjacency: dict[str, set[str]] = {}
                for e in edges:
                    adjacency.setdefault(e["fromEventId"], set()).add(e["toEventId"])
                for cycle in graph["cycles"]:
                    nodes = cycle["nodes"]
                    reachable = all(
                        nodes[(i + 1) % len(nodes)] in adjacency.get(nodes[i], set())
                        for i in range(len(nodes))
                    )
                    self.assertTrue(reachable, f"{title} 声明的环 {nodes} 在边集里走不通")

    def test_single_char_markers_are_not_word_internal(self):
        """单字连接词必须整词判定（P13-wave2 复核缺陷 D1 的防回归）。

        缺陷：`故` / `遂` 原用裸子串匹配，会把「故人 / 故意 / 缘故 / 无故」的
        词内字符当因果连接词。实测大奉 21 条弱标记边里 16 条如此，
        其中 15 条引文内无任何强连接词兜底 —— 该边宣称的文本依据不存在。

        **两条关键约束（都是被真实缺陷逼出来的）**：
          1. 判据必须锚定 `markerOffsetInQuote`（该边所用那一次出现），
             不能对整段引文做全局匹配 —— 引文可能含同一字的多次出现。
          2. 复合词表**必须从生产源码读取**，不得在测试里复制一份：
             复制品会与实现漂移（实测：本测试曾硬编码含「遂行」，
             而生产已按 wave4 的 F2-k 移除它 ⇒ 测试把**已修好的边**判成缺陷）。
             判据用 **covering** 语义（复合词真的覆盖该偏移），
             而非「窗口内出现过」—— 后者过宽，会误报相邻词。
        """
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location(
            "bnl_for_contract", ROOT / "tools" / "plan100" / "build_narrative_layers.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        compounds = mod._WEAK_COMPOUNDS

        def covering(mk: str, quote: str, off: int):
            """返回真正覆盖 off 的复合词（要求完整包含该偏移）。"""
            for c in compounds.get(mk, ()):
                i = quote.find(c)
                while i >= 0:
                    if i <= off < i + len(c) and c != mk:
                        return c
                    i = quote.find(c, i + 1)
            return None

        checked = 0
        for key, title in BOOKS:
            doc = load_doc(key, "causal")
            for e in doc.get("edges") or []:
                mk = str(e.get("mechanism") or "")
                if len(mk) != 1:
                    continue
                quote = str(e.get("quote") or "")
                off = e.get("markerOffsetInQuote")
                with self.subTest(book=title, edge=e.get("id")):
                    self.assertIsInstance(off, int,
                                          f"{title} {e.get('id')} 缺 markerOffsetInQuote")
                    self.assertEqual(quote[off:off + len(mk)], mk,
                                     f"{title} {e.get('id')} 的 markerOffsetInQuote 不指向该连接词")
                    hit = covering(mk, quote, off)
                    self.assertIsNone(
                        hit,
                        f"{title} {e.get('id')} 的 marker「{mk}」被复合词"
                        f"「{hit}」完整覆盖（offset={off}）—— 词内字符不得作因果依据")
                    checked += 1
        self.assertGreater(checked, 0, "未检查到任何单字边 ⇒ 契约未生效")

    def test_weak_marker_drop_is_accounted(self):
        """剔除的弱连接词必须如实记账，不能静默丢弃。"""
        for key, title in BOOKS:
            doc = load_doc(key, "causal")
            report = doc.get("extractionReport") or {}
            with self.subTest(book=title):
                self.assertIn("weakMarkersDroppedAsWordInside", report,
                              f"{title} 未记账剔除的弱连接词")
                self.assertIsInstance(report["weakMarkersDroppedAsWordInside"], dict)

    def test_no_known_false_kills_in_compound_table(self):
        """复合词表不得含**已知误杀**词条（P13-wave4 F2-k / wave5 的防回归）。

        为什么需要单独一条：上面那条契约只检「**已建成的边**是否词内」——
        它检不到「**被词表挡掉的合法边**」（那种边根本没建出来，无从检查）。

        实测两个误杀都是这个形态：词条挡掉了唯一文本依据，而该处并未产出边，
        所以边级契约**静默通过**。这类缺口只能靠**登记已知误杀词条**来锁。
        """
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location(
            "bnl_for_kills", ROOT / "tools" / "plan100" / "build_narrative_layers.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)

        KNOWN_FALSE_KILLS = {
            "遂行": "西游 3 处全是「遂（于是）+行（动身）」：「无已，遂行」",
            "故知": "西游/三国 16 处中 14 处是「故（所以）+知（知道）」：「故知必败」",
        }
        for word, why in KNOWN_FALSE_KILLS.items():
            for mk, clist in mod._WEAK_COMPOUNDS.items():
                with self.subTest(word=word, marker=mk):
                    self.assertNotIn(
                        word, clist,
                        f"复合词表含已知误杀「{word}」（{why}）—— "
                        f"它挡掉的是合法因果边，不是词内字符")

        with self.subTest(word="故而"):
            self.assertNotIn("故而", mod._WEAK_COMPOUNDS.get("故", ()),
                             "「故而」在 CAUSAL_MARKERS_STRONG 里，列入复合词表会重复计")

    def test_reported_graph_counts_match_edges(self):
        for key, title in BOOKS:
            doc = load_doc(key, "causal")
            graph = doc["propagationGraph"]
            edges = doc["edges"]
            with self.subTest(book=title):
                self.assertEqual(graph["edgeCount"], len(edges),
                                 f"{title} propagationGraph.edgeCount 与实际边数不符")
                self.assertEqual(
                    sum(1 for n in graph["nodes"] if n["outDegree"] or n["inDegree"]),
                    len({e["fromEventId"] for e in edges} | {e["toEventId"] for e in edges}),
                    f"{title} 传播图节点数与边端点不一致",
                )

    # ---------------------------------------------------------------- D 同场未升格

    def test_co_presence_is_never_escalated(self):
        for key, title in BOOKS:
            doc = load_doc(key, "relations")
            co = 0
            for rel in doc.get("relations") or []:
                if rel.get("claimTier") != "co_presence_only":
                    continue
                co += 1
                with self.subTest(book=title, id=rel.get("id")):
                    self.assertEqual(rel.get("anchorStatus"), "no_event_level_anchor",
                                     "同场关系必须显式标注无事件级锚点")
                    self.assertIn("无事件级锚点", rel.get("desc") or "",
                                  "同场关系的 desc 必须写明「无事件级锚点，仅为同场推导」")
                    self.assertNotEqual(rel.get("evidenceState"), "explicit",
                                        "同场不得被标成原文明确")
                    self.assertFalse(rel.get("quoteVerified"),
                                     "同场关系不得声称引句已核验")
            self.assertIsInstance(doc.get("tierCounts"), dict)
            if co:
                self.assertEqual(doc["tierCounts"].get("co_presence_only"), co,
                                 f"{title} tierCounts 与实际同场数不符")

    def test_relations_kinds_without_assertion_vocabulary_stay_co_presence(self):
        """同场/同阵营类 kind 本身无断言词表，必须一律落在 co_presence_only。"""
        non_asserting = {"同场", "间接同场", "同阵营", "同朝", "同僚", "同族", "合作"}
        for key, title in BOOKS:
            doc = load_doc(key, "relations")
            for rel in doc.get("relations") or []:
                if rel.get("kind") in non_asserting:
                    with self.subTest(book=title, id=rel.get("id"), kind=rel.get("kind")):
                        self.assertEqual(
                            rel.get("claimTier"), "co_presence_only",
                            f"{title} kind={rel.get('kind')} 不得升格为 {rel.get('claimTier')}",
                        )

    # ---------------------------------------------------------------- E 身份冲突不归并

    def test_identity_conflicts_are_queued_not_merged(self):
        graphs = {key: load_graph(key) for key, _ in BOOKS}
        for key, title in BOOKS:
            issues = [i for i in (graphs[key].get("reviewIssues") or [])
                      if isinstance(i, dict) and i.get("kind") == "identity"]
            if not issues:
                continue
            doc = load_doc(key, "states")
            queued = doc.get("identityReview") or []
            with self.subTest(book=title):
                self.assertEqual(len(queued), len(issues),
                                 f"{title} 身份冲突未全部进入待审队列")
                for rec in queued:
                    self.assertFalse(rec.get("autoMerge"),
                                     "身份冲突不得自动归并")
                    self.assertEqual(rec.get("decision"), "pending")
            conflicted = {i.get("characterId") for i in issues}
            rel_doc = load_doc(key, "relations")
            for rel in rel_doc.get("pendingIdentityReview") or []:
                self.assertTrue(isinstance(rel, str))
            for layer in ("causal", "states"):
                layer_doc = load_doc(key, layer)
                for field in REQUIRED_DOCS[layer]:
                    value = layer_doc.get(field)
                    if not isinstance(value, list):
                        continue
                    for rec in value:
                        if not isinstance(rec, dict):
                            continue
                        if rec.get("characterId") in conflicted and rec.get("characterId"):
                            with self.subTest(book=title, layer=layer, id=rec.get("id")):
                                self.assertNotEqual(
                                    rec.get("claimStatus"), "verified",
                                    "身份冲突人物的结论不得标记为已验证",
                                )

    # ---------------------------------------------------------------- F 定位口径

    def test_locator_only_anchors_are_not_counted_as_verified(self):
        """match != exact 的锚点不得计为已核验引句。"""
        for key, title in BOOKS:
            for layer in ("causal", "clues", "states", "relations"):
                doc = load_doc(key, layer)
                for field in REQUIRED_DOCS[layer]:
                    value = doc.get(field)
                    if not isinstance(value, list):
                        continue
                    for rec in value:
                        if not isinstance(rec, dict):
                            continue
                        for name, ref in iter_anchors(rec):
                            if ref.get("match") in (None, "exact"):
                                continue
                            with self.subTest(book=title, layer=layer, ref=name):
                                self.assertFalse(
                                    ref.get("verified"),
                                    f"{title}/{layer} id={rec.get('id')} 的 {name} "
                                    f"match={ref.get('match')} 却标 verified",
                                )
                                self.assertTrue(
                                    ref.get("locatorOnly"),
                                    f"{title}/{layer} id={rec.get('id')} 的 {name} "
                                    f"非 exact 定位必须标 locatorOnly",
                                )

    def test_unverified_anchor_ledger_keeps_everything(self):
        """not_found / normalized 的锚点必须留在台账里，不能删掉了事。"""
        for key, title in BOOKS:
            doc = load_doc(key, "causal")
            ledger = doc.get("unverifiedAnchors")
            with self.subTest(book=title):
                self.assertIsInstance(ledger, list)
                self.assertIsInstance(doc.get("matchDistribution"), dict)
                for row in ledger:
                    self.assertEqual(row.get("disposition"), "unverified")
                    self.assertEqual(row.get("evidenceState"), "unverified")
                    self.assertIn(row.get("measuredMatch"),
                                  ("normalized", "not_found", "ambiguous", "fuzzy"))

    # ---------------------------------------------------------------- G 不删除既有声明

    def test_baseline_relations_with_anchors_keep_them(self):
        """基线关系自带逐字核验锚点的，产物不得把它清成无锚点（等于删证据）。"""
        for key, title in BOOKS:
            graph = load_graph(key)
            text = load_text(key)
            base_with_anchor = []
            for rel in graph.get("relations") or []:
                if not isinstance(rel, dict):
                    continue
                for ref in (rel.get("sourceRefs") or []):
                    if isinstance(ref, dict) and isinstance(ref.get("quote"), str) \
                            and ref["quote"].strip() and ref["quote"].strip() in text:
                        base_with_anchor.append(rel.get("id"))
                        break
            if not base_with_anchor:
                continue
            doc = load_doc(key, "relations")
            got = {}
            for rel in doc.get("relations") or []:
                got[rel.get("id")] = rel
            missing = [i for i in base_with_anchor
                       if not (got.get(i) or {}).get("sourceRefs")]
            with self.subTest(book=title):
                self.assertFalse(
                    missing,
                    f"{title} 基线关系的可核验锚点被清空：{missing[:5]}",
                )

    def test_baseline_records_are_carried_not_deleted(self):
        for key, title in BOOKS:
            graph = load_graph(key)
            base_cause = {c.get("id") for c in (graph.get("causeEdges") or [])
                          if isinstance(c, dict) and c.get("id")}
            doc = load_doc(key, "causal")
            carried = {c.get("id") for c in (doc.get("carriedFromBaseline") or [])
                       if isinstance(c, dict)}
            with self.subTest(book=title, layer="causeEdges"):
                self.assertTrue(
                    base_cause <= carried,
                    f"{title} 基线因果边被删除：{sorted(base_cause - carried)[:5]}",
                )

            base_clues = graph.get("clues") or []
            if base_clues:
                cdoc = load_doc(key, "clues")
                kept = {c.get("id") for c in (cdoc.get("carriedFromBaseline") or [])
                        if isinstance(c, dict)}
                base_ids = {c.get("id") for c in base_clues if isinstance(c, dict) and c.get("id")}
                self.assertTrue(base_ids <= kept,
                                f"{title} 基线伏笔被删除：{sorted(base_ids - kept)[:5]}")

            base_states = {s.get("id") for s in (graph.get("characterStates") or [])
                           if isinstance(s, dict) and s.get("id")}
            if base_states:
                sdoc = load_doc(key, "states")
                got = {s.get("id") for s in (sdoc.get("carriedFromBaseline") or [])
                       if isinstance(s, dict)}
                unverified = {s.get("id") for s in (sdoc.get("unverifiedAnchors") or [])
                              if isinstance(s, dict)}
                self.assertTrue(
                    base_states <= (got | unverified),
                    f"{title} 基线人物状态被删除：{sorted(base_states - got - unverified)[:5]}",
                )

    # ---------------------------------------------------------------- H 前端可消费

    def test_endpoint_ids_resolve_inside_the_same_graph(self):
        """产物要能被前端消费：每条因果/状态/伏笔的事件 ID 必须在同一本书的
        events 里存在（前端 sky-model.js::endpoint 只做 ID 查表，查不到就不画）。"""
        for key, title in BOOKS:
            graph = load_graph(key)
            ids = {e.get("id") for e in (graph.get("events") or [])
                   if isinstance(e, dict) and e.get("id")}
            causal = load_doc(key, "causal")
            for edge in (causal.get("edges") or []) + (causal.get("carriedFromBaseline") or []):
                with self.subTest(book=title, layer="causeEdges", id=edge.get("id")):
                    self.assertIn(edge.get("fromEventId"), ids,
                                  "因果前件事件 ID 在本图谱中不存在")
                    self.assertIn(edge.get("toEventId"), ids,
                                  "因果后件事件 ID 在本图谱中不存在")
            clues = load_doc(key, "clues")
            for clue in (clues.get("clues") or []) + (clues.get("unresolvedClues") or []):
                with self.subTest(book=title, layer="clues", id=clue.get("id")):
                    if clue.get("seedEventId"):
                        self.assertIn(clue["seedEventId"], ids, "伏笔埋设事件 ID 不存在")
                    if clue.get("payoffEventId"):
                        self.assertIn(clue["payoffEventId"], ids, "伏笔兑现事件 ID 不存在")
            states = load_doc(key, "states")
            for rec in (states.get("states") or []) + (states.get("transitions") or []) \
                    + (states.get("carriedFromBaseline") or []):
                eid = rec.get("eventId")
                if eid:
                    with self.subTest(book=title, layer="characterStates", id=rec.get("id")):
                        self.assertIn(eid, ids, "状态事件 ID 不存在")
            for rec in (states.get("knowledge") or []):
                eid = rec.get("eventId")
                if eid:
                    with self.subTest(book=title, layer="knowledge", id=rec.get("id")):
                        self.assertIn(eid, ids, "知情声明事件 ID 不存在")

    def test_basis_values_are_frontend_mappable(self):
        """basis 必须落在前端 narrativeBasis 认得的取值域内，否则会静默显示「未核验」。"""
        allowed = {"explicit", "synthesis", "inference", "unverified"}
        for key, title in BOOKS:
            for layer, fields in REQUIRED_DOCS.items():
                doc = load_doc(key, layer)
                for field in fields:
                    value = doc.get(field)
                    if not isinstance(value, list):
                        continue
                    for rec in value:
                        if not isinstance(rec, dict) or "basis" not in rec:
                            continue
                        with self.subTest(book=title, layer=layer, id=rec.get("id")):
                            self.assertIn(rec["basis"], allowed,
                                          f"basis={rec['basis']!r} 前端无法映射")

    # ---------------------------------------------------------------- 因果机制

    def test_every_cause_edge_has_mechanism_description_and_quote(self):
        """计划硬性要求：一条因果边必须有 description（机制）+ 原文锚点。"""
        for key, title in BOOKS:
            doc = load_doc(key, "causal")
            for edge in doc.get("edges") or []:
                with self.subTest(book=title, id=edge.get("id")):
                    self.assertTrue((edge.get("description") or "").strip(),
                                    "因果边缺少机制描述")
                    self.assertNotEqual(
                        (edge.get("description") or "").strip(),
                        (edge.get("quote") or "").strip(),
                        "因果边的 description 不能只是复述引文",
                    )
                    self.assertTrue((edge.get("quote") or "").strip(),
                                    "因果边缺少原文引句")
                    self.assertTrue(edge.get("sourceRefs"),
                                    "因果边缺少 sourceRefs")
                    self.assertTrue(edge.get("fromEventId"))
                    self.assertTrue(edge.get("toEventId"))
                    self.assertNotEqual(edge.get("fromEventId"), edge.get("toEventId"),
                                        "因果边不能自环（自环需单独标记，不在此产出）")

    def test_cause_edges_are_anchored_by_an_original_connective(self):
        """禁止以时间相邻替代因果：每条边必须记录原文因果连接词与绑定方式。"""
        for key, title in BOOKS:
            text = load_text(key)
            doc = load_doc(key, "causal")
            for edge in doc.get("edges") or []:
                with self.subTest(book=title, id=edge.get("id")):
                    marker = edge.get("mechanism")
                    self.assertTrue(marker, "因果边必须记录原文因果连接词")
                    self.assertIn(marker, text,
                                  f"连接词 {marker!r} 不在原文中")
                    self.assertIn(edge.get("markerStrength"), ("strong", "weak"))
                    self.assertIn(edge.get("bindPass"),
                                  ("syntactic_scope", "distance_bounded"))
                    ref = (edge.get("sourceRefs") or [{}])[0]
                    start, end = ref.get("start"), ref.get("end")
                    if isinstance(start, int) and isinstance(end, int):
                        self.assertIn(marker, text[start:end],
                                      "引文区间内找不到该边的因果连接词")

    def test_weak_markers_require_supporting_evidence(self):
        for key, title in BOOKS:
            doc = load_doc(key, "causal")
            for edge in doc.get("edges") or []:
                if edge.get("markerStrength") != "weak":
                    continue
                with self.subTest(book=title, id=edge.get("id")):
                    self.assertTrue(edge.get("weakSupport"),
                                    "弱连接词（兼表顺承）必须记录因果性佐证词")

    def test_cause_edges_are_not_backward_in_time(self):
        """后件不得早于前件；倒挂说明辖域绑定错了。"""
        for key, title in BOOKS:
            doc = load_doc(key, "causal")
            for edge in doc.get("edges") or []:
                fo, to = edge.get("fromOrder"), edge.get("toOrder")
                if not isinstance(fo, int) or not isinstance(to, int):
                    continue
                with self.subTest(book=title, id=edge.get("id")):
                    self.assertLessEqual(fo, to,
                                         f"{title} 因果边时间倒挂：{fo} -> {to}")

    # ---------------------------------------------------------------- 伏笔生命周期

    def test_clue_lifecycle_is_complete_or_explicitly_unresolved(self):
        for key, title in BOOKS:
            doc = load_doc(key, "clues")
            for clue in doc.get("clues") or []:
                with self.subTest(book=title, id=clue.get("id"), status="resolved"):
                    self.assertEqual(clue.get("status"), "resolved")
                    self.assertTrue((clue.get("seedQuote") or "").strip())
                    self.assertTrue((clue.get("payoffQuote") or "").strip(),
                                    "已回收的伏笔必须有兑现引句")
                    self.assertNotEqual(clue.get("seedQuote"), clue.get("payoffQuote"),
                                        "埋设句与兑现句不能是同一句")
                    self.assertTrue(clue.get("seedEventId"))
                    self.assertTrue(clue.get("payoffEventId"),
                                    "已回收的伏笔必须挂到兑现事件")
                    self.assertIn("seeded", clue.get("lifecycle") or [])
                    self.assertIn("paid_off", clue.get("lifecycle") or [])
            for clue in doc.get("unresolvedClues") or []:
                with self.subTest(book=title, id=clue.get("id"), status="seeded"):
                    self.assertIn(clue.get("status"), ("seeded", "uncertain"),
                                  "未兑现的伏笔不得标 resolved")
                    self.assertFalse(clue.get("payoffQuote"),
                                     "未兑现的伏笔不得编造兑现引句")
                    self.assertFalse(clue.get("payoffEventId"))

    # ---------------------------------------------------------------- 状态与信息差

    def test_state_transitions_declare_before_and_after(self):
        for key, title in BOOKS:
            doc = load_doc(key, "states")
            for rec in doc.get("transitions") or []:
                tr = rec.get("transition") or {}
                with self.subTest(book=title, id=rec.get("id")):
                    self.assertTrue((tr.get("before") or "").strip(),
                                    "状态相变必须给出变化前")
                    self.assertTrue((tr.get("after") or "").strip(),
                                    "状态相变必须给出变化后")
                    self.assertNotEqual(tr.get("before"), tr.get("after"),
                                        "相变前后不能相同")
                    self.assertTrue((tr.get("quote") or "").strip())
                    self.assertTrue(tr.get("beforeEventId"))
                    self.assertTrue(tr.get("afterEventId"))

    def test_knowledge_records_name_a_holder_or_say_unresolved(self):
        """信息差必须能说出「谁」知道了；说不出就标未解析，不能编人名。"""
        for key, title in BOOKS:
            text = load_text(key)
            doc = load_doc(key, "states")
            for rec in doc.get("knowledge") or []:
                with self.subTest(book=title, id=rec.get("id")):
                    self.assertIn(rec.get("knowledgeStatus"), ("known", "unknown"))
                    self.assertTrue((rec.get("text") or "").strip())
                    self.assertIn(rec["text"].strip(), text,
                                  "知情声明的原文必须是原文子串")
                    if rec.get("characterResolved"):
                        self.assertTrue((rec.get("character") or "").strip(),
                                        "标记为已解析却没有人物名")
                    else:
                        self.assertFalse((rec.get("character") or "").strip(),
                                         "未解析不得填一个人物名冒充")
            gaps = [r for r in (doc.get("knowledge") or []) if r.get("isGap")]
            for rec in gaps:
                self.assertEqual(rec.get("knowledgeStatus"), "unknown",
                                 "knowledgeGaps 里的记录必须是明确不知")

    def test_carried_states_keep_a_legal_evidence_state(self):
        for key, title in BOOKS:
            doc = load_doc(key, "states")
            rows = (doc.get("carriedFromBaseline") or []) + (doc.get("unverifiedAnchors") or [])
            self.assertTrue(rows, f"{title} 基线人物状态没有出现在产物里")
            for rec in rows:
                with self.subTest(book=title, id=rec.get("id")):
                    self.assertTrue(rec.get("carriedFromBaseline"),
                                    "基线记录必须标 carriedFromBaseline")
                    self.assertIn(rec.get("evidenceState"), EVIDENCE_STATES)


class SelfTestContract(unittest.TestCase):
    """构建器自带反例自检必须在离线环境通过。"""

    def test_builder_self_test_passes(self):
        import subprocess
        r = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "plan100" / "build_narrative_layers.py"),
             "--self-test"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, f"构建器自检失败：\n{r.stdout}\n{r.stderr}")
        self.assertIn("self-test OK", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
