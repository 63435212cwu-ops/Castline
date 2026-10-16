#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构造 read:dafeng:L3:0307（第七十八章 你来啦）的候选，并在写入前做机器可复核的自检。

本脚本只做两件事：
  1. 把候选内容里用到的**每一条引文**按 `docs[0].text.find(quote)` 在全文里定位，
     断言该引文在本单元切片 [1366953,1373655) 内**恰好出现一次**；
  2. 写盘前跑结构性断言（五栏不共用区间、null 栏位必须带理由、分区键齐全、
     世界设定的三区分字段齐全）。

偏移口径：start/end 一律是相对 docs[0].text 全文的 codepoint 偏移。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L3_0307.candidate.json"
REPORT = Path(__file__).resolve().parent / "check_report.json"

START, END = 1366953, 1373655
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

DOC = json.loads(DOCS.read_text("utf-8"))
TEXT = DOC[0]["text"]
SLICE = TEXT[START:END]
SLICE_SHA = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

errors: list[str] = []
checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"check": name, "result": "pass" if ok else "fail", "detail": detail})
    if not ok:
        errors.append("%s :: %s" % (name, detail))


check("切片起点是单元标题", TEXT[START:START + 9] == "第七十八章 你来啦",
      "TEXT[%d:%d]=%r" % (START, START + 9, TEXT[START:START + 9]))
check("切片长度 6702", len(SLICE) == 6702, "len=%d" % len(SLICE))
check("切片 sha256", SLICE_SHA == "6b67dd884d3f134b74ac4fa03e18818afc91aaae8d25082585dbfa2d0cfadd77",
      SLICE_SHA)

# --------------------------------------------------------------------- 引文库
# key -> (逐字原文子串, 载体类型, 段落号)
QT: dict[str, tuple[str, str, int]] = {
    "q_wild_sorcerer": ("野生术士如同大熊猫，异常珍稀，不可能在襄城附近同时出现两位。", "inner", 2),
    "q_gongyang_reveal": ("“这座墓的主人不简单，呵呵，看到一些不该看的东西就不好了。这是老头子多年来掘墓的心得，你们司天监的术士不屑干这种活计，缺了点经验。”公羊宿笑道。", "dialogue", 4),
    "q_houtu_shock": ("后土帮的成员看向钟璃，满脸愕然，像是被惊到了。", "narration", 6),
    "q_bfzz_core": ("原来是真人不露相，她竟然是司天监的术士.........果然这种闷不吭声的人物往往才是核心人物之一。", "inner", 7),
    "q_bfzz_low": ("他再看向许七安，愈发觉得此人地位最低。", "inner", 9),
    "q_shield2": ("首先是武夫身份很难在这样的队伍里成为核心。其次，刚才击杀邪物时，此人的作用就是盾牌。", "inner", 10),
    "q_zhongli_nod": ("“嗯嗯。”钟璃点点头，表示自己知道了。", "dialogue", 12),
    "q_zhongli_rule": ("她绝对不会施展任何法术的，绝对不会参与任何战斗，这是一位成熟的预言师总结出来的经验。", "free_indirect", 13),
    "q_chu_gaze": ("楚元缜沉默不语，目光时而审视许七安，时而打量金莲道长。", "narration", 14),
    "q_chu_simple": ("许宁宴很奇怪，他绝非表面上那么简单。", "inner", 15),
    "q_chu_3times": ("三次都走到这间偏室里，只有两个可能，要么许宁宴是故意的，要么有什么特殊原因，让他不断的重返此处。", "inner", 16),
    "q_chu_cang": ("道长啊道长，你藏的可真好。", "inner", 17),
    "q_chu_secret": ("“许宁宴身上到底隐藏什么秘密........", "inner", 17),
    "q_enter_pian": ("众人心情沉重的进入偏室，偏室的尽头是一条甬道，通往位置的深处。", "narration", 19),
    "q_ask_lead": ("“那，那个........道长要不您走前面？我还只是个孩子。”", "dialogue", 20),
    "q_ask_danger": ("“有感知到危险？”金莲道长神色一肃。", "dialogue", 21),
    "q_enter_corridor": ("深吸一口气，举着火把进入甬道。", "narration", 22),
    "q_quiet": ("他们的脚步声回荡在寂静的甬道里，谁都没有说话，凸显出众人内心的紧张。", "narration", 24),
    "q_stone_door": ("甬道尽头是一扇高大的石门，紧闭着，尚未有人光顾。", "narration", 25),
    "q_shenjue": ("许七安停在石门前，双手按在门上，他尝试着发力，但又未真正用力，静默几秒，没有受到来自神觉的预警。", "narration", 26),
    "q_no_danger": ("收回手，朝金莲道长点头：“没有危险，嗯，至少我没感知到。”", "dialogue", 27),
    "q_open_door": ("“开门吧。”金莲道长说。", "dialogue", 28),
    "q_door_open": ("生涩沉重的摩擦声里，石门缓缓往后敞开。", "narration", 30),
    "q_dark": ("火把的光芒照入，只能照亮范围数丈距离，再往内，光芒就被黑暗吞噬了。", "narration", 31),
    "q_no_air": ("许七安看见火把黯淡了一下，忙说：“再等等，里面没有空气。”", "narration", 32),
    "q_ask_pill": ("而后吩咐钟璃：“有辟毒丹吗？给后土帮的兄弟们分一点。”", "dialogue", 33),
    "q_pill_declined": ("白袍肮脏的公羊宿说道：“不必客气，我们服用过辟毒丹了。”", "dialogue", 34),
    "q_wait_enter": ("在外头等了一刻钟，许七安半只脚踏入墓室，既没有危险预警，火把也没有黯淡，这让他松了口气，道：", "narration", 35),
    "q_datou": ("“我先打头阵，你们跟在身后，记住，不要做多余的事。”", "dialogue", 36),
    "q_everyone_low": ("到现在，不止是病夫帮主，连普通成员也看出许七安的低等地位。", "narration", 38),
    "q_shield_line": ("探路打头阵，危险当盾牌。", "narration", 39),
    "q_self_view": ("我这一波操作也算出尽风头了，作用最大，道长他们都要倚仗我.........许七安嘴角微挑。", "inner", 41),
    "q_recall_detail": ("同时，许七安想起以前没有注意道的细节。", "narration", 42),
    "q_canhun": ("“金莲道长果然是残魂啊，我想起来了，桑泊案时，我们潜入平远伯府，结果遭遇了被神殊俯身的恒慧，道长当时的操作是，元神莽上去。", "inner", 43),
    "q_pingyuan": ("桑泊案时，我们潜入平远伯府，结果遭遇了被神殊俯身的恒慧，道长当时的操作是，元神莽上去。", "inner", 43),
    "q_canhun_explain": ("“可道长如果是残魂，一切就可以解释。甚至，他喜欢上猫也能解释，反正人和猫都不是自己的肉身。", "inner", 46),
    "q_canhun_doubt": ("“不过，残魂能活这么久？道门不愧是玩鬼专业户。”", "inner", 47),
    "q_enter_main": ("进入主墓后，五根火把驱散的大部分的黑暗，墓室内的场景一点点勾勒于众人眼前。", "narration", 49),
    "q_width": ("数人合抱的立柱支撑起看不见高度的穹顶，两边的墙壁距离初步估计有二十丈，也就是说，这座主墓的宽度是二十丈（60米）。", "narration", 51),
    "q_depth_unknown": ("深度未知，有待探索。", "narration", 52),
    "q_bfzz_advice": ("“按照墓穴的格局，中央必定是墓穴主人的棺椁，我建议先别过去，绕着墙壁摸索圈，估测出模式的大小，顺便看看能不能发现有价值的信息。”", "dialogue", 53),
    "q_bfzz_walk": ("病夫帮主走到金莲道长身边，建议道。", "narration", 54),
    "q_xqa_mutter": ("老盗墓贼了........不过，领队的是我啊，为什么不找我商量？许七安心里嘀咕。", "inner", 55),
    "q_youli": ("“有理。”金莲道长颔首。", "dialogue", 56),
    "q_go_left": ("许七安带领着众人往左开始探索，谨慎移动，直到看见一副巨大的壁画。", "narration", 57),
    "q_mural_snake": ("壁画的内容是：一条可怕的巨蛇闯入了人类城市，它盘绕起来时，身躯比城墙还高。它的瞳孔猩红发光，狰狞可怕。", "narration", 60),
    "q_mural_same1": ("群臣膜拜高台的画面，与外头那幅壁画一模一样。", "narration", 79),
    "q_mural_usurp": ("接下来的壁画内容，让众人大吃一惊，那面目模糊的道长挥剑斩杀了皇帝，然后穿上龙袍，戴上皇冠，他篡位了。", "narration", 80),
    "q_hengyuan_ask": ("恒远大师皱眉道：“如此高人，应该不至于留恋权力。称帝对他而言有何意义？”", "dialogue", 84),
    "q_yuanjing": ("他们默契的相视一笑，知道对方和自己一样，想到了元景帝。", "narration", 86),
    "q_mural_orgy": ("这幅“多人运动”壁画，与外头那幅一样，只不过没有行气经络图", "inner", 93),
    "q_thunder_kill": ("可能是上天也看不惯皇帝昏聩的行为，某一天忽然乌云大作，降下雷霆劈死了他。皇帝驾崩了。", "narration", 100),
    "q_xqa_logic": ("许七安从理性的角度出发，分析道：“奇怪，有些地方不符合逻辑。”", "dialogue", 104),
    "q_xqa_credit": ("金莲和楚元缜等人知道许七安在破案方面有着异于常人的天赋，纷纷按捺住发散的思绪，聆听他说话。", "narration", 105),
    "q_xqa_mural_odd": ("“如果这座墓的主人是壁画里的皇帝，也就是道人，那么，这幅壁画就很奇怪了。”", "dialogue", 106),
    "q_xqa_history": ("“即使是我们大奉英明神武的陛下，也知道修改史书，遮掩自己的污点。而这壁画，赤裸裸的画在这里，是讽刺？”", "dialogue", 107),
    "q_hengyuan_counter": ("“天雷劈死了他，所以，这座墓应该是臣子、后人修建，批判他不是很正常吗。”恒远道。", "dialogue", 110),
    "q_xqa_rebut": ("“大师，您或许会为了仇人建墓，可别人未必会。”许七安摇头，说道：", "dialogue", 111),
    "q_xqa_unless": ("“如果后人憎恨着他，那么便不会修建出如此规格的大墓。反之，就不会画这样的壁画。除非壁画的内容无比真实。”", "dialogue", 112),
    "q_accepted": ("众人点头，接受了他的说法", "narration", 113),
    "q_chu_ask_thunder": ("“以道人的实力，等闲的雷霆劈不死他。这雷霆是不是还有别的寓意？”", "dialogue", 113),
    "q_tianjie": ("这时，金莲道长说话了，一字一句，沉声道：“是天劫。”", "dialogue", 114),
    "q_strange_word": ("闻言，许七安等人看向金莲道长，这是一个陌生的词汇。", "narration", 116),
    "q_daomen_rank": ("金莲道长缓缓点头：“在道门体系中，二品叫做‘渡劫’，度过天劫，就可以成为一品的陆地神仙。呵呵，这可不是司天监预言师的天谴能比拟。上一代的人宗道首，就是在天劫中，灰飞烟灭。”", "dialogue", 117),
    "q_remember": ("原来道门二品叫“渡劫”，一品叫“陆地神仙”。天地会众人颇为欣喜的记下来。", "narration", 118),
    "q_chu_conclude": ("“也就是说，这位皇帝是道门二品，而且是巅峰的二品，距离陆地神仙境只差一线。”楚元缜说道。", "dialogue", 121),
    "q_yiguanzhong": ("金莲道长忽然松了口气，“死于天劫，灰飞烟灭，这座墓应该是衣冠冢。不会有太大的危险。”", "dialogue", 122),
    "q_songqi": ("其他人也松了口气", "narration", 123),
    "q_qingsong": ("许七安颇为轻松的调侃道：", "narration", 123),
    "q_chaqi_warn": ("“道长，过于笃定的判断，往往会招来相反的后果。”", "dialogue", 123),
    "q_bieluan": ("道长这家伙，别乱插旗啊。", "narration", 124),
    "q_other_side": ("在许七安的带领下，他们来到了主墓的另一侧，失望的发现并没有壁画。", "narration", 125),
    "q_torch_use": ("许七安手持火把", "narration", 126),
    "q_black_corridor": ("看见了一条宽阔的黑色通道。", "narration", 126),
    "q_pools": ("这条通道笔直的通向最中央的高台，通道两边是浅浅的水坑，水质浑浊。", "narration", 127),
    "q_candles_along": ("许七安移动火把，橘色的光辉照到了通道边缘，每隔十步树立一个等人高的烛台，一直连绵到高台。", "narration", 130),
    "q_candle_material": ("“这似乎是东海红龙身上提炼出的油脂，这一根蜡烛，能烧几十年不灭。”金莲道长嗅了嗅，辨识出蜡烛的材质。", "dialogue", 131),
    "q_candle_light": ("许七安和楚元缜点燃了蜡烛", "narration", 132),
    "q_pool_watch": ("许七安一边让人注意两侧的水池，防止水中藏着邪物；一边点亮通道边缘的烛台。", "narration", 133),
    "q_torch_wane": ("火把无法维持太久，终将熄灭，得赶在它们燃尽前，用别的东西接替照明任务。", "free_indirect", 134),
    "q_soldiers": ("临近高台，许七安忽然停了下来，因为通往高台的台阶上，伫立着两列士卒，静静的注视着这群不速之客。", "narration", 135),
    "q_corpse_check": ("妈的，吓老子一跳........许七安骂骂咧咧的走过去，先侧耳聆听，确认没有心跳，接着观察这些干尸。", "narration", 136),
    "q_dont_touch": ("“只是干尸而已，大家不要胡乱触碰，跟在我身后。”", "dialogue", 137),
    "q_climb": ("告诫了一句后，他拾阶而上，踏过九十九阶，登上了高台。", "narration", 138),
    "q_coffin_center": ("高台上的景物最先映入许七安眼里，中央摆放着一具巨大的青铜棺椁，高台的四角伫立着四道高大身影。", "narration", 139),
    "q_four_figures": ("这些身影手持各不相同的武器，无声的伫立着，伫立了数千年的岁月，屹立不倒。", "narration", 140),
    "q_dry_corpse": ("这具干尸穿着鱼鳞甲胄，手持紫金锤，带着青铜面具，只露出一双眼睛。", "narration", 142),
    "q_bronze_sword": ("“这似乎是道门作品？”楚元缜同样在观察干尸，不过他看的那具干尸，手里拄着一柄锈迹斑斑的青铜剑。", "dialogue", 144),
    "q_wuxing_place_full": ("“确实有道门痕迹，不过，这种上古符文我只能猜测一二，西边那具主金，南北东分别主火、水、木。”", "dialogue", 146),
    "q_wuxing_place": ("“确实有道门痕迹，不过，这种上古符文我只能猜测一二，西边那具主金，南北东分别主火、水、木。”", "dialogue", 146),
    "q_rune_guess": ("这种上古符文我只能猜测一二", "dialogue", 146),
    "q_daomen_trace": ("确实有道门痕迹，不过，", "dialogue", 146),
    "q_place_five": ("西边那具主金，南北东分别主火、水、木。”", "dialogue", 146),
    "q_corpse_study": ("金莲道长看完四具干尸，观察过他们身上的甲胄，沉吟道：", "narration", 145),
    "q_chu_sword_q": ("“这似乎是道门作品？”", "dialogue", 144),
    "q_yuan_ask": ("“确实有一些天赋异禀的妖族，体型庞大。但也不至于这么夸张。而且，如果你们知道妖族五品的时候，会凝聚妖丹，就不会认为壁画上这条蛇是妖族了。”", "dialogue", 66),
    "q_hengyuan_snake": ("“这么大的蛇，是妖族？”恒远皱眉。", "dialogue", 63),
    "q_chu_dontknow": ("楚元缜摇摇头，表示自己不知道，他虽四处云游，但自从甲子荡妖后，大妖渐渐绝迹。而二十年前的山海关战役，倒是有妖族出现，但楚元缜当时还是孩童。", "narration", 64),
    "q_yuangu_shenmo": ("“不过远古神魔活跃的年代，人类还处在蒙昧时期，处在部落时代。所以，壁画上这条蛇，应该是远古神魔的血裔，并非真正的神魔。”", "dialogue", 73),
    "q_snake_can": ("“即使如此，这道人能斩大蛇，实力恐怕非凡寻常。”楚状元道。", "dialogue", 75),
    "q_mural_lift": ("许七安和楚元缜一前一后，高举火把，照亮壁画。", "narration", 59),
    "q_snake_mural": ("壁画的内容是：",
                       "narration", 60),
    "q_emperor_worship": ("皇帝为了答谢道人，为他铸了高台，率文武百官膜拜。", "narration", 77),
    "q_width_20": ("两边的墙壁距离初步估计有二十丈", "narration", 51),
    "q_black_corridor_2": ("这条通道笔直的通向最中央的高台", "narration", 127),
    "q_ask_lead_body": ("许七安站在甬道口，望着前方的黑暗，有些踌躇。", "narration", 20),
    "q_scared_inner": ("没有，就是有点怂，勾起了我儿时看恐怖片的心理阴影", "inner", 22),
    "q_no_danger_ok": ("收回手，朝金莲道长点头：“没有危险，嗯，至少我没感知到。”", "dialogue", 27),
    "q_open_ok": ("“开门吧。”金莲道长说。", "dialogue", 28),
    "q_mural_daoren": ("这时，一位脚踏飞剑的道人从天而降，斩杀了巨蛇。", "narration", 61),
    "q_mural_worship2": ("城中的皇帝带领臣子们出来迎接道人，对他磕头跪拜，道人踩踏飞剑，凝于半空，俯瞰着下方的皇帝和臣子。", "narration", 62),
    "q_mural_war": ("再接下来，壁画描绘的内容变成了战争，黑甲军队和白甲军队厮杀，白甲军队后方是巨人般的皇帝——那位篡位的道人。", "narration", 87),
    "q_mural_orgy2": ("皇帝的军队平定了叛乱，但他似乎并没有打算做个好皇帝，他开始玩起了多人运动。", "narration", 89),
    "q_chu_liupai": ("许七安脑海里诸多念头闪过，然后听见楚元缜低声道：“道长，这位皇帝，与道门双修流派有莫大的渊源啊。”", "dialogue", 95),
    "q_chu_realask": ("他真正想说的是，这道长会不会是那支流派的开宗祖师？", "inner", 96),
    "q_dontknow2": ("“不知道。”金莲道长的回答言简意赅。", "dialogue", 98),
    "q_xqa_agree": ("楚状元还是很聪明的吗，我也是这么想的", "inner", 97),
    "q_three_views1": ("许七安想的是，原来五品妖族凝练的是妖丹", "inner", 69),
    "q_three_views2": ("楚元缜则在想，既然不是妖族，那这条蛇是什么？他心里隐约有个猜测。", "inner", 70),
    "q_three_views3": ("恒远的想法比较简单，这条蛇他打不过，是佛法暂时无法降服的妖孽。", "inner", 71),
    "q_tianjie_echo": ("“天劫？”", "dialogue", 115),
    "q_dizong": ("许七安一拍脑袋，道：“我想起来了，道长你说过，那个该死的地宗道首就是渡劫失败，才被魔性反噬，堕落成妖道。”", "dialogue", 119),
    "q_zilian": ("当初杀死紫莲后，金莲道长夜里潜入许七安房间，与他有过一番坦诚布公的谈话。", "narration", 120),
    "q_no_mural": ("在许七安的带领下，他们来到了主墓的另一侧，失望的发现并没有壁画。", "narration", 125),
    "q_where_earth2": ("“土呢？”许七安问。", "dialogue", 147),
    "q_wangsheng": ("“是不是往生？”野生术士公羊宿，望向了钟璃。", "dialogue", 150),
    "q_armor_detail": ("一片片鱼鳞甲胄用红线串联，每一片鱼鳞上都刻着古怪的符文，既邪异又精美。", "narration", 143),
    "q_daozhang_examine": ("金莲道长看了一眼青铜棺椁，挪开目光，走到高台边缘，审视着最近的一具干尸。", "narration", 141),
    "q_candle_detail": ("烛台上有尚未燃尽的蜡烛，赤红如血，却又晶莹剔透，宛如红宝石一般。", "narration", 130),
    "q_candles_cry": ("“两边都是蜡烛........”", "dialogue", 128),
    "q_goulan": ("“道长篡位，荒淫无度，于是上天降下雷霆劈死了他.........这未免也太勾栏了。”病夫帮主摇摇头，给出评价。", "dialogue", 101),
    "q_buji": ("“即使是我们大奉英明神武的陛下，也知道修改史书，遮掩自己的污点。而这壁画，赤裸裸的画在这里，是讽刺？”", "dialogue", 107),
    "q_chu_careful": ("英明神武的陛下修改史书，遮掩自己的污点.........许宁宴也太谨慎了吧，即使在这样的场合里，也不留下“大不敬”的把柄。", "inner", 108),
    "q_chill_before_ask": ("众人听的津津有味，许七安却忽然脊背一凉，道：", "narration", 152),
    "q_where_earth": ("“土呢？”许七安问。", "dialogue", 147),
    "q_no_answer": ("金莲道长没有回答，而是看向摆在中央的青铜棺椁。", "narration", 148),
    "q_center_earth": ("“中央主土！”", "dialogue", 149),
    "q_geju_ask": ("楚元缜低声道：“这样的格局代表什么意思？”", "dialogue", 149),
    "q_wangsheng_ask": ("“是不是往生？”野生术士公羊宿，望向了钟璃。", "dialogue", 150),
    "q_wuxing_belief": ("钟璃点点头，道：“天地万物皆为五行幻化，古代人相信，人死后葬于墓，墓在土，若能在墓中摆下五行阵，死者终有一天，会从土中转生。”", "dialogue", 151),
    "q_chill_xqa": ("众人听的津津有味，许七安却忽然脊背一凉，道：", "narration", 152),
    "q_xqa_contradiction": ("“这不对啊，道长，你不是说死于天劫，灰飞烟灭？什么都没有了，那如何转生？这五行阵又有何用？”", "dialogue", 153),
    "q_daozhang_leave": ("金莲道长先是一愣，继而瞳孔微微缩，沉声道：“走吧，主墓探索过去了，没必要多逗留。”", "dialogue", 154),
    "q_about_to": ("许七安点点头，正要宣布撤退", "narration", 155),
    "q_sigh": ("突然听见了青铜棺椁里传来叹息声：", "narration", 155),
    "q_nilai": ("“你来啦........”", "dialogue", 156),
    "q_chill_one": ("一股凉意从尾椎骨升起，直窜头皮，许七安“咕噜”一声，吞咽了口吐沫，霍然扭头看向众人", "narration", 157),
    "q_others_calm": ("却发现他们脸色虽然严肃，却并没有惶恐。", "narration", 157),
    "q_daozhang_ask_you": ("金莲道长察觉到许七安无比难看的脸色，问道：“你怎么了？”", "dialogue", 158),
    "q_xqa_tell": ("“我听见，棺材里.......”许七安嘴唇嗫嚅几下，从牙缝里一字一句吐出：", "dialogue", 159),
    "q_xqa_tell2": ("“有——人——说——话。”", "dialogue", 160),
    "q_chill_all": ("一股凉意从众人尾椎骨窜起，头皮瞬间发麻。", "narration", 161),
    "q_zhongli_shiver": ("钟璃缓缓打了个寒颤，差点背不住丽娜。", "narration", 162),
    "q_chu_flee": ("楚元缜脸色铁青，声音又低又急促：“走，离开主墓，快点离开...........”", "dialogue", 163),
    "q_all_flee": ("这一刻，所有人都展现出了强烈的求生欲，没有废话，扭头就走。", "narration", 164),
    "q_sound_behind": ("这时，众人听见了生涩且沉重的摩擦声，从身后传来。", "narration", 166),
    "q_coffin_open": ("那是青铜棺椁揭开的声音。", "narration", 167),
}

Q: dict[str, dict] = {}
for key, (lit, kind, para) in QT.items():
    idx = SLICE.find(lit)
    hits = SLICE.count(lit)
    if idx < 0 or hits != 1:
        check("引文定位 %s" % key, False,
              "在切片内命中 %d 次（要求恰好 1 次）：%r" % (hits, lit[:30]))
        continue
    start = START + idx
    end = start + len(lit)
    ok = TEXT[start:end] == lit
    check("引文逐字 %s" % key, ok, "[%d,%d)" % (start, end))
    Q[key] = {
        "key": key,
        "quote": lit,
        "start": start,
        "end": end,
        "sourceHash": SOURCE_HASH,
        "kind": kind,
        "para": para,
        "occ": idx,
        "occInSlice": hits,
        "globalOcc": TEXT.count(lit),
    }


def qs(*keys: str) -> list[dict]:
    return [Q[k] for k in keys]


def qw(*pairs) -> list[dict]:
    """带 why 的引文（伏笔用）。"""
    out = []
    for key, why in pairs:
        item = dict(Q[key])
        item["why"] = why
        out.append(item)
    return out


# --------------------------------------------------------------------- 内容
tasks = [
    {
        "id": "T01",
        "who": "许七安（打头阵者）与随行的金莲道长、楚元缜、恒远、钟璃、后土帮众人",
        "objective": {
            "text": "由他先探路：自请走在最前、把众人留在身后，并限定他们「不要做多余的事」——第一份未知风险归他。这句是他当面对众人说的（dialogue），区间内没有写他为什么这样做。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_datou"),
        },
        "objectiveNote": "只引他自己说的那句话；他事后那句自我评价（「我这一波操作也算出尽风头了」）不是同一区间，登记在 S02 与主题解读。",
        "obstacle": {
            "text": "石门后没有空气，且火把只能照亮数丈，再往内全黑——先要解决的是「进不进得去」，而不是打不打得过。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_dark", "q_no_air"),
        },
        "obstacleNote": "两条都是叙述/现场对白给出的环境阻碍，不是我的归纳：「再等等，里面没有空气」是他当场给出的判断。",
        "action": {
            "text": "先按「不真正用力、静等几秒」的方式探神觉预警，再在门外等一刻钟确认火把不再黯淡，然后才半只脚踏入、举火把带队进入。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_shenjue", "q_wait_enter"),
        },
        "actionNote": "两句都是叙述对动作的直述；「等一刻钟」既是动作也是他付出的时间，见 costNote 的取舍说明。",
        "result": {
            "text": "队伍进入主墓：五根火把驱散了大部分黑暗，墓室在众人眼前展开。这是本区间为他这次打头阵写到的最好结果；主墓是否安全走完，要看到区间末尾才见分晓。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_enter_main"),
        },
        "resultNote": "result 只写到「进入并照明」这一步；不把「进得去」写成「墓穴安全」。",
        "cost": None,
        "costNote": "本区间没有写这次打头阵让他付出了什么。唯一像代价的是在门外停手等待的一刻钟，但那一句已作为 action 的依据，按纪律不重复引用；而「火把无法维持太久，终将熄灭」是预期损失，不是已付出的代价，也不作 cost。",
    },
    {
        "id": "T02",
        "who": "钟璃（司天监预言师；随队但不作战）",
        "objective": {
            "text": "给自己立一条硬规矩：绝不施展任何法术、绝不参与任何战斗。原文把它写成她自己的经验结论（叙述转述她的内心），不是叙述对事实的判定。",
            "basis": "explicit",
            "claimKind": "free_indirect",
            "quotes": qs("q_zhongli_rule"),
        },
        "objectiveNote": "「这是一位成熟的预言师总结出来的经验」说明这条规矩来自行业经验，不是谁下的命令；本区间没有任何诏令类依据。",
        "obstacle": None,
        "obstacleNote": "本区间没有任何人或事逼她施法或参战：没有战斗场面，也没有人受伤需要她出手。唯一的压力是公羊宿当众点破她的身份（q_gongyang_reveal），但那改变的是后土帮如何看待她，不是她要不要施法。没有阻碍就不编一个。",
        "action": {
            "text": "她只用最小的方式参与：被点破身份时「嗯嗯」点头带过；被公羊宿问「是不是往生」时，只口述五行与转生的说法，不动手。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_zhongli_nod", "q_wuxing_belief"),
        },
        "actionNote": "两处都是她本人的言语/应答（dialogue），不是叙述替她认定的动作。",
        "result": None,
        "resultNote": "「她全程没有施法、没有参战」是缺席判断：区间内**没有任何一句**写她没出手，也没有战斗可参加。把缺席写成 explicit 的 result 就是造证据，所以记 null；区间内她最后的状态仍是背着丽娜、只打了个寒颤（见 cost）。",
        "cost": {
            "text": "她身上有实际负担：背着昏迷的丽娜，恐惧袭来时「差点背不住丽娜」。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_zhongli_shiver"),
        },
        "costNote": "原文只写了「差点背不住」这一结果，没有写她因此放弃了什么；本栏不替她补动机。",
    },
    {
        "id": "T03",
        "who": "病夫帮主（后土帮，自称老盗墓贼）",
        "objective": {
            "text": "主张先别靠近中央棺椁，改成绕墙摸索、估测墓室大小、顺便找有价值的信息。这是他当面说出的建议（dialogue）。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_bfzz_advice"),
        },
        "objectiveNote": "「按照墓穴的格局，中央必定是墓穴主人的棺椁」是他的行内判断，不是叙述对墓内布局的认定——布局要到 T/世界设定里由高台上的实物印证。",
        "obstacle": {
            "text": "墓室深度未知：原文只给了宽度二十丈（60 米），深度没有数，而他这一栏的目标恰恰是「估测大小」。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_width", "q_depth_unknown"),
        },
        "obstacleNote": "两条合起来才成立：宽度可知、深度未知。单引「深度未知」会看不出他要估的是什么。",
        "action": {
            "text": "他没有直接跟名义上的领队许七安说，而是走到金莲道长身边提建议。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_bfzz_walk"),
        },
        "actionNote": "叙述只写了「走到金莲道长身边」，没有写他为什么绕过许七安。",
        "result": {
            "text": "道长当场采纳（「有理。」颔首），队伍随即按他的方案往左绕行，并因此看到了壁画。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_youli", "q_go_left"),
        },
        "resultNote": "「看到壁画」是这条方案的下游结果，引文给出的是路线与发现，不是壁画内容（内容归入别的条目）。",
        "cost": None,
        "costNote": "本区间没有写他为这条建议付出任何代价。许七安的腹诽（「领队的是我啊，为什么不找我商量？」）是许七安的反应，不是病夫帮主的代价。",
    },
    {
        "id": "T04",
        "who": "楚元缜（云鹿书院出身，天地会成员）",
        "objective": {
            "text": "想弄清许宁宴身上到底隐藏什么秘密——这是他内心直接提出的问题；紧接着他把范围收到「三次都走到这间偏室」这一条观察上。",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_chu_secret", "q_chu_3times"),
        },
        "objectiveNote": "这是他的内心疑问（inner），不是叙述对许七安的判定；「三次」也是他的观察，区间内没有第二处独立佐证。",
        "obstacle": {
            "text": "对方的秘密藏得很深，他把这一点连金莲道长一起算上。",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_chu_cang"),
        },
        "obstacleNote": "引的是他感叹的那半句；同一段里还有关于「三号」「堂兄」的猜测，所指在本区间没有交代，登记在 K04，不当作障碍依据。",
        "action": {
            "text": "沉默观察：目光在许七安与金莲道长之间来回审视。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_chu_gaze"),
        },
        "actionNote": "这是本区间他唯一被叙述写出的查探动作——没有问话、没有翻查。",
        "result": {
            "text": "区间内他没有得到答案，只得到一个更硬的判断：许宁宴绝非表面上那么简单。",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_chu_simple"),
        },
        "resultNote": "这是他的判断（inner），不是叙述认定的结论；把它读成「许宁宴确实有问题」就越过了原文。",
        "cost": None,
        "costNote": "本区间没有写他为这番查探付出任何代价，也没有写他因怀疑而采取行动后遭到反噬。",
    },
    {
        "id": "T05",
        "who": "许七安（推理者）；恒远、楚元缜与在场众人在旁",
        "objective": {
            "text": "从理性出发检查壁画逻辑：如果墓主就是壁画里那位篡位皇帝/道人，那这面壁画的存在本身就说不通。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_xqa_logic", "q_xqa_mural_odd"),
        },
        "objectiveNote": "目标以他提问的方式说出来；「有些地方不符合逻辑」是他自己的判断（他还用大奉陛下改史书作类比）。",
        "obstacle": {
            "text": "恒远当场给出一个能顶掉他前提的反向解释：墓若是臣子后人所建，批判墓主很正常。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_hengyuan_counter"),
        },
        "obstacleNote": "这是恒远的反驳（dialogue），不是叙述对墓主身份的认定。",
        "action": {
            "text": "用「没人会给仇人建这种规格的大墓」反驳，并留下条件：除非壁画内容无比真实。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_xqa_rebut", "q_xqa_unless"),
        },
        "actionNote": "两句都是他的原话；他给出的是一条条件式推理，不是对壁画真伪的结论。",
        "result": {
            "text": "众人点头接受了他的说法，楚元缜顺势把话题推进到「这场雷霆是不是另有寓意」。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_accepted"),
        },
        "resultNote": "结果只到「被接受」这一层：原文没有写他的解释被证实，也没有写反对意见被驳倒。",
        "cost": None,
        "costNote": "本区间没有写他为这番推理付出代价：没有争执、没有得罪人、也没有耽误行程的记载。",
    },
    {
        "id": "T06",
        "who": "楚元缜（提问者）→ 金莲道长（作答者）；许七安、恒远与天地会众人为听众",
        "objective": {
            "text": "楚元缜要一个解释：以道人的实力，等闲雷霆劈不死他，这场雷击是不是还有别的寓意。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_chu_ask_thunder"),
        },
        "objectiveNote": "这一栏的目标属于**提问者楚元缜**，不属于道长；道长在本任务里对应的是 action。跨人物记一条任务，是因为「问—答」是同一个动作对。",
        "obstacle": {
            "text": "「天劫」对在场所有人都是陌生词汇——没有人能自己判断，只能等道长的解释。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_strange_word"),
        },
        "obstacleNote": "障碍是知识空缺，不是有人阻拦；原文用「这是一个陌生的词汇」直述。",
        "action": {
            "text": "金莲道长一字一句给出答案「是天劫」，并补出道门体系：二品叫「渡劫」，度过天劫就是一品「陆地神仙」，人宗道首就是死在天劫里灰飞烟灭。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_tianjie", "q_daomen_rank", "q_tianjie_echo"),
        },
        "actionNote": "前两条是他的原话；第三条「天劫？」是**听者的反问**（许七安等人重复这个陌生词），引它是为了标出问答的接口，不代表叙述对它的确认。",
        "result": {
            "text": "天地会众人把品阶记了下来；许七安还由此想起旧事——地宗道首正是渡劫失败、被魔性反噬堕落成妖道；楚元缜随即把墓主人定为「巅峰二品，距离陆地神仙只差一线」。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_remember", "q_dizong", "q_chu_conclude"),
        },
        "resultNote": "「记下来」是叙述直述；「我想起来了」是许七安的原话（dialogue，他在复述道长此前告诉过他的一件事）；墓主品级是楚元缜的推断，都不是叙述认定。",
        "cost": None,
        "costNote": "本区间没有写道长为这次解答付出任何代价（也没有写他因透露道门体系而受约束或遭反噬）。",
    },
    {
        "id": "T07",
        "who": "许七安（提醒者）／金莲道长（被提醒者）",
        "objective": {
            "text": "想拦住道长那句「过于笃定的判断」——他心里把这叫「别乱插旗」，即不要在事前把结论钉死。",
            "basis": "inferred",
            "claimKind": "inner",
            "quotes": qs("q_bieluan"),
        },
        "objectiveNote": "按 inferred 标注：这句内心话表达的是他的态度，原文并没有把它写成一条「想要做什么」的目标陈述，把态度读成目标是**我的归纳**；引文本身逐字成立。",
        "obstacle": {
            "text": "道长的判断是有依据的：死于天劫、灰飞烟灭，所以墓应是衣冠冢、不会有太大危险——这话不容易反驳。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_yiguanzhong"),
        },
        "obstacleNote": "把道长的话当障碍依据，是因为它先给出了一个自洽的低风险结论；许七安手里没有反证，只能口头提醒。",
        "action": {
            "text": "他当众说了出来，方式是「颇为轻松的调侃」，而不是郑重提出反对；原话就是那句提醒。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_qingsong", "q_chaqi_warn"),
        },
        "actionNote": "两栏依据分别取自不同段落：objective 是紧随其后的那句内心话（p0124），action 是他说这句话的现场（p0123）。同一栏内两条引文同属一个长句（叙述 + 引语），这不构成跨栏共用。",
        "result": None,
        "resultNote": "区间内没有写道长是否接受这句提醒：他没有回应，原文紧接着就转去写队伍走向主墓另一侧。所以 result 记 null，不把「提醒过」写成「提醒奏效」。",
        "cost": None,
        "costNote": "本区间没有写许七安为这句提醒付出任何代价（没有人不快、也没有人反驳他）。",
    },
    {
        "id": "T08",
        "who": "楚元缜（先喊撤）与在场所有人（含背着丽娜的钟璃、后土帮众人）",
        "objective": {
            "text": "立刻离开主墓：楚元缜脸色铁青，声音又低又急促地喊「走，离开主墓，快点离开」。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_chu_flee"),
        },
        "objectiveNote": "撤离的目标由楚元缜喊出；原文没有写是谁先意识到危险，只写了他先出声。",
        "obstacle": {
            "text": "威胁无法定位：棺椁里传出叹息声（许七安听见），而其他人当时并未显出惶恐——不知道是什么、不知道会不会再来。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_sigh", "q_others_calm"),
        },
        "obstacleNote": "两条都落在同一个不确定上：声源在棺内、且只有许七安先听见。",
        "action": {
            "text": "没有人废话，所有人扭头就走。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_all_flee"),
        },
        "actionNote": "叙述只写「扭头就走」，没有写队形、路线，也没有写是否有人殿后。",
        "result": None,
        "resultNote": "区间在这里结束：原文只写到「扭头就走」和身后的摩擦声，没有写他们是否走出主墓、是否有人受伤、有没有被追上。按纪律不把「开始逃」记成「逃成功」（结束≠成功）。",
        "cost": None,
        "costNote": "同 resultNote：撤离的代价（是否丢下东西、是否有人受伤）在本区间内没有写，不补。",
    },
    {
        "id": "T09",
        "who": "金莲道长（鉴物者）／楚元缜（同行观察者）",
        "objective": {
            "text": "判断高台四角那四具干尸与甲胄是不是道门之物——楚元缜先提出「这似乎是道门作品？」这个待验的问题。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_chu_sword_q"),
        },
        "objectiveNote": "目标以楚元缜的疑问句给出（dialogue）；这不是叙述对干尸来历的认定。",
        "obstacle": {
            "text": "凭据只能猜：甲胄上的上古符文，道长自认「这种上古符文我只能猜测一二」。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_rune_guess"),
        },
        "obstacleNote": "障碍是识别能力的上限，是道长自己说出的（dialogue），不是叙述对他水平的评价。",
        "action": {
            "text": "逐一查看四具干尸与甲胄后给出方位属性：西主金，南北东分主火、水、木。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_corpse_study", "q_place_five"),
        },
        "actionNote": "前一句是叙述写出的查看动作，后一句是他的判断内容；两者都只写「看」与「说」，没有写他动手查验符文。",
        "result": {
            "text": "得出「确实有道门痕迹」这一有限结论，并留下一个空缺：他没有回答「土呢？」——而是把目光转向中央的青铜棺椁。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_daomen_trace", "q_no_answer"),
        },
        "resultNote": "「土」的答案由楚元缜接出（「中央主土！」），不是道长的回答；这一层分工照实记，不合并不写。",
        "cost": None,
        "costNote": "本区间没有写他为这次鉴定付出任何代价；他自陈「只能猜测一二」是能力限度，不是代价。",
    },
    {
        "id": "T10",
        "who": "许七安（质疑者）／金莲道长（被质疑者）",
        "objective": {
            "text": "把两套说法并起来问一个不能两全的问题：既然墓主死于天劫、灰飞烟灭，那五行阵如何让他转生、这阵又有何用。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_xqa_contradiction"),
        },
        "objectiveNote": "目标是当场把这个矛盾问出来（dialogue）；原文还写他发问前「忽然脊背一凉」，那是他的反应，不作目标依据。",
        "obstacle": {
            "text": "「转生」这套说法是钟璃以葬制常识给出的，听起来完整自洽；要反驳它，只能靠另一套说法（灰飞烟灭）来对撞。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_wuxing_belief"),
        },
        "obstacleNote": "把钟璃的完整说法当障碍依据：它先立起一个自洽的解释，许七安的问题才有对撞的对象。",
        "action": {
            "text": "他直接向道长发问，没有得到解释性回答——道长先是一愣、继而瞳孔微微缩，改口要求撤出主墓。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_daozhang_leave"),
        },
        "actionNote": "action 这里记的是**被质疑方的处置**（终止探索），不是质疑者的动作；质疑者的动作已由 objective 的那句问话承载，两栏区间不重叠。",
        "result": {
            "text": "探索就此终止：许七安点头，正要宣布撤退——随即被棺椁里的叹息声打断。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_about_to"),
        },
        "resultNote": "结果是「探索被叫停」，不是「矛盾被解答」：区间内没有任何人对这个矛盾作出解释（见 K05）。",
        "cost": None,
        "costNote": "本区间没有写他因这次质疑付出任何代价：没有人责备他，也没有写他失去什么；探索被叫停是道长的处置，方向相反，不记作他的代价。",
    },
    {
        "id": "T11",
        "who": "恒远（提问者）／金莲道长（作答者）；楚元缜、许七安为旁证",
        "objective": {
            "text": "弄清壁画上那条巨蛇是什么——恒远先问「这么大的蛇，是妖族？」。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_hengyuan_snake"),
        },
        "objectiveNote": "目标以恒远的疑问句给出（dialogue）；这不是叙述对巨蛇来历的认定。",
        "obstacle": {
            "text": "队里没有人认得：楚元缜四处云游也摇头说不知道——甲子荡妖后大妖渐绝，二十年前山海关战役虽有妖族出现，但他当时还是孩童。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_chu_dontknow"),
        },
        "obstacleNote": "障碍是阅历不足，由叙述以楚元缜的履历直述；「不知道」是叙述转述（他摇头），不是原话引语。",
        "action": {
            "text": "金莲道长给出判别标准：若知道妖族五品会凝聚妖丹，就不会把这条蛇认作妖族；他进而判断它是远古神魔的血裔，而非真正的神魔。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_yuan_ask", "q_yuangu_shenmo"),
        },
        "actionNote": "两句都是他的原话（dialogue）；判别标准是他给出的知识，不是叙述认定壁画上的蛇确实不是妖族。",
        "result": {
            "text": "在场接受了这个答案，并把它推进成对实力的判断：楚元缜说「即使如此，这道人能斩大蛇，实力恐怕非凡寻常」。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_snake_can"),
        },
        "resultNote": "结果只到「接受并顺推」这一层：原文没有写这个判断被证实，也没有写有人反对。",
        "cost": None,
        "costNote": "本区间没有写任何一方为这次问答付出代价；也没有写道长因透露妖族知识而受到限制。",
    },
    {
        "id": "T12",
        "who": "许七安与楚元缜（共同持火把看壁画的人）",
        "objective": {
            "text": "把壁照亮、逐段读完：两人一前一后高举火把照明，整面墙被当作画卷边走边看。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_mural_lift"),
        },
        "objectiveNote": "目标是叙述直述的照明动作；原文没有写他们想从壁画得到什么结论。",
        "obstacle": {
            "text": "墓内没有现成照明可用，只能靠手里的火把照出局部——火光范围有限，壁画又长，必须边走边照才能读完整面墙。",
            "basis": "derived",
            "claimKind": "narration",
            "quotes": qs("q_dark"),
        },
        "obstacleNote": "按 derived 标注：照明不足这一点在甬道口被明写（「只能照亮范围数丈距离」），把它当作读壁画的障碍是**我的跨段推导**；原文在壁画段没有重述这一限制。",
        "action": {
            "text": "两人一边走一边把壁画内容读出来、互相印证——楚元缜在旁给出联想，许七安两次认出「这不就是我们之前看到的壁画吗」。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_mural_same1"),
        },
        "actionNote": "引的是叙述对画面对应关系的直述（群臣膜拜高台与外头那幅一模一样），不是他们两人的原话。",
        "result": {
            "text": "读出的壁画序列被整理成一条完整叙事：皇帝为答谢道人铸高台、率百官膜拜。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_emperor_worship"),
        },
        "resultNote": "这里只取序列中被独立成段的一句作为结果锚点；壁画全序列的内容与解读归入 K06 与 T05，不在这条任务里再列一遍。",
        "cost": None,
        "costNote": "本区间没有写他们为看壁画付出任何代价（没有人受伤、没有人因逗留而遇险）。",
    },
    {
        "id": "T13",
        "who": "许七安（带队者）",
        "objective": {
            "text": "把照明从会烧尽的火把换成墓里现成的烛台，让队伍在火把熄灭后仍有光可用——原文写出这条动机：火把无法维持太久，终将熄灭。",
            "basis": "explicit",
            "claimKind": "free_indirect",
            "quotes": qs("q_torch_wane"),
        },
        "objectiveNote": "这句是叙述转述他的判断（free_indirect），不是他本人说出口的话；本区间没有引号内的同义对白。",
        "obstacle": {
            "text": "通道两边是浅浅的水坑、水质浑浊：点烛的同时还要防着水里藏东西，注意力被分成两半。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_pools"),
        },
        "obstacleNote": "两条合起来才是完整阻碍：一手是燃料将尽，一手是水下不明；原文没写水里确实有东西，只写了防备这个动作。",
        "action": {
            "text": "他一边让人注意两侧水池，一边亲手点亮通道边缘的烛台；楚元缜也一起点了蜡烛。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_pool_watch", "q_candle_light"),
        },
        "actionNote": "两条都是叙述对动作的直述；「一边…一边…」正说明两件事同时做，不是先后因果。",
        "result": {
            "text": "照明被接替：烛台从通道边缘一直连绵到高台，一簇簇烛光为主墓带来更多光明。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_candles_along"),
        },
        "resultNote": "结果只到「亮起来」：原文没有写他们是否真的靠这些蜡烛走完全程（区间在别处结束）。",
        "cost": None,
        "costNote": "本区间没有写换照明付出了什么代价：蜡烛是墓里现成的（不是他们的物资），也没有写有人因点烛而受伤或落在后面。",
    },
    {
        "id": "T14",
        "who": "许七安（独自觉察者）／金莲道长（被追问者）",
        "objective": {
            "text": "在宣布撤退之前，把刚听到的那声叹息告诉别人——他听见棺椁里有叹息声，正要宣布撤退时被打断。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_about_to", "q_sigh"),
        },
        "objectiveNote": "这里记的是「把听见的事说出去」这个动作目标；他的恐惧反应（脊背一凉）不作目标依据。",
        "obstacle": {
            "text": "他先独自撞上了没人共享的感知：叙述写他脊背一凉、吞了口吐沫、霍然扭头，却发现众人「脸色虽然严肃，却并没有惶恐」。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_chill_one", "q_others_calm"),
        },
        "obstacleNote": "障碍是**信息只有他一个人有**（别人没有对应反应），而不是有人拦着他不让说。",
        "action": {
            "text": "被道长问「你怎么了」之后，他嘴唇嗫嚅几下，从牙缝里一字一句说出「有——人——说——话」。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_daozhang_ask_you", "q_xqa_tell2"),
        },
        "actionNote": "两句都是对白：道长先问、他后答；他说出口的内容只有这五个字，区间内没有更多补充。",
        "result": {
            "text": "话一出口，恐惧才扩散到所有人：「一股凉意从众人尾椎骨窜起，头皮瞬间发麻。」",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_chill_all"),
        },
        "resultNote": "结果是**转述造成的情绪扩散**，不是「危险被确认」：原文没有写任何人因此知道棺里是谁、也没写有人去查看。",
        "cost": None,
        "costNote": "本区间没有写他为说出这件事付出代价；紧接着的逃跑是全队一致的求生反应，方向相同，不记作他个人的代价。",
    },
    {
        "id": "T15",
        "who": "许七安（被要求走前面的人）／金莲道长（被请求的人）",
        "objective": {
            "text": "不想第一个进甬道，于是当众请道长走前面——理由是「我还只是个孩子」。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_ask_lead"),
        },
        "objectiveNote": "目标由他本人的请求给出（dialogue）；「我还只是个孩子」是他给出的理由，不是叙述对他年龄的判断。",
        "obstacle": {
            "text": "他其实没有感知到危险，只是心里发怵：原文紧接一句写他心里承认「就是有点怂，勾起了我儿时看恐怖片的心理阴影」。",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_scared_inner", "q_ask_lead_body"),
        },
        "obstacleNote": "障碍是他自己的心理而非外部威胁；「有些踌躇」是叙述写出的外部可见状态，与内心那句互为表里。",
        "action": {
            "text": "道长反问「有感知到危险？」，他没有拿这个当台阶，而是深吸一口气、举着火把自己先进去；随后到石门前按门试探神觉预警，再回报「没有危险」。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_enter_corridor", "q_no_danger_ok"),
        },
        "actionNote": "两条都是叙述写出的动作与对白：先进入、后探门；他没有再要求别人替他走前面。",
        "result": {
            "text": "道长据此下令开门，石门被推开，队伍进入主墓。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_open_ok", "q_door_open"),
        },
        "resultNote": "结果是他的探路被采纳并放行；原文没有写他的恐惧被谁评价或嘲笑。",
        "cost": None,
        "costNote": "本区间没有写他为这次让步付出代价：没有受伤、没有被谁指责，也没有写他丢了面子（后土帮的低评在更早就已成立）。",
    },
    {
        "id": "T16",
        "who": "楚元缜（追问者）／金莲道长（拒答者）；许七安在旁",
        "objective": {
            "text": "想知道那位篡位皇帝与道门双修流派的关系——他当面问「这位皇帝，与道门双修流派有莫大的渊源啊」。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_chu_liupai"),
        },
        "objectiveNote": "他真正想问的其实是另一句（这道长会不会是那支流派的开宗祖师）——那是他的内心话，登记在同任务 action 栏，两栏区间不重叠。",
        "obstacle": {
            "text": "他不敢直接问，只把话说到「渊源」为止；真正的疑问（是不是开宗祖师）只留在心里。",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_chu_realask"),
        },
        "obstacleNote": "障碍是他自己的顾虑与分寸，不是道长拒绝回答——原文写的是「他真正想说的是」，说明他换了说法。",
        "action": {
            "text": "许七安在旁点头附和（他心里也觉得楚元缜聪明、自己也这么想），并和楚元缜一起看向金莲道长，等一个回答。",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_xqa_agree"),
        },
        "actionNote": "引的是许七安这边的内心附和（inner）；楚元缜已经问出口的那句归 objective，两栏不共用。",
        "result": {
            "text": "只得到三个字：「不知道。」——道长的回答言简意赅，追问没有下文。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_dontknow2"),
        },
        "resultNote": "结果是**没有获得信息**，不是「确认无关」：不知道≠否定，也不等于他在隐瞒（原文没有写他的心理）。",
        "cost": None,
        "costNote": "本区间没有写楚元缜为这次碰壁付出代价；也没有写这次拒答影响后续行动。",
    },
    {
        "id": "T17",
        "who": "许七安、楚元缜、恒远（三人各自解读同一幅蛇壁画）",
        "objective": {
            "text": "三人各自要给壁画上的巨蛇一个说法：许七安顺着道长的话推测妖丹与体型的关系，楚元缜心里隐约有了猜测，恒远则直接把它归为佛法降不服的妖孽。",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_three_views1", "q_three_views2", "q_three_views3"),
        },
        "objectiveNote": "三条都是各自的内心（inner），由叙述以「三人的想法各有不同」领起；它们不是同一套结论，也不互为印证。",
        "obstacle": {
            "text": "三人手里都没有可验证的材料：许七安只能从道长话里反推，楚元缜只说「隐约有个猜测」，恒远则按自己的佛法标准下判断。",
            "basis": "derived",
            "claimKind": "inner",
            "quotes": qs("q_yuan_ask"),
        },
        "obstacleNote": "按 derived 标注：道长给的是判别标准（妖丹），把它当作「三人都缺可验证材料」的依据是**我的归纳**；原文没有一句直述他们无从验证。",
        "action": {
            "text": "壁画序列继续被读完：道人斩蛇、受皇帝率百官膜拜、随后挥剑斩杀皇帝篡位，接着是白甲与黑甲军队的战争。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_mural_daoren", "q_mural_worship2", "q_mural_war"),
        },
        "actionNote": "三条都是叙述对壁画内容的直述（画上画了什么可以当事实），不是三人对它的解读。",
        "result": {
            "text": "读到的后续内容把「多人运动」一段也接了进来：皇帝平定叛乱后沉迷其中。这一序列成为后面许七安质疑「壁画为何画得这么直白」的直接材料。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_mural_orgy2"),
        },
        "resultNote": "结果只到「材料被读到」：三人各自的说法在本区间都没有被验证或推翻（见 K06）。",
        "cost": None,
        "costNote": "本区间没有写三人为这些解读付出任何代价；也没有写谁因判断错误而受损。",
    },
]

causeEdges = [
    {
        "id": "C01",
        "from": "公羊宿当众点破钟璃是司天监的术士",
        "to": "后土帮与病夫帮主重排队伍地位：钟璃被看成「核心人物之一」",
        "trigger": "机制是**身份信息替换了能力判断的依据**：在此之前钟璃只是个「闷不吭声」的同行者，公羊宿一句行内话把她的师门背景公开，后土帮先是被惊到，病夫帮主随即把她归入核心人物。触发点是那句公开的对白，不是时间相邻。",
        "basis": "derived",
        "claimKind": "dialogue",
        "quotes": qs("q_gongyang_reveal", "q_houtu_shock", "q_bfzz_core"),
        "note": "「核心人物之一」是病夫帮主心里的话（inner），不是叙述对钟璃地位的认定。",
    },
    {
        "id": "C02",
        "from": "许七安自请打头阵、并在队伍里充当抗打击的角色",
        "to": "连后土帮普通成员也据此判定他地位最低（「探路打头阵，危险当盾牌」）",
        "trigger": "机制是**可见行为被读成身份信号**：同一批动作——走在最前、挨打当盾——在后土帮眼里不是贡献而是「武夫就是如此粗鄙」的证据；判断因此从病夫帮主一个人扩散到普通成员。",
        "basis": "derived",
        "claimKind": "narration",
        "quotes": qs("q_datou", "q_shield2", "q_everyone_low", "q_shield_line"),
        "note": "原文没有写「因为…所以…」，是把「打头阵→当盾牌→连普通成员也看出低等地位」三句连起来读；把这三句看成并列评论也说得通，此点登记在 U04。",
    },
    {
        "id": "C03",
        "from": "火把在石门前黯淡了一下",
        "to": "许七安判定门内没有空气，推迟进入，在门外等了一刻钟",
        "trigger": "机制是**用火焰状态反推空气**：火焰变暗说明缺氧，于是他当场叫停；等到火把不再黯淡，他才带队进入。触发点是他看见火把黯淡的那一眼。",
        "basis": "derived",
        "claimKind": "narration",
        "quotes": qs("q_no_air", "q_wait_enter"),
        "note": "「没有空气」是他当场给出的判断（他说出口），不是叙述给出的物理解释；我等一刻钟后火把不暗这一观察，才把它当作已被行动确认。",
    },
    {
        "id": "C04",
        "from": "病夫帮主建议先绕墙勘察、不走中央",
        "to": "道长采纳，队伍改走左侧绕行，发现巨幅壁画",
        "trigger": "机制是**方案被采纳改变路线**：原本的默认走法是直奔中央棺椁，建议把路线改成沿墙勘察，路线一改，墙上的壁画才进入视野，后续所有推理都由这面墙上的内容触发。",
        "basis": "derived",
        "claimKind": "narration",
        "quotes": qs("q_bfzz_advice", "q_youli", "q_go_left"),
        "note": "「发现壁画」在这里只作为**路线改变的下游结果**；壁画内容本身的含义另记，不在这条边上推断。",
    },
    {
        "id": "C05",
        "from": "钟璃口述五行阵可让死者转生",
        "to": "许七安推出与「灰飞烟灭」的矛盾；道长一愣、瞳孔微缩，改口要求撤出主墓",
        "trigger": "机制是**新知识撞上旧断言**：道长先前断言墓主「死于天劫，灰飞烟灭」，钟璃给出的葬制目的却是「终有一天会从土中转生」；两者不可能同时成立，而提出矛盾的人此前刚被叙述点明「在破案方面有着异于常人的天赋」，于是道长选择终止话题与探索，而不是回答。",
        "basis": "derived",
        "claimKind": "narration",
        "quotes": qs("q_wuxing_belief", "q_xqa_credit", "q_xqa_contradiction", "q_daozhang_leave"),
        "note": "「改口要求撤出」是叙述写出的动作与对白；「因为被问住」是我的机制解释（derived），原文没有写他为什么不再逗留。",
    },
    {
        "id": "C06",
        "from": "道长的低风险判断（衣冠冢、不会有太大的危险）",
        "to": "其他人跟着松了口气，风险预期下降",
        "trigger": "机制是**权威的风险定级被接受，情绪随之下降**：判断由唯一懂道门体系的人给出且语气笃定，听众没有可用的反驳材料，于是集体放松。",
        "basis": "derived",
        "claimKind": "narration",
        "quotes": qs("q_yiguanzhong", "q_songqi"),
        "note": "这条边**只连到「松了口气」为止**。区间末尾的恐慌与棺椁异动不再连回来：那一段由棺中人语触发（C07），与这里的放松只是时间相邻，不构成机制。",
    },
    {
        "id": "C07",
        "from": "青铜棺椁里传出叹息声（许七安先听见）",
        "to": "许七安转述给道长 → 众人头皮发麻 → 楚元缜喊撤 → 所有人扭头就走",
        "trigger": "机制是**无法解释的、只有一人先感知到的声音推翻了安全判断**，且恐慌是经**转述**扩散的：叙述的顺序是「许七安听见→众人并没有惶恐→道长问他怎么了→他一个字一个字说出来→众人头皮发麻→楚元缜喊走→所有人扭头就走」。触发点是那一声叹息。",
        "basis": "derived",
        "claimKind": "narration",
        "quotes": qs("q_sigh", "q_others_calm", "q_daozhang_ask_you", "q_xqa_tell", "q_xqa_tell2", "q_chill_all", "q_chu_flee", "q_all_flee"),
        "note": "每一步都有原文直述；连成一条边靠的是叙述给出的顺序与「转述后才发麻」这一落差。谁真正听见了那声叹息，见 K01。",
    },
    {
        "id": "C08",
        "from": "道长说「走吧，主墓探索过去了，没必要多逗留」",
        "to": "许七安点头、正要宣布撤退（随即被棺中叹息打断）",
        "trigger": "机制是**命令进入执行准备**：道长下令，许七安作为带队者准备把撤退宣布出去。这条边在原文里被下一个事件截断——真正让所有人跑起来的是那声叹息（C07），不是这道命令。",
        "basis": "explicit",
        "claimKind": "narration",
        "quotes": qs("q_daozhang_leave", "q_about_to"),
        "note": "保留这条边是为了区分「有序撤退」与「恐慌逃跑」两个不同的触发源。",
    },
]

rejectedEdges = [
    {
        "id": "R01",
        "wouldBe": "所有人扭头就走 → 青铜棺椁揭开的声音",
        "why": "两句紧挨着（p0164→p0166），但原文没有写两者有联系：既没写揭开是逃跑造成的，也没写是谁/什么揭开的。方向与机制都缺，只凭时间相邻不连边。",
        "quotes": qs("q_all_flee", "q_sound_behind"),
    },
    {
        "id": "R02",
        "wouldBe": "壁画里的篡位道人 → 这座墓的主人",
        "why": "壁画是被观看的图像。原文只让许七安提出假设（「如果这座墓的主人是壁画里的皇帝」）、让楚元缜推断品级，没有任何确认。人物猜测不是叙述事实，不连边。",
        "quotes": qs("q_xqa_mural_odd", "q_chu_conclude"),
    },
    {
        "id": "R03",
        "wouldBe": "公羊宿点破钟璃身份 → 钟璃立誓不施法不参战",
        "why": "两条不相邻也无机制：她的规矩被原文写成「一位成熟的预言师总结出来的经验」，是她自己早先的结论；身份被点破改变的是别人怎么看她，不是她要不要出手。不连边。",
        "quotes": qs("q_gongyang_reveal", "q_zhongli_rule"),
    },
]

states = [
    {
        "id": "S01",
        "who": "后土帮（含病夫帮主）对钟璃的认知",
        "before": {
            "text": "不知道她是司天监的术士——身份被当众说出时，后土帮成员「满脸愕然，像是被惊到了」。惊讶本身即此前不知情（inferred）。",
            "basis": "inferred",
            "claimKind": "narration",
            "quotes": qs("q_houtu_shock"),
        },
        "beforeNote": "「不知道」是从「被惊到」反推的（inferred），区间内没有一句直述他们原先不知道。利用「真人不露相」这句也可以反推，但那是病夫帮主心里的评语。",
        "after": {
            "text": "把她归入「核心人物之一」：真人不露相。",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_bfzz_core"),
        },
        "afterNote": "后值是病夫帮主的心里话（inner），代表他这一侧的评价；原文没有写后土帮普通成员是否也这么想。",
        "anchor": {
            "text": "锚点是公羊宿当众点破钟璃身份这句话。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_gongyang_reveal"),
        },
        "anchorNote": "身份公开是这一前后值之间唯一被写出的触发事件。",
    },
    {
        "id": "S02",
        "who": "后土帮对许七安地位的判断",
        "before": {
            "text": "还只是病夫帮主一个人的看法：他「愈发觉得此人地位最低」。",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_bfzz_low"),
        },
        "beforeNote": "「愈发」说明这是加深中的既有判断，不是第一次形成；本区间只能取到加深后的这一句。",
        "after": {
            "text": "扩散到全队：「不止是病夫帮主，连普通成员也看出许七安的低等地位」。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_everyone_low"),
        },
        "afterNote": "这是后土帮的看法，不是叙述对许七安实际地位的认定；许七安自己的评价相反（「作用最大，道长他们都要倚仗我」），两边并列记在主题解读里。",
        "anchor": {
            "text": "锚点是他打头阵探路、以及被当成盾牌这件事。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_shield_line"),
        },
        "anchorNote": "原句紧跟在「连普通成员也看出」之后，形如解释句；把它当作锚点是最自然的读法，但两句也可能是并列评论，见 U04。",
    },
    {
        "id": "S03",
        "who": "众人对这座墓的风险预期",
        "before": {
            "text": "紧张：进偏室时「心情沉重」，甬道里「谁都没有说话，凸显出众人内心的紧张」。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_enter_pian", "q_quiet"),
        },
        "beforeNote": "两条都是叙述对气氛的直述，不是某个人的判断。",
        "after": {
            "text": "放松下来：听道长判定是衣冠冢、不会有太大危险后，「其他人也松了口气」。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_songqi"),
        },
        "afterNote": "这条状态在区间末尾还会再翻转（见 S04），两条状态分开记，不合并成一条曲线。",
        "anchor": {
            "text": "锚点是道长的「衣冠冢、不会有太大的危险」这句判断。",
            "basis": "explicit",
            "claimKind": "dialogue",
            "quotes": qs("q_yiguanzhong"),
        },
        "anchorNote": "判断的可靠性没有第三方印证；本区间内它确实立刻改变了众人的情绪。",
    },
    {
        "id": "S04",
        "who": "众人的行动状态（整体）",
        "before": {
            "text": "有序撤离的准备态：许七安点头，「正要宣布撤退」。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_about_to"),
        },
        "beforeNote": "这是被下一件事打断的那个瞬间；说明在叹息声之前，队伍仍在按领队的节奏走。",
        "after": {
            "text": "恐慌逃跑：「所有人都展现出了强烈的求生欲，没有废话，扭头就走」。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_all_flee"),
        },
        "afterNote": "原文没有写队形、路线、是否有人殿后；也没有写他们是否逃出（见 T08.resultNote）。",
        "anchor": {
            "text": "锚点是棺椁里的叹息声，以及许七安把它一个字一个字转述出来。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_nilai", "q_xqa_tell2"),
        },
        "anchorNote": "转述是恐慌扩散的节点：叙述在转述之后才写众人头皮发麻。",
    },
    {
        "id": "S05",
        "who": "青铜棺椁（物）的状态",
        "before": {
            "text": "静置在高台中央，被看见、未被触碰。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_coffin_center"),
        },
        "beforeNote": "原文只写它摆在那里；没有任何人靠近它的描写。",
        "after": {
            "text": "传出「揭开的声音」——原文写的是声音，不是被看见打开。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_coffin_open"),
        },
        "afterNote": "「那是青铜棺椁揭开的声音」是叙述对声音来源的命名/判断，不等于有人目击棺椁开启；此点登记在 K03。",
        "anchor": {
            "text": "锚点是众人从身后听见的生涩且沉重的摩擦声。",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_sound_behind"),
        },
        "anchorNote": "声音在众人开始逃跑之后才被听见，前后值的时间关系照实记，不颠倒。",
    },
    {
        "id": "S06",
        "who": "许七安对金莲道长的认知",
        "before": {
            "text": "先前没有细想的疑点：「同时，许七安想起以前没有注意道的细节。」",
            "basis": "explicit",
            "claimKind": "narration",
            "quotes": qs("q_recall_detail"),
        },
        "beforeNote": "前值是「没注意过」，不是「不知道」——他随即用旧事把这批细节串了起来。",
        "after": {
            "text": "把旧事串成一条解释：如果道长是残魂，一切就可以解释（连他喜欢猫也解释得通，因为人和猫都不是自己的肉身）；但仍留下一个疑问——残魂能活这么久？",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_canhun_explain", "q_canhun_doubt"),
        },
        "afterNote": "整段都是他的内心独白（inner）：原文没有以叙述身份认定「金莲道长是残魂」。这条解释是他的归纳（条件句「如果…就可以解释」），不是事实认定。",
        "anchor": {
            "text": "锚点是他回忆起的平远伯府之战：遭遇被神殊俯身的恒慧时，道长当时的操作是「元神莽上去」——正是这件旧事让他觉得不对（法宝呢？法术呢？金丹呢？）。",
            "basis": "explicit",
            "claimKind": "inner",
            "quotes": qs("q_pingyuan"),
        },
        "anchorNote": "锚点只取「回忆起的旧事」这一句（含他自陈「果然是残魂」的起点），与 after 的两条引文（条件式解释、残魂寿命之疑）分属不同句子，区间不重叠。",
    },
]

knowledgeGaps = [
    {
        "id": "K01",
        "who": "在场众人 vs 许七安",
        "known": "许七安听见棺里有人说话，并把这件事一个字一个字说了出来。",
        "unknown": "其他人是否也**亲耳**听见了那声叹息——叙述只写他听见、其他人当时「并没有惶恐」，随后在转述之后才头皮发麻。",
        "basis": "unverified",
        "quotes": qs("q_chill_one", "q_others_calm", "q_chill_all"),
        "note": "两种读法都成立：①只有他听见（信息不对称）；②别人也听见但没当真，直到他开口才反应过来。原文没有裁定，不替它选。",
    },
    {
        "id": "K02",
        "who": "在场所有人",
        "known": "棺椁里传出「你来啦」三个字（叹息声）。",
        "unknown": "说话的是谁、是不是墓主人、这句话是对谁说的。区间内没有任何交代。",
        "basis": "unverified",
        "quotes": qs("q_nilai"),
        "note": "「你来啦」在区间内只出现一次，按纪律不登记为伏笔（见 notForeshadows），只登记为未知。",
    },
    {
        "id": "K03",
        "who": "在场所有人",
        "known": "众人从身后听见生涩且沉重的摩擦声，叙述把这声音称作「青铜棺椁揭开的声音」。",
        "unknown": "棺椁是否真的被打开、被谁/什么打开、打开后是什么——区间内只到「听见」，没有目击。",
        "basis": "unverified",
        "quotes": qs("q_sound_behind", "q_coffin_open"),
        "note": "不把「声音」写成「棺椁已打开」；下一章的标题在区间之外，不能拿来当本区间的结论。",
    },
    {
        "id": "K04",
        "who": "楚元缜（单方面怀疑）",
        "known": "他确信许宁宴不简单，并自列两种可能解释他三次重返同一偏室。",
        "unknown": "秘密是什么；他提到的「三号」「他堂兄」具体指谁——区间内只有他的内心话，没有任何说明。",
        "basis": "unverified",
        "quotes": qs("q_chu_3times", "q_chu_cang"),
        "note": "不得用本区间之外的设定替原文补出「三号是谁」；本区间内它只是个未展开的指称。",
    },
    {
        "id": "K05",
        "who": "许七安 → 金莲道长",
        "known": "许七安指出：若墓主死于天劫、灰飞烟灭，五行阵就无从让死者转生。",
        "unknown": "道长怎么解释这个矛盾——他「没有回答」，只令撤离；区间内这个问题没有下文。",
        "basis": "unverified",
        "quotes": qs("q_xqa_contradiction", "q_no_answer", "q_daozhang_leave"),
        "note": "「没有回答」是叙述写出的动作（他看向中央的青铜棺椁）；我把它登记为未解，而不是解释成默认。",
    },
    {
        "id": "K06",
        "who": "在场所有人",
        "known": "壁画把墓主人指向一位篡位称帝的道人：斩蛇、受膜拜、篡位、平定叛乱、沉迷双修、被雷劈死。",
        "unknown": "墓主人是否就是壁画里这个人——区间内全部是假设与推断（许七安的条件句、楚元缜的品级推断），没有任何确认。",
        "basis": "unverified",
        "quotes": qs("q_mural_usurp", "q_thunder_kill", "q_xqa_mural_odd"),
        "note": "壁画的叙事本身是叙述直述（画上画了什么可以当事实）；「墓主=画中人」才是未确认的推断，两者必须分开。",
    },
]

foreshadows = [
    {
        "id": "F01",
        "name": "「别乱插旗」——道长「不会有太大的危险」的笃定判断，对上区间末尾的棺中异动",
        "resolved": False,
        "unresolved": True,
        "basis": "explicit",
        "setup": {
            "text": "铺设有三处，且互相咬合：①道长给出笃定的低风险判断（衣冠冢、不会有太大的危险）；②许七安当场提醒「过于笃定的判断，往往会招来相反的后果」；③叙述紧接一句替他点明这是「插旗」。",
            "basis": "explicit",
            "quotes": qw(
                ("q_yiguanzhong", "铺设①：先立一个笃定结论——衣冠冢、不会有太大的危险。"),
                ("q_chaqi_warn", "铺设②：许七安当众给出「过于笃定会招来相反后果」的提醒。"),
                ("q_bieluan", "铺设③：叙述用「别乱插旗」把这条提醒明确成对后文的预示。"),
            ),
        },
        "payoff": {
            "text": "回收（部分）：区间末尾棺椁里传出「你来啦」，随后众人听见棺椁揭开的摩擦声——与「不会有太大的危险」相反。但原文没有写任何实际危险发生（没有人受伤、没有战斗）。",
            "basis": "explicit",
            "quotes": qw(
                ("q_nilai", "回收①：棺椁里传出人语，直接顶在「不会有太大的危险」之后。"),
                ("q_coffin_open", "回收②：身后的摩擦声被叙述命名为棺椁揭开的声音。"),
            ),
        },
        "statusNote": "标 unresolved=true 而不是 resolved：反向迹象已经出现，但「后果」没有落地，且揭开声的成因与结果都在区间之外。若复核者按「迹象出现即算回收」读，这条应改 resolved；我把两种读法的差别写在这里，不替复核者决定。",
    },
    {
        "id": "F02",
        "name": "五行阵能让人转生，与「死于天劫、灰飞烟灭」不能相容——矛盾被点出但区间内没有解答",
        "resolved": False,
        "unresolved": True,
        "basis": "explicit",
        "setup": {
            "text": "铺设是两套互相冲突的前提被先后摆在同一段里：①道长先前断言墓主死于天劫、灰飞烟灭；②钟璃给出五行阵的葬制目的——死者终有一天会从土中转生，而墓内四角与中央正好按五行布置。",
            "basis": "explicit",
            "quotes": qw(
                ("q_wuxing_belief", "铺设①：五行阵的用途被明确说出——终有一天会从土中转生。"),
                ("q_yiguanzhong", "铺设②：道长先前断言「灰飞烟灭」，两者不能同时成立。"),
            ),
        },
        "payoff": {
            "text": "提示（不是回收）：许七安当场把矛盾说出来；道长的反应是一愣、瞳孔微缩，然后要求撤出，没有回答。",
            "basis": "explicit",
            "quotes": qw(
                ("q_xqa_contradiction", "提示：矛盾被当场点出。"),
                ("q_daozhang_leave", "未回收：回答被撤出令替代，问题在区间内没有下文。"),
            ),
        },
        "statusNote": "一条被明写的、悬而未决的知识冲突。它的价值不在「猜答案」，而在它确实改变了人物的行动（终止探索）。",
    },
    {
        "id": "F03",
        "name": "许宁宴三次重返同一间偏室——楚元缜的怀疑被立起，区间内没有回收",
        "resolved": False,
        "unresolved": True,
        "basis": "inferred",
        "setup": {
            "text": "铺设是「重复」本身：同一个偏室被走到第三次，楚元缜据此认为要么是故意、要么另有原因，并称许宁宴绝非表面那么简单。",
            "basis": "inferred",
            "quotes": qw(
                ("q_chu_3times", "铺设①：反复重回同一地点这一模式，被楚元缜当作线索。"),
                ("q_chu_simple", "铺设②：他把这个模式收束成一个判断——此人绝非表面上那么简单。"),
            ),
        },
        "payoff": {
            "text": "区间内没有回收：他既没有查问，也没有得到任何新证据；本区间他唯一的动作是沉默观察。",
            "basis": "explicit",
            "quotes": qw(
                ("q_chu_gaze", "未回收：整段里他只做了观察，没有推进。"),
            ),
        },
        "statusNote": "这条的铺设强度弱于 F01/F02（「三次」是楚元缜的观察，不是叙述给出的客观计数），所以我把它标成 inferred 并显式 unresolved，而不是当成已成立的伏笔。",
    },
]

notForeshadows = [
    {
        "id": "NF01",
        "item": "东海红龙油脂蜡烛（能烧几十年不灭）",
        "why": "在本区间只出现一次：被道长嗅辨出材质、随即被点燃照明。没有「以后要用它做什么」的铺设，也没有回收，只算环境细节与照明资源。",
        "quotes": qs("q_candle_material"),
    },
    {
        "id": "NF02",
        "item": "辟毒丹",
        "why": "在本区间出现一次，而且**没有发生转交**：许七安吩咐分给后土帮，公羊宿回答「我们服用过辟毒丹了」。不能写成 transfer，也不构成伏笔。",
        "quotes": qs("q_ask_pill", "q_pill_declined"),
    },
    {
        "id": "NF03",
        "item": "四角武士的兵器（紫金锤、青铜剑）",
        "why": "在本区间各出现一次，作为干尸外观与道门痕迹的描述；没有被取用、也没有后续提及，不构成伏笔。",
        "quotes": qs("q_dry_corpse", "q_bronze_sword"),
    },
    {
        "id": "NF04",
        "item": "「你来啦」这句话本身",
        "why": "只出现一次，指向不明，既没有可辨认的铺设，也没有回收。未回收且指向不明的东西按纪律登记为未知（K02），而不是伏笔。",
        "quotes": qs("q_nilai"),
    },
]

worldSettings = [
    {
        "id": "W01",
        "kind": "place",
        "name": "偏室尽头的甬道与尽头的石门",
        "basis": "explicit",
        "placeState": "arrived",
        "placeStateNote": "有明确的进入动作：「举着火把进入甬道」；石门也被推开（「石门缓缓往后敞开」）。",
        "explain": "这条通道决定了队伍的推进方式与代价：门后没有空气（火把黯淡），必须先等一刻钟才能进——照明与呼吸成了比敌人更早出现的约束。",
        "quotes": qs("q_enter_corridor", "q_stone_door", "q_door_open"),
    },
    {
        "id": "W02",
        "kind": "place",
        "name": "主墓（墓室内部）",
        "basis": "explicit",
        "placeState": "arrived",
        "placeStateNote": "有明确的进入动作：「进入主墓后，五根火把驱散的大部分的黑暗」。",
        "explain": "尺度直接解释了行动方案：宽二十丈（60 米）而深度未知，因此病夫帮主主张先绕墙估测、而不是直取中央——这条建议随后被采纳，队伍因此才看到壁画。",
        "quotes": qs("q_enter_main", "q_width", "q_depth_unknown"),
    },
    {
        "id": "W03",
        "kind": "place",
        "name": "主墓中央的高台（含通向它的黑色通道）",
        "basis": "explicit",
        "placeState": "arrived",
        "placeStateNote": "有明确的到达动作：「他拾阶而上，踏过九十九阶，登上了高台」。",
        "explain": "高台是五行格局的实物落点（四角武士、中央棺椁），正因为到了这里、看见了布局，钟璃的五行说法与许七安的矛盾才被触发。",
        "quotes": qs("q_black_corridor", "q_climb", "q_soldiers", "q_coffin_center"),
    },
    {
        "id": "W04",
        "kind": "item",
        "name": "火把（队伍的初始照明）",
        "basis": "explicit",
        "itemStates": ["use"],
        "itemStateNote": "use：全程被手持、举高、用来照壁画、照通道。原文没有写它的获得、转交或丢失，因此只写 use。",
        "explain": "它是**会耗尽的资源**（「火把无法维持太久，终将熄灭」），这条约束直接触发了改用烛台接替照明的动作。",
        "quotes": qs("q_torch_use", "q_torch_wane"),
    },
    {
        "id": "W05",
        "kind": "item",
        "name": "通道两侧烛台上的蜡烛（东海红龙油脂）",
        "basis": "explicit",
        "itemStates": ["use"],
        "itemStateNote": "use：被点燃、被点亮以接替火把。原文没有写谁持有或转交它们（它们本来就长在墓道烛台上），所以不写 hold/transfer。",
        "explain": "「一根蜡烛，能烧几十年不灭」意味着墓内存在可持续光源，队伍才能在火把耗尽后继续深入——这是资源设定，不是装饰。",
        "quotes": qs("q_candle_material", "q_candle_light", "q_pool_watch"),
    },
    {
        "id": "W06",
        "kind": "item",
        "name": "高台士卒干尸及所持兵器",
        "basis": "explicit",
        "itemStates": ["hold"],
        "itemStateNote": "hold：干尸各自持握不同武器（紫金锤、青铜剑等），「手持各不相同的武器…屹立不倒」。原文没有写这些兵器被取下、被夺或被转交。",
        "explain": "它们是五行格局的实物证据（西主金、南北东主火水木），也构成队伍的行为约束：许七安明令「不要胡乱触碰」。",
        "quotes": qs("q_four_figures", "q_dry_corpse", "q_dont_touch"),
    },
    {
        "id": "W07",
        "kind": "rule",
        "name": "道门品阶与天劫（二品渡劫／一品陆地神仙）",
        "basis": "explicit",
        "institution": None,
        "institutionNote": "本区间没有诏/令/法，因此不写 declared；没有任何执行动作，不写 executed；也没有人误解它（众人是「颇为欣喜的记下来」），不写 misunderstood。它是金莲道长以道门身份口述的体系规则，故 institution 记 null 并写明理由。",
        "explain": "这条规则把「天雷劈死」从自然现象变成可判断项（天劫），于是能推出墓主是巅峰二品、墓是衣冠冢、危险不大；也正是它的前提（灰飞烟灭）被许七安反过来用来质疑五行阵的用途。",
        "quotes": qs("q_daomen_rank"),
    },
    {
        "id": "W08",
        "kind": "rule",
        "name": "五行阵与转生（古代葬制信仰）",
        "basis": "explicit",
        "institution": None,
        "institutionNote": "不是诏令，也不是已执行的法令，更不是某个人对规则的误解：它是钟璃口述的「古代人相信」，故 institution 记 null 并写明理由。",
        "explain": "它规定了墓内布局该怎么读（四角主金火水木、中央主土），并给出这套布局的目的（死者终有一天会从土中转生）；正因为它许诺了「转生」，才与「灰飞烟灭」冲突，直接改变了道长的行动（终止探索）。",
        "quotes": qs("q_wuxing_place", "q_center_earth", "q_wuxing_belief"),
    },
    {
        "id": "W09",
        "kind": "rule",
        "name": "预言师的自我约束：不施法、不参战",
        "basis": "explicit",
        "institution": None,
        "institutionNote": "不是诏令；这是钟璃依据「一位成熟的预言师总结出来的经验」给自己定的规矩。它在本区间体现为她的不作为，不是被谁执行，也没有人对它产生误解，故 institution 记 null。",
        "explain": "这条规矩解释了钟璃在本区间的全部行为边界：即使下墓、即使遇险，她只点头、只口述知识、只背着伤者，不动手——队伍因此实际上少了一个战力。",
        "quotes": qs("q_zhongli_rule"),
    },
    {
        "id": "W10",
        "kind": "rule",
        "name": "神觉预警（武夫对危险的预感）",
        "basis": "explicit",
        "institution": None,
        "institutionNote": "既非诏令，也无执行机构；它是武夫能力的运用方式（他「尝试着发力，但又未真正用力」来触发它），故 institution 记 null。",
        "explain": "它把「门后有没有危险」变成一次可操作的检查（静等几秒看有没有预警），并决定了开门时机：没有预警，他才请道长开门。",
        "quotes": qs("q_shenjue"),
    },
]

notWorldSettings = [
    {
        "id": "NW01",
        "candidate": "襄城",
        "why": "本区间只在公羊宿的推断里作为方位出现（「不可能在襄城附近同时出现两位」），既没有到达/驻守动作，也不约束本段任何行动——按「提及≠到达」的纪律，不写成 place。",
        "quotes": qs("q_wild_sorcerer"),
    },
    {
        "id": "NW02",
        "candidate": "东海",
        "why": "只作为蜡烛油脂的出处被提到一次（「东海红龙身上提炼出的油脂」），不构成影响行动/资源/约束的地点条目。",
        "quotes": qs("q_candle_material"),
    },
    {
        "id": "NW03",
        "candidate": "辟毒丹（作为可转交的物件）",
        "why": "本区间**没有发生转交**：许七安吩咐分丹，公羊宿当场婉拒（「我们服用过辟毒丹了」）。四态里的 transfer 不成立，hold 也没有依据（没人被写出手里有丹），故不写进 worldSettings。",
        "quotes": qs("q_ask_pill", "q_pill_declined"),
    },
    {
        "id": "NW04",
        "candidate": "青铜棺椁（作为四态物件）",
        "why": "它的变化是「揭开的声音」，不属于 hold/transfer/use/lose 任何一态；不硬塞进 item。它作为状态变化记在 S05，成因记在 K03。",
        "quotes": qs("q_coffin_center", "q_coffin_open"),
    },
    {
        "id": "NW05",
        "candidate": "壁画（作为世界设定条目）",
        "why": "壁画是本段的**信息载体**：画了什么属于叙述事实，但它不解释人物能做/不能做，四态也不适用。故不放进 worldSettings；其内容留在 tasks（T05）与 K06，不在这里扩出一个「地图/物品链」。",
        "quotes": qs("q_mural_snake", "q_mural_usurp"),
    },
    {
        "id": "NW06",
        "candidate": "元景帝",
        "why": "本区间只作为许七安与楚元缜的联想出现（「想到了元景帝」），不是本段的地点、物品或规则；不扩成条目。",
        "quotes": qs("q_yuanjing"),
    },
]

themeReadings = [
    {
        "id": "TH01",
        "perspective": "以「同一批事实在不同人眼里是不同的东西」为轴读这一章：几乎每一次「看见」都被分成两套读数——许七安自认「出尽风头、作用最大」，后土帮读成「探路打头阵，危险当盾牌」；楚元缜从许宁宴身上读出「绝非表面上那么简单」；棺中那声叹息先只落到许七安一个人头上（叙述明写其他人当时并没有惶恐）。",
        "note": "这是可选视角，不是唯一真相。同一批事实也可以读成「一群人在黑暗里各自用自己熟的那套经验做判断」——那样重点在经验差异（老盗墓贼、预言师、武夫、状元各有一套），而不在信息不对称。两种读法我都保留。",
        "support": {
            "text": "支持材料在区间内成串：①许七安的自我评价与后土帮的评价相反；②楚元缜的怀疑只有他自己知道；③棺中叹息先只有许七安听见，众人是在他转述之后才发麻。",
            "basis": "explicit",
            "quotes": qs("q_self_view", "q_shield_line", "q_chu_simple", "q_others_calm", "q_chill_all"),
        },
        "counter": {
            "text": "不利证据同样在本区间：他的推理被众人当场接受（「众人点头，接受了他的说法」），说明分歧不是全面的；后土帮对钟璃「核心人物之一」的判断说明他们能识别真实身份信息；而棺椁异动的效果对所有人同时成立（「一股凉意从众人尾椎骨窜起」）——差异在「谁先感知到」，不在「各自看到不同的事实」。",
            "basis": "explicit",
            "quotes": qs("q_accepted", "q_bfzz_core", "q_chill_all"),
        },
    },
    {
        "id": "TH02",
        "perspective": "以「权威给出的宽心判断，如何被本段自己的材料顶住」为轴读：道长用「天劫→灰飞烟灭→衣冠冢→不会有太大的危险」把风险降级，许七安当场提醒「过于笃定的判断，往往会招来相反的后果」，叙述还替他点明「别乱插旗」；区间末尾棺椁传出人语与揭开声。",
        "note": "借的是「预示—反转」这一可选视角，不是三幕结构。反例见 counter：区间内没有任何实际危险落地，把末尾读成「打脸」是一种预期读法，不是已证事实。",
        "support": {
            "text": "支持：笃定判断、提醒、叙述提示、末尾异动四件事按顺序出现在同一区间内，且都指向「判断被顶住」。",
            "basis": "explicit",
            "quotes": qs("q_yiguanzhong", "q_chaqi_warn", "q_bieluan", "q_sigh"),
        },
        "counter": {
            "text": "反例：区间内没有人受伤、没有战斗，「危险」始终只是预期；棺椁揭开声的成因与后果都在区间之外（K03）。同时道长的知识权威在别处仍然有效——众人欣喜地记下品阶，他对上古符文与五行方位的解读无人反驳。",
            "basis": "explicit",
            "quotes": qs("q_remember", "q_wuxing_place"),
        },
    },
]

textualNotes = [
    {
        "id": "TN01",
        "text": "偏移口径：本文件所有 start/end 都是相对 docs[0].text 全文的 codepoint 偏移，不是相对切片的。自检式：TEXT[1366953:1366965] == '第七十八章 你来啦'（切片以本单元标题开头），len(TEXT[1366953:1373655]) == 6702。",
        "basis": "explicit",
    },
    {
        "id": "TN02",
        "text": "引文一律照抄原文，未做现代汉语规范化。原文里的「通往位置的深处」「没有注意道的细节」以及在多处用作省略号的「........」「..........」都按原样保留；本文件不修改原文。",
        "basis": "explicit",
    },
    {
        "id": "TN03",
        "text": "切片尾部包含作者附言区（PS 与分隔线），它不是叙事内容，已单独登记在 authorRegion，未当作情节或线索使用。",
        "basis": "explicit",
    },
    {
        "id": "TN04",
        "text": "本区间没有任何战斗、没有任何人受伤；区间内被击杀的邪物发生在切片之外。因此凡涉及「打斗/伤亡」的判断都不在本区间取材。",
        "basis": "explicit",
    },
]

unknowns = [
    {
        "id": "U01",
        "text": "「墓主人是谁」在本区间没有答案：壁画叙事、五行格局、棺中人语都只是线索；「墓主=壁画里的篡位道人」是许七安的条件假设与楚元缜的推断。",
        "basis": "unverified",
        "why": "不把人物推断升格为叙述事实；也不把下一章才能揭晓的内容提前写成本区间的结论。",
    },
    {
        "id": "U02",
        "text": "棺椁里说话的是谁、那声「你来啦」是对谁说的：区间内没有任何交代。",
        "basis": "unverified",
        "why": "该句在区间内只出现一次且指向不明，登记为未知比编一个解释有价值。",
    },
    {
        "id": "U03",
        "text": "「三号」「他堂兄」的所指：楚元缜的内心话里出现，但区间内没有说明他们是谁、与许宁宴什么关系。",
        "basis": "unverified",
        "why": "本区间内无法读出来；用本区间之外的设定去补，就是拿外部知识冒充原文证据。",
    },
    {
        "id": "U04",
        "text": "「连普通成员也看出许七安的低等地位」与紧跟的「探路打头阵，危险当盾牌」之间是不是解释关系：原文没有连词，也可能只是并列的评论短句。",
        "basis": "unverified",
        "why": "我在 C02 里按解释关系连了边，理由是两句紧接且第二句正好回答了第一句的「为什么」；这是本文件最可能被判「时间相邻当因果」的一处，故在此显式登记。",
    },
    {
        "id": "U05",
        "text": "钟璃在本区间「一次法术也没施、一次战斗也没参加」：这是缺席判断，区间内没有任何一句直述她没出手。",
        "basis": "unverified",
        "why": "缺席无法用引文证明；我把 T02.result 记为 null 而不是写一个 explicit 的成功结果。",
    },
    {
        "id": "U06",
        "text": "神觉预警的触发条件与边界（要不要真的发力、预警以什么形式出现）：原文只给了「未真正用力、静默几秒、没有受到预警」这一次实例。",
        "basis": "unverified",
        "why": "单次实例不足以归纳成规则；W10 只写它在本段如何被使用，不写它的完整机制。",
    },
]

selfCritique = [
    {
        "id": "SC01",
        "text": "最可能读错的一处：把许七安的内心推理当成叙述认定。他关于「金莲道长是残魂」的那整段是内心独白（「果然」二字还说明他此前已有怀疑），关于墓主身份的也全是条件句与假设。",
        "whyStillJudged": "我仍然按 inner/derived 标注并保留原文措辞，是因为叙述从未以自己身份说「道长是残魂」或「墓主是那位道人」；把人物的确信度读成事实确立，正是本角色契约里最重的红线。",
    },
    {
        "id": "SC02",
        "text": "第二处：T02（钟璃不施法不参战）的 result 我记了 null。复核者完全可能认为「她确实没出手」应当有结论，把它读成漏读。",
        "whyStillJudged": "区间内没有任何一句写她没出手，也没有战斗可参加；缺席判断写成 explicit 就是造证据。我把理由写进 resultNote 与 U05，宁可被读成保守，也不伪造一条引文。",
    },
    {
        "id": "SC03",
        "text": "第三处：F01 的 resolved 取值。反向迹象（棺中人语、揭开声）确实已经在同一区间出现，按「迹象即回收」的读法应该记 resolved。",
        "whyStillJudged": "我记 unresolved=true，因为「不会有太大的危险」这句判断的反面没有被落实：没有人受伤、没有危险现身，揭开声的成因与后果都在区间之外。取值差别已写进 F01.statusNote，请复核者裁断。",
    },
    {
        "id": "SC04",
        "text": "附带第四处：C02 与 U04 是同一个判断的两面——「打头阵/当盾牌」到「连普通成员也看出低等地位」之间，原文用的是并列短句而非因果句。",
        "whyStillJudged": "我仍连边，是因为第二句紧随其后且内容正好解释第一句；但这条边的强度低于其余各边，我已按 derived 标注并在 U04 写明可被推翻。",
    },
]

author_region_start = TEXT.find("PS：想说些什么", START, END)
check("作者附言区可定位", author_region_start > 0, "start=%d" % author_region_start)
PS_TEXT = TEXT[author_region_start:END]

candidate = {
    "schemaVersion": 1,
    "task": "read:dafeng:L3:0307",
    "agent": "w-sanguo-0",
    "role": "READER",
    "book": "dafeng",
    "lane": 3,
    "unitIndex": 307,
    "unitHead": "第七十八章 你来啦",
    "provenanceNote": "本轮由 w-sanguo-0 独立读完切片全文（docs[0].text[1366953,1373655)）后从零写出，没有沿用任何上一轮候选（该文件此前不存在）。所有引文由本目录下的 build_0307.py 逐条在全文里定位并断言「切片内恰好出现一次」，再由 check_0307.py 重新读回候选复核一遍。",
    "semanticReview": "not-performed",
    "semanticReviewNote": "本文件只做到「引文逐字定位 + 结构分区产出 + 机器可复核」。定位正确 ≠ 语义已核验：每条断言的语义、五栏归位、explicit/inferred 的划分、placeState 与四态的取舍，都需要独立复核者对着原文判定。本文件不声称语义已核验。",
    "basisLegend": {"explicit": "原文直述", "inferred": "我的归纳", "derived": "跨段推导", "unverified": "存疑"},
    "kindLegend": {
        "narration": "叙述（含叙述者评论）",
        "dialogue": "人物说的话（不是叙述事实）",
        "inner": "人物内心独白",
        "free_indirect": "叙述转述人物理解（非叙述认定）",
    },
    "nullFieldRule": "缺哪一栏写 null，并在同名 <栏>Note 写明为什么没有依据；不写理由的 null 会被判为未标注的未知。",
    "source": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "selector": "docs[0].text",
        "range": [START, END],
        "codepoints": len(SLICE),
        "sourceHash": SOURCE_HASH,
        "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
        "sliceSha256": SLICE_SHA,
        "sliceSha256Scope": "docs[0].text[1366953:1373655] 的 sha256（附列，不覆盖 sourceHash）",
        "offsetUnit": "codepoint",
        "verificationCommand": "python3 -B -s loop/state/out/read_dafeng_L3_0307.w-sanguo-0.build/check_0307.py",
    },
    "authorRegion": {
        "range": [author_region_start, END],
        "text": PS_TEXT,
        "note": "作者附言与分隔线，不属于叙事内容；本文件的任何任务/因果/状态/伏笔都不从这里取材，也不引用它作为证据。",
    },
    "tasks": tasks,
    "causeEdges": causeEdges,
    "rejectedEdges": rejectedEdges,
    "states": states,
    "knowledgeGaps": knowledgeGaps,
    "foreshadows": foreshadows,
    "notForeshadows": notForeshadows,
    "worldSettings": worldSettings,
    "notWorldSettings": notWorldSettings,
    "themeReadings": themeReadings,
    "textualNotes": textualNotes,
    "unknowns": unknowns,
    "selfCritique": selfCritique,
}

# ------------------------------------------------------------------ 结构自检
REQUIRED_SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
check("六个必需分区齐全", all(k in candidate and isinstance(candidate[k], list) for k in REQUIRED_SECTIONS),
      ",".join(REQUIRED_SECTIONS))

# 1) 任务五栏：区间不重叠、null 必须有 Note
for t in tasks:
    used: list[tuple[int, int, str]] = []
    for col in ("objective", "obstacle", "action", "result", "cost"):
        entry = t[col]
        note = t.get(col + "Note")
        if entry is None:
            ok = isinstance(note, str) and len(note.strip()) >= 10
            check("%s.%s 为 null 且有理由" % (t["id"], col), ok, "note=%r" % (note,))
            continue
        if not isinstance(note, str) or not note.strip():
            check("%s.%s 非 null 但有 Note" % (t["id"], col), False, "Note 为空")
        keys = [q["key"] for q in entry["quotes"]]
        for q in entry["quotes"]:
            rng = (q["start"], q["end"])
            for other in used:
                if not (rng[1] <= other[0] or rng[0] >= other[1]):
                    check("%s 五栏区间不重叠" % t["id"], False,
                          "%s(%s) 与 %s(%s) 重叠" % (q["key"], col, other[2], other[1]))
            used.append((rng[0], rng[1], "%s:%s" % (col, q["key"])))
        check("%s.%s 引文非空" % (t["id"], col), len(keys) > 0, ",".join(keys))
        check("%s.%s 有 basis" % (t["id"], col), entry.get("basis") in
              ("explicit", "inferred", "derived", "unverified"), str(entry.get("basis")))

# 1b) 更严的「同一句话不得跨栏」检查：按**自然句**切分，同一句不得被两栏同时引用。
#     提示词点名的旧图谱病灶是「整条任务五栏共用一句」。只查区间不重叠挡不住
#     「一句话里各取一段」这种变体，所以这里额外做一次**句级**归属：
#     一条引文覆盖到的每个自然句都记到它所在栏，若某句同时被两栏覆盖就报出来。
import re as _re

def sentences(lo: int, hi: int) -> list[tuple[int, int]]:
    """把 [lo,hi) 按句末标点切成自然句，返回全文偏移区间。"""
    chunk = TEXT[lo:hi]
    bounds, cur = [], 0
    for m in _re.finditer(r"[。！？…”]+", chunk):
        end = m.end()
        if end > cur:
            bounds.append((lo + cur, lo + end))
            cur = end
    if cur < len(chunk):
        bounds.append((lo + cur, lo + len(chunk)))
    return [(a, b) for a, b in bounds if TEXT[a:b].strip()]

def covered_sentences(rng: tuple[int, int]) -> list[tuple[int, int]]:
    """引文区间覆盖到的全部自然句（引文可能横跨两句）。"""
    return [(a, b) for a, b in sentences(rng[0], rng[1])
            if not (b <= rng[0] or a >= rng[1])]

for t in tasks:
    by_sentence: dict[tuple[int, int], set[str]] = {}
    for col in ("objective", "obstacle", "action", "result", "cost"):
        entry = t[col]
        if entry is None:
            continue
        for q in entry["quotes"]:
            for sid in covered_sentences((q["start"], q["end"])):
                by_sentence.setdefault(sid, set()).add(col)
    for sid, cols in by_sentence.items():
        if len(cols) > 1:
            check("%s 同一句话不跨栏" % t["id"], False,
                  "句 [%d,%d) %r 被 %s 栏共用" % (sid[0], sid[1], TEXT[sid[0]:sid[1]][:26],
                                              "/".join(sorted(cols))))

# 2) 所有引文都落在切片内，且逐字成立
all_quotes = []
def walk(node):
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            all_quotes.append(node)
        for v in node.values():
            walk(v)
    elif isinstance(node, list):
        for v in node:
            walk(v)
walk(candidate)
check("引文条目数 >= 40", len(all_quotes) >= 40, "n=%d" % len(all_quotes))
bad_scope = [q["key"] for q in all_quotes if not (START <= q["start"] < q["end"] <= END)]
check("全部引文落在切片内", not bad_scope, ",".join(bad_scope))
bad_lit = [q["key"] for q in all_quotes if TEXT[q["start"]:q["end"]] != q["quote"]]
check("全部引文逐字命中", not bad_lit, ",".join(bad_lit))
bad_hash = [q["key"] for q in all_quotes if q["sourceHash"] != SOURCE_HASH]
check("全部引文 sourceHash 一致", not bad_hash, ",".join(bad_hash))

# 3) 世界设定三区分
for w in worldSettings:
    if w["kind"] == "place":
        check("W %s 有 placeState" % w["id"], w.get("placeState") in ("arrived", "mentioned"), str(w.get("placeState")))
        check("W %s 有 placeStateNote" % w["id"], bool((w.get("placeStateNote") or "").strip()), "")
    elif w["kind"] == "item":
        states_ = w.get("itemStates")
        ok = isinstance(states_, list) and states_ and all(s in ("hold", "transfer", "use", "lose") for s in states_)
        check("W %s itemStates 合法且非空" % w["id"], bool(ok), str(states_))
        check("W %s 有 itemStateNote" % w["id"], bool((w.get("itemStateNote") or "").strip()), "")
    elif w["kind"] == "rule":
        check("W %s institution 字段存在" % w["id"], "institution" in w, "")
        if w.get("institution") is None:
            check("W %s institution=null 有理由" % w["id"],
                  bool((w.get("institutionNote") or "").strip()), "")
        else:
            check("W %s institution 取值合法" % w["id"],
                  w["institution"] in ("declared", "executed", "misunderstood"), str(w["institution"]))
        check("W %s 有 explain" % w["id"], len((w.get("explain") or "").strip()) > 10, "")
    else:
        check("W %s kind 合法" % w["id"], False, str(w.get("kind")))

# 4) 主题解读最多 2 条、三件齐全
check("themeReadings <= 2", len(themeReadings) <= 2, "n=%d" % len(themeReadings))
for th in themeReadings:
    check("TH %s 三件齐全" % th["id"],
          bool(th.get("perspective")) and bool(th.get("support", {}).get("quotes")) and bool(th.get("counter", {}).get("quotes")), "")
    check("TH %s counter 非空" % th["id"], len(th["counter"]["quotes"]) > 0, "")

# 5) 伏笔必须有铺设与回收（或显式 unresolved）
for f in foreshadows:
    check("F %s 有 setup" % f["id"], bool(f.get("setup", {}).get("quotes")), "")
    check("F %s payoff/unresolved 标注一致" % f["id"],
          (bool(f.get("payoff", {}).get("quotes")) or f.get("unresolved") is True), "")

# 6) selfCritique 至少三条
check("selfCritique >= 3", len(selfCritique) >= 3, "n=%d" % len(selfCritique))
check("unknowns 非空", len(unknowns) > 0, "n=%d" % len(unknowns))

# 7) 覆盖：每个任务至少 3 栏有依据
for t in tasks:
    filled = sum(1 for c in ("objective", "obstacle", "action", "result", "cost") if t[c] is not None)
    check("%s 至少 3 栏有依据" % t["id"], filled >= 3, "filled=%d" % filled)

report = {
    "task": "read:dafeng:L3:0307",
    "source": str(DOCS.relative_to(ROOT)),
    "sourceHash": SOURCE_HASH,
    "sliceRange": [START, END],
    "sliceSha256": SLICE_SHA,
    "quoteCount": len(all_quotes),
    "uniqueQuoteKeys": len({q["key"] for q in all_quotes}),
    "taskCount": len(tasks),
    "causeEdgeCount": len(causeEdges),
    "stateCount": len(states),
    "foreshadowCount": len(foreshadows),
    "worldSettingCount": len(worldSettings),
    "themeCount": len(themeReadings),
    "checks": checks,
    "failed": errors,
}

REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")

if errors:
    print("自检失败 %d 项：" % len(errors))
    for e in errors:
        print("  -", e)
    sys.exit(1)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", "utf-8")
print("已写出 %s" % OUT.relative_to(ROOT))
print("引文 %d 条 / 任务 %d / 因果 %d / 状态 %d / 伏笔 %d / 世界设定 %d / 主题 %d" % (
    len(all_quotes), len(tasks), len(causeEdges), len(states), len(foreshadows),
    len(worldSettings), len(themeReadings)))
print("自检 %d 项全部通过" % len(checks))
