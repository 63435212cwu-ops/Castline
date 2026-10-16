import json, re
t=json.load(open('data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
START,END=862305,872127
S=t[START:END]
cand=json.load(open('loop/state/out/read_dafeng_L3_0227.candidate.json'))

# collect all quoted intervals (absolute)
ivs=[]
def walk(o):
    if isinstance(o,dict):
        if isinstance(o.get('quote'),str) and o.get('start') is not None:
            ivs.append((o['start'],o['end']))
        for v in o.values(): walk(v)
    elif isinstance(o,list):
        for v in o: walk(v)
walk(cand)
ivs.sort()
# merge
merged=[]
for a,b in ivs:
    if merged and a<=merged[-1][1]: merged[-1][1]=max(merged[-1][1],b)
    else: merged.append([a,b])
def covered(a,b):
    return any(m[0]<b and a<m[1] for m in merged)
print('merged quote intervals:',len(merged))

# paragraphs of slice
paras=[]
off=0
for p in S.split('\n'):
    paras.append((START+off,p))
    off+=len(p)+1
uncov=[(a,p) for a,p in paras if p.strip() and not covered(a,a+len(p))]
substantive=[(a,p) for a,p in uncov if len(re.sub(r'\s','',p))>=12]
print('uncovered paras:',len(uncov),' substantive(>=12 nonspace):',len(substantive))
for a,p in substantive:
    print('%7d | %s'%(a,p.strip()[:130]))
