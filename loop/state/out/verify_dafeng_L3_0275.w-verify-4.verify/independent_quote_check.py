import json,hashlib,sys
DOC='data/cache/1063b17ca65ec1b76f30e460.docs.json'
CAND='loop/state/out/read_dafeng_L3_0275.candidate.json'
SH='fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839'
S,E=1162472,1167780
t=json.load(open(DOC))[0]['text']; s=t[S:E]
cand=json.load(open(CAND))
refs=[]
def walk(o):
    if isinstance(o,dict):
        if 'quote' in o and isinstance(o.get('start'),int): refs.append(o)
        for v in o.values(): walk(v)
    elif isinstance(o,list):
        for v in o: walk(v)
walk(cand)
bad=[]
for o in refs:
    q,a,b=o['quote'],o['start'],o['end']
    if t[a:b]!=q: bad.append(('slice',q[:30]))
    if not (S<=a<E and S<b<=E): bad.append(('range',q[:30]))
    if t.find(q)<0: bad.append(('find',q[:30]))
    if o.get('sourceHash')!=SH: bad.append(('hash',q[:30]))
    if o.get('inAuthorRegion'): bad.append(('ps',q[:30]))
    if 'wholeTextOccurrences' in o and o['wholeTextOccurrences']!=t.count(q): bad.append(('wc',q[:30]))
    if 'occurrencesInRange' in o and o['occurrencesInRange']!=s.count(q): bad.append(('rc',q[:30]))
    if 'startIsFirstOccurrence' in o and o['startIsFirstOccurrence']!=(t.find(q)==a): bad.append(('first',q[:30]))
print('refs=%d problems=%d' % (len(refs),len(bad)))
for x in bad[:10]: print(' ',x)
assert not bad
print('OK')
