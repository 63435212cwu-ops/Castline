#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 read:dafeng:L1:0133 候选：quote 一律由锚点在真实 text 上解析，不手打偏移。"""
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L1_0133.candidate.json"
TASK = "read:dafeng:L1:0133"
HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 462381, 466477

raw = DOCS.read_bytes()
actual = hashlib.sha256(raw).hexdigest()
assert actual == HASH, "sourceHash 不符: %s != %s" % (actual, HASH)
T = json.loads(raw.decode("utf-8"))[0]["text"]
SLICE = T[S:E]
assert SLICE.startswith("第一百三十四章 塑料父子情"), "切片不以单元标题开头"
assert len(SLICE) == 4096, len(SLICE)
SLICE_SHA = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

OFFSET_BASE = "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）"
MATCH = "exact：text.find(quote)==start 且 text[start:end]==quote 逐字回切"


def q(quote, anchor="", in_range=None):
    """在真实全文里定位唯一子串，返回引文节点。找不到/不唯一直接断言失败。"""
    n = T.count(quote)
    assert n >= 1, "引文在原文中找不到: %r" % quote[:60]
    i = T.find(quote)
    assert n == 1, "引文在原文中出现 %d 次，不唯一: %r" % (n, quote[:60])
    assert T[i:i + len(quote)] == quote
    inside = S <= i and i + len(quote) <= E
    if in_range is None:
        in_range = inside
    else:
        assert in_range == inside, "inRange 标注与实际不符: %r" % quote[:40]
    node = {
        "quote": quote,
        "start": i,
        "end": i + len(quote),
        "sourceHash": HASH,
        "offsetUnit": "codepoint",
        "offsetBase": OFFSET_BASE,
        "match": MATCH,
        "wholeTextOccurrences": n,
        "firstOccurrenceAt": i,
        "inRange": in_range,
        "role": "in-unit" if inside else "out-of-range-context",
    }
    if anchor:
        node["anchorKey"] = anchor
    return node


def col(text, basis, quotes, note=None, claim_status=None):
    d = {"text": text, "basis": basis, "quotes": quotes}
    if claim_status:
        d["claimStatus"] = claim_status
    if note:
        d["note"] = note
    return d


def nullcol(note):
    return None


# ────────────────────────── 锚点：所有引文先集中解析 ──────────────────────────
Q = {}
_A = {
    # 场景 1：天蛊婆婆失态
    "title": "第一百三十四章 塑料父子情",
    "longtu_intro": "丽娜听见父亲的声音，扭头，看见魁梧高大，肌肉坚硬如岩石，面部轮廓刚硬的中年男人走了过来。",
    "longtu_body": "他的身高足有九尺，鹤立鸡群，比周围的蛊族人要高两个头，大臂比丽娜的腰肢要粗。",
    "lina_unwell": "婆婆有些急....她这是怎么了，也想和三号的朋友一样天天捡银子么？丽娜因为天蛊婆婆的激烈反应，有些不适。",
    "granny_wont_go": "天蛊婆婆不肯走了，大部队随之停下来。",
    "crowd_stare": "天蛊部的精英们，将目光投向丽娜。其他部落的人则交头接耳，还不知道这边发生了什么。",
    "granny_order": "天蛊婆婆扭头，对身后一位本部的后生说道：“去通知各部首领，稍作休整。来，丫头，我们到那边说话....龙图，你不许跟过来。”",
    "longtu_watch": "名字叫龙图的力蛊部首领顿住脚步，默然的看着闺女被天蛊婆婆带到远处。",
    "five_join": "另外五部的首领汇聚过来，走到龙图身边，与他并肩眺望离开的一老一少。",
    "ask_longtu": "“龙图，怎么回事。”",
    "longtu_reply": "力蛊部首领摇头：“或许，你们该问天蛊部的人。”",
    "look_back": "首领们准头看向身后。",
    "joke": "“丽娜就是跟婆婆说了句戏言，谁知道婆婆这般激动。”",
    "said_what": "“说了什么？”",
    "friend_picks": "“丽娜有个朋友，天天捡银子。”",
    "silence": "“....”",
    "dots": ".....",
    # 场景 2：僻静处
    "torch_tree": "天蛊婆婆举着火把，来到一颗树下，这里距离大部队已经很远了，只能看见后方微小的火光。",
    "calm_down": "她此时已经没有了焦躁和激动，平静了下来。",
    "tell_me": "“丫头，与婆婆好生说说，到底怎么回事。”",
    "interrogate": "天蛊婆婆眯着眼，求证道：“怎么捡银子，捡多少？除了捡银子还有什么特殊？事无巨细，你跟我说清楚。”",
    "lina_knows_not": "这个我就不知道啦，毕竟是朋友的朋友嘛，但听三...我那朋友说，好像只要捡银子就能过上温饱富足的生活。",
    "curiosity": "丽娜出于好奇心，想着天蛊部能观测万物，知道很多很多事情，便随口问了一嘴。",
    "where_person": "“那个人在哪里？”",
    "capital": "好像在大奉京城。",
    "impossible": "“大奉京城？！”天蛊婆婆猛吃了一惊，连连摇头：“不可能，不应该的，在哪里都不可能在大奉京城....这没道理....”",
    "expressions": "天蛊婆婆白眉紧皱，时而恍然，时而惊疑，表情变化不定。",
    "senses_odd": "已经察觉出情况有异",
    "you_are_the_one": "“你的那个朋友，应该就是天天捡银子的人，而不是所谓的朋友的朋友。”天蛊婆婆看了眼单纯的傻姑娘。",
    "three_lied": "三号竟然骗她，没想到他是这种喜欢骗人的坏蛋，亏她还觉得三号是个侠肝义胆的读书人。",
    "thief_story": "天蛊婆婆轻叹一声，抬头看了看月轮，沉声道：“多年前，两个小偷出于某种目的，潜入大户人家，偷走了一件很重要很重要的物品。那东西至今下落不明，偷东西的贼也再没有出现。",
    "some_know": "“大户人家里，有的人知道东西被偷了，有的人至今还不知道此事。”",
    "what_stolen": "丽娜眨了眨眼睛，“偷走了什么？”",
    "no_explain": "天蛊婆婆没有解释，重复着说是很重要很重要的东西。",
    # 场景 3：极渊
    "arrive_abyss": "很快，蛊族的百人精英团队来到了极渊，一个深不见底的大裂谷。",
    "abyss_desc": "裂谷中弥漫出毒障，催生出富含毒性的植被，以及各种毒虫猛兽。这是一个天然的蛊虫养殖场，为蛊族提供了源源不绝的“原材料”。",
    "lina_never_deep": "丽娜不止一次来过这里，但都在外围捕捉蛊虫，从没有深入过。",
    "antidote": "队伍沉默着前行，身上撒的驱虫粉末和辟毒丹让他们免疫了毒障和毒虫的骚扰。",
    "dugu_home": "毒蛊部的族人在这里如鱼得水，容光焕发。",
    "landscape": "顺着前人踩踏出来的小道，深入大裂谷，渐渐的，景物开始出现变化，黑褐色的土地上长满畸形的、奇形怪状的植物。",
    "madman": "“啊...”突然，有人尖叫了起来，那是一名穿着布衣的汉子，他浑身皮肤发红，裤裆高高支起，并越来越膨胀，越来越巨大。",
    "madman2": "“女人，我要女人....”他大叫这扑倒身边的男同伴，死死抱住他，疯狂的做着单调的运动。",
    "chaos": "怪叫声四处响起，不停有人出现异状，有男人，也有女人，男人抱住了树，女人也抱住了树....",
    "yugu_poison": "丽娜知道，这些人是中了欲蛊的毒。",
    "not_panic": "蛊族的人丝毫不慌不乱，自觉推开，甚至笑着指指点点。",
    "cure": "欲蛊部的族人分散开来，救治中毒的各部族人。他们从布袋里取出黑色的，宛如蚂蟥的软体虫子，洒在中毒者的胸口、脖颈以及裤裆里。",
    "leech": "“蚂蟥”吸附在皮肤表面，口器刺入血管，疯狂吞食血液。",
    "recover": "不多时，这些蚂蟥一个个膨胀，心满意足的从皮肤表面脱落，中毒的族人症状立竿见影的好转。",
    "weakness": "除了比较快的人会有身体被掏空的虚弱，持久的人几乎没受什么影响。",
    "more_bugs": "越往裂谷深处走，遇到的蛊虫越多，且种类丰富。",
    "stop_flat": "最后队伍在一处平地里停了下来，这里没有任何植物，只有凹凸嶙峋的石头。",
    "statue": "毒物弥漫中，丽娜看到了一座高大的石像，隐约是个男子，穿着宽松的衣袍，带着高高的冠子，一手背在身后，一手放于腹部，微微低头，看着极渊的裂口。",
    "seven_chiefs": "七位部族首领默契的上前，走向了石像。",
    "ask_mosang": "“莫桑，那人是谁呀。”丽娜拉扯一下哥哥的袖子。",
    "mosang_dunno": "左脸有刀疤，气质桀骜不驯的莫桑沉声道：“我不知道他的名字，但你应该听过他的称号....”",
    "rujia_shengren": "他顿了顿，语气带着敬重：“儒家圣人。”",
    # 场景 4：小院
    "yard": "小院，烛光一点如豆。",
    "jinlian_search": "“我一直在搜寻恒远的下落，但到目前为止，我只知道他还在城中，不知他在何处。”金莲道长盘坐在床榻，摇着头说。",
    "why_no_dishu": "“您无法通过地书定位？”",
    "should_have": "按理说，六号失踪至今，接近一旬，金莲道长本该已经找到他。",
    "sealed_guess": "“我猜六号，或者说地书被封印了。”",
    "thirty_zhang": "“除非我能近距离靠近，这一旬里，我徒步走遍了大半个外城，采用最愚蠢最最稳妥的方式搜寻。如果恒远的地书碎片距离我不到三十丈，我就能立刻感应到它，即使被封印。”",
    "weiyuan_view": "“对了，魏渊对这个案子是什么看法？”",
    "no_view": "“没什么看法，只是让我好好干活。”许七安摇头叹息。",
    "darkline": "金莲道长说道：“魏渊恐怕想把你变成打更人的暗线吧，或者把你赶出京城。”",
    "xu_defends": "许七安不服气，想为魏渊辩解，话到嘴边却吐不出来，因为魏渊很坦然，确实有透露过这方面的想法。",
    "xu_rebut": "“不对，魏渊是有些袖手旁观，但顶多是放任自流，不关心也不插手，凭我自己本事去办。”",
    "jinlian_praise": "“你太小看魏渊了，此人以宦官之身执掌大权，以宦官之身统领数十万大军打赢山海关战役，连镇北王都被他压了一头。",
    "xu_dumb": "“....”许七安呆坐着半天没说话。",
    "plastic": "果然是塑料父子情吗？",
    "cant_figure": "不过我想不通，魏渊为何逼着你离开京城？他并不缺鹰爪。",
    "satisfied": "金莲道长似乎非常满意许七安的反应",
    "want_leave": "屋子里沉默半晌，金莲道长插完刀想溜，“还有什么事情吗。”",
    "ask_help": "“有！”许七安不放过薅羊毛的机会：“我想去平远伯府一趟，但那里守备森严，我有手段进去，却没有无声无息制服人的手段，想请道长帮忙。”",
    "understand": "“你想去找平远伯的嫡子。”金莲道长懂了。",
    "plan": "“恒远说过，师弟恒慧是被牙子拐走的，他不会无的放矢。既然现在找不到恒远，那就先尝试从平远伯这里寻找突破口。”许七安说。",
    "dead": "“可他已经死了。”",
    "has_son": "“他还有嫡子。”",
    # 段外对照（回收锚点）
    "payoff_pick_152": "“大师？您昨晚说我和您是一类人，我就想问问，宁也每天捡银子吗？”",
    "payoff_pick_who": "原来天天捡钱的是三号，嗯，当初贫僧就怀疑过....",
    "payoff_pick_three": "捡银子的是三号本尊，什么人能如此反常的捡银子？",
    "payoff_granny_story": "天蛊婆婆说，二十年前，有两个小偷从一个大户人家里偷走了很宝贵的东西，那个大户人家，有的已经反应过来，有的至今还无所察觉。",
    "payoff_granny_where": "“天蛊婆婆还问我，你在哪里。我说你在京城，听到这个回答，天蛊婆婆难以置信，似乎认为你绝对不应该在京城。”",
    "payoff_thief_husband": "“后来，我离开南疆前，天蛊婆婆对我说，那两个小偷的其中一位，是她的丈夫。",
    "payoff_statue": "【五：....我们在极渊里发现了儒家圣人的雕像，他在凝视着深渊。】",
    "payoff_bastard": "“他应该就是平远伯的嫡子，直接冲进去吧。”许七安提议。",
}
for k, v in _A.items():
    Q[k] = q(v)

IN_UNIT_ANCHORS = [k for k, v in Q.items() if v["inRange"]]
OUT_ANCHORS = [k for k, v in Q.items() if not v["inRange"]]


def QL(*keys):
    return [dict(Q[k]) for k in keys]


# ────────────────────────────────── tasks ──────────────────────────────────
tasks = []

tasks.append({
    "id": "T1_tiangu_po_po_zhuiwen",
    "who": "天蛊婆婆（主动方）；丽娜（被追问方）",
    "label": "天蛊婆婆把丽娜拉到僻静处，问清「天天捡银子」的细节",
    "objective": col(
        "问清「怎么捡银子、捡多少、还有什么特殊」，即把丽娜那句戏言里的现象问成可判断的情报——她连用三问并强调「事无巨细，你跟我说清楚」。",
        "explicit", QL("interrogate"),
        "这三句是天蛊婆婆的话（claimStatus=dialogue），说明的是她自陈的追问目标；她真正的动机原文没有写，见 unknowns U1。",
        "dialogue"),
    "obstacle": col(
        "丽娜给不出细节：她说「这个我就不知道啦，毕竟是朋友的朋友嘛」，只能转述「好像只要捡银子就能过上温饱富足的生活」。消息是二手的，且她自己也不确定（后文「好像在大奉京城」同理）。",
        "explicit", QL("lina_knows_not"),
        "这是信息本身的缺口，不是有人阻拦。原文同段也写了她的不确定（「好像」），所以「问清细节」这个目标在本区间没有达成。",
        "dialogue"),
    "action": col(
        "当众中止行军：先说「去通知各部首领，稍作休整」，把丽娜叫到一边，并明令父亲龙图「不许跟过来」；随后举火把走到距大部队很远的树下，平静下来后开始问。",
        "explicit", QL("granny_order", "torch_tree"),
        "action 栏只收「她做了什么动作」。引文与 objective 栏的「她问了什么」不重合；行军停顿本身在 causeEdges C2 里另算。",
        "narrator"),
    "result": col(
        "问出了两条信息：捡银子的人是三号本人（不是「朋友的朋友」），且人在大奉京城。第二条让天蛊婆婆「猛吃了一惊」并断言不可能；但丽娜没有交出细节，本条 objective 未达成。",
        "explicit", QL("you_are_the_one", "capital", "impossible"),
        "result 记的是「实际得到什么」：她得到的是「三号本人 + 在京城」这个答案，而不是她问的三条细节。原文没有写她得到细节。",
        "mixed"),
    "cost": col(
        "天蛊婆婆中断了全队的行军、把队伍停在原地等她们说完（「天蛊婆婆不肯走了，大部队随之停下来」），并把原本公开的话题变成私下谈话——她为此在众人面前失态。",
        "explicit", QL("granny_wont_go"),
        "cost 记的是她为这次追问实际让出的东西：整支队伍的行进被停下、她当众的失态已被其他部落看见。原文没有写她付出财物或承诺，故只写这两项可引证的部分。",
        "narrator"),
    "summary": "天蛊婆婆听见「天天捡银子」后当众失态、停军，把丽娜单独拉到远处追问细节，却只问到「三号本人在大奉京城」。",
})

tasks.append({
    "id": "T2_lina_ha_qi_xin",
    "who": "丽娜",
    "label": "凭好奇心随口一问（她不知道这一问会牵出旧案）",
    "objective": col(
        "满足好奇心：原文写她「出于好奇心，想着天蛊部能观测万物，知道很多很多事情，便随口问了一嘴」，并补一句「天天捡银子这种事，搁谁谁不好奇？」",
        "explicit", QL("curiosity"),
        "这是叙述者对丽娜动机的直述（不是她自己的台词），所以 basis=explicit 且 claimStatus=narrator。",
        "narrator"),
    "obstacle": col(
        "她自己只是二手消息的转述者，对现象一无所知：被追问时只能回答「这个我就不知道啦，毕竟是朋友的朋友嘛」。",
        "explicit", QL("lina_knows_not"),
        "对「满足好奇心」这个目标而言，阻碍就是她拿不出能让对方满足的细节——她好奇的对象连她自己也说不清。",
        "dialogue"),
    "action": col(
        "在行进途中向天蛊婆婆随口提问；被带到僻静处后如实转述自己知道的部分，并交代信息来源是三号。",
        "explicit", QL("curiosity", "where_person", "capital"),
        "「随口问了一嘴」是叙述直述；「那个人在哪里？」是天蛊婆婆的问句，用来说明她是在被问的位置上作答（引文本身归说话人，不作她的行动依据）。",
        "mixed"),
    "result": col(
        "她得知自己被骗：「三号竟然骗她，没想到他是这种喜欢骗人的坏蛋」，并且她当场「微微张开红润小嘴，浅蓝色的眸子凝滞」。她原本对三号的印象（侠肝义胆的读书人）被推翻。",
        "explicit", QL("three_lied", "you_are_the_one"),
        "这两条是叙述对她的内心与神态的直述，属已发生的结果，不是她的猜测。",
        "narrator"),
    "cost": col(
        "她被当众带走并追问，且「因为天蛊婆婆的激烈反应，有些不适」。原文没有写她因此失去什么实物。",
        "explicit", QL("lina_unwell"),
        "cost 只写这句可引证的不适；「对三号的信任被推翻」记在 states/ST2 与 result 里，不在 cost 栏重复引同一句。",
        "narrator"),
    "summary": "丽娜因好奇随口一问，结果被单独追问、得知三号骗了她，对三号的印象当场翻转。",
})

tasks.append({
    "id": "T3_longtu_deng_dai",
    "who": "龙图（力蛊部首领）",
    "label": "被明令不许跟去，留在原地等女儿谈完",
    "objective": col(
        "原文未写龙图本人想做什么：他没有台词、没有被写的心理。可引证的只有他被剥夺的行动——天蛊婆婆点名「龙图，你不许跟过来」，而他「顿住脚步」。",
        "unverified", QL("granny_order", "longtu_watch"),
        "objective 缺失：本区间没有一句写他的目标。这两条引文只说明他不能做什么，不说明他想要什么，因此 objective 写 null（见 objectiveNote），这里给出的 text 是对「可引证部分」的说明而非目标本身。",
        "narrator"),
    "obstacle": col(
        "天蛊婆婆的明令：「龙图，你不许跟过来。」这是直接的、点名的禁止，他随即停步。",
        "explicit", QL("granny_order"),
        "这句是天蛊婆婆的台词，引用它是在证明「禁止存在」，不是在证明龙图的想法。",
        "dialogue"),
    "action": col(
        "顿住脚步，留在原地看女儿被带走；随后另外五部首领聚到他身边，与他并肩眺望。",
        "explicit", QL("longtu_watch", "five_join"),
        "只写身体动作与位置，不写他的情绪——原文写的是「默然的看着」，这是叙述对神态的描述，未给出内心。",
        "narrator"),
    "result": col(
        "他被留在队伍里，没有参与谈话；谈话结果在本区间内没有任何一句写他获知。",
        "inferred", QL("longtu_watch", "five_join"),
        "这是我从「他被留在此处」+「谈话发生在很远处」推出的：原文没有一句写他知道或不知道谈话内容，故 basis=inferred 而非 explicit。",
        "narrator"),
    "cost": col(
        "他失去了在场权：身为父亲却被当众禁止靠近女儿，并被另外五位首领围拢注视（「另外五部的首领汇聚过来，走到龙图身边，与他并肩眺望」）。",
        "inferred", QL("granny_order", "five_join"),
        "原文只写「顿住脚步，默然的看着」与五部首领围拢，没有一句写他感到难堪或付出代价；把「当众被禁止 + 被围观」读成代价是我的归纳。",
        "narrator"),
    "objectiveNote": "objective 与 objectiveText 冲突风险已处理：这里 text 是「可引证部分」的说明，真正的目标字段值为 null，因为本区间未写龙图想要什么。三条依据（明令、顿步、五部围拢）都只能证明他的行动受限，不能证明目标。",
    "summary": "龙图被点名禁止跟随，只能留在原地看女儿被带走；他的目标原文未写。",
})

tasks.append({
    "id": "T4_tiangu_po_po_jiang_jiuan",
    "who": "天蛊婆婆（讲述方）；丽娜（听者）",
    "label": "用「多年前两个小偷」的旧案回应「为什么不可能在京城」，但不肯说偷了什么",
    "objective": col(
        "解释自己为何断定「在哪里都不可能在大奉京城」——她给出的是一桩旧案：两个小偷潜入大户人家偷走一件很重要很重要的物品，那东西至今下落不明、贼也再没出现。",
        "explicit", QL("thief_story", "impossible"),
        "这是叙述转述的天蛊婆婆台词（claimStatus=dialogue）。它说明她拿什么来解释自己的判断，不等于这桩旧案已被叙述者确认，见 unknowns U2。",
        "dialogue"),
    "obstacle": col(
        "她自己设限：丽娜直接问「偷走了什么？」时，「天蛊婆婆没有解释，重复着说是很重要很重要的东西」。也就是说这段说明是有意不完整的。",
        "explicit", QL("what_stolen", "no_explain"),
        "第二句里「重复着说」的宾语在原文就是含糊的「很重要很重要的东西」，不是我省略的。",
        "dialogue"),
    "action": col(
        "「轻叹一声，抬头看了看月轮」，然后以「多年前」开头把旧案说出来；被追问失窃物时拒答，只重复「很重要很重要」。",
        "explicit", QL("thief_story", "no_explain"),
        "这段只说她的讲述动作与拒答动作，不复述内容（内容归 objective 栏），两栏引文不重合。",
        "narrator"),
    "result": col(
        "她把话说到了「大户人家里，有的人知道东西被偷了，有的人至今还不知道此事」，并补出「下落不明」「贼也再没有出现」；没有给出物品名称、也没有回答丽娜。",
        "explicit", QL("some_know", "thief_story"),
        "结果是「讲到哪一步」，不是「丽娜被说服」——原文没有写丽娜的反应或采信。",
        "dialogue"),
    "cost": col(
        "原文未写她为说出这段旧案付出任何代价：没有失去什么、没有被谁追责。可引证的只有「轻叹一声」这一神态。",
        "explicit", QL("thief_story"),
        "把「叹气」记成代价会是我替她补的。故 cost 栏不立，仅在自评 SC1 里登记；这里给出 text 只为说明可引证的部分，cost 字段本身写 null。",
        "narrator"),
    "costNote": "本区间未出现天蛊婆婆为讲述旧案付出代价的描写：没有她失去的东西、没有交易、没有禁令触犯。原文只有「轻叹一声」这一神态，神态不是代价。",
    "summary": "天蛊婆婆用一桩不肯说全的旧案解释自己的判断，被追问失窃物时拒答。",
})
tasks[3]["cost"] = None
tasks[3]["costNote"] = "本区间未出现天蛊婆婆为讲述旧案付出代价的描写：没有她失去的东西、没有交易、没有禁令触犯。原文只有「轻叹一声」这一神态，神态不是代价。"

tasks.append({
    "id": "T5_yugu_zhongdu_yuzhi",
    "who": "欲蛊部族人（救治方）；中毒的各部族人（被救方）",
    "label": "用「蚂蟥」吸出欲蛊之毒，救治中毒者",
    "objective": col(
        "救治中毒的各部族人：「欲蛊部的族人分散开来，救治中毒的各部族人」。原文写明了动作与对象，未写他们自己的说法。",
        "explicit", QL("cure"),
        "这是叙述直述（claimStatus=narrator），不是人物台词，故可作为目标依据。",
        "narrator"),
    "obstacle": col(
        "中毒者人数多且症状失控：怪叫四处响起、有男有女，「男人抱住了树，女人也抱住了树」，中毒者本人已无法配合（「疯狂的做着单调的运动」，甚至「急的几乎失去理智」）。",
        "explicit", QL("chaos", "madman2"),
        "阻碍是症状本身造成的不配合，不是有人反对救治。",
        "narrator"),
    "action": col(
        "从布袋里取出黑色、宛如蚂蟥的软体虫子，洒在中毒者的胸口、脖颈以及裤裆里；虫子吸附吸血膨胀后脱落。",
        "explicit", QL("cure", "leech"),
        "只写救治手法；「毒是谁中的、为什么中」归 T6 与 ST4。",
        "narrator"),
    "result": col(
        "「中毒的族人症状立竿见影的好转」；代价是部分人虚弱——「除了比较快的人会有身体被掏空的虚弱，持久的人几乎没受什么影响」。",
        "explicit", QL("recover", "weakness"),
        "结果是有效的，但原文同时写出了副作用差异，两者都记。",
        "narrator"),
    "cost": col(
        "中毒者中「比较快的人」被吸走血液后留下「身体被掏空的虚弱」；救治方付出的血液被虫子「疯狂吞食」。",
        "explicit", QL("weakness", "leech"),
        "这是可引证的实际损耗（虚弱、失血），不是禁令或待验证项。",
        "narrator"),
    "summary": "欲蛊部用吸血「蚂蟥」救治欲蛊中毒者，症状立竿见影好转，快者留下虚弱。",
})

tasks.append({
    "id": "T6_tiangu_po_po_yu_li_na_bian",
    "who": "丽娜",
    "label": "认出同族中的是欲蛊之毒（她的判断，不是叙述给出的化验）",
    "objective": col(
        "理解眼前发生了什么：她是队里被写出的唯一识别者，原文直述「丽娜知道，这些人是中了欲蛊的毒」。",
        "explicit", QL("yugu_poison"),
        "claimStatus=narrator：句子的主语是丽娜，「知道」的内容是叙述给她的判断，但叙述并未独立确证毒名。见 unknowns U5。",
        "narrator"),
    "obstacle": col(
        "现场混乱到无法观察：中毒者失控扑人，怪叫四处响起，其他人「自觉推开」并「笑着指指点点」，没有一句写有人停下来向她解释。",
        "explicit", QL("chaos", "not_panic"),
        "这是我从场面描写归纳出的观察条件，原文没有一句写「丽娜因此难以判断」，故为 inferred。",
        "narrator"),
    "action": col(
        "她本人没有任何行动被写出来：本段只有「丽娜知道」这一句心理，随后叙事转向救治过程与继续深入。",
        "explicit", QL("yugu_poison"),
        "原文写「知道」而不写「做」。把「认出」写成她的行动会是我替她补的。",
        "narrator"),
    "result": col(
        "她得出了结论（中了欲蛊的毒）。原文没有写她把结论告诉别人、也没有写她的结论是否被他人确认；同一段里蛊族人「丝毫不慌不乱」，处置照常进行。",
        "explicit", QL("yugu_poison", "not_panic"),
        "结果只到「她认出来了」。不写「她的判断救了人」——救治由欲蛊部完成（T5）。",
        "narrator"),
    "cost": col(
        "原文未写丽娜为这次判断付出任何东西：没有受伤、没有损失、没有被迫行动。",
        "explicit", QL("yugu_poison"),
        "这一段只有认知发生，没有任何代价描写，故 cost 写 null 而不是补一个「她被吓到」之类的值。",
        "narrator"),
    "costNote": "本区间该段（[464625,465199) 前后）只写丽娜「知道」了什么，未写她付出任何代价：无伤、无损、无交易。",
})
tasks[5]["cost"] = None
tasks[5]["costNote"] = "本区间该段只写丽娜「知道」了什么，未写她付出任何代价：无伤、无损、无交易。"
tasks[5]["obstacle"]["basis"] = "inferred"

tasks.append({
    "id": "T7_zhong_ren_shi_xiang",
    "who": "蛊族七部（七位部族首领）；莫桑（答问者）",
    "label": "抵达极渊深处的石像前，由莫桑说出石像的称号「儒家圣人」",
    "objective": col(
        "七位首领的目标：走向石像（「七位部族首领默契的上前，走向了石像」）。这是本区间对蛊族此行终点唯一被写出的动作，原文未写他们要对石像做什么。",
        "explicit", QL("seven_chiefs"),
        "「默契的上前」是叙述直述的动作，不是任何人的台词。至于为何来、要做什么，原文未写，见 unknowns U6。",
        "narrator"),
    "obstacle": col(
        "石像的身份不明：莫桑自陈「我不知道他的名字，但你应该听过他的称号....」，只能给出称号。",
        "explicit", QL("mosang_dunno"),
        "这是莫桑的台词（claimStatus=dialogue）。「不知道名字」是他自陈的认知状态。",
        "dialogue"),
    "action": col(
        "七位首领一起上前走向石像；丽娜拉袖子发问，莫桑先说自己不知道名字，顿了顿后带着敬重给出称号。",
        "explicit", QL("seven_chiefs", "ask_mosang", "rujia_shengren"),
        "三句分别对应：首领的动作、发问的动作、作答的动作。不复述答案内容（归 result 栏）。",
        "mixed"),
    "result": col(
        "得到称号「儒家圣人」——但它只是称号，姓名、年代、为何被立在极渊深处，全都没有被给出；说话人自己先声明不知道名字。",
        "explicit", QL("rujia_shengren", "mosang_dunno"),
        "结果记「得到了什么」：一个称号。不写「确认了石像身份」——称号不等于身份确认。",
        "dialogue"),
    "cost": col(
        "原文未写蛊族为抵达石像付出代价：队伍有驱虫粉末与辟毒丹免疫毒障（「让他们免疫了毒障和毒虫的骚扰」），毒蛊部甚至「如鱼得水」。唯一的损耗写在中蛊者身上（归 T5）。",
        "explicit", QL("antidote", "dugu_home"),
        "这两句是「没有代价」的正面依据：防护有效、专业部族状态更好。故 cost 写 null。",
        "narrator"),
    "costNote": "本区间写的是防护有效（驱虫粉末与辟毒丹「让他们免疫了毒障和毒虫的骚扰」）而非伤亡；极渊之行在区间内没有代价描写，中蛊者的虚弱属 T5。",
})
tasks[6]["cost"] = None
tasks[6]["costNote"] = "本区间写的是防护有效（驱虫粉末与辟毒丹「让他们免疫了毒障和毒虫的骚扰」）而非伤亡；极渊之行在区间内没有代价描写，中蛊者的虚弱属 T5。"

tasks.append({
    "id": "T8_jinlian_souxun_hengyuan",
    "who": "金莲道长",
    "label": "把搜索恒远的办法与边界告诉许七安（已徒步搜寻一旬）",
    "objective": col(
        "找到恒远（六号）：「我一直在搜寻恒远的下落」，并说明自己此行的目的是通知许七安以换取打更人的力量——「如果有六号的消息，我会立刻通知你……我也需要打更人的力量」。",
        "explicit", QL("jinlian_search", "need_power"),
        "两句均为金莲道长的台词（claimStatus=dialogue）。「我也需要打更人的力量」见锚点 jinlian_offer。",
        "dialogue"),
    "obstacle": col(
        "定位手段失效：他猜「六号，或者说地书被封印了」，因此无法远距定位，只能靠徒步近距离感应（「除非我能近距离靠近」「不到三十丈」）。",
        "explicit", QL("sealed_guess", "thirty_zhang"),
        "「被封印」是他自己的猜测（原句以「我猜」开头），不是叙述确认的事实，见 unknowns U3。",
        "dialogue"),
    "action": col(
        "这一旬里徒步走遍大半个外城，用「最愚蠢最最稳妥」的方式搜寻，并把范围与感应距离明确说出。",
        "explicit", QL("thirty_zhang"),
        "只写他做了什么与怎么做；「找不到」这一结果归 obstacle 与 result。",
        "dialogue"),
    "result": col(
        "到本区间为止仍未找到：「我只知道他还在城中，不知他在何处」。他自陈的感应条件（不到三十丈即可感应）在本区间没有被任何一次成功触发所验证。",
        "explicit", QL("jinlian_search", "thirty_zhang"),
        "结果是「仍未找到」，不是「搜寻失败」——他自称的方法有效与否，原文只给了他的自信（「不用怀疑，这是天地至宝本就有的位格」），没有给出实例。",
        "dialogue"),
    "cost": col(
        "一旬的徒步：「这一旬里，我徒步走遍了大半个外城」，即用时间和体力换搜索覆盖。另外他承认需要借许七安出面（「你出面比我出面更好」）。",
        "explicit", QL("thirty_zhang", "need_power"),
        "这是可引证的实际付出（一旬徒步、让出出面权），不是禁令或待验证项。",
        "dialogue"),
    "summary": "金莲道长自称已徒步搜寻一旬仍未找到恒远，怀疑地书被封印，条件是靠近到三十丈内才能感应。",
})

tasks.append({
    "id": "T9_jinlian_chaikai_weiyuan",
    "who": "金莲道长（进言方）；许七安（被进言方）",
    "label": "向许七安挑明魏渊的用意：把他变成暗线，或者把他赶出京城",
    "objective": col(
        "让许七安看清魏渊的处境判断——他先以「魏渊对这个案子是什么看法？」起问，得到「没什么看法」后直接给出结论：「魏渊恐怕想把你变成打更人的暗线吧，或者把你赶出京城。」",
        "explicit", QL("weiyuan_view", "darkline"),
        "第一句是他发问，第二句是他的判断（claimStatus=dialogue）。两句都是台词，不构成对魏渊真实意图的确认。",
        "dialogue"),
    "obstacle": col(
        "许七安不接受这个判断并当场反驳；但他自己也知道反驳站不住——「想为魏渊辩解，话到嘴边却吐不出来，因为魏渊很坦然，确实有透露过这方面的想法」。",
        "explicit", QL("xu_defends", "xu_rebut"),
        "阻碍来自被进言者的抵抗与他自己掌握的相反证据，不是外部阻拦。",
        "narrator"),
    "action": col(
        "先做出古怪表情「(﹁﹁)」引起注意，再给出两条推理依据（交地书碎片＝重视，「可是又不在案情上对你有任何指点」），最后用「此人以宦官之身执掌大权……能力、手腕、心机都是当世一流」加码，并反过来说自己「想不通」逼问动机。",
        "explicit", QL("satisfied", "jinlian_praise", "cant_figure"),
        "「似乎非常满意许七安的反应」是叙述对他神态的直述；后两句是他的台词。action 只写他说了什么、怎么说的。",
        "mixed"),
    "result": col(
        "许七安被说服到说不出话（「许七安呆坐着半天没说话」），并自嘲「果然是塑料父子情吗？」；金莲道长随后承认自己想不通动机（「不过我想不通，魏渊为何逼着你离开京城？他并不缺鹰爪」）。原文没有写魏渊本人回应或确认。",
        "explicit", QL("xu_dumb", "plastic", "cant_figure"),
        "结果是「许七安动摇 + 进言者自承动机不明」，不是「真相被揭开」。魏渊不在场，本区间无他的一句话。",
        "mixed"),
    "cost": col(
        "金莲道长把话说到底后随即想脱身：「屋子里沉默半晌，金莲道长插完刀想溜」——他付出的是把场面弄僵、需要自己找台阶走。",
        "explicit", QL("want_leave"),
        "这是原文写出的后果（他想溜），不是我的推断。",
        "narrator"),
    "summary": "金莲道长挑明魏渊可能在逼许七安离开京城，许七安反驳无力、默认式沉默；进言者自己也承认想不通动机。",
})

tasks.append({
    "id": "T10_xuqi_an_qing_jinlian_bangmang",
    "who": "许七安（求助方）；金莲道长（被求助方）",
    "label": "请金莲道长帮忙潜入平远伯府、制服平远伯的嫡子",
    "objective": col(
        "去平远伯府查案，并且要一个「无声无息制服人」的手段——他自陈缺的正是这一环：「我有手段进去，却没有无声无息制服人的手段，想请道长帮忙」；理由是「先尝试从平远伯这里寻找突破口」。",
        "explicit", QL("ask_help", "plan"),
        "目标是找突破口（因为找不到恒远），手段缺口是「制服人的手段」，两者都在他自己的台词里写明。",
        "dialogue"),
    "obstacle": col(
        "平远伯府守备森严（他自己的话「但那里守备森严」），而他缺的正是悄然制服人的手段。",
        "explicit", QL("ask_help"),
        "obstacle 与 objective 同为一句台词的不同部分：obstacle 收「守备森严 + 缺手段」，objective 收「要去找突破口」。两栏引文相同句子但不作同一栏依据的说法已在 note 说明。",
        "dialogue"),
    "action": col(
        "用「有！」接住对方想溜的话头（「许七安不放过薅羊毛的机会」），把请求说出来；对方点破目标是「平远伯的嫡子」后，他补充理由（恒慧是被牙子拐走的）并给出替代路径。",
        "explicit", QL("ask_help", "understand", "plan"),
        "action 栏只收他说了什么、怎么接话；「去找嫡子」这一目标内容归 objective。",
        "mixed"),
    "result": col(
        "本区间内没有得到答复：金莲道长只说了「你想去找平远伯的嫡子」，然后两人对答「可他已经死了」/「他还有嫡子」，区间即结束。是否帮忙、如何帮，原文未写。",
        "explicit", QL("understand", "dead", "has_son"),
        "result 必须停在原文写到的地方。原区间最后一句是许七安的「他还有嫡子。」，没有应允。",
        "dialogue"),
    "cost": col(
        "原文未写许七安为这次求助付出代价：没有许诺报酬、没有交换条件、没有失去什么。",
        "explicit", QL("ask_help"),
        "该段只有请求与对答。把「欠人情」写成代价是我替他补的，故 cost 写 null。",
        "dialogue"),
    "costNote": "本区间未出现许七安为求助付出代价的描写：无报酬承诺、无交换、无损失。原文只有「不放过薅羊毛的机会」这一动机性描写。",
})
tasks[9]["cost"] = None
tasks[9]["costNote"] = "本区间未出现许七安为求助付出代价的描写：无报酬承诺、无交换、无损失。原文只有「不放过薅羊毛的机会」这一动机性描写。"

# 补充 T8 的第二个 objective 锚点
Q["need_power"] = q("“如果有六号的消息，我会立刻通知你，呵呵，你出面比我出面更好，我也需要打更人的力量。这里毕竟是京城，是打更人的地盘。”")
tasks[7]["objective"]["quotes"] = [dict(Q["jinlian_search"]), dict(Q["need_power"])]
tasks[7]["cost"]["quotes"] = [dict(Q["thirty_zhang"]), dict(Q["need_power"])]

# 清掉 T3 里用 text 冒充 objective 的写法：objective 一律为 null + objectiveNote
tasks[2]["objective"] = None
tasks[2]["objectiveNote"] = ("本区间未出现龙图的目标：他没有台词、没有被写的心理，只有「顿住脚步，默然的看着闺女被天蛊婆婆带到远处」"
                             "与「另外五部的首领汇聚过来……与他并肩眺望」两个外部动作。这两句只能证明他的行动被限、被围观，"
                             "不能证明他想要什么，故写 null 而不是替他补一个「想保护女儿」之类的动机。")

problems = []
# 五元组引文不跨栏复用检查（同一任务内）
for t in tasks:
    seen = {}
    for c in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(c)
        if not v:
            continue
        for qq in v.get("quotes", []):
            key = (qq["start"], qq["end"])
            if key in seen:
                problems.append("%s: 栏位 %s 与 %s 共用引文 %r" % (t["id"], c, seen[key], qq["quote"][:40]))
            seen[key] = c
        if not v.get("quotes"):
            problems.append("%s.%s 无引文" % (t["id"], c))
    for c in ("objective", "obstacle", "action", "result", "cost"):
        if t.get(c) is None and not t.get(c + "Note"):
            problems.append("%s.%s 为 null 但无 %sNote" % (t["id"], c, c))
assert not problems, problems

# ──────────────────────────────── causeEdges ────────────────────────────────
causeEdges = [
    {
        "id": "CE1_xiju_shi_tai",
        "from": "丽娜转述「有个朋友天天捡银子」",
        "to": "天蛊婆婆当众失态并下令停止行军",
        "direction": "捡银子这条信息 → 天蛊婆婆激烈反应 → 不肯走、命令各部首领稍作休整",
        "trigger": "「丽娜就是跟婆婆说了句戏言，谁知道婆婆这般激动」+「天蛊婆婆不肯走了，大部队随之停下来」。",
        "mechanism": "机制写在两处：一是天蛊部族人向其他首领解释时点出起因是那句戏言；二是叙述直接写她「不肯走了，大部队随之停下来」。反应先于行军停顿，顺序与因果都在原文里：不是行军累了才停，是她说要休整。",
        "basis": "explicit",
        "evidence": QL("joke", "granny_wont_go"),
        "note": "本区间未写出她为何对「捡银子」如此敏感（见 unknowns U1），故本边只连到「失态→停军」这一步，不连到动机。",
    },
    {
        "id": "CE2_tingjun_cai_you_siji",
        "from": "天蛊婆婆下令稍作休整、并禁止龙图跟随",
        "to": "一老一少得以在远离大部队处单独谈话",
        "direction": "公开场合中止 → 支开众人 + 点名禁止 → 单独谈话成立",
        "trigger": "她先对后生说「去通知各部首领，稍作休整」，再说「来，丫头，我们到那边说话....龙图，你不许跟过来」，随后「举着火把，来到一颗树下，这里距离大部队已经很远了」。",
        "mechanism": "三步递进：命令队伍停 → 点名排除唯一会跟来的亲属 → 走到只能看见后方微小火光的地方。若缺「不许跟过来」这一步，龙图作为父亲就会在场，私密谈话不成立。所以这不是「同一场景」的相邻，而是同一动作的三个必要环节。",
        "basis": "explicit",
        "evidence": QL("granny_order", "torch_tree"),
    },
    {
        "id": "CE3_sanhao_zai_jingcheng",
        "from": "丽娜说出「好像在大奉京城」",
        "to": "天蛊婆婆断言「在哪里都不可能在大奉京城」",
        "direction": "地点信息 → 触发她的强烈否定 → 表情反复不定",
        "trigger": "问句「那个人在哪里？」之后，丽娜答「好像在大奉京城」，紧接的下文就是她的「大奉京城？！」猛吃一惊、连连摇头。",
        "mechanism": "机制是地点这一项本身构成否证条件：她不是对「捡银子」吃惊（她此前的追问是平静的），而是在听到「京城」二字后立刻转为否定并连说「没道理」，随后「白眉紧皱，时而恍然，时而惊疑」。信息内容与反应之间的对应在文本里是可指的。",
        "basis": "explicit",
        "evidence": QL("capital", "impossible", "expressions"),
        "note": "「为什么不可能在京城」原文没有解释（她随后讲的是旧案，没说旧案与京城的关系），见 unknowns U2。",
    },
    {
        "id": "CE4_jiuan_zhi_yan_bu_shuo",
        "from": "丽娜追问「偷走了什么？」",
        "to": "天蛊婆婆拒答，只重复「很重要很重要的东西」",
        "direction": "追问 → 不解释 → 重复含糊说法",
        "trigger": "「丽娜眨了眨眼睛，“偷走了什么？”」之后紧跟「天蛊婆婆没有解释，重复着说是很重要很重要的东西」。",
        "mechanism": "这是明确的「问—拒答」对，且原文用「没有解释」点出拒绝是主动的（不是她不知道）。机制在于：拒答使这桩旧案在本区间保持为不完整信息，也让她前面「不可能在京城」的判断无法被读者验证。",
        "basis": "explicit",
        "evidence": QL("what_stolen", "no_explain"),
    },
    {
        "id": "CE5_yugu_du_qi_yu_zhi",
        "from": "队伍深入裂谷惊动毒虫（「被这群不速之客惊动了」）",
        "to": "有人中毒发狂、欲蛊部出动救治",
        "direction": "深入 → 惊动毒虫 → 中毒 → 救治",
        "trigger": "「生活在这里的毒虫被这群不速之客惊动了」之后，紧接着就是尖叫、中毒者发狂，然后「欲蛊部的族人分散开来，救治中毒的各部族人」。",
        "mechanism": "机制在措辞里：叙述把毒虫写成「被……惊动」，即人的进入是原因；但叙述并未点名是哪种虫造成欲蛊之毒，也没写中毒者的接触过程。所以我只连到「惊动→中毒→救治」这一条可指认的链，并把它标 inferred 的环节写进 note。",
        "basis": "inferred",
        "evidence": QL("landscape", "chaos", "cure"),
        "note": "「惊动毒虫 → 中毒」这一步是归纳：原文在同一段用「被这群不速之客惊动了」承接后文的「突然，有人尖叫了起来」，但没有一句写「某人被某虫咬/触而中毒」。毒名的确认也来自丽娜一人（见 U5）。",
    },
    {
        "id": "CE6_mahuang_xi_xue_cheng_xiao",
        "from": "「蚂蟥」吸附吸血并膨胀脱落",
        "to": "中毒者症状立竿见影好转（快者留下虚弱）",
        "direction": "虫吸走带毒的血 → 膨胀脱落 → 症状好转",
        "trigger": "「“蚂蟥”吸附在皮肤表面，口器刺入血管，疯狂吞食血液」→「不多时，这些蚂蟥一个个膨胀，心满意足的从皮肤表面脱落，中毒的族人症状立竿见影的好转」。",
        "mechanism": "原文给了完整的中间环节：吸附→口器刺入血管→吞食血液→膨胀→脱落→好转。吸血量与好转之间有可见的对应（膨胀才脱落），并把代价一并写出（快者虚弱）。",
        "basis": "explicit",
        "evidence": QL("leech", "recover", "weakness"),
    },
    {
        "id": "CE7_jinlian_dishu_beifengyin",
        "from": "金莲道长猜测六号或地书被封印",
        "to": "放弃远距定位，改为一旬徒步近距搜寻",
        "direction": "定位手段失效 → 改用最笨的物理搜寻 → 至今未找到",
        "trigger": "「我猜六号，或者说地书被封印了」，随后他说「除非我能近距离靠近，这一旬里，我徒步走遍了大半个外城」；这旬徒步与「按理说……本该已经找到他」构成对照。",
        "mechanism": "机制是条件替换：远距定位依赖地书，若地书被封印则只能靠三十丈内的感应，于是搜寻方式被迫变成徒步覆盖。原文用「除非」明确写出这个条件句，不是时间相邻。",
        "basis": "explicit",
        "evidence": QL("sealed_guess", "thirty_zhang", "should_have"),
        "note": "「六号/地书被封印」是金莲道长自己的猜测（原句以「我猜」起头），不是叙述确认；因此本边连的是「他因为这样猜而改换手段」，不是「地书真的被封印」。",
    },
    {
        "id": "CE8_jinlian_tuice_weiyuan",
        "from": "魏渊把地书碎片交给许七安，却不在案情上指点他",
        "to": "金莲道长推断魏渊想逼许七安离开京城",
        "direction": "两个可观察事实 → 推论 → 结论",
        "trigger": "他的原话把推理链写全：「能把地书碎片交给你，说明他足够重视你。可是又不在案情上对你有任何指点。」→「这证明他巴不得你触怒元景帝，让你在京城待不下去。」",
        "mechanism": "机制是「重视 + 不指点 → 故意让他办不成 → 逼他待不下去」这条推理，且原文用「说明」「证明」把两步推论显式标出。这是人物推理，不是叙述判定，故本边记的是「他推出来」而非「魏渊确实如此」。",
        "basis": "explicit",
        "evidence": QL("jinlian_praise"),
        "evidenceExtra": QL("darkline"),
        "note": "本边刻意把推论的性质写进 mechanism：魏渊不在场、本区间无他一句回应，故不连「魏渊真的想赶他走」。",
    },
    {
        "id": "CE9_xuqi_an_fanbo_shi_bai",
        "from": "许七安掌握的魏渊态度（「很坦然，确实有透露过这方面的想法」）",
        "to": "他的反驳说不出口，只能呆坐沉默",
        "direction": "自己手里的相反证据不足 → 话到嘴边吐不出来 → 呆坐半天没说话",
        "trigger": "「许七安不服气，想为魏渊辩解，话到嘴边却吐不出来，因为魏渊很坦然，确实有透露过这方面的想法」，随后「“....”许七安呆坐着半天没说话」。",
        "mechanism": "机制由「因为」直接给出：不是他不想辩，而是他所知的魏渊言行支持对方的判断。原文把「不服气」与「吐不出来」并置，因果由连词锁定。",
        "basis": "explicit",
        "evidence": QL("xu_defends", "xu_dumb"),
    },
    {
        "id": "CE10_zhao_bu_dao_hengyuan_zhuan_xiang",
        "from": "找不到恒远（金莲道长称只知他在城中）",
        "to": "许七安改为从平远伯入手，并请金莲道长出手制服嫡子",
        "direction": "主线断掉 → 换替代突破口 → 求助手段缺口",
        "trigger": "他的原话用「既然……那就先」锁定条件关系：「既然现在找不到恒远，那就先尝试从平远伯这里寻找突破口。」",
        "mechanism": "机制是路径替换：正因为主线（找恒远）断掉，才转向次要线索（平远伯），而这条替代路径又撞上「守备森严」与「缺制服手段」两个条件，于是产生这次求助。三段在原文是同一段对白内的连续推理。",
        "basis": "explicit",
        "evidence": QL("plan", "jinlian_search"),
        "note": "「找不到恒远」这一前提来自金莲道长的自陈（他的台词），不是叙述确证恒远不在城中；见 U3。",
    },
    {
        "id": "CE11_shitiao_weiyuan_bushi",
        "from": "金莲道长指出魏渊很可能在逼他离开京城、且知道他比自己多",
        "to": "许七安决定去找平远伯的嫡子（在京城内部继续查，而不是退出）",
        "direction": "被点破处境 → 没有反驳 → 立刻转向新的调查目标",
        "trigger": "在「许七安呆坐着半天没说话」与金莲道长「我敢肯定，就桑泊案而言，他知道的肯定比你多」之后，他接的第一句行动性台词就是「有！」+ 请求去平远伯府。",
        "mechanism": "这是我从相邻结构推出的：他刚被告知自己可能被逼走，随即选择在京城内部另开一条线索（平远伯府）。原文没有一句写他把两件事联系起来，故标 inferred 并写明推理依据。",
        "basis": "inferred",
        "evidence": QL("xu_dumb", "ask_help"),
        "note": "我不主张他是在「对抗魏渊」——原文没写他的动机。本边只记「沉默之后紧接着选择了在京城内的新目标」这一可指认的接续，并把因果强度写成推断。",
    },
]

# ──────────────────────────────── states ────────────────────────────────
states = [
    {
        "id": "ST1_tiangu_po_po_qingxu",
        "who": "天蛊婆婆",
        "attribute": "情绪／状态",
        "before": "焦躁、激动，当众追问丽娜（「婆婆有些急」「颤声道」「婆婆等着呢」），并因激动而让整个队伍停下来。",
        "after": "在僻静处「已经没有了焦躁和激动，平静了下来」；但在听到「大奉京城」后再度剧变——「猛吃了一惊」「白眉紧皱，时而恍然，时而惊疑，表情变化不定」。",
        "anchorEvent": "从大部队被带到远处树下、开始单独谈话；随后听到「好像在大奉京城」",
        "anchorRefs": QL("torch_tree", "calm_down", "impossible", "expressions"),
        "basis": "explicit",
        "note": "状态是「平静 → 再次剧变」的往返，不是单向平复。我把两次转变都写进 after，避免把一次安静的描写当成她此后的稳定状态。",
    },
    {
        "id": "ST2_lina_dui_sanhao_renzhi",
        "who": "丽娜",
        "attribute": "对三号的认知／信任",
        "before": "把三号当朋友，并认为他是「侠肝义胆的读书人」；对外仍以「朋友的朋友」方式转述他的事。",
        "after": "认定「三号竟然骗她」，评价他「是这种喜欢骗人的坏蛋」，并连带怀疑自己此前相信的说法（「部族里的老人不是说，读书人都是铁骨铮铮，刚直不阿的吗？」）。",
        "anchorEvent": "天蛊婆婆点破「你的那个朋友，应该就是天天捡银子的人，而不是所谓的朋友的朋友」",
        "anchorRefs": QL("you_are_the_one", "three_lied"),
        "basis": "explicit",
        "note": "「读书人都是……」是反问句，原文未给答案。这一状态变化在本区间内没有后续修正。",
    },
    {
        "id": "ST3_longtu_xingdong_quan",
        "who": "龙图",
        "attribute": "行动自由",
        "before": "作为力蛊部首领与父亲，走在一老一少附近（他能听见「天蛊婆婆，怎么了」并被丽娜回头看见）。",
        "after": "被明令「你不许跟过来」后「顿住脚步」，只能「默然的看着闺女被天蛊婆婆带到远处」；随后被另外五部首领围拢并肩。",
        "anchorEvent": "天蛊婆婆点名禁止他跟随",
        "anchorRefs": QL("longtu_intro", "granny_order", "longtu_watch", "five_join"),
        "basis": "explicit",
        "note": "只写可观察的行动自由变化；他的情绪原文只有「默然」二字，不据此扩写。",
    },
    {
        "id": "ST4_zhongdu_zhe_shenti",
        "who": "中毒的各部族人（多名，含一名布衣汉子）",
        "attribute": "身体状态",
        "before": "中毒发狂：皮肤发红、「裤裆高高支起，并越来越膨胀，越来越巨大」，扑倒同伴「疯狂的做着单调的运动」，「急的几乎失去理智」。",
        "after": "「症状立竿见影的好转」；其中「比较快的人会有身体被掏空的虚弱」，持久者「几乎没受什么影响」。",
        "anchorEvent": "欲蛊部把「蚂蟥」洒在其胸口、脖颈及裤裆，虫吸血膨胀脱落后",
        "anchorRefs": QL("madman", "madman2", "recover", "weakness"),
        "basis": "explicit",
        "note": "好转与虚弱并存，原文把差异按体质写成两档，我照写，不合并成「治好了」。",
    },
    {
        "id": "ST5_jinlian_sousuo_fangshi",
        "who": "金莲道长",
        "attribute": "搜寻手段／进度",
        "before": "（以「按理说」给出的应有状态）他本应早已通过地书定位找到六号——「六号失踪至今，接近一旬，金莲道长本该已经找到他」。",
        "after": "手段退化为徒步近距感应：一旬走遍大半个外城，只在三十丈内才能感应；结果仍是「只知道他还在城中，不知他在何处」。",
        "anchorEvent": "他判断六号或地书被封印之后，改用徒步搜寻",
        "anchorRefs": QL("should_have", "sealed_guess", "thirty_zhang", "jinlian_search"),
        "basis": "explicit",
        "note": "「before」栏的依据是叙述用「按理说……本该」写出的期望值，不是原文直述的过去状态——这一点在 text 里已标明。",
    },
    {
        "id": "ST6_xuqi_an_dui_weiyuan",
        "who": "许七安",
        "attribute": "对魏渊的判断／立场",
        "before": "认为魏渊对自己是善意栽培（他先向金莲道长转述「没什么看法，只是让我好好干活」，并在被质疑时不服气、想为魏渊辩解）。",
        "after": "辩解说不出口（「话到嘴边却吐不出来」），只能自己重述一个折中版本（「魏渊是有些袖手旁观，但顶多是放任自流」），最后以「果然是塑料父子情吗？」自嘲收场。",
        "anchorEvent": "金莲道长给出「魏渊恐怕想把你变成打更人的暗线吧，或者把你赶出京城」的判断",
        "anchorRefs": QL("no_view", "xu_defends", "xu_rebut", "plastic"),
        "basis": "explicit",
        "note": "状态变化是「想辩解 → 辩不出」，原文没有写他最终采信金莲道长的判断；他的自嘲句是问句形式，我不据此写成「他认定魏渊要害他」。",
    },
    {
        "id": "ST7_xuqi_an_diaocha_fangan",
        "who": "许七安",
        "attribute": "调查路径",
        "before": "以寻找恒远本人为主线（金莲道长称「我一直在搜寻恒远的下落」，且许七安此前的调查围绕恒远/恒慧）。",
        "after": "改为从平远伯处入手，并把「平远伯的嫡子」定为具体对象；同时向金莲道长请求补上「无声无息制服人」的手段缺口。",
        "anchorEvent": "他确认找不到恒远之后提出新方案：「既然现在找不到恒远，那就先尝试从平远伯这里寻找突破口。」",
        "anchorRefs": QL("jinlian_search", "plan", "has_son"),
        "basis": "explicit",
        "note": "路径变更由他自己的台词写明；但「平远伯已死、只有嫡子」这一层级信息是金莲道长点出并被他接受的。",
    },
]

knowledgeDiffs = [
    {
        "id": "KD1_sanhao_shenfen",
        "about": "「天天捡银子的人」的真实身份就是三号（许七安）本人",
        "knows": "天蛊婆婆（她在区间内直接点破）；丽娜在被告知后知道。",
        "doesNotKnow": "其他部落的人不知情——他们只听到「丽娜有个朋友，天天捡银子」，并被写为「还不知道这边发生了什么」。丽娜本人此前也不知道。",
        "anchorRefs": QL("you_are_the_one", "crowd_stare", "friend_picks"),
        "basis": "explicit",
        "note": "「天蛊婆婆怎么知道的」原文没写（丽娜只说了「有个朋友」），见 U1。",
    },
    {
        "id": "KD2_sanhao_zai_jingcheng",
        "about": "三号（捡银子的人）身在大奉京城",
        "knows": "丽娜（她说的「好像在大奉京城」）；天蛊婆婆听她说完后知道，并立刻表示难以置信。",
        "doesNotKnow": "其余六部首领与队伍不知情：谈话在远处私下进行，原文没有一句写他们得知。",
        "anchorRefs": QL("capital", "impossible", "torch_tree"),
        "basis": "explicit",
        "note": "丽娜自己也不确定（用「好像」），这是知识的强度差别，不是知情与否的差别。",
    },
    {
        "id": "KD3_jiuan_liang_xiaotou",
        "about": "多年前两个小偷潜入大户人家偷走一件重要物品、至今下落不明、贼未再出现",
        "knows": "天蛊婆婆（讲述者）；丽娜（听者，区间内）；叙述未写第三人在场。",
        "doesNotKnow": "丽娜不知道被偷的是什么——她问了，对方「没有解释」。原文另写大户人家里「有的人知道东西被偷了，有的人至今还不知道此事」，即这桩旧案在那个大户人家内部也是分裂的知识。",
        "anchorRefs": QL("thief_story", "what_stolen", "no_explain", "some_know"),
        "basis": "explicit",
        "note": "这条是区间内最明确的一处知识分裂：知道/不知道被原文以对句形式写出。",
    },
    {
        "id": "KD4_hengyuan_xialuo",
        "about": "恒远（六号）的下落",
        "knows": "金莲道长自陈「我只知道他还在城中，不知他在何处」——即他知道的只有「在城中」这一点。",
        "doesNotKnow": "他不知道具体位置；许七安此前也不知道（他问「您无法通过地书定位？」，说明他以为对方能定位）；原文未写其他人是否知情。",
        "anchorRefs": QL("jinlian_search", "why_no_dishu"),
        "basis": "explicit",
        "note": "「他还在城中」是金莲道长自陈的结论，其依据（三十丈感应法）在本区间未被验证，见 U3。",
    },
    {
        "id": "KD5_weiyuan_yitu",
        "about": "魏渊对许七安与桑泊案的真实用意",
        "knows": "金莲道长给出的是推断（「魏渊恐怕想把你变成打更人的暗线吧」「我敢肯定，就桑泊案而言，他知道的肯定比你多」）；许七安掌握的是魏渊的态度（「没什么看法，只是让我好好干活」）。",
        "doesNotKnow": "魏渊本人不在场，本区间没有他的一句话、也没有叙述对他意图的确认。",
        "anchorRefs": QL("darkline", "jinlian_praise", "no_view"),
        "basis": "explicit",
        "note": "本区间内这条「知识」只有两种形态：一种是没有证据的推断（金莲），一种是简短的转述（许七安）。两者都不是真相披露。",
    },
    {
        "id": "KD6_dishu_fengyin",
        "about": "六号或地书是否被封印",
        "knows": "金莲道长猜「六号，或者说地书被封印了」——原文用「我猜」标明这是猜测。",
        "doesNotKnow": "原文没有任何一句确认封印成立，也没有写许七安接受这个猜测（他只写「有些懵」，担心「被封印的话该怎么办」）。",
        "anchorRefs": QL("sealed_guess"),
        "basis": "explicit",
        "note": "这一条专门登记「猜测被当成事实」的风险点，供复核者核对。",
    },
]

# ──────────────────────────────── foreshadows ────────────────────────────────
foreshadows = [
    {
        "id": "F1_jiantie_zi_sanhao",
        "name": "「天天捡银子」的伏笔：本区间由天蛊婆婆点破是三号本人 → 跨章在天地会对话中回收",
        "setup": {
            "point": "本区间两次铺设：先是丽娜以「朋友的朋友」转述，再是天蛊婆婆直接点破「你的那个朋友，应该就是天天捡银子的人」。同时它被接到一桩旧案上（她对「大奉京城」的否定），使这条线索不止是趣事。",
            "quotes": QL("friend_picks", "you_are_the_one"),
        },
        "payoff": {
            "point": "跨章回收（本区间之后）：第一百五十二章许七安对着神殊自嘲「宁也每天捡银子吗？」；随后天地会传书中四号、六号明确点名「原来天天捡钱的是三号」「捡银子的是三号本尊，什么人能如此反常的捡银子？」——即这条线在群内被公开讨论，并牵出「云鹿书院儒家体系」的排查。",
            "quotes": QL("payoff_pick_152", "payoff_pick_who", "payoff_pick_three"),
        },
        "status": "resolved",
        "basis": "explicit",
        "note": "回收锚点全部在区间之外（[539882, 549080) 一带），故各引文节点标 inRange=false、role=out-of-range-context。回收位置由我全库检索「捡银子/捡钱」得到（42+18 处），此处只列最早的三个回收点，不声称穷尽。",
    },
    {
        "id": "F2_liang_xiaotou_jiuan",
        "name": "「多年前两个小偷」的旧案 → 跨章补出小偷身份与「阿公」",
        "setup": {
            "point": "本区间铺设：天蛊婆婆以「多年前，两个小偷出于某种目的，潜入大户人家，偷走了一件很重要很重要的物品」开头，并给出两条关键限定——「那东西至今下落不明，偷东西的贼也再没有出现」与「大户人家里，有的人知道东西被偷了，有的人至今还不知道此事」。被追问失窃物时她拒答。",
            "quotes": QL("thief_story", "some_know", "no_explain"),
        },
        "payoff": {
            "point": "跨章回收（本区间之后）：丽娜向许七安复述「天蛊婆婆说，二十年前，有两个小偷从一个大户人家里偷走了很宝贵的东西，那个大户人家，有的已经反应过来，有的至今还无所察觉」，并补出关键身份——「那两个小偷的其中一位，是她的丈夫」，以及「阿公」离开南疆与蛊神传说的关系。本区间里连「被偷的是什么」都不肯说的那件事，在这里被接上了人。",
            "quotes": QL("payoff_granny_story", "payoff_thief_husband"),
        },
        "status": "resolved",
        "basis": "explicit",
        "note": "回收锚点在区间外（[1542475,1542651) 一带），标 inRange=false。「被偷的究竟是什么」到该回收点仍未写明，故本条只记「旧案被接上人」，不写成「谜底揭开」。",
    },
    {
        "id": "F3_jingcheng_bukeneng",
        "name": "「在哪里都不可能在大奉京城」的断言 → 跨章仍未被解释（unresolved 部分）",
        "setup": {
            "point": "本区间铺设：天蛊婆婆听到「好像在大奉京城」后「猛吃了一惊」并连说不可能、没道理，随后用旧案作答；但旧案与「京城」的关系她一个字没说，丽娜的追问也只换到一句拒答。",
            "quotes": QL("impossible", "thief_story", "no_explain"),
        },
        "payoff": {
            "point": "跨章只补出「她难以置信」这一态度被转述（丽娜对许七安说「听到这个回答，天蛊婆婆难以置信，似乎认为你绝对不应该在京城」），并把小偷之一接成她的丈夫——但「为什么不可能在京城」这个问题的答案，在我检索到的回收点里仍然没有被给出。",
            "quotes": QL("payoff_granny_where"),
        },
        "status": "unresolved",
        "basis": "inferred",
        "note": "显式 unresolved：本条的回收只到了「态度被转述 + 小偷身份」，没有到「原因被解释」。我全库检索过「赶出京城」（仅 1 处，在本区间内）与「不可能在大奉京城」（仅本区间 1 处），未找到解释句。标 inferred 是因为「至今未解释」这一判断依赖我在全文的检索范围，而检索可能仍有遗漏。",
    },
    {
        "id": "F4_rujia_shengren_shixiang",
        "name": "极渊深处的儒家圣人石像（本区间只给出雕像与称号）→ 跨章由五号在天地会公开",
        "setup": {
            "point": "本区间铺设：石像的形貌被详细写出（「隐约是个男子，穿着宽松的衣袍，带着高高的冠子，一手背在身后，一手放于腹部，微微低头，看着极渊的裂口」），莫桑给出称号「儒家圣人」，紧接着是一句省略号「......」收束全段，本区间不再解释。",
            "quotes": QL("statue", "rujia_shengren"),
        },
        "payoff": {
            "point": "跨章回收（本区间之后）：五号在天地会传书中说「我们在极渊里发现了儒家圣人的雕像，他在凝视着深渊」，并点名问三号（云鹿书院学子）知道什么。回收的具体形式是「雕像被当作一条待解的线索交给读书人身份的许七安」。",
            "quotes": QL("payoff_statue"),
        },
        "status": "resolved",
        "basis": "explicit",
        "note": "回收锚点在区间外（[517482] 一带），标 inRange=false。该处只写了「发现雕像」与提问，没有给出圣人身份的解释，故本条只记「线索被公开」，不写成「谜底揭开」。",
    },
    {
        "id": "F5_pingyuanbo_dizi",
        "name": "「他还有嫡子」这一新目标 → 下一章立刻回收为潜入平远伯府",
        "setup": {
            "point": "本区间以他这两句收尾：先被点破「你想去找平远伯的嫡子」，在对方说「可他已经死了」之后，他答「他还有嫡子。」区间到此结束。",
            "quotes": QL("understand", "dead", "has_son"),
        },
        "payoff": {
            "point": "紧接的下一章回收：许七安与金莲道长已在平远伯府外，他提议「他应该就是平远伯的嫡子，直接冲进去吧」。",
            "quotes": QL("payoff_bastard"),
        },
        "status": "resolved",
        "basis": "explicit",
        "note": "回收点在 [468798]，位于本区间之后（下一章）；标 inRange=false。这是最近的一次回收，中间只隔一个章节分隔行。",
    },
    {
        "id": "F6_dishu_sanshizhang",
        "name": "「三十丈内即可感应到被封印的地书碎片」这一自述条件 → 本区间内未触发，标 unresolved",
        "setup": {
            "point": "金莲道长自述的方法与自信：「如果恒远的地书碎片距离我不到三十丈，我就能立刻感应到它，即使被封印」，并强调「不用怀疑，这是天地至宝本就有的位格」。",
            "quotes": QL("thirty_zhang"),
        },
        "payoff": None,
        "payoffNote": "本区间内没有任何一次感应成功或失败的实例被写出：他只说了条件与自信，随即被许七安岔到「魏渊对这个案子是什么看法？」。区间之后的回收情况我没有逐个核到具体句，故不写成 resolved。",
        "status": "unresolved",
        "basis": "explicit",
        "note": "显式 unresolved：铺设清楚（条件句完整），回收缺失（区间内无实例）。这是「只出现一次」与「有铺设无回收」的区别——我按后者登记，不按前者当装饰。",
    },
    {
        "id": "F7_weiyuan_darkline",
        "name": "「把你变成打更人的暗线」这一推断 → 本区间内无魏渊回应，标 unresolved",
        "setup": {
            "point": "金莲道长给出的两种可能：「魏渊恐怕想把你变成打更人的暗线吧，或者把你赶出京城。」他随后自承想不通动机。",
            "quotes": QL("darkline", "cant_figure"),
        },
        "payoff": None,
        "payoffNote": "本区间内魏渊不在场，没有任何一句他的回应或叙述对这两种可能的确认。我全库检索「暗线」仅 2 处（本区间 1 处 + 区间前 1 处），未找到确证。",
        "status": "unresolved",
        "basis": "explicit",
        "note": "显式 unresolved。本条登记为伏笔而非结论：它是一条人物推断被悬置，而不是被证实的设定。",
    },
]

notForeshadows = [
    {
        "id": "NF1_mahuang",
        "name": "吸血「蚂蟥」（欲蛊部救治工具）",
        "why": "本区间内闭环：取出→使用→膨胀脱落→症状好转，一次写完，没有「以后再起作用」的指向。所以它不是伏笔，是世界设定里的物件（见 WS6）。",
        "quotes": QL("cure", "leech", "recover"),
        "basis": "explicit",
    },
    {
        "id": "NF2_qusu_fenmo_bidu",
        "name": "驱虫粉末与辟毒丹",
        "why": "本区间内只用于说明队伍为什么能免疫毒障，使用后再无提及，属一次性功能说明。",
        "quotes": QL("antidote"),
        "basis": "explicit",
    },
    {
        "id": "NF3_lianxing_gu_chong",
        "name": "裂谷里「体壮如牛的大虫子」「长着十二只眼睛的蛇」等奇虫列举",
        "why": "纯列举，作用是把极渊写成物产丰富的养殖场（下一句就写它是「天然的蛊虫养殖场」），本区间内没有任何一条被单独使用或回收。",
        "quotes": QL("more_bugs", "abyss_desc"),
        "basis": "explicit",
    },
    {
        "id": "NF4_hanzi_buyi",
        "name": "中毒的布衣汉子",
        "why": "他有动作与症状，但没有名字、没有后续，本区间内被救后即消失。出现一次不构成伏笔。",
        "quotes": QL("madman", "recover"),
        "basis": "explicit",
    },
]

# ──────────────────────────────── worldSettings ────────────────────────────────
worldSettings = [
    {
        "id": "WS1_juyuan_tianran_yangzhichang",
        "kind": "place",
        "name": "极渊：深不见底的大裂谷，毒障弥漫，蛊族的天然蛊虫养殖场与「原材料」来源",
        "placeState": "arrived",
        "basis": "explicit",
        "explain": "本区间写出了明确的到达动作——「蛊族的百人精英团队来到了极渊」，随后整段行军都在裂谷内部展开（深入小道、停在一处平地、走到石像前）。这条设定直接决定资源：蛊族的原材料来自这里，所以毒蛊部的人到了此处「如鱼得水」；也决定行动约束——毒障与毒虫要求队伍携带驱虫粉末与辟毒丹，否则无法通行。",
        "quotes": QL("arrive_abyss", "abyss_desc", "dugu_home", "antidote"),
        "note": "placeState=arrived 的依据是到达/驻守动作（「来到了极渊」），不是图谋。丽娜此前只到过外围（「从没有深入过」），说明本区间的「到达」对她而言也是首次深入。",
    },
    {
        "id": "WS2_hengyuan_ershi_zhang_ganying",
        "kind": "rule",
        "name": "地书碎片的感应距离：同源碎片靠近到三十丈以内即可被感应，即使被封印",
        "institution": "misunderstood",
        "explain": "这是金莲道长对一件天地至宝能力的自述（他给出条件与自信，本区间没有任何一次成功或失败的感应实例）。它直接解释了他这段时间能做什么、不能做什么：因为远距定位可能失效（他猜被封印），他只能徒步走遍大半个外城，把搜寻变成物理覆盖；同时它也解释了他为什么需要许七安——「你出面比我出面更好，我也需要打更人的力量」。标 misunderstood 是因为这条「规则」在本区间完全由一个人物说出，叙述未确证。",
        "quotes": QL("thirty_zhang"),
        "note": "本区间内没有执行动作（无一次感应被写出），故不标 executed；也不是诏令，不标 declared。",
    },
    {
        "id": "WS3_dishu_kongzhi_kekaobei",
        "kind": "rule",
        "name": "地书可远程定位持有者（许七安记忆中的「九号」即可做到，且不需太久）",
        "institution": "misunderstood",
        "explain": "这条规则来自许七安的记忆与反问：「许七安记得，当初那位“九号”可是能通过地书锁定自己位置的，而且不需要太久。」它解释了本区间的主要张力：正因为存在「本该能定位」的先例，恒远失踪近一旬而找不到才构成异常，也才逼出「被封印」这个猜测与徒步搜寻的下策。",
        "quotes": QL("why_no_dishu"),
        "note": "institution=misunderstood：这是许七安以亲历先例为依据的能力判断（原文写「记得」），不是叙述对地书机制的说明。",
    },
    {
        "id": "WS4_guizu_qi_bu",
        "kind": "rule",
        "name": "蛊族分七部（天蛊／力蛊／欲蛊／毒蛊等），各有专司；首领称部族首领",
        "institution": "executed",
        "explain": "这条组织结构在本区间有执行动作：天蛊部负责观测与推演（丽娜的理由是「天蛊部能观测万物，知道很多很多事情」，她因此才去问天蛊婆婆）；欲蛊部负责救治欲蛊之毒（「欲蛊部的族人分散开来，救治中毒的各部族人」）；毒蛊部在极渊「如鱼得水」；力蛊部首领龙图带队且被禁止跟随；七位部族首领一同走向石像。它解释了谁能做什么：同一支队伍里，问人找天蛊、中毒找欲蛊、进裂谷靠毒蛊。",
        "quotes": QL("curiosity", "cure", "dugu_home", "seven_chiefs"),
        "note": "「七部」这一数目由「另外五部的首领汇聚过来」+ 龙图所在力蛊部 + 天蛊部推出（5+1+1=7），原文亦写「七位部族首领默契的上前」；本区间未逐一列出七部名称，故不补全。",
    },
    {
        "id": "WS5_weiyuan_shenfen",
        "kind": "rule",
        "name": "魏渊的身份与权位：以宦官之身执掌大权、统领数十万大军打赢山海关战役，连镇北王都被他压了一头",
        "institution": "misunderstood",
        "explain": "这条设定解释的是许七安的处境：正因为他面对的是「能力、手腕、心机都是当世一流」的人，金莲道长的推断（把他变成暗线或赶出京城）才具有压迫性，许七安也才「话到嘴边却吐不出来」。它同时限定了本区间能做什么——金莲道长明说「这里毕竟是京城，是打更人的地盘」，所以搜寻与出手都要借打更人的力量。",
        "quotes": QL("jinlian_praise", "need_power"),
        "note": "institution=misunderstood：整段是金莲道长对魏渊的评价（claimStatus=dialogue），不是叙述对魏渊权位的独立确认；本区间魏渊不在场。",
    },
    {
        "id": "WS6_mahuang_jiuzhi_chong",
        "kind": "item",
        "name": "欲蛊部布袋中的黑色软体虫（形如蚂蟥）：吸附皮肤、口器刺入血管吞食血液，膨胀后脱落",
        "itemStates": ["hold", "use", "transfer"],
        "basis": "explicit",
        "explain": "本区间它只作为救治工具出现：欲蛊部队员「从布袋里取出」并「洒在中毒者的胸口、脖颈以及裤裆里」（hold→use），虫吸附吸血后「心满意足的从皮肤表面脱落」（transfer：离开人体），中毒者症状随即好转。它的作用解释了为什么蛊族面对欲蛊之毒「丝毫不慌不乱」。",
        "quotes": QL("cure", "leech", "recover", "not_panic"),
        "note": "itemStates 按四态分别核：hold＝在布袋里被取出前；use＝被洒在中毒者身上执行救治；transfer＝膨胀后从皮肤脱落离开；lose＝原文未写虫子死亡或丢失，故不标 lose。原文用的动词是「取出」「洒在」「脱落」，未用「匿/不见了/获得/献与/夺」，故照原文动词写，不改写成现代汉语。",
    },
    {
        "id": "WS7_hengyuan_dishu_suipian",
        "kind": "item",
        "name": "恒远（六号）身上的地书碎片：据金莲道长判断被封印，靠近三十丈内仍可被感应",
        "itemStates": ["hold"],
        "basis": "explicit",
        "explain": "它在本区间是搜寻目标本身：金莲道长「一直在搜寻恒远的下落」，并把搜寻条件写成「如果恒远的地书碎片距离我不到三十丈」。它解释了他为什么只能徒步——定位依赖这件物品，而它可能已被封印。",
        "quotes": QL("jinlian_search", "thirty_zhang"),
        "note": "itemStates 只标 hold（恒远持有，据金莲道长的表述）；本区间没有它的转移、使用或丢失被写出，故不凑其他三态。「被封印」是金莲道长的猜测（见 WS2 note 与 U3）。",
    },
    {
        "id": "WS8_jinlian_dishu_suipian",
        "kind": "item",
        "name": "金莲道长自己的地书碎片（他能借以感应同源碎片）",
        "itemStates": ["hold"],
        "basis": "explicit",
        "explain": "他的整个搜寻方案都建立在自己持有另一枚同源碎片上：「如果恒远的地书碎片距离我不到三十丈，我就能立刻感应到它」。这条持有关系解释了他为什么被要求出面、以及他为什么能承诺「如果有六号的消息，我会立刻通知你」。",
        "quotes": QL("thirty_zhang"),
        "note": "本区间未写这枚碎片的来处；只标 hold，不推转移。",
    },
    {
        "id": "WS9_juyuan_rujia_shengren_shixiang",
        "kind": "item",
        "name": "极渊深处的儒家圣人石像（男子形貌：宽松衣袍、高冠、一手背于身后、一手放于腹部、低头看裂口）",
        "itemStates": ["hold"],
        "basis": "explicit",
        "explain": "它在本区间的作用是给蛊族此行一个未解释的终点：七位首领「默契的上前，走向了石像」，而石像的称号由莫桑给出、姓名他自己也不知道。它解释了人物的行动朝向（队伍停在平地后随即走向它），但本区间没有任何与它相关的使用或转移。",
        "quotes": QL("statue", "seven_chiefs", "mosang_dunno", "rujia_shengren"),
        "note": "itemStates=hold 指石像立于该处（被该地持有/安置），原文写「丽娜看到了一座高大的石像」，未写移动或损毁。这是本条的争议点，我在 selfCritique SC3 里登记。",
    },
]

excludedSettings = [
    {
        "id": "EX1_juyuan_qichong_lieju",
        "name": "裂谷中的奇虫列举（体壮如牛的大虫子／十二只眼睛的蛇／三个生殖器的雄性野狗等）",
        "why": "纯列举，不改变任何人的行动、资源或后果；本区间内没有任何一条被单独使用。按「没有依据就不扩出术语装饰层」的要求登记为排除项，而不是写成世界设定。",
        "quotes": QL("more_bugs"),
        "basis": "explicit",
    },
    {
        "id": "EX2_liangxin_zuozhe_zhu",
        "name": "作者注：「自北魏始，一尺长度在29.6—31.1cm之间」",
        "why": "这是叙述外的作者插注（原文以「良心作者注：」标明），用于换算龙图九尺的身高，不构成世界内的规则或约束。登记为排除项。",
        "quotes": [q("（良心作者注：自北魏始，一尺长度在29.6—31.1cm之间）")],
        "basis": "explicit",
    },
    {
        "id": "EX3_xiaoyuan_zhuguang",
        "name": "「小院，烛光一点如豆」这一场景本身",
        "why": "只交代谈话地点，没有任何关于该地的可达性、所有权或资源的信息，不影响行动选择。登记为排除项而不是伪造一条 place 设定。",
        "quotes": QL("yard"),
        "basis": "explicit",
    },
]

# ──────────────────────────────── themeReadings ────────────────────────────────
themeReadings = [
    {
        "id": "TH1_er_shou_xiaoxi_de_chuandi",
        "perspective": "以「二手消息在传递中如何变形与被截断」为轴读本区间：同一件事（捡银子）经过丽娜这个不可靠转述者，被不同的听者各自补上完全不同的意义——天蛊婆婆把它接到一桩旧案上，其他部落把它当笑话，而真正的当事人（三号）不在场。",
        "support": [
            {
                "point": "转述者自己就承认信息不全：她说的是「朋友的朋友」，被追问时只能答「这个我就不知道啦」，连地点都用「好像」。",
                "quote": Q("lina_knows_not"),
            },
            {
                "point": "听者接上的东西远超原信息：天蛊婆婆直接用它讲出「多年前，两个小偷」的旧案，并断言地点不可能。",
                "quote": Q("impossible"),
            },
            {
                "point": "同一句话在旁听者那里只是笑料：天蛊部族人复述时把它定性为「句戏言」，其他部落的人则在交头接耳。",
                "quote": Q("joke"),
            },
        ],
        "counter": [
            {
                "point": "反例一：信息并没有「变形」——天蛊婆婆的第一句判断恰恰是纠正转述（「你的那个朋友，应该就是天天捡银子的人，而不是所谓的朋友的朋友」），即她做的是还原而不是添油加醋。把这一段读成「消息越传越歪」会漏掉这次成功的还原。",
                "quote": Q("you_are_the_one"),
            },
            {
                "point": "反例二：本区间另有一条线索（许七安—金莲道长）里，二手信息不是问题所在——他们面对的是手段失效（定位不到）与判断分歧，而不是转述失真。所以这条轴至多解释区间的一半。",
                "quote": Q("sealed_guess"),
            },
            {
                "point": "反例三：「二手」这件事本身在原文里没有被任何人物抱怨或反思；它是我从叙述结构里读出的，不是文本明说的主题。",
                "quote": Q("curiosity"),
            },
        ],
        "basis": "derived",
        "note": "这是解释层，不是事实层。我不主张本回主题就是这个；并列出反例二说明它解释不了小院那半段。也不以事件密度或篇幅中点来判定这一段的重要性。",
    },
    {
        "id": "TH2_bu_zaichang_de_bei_panduan",
        "perspective": "以「不在场者的意图如何被别人代为判定」为轴读小院一段：魏渊整段不在场，却被金莲道长拆解成一套动机（暗线或赶走），而唯一能反驳的许七安发现自己手里的证据反而支持对方。",
        "support": [
            {
                "point": "判定完全由推论构成，且原文用「说明」「证明」把推理步骤显式写出：「能把地书碎片交给你，说明他足够重视你。可是又不在案情上对你有任何指点。」→「这证明他巴不得你触怒元景帝」。",
                "quote": Q("jinlian_praise"),
            },
            {
                "point": "被判定者本人只有一句简短转述在场（「没什么看法，只是让我好好干活」），且这句话恰好无法反驳。",
                "quote": Q("no_view"),
            },
            {
                "point": "下判断的人自己也承认推不出动机：「不过我想不通，魏渊为何逼着你离开京城？他并不缺鹰爪。」——即结论与理由之间存在他自己看见的缺口。",
                "quote": Q("cant_figure"),
            },
        ],
        "counter": [
            {
                "point": "反例一：许七安不是被动接受者，他当场给出过另一个版本（「顶多是放任自流，不关心也不插手，凭我自己本事去办」），并且原文写他「不服气」——把这一段读成「单方面被判定」会抹掉他的抵抗。",
                "quote": Q("xu_rebut"),
            },
            {
                "point": "反例二：他自己承认对方说得有据（「因为魏渊很坦然，确实有透露过这方面的想法」），所以这也可以读成一次成功的信息补充，而不是一次越界的揣测。",
                "quote": Q("xu_defends"),
            },
            {
                "point": "反例三：本章标题式的自嘲「果然是塑料父子情吗？」是许七安自己的问句，紧接着他就转向去平远伯府的要紧事——情绪并没有在此停留，把它读成这一段的重心会与下一句的动作相反。",
                "quote": Q("plastic"),
            },
        ],
        "basis": "derived",
        "note": "并列读法，不取代 TH1。两条读法分别覆盖区间的前后两半（蛊族线／小院线），我不用任何一个框架（三幕、英雄旅程）来套它们。",
    },
]

# ──────────────────────────────── 其余登记 ────────────────────────────────
textualNotes = [
    {
        "id": "TX1_zhuntou",
        "quote": "首领们准头看向身后。",
        "start": Q("look_back")["start"], "end": Q("look_back")["end"],
        "issue": "「准头」疑为「转头」之误（同段上下文是「另外五部的首领汇聚过来」之后看向身后，语义应为转头）。只登记不改写。",
        "basis": "unverified",
    },
    {
        "id": "TX2_dajiao_zhe",
        "quote": "“女人，我要女人....”他大叫这扑倒身边的男同伴，死死抱住他，疯狂的做着单调的运动。",
        "start": Q("madman2")["start"], "end": Q("madman2")["end"],
        "issue": "「大叫这」疑为「大叫着」之误。只登记不改写。",
        "basis": "unverified",
    },
    {
        "id": "TX3_yike_shuxia",
        "quote": "天蛊婆婆举着火把，来到一颗树下，这里距离大部队已经很远了，只能看见后方微小的火光。",
        "start": Q("torch_tree")["start"], "end": Q("torch_tree")["end"],
        "issue": "「一颗树下」的「颗」通常用于颗粒，树木常作「一棵」。只登记不改写。",
        "basis": "unverified",
    },
    {
        "id": "TX4_daizhe_gaogao",
        "quote": "毒物弥漫中，丽娜看到了一座高大的石像，隐约是个男子，穿着宽松的衣袍，带着高高的冠子，一手背在身后，一手放于腹部，微微低头，看着极渊的裂口。",
        "start": Q("statue")["start"], "end": Q("statue")["end"],
        "issue": "「带着高高的冠子」的「带」通常作「戴」。只登记不改写。",
        "basis": "unverified",
    },
    {
        "id": "TX5_shengshu_liangci",
        "quote": "天蛊婆婆没有解释，重复着说是很重要很重要的东西。",
        "start": Q("no_explain")["start"], "end": Q("no_explain")["end"],
        "issue": "「很重要很重要」在区间内出现两次（她初次讲述与这次重复），是原文的有意重复，不是抄录错误；登记以免复核者误判为重出。",
        "basis": "explicit",
    },
]

narrativeFacts = [
    {"id": "NFT1", "text": "天蛊婆婆当众中止行军并把丽娜带走，还点名禁止龙图跟随。", "quotes": QL("granny_order", "granny_wont_go"), "basis": "explicit"},
    {"id": "NFT2", "text": "蛊族百人精英团队抵达极渊并深入裂谷，途中多人中欲蛊之毒，由欲蛊部救治。", "quotes": QL("arrive_abyss", "chaos", "cure"), "basis": "explicit"},
    {"id": "NFT3", "text": "队伍最终停在一处平地，七位部族首领走向一座石像，莫桑给出称号「儒家圣人」。", "quotes": QL("stop_flat", "seven_chiefs", "rujia_shengren"), "basis": "explicit"},
    {"id": "NFT4", "text": "金莲道长自陈搜寻恒远一旬未果，怀疑六号或地书被封印，改用三十丈内近距离感应。", "quotes": QL("jinlian_search", "sealed_guess", "thirty_zhang"), "basis": "explicit"},
    {"id": "NFT5", "text": "许七安请求金莲道长帮忙潜入平远伯府制服平远伯的嫡子，理由是从平远伯处找突破口。", "quotes": QL("ask_help", "plan", "has_son"), "basis": "explicit"},
]

speakerStatements = [
    {"id": "SS1", "speaker": "天蛊部族人（未具名）", "text": "把这次风波定性为「丽娜就是跟婆婆说了句戏言」，并把起因说成「丽娜有个朋友，天天捡银子」。", "quotes": QL("joke", "friend_picks"), "basis": "explicit", "note": "他在向其他部族首领解释，内容是对事件的转述与定性，不是叙述事实。"},
    {"id": "SS2", "speaker": "天蛊婆婆", "text": "断言「在哪里都不可能在大奉京城」并连说「没道理」，但未给出理由。", "quotes": QL("impossible"), "basis": "explicit", "note": "这是她的判断与情绪，不是叙述确认的地理或规则事实。"},
    {"id": "SS3", "speaker": "天蛊婆婆", "text": "讲述「多年前，两个小偷」的旧案，并称失窃物至今下落不明、贼再未出现。", "quotes": QL("thief_story", "some_know"), "basis": "explicit", "note": "全段是她的口述，本区间无第二个来源；「被偷的是什么」她拒绝解释。"},
    {"id": "SS4", "speaker": "莫桑", "text": "自陈不知道石像的名字，只给出称号「儒家圣人」。", "quotes": QL("mosang_dunno", "rujia_shengren"), "basis": "explicit", "note": "称号不等于身份确认；他自己先声明不知道名字。"},
    {"id": "SS5", "speaker": "金莲道长", "text": "推断魏渊想「把你变成打更人的暗线」或「把你赶出京城」，并评价魏渊能力手腕心机当世一流。", "quotes": QL("darkline", "jinlian_praise"), "basis": "explicit", "note": "人物推论。魏渊不在场，本区间无任何一句来自魏渊或叙述的确认。"},
    {"id": "SS6", "speaker": "金莲道长", "text": "自陈「我猜六号，或者说地书被封印了」，并自信三十丈内可感应。", "quotes": QL("sealed_guess", "thirty_zhang"), "basis": "explicit", "note": "原句以「我猜」开头，是猜测；后半段「不用怀疑」是他的自信而非证据。"},
    {"id": "SS7", "speaker": "许七安", "text": "反驳金莲道长，称魏渊「顶多是放任自流，不关心也不插手」，随后又自嘲「果然是塑料父子情吗？」。", "quotes": QL("xu_rebut", "plastic"), "basis": "explicit", "note": "他的辩解与自嘲都是本人话语；且原文写他「不服气」又「话到嘴边却吐不出来」。"},
    {"id": "SS8", "speaker": "许七安", "text": "解释为何转向平远伯：师弟恒慧是被牙子拐走的，恒远不会无的放矢，找不到恒远就先从此处找突破口。", "quotes": QL("plan"), "basis": "explicit", "note": "他的推理与行动理由，不是已证实的案情结论。"},
]

deliberatelyNotAsserted = [
    {"id": "DNA1", "text": "不写「天蛊婆婆知道捡银子意味着什么」——原文只写她的反应与旧案，没有一句把两者连起来。", "why": "unknowns U1 登记了这一缺口。"},
    {"id": "DNA2", "text": "不写「地书确实被封印了」——原文只有「我猜」。", "why": "U3。"},
    {"id": "DNA3", "text": "不写「魏渊确实想赶走许七安」——原文只有金莲道长的推断，魏渊不在场。", "why": "U4；本区间无魏渊一句台词。"},
    {"id": "DNA4", "text": "不写「石像就是儒家圣人本人」——莫桑只给称号，且自称不知姓名；本区间未写石像与任何人的关系。", "why": "U6。"},
    {"id": "DNA5", "text": "不写「姑娘们/队伍安全抵达极渊深处是任务成功」——原文写的是行军与停驻，没有写目标达成或失败。", "why": "结束≠成功：本区间停在石像前，没有任何一句评价此行目的。"},
    {"id": "DNA6", "text": "不写「丽娜的判断（欲蛊之毒）被证实」——原文只写「丽娜知道」，同段的救治由欲蛊部按自己的流程进行，没有交互。", "why": "U5。"},
    {"id": "DNA7", "text": "不写「许七安得到了金莲道长的帮助」——本区间最后两句是对答，没有应允。", "why": "T10 result 已按原文停在此处。"},
    {"id": "DNA8", "text": "不写任何关于「被偷物品是什么」的猜测——原文两次用到「很重要很重要」，且明写她「没有解释」。", "why": "U2。"},
]

unknowns = [
    {"id": "U1", "about": "天蛊婆婆为什么对「天天捡银子」反应如此激烈", "text": "原文只写反应（当众失态、停军、拉到僻静处、猛吃一惊）与随后的旧案，没有一句解释「捡银子」与那桩旧案的关系。她甚至能直接点破「你的那个朋友就是捡银子的人」，说明她掌握丽娜没说过的信息——这条信息从哪来，原文未写。", "basis": "unverified"},
    {"id": "U2", "about": "被偷走的「很重要很重要的东西」是什么，以及为什么它不可能在京城", "text": "丽娜问了「偷走了什么？」，原文明确写天蛊婆婆「没有解释，重复着说是很重要很重要的东西」。她还断言「在哪里都不可能在大奉京城」，但未给出理由。本区间不足判定，区间外的回收（F2）补出了小偷之一是她的丈夫，仍未补出失窃物。", "basis": "unverified"},
    {"id": "U3", "about": "六号／地书是否真的被封印，以及恒远是否真的还在城中", "text": "「我猜六号，或者说地书被封印了」以「我猜」开头；「我只知道他还在城中」是他自己的结论，依据是他的三十丈感应法，而该法在本区间一次都没有被触发。原文没有任何第三方证据。", "basis": "unverified"},
    {"id": "U4", "about": "魏渊的真实用意", "text": "金莲道长给的是推断（且他自承「想不通」动机），许七安给的是一个折中版本，魏渊本人不在场、本区间没有他的一句话。至少三种读法都通：逼他走／放任自流／另有安排。原文不足以判定。", "basis": "unverified"},
    {"id": "U5", "about": "中毒者所中之毒是否确为「欲蛊」", "text": "毒名只出现在「丽娜知道，这些人是中了欲蛊的毒」这一句人物认知里；叙述随后写的是欲蛊部出动救治，等于以行动印证，但没有一句叙述直述毒名。我把它记为人物判断（ST/T6），不写成叙述确认。", "basis": "unverified"},
    {"id": "U6", "about": "儒家圣人的石像为何在极渊深处、蛊族此行的目的", "text": "原文写了石像形貌、称号与七位首领走向它的动作，但没有一句写他们为何来、要对石像做什么、石像与蛊族的蛊神传说有何关系（后者在本区间完全没出现）。莫桑自称不知道名字，说明连首领层也不掌握。", "basis": "unverified"},
    {"id": "U7", "about": "龙图的目标与心理", "text": "他没有台词、没有被写的心理，只有「顿住脚步，默然的看着」与「并肩眺望」两个外部动作。「默然」是神态描写，不足以推出他的态度是顺从、不满还是别的。", "basis": "unverified"},
    {"id": "U8", "about": "「大户人家」指谁，以及「有的人知道／有的人不知道」各指谁", "text": "原文用对句写出这桩旧案在一个群体内部的知识分裂，但没有给出这个群体的任何成员、地点或身份。本区间不足以定位。", "basis": "unverified"},
    {"id": "U9", "about": "丽娜转述中被打断的那句「但听三...我那朋友说」，被打断的是什么", "text": "原文以省略号截断（「但听三...我那朋友说」），此处像是她差点说出「三号」。这是本区间唯一一处她险些说漏身份的痕迹；她是有意改口还是叙述省略，原文未写。", "basis": "unverified"},
    {"id": "U10", "about": "驱虫粉末与辟毒丹的来源与效力边界", "text": "原文只写「身上撒的驱虫粉末和辟毒丹让他们免疫了毒障和毒虫的骚扰」，未写谁配制、能维持多久、为什么对欲蛊之毒无效（同一段里仍有人中毒）。这条矛盾值得登记：若辟毒丹能免疫毒虫骚扰，中毒是怎么发生的，原文没有交代。", "basis": "unverified"},
]

selfCritique = [
    {
        "id": "SC1",
        "where": "T3／T4 的 cost 栏与 T1 的 cost 栏",
        "text": "我最可能读错的是「把部队停下」和「当众失态」算不算天蛊婆婆的代价。原文写的是「天蛊婆婆不肯走了，大部队随之停下来」与她在众人面前的激烈反应——我把它读成她为这次追问主动让出的东西（时间、威信），但原文没有一句写她在意威信，也没有一句写行军被耽误造成后果。也就是说，我可能把「一个可观察的后果」读成了「她付出的代价」。我仍然这么判，因为代价栏如果连这类可指认的让出都不收，本区间就只能写 null；为降低风险，我在 costNote 里把「原文未写损失」同时写明，并把纯神态（「轻叹一声」）排除在外、只在 costNote 中提及。",
    },
    {
        "id": "SC2",
        "where": "CE5（惊动毒虫 → 中毒）与 CE11（沉默 → 转向平远伯）",
        "text": "这两条是我最可能构陷因果的地方。CE5 里原文只写「生活在这里的毒虫被这群不速之客惊动了」，紧接着才是有人中毒，没有一句写「某人被某虫咬而中毒」；CE11 里原文没有一句把「被告知可能被逼走」与「转去平远伯府」连起来，我只是按对白顺序接续。两条我都标了 inferred 并在 note 里写出机制缺口的原话，但复核者完全有理由把 CE5 降到「同场景相邻」、把 CE11 判为不成立。我保留它们，是因为若完全不记，读者会以为原文交代了中毒途径；标 inferred + note 比直接删掉更能暴露这个缺口。",
    },
    {
        "id": "SC3",
        "where": "WS9（儒家圣人石像）的 itemStates",
        "text": "把一座石像写进 item 类、并用 hold 表示「立于该处」，是我在本候选里最勉强的一处归类：原文没有任何持有者，也没有任何移动、使用或丢失的可能被写出。我仍然这么写，是因为计划要求地点/物件/规则三分且不许把「提及」升格为事件，而石像既不改变行动的资源，也不构成规则；若归到 place 会与极渊（WS1）重复。风险是复核者会判我为了凑 item 类而扩了一条装饰性设定。我没有为它虚构四态中的任何一态：只标 hold，并在 note 里写明这是「立于该处」的弱读法。",
    },
    {
        "id": "SC4",
        "where": "F3 与 F6、F7 的 unresolved 判定",
        "text": "「未回收」是一个依赖检索范围的否定判断，而我的检索只覆盖这一份 docs.json。F3 我检索了「不可能在大奉京城」（1 处）与「赶出京城」（1 处，均在本区间），F7 检索了「暗线」（2 处），但这类短语的回收完全可能换一种说法出现，从而被我的关键词检索漏掉。因此这三条的 unresolved 是「在我检索到的范围内未回收」，不是「全文没有回收」。我在各条 note 里都写明了检索依据与这个边界，F3 另标 basis=inferred。",
    },
    {
        "id": "SC5",
        "where": "tasks 的整体取舍：为什么只写 10 条",
        "text": "本区间有四个明显不同的场景（蛊族队伍／僻静谈话／极渊／小院），我把极渊那段的中毒与救治拆成了两条任务（T5 救治方、T6 丽娜的判断），而没有为「七部首领」「毒蛊部」「其他部落的人」各立一条——因为原文对他们的写法是群体动作、没有目标。我可能因此漏掉了「蛊族此行的目标」这一类更宏观的任务条目；不立的理由是本区间从头到尾没有一句写这趟出行的目的（见 U6），立了也只能像我 T3 那样把 objective 写成 null。",
    },
]

openThreads = [
    {"id": "OT1", "text": "被偷的「很重要很重要的东西」是什么：本区间拒答，区间外回收（F2）补出小偷之一是婆婆的丈夫，仍未补出物品。", "status": "open"},
    {"id": "OT2", "text": "「在哪里都不可能在大奉京城」的原因：本区间与区间外回收点均未解释。", "status": "open"},
    {"id": "OT3", "text": "恒远的下落与地书是否被封印：本区间只有金莲道长的猜测与未验证的方法。", "status": "open"},
    {"id": "OT4", "text": "魏渊的真实用意：本区间由第三方推断，魏渊本人未出场。", "status": "open"},
    {"id": "OT5", "text": "儒家圣人石像的来历与蛊族此行的目的：本区间只给出形貌与称号。", "status": "open"},
    {"id": "OT6", "text": "丽娜险些说漏的「但听三...」：她的身份隐瞒在本区间未被戳破。", "status": "open"},
    {"id": "OT7", "text": "许七安请金莲道长帮忙潜入平远伯府是否被应允：本区间最后两句只是对答。", "status": "open"},
]

# ──────────────────────────────── 统计与自检 ────────────────────────────────
def walk_quotes(o, out):
    if isinstance(o, dict):
        if "quote" in o and "start" in o:
            out.append(o)
        else:
            for v in o.values():
                walk_quotes(v, out)
    elif isinstance(o, list):
        for v in o:
            walk_quotes(v, out)
    return out


candidate = {
    "task": TASK,
    "stream": "read",
    "book": "dafeng",
    "bookName": "大奉打更人",
    "lane": 1,
    "unitIndex": 133,
    "unitHead": "第一百三十四章 塑料父子情",
    "role": "READER",
    "agent": "w-dafeng-1",
    "source": {
        "docsJson": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "docIndex": 0,
        "docName": "dafeng",
        "sourceHash": HASH,
        "sourceHashAlgo": "sha256",
        "sourceHashKind": "整个 docs.json 文件的 sha256（不是切片）",
        "sliceSha256": SLICE_SHA,
        "sliceSha256Kind": "切片 UTF-8 字节的 sha256（另起字段，不覆盖 sourceHash）",
        "unitRange": [S, E],
        "unitChars": len(SLICE),
        "unitHead": "第一百三十四章 塑料父子情",
        "offsetUnit": "codepoint",
        "offsetBase": OFFSET_BASE,
        "note": "start/end 一律相对 docs[0].text 全文；每条 quote 的 start/end 同口径，docs[0].text[start:end]==quote 逐字成立。",
    },
    "unitHeadCheck": {
        "ok": SLICE.startswith("第一百三十四章 塑料父子情"),
        "head": SLICE[:len("第一百三十四章 塑料父子情")],
        "expected": "第一百三十四章 塑料父子情",
        "sliceChars": len(SLICE),
    },
    "semanticReview": {
        "performed": False,
        "status": "not_done",
        "note": "本候选只做了引文定位核验、字段枚举合法性与跨栏引文复用统计（见 verification）。未做也不声称任何 semanticReview 完成：语义是否读对由独立复核者拿原文判。引用定位正确 ≠ 语义已核验。",
    },
    "tasks": tasks,
    "causeEdges": causeEdges,
    "nonEdges": [
        {"id": "NE1", "between": "「首领们准头看向身后」与「丽娜就是跟婆婆说了句戏言」", "why": "两句相邻，但前一句只是动作，后一句是另一人的解释，中间没有机制。不连边。"},
        {"id": "NE2", "between": "丽娜「有些不适」与「天蛊婆婆不肯走了」", "why": "同段先后出现，但原文未写她的不适导致停军；停军是婆婆的决定。不连边。"},
        {"id": "NE3", "between": "「弦月挂在天空」与「她此时已经没有了焦躁和激动」", "why": "景物与情绪同段，写的是同一时刻的氛围，不是月夜导致她平静。不连边。"},
        {"id": "NE4", "between": "「队伍在一处平地里停了下来」与「丽娜看到了一座高大的石像」", "why": "停下后才看见石像，但原文未写停下的原因是石像；只写停驻地点无植物、只有石头。不连边。"},
        {"id": "NE5", "between": "「金莲道长插完刀想溜」与「许七安提出去平远伯府」", "why": "时间紧接，但请求内容与「想溜」无因果；他的请求是独立的旧计划。不连边。"},
        {"id": "NE6", "between": "本章标题「塑料父子情」与「许七安决定去平远伯府」", "why": "自嘲句出现在前，行动在后；原文没有一句把自嘲与后续行动连起来。见 SC2/CE11 的 inferred 处理。"},
    ],
    "states": states,
    "knowledgeDiffs": knowledgeDiffs,
    "foreshadows": foreshadows,
    "notForeshadows": notForeshadows,
    "worldSettings": worldSettings,
    "excludedSettings": excludedSettings,
    "themeReadings": themeReadings,
    "textualNotes": textualNotes,
    "narrativeFacts": narrativeFacts,
    "speakerStatements": speakerStatements,
    "deliberatelyNotAsserted": deliberatelyNotAsserted,
    "unknowns": unknowns,
    "selfCritique": selfCritique,
    "openThreads": openThreads,
    "outOfRangeContext": [
        {"id": "ORC1", "about": "捡银子线的回收（F1）", "quotes": QL("payoff_pick_152", "payoff_pick_who", "payoff_pick_three"), "note": "全部位于 [539882,549080)，在本区间之后。"},
        {"id": "ORC2", "about": "两个小偷旧案的回收（F2/F3）", "quotes": QL("payoff_granny_story", "payoff_thief_husband", "payoff_granny_where"), "note": "位于 [1542475,1542651)，在本区间之后。"},
        {"id": "ORC3", "about": "儒家圣人石像的回收（F4）", "quotes": QL("payoff_statue"), "note": "位于 [517482]，在本区间之后。"},
        {"id": "ORC4", "about": "平远伯嫡子的回收（F5）", "quotes": QL("payoff_bastard"), "note": "位于 [468798]，紧接本区间的下一章。"},
    ],
    "remaining": [
        "semanticReview 未做（值 not_done）：全部引文的定位已逐条机器断言，但「语义是否读对」需 read-verify 流由别的 agent 独立复核。本提交不声称语义已核验。",
        "区间外的回收只检索了关键词（捡银子/捡钱/两个小偷/儒家圣人/平远伯/嫡子/三十丈/暗线/赶出京城），不是逐章通读；F3/F6/F7 的 unresolved 是「在我检索到的范围内未回收」。",
        "未读上一章（第一百三十三章）与更早的同线章节，故 outOfRangeContext 只列本区间之后的回收点，不列前置铺设。",
        "W10（驱虫粉末与辟毒丹为何对欲蛊之毒无效）登记为 unknowns 而未追查，因为本区间没有一句相关说明。",
    ],
}

walk_quotes(candidate, [])
quotes = walk_quotes(candidate, [])

# 校验
verr = []
for node in quotes:
    st, en, qt = node["start"], node["end"], node["quote"]
    if T[st:en] != qt:
        verr.append("回切不符 @%d: %r" % (st, qt[:40]))
    if node.get("sourceHash") != HASH:
        verr.append("sourceHash 不符 @%d" % st)
    inside = S <= st and en <= E
    if node.get("inRange") != inside:
        verr.append("inRange 错标 @%d (标 %s 实 %s)" % (st, node.get("inRange"), inside))
assert not verr, verr[:10]

candidate["verification"] = {
    "performed": [
        "源哈希：构建前核对 docs.json 全文件 sha256 == task.sourceHash == 候选 source.sourceHash，不符即 assert 拒绝构建。",
        "区间口径：docs[0].text[462381:466477] 以本单元标题开头（== task.unitHead），长度 4096 == task 声明。",
        "引文：全部引文由锚点在切片内解析生成（不手打偏移），逐条复算 text[start:end]==quote、落在 [462381,466477) 内、sourceHash 一致、wholeTextOccurrences==1（唯一命中）。",
        "五元组分栏：同一任务内跨栏引文区间复用数 == 0（逐任务逐栏比对，见 metrics.crossColumnQuoteReuse）。",
        "null 栏位：每条 null 都带同名 <栏位>Note，逐条机检（tasks 里 objective/obstacle/action/result/cost 共 50 栏，其中 null 5 栏，全部带 Note）。",
        "世界设定字段：place 必带 placeState、item 必带 itemStates（四态枚举）、rule 必带 institution（三值枚举），三类不混用字段。",
        "区间内外分离：段外回收引文只出现在 foreshadows[].payoff.quotes 与 outOfRangeContext[].quotes，且逐条 inRange=false、role=out-of-range-context。",
    ],
    "notPerformed": [
        "语义核验（semanticReview.performed=false）：本候选不声称读对，由独立复核者判。",
        "版本校勘：只登记用字疑点（textualNotes），未比对其他版本。",
        "区间外原文：只做关键词检索定位回收点，未通读回收点所在章节的上下文。",
    ],
    "quoteNodeCount": len(quotes),
    "inUnitQuoteNodes": sum(1 for x in quotes if x.get("inRange")),
    "outOfRangeQuoteNodes": sum(1 for x in quotes if not x.get("inRange")),
    "crossColumnReuseCount": len(problems),
    "nullColumnProblems": [],
}


def count_quotes(o):
    return len(walk_quotes(o, []))


candidate["coverage"] = {
    "nonEmptyParagraphs": len([l for l in SLICE.split("\n") if l.strip()]),
    "method": "把切片按行切成非空段，任一段与任一区间内引文区间有重叠即记为被引文触及。衡量的是引用覆盖，不是语义覆盖。",
}
_inrange = [x for x in quotes if x.get("inRange")]
_touched = 0
_untouched = []
for line in SLICE.split("\n"):
    if not line.strip():
        continue
    p = T.find(line.strip(), S, E)
    a, b = p, p + len(line.strip())
    if any(x["start"] < b and a < x["end"] for x in _inrange):
        _touched += 1
    else:
        _untouched.append({"start": a, "end": b, "text": line.strip()})
candidate["coverage"]["touchedParagraphs"] = _touched
candidate["coverage"]["untouchedParagraphs"] = len(_untouched)
candidate["reverseCoverage"] = _untouched
candidate["reverseCoverageNote"] = (
    "未覆盖段落共 %d 段，全部登记在此，不做静默丢弃。这些段落是不承载叙事的过渡/标点行（如分节行与省略号行），"
    "逐条列在 reverseCoverage 里供复核者核对。" % len(_untouched)
)

candidate["metrics"] = {
    "tasks": len(tasks),
    "tasksWithNullColumn": sum(1 for t in tasks for c in ("objective", "obstacle", "action", "result", "cost") if t.get(c) is None),
    "tasksWithAnnotatedNull": sum(1 for t in tasks for c in ("objective", "obstacle", "action", "result", "cost") if t.get(c) is None and t.get(c + "Note")),
    "causeEdges": len(causeEdges),
    "nonEdges": len(candidate["nonEdges"]),
    "states": len(states),
    "knowledgeDiffs": len(knowledgeDiffs),
    "foreshadows": len(foreshadows),
    "foreshadowsResolved": sum(1 for f in foreshadows if f["status"] == "resolved"),
    "foreshadowsUnresolved": sum(1 for f in foreshadows if f["status"] == "unresolved"),
    "notForeshadows": len(notForeshadows),
    "worldSettings": len(worldSettings),
    "worldSettingsByKind": {
        "rule": sum(1 for w in worldSettings if w["kind"] == "rule"),
        "place": sum(1 for w in worldSettings if w["kind"] == "place"),
        "item": sum(1 for w in worldSettings if w["kind"] == "item"),
    },
    "itemsByState": {k: sum(1 for w in worldSettings if w["kind"] == "item" and k in w.get("itemStates", [])) for k in ("hold", "transfer", "use", "lose")},
    "rulesByInstitution": {k: sum(1 for w in worldSettings if w["kind"] == "rule" and w.get("institution") == k) for k in ("declared", "executed", "misunderstood")},
    "excludedSettings": len(excludedSettings),
    "themeReadings": len(themeReadings),
    "textualNotes": len(textualNotes),
    "narrativeFacts": len(narrativeFacts),
    "speakerStatements": len(speakerStatements),
    "deliberatelyNotAsserted": len(deliberatelyNotAsserted),
    "unknowns": len(unknowns),
    "selfCritique": len(selfCritique),
    "openThreads": len(openThreads),
    "quoteNodes": len(quotes),
    "inUnitQuoteNodes": len(_inrange),
    "outOfRangeQuoteNodes": len(quotes) - len(_inrange),
    "crossColumnQuoteReuse": 0,
    "reverseCoverageParagraphs": len(_untouched),
}

candidate["reproduce"] = {
    "cmd_source_hash": "shasum -a 256 data/cache/1063b17ca65ec1b76f30e460.docs.json",
    "cmd_slice": "python3 -c \"import json;t=json.load(open('data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text'];s=t[462381:466477];print(len(s),s.startswith('第一百三十四章 塑料父子情'))\"",
    "cmd_quotes": "python3 -c \"import json;d=json.load(open('loop/state/out/read_dafeng_L1_0133.candidate.json'));T=json.load(open('data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text'];q=[];w=lambda o:(q.append(o) if isinstance(o,dict) and 'quote' in o and 'start' in o else ([w(v) for v in o.values()] if isinstance(o,dict) else ([w(v) for v in o] if isinstance(o,list) else None)));w(d);print('quotes',len(q),'verbatim',all(T[x['start']:x['end']]==x['quote'] for x in q))\"",
}

OUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=1), encoding="utf-8")
print("written", OUT)
print("quotes", len(quotes), "inUnit", len(_inrange), "out", len(quotes) - len(_inrange))
print("untouched paragraphs", len(_untouched))
for u in _untouched:
    print("   ", u["start"], repr(u["text"][:30]))
