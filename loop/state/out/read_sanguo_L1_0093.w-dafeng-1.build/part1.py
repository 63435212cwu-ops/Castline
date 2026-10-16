# -*- coding: utf-8 -*-
"""第九十四回精读：内容分区。

引文键取自 quotes.py，偏移由 build.py 用 text.find 解析。
本文件只负责「哪一栏引哪句、basis 是什么、没说清的地方怎么标注」。
"""

# ═══════════════════════════════════════════════════════════════════
# 1. tasks[]  五元组：objective / obstacle / action / result / cost
#    每栏自带 quotes[]；同一 task 内五栏的引文区间**两两不相交**
#    （由 build.py 强制检查，禁止同一句同时当多栏依据）。
#    某栏在本区间确无依据 ⇒ null + <栏位>Note 写明为什么没有。
# ═══════════════════════════════════════════════════════════════════
tasks = []
def add_task(tid, title, actor, objective, obstacle, action, result, cost):
    t = {"id": tid, "title": title, "actor": actor}
    for name, v in (("objective", objective), ("obstacle", obstacle),
                    ("action", action), ("result", result), ("cost", cost)):
        if v is None:
            t[name] = None
        else:
            t[name] = v
    tasks.append(t)


# ── T01 魏方求羌援 ───────────────────────────────────────────────
add_task("T01", "郭淮献策求救西羌，曹真遣使赍书", "郭淮（献策）· 曹真（采纳）· 魏使（执行）",
    {"text": "郭淮要曹真据住险阻，遣人从小路入羌中求救、许以和亲，使羌人起兵袭蜀兵之后，魏再以大兵夹击。",
     "basis": "explicit", "voice": "character",
     "note": "这是郭淮对曹真说的话（「郭淮谓曹真曰」）：目标出自人物之口，不是叙述层对局势的判断。"
             "「岂不大胜」是反问，不是既成结果。",
     "quotes": [("guohuai_plan", "mixed")]},
    None,
    {"text": "曹真采纳后当即遣人星夜驰书赴羌。", "basis": "explicit", "voice": "narration",
     "quotes": [("congzhi", "narration")]},
    {"text": "羌方允诺出兵：雅丹以「素相往来」「且许和亲」为由主张依允，彻里吉从其言，命雅丹与越吉起羌兵十五万。",
     "basis": "explicit", "voice": "mixed",
     "note": "「理合依允」是雅丹的进言（character），起兵十五万是叙述层（narration），同栏故为 mixed。",
     "quotes": [("yadan_allow", "character"), ("cheliqi_troops", "narration")]},
    {"text": "魏方**已交付**的对价是随书送出的金珠礼物（「赍金珠并书到国」「送了礼物」）。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("weishi_jinzhu", "narration")]})
tasks[-1]["obstacleNote"] = ("本区间未出现郭淮此策的阻碍描写：郭淮进言后原文只写「真从之」，"
                             "既无反对也无需要克服的条件。不把后文羌兵被破当作本条的 obstacle —— "
                             "那发生在结果之后，不是事前阻碍。")

# ── T02 羌国发兵扣关 ─────────────────────────────────────────────
add_task("T02", "羌国受魏请发兵，直扣西平关", "彻里吉 · 雅丹丞相 · 越吉元帅",
    {"text": "雅丹主张依允所求，其理由是「我与魏国素相往来，今曹都督求救，且许和亲」——羌方要的是履约与和亲之利。",
     "basis": "explicit", "voice": "character",
     "note": "「理合依允」是雅丹的进言，非叙述层对局势的判定。",
     "quotes": [("yadan_allow", "character")]},
    {"text": "阻碍来自蜀方的反应：羌兵扣关的消息传到蜀方后，孔明当即问众将「谁敢去退羌兵」，蜀方开始派兵应援。",
     "basis": "inferred", "voice": "character",
     "note": "降级说明：孔明问将证明**存在对手反应**，但原文没有写羌兵在扣关时被挡住或受阻的动作；"
             "把「蜀方来援」当作羌兵行动的阻碍属归纳，故 basis=inferred。"
             "又：该句是孔明的发问（character），不是叙述层对局势的判定。",
     "quotes": [("kongming_ask", "character")]},
    {"text": "彻里吉从其言，命雅丹与越吉起羌兵十五万，备铁车兵等器，领兵直扣西平关。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("cheliqi_troops", "narration"), ("kou_xiping", "narration")]},
    {"text": "直接结果是关隘守将告急：守关蜀将韩祯急差人赍文报知孔明——羌兵压境迫使蜀方求援（原文未写关隘失守）。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("hanzhen_report", "narration")]},
    {"text": "羌方为出兵投入的**已执行**代价：起兵十五万，并备下铁车、弓弩、枪刀、蒺藜、飞锤与粮草军器等物。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("tieche_desc", "narration")]})

# ── T03 孔明遣将赴援 ─────────────────────────────────────────────
add_task("T03", "孔明遣关兴、张苞往退羌兵，以马岱为向导", "孔明 · 关兴 · 张苞 · 马岱",
    {"text": "孔明闻韩祯之报，问众将「谁敢去退羌兵」——他要的是派人退去已扣关的羌兵。",
     "basis": "explicit", "voice": "character",
     "note": "「谁敢去退羌兵」是孔明的发问（character）；此处记的是他提出的目标，不是结果。",
     "quotes": [("kongming_ask", "character")]},
    {"text": "阻碍是路途不熟：孔明自己说「汝二人要去，奈路途不熟」，因此必须另找向导。",
     "basis": "explicit", "voice": "character",
     "quotes": [("road_unfamiliar", "character")]},
    {"text": "关兴、张苞应命愿往；孔明唤马岱作向导（因其素知羌人之性、久居彼处）。",
     "basis": "explicit", "voice": "mixed",
     "note": "「某等愿往」是关张二人之语（character）；唤马岱是叙述层（narration）。",
     "quotes": [("xingbao_volunteer", "character"), ("madai_guide", "narration")]},
    {"text": "蜀兵行数日后遇羌兵，进入前线接触。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("march_and_meet", "narration")]},
    {"text": "**已执行**的兵力投入：起精兵五万，与关兴、张苞同往。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("troops_50000", "narration")]})

# ── T04 兴苞首战失利 ─────────────────────────────────────────────
add_task("T04", "关兴登山观铁车阵，三路齐进被铁车击溃", "关兴 · 张苞 · 马岱（蜀） vs 越吉（羌）",
    {"text": "关兴观阵后「无破敌之策」，回寨与张苞、马岱商议——其直接所求是先议出破铁车的打法。",
     "basis": "inferred", "voice": "narration",
     "note": "objective 由「无破敌之策」+ 回寨商议反推：原文没有一句直述关兴此时想要什么，故 basis=inferred。",
     "quotes": [("no_plan", "narration")]},
    {"text": "阻碍是铁车阵本身：铁车首尾相连、随处结寨，车上遍排兵器，「就似城池一般」。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("tieche_city", "narration")]},
    {"text": "关兴分兵三路（兴在中、苞在左、岱在右）齐进，并招三路兵径进。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("three_routes", "narration"), ("xing_advance", "narration")]},
    {"text": "羌兵分在两边、中央放出铁车如潮涌，弓弩齐发，蜀兵大败。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("tieche_release", "narration"), ("shu_defeat", "narration")]},
    {"text": "**已执行**的代价：马岱、张苞两军先退，关兴一军被羌兵裹住、直围入西北角，与主力失联。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("xing_surrounded", "narration")]})

# ── T05 孔明定雪计 ───────────────────────────────────────────────
add_task("T05", "孔明观阵后定雪中诱敌之计", "孔明 · 马岱 · 张冀 · 关兴 · 张苞 · 姜维",
    {"text": "孔明登高阜观看铁车阵后说「此不难破也」——其目标是以计破铁车、退羌兵。",
     "basis": "explicit", "voice": "mixed",
     "note": "「此不难破也」是孔明的话（character）；登高阜观看铁车阵是叙述层（narration）。",
     "quotes": [("view_high", "narration"), ("easy_to_break", "character")]},
    {"text": "阻碍是铁车结阵难攻（「铁车密围，就如城池」），且马岱自认「此军无计可退」，只能请孔明用计。",
     "basis": "explicit", "voice": "mixed",
     "note": "「铁车密围」是叙述层；「此军无计可退」是马岱的话（character）。",
     "quotes": [("tieche_siege", "narration"), ("madai_hold", "character")]},
    {"text": "孔明分付马岱、张冀「如此如此」；断言「今彤云密布，朔风紧急，天将降雪，吾计可施矣」；"
             "并令关兴张苞埋伏、令姜维领兵出战（遇铁车即退，寨口虚立旌旗不设军马）。",
     "basis": "explicit", "voice": "mixed",
     "note": "「天将降雪，吾计可施矣」是孔明之言（character），分付与下令是叙述层（narration）。",
     "quotes": [("assign_madai", "narration"), ("snow_prediction", "character"),
                ("ambush_order", "narration")]},
    {"text": "部署完成：「准备已定」。注意此处只到准备为止——计策尚未执行，胜负未分。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("ready", "narration")]},
    {"text": "**已执行**的兵力投入：先命赵云、魏延各引一军埋伏，再点三万军，带姜维、张冀、关兴、张苞亲赴马岱寨。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("zhaoyun_weiyan", "narration")]})

# ── T06 雪中诱敌 ─────────────────────────────────────────────────
add_task("T06", "羌兵追入空寨，落坑堑、铁车自相践踏", "越吉 · 雅丹（羌，追）· 孔明 · 姜维（蜀，诱）",
    {"text": "羌方的目标（由雅丹主张）是趁势攻破孔明营寨：他判「此诸葛亮诡计，虚设疑兵耳，可以攻之」。",
     "basis": "explicit", "voice": "character",
     "note": "这是雅丹对越吉说的话：属羌方的判断与主张，不是叙述层事实。",
     "quotes": [("yadan_trick", "character")]},
    {"text": "羌方的阻碍先来自内部：越吉自己「心疑，未敢轻进」，是雅丹再劝才继续进军。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("yueji_doubt", "narration")]},
    {"text": "羌兵抢入寨栅、直赶过山口；雅丹称「不足为惧」并催大兵追赶，越吉催兵急追。",
     "basis": "explicit", "voice": "mixed",
     "note": "「不足为惧」是雅丹的话（character），抢寨追赶是叙述层（narration）。",
     "quotes": [("qiang_enter", "narration"), ("yadan_not_afraid", "character")]},
    {"text": "落坑：一声响如山崩地陷，羌兵俱落坑堑；背后铁车收止不住并拥而来、自相践踏。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("pit", "narration")]},
    {"text": "**已执行**的代价：遭关兴、张苞两军冲出（万弩齐发），背后姜维、马岱、张冀三路又到，被六路合击。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("ambush_spring", "narration")]})

# ── T07 越吉死、雅丹擒 ───────────────────────────────────────────
add_task("T07", "越吉败逃正逢关兴被杀，雅丹为马岱活捉", "关兴 · 马岱（蜀） vs 越吉 · 雅丹（羌）",
    {"text": "关兴截住败逃的越吉：原文写越吉「望后面山谷中而逃，正逢关兴」。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("yueji_flee_meet", "narration")]},
    {"text": "越吉此前已表现过脱身能力——他落水后「跃水而走」，故并非束手待擒。",
     "basis": "inferred", "voice": "narration",
     "note": "「吉跃水而走」是前一次脱逃的**事实**；把它当作本次交锋的阻碍属归纳，故 basis=inferred。",
     "quotes": [("yueji_escape", "narration")]},
    {"text": "雅丹被马岱活捉，押解赴大寨。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("yadan_captured", "narration")]},
    {"text": "越吉被关兴举刀砍死于马下；铁车兵大乱。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("kansha", "narration"), ("tieche_chaos", "narration")]},
    {"text": "**已执行**的损失：越吉本人先落水（「连人带马，平白地倒下水来」），随后失去坐骑（「关兴得了越吉马」）。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("yueji_fall", "narration"), ("get_horse", "narration")]})

# ── T08 孔明释雅丹结盟 ───────────────────────────────────────────
add_task("T08", "孔明释雅丹、尽还所获、与羌结盟", "孔明 · 雅丹",
    {"text": "孔明要羌国不再助魏：他对被押来的雅丹说「吾今放汝回去，说与汝主：吾国与尔乃邻邦，永结盟好，勿听反贼之言」。",
     "basis": "explicit", "voice": "character",
     "note": "这是孔明对雅丹说的话：目标出自人物之口。",
     "quotes": [("kongming_terms", "character")]},
    None,
    {"text": "孔明叱武士去其缚、赐酒压惊、用好言抚慰。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("kongming_untie", "narration")]},
    {"text": "雅丹深感其德；众皆拜谢而去——羌方接受了释放。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("yadan_moved", "narration"), ("all_bow", "narration")]},
    {"text": "**已执行**的代价：蜀方放弃全部缴获——所获羌兵及车马器械「尽给还雅丹，俱放回国」。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("return_all", "narration")]})
tasks[-1]["obstacleNote"] = ("本区间未出现此事的阻碍描写：雅丹此时已是「马岱押过」的俘虏，"
                             "孔明要放他只需下令，原文没有任何反对、条件不足或雅丹拒绝的记述。"
                             "不把「雅丹是俘虏」当作 obstacle —— 那是处置的前提，不是需要克服的阻力。")

# ── T09 曹真郭淮误判中伏 ─────────────────────────────────────────
add_task("T09", "曹真郭淮误判蜀兵退走而追击，折两先锋", "曹真 · 郭淮 · 曹遵 · 朱赞（魏） vs 魏延 · 赵云（蜀）",
    {"text": "郭淮要趁蜀兵退走时追击取胜：他判「此因羌兵攻击，故尔退去」，遂分两路追赶。",
     "basis": "explicit", "voice": "mixed",
     "note": "「此因羌兵攻击，故尔退去」是郭淮的判断（character）——**该判断是错的**，"
             "原文紧接着写蜀兵乱走后伏兵闪出；「遂分两路追赶」是叙述层（narration）。",
     "quotes": [("guohuai_happy", "mixed")]},
    {"text": "阻碍是蜀方的伏兵：追袭途中「忽然鼓声大震，一彪军闪出，为首大将乃魏延也」。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("weiyan_appear", "narration")]},
    {"text": "曹真连日望羌人消息，伏路军报「蜀兵拔寨收拾起程」；魏兵随后追袭乱走的蜀兵。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("caozhen_wait", "narration"), ("shu_flee", "narration")]},
    {"text": "曹遵被魏延一刀斩于马下；朱赞被赵云一枪刺死。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("caozun_killed", "narration"), ("zhuzan_killed", "narration")]},
    {"text": "**已执行**的代价：折了两个先锋，曹真「哀伤不已」，只得写本申朝乞拨援兵。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("two_vanguards", "narration")]})

# ── T10 钟繇保举、曹睿复司马懿职 ─────────────────────────────────
add_task("T10", "钟繇以全家保举司马懿，曹睿降诏复职", "钟繇 · 曹睿 · 司马懿（受诏）",
    {"text": "魏主要的是退蜀兵：近臣奏曹真数败于蜀、折两先锋、羌兵又折无数，「其势甚急」，请陛下裁处。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("crisis_report", "narration")]},
    {"text": "阻碍有二：钟繇判「曹真虽久用兵，非诸葛亮对手」；华歆则主张须陛下御驾亲征，否则「长安有失，关中危矣」。",
     "basis": "explicit", "voice": "character",
     "note": "两条都是臣下的奏言（character）；「长安有失，关中危矣」是华歆预言的后果，本区间未发生。",
     "quotes": [("zhongyou_assess", "character"), ("huaxin", "character")]},
    {"text": "钟繇报出人选「骠骑大将军司马懿也」，并追述诸葛亮曾惧此人、故散流言使陛下疑而去之。",
     "basis": "explicit", "voice": "character",
     "note": "报出人选与追述旧事都是钟繇的奏言（character）。",
     "quotes": [("zhongyou_name", "character"), ("liuyan", "character")]},
    {"text": "曹睿降诏，遣使持节复司马懿官职、加为平西都督，起南阳诸路军马前赴长安；使命星夜望宛城去了。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("edict", "narration"), ("envoy_go", "narration")]},
    {"text": "**已执行**的代价：钟繇以「全家良贱」作保举的担保（他自陈的风险成本）。",
     "basis": "explicit", "voice": "character",
     "note": "「臣以全家良贱，保举一人」是钟繇自述其担保，属人物之言而非叙述层确认的既成损失；"
             "本栏据其自陈记为代价，并标 voiceSurface=character 以示区别。",
     "quotes": [("baoju", "character")]})

# ── T11 李丰报孟达欲举事 ─────────────────────────────────────────
add_task("T11", "李丰代父报孟达欲举事取洛阳", "李丰（李严子）· 孔明 · 孟达（未出场）",
    {"text": "孟达（经李丰转述）欲起金城、新城、上庸三处军马举事，径取洛阳；孔明取长安则「两京大定」。",
     "basis": "explicit", "voice": "character",
     "note": "整条消息是李丰转述孟达的意图（character），不是叙述层已发生的事实；"
             "「径取洛阳」在本区间始终是图谋，未执行。",
     "quotes": [("plan_luoyang", "character")]},
    None,
    {"text": "李丰陈说孟达降魏的缘由与所受恩遇（「昔日孟达降魏，乃不得已也……封为散骑常侍，领新城太守」），"
             "并呈上孟达累次书信。",
     "basis": "explicit", "voice": "character",
     "note": "孟达旧职与降魏缘由出自李丰之口（character）；「今某引来人并累次书信呈上」亦是其言。",
     "quotes": [("mengda_past", "character"), ("letters_presented", "character")]},
    {"text": "孔明大喜，厚赏李丰等——蜀方接受了这条内应线索。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("reward_lifeng", "narration")]},
    None)
tasks[-1]["obstacleNote"] = ("本区间未出现此事的阻碍描写：李丰开口即「特来报喜」，孔明「大喜」并厚赏，"
                             "原文没有写举事遇到反对或条件不足。"
                             "孟达后来被申耽申仪以「军器粮草，俱未完备」推托，那是后文对他们的佯许，"
                             "且发生在孟达处而非李丰报信这一环，不作本条的 obstacle。")
tasks[-1]["costNote"] = ("本区间未出现李丰此行或孟达举事的代价描写。"
                         "孟达降魏时所得官职赏赐（散骑常侍、新城太守、骏马金珠）是**既得利益**而非已付出的代价，"
                         "且出自李丰转述；按要求不把它折算成 cost。")

# ── T12 孔明修书预警孟达 ─────────────────────────────────────────
add_task("T12", "孔明修书令孟达提防司马懿", "孔明 · 马谡 · 孟达（受书）",
    {"text": "孔明要孟达提防司马懿：他判「今孟达欲举大事，若遇司马懿，事必败矣」「达非司马懿对手，必被所擒」。",
     "basis": "explicit", "voice": "character",
     "note": "这是孔明对马谡说的话：目标与判断都出自人物之口。",
     "quotes": [("fear_sima", "character")]},
    {"text": "阻碍是司马懿复职的消息：细作报魏主诏司马懿复职、加平西都督、起本处之兵于长安聚会，孔明因此「大惊」。",
     "basis": "explicit", "voice": "mixed",
     "note": "细作所报是转述之辞（character）；「孔明大惊」是叙述层（narration）。",
     "quotes": [("spy_report", "character"), ("kongming_shocked", "narration")]},
    {"text": "马谡建议「何不急修书，令孟达提防」；孔明从之，即修书令来人星夜回报孟达。",
     "basis": "explicit", "voice": "mixed",
     "note": "「何不急修书」是马谡的建议（character）；「孔明从之，即修书」是叙述层（narration）。",
     "quotes": [("masu_suggest", "character"), ("write_letter", "narration")]},
    {"text": "孟达览书后「笑曰：人言孔明心多，今观此事可知矣」，并回书称「司马懿即来，达何惧哉」——"
             "他**没有接受**预警。",
     "basis": "explicit", "voice": "character",
     "note": "孟达的笑语与回书内容都是人物之言（character）。此处 result 记的是「预警未被接受」这一实际反应，"
             "不是叙述层对成败的判定。",
     "quotes": [("mengda_laugh", "character"), ("mengda_delay", "character")]},
    None)
tasks[-1]["costNote"] = ("本区间未出现孔明为这次修书付出的实质代价：动用书信渠道并「令来人星夜回报」"
                         "是**执行投入**（已计入 action），不是付出物。"
                         "孟达不听劝属结果面的失败，不是孔明付出的代价。")

# ── T13 司马懿不待圣旨发兵 ───────────────────────────────────────
add_task("T13", "司马懿得密告，不待圣旨发兵擒孟达", "司马懿 · 司马师 · 申仪家人 · 李辅 · 邓贤",
    {"text": "司马懿要抢在孟达举事之前擒之：他判「此贼必通谋诸葛亮。吾先擒之，诸葛亮定然心寒，自退兵也」，"
             "其情报来自申仪家人密告与李辅、邓贤出首。",
     "basis": "explicit", "voice": "character",
     "note": "「吾先擒之…自退兵也」是司马懿之言（character）；告密与出首的具体动作见 action 栏所引叙述层。",
     "quotes": [("secret_told", "narration"), ("analysis", "character")]},
    {"text": "阻碍是奏闻程序：长子司马师劝「父亲可急写表申奏天子」，若照此办理则往复费时。",
     "basis": "explicit", "voice": "character",
     "note": "「可急写表申奏天子」是司马师的建议（character），代表制度上的正当程序要求。",
     "quotes": [("shi_advice", "character")]},
    {"text": "司马懿决意不等圣旨（「若等圣旨，往复一月之间，事无及矣」），即传令「一日要行二日之路，如迟立斩」，"
             "一面令梁畿赍檄先去新城「使其不疑」；梁畿先行，懿随后发兵。",
     "basis": "explicit", "voice": "mixed",
     "note": "「事无及矣」是司马懿之言（character）；传令、行军、遣梁畿是叙述层（narration）。",
     "quotes": [("no_wait", "character"), ("order_march", "narration"), ("liangji_first", "narration")]},
    {"text": "前军哨马捉住孟达心腹人，搜出孔明回书——司马懿由此掌握对方往来。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("capture_spy", "narration")]},
    None)
tasks[-1]["costNote"] = ("本区间未出现司马懿此行付出的代价：他抗命不待圣旨，但结果是受赏（赐金钺斧、许便宜行事），"
                         "原文没有写他因此受责、损兵或将佐阵亡。"
                         "「如迟立斩」是他**施加**于部下的军令，不是他自己付出的代价。")

# ── T14 孟达被围身死 ─────────────────────────────────────────────
add_task("T14", "孟达约内应举事，被围城破身死", "孟达（新城）· 申耽 · 申仪 · 李辅 · 邓贤 · 徐晃 · 司马懿",
    {"text": "孟达约下申仪、申耽克日举事，定「明日举事，换上大汉旗号，发诸路军马，径取洛阳」。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("mengda_ally", "narration"), ("feast_plan", "narration")]},
    {"text": "阻碍是内应早已倒向魏方：申耽、申仪「佯许之」并推托「军器粮草，俱未完备，不敢约期起事」，孟达却「信之不疑」。",
     "basis": "explicit", "voice": "narration",
     "note": "「佯许」是叙述层对二人真实立场的揭示——他们在孟达面前说的是军器粮草未备。",
     "quotes": [("fake_agree", "narration"), ("believe", "narration")]},
    {"text": "孟达登城见「右将军徐晃」旗号，大惊扯起吊桥；徐晃直来壕边喊降，孟达开弓射之，正中徐晃头额。",
     "basis": "explicit", "voice": "mixed",
     "note": "「反贼孟达，早早受降」是徐晃的喊话（character）；登城、扯桥、开弓是叙述层（narration）。",
     "quotes": [("on_wall", "narration"), ("raise_bridge", "narration"), ("mengda_shoot", "narration")]},
    {"text": "申耽、申仪自外杀来喊「反贼休走」，孟达误以为是救军而开门杀出；人困马乏，被申耽一枪刺于马下，枭其首级。",
     "basis": "explicit", "voice": "mixed",
     "note": "「反贼休走」是二人的喊话（character）；被刺与枭首是叙述层（narration）。",
     "quotes": [("betray_shout", "character"), ("killed", "narration")]},
    {"text": "**已执行**的代价：城被献（「吾等已献了城也」）余军皆降。",
     "basis": "explicit", "voice": "mixed",
     "note": "「吾等已献了城也」是李辅邓贤在城上的宣告（character）；「余军皆降」是叙述层（narration）。",
     "quotes": [("city_given", "character"), ("yujun_surrendered", "narration")]})

# ── T15 司马懿奏明获授权 ─────────────────────────────────────────
add_task("T15", "司马懿入城奏明不待圣旨之由，获赐金钺斧", "司马懿 · 曹睿",
    {"text": "司马懿要曹睿认可他不待圣旨的处置：他奏「臣闻申仪密告反情，意欲表奏陛下，恐往复迟滞，故不待圣旨，星夜而去。"
             "若待奏闻，则中诸葛亮之计也」。",
     "basis": "explicit", "voice": "character",
     "note": "全句是司马懿的奏言（character），是他对自己行为的解释与辩护。",
     "quotes": [("sima_explain", "character")]},
    None,
    {"text": "司马懿将孔明回孟达的密书奉上，作为证据。",
     "basis": "explicit", "voice": "narration",
     "quotes": [("present_letter", "narration")]},
    {"text": "曹睿大喜，赞「卿之学识，过于孙、吴矣」，赐金钺斧一对，许「后遇机密重事，不必奏闻，便宜行事」。",
     "basis": "explicit", "voice": "mixed",
     "note": "「卿之学识，过于孙、吴矣」与「不必奏闻，便宜行事」都是曹睿之言（character）；"
             "「赐金钺斧一对」是叙述层（narration）。",
     "quotes": [("praise", "character"), ("axe_grant", "mixed")]},
    None)
tasks[-1]["obstacleNote"] = ("本区间未出现此事的阻碍描写：司马懿入城见魏主后，曹睿当即大喜并加赏，"
                             "原文没有写质疑、追究抗命或任何需要克服的阻力。"
                             "曹睿先前的「此事朕亦悔之」是对**旧事**（疑司马懿而散流言）的自责，"
                             "不是对本条奏明的阻碍，故不列入。")
tasks[-1]["costNote"] = ("本区间未出现司马懿为这次奏明付出的代价：他得到的是授权与赏赐（金钺斧、便宜行事），"
                         "并非损失。不把「曾受怀疑」折算成代价 —— 那是本区间之外的旧事，且出自钟繇追述。")

# ═══════════════════════════════════════════════════════════════════
# 2. causeEdges[]  方向 + 触发机制（不是时间相邻）
# ═══════════════════════════════════════════════════════════════════
causeEdges = []
def add_edge(eid, cause, effect, mech, cq, eq, basis="explicit"):
    causeEdges.append({"id": eid, "cause": cause, "effect": effect, "mechanism": mech,
                       "basis": basis,
                       "causeQuotes": [(k, "narration") for k in cq],
                       "effectQuotes": [(k, "narration") for k in eq]})

add_edge("C02", "魏方许以和亲并赍金珠礼物到国", "彻里吉允诺起兵十五万",
    "利益与旧交使羌方履约：雅丹以「素相往来…且许和亲，理合依允」进言，彻里吉从其言即命起兵。"
    "机制是**对价换出兵**，不是两国相邻。",
    ["weishi_jinzhu", "yadan_allow"], ["cheliqi_troops"])
add_edge("C03", "羌兵直扣西平关、韩祯告急", "孔明遣兴苞马岱往退羌兵",
    "关隘告急触发蜀方应援：韩祯「急差人赍文报知孔明」，孔明闻报即问「谁敢去退羌兵」。",
    ["kou_xiping", "hanzhen_report"], ["kongming_ask"])
add_edge("C04", "铁车首尾相连、车上遍排兵器", "关兴「无破敌之策」，首战三路齐进仍大败",
    "铁车结阵形成物理屏障：关兴登山见「铁车首尾相连…就似城池一般」，故无策；"
    "交战时羌兵分在两边、中央放出铁车、弓弩齐发，蜀兵大败。",
    ["tieche_city"], ["no_plan", "tieche_release"])
add_edge("C05", "羌兵裹围关兴一军", "关兴逃向断涧、马倒落水",
    "围困迫使关兴寻路而走：军被「直围入西北角」，兴「望山谷中寻路而走」，正遇断涧只得回马，"
    "被越吉一锤正中马胯，「那马望涧中便倒，兴落于水中」。"
    "**越吉自身落水的原因原文未写**，故本边只连到关兴落水为止（另见 R01/R02）。",
    ["xing_surrounded", "escape_attempt"], ["horse_fall"])
add_edge("C06", "孔明登高观铁车阵后判「此不难破也」", "分付马岱、张冀",
    "观阵得出可破的判断后即刻派人执行：孔明见「铁车连络不绝，人马纵横」后说「此不难破也」，"
    "随即「唤马岱、张冀分付如此如此」。",
    ["view_high"], ["assign_madai"])
add_edge("C06b", "孔明判「天将降雪，吾计可施」", "令关兴张苞埋伏、令姜维退走不设军马",
    "天时被当作计策成立的条件：孔明明言「今彤云密布，朔风紧急，天将降雪，吾计可施矣」之后，"
    "紧接着才是「便令关兴、张苞二人引兵埋伏去讫；令姜维领兵出战…」。",
    ["snow_prediction"], ["ambush_order"])
add_edge("C07", "孔明虚设旌旗、寨口不设军马", "越吉心疑、雅丹力主进攻",
    "空寨与鼓琴制造「疑兵」并引出一致判断分歧：羌兵见四壁空竖旌旗回报，越吉「心疑，未敢轻进」，"
    "雅丹判为「虚设疑兵耳，可以攻之」，越吉遂进兵。",
    ["qin_voice"], ["yueji_doubt", "yadan_trick"])
add_edge("C08", "雅丹两度轻敌催兵急追", "羌兵俱落坑堑、铁车自相践踏",
    "轻敌使羌兵进入预设地形：雅丹先称「不足为惧」引大兵追赶，再称「纵有些小伏兵，何足惧哉」只顾催趱前进；"
    "随后「一声响，如山崩地陷」羌兵落坑，铁车收止不住并拥而来。",
    ["yadan_small", "yadan_not_afraid"], ["pit"])
add_edge("C09", "羌兵落坑、铁车自乱", "越吉被杀、雅丹被擒",
    "阵形崩溃后主将被截：铁车兵大乱，越吉「望后面山谷中而逃，正逢关兴」被砍死；雅丹「早被马岱活捉」。",
    ["tieche_chaos"], ["yueji_flee_meet", "yadan_captured"])
add_edge("C10", "孔明叱武士去其缚、赐酒压惊、用好言抚慰", "雅丹深感其德",
    "恩遇换取羌方归心：原文写孔明去缚赐酒用好言抚慰之后，紧接「雅丹深感其德」——"
    "**先释其缚，才有归心**；这与后文「尽给还雅丹」是两步，故分列。",
    ["kongming_untie"], ["yadan_moved"])
add_edge("C10b", "孔明将所获羌兵及车马器械尽给还雅丹", "羌众拜谢而去",
    "归还全部缴获使释放变成可验证的恩惠：原文写「遂将所获羌兵及车马器械，尽给还雅丹，俱放回国」，"
    "紧随其后即是「众皆拜谢而去」。",
    ["return_all"], ["all_bow"])
add_edge("C11", "郭淮误判蜀兵因羌兵攻击而退", "魏军分两路追赶，折曹遵、朱赞",
    "**错误判断**导致进入伏击（机制在判断，不在时间相邻）：郭淮判「此因羌兵攻击，故尔退去」遂追赶，"
    "结果是魏延闪出斩曹遵、赵云刺死朱赞。",
    ["guohuai_happy"], ["caozun_killed", "zhuzan_killed"])
add_edge("C12", "曹真折两先锋、羌兵又折无数，上表求救", "钟繇保举、曹睿降诏复司马懿职",
    "军情危急触发高层换将：近臣奏「其势甚急，今上表求救」→钟繇以全家保举司马懿→曹睿降诏复职加平西都督。",
    ["crisis_report"], ["edict"])
add_edge("C13", "孟达欲举事、司马懿复职的消息到蜀", "孔明修书令孟达提防",
    "潜在遭遇触发预警：孔明判「今孟达欲举大事，若遇司马懿，事必败矣」，马谡建议「何不急修书」，孔明从之即修书。",
    ["fear_sima"], ["write_letter"])
add_edge("C14", "金城太守申仪家人有机密事求见", "司马懿于密室得闻孟达欲反，并有李辅、邓贤随状出首",
    "告密使司马懿获得孟达举事的情报：原文先写「忽又报金城太守申仪家人，有机密事求见」，"
    "次写「懿唤入密室问之，其人细说孟达欲反之事」，再写「更有孟达心腹人李辅并达外甥邓贤，随状出首」——"
    "三段按时序推进，故一并列在果侧。",
    ["shentong_secret"], ["secret_told", "lifu_dengxian"])
add_edge("C15", "司马懿判定等圣旨会误期", "加倍行程并令梁畿先去新城安孟达之心",
    "绕开奏闻程序以争取时间：司马师劝「急写表申奏天子」，懿答「若等圣旨，往复一月之间，事无及矣」，"
    "即传令「一日要行二日之路，如迟立斩」，一面令梁畿赍檄去新城「使其不疑」。",
    ["no_wait"], ["order_march", "liangji_first"])
add_edge("C16", "哨马捉住孟达心腹人、搜出孔明回书", "司马懿确认计谋已被孔明看破，星夜催军",
    "截获书信使司马懿掌握对方全部往来：搜出孔明回书后懿「大惊曰：…吾机先被孔明识破。幸得天子有福，获此消息」，"
    "遂星夜催军前行。",
    ["capture_spy"], ["sima_realize", "press_on"])
add_edge("C17", "梁畿传假调遣令", "孟达不疑而定期举事",
    "假传调遣稳住孟达：梁畿传司马懿将令「太守可集本部军马听候调遣」，孟达问都督何日起程，"
    "得答「此时约离宛城，望长安去了」，达遂「暗喜曰：吾大事成矣」。",
    ["liangji_order", "when_start"], ["da_pleased"])
add_edge("C18", "申耽申仪佯许并推托军器粮草未备", "孟达不疑，围城时被诱出城败死",
    "内应以拖延配合围城：二人「佯许之…却报孟达言：军器粮草，俱未完备，不敢约期起事」，达「信之不疑」；"
    "围城后二人自外杀来，孟达「只道是救军到」开门杀出，遂被刺。",
    ["fake_agree", "believe"], ["thinks_rescue", "killed"])
add_edge("C19", "孟达开弓射中徐晃头额", "徐晃当晚身死",
    "箭伤致死的机制被原文明确写出：孟达「急开弓射之，正中徐晃头额」，众军救回「取了箭头，令医调治」，"
    "「当晚身死，时年五十九岁」。",
    ["mengda_shoot"], ["xuhuang_death"])
add_edge("C20", "司马懿不待圣旨星夜擒孟达", "曹睿赐金钺斧、许「便宜行事」",
    "先斩后奏的成效换来制度性授权：懿奏「恐往复迟滞，故不待圣旨，星夜而去」，睿大喜赐金钺斧一对，"
    "「后遇机密重事，不必奏闻，便宜行事」。机制是**成效改变授权规则**。",
    ["sima_explain"], ["axe_grant"])
add_edge("C21", "孟达军器粮草未备（申耽申仪之辞）", "孟达暂缓起事",
    "拖延直接改变孟达的时间表：二人报「军器粮草，俱未完备，不敢约期起事」，孟达因此未按期举事，"
    "直到梁畿来后才定「明日举事」——为司马懿争取到行军时间。",
    ["fake_agree"], ["feast_plan"])

add_edge("C22", "孔明携琴上车、引数骑入寨望后而走", "羌兵抢入寨栅、追过山口",
    "示弱动作直接把羌兵引进预设地形：越吉至寨前「但见孔明携琴上车，引数骑入寨，望后而走」，"
    "羌兵遂「抢入寨栅，直赶过山口」——诱敌靠的是让对手看到可追的目标。",
    ["kongming_qin_retreat"], ["qiang_enter"])
add_edge("C23", "曹遵、朱赞两先锋先后被斩", "曹真、郭淮被关兴张苞两路围杀",
    "前军覆没使主将失去掩护并被合围：原文写二人「见西路先锋有失，欲收兵回」，"
    "随即「背后喊声大震…关兴、张苞两路兵杀出，围了曹真、郭淮」。",
    ["caozun_killed", "zhuzan_killed"], ["surround_caozhen_full"])
add_edge("C24", "钟繇以全家保举司马懿", "曹睿降诏复其官职",
    "保举改变了魏主的人选决策：钟繇陈「非诸葛亮对手」并「以全家良贱，保举一人」，"
    "报出司马懿后，睿即降诏复职加平西都督。",
    ["baoju"], ["edict"])

# ── 被拒绝的因果边（时间相邻/同场景，但原文没有机制）────────────
rejectedCauseEdges = [
    {"id": "R01", "pair": "越吉落水 → 关兴得马",
     "why": "两事紧接，但原文写越吉落水为「忽听得一声响处…平白地倒下水来」，未给出原因，"
            "也未写它与关兴得马之间的机制；关兴得马写的是「关兴得了越吉马，牵到岸上，整顿鞍辔」，"
            "是结果陈述而非因果链。",
     "quotes": [("yueji_fall", "narration"), ("get_horse", "narration")], "basis": "explicit"},
    {"id": "R02", "pair": "岸上大将杀退羌兵 → 越吉落水",
     "why": "时序上越吉落水在前（「忽听得一声响处」），「岸上一员大将，杀退羌兵」写在关兴挣起看时之后；"
            "把落水归因于这位大将（乃至关公）是读者补的机制，原文没有把两者连起来。",
     "quotes": [("yueji_fall", "narration"), ("guangong_appear", "narration")], "basis": "explicit"},
    {"id": "R03", "pair": "曹真郭淮走脱 → 蜀兵夺渭水魏寨",
     "why": "两者是同一场战斗的连续结果，但「夺了魏寨」的直接前提是蜀兵全胜直追；"
            "原文没有写魏寨是否因二人离开而空，机制缺失，故不单列一条因果边。",
     "quotes": [("escape", "narration"), ("weishui", "narration")], "basis": "explicit"},
    {"id": "R04", "pair": "孔明回书被搜出 → 孟达被杀",
     "why": "时间上书信被截在先、孟达死在后，但孟达之死的直接机制是申耽申仪内应与围城（见 C18），"
            "不是书信本身；把两者直连会把「情报泄露」与「军事失败」混为一因。",
     "quotes": [("capture_spy", "narration"), ("killed", "narration")], "basis": "explicit"},
    {"id": "R05", "pair": "徐晃请为先锋 → 徐晃被孟达射中",
     "why": "徐晃任先锋与中箭之间隔着围城过程，原文未写其先锋身份使他处于壕边的机制，"
            "只写「坐下马收拾不住，直来到壕边」；中间环节缺失，不连边。",
     "quotes": [("xuhuang_volunteer", "narration"), ("mengda_shoot", "narration")], "basis": "explicit"},
    {"id": "R07", "pair": "曹真数败于蜀 → 郭淮献策求救西羌",
     "why": "因果上讲得通，但**在区间内的引文时序是反的**：郭淮献策在段1（472805），"
            "而「曹真数败于蜀、折了两个先锋」的唯一在区间表述在段11（475167，近臣奏），"
            "是事后追述而非事前动因；真正的战败发生在本区间之前的回目。"
            "按「引文必须支持断言」的口径，本边不成立，故不列为 causeEdge，"
            "改由此处登记（相关军情触发见 C12）。",
     "quotes": [("guohuai_plan", "narration"), ("crisis_report", "narration")], "basis": "explicit"},
    {"id": "R06", "pair": "关公显灵 → 张苞寻到关兴",
     "why": "张苞自述「忽见伯父自空而下，惊退羌兵，指曰：汝从这条路去救吾儿」，"
            "「因此引军径来寻你」——此处的因果是**张苞自述的**，且显灵是否实有原文未在叙述层确认；"
            "故不把它写成客观因果边（见 U06、V08）。",
     "quotes": [("zhangbao_account", "narration"), ("both_return", "narration")], "basis": "explicit"},
]

# ═══════════════════════════════════════════════════════════════════
# 3. states[]  前值 / 后值 + 事件锚点
# ═══════════════════════════════════════════════════════════════════
states = []
def add_state(sid, who, field, before, after, anchor, bq, aq, basis="explicit", note=None):
    d = {"id": sid, "who": who, "field": field, "before": before, "after": after,
         "anchor": anchor, "basis": basis,
         "beforeQuotes": [(k, "narration") for k in bq], "afterQuotes": [(k, "narration") for k in aq]}
    if note:
        d["note"] = note
    states.append(d)

add_state("S01", "关兴", "处境", "与张苞、马岱同领五万精兵往退羌兵",
          "首战被羌兵裹围、直围入西北角，困于垓心不得脱",
          "三路齐进遇铁车放出、弓弩齐发，蜀兵大败",
          ["troops_50000"], ["xing_surrounded", "gaixin"])
add_state("S02", "关兴", "生命危险", "困于垓心不能得脱，「胆寒，抵敌不住，望涧中而逃」，正遇断涧",
          "被岸上一员大将所救，得越吉马、绰刀上马（未死）",
          "越吉锤击马胯、马倒兴落水；随后岸上大将杀退羌兵",
          ["danhan", "duanjian"], ["get_horse"],
          note="「岸上一员大将」的身份在下一段才由关兴认出为关公（见 S03）。"
               "救援者的动作原文写作「只见岸上一员大将，杀退羌兵」，未写其如何使越吉落水（见 U01）。")
add_state("S03", "关兴", "对救援者的认知", "只见岸上一员大将杀退羌兵，且「尚在前面追杀羌兵」，不知是谁；"
                                          "兴「自思此人救我性命，当与相见」",
          "认出是父亲关公，受其指路「吾儿可速望此路去」；关公「言讫不见」后，兴望东南急走",
          "关兴拍马赶来，于云雾中看清面容（面如重枣、提青龙刀、骑赤兔马）",
          ["yueji_fall", "xing_thought"], ["guangong_appear", "vanish", "xing_go_se"],
          note="此为关兴的**认知**变化（「分明认得是」），原文写在关兴视角内；不据此判定异象为客观事实。")
add_state("S04", "张苞", "处境", "被铁车军追急",
          "见伯父自空而下惊退羌兵并受指路，引军寻到关兴，二人同归寨内",
          "关公显灵惊退羌兵并指示「汝从这条路去救吾儿」",
          ["zhangbao_account"], ["both_return"],
          note="前值取自张苞**自述**（character）；后值「二人同归寨内」是叙述层。")
add_state("S05", "孔明", "对破羌兵的把握", "累获全胜、心中甚喜；闻羌兵扣关只问「谁敢去退羌兵」",
          "登高观阵后断言「此不难破也」，并定下雪中诱敌之计",
          "亲到马岱寨中、次日上高阜观看铁车阵",
          ["kongming_pleased"], ["easy_to_break"],
          note="「此不难破也」是孔明之言；此处记的是他的判断与部署动作，不是叙述层对胜负的宣告。")
add_state("S06", "越吉", "生命", "引铁车兵来战，姜维退走；心疑未敢轻进，后被雅丹劝动催兵急追",
          "落坑堑后铁车兵大乱，望山谷而逃，被关兴砍死于马下",
          "羌兵俱落坑堑、铁车自相践踏，关兴等合击",
          ["yueji_doubt"], ["kansha"])
add_state("S07", "雅丹", "身份", "羌国丞相，力主攻孔明虚寨（「可以攻之」）",
          "被马岱活捉押赴大寨，得孔明释放并还所获，深感其德而回",
          "羌兵落坑堑大乱后「雅丹丞相早被马岱活捉」",
          ["yadan_trick"], ["yadan_captured", "return_all"])
add_state("S08", "曹真、郭淮", "战况", "连日望羌人消息，误判蜀兵因羌兵攻击而退，遂分两路追赶",
          "折曹遵、朱赞两先锋，被围痛杀后引败兵冲路走脱，失渭水魏寨",
          "魏延、赵云伏兵闪出斩将，关兴张苞两路围杀",
          ["guohuai_happy"], ["two_vanguards", "weishui"])
add_state("S09", "司马懿", "在魏廷的任用状态", "在宛城闲住，闻魏兵累败仰天长叹",
          "受诏复职加平西都督、起南阳诸路军马；后获赐金钺斧许便宜行事",
          "天使持节至、懿听诏毕调宛城诸路军马",
          ["sima_sigh"], ["edict_received", "axe_grant"])
add_state("S10", "孟达", "处境", "在新城约下申仪申耽克日举事，得孔明回书而不惧，定明日举事径取洛阳",
          "被围新城、内应倒戈，人困马乏被申耽一枪刺于马下，枭其首级",
          "徐晃兵到、司马懿兵到，申耽申仪佯许后倒戈",
          ["mengda_ally"], ["killed"])
add_state("S11", "徐晃", "生命", "请为先锋，为前部随司马懿进兵",
          "被孟达射中头额，众军救回取箭头令医调治，当晚身死，时年五十九岁",
          "徐晃坐下马收拾不住直到壕边高叫受降，孟达开弓射之",
          ["xuhuang_volunteer"], ["xuhuang_death"])
add_state("S12", "申耽、申仪", "立场", "受孟达之约「克日举事」",
          "佯许并推托军器粮草未备，围城时自外杀来倒戈，孟达死后受魏官职随司马懿征进",
          "耽仪二人佯许、每日调练军马只待魏兵到便为内应",
          ["mengda_ally"], ["fake_agree", "head_luoyang"],
          note="「佯许」是叙述层对其真实立场的揭示；他们在孟达面前说的是「军器粮草，俱未完备」。")
add_state("S13", "曹睿", "对司马懿的态度", "曾疑司马懿而散流言去之（钟繇追述），叹「此事朕亦悔之」",
          "复其官职并赐金钺斧许便宜行事，赞「卿之学识，过于孙、吴矣」",
          "钟繇保举、司马懿擒孟达后入城见魏主",
          ["regret"], ["praise", "axe_grant"],
          note="「散流言」出自钟繇奏言中的追述（见 V21），不是本区间叙述层直接呈现的事件。")
add_state("S14", "姜维", "所领任务", "奉命领兵出战，遇铁车兵来便退走、寨口虚立旌旗不设军马",
          "将羌兵诱过山口后，与马岱、张冀三路杀到，参与合击",
          "姜维引军出、越吉引铁车兵来、姜维即退走；后三路兵杀到",
          ["ambush_order"], ["ambush_spring"])
add_state("S15", "孔明（对孟达的判断）", "对孟达结局的预判", "修书警告孟达提防司马懿，并在掷书后断言「孟达必死于司马懿之手矣」",
          "本区间**未写**孔明得知孟达死讯（他最后出场是令来人回报警告）",
          "孔明掷书顿足断言；此后叙述转写司马懿与孟达，未再回到孔明视角",
          ["throw_letter", "bingfa"], ["envoy_back"],
          note="后值记为「未得知」而非「得知」：原文没有写孔明收到孟达死讯，不补原文没有的情节。")

add_state("S16", "姜维", "诱敌执行", "领兵出战，奉命「但有铁车兵来，退后便走」",
          "引军出、遇越吉铁车兵即退走，羌兵赶到寨前时已从寨后而去——诱敌动作按部署完成",
          "姜维引军出，越吉引铁车兵来；姜维即退走，羌兵赶到寨前，姜维从寨后而去",
          ["ambush_order"], ["jiangwei_retreat_full"])
add_state("S17", "钟繇（朝议发言）", "保举方式", "先陈为将之道与「知彼知己，百战百胜」，再以「臣量曹真虽久用兵，非诸葛亮对手」铺垫",
          "以「臣以全家良贱，保举一人」请举，报出「骠骑大将军司马懿也」",
          "魏主设朝、近臣奏曹真求救；睿大惊急问退军之策，钟繇奏对",
          ["zhongyou_preface", "rui_ask"], ["baoju", "zhongyou_name"])
add_state("S18", "曹睿（末段处置）", "对蜀部署", "受孟达造反、两京几危之报（「非卿等制之，两京休矣」）",
          "赐金钺斧许便宜行事，令司马懿出关破蜀；从其所举命张颌为前部先锋",
          "司马懿入城奏明并奉上孔明密书；睿大喜加赏",
          ["rui_regret"], ["break_shu", "recommend", "vanguard"])

# ── knowledgeGaps[]：知识差（谁知/不知）─────────────────────────
knowledgeGaps = [
    {"id": "K01", "who": "司马懿", "knows": "孟达欲反（得申仪家人密告 + 李辅邓贤出首）；后截获孔明回书",
     "doesNotKnow": "孟达已定「明日举事」的确切日期（梁畿回报在新城，且是假令）",
     "quotes": [("secret_told", "narration"), ("capture_spy", "narration")], "basis": "explicit"},
    {"id": "K02", "who": "孟达", "knows": "孔明回书警告司马懿必先至；梁畿来传调遣令",
     "doesNotKnow": "申耽申仪是「佯许」、李辅邓贤已出首、司马懿已发兵奔新城——他判「司马懿即来，达何惧哉」",
     "quotes": [("mengda_delay", "narration"), ("fake_agree", "narration")], "basis": "explicit",
     "note": "「佯许」是叙述层告诉读者的，孟达不知；这正是知识差。"},
    {"id": "K03", "who": "孔明", "knows": "孟达欲举事；司马懿复职加平西都督；判「若知孟达反，不须十日，兵必到矣」",
     "doesNotKnow": "孟达已被杀——本区间孔明自「掷书」后再未获孟达消息，原文未写他知道结果",
     "quotes": [("bingfa", "narration"), ("throw_letter", "narration")], "basis": "explicit"},
    {"id": "K04", "who": "曹真、郭淮", "knows": "伏路军报「蜀兵拔寨收拾起程」",
     "doesNotKnow": "蜀兵是诱敌而非真退——故郭淮判「此因羌兵攻击，故尔退去」，结果中伏",
     "quotes": [("caozhen_wait", "narration"), ("guohuai_happy", "narration")], "basis": "explicit"},
    {"id": "K05", "who": "越吉", "knows": "寨内鼓琴、四壁空竖旌旗（回报所得）",
     "doesNotKnow": "空寨是诱敌之计——他「心疑，未敢轻进」，最终采信了雅丹「虚设疑兵耳，可以攻之」",
     "quotes": [("qin_voice", "narration"), ("yadan_trick", "narration")], "basis": "explicit"},
    {"id": "K06", "who": "曹睿", "knows": "孟达造反、司马懿已擒之",
     "doesNotKnow": "司马懿是「不待圣旨」先行发兵——经懿当面奏明后才知",
     "quotes": [("sima_explain", "narration"), ("rui_regret", "narration")], "basis": "explicit"},
    {"id": "K07", "who": "关兴、张苞", "knows": "各自被「伯父」所救并受指路",
     "doesNotKnow": "对方也曾见同一异象——两人是归寨后互相说前事才知（「共相嗟异」）",
     "quotes": [("zhangbao_account", "narration"), ("both_return", "narration")], "basis": "explicit"},
    {"id": "K08", "who": "曹睿（对华歆之议）", "knows": "华歆奏请御驾亲征",
     "doesNotKnow": "原文未写曹睿对华歆之议的答复——只写他接着问钟繇「有何贤士」并采纳保举",
     "quotes": [("huaxin", "narration"), ("regret", "narration")], "basis": "explicit",
     "note": "登记此条是为了避免把「御驾亲征」写成华歆之议被采纳的**因果**（实际另有「驾幸长安」的叙述）。"},
]

# ═══════════════════════════════════════════════════════════════════
# 4. foreshadows[]  有铺设 + 回收才算伏笔
# ═══════════════════════════════════════════════════════════════════
foreshadows = []
def add_fs(fid, name, setup, payoff, status, sq, pq, basis="explicit", note=None):
    d = {"id": fid, "name": name, "setup": setup, "payoff": payoff, "status": status,
         "basis": basis, "setupQuotes": [(k, "narration") for k in sq], "payoffQuotes": [(k, "narration") for k in pq]}
    if note:
        d["note"] = note
    foreshadows.append(d)

add_fs("F01", "孔明判「天将降雪，吾计可施」",
       "孔明观铁车阵后说「今彤云密布，朔风紧急，天将降雪，吾计可施矣」，当即部署埋伏与退走",
       "「是时十二月终，果然天降大雪」，随后羌兵被诱入坑堑",
       "resolved", ["snow_prediction"], ["snow_fell"])
add_fs("F02", "「虚立旌旗，不设军马」的空寨",
       "孔明令「寨口虚立旌旗，不设军马」，姜维遇铁车即退",
       "羌兵见四壁空竖旌旗，「越吉心疑」；雅丹判为疑兵而进攻，羌兵遂抢入寨栅追过山口",
       "resolved", ["ambush_order"], ["qin_voice", "qiang_enter"],
       note="空寨的作用是诱敌深入，不是空城退敌——原文写羌兵最终「抢入寨栅」。")
add_fs("F03", "孔明命赵云、魏延各引一军埋伏",
       "孔明「随命赵云、魏延各引一军埋伏去讫」，二人此后在本区间前段不再出现",
       "曹真郭淮追袭时，魏延闪出斩曹遵、赵云一枪刺死朱赞",
       "resolved", ["zhaoyun_weiyan"], ["weiyan_appear", "zhuzan_killed"])
add_fs("F04", "申耽、申仪「佯许之」并为内应",
       "孟达约二人克日举事，「耽仪二人佯许之，每日调练军马，只待魏兵到，便为内应」",
       "围城时二人自外杀来大叫「反贼休走」，孟达被刺死，二人受魏官职",
       "resolved", ["fake_agree"], ["betray_shout", "killed"])
add_fs("F05", "梁畿赍檄先去新城「使其不疑」",
       "司马懿「令参军梁畿赍檄星夜去新城，教孟达等准备征进，使其不疑」",
       "梁畿到新城传令、答「此时约离宛城，望长安去了」，孟达遂定明日举事；随即司马懿兵到",
       "resolved", ["order_march"], ["liangji_order", "da_pleased"])
add_fs("F06", "李辅、邓贤「随状出首」",
       "司马懿处「更有孟达心腹人李辅并达外甥邓贤，随状出首」",
       "围城时二人在城上大骂「吾等已献了城也」，并大开城门迎司马懿入城",
       "resolved", ["lifu_dengxian"], ["city_given", "open_gate"])
add_fs("F07", "孔明警告「切莫教同事者知之；知则必败」",
       "孔明急令来人回报「若未举事，切莫教同事者知之；知则必败」",
       "孟达仍「即报申耽、申仪知道」并定明日举事，而二人正是内应——事败身死",
       "resolved", ["final_warning"], ["feast_plan", "killed"], basis="derived",
       note="原文没有写孟达「告诉了同事」这一动作的直述句，只写他「即报申耽、申仪知道」；"
            "把它与孔明的警告对照得出回收，属跨段推导，故 basis=derived。")
add_fs("F08", "孟达自信「司马懿即来，达何惧哉」",
       "孟达回书称「若司马懿闻达举事，须表奏魏主。往复一月间事」，孔明则判「不须十日，兵必到矣」",
       "司马懿果不待圣旨、加倍行程，孟达被围时叹「果不出孔明所料也」",
       "resolved", ["mengda_delay", "bingfa"], ["no_wait", "da_sigh"])
add_fs("F09", "司马懿「吾机先被孔明识破」",
       "司马懿截获孔明回书后大惊曰「世间能者所见皆同。吾机先被孔明识破」",
       "本区间**未回收**：这一互相识破只停在司马懿的自陈，原文没有再写孔明得知此事，也未写二人因此再交手",
       "unresolved", ["sima_realize"], [],
       note="孔明的判断在孟达处已落空（K02/K03），而司马懿的佩服没有传给孔明——本区间到此为止。")
add_fs("F10", "关兴得越吉马",
       "落水后「关兴得了越吉马，牵到岸上，整顿鞍辔，绰刀上马」",
       "本区间**未再出现**此马的任何后续（越吉此后再出现时是步行逃入山谷后被砍死）",
       "unresolved", ["get_horse"], [],
       note="它在本区间只出现一次。按「一次出现不叫伏笔」的口径，本条只在被显式标为 unresolved 时才列出；"
            "下游如需严格执行该口径，可整条丢弃。")

# ── notForeshadows[]：只出现一次、不构成伏笔 ─────────────────────
notForeshadows = [
    {"name": "宝雕弓", "why": "全区间仅 1 次（越吉「腰悬宝雕弓」），此后越吉再未用弓，无铺设—回收对。",
     "quotes": [("yueji_shout", "narration")], "basis": "explicit"},
    {"name": "青龙刀、赤兔马", "why": "仅出现在关公显灵那一段描写里，本区间唯一一次；"
                                      "同一物在别处的出现不在本区间，不能据此在本区间内宣告伏笔。",
     "quotes": [("guangong_appear", "narration")], "basis": "explicit"},
    {"name": "华歆「御驾亲征」之议", "why": "华歆奏请御驾亲征后，原文紧接着写钟繇保举司马懿并被采纳（「睿即降诏」）；"
                                          "华歆的建议本身没有被单独回收（既未写被褒奖，也未写被驳回）。"
                                          "后文「驾幸长安」是叙述层的既成安排，不构成对这条建议的回收。",
     "quotes": [("huaxin", "narration"), ("regret", "narration")], "basis": "explicit"},
    {"name": "断涧", "why": "作为地形只出现于关兴被追一段；后文雪地战场写的是「山路被雪漫盖，一望平坦」，"
                            "两处地形未构成同一物的铺设—回收。",
     "quotes": [("duanjian", "narration"), ("snow_road", "narration")], "basis": "explicit"},
    {"name": "「岂不大胜」的反问", "why": "郭淮的这一反问是他进言中的预判，后文羌兵确被大破——"
                                        "但预判应验不等于伏笔（同一句话没有被「铺设」为悬置线索）。",
     "quotes": [("guohuai_plan", "narration")], "basis": "explicit"},
]

# ═══════════════════════════════════════════════════════════════════
# 4b. worldSettings[]  kind = place / item / rule
#     只提取影响行动、资源、约束或后果的明确设定
# ═══════════════════════════════════════════════════════════════════
worldSettings = []
def add_ws(kind, name, keys, explain, placeState=None, itemStates=None, institution=None,
           basis="explicit", note=None):
    d = {"kind": kind, "name": name, "explain": explain, "basis": basis,
         "quotes": [(k, "narration") for k in keys]}
    if placeState:
        d["placeState"] = placeState
    if itemStates:
        d["itemStates"] = itemStates
    if institution:
        d["institution"] = institution
    if note:
        d["note"] = note
    worldSettings.append(d)

# ── place ────────────────────────────────────────────────────────
add_ws("place", "西平关", ["kou_xiping", "hanzhen_report"],
       "羌兵出兵的直接对象是蜀方关隘西平关；它决定蜀方必须应援（守将韩祯只能赍文告急），是行动的地理约束。",
       placeState="arrived")
add_ws("place", "新城", ["jincheng_title", "on_wall"],
       "孟达以新城太守身份镇守上庸、金城；新城是他举事的据点，也是司马懿奔袭的目标。"
       "原文以「登城视之」「急扯起吊桥」等动作确认他确在该城。",
       placeState="arrived")
add_ws("place", "上庸、金城", ["jincheng_title", "shangyong_appoint"],
       "与新城同属孟达辖区（「镇守上庸、金城等处」），是举事时「欲起金城、新城、上庸三处军马」的兵源；"
       "事后魏以李辅、邓贤分守新城、上庸，是其战略地位的落实。",
       placeState="mentioned",
       note="本区间只写孟达「约下金城太守申仪、上庸太守申耽」并宣布「欲起…三处军马」，"
            "没有写到三处兵马的到达或驻守动作，故记 mentioned 而非 arrived。")
add_ws("place", "洛阳", ["plan_luoyang", "mengda_reply"],
       "孟达举事的目标是「径取洛阳」，孔明取长安则「两京大定」；孟达又用「宛城离洛阳约八百里」论证司马懿表奏往返需时——"
       "洛阳在此既是目标，也是**距离计算的参照点**。",
       placeState="mentioned",
       note="「径取洛阳」是孟达的图谋且始终未执行；本区间没有任何到达洛阳的动作（孟达首级是被送去示众，非其本人到达），"
            "故 mentioned。")
add_ws("place", "宛城", ["sima_sigh", "when_start"],
       "司马懿闲住之地，也是他受诏后起兵之处；孟达用它的位置推断司马懿不能速至。",
       placeState="arrived")
add_ws("place", "长安", ["spy_report", "camp_changan"],
       "魏主驾幸长安、司马懿受命「于长安聚会」，是魏方集结地；司马懿擒孟达后引兵到长安城外下寨见魏主。",
       placeState="arrived")
add_ws("place", "祁山", ["kongming_pleased", "back_qishan"],
       "蜀方大寨所在：孔明「正在祁山寨中」议事，破羌兵后「连夜投祁山大寨而来」。",
       placeState="arrived")
add_ws("place", "渭水", ["weishui", "escape"],
       "蜀兵全胜追击的终点与魏寨所在：「直追到渭水，夺了魏寨」——夺取此处即魏西线失利的具体体现。",
       placeState="arrived")
add_ws("place", "羌中", ["guohuai_plan"],
       "郭淮所指的求救方向（「遣人从小路直入羌中」），是魏方外援路线的设定。",
       placeState="mentioned",
       note="本区间只有魏方「遣人」的动作，羌中作为地点仅在被议论时出现（遣使的对象），故 mentioned。")

# ── item ─────────────────────────────────────────────────────────
add_ws("item", "铁车", ["tieche_desc", "tieche_city", "pit"],
       "羌军的核心装备：用铁叶裹钉的战车，可骆驼或骡马驾引，能「首尾相连，随处结寨」「就似城池一般」。"
       "它既是羌兵战力（弓弩齐发大败蜀兵），也因「行得紧溜，急难收止」成为落坑后自相践踏的原因——"
       "同一物件同时解释了羌兵的强与败。",
       itemStates=["use", "lose"],
       note="use：铁车被羌兵用于结寨与放出冲阵；lose：落坑堑后被蜀兵所获并「尽给还雅丹」。"
            "两态分列，不合并成一条物品链。")
add_ws("item", "金珠（魏使所赍）", ["weishi_jinzhu"],
       "魏方为求羌兵出兵而实际交付的财物，是这次结盟的可见对价。",
       itemStates=["transfer"])
add_ws("item", "孔明回孟达的书信", ["write_letter", "capture_spy"],
       "孔明警告孟达提防司马懿的密书；它被孟达心腹人携带，最终被魏军哨马搜出，成为司马懿确认对方往来的凭据。",
       itemStates=["transfer", "lose"],
       note="transfer：书由孔明交给孟达来人带回（「修书令来人星夜回报」）；"
            "lose：心腹人被捉后「搜出孔明回书」，书信落到司马懿手里。"
            "孟达给孔明的回书属同类，此处不重复列条。")
add_ws("item", "铁锤", ["yueji_shout", "hammer_hit"],
       "越吉的兵器，直接造成关兴战马被击倒（「正中马胯」），是把关兴逼入落水的器具。",
       itemStates=["use"])
add_ws("item", "越吉的马", ["get_horse"],
       "越吉落水后留下的坐骑，被关兴所得并整顿鞍辔骑用——装备在交战双方之间的实际转移。",
       itemStates=["transfer"])
add_ws("item", "金钺斧", ["axe_grant"],
       "曹睿赐给司马懿的信物，附带制度性授权：「后遇机密重事，不必奏闻，便宜行事」——"
       "它把「不待圣旨发兵」这一既成事实追认为常设权限。",
       itemStates=["transfer", "hold"],
       note="transfer：由曹睿赐予司马懿；hold：司马懿受赐持有。"
            "此物不只是一件赏赐，它改变了司马懿此后能否自行发兵。")
add_ws("item", "孟达首级", ["killed", "head_luoyang"],
       "孟达死后被枭首，曹睿「教将孟达首级去洛阳城市示众」——首级被用作公开警示。",
       itemStates=["transfer", "use"])
add_ws("item", "射中徐晃的箭", ["mengda_shoot", "xuhuang_death"],
       "孟达所射之箭命中徐晃头额；众军「取了箭头，令医调治」而当晚仍身死——"
       "箭头被取出这一处置动作与死亡结果并列，说明伤势非表面处置可救。",
       itemStates=["use", "lose"],
       note="use：孟达以弓箭射击；lose：箭头被从伤口取出（离开身体）。")
add_ws("item", "铁车兵所用的弓弩、枪刀、蒺藜、飞锤", ["tieche_desc"],
       "羌军配备的器用（「皆惯使弓弩、枪刀、蒺藜、飞锤等器」）；其中弓弩在首战中「一齐骤发」直接大败蜀兵，"
       "是羌兵战力的具体构成。",
       itemStates=["use", "lose"],
       note="use：首战弓弩齐发；lose：落坑大乱后被蜀兵所获并尽还给雅丹。")

# ── rule ─────────────────────────────────────────────────────────
add_ws("rule", "「一日要行二日之路，如迟立斩」", ["rule_zhanshou"],
       "司马懿发兵时自定的行军军令：以斩刑强制加倍行程。它解释了司马懿为何能在孟达估算的「往复一月」之前兵临城下——"
       "即人物能做出超出常规速度的行动，靠的是这条自家军令而非朝廷授权。",
       institution="executed",
       note="有执行动作：「即传令教人马起程，一日要行二日之路」，且后续「行了二日」「又行了二日」是行军实际推进。"
            "是否有人因「迟」被斩，原文未写。")
add_ws("rule", "天子诏：复司马懿官职、加平西都督", ["edict", "edict_received"],
       "曹睿的诏令恢复司马懿官职并授权他「就起南阳诸路军马，前赴长安」——"
       "这是他此后能够调动宛城诸路军马的制度依据（「懿听诏毕，遂调宛城诸路军马」）。",
       institution="executed",
       note="declared（降诏）与 executed（听诏毕即调兵）都有；此处按「有执行动作」记 executed。")
add_ws("rule", "「若等圣旨，往复一月之间，事无及矣」", ["no_wait", "shi_advice"],
       "司马懿对「是否先奏闻」的处置：他判断等待圣旨会误期，遂不待奏闻即发兵。"
       "这不是朝廷法令，而是**人物**对程序成本的计算，解释了他为何能抢在孟达举事之前；"
       "也让后文曹睿的追认（赐金钺斧、许便宜行事）成为必要。",
       institution="misunderstood",
       note="misunderstood 在此取「这是**人物**的理解」之义：原文记的是司马懿自己的判断与原话，"
            "不是叙述层宣告的制度。他直到入城见魏主才当面奏明（见 sima_explain）。")
add_ws("rule", "「后遇机密重事，不必奏闻，便宜行事」", ["axe_grant"],
       "曹睿赐金钺斧时给的常设授权：司马懿此后遇机密重事可自行处置、无须奏闻。"
       "它把前面「不待圣旨」的个案追认为制度，直接决定他后续能否再自行发兵。",
       institution="declared",
       note="原文只写曹睿的授予之言（declared）；本区间没有写司马懿依此权限再行事的动作。")
add_ws("rule", "孟达「克日举事」的约期", ["mengda_ally", "fake_agree"],
       "孟达与申仪、申耽约定限期起事，但二人以「军器粮草，俱未完备，不敢约期起事」推托——"
       "这条约期因此被**实际搁置**，直到梁畿来后才改为「明日举事」。"
       "它解释了孟达为何在司马懿兵临时尚未准备好。",
       institution="misunderstood",
       note="misunderstood 取「人物的理解/操作」之义：约期是孟达与内应之间的私约，"
            "既非朝廷诏令也无执行效力——正因如此才会被一句推托无限期推迟。")

# ── notWorldSettings[]：看着像设定但不影响行动/资源/约束/后果 ────
notWorldSettings = [
    {"name": "「两京大定」（孟达对前景的描绘）",
     "why": "这是孟达书信里对举事成功后的设想，不是已生效的规则或已到达的地点；写成 place/rule 会把图谋当既成。",
     "quotes": [("plan_luoyang", "narration")], "basis": "explicit"},
    {"name": "「永结盟好」（孔明对羌方的提议）",
     "why": "孔明这句是对雅丹的**要求**（放汝回去，说与汝主）；本区间只写到「众皆拜谢而去」，"
            "没有写羌主接受结盟的动作，记为 rule 会夸大其效力。",
     "quotes": [("kongming_terms", "narration"), ("all_bow", "narration")], "basis": "explicit"},
    {"name": "「朕一时不明，误中反间之计」",
     "why": "曹睿这句是事后自责，指的是本区间之外的旧事（钟繇追述的散流言）；在本区间内没有对应的行动约束。",
     "quotes": [("rui_regret", "narration")], "basis": "explicit"},
    {"name": "「兵法云，攻其不备，出其不意」",
     "why": "这是孔明引用的兵法格言，用来解释他的判断；本区间没有写它被立为军令或被执行的动作，"
            "属泛泛术语，按要求不扩出术语装饰层。",
     "quotes": [("bingfa", "narration")], "basis": "explicit"},
    {"name": "「山路被雪漫盖，一望平坦」",
     "why": "这是战地状况的描写，不是规则/地点/物件的设定条目；它作为 C08 的地形条件被引用，不单列 worldSetting。",
     "quotes": [("snow_road", "narration")], "basis": "explicit"},
]

# ═══════════════════════════════════════════════════════════════════
# 4c. themeReadings[]  最多 1–2 条，每条必须 perspective + support + counter
# ═══════════════════════════════════════════════════════════════════
themeReadings = [
    {"id": "TH01",
     "perspective": "以**时间估算**为轴读：本区间里孟达一线的胜负由「谁算得准对方的行动时间」决定——"
                    "孔明算司马懿「不须十日，兵必到矣」，孟达算「往复一月间事」，司马懿算「若等圣旨…事无及矣」。"
                    "这是可选的读法之一，不是本区间唯一的主题。",
     "support": [
        {"point": "孟达以里程推算司马懿不可能速至", "quotes": [("mengda_delay", "narration")]},
        {"point": "孔明直接否掉这个算法", "quotes": [("bingfa", "narration")]},
        {"point": "司马懿用不待圣旨 + 加倍行程把它变成事实", "quotes": [("no_wait", "narration"), ("rule_zhanshou", "narration")]},
        {"point": "孟达被围时承认算错", "quotes": [("da_sigh", "narration")]},
     ],
     "counter": [
        {"point": "反例：同一区间里蜀方对羌方的胜利靠的是**天时与地形**（降雪、坑堑），不是时间估算——"
                  "孔明赢在「吾计可施」的物理条件，把两场胜负都归到「算时间」会漏掉这一半。",
         "quotes": [("snow_prediction", "narration"), ("pit", "narration")]},
        {"point": "反例：说孟达「算错」并不完全公平——他的算法以一个真实前提为基础（须表奏魏主），"
                  "错的是这个前提被司马懿违反，而违反又靠曹睿事后追认才合法化。",
         "quotes": [("mengda_delay", "narration"), ("axe_grant", "narration")]},
        {"point": "反例：本区间还写了一层不属于算计的东西——关公显灵救关兴，"
                  "其解释权不在任何人手里，也无法用时间估算框架吸收。",
         "quotes": [("guangong_appear", "narration")]},
     ],
     "basis": "inferred",
     "notClaimed": "本条不主张这是本回主旨，也不主张「算得准就一定赢」：蜀方在羌战线上的胜利证明还有别的机制。"},
    {"id": "TH02",
     "perspective": "以**知情差**为轴读：同一件事（孟达要反）被不同人以不同方式知道——"
                    "孔明由李丰转述得知、司马懿由告密与首告得知、孟达不知道申耽申仪是内应。"
                    "胜负在这里部分表现为「谁知道谁」。",
     "support": [
        {"point": "孔明一方的情报来自李丰转呈的书信", "quotes": [("letters_presented", "narration")]},
        {"point": "司马懿一方来自申仪家人密告与李辅邓贤出首",
         "quotes": [("secret_told", "narration"), ("lifu_dengxian", "narration")]},
        {"point": "孟达对申耽申仪的判断是错的", "quotes": [("fake_agree", "narration"), ("believe", "narration")]},
        {"point": "孔明警告他别让同事知道，他没有做到", "quotes": [("final_warning", "narration")]},
     ],
     "counter": [
        {"point": "反例：情报优势并未让司马懿全知——他截获孔明回书后才「大惊」承认「吾机先被孔明识破」，"
                  "说明情报多的一方也可能落后于对方的判断。",
         "quotes": [("sima_realize", "narration")]},
        {"point": "反例：本区间最关键的一次反转（羌兵被破）不靠情报，靠的是天降大雪与预设坑堑。",
         "quotes": [("snow_fell", "narration"), ("pit", "narration")]},
        {"point": "反例：关兴、张苞「共相嗟异」的显灵事件里，两人各自掌握不完整信息，"
                  "但这并没有影响任何军事结果。",
         "quotes": [("both_return", "narration")]},
     ],
     "basis": "inferred",
     "notClaimed": "本条只描述「谁知道什么」在本区间的分布，不主张作者以此为主题；"
                   "「部分表现为」是因为羌线胜负与知情差无关。"},
]

# ═══════════════════════════════════════════════════════════════════
# speechAsClueNotFact：人物之言，不作为叙述事实
# ═══════════════════════════════════════════════════════════════════
speechAsClueNotFact = [
    {"id": "V01", "speaker": "郭淮", "quote": ("guohuai_plan", "narration"),
     "why": "进言中的主张与预判（「岂不大胜」是反问），不是已发生的事。"},
    {"id": "V02", "speaker": "雅丹", "quote": ("yadan_allow", "narration"),
     "why": "「理合依允」是他主张出兵的判断。"},
    {"id": "V03", "speaker": "孔明", "quote": ("kongming_ask", "narration"),
     "why": "问众将谁愿去，是发问不是结果。"},
    {"id": "V04", "speaker": "关兴、张苞", "quote": ("xingbao_volunteer", "narration"),
     "why": "「某等愿往」是应命，不是任务已完成。"},
    {"id": "V05", "speaker": "孔明", "quote": ("road_unfamiliar", "narration"),
     "why": "孔明对二人路途不熟的判断。"},
    {"id": "V06", "speaker": "马岱", "quote": ("madai_wait", "narration"),
     "why": "「且待来日见阵」是建议（后确照此而行）；建议与被采纳要分开记。"},
    {"id": "V07", "speaker": "越吉", "quote": ("yueji_shout", "narration"),
     "why": "「吾乃越吉元帅也」是阵前自报身份。"},
    {"id": "V08", "speaker": "关公（关兴所见）", "quote": ("guangong_point", "narration"),
     "why": "「吾儿可速望此路去。吾当护汝归寨。」是关兴视角中的话语；"
            "「护汝归寨」是否真由关公所为，原文未在叙述层确认。"},
    {"id": "V09", "speaker": "张苞", "quote": ("zhangbao_account", "narration"),
     "why": "张苞自述被伯父所救——这是他的陈述，不是叙述层对异象的确认。"},
    {"id": "V10", "speaker": "马岱", "quote": ("madai_hold", "narration"),
     "why": "「此军无计可退」是马岱的判断；「我守住寨栅」是他的承诺（后文未再提寨栅）。"},
    {"id": "V11", "speaker": "孔明", "quote": ("easy_to_break", "narration"),
     "why": "「此不难破也」是孔明的判断，不是叙述层宣告胜负。"},
    {"id": "V12", "speaker": "姜维", "quote": ("jiangwei_answer", "narration"),
     "why": "「羌人惟恃一勇力，岂知妙计乎」是姜维对羌兵的评断。"},
    {"id": "V13", "speaker": "孔明", "quote": ("snow_prediction", "narration"),
     "why": "「天将降雪，吾计可施矣」是预判；降雪在下一段才由叙述层写出（见 F01 回收）。"},
    {"id": "V14", "speaker": "雅丹", "quote": ("yadan_trick", "narration"),
     "why": "「此诸葛亮诡计，虚设疑兵耳」是雅丹的判断——他判断的**方向对、结论错**。"},
    {"id": "V15", "speaker": "雅丹", "quote": ("yadan_not_afraid", "narration"),
     "why": "「不足为惧」是雅丹的主张。"},
    {"id": "V16", "speaker": "雅丹", "quote": ("yadan_small", "narration"),
     "why": "「纵有些小伏兵，何足惧哉」是雅丹的主张，直接导致进入坑堑（见 C08）。"},
    {"id": "V17", "speaker": "孔明", "quote": ("kongming_terms", "narration"),
     "why": "「永结盟好」是孔明对羌方的要求，不是已达成的盟约。"},
    {"id": "V18", "speaker": "郭淮", "quote": ("guohuai_happy", "narration"),
     "why": "「此因羌兵攻击，故尔退去」是**错误判断**（见 C11）；把它当事实会写出假因果。"},
    {"id": "V19", "speaker": "华歆", "quote": ("huaxin", "narration"),
     "why": "「须是陛下御驾亲征」是建议；「长安有失，关中危矣」是他预言的后果，本区间未发生。"},
    {"id": "V20", "speaker": "钟繇", "quote": ("zhongyou_assess", "narration"),
     "why": "「非诸葛亮对手」是钟繇的评断。"},
    {"id": "V21", "speaker": "钟繇", "quote": ("baoju", "narration"),
     "why": "「臣以全家良贱，保举一人」是他自陈的担保，属人物之言。"},
    {"id": "V22", "speaker": "钟繇", "quote": ("liuyan", "narration"),
     "why": "「故散流言，使陛下疑而去之」是钟繇追述旧事；本区间叙述层没有呈现散流言的过程。"},
    {"id": "V23", "speaker": "李丰", "quote": ("mengda_past", "narration"),
     "why": "孟达降魏缘由与所受恩遇是李丰转述的往事。"},
    {"id": "V24", "speaker": "李丰（转述孟达）", "quote": ("plan_luoyang", "narration"),
     "why": "「欲起…径取洛阳」是孟达的意图，本区间未执行；「两京大定」是他的设想。"},
    {"id": "V25", "speaker": "马谡", "quote": ("masu_scoff", "narration"),
     "why": "「量曹睿何足道」是马谡的轻敌之言。"},
    {"id": "V26", "speaker": "孔明", "quote": ("fear_sima", "narration"),
     "why": "「必被所擒」「中原不易得也」是孔明的预判（后在孟达处应验，但此处仍是预判）。"},
    {"id": "V27", "speaker": "孔明（书信）", "quote": ("letter_content", "narration"),
     "why": "「若成大事，则公汉朝中兴第一功臣也」是书信中的勉励之辞，不是对孟达功劳的叙述认定。"},
    {"id": "V28", "speaker": "孟达", "quote": ("mengda_laugh", "narration"),
     "why": "「人言孔明心多」是他对孔明预警的轻慢反应。"},
    {"id": "V29", "speaker": "孟达（回书）", "quote": ("mengda_reply", "narration"),
     "why": "「往复一月间事」「达何惧哉」是他的估算与自信，全部落空（见 F08）。"},
    {"id": "V30", "speaker": "孔明", "quote": ("throw_letter", "narration"),
     "why": "「孟达必死于司马懿之手矣」是孔明的预言；其应验见 S10，但预言本身不是事实陈述。"},
    {"id": "V31", "speaker": "孔明", "quote": ("bingfa", "narration"),
     "why": "引兵法以驳孟达的算法，属人物论证。"},
    {"id": "V32", "speaker": "孔明", "quote": ("final_warning", "narration"),
     "why": "「知则必败」是孔明的警告。"},
    {"id": "V33", "speaker": "司马师", "quote": ("shi_guess", "narration"),
     "why": "「莫非叹魏主不用乎」是猜测。"},
    {"id": "V34", "speaker": "司马昭", "quote": ("zhao_guess", "narration"),
     "why": "「早晚必来宣召父亲也」是猜测（紧随其后天使即至，但猜测不因应验而变事实）。"},
    {"id": "V35", "speaker": "司马懿", "quote": ("fortune", "narration"),
     "why": "「此乃皇上齐天之洪福也」是他的感叹与归因。"},
    {"id": "V36", "speaker": "司马懿", "quote": ("analysis", "narration"),
     "why": "「此贼必通谋诸葛亮…自退兵也」是他的推断。"},
    {"id": "V37", "speaker": "司马师", "quote": ("shi_advice", "narration"),
     "why": "「可急写表申奏天子」是建议（未被采纳）。"},
    {"id": "V38", "speaker": "司马懿", "quote": ("no_wait", "narration"),
     "why": "「事无及矣」是他对等待圣旨后果的判断——正是这个判断决定了后续行动。"},
    {"id": "V39", "speaker": "司马懿", "quote": ("sima_realize", "narration"),
     "why": "「吾机先被孔明识破」是他的自陈；「孟达今无能为矣」是他的结论。"},
    {"id": "V40", "speaker": "梁畿（传司马懿令）", "quote": ("liangji_order", "narration"),
     "why": "这是有意让孟达听到的调遣令（「使其不疑」），其内容不是真实部署方向。"},
    {"id": "V41", "speaker": "梁畿", "quote": ("when_start", "narration"),
     "why": "「此时约离宛城，望长安去了」是司马懿**有意**让孟达得到的假信息。"},
    {"id": "V42", "speaker": "孟达", "quote": ("da_pleased", "narration"),
     "why": "「吾大事成矣」是他的误判，随即被围。"},
    {"id": "V43", "speaker": "徐晃", "quote": ("xuhuang_challenge", "narration"),
     "why": "「早早受降」是阵前喊话。"},
    {"id": "V44", "speaker": "孟达", "quote": ("da_sigh", "narration"),
     "why": "「果不出孔明所料也」是孟达的承认，可作为 F08 回收的**人物自陈**证据；"
            "但「孔明所料」本身仍出自孔明之口。"},
    {"id": "V45", "speaker": "申耽、申仪", "quote": ("betray_shout", "narration"),
     "why": "「反贼休走」是他们倒戈时的喊话；倒戈本身由叙述层确认（「忽见两路兵自外杀来」）。"},
    {"id": "V46", "speaker": "李辅、邓贤", "quote": ("city_given", "narration"),
     "why": "「吾等已献了城也」是他们在城上的宣告，与叙述层「大开城门，迎接司马懿入城」一致。"},
    {"id": "V47", "speaker": "曹睿", "quote": ("rui_regret", "narration"),
     "why": "「误中反间之计，悔之无及」是曹睿的自责，指本区间之外的旧事。"},
    {"id": "V48", "speaker": "司马懿", "quote": ("sima_explain", "narration"),
     "why": "「不待圣旨，星夜而去」是他对**自己行为**的奏明；虽与叙述层一致，仍属其自陈。"},
    {"id": "V49", "speaker": "曹睿", "quote": ("praise", "narration"),
     "why": "「卿之学识，过于孙、吴矣」是褒语，不是对学识的客观判定。"},
    {"id": "V50", "speaker": "曹睿", "quote": ("axe_grant", "narration"),
     "why": "「不必奏闻，便宜行事」在此是**授予**（declared）；本区间未写依此权限行事的动作。"},
    {"id": "V51", "speaker": "曹睿", "quote": ("rui_wanted", "narration"),
     "why": "「朕正欲用之」是曹睿对张颌任用的表态。"},
    {"id": "V52", "speaker": "叙述层（对照项）", "quote": ("sons", "narration"),
     "why": "「二人素有大志，通晓兵书」是叙述层评断，不是人物之言——列出以说明本表并非收录所有评价句。"},
]

# ═══════════════════════════════════════════════════════════════════
# unknowns[]  读不出来或原文有矛盾的地方
# ═══════════════════════════════════════════════════════════════════
unknowns = [
    {"id": "U01", "question": "越吉「连人带马，平白地倒下水来」的原因是什么？",
     "finding": "原文只写「忽听得一声响处」，并用「平白地」描述结果，没有把原因归给任何人或动作；"
                "紧接着写的是岸上「一员大将，杀退羌兵」，与落水不是同一件事。",
     "reading": "不补机制（见 R01/R02）。若要写「关公使越吉落水」，原文无据。",
     "basis": "explicit", "quotes": [("yueji_fall", "narration")]},
    {"id": "U02", "question": "「彼时曹不爱其才」「自不死后，曹睿即位」二处是否脱字（当作曹丕）？",
     "finding": "本区间「曹丕」0 次、「丕」0 次，而全篇「曹丕」88 次、「丕」185 次。"
                "从上下文（同辇出入、封散骑常侍、曹睿即位）看所指当为曹丕，但原文此处写作「曹」与「自」。",
     "reading": "不迳改字：引文照录以保证 text[start:end]==quote；字形问题登记在 TN01/TN02，不下版本学结论。",
     "basis": "explicit", "quotes": [("mengda_past", "narration"), ("envied", "narration")]},
    {"id": "U03", "question": "「张冀」「张颌」是否为「张翼」「张郃」之讹？",
     "finding": "本区间「张冀」3 次而全篇「张翼」95 次、「张冀」5 次；本区间「张颌」2 次，全篇「张郃」0 次、「张颌」184 次。"
                "两个用字在全书内部并不一致（前者是少数写法，后者是本书通行写法）。",
     "reading": "照录不改（见 TN03）。是否属讹字需版本学证据，本候选不下结论。",
     "basis": "explicit", "quotes": [("zhaoyun_weiyan", "narration"), ("zhanghe", "narration")]},
    {"id": "U04", "question": "从司马懿发兵到兵临新城，实际经过多少天？",
     "finding": "原文给出的都是不完整的时间信息：「行了二日」遇徐晃，「又行了二日」捉住孟达心腹人，"
                "孟达处写「明日举事」，梁畿则说司马懿「此时约离宛城，望长安去了」。各段之和不等于全程，"
                "且司马懿的实际路线（奔新城）与梁畿所说方向（望长安）相反。",
     "reading": "不推算天数。孔明的「不须十日」与孟达的「往复一月」都是人物估计（见 K03、TH01）。",
     "basis": "explicit", "quotes": [("xuhuang_join", "narration"), ("capture_spy", "narration"), ("when_start", "narration")]},
    {"id": "U05", "question": "「一日要行二日之路」是否真的执行到新城？是否有人因迟到被斩？",
     "finding": "原文写「即传令教人马起程，一日要行二日之路，如迟立斩」，随后只写「行了二日」「又行了二日」两次行程，"
                "没有给出总里程或到达日，也没有写有人被斩。",
     "reading": "只记军令与行进事实，不推算速度、不假定有人被斩。",
     "basis": "explicit", "quotes": [("order_march", "narration")]},
    {"id": "U06", "question": "关公显灵是「真」的吗？",
     "finding": "本区间的呈现方式是：先由关兴视角看见（「隐隐有一大将…分明认得是父亲关公」），"
                "再由张苞自述（「忽见伯父自空而下」）。两处都在人物视角/人物自述内，"
                "叙述层没有以全知口吻确认关公到场。",
     "reading": "不判定真伪。凡引用此节均标 character 或注明为关兴认知（见 S03、V08、V09）。",
     "basis": "explicit", "quotes": [("guangong_appear", "narration"), ("zhangbao_account", "narration")]},
    {"id": "U07", "question": "徐晃之死（「时年五十九岁」）是否有文本内部矛盾？",
     "finding": "本区间明写「乃是右将军徐晃」，并给出「徐晃被孟达射中头额…当晚身死，时年五十九岁」，"
                "文本内部无矛盾；是否与史实相符超出本区间可判范围。",
     "reading": "照录，不做史实校正。",
     "basis": "explicit", "quotes": [("xuhuang_join", "narration"), ("xuhuang_death", "narration")]},
    {"id": "U08", "question": "华歆的「御驾亲征」之议是否被采纳？",
     "finding": "华歆奏请御驾亲征后，原文紧接着写钟繇保举司马懿并被采纳（「睿即降诏」），"
                "没有写曹睿对华歆之议的答复；但后文另有「魏主曹睿，一面驾幸长安」与「天子驾到长安」的叙述。",
     "reading": "不写成「华歆之议被采纳」也不写成「被驳回」；两处引文并置，留给下游（见 K08、notForeshadows）。",
     "basis": "explicit", "quotes": [("huaxin", "narration"), ("spy_report", "narration")]},
    {"id": "U09", "question": "孔明是否知道孟达后来被杀？",
     "finding": "本区间孔明最后出现是「掷书于地」并令来人回报警告；此后到区间结束，"
                "叙述层的孟达之死、司马懿复命、张颌为先锋等事，都没有写孔明得知。",
     "reading": "记 K03/S15：孔明在区间内不知道结果。不写「孔明闻孟达死」之类原文没有的情节。",
     "basis": "explicit", "quotes": [("throw_letter", "narration"), ("envoy_back", "narration")]},
    {"id": "U10", "question": "「曹真折了两个先锋」的「两个先锋」是哪两人？",
     "finding": "本区间前文写「先锋曹遵」「副先锋朱赞」分别被魏延、赵云所杀，后文写「曹真折了两个先锋」。"
                "两处对得上，但「两个先锋」一词本身未再点名。",
     "reading": "按两次斩将的原文记为曹遵、朱赞，basis=derived（跨两段对应），不写成一句直述。",
     "basis": "derived", "quotes": [("caozun_killed", "narration"), ("two_vanguards", "narration")]},
    {"id": "U11", "question": "雅丹被释后，羌国是否真的「永结盟好」？",
     "finding": "本区间只写到「雅丹深感其德」「众皆拜谢而去」，没有写羌主彻里吉的回应，"
                "也没有写此后羌兵是否再助魏。",
     "reading": "只记释放与归还的事实，不把结盟写成已达成的结果（见 notWorldSettings）。",
     "basis": "explicit", "quotes": [("yadan_moved", "narration"), ("all_bow", "narration")]},
    {"id": "U12", "question": "回末「未知胜负如何，且看下文分解」是否意味着蜀魏胜负已定？",
     "finding": "该句是回末套语，出现在张颌为先锋、随司马懿来破蜀兵之后；本区间没有写任何蜀魏主力交锋的结果。",
     "reading": "不因回末套语推断胜负（结束≠成功）。蜀方在本区间的战果仅限破羌兵与夺渭水魏寨。",
     "basis": "explicit", "quotes": [("vanguard", "narration")]},
    {"id": "U13", "question": "申耽、申仪「佯许之」是从何时开始的？与申仪家人告密孰先孰后？",
     "finding": "孟达处写「约下金城太守申仪、上庸太守申耽，克日举事。耽仪二人佯许之」；"
                "而司马懿处已先有「金城太守申仪家人…细说孟达欲反之事」与李辅邓贤出首。"
                "两人是**先**告密后佯许，还是同时，原文没有给出时序。",
     "reading": "不排时序：C14 只连到司马懿得知情报，不断言「因为告密所以佯许」。",
     "basis": "explicit", "quotes": [("mengda_ally", "narration"), ("fake_agree", "narration"), ("shentong_secret", "narration")]},
    {"id": "U14", "question": "关兴所得越吉之马的下落？",
     "finding": "原文写「关兴得了越吉马，牵到岸上，整顿鞍辔，绰刀上马」，此后本区间再未提到此马；"
                "越吉本人再次出现时已是步行逃入山谷（「望后面山谷中而逃」）。",
     "reading": "记为 F10（unresolved）。不补后续。",
     "basis": "explicit", "quotes": [("get_horse", "narration"), ("yueji_flee_meet", "narration")]},
]

# ═══════════════════════════════════════════════════════════════════
# textualNotes[]  文本内部观察（不改字）
# ═══════════════════════════════════════════════════════════════════
textualNotes = [
    {"id": "TN01", "note": "「彼时曹不爱其才」缺字（全篇「曹丕」88 次，此处作「曹」）。",
     "quotes": [("mengda_past", "narration")]},
    {"id": "TN02", "note": "「自不死后，曹睿即位」缺字（当作「自丕死后」）。",
     "quotes": [("envied", "narration")]},
    {"id": "TN03", "note": "「张冀」本区间 3 次、「张颌」本区间 2 次，与全书通行写法（张翼 95 / 张颌 184）不一致。",
     "quotes": [("zhaoyun_weiyan", "narration"), ("zhanghe", "narration")]},
    {"id": "TN04", "note": "「马谡曰：“何不急修书，令孟达提防？’”引号不成对：以左双引号起，却以单右引号收。",
     "quotes": [("masu_suggest", "narration")]},
    {"id": "TN05", "note": "本区间末尾两行为分隔线与整理者署名（「枫林晚 整理校对」），非原文正文，"
                           "已排除在所有抽取之外。",
     "quotes": []},
]

# ═══════════════════════════════════════════════════════════════════
# sceneIndex：段落索引（供复核者定位）
# ═══════════════════════════════════════════════════════════════════
sceneIndex = {
    "note": "本区间 14 个非空段落（含标题、分隔线、整理者署名）；段号 0 起，偏移为全文 codepoint 偏移。",
    "paragraphs": [
        {"i": 0, "start": 472736, "end": 472759, "kind": "title",
         "head": "第九十四回　诸葛亮乘雪破羌兵　司马懿克日擒孟达"},
        {"i": 1, "start": 472760, "end": 472866, "kind": "narrative", "head": "郭淮献策求救西羌，曹真遣人驰书"},
        {"i": 3, "start": 472868, "end": 473443, "kind": "narrative",
         "head": "彻里吉发兵扣西平关；兴苞赴援，三路齐进大败，关兴被围"},
        {"i": 5, "start": 473445, "end": 474244, "kind": "narrative",
         "head": "关兴落水遇关公显灵；归寨禀孔明，孔明定雪计"},
        {"i": 7, "start": 474246, "end": 474854, "kind": "narrative",
         "head": "雪中诱敌，羌兵落坑；越吉死、雅丹擒，孔明释而结盟"},
        {"i": 9, "start": 474856, "end": 475148, "kind": "narrative",
         "head": "曹真郭淮追击中伏，折两先锋，蜀兵夺渭水魏寨"},
        {"i": 11, "start": 475150, "end": 475551, "kind": "narrative", "head": "曹睿设朝，钟繇保举司马懿，降诏复职"},
        {"i": 13, "start": 475553, "end": 475866, "kind": "narrative", "head": "李丰代父报孟达欲举事取洛阳"},
        {"i": 15, "start": 475868, "end": 476374, "kind": "narrative", "head": "细作报司马懿复职；孔明修书，孟达回书轻慢"},
        {"i": 16, "start": 476375, "end": 476535, "kind": "narrative", "head": "孔明掷书断言孟达必死，令勿泄于同事"},
        {"i": 18, "start": 476537, "end": 477189, "kind": "narrative",
         "head": "司马懿受诏、得告密，不待圣旨发兵，截获孔明回书"},
        {"i": 20, "start": 477191, "end": 478216, "kind": "narrative",
         "head": "孟达被围身死；司马懿见魏主受金钺斧，荐张颌为先锋"},
        {"i": 22, "start": 478218, "end": 478238, "kind": "separator", "head": "------------------"},
        {"i": 23, "start": 478239, "end": 478273, "kind": "colophon", "head": "整理者署名"},
    ],
}

# ═══════════════════════════════════════════════════════════════════
# selfCritique：本段我最可能读错的三处
# ═══════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════
# 补充抽取（第二轮反向覆盖自检后补入的真实内容）
#   第一轮 uncovered 报出 40 条叙述子句未被任何引文覆盖；逐条归位后补入下列条目。
#   补入的每条都对应原文中确实存在、而首轮未处理的事实，不是为凑覆盖率。
# ═══════════════════════════════════════════════════════════════════
supplementary = {
    "why": "第二轮反向覆盖自检（uncoveredClauses）暴露的整段未覆盖项；补入后重算 uncovered。",
    "items": [
        {"id": "X01", "kind": "worldSetting", "slot": "place",
         "name": "西羌国（彻里吉之国的君臣结构）",
         "explain": "羌国的决策结构（国王彻里吉 + 文雅丹丞相 + 武越吉元帅）解释了出兵决议为何是"
                    "「雅丹进言→国王从其言→二人领兵」这一条路径，也解释了后来雅丹被擒、越吉被杀"
                    "对羌方战力的直接打击。",
         "placeState": "mentioned",
         "note": "本区间只写羌国的君臣结构与其出兵决议，没有写蜀魏任何一方到达西羌国；"
                 "故记 mentioned（羌中作为遣使方向另见 worldSettings 的「羌中」条）。",
         "quotes": [("xixiang_court", "narration"), ("yadan_present_court", "narration")], "basis": "explicit"},
        {"id": "X02", "kind": "worldSetting", "slot": "item",
         "name": "宝雕弓",
         "explain": "越吉出阵时的装备（「手挽铁锤，腰悬宝雕弓」）。本区间只用铁锤，弓未发一矢——"
                    "列出以说明其装备与其实际使用不符（见 notForeshadows）。",
         "itemStates": ["hold"],
         "note": "hold：越吉出阵时佩带此弓（「腰悬宝雕弓」）。"
                 "本区间没有发射、转手或丢失的描写（作战用的是铁锤），故只记 hold 一态。",
         "quotes": [("yueji_array", "narration")], "basis": "explicit"},
        {"id": "X03", "kind": "state", "who": "越吉", "field": "出阵态势",
         "before": "在羌兵阵里「手挽铁锤，腰悬宝雕弓，跃马奋勇而出」",
         "after": "落坑堑后铁车兵大乱，最终被关兴砍死（见 S06）",
         "anchor": "三路齐进前越吉出阵挑战",
         "bq": [("yueji_array", "narration")], "aq": [("kansha", "narration")], "basis": "explicit"},
        {"id": "X04", "kind": "state", "who": "关兴（对岸上大将的观察）", "field": "所见",
         "before": "「兴就水中挣起看时，只见岸上一员大将，杀退羌兵」——只知有人相救",
         "after": "「只见那员将，尚在前面追杀羌兵」，兴「自思此人救我性命，当与相见，遂拍马赶来」",
         "anchor": "关兴自水中挣起后追赶那员将",
         "bq": [("savior_seen", "narration")], "aq": [("savior_pursuing", "narration"), ("xing_thought", "narration")], "basis": "explicit"},
        {"id": "X05", "kind": "state", "who": "关兴、张苞", "field": "会合",
         "before": "关兴望东南急走，「至半夜，忽一彪军到，乃张苞也」——张苞开口先问「你曾见二伯父否？」",
         "after": "两人「各说前事，共相嗟异」，同归寨内，随后星夜来见孔明备说此事",
         "anchor": "张苞于半夜引军寻到关兴",
         "bq": [("zhangbao_arrive", "narration")], "aq": [("both_marvel", "narration"), ("xing_report_back", "narration")], "basis": "explicit"},
        {"id": "X06", "kind": "state", "who": "雅丹", "field": "被押见孔明",
         "before": "被马岱活捉（见 S07）",
         "after": "「孔明升帐，马岱押过雅丹来」，随即被去缚赐酒（见 T08 动作栏）",
         "anchor": "孔明升帐、马岱押过雅丹",
         "bq": [("yadan_captured", "narration")], "aq": [("yadan_brought_full", "narration")], "basis": "explicit"},
        {"id": "X07", "kind": "state", "who": "赵云", "field": "伏兵出击",
         "before": "奉命与魏延各引一军埋伏（见 F03）",
         "after": "「副先锋朱赞引兵追赶，忽然一彪军闪出，为首大将乃赵云也」，朱赞被一枪刺死",
         "anchor": "朱赞追赶时赵云闪出",
         "bq": [("zhaoyun_weiyan", "narration")], "aq": [("zhaoyun_appear", "narration"), ("zhuzan_killed", "narration")], "basis": "explicit"},
        {"id": "X08", "kind": "state", "who": "曹睿", "field": "对司马懿行踪的掌握",
         "before": "叹「此事朕亦悔之」，问「今仲达现在何地？」",
         "after": "钟繇答「近闻仲达在宛城闲住」，睿即降诏并「御驾亲征，令司马懿克日到彼聚会」",
         "anchor": "钟繇报出司马懿在宛城闲住",
         "bq": [("regret", "narration")], "aq": [("zhongyou_home", "narration"), ("rui_personal", "narration")], "basis": "explicit"},
        {"id": "X09", "kind": "state", "who": "孔明（接李丰来报时的预判）", "field": "对来意的判断",
         "before": "「孔明只道东吴犯境，心甚惊疑，唤入帐中问之」——他以为李丰是来报东吴犯境",
         "after": "李丰「特来报喜」，孔明转为大喜并厚赏（见 T11）",
         "anchor": "李严令子李丰来见",
         "bq": [("kongming_suspect", "narration")], "aq": [("lifeng_good", "narration"), ("reward_lifeng", "narration")], "basis": "explicit",
         "note": "此处对比本身即说明「报喜」出乎孔明预料；不据此推断孔明对东吴另有情报。"},
        {"id": "X10", "kind": "state", "who": "孟达", "field": "等待回信",
         "before": "「却说孟达在新城，专望心腹人回报」",
         "after": "「一日，心腹人到来，将孔明回书呈上。孟达拆封视之」，随后「乃具回书，令心腹人来答孔明」",
         "anchor": "心腹人自孔明处返回新城",
         "bq": [("mengda_wait_letter", "narration")], "aq": [("mengda_letter_arrive", "narration"), ("mengda_reply_send", "narration")], "basis": "explicit"},
        {"id": "X11", "kind": "state", "who": "马谡（追问孔明判断）", "field": "对话",
         "before": "孔明掷书顿足断言「孟达必死于司马懿之手矣」",
         "after": "「马谡问曰：丞相何谓也？」孔明以兵法作答，众将皆服",
         "anchor": "孔明断言孟达必死于司马懿之手",
         "bq": [("throw_letter", "narration")], "aq": [("masu_ask", "narration"), ("bingfa", "narration"), ("all_convinced", "narration")], "basis": "explicit"},
        {"id": "X12", "kind": "state", "who": "司马师、司马昭", "field": "对父亲长叹的揣测",
         "before": "「当日侍立于侧，见懿长叹，乃问曰：父亲何为长叹？」懿答「汝辈岂知大事耶？」",
         "after": "司马师猜「莫非叹魏主不用乎」，司马昭猜「早晚必来宣召父亲也」，随即「忽报天使持节至」",
         "anchor": "司马懿于宛城仰天长叹，二子在侧",
         "bq": [("sons_ask", "narration"), ("yi_reply", "narration")], "aq": [("shi_guess", "narration"), ("zhao_guess", "narration"), ("angel_arrive", "narration")], "basis": "explicit",
         "note": "二子所猜**不是**叙述层给出的原因；原文没有说明司马懿长叹究竟为何（见 unknowns 未列项，"
                 "因「汝辈岂知大事耶」已把事情推开）。"},
        {"id": "X13", "kind": "state", "who": "司马懿（对时局的判断）", "field": "对魏主处境的评估",
         "before": "以手加额称「此乃皇上齐天之洪福也」",
         "after": "续言「诸葛亮兵在祁山，杀得内外人皆胆落；今天子不得已而幸长安，若旦夕不用吾时，"
                  "孟达一举，两京休矣」——由此推出「吾先擒之」",
         "anchor": "申仪家人与李辅邓贤告密之后",
         "bq": [("fortune", "narration")], "aq": [("siwang_analysis", "narration"), ("analysis", "narration")], "basis": "explicit"},
        {"id": "X14", "kind": "state", "who": "徐晃", "field": "加入南征",
         "before": "「行了二日，山坡下转出一军，乃是右将军徐晃」",
         "after": "徐晃下马问都督何往，懿低声告以擒孟达，晃「某愿为先锋」，遂「徐晃为前部，懿在中军，二子押后」",
         "anchor": "行军二日后与徐晃相遇",
         "bq": [("xuhuang_join", "narration")], "aq": [("xuhuang_tell", "narration"), ("sima_low_voice", "narration"), ("formation_full", "narration")], "basis": "explicit"},
        {"id": "X15", "kind": "state", "who": "孟达的心腹人", "field": "被擒与供述",
         "before": "携带孔明回书自蜀返新城途中",
         "after": "被前军哨马捉住、搜出孔明回书；司马懿「吾不杀汝，汝从头细说」，其人只得一一告说",
         "anchor": "前军哨马捉住孟达心腹人",
         "bq": [("capture_spy", "narration")], "aq": [("interrogate", "narration"), ("spy_told_all", "narration")], "basis": "explicit"},
        {"id": "X16", "kind": "state", "who": "梁畿", "field": "到新城传令",
         "before": "奉命赍檄星夜去新城「使其不疑」（见 C15）",
         "after": "「忽报参军梁畿来到，孟达迎入城中」，传司马懿将令后孟达设宴相待、送出城外",
         "anchor": "梁畿抵新城，孟达迎入城中",
         "bq": [("order_march", "narration")], "aq": [("liangji_arrive_full", "narration"), ("feast_plan", "narration")], "basis": "explicit"},
        {"id": "X17", "kind": "state", "who": "徐晃（阵亡后的处置）", "field": "后事",
         "before": "被孟达射中头额，众军救回取箭头令医调治（见 S11）",
         "after": "当晚身死；司马懿「令人扶柩还洛阳安葬」",
         "anchor": "徐晃死于寨中",
         "bq": [("xuhuang_death", "narration")], "aq": [("coffin_luoyang", "narration")], "basis": "explicit"},
        {"id": "X18", "kind": "state", "who": "孟达（围城中的反应）", "field": "战守",
         "before": "先射退徐晃，「城上乱箭射下，魏兵方退」",
         "after": "「孟达恰待开门追赶，四面旌旗蔽日，司马懿兵到」，遂闭门坚守；次日见「魏兵四面围得铁桶相似」，"
                 "「行坐不安，惊疑未定」",
         "anchor": "徐晃被射退后司马懿大军继至",
         "bq": [("arrows_down", "narration")], "aq": [("pursue_out", "narration"), ("da_sigh", "narration"), ("iron_surround", "narration")], "basis": "explicit"},
        {"id": "X19", "kind": "state", "who": "孟达（突围失败）", "field": "最后动作",
         "before": "见申耽申仪两路兵到，「只道是救军到」开门杀出",
         "after": "二人喊「反贼休走」，孟达「见事变，拨马望城中便走，城上乱箭射下」，被申耽一枪刺于马下",
         "anchor": "申耽申仪倒戈",
         "bq": [("thinks_rescue", "narration")], "aq": [("turn_back", "narration"), ("killed", "narration")], "basis": "explicit"},
        {"id": "X20", "kind": "state", "who": "司马懿（战后处置）", "field": "善后与奏报",
         "before": "李辅邓贤大开城门迎其入城（见 F06）",
         "after": "「抚民劳军已毕，遂遣人奏知魏主曹睿」；曹睿教将孟达首级示众并加申耽申仪官职",
         "anchor": "司马懿入新城",
         "bq": [("open_gate", "narration")], "aq": [("report_rui2", "narration"), ("head_luoyang", "narration")], "basis": "explicit"},
        {"id": "X21", "kind": "state", "who": "曹睿（对张颌的任用）", "field": "先锋人选",
         "before": "「就令司马懿出关破蜀」",
         "after": "司马懿举「右将军张颌」为先锋，曹睿笑曰「朕正欲用之」，遂命张颌为前部先锋随懿离长安",
         "anchor": "司马懿奏举先锋",
         "bq": [("break_shu", "narration")], "aq": [("recommend", "narration"), ("zhanghe", "narration"), ("rui_wanted", "narration"), ("vanguard", "narration")], "basis": "explicit"},
        {"id": "X23", "kind": "state", "who": "姜维（诱敌深入）", "field": "退走方式",
         "before": "奉命遇铁车兵即退（见 S16）",
         "after": "「又见姜维兵俱在雪地之中奔走」，越吉因此「大怒，催兵急追」——"
                  "退走被刻意做得可见，是把羌兵往坑堑引的关键一步",
         "anchor": "雪地中山路被雪漫盖、姜维兵奔走可见",
         "bq": [("ambush_order", "narration")],
         "aq": [("jiangwei_snow_run", "narration")], "basis": "explicit"},
        {"id": "X24", "kind": "state", "who": "羌兵（追兵）", "field": "追击途中再生疑虑",
         "before": "雅丹称「不足为惧」并催大兵追赶（见 C08）",
         "after": "「正赶之间，忽报蜀兵自山后而出」——追兵得到新的警讯，而雅丹仍称「纵有些小伏兵，何足惧哉」继续前进",
         "anchor": "追赶途中报蜀兵自山后而出",
         "bq": [("yadan_not_afraid", "narration")],
         "aq": [("shu_from_hill_full", "narration"), ("yadan_small", "narration")], "basis": "explicit"},
        {"id": "X25", "kind": "state", "who": "孟达（见内应旗号时的判断）", "field": "误判",
         "before": "被围新城，「行坐不安，惊疑未定」",
         "after": "「忽见两路兵自外杀来，旗上大书“申耽”、“申仪”。孟达只道是救军到，忙引本部兵大开城门杀出」",
         "anchor": "申耽申仪两路兵自外杀来",
         "bq": [("iron_surround", "narration")],
         "aq": [("two_armies_full", "narration")], "basis": "explicit",
         "note": "「只道是救军到」点明这是**孟达的判断**；二人的真实来意由下一句「反贼休走」揭破（见 V45）。"},
        {"id": "X22", "kind": "note", "name": "回末套语与整理行",
         "explain": "区间末尾「正是：既有谋臣能用智，又求猛将助施威。未知胜负如何，且看下文分解」是回末套语，"
                    "其后「------------------」与「枫林晚 整理校对…」是整理标记，均非情节。"
                    "登记于此以说明它们被有意排除在抽取之外（见 U12、TN05）。",
         "quotes": [("ending_couplet", "narration"), ("ending_line", "narration")], "basis": "explicit"},
    ],
}

selfCritique = [
    {"id": "SC1", "risk": "把郭淮「此因羌兵攻击，故尔退去」读成叙述事实，从而写出「羌兵得手→蜀兵真退」的假因果。",
     "why": "原文紧接着写「前面蜀兵乱走，魏兵随后追袭」，随后魏延、赵云伏兵闪出、曹真折两先锋——"
            "可见蜀兵退走是**诱敌**，郭淮的判断是错的。",
     "howIHandled": "已把该句标 voiceSurface=mixed 并在 C11 中写明「机制在判断错误，不在时间相邻」；"
                    "另在 V18 单列为「错误判断」。",
     "quotes": [("guohuai_happy", "narration"), ("weiyan_appear", "narration")]},
    {"id": "SC2", "risk": "把关兴所见「父亲关公」当作叙述层确认的显灵，并据此写一条「关公救关兴」的因果边。",
     "why": "该段全部写在关兴视角内（「兴自思」「看看至近」「分明认得是」），张苞那一处也是**自述**；"
            "叙述层从未以全知口吻说关公到场。越吉落水的原因更是只写「忽听得一声响处」「平白地」——"
            "把两者接起来就是读者补的机制。",
     "howIHandled": "记为 U06 与 R02，不建因果边；S03 只记关兴的**认知**变化；V08/V09 标为人物之言。",
     "quotes": [("guangong_appear", "narration"), ("yueji_fall", "narration")]},
    {"id": "SC3", "risk": "把「明日举事，换上大汉旗号，发诸路军马，径取洛阳」当成孟达已经出兵，"
                         "或把「径取洛阳」当成到达。",
     "why": "原文写孟达说完这句后立刻是「忽报：城外尘土冲天，不知何处兵来」——他始终没有出兵；"
            "洛阳在本区间只是图谋（worldSettings 中记 placeState=mentioned 正是为此）。"
            "同理「两京大定」只是他对前景的设想（见 notWorldSettings）。",
     "howIHandled": "T14 objective 明确标为叙述层对**约定**的记述；洛阳记 mentioned；"
                    "「两京大定」列入 notWorldSettings。",
     "quotes": [("feast_plan", "narration"), ("dust", "narration")]},
    {"id": "SC4", "risk": "把孔明「孟达必死于司马懿之手矣」的预言当成事实陈述，或反过来把它当成本区间的结局。",
     "why": "孟达确实在本区间被杀，但该句是孔明的**预言**（人物之言），且孔明本人此后未再获孟达消息；"
            "「应验」与「事实陈述」是两件事。同理回末「且看下文分解」也不等于蜀魏胜负已定。",
     "howIHandled": "V30 标为人物之言；S15/K03 记孔明不知结果；U12 明确不因回末套语推断胜负。",
     "quotes": [("throw_letter", "narration"), ("vanguard", "narration")]},
]
