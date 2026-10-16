#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复算脚本（不复用 build_candidate.py 的任何逻辑）。

用途：核对候选里所有**可机器复算**的声明，以及重新做一遍句/分句级未覆盖扫描。
与构建期的区别（这是它存在的理由）：
  · 自己重新切段/句/分句（正则独立写一遍，不 import 构建脚本）；
  · 从**候选文件**读 quote 字符串，自己重新 find 偏移，再与候选声明的 start/end 比对
    —— 而不是复用构建期已经算好的偏移；
  · 五栏独立性改用**字符区间重叠**判定（与切句规则无关），避免同一条规则自己验自己；
  · 行内「…」独立重扫一遍（0178 CE1 的缺口）。

退出码 0 = 全通过；非 0 = 有判据不过。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
DOCS = ROOT / 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
TASKF = ROOT / 'loop/state/runs/task-read_dafeng_L2_0182.json'
CAND = ROOT / 'loop/state/out/read_dafeng_L2_0182.candidate.json'

TASK = json.loads(TASKF.read_text(encoding='utf-8'))
S, E = TASK['sourceRange']
TEXT = json.loads(DOCS.read_bytes().decode('utf-8'))[0]['text']
C = json.loads(CAND.read_text(encoding='utf-8'))

fails = []
checks = []


def ck(name, cond, detail=''):
    checks.append((name, bool(cond), detail))
    if not cond:
        fails.append('%s %s' % (name, detail))


# ── 1. 源与边界 ────────────────────────────────────────────────────────
import hashlib
ck('H1 sourceHash 一致', C['source']['sourceHash'] == TASK['sourceHash'])
ck('H2 文件 sha256', hashlib.sha256(DOCS.read_bytes()).hexdigest() == TASK['sourceHash'])
ck('H3 切片以标题开头', TEXT[S:E].startswith(TASK['unitHead']))
ck('H4 segmentSha256', hashlib.sha256(TEXT[S:E].encode()).hexdigest() == C['source']['segmentSha256'])

# ── 2. 独立重切单元 ─────────────────────────────────────────────────────
PARAS = [(m.start() + S + (len(m.group(0)) - len(m.group(0).lstrip())),
          m.start() + S + len(m.group(0).rstrip()), m.group(0).strip())
         for m in re.finditer(r'[^\n]+', TEXT[S:E]) if m.group(0).strip()]
ck('P1 段数一致', len(PARAS) == C['source']['nonEmptyParagraphs'],
   '%d vs %d' % (len(PARAS), C['source']['nonEmptyParagraphs']))


def cut(regex):
    out = []
    for pno, (a, b, t) in enumerate(PARAS, 1):
        for m in regex.finditer(t):
            if m.group(0):
                out.append((pno, a + m.start(), a + m.end(), m.group(0)))
    return out


SENTS = cut(re.compile(r'[^。！？]*[。！？]|[^。！？]+$'))
CLAUSES = cut(re.compile(r'[^，。！？；：]*[，。！？；：]|[^，。！？；：]+$'))
ck('P2 句数一致', len(SENTS) == C['source']['sentenceUnits'],
   '%d vs %d' % (len(SENTS), C['source']['sentenceUnits']))
ck('P3 分句数一致', len(CLAUSES) == C['source']['clauseUnits'],
   '%d vs %d' % (len(CLAUSES), C['source']['clauseUnits']))

# ── 3. 全量引文复算 ─────────────────────────────────────────────────────
Q = []


def walk(o, path='$'):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o and 'end' in o:
            Q.append((path, o))
        else:
            for k, v in o.items():
                walk(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, '%s[%d]' % (path, i))


walk(C)
ck('Q1 引文条数 == machineAssertions',
   len(Q) == C['machineAssertions']['quoteObjectsResolved'],
   '%d vs %s' % (len(Q), C['machineAssertions']['quoteObjectsResolved']))

bad_verbatim = bad_offset = bad_range = bad_uniq = bad_hash = 0
for path, q in Q:
    s = q['quote']
    occ = [m.start() for m in re.finditer(re.escape(s), TEXT)]
    if TEXT[q['start']:q['end']] != s:
        bad_verbatim += 1
    inr = [o for o in occ if o >= S and o + len(s) <= E]
    if len(inr) != 1:
        bad_uniq += 1
    elif inr[0] != q['start']:
        bad_offset += 1
    if not (q['start'] >= S and q['end'] <= E):
        bad_range += 1
    if q.get('sourceHash') != TASK['sourceHash']:
        bad_hash += 1
ck('Q2 全部逐字', bad_verbatim == 0, '%d 条不符' % bad_verbatim)
ck('Q3 全部区间内唯一', bad_uniq == 0, '%d 条不唯一' % bad_uniq)
ck('Q4 偏移与 find 一致', bad_offset == 0, '%d 条偏移不符' % bad_offset)
ck('Q5 全部在区间内', bad_range == 0)
ck('Q6 全部 sourceHash 正确', bad_hash == 0)

# occurrence 元数据复算
bad_meta = 0
for path, q in Q:
    occ = [m.start() for m in re.finditer(re.escape(q['quote']), TEXT)]
    inr = [o for o in occ if o >= S and o + len(q['quote']) <= E]
    if (q.get('wholeTextOccurrences') != len(occ)
            or q.get('occurrencesInRange') != len(inr)
            or q.get('firstOccurrenceAt') != occ[0]
            or q.get('startIsFirstOccurrence') != (q['start'] == occ[0])
            or q.get('startIsFirstOccurrenceInRange') != (q['start'] == inr[0])):
        bad_meta += 1
ck('Q7 occurrence 元数据可复算', bad_meta == 0, '%d 条不符' % bad_meta)

# para 字段复算
bad_para = 0
for path, q in Q:
    p = next((i for i, (a, b, t) in enumerate(PARAS, 1) if a <= q['start'] < b), None)
    if p != q.get('para'):
        bad_para += 1
ck('Q8 para 字段可复算', bad_para == 0, '%d 条不符' % bad_para)

# ── 4. 同任务五栏：字符区间重叠（与切句无关）────────────────────────────
FIVE = ['objective', 'obstacle', 'action', 'result', 'cost']
overlap = 0
for t in C['tasks']:
    spans = []
    for f in FIVE:
        col = t.get(f)
        if not col:
            continue

        def collect(o):
            if isinstance(o, dict):
                if 'quote' in o and 'start' in o:
                    spans.append((o['start'], o['end'], f))
                else:
                    for v in o.values():
                        collect(v)
            elif isinstance(o, list):
                for v in o:
                    collect(v)
        collect(col)
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b, fa = spans[i]
            c, d, fb = spans[j]
            if a < d and c < b:
                overlap += 1
ck('C1 五栏字符区间无重叠', overlap == 0, '%d 处重叠' % overlap)

null_no_note = 0
for t in C['tasks']:
    for f in FIVE:
        if t.get(f) is None and not t.get(f + 'Note'):
            null_no_note += 1
ck('C2 空栏都有 Note', null_no_note == 0)

# ── 5. 行内「…」独立重扫（CE1 缺口）─────────────────────────────────────
inline_bad = []


def scan(o, path='$'):
    if isinstance(o, dict):
        for k, v in o.items():
            scan(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan(v, '%s[%d]' % (path, i))
    elif isinstance(o, str):
        for m in re.finditer(r'「([^「」]*)」', o):
            if TEXT.find(m.group(1)) < 0:
                inline_bad.append((path, m.group(1)))


scan(C)
ck('B1 散文「…」全部逐字', not inline_bad, '%d 处非逐字：%s' % (len(inline_bad), inline_bad[:5]))
ck('B2 inlineQuoteAudit 声明与实扫一致',
   C['inlineQuoteAudit']['nonVerbatimCount'] == len(inline_bad))

# 嵌套同类括号（『…『…』…』／「…「…」…」）：fixer 批量替换可能留下的假引文
nested = []


def scan_nested(o, path='$'):
    if isinstance(o, dict):
        for k, v in o.items():
            scan_nested(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan_nested(v, '%s[%d]' % (path, i))
    elif isinstance(o, str):
        for pat in (r'『[^『』]*『', r'「[^「」]*「'):
            for m in re.finditer(pat, o):
                nested.append((path, o[max(0, m.start() - 20):m.start() + 50]))


scan_nested(C)
ck('B3 无嵌套同类括号', not nested, '%d 处：%s' % (len(nested), nested[:3]))

# ── 6. 三级覆盖独立复算 ─────────────────────────────────────────────────
cov = set()
for _p, q in Q:
    cov.update(range(q['start'], q['end']))


def zero_count(units):
    n = 0
    for u in units:
        a, b = (u[0], u[1]) if len(u) == 3 else (u[1], u[2])
        if not any(o in cov for o in range(a, b)):
            n += 1
    return n


cd = C['coverageDeclaration']
ck('V1 段级零覆盖一致', zero_count(PARAS) == len(cd['zeroCoveredParagraphs']),
   '%d vs %d' % (zero_count(PARAS), len(cd['zeroCoveredParagraphs'])))
ck('V2 句级零覆盖一致', zero_count(SENTS) == len(cd['zeroCoveredSentences']),
   '%d vs %d' % (zero_count(SENTS), len(cd['zeroCoveredSentences'])))
ck('V3 分句级零覆盖一致', zero_count(CLAUSES) == len(cd['zeroCoveredClauses']),
   '%d vs %d' % (zero_count(CLAUSES), len(cd['zeroCoveredClauses'])))
touched = {next(i for i, (a, b, t) in enumerate(PARAS, 1) if a <= q['start'] < b) for _p, q in Q}
ck('V4 段覆盖数一致', len(touched) == cd['paragraphsTouchedByAtLeastOneQuote'],
   '%d vs %d' % (len(touched), cd['paragraphsTouchedByAtLeastOneQuote']))
ck('V5 字符覆盖率一致',
   abs(round(len(cov) / len(TEXT[S:E]), 4) - cd['charCoverageRatio']) < 1e-9,
   '%s vs %s' % (round(len(cov) / len(TEXT[S:E]), 4), cd['charCoverageRatio']))

# ── 7. sceneBeats range 复算 ────────────────────────────────────────────
bad_range2 = 0
for b in C['sceneBeats']:
    lo = min(x['start'] for x in b['quotes'])
    hi = max(x['end'] for x in b['quotes'])
    if b['range'] != [lo, hi] or b['rangeLen'] != hi - lo:
        bad_range2 += 1
ck('S1 sceneBeats range 一致', bad_range2 == 0, '%d 条不符' % bad_range2)

# ── 8. 结构约束 ─────────────────────────────────────────────────────────
ck('T1 themeReadings ≤ 2', len(C['themeReadings']) <= 2, str(len(C['themeReadings'])))
for th in C['themeReadings']:
    ck('T2 %s 三件齐全' % th['id'],
       all(th.get(k) for k in ('perspective', 'support', 'counter')))
for f in C['foreshadows']:
    ck('F1 %s 未回收有理由' % f['id'],
       f['status'] != 'unresolved' or bool(f.get('unresolvedReason')))
for w in C['worldSettings']:
    if w['kind'] == 'place':
        ck('W1 %s placeState 合法' % w['id'], w['placeState'] in ('arrived', 'mentioned'))
    elif w['kind'] == 'item':
        ck('W2 %s itemStates 合法' % w['id'],
           isinstance(w['itemStates'], list) and w['itemStates']
           and all(x in ('hold', 'transfer', 'use', 'lose') for x in w['itemStates']))
    elif w['kind'] == 'rule':
        ck('W3 %s institution 合法' % w['id'],
           w['institution'] in ('declared', 'executed', 'misunderstood'))
ck('D1 semanticReview 未声称完成', C['semanticReview'] == 'not-performed')

# ── 输出 ────────────────────────────────────────────────────────────────
print('独立复算：%d 条判据' % len(checks))
for name, ok, detail in checks:
    if not ok:
        print('  FAIL %s %s' % (name, detail))
print('通过 %d / %d' % (sum(1 for _n, ok, _d in checks if ok), len(checks)))
print('引文 %d 条；段 %d 句 %d 分句 %d；字符覆盖 %.4f'
      % (len(Q), len(PARAS), len(SENTS), len(CLAUSES), len(cov) / len(TEXT[S:E])))
if fails:
    print('未通过：%d 条' % len(fails))
    sys.exit(1)
print('全部通过。')
