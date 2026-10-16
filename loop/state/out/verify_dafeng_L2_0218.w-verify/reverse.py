import json,random,hashlib
ROOT='/Users/carmen/Desktop/星系'
t=json.load(open(f'{ROOT}/data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
S,E=813350,817425; seg=t[S:E]
C=json.load(open(f'{ROOT}/loop/state/out/read_dafeng_L2_0218.candidate.json'))
def qs(o,out=None,path=''):
    if out is None: out=[]
    if isinstance(o,dict):
        if isinstance(o.get('quote'),str) and 'start' in o: out.append((path,o))
        for k,v in o.items(): qs(v,out,path+'.'+k)
    elif isinstance(o,list):
        for i,v in enumerate(o): qs(v,out,f'{path}[{i}]')
    return out
Q=qs(C)
print('=== CITATION SAMPLE (5, deterministic seed) ===')
random.seed(218)
samp=random.sample(Q,5)
for p,q in samp:
    s=q['quote']; f=t.find(s)
    sec=p.split('[')[0].lstrip('.')
    print(f'  section={sec}')
    print(f'    quote={s[:70]!r}')
    print(f'    recorded=({q["start"]},{q["end"]}) find()={f} verbatim={f==q["start"]} len_ok={q["end"]-q["start"]==len(s)} in_range={S<=q["start"] and q["end"]<=E}')
    print(f'    re-slice_eq={t[q["start"]:q["end"]]==s}')
print()
print('=== COUNTEREXAMPLE QUOTES ===')
for lab,q in [('CE1 许七安 absorb 一号分析','一号的分析，给许七安打开了思路。'),
              ('CE1b 许七安 react 司天监','司天监的术士？许七安吃了一惊。'),
              ('CE2 张巡抚被转述','房间里，李妙真绘声绘色的把“聊天记录”转述了一遍，听的张巡抚和姜律中一愣一愣。'),
              ('R1 一号自陈赞同','【梁有平杀死原本的接头人，销毁账簿里有问题的部分....我个人是赞同这个猜测的。因此，他齐党身份可能性很高。】'),
              ('R2 苦肉计提问','保险起见，她传书道：【有没有杨川南和梁有平是同伙，在演苦肉计的可能？】'),
              ('R2b 一号驳回','【一号：可能性不大，官场规矩，杨川南这次无论如何都要担责任，区别只在轻重。如果你是杨川南，你会自己挖坑自己跳？'),
              ('R3 性质一样','【还有一点，对方既然来试探，说明已经做好梁有平落入打更人手里的心里准备。至少在他们眼里，落入司天监术士和落入打更人手里，性质是一样的。'),
              ('R4 宁宴','张巡抚和姜律中相视一眼，前者目光微闪：“我们到房间说话，宁宴，你也来。”'),
              ('R5 张巡抚熬夜','“李将军心细如发，本官佩服。”张巡抚精神一振，熬夜的疲惫都退去不少。'),
              ('R6 兄弟通吃','金莲道长将地书碎片赠予那位堂弟，其实，是打算兄弟通吃的意思？'),
              ('R7 交换眼神','张巡抚顿时与姜律中等三人无声交换了一个眼神。')]:
    f=seg.find(q)
    print(f'  {lab}: in_seg={f>=0} abs_start={S+f if f>=0 else None} abs_end={S+f+len(q) if f>=0 else None}')
