import json,re
ROOT='/Users/carmen/Desktop/星系'
d=json.load(open(f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'))
t=d[0]['text']; S,E=813350,817425
seg=t[S:E]
# split into paragraphs like the candidate (non-empty lines)
lines=[];pos=0
for m in re.finditer(r'[^\n]+', seg):
    lines.append((S+m.start(), S+m.end(), m.group()))
for i,(a,b,s) in enumerate(lines):
    print(f'P{i:03d} [{a},{b}) {s[:150]}')
