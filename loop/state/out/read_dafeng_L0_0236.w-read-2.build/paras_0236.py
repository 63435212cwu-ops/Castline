# -*- coding: utf-8 -*-
"""把切片按段/句切开，便于用「段号+句号」而不是手抄字符来指定引文。"""

import json
import re

DOCS = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
RANGE = (934756, 943450)

_t = json.load(open(DOCS, encoding="utf-8"))[0]["text"]

_TERM = re.compile(r"(?:[。！？]|…+|\.{2,})+[”\"』」]?")


def _split_sentences(p):
    out = []
    last = 0
    for m in _TERM.finditer(p):
        s = p[last:m.end()]
        if s.strip():
            out.append((last, m.end(), s))
        last = m.end()
    if last < len(p):
        s = p[last:]
        if s.strip():
            out.append((last, len(p), s))
    return out


PARAS = {}          # label -> (start, end, stripped_text, strip_offset)
SENTS = {}          # label -> [(a,b,text)] offsets relative to stripped text
_n = 0
for m in re.finditer(r"[^\n]+", _t[RANGE[0]:RANGE[1]]):
    raw = m.group(0)
    if not raw.strip():
        continue
    _n += 1
    lab = "P%03d" % _n
    gs = RANGE[0] + m.start()
    lead = len(raw) - len(raw.lstrip())
    body = raw.strip()
    PARAS[lab] = (gs + lead, gs + lead + len(body), body)
    SENTS[lab] = _split_sentences(body)


def P(label):
    return PARAS[label][2]


def S(label, i):
    return SENTS[label][i][2]


def R(label, i, j):
    a = SENTS[label][i][0]
    b = SENTS[label][j][1]
    return PARAS[label][2][a:b]


if __name__ == "__main__":
    import sys
    for lab in sys.argv[1:]:
        print("=" * 8, lab, PARAS[lab][2][:40])
        for i, (a, b, s) in enumerate(SENTS[lab]):
            print("  [%d] %r" % (i, s))
