# -*- coding: utf-8 -*-
"""Shared helpers: load source, resolve quotes to whole-text codepoint offsets."""
import json, hashlib, os

ROOT = '/Users/carmen/Desktop/星系'
SRC_REL = 'data/cache/fe42d01f3826fe8096f86614.docs.json'
S, E = 484338, 489034
FILESHA = hashlib.sha256(open(os.path.join(ROOT, SRC_REL), 'rb').read()).hexdigest()
text = json.load(open(os.path.join(ROOT, SRC_REL)))[0]['text']
SEG = text[S:E]

def q(s, voice='narration'):
    """Resolve verbatim substring s to an in-range quote ref. Fails loudly."""
    occ = []
    i = text.find(s)
    while i >= 0:
        occ.append(i)
        i = text.find(s, i + 1)
    if not occ:
        raise AssertionError('QUOTE NOT IN TEXT: %r' % s)
    inr = [i for i in occ if S <= i and i + len(s) <= E]
    if not inr:
        raise AssertionError('QUOTE NOT IN RANGE: %r (occ=%s)' % (s, occ))
    start = inr[0]
    # ordinal among ALL occurrences (1-based)
    nth = occ.index(start) + 1
    return {
        'quote': s, 'start': start, 'end': start + len(s),
        'sourceHash': FILESHA,
        'globalOccurrences': len(occ), 'nthOccurrence': nth,
        'inRange': True, 'inRangeOccurrences': len(inr),
        'voiceSurface': voice,
    }

def F(txt, basis, voice, *quotes):
    return {'text': txt, 'basis': basis, 'voice': voice, 'quotes': list(quotes)}
