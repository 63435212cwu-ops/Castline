# -*- coding: utf-8 -*-
"""独立审计（不复用 build 脚本的任何代码路径）：把候选里的每条引文重新在原文里定位。"""
import json, hashlib, sys
DOCS='data/cache/1063b17ca65ec1b76f30e460.docs.json'
CAND='loop/state/out/read_dafeng_L2_0174.candidate.json'
SRC_HASH='fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839'
S,E=627871,631698
raw=open(DOCS,'rb').read()
assert hashlib.sha256(raw).hexdigest()==SRC_HASH
T=json.loads(raw.decode('utf-8'))[0]['text']
assert T[S:E].startswith('第一百七十四章 鸡精')
c=json.load(open(CAND))

quotes=[]
def walk(o,path='root'):
    if isinstance(o,dict):
        if set(('quote','start','end','sourceHash')) <= set(o):
            quotes.append((path,o))
        for k,v in o.items(): walk(v,path+'.'+str(k))
    elif isinstance(o,list):
        for i,v in enumerate(o): walk(v,'%s[%d]'%(path,i))
walk(c)

bad=[]; warn=[]
for path,q in quotes:
    t,a,b,h=q['quote'],q['start'],q['end'],q['sourceHash']
    if T[a:b]!=t: bad.append(('切片不等',path,t[:30]))
    if not (S<=a and b<=E): bad.append(('越界',path,t[:30]))
    if T.find(t)<0: bad.append(('全文找不到',path,t[:30]))
    if h!=SRC_HASH: bad.append(('哈希不符',path,t[:30]))
    # 区间内命中次数
    n=0;i=T.find(t)
    while i>=0:
        if S<=i and i+len(t)<=E: n+=1
        i=T.find(t,i+1)
    if n!=1: warn.append(('区间内命中%d次'%n,path,t[:30]))
    if not (T.find(t)>=0 and q.get('wholeTextOccurrences',T.count(t))==T.count(t)):
        bad.append(('出现次数声明不符',path,t[:30]))

print('引文对象总数',len(quotes))
print('硬错误',len(bad))
for x in bad[:20]: print('  BAD',x)
print('警告',len(warn))
for x in warn[:20]: print('  WARN',x)

# 任务五栏复用检查
print('\n--- 任务内五栏引文复用 ---')
for t in c['tasks']:
    seen={}
    dup=[]
    for col in ('objective','obstacle','action','result','cost'):
        v=t.get(col)
        if not isinstance(v,dict): continue
        for q in v.get('quotes',[]):
            k=(q['start'],q['end'])
            if k in seen: dup.append((col,seen[k],q['quote'][:30]))
            seen[k]=col
    print(t['id'],'复用' if dup else 'OK', dup)

# 五栏 null 必须带 Note
print('\n--- null 栏位与 Note ---')
for t in c['tasks']:
    for col in ('objective','obstacle','action','result','cost'):
        v=t.get(col)
        if v is None:
            note=t.get(col+'Note')
            print(t['id'],col,'null','Note:',('有' if note else '**缺**'))
        elif isinstance(v,dict):
            assert v.get('basis') in ('explicit','inferred','derived','unverified'), (t['id'],col,v.get('basis'))
        else:
            print(t['id'],col,'**既非 null 也非对象**',type(v).__name__)

# 必需分区
print('\n--- 分区 ---')
for k in ('tasks','causeEdges','states','foreshadows','worldSettings','themeReadings'):
    print(k, len(c[k]) if isinstance(c.get(k),list) else '**缺**')
print('semanticReview =',c.get('semanticReview'))
print('unknowns',len(c['unknowns']),'selfCritique',len(c['selfCritique']))
# worldSettings 字段完备
print('\n--- worldSettings 字段 ---')
for w in c['worldSettings']:
    need = {'place':('placeState',),'item':('itemStates',),'rule':('institution',)}[w['kind']]
    miss=[f for f in need if f not in w]
    print(w['id'],w['kind'],w['name'],'缺:'+str(miss) if miss else 'OK',
          w.get('placeState') or w.get('itemStates') or w.get('institution'))
# themeReadings 三件
print('\n--- themeReadings 三件 ---')
for th in c['themeReadings']:
    print(th['id'],'perspective' in th,'support' in th,len(th.get('support',[])),'counter' in th,len(th.get('counter',[])))
print('\n结论:', 'PASS' if not bad else 'FAIL')
sys.exit(1 if bad else 0)
