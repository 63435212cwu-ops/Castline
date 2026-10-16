import json, sys, hashlib
SRC='data/cache/1063b17ca65ec1b76f30e460.docs.json'
START,END=862305,872127
t=json.load(open(SRC))[0]['text']
S=t[START:END]
cand=json.load(open('loop/state/out/read_dafeng_L3_0227.candidate.json'))
print('sliceSha256 recomputed:', hashlib.sha256(S.encode()).hexdigest())
print('candidate sliceSha256  :', cand['source']['sliceSha256'])

nodes=[]
def walk(o,path=''):
    if isinstance(o,dict):
        # a quote node: has 'quote' (str) and maybe start/end
        if isinstance(o.get('quote'),str):
            nodes.append((path,o.get('quote'),o.get('start'),o.get('end'),o))
        for k,v in o.items():
            walk(v,path+'/'+k)
    elif isinstance(o,list):
        for i,v in enumerate(o):
            walk(v,path+'[%d]'%i)
walk(cand)
print('quote nodes found:',len(nodes))
bad=[]; offbad=[]; oob=[]
for p,q,st,en,node in nodes:
    i=S.find(q)
    if i<0:
        j=t.find(q)
        bad.append((p,q[:40],j))
        continue
    a=START+i; b=a+len(q)
    if st is not None and (st!=a or en!=b):
        offbad.append((p,q[:30],st,en,a,b))
    if a<START or b>END: oob.append((p,))
print('NOT FOUND in slice:',len(bad))
for x in bad[:20]: print('  MISS',x)
print('offset mismatch:',len(offbad))
for x in offbad[:20]: print('  OFF',x)
print('out of range:',len(oob))
