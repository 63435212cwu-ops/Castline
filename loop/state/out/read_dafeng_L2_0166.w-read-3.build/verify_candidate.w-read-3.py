# -*- coding: utf-8 -*-
"""独立复算：不复用构建期偏移，全部从 docs[0].text 现取现验。

与 scan_claims 的分工：scan_claims 查**散文计数**（0162 partial 的根因），
本脚本查**引文层 + 结构层 + 覆盖层**。两者都过才算候选可用。
"""
import json, hashlib, re, sys
from collections import defaultdict

SRC  = 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
CAND = 'loop/state/out/read_dafeng_L2_0166.candidate.json'
GRAPH= 'data/cache/1063b17ca65ec1b76f30e460.json'
TASK = 'loop/state/runs/task-read_dafeng_L2_0166.json'
S, E = 594977, 599088
HASH = 'fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839'

problems = []
doc = json.load(open(SRC))
text = doc[0]['text']
task = json.load(open(TASK))
cand = json.load(open(CAND))

# ── 0. 源哈希 ───────────────────────────────────────────────────────────────
h = hashlib.sha256(open(SRC,'rb').read()).hexdigest()
if h != HASH: problems.append("docs.json sha256 不符：%s" % h)
if h != task['sourceHash']: problems.append("与 task.sourceHash 不符")

# ── 1. 边界自检式 ───────────────────────────────────────────────────────────
seg = text[S:E]
head = task['unitHead']
if not seg.startswith(head): problems.append("切片不以单元标题开头：%r" % seg[:30])
if (S, E) != tuple(task['sourceRange']): problems.append("区间与任务不符")
if len(seg) != E - S: problems.append("切片长度不符")

# ── 2. 段索引（独立枚举，用于段号回验） ─────────────────────────────────────
paras = []; cur = S
for ln in seg.split('\n'):
    if ln.strip(): paras.append((len(paras)+1, cur, cur+len(ln), ln.strip()))
    cur += len(ln) + 1
def para_of(off):
    for n, a, b, t in paras:
        if a <= off < b: return n
    return None

def walk(o, path=""):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o: yield path, o
        for k, v in o.items(): yield from walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from walk(v, path + "/%d" % i)

# ── 3. 引文层全量复算 ───────────────────────────────────────────────────────
nref = 0; uniq = set()
for path, q in walk(cand):
    nref += 1
    s, e, qt = q.get('start'), q.get('end'), q.get('quote')
    if not isinstance(s, int) or not isinstance(e, int):
        problems.append("%s 偏移非整数" % path); continue
    if text[s:e] != qt:
        problems.append("%s 逐字不符 s=%d e=%d want=%r got=%r" % (path, s, e, qt, text[s:e]))
    if e - s != len(qt):
        problems.append("%s 长度不符" % path)
    if q.get('sourceHash') != HASH:
        problems.append("%s sourceHash 不符" % path)
    if not (S <= s and e <= E):
        problems.append("%s 越出区间" % path)
    uniq.add(qt)
    if 'wholeTextOccurrences' in q and text.count(qt) != q['wholeTextOccurrences']:
        problems.append("%s 全书出现次数不符" % path)
    if text.find(qt) != q.get('firstOccurrenceAt'):
        problems.append("%s firstOccurrenceAt 不符" % path)
    if q.get('startIsFirstOccurrence') != (text.find(qt) == s):
        problems.append("%s startIsFirstOccurrence 不符" % path)
    if q.get('para') is not None and para_of(s) != q['para']:
        problems.append("%s 段号不符 declared=%s actual=%s" % (path, q['para'], para_of(s)))

# ── 4. 结构层：分区齐全 + 空栏带理由 + 跨栏不共用 ──────────────────────────
for sec in ('tasks','causeEdges','states','foreshadows','worldSettings','themeReadings'):
    if sec not in cand: problems.append("缺分区 %s" % sec)

for t in cand.get('tasks', []):
    seen = defaultdict(list)
    for slot in ('objective','obstacle','action','result','cost'):
        v = t.get(slot)
        if v is None:
            note = t.get(slot + 'Note') or t.get(slot + 'note')
            if not note: problems.append("%s.%s 为 null 但无同名 Note" % (t.get('id'), slot))
            continue
        if not v.get('quotes'): problems.append("%s.%s 无引文" % (t.get('id'), slot))
        for q in v.get('quotes', []): seen[(q['start'], q['end'])].append(slot)
    for k, slots in seen.items():
        if len(slots) > 1:
            problems.append("%s 跨栏共用同一引文跨度 %s -> %s" % (t.get('id'), k, slots))
    # 五栏跨度两两不重叠
    spans = {}
    for slot in ('objective','obstacle','action','result','cost'):
        v = t.get(slot)
        if v: spans[slot] = [(q['start'], q['end']) for q in v.get('quotes', [])]
    sl = list(spans)
    for i in range(len(sl)):
        for j in range(i+1, len(sl)):
            for a in spans[sl[i]]:
                for b in spans[sl[j]]:
                    if a[0] < b[1] and b[0] < a[1]:
                        problems.append("%s 栏位跨度重叠 %s%s %s%s" % (t.get('id'), sl[i], a, sl[j], b))

# ── 5. 世界设定三态 / 主题三件 ──────────────────────────────────────────────
for w in cand.get('worldSettings', []):
    k = w.get('kind')
    if k == 'place':
        if w.get('placeState') not in ('arrived','mentioned'):
            problems.append("%s place 缺合法 placeState" % w.get('id'))
    elif k == 'item':
        st = w.get('itemStates')
        if not isinstance(st, list) or not st or any(x not in ('hold','transfer','use','lose') for x in st):
            problems.append("%s item itemStates 非法：%r" % (w.get('id'), st))
    elif k == 'rule':
        if w.get('institution') not in ('declared','executed','misunderstood'):
            problems.append("%s rule 缺合法 institution" % w.get('id'))
    else:
        problems.append("%s kind 非法：%r" % (w.get('id'), k))
    if not w.get('explain'): problems.append("%s 缺 explain" % w.get('id'))

for th in cand.get('themeReadings', []):
    for f in ('perspective','support','counter'):
        if not th.get(f): problems.append("%s 主题读法缺 %s" % (th.get('id'), f))

for f in cand.get('foreshadows', []):
    if f.get('status') not in ('resolved','unresolved'):
        problems.append("%s 伏笔缺 status" % f.get('id'))
    if f.get('status') == 'unresolved' and not (f.get('payoffNote') or f.get('note')):
        problems.append("%s unresolved 无 payoffNote" % f.get('id'))

# ── 6. coverage 声明可复现 ──────────────────────────────────────────────────
spans = [(q['start'], q['end']) for _, q in walk(cand)]
touched = {n for n, a, b, t in paras if any(s < b and a < e for s, e in spans)}
cov = cand.get('coverageDeclaration', {})
if cov.get('nonEmptyParagraphs') != len(paras):
    problems.append("coverage 段数不符：%s vs %d" % (cov.get('nonEmptyParagraphs'), len(paras)))
declared_unc = set(cov.get('uncoveredItems') or [])
actual_unc = set(range(1, len(paras)+1)) - touched
if declared_unc != actual_unc:
    problems.append("coverage 未覆盖集不符：declared=%s actual=%s" % (sorted(declared_unc), sorted(actual_unc)))

# ── 7. 图缓存只作对照，不作证据 ────────────────────────────────────────────
try:
    gh = hashlib.sha256(open(GRAPH,'rb').read()).hexdigest()
except Exception as exc:
    gh = None; problems.append("图谱缓存不可读：%r" % (exc,))

report = {
 "verdict": "pass" if not problems else "fail",
 "quoteRefs": nref,
 "uniqueQuoteStrings": len(uniq),
 "paragraphs": len(paras),
 "covered": len(touched),
 "uncovered": sorted(actual_unc),
 "sourceHash": h,
 "graphCacheSha256": gh,
 "problems": problems,
}
print(json.dumps(report, ensure_ascii=False, indent=1))
open('loop/state/out/read_dafeng_L2_0166.w-read-3.build/verify_report.w-read-3.json','w',encoding='utf-8').write(
    json.dumps(report, ensure_ascii=False, indent=1) + "\n")
sys.exit(1 if problems else 0)
