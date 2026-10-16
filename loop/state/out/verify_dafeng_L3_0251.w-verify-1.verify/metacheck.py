import json
DOC='data/cache/1063b17ca65ec1b76f30e460.docs.json'
d=json.load(open(DOC)); T=d[0]['text']; S,E=1032194,1038254
cand=json.load(open('loop/state/out/read_dafeng_L3_0251.candidate.json'))
quotes=[]
def walk(o,path=''):
    if isinstance(o,dict):
        if isinstance(o.get('quote'),str) and 'start' in o and 'end' in o: quotes.append((path,o))
        for k,v in o.items(): walk(v,path+'/'+str(k))
    elif isinstance(o,list):
        for i,v in enumerate(o): walk(v,path+'[%d]'%i)
walk(cand)
# paragraph index within slice: split by '\n' preserving, compute para index for each char offset
paras=[]; pos=S
for line in T[S:E].split('\n'):
    paras.append((pos,pos+len(line))); pos+=len(line)+1
def para_of(off):
    for i,(a,b) in enumerate(paras):
        if a<=off<b: return i+1
    return None
badcnt=[];badfirst=[];badpara=[];badfirstat=[]
for p,q in quotes:
    txt=q['quote']; st=q['start']
    occ=T.count(txt)
    if 'wholeTextOccurrences' in q and q['wholeTextOccurrences']!=occ: badcnt.append((p,q['wholeTextOccurrences'],occ,txt[:40]))
    inrange=T.count(txt,S,E)
    if 'occurrencesInRange' in q and q['occurrencesInRange']!=inrange: badcnt.append((p,'range',q['occurrencesInRange'],inrange,txt[:40]))
    first=T.find(txt)
    if q.get('startIsFirstOccurrence') is not None:
        if q['startIsFirstOccurrence']!=(first==st): badfirst.append((p,q['startIsFirstOccurrence'],first,st,txt[:40]))
    if 'firstOccurrenceAt' in q and q['firstOccurrenceAt']!=first: badfirstat.append((p,q['firstOccurrenceAt'],first,txt[:40]))
    if 'para' in q:
        ap=para_of(st)
        if ap!=q['para']: badpara.append((p,q['para'],ap,txt[:40]))
    if 'declaredPara' in q:
        ap=para_of(st)
        if ap!=q['declaredPara']: badpara.append((p,'decl',q['declaredPara'],ap,txt[:40]))
print('bad occ counts:',len(badcnt))
for b in badcnt[:20]: print('  ',b)
print('bad startIsFirstOccurrence:',len(badfirst))
for b in badfirst[:20]: print('  ',b)
print('bad firstOccurrenceAt:',len(badfirstat))
for b in badfirstat[:20]: print('  ',b)
print('bad para numbers:',len(badpara))
for b in badpara[:20]: print('  ',b)
print('nonEmptyParagraphs declared:',cand['source'].get('nonEmptyParagraphs'))
ne=[l for l in T[S:E].split('\n') if l.strip()]
print('actual non-empty lines:',len(ne))
