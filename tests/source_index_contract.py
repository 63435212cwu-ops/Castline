#!/usr/bin/env python3
"""P02 原文索引 / 覆盖台账契约（离线，零第三方依赖）。

断言四类硬约束（审核要求，违反即伪完成）：
  1. 偏移可逆：`text[start:end]` 以该单元的 heading 开头（空白归一后比较）；
  2. 章节无重叠、无空洞：单元首尾相接；
  3. ID 唯一：章节 ID、卷 ID 全局唯一且与 `meta.index` 的对应关系可复算；
  4. 声明的差异被记录：`extraction.declared != extraction.extracted` 时
     `extraction.gaps` 非空，且**没有**任何插值/均分补齐的痕迹。

另外复核覆盖台账的核心口径：
  - 分母来自实际抽取的章单元，不等于图谱声明值；
  - `match != exact` 的锚点只计「定位成功」，不计「已核验引句」；
  - 关系/故事线的可挂锚点率被显式记录（审核点名项）。

结论只来自重建（复用 tools/plan100/build_source_index.py），不硬编码数字。
"""
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BUILD = ROOT / "tools" / "plan100" / "build_source_index.py"
spec = importlib.util.spec_from_file_location("plan100_build_source_index", BUILD)
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

BOOKS = [b for b in B.BOOKS]
INDEX_DIR = ROOT / "tests" / "fixtures" / "contracts" / "source-index"
COVER_DIR = ROOT / "tests" / "fixtures" / "contracts" / "coverage"


def norm(s):
    return re.sub(r"[\s\u3000\u200b]+", "", s or "")


def heading_line(text, start):
    eol = text.find("\n", start)
    return text[start: eol if eol >= 0 else len(text)].strip()


class Plan100SourceIndexContract(unittest.TestCase):
    """每本作品独立断言；产物缺失即失败（P02 是内容阶段网关）。"""

    @classmethod
    def setUpClass(cls):
        cls.cache = {}
        for key, title in BOOKS:
            ip, cp = INDEX_DIR / f"{key}.json", COVER_DIR / f"{key}.json"
            assert ip.exists(), f"缺少原文索引 {ip.relative_to(ROOT)}：请先跑 build_source_index.py"
            assert cp.exists(), f"缺少覆盖台账 {cp.relative_to(ROOT)}：请先跑 build_source_index.py"
            cls.cache[key] = {
                "title": title,
                "index": json.loads(ip.read_text(encoding="utf-8")),
                "coverage": json.loads(cp.read_text(encoding="utf-8")),
                "text": B.load_docs(key)[0]["text"],
                "graph": B.load_graph(key),
            }

    # ---------------------------------------------------------------- 偏移可逆
    def test_offsets_are_reversible_into_original_text(self):
        for key, d in self.cache.items():
            with self.subTest(book=key):
                text, index = d["text"], d["index"]
                self.assertEqual(index["offsetUnit"], "codepoint")
                self.assertEqual(index["chars"], len(text))
                for c in index["chapters"]:
                    seg = text[c["start"]: c["end"]]
                    self.assertTrue(
                        seg.startswith(c["heading"]) or norm(heading_line(text, c["start"])) == norm(c["heading"]),
                        f"{key} {c['id']} text[start:end] 未以 heading 开头: {seg[:30]!r}",
                    )
                    if c["gluedHeading"]:
                        self.assertTrue(heading_line(text, c["start"]).startswith(c["heading"]))
                    else:
                        self.assertEqual(norm(heading_line(text, c["start"])), norm(c["heading"]))
                    self.assertEqual(c["chars"], c["end"] - c["start"])

    def test_heading_carries_a_real_chapter_number(self):
        for key, d in self.cache.items():
            with self.subTest(book=key):
                for c in d["index"]["chapters"]:
                    if c["kind"] != "chapter":
                        self.assertIsNone(c["chapterNo"])
                        continue
                    self.assertIsInstance(c["chapterNo"], int)
                    self.assertGreater(c["chapterNo"], 0)
                    m = re.match(r"^第[一二三四五六七八九十百千万零〇两0-9]+[章回]",
                                 c["heading"])
                    self.assertIsNotNone(m, f"{key} {c['id']} heading 无章节号: {c['heading']!r}")

    # -------------------------------------------------------- 无重叠 / 无空洞
    def test_units_are_contiguous_without_overlap_or_hole(self):
        for key, d in self.cache.items():
            with self.subTest(book=key):
                chapters, text = d["index"]["chapters"], d["text"]
                self.assertGreater(len(chapters), 0)
                for i, c in enumerate(chapters):
                    nxt = chapters[i + 1]["start"] if i + 1 < len(chapters) else len(text)
                    self.assertLessEqual(c["end"], nxt, f"{key} {c['id']} 与下一单元重叠")
                    self.assertEqual(c["end"], nxt, f"{key} {c['id']} 与下一单元之间存在空洞")
                self.assertEqual(chapters[0]["start"], json.loads(
                    (INDEX_DIR / f"{key}.json").read_text(encoding="utf-8"))["prelude"]["end"]
                    if json.loads((INDEX_DIR / f"{key}.json").read_text(encoding="utf-8"))["prelude"]
                    else 0)
                integ = d["index"]["integrity"]
                self.assertTrue(integ["contiguous"])
                self.assertEqual(integ["overlaps"], 0)
                self.assertEqual(integ["holes"], 0)
                self.assertTrue(integ["offsetReversible"])
                self.assertEqual(integ["coveredTo"], len(text))

    def test_volume_partition_covers_every_chapter_once(self):
        for key, d in self.cache.items():
            with self.subTest(book=key):
                index = d["index"]
                seen = [cid for v in index["volumes"] for cid in v["chapters"]]
                allids = [c["id"] for c in index["chapters"]]
                self.assertEqual(len(seen), len(set(seen)), f"{key} 章节被分到多个卷")
                self.assertEqual(set(seen), set(allids), f"{key} 卷划分未覆盖全部章节")
                for v in index["volumes"]:
                    self.assertEqual(v["chapterCount"],
                                     sum(1 for c in index["chapters"]
                                         if c["id"] in set(v["chapters"]) and c["kind"] == "chapter"))
                    kids = [c for c in index["chapters"] if c["id"] in set(v["chapters"])]
                    self.assertEqual(v["start"], kids[0]["start"])
                    self.assertEqual(v["end"], kids[-1]["end"])

    # ------------------------------------------------------------------ ID 唯一
    def test_ids_are_unique_and_stable(self):
        for key, d in self.cache.items():
            with self.subTest(book=key):
                index = d["index"]
                ids = [c["id"] for c in index["chapters"]]
                self.assertEqual(len(ids), len(set(ids)), f"{key} 章节 ID 重复")
                vids = [v["id"] for v in index["volumes"]]
                self.assertEqual(len(vids), len(set(vids)), f"{key} 卷 ID 重复")
                prefix = key[:8]
                for c in index["chapters"]:
                    self.assertTrue(c["id"].startswith(f"ch_{prefix}_"))
                for v in index["volumes"]:
                    self.assertTrue(v["id"].startswith(f"vol_{prefix}_"))
                rebuilt = B.build_source_index(key, d["title"])
                self.assertEqual([c["id"] for c in rebuilt["chapters"]], ids)
                self.assertEqual([(c["start"], c["end"]) for c in rebuilt["chapters"]],
                                 [(c["start"], c["end"]) for c in index["chapters"]])

    def test_graph_meta_index_correspondence_is_recorded(self):
        """稳定 ID 必须给出与图谱缓存 meta.index / events[].chapter 的对应关系。"""
        for key, d in self.cache.items():
            with self.subTest(book=key):
                ex = d["index"]["extraction"]
                declared = (d["graph"].get("meta") or {}).get("index", {}).get("chapters")
                if isinstance(declared, int):
                    self.assertEqual(ex["declared"], declared)
                    self.assertEqual(ex["declaredSource"], "meta.index.chapters")
                self.assertEqual(
                    ex["declared"],
                    B.declared_chapter_count(d["graph"]),
                )
                by_no = {c["chapterNo"] for c in d["index"]["chapters"] if c["chapterNo"]}
                for e in (d["graph"].get("events") or []):
                    label = e.get("chapter")
                    if not label:
                        continue
                    m = re.search(r"第\s*([一二三四五六七八九十百千万零〇两0-9]+)\s*[章回]", label)
                    if not m:
                        continue
                    no = B.N.cn_int(m.group(1))
                    self.assertIn(no, by_no,
                                  f"{key} 事件章节标签 {label!r} 在原文中无对应边界")

    # ------------------------------------------------- 声明的差异必须被记录
    def test_declared_vs_extracted_difference_is_recorded(self):
        for key, d in self.cache.items():
            with self.subTest(book=key):
                ex = d["index"]["extraction"]
                self.assertGreater(ex["extracted"], 0)
                self.assertGreater(ex["declared"], 0)
                self.assertTrue(ex["gaps"], f"{key} extraction.gaps 为空")
                if ex["declared"] != ex["extracted"]:
                    joined = "".join(ex["gaps"])
                    self.assertIn(str(ex["declared"]), joined)
                    self.assertIn(str(ex["extracted"]), joined)
                numbered = [c for c in d["index"]["chapters"] if c["kind"] == "chapter"]
                self.assertEqual(ex["extracted"], len(numbered))
                self.assertEqual(ex["extractedTotal"], len(d["index"]["chapters"]))
                self.assertEqual(ex["extractedSpecial"],
                                 sum(1 for c in d["index"]["chapters"] if c["kind"] != "chapter"))

    def test_no_interpolation_or_even_split_padding(self):
        """禁止用插值/均分补齐缺失章节：不得出现编造的连续章号填充。"""
        for key, d in self.cache.items():
            with self.subTest(book=key):
                index = d["index"]
                gaps = index["extraction"]["numberingGaps"]
                real = {(c["volume"], c["chapterNo"]) for c in index["chapters"]
                        if c["chapterNo"] is not None}
                for g in gaps:
                    self.assertNotIn((g["volume"], g["chapterNo"]), real,
                                     f"{key} 缺号章 {g} 被凭空补齐")
                for v in index["volumes"]:
                    rows = [c for c in index["chapters"]
                            if c["volume"] == v["index"] and c["chapterNo"] is not None]
                    for a, b in zip(rows, rows[1:]):
                        if b["chapterNo"] < a["chapterNo"]:
                            self.assertTrue(
                                b.get("outOfOrder"),
                                f"{key} 卷{v['index']} {b['id']} 章号倒序"
                                f"（{a['chapterNo']}→{b['chapterNo']}）但未标 outOfOrder"
                                f" —— 倒序必须显式披露，不得静默拼接")
                for c in index["chapters"]:
                    if c.get("outOfOrder"):
                        nums = {x["chapterNo"] for x in index["chapters"]
                                if x["volume"] == c["volume"] and x["chapterNo"] is not None}
                        self.assertTrue(
                            any(abs(c["chapterNo"] - n) <= 3 for n in nums if n != c["chapterNo"]),
                            f"{key} {c['id']} 标了 outOfOrder 但附近没有相邻章号 —— 疑似噪声")

    # ---------------------------------------------------------------- 多体例适配
    def test_each_book_uses_its_own_chapter_unit(self):
        units = {}
        for key, d in self.cache.items():
            with self.subTest(book=key):
                index = d["index"]
                units[key] = index["chapterUnit"]
                self.assertIn(index["chapterUnit"], ("章", "回"))
                for c in index["chapters"]:
                    if c["kind"] != "chapter":
                        continue
                    self.assertEqual(c["unit"], index["chapterUnit"])
                self.assertEqual(index["extraction"]["extracted"],
                                 sum(1 for c in index["chapters"] if c["kind"] == "chapter"))
        self.assertEqual(units["9b676d7031b1bcd3b8377a18"], "章")
        self.assertEqual(units["df959d743e53206f56db2f92"], "回")
        self.assertEqual(units["152e2a6eed94f1075e7e7070"], "回")

    # ------------------------------------------------------------- 覆盖台账口径
    def test_coverage_denominator_comes_from_extracted_units(self):
        for key, d in self.cache.items():
            with self.subTest(book=key):
                cov, index = d["coverage"], d["index"]
                den = cov["denominator"]
                self.assertTrue(den["declaredIsNotDenominator"])
                self.assertEqual(den["chapters"], len(index["chapters"]))
                self.assertEqual(den["numberedChapters"], index["extraction"]["extracted"])
                self.assertEqual(den["chars"], index["chars"])
                rows = cov["chapters"]
                self.assertEqual(len(rows), len(index["chapters"]))
                self.assertEqual([r["id"] for r in rows], [c["id"] for c in index["chapters"]])
                bucket = sum(cov["coverage"][k] for k in
                             ("deepRead", "windowRead", "anchoredUnreviewed", "pending"))
                self.assertEqual(bucket, len(rows), f"{key} 覆盖分桶之和 != 章节总数")
                for r in rows:
                    self.assertIn(r["status"], ("deep-read", "window-read",
                                                "anchored-unreviewed", "pending"))

    def test_located_is_not_counted_as_verified_quote(self):
        for key, d in self.cache.items():
            with self.subTest(book=key):
                cov = d["coverage"]
                q = cov["quotes"]
                dist = cov["matchDistribution"]
                self.assertEqual(q["verifiedQuotes"], dist.get("exact", 0))
                self.assertEqual(
                    q["locatedOnly"],
                    sum(dist.get(k, 0) for k in ("normalized", "ambiguous", "no_offset")),
                )
                self.assertIn("定位成功不等于语义判断正确", q["rule"])
                flagged = [layer for layer in B.LAYERS
                           for it in (d["graph"].get(layer) or [])
                           if isinstance(it, dict) and it.get("claimVerified")]
                self.assertEqual(flagged, [], f"{key} 存在 claimVerified=true，与未核验口径冲突")

    def test_relation_and_storyline_attachable_rate_is_recorded(self):
        for key, d in self.cache.items():
            with self.subTest(book=key):
                cov = d["coverage"]
                for name in ("relations", "storylines"):
                    st = cov[name]
                    self.assertIn("attachableRate", st)
                    self.assertEqual(
                        st["chapterOffsetAttachable"] if name == "relations"
                        else st["withOwnExactAnchor"] + st["resolvableToExactEvent"],
                        (st["withOwnExactAnchor"] + st["resolvableToExactEvent"]),
                    )
                    total = st["records"]
                    if total:
                        expect = (st["withOwnExactAnchor"] + st["resolvableToExactEvent"]) / total
                        self.assertAlmostEqual(st["attachableRate"], round(expect, 4), places=4)
                zero = cov["suspects"]["layersWithZeroAnchor"]
                for layer, st in cov["layers"].items():
                    if st["records"] and st["withAnchor"] == 0:
                        self.assertIn(layer, zero)
                    if st["records"]:
                        self.assertLessEqual(st["anchorRate"], 1.0)
                        self.assertLessEqual(st["exactRecordRate"], 1.0)

    def test_equal_split_claim_is_adjudicated_with_evidence(self):
        """大奉「8 条全书线为机械等分」：必须给出可复核的判定，而不是复述审核。"""
        key = "9b676d7031b1bcd3b8377a18"
        st = self.cache[key]["coverage"]["storylines"]
        test = st["boundaryTest"]
        self.assertTrue(test["applicable"])
        sls = [s for s in (self.cache[key]["graph"].get("storylines") or []) if isinstance(s, dict)]
        self.assertEqual(test["storylines"], len(sls))
        self.assertEqual(test["eventCounts"], [len(s.get("eventIds") or []) for s in sls])
        self.assertIn(test["verdict"], ("mechanical-equal-split-confirmed",
                                        "equal-split-on-event-order", "not-equal-split"))
        if test["nearUniform"] and test["contiguousOrderPartition"] and test["cutPointsTested"]:
            self.assertIn(test["verdict"],
                          ("mechanical-equal-split-confirmed", "equal-split-on-event-order"))
            self.assertTrue(test["narrativeRisk"])
        else:
            self.assertEqual(test["verdict"], "not-equal-split")
        self.assertEqual(test["cutPointsTested"], test["storylines"] - 1)

    def test_stable_id_registry_and_alias_orphan_records(self):
        """P02-W03：稳定 ID 唯一，且别名冲突与孤立节点被记录（不自动合并）。"""
        for key, d in self.cache.items():
            with self.subTest(book=key):
                ids = d["coverage"]["ids"]
                self.assertTrue(ids["chapterIdUnique"])
                self.assertTrue(ids["chapterOrdinalMatchesIndex"])
                self.assertEqual(ids["chapterIdCount"], len(d["index"]["chapters"]))
                for c in ids["chapters"]:
                    self.assertTrue(c["id"].startswith(f"ch_{key[:8]}_"))
                    self.assertTrue(c["volumeId"].startswith(f"vol_{key[:8]}_"))
                for layer, st in ids["graphLayers"].items():
                    self.assertEqual(st["uniqueIds"], st["withId"],
                                     f"{key} {layer} 存在重复 id")
                    self.assertEqual(st["withId"] + st["missingIds"], st["records"])
                    if st["missingIds"]:
                        self.assertEqual(st["stableIdStatus"], "no-stable-id")
                        self.assertIn("missingIdNote", st)
                    else:
                        self.assertEqual(st["stableIdStatus"], "ok")
                self.assertEqual(ids["graphLayers"]["camps"]["stableIdStatus"], "no-stable-id")
                self.assertIn("namespaceCollisionWarning", ids)
                ident = d["coverage"]["identity"]
                self.assertEqual(ident["characters"],
                                 len([c for c in (d["graph"].get("characters") or [])]))
                for coll in ident["aliasCollisions"]:
                    self.assertGreater(coll["count"], 1)
                self.assertEqual(sum(1 for _ in (d["graph"].get("characters") or [])),
                                 ident["characters"])

    def test_reference_index_maps_every_chapter(self):
        """引用索引：每章都有 exact 锚点密度入口（0 也要有键，不能缺项）。"""
        for key, d in self.cache.items():
            with self.subTest(book=key):
                ri = d["coverage"]["referenceIndex"]
                dens = ri["chapterAnchorDensity"]
                self.assertEqual(len(dens), len(d["index"]["chapters"]))
                for c in d["index"]["chapters"]:
                    self.assertIn(c["id"], dens)
                self.assertEqual(ri["chaptersTotal"], len(d["index"]["chapters"]))
                self.assertEqual(ri["chaptersWithExactAnchor"],
                                 sum(1 for v in dens.values() if v > 0))

    def test_missing_fields_are_reported_as_pending_not_defaulted(self):
        for key, d in self.cache.items():
            with self.subTest(book=key):
                mf = d["coverage"]["missingFields"]
                self.assertTrue(mf["layersNotProvided"] or mf["layersAbsent"]
                                or mf["incompleteRecordFields"])
                self.assertIn("待核", mf["noFabricatedDefaults"])
                for layer in mf["layersNotProvided"]:
                    self.assertFalse((d["graph"].get(layer) or []),
                                     f"{key} {layer} 声称 not_provided 却有条目")

    def test_every_artifact_is_reproducible_byte_for_byte(self):
        """证据可复现：重建结果必须与已产出文件逐字节一致（--check 的语义）。"""
        for key, d in self.cache.items():
            with self.subTest(book=key):
                rebuilt_index = B.build_source_index(key, d["title"])
                rebuilt_cov = B.build_coverage(key, d["title"], d["text"], d["graph"], rebuilt_index)
                self.assertEqual(rebuilt_index, d["index"], f"{key} source-index 不可复现")
                self.assertEqual(rebuilt_cov, d["coverage"], f"{key} coverage 不可复现")


if __name__ == "__main__":
    unittest.main(verbosity=2)
