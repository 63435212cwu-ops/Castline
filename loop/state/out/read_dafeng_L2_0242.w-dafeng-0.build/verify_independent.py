#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核脚本：**不 import 构造器、不 import 内容层**。

从磁盘重新读候选、重新打开源文件、重算全部哈希、独立重切段落（用**行扫描**而不是
构造器的 `split('\\n\\n')`），逐条重新 find 每一条引文。

还包含一个**变异测试**（C12）：故意改坏一条引文的末字符、把另一条的 start+1，
两次都必须让引文判据报红 —— 否则说明判据本身是假的（永远绿的检查等于没有检查）。

用法：python3 -B -s verify_independent.py
"""
import hashlib
import json
import re
import sys

ROOT = '/Users/carmen/Desktop/星系'
DOCS = ROOT + '/data/cache/1063b17ca65ec1b76f30e460.docs.json'
CAND = ROOT + '/loop/state/out/read_dafeng_L2_0242.candidate.json'
TASKF = ROOT + '/loop/state/runs/task-read_dafeng_L2_0242.json'

R = []


def chk(cid, ok, detail):
    R.append((cid, bool(ok), detail))
    return ok


# ── 读盘 ────────────────────────────────────────────────────────────────────
task = json.load(open(TASKF, encoding='utf-8'))
cand = json.load(open(CAND, encoding='utf-8'))
raw = open(DOCS, 'rb').read()
text = json.loads(raw)[0]['text']
START, END = task['sourceRange']

# ── C01 源哈希三处一致 ──────────────────────────────────────────────────────
file_sha = hashlib.sha256(raw).hexdigest()
chk('C01', file_sha == task['sourceHash'] == cand['sourceHash'],
    'docs.json sha256=%s / task=%s / candidate=%s' % (file_sha[:16], task['sourceHash'][:16], cand['sourceHash'][:16]))

# ── C02 偏移口径：切片以标题开头 ────────────────────────────────────────────
sl = text[START:END]
chk('C02', sl.startswith(task['unitHead']) and len(sl) == END - START == cand['sourceSliceCodepoints'],
    'docs[0].text[%d:%d) 长度=%d 开头=%r' % (START, END, len(sl), sl[:14]))

# ── C03 切片哈希与 docs 文本哈希自算 ────────────────────────────────────────
chk('C03', cand['sliceSha256'] == hashlib.sha256(sl.encode('utf-8')).hexdigest()
    and cand['docsTextSha256'] == hashlib.sha256(text.encode('utf-8')).hexdigest(),
    'sliceSha256/docsTextSha256 自算一致')

# ── C04 独立重切段落（行扫描法，与构造器的 split('\n\n') 不同实现）──────────
paras = []
for m in re.finditer(r'[^\n]+', sl):
    line = m.group(0)
    if line.strip():
        paras.append(('P%03d' % (len(paras) + 1), START + m.start(), START + m.end()))
pby = {lab: (s, e) for lab, s, e in paras}
chk('C04', len(paras) == cand['coverageNote']['totalParagraphs'],
    '独立行扫描得 %d 段；候选声明 %d 段' % (len(paras), cand['coverageNote']['totalParagraphs']))

# ── C05 逐条引文重算 ────────────────────────────────────────────────────────
refs = []


def walk(n):
    if isinstance(n, dict):
        if 'quote' in n and 'start' in n and 'end' in n and 'sourceHash' in n:
            refs.append(n)
            return
        for v in n.values():
            walk(v)
    elif isinstance(n, list):
        for v in n:
            walk(v)


for k, v in cand.items():
    if k in ('tasks', 'causeEdges', 'notCauseEdges', 'states', 'knowledgeGaps', 'foreshadows',
             'singleAppearanceNotForeshadow', 'worldSettings', 'themeReadings', 'unknowns',
             'notCategorizedFacts'):
        walk(v)

bad_slice, bad_find, bad_range, bad_hash, bad_count, bad_para = [], [], [], [], [], []
for r in refs:
    qs, s, e = r['quote'], r['start'], r['end']
    if text[s:e] != qs:
        bad_slice.append((qs[:30], s, e))
    occ = [m.start() for m in re.finditer(re.escape(qs), text)]
    if not occ:
        bad_find.append(qs[:30])
    if not (START <= s and e <= END):
        bad_range.append((qs[:30], s, e))
    if r['sourceHash'] != file_sha:
        bad_hash.append(qs[:30])
    inr = [i for i in occ if START <= i and i + len(qs) <= END]
    if r.get('wholeTextOccurrences') != len(occ) or r.get('occurrencesInRange') != len(inr):
        bad_count.append((qs[:24], r.get('wholeTextOccurrences'), len(occ),
                          r.get('occurrencesInRange'), len(inr)))
    lab = r.get('paraLabel')
    if lab and lab in pby:
        ps, pe = pby[lab]
        if not (ps <= s and e <= pe):
            bad_para.append((qs[:24], lab, s, e, ps, pe))
    elif lab:
        bad_para.append((qs[:24], lab, '段号不存在', s, e))

chk('C05', not bad_slice, '%d 条引文 text[start:end]==quote（不符 %d 条）' % (len(refs), len(bad_slice)))
chk('C06', not bad_find, '全部引文在全文 find 命中（未命中 %d）' % len(bad_find))
chk('C07', not bad_range, '全部引文落在 [%d,%d) 内（越界 %d）' % (START, END, len(bad_range)))
chk('C08', not bad_hash, '全部 sourceHash 等于源文件 sha256（不符 %d）' % len(bad_hash))
chk('C09', not bad_count, 'wholeTextOccurrences/occurrencesInRange 逐条重算一致（不符 %d）%r'
    % (len(bad_count), bad_count[:3]))
chk('C10', not bad_para, 'paraLabel 与独立重切段落一致（不符 %d）%r' % (len(bad_para), bad_para[:3]))

# ── C11 任务五栏：不得共用同一句，且区间不得重叠 ────────────────────────────
five = ('objective', 'obstacle', 'action', 'result', 'cost')
share, overlap, nullnote = [], [], []
for t in cand['tasks']:
    seen, spans = {}, []
    for c in five:
        v = t.get(c)
        if v is None:
            if not t.get(c + 'Note'):
                nullnote.append((t['id'], c))
            continue
        for r in v.get('quotes') or []:
            if r['quote'] in seen:
                share.append((t['id'], seen[r['quote']], c, r['quote'][:24]))
            seen[r['quote']] = c
            for a, b, o in spans:
                if r['start'] < b and a < r['end']:
                    overlap.append((t['id'], o, c))
            spans.append((r['start'], r['end'], c))

ncol = len(cand['tasks']) * len(five)
chk('C11a', not share, '同一任务五栏未共用同一句（%d 栏位组合，违规 %d）%r' % (ncol, len(share), share[:3]))
chk('C11b', not overlap, '同一任务五栏的引文区间互不重叠（违规 %d）%r' % (len(overlap), overlap[:3]))
chk('C11c', not nullnote, 'null 栏位都带同名 Note（缺 %d）%r' % (len(nullnote), nullnote))

# ── C12 变异测试：判据必须能报红 ────────────────────────────────────────────
r0 = refs[0]
mut_slice = text[r0['start']:r0['end'] - 1] + ('X' if r0['quote'][-1] != 'X' else 'Y')
r1 = refs[1]
mut_shift_ok = text[r1['start'] + 1:r1['end'] + 1] == r1['quote']
chk('C12', mut_slice != r0['quote'] and not mut_shift_ok,
    '变异测试：改坏末字符后 text[s:e]!=quote 成立=%s；start+1 后仍逐字相等=%s（应为 False）'
    % (mut_slice != r0['quote'], mut_shift_ok))

# ── C13 分区与字段结构 ──────────────────────────────────────────────────────
need = ['tasks', 'causeEdges', 'states', 'foreshadows', 'worldSettings', 'themeReadings']
miss = [k for k in need if k not in cand]
chk('C13', not miss, '提示词要求的 6 个分区全部存在（缺 %r）' % miss)

BASIS = {'explicit', 'inferred', 'derived', 'unverified'}
bad_basis = []
for k in ('tasks', 'causeEdges', 'states', 'knowledgeGaps', 'foreshadows', 'worldSettings',
          'themeReadings', 'unknowns', 'singleAppearanceNotForeshadow'):
    for item in (cand.get(k) or []):
        for kk, vv in item.items():
            if isinstance(vv, dict) and 'basis' in vv and vv['basis'] not in BASIS:
                bad_basis.append((k, item.get('id'), kk, vv['basis']))
            if kk == 'basis' and vv not in BASIS:
                bad_basis.append((k, item.get('id'), kk, vv))
chk('C14', not bad_basis, '所有 basis 取值合法（非法 %d）%r' % (len(bad_basis), bad_basis[:3]))

# ── C15 worldSettings 三态字段写进字段 ──────────────────────────────────────
wp, wi, wr = [], [], []
for w in cand['worldSettings']:
    if w['kind'] == 'place' and w.get('placeState') not in ('arrived', 'mentioned'):
        wp.append(w.get('id'))
    if w['kind'] == 'item':
        st = w.get('itemStates')
        if not isinstance(st, list) or not st or any(x not in ('hold', 'transfer', 'use', 'lose') for x in st):
            wi.append(w.get('id'))
    if w['kind'] == 'rule' and w.get('institution') not in ('declared', 'executed', 'misunderstood'):
        wr.append(w.get('id'))
chk('C15', not (wp or wi or wr), 'worldSettings 三态字段齐备（place %r / item %r / rule %r）' % (wp, wi, wr))

# ── C16 themeReadings 三件齐备 ──────────────────────────────────────────────
bad_th = [t.get('id') for t in cand['themeReadings']
          if not (t.get('perspective') and t.get('support') and t.get('counter'))]
chk('C16', not bad_th and len(cand['themeReadings']) <= 2,
    'themeReadings 各带 perspective/support/counter 且 ≤2 条（问题 %r，条数 %d）'
    % (bad_th, len(cand['themeReadings'])))

# ── C17 不得声称 semanticReview 完成 ────────────────────────────────────────
sr = str(cand.get('semanticReview', ''))
chk('C17', sr in ('not-performed', 'none', '') or 'not' in sr.lower(),
    'semanticReview=%r（不得声称已完成）' % sr)

# ── C18 引文统计自洽 ────────────────────────────────────────────────────────
uniq = {r['quote'] for r in refs}
chk('C18', cand['quoteCount'] == len(refs) and cand['quotesRegistered'] == len(uniq)
    and cand['quotesInRangeRegistered'] == len(refs),
    'quoteCount=%d(实%d) quotesRegistered=%d(实%d) inRange=%d(实%d)'
    % (cand['quoteCount'], len(refs), cand['quotesRegistered'], len(uniq),
       cand['quotesInRangeRegistered'], len(refs)))

# ── C19 覆盖段号确实存在 ────────────────────────────────────────────────────
cov = set()
for r in refs:
    if r.get('paraLabel'):
        cov.add(r['paraLabel'])
unc = cand['coverageNote']['unquotedParagraphs']
allp = set(pby)
chk('C19', set(unc) | cov == allp and not (set(unc) & cov),
    '覆盖段 %d + 未引用段 %d == 总段 %d，且两集合不相交'
    % (len(cov), len(unc), len(allp)))

# ── 输出 ────────────────────────────────────────────────────────────────────
npass = sum(1 for _c, ok, _d in R if ok)
lines = ['独立复核报告 read:dafeng:L2:0242',
         '候选：loop/state/out/read_dafeng_L2_0242.candidate.json',
         '候选 sha256：%s' % hashlib.sha256(open(CAND, 'rb').read()).hexdigest(),
         '源：data/cache/1063b17ca65ec1b76f30e460.docs.json sha256=%s' % file_sha,
         '引文条目 %d（去重 %d）· 段 %d · 检查 %d 项：PASS %d / FAIL %d'
         % (len(refs), len(uniq), len(paras), len(R), npass, len(R) - npass), '']
for cid, ok, d in R:
    lines.append('%s %-6s %s' % ('PASS' if ok else 'FAIL', cid, d))
lines.append('')
lines.append('未引用段（%d）：%s' % (len(unc), ' '.join(sorted(unc))))
out = '\n'.join(lines) + '\n'
open(ROOT + '/loop/state/out/read_dafeng_L2_0242.w-dafeng-0.build/verify_independent_report.txt',
     'w', encoding='utf-8').write(out)
print(out)
sys.exit(0 if npass == len(R) else 1)
