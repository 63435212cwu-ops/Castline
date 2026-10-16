# -*- coding: utf-8 -*-
"""反向覆盖审计：把区间切段，统计每段被候选引文覆盖的字符占比，列出零覆盖段。"""
import json
S, E = 504841, 510210
TEXT = json.load(open('/Users/carmen/Desktop/星系/data/cache/fe42d01f3826fe8096f86614.docs.json', encoding='utf-8'))[0]['text']
C = json.load(open('/Users/carmen/Desktop/星系/loop/state/out/read_sanguo_L1_0099.candidate.json', encoding='utf-8'))

refs = []
def walk(o):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o and 'end' in o:
            refs.append((o['start'], o['end']))
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(C)

cov = [0]*(E-S)
for a,b in refs:
    for i in range(max(a,S), min(b,E)):
        cov[i-S] = 1

# 按自然段切
paras = []
i = 0
seg = TEXT[S:E]
while i < len(seg):
    j = seg.find('\n', i)
    if j < 0: j = len(seg)
    line = seg[i:j]
    if line.strip():
        paras.append((S+i, S+j, line))
    i = j+1

print('段数 %d  引文数 %d' % (len(paras), len(refs)))
print()
for a,b,line in paras:
    c = sum(cov[a-S:b-S]); tot = b-a
    pct = 100.0*c/tot
    flag = 'ZERO ' if c == 0 else ('low  ' if pct < 35 else '     ')
    print('%s%5.1f%%  @%d  %s' % (flag, pct, a, line[:52]))
