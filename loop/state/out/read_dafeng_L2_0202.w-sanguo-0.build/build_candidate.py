#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立构建 read:dafeng:L2:0202 候选（第两百零一章 呵，女人）。作者：w-sanguo-0。

偏移口径（任务提示词硬性要求，本脚本逐条现算，任一为假即退出 1、不写盘）：
  · start/end 一律是 docs[0].text **全文** codepoint 偏移；text[start:end] == quote 逐字成立
  · 每条引文必须落在 [740647,745827) 内，且在**区间内**唯一（否则 start 有歧义）
  · 偏移一律用 S + SEG.find(q) 现取，**不用** TEXT.find（全文首见会指到区间外别人的段落）
  · sourceHash 是整个 docs.json 的 sha256；切片哈希另起 segmentSha256，不覆盖 sourceHash

内容纪律（照抄任务提示词，写成机器判据）：
  · 同一任务五栏（objective/obstacle/action/result/cost）的引文互不重复：
    句单元级 + 字符区间级两套判据，写盘前各算一次
  · 每个 null 栏必须有同名 <栏位>Note 写明**为什么没有**（不写理由的 null 判为未标注的未知）
  · 散文字段里的「…」只允许包住 docs[0].text 的逐字子串；我自己的标签一律用『…』
  · worldSettings 三类判别字段必须写进字段本身：place→placeState / rule→institution /
    item→itemStates（多选）；不许把提及写成到达、不许把持有与丢失合成一条物品链
  · 结构判据：悬空 ID、散文里的 P 段号归属、区间内零出现词当事实 三类，扫描全候选
  · 零覆盖段逐段给出处置，处置集合必须与实测零覆盖集合**完全相等**（漏一或多一都失败）
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L2_0202.candidate.json"
S, E = 740647, 745827
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
TASK = "read:dafeng:L2:0202"
AGENT = "w-sanguo-0"
UNIT_HEAD = "第两百零一章 呵，女人"
BASIS = ("explicit", "inferred", "derived", "unverified")
PROBLEMS = []

RAW = DOCS.read_bytes()
FILE_HASH = hashlib.sha256(RAW).hexdigest()
if FILE_HASH != SRC_HASH:
    sys.exit("源文件哈希与 task.sourceHash 不符：%s" % FILE_HASH)
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SEG = TEXT[S:E]
if TEXT[S:S + len(UNIT_HEAD)] != UNIT_HEAD:
    sys.exit("切片不以本单元标题开头")
SEG_HASH = hashlib.sha256(SEG.encode("utf-8")).hexdigest()

# ── 段落索引（1-based 非空段；P001 = 标题）────────────────────────────────
PARAS = []
_pos = S
for _line in SEG.split("\n"):
    if _line.strip():
        _i = TEXT.find(_line, _pos)
        if _i < 0:
            sys.exit("段落在全文里找不到：%r" % _line[:20])
        PARAS.append((_i, _i + len(_line), _line.strip()))
        _pos = _i + len(_line)
NPARA = len(PARAS)


def sentence_spans():
    spans = []
    for a, b, _t in PARAS:
        cur = a
        for m in re.finditer(r"[。！？…]+|\.{2,}", TEXT[a:b]):
            end = a + m.end()
            if end > cur:
                spans.append((cur, end))
            cur = end
        if cur < b:
            spans.append((cur, b))
    return spans


SENTS = sentence_spans()


def sent_id(pos):
    for i, (a, b) in enumerate(SENTS, start=1):
        if a <= pos < b:
            return i
    return None


def para_label(pos):
    for i, (a, b, _t) in enumerate(PARAS, start=1):
        if a <= pos < b:
            return "P%03d" % i
    return None


OFFSET_BASE = "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）"
ALL_QUOTES = []


def q(s):
    """构造引文对象：逐字 / 区间内 / 区间内唯一 三条全部现算。"""
    n = SEG.count(s)
    if n != 1:
        PROBLEMS.append("引文在区间内出现 %d 次（要求 1）：%r" % (n, s[:50]))
        return None
    start = S + SEG.find(s)
    end = start + len(s)
    if not (S <= start and end <= E):
        PROBLEMS.append("引文越界：%r" % s[:50])
        return None
    if TEXT[start:end] != s:
        PROBLEMS.append("text[start:end] != quote：%r" % s[:50])
        return None
    o = {"quote": s, "start": start, "end": end, "sourceHash": SRC_HASH,
         "offsetUnit": "codepoint", "offsetBase": OFFSET_BASE, "match": "exact",
         "wholeTextOccurrences": TEXT.count(s), "occurrencesInRange": n,
         "paraLabel": para_label(start), "sentUnit": sent_id(start)}
    ALL_QUOTES.append(o)
    return o


def col(text, basis, quotes, note=None):
    assert basis in BASIS, basis
    d = {"text": text, "basis": basis, "quotes": [q(x) for x in quotes]}
    if note:
        d["note"] = note
    return d


def qs(*items):
    """其余分区：引文写成原始字符串，稍后由 resolve_all() 统一解析并追加进 ALL_QUOTES。"""
    return list(items)


# ═══════════════════════════════════════════════════════════════════════════
# 内容分区装配
# ═══════════════════════════════════════════════════════════════════════════
sys.path.insert(0, str(Path(__file__).resolve().parent))
import content_a  # noqa: E402
import content_b  # noqa: E402
import content_c  # noqa: E402

TASKS = content_a.build(col, qs)
B = content_b.build(qs)
C = content_c.build(qs)


# ── 全局引文解析：除 tasks 五栏（已由 col() 解析）外，其余分区写的是原始字符串 ──
def resolve_all(o):
    """就地遍历：把裸字符串换成已现算偏移的引文对象。其它类型原样返回。"""
    if isinstance(o, str):
        d = q(o)
        if d is None:
            PROBLEMS.append("无法解析的引文：%r" % o[:60])
            return {"quote": o, "unresolved": True}
        return d
    if isinstance(o, list):
        return [resolve_all(x) for x in o]
    if isinstance(o, dict):
        return {k: resolve_all(v) for k, v in o.items()}
    return o


RESOLVED = {k: resolve_all(v) for k, v in B.items()}

# null 栏位处置表（由 tasks 现算，保证与栏位一一对应）
NULLFIELDS = []
for t in TASKS:
    for f in ("objective", "obstacle", "action", "result", "cost"):
        if t.get(f) is None:
            note = t.get(f + "Note")
            if not note or not note.strip():
                PROBLEMS.append("%s.%s 为 null 但没有 %sNote" % (t["id"], f, f))
            NULLFIELDS.append({"task": t["id"], "field": f, "why": note})
