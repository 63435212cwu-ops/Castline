import json,re
ROOT='/Users/carmen/Desktop/星系'
t=json.load(open(f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
S,E=813350,817425; seg=t[S:E]
C=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))

print('### REV-A: is there ANY causeEdge / rejectedEdge whose from/to touches P014 (苦肉计提问)?')
for sec in ['causeEdges','rejectedEdges']:
    for e in C[sec]:
        hit = ('苦肉计' in e['from']+e['to']) or ('P014' in e['from']+e['to']) or any(q.get('paraLabel')=='P014' for q in e['quotes'])
        if hit: print(f'   {sec}.{e["id"]}: {e["from"][:70]} -> {e["to"][:60]}')
print('   all causeEdges from/to:')
for e in C['causeEdges']:
    print(f'     {e["id"]}: {e["from"][:58]}')
print('   P015/P016 paragraph label present in ANY edge?',
      any(q.get('paraLabel') in ('P015','P016') for sec in ['causeEdges','rejectedEdges'] for e in C[sec] for q in e['quotes']))

print()
print('### REV-B: is the chapter-title emotion (爽) registered as any state/knowledgeDiff?')
for s in C['states']: print(f'   state {s["id"]}: who={s["who"][:40]} after={s["after"][:60]}')
print('   "爽" in any state before/after:', any('爽' in (s['before']+s['after']+s['anchor']) for s in C['states']))
print('   "爽" in any knowledgeDiff:', any('爽' in json.dumps(k,ensure_ascii=False) for k in C['knowledgeDiffs']))
print('   P086 quoted at:', [q.get('paraLabel') for sec in C for e in (C[sec] if isinstance(C[sec],list) else []) for q in (e.get('quotes') or []) if isinstance(e,dict) and q.get('paraLabel')=='P086'] if False else '')
def qs(o,out=None):
    if out is None: out=[]
    if isinstance(o,dict):
        if isinstance(o.get('quote'),str) and 'start' in o: out.append(o)
        for v in o.values(): qs(v,out)
    elif isinstance(o,list):
        for v in o: qs(v,out)
    return out
Q=qs(C)
for p in ['P086','P087','P088']:
    print(f'   {p} appears in sections:', sorted({k for k in C if isinstance(C[k],list) and any(isinstance(x,dict) and any(q.get("paraLabel")==p for q in qs(x)) for x in C[k])}))

print()
print('### REV-C: 熬夜 registered anywhere outside the embedded quote?')
import copy
def stripq(o):
    if isinstance(o,dict): return {k:stripq(v) for k,v in o.items() if k!='quote'}
    if isinstance(o,list): return [stripq(v) for v in o]
    return o
prose=json.dumps(stripq(C),ensure_ascii=False)
print('   occurrences of 熬夜 in prose-minus-quotes:', prose.count('熬夜'))
for m in re.finditer('熬夜',prose):
    a=max(0,m.start()-90); print('     ctx:',prose[a:m.end()+90])
print('   熬夜 in states:', any('熬夜' in json.dumps(s,ensure_ascii=False) for s in C['states']))
print('   熬夜 in unknowns:', any('熬夜' in json.dumps(u,ensure_ascii=False) for u in C['unknowns']))
print('   熬夜 anywhere in candidate:', json.dumps(C,ensure_ascii=False).count('熬夜'))

print()
print('### REV-D: 一号 self-stated credence P016 registered as a fact anywhere but NW1?')
for k in C:
    if isinstance(C[k],list):
        for x in C[k]:
            if isinstance(x,dict) and any(q.get('paraLabel')=='P016' for q in qs(x)):
                print(f'   P016 cited in {k}.{x.get("id")}')
print('   "齐党" in knowledgeDiffs:', any('齐党' in json.dumps(k,ensure_ascii=False) for k in C['knowledgeDiffs']))
for k in C['knowledgeDiffs']:
    print(f'   {k["id"]}.what={k["what"][:80]}')
