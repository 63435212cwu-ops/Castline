# -*- coding: utf-8 -*-
"""打印未被任何引文覆盖的**连续片段**（只显示长度 >= 12 的），供反向覆盖自检。"""
import json, sys
S, E = 504841, 510210
TEXT = json.load(open('/Users/carmen/Desktop/星系/data/cache/fe42d01f3826fe8096f86614.docs.json', encoding='utf-8'))[0]['text']
C = json.load(open('/Users/carmen/Desktop/星系/loop/state/out/read_sanguo_L1_0099.candidate.json', encoding='utf-8'))
refs = []
def walk(o):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o and 'end' in o: refs.append((o['start'], o['end']))
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(C)
cov = [0]*(E-S)
for a,b in refs:
    for i in range(max(a,S), min(b,E)): cov[i-S] = 1
lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv)>2 else (S, E)
i = lo
while i < hi:
    if cov[i-S] == 0:
        j = i
        while j < hi and cov[j-S] == 0: j += 1
        fr = TEXT[i:j]
        if len(fr) >= 12 and fr.strip() and not fr.strip().startswith('---'):
            print('@%d  len=%d  %r' % (i, j-i, fr))
        i = j
    else:
        i += 1
