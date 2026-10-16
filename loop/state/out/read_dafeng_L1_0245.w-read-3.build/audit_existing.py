import json, hashlib, pathlib
ROOT = pathlib.Path('.')
docs = json.loads((ROOT/'data/cache/1063b17ca65ec1b76f30e460.docs.json').read_text())
T = docs[0]['text']
S, E = 994884, 1001227
cand = json.loads((ROOT/'loop/state/out/read_dafeng_L1_0245.candidate.json').read_text())

quotes = []
def walk(o, path=''):
    if isinstance(o, dict):
        if 'quote' in o and isinstance(o['quote'], str):
            quotes.append((path, o))
        for k, v in o.items(): walk(v, path+'/'+str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o): walk(v, path+'[%d]'%i)
walk(cand)

bad_pos, bad_range, bad_uniq, uniq_n = [], [], [], 0
for path, q in quotes:
    s, e = q.get('start'), q.get('end')
    if s is None or e is None:
        bad_pos.append((path, 'no-offset')); continue
    if T[s:e] != q['quote']:
        bad_pos.append((path, q['quote'][:30])); continue
    if not (S <= s and e <= E):
        bad_range.append((path, q['quote'][:30]))
    if T.count(q['quote']) != 1:
        bad_uniq.append((path, T.count(q['quote']), q['quote'][:30]))
    else:
        uniq_n += 1

print('total quotes:', len(quotes))
print('bad_pos(mismatch):', len(bad_pos), bad_pos[:5])
print('out_of_range:', len(bad_range), bad_range[:5])
print('not_unique:', len(bad_uniq), bad_uniq[:5])
print('unique_ok:', uniq_n)

# five-slot sharing check inside each task
share = []
for t in cand.get('tasks', []):
    seen = {}
    for slot in ('objective','obstacle','action','result','cost'):
        v = t.get(slot)
        qs = []
        if isinstance(v, dict): qs = [x['quote'] for x in v.get('quotes',[])]
        for q in qs: seen.setdefault(q, []).append(slot)
    for q, slots in seen.items():
        if len(slots) > 1: share.append((t.get('id'), slots, q[:30]))
print('tasks:', len(cand.get('tasks',[])), 'shared-slot-quotes:', len(share), share[:5])

ws = cand.get('worldSettings', [])
print('worldSettings:', len(ws), 'kinds:', {k: sum(1 for w in ws if w.get('kind')==k) for k in ('rule','place','item')})
print('places missing placeState:', [w.get('name') for w in ws if w.get('kind')=='place' and not w.get('placeState')])
print('items missing itemStates:', [w.get('name') for w in ws if w.get('kind')=='item' and not w.get('itemStates')])
print('rules missing institution:', [w.get('name') for w in ws if w.get('kind')=='rule' and not w.get('institution')])
for sec in ('causeEdges','states','foreshadows','themeReadings','unknowns','selfCritique'):
    print(sec, '=', len(cand.get(sec, [])))
