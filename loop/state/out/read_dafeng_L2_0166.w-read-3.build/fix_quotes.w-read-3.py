# -*- coding: utf-8 -*-
"""第二处返工：把散文里用『』改写的原文引号恢复成原文的“”。

缺陷（可用原文逐字证伪）：原文 p68 是
   听到了“火炮”、“器械”等字眼
本候选在两处散文里把内层引号写成『』（knowledgeDiffs.K5.knows、notWorldSettings.NW4.item），
而**源文本里『』出现 0 次**（seg.count('『')==0）——即给原文安了它没有的标点。
这与 0162 被判 partial 的「交给三司」同形：结论可能仍成立，但引文不可 find。

修法：把『』还原为原文的“”，并复算 find 命中。替换前断言旧串唯一存在。
"""
import json, hashlib, re

CAND = 'loop/state/out/read_dafeng_L2_0166.candidate.json'
SRC  = 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
S, E = 594977, 599088
text = json.load(open(SRC))[0]['text']
seg  = text[S:E]
doc  = json.load(open(CAND))

assert seg.count('『') == 0 and seg.count('』') == 0, "原文竟含『』，前提不成立"

FIXES = [
 ("knowledgeDiffs/4/knows",
  "「听到了『火炮』、『器械』等字眼，于是被残忍杀害，抛尸井中」",
  "「听到了“火炮”、“器械”等字眼，于是被残忍杀害，抛尸井中」",
  "seg.find 命中 p68"),
 ("notWorldSettings/3/item",
  "「『火炮』、『器械』等字眼」（p68，女鬼偷听到的密谈内容）",
  "「“火炮”、“器械”等字眼」（p68，女鬼偷听到的密谈内容）",
  "seg.find 命中 p68"),
]

def get(d, path):
    cur = d
    for part in path.split('/'):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur

def setv(d, path, val):
    parts = path.split('/'); cur = d
    for part in parts[:-1]:
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    last = parts[-1]
    if isinstance(cur, list): cur[int(last)] = val
    else: cur[last] = val

for path, old, new, why in FIXES:
    cur = get(doc, path)
    if cur.count(old) != 1:
        raise SystemExit("FAIL 旧串不唯一：%s x%d" % (path, cur.count(old)))
    setv(doc, path, cur.replace(old, new))
    print("FIXED %-32s (%s)" % (path, why))

# 复算：修后不得再有『』，且两处内层引文必须 find 到
def walk(o):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o: return
        for v in o.values(): yield from walk(v)
    elif isinstance(o, list):
        for v in o: yield from walk(v)
    elif isinstance(o, str): yield o
n_corner = sum(s.count('『') + s.count('』') for s in walk(doc))
assert n_corner == 0, "仍有『』残留 %d" % n_corner
for t in ('听到了“火炮”、“器械”等字眼，于是被残忍杀害，抛尸井中',
          '“火炮”、“器械”等字眼'):
    assert seg.find(t) >= 0, t
print("复算：『』残留 0；两处内层引文 find 命中")

def walkq(o):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o: yield o
        for v in o.values(): yield from walkq(v)
    elif isinstance(o, list):
        for v in o: yield from walkq(v)
n = 0
for q in walkq(doc):
    n += 1
    assert text[q['start']:q['end']] == q['quote'], q['quote'][:40]
print("引文层复核：%d/%d 仍逐字成立" % (n, n))

doc['reworkOf'] = "loop/state/out/read_dafeng_L2_0166.w-read-3.build/prior_draft_unsubmitted.deb6065b.json"
doc['reworkReason'] = doc['reworkReason'] + (
 " 另补一处同类缺陷（第二轮自查由 scan_claims 的 B/D 规则抓出）："
 "knowledgeDiffs.K5 与 notWorldSettings.NW4 把原文的内层引号“”写成『』，"
 "而源文本『』出现 0 次 —— 与 0162 的「交给三司」同形（给原文安了它没有的字符）。已还原为原文引号。"
)
open(CAND, 'w', encoding='utf-8').write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
print("WROTE", CAND)
print("sha256", hashlib.sha256(open(CAND,'rb').read()).hexdigest())
