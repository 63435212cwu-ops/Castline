# -*- coding: utf-8 -*-
"""独立缺陷扫描：引文层之外**可逐字证伪**的三类散文错误。

为什么必须单列（0162 被判 partial 的根因）：
  `numericClaims` 这类**结构化字段**只覆盖候选自愿登记的条目；0162 的计数错误
  恰恰出在**散文里**（notForeshadows / notWorldSettings 的 why/item），结构化字段全对。
  所以判据必须直接扫散文，而不是只复算结构化字段。

四条规则（每条都可用原文逐字证伪，不依赖审美判断）：
  A 计数断言：「T」…(出现|命中|全书)…N次 ⇒ N 必须等于 seg.count 或 text.count。
    范围按**数字所在小句**判定（否则「在本区间…一次，全书 78 次」这类并列断言会误判）。
  B 引文归属：「T」（pNN …）⇒ T 必须能在原文 find 到。
    含省略号的 T 先按 …/.... 切成片段，逐片段要求 find 到（省略号是合法的截断写法，
    但**截短到原文没有的串**不是 —— 0162 的「交给三司」即此形态）。
  C 段号归属：「T」（pNN …）⇒ 被引的段号集合里，至少有一段真的含 T。
    支持区间写法：p68/p69、p69–p71 都算合法引用。
  D 原文措辞：在「原文/照录/以物待之/逐字」语境里的「T」⇒ T 必须 find 到
    （否则是给原文安了它没有的词）。排除箭头式自造标签（含 → ／ / 、）。

每个「跳过」都写明理由，不静默丢样本。
自证有效：对**修复前草稿**必须报警（见 B 节 run 记录），对修复后候选必须为 0。
"""
import json, re, sys

SRC  = 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
CAND = sys.argv[1] if len(sys.argv) > 1 else 'loop/state/out/read_dafeng_L2_0166.candidate.json'
S, E = 594977, 599088

text = json.load(open(SRC))[0]['text']
seg  = text[S:E]
cand = json.load(open(CAND))

paras = []; cur = S
for ln in seg.split('\n'):
    if ln.strip(): paras.append((len(paras)+1, cur, cur+len(ln), ln.strip()))
    cur += len(ln) + 1
pmap = {n: t for n, a, b, t in paras}

CN = {'一':1,'两':2,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'零':0}
def num(r): return int(r) if (r and r.isdigit()) else CN.get(r or "")

def walk(o, path=""):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o: return
        for k, v in o.items(): yield from walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from walk(v, path + "/%d" % i)
    elif isinstance(o, str):
        yield path, o

QUOTED = re.compile(r'[「“]([^」”\n]{1,40})[」”]')
LABEL  = re.compile(r'[→/／、]|^(?:被收容|失去某物|因此失去|如木偶|有这么一条)')
bad = {"A": [], "B": [], "C": [], "D": [], "E": []}
checked = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
skipped = []

def frags(t):
    """把含省略号的引文切成片段；返回需要 find 到的片段。"""
    parts = re.split(r'…+|\.{2,}|。{2,}', t)
    out = []
    for p in parts:
        p = p.strip().strip('，。；：、"').strip()
        if len(p) >= 3: out.append(p)     # <3 字的片段（「不，」等）不作为逐字要求
    return out or [t]

for p, s in walk(cand):
    if p in ('/reworkReason', '/reworkNote', '/basisLegend', '/machineSelfCheck/note'):
        skipped.append((p, '返工/图例说明，转述旧串')); continue

    # ── A ──
    for m in re.finditer(r'(?:出现|命中|全书)[^。；\n]{0,40}?([0-9]+|[一二两三四五六七八九十]+)\s*次', s):
        n = num(m.group(1))
        if n is None: continue
        best = None
        for q in QUOTED.finditer(s, 0, m.start()):
            if '。' in s[q.end():m.start()] or '；' in s[q.end():m.start()]: continue
            best = q
        if best is None: continue
        term = best.group(1)
        cstart = max(s.rfind(c, 0, m.start()) for c in '，。；\n') + 1
        clause = s[cstart:m.end()+2]
        scope = text if ('全书' in clause and '区间' not in clause) else seg
        checked["A"] += 1
        if scope.count(term) != n:
            bad["A"].append((p, term, n, scope.count(term),
                             'wholeBook' if scope is text else 'slice',
                             s[max(0,best.start()-25):m.end()+35]))

    # ── B / C ──
    # 注意：引文里可以**嵌套**原文引号（如「听到了“火炮”、“器械”等字眼」），
    # 故 [^」”] 会把内层 “ 当成结束符而截断 —— 第一版因此对 NW4 报假阳性。
    # 正确做法：外层用「…」时只认 」，外层用 “…” 时只认 ”，按起始符配对。
    for m in re.finditer(r'(?:「([^「」\n]{1,60})」|“([^“”\n]{1,60})”)\s*[（(]\s*(p[0-9p\-–—/、\s]+)', s):
        term, ref = (m.group(1) or m.group(2)), m.group(3)
        pns = [int(x) for x in re.findall(r'p(\d+)', ref)]
        if not pns: continue
        # B：逐字
        miss = [f for f in frags(term) if f not in seg]
        if miss:
            checked["B"] += 1
            bad["B"].append((p, term, miss, s[max(0,m.start()-25):m.end()+25]))
        # C：段号（区间引用里任一命中即合法）
        checked["C"] += 1
        if term in seg and not any(term in pmap.get(n, '') for n in pns):
            bad["C"].append((p, term, ref, [pmap.get(n,'')[:60] for n in pns[:3]]))

    # ── D ──
    for m in QUOTED.finditer(s):
        term = m.group(1)
        if term in seg or LABEL.search(term): continue
        win = s[max(0, m.start()-60):m.end()+40]
        if not re.search(r'原文|照录|以物待之|逐字|原话', win): continue
        if re.search(r'不等于|不是|而不是|并非', win): 
            skipped.append((p, '否定对比：' + term)); continue
        checked["D"] += 1
        bad["D"].append((p, term, s[max(0,m.start()-45):m.end()+45]))

# ── E 裸计数：条目内的「出现N次」以该条目自身的 item/name 为主语 ──────────────
# 形态来源：notForeshadows[].why 里写「出现两次但…」，句中没有引号主语，
# 主语由条目自己的 item 字段给出（如「塔姆拉哈」）。只在这类**条目自带主语**时检查，
# 避免把「两次执行动作」这类别的计数误当成词频断言。
bare = re.compile(r'出现\s*([0-9]+|[一二两三四五六七八九十]+)\s*次')
def scan_entry(entry, path):
    subj = None
    for k in ('item', 'name', 'topic'):
        v = entry.get(k)
        if isinstance(v, str):
            mm = QUOTED.search(v)
            cand_subj = mm.group(1) if mm else v
            cand_subj = cand_subj.split('（')[0].strip()
            if cand_subj and cand_subj in seg:
                subj = cand_subj; break
    if not subj: return
    for k, v in entry.items():
        if not isinstance(v, str): continue
        for m in bare.finditer(v):
            n = num(m.group(1))
            if n is None: continue
            head = v[max(0, m.start()-12):m.start()]
            if '」' in head or '”' in head: continue      # 主语已在引号里 ⇒ 规则 A 管
            # 排除**引用通用口径**的句子：如「同一物件出现两次不叫伏笔，要有铺设＋回收」
            # 是任务提示词里的判据原文，主语是「同一物件」这类泛指，不是在断言本词词频。
            st = max(v.rfind(c, 0, m.start()) for c in '，。；\n') + 1
            clause = v[st:m.end()+30]
            if re.search(r'不叫|泛指|同一物件|口径|判据|通例', clause): continue
            checked["E"] += 1
            if seg.count(subj) != n:
                bad["E"].append((path + "/" + k, subj, n, seg.count(subj),
                                 v[max(0,m.start()-30):m.end()+45]))

for i, nf in enumerate(cand.get('notForeshadows', [])):
    scan_entry(nf, "/notForeshadows/%d" % i)
for i, nw in enumerate(cand.get('notWorldSettings', [])):
    scan_entry(nw, "/notWorldSettings/%d" % i)

print("A count-assertions checked:", checked["A"])
print("B verbatim-citations checked:", checked["B"])
print("C para-citations checked:", checked["C"])
print("D original-wording checked:", checked["D"])
print("E bare-count checked:", checked["E"])
print("skipped with reason:", len(skipped))
for p, r in skipped[:12]: print("   -", p, "::", r)
total = sum(len(v) for v in bad.values())
print("DEFECTS:", total)
for k in ("A", "B", "C", "D", "E"):
    for item in bad[k]:
        print(f"\n  [{k}] {item[0]}")
        print(f"      {item[1:]}")
sys.exit(1 if total else 0)
