#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复算脚本（**不 import build_candidate.py，也不 import content_0243.py**）。

存在的理由：构建脚本自己验自己不算验证。这里独立地
  · 自己重新切段/断句（正则另写一遍）；
  · 从**候选文件**读 quote 字符串，自己重新 `find` 偏移，再与候选声明的 start/end 比对
    —— 而不是复用构建期算好的偏移；
  · 五栏独立性改用**字符区间重叠**判定（与切句规则无关）；
  · 行内括号独立重扫（构建期漏掉的形态在这里会露出来）。

退出码 0 = 全部判据通过；非 0 = 有判据不过，候选不可提交。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
DOCS = ROOT / 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
TASKF = ROOT / 'loop/state/runs/task-read_dafeng_L3_0243.json'
CAND = ROOT / 'loop/state/out/read_dafeng_L3_0243.candidate.json'

TASK = json.loads(TASKF.read_text(encoding='utf-8'))
S, E = TASK['sourceRange']
DOCS_BYTES = DOCS.read_bytes()
TEXT = json.loads(DOCS_BYTES.decode('utf-8'))[0]['text']
C = json.loads(CAND.read_text(encoding='utf-8'))

checks = []
fails = []


def ck(name, cond, detail=''):
    checks.append((name, bool(cond), detail))
    if not cond:
        fails.append('%s %s' % (name, detail))


# ── 1. 源与边界 ────────────────────────────────────────────────────────
ck('H1 sourceHash 与任务一致', C['source']['sourceHash'] == TASK['sourceHash'])
ck('H2 文件 sha256 复算', hashlib.sha256(DOCS_BYTES).hexdigest() == TASK['sourceHash'])
ck('H3 切片以标题开头', TEXT[S:E].startswith(TASK['unitHead']))
ck('H4 切片 sha256 复算',
   hashlib.sha256(TEXT[S:E].encode('utf-8')).hexdigest() == C['source']['sliceSha256'])
ck('H5 区间长度', C['source']['codepoints'] == E - S)

# ── 2. 独立重切段落 ─────────────────────────────────────────────────────
PARAS = []
for m in re.finditer(r'[^\n]+', TEXT[S:E]):
    a = m.start() + S + (len(m.group(0)) - len(m.group(0).lstrip()))
    b = m.start() + S + len(m.group(0).rstrip())
    if m.group(0).strip():
        PARAS.append((a, b, m.group(0).strip()))
ck('P1 段数复算', len(PARAS) == C['source']['nonEmptyParagraphs'],
   '%d vs %d' % (len(PARAS), C['source']['nonEmptyParagraphs']))


def para_of(pos):
    for i, (a, b, _t) in enumerate(PARAS, 1):
        if a <= pos < b:
            return i
    return None


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
ck('Q0 引文条数 == machineSelfCheck 声明',
   len(Q) == C['machineSelfCheck']['quoteObjectsResolved'],
   '%d vs %s' % (len(Q), C['machineSelfCheck']['quoteObjectsResolved']))

# 漏解析检查：带字符串 quote 却没有 start/end 的 dict = 没算偏移的引文。
# 构建脚本曾经漏掉 speechAsClueNotFact 整块（12 条），这条判据负责不再漏。
dangling = []


def scan_dangling(o, path='$'):
    if isinstance(o, dict):
        if isinstance(o.get('quote'), str) and ('start' not in o or 'end' not in o):
            dangling.append((path, o['quote'][:40]))
            return
        for k, v in o.items():
            scan_dangling(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan_dangling(v, '%s[%d]' % (path, i))


scan_dangling(C)
ck('Q9 没有"有 quote 无偏移"的漏解析引文', not dangling,
   '%d 处：%s' % (len(dangling), dangling[:5]))

bad_verbatim = bad_uniq = bad_range = bad_hash = bad_offset = bad_para = 0
for _p, q in Q:
    s = q['quote']
    occ = [m.start() for m in re.finditer(re.escape(s), TEXT)]
    if q['start'] is None or TEXT[q['start']:q['end']] != s:
        bad_verbatim += 1
        continue
    inr = [o for o in occ if o >= S and o + len(s) <= E]
    if len(inr) != 1:
        bad_uniq += 1
    elif inr[0] != q['start']:
        bad_offset += 1
    if not (q['start'] >= S and q['end'] <= E):
        bad_range += 1
    if q.get('sourceHash') != TASK['sourceHash']:
        bad_hash += 1
    if para_of(q['start']) != q.get('para'):
        bad_para += 1

ck('Q1 全部逐字（text[start:end]==quote）', bad_verbatim == 0, '%d 条不符' % bad_verbatim)
ck('Q2 区间内出现次数恰好 1', bad_uniq == 0, '%d 条不唯一' % bad_uniq)
ck('Q3 偏移与独立 find 一致', bad_offset == 0, '%d 条偏移不符' % bad_offset)
ck('Q4 全部落在 [%d,%d) 内' % (S, E), bad_range == 0, '%d 条越界' % bad_range)
ck('Q5 全部 sourceHash 正确', bad_hash == 0)
ck('Q6 para 字段可复算', bad_para == 0, '%d 条不符' % bad_para)

# occurrence 元数据复算
bad_meta = 0
for _p, q in Q:
    occ = [m.start() for m in re.finditer(re.escape(q['quote']), TEXT)]
    inr = [o for o in occ if o >= S and o + len(q['quote']) <= E]
    if (q.get('wholeTextOccurrences') != len(occ)
            or q.get('occurrencesInRange') != len(inr)
            or q.get('firstOccurrenceAt') != (occ[0] if occ else None)
            or q.get('startIsFirstOccurrence') != (bool(occ) and q['start'] == occ[0])):
        bad_meta += 1
ck('Q7 occurrence 元数据可复算', bad_meta == 0, '%d 条不符' % bad_meta)

# 声明的段号必须真的包含该引文
bad_decl = 0
for _p, q in Q:
    dp = q.get('declaredPara')
    if dp is None:
        continue
    a, b, txt = PARAS[dp - 1]
    if q['quote'] not in txt:
        bad_decl += 1
ck('Q8 声明的段号确实含该引文', bad_decl == 0, '%d 条不符' % bad_decl)

# ── 4. 五栏独立性：字符区间两两不相交 ────────────────────────────────────
FIVE = ('objective', 'obstacle', 'action', 'result', 'cost')
overlaps = []
for t in C['tasks']:
    spans = []
    for f in FIVE:
        col = t.get(f)
        if not col:
            continue
        refs = []

        def collect(o):
            if isinstance(o, dict):
                if 'quote' in o and 'start' in o:
                    refs.append(o)
                else:
                    for v in o.values():
                        collect(v)
            elif isinstance(o, list):
                for v in o:
                    collect(v)
        collect(col)
        for r in refs:
            spans.append((r['start'], r['end'], f))
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b, fa = spans[i]
            c, d, fb = spans[j]
            if a < d and c < b:
                overlaps.append((t['id'], fa, fb, a, b, c, d))
ck('C1 同任务五栏字符区间无重叠', not overlaps, '%d 处：%s' % (len(overlaps), overlaps[:3]))

# 同一引文字符串不得同时出现在同一条任务的两个栏里
cross = []
for t in C['tasks']:
    seen = {}
    for f in FIVE:
        col = t.get(f)
        if not col:
            continue
        refs = []

        def collect2(o):
            if isinstance(o, dict):
                if 'quote' in o and 'start' in o:
                    refs.append(o)
                else:
                    for v in o.values():
                        collect2(v)
            elif isinstance(o, list):
                for v in o:
                    collect2(v)
        collect2(col)
        for r in refs:
            if r['quote'] in seen and seen[r['quote']] != f:
                cross.append((t['id'], seen[r['quote']], f, r['quote'][:40]))
            seen[r['quote']] = f
ck('C2 同任务五栏不共用同一句', not cross, '%d 处：%s' % (len(cross), cross[:3]))

null_no_note = ['%s.%s' % (t['id'], f) for t in C['tasks'] for f in FIVE
                if t.get(f) is None and not t.get(f + 'Note')]
ck('C3 空栏都有同名的 Note', not null_no_note, str(null_no_note))
ck('C4 nullFieldRule 里的条数与实际一致',
   C['nullFieldRule'].count('.cost') + C['nullFieldRule'].count('.action')
   + C['nullFieldRule'].count('.obstacle') == C['machineSelfCheck']['nullFields'],
   C['nullFieldRule'][:80])

# ── 5. 行内括号独立重扫 ──────────────────────────────────────────────────
inline_bad = []


def scan(o, path='$'):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o:
            return
        for k, v in o.items():
            scan(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan(v, '%s[%d]' % (path, i))
    elif isinstance(o, str):
        for m in re.finditer(r'「([^「」]*)」', o):
            if TEXT.find(m.group(1)) < 0:
                inline_bad.append((path, m.group(1)[:50]))


scan(C)
ck('B1 散文「」全部逐字可 find', not inline_bad,
   '%d 处非逐字：%s' % (len(inline_bad), inline_bad[:5]))
ck('B2 machineSelfCheck.inlineNonVerbatim 与实扫一致',
   len(C['machineSelfCheck']['inlineNonVerbatim']) == len(inline_bad))

# ── 6. 覆盖度复算 ───────────────────────────────────────────────────────
cov = set()
for _p, q in Q:
    if q['start'] is not None:
        cov.update(range(q['start'], q['end']))
zero = [i for i, (a, b, _t) in enumerate(PARAS, 1) if not any(o in cov for o in range(a, b))]
ck('V1 零覆盖段数一致', len(zero) == len(C['coverage']['zeroCoveredParagraphs']),
   '%d vs %d' % (len(zero), len(C['coverage']['zeroCoveredParagraphs'])))
touched = {para_of(q['start']) for _p, q in Q if q['start'] is not None}
ck('V2 被引段落数一致',
   len(touched) == C['coverage']['paragraphsTouchedByAtLeastOneQuote'],
   '%d vs %d' % (len(touched), C['coverage']['paragraphsTouchedByAtLeastOneQuote']))
nonspace = sum(1 for ch in TEXT[S:E] if not ch.isspace())
ck('V3 非空码点覆盖率一致',
   abs(round(len(cov) / nonspace, 4) - C['coverage']['quoteUnionRatioOfNonSpace']) < 1e-9,
   '%s vs %s' % (round(len(cov) / nonspace, 4), C['coverage']['quoteUnionRatioOfNonSpace']))

# ── 7. 结构约束 ─────────────────────────────────────────────────────────
REQ = ['tasks', 'causeEdges', 'states', 'foreshadows', 'worldSettings', 'themeReadings']
ck('S0 六个顶层分区齐全', all(k in C for k in REQ),
   '缺 %s' % [k for k in REQ if k not in C])
ck('S1 semanticReview 未声称完成', C['semanticReview'] == 'not-performed')
ck('S2 themeReadings ≤ 2', len(C['themeReadings']) <= 2, str(len(C['themeReadings'])))
for th in C['themeReadings']:
    ck('S3 %s 三件齐全（perspective/support/counter）' % th['id'],
       all(th.get(k) for k in ('perspective', 'support', 'counter')))
for f in C['foreshadows']:
    ck('S4 %s 未回收项写明未回收的是什么' % f['id'],
       f['status'] != 'unresolved' or bool(f.get('unresolvedWhat')))
for w in C['worldSettings']:
    if w['kind'] == 'place':
        ck('S5 %s placeState 合法' % w['id'], w['placeState'] in ('arrived', 'mentioned'))
    elif w['kind'] == 'item':
        ck('S6 %s itemStates 合法' % w['id'],
           isinstance(w['itemStates'], list) and w['itemStates']
           and all(x in ('hold', 'transfer', 'use', 'lose') for x in w['itemStates']))
    elif w['kind'] == 'rule':
        ck('S7 %s institution 合法' % w['id'],
           w['institution'] in ('declared', 'executed', 'misunderstood'))
    else:
        ck('S8 %s kind 合法' % w['id'], False, w['kind'])
# 每条 causeEdge 必须有 trigger 与 mechanism（方向 + 触发）
for ce in C['causeEdges']:
    ck('S9 %s 有 trigger 与 mechanism' % ce['id'],
       bool(ce.get('trigger')) and bool(ce.get('mechanism')))
# 每条断言有 basis；**未回收的伏笔 payoff 是空的、本就没有断言**，不算违规
miss_basis = []


def scan_basis(o, path='$'):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o:
            return
        for k, v in o.items():
            if k == 'basis':
                if v is None and path.endswith('.payoff'):
                    continue          # payoff 为空（未回收）⇒ 没有断言可标 basis
                if v not in ('explicit', 'inferred', 'derived', 'unverified'):
                    miss_basis.append('%s.basis=%r' % (path, v))
            scan_basis(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan_basis(v, '%s[%d]' % (path, i))


scan_basis(C)
ck('S10 basis 取值全部合法', not miss_basis, str(miss_basis[:5]))

# ── 输出 ────────────────────────────────────────────────────────────────
print('独立复算：%d 条判据' % len(checks))
for name, ok, detail in checks:
    if not ok:
        print('  FAIL %s %s' % (name, detail))
print('通过 %d / %d' % (sum(1 for _n, ok, _d in checks if ok), len(checks)))
print('引文 %d 条；段 %d；被引段 %d；非空码点覆盖 %.4f'
      % (len(Q), len(PARAS), len(touched), len(cov) / nonspace))
if fails:
    print('未通过：%d 条' % len(fails))
    sys.exit(1)
print('全部通过。')
