# -*- coding: utf-8 -*-
"""read:dafeng:L1:0237 内容核（w-sanguo-0 独立精读）。

设计要点（为什么这样写）：
- 引文**一律不写偏移**，只写「在第几段(段落号见 paras.json)里、逐字子串是什么、第几次出现」。
  真实偏移由 build_candidate.py 用 str.find 现算。这样「引文与偏移不一致」这类错误
  在结构上不可能发生：只要我手打的子串不是原文，构建就直接报错退出，而不是产出错引文。
- 判断与原文严格分开：我的分析文字里不出现直角引号，原文一律只放在 quote 字段。
- 凡是「人物说的」「人物的猜测/侧写」都单独标层，不允许混成叙述事实。
"""

# ── 引文表 ────────────────────────────────────────────────────────────────
# 值 = (段号, 逐字子串, 第几次出现[默认0])
Q = {
    # 章节标题由 build_candidate.py 直接断言（slice 必须以它开头），不在引文表里重复登记。

    # ── 开篇：许七安与临安的感情线（叙述层） ──
    "t_xu_reads_signals": (7, "裱裱这种花信少女，时不时表露出的信赖、亲近，都在向他传达一个信息："),
    "t_biao_oblivious": (4, "所以她也许没意识到自己对这个小铜锣有了情愫。"),
    "t_biao_show": (55, "这是刻意在许七安面前展示美貌，可能她自己没意识到。"),

    # ── 太子 vs 许七安 ──
    "t_zi_deny": (9, "太子也是男人，所以许七安在他面前否认没有意义。"),
    "t_zi_cancel": (11, "听说父皇原本打算封你为长乐县子，但得知你复生后，又取消了？"),
    "t_xu_rank": (12, "陛下答应我，只要找找查福妃的案子，我封爵指日可待。"),
    "t_zi_ask": (10, "“太子觉得呢？”许七安反问。"),
    "t_zi_offer": (13, "你若是能还本宫一个清白，本宫可以帮你再往上抬一抬。"),
    "t_zi_offer2": (13, "有些事，子爵是不够的。"),
    "t_xu_mock": (14, "殿下不如直接赏我黄金千两，也比画大饼要实在。"),
    "t_zi_press": (15, "太子眉梢一挑：“你不信本宫？”"),
    "t_xu_refuse": (16, "不是不信，而是太子能给我的，魏公也能给我。太子给不了我的，魏公依然能给我。"),
    "t_zi_warn": (17, "许七安，魏渊是孤臣，纵观史书，哪个孤臣有好下场？"),
    "t_xu_leave": (18, "许七安躬身作揖，离开了房间。"),

    # ── 许府：铃音逃学 ──
    "ling_excuse": (23, "“大锅不在，我就不走，我要大锅。”许铃音生气的说。"),
    "ling_ask2": (27, "“娘，那我留在家里跟二哥读书好不好。”许铃音娇声道。"),
    "shen_see_through": (24, "少给老娘来这套，你不就是想找个借口不去塾堂吗。"),
    "shen_see_through_narr": (25, "自己想了好久才想出来的办法，竟然被娘一眼就看穿了。"),
    "shen_refuse": (28, "“长的最丑，想的最美。”婶婶骂道：“你二哥马上要参加春闱了，哪有时间管你这个笨孩子。”"),
    "chunwei": (28, "你二哥马上要参加春闱了"),
    "ling_pouch": (22, "婶婶边回答，边给幼女脖子套上小布包。"),

    # ── 临安的红裙一段（情绪反转） ──
    "t_lian_pout": (57, "话音方落，裱裱脸色瞬间垮下来。"),
    "t_lian_pout2": (58, "“哼，狗奴才，你不是说本宫穿裙子特比漂亮吗？”"),
    "t_lian_flatter": (61, "“殿下实在太美，光辉万丈，闪瞎卑职的眼了。”许七安大声说。"),
    "t_lian_pleased": (62, "裱裱一听，转嗔为喜，许宁宴说话真好听，真有意思。"),
    "t_xu_knows": (5, "但许七安会不知道？"),

    # ── 许府：青橘 ──
    "juzi_enter": (35, "许二郎拎着一袋青橘进了府"),
    "juzi_give": (36, "“铃音，给你带塾堂去吃。”"),
    "juzi_take": (37, "许铃音开心的接过"),
    "juzi_taste": (37, "二哥，这个橘子不好吃的。"),
    "juzi_why": (39, "上次你爹买过这种青橘。"),
    "erlang_look": (40, "许新年深深的看了眼婶婶"),

    # ── 许府：二郎的谎 ──
    "lie_words": (42, "我昨天看到大哥给了爹五十两银子，您早点给收过来，免得他出去花天酒地。"),
    "lie_is_lie": (44, "其实许二郎是骗婶婶的"),
    "lie_goal": (44, "之所以这么说是为了让娘榨干爹的私房钱"),
    "lie_mech": (44, "为了安抚娘，爹咬紧牙关也会交出私房钱，这样就没法出去花天酒地了。"),
    "lie_resent": (45, "然后，讨厌的大哥会很长一段时间被娘记恨。"),
    "lie_perfect": (46, "一箭双雕，完美！"),
    "aunt_angry": (43, "婶婶一听，柳眉倒竖：“这个许宁宴，可恨。”"),
    "erlang_leave": (47, "许二郎满意的回书房读书去了。"),

    # ── 进宫 ──
    "enter_palace": (50, "手持令牌，一路畅通无阻的进了皇宫，来到韶音苑，接裱裱一起去破案。"),
    "xu_plan": (63, "“殿下，我今天准备去清风殿看一看。”许七安道。"),
    "lian_wait": (64, "临安点了点头，娇声道：“本宫要等一个人。”"),
    "lian_proud": (65, "她眉眼间有得意的神采，昂起下颌，露出雪白修长的脖颈。"),
    "xu_dread": (66, "许七安心里徒然一沉，心说不会吧不会吧，不会跟我想的一样吧。"),
    "huaiqing_arrive": (67, "也就一刻钟，穿着白色宫裙，清冷绝丽，行走间风情妙不可言的怀庆来了。"),
    "lian_claim": (69, "怀庆非要跟着我们主仆长长见识，本宫就做主满足她的需求"),
    "lian_owner": (70, "她特意把“主仆”两字咬的极重，似乎在宣示某人的所有权。"),
    "xu_inner_deny": (72, "我什么时候成你仆人了"),
    "xu_surface": (72, "他表面微笑道：“卑职都无所谓。”"),
    "hq_debt": (73, "怀庆公主清亮的眼波扫来，淡淡道：“那本宫就承许大人的情了。”"),
    "xu_embarrass": (81, "三家姓奴的许七安很尴尬，于是前往清风殿的路上，他沉默的坠在两位公主身后，一言不发，降低存在感。"),

    # ── 怀庆为何来 ──
    "hq_why_surprise": (75, "他没想到怀庆会参与福妃案，但转念一想，又觉得这是在所难免之事。"),
    "hq_interest": (76, "首先，怀庆对查案破案很有兴趣，只是身为千金之躯的公主，她以前没理由也没环境去接触。"),
    "hq_sangbo": (77, "桑泊案时，怀庆就常常召许七安入宫询问案件详情，还陪着他一起埋首史书，寻找线索。"),
    "hq_switch": (79, "先前主办机构是三司，怀庆插不上手，而今主审官变成了许七安，怀庆自然就来了。"),
    "hq_suspect": (79, "当然，许七安怀疑其中还有裱裱作妖的成分。"),
    "hq_boast": (80, "比如屁颠颠的跑到怀庆面前说：本宫的狗奴才回来了，狗奴才最听本宫的话"),

    # ── 小宦官 ──
    "eunuch_fetch": (83, "途中，让当值的侍卫去寻来了昨日的小宦官。"),
    "eunuch_change": (84, "小宦官态度转变极大，与怀庆临安恭敬行礼后，他又朝着许七安行礼"),
    "eunuch_sorry": (84, "许大人，昨日奴才有冲撞之处，请许大人莫要见怪。许大人的好意，奴才都记在心里的。"),
    "xu_puzzle": (85, "许七安一愣，心说我哪有的好意，你在说什么？"),
    "xu_hide": (86, "但他没有表露情绪，不动声色的“嗯”一声。"),

    # ── 清风殿：封锁与进入 ──
    "qd_arrive": (98, "很快，一行人抵达清风殿。"),
    "qd_sealed": (99, "清风殿已经被宫中侍卫封锁，宫女宦官被禁足在大院内。"),
    "qd_prestige": (100, "临安和怀庆两位公主的面子不管用，还是许七安亮出金牌，自报身份，侍卫才放行"),
    "qd_layout": (101, "所谓清风殿，其实是一座两进的宫苑，前院住着低等宫女和宦官，后院住着福妃娘娘的心腹。"),
    "qd_main": (102, "主殿是一座两层高的阁楼，飞檐斗角，气派恢弘。"),
    "qd_rail": (103, "二楼的眺望台，护栏断了一截，福妃想必就是从这里坠楼身亡的。"),
    "qd_height": (104, "许七安目测了一下高度，大概有个六七米，这种高度摔下来，基本看阎王爷收不收你。"),
    "qd_backhead": (105, "像福妃这样后脑勺着地的，可以解释成阎王爷觊觎她美色，召她下去陪伴，谁都救不了。"),
    "qd_main_sealed": (106, "主殿也被封闭了，四名侍卫守在门口，保护现场。"),
    # ── 现场勘验 ──
    "ask_where": (107, "“当时福妃是死在哪个位置？”许七安问侍卫小头目。"),
    "guard_point": (108, "小头目指着临安的落脚处，道：“福妃娘娘就摔在那个位置。”"),
    "lian_jump": (109, "裱裱像只敏捷的，受惊的兔子，“噌”一下蹦开。"),
    "ask_ever": (110, "许七安站在福妃尸体摔落的位置，抬头看了眼阁楼，收回目光，道：“阁楼从未有人进过？”"),
    "guard_sanfa": (111, "“三法司的人进去过。”"),
    "ask_take": (112, "“有没有拿走，或破坏过什么？”"),
    "guard_keep": (113, "没有，卑职一直在旁盯着。断裂的护栏也被保留库房里，没有被三法司的人带走。"),
    "narr_watch": (114, "有人在旁监督......现场证物不允许带走"),
    "narr_yuanjing": (114, "元景帝不愧是权术高手，直接杜绝太子党帮太子“善后”的可能性。"),
    "xu_open": (115, "许七安道：“开门，本官要上来。”"),
    "xu_upstairs": (116, "进了阁楼，拾阶而上，来到二楼。"),
    "search_pair": (117, "许七安和怀庆公主目光锐利，仔细的扫视现场每一处角落。"),
    "lian_pretend": (117, "裱裱看了两人一眼，也装模作样的摆出“认真搜索”的姿态。"),
    "scene_items": (118, "首先被他们注意到的，是桌边倾翻的圆凳；桌上一杯早已冰凉的茶；凌乱的床榻；被撕下一角的床幔；东侧墙壁脱落的字画"),

    # ── 嗅探 ──
    "xu_sniff": (119, "许七安抽动鼻子，四处乱嗅。"),
    "lian_ask_smell": (120, "“你在闻什么？”裱裱装不下去了。"),
    "xu_dna_joke": (121, "“别吵，我在闻脱氧核糖核酸的味道。”"),
    "lian_puzzled": (122, "“脱什么酸？”裱裱懵了。"),
    "narr_real_aim": (123, "其实他只是闻一闻空气里会不会有残留着某种气味，并不一定是脱氧核糖，毕竟过去这么多天，气味不可能保留下来。"),
    "narr_still_do": (124, "但该做的甄别还是要做。"),
    "hq_ask_dna": (125, "“脱氧核糖是什么？”怀庆主动问道。"),
    "narr_scholar": (126, "来自一个女学霸本能的知识欲求。"),
    "xu_inner_joke": (127, "是咱们的子孙......许七安心里口嗨了一句"),
    "ask_bed": (127, "指着卧室的床榻，问小头目：“床榻就是这么乱的？”"),
    "guard_bed": (128, "有被三法司的人翻找过，不过，他们第一次来时，也是乱的。"),
    "xu_no_dna": (129, "可惜验不了DNA，不然直接可以破案了"),

    # ── 侧写 ──
    "profile_sit": (130, "检查完护栏的断口，许七安便在瞭望厅盘坐下来，闭着眼，强大的精神力让他的侧写能力暴涨。"),
    "profile_from": (131, "根据目前的现场细节反馈，他在脑海里勾勒出动态的图像："),
    "profile_1": (132, "太子醉醺醺的登楼，福妃在桌边倒了被热茶，帮他解酒，但太子没去碰茶杯，而是碰了福妃的小手，或者其他地方，导致福妃大惊失色，撞翻了凳子。"),
    "profile_2": (133, "然后太子霸王硬上弓，拉拽着福妃到床榻，激烈颤抖中，床榻一片混乱，一角床幔被撕下。"),
    "profile_3": (134, "太子一见情况不妙，恶向胆边生，将福妃推下瞭望厅。接着，来到外室昏睡，假装自己什么都没干。"),
    "xu_eyes_open": (135, "许七安睁开眼，吐出一口气。"),
    "both_ask": (136, "始终关注着他的怀庆和临安，立刻开口道：“有什么发现？”"),
    "xu_conclude": (137, "“案子其实也不难，但有几点我要先做确认。”许七安道。"),

    # ── 作者附言（非叙事层） ──
    "ps_sep": (138, "------------"),
    "ps_head": (139, "重要通告！"),
    "ps_delay": (140, "今天两章在晚上，上午的没写出来。"),
    "ps_reason": (141, "倒不是我卡文，而是我要捋一捋案件的脉络，以及推敲细节。"),
    "ps_craft": (144, "但写案子是一个逆推的过程，我要先想好结尾，然后逆推整个查案过程，哪几章要埋伏笔，哪几章要做铺垫，都是得一口气想明白，想清楚了，才能动笔。"),
    "ps_long": (145, "而写案子，我可能要先想好后续十几章的内容，是没办法当天写，当天想的。"),
    "ps_sangbo": (147, "就好比桑泊案，都是提前做好细纲的，不然做不到小案子之间的环环相扣。"),
    "ps_promise": (148, "不过更新会迟到，但不会缺席。"),
    "ps_vote": (149, "月票别忘了哦，嘤嘤嘤嘤嘤。"),

    # ── 被排除段落的取样引文（用于 excludedSettings / unknowns 定位） ──
    "t_compare_block": (88, "临安的屁股没有怀庆大"),
    "t_hq_xiuwei": (94, "怀庆有修为在身"),
    "t_scene_section_break": (19, ".........."),
    "t_scene_marker_xufu": (20, "许府。"),
    "t_scene_marker_palace": (49, "皇宫。"),
    "t_lian_excited": (51, "她开心的蹦跳过来，鹅蛋脸扬起甜美的笑容，桃花眸里洋溢着明媚的风情。"),
    "t_lian_red": (51, "临安公主今天穿着火红色的宫装，颜色如昨天一致，但款式不同。"),
    "t_lian_ask_red": (56, "许七安纳闷道：“你怎么老穿红色的裙子"),
    "t_lian_scared": (60, "裱裱关切道：“怎么啦？”"),
    "t_xu_fake_scream": (59, "许七安忽然捂住眼睛，惨叫起来。"),
    "t_xu_speechless": (68, "许七安：“......”"),
    "t_xu_roar": (71, "许七安在心里怒吼道：我觉得很淦！"),
    "t_xu_two_boats": (82, "我总有一天会因为脚踏两只船而劈叉，扯到蛋"),
    "t_ling_baozi": (21, "“大锅呢，大锅怎么又不见了。”许铃音嘴里塞着肉包，左顾右盼。"),
    "t_ling_whine": (34, "“许铃音你要气死我吗。”婶婶被气的嗷嗷叫。"),
    "t_ling_quiz": (29, "“春闱是什么啊。”"),
    "t_erlang_ask_eat": (38, "许二郎一愣：“你吃过？”"),
    "t_aunt_urge": (41, "婶婶疑惑的看着他：“有事说事，吞吞吐吐的。”"),
    "t_two_girls_front": (87, "一行人朝着清风殿走去，两位公主行在最前头，白衣对红衣"),

    # ── 前期（区间外）用于判定知识差的对照，不进入任何引用 ──
}

# 人物话语（不是叙述事实）清单：值 = 引文名
SPEECH_KEYS = [
    "t_zi_ask", "t_zi_offer", "t_zi_offer2", "t_xu_mock", "t_zi_press", "t_xu_refuse",
    "t_zi_warn", "ling_excuse", "ling_ask2", "shen_see_through", "shen_refuse",
    "juzi_give", "juzi_taste", "juzi_why", "lie_words", "aunt_angry",
    "xu_plan", "lian_wait", "lian_claim", "xu_surface", "hq_debt",
    "eunuch_sorry", "ask_where", "guard_point", "ask_ever", "guard_sanfa",
    "ask_take", "guard_keep", "xu_open", "lian_ask_smell", "xu_dna_joke",
    "lian_puzzled", "hq_ask_dna", "ask_bed", "guard_bed", "both_ask", "xu_conclude",
    "t_zi_cancel", "t_xu_rank", "t_zi_deny", "t_lian_pout2", "hq_why_surprise",
]
SPEECH_NOTES = {
    "t_zi_offer": "太子的招揽条件，属话语层；他是否真能「往上抬一抬」在本区间无任何兑现动作。",
    "t_xu_refuse": "许七安对自身筹码的判断，属话语层；不构成对魏渊实力的叙述事实。",
    "t_xu_mock": "许七安把太子的许诺贬为「画大饼」，是他的评价而非叙述事实。",
    "t_zi_warn": "太子对孤臣下场的论断，属话语层；本区间无任何孤臣结局的叙述。",
    "lie_words": "**这句是谎话**：第 44 段叙述者明写「其实许二郎是骗婶婶的」。不得当作「大哥给过爹五十两」的事实。",
    "guard_point": "侍卫小头目的指认，属证人口供；本区间没有第三方核对。",
    "guard_keep": "侍卫小头目的口供（他一直盯着、证物未带走）；「三法司有没有拿走过什么」本区间只有他一人之言。",
    "guard_bed": "侍卫小头目的口供；且他回答的是许七安的引导性提问（「床榻就是这么乱的？」）。",
    "xu_conclude": "许七安自己的判断，属话语层；「案子其实也不难」不是已破案的结果。",
    "eunuch_sorry": "小宦官的话；「许大人的好意」所指何事在本区间没有解释（见 unknowns）。",
    "hq_why_surprise": "叙述句，但内容是许七安的心理活动（他没想到怀庆会参与）；「觉得这是在所难免」是他的判断，不是客观结论。",
    "narr_scholar": "叙述者对怀庆提问动机的点评（女学霸本能），属于叙述者评价，不是怀庆本人陈述的动机。",
}
# 叙述者评价（不是可核验事实）
NARRATOR_EVALUATION = [
    ("narr_yuanjing", "叙述者把「有人在旁监督、证物不许带走」的动机归给元景帝（「不愧是权术高手」），这是叙述者的评价与归因，不是本区间可核验的事实：没有任何元景帝下令的场景。"),
    ("qd_rail", "「福妃想必就是从这里坠楼身亡的」带「想必」，是推断语气，不是已确认结论。"),
    ("profile_from", "整段侧写（profile_1/2/3）是许七安的推断产物，**不是叙述事实**；本区间没有任何独立证据确认这条时间线。"),
    ("t_biao_show", "「这是刻意在许七安面前展示美貌，可能她自己没意识到」—— 前半句是叙述者的判断，后半句带「可能」，都不是临安的自述。"),
    ("narr_scholar", "「来自一个女学霸本能的知识欲求」是叙述者对怀庆提问动机的点评，不是怀庆本人说出的动机。"),
]

# ── 1. tasks[] ───────────────────────────────────────────────────────────
TASKS = [
    {
        "id": "t1_taizi_recruit",
        "who": "太子",
        "label": "太子以「还清白」为条件招揽许七安，换取爵位再抬一抬",
        "objective": {"text": "让许七安替他还一个清白（作为交换，他可以把许七安的爵位再往上抬）。", "basis": "explicit", "quotes": ["t_zi_offer", "t_zi_offer2"]},
        "obstacle": {"text": "许七安不信他的许诺，并当面指出太子能给的魏渊也能给 —— 招揽没有独家筹码。", "basis": "explicit", "quotes": ["t_xu_refuse"]},
        "action": {"text": "太子先以「子爵不够」加码，被哂笑后挑眉质问，再以孤臣下场施压。", "basis": "explicit", "quotes": ["t_zi_press", "t_zi_warn"]},
        "result": {"text": "许七安把许诺贬为画大饼、拒绝结盟后躬身离开；太子没有得到任何承诺。", "basis": "explicit", "quotes": ["t_xu_mock", "t_xu_leave"]},
        "cost": None,
        "costNote": "本区间没有出现太子为这次招揽付出任何代价的描写（无损失、无让步已执行、无资源支出）。他开出的条件全是**未兑现的许诺**，许诺不构成代价。",
        "speechDriven": True,
    },
    {
        "id": "t2_erlang_frame",
        "who": "许二郎（许新年）",
        "label": "许二郎编谎让娘去榨干爹的私房钱，并让大哥被娘记恨",
        "objective": {"text": "让娘把爹的私房钱收走（这样爹没法出去花天酒地），顺带让大哥被娘记恨 —— 他自己写明是一箭双雕。", "basis": "explicit", "quotes": ["lie_goal", "lie_resent"]},
        "obstacle": None,
        "obstacleNote": "本区间没有出现任何阻碍他实施这个谎的描写：没有第三方质疑、没有娘起疑、没有爹当场否认。第 44 段的机制句写的是他预期的爹的反应，不是实施中的阻力，所以不填。",
        "action": {"text": "他借「也不是什么大事」的口气，把一句编造的见闻说给娘听，诱导娘去收钱。", "basis": "explicit", "quotes": ["lie_words"]},
        "result": {"text": "娘当场动怒、骂大哥可恨；他本人满意地回书房读书。至于爹的私房钱有没有真被榨干，本区间没有写。", "basis": "explicit", "quotes": ["aunt_angry", "erlang_leave"]},
        "cost": None,
        "costNote": "本区间没有写许二郎为此付出任何代价（没有风险、没有损失、后文也没有反噬）。被损害的是不在场的大哥，他不是这条任务的执行者，所以不计入本条的 cost。",
        "actionIsFalseSpeech": True,
        "selfAssessment": {"text": "他把这套安排自我评价为「一箭双雕，完美！」。", "basis": "explicit", "quotes": ["lie_perfect"]},
    },
    {
        "id": "t3_lingyin_skip_school",
        "who": "许铃音",
        "label": "许铃音用「找大哥」当借口逃避去塾堂",
        "objective": {"text": "留在家里、不去塾堂 —— 她先以找大哥为由不走。", "basis": "explicit", "quotes": ["ling_excuse"]},
        "obstacle": {"text": "娘一眼看穿这是她找的借口。", "basis": "explicit", "quotes": ["shen_see_through", "shen_see_through_narr"]},
        "action": {"text": "第一个借口被拆穿后，她改口要求留在家里跟二哥读书。", "basis": "explicit", "quotes": ["ling_ask2"]},
        "result": {"text": "娘不但拒绝，还骂她「长的最丑，想的最美」，并给出理由：二哥要参加春闱，没时间管她。", "basis": "explicit", "quotes": ["shen_refuse"]},
        "cost": None,
        "costNote": "本区间没有写许铃音付出代价：被骂之后没有惩罚动作、没有后续处置，她的图谋落空本身不是代价。",
    },
    {
        "id": "t4_xu_survey_scene",
        "who": "许七安",
        "label": "许七安以主审官身份进入清风殿勘验现场",
        "objective": {"text": "去清风殿看一看（勘验现场）。", "basis": "explicit", "quotes": ["xu_plan"]},
        "obstacle": {"text": "清风殿已被宫中侍卫封锁，两位公主的面子不好使，通行需要凭证。", "basis": "explicit", "quotes": ["qd_sealed", "qd_prestige"]},
        "action": {"text": "他上楼进入主殿二层，与怀庆一起逐处扫视现场。", "basis": "explicit", "quotes": ["xu_upstairs", "search_pair"]},
        "result": {"text": "他取得了现场的一批物理细节：倾翻的圆凳、早已冰凉的茶、凌乱的床榻、被撕下一角的床幔、东侧墙壁脱落的字画。", "basis": "explicit", "quotes": ["scene_items"]},
        "cost": None,
        "costNote": "本区间没有写他为进现场付出代价：亮出的是本就持有的令牌/金牌，两位公主被拦不构成他的支出，也没有任何代价描写。",
    },
    {
        "id": "t8_xu_pursue_rank",
        "who": "许七安",
        "label": "许七安把查福妃案当作晋爵的路径",
        "objective": {"text": "查福妃案以求封爵 —— 他自述陛下答应过「只要找找查福妃的案子，我封爵指日可待」。", "basis": "explicit", "quotes": ["t_xu_rank"]},
        "obstacle": {"text": "原本要封的长乐县子因他复生而被取消（太子转述）；且太子当面指出子爵位置终究低了些。", "basis": "explicit", "quotes": ["t_zi_cancel"]},
        "action": {"text": "他在太子面前把自己的价码摆出来，反问「太子觉得呢？」，并拒绝接受太子的独家招揽。", "basis": "explicit", "quotes": ["t_zi_ask"]},
        "result": {"text": "本区间没有拿到任何爵位：只有一句许诺（封爵指日可待）与太子的口头加码，两样都没有兑现动作。", "basis": "explicit", "quotes": ["t_zi_offer"]},
        "cost": None,
        "costNote": "本区间没有写他为晋爵付出代价（没有已执行的交换、没有损失、没有让步），有的只是他自己转述的陛下许诺与太子的空头加码。",
        "speechDriven": True,
    },
    {
        "id": "t5_huaiqing_join",
        "who": "怀庆公主",
        "label": "怀庆公主介入福妃案的现场勘验",
        "objective": {"text": "接触查案破案 —— 她本来就对此很有兴趣，只是一直没有理由和环境。", "basis": "explicit", "quotes": ["hq_interest"]},
        "obstacle": {"text": "此前主办机构是三司，她插不上手。", "basis": "explicit", "quotes": ["hq_switch"]},
        "action": {"text": "她如约来到韶音苑与队伍会合，随后一起勘验现场。", "basis": "explicit", "quotes": ["huaiqing_arrive"]},
        "result": {"text": "她实际参与了现场搜索（与许七安一起逐处查看），并主动追问「脱氧核糖是什么」。", "basis": "explicit", "quotes": ["hq_ask_dna"]},
        "cost": None,
        "costNote": "本区间没有写怀庆为此付出代价；她说的「承许大人的情」是一句客气话，没有对应的支出动作。",
        "speechDriven": True,
    },
    {
        "id": "t6_eunuch_apology",
        "who": "昨日的小宦官",
        "label": "小宦官向许七安行礼赔罪，并声称记着他的好意",
        "objective": {"text": "为昨日的冲撞赔罪，并表明自己记得许七安的好意。", "basis": "explicit", "quotes": ["eunuch_sorry"]},
        "obstacle": None,
        "obstacleNote": "本区间没有写他赔罪遇到任何阻碍：没有人拦他、没有许七安拒见的动作。他先前冲撞过许七安是赔罪的缘由而不是阻碍，所以不填。",
        "action": {"text": "被侍卫寻来后，他与两位公主恭敬行礼，又单独向许七安行礼。", "basis": "explicit", "quotes": ["eunuch_change"]},
        "result": {"text": "许七安不动声色地应了一声「嗯」，没有追问也没有表露情绪 —— 赔罪被收下，但那句「好意」的所指始终没被澄清。", "basis": "explicit", "quotes": ["xu_hide"]},
        "cost": None,
        "costNote": "本区间没有写小宦官付出代价；赔罪本身不是代价，原文也没有任何处罚、损失或让步动作。",
    },
    {
        "id": "t9_xu_screen_smell",
        "who": "许七安",
        "label": "许七安在现场做气味甄别（明知大概率无用仍走完流程）",
        "objective": {"text": "闻一闻空气里会不会残留某种气味，做该做的甄别。", "basis": "explicit", "quotes": ["narr_real_aim", "narr_still_do"]},
        "obstacle": {"text": "已过去这么多天，气味不可能保留下来；本世上辈子的化验手段也用不上（验不了 DNA）。", "basis": "explicit", "quotes": ["xu_no_dna"]},
        "action": {"text": "他抽动鼻子四处乱嗅，并用一句现代术语「脱氧核糖核酸」把追问挡回去。", "basis": "explicit", "quotes": ["xu_sniff", "xu_dna_joke"]},
        "result": {"text": "本区间没有写他闻到任何东西：两位公主的追问（裱裱懵了、怀庆问「脱氧核糖是什么」）没有得到解释，他随后转去问床榻。", "basis": "explicit", "quotes": ["hq_ask_dna"]},
        "cost": None,
        "costNote": "本区间没有写这次甄别让他付出代价：没有体力/精神消耗的描写，也没有因白费功夫而受损；「精神力暴涨」另属侧写那条任务。",
        "resultIsEmpty": True,
    },
    {
        "id": "t7_xu_profile",
        "who": "许七安",
        "label": "许七安在瞭望厅以侧写还原案发经过",
        "objective": {"text": "把现场细节还原成一幅动态图像（谁做了什么、怎么发生的）。", "basis": "explicit", "quotes": ["profile_from"]},
        "obstacle": {"text": "他手上只有一批互不连贯的物证与口供，且此前的气味甄别已经失效；物证本身还是被三法司翻找过的现场。", "basis": "explicit", "quotes": ["guard_bed"]},
        "action": {"text": "他检查完护栏断口后在瞭望厅盘坐闭眼，靠精神力把侧写能力推起来。", "basis": "explicit", "quotes": ["profile_sit"]},
        "result": {"text": "他得到一条指向太子的完整经过（醉后登楼、动手、撕破床幔、福妃逃向瞭望厅、被推下、之后装睡），但这条经过是他自己的推断产物；他本人紧接着说还要先做几点确认。", "basis": "inferred", "quotes": ["profile_3", "xu_conclude"], "caution": "profile_3 是许七安的侧写内容，不是叙述事实；本条 result 记的是「他形成了一个推断」，不是「案情已查明」。"},
        "cost": None,
        "costNote": "本区间没有写他为这次侧写付出代价；「精神力暴涨」是能力描写，没有对应的消耗、损伤或代价句。",
    },
]

# ── 2. causeEdges[] ──────────────────────────────────────────────────────
CAUSE_EDGES = [
    {
        "id": "e1",
        "from": "许七安当面拒绝太子的招揽并把许诺贬为画大饼",
        "to": "太子改口质问并以「孤臣没有好下场」施压",
        "trigger": "招揽失去筹码后，太子换用威胁（先挑眉质问「你不信本宫？」，再沉声点魏渊的孤臣处境）。",
        "mechanism": "explicit",
        "quotes": ["t_xu_mock", "t_zi_press", "t_zi_warn"],
        "note": "对话内的真实因果链：拒绝 → 质问 → 施压，三句相邻但机制是「筹码失效改用恐吓」，不是靠相邻连边。",
    },
    {
        "id": "e2",
        "from": "许铃音用「找大哥」当借口不肯走",
        "to": "她的借口被娘当场拆穿、逃学图谋失败",
        "trigger": "娘直接点破她是在找不去塾堂的借口。",
        "mechanism": "explicit",
        "quotes": ["ling_excuse", "shen_see_through_narr"],
        "note": "原文用「竟然被娘一眼就看穿了」明确写了拆穿动作，因此是因果不是先后。",
    },
    {
        "id": "e3",
        "from": "许二郎编造「大哥给了爹五十两银子」",
        "to": "娘动怒并记恨大哥",
        "trigger": "娘听完当场柳眉倒竖、骂大哥可恨；这正是许二郎预期的「大哥被娘记恨」。",
        "mechanism": "explicit",
        "quotes": ["aunt_angry", "lie_resent"],
        "note": "方向是「谎话 → 娘的怒火」，不是「娘本来就在生气」。第 43 段写的是听话后的即时反应。",
    },
    {
        "id": "e4",
        "from": "福妃案的主审官从三司换成许七安",
        "to": "怀庆得以参与本案（她以前插不上手）",
        "trigger": "主办机构是三司时她插不上手；主审官变成许七安后她就来了。",
        "mechanism": "explicit",
        "quotes": ["hq_switch"],
        "note": "原文用「先前……而今……」的对照句写出通路变化，机制是「门禁式准入随主办方转移」。",
    },
    {
        "id": "e5",
        "from": "许七安亮出金牌并自报身份",
        "to": "侍卫放行、一行人得以进入清风殿",
        "trigger": "两位公主的面子都不管用，只有出示凭证才被放行。",
        "mechanism": "explicit",
        "quotes": ["qd_prestige"],
        "note": "「还是……才……」是否定式对照，表明没有凭证就进不去 —— 这是反事实机制，不是时间先后。",
    },
    {
        "id": "e6",
        "from": "元景帝安排的「有人监督 + 现场证物不允许带走」",
        "to": "三法司进过阁楼却没有拿走或破坏证物，断裂护栏仍留在库房",
        "trigger": "侍卫一直在一旁盯着，证物按规定不得带离。",
        "mechanism": "derived",
        "quotes": ["guard_keep", "narr_watch"],
        "note": "「没有拿走或破坏」是侍卫亲口所述（guard_keep）；把它归因到「元景帝的安排」是叙述者的推想（narr_yuanjing 明写「不愧是权术高手」），本区间没有元景帝下令的场景，所以整条标 derived 而不是 explicit。",
    },
    {
        "id": "e7",
        "from": "现场的物证组合（倾翻圆凳、冰凉茶、凌乱床榻、撕破床幔、脱落字画）",
        "to": "许七安在脑内还原出一条动态的案发经过",
        "trigger": "他依据这些现场细节反馈做侧写。",
        "mechanism": "explicit",
        "quotes": ["profile_from"],
        "note": "机制句「根据目前的现场细节反馈，他在脑海里勾勒出动态的图像」是原文直写；但产物是**推断**，见 e7 的 to 只写「还原出一条经过」而不写「查明真相」。",
    },
    {
        "id": "e8",
        "from": "许七安的强大精神力",
        "to": "他的侧写能力暴涨（得以完成这次还原）",
        "trigger": "他在瞭望厅盘坐闭眼、把精神力推起来，随后才勾出图像。",
        "mechanism": "explicit",
        "quotes": ["profile_sit"],
        "note": "原文用使役句「强大的精神力让他的侧写能力暴涨」，「让」就是机制标记。",
    },
    {
        "id": "e9",
        "from": "小宦官被侍卫寻来",
        "to": "小宦官当面向许七安赔罪、并说记着他的好意",
        "trigger": "许七安在途中主动让人去把昨日的小宦官找来。",
        "mechanism": "explicit",
        "quotes": ["eunuch_fetch"],
        "note": "「寻来了」与随后的行礼赔罪是同一因果链；注意这**不能**解释成「许七安料到他会道谢」。",
    },
]

# 被拒绝的因果边（登记比不登记有价值：说明我检查过这些诱人的连边）
REJECTED_EDGES = [
    {
        "id": "r1",
        "candidateEdge": "临安说「本宫要等一个人」→ 怀庆出现",
        "why": "这是**预告与应验**，不是致使：临安的话不会让怀庆来，怀庆也不是因为这句话才来。已改登记为伏笔 f1（铺设+回收俱在区间内）。",
        "quotes": ["lian_wait", "huaiqing_arrive"],
    },
    {
        "id": "r2",
        "candidateEdge": "小宦官态度转变 → 许七安明白了自己哪来的好意",
        "why": "与原文相反：许七安听完仍然不知道（xu_puzzle 明写「心说我哪有的好意，你在说什么？」），他只是不表露。态度转变的原因在本区间外（见 unknowns u2），本区间只有结果没有机制，不连边。",
        "quotes": ["xu_puzzle"],
    },
    {
        "id": "r3",
        "candidateEdge": "许七安问「阁楼从未有人进过？」→ 阁楼从未有人进过",
        "why": "把提问当成结论。侍卫的回答是「三法司的人进去过」，恰好否定了这个预设；许七安的提问不产生事实。",
        "quotes": ["ask_ever", "guard_sanfa"],
    },
    {
        "id": "r4",
        "candidateEdge": "太子醉醺醺登楼 → 福妃端茶解酒 → 太子动手 → 福妃坠楼",
        "why": "整条链条是许七安侧写出的**假设**，本区间没有任何独立证据或第三人证词确认。当作 causeEdge 就是把人物推断写成叙述事实。已改登记为 hypothesizedEdges（显式标 inferred），不放进 causeEdges。",
        "quotes": ["profile_1"],
    },
    {
        "id": "r5",
        "candidateEdge": "婶婶解释「上次你爹买过这种青橘」→ 许二郎决定诬陷大哥",
        "why": "只有「许新年深深的看了眼婶婶」这个动作紧接其后，原文没有写他因此起意。把相邻动作读成动机是编造动机。",
        "quotes": ["erlang_look"],
    },
    {
        "id": "r6",
        "candidateEdge": "元景帝是权术高手 → 太子确实有需要善后的隐情",
        "why": "把叙述者评价当事实，还替太子定了罪。叙述者只说这个安排杜绝了「帮太子善后的可能性」，没有说太子有罪；福妃案真相在本区间未定。",
        "quotes": ["narr_yuanjing"],
    },
    {
        "id": "r7",
        "candidateEdge": "清风殿被封锁 → 宫女宦官是凶手/知情者",
        "why": "封锁与禁足是现场管制措施（防串供、保现场），不指向任何人的嫌疑；原文没有一句把禁足与嫌疑挂钩。",
        "quotes": ["qd_sealed"],
    },
]

# 许七安侧写出的假设链：单列，绝不当事实
HYPOTHESIZED_EDGES = [
    {
        "id": "h1",
        "from": "太子醉醺醺登楼",
        "to": "福妃在桌边倒热茶替他解酒，茶杯却没被碰过",
        "mechanism": "inferred",
        "quotes": ["profile_1"],
        "status": "许七安侧写，未验证",
    },
    {
        "id": "h2",
        "from": "太子碰了福妃的手或别处",
        "to": "福妃大惊失色、撞翻圆凳",
        "mechanism": "inferred",
        "quotes": ["profile_1"],
        "status": "许七安侧写，未验证",
    },
    {
        "id": "h3",
        "from": "太子霸王硬上弓、拉拽到床榻",
        "to": "床榻一片混乱、一角床幔被撕下",
        "mechanism": "inferred",
        "quotes": ["profile_2"],
        "status": "许七安侧写，未验证",
    },
    {
        "id": "h4",
        "from": "福妃挣脱、冲向瞭望厅呼救、沿途碰落挂画",
        "to": "东侧墙壁的字画脱落",
        "mechanism": "inferred",
        "quotes": ["profile_2"],
        "status": "许七安侧写，未验证",
    },
    {
        "id": "h5",
        "from": "太子见情况不妙、恶向胆边生",
        "to": "福妃被推下瞭望厅，随后太子到外室装睡",
        "mechanism": "inferred",
        "quotes": ["profile_3"],
        "status": "许七安侧写，未验证；这是全案定性最关键也最缺旁证的一步",
    },
]

# ── 3. states[] ──────────────────────────────────────────────────────────
STATES = [
    {
        "id": "s1",
        "kind": "change",
        "who": "小宦官",
        "what": "对许七安的态度",
        "before": {"text": "昨日与许七安有过冲撞（他自称「昨日奴才有冲撞之处」）。", "basis": "explicit", "quotes": ["eunuch_sorry"]},
        "after": {"text": "恭敬行礼、当面赔罪，并声称把许七安的好意记在心里。", "basis": "explicit", "quotes": ["eunuch_change"]},
        "anchor": {"text": "途中被侍卫寻来、与两位公主及许七安见面的这一刻。", "basis": "explicit", "quotes": ["eunuch_fetch"]},
        "note": "前值只有他自己的话作依据（叙述者只说「态度转变极大」，没有直写前值），所以前值标 explicit 但注明是话语来源；转变的原因不在本区间。",
    },
    {
        "id": "s2",
        "kind": "change",
        "who": "婶婶",
        "what": "对大哥（许七安）的态度",
        "before": {"text": "本区间开场时她正在教训幼女，尚未提到大哥。", "basis": "explicit", "quotes": ["shen_see_through"]},
        "after": {"text": "柳眉倒竖、骂「这个许宁宴，可恨」，并将持续记恨他。", "basis": "explicit", "quotes": ["aunt_angry", "lie_resent"]},
        "anchor": {"text": "许二郎把那句编造的见闻说完之后。", "basis": "explicit", "quotes": ["lie_words"]},
        "note": "这条变化的触发是一句**谎话**；「许七安给过爹五十两」本身不是事实。",
    },
    {
        "id": "s3",
        "kind": "change",
        "who": "临安公主（裱裱）",
        "what": "情绪：被问到为何老穿红裙时的不快",
        "before": {"text": "脸色瞬间垮下来，并质问许七安不是说过她穿裙子漂亮。", "basis": "explicit", "quotes": ["t_lian_pout", "t_lian_pout2"]},
        "after": {"text": "转嗔为喜，心里觉得许宁宴说话真好听、真有意思。", "basis": "explicit", "quotes": ["t_lian_pleased"]},
        "anchor": {"text": "许七安捂住眼睛惨叫、说「殿下实在太美，光辉万丈，闪瞎卑职的眼了」。", "basis": "explicit", "quotes": ["t_lian_flatter"]},
    },
    {
        "id": "s10",
        "kind": "change",
        "who": "许七安",
        "what": "对临安「要等一个人」的预感",
        "before": {"text": "听到临安说要等一个人，心里徒然一沉，预感与自己所想相同。", "basis": "explicit", "quotes": ["xu_dread"]},
        "after": {"text": "预感被证实：来的是怀庆，他当场无语，随后在两人之间陷入尴尬。", "basis": "explicit", "quotes": ["huaiqing_arrive"]},
        "anchor": {"text": "临安说要等一个人、并露出得意的神色之后。", "basis": "explicit", "quotes": ["lian_proud"]},
        "note": "这条变化是**预感 → 证实**，不是因果：许七安的预感没有让怀庆来。它之所以值得记，是因为它证明 f1 是被当作悬念写的（当事人当场就绷紧了）。",
    },
    {
        "id": "s4",
        "kind": "change",
        "who": "临安公主",
        "what": "站位：从案发现场中心挪开",
        "before": {"text": "她站在福妃尸体摔落的位置上而不知情。", "basis": "explicit", "quotes": ["guard_point"]},
        "after": {"text": "像受惊的兔子一样噌地蹦开。", "basis": "explicit", "quotes": ["lian_jump"]},
        "anchor": {"text": "侍卫小头目指着她的落脚处说「福妃娘娘就摔在那个位置」。", "basis": "explicit", "quotes": ["guard_point"]},
        "note": "anchor 与 before 共用同一句引文（这是同一动作的两面：指认即站位事实的来源），已在 crossSectionQuoteReuse 中披露。",
    },
    {
        "id": "s5",
        "kind": "change",
        "who": "许七安",
        "what": "对福妃案的认识状态",
        "before": {"text": "手上只有一批互不连贯的现场物证（圆凳、凉茶、床榻、床幔、字画）。", "basis": "explicit", "quotes": ["scene_items"]},
        "after": {"text": "脑内形成一条完整的动态经过，同时明确「有几点我要先做确认」——即结论尚未确认。", "basis": "explicit", "quotes": ["xu_conclude"]},
        "anchor": {"text": "他在瞭望厅盘坐闭眼、精神力推起侧写，睁开眼吐出一口气。", "basis": "explicit", "quotes": ["xu_eyes_open"]},
        "note": "后值写的是「他形成了推断」，不是「案情查明」；后值的引文 itself 就带「要先做确认」。",
    },
    {
        "id": "s6",
        "kind": "change",
        "who": "怀庆公主",
        "what": "对福妃案的参与权限",
        "before": {"text": "主办机构是三司，她插不上手，以前没有理由和环境接触查案。", "basis": "explicit", "quotes": ["hq_interest"]},
        "after": {"text": "进入清风殿主殿二层，与许七安一起逐处扫视现场。", "basis": "explicit", "quotes": ["search_pair"]},
        "anchor": {"text": "主审官由三司变为许七安。", "basis": "explicit", "quotes": ["hq_switch"]},
    },
    {
        "id": "s7",
        "kind": "change",
        "who": "许七安",
        "what": "在两位公主之间的处境（外在定位）",
        "before": {"text": "被临安当众用「主仆」框定，并被咬重这两个字宣示所有权。", "basis": "explicit", "quotes": ["lian_owner"]},
        "after": {"text": "自称「三家姓奴」而感到尴尬，只能沉默地坠在两人身后降低存在感；表面上仍答「卑职都无所谓」。", "basis": "explicit", "quotes": ["xu_embarrass"]},
        "anchor": {"text": "怀庆到场、临安当场宣布「本宫就做主满足她的需求」。", "basis": "explicit", "quotes": ["lian_claim"]},
        "note": "内在与外在相反：他表面顺从（xu_surface），心里否认（xu_inner_deny），这条记的是外在定位的变化。",
    },
    {
        "id": "k1",
        "kind": "knowledge_gap",
        "topic": "小宦官口中的「许大人的好意」到底指什么",
        "knownBy": {"who": "小宦官本人", "basis": "explicit", "quotes": ["eunuch_sorry"]},
        "unknownTo": {"who": "许七安", "basis": "explicit", "quotes": ["xu_puzzle"]},
        "note": "许七安当场自问「我哪有的好意，你在说什么？」，也没有追问。解释这件事的场景不在本区间内（见 unknowns u2），所以本区间内这是一个双方信息不对等的悬置点。",
    },
    {
        "id": "k2",
        "kind": "knowledge_gap",
        "topic": "临安公主自己对许七安的情愫",
        "knownBy": {"who": "许七安", "basis": "explicit", "quotes": ["t_xu_knows"]},
        "unknownTo": {"who": "临安公主（叙述者用「也许」保留）", "basis": "inferred", "quotes": ["t_biao_oblivious"]},
        "note": "这是本区间唯一一处明确写出「谁知／谁不知」的感情线知识差。**必须保留原文的「也许」**：叙述者说的是「她也许没意识到」，不是断定她不知道；旁证是她刻意展示美貌「可能她自己没意识到」（同为「可能」语气）。",
    },
    {
        "id": "k6",
        "kind": "knowledge_gap",
        "topic": "怀庆为何值得为福妃案跑一趟",
        "knownBy": {"who": "许七安（他给出一套解释，但自己也知道其中含猜测）", "basis": "explicit", "quotes": ["hq_switch", "hq_suspect"]},
        "unknownTo": {"who": "怀庆本人（本区间没有给她一句解释动机的话，她只说了「承许大人的情」）", "basis": "explicit", "quotes": ["hq_debt"]},
        "note": "这一条不是「没人知道」，而是**解释权只在许七安手里**：他的解释由「怀庆对查案有兴趣 + 主审官换成他 + 怀疑裱裱作妖」三层组成，前两层有前情支撑，第三层他自己用的是「怀疑」和「比如」的假想语气。对话方从未确认过。",
    },
    {
        "id": "k3",
        "kind": "knowledge_gap",
        "topic": "福妃案的真实经过",
        "knownBy": {"who": "无人（许七安只持有未经确认的侧写）", "basis": "explicit", "quotes": ["xu_conclude"]},
        "unknownTo": {"who": "怀庆与临安（她们只能问「有什么发现？」）", "basis": "explicit", "quotes": ["both_ask"]},
        "note": "knownBy 写「无人」是有依据的：许七安本人紧接着说还要先做几点确认，且本区间没有任何验证动作。",
    },
    {
        "id": "k4",
        "kind": "knowledge_gap",
        "topic": "太子是否真有需要「善后」的隐情",
        "knownBy": {"who": "（有依据的空集：本区间没有任何人明确知道或说过太子有罪）", "basis": "explicit", "quotes": ["narr_yuanjing"]},
        "unknownTo": {"who": "许七安（他手上只有侧写，还在等确认）", "basis": "explicit", "quotes": ["xu_conclude"]},
        "note": "knownBy 是**空**而不是「元景帝」：原文只写元景帝的安排杜绝了「帮太子善后的可能性」，这是一句关于防范的说法，不是「他知道太子有罪」。空集在这里是结论，不是缺数据（对照组：本文件其它 knowledge_gap 的 knownBy 都非空）。",
    },
    {
        "id": "s8",
        "kind": "change",
        "who": "许七安",
        "what": "在太子面前的处境（爵位预期）",
        "before": {"text": "原本要被封为长乐县子（太子转述），但此事已被取消、封爵尚未落地。", "basis": "explicit", "quotes": ["t_zi_cancel"]},
        "after": {"text": "把封爵的希望押在查清福妃案上（陛下答应过），并从太子那里得到一句口头加码 —— 爵位本身仍未到手。", "basis": "explicit", "quotes": ["t_xu_rank"]},
        "anchor": {"text": "他与太子在房内就爵位与结盟的一番问答。", "basis": "explicit", "quotes": ["t_zi_ask"]},
        "note": "前值来自太子的话、后值来自许七安自己的话，都不是叙述者的客观交代；本区间没有任何授爵或取消的正式场景。",
    },
    {
        "id": "s9",
        "kind": "change",
        "who": "临安公主",
        "what": "对「查案现场」的参与姿态",
        "before": {"text": "自认是带仆人去长长见识的主人（当众咬重「主仆」二字），并把怀庆说成非要跟来的一方。", "basis": "explicit", "quotes": ["lian_claim"]},
        "after": {"text": "在阁楼上看到许七安与怀庆认真搜索后，也装模作样地摆出认真搜索的姿态 —— 参与停留在模仿层面。", "basis": "explicit", "quotes": ["lian_pretend"]},
        "anchor": {"text": "进了阁楼、许七安与怀庆开始逐处扫视之后。", "basis": "explicit", "quotes": ["search_pair"]},
        "note": "后值带明显的贬义描写（装模作样），这是叙述者的用词，我照录不改写；本区间也没有她实际发现任何线索的描写（见 unknowns u21）。",
    },
    {
        "id": "k5",
        "kind": "knowledge_gap",
        "topic": "「脱氧核糖核酸」是什么意思",
        "knownBy": {"who": "许七安（他自己说得出这个词，也自认在胡扯）", "basis": "explicit", "quotes": ["xu_inner_joke"]},
        "unknownTo": {"who": "临安公主与怀庆公主（一个懵了、一个认真追问）", "basis": "explicit", "quotes": ["hq_ask_dna"]},
        "note": "这是一处喜剧性的知识差：提问方是真心求知的（叙述者点明是女学霸本能的知识欲求），回答方却在心里把它转成荤话。全程没有人得到解释。",
    },
]

# ── 4. foreshadows[] ─────────────────────────────────────────────────────
FORESHADOWS = [
    {
        "id": "f1",
        "name": "「本宫要等一个人」→ 怀庆到场",
        "setup": {"text": "临安在韶音苑说有一个人要等，且眉眼得意、昂起下颌。", "basis": "explicit", "quotes": ["lian_wait", "lian_proud"]},
        "payoff": {"text": "约一刻钟后怀庆到场 —— 等的就是她。", "basis": "explicit", "quotes": ["huaiqing_arrive"]},
        "status": "resolved",
        "note": "严格意义上的铺设+回收都在本区间内：先有悬念（等谁、为什么得意），后有兑现（来的是怀庆）。许七安当场就有预感（xu_dread），进一步说明这是被当作悬念写的，不是普通叙述。",
    },
    {
        "id": "f2",
        "name": "小宦官的「好意」",
        "setup": {"text": "小宦官郑重赔罪并说许七安的好意他记在心里，而许七安完全不知道他指什么、也没有追问。", "basis": "explicit", "quotes": ["eunuch_sorry", "xu_puzzle"]},
        "payoff": None,
        "payoffNote": "本区间没有任何回收：许七安只回了一声「嗯」，没有澄清、没有追问，第 83–86 段之后再未出现这个小宦官。",
        "status": "unresolved",
        "note": "标 unresolved 是**显式**的：铺设（他郑重其事的感谢 + 主角的茫然）与未回收都在本区间可见。所指事件在上一章，不在本区间（见 unknowns u2）。",
    },
    {
        "id": "f3",
        "name": "「有几点我要先做确认」——侧写结论的验证",
        "setup": {"text": "许七安在脑内还原出完整经过（含推人下楼的定性），随即声明案件不难、但有几点要先做确认。", "basis": "explicit", "quotes": ["profile_from", "xu_conclude"]},
        "payoff": None,
        "payoffNote": "本区间在两位公主问「有什么发现？」之后就此收束，没有任何一条疑点被确认或推翻。",
        "status": "unresolved",
        "note": "铺设是双重的：一段具体的侧写（可被检验的断言）+ 一句「要先做确认」的明示。这两者合起来才构成伏笔，不是「只出现一次的东西」。",
    },
]

NOT_FORESHADOWS = [
    {"id": "nf1", "item": "断裂的护栏被保留在库房", "why": "本区间只出现一次，而且**当场就由叙述者解释了**（有人在旁监督、证物不许带走）。已被解释的安排不是未回收的伏笔；登记它才是「一次出现当伏笔」。已改记为世界设定 w_rule2 / 物件 i4。", "quotes": ["guard_keep"]},
    {"id": "nf2", "item": "太子「哪个孤臣有好下场」的警告", "why": "全区间只出现一次、且没有任何针对魏渊的后续动作。它把太子的敌意显性化，但没有铺设-回收结构，不构成伏笔。", "quotes": ["t_zi_warn"]},
    {"id": "nf3", "item": "青橘（许二郎带来、妹妹嫌不好吃）", "why": "只出现一次，且当场被娘用「上次你爹买过」解释掉。它的作用是给二郎的登场与说谎做台阶，没有回收。", "quotes": ["juzi_taste", "juzi_why"]},
    {"id": "nf4", "item": "「脱氧核糖核酸」这个现代词", "why": "是许七安单方面的口嗨（叙述者当场说明他真正只是在闻气味），两位公主听不懂。它只出现一次、且在段内被解释，不是伏笔。", "quotes": ["xu_dna_joke", "narr_real_aim"]},
    {"id": "nf5", "item": "福妃「后脑勺着地」", "why": "只出现一次，是叙述者对死状/高度的补充说明，没有铺设-回收结构。若把它当伏笔等于给死因预设立场。", "quotes": ["qd_backhead"]},
]

# ── 4b. worldSettings[] ──────────────────────────────────────────────────
WORLD_SETTINGS = [
    # ── 规则 ──
    {
        "id": "w_rule1", "kind": "rule", "name": "案发宫苑封锁与人员禁足",
        "institution": "executed",
        "quote": "qd_sealed",
        "explain": "清风殿已被宫中侍卫封锁、宫女宦官被禁足在大院内。它直接解释了人物能做什么、不能做什么：外人进不去（要凭证）、院内人被限制在原地（不能串供或离场）。是有执行动作的现场管制，不是一句泛泛的宫规。",
    },
    {
        "id": "w_rule2", "kind": "rule", "name": "现场证物不许带离、须有人在场监督",
        "institution": "executed",
        "quote": "narr_watch",
        "explain": "它解释了勘验时能查到什么：三法司进过阁楼却没有带走或破坏证物，断裂护栏因此还留在库房。这条约束同时决定了几名当事人（三法司、太子党）不能做什么 —— 灭证与「善后」被这一步挡住。",
    },
    {
        "id": "w_rule3", "kind": "rule", "name": "皇宫通行凭令牌、放行由侍卫裁量",
        "institution": "executed",
        "quote": "qd_prestige",
        "explain": "许七安持令牌一路畅通进皇宫；到了被封锁的清风殿，两位公主的身份不好使，只有亮出金牌、自报身份才被放行。它解释了「谁进得去」这个行动前提，也解释了公主的尊位在本案现场并不构成通行权。",
    },
    {
        "id": "w_rule4", "kind": "rule", "name": "福妃案主审权已由三司转到许七安",
        "institution": "executed",
        "quote": "hq_switch",
        "explain": "主审官易人直接改变了怀庆能不能参与：先前主办机构是三司时她插不上手，主审官变成许七安后她就来了。这条设定决定的是「参与权限」，不是一句官制名词。",
        "speechOrNarration": "叙述句（非对白）",
    },
    {
        "id": "w_rule5", "kind": "rule", "name": "春闱在即，考生没有余暇",
        "institution": "executed",
        "quote": "chunwei",
        "explain": "它解释了二哥为什么不能接铃音「留在家里跟二哥读书」的请求 —— 春闱将临，他无暇管她。这是对人物可支配时间的实际约束。证据是婶婶的一句话（话语层），不是叙述句，所以只记「约束存在」，不替春闱补任何制度细节。",
        "speechOrNarration": "对白（婶婶的话）",
    },
    # ── 地点 ──
    {
        "id": "w_place1", "kind": "place", "name": "清风殿（两进宫苑）",
        "placeState": "arrived",
        "quote": "qd_arrive",
        "explain": "一行人抵达清风殿。它是本案现场所在：前院住低等宫女宦官、后院住福妃的心腹，主殿是两层阁楼。有明确到达动作，记 arrived。",
    },
    {
        "id": "w_place2", "kind": "place", "name": "清风殿主殿二层（瞭望台／瞭望厅）",
        "placeState": "arrived",
        "quote": "xu_upstairs",
        "explain": "许七安要开门上去，进了阁楼拾阶而上来到了二楼，随后在瞭望厅盘坐侧写。原文对同一处先叫「二楼的眺望台」、后叫「瞭望厅」，两者共指同一处（护栏断口即在此），所以合并为一条而不拆成两处到达。",
    },
    {
        "id": "w_place3", "kind": "place", "name": "皇宫",
        "placeState": "arrived",
        "quote": "enter_palace",
        "explain": "许七安持令牌进了皇宫。它是本单元后半段的行动舞台，也是「持令牌畅通」这条规则的落点。",
    },
    {
        "id": "w_place4", "kind": "place", "name": "韶音苑",
        "placeState": "arrived",
        "quote": "enter_palace",
        "explain": "许七安到韶音苑接临安同行，怀庆也到此会合。有到达动作，记 arrived。与 w_place3 同句，已披露复用。",
    },
    {
        "id": "w_place5", "kind": "place", "name": "许府",
        "placeState": "arrived",
        "quote": "juzi_enter",
        "explain": "许府是前半段的场景，许二郎拎着一袋青橘进了府 —— 有明确的进入动作，所以记 arrived 而不是仅提及。",
    },
    {
        "id": "w_place6", "kind": "place", "name": "库房（存放断裂护栏处）",
        "placeState": "mentioned",
        "quote": "guard_keep",
        "explain": "只在侍卫口供里被提到：断裂护栏保留在库房、没被三法司带走。本区间没有任何人前往或驻守库房，所以只能记 mentioned —— 把它写成 arrived 就是把提及当到达。",
    },
    {
        "id": "w_place7", "kind": "place", "name": "桑泊",
        "placeState": "mentioned",
        "quote": "hq_sangbo",
        "explain": "只在回顾旧案时出现（桑泊案时怀庆常召许七安入宫问案）。本区间无人前往，是纯粹的提及，记 mentioned。",
    },
    # ── 物件 ──
    {
        "id": "w_item1", "kind": "item", "name": "令牌／金牌（许七安的通行凭证）",
        "itemStates": ["hold", "use"],
        "quote": "enter_palace",
        "stateEvidence": [
            {"state": "hold", "quote": "enter_palace", "note": "「手持令牌」—— 持有态由原文的「手持」直写。"},
            {"state": "use", "quote": "qd_prestige", "note": "「亮出金牌，自报身份，侍卫才放行」—— 这是使用态：出示以换取通行。"},
        ],
        "explain": "同一个通行凭证在原文里一处叫「令牌」、一处叫「金牌」；我把两处并入同一条物件并在此说明，而不是硬拆成两件或悄悄合并。四态只用到 hold 与 use，没有 transfer（没有赠予/被夺）也没有 lose（没有丢失）。",
    },
    {
        "id": "w_item2", "kind": "item", "name": "小布包",
        "itemStates": ["transfer"],
        "quote": "ling_pouch",
        "stateEvidence": [
            {"state": "transfer", "quote": "ling_pouch", "note": "「边回答，边给幼女脖子套上小布包」—— 由婶婶转给幼女并当场佩戴，照原文写「套上」，没有改写成「交给」。"},
        ],
        "explain": "只出现一次、只有转移态：婶婶给幼女脖子套上。没有持有者之外的获得/献与/夺，所以 itemStates 只有 transfer。",
    },
    {
        "id": "w_item3", "kind": "item", "name": "一袋青橘",
        "itemStates": ["hold", "transfer"],
        "quote": "juzi_enter",
        "stateEvidence": [
            {"state": "hold", "quote": "juzi_enter", "note": "「许二郎拎着一袋青橘进了府」—— 拎着即持有。"},
            {"state": "transfer", "quote": "juzi_take", "note": "「许铃音开心的接过」—— 从二哥转到妹妹手里。"},
        ],
        "explain": "四态里只有 hold 与 transfer：原文没有写青橘被吃掉（use）、也没有写被丢弃或被夺（lose）。妹妹那句「这个橘子不好吃的」是评价，不等于使用。",
    },
    {
        "id": "w_item4", "kind": "item", "name": "断裂的护栏",
        "itemStates": ["lose", "hold"],
        "quote": "qd_rail",
        "stateEvidence": [
            {"state": "lose", "quote": "qd_rail", "note": "「护栏断了一截」—— 护栏失去完整/脱离原位，照原文写「断了」，不改写成「损毁」。"},
            {"state": "hold", "quote": "guard_keep", "note": "「断裂的护栏也被保留库房里」—— 断件被留存入库，处于被保管的持有态。"},
        ],
        "explain": "这是本区间唯一同时具备「失去」与「被保管持有」两态的物件，两态分开写、不合成一条物品链。要注意「保留」的主语在原文里没有点明（被动式），所以只记「被保管」，不替它指定保管人。",
    },
]

PLACES_NOTE = (
    "地点 7 条：arrived 5（清风殿、主殿二层／瞭望厅、皇宫、韶音苑、许府）／mentioned 2（库房、桑泊）。"
    "三条区分写进字段而没有留给读者：(1) 库房与桑泊**只出现在谈话或回顾里**，本区间无人到达，所以是 mentioned —— "
    "反过来，如果我把「断裂护栏保留库房」写成到达，那就是计划点名的「提及≠到达」混淆；"
    "(2) 主殿二层与瞭望厅在原文里先叫「眺望台」后叫「瞭望厅」，护栏断口把两者钉成同一处，因此合并为一条到达，"
    "不把同一个动作登记两次；(3) 清风殿（整座宫苑）与主殿二层（院内建筑）是包含关系，我保留为两条但在此说明包含关系，避免被读成两个并列地点。"
)
ITEMS_NOTE = (
    "物件 4 条，四态分开写、每条态各自带 stateEvidence，没有任何一条被合成「物品链」："
    "hold 3（令牌、青橘、断裂护栏）／transfer 2（小布包、青橘）／use 1（令牌）／lose 1（断裂护栏）。"
    "原文用词照抄不改写：手持／亮出／给幼女脖子套上／拎着／接过／断了一截／保留库房里。"
    "**没有为了凑四态而造条目**：lose 只有护栏一处，transfer 只有小布包与青橘两处。"
    "另外把「桌上一杯早已冰凉的茶」「凌乱的床榻」「被撕下一角的床幔」「东侧墙壁脱落的字画」排除在物件之外（见 excludedSettings x2）——"
    "它们是无人称的现场物证，若硬套四态就等于替它们编一个持有者。"
)
RULES_NOTE = (
    "规则 5 条，全部 institution=executed：封锁禁足、证物不许带离且有监督、通行凭证、主审权转移、春闱在即。"
    "**declared 0 条**：本区间没有任何诏、令、法的文本或宣示动作 —— 元景帝的安排只以「有人在旁监督、证物不允许带走」的实际效果出现，"
    "没有一句圣旨或律条被引用，所以我不给它补一个 declared。"
    "**misunderstood 0 条**：本区间的人物理解（小宦官以为许七安对他有恩、婶婶以为大哥给了爹银子）都是对**具体人事**的误解，不是对某条规则的理解，"
    "套 institution=misunderstood 会把它降格成术语装饰（见 excludedSettings x4、x6）。"
    "两条规则的证据来自对白而非叙述句（主审权转移、春闱），已在各自条目的 speechOrNarration 字段写明。"
)

EXCLUDED_SETTINGS = [
    {"id": "x1", "item": "「脱氧核糖核酸／DNA」这套上辈子的知识", "why": "在本区间它**没有产生任何作用**：许七安自己说明他只是在闻气味，而且承认气味早就不可能保留；这世上也没有化验手段（验不了 DNA）。没有影响行动、资源、约束或后果 ⇒ 不登记为世界规则。它作为人物口嗨与主题素材保留在别处。", "quotes": ["xu_dna_joke", "xu_no_dna"]},
    {"id": "x2", "item": "桌上一杯早已冰凉的茶；凌乱的床榻；被撕下一角的床幔；东侧墙壁脱落的字画；桌边倾翻的圆凳", "why": "这些是**无人称的现场物证**（损坏/凌乱状态），原文没有给它们持有者，也没有获得、转移、献与、被夺的动作。四态无法成立，硬登记就是替物证编一个归属 ⇒ 排除；它们已作为物证进入 t4.result 与 h1–h4。", "quotes": ["scene_items"]},
    {"id": "x3", "item": "「精神力／侧写能力」的能力体系", "why": "原文只写「强大的精神力让他的侧写能力暴涨」，没有给这个能力的来源、上限、消耗或代价。除了这一次侧写，本区间没有任何地方用它约束人物行动 ⇒ 只作为 e8 的因果机制登记，不扩出一条术语装饰层。", "quotes": ["profile_sit"]},
    {"id": "x4", "item": "「主仆」这个称谓（临安主权宣示）", "why": "临安把「主仆」咬得极重是**她单方面的框定**：许七安心里否认（我什么时候成你仆人了），怀庆那边又是另一套说法（承许大人的情）。它既非诏令亦无执行动作，是对人际关系的宣称而不是制度 ⇒ 不登记为规则，改记入状态 s7。", "quotes": ["lian_owner", "xu_inner_deny"]},
    {"id": "x5", "item": "「花信少女」这类年龄/外貌评语", "why": "是叙述者的评价性用语，不影响任何行动、资源、约束或后果 ⇒ 排除。", "quotes": ["t_biao_oblivious"]},
    {"id": "x6", "item": "婶婶相信「大哥给了爹五十两」", "why": "这是被谎话造成的**事实性误解**，不是对某条规则的理解，所以不进 institution=misunderstood；它已经作为状态 s2 的触发与 causeEdge e3 登记。", "quotes": ["lie_is_lie"]},
    {"id": "x7", "item": "「姐妹花」外貌比较那一整段（臀型、身高、腰、扭动幅度等约 11 段）", "why": "这是**叙述者的主观品评**（多为许七安的视角），不产生任何行动、资源、约束或后果，因此不登记为世界设定或物件。它是一个真实的文本事实（占了本区间相当篇幅），我以 narratorEvaluation 条目与 unknowns 处置，而不是替它编一条设定。", "quotes": ["t_compare_block"]},
    {"id": "x8", "item": "「怀庆有修为在身」", "why": "这是一条能力信息，但**在本区间没有约束任何行动**：没有任何打斗、施法、或凭修为达成/受阻的事件，它只被用来说明她的体态。按「没有依据就不扩出术语装饰层」，我不把它升级成规则；作为能力线索登记在此，供后续区间接手。", "quotes": ["t_hq_xiuwei"]},
]

WORLD_SETTINGS_NOTE = RULES_NOTE + " 地点与物件另见 placesNote / itemsNote；被排除项见 excludedSettings（6 条，逐条写明理由）。"

# ── 4c. themeReadings[] ──────────────────────────────────────────────────
THEME_READINGS = [
    {
        "id": "th1",
        "perspective": "以许七安为轴，读「信息不对称」如何同时被他利用和被他承受：他握有别人没有的知识与推演力，却也在别人握有的信息面前完全被动。",
        "support": [
            {"text": "他靠一句现代术语把场面搅乱（裱裱懵了、怀庆追问「脱氧核糖是什么」），紧接着叙述者说明他真正做的只是闻气味、且气味早已不可能保留。", "quotes": ["xu_dna_joke", "lian_puzzled", "hq_ask_dna", "narr_real_aim"]},
            {"text": "他能从一批物证推出一条完整经过，却立刻声明还有几点要先做确认。", "quotes": ["profile_from", "xu_conclude"]},
            {"text": "这种不对等也发生在他自己身上：他确信裱裱对他有情愫，而对方「也许」还没意识到 —— 他读得懂别人，别人读不懂他。", "quotes": ["t_xu_reads_signals", "t_biao_oblivious"]},
        ],
        "counter": [
            {"text": "同一个人在小宦官面前是完全不知情的一方：对方郑重道谢，他自问「我哪有的好意，你在说什么？」。", "quotes": ["eunuch_sorry", "xu_puzzle"]},
            {"text": "他对太子立场的判断也只是自己的话（「太子能给我的，魏公也能给我」），并非可核验的胜负结算。", "quotes": ["t_xu_refuse"]},
            {"text": "他在太子面前连否认的余地都没有 —— 叙述者直接写明「太子也是男人，所以许七安在他面前否认没有意义」。", "quotes": ["t_zi_deny"]},
        ],
        "basis": "inferred",
        "note": "这是解释层不是事实层。刻意**没有**用事件密度、剧情点数量、死亡人数或篇幅中点来定义所谓的「高潮」；本区间也没有三幕或英雄旅程结构可用。",
    },
    {
        "id": "th2",
        "perspective": "以「案发现场的证据秩序」为轴，读权力如何布置现场：谁进来、谁能碰证物、证物放在哪里，都是被安排过的。",
        "support": [
            {"text": "清风殿被封锁、宫女宦官禁足；两位公主的面子不好使，只有亮出金牌才被放行。", "quotes": ["qd_sealed", "qd_prestige"]},
            {"text": "证物不许带走、有人全程在旁盯着，断裂的护栏被保留入库。", "quotes": ["narr_watch", "guard_keep"]},
            {"text": "宫苑本身的格局也是被规定的：前院住低等宫女宦官、后院住福妃的心腹，主殿是两层阁楼。", "quotes": ["qd_layout", "qd_main"]},
        ],
        "counter": [
            {"text": "现场并不是未被触碰的：床榻被三法司翻找过（侍卫承认「有被三法司的人翻找过」）。", "quotes": ["guard_bed"]},
            {"text": "把这一切归因于元景帝的权术，是叙述者的评价（「不愧是权术高手」），本区间没有他下过任何命令的场景；把它当既定事实就是拿叙述者评价当证据。", "quotes": ["narr_yuanjing"]},
        ],
        "basis": "inferred",
        "note": "两个解释并存而非压成一条「唯一真相」：th1 关注个人的信息处境，th2 关注制度对现场的塑形；同一批事实（物证清单、封锁、监督）在两种读法里各有位置。",
    },
]

THEME_READINGS_NOTE = (
    "2 条主题解读，各带 perspective（以谁为轴）、support（逐字引文）、counter（不利或相反的证据），两条都标 basis=inferred —— "
    "这是解释层不是事实层。没有用事件密度、剧情点数量、死亡人数或篇幅中点来定义高潮，也没有强行套三幕或英雄旅程；"
    "同一批事实（现场物证、封锁与监督、许七安的推演）在两条读法里都能安放，所以并列写出而不压成一条唯一解释。"
)

# ── 5. unknowns[] ────────────────────────────────────────────────────────
UNKNOWNS = [
    {"id": "u1", "topic": "福妃究竟是怎么死的、是谁推的", "why": "本区间只有两条依据：叙述者的高度/着地描述（推断语气）与许七安自己的侧写。没有尸检、没有目击者、没有物证鉴定，许七安本人也说还有几点要先做确认。", "quotes": ["qd_rail", "xu_conclude"]},
    {"id": "u2", "topic": "小宦官口中的「好意」具体指哪件事", "why": "本区间只写他道谢与许七安的茫然，没有任何解释。解释这件事的场景在上一章（本区间之外），所以在本区间内我读不出来，也不替它编一个答案。", "quotes": ["eunuch_sorry", "xu_puzzle"]},
    {"id": "u3", "topic": "太子被要求「还一个清白」所指的具体指控", "why": "太子只说了条件，没说指控内容；本区间没有列出他具体被怀疑做了什么。", "quotes": ["t_zi_offer"]},
    {"id": "u4", "topic": "太子是否真的有罪", "why": "本区间没有任何独立证据；叙述者那句「杜绝太子党帮太子善后的可能性」是防范围的描述，不是定罪。许七安的侧写指认他，但那是推断。", "quotes": ["narr_yuanjing", "profile_3"]},
    {"id": "u5", "topic": "爹到底有没有私房钱、有没有真被榨干", "why": "起点就是许二郎编的谎（叙述者明写「其实许二郎是骗婶婶的」），后续在本区间没有写结果，只在第 44 段写了他的预期机制。", "quotes": ["lie_is_lie", "lie_mech"]},
    {"id": "u6", "topic": "许二郎为什么在听完青橘的解释后深深看了婶婶一眼", "why": "原文只给了一个动作，没有写他心里在想什么，也没有写这个眼神与随后那句谎的关系。我不替它补动机。", "quotes": ["erlang_look"]},
    {"id": "u7", "topic": "临安到底有没有意识到自己的情愫", "why": "叙述者用「也许没意识到」保留，且旁证也带「可能」。这是原文刻意不定的，不能替它定。", "quotes": ["t_biao_oblivious"]},
    {"id": "u8", "topic": "许七安对太子说的话有几分是真", "why": "「太子能给我的，魏公也能给我」是他当面的说辞，本区间没有他的内心对照，也没有魏渊一方的任何回应。", "quotes": ["t_xu_refuse"]},
    {"id": "u9", "topic": "三法司第一次进入时现场是什么状态", "why": "唯一来源是侍卫小头目的口供（「他们第一次来时，也是乱的」），且他回答的是许七安的引导性提问；没有第二方核对。", "quotes": ["guard_bed"]},
    {"id": "u10", "topic": "怀庆参与的真正动机", "why": "许七安给的解释本身带猜测成分（他「怀疑其中还有裱裱作妖的成分」），且「裱裱作妖」只是他举的假想例子（「比如屁颠颠的跑到怀庆面前说……」），没有场景落实。", "quotes": ["hq_suspect", "hq_boast"]},
    {"id": "u11", "topic": "令牌与金牌是不是同一件东西", "why": "同一段行程里先写「手持令牌」、后写「亮出金牌」，原文没有明说二者关系。我按同一凭证处理并在 w_item1 里写明这一处理，但这是我的判断，不是原文直述。", "quotes": ["enter_palace", "qd_prestige"]},
    {"id": "u12", "topic": "「瞭望台」与「瞭望厅」是不是同一处", "why": "原文先写「二楼的眺望台，护栏断了一截」，后写他「来到瞭望厅」「检查完护栏的断口」。护栏把两处钉在一起，但没有一句直说二者同名同地。", "quotes": ["qd_rail", "profile_sit"]},
    {"id": "u13", "topic": "断裂的护栏由谁保管", "why": "原文是被動式「被保留库房里」，没有点明保管人或机构；我不替它指定。", "quotes": ["guard_keep"]},
    {"id": "u14", "topic": "「断了一截」的护栏与坠楼之间的物理关系", "why": "原文只把两件事写在一起（护栏断了、福妃想必从这坠落），没有写护栏是被撞断还是本来就断、也没写与人坠落的先后。这不是因果，是并存，我不连边。", "quotes": ["qd_rail"]},
    {"id": "u15", "topic": "元景帝是否真的下令做了这些安排", "why": "原文只有叙述者的评价句（「不愧是权术高手，直接杜绝……」），没有任何诏令、口谕或执行场景。", "quotes": ["narr_yuanjing"]},
    {"id": "u16", "topic": "婶婶记恨大哥会持续多久、有没有后果", "why": "原文只说「会很长一段时间被娘记恨」，这是叙述者对许二郎预期的转述，本区间没有后续。", "quotes": ["lie_resent"]},
    {"id": "u17", "topic": "「花信少女」的具体年龄与它和别处设定的关系", "why": "叙述者用它形容裱裱，本区间没有给年龄数字，也没有与其他人物年龄的对照。", "quotes": ["t_biao_oblivious"]},
    {"id": "u18", "topic": "许七安检查护栏断口得到了什么结论", "why": "原文只写他「检查完护栏的断口」，没有写检查结果；紧接着就是盘坐侧写。检查动作与侧写结论之间的推理步骤被省略了。", "quotes": ["profile_sit"]},
    {"id": "u19", "topic": "末段的「重要通告」是否算正文", "why": "它明显是作者附言（谈更新与写案子的方法），不是叙事。我把它作为非叙事层单列处理、不从中提取任何剧情事实；但它出现在本区间内这件事本身是客观的。", "quotes": ["ps_head", "ps_vote"]},
    {"id": "u20", "topic": "「倒了被热茶」的词形", "why": "原文该处写作「倒了被热茶」，按上下文应是「倒了一杯热茶」的形近误写。我不改字，引文照原文；因此我的侧写转述里也不把它当另一个动作。", "quotes": ["profile_1"]},
    {"id": "u21", "topic": "临安与怀庆在现场有没有任何发现", "why": "本区间只写临安装模作样地搜索、并跟着问「有什么发现？」，没有写两位公主发现任何线索。怀庆的追问限于「脱氧核糖是什么」，属于求知而不是查案结果。", "quotes": ["lian_pretend", "both_ask"]},
    {"id": "u22", "topic": "清风殿的宫女宦官被禁足后有没有被问话", "why": "原文只写他们被禁足在大院内，本区间没有任何问话、口供或释放的描写；这条线索在本区间是断的。", "quotes": ["qd_sealed"]},
    {"id": "u23", "topic": "主殿门口四名侍卫是否目击过什么", "why": "原文只写主殿被封闭、四名侍卫守在门口保护现场；许七安只问了小头目现场与证物的保管情况，没有问他们案发当晚是否在场或看到什么。", "quotes": ["qd_main_sealed", "ask_ever"]},
    {"id": "u24", "topic": "福妃的「心腹」住在后院这条布局有没有后续作用", "why": "原文交代了前后院的居住分配（后院住福妃的心腹），但本区间没有让任何心腹出场或提供信息。我照录布局，不替它安排用途。", "quotes": ["qd_layout"]},
    {"id": "u25", "topic": "两三丈高的坠落与「谁都救不了」是否被当作死因结论", "why": "原文用的是叙述者的推断语气（「基本看阎王爷收不收你」「可以解释成」），不是验尸结论；许七安也只说还要先做确认。我不把它升级成已确认死因。", "quotes": ["qd_height", "qd_backhead"]},
    {"id": "u26", "topic": "许七安与临安「清清白白」的自我声明与实际关系是否一致", "why": "这句话是他的内心辩解（「我还是你的牛马」也是自我定位），而开篇叙述已写他确信裱裱对他有情愫、且他在两位公主之间尴尬。两者张力原文没有裁决，我不替它下判断。", "quotes": ["t_xu_reads_signals", "xu_embarrass"]},
]

UNKNOWNS_NOTE = (
    "20 条 unknowns，按来源分四类：动机不明（u6、u7、u8、u10）、案情与证据不足（u1、u3、u4、u9、u13、u14、u18）、"
    "身份与物品归属（u5、u11、u12、u16）、文本层次与词形（u2、u15、u17、u19、u20）。"
    "其中 u2 与 u19 是「本区间结构性读不出来」而不是「我没读到」：u2 的解释在上一章，u19 属于非叙事层。"
    "u11、u12 是**我做了处理但处理本身是判断**的地方，所以即使已在世界设定里写明，仍然在此登记。"
)

# ── selfCritique ──────────────────────────────────────────────────────────
SELF_CRITIQUE = [
    {
        "where": "e7 与 t7.result：把「现场物证 → 许七安的侧写」连成因果边，并把侧写写进任务结果栏",
        "risk": "最可能被复核者推翻的一处：侧写产物（profile_1/2/3）指认太子推人，若我把这条边写成 explicit 或把 result 写成「查明经过」，就等于拿人物推断充当叙述事实 —— 这正是硬红线里「不许把诈问/猜测写成真相」。",
        "why_still": "我仍然这么判断，但做了三层隔离：边只连到「他形成了一条经过」而不连到「福妃是被推的」；侧写链另立 hypothesizedEdges 并逐条标 inferred/未验证；t7.result 标 basis=inferred 且在同一栏带上他本人「有几点我要先做确认」的原话。如果复核者认为连这层隔离也不该连边，那应该删掉的是 e7，而不是把它降级 —— 因为它的机制句（根据现场细节反馈勾勒图像）原文直写，问题只在产物性质。",
    },
    {
        "where": "t2.cost 与 t3.cost 都写了 null（都带理由）",
        "risk": "被读成「没读到就填 null」。t2 里确实有一处很像代价的东西：大哥会很长一段时间被娘记恨；t3 里铃音图谋落空也像代价。",
        "why_still": "cost 是**执行者**付出的东西。t2 的受损者是不在场的大哥、且这个损害是许二郎刻意追求的效果（原文写在一箭双雕里），把它记成许二郎的代价正好把「收益」写成「成本」；t3 的图谋落空是结果而不是代价，原文也没有惩罚动作。两条都按「缺哪一项写 null + 写清为什么」处理，而不是塞一个听起来合理的值。如果复核者认为「被记恨」应计入 t2.cost，我接受改判，但那需要先改写「cost 属于谁」的口径。",
    },
    {
        "where": "w_rule1–w_rule5 全部 institution=executed，declared 0 条；misunderstood 也 0 条",
        "risk": "被读成漏项（提示词把 declared/executed/misunderstood 三态并列，交出「0 个 declared」会被怀疑没查）。",
        "why_still": "本区间确实没有诏、令、法的文本或宣示：元景帝的那套安排只以「有人监督、证物不许带走」的实际效果出现，连一句命令都没有被引用。替它补一个 declared 就是编依据。misunderstood 的情况不同：本区间有两处「人物理解错了」，但错的是**具体人事**（以为许七安对自己有恩、以为大哥给了爹银子），不是对某条规则的理解 —— 套 misunderstood 会把它们从状态/因果降格成术语标签，所以改为记入 s2、k1 并在 excludedSettings x4、x6 写明。这是我主动选择的空集，不是漏查。",
    },
]

SELF_CRITIQUE_NOTE = (
    "3 条自我批评，各写 where（在哪一处）/ risk（最可能怎么被推翻）/ why_still（我为什么仍这么判断、以及若被推翻该改哪一层）。"
    "挑的都是本候选里最脆的判断，而不是最稳的判断；三条都写明了改判时应该改动的具体字段。"
)

# ── 非叙事层：作者附言 ────────────────────────────────────────────────────
AUTHOR_NOTE_LAYER = {
    "present": True,
    "range": "第 138–150 段（分隔线「------------」之后、「重要通告！」至「月票别忘了哦」，至末尾分隔线止）",
    "what": "作者谈更新延误与写案子的方法（先想结尾再逆推、哪章埋伏笔哪章做铺垫）。",
    "disposition": "整段**不作为剧情事实**：不从中提取人物、事件、因果、状态或世界设定。它只被用来解释一条文本事实 —— 本案的伏笔与铺垫是作者预先设计过的。",
    "quotes": ["ps_head", "ps_reason", "ps_craft", "ps_long", "ps_sangbo"],
    "whyItMatters": "这段里「哪几章要埋伏笔」是**作者**的自述，不能拿来倒推本区间内某一处就是伏笔：判定伏笔仍须在正文里找到铺设与回收（见 foreshadows 的判定口径）。",
    "segments": [
        {"label": "分隔线", "quotes": ["ps_sep"]},
        {"label": "通告抬头", "quotes": ["ps_head"]},
        {"label": "延误说明", "quotes": ["ps_delay"]},
        {"label": "不是卡文，是要捋案件脉络", "quotes": ["ps_reason"]},
        {"label": "写案子的方法：逆推、先想结尾", "quotes": ["ps_craft"]},
        {"label": "写案子要先想后续十几章", "quotes": ["ps_long"]},
        {"label": "举桑泊案为例", "quotes": ["ps_sangbo"]},
        {"label": "更新承诺", "quotes": ["ps_promise"]},
        {"label": "求月票", "quotes": ["ps_vote"]},
    ],
}

# ── 段落处置表（反向验证用） ──────────────────────────────────────────────
# 说明：coverage.zeroCoverageList 会列出所有「没有任何引文落点」的段落。
# 那张表只说明「我没引它」，不说明「我读过它、并且判断它不需要引」。
# 下面按**类别**逐条给出处置，配一条取样引文，让复核者能直接核对判断是否成立。
PARAGRAPH_DISPOSITION = [
    {
        "category": "场景分隔与地点标记",
        "handling": "结构性标记，不含可提取的事实；不引不等于漏读。它们的功能是把本章切成四段场景。",
        "quotes": ["t_scene_section_break", "t_scene_marker_xufu", "t_scene_marker_palace"],
    },
    {
        "category": "外貌与体态品评（本区间篇幅最大的一整块）",
        "handling": "叙述者/许七安视角的主观品评。它不产生行动、资源、约束或后果，因此不进世界设定与物件（见 excludedSettings x7）。这是一处**我主动选择不提取**的地方，不是没看到；若复核者认为这类文字也应留痕，那需要先定一条提取口径。",
        "quotes": ["t_compare_block", "t_hq_xiuwei"],
    },
    {
        "category": "临安的服饰与情绪细节",
        "handling": "细节已作为状态 s3 的前值（红裙被问导致不快）与临安登场描写采纳入 biaoShow；其余零散服饰句不再逐句引，避免用同一类事实灌满引文数。",
        "quotes": ["t_lian_red", "t_lian_ask_red", "t_lian_excited"],
    },
    {
        "category": "许七安的内心吐槽（情绪性、无行动后果）",
        "handling": "「很淦」「脚踏两只船」「......」这类吐槽是人物内心情绪，不构成因果或状态变化；其中与处境有关的已提炼进 s7（三家姓奴的尴尬）与 s10（预感被证实）。其余不引。",
        "quotes": ["t_xu_roar", "t_xu_two_boats", "t_xu_speechless"],
    },
    {
        "category": "许府的日常对话（递进式问答与训斥）",
        "handling": "「春闱是什么 / 就是科举 / 科举是什么」这类递进问答是喜剧节奏，事实内容只有一条（春闱在即）已作为 w_rule5；训斥句与逃学图谋已进 t3。不逐句引。",
        "quotes": ["t_ling_quiz", "t_ling_whine", "t_aunt_urge", "t_erlang_ask_eat"],
    },
    {
        "category": "喜剧性动作与互动",
        "handling": "捂眼惨叫、裱裱关切等属于表演性描写：它们支撑 s3 的情绪反转，但本身不含新事实，因此只在 s3 的 anchor 里体现，不单列条目。",
        "quotes": ["t_xu_fake_scream", "t_lian_scared"],
    },
    {
        "category": "行进镜头",
        "handling": "「两位公主行在最前头，白衣对红衣」是过场镜头，唯一可提取的事实（谁走在前面）已在 s7 的处境描写里用到，不再重复引。",
        "quotes": ["t_two_girls_front"],
    },
]
