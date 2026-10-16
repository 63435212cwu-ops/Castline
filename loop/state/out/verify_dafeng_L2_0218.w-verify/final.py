import json,re,hashlib
ROOT='/Users/carmen/Desktop/星系'
DOC=f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'
t=json.load(open(DOC))[0]['text']
S,E=813350,817425; seg=t[S:E]
C=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))
print('--- A. non-null columns must have >=1 quote ---')
for tk in C['tasks']:
    for col in ['objective','obstacle','action','result','cost']:
        v=tk[col]
        if v is None:
            print(f'  {tk["id"]}.{col}=null note_ok={bool((tk.get(col+"Note") or "").strip())}')
        else:
            ok=bool(v.get('quotes'))
            if not ok: print(f'  !! {tk["id"]}.{col} NON-NULL but no quotes')
    print(f'  {tk["id"]}: all non-null columns quoted = True')
print()
print('--- B. marker hygiene: 「」 must not be used as third marker; 〔〕 present ---')
s=json.dumps(C,ensure_ascii=False)
print('   「 count:',s.count('「'),' 」 count:',s.count('」'),' 〔 count:',s.count('〔'))
print('   〔 in docs text:',t.count('〔'),' 「 in docs text:',t.count('「'))
print()
print('--- C. out-of-interval tokens inside who/name/place/state fields ---')
def fields(o,keys=('who','name','label')):
    out=[]
    if isinstance(o,dict):
        for k,v in o.items():
            if k in keys and isinstance(v,str): out.append((k,v))
            out+=fields(v,keys)
    elif isinstance(o,list):
        for v in o: out+=fields(v,keys)
    return out
for k,v in fields(C):
    if k=='who':
        toks=re.findall(r'[\u4e00-\u9fff]{2,}',v)
        miss=[x for x in toks if x not in seg]
        if miss: print(f'   who-field tokens NOT in interval: {miss} :: {v[:90]}')
print()
print('--- D. K1 internal contradiction (same item, same what) ---')
for kd in C['knowledgeDiffs']:
    kn=' '.join(kd['whoKnows']); dn=' '.join(kd['whoDoesNotKnow'])
    both=[n for n in ['许七安','李妙真','三号','二号','张巡抚','姜律中','一号','四号','五号','六号','苏苏'] if n in kn and n in dn]
    if both: print(f'   {kd["id"]}: appears in BOTH knows & doesNotKnow -> {both}')
print()
print('--- E. relevance of extra quotes in worldSettings (P035 vs W03) ---')
w=[x for x in C['worldSettings'] if x['id']=='W03'][0]
print('   W03.name:',w['name'])
for q in w['quotes']:
    print(f'     {q["paraLabel"]} {q["quote"][:70]!r}')
print('   P035 text:',repr(seg[814929-S:814953-S]))
print('   "官场规矩" in P035 quote:', '官场规矩' in seg[814929-S:814953-S])
print()
print('--- F. W05 explain: is "留在外面" stated anywhere in interval? ---')
for probe in ['留在外面','都在外面','留在厅','在外面']:
    print(f'   {probe!r} in interval:', probe in seg)
w5=[x for x in C['worldSettings'] if x['id']=='W05'][0]
print('   W05.explain contains 留在外面:', '留在外面' in w5['explain'])
print()
print('--- G. T1.obstacle order claim vs P001 ---')
p001=seg[813367-S:813403-S]; p004=seg[813486-S:813516-S]
print('   P001:',repr(p001)); print('   P004:',repr(p004))
print('   P001 says 五号 first:', '最先回复的是南疆小蛮妞五号' in p001)
print()
print('--- H. S2.before cites P020 but provides no P020 quote ---')
s2=[x for x in C['states'] if x['id']=='S2'][0]
print('   before cites P020:', 'P020' in s2['before'])
print('   S2 quote paraLabels:',[q.get('paraLabel') for q in s2['quotes']])
print()
print('--- I. hashes ---')
print('   docs sha256   :',hashlib.sha256(open(DOC,'rb').read()).hexdigest())
print('   segment sha256:',hashlib.sha256(seg.encode()).hexdigest())
print('   candidate sha256:',hashlib.sha256(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json','rb').read()).hexdigest())
