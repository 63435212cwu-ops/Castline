# -*- coding: utf-8 -*-
"""第七十章 赴会 —— 任务五元组 / 因果边 / 被拒边。

本文件只写**引文键**（见 quotes_0299.py）与文字判断；start/end/occ/para 全部由
build_candidate.py 现场构造并断言，本文件不含任何手写偏移数字。

五栏纪律：同一任务里，五个栏位的引文键**两两不重复**，且字符区间两两不相交
（build_candidate.py 的 A4 断言）。某一栏在原文区间内确实没有依据时写 None，
并在同名字段 <栏>Note 里写明**为什么没有**。
"""

TASKS = [
    # ── 书房线 ────────────────────────────────────────────────────────────
    {
        "id": "T01",
        "who": "许新年（许二郎）",
        "objective": {
            "text": "要大哥陪他一起去文会。这句是他自己说的目标，不是叙述者的认定；"
                    "他先绕了一大圈推演，被大哥说「听不懂」之后才把真实诉求讲出来。",
            "basis": "explicit",
            "quotes": ["q_want_together"],
        },
        "objectiveNote": "目标是人物自述（dialogue），我按他本人的原话记录，不代他补动机。",
        "obstacle": {
            "text": "许七安当面拒绝，并且给出的不是「没空」而是身份理由：兄弟在官场上不能是一路人。",
            "basis": "explicit",
            "quotes": ["q_cannot_together", "q_not_same_path"],
        },
        "obstacleNote": None,
        "action": {
            "text": "他先用一句挖苦把话挑明（把大哥与铃音并称），再点破大哥没听懂他的意思——"
                    "即：前面那一大段推演本就是在为「同去」这个请求铺垫。",
            "basis": "explicit",
            "quotes": ["q_speak_plainly", "q_pace_think", "q_ask_brother",
                       "q_compared_lingyin", "q_not_get_it"],
        },
        "actionNote": "五个动作按时间排列：大哥先要求「有话直说」，他在屋里踱步推演，"
                      "推完转向大哥追问（「大哥，你说句话啊」），被大哥的岔开惹恼后才挖苦"
                      "「大哥几时与铃音一般笨了」，最后点破自己的真实意图。",
        "result": {
            "text": "没有要到同行。他「默然片刻」应了一声，接受被拒——本区间内没有任何他改变大哥主意的后续，"
                    "也没有任何他另找帮手的动作。",
            "basis": "explicit",
            "quotes": ["q_silent_yes"],
        },
        "resultNote": None,
        "cost": None,
        "costNote": "本区间未写许新年为这次请求付出可辨认的代价：被拒之后原文只写他「嗯」了一声"
                    "并认同大哥的分道逻辑，没有写他损失什么、放弃什么、或因此受罚。"
                    "不把「没去成」这件事本身改写成代价（那是 result 一侧）。",
        "costQuotes": [],
    },
    {
        "id": "T02",
        "who": "许七安",
        "objective": {
            "text": "先分辨这张请柬到底是寻常文会还是另有蹊跷——他给二郎的是一个判别式："
                    "同窗也有请柬就是寻常文会，独独请了二郎一位云鹿书院学子就必有蹊跷。",
            "basis": "inferred",
            "quotes": ["q_test_criterion"],
        },
        "objectiveNote": "该句原文是**判据**不是目标宣言；目标（先辨真伪）由判据反推，故记 inferred，"
                         "不把它写成许七安明说过「我要查清」。",
        "obstacle": {
            "text": "时间不够：文会就在次日上午，一晚之间来不及在同窗里核对请柬。"
                    "这条时间约束在原文里由许二郎自己陈述，不是叙述者的认定。",
            "basis": "explicit",
            "quotes": ["q_no_time", "q_wenhui_tomorrow"],
        },
        "obstacleNote": "两条引文都是人物说的话（dialogue）；我记录的是「他陈述了这个约束」这一事实，"
                        "并未把「真的来不及」当作叙述认定。",
        "action": {
            "text": "提出可执行的核实办法：去问其他中贡士的同窗有没有收到请柬。",
            "basis": "explicit",
            "quotes": ["q_ask_peers"],
        },
        "actionNote": None,
        "result": None,
        "resultNote": "本区间**没有任何核实结果**：没有人去问同窗，也没有任何同窗的回音。"
                      "二郎紧接着讲的是他自己的推断（「王首辅这是根本不给我反应的机会」），"
                      "那是他的猜测而不是核实所得，因此不写进 result（该句见 R04 的拒绝理由）。",
        "cost": None,
        "costNote": "本区间未出现许七安为这条建议付出代价的描写：他提完建议后只是把决定权交回二郎"
                    "（「二郎自己定夺吧」），没有损失、支出或受罚。",
        "costQuotes": [],
    },
    {
        "id": "T03",
        "who": "王贞文（当朝首辅）",
        "objective": None,
        "objectiveNote": "**本区间没有一句写王贞文想要什么。** 请柬只写他邀请许二郎参加文会、"
                         "附一句「携妹同往」；凡是涉及他动机的句子（忌惮、扼杀、不给他反应机会、"
                         "文会上有阴谋）全部出自许新年的推测或自问自答，原文没有叙述认定。"
                         "按红线「不许把人物说的话当成叙述事实」，此栏记 null 而不是补一个合理动机。",
        "obstacle": None,
        "obstacleNote": "**本区间没有写他遇到任何阻力。** 请柬已经送到许二郎手里、文会定在次日上午，"
                        "原文未写任何人阻拦、拒绝或回绝这场邀请（二郎最终也确实动身了，见 T10）。",
        "action": {
            "text": "以请柬邀请许新年参加文会，并在请柬上写明「携妹同往」——"
                    "这两件事都是叙述直述的（「邀请人是当朝首辅王贞文」「上面有句话很有意思：携妹同往」）。",
            "basis": "explicit",
            "quotes": ["q_inviter", "q_invite_content"],
        },
        "actionNote": "原文未写递送过程（谁送、何时送），只写请柬已在二郎手里并被他拍到大哥面前；"
                      "这栏只断言「请柬存在且写明这两点」，不推断他如何发出。",
        "result": None,
        "resultNote": "**本区间没有这场邀请的结果。** 文会定在「明日上午」，全章写到章末也只到"
                      "「马车抵达王府」为止：文会是否召开、他图的是什么、二郎是否落入什么局，"
                      "区间内一个字都没有。这正是「结束≠成功」——抵达不是达成。",
        "cost": None,
        "costNote": "本区间未写他为这次邀请付出任何代价（无花费、无损失、无受阻的描写）。",
        "costQuotes": [],
    },

    # ── 打更人衙门：姜律中 ────────────────────────────────────────────────
    {
        "id": "T04",
        "who": "姜律中（金锣，四品武夫）",
        "objective": {
            "text": "想弄懂堂里传的那两句「口诀」到底深在何处。原文没有一句写他明说想要什么，"
                    "这栏由他的后续行为反推：他先旁听、再打算去请教魏公。",
            "basis": "inferred",
            "quotes": ["q_ask_wei"],
        },
        "objectiveNote": "**这是归纳不是原文直述**：他从未说过「我要弄懂」。"
                         "我引的句子是他的内心打算（inner），不是目标宣言。",
        "obstacle": {
            "text": "他听不懂。原文把他的困惑写得很具体：两句话听起来毫无理解障碍，"
                    "但他觉得背后潜藏着难以想象的深奥——即障碍不在字面而在他的领悟。",
            "basis": "explicit",
            "quotes": ["q_jiang_ponder"],
        },
        "obstacleNote": None,
        "action": {
            "text": "一明一暗两套动作：当众以金锣身份训斥「当值期间聚众闲聊」，却又放行"
                    "（「你们聊你们的，记得别聚太久」）；出了院子靠墙一靠，激发四品武夫的听力继续听。",
            "basis": "explicit",
            "quotes": ["q_discipline", "q_pipe_dream", "q_dont_gather", "q_eavesdrop"],
        },
        "actionNote": "「激发听力」这个动作是叙述直述；他**为什么**要听（想学、好奇、还是别的）"
                      "原文没写，我不替他补动机。",
        "result": None,
        "resultNote": "**没有结果可写。** 区间内他两次旁听、又若有所思地离开，始终没有得到解释；"
                      "唯一的后续是「还是去问问魏公吧」这个打算（该句已作 objective 依据，"
                      "不在本栏重复引用）。打算不是获得，故 result 记 null 而不是写「他领悟了」。",
        "cost": None,
        "costNote": "本区间未写他为这次旁听付出代价：没有身份受损、没有受罚、没有花销。"
                    "「当众训斥又私下偷听」是行为上的两面，原文没有把它写成他付出的代价。",
        "costQuotes": [],
    },
    {
        "id": "T05",
        "who": "姜律中（经吏员传话）",
        "objective": {
            "text": "想知道许七安是否还需要衙门为他准备烹煮的药材——问句的由头是"
                    "「您的修为，可以尝试淬体了」。",
            "basis": "explicit",
            "quotes": ["q_herb_question"],
        },
        "objectiveNote": "这句是吏员的转述（dialogue），不是姜律中本人开口，也不是叙述认定；"
                         "原文用「姜金锣让我来问你」标明是代问。",
        "obstacle": {
            "text": "按许七安的推测，姜律中本人不好意思为这件事亲自过来，所以派了吏员。"
                    "**这是许七安的内心推测**，原文没有叙述认定；我照推测原样记录，不写成事实。",
            "basis": "inferred",
            "quotes": ["q_why_not_himself", "q_guess_kingkong"],
        },
        "obstacleNote": "两条引文都是许七安的内心（inner），且第二条原文自己就带「应该是」；"
                        "它至多说明许七安如此理解，不能证明姜律中确实不好意思。见 U06。",
        "action": None,
        "actionNote": "**本区间没有单独写「派吏员来问」这个动作。** 差遣与问句被合写在同一条转述里"
                      "（见 objective 的依据句），为遵守「同一句话不得同时充当两栏依据」，"
                      "此栏不重复引用该句，如实记 null 而不是把 objective 那句挪来凑数。",
        "result": {
            "text": "得到了明确答复：不需要再准备药材；吏员应声退走。答复是许七安给的（见 T06 一侧的叙事），"
                    "此处只记这次询问的收束。",
            "basis": "explicit",
            "quotes": ["q_no_need", "q_clerk_leaves"],
        },
        "resultNote": None,
        "cost": None,
        "costNote": "本区间未写这次询问有任何代价（无人受损、无花费、无被拒）。",
        "costQuotes": [],
    },

    # ── 打更人衙门：治安折子 ──────────────────────────────────────────────
    {
        "id": "T06",
        "who": "许七安（银锣）",
        "objective": {
            "text": "解决涌入京城的江湖人士带来的治安问题：他把它定性为「要解决这方面的事」。",
            "basis": "explicit",
            "quotes": ["q_jianghu_influx", "q_two_aspects"],
        },
        "objectiveNote": None,
        "obstacle": {
            "text": "两条阻力：一是案件已经在频发（坑门拐骗甚至入室抢劫频出不断）；"
                    "二是他选的方案本身有执行门槛——重刑之下贼人必定走极端，因此需要大量兵力、高手镇压。",
            "basis": "explicit",
            "quotes": ["q_cases", "q_heavy_law"],
        },
        "obstacleNote": None,
        "action": {
            "text": "唤来吏员口授、让吏员写折子，内容是给魏渊的三条建议："
                    "抽调京城下辖十三县兵力维持外城治安、上奏请禁军参与内城巡逻、"
                    "对入室偷盗／当街抢劫／当街寻衅滋事三档一律「斩」。",
            "basis": "explicit",
            "quotes": ["q_call_clerk", "q_write_memo", "q_three_suggestions"],
        },
        "actionNote": "「斩」在原文里是**他提的建议内容**，不是已经执行的刑罚；"
                      "原文到区间结束都没有任何执行描写（见 U05 与 R06）。",
        "result": {
            "text": "只做到「折子写完」这一步。三条建议是否被采纳、有没有上奏、"
                    "「斩」有没有落地，本区间一个字都没有。",
            "basis": "explicit",
            "quotes": ["q_after_memo"],
        },
        "resultNote": "「写完折子后」这个短语是区间内唯一标记折子完成的地方；"
                      "衬底的侍卫出场句留给 T08，避免两栏共用一句。",
        "cost": None,
        "costNote": "**本区间没有已发生的代价。** 原文对这套重刑方案只写了**模态化的可能后果**："
                    "「这或许会造成贼子铤而走险，犯下杀孽」——「或许」表示未发生，"
                    "而且承受方是贼子与路人、不是行动者本人；另有一项是执行门槛（需要大量兵力、高手），"
                    "已记入 obstacle。因此不把可能后果写成代价，也不写 0 或估算值。",
        "costQuotes": [],
        "costNullReasonQuotes": ["q_maybe_kill"],
        "costNullReasonNote": "此处引「这或许会造成……」**不是为了支撑一个代价**，"
                              "而是为了说明「为什么这一栏必须是 null」：原句自带「或许」，是未发生的可能，"
                              "不是已付出的代价。它与本任务其他四栏的引文不重复。",
    },

    # ── 两处召见 ──────────────────────────────────────────────────────────
    {
        "id": "T07",
        "who": "二公主（经韶音苑侍卫传召）",
        "objective": {
            "text": "召许七安过去。原文只有侍卫转述的这一句，没有写召见的目的。",
            "basis": "explicit",
            "quotes": ["q_second_princess"],
        },
        "objectiveNote": "「召您过去」是召见本身，不是目的；原文未写她想做什么，我不替她补一个理由。",
        "obstacle": {
            "text": "许七安把手头的事排在前面：他说「我手头还有事，晚些便去」，并且坐着没动。",
            "basis": "explicit",
            "quotes": ["q_later", "q_not_move"],
        },
        "obstacleNote": None,
        "action": {
            "text": "派韶音苑的侍卫到许七安堂口传召；被回以「晚些便去」之后，侍卫拱手离去。",
            "basis": "explicit",
            "quotes": ["q_culprit", "q_guard_leaves"],
        },
        "actionNote": None,
        "result": {
            "text": "**没有赴召。** 区间内只写到他继续翻看卷宗、约一刻钟后把卷宗放下松了口气；"
                    "没有任何「到达韶音苑／公主处」的描写，也没有第二次催促。"
                    "「晚些便去」是承诺不是到达（提及≠到达）。",
            "basis": "explicit",
            "quotes": ["q_relax"],
        },
        "resultNote": None,
        "cost": None,
        "costNote": "本区间未写这次推迟给任何一方带来代价（没有得罪、没有受责、没有损失）。",
        "costQuotes": [],
    },
    {
        "id": "T08",
        "who": "怀庆公主（经德馨苑侍卫传话）",
        "objective": {
            "text": "请许七安入宫一叙。原文只有侍卫转述的这一句。",
            "basis": "explicit",
            "quotes": ["q_huaiqing"],
        },
        "objectiveNote": "「入宫一叙」是要请，不是已发生的会面；原文没有写她想谈什么。",
        "obstacle": None,
        "obstacleNote": "**本区间没有写任何阻力。** 这句传话刚说完，场景即切到许府（「许府。」），"
                        "既没有人拦、也没有人推辞、更没有时间冲突的描写——缺依据就记 null。",
        "action": {
            "text": "派德馨苑的侍卫进来传话。",
            "basis": "explicit",
            "quotes": ["q_dexin_guard"],
        },
        "actionNote": None,
        "result": None,
        "resultNote": "**本区间没有结果。** 传话之后场景直接切到许府，许七安既没有回应、"
                      "也没有赴约或拒绝的描写。按「结束≠成功」，不因为章末的「马车抵达王府」"
                      "就写成他进了宫（抵达王府的是赴文会的人，与本次入宫之请是两回事）。",
        "cost": None,
        "costNote": "本区间未写这次邀请带来任何代价或后果。",
        "costQuotes": [],
    },

    # ── 许府线 ────────────────────────────────────────────────────────────
    {
        "id": "T09",
        "who": "许铃音（小豆丁）",
        "objective": {
            "text": "要跟二哥去文会：姐姐说不去之后，她立刻抢这个名额。",
            "basis": "explicit",
            "quotes": ["q_lingyin_volunteer"],
        },
        "objectiveNote": None,
        "obstacle": {
            "text": "二哥不是白答应的，先摆了一个条件：得去换漂亮裙子，不然不带她去。",
            "basis": "explicit",
            "quotes": ["q_condition"],
        },
        "obstacleNote": "她此前的阻力（二哥想把她抖开）写在 action 一侧，两侧不共用同一句。",
        "action": {
            "text": "先扑上去、整个人挂在二哥腿上；二哥抖了几下没抖开——"
                    "叙述自己给出解释：这小丫头力气大的吓人。",
            "basis": "explicit",
            "quotes": ["q_hang_leg", "q_strong_girl"],
        },
        "actionNote": None,
        "result": {
            "text": "**没去成。** 她按要求回屋换好裙子出来时，二哥和姐姐已经走了；"
                    "她以「杀猪般的哭声」收场。这是本区间里目标与结果落差最直白的一处："
                    "她完成了条件，却没有得到承诺的结果。",
            "basis": "explicit",
            "quotes": ["q_change_clothes", "q_they_left", "q_cry"],
        },
        "resultNote": "「二哥和姐姐已经走了。」同时是 F01（携妹同往的回收）的依据；"
                      "跨分区复用同一句是正常的，本任务五栏之内没有复用。",
        "cost": None,
        "costNote": "本区间未写她付出代价（换裙子不是代价、被留下也不是原文写的「代价」）；"
                    "原文只写她哭，没有写她失去什么。不把「白换了一次衣服」当作代价写进 cost。",
        "costQuotes": [],
    },
    {
        "id": "T10",
        "who": "许新年（许二郎）",
        "objective": {
            "text": "两件事合在一起：把自己收拾得体面地去赴这场文会（他认定这必定才子如云、"
                    "是「这个时代最顶层的聚会之下」，务必穿得体面），以及按请柬带上玲月。",
            "basis": "explicit",
            "quotes": ["q_dress_up", "q_bring_lingyue"],
        },
        "objectiveNote": "「带上玲月」的理由他给的是「请柬是这么写的，就当带玲月去长长见识」——"
                         "前半句指请柬的「携妹同往」，后半句是他自己的说法。",
        "obstacle": {
            "text": "婶婶当场追问：参加文会便去，为何要带上玲月？他得给出理由。",
            "basis": "explicit",
            "quotes": ["q_why_lingyue"],
        },
        "obstacleNote": "玲月本人的拒绝写在 T11.result（那是婶婶那条任务的收束），"
                        "本栏不重复引用同一句。",
        "action": {
            "text": "他为出行做的具体准备：穿浅白色袍子、玉冠束发，把家里男人的腰玉都挂上；"
                    "并对婶婶和玲月解释「大哥和爹是武夫，平日里用都不用，我看搁着也是浪费」。",
            "basis": "explicit",
            "quotes": ["q_jade", "q_jade_waste"],
        },
        "actionNote": "腰玉的归属与四态见 W15（item）；此处只记他的准备动作。",
        "result": {
            "text": "**只到抵达王府为止。** 原文写「春日融融的阳光里，马车抵达王府」——"
                    "这是行程的终点，不是文会的结果：文会上有什么、他是否被针对、"
                    "「携妹同往」换来了什么，区间内全部没有写。",
            "basis": "explicit",
            "quotes": ["q_arrive_wangfu"],
        },
        "resultNote": "「抵达王府」与 T03.result 的 null 是同一件事的两面：邀请发出了（T03.action）、"
                      "人到了门口（T10.result），但结果（文会本身）不在区间内。",
        "cost": None,
        "costNote": "本区间未写他为赴会付出代价：没有花费描写、没有受阻、没有损失；"
                    "借用父兄腰玉是他的说辞，原文没有把它写成他付了代价（也未写归还）。",
        "costQuotes": [],
    },
    {
        "id": "T11",
        "who": "婶婶（许新年之母）",
        "objective": {
            "text": "把文会当成给玲月相看人家的场合，目标是把女儿嫁入豪门："
                    "「去了文会，你多看看，瞧中哪家的公子，回来要跟娘说」。",
            "basis": "explicit",
            "quotes": ["q_marry_rich"],
        },
        "objectiveNote": "这是她本人的打算（dialogue），不是叙述认定；也谈不上已执行——见 result。",
        "obstacle": None,
        "obstacleNote": "**本区间没有写她遇到阻力。** 玲月的当场拒绝写在 result 一侧（那是她这番劝说"
                        "的直接结果），此栏若再引同一句就会变成「同一句话既当阻力又当结果」；"
                        "除此之外原文没有写任何阻碍她这个计划的人和事。",
        "action": {
            "text": "拉着女儿当场叮嘱（原文作「婶婶顿时拉着女儿的说，兴奋的说：」——"
                    "「的说」是原文如此，照抄不改）。",
            "basis": "explicit",
            "quotes": ["q_pull_daughter"],
        },
        "actionNote": "原文此处的「的说」疑为「的手」之误，见 TX01；引文逐字保留。",
        "result": {
            "text": "**碰了钉子。** 玲月当场回「娘你说什么呢，我不去了」，并且「不开心的侧过身」。"
                    "她的计划在本区间内没有兑现：文会上有没有「哪家的公子」、她是否再提，都没有写。",
            "basis": "explicit",
            "quotes": ["q_lingyue_refuse", "q_turn_away"],
        },
        "resultNote": None,
        "cost": None,
        "costNote": "本区间未写她为这番话付出代价（没有争执升级、没有损失）。",
        "costQuotes": [],
    },

    # ── 打更人衙门：教坊司与「诀窍」 ──────────────────────────────────────
    {
        "id": "T12",
        "who": "众打更人（宋廷风等）",
        "objective": {
            "text": "起哄要许七安请客教坊司——点卯之后围坐喝茶嗑花生米，吹完牛皮就开始怂恿。",
            "basis": "explicit",
            "quotes": ["q_colleagues"],
        },
        "objectiveNote": None,
        "obstacle": {
            "text": "许七安当场啐回去并骂道：成天就知道去教坊司，还搬出斗法时菩提树下老僧"
                    "「美色是刮骨刀」的话来堵。",
            "basis": "explicit",
            "quotes": ["q_refuse_treat"],
        },
        "obstacleNote": None,
        "action": {
            "text": "请客要不到就改打嘴仗：反问他「咱们衙门里，谁比你嫖的更多？」",
            "basis": "explicit",
            "quotes": ["q_who_more", "q_not_paying"],
        },
        "actionNote": None,
        "result": {
            "text": "**没请成。** 区间内没有任何人动身去教坊司；收束在叙述对他人气的一句评价上——"
                    "大家其实很佩服他，因为不是他睡花魁不给钱，而是花魁想花钱睡他。",
            "basis": "explicit",
            "quotes": ["q_admire"],
        },
        "resultNote": "「教坊司」在本区间只被议论与怂恿，没有人到场，见 W09（placeState=mentioned）。",
        "cost": None,
        "costNote": "本区间未写他们为这次起哄付出代价（没有受罚、没有花销）。",
        "costQuotes": [],
    },
    {
        "id": "T13",
        "who": "众打更人（一位铜锣出面）",
        "objective": {
            "text": "想问出许七安在教坊司的「绝学」——由头是他还是铜锣、刚加入打更人时"
                    "就已经和浮香姑娘好上了，除了一首诗之外还有什么门道。",
            "basis": "explicit",
            "quotes": ["q_ask_secret"],
        },
        "objectiveNote": None,
        "obstacle": {
            "text": "许七安卖关子：先咳嗽一声说「有点渴」，把讲述卡在这里。",
            "basis": "explicit",
            "quotes": ["q_thirsty"],
        },
        "obstacleNote": "中间还有姜律中当众训斥造成的打断；那段动作与引文归 T04，本栏不重复引用。",
        "action": {
            "text": "先给了一个肯定的答复（「这确实是有诀窍的」）把胃口吊住，"
                    "再由宋廷风端茶续上下文。",
            "basis": "explicit",
            "quotes": ["q_has_secret", "q_serve_tea"],
        },
        "actionNote": "这是同僚为换取下文做的服务性动作；它是不是「代价」见 costNote。",
        "result": {
            "text": "拿到了两句「口诀」——「交浅言深」与「到底，行不行」——但得到的是"
                    "「能不能领悟，靠个人」；宋廷风当场质疑「我怀疑你在骗我们，但我们没有证据」。"
                    "即：问题没有被回答，只是被转移成一句要靠自己悟的话。",
            "basis": "explicit",
            "quotes": ["q_what_hate", "q_ponder", "q_jiaoqian", "q_first_meet",
                       "q_xing_buxing", "q_doubt", "q_not_for_everyone"],
        },
        "resultNote": None,
        "cost": None,
        "costNote": "**端茶不是代价。** 原文只写宋廷风端了一次茶，没有写他为这次求教付出什么"
                    "（无花费、无损失、无被罚）；把「倒一杯茶」写成 cost 属于把动作拔高成代价。"
                    "本区间其余人也没有代价描写。",
        "costQuotes": [],
    },
]

# ── 因果边：每条必须有方向 + 触发机制，且 ≥2 条引文 ────────────────────────
CAUSE_EDGES = [
    {
        "id": "C01",
        "from": "请柬内容（邀许二郎参加文会，附「携妹同往」）",
        "to": "许七安一眼看出许二郎为何表情古怪",
        "trigger": "他展开请柬读到那句反常要求，随即把二郎进书房时的古怪神色与请柬内容对上——"
                   "信息先于判断，判断由那句「有意思」的话触发。",
        "quotes": ["q_open_invite", "q_invite_content"],
        "basis": "explicit",
        "claimKind": "narration",
    },
    {
        "id": "C02",
        "from": "许二郎的「两头猛虎」推理（王贞文与魏渊水火不容、请他必不简单）",
        "to": "许七安也跟着警惕起来",
        "trigger": "二郎把请柬放进朝堂对立关系里解释，这套推理说服了许七安，使他从"
                   "「合情合理」的初判转为警惕。",
        "quotes": ["q_guanchang", "q_two_tigers", "q_alert"],
        "basis": "explicit",
        "claimKind": "character-inference",
        "claimKindNote": "被传导的内容（王贞文与魏渊水火不容、请他去必有蹊跷）是**人物推理**，"
                         "不是叙述认定；本边只断言「这段推理使许七安转为警惕」这一可观察的传导，"
                         "不断言推理本身为真。",
    },
    {
        "id": "C03",
        "from": "文会定在次日上午（只剩一晚）",
        "to": "「问同窗」的核实方案无法执行",
        "trigger": "时间窗口太短：从拿到请柬到文会只有一个晚上，来不及在同窗之间核对请柬，"
                   "因此判据虽已给出却没有被使用。",
        "quotes": ["q_test_criterion", "q_wenhui_tomorrow", "q_no_time"],
        "basis": "explicit",
        "claimKind": "character-statement",
        "claimKindNote": "时间约束由许二郎自己陈述（dialogue）；我记录的是「该约束挡住了方案」，"
                         "不把它写成叙述者对时间的认定。",
    },
    {
        "id": "C04",
        "from": "二郎当面提出「同去」＋许七安对官场站队的顾虑",
        "to": "许七安拒绝同行，并要求二郎与自己保持距离",
        "trigger": "机制被叙述点明：他是在告诫二郎不要与魏渊有任何牵扯——"
                   "有朝一日魏渊倒台，他受牵连难免，而二郎的身份只是他的兄弟、不是魏渊的下属，"
                   "所以二郎不能与他同路。",
        "quotes": ["q_pat_shoulder", "q_want_together", "q_cannot_together",
                   "q_serious", "q_warn_wei_yuan"],
        "basis": "explicit",
        "claimKind": "narration",
        "claimKindNote": "「大哥其实是在告诫他」是叙述对动机的直述（free_indirect 转述二郎的理解），"
                         "不是我替他补的理由。",
    },
    {
        "id": "C05",
        "from": "姜律中以金锣身份训斥「当值期间聚众闲聊」",
        "to": "众人收敛嬉皮笑脸、恭敬解释",
        "trigger": "身份与纪律一起压场：金锣开口即问责，众人立刻换姿态，并把正在做的事"
                   "（教许宁宴如何不花钱睡花魁）如实报上去。",
        "quotes": ["q_discipline", "q_jiang_appears", "q_respectful"],
        "basis": "explicit",
        "claimKind": "narration",
    },
    {
        "id": "C06",
        "from": "姜律中当众退场（「你们聊你们的」）",
        "to": "他靠墙激发四品武夫的听力，继续旁听堂内谈话",
        "trigger": "公开训斥维持了身份、也给了他离开的台阶；出院子后他不再受「在场」约束，"
                   "便用听力把堂内谈话接回来。",
        "quotes": ["q_dont_gather", "q_eavesdrop"],
        "basis": "inferred",
        "claimKind": "narration",
        "claimKindNote": "两个动作是叙述直述，但「他为什么要这么做」原文没写；"
                         "此边只把可观察的动作接成机制，标 inferred，不写成他自述的目的。",
    },
    {
        "id": "C07",
        "from": "「这是许银锣亲口说的」这一来源",
        "to": "两句口诀在打更人衙门传开、各堂口展开讨论",
        "trigger": "叙述自己给出了扩散机制：不要怀疑，因为这是许银锣亲口说的——"
                   "传言的可信度来自说话人的身份，加上「领悟即可白嫖花魁」的收益预期，"
                   "于是从堂口内扩散到各大堂口。",
        "quotes": ["q_spread", "q_because_he_said", "q_discuss"],
        "basis": "explicit",
        "claimKind": "narration",
    },
    {
        "id": "C08",
        "from": "许七安卖关子「有点渴」",
        "to": "宋廷风端茶，他随后继续讲下去",
        "trigger": "他用一句「渴」把讲述停住，同僚以端茶把下文换回来；"
                   "喝了一口润嗓子之后他才接着讲浮香的事。",
        "quotes": ["q_continue", "q_thirsty", "q_serve_tea", "q_zhu_ask"],
        "basis": "inferred",
        "claimKind": "narration",
        "claimKindNote": "三个动作紧接且方向一致，但叙述没有用因果连接词；"
                         "「交换」这层意思是我读出来的，故不标 explicit。",
    },
    {
        "id": "C09",
        "from": "江湖人士涌入京城、治安案件频出不断",
        "to": "许七安上折子，向魏渊提三条建议",
        "trigger": "案件量上升被他定性为要解决的事，于是从「两方面入手」，落成折子里的三条建议。",
        "quotes": ["q_cases", "q_two_aspects", "q_three_suggestions"],
        "basis": "explicit",
        "claimKind": "narration",
    },
    {
        "id": "C10",
        "from": "第三条的「斩」（重刑）",
        "to": "前两条（抽调十三县兵力、请禁军巡逻）成为必需",
        "trigger": "机制由叙述直接给出：重刑之下贼人必定走极端，因此需要大量兵力、高手镇压——"
                   "前两条是为第三条做铺垫。",
        "quotes": ["q_heavy_law", "q_three_suggestions"],
        "basis": "explicit",
        "claimKind": "narration",
    },
    {
        "id": "C11",
        "from": "婶婶把文会当成相看人家、嫁入豪门的场合",
        "to": "玲月不快并当场拒绝",
        "trigger": "她的婚事被母亲当众摆到台面上（「瞧中哪家的公子，回来要跟娘说」），"
                   "反感随即以一句「我不去了」和侧过身表达出来。",
        "quotes": ["q_marry_rich", "q_lingyue_refuse"],
        "basis": "inferred",
        "claimKind": "narration",
        "claimKindNote": "两句紧接且语义相对（一个要她看公子、一个说不去），"
                         "但原文没有写「因为娘这么说所以我不去」；机制是我的读法，故标 inferred。",
    },
    {
        "id": "C12",
        "from": "铃音挂在二郎腿上、他抖不开",
        "to": "二郎答应带她（附加「换漂亮裙子」的条件）",
        "trigger": "体力上摆脱不掉（叙述点明这小丫头力气大的吓人），他只能以条件换脱身："
                   "「行吧，但你得去换漂亮裙子，不然不带你去。」",
        "quotes": ["q_lingyin_head", "q_hang_leg", "q_strong_girl", "q_condition"],
        "basis": "explicit",
        "claimKind": "narration",
    },
    {
        "id": "C13",
        "from": "「换漂亮裙子」这个条件",
        "to": "铃音回屋换衣，期间二哥与姐姐出发，她出来时人已走、大哭",
        "trigger": "条件把她支开去更衣；换装耗时正好与出发错开，于是她完成条件却错过了车。",
        "quotes": ["q_condition", "q_they_left", "q_cry"],
        "basis": "derived",
        "claimKind": "narration",
        "claimKindNote": "原文写了条件、写了「已经走了」、写了她哭，但**没有写谁决定先走**；"
                         "把三段接成一条时间机制是跨段推导（derived），不写成叙述认定。",
    },
    {
        "id": "C14",
        "from": "二公主的召见（许七安手头有卷宗）",
        "to": "召见被推迟：他继续翻看卷宗，约一刻钟后才放下",
        "trigger": "他明确把手头的事排在召见之前（「我手头还有事，晚些便去」），"
                   "并且坐着没动；于是召见在这一刻钟里被挂起。",
        "quotes": ["q_second_princess", "q_not_move", "q_relax"],
        "basis": "explicit",
        "claimKind": "narration",
    },
]

# ── 被拒边：时间相邻 / 同场景 / 人物说法，都不当因果 ──────────────────────
REJECTED_EDGES = [
    {
        "id": "R01",
        "from": "许七安写完折子",
        "to": "德馨苑的侍卫进来传怀庆公主之请",
        "why": "两件事在原文里紧接（「写完折子后，又有侍卫进来」），但没有任何机制把折子与"
               "怀庆的邀请连起来：侍卫来传的是公主的话，与折子内容无关。"
               "这正是「时间相邻当因果」的形态，拒绝连边。",
        "quotes": ["q_after_memo", "q_dexin_guard"],
    },
    {
        "id": "R02",
        "from": "二公主召见许七安",
        "to": "怀庆公主请许七安入宫",
        "why": "两次召见先后发生、都由侍卫传达，但原文没有一句把后者写成前者的结果"
               "（也没有写两人通气、竞争或先后安排的缘由）。同场景顺序不构成因果。",
        "quotes": ["q_second_princess", "q_huaiqing"],
    },
    {
        "id": "R03",
        "from": "铃音在院子里大哭",
        "to": "二郎在文会上遇到变故",
        "why": "本区间在「马车抵达王府」处收束，此后没有任何关于文会的文字；"
               "把哭声当作后续变故的铺垫，等于用区间外的想象补因果。",
        "quotes": ["q_cry", "q_arrive_wangfu"],
    },
    {
        "id": "R04",
        "from": "「王贞文和魏渊是两头猛虎、水火不容」",
        "to": "「文会上必定有阴谋诡计等着我」",
        "why": "这是许新年的人物推理（dialogue），不是叙述认定的因果；"
               "而且他在同一段里自己就把这条推理推翻了——「他要对付我，根本不需要阴谋诡计」。"
               "把角色猜测当因果，正是红线「把说法当事实」的形态。",
        "quotes": ["q_two_tigers", "q_no_need_scheme"],
    },
    {
        "id": "R05",
        "from": "婶婶说要把玲月嫁入豪门",
        "to": "玲月在文会上被许配人家",
        "why": "计划不是结果：本区间只写她说出打算、以及玲月当场拒绝，"
               "没有任何相看、议亲、许配的落地描写。",
        "quotes": ["q_marry_rich", "q_lingyue_refuse"],
    },
    {
        "id": "R06",
        "from": "姜律中听完口诀若有所思",
        "to": "「交浅言深／到底行不行」确实是有效的诀窍",
        "why": "他的反应只说明他没听懂（「乍一看毫无理解障碍，但又觉得背后潜藏着难以想象的深奥」），"
               "不构成对内容真伪的验证；叙述也没有裁决许七安那套说法是真是假。"
               "宋廷风的当场质疑同样是「没有证据」而非证伪。",
        "quotes": ["q_jiang_ponder", "q_doubt"],
    },
    {
        "id": "R07",
        "from": "春日融融的阳光里，马车抵达王府",
        "to": "文会赴会成功／目的达成",
        "why": "「抵达」是行程终点，不是目标达成；原文没有写文会开始、没有人被针对、"
               "也没有写「携妹同往」换来了什么。按「结束≠成功」，拒绝把抵达当结果。",
        "quotes": ["q_arrive_wangfu"],
    },
]
