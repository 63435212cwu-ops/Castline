import json, re, collections
t=json.load(open('data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
START,END=862305,872127
S=t[START:END]
cand=json.load(open('loop/state/out/read_dafeng_L3_0227.candidate.json'))
def strip_quotes(o):
    if isinstance(o,dict): return {k:strip_quotes(v) for k,v in o.items() if k!='quote'}
    if isinstance(o,list): return [strip_quotes(v) for v in o]
    return o
prose=json.dumps(strip_quotes(cand),ensure_ascii=False)
grams=set()
for m in re.finditer(r'[\u4e00-\u9fff]+',prose):
    w=m.group()
    for n in (2,3,4):
        for i in range(len(w)-n+1): grams.add(w[i:i+n])
out=[]
for g in grams:
    if g in S: continue
    c=t.count(g)
    if c>0: out.append((c,g))
out.sort(reverse=True)
print('grams in candidate prose, ABSENT from slice but present elsewhere in novel:',len(out))
for c,g in out[:60]:
    ex=t.find(g)
    print('%5d %s   e.g. %s'%(c,g,repr(t[max(0,ex-25):ex+25])))
