#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：把 docs[0].text[S:E) 切成 段 / 句单元 / 分句单元，打印编号与文本。

用途（AGENTS.md：一次性探针外置；本文件是候选构建链条的一环，随候选一起留证）：
  · 让 reverseValidation 与 coverageDeclaration 有**可复算**的单元表，而不是我口头数的；
  · 句级/分句级覆盖是上一单元（0178）独立复核 RC5 的明确建议：
    段级覆盖会系统性地放过「同段内有一句被引、另一句从未被引」。

不写任何结论，只打印结构。结论在 build_candidate.py 里由同一套切分算出。
"""
import json
import re
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
DOCS = ROOT / 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
TASKF = ROOT / 'loop/state/runs/task-read_dafeng_L2_0182.json'

TASK = json.loads(TASKF.read_text(encoding='utf-8'))
S, E = TASK['sourceRange']
TEXT = json.loads(DOCS.read_bytes().decode('utf-8'))[0]['text']
SEG = TEXT[S:E]

PARAS = []
for m in re.finditer(r'[^\n]+', SEG):
    body = m.group(0).strip()
    if not body:
        continue
    lead = len(m.group(0)) - len(m.group(0).lstrip())
    st = S + m.start() + lead
    PARAS.append((st, st + len(body), body))

SENT_RE = re.compile(r'[^。！？]*[。！？]|[^。！？]+$')
CLAUSE_RE = re.compile(r'[^，。！？；：]*[，。！？；：]|[^，。！？；：]+$')


def units(regex):
    out = []
    for pno, (pst, pen, ptext) in enumerate(PARAS, 1):
        for m in regex.finditer(ptext):
            t = m.group(0)
            if not t:
                continue
            st = pst + m.start()
            out.append((pno, st, st + len(t), t))
    return out


SENTS = units(SENT_RE)
CLAUSES = units(CLAUSE_RE)

print('=== 段：%d 个非空段；句单元：%d；分句单元：%d' % (len(PARAS), len(SENTS), len(CLAUSES)))
print()
print('=== 句单元表（编号 | 段号 | 绝对区间 | 文本）')
for i, (pno, a, b, t) in enumerate(SENTS, 1):
    print('S%03d p%03d [%d,%d) %s' % (i, pno, a, b, t))
print()
print('=== 分句单元表')
for i, (pno, a, b, t) in enumerate(CLAUSES, 1):
    print('C%03d p%03d [%d,%d) %s' % (i, pno, a, b, t))
