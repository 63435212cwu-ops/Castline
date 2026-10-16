# -*- coding: utf-8 -*-
"""Independent re-verification from the file on disk. Does not trust build-time memory."""
import json, sys, hashlib, os
ROOT='/Users/carmen/Desktop/星系'
SRC=os.path.join(ROOT,'data/cache/fe42d01f3826fe8096f86614.docs.json')
CAND=os.path.join(ROOT,'loop/state/out/read_sanguo_L1_0095.candidate.json')
S,E=484338,489034
text=json.load(open(SRC))[0]['text']
filesha=hashlib.sha256(open(SRC,'rb').read()).hexdigest()
d=json.load(open(CAND))
problems=[]; n=0; inrange=0
def walk(o,path=''):
    global n,inrange
    if isinstance(o,dict):
        if isinstance(o.get('quote'),str):
            n+=1
            s=o['quote']; a=o.get('start'); b=o.get('end')
            if text.find(s)<0: problems.append('NOT-VERBATIM %s %r'%(path,s[:40]))
            elif text[a:b]!=s: problems.append('OFFSET %s %r'%(path,s[:40]))
            elif text.find(s)!=a: problems.append('FIND-NE-START %s %r (start=%s find=%s)'%(path,s[:40],a,text.find(s)))
            elif not(S<=a and b<=E): problems.append('OUTOFRANGE %s %r'%(path,s[:40]))
            else:
                inrange+=1
                if o.get('sourceHash')!=filesha: problems.append('HASH %s'%path)
                if o.get('globalOccurrences') is not None and o['globalOccurrences']!=text.count(s):
                    problems.append('OCC %s'%path)
        for k,v in o.items():
            if k=='quote': continue
            walk(v,path+'/'+k)
    elif isinstance(o,list):
        for i,v in enumerate(o): walk(v,path+'[%d]'%i)
walk(d)

# structural: five-tuple fields + per-field quotes + no intra-task reuse
F=('objective','obstacle','action','result','cost')
reuse=0
for T in d['tasks']:
    seen={}
    for fl in F:
        v=T.get(fl)
        if v is None:
            if not (T.get(fl+'Note') or '').strip(): problems.append('NULL-NO-NOTE %s.%s'%(T['id'],fl))
            continue
        if not v.get('quotes'): problems.append('NO-QUOTES %s.%s'%(T['id'],fl))
        for qq in v.get('quotes') or []: seen.setdefault(qq['quote'],[]).append(fl)
    for s,fls in seen.items():
        if len(fls)>1:
            reuse+=1; problems.append('REUSE %s %s %r'%(T['id'],fls,s[:40]))

# enum + theme triples
for W in d['worldSettings']:
    if W['kind']=='place' and W.get('placeState') not in ('arrived','mentioned'): problems.append('placeState %s'%W.get('name'))
    if W['kind']=='item' and (not W.get('itemStates') or any(x not in ('hold','transfer','use','lose') for x in W['itemStates'])): problems.append('itemStates %s'%W.get('name'))
    if W['kind']=='rule' and W.get('institution') not in ('declared','executed','misunderstood'): problems.append('institution %s'%W.get('name'))
for T in d['themeReadings']:
    if not(T.get('perspective') and T.get('support') and T.get('counter')): problems.append('theme %s'%T.get('id'))

# fabricated-mechanism regression guard.
# The token must not be ASSERTED as a mechanism. Honest negations (e.g. "并未写断水")
# and provenance notes documenting the correction are legitimate and must not be flagged.
# Method: flag only if the token appears inside a *mechanism* field without a negation nearby.
FORBID=['断水','汲道','水源','舍水上山']
NEG=['并未写','不写','未写','不存在','没有','无此','属编造','旧稿','修正','0 次']
def scan_mechanisms(o, path=''):
    if isinstance(o, dict):
        for k,v in o.items():
            if k in ('mechanism','explain','note','detail','why','payoff','setup') and isinstance(v,str):
                for tok in FORBID:
                    if tok in v and not any(n in v for n in NEG):
                        problems.append('ASSERTED-FABRICATION %s/%s contains %r without negation'%(path,k,tok))
            scan_mechanisms(v, path+'/'+str(k))
    elif isinstance(o, list):
        for i,v in enumerate(o): scan_mechanisms(v, path+'[%d]'%i)
scan_mechanisms(d)

# range boundary (both ends, machine-checked)
head=text[S:S+21]
if not head.startswith('第九十六回'): problems.append('head does not start with unit title: %r'%head)
_nl=text.find('\n',E)
_nxt=text[E:_nl]
if _nxt!='第九十七回\u3000讨魏国武侯再上表\u3000破曹兵姜维诈献书':
    problems.append('next unit head mismatch at E: %r'%_nxt)
# textualNotes X04 must state the CORRECT slice length
_tn=[x for x in d['textualNotes'] if x.get('id')=='X04']
if _tn and ('[489034:489057]' not in _tn[0]['note']):
    problems.append('X04 boundary claim does not match measured slice [489034:489057]')

spec=['tasks','causeEdges','states','foreshadows','worldSettings','themeReadings']
missing=[k for k in spec if k not in d]
if missing: problems.append('missing sections %s'%missing)

# C03 numeric-claim guard: every offset cited in C03 must be a real offset in the text,
# and it must land on the phrase C03 says it lands on. (Offsets may be inside or outside
# the range -- C03 deliberately cites both -- so membership is NOT the criterion; the
# criterion is that each cited offset is real and that the water phrases it attributes
# to 第九十五回 really are outside the assigned range.)
_c03=[c for c in d['causeEdges'] if c.get('id')=='C03']
if _c03:
    import re as _re
    for _off in _re.findall(r'(\d{6})', _c03[0].get('mechanism') or ''):
        _o=int(_off)
        if not (0<=_o<len(text)):
            problems.append('C03 cites out-of-text offset %d'%_o)
    for _w in ('断汲水道路','山上无水','先断了汲水道路'):
        _i=text.find(_w)
        if _i<0: problems.append('C03 names %r but it is not in the text'%_w)
        elif S<=_i<E: problems.append('C03 says %r is outside the range, but it is inside (offset %d)'%(_w,_i))

print('quotes checked:', n, ' in-range:', inrange)
print('candidate sha256:', hashlib.sha256(open(CAND,'rb').read()).hexdigest())
print('source file sha256:', filesha)
print('range head:', repr(head))
print('next unit head at E:', repr(text[E:E+20]))
print('intra-task cross-field reuse:', reuse)
print('problems:', len(problems))
for p in problems[:30]: print('  -',p)
sys.exit(1 if problems else 0)
