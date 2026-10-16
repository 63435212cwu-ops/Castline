# -*- coding: utf-8 -*-
"""read:dafeng:L3:0243《大奉打更人》第十四章 女尸 —— 内容分区（数据层）。

本文件只有数据与三个标记辅助函数；**没有任何 start/end 偏移**。
偏移全部由 build.py 用 TEXT.find(锚点) 现算（锚点=整行或行内 seg），
所以这里的 ANCHORS 值必须逐字来自 docs[0].text[983109:988086)；
写错一个字，构建期就会以「锚点未命中/不唯一」中止，不会静默产出错引文。

标记约定：
  · A1(name)        → 单个引文节点（用于 quote / quoteRef 这类单值栏）
  · A(name, ...)    → 引文节点**列表**
  · SG(line, h, t)  → 行内片段引文节点（单值）
  · 需要混合时直接写 Python 列表，例如 [SG(...), A1(...)]；build.py 的
    _resolve 会递归处理列表，所以多值引文栏一律是 list。
"""


def A(*names):
    """多值引文栏：解析成一个引文节点列表。"""
    return {"__anchors__": list(names)}


def A1(name):
    """单值引文栏：解析成一个引文节点。"""
    return {"__anchor__": name}


def SG(line, head, tail):
    """行内片段：第 line 行里从 head 起、到 tail 止（必须同一行）。"""
    return {"__seg__": [line, head, tail]}


# ── 锚点表：值必须逐字出现在 [983109,988086) 且在该区间内唯一 ──────────────
ANCHORS = {
    # 浩气楼·金锣上场
    "L_ARRIVE": "一道道气机强盛的身影出现在七楼",
    "L_OLD_FRIENDS": "其中两人还是老熟人",
    "L_WEI_OK": "“魏公，你没事吧。”",
    "L_BURLY": "一位壮实魁梧的金锣，手持一柄紫金锤",
    "L_SORRY": "“卑职等人失职，竟未发现有外敌入侵，请魏公恕罪。”",
    "L_ZHANG_SENSE": "张开泰一边说着，一边扩散精神力",
    "L_NOTRIGHT": "渐渐的，经验丰富的金锣们察觉到了不对劲",
    "L_NOCRISIS": "但是完全没有。",
    "L_CALM": "整个浩气楼风平浪静",
    "L_SECOND": "其次，如果是强敌入侵",
    "L_RUMOR": "莫非真如传说中的那般",
    "L_GUESS": "这个猜测在众金锣心中升起",
    "L_NOT_NEW": "绝非一个初入炼神境的家伙能激发出来。",
    "L_NAN_ASK": "这时，他们听见南宫倩柔朝着许七安问道",
    "L_NAN_KNOW": "南宫倩柔知道许七安不是一般的炼神境。",
    "L_ADMIT": "搞什么鬼，我又不是宁采臣",
    "L_SILENCE": "茶室内，陷入了短暂的寂静。",
    "L_STARE": "金锣们无声的望着他，脸上都缺乏表情。",
    "L_ZHANG_PROBE": "过了许久，张开泰试探道",
    "L_LETTER": "早在姜律中密信传回京城时",
    "L_HALFMONTH": "可是，即便如此，他晋升炼神境也不过半个多月",
    "L_TALENT": "这份天资，委实有些惊人了。",
    "L_LIKE_OBJ": "想到这里，金锣们看着许七安的眼神，就像打量奇怪的物品。",
    "L_MUTTER": "“我突然明白姜律中和杨砚，为什么要为他大打出手。”",
    "L_SUDDEN": "恍然大悟！",
    "L_EAGER": "金锣们的目光愈发炽烈。",
    "L_DONT_MISREAD": "“你们别误会......”许七安摆摆手",
    "L_CHORUS_WEI": "这.....金锣们再次审视他，短暂沉默后，齐声道：“魏公.....”",
    "L_WEI_SHAKE": "魏渊摇摇头：“许七安依旧在杨砚麾下",
    "L_AGREED": "“一言为定！”",
    "L_SIX": "除南宫倩柔外，六名金锣再次齐声。",
    "L_PRAY": "我入谁麾下无所谓啦",
    "L_IMAGINE": "试想，在外头辛苦平叛剿匪的杨金锣",
    "L_ZHANG_LOOKOUT": "张开泰走到瞭望厅，往外张望",
    "L_WEI_DISMISS": "魏渊道：“散了吧，这件事你们知道就成，不许外传。”",
    "L_YES": "“是！”",
    "L_LEAVE_LOU": "等外头的侍卫和打更人散去",
    # 春风堂·家人
    "L_AUNT_WAIT": "婶婶和许玲月坐在桌边等待",
    "L_SISTER_ASK": "“大哥，你去哪了。”许玲月迎上来",
    "L_THUNDER": "“刚才怎么会有雷声，娘和铃音都被吓着了。”",
    "L_PERFECT": "许玲月是个有心机，有些小腹黑的妹妹",
    "L_USE_FAMILY": "巧妙的利用妹妹和母亲。",
    "L_SUNNY": "“晴天霹雳嘛，常有的事。”",
    "L_AUNT_ME": "婶婶看着银票，难以置信：“给我？”",
    "L_DESERVE": "许七安用力点头：“婶婶为了家，辛苦操持",
    "L_AUNT_SOFT": "婶婶接过银票，看着他，有些感动",
    "L_FAMILY": "“都是一家人。”许七安诚恳的说。",
    "L_TONIGHT": "“啊，对了，我今晚有事，不回家了。”",
    "L_AUNT_WHY": "“有事？”婶婶收好银票",
    "L_MOUNTAIN": "我要和人开发两座山峰",
    "L_SISTER_SUSPECT": "“大哥昨夜便没回府，今夜总不能又是同僚应酬吧。”",
    "L_DAD_SAYS": "“爹说大哥喜欢去教坊司。”",
    "L_AUNT_SCOLD": "“去去去。”婶婶啐了她一通",
    "L_SWEAR_DEMAND": "“那大哥跟我发誓，从未去过教坊司。”",
    "L_NO_QUALIFY": "不是，你一个妹妹，哪来的资格质问我",
    "L_OATH": "“我许七安，从未在教坊司花过银子。”",
    "L_SMILE": "许玲月嫣然一笑，眼波荡漾。",
    "L_URGE": "“玲月，回家后你也可以这般质问二郎。”",
    "L_AUNT_CONFIDENT": "“二郎当然不会去教坊司。”婶婶自信满满",
    # 春风堂·吕青
    "L_SEND_OFF": "送走婶婶和妹妹们，许七安打算回青云堂拿回金牌",
    "L_CLERK": "“许大人，府衙的总捕头吕青求见。”",
    "L_INVITE": "“把她请到堂内。”",
    "L_FOOTSTEP": "不多时，坐在桌案后的他听见了急促的脚步声",
    "L_LV_STARTLED": "看到许七安的刹那，清秀脸庞布满惊喜和激动的吕青",
    "L_LV_LOOK": "许七安也在打量许久不见的朋友",
    "L_OFFICIAL": "身上的官威也比以前更甚。",
    "L_GREET": "“吕捕头，许久未见，别来无恙？”",
    "L_LV_HUH": "“许，许大人？”吕捕头盯着许七安猛看。",
    "L_PILL": "“在云州服用了脱胎丸，这才死里逃生",
    "L_LV_MEDAL": "吕青点点头，勉强笑了笑，从怀里摸出金牌",
    "L_FACE": "“这点薄面，许大人想必会给我吧。”",
    "L_WATCH": "说话的时候，吕青秀气的眸子死死盯着许七安",
    "L_MEDAL_NOT": "“金牌不重要，”许七安把金牌丢在桌上",
    "L_DECLINE": "吕青摇头婉拒：“许大人，我毕竟是女子......”",
    "L_IF_MAN": "你要是男人，我刚才说的就是",
    "L_CHAT": "两人喝着茶，聊着聊着就忘了时间",
    "L_LEAVE_WORD": "“那小女子就告辞了。”",
    "L_SEE_OFF": "许七安把她送到衙门口",
    "L_GOOD_GIRL": "“算了，吕青是良家女子",
    "L_INTERESTED": "“吕青好像对我有点意思？",
    "L_CANT": "这事儿，许七安肯定做不到。",
    # 教坊司·浮香
    "L_SUNSET": "夕阳里，许七安骑着马",
    "L_FX_SICK": "浮香生病了，感染风寒",
    "L_FX_GLAD": "见到许七安过来，很惊喜，强撑着要起来。",
    "L_GUILT": "这就让许白嫖很愧疚了",
    "L_FX_OFFER": "浮香美眸半开半阖，昏昏欲睡",
    "L_MAIDS_EYES": "卧室里，三个清秀的丫鬟，眼睛唰的亮起来。",
    "L_REFUSE": "许七安摇摇头，一本正经的拒绝",
    "L_TRANSFER": "说完，握住浮香的手腕，渡入一缕缕细流般的气机。",
    "L_RULE_QI": "气机能疏通脉络，激活体内生机",
    "L_COUGH": "“咳咳咳.....”浮香剧烈咳嗽",
    "L_QUARTER": "一刻钟后，她的脸色果然大有好转。",
    "L_FX_BETTER": "“许郎，奴家好多了。”",
    "L_MAIDS_HAPPY": "三个丫鬟也露出了喜色。",
    "L_MED_FAIL": "娘子喝了药也不见好",
    "L_BYEBYE": "“好好休息，我明日再来看你。”",
    "L_AFTER_LEAVE": "确认他走后，浮香睁开眼睛",
    "L_MAIDS_LEAVE": "三个丫鬟应声离开。",
    "L_DOOR": "卧室的门缓缓关闭",
    "L_SIGH": "卧室里，轻轻的叹息回荡。",
    # 教坊司·明砚
    "L_QINGCHI": "许七安扭头去了青池院",
    "L_MY_DESC": "明砚花魁身材娇小玲珑",
    "L_MY_PAST": "明砚出身江南之地",
    "L_MY_FATHER": "第二年，她父亲就因为站错队被清算",
    "L_MY_CALL": "“许大人！”",
    "L_MY_SHOCK": "见到许七安后，笑容转变成愕然",
    "L_SWEET": "“一日不见如隔三秋。”",
    "L_MY_MOVED": "说话真好听.......明砚花魁惊喜的眼眶湿润",
    "L_ASHAMED": "哎，这些不负责任的甜言蜜语",
    "L_PLACE_RULE": "不过教坊司这种地方",
    "L_MY_SEAT": "明砚花魁引着许七安入座",
    "L_POUR": "说着，一手拎酒壶",
    "L_MISS": "“因为想念明砚娘子了。”",
    "L_CLOSE_GATE": "明砚花魁喜滋滋的扭头，吩咐丫鬟",
    "L_SNUGGLE": "顺势依偎在许七安怀里",
    "L_LUST": "如果说以前是看中他的才华",
    "L_TELL": "许七安简单的说起云州发生的事，侃侃而谈：",
    "L_WAR1": "“.......当时，八千叛军围攻了云州布政使衙门",
    "L_WAR2": "“不得以之下，我只能一人一刀",
    "L_WAR3": "“我整整砍了半个时辰",
    "L_TO_BED": "说着说着，两人从厅里说到了卧室",
    "L_DANCE": "“许公子，不是说好让奴家为你献上一舞么。”",
    "L_LATIN": "“那就来一支拉丁舞吧。”",
    "L_ALLNIGHT": "青池院，明砚花魁的床，摇到三更半夜。",
    # 皇宫·小宦官
    "L_NEXTDAY": "次日，精神抖擞的许七安离开青池院",
    "L_JOKE": "“呦，小公公今日格外客气。”",
    "L_ON_HORSE": "许七安坐在马背，笑着调侃。",
    "L_EUNUCH_PACE": "远远的，看见监督他的小宦官站在宫门不远处",
    "L_REPORT": "“许大人，您可算来了。”",
    "L_CORPSE": "“出事了出事了，昨夜有人在井中捞出一具女尸。”",
}

DELIBERATELY_UNQUOTED_NOTE = (
    "未引用段落分四类：①标题与分节行（第十四章 女尸 / .......... / ------------）；"
    "②短应答与重复感叹（“是！”之类），已由相邻动作句覆盖语义，单独引用不承载信息；"
    "③纯过渡句（席间闲聊、走到某处、心理感叹的延伸），不构成人物目标/阻力/因果/状态/设定中的任何一项；"
    "④荤笑话与现代梗的延伸句，只作 textualNotes 的注释对象，不升级为世界观设定。"
    "覆盖率只说明「这些码点被至少一条引文覆盖」，不等于语义已核验。"
)

SPEECH_NOTE = (
    "人物的话一律只当**线索**：能证明他说了什么、主张什么、想什么，不能证明他说的内容为真。"
    "本区间最危险的三条是 P01（许七安当众认下那一吼并给出「魏公要测试我元神强度」的理由）、"
    "P04（「我许七安，从未在教坊司花过银子」——与他当晚就进教坊司并排看）、"
    "P06（小宦官转述「昨夜有人在井中捞出一具女尸」——这是转述，且是区间内唯一信源）。"
    "P05（云州战功的自述）在区间内没有任何对照材料，既不能证实也不能证伪，已记 U06。"
)

NULL_FIELD_RULE = (
    "缺依据的栏写 null，并在同名 <栏位>Note 里写明为什么没有。"
    "本候选 null 共 8 处：T01–T06、T08、T09 的 cost，每处都带 costNote。"
    "构建期强制「null 必须带 Note」且「null 栏不得同时带 quotes」，实测 0 例外。"
    "T07 的 cost 有直述依据（关院门、当晚不打茶围），故不写 null，但仍写了 costNote 说明它是归纳而非直述。"
    "本区间**没有**出现「待验证/待核」冒充代价、也没有把法律规定/禁令当成已执行结果的情况。"
)

FORESHADOWS_NOTE = (
    "判据：要有铺设**与**回收才算伏笔；只出现一次的东西不写进 foreshadows。"
    "因此本区间最显眼的「女尸」（区间末尾只出现一次）**不**列为伏笔，而是写进 notForeshadows，"
    "它的回收在下一单元（第十五章 黄小柔），不在本区间。"
    "F02 是本区间唯一在区间内完成回收的伏笔；F01 为 partial（铺设完成、兑现发生在区间外）；"
    "F03/F04 为 unresolved 并各自写明 unresolvedWhat。"
)

WORLD_SETTINGS_NOTE = (
    "只收录**影响行动、资源、约束或后果**的明确设定，不为凑数扩地图/物品链/术语装饰层。"
    "place 的 placeState 与 item 的 itemStates 都写了判定依据（stateEvidence + stateEvidenceWhy/itemStatesNote），"
    "不靠读者自己分辨。判「未到达」的典型是本区间的青云堂：许七安「打算回青云堂拿回金牌」，"
    "但金牌被人送回来，他并没有去 —— 记为 mentioned，不记 arrived。"
    "rule 三条分档：气机治病与封口令有执行动作（executed）；人员归属的分派是当众给条件、"
    "执行（找杨砚）发生在区间外（declared）；「魏公身边有阴影高手」是人物群体的理解且被后文证伪"
    "（misunderstood，见 CE01）。"
)


SPEECHASCLUENOTFACT = [
    {
        "id": "P01",
        "speaker": "许七安",
        "speech": "“是我，刚才魏公要测试我元神强度，我就随便吼了一声。”",
        "canProve": "他当众认下那一吼，并给出「魏渊要测试他元神强度」这个理由。",
        "cannotProve": "不能证明魏渊真的要测试他——区间内没有魏渊自己的话，只见他「颔首」；也不能证明那一吼是「随便」的。",
        "why": "转述他人的授意＋自我贬低的措辞，都是当事人的说法，不是叙述事实。",
        "quoteRef": A1("L_ADMIT"),
    },
    {
        "id": "P02",
        "speaker": "许七安",
        "speech": "“我是在死之前最后一刻，才晋升炼神境的。”",
        "canProve": "他这样说明自己晋升的时点。",
        "cannotProve": "「死之前最后一刻」具体指什么，区间内没有解释（U05）。",
        "why": "关键情节只在人物一句话里，本区间没有第二处材料。",
        "quoteRef": A1("L_DONT_MISREAD"),
    },
    {
        "id": "P03",
        "speaker": "许七安",
        "speech": "“事情已经解决了，这是赵家给的赔偿金，这件事你们不用管了。”",
        "canProve": "他把一张百两银票交给家里，并声称来源是赵家的赔偿金。",
        "cannotProve": "银票是否真出自赵家、私塾的事是否真的了结（U04）。",
        "why": "来源只有他一句话；婶婶与许玲月只是接受，没有独立确认。",
        "quoteRef": SG("L_SUNNY", "事情已经解决了", "这件事你们不用管了。"),
    },
    {
        "id": "P04",
        "speaker": "许七安",
        "speech": "“我许七安，从未在教坊司花过银子。”",
        "canProve": "他发的誓在字面上只否定「花过银子」；这与他妹妹要求的「从未去过」不是同一件事。",
        "cannotProve": "他有没有去过教坊司——他当晚就进了教坊司（见 W04 与 U12）。",
        "why": "重誓的措辞与要求的措辞不同，这个差值是原文可核的；把它读成有意规避是我的归纳（见 CE07、SC04）。",
        "quoteRef": A1("L_OATH"),
    },
    {
        "id": "P05",
        "speaker": "许七安（对明砚）",
        "speech": "“不得以之下，我只能一人一刀，挡在八千叛军之前，来一个我杀一个，来两个我杀一双。”",
        "canProve": "他这样对明砚讲述云州之事。",
        "cannotProve": "战功是否属实：本区间没有对照材料，也没有第三方在场核实。",
        "why": "单一信源的自述，且听众无从核实；已记 U06，不作结论。",
        "quoteRef": A1("L_WAR2"),
    },
    {
        "id": "P06",
        "speaker": "小宦官",
        "speech": "“出事了出事了，昨夜有人在井中捞出一具女尸。”",
        "canProve": "他把这件事报了出来。",
        "cannotProve": "女尸的身份、死因、是否命案——区间内没有任何核实（U07）。",
        "why": "转述「昨夜」发生的事，且是区间内唯一信源；本章即止于此。",
        "quoteRef": SG("L_REPORT", "出事了出事了", "捞出一具女尸。"),
    },
    {
        "id": "P07",
        "speaker": "吕青",
        "speech": "“府衙的捕手与我说了私塾的事，我做主让朱捕头回去了，亲自将金牌送还许大人。顺便来探望探望。",
        "canProve": "她自称作主让朱捕头回去、并亲自送还金牌。",
        "cannotProve": "朱捕头是否真的被召回、私塾的事到底如何了结（U09）。",
        "why": "全是她的一面之词；区间内没有府衙一侧的第二信源。",
        "quoteRef": A1("L_LV_MEDAL"),
    },
    {
        "id": "P08",
        "speaker": "魏渊",
        "speech": "“许七安依旧在杨砚麾下，你们谁想要，自己找杨砚去。”",
        "canProve": "他当众把许七安留在杨砚麾下，并把交涉推给杨砚。",
        "cannotProve": "杨砚会不会同意放人——本区间没有人知道（K06）。",
        "why": "这句话是权力分配，不是对杨砚意愿的陈述；它只解释金锣们「不能直接得到人」。",
        "quoteRef": A1("L_WEI_SHAKE"),
    },
    {
        "id": "P09",
        "speaker": "金锣（壮实魁梧者）",
        "speech": "“卑职等人失职，竟未发现有外敌入侵，请魏公恕罪。”",
        "canProve": "他们进来时把现场当成外敌入侵，并为此请罪。",
        "cannotProve": "真有外敌入侵——他们自己随后就判断「但是完全没有」。",
        "why": "请罪时的假设随后被同一段叙述推翻，是「说法≠事实」的当场例子。",
        "quoteRef": A1("L_SORRY"),
    },
]


TASKS = [
    {
        "id": "T01",
        "actor": "六名金锣（除南宫倩柔外）",
        "objective": "把许七安要到自己的麾下。",
        "objectiveBasis": "inferred",
        "objectiveQuotes": A("L_MUTTER", "L_EAGER"),
        "objectiveNote": "原文没有一句写「我们要他」。这一栏是从两处直述归纳的：他们意识到许七安的天资后「目光愈发炽烈」，"
                         "并当场明白了姜律中与杨砚为何为他大打出手。若复核认为 objective 必须有直述，本栏应改 null。",
        "obstacle": "许七安名义上属杨砚麾下，魏渊不直接分配，要人得自己去找杨砚。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": A("L_WEI_SHAKE"),
        "action": "沉默片刻后齐声向魏渊开口要人。",
        "actionBasis": "explicit",
        "actionQuotes": A("L_CHORUS_WEI"),
        "result": "没有当场得到人：魏渊把人留在杨砚麾下，只给了「自己找杨砚去」的条件；六人当场应下，人并没有转手。",
        "resultBasis": "explicit",
        "resultQuotes": A("L_AGREED", "L_SIX"),
        "cost": None,
        "costNote": "本区间未写金锣为争人付出任何代价：没有许诺、没有交换、也没有损失。他们只是口头应下要自己去找杨砚；"
                    "与杨砚的交涉发生在区间外，其后果只出现在许七安的预想里（见 U10），不能当成他们的已付代价。",
    },
    {
        "id": "T02",
        "actor": "许七安",
        "objective": "把赵家的赔偿金交给婶婶，并让家里不必再管私塾这件事。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": [SG("L_SUNNY", "事情已经解决了", "这件事你们不用管了。")],
        "obstacle": "赔偿只有一百两，他要为「只有这些」作解释（赵家背后的靠山不小）。",
        "obstacleBasis": "inferred",
        "obstacleQuotes": [SG("L_DESERVE", "可惜只有一百两", "靠山也不小。")],
        "obstacleNote": "直述的是「可惜只有一百两，毕竟人家背后的靠山也不小」这句话本身；把它读成阻力（他必须解释数额）是我的归纳，"
                        "原文没有写婶婶嫌少或追责。",
        "action": "从怀里掏出银票，当面交给婶婶。",
        "actionBasis": "explicit",
        "actionQuotes": [SG("L_SUNNY", "许七安从怀里掏出一张百两银票", "百两银票")],
        "result": "婶婶收下银票、态度转缓：她自认只是爱发牢骚，让他别把不中听的话往心里去。",
        "resultBasis": "explicit",
        "resultQuotes": A("L_AUNT_SOFT"),
        "cost": None,
        "costNote": "本区间未写许七安为此付出代价：银票是赵家给的赔偿金（他自称），不是他的支出；"
                    "也没有写他为让家里不再过问而让渡或损失了什么。他紧接着在一场质问里被要求发誓（T03），但那是另一件事。",
    },
    {
        "id": "T03",
        "actor": "许玲月",
        "objective": "逼大哥就「去没去过教坊司」表态：先搬出「爹说大哥喜欢去教坊司」把话挑明。",
        "objectiveBasis": "inferred",
        "objectiveQuotes": A("L_DAD_SAYS"),
        "objectiveNote": "这句是她的指控/引述，不是她的目的陈述；把「挑明指控」读成「要一个表态」是我的归纳（紧接着她确实提出了发誓要求）。",
        "obstacle": "婶婶当面回护大哥，把她的怀疑挡回去。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": A("L_AUNT_SCOLD"),
        "action": "抿着唇、以倔强的姿态要求大哥发誓从未去过教坊司。",
        "actionBasis": "explicit",
        "actionQuotes": A("L_SWEAR_DEMAND"),
        "result": "大哥发了誓，她满意地笑了；但誓言的措辞是「从未在教坊司花过银子」，而不是她要求的「从未去过」。",
        "resultBasis": "derived",
        "resultQuotes": A("L_OATH", "L_SMILE"),
        "resultNote": "「她得到了一个措辞不同的誓言」是我把她的要求与他的誓言并排读出来的（两处都是直述，差值由我指出），"
                      "原文没有写她是否注意到这个差别——她只「嫣然一笑」。",
        "cost": None,
        "costNote": "本区间未写许玲月为这次质问付出代价：她没有被罚、没有失去什么，也没有付出交换；"
                    "她在这一场之前确实被雷声吓到（引文见 actionQuotes 之外的 T02；那是另一件事，不是这次追问的代价）。",
    },
    {
        "id": "T04",
        "actor": "吕青",
        "objective": "亲自把金牌送还许七安，顺便探望，并希望「这点薄面」被他接下。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": A("L_LV_MEDAL", "L_FACE"),
        "obstacle": "她拿不准许七安会不会不悦，只能盯着他的脸色，准备一有不对就道歉、还牌、走人。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": A("L_WATCH"),
        "action": "以急促的脚步跨进春风堂，当面见他。",
        "actionBasis": "explicit",
        "actionQuotes": A("L_FOOTSTEP"),
        "result": "许七安说金牌不重要、把金牌丢在桌上，并邀她晚上一起喝酒；她以「我毕竟是女子」婉拒，两人喝茶聊到散值。",
        "resultBasis": "explicit",
        "resultQuotes": A("L_MEDAL_NOT", "L_DECLINE", "L_CHAT"),
        "cost": None,
        "costNote": "本区间未写吕青付出代价：她「做主让朱捕头回去了」是行使职权（且被她说成是给许七安的面子），"
                    "原文没有写她因此受罚、损失或让渡任何东西。",
    },
    {
        "id": "T05",
        "actor": "许七安",
        "objective": "为浮香渡送气机，治她的风寒。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": [SG("L_REFUSE", "我为你渡送气机", "气机")],
        "obstacle": "治疗过程中她剧烈咳嗽、俏脸憋得通红。",
        "obstacleBasis": "inferred",
        "obstacleQuotes": A("L_COUGH"),
        "obstacleNote": "直述的只有「剧烈咳嗽、俏脸憋的通红」这一现象；把它读成阻力是我的归纳（它也可能是好转前的反应）。"
                        "原文没有写任何人或任何东西在拦他。",
        "action": "握住她的手腕，渡入一缕缕细流般的气机。",
        "actionBasis": "explicit",
        "actionQuotes": A("L_TRANSFER"),
        "result": "一刻钟后她的脸色大有好转，自称好多了；三名丫鬟也露出喜色。",
        "resultBasis": "explicit",
        "resultQuotes": A("L_QUARTER", "L_FX_BETTER", "L_MAIDS_HAPPY"),
        "cost": None,
        "costNote": "本区间未写许七安为渡送气机付出代价：没有写他损耗修为、也没有写他付出财物；"
                    "浮香的剧烈咳嗽是治疗过程中的反应，不是他的代价。",
    },
    {
        "id": "T06",
        "actor": "浮香",
        "objective": "把人都遣出去，独自留在房里。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": [SG("L_AFTER_LEAVE", "你们都出去吧", "房间里不必留人。")],
        "obstacle": "她必须先确认许七安已经离开，才敢睁眼开口。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": [SG("L_AFTER_LEAVE", "确认他走后", "浮香睁开眼睛")],
        "action": "丫鬟应声离开。",
        "actionBasis": "explicit",
        "actionQuotes": A("L_MAIDS_LEAVE"),
        "result": "卧室的门关上、房里只剩她一人后，原本好转的脸色迅速颓败，只剩一声叹息。",
        "resultBasis": "explicit",
        "resultQuotes": A("L_DOOR", "L_SIGH"),
        "cost": None,
        "costNote": "本区间未写她为独处付出代价：「脸色颓败」是她的病情/结果，不是她为达成目标付出的代价；"
                    "原文也没有写她付出财物或人情。",
    },
    {
        "id": "T07",
        "actor": "明砚",
        "objective": "留住许七安（叙述已写明她由看中才华转为馋他身子）。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": A("L_LUST"),
        "obstacle": "许七安容貌变化太大，她迎上来时差点以为自己认错人。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": A("L_MY_SHOCK"),
        "action": "亲手给他倒酒，顺势依偎进他怀里。",
        "actionBasis": "explicit",
        "actionQuotes": A("L_POUR", "L_SNUGGLE"),
        "result": "她吩咐关院门、当晚不再打茶围；两人从厅里到卧室，床摇到三更半夜。",
        "resultBasis": "explicit",
        "resultQuotes": A("L_TO_BED", "L_ALLNIGHT"),
        "cost": "关院门、当晚不再打茶围——放弃当晚其他客人的生意。",
        "costBasis": "inferred",
        "costQuotes": [SG("L_CLOSE_GATE", "关院门", "今晚不打茶围了。")],
        "costNote": "直述的只有她的吩咐；把它算成代价是归纳（关院门＝当晚不再接别的客人）。"
                    "原文没有写她因此损失了多少，也没有写她为此犹豫。若复核认为手段不等于代价，本栏应改 null。",
    },
    {
        "id": "T08",
        "actor": "小宦官",
        "objective": "等到许七安，把出事的消息当面报给他。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": [SG("L_REPORT", "“许大人，您可算来了。”", "您可算来了。”")],
        "obstacle": "许七安迟迟不到，他在宫门不远处焦急地来回踱步。",
        "obstacleBasis": "inferred",
        "obstacleQuotes": A("L_EUNUCH_PACE"),
        "obstacleNote": "「焦急的来回踱步」是直述；把它读成「等不到人」这个阻力是我的归纳——原文没有写他等了多久、也没有写他被谁拦。",
        "action": "疾步迎上来，边走边说。",
        "actionBasis": "explicit",
        "actionQuotes": [SG("L_REPORT", "小宦官疾步上来", "边走边说：")],
        "result": "他把消息报了出来：昨夜有人在井中捞出一具女尸。",
        "resultBasis": "explicit",
        "resultQuotes": [SG("L_REPORT", "出事了出事了", "捞出一具女尸。")],
        "resultNote": "这里只记「他把这句话说出来了」，不记「井中真有女尸」——后者是他的一句转述，区间内没有第二信源（U07）。",
        "cost": None,
        "costNote": "本区间未写小宦官为此付出代价：他只是等待与传讯，没有被罚、没有损耗、也没有交换。",
    },
    {
        "id": "T09",
        "actor": "魏渊",
        "objective": "不让今天这件事外传。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": [SG("L_WEI_DISMISS", "这件事你们知道就成", "不许外传。")],
        "obstacle": "楼下的打更人和侍卫聚在一起，人多口杂。",
        "obstacleBasis": "inferred",
        "obstacleQuotes": A("L_ZHANG_LOOKOUT"),
        "obstacleNote": "「都聚集在楼下了」是直述；把它读成封口的阻力（人多易传）是我的归纳，原文没有把这两句连起来说。",
        "action": "让在场金锣散了。",
        "actionBasis": "explicit",
        "actionQuotes": [SG("L_WEI_DISMISS", "散了吧", "散了吧")],
        "result": "外头的侍卫和打更人散去，许七安随后也离开浩气楼返回春风堂。",
        "resultBasis": "explicit",
        "resultQuotes": A("L_LEAVE_LOU"),
        "cost": None,
        "costNote": "本区间未写魏渊为封口付出代价（没有惩罚、没有交换、没有损失）；"
                    "也**没有**写这条命令在区间之外是否被遵守——「不许外传」是命令，不是已执行的结果。",
    },
]


CAUSEEDGES = [
    {
        "id": "CE01",
        "from": "许七安那一声吼造成的强元神波动",
        "to": "金锣们把来源归给一个不存在的「魏公身边的阴影高手」",
        "trigger": "金锣们的灵觉在整座浩气楼没有任何危机反馈，而魏渊安然无恙。",
        "mechanism": "先排除外敌入侵（否则魏公不会安然无恙），再排除许七安（那波动「绝非一个初入炼神境的家伙能激发出来」，"
                     "而他们知道他才晋升半个多月），剩下的解释就只有那个传说——于是误判成立。",
        "basis": "derived",
        "quotes": A("L_NOT_NEW", "L_RUMOR", "L_GUESS", "L_SECOND"),
        "note": "两处直述（不是他→只能是传说中的护卫）由我把中间的排除过程接起来，所以是 derived 而不是 explicit。",
    },
    {
        "id": "CE02",
        "from": "南宫倩柔当面发问",
        "to": "许七安当众承认那一吼是自己",
        "trigger": "她问「刚才是不是你在搞鬼」，而许七安看向魏渊、见他颔首。",
        "mechanism": "她本来就「知道许七安不是一般的炼神境」，所以问的是他而不是别人；他不确定能不能说，先看魏渊，"
                     "得到颔首后才「大方承认」。",
        "basis": "explicit",
        "quotes": A("L_NAN_ASK", "L_NAN_KNOW", "L_ADMIT"),
    },
    {
        "id": "CE03",
        "from": "许七安承认并自陈「死之前最后一刻才晋升炼神境」",
        "to": "六名金锣当场向魏渊开口要人",
        "trigger": "他的解释没有压低评价，反而与「半个多月」的资历并排后更显天资。",
        "mechanism": "承认→解释资历→金锣们把资历与刚才的波动对照，得出「这份天资，委实有些惊人了」，"
                     "于是短暂沉默后齐声喊魏公。",
        "basis": "derived",
        "quotes": A("L_DONT_MISREAD", "L_HALFMONTH", "L_TALENT", "L_CHORUS_WEI"),
    },
    {
        "id": "CE04",
        "from": "魏渊把人留在杨砚麾下、把交涉推给杨砚",
        "to": "金锣们应下「一言为定」，许七安开始担心杨砚回京后的场面",
        "trigger": "「你们谁想要，自己找杨砚去」这句条件。",
        "mechanism": "冲突没有被解决，只是被移交给不在场的杨砚；金锣们接受这个条件，许七安则顺着这条线想到"
                     "杨砚回京要面对同僚的拳头与姜律中的背刺。",
        "basis": "derived",
        "quotes": A("L_WEI_SHAKE", "L_AGREED", "L_PRAY", "L_IMAGINE"),
    },
    {
        "id": "CE05",
        "from": "楼下聚集的打更人与侍卫",
        "to": "魏渊当场下令散了并封口",
        "trigger": "张开泰从瞭望厅回报「打更人和侍卫都聚集在楼下了」。",
        "mechanism": "楼下已经聚起不知情的人，事情越传越广；他在同一轮里先让金锣散场，再补一句「这件事你们知道就成，不许外传」。",
        "basis": "derived",
        "quotes": A("L_ZHANG_LOOKOUT", "L_WEI_DISMISS"),
    },
    {
        "id": "CE06",
        "from": "许七安给婶婶百两银票并说「这是婶婶应得的」",
        "to": "婶婶态度转缓、当面说软话",
        "trigger": "银票与那句「婶婶为了家，辛苦操持，这是婶婶应得的」。",
        "mechanism": "她先是不敢相信「给我？」，随后接过银票、有些感动，改口说自己只是爱发牢骚、让他别把不中听的话往心里去。",
        "basis": "explicit",
        "quotes": A("L_AUNT_ME", "L_DESERVE", "L_AUNT_SOFT"),
    },
    {
        "id": "CE07",
        "from": "许玲月要求大哥发誓「从未去过教坊司」",
        "to": "许七安发了一个措辞更窄的誓：从未在教坊司花过银子",
        "trigger": "婶婶先替他挡了一句，他仍被妹妹逼到必须当场表态。",
        "mechanism": "他不能照字面认下或否认「去过」，于是把誓言收在「花过银子」上；两处措辞的差值是原文可核的，"
                     "但**是不是有意规避**原文没有写，这一段由我补。",
        "basis": "derived",
        "quotes": A("L_SWEAR_DEMAND", "L_OATH", "L_NO_QUALIFY"),
        "note": "本条只声称「措辞不同」，不声称「他在说谎」——他当晚确实进了教坊司（L_SUNSET），但那不等于花过银子。见 U12。",
    },
    {
        "id": "CE08",
        "from": "许七安渡气使浮香当场好转",
        "to": "许七安与丫鬟都以为她好转；他离开、丫鬟退下后她的脸色迅速颓败",
        "trigger": "「确认他走后」——她先确认他离阁，才睁眼遣走丫鬟、关门。",
        "mechanism": "原文把「好转」与「颓败」写成同一晚的两段，并以「他走后」为前提；成因（是病情另有内情，还是好转只是暂时）"
                     "原文**没有写**，故本边只主张「独处后才显露颓败」这个顺序，不主张她是装病。",
        "basis": "derived",
        "quotes": A("L_TRANSFER", "L_QUARTER", "L_AFTER_LEAVE", "L_DOOR"),
    },
    {
        "id": "CE09",
        "from": "吕青做主让朱捕头回去、亲自送还金牌",
        "to": "许七安不必再回青云堂取牌，并在春风堂与她见了一面",
        "trigger": "吏员禀报「府衙的总捕头吕青求见」。",
        "mechanism": "他刚「打算回青云堂拿回金牌」，就被告知金牌「被人给送回来了」，紧接着求见者正是送牌的人；"
                     "两件事指向同一个动作，她的到访取代了他原本要跑的一趟。",
        "basis": "derived",
        "quotes": A("L_SEND_OFF", "L_CLERK", "L_LV_MEDAL"),
    },
    {
        "id": "CE10",
        "from": "吕青盯着许七安脸色、随时准备道歉走人",
        "to": "许七安以「金牌不重要」把话题从公事转到私交并邀酒",
        "trigger": "她那句「这点薄面，许大人想必会给我吧」与她死死盯着他的眼神。",
        "mechanism": "她的不确定写在脸上，他的回应是丢开金牌、直接提出晚上一起喝酒，于是会面没有变成一次尴尬的公事交接。",
        "basis": "derived",
        "quotes": A("L_WATCH", "L_FACE", "L_MEDAL_NOT"),
    },
    {
        "id": "CE11",
        "from": "许七安容貌大变让明砚一时认不出",
        "to": "他用甜言蜜语消解，她关院门留客、两人留宿青池院",
        "trigger": "她「笑容转变成愕然，差点以为自己认错人」。",
        "mechanism": "他先用「稍后再说」把容貌问题搁置，再补一串情话；她由惊愕转回情意，随后吩咐关院门、当晚不接茶围。",
        "basis": "derived",
        "quotes": A("L_MY_SHOCK", "L_SWEET", "L_CLOSE_GATE", "L_LUST"),
    },
    {
        "id": "CE12",
        "from": "井中捞出女尸这件事",
        "to": "小宦官在宫门等许七安并把消息报给他",
        "trigger": "「昨夜有人在井中捞出一具女尸」——他见面第一句就是这句。",
        "mechanism": "原文写他在宫门外「焦急的来回踱步」、见到许七安说「您可算来了」，随后直接报讯；"
                     "我推断他等的是许七安、为的是报讯。原文**没有**写他为什么等、等了多久。",
        "basis": "inferred",
        "quotes": A("L_EUNUCH_PACE", "L_REPORT", "L_CORPSE"),
    },
]


REJECTEDEDGES = [
    {
        "id": "RE01",
        "wouldBe": "浮香剧烈咳嗽 → 一刻钟后脸色好转",
        "why": "两句时间相邻，但原文写好转的原因是渡入气机（以及「一刻钟后」这个时长），没有把咳嗽写成好转的原因；"
               "咳嗽只是治疗过程中的反应。按「时间相邻当因果」的红线，这里不连边。",
        "quotes": A("L_COUGH", "L_QUARTER"),
    },
    {
        "id": "RE02",
        "wouldBe": "婶婶收下银票 → 许玲月追问大哥去不去教坊司",
        "why": "两句前后相邻，但玲月那句的直接由来是「爹说大哥喜欢去教坊司」，与银票之间没有机制；"
               "把同场景的两件事连成因果属于「同一场景当因果」。",
        "quotes": A("L_AUNT_SOFT", "L_DAD_SAYS"),
    },
    {
        "id": "RE03",
        "wouldBe": "明砚关院门 → 许七安讲云州战功",
        "why": "同场景相邻，但讲战功的触发是她问「许公子怎么没留宿影梅小阁」，与关院门之间没有可写的机制；"
               "一个人的吩咐不会使另一个人开口讲战功。",
        "quotes": A("L_CLOSE_GATE", "L_TELL"),
    },
    {
        "id": "RE04",
        "wouldBe": "井中女尸的消息 → 小宦官被派来监督许七安",
        "why": "方向反了：监督是他既有的差事（「监督他的小宦官」），女尸是「昨夜」才发生的事，"
               "不能用后发生的事解释先存在的关系。",
        "quotes": A("L_EUNUCH_PACE", "L_CORPSE"),
    },
    {
        "id": "RE05",
        "wouldBe": "许七安发誓「从未在教坊司花过银子」 → 他当晚进教坊司",
        "why": "看似矛盾，其实两句约束的不是同一件事：誓言只说「没花过银子」，而他进教坊司是去看浮香与明砚。"
               "把它读成「他说谎」需要额外前提（进教坊司＝花银子），原文没有给这个前提。已记 U12。",
        "quotes": A("L_OATH", "L_SUNSET"),
    },
]


STATES = [
    {
        "id": "S01",
        "who": "金锣们对许七安实力的判断",
        "before": "只知道他半个多月前在云州晋升炼神境，此前那一声吼在他们看来「绝非一个初入炼神境的家伙能激发出来」。",
        "after": "把他当成「这份天资，委实有些惊人了」的异数，看他的眼神「就像打量奇怪的物品」，随即六人开口要人。",
        "anchor": "那一吼的余波 ＋ 他自陈「死之前最后一刻」才晋升。",
        "basis": "derived",
        "anchorQuotes": A("L_HALFMONTH", "L_TALENT", "L_LIKE_OBJ", "L_SIX"),
    },
    {
        "id": "S02",
        "who": "在场金锣对「那一吼是谁发出的」的认定",
        "before": "谁都没想到许七安，猜测是「魏公身边存在着阴影里高手」。",
        "after": "许七安当众承认「是我」；茶室短暂寂静，金锣们无声地望着他。",
        "anchor": "南宫倩柔当面发问 ＋ 许七安见魏渊颔首后承认。",
        "basis": "explicit",
        "anchorQuotes": A("L_GUESS", "L_ADMIT", "L_SILENCE"),
    },
    {
        "id": "S03",
        "who": "婶婶对许七安的态度",
        "before": "爱发牢骚，说过些不中听的话（由她自己在事后承认）。",
        "after": "收下银票、有些感动，当面说自己只是爱发牢骚，让他别往心里去。",
        "anchor": "许七安交出百两银票并说「这是婶婶应得的」。",
        "basis": "explicit",
        "anchorQuotes": A("L_AUNT_SOFT", "L_AUNT_ME"),
    },
    {
        "id": "S04",
        "who": "浮香的病况外表",
        "before": "感染风寒，昏昏沉沉、脸色苍白地躺在床上，连起身都要强撑。",
        "after": "渡气一刻钟后「脸色果然大有好转」、自称好多了；许七安离开、丫鬟退下、门关上之后，脸色又「迅速颓败下去」。",
        "anchor": "许七安渡气 → 离开影梅小阁；她确认他走后遣走丫鬟并关门。",
        "basis": "explicit",
        "anchorQuotes": A("L_FX_SICK", "L_QUARTER", "L_DOOR"),
        "note": "后一段转向的**原因**原文没有写（U02）；这里只记前后两值的直述。",
    },
    {
        "id": "S05",
        "who": "吕青对许七安容貌的辨认",
        "before": "进堂看到他就「猛的一愣，疑惑的盯着他」，只叫出「许，许大人？」。",
        "after": "听他解释是服了脱胎丸、死里逃生后点头接受，并当面托付「这点薄面」。",
        "anchor": "许七安自述在云州服用脱胎丸、模样有了变化。",
        "basis": "explicit",
        "anchorQuotes": A("L_LV_STARTLED", "L_LV_HUH", "L_PILL"),
    },
    {
        "id": "S06",
        "who": "明砚对许七安的取向",
        "before": "「看中他的才华」。",
        "after": "「有些馋他身子了」——月余未见，他的容貌变化翻天覆地。",
        "anchor": "她在青池院迎他、亲手倒酒、依偎入怀并留他过夜。",
        "basis": "explicit",
        "anchorQuotes": A("L_LUST", "L_SNUGGLE"),
    },
    {
        "id": "S07",
        "who": "婶婶对「二郎会不会去教坊司」的确定程度",
        "before": "自信满满：二郎当然不会去教坊司。",
        "after": "决定当晚等许平志回家后，自己也这般质问，看他敢不敢发誓。",
        "anchor": "许七安怂恿玲月回家质问二郎。",
        "basis": "explicit",
        "anchorQuotes": A("L_AUNT_CONFIDENT", "L_URGE"),
    },
    {
        "id": "S08",
        "who": "浩气楼内外的秩序",
        "before": "金锣如临大敌、楼内吏员陷入慌乱，打更人与侍卫聚集在楼下。",
        "after": "金锣领命散去，外头侍卫与打更人散去，许七安随后离开返回春风堂；魏渊同时下了封口令。",
        "anchor": "魏渊「散了吧，这件事你们知道就成，不许外传」。",
        "basis": "explicit",
        "anchorQuotes": A("L_CALM", "L_ZHANG_LOOKOUT", "L_WEI_DISMISS", "L_LEAVE_LOU"),
    },
]


KNOWLEDGEGAPS = [
    {
        "id": "K01",
        "whoKnows": "南宫倩柔——她「知道许七安不是一般的炼神境」，所以当面问他是不是在搞鬼。",
        "whoDoesNot": "其余金锣——他们猜的是「魏公身边存在着阴影里高手」。",
        "what": "那一吼是谁发出的、为什么强得不像新晋炼神境。",
        "resolution": "区间内闭合：许七安当众承认「是我」。",
        "basis": "explicit",
        "quotes": A("L_NAN_KNOW", "L_GUESS", "L_ADMIT"),
    },
    {
        "id": "K02",
        "whoKnows": "魏渊（他手里有那个「回复」）。",
        "whoDoesNot": "许七安——开篇就写「许七安没等来魏渊的回复」。",
        "what": "魏渊要回复他的那件事的内容（本区间没有写请求是什么）。",
        "resolution": "区间内未闭合。",
        "basis": "explicit",
        "quotes": A("L_ARRIVE"),
        "note": "引文锚定的是「没等来魏渊的回复」所在的整行；请求内容本区间确实未写（U01）。",
    },
    {
        "id": "K03",
        "whoKnows": "许七安（他知道那声「雷」是什么、银票从哪来）。",
        "whoDoesNot": "婶婶与许玲月——她们接受了「晴天霹雳」和「赵家给的赔偿金」两个说法。",
        "what": "那声「雷」的真实来路（他自己吼的）与银票的真实来源。",
        "resolution": "区间内未闭合；她们没有追问。",
        "basis": "derived",
        "quotes": A("L_THUNDER", "L_SUNNY"),
    },
    {
        "id": "K04",
        "whoKnows": "浮香（她知道自己的脸色在他走后变成什么样）。",
        "whoDoesNot": "许七安与三名丫鬟——他们看到的是「大有好转」与「气色马上好转」。",
        "what": "她的病并没有真的好；好转只维持到他离开。",
        "resolution": "区间内未闭合（读者看到了，区间内人物没有）。",
        "basis": "derived",
        "quotes": A("L_MED_FAIL", "L_DOOR", "L_SIGH"),
    },
    {
        "id": "K05",
        "whoKnows": "许七安（他自称是脱胎丸）。",
        "whoDoesNot": "吕青、明砚、婶婶等所有听到他解释的人。",
        "what": "他容貌变化的成因；区间内只有他给出的说法（脱胎丸），没有第二信源。",
        "resolution": "区间内未闭合。",
        "basis": "explicit",
        "quotes": A("L_PILL"),
        "note": "这里不判定他说的是真是假——只是登记「区间内没有第二个来源」。",
    },
    {
        "id": "K06",
        "whoKnows": "区间内没有人知道——原文没有写杨砚的态度。",
        "whoDoesNot": "六名金锣：他们只应下「一言为定」，还没去找杨砚。",
        "what": "杨砚愿不愿意放人。",
        "resolution": "区间内未闭合（交涉发生在区间外）。",
        "basis": "explicit",
        "quotes": A("L_AGREED", "L_WEI_SHAKE"),
    },
    {
        "id": "K07",
        "whoKnows": "魏渊与在场金锣。",
        "whoDoesNot": "楼下的打更人与侍卫、楼内吏员——他们只看到「雷声」与人群聚集。",
        "what": "那一吼的来源与许七安的实力。魏渊当场下令「这件事你们知道就成，不许外传」，说明这个信息差是被有意维持的。",
        "resolution": "区间内未闭合（封口令刚下，是否守住发生在区间外）。",
        "basis": "derived",
        "quotes": A("L_WEI_DISMISS", "L_ZHANG_LOOKOUT"),
    },
    {
        "id": "K08",
        "whoKnows": "小宦官（他知道井中捞出女尸这件事）。",
        "whoDoesNot": "许七安——他在本章最后一句才听到；两人都不知道女尸的身份与案情。",
        "what": "女尸是谁、怎么死的、是否命案。",
        "resolution": "区间内未闭合（下一单元才展开）。",
        "basis": "explicit",
        "quotes": A("L_CORPSE", "L_ON_HORSE"),
    },
]


FORESHADOWS = [
    {
        "id": "F01",
        "name": "「发誓」这个动作被递给二郎与许平志",
        "setup": "许七安刚用一句窄誓过关，就怂恿妹妹「回家后你也可以这般质问二郎」；婶婶自信二郎不会去，"
                 "心里却已经开始打算当晚照样质问许平志。",
        "setupQuotes": A("L_OATH", "L_URGE", "L_AUNT_CONFIDENT"),
        "status": "partial",
        "payoff": "区间内只兑现到「婶婶决定当晚质问」这一步。",
        "unresolvedWhat": "许平志当晚是否被质问、他敢不敢发誓、结果如何——都在区间外。",
        "basis": "explicit",
        "note": "判 partial 而不是 resolved-in-range：决心已经写下（可核），兑现没有。",
    },
    {
        "id": "F02",
        "name": "浮香「好转」的表象",
        "setup": "渡气一刻钟后脸色大有好转、自称好多了，三名丫鬟也露出喜色；许七安还许诺明日再来看她。",
        "setupQuotes": A("L_QUARTER", "L_FX_BETTER", "L_MAIDS_HAPPY"),
        "status": "resolved-in-range",
        "payoff": "他一走、丫鬟一退、门一关，她「原本已经好转的脸色，迅速颓败下去」，房里只剩一声叹息。",
        "payoffQuotes": A("L_AFTER_LEAVE", "L_DOOR", "L_SIGH"),
        "basis": "explicit",
        "note": "回收在区间内完成（表象被推翻）；但**成因**原文没写，见 U02，不作「装病」结论。",
    },
    {
        "id": "F03",
        "name": "许七安许诺「我明日再来看你」",
        "setup": "离开影梅小阁前，他捏了捏浮香的脸蛋，说「好好休息，我明日再来看你」。",
        "setupQuotes": A("L_BYEBYE"),
        "status": "unresolved",
        "unresolvedWhat": "次日他是否去了影梅小阁——区间里的次日只写「离开青池院，骑着马来到皇宫」，没有兑现这一句。",
        "basis": "explicit",
        "note": "有明确的未来意向（明日）＋未兑现，才写 unresolved；单次背景描写不按伏笔处理。",
    },
    {
        "id": "F04",
        "name": "金锣要自己去找杨砚要人",
        "setup": "魏渊把交涉推给不在场的杨砚，六名金锣齐声应下「一言为定」；许七安随即祈祷杨砚迟些回京，"
                 "并预想他回京要面对同僚的拳头与姜律中的背刺。",
        "setupQuotes": A("L_SIX", "L_AGREED", "L_PRAY", "L_IMAGINE"),
        "status": "unresolved",
        "unresolvedWhat": "杨砚何时回京、他是否会放人、同僚是否真的为此动手——全部在区间外。",
        "basis": "explicit",
        "note": "「拳头」「背刺」是许七安的预想（原文用「试想」引出），只能当铺设，不能当已发生的事（U10）。",
    },
]


NOTFORESHADOWS = [
    {
        "id": "NF01",
        "name": "井中女尸",
        "why": "区间内只出现一次，且在最后一句；它的回收在下一单元（第十五章 黄小柔）。按本任务判据（要有铺设＋回收），"
               "它在本区间不构成伏笔。已记 U07，留给下一单元。",
        "quotes": A("L_CORPSE"),
    },
    {
        "id": "NF02",
        "name": "明砚的家世（父亲站错队被清算流放、她被充入教坊司）",
        "why": "一段背景交代，区间内没有对应的回收动作，也没有像 F03/F04 那样的未来意向或未兑现承诺；"
               "「单次出现」不足以判伏笔。若后续卷里回收，本候选会漏一条，这是这一判据的代价。",
        "quotes": A("L_MY_FATHER"),
    },
    {
        "id": "NF03",
        "name": "吕青对许七安「有点意思」",
        "why": "这只是许七安自己的猜测（「吕青好像对我有点意思？」），区间内没有第二处独立证据；"
               "把单次猜测当伏笔就是把说法当事实。他随后自己收束了这条线（「这事儿，许七安肯定做不到」）。",
        "quotes": A("L_GOOD_GIRL", "L_CANT"),
    },
    {
        "id": "NF04",
        "name": "赵家「背后的靠山也不小」",
        "why": "这句话只是在解释赔偿为何只有一百两，区间内没有后续指向，也没有第二次出现。",
        "quotes": [SG("L_DESERVE", "可惜只有一百两", "靠山也不小。")],
    },
    {
        "id": "NF05",
        "name": "脱胎丸",
        "why": "它是用来解释已经发生的容貌变化（既成事实的说明），不是铺设；区间内没有关于它的后续动作。",
        "quotes": A("L_PILL"),
    },
    {
        "id": "NF06",
        "name": "教坊司「老油条才能混的风生水起」的议论",
        "why": "叙述者的一段议论，不指向任何具体后文事件。",
        "quotes": A("L_PLACE_RULE"),
    },
]


WORLDSETTINGS = [
    {
        "id": "W01",
        "kind": "place",
        "name": "浩气楼（七楼茶室/瞭望厅）",
        "placeState": "arrived",
        "quote": A1("L_ARRIVE"),
        "stateEvidence": A("L_ARRIVE", "L_LEAVE_LOU"),
        "stateEvidenceWhy": "有明确的到达动作（金锣的身影「出现在七楼」）与离开动作（许七安「告退离开浩气楼，返回春风堂」），故记 arrived。"
                            "它是本区间前半段的现场：测试的余波、争人、封口令都发生在这里。",
        "explain": "地点约束：魏渊在这里当众处置人事与消息（把人留在杨砚麾下、下令不许外传），"
                   "金锣与楼内吏员都在场——这解释了为什么争人是当着众人发生的，也解释了封口令必须当场下。",
        "basis": "explicit",
    },
    {
        "id": "W02",
        "kind": "place",
        "name": "春风堂",
        "placeState": "arrived",
        "quote": A1("L_LEAVE_LOU"),
        "stateEvidence": A("L_LEAVE_LOU", "L_CLERK"),
        "stateEvidenceWhy": "「返回春风堂」是到达动作；随后「春风堂的吏员进来禀报」表明他人在堂内。故 arrived。",
        "explain": "地点约束：它是许七安的办公处，家人在这里等他、吏员在这里通报访客——"
                   "所以婶婶与许玲月的话、以及吕青的到访都发生在这个半公开的场合。",
        "basis": "explicit",
    },
    {
        "id": "W03",
        "kind": "place",
        "name": "青云堂（他原本要去取金牌的地方）",
        "placeState": "mentioned",
        "quote": A1("L_SEND_OFF"),
        "stateEvidence": A("L_SEND_OFF"),
        "stateEvidenceWhy": "只有「打算回青云堂」这个图谋，紧接着金牌被送回来，他并没有去；区间内没有出现任何到达青云堂的动作。"
                            "按「图谋≠到达」记 mentioned。",
        "explain": "这个「没去成」正是本区间行动链的一环：因为金牌被吕青送回，他省了一趟，"
                   "会面改在春风堂发生（见 CE09）。把它记成 arrived 会把一次未执行的打算写成已发生的事。",
        "basis": "explicit",
    },
    {
        "id": "W04",
        "kind": "place",
        "name": "教坊司",
        "placeState": "arrived",
        "quote": A1("L_SUNSET"),
        "stateEvidence": A("L_SUNSET", "L_TONIGHT"),
        "stateEvidenceWhy": "「进了教坊司」是到达动作，随后他在影梅小阁与青池院两处停留，故 arrived。",
        "explain": "地点约束：它解释了为什么他当晚「不回家了」（原话在 stateEvidence 里锚定），"
                   "也让他白天对妹妹发的誓（只否认花银子）在字面上仍然成立；"
                   "同时它划定了吕青不能去的地方——她婉拒喝酒的理由是「我毕竟是女子」（见 supportQuotes）。",
        "supportQuotes": A("L_DECLINE", "L_IF_MAN"),
        "basis": "explicit",
    },
    {
        "id": "W05",
        "kind": "place",
        "name": "影梅小阁（浮香处）",
        "placeState": "arrived",
        "quote": A1("L_BYEBYE"),
        "stateEvidence": A("L_BYEBYE", "L_AFTER_LEAVE"),
        "stateEvidenceWhy": "「离开影梅小阁」是离开动作，说明他此前确实在场；且他走后浮香才开始遣人，故 arrived。",
        "explain": "地点约束：这是本区间唯一一个「他以为自己在照顾人、实际被瞒住」的现场——"
                   "他的渡气与许诺发生在这里，浮香的独处与颓败也发生在这里。",
        "basis": "explicit",
    },
    {
        "id": "W06",
        "kind": "place",
        "name": "青池院（明砚处）",
        "placeState": "arrived",
        "quote": A1("L_QINGCHI"),
        "stateEvidence": A("L_QINGCHI", "L_ALLNIGHT", "L_CLOSE_GATE"),
        "stateEvidenceWhy": "「扭头去了青池院」是到达动作，并在此留宿至三更半夜，故 arrived。",
        "explain": "地点约束：它紧接影梅小阁之后，构成同一晚的两站；「关院门，今晚不打茶围了」这条吩咐只在这个地点有约束力（见 T07 的 cost）。",
        "basis": "explicit",
    },
    {
        "id": "W07",
        "kind": "place",
        "name": "皇宫（宫门外）",
        "placeState": "arrived",
        "quote": A1("L_NEXTDAY"),
        "stateEvidence": A("L_NEXTDAY", "L_EUNUCH_PACE"),
        "stateEvidenceWhy": "「骑着马来到皇宫」是到达动作，随后写他在宫门不远处看见小宦官，故 arrived。",
        "explain": "地点约束：他有「监督他的小宦官」在宫门等，说明他每日入宫是既有差事，"
                   "所以女尸这条消息是在他上班路上被递进来的，而不是他主动去查的。",
        "basis": "explicit",
    },
    {
        "id": "W08",
        "kind": "place",
        "name": "云州",
        "placeState": "mentioned",
        "quote": A1("L_ZHANG_PROBE"),
        "stateEvidence": A("L_ZHANG_PROBE", "L_HALFMONTH"),
        "stateEvidenceWhy": "云州在本区间只出现在金锣的追问与对晋升时点的追述里，没有任何到达动作（他人在京城），故 mentioned。",
        "explain": "它约束的是资历这件事：因为晋升发生在云州、且只有半个多月，"
                   "金锣们才能用「时间这么短、波动却这么强」来推断他的天资——这是争人的算法基础。",
        "basis": "explicit",
    },
    {
        "id": "W09",
        "kind": "place",
        "name": "井（捞出女尸处）",
        "placeState": "mentioned",
        "quote": A1("L_CORPSE"),
        "stateEvidence": A("L_CORPSE"),
        "stateEvidenceWhy": "井只出现在小宦官的转述里，区间内没有任何人到过现场，故 mentioned。"
                            "它与青云堂同属「提到不等于到达」，但性质不同：青云堂是本人未执行的打算，井是他人转述的别处。",
        "explain": "它决定了本章的收束方式：一条从别处递来的消息把下一单元的任务抛出来，"
                   "而本区间结束时没人知道死者是谁（K08）。",
        "basis": "explicit",
    },
    {
        "id": "W10",
        "kind": "item",
        "name": "金牌",
        "itemStates": ["hold", "transfer"],
        "quote": A1("L_LV_MEDAL"),
        "stateEvidence": {
            "hold": A("L_MEDAL_NOT"),
            "transfer": A("L_LV_MEDAL"),
            "use": None,
            "lose": None,
        },
        "itemStatesNote": "四态分开判定：hold——他拿到后「把金牌丢在桌上」，仍是持有状态；transfer——吕青「从怀里摸出金牌」当面送还，"
                          "占有从她转到许七安；use——区间内没有把金牌当凭证使用的动作（他只说「金牌不重要」）；"
                          "lose——区间内没有丢失。「丢在桌上」是随手放置，不是遗失，故不记 lose。",
        "explain": "它在本区间的作用是让吕青有一个上门的正当理由：他把牌丢开、说金牌不重要，"
                   "于是这次会面从公事交接转成私交试探（CE10）。",
        "basis": "explicit",
    },
    {
        "id": "W11",
        "kind": "item",
        "name": "紫金锤",
        "itemStates": ["hold"],
        "quote": A1("L_BURLY"),
        "stateEvidence": {
            "hold": A("L_BURLY"),
            "transfer": None,
            "use": None,
            "lose": None,
        },
        "itemStatesNote": "只有 hold 一态有依据：他「手持」紫金锤。use——区间内他没有任何挥锤/出手的动作（后来判断「但是完全没有」）；"
                          "transfer/lose——区间内没有交出或丢失。",
        "supportQuotes": A("L_CALM", "L_NOCRISIS"),
        "explain": "它是「如临大敌」这个误判的外化：持锤扫视的架势与随后「整个浩气楼风平浪静」形成落差，"
                   "支撑了 CE01 的排除过程。",
        "basis": "explicit",
    },
    {
        "id": "W12",
        "kind": "item",
        "name": "百两银票",
        "itemStates": ["hold", "transfer"],
        "quote": A1("L_AUNT_SOFT"),
        "stateEvidence": {
            "hold": A("L_SUNNY"),
            "transfer": A("L_AUNT_SOFT"),
            "use": None,
            "lose": None,
        },
        "itemStatesNote": "hold——许七安「从怀里掏出一张百两银票」（先由他持有），之后婶婶「收好银票」（转由她持有）；"
                          "transfer——「接过银票」是交付动作；use——区间内没有把它花出去、兑换或用于办事；lose——没有丢失。"
                          "四态分开写，没有把它合成一条「物品链」。",
        "supportQuotes": A("L_AUNT_WHY"),
        "explain": "它在本区间是唯一被明确定价的资源：一百两换来了婶婶的态度转缓（CE06），"
                   "也解释了他为什么能用「赵家的赔偿金」把私塾的事封住。",
        "basis": "explicit",
    },
    {
        "id": "W13",
        "kind": "rule",
        "name": "气机可以疏通脉络、治病（本区间被实际执行）",
        "institution": "executed",
        "quote": A1("L_RULE_QI"),
        "supportQuotes": A("L_RULE_QI", "L_TRANSFER", "L_MED_FAIL"),
        "explain": "它解释了许七安能做什么：他不必请医、不必用药，握住手腕渡气即可治病——"
                   "所以他进门后拒绝寻欢、直接渡气；丫鬟的对照（「娘子喝了药也不见好，许公子一来，气色马上好转」）也说明这是常规医药之外的手段。"
                   "⚠️ 但原文这条规则说「区区风寒，不在话下」，而同一晚他走后浮香的脸色就迅速颓败（U02）：规则与现象之间存在张力，"
                   "本候选只登记张力，不替原文补解释。",
        "basis": "explicit",
    },
    {
        "id": "W14",
        "kind": "rule",
        "name": "魏渊的封口令",
        "institution": "executed",
        "quote": A1("L_WEI_DISMISS"),
        "supportQuotes": A("L_YES", "L_LEAVE_LOU"),
        "explain": "它解释了在场金锣**不能**做什么：不许把那一吼的事传出去。当场的执行动作是金锣齐声应「是」，"
                   "随后外头的侍卫与打更人散去。这条命令同时造成了 K07 的信息差。"
                   "命令在区间外是否被遵守，原文没写，不作结论。",
        "basis": "explicit",
    },
    {
        "id": "W15",
        "kind": "rule",
        "name": "人员归属：要人须经现任上官（杨砚）",
        "institution": "declared",
        "quote": A1("L_WEI_SHAKE"),
        "supportQuotes": A("L_AGREED", "L_SIX"),
        "explain": "它解释了在场金锣**能做什么、不能做什么**：他们不能凭魏渊一句话把人要走，只能自己去找杨砚；"
                   "魏渊能决定的只是不在这里改归属。金锣们的回应「一言为定」是接受这个条件。"
                   "记 declared 而不是 executed：区间内只有这条当众给出的条件与接受，真正去找杨砚的动作发生在区间外（K06）。",
        "basis": "explicit",
    },
    {
        "id": "W16",
        "kind": "rule",
        "name": "「魏公身边有阴影高手护卫」的传闻",
        "institution": "misunderstood",
        "quote": A1("L_RUMOR"),
        "supportQuotes": A("L_SORRY", "L_GUESS", "L_SECOND", "L_NOT_NEW"),
        "explain": "这是**人物群体**的理解，不是叙述事实：它解释了金锣们为什么把那一吼归给别人、"
                   "为什么一进门就请罪「竟未发现有外敌入侵」，也解释了许七安为什么没有被联想到——"
                   "他们宁可相信一个传闻中的护卫，也不相信一个刚晋升半个多月的年轻人（CE01）。"
                   "本区间没有给这条传闻任何证实；紧接着那句「谁都没有联想到许七安」正是这个理解的后果。",
        "basis": "explicit",
    },
]


NOTWORLDSETTINGS = [
    {
        "id": "NW01",
        "name": "金锣 / 打更人 / 花魁 / 总捕头等身份称谓",
        "why": "这些称谓在本区间只用于称呼人，没有出现任何一条「因为身份所以能做/不能做某事」的明确约束条文；"
               "按计划「没有依据就不扩出术语装饰层」，不单列为世界设定。"
               "其中唯一影响行动的是人员归属（W15），已单独收录。",
    },
    {
        "id": "NW02",
        "name": "「良家女子的世界不是你想进就进，想出就出」",
        "why": "这是许七安心里的一句牢骚式比喻（紧接着就是「你得不停的进进出出」的双关），不是规则；"
               "它没有约束任何人的行动，只表达他自己的退意。",
        "quotes": A("L_GOOD_GIRL"),
    },
    {
        "id": "NW03",
        "name": "「院子里的姑娘，许郎随意挑便是」",
        "why": "这是浮香的一句话（她的主张），而且当场被许七安拒绝；它既不是规则，也没有被执行成任何行动。"
               "人物的话只能当线索。",
        "quotes": A("L_FX_OFFER"),
    },
    {
        "id": "NW04",
        "name": "教坊司的地形/格局（影梅小阁、青池院的具体位置）",
        "why": "区间内只有点名，没有可用于行动的距离、门禁、路线描述；不扩地图。",
    },
]


THEMEREADINGS = [
    {
        "id": "TH01",
        "perspective": "以「被看见的版本」为轴读这一章：几乎每个主要人物都在管理别人看到的东西，而这一章反复把「看到的」与「实际的」并排摆出来。",
        "support": "①许玲月刚刚被吓得面如土色，却「在大哥面前，她要保持完美形象」；②浮香当面「大有好转」，人一走、门一关就「迅速颓败下去」；"
                   "③许七安当众认下那一吼，同时把「死之前最后一刻才晋升」摆出来，实际效果是让金锣们更想要他；"
                   "④他自己也知道那串情话不负责任（「我越来越得心应手了」），明砚却听得眼眶湿润。",
        "supportQuotes": A("L_PERFECT", "L_USE_FAMILY", "L_DOOR", "L_ASHAMED", "L_MY_MOVED"),
        "counter": "反例同样在同一区间：①吕青不掩饰——她「秀气的眸子死死盯着许七安」，若他脸上有不悦就准备道歉走人，情绪是可读的；"
                   "②魏渊的封口令是当众下的，它收紧信息但不是伪装；③最关键的是，浮香脸色颓败的**原因**原文完全没写（U02），"
                   "把它读成「她在演」是解释而不是事实——把它读成病情另有内情同样没有依据。",
        "counterQuotes": A("L_WATCH", "L_WEI_DISMISS"),
        "basis": "inferred",
        "note": "本条是可选读法，不是唯一真相；框架只用「可见/实际」这一组对立，没有套三幕或英雄旅程。",
    },
    {
        "id": "TH02",
        "perspective": "以「一个人值多少」为轴读：这一章反复用可计价的东西来衡量人，并且把不同性质的交换并排放在同一章里。",
        "support": "①金锣们对许七安的估价在一瞬间完成——从「半个多月」的资历跳到「这份天资，委实有些惊人了」，随即六人开口要人；"
                   "②婶婶的态度由一百两银票转缓（「接过银票，看着他，有些感动」）；"
                   "③明砚的取向从「看中他的才华」转为「有些馋他身子」；④教坊司本身就是个买卖场所，他在这里用气机换情意。",
        "supportQuotes": A("L_TALENT", "L_SIX", "L_AUNT_SOFT", "L_LUST"),
        "counter": "反例：①他对吕青划的那条线不是交易逻辑——「吕青是良家女子，和教坊司姑娘不同」，并且自认「这事儿，许七安肯定做不到」；"
                   "②他对婶婶说的是「都是一家人」，用的是亲属话术而不是价钱；③而且这几处（编制、家务、情欲）性质并不相同，"
                   "把它们并置是我的读法，原文从未把它们联系起来——单独看，任一处都可以解释成别的东西。",
        "counterQuotes": A("L_GOOD_GIRL", "L_CANT", "L_FAMILY"),
        "basis": "inferred",
        "note": "本条与 TH01 是并列的两种读法，不互相排斥；两条都不声称是原文的主题陈述。",
    },
]


TEXTUALNOTES = [
    {
        "id": "TN01",
        "topic": "「宁采臣」",
        "note": "原文「搞什么鬼，我又不是宁采臣......」是许七安的心理吐槽。宁采臣是《聊斋志异·聂小倩》里的人物（**外部知识，非原文证据**），"
                "此处与「女鬼」相关的联想属于本书的跨文本梗；本候选不对这个梗做世界观推断。",
        "quotes": A("L_ADMIT"),
    },
    {
        "id": "TN02",
        "topic": "「管鲍之交」与「拉丁舞」「办公室」",
        "note": "这三处都是现代词/典故被放进古代背景（管鲍之交的典故、拉丁舞、「办公室」），属于本书的穿越梗写法。"
                "照原文逐字引用，不改写；也不据此推断世界观（见 notWorldSettings）。",
        "quotes": A("L_MY_DESC", "L_LATIN", "L_INVITE"),
    },
    {
        "id": "TN03",
        "topic": "「我要和人开发两座山峰，一条峡谷，投资几十亿金子」",
        "note": "这是许七安对「今晚有事」的内心戏谑，指去教坊司；「两座山峰/一条峡谷」是身体隐喻。照原文引，不翻译成现代白话。",
        "quotes": A("L_MOUNTAIN"),
    },
    {
        "id": "TN04",
        "topic": "「脱胎丸」",
        "note": "用来解释容貌变化的一个物名，原文在本区间只出现在他的一句自述里（「在云州服用了脱胎丸，这才死里逃生」），"
                "没有说明它的来源、机制或代价——本候选也不替它补（K05、U05）。",
        "quotes": A("L_PILL"),
    },
    {
        "id": "TN05",
        "topic": "「气机」与「区区风寒，不在话下」",
        "note": "叙述给了一段作用说明（疏通脉络、激活生机、滋养脏腑、抵抗力倍增），但同一晚浮香独处后脸色就颓败。"
                "这条规则与现象之间的张力原文没有解释（U02）；本候选不作补写。",
        "quotes": A("L_RULE_QI", "L_DOOR"),
    },
    {
        "id": "TN06",
        "topic": "「打更人和侍卫都聚集在楼下了」",
        "note": "本区间没有写他们聚集的原因（是否与那一声吼有关）；只说聚集，随后被散去。"
                "把它当成「吼声引来」是归纳，本候选只在 T09 的 obstacleNote 里标明这一点，不写成因果边。",
        "quotes": A("L_ZHANG_LOOKOUT"),
    },
]


UNKNOWNS = [
    {
        "id": "U01",
        "what": "许七安在等的「魏渊的回复」是什么事的回复。",
        "why": "开篇只写「许七安没等来魏渊的回复」，本区间没有交代请求内容；随后金锣到场打断了这条线，它在本区间没有下文。",
        "quotes": A("L_ARRIVE"),
    },
    {
        "id": "U02",
        "what": "浮香独处后脸色为什么迅速颓败——是病情另有内情、好转只是暂时，还是别的。",
        "why": "原文只写现象与顺序（确认他走后→遣人→关门→颓败→叹息），没有写成因；叙述对气机的评价是「区区风寒，不在话下」，"
               "与现象冲突。不能据此断定她装病，也不能断定气机无效。",
        "quotes": A("L_RULE_QI", "L_DOOR", "L_SIGH"),
    },
    {
        "id": "U03",
        "what": "「刚才那一吼」的具体情形（何时、为何、魏渊如何测试）。",
        "why": "本区间只由许七安的一句话与金锣们的反应转述，事件本身发生在区间之外（上一单元或本章之前）。",
        "quotes": A("L_ADMIT", "L_NOT_NEW"),
    },
    {
        "id": "U04",
        "what": "百两银票是否真出自赵家、私塾的事如何了结。",
        "why": "只有许七安一句话（P03），婶婶与许玲月只是接受；本区间没有第三方证据。",
        "quotes": A("L_SUNNY"),
    },
    {
        "id": "U05",
        "what": "「我是在死之前最后一刻，才晋升炼神境的」里的「死」指什么，以及脱胎丸与此的关系。",
        "why": "他只说了这一句，本区间没有展开；听他说话的金锣们也没有追问这一句。",
        "quotes": A("L_DONT_MISREAD"),
    },
    {
        "id": "U06",
        "what": "他对明砚讲的云州战功是否属实。",
        "why": "本区间没有对照材料，也没有第三方在场可核实；它是单一信源的自述（P05）。",
        "quotes": A("L_WAR1", "L_WAR2"),
    },
    {
        "id": "U07",
        "what": "井中女尸的身份、死因与案情。",
        "why": "本区间只有小宦官一句转述，且是「昨夜」发生的事；本章到此为止。回收应在下一单元。",
        "quotes": A("L_CORPSE"),
    },
    {
        "id": "U08",
        "what": "明砚父亲「站错队」的具体阵营与年份。",
        "why": "原文只写「第二年」，基准年没写；「站错队」也只给了结果（清算、流放三千里），没给对象。",
        "quotes": A("L_MY_FATHER"),
    },
    {
        "id": "U09",
        "what": "金牌此前为什么在府衙捕手手里、朱捕头被召回的经过。",
        "why": "吕青只说「府衙的捕手与我说了私塾的事，我做主让朱捕头回去了」，中间经过没有写（P07）。",
        "quotes": A("L_LV_MEDAL"),
    },
    {
        "id": "U10",
        "what": "杨砚回京后是否真的会发生同僚争抢与姜律中的背刺。",
        "why": "这是许七安的预想（原文用「试想」引出），不是已发生的事；区间内没有任何人确认。",
        "quotes": A("L_IMAGINE", "L_PRAY"),
    },
    {
        "id": "U11",
        "what": "婶婶当晚是否真的质问许平志、结果如何。",
        "why": "本区间只写到她的打算（「心里想着」），兑现发生在区间外。见 F01 的 unresolvedWhat。",
        "quotes": A("L_AUNT_CONFIDENT"),
    },
    {
        "id": "U12",
        "what": "许七安发誓「从未在教坊司花过银子」是不是有意规避；以及「花银子」与「去过」在他这里是否真的可分。",
        "why": "两处措辞的差值是原文可核的（见 P04 与 W04 的引文），但原文没有写他的动机；他当晚确实进了教坊司。"
               "本候选只登记差值，不判定他在说谎。",
        "quotes": A("L_OATH", "L_SWEAR_DEMAND"),
    },
    {
        "id": "U13",
        "what": "魏渊为什么要让人测试许七安的元神强度。",
        "why": "本区间只有许七安转述的那句「刚才魏公要测试我元神强度」，魏渊本人没有说明用意；他只在许七安看他时「颔首」。",
        "quotes": A("L_ADMIT"),
    },
]


SELFCRITIQUE = [
    {
        "id": "SC01",
        "risk": "把浮香的「颓败」读成她在演、或读成病情另有内情。",
        "why": "原文只给现象与顺序（确认他走后→遣人→关门→颓败→叹息），成因没有写；同一段还给了「气机能…区区风寒，不在话下」的相反评价。",
        "still": "我仍然把它写成 S04 与 CE08：因为「好转」与「颓败」两处都是直述，且「确认他走后」这个前提是原文自己加的；"
                 "但我把 basis 标 derived、只主张顺序不主张成因，并把成因单列为 U02。",
    },
    {
        "id": "SC02",
        "risk": "把金锣们「想要许七安」写成 T01 的 objective。",
        "why": "原文没有一句直说他们要人；我是从「目光愈发炽烈」「齐声道：魏公.....」「一言为定」归纳的。",
        "still": "我仍这么判断：这几处动作连起来只支持争夺这一种读法（其中「一言为定」是对「自己找杨砚去」这个条件的接受）；"
                 "但 objectiveBasis 标为 inferred，并在 objectiveNote 里写明「若复核要求直述，本栏应改 null」。",
    },
    {
        "id": "SC03",
        "risk": "把「其中两人还是老熟人」读成「与许七安是老熟人」。",
        "why": "这句紧跟在金锣们上场之后，没有写明与谁相熟；后文南宫倩柔直接点他名字、他也能与金锣们对话，指向与许七安相熟。",
        "still": "我按「与许七安是老熟人」理解（否则南宫倩柔那句「刚才是不是你在搞鬼」缺少由头），"
                 "但我没有把这条理解写成任何一条断言——它只影响叙事连贯性，不影响任何五元组栏位。",
    },
    {
        "id": "SC04",
        "risk": "把许七安的誓言读成有意规避（换一个自己守得住的措辞）。",
        "why": "原文只给了两句不同的措辞，没有任何心理描写；也可能他只是随口。",
        "still": "我在 CE07 里只主张「措辞不同」这个可核事实，把「有意」的部分明确标为「原文没有写，由我补」，并列进 U12。",
    },
    {
        "id": "SC05",
        "risk": "把教坊司写成 arrived、把青云堂写成 mentioned，标准是否一致。",
        "why": "两者的差别只在有无到达动作：他有「进了教坊司」；青云堂只有「打算回」，紧接着金牌被送回、他没去。",
        "still": "我仍这么分：判据是动作而非意图，且两处都在 stateEvidenceWhy 里写明了依据，复核可以直接推翻其中任一条。",
    },
    {
        "id": "SC06",
        "risk": "把 T08 的 result 写成「消息送达」。",
        "why": "原文止于小宦官那句话，女尸之事本身完全未核实；若 result 写成「发现命案」就是把转述当事实。",
        "still": "我在 result 的正文与 resultNote 里都把 result 限定为「他把这句话说出来了」，"
                 "并把女尸本身列进 U07 与 NF01（本区间不构成伏笔）。",
    },
]
