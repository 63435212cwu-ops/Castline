import json
T = json.load(open('data/cache/df959d743e53206f56db2f92.docs.json'))[0]['text']
C = json.load(open('loop/state/out/read_xiyou_L0_0024.candidate.json'))
N = []
def w(o):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o: N.append(o)
        for v in o.values(): w(v)
    elif isinstance(o, list):
        for v in o: w(v)
w(C)
bad = [n for n in N if T[n['start']:n['end']] != n['quote'] or T.count(n['quote']) != 1
       or not (164172 <= n['start'] and n['end'] <= 171564)
       or n['sourceHash'] != 'c282cf39b2ae739a15a3efe4a0e83af546c525bcaad3bac6e21c9d6179a152a2']
print('nodes=%d distinct=%d bad=%d' % (len(N), len({n['quote'] for n in N}), len(bad)))
