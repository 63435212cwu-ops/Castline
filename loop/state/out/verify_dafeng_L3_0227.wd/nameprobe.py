import json, re
t=json.load(open('data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
START,END=862305,872127
S=t[START:END]
cand=json.load(open('loop/state/out/read_dafeng_L3_0227.candidate.json'))
raw=json.dumps(cand,ensure_ascii=False)

# candidate prose = everything except the 'quote' values
def strip_quotes(o):
    if isinstance(o,dict):
        return {k:strip_quotes(v) for k,v in o.items() if k not in ('quote',)}
    if isinstance(o,list): return [strip_quotes(v) for v in o]
    return o
prose=json.dumps(strip_quotes(cand),ensure_ascii=False)

# candidate names: CJK 2-4 grams that look like names
names=set(re.findall(r'[\u4e00-\u9fff]{2,4}', prose))
# filter to plausible proper nouns by checking not-in-slice but CJK
cjk_all=set(re.findall(r'[\u4e00-\u9fff]{2,4}', S))
missing=sorted(n for n in names if n not in S)
# heuristics: report those that are name-like (appear in a person-ish context)
print('total candidate n-grams:',len(names),' not present in slice:',len(missing))
