import json,re
ROOT='/Users/carmen/Desktop/星系'
t=json.load(open(f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
S,E=813350,817425; seg=t[S:E]
C=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))
def strip_quotes(o):
    if isinstance(o,dict): return {k:strip_quotes(v) for k,v in o.items() if k!='quote'}
    if isinstance(o,list): return [strip_quotes(v) for v in o]
    return o
prose=json.dumps(strip_quotes(C),ensure_ascii=False)
# sentences = split on 。！？ and ..... ; keep the delimiter
sents=[]
for m in re.finditer(r'[^。！？\n]*(?:。|！|？|\.\.\.\.\.?|\.\.\.\.)', seg):
    s=m.group().strip()
    if len(s)>=12: sents.append((S+m.start()+ (len(m.group())-len(m.group().lstrip())), s))
seen=set(); uniq=[]
for a,s in sents:
    if s in seen: continue
    seen.add(s); uniq.append((a,s))
missing=[(a,s) for a,s in uniq if s not in prose]
print(f'sentences(counted once)={len(uniq)} | present-in-prose={len(uniq)-len(missing)} | quote-only={len(missing)}')
print()
for a,s in missing:
    inq = s in seg
    print(f'  [{a}] {s[:120]!r}')
