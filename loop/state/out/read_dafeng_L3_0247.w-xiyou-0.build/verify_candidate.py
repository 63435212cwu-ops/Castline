#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复算脚本（**不 import build_candidate.py，也不 import 任何 content_*.py**）。

存在的理由：构建脚本自己验自己不算验证。这里独立地
  · 自己重新切段（正则另写一遍，不复用构建期段落表）；
  · 从**候选文件**读 quote 字符串，自己重新 `find` 偏移，再与候选声明的
    start/end 比对 —— 而不是复用构建期算好的偏移；
  · 五栏独立性改用**字符区间重叠**判定（与切句规则无关）；
  · 行内「」独立重扫（构建期漏掉的形态在这里会露出来）；
  · 独立核对六个内容分区、worldSettings 三态字段、null 栏 Note、unresolved 伏笔说明。

退出码 0 = 全部判据通过；非 0 = 有判据不过，候选不可提交。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
DOCS = ROOT / 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
TASKF = ROOT / 'loop/state/runs/task-read_dafeng_L3_0247.json'
CAND = ROOT / 'loop/state/out/read_dafeng_L3_0247.candidate.json'

TASK = json.loads(TASKF.read_text(encoding='utf-8'))
S, E = TASK['sourceRange']
DOCS_BYTES = DOCS.read_bytes()
TEXT = json.loads(DOCS_BYTES.decode('utf-8'))[0]['text']
SLICE = TEXT[S:E]
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
ck('H3 切片以标题开头', SLICE.startswith(TASK['unitHead']))
ck('H4 切片 sha256 复算',
   hashlib.sha256(SLICE.encode('utf-8')).hexdigest() == C['source']['sliceSha256'])
ck('H5 区间长度', C['source']['codepoints'] == E - S)
ck('H6 sourceHashScope 明说是整文件', '整' in C['source']['sourceHashScope'])
ck('H7 sliceSha256 是附加字段（没覆盖 sourceHash）',
   C['source']['sliceSha256'] != C['source']['sourceHash'])

# ── 2. 独立重切段落 ─────────────────────────────────────────────────────
PARAS = []
for m in re.finditer(r'[^\n]+', SLICE):
    raw = m.group(0)
    st = raw.strip()
    if not st:
        continue
    a = S + m.start() + (len(raw) - len(raw.lstrip()))
    PARAS.append((a, a + len(st), st))
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
ck('Q9 没有「有 quote 无偏移」的漏解析引文', not dangling,
   '%d 处：%s' % (len(dangling), dangling[:5]))

bad_verbatim = bad_uniq = bad_range = bad_hash = bad_offset = bad_para = 0
for _p, q in Q:
    s = q['quote']
    if q['start'] is None or TEXT[q['start']:q['end']] != s:
        bad_verbatim += 1
        continue
    occ = [m.start() for m in re.finditer(re.escape(s), TEXT)]
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


def collect_refs(col):
    refs = []

    def rec(o):
        if isinstance(o, dict):
            if 'quote' in o and 'start' in o:
                refs.append(o)
            else:
                for v in o.values():
                    rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
    rec(col)
    return refs


overlaps = []
cross = []
for t in C['tasks']:
    spans = []
    seen = {}
    for f in FIVE:
        col = t.get(f)
        if not col:
            continue
        for r in collect_refs(col):
            spans.append((r['start'], r['end'], f))
            if r['quote'] in seen and seen[r['quote']] != f:
                cross.append((t['id'], seen[r['quote']], f, r['quote'][:40]))
            seen[r['quote']] = f
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b, fa = spans[i]
            c, d, fb = spans[j]
            if a < d and c < b:
                overlaps.append((t['id'], fa, fb, a, b, c, d))
ck('C1 同任务五栏字符区间无重叠', not overlaps, '%d 处：%s' % (len(overlaps), overlaps[:3]))
ck('C2 同任务五栏不共用同一句', not cross, '%d 处：%s' % (len(cross), cross[:3]))

null_no_note = ['%s.%s' % (t['id'], f) for t in C['tasks'] for f in FIVE
                if t.get(f) is None and not t.get(f + 'Note')]
ck('C3 空栏都有同名的 Note', not null_no_note, str(null_no_note))
ck('C4 nullFieldList 条数与实际一致',
   len(C['machineSelfCheck'].get('nullFieldList') or []) ==
   sum(1 for t in C['tasks'] for f in FIVE if t.get(f) is None),
   '%s vs %d' % (len(C['machineSelfCheck'].get('nullFieldList') or []),
                 sum(1 for t in C['tasks'] for f in FIVE if t.get(f) is None)))
ck('C5 nullFieldRule 里回填的数字与实际一致',
   ('%d 个 null 栏' % sum(1 for t in C['tasks'] for f in FIVE if t.get(f) is None))
   in C['nullFieldRule'], C['nullFieldRule'][:60])
# 每个有值的栏都必须有 basis
missing_basis = []
for t in C['tasks']:
    for f in FIVE:
        if t.get(f) is not None and not t.get(f + 'Basis'):
            missing_basis.append('%s.%s' % (t['id'], f))
ck('C6 有值的栏都带 basis', not missing_basis, str(missing_basis))

# ── 5. 行内「」独立重扫 ──────────────────────────────────────────────────
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
ck('V1b 零覆盖段清单逐项一致',
   sorted(zero) == sorted(C['coverage']['zeroCoveredParagraphs']))
touched = {para_of(q['start']) for _p, q in Q if q['start'] is not None}
ck('V2 被引段落数一致',
   len(touched) == C['coverage']['paragraphsTouchedByAtLeastOneQuote'],
   '%d vs %d' % (len(touched), C['coverage']['paragraphsTouchedByAtLeastOneQuote']))
nonspace = sum(1 for ch in SLICE if not ch.isspace())
ck('V3 非空码点覆盖率一致',
   abs(round(len(cov) / nonspace, 4) - C['coverage']['quoteUnionRatioOfNonSpace']) < 1e-9,
   '%s vs %s' % (round(len(cov) / nonspace, 4), C['coverage']['quoteUnionRatioOfNonSpace']))
ck('V4 覆盖率不超过 1', len(cov) <= nonspace)
ck('V5 区间码点数一致', C['coverage']['sliceCodepoints'] == E - S)

# ── 7. 结构约束 ─────────────────────────────────────────────────────────
REQ = ['tasks', 'causeEdges', 'states', 'foreshadows', 'worldSettings', 'themeReadings']
ck('S0 六个顶层分区齐全', all(k in C for k in REQ),
   '缺 %s' % [k for k in REQ if k not in C])
ck('S1 semanticReview 未声称完成', C['semanticReview'] == 'not-performed')
ck('S2 themeReadings ≤ 2', len(C['themeReadings']) <= 2, str(len(C['themeReadings'])))
for th in C['themeReadings']:
    ck('S3 %s 三件齐全（perspective/support/counter）' % th['id'],
       all(th.get(k) for k in ('perspective', 'support', 'counter')))
    ck('S3b %s counter 非空且不是一句套话' % th['id'],
       len(th.get('counter') or '') > 40, str(len(th.get('counter') or '')))
for f in C['foreshadows']:
    ck('S4 %s 未回收项写明未回收的是什么' % f['id'],
       f['status'] != 'unresolved' or bool(f.get('unresolvedWhat')))
    ck('S4b %s 有 setup' % f['id'], bool(f.get('setup', {}).get('what')))
    ck('S4c %s payoff 为空时必须 unresolved' % f['id'],
       bool(f.get('payoff')) or f['status'] == 'unresolved')
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
        ck('S7b %s rule 有 explain' % w['id'], bool(w.get('explain')))
    else:
        ck('S8 %s kind 合法' % w['id'], False, w['kind'])
# 每条 causeEdge 必须有 trigger 与 mechanism（方向 + 触发）
for ce in C['causeEdges']:
    ck('S9 %s 有 trigger 与 mechanism' % ce['id'],
       bool(ce.get('trigger')) and bool(ce.get('mechanism')))
# 被拒边必须写明 why，且不得带 trigger/mechanism（否则就是把相邻当因果）
for re_ in C.get('rejectedEdges') or []:
    ck('S9b %s（被拒边）写明 why' % re_['id'], bool(re_.get('why')))
    ck('S9c %s（被拒边）没有偷偷连边' % re_['id'],
       not re_.get('trigger') and not re_.get('mechanism'))
# states 前值/后值/锚点齐全
for s in C['states']:
    for k in ('before', 'after', 'anchor'):
        ck('S11 %s.%s 非空且带引文' % (s['id'], k),
           bool(s.get(k)) and bool(s.get(k + 'Quotes')))
    ck('S11b %s 前值/后值带 basis' % s['id'],
       bool(s.get('beforeBasis')) and bool(s.get('afterBasis')))

# 每条断言有 basis；未回收伏笔的 payoff 是空的、本就没有断言
miss_basis = []


def scan_basis(o, path='$'):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o:
            return
        for k, v in o.items():
            if k == 'basis':
                if v is None and path.endswith('.payoff'):
                    continue
                if v not in ('explicit', 'inferred', 'derived', 'unverified'):
                    miss_basis.append('%s.basis=%r' % (path, v))
            scan_basis(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan_basis(v, '%s[%d]' % (path, i))


scan_basis(C)
ck('S10 basis 取值全部合法', not miss_basis, str(miss_basis[:5]))
ck('S12 selfCritique ≥ 3 条', len(C['selfCritique']) >= 3, str(len(C['selfCritique'])))
ck('S13 unknowns 非空（读不出来的要写出来）', len(C['unknowns']) > 0)
ck('S14 没有重号 id（每个分区内）',
   all(len(v) == len({x['id'] for x in v})
       for k, v in C.items() if isinstance(v, list) and v and isinstance(v[0], dict) and 'id' in v[0]),
   '有重复 id')

# ── 7b. 标签字段【】复算（独立于构建脚本，见 build §13c）─────────────────
# 真实缺陷：F04.name 曾写「【第二天才好】」，全本 476 万字零命中；
# W01.name 曾写「【后宫之中想去哪就去哪】」，原文实为「后宫之中，你想去哪就去哪」（漏一个「，你」）。
# 这里在**最终产物**上独立重扫 name/title，不信任构建脚本的自报字段。
LBL_BAD = []


def _scan_labels(o, path='$'):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ('name', 'title') and isinstance(v, str):
                for m in re.finditer(r'【([^【】]+)】', v):
                    frag = m.group(1)
                    if len(frag) < 4 or any(a in frag for a in ('≠', '→', '=', '+')):
                        continue
                    if TEXT.find(frag) < 0:
                        LBL_BAD.append('%s.%s【%s】' % (path, k, frag[:40]))
            _scan_labels(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _scan_labels(v, '%s[%d]' % (path, i))


_scan_labels(C)
ck('S15 标签【】逐字可 find（或为自造对照式命名）', not LBL_BAD, str(LBL_BAD[:5]))
ck('S16 构建脚本自报的 labelNotInSource 与独立复算一致',
   [list(x) for x in C['machineSelfCheck'].get('labelNotInSource', [])] == [],
   str(C['machineSelfCheck'].get('labelNotInSource'))[:120])

# ── 7c. 零覆盖段落分类：独立重算，不信任构建脚本的自报分类 ────────────────
# 理由：首版 note 用「多为…」把 9 段真实叙事段的漏引文掩盖过去。分类必须可复算，
# 否则「多为」这种形容词会让复核者以为零覆盖全是排版噪声。
_zc = C['coverage']
_cats = _zc.get('zeroCoveredByCategory') or {}
_flat = [i for v in _cats.values() for i in v]
ck('C1 零覆盖分类是 zeroCoveredParagraphs 的一个划分',
   sorted(_flat) == sorted(_zc['zeroCoveredParagraphs']),
   '%d vs %d' % (len(_flat), len(_zc['zeroCoveredParagraphs'])))
ck('C2 zeroCoveredCounts 与分类列表一致',
   _zc.get('zeroCoveredCounts') == {k: len(v) for k, v in _cats.items()}, 'counts 不符')
# 独立重算「实打实叙事段」：不含 XML/分隔符样、非附言、长度 > 22
_post = None
for _i, (_a, _b, _t) in enumerate(PARAS, 1):
    if '更新时间更改说明' in _t:
        _post = _i
        break
_recomputed = [i for i in _zc['zeroCoveredParagraphs']
               if not (set(PARAS[i - 1][2]) <= set('. -'))
               and not (_post and i >= _post)
               and len(PARAS[i - 1][2]) > 22]
ck('C3 独立复算「实打实叙事段」与候选一致',
   _recomputed == _cats.get('substantive'),
   '复算 %s vs 候选 %s' % (_recomputed, _cats.get('substantive')))
ck('C4 候选如实报出了 substantive 类（不写 0 蒙混）',
   len(_cats.get('substantive') or []) >= 1,
   'substantive=%s' % (_cats.get('substantive'),))

# ── 8. 只读证据文件（防"我先写好结论再补引文"）─────────────────────────
# 反向核验：候选里每条任务的每一栏，其引文必须**真的落在该栏 Note 描述的位置附近**
# 这里做一条粗但有效的检查：五栏引文的段号必须落在该任务所有引文段号的 min..max 内
for t in C['tasks']:
    ps = [r['para'] for f in FIVE if t.get(f) for r in collect_refs(t[f])]
    if ps:
        ck('R1 %s 引文段号跨度合理（≤80 段）' % t['id'], max(ps) - min(ps) <= 80,
           'span=%d' % (max(ps) - min(ps)))

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
