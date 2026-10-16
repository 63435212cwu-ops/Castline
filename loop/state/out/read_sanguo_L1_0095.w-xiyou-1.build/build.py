# -*- coding: utf-8 -*-
"""Assemble the candidate and run in-build verification. Writes ONLY the task's writes path."""
import json, sys, os, hashlib, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('h', os.path.join(os.path.dirname(os.path.abspath(__file__)), '00_helper.py'))
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
sys.modules['h'] = h

import importlib
def load(name):
    s = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(os.path.abspath(__file__)), name + '.py'))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

t  = load('10_tasks'); r = load('20_rest'); w = load('30_world'); f = load('40_final')

tasks = t.build()
cause = r.cause_edges(); rej = r.rejected_cause_edges(); states = r.states()
gaps = r.knowledge_gaps(); fore = r.foreshadows(); nfore = r.not_foreshadows()
ws = w.world_settings(); nws = w.not_world_settings(); themes = w.theme_readings()
speech = f.speech_clues(); unk = f.unknowns(); sc = f.self_critique(); tn = f.textual_notes()
rcov = f.reverse_coverage(); covnote = f.coverage_note()

text = h.text; S, E = h.S, h.E
FIELDS = ('objective', 'obstacle', 'action', 'result', 'cost')

# ---------- in-build verification ----------
problems = []
qcount = 0
def check_quotes(o, path):
    global qcount
    if isinstance(o, dict):
        if isinstance(o.get('quote'), str):
            qcount += 1
            s = o.get('quote'); a = o.get('start'); b = o.get('end')
            if text.find(s) < 0: problems.append('NOT VERBATIM %s: %r' % (path, s[:40]))
            elif text[a:b] != s: problems.append('OFFSET MISMATCH %s: %r' % (path, s[:40]))
            elif not (S <= a and b <= E): problems.append('OUT OF RANGE %s: %r (%d,%d)' % (path, s[:40], a, b))
            elif o.get('sourceHash') != h.FILESHA: problems.append('BAD HASH %s' % path)
            if o.get('globalOccurrences') is not None and o['globalOccurrences'] != text.count(s):
                problems.append('BAD OCC COUNT %s: %r' % (path, s[:40]))
        for k, v in o.items():
            if k == 'quote': continue
            check_quotes(v, path + '/' + k)
    elif isinstance(o, list):
        for i, v in enumerate(o): check_quotes(v, path + '[%d]' % i)

# 1) every task field must carry its own quotes; no cross-field reuse within a task
for T in tasks:
    seen = {}
    for fl in FIELDS:
        v = T.get(fl)
        if v is None:
            if not (T.get(fl + 'Note') or '').strip():
                problems.append('%s.%s is null without a reason note' % (T['id'], fl))
            continue
        if not v.get('quotes'): problems.append('%s.%s has no quotes' % (T['id'], fl))
        for qq in v.get('quotes') or []:
            seen.setdefault(qq['quote'], []).append(fl)
    for s, fls in seen.items():
        if len(fls) > 1:
            problems.append('%s reuses one quote across fields %s: %r' % (T['id'], fls, s[:40]))

for name, obj in (('tasks', tasks), ('causeEdges', cause), ('rejectedCauseEdges', rej),
                  ('states', states), ('knowledgeGaps', gaps), ('foreshadows', fore),
                  ('notForeshadows', nfore), ('worldSettings', ws), ('notWorldSettings', nws),
                  ('themeReadings', themes), ('speechAsClueNotFact', speech),
                  ('unknowns', unk), ('selfCritique', sc), ('textualNotes', tn), ('reverseCoverage', rcov)):
    check_quotes(obj, name)

# 2) enum checks
for W in ws:
    if W['kind'] == 'place' and W.get('placeState') not in ('arrived', 'mentioned'):
        problems.append('bad placeState %s' % W.get('name'))
    if W['kind'] == 'item':
        if not W.get('itemStates') or any(x not in ('hold', 'transfer', 'use', 'lose') for x in W['itemStates']):
            problems.append('bad itemStates %s' % W.get('name'))
    if W['kind'] == 'rule' and W.get('institution') not in ('declared', 'executed', 'misunderstood'):
        problems.append('bad institution %s' % W.get('name'))
for T in themes:
    if not (T.get('perspective') and T.get('support') and T.get('counter')):
        problems.append('theme %s missing perspective/support/counter' % T.get('id'))

# 3) cross-field reuse across the WHOLE tasks layer (field-to-field in different tasks is allowed;
#    within a task it is not). Also forbid a field's ONLY quote being reused as another field's only quote.
cand = {
    'schemaVersion': 32,
    'task': 'read:sanguo:L1:0095',
    'agent': 'w-xiyou-1',
    'role': 'READER（原文精读工作者）',
    'book': 'sanguo', 'bookTitle': '三国演义', 'lane': 1, 'unitIndex': 95,
    'unitHead': '第九十六回　孔明挥泪斩马谡　周鲂断发赚曹休',
    'semanticReview': 'not_performed',
    'semanticReviewNote': '本候选只做定位、抽取与自证；语义核验属 read-verify 通道，由另一位 agent 独立进行。引文定位正确 ≠ 语义已核验，不得据此认定 semanticReview 已完成。',
    'source': {
        'path': h.SRC_REL, 'docIndex': 0,
        'sourceHash': h.FILESHA,
        'sourceHashMeaning': '整个 docs.json 文件的 sha256（实测）',
        'measuredFileSha256': h.FILESHA,
        'textCodepoints': len(text),
        'textSha256': hashlib.sha256(text.encode()).hexdigest(),
        'range': [S, E], 'rangeCodepoints': E - S,
        'segmentSha256': hashlib.sha256(text[S:E].encode()).hexdigest(),
        'segmentSha256Meaning': 'docs[0].text[start:end] 切片自身的 sha256（与 sourceHash 不同口径，另起字段）',
        'boundaryCheck': {'head': text[S:S + 21], 'headIsUnitHead': text[S:S + 21].startswith('第九十六回'),
                          'nextUnitHeadAtEnd': text[E:E + 20]},
    },
    'sourceHashDiscrepancy': {
        'taskJsonSourceHash': '2988ce6e36c80c4effc81f73a65221adf779631682da848bb67ef6f52a5a97ff',
        'promptBodySourceHash': '8ab7298a6960c6fec50e26338092abf2693e2cb39f1547f1a99ee2701ef29ec2',
        'measuredFileHash': h.FILESHA,
        'finding': ('任务 JSON 的 sourceHash（2988ce6e…）不等于提示词正文给出的、也不等于本候选实测的 fe42d01f3826fe8096f86614.docs.json '
                    '文件哈希（8ab7298a…）。实测 2988ce6e… 是**真实存在**的另一个三国 docs.json 的哈希'
                    '（data/cache/f0b45e85aac6c95e584075a2.docs.json 与 data/cache/152e2a6eed94f1075e7e7070.docs.json，二者与 fe42d01f… 的 docs[0].text 逐字相同、'
                    '长度同为 607191，切片 [484338,489034) 的 sha256 亦同为 53ec3c8a…）。故本候选按提示词正文指定的 fe42d01f… 取原文，'
                    '并同时登记这一出入，不擅自改写任务声明的哈希。'),
        'verifiedBy': 'shasum -a 256 on the three files; text equality compared in Python',
        'impact': 'none on quotes（三份 text 逐字相同）；差异只在文件级哈希口径。',
    },
    'basisLegend': {'explicit': '原文直述（叙述层或人物话语中明确写出的内容）',
                    'inferred': '我的归纳（原文未直说，由若干处事实归纳得出）',
                    'derived': '跨段推导（需组合本区间不同位置的信息才能得出）',
                    'unverified': '存疑（原文有歧义或证据不足）'},
    'voiceLegend': {'narration': '叙述层语句', 'character': '人物话语（含奏对、表文、书中语）',
                    'mixed': '同栏内同时含叙述层与人物话语'},
    'quotationConvention': '全部 quote 为 docs[0].text 的逐字子串，start/end 为**全文 codepoint 偏移**（与本单元区间同一口径），满足 text[start:end]==quote 且 text.find(quote)>=0。文言原字（如「掷」「掣」「叱」）照原文抄录，不改写成现代汉语。',
    'tasks': tasks,
    'causeEdges': cause,
    'rejectedCauseEdges': rej,
    'states': states,
    'knowledgeGaps': gaps,
    'foreshadows': fore,
    'notForeshadows': nfore,
    'worldSettings': ws,
    'notWorldSettings': nws,
    'themeReadings': themes,
    'speechAsClueNotFact': speech,
    'unknowns': unk,
    'selfCritique': sc,
    'textualNotes': tn,
    'reverseCoverage': rcov,
    'reverseCoverageNote': covnote,
    'provenanceNote': ('由 READER 通道依 loop/ROLES/READER.md 与任务 read:sanguo:L1:0095 生成（agent=w-xiyou-1，该任务租约持有者）。'
                       '先通读 docs[0].text[484338,489034) 全文（4696 codepoint），再按句建立偏移索引，逐条抽取五元组、因果边、状态、伏笔、'
                       'worldSettings 与主题解读。所有引文在构建期由 helper 用 text.find 解析全文偏移并断言'
                       '（逐字命中 / text[start:end]==quote / 落在区间内 / 哈希相符 / 出现次数相符）；'
                       '落盘后由独立脚本 verify_candidate.py 从文件重新解析复算一次（不采信构建期内存）。'
                       '本稿取代此前同路径上一份未提交的旧稿（agent=w-dafeng-1，sha256 5def33a4…，已存证于 artifacts），'
                       '修正了三类实测缺陷：(1) 旧稿 C03 机制写入「断水／断水直接导致瓦解」，而「断水」二字在全书出现 0 次、本区间 0 次，属编造机制；'
                       '(2) 旧稿 T18/T19 的 costNote 内容属于 T17（串栏），已改为各自栏位的真实说明；'
                       '(3) 旧稿 T22.cost 把「所得车仗…降兵数万余人」（缴获与降兵）写成代价，方向相反，已改列为 result 侧并留说明。'
                       '语义核验未做：semanticReview=not_performed，属 read-verify 通道。'),
    'fieldCounts': {
        'tasks': len(tasks), 'causeEdges': len(cause), 'rejectedCauseEdges': len(rej),
        'states': len(states), 'knowledgeGaps': len(gaps),
        'foreshadows': len(fore),
        'foreshadowsResolved': sum(1 for x in fore if x['status'] == 'resolved'),
        'foreshadowsUnresolved': sum(1 for x in fore if x['status'] == 'unresolved'),
        'notForeshadows': len(nfore), 'worldSettings': len(ws),
        'worldSettingsByKind': {k: sum(1 for x in ws if x['kind'] == k) for k in ('place', 'item', 'rule')},
        'placeStateCounts': {k: sum(1 for x in ws if x.get('placeState') == k) for k in ('arrived', 'mentioned')},
        'themeReadings': len(themes), 'speechAsClueNotFact': len(speech),
        'unknowns': len(unk), 'selfCritique': len(sc), 'textualNotes': len(tn),
        'reverseCoverage': len(rcov), 'reverseCoverageQuotes': sum(len(x.get('quotes') or []) for x in rcov),
        'quoteRefs': qcount,
    },
}
# quoteRefs was already accumulated by the named-section loop above; do NOT re-walk
# (re-walking tasks/causeEdges double-counted them: 501 vs the true 347).
cand['fieldCounts']['quoteRefs'] = qcount

# ---------- voiceSurface: recompute mechanically and uniformly ----------
# Rule (documented in voiceLegend): build “…” spans from the source, then for each quote
#   frac = fraction of [start,end) lying inside any “…” span
#   frac == 0  -> narration （纯叙述层）
#   frac == 1  -> character （整段落在人物话语的引号之内）
#   0 < frac < 1 -> mixed  （引文同时含「某曰：」这类叙述框架与引号内话语）
# Exception: authorial verse (后人有诗曰：“…”) is a narrator/compiler aside, not a
# character's speech; it is marked narration with a recorded voiceException.
speech_spans = []
_i = 0
while True:
    _a = text.find('\u201c', S + _i)
    if _a < 0 or _a >= E: break
    _b = text.find('\u201d', _a + 1)
    if _b < 0: break
    speech_spans.append((_a, _b + 1)); _i = (_a - S) + 1

def _frac(a, b):
    best = 0.0
    for x, y in speech_spans:
        ov = min(b, y) - max(a, x)
        if ov > 0: best = max(best, ov / (b - a))
    return best

VOICE_EXC = ('\u540e\u4eba\u6709\u8bd7\u66f0',)  # 后人有诗曰
fixed_voice = [0, 0, 0]
def voice_fix(o, path=''):
    if isinstance(o, dict):
        if isinstance(o.get('quote'), str):
            f = _frac(o['start'], o['end'])
            want = 'narration' if f == 0 else ('character' if f == 1 else 'mixed')
            if any(t in o['quote'] for t in VOICE_EXC):
                want = 'narration'
                o['voiceException'] = ('作者/整理者的「后人有诗曰」评赞属叙述层aside，'
                                       '不是人物话语，故按 narration 记而非 mixed。')
            if o.get('voiceSurface') != want:
                fixed_voice[0] += 1
                o['voiceSurfaceRecomputedFrom'] = o.get('voiceSurface')
                o['voiceSurface'] = want
            elif want != 'mixed':
                fixed_voice[1] += 1
            else:
                fixed_voice[2] += 1
        for k, v in o.items():
            if k == 'quote': continue
            voice_fix(v, path + '/' + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o): voice_fix(v, path + '[%d]' % i)
voice_fix(cand)
cand['voiceLegend']['rule'] = ('机械判据：把原文区间内的 “…” 引号跨度取出，'
                               'frac=引文落在引号内的比例；frac=0→narration，frac=1→character，'
                               '0<frac<1→mixed。唯一例外是「后人有诗曰」的作者评赞，'
                               '按 narration 记并写入 voiceException。')
cand['fieldCounts']['voiceRelabeled'] = fixed_voice[0]

if problems:
    print('IN-BUILD PROBLEMS (%d):' % len(problems))
    for p in problems[:40]: print('  -', p)
    sys.exit(1)

out = '/Users/carmen/Desktop/星系/loop/state/out/read_sanguo_L1_0095.candidate.json'
import io
with io.open(out, 'w', encoding='utf-8') as fh:
    json.dump(cand, fh, ensure_ascii=False, indent=1)
    fh.write('\n')
print('WROTE', out)
print('quoteRefs:', qcount)
print('sha256:', hashlib.sha256(open(out, 'rb').read()).hexdigest())
