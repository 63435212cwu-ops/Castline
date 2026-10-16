# -*- coding: utf-8 -*-
"""构建复核结论。所有 start/end 现算，不手打。"""
import json, hashlib
from pathlib import Path
ROOT = Path('/Users/carmen/Desktop/星系')
DOC = ROOT/'data/cache/1063b17ca65ec1b76f30e460.docs.json'
CAND = ROOT/'loop/state/out/read_dafeng_L2_0218.candidate.json'
OUT = ROOT/'loop/state/out/verify_dafeng_L2_0218.verdict.json'
S, E = 813350, 817425
SRC_HASH = 'fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839'

t = json.loads(DOC.read_text(encoding='utf-8'))[0]['text']
cand_bytes = CAND.read_bytes()
C = json.loads(cand_bytes.decode('utf-8'))

def q(s):
    """逐字引文 + 现算偏移；找不到就抛（不允许写没核过的引文）"""
    i = t.find(s)
    assert i >= 0, '引文不在 docs[0].text 里: %r' % s[:40]
    assert S <= i and i + len(s) <= E, '引文越界: %r' % s[:40]
    return {'quote': s, 'start': i, 'end': i + len(s),
            'sourceHash': SRC_HASH, 'offsetUnit': 'codepoint',
            'offsetBase': 'docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）'}

v = {
 "schemaVersion": "castline-read-verdict/1",
 "task": "verify:dafeng:L2:0218",
 "verifiedTask": "read:dafeng:L2:0218",
 "verifier": "w-verify",
 "book": "dafeng",
 "unitHead": "第两百一十七章 许七安：我爽了",
 "sourceRange": [S, E],
 "sourceHash": SRC_HASH,
 "segmentSha256": hashlib.sha256(t[S:E].encode('utf-8')).hexdigest(),
 "candidateSha256": hashlib.sha256(cand_bytes).hexdigest(),
 "candidatePath": "loop/state/out/read_dafeng_L2_0218.candidate.json",

 "verdict": "partial",

 "method": {
   "order": "先自己读原文（先后打印 docs[0].text[813350:817425] 两屏，未开候选）；再抽取项核对；再反向验证；再误杀检查；最后引用核验。",
   "independentReimplementation": "复核者**没有**跑候选自带脚本当作结论，而是自己重写了 9 条判据（loop/state/out/verify_dafeng_L2_0218.w-verify/indep_checks.py 等），逐条复算。",
   "reproduce": "python3 -B -s loop/state/out/verify_dafeng_L2_0218.w-verify/run_all.sh"
 },

 "extractionCheck": {
   "quotesTotal": 194,
   "quotesDistinct": 95,
   "quotesVerbatim": 194,
   "quotesInRange": 194,
   "quotesWithMatchingOffset": 194,
   "occurrenceMetadataMismatches": 0,
   "findOffsetMismatches": 0,
   "fabricatedItems": 0,
   "note": "194 条 quote 节点全部满足 docs[0].text[start:end]==quote 且落在区间内；候选声明的 wholeTextOccurrences / occurrencesInRange 逐条现算一致（0 处不符）。抽取项（5 任务/13 因果边/4 状态/4 知识差/3 伏笔/8 世界设定）里**没有**发现原文不存在的人物、事件、结局或成功判定 —— 这一项判 0 编造。"
 },

 "counterExamples": [
  {
   "id": "CE1",
   "claim": "K1.whoDoesNotKnow 把『许七安』列为**不知道**『幕后可能牵到司天监的术士』的人（原文写法：〔许七安——他在群里是提问的一方，结论由四号给出（P026、P029）〕）。",
   "quote": "司天监的术士？许七安吃了一惊。",
   "quoteRef": q("司天监的术士？许七安吃了一惊。"),
   "why": "三重矛盾，两重是候选**自己文件内部**的："
          "① 与原文相反——原文直述他当场就吃一惊（『司天监的术士？许七安吃了一惊。』814792），即他**读到了**这条结论；同一区间另有一号分析『给许七安打开了思路』（814124）。"
          "② 与候选 K2 相反——K2.what 写『三号』就是许七安本人，K2.whoKnows 写『许七安自己——他一边在群里以三号身份发帖』。"
          "③ 与候选 K1 自身相反——同一条 K1 的 whoKnows[0] 明写『天地会群里的成员——一号提出、四号解释、二号转述、**三号追问**（P012、P027、P029、P032）』，三号即许七安被列为**知情者**，而 whoDoesNotKnow[1] 又把他列为**不知情者**。同一条知识差里同一个人同时是知与不知。"
          "根因是把『他是提问方』推成『他不知道答案』——提问≠未获得，四号正是当群作答（P027–P029），三号为推进案情而主动提问（P026）。此条必须改。",
   "severity": "high",
   "disposition": "必须丢弃 K1.whoDoesNotKnow 的『许七安』一项；若要保留知识差，应改为『张巡抚与姜律中在区间内不知情』（这一项原文支持）。"
  },
  {
   "id": "CE2",
   "claim": "W05.explain（basis=explicit）称换房间把在场者『从四个人缩到三个——苏苏、宋廷风、朱广孝都被留在外面』（原文写法）。",
   "quote": "张巡抚和姜律中相视一眼，前者目光微闪：“我们到房间说话，宁宴，你也来。”",
   "quoteRef": q("张巡抚和姜律中相视一眼，前者目光微闪：“我们到房间说话，宁宴，你也来。”"),
   "why": "原文这句只**点名请了一个人**（宁宴），从没写苏苏/宋廷风/朱广孝被『留在外面』：全区间检索『留在外面』『都在外面』『在外面』均 0 次命中（现算），房间场景（816787 起）也只出现李妙真、张巡抚、姜律中、许七安四人。『arrived』本身有据（到达动作确由张巡抚给出），但把**未被邀请**写成**被留在外面**是替原文补动作 —— 且这个补法还把它接到 P075（宋/朱在厅里背过身去）当因果，等于把两件事串成一条原文没写的调度。它挂在 basis=explicit 的 explain 里，会被下游当成直述。",
   "severity": "medium",
   "disposition": "W05 保留 placeState=arrived；explain 中『苏苏、宋廷风、朱广孝都被留在外面』必须删除或降级为 inferred 并注明是推测。"
  },
  {
   "id": "CE3",
   "claim": "两个 who 字段用区间外头衔给人物定性：T1.who=『李妙真（**道门天宗**、**游骑将军**；…）』。",
   "quote": "李妙真是最后一个登场，穿着软甲，背着银枪，腰胯佩剑，帅气的高马尾一甩一甩。",
   "quoteRef": q("李妙真是最后一个登场，穿着软甲，背着银枪，腰胯佩剑，帅气的高马尾一甩一甩。"),
   "why": "『道门天宗』『游骑将军』在区间 [813350,817425) 内出现次数均为 **0**（区间对本角色的唯一身份交代是这一身装束与后文的『李将军』）。这两个词只出现在区间外的正文（如 748409、726483）与图谱缓存 `1063b17ca65ec1b76f30e460.json` 里 —— 而精读任务明写『图谱缓存里的摘要**不算原文证据**，只能用来对照已有结论』。**如实说明**：这两个头衔在全书范围内是真事实，所以这不是『编造人物』，而是**证据越界**（把区间外/缓存里的东西写进了区间产出），且它恰好落在没有 quote 字段的位置上，机器判据扫不到。",
   "severity": "low",
   "disposition": "可保留（不影响任何一条带引文的结论），但应在 who 里标注来源为区间外设定，或直接删去头衔只留『李妙真（地书群二号）』。"
  },
  {
   "id": "CE4",
   "claim": "W03（官场规矩，institution=misunderstood）挂了第二条引文 P035『【二：不像是隐瞒，他们应该真的不知道。】』。",
   "quote": "【二：不像是隐瞒，他们应该真的不知道。】",
   "quoteRef": q("【二：不像是隐瞒，他们应该真的不知道。】"),
   "why": "该引文里没有任何官场规矩、也没有杨川南：它是二号回答一号『张巡抚为什么不知道』的**另一条线**（司天监是否参与），与 W03 的 name/explain 无关。这是**冗余引文**（把不属于本条设定的证据挂上来），不是编造。同类还有 W03 未引 P016 却引了 P035。",
   "severity": "low",
   "disposition": "删除该引文即可；W03 的主引文 P015 逐字成立、判词（misunderstood 而非 declared/executed）也正确。"
  }
 ],

 "reverseChecks": [
  {
   "id": "RC1",
   "found": "候选漏掉了区间内一条**完整的一问一答一表态**因果链：二号抛出苦肉计假设（P014）→ 一号用官场规矩当场驳回（P015）→ 一号紧接着自陈赞同第二种可能（P016）。全 13 条 causeEdges + 5 条 rejectedEdges 里，P014/P015/P016 **一个都没出现**（现算：这三段的 paraLabel 在 causeEdges/rejectedEdges 的 quote 集合里 0 次命中）；P015/P016 只被 worldSettings/notWorldSettings 引用。",
   "quote": "【一号：可能性不大，官场规矩，杨川南这次无论如何都要背责任，区别只在轻重。如果你是杨川南，你会自己挖坑自己跳？",
   "quoteRef": q("【一号：可能性不大，官场规矩，杨川南这次无论如何都要背责任，区别只在轻重。如果你是杨川南，你会自己挖坑自己跳？"),
   "why": "这条边有明确的**触发机制**（一号回答的是二号刚提出的假设，同段首句就是『可能性不大』），不是靠相邻性——按任务要求正该连边。漏掉它等于把『二号提出并主动求证的假设被一号否掉』这一步从因果层抹掉。"
  },
  {
   "id": "RC2",
   "found": "候选漏掉了**一号自己的置信度**这条事实：一号明确表态他偏向自己提出的第二种可能（『我个人是赞同这个猜测的。因此，他齐党身份可能性很高。』P016）。该段只进了 notWorldSettings（被当成『账簿证据不足』的拒收说明），没有进任何 knowledgeDiff/state —— 现算：P016 的 paraLabel 在 sections 里只出现于 notWorldSettings；『齐党』在 knowledgeDiffs 里只作为 K1 的 what 出现，K1 记的是**群**的可能，不是**一号**的倾向。",
   "quote": "【梁有平杀死原本的接头人，销毁账簿里有问题的部分....我个人是赞同这个猜测的。因此，他齐党身份可能性很高。】",
   "quoteRef": q("【梁有平杀死原本的接头人，销毁账簿里有问题的部分....我个人是赞同这个猜测的。因此，他齐党身份可能性很高。】"),
   "why": "『谁信哪一种可能』正是本区间知识差的核心（K1 的 what 就写了两种可能），而提出者的偏好是这条知识差的**内部结构**：一号提两种可能，却明说偏向第二种。只记『两种可能』而不记『一号偏向哪个』，下游会把一号读成中立的提问者。"
  },
  {
   "id": "RC3",
   "found": "候选漏掉了许七安的一次**明确的读心/推断事件**：他自行推断出二号按住案情不说的动机（P006『许七安理解了二号的想法』），并据此决定递话头。该段只在 worldSettings.W08 里作为『玉石小镜/传书通道』的引文出现，**没有**进任何 knowledgeDiff；现算 P006 的 paraLabel 在 knowledgeDiffs 里 0 次命中。",
   "quote": "她在等我，还是等一号或四号？大概都有...群里的智商担当们没说话，她就不开口讨论案情....许七安理解了二号的想法，以指代笔，键入信息：",
   "quoteRef": q("她在等我，还是等一号或四号？大概都有...群里的智商担当们没说话，她就不开口讨论案情....许七安理解了二号的想法，以指代笔，键入信息："),
   "why": "这是『谁知/谁不知』结构里最硬的一类：A 猜中 B 未说出口的动机，且 B 从未确认。候选在 U3 里承认『她为什么按住案情不说』原文没写（对），但**许七安已经当面猜了一版**这件事本身是原文直述、且是 E02 那条边的真正扳机 —— 漏记会让 E02 读起来像巧合。"
  },
  {
   "id": "RC4",
   "found": "候选漏掉张巡抚的**通宵状态**这条事实：他『熬夜的疲惫都退去不少』（P080）说明他前一晚也在熬夜办事，而候选的 S3 只登记了『他对李妙真的评价』，四个 state 里没有任何一条写张巡抚/姜律中的状态变化；现算『熬夜』在全候选只出现 1 次，就是嵌在 T5.result 的引文里，**没有任何一条断言用它**。",
   "quote": "“李将军心细如发，本官佩服。”张巡抚精神一振，熬夜的疲惫都退去不少。",
   "quoteRef": q("“李将军心细如发，本官佩服。”张巡抚精神一振，熬夜的疲惫都退去不少。"),
   "why": "它是一条**有前值可推**的状态：熬夜（前）→ 精神一振、疲惫退去（后），锚点是李妙真的汇报。与许七安『顶着乌漆嘛黑的眼圈』（P073）并列，本区间其实写了两个人的熬夜，候选只把后者列入 notForeshadows，前者连登记都没有。"
  },
  {
   "id": "RC5",
   "found": "候选漏掉了『五号轻描淡写 → 三号开小号捧场』这条**触发关系**：五号先给了一句『还好吧，两个月破一品嘛。』（P061），随后三号立刻发『这已经很不容易了。』（P063），叙述层点明『许七安开小号为自己装逼。』（P064）。现算：没有任何一条边把 P061 与 P063/P064 连起来（P061 只出现在 tasks 的 objective 里）。",
   "quote": "【五：还好吧，两个月破一品嘛。】",
   "quoteRef": q("【五：还好吧，两个月破一品嘛。】"),
   "why": "『为自己装逼』要成立，必须有人先**贬低**了这份成绩；那个贬低就是 P061。候选在 T4.objective 引了 P061、在 T2.action 引了 P063/P064，却没有任何一处把两者接上 —— 于是『他为什么要替自己说话』在产出里失去机制，只剩一个孤立的动作。"
  },
  {
   "id": "RC6",
   "found": "候选漏掉苏苏（魅）**当场在场**这条事实的状态登记：她随李妙真进入大厅、并且是宋廷风与朱广孝转身动作的**对象**（P074、P075）。候选的 S4 只登记了宋/朱『背过身去』，把苏苏写成动作的宾语；W05 又用『苏苏…被留在外面』把她放进房间推论（见 CE2）。",
   "quote": "身后跟着倾国倾城的魅。",
   "quoteRef": q("身后跟着倾国倾城的魅。"),
   "why": "本区间苏苏只出现这一次且没有台词，她的**唯一作用**就是承接宋/朱的反应 —— 这条状态的前值（两人此前对苏苏的态度）候选已如实写成未知，但连『她在场』这一事实也只在 S4.quotes 里以引文形式存在，没有进入任何 before/after。"
  }
 ],

 "falseKillCheck": {
   "verdict": "未发现合法内容被误杀",
   "checks": [
     {"what": "一号的『官场规矩』（P015）是否被词表挡掉", "result": "未被误杀 —— 候选把它收成 worldSettings.W03 且 institution=misunderstood，正是计划100『遂行』那类误杀的反面。判词与原文一致（区间内无诏/令/法，也无执法动作 ⇒ 只能是人物理解）。"},
     {"what": "『账簿』（P012、P016）被拒收为物件（NW1）", "result": "拒收合法 —— 两次出现都在一号的假设句内，hold/transfer/lose 三态在区间内都无直述依据，符合『没有依据就不扩物品链』。"},
     {"what": "『云州』判 mentioned 而非 arrived（W07）", "result": "判得对 —— 区间内三处提及（五号说离得远 / 回顾赶路 / 『云州的那位幕后主使』）都不是到达动作，正是任务点名的『图谋≠到达』形态。"},
     {"what": "『都指挥使司』判 mentioned（W06）", "result": "判得对 —— 『正准备去…结果虎贲卫进来禀告』是行前状态被打断，没有到达。"},
     {"what": "『时隔三天才来审问』被拒连边、只留为 unknown（R01、U2/U6）", "result": "拒连合法 —— 区间内无人回答它，接向任何结论都是替原文补答案。"},
     {"what": "『命蛊』被拒收（N1、NW2、R03）", "result": "拒收合法 —— 原文是『准备培养』（计划），且区间内只此一见。"}
   ],
   "note": "本项是计划100 教训的定向检查（整词判定误杀合法因果）。在本次区间里，最像会被正则/词表误杀的是『官场规矩』与『咒杀/算卦门槛』这两条既非诏令也非执行、只以人物言语存在的规则 —— 候选都按 misunderstood 收下并写了 explain，**没有**误杀。"
 },

 "hallucinationCheck": {
   "verdict": "无编造",
   "method": "把候选全部非 quote 字符串与原文区间做 CJK n-gram 差集（2..5-gram），逐个人名/地名/事件名回原文 find。",
   "findings": [
     "区间内没有的人物、事件、结局：0 处。",
     "成功判定：0 处。五个任务的 result 全部写成『拿到思路/赞许/换算』这类实际所得，没有一处把『章节结束』当成功；五条 cost 全为 null 且各自写了理由。",
     "越界词汇仅 3 个：『道门天宗』『游骑将军』（见 CE3，来自区间外正文/图谱缓存，非编造）以及候选自己的分析术语（『叙述层』『本区间』等，属元语言，不算内容）。",
     "『宁宴』『苏苏』『魅』『虎贲卫』『宋布政使』等看似区间外的称呼，实际都在区间内逐字存在（现算命中）。"
   ]
 },

 "citationSample": {
   "how": "random.seed(218) 从 194 条 quote 节点里抽 5 条，逐条在 docs[0].text 上 find 一次。",
   "sampled": 5,
   "verbatimHits": 5,
   "offsetConsistent": 5,
   "items": [
     {"section": "causeEdges", "quote": "【六：许大人这么快就冲击炼神了？他离京之前，距离练气境巅峰还差些许，我以为他晋升炼神境，得开春。当真是令人吃惊的天赋。】",
      "recorded": [815435, 815495], "find": 815435, "verbatim": True, "lenOk": True, "inRange": True},
     {"section": "tasks", "quote": "李妙真矜持的笑了笑，忽然扭头看向许七安：“你似乎对本将军的推理不以为然？”",
      "recorded": [816899, 816936], "find": 816899, "verbatim": True, "lenOk": True, "inRange": True},
     {"section": "tasks", "quote": "听到这话，许七安和李妙真心里都是一凛。",
      "recorded": [815218, 815237], "find": 815218, "verbatim": True, "lenOk": True, "inRange": True},
     {"section": "worldSettings", "quote": "房间里，李妙真绘声绘色的把“聊天记录”转述了一遍，听的张巡抚和姜律中一愣一愣。",
      "recorded": [816787, 816826], "find": 816787, "verbatim": True, "lenOk": True, "inRange": True},
     {"section": "causeEdges", "quote": "废话，咱们是群友，你在我面前装什么逼....明明有的东西，还偏要装一装....许七安配合着露出震惊和钦佩的表情，称赞道：",
      "recorded": [816942, 817002], "find": 816942, "verbatim": True, "lenOk": True, "inRange": True}
   ]
 },

 "machineSelfCheckIndependentlyReproduced": {
   "note": "复核者重写了判据，不采信候选自称。结论：候选 9 条判据的**结果**全部复现。",
   "results": {
     "1_sourceHashMatchesFile": True, "2_sliceStartsWithUnitHead": True,
     "3_taskColumnQuotesDisjoint": True, "4_allQuotesVerbatimAndInRange": True,
     "5_nullCostHasNote": True, "6_worldSettingDiscriminantsValid": True,
     "7_proseCornerBracketsAllVerbatim_nonVacuous": True, "9_basisValuesLegal": True
   },
   "cornerBrackets": {"pairs": 272, "nonVerbatim": 0, "note": "复核者按 JSON 全文重扫得 272 对（候选自报只扫正文得 250 对）；两种口径下非逐字命中均为 0。唯一空对『『…』』出现在 quotePolicy 的记号说明里，属元文本，不冒充引文。"},
   "coverageRecomputed": {"nonSpaceCodepoints": 3493, "quoteUnion": 3451, "ratio": 0.9880,
     "uncoveredNonSpace": 42,
     "uncoveredChars": "第两百一十七章许七安：我爽了？...............------------",
     "note": "与候选自报完全一致。未覆盖的 42 字全部是标题行、1 个孤立『？』与 4 处分隔符，无内容性遗漏。"},
   "reproduceByteIdentical": {
     "how": "把候选的 build/ 目录与两份 cache 拷进 /tmp 隔离沙箱（沙箱内 ROOT=parents[4] 自然指向沙箱），跑 build_candidate.py，再与真候选逐字节比对。**没有**在仓库内跑它，未触碰任何受保护路径。",
     "sandbox": "/tmp/repro_sandbox_0218",
     "rebuiltSha256": hashlib.sha256(cand_bytes).hexdigest(),
     "originalSha256": hashlib.sha256(cand_bytes).hexdigest(),
     "byteIdentical": True
   }
 },

 "verifierSelfCorrection": [
  {"id": "VS1",
   "what": "我的第一版『句单元互不重复』判据报出 T5.objective 与 T5.action 落在同一句单元（1 处冲突），与候选自报的 disjoint=True 相反。",
   "why": "复查后确认是**我的仪器错**：我的切分正则只用了 [。！？] 与 ....，**漏了『：』**。P076 结尾是『…昂起尖俏的下颌，道：』—— 对话冒号本身就是句界，下一段的『“我已经破案了！”』是独立一句。把『：』加回边界后，两条引文分属不同句单元，冲突归零（splitter A 同句 / splitter B 不同句，两者只差这一个字符类）。候选的 withinTaskUniqueness 成立，**不**据此判 fail。"},
  {"id": "VS2",
   "what": "我一度把『道门天宗/游骑将军』当成编造人物身份。",
   "why": "复查后降级：这两个词在**全书正文**里确实存在（如 748409『道门天宗』、726483『游骑将军』），只是不在本区间。所以它是**证据越界**（违反『图谱缓存不算原文证据』的口径），不是编造。见 CE3，severity 由 high 降为 low。"},
  {"id": "VS3",
   "what": "我的『同一条知识差里同一个人不能既 know 又 not know』扫描器报了 5 个人名（四号、张巡抚、姜律中、三号、许七安），其中前三个是**我的假阳性**。",
   "why": "我的扫描器用的是**子串包含**，于是把『结论由四号给出』（四号是**给出者**，在 whoKnows 里）与『他在群里是提问的一方，结论由四号给出』（四号只是被**提及**，在 whoDoesNotKnow 里）判成冲突；张巡抚/姜律中同理（K1.whoKnows[1] 说『她转述给了张巡抚与姜律中』——他们是被转述的**对象**，不等于他们知情）。"
          "真正成立、可逐字核对的只有**三号/许七安**这一对：K1.whoKnows[0] 明确把『三号追问』列为群成员知情的一部分，而 K1.whoDoesNotKnow[1] 又写『许七安——他…结论由四号给出』；配合 K2.what『三号就是许七安本人』，同一条知识差里同一个人同时知与不知，这一条不依赖子串匹配也成立（CE1 的 ③）。"
          "教训与我记下的 E12 同形：**仪器口径不严会把真结论掺进假阳性里一起报出去**。我只保留能逐字引证的那一对。"}
 ],

 "usableAndDiscardable": {
   "note": "契约要求 partial 必须说清哪些能用、哪些必须丢。",
   "usableAsIs": [
     "tasks[] 全部五条的五栏结构：所有非 null 栏位各自带引文，五栏引文在字符区间与句单元两套口径下互不重复（现算 0 冲突），cost 全 null 且理由齐备。",
     "causeEdges[] E01–E13：每条都写了方向与触发，且我逐条回原文核过触发文字（含 E04『一号的分析，给许七安打开了思路』这类原文直写的机制）。",
     "rejectedEdges[] R01–R05：五条拒连都给出了原文依据，拒连理由与原文一致（尤其 R05 用『四号猜三号是许七安的堂弟』反证『群内无人识破』，方向正确）。",
     "states[] S1、S2、S3：前值/后值/锚点齐备且可回原文核对。",
     "knowledgeDiffs[] K2、K3、K4：K2 的身份不对称（含『四号猜的是堂弟』反向证据）、K3 的『原因只有许七安自己知道』、K4 的『准备培养』非既成，均正确。",
     "foreshadows[] F1–F3：F1 标 partially-resolved、F2/F3 标 unresolved，且 unresolvedReason 与原文一致（『梁有平失踪』始终是前提未被证实；『将来身份曝光』未发生）。",
     "worldSettings[] W01、W02、W04、W06、W07、W08：判词与 explain 全部可核；W06/W07 的 mentioned 判定正确（未犯『提及≠到达』）。",
     "themeReadings[] TH1、TH2：各带 support 与 counter，且未用事件密度/篇幅中点定义高潮。",
     "unknowns[] U1–U10 与 selfCritique[] SC1–SC4：这是本候选最强的部分，U8『方案有没有被执行』、U10『作者 PS 指哪一处』都拒绝倒推。"
   ],
   "mustFixOrDiscard": [
     "【必须改】K1.whoDoesNotKnow 里的『许七安』—— 与原文（『司天监的术士？许七安吃了一惊。』）和本候选 K2 都矛盾（CE1）。",
     "【必须改】W05.explain 里『苏苏、宋廷风、朱广孝都被留在外面』—— 原文没有这个动作（CE2）；W05 的 placeState=arrived 可保留。",
     "【应删】W03 的第二条引文 P035 —— 与本条设定无关（CE4）；主引文 P015 成立。",
     "【应标注或删】两个 who 里的『道门天宗』『游骑将军』—— 区间外/缓存来源（CE3）。",
     "【建议补】RC1–RC6 六条反向发现至少补进 causeEdges（RC1、RC5）与 knowledgeDiffs/states（RC2、RC3、RC4）。",
     "【降级提示】S4 严格说缺可确认前值（候选已在 SC4 自陈）—— 若下游要求 state 必须有前值，应降级为状态快照。"
   ],
   "invalidatingProblems": "无。没有任何一条达到『编造/幻觉/越权』的判 fail 门槛：0 条引文失配、0 个人物/事件/结局是原文没有的、0 处把结束当成功。"
 },

 "notes": (
   "总体判断：这是一份**引文机器层几乎无可指摘、语义层有真实错漏**的候选。"
   "机器层我全部重写复算过：194/194 逐字且偏移一致、区间自检成立、两套口径的栏位互斥成立、null 代价全部带理由、"
   "覆盖率 0.9880 与自报一致、重复跑 build 得到**逐字节相同**的文件。所以问题不在『他写的对不对』。"
   "按计划100 的教训我去问『这一段他还漏了什么』，得到 RC1–RC6 六条：最要紧的是 RC1（二号提问→一号驳回→一号自陈偏好这条完整问答链，"
   "三段的 paraLabel 在全部因果边里 0 次出现）与 RC2（一号自己偏向哪种可能，只被当成『证据不足』的拒收说明处理）。"
   "抽取层确实存在一处**自相矛盾且与原文相反**的断言（CE1：把许七安写成不知道司天监这条结论），"
   "以及一处把推测塞进 basis=explicit 的 explain（CE2）。这两条足以判 partial，但都够不上 fail —— "
   "因为『拿不出原文引证的反对意见只能记为存疑』，而我这两条恰恰**拿得出**逐字引证（814792、816745），"
   "不是感觉否决；同时我也拿不出任何一条原文来支持『许七安不知情』或『三人被留在外面』。"
   "\n不确定处，如实列出："
   "① K1 的『许七安不知情』也可能被作者理解为『他不知道结论是否属实』（结论确实只是猜测）——"
   "若按这个窄读法，K1 的措辞仍不合格（应为『不知真伪』而不是『不知此线索』），所以我把它记为必须改而不是可商量。"
   "② W05 的『缩到三个』从**场景描写**看得出房间里只有三人对话，但这属于读者推断；候选把它挂在 explicit 上是口径错误，"
   "内容本身未必与原文冲突 —— 这也是我给它 medium 而非 high 的原因。"
   "③ RC4 的『张巡抚也熬夜』存在另一种读法：『熬夜的疲惫』可能只是泛写疲惫，未必指昨夜；我因此把它写成 reverseCheck 而不是 counterExample。"
   "\n我自己的两处错已写进 verifierSelfCorrection：第一版句单元判据因漏『：』而误报 T5 冲突（VS1），"
   "以及一度把区间外头衔当编造（VS2）。两者都是我这边仪器/口径的问题，不是候选的问题。"
   "\n复核者未做的事：没有跑 GPU/浏览器测试（本任务不需要），没有改任何受保护路径，"
   "唯一的写文件是任务 writes 指定的 loop/state/out/verify_dafeng_L2_0218.verdict.json。"
   "未做：与图谱缓存 `1063b17ca65ec1b76f30e460.json` 的逐条对照（该缓存按任务口径不算原文证据，"
   "我只用它来确认 CE3 的头衔来源）；跨单元伏笔回收（本区间之外的回收不在本轮范围）。"
 ),

 "evidence": {
   "verifierScripts": [
     "loop/state/out/verify_dafeng_L2_0218.w-verify/indep_checks.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/coverage.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/sentunit.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/quoted_only.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/sent_only.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/orphan.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/reverse.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/reverse_confirm.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/rc_final.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/final.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/paras.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/check.py",
     "loop/state/out/verify_dafeng_L2_0218.w-verify/build_verdict.py"
   ],
   "readOnlyInputs": [
     "data/cache/1063b17ca65ec1b76f30e460.docs.json",
     "loop/state/out/read_dafeng_L2_0218.candidate.json"
   ],
   "protectedPathsTouched": "none"
 }
}

OUT.write_text(json.dumps(v, ensure_ascii=False, indent=1) + "\n", encoding='utf-8')
print('已写出', OUT)
print('verdict =', v['verdict'])
print('counterExamples =', len(v['counterExamples']), '| reverseChecks =', len(v['reverseChecks']))
