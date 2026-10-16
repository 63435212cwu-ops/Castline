# -*- coding: utf-8 -*-
"""READER 任务 read:sanguo:L1:0097 的引用核验工具。

所有 quote 都必须能在 docs[0].text 里逐字 find 到，且落在本单元区间内。
定位口径：全文 codepoint 偏移（不是切片偏移）。
"""
import hashlib
import json
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
DOCS = ROOT / 'data/cache/fe42d01f3826fe8096f86614.docs.json'
GRAPH = ROOT / 'data/cache/fe42d01f3826fe8096f86614.json'

START, END = 493949, 499135
UNIT_HEAD = '第九十八回\u3000追汉军王双受诛\u3000袭陈仓武侯取胜'

_raw = DOCS.read_bytes()
SOURCE_HASH = hashlib.sha256(_raw).hexdigest()
DOCS_JSON = json.loads(_raw.decode('utf-8'))
TEXT = DOCS_JSON[0]['text']
TEXT_SHA = hashlib.sha256(TEXT.encode('utf-8')).hexdigest()
SEGMENT = TEXT[START:END]
SEGMENT_SHA = hashlib.sha256(SEGMENT.encode('utf-8')).hexdigest()

# 「引号内」掩码：用于机械判定 quote 落在叙述层还是人物话语
_in_quote = [False] * len(TEXT)
_depth = 0
for _i, _c in enumerate(TEXT):
    if _c == '\u201c':          # “
        _depth += 1
        _in_quote[_i] = True
    elif _c == '\u201d':        # ”
        _in_quote[_i] = True
        _depth = max(0, _depth - 1)
    else:
        _in_quote[_i] = _depth > 0

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

    nth=None（默认）时**自动选取落在本单元区间内的那一次出现**：
    实测多个短语在本区间之前就已出现过（例如「可将计就计而行。」
    在全书更早的位置另有出处），若取首次出现就会把偏移落到区间之外。
    显式给 nth 时按全局第 nth 次出现取，仍会校验是否在区间内。
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
            PROBLEMS.append('引文在区间 [%d,%d) 内没有出现（全书共 %d 次，均在区间外）：%r（%s）'
                            % (START, END, len(occ), text, why))
            return None
        idx = in_range_idx[0]
    else:
        if nth > len(occ):
            PROBLEMS.append('第 %d 次出现不存在（共 %d 次）：%r（%s）'
                            % (nth, len(occ), text, why))
            return None
        idx = nth - 1
        if idx not in in_range_idx:
            PROBLEMS.append('指定的第 %d 次出现不在本单元区间内（该引文在区间内有 %d 次）：%r（%s）'
                            % (nth, len(in_range_idx), text, why))
            return None
    start = occ[idx]
    end = start + len(text)
    inside = sum(1 for k in range(start, end) if _in_quote[k])
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


def qs(*pairs):
    """qs(('引文',), ('引文', 2)) 形式批量构造。"""
    out = []
    for p in pairs:
        if isinstance(p, str):
            out.append(q(p))
        else:
            out.append(q(p[0], p[1] if len(p) > 1 else None))
    return [x for x in out if x is not None]


def col(text, quotes, basis='explicit', note=''):
    refs = [x for x in quotes if x is not None]
    voices = set(r['voiceSurface'] for r in refs)
    if len(voices) == 1:
        voice = voices.pop()
    elif voices == {'narration', 'character'}:
        voice = 'mixed'
    elif voices:
        voice = 'mixed'
    else:
        voice = None
    if text is None:
        return None
    return {'text': text, 'basis': basis, 'voice': voice, 'quotes': refs}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
