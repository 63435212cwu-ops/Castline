# -*- coding: utf-8 -*-
"""变异自检：故意把候选改坏，确认 verify_independent.py 真的会拦下来。

一个「永远判 pass」的校验器等于没有校验器。本脚本对候选做 5 种真实缺陷注入，
每次都在临时副本上跑 verify_independent.py，要求它**非 0 退出**。
原候选文件只读、不被修改。
"""
import json, os, shutil, subprocess, sys, tempfile

CAND = 'loop/state/out/read_dafeng_L1_0249.candidate.json'
VERIFY = 'loop/state/out/read_dafeng_L1_0249.w-read-4.build/verify_independent.py'

base = json.load(open(CAND, encoding='utf-8'))

def run(cand_obj):
    """把变异体写到临时文件，跑校验器（校验器读固定路径 ⇒ 用 CAND 的备份替换法）。"""
    bak = CAND + '.mutbak'
    shutil.copy2(CAND, bak)
    try:
        with open(CAND, 'w', encoding='utf-8') as fh:
            json.dump(cand_obj, fh, ensure_ascii=False)
        r = subprocess.run([sys.executable, '-B', '-s', VERIFY], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr
    finally:
        shutil.move(bak, CAND)

muts = []

# m1 改一个 start 偏移（引用定位错误）
m = json.loads(json.dumps(base)); m['tasks'][0]['objective']['quotes'][0]['start'] += 1
muts.append(('m1 start 偏移 +1', m))

# m2 改一个 quote 文本（回读不成立）
m = json.loads(json.dumps(base)); q = m['tasks'][0]['objective']['quotes'][0]; q['quote'] = q['quote'][:-1] + '。'
muts.append(('m2 quote 末字改坏', m))

# m3 改 sourceHash
m = json.loads(json.dumps(base)); m['causeEdges'][0]['quotes'][0]['sourceHash'] = 'deadbeef' * 8
muts.append(('m3 sourceHash 改坏', m))

# m4 删掉一个内容分区
m = json.loads(json.dumps(base)); m.pop('themeReadings', None)
muts.append(('m4 删掉 themeReadings', m))

# m5 让任务五栏共用同一句引文
m = json.loads(json.dumps(base))
t0 = m['tasks'][0]
shared = t0['objective']['quotes'][0]
t0['cost'] = {'text': 'x', 'basis': 'explicit', 'quotes': [dict(shared)]}
t0.pop('costNote', None)
muts.append(('m5 五栏共用同一句引文', m))

# m6 null 栏位不写 Note
m = json.loads(json.dumps(base))
for tk in m['tasks']:
    if tk.get('cost') is None and 'costNote' in tk:
        tk.pop('costNote'); break
muts.append(('m6 null 栏位缺 Note', m))

print('变异体 %d 个；要求每个都被校验器拦下（非 0 退出）\n' % len(muts))
ok = 0
for name, obj in muts:
    rc, out = run(obj)
    caught = rc != 0
    ok += caught
    print('%-28s rc=%d  %s' % (name, rc, '已拦下' if caught else '*** 漏过 ***'))
    if caught:
        line = [l for l in out.splitlines() if l.strip().startswith('!!')]
        if line:
            print('      %s' % line[0].strip()[:110])

print('\n拦下 %d/%d' % (ok, len(muts)))
sys.exit(0 if ok == len(muts) else 1)
