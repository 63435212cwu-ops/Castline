#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核脚本：不复用构建期偏移，全部从 docs[0].text 现取现验。

与 build_candidate.py 的差别（这是它存在的理由）：
  · 构建脚本的「同任务不共用一句」断言用的是**它自己切句的规则**；本脚本改用
    「引文两两之间的重叠字符数」这个与切句规则无关的判据，避免同一条规则自己验自己。
  · 构建脚本把偏移写进 JSON 后由自己读回；本脚本**只从候选 JSON 里取 quote 字符串**，
    偏移一律重新计算，再与候选里声明的 start/end 比对。
  · 覆盖统计、世界设定三态、空栏 Note、主题三件，全部独立重算。
"""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
DOCS = ROOT / 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
TASKF = ROOT / 'loop/state/runs/task-read_dafeng_L2_0178.json'
CAND = ROOT / 'loop/state/out/read_dafeng_L2_0178.candidate.json'

T = json.loads(TASKF.read_text(encoding='utf-8'))
S, E = T['sourceRange']
DECLARED = T['sourceHash']

raw = DOCS.read_bytes()
file_sha = hashlib.sha256(raw).hexdigest()
TEXT = json.loads(raw.decode('utf-8'))[0]['text']
SEG = TEXT[S:E]

fails = []
warns = []


def chk(cond, msg):
    (fails if not cond else warns).append(msg) if not cond else None
    print(('  [OK] ' if cond else '  [FAIL] ') + msg)
    return cond


print('=== A. 源与区间 ===')
print('  file sha256 =', file_sha)
chk(file_sha == DECLARED, 'A1 文件哈希 == task.sourceHash')
chk(SEG.startswith(T['unitHead']), 'A2 text[start:end] 以单元标题开头：%r' % SEG[:22])
chk(len(SEG) == E - S, 'A3 切片长度 == end-start（%d）' % len(SEG))
next_head = TEXT[E:E + 40].strip().split('\n')[0]
print('  E 处下一单元标题 =', repr(next_head[:30]))

paras = []
for m in re.finditer(r'[^\n]+', SEG):
    b = m.group(0).strip()
    if not b:
        continue
    lead = len(m.group(0)) - len(m.group(0).lstrip())
    st = S + m.start() + lead
    paras.append((st, st + len(b), b))

cand = json.loads(CAND.read_text(encoding='utf-8'))

print()
print('=== B. 候选 JSON 与源的一致性 ===')
chk(cand['source']['sourceHash'] == DECLARED, 'B1 候选 sourceHash == task.sourceHash')
seg_sha = hashlib.sha256(SEG.encode('utf-8')).hexdigest()
chk(cand['source']['segmentSha256'] == seg_sha, 'B2 候选 segmentSha256 可复算：%s' % seg_sha[:16])
chk(cand['source']['range'] == [S, E], 'B3 候选 range == sourceRange')
chk(cand['source']['sliceStartsWithUnitHead'] is True, 'B4 候选声明切片以标题开头')
chk(cand['source']['nonEmptyParagraphs'] == len(paras),
    'B5 候选非空段数 == 实测（%d）' % len(paras))
chk(cand.get('semanticReview') == 'not-performed',
    'B6 未声称 semanticReview 完成（值=%r）' % cand.get('semanticReview'))


def walk(obj, path='$'):
    if isinstance(obj, dict):
        if 'quote' in obj and 'start' in obj and 'end' in obj:
            yield path, obj
        else:
            for k, v in obj.items():
                yield from walk(v, '%s.%s' % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, '%s[%d]' % (path, i))


print()
print('=== C. 引文逐字 / 偏移 / 区间（全部重算）===')
qobjs = list(walk(cand))
print('  引文对象总数：%d' % len(qobjs))
bad_lit = bad_off = bad_range = bad_meta = bad_hash = 0
per_quote_span = {}
for path, o in qobjs:
    s = o['quote']
    st, en = o['start'], o['end']
    if TEXT[st:en] != s:
        bad_lit += 1
        print('  [FAIL] %s text[start:end] != quote' % path)
        continue
    occ = [m.start() for m in re.finditer(re.escape(s), TEXT)]
    if occ[0] != st and o.get('startIsFirstOccurrence') is not False:
        bad_off += 1
        print('  [FAIL] %s start=%d 非全文首现（首现 %d），但声明 startIsFirstOccurrence=%r'
              % (path, st, occ[0], o.get('startIsFirstOccurrence')))
    if occ[0] == st and o.get('startIsFirstOccurrence') is not True:
        bad_meta += 1
        print('  [FAIL] %s start 是全文首现，但声明 startIsFirstOccurrence=%r'
              % (path, o.get('startIsFirstOccurrence')))
    if o.get('firstOccurrenceAt') != occ[0]:
        bad_meta += 1
        print('  [FAIL] %s firstOccurrenceAt 声明 %r 实际 %d'
              % (path, o.get('firstOccurrenceAt'), occ[0]))
    if not (st >= S and en <= E):
        bad_range += 1
        print('  [FAIL] %s 越出区间：%d..%d' % (path, st, en))
    if o.get('sourceHash') != DECLARED:
        bad_hash += 1
        print('  [FAIL] %s sourceHash 不符' % path)
    if o.get('wholeTextOccurrences') != len(occ):
        bad_meta += 1
        print('  [FAIL] %s wholeTextOccurrences 声明 %r 实际 %d'
              % (path, o.get('wholeTextOccurrences'), len(occ)))
    inr = [x for x in occ if x >= S and x + len(s) <= E]
    if o.get('occurrencesInRange') != len(inr):
        bad_meta += 1
        print('  [FAIL] %s occurrencesInRange 声明 %r 实际 %d'
              % (path, o.get('occurrencesInRange'), len(inr)))
    pno = next((i for i, (a, b, _t) in enumerate(paras, 1) if a <= st < b), None)
    if o.get('para') != pno:
        bad_meta += 1
        print('  [FAIL] %s para 声明 %r 实际 %r' % (path, o.get('para'), pno))
    per_quote_span.setdefault((st, en), []).append(path)

chk(bad_lit == 0, 'C1 全部引文逐字命中（%d 条）' % len(qobjs))
chk(bad_off == 0, 'C2 startIsFirstOccurrence 声明与「是否为全文首现」逐条一致')
# 区间内命中唯一：这是任务契约真正要求的（避免短句落到区间外的同形句）
nonuniq = [(p, o['quote']) for p, o in qobjs if o.get('occurrencesInRange') != 1]
for p, s2 in nonuniq:
    print('  [FAIL] %s 区间内命中不唯一：%r' % (p, s2[:24]))
chk(not nonuniq, 'C2b 255 条引文在区间内各只命中一次（区间内唯一性）')
n_global = sum(1 for _p, o in qobjs if o.get('startIsFirstOccurrence') is False)
print('  其中 start 不是全文首现、但区间内唯一的引文：%d 条（候选显式标为 False，未冒充首现）' % n_global)
chk(bad_range == 0, 'C3 全部引文落在 [start,end) 区间内')
chk(bad_hash == 0, 'C4 全部引文 sourceHash 与 task 一致')
chk(bad_meta == 0, 'C5 全部 occurrences/para 元数据可复算')

print()
print('=== D. 任务五栏独立性（与切句规则无关的判据：字符重叠）===')
FIELDS = ['objective', 'obstacle', 'action', 'result', 'cost']
share_fail = 0
for t in cand['tasks']:
    spans = {}
    for f in FIELDS:
        v = t.get(f)
        if v is None:
            continue
        for o in v['quotes']:
            spans[f] = spans.get(f, []) + [(o['start'], o['end'], o['quote'])]
    # 两栏之间的**字符区间重叠**即为共用
    keys = list(spans)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            for (a1, b1, s1) in spans[keys[i]]:
                for (a2, b2, s2) in spans[keys[j]]:
                    ov = min(b1, b2) - max(a1, a2)
                    if ov > 0:
                        share_fail += 1
                        print('  [FAIL] %s %s/%s 重叠 %d 字：%r | %r'
                              % (t['id'], keys[i], keys[j], ov, s1[:22], s2[:22]))
    # 同栏内也不应有完全重复的引文
    for f in spans:
        c = Counter(x[2] for x in spans[f])
        for s, n in c.items():
            if n > 1:
                share_fail += 1
                print('  [FAIL] %s.%s 同栏重复引文：%r' % (t['id'], f, s[:22]))
chk(share_fail == 0, 'D1 同任务五栏无任何字符重叠（含同栏重复）')
print('  各任务栏位填充情况：')
for t in cand['tasks']:
    filled = [f for f in FIELDS if t.get(f) is not None]
    nulls = [f for f in FIELDS if t.get(f) is None]
    print('    %s: 有值=%s 空=%s' % (t['id'], ','.join(filled), ','.join(nulls) or '-'))
    for f in nulls:
        chk(bool(t.get(f + 'Note')), 'D2 %s.%s 为 null 且带 %sNote' % (t['id'], f, f))
chk(all(any(t.get(f) is not None for f in FIELDS) for t in cand['tasks']),
    'D3 没有「五栏全空」的伪任务')

print()
print('=== E. causeEdges 方向与机制 ===')
for c in cand['causeEdges']:
    chk(bool(c.get('from')) and bool(c.get('to')), 'E1 %s 有 from/to' % c['id'])
    chk(bool(c.get('mechanism')) and len(c['mechanism']) > 20, 'E2 %s 有机制说明' % c['id'])
    chk(bool(c.get('quotes')), 'E3 %s 有引文' % c['id'])
rej = {r['id'] for r in cand.get('rejectedEdges', [])}
chk(len(cand.get('rejectedEdges', [])) >= 3, 'E4 有拒绝边记录（%d 条）' % len(cand.get('rejectedEdges', [])))

print()
print('=== F. states / knowledgeDiffs ===')
for s in cand['states']:
    ok = bool(s.get('before')) and bool(s.get('after')) and bool(s.get('anchor'))
    chk(ok, 'F1 %s 有前值/后值/锚点' % s['id'])
for k in cand['knowledgeDiffs']:
    has = isinstance(k.get('whoKnows'), list) and isinstance(k.get('whoDoesNotKnow'), list)
    chk(has, 'F2 %s 知/不知名单为列表' % k['id'])

print()
print('=== G. foreshadows 两端 ===')
for f in cand['foreshadows']:
    chk(bool(f.get('setup')) and bool(f.get('status')), 'G1 %s 有 setup/status' % f['id'])
    if f['status'] == 'unresolved':
        chk(bool(f.get('unresolvedReason')), 'G2 %s 未回收且有理由' % f['id'])
    else:
        chk(bool(f.get('payoff')), 'G3 %s 已回收且有 payoff' % f['id'])
chk(len(cand.get('notForeshadows', [])) >= 3,
    'G4 有「不是伏笔」清单（%d 条）' % len(cand.get('notForeshadows', [])))

print()
print('=== H. worldSettings 三态 ===')
kinds = Counter(w['kind'] for w in cand['worldSettings'])
print('  kind 分布：', dict(kinds))
for w in cand['worldSettings']:
    if w['kind'] == 'place':
        chk(w.get('placeState') in ('arrived', 'mentioned'),
            'H1 %s placeState=%s' % (w['id'], w.get('placeState')))
    elif w['kind'] == 'item':
        chk(isinstance(w.get('itemStates'), list) and w['itemStates'], 'H2 %s itemStates 非空' % w['id'])
        chk(all(x in ('hold', 'transfer', 'use', 'lose') for x in w['itemStates']),
            'H3 %s itemStates 取值合法' % w['id'])
        chk(bool(w.get('stateVerbsOriginal')), 'H4 %s 照录原文动词' % w['id'])
    elif w['kind'] == 'rule':
        chk(w.get('institution') in ('declared', 'executed', 'misunderstood'),
            'H5 %s institution=%s' % (w['id'], w.get('institution')))
    chk(bool(w.get('explain')), 'H6 %s 有 explain' % w['id'])
    chk(bool(w.get('quote')) and bool(w.get('quotes')), 'H7 %s 有 quote 与 quotes' % w['id'])
chk(len(cand.get('notWorldSettings', [])) >= 3,
    'H8 有「不是设定」清单（%d 条）' % len(cand.get('notWorldSettings', [])))

print()
print('=== I. themeReadings 三件 + 上限 ===')
chk(len(cand['themeReadings']) <= 2, 'I1 主题读法 <= 2 条（%d）' % len(cand['themeReadings']))
for th in cand['themeReadings']:
    chk(bool(th.get('perspective')) and bool(th.get('support')) and bool(th.get('counter')),
        'I2 %s 三件齐全（support %d / counter %d）'
        % (th['id'], len(th.get('support', [])), len(th.get('counter', []))))
    chk(len(th.get('counter', [])) >= 1, 'I3 %s 至少 1 条反例' % th['id'])

print()
print('=== J. 覆盖统计（独立重算）===')
touched = sorted({o['para'] for _p, o in qobjs})
cov = cand['coverageDeclaration']
chk(cov['nonEmptyParagraphs'] == len(paras), 'J1 段数一致')
chk(cov['paragraphsTouchedByAtLeastOneQuote'] == len(touched),
    'J2 被引段落数一致（%d）' % len(touched))
chk(sorted(cov['uncoveredParagraphs']) == [i for i in range(1, len(paras) + 1) if i not in touched],
    'J3 uncoveredParagraphs 与重算一致：%s' % cov['uncoveredParagraphs'])
chk(abs(cov['paragraphCoverageRatio'] - round(len(touched) / len(paras), 4)) < 1e-9,
    'J4 覆盖率一致：%.4f' % cov['paragraphCoverageRatio'])

print()
print('=== K. 分区存在性（提交机器校验的那 6 个）===')
for sec in ['tasks', 'causeEdges', 'states', 'foreshadows', 'worldSettings', 'themeReadings']:
    chk(sec in cand and isinstance(cand[sec], list), 'K1 顶层分区 %s 存在' % sec)

print()
print('=' * 60)
print('未通过项：%d' % len(fails))
for f in fails:
    print('  -', f)
print('切片 sha256 =', seg_sha)
print('候选引文对象 =', len(qobjs), '；覆盖段 =', len(touched), '/', len(paras))
sys.exit(1 if fails else 0)
