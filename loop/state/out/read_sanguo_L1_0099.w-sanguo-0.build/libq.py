# -*- coding: utf-8 -*-
"""READER read:sanguo:L1:0099 的引用核验库（工具，放在仓库外，不写仓库）。

口径：
  · quote 必须是 docs[0].text 的逐字子串
  · start/end 是**全文 codepoint 偏移**（不是切片偏移）
  · sourceHash 是整个 docs.json 文件的 sha256

引号掩码局部重算（本单元的真实情况）：
  本单元区间内 “ 有 75 个、” 只有 73 个（净多 2 个未闭合左引号）：
    MR1 @508388 前：`孔明曰：“先布阵我看。懿入中军帐下…` —— 「我看。」后缺 ”
    MR2 @509483 前：`后主惊讶曰：“似此如之奈何？宦官曰：“…` —— 「奈何？」后缺 ”
  若从全书开头累加深度会漂移（全书 “ 9327 / ” 9263）。此处**从本单元起点 depth=0 起算**
  并在两处补虚拟右引号，正文一字未改；修复后区间末尾 depth 回到 0。
"""
import hashlib
import json
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
DOCS = ROOT / 'data/cache/fe42d01f3826fe8096f86614.docs.json'

START, END = 504841, 510210
UNIT_HEAD = '第一百回\u3000汉兵劫寨破曹真\u3000武侯斗阵辱仲达'

_raw = DOCS.read_bytes()
SOURCE_HASH = hashlib.sha256(_raw).hexdigest()
DOCS_JSON = json.loads(_raw.decode('utf-8'))
TEXT = DOCS_JSON[0]['text']
TEXT_SHA = hashlib.sha256(TEXT.encode('utf-8')).hexdigest()
SEGMENT = TEXT[START:END]
SEGMENT_SHA = hashlib.sha256(SEGMENT.encode('utf-8')).hexdigest()

R1 = TEXT.find('懿入中军帐下，手执黄旗招飐')
R2 = TEXT.find('宦官曰：“可诏还成都，削其兵权，免生叛逆。”')
MASK_REPAIRS = [
    {'id': 'MR1', 'at': R1, 'why': '「先布阵我看。」后缺右引号（原文如此）',
     'context': TEXT[R1 - 16:R1 + 12]},
    {'id': 'MR2', 'at': R2, 'why': '「似此如之奈何？」后缺右引号（原文如此）',
     'context': TEXT[R2 - 16:R2 + 12]},
]
_REPAIR_POINTS = sorted(r['at'] for r in MASK_REPAIRS)

INSIDE = [False] * len(TEXT)
_depth = 0
for _i in range(START, END):
    if _i in _REPAIR_POINTS:
        _depth = max(0, _depth - 1)
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


def _occ(q):
    out, i = [], TEXT.find(q)
    while i >= 0:
        out.append(i)
        i = TEXT.find(q, i + 1)
    return out


def q(text, nth=None, why=''):
    if not isinstance(text, str) or not text:
        PROBLEMS.append('空 quote（%s）' % why)
        return None
    occ = _occ(text)
    if not occ:
        PROBLEMS.append('find 不到：%r（%s）' % (text, why))
        return None
    inr = [i for i, o in enumerate(occ) if START <= o and o + len(text) <= END]
    if nth is None:
        if not inr:
            PROBLEMS.append('区间内无此句（全书 %d 次）：%r（%s）' % (len(occ), text, why))
            return None
        idx = inr[0]
    else:
        if nth > len(occ):
            PROBLEMS.append('第 %d 次不存在（共 %d）：%r（%s）' % (nth, len(occ), text, why))
            return None
        idx = nth - 1
        if idx not in inr:
            PROBLEMS.append('第 %d 次不在区间内：%r（%s）' % (nth, text, why))
            return None
    s = occ[idx]
    e = s + len(text)
    inside = sum(1 for k in range(s, e) if INSIDE[k])
    frac = inside / float(len(text))
    voice = 'narration' if frac == 0.0 else ('character' if frac == 1.0 else 'mixed')
    return {'quote': text, 'start': s, 'end': e, 'sourceHash': SOURCE_HASH,
            'globalOccurrences': len(occ), 'nthOccurrence': idx + 1,
            'inRange': True, 'inRangeOccurrences': len(inr), 'voiceSurface': voice}


def qs(*items):
    out = []
    for it in items:
        if it is None:
            continue
        if isinstance(it, str):
            out.append(q(it))
        else:
            out.append(q(it[0], it[1] if len(it) > 1 else None,
                         it[2] if len(it) > 2 else ''))
    return [x for x in out if x is not None]


def col(text, quotes, basis='explicit', note=''):
    refs = [x for x in quotes if x is not None]
    voices = set(r['voiceSurface'] for r in refs)
    voice = (voices.pop() if len(voices) == 1 else ('mixed' if voices else None))
    if text is None:
        return None
    return {'text': text, 'basis': basis, 'voice': voice, 'quotes': refs}


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def qx(a, b, nth=None, why=''):
    """按**锚点**从原文切出引文，避免手打标点造成的不逐字。

    a: 起始锚（含），b: 结束锚（含）。返回 TEXT[i:j+len(b)]，i 为 a 首次出现处。
    """
    i = TEXT.find(a)
    if i < 0:
        PROBLEMS.append('起始锚找不到：%r（%s）' % (a, why))
        return None
    j = TEXT.find(b, i)
    if j < 0:
        PROBLEMS.append('结束锚找不到：%r（%s）' % (b, why))
        return None
    return q(TEXT[i:j + len(b)], nth, why)


def qxs(*items):
    out = []
    for it in items:
        if it is None:
            continue
        if isinstance(it, str):
            out.append(q(it))
        elif len(it) == 2:
            out.append(qx(it[0], it[1]))
        else:
            out.append(qx(it[0], it[1], it[2], it[3] if len(it) > 3 else ''))
    return [x for x in out if x is not None]
