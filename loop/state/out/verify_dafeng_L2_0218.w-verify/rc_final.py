import json,re
ROOT='/Users/carmen/Desktop/星系'
t=json.load(open(f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
S,E=813350,817425; seg=t[S:E]
C=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))
def qs(o,out=None):
    if out is None: out=[]
    if isinstance(o,dict):
        if isinstance(o.get('quote'),str) and 'start' in o: out.append(o)
        for v in o.values(): qs(v,out)
    elif isinstance(o,list):
        for v in o: qs(v,out)
    return out

print('### RC1: 苦肉计 Q&A arc (P014->P015/P016) absent from edges')
print('   P014/P015/P016 as edge quotes:',
      sorted({q.get('paraLabel') for sec in ('causeEdges','rejectedEdges') for e in C[sec] for q in e['quotes'] if q.get('paraLabel') in ('P014','P015','P016')}) or 'NONE')
print('   P015/P016 cited only in:', sorted({k for k in C if isinstance(C[k],list) and any(isinstance(x,dict) and any(q.get('paraLabel') in ('P015','P016') for q in qs(x)) for x in C[k])}))
print('   quote P014 verbatim:', t.find('保险起见，她传书道：【有没有杨川南和梁有平是同伙，在演苦肉计的可能？】'))
print('   quote P015 verbatim:', t.find('【一号：可能性不大，官场规矩，杨川南这次无论如何都要背责任，区别只在轻重。如果你是杨川南，你会自己挖坑自己跳？'))

print()
print('### RC2: 许七安 infers 二号 unstated motive (P006) — registered as knowledge anywhere?')
P6='她在等我，还是等一号或四号？大概都有...群里的智商担当们没说话，她就不开口讨论案情....许七安理解了二号的想法，以指代笔，键入信息：'
print('   P006 verbatim at:', t.find(P6))
print('   "理解了二号的想法" in candidate:', '理解了二号的想法' in json.dumps(C,ensure_ascii=False))
print('   P006 cited in sections:', sorted({k for k in C if isinstance(C[k],list) and any(isinstance(x,dict) and any(q.get('paraLabel')=='P006' for q in qs(x)) for x in C[k])}))
print('   covered by any knowledgeDiff?:', any('P006' in json.dumps(k,ensure_ascii=False) for k in C['knowledgeDiffs']))

print()
print('### RC3: P061(五号轻描淡写) -> P063/P064(许七安小号自捧) arc absent from edges?')
print('   P061/P063/P064 in edge quotes:',
      sorted({q.get('paraLabel') for sec in ('causeEdges','rejectedEdges') for e in C[sec] for q in e['quotes'] if q.get('paraLabel') in ('P061','P063','P064')}) or 'NONE')
print('   P061 cited in sections:', sorted({k for k in C if isinstance(C[k],list) and any(isinstance(x,dict) and any(q.get('paraLabel')=='P061' for q in qs(x)) for x in C[k])}))
print('   P063 cited in sections:', sorted({k for k in C if isinstance(C[k],list) and any(isinstance(x,dict) and any(q.get('paraLabel')=='P063' for q in qs(x)) for x in C[k])}))
for lab,q in [('P061','【五：还好吧，两个月破一品嘛。】'),('P062','一直插不上嘴的五号，传书评价。'),
              ('P063','【三：这已经很不容易了。】'),('P064','许七安开小号为自己装逼。')]:
    print(f'   {lab} verbatim at:', t.find(q))
