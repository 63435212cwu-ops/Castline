#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立反向复核脚本：verify:sanguo:L0:0116（复核者 w-verify-3）。

纪律：不 import 候选生成器/作者任何模块；从磁盘重读 docs.json；
所有偏移由本脚本现场 find 生成，不手抄。
"""
import json, hashlib, re, sys, random

DOCS = 'data/cache/fe42d01f3826fe8096f86614.docs.json'
CAND = 'loop/state/out/read_sanguo_L0_0116.candidate.json'
S, E = 586983, 591664
FAILS = []

def ck(label, ok, detail=''):
    print('%-58s %s %s' % (label, 'OK' if ok else 'FAIL', detail))
    if not ok:
        FAILS.append(label)

T = json.load(open(DOCS, encoding='utf-8'))[0]['text']
CAND_D = json.load(open(CAND, encoding='utf-8'))
SRC_HASH = hashlib.sha256(open(DOCS, 'rb').read()).hexdigest()
SL = T[S:E]

def walk(o, p=''):
    if isinstance(o, dict):
        if set(['quote', 'start', 'end']).issubset(o.keys()) and isinstance(o.get('quote'), str):
            yield p, o
        for k, v in o.items():
            yield from walk(v, p + '/' + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, p + '/%d' % i)

QS = list(walk(CAND_D))
print('=== 1. 引文层（%d 条）===' % len(QS))
v = sum(1 for _, q in QS if T[q['start']:q['end']] == q['quote'])
ck('text[start:end]==quote 逐字', v == len(QS), '%d/%d' % (v, len(QS)))
insl = sum(1 for _, q in QS if S <= q['start'] and q['end'] <= E)
ck('引文落在切片区间内', insl == len(QS), '%d/%d' % (insl, len(QS)))
uniq = sum(1 for _, q in QS if T.find(q['quote'], S, E) == q['start'])
ck('切片内首次 find == 自报 start', uniq == len(QS), '%d/%d' % (uniq, len(QS)))
h = sum(1 for _, q in QS if q.get('sourceHash') == SRC_HASH)
ck('sourceHash == sha256(docs.json)', h == len(QS), '%d/%d' % (h, len(QS)))

print()
print('=== 2. 结构计数复算 ===')
c = CAND_D['counts']
for lab, act, cl in [('tasks', len(CAND_D['tasks']), c['tasks']),
                     ('causeEdges', len(CAND_D['causeEdges']), c['causeEdges']),
                     ('rejectedCauseEdges', len(CAND_D['rejectedCauseEdges']), c['rejectedCauseEdges']),
                     ('states', len(CAND_D['states']), c['states']),
                     ('foreshadows', len(CAND_D['foreshadows']), c['foreshadows']),
                     ('worldSettings', len(CAND_D['worldSettings']), c['worldSettings']),
                     ('knowledgeGaps', len(CAND_D['knowledgeGaps']), c['knowledgeGaps']),
                     ('unknowns', len(CAND_D['unknowns']), c['unknowns']),
                     ('themeReadings', len(CAND_D['themeReadings']), c['themeReadings'])]:
    ck('counts.%s' % lab, act == cl, 'actual=%d claimed=%d' % (act, cl))
nulls = [(t['id'], col) for t in CAND_D['tasks'] for col in ['objective', 'obstacle', 'action', 'result', 'cost'] if t.get(col) is None]
ck('null 栏数', len(nulls) == c['nullColumns'], '%d vs %d' % (len(nulls), c['nullColumns']))
noNote = [(tid, col) for tid, col in nulls if not [t for t in CAND_D['tasks'] if t['id'] == tid][0].get(col + 'Note')]
ck('每个 null 栏都有 Note 说明', not noNote, str(noNote))
badfs = [f['id'] for f in CAND_D['foreshadows'] if f['status'] == 'resolved' and not f.get('payoff')]
ck('resolved 伏笔必须有 payoff', not badfs, str(badfs))

print()
print('=== 3. 同句读单元共用（候选自报规则：。！？ + 换行）===')
units = []
st = 0
for i, ch in enumerate(SL):
    if ch in '。！？\n':
        units.append((st + S, i + 1 + S, SL[st:i + 1]))
        st = i + 1
if st < len(SL):
    units.append((st + S, E, SL[st:]))

def u_of(pos):
    for i, (a, b, _) in enumerate(units):
        if a <= pos < b:
            return i
    return None

# 解释B：引文**起点**所在单元被同任务两栏共用 —— 候选 crossTaskReuse 自报「本轮无同一句被同任务两栏共用」
shared = []
for t in CAND_D['tasks']:
    m = {}
    for col in ['objective', 'obstacle', 'action', 'result', 'cost']:
        for q in (t.get(col + 'Quotes') or []):
            m.setdefault(u_of(q['start']), set()).add(col)
    for u, cols in m.items():
        if len(cols) > 1:
            shared.append((t['id'], u, sorted(cols), units[u][2][:46]))
ck('无同任务两栏共用同一起句单元', not shared, str(shared))

print()
print('=== 4. 反向覆盖（与切句口径无关的并集口径）===')
iv = sorted((q['start'], q['end']) for _, q in QS)
mg = []
for a, b in iv:
    if mg and a <= mg[-1][1]:
        mg[-1][1] = max(mg[-1][1], b)
    else:
        mg.append([a, b])
cov = sum(b - a for a, b in mg)
print('切片 4681 字符；被引文覆盖 %d 字符 = %.1f%%' % (cov, 100.0 * cov / (E - S)))
gaps = []
cur = S
for a, b in mg:
    if a > cur:
        gaps.append((cur, a, T[cur:a]))
    cur = max(cur, b)
if cur < E:
    gaps.append((cur, E, T[cur:E]))
nonspace = [g for g in gaps if g[2].strip()]
print('非空白未覆盖段：%d 段' % len(nonspace))
for a, b, x in nonspace:
    print('   [%d,%d) len=%d %r' % (a, b, b - a, x[:74]))

print()
print('=== 5. 引用抽样（seed=116，5 条）===')
random.seed(116)
for p, q in random.sample(QS, 5):
    ok = (T[q['start']:q['end']] == q['quote'] and T.find(q['quote'], S, E) == q['start'])
    ck('sample %s' % p, ok, '[%d,%d)' % (q['start'], q['end']))

print()
print('=== 6. 分词/词表误杀探针（合法因果是否被正则挡掉）===')
# 候选自报 sameClauseRule 以 。！？ 与换行为界；检查 T10 声明的「同属一句」是否成立
o10 = [t for t in CAND_D['tasks'] if t['id'] == 'T10'][0]
p_obst = T.find('吾等有来路而无归路矣', S, E)
p_obj = T.find('前江油城中，粮食足备', S, E)
ck('T10 obstacle 与 objective 同单元？(候选 note 声称同句)',
   u_of(p_obst) == u_of(p_obj),
   'obstacle unit=%s objective unit=%s -> 候选 note 的留空理由不成立' % (u_of(p_obst), u_of(p_obj)))

print()
print('TOTAL FAILS: %d' % len(FAILS))
for f in FAILS:
    print('  -', f)
sys.exit(0)
