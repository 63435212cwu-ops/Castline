import json,hashlib,re,collections
ROOT='/Users/carmen/Desktop/星系'
DOC=f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'
d=json.load(open(DOC)); t=d[0]['text']; S,E=813350,817425; seg=t[S:E]
C=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))
print('--- check1 sourceHash')
h=hashlib.sha256(open(DOC,'rb').read()).hexdigest()
print('  file sha256 ==', h, '| claimed', C['source']['sourceHash'], '|', h==C['source']['sourceHash'])
print('--- check1b segmentSha256')
sh=hashlib.sha256(seg.encode()).hexdigest()
print('  seg sha256 ==', sh, '| claimed', C['source']['segmentSha256'], '|', sh==C['source']['segmentSha256'])
print('--- check2 sliceStartsWithUnitHead')
print('  ', seg.startswith(C['unitHead']), repr(seg[:len(C['unitHead'])]))

def quotes_of(o):
    out=[]
    if isinstance(o,dict):
        if isinstance(o.get('quote'),str): out.append(o)
        for v in o.values(): out+=quotes_of(v)
    elif isinstance(o,list):
        for v in o: out+=quotes_of(v)
    return out

print('--- check3 task column quotes disjoint (char-interval AND sentence-unit)')
allok=True
for task in C['tasks']:
    cols={}
    for col in ['objective','obstacle','action','result','cost']:
        v=task[col]
        if isinstance(v,dict): cols[col]=quotes_of(v.get('quotes') or [])
        else: cols[col]=[]
    # char interval overlap
    prob=[]
    names=list(cols)
    for i in range(len(names)):
        for j in range(i+1,len(names)):
            for a in cols[names[i]]:
                for b in cols[names[j]]:
                    if a['start']<b['end'] and b['start']<a['end']:
                        prob.append((names[i],names[j],a['quote'][:30],b['quote'][:30]))
    # identical quote string across columns (sentence-unit level proxy)
    seen=collections.defaultdict(list)
    for n in names:
        for q in cols[n]: seen[q['quote']].append(n)
    dup={k:v for k,v in seen.items() if len(set(v))>1}
    if prob or dup: allok=False
    print(f'  {task["id"]}: intervalOverlaps={len(prob)} crossColumnSameQuote={len(dup)}')
    for p in prob[:3]: print('     OVERLAP',p)
    for k,v in list(dup.items())[:3]: print('     DUP',repr(k[:40]),v)
print('  ALL DISJOINT:', allok)

print('--- check5 nullCostHasNote')
for task in C['tasks']:
    if task['cost'] is None:
        n=task.get('costNote')
        print(f'  {task["id"]}: costNote present={bool(n and n.strip())} len={len(n or "")}')

print('--- check6 worldSetting discriminants')
legal={'place':{'placeState':{'arrived','mentioned'}},'item':{'itemStates':{'hold','transfer','use','lose'}},'rule':{'institution':{'declared','executed','misunderstood'}}}
bad=[]
for w in C['worldSettings']:
    k=w['kind']
    if k=='place':
        if w.get('placeState') not in legal['place']['placeState']: bad.append((w['id'],'placeState',w.get('placeState')))
    elif k=='item':
        st=w.get('itemStates')
        if not isinstance(st,list) or not st or not set(st)<=legal['item']['itemStates']: bad.append((w['id'],'itemStates',st))
    elif k=='rule':
        if w.get('institution') not in legal['rule']['institution']: bad.append((w['id'],'institution',w.get('institution')))
    else: bad.append((w['id'],'kind',k))
print('  kinds:',collections.Counter(w['kind'] for w in C['worldSettings']))
print('  violations:',bad)

print('--- check7 all prose 『…』 verbatim substrings (non-vacuous)')
s=json.dumps(C,ensure_ascii=False)
pairs=re.findall(r'『([^』]*)』',s)
nonverb=[p for p in pairs if p not in t]
print('  pairs:',len(pairs),'| non-verbatim:',len(nonverb), nonverb[:5])
print('  empty pairs:',sum(1 for p in pairs if not p.strip()))
print('  ALSO 〔…〕 marker must appear 0 times in docs text:', t.count('〔'), t.count('〕'))

print('--- check9 basis values legal')
LEG={'explicit','inferred','derived','unverified'}
vals=[]
def walk(o):
    if isinstance(o,dict):
        for k,v in o.items():
            if k=='basis' and isinstance(v,str): vals.append(v)
            walk(v)
    elif isinstance(o,list):
        for v in o: walk(v)
walk(C)
print('  ',collections.Counter(vals), '| illegal:', [v for v in vals if v not in LEG])
