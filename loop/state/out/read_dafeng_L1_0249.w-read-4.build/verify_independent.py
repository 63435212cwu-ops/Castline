# -*- coding: utf-8 -*-
"""独立复核脚本（不复用构建脚本的任何缓存/函数）。

用法：
    python3 -B -s /tmp/b249/verify_candidate.py

它只做四件事，全部可复现：
  1. 复算 docs.json 文件 sha256，与任务声明的 sourceHash 比对；
  2. 确认 docs[0].text[1019685:1026579) 以本单元标题开头、长度为 6894；
  3. 遍历候选里**每一处** {quote,start,end,sourceHash}，验证
     text[start:end]==quote 逐字成立、sourceHash 与文件一致、且该 quote
     在整个 [start,end) 区间内**唯一命中**且命中位置就是 start；
  4. 检查内容分区齐备、任务五栏无共用引文、null 栏位都有同名 Note。
任何一项不合格 ⇒ 退出码非 0。
"""
import json, hashlib, sys

DOCS = 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
CAND = 'loop/state/out/read_dafeng_L1_0249.candidate.json'
DECLARED = 'fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839'
S, E = 1019685, 1026579
HEAD = '第二十章 头脑风暴'

problems = []

fh = hashlib.sha256(open(DOCS, 'rb').read()).hexdigest()
if fh != DECLARED:
    problems.append('docs.json 文件哈希 %s != 任务声明 %s' % (fh[:16], DECLARED[:16]))

text = json.load(open(DOCS, encoding='utf-8'))[0]['text']
sl = text[S:E]
if not sl.startswith(HEAD):
    problems.append('切片未以标题开头：%r' % sl[:30])
if len(sl) != E - S:
    problems.append('切片长度 %d != %d' % (len(sl), E - S))
print('docs.json sha256      =', fh)
print('slice [%d,%d) codepoints = %d' % (S, E, len(sl)))
print('slice sha256          =', hashlib.sha256(sl.encode('utf-8')).hexdigest())

c = json.load(open(CAND, encoding='utf-8'))

n = 0
def walk(o, path=''):
    global n
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o and 'end' in o:
            n += 1
            q, s, e = o['quote'], o['start'], o['end']
            if text[s:e] != q:
                problems.append('%s 回读不符' % path)
            if o.get('sourceHash') != DECLARED:
                problems.append('%s sourceHash 不符' % path)
            if not (S <= s < E and S < e <= E):
                problems.append('%s 偏移越界 (%d,%d)' % (path, s, e))
            idxs, i = [], text.find(q)
            while i >= 0:
                idxs.append(i); i = text.find(q, i + 1)
            inr = [x for x in idxs if S <= x < E]
            if len(inr) != 1:
                problems.append('%s 区间内命中 %d 次' % (path, len(inr)))
            elif inr[0] != s:
                problems.append('%s start=%d 但实际定位在 %d' % (path, s, inr[0]))
        for k, v in o.items():
            walk(v, path + '/' + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + '[%d]' % i)

walk(c)
print('quoteRef 条目数         =', n)

want = ['tasks', 'causeEdges', 'states', 'foreshadows', 'worldSettings', 'themeReadings']
missing = [k for k in want if k not in c]
if missing:
    problems.append('内容分区缺失：%s' % missing)

# 任务五栏不得共用同一句引文
for tk in c.get('tasks', []):
    seen = {}
    for col in ['objective', 'obstacle', 'action', 'result', 'cost']:
        v = tk.get(col)
        if isinstance(v, dict):
            for q in v.get('quotes', []):
                if isinstance(q, dict):
                    seen.setdefault(q.get('quote', ''), []).append(col)
    for qq, cols in seen.items():
        if len(cols) > 1:
            problems.append('%s 五栏共用同一句引文：%s ← %s' % (tk['id'], cols, qq[:40]))
    for col in ['objective', 'obstacle', 'action', 'result', 'cost']:
        if tk.get(col) is None and not tk.get(col + 'Note'):
            problems.append('%s.%s 为 null 但没有 %sNote' % (tk['id'], col, col))

# worldSettings 三区分必须写进字段
for w in c.get('worldSettings', []):
    k = w.get('kind')
    if k == 'place' and w.get('placeState') not in ('arrived', 'mentioned'):
        problems.append('%s placeState 非法' % w.get('id'))
    if k == 'item' and not isinstance(w.get('itemStates'), list):
        problems.append('%s itemStates 非法' % w.get('id'))
    if k == 'rule' and w.get('institution') not in ('declared', 'executed', 'misunderstood'):
        problems.append('%s institution 非法' % w.get('id'))

# themeReadings 必须三件齐备
for th in c.get('themeReadings', []):
    for f in ('perspective', 'support', 'counter'):
        if not th.get(f):
            problems.append('%s 缺 %s' % (th.get('id'), f))

print('分区                  =', {k: (len(c[k]) if isinstance(c.get(k), list) else 'ok') for k in want})
print()
if problems:
    print('不合格项 %d：' % len(problems))
    for p in problems:
        print('  !!', p)
    sys.exit(1)
print('全部通过：%d 条引用逐字回读成立、区间内唯一命中、sourceHash 与文件一致。' % n)
