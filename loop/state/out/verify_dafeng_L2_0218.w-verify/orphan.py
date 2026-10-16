import json,re
ROOT='/Users/carmen/Desktop/星系'
C=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))
def labels(txt): return set(re.findall(r'P\d{3}', txt or ''))
print('=== quotes whose paragraph label is NOT cited in that column prose ===')
tot=0; orph=0
for t in C['tasks']:
    for col in ['objective','obstacle','action','result','cost']:
        v=t[col]
        if not isinstance(v,dict): continue
        cited=labels(v.get('text',''))|labels(v.get('note',''))
        ql=[q.get('paraLabel') for q in (v.get('quotes') or [])]
        tot+=len(ql)
        miss=[p for p in ql if p not in cited]
        if miss:
            orph+=len(miss)
            print(f'  {t["id"]}.{col}: quotes={ql} not-cited={miss}')
print(f'  -> {orph}/{tot} task-column quotes have no paragraph-label mention in their own column prose')
print()
print('=== same test for causeEdges / states / knowledgeDiffs / foreshadows / worldSettings / themeReadings ===')
for sec,fields in [('causeEdges',['mechanism']),('states',['before','after','anchor']),
                   ('knowledgeDiffs',['what','note']),('foreshadows',['setup','payoff','unresolvedReason']),
                   ('worldSettings',['explain']),('themeReadings',[])]:
    for e in C[sec]:
        txt=' '.join(str(e.get(f) or '') for f in fields)
        for lst in ('whoKnows','whoDoesNotKnow'):
            if lst in e: txt+=' '+' '.join(e[lst])
        for sp in ('support','counter'):
            if sp in e:
                for x in e[sp]: txt+=' '+str(x.get('what') or '')
        cited=labels(txt)
        ql=[q.get('paraLabel') for q in (e.get('quotes') or [])]
        miss=[p for p in ql if p not in cited]
        if miss: print(f'  {sec}.{e["id"]}: quotes={ql} not-cited={miss}')
