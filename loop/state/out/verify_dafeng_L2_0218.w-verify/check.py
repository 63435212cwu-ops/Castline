import json, hashlib, sys, re
ROOT='/Users/carmen/Desktop/星系'
d=json.load(open(f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'))
t=d[0]['text']
S,E=813350,817425
c=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))

def collect(o, path='', out=None):
    if out is None: out=[]
    if isinstance(o,dict):
        # a quote node?
        if 'quote' in o and isinstance(o['quote'],str):
            out.append((path,o))
        for k,v in o.items():
            collect(v, path+'.'+k, out)
    elif isinstance(o,list):
        for i,v in enumerate(o):
            collect(v, f'{path}[{i}]', out)
    return out

qs=collect(c)
print('total quote nodes:', len(qs))
bad=[]; oob=[]; notinslice=[]
for p,q in qs:
    text=q['quote']; st=q.get('start'); en=q.get('end')
    if st is None or en is None:
        bad.append((p,'missing offsets',text[:40])); continue
    if t[st:en]!=text:
        bad.append((p,f't[st:en] mismatch st={st} en={en}', repr(t[st:en])[:80]+' != '+repr(text)[:80]))
    if en-st!=len(text):
        bad.append((p,f'len mismatch {en-st} vs {len(text)}',text[:40]))
    if not (S<=st and en<=E):
        oob.append((p,st,en,text[:40]))
print('VERBATIM FAILURES:', len(bad))
for b in bad[:20]: print('  ', b)
print('OUT-OF-RANGE:', len(oob))
for b in oob[:20]: print('  ', b)
