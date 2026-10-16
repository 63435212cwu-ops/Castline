# -*- coding: utf-8 -*-
"""read:sanguo:L1:0105 候选的独立可复现校验（不依赖生成脚本的中间态）。

用法：
    python3 -B -s loop/state/out/read_sanguo_L1_0105.w-read-4.audit/verify_candidate.py

判据（任一失败即 exit 1）：
 1. 每条 quote 都是 docs[0].text 的逐字子串，且 T[start:end] == quote；
 2. 该 quote 在本单元区间内**有且仅有一次**命中，且 start 正是那一次；
 3. sourceHash == 实测 docs.json 文件 sha256；
 4. 所有引文落在 [537888,543089) 内；
 5. 任务五栏内部不得共用同一引文（同一句同时当两栏依据＝该栏无独立依据）；
 6. 五栏为 null 时必须带同名 <栏位>Note；
 7. worldSettings 枚举合法（place/item/rule + placeState/itemStates/institution）；
 8. foreshadows：resolved 必有回收引文，unresolved 必显式标 note；
 9. causeEdges 必有 mechanism 与方向证据。
另做**反向覆盖**（问「这一段里还漏了什么」）：
10. 把区间按句读切分并剥离「X曰：」说话人前缀后，逐句核对是否被任一引文触及
    （引文⊆句子 或 句子⊆引文）；打印未触及句清单。
"""
import json, hashlib, re, sys, os

# 本文件位于 <repo>/loop/state/out/<task>.audit/verify_candidate.py，上溯 4 层到仓库根
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..', '..'))
CAND = os.path.join(ROOT, 'loop/state/out/read_sanguo_L1_0105.candidate.json')
DOCS = os.path.join(ROOT, 'data/cache/fe42d01f3826fe8096f86614.docs.json')
S, E = 537888, 543089

raw = open(DOCS, 'rb').read()
FSHA = hashlib.sha256(raw).hexdigest()
T = json.loads(raw.decode('utf-8'))[0]['text']
D = json.load(open(CAND, encoding='utf-8'))
seg = T[S:E]

problems = []

def walk(o, path='root'):
    if isinstance(o, dict):
        if 'quote' in o and isinstance(o['quote'], str):
            yield path, o
        for k, v in o.items():
            if k != 'quote':
                yield from walk(v, path + '.' + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, path + '[%d]' % i)

# 0) 边界自检：区间必须以本单元标题开头
if not seg.startswith('第一百六回　公孙渊兵败死襄平　司马懿诈病赚曹爽'):
    problems.append('区间起点不是本单元标题')
if len(seg) != E - S:
    problems.append('区间长度不符')

# 1-4) 引文往返 / 唯一性 / 哈希 / 范围
nquote = 0
for p, it in walk(D):
    nquote += 1
    q, a, b = it['quote'], it.get('start'), it.get('end')
    if not isinstance(a, int) or not isinstance(b, int):
        problems.append('引文缺偏移 %s' % p); continue
    if T[a:b] != q:
        problems.append('往返失败 %s @%d:%d' % (p, a, b)); continue
    if it.get('sourceHash') != FSHA:
        problems.append('sourceHash 不符 %s' % p)
    if not (S <= a and b <= E):
        problems.append('引文越出区间 %s @%d' % (p, a))
    hits, st = [], 0
    while True:
        i = T.find(q, st)
        if i < 0: break
        hits.append(i); st = i + 1
    inr = [i for i in hits if S <= i and i + len(q) <= E]
    if len(inr) != 1:
        problems.append('区间内命中数=%d（要求 1）%s' % (len(inr), p))
    elif inr[0] != a:
        problems.append('偏移指向的不是区间内那一次 %s' % p)

# 5-6) 五栏独立依据
TC = ('objective', 'obstacle', 'action', 'result', 'cost')
for t in D['tasks']:
    seen = {}
    for cn in TC:
        c = t.get(cn)
        if c is None:
            if not t.get(cn + 'Note'):
                problems.append('null 栏无 Note：%s.%s' % (t['id'], cn))
            continue
        if c.get('basis') not in ('explicit', 'inferred', 'derived', 'unverified'):
            problems.append('basis 非法 %s.%s' % (t['id'], cn))
        for qq in c['quotes']:
            if qq['quote'] in seen:
                problems.append('五栏共用引文 %s：%s / %s' % (t['id'], seen[qq['quote']], cn))
            seen[qq['quote']] = cn

# 7) worldSettings 枚举
for w in D['worldSettings']:
    if w['kind'] == 'place':
        if w.get('placeState') not in ('arrived', 'mentioned'):
            problems.append('placeState 非法：%s' % w['name'])
    elif w['kind'] == 'item':
        st = w.get('itemStates') or []
        if not st or any(x not in ('hold', 'transfer', 'use', 'lose') for x in st):
            problems.append('itemStates 非法：%s %r' % (w['name'], st))
    elif w['kind'] == 'rule':
        if w.get('institution') not in ('declared', 'executed', 'misunderstood'):
            problems.append('institution 非法：%s' % w['name'])
    else:
        problems.append('kind 非法：%r' % w['kind'])

# 8) foreshadows
for f in D['foreshadows']:
    if f['status'] not in ('resolved', 'unresolved'):
        problems.append('foreshadow status 非法 %s' % f['id'])
    if f['status'] == 'resolved' and not f['payoffQuotes']:
        problems.append('resolved 无回收引文 %s' % f['id'])
    if f['status'] == 'unresolved' and (f.get('payoff') or not f.get('note')):
        problems.append('unresolved 写法不当 %s' % f['id'])

# 9) causeEdges
for c in D['causeEdges']:
    if not c.get('mechanism') or len(c['mechanism']) < 20:
        problems.append('机制过短 %s' % c['id'])
    if not c['causeQuotes'] or not c['effectQuotes']:
        problems.append('缺方向证据 %s' % c['id'])

# 10) 反向覆盖
qs = [x for _, x in walk(D)]
qs = [x['quote'] for x in qs if len(x['quote']) >= 4]
SPK = re.compile(r'^[^：]{0,14}(曰|告曰|奏曰|谏曰|问曰|答曰|叱曰|骂曰|称贺曰|赞之曰)：?')
STRIP = '“”"　 \n'

def norm(x):
    x = x.strip().strip(STRIP).strip()
    m = SPK.match(x)
    if m:
        x = x[m.end():].strip().strip(STRIP).strip()
    return x

AUTH = ('------------------', '枫林晚', '回目录')
sents = [p for p in re.split(r'(?<=[。！？；])', seg) if p.strip()]
tot, uncov = 0, []
for p in sents:
    if any(a in p for a in AUTH):
        continue
    b = norm(p)
    if len(b) < 6 or b.startswith('第一百六回'):
        continue
    tot += 1
    if any((b in q) or (q in b) for q in qs):
        continue
    uncov.append((seg.find(p) + S, b))

print('docs.json sha256      :', FSHA)
print('candidate sha256      :', hashlib.sha256(open(CAND, 'rb').read()).hexdigest())
print('range                 : [%d,%d) len=%d' % (S, E, len(seg)))
print('quote refs checked    :', nquote)
print('sentences checked     :', tot)
print('sentences uncovered   :', len(uncov))
for off, b in uncov:
    print('   UNCOVERED @%d %s' % (off, b))
print('structure problems    :', len(problems))
for x in problems:
    print('   -', x)
print('RESULT:', 'PASS' if not problems else 'FAIL')
sys.exit(1 if problems else 0)
