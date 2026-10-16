# -*- coding: utf-8 -*-
"""引文锚串声明（只写锚串与语层，**不写任何数字偏移**）。

语层口径（本单元适用）：
  speech    引号内的人物言辞（对话）；**本单元另有四封信**——它们同样以引号成段
            出现，也登记为 speech，但额外登记进 LETTER_KEYS，生成侧会给它们加
            `speechKind='letter'`。信只能承担「信上这样写」，其内容不得当作叙述事实。
  inner     叙述转述的人物内心（心说 / 腹诽 / 自由间接引语）
  narration 其余叙述层

为什么信件不单开一个 layer：它们与对话在原文里是同一形态（引号成段），
单开一层会让「同一句话在两处承担不同分量」更难被发现；改成在 layer 之外
加 `speechKind` 字段，语层仍是三分，来源另标。

硬约束（gen_quotes.py 强制）：
  · 每个锚串在 docs[0].text **全文**命中 1 次、在单元切片内命中 1 次，且落在区间内；
  · 锚串之间不得重复、不得互相包含（防假多样性：两个键指向同一段文字，
    看上去引文很多，实际只有一条证据）。

因此：**一个引文字面量只登记一次**，多处需要就复用同一个键。
"""

ANCHORS = {
    # ══════ 第一场：棺中梦境与醒来 ═══════════════════════════════════════
    "q_amnesia": ("narration", "他迷迷糊糊的想，记不清自己是谁，身在何处。"),
    "q_amnesia_voice": ("inner", "好黑....我在哪里....我是谁？"),
    "q_dream_split": ("narration", "他刚这么想，眼前的黑暗便劈开，光明穿透进来，视线里果然是一片战场。"),
    "q_weiyuan_call": ("speech", "“魏渊？！”"),
    "q_remember_collapse": ("narration", "许七安心头一震，忽然记起自己是谁了，也就是这个瞬间，战场画面崩溃，归于无边无际的黑暗。"),
    "q_see_boat": ("narration", "他“看见”了黑暗的船舱，看见了整齐排列的五口棺材，看见了缓速航行的官船，看见了波光荡漾的运河。"),
    "q_psychic_eye": ("narration", "这是他踏入炼神境后获得的神异。"),
    "q_psychic_eye2": ("narration", "不知道其他炼神境武者是怎么样的，反正许七安的精神力一定程度上可以充当眼睛。"),
    "q_attributes": ("narration", "踏入炼神境后，身体各方面属性得到提升。"),
    "q_darkvision": ("narration", "而今他的目力，已经能做到黑夜中视物，毫无障碍。"),
    "q_dog_eyes": ("narration", "哪天即使钛合金狗眼瞎掉，他也丝毫不怵。"),
    "q_dream_not_simple": ("inner", "“我刚才看见的梦境....不，应该不是单纯的梦，梦哪有这般清晰？"),
    "q_dream_unfamiliar": ("inner", "什么死尸大军、佛门高僧....这些我都没接触过，怎么会梦到？"),
    "q_dream_young": ("inner", "“梦里为什么会有魏渊？他看起来还很年轻....至少两鬓没有斑白"),
    "q_dream_recall": ("narration", "许七安躺在棺材里，回忆着梦境里看到的画面"),
    "q_dream_factions": ("narration", "多方势力混战。"),
    "q_dream_guess": ("inner", "再结合魏渊的出现，以及他的事迹，许七安心里当即有了猜测——山海关战役。"),
    "q_dream_legend": ("inner", "魏渊的事迹里，最出名的就是山海战役......诸国混战，规模庞大，完美契合史书记载的山海关战役....."),
    "q_dream_why": ("inner", "只是我为什么会梦到山海关战役？"),
    "q_coffin_hold": ("narration", "棺材存放在舱底，只有微弱的光从甲板缝隙里穿透进来。"),
    "q_deck_light": ("inner", "甲板居然透光，这船应该好好修缮了....."),

    # ── 杨千幻：重逢与他的隐情 ──────────────────────────────────────────
    "q_yqh_wake": ("narration", "新鲜的空气涌入，他深吸一口气，翻身坐起"),
    "q_yqh_wake_voice": ("speech", "“你醒了。”"),
    "q_yqh_reveal": ("narration", "许七安被吓的一抖，这才发现，左侧三米外盘坐着一个白衣人，背对着他......好了，身份揭晓了，杨千幻。"),
    "q_where_ask": ("speech", "“我们这是在哪里？”"),
    "q_yqh_where": ("speech", "“回京的路上，哦不，水上。”"),
    "q_yqh_mood": ("narration", "杨千幻语气颇为轻快，显示出他心情极好："),
    "q_yqh_patience": ("narration", "杨千幻耐心的听他唠嗑。"),
    "q_case_done": ("speech", "“云州的案子结束了？”许七安脸上喜色浮动：“哎，这破案子终于完结了，老子终于不用熬夜爆肝。"),
    "q_xu_dead_once": ("speech", "“我死了一回，也不知道宋廷风和朱广孝有没有为我伤心，可能更伤心五次白嫖的机会没有了吧...."),
    "q_xu_susu": ("inner", "哎，最后还是没有把苏苏骗回家当纸片人老婆，李妙真恐怕想砍死我的心都有了，幸好老子早死一步，不然还挺尴尬的...."),
    "q_yqh_ask_boat": ("speech", "“对了，你怎么也在船上？”许七安问道。"),
    "q_yqh_mission": ("speech", "“我奉师命来云州办事，现在事了，自然就回去了"),
    "q_yqh_snuck": ("speech", "恰好打更人送你们的尸骨回京"),
    "q_yqh_snuck2": ("speech", "我便偷偷溜上来。"),
    "q_yqh_noticed": ("speech", "随后，我就发现你身上的刀伤箭孔，竟诡异的修复"),
    "q_yqh_concluded": ("speech", "我便料定你没死。"),
    "q_yqh_waited": ("speech", "等了一旬，嘿，还真就活过来了。"),
    "q_yqh_panic": ("inner", "得知许七安战死的消息后，他心说完了完了，回京后老师要把我镇压在摘星楼底，永世不见天日了。"),
    "q_yqh_flee": ("inner", "恐慌的差点脱离师门跑路。"),
    "q_yqh_pity": ("inner", "同时觉得很可惜，辣么有趣的一个小子，怎么就战死了呢，怎么就想不开呢，竟然用自己20岁的生命去换一个老头子的命。"),
    "q_yqh_open": ("narration", "他一路尾随，潜入官船，打开了许七安的棺材板"),
    "q_yqh_healed": ("narration", "这小子身上的伤势竟离奇恢复，心跳渐渐复苏，居然是否极泰来的气象。"),
    "q_yqh_wait": ("narration", "于是，杨千幻便开心的守在棺材边，屎都没时间拉。"),
    "q_yqh_secret": ("inner", "当然，这些事是不能让许七安知道的。"),
    "q_yqh_suspicion": ("inner", ".....他是不是揭我棺材了？不然怎么知道我身上的伤势修复.....好端端的揭我棺材干嘛.....总觉得他有什么不可告人的目的...."),
    "q_yqh_ask": ("speech", "“监正大人派你来云州做什么？”"),
    "q_revive_q": ("speech", "“你怎么做到死而复生的？”"),
    "q_both_silent": ("narration", "问完，两人望着彼此，陷入了沉默。"),
    "q_both_topic": ("narration", "几秒后，心虚的他们又默契的同时岔开话题："),
    "q_topic_weather": ("speech", "“今天天气不错。”"),
    "q_both_silent2": ("narration", "许七安和杨千幻又沉默了下来。"),

    # ══════ 四封信 ═══════════════════════════════════════════════════════
    "q_letters_found": ("narration", "他忽然发现自己怀里揣着四份信函。"),
    "q_letter_open": ("narration", "随手拆开信封，接着微光阅读起来。"),

    # —— 第一封：许玲月（妹妹）
    "q_lingyue_hand": ("narration", "字迹娟秀，是玲月妹子的寄来的信。"),
    "q_lingyue_safe": ("speech", "知道大哥在外一切安好，我便放心了。"),
    "q_lingyin_school": ("speech", "你离京没多久，铃音就被迫去塾堂读书啦，一切都是二哥操办的。"),
    "q_lingyue_school": ("speech", "现在，铃音已经会背诵三字经的前九个字了，爹和娘刚得知时，险些喜极而泣。"),
    "q_bracelet_bought": ("speech", "娘给她买的玉镯子"),
    "q_bracelet_gone": ("speech", "价值十两的玉镯子，前几天不见了踪影。"),
    "q_bracelet_yank": ("speech", "她的手腕有浅浅的淤青，显然是被人硬拽下来的。"),
    "q_t6_obj": ("speech", "问她是谁干的"),
    "q_t6_obs": ("speech", "她也不说，完全不当一回事。"),
    "q_spring_family": ("speech", "春祭将近，爹每日都归家都很晚"),
    "q_uncle_busy": ("speech", "要么就宿在外营，没时间管理家里的事。"),
    "q_mother_secret": ("speech", "娘没敢告诉他"),
    "q_t6_act": ("speech", "自己去找塾堂先生质问"),
    "q_t6_res": ("speech", "但先生推说不知道，兴许是铃音自己弄丢了。"),
    "q_t6_cost": ("speech", "娘气的浑身发抖，但又无可奈何。"),
    "q_if_brother_home": ("speech", "如果大哥在家里，肯定不会发生这种事吧。如果二哥在家，肯定骂的先生无地自容。"),
    "q_second_brother": ("speech", "不过二哥最近很生气，听爹说，他在寒风里冻了半宿，第二天回家拿钱粮时，就不跟我们说话了。"),
    "q_lingyue_blame": ("speech", "二哥真小气，忘记给他写信又不是大哥的错，大哥也是很忙的呀。”"),
    "q_lingyue_husband": ("speech", "“对了，娘说开春后，就要给我找夫婿，娘真讨厌，她怎么不自己嫁。铃音很想你，天天嚷嚷着要找大哥。我，我....也很想你。”"),
    "q_xu_widow": ("inner", "说什么傻话，婶婶怎么能改嫁？婶婶生是我许家的人，死是我许家的鬼"),
    "q_xu_pleased": ("narration", "看完了，许七安心满意足的折叠好信纸，装回信封里。"),
    "q_misc_kuku": ("inner", "好可惜，没能目睹二郎狼狈模样，库库库...."),

    # —— 第二封：浮香（花魁娘子）
    "q_huakui_from": ("narration", "这是花魁娘子的回信。"),
    "q_huakui_life": ("speech", "我在教坊司一切安好，就是总爱瞌睡，醒来便摘摘梅花，四处走走。"),
    "q_huakui_wine": ("speech", "我酿了一坛梅花酒，盼君归来，举杯共饮。"),
    "q_huakui_guests": ("speech", "偶尔也会出去陪客人小酌几杯，听他们高谈阔论，其实奴家是想听到关于你的消息"),
    "q_huakui_far": ("speech", "然云州与京城相隔万里，消息传递不易。"),
    "q_huakui_poem": ("speech", "“前些日子，倒是丫鬟带回来一个消息，听说许郎在青州新作一首诗，被紫阳居士奉若至宝，铭刻在碑文上，警示世人。"),
    "q_huakui_nails": ("speech", "“许郎，奴家夜夜想你，指甲修的干干净净啦。”"),

    # —— 备胎清单
    "q_backup_list": ("narration", "最后还有两封信，他回忆了一下自己养的备胎们：褚采薇、怀庆、临安。"),
    "q_backup_three": ("narration", "分明是三个人呀，哦不，三个胎呀，怎么只回了两封信。"),
    "q_t2_obj": ("inner", "许七安有些生气，心说谁没给我回信？是我养胎技术不够好，还是本海王的钢叉，插的不够准？"),

    # —— 第三封：临安公主
    "q_t2_act1": ("narration", "他随便选了一封信，展开阅读："),
    "q_la_guard": ("speech", "云州的案子何时结束？本宫不是想你，只是觉得春祭在即，好多侍卫都休沐回家啦，身边没几个可用的奴才了。”"),
    "q_la_gomoku": ("speech", "“你发明的五子棋在本宫手里发扬光大啦，人人都夸我是兰心蕙质，聪明绝顶"),
    "q_la_claims_hq": ("speech", "就连讨厌的怀庆也对我心悦诚服，五体投地，私底下与我说：临安智慧远胜与我，怀庆甘拜下风。"),
    "q_la_no_admit": ("speech", "“但是这种事情她肯定不会承认的啦，我随口告诉你一声，你也别记在心里，怀庆毕竟是公主，留她几分薄面。"),
    "q_la_gift": ("speech", "“本宫也不占你便宜，春祭将近，父皇送了我一些金银玉器，绸缎首饰。等你回来，随便去本宫库房挑几件。”"),
    "q_xu_lied": ("inner", "哈哈哈，临安这个傻妞儿，我哄她说二叔为了供我习武，四处举债，日子过的艰难，她竟然就当真了，变着法子送我银子，太特么天真了吧"),
    "q_la_misbelief": ("speech", "“那个鸡精是怎么回事啊，不是你发明的吗？"),
    "q_la_rumor": ("speech", "为什么外头都在传，说是司天监的褚采薇发明的。"),
    "q_la_raid": ("speech", "本宫气的要死，就跑司天监闹了一场。"),
    "q_la_scolded": ("speech", "“司天监的白衣不敢对我出手，竟跑去父皇那里告状，本宫被父皇狠狠臭骂了一顿。等你回来，本宫再带你去讨回公道。”"),
    "q_xu_chicken": ("inner", "额.....其实鸡精还真是采薇做出来的，我只是给个思路。嗯，她要利用鸡精来凝聚炼金术士的位格，这件事早就与我知会过了。"),
    "q_la_protect": ("inner", "许七安有些小感动，裱裱还是很护犊子的。"),
    "q_t2_act2": ("narration", "他把临安的信塞回信封，深吸一口气，打开了最后一封信。"),

    # —— 第四封：怀庆公主
    "q_hq_traitor": ("narration", "怀庆和采薇，你俩到底谁是叛徒，现在就见分晓了。"),
    "q_hq_yunzhou": ("speech", "云州环境复杂，匪患由来已久，齐党与巫神教既以秘密谋划多年，想必在云州积蓄了不小的势力。"),
    "q_hq_careful": ("speech", "“切记小心行事，即使有姜律中一位四品武夫，也不是万分稳妥。若是锁定目标，一定要以雷霆之势缉拿，不给对方应对的时间。"),
    "q_hq_guess": ("speech", "“我猜魏公暗中布局，但多半不会与你们碰头，或许张巡抚知晓，或许不知。"),
    "q_hq_alone": ("speech", "你虽断案如神，奈何实力有限，切莫单独行动。”"),
    "q_t2_res": ("narration", "信是怀庆的啊。"),
    "q_hq_complex": ("inner", "许七安心情很复杂，失望和喜悦都有，失望的是大眼萌妹竟是个渣女，枉费我一往情深，将她收入鱼塘，而她如此绝情。"),
    "q_hq_relief": ("inner", "喜悦的是怀庆没有当渣女，心里还是惦记着本铜锣的。"),
    "q_hq_half": ("inner", "手心手背都是肉，面对这样的结局，许七安喜忧参半。"),
    "q_hq_scary": ("inner", "“怀庆真可怕啊，智商未免太高了吧......不，这不仅仅是智商，还有对局势的分析，对人心的把控，她连魏公的心思都能把握到"),
    "q_hq_disciple": ("narration", "怀庆公主似乎还是魏渊的半个弟子，有这份本事倒也不奇怪"),
    "q_hq_caiwei": ("speech", "“前些日子，采薇来我宫苑用膳，闲聊时说起了你"),
    "q_hq_caiwei_worry": ("speech", "她说最近在烦恼怎么给你回信，因为她不爱读书，怕写的不好让你笑话。"),
    "q_hq_petal": ("speech", "“她还说：许宁宴真有心，从青州寄了一片红莲花瓣给我。说我与红莲一样明媚如风。"),
    "q_hq_ghost_share": ("speech", "“采薇与本宫说起时，眼角眉梢挂着笑意"),
    "q_hq_ghost_write": ("speech", "我便与采薇说：本宫替你执笔回信。她欣然同意。"),
    "q_hq_flower": ("speech", "“呵，许大人真是风流倜傥，一花赠两人，说辞各不同，偏还形容的恰到好处。"),
    "q_hq_admire": ("speech", "“本宫佩服。”"),
    "q_xu_stunned": ("narration", "......许七安脸色呆滞的看着信纸。"),
    "q_xu_flip": ("speech", "“翻车了.....”许白嫖老脸一红，羞耻的想要跳进运河，游回白帝城。"),
    "q_xu_naive": ("inner", "卧槽，忘记褚采薇是个情窦未开的少女，她和怀庆关系又好，与好闺蜜分享这种事完全没心理障碍啊。"),
    "q_xu_prejudice": ("inner", "怀庆本来就对我有偏见，离京时都不肯见我，如今采薇姑娘这波偷家......怀庆肯定把我打上渣男标签了吧。"),
    "q_t2_cost": ("narration", "许七安臊的面红耳赤。"),
    "q_xu_face": ("inner", "许某人也是有头有脸的人啊，你这样让我怎么有脸回京.....哦，我已经死了，那没事了。"),
    "q_xu_hidden": ("inner", "同时又觉得庆幸，因为裱裱、浮香、玲月妹子的信，怀庆是看不到的。"),
    "q_xu_why_hidden": ("inner", "后两者不用说，与怀庆没有交集，裱裱虽是她姐妹，但两人势如水火，不可能分享这种闺房密信。"),
    "q_xu_friends": ("inner", "还好我知道褚采薇是个榆木脑袋，没有与她调情，说的都是些沿途的美食"),
    "q_xu_hq_note": ("inner", "恐怕正是如此，怀庆公主心里不悦，但还是写信提点我。"),
    "q_xu_layer": ("inner", "嘿嘿，想不到吧怀庆，你以为我在第二层，其实我在第五层。"),

    # ══════ 第二场：偷信一事被诈出来 ═════════════════════════════════════
    "q_pos_who": ("speech", "“是谁写的信？”"),
    "q_pos_friend": ("speech", "“京城的朋友寄来的信。”许七安面不改色。"),
    "q_pos_mistress": ("speech", "“是相好的吧。”杨千幻道。"),
    "q_pos_wary": ("speech", "许七安一下警惕起来：“你偷看我的信？”"),
    "q_t3_obs": ("speech", "杨千幻冷笑道：“我杨千幻不屑做这等龌龊之事。”"),
    "q_t3_act": ("speech", "毕竟是四品术士.....许七安颔首，道：“话说回来，你家的采薇师妹真是个榆木脑袋，到她那年纪，也该少女怀春了吧。我愣是撩不动，给她写信，她还.....”"),
    "q_pos_agree": ("speech", "杨千幻赞同道：“采薇师妹的确开窍的晚，她只是当成了寻常朋友的书信往来，才告诉怀庆公主的。也不是完全对你无意，至少你在她心里是很有重要的朋友。”"),
    "q_t3_res_quote": ("speech", "许七安目光骤然犀利：“你特娘的怎么知道她告诉怀庆了？”"),
    "q_t3_res": ("narration", "逼王好半天没说话，知道自己被套路了"),
    "q_yang_shame": ("narration", "顿时，他也体会到了许七安刚才的羞耻感。"),
    "q_pos_glue": ("inner", "你不但偷看我的信，你特么还给粘回去了....."),
    "q_pos_trade": ("speech", "“算了，看在你帮我抓住梁有平的份上，我也懒得计较。”许七安告诫道："),
    "q_t3_obj": ("speech", "“但你千万不要把信的事外传。”"),
    "q_t3_cost": ("narration", "事已至此，杨千幻看都看了，他还能让时光倒流不成，不如假装大方。"),
    "q_pos_deny": ("speech", "杨千幻一愣：“我没帮你们抓梁有平啊。”"),
    "q_pos_cold": ("narration", "甲板缝隙里，一阵寒流扑进来，吹在许七安脖颈。"),
    "q_pos_shiver": ("speech", "他缓缓打了个冷战，汗毛一根根竖起，连声音也带着一丝颤抖：“你说什么？”"),

    # ══════ 第三场：宫城·御书房 ═════════════════════════════════════════
    "q_ct_arrive": ("narration", "冬日的暖阳高挂，南宫倩柔驾车抵达宫城外。"),
    "q_ct_aide": ("narration", "停泊好马车，他把缰绳丢给迎上来的羽林卫，弯腰摘下木凳，打开马车的门，道："),
    "q_ct_father": ("speech", "打开马车的门，道：\n\n    “义父，到了。”"),
    "q_ct_weiyuan": ("narration", "穿着奢华的大青袍，两鬓斑白的魏渊，钻出马车，踏着木凳下来。"),
    "q_ct_enter": ("narration", "两人进了宫城，往御书房行去。"),
    "q_ct_urgent_q": ("speech", "“义父，听说今早有八百里加急？”南宫倩柔问道。"),
    "q_ct_levels": ("narration", "大奉情报等级，分为三百里加急、四百里加急、六百里加急，以及最高的八百里加急。"),
    "q_ct_cabinet": ("narration", "其中八百里加急的情报，直接送入内阁，由内阁转送皇帝。"),
    "q_ct_only": ("narration", "在送入内阁前，除传送情报的驿卒外，任何人不得经手。"),
    "q_ct_treason": ("narration", "否则视为谋逆。"),
    "q_ct_meeting": ("narration", "魏渊脸色凝重的点头"),
    "q_ct_smallcourt": ("narration", "八百里加急文书送进宫后，没多久，陛下就在御书房召开了小朝会。"),
    "q_ct_bigdeal": ("narration", "八百里加急的，必然是大事，只是不知来自哪一个州。"),
    "q_ct_sigh": ("speech", "“真是多事之秋！”魏渊轻叹一声"),
    "q_t4_act": ("speech", "让你准备的犀甲，进展如何？”"),
    "q_t4_res": ("speech", "“材料已经收集完毕，就等拿去司天监炼制了。”"),
    "q_t4_sour": ("narration", "南宫倩柔酸溜溜的语气。"),
    "q_ct_armor": ("narration", "犀甲是魏渊要送给许七安的礼物，犀甲刀枪不入，水火不侵。"),
    "q_t4_obs": ("narration", "若再请司天监的炼金术师和阵师出手，炼制成法器。"),
    "q_ct_treasure": ("narration", "那就是一件防御无双的至宝，哪怕是五品境的武者，也休想轻易攻破。"),
    "q_t4_obj": ("narration", "南宫倩柔知道魏渊的想法，他要为许七安补足最后的短板，为这株尚未长成的树苗保驾护航。"),
    "q_t5_obs": ("narration", "临近御书房，南宫倩柔被禁军拦下"),
    "q_t5_obs2": ("narration", "魏渊独自一人前行。"),
    "q_t5_act": ("narration", "魏渊跨过门槛，进去御书房。"),
    "q_t5_res": ("narration", "他随意扫了眼两侧的群臣，眉头顿时一皱。"),
    "q_t5_res2": ("narration", "众大臣都在看他，以一种晦涩莫名的眼神。"),
    "q_ct_emperor": ("narration", "元景帝也在看着魏渊，不过老皇帝心思深沉，不露喜怒。"),
    "q_t5_act2": ("narration", "“陛下。”魏渊作揖行礼，自然而然的入列，站在自己的位置。"),

    # ══════ 正文 / 作者附言分界（附言不作为剧情证据）═══════════════════════
    "q_author_note": ("narration", "PS：感谢“倚剑拄刀的老人”、“社会逼你坚强”、“狂歌~”的盟主打赏。会加更的。"),
    "q_author_vol": ("narration", "PS：明天早上的更新留到晚上，本卷结束了，开启第二卷，我要构思一下。"),
}

# 这四封信以引号成段出现（原文形态与对话相同），但它们是**书面文书**：
# 生成侧会给这些键加 speechKind='letter'，候选里也只能用它们支持
# 「信上这样写」，不得当作叙述事实。
LETTER_KEYS = (
    "q_lingyue_safe", "q_lingyin_school", "q_lingyue_school",
    "q_bracelet_bought", "q_bracelet_gone", "q_bracelet_yank",
    "q_t6_obj", "q_t6_obs", "q_spring_family", "q_uncle_busy", "q_mother_secret",
    "q_t6_act", "q_t6_res", "q_t6_cost", "q_if_brother_home",
    "q_second_brother", "q_lingyue_blame", "q_lingyue_husband",
    "q_huakui_life", "q_huakui_wine", "q_huakui_guests", "q_huakui_far",
    "q_huakui_poem", "q_huakui_nails",
    "q_la_guard", "q_la_gomoku", "q_la_claims_hq", "q_la_no_admit",
    "q_la_gift", "q_la_misbelief", "q_la_rumor", "q_la_raid", "q_la_scolded",
    "q_hq_yunzhou", "q_hq_careful", "q_hq_guess", "q_hq_alone",
    "q_hq_caiwei", "q_hq_caiwei_worry", "q_hq_petal", "q_hq_ghost_share",
    "q_hq_ghost_write", "q_hq_flower", "q_hq_admire",
)
