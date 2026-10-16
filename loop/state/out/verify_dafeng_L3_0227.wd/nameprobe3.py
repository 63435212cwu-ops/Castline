import json, re
t=json.load(open('data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
START,END=862305,872127
S=t[START:END]
cand=json.load(open('loop/state/out/read_dafeng_L3_0227.candidate.json'))
def strip_quotes(o):
    if isinstance(o,dict): return {k:strip_quotes(v) for k,v in o.items() if k!='quote'}
    if isinstance(o,list): return [strip_quotes(v) for v in o]
    return o
prose=json.dumps(strip_quotes(cand),ensure_ascii=False)
# candidate's OWN named entities = grams appearing >=2 times in prose (recurring = treated as referent)
cnt=__import__('collections').Counter()
for m in re.finditer(r'[\u4e00-\u9fff]+',prose):
    w=m.group()
    for n in (2,3,4):
        for i in range(len(w)-n+1): cnt[w[i:i+n]]+=1
sus=[]
for g,c in cnt.items():
    if c<2 or g in S: continue
    if len(g)<2: continue
    if t.count(g)>0: sus.append((c,g))
sus.sort(reverse=True)
print('recurring candidate entities absent from slice (present in wider novel):',len(sus))
for c,g in sus[:40]:
    ex=t.find(g); print('%4d %s  ctx: %s'%(c,g,repr(t[max(0,ex-20):ex+22])))
