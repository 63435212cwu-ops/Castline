#!/usr/bin/env python3
"""P03 契约测试：任务五元组状态机 + 故事线真实挂接。

断言的五件事（对应计划 P03 验收断言与审核扣分点）：

  T1 五元组字段完整      goal/obstacle/action/outcome/cost 五个维度都存在，
                         且每个维度都有 text/basis/sourceRefs。
  T2 四态标记合法        每个 basis ∈ {explicit,inferred,derived,unverified}；
                         state ∈ {open,blocked,advanced,resolved,failed}。
  T3 终态有原文证据      state 为 resolved/failed 时，必须给出终态判据的原文锚点，
                         或显式承认没有（successClaim=unverified）。
  T4 结束≠成功            successClaim != "explicit" ⇒ endNotSuccess 必须为 true。
                         status=completed / 事件序列排完 / 有 outcomeEventId
                         都不允许单独把任务判成成功。
  T5 时间相邻未被当因果   relation=="causal-evidence" 的转移，必须能在 causeEdges 里
                         找到真实边；找不到的一律 sequence-only，且计数对得上。

外加：引文必须是原文子串（text[start:end] == quote），用真实缓存复核。

负向控制：每个断言都配一个"故意改坏"的样本，证明检查器真的会拒绝，
而不是永远返回通过。零第三方依赖、不写 data/、不启动浏览器。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NARRATIVE = ROOT / "tests" / "fixtures" / "contracts" / "narrative"
CACHE = ROOT / "data" / "cache"

BOOKS = [
    ("9b676d7031b1bcd3b8377a18", "大奉打更人"),
    ("df959d743e53206f56db2f92", "西游记"),
    ("152e2a6eed94f1075e7e7070", "三国演义"),
]

ASPECTS = ("goal", "obstacle", "action", "outcome", "cost")
BASIS_STATES = ("explicit", "inferred", "derived", "unverified")
STATES = ("open", "blocked", "advanced", "resolved", "failed")
TERMINAL = ("resolved", "failed")



class ContractError(AssertionError):
    pass


def validate_task(task: dict, cause_pairs: set, text: str, where: str = "") -> list[str]:
    """返回违规列表。空列表 = 通过。"""
    bad: list[str] = []
    p = f"{where} " if where else ""

    for a in ASPECTS:
        if a not in task:
            bad.append(f"{p}T1 缺维度 {a}")
            continue
        asp = task[a]
        for k in ("text", "basis", "sourceRefs"):
            if k not in asp:
                bad.append(f"{p}T1 维度 {a} 缺字段 {k}")
        if not isinstance(asp.get("sourceRefs"), list):
            bad.append(f"{p}T1 维度 {a} 的 sourceRefs 不是列表")

    for a in ASPECTS:
        asp = task.get(a) or {}
        if asp.get("basis") not in BASIS_STATES:
            bad.append(f"{p}T2 维度 {a} 的 basis={asp.get('basis')!r} 不在四态词表")
    if task.get("state") not in STATES:
        bad.append(f"{p}T2 state={task.get('state')!r} 不在状态词表")

    for a in ASPECTS:
        asp = task.get(a) or {}
        if isinstance(asp.get("text"), str) and not asp["text"].strip():
            if asp.get("basis") != "unverified":
                bad.append(f"{p}T1b 维度 {a} 文本为空但 basis={asp.get('basis')!r}（空缺被填了默认值）")

    for a in ASPECTS + ("__top__",):
        refs = task.get("sourceRefs") if a == "__top__" else (task.get(a) or {}).get("sourceRefs")
        for r in refs or []:
            if not isinstance(r, dict) or r.get("match") != "exact":
                continue
            s, e, q = r.get("start"), r.get("end"), r.get("quote")
            if not (isinstance(s, int) and isinstance(e, int) and 0 <= s <= e <= len(text)):
                bad.append(f"{p}引文 offset 越界：{q!r}")
            elif text[s:e] != q:
                bad.append(f"{p}标为 exact 的引文不是原文子串：{q!r}")

    te = task.get("terminalEvidence") or {}
    if task.get("state") in TERMINAL:
        if not te:
            bad.append(f"{p}T3 终态缺 terminalEvidence")
        elif not te.get("successClaim"):
            bad.append(f"{p}T3 终态缺 successClaim")
        elif te["successClaim"] == "explicit" and not te.get("outcomeAnchoredInText"):
            bad.append(f"{p}T3 successClaim=explicit 但结果维度无原文锚点")

    claim = te.get("successClaim")
    if claim and claim != "explicit" and te.get("endNotSuccess") is not True:
        bad.append(f"{p}T4 successClaim={claim!r} 时 endNotSuccess 必须为 true（结束被当成成功了）")
    if claim == "explicit" and te.get("endNotSuccess") is not False:
        bad.append(f"{p}T4 successClaim=explicit 时 endNotSuccess 应为 false")
    if task.get("endNotSuccess") is not te.get("endNotSuccess"):
        bad.append(f"{p}T4 顶层的 endNotSuccess 与 terminalEvidence 不一致")
    if te.get("claimVerified") is True:
        bad.append(f"{p}T4 claimVerified 不得为 true（逐字命中不证明语义）")
    if task.get("state") == "failed" and claim == "explicit":
        hits_success = te.get("successLexemeHits") or []
        hits_failure = te.get("failureLexemeHits") or []
        if not hits_success:
            bad.append(f"{p}T4b state=failed 但 successClaim=explicit，且结果引句无成功措辞 "
                       f"（失败态被读成成功；successLexemeHits={hits_success}）")
        elif hits_failure:
            bad.append(f"{p}T4b state=failed 但 successClaim=explicit，且结果引句含失败措辞 "
                       f"{hits_failure}（成功与失败措辞并存，不得判 explicit）")

    seq_only = 0
    trans = task.get("transitions") or []
    for i, t in enumerate(trans):
        rel = t.get("relation")
        if rel not in ("causal-evidence", "sequence-only"):
            bad.append(f"{p}T5 转移 relation={rel!r} 不在词表")
        if rel == "sequence-only":
            seq_only += 1
        if rel == "causal-evidence":
            eid = t.get("eventId")
            prev = trans[i - 1].get("eventId") if i else None
            nxt = trans[i + 1].get("eventId") if i + 1 < len(trans) else None
            pairs = {x for x in ((prev, eid), (eid, nxt)) if x[0] and x[1]}
            if not (pairs & cause_pairs):
                bad.append(f"{p}T5 事件 {eid} 标为因果，但 causeEdges 里没有对应真实边")
    re_ = task.get("reverseEvidence") or {}
    if re_ and re_.get("sequenceOnlyTransitionCount") != seq_only:
        bad.append(f"{p}T5 sequenceOnlyTransitionCount="
                   f"{re_.get('sequenceOnlyTransitionCount')} 与实际 sequence-only 转移数 {seq_only} 不符")
    return bad


def validate_storyline(s: dict, story_ids: set, text: str, where: str = "") -> list[str]:
    bad: list[str] = []
    p = f"{where} " if where else ""
    for k in ("id", "sourceRefs", "eventIds", "handoff_from", "handoff_reason"):
        if k not in s:
            bad.append(f"{p}故事线缺字段 {k}")
    if not isinstance(s.get("sourceRefs"), list):
        bad.append(f"{p}sourceRefs 不是列表")
    for r in s.get("sourceRefs") or []:
        if isinstance(r, dict) and r.get("match") == "exact":
            st, en, q = r.get("start"), r.get("end"), r.get("quote")
            if not (isinstance(st, int) and isinstance(en, int) and 0 <= st <= en <= len(text)):
                bad.append(f"{p}故事线引文 offset 越界：{q!r}")
            elif text[st:en] != q:
                bad.append(f"{p}故事线标为 exact 的引文不是原文子串：{q!r}")
    hf = s.get("handoff_from") or ""
    if hf and hf not in story_ids:
        bad.append(f"{p}handoff_from={hf!r} 不指向本书任何故事线")
    if hf and str(hf) == str(s.get("id")):
        bad.append(f"{p}handoff_from 自指")
    kind = s.get("handoffReasonKind")
    if kind == "temporal-adjacency-only" and s.get("handoffSelfConsistent") is not True:
        bad.append(f"{p}标注为仅时间相邻的换手，自洽性未核验")
    return bad



def _load_book(key: str):
    tp = NARRATIVE / f"{key}.tasks.json"
    sp = NARRATIVE / f"{key}.storylines.json"
    if not tp.exists() or not sp.exists():
        return None
    tasks_doc = json.loads(tp.read_text(encoding="utf-8"))
    lines_doc = json.loads(sp.read_text(encoding="utf-8"))
    docs = json.loads((CACHE / f"{key}.docs.json").read_text(encoding="utf-8"))
    text = docs[0]["text"]
    graph = json.loads((CACHE / f"{key}.json").read_text(encoding="utf-8"))
    cause_pairs = {(c.get("fromEventId"), c.get("toEventId"))
                   for c in (graph.get("causeEdges") or []) if isinstance(c, dict)}
    return tasks_doc, lines_doc, text, cause_pairs


class ArtifactsPresent(unittest.TestCase):
    def test_all_three_books_have_p03_artifacts(self):
        for key, title in BOOKS:
            with self.subTest(book=title):
                self.assertIsNotNone(_load_book(key),
                                     f"缺 tests/fixtures/contracts/narrative/{key}.tasks.json 或 .storylines.json")
        self.assertTrue((NARRATIVE / "storyline-diagnosis.json").exists(),
                        "缺 storyline-diagnosis.json")


class TaskStateMachineContract(unittest.TestCase):
    def test_every_task_passes_the_contract(self):
        for key, title in BOOKS:
            loaded = _load_book(key)
            if loaded is None:
                self.skipTest(f"{title} 产物缺失")
            tasks_doc, _, text, cause_pairs = loaded
            self.assertEqual(tasks_doc.get("aspectOrder"), list(ASPECTS))
            for t in tasks_doc["tasks"]:
                with self.subTest(book=title, task=t.get("taskId")):
                    self.assertEqual(validate_task(t, cause_pairs, text, title), [])

    def test_no_temporal_adjacency_is_reported_as_causality(self):
        """即使全部通过，也要确认 sequence-only 确实被大量标出（不是全被写成因果）。"""
        for key, title in BOOKS:
            loaded = _load_book(key)
            if loaded is None:
                self.skipTest(f"{title} 产物缺失")
            tasks_doc, _, _, cause_pairs = loaded
            seq = sum(t["reverseEvidence"]["sequenceOnlyTransitionCount"] for t in tasks_doc["tasks"])
            caus = sum(t["coverage"]["eventsLinkedByRealCause"] for t in tasks_doc["tasks"])
            with self.subTest(book=title):
                self.assertGreater(seq, 0, "没有任何 sequence-only 转移，说明相邻事件被默认当成了因果")
                self.assertLessEqual(caus, len(cause_pairs) * 2,
                                     "因果转移数远超真实 causeEdges 边数")
                self.assertEqual(
                    tasks_doc["summary"]["totalSequenceOnlyTransitions"], seq,
                    "汇总里的 sequence-only 计数与逐条统计不符")

    def test_unverified_is_never_silently_upgraded(self):
        """西游/三国没有维度级 fieldEvidence：维度必须停在 unverified/derived，不得出现 explicit。"""
        for key, title in BOOKS:
            loaded = _load_book(key)
            if loaded is None:
                self.skipTest(f"{title} 产物缺失")
            tasks_doc, _, _, _ = loaded
            for t in tasks_doc["tasks"]:
                for a in ASPECTS:
                    with self.subTest(book=title, task=t["taskId"], aspect=a):
                        asp = t[a]
                        if asp["basis"] == "explicit":
                            self.assertTrue(asp["textVerbatimInSource"],
                                            "标为 explicit 的维度文本必须本身是原文子串")
                        if asp["textIsAnalystSummary"]:
                            self.assertNotEqual(asp["basis"], "explicit",
                                                "分析者归纳不得标成 explicit")


class DiagnosisContract(unittest.TestCase):
    def test_dafeng_is_reported_as_mechanical_equal_split(self):
        d = json.loads((NARRATIVE / "storyline-diagnosis.json").read_text(encoding="utf-8"))
        by_key = {b["bookKey"]: b for b in d["books"]}
        df = by_key["9b676d7031b1bcd3b8377a18"]
        self.assertEqual(df["verdict"], "mechanical_equal_split")
        s = df["summary"]
        self.assertEqual(s["attachStepDistinct"], 1, "大奉 attach_order 步长应完全等距")
        self.assertEqual(set(s["attachStepSizes"]), {374})
        self.assertTrue(s["windowsTileAllEvents"], "等分切片应无缝铺满全书")
        self.assertEqual(s["windowOverlapEvents"], 0)
        self.assertEqual(s["storylinesWithExactAnchor"], 0)
        self.assertTrue(df["verdictReasons"])

    def test_xiyou_and_sanguo_are_not_reported_as_mechanical(self):
        d = json.loads((NARRATIVE / "storyline-diagnosis.json").read_text(encoding="utf-8"))
        by_key = {b["bookKey"]: b for b in d["books"]}
        for k in ("df959d743e53206f56db2f92", "152e2a6eed94f1075e7e7070"):
            with self.subTest(book=k):
                self.assertEqual(by_key[k]["verdict"], "evidence_bounded")
                self.assertGreater(by_key[k]["summary"]["attachStepDistinct"], 1)


class StorylineAttachmentContract(unittest.TestCase):
    def test_storylines_pass_the_contract(self):
        for key, title in BOOKS:
            loaded = _load_book(key)
            if loaded is None:
                self.skipTest(f"{title} 产物缺失")
            _, lines_doc, text, _ = loaded
            ids = {str(s.get("id")) for s in lines_doc["storylines"]}
            for s in lines_doc["storylines"]:
                with self.subTest(book=title, storyline=s.get("id")):
                    self.assertEqual(validate_storyline(s, ids, text, title), [])

    def test_dafeng_storylines_are_bounded_by_source_text_not_by_event_count(self):
        _, lines_doc, text, _ = _load_book("9b676d7031b1bcd3b8377a18")
        self.assertEqual(lines_doc["attachmentMode"], "volume-boundary-from-source-text")
        for s in lines_doc["storylines"]:
            with self.subTest(storyline=s["id"]):
                be = s.get("boundaryEvidence")
                self.assertIsNotNone(be, "每条线都要有边界原文证据")
                self.assertEqual(be["match"], "exact")
                self.assertEqual(text[be["start"]:be["end"]], be["quote"])
                self.assertTrue(s["sourceRefs"], "每条线至少一个原文锚点")
        names = [s["volume"]["name"] for s in lines_doc["storylines"]]
        self.assertEqual(names, ["京察风云", "国士无双", "少年羁旅", "逐鹿中原", None])

    def test_dafeng_anchor_rate_is_no_longer_zero(self):
        _, lines_doc, _, _ = _load_book("9b676d7031b1bcd3b8377a18")
        self.assertEqual(lines_doc["summary"]["anchorRate"], 1.0)



class NegativeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loaded = _load_book("9b676d7031b1bcd3b8377a18")
        if loaded is None:
            raise AssertionError("大奉任务夹具缺失，负向控制无法运行")
        cls.tasks_doc, cls.lines_doc, cls.text, cls.cause_pairs = loaded
        cls.task = next(t for t in cls.tasks_doc["tasks"]
                        if (t.get("terminalEvidence") or {}).get("successClaim") != "explicit")

    def test_clean_sample_passes(self):
        self.assertEqual(validate_task(copy.deepcopy(self.task), self.cause_pairs, self.text), [])

    def test_empty_aspect_filled_with_default_is_rejected(self):
        bad = copy.deepcopy(self.task)
        bad["cost"] = {"text": "", "basis": "explicit", "sourceRefs": []}
        self.assertTrue(validate_task(bad, self.cause_pairs, self.text))

    def test_missing_aspect_is_rejected(self):
        bad = copy.deepcopy(self.task)
        del bad["obstacle"]
        self.assertTrue(validate_task(bad, self.cause_pairs, self.text))

    def test_illegal_basis_is_rejected(self):
        bad = copy.deepcopy(self.task)
        bad["goal"]["basis"] = "confirmed"
        self.assertTrue(validate_task(bad, self.cause_pairs, self.text))

    def test_end_treated_as_success_is_rejected(self):
        bad = copy.deepcopy(self.task)
        bad["terminalEvidence"]["endNotSuccess"] = False
        bad["endNotSuccess"] = False
        self.assertTrue(validate_task(bad, self.cause_pairs, self.text),
                        "把结束当成功必须被拒绝")

    def test_playback_completion_alone_cannot_make_success_explicit(self):
        """播放器放完 = status completed + 有 outcomeEventId，但没有原文成功措辞。"""
        bad = copy.deepcopy(self.task)
        bad["state"] = "resolved"
        bad["terminalEvidence"]["successClaim"] = "explicit"
        bad["terminalEvidence"]["outcomeAnchoredInText"] = False
        bad["terminalEvidence"]["endNotSuccess"] = False
        bad["endNotSuccess"] = False
        self.assertTrue(validate_task(bad, self.cause_pairs, self.text))

    def test_failed_state_cannot_be_claimed_explicit_without_success_wording(self):
        """P13 独立复核 D1/D2：源记录判失败的任务有逐字锚点，但锚点里没有成功措辞。

        这是真实发生过的缺陷（大奉 task_review_44b39f1ed05a6861：「争取司天监庇护作为保命后路」，
        原文「得，这条路没得走」），旧契约字面自洽地放行了它 ——
        state=failed + successClaim=explicit + endNotSuccess=false 三者互推成立，
        但语义上是把「未达成」读成了成功。
        """
        bad = copy.deepcopy(self.task)
        bad["state"] = "failed"
        bad["terminalEvidence"].update({
            "state": "failed", "successClaim": "explicit",
            "outcomeAnchoredInText": True,
            "successLexemeHits": [], "failureLexemeHits": [],
            "endNotSuccess": False,
        })
        bad["endNotSuccess"] = False
        self.assertTrue(validate_task(bad, self.cause_pairs, self.text),
                        "失败态无成功措辞却被判 explicit 必须被拒绝")

    def test_failed_state_cannot_be_explicit_when_failure_wording_present(self):
        """失败态即使命中成功措辞，只要同时含失败措辞也不得判 explicit。"""
        bad = copy.deepcopy(self.task)
        bad["state"] = "failed"
        bad["terminalEvidence"].update({
            "state": "failed", "successClaim": "explicit",
            "outcomeAnchoredInText": True,
            "successLexemeHits": ["追回"], "failureLexemeHits": ["行不通"],
            "endNotSuccess": False,
        })
        bad["endNotSuccess"] = False
        self.assertTrue(validate_task(bad, self.cause_pairs, self.text),
                        "成功与失败措辞并存时不得判 explicit")

    def test_claimVerified_true_is_rejected(self):
        bad = copy.deepcopy(self.task)
        bad["terminalEvidence"]["claimVerified"] = True
        self.assertTrue(validate_task(bad, self.cause_pairs, self.text))

    def test_forged_quote_is_rejected(self):
        bad = copy.deepcopy(self.task)
        bad["goal"]["sourceRefs"] = [{
            "sourceId": "src_x", "sourcePath": "x.txt", "offsetUnit": "codepoint",
            "textHash": "x", "start": 0, "end": 4, "quote": "原文里没有这四个字",
            "match": "exact"}]
        self.assertTrue(validate_task(bad, self.cause_pairs, self.text))

    def test_temporal_neighbour_labelled_causal_without_edge_is_rejected(self):
        bad = copy.deepcopy(self.task)
        if not bad.get("transitions"):
            self.skipTest("样本没有转移")
        bad["transitions"][0]["relation"] = "causal-evidence"
        self.assertTrue(validate_task(bad, self.cause_pairs, self.text),
                        "没有真实因果边的相邻事件被标成因果，必须拒绝")

    def test_storyline_self_referential_handoff_is_rejected(self):
        s = copy.deepcopy(self.lines_doc["storylines"][-1])
        s["handoff_from"] = s["id"]
        ids = {str(x["id"]) for x in self.lines_doc["storylines"]}
        self.assertTrue(validate_storyline(s, ids, self.text))

    def test_storyline_dangling_handoff_is_rejected(self):
        s = copy.deepcopy(self.lines_doc["storylines"][-1])
        s["handoff_from"] = "no-such-storyline"
        ids = {str(x["id"]) for x in self.lines_doc["storylines"]}
        self.assertTrue(validate_storyline(s, ids, self.text))


def main() -> int:
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"\nP03 task state machine contract: "
          f"{result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} passed")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
