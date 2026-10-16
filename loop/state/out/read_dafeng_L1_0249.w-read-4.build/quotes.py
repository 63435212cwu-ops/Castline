# -*- coding: utf-8 -*-
"""引用登记：所有 quote 在这里集中登记，构建时在 docs[0].text 全文里现定位。"""
import json, hashlib

DOCS = 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
START, END = 1019685, 1026579
SRC_HASH = 'fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839'

_d = json.load(open(DOCS, encoding='utf-8'))
TEXT = _d[0]['text']

def _file_sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def selftest():
    errs = []
    if _file_sha256(DOCS) != SRC_HASH:
        errs.append('docs.json 文件哈希与任务声明不符')
    if TEXT[START:END][:len('第二十章 头脑风暴')] != '第二十章 头脑风暴':
        errs.append('切片未以本单元标题开头：%r' % TEXT[START:START+20])
    if len(TEXT[START:END]) != END - START:
        errs.append('切片长度不符')
    return errs

_cache = {}
FAILURES = []

class _QuoteFail(Exception):
    pass

def Q(q):
    """定位引文：必须在 [START,END) 内唯一命中；返回 quoteRef。"""
    if q in _cache:
        return dict(_cache[q])
    idxs = []
    i = TEXT.find(q)
    while i >= 0:
        idxs.append(i)
        i = TEXT.find(q, i + 1)
    inr = [x for x in idxs if START <= x < END]
    if len(inr) != 1:
        FAILURES.append({'quote': q, 'n_total': len(idxs), 'n_in_range': len(inr), 'in_range': inr})
        raise _QuoteFail(q)
    s = inr[0]
    e = s + len(q)
    ref = {'quote': q, 'start': s, 'end': e, 'sourceHash': SRC_HASH}
    if TEXT[s:e] != q:
        raise SystemExit('回读不成立 :: %r' % q[:80])
    _cache[q] = ref
    return dict(ref)

def QL(qs):
    out = []
    for q in qs:
        try:
            out.append(Q(q))
        except _QuoteFail:
            out.append({'_QUOTE_FAIL': q[:120]})
    return out
