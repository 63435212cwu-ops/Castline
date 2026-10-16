import json,re
ROOT='/Users/carmen/Desktop/星系'
t=json.load(open(f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
S,E=813350,817425; seg=t[S:E]
C=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))
# sentence spans over the whole text around our slice
bounds=[S]
for m in re.finditer(r'[。！？]|\.\.\.\.', seg):
    bounds.append(S+m.end())
bounds.append(E)
spans=list(zip(bounds,bounds[1:]))
def sentid(a,b):
    for i,(x,y) in enumerate(spans):
        if a<y and x<b: return i
    return None
for tk in C['tasks']:
    cols={}
    for col in ['objective','obstacle','action','result','cost']:
        v=tk[col]
        cols[col]=[] if not isinstance(v,dict) else (v.get('quotes') or [])
    viol=[]
    names=list(cols)
    for i in range(len(names)):
        for j in range(i+1,len(names)):
            for a in cols[names[i]]:
                for b in cols[names[j]]:
                    sa,sb=sentid(a['start'],a['end']),sentid(b['start'],b['end'])
                    if sa is not None and sa==sb:
                        viol.append((names[i],names[j],a['quote'][:40],b['quote'][:40]))
    print(f'{tk["id"]}: same-sentence cross-column pairs = {len(viol)}')
    for v in viol[:4]: print('    ',v)
