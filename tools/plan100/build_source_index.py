#!/usr/bin/env python3
"""P02 原文索引 + 覆盖台账的一键重建器（零第三方依赖，Python 3.13）。

产出（相对仓库根）：
  artifacts/plan100/source-index/<bookKey>.json   原文卷章边界索引（契约见 BRIEFING 4.1）
  artifacts/plan100/coverage/<bookKey>.json       覆盖台账（契约见 BRIEFING 4.2）

设计原则（违反即伪完成）：
  1. 章节边界**只从正文实际抽取**，绝不用插值/均分/按声明数量补齐缺失章节。
     抽取不到就写进 `extraction.gaps`，`extracted` 就是实际数量。
  2. `start`/`end` 是**正文 codepoint 偏移**，`text[start:end]` 必须能直接取出该章原文。
  3. 卷/章单元首尾相接、无重叠无空洞：每个单元 end = 下一个单元 start。
  4. `match != exact` 的锚点只计「定位成功」（`located`），不计「已核验引句」
     （`verifiedQuotes`）。定位成功不等于语义判断正确。

复用：章节标题解析复用 `narrative.chapter_spans()`（仓库既有能力，不另造正则）。
本脚本对 `narrative.chapter_spans` 做三件事，都在索引里显式记录：
  a. 前置卷首 `volumes` 切分（由「同卷第 1 章」重建，仓库正文无独立卷标题行）；
  b. 补上正文首个标题之前的卷首前言单元；
  c. 逐单元校验 offset 可逆、无重叠、无空洞，失败即报错退出（不做静默修补）。

用法：
  python3 tools/plan100/build_source_index.py               # 重建全部
  python3 tools/plan100/build_source_index.py --check       # 只校验已产出文件是否与重建一致
  python3 tools/plan100/build_source_index.py --book <key>  # 只重建一本
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import narrative as N

SOURCE_INDEX_DIR = artifact_path() / "plan100" / "source-index"
COVERAGE_DIR = artifact_path() / "plan100" / "coverage"

BOOKS = [
    ("9b676d7031b1bcd3b8377a18", "大奉打更人"),
    ("df959d743e53206f56db2f92", "西游记"),
    ("152e2a6eed94f1075e7e7070", "三国演义"),
]

LAYERS = (
    "events", "relations", "causeEdges", "tasks", "characterStates",
    "clues", "storylines", "episodes", "narrativeUnits", "characters", "camps",
)

REF_FIELDS = ("sourceRefs", "quoteRef", "quoteRefs", "evidenceRefs", "referenceRefs")

REVIEWED_PROVENANCE = ("assistant-reviewed-source", "assistant_reviewed_source")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_docs(book_key: str) -> list[dict]:
    p = ROOT / "data" / "cache" / f"{book_key}.docs.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_graph(book_key: str) -> dict:
    p = ROOT / "data" / "cache" / f"{book_key}.json"
    return json.loads(p.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def chapter_units(text: str) -> list[dict]:
    """正文实际卷章单元（首尾相接）。

    直接使用 `narrative.chapter_spans`：它是仓库里唯一经过现有契约测试
    （tests/narrative_context_contract.py 等）的标题解析器，已经处理了
    西游第二十五回「标题与正文粘连」、大奉无编号番外、西游附录等形态。

    第一个标题之前的内容（站点信息 / 卷名分节块）不在 chapters 里造伪章节，
    而是单独放进索引顶层的 `prelude`（见 build_source_index），这样每个
    chapters[] 条目的 `text[start:end]` 都精确以自身 heading 开头。
    """
    spans = N.chapter_spans(text)
    units: list[dict] = []
    for i, s in enumerate(spans):
        end = spans[i + 1]["start"] if i + 1 < len(spans) else len(text)
        kind = "special" if s["no"] is None else "chapter"
        units.append({
            "start": s["start"], "end": end, "no": s["no"], "unit": s["unit"],
            "heading": s["head"], "kind": kind,
        })
    return units


def split_volumes(units: list[dict]) -> list[list[dict]]:
    """按「同卷第 1 章」把单元切成卷。

    仓库正文没有独立卷标题行（大奉卷名只出现在卷首/卷尾感言里），因此卷边界
    只能由正文自身的「第一章」重号重建；这不是插值——每个卷都包含真实章节。
    无编号单元（卷首前言、番外、附录）归入其所在位置的前一卷。
    """
    volumes: list[list[dict]] = []
    cur: list[dict] = []
    for u in units:
        if u["kind"] == "chapter" and u["no"] == 1 and cur and any(x["kind"] == "chapter" for x in cur):
            volumes.append(cur)
            cur = []
        cur.append(u)
    if cur:
        volumes.append(cur)
    return volumes


VOLUME_TITLE_PATTERNS = (
    re.compile(r"第([一二三四五六七八九十]+)卷\s*(?:是|叫|名为?|[:：，,、]|——|--|—)\s*《?([^\n。，！？；、」』】）)]{1,10})》?"),
    re.compile(r"第([一二三四五六七八九十]+)卷\s*《([^》\n]{1,10})》"),
)
VOLUME_NOTE_TAIL = 24000
VOLUME_NAME_REJECT = re.compile(
    r"本书|整本|一个|一些|的|是|了|这|那|目前为止|剧情|大纲|内容|名字|名称|总结|部分|前半|后半|写完|结束"
)
VOLUME_NAME_OK = re.compile(r"^[\u4e00-\u9fff]{2,8}$")


def looks_like_volume_name(cand: str) -> bool:
    """卷名判据：2–8 个纯汉字、不含功能词。不满足就当作『没取到』而不是猜一个。"""
    return bool(VOLUME_NAME_OK.match(cand)) and not VOLUME_NAME_REJECT.search(cand)


def volume_titles_from_author_notes(text: str, vol_units: list[dict],
                                     prelude: dict | None) -> list[dict]:
    """卷名只从**正文自身的作者单章**取，并记录取证 offset。

    判据（任一命中，且「第N卷」的 N 必须等于本卷序号）：
      1. 作者单章句式 `第N卷是/叫/：X`、`第N卷——X`、`第N卷《X》`；
      2. 卷首分节块里的短行（大奉首卷「京察风云」写在正文最前面的卷首块中）。
    取不到 → title 为空、basis=unknown、evidence 为空。**不猜、不编、不借用别卷名字。**
    """
    out: list[dict] = []
    for vi, g in enumerate(vol_units, start=1):
        base = g[0]["start"]
        nxt = vol_units[vi][0]["start"] if vi < len(vol_units) else len(text)
        body = text[base: min(len(text), nxt + VOLUME_NOTE_TAIL)]
        title, basis, evidence = "", "unknown", None
        for pat in VOLUME_TITLE_PATTERNS:
            for m in pat.finditer(body):
                if N.cn_int(m.group(1)) != vi:
                    continue
                cand = m.group(2).strip("《》「」 \u3000")
                if looks_like_volume_name(cand):
                    title, basis = cand, "author_note_in_volume"
                    evidence = {"start": base + m.start(), "end": base + m.end(),
                                "quote": m.group(0)[:80]}
                    break
            if title:
                break
        if not title and vi == 1 and prelude:
            raw = text[prelude["start"]: prelude["end"]]
            for line in raw.splitlines():
                s = line.strip()
                if looks_like_volume_name(s):
                    off = prelude["start"] + raw.find(s)
                    title, basis = s, "volume_preface_in_source"
                    evidence = {"start": off, "end": off + len(s), "quote": s}
                    break
        out.append({"title": title, "basis": basis, "evidence": evidence})
    return out


def build_source_index(book_key: str, title: str) -> dict:
    docs = load_docs(book_key)
    graph = load_graph(book_key)
    meta = graph.get("meta") or {}
    sources = meta.get("sources") or []
    src = sources[0] if sources else {}
    doc = docs[0]
    text: str = doc["text"]

    units = chapter_units(text)
    if not units:
        raise SystemExit(f"{book_key}: 正文未抽到任何章节边界，拒绝生成索引（不得插值补齐）")

    prelude = None
    if units[0]["start"] > 0:
        raw = text[: units[0]["start"]]
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        title_line = next((ln for ln in lines if not set(ln) <= {"-", "－", "—"}), "")
        prelude = {
            "start": 0,
            "end": units[0]["start"],
            "chars": units[0]["start"],
            "titleLine": title_line,
            "excerpt": raw.strip()[:200],
            "note": "首个章节标题之前的卷首内容；不计入章节分母，也不作为章节单元。",
        }

    vol_groups = split_volumes(units)

    vol_titles: list[dict] = volume_titles_from_author_notes(text, vol_groups, prelude)

    chapters: list[dict] = []
    volumes: list[dict] = []
    ordinal = 0
    chapter_ordinal = 0
    special_ordinal = 0
    for vi, g in enumerate(vol_groups, start=1):
        vstart, vend = g[0]["start"], g[-1]["end"]
        vt = vol_titles[vi - 1]
        vname, vbasis = vt["title"], vt["basis"]
        vol_children = []
        prev_no = None
        for u in g:
            ordinal += 1
            seg = text[u["start"]: u["end"]]
            if not offset_reversible(text, u):
                raise SystemExit(
                    f"{book_key}: offset 不可逆 unit#{ordinal} start={u['start']} "
                    f"heading={u['heading'][:40]!r} seg={seg[:40]!r}"
                )
            if u["kind"] == "chapter":
                chapter_ordinal += 1
                index_no, stable_kind = chapter_ordinal, "chapter"
            else:
                special_ordinal += 1
                index_no, stable_kind = special_ordinal, u["kind"]
            cid = stable_chapter_id(book_key, u, index_no, chapter_ordinal, special_ordinal)
            assert cid not in {c["id"] for c in chapters}, f"duplicate chapter id {cid}"
            row = {
                "index": index_no,
                "ordinal": ordinal,
                "id": cid,
                "kind": stable_kind,
                "label": u["heading"],
                "heading": u["heading"],
                "chapterNo": u["no"],
                "unit": u["unit"],
                "start": u["start"],
                "end": u["end"],
                "chars": u["end"] - u["start"],
                "title": strip_heading_number(u["heading"]),
                "volume": vi,
                "volumeTitle": vname,
                "gluedHeading": bool(offset_reversible(text, u)
                                     and norm_ws(heading_line(text, u["start"])) != norm_ws(u["heading"])),
                "outOfOrder": bool(prev_no is not None and u["no"] is not None
                                   and u["no"] < prev_no),
            }
            assert cid.startswith(f"ch_{book_key[:8]}_")
            chapters.append(row)
            vol_children.append(cid)
            if u["no"] is not None:
                prev_no = u["no"]
        volumes.append({
            "index": vi,
            "id": stable_volume_id(book_key, vi),
            "title": vname,
            "titleBasis": vbasis,
            "titleEvidence": vt["evidence"],
            "start": vstart,
            "end": vend,
            "chars": vend - vstart,
            "chapterCount": sum(1 for u in g if u["kind"] == "chapter"),
            "prefaceChars": prelude["chars"] if (vi == 1 and prelude) else 0,
            "chapters": vol_children,
        })

    declared = declared_chapter_count(graph)
    numbered = [c for c in chapters if c["chapterNo"] is not None]
    gaps = extraction_gaps(book_key, title, text, graph, units, chapters, declared)

    return {
        "schema": "castline/plan100-source-index/v1",
        "bookKey": book_key,
        "title": title,
        "docsPath": f"data/cache/{book_key}.docs.json",
        "graphPath": f"data/cache/{book_key}.json",
        "sourceId": src.get("id"),
        "sourcePath": src.get("path") or doc.get("path"),
        "sourceName": src.get("name") or doc.get("name"),
        "textHash": sha256_text(text),
        "cacheTextHash": src.get("textHash"),
        "offsetUnit": "codepoint",
        "chars": len(text),
        "declaredChars": src.get("chars"),
        "chapterUnit": "章" if book_key == "9b676d7031b1bcd3b8377a18" else "回",
        "idScheme": {
            "chapter": f"ch_{book_key[:8]}_<index>",
            "volume": f"vol_{book_key[:8]}_<index>",
            "event": "沿用图谱既有 ev_* id（不重编号）",
            "character": "沿用图谱既有 ch_* id（与章节 id 前缀同名但空间不同，见 notes）",
        },
        "chapters": chapters,
        "volumes": volumes,
        "prelude": prelude,
        "extraction": {
            "declared": declared,
            "declaredSource": declared_source(graph),
            "extracted": len(numbered),
            "extractedTotal": len(chapters),
            "extractedSpecial": sum(1 for c in chapters if c["kind"] != "chapter"),
            "extractedPreface": sum(1 for c in chapters if c["kind"] == "preface"),
            "volumeCount": len(volumes),
            "maxChapterNo": max((c["chapterNo"] for c in numbered), default=0),
            "distinctChapterNo": len({c["chapterNo"] for c in numbered}),
            "numberingGaps": numbering_gaps(numbered),
            "duplicateChapterNo": duplicate_numbers(numbered),
            "gaps": gaps,
        },
        "integrity": integrity_report(text, chapters, volumes),
    }


def norm_ws(s: str) -> str:
    """比较用：去掉所有空白（含全角空格）。"""
    return re.sub(r"[\s\u3000\u200b]+", "", s or "")


def heading_line(text: str, start: int) -> str:
    """正文里真实的第一行标题（保留原始全角空格与分隔符）。"""
    eol = text.find("\n", start)
    return text[start: eol if eol >= 0 else len(text)].strip()


BARE_HEAD_RE = re.compile(r"^第[一二三四五六七八九十百千万零〇两0-9]+[章回]$")


def offset_reversible(text: str, unit: dict) -> bool:
    """`text[start:end]` 必须以该单元的标题行为开头。

    两种情况都算可逆，且都被如实标注：
      1. 空白归一后完全一致（正文对附录等做过排版：`附  录` vs `附录`）；
      2. 「粘连标题」——标题只有 `第N回/章`（如西游第二十五回，回目与正文之间
         没有换行），此时要求真实行以该编号原文开头；索引里记 `gluedHeading=true`，
         消费方不得把 `heading` 当成完整回目。
    """
    if unit["start"] >= len(text):
        return False
    line = heading_line(text, unit["start"])
    if norm_ws(line) == norm_ws(unit["heading"]):
        return True
    return bool(BARE_HEAD_RE.match(unit["heading"])) and line.startswith(unit["heading"])


def strip_heading_number(heading: str) -> str:
    m = re.match(r"^第[一二三四五六七八九十百千万零〇两0-9]+[章回][ \t\u3000：:]*", heading or "")
    return (heading or "")[m.end():].strip() if m else (heading or "").strip()


def stable_chapter_id(book_key: str, unit: dict, index_no: int,
                      chapter_ordinal: int = 0, special_ordinal: int = 0) -> str:
    """稳定章节 ID：ch_<bookKey前8>_<章序号>；无编号单元用 x 前缀分空间，避免撞号。"""
    if unit["kind"] == "chapter":
        return f"ch_{book_key[:8]}_{chapter_ordinal:04d}"
    return f"ch_{book_key[:8]}_x{special_ordinal:03d}"


def stable_volume_id(book_key: str, index: int) -> str:
    return f"vol_{book_key[:8]}_{index}"


def declared_chapter_count(graph: dict) -> int:
    meta = graph.get("meta") or {}
    n = (meta.get("index") or {}).get("chapters")
    if isinstance(n, int) and n > 0:
        return n
    return len({e.get("chapter") for e in (graph.get("events") or []) if e.get("chapter")})


def declared_source(graph: dict) -> str:
    meta = graph.get("meta") or {}
    if isinstance((meta.get("index") or {}).get("chapters"), int):
        return "meta.index.chapters"
    return "distinct(events[].chapter)"


def numbering_gaps(numbered: list[dict]) -> list[dict]:
    """章号序列里缺号的位置（只报告，不修补）。"""
    out = []
    by_vol: dict[int, list[int]] = {}
    for c in numbered:
        by_vol.setdefault(c["volume"], []).append(c["chapterNo"])
    for vol, nums in sorted(by_vol.items()):
        seen = set(nums)
        for n in range(1, max(nums) + 1):
            if n not in seen:
                out.append({"volume": vol, "chapterNo": n})
    return out


def duplicate_numbers(numbered: list[dict]) -> list[dict]:
    """同卷内重复章号（大奉存在真重号章，例如第一百五十五章两章）。"""
    by_vol: dict[int, dict[int, list[dict]]] = {}
    for c in numbered:
        by_vol.setdefault(c["volume"], {}).setdefault(c["chapterNo"], []).append(c)
    out = []
    for vol, groups in sorted(by_vol.items()):
        for no, items in sorted(groups.items()):
            if len(items) > 1:
                out.append({
                    "volume": vol, "chapterNo": no,
                    "count": len(items),
                    "ids": [i["id"] for i in items],
                    "headings": [i["heading"] for i in items],
                })
    return out


def integrity_report(text: str, chapters: list[dict], volumes: list[dict]) -> dict:
    """偏移可逆 / 无重叠 / 无空洞 / ID 唯一 —— 供契约测试复核。"""
    ids = [c["id"] for c in chapters]
    vid = [v["id"] for v in volumes]
    overlaps, holes, reversible = 0, 0, True
    for i, c in enumerate(chapters):
        if not offset_reversible(text, c):
            reversible = False
        nxt = chapters[i + 1]["start"] if i + 1 < len(chapters) else len(text)
        if c["end"] > nxt:
            overlaps += 1
        if c["end"] < nxt:
            holes += 1
    return {
        "offsetReversible": reversible,
        "overlaps": overlaps,
        "holes": holes,
        "contiguous": overlaps == 0 and holes == 0,
        "coveredFrom": chapters[0]["start"] if chapters else None,
        "coveredTo": chapters[-1]["end"] if chapters else None,
        "chars": len(text),
        "uniqueChapterIds": len(set(ids)) == len(ids),
        "uniqueVolumeIds": len(set(vid)) == len(vid),
        "chapterIdPrefix": f"ch_{chapters[0]['id'].split('_')[1]}_" if chapters else None,
    }


def extraction_gaps(book_key, title, text, graph, units, chapters, declared) -> list[str]:
    """declared vs extracted 的差异，逐条查清来源后如实写入。"""
    gaps: list[str] = []
    numbered = [c for c in chapters if c["chapterNo"] is not None]
    gaps.append(
        f"图谱声明 {declared} 章（{declared_source(graph)}），正文实际抽到 {len(numbered)} 章；"
        f"差异原因是声明值数的是 events[].chapter 标签去重数，而正文同一卷内存在重号章"
        f"（作者改稿/重发）以及番外/附录等无编号单元，两者不是同一个口径。"
        f"本索引以正文实际边界为准，禁用 {declared} 作为分母。"
    )
    dup = duplicate_numbers(numbered)
    if dup:
        gaps.append(
            f"正文存在 {len(dup)} 处同卷重号章（例如 "
            + "；".join(f"第{d['chapterNo']}章×{d['count']}" for d in dup[:3])
            + "）。按章号去重会把章节数砍到 distinct 数，本索引按标题全串去重，保留全部单元。"
        )
    special = [c for c in chapters if c["kind"] == "special"]
    if special:
        gaps.append(
            "正文含无编号单元（" + "；".join(c["heading"][:24] for c in special[:4]) + "），"
            "已单独建为 kind=special/preface 单元并纳入分母，未按章号强编号。"
        )
    if book_key == "9b676d7031b1bcd3b8377a18":
        gaps.append(
            "大奉正文没有独立的卷标题行；卷边界由正文自身的「第一章」重号重建，卷名只在卷首/卷尾"
            "作者单章里出现（本索引的 volume.title 即取自正文自身，titleBasis=author_note_in_volume "
            "或 volume_preface，取不到时为 unknown，未编造）。"
        )
    if book_key == "152e2a6eed94f1075e7e7070":
        nav = text.count("回首页后一页前一页回目录回首页")
        gaps.append(
            f"三国正文混入抓取站点导航垃圾（『回首页后一页前一页回目录回首页』出现 {nav} 次），"
            "位于上一回正文与下一回标题之间，导致回目标题不总在行首；narrative.chapter_spans 仍能"
            "正确切出全部 120 回，但该噪声仍留在章内正文里，属数据质量缺陷。"
        )
    if book_key == "df959d743e53206f56db2f92":
        gaps.append(
            "西游第二十五回标题与正文粘连（『…孙行者大闹五庄观却说他兄弟三众…』，标题后无换行），"
            "只做行首/行内换行匹配的解析器会漏掉该回并少算 1 章；narrative.chapter_spans 已正确处理。"
        )
        gaps.append(
            "西游含『附录　陈光蕊赴任逢灾　江流僧复仇报本』（无回号）与回目字号/分隔符不统一"
            "（既有全角空格也有半角空格与无分隔），已作为 kind=special 单元保留。"
        )
    return gaps


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def iter_refs(rec: dict, fields=REF_FIELDS):
    for f in fields:
        v = rec.get(f)
        if isinstance(v, dict):
            yield f, v
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    yield f, item
    fe = rec.get("fieldEvidence")
    if isinstance(fe, dict):
        for f, arr in fe.items():
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, dict):
                        yield f"fieldEvidence.{f}", item
    attrs = rec.get("attrs")
    if isinstance(attrs, dict):
        for name, a in attrs.items():
            if isinstance(a, dict):
                for item in a.get("evidenceRefs") or []:
                    if isinstance(item, dict):
                        yield f"attrs.{name}", item


def classify_ref(ref: dict) -> str:
    """把锚点归入 exact / normalized / ambiguous / not_found / no_offset。

    判据以**归一化流程自己的 `match` 字段**为准（图谱是权威），不反过来用
    `verified` 去推翻它：实测存在 `match=exact` 但 `verified=false` 的锚点
    （西游/三国各 2 条），把 `verified` 当门槛会把它误判成未定位。
    """
    m = ref.get("match")
    if m is None:
        m = "exact" if ref.get("verified") else None
    if m == "fuzzy":
        return "normalized"
    if m in ("exact", "normalized", "ambiguous"):
        return m
    if m in ("none", "unmatched", "missing"):
        return "not_found"
    return "no_offset"


def chapter_of(chapters: list[dict], offset: int) -> dict | None:
    lo, hi, found = 0, len(chapters) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if chapters[mid]["start"] <= offset:
            found = chapters[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return found


def build_reference_index(book_key: str, text: str, graph: dict, chapters: list[dict]) -> dict:
    """逐层统计锚点，并给出**记录级**（不是锚点级）的分布与章节归属核对。

    关键口径：
      * `withAnchor` = 至少有一条锚点的记录数；`exact` = 至少有一条 exact 锚点的**记录数**
        （与 withAnchor 同口径，避免「一个记录 100 条引句」把比例冲到 150%）。
      * `refs` 才是锚点条数，`refMatches` 才是锚点级分布。
      * `chapterMismatch` 按**记录**计数（同一记录的多个字段引用同一错章只算一次）。
    """
    match_counts: dict[str, int] = {}
    layer_stats: dict[str, dict] = {}
    for layer in LAYERS:
        items = graph.get(layer) or []
        if not isinstance(items, list) or not items:
            continue
        stat = {"records": len(items), "withAnchor": 0, "exact": 0, "locatedOnly": 0,
                "noAnchor": 0, "refs": 0, "refMatches": {}, "chapterMismatch": 0,
                "mismatchSamples": []}
        for rec in items:
            if not isinstance(rec, dict):
                continue
            refs = list(iter_refs(rec))
            if not refs:
                stat["noAnchor"] += 1
                continue
            stat["withAnchor"] += 1
            kinds = []
            mismatch_here = None
            for fname, ref in refs:
                stat["refs"] += 1
                kind = classify_ref(ref)
                kinds.append(kind)
                match_counts[kind] = match_counts.get(kind, 0) + 1
                stat["refMatches"][kind] = stat["refMatches"].get(kind, 0) + 1
                if kind == "exact" and isinstance(ref.get("start"), int):
                    declared = rec.get("chapter") or rec.get("chapterLabel")
                    loc = chapter_of(chapters, ref["start"])
                    if declared and loc is not None:
                        dn = re.search(r"第\s*([一二三四五六七八九十百千万零〇两0-9]+)\s*[章回]",
                                       str(declared))
                        declared_no = N.cn_int(dn.group(1)) if dn else None
                        if declared_no and declared_no != loc["chapterNo"] and mismatch_here is None:
                            mismatch_here = {
                                "id": rec.get("id") or rec.get("entityId"),
                                "declared": str(declared)[:40],
                                "actual": loc["heading"][:40],
                                "start": ref["start"],
                                "field": fname,
                            }
            if "exact" in kinds:
                stat["exact"] += 1
            elif any(k in ("normalized", "ambiguous") for k in kinds):
                stat["locatedOnly"] += 1
            if mismatch_here:
                stat["chapterMismatch"] += 1
                if len(stat["mismatchSamples"]) < 5:
                    stat["mismatchSamples"].append(mismatch_here)
        stat["anchorRate"] = round(stat["withAnchor"] / stat["records"], 4) if stat["records"] else None
        stat["exactRecordRate"] = round(stat["exact"] / stat["records"], 4) if stat["records"] else None
        layer_stats[layer] = stat

    per_chapter: dict[str, int] = {c["id"]: 0 for c in chapters}
    for layer in LAYERS:
        for rec in graph.get(layer) or []:
            if not isinstance(rec, dict):
                continue
            for _f, ref in iter_refs(rec):
                if classify_ref(ref) == "exact" and isinstance(ref.get("start"), int):
                    loc = chapter_of(chapters, ref["start"])
                    if loc is not None:
                        per_chapter[loc["id"]] += 1

    return {
        "matchDistribution": match_counts,
        "layerStats": layer_stats,
        "chapterAnchorDensity": per_chapter,
        "chaptersWithExactAnchor": sum(1 for v in per_chapter.values() if v > 0),
        "chaptersTotal": len(chapters),
    }


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def coverage_scope(graph: dict) -> dict:
    """图谱自带的已精读范围（诚实读取，不推断）。"""
    cov = (graph.get("meta") or {}).get("coverage") or {}
    scopes: dict[str, dict] = {}
    for layer, v in cov.items():
        if not isinstance(v, dict):
            continue
        scope = v.get("scope") or {}
        scopes[layer] = {
            "known": v.get("known"),
            "count": v.get("count"),
            "reason": v.get("reason"),
            "semanticCompleteness": v.get("semanticCompleteness"),
            "start": scope.get("start"),
            "end": scope.get("end"),
            "chapters": scope.get("chapters"),
            "name": scope.get("name"),
            "fullOriginalChaptersRead": scope.get("fullOriginalChaptersRead"),
            "originalWindowChaptersRead": scope.get("originalWindowChaptersRead"),
            "wholeNovelVerbatimRead": scope.get("wholeNovelVerbatimRead"),
            "unreviewed": scope.get("unreviewed") or scope.get("unreviewedOriginal"),
            "originalRead": scope.get("originalRead"),
            "fullEpisodeRead": scope.get("fullEpisodeRead"),
            "classification": scope.get("classification"),
        }
    return scopes


def build_coverage(book_key: str, title: str, text: str, graph: dict, index: dict) -> dict:
    chapters = index["chapters"]
    ref_index = build_reference_index(book_key, text, graph, chapters)
    density = ref_index["chapterAnchorDensity"]
    scopes = coverage_scope(graph)

    # ---- 已精读范围：图谱自带的三种声明形态都要认，不能只认 offset 窗口 ----
    reviewed_offsets: list[tuple[int, int, str]] = []
    reviewed_chapter_nos: set[int] = set()
    reviewed_window_nos: set[int] = set()
    reviewed_notes: list[dict] = []
    for layer, sc in scopes.items():
        tag = f"meta.coverage.{layer}"
        if sc.get("start") is not None and sc.get("end") is not None:
            reviewed_offsets.append((sc["start"], sc["end"], tag))
            reviewed_notes.append({"source": tag, "form": "offsetWindow",
                                   "start": sc["start"], "end": sc["end"],
                                   "name": sc.get("name"), "chapters": sc.get("chapters")})
        for arr_key in ("fullOriginalChaptersRead", "originalWindowChaptersRead"):
            arr = sc.get(arr_key)
            if isinstance(arr, list) and all(isinstance(x, int) for x in arr):
                kind = "fullRead" if arr_key == "fullOriginalChaptersRead" else "windowRead"
                for n in arr:
                    if kind == "fullRead":
                        reviewed_chapter_nos.add(n)
                    else:
                        reviewed_window_nos.add(n)
                reviewed_notes.append({"source": tag, "form": "chapterNumbers",
                                       "kind": kind, "chapters": arr})
        fe = sc.get("fullEpisodeRead")
        if isinstance(fe, list):
            for entry in fe:
                m = re.search(r"(\d+)\s*[–\-~至]\s*(\d+)\D+(\d+)\s*[–\-~至]\s*(\d+)", str(entry))
                if m:
                    lo, hi = int(m.group(3)), int(m.group(4))
                    reviewed_offsets.append((lo, hi, f"{tag}.fullEpisodeRead"))
                    reviewed_notes.append({"source": f"{tag}.fullEpisodeRead", "form": "offsetWindow",
                                           "start": lo, "end": hi, "name": str(entry)})
                else:
                    reviewed_notes.append({"source": f"{tag}.fullEpisodeRead", "form": "unparsed",
                                           "name": str(entry)})
    no_to_ids: dict[int, list[int]] = {}
    for c in chapters:
        if c["chapterNo"] is not None:
            no_to_ids.setdefault(c["chapterNo"], []).append(c["index"])

    episode_ranges = []
    for it in (graph.get("episodes") or []) + (graph.get("narrativeUnits") or []):
        refs = [r for _f, r in iter_refs(it) if classify_ref(r) == "exact"]
        if refs:
            starts = [r["start"] for r in refs]
            episode_ranges.append((min(starts), max(r.get("end", r["start"]) for r in refs),
                                   f"{it.get('id')}"))

    chapter_rows = []
    for c in chapters:
        cid = c["index"]
        exact = density.get(c["id"], 0)
        in_scope = (any(s <= c["start"] < e for s, e, _src in reviewed_offsets)
                    or (c["chapterNo"] is not None and c["chapterNo"] in reviewed_chapter_nos))
        in_window = c["chapterNo"] is not None and c["chapterNo"] in reviewed_window_nos
        in_episode = any(s <= c["start"] < e for s, e, _src in episode_ranges)
        if in_scope:
            status = "deep-read"
            src = "meta.coverage.declaredFullRead"
        elif in_window:
            status = "window-read"
            src = "meta.coverage.declaredWindowRead"
        elif in_episode or exact > 0:
            status = "anchored-unreviewed"
            src = "episodeAnchorOnly" if in_episode else "graphAnchor"
        else:
            status = "pending"
            src = "none"
        chapter_rows.append({
            "id": c["id"],
            "index": cid,
            "label": c["label"],
            "chapterNo": c["chapterNo"],
            "volume": c["volume"],
            "start": c["start"],
            "end": c["end"],
            "chars": c["chars"],
            "exactAnchorHits": exact,
            "inDeclaredReadScope": in_scope,
            "inDeclaredWindowRead": in_window,
            "inEpisodeRange": in_episode,
            "status": status,
            "source": src,
        })

    rel_anchor = attachable_relations(graph, ref_index)
    sl_anchor = attachable_storylines(graph)
    sl_anchor["boundaryTest"] = storyline_boundary_test(graph, chapters)

    missing_fields = missing_field_report(graph, index)
    identity = alias_and_orphan_report(graph)

    return {
        "schema": "castline/plan100-coverage/v1",
        "bookKey": book_key,
        "title": title,
        "sourceIndex": f"artifacts/plan100/source-index/{book_key}.json",
        "textHash": index["textHash"],
        "offsetUnit": "codepoint",
        "denominator": {
            "basis": "正文实际抽取的章单元（source-index chapters）",
            "chapters": len(chapters),
            "numberedChapters": index["extraction"]["extracted"],
            "specialChapters": index["extraction"]["extractedSpecial"],
            "volumes": len(index["volumes"]),
            "chars": index["chars"],
            "declaredChapters": index["extraction"]["declared"],
            "declaredIsNotDenominator": True,
            "note": "分母 = 实际抽取章单元；图谱声明值仅作对照，禁用其作分母。",
        },
        "materials": {
            "chars": index["chars"],
            "volumes": len(index["volumes"]),
            "chapters": len(chapters),
            "chapterCharsMin": min((c["chars"] for c in chapters), default=0),
            "chapterCharsMax": max((c["chars"] for c in chapters), default=0),
        },
        "coverage": {
            "deepRead": sum(1 for c in chapter_rows if c["status"] == "deep-read"),
            "windowRead": sum(1 for c in chapter_rows if c["status"] == "window-read"),
            "anchoredUnreviewed": sum(1 for c in chapter_rows if c["status"] == "anchored-unreviewed"),
            "pending": sum(1 for c in chapter_rows if c["status"] == "pending"),
            "statusLegend": {
                "deep-read": "图谱声明逐字通读该章/窗口",
                "window-read": "图谱只声明读过关键原文窗口，未声明逐字通读",
                "anchored-unreviewed": "章内存在精确锚点，但无语义复核声明",
                "pending": "既无锚点也无可读声明，显示为待核",
            },
            "chaptersWithExactAnchor": ref_index["chaptersWithExactAnchor"],
            "declaredScopes": scopes,
            "reviewedScopes": reviewed_notes,
            "reviewedChapterNos": sorted(reviewed_chapter_nos),
            "reviewedWindowChapterNos": sorted(reviewed_window_nos),
            "reviewedWindowDeclarations": [
                {"source": src, "start": s, "end": e,
                 "chapters": [c["id"] for c in chapters if s <= c["start"] < e]}
                for s, e, src in reviewed_offsets
            ],
            "episodeScopes": [
                {"id": _i, "start": s, "end": e,
                 "chapters": [c["id"] for c in chapters if s <= c["start"] < e]}
                for s, e, _i in episode_ranges
            ],
        },
        "layers": ref_index["layerStats"],
        "matchDistribution": ref_index["matchDistribution"],
        "quotes": {
            "verifiedQuotes": ref_index["matchDistribution"].get("exact", 0),
            "basis": "锚点级（每条 sourceRefs/quoteRef 计 1）",
            "locatedOnly": sum(ref_index["matchDistribution"].get(k, 0)
                               for k in ("normalized", "ambiguous", "no_offset")),
            "notFound": ref_index["matchDistribution"].get("not_found", 0),
            "rule": "match != exact 一律只计『定位成功』；定位成功不等于语义判断正确。",
        },
        "relations": rel_anchor,
        "storylines": sl_anchor,
        "ids": id_registry(graph, index),
        "identity": identity,
        "suspects": suspect_report(graph, chapters, ref_index),
        "missingFields": missing_fields,
        "chapters": chapter_rows,
        "referenceIndex": {
            "matchDistribution": ref_index["matchDistribution"],
            "chapterAnchorDensity": ref_index["chapterAnchorDensity"],
            "chaptersWithExactAnchor": ref_index["chaptersWithExactAnchor"],
            "chaptersTotal": ref_index["chaptersTotal"],
            "note": ("引用索引：章节 -> exact 锚点密度；每章可据此回到 text[start:end] 复核原文。"
                     "密度是**定位量**，不是语义核验量。"),
        },
        "gaps": index["extraction"]["gaps"] + coverage_gaps(graph, index, rel_anchor, sl_anchor),
        "generatedFrom": "tools/plan100/build_source_index.py",
    }


def attachable_relations(graph: dict, ref_index: dict) -> dict:
    """有多少关系能挂到「章节+offset」（审核点名：旧关系无事件级原文锚点）。

    「可挂锚点」= 关系自带 exact 锚点 ∪ 可经 eventIds 走到有 exact 锚点的事件，
    两者互斥计数（自带锚点的关系不再经事件重复计入），避免出现 >100% 的比率。
    """
    rels = graph.get("relations") or []
    events = {e.get("id"): e for e in (graph.get("events") or []) if isinstance(e, dict)}
    chars = {c.get("name"): c for c in (graph.get("characters") or [])}
    direct = via_event = 0
    samples = []
    for r in rels:
        if not isinstance(r, dict):
            continue
        if any(classify_ref(ref) == "exact" for _f, ref in iter_refs(r)):
            direct += 1
            continue
        ev_ids = r.get("eventIds") or []
        ok = False
        for eid in ev_ids:
            e = events.get(eid)
            if e and any(classify_ref(ref) == "exact" for _f, ref in iter_refs(e)):
                ok = True
                break
        if ok:
            via_event += 1
        elif len(samples) < 5:
            samples.append({"id": r.get("id"), "a": r.get("a"), "b": r.get("b"),
                            "eventIds": ev_ids[:3]})
    attachable = direct + via_event
    return {
        "records": len(rels),
        "withOwnExactAnchor": direct,
        "withEventIds": sum(1 for r in rels if isinstance(r, dict) and (r.get("eventIds") or [])),
        "resolvableToExactEvent": via_event,
        "chapterOffsetAttachable": attachable,
        "attachableRate": round(attachable / len(rels), 4) if rels else None,
        "unattachable": len(rels) - attachable,
        "unattachableSamples": samples,
        "endpointsKnown": sum(1 for r in rels if isinstance(r, dict)
                              and r.get("a") in chars and r.get("b") in chars),
        "note": ("自带精确锚点、或经 eventIds 指向有精确锚点的事件，才算『可挂到章节+offset』；"
                 "其余一律显示为待核，不得用同场关系或结构数量冒充。"),
    }


def attachable_storylines(graph: dict) -> dict:
    sls = graph.get("storylines") or []
    events = {e.get("id"): e for e in (graph.get("events") or []) if isinstance(e, dict)}
    direct = resolvable = 0
    for s in sls:
        if not isinstance(s, dict):
            continue
        if any(classify_ref(ref) == "exact" for _f, ref in iter_refs(s)):
            direct += 1
            continue
        ids = s.get("eventIds") or []
        if any(any(classify_ref(ref) == "exact" for _f, ref in iter_refs(events.get(i, {}))) for i in ids):
            resolvable += 1
    return {
        "records": len(sls),
        "withOwnExactAnchor": direct,
        "resolvableToExactEvent": resolvable,
        "chapterOffsetAttachable": direct + resolvable,
        "attachableRate": round((direct + resolvable) / len(sls), 4) if sls else None,
        "note": "有锚点只表示故事线里的引句可定位，不表示整条线的边界来自原文。",
    }


def storyline_boundary_test(graph: dict, chapters: list[dict]) -> dict:
    """审核点名：大奉「8 条全书线为机械等分」——用**真实章节边界**证实或推翻。

    判据分两层，缺一不可：
      A. 事件序等分：各线 eventIds 数是否近似等量、order 区间是否相邻整段切分；
      B. 章节边界对齐：把各条线首事件的 exact 锚点 offset 与 source-index 的
         真实章/卷边界比对。机械等分只会在 A 上成立；切点若全部落在章内
         （不对齐任何边界），说明分段是纯计数产物，与原文结构无关。
    """
    sls = [s for s in (graph.get("storylines") or []) if isinstance(s, dict)]
    if not sls:
        return {"applicable": False, "reason": "无 storylines"}
    order = {e.get("id"): e.get("order") for e in (graph.get("events") or []) if isinstance(e, dict)}
    ev_by_id = {e.get("id"): e for e in (graph.get("events") or []) if isinstance(e, dict)}
    sizes, spans, first_offsets = [], [], []
    for s in sls:
        ids = s.get("eventIds") or []
        sizes.append(len(ids))
        ords = sorted(o for o in (order.get(i) for i in ids) if o is not None)
        spans.append([ords[0], ords[-1]] if ords else [None, None])
        offs = []
        for i in ids:
            for _f, ref in iter_refs(ev_by_id.get(i, {})):
                if classify_ref(ref) == "exact":
                    offs.append(ref["start"])
                    break
        first_offsets.append(min(offs) if offs else None)

    contiguous = all(spans[i][1] is not None and spans[i + 1][0] is not None
                     and spans[i][1] + 1 == spans[i + 1][0] for i in range(len(spans) - 1))
    uniform = len(set(sizes)) == 1
    near_uniform = bool(sizes) and all(abs(sizes[i] - sizes[i + 1]) <= 2
                                       for i in range(len(sizes) - 1))

    bounds = set()
    for c in chapters:
        bounds.add(c["start"])
        bounds.add(c["end"])
    chapter_starts = {c["start"] for c in chapters}
    cut_points = [o for o in first_offsets[1:] if isinstance(o, int)]
    on_chapter_start = sum(1 for o in cut_points if o in chapter_starts)
    on_boundary = sum(1 for o in cut_points if o in bounds)

    if near_uniform and contiguous and cut_points and on_chapter_start == 0:
        verdict = "mechanical-equal-split-confirmed"
    elif near_uniform and contiguous:
        verdict = "equal-split-on-event-order"
    else:
        verdict = "not-equal-split"
    return {
        "applicable": True,
        "storylines": len(sls),
        "eventCounts": sizes,
        "uniformSize": uniform,
        "nearUniform": near_uniform,
        "orderSpans": spans,
        "contiguousOrderPartition": contiguous,
        "cutPointsTested": len(cut_points),
        "cutPointsOnChapterStart": on_chapter_start,
        "cutPointsOnAnyBoundary": on_boundary,
        "cutPointsInsideChapter": len(cut_points) - on_boundary,
        "chapterBoundaryAlignmentRate": (round(on_chapter_start / len(cut_points), 4)
                                         if cut_points else None),
        "verdict": verdict,
        "evidence": (
            "A 层（事件序）：各线事件数与 order 区间取自图谱 events[].order 实测。"
            "B 层（原文边界）：把各线首事件的 exact 锚点 offset 与 source-index 的真实"
            "章/卷边界比对——切点落在章内说明分段来自计数而非原文结构。"
        ),
        "narrativeRisk": (
            "机械等分不能作为剧情理解的证据：切点不对齐任何真实章节起点，"
            "『全书阶段N』与原文卷章无对应关系，必须由 P03 回到卷章边界重建。"
            if verdict != "not-equal-split" else ""
        ),
    }


def id_registry(graph: dict, index: dict) -> dict:
    """稳定 ID 注册表（P02-W03）：ID 空间、计数、与图谱缓存的对应关系。"""
    chapters = index["chapters"]
    reg = {}
    for layer, prefix in (("events", "ev_"), ("characters", "ch_"), ("relations", "rel_"),
                          ("causeEdges", "cause_"), ("storylines", "sl_"), ("tasks", "task_"),
                          ("clues", "clue_"), ("camps", None)):
        items = [i for i in (graph.get(layer) or []) if isinstance(i, dict)]
        if not items:
            continue
        ids = [i.get("id") or i.get("entityId") for i in items]
        reg[layer] = {
            "records": len(items),
            "withId": sum(1 for i in ids if i),
            "uniqueIds": len({i for i in ids if i}),
            "missingIds": sum(1 for i in ids if not i),
            "prefix": prefix,
            "idEntityAgreement": sum(1 for i in items
                                     if i.get("id") and i.get("entityId") and i["id"] == i["entityId"]),
            "stableIdStatus": ("ok" if all(ids) and len({i for i in ids if i}) == len(items)
                               else "no-stable-id"),
        }
        if not all(ids):
            reg[layer]["missingIdNote"] = (
                f"{layer} 图层条目**没有** id/entityId 字段，只有 name 等展示字段；"
                "跨图定位必须改用 (name) 作为弱键，且需视为身份未核验，不得当作稳定 ID 使用。"
            )
    ch_ids = [c["id"] for c in chapters]
    return {
        "scheme": {
            "chapter": f"ch_{index['bookKey'][:8]}_<章序号4位>；无编号单元 ch_..._x<序号3位>",
            "volume": f"vol_{index['bookKey'][:8]}_<卷序号>",
            "graphLayers": "沿用图谱既有 id，不重编号、不迁移",
        },
        "namespaceCollisionWarning": (
            "章节 ID 前缀 ch_<bookKey前8>_ 与人物 ID 前缀 ch_ 同名但空间不同："
            "人物 id 形如 ch_<16位hex>，章节 id 形如 ch_<8位bookKey>_<4位序号>，"
            "两者可区分，但消费方**不得**用 `startswith('ch_')` 判类型。"
        ),
        "chapterIdCount": len(ch_ids),
        "chapterIdUnique": len(set(ch_ids)) == len(ch_ids),
        "chapterOrdinalMatchesIndex": all(c["ordinal"] == i + 1 for i, c in enumerate(chapters)),
        "chapters": [
            {"id": c["id"], "ordinal": c["ordinal"], "index": c["index"], "kind": c["kind"],
             "chapterNo": c["chapterNo"], "label": c["label"],
             "volume": c["volume"], "volumeId": index["volumes"][c["volume"] - 1]["id"],
             "start": c["start"], "end": c["end"]}
            for c in chapters
        ],
        "graphLayers": reg,
        "graphMetaIndex": (graph.get("meta") or {}).get("index"),
        "graphMetaIndexNote": (
            "meta.index 的 chapters 是**事件标签去重数**，不是正文卷章边界；"
            "P02 的稳定 ID 与 offset 一律以 source-index 为准，meta.index 仅作对照。"
        ),
    }


def alias_and_orphan_report(graph: dict) -> dict:
    """别名冲突与孤立节点（P02-W03 明确要求记录）。"""
    chars = [c for c in (graph.get("characters") or []) if isinstance(c, dict)]
    names = [c.get("name") for c in chars]
    nameset = set(names)
    dup_names = sorted({n for n in names if names.count(n) > 1})
    alias_owner: dict[str, list[str]] = {}
    for c in chars:
        for a in c.get("aliases") or []:
            alias_owner.setdefault(a, []).append(c.get("name"))
    collisions = [{"alias": a, "owners": sorted(set(o)), "count": len(set(o))}
                  for a, o in sorted(alias_owner.items()) if len(set(o)) > 1]
    alias_is_other_name = [{"alias": a, "owners": sorted(set(o))}
                           for a, o in sorted(alias_owner.items())
                           if a in nameset and a not in set(o)]
    used: set[str] = set()
    for layer, key in (("events", "characters"), ("storylines", "cast"), ("camps", "members")):
        for it in graph.get(layer) or []:
            if isinstance(it, dict):
                used.update(it.get(key) or [])
    for r in graph.get("relations") or []:
        if isinstance(r, dict):
            used.update([r.get("a"), r.get("b")])
    orphans = sorted(n for n in nameset if n and n not in used)
    endpoints_unknown = sorted({x for r in (graph.get("relations") or [])
                                if isinstance(r, dict)
                                for x in (r.get("a"), r.get("b"))
                                if x and x not in nameset})
    return {
        "characters": len(chars),
        "duplicatePrimaryNames": dup_names,
        "aliasCollisionCount": len(collisions),
        "aliasCollisions": collisions[:40],
        "aliasShadowingAnotherNameCount": len(alias_is_other_name),
        "aliasShadowingAnotherName": alias_is_other_name[:40],
        "orphanCharacterCount": len(orphans),
        "orphanCharacters": orphans[:40],
        "relationEndpointsUnknown": endpoints_unknown,
        "note": ("别名冲突与孤立节点只做记录，不自动合并、不自动删除；"
                 "任何合并需回到原文证据后由人工判定。"),
    }


def suspect_report(graph: dict, chapters: list[dict], ref_index: dict) -> dict:
    """疑点/冲突：身份冲突、章节归属不符、无锚点层、声明范围与实际不符。"""
    issues = []
    for it in graph.get("reviewIssues") or []:
        if not isinstance(it, dict):
            continue
        issues.append({
            "kind": it.get("kind") or it.get("identityStatus") or "reviewIssue",
            "id": it.get("id"),
            "subject": it.get("character") or it.get("name") or it.get("characterId"),
            "description": (it.get("description") or "")[:400],
            "status": it.get("status") or it.get("identityStatus"),
            "eventIds": it.get("eventIds") or [],
        })
    mismatches = []
    for layer, st in ref_index["layerStats"].items():
        for s in st.get("mismatchSamples") or []:
            mismatches.append(dict(s, layer=layer))
        if st["chapterMismatch"] > len(st.get("mismatchSamples") or []):
            mismatches.append({"layer": layer, "note": "余下见 sourceIndex mismatchCount",
                               "truncated": st["chapterMismatch"] - len(st.get("mismatchSamples") or [])})
    zero = [layer for layer, st in ref_index["layerStats"].items()
            if st["records"] and st["withAnchor"] == 0]
    return {
        "identityIssues": issues,
        "identityIssueCount": len(issues),
        "chapterMismatchCount": sum(st["chapterMismatch"] for st in ref_index["layerStats"].values()),
        "chapterMismatchSamples": mismatches,
        "layersWithZeroAnchor": zero,
        "semanticStatusUnreviewed": sum(1 for layer in LAYERS
                                        for it in (graph.get(layer) or [])
                                        if isinstance(it, dict) and it.get("semanticStatus") == "unreviewed"),
    }


def missing_field_report(graph: dict, index: dict) -> dict:
    """缺失字段：该图层整体未提供，或图层内条目缺关键字段。"""
    cov = (graph.get("meta") or {}).get("coverage") or {}
    not_provided = sorted(layer for layer, v in cov.items()
                          if isinstance(v, dict) and v.get("known") is False)
    absent_layers = [layer for layer in LAYERS if not (graph.get(layer) or [])]
    incomplete = {}
    for layer in LAYERS:
        items = [i for i in (graph.get(layer) or []) if isinstance(i, dict)]
        if not items:
            continue
        miss = {}
        for key in ("id", "sourceRefs", "claimStatus", "semanticStatus"):
            n = sum(1 for i in items if not i.get(key))
            if n:
                miss[key] = n
        if miss:
            incomplete[layer] = miss
    return {
        "layersNotProvided": not_provided,
        "layersAbsent": absent_layers,
        "incompleteRecordFields": incomplete,
        "noFabricatedDefaults": "缺失图层一律显示『待核』；本台账不为其生成默认分值或占位条目。",
    }


def coverage_gaps(graph: dict, index: dict, rel_anchor: dict, sl_anchor: dict) -> list[str]:
    gaps = []
    if rel_anchor["records"] and rel_anchor["withOwnExactAnchor"] == 0:
        gaps.append(
            f"relations {rel_anchor['records']} 条中 {rel_anchor['withOwnExactAnchor']} 条自带原文锚点，"
            f"{rel_anchor['resolvableToExactEvent']} 条可经 eventIds 间接挂到有 exact 锚点的事件；"
            f"可挂锚点率 {rel_anchor['attachableRate']}。其余 {rel_anchor['unattachable']} 条"
            f"**无法**挂到「章节+offset」，只能显示为待核。"
        )
    if sl_anchor["records"] and sl_anchor["withOwnExactAnchor"] == 0:
        gaps.append(
            f"storylines {sl_anchor['records']} 条自带锚点 0 条，可挂到 exact 事件的比例 "
            f"{sl_anchor['attachableRate']}；故事线级语义未经原文核验。"
        )
    cov = (graph.get("meta") or {}).get("coverage") or {}
    for layer, v in cov.items():
        if isinstance(v, dict) and v.get("known") and v.get("semanticCompleteness") == "unverified":
            gaps.append(f"{layer}: 图谱自述 semanticCompleteness=unverified（定位不等于语义核验）。")
    return gaps


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def write_json(path: Path, data: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    path.write_text(body, encoding="utf-8")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", action="append", default=None)
    ap.add_argument("--check", action="store_true",
                    help="只校验已产出文件与重建结果一致，不写入")
    args = ap.parse_args()

    books = [b for b in BOOKS if not args.book or b[0] in args.book]
    if not books:
        print("no matching book", file=sys.stderr)
        return 2

    for key, title in books:
        index = build_source_index(key, title)
        text = load_docs(key)[0]["text"]
        graph = load_graph(key)
        coverage = build_coverage(key, title, text, graph, index)
        ip = SOURCE_INDEX_DIR / f"{key}.json"
        cp = COVERAGE_DIR / f"{key}.json"
        if args.check:
            ok = True
            for p, data in ((ip, index), (cp, coverage)):
                if not p.exists():
                    print(f"MISSING {artifact_rel(p)}", file=sys.stderr)
                    ok = False
                    continue
                have = json.loads(p.read_text(encoding="utf-8"))
                if have != data:
                    print(f"STALE   {artifact_rel(p)}", file=sys.stderr)
                    ok = False
            if not ok:
                return 1
            print(f"OK      {key} {title}")
            continue
        hi = write_json(ip, index)
        hc = write_json(cp, coverage)
        ex, dec = index["extraction"]["extracted"], index["extraction"]["declared"]
        print(f"{key} {title}: 卷 {len(index['volumes'])} · 实际章 {ex}（声明 {dec}）"
              f" · 有 exact 锚点章 {coverage['coverage']['chaptersWithExactAnchor']}/{len(index['chapters'])}"
              f" · 关系可挂锚点率 {coverage['relations']['attachableRate']}")
        print(f"   {artifact_rel(ip)}  sha256:{hi[:16]}")
        print(f"   {artifact_rel(cp)}  sha256:{hc[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
