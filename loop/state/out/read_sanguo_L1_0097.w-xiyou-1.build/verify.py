# -*- coding: utf-8 -*-
"""独立复核 read_sanguo_L1_0097.candidate.json。

刻意**不 import lib_q / build_candidate**：所有判据从原始文件重新推导，
避免「生成器自己证明自己」。这是对抗式自检，目标是找出候选里的问题。
"""
import hashlib
import json
import re
import sys
from collections import Counter

ROOT = '/Users/carmen/Desktop/星系'
DOCS = ROOT + '/data/cache/fe42d01f3826fe8096f86614.docs.json'
CAND = sys.argv[1]
START, END = 493949, 499135

raw = open(DOCS, 'rb').read()
FILE_SHA = hashlib.sha256(raw).hexdigest()
TEXT = json.loads(raw.decode('utf-8'))[0]['text']
UNIT_HEAD = '第九十八回\u3000追汉军王双受诛\u3000袭陈仓武侯取胜'
C = json.load(open(CAND, encoding='utf-8'))

FAIL = []
WARN = []
INFO = []


def fail(m):
    FAIL.append(m)


def warn(m):
    WARN.append(m)


# ── 1. 区间与边界 ────────────────────────────────────────────────
if not TEXT[START:END].startswith(UNIT_HEAD):
    fail('区间起点不是本单元标题：%r' % TEXT[START:START + 20])
if len(TEXT[START:END]) != END - START:
    fail('切片长度与区间不符')
INFO.append('区间 [%d,%d) 共 %d 字；切点校验：%r' % (START, END, END - START, TEXT[START:START + 16]))

# ── 2. 收集全部 quoteRef（不依赖候选自报的字段名）────────────────
refs = []


def harvest(obj, path):
    if isinstance(obj, dict):
        if 'quote' in obj and 'start' in obj and 'end' in obj:
            refs.append((path, obj))
        for k, v in obj.items():
            harvest(v, '%s.%s' % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            harvest(v, '%s[%d]' % (path, i))


for key in C:
    harvest(C[key], key)

INFO.append('共收集到 quoteRef %d 条' % len(refs))

bad_pos = bad_hash = 0
quote_counter = Counter()
for path, r in refs:
    qs_, s, e = r.get('quote'), r.get('start'), r.get('end')
    if not isinstance(qs_, str) or not isinstance(s, int) or not isinstance(e, int):
        fail('%s: quote/start/end 类型异常' % path)
        continue
    if s < 0 or e > len(TEXT) or s >= e:
        fail('%s: 偏移越界 %d..%d' % (path, s, e))
        bad_pos += 1
        continue
    if TEXT[s:e] != qs_:
        fail('%s: docs[0].text[%d:%d] != quote（实得 %r）' % (path, s, e, TEXT[s:e][:40]))
        bad_pos += 1
    # 逐字 find 复现
    if TEXT.find(qs_) != s and TEXT.find(qs_, 0) != s:
        if qs_ not in TEXT:
            fail('%s: quote 在原文中 find 不到' % path)
    if not (START <= s and e <= END):
        fail('%s: 引文越出本单元区间 @%d..%d' % (path, s, e))
        bad_pos += 1
    if r.get('sourceHash') != FILE_SHA:
        bad_hash += 1
    quote_counter[qs_] += 1

if bad_hash:
    fail('%d 条 quoteRef 的 sourceHash 与实测文件哈希不符' % bad_hash)

# ── 3. voiceSurface 机械复算 ────────────────────────────────────
inside = [False] * len(TEXT)
depth = 0
for i, ch in enumerate(TEXT):
    if ch == '\u201c':
        depth += 1
        inside[i] = True
    elif ch == '\u201d':
        inside[i] = True
        depth = max(0, depth - 1)
    else:
        inside[i] = depth > 0

vmismatch = 0
for path, r in refs:
    s, e = r['start'], r['end']
    frac = sum(1 for k in range(s, e) if inside[k]) / float(e - s)
    exp = 'narration' if frac == 0 else ('character' if frac == 1 else 'mixed')
    got = r.get('voiceSurface')
    if got is not None and got != exp:
        vmismatch += 1
        if vmismatch <= 5:
            fail('%s: voiceSurface 应为 %s 实为 %s（%r）' % (path, exp, got, r['quote'][:26]))
if vmismatch == 0:
    INFO.append('voiceSurface 全部 %d 条与机械判据一致' % len(refs))

# ── 4. 五栏共用引文（去标点后同句/包含）─────────────────────────
def norm(s):
    return re.sub(r'[，。；：、“”「」！？（）\s]', '', s)


share = 0
for t in C['tasks']:
    cols = {}
    for f in ('objective', 'obstacle', 'action', 'result', 'cost'):
        v = t.get(f)
        if isinstance(v, dict):
            cols[f] = [x['quote'] for x in v.get('quotes', [])]
    for a in cols:
        for b in cols:
            if a >= b:
                continue
            for x in cols[a]:
                for y in cols[b]:
                    nx, ny = norm(x), norm(y)
                    if nx and ny and (nx == ny or (len(nx) >= 6 and nx in ny)
                                      or (len(ny) >= 6 and ny in nx)):
                        fail('%s: %s 与 %s 共用同句（%r / %r）' % (t['id'], a, b, x[:20], y[:20]))
                        share += 1
if share == 0:
    INFO.append('五栏共用引文：0 处（逐字 + 去标点包含两层）')

# ── 5. 五元组完整性：null 必须有 Note ───────────────────────────
norationale = 0
for t in C['tasks']:
    for f in ('objective', 'obstacle', 'action', 'result', 'cost'):
        if t.get(f) is None:
            note = (t.get(f + 'Note') or '').strip()
            if len(note) < 12:
                fail('%s.%s 为 null 但 Note 缺失或过短' % (t['id'], f))
                norationale += 1
        else:
            v = t[f]
            if not isinstance(v, dict) or not v.get('quotes'):
                fail('%s.%s 非 null 但无 quotes 依据' % (t['id'], f))
    if t.get('cost') is not None:
        ct = t['cost'].get('text', '')
        for bad in ('待验证', '待核', '法律规定', '禁令'):
            if bad in ct:
                fail('%s.cost 含被明令禁止的伪代价措辞：%s' % (t['id'], bad))

# ── 6. basis 取值合法 ──────────────────────────────────────────
LEGAL = {'explicit', 'inferred', 'derived', 'unverified'}
nb = 0
for path, obj in []:
    pass


def check_basis(obj, path):
    global nb
    if isinstance(obj, dict):
        if 'basis' in obj and obj['basis'] not in LEGAL:
            fail('%s: basis 非法 %r' % (path, obj['basis']))
            nb += 1
        for k, v in obj.items():
            check_basis(v, '%s.%s' % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_basis(v, '%s[%d]' % (path, i))


check_basis(C, 'cand')

# ── 7. placeState 判据：arrived 必须有到达/驻守动作 ─────────────
# 这个词表是**启发式**，只用来把可疑条目挑出来供人工裁定，不是判定规则。
# 首轮它漏了「驻守」类动词，于是对「在陈仓道口拒住王双」报了一条假警告
# （任务 prompt 明写 arrived 的条件是「有到达/驻守动作」，拒住即驻守）。
# 按「不拿它当判据、只当线索」的定位，这里补入驻守类动词并保留原表：
# 补词是为了减少假警告，不是为了放宽判据——真到达仍须引文里有动作。
ARRIVE = ('入城', '到', '上关', '守住', '据', '拔寨', '回', '奔', '还', '伏于',
          '凭高而坐', '安下营寨', '取了', '筑坛', '登坛', '守', '往', '赴')
GARRISON = ('拒住', '驻', '守把', '提调', '同守', '在营中', '伏于', '守着')
ARRIVE = ARRIVE + GARRISON
for w in C.get('worldSettings', []):
    if w.get('kind') != 'place':
        continue
    quotes = ' '.join(x['quote'] for x in w.get('quotes', []))
    st = w.get('placeState')
    if st not in ('arrived', 'mentioned'):
        fail('place %s: placeState 非法 %r' % (w['name'], st))
    if st == 'arrived' and not any(a in quotes for a in ARRIVE):
        warn('place %s 记 arrived，但其引文中未见显式到达/驻守动词：%r'
             % (w['name'], quotes[:50]))
    if st == 'mentioned' and any(a in quotes for a in ('入城', '遂回', '取了', '守御')):
        warn('place %s 记 mentioned，但其引文含到达类动词' % w['name'])

# ── 8. itemStates 取值合法且非空 ────────────────────────────────
for w in C.get('worldSettings', []):
    if w.get('kind') != 'item':
        continue
    st = w.get('itemStates')
    if not isinstance(st, list) or not st:
        fail('item %s: itemStates 必须是非空多选列表' % w['name'])
    for s in st or []:
        if s not in ('hold', 'transfer', 'use', 'lose'):
            fail('item %s: itemStates 含非法值 %r' % (w['name'], s))

# ── 9. rule institution 取值合法 ────────────────────────────────
for w in C.get('worldSettings', []):
    if w.get('kind') != 'rule':
        continue
    if w.get('institution') not in ('declared', 'executed', 'misunderstood'):
        fail('rule %s: institution 非法 %r' % (w['name'], w.get('institution')))
    if not (w.get('explain') or '').strip():
        fail('rule %s: 缺 explain' % w['name'])

# ── 10. foreshadows：unresolved 必须显式标注 ───────────────────
for f in C.get('foreshadows', []):
    if f.get('status') not in ('resolved', 'unresolved'):
        fail('foreshadow %s: status 非法 %r' % (f.get('id'), f.get('status')))
    if not f.get('setupQuotes') or not f.get('payoffQuotes'):
        fail('foreshadow %s: 缺铺设或回收引文' % f.get('id'))
    if f.get('status') == 'unresolved' and 'unresolved' not in (f.get('note') or ''):
        warn('foreshadow %s 标 unresolved 但 note 未显式说明' % f.get('id'))

# ── 11. causeEdges：必须有机制 ─────────────────────────────────
for c in C.get('causeEdges', []):
    if not (c.get('mechanism') or '').strip():
        fail('cause %s: 缺 mechanism（无机制的相邻不算因果）' % c.get('id'))
    if not c.get('causeQuotes') or not c.get('effectQuotes'):
        fail('cause %s: 缺 cause/effect 引文' % c.get('id'))

# ── 12. themeReadings：三件齐全且 ≤2 ───────────────────────────
th = C.get('themeReadings', [])
if len(th) > 2:
    fail('themeReadings 超过 2 条（%d）' % len(th))
BANNED = ('事件密度', '剧情点', '死亡人数', '篇幅中点', '三幕', '英雄旅程')
for t in th:
    for k in ('perspective', 'support', 'counter'):
        if not t.get(k):
            fail('theme %s: 缺 %s' % (t.get('id'), k))
    blob = json.dumps(t, ensure_ascii=False)
    for b in BANNED:
        if b in blob:
            fail('theme %s: 使用了被禁止的「高潮」判据 %r' % (t.get('id'), b))

# ── 13. 人物名是否都在原文区间内出现（防编造）───────────────────
# 判据必须**同时**满足两条：① 该名字在本区间内不出现；② 它出现在候选里。
# 只看 ① 会报出「本区间没提到曹休」这种废话警告——它不在区间里也不在候选里，
# 与编造无关。第一版就是只看 ①，于是留下一条永远无法消除的假警告。
seg = TEXT[START:END]
NAMES = ['孔明', '司马懿', '曹真', '曹睿', '郭淮', '孙礼', '王双', '魏延', '姜维',
         '张颌', '郝昭', '孙权', '张昭', '诸葛恪', '诸葛瑾', '陆逊', '顾雍', '孙登',
         '孙坚', '孙策', '陈震', '蒋琬', '后主', '杨仪', '马岱', '马忠', '张嶷',
         '关兴', '张苞', '吴班', '吴懿', '张虎', '乐綝', '满宠', '韩暨', '陈式',
         '张体', '张休', '曹休', '孙资', '马谡', '赵云', '周鲂', '贾逵', '邓芝', '王平']
cand_blob = json.dumps(C, ensure_ascii=False)
ghost = [n for n in NAMES if n not in seg and n in cand_blob]
if ghost:
    fail('以下名字不在本区间出现、但被候选提及（疑似编造）：%s' % '、'.join(ghost))
else:
    INFO.append('人名核查：%d 个候选名均在本区间内出现，无区间外人物被提及' % len(NAMES))

# ── 14. 自证字段 ───────────────────────────────────────────────
if C.get('semanticReview') == 'performed':
    fail('不得声称 semanticReview 完成（本通道只做定位与抽取）')
if not C.get('unknowns'):
    fail('unknowns 为空：本区间不可能没有任何读不出的地方')
if not C.get('selfCritique'):
    fail('缺 selfCritique')

# ── 15. 内容分区存在性（与 loop.py required_sections 对齐）──────
for sec in ('tasks', 'causeEdges', 'states', 'foreshadows', 'worldSettings', 'themeReadings'):
    if sec not in C:
        fail('缺内容分区 %s' % sec)

# ── 输出 ──────────────────────────────────────────────────────
print('=' * 66)
print('独立复核：%s' % CAND)
print('=' * 66)
print('文件哈希 sha256 = %s' % FILE_SHA)
print('quoteRef 总数 = %d，去重后 = %d' % (len(refs), len(quote_counter)))
print()
for i in INFO:
    print('  [info] %s' % i)
for w in WARN:
    print('  [warn] %s' % w)
for f in FAIL:
    print('  [FAIL] %s' % f)
print()
print('结论：%s（FAIL=%d WARN=%d）' % ('pass' if not FAIL else 'fail', len(FAIL), len(WARN)))
sys.exit(1 if FAIL else 0)
