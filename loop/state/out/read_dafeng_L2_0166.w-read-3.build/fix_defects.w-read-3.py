# -*- coding: utf-8 -*-
"""定点修 7 处**可用原文逐字证伪**的散文断言错误。

为什么不重新生成整份候选：现有候选的 234 个引文对象已全部逐字回验通过
（偏移/长度/区间/出现次数/首现位置/段号/哈希），重新生成会把这些已验证的
偏移置于风险中；缺陷全部是**散文层的计数与措辞**，与引文层无关，故定点替换。

每处替换都先断言「旧串唯一存在」，替换后由 scan_claims + verify_candidate 复算；
任一断言失败即抛错、不写盘。
"""
import json, hashlib, sys, io

CAND = 'loop/state/out/read_dafeng_L2_0166.candidate.json'
SRC  = 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
S, E = 594977, 599088

text = json.load(open(SRC))[0]['text']
seg  = text[S:E]
doc  = json.load(open(CAND))

# (定位路径, 旧串, 新串, 依据)
FIXES = [
 # D1  F3.payoff：宅子实际 4 次（候选自己的 unknowns/11 与 numericClaims 都写 4，此处写 2，自相矛盾）
 ("foreshadows/2/payoff",
  "「宅子」在本区间出现两次（p42 购置房产的由头、p97 提议），都不是到达。",
  "「宅子」在本区间出现四次（p9 私宅的宅子、p42 购置房产的由头、p97 提议、p98 婶婶提起），都不是到达。",
  "seg.count('宅子')==4"),

 # D2  F4.payoffNote：风水盘实际 4 次（p46 一次、p53 两次、p57 一次）
 ("foreshadows/3/payoffNote",
  "区间内「风水盘」出现三次（p46 许七安的话、p53 取出、p57 收回）",
  "区间内「风水盘」出现四次（p46 许七安的话、p53 两次：取出并绽放清光、p57 收回）",
  "seg.count('风水盘')==4"),

 # D2b numericClaims.inSlice[3].claim：结构化字段 expected=4/actual=4 本来就对，
 #     错的是**人读的那句 claim**——这正是 0162 判 partial 的形态（结构化过、散文错）。
 ("numericClaims/inSlice/3/claim",
  "「风水盘」在区间内出现三次（p46 一次、p53 两次、p57 一次）",
  "「风水盘」在区间内出现四次（p46 一次、p53 两次、p57 一次）",
  "seg.count('风水盘')==4"),

 # D3  NF4：塔姆拉哈实际 3 次（p65/p66/p68），且 p68 不与 p65/p66 同段
 ("notForeshadows/3/item",
  "「塔姆拉哈」（p65/p66，女鬼的相好、异族人）",
  "「塔姆拉哈」（p65/p66/p68，女鬼的相好、异族人）",
  "seg.count('塔姆拉哈')==3"),

 ("notForeshadows/3/why",
  "出现两次但**都在同一段证词的相邻两段内**（一次在证词里、一次是叙述对名字的注解），属于同一次引入，不是铺设＋回收；",
  "出现三次（p65 证词里、p66 叙述对名字的注解、p68 复述密谈时再次提到），三处都在同一场证词的连续段落内，属于同一次引入，不是铺设＋回收；",
  "seg.count('塔姆拉哈')==3；p65/p66/p68"),

 # D5  「抽回」不是原文用词（原文是「抽出」「收回」）。W-item-1.note 自己写着
 #     「原文动词照录：取出／收回／弹出／抽出」，W-item-3/selfCritique 却用了原文没有的「抽回」。
 ("worldSettings/9/explain",
  "操作时以黑雾形态弹出（p53）、侵入他人元神（p54）、再被「抽回」盘中（p57）",
  "操作时以黑雾形态弹出（p53）、侵入他人元神（p54）、再被「抽出」并「收回」盘中（p57）",
  "seg.count('抽回')==0；p57 原文=抽出玉指/抽出了黑雾/收回风水盘"),

 ("worldSettings/9/note",
  "原文以物待之：收在盘中、弹出、抽回）",
  "原文以物待之：收在盘中、弹出、抽出、收回）",
  "同上"),

 ("worldSettings/7/explain",
  "绽放清光、太极鱼旋转、弹出黑雾、再把黑雾抽回）",
  "绽放清光、太极鱼旋转、弹出黑雾、再把黑雾抽出并收回盘中）",
  "同上"),

 ("selfCritique/1/why",
  "以黑雾形态被「弹出」（p53）、被「抽回」（p57）",
  "以黑雾形态被「弹出」（p53）、被「抽出」并「收回」（p57）",
  "同上"),

 # D6  「晋升银锣十拿九稳」是把原文「我晋升银锣的事儿应该十拿九稳」截短后放进「」当引文
 ("tasks/2/result/note",
  "许七安据此推算「晋升银锣十拿九稳」（p79）只是他自己的打算",
  "许七安据此推算「我晋升银锣的事儿应该十拿九稳」（p79）只是他自己的打算",
  "seg.count('晋升银锣十拿九稳')==0；原文全串=我晋升银锣的事儿应该十拿九稳"),

 ("rejectedEdges/6/why",
  "许七安自己推的「晋升银锣十拿九稳」（p79）同样是心念。",
  "许七安自己推的「我晋升银锣的事儿应该十拿九稳」（p79）同样是心念。",
  "同上"),

 # D7  NW5 把「银锣」也挂到 p33/p38：原文 p33/p34/p38/p41 只有「铜锣」，「银锣」仅见 p79
 ("notWorldSettings/4/item",
  "「铜锣」「银锣」（p33/p38 许七安的职名、「我晋升银锣的事儿」p79）",
  "「铜锣」「银锣」（「铜锣」见 p33/p34/p38/p41 许七安的职名；「银锣」只出现于 p79「我晋升银锣的事儿」）",
  "银锣 在区间内仅 p79 一处；铜锣 在 p33/p34/p38/p41"),

 # D8  NW6 把「王党」挂到 p24：p24 只有「齐党」，「王党」见 p25/p35
 ("notWorldSettings/5/item",
  "「齐党」「王党」（p24/p25/p35/p75）",
  "「齐党」「王党」（「齐党」见 p24/p25/p75/p76；「王党」见 p25/p35）",
  "王党 在 p25/p35；齐党 在 p24/p25/p75/p76"),
]

def get(doc, path):
    cur = doc
    for part in path.split('/'):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur

def setv(doc, path, val):
    parts = path.split('/')
    cur = doc
    for part in parts[:-1]:
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    last = parts[-1]
    if isinstance(cur, list): cur[int(last)] = val
    else: cur[last] = val

for path, old, new, why in FIXES:
    cur = get(doc, path)
    if not isinstance(cur, str):
        raise SystemExit("FAIL 非字符串：%s (%r)" % (path, type(cur)))
    if cur.count(old) != 1:
        raise SystemExit("FAIL 旧串不唯一/不存在：%s x%d\n  %r" % (path, cur.count(old), old))
    setv(doc, path, cur.replace(old, new))
    print("FIXED %-34s  (%s)" % (path, why))

# 修完立刻复算：这些断言必须全部成立才写盘
assert seg.count('宅子') == 4
assert seg.count('风水盘') == 4
assert seg.count('塔姆拉哈') == 3
assert seg.count('抽回') == 0
assert seg.count('晋升银锣十拿九稳') == 0
assert seg.count('我晋升银锣的事儿应该十拿九稳') == 1

# 引文层不能被这次修改碰到：替换只发生在散文串里，引文对象须逐字仍成立
def walk(o):
    if isinstance(o, dict):
        if 'quote' in o and 'start' in o: yield o
        for v in o.values(): yield from walk(v)
    elif isinstance(o, list):
        for v in o: yield from walk(v)
n = 0
for q in walk(doc):
    n += 1
    if text[q['start']:q['end']] != q['quote']:
        raise SystemExit("FAIL 引文被改坏：%r" % (q['quote'][:40],))
print("引文层复核：%d/%d 仍逐字成立" % (n, n))

# 记录返工原因（提交侧要求 reworkOf 必须配 reworkReason）
doc['reworkOf'] = "loop/state/out/read_dafeng_L2_0166.w-read-3.build/prior_draft_unsubmitted.deb6065b.json"
doc['reworkReason'] = (
 "上一轮 w-read-3 写出候选但未提交（无 submit 记录）。本轮先对既有稿做**独立复算**，"
 "查出 7 处可用原文逐字证伪的散文断言错误，全部集中在**计数与措辞层**、不动引文层："
 "① foreshadows F3 说「宅子」出现两次，实为 4 次；"
 "② foreshadows F4 说「风水盘」出现三次，实为 4 次；"
 "③ numericClaims.inSlice[3] 的 claim 句同样写「三次」（其 expected/actual 字段本来就是 4，"
 "错的是人读的那句 —— 与 0162 被判 partial 的形态相同：结构化字段过、散文错）；"
 "④ notForeshadows NF4 说「塔姆拉哈」出现两次且「都在相邻两段内」，实为 3 次（p65/p66/p68）；"
 "⑤ W-item-3/W-item-1/selfCritique 用原文没有的动词「抽回」当引文（原文是「抽出」「收回」，"
 "seg.count('抽回')==0），与本候选 W-item-1.note 自述的「原文动词照录」自相矛盾；"
 "⑥ tasks T3 与 rejectedEdges R7 把「我晋升银锣的事儿应该十拿九稳」截短成「晋升银锣十拿九稳」当引文；"
 "⑦ notWorldSettings NW5/NW6 的段号归属错（「银锣」只出现于 p79，却挂到 p33/p38；"
 "「王党」见 p25/p35，却挂到 p24）。"
 "修法：逐处定点替换（替换前断言旧串唯一存在、替换后复算计数并全量回验 234 个引文对象），不重新生成，"
 "以免把已验证的偏移置于风险中。"
)
doc.setdefault('machineSelfCheck', {})['reworkNote'] = (
 "本轮为返工：修 7 处散文层计数/措辞错误，引文层 234 个对象未改动、仍逐字成立。"
)

out = json.dumps(doc, ensure_ascii=False, indent=1)
with open(CAND, 'w', encoding='utf-8') as fh:
    fh.write(out + "\n")
print("WROTE", CAND)
print("sha256", hashlib.sha256(open(CAND,'rb').read()).hexdigest())
