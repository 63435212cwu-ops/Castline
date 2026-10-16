#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核：不复用构建脚本的定位结果，直接从候选 JSON 重新遍历、
用 text.find() 重新定位、重新计算偏移与哈希。只读 + 只打印。
"""
import json, hashlib, sys, importlib.util

ROOT = '/Users/carmen/Desktop/星系'
SRC = ROOT + '/data/cache/1063b17ca65ec1b76f30e460.docs.json'
CAND = ROOT + '/loop/state/out/read_dafeng_L3_0215.candidate.json'
START, END = 799532, 805083
SRC_HASH = 'fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839'

raw = open(SRC, 'rb').read()
fhash = hashlib.sha256(raw).hexdigest()
T = json.loads(raw.decode('utf-8'))[0]['text']
c = json.load(open(CAND, encoding='utf-8'))

ok = True
def chk(cond, msg):
    global ok
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        ok = False

print('=== A. 偏移口径与源哈希 ===')
chk(fhash == SRC_HASH, '整个 docs.json 的 sha256 == 任务声明 sourceHash')
chk(c['source']['sha256'] == SRC_HASH, '候选 source.sha256 == task.sourceHash')
chk(T[START:END].startswith('第两百一十四章 扑朔迷离'), 'text[start:end] 以本单元标题开头')
# 注意：'第两百一十五章 梦境' 是 10 个 codepoint（第两 百一 十五 章 + 空格 + 梦境），
# 早先写成 T[END:END+9] 会截成「第两百一十五章 梦」而误报 FAIL——那是检查脚本的错，不是数据的错。
chk(T[END:END+10] == '第两百一十五章 梦境', 'end 落在下一章标题之前：%r' % T[END:END+10])
chk(not T[START:END].rstrip().endswith('梦境'), '本切片内不含下一章标题（无跨单元污染）')
chk(len(T[START:END]) == 5551, '切片长度 == 5551（实测 %d）' % len(T[START:END]))
seg = hashlib.sha256(T[START:END].encode('utf-8')).hexdigest()
chk(seg == c['source']['segmentSha256'], '切片 sha256 与候选声明一致')
chk(c['source']['sha256'] != seg, '切片哈希另起字段，未覆盖 sourceHash（两值确实不同）')

print('\n=== B. 全量引文：find 重定位 + 偏移回填 + 区间 + 哈希 ===')
def walk(o, path=''):
    if isinstance(o, dict):
        if 'quote' in o and isinstance(o['quote'], str):
            yield path, o
        for k, v in o.items():
            yield from walk(v, path + '/' + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, path + '[%d]' % i)

bad_find, bad_off, bad_rng, bad_hash, no_span = [], [], [], [], []
n = 0
for p, o in walk(c):
    n += 1
    q = o['quote']
    if not q:
        bad_find.append((p, '(空引文)')); continue
    i = T.find(q)                       # 全书范围内定位
    if i < 0:
        bad_find.append((p, q[:40])); continue
    j = i + len(q)
    s, e = o.get('start'), o.get('end')
    if not isinstance(s, int) or not isinstance(e, int):
        no_span.append(p); continue
    if T[s:e] != q:
        bad_off.append((p, s, e, T[s:e][:40], q[:40]))
    if not (START <= s and e <= END):
        bad_rng.append((p, s, e))
    if o.get('sourceHash') != SRC_HASH:
        bad_hash.append(p)
chk(not bad_find, '全部 %d 个引文节点都能 text.find() 逐字命中（失败 %d）' % (n, len(bad_find)))
for x in bad_find[:6]: print('        ->', x)
chk(not bad_off, '全部 start/end 满足 text[start:end]==quote（失败 %d）' % len(bad_off))
for x in bad_off[:6]: print('        ->', x)
chk(not bad_rng, '全部引文落在 [799532,805083) 内（越界 %d）' % len(bad_rng))
for x in bad_rng[:6]: print('        ->', x)
chk(not bad_hash, '每条引文 sourceHash 都等于文件 sha256（失败 %d）' % len(bad_hash))
chk(not no_span, '不存在缺 start/end 的引文（缺失 %d）' % len(no_span))

print('\n=== C. 同一任务五栏引文两两不相交（独立重算）===')
FIELDS = ('objective', 'obstacle', 'action', 'result', 'cost')
coll = 0
for t in c['tasks']:
    ivs = []
    for f in FIELDS:
        for q in (t.get(f + 'Quotes') or []):
            ivs.append((f, q['start'], q['end']))
    for a in range(len(ivs)):
        for b in range(a + 1, len(ivs)):
            f1, s1, e1 = ivs[a]; f2, s2, e2 = ivs[b]
            if s1 < e2 and s2 < e1:
                coll += 1
                print('        重叠 %s: %s[%d,%d) × %s[%d,%d)' % (t['id'], f1, s1, e1, f2, s2, e2))
chk(coll == 0, '%d 条任务的五栏引文两两不相交（重叠 %d）' % (len(c['tasks']), coll))

print('\n=== D. null 必须带 Note ===')
miss = []
for t in c['tasks']:
    for f in FIELDS:
        if t.get(f) is None and not t.get(f + 'Note'):
            miss.append('%s.%s' % (t['id'], f))
chk(not miss, '所有 null 栏位都带同名 Note（缺 %s）' % (miss or '无'))
nulls = [(t['id'], f) for t in c['tasks'] for f in FIELDS if t.get(f) is None]
print('        null 栏位共 %d 个：%s' % (len(nulls), nulls))

print('\n=== E. 内容分区：用 loop.py 自己的校验器复算 ===')
spec = importlib.util.spec_from_file_location('loopmod', ROOT + '/loop/bin/loop.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
task = json.load(open(ROOT + '/loop/state/runs/task-read_dafeng_L3_0215.json', encoding='utf-8'))
want = m.required_sections(task['prompt'])
got = m.validate_sections({'task': task['id']}, task)
chk(want == ['tasks', 'causeEdges', 'states', 'foreshadows', 'worldSettings', 'themeReadings'],
    'required_sections 复算 == 提示词要求的 6 个分区')
chk(got == [], 'validate_sections 返回空（缺项：%s）' % (got or '无'))

print('\n=== F. 红线自查项存在性 ===')
chk(c.get('semanticReview') == 'not-performed', 'semanticReview 明确写 not-performed（未声称语义已核验）')
chk(isinstance(c.get('unknowns'), list) and len(c['unknowns']) >= 10,
    'unknowns 非空且充分（%d 条）' % len(c.get('unknowns') or []))
chk(isinstance(c.get('selfCritique'), list) and len(c['selfCritique']) >= 3,
    'selfCritique ≥3 条（%d 条）' % len(c.get('selfCritique') or []))
chk(all(t.get('actor') for t in c['tasks']), '每条任务都有 actor（无凭空主体）')
for t in c['tasks']:
    for f in FIELDS:
        if t.get(f) is not None:
            if not t.get(f + 'Basis'):
                chk(False, '%s.%s 有值但缺 basis' % (t['id'], f))
chk(all(t.get(f + 'Basis') for t in c['tasks'] for f in FIELDS if t.get(f) is not None),
    '每个有值的栏位都带 basis')

print('\n=== G. 世界设定三态区分字段检查 ===')
ws = c['worldSettings']
pl = [w for w in ws if w['kind'] == 'place']
it = [w for w in ws if w['kind'] == 'item']
ru = [w for w in ws if w['kind'] == 'rule']
chk(all(w.get('placeState') in ('arrived', 'mentioned') for w in pl),
    'place 全部带 placeState（%d 条：arrived=%d mentioned=%d）'
    % (len(pl), sum(w['placeState'] == 'arrived' for w in pl), sum(w['placeState'] == 'mentioned' for w in pl)))
ALLOWED = {'hold', 'transfer', 'use', 'lose'}
chk(all(w.get('itemStates') and set(w['itemStates']) <= ALLOWED for w in it),
    'item 全部带 itemStates 且取值合法（%d 条）' % len(it))
chk(all(w.get('institution') in ('declared', 'executed', 'misunderstood') for w in ru),
    'rule 全部带 institution（%d 条：%s）' % (len(ru), [w['institution'] for w in ru]))
chk(all(w.get('explain') for w in ws), '每条 worldSettings 都有 explain（如何解释人物能做/不能做）')

print('\n=== H. 伏笔：未回收必须显式 unresolved ===')
fs = c['foreshadows']
chk(all((f.get('status') == 'resolved') or (f.get('payoff') is None and f.get('unresolvedWhat')) for f in fs),
    '%d 条伏笔：有铺设/回收，未回收的带 payoff=null + unresolvedWhat' % len(fs))
print('        status 分布：%s' % {s: sum(1 for f in fs if f['status'] == s) for s in {f['status'] for f in fs}})

print('\n=== I. 主题条目三要素 ===')
chk(all(t.get('perspective') and t.get('support') and t.get('counter') for t in c['themeReadings']),
    '%d 条 themeReadings 都含 perspective/support/counter' % len(c['themeReadings']))

print('\n=== J. 采纳的改动面（受保护路径）===')
chk(c['task'] == 'read:dafeng:L3:0215', '候选 task 字段正确')

print('\n===== 总结论：%s =====' % ('全部通过' if ok else '存在 FAIL，需处理'))
sys.exit(0 if ok else 1)
