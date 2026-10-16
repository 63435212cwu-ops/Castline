#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核脚本：大奉打更人 第四十六章 赎人 [1162472,1167780)

不 import 候选作者的任何构建/审计模块，只读原文与候选 JSON。

跑法：
    python3 -B -s loop/state/out/verify_dafeng_L3_0275.w-verify-4.verify/independent_check.py
期望：全部判据 OK，退出码 0。
"""
import hashlib
import json
import re
import sys

DOC = 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
CAND = 'loop/state/out/read_dafeng_L3_0275.candidate.json'
VERDICT = 'loop/state/out/verify_dafeng_L3_0275.verdict.json'
SH = 'fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839'
S, E = 1162472, 1167780
PS_START = 1167694          # 作者 PS 起点（叙述区外）

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print('%-46s %s %s' % (name, 'OK  ' if ok else 'FAIL', detail))


t = json.load(open(DOC))[0]['text']
s = t[S:E]
cand = json.load(open(CAND))
verdict = json.load(open(VERDICT))

# ── 1. 源身份 ────────────────────────────────────────────────────────────────
check('source sha256 == task.sourceHash',
      hashlib.sha256(open(DOC, 'rb').read()).hexdigest() == SH)
check('slice head == 第四十六章 赎人', s.startswith('第四十六章 赎人'), repr(s[:8]))
check('slice length == 5308 codepoints', len(s) == 5308, str(len(s)))
check('slice sha256 matches candidate claim',
      hashlib.sha256(s.encode()).hexdigest() == cand['source']['sliceSha256'])

# ── 2. 候选引文逐字复核（全部 184 条）───────────────────────────────────────
refs = []


def walk(o):
    if isinstance(o, dict):
        if 'quote' in o and isinstance(o.get('start'), int):
            refs.append(o)
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(cand)
bad = []
for o in refs:
    q, a, b = o['quote'], o['start'], o['end']
    if t[a:b] != q:
        bad.append(('slice!=quote', q[:30]))
    if not (S <= a < E and S < b <= E):
        bad.append(('out-of-range', q[:30]))
    if t.find(q) < 0:
        bad.append(('find-fail', q[:30]))
    if o.get('sourceHash') != SH:
        bad.append(('bad-sourceHash', q[:30]))
    if o.get('inAuthorRegion'):
        bad.append(('in-author-region', q[:30]))
    if 'wholeTextOccurrences' in o and o['wholeTextOccurrences'] != t.count(q):
        bad.append(('wholeTextOccurrences', q[:30]))
    if 'occurrencesInRange' in o and o['occurrencesInRange'] != s.count(q):
        bad.append(('occurrencesInRange', q[:30]))
    if 'startIsFirstOccurrence' in o and o['startIsFirstOccurrence'] != (t.find(q) == a):
        bad.append(('startIsFirstOccurrence', q[:30]))
check('all %d candidate quotes verbatim+offsets' % len(refs), not bad, str(bad[:3]))
check('candidate quote count == its own claim',
      len(refs) == cand['machineSelfCheck']['quoteRefsChecked'],
      '%d vs %d' % (len(refs), cand['machineSelfCheck']['quoteRefsChecked']))

# ── 3. 同任务五栏引文区间不重叠 ──────────────────────────────────────────────
viol = []
for tk in cand['tasks']:
    spans = []
    for col in ['objective', 'obstacle', 'action', 'result', 'cost']:
        for o in (tk.get(col + 'Quotes') or []):
            spans.append((o['start'], o['end'], col))
    spans.sort()
    for i in range(len(spans) - 1):
        if spans[i + 1][0] < spans[i][1]:
            viol.append((tk['id'], spans[i], spans[i + 1]))
check('no cross-column span overlap in 5-tuples', not viol, str(viol[:2]))

# ── 4. null 栏必须带理由 ─────────────────────────────────────────────────────
nulls, unlabeled = 0, []
for tk in cand['tasks']:
    for col in ['objective', 'obstacle', 'action', 'result', 'cost']:
        if tk.get(col) is None:
            nulls += 1
            note = (tk.get(col + 'Note') or '').strip()
            qs = tk.get(col + 'Quotes') or []
            if not note or qs:
                unlabeled.append((tk['id'], col))
check('%d null fields all carry a reason' % nulls, not unlabeled, str(unlabeled))

# ── 5. 内容分区（用 loop.py 自己的校验器）────────────────────────────────────
import importlib.util
spec = importlib.util.spec_from_file_location('loopmod', 'loop/bin/loop.py')
loopmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loopmod)
task = json.load(open('loop/state/runs/task-read_dafeng_L3_0275.json'))
want = loopmod.required_sections(task['prompt'])
check('required sections present', not [k for k in want if k not in cand], ','.join(want))

# ── 6. coverage 声明 == 实际长度 ─────────────────────────────────────────────
mism = [(k, v, len(cand[k])) for k, v in cand['coverage'].items()
        if isinstance(cand.get(k), list) and v != len(cand[k])]
check('coverage counts match actual lengths', not mism, str(mism))

# ── 7. 幻觉检查：候选里的专名必须都能在原文命中 ──────────────────────────────
names = ['许七安', '蓉蓉', '金莲道长', '葛小菁', '闵银锣', '闵山', '魏渊', '地宗道首',
         '千面女飞贼', '女飞贼', '橘猫', '小母马', '吏员', '狱卒', '盗门', '神偷门',
         '道门', '地宗', '查水裱', '瞒天过海', '黑金长刀', '地书碎片']
ghost = [n for n in names if s.count(n) == 0]
check('no fabricated proper noun', not ghost, str(ghost))

# ── 8. counterExample/reverseCheck 引文逐字 + 偏移一致 ───────────────────────
bad2 = []
for item in verdict['counterExamples'] + verdict['reverseChecks']:
    q = item['quote']
    i = t.find(q, S, E)
    if i < 0 or t[i:i + len(q)] != q:
        bad2.append(('not-verbatim', q[:30]))
    if 'offset' in item and list(item['offset']) != [i, i + len(q)]:
        bad2.append(('offset-mismatch', q[:30], item['offset'], i))
check('verdict CE/RC quotes verbatim + offsets',
      not bad2, str(bad2[:3]))

# ── 9. 复核发现本身可复现（这是本复核的实质结论）────────────────────────────
facts = {
    'A 元神出窍 in range == 0': s.count('元神出窍') == 0,
    'B 原文用词为 元神出动': s.count('元神出动') == 1,
    'C 盗门 in range == 5 (候选称 2)': s.count('盗门') == 5,
    'D 交感规则句在原文': t.find('地书碎片和宿主在近距离内，能产生交感。', S, E) == 1164420,
    'E 交感 不在 C03.trigger': '交感' not in cand['causeEdges'][2]['trigger'],
    'F 交感 不在 C02': '交感' not in json.dumps(cand['causeEdges'][1], ensure_ascii=False),
    'G 交感 被 W08.explain 当机制用':
        '交感' in [w for w in cand['worldSettings'] if w['id'] == 'W08'][0]['explain'],
    'H T04.costNote 指向 C08，实为 C07':
        'C08' in cand['tasks'][3]['costNote'] and '宵禁' in cand['causeEdges'][6]['from'],
    'I 「告别了金莲道长」无任何边覆盖':
        not [e for e in cand['causeEdges'] if '告别' in json.dumps(e, ensure_ascii=False)],
    'J 错抓蓉蓉 未被候选记录': '错抓' not in json.dumps(cand, ensure_ascii=False),
    'K 早已知晓 未被候选记录': '早已知晓' not in json.dumps(cand, ensure_ascii=False),
    'L 一路小心 未被候选记录': '一路小心' not in json.dumps(cand, ensure_ascii=False),
    'M 闵山 未被候选记录': '闵山' not in json.dumps(cand, ensure_ascii=False),
    'N 佩刀 未被候选记录': '佩刀' not in json.dumps(cand, ensure_ascii=False),
    'O 人让车 未被候选记录': '人让车' not in json.dumps(cand, ensure_ascii=False),
}
for k, v in facts.items():
    check('finding ' + k, v)

# ── 10. 固定种子抽 5 条 quote 复算 find ─────────────────────────────────────
import random
random.seed(275)
smp = random.sample(refs, 5)
ok5 = all(t.find(o['quote']) == o['start'] for o in smp)
check('seeded sample of 5 quotes: find==start', ok5)

fails = [r for r in results if not r[1]]
print('\n%d checks, %d failed' % (len(results), len(fails)))
sys.exit(1 if fails else 0)
