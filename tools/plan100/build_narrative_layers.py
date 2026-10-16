#!/usr/bin/env python3
"""P04 叙事层构建器：因果边 / 伏笔生命周期 / 人物状态相变 / 信息差 / 关系锚点。

设计约束（来自计划与简报，逐条对应代码）：
  1. 禁止以时间相邻替代因果 —— 每条因果边必须由原文中的**显式因果连接词**锚定，
     `from` / `to` 端点在该连接词前后各自唯一可定位；同场、先后、共现一律不计为因果。
  2. 不得虚构引文 —— 所有 quote 都经 `text[start:end] == quote` 逐字验证后才写入，
     否则降级为 `unverified` 并保留在 `unverifiedAnchors` 里（**不删除**）。
  3. 四态证据标记必须保留：`explicit` / `inferred` / `derived` / `unverified`。
     四态映射到既有 `basis` 字段（前端已消费 explicit/synthesis/inference/unverified），
     同时保留 P04 原生的 `evidenceState`。
  4. `match != exact` 不得计为「已核验引句」，只能计「定位成功」——本脚本分开统计。
  5. 身份冲突不自动归并 —— 命中 reviewIssues 的人物对进待审队列，不出确定性结论。
  6. 同场不得升格为师徒/盟友/敌对 —— 关系缺事件级断言时明确标注
     `claimTier = "co_presence_only"`，并写明「无事件级锚点，仅为同场推导」。

不修改 data/。只读缓存，写 artifacts/plan100/narrative/。

用法：
    python3 tools/plan100/build_narrative_layers.py                 # 三书全量
    python3 tools/plan100/build_narrative_layers.py --book df959... # 单本
    python3 tools/plan100/build_narrative_layers.py --self-test     # 内建反例自检
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from bisect import bisect_left
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
sys.path.insert(0, str(ROOT / "tools" / "plan100"))

from evidence_audit import build_chapter_index, cn_to_int, locate

OUT_DIR = artifact_path() / "plan100" / "narrative"
SOURCE_INDEX_DIR = ROOT / "tests" / "fixtures" / "contracts" / "source-index"

SCHEMA_VERSION = "plan100/narrative-layers/1"
GENERATOR = "tools/plan100/build_narrative_layers.py"

BOOKS = [
    ("9b676d7031b1bcd3b8377a18", "大奉打更人"),
    ("df959d743e53206f56db2f92", "西游记"),
    ("152e2a6eed94f1075e7e7070", "三国演义"),
]

# ---------------------------------------------------------------- 四态证据标记

BASIS_OF_STATE = {
    "explicit": "explicit",
    "inferred": "synthesis",
    "derived": "inference",
    "unverified": "unverified",
}
EVIDENCE_STATES = tuple(BASIS_OF_STATE)


def basis_of(state: str) -> str:
    return BASIS_OF_STATE[state]


# ---------------------------------------------------------------- 文本工具

CAUSAL_MARKERS_STRONG = (
    "因此", "所以", "致使", "以致", "因而", "故而", "故此",
    "从而", "导致", "以至于", "于是",
)
CAUSAL_MARKERS_WEAK = ("遂", "故")
CAUSAL_MARKERS_EXCLUDED = {"乃": "文言判断词（是/就是），抽样多为身份定义，非因果"}
CAUSAL_MARKERS = CAUSAL_MARKERS_STRONG + CAUSAL_MARKERS_WEAK

_WEAK_COMPOUNDS = {
    "故": (
        "故人", "故意", "缘故", "无故", "故事", "故土", "故乡", "故友", "故旧",
        "故去", "故世", "故交", "故里", "借故", "托故", "何故", "如故",
        "故纸", "典故", "变故", "故态", "故伎", "故迹", "故园", "故国", "故宅",
        "世故",
        "亲非故",
        "非故",
        "带故",
        "自由故",
        "故作",
        "故弄",
        "故步",
        "之故",
        "有故",
        "甚故",
    ),
    "遂": (
        "遂心", "遂意", "遂愿", "未遂", "顺遂", "遂字", "毛遂",
    ),
}
_SHIPU_NOUN_HEADS = frozenset("意人事乡土里友旧交知去世园国宅步弄")


def _weak_occurrences(text: str, mk: str, drop: dict):
    """产出单字连接词 `mk` 的**合法**出现位置；词内的计入 `drop`（由调用方持有）。

    整词判定：任一所列复合词覆盖该位置时丢弃并记账。

    记账**必须由调用方持有**：本函数被多处调用（两个匹配点 + 候选计数），
    若写成模块级累加器会被重复计数（实测放大 3 倍，且跨书累积到 23 倍）。
    """
    compounds = _WEAK_COMPOUNDS.get(mk, ())
    n = len(mk)
    for m in re.finditer(re.escape(mk), text):
        pos = m.start()
        if mk == "故" and text[max(0, pos - 1):pos] == "是":
            nxt = text[pos + 1:pos + 2]
            if nxt in _SHIPU_NOUN_HEADS:
                drop["count"] += 1
                k2 = "故←是故+" + nxt
                drop["detail"][k2] = drop["detail"].get(k2, 0) + 1
                continue
            yield pos
            continue
        win = text[max(0, pos - 2): pos + n + 2]
        hit = next((c for c in compounds if c in win), None)
        if hit:
            drop["count"] += 1
            key = mk + "←" + hit
            drop["detail"][key] = drop["detail"].get(key, 0) + 1
            continue
        yield pos


def causal_marker_spans(text: str, drop: dict | None = None):
    """产出所有**合法**的连接词位置 `(start, marker, strength)`。

    多字连接词直接子串匹配；单字连接词走整词判定（`_weak_occurrences`）。
    `drop` 传入时收集剔除记账；**不传则不记账**（纯遍历场景，避免重复计数）。
    """
    for mk in CAUSAL_MARKERS:
        strength = "strong" if mk in CAUSAL_MARKERS_STRONG else "weak"
        if strength == "strong":
            for m in re.finditer(re.escape(mk), text):
                yield m.start(), mk, strength
        else:
            sink = drop if drop is not None else {"count": 0, "detail": {}}
            for pos in _weak_occurrences(text, mk, sink):
                yield pos, mk, strength


WEAK_SUPPORT = (
    "因", "由", "缘", "罪", "怒", "惧", "恐", "惊",
    "计", "谋", "议", "请", "命", "令", "遣", "使", "失", "败",
    "胜", "破", "杀", "斩", "降", "叛", "逃", "走", "追", "救", "攻",
    "取", "夺", "立", "废", "封", "赏", "罚", "报", "仇", "误", "诈",
)

VERSE_OPENERS = ("后人有诗", "诗曰", "正是：", "赞曰", "有诗叹曰", "史官有诗",
                 "后人有诗叹曰", "有诗赞曰", "但见", "怎见得", "未知", "且看下文",
                 "且听下回", "毕竟", "话表", "却说")

AUTHOR_NOTE_OPENERS = ("PS：", "ps：", "PS:", "ps:", "作者的话", "求月票", "求推荐",
                       "本章完", "感谢", "推荐票", "月票")

VERSE_SCAN = 420

DISTANCE_PASS_BOUND = 600

SENT_BREAK = "。！？!?\n"
CLAUSE_BREAK = "，。！？；：,;!?\n“”「」（）()《》〈〉…—"

WS_RE = re.compile(r"[\s\u3000]+")
PUNCT_RE = re.compile(r"[\s\u3000，。！？；：、“”‘’（）《》〈〉·…—～!?,.;:()\[\]{}<>/\\|\"']+")


def norm(s: str) -> str:
    """比较用归一化：只去排版噪声，不改原文。"""
    return WS_RE.sub("", s or "")


def nfkc_norm(s: str) -> str:
    return PUNCT_RE.sub("", unicodedata.normalize("NFKC", str(s or ""))).lower()


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def stable_id(kind: str, *parts) -> str:
    raw = json.dumps([str(p) for p in parts], ensure_ascii=False, separators=(",", ":"))
    return f"{kind}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


# ---------------------------------------------------------------- Aho-Corasick

class AhoCorasick:
    """多模式一次扫描；30 万字级正文需要它，纯 Python 逐模式 find 太慢。"""

    def __init__(self, words):
        self.goto = [{}]
        self.fail = [0]
        self.out = [[]]
        for w in words:
            if not w:
                continue
            s = 0
            for ch in w:
                nxt = self.goto[s].get(ch)
                if nxt is None:
                    self.goto.append({})
                    self.fail.append(0)
                    self.out.append([])
                    nxt = len(self.goto) - 1
                    self.goto[s][ch] = nxt
                s = nxt
            self.out[s].append(w)
        q = deque(self.goto[0].values())
        while q:
            r = q.popleft()
            for ch, s in self.goto[r].items():
                q.append(s)
                f = self.fail[r]
                while f and ch not in self.goto[f]:
                    f = self.fail[f]
                self.fail[s] = self.goto[f].get(ch, 0)
                if self.out[self.fail[s]]:
                    self.out[s] = self.out[s] + self.out[self.fail[s]]

    def find(self, text):
        s = 0
        goto, fail, out = self.goto, self.fail, self.out
        for i, ch in enumerate(text):
            while s and ch not in goto[s]:
                s = fail[s]
            s = goto[s].get(ch, 0)
            if out[s]:
                for w in out[s]:
                    yield i - len(w) + 1, w

    def longest_at(self, text, pos):
        """返回恰好在 pos 起始的最长匹配（用于解决「刘备」vs「刘备受」类子串包含）。"""
        best = None
        s = 0
        for i in range(pos, len(text)):
            ch = text[i]
            while s and ch not in self.goto[s]:
                s = self.fail[s]
            s = self.goto[s].get(ch, 0)
            if not s:
                break
            if self.out[s]:
                best = max(self.out[s], key=len)
        return best


# ---------------------------------------------------------------- 章节索引

def chapter_source(book_key: str) -> str:
    """返回章节索引来源标识；P02 就绪则用 P02，否则回退审计脚本实现。"""
    p = SOURCE_INDEX_DIR / f"{book_key}.json"
    if p.exists():
        return "p02-source-index"
    return "evidence_audit.build_chapter_index"


def build_chapters(book_key: str, text: str) -> tuple[list[dict], str]:
    """优先消费 P02 契约；P02 未就绪时回退并如实标注。"""
    p = SOURCE_INDEX_DIR / f"{book_key}.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            chapters = [
                {"num": cn_to_int(c.get("label") or "") or c.get("index"),
                 "heading": c.get("heading") or c.get("label") or "",
                 "start": int(c["start"])}
                for c in data.get("chapters") or []
                if isinstance(c, dict) and isinstance(c.get("start"), int)
            ]
            if chapters:
                chapters.sort(key=lambda c: c["start"])
                return chapters, "p02-source-index"
        except Exception:
            pass
    raw = build_chapter_index(text)
    chapters = [{"num": c["num"], "heading": c["heading"], "start": c["start"]} for c in raw]
    return chapters, "evidence_audit.build_chapter_index"


def chapter_at(chapters: list[dict], offset: int) -> dict | None:
    return locate(chapters, offset)


def chapter_span(chapters: list[dict], offset: int) -> tuple[int, int, dict | None]:
    c = chapter_at(chapters, offset)
    if c is None:
        return 0, 0, None
    i = chapters.index(c)
    end = chapters[i + 1]["start"] if i + 1 < len(chapters) else None
    return c["start"], end, c


# ---------------------------------------------------------------- 锚点

class Anchors:
    """已核验引句索引。

    每条事件可贡献**多个**逐字锚点：除了 `quoteRef`，事件的 `sourceRefs` /
    `contextRefs` 同样在原文里逐字核验过。只取 quoteRef 会让三国 434 条事件
    只剩 319 个落点，大量真实因果端点因「因区没有锚点」被误判为不可判定。
    这里纳入所有经 `text[start:end] == quote` 复核的锚点。
    """

    def __init__(self, events: list[dict], text: str):
        self.text = text
        self.exact: list[tuple[int, int, str]] = []
        self.primary: list[tuple[int, int, str]] = []
        self.by_event: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
        seen: set[tuple[int, int, str]] = set()
        for e in events:
            quote_ref = e.get("quoteRef")
            refs: list[tuple[dict, bool]] = []
            for field in ("quoteRef", "sourceRefs", "contextRefs"):
                v = e.get(field)
                if isinstance(v, dict):
                    refs.append((v, field == "quoteRef"))
                elif isinstance(v, list):
                    refs.extend((x, False) for x in v if isinstance(x, dict))
            for ref, is_primary in refs:
                got = self._check(ref)
                if not got:
                    continue
                key = (got[0], got[1], e["id"])
                if key in seen:
                    continue
                seen.add(key)
                self.exact.append(key)
                self.by_event[e["id"]].append(key)
                if is_primary or (isinstance(quote_ref, dict)
                                  and ref.get("quote") == quote_ref.get("quote")):
                    self.primary.append(key)
        self.exact.sort()
        self.primary.sort()
        self._starts = [a[0] for a in self.exact]
        self.event_count = len(self.by_event)

    def _check(self, ref) -> tuple[int, int] | None:
        s, en, q = ref.get("start"), ref.get("end"), ref.get("quote")
        if not (isinstance(s, int) and isinstance(en, int)) or not isinstance(q, str):
            return None
        if 0 <= s < en <= len(self.text) and self.text[s:en] == q:
            return s, en
        return None

    def nearest_before(self, pos: int, window: int):
        """marker 之前、**整段都落在 marker 之前**的最近事件；count 为同一因区内
        可竞争的事件数（>1 表示因区不唯一，该边必须弃用）。"""
        i = bisect_left(self._starts, pos) - 1
        if i >= 0:
            a = self.exact[i]
            if a[1] <= pos and pos - a[1] <= window:
                return a, sum(1 for x in self.exact[: i + 1]
                              if x[0] >= pos - window and x[1] <= pos)
        return None, 0

    def nearest_after(self, pos: int, window: int):
        """marker 之后、**整段都落在 marker 之后**的最近事件。"""
        i = bisect_left(self._starts, pos)
        if i < len(self.exact):
            a = self.exact[i]
            if a[0] >= pos and a[0] - pos <= window:
                return a, sum(1 for x in self.exact[i:]
                              if x[0] >= pos and x[0] <= a[0] + window)
        return None, 0

    def covers(self, start: int, end: int) -> list[tuple[int, int, str]]:
        """落在 [start,end) 区间内、且整段被区间包含的事件锚点。"""
        i = bisect_left(self._starts, start)
        out = []
        while i < len(self.exact) and self.exact[i][0] < end:
            a = self.exact[i]
            if a[1] <= end:
                out.append(a)
            i += 1
        return out


def sentence_bounds(text: str, pos: int) -> tuple[int, int]:
    a = pos
    while a > 0 and text[a - 1] not in SENT_BREAK:
        a -= 1
    b = pos
    n = len(text)
    while b < n and text[b] not in SENT_BREAK:
        b += 1
    return a, min(b + 1, n)


def causal_scope(text: str, marker_start: int, marker_len: int, anchors, max_chars: int):
    """因果连接词在原文中的辖域（scope）—— 由**原文**决定，不是取最近邻事件。

    中文小说的因果连接词有三种真实位置，必须分别判定：
      - same_sentence：连接词句内，因在前、果在后 ——「A，因此B」。
      - preceding_sentence：连接词开启新句，因落在紧邻的上一句 ——「A。因此B。」
      - across_sentences：因/果各自需要向邻句扩展才落到**唯一**事件上。
        这是真实叙事里最常见的形态（因是一段叙述，果是下一句动作）。
        扩展是有界的（max_chars），且扩展后因区/果区各自仍必须**唯一**，
        否则该连接词不足以判定端点，整条弃用（不猜）。

    返回 (span_start, span_end, span_kind, cause_boundary) 或 None。
    """
    sent_a, sent_b = sentence_bounds(text, marker_start)
    marker_end = marker_start + marker_len
    cause_hi = marker_start
    cause_lo = sent_a
    effect_hi = sent_b

    def zone(lo, hi, exclude=frozenset()):
        got = [a for a in anchors.covers(lo, hi) if a[2] not in exclude]
        ids = {a[2] for a in got}
        return got, ids

    head = text[sent_a:marker_start]
    if not head.strip(CLAUSE_BREAK + " \u3000\t") and sent_a > 0:
        prev_a, prev_b = sentence_bounds(text, sent_a - 1)
        if prev_b >= sent_a and prev_b > prev_a:
            cause_lo = prev_a
    kind = "preceding_sentence" if cause_lo < sent_a else "same_sentence"

    got_c, ids_c = zone(cause_lo, cause_hi)
    got_e, ids_e = zone(cause_hi, effect_hi, exclude=ids_c)
    if len(ids_c) == 1 and len(ids_e) == 1 and ids_c != ids_e:
        return cause_lo, effect_hi, kind, marker_start

    expanded = False
    while (len(ids_e) != 1 or not ids_e) and effect_hi - marker_start < max_chars:
        nxt = sentence_bounds(text, effect_hi)[1] if effect_hi < len(text) else effect_hi
        if nxt <= effect_hi:
            break
        effect_hi = nxt
        got_e, ids_e = zone(cause_hi, effect_hi, exclude=ids_c)
        expanded = True
    while (len(ids_c) != 1 or not ids_c) and cause_hi - cause_lo < max_chars and cause_lo > 0:
        prev_a, _ = sentence_bounds(text, cause_lo - 1)
        if prev_a >= cause_lo:
            break
        cause_lo = prev_a
        got_c, ids_c = zone(cause_lo, cause_hi)
        expanded = True
    if len(ids_c) == 1 and len(ids_e) == 1 and ids_c != ids_e:
        return cause_lo, effect_hi, ("across_sentences" if expanded else kind), marker_start
    return None


def tag_ref(quote: str, start: int, end: int, text: str, source: dict,
            chapter: dict | None, match: str) -> dict:
    return {
        "sourceId": source["sourceId"],
        "sourcePath": source["sourcePath"],
        "offsetUnit": "codepoint",
        "start": start,
        "end": end,
        "chapterIndex": chapter.get("num") if chapter else None,
        "chapterLabel": chapter.get("heading") if chapter else None,
        "quote": quote,
        "match": match,
        "verified": match == "exact",
        "locatorOnly": match != "exact",
        "textHash": source["textHash"],
    }


# ---------------------------------------------------------------- 因果边

CAUSE_ENTITY_HINT = {
    "转折": 1.0, "冲突": 0.9, "抉择": 0.9, "智谋": 0.9, "智取": 0.85,
    "高燃": 0.7, "关系": 0.6, "领悟": 0.6, "日常": 0.35, "情感": 0.5,
    "智斗": 0.9, "伏笔": 0.8,
}


def verse_regions(text: str) -> list[tuple[int, int]]:
    """诗词 / 赞语 / 回末套语 / 作者附言区间。

    这些区间里的「故/乃/遂」是修辞、身份定义或场外话，不是事件因果。
    区间从套语标记起算，到下一个空行结束（有界），避免吞掉真正的叙事。
    """
    out = []
    for opener in VERSE_OPENERS + AUTHOR_NOTE_OPENERS:
        for m in re.finditer(re.escape(opener), text):
            s = m.start()
            e = min(len(text), s + VERSE_SCAN)
            nl = text.find("\n\n", s)
            if nl > 0:
                e = min(e, nl + 1)
            out.append((s, e))
    out.sort()
    merged = []
    for s, e in out:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def in_regions(regions, start: int, end: int) -> bool:
    for s, e in regions:
        if s <= start < e or s < end <= e:
            return True
    return False


def classify_scope_failure(text, marker_start, marker_len, anchors, window) -> str:
    """区分「因区没有锚点」「果区没有锚点」「因区多义」「果区多义」。

    这是审核要看的缺口成因 —— 只有知道是哪一类，才知道下一步补什么。
    """
    sent_a, sent_b = sentence_bounds(text, marker_start)
    cause_lo, cause_hi = sent_a, marker_start
    effect_hi = sent_b
    while effect_hi - marker_start < window and effect_hi < len(text):
        nxt = sentence_bounds(text, effect_hi)[1]
        if nxt <= effect_hi:
            break
        effect_hi = nxt
        if {a[2] for a in anchors.covers(marker_start, effect_hi)}:
            break
    lo = cause_lo
    while cause_hi - lo < window and lo > 0:
        pa, _ = sentence_bounds(text, lo - 1)
        if pa >= lo:
            break
        lo = pa
        if {a[2] for a in anchors.covers(lo, cause_hi)}:
            break
    nc = len({a[2] for a in anchors.covers(lo, cause_hi)})
    ne = len({a[2] for a in anchors.covers(marker_start, effect_hi)})
    if nc == 0 and ne == 0:
        return "both_zones_without_anchor"
    if nc == 0:
        return "cause_zone_without_anchor"
    if ne == 0:
        return "effect_zone_without_anchor"
    return "multiple_candidates_in_zone"


def add_distance_bounded_pass(text, anchors, by_id, order_of, regions, edges,
                              max_distance, scope_fail):
    """第二遍：距离上界的唯一性绑定（**限同章**）。

    第一遍（causal_scope）要求「因区/果区」是原文句法辖域，最严格但覆盖率低 ——
    实测三国 3963 个连接词只有 19 个能过，瓶颈是**锚点密度**（319 个锚点 / 60 万字），
    不是规则本身。

    本遍在不放弃唯一性的前提下放宽距离，并加两条硬约束：
      1. 前后件必须**同章**。跨章绑定实测会把连接词绑到别的场景（大奉出现
         「PS：求月票」被绑成因果边），那不是因果，是章节邻近。
      2. 前后件的事件序不得倒挂。
    仍然满足「禁止以时间相邻替代因果」：它不是「取相邻事件」，而是要求
    原文给出的因果连接词 + 两端唯一可定位 + 同章 + 距离有界。
    本遍产出**最高只能到 inferred**，永不写 explicit（距离越远证据越弱）。
    """
    added = 0
    chapter_of = {}
    for eid in by_id:
        chapter_of[eid] = (by_id[eid] or {}).get("chapter")
    _weak_drop = {"count": 0, "detail": {}}
    try:
        scope_fail["_weak_drop"] = _weak_drop
    except Exception:
        pass
    for p, mk, strength in causal_marker_spans(text, _weak_drop):
        if True:
            if in_regions(regions, max(0, p - 120), p + 120):
                continue
            frm, nf = anchors.nearest_before(p, max_distance)
            to, nt = anchors.nearest_after(p + len(mk), max_distance)
            if not frm or not to or frm[2] == to[2]:
                continue
            if nf != 1 or nt != 1:
                scope_fail["distance_pass_not_unique"] += 1
                continue
            if chapter_of.get(frm[2]) != chapter_of.get(to[2]):
                scope_fail["distance_pass_cross_chapter"] += 1
                continue
            key = (frm[2], to[2])
            if key in edges:
                continue
            of, ot = order_of.get(frm[2]), order_of.get(to[2])
            if isinstance(of, int) and isinstance(ot, int) and ot < of:
                scope_fail["distance_pass_backward_order"] += 1
                continue
            support = ""
            if strength == "weak":
                zone_text = text[max(0, frm[1] - 40):p]
                support = next((w for w in WEAK_SUPPORT if w in zone_text), "")
                if not support:
                    scope_fail["distance_pass_weak_unsupported"] += 1
                    continue
            edges[key] = {
                "key": key, "marker": mk, "markerStrength": strength, "weakSupport": support,
                "markerStart": p, "quoteStart": frm[0], "quoteEnd": to[1],
                "quote": text[frm[0]:to[1]], "spanKind": "distance_bounded",
                "causeEnd": p, "causeDistance": p - frm[1], "effectDistance": to[0] - (p + len(mk)),
                "fromEventId": frm[2], "toEventId": to[2], "score": 0.5,
                "pass": "distance_bounded",
            }
            added += 1
    return added


def build_causal(book_key, title, graph, text, chapters, anchors, window, existing_ids):
    events = [e for e in graph.get("events") or [] if isinstance(e, dict)]
    by_id = {e["id"]: e for e in events}
    order_of = {e["id"]: e.get("order") for e in events}
    source = source_meta(graph, book_key)
    regions = verse_regions(text)
    edges: dict[tuple[str, str], dict] = {}
    rejected_same_scene = 0
    rejected_chain = 0
    rejected_unclear = 0
    rejected_no_scope = 0
    rejected_weak_unsupported = 0
    rejected_verse = 0
    rejected_backward = 0
    scope_fail = Counter()

    for p, mk, strength in causal_marker_spans(text):
        if True:
            scope = causal_scope(text, p, len(mk), anchors, window)
            if scope is None:
                rejected_unclear += 1
                reason = classify_scope_failure(text, p, len(mk), anchors, window)
                scope_fail[reason] += 1
                continue
            sent_a, sent_b, span_kind, boundary = scope
            sentence = text[sent_a:sent_b]
            if len(sentence) < 8:
                rejected_same_scene += 1
                continue
            if in_regions(regions, sent_a, sent_b):
                rejected_verse += 1
                continue
            support = ""
            if strength == "weak":
                zone_text = text[sent_a:boundary]
                support = next((w for w in WEAK_SUPPORT if w in zone_text), "")
                if not support:
                    rejected_weak_unsupported += 1
                    continue
            cause_zone = anchors.covers(sent_a, boundary)
            effect_zone = [a for a in anchors.covers(boundary, sent_b) if a[0] >= boundary]
            if not cause_zone or not effect_zone:
                rejected_no_scope += 1
                continue
            cause_ids = {a[2] for a in cause_zone}
            effect_ids = {a[2] for a in effect_zone}
            if len(cause_ids) != 1 or len(effect_ids) != 1:
                rejected_unclear += 1
                continue
            frm = max((a for a in cause_zone), key=lambda a: a[1])
            to = min((a for a in effect_zone), key=lambda a: a[0])
            if frm[2] == to[2]:
                continue
            of, ot = order_of.get(frm[2]), order_of.get(to[2])
            if isinstance(of, int) and isinstance(ot, int) and ot < of:
                rejected_backward += 1
                continue
            ef, et = by_id.get(frm[2]), by_id.get(to[2])
            if not ef or not et:
                continue
            key = (frm[2], to[2])
            score = (CAUSE_ENTITY_HINT.get(ef.get("kind"), 0.5)
                     + CAUSE_ENTITY_HINT.get(et.get("kind"), 0.5)) / 2
            cand = {
                "key": key,
                "marker": mk,
                "markerStrength": strength,
                "weakSupport": support,
                "markerStart": p,
                "quoteStart": sent_a,
                "quoteEnd": sent_b,
                "quote": sentence,
                "spanKind": span_kind,
                "causeEnd": boundary,
                "causeDistance": boundary - frm[1],
                "effectDistance": to[0] - (boundary + len(mk)),
                "fromEventId": frm[2],
                "toEventId": to[2],
                "score": round(score, 3),
            }
            prev = edges.get(key)
            if prev is None or score > prev["score"] or (
                    score == prev["score"] and abs(p - frm[1]) < abs(prev["markerStart"] - prev["quoteStart"])):
                edges[key] = cand

    scope_pass_count = len(edges)
    distance_added = add_distance_bounded_pass(text, anchors, by_id, order_of, regions,
                                               edges, max(window, DISTANCE_PASS_BOUND),
                                               scope_fail)

    out = []
    ch_touched = set()
    for (fid, tid), c in sorted(edges.items(), key=lambda kv: kv[1]["markerStart"]):
        ef, et = by_id[fid], by_id[tid]
        ch_f = chapter_at(chapters, c["quoteStart"])
        ch_t = chapter_at(chapters, c["markerStart"])
        same_chapter = ch_f is not None and ch_t is not None and ch_f["start"] == ch_t["start"]
        in_scope_pass = c["spanKind"] in ("same_sentence", "preceding_sentence")
        if (c["markerStrength"] == "strong" and same_chapter and in_scope_pass):
            state = "explicit"
        elif not same_chapter and ef.get("chapter") != et.get("chapter"):
            state = "derived"
        else:
            state = "inferred"
        ref = tag_ref(c["quote"], c["quoteStart"], c["quoteEnd"], text, source, ch_f, "exact")
        eid = stable_id("cause", book_key, fid, tid, c["quoteStart"])
        out.append({
            "id": eid,
            "entityId": eid,
            "fromEventId": fid,
            "toEventId": tid,
            "bindTier": ("same_sentence_binding" if c["spanKind"] != "across_sentences"
                         else "bounded_scope_binding"),
            "bindPass": c.get("pass", "syntactic_scope"),
            "sourceId": fid,
            "targetId": tid,
            "declaredSourceId": fid,
            "declaredTargetId": tid,
            "description": describe_edge(ef, et, c["marker"], c["quote"]),
            "mechanism": c["marker"],
            "markerOffsetInQuote": (c["markerStart"] - c["quoteStart"]
                                    if c.get("quoteStart") is not None else None),
            "markerStrength": c["markerStrength"],
            "weakSupport": c["weakSupport"],
            "quote": c["quote"],
            "quoteRef": ref,
            "sourceRefs": [ref],
            "basis": basis_of(state),
            "evidenceState": state,
            "markerClass": "explicit_conjunction",
            "markerSpan": c["spanKind"],
            "causeBoundary": c["causeEnd"],
            "causeDistance": c["causeDistance"],
            "effectDistance": c["effectDistance"],
            "sameChapter": same_chapter,
            "fromChapter": ef.get("chapter"),
            "toChapter": et.get("chapter"),
            "fromOrder": ef.get("order"),
            "toOrder": et.get("order"),
            "orderForward": bool((ef.get("order") or 0) < (et.get("order") or 0)),
            "claimStatus": "unreviewed",
            "claimVerified": False,
            "semanticStatus": "unreviewed",
            "quoteVerified": True,
            "referenceStatus": "resolved",
            "resolved": True,
            "provenance": "deterministic-marker-extraction",
            "generator": GENERATOR,
        })
        if ch_f:
            ch_touched.add(ch_f["heading"])

    graph_info = build_causal_graph(out, by_id)
    report = {
        "extracted": len(out),
        "candidateMarkersScanned": sum(1 for _ in causal_marker_spans(text)),
            "weakMarkersDroppedAsWordInside": dict(scope_fail.get("_weak_drop", {}).get("detail", {})),
            "weakMarkersDroppedCount": scope_fail.get("_weak_drop", {}).get("count", 0),
        "rejectedAmbiguousEndpoints": rejected_unclear,
        "rejectedSameSceneOnly": rejected_same_scene,
        "rejectedNonPartitioned": rejected_chain,
        "rejectedNoScopeEndpoint": rejected_no_scope,
        "rejectedWeakMarkerWithoutSupport": rejected_weak_unsupported,
        "rejectedVerseOrFormulaRegion": rejected_verse,
        "rejectedBackwardOrder": rejected_backward,
        "scopeFailureBreakdown": dict(scope_fail),
        "syntacticScopeEdges": scope_pass_count,
        "distanceBoundedAdded": distance_added,
        "markerStrength": {
            "strong": list(CAUSAL_MARKERS_STRONG),
            "weak": list(CAUSAL_MARKERS_WEAK),
            "weakRule": "弱连接词（兼表顺承）必须另有因果性佐证词出现在因区，否则不出边。",
            "excluded": CAUSAL_MARKERS_EXCLUDED,
        },
        "existingBaselineEdges": len(existing_ids),
        "window": window,
        "chaptersTouched": len(ch_touched),
        "endpointRule": "连接词辖域内「因区」「果区」各自唯一指向一个事件；"
                        "任一区有 0 或 ≥2 个事件候选即弃用该连接词（不取最近邻）。",
    }
    carried = keep_existing_causal(graph.get("causeEdges") or [], text, anchors,
                                  chapters, source, book_key, by_id)
    report["carriedFromBaseline"] = len(carried)
    report["carriedVerified"] = sum(1 for c in carried if c["quoteVerified"])
    return out, graph_info, report, carried


def keep_existing_causal(existing, text, anchors, chapters, source, book_key, by_id):
    """复核基线因果边而不是丢弃：端点可解、引句可逐字定位的保留；否则降级标未核验。"""
    kept = []
    for i, edge in enumerate(existing or []):
        if not isinstance(edge, dict):
            continue
        rec = dict(edge)
        rec["id"] = edge.get("id") or stable_id("cause", book_key, "legacy", i)
        rec["entityId"] = rec["id"]
        frm = edge.get("fromEventId") or edge.get("sourceId") or edge.get("declaredSourceId")
        to = edge.get("toEventId") or edge.get("targetId") or edge.get("declaredTargetId")
        endpoints_ok = bool(frm and to and frm in by_id and to in by_id)
        quotes = []
        for name in ("quote",):
            v = edge.get(name)
            if isinstance(v, str) and v.strip():
                quotes.append(v.strip())
        for name in ("sourceRefs",):
            v = edge.get(name)
            for ref in (v if isinstance(v, list) else []):
                if isinstance(ref, dict) and isinstance(ref.get("quote"), str):
                    quotes.append(ref["quote"].strip())
        refs = []
        for q in dict.fromkeys(quotes):
            pos = text.find(q)
            if pos >= 0:
                ch = chapter_at(chapters, pos)
                refs.append(tag_ref(q, pos, pos + len(q), text, source, ch, "exact"))
            else:
                refs.append({
                    "sourceId": source["sourceId"], "sourcePath": source["sourcePath"],
                    "offsetUnit": "codepoint", "start": None, "end": None,
                    "chapterIndex": None, "chapterLabel": None, "quote": q,
                    "match": "not_found", "verified": False, "locatorOnly": True,
                    "textHash": source["textHash"], "reason": "quote_not_found_in_source",
                })
        rec["sourceRefs"] = refs
        rec["quoteVerified"] = bool(refs) and all(r["verified"] for r in refs)
        rec["endpointsResolved"] = endpoints_ok
        rec["carriedFromBaseline"] = True
        rec["claimStatus"] = "unreviewed"
        rec["claimVerified"] = False
        rec["semanticStatus"] = "unreviewed"
        if rec["quoteVerified"] and endpoints_ok:
            rec["evidenceState"] = edge.get("evidenceState") or "explicit"
            rec["referenceStatus"] = "resolved"
            rec["resolved"] = True
        else:
            rec["evidenceState"] = "unverified"
            rec["referenceStatus"] = "unresolved"
            rec["resolved"] = False
            rec["anchorNote"] = ("基线因果边未能完全复核："
                                 + ("端点无法解析；" if not endpoints_ok else "")
                                 + ("引句未能在原文逐字定位。" if not rec["quoteVerified"] else ""))
        rec["basis"] = basis_of(rec["evidenceState"])
        kept.append(rec)
    return kept


def describe_edge(ef, et, marker, sentence) -> str:
    """机制描述：不复述原文，说明「前件为何使后件成为可能/必然」。"""
    return (
        f"原文以「{marker}」把【{ef.get('title')}】标为【{et.get('title')}】的前件："
        f"{ef.get('summary') or ef.get('title')}；由此产生后件的条件/后果"
        f"（{et.get('summary') or et.get('title')}）。该连接词的辖域是同一句，"
        f"不代表全书只有这一条因。"
    )


def build_causal_graph(edges: list[dict], by_id: dict) -> dict:
    nodes = set()
    adj = defaultdict(list)
    radj = defaultdict(list)
    for e in edges:
        nodes.add(e["fromEventId"])
        nodes.add(e["toEventId"])
        adj[e["fromEventId"]].append(e["toEventId"])
        radj[e["toEventId"]].append(e["fromEventId"])

    index, low, onstack, stack, comps = {}, {}, {}, [], []
    counter = [0]
    for root in sorted(nodes):
        if root in index:
            continue
        work = [(root, iter(adj[root]))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        onstack[root] = True
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    stack.append(nxt)
                    onstack[nxt] = True
                    work.append((nxt, iter(adj[nxt])))
                    advanced = True
                    break
                if onstack.get(nxt):
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    onstack[w] = False
                    comp.append(w)
                    if w == node:
                        break
                comps.append(comp)

    cycles = []
    for comp in comps:
        if len(comp) > 1:
            cycles.append({"kind": "cycle", "nodes": sorted(comp)})
        else:
            n = comp[0]
            if n in adj[n]:
                cycles.append({"kind": "self_loop", "nodes": [n]})

    isolates = [n for n in sorted(nodes)
                if not adj[n] and not radj[n] and len(edges) > 1 and n not in
                {x for comp in cycles for x in comp["nodes"]}]

    return {
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "nodes": [{"eventId": n, "order": (by_id.get(n) or {}).get("order"),
                   "chapter": (by_id.get(n) or {}).get("chapter"),
                   "title": (by_id.get(n) or {}).get("title"),
                   "outDegree": len(adj[n]), "inDegree": len(radj[n])} for n in sorted(nodes)],
        "cycles": cycles,
        "cycleCount": len(cycles),
        "isolatedNodes": isolates,
        "isolatedNodeCount": len(isolates),
        "roots": sorted(n for n in nodes if not radj[n]),
        "leaves": sorted(n for n in nodes if not adj[n]),
        "maxOutDegree": max((len(adj[n]) for n in nodes), default=0),
    }


# ---------------------------------------------------------------- 伏笔生命周期

CLUE_CUES = {
    "foreshadow_object": {
        "prolepsis": ["且看下文分解", "且听下回分解", "毕竟不知", "未知如何", "毕竟如何",
                      "毕竟不知", "且看下文", "下落如何", "性命如何", "怎生结果",
                      "且听下文", "再看下文", "后文再表"],
        "prophecy": ["久后必", "他日必", "异日必", "日后必", "将来必", "他年必", "必为后患",
                     "久后定", "他日定", "日后定", "早晚必", "终必", "必当"],
        "omen": ["后来果", "后果应验", "果然应验", "暗伏", "伏下", "伏笔", "埋下",
                 "预兆", "征兆", "先兆", "此乃天意", "天数已定", "命数"],
        "vow": ["立誓", "盟誓", "发誓", "誓不", "如违此誓", "若有负", "誓当", "誓要",
                "必报此仇", "此仇不报"],
        "token": ["锦囊", "密书", "密信", "遗书", "遗命", "遗嘱", "密计", "手书",
                  "衣带诏", "令牌", "锦袋", "丹书", "铁券", "白绫", "血书"],
    },
}


def clue_kind(sentence: str) -> str | None:
    for kind, cues in CLUE_CUES["foreshadow_object"].items():
        for c in cues:
            if c in sentence:
                return kind
    return None


def build_clues(book_key, title, graph, text, chapters, anchors, events, existing):
    """伏笔生命周期：埋设 -> 强化/误导 -> 回收（或未回收）。

    埋设句是原文中**可定位的暗示句**；回收句必须是同一「线索指纹」在后续
    再次出现并被显式兑现/呼应。没有找到回收的，必须 `seeded` / `unresolved`，
    不得凭常识猜测结局。
    """
    source = source_meta(graph, book_key)
    by_id = {e["id"]: e for e in events}
    out = []
    unresolved = []
    seen_sent = set()

    for m in re.finditer(r"[^。！？!?\n]{6,240}", text):
        s, e = m.start(), m.end()
        sentence = text[s:e]
        kind = clue_kind(sentence)
        if kind is None:
            continue
        key = nfkc_norm(sentence)
        if len(key) < 6 or key in seen_sent:
            continue
        seen_sent.add(key)
        frm, nf = anchors.nearest_before(s, 400)
        to, nt = anchors.nearest_after(e, 400)
        if not frm:
            continue
        ch = chapter_at(chapters, s)
        ref = tag_ref(sentence, s, e, text, source, ch, "exact")
        seed_ev = by_id.get(frm[2])
        payoff = find_payoff(text, s, sentence, kind, events, anchors, chapters, source)
        state = "explicit"
        record = {
            "id": stable_id("clue", book_key, s),
            "entityId": stable_id("clue", book_key, s),
            "name": f"{kind}·{sentence[:24]}",
            "clueType": kind,
            "summary": f"原文在《{seed_ev.get('chapter') if seed_ev else '?'}》"
                       f"{'埋设' if payoff.get('found') else '出现暗示'}的{kind}；"
                       f"{'并在后续被呼应' if payoff.get('found') else '本轮未在原文中找到兑现句'}。",
            "seedEventId": frm[2],
            "seedQuote": sentence,
            "seedRef": ref,
            "seedChapter": ch.get("heading") if ch else None,
            "reinforceRefs": [],
            "misleadRefs": [],
            "payoffEventId": payoff.get("eventId") or "",
            "payoffQuote": payoff.get("quote") or "",
            "payoffRef": payoff.get("ref"),
            "status": "resolved" if payoff.get("found") else "seeded",
            "lifecycle": ["seeded"] + (["reinforced"] if payoff.get("reinforced") else [])
                         + (["paid_off"] if payoff.get("found") else []),
            "sourceRefs": [ref] + ([payoff["ref"]] if payoff.get("ref") else []),
            "basis": basis_of(state),
            "evidenceState": state,
            "claimStatus": "unreviewed",
            "claimVerified": False,
            "semanticStatus": "unreviewed",
            "quoteVerified": True,
            "referenceStatus": "resolved",
            "resolved": True,
            "provenance": "deterministic-cue-extraction",
            "generator": GENERATOR,
            "reviewNote": "伏笔的存在由原文暗示句证明；是否属于作者有意设计不在此断言。",
        }
        if payoff.get("found"):
            out.append(record)
        else:
            unresolved.append(record)

    kept = keep_existing_clues(existing, text, anchors, chapters, source, book_key)
    return out, unresolved, kept


def find_payoff(text, seed_pos, seed_sentence, kind, events, anchors, chapters, source):
    """在 seed 之后寻找同一「线索指纹」的兑现 / 呼应。

    判定要求三件事同时成立，缺一不算回收：
      1. 同一**具体线索载体**（信物词，如「锦囊」「衣带诏」）在 seed 之后再次出现；
      2. 该处句子带**兑现标记**（果然 / 应验 / 方知 / 正应 / 依言 …）——
         只有承诺再次被提及而没有兑现语，不足以判为回收；
      3. 该处能被原文锚点定位（否则回收句无法回到原文，不能算已核验）。
    找不到就如实留 seeded / unresolved，绝不凭常识猜结局。
    """
    carrier = next((c for c in clue_carriers(kind) if c in seed_sentence), "")
    if not carrier:
        return {"found": False, "reason": "no_carrier_in_seed"}
    tail_start = seed_pos + len(seed_sentence)
    tail = text[tail_start: tail_start + 1_500_000]
    for m in re.finditer(r"[^。！？!?\n]{6,240}", tail):
        s2 = tail_start + m.start()
        sentence2 = m.group(0)
        if carrier not in sentence2:
            continue
        if not has_redemption_marker(sentence2):
            continue
        to, nt = anchors.nearest_after(s2, 600)
        if to is None:
            continue
        ch = chapter_at(chapters, s2)
        ref = tag_ref(sentence2, s2, s2 + len(sentence2), text, source, ch, "exact")
        return {"found": True, "quote": sentence2, "ref": ref, "carrier": carrier,
                "eventId": to[2], "reinforced": nt > 1}
    return {"found": False, "reason": "no_redeemed_occurrence"}


REDEMPTION_MARKERS = ("果然", "果应", "应验", "正应", "方知", "才知", "始知",
                      "依言", "如言", "果如所言", "不差", "竟应", "却应",
                      "至此方", "这才明白", "这才知道", "一语成谶", "竟成",
                      "果如其言", "果不其然", "验矣", "应了", "兑现")
REDEMPTION_FALSE_FRIENDS = ("如果", "后果", "效果", "成果", "果决", "果断",
                            "水果", "因果", "结果")


def has_redemption_marker(sentence: str) -> bool:
    """真正的兑现标记：排除「如果/后果/结果」这类含「果」的无关词。"""
    probe = sentence
    for bad in REDEMPTION_FALSE_FRIENDS:
        probe = probe.replace(bad, "\u3000")
    return any(m in probe for m in REDEMPTION_MARKERS)


def clue_carriers(kind):
    """可作为回收载体的具体线索词（不含泛词）。"""
    return CLUE_CUES["foreshadow_object"].get(kind, [])


def payoff_probes(kind):
    return clue_carriers(kind)


_FOCUS_STOP = set("的了是在有和与这那不一我你他她它们个之其所以因为但是然后于是")


def extract_focus(sentence: str) -> list[str]:
    """抽取线索指纹人物：连续 2-4 个非常用字的 CJK 串。"""
    out = []
    for m in re.finditer(r"[\u4e00-\u9fff]{2,4}", sentence):
        w = m.group(0)
        if any(ch in _FOCUS_STOP for ch in w):
            continue
        out.append(w)
    return out[:6]


def keep_existing_clues(existing, text, anchors, chapters, source, book_key):
    """基线伏笔一条不删；重新核验引句并如实标注定位结果。"""
    kept = []
    for i, item in enumerate(existing or []):
        if not isinstance(item, dict):
            continue
        rec = dict(item)
        seed_q = str(item.get("seedQuote") or "").strip()
        payoff_q = str(item.get("payoffQuote") or "").strip()
        refs = []
        for q in (seed_q, payoff_q):
            if not q:
                continue
            pos = text.find(q)
            if pos >= 0:
                ch = chapter_at(chapters, pos)
                refs.append(tag_ref(q, pos, pos + len(q), text, source, ch, "exact"))
            else:
                refs.append({
                    "sourceId": source["sourceId"], "sourcePath": source["sourcePath"],
                    "offsetUnit": "codepoint", "start": None, "end": None,
                    "chapterIndex": None, "chapterLabel": None, "quote": q,
                    "match": "not_found", "verified": False, "locatorOnly": True,
                    "textHash": source["textHash"],
                    "reason": "quote_not_found_in_source",
                })
        rec["sourceRefs"] = refs
        rec["id"] = item.get("id") or stable_id("clue", book_key, "legacy", i)
        rec["entityId"] = rec["id"]
        rec["quoteVerified"] = bool(refs) and all(r["verified"] for r in refs)
        rec["evidenceState"] = "explicit" if rec["quoteVerified"] else "unverified"
        rec["basis"] = basis_of(rec["evidenceState"])
        rec["claimStatus"] = "unreviewed"
        rec["claimVerified"] = False
        rec["semanticStatus"] = "unreviewed"
        rec["referenceStatus"] = ("resolved" if rec["quoteVerified"] else "unresolved")
        rec["resolved"] = rec["quoteVerified"]
        rec["carriedFromBaseline"] = True
        if item.get("status") == "resolved" and not rec["quoteVerified"]:
            rec["status"] = "uncertain"
            rec["statusDowngrade"] = "resolved→uncertain：回收引句未能在原文逐字定位"
        kept.append(rec)
    return kept


# ---------------------------------------------------------------- 状态相变与信息差

STATE_PREDICATES = [
    "即位", "登基", "被废", "废为", "称帝", "称王", "自立", "封为", "封作", "拜为",
    "授为", "任命", "投降", "归降", "归顺", "投奔", "叛", "被杀", "被斩", "遇害",
    "战死", "病逝", "病亡", "而死", "获释", "出狱", "被囚", "下狱", "罢官", "辞官",
    "弃官", "升为", "擢为", "迁为", "成为", "沦为", "被贬", "流放", "夺得", "失去",
    "占领", "攻取", "陷落", "阵亡", "自刎", "伏诛", "斩首", "加封", "进位",
]

KNOW_PREDICATES = ["得知", "获悉", "方知", "才知", "方才知道", "明白了", "醒悟",
                   "恍然大悟", "察觉", "获知", "探知", "始知", "乃知", "闻知"]
UNKNOW_PREDICATES = ["不知", "不知道", "不晓得", "未知", "蒙在鼓里", "浑然不知",
                     "毫不知情", "被瞒", "瞒着", "并未告知", "未曾告知", "不知情",
                     "尚不知", "全不知"]


def build_states(book_key, title, graph, text, chapters, anchors, events, review_pairs, existing):
    """人物状态相变 + 信息差。

    状态相变必须给出 before/after（何时、因何、从什么到什么）；只找到
    单点属性的记为 snapshot，不冒充相变。
    """
    source = source_meta(graph, book_key)
    char_index = char_lookup(graph)
    by_id = {e["id"]: e for e in events}
    names = sorted(char_index, key=len, reverse=True)
    ac = AhoCorasick(names) if names else None
    states, transitions, knowledge, unresolved = [], [], [], []
    seen = set()

    def scan(preds, kind):
        for m in re.finditer("|".join(re.escape(p) for p in preds), text):
            p = m.start()
            frm, nf = anchors.nearest_before(p, 300)
            to, nt = anchors.nearest_after(p, 300)
            if not to:
                continue
            ev = by_id.get(to[2])
            if not ev:
                continue
            ch = chapter_at(chapters, p)
            sa, sb = sentence_bounds(text, p)
            sentence = text[sa:sb]
            if len(sentence) < 6 or len(sentence) > 260:
                continue
            people = matched_people(ac, sentence, char_index)
            key = (kind, nfkc_norm(sentence))
            if key in seen:
                continue
            seen.add(key)
            yield {"kind": kind, "pos": p, "eventId": to[2], "prevEventId": frm[2] if frm else "",
                   "chapter": ch, "sentence": sentence, "people": people,
                   "predicate": m.group(0), "predicateOffset": p - sa,
                   "beforeEvent": by_id.get(frm[2]) if frm else None,
                   "ac": ac, "charIndex": char_index, "sentenceStart": sa,
                   "event": ev}

    for hit in scan(STATE_PREDICATES, "state"):
        rec = make_state_record(hit, text, source, chapters, book_key, "state")
        rec["transition"] = {
            "before": (hit["beforeEvent"] or {}).get("summary") or "",
            "after": hit["event"].get("summary") or "",
            "description": f"原文以「{hit['predicate']}」标明 {hit['sentence'][:40]} 这一状态改变；"
                           f"变化前为「{(hit['beforeEvent'] or {}).get('title') or '未提供'}」，"
                           f"变化后为「{hit['event'].get('title')}」。",
            "quote": hit["sentence"],
            "beforeEventId": hit["prevEventId"],
            "afterEventId": hit["eventId"],
        }
        if hit["prevEventId"] and hit["prevEventId"] != hit["eventId"]:
            rec["evidenceState"] = "explicit"
            rec["basis"] = basis_of("explicit")
            transitions.append(rec)
        else:
            rec["evidenceState"] = "inferred"
            rec["basis"] = basis_of("inferred")
            rec.pop("transition")
            states.append(rec)

    for hit in scan(KNOW_PREDICATES, "knowledge"):
        rec = make_state_record(hit, text, source, chapters, book_key, "knowledge")
        rec["knowledgeStatus"] = "known"
        rec["text"] = hit["sentence"]
        rec["evidenceState"] = "explicit"
        rec["basis"] = basis_of("explicit")
        knowledge.append(rec)

    for hit in scan(UNKNOW_PREDICATES, "knowledge"):
        rec = make_state_record(hit, text, source, chapters, book_key, "knowledge")
        rec["knowledgeStatus"] = "unknown"
        rec["isGap"] = True
        rec["text"] = hit["sentence"]
        rec["evidenceState"] = "explicit"
        rec["basis"] = basis_of("explicit")
        knowledge.append(rec)

    kept_states, kept_knowledge, kept_unverified = keep_existing_states(
        existing, text, anchors, chapters, source, book_key)

    review = build_identity_review(graph, review_pairs, book_key)

    return {
        "states": states,
        "transitions": transitions,
        "knowledge": knowledge,
        "carriedStates": kept_states,
        "carriedKnowledge": kept_knowledge,
        "unverifiedAnchors": kept_unverified,
        "identityReview": review,
    }


def char_lookup(graph):
    index = {}
    for c in graph.get("characters") or []:
        if not isinstance(c, dict):
            continue
        n = c.get("name")
        if n and len(n) >= 2:
            index.setdefault(n, c)
        for a in c.get("aliases") or []:
            if a and len(a) >= 2:
                index.setdefault(a, c)
    return index


def matched_people(ac, sentence, char_index):
    """返回 (canonical_name, characterId) 列表，按出现顺序、去重。"""
    if ac is None:
        return []
    found, seen = [], set()
    pos = 0
    while pos < len(sentence):
        w = ac.longest_at(sentence, pos)
        if w:
            c = char_index.get(w) or {}
            canon = c.get("name") or w
            if canon not in seen:
                seen.add(canon)
                found.append((canon, c.get("id") or c.get("entityId") or ""))
            pos += len(w)
        else:
            pos += 1
    return found[:6]


def subject_of(sentence: str, people: list[tuple[str, str]], predicate_pos: int = -1):
    """判定状态/知情句的主语人物。

    「谁在第几章知道了什么」必须落到具体人物。中文叙事里知情动词的主语通常在
    动词**之前**，所以优先取谓词之前、最靠近谓词的人名；谓词前没有人名时
    退回句内最靠前的人名；一句都没有就不猜 —— 返回空并由调用方标
    `characterResolved=false`，前端显示「人物待核」而不是编一个人名。
    """
    if not people:
        return "", ""
    if predicate_pos >= 0:
        before = [(p, c, sentence.find(p)) for p, c in people
                  if 0 <= sentence.find(p) < predicate_pos]
        if before:
            p, c, _ = max(before, key=lambda x: x[2])
            return p, c
    return people[0][0], people[0][1]


PRONOUNS = ("他", "她", "它", "其", "之", "彼", "此", "吾", "我", "予", "汝", "尔",
            "众人", "众将", "二人", "三人", "兄弟", "师徒")


def resolve_subject_with_context(text, sentence_start_pos, sentence, people, predicate_pos, ac, char_index):
    """先在本句找主语；本句只有代词时，回看**紧邻的前文**里的专名。

    回看最多 2 句且总长 ≤240 字，并**要求前文只出现一个人名**（唯一性），
    否则宁可标未解析也不猜 —— 猜错主语会让「谁知道什么」整体失真。
    """
    p, c = subject_of(sentence, people, predicate_pos)
    if p:
        return p, c, "in_sentence"
    if sentence_start_pos <= 0:
        return "", "", "unresolved"
    collected = []
    cursor = sentence_start_pos
    for _ in range(2):
        if cursor <= 0:
            break
        pa, pb = sentence_bounds(text, cursor - 1)
        if pb > cursor or pb <= pa:
            break
        collected.append(text[pa:pb])
        cursor = pa
        if sum(len(x) for x in collected) > 240:
            break
    if not collected:
        return "", "", "unresolved"
    window = "".join(reversed(collected))
    found = matched_people(ac, window, char_index)
    if len(found) == 1:
        return found[0][0], found[0][1], "previous_context"
    return "", "", "unresolved"


def make_state_record(hit, text, source, chapters, book_key, kind):
    ch = hit["chapter"]
    s0 = sentence_start(text, hit["pos"])
    ref = tag_ref(hit["sentence"], s0, s0 + len(hit["sentence"]), text, source, ch, "exact")
    people = hit["people"]
    primary, cid, subj_src = resolve_subject_with_context(
        text, s0, hit["sentence"], people, hit.get("predicateOffset", -1),
        hit.get("ac"), hit.get("charIndex") or {})
    eid = stable_id("state", book_key, kind, hit["eventId"], nfkc_norm(hit["sentence"]))
    return {
        "id": eid,
        "entityId": eid,
        "characterId": cid,
        "character": primary,
        "name": primary,
        "characterResolved": bool(primary),
        "subjectSource": subj_src,
        "castInSentence": [p for p, _ in people],
        "eventId": hit["eventId"],
        "chapter": ch.get("heading") if ch else "",
        "chapterIndex": ch.get("num") if ch else None,
        "chapterRange": [ch.get("heading") if ch else "", ch.get("heading") if ch else ""],
        "summary": hit["sentence"][:80],
        "quote": hit["sentence"],
        "quoteRef": ref,
        "sourceRefs": [ref],
        "attributes": [{
            "name": "原文明示" if kind == "state" else "知情内容",
            "value": hit["sentence"],
            "quote": hit["sentence"],
            "sourceRefs": [ref],
            "quoteVerified": True,
        }],
        "basis": basis_of("explicit"),
        "evidenceState": "explicit",
        "claimStatus": "unreviewed",
        "claimVerified": False,
        "semanticStatus": "unreviewed",
        "quoteVerified": True,
        "referenceStatus": "resolved",
        "resolved": True,
        "provenance": "deterministic-predicate-extraction",
        "generator": GENERATOR,
    }


def sentence_start(text, pos):
    a = pos
    while a > 0 and text[a - 1] not in SENT_BREAK:
        a -= 1
    return a


def char_id_for(text, hit, people):
    return ""


def keep_existing_states(existing, text, anchors, chapters, source, book_key):
    """基线 characterStates 一条不删。分三类：已定位 / 定位成功但需归一化 / 定位不到。"""
    ok, unverified = [], []
    for i, item in enumerate(existing or []):
        if not isinstance(item, dict):
            continue
        rec = dict(item)
        rec["id"] = item.get("id") or stable_id("state", book_key, "legacy", i)
        rec["entityId"] = rec["id"]
        q = str(item.get("quote") or "").strip()
        refs = []
        if q:
            pos = text.find(q)
            if pos >= 0:
                ch = chapter_at(chapters, pos)
                refs.append(tag_ref(q, pos, pos + len(q), text, source, ch, "exact"))
            else:
                npos = normalized_locate(text, q)
                refs.append({
                    "sourceId": source["sourceId"], "sourcePath": source["sourcePath"],
                    "offsetUnit": "codepoint",
                    "start": npos[0] if npos else None,
                    "end": npos[1] if npos else None,
                    "chapterIndex": (chapter_at(chapters, npos[0]) or {}).get("num") if npos else None,
                    "chapterLabel": (chapter_at(chapters, npos[0]) or {}).get("heading") if npos else None,
                    "quote": q, "match": "normalized" if npos else "not_found",
                    "verified": False, "locatorOnly": True,
                    "textHash": source["textHash"],
                    "reason": "raw_text_mismatch" if npos else "quote_not_found_in_source",
                })
        rec["sourceRefs"] = refs
        rec["quoteVerified"] = bool(refs) and all(r["verified"] for r in refs)
        rec["evidenceState"] = "explicit" if rec["quoteVerified"] else "unverified"
        rec["basis"] = basis_of(rec["evidenceState"])
        rec["claimStatus"] = "unreviewed"
        rec["claimVerified"] = False
        rec["semanticStatus"] = "unreviewed"
        rec["referenceStatus"] = "resolved" if rec["quoteVerified"] else "unresolved"
        rec["resolved"] = rec["quoteVerified"]
        rec["carriedFromBaseline"] = True
        (ok if rec["quoteVerified"] else unverified).append(rec)
    return ok, [], unverified


_NORM_STRIP = re.compile(r"[\s\u3000，。！？；：、“”‘’（）《》〈〉·…—～!?,.;:()\[\]{}<>/\\|\"']+")


def normalized_locate(text, quote):
    """去标点后定位；返回原文 raw 区间。仅供「定位成功」计数，不算已核验引句。"""
    target = _NORM_STRIP.sub("", quote)
    if len(target) < 4:
        return None
    idx = _norm_index(text)
    j = idx["text"].find(target)
    if j < 0:
        return None
    return idx["map"][j], idx["map"][j + len(target) - 1] + 1


_NORM_CACHE: dict[str, dict] = {}


def _norm_index(text):
    key = sha256(text)
    got = _NORM_CACHE.get(key)
    if got:
        return got
    buf, mapping = [], []
    for m in re.finditer(r"[^\s\u3000，。！？；：、“”‘’（）《》〈〉·…—～!?,.;:()\[\]{}<>/\\|\"']+", text):
        buf.append(m.group(0))
        mapping.extend(range(m.start(), m.end()))
    idx = {"text": "".join(buf), "map": mapping}
    _NORM_CACHE[key] = idx
    return idx


def build_identity_review(graph, review_pairs, book_key):
    out = []
    for issue in graph.get("reviewIssues") or []:
        if not isinstance(issue, dict):
            continue
        if issue.get("kind") != "identity":
            continue
        cid = issue.get("characterId")
        rec = {
            "id": issue.get("id") or stable_id("review", book_key, cid),
            "kind": "identity",
            "characterId": cid,
            "identityStatus": issue.get("identityStatus"),
            "description": issue.get("description"),
            "sourceRefs": issue.get("sourceRefs") or [],
            "decision": "pending",
            "autoMerge": False,
            "mergeRule": "身份冲突不得自动归并：本产出不合并该人物的任何新增因果/状态/关系。",
            "affectedEventIds": issue.get("eventIds") or [],
        }
        out.append(rec)
    return out


# ---------------------------------------------------------------- 关系锚点

REL_CUES = {
    "师徒": ["为师", "弟子", "徒弟", "师父", "受业", "学艺", "门下", "传授", "拜师", "师事"],
    "结义": ["结为兄弟", "结拜", "义结金兰", "誓同生死", "结为", "约为兄弟"],
    "父子": ["之子", "其父", "生父", "所生", "父子", "父亲"],
    "母子": ["之母", "其母", "母子", "母亲"],
    "血亲": ["之弟", "之兄", "之妹", "之姐", "之女", "宗亲", "胞弟", "胞兄", "兄弟", "姊妹"],
    "夫妻": ["为妻", "之妻", "娶", "嫁", "夫妇", "夫妻", "夫人"],
    "君臣": ["为臣", "称臣", "主公", "陛下", "君臣", "事之", "君命"],
    "同盟": ["结盟", "同盟", "联盟", "合兵", "并力", "歃血", "共讨"],
    "盟友": ["结盟", "同盟", "联盟", "合兵", "并力", "相善", "交好"],
    "敌对": ["为敌", "不共戴天", "誓杀", "必杀", "报仇", "讨伐", "仇", "恨"],
    "对立": ["为敌", "不共戴天", "讨伐", "相争", "不和", "反目"],
    "对抗": ["厮杀", "交战", "迎敌", "大战", "来攻", "单搦", "搦战", "交锋", "对敌"],
    "上下级": ["封为", "拜为", "授为", "命为", "麾下", "部下", "帐下"],
    "部属": ["麾下", "部下", "将士", "部曲", "帐下"],
    "背叛": ["背叛", "背主", "叛", "卖主", "反", "降", "弑"],
    "利用": ["利用", "借刀", "假手", "诈", "赚"],
    "同谋": ["密议", "共谋", "同谋", "合谋", "同议"],
    "同门": ["同门", "同师", "师兄弟", "师姐妹"],
    "归降": ["投降", "归降", "归顺", "来投", "降"],
    "君臣招揽": ["招为", "延请", "请为", "礼聘", "征辟"],
    "同场": [],
    "间接同场": [],
    "同阵营": [],
    "同僚": [],
    "同朝": [],
    "同族": [],
    "合作": [],
    "镇压": ["镇压", "压", "收服", "降伏"],
    "护持": ["护持", "保护", "护送", "保全"],
    "收录门下": ["收为", "门下", "收录"],
    "取经脚力": ["脚力", "坐骑", "化马"],
    "守山护法": ["守山", "护法", "镇守"],
    "审讯": ["审", "问案", "拷", "刑"],
    "交易": ["交易", "买卖", "买", "卖", "赎"],
    "对峙": ["对峙", "相持", "扎营", "下寨"],
}

CO_PRESENCE_KINDS = {"同场", "间接同场", "同阵营", "同朝", "同僚", "同族", "合作"}


def cues_for(kind: str) -> list[str]:
    """只按**精确 kind** 取断言词表。

    不做子串回退：子串回退会让「同僚」命中「僚」类词表、「合作」命中「同谋」词表，
    从而把同场关系升格成断言 —— 契约测试实测抓到「合作/同僚」被升格。
    未知 kind 一律返回空，走 co_presence_only。
    """
    return list(REL_CUES.get(kind, []))


def build_relations(book_key, title, graph, text, chapters, anchors, events, char_index,
                    review_pairs=frozenset()):
    """关系锚点补全。

    三级证据分层，绝不把同场升格为师徒/盟友/敌对：
      - explicit_assertion：原文句同时含双方人名 + 该关系类型的断言词（事件级锚点）
      - co_presence_only：只在同一事件中共同出现，无任何关系断言
        -> claimTier 明确标 "co_presence_only"，desc 追加「无事件级锚点，仅为同场推导」
      - unverified：既无断言也无同场事件 -> 保持 unverified，不生成结论
    """
    source = source_meta(graph, book_key)
    rels = [r for r in graph.get("relations") or [] if isinstance(r, dict)]
    rel_names = sorted({n for r in rels for n in (r.get("a"), r.get("b"))
                        if isinstance(n, str) and len(n) >= 2}, key=len, reverse=True)
    name_ac = AhoCorasick(rel_names) if rel_names else None
    all_cues = sorted({c for r in rels for c in cues_for(r.get("kind") or "") if c},
                      key=len, reverse=True)
    cue_ac = AhoCorasick(all_cues) if all_cues else None

    sentences = []
    for m in re.finditer(r"[^。！？!?\n]{4,300}", text):
        s, e = m.start(), m.end()
        names, cues = set(), set()
        if name_ac:
            names = {w for _, w in name_ac.find(m.group(0))}
        if cue_ac:
            cues = {w for _, w in cue_ac.find(m.group(0))}
        sentences.append((s, e, names, cues))

    ev_names = [set(e.get("characters") or []) for e in events]
    ev_of_name = defaultdict(list)
    for i, ns in enumerate(ev_names):
        for n in ns:
            ev_of_name[n].append(i)

    out, review = [], []
    counters = Counter()
    for r in rels:
        a, b = r.get("a"), r.get("b")
        kind = r.get("kind") or ""
        if not isinstance(a, str) or not isinstance(b, str) or a == b:
            continue
        cues = set(cues_for(kind))
        rec = dict(r)
        rec["id"] = r.get("id") or stable_id("rel", book_key, *sorted((a, b)), kind)
        rec["entityId"] = rec["id"]

        baseline_refs, baseline_verified = recheck_baseline_relation(r, text, chapters, source)
        if baseline_verified:
            rec["sourceRefs"] = baseline_refs
            rec["quote"] = baseline_refs[0]["quote"]
            rec["claimTier"] = "explicit_assertion"
            rec["evidenceState"] = "explicit"
            rec["basis"] = basis_of("explicit")
            rec["anchorStatus"] = "event_level_verified"
            rec["carriedFromBaseline"] = True
            rec["quoteVerified"] = True
            rec["claimStatus"] = "unreviewed"
            rec["claimVerified"] = False
            rec["referenceStatus"] = "resolved"
            rec["resolved"] = True
            counters["explicit_assertion"] += 1
            counters["carried_from_baseline"] += 1
            out.append(rec)
            continue
        if not cues:
            evid = [events[i]["id"] for i in ev_of_name.get(a, []) if b in ev_names[i]]
            rec["eventIds"] = evid[:20]
            rec["claimTier"] = "co_presence_only"
            rec["evidenceState"] = "derived"
            rec["basis"] = basis_of("derived")
            rec["desc"] = ensure_no_escalation(r.get("desc") or "", "同场")
            rec["sourceRefs"] = []
            rec["anchorStatus"] = "no_event_level_anchor"
            rec["anchorNote"] = "无事件级原文锚点，仅为同场推导；同场不构成师徒/盟友/敌对。"
            rec["coPresenceEventIds"] = evid[:20]
            rec["claimStatus"] = "unreviewed"
            rec["claimVerified"] = False
            rec["quoteVerified"] = False
            rec["referenceStatus"] = "resolved"
            rec["resolved"] = True
            counters["co_presence_only"] += 1
            out.append(rec)
            continue
        best = None
        for s, e, names, sent_cues in sentences:
            if a in names and b in names and (sent_cues & cues):
                if best is None or (e - s) < (best[1] - best[0]):
                    best = (s, e)
        if best:
            ch = chapter_at(chapters, best[0])
            ref = tag_ref(text[best[0]:best[1]], best[0], best[1], text, source, ch, "exact")
            ev = enclosing_event(events, best[0])
            rec["claimTier"] = "explicit_assertion"
            rec["evidenceState"] = "explicit"
            rec["basis"] = basis_of("explicit")
            rec["sourceRefs"] = [ref]
            rec["quote"] = ref["quote"]
            rec["anchorStatus"] = "event_level_verified"
            rec["eventIds"] = [ev["id"]] if ev else []
            rec["quoteVerified"] = True
            rec["claimStatus"] = "unreviewed"
            rec["claimVerified"] = False
            rec["referenceStatus"] = "resolved"
            rec["resolved"] = True
            counters["explicit_assertion"] += 1
            out.append(rec)
            continue
        same = [events[i]["id"] for i in ev_of_name.get(a, []) if b in ev_names[i]]
        if same:
            rec["claimTier"] = "co_presence_only"
            rec["evidenceState"] = "derived"
            rec["basis"] = basis_of("derived")
            rec["desc"] = ensure_no_escalation(r.get("desc") or "", kind)
            rec["sourceRefs"] = []
            rec["anchorStatus"] = "no_event_level_anchor"
            rec["anchorNote"] = "无事件级原文锚点，仅为同场推导；同场不构成师徒/盟友/敌对。"
            rec["coPresenceEventIds"] = same[:20]
            rec["eventIds"] = same[:20]
            rec["claimStatus"] = "unreviewed"
            rec["claimVerified"] = False
            rec["quoteVerified"] = False
            rec["referenceStatus"] = "resolved"
            rec["resolved"] = True
            counters["co_presence_only"] += 1
        else:
            rec["claimTier"] = "unverified"
            rec["evidenceState"] = "unverified"
            rec["basis"] = basis_of("unverified")
            rec["sourceRefs"] = []
            rec["anchorStatus"] = "no_anchor_no_event"
            rec["anchorNote"] = "既无原文断言句，也无共同事件；本产出不为其生成确定结论。"
            rec["coPresenceEventIds"] = []
            rec["eventIds"] = []
            rec["claimStatus"] = "unreviewed"
            rec["claimVerified"] = False
            rec["quoteVerified"] = False
            rec["referenceStatus"] = "unresolved"
            rec["resolved"] = False
            counters["unverified"] += 1
        out.append(rec)

    for rec in out:
        if rec.get("id") in review_pairs:
            rec["claimTier"] = "pending_identity_review"
            rec["evidenceState"] = "unverified"
            rec["basis"] = basis_of("unverified")
            rec["resolved"] = False
            rec["referenceStatus"] = "unresolved"
            review.append(rec["id"])
    return out, counters, review


def ensure_no_escalation(desc: str, kind: str) -> str:
    marker = "无事件级锚点，仅为同场推导"
    if marker in desc:
        return desc
    return f"{desc}（{marker}；kind=「{kind}」为同场归类，未升格为师徒/盟友/敌对。）"


def enclosing_event(events, pos):
    for e in events:
        ref = e.get("quoteRef") or {}
        s, en = ref.get("start"), ref.get("end")
        if isinstance(s, int) and isinstance(en, int) and s <= pos < en:
            return e
    return None


def recheck_baseline_relation(rec, text, chapters, source):
    """复核基线关系自带的 sourceRefs：逐字命中才算已核验，否则不算。

    这是「保留既有证据」与「不信任旧标记」之间唯一诚实的做法：
    位置必须由本次读取的原文重新证明，旧的 verified=true 不作数。
    """
    refs = []
    items = rec.get("sourceRefs")
    items = items if isinstance(items, list) else ([items] if isinstance(items, dict) else [])
    for ref in items:
        if not isinstance(ref, dict):
            continue
        q = ref.get("quote")
        if not isinstance(q, str) or not q.strip():
            continue
        q = q.strip()
        pos = text.find(q)
        if pos < 0:
            continue
        ch = chapter_at(chapters, pos)
        refs.append(tag_ref(q, pos, pos + len(q), text, source, ch, "exact"))
    if not refs:
        q = rec.get("quote")
        if isinstance(q, str) and q.strip():
            q = q.strip()
            pos = text.find(q)
            if pos >= 0:
                ch = chapter_at(chapters, pos)
                refs.append(tag_ref(q, pos, pos + len(q), text, source, ch, "exact"))
    return refs, bool(refs)


# ---------------------------------------------------------------- 未核验锚点台账

def unverified_ledger(graph, text, chapters, source, book_key):
    """not_found / normalized / ambiguous 的锚点一条不删，全部进台账并给出可复用位置。

    「定位成功但章节归属不符」单独统计 —— 审核点名的真实缺陷形态。
    """
    collections = [
        ("events", graph.get("events") or [], ["quoteRef", "sourceRefs"]),
        ("relations", graph.get("relations") or [], ["sourceRefs"]),
        ("causeEdges", graph.get("causeEdges") or [], ["sourceRefs", "quoteRef"]),
        ("characterStates", graph.get("characterStates") or [], ["sourceRefs", "quoteRef"]),
        ("storylines", graph.get("storylines") or [], ["sourceRefs"]),
        ("tasks", graph.get("tasks") or [], ["sourceRefs"]),
        ("clues", graph.get("clues") or [], ["sourceRefs"]),
    ]
    rows = []
    match_counter = Counter()
    chapter_mismatch = []
    for cname, records, fields in collections:
        for rec in records:
            if not isinstance(rec, dict):
                continue
            for f in fields:
                v = rec.get(f)
                items = v if isinstance(v, list) else ([v] if isinstance(v, dict) else [])
                for ref in items:
                    if not isinstance(ref, dict):
                        continue
                    q = str(ref.get("quote") or "")
                    status = ref.get("match") or ("exact" if ref.get("verified") else "missing")
                    if not q:
                        match_counter["empty"] += 1
                        continue
                    pos = text.find(q)
                    if pos >= 0:
                        m = "exact"
                    else:
                        npos = normalized_locate(text, q)
                        m = "normalized" if npos else ("ambiguous" if status == "ambiguous" else "not_found")
                        pos = npos[0] if npos else None
                    match_counter[m] += 1
                    if m == "exact":
                        continue
                    row = {
                        "collection": cname,
                        "recordId": rec.get("id") or rec.get("entityId"),
                        "field": f,
                        "declaredMatch": status,
                        "measuredMatch": m,
                        "quote": q,
                        "sourceId": ref.get("sourceId") or source["sourceId"],
                        "start": pos,
                        "end": (normalized_locate(text, q) or (None, None))[1] if pos is not None else None,
                        "searchProbe": q[:24],
                        "disposition": "unverified",
                        "note": ("引句在原文中无法逐字定位；不得计为已核验引句。"
                                 if m == "not_found" else
                                 "仅归一化定位成功（去除标点/全角差异后可匹配）；"
                                 "不得计为已核验引句，只得计为定位成功。"),
                        "evidenceState": "unverified",
                    }
                    rows.append(row)
                    if rec.get("chapter") and pos is not None:
                        decl = rec["chapter"]
                        loc = chapter_at(chapters, pos)
                        if loc and norm(decl) != norm(loc["heading"]) and norm(loc["heading"]).startswith(norm(decl)[:4]):
                            chapter_mismatch.append({
                                "collection": cname, "recordId": row["recordId"],
                                "declared": decl, "actual": loc["heading"], "start": pos,
                            })
    return {
        "bookKey": book_key,
        "matchDistribution": dict(match_counter),
        "unverifiedAnchors": rows,
        "unverifiedCount": len(rows),
        "chapterMismatchCount": len(chapter_mismatch),
        "chapterMismatchSample": chapter_mismatch[:60],
    }


# ---------------------------------------------------------------- 汇总

def source_meta(graph, book_key):
    srcs = ((graph.get("meta") or {}).get("sources") or [{}])
    s = srcs[0] if isinstance(srcs, list) and srcs else {}
    return {
        "sourceId": s.get("id") or "",
        "sourcePath": s.get("path") or "",
        "textHash": s.get("textHash") or "",
        "bookKey": book_key,
    }


def build_book(book_key, title, window=800):
    t0 = time.time()
    gpath = ROOT / "data" / "cache" / f"{book_key}.json"
    dpath = ROOT / "data" / "cache" / f"{book_key}.docs.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    docs = json.loads(dpath.read_text(encoding="utf-8"))
    text = docs[0]["text"]
    chapters, chap_src = build_chapters(book_key, text)
    events = [e for e in graph.get("events") or [] if isinstance(e, dict)]
    anchors = Anchors(events, text)
    source = source_meta(graph, book_key)
    existing_cause = graph.get("causeEdges") or []
    review_pairs = {i.get("id") for i in (graph.get("reviewIssues") or [])
                    if isinstance(i, dict)}

    causal, cgraph, creport, causal_carried = build_causal(
        book_key, title, graph, text, chapters, anchors, window,
        {c.get("id") for c in existing_cause if isinstance(c, dict)})
    clues, clue_unresolved, clues_kept = build_clues(
        book_key, title, graph, text, chapters, anchors, events, graph.get("clues") or [])
    st = build_states(book_key, title, graph, text, chapters, anchors, events,
                      review_pairs, graph.get("characterStates") or [])
    relations, rel_counters, rel_review = build_relations(
        book_key, title, graph, text, chapters, anchors, events, char_lookup(graph),
        review_pairs=review_pairs)
    ledger = unverified_ledger(graph, text, chapters, source, book_key)

    common = {
        "schemaVersion": SCHEMA_VERSION,
        "bookKey": book_key,
        "title": title,
        "generator": GENERATOR,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": dict(source, docsPath=str(dpath.relative_to(ROOT)),
                       chars=len(text), extractedChapters=len(chapters),
                       chapterIndexSource=chap_src),
        "evidenceStates": list(EVIDENCE_STATES),
        "basisMap": BASIS_OF_STATE,
        "claimVerification": "not_performed",
        "semanticReview": "not_performed",
        "note": ("引文定位不等于语义判断正确。match=exact 仅表示该引句逐字存在于原文；"
                 "match=normalized/not_found 只计「定位成功」或未定位，不计已核验引句。"),
    }

    causal_doc = dict(common, layer="causeEdges",
                      edges=causal, carriedFromBaseline=causal_carried,
                      propagationGraph=cgraph,
                      extractionReport=dict(creport,
                                            hardRule="禁止以时间相邻替代因果：每条边都由原文因果连接词锚定，"
                                                     "同场/先后/共现一律不计。"),
                      baselineEdgeCount=len(existing_cause),
                      totalEdgeCount=len(causal) + len(causal_carried),
                      unverifiedAnchors=ledger["unverifiedAnchors"],
                      matchDistribution=ledger["matchDistribution"],
                      chapterMismatchCount=ledger["chapterMismatchCount"],
                      chapterMismatchSample=ledger["chapterMismatchSample"])
    clue_doc = dict(common, layer="clues",
                    clues=clues, unresolvedClues=clue_unresolved,
                    carriedFromBaseline=clues_kept,
                    lifecycleVocabulary=["seeded", "reinforced", "misled", "paid_off", "unresolved"])
    state_doc = dict(common, layer="characterStates",
                     states=st["states"], transitions=st["transitions"],
                     knowledge=st["knowledge"],
                     carriedFromBaseline=st["carriedStates"],
                     unverifiedAnchors=st["unverifiedAnchors"],
                     identityReview=st["identityReview"],
                     baselineCounts={"characterStates": len(graph.get("characterStates") or []),
                                     "clues": len(graph.get("clues") or [])})
    rel_doc = dict(common, layer="relations",
                   relations=relations, tierCounts=dict(rel_counters),
                   pendingIdentityReview=rel_review,
                   hardRule="同场不得升格为师徒/盟友/敌对；无事件级断言的关系一律 claimTier=co_presence_only。")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix, doc in (("causal", causal_doc), ("clues", clue_doc),
                        ("states", state_doc), ("relations", rel_doc)):
        (OUT_DIR / f"{book_key}.{suffix}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    summary = {
        "bookKey": book_key, "title": title,
        "chars": len(text), "chapters": len(chapters), "chapterIndexSource": chap_src,
        "events": len(events),
        "anchoredEvents": len({a[2] for a in anchors.exact}),
        "causeEdges": {
            "baseline": len(existing_cause), "new": len(causal),
            "carriedFromBaseline": len(causal_carried),
            "total": len(causal) + len(causal_carried),
            "withExactAnchor": sum(1 for e in causal if e["quoteRef"]["match"] == "exact"),
            "chaptersTouched": creport["chaptersTouched"],
            "cycles": cgraph["cycleCount"], "isolatedNodes": cgraph["isolatedNodeCount"],
            "scopeFailureBreakdown": creport.get("scopeFailureBreakdown", {}),
        },
        "clues": {"baseline": len(graph.get("clues") or []), "resolved": len(clues),
                  "seeded": len(clue_unresolved), "carried": len(clues_kept)},
        "states": {"baseline": len(graph.get("characterStates") or []),
                   "newStates": len(st["states"]), "newTransitions": len(st["transitions"]),
                   "knowledge": len(st["knowledge"]),
                   "carriedVerified": len(st["carriedStates"]),
                   "carriedUnverified": len(st["unverifiedAnchors"]),
                   "identityReview": len(st["identityReview"])},
        "relations": {"baseline": len(graph.get("relations") or []),
                      "tiers": dict(rel_counters),
                      "anchorRate": round(
                          rel_counters["explicit_assertion"] /
                          max(1, rel_counters["explicit_assertion"]
                              + rel_counters["co_presence_only"]
                              + rel_counters["unverified"]), 4)},
        "unverified": {"count": ledger["unverifiedCount"],
                       "distribution": ledger["matchDistribution"],
                       "chapterMismatch": ledger["chapterMismatchCount"]},
        "elapsedSec": round(time.time() - t0, 1),
    }
    return summary


def self_test() -> int:
    """内建反例：确认工具不会把时间相邻当因果、不会升格同场、不会虚构引文。"""
    failures = []
    text = "甲杀了乙。因此丙逃走。丁与戊同席饮酒。"
    fake_graph = {
        "events": [
            {"id": "e1", "order": 1, "chapter": "第一回", "title": "杀乙", "kind": "冲突",
             "characters": ["甲"], "quote": "甲杀了乙。", "quoteRef": {"match": "exact", "start": 0, "end": 5, "quote": "甲杀了乙。", "verified": True}},
            {"id": "e2", "order": 2, "chapter": "第一回", "title": "丙逃", "kind": "转折",
             "characters": ["丙"], "quote": "因此丙逃走。", "quoteRef": {"match": "exact", "start": 5, "end": 11, "quote": "因此丙逃走。", "verified": True}},
        ],
        "characters": [{"id": "c1", "name": "甲"}, {"id": "c2", "name": "乙"}, {"id": "c3", "name": "丙"}],
        "relations": [{"id": "r1", "a": "丁", "b": "戊", "kind": "同场", "desc": "同席"}],
    }
    class FakeChapters:
        pass
    chapters = [{"num": 1, "heading": "第一回", "start": 0}]
    a = Anchors(fake_graph["events"], text)
    edges, cg, rep, _carried = build_causal("test", "test", fake_graph, text, chapters, a, 800, set())
    if not edges:
        failures.append("因果抽取在对齐样本上返回 0 条")
    for e in edges:
        if text[e["quoteRef"]["start"]:e["quoteRef"]["end"]] != e["quote"]:
            failures.append("因果边引文不是原文子串")
        if e["evidenceState"] not in EVIDENCE_STATES:
            failures.append("因果边四态标记非法")
    rels, counters, _ = build_relations("test", "test", fake_graph, text, chapters, a,
                                        fake_graph["events"], char_lookup(fake_graph))
    for r in rels:
        if r["claimTier"] != "co_presence_only":
            failures.append(f"同场关系被升格为 {r['claimTier']}")
        if "无事件级锚点" not in r["desc"]:
            failures.append("同场关系缺少「无事件级锚点」标注")
        if r["evidenceState"] == "explicit":
            failures.append("同场关系被标成 explicit")
    bogus = {"id": "x", "quote": "这句话原文根本没有。",
             "sourceRefs": [{"quote": "这句话原文根本没有。", "match": "exact", "start": 0, "end": 3}]}
    led = unverified_ledger({"events": [bogus]}, text, chapters,
                            {"sourceId": "s", "sourcePath": "p", "textHash": "h"}, "test")
    if led["unverifiedCount"] != 1:
        failures.append("伪造引文未被计入未核验台账")
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("self-test OK: 因果需连接词锚定 / 同场未升格 / 伪造引文入未核验台账")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", action="append", help="只处理指定 bookKey（可多次）")
    ap.add_argument("--window", type=int, default=800, help="连接词到端点的最大字符距离")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--summary", default=None, help="汇总 JSON 输出路径")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = [b for b in BOOKS if not args.book or b[0] in args.book]
    out = []
    for key, title in targets:
        s = build_book(key, title, window=args.window)
        out.append(s)
        print(f"== {title} ({key})")
        print(f"   因果 {s['causeEdges']['baseline']} -> {s['causeEdges']['new']} "
              f"(exact {s['causeEdges']['withExactAnchor']}, 触及章 {s['causeEdges']['chaptersTouched']}, "
              f"环 {s['causeEdges']['cycles']}, 孤立 {s['causeEdges']['isolatedNodes']})")
        print(f"   伏笔 基线 {s['clues']['baseline']} -> resolved {s['clues']['resolved']} "
              f"+ seeded {s['clues']['seeded']} + 保留 {s['clues']['carried']}")
        print(f"   状态 基线 {s['states']['baseline']} -> 新相变 {s['states']['newTransitions']} "
              f"+ 快照 {s['states']['newStates']} + 知情 {s['states']['knowledge']} "
              f"(基线未定位 {s['states']['carriedUnverified']})")
        print(f"   关系 基线 {s['relations']['baseline']} 断言锚点 {s['relations']['tiers'].get('explicit_assertion', 0)} "
              f"同场 {s['relations']['tiers'].get('co_presence_only', 0)} "
              f"未核验 {s['relations']['tiers'].get('unverified', 0)} 锚点率 {s['relations']['anchorRate']*100:.1f}%")
        print(f"   未核验锚点台账 {s['unverified']['count']} 条，章节不符 {s['unverified']['chapterMismatch']} 条")
    sp = Path(args.summary) if args.summary else OUT_DIR / "summary.json"
    sp.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    try:
        shown = sp.relative_to(ROOT)
    except ValueError:
        shown = sp
    print(f"-> {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
