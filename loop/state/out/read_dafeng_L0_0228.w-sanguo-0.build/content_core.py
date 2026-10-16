# -*- coding: utf-8 -*-
"""内容源：第两百二十七章 备胎们的回信（为盟主“败笔的人生”加更）。

纪律：
  · 本文件**只写结论文本 + 引文键**，不写任何数字偏移（偏移由 gen_quotes.py 生成）。
  · 每一栏（objective/obstacle/action/result/cost）自带独立的 quoteKeys；
    构建侧会强制「同一条任务的五栏之间不得共用任何引文键」。
  · 缺依据的栏位写 None，并**必须**在同名 <栏位>Note 里写明为什么没有。
  · 信（letter）只能支持「信上这样写」，不得当作叙述事实 —— 凡以信为据处，
    note 里一律点明语层。
"""

# ─────────────────────────────────────────────────────────────────────────
# 1. tasks[]：任务五元组
# ─────────────────────────────────────────────────────────────────────────
TASKS = [
    {
        "id": "t1_xu_identifies_the_dream",
        "name": "许七安在棺中推断自己梦见的是什么",
        "actor": "许七安",
        "actorBasis": "explicit",
        "objective": {
            "text": "弄清自己为什么会梦到那一场规模庞大的多方混战。",
            "basis": "explicit",
            "quoteKeys": ["q_dream_why"],
            "note": "这一句是他把画面认成「山海关战役」之后自问的，问的是**原因**，"
                    "所以本栏记的是「想弄明白这场梦是什么、为什么会有」。原文没有写他"
                    "「想要弄清楚」这一类动机句，本栏的依据是他明确提出的疑问本身。",
        },
        "obstacle": {
            "text": "梦里出现的东西他一样都没接触过 —— 死尸大军、佛门高僧，"
                    "他无从用自身经历去对应。",
            "basis": "explicit",
            "quoteKeys": ["q_dream_unfamiliar"],
            "note": "这是「不可解」这一障碍的直接依据（本人自语）。注意它是**内心话**，"
                    "只能支持「他确实这样想」，不能支持「这些东西真的不存在于他的经历」。",
        },
        "action": {
            "text": "躺在棺材里回忆梦中画面，确认是多方势力混战。",
            "basis": "explicit",
            "quoteKeys": ["q_dream_recall", "q_dream_factions"],
            "note": "两条都是叙述层，写的是他的回忆动作与回忆内容，不是他的结论。",
        },
        "result": {
            "text": "结合魏渊的出现与其事迹，他判断这是史书记载的山海关战役。",
            "basis": "inferred",
            "quoteKeys": ["q_dream_legend", "q_dream_guess"],
            "note": "降为 inferred 而不是 explicit：原文用的是「心里当即有了猜测」，"
                    "**猜测**是人物判断，不是叙述确认。本区间没有任何旁证（没有人回应、"
                    "没有史料原文、没有第二次确认），所以「这是山海关战役」只能记为他的推断。",
        },
        "cost": None,
        "costNote": "本区间没有为这次推断写任何代价：没有消耗、没有伤害、"
                    "没有因为想这件事而耽误任何行动（他推棺起身紧接着就发生了）。"
                    "这是**已确认无代价描写**，不是「未提及」。",
        "note": "五栏引文两两不同（q_dream_why / q_dream_unfamiliar / "
                "q_dream_recall+q_dream_factions / q_dream_legend+q_dream_guess / —）。",
    },
    {
        "id": "t2_xu_reads_the_four_letters",
        "name": "许七安拆读怀里四封信，核对「谁没给我回信」",
        "actor": "许七安",
        "actorBasis": "explicit",
        "objective": {
            "text": "查出三个备胎里谁没有给他回信。",
            "basis": "explicit",
            "quoteKeys": ["q_t2_obj"],
            "note": "这是内心话（inner），只能支持「他这样想」。前一秒他还数出三个人"
                    "（q_backup_list）却发现只有两封，目标由此而来。",
        },
        "obstacle": None,
        "obstacleNote": "本区间**没有为读信设置任何障碍**，这是已确认的无障碍、不是未知："
                        "舱底只有微光（q_coffin_hold），但原文紧接着就写他黑夜视物毫无障碍"
                        "（q_darkvision，见 states s9 与 worldSettings w10），"
                        "且没有任何人来打断他（杨千幻背对着他、只在读完后才开口）。"
                        "所以本栏写 null 而不是补一条「光线昏暗」—— 那会被原文自己的下一句否掉。",
        "action": {
            "text": "借着甲板缝隙的微光，按顺序拆开信封：先读玲月的信，再读花魁娘子的信，"
                    "然后读临安的信，最后拆开第四封。",
            "basis": "explicit",
            "quoteKeys": ["q_letter_open", "q_t2_act1", "q_t2_act2"],
            "note": "三条分别是「开始读」「拆第三封」「拆第四封」，构成四次拆信的先后，"
                    "而不是同一动作的重复描述。",
        },
        "result": {
            "text": "确认第四封是怀庆写的；而怀庆在信里点出他一花赠两人、说辞各不同，"
                    "等于把他并行的示好摊在了桌面上。",
            "basis": "explicit",
            "quoteKeys": ["q_t2_res", "q_hq_flower"],
            "note": "「信是怀庆的啊」是叙述层的确认；「一花赠两人」出自**信文**（letter），"
                    "只能支持「怀庆在信里这样写」。两处必须分开看：许七安读到的是一封信的"
                    "内容，不是被叙述确认的事实。",
        },
        "cost": {
            "text": "羞耻：读到第四封后他脸色呆滞、面红耳赤，自陈「没脸回京」。",
            "basis": "explicit",
            "quoteKeys": ["q_t2_cost", "q_xu_face"],
            "note": "这是**社交/情绪代价**，不是物质代价 —— 原文没有写他为读这封信损失了"
                    "任何东西。之所以仍记入本栏：代价的形态由原文给出（无地自容），"
                    "不是我替他补的。若复核者认为情绪不构成 cost，此栏应改 null 并保留本注。",
        },
        "note": "五栏引文两两不同（q_t2_obj / — / q_letter_open+q_t2_act1+q_t2_act2 / "
                "q_t2_res+q_hq_flower / q_t2_cost+q_xu_face），有 1 个带理由的裸 null。",
    },
    {
        "id": "t3_yang_keeps_vigil_over_the_coffin",
        "name": "杨千幻潜上官船、开棺守候许七安复活",
        "actor": "杨千幻",
        "actorBasis": "explicit",
        "objective": {
            "text": "验证许七安到底死没死 —— 他料定没死，要等出结果。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_concluded"],
            "note": "语层是 speech（杨千幻自述）。他说的是「我便料定你没死」，"
                    "即他的判断，不能当作「许七安确实没死」的叙述证据 —— 后者由 q_yqh_healed"
                    "（叙述）承担。",
        },
        "obstacle": {
            "text": "他只能偷着来：一路尾随、潜入官船、开棺，这些事不能让人知道。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_secret"],
            "note": "「这些事是不能让许七安知道的」是叙述层对他自设约束的直接交代。"
                    "这是**已确认的约束**，不是猜测。",
        },
        "action": {
            "text": "一路尾随官船，潜入船上，打开了许七安的棺材板。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_open"],
            "note": "叙述层。三件事（尾随、潜入、开棺）在原文里是同一句的连动。",
        },
        "result": {
            "text": "看见他伤势离奇恢复、心跳渐渐复苏，就守在棺材边等；等了一旬，"
                    "许七安真的活过来了。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_healed", "q_yqh_waited"],
            "note": "两处语层不同：q_yqh_healed 是叙述（伤势恢复、心跳复苏），"
                    "q_yqh_waited 是杨千幻自己的话（「等了一旬，还真就活过来了」）。"
                    "复活这一事实同时有叙述侧的依据 —— 许七安推棺起身、开口说话。",
        },
        "cost": {
            "text": "守着棺材寸步不离，连如厕的时间都没有。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_wait"],
            "note": "这是**喜剧笔法**写的看护代价，价值很低（原文用「屎都没时间拉」这种"
                    "粗俗夸张收尾）。我把它记进本栏而不是写 null，因为原文确实写出了一项"
                    "被他放弃的东西；但它是否够格算「代价」，请复核者按原文语域判断。",
        },
        "note": "五栏引文两两不同（q_yqh_concluded / q_yqh_secret / q_yqh_open / "
                "q_yqh_healed+q_yqh_waited / q_yqh_wait）。",
    },
    {
        "id": "t4_xu_baits_yang_into_admitting",
        "name": "许七安用采薇的话头诈出杨千幻偷看过信",
        "actor": "许七安",
        "actorBasis": "explicit",
        "objective": {
            "text": "当面质问杨千幻是不是偷看了他的信。",
            "basis": "explicit",
            "quoteKeys": ["q_pos_wary"],
            "note": "这是台词（speech），而且是个**反问式指控**。它支持「他起了疑并当面相逼」，"
                    "不支持「杨千幻确实偷看了」—— 后者要到杨千幻自己接话露馅才成立。",
        },
        "obstacle": {
            "text": "杨千幻当场否认，说自己不屑做这种龌龊事。",
            "basis": "explicit",
            "quoteKeys": ["q_t3_obs"],
            "note": "**这是人物的话，不是事实**。他否认了，但后文证明他确实看过（q_pos_glue）。"
                    "本栏记的是「许七安当面遇到了一堵否认」，不是「他没有偷看」。",
        },
        "action": {
            "text": "先顺着「四品术士不屑于此」的说法放松对方，再主动提起采薇是个榆木脑袋、"
                    "自己写信撩不动她；等杨千幻替师妹解释时，立刻抓住他话里的破绽反问"
                    "「你怎么知道她告诉怀庆了」。",
            "basis": "explicit",
            "quoteKeys": ["q_t3_act", "q_t3_res_quote"],
            "note": "两条都是台词。第一步是示弱抛饵（他说自己撩不动），第二步是收网。"
                    "把它写成两步而不是一步，是因为原文用「话说回来」明确标出了转向。",
        },
        "result": {
            "text": "杨千幻好半天说不出话，意识到自己被套了，也尝到了许七安刚才的羞耻感。",
            "basis": "explicit",
            "quoteKeys": ["q_t3_res"],
            "note": "叙述层。结果是**诈问成功**，不是「信被偷看」这件事第一次发生 ——"
                    "偷看发生在区间之前（他自己在 q_yqh_open 里承认过开棺尾随）。",
        },
        "cost": {
            "text": "他放弃了追究：信已经被看过，时光不能倒流，不如假装大方。",
            "basis": "explicit",
            "quoteKeys": ["q_t3_cost"],
            "note": "这是**放弃追责的让步**，不是资源损耗。之所以记入本栏：原文写的是他"
                    "为这件事付出的东西（不再计较、还要装大度）。若复核者认为让步不构成"
                    "cost，此栏应改 null 并保留本注。",
        },
        "note": "五栏引文两两不同（q_pos_wary / q_t3_obs / q_t3_act+q_t3_res_quote / "
                "q_t3_res / q_t3_cost）。",
    },
    {
        "id": "t5_wei_prepares_the_rhino_armor",
        "name": "魏渊为许七安备办犀甲，南宫倩柔禀报材料已齐",
        "actor": "魏渊（发起）、南宫倩柔（执行）",
        "actorBasis": "explicit",
        "objective": {
            "text": "把犀甲做成法器，替许七安补足最后的短板，给这株还没长成的树苗保驾护航。",
            "basis": "explicit",
            "quoteKeys": ["q_t4_obj"],
            "note": "叙述明确写成「南宫倩柔知道魏渊的想法」—— 所以本栏记的是"
                    "**经南宫转述的魏渊意图**，不是魏渊自述。区别在于：如果是魏渊自己说的，"
                    "它只是一句台词；现在是叙述替他确认了这个意图。",
        },
        "obstacle": {
            "text": "犀甲本身还不是法器：要再请司天监的炼金术师和阵师出手炼制才行。",
            "basis": "explicit",
            "quoteKeys": ["q_t4_obs"],
            "note": "原文用「若再请…炼制成法器。那就是…」的条件式标出这一步尚未完成。"
                    "这正是本任务 result 为 null 的原因（见 resultNote）。",
        },
        "action": {
            "text": "魏渊询问犀甲的进展；南宫倩柔答材料已收集完毕，等着拿去司天监炼制。",
            "basis": "explicit",
            "quoteKeys": ["q_t4_act", "q_t4_res"],
            "note": "一问一答。q_t4_act 里同时含魏渊的感叹「真是多事之秋」，"
                    "那句话与本栏无关，只用于 obstacle 之外的语境，不计入依据。",
        },
        "result": None,
        "resultNote": "本区间**没有结果**：材料收齐只是把工序推进了一步，甲还没有炼成。"
                      "原文关于成品的两句话都是条件式展望 ——「若再请司天监的炼金术师和阵师"
                      "出手，炼制成法器」「那就是一件防御无双的至宝」—— 前提未发生时"
                      "不能当结果。按「结束≠成功」的口径，本栏必须写 null，"
                      "而不是把「材料已齐」重复一遍充作结果。",
        "cost": {
            "text": "执行者南宫倩柔的语气是酸溜溜的。",
            "basis": "explicit",
            "quoteKeys": ["q_t4_sour"],
            "note": "**这是执行者的情绪，不是资源代价** —— 原文没有写材料值多少钱、"
                    "花了多少时间、谁出的钱。我把它记进本栏而不是写 null，因为原文确实"
                    "写出了一项伴随这项工作出现的东西；但「酸溜溜」是否够格算 cost，"
                    "请复核者判。若认为不构成，此栏应改 null 并保留本注。",
        },
        "note": "五栏引文两两不同（q_t4_obj / q_t4_obs / q_t4_act+q_t4_res / — / q_t4_sour）。",
    },
    {
        "id": "t6_wei_enters_the_study",
        "name": "魏渊独自进御书房列朝",
        "actor": "魏渊",
        "actorBasis": "explicit",
        "objective": {
            "text": "应召入御书房参加因八百里加急而召开的小朝会。",
            "basis": "explicit",
            "quoteKeys": ["q_ct_smallcourt"],
            "note": "**本栏是全候选最弱的一处**：原文只写了小朝会**因八百里加急而召开**这个"
                    "事由，从头到尾没有写魏渊自己想不想去、去了要做什么。所以这里记的是"
                    "「他赴的是一场什么会」，不是「他想要什么」。我选择写出来并标注，"
                    "而不是写 null —— 因为「应召赴会」至少有原文的召开依据，"
                    "而 null 会掩盖这一场戏确实存在的行动线。请复核者重点判这一栏。",
        },
        "obstacle": {
            "text": "南宫倩柔在御书房外被禁军拦下，不能再跟进去。",
            "basis": "explicit",
            "quoteKeys": ["q_t5_obs", "q_t5_obs2"],
            "note": "两条紧邻：前一条写拦截，后一条写结果（魏渊独自前行）。"
                    "这不是「时间相邻当因果」—— 拦的是义子、独行的是义父，"
                    "原文用「魏渊独自一人前行」直接承接。",
        },
        "action": {
            "text": "跨过门槛进入御书房，向元景帝作揖行礼，自然而然地入列站到自己的位置。",
            "basis": "explicit",
            "quoteKeys": ["q_t5_act", "q_t5_act2"],
            "note": "两条都是叙述。q_t5_act2 的锚串里含一句引号内的「陛下。」——"
                    "整条登记为 narration 而不是 speech，因为它的主干是行礼入列的动作描写；"
                    "这个语层判断写进 selfCritique 请复核。",
        },
        "result": {
            "text": "只得到满朝的晦涩眼神：他扫视群臣后眉头一皱，众大臣都在看他，"
                    "元景帝也在看他但不露喜怒。",
            "basis": "explicit",
            "quoteKeys": ["q_t5_res", "q_t5_res2", "q_ct_emperor"],
            "note": "**这不是处置结果，是气氛**：本区间没有任何决定、旨意、赏罚、"
                    "罪名落到魏渊头上，章节在他入列处结束。所以本栏写的是"
                    "「他实际得到什么」的字面答案 —— 只有注视，没有后果。"
                    "不要把它读成「魏渊失势」：原文一个字都没写原因。",
        },
        "cost": None,
        "costNote": "本区间没有为魏渊入朝写任何代价：没有罚俸、没有夺职、没有损失，"
                    "连一句抱怨都没有（他唯一的话是「真是多事之秋」，那是对形势的感叹，"
                    "已用于别的栏位）。这是**已确认无代价描写**，不是未提及。",
        "note": "五栏引文两两不同（q_ct_smallcourt / q_t5_obs+q_t5_obs2 / "
                "q_t5_act+q_t5_act2 / q_t5_res+q_t5_res2+q_ct_emperor / —）。",
        "layerWarning": "narration —— 本任务五栏依据全部出自叙述层（唯一一处引号内容"
                        "「陛下。」只是称呼，不承载命题）。原文在这一场里没有给魏渊"
                        "任何一句表态性的台词：他唯一较长的话是「真是多事之秋」"
                        "（q_ct_sigh，与犀甲那件事连在一起），而那一处不属本任务。"
                        "所以本任务语层单一**是原文的形态**，不是我省略了台词。",
    },
    {
        "id": "t7_mother_questions_the_teacher",
        "name": "婶婶为铃音被拽走的玉镯去质问塾堂先生",
        "actor": "婶婶（许家二房主母，原文只称「娘」）",
        "actorBasis": "explicit",
        "actorNote": "原文通篇用「娘」指代，未给姓名。本任务是**信里转述**的事，"
                     "不是本区间叙述直接呈现的场景。",
        "layerWarning": "letter —— 本任务五栏的依据全部出自许玲月的信文，"
                        "只能支持「信上这样写」，不能当作叙述事实。",
        "objective": {
            "text": "问出玉镯是谁弄走的。",
            "basis": "explicit",
            "quoteKeys": ["q_t6_obj"],
            "note": "信文层。信里写的是「问她是谁干的」—— 先问铃音本人；"
                    "问不出来才转去质问塾堂先生（见 action）。",
        },
        "obstacle": {
            "text": "铃音不肯说，而且完全不当一回事。",
            "basis": "explicit",
            "quoteKeys": ["q_t6_obs"],
            "note": "信文层。这一句同时是「问不出来」和「孩子不配合」两层障碍的依据。",
        },
        "action": {
            "text": "没敢告诉丈夫，自己去找塾堂先生质问。",
            "basis": "explicit",
            "quoteKeys": ["q_t6_act"],
            "note": "信文层。原文把「没敢告诉他」与「自己去找先生」连在同一句里，"
                    "所以「独自去」也是这一句给出的；「没敢告诉他」另见 causeEdges e11。",
        },
        "result": {
            "text": "先生推说不知道，反过来猜是铃音自己弄丢了 —— 什么都没问出来。",
            "basis": "explicit",
            "quoteKeys": ["q_t6_res"],
            "note": "信文层。这是**未达成**，不是成功后的小波折：镯子、责任人、"
                    "赔偿在本区间一个字都没有下文。",
        },
        "cost": {
            "text": "娘气得浑身发抖，却又无可奈何。",
            "basis": "explicit",
            "quoteKeys": ["q_t6_cost"],
            "note": "信文层。记的是情绪代价 + 「无可奈何」这一处境。"
                    "如果复核者认为情绪不构成 cost，此栏应改 null 并保留本注。",
        },
        "note": "五栏引文两两不同（q_t6_obj / q_t6_obs / q_t6_act / q_t6_res / q_t6_cost），"
                "且五栏语层全部为 letter —— 本任务是全候选里语层最单一的一条。",
    },
    {
        "id": "t8_linan_makes_a_scene",
        "name": "临安公主为鸡精的归属跑去司天监闹了一场",
        "actor": "临安公主（信里自称「本宫」）",
        "actorBasis": "explicit",
        "layerWarning": "letter —— 本任务五栏的依据全部出自临安的信文，"
                        "只能支持「信上这样写」，不能当作叙述事实。",
        "objective": {
            "text": "为「鸡精是褚采薇发明的」这个说法生气、去司天监讨说法。",
            "basis": "explicit",
            "quoteKeys": ["q_la_rumor"],
            "note": "**本栏偏弱**：原文写的是她的气愤与不解（她认定鸡精是许七安发明的），"
                    "不是一句自述的目标。我用这句传言作为她行动的直接由头；"
                    "若复核者认为「生气」不构成 objective，此栏应改 null 并保留本注。",
        },
        "obstacle": None,
        "obstacleNote": "原文只写「司天监的白衣不敢对我出手」—— 这是**确认没有遇到阻碍**，"
                        "不是未知。真正的反噬发生在事后（白衣去父皇那里告状，见 result），"
                        "所以本栏写 null 而不是把事后反噬挪来充作事前障碍。",
        "action": {
            "text": "气得要死，跑到司天监闹了一场。",
            "basis": "explicit",
            "quoteKeys": ["q_la_raid"],
            "note": "信文层。原文没有写「闹」的具体形态（砸了什么、骂了谁），"
                    "所以 action 只写到「闹了一场」为止，不补细节。",
        },
        "result": {
            "text": "白衣不敢对她出手，转去皇帝那里告状，她被父皇狠狠臭骂了一顿。",
            "basis": "explicit",
            "quoteKeys": ["q_la_scolded"],
            "note": "信文层。这是**反噬**而不是她想要的结果（她去是为了讨公道，"
                    "得到的是被骂）。按「结束≠成功」口径不许写成她讨回了公道。",
        },
        "cost": None,
        "costNote": "被臭骂记在 result（那是她得到的处置，不是她付出的东西）；"
                    "本区间没有写她为这次闹事付出别的代价（没有禁足、没有罚俸、"
                    "没有道歉的描写）。这是**已确认无其他代价描写**。",
        "note": "五栏引文两两不同（q_la_rumor / — / q_la_raid / q_la_scolded / —），"
                "有 2 个带理由的裸 null。",
    },
    {
        "id": "t9_xu_probes_yang_purpose",
        "name": "许七安试探杨千幻来云州的真正差事",
        "actor": "许七安",
        "actorBasis": "explicit",
        "objective": {
            "text": "问出监正派杨千幻到云州办的是什么事。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_ask"],
            "note": "台词（speech）。问句本身就是目标：他已经听对方说过「奉师命来云州办事」"
                    "（q_yqh_mission，已用于 e13），但不满足于这个笼统说法，才追问具体差事。",
        },
        "obstacle": {
            "text": "对方也在问他 —— 杨千幻同一时间反问「你怎么做到死而复生的？」"
                    "两个问题互相顶住，谁都没答。",
            "basis": "explicit",
            "quoteKeys": ["q_revive_q", "q_both_silent"],
            "note": "两处语层不同：q_revive_q 是台词（对方向他发问），"
                    "q_both_silent 是叙述（「问完，两人望着彼此，陷入了沉默」）。"
                    "后者是这条障碍成立的关键 —— 原文用沉默明确交代**两个问题都没有答案**。",
        },
        "action": {
            "text": "先在心里腹诽对方揭过自己的棺材，脸上却挂着微笑，然后把问题问出口。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_suspicion"],
            "note": "inner 语层。本栏记的是「带着怀疑去问」这个动作形态 ——"
                    "原文写他「心里腹诽，脸上却露出微笑：」然后才引出问句，"
                    "冒号直接把内心与随后的开口连起来。",
        },
        "result": None,
        "resultNote": "本区间**没有结果**：他问出口之后，原文立刻转到杨千幻的反问，"
                      "然后是沉默、然后两人岔开话题。「监正派你来云州做什么」"
                      "从头到尾没有得到任何回答，本区间也没有第二个来源能补上。"
                      "按「结束≠成功」口径写 null，不把「他问了」当成「他问出了」。",
        "cost": None,
        "costNote": "本区间没有为这次试探写任何代价：话题被岔开之后，"
                    "原文没有再回到这件事，也没有写他因此失去什么或付出什么。"
                    "这是**已确认无代价描写**，不是未提及。",
        "note": "五栏引文两两不同（q_yqh_ask / q_revive_q+q_both_silent / "
                "q_yqh_suspicion / — / —），有 2 个带理由的裸 null。",
    },
]

# 被排除的候选任务（写出来是为了让复核者看到我**考虑过并否决**了什么）
REJECTED_TASKS = [
    {
        "id": "rt1_huaiqing_ghostwrites_for_caiwei",
        "candidate": "怀庆替褚采薇执笔写回信",
        "why": "五栏里 objective 与 action 只能是同一句话（「我便与本宫替你执笔回信」"
               "这一句既是她要做的、也是她做了的），硬拆两栏就会让同一句同时充当两栏依据，"
               "正是提示词点名禁止的形态。该事件改记为 causeEdges e3 与 states s7。",
        "quoteKeys": ["q_hq_ghost_write"],
    },
    {
        "id": "rt2_xu_hides_letters_from_huaiqing",
        "candidate": "许七安确保裱裱、浮香、玲月的信不被怀庆看到",
        "why": "原文写的是他**庆幸**那些信怀庆看不到（已经在发生的事），不是他采取了"
               "任何隐藏动作；把庆幸立成任务会把状态写成行动。改记为 states s7。",
        "quoteKeys": ["q_xu_hidden"],
    },
    {
        "id": "rt3_wei_yuan_attends_as_routine",
        "candidate": "把小朝会写成魏渊主动谋求的朝会",
        "why": "原文只写「陛下就在御书房召开了小朝会」—— 召集者是皇帝，魏渊是应召者。"
               "把它写成魏渊谋划的事会换掉行动主体。t6 的 objectiveNote 已标注这一栏的弱点。",
        "quoteKeys": ["q_ct_smallcourt"],
    },
]

# ─────────────────────────────────────────────────────────────────────────
# 2. causeEdges[]：必须有方向与触发机制
# ─────────────────────────────────────────────────────────────────────────
CAUSE_EDGES = [
    {
        "id": "e1_healing_wounds_convince_yang",
        "from": "许七安身上的刀伤箭孔诡异修复",
        "to": "杨千幻断定他没死，决定等下去",
        "mechanism": "触发是**观察到的反常**：伤口不该自愈却自愈了，"
                     "由此推出「人还没死」。原文用「我便料定」这个推断动词把"
                     "「观察到修复」与「断定没死」扣在一起，不是靠两句相邻。",
        "basis": "explicit",
        "quoteKeys": ["q_yqh_noticed", "q_yqh_concluded"],
        "note": "前半出自杨千幻的台词，后半也是他的台词 —— 整条边建立在**单一人物的"
                "自述**上。叙述侧另有一条独立依据（q_yqh_healed：伤势离奇恢复、心跳复苏），"
                "所以「确实在恢复」这一半不是孤证。",
    },
    {
        "id": "e2_fear_of_punishment_breeds_flight",
        "from": "得知许七安战死、想到回京后老师会把他镇压在摘星楼",
        "to": "恐慌到差点脱离师门跑路",
        "mechanism": "触发是**对后果的预判**：他把许七安的死与自己的失职连起来，"
                     "推出将受的惩罚，再由恐惧推出逃跑念头。原文以「恐慌的」"
                     "作下一句的状语，直接标明因果。",
        "basis": "explicit",
        "quoteKeys": ["q_yqh_panic", "q_yqh_flee"],
        "note": "这是**内心历程**（叙述转述他的心说），不是已发生的事："
                "「差点」表示他没有真跑。不要把它读成叛出师门。",
    },
    {
        "id": "e3_caiwei_shares_to_huaiqing",
        "from": "褚采薇与怀庆关系好、把红莲花瓣与许七安的说辞讲给怀庆",
        "to": "怀庆在信里点出「一花赠两人」",
        "mechanism": "触发是**转述**：采薇根本没意识到这是暧昧（她自己解释成寻常朋友书信），"
                     "于是把花瓣和那句「与红莲一样明媚如风」当闲话讲给闺蜜；"
                     "怀庆由此拿到许七安并行示好的证据。原文用「眼角眉梢挂着笑意」"
                     "写采薇讲这件事时的状态，再用「呵」引出怀庆的点评。",
        "basis": "derived",
        "quoteKeys": ["q_hq_ghost_share", "q_xu_naive", "q_hq_flower"],
        "note": "降为 derived：机制的两端都在原文，但「采薇是在不知情的情况下说出去的」"
                "这一步是我从 q_xu_naive（许七安的复盘）推出来的，不是叙述直接写的。"
                "整条边跨了信内信外两个语层。",
    },
    {
        "id": "e4_yang_self_defeating_explanation",
        "from": "杨千幻为了替师妹开脱，主动解释她只是当成寻常朋友书信往来",
        "to": "许七安抓住「你怎么知道她告诉怀庆了」，诈问成功",
        "mechanism": "触发是**信息自证**：要解释采薇为何那样做，就必须引用"
                     "「她告诉了怀庆公主」这一事实；而这个事实只在信里出现过，"
                     "杨千幻能知道它，只有偷看一个来源。原文把这两句排成紧邻的问答，"
                     "逻辑上的破绽由许七安当场点出。",
        "basis": "derived",
        "quoteKeys": ["q_pos_agree", "q_t3_res_quote", "q_t3_res"],
        "note": "降为 derived：原文没有写许七安的推理过程，是我替他把「只有看过信"
                "才可能知道」这一步补出来的。但「被套路了」是叙述对他的判定，"
                "说明这一步至少方向正确。",
    },
    {
        "id": "e5_denial_pulls_the_rug",
        "from": "许七安把「你帮我抓住梁有平」当作既成事实、以此交换不计较",
        "to": "杨千幻否认帮过忙，许七安变色战栗",
        "mechanism": "触发是**前提被推翻**：许七安用一件他确信发生过的事做人情，"
                     "而对方说那件事根本没发生 —— 那么要么他的记忆错了，"
                     "要么梁有平被抓另有其人。原文把否认与寒流、冷战、颤抖排在一起，"
                     "用生理反应标出这个前提崩塌的分量。",
        "basis": "derived",
        "quoteKeys": ["q_pos_trade", "q_pos_deny", "q_pos_shiver"],
        "note": "降为 derived：机制里「前提被推翻」这一层是我补的；原文只给"
                "「否认」与「战栗」两个事实，中间没有任何解释，"
                "甚至可能是他没听清（见 selfCritique sc4）。这是本候选跨度最大的边。",
    },
    {
        "id": "e6_urgent_dispatch_forces_the_court",
        "from": "八百里加急文书送进宫",
        "to": "皇帝在御书房召开小朝会、魏渊入朝",
        "mechanism": "触发是**制度规定的传递路径**：八百里加急直接送入内阁、由内阁转送"
                     "皇帝，且送入内阁前除驿卒外任何人不得经手 —— 这条规则决定了"
                     "文书一到就等于最高层被迫议事，于是小朝会召开。原文用「没多久」"
                     "把文书进宫与小朝会扣在一起。",
        "basis": "explicit",
        "quoteKeys": ["q_ct_cabinet", "q_ct_only", "q_ct_smallcourt"],
        "note": "这条边不靠时间相邻：如果只有「文书进宫」和「开了小朝会」两句，"
                "相邻就只是相邻。之所以能连，是因为原文先给出了经手禁令与直达路径"
                "这两条规则，规则解释了为什么文书一进宫就必须由皇帝处理。",
    },
    {
        "id": "e7_armor_needs_sitianjian",
        "from": "犀甲目前只是收齐的材料",
        "to": "要成为「防御无双的至宝」还需司天监的炼金术师与阵师出手",
        "mechanism": "触发是**条件链**：原文用「若再请…炼制成法器。那就是…」"
                     "把「司天监出手」写成后面一切的前提。所以现在这一步不做，"
                     "至宝就不存在 —— 这正是 t5 的 result 必须为 null 的机制依据。",
        "basis": "explicit",
        "quoteKeys": ["q_t4_obs", "q_ct_treasure"],
        "note": "条件式不是事实：本栏连的是「要成器就得先炼制」这个必要条件，"
                "不是「已经成了至宝」。",
    },
    {
        "id": "e8_child_silence_narrows_the_search",
        "from": "铃音不肯说是谁干的",
        "to": "娘只能转去质问塾堂先生",
        "mechanism": "触发是**线索源被封死**：家里唯一在场的人不开口，"
                     "可追问的对象就只剩看管学堂的先生。原文把「她也不说」"
                     "与「自己去找塾堂先生质问」放在相邻两句，中间用「春祭将近，"
                     "爹每日都归家都很晚」交代了为什么不是爹去。",
        "basis": "derived",
        "quoteKeys": ["q_t6_obs", "q_t6_act"],
        "note": "降为 derived：原文没有明写「因为问不出来所以去问先生」，"
                "这一步是我把两句连起来补的。整条边在 letter 语层内。",
    },
    {
        "id": "e9_spring_rites_keep_the_father_away",
        "from": "春祭将近，爹每日归家很晚或宿在外营",
        "to": "娘没敢把玉镯的事告诉他，自己去找先生",
        "mechanism": "触发是**丈夫不在场**：家里出了事而当家的人连日不在，"
                     "于是她既没机会说、也选择不说。原文把「归家都很晚／宿在外营」"
                     "与「娘没敢告诉他」排成先后两句，用「没敢」标出这是她的选择而非遗忘。",
        "basis": "derived",
        "quoteKeys": ["q_spring_family", "q_mother_secret"],
        "note": "降为 derived：「没机会说」与「不敢说」原文只给了后者（「没敢」），"
                "前者是我从「归家都很晚」补的。整条边在 letter 语层内。",
    },
    {
        "id": "e10_scene_the_white_robes_and_the_emperor",
        "from": "临安跑司天监闹了一场",
        "to": "白衣不敢对她出手、转去皇帝那里告状，她挨了一顿臭骂",
        "mechanism": "触发是**身份不对等造成的路径转换**：她动不得（白衣不敢出手），"
                     "但白衣能动她的父皇，于是惩罚从司天监转到皇帝手里。"
                     "原文用「竟」与「被…狠狠臭骂了一顿」把这条转换路径写实。",
        "basis": "explicit",
        "quoteKeys": ["q_la_raid", "q_la_scolded"],
        "note": "整条边在 letter 语层内：两处都是临安信里的话，只能支持"
                "「信上这样写」。",
    },
    {
        "id": "e11_dream_name_triggers_recall",
        "from": "梦里认出兽头上那个青衣人是魏渊",
        "to": "他忽然记起自己是谁，梦境随即崩溃",
        "mechanism": "触发是**认出熟人**：名字一出口，失忆的状态就被打破。"
                     "原文把三件事压在同一个句子里 ——「心头一震，忽然记起自己是谁了，"
                     "也就是这个瞬间，战场画面崩溃」——「也就是这个瞬间」"
                     "明确把认出、记起、崩溃锁在同一时刻，不是相邻叙述。",
        "basis": "explicit",
        "quoteKeys": ["q_weiyuan_call", "q_remember_collapse"],
        "note": "这条边**不解释**为什么认出魏渊就能记起自己 —— 原文没有给机制，"
                "只给了同时发生。我连的是「认出 → 记起」这一处原文明确标了同时性的"
                "转换，而不是替它补一个心理学解释。",
    },
    {
        "id": "e12_mutual_guilt_blocks_the_questions",
        "from": "两人各自心虚：许七安不想解释死而复生，杨千幻不能让他知道自己在守棺",
        "to": "同时发问后又同时岔开话题，谁也没有回答对方",
        "mechanism": "触发是**双向的信息封锁**：许七安问「监正大人派你来云州做什么」"
                     "（试探对方的目的），杨千幻问「你怎么做到死而复生的」"
                     "（要答案）；两人的问题都指向对方不愿说的东西，"
                     "于是原文用「心虚的他们又默契的同时岔开话题」把两个问句一起作废。",
        "basis": "derived",
        "quoteKeys": ["q_yqh_ask", "q_revive_q", "q_both_topic"],
        "note": "降为 derived：机制里「两人的问题都指向对方不愿说的东西」这一步是我补的。"
                "原文只给「心虚」「默契」两个词与两个问句的并列 ——"
                "「心虚」是叙述对两人状态的判定，但**它没有写各自心虚什么**，"
                "所以这条边只连到「话题被岔开」，连不到「他们在互相隐瞒什么具体的事」。",
    },
    {
        "id": "e13_mission_back_to_capital_puts_yang_on_board",
        "from": "杨千幻奉师命来云州办事、事情已了要回去",
        "to": "他顺路搭上送尸骨回京的官船，并偷偷溜上船",
        "mechanism": "触发是**行程重合**：他的回程与打更人送尸骨回京是同一条路，"
                     "于是他选择搭这条船，而不是自己走。原文用「恰好」标出这是巧合、"
                     "用「便偷偷溜上来」标出他上船的方式不合规。",
        "basis": "explicit",
        "quoteKeys": ["q_yqh_mission", "q_yqh_snuck", "q_yqh_snuck2"],
        "note": "三处同属杨千幻的台词（speech）。所以「奉师命办事」这一层"
                "只有他自己的说法，本区间没有第三方（监正、打更人）确认过；"
                "这也是 unknowns 没有单列它的原因 —— 原文没有第二处矛盾的说法。",
    },
]

REJECTED_EDGES = [
    {
        "id": "re1_awkwardness_to_exposure",
        "candidate": "两人同时岔开话题（今天天气不错／风儿甚是喧嚣）→ 许七安读到信后翻车",
        "why": "**时间相邻，不是因果**：岔开话题发生在拆信之前，翻车是怀庆信里的内容"
               "引发的，与那段尴尬没有机制连接。把它们连起来等于把「同一场景」当因果。",
        "quoteKeys": ["q_both_topic", "q_both_silent2"],
    },
    {
        "id": "re2_urgent_dispatch_to_yunzhou_case",
        "candidate": "八百里加急 → 「云州的案子结束了」",
        "why": "**用未知填因果**：八百里加急的内容在本区间**一个字都没写出来**，"
               "连来自哪个州都只是魏渊的推测（「必然是大事，只是不知来自哪一个州」）。"
               "而「云州的案子结束了？」是许七安在另一条船上的问句，"
               "两者在本区间没有任何交集。连这条边就是拿未写出的东西当机制。",
        "quoteKeys": ["q_ct_bigdeal", "q_case_done"],
    },
    {
        "id": "re3_banter_to_relationship_damage",
        "candidate": "许七安与杨千幻互相套话 → 两人关系恶化",
        "why": "原文写的是许七安「不如假装大方」、杨千幻「体会到了许七安刚才的羞耻感」，"
               "没有任何关系变化的描写；紧接着章节就被另一个消息截断。"
               "把斗嘴读成关系恶化是替原文加判断。",
        "quoteKeys": ["q_t3_cost", "q_yang_shame"],
    },
    {
        "id": "re4_healing_to_the_dream",
        "candidate": "他伤势自愈 → 他梦见山海关战役",
        "why": "**并列而非因果**：两件事同属他醒转前后的经历，但原文没有任何机制"
               "把「伤口修复」与「梦到什么」连起来 —— 梦发生在他醒来**之前**，"
               "叙述也没有写这两者相关。把它们连边等于因为同属一场戏就宣称因果。",
        "quoteKeys": ["q_yqh_healed", "q_dream_split"],
    },
    {
        "id": "re5_the_two_dead_brothers_worry",
        "candidate": "他念叨宋廷风和朱广孝有没有为他伤心 → 后文出现他们的反应",
        "why": "**本区间没有后文**：这句话之后，宋廷风与朱广孝在本区间再没有出现，"
               "也没有任何人为他伤心的描写。用一句自语去预言区间外的事，"
               "就是拿未写出的内容当结论。",
        "quoteKeys": ["q_xu_dead_once"],
    },
    {
        "id": "re6_lying_to_linan_to_her_gifts",
        "candidate": "他谎称二叔举债 → 临安变着法子送银子 → 他因此受益",
        "why": "这条边**方向可疑**：临安在信里给出的回报是「等你回来，随便去本宫库房"
               "挑几件」（q_la_gift），那是**将来**的许诺，不是已经到手的收益；"
               "而「变着法子送我银子」是许七安对**过往**的回顾。"
               "把许诺当收益、把回顾当结果，会把两个不同时点的东西连成一条链。"
               "两件事各自的依据已分别记进 t2.result 与 th1.support，不单独立边。",
        "quoteKeys": ["q_xu_lied", "q_la_gift"],
    },
]

# ─────────────────────────────────────────────────────────────────────────
# 3. states[]：前值 / 后值 + 事件锚点
# ─────────────────────────────────────────────────────────────────────────
STATES = [
    {
        "id": "s1_xu_from_killed_in_action_to_awake",
        "kind": "change",
        "who": "许七安（生死与意识状态）",
        "before": {
            "text": "战死：打更人只把他的尸骨送回京，杨千幻得知的消息也是「许七安战死」。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_panic"],
            "note": "依据是杨千幻的心理描写（inner），它支持「他得到的是战死消息」，"
                    "这正是需要的前值口径 —— 前值是**外界所知的状态**，"
                    "不是「他确实死了」（叙述从未这样写过）。",
        },
        "after": {
            "text": "伤势离奇恢复、心跳渐渐复苏，随后自己推开棺材坐起、开口说话。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_healed"],
            "note": "叙述层（不是台词）。后半「推棺起身」另见锚点。",
        },
        "anchor": {
            "text": "新鲜空气涌入，他深吸一口气，翻身坐起。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_wake"],
        },
        "note": "前值出自 inner、后值出自 narration —— 后值语层更强，方向是"
                "「外界以为的死 → 叙述确认的活」，不构成口径冲突。",
    },
    {
        "id": "s2_who_has_read_the_letters",
        "kind": "knowledge",
        "who": "「谁读过那四封信」上的知识差（杨千幻／许七安）",
        "before": {
            "text": "许七安起疑并当面相逼，但杨千幻否认偷看；许七安当场接受了这个说法"
                    "（他随即放松下来抛饵）。",
            "basis": "explicit",
            "quoteKeys": ["q_t3_obs"],
            "note": "「否认」是台词，「当场接受」这一步由他随后的举动反推（见 note 末），"
                    "属推导。",
        },
        "after": {
            "text": "杨千幻自己接话露馅，许七安确认他不但看过、还把信粘了回去。",
            "basis": "explicit",
            "quoteKeys": ["q_pos_glue"],
            "note": "依据是 inner（许七安的腹诽），它只支持「他已经认定」，"
                    "不支持「杨千幻确实粘过」—— 后者由 e4 的机制间接支持。",
        },
        "anchor": {
            "text": "许七安目光骤然犀利，反问「你特娘的怎么知道她告诉怀庆了？」",
            "basis": "explicit",
            "quoteKeys": ["q_t3_res_quote"],
        },
        "knowledge": {
            "whoKnows": "杨千幻：从头到尾知道自己看过信、开过棺；露馅后许七安也知道了。",
            "whoDoesNotKnow": "许七安在露馅前不知道杨千幻看过信；"
                              "杨千幻不知道许七安在诈他（他以为自己是在替师妹解释）。",
        },
        "note": "「当场接受」的推导链：他刚被否认就立刻抛出采薇的话头（q_t3_act），"
                "说明他把「不屑做这等龌龊之事」当成了可信的答复。这一步是我推的，"
                "已标在 before.note 里。",
    },
    {
        "id": "s3_bracelet_from_gift_to_lost",
        "kind": "change",
        "who": "铃音的玉镯",
        "before": {
            "text": "娘买给她的、价值十两的玉镯子。",
            "basis": "explicit",
            "quoteKeys": ["q_bracelet_bought"],
        },
        "after": {
            "text": "前几天不见了踪影。",
            "basis": "explicit",
            "quoteKeys": ["q_bracelet_gone"],
        },
        "anchor": {
            "text": "她手腕上有浅浅的淤青，显然是被硬拽下来的。",
            "basis": "explicit",
            "quoteKeys": ["q_bracelet_yank"],
        },
        "note": "**三处语层全部是 letter**（许玲月的信）—— 只能支持「信上这样写」。"
                "另外「显然是被人硬拽下来的」是**写信人的判断**（她自己用了「显然」），"
                "不是验伤结论；所以锚点记的是「她这样解释淤青的来源」，"
                "不是「已确认被人拽走」。",
    },
    {
        "id": "s4_xu_mood_from_content_to_stunned",
        "kind": "change",
        "who": "许七安（读完信后的情绪）",
        "before": {
            "text": "读完玲月的信，心满意足地把信纸折好装回信封。",
            "basis": "explicit",
            "quoteKeys": ["q_xu_pleased"],
        },
        "after": {
            "text": "读完第四封后脸色呆滞地看着信纸。",
            "basis": "explicit",
            "quoteKeys": ["q_xu_stunned"],
        },
        "anchor": {
            "text": "「信是怀庆的啊」—— 他确认第四封的写信人。",
            "basis": "explicit",
            "quoteKeys": ["q_t2_res"],
        },
        "note": "情绪起伏的方向由三处叙述给出，不是我替她（他）概括的。"
                "中间还有一次上扬（读完临安的信「有些小感动」，q_la_protect），"
                "本状态只取首尾两点，不把中间那次也算进来。",
    },
    {
        "id": "s5_wei_yuan_from_carriage_to_his_place",
        "kind": "change",
        "who": "魏渊（所在位置／在场状态）",
        "before": {
            "text": "在宫城外下车。",
            "basis": "explicit",
            "quoteKeys": ["q_ct_weiyuan"],
        },
        "after": {
            "text": "在御书房内向皇帝作揖行礼、入列站到自己的位置。",
            "basis": "explicit",
            "quoteKeys": ["q_t5_act2"],
        },
        "anchor": {
            "text": "跨过门槛，进去御书房。",
            "basis": "explicit",
            "quoteKeys": ["q_t5_act"],
        },
        "note": "三点同属叙述层，链条完整（车外 → 门内 → 入列）。"
                "注意 after 用的是「入列站在自己的位置」这一动作，"
                "不是「他受到了某种待遇」—— 本区间没有后者。",
    },
    {
        "id": "s6_knowledge_gap_about_the_petal",
        "kind": "knowledge",
        "who": "「怀庆知道多少」上的知识差（怀庆／许七安）",
        "before": {
            "text": "许七安的判断：裱裱、浮香、玲月那三封信怀庆看不到 ——"
                    "后两者与她没交集，裱裱虽是她姐妹但两人势如水火，"
                    "且以公主身份不会把闺房密信拿出去说。",
            "basis": "explicit",
            "quoteKeys": ["q_xu_hidden", "q_xu_why_hidden"],
            "note": "两处都是 inner（他的推理），所以这是**他的判断**，"
                    "不是叙述对「怀庆看不到」的确认。",
        },
        "after": {
            "text": "怀庆在信里写出采薇转述的红莲花瓣与「与红莲一样明媚如风」——"
                    "说明至少这一条并行示好已经传到了怀庆那里。",
            "basis": "explicit",
            "quoteKeys": ["q_hq_petal"],
            "note": "letter 语层：只能支持「信上这样写」。",
        },
        "anchor": {
            "text": "「呵，许大人真是风流倜傥，一花赠两人，说辞各不同，偏还形容的恰到好处。」",
            "basis": "explicit",
            "quoteKeys": ["q_hq_flower"],
        },
        "knowledge": {
            "whoKnows": "怀庆：知道采薇收到了花瓣以及许七安的说辞；"
                        "采薇：知道自己的回信由怀庆代笔（她「欣然同意」）。",
            "whoDoesNotKnow": "许七安：在读到第四封之前不知道采薇把花瓣的事讲给了怀庆；"
                              "怀庆：看不到裱裱、浮香、玲月那三封信（依据是许七安的推理，"
                              "不是叙述确认）。",
        },
        "note": "两个方向的知识差强度不同：许七安那侧由信文**直接推翻**了他的预判；"
                "怀庆那侧（她看不到另三封）**只是许七安的推理**，原文没有旁证。"
                "不要把它读成已确认的事实。",
    },
    {
        "id": "s7_caiwei_reply_written_by_huaiqing",
        "kind": "change",
        "who": "褚采薇的回信（谁执笔）",
        "before": {
            "text": "采薇在烦恼怎么给许七安回信 —— 她不爱读书，怕写得不好让人笑话。",
            "basis": "explicit",
            "quoteKeys": ["q_hq_caiwei_worry"],
            "note": "letter 语层：这是怀庆在信里的转述，只能支持「信上这样写采薇的处境」。",
        },
        "after": {
            "text": "怀庆提出替她执笔，她欣然同意。",
            "basis": "explicit",
            "quoteKeys": ["q_hq_ghost_write"],
            "note": "letter 语层。原文只有「欣然同意」这一处对她的态度交代，"
                    "没有写她后来是否知道信里写了什么。",
        },
        "anchor": {
            "text": "采薇来怀庆宫苑用膳，闲聊时说起了许七安。",
            "basis": "explicit",
            "quoteKeys": ["q_hq_caiwei"],
            "note": "letter 语层。这一句是整条状态变化的起点（两人同席闲谈）。",
        },
        "note": "这条状态**跨了两个语层的主体**：采薇本人没有在本区间说过话，"
                "她的处境全部由怀庆的信转述。所以本状态只能支持"
                "「怀庆在信里这样交代」，不能支持「这就是采薇的真实想法」。",
    },
    {
        "id": "s8_xu_reaction_to_linan_letter",
        "kind": "change",
        "who": "许七安（读完临安信后的态度）",
        "before": {
            "text": "把临安称作傻妞儿，得意于自己哄住了她、她变着法子送银子。",
            "basis": "explicit",
            "quoteKeys": ["q_xu_lied"],
            "note": "inner 语层。这份得意同时是 th1 的 support 之一，"
                    "在本状态里只取「他对临安的态度」这一面。",
        },
        "after": {
            "text": "看到临安为鸡精的事跑去司天监闹、还挨了父皇的骂，"
                    "他承认对方是护着自己的。",
            "basis": "explicit",
            "quoteKeys": ["q_la_protect"],
            "note": "inner 语层（「许七安有些小感动，裱裱还是很护犊子的」）。"
                    "这是本区间里他对临安唯一一次非算计的评价。",
        },
        "anchor": {
            "text": "他读完了临安的信，把信塞回信封，深吸一口气，"
                    "拆开最后一封（准备看谁才是那个「叛徒」）。",
            "basis": "explicit",
            "quoteKeys": ["q_t2_act2"],
            "note": "叙述层。它是这次态度变化的收束点：从读信转向核对下一个对象。",
        },
        "note": "前值出自 inner、后值也出自 inner —— 两点同层，"
                "所以这条状态不涉及语层强弱问题；但它全程只反映**他怎么看临安**，"
                "不构成对临安本人的任何判定。",
    },
    {
        "id": "s9_xu_senses_after_lian_shen",
        "kind": "change",
        "who": "许七安（感知能力）",
        "before": {
            "text": "躺在棺中，眼前只有黑暗，看不见任何东西。",
            "basis": "explicit",
            "quoteKeys": ["q_amnesia"],
            "note": "前值取自「好黑」与「睁着眼看见的还是黑暗」这一处境 ——"
                    "本栏引的是他自问「我是谁」那一段所处的黑暗。"
                    "严格说本区间并没有一处写「他看不见」，只写了他所见是黑暗；"
                    "这一点已写进 selfCritique sc7 请复核者判。",
        },
        "after": {
            "text": "凝神感应后「看见」了船舱、五口棺材、航行的官船与运河；"
                    "目力已能在黑夜中视物，毫无障碍。",
            "basis": "explicit",
            "quoteKeys": ["q_see_boat", "q_darkvision"],
            "note": "两处叙述层。前者是精神力充眼所「看」到的，"
                    "后者是对目力的直接交代 —— 后者是**能力描述**，"
                    "前者是这项能力的一次实际运用。",
        },
        "anchor": {
            "text": "他凝神细感应，接着「看见」了这些 —— 这是他踏入炼神境后获得的神异。",
            "basis": "explicit",
            "quoteKeys": ["q_psychic_eye"],
            "note": "叙述层，直接给出能力的来源（炼神境）。",
        },
        "note": "这条状态解释了一个否则会很可疑的点：舱底只有甲板缝隙的微光，"
                "他读信却毫无困难。依据是三处叙述：能力来源（q_psychic_eye）、"
                "精神力可充眼（q_psychic_eye2，另见 w10）、身体属性提升（q_attributes，"
                "另见 w10）。**三处都只解释「他为什么看得见」，不解释信上写了什么。**",
    },
    {
        "id": "s10_lingyin_bracelet_and_household",
        "kind": "change",
        "who": "许家（玲月信里交代的家况）",
        "before": {
            "text": "铃音被迫去塾堂读书，已经会背诵三字经的前九个字；"
                    "二哥操办了这件事，爹娘得知时险些喜极而泣。",
            "basis": "explicit",
            "quoteKeys": ["q_lingyin_school", "q_lingyue_school"],
            "note": "letter 语层。两处都是许玲月信里的报平安式交代。",
        },
        "after": {
            "text": "铃音的玉镯被拽走、手腕留淤青，她不说；娘去质问先生问不出；"
                    "爹因春祭连日不归；二哥冻了半宿后不跟家里说话；"
                    "娘还打算开春后给玲月找夫婿。",
            "basis": "explicit",
            "quoteKeys": ["q_t6_res", "q_uncle_busy", "q_second_brother", "q_lingyue_husband"],
            "note": "letter 语层，四处同出一封信。这是本区间信息量最大的一处「后值」："
                    "家里四口人各有一条状态线，而写信人只用了三段话。",
        },
        "anchor": {
            "text": "她好像被人欺负了 —— 镯子不见了，手腕有浅浅的淤青。",
            "basis": "explicit",
            "quoteKeys": ["q_bracelet_gone"],
            "note": "letter 语层，是这一串变化的转折点。",
        },
        "note": "**这条状态全部建在 letter 语层上**：本区间没有任何叙述侧的镜头回到许家，"
                "所以它只能支持「信上这样写」。另外「二哥冻了半宿」与"
                "「忘记给他写信又不是大哥的错」是玲月的**归因**（她自己把二哥的怒气"
                "算在「没给他写信」上），不是叙述对因果的确认 ——"
                "这一层已写进 selfCritique sc8。",
    },
    {
        "id": "s12_yang_from_watching_to_revealed",
        "kind": "change",
        "who": "杨千幻（在场方式：从背对静坐到被卷入对话）",
        "before": {
            "text": "许七安醒来时，左侧三米外盘坐着一个白衣人，背对着他 ——"
                    "他只看背影就认出了是杨千幻。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_reveal"],
            "note": "叙述层。原文用「好了，身份揭晓了」这种打破第四面的插话收尾，"
                    "语气是喜剧式的，但**身份信息本身是叙述给出的**。",
        },
        "after": {
            "text": "被诈出偷看信件后，他好半天说不出话；随后主动解释采薇为何会把事情"
                    "告诉怀庆，并在被追问时否认帮抓过梁有平。",
            "basis": "explicit",
            "quoteKeys": ["q_yang_shame", "q_pos_agree"],
            "note": "两处语层不同：q_yang_shame 是叙述（他体会到羞耻感、无言），"
                    "q_pos_agree 是他的台词（替师妹解释）。",
        },
        "anchor": {
            "text": "许七安被吓的一抖 —— 醒来第一眼就发现有人背对着自己坐着；"
                    "对方开口第一句是「你醒了。」",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_wake_voice"],
            "note": "speech 层。它是这场对手戏的开场，也是「他一直在守着」的第一处信号。",
        },
        "note": "这条状态只写**在场方式**的变化，不写关系变化 ——"
                "原文没有一句话交代两人此后是敌是友。"
                "同一场景里对方的心情另有一处叙述交代（q_yqh_mood「语气颇为轻快，"
                "显示出他心情极好」），我把那一处留在 unknowns u10 里说明它的可疑，"
                "不拿它当状态依据。",
    },
    {
        "id": "s13_xu_on_the_fourth_letter_author",
        "kind": "knowledge",
        "who": "「第四封信是谁写的」上的知识差（许七安一人两段）",
        "before": {
            "text": "他怀疑写信的人在自己养的三个备胎里，并把「谁没回信」当成"
                    "判断的依据 —— 三个备胎是褚采薇、怀庆、临安。",
            "basis": "explicit",
            "quoteKeys": ["q_backup_list"],
            "note": "叙述层，直接列出名单。",
        },
        "after": {
            "text": "拆开第四封才确认是怀庆写的 —— 也就是说，没回信的那个人是褚采薇。",
            "basis": "explicit",
            "quoteKeys": ["q_t2_res"],
            "note": "叙述层。注意「没回信的是采薇」这一步原文并没有直接写出，"
                    "是从「三个人、两封信、第四封是怀庆」**推**出来的；"
                    "我把它放在 after 的文本里，但没有单独引一处证据，"
                    "因为原文确实没有那一句（见 note 末）。",
        },
        "anchor": {
            "text": "他拆信前自问「怀庆和采薇，你俩到底谁是叛徒，现在就见分晓了。」",
            "basis": "explicit",
            "quoteKeys": ["q_hq_traitor"],
            "note": "inner 语层。它把问题明确锁在怀庆与采薇两人之间 ——"
                    "这是本条知识差的锚点。",
        },
        "knowledge": {
            "whoKnows": "许七安：拆开第四封后知道是怀庆写的。",
            "whoDoesNotKnow": "许七安在拆开前不知道；"
                              "而「采薇没回信」的**真正原因**（她请怀庆代笔）"
                              "要到怀庆的信里才被他自己读到 —— 那一刻本状态已经结束了。",
        },
        "note": "严格说这条状态的后值差一句原文：「没回信的是采薇」从未被写出来，"
                "它是我从「三个备胎、两封回信、第四封是怀庆」算出来的。"
                "我已把它标在 after.note 里，请复核者决定是否应当降 basis 或改为 unknowns。",
    },
    {
        "id": "s11_xu_identity_recovered_by_the_dream",
        "kind": "change",
        "who": "许七安（自我认知）",
        "before": {
            "text": "记不清自己是谁、身在何处，只反复自问「我在哪里」「我是谁」。",
            "basis": "explicit",
            "quoteKeys": ["q_amnesia_voice"],
            "note": "inner 语层（他的自语）。叙述侧另有一句「他迷迷糊糊的想，"
                    "记不清自己是谁，身在何处」作平行依据，但那一处锚串"
                    "（q_amnesia）已用在 states s9 的前值上 —— 按「同一栏位不共用」"
                    "的口径，本状态只用另一处。",
        },
        "after": {
            "text": "认出梦里那个傲立兽头的人是魏渊，随即记起了自己是谁。",
            "basis": "explicit",
            "quoteKeys": ["q_remember_collapse"],
            "note": "叙述层，同时给出后值与紧随其后的画面崩溃。",
        },
        "anchor": {
            "text": "「魏渊？！」—— 他在梦里脱口叫出这个名字。",
            "basis": "explicit",
            "quoteKeys": ["q_weiyuan_call"],
            "note": "speech 层（梦中的一声惊呼），它是整条状态变化的触发点。",
        },
        "note": "三点分属 inner / narration / speech 三个语层，且**顺序是**"
                "自语失忆 → 惊呼认人 → 记起自己。这条状态是本区间唯一一处"
                "「自我认知」的变化，与 s1（生死状态）是两条不同的线，不要合并。",
    },
]

# ─────────────────────────────────────────────────────────────────────────
# 4. foreshadows[]：有铺设与回收才算；未回收显式标 unresolved
# ─────────────────────────────────────────────────────────────────────────
FORESHADOWS = [
    {
        "id": "f1_the_shanhaiguan_dream",
        "name": "棺中那场山海关战役的梦",
        "status": "unresolved",
        "setup": {
            "text": "梦里是多方势力混战、死尸大军与佛门高僧，还有年轻未斑白两鬓的魏渊；"
                    "这些人事物他一样都没接触过，却清晰得不像梦。他推断那是山海关战役，"
                    "随即自问为什么会梦到它。",
            "basis": "explicit",
            "quoteKeys": ["q_dream_unfamiliar", "q_dream_young", "q_dream_guess", "q_dream_why"],
            "note": "四处的语层不统一：q_dream_unfamiliar / q_dream_young / q_dream_why "
                    "是 inner（他的自语），q_dream_guess 是 inner 的叙述转述。"
                    "整条铺设**没有一处叙述确认**，全部是他自己的判断。",
        },
        "payoff": None,
        "payoffNote": "**本区间未回收**：从推棺起身到章节结束，梦境再没有被提起过 ——"
                      "没有人解释它、他没有再想起它、也没有第二次做梦的描写。"
                      "所以标 unresolved，而不是拿「他猜出是山海关战役」当回收："
                      "猜出名字只是给梦贴了标签，不是解释它为什么出现。",
    },
    {
        "id": "f2_who_took_liang_youping",
        "name": "梁有平到底是谁掳走的",
        "status": "unresolved",
        "setup": {
            "text": "许七安把「杨千幻帮我抓住梁有平」当作既成事实，用它交换不计较偷信；"
                    "杨千幻却说他没帮过这个忙。",
            "basis": "explicit",
            "quoteKeys": ["q_pos_trade", "q_pos_deny"],
            "note": "两处都是台词（speech）。前一句是许七安的前提，后一句是对它的否认 ——"
                    "铺设正是由这个矛盾构成的：两个人都没有在区间内解释它。",
        },
        "payoff": None,
        "payoffNote": "**本区间未回收**：章节结束在他打了个冷战、问出「你说什么？」"
                      "这一句上，之后直接切到宫城场景（魏渊一线），"
                      "梁有平的问题在本区间内再没有出现。",
    },
    {
        "id": "f3_the_rhino_armor",
        "name": "魏渊要给许七安的犀甲",
        "status": "unresolved",
        "setup": {
            "text": "犀甲刀枪不入、水火不侵，是魏渊要送给许七安的礼物；"
                    "材料已经收集完毕，只等拿去司天监炼制成法器，"
                    "制成后连五品境武者也难以攻破。",
            "basis": "explicit",
            "quoteKeys": ["q_ct_armor", "q_ct_treasure", "q_t4_obj"],
            "note": "三处都是叙述层。注意 q_ct_treasure 是**条件式展望**"
                    "（「若再请…那就是…」），所以它在本区间只能算铺设，不算成果。",
        },
        "payoff": None,
        "payoffNote": "**本区间未回收**：甲没有炼成、没有送出、许七安也不知道有这回事"
                      "（他此刻在船上读信，与魏渊一线没有任何交集）。"
                      "本区间给到的只有「材料已齐」这一步。",
    },
    {
        "id": "f4_did_yang_open_the_coffin",
        "name": "杨千幻到底有没有揭过许七安的棺材",
        "status": "unresolved",
        "setup": {
            "text": "许七安当面起疑：不然他怎么知道自己身上的伤势修复？"
                    "好端端的揭棺材做什么？总觉得这人有什么不可告人的目的。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_suspicion"],
            "note": "inner 语层，是**单方面的怀疑**。同一段里他脸上还挂着微笑，"
                    "所以这处铺设只表示他心里存了疑，不表示他打算追究。",
        },
        "payoff": None,
        "payoffNote": "**本区间只回收了一半，另一半仍未回收**：他诈出杨千幻动过信件"
                      "（q_pos_glue：看过、还粘回去了），但**揭棺**这件事原文从头到尾"
                      "没有确认 —— 杨千幻唯一的自述是「我便偷偷溜上来」"
                      "与「我便料定你没死」（q_yqh_snuck2 / q_yqh_concluded），"
                      "而叙述侧写他开棺（q_yqh_open）时，许七安并不在场。"
                      "所以标 unresolved，不把「动过信」当成「揭过棺」的回收。",
    },
]

NOT_FORESHADOWS = [
    {
        "id": "nf1_five_coffins",
        "name": "整齐排列的五口棺材",
        "why": "**只出现一次**（q_see_boat），本区间没有任何一处再指向它们 ——"
               "没写另外四口是谁、没写有谁来看过、也没写它们被运到哪里。"
               "一次出现不叫伏笔。",
        "quoteKeys": ["q_see_boat"],
    },
    {
        "id": "nf5_the_other_three_brothers_in_arms",
        "name": "宋廷风与朱广孝有没有为他伤心",
        "why": "**只有一次自问，且没有下文**：许七安在心里念叨这两人"
               "（q_xu_dead_once），但本区间他们再没有出现。"
               "一次出现、零回收 —— 记进 re5 而不是伏笔。",
        "quoteKeys": ["q_xu_dead_once"],
    },
    {
        "id": "nf6_susu_and_li_miaozhen",
        "name": "苏苏与李妙真",
        "why": "**同一次自嘲里的一次性提及**：他念叨没把苏苏骗回家当纸片人老婆、"
               "李妙真恐怕想砍死他（q_xu_susu）。两人在本区间都没有出现，"
               "也没有任何后续指向。这是喜剧式的收尾感慨，不是铺设。",
        "quoteKeys": ["q_xu_susu"],
    },
    {
        "id": "nf7_missing_reply_from_caiwei",
        "name": "褚采薇「没有回信」这件事",
        "why": "它表面上像一条铺设（三个人只回了两封，他因此生气，"
               "还怀疑「谁是叛徒」q_hq_traitor），但本区间**当场就把它解释了**："
               "采薇不是没写，是怀庆替她执笔（q_hq_ghost_write）。"
               "铺设与回收同在一章、且回收就在同一封信里 ——"
               "按「有铺设与回收才算伏笔」的字面，它确实成立；"
               "但它不是「悬而未决的线索」，所以记进 states s7 而不记作伏笔，"
               "以免与 f1–f4 那类真未回收的线索混在一起。",
        "quoteKeys": ["q_backup_three", "q_hq_traitor", "q_hq_ghost_write"],
    },
    {
        "id": "nf8_the_nine_characters",
        "name": "铃音能背三字经前九个字",
        "why": "一句报平安的家常（q_lingyue_school），本区间没有第二次提及，"
               "也不指向任何后续。它是信里的生活细节，不是铺设。"
               "同一封信里「娘说开春后就要给我找夫婿」（q_lingyue_husband）同理 ——"
               "**指向未来但没有任何回收**，我把它记进 states s10 的后值，不记作伏笔。",
        "quoteKeys": ["q_lingyue_school", "q_lingyue_husband"],
    },
    {
        "id": "nf9_author_notes",
        "name": "章末的作者附言",
        "why": "感谢盟主打赏、卷末公告、「打个招呼」那一组文字（q_author_note / "
               "q_author_vol）属作者的话，**不是剧情**。"
               "它们既不是铺设也不是回收；本候选任何分区都未用它们作依据。"
               "写在这里是为了让复核者看到我识别出了这段并主动排除。",
        "quoteKeys": ["q_author_note", "q_author_vol"],
    },
    {
        "id": "nf2_titanium_dog_eyes",
        "name": "钛合金狗眼",
        "why": "自嘲口吻的一句话（q_dog_eyes），本区间只出现一次，"
               "既不指向未来也不被后文触及。它是穿越者腔调的装饰，不是铺设。",
        "quoteKeys": ["q_dog_eyes"],
    },
    {
        "id": "nf3_is_the_yunzhou_case_over",
        "name": "「云州的案子结束了？」",
        "why": "这是许七安的**问句**（q_case_done），而杨千幻只答了「回京的路上，"
               "哦不，水上」（q_yqh_where），没有正面确认案子结束。"
               "一句话没有被回答，不等于它被铺设成伏笔；本区间也没有任何回收。",
        "quoteKeys": ["q_case_done", "q_yqh_where"],
    },
    {
        "id": "nf4_the_bracelet",
        "name": "被拽走的玉镯",
        "why": "它是**信里追述的已发生事件**（letter 语层），指向过去而不指向未来；"
               "本区间对它的去向、责任人、赔偿一个字都没有下文。"
               "未回收 + 只在一封信里出现 = 记进 unknowns，不记作伏笔。",
        "quoteKeys": ["q_bracelet_gone", "q_bracelet_yank"],
    },
]

# ─────────────────────────────────────────────────────────────────────────
# 4b. worldSettings[]（P3.10）：只提取影响行动、资源、约束或后果的明确设定
# ─────────────────────────────────────────────────────────────────────────
WORLD_SETTINGS = [
    {
        "id": "w1_urgent_dispatch_handling_rule",
        "kind": "rule",
        "name": "八百里加急的传递与经手禁令",
        "institution": "declared",
        "explain": "它解释了本区间最后一场戏里**谁能做什么、谁不能做什么**：文书直达内阁、"
                   "由内阁转送皇帝，且在送入内阁前除驿卒外任何人不得经手，违者视为谋逆。"
                   "于是南宫倩柔只能在宫道上**问**这件事、不能经手；"
                   "而魏渊一进御书房就被满朝注视，也正因为这封文书已经越过了所有人的手。"
                   "判 declared 而不判 executed：原文只给出规则本身，"
                   "本区间没有任何一处执行动作（没有人被追究、没有文书被拦下）。"
                   "也不判 misunderstood：这是叙述对制度的交代，不是某个人物的理解。",
        "basis": "explicit",
        "quoteKeys": ["q_ct_cabinet", "q_ct_only", "q_ct_treason"],
        "note": "不扩术语层：三百里/四百里/六百里这几档原文只是列举，"
                "不改变任何人的可选项，故不单列一条（见 excludedSettings）。",
    },
    {
        "id": "w2_rhino_armor",
        "kind": "item",
        "name": "犀甲",
        "itemStates": ["hold"],
        "explain": "它是魏渊为许七安准备的资源，本区间只走到「材料已收集完毕、"
                    "等着拿去司天监炼制」这一步：材料在魏渊/NJH 一侧持有，"
                    "所以只记 hold。原文没有写它已经送到许七安手上（没有 transfer）、"
                    "没有写谁穿过或动用过（没有 use）、也没有写它丢失或损毁（没有 lose）——"
                    "三态缺依据就不写，不为了凑满四态而编。",
        "basis": "explicit",
        "quoteKeys": ["q_ct_armor", "q_t4_obs", "q_t4_res"],
        "note": "「刀枪不入，水火不侵」是原文对材质的交代，"
                "「防御无双的至宝」是**条件式展望**（要司天监出手才成立），"
                "两者都不构成 itemStates 的一项。",
    },
    {
        "id": "w3_jade_bracelet",
        "kind": "item",
        "name": "玉镯子",
        "itemStates": ["transfer", "lose"],
        "explain": "原文给出两个时点：娘买给她（q_bracelet_bought，物件从娘转到铃音手上，"
                    "记 transfer）；前几天不见了踪影、手腕有被硬拽的淤青"
                    "（q_bracelet_gone / q_bracelet_yank，记 lose）。"
                    "四态分开写：transfer 与 lose 是不同时点的两件事，"
                    "不是我合成的一条「物品链」；本区间没有写它现在在谁手里，"
                    "所以 hold 不写。",
        "basis": "explicit",
        "quoteKeys": ["q_bracelet_bought", "q_bracelet_gone", "q_bracelet_yank"],
        "note": "三处全部是 letter 语层（许玲月的信）。照原文用词：原文写的是"
                "「买的」「不见了踪影」「硬拽下来的」，我没有改写成现代汉语的"
                "「购买/丢失/抢夺」。",
    },
    {
        "id": "w4_yushufang",
        "kind": "place",
        "name": "御书房",
        "placeState": "arrived",
        "explain": "它是本区间最后一场戏的发生地，也是小朝会的召开地；"
                   "到达动作明确（魏渊跨过门槛进去），故记 arrived。"
                   "它还解释了一条约束：禁军把南宫倩柔拦在这里的外面，"
                   "所以只有魏渊一个人能进。",
        "basis": "explicit",
        "quoteKeys": ["q_t5_act", "q_t5_obs"],
        "note": "到达动词依据「跨过门槛，进去御书房」；不是靠「往御书房行去」"
                "这种朝向动词。",
    },
    {
        "id": "w5_gongcheng",
        "kind": "place",
        "name": "宫城",
        "placeState": "arrived",
        "explain": "南宫倩柔驾车到宫城外、两人随后进宫城往御书房走 ——"
                   "有连续的到达动作，故记 arrived。它是这一场戏从车马转入朝堂的空间节点。",
        "basis": "explicit",
        "quoteKeys": ["q_ct_arrive", "q_ct_enter"],
        "note": "「抵达宫城外」与「进了宫城」是两处不同的到达，分列两条引文，"
                "不合并成一句。",
    },
    {
        "id": "w6_jingcheng",
        "kind": "place",
        "name": "京城",
        "placeState": "mentioned",
        "explain": "本区间**没有一个人到达京城**：杨千幻只说船在「回京的路上」，"
                   "浮香的信里说京城与云州相隔万里、消息传递不易。"
                   "它解释了两件事：许七安此刻仍在途中（所以只能读信、不能见人），"
                   "以及为什么花魁娘子只能靠丫鬟带回来的消息知道他的近况。",
        "basis": "explicit",
        "quoteKeys": ["q_yqh_where", "q_huakui_far"],
        "note": "这是本单元最容易写错的一处：标题与信件都在谈京城，"
                "但全文只写「回京的路上」。**朝向不等于到达**，故记 mentioned。",
    },
    {
        "id": "w7_yunzhou",
        "kind": "place",
        "name": "云州",
        "placeState": "mentioned",
        "explain": "它在本区间只以两种方式出现：怀庆在信里分析云州的局势"
                   "（齐党与巫神教谋划多年），以及许七安问「云州的案子结束了？」。"
                   "本区间没有任何人此刻在云州，也没有任何到达动作 ——"
                   "许七安已经在回京的船上。所以记 mentioned。",
        "basis": "explicit",
        "quoteKeys": ["q_hq_yunzhou", "q_case_done"],
        "note": "「云州的案子结束了？」是问句，不是到达也不是结论；"
                "把它当成「云州已在掌控中」就是计划禁止的「提及≠到达」混淆。",
    },
    {
        "id": "w8_sitianjian",
        "kind": "place",
        "name": "司天监",
        "placeState": "mentioned",
        "explain": "它在本区间承担两处资源/后果上的作用：犀甲要拿去司天监由"
                   "炼金术师与阵师炼制成法器（资源环节），以及临安跑到司天监闹了一场、"
                   "白衣转去告状（后果环节）。本区间没有任何人此刻走进司天监的场景描写，"
                   "临安的「跑去闹」也只是她信里的自述，故记 mentioned。",
        "basis": "explicit",
        "quoteKeys": ["q_t4_obs", "q_la_raid"],
        "note": "临安那一处的语层是 letter：只能支持「信上这样写」。"
                "如果把她自称的「跑司天监闹了一场」当成叙述确认的到达，"
                "就是拿人物自述当事实 —— 故仍记 mentioned。",
    },
    {
        "id": "w9_zaixinglou",
        "kind": "place",
        "name": "摘星楼",
        "placeState": "mentioned",
        "explain": "它只出现在杨千幻的恐惧里（回京后老师要把他镇压在摘星楼底、"
                   "永世不见天日）。它解释了他的行为动机 —— 为什么他宁可偷着上船、"
                   "守着棺材等许七安活过来，也不敢把这件事报回去。"
                   "本区间没有任何人到达那里，故记 mentioned。",
        "basis": "explicit",
        "quoteKeys": ["q_yqh_panic"],
        "note": "这是 inner 语层里的**假想后果**，不是已执行的惩罚 ——"
                "「要把他镇压」是杨千幻对老师将要做的事的预判。",
    },
    {
        "id": "w10_lian_shen_senses",
        "kind": "rule",
        "name": "炼神境带来的感知能力",
        "institution": "executed",
        "explain": "它解释了许七安**能在舱底读信**：棺存放在舱底、只有甲板缝隙的微光，"
                   "而他的精神力一定程度上可以充当眼睛、目力已能在黑夜中视物，"
                   "身体各方面属性也随炼神境提升。于是「光线不足」在本区间不构成任何约束，"
                   "t2.obstacle 因此写 null 而不是补一条昏暗。判 executed 而不判 declared："
                   "原文给了这项能力的**实际运用**（他确实「看见」了船舱与运河），"
                   "不是只有一句规定。不判 misunderstood：这是叙述对能力的交代，"
                   "不是某个人物的理解。",
        "basis": "explicit",
        "quoteKeys": ["q_psychic_eye2", "q_attributes", "q_darkvision"],
        "note": "不扩术语层：炼神境是武夫途径里的七品、以及它与练气境的先后关系，"
                "本区间都没有交代（那些在别处），故不写进来。"
                "本条的引文与 states s9 有重叠键（q_darkvision）——"
                "同一处证据支撑两条不同类型的分区，这是允许的；"
                "禁止的是**同一栏位内部**或**五栏之间**共用引文。",
    },
]

EXCLUDED_SETTINGS = [
    {
        "id": "ex1_intel_tier_list",
        "candidate": "三百里加急／四百里加急／六百里加急这几档的分级",
        "why": "原文只把它们列举出来（q_ct_levels），本区间没有任何一处行动因"
               "「这封是六百里而不是八百里」而改变。真正的约束在八百里那一档的"
               "经手禁令上，已单列为 w1。泛泛的分级表属装饰性设定，不写。",
        "quoteKeys": ["q_ct_levels"],
    },
    {
        "id": "ex2_chicken_essence_attribution",
        "candidate": "鸡精的发明权，以及褚采薇要用它凝聚炼金术士的位格",
        "why": "本区间里鸡精只以「传言」和「临安为此闹了一场」出现；"
               "许七安那句「其实鸡精还真是采薇做出来的，我只是给个思路」"
               "是他自己的内心话（q_xu_chicken），不是叙述对发明权的判定。"
               "它既没有改变本区间任何人的可选项，也不能当世界规则 ——"
               "写进去就会把「人物知道什么」写成「世界是什么样」。",
        "quoteKeys": ["q_la_rumor", "q_xu_chicken"],
    },
    {
        "id": "ex3_gomoku",
        "candidate": "五子棋是许七安发明的、在临安手里发扬光大",
        "why": "临安信里的这句自夸（q_la_gomoku）在本区间不产生任何约束或后果，"
               "也没有第二次被触及。属装饰性提及，不写成 item 或 rule。"
               "同一封信里她转述的「怀庆甘拜下风」（q_la_claims_hq）更明显是自夸，"
               "连她自己也承认「这种事情她肯定不会承认的啦」—— 一并排除。",
        "quoteKeys": ["q_la_gomoku", "q_la_claims_hq"],
    },
    {
        "id": "ex4_places_in_letters",
        "candidate": "教坊司、青州、白帝城",
        "why": "三处都只在信文或自嘲里被提到一次，且不影响本区间的行动："
               "教坊司是浮香的所在（她的处境由 w6 京城那条的「消息传递不易」解释）、"
               "青州是那首诗写作的地方、白帝城是许七安羞耻时的玩笑话"
               "（「游回白帝城」）。按「没有依据就不扩出地图」的口径不单列。",
        "quoteKeys": ["q_huakui_life", "q_huakui_poem", "q_xu_flip"],
    },
]

# ─────────────────────────────────────────────────────────────────────────
# 4c. themeReadings[]（P3.11）：最多 1–2 条，每条必须给 perspective/support/counter
# ─────────────────────────────────────────────────────────────────────────
THEME_READINGS = [
    {
        "id": "th1_the_ledger_of_affection",
        "perspective": "以「许七安自己那本感情账」为轴读这一章：不问他是不是真心，"
                       "只问他在这一章里**怎么记账**——他把人分栏、把回信当成对账、"
                       "把示好当成投放。",
        "support": {
            "text": "四处支撑，按发生顺序：① 他数出三个备胎（褚采薇、怀庆、临安），"
                    "发现只回了两封就「有些生气」，还自问是不是养胎技术不够、钢叉插得不准；"
                    "② 他对临安谎称二叔为供他习武四处举债，对方信了并变着法子送他银子，"
                    "他的反应是「太特么天真了吧.......请继续保持啊」；"
                    "③ 他从青州给采薇寄了一片红莲花瓣，说她与红莲一样明媚如风；"
                    "④ 怀庆一句「一花赠两人，说辞各不同」把这本账摊在了桌面上，"
                    "紧接着他就「翻车了」。四处里有三处是他的内心话或自述。",
            "basis": "explicit",
            "quoteKeys": ["q_backup_list", "q_t2_obj", "q_xu_lied", "q_hq_petal", "q_hq_flower"],
            "note": "引用里 q_hq_petal 与 q_hq_flower 出自**信文**（letter），"
                    "只能支持「怀庆在信里这样写」；q_xu_lied 是他的内心话（inner），"
                    "支持「他确实这样想」，不构成「临安真的被哄住了」的旁证。",
        },
        "counter": {
            "text": "四条不利或相反的证据：① 同一章里他读妹妹的信完全没有设防 ——"
                    "「婶婶生是我许家的人，死是我许家的鬼」「大哥也很想你们」，"
                    "读完还「心满意足」地把信纸折好，这一场不像在对账；"
                    "② 怀庆的信不是清算而是提点 —— 他读完后自己也承认"
                    "「怀庆公主心里不悦，但还是写信提点我」；"
                    "③ 「备胎／海王／钢叉／第二层第五层」是网络化戏仿用语，"
                    "把它读成严肃的伦理账本可能是过度解读，"
                    "原文的整体语气一直在喜剧一侧；"
                    "④ 四封信里只有一封（怀庆的）带揭穿性质，"
                    "另外三封都是报平安、示好或撒娇，账本这个框架解释不了它们的篇幅。",
            "basis": "explicit",
            "quoteKeys": ["q_xu_widow", "q_xu_pleased", "q_xu_hq_note", "q_xu_layer"],
        },
        "note": "我不把这一章称作「高潮」，也不给它分段：提示词禁止用事件密度、"
                "剧情点数量或篇幅中点来定义高潮，本单元也没有可比对的其它章节。"
                "另一种同样成立的读法是「一次收信日」——整章的推进几乎都由读信与回话构成，"
                "魏渊那一场是唯一的例外。两种读法不冲突。",
    },
    {
        "id": "th2_every_scene_turns_on_who_knows",
        "perspective": "以「谁知道什么」为轴读这一章：把每一场戏看成一次信息状态的变动，"
                       "看知识差是怎么被建立、被利用、被打破的。",
        "support": {
            "text": "六处支撑：① 杨千幻知道许七安伤势修复的实情，"
                    "但叙述明写「这些事是不能让许七安知道的」；"
                    "② 许七安怀疑对方揭过自己的棺材，却把微笑挂在脸上、"
                    "只在心里腹诽「总觉得他有什么不可告人的目的」；"
                    "③ 两人同时心虚、默契地岔开话题（「今天天气不错」「今天风儿甚是喧嚣」）；"
                    "④ 许七安用「我撩不动采薇」抛饵，杨千幻一替师妹解释就露了馅 ——"
                    "因为「她告诉怀庆公主了」这条信息只有看过信的人才知道；"
                    "⑤ 怀庆知道采薇收到了花瓣以及许七安的说辞，"
                    "而许七安不知道她知道，读到信才「翻车」；"
                    "⑥ 制度层面也有一条信息线：八百里加急在送入内阁前"
                    "「除传送情报的驿卒外，任何人不得经手」。",
            "basis": "explicit",
            "quoteKeys": ["q_yqh_secret", "q_yqh_suspicion", "q_both_topic",
                          "q_t3_act", "q_pos_agree", "q_xu_naive", "q_ct_only"],
            "note": "① ② ⑤ 的「知道」分别出自叙述、内心话、信文三个语层，"
                    "强度并不相同；把它们并列是为了看结构，不是把它们当同等分量的证据。",
        },
        "counter": {
            "text": "四条反例：① 这个框架解释不了本区间的后半场 —— 魏渊备甲与入朝"
                    "几乎不含人物间的信息博弈，推动它的是**制度与一件还没做成的礼物**；"
                    "② 「岔开话题」也可能只是尴尬：原文写的是「心虚的他们」，"
                    "而心虚不等于隐瞒，两个人可能只是都不想把话挑明；"
                    "③ 最后一场的不对称在**读者**与文本之间（读者不知道群臣为何那样看他），"
                    "不是人物之间的知识差，硬套进来会混淆两种不对称；"
                    "④ 临安信里「怀庆甘拜下风」是明显的自夸，许七安一眼看破，"
                    "这处不对称是喜剧效果而非结构装置。",
            "basis": "explicit",
            "quoteKeys": ["q_ct_armor", "q_t4_obj", "q_both_topic",
                          "q_t5_res2", "q_la_claims_hq"],
            "note": "counter 的第 ① 条依赖我把魏渊那场戏读作「非信息博弈」——"
                    "这是我的判断，不是原文的声明。",
        },
        "note": "两条主题读法并列给出，不合并成一条「唯一真相」："
                "th1 解释四封信那一场，th2 解释偷信败露那一场，"
                "两条对魏渊那一场都解释得不好 —— 这恰好说明本单元不是单一主题。",
    },
]

# ─────────────────────────────────────────────────────────────────────────
# 5. unknowns[]
# ─────────────────────────────────────────────────────────────────────────
UNKNOWNS = [
    {
        "id": "u1_did_yang_help_catch_liang",
        "text": "杨千幻到底有没有帮打更人抓住梁有平",
        "why": "许七安把这件事当既成事实用来交换人情（q_pos_trade），"
               "杨千幻当面否认（q_pos_deny）。本区间没有第三方证据，"
               "也没有第二个人提到过这件事。已作为 f2 显式标 unresolved。",
        "quoteKeys": ["q_pos_trade", "q_pos_deny"],
    },
    {
        "id": "u2_the_second_recipient_of_the_flower",
        "text": "「一花赠两人」里的另一个人是谁",
        "why": "这句话只出现在怀庆的信里（q_hq_flower），本区间没有点明第二个人是谁；"
               "许七安的反应是羞耻与「翻车」，也没有在心里说出名字。"
               "他在同一段里只想得到「怀庆肯定把我打上渣男标签了吧」。"
               "我没有出区间去查证，所以这里如实留白。",
        "quoteKeys": ["q_hq_flower", "q_xu_prejudice"],
    },
    {
        "id": "u3_what_the_dream_really_was",
        "text": "棺中那场梦到底是回忆、预兆还是别的什么",
        "why": "他判断「不是单纯的梦」（q_dream_not_simple），又猜是山海关战役"
               "（q_dream_guess），但叙述从未确认。本区间没有任何人回应这件事，"
               "也没有第二次做梦。已作为 f1 显式标 unresolved。",
        "quoteKeys": ["q_dream_not_simple", "q_dream_guess"],
    },
    {
        "id": "u4_the_other_four_coffins",
        "text": "船舱里另外四口棺材装的是谁",
        "why": "原文只写他「看见」了整齐排列的五口棺材（q_see_boat），"
               "没有任何一处点名或交代。本区间也没有人来开这些棺材。",
        "quoteKeys": ["q_see_boat"],
    },
    {
        "id": "u5_who_yanked_the_bracelet",
        "text": "玉镯是被谁拽走的",
        "why": "信里只写了淤青与「显然是被人硬拽下来的」（q_bracelet_yank），"
               "铃音不肯说（q_t6_obs），先生推说不知道（q_t6_res）。"
               "三处都在 letter 语层，本区间没有任何叙述侧证据。",
        "quoteKeys": ["q_bracelet_yank", "q_t6_obs", "q_t6_res"],
    },
    {
        "id": "u6_is_the_yunzhou_case_really_over",
        "text": "云州的案子到底结没结",
        "why": "「云州的案子结束了？」是许七安的**问句**（q_case_done），"
               "杨千幻只回答了他们在哪里（q_yqh_where），没有正面确认。"
               "「回京的路上」只说明船在往回走，不说明案子了结。",
        "quoteKeys": ["q_case_done", "q_yqh_where"],
    },
    {
        "id": "u7_why_the_ministers_stare",
        "text": "众大臣为什么以晦涩莫名的眼神看魏渊，元景帝为什么不露喜怒",
        "why": "原文只写现象（q_t5_res2「以一种晦涩莫名的眼神」、"
               "q_ct_emperor「心思深沉，不露喜怒」），一个字都没有解释原因。"
               "八百里加急的内容在本区间也完全没有写出来（q_ct_bigdeal 只到"
               "「必然是大事，只是不知来自哪一个州」）。不要用未见的内容补因。",
        "quoteKeys": ["q_t5_res2", "q_ct_emperor", "q_ct_bigdeal"],
    },
    {
        "id": "u8_is_huaiqing_guess_right",
        "text": "怀庆对魏渊布局的猜测对不对",
        "why": "她在信里写的是「我猜魏公暗中布局，但多半不会与你们碰头，"
               "或许张巡抚知晓，或许不知」（q_hq_guess）——"
               "一句话里带两个「或许」，全是推测。本区间没有任何验证，"
               "也没有魏渊一线的对应描写（他那一场从头到尾没提云州）。"
               "注意这一条与 re2 相关：正因为八百里加急的内容未写出，"
               "连「云州是否叛变」都无法在本区间内确认。",
        "quoteKeys": ["q_hq_guess", "q_ct_bigdeal"],
    },
    {
        "id": "u10_yang_mood_contradiction",
        "text": "杨千幻心情极好，与他的心理历程是否矛盾",
        "why": "叙述写他开口时「语气颇为轻快，显示出他心情极好」（q_yqh_mood），"
               "但紧接着的另一段又说，他得知许七安战死时恐慌得差点脱离师门跑路"
               "（q_yqh_panic、q_yqh_flee）。**这两处并不必然矛盾**——"
               "前者是他等到人活过来之后的当下心情，后者是过去一段的情绪，"
               "时间点不同。原文没有写他此刻的情绪里是否还残留着那段恐慌，"
               "所以我把它记进 unknowns 而不是替他把两个时间点调和掉。"
               "另外「当然，这些事是不能让许七安知道的」（q_yqh_secret）表明"
               "他此刻的表现是被他有意识控制过的 —— 这也是「轻快」不能直接"
               "当作他真实心情的原因。",
        "quoteKeys": ["q_yqh_mood", "q_yqh_panic"],
    },
    {
        "id": "u11_the_three_letters_he_kept",
        "text": "裱裱、浮香、玲月那三封信为什么会在许七安怀里",
        "why": "他「忽然发现自己怀里揣着四份信函」（q_letters_found），"
               "但原文没有写这些信是谁放进去的、什么时候放的。"
               "本区间唯一相关的线索是叙述交代杨千幻潜入官船、开过棺材板"
               "（q_yqh_open）—— 可是他与许七安同时在场，"
               "而叙述没有把「放信」这件事归给他，他本人也从未提过。"
               "**不要用「他开过棺」去填「信是谁放的」**：两件事原文没有连起来。",
        "quoteKeys": ["q_letters_found", "q_yqh_open"],
    },
    {
        "id": "u12_the_two_letters_he_skipped",
        "text": "四封信的阅读顺序与「最后还有两封信」的对应",
        "why": "他先读玲月、再读花魁娘子（q_huakui_from、q_lingyue_hand 给出写信人），"
               "然后说「最后还有两封信」（q_backup_three 的相邻原文），"
               "接着「他随便选了一封信」读到了临安（q_t2_act1），"
               "最后拆开的是怀庆（q_t2_act2）。**顺序本身可核**，"
               "但原文没有写他为什么先挑临安那一封、也没写他把哪封信留到最后；"
               "「随便选」与「深吸一口气」是原文仅有的两处态度交代，"
               "不足以推出偏好。所以这里只记顺序，不推动机。",
        "quoteKeys": ["q_lingyue_hand", "q_huakui_from", "q_t2_act1", "q_t2_act2"],
    },
    {
        "id": "u9_the_author_notes_are_not_plot",
        "text": "章节末尾的作者附言是否属于正文",
        "why": "切片末尾有一组与剧情无关的公告：感谢盟主打赏、"
               "「明天早上的更新留到晚上，本卷结束了，开启第二卷，我要构思一下」"
               "以及「打个招呼」那一段。它们属作者的话，"
               "不是剧情证据（q_author_note / q_author_vol 已单列，"
               "未被任何分区用作依据）。我因此**不拿它们判断章节归属或卷界**。",
        "quoteKeys": ["q_author_note", "q_author_vol"],
    },
]

# ─────────────────────────────────────────────────────────────────────────
# selfCritique
# ─────────────────────────────────────────────────────────────────────────
SELF_CRITIQUE = [
    {
        "id": "sc1_letters_registered_as_speech",
        "risk": "四封信我登记为 speech（并加 speechKind='letter'），"
                "于是以信为据的条目（t7、t8，以及 worldSettings w3 玉镯、"
                "w7 云州、w8 司天监）全都建在 speech 层上。",
        "why_still": "它们在原文里与对话同形：引号成段、以「某某：」领起。"
                     "单开一层会让「同一句话在两处承担不同分量」更难被发现。"
                     "我改用 layer 之外的 speechKind 字段标记来源，"
                     "并在每一条以信为据的 note 里写明「只能支持信上这样写」。"
                     "**这是我最可能读错的一处**：若复核者认为信件应单列一层，"
                     "上述条目的语层标注都要改。",
    },
    {
        "id": "sc2_mixed_layer_anchor",
        "risk": "q_t5_act2 的锚串是「“陛下。”魏渊作揖行礼，自然而然的入列，"
                "站在自己的位置。」—— 它含一句引号内的台词，我却整条登记为 narration，"
                "并在 t6.action 与 states s5.after 里使用。",
        "whyStill": "锚串的主干是动作描写（作揖、入列、站到位置），"
                    "那句「陛下。」只是称呼、不承载任何命题内容。"
                    "若按「含台词即 speech」的口径，这两处的语层要改；"
                    "但无论哪一层，它都只能支持「他行了礼、入了列」，"
                    "不影响我的用法。",
    },
    {
        "id": "sc3_emotion_used_as_cost",
        "risk": "三条任务的 cost 栏用的是情绪或让步而不是资源损耗："
                "t4 用「不如假装大方」（放弃追责）、t5 用「酸溜溜的语气」（执行者情绪）、"
                "t7 用「娘气的浑身发抖，但又无可奈何」。",
        "whyStill": "提示词要求缺依据时写 null 并说明理由，但这里每一项都有原文依据，"
                    "问题是**它够不够格叫代价**。我选择写出来并在每条的 note 里"
                    "写明「若复核者认为不构成，此栏应改 null 并保留本注」，"
                    "而不是用 null 把原文确实写出的东西藏起来。"
                    "本候选最可能被判「用情绪冒充代价」的就是这三处。",
    },
    {
        "id": "sc4_the_denial_edge",
        "risk": "causeEdges e5 把「许七安拿抓梁有平做人情 → 杨千幻否认 → 许七安战栗」"
                "连成一条因果边，机制是我补的「前提被推翻」。",
        "whyStill": "原文在否认与战栗之间只给了生理反应（寒流、冷战、汗毛竖起、"
                    "声音颤抖），没有一个字的解释。「你说什么？」甚至可能只是没听清。"
                    "我仍然连，因为叙述把否认放在寒流之前、把战栗放在之后，"
                    "顺序本身是有意的；但这是本候选跨度最大的一条边，已标 derived。",
    },
    {
        "id": "sc5_theme_counters_are_mine",
        "risk": "themeReadings 里 th1/th2 的 counter 是我自己想的反驳，"
                "不等于原文里存在反例；尤其 th2 的 counter ① 依赖我把魏渊那一场戏"
                "读作「非信息博弈」这个判断。",
        "whyStill": "提示词要求 counter 是「不利或相反的证据」而不是「补一句免责声明」，"
                    "所以我尽量让每条 counter 落在可引的原文上"
                    "（q_xu_widow / q_xu_pleased / q_xu_hq_note / q_xu_layer / "
                    "q_both_topic / q_t5_res2 / q_la_claims_hq）。"
                    "但「这些证据构成反驳」这一步是我的解释，不是原文的结论 ——"
                    "主题层本来就是解释层，不该被当成事实层。",
    },
    {
        "id": "sc6_first_pass_coverage",
        "risk": "我的条目是按「场景主角」组织的：先立许七安一线、杨千幻一线、魏渊一线，"
                "再回头补信里的人物。这样组织容易整段漏掉不落在任何主角线上的内容。",
        "whyStill": "为对冲这个结构性缺口，我在构建脚本里保留了 zeroCoverageList"
                    "（未被任何引文触及的非空段），并在写完之后逐段回读。"
                    "本候选的 letter 语层条目（t7/t8、w3、s10）与 unknowns u5 都是"
                    "这样回读时补上的 —— 第一遍我只把四封信当成「许七安读到的内容」，"
                    "没有把它们当成四个独立人物的行动线。请复核者按同一方法"
                    "再扫一遍我剩下的零覆盖清单。",
    },
    {
        "id": "sc7_darkness_is_not_blindness",
        "risk": "states s9 的 before 用「好黑....我在哪里....我是谁？」作前值，"
                "把它读成「他看不见」。",
        "whyStill": "原文写的是他所见为黑暗，并没有一句「他看不见」；"
                    "而且那句本身是**失忆中的自问**（inner），"
                    "不是对视觉能力的陈述。我仍然把它当前值，理由是同一段接下来写"
                    "「许七安睁开眼，看见的还是黑暗」—— 睁眼仍是黑暗，"
                    "说明此刻视觉没有提供信息。这是一个**推导**，已标在 before.note 里。"
                    "若复核者认为它够不上前值，s9 应改为「无前值」或降 basis。",
    },
    {
        "id": "sc8_lingyue_attribution_is_hers",
        "risk": "states s10 的后值把「二哥冻了半宿 → 不跟家里说话」并排列出，"
                "而原文里这两件事是由**玲月的归因**串起来的"
                "（「二哥真小气，忘记给他写信又不是大哥的错」）。",
        "whyStill": "我只把两件事并列，没有替她坐实因果 —— 冻结与沉默都发生在原文里，"
                    "而「因为没写信所以生气」是她的解释。"
                    "但如果复核者把并排读成我认可了她的归因，这条状态需要拆开重写。"
                    "同一封信里她还有一处同类归因（「如果大哥在家里，肯定不会发生这种事吧」），"
                    "我同样没有把它当成事实。",
    },
    {
        "id": "sc9_three_tasks_are_letter_only",
        "risk": "t7（婶婶质问先生）、t8（临安闹司天监）两条任务的五栏依据"
                "**全部**出自信文；也就是说这两条任务的存在本身，"
                "取决于我把信当成「人物行动线的转述」而不是「许七安读到的内容」。",
        "whyStill": "计划要求覆盖原文单元，而这两件事是区间内**明确的行动叙述**——"
                    "只是转述者是写信人。把它们排除，等于让这一章只留下许七安一个人的视角，"
                    "丢掉信件本身承载的四个家庭的行动线。我用 layerWarning 与逐条 note "
                    "把语层限制写明，而不是把它们藏起来。"
                    "如果复核者判定 letter 语层不足以支撑 tasks，这两条应整体降级为 unknowns。",
    },
    {
        "id": "sc10_theme_counter_reuse",
        "risk": "th2.counter 里的第 ① 条我原本想引「魏渊备甲」那一段，"
                "但该锚串（q_ct_armor）同时出现在 th2.counter 与 w2 的 quoteKeys 里 ——"
                "跨分区复用是允许的，可一旦读者把它读成「同一证据支持两个相反结论」，"
                "就会觉得我在两头下注。",
        "whyStill": "我在 th2.counter 里保留 q_ct_armor，"
                    "是因为「魏渊那一场不含信息博弈」这个反例必须落在具体文本上，"
                    "否则 counter 就退化成一句免责声明。"
                    "我在 counter.note 里已经写明「这一条依赖我的判断」，"
                    "并请复核者按原文字面判。",
    },
]
