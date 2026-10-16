import json,re
ROOT='/Users/carmen/Desktop/星系'
t=json.load(open(f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
S,E=813350,817425; seg=t[S:E]
C=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))
paras=[(m.start()+S,m.end()+S) for m in re.finditer(r'[^\n]+',seg)]
def pidx(a,b):
    out=[]
    for i,(pa,pb) in enumerate(paras):
        if a<pb and pa<b: out.append(f'P{i:03d}')
    return out
SEC=['tasks','causeEdges','rejectedEdges','states','knowledgeDiffs','foreshadows','notForeshadows','worldSettings','notWorldSettings','themeReadings']
pos={'tasks','causeEdges','states','knowledgeDiffs','foreshadows','worldSettings','themeReadings'}
neg={'rejectedEdges','notForeshadows','notWorldSettings'}
mapping={}
for sec in SEC:
    qs=[]
    def walk(o):
        if isinstance(o,dict):
            if isinstance(o.get('quote'),str) and 'start' in o: qs.append(o)
            for v in o.values(): walk(v)
        elif isinstance(o,list):
            for v in o: walk(v)
    walk(C[sec])
    for q in qs:
        for p in pidx(q['start'],q['end']): mapping.setdefault(p,set()).add(sec)
print('paragraphs cited ONLY in negative sections:')
for i,(a,b) in enumerate(paras):
    k=f'P{i:03d}'; ss=mapping.get(k,set())
    if ss and not (ss & pos):
        print(f'  {k} [{a},{b}) secs={sorted(ss)}  {seg[a-S:b-S][:110]!r}')
print()
print('paragraphs cited in NO section at all:')
for i,(a,b) in enumerate(paras):
    k=f'P{i:03d}'
    if k not in mapping: print(f'  {k} {seg[a-S:b-S][:90]!r}')
print()
print('compare with candidate perParagraph claim:')
claim={p['para']:set(p['sections']) for p in C['coverage']['perParagraph']}
# candidate does not count not*/rejected as "sections"? check P016
for k in ['P016','P021','P060','P058','P065','P073','P066']:
    print(' ',k,'candSections=',sorted(claim.get(k,[])),'| mySections=',sorted(mapping.get(k,[])))
