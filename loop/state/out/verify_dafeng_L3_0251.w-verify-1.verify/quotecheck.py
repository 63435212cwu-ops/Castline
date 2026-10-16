import json, hashlib
DOC='data/cache/1063b17ca65ec1b76f30e460.docs.json'
d=json.load(open(DOC))
T=d[0]['text']
S,E=1032194,1038254
SLICE=T[S:E]
print('slice len',len(SLICE),'head',repr(SLICE[:12]))
print('slice sha256',hashlib.sha256(SLICE.encode()).hexdigest())
print('file sha256',hashlib.sha256(open(DOC,'rb').read()).hexdigest())

cand=json.load(open('loop/state/out/read_dafeng_L3_0251.candidate.json'))

quotes=[]  # (path, quoteObj)
def walk(o,path=''):
    if isinstance(o,dict):
        if 'quote' in o and isinstance(o['quote'],str) and 'start' in o and 'end' in o:
            quotes.append((path,o))
        for k,v in o.items():
            walk(v,path+'/'+str(k))
    elif isinstance(o,list):
        for i,v in enumerate(o):
            walk(v,path+'[%d]'%i)
walk(cand)
print('TOTAL quote objects with start/end:',len(quotes))
bad=[]; badhash=[]; badfind=[]; mismatch=[]
for p,q in quotes:
    s,e=q['start'],q['end']; txt=q['quote']
    slice_txt=T[s:e]
    if slice_txt!=txt: mismatch.append((p,s,e,txt,slice_txt))
    if q.get('sourceHash')!=None and q['sourceHash']!='fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839':
        badhash.append((p,q.get('sourceHash')))
    # find in whole text
    idx=T.find(txt)
    if idx<0: badfind.append((p,txt))
    # occurrences in range
    if not (S<=s and e<=E): bad.append((p,s,e))
print('--- offset out of range:',len(bad))
for b in bad: print('   ',b)
print('--- slice mismatch (text[s:e]!=quote):',len(mismatch))
for m in mismatch: print('   ',m[0],m[1],m[2],'|decl|',repr(m[3])[:80],'|actual|',repr(m[4])[:80])
print('--- bad sourceHash:',len(badhash))
for b in badhash: print('   ',b)
print('--- quote not found by find():',len(badfind))
for b in badfind: print('   ',b[0],repr(b[1])[:100])
json.dump({'total':len(quotes),'mismatch':[[m[0],m[1],m[2],m[3],m[4]] for m in mismatch],
           'notfound':[[b[0],b[1]] for b in badfind],'outofrange':[[b[0],b[1],b[2]] for b in bad]},
          open('loop/state/out/verify_dafeng_L3_0251.w-verify-1.verify/quotecheck.json','w'),ensure_ascii=False,indent=1)
