# -*- coding: utf-8 -*-
"""第六十六章 不跪 —— 内容分区（人工精读结论，全部用引文键引用原文）。

规则：
  · 每条断言给 basis ∈ {explicit, inferred, derived, unverified}；
  · tasks[] 的五栏**各自**带 quotes，栏间不共用同一引文键（构建期强断言）；
  · 某栏在本区间确实没有依据 ⇒ 该栏 None，并给同名 <栏>Note 说明为什么；
  · 引文键必须存在于 quotes_0295.QUOTES，构建期逐个解析成 {quote,start,end,sourceHash,kind}。
"""

# ═══════════════════════════════════════════════════════════════════════
# 1. tasks[] —— 任务五元组（objective / obstacle / action / result / cost）
# ═══════════════════════════════════════════════════════════════════════
TASKS = [
    dict(
        id="T01", who="度厄罗汉",
        objective=dict(basis="explicit", quotes=["jd_motive_a", "jd_motive_b"], text=(
            "把许七安度入空门、收为佛门弟子。叙述把他的动机写成两层：惜才（「一位天生慧根的佛子」），"
            "以及他要做「大乘佛法的奠基人」——许七安是大乘佛法的开创者，把他收进门才能彰显「正统」。")),
        objectiveNote=None,
        obstacle=dict(basis="explicit", quotes=["dh_frown_a"], text=(
            "许七安「有大佛根」却「执迷不悟」；度厄罗汉此时能做的手段只剩下言语劝诱，"
            "而这句话本身就是劝诱失败后的反应（「皱了皱眉，摇头道」）。")),
        obstacleNote=None,
        action=dict(basis="inferred", quotes=["jd_bait_a", "jd_offer_a"], text=(
            "以金刚经为饵拉拢：先当众宣称「金刚经的奥秘就在金身之中……便可修成佛门金刚不败」，"
            "叙述随即点明这个许诺的性质是「画饼，为拉拢许七安进佛门做铺垫」。"
            "注意「画饼」是叙述的判断，不是度厄罗汉自己的说法。")),
        actionNote=None,
        result=dict(basis="explicit", quotes=["ql_bowl_a", "ql_end_a"], text=(
            "未达成，且法器损毁：他自己的金钵「裂开一道道缝隙……炸成齑粉」，佛境随之幻灭。"
            "本区间没有任何一句写他改口认输或宣布佛门落败，所以只写到「度化失败 + 金钵毁」为止。")),
        resultNote=None,
        cost=None,
        costNote=("本区间未出现度厄罗汉为这次度化付出可辨认代价的描写。金钵炸裂写在 result（度化失败）一侧，"
                  "原文没有把它写成「他因此损失了什么」的代价陈述，也没有任何叙述句说明他因本关受罚、受损或失去资格。"
                  "不把 result 里的损毁改写成 cost。"),
    ),
    dict(
        id="T02", who="许七安（不跪这条主线）",
        objective=dict(basis="explicit", quotes=["bx_oath_a"], text=(
            "不接受被强迫的信佛：跪下去就再没有回头路；要信也只能是「我心甘情愿的信」，"
            "「谁都不能驯服我」。")),
        objectiveNote=None,
        obstacle=dict(basis="explicit", quotes=["bx_kneel_a"], text=(
            "佛掌下压带来的肉体压力直接迫使他下跪——这是外力，不是他自己的意愿动摇。")),
        obstacleNote=None,
        action=dict(basis="explicit", quotes=["ql_shout_a"], text=(
            "吼出「我！许七安，不！跪！」。叙述把这句话写成「京城成千上万百姓的心声」，"
            "即此刻他的发声与场外同声，但发声本身仍是他的动作。")),
        actionNote=None,
        result=dict(basis="explicit", quotes=["ql_stand_a"], text=(
            "直起腰杆并握紧刻刀。注意这只写到本区间的直接目标（站起来、手里有刀），"
            "不是「全书胜利」，也不等于佛门正式认输——他随即昏了过去。")),
        resultNote=None,
        cost=dict(basis="explicit", quotes=["nk_blood_a"], text=(
            "身体代价：「肩膀血肉模糊，颈椎以诡异的角度弯曲」，且这痛苦被场外众人清晰看见"
            "（即代价包含当众受辱这一层）。")),
        costNote=None,
    ),
    dict(
        id="T03", who="监正",
        objective=dict(basis="explicit", quotes=["jz_goal_a"], text=(
            "取金刚经。叙述用「金刚经到手，他的目的达到了」把这件事写成已经完成的目的；"
            "同段还写他为「修罗问心」这一关备了后手（必须有外力才能阻止）。")),
        objectiveNote=None,
        obstacle=dict(basis="explicit", quotes=["jz_need_a"], text=(
            "「修罗问心」这一关单凭许七安自己绝对扛不住佛法灌顶，必须由外力介入——"
            "即他判断自己必须出手，但原文没有写他出手要付什么代价。")),
        obstacleNote=None,
        action=dict(basis="inferred", quotes=["jz_cup_a", "jz_power_a"], text=(
            "握杯蓄力。叙述只写他握住酒杯、手掌「青筋凸起，似乎在蓄力」——"
            "带「似乎」，具体要施展什么法术本区间未写明，所以我只记到「蓄力」为止。")),
        actionNote=None,
        result=dict(basis="explicit", quotes=["jz_stop_a"], text=(
            "中途停手：他「忽然停下来，愕然眺望远方。那是云鹿书院的方向」。"
            "最终破局的是从书院飞来的清光，不是他这一手——本区间没有写他再出手。")),
        resultNote=None,
        cost=None,
        costNote=("本区间未出现监正付出代价的描写。「停下来」是动作的中止，不是损失；"
                  "原文没有写他因此受损、失算受罚或消耗了什么。不把「停手」当代价。"),
    ),
    dict(
        id="T04", who="元景帝",
        objective=dict(basis="explicit", quotes=["em_turn_a"], text=(
            "不允许许七安遁入空门、成为佛家弟子，并要求监正出手阻止。")),
        objectiveNote=None,
        obstacle=dict(basis="explicit", quotes=["jz_brush_a"], text=(
            "监正先以「陛下乃九五之尊，区区一个银锣，不必在乎」把这件事轻轻挡回——"
            "皇帝的意志先被臣下一句轻描淡写顶了一下。")),
        obstacleNote=None,
        action=dict(basis="explicit", quotes=["em_insist_a"], text=(
            "一口否决监正的说法、气冲冲重申要求，并主动把天机盘押上（「哪怕输了天机盘」）。")),
        actionNote=None,
        result=dict(basis="explicit", quotes=["jz_promise_a"], text=(
            "只得到一句口头承诺（监正颔首「陛下放心」）。本区间没有任何叙述句确认监正此后真的以法术阻止成功，"
            "也没有写天机盘的胜负。")),
        resultNote=None,
        cost=None,
        costNote=("本区间未出现元景帝已付出代价的描写。「哪怕输了天机盘」是**他愿意承担的赌注**（条件式让步），"
                  "原文没有任何一处写天机盘真的输掉了；把意愿当已执行的代价正是任务书禁止的形态。"),
    ),
    dict(
        id="T05", who="赵守（云鹿书院院长）与三位大儒",
        objective=dict(basis="explicit", quotes=["yl_zhaoshou_a"], text=(
            "让红木盒子安静下来——院长赵守以拱手请求的方式开口「请前辈安静」，"
            "对象被称作「前辈」，即他们把这个封印物当作可沟通的对象。")),
        objectiveNote=None,
        obstacle=dict(basis="explicit", quotes=["yl_hum_a"], text=(
            "四人第一次请求之后盒子只安静了「就在下一刻」就再震，且「震动愈发剧烈」——"
            "请求式压制对它是无效的。")),
        obstacleNote=None,
        action=dict(basis="explicit", quotes=["yl_join_a"], text=(
            "三位大儒「鼓荡浩然正气」与院长联手压制红木盒子（并再次拱手「请前辈安静」）——"
            "从口头请求升级到动手压制。")),
        actionNote=None,
        result=dict(basis="explicit", quotes=["yl_burst_short", "yl_escape_a"], text=(
            "失败：红木盒子炸散，一道清光破盒而出、撞穿殿顶、破空飞向京城方向。")),
        resultNote=None,
        cost=dict(basis="explicit", quotes=["yl_hurt"], text=(
            "四人被震伤：「胸口如撞，鲜血狂喷，齐齐震飞」——这是他们动手压制后自己承受的伤。")),
        costNote=None,
    ),
    dict(
        id="T06", who="许七安（求金刚神功的一面）",
        objective=dict(basis="explicit", quotes=["jd_crave_a"], text=(
            "想参悟金刚经、修成「金刚不败」这门护体神功。叙述明写他「一直很眼馋佛门的金刚神通」，"
            "并给出他自己的盘算：修成后「在六品武者境，堪称无敌」。")),
        objectiveNote=None,
        obstacle=dict(basis="explicit", quotes=["jd_missing_a"], text=(
            "他在佛像身上找不到金刚经（「明明没有啊」）——度厄罗汉许诺的「奥秘就在金身之中」，"
            "以他当时的眼光看不到。")),
        obstacleNote=None,
        action=dict(basis="explicit", quotes=["jd_sit_a"], text=(
            "盘坐蒲团、昂头审视金刚法相。这是本区间他为此做的唯一可辨认的动作。")),
        actionNote=None,
        result=dict(basis="explicit", quotes=["jd_done_a"], text=(
            "意外修成金身：「几个呼吸间，许七安浑身灿灿金光，俨然也是一尊金身法相」。"
            "叙述并未说他得到金刚经文本，也并未说这金身是他自己参悟来的——见 costNote 与 unknowns。")),
        resultNote=None,
        cost=None,
        costNote=("本区间未出现许七安为求金刚神功付出代价的描写。这一段只有「眼睛快酸了」这类过程性不适，"
                  "且原文把它写成自嘲（「我果然是没有佛根的粗鄙武夫」），不是损失；"
                  "真正的身体代价写在被迫下跪那一段（脊椎/肩膀），与「求神功」这条线不是同一件事，不挪用。"),
    ),
    dict(
        id="T07", who="在场的大奉子民（凉棚贵族到场外百姓）",
        objective=dict(basis="explicit", quotes=["nk_crowd_a"], text=(
            "喊出「不跪」——由群众中某人先抬拳喊出，随后扩散为众人共同的要求：要许七安不向佛门下跪。")),
        objectiveNote=None,
        obstacle=dict(basis="explicit", quotes=["bx_palm_a"], text=(
            "擎天法相垂头伸手、巨大的佛掌往下一按；压力落在庙内许七安身上，场外众人只能喊，"
            "无法直接干预仪式。")),
        obstacleNote=None,
        action=dict(basis="explicit", quotes=["nk_all_a"], text=(
            "「从凉棚到场外，从贵族到百姓」同声发出「不跪」——从个别人到全场的一致发声，"
            "原文用「发出了共同的声音」写这次齐声。")),
        actionNote=None,
        result=dict(basis="derived", quotes=["ql_summon_a"], text=(
            "一道清光破空而来、撞入佛境。叙述用「这道清光，应召而来」把清光的到来写成被召唤的结果，"
            "方向是「呼声 → 应召」，但**没有**写召唤者是谁、机制是什么（见 unknowns U01/U04）。")),
        resultNote=None,
        cost=None,
        costNote=("本区间未出现百姓为这次呼喊付出代价的描写。原文写到爆炸声「震的京城百姓抱头鼠窜」"
                  "属于场外受惊的即时反应，叙述没有把它写成他们付出的代价，也没有任何损失结算；不把惊吓升级成 cost。"),
    ),
    dict(
        id="T08", who="许七安（守住自我这条意志线）",
        objective=dict(basis="explicit", quotes=["bx_warn_a"], text=(
            "守住自我、不下跪：他「心生警兆」，预感这一跪「就再没有回头路了」，会变成另一个自己。")),
        objectiveNote=None,
        obstacle=dict(basis="explicit", quotes=["gz_crush_a"], text=(
            "佛光在「瞬间压垮了他的意志，改变了他的内心」——阻力不是说服，是直接改写内心。")),
        obstacleNote=None,
        action=dict(basis="explicit", quotes=["gz_shame_b"], text=(
            "靠「巨大的羞耻感」找回一点自我（触发点是当众摘貂帽会露出光头，见 gz_shame_a）。")),
        actionNote=None,
        result=dict(basis="explicit", quotes=["gz_hold_a"], text=(
            "只取得**短暂**的自我意志，能抗拒加入佛门与灌输进来的思想——原文用「短暂的」限定，"
            "这不是彻底摆脱，随后他仍被压到「头埋的更低了」。")),
        resultNote=None,
        cost=None,
        costNote=("本区间未出现这条线单独的代价描写。此线写的是意志被压垮又短暂夺回，原文没有为「找回自我」"
                  "结算任何付出；与他身体受损（T02 cost）是两条线，不重复引用同一句充当两处依据。"),
    ),
    dict(
        id="T09", who="裱裱（二公主）",
        objective=dict(basis="explicit", quotes=["bb_demand_a"], text=(
            "要看寺庙里的情形——她怀疑佛门在里头设龌龊伎俩坑害大奉的银锣，因此要求公开庙内景象。")),
        objectiveNote=None,
        obstacle=dict(basis="explicit", quotes=["bb_fill_a"], text=(
            "看不见庙内景象，她只能不停脑补许七安受害——信息的缺失本身构成她的处境。")),
        obstacleNote=None,
        action=dict(basis="explicit", quotes=["nk_bb_a"], text=(
            "走出凉棚高声喊「不要给秃驴下跪，狗奴才，站着」。"
            "注意：她「要看」的诉求在叙述里是由怀庆以「风光霁月」为由头接续提出的（见 causeEdges C17），"
            "裱裱本人的可归因动作是这次喊话。")),
        actionNote=None,
        result=dict(basis="explicit", quotes=["switch_view_a"], text=(
            "庙内景象被公开：度厄罗汉挥袖切换佛境画面，众人看见了烛光摇曳的大殿——"
            "她「要看」的诉求得到满足。")),
        resultNote=None,
        cost=None,
        costNote=("本区间未出现裱裱为这次出头付出代价的描写：她喊话前后没有被斥责、被拦、被罚，"
                  "也没有任何叙述句把她的失态记为损失。原文对她这一段只写到情绪与动作，不写后果。"),
    ),
]


# ═══════════════════════════════════════════════════════════════════════
# 2. causeEdges[] —— 每条必须有方向 + 触发机制
# ═══════════════════════════════════════════════════════════════════════
CAUSE_EDGES = [
    dict(id="C01", **{"from": "度厄罗汉当众改口", "to": "武夫群体的情绪逆转"}, basis="explicit",
         trigger=("机制：叙述先用整整一段铺「武夫被各大体系鄙夷、武以力犯禁」，"
                  "再用「而现在」把度厄罗汉以「当为吾师」称呼一名武夫的事实与之对立，"
                  "落差本身就是触发条件——所以「扬眉吐气」是被这个对比激出来的。"),
         quotes=["op_speech_b", "op_wufu_b", "op_wufu_c"]),
    dict(id="C02", **{"from": "度厄罗汉宣称金刚经的奥秘就在金身之中", "to": "许七安起贪求之心"}, basis="explicit",
         trigger="机制：许诺给出具体可得的收益（修成护体神功、六品境无敌），许七安的反应被写成「眼神火热」。",
         quotes=["jd_offer_a", "jd_crave_a"]),
    dict(id="C03", **{"from": "许七安回忆教坊司花魁的一百零八种招式自污", "to": "他把「老色批」身份当成入庙前的护身符"}, basis="inferred",
         trigger=("机制：原文写他「以此污浊内心」——目的是不让自己以清净心进庙；"
                  "紧接着写「确认自己成为了一个老色批，他才满意的颔首」才推门。"
                  "这是他的自我准备，原文没有写这一手是否真的奏效（见 unknowns U13）。"),
         quotes=["in_plan_a", "in_enter_a"]),
    dict(id="C04", **{"from": "腹内暖流上行、眉心开启使他看懂佛韵", "to": "他化现金身法相"}, basis="explicit",
         trigger=("机制：原文按顺序写「暖流 → 眉心霍然一振 → 佛像有变化、他看懂禅意 → "
                  "不自觉改变坐姿、与佛像一模一样 → 眉心金漆诞生并蔓延 → 浑身灿灿金光」。"
                  "坐姿模仿是关键中间环节，不是直接跳到金身。"),
         quotes=["jd_flow_a", "jd_gild_a", "jd_done_a"]),
    dict(id="C05", **{"from": "许七安浑身金光（外形）", "to": "市井百姓误判为皈依、士气崩溃"}, basis="explicit",
         trigger=("机制：误读源于他们只看得见「化成金身」这一外形，看不见成因；"
                  "叙述把结果写成「险些崩裂，脸色瞬间垮了，像是戳破了的气球」。"
                  "这是**误读**，同一段后文立刻由江湖客纠正（见 C06），不能当成叙述事实。"),
         quotes=["ms_shock_a", "ms_collapse_a", "ms_wrong_a"]),
    dict(id="C06", **{"from": "江湖客喊出「金刚不败」这一正确解释", "to": "百姓放心、重新笑起来"}, basis="explicit",
         trigger=("机制：纠正性信息补上了「金光＝修成佛门神功而非皈依」这一环，"
                  "叙述用「喧哗声顿时如开闸的洪水」写情绪回摆。"),
         quotes=["ms_call_a", "ms_explain_a", "ms_relief_a"]),
    dict(id="C07", **{"from": "金刚法相忽然睁眼、霸道佛光吞没", "to": "许七安的意志被压垮、本心被改写"}, basis="explicit",
         trigger=("机制：不是说服而是直接改写——原文写这佛光「并不能让人感觉祥和，反而给人霸道无理的感觉」，"
                  "并明写「在瞬间压垮了他的意志，改变了他的内心」「短短一瞬间，改变了本心」。"),
         quotes=["gz_eye_a", "gz_crush_a", "gz_change_a"]),
    dict(id="C08", **{"from": "本心被改写为向往佛门", "to": "他起身抽刀、按住貂帽（剃度动作）"}, basis="derived",
         trigger=("机制：叙述先写「开始向往佛门，向往佛法」，紧接写他站起、抽刀、把手按在貂帽上；"
                  "叙述自己给出解释「这是要给自己剃度」。"
                  "标 derived 是因为「向往 → 剃度」这一步是叙述用相邻两句完成的，没有明写因果连词。"),
         quotes=["gz_yearn_a", "gz_draw_a"]),
    dict(id="C09", **{"from": "当众摘帽会露出光头的羞耻感", "to": "他找回一点自我、松开按帽的手"}, basis="explicit",
         trigger=("机制：阻断面来自他残存的自尊而非力量——原文写「巨大的羞耻感让他找回了一点『自我』」，"
                  "结果直接写成「松开了按住貂帽的手，貂帽依旧戴在头上」。"),
         quotes=["gz_shame_a", "gz_shame_b", "gz_hat_a"]),
    dict(id="C10", **{"from": "许七安的抗拒", "to": "佛像震怒、凝聚擎天法相并以佛掌下压"}, basis="explicit",
         trigger=("机制：原文用「许七安的抗拒，**似乎**引来了佛像的震怒」——带「似乎」，"
                  "即叙述对这一因果本身留了余地；但「佛山雾气剧烈抖动 → 金身法相凝聚 → 佛掌下按 → "
                  "肩膀一沉」这一段动作链是直述的。我不把「似乎」删掉。"),
         quotes=["bx_rage_a", "bx_palm_a", "bx_press_a"]),
    dict(id="C11", **{"from": "佛掌下压的重量", "to": "骨头爆响、头埋更低；但膝盖没有弯曲"}, basis="explicit",
         trigger=("机制：压力被写成对身体的直接作用（脊椎外凸、随时刺破血肉），"
                  "而结果被写成分离的两项——头更低（屈服了一半）与膝盖未弯（没屈服）；"
                  "「唯一不变的，是膝盖没有弯曲」正是不把「低头」等同于「跪下」的原文依据。"),
         quotes=["bx_bones_a", "bx_knee_a"]),
    dict(id="C12", **{"from": "红木盒子剧烈震动（李慕白归因为「又有人调动众生之力」）", "to": "四人压制失败、盒子炸散、清光飞向京城"}, basis="explicit",
         trigger=("机制：震动 → 口头请求 → 联手压制 → 短暂安静 → 炸散，是一条动作链；"
                  "但「又有人调动众生之力」是**李慕白的疑问**（人物推断），原文并未认定盒子异动就是众生之力所致，"
                  "所以这条边只把该句当作触发点之一，不当作叙述对成因的认定。"),
         quotes=["yl_box_a", "yl_li_a", "yl_join_a", "yl_dir_a"]),
    dict(id="C13", **{"from": "全场齐喊「不跪」", "to": "许七安感到众生之力般的念头涌入识海"}, basis="derived",
         trigger=("机制：原文把两件事紧接写出——众人「发出了共同的声音：不跪！」之后，"
                  "许七安内心「我**好像**又感觉到众生之力了……一股纯粹的念头涌入他的识海……在向他传递一个声音：不跪！」。"
                  "标 derived：接通两段的是他的内感受，且带「好像」，不是叙述对机制的认定。"),
         quotes=["nk_all_a", "ql_feel_a", "ql_voice_a"]),
    dict(id="C14", **{"from": "清光破空撞入佛境", "to": "擎天法相收掌拍向清光；清光入庙落到许七安手里"}, basis="explicit",
         trigger=("机制：方向明确——法相「似有所感，收回了佛掌，拍向撞入秘境的清光」，"
                  "交锋后法相崩裂成金光，清光「旋即入庙，落在许七安手里」。"
                  "「似有所感」同样保留了余地，我不删。"),
         quotes=["ql_fly_a", "ql_clash_a", "ql_land_a", "ql_knife_a"]),
    dict(id="C15", **{"from": "许七安以刻刀刺出", "to": "佛像崩散、佛境坍塌、金钵炸成齑粉"}, basis="explicit",
         trigger=("机制：刺出 → 佛像眉心龟裂 → 裂缝遍布全身崩散 → 佛境剧烈抖动、佛山坍塌 → "
                  "度厄罗汉的金钵炸成齑粉 → 佛境幻灭，是一条按顺序写出的连锁。"),
         quotes=["ql_stab_a", "ql_crack_a", "ql_collapse_a", "ql_bowl_a"]),
    dict(id="C16", **{"from": "佛境幻灭", "to": "许七安与净思跌出；许七安昏倒前按住貂帽"}, basis="explicit",
         trigger=("机制：佛境消失的直接后果是困在其中的两人跌出（净思昏迷、许七安傲然而立）；"
                  "紧接着写他扫视全场、昏过去，并在昏倒前按住貂帽——叙述自己给出评价「这是他的尊严」。"),
         quotes=["ql_end_a", "ql_out_a", "ql_hat_a", "ql_dignity_a"]),
    dict(id="C17", **{"from": "裱裱质问并索看庙内，怀庆以「风光霁月」接续施压，贵族纷纷开口", "to": "度厄罗汉挥袖切换佛境画面"}, basis="explicit",
         trigger=("机制：从一个人的质问升级为多人一致要求，度厄罗汉才「合十微笑，宽大的袖子一挥」。"
                  "注意归因要分清楚：**索看的诉求由裱裱提出，措辞由怀庆给，声势由贵族给**，"
                  "不能把画面切换记成裱裱一个人的因果（见 T09 actionNote 与 unknowns）。"),
         quotes=["bb_demand_a", "hq_demand_a", "switch_view_a"]),
    dict(id="C18", **{"from": "许七安吼出「我！许七安，不！跪！」", "to": "清光应召而来、悍然撞入佛境"}, basis="derived",
         trigger=("机制：原文把「吼出」与「当是时，一道清光破空而来」紧接写出，并在其后用"
                  "「这道清光，应召而来」明确给出「被召唤」这一判断。"
                  "标 derived：原文只说「应召」，**没有**说召唤者是谁、以什么为凭（见 unknowns U01）。"),
         quotes=["ql_shout_a", "ql_fly_a", "ql_summon_a"]),
    dict(id="C19", **{"from": "度厄罗汉命名并讲述「修罗问心」典故", "to": "该关以压迫意志的方式实际执行"}, basis="derived",
         trigger=("机制：典故说的是佛陀挨三千六百刀而现金身、修罗族因此皈依；"
                  "本关的执行与之同向——先由金刚法相睁眼以佛光「压垮意志、改变内心」，"
                  "再由擎天法相以佛掌迫其下跪。即「问心」被兑现为对意志的强制。"
                  "标 derived：原文没有一句写「这一关就是这样执行的」，是典故与后续动作的对应。"),
         quotes=["xl_name_a", "gz_light_a", "bx_kneel_a"]),
]


# ═══════════════════════════════════════════════════════════════════════
# 3. rejectedEdges[] —— 时间相邻/同场景，但不构成因果（我考虑过并拒绝）
# ═══════════════════════════════════════════════════════════════════════
REJECTED_EDGES = [
    dict(id="R01", pair=["监正「忽然停下来，愕然眺望远方」", "清光撞入佛境"], basis="explicit",
         why=("时间上紧邻，但原文把清光的来源明确指向云鹿书院方向（「那是云鹿书院的方向」），"
              "并写它「应召而来」；把「监正停手」当作「他召唤了清光」没有任何机制句支撑，"
              "而且监正停手的叙述语义恰恰是「他没做」。拒绝连边。"),
         quotes=["jz_stop_a", "yl_dir_a"]),
    dict(id="R02", pair=["许新年「我在想应该从哪个角度捅他一刀」", "度厄罗汉随后的皱眉与施压"], basis="explicit",
         why="一句私下的戏言与后文佛像施压之间没有任何机制；且许新年此后再未被写及行动。拒绝连边。",
         quotes=["dh_xxn_a", "dh_frown_a"]),
    dict(id="R03", pair=["美妇人劝蓉蓉给许大人做妾", "许七安破佛像"], basis="explicit",
         why=("同一章内两条互不相干的线程：一条写在角落里议亲，一条写在佛境中斗法，"
              "二者既无信息传递也无动作接续。仅因同章而连边就是「同一场景当因果」。拒绝连边。"),
         quotes=["op_matchmaker_b", "ql_crack_a"]),
    dict(id="R04", pair=["度厄罗汉「进了此庙，便是石头，也能点化，皈依佛门」", "许七安修成金身"], basis="explicit",
         why=("这是度厄罗汉的**夸口**，且后文的实际结果是相反的（许七安没皈依、还偷学了金刚不败、"
              "最后砸了场子）。把夸口当因果会得出「他说能点化所以许七安被点化」的错误结论。拒绝连边。"),
         quotes=["in_boast_a", "ms_steal_a"]),
    dict(id="R05", pair=["净思昏迷跌出", "金钵炸成齑粉"], basis="explicit",
         why=("两者都是佛境幻灭的**并发结果**，彼此之间没有方向。原文用「佛境随之幻灭。两道身影跌出」"
              "与「度厄罗汉愕然低头，看见金钵……」分写两处，谁也不导致谁。拒绝连边。"),
         quotes=["ql_out_a", "ql_bowl_a"]),
    dict(id="R06", pair=["开篇「天空中惊雷响了一声」", "「度厄罗汉身上的佛光收敛」"], basis="explicit",
         why=("同一句里并写的两个现象，原文用「与之相对应的」把二者写成对应关系而非因果关系；"
              "没有机制说明雷导致佛光收敛。拒绝连边。"),
         quotes=["nm_thunder_a"]),
    dict(id="R07", pair=["王首辅等喊「不跪」", "监正停手"], basis="explicit",
         why=("监正的停手在原文中紧接「那是云鹿书院的方向」，其视线方向被写明是书院；"
              "与凉棚里的喊话没有机制关联。把同时发生的两件事连边就是时间相邻当因果。拒绝连边。"),
         quotes=["nk_wang_a", "jz_stop_a"]),
    dict(id="R08", pair=["许七安内心「我好像又感觉到众生之力了」", "认定清光就是众生之力"], basis="explicit",
         why=("该句是**人物内心**且带「好像」；本区间内「众生之力」另一次出现是李慕白的疑问句。"
              "两句都不是叙述认定。把带不确定限定的人物感受升级为事实认定，是任务书禁止的形态。拒绝连边。"),
         quotes=["ql_feel_a", "yl_li_a"]),
    dict(id="R09", pair=["许七安昏倒", "满场寂静无声"], basis="explicit",
         why="两个同时发生的收束性描写，没有方向也没有机制。拒绝连边。",
         quotes=["ql_scan_a", "ql_silence_a"]),
    dict(id="R10", pair=["佛门弟子「见悟」", "度厄罗汉改口认负"], basis="explicit",
         why=("原文写弟子们陷入见悟，紧接着写度厄罗汉「没有去打搅弟子们领悟」而后朗声认输；"
              "弟子是否见悟与他认输之间没有机制句，且「这和度厄大师的顿悟差了十万八千里」"
              "更像是在贬低这次见悟的分量。拒绝连边。"),
         quotes=["op_see_a", "nm_gap_a"]),
]


# ═══════════════════════════════════════════════════════════════════════
# 4. states[] —— 前值 / 后值 / 事件锚点（各带引文与 basis）
# ═══════════════════════════════════════════════════════════════════════
STATES = [
    dict(id="S01", who="许七安·形体", before=dict(basis="explicit", quotes=["jd_selfmock_a"],
         text="自认「没有佛根的粗鄙武夫」——他对自己能否与佛法相应是负面判断。"),
         after=dict(basis="explicit", quotes=["jd_done_a"], text="浑身灿灿金光，俨然一尊金身法相。"),
         anchor=dict(basis="explicit", quotes=["jd_flow_a"], text="腹内暖流上行、眉心霍然一振——变化从这一刻开始。")),
    dict(id="S02", who="度厄罗汉·情绪", before=dict(basis="explicit", quotes=["dh_happy_b"],
         text="畅快淋漓：「一朝顿悟大乘佛法，更得一位天生慧根的佛子」。"),
         after=dict(basis="explicit", quotes=["ms_deun_a"], text="愕然——他也没料到许七安会化出金身。"),
         anchor=dict(basis="explicit", quotes=["jd_gild_a"], text="许七安眉心金漆蔓延、被金光勾勒成形。")),
    dict(id="S03", who="市井百姓·对局面的判断", before=dict(basis="explicit", quotes=["ms_wrong_a"],
         text="以为许七安「让京城百姓扬眉吐气」之后「最后却被佛门『度化』」。"),
         after=dict(basis="explicit", quotes=["ms_relief_a"], text="放心了、再次笑了起来（因为得知那是金刚不败）。"),
         anchor=dict(basis="explicit", quotes=["ms_call_a"], text="江湖客当众喊出「金刚不败，他修成金刚不败了！」")),
    dict(id="S04", who="许七安·本心", before=dict(basis="explicit", quotes=["gz_yearn_a"], text="开始向往佛门、向往佛法。"),
         after=dict(basis="explicit", quotes=["gz_hold_a"], text="短暂获得自我意志，抗拒加入佛门与被灌输的思想。"),
         anchor=dict(basis="explicit", quotes=["gz_shame_b"], text="巨大的羞耻感让他找回一点「自我」。")),
    dict(id="S05", who="擎天法相·存在状态", before=dict(basis="explicit", quotes=["bx_huge_a"],
         text="顶天立地：「万事万物都变的渺小」「寺庙还没有法相手掌大」。"),
         after=dict(basis="explicit", quotes=["ql_break_a"], text="崩裂成纯粹的金光，归于佛境。"),
         anchor=dict(basis="explicit", quotes=["ql_clash_a"], text="它收回佛掌、拍向撞入秘境的清光，交锋后一黯。")),
    dict(id="S06", who="许七安·脊梁", before=dict(basis="explicit", quotes=["bx_bow_a"], text="头埋得更低，怎么都直不起来。"),
         after=dict(basis="explicit", quotes=["ql_stand_a"], text="缓缓的、慢慢的直起腰杆，握紧了刻刀。"),
         anchor=dict(basis="explicit", quotes=["ql_land_a"], text="清光入庙，落在许七安手里。")),
    dict(id="S07", who="红木盒子·存续", before=dict(basis="explicit", quotes=["yl_box_a"],
         text="剧烈震动，「里面的东西似乎迫切的想要出来」。"),
         after=dict(basis="explicit", quotes=["yl_burst_short"], text="炸散（内含之物已脱出）。"),
         anchor=dict(basis="explicit", quotes=["yl_join_a"], text="三位大儒与院长联手压制。")),
    dict(id="S08", who="裱裱·姿态", before=dict(basis="explicit", quotes=["bb_fill_a"], text="看不见庙内，只能不停脑补许七安受害。"),
         after=dict(basis="explicit", quotes=["nk_bb_a"], text="走出凉棚高喊「不要给秃驴下跪，狗奴才，站着」。"),
         anchor=dict(basis="explicit", quotes=["bb_demand_a"], text="她霍然起身、以「本宫要看寺庙里的情形」当面质问度厄罗汉。")),
    dict(id="S09", who="清光·所在", before=dict(basis="derived", quotes=["yl_box_a"],
         text="被封在亚圣殿的红木盒子里（原文只写盒子「里面的东西似乎迫切的想要出来」，未直说就是清光）。"),
         after=dict(basis="explicit", quotes=["ql_land_a"], text="入庙，落在许七安手里，现形为一把古朴的黑色刻刀。"),
         anchor=dict(basis="explicit", quotes=["yl_escape_a"], text="破盒而出、撞穿殿顶、破空而起。")),
    dict(id="S10", who="净思·状态", before=None,
         beforeNote=("本区间没有他在此之前的状态描写——他在本章第一次被写及就已经是「昏迷不醒的净思」。"
                     "他在此之前坐镇第二关、与许七安交手等情都在本区间之外，我不从区外补一个前值。"),
         after=dict(basis="explicit", quotes=["ql_out_a"], text="与许七安一同从幻灭的佛境中跌出，昏迷不醒。"),
         anchor=dict(basis="explicit", quotes=["ql_end_a"], text="佛境随之幻灭。")),
    dict(id="S11", who="佛境·存续", before=dict(basis="explicit", quotes=["switch_view_a"],
         text="正常运作：画面可切换，众人能看见殿内烛光。"),
         after=dict(basis="explicit", quotes=["ql_end_a"], text="随之幻灭。"),
         anchor=dict(basis="explicit", quotes=["ql_collapse_a"], text="佛像崩溃的同时佛境剧烈抖动，佛山坍塌、天摇地动。")),
    dict(id="S12", who="武夫群体·被看待的方式", before=dict(basis="explicit", quotes=["op_wufu_a"],
         text="被各大体系鄙夷：「武以力犯禁」，是「九州社会的不安定因素」。"),
         after=dict(basis="explicit", quotes=["op_wufu_c"], text="扬眉吐气，恨不得仰天长啸。"),
         anchor=dict(basis="explicit", quotes=["op_speech_b"], text="号「当为吾师」——二品罗汉尊一名武夫为师长。")),
]


# ═══════════════════════════════════════════════════════════════════════
# 5. knowledgeGaps[] —— 谁知 / 谁不知（知识差）
# ═══════════════════════════════════════════════════════════════════════
KNOWLEDGE_GAPS = [
    dict(id="K01", knower="许七安", knows=False, about="监正是否预知并安排了这一切",
         basis="explicit", quotes=["nm_plan_a"],
         note="他只能自问「监正，这一切都在你的预料之中吗？」，本区间没有给出答案；同段他还写「监正太可怕了」。"),
    dict(id="K02", knower="市井百姓", knows=False, about="许七安化金身的原因",
         basis="explicit", quotes=["ms_shock_a", "ms_collapse_a"],
         note="他们只看得见外形（浑身金光），于是按「皈依佛门」来理解，情绪先崩后笑；成因由江湖客事后补上。"),
    dict(id="K03", knower="王首辅等权臣与世袭贵族", knows=False, about="「修罗问心」的实际效果",
         basis="explicit", quotes=["xl_infer_a", "xl_infer_b"],
         note=("他们的判断是从关名类推出来的（「既然命名为『修罗问心』，那效果必然是与佛陀度化修罗族是一样的」），"
               "属未经证实的推断；原文并未在同一处确认该推断。")),
    dict(id="K04", knower="裱裱", knows=False, about="庙内正在发生什么",
         basis="explicit", quotes=["bb_fill_a", "bb_brain_a"],
         note="信息缺失使她的判断靠脑补完成——原文写她「反而不停脑补，脑补许七安受害」。"),
    dict(id="K05", knower="许七安", knows=False, about="是什么力量在帮自己",
         basis="explicit", quotes=["jd_help_a"],
         note="他只能以疑问句记下「是，是......在帮我？！」，本区间没有任何一句点名那股力量的来源。"),
    dict(id="K06", knower="全场众人（与本区间读者）", knows=False, about="刻刀的来历",
         basis="derived", quotes=["yl_dir_a", "ql_knife_a"],
         note=("原文只写「一道清光破盒而出」并给出方向「那是京城的方向」，随后写「那道清光旋即入庙……"
               "那是一把古朴的，黑色的刻刀」。把盒中之物与刻刀认定为同一物，靠的是「清光」这一称谓的连续，"
               "没有任何直述句（见 unknowns U02）。")),
    dict(id="K07", knower="魏渊", knows=None, about="许七安修成金刚不败的内幕",
         basis="explicit", quotes=["ms_wei_b"],
         note=("原文写他「不追究内幕」——这是他主动选择不去追究，因此他的知识状态不是「不知道」而是「不查」，"
               "我按原文字面记为主动放弃知情。")),
    dict(id="K08", knower="李慕白", knows=False, about="红木盒子异动的成因",
         basis="explicit", quotes=["yl_li_a"],
         note="他以疑问句提出「又有人调动众生之力？」；这是人物推断，不是叙述认定。"),
    dict(id="K09", knower="元景帝", knows=False, about="监正打算怎么阻止",
         basis="explicit", quotes=["jz_promise_a"],
         note="他得到的只是「陛下放心」四个字，本区间没有写监正告知方案。"),
    dict(id="K10", knower="张巡抚", knows=True, about="许七安写过什么词",
         basis="explicit", quotes=["nk_ci_a"],
         note=("他当众背诵「少年侠气，交结五都雄……」并以「能写出这种词的人，不跪！」作结——"
               "即他用自己掌握的文本知识为许七安的人格作保。"),
         ),
    dict(id="K11", knower="场外众人", knows=True, about="许七安正在挣扎这件事",
         basis="explicit", quotes=["dh_watch_a"],
         note="原文写「任谁都看出了许七安在挣扎，在于『修罗问心』做抗争」——他们看得见挣扎，看不见机制。"),
    dict(id="K12", knower="净思", knows=False, about="本场斗法的结局",
         basis="explicit", quotes=["ql_out_a"],
         note="他被写出时已「昏迷不醒」，本区间未写他何时、因何失去意识。"),
]


# ═══════════════════════════════════════════════════════════════════════
# 6. foreshadows[] —— 必须有铺设 + 回收；未回收显式 unresolved
# ═══════════════════════════════════════════════════════════════════════
FORESHADOWS = [
    dict(id="F01", name="貂帽＝尊严", resolved=True, basis="explicit",
         setup=["gz_draw_a", "gz_ton_a"],
         payoff=["gz_hat_a", "ql_hat_a", "ql_dignity_a"],
         note=("铺设：他被改写本心后起身抽刀、手按貂帽，叙述点明这是要剃度、摘了帽子光头就会曝光。"
               "回收两次：①羞耻感让他松开手、帽子仍在头上；②昏倒前他又按住貂帽，叙述给出评价「这是他的尊严」。"
               "铺设与回收是同一物件、同一语义（帽子＝他仅剩的自尊），成立。")),
    dict(id="F02", name="书院清光 → 刻刀", resolved=True, basis="derived",
         setup=["yl_box_a", "yl_escape_a"],
         payoff=["ql_fly_a", "ql_land_a", "ql_stab_a"],
         note=("铺设：亚圣殿盒中之物急欲脱出，随后破盒而出、飞向京城方向。"
               "回收：一道清光破空撞入佛境，交锋后「旋即入庙，落在许七安手里」，现形为刻刀，"
               "并成为刺碎佛像的那件东西。标 derived 是因为「盒中之物＝刻刀」由「清光」称谓的连续推出，非直述。")),
    dict(id="F03", name="「修罗问心」的命名与典故", resolved=True, basis="derived",
         setup=["xl_name_a", "xl_tale_b"],
         payoff=["gz_light_a", "bx_kneel_a"],
         note=("铺设：度厄罗汉先报出关名，再讲佛陀挨三千六百刀而现金身、修罗族因此皈依的典故，"
               "使「这一关会怎样」有了预期。回收：该关的实际执行与典故同向——先以佛光压垮意志，"
               "再以佛掌迫使下跪。标 derived：原文没有一句直接说「本关即按典故执行」。")),
    dict(id="F04", name="金刚经的许诺 → 金刚不败", resolved=True, basis="explicit",
         setup=["jd_offer_a"],
         payoff=["jd_done_a", "ms_explain_a"],
         note=("铺设：度厄罗汉当众宣称「金刚经的奥秘就在金身之中……便可修成佛门金刚不败」，"
               "同时叙述点明这是「画饼」。回收：许七安确实化出金身，场外江湖客把这件事命名为「金刚不败」，"
               "并说佛门「偷鸡不成蚀把米」。铺设时的许诺与回收时的结果指向同一件事。")),
    dict(id="F05", name="天机盘", resolved=False, basis="explicit",
         setup=["in_topic_a"],
         payoff=[],
         note=("铺设：「西域使团不但要赢天机盘」——它被写成这场斗法的赌注。"
               "本区间内它只再出现在元景帝的条件式让步里（「哪怕输了天机盘」），"
               "没有任何一句交代它的归属或它是什么。显式标 unresolved。")),
    dict(id="F06", name="众生之力", resolved=False, basis="derived",
         setup=["ql_feel_a"],
         payoff=[],
         note=("铺设：许七安内心「我好像又感觉到众生之力了」，接着写念头涌入识海。"
               "本区间内「众生之力」另一次出现是李慕白的疑问句，没有任何叙述句把它与清光/刻刀认定为同一物，"
               "也没有写这次感受带来了什么可验证的结果。显式标 unresolved。")),
    dict(id="F07", name="红木盒中「前辈」的身份与「谁调动了众生之力」", resolved=False, basis="explicit",
         setup=["yl_zhang_a", "yl_li_a"],
         payoff=[],
         note=("铺设：盒子「又一次」震动（说明此前已发生过一次）、张慎称「前辈怎么又动了」、"
               "李慕白问「又有人调动众生之力？」。回收：盒子炸散、清光飞出——但「前辈」是谁、"
               "是谁调动了众生之力，本区间都没有交代。显式标 unresolved。")),
    dict(id="F08", name="以好色自污当护身符 → 被度化后失效", resolved=True, basis="inferred",
         setup=["in_plan_a", "in_enter_a"],
         payoff=["gz_scent_a"],
         note=("铺设：他刻意回忆教坊司花魁的招式「以此污浊内心」，确认自己是老色批才进庙。"
               "回收：本心被改写后，叙述写「连教坊司的花魁们都不香了」——那面护身符当场失效。"
               "标 inferred：原文没有用因果连词把这两处接起来，是靠同一意象的前后反转读出的。")),
]


# ═══════════════════════════════════════════════════════════════════════
# 7. notForeshadows[] —— 只出现一次、不构成伏笔（避免「一次出现当伏笔」）
# ═══════════════════════════════════════════════════════════════════════
NOT_FORESHADOWS = [
    dict(id="N01", name="开篇的一声惊雷", quotes=["nm_thunder_a"],
         why="本区间只出现这一次，既无后续呼应也无解释；把它当伏笔就是把「写景」当铺设。"),
    dict(id="N02", name="美妇人替蓉蓉议妾", quotes=["op_matchmaker_b"],
         why="只出现这一次，此后本区间再未写到蓉蓉或这位美妇人的任何行动与结果。"),
    dict(id="N03", name="「上来，自己动」的玩笑", quotes=["nm_short_a"],
         why="叙述里的一句插科打诨，只出现一次，与后文无任何呼应；不因为是「梗」就算伏笔。"),
]


# ═══════════════════════════════════════════════════════════════════════
# 8. worldSettings[] —— 只收影响行动/资源/约束/后果的明确设定
# ═══════════════════════════════════════════════════════════════════════
WORLD_SETTINGS = [
    dict(id="W01", kind="rule", name="入庙不皈依即佛门输", institution="declared",
         quotes=["in_rule_a"], basis="explicit",
         explain=("这条规则决定了许七安为什么必须走进寺庙、以及「不被度化」本身就是可判定的胜利条件——"
                  "它把「守住本心」从姿态变成胜负。叙述来源是许七安复述度厄罗汉此前的说法（转述），"
                  "本区间内没有任何一句宣布该规则被触发的判决。"),
         institutionNote=("本区间只有规则陈述（许七安复述），没有诏令法文本、也没有任何执行/判决动作，"
                          "因此记 declared；不因为最后佛境幻灭就倒推为 executed——胜负的正式宣告在本区间之外。")),
    dict(id="W02", kind="rule", name="「修罗问心」的效果等同佛陀度化修罗族", institution="misunderstood",
         quotes=["xl_infer_a"], basis="explicit",
         explain=("它解释了权臣与贵族为什么「脸色大变」：按他们的理解，连茹毛饮血的修罗族都被度化，"
                  "许七安必然扛不住。这是**人物的理解**，原文并未确认它与本关实际机制一致——"
                  "实际执行是先压垮意志再以佛掌迫跪，与「度化」同向但不等同。")),
    dict(id="W03", kind="rule", name="金刚神功的修习限制：只适合武僧，不到罗汉境无法掌握", institution="declared",
         quotes=["nm_de_a"], basis="explicit",
         explain=("它解释了度厄罗汉许诺「金刚不败」为什么被叙述称为「画饼」：这门功夫只对武僧一路可行，"
                  "修佛法的僧人不到罗汉境拿不到，所以对许七安而言收益诱人而对佛门僧人而言并非常规可得。"
                  "同时它也解释了叙述为什么特意点出「金刚神功只适合武僧」。"),
         institutionNote=("这是叙述直述的修习条件，不是诏/令/法，本区间也没有对该限制的执行动作"
                          "（既没写谁被禁止，也没写谁被处罚），因此记 declared，并在此标注这一分类张力（见 U14）。")),
    dict(id="W04", kind="rule", name="武夫被各大体系鄙夷、武以力犯禁", institution="declared",
         quotes=["op_wufu_a"], basis="explicit",
         explain=("它解释了后果的方向：正因为常态是「粗鄙的武夫」被视为不安定因素，"
                  "二品罗汉尊一名武夫为师长才会让江湖人士「扬眉吐气」。没有这条社会常态，"
                  "C01 那条情绪逆转就无从解释。"),
         institutionNote="社会常态的陈述，无诏令法文本、无执行动作，记 declared。"),
    dict(id="W05", kind="place", name="山顶寺庙（佛境最后一关）", placeState="arrived",
         quotes=["in_stairs_a", "in_temple_a"], basis="explicit",
         explain=("有明确的到达动作（拾阶而上、走到台阶尽头、踏入小广场、推门进入殿内），"
                  "且被写成独栋一主殿的封闭空间——「最后一关」的判定就在这座殿里发生。"),
         placeStateNote="到达动作在原文里是连续的：拾阶而上 → 踏入广场 → 推开寺庙的门 → 进入殿内。"),
    dict(id="W06", kind="place", name="亚圣殿（云鹿书院）", placeState="arrived",
         quotes=["yl_enter_a"], basis="explicit",
         explain=("四位压制者在此处现身并动手（「殿内清光接连闪烁，院长赵守，三位大儒同时出现」），"
                  "封印物红木盒子也悬在此殿；它是本区间第二条战线发生的地点。"),
         placeStateNote="以「同时出现」在殿内确立在场，属驻守/在场而非单纯提及。"),
    dict(id="W07", kind="place", name="观星楼顶", placeState="arrived",
         quotes=["em_turn_a"], basis="explicit",
         explain=("元景帝在此处发号施令（「猛的回身，指着秘境中的许七安」），"
                  "这条线的全部动作都发生在这个位置上。"),
         placeStateNote=("本区间**没有**写他到达观星楼顶的过程；判为 arrived 的依据是他在此处驻守/在场并发号施令，"
                         "不是单纯的提及或图谋。")),
    dict(id="W08", kind="place", name="酒楼顶", placeState="arrived",
         quotes=["ms_tavern_a"], basis="explicit",
         explain="楚元缜与恒远在此处观战并议论（恒远「羡慕不已」，楚元缜接话），是场外观察点之一。",
         placeStateNote="「酒楼顶上」即其驻守位置，原文直接写在该处发生的动作。"),
    dict(id="W09", kind="place", name="京城（方向指认）", placeState="mentioned",
         quotes=["yl_dir_a"], basis="explicit",
         explain=("原文只写清光「掠过群山，消失在天际」并指出方向是京城，"
                  "没有任何到达动作落到「京城」这个词上（清光最终落点是庙内的许七安手里）。"
                  "记 mentioned，不把方向指认写成抵达。"),
         placeStateNote=("这一条是刻意收录的「提及≠到达」样本：清光确实朝京城方向飞去，"
                         "但原文在京城这个地点上没有任何到达/驻守动作。")),
    dict(id="W10", kind="item", name="貂帽", itemStates=["hold", "use"],
         quotes=["gz_hat_a", "ql_hat_a", "ql_dignity_a"], basis="explicit",
         explain=("hold：被改写本心、松手之后「貂帽依旧戴在头上」，昏倒前又「按住了貂帽」，始终在他头上。"
                  "use：叙述把它当作他抗拒剃度的触发点与最后的尊严（「这是他的尊严」）。"
                  "本区间没有丢失/转手。"),
         itemVerbs="照原文动词：戴 / 按住 / 松开 / 摘（未发生）。",
         itemStatesNote="四态分开判：hold 与 use 同时成立；transfer 与 lose 在本区间均无依据。"),
    dict(id="W11", kind="item", name="刻刀（古朴的，黑色的）", itemStates=["transfer", "hold", "use"],
         quotes=["ql_knife_a", "ql_stab_a", "ql_stand_a"], basis="explicit",
         explain=("transfer：随清光「旋即入庙，落在许七安手里」——由外部转入他手中。"
                  "hold：「握紧了刻刀」。use：「平静的刺出了刻刀」，并直接导致佛像崩散。"
                  "本区间没有丢失。"),
         itemVerbs="照原文动词：落在（手里）/ 握紧 / 刺出。",
         itemStatesNote=("不合并成「物品链」：到手（transfer）、握持（hold）、使用（use）是三个可分别成立的状态，"
                         "原文也分别写了三次动作。")),
    dict(id="W12", kind="item", name="金钵（度厄罗汉的）", itemStates=["lose"],
         quotes=["ql_bowl_a"], basis="explicit",
         explain="「裂开一道道缝隙，终于，『砰』的一声，炸成齑粉」——法器在此役损毁，即持有者失去它。",
         itemVerbs="照原文动词：炸成齑粉。",
         itemStatesNote="lose 成立；本区间未写它此前如何被持有或转手，故不写 hold/transfer。"),
    dict(id="W13", kind="item", name="红木盒子（亚圣殿封印物）", itemStates=["lose"],
         quotes=["yl_burst_short"], basis="explicit",
         explain="「红木盒子炸散」——封印容器在此役毁去，即失去该物。",
         itemVerbs="照原文动词：炸散。",
         itemStatesNote="lose 成立；它此前「悬挂在亚圣雕像头顶」的持有状态属静态陈设，本区间未写成一次 hold 动作。"),
    dict(id="W14", kind="item", name="黑金长刀", itemStates=["hold"],
         quotes=["gz_draw_a"], basis="explicit",
         explain=("本心被改写时他「缓缓抽出黑金长刀」——刀被抽出、持在手里；"
                  "但本区间内它一次也没有被用来攻击，真正刺碎佛像的是随后到手的刻刀。"
                  "这个「抽了却没用上」的错位是本章的一处关键对照。"),
         itemVerbs="照原文动词：抽出。",
         itemStatesNote="只判 hold；use 在本区间无依据（抽刀后没有任何挥砍动作），不凭「抽刀」推定使用。"),
    dict(id="W15", kind="item", name="金刚经", itemStates=["transfer"],
         quotes=["jz_goal_a"], basis="explicit",
         explain=("「金刚经到手，他的目的达到了」——这里的「他」是监正，即经书在这一役中转入监正之手，"
                  "这是本区间唯一一处金刚经的归属变化。"),
         itemVerbs="照原文动词：到手。",
         itemStatesNote=("必须与许七安那条线分开：许七安得到的是**金刚不败**这门护体神功（外形化金身），"
                         "原文从未写他拿到金刚经文本。二者不是同一件物品，不合并。")),
]


# ═══════════════════════════════════════════════════════════════════════
# 9. notWorldSettings[] —— 看起来像设定、但本区间不足以收（写明为什么）
# ═══════════════════════════════════════════════════════════════════════
NOT_WORLD_SETTINGS = [
    dict(id="NW01", name="天机盘", quotes=["in_topic_a"],
         why=("它在区间内只有两处提及（「要赢天机盘」「哪怕输了天机盘」），两处都是赌注/彩头，"
              "没有任何 hold/transfer/use/lose 的动作落到它身上，也没写它是什么器物。四态皆无 ⇒ 不收录。")),
    dict(id="NW02", name="众生之力", quotes=["ql_feel_a", "yl_li_a"],
         why=("本区间里它只出现在一句人物疑问（李慕白「又有人调动众生之力？」）与一句带「好像」的内心感受里，"
              "没有一句设定它是什么、如何调动、有何代价。没有依据就不扩术语层 ⇒ 不收录。")),
    dict(id="NW03", name="浩然正气", quotes=["yl_join_a"],
         why="只作为三位大儒压制盒子时的动作被提到（「鼓荡浩然正气」），无解释、无规则、无代价 ⇒ 不收录。"),
    dict(id="NW04", name="金刚不败（作为功法设定）", quotes=["ms_explain_a", "jd_done_a"],
         why=("它是 W03 那条修习限制规则的**后果**，本区间没有为它本身给出任何可判定的设定"
              "（品级、条件、代价都没有），且它不是器物、四态不适用 ⇒ 作为后果处理，不另立设定条目。")),
]


# ═══════════════════════════════════════════════════════════════════════
# 10. themeReadings[] —— 解释层（最多 2 条），每条三件：perspective/support/counter
# ═══════════════════════════════════════════════════════════════════════
THEME_READINGS = [
    dict(id="TH01",
         perspective=("以「跪／不跪」为轴，读个体意志与外力在这一章里的分工——这一读法把许七安当成承受者而非施动者，"
                      "看他的「不跪」究竟由谁支撑。"),
         support=dict(quotes=["bx_oath_a", "ql_shout_a", "ql_line_a"], basis="explicit", text=(
             "支持这一读法的材料很硬：他的自我宣告（「就算要信佛，也是我心甘情愿的信，谁都不能驯服我」）、"
             "他与全场同声的那一吼（「我！许七安，不！跪！」）、以及破像前的那句"
             "「众生皆可成佛，为何跪你？」——三处都把「不跪」写成他主动选择的立场。")),
         counter=dict(quotes=["gz_hold_a", "jz_need_a", "ql_fly_a"], basis="explicit", text=(
             "但不利证据同样明确，且都在同一区间内：①他夺回的自我被原文限定为「**短暂的**」；"
             "②叙述直接判定「单凭许七安自己，绝对无法抗住佛法灌顶」；"
             "③真正打断施压的是外来的清光（「当是时，一道清光破空而来」）。"
             "即：文本一边写他不跪，一边反复声明他独自扛不住。")),
         note=("结论不压成一条：可以读成「意志是必要的点火条件、外力是充分的破局条件」，"
               "也可以读成「本章其实在削弱个人英雄叙事」——同一批事实两种都成立，我并列写出。")),
    dict(id="TH02",
         perspective=("以「场外看客的认知」为轴，读这一章如何反复写「误读—纠正—再误读」——"
                      "看客的判断被写成随信息与立场摆动的量，而不是可靠的评判。"),
         support=dict(quotes=["ms_collapse_a", "ms_explain_a", "ms_relief_a"], basis="explicit", text=(
             "同一次金光，先被读成「被佛门度化」而士气崩溃，再由江湖客纠正为「修成了佛门神功——金刚不败」，"
             "百姓随即「放心了，再次笑了起来」。误读与纠正各有明确引文支撑。")),
         counter=dict(quotes=["ms_jinluo_a", "ms_woman_in_a", "xl_infer_a"], basis="explicit", text=(
             "但「纠正之后就看对了」并不成立：①九位金锣的反应是「酸的胃水翻腾」，注意力在战力与归属；"
             "②那位妇人内心仍在说「骗人的，大奉怎么可能有人在武道上超越镇北王」；"
             "③权臣对「修罗问心」的判断本身就是从关名类推出来的未经证实推断。"
             "可见看客的「懂」与「不懂」都绕不开立场与信息缺口。")),
         note=("这一读法只用「信息—立场」来解释看客反应；不借助任何篇幅、数量一类的判据，也不假设看客的反应会随情节推进而单向变准。")),
]


# ═══════════════════════════════════════════════════════════════════════
# 11. speechAsClueNotFact[] —— 人物说的话/推断，不是叙述事实
# ═══════════════════════════════════════════════════════════════════════
SPEECH_AS_CLUE = [
    dict(id="SP01", speaker="度厄罗汉", quotes=["op_speech_b"], claim="「这第三关，是你胜了。」",
         whyNotFact=("这是他的认负声明，只覆盖**第三关**；本区间没有任何叙述句宣布整场斗法的胜负，"
                     "结束时只写「满场寂静无声」。不得据此写「大乘赢了」或「佛门认输」。")),
    dict(id="SP02", speaker="度厄罗汉", quotes=["op_speech_a"], claim="许七安「拥有大佛根」、让他「茅塞顿开」",
         whyNotFact="高僧的当面称许，属人物评价；原文未以叙述口吻确认许七安真有「大佛根」。",
         note="它确实在本区间产生了后果（江湖人士扬眉吐气），但那是「众人相信了这句话」的后果。"),
    dict(id="SP03", speaker="度厄罗汉", quotes=["in_boast_a"], claim="「进了此庙，便是石头，也能点化，皈依佛门。」",
         whyNotFact="夸口，且被后文结果反证（许七安未皈依、反修成金刚不败并砸毁佛境）。"),
    dict(id="SP04", speaker="度厄罗汉", quotes=["dh_frown_a"], claim="许七安「执迷不悟」",
         whyNotFact="劝诱失败后的评语，不是对许七安心理的叙述认定。"),
    dict(id="SP05", speaker="江湖客（人群中的观众）", quotes=["ms_explain_a"], claim="「非但不是皈依佛门，反而是修成了佛门神功——金刚不败。」",
         whyNotFact=("这是**场外观众的推断**被叙述当作纠正性解释使用；原文并未以叙述句直说许七安修成了什么。"
                     "我把它记为「解释被提出」，而不是「叙述确认了金刚不败的品级或归属」。"),
         note="它在本区间的确改变了群众情绪（见 C06），这是它的可验证后果。"),
    dict(id="SP06", speaker="元景帝", quotes=["em_insist_a"], claim="「哪怕输了天机盘」",
         whyNotFact="条件式让步，表达的是他的意愿与底线，不是已经发生的结果；本区间无天机盘胜负。"),
    dict(id="SP07", speaker="监正", quotes=["jz_promise_a"], claim="「陛下放心。」",
         whyNotFact="口头承诺，本区间没有任何叙述句确认他兑现（他随后反而停手了）。"),
    dict(id="SP08", speaker="李慕白", quotes=["yl_li_a"], claim="「又有人调动众生之力？」",
         whyNotFact="疑问句，人物推断；本区间没有把盒子异动归因于众生之力的叙述句。"),
    dict(id="SP09", speaker="张慎", quotes=["yl_zhang_a"], claim="「前辈怎么又动了。」",
         whyNotFact="他对盒子的称呼与惊讶，透露此前有过一次异动，但「前辈」是谁本区间未交代。"),
    dict(id="SP10", speaker="赵守与三位大儒", quotes=["yl_zhaoshou_a"], claim="「请前辈安静。」",
         whyNotFact="请求式措辞，把封印物当作可沟通对象；这是他们的处置方式，不是对盒子性质的叙述说明。"),
    dict(id="SP11", speaker="楚元缜（对恒远）", quotes=["ms_chu_a"], claim="「稳了。」回头找许宁宴讨要金刚不败……晋升三品金刚也不是不可能",
         whyNotFact="朋友间的乐观议论与品级推测，非叙述事实；本区间没有任何后续验证。"),
    dict(id="SP12", speaker="许新年", quotes=["dh_xxn_a"], claim="「我在想应该从哪个角度捅他一刀。」",
         whyNotFact="戏言，且指向的是对度厄罗汉的敌意而非已发生的行动。"),
    dict(id="SP13", speaker="许七安（内心）", quotes=["ql_feel_a"], claim="「我好像又感觉到众生之力了」",
         whyNotFact="内心感受，且用「好像」自我限定；不能升级为「清光就是众生之力」的事实认定。"),
    dict(id="SP14", speaker="权臣与贵族（叙述转述其推断）", quotes=["xl_infer_b"], claim="「连凶残成性，茹毛饮血的修罗族都能度化，还度不了一个许七安？」",
         whyNotFact="叙述转述的众人推断（free_indirect），不是叙述对结果的预言；结果恰恰相反。"),
]


# ═══════════════════════════════════════════════════════════════════════
# 12. textualNotes[] —— 文本层面的观察（含作者区）
# ═══════════════════════════════════════════════════════════════════════
TEXTUAL_NOTES = [
    dict(id="TX01", topic="作者区", quotes=["nm_author_a", "nm_author_b"], basis="explicit",
         note=("末尾「PS：感谢……盟主打赏」起至片末为作者区（致谢与创作自述），不是叙事正文。"
               "本候选的全部叙事引文都落在作者区起点之前，作者区引文只出现在本分区与 authorRegionEvidence 里。")),
    dict(id="TX02", topic="同一人物的两个称法", quotes=["nm_de_b"], basis="explicit",
         note=("叙述段称「度厄罗汉」，引述其**声音**时称「度厄大师」（「度厄大师的声音传了进来」），"
               "前文另有「陆压道君」式的第三人称称呼。本候选统一用「度厄罗汉」，"
               "并在需要逐字引用时保留原文的「度厄大师」。不把两个称法当成两个人。")),
    dict(id="TX03", topic="开篇与上一章的接续", quotes=["nm_thunder_a"], basis="explicit",
         note="本区间以「天空中惊雷响了一声后，便没有了动静」起笔，是上一章斗法余波的收束；本章内部没有解释这声雷的来历。"),
    dict(id="TX04", topic="度厄罗汉的佛号与自称", quotes=["nm_saint_a"], basis="explicit",
         note="他引「圣人曰，学无长幼，达者为仙」——这是把儒家话头挪用到佛门语境里，本区间未作解释。"),
    dict(id="TX05", topic="「皇室专属的颜色」", quotes=["in_plan_a"], basis="inferred",
         note=("原文用「整个人染上皇室专属的颜色」这一婉语指涉好色之心（黄色），本区间未解释其具体所指。"
               "我不改写这个婉语，也不替它补一个解释。")),
    dict(id="TX06", topic="净思在本区间只出现一次", quotes=["ql_out_a"], basis="explicit",
         note=("他在本章仅以「昏迷不醒的净思」出现一次，此前坐镇第二关、与许七安交手等都在本区间之外；"
               "本候选不为他补写区外情节。")),
    dict(id="TX07", topic="「上来，自己动」的插叙", quotes=["nm_short_a"], basis="explicit",
         note="这是叙述模拟许七安修成护体神功后的自嘲场景，属假设性想象，不是已发生的事件。"),
    dict(id="TX08", topic="叙述对许七安「色批」身份的自我确认", quotes=["ms_linan_a"], basis="explicit",
         note="「临安弯起眉眼」只有动作没有言语，本候选不为她补写心理。"),
]


# ═══════════════════════════════════════════════════════════════════════
# 13. unknowns[] —— 读不出来或有矛盾的地方（比编结论有价值）
# ═══════════════════════════════════════════════════════════════════════
UNKNOWNS = [
    dict(id="U01", about="是谁／什么「召唤」了那道清光",
         why=("原文只写「这道清光，应召而来」，没有任何一句写召唤者、召唤的凭据或机制。"
              "当时在场的可能施动者包括监正（他刚蓄力又停手）与全场齐喊的众生，但都是可能，不是原文。"),
         keep="因此 C18 标 derived；不指定召唤者。"),
    dict(id="U02", about="盒中之物与刻刀是否同一物",
         why=("原文写「一道清光破盒而出……那是京城的方向」，又写「一道清光破空而来……那道清光旋即入庙，"
              "落在许七安手里。那是一把古朴的，黑色的刻刀」。两处都叫「清光」且方向一致，"
              "但**没有**任何一句直述二者的同一性。"),
         keep="我按「清光」称谓的连续把它判为同一物（F02 标 derived），并在 K06 把这一点写成知识缺口。"),
    dict(id="U03", about="压迫许七安的具体施动者是谁",
         why=("原文写「许七安的抗拒，**似乎**引来了佛像的震怒」，随后是「一道顶天立地的金身法相凝聚」"
              "与「擎天的法相……徐徐伸出了巨大的佛掌」。施动者被写成「佛像／法相」，"
              "度厄罗汉是否在操控，本区间没有一句交代。"),
         keep="C10 保留「似乎」原样，不把施动者钉死。"),
    dict(id="U04", about="那道清光是否就是「众生之力」",
         why=("「众生之力」在本区间只出现两次：李慕白的疑问句与许七安带「好像」的内心感受。"
              "两处都不是叙述认定，也没有任何一句把清光与它等同。"),
         keep="F06 显式标 unresolved；拒绝边 R08 记录了这个诱惑。"),
    dict(id="U05", about="度厄罗汉许诺的金刚不败是不是他真能给出的东西",
         why=("叙述判定这是「画饼」，但没有写他是否有能力给出、以及他是否知道许七安会自行修成。"
              "他被写成愕然（「度厄罗汉愕然不已」），这更接近「没料到」。"),
         keep="T01 action 只写到「以金刚经为饵」，不推断他的能力边界。"),
    dict(id="U06", about="天机盘的最终归属",
         why="本区间只有「要赢天机盘」与「哪怕输了天机盘」两处，没有任何胜负结算。",
         keep="F05 显式标 unresolved；NW01 说明它为什么不作为设定收录。"),
    dict(id="U07", about="天机盘究竟是什么",
         why="两处提及都把它当赌注，未写它的形制、作用或归属规则。",
         keep="按要求「没有依据就不扩物品链」，不收为 item。"),
    dict(id="U08", about="净思因何昏迷",
         why="他被写出时已「昏迷不醒」，本区间未写他何时、因何失去意识（他此前与许七安的交手在本区间之外）。",
         keep="S10 的 before 写 null 并给 beforeNote，不从区外补前值。"),
    dict(id="U09", about="这场斗法最终谁赢、佛门是否正式认输",
         why=("本区间结束于「满场寂静无声」，没有任何一句判决性叙述。"
              "能被原文支撑的只有：度厄罗汉宣布第三关许七安胜、他的金钵炸成齑粉、佛境幻灭。"),
         keep="T02 result 只写到「直起腰杆、握紧刻刀」；不写「大奉获胜」。这正是「结束≠成功」的落点。"),
    dict(id="U10", about="许七安修成的金刚不败事后是否保留、是否被佛门看见",
         why="本区间未写收尾处置，只写他昏过去、满场寂静。",
         keep="不推断；如需结论必须去区外找证据。"),
    dict(id="U11", about="「皇室专属的颜色」具体所指",
         why="原文用婉语，未作解释。",
         keep="TX05 照原文保留婉语，不改写成现代汉语的直白说法。"),
    dict(id="U12", about="被称作「前辈」的盒中之物是什么",
         why="张慎称「前辈怎么又动了」，赵守等拱手「请前辈安静」，但本区间没有交代其身份，也没写它此前那次异动是什么。",
         keep="F07 显式标 unresolved。"),
    dict(id="U13", about="许七安以好色自污是否真的起了抵御度化的作用",
         why=("原文只写他这么做并「满意的颔首」才进庙；随后他被佛光「在瞬间压垮了他的意志」。"
              "两处的关系（自污有效但不够？还是根本无效？）本区间没有交代。"),
         keep="C03 的机制只写到他「把老色批身份当成护身符」这一意图，不写成有效的防御。"),
    dict(id="U14", about="worldSettings 的 institution 三分类对本区间两条 rule 的适配",
         why=("`declared`（只有诏/令/法）/ `executed`（有执行动作）/ `misunderstood`（人物的理解）"
              "是按诏令法设计的。本区间的 W01 与 W03 是叙述直述的**规则/修习条件**，"
              "既没有诏令法文本，也没有针对它的执行或处罚动作。"),
         keep=("我把它们记为 declared 并在 institutionNote 里写明理由与张力，"
               "而不是硬套 executed 来显得「更实」。这一判断本身请复核者重点看。")),
]


# ═══════════════════════════════════════════════════════════════════════
# 14. selfCritique[] —— 本段我最可能读错的三处（及其理由）
# ═══════════════════════════════════════════════════════════════════════
SELF_CRITIQUE = [
    dict(id="SC01", risk="把「盒中之物＝刻刀」当成叙述事实",
         why=("原文通篇没有一句写盒子里装的就是刻刀，我是靠「清光」这一称谓在前后三处的连续"
              "（破盒而出 → 破空撞入佛境 → 旋即入庙现形为刻刀）来判定的，而且中间没有出现第二个清光来源。"
              "我仍然这么判断，因为若不这样读，「刻刀从哪来」在本区间就没有任何线索，"
              "而叙述特意用同一个词并给出「京城的方向」这一空间桥梁。"),
         mitigation="F02 标 derived 而非 explicit，并在 U02/K06 两处显式写出这是我的推断。"),
    dict(id="SC02", risk="把「金刚法相睁眼」与「佛像震怒」合成同一个施动者",
         why=("原文对前者只写「那位眯眼的金刚法相，忽然睁开了眼睛」，对后者写「许七安的抗拒，似乎引来了佛像的震怒」，"
              "施动者分别是「法相」与「佛像」，且后句带「似乎」。"),
         mitigation="C07 与 C10 分成两条边，C10 保留「似乎」原样，并在 U03 写明施动者未定。"),
    dict(id="SC03", risk="把「全场齐喊不跪」当成许七安破局的充分原因",
         why=("支持这一读法的只有两句：一句带「好像」的内心感受，一句未写召唤者的「应召而来」。"
              "把群众的呼声写成获胜主因，会把人物内心感受与一个未指明的机制当成因果链。"),
         mitigation="C13/C18 都标 derived，F06 标 unresolved，U01/U04 逐条写明缺口；"
                    "同时也不走向另一个极端（否认任何关联），因为叙述确实把两段紧接写出。"),
    dict(id="SC04", risk="把「度厄罗汉宣布第三关许七安胜」读成整场斗法大奉获胜",
         why="「这第三关，是你胜了」明确限定了范围；本区间结束时只写「满场寂静无声」，没有任何判决句。",
         mitigation="T02 的 result 只写到可验证的直接结果；U09 显式写明胜负宣告在本区间之外。这是「结束≠成功」的落点。"),
]


# ═══════════════════════════════════════════════════════════════════════
# 15. authorRegionEvidence[] —— 作者区边界（供复核者核对叙事/作者区切分）
# ═══════════════════════════════════════════════════════════════════════
AUTHOR_REGION = dict(
    quotes=["nm_author_a", "nm_author_b"],
    note=("末尾作者区自「    PS：感谢『沛哥大大』和『城北徐工』的盟主打赏。」起，到片末的「------------」为止。"
          "叙事正文在「满场寂静无声。」之后即结束。除本分区与 textualNotes 的 TX01 外，"
          "本候选没有任何叙事分区引用作者区文字（构建期断言）。"),
)
