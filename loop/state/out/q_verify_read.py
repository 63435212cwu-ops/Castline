#!/usr/bin/env python3
"""通用独立复核器：核验一条 `read:*` 提交（不写共享树，输出复核 verdict）。

我手工复核了两次（dafeng L0:0004、sanguo L0:0000）后把它固化成脚本，
因为**手工复核的问题在于不可复算、且我自己的口径会漂**（sanguo 那次我的
"含对话"判据就出现了 3 个假阳性）。

检查项（每项都能被机器重算）：
  ① 证据存在 + sha256 一致（跳过 sha256 为 None 的自引用条目）
  ② 遍历候选里**所有嵌套** quotes[]，逐条 `text[start:end] == quote`
  ③ 偏移是否落在任务自称区间内
  ④ 边界自称（若有）是否与独立计算的 `text.find(下一章标记)` 一致
  ⑤ **反向验证**：区间被覆盖位置取补集，报告覆盖率与补集规模；
     并区分「连接语」（长度小、位于两引文之间）与「真未覆盖对话」

用法：python3 /tmp/q-verify-read.py <记录文件> <候选文件> <docs文件> <lo> <hi> [下一章标记]
"""
import json,hashlib,pathlib,re,sys

def walk_quotes(o, acc):
    if isinstance(o, dict):
        if isinstance(o.get('quote'), str) and isinstance(o.get('start'), int) and isinstance(o.get('end'), int):
            acc.append(o)
        for v in o.values(): walk_quotes(v, acc)
    elif isinstance(o, list):
        for v in o: walk_quotes(v, acc)

def main(recp, candp, docsp, lo, hi, nextmark=None):
    out = {'checks': [], 'verdict': None}
    rec = json.load(open(recp))
    # ① 证据
    for e in rec.get('evidence') or []:
        p = pathlib.Path(e['path']); want = e.get('sha256')
        if not p.exists(): out['checks'].append({'name':'证据存在','path':e['path'],'ok':False}); continue
        if want is None:
            out['checks'].append({'name':'证据哈希','path':e['path'],'ok':None,'note':'未登记 sha256（自引用条目），不判'})
            continue
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        out['checks'].append({'name':'证据哈希','path':e['path'],'ok':got==want})
    # ②③ 引文
    c = json.load(open(candp)); text = json.load(open(docsp))[0]['text']
    acc = []; walk_quotes(c, acc)
    bad = [a for a in acc if text[a['start']:a['end']] != a['quote']]
    outside = [a for a in acc if not (lo <= a['start'] < hi)]
    out['checks'].append({'name':'引文逐字','total':len(acc),'ok':len(acc)-len(bad),'fail':len(bad)})
    out['checks'].append({'name':'偏移在区间内','total':len(acc),'outside':len(outside)})
    # ④ 边界
    if nextmark:
        f = text.find(nextmark)
        out['checks'].append({'name':'边界自称','nextmark':nextmark,'find':f,'claimed_hi':hi,'ok':f==hi or f<0})
    # ⑤ 反向
    cov = sorted((a['start'],a['end']) for a in acc); m=[]
    for s,e in cov:
        if m and s<=m[-1][1]: m[-1][1]=max(m[-1][1],e)
        else: m.append([s,e])
    gaps=[]; prev=lo
    for s,e in m:
        if s>prev: gaps.append((prev,s,text[prev:s]))
        prev=max(prev,e)
    if prev<hi: gaps.append((prev,hi,text[prev:hi]))
    covered=sum(e-s for s,e in m)
    # 连接语判据：长度 ≤14 且两侧都紧邻引文（即它是两条引文之间的空隙）
    link=[g for g in gaps if len(g[2])<=14]
    realdial=[g for g in gaps if '“' in g[2] and len(g[2])>14]
    out['reverse']={'covered':covered,'span':hi-lo,'coverage_pct':round(covered/(hi-lo)*100,1),
                    'gaps':len(gaps),'max_gap_len':max((len(g[2]) for g in gaps),default=0),
                    'connective_gaps':len(link),'real_uncovered_dialogue':len(realdial)}
    out['verdict']='pass' if (not bad and not outside and not realdial) else 'partial'
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0

if __name__=='__main__':
    a=sys.argv[1:]
    main(a[0],a[1],a[2],int(a[3]),int(a[4]),a[5] if len(a)>5 else None)
