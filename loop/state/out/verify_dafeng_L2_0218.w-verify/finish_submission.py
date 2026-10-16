# -*- coding: utf-8 -*-
"""把复核结论补成 loop 可提交的记录形态：现算 evidence 哈希 + 必填字段。"""
import json, hashlib, glob, os
from pathlib import Path
ROOT = Path('/Users/carmen/Desktop/星系')
V = ROOT/'loop/state/out/verify_dafeng_L2_0218.verdict.json'
CAND = ROOT/'loop/state/out/read_dafeng_L2_0218.candidate.json'
DOCS = ROOT/'data/cache/1063b17ca65ec1b76f30e460.docs.json'
BUILD = ROOT/'loop/state/out/read_dafeng_L2_0218.w-sanguo-0.build'
AGENT = 'w-verify-1'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

v = json.loads(V.read_text(encoding='utf-8'))

# ── 身份与任务（submit/verify 都要）────────────────────────────────────
v['task'] = 'verify:dafeng:L2:0218'
v['agent'] = AGENT
v['verifier'] = AGENT
v['role'] = 'VERIFIER（独立反向复核者）'
v['reviewedTask'] = 'read:dafeng:L2:0218'
v['reviewedAuthor'] = 'w-sanguo-0'
v['verifierIsNotAuthor'] = True
v['reviewedFile'] = 'loop/state/out/read_dafeng_L2_0218.candidate.json'
v['reviewedSha256'] = sha(CAND)
v['status'] = 'done'

# ── 证据（现算哈希；只放**不会被本次提交改写**的稳定文件）──────────────
scripts = sorted(glob.glob(str(ROOT/'loop/state/out/verify_dafeng_L2_0218.w-verify'/'*')))
v['evidence'] = [
    {'path': str(Path(p).relative_to(ROOT)), 'sha256': sha(p),
     'what': '复核者自写的独立核验脚本'}
    for p in scripts
] + [
    {'path': 'data/cache/1063b17ca65ec1b76f30e460.docs.json', 'sha256': sha(DOCS),
     'what': '原文（只读输入；整个 docs.json 的 sha256，与任务 sourceHash 一致）'},
]

v['sourceHashes'] = {
    'loop/state/out/read_dafeng_L2_0218.candidate.json': sha(CAND),
    'data/cache/1063b17ca65ec1b76f30e460.docs.json': sha(DOCS),
    'loop/state/out/read_dafeng_L2_0218.w-sanguo-0.build/build_candidate.py': sha(BUILD/'build_candidate.py'),
    'note': ('前两项为只读审阅对象，动手前后各取一次、哈希未变（候选 873d53b1…、docs fdde5558…）。'
             '第三项是**他人**的构建脚本，我只在 /tmp 隔离沙箱里跑过它、未改写；'
             '若原作者日后再动它，本条会漂移并触发重做 —— 如实登记这个代价。'
             '**未列入** loop/state/out/read_dafeng_L2_0218.json：本次 verify 会向它追加 review，'
             '列入会让它其后必然被判证据失效（0214 的同类条目即因此 hash-changed）。'),
}

v['changes'] = []   # 只读复核，未改任何文件（唯一写入是本复核文件自身）

v['assertions'] = [
  {'text': '原文切片自检：shasum -a 256 data/cache/1063b17ca65ec1b76f30e460.docs.json = fdde5558…39839（与任务 sourceHash 一致）；'
           'docs[0].text[813350:817425] 以『第两百一十七章 许七安：我爽了』开头、长 4075、切片 sha256 = ed544184…1cd5b1（与候选声明相等）。',
   'result': 'pass'},
  {'text': '引用层全量复算（194/194，非抽样）：docs[0].text[start:end]==quote、逐条 t.find(quote)==start、全部落在 [813350,817425)、'
           'wholeTextOccurrences / occurrencesInRange 与 str.count 相符 ⇒ 0 失配。**未发现编造**。',
   'result': 'pass'},
  {'text': '随机抽 5 条 quote（random.seed(218)）在全文 find 一次：5/5 逐字命中、find == 声明的 start、长度与区间均一致。',
   'result': 'pass'},
  {'text': '候选 9 条机器判据**由复核者重写后复现**（不采信候选自报）：判据 1/2/3/4/5/6/7/9 结果全部一致。'
           '判据 3 我用字符区间与句单元两套口径重算，0 冲突；判据 7 我按 JSON 全文重扫得 272 对（候选自报只扫正文 250 对），两种口径下非逐字命中均为 0。',
   'result': 'pass'},
  {'text': '覆盖率独立复算：quoteUnion 3451 / nonSpace 3493 / ratio 0.9880 / 非空段 98 / 零覆盖段 [P000,P066,P072,P089,P095,P097]，'
           '与候选声明逐项相等；未覆盖的 42 字全是标题行、1 个孤立『？』与 4 处分隔符，无内容性遗漏。',
   'result': 'pass'},
  {'text': 'reproduce 声明核验：把候选 build/ 与两份 cache 拷进 /tmp/repro_sandbox_0218（沙箱内 __file__ parents[4] 自然指向沙箱），'
           '跑 build_candidate.py 后与真候选 **cmp 逐字节相同**（873d53b1…）。未在仓库内跑它、未触碰任何受保护路径。',
   'result': 'pass'},
  {'text': 'CE1（与原文相反 + 候选自相矛盾，可逐字引证）：K1.whoDoesNotKnow 写『许七安——他在群里是提问的一方，结论由四号给出』，'
           '但原文直述『司天监的术士？许七安吃了一惊。』（find=814792，逐字）；且 K1.whoKnows[0] 已把『三号追问』列为知情者、'
           'K2.what 又写『三号』就是许七安本人 ⇒ 同一条知识差里同一人同时知与不知。',
   'result': 'fail'},
  {'text': 'CE2（推测塞进 basis=explicit 的 explain）：W05.explain 称换房间把在场者『从四个人缩到三个——苏苏、宋廷风、朱广孝都被留在外面』；'
           '全区间检索『留在外面』『都在外面』『在外面』均 0 次命中，原文只点名请了『宁宴』一人。placeState=arrived 本身成立。',
   'result': 'fail'},
  {'text': '反向验证 R1–R6（本轮主产出）：逐段重扫后确认至少 6 条原文明确存在、候选未覆盖的事实；'
           '其中 RC1（P014→P015→P016 完整问答链，三段 paraLabel 在全部 causeEdges/rejectedEdges 里 0 次出现）与 '
           'RC2（一号自陈偏向第二种可能，只被当作『账簿证据不足』的拒收说明）最实质。',
   'result': 'fail'},
  {'text': '误杀检查：定向查了本区间最可能被词表/正则误杀的合法内容 —— 一号的『官场规矩』与四号的咒杀/算卦门槛'
           '（既非诏令也非执行，只以人物言语存在）。候选都按 institution=misunderstood 收下并写了 explain ⇒ **未发现误杀**。',
   'result': 'pass'},
  {'text': '幻觉/越权检查：把候选全部非 quote 字符串与区间做 CJK 2..5-gram 差集，逐个人名/地名/事件名回原文 find ⇒ '
           '0 个原文没有的人物、0 个原文没有的事件、0 个原文没有的结局、0 处把结束当成功（五条 cost 全 null 且各自写了理由）。',
   'result': 'pass'},
  {'text': '复核者自查（如实记录两处我自己的错）：VS1 我第一版句单元判据漏了『：』为句界，误报 T5 一处冲突，加回后归零；'
           'VS2 我一度把『道门天宗/游骑将军』当编造，复查后降级为『证据越界』（这两个词在全书正文存在、只是不在本区间）。'
           'VS3 我的 knows/notknow 扫描器用子串包含，报出 5 个假阳性，只保留可逐字引证的三号/许七安这一对。',
   'result': 'pass'},
]

v['remaining'] = [
  'CE1 需原作者改写 K1.whoDoesNotKnow 的『许七安』一项（改为『不知结论真伪』或直接删除）；同时应修掉 K1 内部『三号』既在 whoKnows 又在 whoDoesNotKnow 的矛盾。',
  'CE2 需删掉 W05.explain 里『苏苏、宋廷风、朱广孝都被留在外面』，或降级为 inferred 并注明是读者推断；W05 的 placeState=arrived 可保留。',
  'CE4 建议删除 W03 的第二条引文 P035（与本条设定无关）；主引文 P015 逐字成立、判词正确。',
  'CE3（低）建议给两个 who 里的『道门天宗』『游骑将军』标注来源为区间外设定，或删去只留『李妙真（地书群二号）』。',
  'RC1–RC6 建议至少补进 causeEdges（RC1、RC5）与 knowledgeDiffs/states（RC2、RC3、RC4）；RC4『张巡抚也熬夜』另有一种读法（泛写疲惫），故只作反向发现、未升级为反例。',
  'S4（宋廷风与朱广孝背过身去）严格说缺可确认前值（候选已在 selfCritique SC4 自陈）；若下游要求 state 必须有前值，应降级为状态快照。',
  '我未复核区间之外的原文，也未做跨单元伏笔回收判定（本区间之外的回收不在本轮范围）。图谱缓存 1063b17ca65ec1b76f30e460.json 我只用于确认 CE3 的头衔来源，未与候选逐条对照（按任务口径它不算原文证据）。',
  '本轮证据含 w-sanguo-0 的 build 目录下 build_candidate.py；若该目录日后被原作者重写，本记录该条 evidence 哈希会失效并触发重做 —— 这是把他人构建脚本纳入证据的代价，已如实登记。',
]

v['rollback'] = (
  '只读复核：未改动候选、源文件、构建脚本与任何受保护路径'
  '（js/ css/ index.html serve.py narrative.py scripts/ tests/ docs/ data/ 一字未动）。'
  '唯一写入是任务 writes 指定的 loop/state/out/verify_dafeng_L2_0218.verdict.json，'
  '以及我自己在 loop/state/out/verify_dafeng_L2_0218.w-verify/ 下的核验脚本；'
  'reproduce 用的沙箱在 /tmp/repro_sandbox_0218，与仓库无关。'
  '提交过程按既有工具追加写入 loop/state/out/read_dafeng_L2_0218.json 的 reviews，属 append-only 登记，不回退。'
)

v['summary'] = (
  '独立反向复核 verify:dafeng:L2:0218（《大奉打更人》第两百一十七章 许七安：我爽了，'
  '原文区间 [813350,817425)，4075 码点 / 98 非空段）。按 VERIFIER.md 的顺序执行：'
  '**先自己读原文**（分两屏打印切片通读，此阶段未打开候选），之后才读候选逐条比对。裁决 **partial**。'
  '机械层全量重算（非抽样）：194 条 quote 逐条 TEXT[start:end]==quote、逐条 find==声明 start、全部在区间内、'
  'sourceHash 与整个 docs.json 相符、wholeTextOccurrences/occurrencesInRange 0 失配；随机抽 5 条（seed=218）5/5 逐字命中；'
  '覆盖率 3451/3493=0.9880、98 非空段、6 个零覆盖段，逐项复算相符；把候选 build/ 拷进 /tmp 沙箱重跑，'
  '产出与真候选 **逐字节相同**。**0 编造**：没有原文没有的人物/事件/结局，没有把结束当成功，五条 cost 全 null 且理由齐备。'
  '所以我没有停在『他写的对不对』，按计划100 的教训去问『这一段他还漏了什么』，得到 RC1–RC6 六条原文明确存在、候选未覆盖的事实。'
  '**判 partial 的依据是两条可逐字引证的硬缺陷**：'
  'CE1 —— K1.whoDoesNotKnow 把许七安写成不知道『幕后可能牵到司天监的术士』，'
  '但原文直述『司天监的术士？许七安吃了一惊。』（find=814792）；这不只是与原文相反，'
  '还与**候选自己**的 K1.whoKnows[0]（『三号追问』列为知情者）和 K2.what（『三号』就是许七安本人）自相矛盾 —— '
  '同一条知识差里同一个人同时知与不知。根因是把『他是提问方』推成『他不知道答案』。'
  'CE2 —— W05.explain（basis=explicit）称换房间把苏苏、宋廷风、朱广孝『都留在外面』，'
  '但全区间检索『留在外面/都在外面/在外面』0 次命中，原文只点名请了『宁宴』一人；placeState=arrived 本身成立，'
  '但把『未被邀请』写成『被留在外面』是替原文补动作，且挂在 explicit 上会被下游当成直述。'
  '另有 CE3（两个 who 用区间外头衔『道门天宗/游骑将军』，属证据越界非编造，低）、'
  'CE4（W03 挂了一条与本设定无关的引文 P035，低）。'
  '反向验证的六条里最实质的是 RC1：二号抛苦肉计假设（P014）→ 一号用官场规矩当场驳回（P015）→ 一号自陈偏向第二种可能（P016），'
  '这三段的 paraLabel 在全部 13 条 causeEdges + 5 条 rejectedEdges 里 **0 次出现** —— 一条机制明确、正该连边的问答链被漏掉；'
  '以及 RC2：一号自己偏向哪种可能（『我个人是赞同这个猜测的』）只被当作拒收说明处理，没进任何 knowledgeDiff。'
  '误杀检查我没有走过场：本区间最可能被词表挡掉的合法内容是『官场规矩』与咒杀/算卦门槛（既非诏令也非执行、只以人物言语存在），'
  '候选都按 misunderstood 收下并写了 explain，**未发现误杀**（这正是计划100『遂行』那类误杀的反面）。'
  '**我也如实记下自己复核里的三处错**：VS1 我第一版句单元判据漏了『：』为句界、误报 T5 一处冲突（加回后归零）；'
  'VS2 我一度把区间外头衔当编造（复查后降级为证据越界）；VS3 我的 knows/notknow 扫描器用子串包含、报出 5 个假阳性，'
  '我只保留能逐字引证的三号/许七安这一对。判 partial 而非 fail，是因为 CE1/CE2 都拿得出逐字原文引证（814792、816745）、'
  '不是凭感觉否决，但它们的**影响面**限于一条知识差条目与一条 explain，'
  '任务的五栏结构、13 条因果边、13 条引文互斥、伏笔 unresolved 标注与 10 条 unknowns 主体仍可用（哪些能用/哪些必须丢见 usableAndDiscardable）。'
)

V.write_text(json.dumps(v, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('已补齐提交字段：', V)
print('evidence 条目 =', len(v['evidence']))
print('status =', v['status'], '| agent =', v['agent'], '| task =', v['task'])
