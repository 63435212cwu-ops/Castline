# -*- coding: utf-8 -*-
"""第六十六章 不跪 —— 读解内容。

规则：凡是引文，都写 quotes_0295.py 里的**键名**；正文散文（objective/obstacle/...）
由我撰写。构建脚本负责把键名解析成 {quote,start,end,sourceHash,para,...}，
并在解析时断言逐字命中、不跨段、落在本单元内、不落进作者区域。

basis 口径（与 basisLegend 一致）：
  explicit  原句直接陈述了该栏内容
  inferred  我的归纳，原文没有一句话直接这么说
  derived   需要把两处分开的陈述合起来才成立
"""

# ── 作者场外留言区（PS/码字说明/文末分隔线）──────────────────────────────
AUTHOR_REGION = [(1295417, 1295556)]
AUTHOR_REGION_NOTE = (
    "AUTHOR_REGION=[(1295417,1295556)]：从 P512「PS：感谢“沛哥大大”和“城北徐工”的盟主打赏。」"
    "起，经 P514 的码字说明，到文末分隔线「------------」为止。它属**场外留言**，不算叙事证据；"
    "本候选所有叙事引文都不落在该区间内（machineSelfCheck.authorRegionLeaks 应为 0）。"
    "注意 1295400 那句「...........」是场景分隔符、仍在叙事文本内，故不在作者区域里。"
    "该区域的引文只出现在 authorRegionEvidence 一节。"
)

# ── tasks：五元组，每栏各自引证 ──────────────────────────────────────────
TASKS = [
    {
        "id": "T01", "actor": "度厄罗汉",
        "title": "把许七安度入空门（以「修罗问心」强压）",
        "objective": "无论如何都要把这位「天生慧根的佛子」度入空门；动机不止惜才，还因为他想做「大乘佛法的奠基人」，"
                     "而许七安是这套理念的开创者——只有许七安入了佛门，才能彰显「正统」。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": ["j_must_convert", "j_founder"],
        "obstacle": "许七安在佛掌重压下「膝盖依旧直着」：他心里反复念「不跪，不跪，不跪」，"
                    "并给自己定下「就算要信佛，也是我心甘情愿的信，谁都不能驯服我」。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": ["knee_straight", "x_obj_will"],
        "action": "他先当众宣布这一关叫「修罗问心」并讲佛陀度修罗族的典故，"
                  "随后金刚法相睁眼、擎天法相垂下佛掌「往下一按」——以佛法灌顶与重压逼人屈服。",
        "actionBasis": "explicit",
        "actionQuotes": ["announce_gate", "legend_end", "palm_lower"],
        "result": "没有度成：佛境幻灭，两道身影跌出，许七安「傲然而立，手握刻刀」；度厄本人的第一反应是「愕然不已」，全场「满场寂静无声」。",
        "resultBasis": "explicit",
        "resultQuotes": ["realm_vanish", "x_res_two", "duer_shock", "silence_all"],
        "cost": "他的法器金钵被震毁——「裂开一道道缝隙，终于，『砰』的一声，炸成齑粉」。",
        "costBasis": "explicit",
        "costQuotes": ["bowl_dust"],
    },
    {
        "id": "T02", "actor": "许七安",
        "title": "守住本心，不进佛门",
        "objective": "进庙过最后一关而不皈依：他记得规则是「进了寺庙，如果依旧不肯皈依佛门，那就算佛门输了」；"
                     "为此他特意在进殿前回忆教坊司花魁的招式「以此污浊内心」，确认自己成了老色批才推门。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": ["x_obj_rule", "x_dirty_mind"],
        "obstacle": "「修罗问心」直接改他的内心：佛光「在瞬间压垮了他的意志，改变了他的内心」，"
                    "排山倒海的压力「迫使他下跪」。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": ["crush_will", "x_obs_press"],
        "action": "他先是倔强吐出「不跪........」；等众生之力涌入、清光化作刻刀落入手中，"
                  "他直起腰杆、说出「众生皆可成佛，为何跪你？」并「平静的刺出了刻刀」。",
        "actionBasis": "explicit",
        "actionQuotes": ["x_spit", "x_res_stand", "x_act_thrust"],
        "result": "佛像眉心龟裂、裂缝瞬间遍布全身继而崩散；佛境剧烈抖动、佛山坍塌、「天摇地动」。",
        "resultBasis": "explicit",
        "resultQuotes": ["x_res_crack", "realm_shake"],
        "cost": "身体代价写得具体：肩膀血肉模糊、颈椎以诡异角度弯曲，痛苦映入场外众人眼中；最后昏厥。",
        "costBasis": "explicit",
        "costQuotes": ["x_cost_wound", "x_cost_faint"],
    },    {
        "id": "T03", "actor": "裱裱与怀庆",
        "title": "要求公开寺庙内的景象",
        "objective": "裱裱要看见寺庙里的情形：她「要看寺庙里的情形」，不信许七安会遁入空门。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": ["b_obj"],
        "obstacle": "佛境里的景象本不对外显示：「看不见寺庙里的景象」时她只能不停脑补许七安受害，越想越忍不住。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": ["b_obs"],
        "action": "裱裱霍然起身、桃花眸里罕见地绽出狠意怒斥佛门「设了什么龌龊伎俩」；"
                  "怀庆接着以斗法应「风光霁月」为由，冷冰冰地请度厄现出寺庙景象。",
        "actionBasis": "explicit",
        "actionQuotes": ["b_rise", "b_suspect", "hq_demand"],
        "result": "要求被满足：度厄合十微笑、宽袖一挥，佛境画面切换，众人看见了烛光摇曳的大殿。",
        "resultBasis": "explicit",
        "resultQuotes": ["b_res_switch"],
        "cost": None,
        "costNote": "本区间没有写她们为这件事付出任何代价：度厄当即应允切换画面，"
                    "叙述也没有写她们因此受损（裱裱此前的焦虑写在 obstacle 里，是阻碍不是代价）。",
    },
    {
        "id": "T04", "actor": "云鹿书院院长赵守与三位大儒",
        "title": "压制亚圣殿里暴动的红木盒子",
        "objective": "让盒子安静下来：赵守「眉头紧锁，拱手道：『请前辈安静。』」——这是他们对盒中之物的请求与约束。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": ["s_obj"],
        "obstacle": "盒子不听：请示之后「震动愈发剧烈」，而且「里面的东西似乎迫切的想要出来」；"
                    "第一次安静只维持了一瞬。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": ["box_shake", "box_hang"],
        "action": "三位大儒「立刻鼓荡浩然正气」，与院长赵守联手压制红木盒子，再次拱手请它安静。",
        "actionBasis": "explicit",
        "actionQuotes": ["s_act"],
        "result": "只换来极短暂的安静——「红木盒子再次安静，但就在下一刻........」；紧接着盒子就炸散了。",
        "resultBasis": "explicit",
        "resultQuotes": ["box_quiet", "box_burst"],
        "cost": "代价明确且有执行动作：盒子炸散的同时，赵守与三位大儒「胸口如撞，鲜血狂喷，齐齐震飞」。",
        "costBasis": "explicit",
        "costQuotes": ["s_cost_hurt"],
    },
    {
        "id": "T05", "actor": "监正",
        "title": "取金刚经，并在必要时出手阻止「修罗问心」",
        "objective": "他的目的已经写明——「金刚经到手，他的目的达到了」；这一章前半段他放任度厄讲经，就是为了这件东西。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": ["jz_scripture"],
        "obstacle": "「修罗问心」这一关「必须有外力才能阻止，单凭许七安自己，绝对无法抗住佛法灌顶」——"
                    "他必须自己动手，别无他法。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": ["jz_need_force"],
        "action": "他先应下皇帝的请求，然后「握住了酒杯」，苍老的手掌「青筋凸起，似乎在蓄力」。",
        "actionBasis": "explicit",
        "actionQuotes": ["jz_cup", "jz_charge"],
        "result": "他中途停手：「监正忽然停下来，愕然眺望远方。那是云鹿书院的方向。」——"
                  "真正撞入佛境的那道清光并非出自他的手（其来处见 E20，为跨场景推导）。",
        "resultBasis": "explicit",
        "resultQuotes": ["e_res_jzstop"],
        "cost": None,
        "costNote": "本区间未写他为这件事付出任何代价。他蓄的力没有发出去（p452「忽然停下来」），"
                    "叙述也没有写他因此受损或受责；「应召而来」的那道清光反而替他解决了问题。",
    },
    {
        "id": "T06", "actor": "元景帝",
        "title": "不许许七安遁入空门",
        "objective": "明确下过禁令式的要求：「朕不允许许七安遁入空门，成为佛家弟子。」",
        "objectiveBasis": "explicit",
        "objectiveQuotes": ["e_obj_stop"],
        "obstacle": "监正当面回绝了他的担忧：「陛下乃九五之尊，区区一个银锣，不必在乎。」——"
                    "他要保的人，在监正眼里不值得在乎。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": ["e_obs_jz"],
        "action": "他「一口否决」监正的说法，把利害讲到国运层面，命令「不管用什么办法，你一定要阻止」，"
                  "并声明「哪怕输了天机盘」。",
        "actionBasis": "explicit",
        "actionQuotes": ["e_order2", "e_act_order"],
        "result": "只拿到一句承诺：「监正颔首：『陛下放心。』」——本区间没有写这道命令被执行成动作"
                  "（监正随即停手，见 R06）。",
        "resultBasis": "explicit",
        "resultQuotes": ["jz_nod"],
        "cost": None,
        "costNote": "「哪怕输了天机盘」是**有条件的授权**（他允许以输掉赌局为代价去阻止），"
                    "但本区间没有写他真的输了天机盘，也没有写他为此付出任何已执行的代价 ⇒ 记 null，"
                    "不把一句条件让步当成已付代价。",
    },
    {
        "id": "T07", "actor": "许七安",
        "title": "参悟金刚法相、拿走金刚经",
        "objective": "他想要的是佛门神通：度厄说完许诺，他「顿时眼神火热」，"
                     "因为「他一直很眼馋佛门的金刚神通」，想修成护体神功在六品武者境称无敌。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": ["j_obj"],
        "obstacle": "经不在他能看到的地方：他盯了一刻钟只得出「金刚经在佛像里？什么乱七八糟的东西，明明没有啊」，"
                    "进而自嘲「我果然是没有佛根的粗鄙武夫」。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": ["j_obs", "x_selfmock"],
        "action": "他「盘坐在蒲团上，昂着头，审视着金刚法相」，一直看下去。",
        "actionBasis": "explicit",
        "actionQuotes": ["j_act_sit"],
        "result": "他看懂了：丹田暖流上行、眉心一振，随后「看懂了禅意，看懂了法相中蕴含的佛韵」，"
                  "不自觉摆出与佛像一样的坐姿，几个呼吸间浑身灿灿金光，成了另一尊金身法相。",
        "resultBasis": "explicit",
        "resultQuotes": ["dantian", "understand_chan", "j_res_gold"],
        "cost": None,
        "costNote": "本区间没有写他为取得金身付出代价：过程只有「眼睛快酸了」（写在 obstacle 里）与"
                    "「这个过程维持了不知多久」的时间流逝，没有任何损失、损伤或付出被叙述；"
                    "事后被百姓误认为皈依，承担后果的是百姓（见 S04），不是他。",
    },
    {
        "id": "T08", "actor": "在场的大奉子民（张巡抚、许平志、魏渊、王首辅与百姓）",
        "title": "喊出「不跪」，把声音送进佛境",
        "objective": "要许七安别跪下去：许平志喝道「宁宴，站直了，不跪」，王首辅朗声「大奉武者，不跪」——"
                     "都是指向他的祈使句。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": ["p_obj", "wang_line"],
        "obstacle": "他正被压得直不起来：浑身骨头爆豆般作响、「头埋的更低了，怎么都直不起来」，"
                    "而场外的人只能看着，无法替他分担。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": ["bones_crack", "p_obs_head", "crowd_angry", "crowd_watch"],
        "action": "从一个声音变成全场的声音：张巡抚起身引「少年侠气……一诺千金重」后高喊「不跪」，"
                  "许平志握拳喝道、魏渊替许铃音补完、王首辅朗声，群众抬拳吼「不跪」，"
                  "像点燃导火索一样沸腾，父亲举子、丈夫握妻，最终「从凉棚到场外，从贵族到百姓」发出共同的声音。",
        "actionBasis": "explicit",
        "actionQuotes": ["zhang_rise", "zhang_ci", "p_fist", "wei_finish", "someone_fist", "fuse", "p_act_many", "p_act_voice"],
        "result": "声音真的进了佛境：意识朦胧间他「又感觉到众生之力」，一股驳杂而宏大的念头涌入识海，"
                  "向他传递「不跪！」。",
        "resultBasis": "explicit",
        "resultQuotes": ["p_res_sense", "voice_bukui"],
        "cost": "代价落在在场的京城百姓身上：清光与佛掌交锋炸开的巨响「震的京城百姓抱头鼠窜」。"
                "注意这是交锋的后果，不是百姓主动付出之物——本候选仍把它记在 cost，理由已写进 selfCritique[1]。",
        "costBasis": "explicit",
        "costQuotes": ["boom"],
    },
    {
        "id": "T09", "actor": "美妇人与弟子蓉蓉",
        "title": "想把蓉蓉送进许府做妾",
        "objective": "美妇人要给弟子谋一个去处：「以你的姿色，给许大人做妻倒是勉强，但身份不够。做个妾，却是没问题的。」",
        "objectiveBasis": "explicit",
        "objectiveQuotes": ["rong_marry"],
        "obstacle": None,
        "obstacleNote": "本区间没有写这件事遇到阻碍。辈分/名分上的障碍（做妻「身份不够」）是美妇人自己一句话就绕开的"
                        "（「咱们江湖儿女，不讲究名分」），不构成她面对的障碍；蓉蓉的迟疑写在 result 里。",
        "action": "她先做了功课再开口：「为师打探过了，这位许大人........嗯，是教坊司的常客。」",
        "actionBasis": "explicit",
        "actionQuotes": ["meifu_probe"],
        "result": "没有答应也没有回绝：蓉蓉「是想拒绝的」，但那个男人太耀眼，「也忍不住有些心动」。",
        "resultBasis": "explicit",
        "resultQuotes": ["rong_hesitate"],
        "cost": None,
        "costNote": "本区间未出现代价描写：既没有写蓉蓉付出什么，也没有写美妇人失去什么，"
                    "叙述停在「有些心动」这一层。",
    },
]

# ── causeEdges：方向 + 触发机制 ─────────────────────────────────────────
CAUSE_EDGES = [
    {
        "id": "E01", "from": "度厄当众认输并说「许施主当为吾师」",
        "to": "在场的江湖人士扬眉吐气，认为武夫终于被其他体系的巅峰强者尊为师长",
        "mechanism": "触发是**当众定性**：一句「当为吾师」把一位武夫放到佛门高僧的师长位置，"
                     "而叙述先交代武夫长期被「各大体系鄙夷」这一旧处境，再写江湖人士「激动了」，"
                     "对比落差就是机制本身，不是先后顺序。",
        "basis": "explicit", "quotes": ["teacher_line", "wufu_despised", "proud_line", "wufu_want", "turn_win"],
    },
    {
        "id": "E02", "from": "度厄许诺「金刚经的奥秘就在金身之中，你若能参悟，便可修成佛门金刚不败」",
        "to": "许七安眼神火热、起意要修这门护体神功",
        "mechanism": "触发是**利益指向**：许诺给出了具体的可得之物（金身中的金刚经）与具体收益"
                     "（六品武者境称无敌、补上砍完一刀气虚力竭的短板），他的反应紧接在许诺之后。",
        "basis": "explicit", "quotes": ["j_promise", "j_eyes_hot"],
    },
    {
        "id": "E03", "from": "许七安盯着佛像观察一刻钟也找不到金刚经",
        "to": "他自嘲「我果然是没有佛根的粗鄙武夫」",
        "mechanism": "触发是**努力落空后的自我归因**：叙述写「明明没有啊」+ 眼睛快酸了，"
                     "紧跟一句「他心里自嘲一声」，把找不到经归因到自己没有佛根。",
        "basis": "explicit", "quotes": ["j_obs", "x_selfmock"],
    },
    {
        "id": "E04", "from": "腹内暖流自丹田上行、眉心霍然一振",
        "to": "他看懂了金刚法相中蕴含的禅意与佛韵",
        "mechanism": "触发是**身体先于认知的变化**：叙述先把暖流的路径（丹田→中丹田→上丹田→眉心）写出来，"
                     "再写「眼前的佛像，有变化了」，然后才是「令人意外的是，他看懂了」。这条通了，看才通。",
        "basis": "explicit", "quotes": ["dantian", "x_see_change", "understand_chan"],
    },
    {
        "id": "E05", "from": "看懂禅意、认出「是在帮我」",
        "to": "他不自觉改变坐姿，双手合十、眼睛半眯，与佛像一模一样",
        "mechanism": "触发是**认同后的模仿**：「念头闪过」之后才是「不自觉的改变坐姿」，"
                     "而坐姿被明确写成与佛像「一模一样」——禅意先被接受，身体才照着做。",
        "basis": "derived", "quotes": ["understand_chan", "chan_help", "j_act_posture"],
    },
    {
        "id": "E06", "from": "坐姿与佛像一模一样、眉心一点金漆诞生",
        "to": "几个呼吸间他浑身灿灿金光，成了另一尊金身法相",
        "mechanism": "触发是**由内而外的描金过程**：金漆从眉心「迅速蔓延」，"
                     "被比作「无形的笔在他身上勾勒」，随后才是全身金光，顺序与因果同向。",
        "basis": "explicit", "quotes": ["gold_paint", "j_res_gold"],
    },
    {
        "id": "E07", "from": "许七安当场化作金身",
        "to": "市井百姓以为他被佛门度化，士气垮掉",
        "mechanism": "触发是**误读**：百姓只看到「浑身灿灿金光」这一表象，"
                     "叙述紧接着写他们「险些崩裂」「像是戳破了的气球」，"
                     "并把原因写成「最后却被佛门『度化』」——先有误读，才有崩溃。",
        "basis": "explicit", "quotes": ["j_res_gold", "people_shatter", "convert_misread"],
    },
    {
        "id": "E08", "from": "江湖客当众解释「非但不是皈依佛门，反而是修成了佛门神功——金刚不败」",
        "to": "不懂修行的百姓放心了，再次笑起来",
        "mechanism": "触发是**解释改变了同一事实的意义**：金身没有变，变的是百姓对它的理解；"
                     "叙述明写「原来不是……而是修成了佛门的金身」，紧接着写喧哗如开闸洪水、百姓再次笑起来。",
        "basis": "explicit", "quotes": ["jh_explain", "other_side_1", "people_relieved"],
    },
    {
        "id": "E09", "from": "度厄宣布这一关叫「修罗问心」并讲出佛陀度修罗族的典故",
        "to": "王首辅等权臣与世袭贵族脸色大变",
        "mechanism": "触发是**类比外推**：叙述先把典故的结局摆出来（修罗族被度化、皈依佛门），"
                     "再写权臣据此推出现在这一关的效果「必然是与佛陀度化修罗族是一样的」，"
                     "于是反推「还度不了一个许七安？」——恐惧来自推论，不是来自场面。",
        "basis": "explicit", "quotes": ["announce_gate", "gate_echo", "legend_end", "ministers_pale"],
    },
    {
        "id": "E10", "from": "金刚法相忽然睁开眼睛",
        "to": "佛法的威严如山崩海啸吞没许七安，瞬间压垮他的意志、改变他的内心",
        "mechanism": "触发是**法器由静转动**：前文这尊法相一直「半眯着眼」，睁眼即是发动；"
                     "紧接着就是佛光与「在瞬间压垮了他的意志」——发动与效果写在相邻两句，"
                     "且中间没有别的动作可归因。",
        "basis": "explicit", "quotes": ["faxiang_open", "foguang", "crush_will"],
    },
    {
        "id": "E11", "from": "本心被改、开始向往佛门佛法",
        "to": "他站起来抽刀、把手按在貂帽上（要给自己剃度）",
        "mechanism": "触发是**信念改变带来行为**：叙述先写思想变了（「开始向往佛门」、"
                     "「连教坊司的花魁们都不香了」），再写他在众目睽睽中起身抽刀按帽；"
                     "剃度的意图由叙述点明（「这是要给自己剃度」）。",
        "basis": "explicit", "quotes": ["yearn", "draw_knife_hat", "tonsure_note"],
    },
    {
        "id": "E12", "from": "意识到摘帽会把「大卤蛋」曝光在成千上万人眼里",
        "to": "巨大的羞耻感让他找回了一点「自我」，松开了按住貂帽的手",
        "mechanism": "触发是**羞耻而非道理**：叙述先喊出「卧槽，不能摘啊，不能摘！」，"
                     "再给出机制「巨大的羞耻感让他找回了一点『自我』」，然后才是松手、貂帽仍在头上。"
                     "救他的不是佛法上的觉悟，是不肯当众出丑。",
        "basis": "explicit", "quotes": ["hat_shame_self", "shame_self", "x_loose_hat"],
    },
    {
        "id": "E13", "from": "度厄再劝「明明有大佛根，为何却如此执迷不悟？」",
        "to": "佛像震怒，佛山雾气抖动，凝聚出一道顶天立地的金身法相",
        "mechanism": "触发是**劝告失败转为压制**：叙述用「许七安的抗拒，似乎引来了佛像的震怒」"
                     "把上一步的抗拒与法相凝聚连起来；「似乎」是叙述的措辞，故本条记 derived 而非 explicit。",
        "basis": "derived", "quotes": ["duer_sigh", "refuse_anger"],
    },
    {
        "id": "E14", "from": "擎天法相的佛掌往下按",
        "to": "许七安肩膀猛的一沉、浑身骨头爆豆般作响，头埋得更低",
        "mechanism": "触发是**直接施加的力**：叙述把「往下一按！」单独成段，"
                     "下一段就是「肩膀猛的一沉，像是肩上被压了一座大山」，再下一段是骨头作响。"
                     "施力点与受力点写得对应。",
        "basis": "explicit", "quotes": ["palm_press", "shoulder_sink", "bones_crack"],
    },
    {
        "id": "E15", "from": "全场「不跪」的声浪与涌入识海的众生之力",
        "to": "许七安吼出「我！许七安，不！跪！」并抬起手臂",
        "mechanism": "触发是**外部念头与本人意志合流**：叙述先写他感应到众生之力、"
                     "「在向他传递一个声音：不跪！」，再写他鬼使神差抬起手臂，"
                     "最后用「同一时刻」把全场心声与他的吼声并置——力量先到，声音才出。",
        "basis": "explicit", "quotes": ["voice_bukui", "raise_arm", "something_came", "x_act_roar"],
    },
    {
        "id": "E16", "from": "许七安吼出不跪、手臂抬起像是要握住什么",
        "to": "一道清光破空而来，悍然撞入佛境",
        "mechanism": "触发是**应召**：叙述在清光撞入之后补了一句「这道清光，应召而来」，"
                     "把这次到来写成对某个呼唤的回应；呼唤的内容在前一段（不跪的心声与吼声）。"
                     "这是叙述明写的机制，不是时间相邻。",
        "basis": "derived", "quotes": ["x_act_roar", "qingguang_in", "yingzhao"],
    },
    {
        "id": "E17", "from": "清光与佛掌交锋、青金光团炸开",
        "to": "擎天法相崩裂成金光，清光入庙落在许七安手里",
        "mechanism": "触发是**对抗的结果**：先是「清光和金光同时一黯」，"
                     "再是爆炸声，然后才写「擎天法相崩裂成纯粹的金光」与「那道清光旋即入庙」——"
                     "两股力量的胜负决定了法相与清光各自的去向。",
        "basis": "explicit", "quotes": ["faxiang_retract", "clash", "boom", "faxiang_beng"],
    },
    {
        "id": "E18", "from": "许七安握紧刻刀、平静刺出",
        "to": "佛像眉心龟裂、遍身崩散，佛境随之幻灭",
        "mechanism": "触发是**一击落在法相本体上**：叙述写「他说完这句话，平静的刺出了刻刀」，"
                     "紧接着「咔擦.......佛像眉心龟裂」，再往下才是佛像崩溃、佛境幻灭。"
                     "刺的是佛像，碎的是佛像，中间没有别的动作。",
        "basis": "explicit", "quotes": ["x_act_thrust", "x_res_crack", "realm_shake"],
    },
    {
        "id": "E19", "from": "佛像崩散、佛境幻灭",
        "to": "度厄的金钵裂开缝隙、炸成齑粉，两道身影跌出",
        "mechanism": "触发是**容器随内容物一同毁坏**：叙述按「佛像崩溃 → 佛境抖动 → "
                     "度厄低头看见金钵裂开 → 佛境幻灭 → 两道身影跌出」的顺序推进，"
                     "金钵裂开被夹在佛境毁灭的过程之中。",
        "basis": "derived", "quotes": ["realm_shake", "bowl_dust", "x_res_two"],
    },
    {
        "id": "E20", "from": "云鹿书院亚圣殿的红木盒子炸散、一道清光破盒而出",
        "to": "撞入佛境、落在许七安手里并化作刻刀的那道清光",
        "mechanism": "触发是**同一道光的接力**，但这条是跨场景推导，机制分三步："
                     "① 盒子炸散、清光「撞穿殿顶，破空而起」；② 赵守追出殿外，目光随清光，"
                     "「那是京城的方向」；③ 京城佛境中「一道清光破空而来」并「落在许七安手里」，"
                     "那是一把黑色刻刀。三处都写作「清光」，且方位从云鹿书院指向京城，"
                     "故推导为同一物——原文没有一句话直接说「刻刀就是盒中之物」，这正是复核该盯的地方。",
        "basis": "derived", "quotes": ["box_burst", "light_out", "city_direction", "knife_desc"],
    },
    {
        "id": "E21", "from": "满场「不跪」的声音与众生之力涌入",
        "to": "许七安在佛掌下直起腰杆",
        "mechanism": "触发是**力量给了他不肯跪的支点**：他先前「依旧无法直起脊梁」，"
                     "在感应到众生之力、吼出不跪之后才「缓缓的，慢慢的直起腰杆」；"
                     "叙述把无法直起与直起写成同一场压力的前后两态。",
        "basis": "explicit", "quotes": ["raise_arm", "x_res_stand", "x_obj_will"],
    },
    {
        "id": "E22", "from": "元景帝下令「不管用什么办法，你一定要阻止」",
        "to": "监正颔首应下「陛下放心」",
        "mechanism": "触发是**君臣之间的应答**：命令与应承紧邻且指向同一件事，"
                     "监正的动作就是颔首答话。注意这条只到「应下」为止——"
                     "应下之后他并没有出手（见 R06）。",
        "basis": "explicit", "quotes": ["e_act_order", "jz_nod"],
    },
    {
        "id": "E23", "from": "监正握住酒杯、青筋凸起蓄力",
        "to": "他忽然停下来，愕然眺望云鹿书院的方向",
        "mechanism": "触发是**察觉变数而收手**：叙述先写蓄力（「似乎在蓄力」），"
                     "紧接着用「但这时」转折写他停下并望向远方。两句之间只有这一个外力线索，"
                     "故记为他因察觉而收手；「似乎在蓄力」本身是叙述的推测措辞，"
                     "所以这条记 derived。",
        "basis": "derived", "quotes": ["jz_charge", "e_res_jzstop"],
    },
    {
        "id": "E24", "from": "三位大儒与赵守鼓荡浩然正气联手压制",
        "to": "红木盒子短暂安静，随即更强地炸散",
        "mechanism": "触发是**压制反被突破**：叙述写「红木盒子再次安静，但就在下一刻........」"
                     "接「砰！」——「再次」表明这是第二次压下又弹起，"
                     "压制动作与失败结果由同一段文字承接连贯。",
        "basis": "explicit", "quotes": ["s_act", "box_quiet", "box_burst"],
    },
    {
        "id": "E25", "from": "许七安化作金身、被误认为修成金刚不败",
        "to": "九位金锣与武将既羡且酸，魏渊则选择不追究内幕",
        "mechanism": "触发是**同一件事在不同人身上产生不同反应**："
                     "金锣「心里像是恰了柠檬似」是因为他们同为武者、明白这门神功的价值"
                     "（叙述补了理由「战力相差不大的情况下，谁最硬，谁就能胜」）；"
                     "魏渊「不追究内幕」是因为他只要许七安在武道勇猛精进。",
        "basis": "explicit", "quotes": ["nine_jinluo", "hard_win", "wujiang", "wei_notinvest"],
    },
]

# ── rejectedEdges：时间相邻/同一场景但不连边 ─────────────────────────────
REJECTED_EDGES = [
    {
        "id": "R01", "wouldBe": "裱裱高喊「不要给秃驴下跪，狗奴才，站着」 → 许七安松开按貂帽的手、恢复自我",
        "whyNot": "方向反了：松手与「貂帽依旧戴在头上」在原文里位于裱裱喊话之前，"
                  "裱裱的高喊发生在佛掌已经压下、他蜷着脖子硬扛之后。"
                  "救他的是羞耻感（E12），不是这句喊话 ⇒ 不连边。",
        "basis": "explicit", "quotes": ["x_loose_hat", "b_nokneel"],
    },
    {
        "id": "R02", "wouldBe": "监正蓄力 → 撞入佛境的那道清光",
        "whyNot": "时间上紧邻，但原文在同一段里写他「忽然停下来，愕然眺望远方」，"
                  "方向是云鹿书院；而清光被写成「应召而来」、且从云鹿书院方向破空而至。"
                  "把清光记成监正出手，等于用时间相邻覆盖掉两句相反的叙述 ⇒ 不连边（改记 E20/E23）。",
        "basis": "explicit", "quotes": ["e_res_jzstop", "yingzhao"],
    },
    {
        "id": "R03", "wouldBe": "度厄说「许施主当为吾师」 → 许七安在佛法上真的胜过了度厄",
        "whyNot": "这是人物的当众之辞，不是叙述判定：他认的只是「第三关是你胜了」，"
                  "同一段里他立刻把战线推到下一关（宣布「修罗问心」）。"
                  "把人物的话当成事实判定，正是本任务禁止的形态 ⇒ 不连边。",
        "basis": "explicit", "quotes": ["teacher_line", "announce_gate"],
    },
    {
        "id": "R04", "wouldBe": "许七安化作金身 → 他皈依了佛门",
        "whyNot": "这是市井百姓当场的第一反应，原文紧接着就由江湖客给出相反的解释，"
                  "并被叙述确认为「原来不是大奉的年轻天才皈依佛门，而是修成了佛门的金身」。"
                  "这条边**被原文本身否证** ⇒ 不连边，只作为 E07 的误读环节保留。",
        "basis": "explicit", "quotes": ["convert_misread", "other_side_1"],
    },
    {
        "id": "R05", "wouldBe": "怀庆说「别高兴的太早，还有一尊法相呢」 → 修罗问心这一关的发生",
        "whyNot": "两件事相邻，但关次是度厄当众宣布的（announce_gate），"
                  "怀庆那句话只是提醒众人场上还有一尊法相未动；原文没有把她的提醒写成触发 ⇒ 不连边。",
        "basis": "explicit", "quotes": ["hq_warn", "announce_gate"],
    },
    {
        "id": "R06", "wouldBe": "元景帝下令阻止 → 监正出手阻止",
        "whyNot": "命令**没有**转成执行动作：监正只颔首应下，随后「忽然停下来」；"
                  "本区间没有任何一句写他发动过什么。这正是「命令 ≠ 已执行」，"
                  "所以只连到「应下」（E22），不连到出手 ⇒ 不连边。",
        "basis": "explicit", "quotes": ["e_act_order", "jz_nod", "e_res_jzstop"],
    },
    {
        "id": "R07", "wouldBe": "「进了此庙，便是石头，也能点化」 → 许七安果然被点化",
        "whyNot": "这是一句大话，而且被后文反向兑现：他既没被点化，佛像还被他用刻刀刺碎。"
                  "把人物的夸口当成预告，等于替原文许下一个它没有兑现的承诺 ⇒ 不连边。",
        "basis": "explicit", "quotes": ["duer_boast_stone", "x_res_crack"],
    },
    {
        "id": "R08", "wouldBe": "百姓齐喊「不跪」 → 许七安第一次拒绝摘帽（松手）",
        "whyNot": "顺序不支持：他松开按貂帽的手发生在全场喊「不跪」之前（见 R01 同一处）。"
                  "声浪确实进了佛境，但作用在佛掌压下的那一段（E15/E21），"
                  "不是作用在更早的剃度动作上 ⇒ 不连边。",
        "basis": "explicit", "quotes": ["x_loose_hat", "p_act_voice"],
    },
]

# ── states：前值 / 后值 / 事件锚点 ──────────────────────────────────────
STATES = [
    {
        "id": "S01", "who": "许七安", "aspect": "本心与意志",
        "before": "被佛光灌顶改心：意志被瞬间压垮、内心被改变，开始向往佛门佛法，连教坊司的花魁都不香了",
        "beforeBasis": "explicit", "beforeQuotes": ["crush_will", "yearn", "no_more_huakui"],
        "after": "短暂夺回自我意志，抗拒加入佛门、抗拒那些灌输进来的思想，貂帽仍戴在头上",
        "afterBasis": "explicit", "afterQuotes": ["x_selfwill"],
        "anchor": "意识到摘帽会把光头曝光在成千上万人眼前，巨大的羞耻感让他找回「自我」",
        "anchorBasis": "explicit", "anchorQuotes": ["x_hat_draw", "hat_shame_self", "shame_self"],
        "note": "锚点是**羞耻**而不是觉悟：原文写的是「巨大的羞耻感让他找回了一点『自我』」，"
                "并且这一态只被称为「短暂的」（after 引文）。不要把它读成他已经彻底摆脱了灌顶。",
    },
    {
        "id": "S02", "who": "许七安", "aspect": "身体损伤",
        "before": "佛掌第一次下按，肩膀猛的一沉，「像是肩上被压了一座大山」",
        "beforeBasis": "explicit", "beforeQuotes": ["shoulder_sink", "stress_sea"],
        "after": "肩膀血肉模糊、颈椎以诡异角度弯曲，痛苦清晰地映入场外众人眼中",
        "afterBasis": "explicit", "afterQuotes": ["x_cost_wound"],
        "anchor": "浑身骨头爆豆般作响、脊椎隐隐外凸「随时都会刺破血肉」",
        "anchorBasis": "explicit", "anchorQuotes": ["bones_crack", "x_bones_red", "x_face_red"],
        "note": "前值取第一次受力、锚点取骨头作响、后值取场外可见的伤；"
                "三处都是叙述直述的伤情，没有写他事后是否痊愈（见 U09）。",
    },
    {
        "id": "S03", "who": "度厄罗汉", "aspect": "心境（得意→愕然）",
        "before": "畅快淋漓：认为来访大奉是生平最正确的决定，「一朝顿悟大乘佛法，更得一位天生慧根的佛子」",
        "beforeBasis": "explicit", "beforeQuotes": ["duer_exult", "duer_exult2"],
        "after": "愕然低头，看见自己的金钵裂开一道道缝隙、炸成齑粉",
        "afterBasis": "explicit", "afterQuotes": ["bowl_dust"],
        "anchor": "佛像崩散、佛境幻灭",
        "anchorBasis": "explicit", "anchorQuotes": ["realm_vanish"],
        "note": "「愕然」在原文出现两次（对金身的愕然、对金钵碎裂的愕然），"
                "本状态取后一次；前一次属于对金身的误读阶段，不混入这条状态。",
    },
    {
        "id": "S04", "who": "市井百姓", "aspect": "情绪（骄傲→崩溃→放心）",
        "before": "以为他被佛门度化，脸色瞬间垮了，「一个个的像是戳破了的气球，一泻千里」",
        "beforeBasis": "explicit", "beforeQuotes": ["people_shatter"],
        "after": "听懂解释后放心了，「再次笑了起来」",
        "afterBasis": "explicit", "afterQuotes": ["people_relieved"],
        "anchor": "江湖客当众点明「非但不是皈依佛门，反而是修成了佛门神功——金刚不败」",
        "anchorBasis": "explicit", "anchorQuotes": ["jh_explain"],
        "note": "这是一条**三段式**状态：骄傲（三关连胜）→ 误读崩溃 → 解释后放心。"
                "中间那次崩溃完全由误读造成，与事实相反。",
    },
    {
        "id": "S05", "who": "云鹿书院院长赵守与三位大儒", "aspect": "从压制到被震飞",
        "before": "三人与院长联手鼓荡浩然正气、拱手请盒中之物安静",
        "beforeBasis": "explicit", "beforeQuotes": ["s_act"],
        "after": "盒子炸散的同时，四人「胸口如撞，鲜血狂喷，齐齐震飞」",
        "afterBasis": "explicit", "afterQuotes": ["s_cost_hurt"],
        "anchor": "红木盒子炸散、亚圣殿内清光一震",
        "anchorBasis": "explicit", "anchorQuotes": ["box_burst"],
        "note": "锚点与后值在原文是同一句的两个分句，但一个是事件、一个是后果，故分开引用。",
    },
    {
        "id": "S06", "who": "亚圣殿里的红木盒子", "aspect": "从剧烈震动到炸散",
        "before": "剧烈震动，「里面的东西似乎迫切的想要出来」，第一次压制后只安静了一瞬",
        "beforeBasis": "explicit", "beforeQuotes": ["box_hang", "box_quiet"],
        "after": "炸散，一道清光破盒而出、撞穿殿顶破空而起",
        "afterBasis": "explicit", "afterQuotes": ["box_burst", "light_out"],
        "anchor": "「嗡嗡嗡........岂料，红木盒子的震动愈发剧烈」——第二次震动升级",
        "anchorBasis": "explicit", "anchorQuotes": ["box_shake"],
        "note": "「炸散」是盒子的失去（lose，见 W08），但它同时是清光的产生，"
                "两种状态分属盒子与清光，不合成一条物品链。",
    },
    {
        "id": "S07", "who": "许七安", "aspect": "姿态（低头→直起腰杆）",
        "before": "头埋得更低，「怎么都直不起来」，同时「唯一不变的，是膝盖没有弯曲」",
        "beforeBasis": "explicit", "beforeQuotes": ["p_obs_head", "d_obs_knee"],
        "after": "「缓缓的，慢慢的直起腰杆，握紧了刻刀」",
        "afterBasis": "explicit", "afterQuotes": ["x_res_stand"],
        "anchor": "众生之力涌入、识海里传来「不跪！」，他吼出自己的不跪",
        "anchorBasis": "explicit", "anchorQuotes": ["voice_bukui", "x_act_roar"],
        "note": "注意前值里两件事是分开的：**膝盖没弯**（不敢跪）但**腰直不起来**（跪不下去也站不起来）。"
                "这一章的动作线是「不肯跪」先于「能站直」。",
    },
    {
        "id": "S08", "who": "金刚法相（殿内那尊）", "aspect": "存亡",
        "before": "半眯着眼的金刚法相忽然睁开眼睛，随之佛光吞没许七安",
        "beforeBasis": "explicit", "beforeQuotes": ["faxiang_open"],
        "after": "佛像眉心龟裂、裂缝瞬间遍布全身，「继而崩散」",
        "afterBasis": "explicit", "afterQuotes": ["x_res_crack"],
        "anchor": "他说完「众生皆可成佛，为何跪你？」后平静地刺出刻刀",
        "anchorBasis": "explicit", "anchorQuotes": ["x_act_thrust"],
        "note": "本状态只跟踪**殿内那尊**金刚法相；殿外凝聚的擎天法相另有一毁，"
                "两者不是同一尊（擎天法相「崩裂成纯粹的金光」写在 E17）。",
    },
    {
        "id": "S09", "who": "监正", "aspect": "从蓄力到收手",
        "before": "握住酒杯、苍老的手掌青筋凸起，「似乎在蓄力」",
        "beforeBasis": "explicit", "beforeQuotes": ["jz_charge"],
        "after": "「忽然停下来，愕然眺望远方。那是云鹿书院的方向。」",
        "afterBasis": "explicit", "afterQuotes": ["e_res_jzstop"],
        "anchor": "佛像震怒、擎天法相凝聚并下按，许七安在重压下硬扛",
        "anchorBasis": "explicit", "anchorQuotes": ["refuse_anger", "palm_press"],
        "note": "「似乎在蓄力」是叙述的推测措辞，不是已发生的动作；"
                "前值因此只记可观察的体态（握杯、青筋凸起）。",
    },
    {
        "id": "S10", "who": "在场的武夫群体（江湖人士）", "aspect": "社会评价与自我感受",
        "before": "武夫长期「被各大体系鄙夷」，被看作只会凭暴力搞破坏、是九州社会的不安定因素",
        "beforeBasis": "explicit", "beforeQuotes": ["wufu_despised"],
        "after": "扬眉吐气，「恨不得仰天长啸」，并打算回乡广而告之、把许七安这个名字记进大奉江湖",
        "afterBasis": "explicit", "afterQuotes": ["wufu_spread", "wufu_name"],
        "anchor": "度厄当众尊一位武夫为师长——「许施主当为吾师」",
        "anchorBasis": "explicit", "anchorQuotes": ["teacher_line"],
        "note": "这是一条**群体评价**状态，不是个人能力状态：变的不是武夫的武力，"
                "是别人（佛门高僧）当众给出的位次；叙述自己就把这句听成「扬眉吐气」的原因。",
    },
    {
        "id": "S11", "who": "怀庆", "aspect": "心境（不动声色地盼他别跪）",
        "before": "瞳孔微有放大，心里有一个无比清晰的念头「化作两个字：不要」",
        "beforeBasis": "explicit", "beforeQuotes": ["hq_inner"],
        "after": "在众人欢呼时保持清醒，提醒「别高兴的太早，还有一尊法相呢」",
        "afterBasis": "explicit", "afterQuotes": ["hq_warn"],
        "anchor": "许七安在金身与欢呼中被当作已经过关",
        "anchorBasis": "explicit", "anchorQuotes": ["j_res_gold"],
        "note": "她的「不要」是**心理内容**，由叙述直述（不是她开口说的）；"
                "与之相对，她当众只说场面话（hq_demand/hq_warn），两者不要混。",
    },

    {
        "id": "S12", "who": "裱裱", "aspect": "情绪（焦虑→兴奋）",
        "before": "忍不住了：看不见寺庙里的景象时反而不停脑补他受害，"
                  "「『坚持住，坚持住......』裱裱碎碎念着，秀气的小手紧紧绞着裙摆」",
        "beforeBasis": "explicit", "beforeQuotes": ["b_worry"],
        "after": "兴奋尖叫「啊，狗奴才抵抗住了」，并走到凉棚外高喊要他站着",
        "afterBasis": "explicit", "afterQuotes": ["b_cheer", "b_out"],
        "anchor": "许七安松开按住貂帽的手，貂帽依旧戴在头上——她看到了他夺回自我意志",
        "anchorBasis": "explicit", "anchorQuotes": ["x_loose_hat"],
        "note": "她的焦虑与兴奋都挂在**同一个可见动作**（他有没有摘帽）上；"
                "「狗奴才」是她的称呼习惯，不是贬义判定。",
    },
]

# ── knowledgeGaps：谁知 / 谁不知 ───────────────────────────────────────
KNOWLEDGE_GAPS = [
    {
        "id": "K01", "knower": "江湖客（并在随后告知百姓）", "notKnower": "度厄罗汉与不知情的市井百姓",
        "content": "许七安化成金身不是皈依佛门，而是修成了佛门神功金刚不败",
        "basis": "explicit", "quotes": ["duer_shock", "jh_explain"],
        "note": "度厄的原话是疑问句「他，他怎么化成金身了？！」，紧跟着百姓猜「真的皈依佛门了？」；"
                "把这两句当事实就会读反这一章。",
    },
    {
        "id": "K02", "knower": "监正与叙述层", "notKnower": "度厄罗汉",
        "content": "监正放度厄讲经的真正目的是拿到金刚经——「金刚经到手，他的目的达到了」",
        "basis": "explicit", "quotes": ["jz_scripture", "duer_exult", "x_guess_jz"],
        "note": "度厄在同一时间正为「更得一位天生慧根的佛子」而畅快，"
                "双方都把这一场当成自己的收获，原文没有写度厄是否察觉监正的意图。",
    },
    {
        "id": "K03", "knower": "许七安（凭记忆）", "notKnower": "本区间的叙述未再交代度厄的原话",
        "content": "「进了寺庙，如果依旧不肯皈依佛门，那就算佛门输了」这条规则，"
                   "本区间只以许七安回忆的形式出现，不是度厄当众重述的",
        "basis": "explicit", "quotes": ["x_obj_rule"],
        "note": "引文自带「我记得度厄罗汉说过」，说明这是回忆；"
                "本区间没有第二处独立复述可以对照（见 U03）。",
    },
    {
        "id": "K04", "knower": "场外观众（画面切换之后）", "notKnower": "画面切换之前的场外观众",
        "content": "寺庙里的情形：六丈金身、度厄的许诺、许七安盘坐参悟",
        "basis": "explicit", "quotes": ["b_res_switch", "tx_liuzhang"],
        "note": "在裱裱与怀庆提出要求之前，众人只能看见佛境画面而看不见殿内；"
                "画面是度厄「宽大的袖子一挥」之后才切换的。",
    },
    {
        "id": "K05", "knower": "院长赵守（凭经验认出「又有人调动众生之力」的是李慕白）",
        "notKnower": "云鹿书院在场的学子与夫子",
        "content": "红木盒子异动的原因是外面有人调动了众生之力",
        "basis": "explicit", "quotes": ["li_mubai_q", "school_watch"],
        "note": "这句是李慕白的惊叹与推断，紧接着张慎追问「怎么回事，前辈怎么又动了」；"
                "「又」字表明这不是第一次，但本区间没有交代上一次（见 U05）。",
    },
    {
        "id": "K06", "knower": "读者（由叙述给出）", "notKnower": "许七安",
        "content": "他丹田暖流上行、看懂禅意这件事，是他自己也不明白来由的——"
                   "他的反应是疑问「是，是......在帮我？！」",
        "basis": "explicit", "quotes": ["chan_help", "understand_chan"],
        "note": "「在帮我」的主语在原文里没有出现（破折号后直接接问号与叹号），"
                "所以这条只记「他不知道是谁/什么在帮他」，不替他指定施助者。",
    },
    {
        "id": "K07", "knower": "叙述层", "notKnower": "场外围观者",
        "content": "许七安在阵中经历的是本心被改的「修罗问心」，外人只能看见他在挣扎",
        "basis": "explicit", "quotes": ["crowd_watch"],
        "note": "叙述写众人「任谁都看出了许七安在挣扎，在于『修罗问心』做抗争」——"
                "他们看出的是**挣扎**，看不出他被灌输的具体念头（那部分只写给读者）。",
    },
    {
        "id": "K08", "knower": "元景帝（听到监正应承）", "notKnower": "元景帝（不知道监正随即收手）",
        "content": "监正应下「陛下放心」之后并没有出手，真正撞入佛境的是从云鹿书院方向来的清光",
        "basis": "derived", "quotes": ["jz_nod", "e_res_jzstop", "city_direction"],
        "note": "本区间没有写元景帝是否看见监正停手，也没有写他事后如何反应；"
                "「监正没出手」是我把「颔首」与「忽然停下来」两处合起来推的（derived）。",
    },
]

# ── foreshadows：铺设 + 回收 ───────────────────────────────────────────
FORESHADOWS = [
    {
        "id": "F01", "name": "亚圣殿红木盒子里的东西",
        "setup": "斗法牵动众生之力时，亚圣殿里被四位儒者压制的红木盒子剧烈震动，"
                 "「里面的东西似乎迫切的想要出来」——先给了一个被镇住、想出来的东西。",
        "setupBasis": "explicit", "setupQuotes": ["box_hang", "box_quiet"],
        "payoff": "盒子炸散，一道清光破盒而出、破空而起，飞向京城方向，"
                  "最终落在许七安手里，是一把古朴的黑色刻刀，并用它刺碎了佛像。",
        "payoffBasis": "derived", "payoffQuotes": ["box_burst", "light_out", "zhaoshou_chase", "city_direction", "knife_desc"],
        "resolved": True,
        "note": "铺设与回收在本区间内闭合；但「盒中物 = 刻刀」是**跨场景推导**"
                "（三处都写「清光」，方位从云鹿书院指向京城），原文没有一句直说，见 E20 与 U01。",
    },
    {
        "id": "F02", "name": "貂帽",
        "setup": "心被灌顶改变后，他在众目睽睽中站起来抽刀、另一只手按在貂帽上——"
                 "叙述点明「这是要给自己剃度」，而他没有头发，摘帽就曝光。",
        "setupBasis": "explicit", "setupQuotes": ["draw_knife_hat", "tonsure_note"],
        "payoff": "羞耻感让他松手、貂帽依旧戴在头上；昏倒之前他还按住了貂帽，"
                  "叙述给出定评「这是他的尊严」。",
        "payoffBasis": "explicit", "payoffQuotes": ["x_loose_hat", "hat_press", "hat_dignity"],
        "resolved": True,
        "note": "同一个动作（按帽）在章中出现了两次、含义相反：第一次是按下去要摘（屈服），"
                "第二次是按住了不让它掉（守住尊严）。两次合起来才构成铺设与回收。",
    },
    {
        "id": "F03", "name": "「还有一尊法相呢」",
        "setup": "金身出现、众人欢呼时，怀庆沉声道：「别高兴的太早，还有一尊法相呢。」",
        "setupBasis": "explicit", "setupQuotes": ["hq_warn"],
        "payoff": "度厄随即宣布这一关叫「修罗问心」，殿内那尊半眯着眼的金刚法相忽然睁开眼睛。",
        "payoffBasis": "explicit", "payoffQuotes": ["announce_gate", "faxiang_open"],
        "resolved": True,
        "note": "她的提醒指向的是**第二尊法相**（金刚法相的另一态/修罗问心的发动），"
                "回收就在同一章的后半段；这与 R05 说的「提醒不构成触发」是两件事："
                "它是预告，不是原因。",
    },
    {
        "id": "F04", "name": "度厄许诺的金刚经（画饼）",
        "setup": "度厄当众许诺金身之中有金刚经的奥秘、参悟即可修成金刚不败；"
                 "叙述紧接着点破这是「在给他画饼，为拉拢许七安进佛门做铺垫」。",
        "setupBasis": "explicit", "setupQuotes": ["j_promise", "j_draw_cake"],
        "payoff": "许七安真的参悟了法相、化成金身，被江湖客认定为修成了金刚不败；"
                  "而监正那边「金刚经到手，他的目的达到了」。",
        "payoffBasis": "derived", "payoffQuotes": ["j_res_gold", "jh_explain", "jz_scripture"],
        "resolved": True,
        "note": "这条伏笔的回收是**反讽式**的：作为诱饵的许诺被真的兑现了，"
                "但得利的不止度厄——监正拿到了经。"
                "「画饼」是叙述的判断（explicit），「真的兑现」需要把三处合起来看（derived）。",
    },
    {
        "id": "F05", "name": "「进了此庙，便是石头，也能点化」",
        "setup": "许七安刚进殿，度厄就当众放话：「进了此庙，便是石头，也能点化，皈依佛门。」"
                 "众人随之想起本次斗法的主题就是「皈依佛门」。",
        "setupBasis": "explicit", "setupQuotes": ["duer_boast_stone", "crowd_frown"],
        "payoff": "他不但没有被点化，反而在佛掌下喊出「不跪」、用刻刀刺碎佛像，"
                  "佛境幻灭收场。",
        "payoffBasis": "explicit", "payoffQuotes": ["x_obj_will", "x_res_crack"],
        "resolved": True,
        "note": "严格说这是一句**被原文反向兑现的大话**，不是埋设的线索；"
                "我把它列进来是因为它确实有「铺设（预期）→ 回收（预期落空）」的完整结构，"
                "但它的性质与 F01/F02 那种物件伏笔不同。如果复核认为「大话被推翻」不算伏笔，"
                "应把它移到 notForeshadows。",
    },
    {
        "id": "F06", "name": "盒中之物的来历与身份（未回收）",
        "setup": "红木盒子「里面不知封印着什么东西，似乎要破盒而出」；"
                 "它为什么会在众生之力被牵动时暴动、为什么被封在亚圣雕像头顶，本区间都没有交代。",
        "setupBasis": "explicit", "setupQuotes": ["box_hang", "li_mubai_q"],
        "payoff": None,
        "payoffBasis": None, "payoffQuotes": [],
        "resolved": False,
        "note": "**显式标为未回收**：本区间只写到它破盒而出、化作刻刀落在许七安手里，"
                "刻刀是什么、盒中物与亚圣/书院是什么关系，都没有在下文回收（见 U01）。",
        "unresolved": True,
    },
    {
        "id": "F07", "name": "净思的昏迷（未回收）",
        "setup": "佛境幻灭后「两道身影跌出」，其中一个是「昏迷不醒的净思」；"
                 "他此前的对手戏在本区间没有交代。",
        "setupBasis": "explicit", "setupQuotes": ["x_res_two"],
        "payoff": None,
        "payoffBasis": None, "payoffQuotes": [],
        "resolved": False,
        "note": "**显式标为未回收**：本区间只给出他昏迷跌出的结果，"
                "没有写他何时/为何昏迷，也没有写他醒来（见 U07）。",
        "unresolved": True,
    },
]

# ── notForeshadows：看着像伏笔但不是 ──────────────────────────────────
NOT_FORESHADOWS = [
    {
        "name": "「教坊司花魁们传授的一百零八种招式」",
        "whyNot": "只在进殿前出现一次，作用是解释他如何「污浊内心」以免被度化，"
                  "本区间没有回收，也没有第二次出现 ⇒ 一次出现不叫伏笔。",
        "quotes": ["x_dirty_mind"],
    },
    {
        "name": "「教坊司的常客」",
        "whyNot": "美妇人打探来的一句话，用来支撑她说媒的理由；"
                  "本区间既没有第二处呼应，也没有指向后文的线索 ⇒ 不记伏笔。",
        "quotes": ["meifu_probe"],
    },
    {
        "name": "楚元缜对恒远说「晋升三品金刚，也不是不可能」",
        "whyNot": "这是对未来的预测（且预测的依据由叙述写成楚元缜的推断），"
                  "本区间没有发生任何与三品金刚有关的事 ⇒ 预测不是伏笔；"
                  "恒远那句「金刚神功........」只是羡慕的接话。",
        "quotes": ["chu_pat", "chu_advice", "heng_yuan"],
    },
    {
        "name": "许铃音喊的「大锅」",
        "whyNot": "童言（「大哥」的讹音），由魏渊替她补完；"
                  "它在本区间只承担喊话作用，没有后续回收 ⇒ 不记伏笔。",
        "quotes": ["xu_lingyin"],
    },
    {
        "name": "「一尊六丈金身盘坐，头顶几乎触到殿顶」",
        "whyNot": "这是对殿内法相尺度的描写，用来衬托后文「寺庙还没有法相手掌大」的对比；"
                  "它本身没有被回收成情节（被刺碎的是佛像本体，不是这个尺寸的伏笔） ⇒ 不记伏笔。",
        "quotes": ["tx_liuzhang"],
    },
]

# ── worldSettings：只收影响行动/资源/约束/后果的明确设定 ─────────────────
WORLD_SETTINGS = [
    {
        "id": "W01", "kind": "rule",
        "name": "斗法主题「皈依佛门」与寺庙这一关的胜负条件",
        "quote": "convert_theme",
        "explain": "它解释了双方在场上的行动边界：西域使团要的不只是赢天机盘，"
                   "还要让斗法者皈依佛门以「狠狠打大奉颜面」；"
                   "而对许七安来说，进了寺庙仍不肯皈依就算佛门输了。"
                   "两边对这最后一关的目标正好相反，所以度厄必须逼他跪、他必须不跪。",
        "basis": "explicit", "institution": "declared",
        "extraQuotes": ["x_obj_rule", "crowd_frown"],
        "note": "胜负条件在原文里以许七安回忆「我记得度厄罗汉说过」的形式出现，"
                "本区间没有度厄本人的当众复述 ⇒ declared（只有约定，本区间无对应的执行动作）。",
    },
    {
        "id": "W02", "kind": "rule",
        "name": "「修罗问心」的效果：如佛陀度修罗族，强改本心",
        "quote": "infer_effect",
        "explain": "它解释了许七安**不能**靠武力过关：这一关不是比招式，而是改本心——"
                   "佛光「在瞬间压垮了他的意志，改变了他的内心」，"
                   "压力「迫使他下跪」，跪下就再没有回头路。"
                   "许七安能做的只剩抗住，而抗住需要外力（见 W05）。",
        "basis": "derived", "institution": "executed",
        "extraQuotes": ["legend_endure", "legend_cut1", "legend_cut2", "legend_gold", "infer_worse", "crush_will", "x_obs_press", "x_obs_nokneel"],
        "note": "效果由**人物**（王首辅等权臣）据典故外推得出（「那效果必然是与佛陀度化修罗族是一样的」），"
                "但它在本区间被真正执行了（法相睁眼、佛光灌顶、佛掌下按），故记 executed；"
                "推断部分记 derived。",
    },
    {
        "id": "W03", "kind": "rule",
        "name": "金刚神功的门槛：只适合武僧，不到罗汉境掌握不了",
        "quote": "rule_jg_monk",
        "explain": "它解释了度厄为什么拿金刚经当诱饵：这门神功对僧人是门槛（要罗汉境），"
                   "对武夫却是可以直接补上短板的东西——所以「画饼」正好画在许七安的痒处。"
                   "它同时解释了为什么在场武夫会「双眼骤放光明」。",
        "basis": "explicit", "institution": "declared",
        "extraQuotes": ["j_draw_cake", "wufu_gaze"],
        "note": "叙述直接给出这条门槛，但本区间没有任何**执行**这条限制的动作"
                "（没有僧人因不到罗汉境而修习失败的情节） ⇒ declared，不记 executed。",
    },
    {
        "id": "W04", "kind": "rule",
        "name": "众生之力可被呼唤、并「应召而来」",
        "quote": "yingzhao",
        "explain": "它是这一章的破局设定：许七安在识海里感觉到众生之力涌入、"
                   "听到「不跪」，同时抬起手臂像是要握住什么，"
                   "叙述随即写明那道撞入佛境的清光「应召而来」。"
                   "这条设定让他不必靠自己扛住灌顶——呼唤本身构成了通路。",
        "basis": "explicit", "institution": "executed",
        "extraQuotes": ["p_res_sense", "voice_bukui", "raise_arm"],
        "note": "「众生之力」的定义与它为何能对抗佛法，本区间没有解释（见 U02）；"
                "记 executed 是因为它在同一段里被真正用上了。",
    },
    {
        "id": "W05", "kind": "place",
        "name": "山顶寺庙（独栋、一字型屋脊、只有主殿）",
        "quote": "temple_desc",
        "explain": "最后一关的场地：他拾阶而上、穿过小广场进殿，殿内就是一尊六丈金身；"
                   "「就一个主殿」的空间设置让殿内的一切都发生在佛像面前，"
                   "也让场外只能靠度厄切换画面才能看见里面。",
        "basis": "explicit", "placeState": "arrived",
        "extraQuotes": ["x_climb", "tx_liuzhang"],
        "note": "到达动作明确：「一直走到台阶尽头，踏入山顶寺庙外的小广场」，随后推门进殿。",
    },
    {
        "id": "W06", "kind": "place",
        "name": "云鹿书院亚圣殿（红木盒子所在）",
        "quote": "yasheng_shake",
        "explain": "众生之力被牵动的另一端：亚圣雕像头顶的红木盒子在这里，"
                   "院长赵守与三位大儒在这里压制它、被震飞，破盒而出的清光也从这里起飞。"
                   "没有这个地点，撞入佛境的清光就没有来处。",
        "basis": "explicit", "placeState": "arrived",
        "extraQuotes": ["yunlu_name", "school_watch"],
        "note": "到达动作明确：院长赵守与三位大儒「同时出现」在殿内，"
                "赵守随后「追出亚圣殿」。",
    },
    {
        "id": "W07", "kind": "place",
        "name": "观星楼顶（元景帝观战并发令处）",
        "quote": "jz_table",
        "explain": "皇帝在这场斗法中的位置：他在这里「猛的回身，指着秘境中的许七安」"
                   "向监正下令阻止。它把最高权力的介入固定在同一个观战点上。",
        "basis": "explicit", "placeState": "arrived",
        "extraQuotes": ["jz_cup"],
        "note": "到达动词未写，但驻守动作明确（回身、指着秘境、握着酒杯、随后「忽然停下来，愕然眺望远方」），"
                "判为 arrived；判定依据写在这里以免与「提及≠到达」混淆。",
    },
    {
        "id": "W08", "kind": "item",
        "name": "红木盒子（亚圣雕像头顶，封印物）",
        "quote": "box_hang",
        "explain": "它是清光的来源：被四位儒者压制却越震越烈，最终炸散。"
                   "它解释了为什么佛境里的破局之物来自云鹿书院而不是监正的手。",
        "basis": "explicit", "itemStates": ["lose", "use"],
        "extraQuotes": ["box_burst", "s_act"],
        "note": "四态分开写：**lose**（原文「红木盒子炸散」，即失去）与 "
                "**use**（四位儒者「鼓荡浩然正气，与院长赵守联手，压制红木盒子」，把它当作要压制的对象）。"
                "本区间没有写它易手（无 transfer）、也没有写许七安持有它（无 hold），故不凑另两态。",
    },
    {
        "id": "W09", "kind": "item",
        "name": "刻刀（古朴的黑色刻刀）",
        "quote": "knife_desc",
        "explain": "它是这一章的落点武器：那道清光入庙后「落在许七安手里」，"
                   "形状是一把古朴的黑色刻刀；他用它刺碎佛像，晕倒前还握着。"
                   "它把「众生之力」这条抽象设定变成了一个可以握在手里的东西。",
        "basis": "explicit", "itemStates": ["transfer", "hold", "use"],
        "extraQuotes": ["faxiang_beng", "x_res_stand", "x_act_thrust"],
        "note": "三态分开写：**transfer**（「落在许七安手里」，从清光/盒中物易手到他）、"
                "**hold**（「握紧了刻刀」）、**use**（「平静的刺出了刻刀」）。"
                "原文用「落在……手里」，照原文写，不改写成现代汉语的「获得」。",
    },
    {
        "id": "W10", "kind": "item",
        "name": "金钵（度厄的法器，佛境的容器）",
        "quote": "bowl_dust",
        "explain": "它把阵内的胜负显示到场外：佛境幻灭的同时，度厄低头看见自己的金钵"
                   "「裂开一道道缝隙」并炸成齑粉。它解释了为什么场外能看见斗法结束——"
                   "容器碎了，佛境才随之幻灭。",
        "basis": "explicit", "itemStates": ["hold", "lose"],
        "extraQuotes": ["realm_vanish", "x_res_two"],
        "note": "四态分开写：**hold**（度厄身边的金钵，他「愕然低头」看见它）与 "
                "**lose**（「炸成齑粉」）。"
                "「金钵是佛境的容器」这一点是**推导**：原文把「佛境幻灭」与「金钵炸成齑粉」"
                "写在相邻两句，没有一句直说容器关系（见 U08）。",
    },
    {
        "id": "W11", "kind": "item",
        "name": "貂帽",
        "quote": "draw_knife_hat",
        "explain": "它是许七安「本心有没有被改」的可见标记：心被改时他站起来要摘帽剃度；"
                   "找回自我后帽「依旧戴在头上」；昏倒前还按住它，叙述说「这是他的尊严」。"
                   "它解释了为什么这一章可以用一个帽子动作代替心理描写。",
        "basis": "explicit", "itemStates": ["hold"],
        "extraQuotes": ["x_loose_hat", "hat_press"],
        "note": "只记 **hold**（戴在头上、按住）。它一度要被摘下但没有摘下，"
                "本区间没有写它易手或丢失 ⇒ 不记 transfer/use/lose。",
    },
    {
        "id": "W12", "kind": "place",
        "name": "西域（佛门所在）",
        "quote": "legend_head",
        "explain": "它给这一场斗法定了量级：佛陀在西域开宗立派、修罗族占据西域的典故"
                   "是「修罗问心」这一关名字的来处，度厄也是从西域来访大奉的使团一方。"
                   "它解释了为什么这一关会被命名为佛门典故里的一场。",
        "basis": "explicit", "placeState": "mentioned",
        "extraQuotes": ["duer_exult"],
        "note": "本区间西域只在**典故与来处**里被提到（「佛陀在西域开宗立派之时」「贫僧来访大奉」），"
                "没有任何人在本区间到达或驻守西域 ⇒ mentioned，不记 arrived。",
    },
]

# ── notWorldSettings：看着像设定但不收 ────────────────────────────────
NOT_WORLD_SETTINGS = [
    {
        "name": "「皇室专属的颜色」",
        "whyNot": "这是叙述的诙谐说法（借「黄」色指代心中所想），"
                  "作用是写他如何刻意污浊内心，不构成能约束行为、资源或后果的世界规则；"
                  "它也没有在下文被任何行动调用 ⇒ 不收，避免扩出术语装饰层。",
        "quotes": ["x_dirty_mind"],
    },
    {
        "name": "「天机盘」",
        "whyNot": "本区间只在赌注里被提到两次（「要赢天机盘」「哪怕输了天机盘」），"
                  "既没有写它的形态、归属或转移，也没有写赌局的实际结算 ⇒ 不收为 item；"
                  "把它写成物品链会是无依据的扩写。",
        "quotes": ["convert_theme", "e_act_order"],
    },
    {
        "name": "「修罗族」与「修罗」这一族名",
        "whyNot": "它出现在度厄讲的典故里，作用已经由 W02 收为「这一关的效果设定」；"
                  "再单列一条族名只会变成术语装饰 ⇒ 不另收。",
        "quotes": ["legend_kill", "legend_head"],
    },
    {
        "name": "「大乘佛法 / 小乘」",
        "whyNot": "本区间提到「化小乘为大乘」「大乘佛法的开创者」等，"
                  "它们解释的是**度厄为什么非要度许七安**（已写进 T01.objective 的依据），"
                  "本身没有构成对行动的新约束 ⇒ 不重复收为规则。",
        "quotes": ["j_founder"],
    },
]

# ── themeReadings：解释层，各带反证 ────────────────────────────────────
THEME_READINGS = [
    {
        "id": "TH1",
        "perspective": "以「谁有权让人跪下」为轴读这一章：把佛门这一关读成一次**改本心的强制**，"
                       "而「不跪」不是一个人的倔强，是全场共同发出的声音。",
        "support": [
            {"event": "佛门的手段落在改变本心与迫使他下跪上：佛光「改变了他的内心」，"
                      "压力「迫使他下跪」，他自己判定这一跪「就再没有回头路了」",
             "quotes": ["crush_will", "x_obs_press", "x_obs_nokneel"]},
            {"event": "「不跪」从凉棚传到场外、从贵族传到百姓，成为在场大奉子民的共同声音",
             "quotes": ["p_act_voice", "p_act_many", "wang_line"]},
            {"event": "他最后的判词把问题直接指向「跪」的正当性：「众生皆可成佛，为何跪你？」",
             "quotes": ["x_line_why", "x_act_thrust"]},
        ],
        "counter": [
            {"event": "反证一：这一关之前，度厄并不是靠压迫取胜的——他当众认输、尊许七安为师，"
                      "还拿金刚经当诱饵；「强制」只出现在最后一关，用它概括整个佛门手段会读偏",
             "quotes": ["teacher_line", "j_promise"]},
            {"event": "反证二：「不跪」的声浪里混着等级秩序的话语（「大奉武者，不跪」「大奉子民，不跪」），"
                      "把它读成纯粹的个人反抗，会漏掉它同时是一次集体身份宣言",
             "quotes": ["wang_line", "husband_wife"]},
        ],
        "note": "这条解释只用**具体场景与台词**支撑，没有用事件密度、死亡人数或篇幅中点来定义「高潮」；"
                "两处反证都是原文里同样明确的文字，故并列写出而不压成一条唯一真相。",
    },
    {
        "id": "TH2",
        "perspective": "以「力量的来源与解释权」为轴读（承接上一章「众生之力」的线）："
                       "破关的力量是借来的，而同一件事被三拨人分别解释成三种东西。",
        "support": [
            {"event": "力量的来路被写成「应召而来」的外部之物，而不是他自己的修为："
                      "众生之力涌入识海，清光撞入佛境并化作刻刀",
             "quotes": ["p_res_sense", "qingguang_in", "knife_desc"]},
            {"event": "同一具金身被三种说法争夺：度厄问「他怎么化成金身了」，"
                      "百姓猜「真的皈依佛门了」，江湖客断言是修成金刚不败",
             "quotes": ["duer_shock", "convert_misread", "jh_explain"]},
            {"event": "监正那条线的说法最冷：他把这一场结算成一件东西——「金刚经到手，他的目的达到了」",
             "quotes": ["jz_scripture", "jz_need_force"]},
        ],
        "counter": [
            {"event": "反证一：落点那一刀并不依赖任何解释——他「平静的刺出了刻刀」，"
                      "佛像就碎了；把这一章全读成「解释权之争」会盖掉这个不需要旁白的动作",
             "quotes": ["x_act_thrust", "x_res_crack"]},
            {"event": "反证二：「应召而来」的措辞把清光写成对他呼唤的回应，"
                      "这支持的是「他召唤了力量」，而不是「他被别人安排了力量」——"
                      "若采信后者，监正停手那一段就白写了",
             "quotes": ["yingzhao", "e_res_jzstop"]},
        ],
        "note": "两种读法（TH1 的「强制与反抗」、TH2 的「借力与解释权」）建立在同一批事实上，"
                "并列比压成一条更贴近原文；每条都带不利证据。",
    },
]

# ── speechAsClueNotFact：人物话语不是叙述事实 ──────────────────────────
SPEECH_AS_CLUE = [
    {"who": "度厄罗汉", "said": "「许施主当为吾师。这第三关，是你胜了。」",
     "whyNotFact": "这是当众认输的场面话，不等于叙述判定许七安在佛法上胜过了他；"
                   "同一段里他立刻把战线推进到下一关（宣布「修罗问心」）。",
     "quotes": ["teacher_line", "announce_gate"]},
    {"who": "度厄罗汉", "said": "「进了此庙，便是石头，也能点化，皈依佛门。」",
     "whyNotFact": "是一句夸口，随后被原文反向兑现（没人被点化，佛像反被刺碎）⇒ 记为人物话语，不作预告。",
     "quotes": ["duer_boast_stone", "x_res_crack"]},
    {"who": "江湖客打扮的男人", "said": "「偷鸡不成蚀把米」「假以时日，未必不能超越镇北王，成为大奉第一武者」",
     "whyNotFact": "是围观者的喝彩与**揣测**；「超越镇北王」本区间没有任何依据，"
                   "紧跟着还有一位妇人明确不信（「骗人的」）⇒ 只作现场舆论的线索。",
     "quotes": ["jh_explain", "hu_furen_doubt"]},
    {"who": "许新年", "said": "「我在想应该从哪个角度捅他一刀。」",
     "whyNotFact": "是他对姑母问话的玩笑式回答（他一直在盯度厄看）；"
                   "本区间没有他真的动手，不能当成立志或计划。",
     "quotes": ["xinnian_stab", "xinnian_stare"]},
    {"who": "美妇人", "said": "「为师打探过了，这位许大人........嗯，是教坊司的常客。」",
     "whyNotFact": "是「打探」得来的说法，用来支撑她说媒的理由；叙述没有独立确认过。",
     "quotes": ["meifu_probe"]},
    {"who": "元景帝", "said": "「不管用什么办法，你一定要阻止。」「哪怕输了天机盘。」",
     "whyNotFact": "是命令与条件授权，本区间没有对应的执行动作（监正只颔首，随后停手）"
                   "⇒ 不能当成已发生的事。",
     "quotes": ["e_order2", "jz_nod", "e_res_jzstop"]},
    {"who": "张巡抚", "said": "「能写出这种词的人，不跪！」",
     "whyNotFact": "是他从词句推出的称赞与判断，不是对许七安会不会跪的叙述判定。",
     "quotes": ["zhang_ci"]},
    {"who": "裱裱", "said": "「谁知道你们佛门在里头设了什么龌龊伎俩，坑害我大奉的银锣。」",
     "whyNotFact": "是她的猜疑（叙述自己写明她「反而不停脑补」），"
                   "本区间没有写出任何佛门暗算的情节。",
     "quotes": ["b_suspect", "b_obs"]},
    {"who": "李慕白", "said": "「又有人调动众生之力？」",
     "whyNotFact": "是惊叹与推断，且用的是疑问句；「有人」是谁本区间没有交代（见 U05）。",
     "quotes": ["li_mubai_q"]},
    {"who": "楚元缜", "said": "「回头找许宁宴讨要金刚不败，你的武僧之路，能走得更远，晋升三品金刚，也不是不可能。」",
     "whyNotFact": "是对恒远前途的预测，依据由叙述写成楚元缜自己的推断；本区间没有兑现。",
     "quotes": ["chu_advice"]},
    {"who": "监正", "said": "「陛下乃九五之尊，区区一个银锣，不必在乎。」",
     "whyNotFact": "是他的回话，与他自己随后「青筋凸起，似乎在蓄力」的行动相反"
                   "⇒ 人物的宽慰话不能读成他的真实判断。",
     "quotes": ["e_obs_jz", "jz_charge"]},
    {"who": "许七安", "said": "「我是大乘佛法的开创者，佛门更适合我发展。」",
     "whyNotFact": "这是**灌顶塞进来的念头**（叙述写「一个个念头闪过，诉说着佛门的种种好处」），"
                   "不是他的真实立场，也不是叙述事实。",
     "quotes": ["inner_voice_1", "x_obs_heart"]},
]

# ── textualNotes：文本现象（不是内容结论）──────────────────────────────
TEXTUAL_NOTES = [
    {"note": "「铿锵之身」：写刀砍进血肉却发出金属声，当作「铿锵之声」；原文作「身」，"
             "照原文引用不改字。",
     "quotes": ["tx_kengqiang"]},
    {"note": "「大风佛法理念」：同一段前文三处都作「大乘佛法」，此处作「大风」，"
             "应为笔误；引用时照原文。",
     "quotes": ["tx_dafeng_fa"]},
    {"note": "「越来越的多的人」：语序异常（应为「越来越多的人」），照原文引用。",
     "quotes": ["tx_many_de"]},
    {"note": "「爆发出一身尖锐的叫声」：「一身」应为「一声」，照原文引用。",
     "quotes": ["tx_yishen"]},
    {"note": "「心里像是恰了柠檬似」：「恰」是网络用法（吃），照原文引用。",
     "quotes": ["tx_ningmeng"]},
    {"note": "「一尊六丈金身盘坐，头顶几乎触到殿顶」与后文「寺庙还没有法相手掌大」"
             "形成尺度对比：殿内的金身是六丈，殿外凝聚的擎天法相大到寺庙不及其手掌——"
             "两处尺度不是同一尊，读的时候要分开。",
     "quotes": ["tx_liuzhang", "realm_scale"]},
    {"note": "「...........」这类纯省略号段落是场景切换标记（原文以单独一行出现），"
             "本候选用它切分场景，但不把它当叙事内容。",
     "quotes": ["tx_fenge"]},
    {"note": "叙述的称谓习惯：说话人常先用身份/无名称呼写完整句，随后单独一段补出姓名"
             "（如张巡抚的高喊之后单起一段「张巡抚。」）。本候选据此把「张巡抚」认定为说话人；"
             "这类单名段落是**称谓**，不是动作。",
     "quotes": ["zhang_name", "zhang_rise"]},
]

# ── authorRegionEvidence：作者区域内的引文 ────────────────────────────
AUTHOR_REGION_EVIDENCE = [
    {"note": "场外留言：感谢两位盟主打赏并问其中一位是否改过名——与叙事无关。",
     "quotes": ["au_ps"]},
    {"note": "场外说明：作者交代自己码字时睡着、白天没补觉、勉强写出大章；"
              "这类「写了多少」的自述不构成任何叙事证据。",
     "quotes": ["au_night"]},
    {"note": "文末分隔线「------------」：与正文之间空两行，是章节结束标记，不是叙事内容。",
     "quotes": ["au_rule"]},
]

# ── unknowns：读不出来或矛盾的地方 ────────────────────────────────────
UNKNOWNS = [
    {"id": "U01", "text": "红木盒子里封印的究竟是什么、与亚圣/云鹿书院是什么关系、"
                          "为何会在众生之力被牵动时暴动，本区间都没有说明；"
                          "只知道它破盒而出后成为一把刻刀、落在许七安手里（这一步还是跨场景推导）。",
     "quotes": ["box_hang", "knife_desc"]},
    {"id": "U02", "text": "「众生之力」为什么能破「修罗问心」这一关，本区间没有给出任何机制；"
                          "原文只写他感觉到它、听到「不跪」，以及清光「应召而来」。",
     "quotes": ["p_res_sense", "yingzhao"]},
    {"id": "U03", "text": "「进了寺庙若不肯皈依就算佛门输」这条规则在本区间只以许七安回忆的形式出现，"
                          "没有度厄或监正的第二处独立复述可以对账。",
     "quotes": ["x_obj_rule"]},
    {"id": "U04", "text": "度厄拿金刚经当诱饵（叙述判定为「画饼」），"
                          "但许七安确实修成了金身、监正也「金刚经到手」——"
                          "经到底算被谁得去、度厄的诱饵是否落空，本区间没有结算。",
     "quotes": ["j_draw_cake", "j_res_gold", "jz_scripture"]},
    {"id": "U05", "text": "云鹿书院红木盒子的异动被李慕白称为「又有人调动众生之力」，"
                          "「又」与「有人」都指向此前发生过同类事件，但本区间没有交代上一次是谁、何时。",
     "quotes": ["li_mubai_q", "zhang_shen"]},
    {"id": "U06", "text": "那道帮许七安看懂禅意的力量是谁/什么，原文没有指明："
                          "他的反应是疑问「是，是......在帮我？！」——主语在原文里缺失。",
     "quotes": ["chan_help"]},
    {"id": "U07", "text": "净思为何昏迷不醒、他与这一关是什么关系，本区间没有交代；"
                          "他只以「昏迷不醒的净思」的结果状态出现一次。",
     "quotes": ["x_res_two"]},
    {"id": "U08", "text": "金钵与佛境的容器关系没有被明说：原文把「佛境随之幻灭」与"
                          "「金钵……炸成齑粉」写在相邻两句，但哪一个是因、哪一个是果，"
                          "或者两者同因，本区间没有交代。",
     "quotes": ["realm_vanish", "bowl_dust"]},
    {"id": "U09", "text": "许七安的伤势后续如何（肩膀血肉模糊、颈椎弯曲、昏厥）本区间没有写；"
                          "他醒来是下一章的事。",
     "quotes": ["x_cost_wound", "x_cost_faint"]},
    {"id": "U10", "text": "天机盘的赌局结局本区间没有结算：西域使团「要赢天机盘」，"
                          "元景帝说「哪怕输了天机盘」，但佛境幻灭之后谁赢了这个赌注没有写。",
     "quotes": ["convert_theme", "e_act_order"]},
    {"id": "U11", "text": "「修罗问心」这一关到底算谁过：度厄没有宣布输赢，"
                          "叙述只写佛境幻灭、金钵碎裂、许七安傲然而立；"
                          "斗法是否就此结束、后面还有没有关次，本区间没有交代。",
     "quotes": ["realm_vanish", "duer_shock"]},
    {"id": "U12", "text": "围观者中「许新年身边」那位姿色平庸的妇人与「许新年身边，听到这句话的妇人」"
                          "是否为同一人、她与许家的关系，本区间没有交代（她只留下「骗人的」这句判断）。",
     "quotes": ["hu_furen_ear", "hu_furen_doubt"]},
    {"id": "U13", "text": "殿外那道被清光击溃的「擎天法相」与殿内被刻刀刺碎的佛像是不是同一尊，"
                          "原文没有明说：一处写「崩裂成纯粹的金光，归于这片佛境」，"
                          "另一处写「佛像眉心龟裂……继而崩散」。",
     "quotes": ["faxiang_beng", "x_res_crack"]},
]

# ── selfCritique：本段我最可能读错的三处（按要求给三处以上）────────────
SELF_CRITIQUE = [
    "最可能读错的一处：把**度厄的「画饼」与许七安真的拿到金刚不败**当成同一件事。"
    "叙述明说度厄「这是在给他画饼，为拉拢许七安进佛门做铺垫」，"
    "可许七安确实化成了金身，监正也确实「金刚经到手」。"
    "我仍把 T07 的 result 记成「他看懂了、成了金身」（有直接动作与结果），"
    "并把「经归谁」写进 U04，因为本区间没有结算；如果复核认为「画饼」意味着他其实什么也没得到，"
    "T07.result 应降为 derived 或 partial。",

    "第二处：T08 的 cost 我用了「震的京城百姓抱头鼠窜」。它是**交锋的后果**，"
    "不是百姓为自己的行动付出的自愿代价；我仍把它记成 cost，"
    "理由是这一栏问的是「付出什么」，而在场百姓确实是这一轮行动的受损方。"
    "如果复核要求 cost 必须是行为主体主动付出之物，T08.cost 应改为 null 并写 costNote。",

    "第三处：E20（云鹿书院清光 → 许七安手里的刻刀）是**跨三个场景的推导**，"
    "原文没有一句直说「刻刀就是盒中之物」。我据三处都写作「清光」"
    "以及方位从云鹿书院指向京城来连这条边，并降为 derived、写进 U01。"
    "若复核认为这属于「时间相邻当因果」的变体，E20 应删除，"
    "F01 的 payoff 也要相应改标 unresolved。",

    "第四处：W07（观星楼顶）记 arrived，依据是「猛的回身」「指着秘境」这样的驻守动作，"
    "原文没有到达动词。这与「提及≠到达」的从严口径有张力；"
    "我判它是「人在此处并且在此处行动」而非「图谋某地」，"
    "但如果复核要求必须有到达动词，W07 应降为 mentioned。",

    "第五处：F05（「进了此庙，便是石头，也能点化」）我列成了伏笔（被反向兑现的大话）。"
    "它确实有铺设与回收的结构，但与 F01/F02 那种物件伏笔性质不同。"
    "我在它的 note 里已经写明这一保留；若复核认为大话被推翻不算伏笔，应移到 notForeshadows。",

    "第六处（关于覆盖）：本区间有两段我**没有**单列任务五元组——"
    "P120 前后风韵犹存的妇人向蓉蓉说媒（我列了 T09）、"
    "以及 P236 前后楚元缜在酒楼顶对恒远说金刚神功那几句（对象是恒远的武僧前途，"
    "本区间只有建议没有行动）。如果复核认为后者也构成一条任务（楚元缜想要恒远晋升三品金刚），"
    "请指出，我按原文补；我没有把它硬凑成任务，是因为那几句里没有可核验的行动与结果。",

    "第七处：本候选的 causeEdges 中 E05/E13/E16/E19/E20/E23 标为 derived。"
    "它们都至少有一处原文措辞是**人物判断或叙述的推测**"
    "（「似乎引来了佛像的震怒」「似乎在蓄力」「应召而来」）。"
    "我选择保留并降级，而不是删掉——因为删掉会让机制链断开。"
    "如果复核的口径是「推测措辞不能支撑因果边」，这六条应一并删除并写进 unknowns。",
]
