#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 read:dafeng:L3:0243（第十四章 女尸）候选 JSON。

设计约束（都来自本任务提示词的硬性红线）：
1. **偏移不手写**：content_0243.py 里只写 quote 字符串，本脚本用 TEXT.find 求出
   start/end；要求该 quote 在 [S,E) 内**恰好出现一次**，否则脚本以退出码 1 拒绝写盘。
2. **五栏不共用一句**：每条任务的 objective/obstacle/action/result/cost 各自带 quotes[]，
   构建期用**字符区间两两不相交**判定，违反则不写盘（比"是不是同一句"更严）。
3. **null 必须带理由**：某一栏为 null 而缺同名 <栏位>Note ⇒ 拒绝写盘。
4. **分区齐全**：提示词要求的 6 个顶层分区缺一 ⇒ 拒绝写盘（即使本区间没有内容也要写空数组）。
5. `「」` 行内引用也逐字核验：散文里出现的每一段「…」都必须在 TEXT 里 find 得到。

本脚本只写 `loop/state/out/read_dafeng_L3_0243.candidate.json`（任务的 writes 路径）
与自身的构建产物；不触碰任何受保护路径。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import content_0243 as CT  # noqa: E402

ROOT = Path('/Users/carmen/Desktop/星系')
DOCS = ROOT / 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
TASKF = ROOT / 'loop/state/runs/task-read_dafeng_L3_0243.json'
OUT = ROOT / 'loop/state/out/read_dafeng_L3_0243.candidate.json'

TASK = json.loads(TASKF.read_text(encoding='utf-8'))
S, E = TASK['sourceRange']
DOCS_BYTES = DOCS.read_bytes()
DOCS_SHA = hashlib.sha256(DOCS_BYTES).hexdigest()
TEXT = json.loads(DOCS_BYTES.decode('utf-8'))[0]['text']
SLICE = TEXT[S:E]

problems: list[str] = []


# ── 段落表（非空行）─────────────────────────────────────────────────────
PARAS = []
for _m in re.finditer(r'[^\n]+', SLICE):
    _a = _m.start() + S + (len(_m.group(0)) - len(_m.group(0).lstrip()))
    _b = _m.start() + S + len(_m.group(0).rstrip())
    if _m.group(0).strip():
        PARAS.append((_a, _b, _m.group(0).strip()))


def para_of(pos: int):
    for i, (a, b, _t) in enumerate(PARAS, 1):
        if a <= pos < b:
            return i
    return None


# ── quote 解析 ─────────────────────────────────────────────────────────
def resolve(quote: str, where: str) -> dict:
    """把 quote 字符串解析成带全文偏移的引用对象。"""
    occ = [m.start() for m in re.finditer(re.escape(quote), TEXT)]
    inr = [o for o in occ if o >= S and o + len(quote) <= E]
    if len(inr) != 1:
        problems.append(
            '%s：引文在区间内出现 %d 次（要求恰好 1 次）—— quote=%r 区间内偏移=%s'
            % (where, len(inr), quote[:60], inr[:5]))
        if not occ:
            problems.append('%s：引文在**全文**里都找不到（非逐字）：%r' % (where, quote[:80]))
        return {'quote': quote, 'start': None, 'end': None}
    st = inr[0]
    return {
        'quote': quote,
        'start': st,
        'end': st + len(quote),
        'sourceHash': DOCS_SHA,
        'para': para_of(st),
        'wholeTextOccurrences': len(occ),
        'occurrencesInRange': len(inr),
        'startIsFirstOccurrence': st == occ[0],
        'firstOccurrenceAt': occ[0] if occ else None,
    }


def check_para(quote: str, para, where: str) -> None:
    """引文必须真的落在作者声明的那一段里（防止把 A 段的话挂到 B 段的判断上）。"""
    if para is None:
        return
    if not (1 <= para <= len(PARAS)):
        problems.append('%s：声明的段号 %r 超出 1..%d' % (where, para, len(PARAS)))
        return
    a, b, txt = PARAS[para - 1]
    if quote not in txt:
        problems.append('%s：引文不在声明的第 %d 段里 —— quote=%r'
                        % (where, para, quote[:60]))


def walk_resolve(o, where='$'):
    if isinstance(o, dict):
        if set(o.keys()) == {'__q__', '__para__'}:
            check_para(o['__q__'], o['__para__'], where)
            r = resolve(o['__q__'], where)
            r['declaredPara'] = o['__para__']
            if r.get('para') is not None and r['para'] != o['__para__']:
                problems.append('%s：偏移落在第 %s 段，与声明的第 %s 段不符'
                                % (where, r['para'], o['__para__']))
            return r
        return {k: walk_resolve(v, '%s.%s' % (where, k)) for k, v in o.items()}
    if isinstance(o, list):
        return [walk_resolve(v, '%s[%d]' % (where, i)) for i, v in enumerate(o)]
    return o


# ── 组装 ───────────────────────────────────────────────────────────────
CAND: dict = {}
CAND['schemaVersion'] = 'castline/read-candidate/1'
CAND['task'] = TASK['id']
CAND['agent'] = 'w-xiyou-0'
CAND['role'] = 'READER'
CAND['book'] = TASK['book']
CAND['bookTitle'] = '大奉打更人'
CAND['lane'] = TASK['lane']
CAND['unitIndex'] = TASK['unitIndex']
CAND['unitHead'] = TASK['unitHead']

CAND['source'] = {
    'path': 'data/cache/1063b17ca65ec1b76f30e460.docs.json',
    'selector': 'docs[0].text',
    'range': [S, E],
    'codepoints': E - S,
    'sourceHash': DOCS_SHA,
    'sourceHashScope': '整个 docs.json 文件的 sha256（不是切片）',
    'sliceSha256': hashlib.sha256(SLICE.encode('utf-8')).hexdigest(),
    'sliceSha256Scope': 'docs[0].text[%d:%d] 的 sha256（附加字段，不覆盖 sourceHash）' % (S, E),
    'offsetCaliber': ('相对 docs[0].text 全文的 codepoint 偏移；'
                      'docs[0].text[start:end]==quote 且 find(quote) 命中同一处'),
    'boundaryHead': SLICE[:len(TASK['unitHead'])],
    'nonEmptyParagraphs': len(PARAS),
    'graphCachePath': 'data/cache/1063b17ca65ec1b76f30e460.json',
    'graphCacheUsage': ('**没有使用**。任务明令图谱缓存里的摘要不算原文证据；'
                        '本候选的每一条引文与断言都只来自 docs[0].text 的切片。'),
}

CAND['provenanceNote'] = CT.PROVENANCE_NOTE_TEMPLATE % len(CT.TASKS)
CAND['semanticReview'] = 'not-performed'
CAND['semanticReviewNote'] = CT.SEMANTIC_REVIEW_NOTE
CAND['basisLegend'] = {
    'explicit': '原文直述（叙述或人物原话直接写出）',
    'inferred': '我的归纳（从原文动作反推目标、从场景反推机制等）',
    'derived': '跨段推导（结论由区间内多处拼接得出，任一处缺失即不成立）',
    'unverified': '存疑（我给出但无法在原文中落实的）',
}
CAND['nullFieldRule'] = None      # 占位：具体条数在算完 null 栏之后回填（见下）
CAND['speechAsClueNotFact'] = walk_resolve(CT.SPEECH_AS_CLUE, '$.speechAsClueNotFact')

for key, src in (
    ('tasks', CT.TASKS),
    ('causeEdges', CT.CAUSE_EDGES),
    ('rejectedEdges', CT.REJECTED_EDGES),
    ('states', CT.STATES),
    ('knowledgeGaps', CT.KNOWLEDGE_GAPS),
    ('foreshadows', CT.FORESHADOWS),
    ('notForeshadows', CT.NOT_FORESHADOWS),
    ('worldSettings', CT.WORLD_SETTINGS),
    ('notWorldSettings', CT.NOT_WORLD_SETTINGS),
    ('themeReadings', CT.THEME_READINGS),
    ('textualNotes', CT.TEXTUAL_NOTES),
    ('unknowns', CT.UNKNOWNS),
    ('selfCritique', CT.SELF_CRITIQUE),
):
    CAND[key] = walk_resolve(src, '$.' + key)

CAND['selfCritiqueNote'] = CT.SELF_CRITIQUE_NOTE


# ── 结构校验 ───────────────────────────────────────────────────────────
FIVE = ('objective', 'obstacle', 'action', 'result', 'cost')


def collect_refs(o, acc):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o:
            acc.append(o)
        else:
            for v in o.values():
                collect_refs(v, acc)
    elif isinstance(o, list):
        for v in o:
            collect_refs(v, acc)


task_collisions = []
same_para_spans = []
for t in CAND['tasks']:
    spans = []
    for f in FIVE:
        col = t.get(f)
        if not col:
            continue
        refs = []
        collect_refs(col, refs)
        for r in refs:
            if r.get('start') is not None:
                spans.append((r['start'], r['end'], f, r.get('para')))
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b, fa, _pa = spans[i]
            c, d, fb, _pb = spans[j]
            if a < d and c < b:
                task_collisions.append((t['id'], fa, fb, a, b, c, d))
    # 同段不同栏（如实报数，不判失败：判定用字符区间是否相交）
    bypara = {}
    for a, b, f, p in spans:
        bypara.setdefault(p, set()).add(f)
    for p, fs in bypara.items():
        if len(fs) > 1 and p is not None:
            same_para_spans.append({'task': t['id'], 'para': p,
                                    'fields': sorted(fs),
                                    'note': '同一自然段内被两个以上栏位引用（分句不同、字符区间不相交）'})

if task_collisions:
    for tid, fa, fb, a, b, c, d in task_collisions:
        problems.append('五栏区间重叠：%s 的 %s 与 %s（[%d,%d) vs [%d,%d)）'
                        % (tid, fa, fb, a, b, c, d))

null_without_note = []
null_fields = 0
null_slots = []
for t in CAND['tasks']:
    for f in FIVE:
        if t.get(f) is None:
            null_fields += 1
            null_slots.append('%s.%s' % (t['id'], f))
            if not t.get(f + 'Note'):
                null_without_note.append('%s.%s' % (t['id'], f))
if null_without_note:
    problems.append('null 栏缺 Note：%s' % null_without_note)
CAND['nullFieldRule'] = CT.NULL_FIELD_RULE_TEMPLATE % (null_fields, ' / '.join(null_slots))

REQUIRED_SECTIONS = ['tasks', 'causeEdges', 'states', 'foreshadows', 'worldSettings', 'themeReadings']
missing_sections = [k for k in REQUIRED_SECTIONS if k not in CAND]
if missing_sections:
    problems.append('内容分区缺失：%s' % missing_sections)

# worldSettings 三态字段
ws_shape = []
for w in CAND['worldSettings']:
    wid = w.get('id')
    if w.get('kind') == 'place':
        if w.get('placeState') not in ('arrived', 'mentioned'):
            ws_shape.append('%s placeState=%r' % (wid, w.get('placeState')))
    elif w.get('kind') == 'item':
        st = w.get('itemStates')
        if not (isinstance(st, list) and st and all(x in ('hold', 'transfer', 'use', 'lose') for x in st)):
            ws_shape.append('%s itemStates=%r' % (wid, st))
    elif w.get('kind') == 'rule':
        if w.get('institution') not in ('declared', 'executed', 'misunderstood'):
            ws_shape.append('%s institution=%r' % (wid, w.get('institution')))
    else:
        ws_shape.append('%s kind=%r' % (wid, w.get('kind')))
if ws_shape:
    problems.append('worldSettings 三态字段非法：%s' % ws_shape)

# worldSettingsNote 按实际候选回填（不写死数字，免得与产物漂移）
_ws_by_kind = {}
for _w in CAND['worldSettings']:
    _ws_by_kind.setdefault(_w['kind'], []).append(_w)
_places = _ws_by_kind.get('place', [])
CAND['worldSettingsNote'] = CT.WORLD_SETTINGS_NOTE_TEMPLATE % (
    len(_ws_by_kind.get('rule', [])), len(_places), len(_ws_by_kind.get('item', [])),
    sum(1 for _w in _places if _w['placeState'] == 'arrived'),
    sum(1 for _w in _places if _w['placeState'] == 'mentioned'),
    len(_ws_by_kind.get('item', [])),
)

# themeReadings 三件套 + 条数
if len(CAND['themeReadings']) > 2:
    problems.append('themeReadings 超过 2 条：%d' % len(CAND['themeReadings']))
for th in CAND['themeReadings']:
    miss = [k for k in ('perspective', 'support', 'counter') if not th.get(k)]
    if miss:
        problems.append('%s 缺 %s' % (th.get('id'), miss))

# foreshadows: unresolved 必须写明 unresolvedWhat/Reason
for f in CAND['foreshadows']:
    if f.get('status') == 'unresolved' and not (f.get('unresolvedWhat') or f.get('unresolvedReason')):
        problems.append('%s 标 unresolved 但没写未回收的是什么' % f.get('id'))

# 行内「」逐字核验
inline_bad = []
inline_curly_nonverbatim = []


def scan_inline(o, path='$'):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o:
            return                      # 这是已解析的引用对象，不是散文
        for k, v in o.items():
            scan_inline(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan_inline(v, '%s[%d]' % (path, i))
    elif isinstance(o, str):
        for m in re.finditer(r'「([^「」]*)」', o):
            if TEXT.find(m.group(1)) < 0:
                inline_bad.append({'path': path, 'fragment': m.group(1)[:60]})
        # 散文里照抄原文的“……”片段：如实报数，不判失败（可能是节引或概念名）
        for m in re.finditer(r'“([^“”]*)”', o):
            if TEXT.find(m.group(1)) < 0:
                inline_curly_nonverbatim.append({'path': path, 'fragment': m.group(1)[:60]})



# ── 自检块 + 覆盖度（写盘前生成）─────────────────────────────────────────
allrefs = []
collect_refs(CAND, allrefs)
uniq = {r['quote'] for r in allrefs}
cov = set()
for r in allrefs:
    if r.get('start') is not None:
        cov.update(range(r['start'], r['end']))
nonspace = sum(1 for ch in SLICE if not ch.isspace())
touched = {r['para'] for r in allrefs if r.get('para')}
zero_paras = [i for i, (a, b, _t) in enumerate(PARAS, 1) if not any(o in cov for o in range(a, b))]

CAND['machineSelfCheck'] = {
    'buildScript': 'loop/state/out/read_dafeng_L3_0243.w-xiyou-0.build/build_candidate.py',
    'contentModule': 'loop/state/out/read_dafeng_L3_0243.w-xiyou-0.build/content_0243.py',
    'verifyScript': 'loop/state/out/read_dafeng_L3_0243.w-xiyou-0.build/verify_candidate.py',
    'reproduceCommand': ('python3 -B -s loop/state/out/read_dafeng_L3_0243.w-xiyou-0.build/build_candidate.py'
                         ' && python3 -B -s loop/state/out/read_dafeng_L3_0243.w-xiyou-0.build/verify_candidate.py'),
    'quoteObjectsResolved': len(allrefs),
    'uniqueQuoteStrings': len(uniq),
    'unresolvedFailures': len(problems),
    'taskFieldIntervalOverlap': len(task_collisions),
    'sameParagraphDistinctClauseSpans': same_para_spans,
    'nullFields': null_fields,
    'nullWithoutNote': len(null_without_note),
    'requiredSections': REQUIRED_SECTIONS,
    'missingSections': missing_sections,
    'worldSettingsShapeProblems': ws_shape,
    'inlineNonVerbatim': inline_bad,
    'inlineCurlyNotVerbatim': inline_curly_nonverbatim,
    'inlineCurlyNote': ('散文里照抄的“……”片段若不逐字，如实列在此处（多为节引、'
                        '概念名或"她原话"的简写），**不判失败**；'
                        '「」里的片段则必须逐字，否则拒绝写盘。'),
    'note': ('本块由构建脚本在写盘前生成；任一项判据失败则脚本以退出码 1 拒绝写出候选文件。'
             '判定【五栏独立性】用的是**字符区间两两不相交**（比"是不是同一句"更严）。'),
}

CAND['coverage'] = {
    'sliceCodepoints': E - S,
    'nonSpaceCodepoints': nonspace,
    'quoteUnionCodepoints': len(cov),
    'quoteUnionRatioOfSlice': round(len(cov) / (E - S), 4),
    'quoteUnionRatioOfNonSpace': round(len(cov) / nonspace, 4),
    'quoteIntervals': len(allrefs),
    'paragraphs': len(PARAS),
    'paragraphsTouchedByAtLeastOneQuote': len(touched),
    'zeroCoveredParagraphs': zero_paras,
    'note': ('零覆盖段落里绝大多数是排版分隔符（「..........」「------------」）与短转场句。'
             '**引文覆盖不等于语义覆盖**：本候选没有做独立语义评审。'),
}

# ── 写盘 ───────────────────────────────────────────────────────────────
# 行内「」扫描**必须在自检块也建好之后**再做：第一版把它放在建块之前，
# 于是自检块自己的 note 里那句「五栏独立性」漏出了扫描范围
# ——独立复验脚本抓到了这个缺口（B1/B2）。扫描范围要覆盖**将要写出的整个对象**。
scan_inline(CAND)
if inline_bad:
    problems.append('散文里「」片段不是逐字原文：%d 处 %s'
                    % (len(inline_bad), [b['fragment'] for b in inline_bad[:6]]))

# 漏解析检查：任何 dict 只要带字符串 quote，就必须同时带算好的 start/end。
# 这个缺口真实发生过一次：`speechAsClueNotFact` 初稿直接赋了原始 dict，
# 12 条引文因此**没有偏移**，而构建脚本当时不报错（是独立复验脚本
# 顺着"零覆盖段落"的线索才挖出来的）。判据加在这里，杜绝同类漏网。
dangling = []


def scan_dangling(o, path='$'):
    if isinstance(o, dict):
        if isinstance(o.get('quote'), str) and ('start' not in o or 'end' not in o):
            dangling.append('%s（quote=%r）' % (path, o['quote'][:40]))
            return
        for k, v in o.items():
            scan_dangling(v, '%s.%s' % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan_dangling(v, '%s[%d]' % (path, i))


scan_dangling(CAND)
if dangling:
    problems.append('有 quote 没解析成偏移（漏了 walk_resolve？）：%d 处 %s'
                    % (len(dangling), dangling[:6]))
CAND['machineSelfCheck']['danglingQuotes'] = dangling
CAND['machineSelfCheck']['inlineNonVerbatim'] = inline_bad
CAND['machineSelfCheck']['inlineCurlyNotVerbatim'] = inline_curly_nonverbatim
CAND['machineSelfCheck']['unresolvedFailures'] = len(problems)

if problems:
    print('构建失败：%d 条判据不过，**不写盘**' % len(problems))
    for p in problems[:40]:
        print('  -', p)
    sys.exit(1)

OUT.write_text(json.dumps(CAND, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('已写出 %s' % OUT)
print('引文对象 %d 个（去重后 %d 条字符串）；段 %d；非空码点覆盖 %.4f'
      % (len(allrefs), len(uniq), len(PARAS), len(cov) / nonspace))
print('五栏区间重叠 %d 处；null 栏 %d 个（全部带 Note）；同段不同栏 %d 处'
      % (len(task_collisions), null_fields, len(same_para_spans)))
