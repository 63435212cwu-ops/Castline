import json,re
ROOT='/Users/carmen/Desktop/星系'
t=json.load(open(f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
S,E=813350,817425; seg=t[S:E]
C=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))

# candidate prose WITHOUT quote strings
def strip_quotes(o):
    if isinstance(o,dict):
        return {k:strip_quotes(v) for k,v in o.items() if k!='quote'}
    if isinstance(o,list): return [strip_quotes(v) for v in o]
    return o
prose=json.dumps(strip_quotes(C),ensure_ascii=False)

paras=[(m.start()+S,m.end()+S,m.group()) for m in re.finditer(r'[^\n]+',seg)]
# split paragraph into clause units on punctuation
SPLIT=re.compile(r'(?<=[。！？])|(?<=\.\.\.\.)|(?<=，)')
for i,(a,b,txt) in enumerate(paras):
    body=re.sub(r'^\s+','',txt)
    units=[u for u in SPLIT.split(body) if len(u.strip())>=6]
    orphan=[u for u in units if u.strip() and u.strip() not in prose]
    if orphan and i not in (0,):
        print(f'P{i:03d}: units-not-in-prose={len(orphan)}/{len(units)}')
        for u in orphan: print(f'      ONLY-AS-QUOTE: {u.strip()[:105]!r}')
