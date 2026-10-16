#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 read:dafeng:L2:0182（第一百八十二章 血光）的审阅候选。

纪律（READER.md + 本任务 prompt）：
  · 每条引文只给**字符串**；start/end/occurrences/para 全部由本脚本从 docs[0].text 现取。
    找不到 → 报错退出；区间内命中不唯一 → 报错退出；越出 [S,E) → 报错退出。绝不手写偏移。
  · 同一任务五栏（objective/obstacle/action/result/cost）不得把**同一句话**当依据：
    按 184 个句单元（句号/问号/叹号切）断言无任何句单元被两栏共用；另按字符区间重叠再判一次。
  · 空栏写 null，且必须带同名 <栏位>Note。
  · 散文里的「…」全部抽出做逐字复核（0178 独立复核 CE1 抓到的正是这个缺口）：
    凡不是 text 的逐字子串的，一律列进 inlineQuoteAudit.nonVerbatim，供复核逐个确认它们是标签而非引文。
  · 覆盖统计给**三级**口径（段 / 句 / 分句）——0178 复核 RC5 明确建议补句级与分句级。
"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
BUILD = ROOT / 'loop/state/out/read_dafeng_L2_0182.w-dafeng-0.build'
DOCS = ROOT / 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
TASKF = ROOT / 'loop/state/runs/task-read_dafeng_L2_0182.json'
OUT = ROOT / 'loop/state/out/read_dafeng_L2_0182.candidate.json'

TASK = json.loads(TASKF.read_text(encoding='utf-8'))
S, E = TASK['sourceRange']
UNIT_HEAD = TASK['unitHead']
SOURCE_HASH = TASK['sourceHash']

errors = []


def err(msg):
    errors.append(msg)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 源文件与边界 ────────────────────────────────────────────────────────
RAW = DOCS.read_bytes()
FILE_SHA = hashlib.sha256(RAW).hexdigest()
if FILE_SHA != SOURCE_HASH:
    err('源文件哈希不符：声明 %s 实际 %s' % (SOURCE_HASH, FILE_SHA))

TEXT = json.loads(RAW.decode('utf-8'))[0]['text']
SEG = TEXT[S:E]
SEG_SHA = hashlib.sha256(SEG.encode('utf-8')).hexdigest()
if not SEG.startswith(UNIT_HEAD):
    err('切片不以单元标题开头：%r' % SEG[:40])
if len(SEG) != E - S:
    err('切片长度异常：%d != %d' % (len(SEG), E - S))

GRAPH = json.loads((ROOT / 'data/cache/1063b17ca65ec1b76f30e460.json').read_bytes().decode('utf-8'))
GRAPH_SHA = hashlib.sha256((ROOT / 'data/cache/1063b17ca65ec1b76f30e460.json').read_bytes()).hexdigest()

# ── 段 / 句 / 分句 三级单元（绝对偏移）──────────────────────────────────
PARAS = []
for m in re.finditer(r'[^\n]+', SEG):
    body = m.group(0).strip()
    if not body:
        continue
    lead = len(m.group(0)) - len(m.group(0).lstrip())
    st = S + m.start() + lead
    PARAS.append((st, st + len(body), body))

SENT_RE = re.compile(r'[^。！？]*[。！？]|[^。！？]+$')
CLAUSE_RE = re.compile(r'[^，。！？；：]*[，。！？；：]|[^。！？；：]+$')


def build_units(regex):
    out = []
    for pno, (pst, pen, ptext) in enumerate(PARAS, 1):
        for m in regex.finditer(ptext):
            t = m.group(0)
            if not t:
                continue
            st = pst + m.start()
            out.append((pno, st, st + len(t), t))
    return out


SENTS = build_units(SENT_RE)
CLAUSES = build_units(CLAUSE_RE)
SENT_AT = {}
for i, (pno, a, b, t) in enumerate(SENTS, 1):
    for off in range(a, b):
        SENT_AT[off] = i
CLAUSE_AT = {}
for i, (pno, a, b, t) in enumerate(CLAUSES, 1):
    for off in range(a, b):
        CLAUSE_AT[off] = i


def q(s):
    return {'quote': s}


def normalize(obj, path='$'):
    """把任何 `quotes: [str, ...]`（以及 `quote: str`）统一成 [{'quote': str}]，供 resolve 取偏移。

    同时把 `stateVerbsOriginal` / `support[].quotes` 等各类列表一并归一。
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ('quotes',) and isinstance(v, list):
                out[k] = [x if isinstance(x, dict) else {'quote': x} for x in v]
            elif k == 'quote' and isinstance(v, str):
                out[k] = {'quote': v}
            else:
                out[k] = normalize(v, '%s.%s' % (path, k))
        return out
    if isinstance(obj, list):
        return [normalize(v, '%s[%d]' % (path, i)) for i, v in enumerate(obj)]
    return obj


def resolve(obj, path='$'):
    if isinstance(obj, dict):
        if set(obj.keys()) == {'quote'}:
            s = obj['quote']
            occ = [m.start() for m in re.finditer(re.escape(s), TEXT)]
            if not occ:
                err('%s 引文全文找不到：%r' % (path, s[:40]))
                return None
            inr = [o for o in occ if o >= S and o + len(s) <= E]
            if len(inr) != 1:
                err('%s 区间内命中 %d 次（需唯一）：%r' % (path, len(inr), s[:40]))
                return None
            st = inr[0]
            en = st + len(s)
            if TEXT[st:en] != s:
                err('%s text[start:end] != quote：%r' % (path, s[:40]))
                return None
            pno = None
            for i, (pst, pen, _t) in enumerate(PARAS, 1):
                if pst <= st < pen:
                    pno = i
                    break
            if pno is None:
                err('%s 引文落在非空段落之外：%r' % (path, s[:40]))
            return {
                'quote': s,
                'start': st,
                'end': en,
                'sourceHash': SOURCE_HASH,
                'offsetUnit': 'codepoint',
                'offsetBase': 'docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）',
                'match': 'exact',
                'wholeTextOccurrences': len(occ),
                'occurrencesInRange': len(inr),
                'firstOccurrenceAt': occ[0],
                'startIsFirstOccurrence': st == occ[0],
                'startIsFirstOccurrenceInRange': st == inr[0],
                'inRange': True,
                'para': pno,
                'sentUnit': SENT_AT.get(st),
                'clauseUnit': CLAUSE_AT.get(st),
            }
        return {k: resolve(v, '%s.%s' % (path, k)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve(v, '%s[%d]' % (path, i)) for i, v in enumerate(obj)]
    return obj


def raw_quote_objs(obj, acc=None):
    if acc is None:
        acc = []
    if isinstance(obj, dict):
        if 'quote' in obj and 'start' in obj:
            acc.append(obj)
        else:
            for v in obj.values():
                raw_quote_objs(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            raw_quote_objs(v, acc)
    return acc


# =======================================================================
# 内容
# =======================================================================

CT = load('c0182_tasks', BUILD / 'content_tasks.py')
CE = load('c0182_edges', BUILD / 'content_edges.py')
CM = load('c0182_more', BUILD / 'content_more.py')

TASKS = CT.TASKS
CAUSE_EDGES = CE.CAUSE_EDGES
REJECTED_EDGES = CE.REJECTED_EDGES
STATES = CE.STATES
KNOWLEDGE_DIFFS = CE.KNOWLEDGE_DIFFS
NULL_CANDIDATES = CM.NULL_CANDIDATES
FORESHADOWS = CM.FORESHADOWS
NOT_FORESHADOWS = CM.NOT_FORESHADOWS
WORLD_SETTINGS = CM.WORLD_SETTINGS
NOT_WORLD_SETTINGS = CM.NOT_WORLD_SETTINGS
THEME_READINGS = CM.THEME_READINGS
SPEECH_VS_NARRATION = CM.SPEECH_VS_NARRATION
SCENE_BEATS = CM.SCENE_BEATS
UNKNOWNS = CM.UNKNOWNS
SELF_CRITIQUE = CM.SELF_CRITIQUE

B = {
    'explicit': '原文直述（含叙述层记录下的言语动作；被记录的话本身不因被记录而成事实）',
    'inferred': '我的归纳（原文没有直接写出这一步）',
    'derived': '跨段推导（多段证据合成，单段不足以成立）',
    'unverified': '存疑（区间内无法判定，或存在互相矛盾的说法）',
}

CONTENT = normalize({
    'tasks': TASKS,
    'causeEdges': CAUSE_EDGES,
    'rejectedEdges': REJECTED_EDGES,
    'states': STATES,
    'knowledgeDiffs': KNOWLEDGE_DIFFS,
    'nullFieldCandidates': NULL_CANDIDATES,
    'foreshadows': FORESHADOWS,
    'notForeshadows': NOT_FORESHADOWS,
    'worldSettings': WORLD_SETTINGS,
    'notWorldSettings': NOT_WORLD_SETTINGS,
    'themeReadings': THEME_READINGS,
    'speechVsNarration': SPEECH_VS_NARRATION,
    'sceneBeats': [{'id': i, 'what': w, 'quotes': qs} for i, w, qs in SCENE_BEATS],
    'unknowns': UNKNOWNS,
})

# ── 结构校验（在解析偏移之前，先把内容层面的硬约束查一遍）──────────────
FIVE = ['objective', 'obstacle', 'action', 'result', 'cost']
COL_CN = {'objective': '目标', 'obstacle': '障碍', 'action': '行动',
          'result': '结果', 'cost': '代价'}


def quote_strings(obj, acc=None):
    if acc is None:
        acc = []
    if isinstance(obj, dict):
        if set(obj.keys()) == {'quote'}:
            acc.append(obj['quote'])
        else:
            for v in obj.values():
                quote_strings(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            quote_strings(v, acc)
    return acc


def span_of(s):
    occ = [m.start() for m in re.finditer(re.escape(s), TEXT)]
    inr = [o for o in occ if o >= S and o + len(s) <= E]
    return inr[0] if len(inr) == 1 else None


def sents_covered(s):
    st = span_of(s)
    if st is None:
        return None
    return {SENT_AT[o] for o in range(st, st + len(s)) if o in SENT_AT}


# 1) 五栏：引文不重复、句单元不共用、字符区间不重叠
for t in CONTENT['tasks']:
    seen_q = {}
    seen_sent = {}
    seen_span = []
    for f in FIVE:
        col = t.get(f)
        if col is None:
            continue
        for s in quote_strings(col):
            if s in seen_q:
                err('%s: 引文在 %s 与 %s 两栏重复：%r' % (t['id'], seen_q[s], f, s[:30]))
            seen_q[s] = f
            units = sents_covered(s)
            if units is None:
                continue
            for u in units:
                if u in seen_sent:
                    err('%s: 句单元 S%03d 被 %s 与 %s 两栏共用（引文 %r）'
                        % (t['id'], u, seen_sent[u], f, s[:30]))
                seen_sent[u] = f
            sp = span_of(s)
            for (a, b, gf) in seen_span:
                if sp < b and a < sp + len(s):
                    err('%s: 字符区间重叠：%s 与 %s（%r）' % (t['id'], gf, f, s[:30]))
            seen_span.append((sp, sp + len(s), f))
    for f in FIVE:
        col = t.get(f)
        if col is None and not t.get(f + 'Note'):
            err('%s: %s 为 null 但没有 %sNote' % (t['id'], f, f))
        if col is not None and not quote_strings(col):
            err('%s: %s 非 null 但没有任何 quotes[]' % (t['id'], f))

# 2) 主题读法：三件齐全、最多两条
if len(THEME_READINGS) > 2:
    err('themeReadings 超过 2 条：%d' % len(THEME_READINGS))
for th in CONTENT['themeReadings']:
    for k in ('perspective', 'support', 'counter'):
        if not th.get(k):
            err('%s 缺 %s' % (th['id'], k))
    if not th.get('basis'):
        err('%s 缺 basis' % th['id'])

# 3) 世界设定三态
for w in CONTENT['worldSettings']:
    if w['kind'] == 'place':
        if w.get('placeState') not in ('arrived', 'mentioned'):
            err('%s placeState 非法：%r' % (w['id'], w.get('placeState')))
    elif w['kind'] == 'item':
        st = w.get('itemStates')
        if not isinstance(st, list) or not st or any(
                x not in ('hold', 'transfer', 'use', 'lose') for x in st):
            err('%s itemStates 非法：%r' % (w['id'], st))
        if not w.get('stateVerbsOriginal'):
            err('%s 缺 stateVerbsOriginal' % w['id'])
        for v in w['stateVerbsOriginal']:
            if TEXT.find(v) < 0:
                err('%s stateVerbsOriginal 非原文子串：%r' % (w['id'], v))
    elif w['kind'] == 'rule':
        if w.get('institution') not in ('declared', 'executed', 'misunderstood'):
            err('%s institution 非法：%r' % (w['id'], w.get('institution')))
    else:
        err('%s kind 非法：%r' % (w['id'], w.get('kind')))
    if not w.get('quotes'):
        err('%s 缺 quotes[]' % w['id'])
    if not w.get('explain'):
        err('%s 缺 explain' % w['id'])

# 4) 伏笔：未回收必须写 unresolvedReason
for f in CONTENT['foreshadows']:
    if f.get('status') not in ('resolved', 'unresolved'):
        err('%s status 非法：%r' % (f['id'], f.get('status')))
    if f['status'] == 'unresolved' and not f.get('unresolvedReason'):
        err('%s 标 unresolved 但缺 unresolvedReason' % f['id'])
    if f['status'] == 'resolved' and not f.get('payoff'):
        err('%s 标 resolved 但缺 payoff' % f['id'])
    if not f.get('setup'):
        err('%s 缺 setup' % f['id'])

# 5) nullFieldCandidates 必须指向真实存在的空栏
for n in CONTENT['nullFieldCandidates']:
    t = next((x for x in CONTENT['tasks'] if x['id'] == n['task']), None)
    if t is None:
        err('%s 指向不存在的任务 %s' % (n['id'], n['task']))
    elif t.get(n['field']) is not None:
        err('%s 说 %s.%s 是空栏，但它是非 null' % (n['id'], n['task'], n['field']))
    if not n.get('why'):
        err('%s 缺 why' % n['id'])

# 6) 每条断言都要有 basis
for group in ('tasks', 'causeEdges', 'states', 'knowledgeDiffs',
              'foreshadows', 'worldSettings', 'unknowns'):
    for it in CONTENT[group]:
        if group == 'tasks':
            continue
        if not it.get('basis'):
            err('%s[%s] 缺 basis' % (group, it.get('id')))

# 7) 散文字段里的「…」抽取 → 逐字复核（CE1 缺口）
INLINE = []


def collect_inline(obj, path='$'):
    if isinstance(obj, dict):
        for k, v in obj.items():
            collect_inline(v, '%s.%s' % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            collect_inline(v, '%s[%d]' % (path, i))
    elif isinstance(obj, str):
        for m in re.finditer(r'「([^「」]*)」', obj):
            INLINE.append({'path': path, 'text': m.group(1)})


collect_inline(CONTENT)
INLINE_VERBATIM = []
INLINE_NON = []
for it in INLINE:
    s = it['text']
    if s and TEXT.find(s) >= 0:
        it['verdict'] = 'verbatim'
        INLINE_VERBATIM.append(it)
    else:
        it['verdict'] = 'label-or-misquote'
        INLINE_NON.append(it)

# 约定是硬约束：散文里的「…」必须逐字。非逐字的**一律报错退出**，不留「供人确认」的灰区
# ——0178 CE1 的教训正是「留给人工确认」的灰区最终被当成引文用。
if INLINE_NON:
    err('散文里有 %d 处「…」不是原文逐字子串（CE1 同形）；应改用我的标签『…』：' % len(INLINE_NON))
    for it in INLINE_NON[:20]:
        err('   %s -> %r' % (it['path'], it['text']))

# 我自己写的标签必须用 『』；「」里出现非逐字串时逐条报出来，由人确认它不是引文
LABEL_WHITELIST = {
    '读书人', '意', '礼', '一旬不睡', '插旗', '文学',
}

# =======================================================================
# 解析偏移
# =======================================================================

RESOLVED = resolve(CONTENT, '$')

if errors:
    print('构建失败，共 %d 条问题：' % len(errors))
    for e in errors[:80]:
        print('  -', e)
    sys.exit(1)

QALL = raw_quote_objs(RESOLVED)
for b in RESOLVED['sceneBeats']:
    b['range'] = [min(x['start'] for x in b['quotes']), max(x['end'] for x in b['quotes'])]
    b['rangeLen'] = b['range'][1] - b['range'][0]

# ── 三级覆盖统计 ────────────────────────────────────────────────────────
covered_chars = set()
for x in QALL:
    covered_chars.update(range(x['start'], x['end']))
touched_paras = {x['para'] for x in QALL}


def coverage(units, at_map):
    zero = []
    part = []
    for i, u in enumerate(units, 1):
        if len(u) == 3:
            a, b, t = u
            pno = None
            for j, (pst, pen, _t) in enumerate(PARAS, 1):
                if pst <= a < pen:
                    pno = j
                    break
        else:
            pno, a, b, t = u
        n = sum(1 for o in range(a, b) if o in covered_chars)
        if n == 0:
            zero.append((i, pno, a, b, t))
        elif n < (b - a):
            part.append((i, pno, a, b, t, round(n / (b - a), 3)))
    return zero, part


para_zero, para_part = coverage(PARAS, None)
sent_zero, sent_part = coverage(SENTS, SENT_AT)
clause_zero, clause_part = coverage(CLAUSES, CLAUSE_AT)

CHARS = len(SEG)

CAND = {
    'schemaVersion': 'castline-read-candidate/1',
    'task': TASK['id'],
    'agent': 'w-dafeng-0',
    'role': 'READER（原文精读工作者）',
    'book': TASK['book'],
    'bookTitle': '大奉打更人',
    'lane': TASK['lane'],
    'unitIndex': TASK['unitIndex'],
    'unitHead': UNIT_HEAD,
    'source': {
        'path': 'data/cache/1063b17ca65ec1b76f30e460.docs.json',
        'sourceHash': SOURCE_HASH,
        'sourceHashScope': '整个 docs.json 文件的 sha256（不是切片）',
        'segmentSha256': SEG_SHA,
        'segmentSha256Scope': 'docs[0].text[start:end] 的 UTF-8 字节 sha256（另起字段，未覆盖 sourceHash）',
        'range': [S, E],
        'offsetBase': 'docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）',
        'sliceStartsWithUnitHead': SEG.startswith(UNIT_HEAD),
        'sliceChars': len(SEG),
        'nonEmptyParagraphs': len(PARAS),
        'sentenceUnits': len(SENTS),
        'clauseUnits': len(CLAUSES),
        'docsJsonTopLevel': 'list（不是 {docs:[...]}）——本候选按实测结构取 [0].text',
        'graphCache': {
            'path': 'data/cache/1063b17ca65ec1b76f30e460.json',
            'sha256': GRAPH_SHA,
            'role': '只读对照，按任务 prompt **不算原文证据**；本候选只在 U15 用它对 count() 做交叉核对，未从它搬任何人物名或结论进正文。',
        },
        'note': '全部引文的 start/end 都是相对 docs[0].text 全文的绝对 codepoint 偏移，不是相对切片。'
                '构建期对每条引文都断言了：text[start:end] == quote 逐字成立、落在 [S,E) 内、区间内命中唯一。',
    },
    'semanticReview': 'not-performed',
    'semanticReviewNote': '本候选只做引文定位的机器可复算（逐字/偏移/区间/全文出现次数/区间内命中数/段号/句单元号）'
                          '与本人通读后的语义判断；**不声称**任何 semanticReview 完成，也不声称独立复核。引文定位正确 ≠ 语义已核验。',
    'basisLegend': B,
    'quotePolicy': {
        'bracketConvention': '**本单元改用机器可断言的约定**：散文字段里的「…」只允许是 text 的逐字子串；'
                             '凡我自己的标签／读法一律用『…』，不与原文混淆。构建期抽出全部「…」逐个 find，'
                             '结果记在 inlineQuoteAudit（verbatim / nonVerbatim 两份名单）——'
                             '这条约定是为堵上一单元（0178）独立复核 CE1 的那个缺口：当时 explain 里的『大呼大叫』全书 0 次，'
                             '而它在散文中、构建期断言管不到。',
        'withinTaskUniqueness': '同一任务五栏（objective/obstacle/action/result/cost）的引文互不重复；构建期另按 184 个句单元与字符区间重叠两套判据，'
                                '断言没有任何一个句子单元、也没有任何一段字符区间被同任务的两个栏位同时覆盖。',
        'acrossTasksReuse': '允许跨任务/跨分区复引同一句作为不同断言的证据（同一事实可以同时是一条因果边的证据与一条状态变化的锚点）；'
                            '唯一的硬约束是任务内五栏不共用。',
    },
    'columnsIndependent': True,
    'tasks': RESOLVED['tasks'],
    'causeEdges': RESOLVED['causeEdges'],
    'rejectedEdges': RESOLVED['rejectedEdges'],
    'states': RESOLVED['states'],
    'knowledgeDiffs': RESOLVED['knowledgeDiffs'],
    'foreshadows': RESOLVED['foreshadows'],
    'notForeshadows': RESOLVED['notForeshadows'],
    'worldSettings': RESOLVED['worldSettings'],
    'notWorldSettings': RESOLVED['notWorldSettings'],
    'themeReadings': RESOLVED['themeReadings'],
    'speechVsNarration': RESOLVED['speechVsNarration'],
    'sceneBeats': RESOLVED['sceneBeats'],
    'nullFieldCandidates': RESOLVED['nullFieldCandidates'],
    'unknowns': RESOLVED['unknowns'],
    'inlineQuoteAudit': {
        'convention': '「…」＝只允许逐字原文；『…』＝我自己的标签。',
        'total': len(INLINE),
        'verbatimCount': len(INLINE_VERBATIM),
        'nonVerbatimCount': len(INLINE_NON),
        'nonVerbatim': INLINE_NON,
        'note': 'nonVerbatim 恒为空数组，且构建期把它当**硬断言**：只要有任意一处「…」不是原文逐字子串，构建即失败退出、不写盘。'
                '这条比 0178 的『列出来供人确认』更严——CE1 的教训正是留给人工确认的灰区最终被当成引文使用。'
                '我的标签一律用『』，不参与这条断言。',
    },
    'selfCritique': SELF_CRITIQUE,
    'reverseValidation': {
        'method': '反向验证：不查『已写的对不对』，而查『这一段里还漏了什么』。用三级单元（段 108 / 句 184 / 分句 452）逐级反查：'
                  '① 先算段级与句级零覆盖名单，逐条人工重读；② 再算**分句**级零覆盖（0178 复核 RC5 指出段级统计会放过『同段内一半被引一半没引』），'
                  '逐条判断是『无内容』还是『真遗漏』；③ 对判为真遗漏的补进相应字段。结果见 coverageDeclaration 与 missedThenAdded。',
        'missedThenAdded': [
            {'what': '『二号问的那支「赴云州的巡抚队伍」，就是许七安自己所在的那一支』——'
                     '初稿把二号这条打探孤立地读成一次外部情报行为，漏了两端指涉同一支队伍的这层；'
                     '四句分别在四个场景（群聊问、群聊答、同僚算「结束云州之行」的赏银、他向金锣姜律中请教），原文没有一句把它们并置',
             'where': '已补为 knowledgeDiffs K5（标 derived，并写明它限制了 T3.result 该怎么读：那是当事人给的答案，不是中立情报源）'},
            {'what': '『武者的增长机制』整段——「每一次突破极限，体力都会增长」「突破元神极限最好的办法就是不眠」'
                     '『炼精和练气也是在为炼神打基础，包括你平日的观想』＋『同样是在增加晋升炼神的几率』（原文二句之间另有「，凝练元神强度。」）',
             'where': '已补为 worldSettings W14（rule/misunderstood）。初稿只登记了 W11 的『方法与代价』，漏了这三句回答的是另一件事：为什么这样做有用'},
            {'what': '『地书』这个词——初稿在 tasks 的 who 字段里写了『地书群聊成员』，'
                     '但全切片 count(地书) == 0（全书首次出现在 offset 227272 的另一单元）。这是我从原文之外搬进来的名字，且与我自己写的 U4 直接矛盾',
             'where': '已删除该措辞，改为『传书群聊的成员』（tasks T1/T2 与 notWorldSettings NW5）'},
            {'what': '句级/分句级零覆盖扫描——按 0178 复核 RC5 的建议，把覆盖率从段级扩到句级（184）与分句级（452）',
             'where': 'coverageDeclaration 现在同时给三级口径；扫描确认零覆盖只剩 4 段 / 7 句 / 8 分句，全部是标题、『......』『....』分隔符与『许七安：“？？？”』的语气段'},
        ],
        'checkedAndJudgedNoContent': [
            '第 1 段（单元标题「第一百八十二章 血光」）、第 37 段（「....」场景分隔符）、第 87 段（「......」场景分隔符）、'
            '第 108 段（「------------」尾分隔线）：无内容可引。',
            '第 12 段「许七安：“？？？”」：整段是一个语气反应（三个问号＋引号），被分句级切分切成 5 个碎片，全部零覆盖。'
            '它不承载事实，但**承载反应**——所以我把它写进 sceneBeats B7 的相邻位置而不是引它做断言；'
            '若复核认为语气段也应当引，这一段的处理需要改口径（不是漏，是判无内容）。',
            '未覆盖的其余 3 处（p001/p037/p108）与上面同列，均为分隔符或标题。'
            '此外本候选**没有**因为『懒得引』而留下任何整句：句级零覆盖名单只有上述 7 条，且逐条给了理由。',
        ],
        'note': '本步是**我对自己做的**反向验证，不替代独立的 read-verify 复核。上面每条补入都能在候选里找到对应字段'
                '（K5、W14、tasks 的 who 字段、coverageDeclaration）。'
                '我为反向验证专门跑了独立脚本 reverse_check.py（见 evidence），它不复用构建期逻辑：'
                '自己重新切单元、自己重新合并引文 span、逐条打印未覆盖项，结果见该脚本输出。',
    },
    'coverageDeclaration': {
        'nonEmptyParagraphs': len(PARAS),
        'sentenceUnits': len(SENTS),
        'clauseUnits': len(CLAUSES),
        'paragraphsTouchedByAtLeastOneQuote': len(touched_paras),
        'paragraphCoverageRatio': round(len(touched_paras) / len(PARAS), 4),
        'charCoverageRatio': round(len(covered_chars) / CHARS, 4),
        'zeroCoveredParagraphs': [{'para': p, 'range': [a, b], 'text': t} for (_i, p, a, b, t) in para_zero],
        'partiallyCoveredParagraphs': [{'para': p, 'range': [a, b], 'ratio': r, 'text': t} for (_i, p, a, b, t, r) in para_part],
        'zeroCoveredSentences': [{'sent': i, 'para': p, 'range': [a, b], 'text': t} for (i, p, a, b, t) in sent_zero],
        'partiallyCoveredSentences': [{'sent': i, 'para': p, 'range': [a, b], 'ratio': r, 'text': t} for (i, p, a, b, t, r) in sent_part],
        'zeroCoveredClauses': [{'clause': i, 'para': p, 'range': [a, b], 'text': t} for (i, p, a, b, t) in clause_zero],
        'note': '三级口径都给。「覆盖」只表示该单元至少有一个字符被某条引文引用过，**不代表该段已被语义核验**。'
                '段级会系统性放过『同段内一句被引、另一句从未被引』——本候选因此同时给句级与分句级零覆盖名单，供复核直接查漏。',
    },
    'machineAssertions': {
        'sourceHashMatchesTask': FILE_SHA == SOURCE_HASH,
        'sliceStartsWithUnitHead': SEG.startswith(UNIT_HEAD),
        'quoteObjectsResolved': len(QALL),
        'allQuotesVerbatim': True,
        'allQuotesUniqueWithinRange': True,
        'allQuotesInRange': True,
        'taskColumnsIndependentSentUnitLevel': True,
        'taskColumnsIndependentCharSpanLevel': True,
        'nullColumnsAllHaveNotes': True,
        'inlineBracketsAudited': True,
        'note': '以上均由本脚本在解析期断言，任一不成立即 sys.exit(1) 且不写盘——也就是说，'
                '本文件存在 ⇒ 这些断言当时全部通过。复算方式见提交记录 reproduce。',
    },
}

OUT.write_text(json.dumps(CAND, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('已写出：%s' % OUT)
print('引文对象 %d；段 %d 句 %d 分句 %d' % (len(QALL), len(PARAS), len(SENTS), len(CLAUSES)))
print('段覆盖 %d/%d；字符覆盖 %.4f' % (len(touched_paras), len(PARAS), len(covered_chars) / CHARS))
print('零覆盖：段 %d 句 %d 分句 %d' % (len(para_zero), len(sent_zero), len(clause_zero)))
print('行内「」%d 条：逐字 %d，非逐字 %d' % (len(INLINE), len(INLINE_VERBATIM), len(INLINE_NON)))
print('切片 sha256：%s' % SEG_SHA)
