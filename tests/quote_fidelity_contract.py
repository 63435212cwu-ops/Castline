#!/usr/bin/env python3
"""P11-W03/W07 · 引用保真契约（内容回归）。

审核点名的真实缺陷是「定位成功被当成语义正确」：
  - 旧关系记录（relations）没有任何事件级原文锚点；
  - 事件声明的章节与引文实际落点所在章节不一致（chapter drift）。

本文件对**三书真实缓存**（图谱 + 原文）逐条回放 sourceRefs，验证
`text[start:end] == quote` 与 `offsetUnit=codepoint` 的一致性，并把
「定位成功」（match=normalized/ambiguous/fuzzy）与「已核验引句」（match=exact）
严格分开计数——`match != exact` 一律不得计入已核验。

分两类断言，互不掩盖：
  HARD    不变量。今天成立，退化即为真实缺陷，直接 fail。
  RATCHET 已知缺陷的**冻结计数**（只减不增）。今天不 fail，但任何增长都会
          立刻 fail。缺陷本身写入 knownGaps 与 decision.md，绝不以放宽断言
          的方式转绿；修复后重跑 --update-baseline 收紧。

章节锚点口径（已实测校准，不要随手放宽）：
  标题必须「第N<单位>」后紧跟空白/全角空格。去掉这个约束，大奉里
  「我继续爆肝码第二章。」这类作者感言会被算成标题（907 → 935），
  章数立刻虚高。反过来说，大奉的章节编号**按卷重新计数**（同一数字重复
  出现 232 次），所以不能用单调递增过滤，只能取「引文落点之前最近的一个
  标题」作为实际章节。

用法：
  python3 tests/quote_fidelity_contract.py              # 门禁（默认，供 accept.sh）
  python3 tests/quote_fidelity_contract.py --report     # 只打印缺陷明细，不门禁
  python3 tests/quote_fidelity_contract.py --update-baseline
"""
from __future__ import annotations

import argparse
import bisect
import collections
import hashlib
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASELINE = os.path.join(HERE, "quote_fidelity_baseline.json")

BOOKS = {
    "9b676d7031b1bcd3b8377a18": ("大奉打更人", "章"),
    "df959d743e53206f56db2f92": ("西游记", "回"),
    "152e2a6eed94f1075e7e7070": ("三国演义", "回"),
}

REF_LAYERS = ("characters", "events", "relations", "causeEdges", "characterStates",
              "storylines", "tasks", "camps", "clues", "episodes", "narrativeUnits")

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}


def cjk_number(text: str) -> int:
    """中文数字 → int（支持 百/十/零）；无法解析返回 -1。仅用于章节序号比对。"""
    text = (text or "").strip()
    if not text:
        return -1
    if text.isdigit():
        return int(text)
    if "百" in text:
        head, _, tail = text.partition("百")
        hundreds = CN_DIGITS.get(head, 1) if head else 1
        if tail.startswith("零"):
            tail = tail[1:]
        if not tail:
            return hundreds * 100
        if "十" in tail:
            tens, _, ones = tail.partition("十")
            return (hundreds * 100 + (CN_DIGITS.get(tens, 1) if tens else 1) * 10
                    + (CN_DIGITS.get(ones, 0) if ones else 0))
        return hundreds * 100 + CN_DIGITS.get(tail, 0)
    if "十" in text:
        tens, _, ones = text.partition("十")
        return (CN_DIGITS.get(tens, 1) if tens else 1) * 10 + (CN_DIGITS.get(ones, 0) if ones else 0)
    return CN_DIGITS.get(text, -1)


def strip_zero(text: str) -> str:
    return (text or "").replace("零", "").replace("〇", "")


def chapter_number(label: str, unit: str) -> int:
    """从 '第一百零一回（本块）' 之类的标签里取出章节序号。"""
    match = re.match(r"第([0-9零〇一二三四五六七八九十百千两]+)" + unit, (label or "").strip())
    if not match:
        return -1
    return cjk_number(strip_zero(match.group(1)))


HEADING_RE = r"第([0-9零〇一二三四五六七八九十百千两]+)%s(?=[\s\u3000])"


def extract_headings(text: str, unit: str):
    """按正文实际抽取章节标题，返回 [{'start','label','number'}]。

    **不做单调过滤**：大奉按卷重排章节号，单调过滤会把 88% 的章节丢掉。
    """
    return [{"start": m.start(), "label": m.group(),
             "number": cjk_number(strip_zero(m.group(1)))}
            for m in re.finditer(HEADING_RE % unit, text)]


class Book:
    """一本书的图谱 + 原文，惰性加载并在进程内复用。"""

    _cache = {}

    def __init__(self, key):
        self.key = key
        self.title, self.unit = BOOKS[key]
        self.graph = json.load(open(os.path.join(ROOT, "data", "cache", key + ".json"), encoding="utf-8"))
        self.text = json.load(open(os.path.join(ROOT, "data", "cache", key + ".docs.json"), encoding="utf-8"))[0]["text"]
        self.sources = self.graph.get("meta", {}).get("sources") or []
        self.headings = extract_headings(self.text, self.unit)
        self._starts = [h["start"] for h in self.headings]

    @classmethod
    def get(cls, key):
        if key not in cls._cache:
            cls._cache[key] = cls(key)
        return cls._cache[key]

    def chapter_at(self, offset):
        """引文落点之前最近的一个章节标题。"""
        index = bisect.bisect_right(self._starts, offset) - 1
        return self.headings[index] if index >= 0 else None

    def refs(self):
        """展开全部层的引用，产出 (layer, item, ref)。

        `sourceRefs`、`quoteRef`、`sourceRef`、`evidenceRef(s)` 以及 meta 里嵌套
        （如 coverage.*.scope.boundaryEvidenceRefs）的引用全部计入：只统计
        sourceRefs 会漏掉 quoteRef 这一路，已核验数会被低报。
        """
        for layer in REF_LAYERS:
            items = self.graph.get(layer)
            if not isinstance(items, list):
                continue
            for item in items:
                for ref in self._refs_of(item):
                    yield layer, item, ref
        for path, node in _walk_meta(self.graph.get("meta")):
            for ref in self._refs_of(node):
                yield "meta" + path, node, ref

    @staticmethod
    def _refs_of(item):
        if not isinstance(item, dict):
            return []
        out = []
        if isinstance(item.get("sourceRefs"), list):
            out.extend(r for r in item["sourceRefs"] if isinstance(r, dict))
        for field in ("quoteRef", "sourceRef", "evidenceRef"):
            if isinstance(item.get(field), dict):
                out.append(item[field])
        if isinstance(item.get("evidenceRefs"), list):
            out.extend(r for r in item["evidenceRefs"] if isinstance(r, dict))
        return out


def _walk_meta(node, path=""):
    """遍历 meta，产出 (路径, 字典节点)，用于捞出嵌套的 boundaryEvidenceRefs。"""
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from _walk_meta(value, path + "." + str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk_meta(value, path + "[%d]" % index)


def scan_book(key):
    """回放一本书的全部引用，返回可定位的失败证据字典。"""
    book = Book.get(key)
    source = book.sources[0] if book.sources else {}
    report = {
        "bookKey": key, "title": book.title, "chars": len(book.text),
        "declaredChars": source.get("chars"), "declaredHash": source.get("textHash"),
        "actualHash": hashlib.sha256(book.text.encode("utf-8")).hexdigest(),
        "declaredChapters": source.get("chapters"),
        "refs": 0, "verified": 0, "exactSpanVerified": 0, "locatedNotVerified": 0,
        "spanViolations": [], "verifiedNotExact": [], "badUnit": [], "badHash": [],
        "nonExact": collections.Counter(),
        "chapterDrift": [], "chapterLabelled": 0, "chapterAccurate": 0,
        "chapterLabelMissing": [],
        "headings": len(book.headings),
        "relations": 0, "relationsWithoutAnchor": 0, "relationsFalselyVerified": [],
    }

    for layer, item, ref in book.refs():
        report["refs"] += 1
        match = ref.get("match")
        verified = ref.get("verified") is True
        start, end, quote = ref.get("start"), ref.get("end"), ref.get("quote")
        if not verified:
            if match and match != "none":
                report["nonExact"][match] += 1
                report["locatedNotVerified"] += 1
            continue
        report["verified"] += 1
        if match != "exact":
            report["verifiedNotExact"].append(
                {"layer": layer, "id": item.get("id"), "match": match, "start": start, "end": end,
                 "quote": str(quote)[:80],
                 "minimalRepro": "verify(ref) where ref.match=%r and ref.verified=True" % (match,)})
        if ref.get("offsetUnit") != "codepoint":
            report["badUnit"].append({"layer": layer, "id": item.get("id"), "offsetUnit": ref.get("offsetUnit")})
        if report["declaredHash"] and ref.get("textHash") != report["declaredHash"]:
            report["badHash"].append({"layer": layer, "id": item.get("id"), "textHash": ref.get("textHash")})
        if match != "exact":
            continue
        in_range = type(start) is int and type(end) is int and 0 <= start < end <= len(book.text)
        actual = book.text[start:end] if in_range else None
        if in_range and actual == quote:
            report["exactSpanVerified"] += 1
        else:
            report["spanViolations"].append({
                "layer": layer, "id": item.get("id"), "start": start, "end": end,
                "expectedQuote": str(quote)[:120],
                "actualText": (str(actual)[:120] if actual is not None else "<越界>"),
                "minimalRepro": "book.text[%r:%r]" % (start, end),
            })

    for event in book.graph.get("events") or []:
        if not isinstance(event, dict):
            continue
        claimed = chapter_number(event.get("chapter"), book.unit)
        if claimed < 0:
            continue
        exact = [r for r in (event.get("sourceRefs") or [])
                 if isinstance(r, dict) and r.get("verified") is True
                 and r.get("match") == "exact" and type(r.get("start")) is int]
        if not exact:
            continue
        heading = book.chapter_at(exact[0]["start"])
        if heading is None:
            continue
        report["chapterLabelled"] += 1
        if heading["number"] == claimed:
            report["chapterAccurate"] += 1
            continue
        report["chapterDrift"].append({
            "eventId": event.get("id"), "claimedChapter": event.get("chapter"),
            "claimedNumber": claimed, "actualHeading": heading["label"],
            "actualNumber": heading["number"], "start": exact[0]["start"],
            "quote": str(exact[0].get("quote"))[:60],
            "minimalRepro": "book.chapter_at(%d) -> %r" % (exact[0]["start"], heading["label"]),
        })

    present = {h["number"] for h in book.headings}
    claimed_labels = {}
    for event in book.graph.get("events") or []:
        if isinstance(event, dict):
            number = chapter_number(event.get("chapter"), book.unit)
            if number >= 0:
                claimed_labels.setdefault(number, (event.get("chapter") or "").strip())
    for number, raw_label in sorted(claimed_labels.items()):
        if number not in present:
            report["chapterLabelMissing"].append({"claimed": raw_label, "number": number})

    for rel in book.graph.get("relations") or []:
        if not isinstance(rel, dict):
            continue
        report["relations"] += 1
        if not [r for r in (rel.get("sourceRefs") or []) if isinstance(r, dict)]:
            report["relationsWithoutAnchor"] += 1
            if rel.get("quoteVerified") is True:
                report["relationsFalselyVerified"].append(
                    {"id": rel.get("id"), "a": rel.get("a"), "b": rel.get("b")})
    report["nonExact"] = dict(report["nonExact"])
    return report


REPORTS = {key: scan_book(key) for key in BOOKS}


def ratchet_summary():
    return {key: {
        "chapterDrift": len(REPORTS[key]["chapterDrift"]),
        "relationsWithoutAnchor": REPORTS[key]["relationsWithoutAnchor"],
        "locatedNotVerified": REPORTS[key]["locatedNotVerified"],
        "spanViolations": len(REPORTS[key]["spanViolations"]),
        "verifiedNotExact": len(REPORTS[key]["verifiedNotExact"]),
    } for key in BOOKS}


def load_baseline():
    with open(BASELINE, encoding="utf-8") as handle:
        return json.load(handle)


def _evidence(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)[:4000]


class QuoteFidelityContract(unittest.TestCase):
    maxDiff = None

    # ---------- HARD：不变量 ----------

    def test_source_text_hash_and_chars_match_declared_metadata(self):
        """原文指纹必须与 meta.sources 声明一致，否则一切 offset 都失去基准。"""
        for key, report in REPORTS.items():
            with self.subTest(book=report["title"]):
                self.assertEqual(
                    report["actualHash"], report["declaredHash"],
                    "原文 textHash 与声明不符——offsetUnit=codepoint 的基准已失效\n" + _evidence(
                        {"book": report["title"], "declared": report["declaredHash"],
                         "actual": report["actualHash"],
                         "minimalRepro": "sha256(open('data/cache/%s.docs.json').read())" % key}))
                self.assertEqual(
                    report["chars"], report["declaredChars"],
                    "原文实际字符数与 meta.sources[0].chars 不符（offsetUnit 为 codepoint）\n" + _evidence(
                        {"book": report["title"], "declared": report["declaredChars"],
                         "actual": report["chars"]}))

    def test_exact_refs_are_verbatim_spans_of_the_original_text(self):
        """verified=true 且 match=exact ⇒ text[start:end] 必须逐字等于 quote。"""
        for key, report in REPORTS.items():
            with self.subTest(book=report["title"]):
                self.assertEqual(
                    report["spanViolations"], [],
                    "存在「已核验 exact」但原文切片不等于 quote 的引用——即伪造/失效锚点\n" + _evidence(
                        {"book": report["title"], "count": len(report["spanViolations"]),
                         "samples": report["spanViolations"][:5]}))
                self.assertGreater(
                    report["exactSpanVerified"], 0,
                    "没有回放到任何一条可逐字验证的 exact 引用——测试本身已失去意义\n" + _evidence(
                        {"book": report["title"], "refs": report["refs"], "verified": report["verified"]}))

    def test_verified_refs_always_declare_exact_match_and_codepoint_unit(self):
        """verified=true 的引用必须自带 match=exact 与 offsetUnit=codepoint。"""
        for key, report in REPORTS.items():
            with self.subTest(book=report["title"]):
                self.assertEqual(
                    report["verifiedNotExact"], [],
                    "存在 verified=true 但 match!=exact 的引用——「定位成功」被当成了「已核验」\n" + _evidence(
                        {"book": report["title"], "count": len(report["verifiedNotExact"]),
                         "samples": report["verifiedNotExact"][:5]}))
                self.assertEqual(
                    report["badUnit"], [],
                    "已核验引用的 offsetUnit 不是 codepoint\n" + _evidence(report["badUnit"][:5]))

    def test_verified_refs_carry_the_current_source_hash(self):
        """引用记录的 textHash 必须是当前原文的哈希，防止旧版本锚点继续冒充已核验。"""
        for key, report in REPORTS.items():
            with self.subTest(book=report["title"]):
                self.assertEqual(
                    report["badHash"], [],
                    "已核验引用的 textHash 与当前原文不符——旧版本锚点未被清除\n" + _evidence(
                        {"book": report["title"], "expected": report["declaredHash"],
                         "samples": report["badHash"][:5]}))

    def test_chapter_labels_claimed_by_events_exist_in_the_real_text(self):
        """事件声明的章节必须在正文里真实存在，不能是插值/均分补出来的。"""
        for key, report in REPORTS.items():
            with self.subTest(book=report["title"]):
                self.assertEqual(
                    report["chapterLabelMissing"], [],
                    "事件引用了正文中不存在的章节标签（疑似插值补齐）\n" + _evidence(
                        {"book": report["title"], "missing": report["chapterLabelMissing"][:10],
                         "extractedHeadings": report["headings"]}))

    def test_relations_without_event_anchor_are_not_marked_quote_verified(self):
        """旧关系记录没有事件级原文锚点，就不得被标成引句已核验。"""
        for key, report in REPORTS.items():
            with self.subTest(book=report["title"]):
                self.assertEqual(
                    report["relationsFalselyVerified"], [],
                    "无 sourceRefs 的关系记录被标成 quoteVerified=true\n" + _evidence(
                        {"book": report["title"], "samples": report["relationsFalselyVerified"][:5]}))

    def test_located_but_not_verified_refs_are_never_promoted(self):
        """match != exact 的引用必须 verified=false，只能计「定位成功」。"""
        for key, report in REPORTS.items():
            with self.subTest(book=report["title"]):
                for layer, item, ref in Book.get(key).refs():
                    if ref.get("match") in (None, "exact", "none"):
                        continue
                    self.assertIs(
                        ref.get("verified"), False,
                        "match=%r 的引用被标成已核验：定位成功不等于语义正确\n%s" % (
                            ref.get("match"),
                            _evidence({"book": report["title"], "layer": layer, "id": item.get("id"),
                                       "ref": {k: ref.get(k) for k in ("match", "verified", "start", "end", "quote")}})))

    def test_chapter_extraction_is_not_inflated_by_author_notes(self):
        """标题抽取必须排除行内作者感言，否则章节数虚高、分母失真。

        这是抽取函数的行为测试，不依赖某一本书恰好含有作者感言：
        三段正文里只有两段是标题。
        """
        sample = ("第一章 牢狱之灾\n\n    正文。\n\n"
                  "    大佬们，记得帮我找错字呀。我继续爆肝码第二章。\n\n"
                  "第二章 妖物作祟\n\n    正文。\n\n"
                  "    PS：我去码第三章，凌晨以后了。\n")
        found = extract_headings(sample, "章")
        self.assertEqual(
            [h["label"] for h in found], ["第一章", "第二章"],
            "标题抽取把行内作者感言算成了章节——章节分母被虚高\n" + _evidence(
                {"sample": sample, "extracted": [h["label"] for h in found],
                 "looseHits": re.findall(r"第[0-9零〇一二三四五六七八九十百千两]+章", sample)}))
        for key, report in REPORTS.items():
            with self.subTest(book=report["title"]):
                loose = len(re.findall(r"第[0-9零〇一二三四五六七八九十百千两]+" + Book.get(key).unit,
                                       Book.get(key).text))
                self.assertLessEqual(
                    report["headings"], loose,
                    "抽出的标题数超过正文中的候选命中数，抽取逻辑不可能正确\n" + _evidence(
                        {"book": report["title"], "extracted": report["headings"], "looseHits": loose}))

    def test_ratchet_metrics_are_computed_over_a_real_sample(self):
        """防止「样本为 0 所以永远通过」的空壳断言。"""
        for key, report in REPORTS.items():
            with self.subTest(book=report["title"]):
                self.assertGreater(report["refs"], 100, "回放到的引用太少，样本不足以支撑结论")
                self.assertGreater(report["chapterLabelled"], 10, "可比对的章节样本太少")

    # ---------- RATCHET：已知缺陷冻结计数 ----------

    def test_known_defects_do_not_grow(self):
        """已知缺陷（章节漂移 / 无锚点关系 / 仅定位成功）只减不增。

        这里**不**放宽任何断言：基线是逐本逐项的精确计数，真实缺陷数量只要
        增长就 fail。缺陷本身记录在 ledger 的 knownGaps 与 decision.md，
        修复后重跑 --update-baseline 收紧。
        """
        baseline = load_baseline()["ratchet"]
        current = ratchet_summary()
        regressions = []
        for key, expected in baseline.items():
            for metric, limit in expected.items():
                value = current.get(key, {}).get(metric, 0)
                if value > limit:
                    regressions.append({"book": BOOKS[key][0], "metric": metric,
                                        "baseline": limit, "actual": value})
        self.assertEqual(
            regressions, [],
            "已知缺陷数量增长——回归而非修复\n" + _evidence(
                {"regressions": regressions,
                 "minimalRepro": "python3 tests/quote_fidelity_contract.py --report"}))

    def test_baseline_covers_exactly_the_current_books(self):
        """基线不得过期：书目集合不符即提示重跑 --update-baseline。"""
        baseline = load_baseline()
        self.assertEqual(set(baseline["ratchet"]), set(BOOKS),
                         "基线覆盖的书目集合与当前不符，请重跑 --update-baseline")
        for key, digest in baseline["sourceHashes"].items():
            self.assertEqual(digest, REPORTS[key]["declaredHash"],
                             "%s 的原文哈希已变，基线失效，请重跑 --update-baseline" % BOOKS[key][0])
        improved = [{"book": BOOKS[key][0], "metric": metric, "baseline": limit,
                     "actual": ratchet_summary()[key][metric]}
                    for key, expected in baseline["ratchet"].items()
                    for metric, limit in expected.items()
                    if ratchet_summary()[key][metric] < limit]
        if improved:
            sys.stderr.write("提示：下列已知缺陷计数已下降，请重跑 --update-baseline 收紧基线：\n"
                             + _evidence(improved) + "\n")


def write_baseline():
    payload = {
        "note": ("P11 引用保真棘轮基线。chapterDrift = 事件声明的章节号与引文实际落点之前"
                 "最近标题的章节号不一致的事件数；relationsWithoutAnchor = 无任何 sourceRefs 的"
                 "关系记录数；locatedNotVerified = match != exact 的引用数。只减不增，"
                 "修复后重跑 --update-baseline 收紧。这些是已记录的真实缺陷，不是允许值。"),
        "sourceHashes": {key: REPORTS[key]["declaredHash"] for key in BOOKS},
        "ratchet": ratchet_summary(),
        "observed": {key: {
            "title": REPORTS[key]["title"], "chars": REPORTS[key]["chars"],
            "refs": REPORTS[key]["refs"], "verified": REPORTS[key]["verified"],
            "exactSpanVerified": REPORTS[key]["exactSpanVerified"],
            "locatedNotVerified": REPORTS[key]["locatedNotVerified"],
            "nonExactByMatch": REPORTS[key]["nonExact"],
            "chapterLabelled": REPORTS[key]["chapterLabelled"],
            "chapterAccurate": REPORTS[key]["chapterAccurate"],
            "chapterDrift": len(REPORTS[key]["chapterDrift"]),
            "relations": REPORTS[key]["relations"],
            "relationsWithoutAnchor": REPORTS[key]["relationsWithoutAnchor"],
            "headings": REPORTS[key]["headings"],
        } for key in BOOKS},
    }
    with open(BASELINE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print("已写入 " + os.path.relpath(BASELINE, ROOT))


def print_report():
    for report in REPORTS.values():
        total = report["chapterAccurate"] + len(report["chapterDrift"])
        print("=" * 78)
        print("%s (%s)  正文 %d 字符 · textHash %s…" % (
            report["title"], report["bookKey"], report["chars"], str(report["declaredHash"])[:16]))
        print("  引用 %d · 已核验(exact) %d · 逐字复核通过 %d · 仅定位成功(未核验) %d"
              % (report["refs"], report["verified"], report["exactSpanVerified"],
                 report["locatedNotVerified"]))
        print("  match 分布（未核验）: %s" % (report["nonExact"] or "{}"))
        print("  HARD 违规: 切片不符 %d · verified非exact %d · 非codepoint %d · 哈希过期 %d · 章节标签不存在 %d"
              % (len(report["spanViolations"]), len(report["verifiedNotExact"]),
                 len(report["badUnit"]), len(report["badHash"]), len(report["chapterLabelMissing"])))
        print("  章节: 正文抽出标题 %d · 可比对事件 %d · 一致 %d · 漂移 %d (%.1f%%)"
              % (report["headings"], total, report["chapterAccurate"],
                 len(report["chapterDrift"]), 100.0 * len(report["chapterDrift"]) / max(1, total)))
        print("  关系 %d · 无事件级原文锚点 %d · 被误标已核验 %d"
              % (report["relations"], report["relationsWithoutAnchor"],
                 len(report["relationsFalselyVerified"])))
        for item in report["chapterDrift"][:6]:
            print("    DRIFT %s 声明 %s(#%d) 实际 %s(#%d) start=%d %r"
                  % (item["eventId"], item["claimedChapter"], item["claimedNumber"],
                     item["actualHeading"], item["actualNumber"], item["start"], item["quote"][:24]))
        for item in report["spanViolations"][:3]:
            print("    SPAN  %s %s" % (item["id"], item["minimalRepro"]))
        if len(report["chapterDrift"]) > 6:
            print("    …另有 %d 条，见 --update-baseline 生成的报告" % (len(report["chapterDrift"]) - 6))
    print("=" * 78)
    print("棘轮计数: " + json.dumps(ratchet_summary(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P11 引用保真契约")
    parser.add_argument("--update-baseline", action="store_true",
                        help="重写 tests/quote_fidelity_baseline.json")
    parser.add_argument("--report", action="store_true", help="只打印缺陷明细，不跑门禁")
    args = parser.parse_args()
    if args.update_baseline:
        write_baseline()
    elif args.report:
        print_report()
    else:
        print("QUOTE FIDELITY CONTRACT · 三书逐条回放 "
              + json.dumps(ratchet_summary(), ensure_ascii=False, sort_keys=True))
        unittest.main(verbosity=2)
