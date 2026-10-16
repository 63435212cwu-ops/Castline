# -*- coding: utf-8 -*-
"""只读检索工具：给一段候选引文，打印它在 docs[0].text 里的**逐字**位置与上下文。

用途：作者写候选前，先用它确认引文确实逐字存在于原文（不靠记忆抄写）。
用法：
    python3 find.py '孔明曰：“司马懿善能用兵'        # 子串检索
    python3 find.py --re '第[一二三四]位'             # 正则检索
    python3 find.py --range 508347 508650             # 打印某区间全文
"""
import json
import re
import sys

DOCS = '/Users/carmen/Desktop/星系/data/cache/fe42d01f3826fe8096f86614.docs.json'
START, END = 504841, 510210
TEXT = json.load(open(DOCS, encoding='utf-8'))[0]['text']


def show(i, n):
    print('  @%d  %r' % (i, TEXT[i:i + n]))
    print('       ...%r' % (TEXT[max(0, i - 30):i + n + 30],))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == '--range':
        a, b = int(argv[1]), int(argv[2])
        print(TEXT[a:b])
        return 0
    if argv[0] == '--re':
        pat = re.compile(argv[1])
        hits = [m.start() for m in pat.finditer(TEXT)]
        print('正则 %r 命中 %d 次' % (argv[1], len(hits)))
        for i in hits:
            mark = 'IN-RANGE' if START <= i < END else 'outside'
            print('  @%d [%s] %r' % (i, mark, TEXT[i:i + 40]))
        return 0
    needle = argv[0]
    occ = []
    i = TEXT.find(needle)
    while i >= 0:
        occ.append(i)
        i = TEXT.find(needle, i + 1)
    print('引文 %r 全篇命中 %d 次（长度 %d）' % (needle, len(occ), len(needle)))
    for i in occ:
        inr = START <= i and i + len(needle) <= END
        print('  @%d inRange=%s' % (i, inr))
        show(i, len(needle))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
