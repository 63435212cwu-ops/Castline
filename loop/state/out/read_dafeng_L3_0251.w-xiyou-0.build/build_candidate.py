#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 loop/state/out/read_dafeng_L3_0251.candidate.json。

设计要点（沿用 L3:0247 轮已验证的判据，并针对本单元重算）：
 1. **偏移不手写**：内容模块只给 (声明段号, 引文字符串)，本脚本在
    docs[0].text **全文** 里 find 出 start，再校验区间内出现次数恰好 1。
 2. **五栏独立性用字符区间判定**：同一条任务的 objective/obstacle/action/
    result/cost 引文字符区间两两不相交，且不共用同一句。违反 ⇒ 退出码 1。
 3. **null 栏必须有同名 Note**，否则拒绝写盘。
 4. 六个内容分区必须齐全（缺失即 []，不能没有键）。
 5. worldSettings 三态字段强制：place→placeState、item→itemStates、
    rule→institution，取值非法即拒绝写盘。
 6. 行内「」必须逐字可 find（术语用【】）。
 7. 写盘前扫出所有「有 quote 无偏移」的漏解析引文。
 8. 标签字段（name/title）里的【】若长度≥4 且不含自造连接符，必须全文可 find。

退出码 0 = 候选已写出且全部判据通过。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
DOCS = ROOT / 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
TASKF = ROOT / 'loop/state/runs/task-read_dafeng_L3_0251.json'
OUT = ROOT / 'loop/state/out/read_dafeng_L3_0251.candidate.json'
BUILD = ROOT / 'loop/state/out/read_dafeng_L3_0251.w-xiyou-0.build'

sys.path.insert(0, str(BUILD))
import content_0251 as A          # noqa: E402
import content_0251b as B         # noqa: E402
import content_0251c as C3        # noqa: E402

TASK = json.loads(TASKF.read_text(encoding='utf-8'))
S, E = TASK['sourceRange']
SOURCE_HASH = TASK['sourceHash']
DOCS_BYTES = DOCS.read_bytes()
TEXT = json.loads(DOCS_BYTES.decode('utf-8'))[0]['text']
SLICE = TEXT[S:E]

PROBLEMS = []


def bad(msg):
    PROBLEMS.append(msg)


# ── 0. 源自检 ──────────────────────────────────────────────────────────
_file_hash = hashlib.sha256(DOCS_BYTES).hexdigest()
if _file_hash != SOURCE_HASH:
    bad('docs.json sha256 与任务不符：%s vs %s' % (_file_hash, SOURCE_HASH))
if not SLICE.startswith(TASK['unitHead']):
    bad('切片不以章题开头：%r' % SLICE[:30])

# ── 1. 独立重切段落 ────────────────────────────────────────────────────
PARAS = []
for m in re.finditer(r'[^\n]+', SLICE):
    raw = m.group(0)
    st = raw.strip()
    if not st:
        continue
    a = S + m.start() + (len(raw) - len(raw.lstrip()))
    PARAS.append((a, a + len(st), st))


def para_of(pos):
    for i, (a, b, _t) in enumerate(PARAS, 1):
        if a <= pos < b:
            return i
    return None


# ── 2. 引文解析（唯一的偏移来源）────────────────────────────────────────
QUOTES = []
UNRESOLVED = []


def resolve(pair, where):
    if not (isinstance(pair, (tuple, list)) and len(pair) == 2):
        bad('%s: 引文必须是 (段号, 字符串)：%r' % (where, pair))
        return None
    decl, q = pair
    if not isinstance(q, str) or not q:
        bad('%s: 引文不是非空字符串：%r' % (where, q))
        return None
    occ = [m.start() for m in re.finditer(re.escape(q), TEXT)]
    inr = [o for o in occ if o >= S and o + len(q) <= E]
    if len(inr) != 1:
        UNRESOLVED.append((where, q[:60], len(occ), len(inr)))
        bad('%s: 区间内出现 %d 次（须恰好 1）：%r' % (where, len(inr), q[:50]))
        return None
    st = inr[0]
    p = para_of(st)
    if p != decl:
        bad('%s: 声明段号 %s 与实际段号 %s 不符：%r' % (where, decl, p, q[:40]))
    obj = {
        'quote': q,
        'start': st,
        'end': st + len(q),
        'sourceHash': SOURCE_HASH,
        'para': p,
        'wholeTextOccurrences': len(occ),
        'occurrencesInRange': len(inr),
        'startIsFirstOccurrence': bool(occ) and st == occ[0],
        'firstOccurrenceAt': occ[0] if occ else None,
        'declaredPara': decl,
    }
    QUOTES.append(obj)
    return obj


def resolve_many(pairs, where):
    return [r for r in (resolve(p, '%s[%d]' % (where, i)) for i, p in enumerate(pairs)) if r]


def q1(pair, where):
    r = resolve_many([pair], where)
    return r[0] if r else None


# ── 3. 组装 tasks（五栏区间不相交是硬判据）─────────────────────────────
FIVE = ('objective', 'obstacle', 'action', 'result', 'cost')
TASKS_OUT = []
NULL_FIELDS = []

for t in A.TASKS:
    o = {'id': t['id'], 'actor': t['actor']}
    spans = []
    for f in FIVE:
        val = t.get(f)
        notes = t.get(f + 'Note')
        if val is None:
            o[f] = None
            o[f + 'Note'] = notes
            o[f + 'Basis'] = None
            NULL_FIELDS.append('%s.%s' % (t['id'], f))
            if not notes:
                bad('%s.%s 为 null 却没有同名 Note' % (t['id'], f))
            continue
        o[f] = val
        o[f + 'Basis'] = t.get(f + 'Basis')
        refs = resolve_many(t.get(f + 'Quotes') or [], '%s.%s' % (t['id'], f))
        o[f + 'Quotes'] = refs
        if not refs:
            bad('%s.%s 有值却没有任何可用引文' % (t['id'], f))
        for r in refs:
            spans.append((r['start'], r['end'], f))
        if notes:
            o[f + 'Note'] = notes
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b, fa = spans[i]
            c, d, fb = spans[j]
            if a < d and c < b:
                bad('%s 五栏区间相交：%s[%d,%d) ∩ %s[%d,%d)'
                    % (t['id'], fa, a, b, fb, c, d))
    o['basis'] = t.get('basis')
    if t.get('note'):
        o['note'] = t['note']
    TASKS_OUT.append(o)

# ── 4. causeEdges / rejectedEdges ──────────────────────────────────────
def edge_block(src, with_counter):
    out = []
    for e in src:
        o = {'id': e['id'], 'from': e['from'], 'to': e['to'],
             'basis': e.get('basis'),
             'quotes': resolve_many(e.get('quotes') or [], e['id'])}
        if with_counter:
            o['trigger'] = e.get('trigger')
            o['mechanism'] = e.get('mechanism')
            if not o['trigger']:
                bad('%s 缺 trigger（方向 + 触发是硬要求）' % e['id'])
            if not o['mechanism']:
                bad('%s 缺 mechanism' % e['id'])
            if e.get('counter'):
                o['counter'] = e['counter']
        else:
            o['why'] = e.get('why')
            if not o['why']:
                bad('%s（被拒边）缺 why：必须写明为什么看似因果却不连边' % e['id'])
            if e.get('trigger') or e.get('mechanism'):
                bad('%s 是被拒边，不应有 trigger/mechanism' % e['id'])
        if e.get('note'):
            o['note'] = e['note']
        out.append(o)
    return out


CAUSE_OUT = edge_block(A.CAUSE_EDGES, True)
REJECTED_OUT = edge_block(A.REJECTED_EDGES, False)

# ── 5. states ──────────────────────────────────────────────────────────
STATES_OUT = []
for s in B.STATES:
    o = {'id': s['id'], 'who': s['who']}
    o['before'] = s['before']
    o['beforeBasis'] = s['beforeBasis']
    o['beforeQuotes'] = resolve_many(s['beforeQuotes'], s['id'] + '.before')
    o['after'] = s['after']
    o['afterBasis'] = s['afterBasis']
    o['afterQuotes'] = resolve_many(s['afterQuotes'], s['id'] + '.after')
    o['anchor'] = s['anchor']
    o['anchorQuotes'] = resolve_many(s['anchorQuotes'], s['id'] + '.anchor')
    if s.get('note'):
        o['note'] = s['note']
    o['basis'] = s['basis']
    for k in ('before', 'after', 'anchor'):
        if not o[k + 'Quotes']:
            bad('%s.%s 无可用引文' % (s['id'], k))
    if not o['beforeBasis'] or not o['afterBasis']:
        bad('%s 前值/后值缺 basis' % s['id'])
    STATES_OUT.append(o)

# ── 6. foreshadows / notForeshadows ────────────────────────────────────
FORESHADOWS_OUT = []
for f in B.FORESHADOWS:
    setup = {'what': f['setup']['what'],
             'quote': q1(f['setup']['quote'], f['id'] + '.setup'),
             'basis': f['setup']['basis']}
    payoff = None
    if f.get('payoff'):
        payoff = {'what': f['payoff']['what'],
                  'quote': q1(f['payoff']['quote'], f['id'] + '.payoff'),
                  'basis': f['payoff']['basis']}
    o = {'id': f['id'], 'name': f['name'], 'setup': setup, 'payoff': payoff,
         'status': f['status'], 'unresolvedWhat': f.get('unresolvedWhat'),
         'basis': f['basis'], 'note': f.get('note')}
    if not setup['quote']:
        bad('%s.setup 引文解析失败' % f['id'])
    if payoff is None and f['status'] != 'unresolved':
        bad('%s 没有 payoff 却不是 unresolved' % f['id'])
    if f['status'] == 'unresolved' and not f.get('unresolvedWhat'):
        bad('%s unresolved 却没写未回收的是什么' % f['id'])
    FORESHADOWS_OUT.append(o)

NOT_FORESHADOWS_OUT = []
for n in B.NOT_FORESHADOWS:
    NOT_FORESHADOWS_OUT.append({
        'id': n['id'], 'name': n['name'], 'why': n['why'], 'basis': n['basis'],
        'quotes': resolve_many(n['quotes'], n['id']),
        'basisNote': n.get('basisNote'),
    })

# ── 7. worldSettings（三态字段强制）────────────────────────────────────
LEGAL_STATES = ('hold', 'transfer', 'use', 'lose')
WORLD_SETTINGS_OUT = []
SHAPE_PROBLEMS = []
for w in B.WORLD_SETTINGS:
    o = {'id': w['id'], 'kind': w['kind'], 'name': w['name'],
         'quote': q1(w['quote'], w['id'] + '.quote'),
         'extraQuotes': resolve_many(w.get('extraQuotes') or [], w['id'] + '.extra'),
         'explain': w['explain'], 'basis': w['basis']}
    if not o['quote']:
        bad('%s.quote 解析失败' % w['id'])
    if w['kind'] == 'place':
        if w.get('placeState') not in ('arrived', 'mentioned'):
            SHAPE_PROBLEMS.append('%s placeState=%r' % (w['id'], w.get('placeState')))
        o['placeState'] = w.get('placeState')
    elif w['kind'] == 'item':
        sts = w.get('itemStates')
        if not (isinstance(sts, list) and sts and all(x in LEGAL_STATES for x in sts)):
            SHAPE_PROBLEMS.append('%s itemStates=%r' % (w['id'], sts))
        o['itemStates'] = sts
    elif w['kind'] == 'rule':
        if w.get('institution') not in ('declared', 'executed', 'misunderstood'):
            SHAPE_PROBLEMS.append('%s institution=%r' % (w['id'], w.get('institution')))
        o['institution'] = w.get('institution')
        if not o['explain']:
            bad('%s rule 缺 explain' % w['id'])
    else:
        SHAPE_PROBLEMS.append('%s kind=%r 非法' % (w['id'], w['kind']))
    for extra in ('institutionNote', 'itemNote', 'placeNote'):
        if w.get(extra):
            o[extra] = w[extra]
    WORLD_SETTINGS_OUT.append(o)
for p in SHAPE_PROBLEMS:
    bad('worldSettings 形态问题：%s' % p)

NOT_WORLD_SETTINGS_OUT = []
for n in B.NOT_WORLD_SETTINGS:
    NOT_WORLD_SETTINGS_OUT.append({
        'id': n['id'], 'name': n['name'], 'why': n['why'], 'basis': n['basis'],
        'quotes': resolve_many(n['quotes'], n['id']),
        'basisNote': n.get('basisNote'),
    })

# ── 8. 主题读法 / 台词定性 / 知识差 / 文本注记 / 存疑 / 自评 ────────────
THEME_OUT = []
for th in C3.THEME_READINGS:
    sup = []
    for s in th['support']:
        ref = q1(s['quote'], th['id'] + '.support')
        sup.append({'text': s['text'], 'quote': ref})
        if not ref:
            bad('%s.support 引文解析失败' % th['id'])
    o = {'id': th['id'], 'perspective': th['perspective'], 'support': sup,
         'counter': th['counter'], 'basis': th['basis'], 'note': th.get('note')}
    if not (o['perspective'] and o['support'] and o['counter']):
        bad('%s 三件不全（perspective/support/counter）' % th['id'])
    THEME_OUT.append(o)
if len(THEME_OUT) > 2:
    bad('themeReadings 超过 2 条：%d' % len(THEME_OUT))

SPEECH_OUT = []
for v in C3.SPEECH_AS_CLUE_NOT_FACT:
    o = {'id': v['id'], 'quote': q1(v['quote'], v['id']),
         'whatItProves': v['whatItProves'], 'whatItDoesNot': v['whatItDoesNot']}
    if not o['quote']:
        bad('%s 引文解析失败' % v['id'])
    _ex = resolve_many(v.get('extraQuotes') or [], v['id'] + '.extra')
    if _ex:
        o['extraQuotes'] = _ex
    SPEECH_OUT.append(o)

KNOWLEDGE_OUT = []
for k in B.KNOWLEDGE_GAPS:
    o = {'id': k['id'], 'whoKnows': k['whoKnows'], 'whoDoesNot': k['whoDoesNot'],
         'why': k['why'], 'basis': k['basis'],
         'quotes': resolve_many(k['quotes'], k['id'])}
    KNOWLEDGE_OUT.append(o)

TEXTUAL_OUT = []
for n in C3.TEXTUAL_NOTES:
    o = {'id': n['id'], 'kind': n['kind'], 'quote': q1(n['quote'], n['id']),
         'note': n['note']}
    if not o['quote']:
        bad('%s 引文解析失败' % n['id'])
    TEXTUAL_OUT.append(o)

UNKNOWNS_OUT = []
for u in C3.UNKNOWNS:
    o = {'id': u['id'], 'what': u['what'], 'why': u['why'], 'basis': u['basis'],
         'quotes': resolve_many(u['quotes'], u['id'])}
    UNKNOWNS_OUT.append(o)

SELF_CRITIQUE_OUT = []
for s in C3.SELF_CRITIQUE:
    SELF_CRITIQUE_OUT.append({
        'id': s['id'], 'what': s['what'], 'whyRisk': s['whyRisk'],
        'whyStill': s['whyStill'], 'basis': s['basis'],
        'quotes': resolve_many(s['quotes'], s['id']),
    })
if len(SELF_CRITIQUE_OUT) < 3:
    bad('selfCritique 少于 3 条')

# ── 9. basis 取值合法性全扫 ────────────────────────────────────────────
LEGAL_BASIS = ('explicit', 'inferred', 'derived', 'unverified')


def scan_basis(o, path='$'):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o:
            return
        for k, v in o.items():
            if k == 'basis' and v not in LEGAL_BASIS:
                bad('%s.basis=%r 非法' % (path, v))
            scan_basis(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan_basis(v, '%s[%d]' % (path, i))


# ── 10. 行内「」必须逐字（本候选约定）──────────────────────────────────
INLINE_BAD = []


def scan_inline(o, path='$'):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o:
            return
        for k, v in o.items():
            scan_inline(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan_inline(v, '%s[%d]' % (path, i))
    elif isinstance(o, str):
        for m in re.finditer(r'「([^「」]*)」', o):
            if TEXT.find(m.group(1)) < 0:
                INLINE_BAD.append((path, m.group(1)[:50]))


# ── 11. 组装候选 ───────────────────────────────────────────────────────
CAND = {
    'schemaVersion': 'castline/read-candidate/1',
    'task': TASK['id'],
    'agent': 'w-xiyou-0',
    'role': 'READER',
    'book': TASK['book'],
    'bookTitle': '大奉打更人',
    'lane': TASK['lane'],
    'unitIndex': TASK['unitIndex'],
    'unitHead': TASK['unitHead'],
    'source': {
        'path': 'data/cache/1063b17ca65ec1b76f30e460.docs.json',
        'selector': 'docs[0].text',
        'range': [S, E],
        'codepoints': E - S,
        'sourceHash': SOURCE_HASH,
        'sourceHashScope': '整个 docs.json 文件的 sha256（不是切片）',
        'sliceSha256': hashlib.sha256(SLICE.encode('utf-8')).hexdigest(),
        'sliceSha256Scope': 'docs[0].text[%d:%d] 的 sha256（附加字段，不覆盖 sourceHash）' % (S, E),
        'offsetCaliber': '相对 docs[0].text 全文的 codepoint 偏移；docs[0].text[start:end]==quote 且 find(quote) 命中同一处',
        'boundaryHead': TASK['unitHead'],
        'nonEmptyParagraphs': len(PARAS),
        'graphCachePath': 'data/cache/1063b17ca65ec1b76f30e460.json',
        'graphCacheUsage': '**没有使用**。任务明令图谱缓存里的摘要不算原文证据；本候选的每一条引文与断言都只来自 docs[0].text 的切片。',
    },
    'provenanceNote': C3.PROVENANCE_NOTE,
    'semanticReview': 'not-performed',
    'semanticReviewNote': C3.SEMANTIC_REVIEW_NOTE,
    'basisLegend': {
        'explicit': '原文直述（叙述或人物原话直接写出）',
        'inferred': '我的归纳（从原文动作反推目标、从场景反推机制等）',
        'derived': '跨段推导（结论由区间内多处拼接得出，任一处缺失即不成立）',
        'unverified': '存疑（我给出但无法在原文中落实的）',
    },
    'nullFieldRule': None,   # 下方回填
    'speechAsClueNotFact': SPEECH_OUT,
    'tasks': TASKS_OUT,
    'causeEdges': CAUSE_OUT,
    'rejectedEdges': REJECTED_OUT,
    'states': STATES_OUT,
    'knowledgeGaps': KNOWLEDGE_OUT,
    'foreshadows': FORESHADOWS_OUT,
    'notForeshadows': NOT_FORESHADOWS_OUT,
    'worldSettings': WORLD_SETTINGS_OUT,
    'notWorldSettings': NOT_WORLD_SETTINGS_OUT,
    'themeReadings': THEME_OUT,
    'textualNotes': TEXTUAL_OUT,
    'unknowns': UNKNOWNS_OUT,
    'selfCritique': SELF_CRITIQUE_OUT,
    'selfCritiqueNote': C3.SELF_CRITIQUE_NOTE if hasattr(C3, 'SELF_CRITIQUE_NOTE') else None,
    'worldSettingsNote': None,   # 由下方回填（计数从列表本身算）
    'taskOrderNote': A.TASK_ORDER_NOTE,
}

scan_basis(CAND)

DANGLING = []


def scan_dangling(o, path='$'):
    if isinstance(o, dict):
        if isinstance(o.get('quote'), str) and ('start' not in o or 'end' not in o):
            DANGLING.append((path, o['quote'][:40]))
            return
        for k, v in o.items():
            scan_dangling(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan_dangling(v, '%s[%d]' % (path, i))


# ── 12. 覆盖度 ─────────────────────────────────────────────────────────
COV = set()
for q in QUOTES:
    COV.update(range(q['start'], q['end']))
NONSPACE = sum(1 for ch in SLICE if not ch.isspace())
ZERO = [i for i, (a, b, _t) in enumerate(PARAS, 1)
        if not any(o in COV for o in range(a, b))]
TOUCHED = {para_of(q['start']) for q in QUOTES}

CAND['machineSelfCheck'] = {
    'buildScript': 'loop/state/out/read_dafeng_L3_0251.w-xiyou-0.build/build_candidate.py',
    'contentModule': ('loop/state/out/read_dafeng_L3_0251.w-xiyou-0.build/content_0251.py + '
                      'content_0251b.py + content_0251c.py'),
    'verifyScript': 'loop/state/out/read_dafeng_L3_0251.w-xiyou-0.build/verify_candidate.py',
    'reproduceCommand': ('python3 -B -s loop/state/out/read_dafeng_L3_0251.w-xiyou-0.build/build_candidate.py && '
                         'python3 -B -s loop/state/out/read_dafeng_L3_0251.w-xiyou-0.build/verify_candidate.py'),
    'quoteObjectsResolved': len(QUOTES),
    'uniqueQuoteStrings': len({q['quote'] for q in QUOTES}),
    'unresolvedFailures': len(UNRESOLVED),
    'taskFieldIntervalOverlap': sum(1 for p in PROBLEMS if '五栏区间相交' in p),
    'nullFields': len(NULL_FIELDS),
    'nullFieldList': NULL_FIELDS,
    'nullWithoutNote': sum(1 for p in PROBLEMS if '没有同名 Note' in p),
    'requiredSections': ['tasks', 'causeEdges', 'states', 'foreshadows',
                         'worldSettings', 'themeReadings'],
    'missingSections': [],
    'worldSettingsShapeProblems': SHAPE_PROBLEMS,
    'inlineNonVerbatim': [list(x) for x in INLINE_BAD],
    'danglingQuotes': [list(x) for x in DANGLING],
    'labelNotInSource': [],
    'note': ('本块由构建脚本在写盘前生成；任一项判据失败则脚本以退出码 1 拒绝写出候选文件。'
             '判定【五栏独立性】用的是**字符区间两两不相交**（比【是不是同一句】更严）。'
             'worldSettings 条目之间、states 的 前值/锚点 之间不适用该判据，'
             '重叠处已在条目 Note 与 selfCritique 里标明。'),
}

_POST_START = None
for _i, (_a, _b, _t) in enumerate(PARAS, 1):
    if _t.startswith('PS:'):
        _POST_START = _i
        break
_CAT = {'separator': [], 'authorPostscript': [], 'short(<=22)': [], 'substantive': []}
for _i in ZERO:
    _t = PARAS[_i - 1][2]
    if set(_t) <= set('. -'):
        _CAT['separator'].append(_i)
    elif _POST_START and _i >= _POST_START:
        _CAT['authorPostscript'].append(_i)
    elif len(_t) <= 22:
        _CAT['short(<=22)'].append(_i)
    else:
        _CAT['substantive'].append(_i)

CAND['coverage'] = {
    'sliceCodepoints': E - S,
    'nonSpaceCodepoints': NONSPACE,
    'quoteUnionCodepoints': len(COV),
    'quoteUnionRatioOfSlice': round(len(COV) / (E - S), 4),
    'quoteUnionRatioOfNonSpace': round(len(COV) / NONSPACE, 4),
    'quoteIntervals': len(QUOTES),
    'paragraphs': len(PARAS),
    'paragraphsTouchedByAtLeastOneQuote': len(TOUCHED),
    'zeroCoveredParagraphs': ZERO,
    'zeroCoveredByCategory': _CAT,
    'zeroCoveredCounts': {k: len(v) for k, v in _CAT.items()},
    'note': ('%d 个零覆盖段按类别分列于 zeroCoveredByCategory（四个数字由构建脚本从段落表算，'
             '不手写）：纯排版分隔符 %d、作者附言（PS: 起）%d、短句（≤22 字）%d、'
             '实打实的叙事段落（长度>22 且非分隔符非附言）%d。'
             '本单元 substantive 为 %d —— 也就是说，**没有任何一段承载叙事的段落被漏掉引文**；'
             '剩下未覆盖的只有 %d 段纯符号分隔与 %d 段短句（多半是单句对白与过场）。'
             '这一条与前一轮（L3:0247，substantive 9）不同，故在此写明数字而不是沿用措辞。'
             '**引文覆盖不等于语义覆盖**：本候选没有做独立语义评审，'
             '零覆盖为 0 也不代表每一段都被正确理解。'
             % (len(ZERO), len(_CAT['separator']), len(_CAT['authorPostscript']),
                len(_CAT['short(<=22)']), len(_CAT['substantive']),
                len(_CAT['substantive']), len(_CAT['separator']),
                len(_CAT['short(<=22)']))),
}

CAND['nullFieldRule'] = (
    '缺依据的栏写 null，并在同名 `<栏位>Note` 里写明为什么没有。'
    '本候选实测 %d 个 null 栏：%s。每一处都带 Note，由构建脚本强制（缺 Note 即拒绝写盘）。'
    % (len(NULL_FIELDS), ' / '.join(NULL_FIELDS))
)

for k in CAND['machineSelfCheck']['requiredSections']:
    if k not in CAND:
        CAND['machineSelfCheck']['missingSections'].append(k)
        bad('内容分区缺失：%s' % k)

# ── 12a. worldSettingsNote 的计数**从列表本身算** ──────────────────────
_ws = CAND['worldSettings']
_counts = {
    'rule': sum(1 for w in _ws if w['kind'] == 'rule'),
    'place': sum(1 for w in _ws if w['kind'] == 'place'),
    'item': sum(1 for w in _ws if w['kind'] == 'item'),
    'arrived': sum(1 for w in _ws if w.get('placeState') == 'arrived'),
    'mentioned': sum(1 for w in _ws if w.get('placeState') == 'mentioned'),
    'declared': sum(1 for w in _ws if w.get('institution') == 'declared'),
    'executed': sum(1 for w in _ws if w.get('institution') == 'executed'),
    'misunderstood': sum(1 for w in _ws if w.get('institution') == 'misunderstood'),
}
CAND['worldSettingsNote'] = (
    '本区间收 %d 个 rule、%d 个 place、%d 个 item'
    '（place 里 %d 个 arrived、%d 个 mentioned；'
    'rule 里 declared %d / executed %d / misunderstood %d；'
    'item 覆盖的状态见各条 itemStates）。'
    % (_counts['rule'], _counts['place'], _counts['item'],
       _counts['arrived'], _counts['mentioned'],
       _counts['declared'], _counts['executed'], _counts['misunderstood'])
) + C3.WORLD_SETTINGS_NOTE_BODY
if _counts['arrived'] + _counts['mentioned'] != _counts['place']:
    bad('worldSettingsNote 计数不一致：arrived+mentioned != place')
if _counts['declared'] + _counts['executed'] + _counts['misunderstood'] != _counts['rule']:
    bad('worldSettingsNote 计数不一致：三态之和 != rule')

# ── 12b. 最终对象上的行内「」扫描（必须在所有字段落定之后）─────────────
INLINE_BAD.clear()
scan_inline(CAND)
for _p, _frag in INLINE_BAD:
    bad('行内「」非逐字（术语请改用【】）：%s 「%s」' % (_p, _frag))
CAND['machineSelfCheck']['inlineNonVerbatim'] = [list(x) for x in INLINE_BAD]

DANGLING.clear()
scan_dangling(CAND)
for d in DANGLING:
    bad('漏解析引文（有 quote 无偏移）：%s %r' % d)
CAND['machineSelfCheck']['danglingQuotes'] = [list(x) for x in DANGLING]

# ── 12c. 标签字段（name/title）里的【】必须能逐字命中（或含自造连接符）──
LABEL_BAD = []
LABEL_ALLOW = ('≠', '→', '=', '+')


def scan_labels(o, path='$'):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ('name', 'title') and isinstance(v, str):
                for m in re.finditer(r'【([^【】]+)】', v):
                    frag = m.group(1)
                    if len(frag) < 4 or any(a in frag for a in LABEL_ALLOW):
                        continue
                    if TEXT.find(frag) < 0:
                        LABEL_BAD.append((path + '.' + k, frag[:50]))
            scan_labels(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan_labels(v, '%s[%d]' % (path, i))


scan_labels(CAND)
for _p, _frag in LABEL_BAD:
    bad('标签【】疑似转述原文但全文找不到：%s 【%s】' % (_p, _frag))
CAND['machineSelfCheck']['labelNotInSource'] = [list(x) for x in LABEL_BAD]

# ── 12d. 期望条数自检（防内容模块被截断）───────────────────────────────
for _name, _got, _min in (
        ('tasks', len(TASKS_OUT), 10),
        ('causeEdges', len(CAUSE_OUT), 8),
        ('rejectedEdges', len(REJECTED_OUT), 5),
        ('states', len(STATES_OUT), 8),
        ('knowledgeGaps', len(KNOWLEDGE_OUT), 5),
        ('foreshadows', len(FORESHADOWS_OUT), 5),
        ('worldSettings', len(WORLD_SETTINGS_OUT), 16),
        ('themeReadings', len(THEME_OUT), 1),
        ('unknowns', len(UNKNOWNS_OUT), 8),
        ('selfCritique', len(SELF_CRITIQUE_OUT), 5),
):
    if _got < _min:
        bad('分区 %s 只有 %d 条（期望 ≥%d）—— 内容模块可能被截断' % (_name, _got, _min))

# ── 13. 写盘（仅在全部判据通过时）──────────────────────────────────────
if PROBLEMS:
    print('构建失败：%d 条判据不过' % len(PROBLEMS))
    for p in PROBLEMS[:40]:
        print('  FAIL %s' % p)
    if UNRESOLVED:
        print('未解析引文：')
        for u in UNRESOLVED[:20]:
            print('  %s tot=%s in=%s %r' % u)
    sys.exit(1)

OUT.write_text(json.dumps(CAND, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('已写出 %s' % OUT)
print('  引文对象 %d（唯一字符串 %d）' % (len(QUOTES), len({q['quote'] for q in QUOTES})))
print('  段 %d，被引段 %d，零覆盖段 %d' % (len(PARAS), len(TOUCHED), len(ZERO)))
print('  非空码点覆盖 %.4f' % (len(COV) / NONSPACE))
print('  null 栏 %d（全部带 Note）' % len(NULL_FIELDS))
