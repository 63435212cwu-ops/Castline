# -*- coding: utf-8 -*-
"""独立复验 read_sanguo_L1_0099.candidate.json（不依赖生成脚本的内存状态）。

检查项：
  A 每条 quoteRef：全文偏移切片 == quote 逐字；区间内；sourceHash 正确
  B tasks 五栏：每栏要么是带 quotes 的 dict，要么是 null + 同名 Note
  C 同一 task 内不允许两栏共用同一条 quote
  D worldSettings 三种 kind 的必填字段与取值域
  E foreshadows 的 status 取值 + 未回收必须显式标 unresolved
  F themeReadings 必须同时有 perspective / support / counter
  G 顶层内容分区齐全（与 loop.py required_sections 的抽法一致）
  H 每个 quote 的 voiceSurface 与局部引号掩码自洽
"""
import hashlib
import json
import sys

CAND = '/Users/carmen/Desktop/星系/loop/state/out/read_sanguo_L1_0099.candidate.json'
DOCS = '/Users/carmen/Desktop/星系/data/cache/fe42d01f3826fe8096f86614.docs.json'
S, E = 504841, 510210

raw = open(DOCS, 'rb').read()
FILE_SHA = hashlib.sha256(raw).hexdigest()
TEXT = json.loads(raw.decode('utf-8'))[0]['text']
C = json.load(open(CAND, encoding='utf-8'))

fails, checks = [], []


def chk(name, ok, detail=''):
    checks.append((name, bool(ok), detail))
    if not ok:
        fails.append('%s %s' % (name, detail))


# ── A 全量 quoteRef 逐字核对 ────────────────────────────────────────────
refs = []


def walk(o):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o and 'end' in o:
            refs.append(o)
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(C)
chk('A1 quoteRef 非空', len(refs) > 0, 'n=%d' % len(refs))
bad_slice = [r for r in refs if TEXT[r['start']:r['end']] != r['quote']]
chk('A2 每条 quote 与全文切片逐字一致', not bad_slice,
    'bad=%d %s' % (len(bad_slice), [r['quote'][:20] for r in bad_slice[:3]]))
bad_range = [r for r in refs if not (S <= r['start'] and r['end'] <= E)]
chk('A3 每条 quote 落在本单元区间内', not bad_range, 'bad=%d' % len(bad_range))
bad_hash = [r for r in refs if r['sourceHash'] != FILE_SHA]
chk('A4 sourceHash 均为实测文件哈希', not bad_hash, 'bad=%d' % len(bad_hash))
chk('A5 candidate.source.sourceHash == 实测', C['source']['sourceHash'] == FILE_SHA)
chk('A6 candidate.source.segmentSha256 与切片一致',
    C['source']['segmentSha256'] == hashlib.sha256(TEXT[S:E].encode('utf-8')).hexdigest())
chk('A7 区间起点即单元标题', TEXT[S:E].startswith(C['unitHead']))

# ── B tasks 五栏 ────────────────────────────────────────────────────────
COLS = ('objective', 'obstacle', 'action', 'result', 'cost')
problems = []
for t in C['tasks']:
    for k in COLS:
        v = t.get(k)
        note = t.get(k + 'Note')
        if v is None:
            if not (isinstance(note, str) and note.strip()):
                problems.append('%s.%s 为 null 但缺 %sNote' % (t['id'], k, k))
        else:
            if not (isinstance(v, dict) and v.get('quotes')):
                problems.append('%s.%s 缺 quotes' % (t['id'], k))
            if not v.get('basis'):
                problems.append('%s.%s 缺 basis' % (t['id'], k))
            if not v.get('text'):
                problems.append('%s.%s 缺 text' % (t['id'], k))
chk('B1 五栏要么有据要么 null+Note', not problems, '; '.join(problems[:5]))

# ── C 同 task 内不共用引文 ──────────────────────────────────────────────
shared = []
for t in C['tasks']:
    seen = {}
    for k in COLS:
        v = t.get(k)
        if not isinstance(v, dict):
            continue
        for r in v.get('quotes') or []:
            q = r['quote']
            if q in seen:
                shared.append('%s: %s 与 %s 共用 %r' % (t['id'], seen[q], k, q[:24]))
            else:
                seen[q] = k
chk('C1 同一任务五栏不共用引文', not shared, '; '.join(shared[:5]))
ncols = sum(1 for t in C['tasks'] for k in COLS
            if isinstance(t.get(k), dict) and t[k].get('quotes'))
chk('C2 有据栏位计数与 fieldCounts 一致',
    ncols == C['fieldCounts']['taskColumnsWithOwnQuotes'], '%d vs %s' % (ncols, C['fieldCounts']['taskColumnsWithOwnQuotes']))

# ── D worldSettings ─────────────────────────────────────────────────────
ws_prob = []
for w in C['worldSettings']:
    k = w.get('kind')
    if k not in ('rule', 'place', 'item'):
        ws_prob.append('kind 非法 %r' % k)
        continue
    if not w.get('quotes'):
        ws_prob.append('%s 缺 quotes' % w.get('name'))
    if not w.get('explain'):
        ws_prob.append('%s 缺 explain' % w.get('name'))
    if k == 'place' and w.get('placeState') not in ('arrived', 'mentioned'):
        ws_prob.append('%s placeState 非法' % w.get('name'))
    if k == 'item':
        st = w.get('itemStates')
        if not isinstance(st, list) or any(s not in ('hold', 'transfer', 'use', 'lose') for s in st):
            ws_prob.append('%s itemStates 非法 %r' % (w.get('name'), st))
    if k == 'rule' and w.get('institution') not in ('declared', 'executed', 'misunderstood'):
        ws_prob.append('%s institution 非法' % w.get('name'))
chk('D1 worldSettings 字段与取值域合法', not ws_prob, '; '.join(ws_prob[:5]))
kinds = set(w['kind'] for w in C['worldSettings'])
chk('D2 三类分区键存在（可空但必须处理）', kinds <= {'rule', 'place', 'item'}, repr(kinds))

# ── E foreshadows ───────────────────────────────────────────────────────
fs_prob = []
for f in C['foreshadows']:
    if f.get('status') not in ('resolved', 'unresolved'):
        fs_prob.append('%s status 非法' % f.get('id'))
    if not f.get('setup') or not f.get('payoff'):
        fs_prob.append('%s 缺 setup/payoff' % f.get('id'))
    if not f.get('setupQuotes') or not f.get('payoffQuotes'):
        fs_prob.append('%s 缺 setup/payoff 引文' % f.get('id'))
chk('E1 foreshadows 有铺设+回收+状态', not fs_prob, '; '.join(fs_prob[:5]))
chk('E2 未回收数统计一致',
    sum(1 for f in C['foreshadows'] if f['status'] == 'unresolved') == C['fieldCounts']['foreshadowsUnresolved'])

# ── F themeReadings ─────────────────────────────────────────────────────
th_prob = []
for t in C['themeReadings']:
    for k in ('perspective', 'support', 'counter'):
        if not t.get(k):
            th_prob.append('%s 缺 %s' % (t.get('id'), k))
chk('F1 themeReadings 三件齐全', not th_prob, '; '.join(th_prob[:5]))
chk('F2 themeReadings 不超过 2 条', len(C['themeReadings']) <= 2, str(len(C['themeReadings'])))

# ── G 顶层分区 ──────────────────────────────────────────────────────────
want = ['tasks', 'causeEdges', 'states', 'foreshadows', 'worldSettings', 'themeReadings']
missing = [k for k in want if k not in C]
chk('G1 顶层内容分区齐全', not missing, repr(missing))

# ── H voice 掩码自洽 ────────────────────────────────────────────────────
rep = sorted([TEXT.find('懿入中军帐下，手执黄旗招飐'),
              TEXT.find('宦官曰：“可诏还成都，削其兵权，免生叛逆。”')])
INSIDE = [False] * len(TEXT)
d = 0
for i in range(S, E):
    if i in rep:
        d = max(0, d - 1)
    c = TEXT[i]
    if c == '\u201c':
        d += 1
        INSIDE[i] = True
    elif c == '\u201d':
        INSIDE[i] = True
        d = max(0, d - 1)
    else:
        INSIDE[i] = d > 0
chk('H1 掩码在区间末尾回到 depth 0', d == 0, 'depth=%d' % d)
vbad = []
for r in refs:
    frac = sum(1 for k in range(r['start'], r['end']) if INSIDE[k]) / float(len(r['quote']))
    exp = 'narration' if frac == 0 else ('character' if frac == 1 else 'mixed')
    if r.get('voiceSurface') != exp:
        vbad.append((r['quote'][:16], r.get('voiceSurface'), exp))
chk('H2 voiceSurface 与掩码一致', not vbad, repr(vbad[:3]))

print('=== 检查项 %d，失败 %d ===' % (len(checks), len(fails)))
for name, ok, detail in checks:
    print('%s %s %s' % ('PASS' if ok else 'FAIL', name, ('| ' + detail) if detail else ''))
if fails:
    print('\n失败明细：')
    for f in fails:
        print(' -', f)
    sys.exit(1)
print('\nquoteRefs=%d 全部逐字命中；tasks=%d causeEdges=%d states=%d foreshadows=%d worldSettings=%d themeReadings=%d'
      % (len(refs), len(C['tasks']), len(C['causeEdges']), len(C['states']),
         len(C['foreshadows']), len(C['worldSettings']), len(C['themeReadings'])))
