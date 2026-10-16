# -*- coding: utf-8 -*-
"""READER 任务 read:sanguo:L1:0099 的引用核验工具。

所有 quote 都必须能在 docs[0].text 里逐字 find 到，且落在本单元区间内。
定位口径：全文 codepoint 偏移（不是切片偏移）。

为什么 voice 掩码要**局部重算**（本单元的真实教训）：
全书的 “ 有 9327 个、” 只有 9263 个（净多 64 个未闭合的左引号），
所以「从全书开头累加深度」的做法会漂移：进入本单元时钳位深度已达 52，
连「却说陈式引兵行不数里……」这种纯叙述句都会被判成 character。
本工具改为**从本单元起点 depth=0 起算**，并显式登记两处缺右引号
（见 MASK_REPAIRS，正文原文一字未改），修复后本单元末尾 depth 回到 0。
"""
import hashlib
import json
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
DOCS = ROOT / 'data/cache/fe42d01f3826fe8096f86614.docs.json'
GRAPH = ROOT / 'data/cache/fe42d01f3826fe8096f86614.json'

START, END = 504841, 510210
UNIT_HEAD = '第一百回\u3000汉兵劫寨破曹真\u3000武侯斗阵辱仲达'

_raw = DOCS.read_bytes()
SOURCE_HASH = hashlib.sha256(_raw).hexdigest()
DOCS_JSON = json.loads(_raw.decode('utf-8'))
TEXT = DOCS_JSON[0]['text']
TEXT_SHA = hashlib.sha256(TEXT.encode('utf-8')).hexdigest()
SEGMENT = TEXT[START:END]
SEGMENT_SHA = hashlib.sha256(SEGMENT.encode('utf-8')).hexdigest()

# ── 缺右引号的两处（原文如此，照录不改字）──────────────────────────
# X01：`孔明曰：“先布阵我看。懿入中军帐下，…` —— 「我看。」后缺 ”
MASK_REPAIR_1_AT = TEXT.find('懿入中军帐下，手执黄旗招飐')
# X02：`后主惊讶曰：“似此如之奈何？宦官曰：“可诏还成都，…` —— 「奈何？」后缺 ”
MASK_REPAIR_2_AT = TEXT.find('宦官曰：“可诏还成都，削其兵权，免生叛逆。”')
MASK_REPAIRS = [
    {'id': 'MR1', 'missingCloseBefore': MASK_REPAIR_1_AT,
     'context': TEXT[MASK_REPAIR_1_AT - 24:MASK_REPAIR_1_AT + 18]},
    {'id': 'MR2', 'missingCloseBefore': MASK_REPAIR_2_AT,
     'context': TEXT[MASK_REPAIR_2_AT - 24:MASK_REPAIR_2_AT + 18]},
]
_REPAIR_POINTS = sorted(r['missingCloseBefore'] for r in MASK_REPAIRS)

# ── 局部引号掩码 ────────────────────────────────────────────────────
INSIDE = [False] * len(TEXT)
_depth = 0
for _i in range(START, END):
    if _i in _REPAIR_POINTS:
        _depth = max(0, _depth - 1)     # 补一个虚拟右引号
    _c = TEXT[_i]
    if _c == '\u201c':
        _depth += 1
        INSIDE[_i] = True
    elif _c == '\u201d':
        INSIDE[_i] = True
        _depth = max(0, _depth - 1)
    else:
        INSIDE[_i] = _depth > 0
DEPTH_AT_END = _depth

PROBLEMS = []
_SEEN = {}


def _occurrences(q):
    out = []
    i = TEXT.find(q)
    while i >= 0:
        out.append(i)
        i = TEXT.find(q, i + 1)
    return out


def q(text, nth=None, why=''):
    """构造一条 quoteRef，并核验它逐字命中原文、位于区间内。

    nth=None（默认）时自动选取落在本单元区间内的那一次出现。
    """
    if not isinstance(text, str) or not text:
        PROBLEMS.append('空 quote（%s）' % why)
        return None
    occ = _occurrences(text)
    if not occ:
        PROBLEMS.append('引文在 docs[0].text 中 find 不到：%r（%s）' % (text, why))
        return None
    in_range_idx = [i for i, o in enumerate(occ) if START <= o and o + len(text) <= END]
    if nth is None:
        if not in_range_idx:
            PROBLEMS.append('引文在区间 [%d,%d) 内没有出现（全书共 %d 次）：%r（%s）'
                            % (START, END, len(occ), text, why))
            return None
        idx = in_range_idx[0]
    else:
        if nth > len(occ):
            PROBLEMS.append('第 %d 次出现不存在（共 %d 次）：%r（%s）' % (nth, len(occ), text, why))
            return None
        idx = nth - 1
        if idx not in in_range_idx:
            PROBLEMS.append('指定的第 %d 次出现不在本单元区间内：%r（%s）' % (nth, text, why))
            return None
    start = occ[idx]
    end = start + len(text)
    inside = sum(1 for k in range(start, end) if INSIDE[k])
    frac = inside / float(len(text))
    if frac == 0.0:
        voice = 'narration'
    elif frac == 1.0:
        voice = 'character'
    else:
        voice = 'mixed'
    return {
        'quote': text,
        'start': start,
        'end': end,
        'sourceHash': SOURCE_HASH,
        'globalOccurrences': len(occ),
        'nthOccurrence': idx + 1,
        'inRange': True,
        'inRangeOccurrences': len(in_range_idx),
        'voiceSurface': voice,
    }


def qs(*items):
    """qs('引文', ('引文', 2)) 形式批量构造。"""
    out = []
    for it in items:
        if isinstance(it, str):
            out.append(q(it))
        else:
            out.append(q(it[0], it[1] if len(it) > 1 else None))
    return [x for x in out if x is not None]


def col(text, quotes, basis='explicit', note=''):
    refs = [x for x in quotes if x is not None]
    voices = set(r['voiceSurface'] for r in refs)
    if len(voices) == 1:
        voice = voices.pop()
    elif voices:
        voice = 'mixed'
    else:
        voice = None
    if text is None:
        return None
    return {'text': text, 'basis': basis, 'voice': voice, 'quotes': refs}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
