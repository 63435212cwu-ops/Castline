#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性修复器：把散文里的「…」收敛成机器可断言的约定。

背景：0178 的独立复核 CE1 抓到的缺陷是——`worldSettings[11].explain` 里把原文的
「大呼小叫」写成了「大呼大叫」（全书 count == 0），而它在**散文字段**里、构建期的
逐字断言管不到。本单元把约定改成：

    「…」 只允许是 docs[0].text 的**逐字子串**；
    『…』 一律是我自己的标签／读法。

本脚本扫描全部字符串字段（跳过 quotes[]/quote —— 那些由 build_candidate.py 逐条断言），
对每个 「…」 依次尝试三种修复：

  R1 原样即逐字                     → 保留「…」
  R2 把内层 『』 还原成 “” 后逐字    → 采用还原后的写法（嵌套引号用「外『内』」）
  R3 其余                          → 改成『…』并在报告里记下原串与替换串

用法：python3 fixer.py            # 只报告，不写盘
      python3 fixer.py --write    # 写回被修改的模块文件
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
BUILD = ROOT / 'loop/state/out/read_dafeng_L2_0182.w-dafeng-0.build'
DOCS = ROOT / 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
TASKF = ROOT / 'loop/state/runs/task-read_dafeng_L2_0182.json'

import json

TASK = json.loads(TASKF.read_text(encoding='utf-8'))
TEXT = json.loads(DOCS.read_bytes().decode('utf-8'))[0]['text']

WRITE = '--write' in sys.argv

# 只扫这三个内容模块的**源码文本**，逐行处理字符串字面量里的「…」。
MODULES = ['content_tasks.py', 'content_edges.py', 'content_more.py']
BRACKET = re.compile(r'「([^「」]*)」')

report = {'R2': [], 'R3': []}
counts = {'R1': 0, 'R2': 0, 'R3': 0}


def repair(inner):
    """返回 (kind, replacement_inner, outer_open, outer_close)。"""
    if TEXT.find(inner) >= 0:
        return 'R1', inner, '「', '」'
    restored = inner.replace('『', '“').replace('』', '”')
    if restored != inner and TEXT.find(restored) >= 0:
        return 'R2', restored, '「', '」'
    return 'R3', inner, '『', '』'


for name in MODULES:
    p = BUILD / name
    src = p.read_text(encoding='utf-8')
    out_lines = []
    for lineno, line in enumerate(src.split('\n'), 1):
        def sub(m):
            inner = m.group(1)
            kind, new_inner, oo, oc = repair(inner)
            counts[kind] += 1
            if kind == 'R2':
                report['R2'].append({'file': name, 'line': lineno,
                                     'before': m.group(0), 'after': oo + new_inner + oc})
            elif kind == 'R3':
                report['R3'].append({'file': name, 'line': lineno,
                                     'before': m.group(0), 'after': oo + new_inner + oc})
            return oo + new_inner + oc
        out_lines.append(BRACKET.sub(sub, line))
    new_src = '\n'.join(out_lines)
    if WRITE and new_src != src:
        p.write_text(new_src, encoding='utf-8')
        print('已写回 %s' % p)

print('修复统计：R1 保留 %d；R2 还原嵌套引号 %d；R3 改标签 %d'
      % (counts['R1'], counts['R2'], counts['R3']))
print()
print('=== R2（还原成原文的嵌套引号）%d 条' % len(report['R2']))
for x in report['R2']:
    print('  %s:%d  %s  ->  %s' % (x['file'], x['line'], x['before'], x['after']))
print()
print('=== R3（改成我的标签『』）%d 条' % len(report['R3']))
for x in report['R3']:
    print('  %s:%d  %s  ->  %s' % (x['file'], x['line'], x['before'], x['after']))

out = BUILD / 'fixer_report.json'
out.write_text(json.dumps({
    'note': '把散文里的「…」收敛为机器可断言约定的一次性修复记录：R1 保留（逐字）、'
            'R2 还原内层引号（『』→“”）、R3 改为我的标签『』。',
    'counts': counts, 'R2': report['R2'], 'R3': report['R3'],
}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print()
print('报告：%s' % out)
