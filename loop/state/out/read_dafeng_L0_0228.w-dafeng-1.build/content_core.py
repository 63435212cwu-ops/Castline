# -*- coding: utf-8 -*-
"""内容源：只写**结论文本 + 引文键**，不含任何手写数字偏移。

偏移由 gen_quotes.py 在 docs[0].text 里 find 出来（见 build_candidate.py 的展开步骤）。

读法口径（本单元最重要的三条）：
  1. **四封信是「他人之言」**。玲月、浮香、临安、怀庆的信都以引号成段出现，与人物台词同层。
     信里的内容只能承担「信上这样写」，**不能**当叙述事实。信里转述的第三人之言
     （如婶婶去质问先生、临安跑去司天监闹事）离事实更远一层，登记为 letter 层。
  2. **本单元是三条线剪在一起**：棺中醒来（P001–P062）、读信（P063–P134）、
     套话与宫城（P135–P176）。三条线在区间内**没有**互相影响，除许七安本人。
  3. **结尾没有结果**。区间止于魏渊入列、群臣以晦涩眼神看他；小朝会议了什么、
     八百里加急说的什么、杨千幻为何否认抓梁有平，一个字都没写。按「结束≠成功」记 null。

五元组（objective/obstacle/action/result/cost）逐栏独立给依据；同一条任务的五栏
**不得共用同一句原文**（build_candidate.py H5 强制），某栏确无依据则写 null 并附
同名 `<栏位>Note` 说明为什么没有 —— 不写理由的 null 会被判为未标注的未知。
"""

# ═══════════════════════════════════════════════════════════════════════════
# 1. tasks —— 任务五元组
# ═══════════════════════════════════════════════════════════════════════════
TASKS = [
    {
        "id": "t1_xu_asks_where_he_is",
        "name": "许七安从棺中醒来后，问明自己身在何处",
        "actor": "许七安",
        "actorBasis": "explicit",
        "actorNote": "原文以「他」「许七安」直呼，身份无歧义。",
        "objective": {
            "text": "问出自己在哪里 —— 他刚醒来时只知道自己躺在黑暗里，连身在何处都不知道。",
            "basis": "explicit",
            "quoteKeys": ["q_t1_obj"],
            "note": "这是**台词**（speech 层），只承担「他问过这句话」，不承担答案的真假。"
                    "问句本身即目标的表述：他要的是位置信息。",
        },
        "obstacle": {
            "text": "睁眼看到的仍是黑暗，且棺内气闷；在问出口之前，他只能靠炼神境的精神力「看」东西。",
            "basis": "explicit",
            "quoteKeys": ["q_t1_obs", "q_t1_stuffy"],
            "note": "两处依据分属叙述（q_t1_obs）与转述内心（q_t1_stuffy），都是**第一人称视角的处境**，"
                    "不是别人对他的评价。q_t1_stuffy 的语层登记为 inner：原文「我去，好闷....." "
                    "没有「心想」字样，但是典型的自语口吻（已写进 selfCritique sc2）。",
        },
        "action": {
            "text": "先不动身，凝神细感应；随后推开棺材盖，翻身坐起。",
            "basis": "explicit",
            "quoteKeys": ["q_t1_act", "q_t1_open"],
            "note": "动作链来自三段叙述（P019 / P028 / P029）。q_t1_open 是梦境回忆的收尾句，"
                    "推棺盖这个动作本身写在里面（「许七安心里想着，推开了棺材盖」）。",
        },
        "result": {
            "text": "得到答案：在回京的路上 —— 走的是水路。",
            "basis": "explicit",
            "quoteKeys": ["q_t1_res"],
            "note": "答案是**杨千幻的台词**（speech 层）：它只承担「他这样回答」，"
                    "与叙述独立确认的官船/运河（见 tasks t3 的 obstacle 栏引文 q_see_boat 之外的"
                    "叙述段落）可以互相印证，但本条不拿台词当叙述事实。",
        },
        "cost": None,
        "costNote": "本区间没有为「问明身在何处」写任何代价：他没有付出资源、没有受伤、没有被拒绝回答，"
                    "杨千幻答得颇为轻快（P034）。他在棺中醒来的被动处境是**处境**不是代价，"
                    "记在 obstacle 栏，不在这里充作本栏的代价。",
        "note": "五栏引文两两不同（q_t1_obj / q_t1_obs+q_t1_stuffy / q_t1_act+q_t1_open / q_t1_res / —）。",
    },
    {
        "id": "t2_yang_guards_coffin_for_revival",
        "name": "杨千幻潜入回京官船、开棺查看，并守候许七安复活",
        "actor": "杨千幻",
        "actorBasis": "explicit",
        "actorNote": "原文以「杨千幻」具名；他的动机与心理历程由叙述转述（P042–P048）。",
        "objective": {
            "text": "验证并等待许七安活过来 —— 他判断许七安没死，于是守在棺材边等。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_verify"],
            "note": "**口径声明**：「我便料定你没死」是**结论**不是**目标**。原文没有一句直写他「想要什么」；"
                    "写 null 会丢掉他实际做的整件事，所以我用他自述的判断来承载 objective，"
                    "并在 selfCritique sc3 说明这是本任务最弱的一栏。",
        },
        "obstacle": {
            "text": "那是一条送「尸骨」回京的打更人官船 —— 他只能偷偷溜上去。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_corpse"],
            "note": "这是**台词**（speech 层，杨千幻自述）。它同时含处境（船是打更人送尸骨的）"
                    "与他的应对（溜上来）；我只在本栏用它承担处境那一半，"
                    "应对那一半留给 action 栏的另一处引文，避免一栏跨两义。",
        },
        "action": {
            "text": "一路尾随、潜入官船，打开许七安的棺材板；发现刀伤箭孔诡异修复；随后守在棺材边等了一旬。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_open", "q_yqh_wound", "q_t2_wait"],
            "note": "q_yqh_open 是叙述（P046），q_yqh_wound 与 q_t2_wait 出自他的台词（P041）。"
                    "两处语层不同、内容互相印证，故并列。",
        },
        "result": {
            "text": "等到了：许七安真的活过来了。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_revive"],
            "note": "**语层**：这是杨千幻的台词（「还真就活过来了。」）。但「许七安确实活着」这一点"
                    "另有叙述独立确认（同一区间里许七安醒来、说话、读信、推棺盖），"
                    "所以这条 result 不是只靠台词成立。",
        },
        "cost": {
            "text": "守棺这一旬里他寸步不离，连如厕的时间都没有。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_wait"],
            "note": "原文用「屎都没时间拉」写这件事，是**叙述**（P047）而不是他的自述 ——"
                    "他明确不想让许七安知道（q_yqh_secret）。这是本单元唯一一处写成文字的个人代价，"
                    "量级上属于生活层面的消耗，不是生死代价。",
        },
        "note": "五栏引文两两不同（q_yqh_verify / q_yqh_corpse / q_yqh_open+q_yqh_wound+q_t2_wait / "
                "q_yqh_revive / q_yqh_wait）。",
    },
    {
        "id": "t3_xu_reads_four_replies",
        "name": "许七安在舱底就着微光拆阅怀里四封回信",
        "actor": "许七安",
        "actorBasis": "explicit",
        "actorNote": "原件以「他」「许七安」直呼。",
        "objective": {
            "text": "弄清自己养的三个人里，谁没给他回信。",
            "basis": "explicit",
            "quoteKeys": ["q_backup_goal"],
            "note": "这是转述内心（inner 层）。原文明写他先列出三个人（q_backup_list，见 action 栏外"
                    "的 states s8 与 causeEdges），再发现只回了两封，于是「有些生气」地自问 ——"
                    "目标由这句自问承载。",
        },
        "obstacle": {
            "text": "信是在舱底读的：棺材存放在舱底，只有甲板缝隙漏下微光；但他踏入炼神境后已能在黑夜中视物。",
            "basis": "explicit",
            "quoteKeys": ["q_coffin_hold", "q_darkvision"],
            "note": "两处都是叙述（P059/P061）。这里如实写出「障碍被能力抵消」——"
                    "不把它写成纯障碍，也不因为被抵消就不记，否则会丢掉原文对这条能力的一句正面交代。",
        },
        "action": {
            "text": "随手拆开信封；读完第一封后拆第二封；最后深吸一口气打开第四封。",
            "basis": "explicit",
            "quoteKeys": ["q_letter_open", "q_read_pick", "q_read_last"],
            "note": "三处都是叙述（P060/P093/P107）。它们标出**阅读进程的三个节点**，"
                    "不承担任何一封信的内容真假。",
        },
        "result": {
            "text": "四封信读完，作者认全：第二封是花魁娘子的、最后一封是怀庆的 —— 三个「备胎」里没有褚采薇的信。",
            "basis": "derived",
            "quoteKeys": ["q_huakui_from", "q_read_last_is_hq"],
            "note": "两个身份判定（q_huakui_from、q_read_last_is_hq）是**叙述明写**的 explicit 事实；"
                    "但「没有采薇的信」是我按四封的枚举推的：怀里共四封（P057），第一封玲月（P065 「是玲月妹子的寄来的信」）、"
                    "第二封花魁（本栏引文）、「最后还有两封信」（P090）→ 临安与怀庆。四封各有其主，采薇不在其中。"
                    "这一步是跨段推导，故整栏 basis 取 derived 而非 explicit。",
        },
        "cost": {
            "text": "读到第四封时他被当面点破，臊得面红耳赤。",
            "basis": "explicit",
            "quoteKeys": ["q_read_shame"],
            "note": "叙述（P128）。**为什么算代价**：他是为了弄清「谁没回信」才把四封都读完的，"
                    "而这一读直接换来当场的难堪。代价是情绪/面子层面的，不是物质损失 ——"
                    "量级如实记，不放大成「心理创伤」。",
        },
        "note": "五栏引文两两不同（q_backup_goal / q_coffin_hold+q_darkvision / "
                "q_letter_open+q_read_pick+q_read_last / q_huakui_from+q_read_last_is_hq / q_read_shame）。",
    },
    {
        "id": "t4_huaIQing_writes_warning_letter",
        "name": "怀庆公主写回信提点许七安云州的危险",
        "actor": "怀庆公主",
        "actorBasis": "explicit",
        "actorNote": "信以「许铜锣」开头，落款处由叙述确认为怀庆（q_read_last_is_hq，用在 t3.result，此处不重复）。",
        "objective": {
            "text": "要许七安小心行事、锁定目标就以雷霆之势缉拿，不单独行动。",
            "basis": "explicit",
            "quoteKeys": ["q_hq_careful"],
            "note": "**语层**：letter —— 这是信里的嘱咐原文。它承担「她在信里这样要求」，"
                    "不承担这条战术判断是否正确。",
        },
        "obstacle": {
            "text": "她对魏渊的布局只能推测：猜魏公暗中布局，但多半不会与许七安碰头，张巡抚或许知情、或许不知。",
            "basis": "explicit",
            "quoteKeys": ["q_hq_guess"],
            "note": "letter 层。原文用「我猜」「多半」「或许…或许」三重不确定词 ——"
                    "这正是「障碍」的性质：她能给的是推测，不是情报。",
        },
        "action": {
            "text": "把云州的形势判断写进信里：匪患由来已久、齐党与巫神教秘密谋划多年、必已积蓄势力。",
            "basis": "explicit",
            "quoteKeys": ["q_hq_yunzhou"],
            "note": "letter 层。「写」这个动作本身没有单独的叙述句（信的存在由 P057 的四封与 P113 的身份确认），"
                    "所以本栏用信文内容承担「她写了这些」。这一层口径写在这里，供复核者质疑。",
        },
        "result": {
            "text": "信到了许七安手里，被他读成「提点」——他自认怀庆心里不悦，却仍写信提点他。",
            "basis": "inferred",
            "quoteKeys": ["q_xu_hq_note"],
            "note": "**这是许七安的解读（inner 层），不是叙述对怀庆意图的确认。**"
                    "我把它记为 result 的依据，是因为它能证明的只有「收信人这样理解」；"
                    "把 basis 降为 inferred，正是为了不把收信人的解读升格成写信人的意图。",
        },
        "cost": None,
        "costNote": "本区间没有写怀庆写这封信付出了什么：没有损耗、没有被谁拦、没有后果描写。"
                    "她信里对许七安「一花赠两人」的讥刺记在 states s5 与 causeEdges，"
                    "那是她主动发出的动作，不是她为这封信付出的代价。",
        "note": "五栏引文两两不同（q_hq_careful / q_hq_guess / q_hq_yunzhou / q_xu_hq_note / —）。",
    },
    {
        "id": "t5_xu_traps_yang_over_letters",
        "name": "许七安设套，套出杨千幻偷看过他的信",
        "actor": "许七安",
        "actorBasis": "explicit",
        "actorNote": "叙述以「许七安」具名。",
        "objective": {
            "text": "查证杨千幻是不是偷看了他的信 —— 他先直接质问了一句。",
            "basis": "explicit",
            "quoteKeys": ["q_pos_wary"],
            "note": "**语层混合**：引号内是台词、引号外「许七安一下警惕起来」是叙述。"
                    "本栏只用它承担「他起了疑并当面质问」，不承担「杨千幻确实偷看了」——"
                    "后者由本任务 result 栏与 causeEdges e14 承担。",
        },
        "obstacle": {
            "text": "杨千幻当面否认，而且否认得很硬：「我杨千幻不屑做这等龌龊之事。」",
            "basis": "explicit",
            "quoteKeys": ["q_t3_obs"],
            "note": "speech 层。这句是**被套话者的挡箭牌**，原文随后证明它是假话（result 栏）——"
                    "所以它才能当障碍：正面问是问不出来的。",
        },
        "action": {
            "text": "先顺着对方聊采薇师妹「榆木脑袋、撩不动」，把话题递到采薇与怀庆的往来上；"
                    "等对方主动接话，再突然反问「你特娘的怎么知道她告诉怀庆了？」",
            "basis": "explicit",
            "quoteKeys": ["q_t3_act", "q_t3_res_quote"],
            "note": "两处都是 speech 层。第一句是**饵**（他先说自己给采薇写过信、撩不动），"
                    "第二句是收网。机制见 causeEdges e14；本栏只登记动作。",
        },
        "result": {
            "text": "套出来了：杨千幻张口结舌，随即明白自己被套路 —— 他确实知道采薇告诉了怀庆，"
                    "而这件事只在信里写过。",
            "basis": "explicit",
            "quoteKeys": ["q_t3_res"],
            "note": "叙述（P146）。原文写「知道自己被套路了」——这是**对杨千幻心理的叙述**，"
                    "不是他的台词；他自始至终没有开口承认偷看。所以这条 result 的强度是"
                    "「叙述确认他上套了」，而不是「他承认了」。",
        },
        "cost": {
            "text": "许七安付出的代价是：事情已经发生，他无法追回，只能装作大方、把话咽下去。",
            "basis": "explicit",
            "quoteKeys": ["q_t3_cost"],
            "note": "叙述（P150）。这是**叙述对许七安处境的判断**（「他还能让时光倒流不成」），"
                    "不是他的台词。",
        },
        "note": "五栏引文两两不同（q_pos_wary / q_t3_obs / q_t3_act+q_t3_res_quote / q_t3_res / q_t3_cost）。",
    },
    {
        "id": "t6_aunt_confronts_teacher",
        "name": "婶婶为铃音被抢的玉镯去塾堂找先生质问（玲月信中转述）",
        "actor": "婶婶（许七安的婶母）",
        "actorBasis": "explicit",
        "actorNote": "信中称「娘」；对许七安而言是婶婶（他在 inner 层称「婶婶」，见 q_xu_table）。",
        "objective": {
            "text": "问出是谁干的 —— 家里先问过铃音本人。",
            "basis": "explicit",
            "quoteKeys": ["q_t6_obj"],
            "note": "**这是本单元最弱的一条依据**：q_t6_obj 只截取了「问她是谁干的」，"
                    "主语是家里（含婶婶）而不是婶婶个人。它证明「追问发生过」，"
                    "不能证明追问者是谁。已在 selfCritique sc4 登记。语层 letter。",
        },
        "obstacle": {
            "text": "春祭将近，父亲每日归家很晚、要么宿在外营，无暇管家；婶婶没敢把这件事告诉他。",
            "basis": "explicit",
            "quoteKeys": ["q_springsac", "q_mother_secret"],
            "note": "letter 层，两处都是信文。第一处含因（春祭）与果（父亲无暇），"
                    "第二处是婶婶主动隐瞒 —— 两件事叠加，才解释她为什么只能自己出面。",
        },
        "action": {
            "text": "婶婶自己去找塾堂先生质问。",
            "basis": "explicit",
            "quoteKeys": ["q_t6_act"],
            "note": "letter 层。原文「娘没敢告诉他，自己去找塾堂先生质问」——"
                    "「自己」二字点明她无人可分担。",
        },
        "result": {
            "text": "没问出结果：先生推说不知道，反说是铃音自己弄丢了。",
            "basis": "explicit",
            "quoteKeys": ["q_t6_res"],
            "note": "letter 层。**注意「结束≠成功」**：她去了、问了，但得到的是推脱，"
                    "玉镯没有找回（q_bracelet_gone 见 states s6）。",
        },
        "cost": {
            "text": "婶婶气得浑身发抖，却又无可奈何。",
            "basis": "explicit",
            "quoteKeys": ["q_t6_cost"],
            "note": "letter 层。代价是情绪与无力感，**不是**物质损失：信里没写她为此花了钱或受了伤。"
                    "量级如实记。",
        },
        "note": "五栏引文两两不同（q_t6_obj / q_springsac+q_mother_secret / q_t6_act / q_t6_res / q_t6_cost）。"
                "整条任务的全部依据都在**一封信里**（letter 层），
                "这一点是本任务最大的强度限制：没有任何一句叙述独立确认过这场质问。",
    },
    {
        "id": "t7_lian_raids_sitianjian",
        "name": "临安因「鸡精」署名跑去司天监闹事（临安信中自述）",
        "actor": "临安公主",
        "actorBasis": "explicit",
        "actorNote": "信以「狗奴才」开头，信末由许七安读信时的独白确认为临安（q_la_protect 等段）。",
        "objective": {
            "text": "要为「鸡精不是采薇发明的」讨个说法 —— 她说等许七安回来再带他去讨回公道。",
            "basis": "explicit",
            "quoteKeys": ["q_t7_obj"],
            "note": "letter 层。**注意时态**：这是她许诺的**将来**动作（「等你回来」），不是已完成的事。"
                    "它承载目标，不承载结果。",
        },
        "obstacle": {
            "text": "外头都在传鸡精是司天监的褚采薇发明的 —— 她要对抗的是一句已经传开的说法。",
            "basis": "explicit",
            "quoteKeys": ["q_la_rumor"],
            "note": "letter 层。这条「传言」是她自己在信里说的；原文没有第三方确认这句话真的在传，"
                    "所以它只能当「她认为的处境」（见 selfCritique sc1 的同类风险）。",
        },
        "action": {
            "text": "她气得要死，跑去司天监闹了一场。",
            "basis": "explicit",
            "quoteKeys": ["q_la_raid"],
            "note": "letter 层。**一处「到达」口径**：她自述去过司天监，但这是信里的话，"
                    "本单元没有叙述层面的到达描写（worldSettings w6 因此记 mentioned 而不记 arrived，"
                    "见该条 note）。",
        },
        "result": {
            "text": "没讨到说法，反而升级：司天监的白衣不敢对她出手，跑去父皇那里告状。",
            "basis": "explicit",
            "quoteKeys": ["q_t7_res"],
            "note": "letter 层。这是她自述的**不利结果**，不是成功。",
        },
        "cost": {
            "text": "她为此被父皇狠狠臭骂了一顿。",
            "basis": "explicit",
            "quoteKeys": ["q_t7_cost"],
            "note": "letter 层。代价明确、可量化到「一顿臭骂」；不要把它读成惩罚性后果之外的引申义。",
        },
        "note": "五栏引文两两不同（q_t7_obj / q_la_rumor / q_la_raid / q_t7_res / q_t7_cost）。"
                "整条任务的依据全在临安自己的信里；写信人对自己的行为叙述有立场，"
                "「闹了一场」的具体情节本单元一字未写。",
    },
    {
        "id": "t8_weiyuan_prepares_rhino_armor",
        "name": "魏渊为许七安筹办犀甲",
        "actor": "魏渊",
        "actorBasis": "explicit",
        "actorNote": "叙述以「魏渊」具名；具体操办者是南宫倩柔（q_t4_res 由他作答）。",
        "objective": {
            "text": "为许七安补足最后的短板，给这株尚未长成的树苗保驾护航 —— 方式是送他一件犀甲。",
            "basis": "explicit",
            "quoteKeys": ["q_t4_obj"],
            "note": "叙述（P170），且明写「南宫倩柔知道魏渊的想法」——"
                    "所以这是**经由他人理解的魏渊意图**，不是魏渊自述。这一点已如实写在引文里。",
        },
        "obstacle": {
            "text": "犀甲还不是法器：要再请司天监的炼金术师和阵师出手炼制。",
            "basis": "explicit",
            "quoteKeys": ["q_t4_obs"],
            "note": "叙述（P168）。这是**尚未完成的那一步**，所以本任务在本区间内处于未完成状态。",
        },
        "action": {
            "text": "魏渊在进宫路上问起犀甲的进展。",
            "basis": "explicit",
            "quoteKeys": ["q_ct_sigh"],
            "note": "speech 层为主（引号内是台词），引号外的「魏渊轻叹一声，顿了顿，又道」是叙述。"
                    "本栏只用它承担「他过问进展」这个动作。",
        },
        "result": {
            "text": "得到进度回话：材料已经收集完毕，只等拿去司天监炼制。",
            "basis": "explicit",
            "quoteKeys": ["q_t4_res"],
            "note": "speech 层（南宫倩柔的答话）。**结果不是「犀甲做成了」**："
                    "炼制这一步在本区间没有发生。",
        },
        "cost": None,
        "costNote": "本区间没有写筹办犀甲付出的代价：没有花钱数目、没有工期损失、没有人被拖累。"
                    "南宫倩柔回话时「酸溜溜的语气」是他对魏渊偏心的情绪（记在 states s7 的处境里），"
                    "不是这项筹办的成本 —— 把别人的情绪记成他的代价是换主体。",
        "note": "五栏引文两两不同（q_t4_obj / q_t4_obs / q_ct_sigh / q_t4_res / —）。",
    },
    {
        "id": "t9_court_convenes_over_urgent_report",
        "name": "八百里加急送进宫，元景帝在御书房召开小朝会",
        "actor": "元景帝（召集者）与入列的群臣",
        "actorBasis": "explicit",
        "actorNote": "原文写「陛下就在御书房召开了小朝会」「元景帝也在看着魏渊」；"
                     "本任务的主体是这场朝会，不是某一个臣子。",
        "objective": {
            "text": "议事 —— 八百里加急送来的必然是大事。",
            "basis": "explicit",
            "quoteKeys": ["q_ct_bigdeal"],
            "note": "叙述（P165）。这是叙述对**急报性质的判断**（「必然是大事」），"
                    "不是对具体内容的交代：来自哪一个州、说的是什么，原文没写（unknowns u8）。",
        },
        "obstacle": {
            "text": "这条情报在送入内阁前，除传送情报的驿卒外任何人不得经手，否则视为谋逆 —— "
                    "在朝的君臣都只能等它走完内阁这道手续。",
            "basis": "explicit",
            "quoteKeys": ["q_ct_only", "q_ct_treason"],
            "note": "两处都是叙述（P162/P163）。这是**制度性约束**，也是本单元唯一写明罚则的规则"
                    "（worldSettings w1 的 declared 依据）。",
        },
        "action": {
            "text": "急报送进宫后没多久，陛下在御书房召开小朝会；魏渊跨过门槛进御书房、行礼、入列。",
            "basis": "explicit",
            "quoteKeys": ["q_e11_cause", "q_t5_act2"],
            "note": "q_e11_cause 是叙述（P164 前半），q_t5_act2 是台词+叙述（P176）。"
                    "q_e11_cause 同时是 causeEdges e16 的因句 —— 允许跨分区复用同一键，"
                    "但**同一条任务内**五栏不得互用（本栏与 obstacle/result 栏无重叠）。",
        },
        "result": None,
        "resultNote": "本区间没有写这场朝会的任何结果：没有议出对策、没有下诏、没有结论。"
                      "区间止于魏渊入列、群臣以晦涩眼神看他（q_t5_res2，见 states s7）。"
                      "按「结束≠成功」的口径，不能把「会开了」当结果，更不能把「必有大事」当结论。",
        "cost": None,
        "costNote": "本区间没有写召开这场朝会付出的代价：没有误期、没有损耗、没有人因此获罪。"
                    "那条「否则视为谋逆」是**规则里的罚则**，本区间无人触犯、无人受罚 ——"
                    "规则不等于已执行的后果，故不记为本栏代价（也不记进 result）。",
        "note": "五栏引文两两不同（q_ct_bigdeal / q_ct_only+q_ct_treason / q_e11_cause+q_t5_act2 / — / —）。",
    },
    {
        "id": "t10_xu_identifies_the_dream",
        "name": "许七安判定棺中梦境是山海关战役",
        "actor": "许七安",
        "actorBasis": "explicit",
        "actorNote": "梦境的参与者与判断者都是他；原文以「许七安心里当即有了猜测」明写。",
        "objective": {
            "text": "弄清这场梦的来历 —— 他反复自问为什么会梦到这些。",
            "basis": "explicit",
            "quoteKeys": ["q_dream_why"],
            "note": "转述内心（inner 层）。与 t1 的 objective（问自己身在何处）不同："
                    "这里问的是**梦境的来源**，两栏引文无重叠。",
        },
        "obstacle": {
            "text": "他没有接触过梦里的东西：死尸大军、佛门高僧这些他从没接触过，却梦得极其清晰。",
            "basis": "explicit",
            "quoteKeys": ["q_dream_reality"],
            "note": "inner 层。这句同时否掉了「只是普通的梦」（「梦哪有这般清晰」）——"
                    "所以他面对的是一个自己无法解释的经验。",
        },
        "action": {
            "text": "把梦里的青衣人与魏渊的事迹对起来，据此作出猜测。",
            "basis": "explicit",
            "quoteKeys": ["q_dream_guess"],
            "note": "inner 层，且原文自带连接词「再结合…当即有了猜测」——"
                    "机制由原文给出（人+事迹 → 判定战役），所以这条不是时间相邻。",
        },
        "result": {
            "text": "猜测成形：规模与史书记载的山海关战役完美契合。",
            "basis": "explicit",
            "quoteKeys": ["q_dream_legend"],
            "note": "inner 层。**这是他自己认定的「契合」，不是叙述对梦境的确认**；"
                    "梦境本身的来源在本区间无人解答（unknowns u1）。",
        },
        "cost": None,
        "costNote": "本区间没有为这段推断写任何代价：没有消耗、没有受伤、没有副作用。"
                    "梦境画面随他记起自己而崩溃（causeEdges e2）是**现象**不是代价，"
                    "不在这里充作本栏的依据。",
        "note": "五栏引文两两不同（q_dream_why / q_dream_reality / q_dream_guess / q_dream_legend / —）。"
                "本任务全部依据都是 inner 层（转述内心），强度上限就是「他这样想」。",
    },
]

# ═══════════════════════════════════════════════════════════════════════════
# 2. causeEdges —— 每条必须有方向与触发机制，不因相邻连边
# ═══════════════════════════════════════════════════════════════════════════
CAUSE_EDGES = [
    {
        "id": "e1_recognizing_weiyuan_triggers_memory",
        "from": "梦中认出兽头上的青衣人是魏渊",
        "to": "许七安忽然记起自己是谁",
        "mechanism": "触发是**认出**这个认知动作：原文把「魏渊？！」这一句喊叫直接接在"
                     "「许七安心头一震，忽然记起自己是谁了」之前，用「忽然」与「心头一震」"
                     "把认人写成记忆恢复的扳机。不是时间相邻：在他喊出名字之前，整场梦"
                     "都以「我是谁」的失忆状态叙述（q_amnesia 见 states s1 前值）。",
        "basis": "explicit",
        "quoteKeys": ["q_weiyuan_call", "q_remember_self"],
        "note": "前半是台词（speech 层），后半是叙述。",
    },
    {
        "id": "e2_remembering_collapses_the_dream",
        "from": "许七安记起自己是谁",
        "to": "战场画面崩溃，归于黑暗",
        "mechanism": "**原文只给同时性，不给机制**：它写的是「也就是这个瞬间，战场画面崩溃」——"
                     "「这个瞬间」标的是同一时刻，没有因果连接词，也没有任何机制说明"
                     "（为什么记起自己会让画面崩溃，原文不解释）。我仍然连这条边，方向取"
                     "「记忆恢复在先、画面崩溃在后」的叙述顺序，故 basis 降为 derived。",
        "basis": "derived",
        "quoteKeys": ["q_remember_self", "q_dream_collapse"],
        "note": "这是本候选**唯一一条承认自己只有同时性的边**。若复核者认为同时性不足以连边，"
                "本条应删除，而不是改成 explicit —— 原文确实没写机制。",
    },
    {
        "id": "e3_opening_the_lid_lets_air_in",
        "from": "许七安推开棺材盖",
        "to": "新鲜空气涌入，他深吸一口气、翻身坐起",
        "mechanism": "物理机制：棺盖闭合时棺内气闷（t1.obstacle 栏的 q_t1_stuffy），"
                     "推开盖子才可能有外面的空气进来。原文的语序也是先推盖、后进气。",
        "basis": "explicit",
        "quoteKeys": ["q_t1_open", "q_yqh_wake"],
        "note": "这条边是**物理常识 + 原文语序**共同支撑的，原文没有写「因为…所以…」；"
                "我判它 explicit，是因为棺盖这个物件的作用在原文里被两次触及"
                "（推盖前的气闷、推盖后的进气）。这一处口径请复核者重点看。",
    },
    {
        "id": "e4_healed_wounds_lead_to_vigil",
        "from": "杨千幻开棺后看到刀伤箭孔诡异修复",
        "to": "他料定许七安没死，于是守在棺材边等",
        "mechanism": "原文自带连接词「我便料定」——观察（伤口自行修复）是他判断的直接依据；"
                     "判断之后才有「于是…守在棺材边」的行动。三步都有文字。",
        "basis": "explicit",
        "quoteKeys": ["q_yqh_wound", "q_yqh_verify", "q_yqh_wait"],
        "note": "三个引文分属叙述（q_yqh_wound）与台词（q_yqh_verify / q_yqh_wait）。"
                "机制句「我便料定」在台词里 —— 即机制是**他自述的推理**，不是叙述的旁白。",
    },
    {
        "id": "e5_both_dodge_after_the_dangerous_question",
        "from": "杨千幻问「你怎么做到死而复生的？」（两人各自都有不能说的秘密）",
        "to": "两人同时岔开话题，说起天气",
        "mechanism": "原文把因果写明：「问完，两人望着彼此，陷入了沉默」，接着"
                     "「几秒后，**心虚的**他们又默契的同时岔开话题」——"
                     "「心虚」是连接词：沉默的成因与岔开的动因都是各自的心虚，"
                     "而不是「问句之后正好接了两句天气」。",
        "basis": "explicit",
        "quoteKeys": ["q_revive_q", "q_both_silent", "q_both_topic"],
        "note": "「心虚」的具体内容分属两人（杨千幻怕被知道开棺与守棺、许七安怕被问到死而复生），"
                "原文两边都写了（q_yqh_secret / q_yqh_suspicion，见 states s4），本条不重复引。",
    },
    {
        "id": "e6_darkvision_enables_reading_in_hold",
        "from": "舱底只有甲板缝隙漏下的微光",
        "to": "许七安仍能读信（黑暗中视物毫无障碍）",
        "mechanism": "能力机制：炼神境让他的目力可在黑夜中视物，所以「光弱」这个限制"
                     "对他不成立。原文把能力交代放在读信动作之后（P061–P062），"
                     "是对同一场景的补述，不是另一件事。",
        "basis": "explicit",
        "quoteKeys": ["q_coffin_hold", "q_darkvision"],
        "note": "方向是「能力→限制被抵消」。**不写反**：不是因为光弱才看得见，而是因为有能力才不受光弱限制。",
    },
    {
        "id": "e7_anger_drives_the_raid",
        "from": "临安听说外面把鸡精的发明算在褚采薇头上",
        "to": "她跑去司天监闹了一场",
        "mechanism": "原文自带情绪连接：「本宫气的要死，就跑司天监闹了一场」——"
                     "「气的要死」是她行动的直接动因，句子内部就把因与果连上。",
        "basis": "explicit",
        "quoteKeys": ["q_la_rumor", "q_la_raid"],
        "note": "**语层**：两处都在临安自己的信里（letter 层），所以这是"她自述自己被气得去闹"，"
                "不是叙述对这场闹事的确认。机制成立，事实强度受语层限制。",
    },
    {
        "id": "e8_complaint_escalates_to_scolding",
        "from": "临安在司天监闹了一场",
        "to": "白衣去父皇处告状，她被父皇狠狠臭骂",
        "mechanism": "原文的链条是两步：「司天监的白衣不敢对我出手，竟跑去父皇那里告状」"
                     "（正面冲突被转成上告），「本宫被父皇狠狠臭骂了一顿」（上告产生后果）。"
                     "「竟」字点出这一步出乎她的预料 —— 她以为对方会接招，对方却换了战场。",
        "basis": "explicit",
        "quoteKeys": ["q_la_raid", "q_t7_res", "q_t7_cost"],
        "note": "letter 层。这条边是本单元**唯一一处写明「代价由谁承担」的因果链**："
                "代价落在她自己头上（q_t7_cost 已在 tasks t7.cost 使用，跨分区复用允许）。",
    },
    {
        "id": "e9_lie_believed_yields_silver",
        "from": "许七安骗临安说二叔为供他习武四处举债、日子艰难",
        "to": "临安信以为真，变着法子送他银子",
        "mechanism": "原文自带结果连接：「她竟然就当真了，变着法子送我银子」——"
                     "「竟然」标出轻信，「就当真了」是机制（信了才送）。"
                     "这一条也是他自己承认骗人的自述，等于自证因果。",
        "basis": "explicit",
        "quoteKeys": ["q_lie_told", "q_lie_effect"],
        "note": "inner 层（他的内心独白，含「哈哈哈」的得意）。它同时是一条**人物自陈的欺骗**，"
                "不是叙述对临安智力的评价。",
    },
    {
        "id": "e10_caiwei_shares_so_huaIQing_knows",
        "from": "采薇把许七安寄红莲花瓣、说她「与红莲一样明媚如风」的事告诉了怀庆",
        "to": "怀庆在信里点破「一花赠两人」",
        "mechanism": "信息传递链：采薇转述 → 怀庆得知同一样东西送了两个人、说辞还各不相同 →"
                     "她在信里写「许大人真是风流倜傥，一花赠两人，说辞各不同」。"
                     "两个环节分别在 P120（采薇转述的原话）与 P122（怀庆的讥刺）里写出。",
        "basis": "explicit",
        "quoteKeys": ["q_hq_petal", "q_hq_flower"],
        "note": "两处都是 letter 层（怀庆信里的转述与讥刺）。机制成立；"
                "「许七安确实一花赠两人」这一点由 q_lie_effect 之外的何处独立确认？"
                "—— 只有怀庆这封信。故本条的事实强度受语层限制，见 unknowns u5 的相邻问题。",
    },
    {
        "id": "e11_caiwei_shy_so_huaIQing_ghostwrites",
        "from": "采薇想回信却怕写得不好被笑话（她不爱读书）",
        "to": "怀庆说「本宫替你执笔回信」，她欣然同意",
        "mechanism": "原文自带连接词「我便与采薇说」——「便」把前一句的困境与后一句的提议连起来："
                     "代笔是针对「怕写得不好」这个困难的解决方案。",
        "basis": "explicit",
        "quoteKeys": ["q_hq_caiwei_shy", "q_hq_ghost_write"],
        "note": "letter 层。**注意方向**：是怀庆替采薇写信给许七安，"
                "不是采薇替怀庆写 —— 本单元这一处最容易被读反，故写进 selfCritique sc5。",
    },
    {
        "id": "e12_urgent_report_convenes_court",
        "from": "八百里加急文书送进宫",
        "to": "元景帝在御书房召开小朝会",
        "mechanism": "原文自带时间+因果连接：「八百里加急文书送进宫后，没多久，陛下就在御书房"
                     "召开了小朝会」——「送进宫后，没多久」把两件事排成前后相继，"
                     "「就」承接为响应。这是本单元唯一由叙述直接连出的朝会成因。",
        "basis": "explicit",
        "quoteKeys": ["q_e11_cause", "q_t5_obj"],
        "note": "第二处引文（q_t5_obj）是**同一句的后半**，两句合起来才是完整链条 ——"
                "单引后半会只剩「开了会」这个孤立事实。",
    },
    {
        "id": "e13_gathering_arms_precedes_claiming_credit",
        "from": "临安闹事、白衣上告、她被臭骂（自家吃了亏）",
        "to": "她把「等你回来再带你去讨回公道」写进信里，把讨说法推给将来",
        "mechanism": "机制是**受挫后的推迟**：当下这条路走不通（对方换了战场、她挨了骂），"
                     "于是她把这个目标挪到许七安回京之后。两处依据在同一封信里前后相邻，"
                     "原文没有因果连接词。",
        "basis": "inferred",
        "quoteKeys": ["q_t7_cost", "q_t7_obj"],
        "note": "**这是我推的，不是原文写的**：她完全可能只是随手许诺，与挨骂无关。"
                "故 basis 取 inferred 而非 explicit，并在 rejectedEdges 里保留一条"
                "「单凭相邻不足以连边」的反例说明。",
    },
    {
        "id": "e14_bait_makes_the_peeker_reveal_himself",
        "from": "许七安把话题递到采薇与怀庆的往来上（他先说自己给采薇写信、撩不动）",
        "to": "杨千幻接话附和，暴露自己知道「采薇告诉了怀庆」——而这只写在信里",
        "mechanism": "套话的机制在原文里两步都写全了：① 许七安抛出诱饵（q_t3_act）；"
                     "② 杨千幻「赞同道：采薇师妹的确开窍的晚，她只是当成了寻常朋友的书信往来，"
                     "**才告诉怀庆公主的**」——他主动说出了只有读过信才知道的信息；"
                     "③ 许七安收网反问（q_t3_res_quote）后，叙述确认他「知道自己被套路了」（q_t3_res）。"
                     "触发是**信息不对称**：能让这句附和成立的唯一来源就是那封信。",
        "basis": "explicit",
        "quoteKeys": ["q_t3_act", "q_pos_agree", "q_t3_res_quote", "q_t3_res"],
        "note": "这是本单元机制写得最完整的一条边（原文自己把「被套路了」写出来）。"
                "唯一未写的环节是：他是怎么看到信的（撬棺时顺手看了？）—— 见 unknowns u3 的相邻条目。",
    },
    {
        "id": "e15_denial_invalidates_xus_premise",
        "from": "许七安以「看在你帮我抓住梁有平的份上」为由表示不追究",
        "to": "杨千幻否认「我没帮你们抓梁有平」，许七安打了个冷战",
        "mechanism": "机制是**前提被推翻**：许七安用来交换的筹码（对方帮过忙）被当事人当面否认，"
                     "意味着他手上那件事的因果链有一段是他自己搞错的。原文用环境侧写收尾"
                     "（甲板缝隙灌进寒流 → 汗毛竖起 → 声音发颤），把「认知被推翻」写成体感。",
        "basis": "derived",
        "quoteKeys": ["q_pos_trade", "q_pos_deny", "q_pos_cold", "q_pos_shiver"],
        "note": "**原文没有解释他为何发抖**，也没有写否认意味着什么。"
                "「前提被推翻 ⇒ 发冷」是我把相邻的否认与寒流体感连成的解释，故 basis=derived，"
                "并把「为何否认」整条挂进 unknowns u3。",
    },
]

REJECTED_EDGES = [
    {
        "id": "re1_silence_then_weather",
        "candidate": "「问完，两人望着彼此，陷入了沉默」→「几秒后…同时岔开话题」",
        "why": "这两句**确实**由原文连成因果，但连接词是「心虚的他们」——"
               "的真实成因是两人的秘密，而不是「沉默」这个状态本身。"
               "把它立成「沉默导致岔开话题」是拿一个中间状态冒充机制："
               "沉默是**表现**，心虚才是因。故本候选改立 e5（因=各自有不能说的秘密），"
               "此处登记被否的那条，防止复核者以为我漏读了这两个相邻句。",
        "quoteKeys": ["q_both_silent", "q_both_topic"],
    },
    {
        "id": "re2_arrival_order_in_palace",
        "candidate": "南宫倩柔驾车抵达宫城外 → 魏渊下车",
        "why": "**时间相邻当因果**的典型：马车到了，所以人下车 —— 这话不必原文写，"
               "但它也不是原文写的。叙述在这里只是按顺序交代动作（停车、丢缰绳、摘木凳、开门），"
               "没有任何一句给机制或目的。这类「动作流水」在本单元还有若干处，"
               "一律不连边 —— 本条的引文因此只用于 states 与 coverage，不作因果依据。",
        "quoteKeys": ["q_ct_arrive", "q_ct_aide"],
    },
    {
        "id": "re3_spring_festival_causes_theft",
        "candidate": "春祭将近 → 铃音的玉镯被抢",
        "why": "两件事在信里紧挨着（「春祭将近，爹每日都归家都很晚…」与「娘给她买的玉镯子…不见了踪影」），"
               "但原文没有给任何机制：春祭让父亲没空管家，这与玉镯被抢没有因果，"
               "只共享「家里没人盯着」这个背景。把它连成因果会把**背景**写成**原因**。"
               "春祭的作用另立在 worldSettings w4（影响家人的可支配时间）。",
        "quoteKeys": ["q_springsac", "q_bracelet_gone"],
    },
    {
        "id": "re4_dream_of_battle_causes_armor_gift",
        "candidate": "许七安梦到山海关战役 → 魏渊要送他犀甲",
        "why": "两条线在同一个区间里前后出现（梦在 P001–P028，犀甲在 P166–P170），"
               "但没有任何信息在这两处之间流动：魏渊不知道他做了什么梦，"
               "梦也没有提示犀甲。这是**平行剪辑**，不是因果。"
               "本条登记在此，正是为了说明「同一章里相邻的两条线」不构成边。",
        "quoteKeys": ["q_dream_guess", "q_t4_obj"],
    },
    {
        "id": "re5_letter_order_as_causation",
        "candidate": "读完玲月的信 → 拆第二封（浮香）",
        "why": "读信顺序是**编排顺序**，不是因果：没有任何一句写他为什么先读哪一封"
               "（q_read_pick 明写「他随便选了一封信」——「随便」正是对因果的否认）。"
               "这一处很值得记：原文用「随便」二字主动排除了顺序的因果含义。",
        "quoteKeys": ["q_read_pick"],
    },
]
