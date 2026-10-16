# -*- coding: utf-8 -*-
"""构建 read:dafeng:L2:0174 候选。
所有引文先由 _spec() 在 docs[0].text 里逐字定位并断言，再写入候选；
任何一条断言失败即整脚本中止（不产出文件）。
"""
import json, hashlib, sys, io, os

DOCS = 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
OUT = 'loop/state/out/read_dafeng_L2_0174.candidate.json'
SRC_HASH = 'fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839'
S, E = 627871, 631698

with open(DOCS, 'rb') as f:
    raw = f.read()
assert hashlib.sha256(raw).hexdigest() == SRC_HASH, 'docs.json 哈希与任务声明不符'
DOC = json.loads(raw.decode('utf-8'))
assert isinstance(DOC, list) and isinstance(DOC[0], dict), 'docs.json 顶层结构不是 [ {text:...} ]'
T = DOC[0]['text']
assert len(T) > E, 'docs[0].text 比区间末端还短'
SEG = T[S:E]
assert SEG.startswith('第一百七十四章 鸡精'), '切片不以本单元标题开头：%r' % SEG[:20]
seg_sha = hashlib.sha256(SEG.encode('utf-8')).hexdigest()

# ---- 全文行号 / 段号表（用于 para 字段） ----
LINES = T.split('\n')
LINE_START = []
_c = 0
for _l in LINES:
    LINE_START.append(_c)
    _c += len(_l) + 1

def line_of(off):
    lo, hi = 0, len(LINE_START) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if LINE_START[mid] <= off:
            lo = mid
        else:
            hi = mid - 1
    return lo

_seg_line0 = line_of(S)

def seg_line(off):
    return line_of(off) - _seg_line0

ANCHORS = {}

def A(key, text):
    """登记一条引文锚点。要求：区间内逐字命中。

    坑（实测踩到）：短句（如「黄昏。」）在全文别处也出现，`T.find` 会返回**区间外**的首次出现。
    所以必须取「完全落在 [S,E) 内」的那次出现；全文出现次数单独记，避免把区间外命中当成本段证据。
    """
    assert key not in ANCHORS, '锚点重复登记：%s' % key
    occ = []
    i = T.find(text)
    while i >= 0:
        occ.append(i)
        i = T.find(text, i + 1)
    assert occ, '原文找不到该引文：%s | %r' % (key, text[:40])
    in_range = [i for i in occ if S <= i and i + len(text) <= E]
    assert in_range, '引文在区间内无命中：%s（全文 %d 次，均在区间外）' % (key, len(occ))
    assert len(in_range) == 1, '引文在区间内出现 %d 次，需加长上下文：%s | %r' % (len(in_range), key, text[:40])
    i = in_range[0]
    assert T[i:i + len(text)] == text
    ANCHORS[key] = dict(quote=text, start=i, end=i + len(text),
                        wholeTextOccurrences=len(occ), occurrencesInRange=1,
                        firstOccurrenceAt=i, para=seg_line(i))

def Q(*keys):
    out = []
    for k in keys:
        a = ANCHORS[k]
        out.append({
            "quote": a['quote'], "start": a['start'], "end": a['end'],
            "sourceHash": SRC_HASH,
            "offsetUnit": "codepoint",
            "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
            "match": "exact", "wholeTextOccurrences": a['wholeTextOccurrences'],
            "occurrencesInRange": a['occurrencesInRange'],
            "firstOccurrenceAt": a['firstOccurrenceAt'],
            "startIsFirstOccurrence": a['firstOccurrenceAt'] == a['start'],
            "inRange": True, "para": a['para'],
        })
    return out

# ============================ 锚点登记 ============================
A('q_meta_speech', '陛下说皇后近来食欲不佳，让微臣过来瞧瞧。')
A('q_empress_ask', '是他让你来的？魏公不知本宫病了吗。')
A('q_empress_cured', '已经痊愈。')
A('q_wei_deny', '近来公务繁忙，不知皇后病了。')
A('q_wei_hesitate', '魏渊略作犹豫，摇头道')
A('q_empress_tired', '皇后脸别向一旁，语气平淡：“本宫乏了。”')
A('q_empress_silent', '“....”皇后张了张嘴，想说些什么，但因为各种各样的顾虑，最后什么都没说。')
A('q_eyes', '千言万语都藏在她美丽的眸子里，只是魏渊看不到。')
A('q_wei_no_turn', '魏渊背对着，没有回头。')
A('q_arrive', '魏渊轻车熟路的来到后宫之主，皇后的宫殿外，通传之后，他进入殿内，看见了坐在软塌上的皇后。')
A('q_empress_thin', '这位母仪天下的皇后，进来清减了许多，圆润端庄的脸庞都变的尖俏起来。')
A('q_tea_advice', '“皇后少喝些茶，对脾胃不好...”见皇后露出不耐，魏渊躬身作揖：“微臣告退。”')
A('q_ignorance', '他确实不知道皇后生病了，因为安插在附近的暗子，前段时间被元景帝拔除。')
A('q_empress_unknowing', '而皇后并不知道此事。')
A('q_public_impossible', '这些事儿，不可能当众说出口，便只能任由皇后误会。')
A('q_wei_explain_hq', '陛下听说皇后食欲不佳，身体有恙，让我代他过来探望。')
A('q_emperor_habit', '父皇早已不来后宫了，每日只想着修仙长生，宫中哪个娘娘病了，他才会关注一下，但通常都是派人过来探望了事。')
A('q_hq_noappetite', '宫里服侍的宫女说，母后近来确实没怎么吃东西。')
A('q_wei_worry', '久病之后，若在绝食，身体会落下病根。')
A('q_wei_hides', '魏渊皱紧了眉头，但在怀庆公主面前，他很好的藏住了自己的忧色，只表达出那份臣子该有的担忧。')
A('q_hq_recipe', '许七安有一特制秘方，可让食物鲜味提升百倍，滋味久久难以忘怀。母后食欲不佳，正好可以试一试这个秘方。')
A('q_hq_convenience', '正好打算传唤许七安，既然在此遇到魏公，怀庆便省的让府上侍卫多跑一趟。')
A('q_hq_notworried', '怀庆公主浅笑一下，似乎并不担心')
A('q_xu_treat', '许七安自掏腰包请宋廷风和朱广孝勾栏听曲')
A('q_compensation', '这是许七安弥补他们的')
A('q_donation', '尤其宋廷风，捐了足足五两银子给养生堂。')
A('q_no_money_woe', '他一个没有成家的浪荡子，生活开销倒在其次，没钱去教坊司的话，就会有蛋蛋的忧伤。')
A('q_life_work', '两位同僚边听曲，边把生命的传承工作给做完。')
A('q_left_satisfied', '离开勾栏，鳝饿有鲍的朱广孝和宋廷风无比满足')
A('q_tongluo', '“魏公有请。”那铜锣说道。')
A('q_wei_listen', '听怀庆说，你有秘制的配方，可提升菜肴的鲜味。')
A('q_wei_request', '皇后近来食欲不佳，身体孱弱，本座想试试你的配方。')
A('q_xu_modest', '雕虫小技，不值得魏公记挂。')
A('q_xu_realize', '皇后是怀庆的生母，怀庆托魏渊找我要鸡精....许七安恍然的点点头')
A('q_well', '返回衙门，进入浩气楼，许七安见到了坐在案边看书的魏渊。')
A('q_xu_takes_jar', '见茶室无人，便取出玉石小镜，轻扣背面，一个脑袋大小的罐子摔了出来，被他稳稳的伸手接住。')
A('q_reserved', '褚采薇和宋卿的劳动成果都在这里了，他只给褚采薇留了一小瓶鸡精。')
A('q_wei_smell_frown', '魏渊打开罐子，嗅了嗅，顿时皱眉。他闻到了略有些刺鼻的鲜味。')
A('q_xu_science', '“此物叫鸡精。”许七安科普道。')
A('q_recipe_mix', '鸡精是混合产物，以味精和鸟苷酸为核心成分，这两者合在一起有相辅相成之效。')
A('q_three_meanings', '它共有三种意思，其中一种便是眼前所见的调味料。')
A('q_wei_orders_noodle', '合上盖子，将罐子还给许七安，魏渊唤来吏员：“让厨子去煮碗面。”')
A('q_noodle', '一刻钟的时间后，许七安捧着一碗鸡蛋肉丝面回来，放在魏渊的案上。')
A('q_taste_poison', '魏渊点点头：“你吃一口，帮我试毒。”')
A('q_xu_tasted', '筷子只有一副，许七安用另一头吃了一口。')
A('q_wei_waits', '等待片刻，确认小铜锣没有被自己捧上来的面毒死，魏渊这才动筷子。')
A('q_xu_joke', '说不定毒是抹在筷子上的呢。')
A('q_wei_angry', '魏渊一愣，怒道：“滚出去。”')
A('q_xu_not_roll', '许七安没滚，咧了咧嘴，和魏爸爸相处这么久，魏渊是个不会真正发怒的人，养气功夫深厚的可怕。')
A('q_guoran', '果然，魏渊不再搭理，低头吃面。')
A('q_eyes_light', '等他喝了一口汤汁时，魏渊的眼睛猛的亮起。')
A('q_wei_praise', '“多少大厨呕心沥血，也做不出这种味道。”魏渊满意的点头')
A('q_wei_tired_of_palace', '皇后吃惯了宫里的珍馐美味，厌食除了自身没胃口，吃腻宫里的菜也是一个原因。')
A('q_xu_feels', '许七安能感受到魏爸爸眼里的赞许。')
A('q_bottle', '魏渊从格子里取出一枚瓷瓶，递给许七安，后者接过，从罐子里倒了些许进瓷瓶。')
A('q_yours', '魏渊摇摇头，没接，看着罐子：“瓶子里是留给你的，那才是我的。”')
A('q_stunned', '许七安表情一下子呆滞。')
A('q_dusk', '黄昏。')
A('q_court_food', '宫女端上里一叠叠美味佳肴，浓郁的菜香飘满室内。但皇后神色恹恹，不悦的皱眉：')
A('q_porridge', '“本宫说了，准备一碗清粥便是。”')
A('q_wei_sent_recipe', '魏公刚送了秘制的配方过来，叮嘱我们一定要给娘娘做些好的。')
A('q_taste_it', '“娘娘，您尝尝吧。”')
A('q_they_tasted', '她们已经试过了，味道与众不同，令人难忘。')
A('q_unprecedented', '唯独今天的滋味，是前所未有的味觉体验，不禁让人觉得以前吃的美味不过尔尔。')
A('q_hears_wei', '听是魏渊的安排，皇后叹了口气，有些抗拒的舀了一碗汤，蹙着眉头品尝。')
A('q_soup', '强烈的鲜味在味蕾间炸开，咕噜...修长的脖颈里，喉咙滚动，下意识的就咽了下去。')
A('q_finish_soup', '接着，皇后一口又一口，没有半点抗拒和厌恶的喝完了汤。')
A('q_hungry', '“本宫忽然有些饿了，盛饭。”皇后把碗递给宫女，期待的盯着满桌的美味。')
A('q_next_day', '次日，卯时刚过，皇后宫里的太监带着一批金银玉器来到打更人衙门。')
A('q_eunuch_receive', '魏渊在浩气楼接见了宦官')
A('q_eunuch_praise', '“魏公是何处找来的秘方，皇后娘娘昨夜吃的甚是欢心。”')
A('q_wei_anxious', '魏渊盯着他，有些紧张的问：“没有厌食？吃了多少。”')
A('q_eunuch_report', '吃的比以往都多，比身子好时还多。今儿早起时，皇后娘娘破天荒的问了午膳的伙食。')
A('q_wei_smiles', '魏渊由衷的笑了。')
A('q_hq_summon', '午后刚过，许七安被怀庆公主喊去了宫里')
A('q_hq_improved', '“今日本宫在母后那儿用了午膳，你那配方似乎有所改良？”怀庆公主问道。')
A('q_xu_credit', '“都是宋师兄和采薇姑娘的功劳。”许七安道。')
A('q_hq_yearn', '“本宫有些留恋那种味道，母后却吝啬的不给。你还有吗？”')
A('q_xu_deny', '“没了。”许七安立刻摇头：“满满一罐都给了魏公，送去了皇后娘娘那里。”')
A('q_he_has', '他其实是有的，还有一小瓶，但不能给怀庆，他得给裱裱留着。')
A('q_biaobiao_noisy', '而是裱裱太能闹腾')
A('q_linan', '鸡精这种新奇玩意，迟早传到临安那里。')
A('q_hq_knows_source', '但怀庆公主是知道真正的“始作俑者”是谁，以怀庆的腹黑')
A('q_prediction', '到时候裱裱就会像打翻醋坛子的怨妇，把火气撒到许七安头上。')
A('q_linan_mab', '毕竟在临安公主心里，许七安早已弃暗投明，成了她麾下的马仔。')
A('q_half_jar', '怀庆公主秀眉轻蹙，“可本宫听说，魏渊送到母后那里的...鸡精，是半罐。”')
A('q_xu_startled', '“嗯？”许七安一愣，看向怀庆。')
A('q_silence', '怀庆也看着他，两人不由的沉默了。')
A('q_palace_24', '皇宫内廷有二十四座宫殿，生活着元景帝的妃嫔和孩子。元景帝的后宫一点都不热闹，储秀宫十几年没有收纳年轻貌美的女子。')
A('q_emperor_face', '望着大青衣的背影，元景帝脸上没有任何表情，像是冷硬的雕塑。')
A('q_ps', 'PS：昨天半夜三更，元气大伤，今天没了。')
A('q_wei_asks', '魏渊率先低头：“听说皇后病了？”')
A('q_empress_calls', '“魏渊！”')
A('q_empress_stops', '皇后忽然喊住了他。')
A('q_hq_greet', '“魏公！”怀庆公主施礼。')
A('q_hq_what', '魏渊愕然道：“殿下此言何意？”')
A('q_third_meaning', '另一种是鸡成了精怪，叫**精。还有一种是男人独有的特产。')
A('q_others_leave', '请的自然是许七安，宋廷风和朱广孝知道自己斤两，挥手告别乐善好施的同僚，继续他们的巡街。')
A('q_boyi', '“何事？”许七安问。')
A('q_how', '“怎么样？”许七安期待的问。')
A('q_hand_back', '然后递还给魏渊。')
A('q_xu_understands', '许七安意会，跟着吏员出去。')
A('q_leave_palace', '魏渊离开皇后的宫殿，清风拂来，一袭青衣飘飘荡荡。')
A('q_hq_approaches', '前方，身段高挑的怀庆公主，正领着宫女和侍卫过来。')
A('q_empress_beauty', '她是个极美的女子，年近四十，风华依旧，虽没了少女时代的活泼明媚，但岁月精心雕琢着她的内涵，成熟而端庄的风韵非寻常少女可比。')
A('q_wei_face', '皇后含蓄微笑，凝视着大青衣的脸，面部线条硬朗，高鼻，薄唇，双眼深邃，蕴含着难以言喻的沧桑。')
A('q_wei_temples', '鬓角的霜白让他更显成熟魅力。')
A('q_hq_dress', '她穿着白色的宫裙，绣着鲜艳的梅花，外面罩了一件避寒的大氅，冷艳华贵，清丽脱俗。')
A('q_hq_unlike_mother', '与她母亲年轻时迥异。')
A('q_hq_lotus', '她一如既往的冷艳、高贵、美丽，不去观看丰腴身段的话，会觉得公主殿下是雪山的白莲，一尘不染。')
A('q_empress_greet', '“魏公怎么来了？”皇后含蓄微笑')
A('q_wei_salute', '“殿下。”魏渊作揖还礼')
A('q_tongluo_complaint', '抱怨道：“你们去何处摸鱼？半天寻不到人。”')
A('q_xu_gossip', '怀庆这么八卦的吗？这种小事也到处乱说')
A('q_first_taste', '咀嚼着劲道的面条，他有些意外于面条的口感，受到了味蕾被鸡精冲击的初体验。')
A('q_years_tasting', '在皇宫住了这么多年，替主子们试过各种各样的山珍海味。')
A('q_never_mind', '这没关系，毕竟是魏渊送的。')
A('q_hq_um', '怀庆公主“嗯”了一声')

BASIS = {"explicit": "原文直述（含叙述层记录下的言语动作；被记录的话本身不因被记录而成事实）",
         "inferred": "我的归纳（原文没有直接写出这一步）",
         "derived": "跨段推导（多段证据合成，单段不足以成立）",
         "unverified": "存疑（区间内无法判定，或存在互相矛盾的说法）"}

def col(text, basis, quotes, note=None):
    d = {"text": text, "basis": basis, "quotes": quotes}
    if note:
        d["note"] = note
    return d

# ============================ tasks ============================
tasks = []

tasks.append({
    "id": "T1_yuanjing_sends_wei",
    "who": "元景帝（差遣方）→ 魏渊（执行方）",
    "label": "代皇帝探望食欲不佳的皇后，并被当面追问是否知情",
    "objective": col(
        "把皇帝的口信带到、当面探视皇后。直接可引的只有魏渊本人转述的那句口信；"
        "「元景帝想要什么」在区间内没有一句叙述层正面写过——他只在开头露过一面，脸上没有任何表情。"
        "另一句旁证来自怀庆视角的叙述层（不是全知断言）：皇帝对生病的妃嫔「才会关注一下」，处理方式是派人探望。",
        "inferred", Q('q_meta_speech', 'q_emperor_habit'),
        note="两段合起来才能支撑「这是皇帝的意思」：口信是**人物转述**，习惯是**怀庆视角的叙述层**；"
             "本栏因此标 inferred 而不是 explicit。"),
    "obstacle": col(
        "两重，都有直证：① 魏渊真的不知道皇后病过——叙述层用「因为」点明原因是他安插在皇后宫附近的暗子"
        "已被元景帝拔除；② 这件事「不可能当众说出口」，所以他在皇后当面质问时给出的只能是会被读成推托的答案。"
        "会面开场就带着这层错位：皇后第一句是「魏公怎么来了？」——她并没有料到他会来。",
        "explicit", Q('q_empress_greet', 'q_ignorance', 'q_public_impossible'),
        note="②是处境约束而不是人物选择：原文写的是「不可能」，并且紧跟一句「便只能任由皇后误会」。"),
    "action": col(
        "通传后进入皇后寝殿，先问病、再传口信；被下逐客令前叮嘱一句「皇后少喝些茶」，随后躬身告退。",
        "explicit", Q('q_arrive', 'q_tea_advice')),
    "result": col(
        "口信带到了，误会没有解除：皇后先追问「是他让你来的？魏公不知本宫病了吗」，听完否认后把脸别向一旁称乏；"
        "她叫住魏渊却又因顾虑什么都没说，魏渊始终没有回头。叙述层给出的收束是「便只能任由皇后误会」。"
        "**这既不是成功也不是失败**：原文没有写皇后相信了否认，也没有写她不信。",
        "explicit", Q('q_empress_ask', 'q_empress_silent', 'q_eyes')),    "cost": None,
    "costNote": "本区间没有写元景帝或魏渊为这趟差事付出任何资源：没有赏赐、处罚、金钱或人情支出。"
                "魏渊唯一的实际损失是被误会，但原文把它写成无法澄清的处境（「便只能任由皇后误会」），不是他付出的代价；"
                "另：「安插在附近的暗子，前段时间被元景帝拔除」虽然在这段文字里被叙述，却发生在区间之前的「前段时间」，"
                "是「他确实不知道」的**原因**而不是这趟探望的**支出**，所以不记进 cost。",
})

tasks.append({
    "id": "T2_huaiqing_recipe_for_mother",
    "who": "怀庆公主（提议方）→ 魏渊（转达方）",
    "label": "把许七安的秘方引进母后的膳食",
    "objective": col(
        "让食欲不佳的母后重新吃东西。她给出的手段是许七安的秘方（「可让食物鲜味提升百倍」），"
        "目的写得和手段同句：「母后食欲不佳，正好可以试一试这个秘方」——目的是母后的进食，不是她自己尝鲜"
        "（她自己想再吃是次日才说的另一件事）。",
        "explicit", Q('q_hq_recipe')),
    "obstacle": col(
        "阻碍在事不在人：母后近来确实吃得很少（**这句是转述宫女的观察**），而能提供秘方的许七安不在宫中——"
        "她原本的路径是「传唤」，要靠府上侍卫跑一趟。",
        "explicit", Q('q_hq_noappetite'),
        note="本栏只写「她原先的路径要派人」，不写「她遇到困难」——原文写的是她「正好打算传唤」，语气是顺路。"),
    "action": col(
        "在宫道上叫住魏渊、施礼（「魏公！」怀庆公主施礼），把秘方的信息与用途当面交给他，"
        "省掉了自己派人传唤的那一趟。",
        "explicit", Q('q_hq_greet', 'q_hq_convenience')),
    "result": col(
        "信息确实转成了行动：随后魏渊在浩气楼对许七安开口第一句就是「听怀庆说，你有秘制的配方，可提升菜肴的鲜味」；"
        "再往后，皇后宫里的宫女对新膳的说法是「魏公刚送了秘制的配方过来」。"
        "**结果不是她直接达成的**，中间经了魏渊与许七安两道手；本栏因此标 derived。",
        "derived", Q('q_wei_listen', 'q_wei_sent_recipe')),
    "cost": None,
    "costNote": "本区间没有写怀庆为这件事付出任何代价：没有出钱、没有许诺、没有失位；"
                "她甚至因为遇到魏渊而省下一趟差遣（「怀庆便省的让府上侍卫多跑一趟」）——省下开销与付出代价方向相反。"
                "次日她向许七安索要鸡精被回「没了。」，那是**请求未达成**，不是这次提议的代价。",
})

tasks.append({
    "id": "T3_wei_gets_chicken_essence",
    "who": "魏渊（索取方）→ 许七安（供给方）",
    "label": "为皇后取鸡精，先自己试味、按规矩试毒",
    "objective": col(
        "要的是**可用的调味成品**，理由他一次说完：「皇后近来食欲不佳，身体孱弱，本座想试试你的配方」。"
        "对照他此前对怀庆的说法（奉命探望），可以确认这趟索取是冲着皇后的食欲去的——但那是跨句对照，本栏只引他自己的诉求句。",
        "explicit", Q('q_wei_request')),
    "obstacle": col(
        "他不认识也不信任这个东西：打开罐子先「嗅了嗅，顿时皱眉」，闻到的鲜味「略有些刺鼻」；"
        "因此面端上来后他不先动筷，要许七安先吃——「你吃一口，帮我试毒」。",
        "explicit", Q('q_wei_smell_frown', 'q_taste_poison')),
    "action": col(
        "合上盖把罐子还回去后唤吏员让厨子煮面；等面端来、许七安试过、确认没出事，他才动筷子。",
        "explicit", Q('q_wei_orders_noodle', 'q_wei_waits')),
    "result": col(
        "吃面的当场反应有叙述层直证：他先「有些意外于面条的口感」，喝汤时「眼睛猛的亮起」；"
        "随后给出明确评价「多少大厨呕心沥血，也做不出这种味道」，并留下整罐（原文：「那才是我的」——该句已作为 cost 证据，"
        "按任务规则不在本栏重引）。其后鸡精确实到了皇后膳房：宫女说「魏公刚送了秘制的配方过来」，"
        "皇后的反应与恢复进食写在 T7；次日皇后宫里的公公当面说「魏公是何处找来的秘方，皇后娘娘昨夜吃的甚是欢心」。"
        "**最后一句是人物话**，它与 T7 的叙述层一致才被采信；区间结束前没有写魏渊因此领赏。",
        "explicit", Q('q_first_taste', 'q_eyes_light', 'q_wei_praise', 'q_eunuch_praise'),
        note="本栏刻意把「魏渊本人的评价」与「别人转述的效果」分开列，避免把话当事实。"),
    "cost": col(
        "从自己格子里取出一枚瓷瓶交给许七安分装，最后没有收回：「瓶子里是留给你的，那才是我的」。"
        "这是区间内唯一从魏渊流向许七安的资源。**「把它算作代价」是我的归类（inferred），物证是叙述层的交付动作**；"
        "金额、人情、权力代价一概没有写。",
        "inferred", Q('q_bottle', 'q_yours'),
        note="分类依据：任务五元组里的 cost 指「付出什么」，而这两句只写了器物归属的转移，没有写对价关系。"),
})

tasks.append({
    "id": "T4_xu_delivers_jar",
    "who": "许七安（供给方）→ 魏渊（受方）",
    "label": "把整罐鸡精交出去，只留小瓶量级",
    "objective": col(
        "满足魏渊的索取并把自己在其中的角色说小：他先自认「雕虫小技，不值得魏公记挂」，"
        "随后按自己的推断（「皇后是怀庆的生母，怀庆托魏渊找我要鸡精」）取出罐子。"
        "**「怀庆托魏渊找我要」是他本人的推断**，本区间没有写怀庆直接托付过。",
        "explicit", Q('q_xu_modest', 'q_xu_realize')),
    "obstacle": col(
        "交付前的两关：① 东西要避人取出——他先确认「见茶室无人」才取法器倒罐；"
        "② 交出去不会直接被接受，要先由他本人试毒。",
        "explicit", Q('q_xu_takes_jar', 'q_taste_poison')),
    "action": col(
        "被铜锣拦下传话后返回衙门；用玉石小镜把罐子取出来；魏渊下令煮面后他跟着吏员出去，"
        "一刻钟后捧回一碗鸡蛋肉丝面；被要求试毒时，因为「筷子只有一副」，他用另一头吃了一口。"
        "他心里还抱怨了一句消息走漏之快（「怀庆这么八卦的吗？这种小事也到处乱说」）——"
        "**这是他的内心话，不是叙述事实**，本栏只把它记为动作的伴随心理。",
        "explicit", Q('q_boyi', 'q_tongluo_complaint', 'q_xu_gossip', 'q_noodle', 'q_xu_tasted')),
    "result": col(
        "东西被收下、他也被认可：叙述层写「许七安能感受到魏爸爸眼里的赞许」；"
        "他留在手里的东西被叙述层点明只有小瓶量级——「褚采薇和宋卿的劳动成果都在这里了，他只给褚采薇留了一小瓶鸡精」。"
        "**叙述层从未写那只罐子原来是满的**（见 unknowns U5）。",
        "explicit", Q('q_xu_feels', 'q_reserved')),
    "cost": None,
    "costNote": "本栏写 null 而不是「付出了整罐」：原文只写了罐子的归属转到魏渊手里、以及他自己留了「一小瓶」，"
                "但**从头到尾没有写过罐子原来有多少**（首次出场只有「一个脑袋大小的罐子」），"
                "因此「损失了多少」不可量化；把不可量化的东西写成一条成本，等于用未知填默认值。"
                "可引的两句（「他只给褚采薇留了一小瓶」「他其实是有的，还有一小瓶」）已分别用于 result 与 T6，"
                "按本任务「同一句不得同时充当多栏依据」的规则不在本栏重引。",
})

tasks.append({
    "id": "T5_xu_makes_up_to_colleagues",
    "who": "许七安（请客方）→ 宋廷风、朱广孝（被请方）",
    "label": "自掏腰包请同僚听曲，弥补宋廷风的捐款",
    "objective": col(
        "让两位同僚（尤其捐过钱的宋廷风）得到补偿：叙述层直接定性「这是许七安弥补他们的」，"
        "并把指名的理由写在同一段——宋廷风「捐了足足五两银子给养生堂」。",
        "explicit", Q('q_compensation', 'q_donation')),
    "obstacle": None,
    "obstacleNote": "本区间没有写任何阻碍：没有人拒绝、没有禁令、没有钱不够的描写。"
                    "同段那句「没钱去教坊司的话，就会有蛋蛋的忧伤」是**一般情形的假设句**（「的话」），"
                    "不是他这次遇到的阻碍，所以不拿来充 obstacle。",
    "action": col(
        "自掏腰包请宋廷风和朱广孝去勾栏听曲。",
        "explicit", Q('q_xu_treat')),
    "result": col(
        "两位同僚满足了：叙述层写他们「边听曲，边把生命的传承工作给做完」，离开勾栏时「无比满足」；"
        "三人随后继续巡街（「继续他们的巡街」）。**「无比满足」是叙述层对两人的状态描写**，本栏只据此写状态，"
        "不解释具体行为；被铜锣拦下传话发生在补偿完成之后，不属于本栏结果。",
        "explicit", Q('q_life_work', 'q_left_satisfied', 'q_others_leave')),
    "cost": col(
        "代价是钱、且是他自己的钱；但本栏的证据是**间接的**，我按 inferred 标："
        "叙述层没有写他花了多少，只写了他这类开销的性质——「他一个没有成家的浪荡子，生活开销倒在其次，"
        "没钱去教坊司的话，就会有蛋蛋的忧伤」。至于「自掏腰包」那句已作为 action 的证据，按本任务规则不在本栏重引。"
        "金额、是否挤占其他开支，区间内都没有写。",
        "inferred", Q('q_no_money_woe'),
        note="本栏是本候选里最弱的一栏，理由如上；若复核认为「一般处境说明句」不足以支撑 cost，"
             "应改判为 null + 理由，而不是另编一条支出。"),
})

tasks.append({
    "id": "T6_xu_hides_bottle_from_huaiqing",
    "who": "许七安（隐瞒方）→ 怀庆公主（被隐瞒方）",
    "label": "对怀庆否认还有鸡精，实际留了一小瓶给裱裱",
    "objective": col(
        "保住手里剩下的那一小瓶、把它留给裱裱：「他其实是有的，还有一小瓶，但不能给怀庆，他得给裱裱留着」。"
        "他避的不是怀庆本人而是后续连锁：鸡精迟早传到临安那里，届时「裱裱就会像打翻醋坛子的怨妇，把火气撒到许七安头上」。"
        "**这两段都是叙述层写他的心理，不是他的台词，也不是已发生的事**（预测，见 foreshadows F2）。"
        "他的顾虑里还有一条自我安慰：即使传开也「没关系，毕竟是魏渊送的」——即责任落在魏渊那边。",
        "explicit", Q('q_he_has', 'q_never_mind', 'q_prediction')),
    "obstacle": col(
        "怀庆当面索要（「你还有吗？」），而且她手里有一条与他的说法冲突的消息——"
        "「可本宫听说，魏渊送到母后那里的...鸡精，是半罐」。**「听说」标明这是转述，不是叙述事实**；"
        "她本人也说了这是「本宫听说」。另一重阻碍来自叙述层：她「是知道真正的“始作俑者”是谁」——"
        "也就是说他知道源头在许七安，否认并不容易成立（该句后接「以怀庆的腹黑」，属叙述层的预判，见 F2）。",
        "explicit", Q('q_hq_yearn', 'q_half_jar', 'q_hq_knows_source')),
    "action": col(
        "当场否认，并把去处一并交代掉以封闭追问：「没了。」许七安立刻摇头：「满满一罐都给了魏公，送去了皇后娘娘那里。」",
        "explicit", Q('q_xu_deny')),
    "result": col(
        "他没有改口，怀庆也没有继续逼问；场面停在对峙上——「“嗯？”许七安一愣，看向怀庆。」、"
        "「怀庆也看着他，两人不由的沉默了」。**区间到此结束，没有写他是否被拆穿，也没有写怀庆是否追问下去**（见 U4/U6）。",
        "explicit", Q('q_xu_startled', 'q_silence')),
    "cost": None,
    "costNote": "本区间没有写他为这次隐瞒付出任何代价：没有损失、没有让步、没有被罚，也没有写他因此欠下人情。"
                "**唯一逼近代价的是风险**——叙述层点明怀庆知道「真正的“始作俑者”是谁」、又听说了「是半罐」，"
                "说谎被撞破的可能性是明写的，但**风险不是已付出的代价**，所以本栏写 null 而不是把它包装成支出。",
})

tasks.append({
    "id": "T7_empress_eats",
    "who": "皇后（进食方）／魏渊—宫女（送膳方）",
    "label": "从只要一碗清粥，到主动要饭",
    "objective": col(
        "她一开始的诉求是**不要**那一桌菜：「本宫说了，准备一碗清粥便是。」"
        "本栏方向与前几条任务相反——她想要的是不被劝食。",
        "explicit", Q('q_porridge')),
    "obstacle": col(
        "抗拒是有理由的：端上来的正是一桌她吃不下的东西（「一叠叠美味佳肴」而「皇后神色恹恹，不悦的皱眉」）；"
        "叙述层还把厌食的一个原因写明——「吃腻宫里的菜也是一个原因」，"
        "并用宫女的资历旁证这一点：「在皇宫住了这么多年，替主子们试过各种各样的山珍海味」。",
        "explicit", Q('q_court_food', 'q_wei_tired_of_palace', 'q_years_tasting')),
    "action": col(
        "在宫女劝说下动勺：推动她的两个条件都有直证——菜是魏渊叮嘱做的（她「听是魏渊的安排」才叹了口气舀汤），"
        "宫女们自己「已经试过了」并力荐。**她是在「有些抗拒」的状态下开始喝的**。",
        "explicit", Q('q_hears_wei', 'q_they_tasted')),
    "result": col(
        "她喝完了一整碗汤并主动要饭。三条证据的层级不同，必须分开："
        "① **叙述层**写她喝完——「接着，皇后一口又一口，没有半点抗拒和厌恶的喝完了汤」；"
        "② **她本人**说「本宫忽然有些饿了，盛饭」；③ 次日是**公公报告**「破天荒的问了午膳的伙食」。"
        "「恢复进食」这一结论由①直证，不是从「本章结束」推出来的；②③是人物话，只作旁证。",
        "explicit", Q('q_finish_soup', 'q_hungry', 'q_eunuch_report')),
    "cost": None,
    "costNote": "本区间没有写皇后为这顿饭付出任何代价：没有付钱、没有许诺、没有失态后的惩罚。"
                "她放下的只是「抗拒」这个态度（「有些抗拒的舀了一碗汤」）——态度不是代价。"
                "次日「皇后宫里的太监带着一批金银玉器来到打更人衙门」方向是从皇后宫流出，"
                "但它是谢礼/赏赐而不是她进食的代价，而且**原文没有写魏渊收没收**（见 U14），故也不计入本栏。",
})

# 任务内引文不得复用（机器断言）
for _t in tasks:
    _seen = {}
    for _c in ("objective", "obstacle", "action", "result", "cost"):
        _v = _t.get(_c)
        if not isinstance(_v, dict):
            continue
        for _q in _v.get("quotes", []):
            _k = (_q["start"], _q["end"])
            assert _k not in _seen, "任务 %s 的 %s 与 %s 复用了同一句引文 %r" % (
                _t["id"], _c, _seen[_k], _q["quote"][:30])
            _seen[_k] = _c

# ============================ causeEdges ============================
causeEdges = [
    {"id": "C1", "from": "元景帝拔除魏渊安插在皇后宫附近的暗子", "to": "魏渊确实不知道皇后生病",
     "mechanism": "情报渠道被移除 ⇒ 他失去皇后近况的消息来源。叙述层用「因为」把两件事直连，属于机制而非相邻。",
     "basis": "explicit", "quotes": Q('q_ignorance')},
    {"id": "C2", "from": "魏渊不知情 + 此事不可能当众说出口", "to": "皇后保留对魏渊的误会",
     "mechanism": "要澄清就必须说出暗子与皇帝的动作，而原文写这件事「不可能当众说出口」；"
                  "于是他只给出「近来公务繁忙，不知皇后病了」这个说法，皇后把这读成推托，误会因此没有被纠正。",
     "basis": "derived", "quotes": Q('q_public_impossible', 'q_wei_deny', 'q_wei_hesitate'),
     "note": "「略作犹豫」是叙述层写他的迟疑，说明这个否认不是随口；把犹豫也算作机制的一环。"},
    {"id": "C3", "from": "皇后食欲不佳（含吃腻宫中菜）", "to": "怀庆把许七安的秘方当成手段",
     "mechanism": "问题与手段在怀庆口中被直接连起来：「母后食欲不佳，正好可以试一试这个秘方」；"
                  "而厌食的成因由叙述层另一段补出（吃腻宫里的菜也是原因之一），说明为什么「鲜味」能对症。",
     "basis": "explicit", "quotes": Q('q_hq_recipe', 'q_wei_tired_of_palace')},
    {"id": "C4", "from": "怀庆把秘方的事告诉魏渊", "to": "魏渊向许七安索取鸡精",
     "mechanism": "魏渊开口第一句就是「听怀庆说，你有秘制的配方」——信息链在文本里被自己点明，不是在时间上挨着。",
     "basis": "explicit", "quotes": Q('q_wei_listen')},
    {"id": "C5", "from": "魏渊试吃并认可鸡精", "to": "鸡精被送进皇后膳房",
     "mechanism": "他索取时就说明用途是皇后（「本座想试试你的配方」），试吃后给出「多少大厨呕心沥血，也做不出这种味道」的评价；"
                  "随后宫女说「魏公刚送了秘制的配方过来，叮嘱我们一定要给娘娘做些好的」。"
                  "**「认可→送达」这一步文本没有用因果连词直连**，所以本边标 derived。",
     "basis": "derived", "quotes": Q('q_wei_praise', 'q_wei_sent_recipe')},
    {"id": "C6", "from": "菜是魏渊叮嘱做的 + 宫女先试过并力荐", "to": "皇后肯动勺",
     "mechanism": "她先说「准备一碗清粥便是」，听到是魏渊的安排后「叹了口气」才舀汤；"
                  "叙述层另写宫女「已经试过了」并当面劝「娘娘，您尝尝吧」——劝食与试吃是同时给的两个条件。",
     "basis": "derived", "quotes": Q('q_hears_wei', 'q_they_tasted', 'q_taste_it')},
    {"id": "C7", "from": "皇后恢复进食", "to": "皇后宫送金银玉器到衙门 + 魏渊「由衷的笑了」",
     "mechanism": "公公把谢礼的由来直接说成「皇后娘娘昨夜吃的甚是欢心」；魏渊是在听到「吃的比以往都多」之后笑的。"
                  "两处都有说话人或叙述层的时间与内容指向，不是同场景硬连。",
     "basis": "explicit", "quotes": Q('q_eunuch_praise', 'q_eunuch_report', 'q_wei_smiles')},
    {"id": "C8", "from": "怀庆听说送到皇后处的是半罐", "to": "许七安「满满一罐」的说法当场露出口径冲突，两人沉默",
     "mechanism": "两条互斥的数量说法被放在同一段对话里：她先问「你还有吗」，他答「没了……满满一罐」；"
                  "她随即给出「是半罐」。叙述层用「两人不由的沉默了」收束，冲突没有被解释掉。",
     "basis": "derived", "quotes": Q('q_half_jar', 'q_silence', 'q_xu_startled')},
    {"id": "C9", "from": "魏渊没有接回分装的瓷瓶", "to": "许七安手里留下小瓶量级的鸡精（次日他说「还有一小瓶」）",
     "mechanism": "魏渊明确说「瓶子里是留给你的，那才是我的」，即分装的小瓶归许七安；"
                  "次日叙述层写「他其实是有的，还有一小瓶」。**本边只主张「他手里有可留之物」**；"
                  "把这只瓷瓶与留给裱裱的那一瓶认定为同一只，是未证的（见 rejectedEdges R5 与 U6）。",
     "basis": "derived", "quotes": Q('q_yours', 'q_he_has')},
]

rejectedEdges = [
    {"id": "R1", "wouldBeEdge": "元景帝面无表情地望着魏渊的背影 → 他对这次探望不满／另有所图",
     "why": "他全章只出现这一次，没有台词、没有后续呼应，也没有人物对他的表情作过任何解读；"
            "「表情=态度」在这里没有机制可写，属编造动机。", "quotes": Q('q_emperor_face')},
    {"id": "R2", "wouldBeEdge": "怀庆「似乎并不担心」→ 她次日追问鸡精",
     "why": "「似乎」标记了这是外部观察，两处之间没有给出任何解释；按时间相邻连边会把观察当成心理事实。",
     "quotes": Q('q_hq_notworried', 'q_hq_yearn')},
    {"id": "R3", "wouldBeEdge": "许七安请同僚听曲／宋廷风捐款 → 皇后食欲恢复",
     "why": "两个场景只是叙述顺序相邻（同一章前后段），人物、地点、物件都不同，没有可写的机制。",
     "quotes": Q('q_donation', 'q_finish_soup')},
    {"id": "R4", "wouldBeEdge": "元景帝拔除暗子 → 皇后误会（直连）",
     "why": "中间必须经过「魏渊不知情」与「不可能当众说出口」两项才能解释误会；砍掉中间项就是相邻即因果。"
            "本候选因此拆成 C1+C2 两条边。", "quotes": Q('q_ignorance', 'q_public_impossible')},
    {"id": "R5", "wouldBeEdge": "魏渊让许七安分装的那只瓷瓶 = 次日他说「还有一小瓶／给裱裱留着」的那一瓶",
     "why": "两处都只写「一小瓶」，没有指明同一只；区间内还另有「他只给褚采薇留了一小瓶鸡精」，"
            "三处小瓶的对应关系无法从原文确定。", "quotes": Q('q_bottle', 'q_he_has', 'q_reserved')},
    {"id": "R6", "wouldBeEdge": "「确认小铜锣没有被面毒死」→ 这碗面被证明无毒／宫里试毒是常制",
     "why": "原文写的是「等待片刻，确认小铜锣没有被自己捧上来的面毒死，魏渊这才动筷子」——这是叙述层的叙述，"
            "不是化验结论，也不能从两个例子推出普遍制度（见 U13）。", "quotes": Q('q_wei_waits', 'q_they_tasted')},
]

# ============================ states ============================
states = [
    {"id": "S1", "who": "魏渊（知识状态）",
     "before": "只知道皇帝口信里的「食欲不佳」，不知道皇后病过",
     "after": "在皇后当面追问下得知她病过并自称已痊愈；但对外仍只承认「不知皇后病了」，误会未被纠正",
     "anchor": "会面本身：他先问「听说皇后病了？」→ 传口信 → 皇后追问 → 他的否认",
     "basis": "explicit", "quotes": Q('q_wei_asks', 'q_meta_speech', 'q_empress_ask', 'q_empress_cured', 'q_wei_deny'),
     "note": "「已经痊愈」是皇后的话，本栏只记「她说自己痊愈了」，不记「她确实痊愈了」。"},
    {"id": "S2", "who": "皇后（对魏渊的认知）",
     "before": "当面质问「是他让你来的？魏公不知本宫病了吗」——把「知情而不来」当成一种可能",
     "after": "把脸别向一旁称乏；叫住魏渊后因顾虑什么都没说，误会保留（叙述层：「便只能任由皇后误会」）",
     "anchor": "皇后宫殿内的整场会面：追问 → 称乏 → 喊住他 → 什么都没说；收束句是「任由皇后误会」",
     "basis": "explicit", "quotes": Q('q_empress_ask', 'q_empress_tired', 'q_empress_calls', 'q_empress_silent', 'q_public_impossible'),
     "note": "「误会」的具体内容原文没有写（见 U2），本栏只记状态方向：从质问到不解释地保留。"},
    {"id": "S3", "who": "皇后（食欲／进食）",
     "before": "只要一碗清粥，对满桌佳肴「神色恹恹，不悦的皱眉」",
     "after": "喝完一碗汤、主动要饭「本宫忽然有些饿了，盛饭」；次日「破天荒的问了午膳的伙食」",
     "anchor": "黄昏的送膳与次日太监的报告",
     "basis": "explicit", "quotes": Q('q_porridge', 'q_hungry', 'q_eunuch_report')},
    {"id": "S4", "who": "魏渊（情绪）",
     "before": "为皇后的身体皱紧眉头，但在怀庆面前藏住忧色，只表达「臣子该有的担忧」",
     "after": "听到公公报告后「由衷的笑了」",
     "anchor": "宫道相遇 → 次日在浩气楼接见宦官",
     "basis": "explicit", "quotes": Q('q_wei_worry', 'q_wei_hides', 'q_wei_anxious', 'q_wei_smiles'),
     "note": "中间的「魏渊盯着他，有些紧张的问：“没有厌食？吃了多少。”」是 before→after 之间的过渡证据，一并列出。"},
    {"id": "S5", "who": "许七安（持有与口径）",
     "before": "持有整罐可支配的鸡精；对魏渊只自称「雕虫小技」并照给，听到「瓶子里是留给你的」时「表情一下子呆滞」",
     "after": "对怀庆声称「没了」，实际仍留有一小瓶；被「半罐」的消息顶住后沉默",
     "anchor": "浩气楼交付（含魏渊留下瓷瓶） → 次日宫中的索要与否认",
     "basis": "explicit", "quotes": Q('q_xu_takes_jar', 'q_stunned', 'q_xu_deny', 'q_he_has')},
    {"id": "S6", "who": "怀庆公主（信息状态）",
     "before": "只知道「味道」值得留恋，向许七安索要（「你还有吗？」）",
     "after": "抛出「可本宫听说，魏渊送到母后那里的...鸡精，是半罐」，与许七安的「满满一罐」形成对立；她没有继续追问",
     "anchor": "午后宫中的一问一答",
     "basis": "inferred", "quotes": Q('q_hq_yearn', 'q_half_jar'),
     "note": "她从哪里听说、何时听说，区间内没有写（见 U3），所以本栏标 inferred。"},
]

knowledgeDiffs = [
    {"id": "K1", "what": "魏渊的暗子被元景帝拔除",
     "whoKnows": ["元景帝（拔除的执行者）", "魏渊（叙述层写明他因此不知情）"],
     "whoDoesNotKnow": ["皇后（「而皇后并不知道此事」）"],
     "basis": "explicit", "quotes": Q('q_ignorance', 'q_empress_unknowing')},
    {"id": "K2", "what": "怀庆是否知道宫中曾有魏渊的暗子",
     "whoKnows": [], "whoDoesNotKnow": [],
     "basis": "unverified", "quotes": Q('q_empress_unknowing'),
     "note": "区间内没有一句写她知道或不知道。本栏留空双方名单而不是默认「不知道」——缺证据不等于已知。"},
    {"id": "K3", "what": "许七安手里还留有一小瓶鸡精",
     "whoKnows": ["许七安"],
     "whoDoesNotKnow": ["怀庆（她只问「你还有吗」，并依赖的是「听说」的半罐消息）"],
     "basis": "inferred", "quotes": Q('q_he_has', 'q_hq_yearn'),
     "note": "「怀庆不知道」是从她提问与她的消息来源推的，不是叙述直述；故标 inferred。"},
    {"id": "K4", "what": "怀庆已经听说「魏渊送到母后那里的...鸡精，是半罐」",
     "whoKnows": ["怀庆"],
     "whoDoesNotKnow": ["许七安（他的「一愣」在消息抛出之后，属预期外反应）"],
     "basis": "inferred", "quotes": Q('q_xu_startled', 'q_half_jar'),
     "note": "「不知情」由反应推断，不是叙述直述。"},
    {"id": "K5", "what": "皇后病过这件事",
     "whoKnows": ["皇后本人", "宫中服侍的宫女（转述给了怀庆）", "怀庆（转述给了魏渊）"],
     "whoDoesNotKnow": ["魏渊（直到会面当天；此前暗子已被拔除）"],
     "basis": "explicit", "quotes": Q('q_hq_noappetite', 'q_ignorance', 'q_wei_deny')},
]

# ============================ foreshadows ============================
foreshadows = [
    {"id": "F1", "name": "鸡精罐的存量与「半罐」",
     "setup": "罐子出场（「一个脑袋大小的罐子」）+ 分装动作（「从罐子里倒了些许进瓷瓶」）+ "
              "许七安次日的数量说法（「满满一罐都给了魏公」）",
     "payoff": "怀庆抛出「可本宫听说，魏渊送到母后那里的...鸡精，是半罐」——两个数量对不上",
     "status": "unresolved",
     "unresolvedReason": "区间在「两人不由的沉默了」处结束，没有交代差额从哪来：分装、厨子试做、"
                         "传递过程中的消耗、或消息本身不准，原文都没有写（见 U4/U5）。",
     "basis": "derived", "quotes": Q('q_xu_takes_jar', 'q_bottle', 'q_xu_deny', 'q_half_jar')},
    {"id": "F2", "name": "留给裱裱的那一小瓶（及「传到临安那里」的后果）",
     "setup": "「他其实是有的，还有一小瓶，但不能给怀庆，他得给裱裱留着」+ "
              "他对连锁反应的预判（「迟早传到临安那里」→「到时候裱裱就会像打翻醋坛子的怨妇，把火气撒到许七安头上」）",
     "payoff": None,
     "status": "unresolved",
     "unresolvedReason": "区间内没有发生任何回收：裱裱/临安公主本人没有出场，也没有写她得知此事。"
                         "预测句是许七安的心理，不是已发生的事。",
     "basis": "inferred", "quotes": Q('q_he_has', 'q_linan', 'q_prediction', 'q_biaobiao_noisy'),
     "note": "登记为伏笔的依据是「有明确铺设（留瓶+预判后果）」，不是「出现过」；回收缺失已显式写出。"},
]

notForeshadows = [
    {"id": "NF1", "candidate": "元景帝开头那张没有任何表情的脸",
     "why": "全章只出现一次，没有铺设与回收的两端结构；把它当伏笔就是「一次出现当伏笔」。",
     "quotes": Q('q_emperor_face')},
    {"id": "NF2", "candidate": "鸡精的三种意思（含被屏蔽的那一种）",
     "why": "单次出现的玩笑性释义，后文没有任何回收；它只服务这一段的插科打诨（见 U18）。",
     "quotes": Q('q_three_meanings', 'q_third_meaning')},
    {"id": "NF3", "candidate": "「魏渊是个不会真正发怒的人」→ 两段后「果然，魏渊不再搭理」",
     "why": "这是同一场戏内的即时性格印证（判断与验证相隔两段、无悬念、无后果），"
            "与跨段埋设—回收不是一回事，因此不计为伏笔。",
     "quotes": Q('q_xu_not_roll', 'q_guoran')},
    {"id": "NF4", "candidate": "魏渊被拔除的暗子",
     "why": "它在本区间以「因为」直连成因果项（见 C1），不是先埋设、后回收；"
            "若同时登记为伏笔，同一事实会被因果与伏笔重复计算。",
     "quotes": Q('q_ignorance')},
    {"id": "NF5", "candidate": "皇后叫住魏渊后什么都没说",
     "why": "原文明确写「最后什么都没说」，且区间内没有回收；单次出现，不构成伏笔。",
     "quotes": Q('q_empress_silent')},
    {"id": "NF6", "candidate": "「说不定毒是抹在筷子上的呢。」",
     "why": "玩笑一句，后文没有任何回收（魏渊只是发怒让他滚）。",
     "quotes": Q('q_xu_joke', 'q_wei_angry')},
    {"id": "NF7", "candidate": "作者附言「PS：昨天半夜三更，元气大伤，今天没了。」",
     "why": "属于文本但不在故事层，不参与情节、因果与伏笔。",
     "quotes": Q('q_ps')},
]

# ============================ worldSettings ============================
worldSettings = [
    {"id": "W1", "kind": "place", "name": "皇后的宫殿（后宫之主）", "placeState": "arrived",
     "quote": Q('q_arrive')[0]["quote"], "quotes": Q('q_arrive'),
     "explain": "有到达与进入动作：「通传之后，他进入殿内」。这条设定约束了行动——后宫要通传才能进，"
                "所以会面不可能避开旁人，与「这些事儿，不可能当众说出口」相扣。",
     "basis": "explicit"},
    {"id": "W2", "kind": "place", "name": "浩气楼（打更人衙门内）", "placeState": "arrived",
     "quote": Q('q_well')[0]["quote"], "quotes": Q('q_well', 'q_eunuch_receive'),
     "explain": "有到达动作：「返回衙门，进入浩气楼」；次日「魏渊在浩气楼接见了宦官」。"
                "它是本区间所有命令与资源交接的发生地（许七安被「魏公有请」带到这里，谢礼也送到这里），"
                "解释了为什么鸡精、命令、赏赐都在这一个点上交换。",
     "basis": "explicit"},
    {"id": "W3", "kind": "place", "name": "皇宫内廷的二十四座宫殿与储秀宫", "placeState": "mentioned",
     "quote": Q('q_palace_24')[0]["quote"], "quotes": Q('q_palace_24'),
     "explain": "只作为背景规模被叙述，**没有任何人到达、驻守或进入某座具体宫殿的动作**，"
                "所以记 mentioned 而不是 arrived。它的作用是解释「元景帝的后宫一点都不热闹」这一处境，"
                "与「父皇早已不来后宫了」互为背景。",
     "basis": "explicit"},
    {"id": "W4", "kind": "place", "name": "茶室（浩气楼内的房间）", "placeState": "mentioned",
     "quote": "见茶室无人", "quotes": Q('q_xu_takes_jar'),
     "explain": "只在「无人」这个状态里被提到一次，原文没有写许七安「进入」茶室；"
                "但它约束了动作：他先确认茶室无人，才敢取出玉石小镜倒出罐子——说明这个取物动作不宜当众。",
     "basis": "explicit",
     "note": "本条的 quote 取的是「见茶室无人」这一子串（整句见 quotes 里的完整引文）。"},
    {"id": "W5", "kind": "item", "name": "鸡精（脑袋大小的罐子装）",
     "quote": Q('q_xu_takes_jar')[0]["quote"],
     "itemStates": ["hold", "transfer", "use"],
     "stateVerbsOriginal": {"hold": "取出／摔了出来／接住", "transfer": "还给（暂时）／没接／那才是我的",
                            "use": "让厨子去煮碗面／魏公刚送了秘制的配方过来"},
     "quotes": Q('q_xu_takes_jar', 'q_yours', 'q_wei_orders_noodle', 'q_wei_sent_recipe'),
     "explain": "四态分开写：hold＝许七安从镜中取出并接住；transfer＝罐子先还给许七安又被留作魏渊所有"
                "（「那才是我的」），随后送到皇后处；use＝用于煮面试味、并进皇后膳房的菜；lose＝本区间**没有**丢失动作。",
     "basis": "explicit",
     "note": "stateVerbsOriginal 里是**原文动词的逐个摘录**（斜杠是我加的分隔符，不是原文）；"
             "本栏照抄原词，未改写成现代汉语动词。完整句见 quotes[]。"},
    {"id": "W6", "kind": "item", "name": "玉石小镜",
     "quote": Q('q_xu_takes_jar')[0]["quote"], "itemStates": ["hold", "use"],
     "stateVerbsOriginal": {"hold": "取出玉石小镜", "use": "轻扣背面"},
     "quotes": Q('q_xu_takes_jar'),
     "explain": "许七安随身携带的储物法器：取出与开启都有具体动作（「取出」「轻扣背面」），"
                "且必须在无人处使用——它决定了这批鸡精「怎么到场」以及为什么交货要避人。",
     "basis": "explicit"},
    {"id": "W7", "kind": "item", "name": "瓷瓶（分装用）",
     "quote": Q('q_bottle')[0]["quote"], "itemStates": ["hold", "transfer", "use"],
     "stateVerbsOriginal": {"hold": "从格子里取出一枚瓷瓶", "transfer": "递给许七安／摇摇头，没接",
                            "use": "从罐子里倒了些许进瓷瓶"},
     "quotes": Q('q_bottle', 'q_yours'),
     "explain": "从魏渊的格子取出，转手给许七安分装，最后魏渊没有接回——归属落在许七安手里。"
                "这条设定解释了次日「他其实是有的」这句话里那个「有」的物证来源（但**不证明是同一只瓶**，见 R5）。",
     "basis": "explicit"},
    {"id": "W8", "kind": "item", "name": "金银玉器",
     "quote": Q('q_next_day')[0]["quote"], "itemStates": ["transfer"],
     "stateVerbsOriginal": {"transfer": "带着一批金银玉器来到打更人衙门"},
     "quotes": Q('q_next_day'),
     "explain": "从皇后宫流向打更人衙门的谢礼，方向由「带着一批金银玉器来到打更人衙门」写明。**原文没有写魏渊收没收、"
                "也没有写数量与价值**，所以只登记 transfer 这一态，不写 hold。",
     "basis": "explicit"},
    {"id": "W9", "kind": "rule", "name": "进食前由他人先尝（试毒）",
     "quote": Q('q_wei_waits')[0]["quote"], "institution": "executed",
     "quotes": Q('q_taste_poison', 'q_wei_waits', 'q_they_tasted', 'q_taste_it'),
     "explain": "有执行动作、不是只有条文：魏渊要许七安「你吃一口，帮我试毒」，并且「等待片刻，确认……"
                "魏渊这才动筷子」（完整句见 quotes[]）；皇后宫里的菜同样由宫女先试（「她们已经试过了」）再劝食。"
                "它解释了**谁不能先动筷子**：魏渊在别人尝过前不吃，许七安则没有拒绝的余地（原文只写他用另一头吃了一口）；"
                "也解释了为什么皇后那桌菜可以先被宫女评价味道。",
     "basis": "explicit",
     "note": "按 prompt 的三分法，本区间没有诏/令/法依据（不是 declared），只有执行动作，故记 executed；"
             "它是常制还是这一次的做法，区间内无法判定（见 U13）。"},
]

notWorldSettings = [
    {"id": "NW1", "candidate": "容貌与服饰描写（皇后「年近四十，风华依旧」、魏渊「鬓角的霜白」、"
                              "怀庆「避寒的大氅」「雪山的白莲」等）",
     "why": "装饰性形容，不约束任何人的行动、资源或后果。注意其中有一处**比较性叙述**"
            "（「与她母亲年轻时迥异」）也只是外貌对比，没有制度含义。",
     "quotes": Q('q_empress_beauty', 'q_wei_face', 'q_wei_temples', 'q_hq_dress', 'q_hq_unlike_mother', 'q_hq_lotus')},
    {"id": "NW2", "candidate": "勾栏／教坊司／养生堂",
     "why": "只作为去处与捐款对象各出现一次，没有写出价格、准入、禁令之类的规则；"
            "把它们扩成地点条目就是「没有依据就扩出地图」。", "quotes": Q('q_xu_treat', 'q_donation')},
    {"id": "NW3", "candidate": "「这些事儿，不可能当众说出口」",
     "why": "它是叙述层给出的处境约束，但**不是诏/令/法**，也没有落到可命名的制度上；"
            "按 prompt 要求的三分法无法诚实填 institution（declared 无据、executed 无执行动作、misunderstood 是人物理解），"
            "故不登记为世界设定，而作为误会的直接原因记在 C2。", "quotes": Q('q_public_impossible')},
    {"id": "NW4", "candidate": "「父皇……每日只想着修仙长生」",
     "why": "这是怀庆视角下的人物评述，解释了他为何「早已不来后宫」，但区间内没有写出任何修仙制度、"
            "禁令或资源规则，不构成可执行的设定。", "quotes": Q('q_emperor_habit')},
    {"id": "NW5", "candidate": "鸡精的化学成分说明（味精、鸟苷酸、相辅相成）",
     "why": "属于术语解释与玩笑层，不影响任何人的行动或后果；本候选只在物件项里记它的用途。",
     "quotes": Q('q_recipe_mix', 'q_three_meanings')},
    {"id": "NW7", "candidate": "宫女「在皇宫住了这么多年，替主子们试过各种各样的山珍海味」",
     "why": "这是对宫女资历的叙述，服务的是「今天的滋味前所未有」这一对比；"
            "它**不构成制度**（没写试吃的规矩），所以只作为 T7 obstacle 的旁证，不登记为世界设定。"
            "真正的试毒执行动作另见 W9。",
     "quotes": Q('q_years_tasting', 'q_unprecedented')},
    {"id": "NW6", "candidate": "「他一个没有成家的浪荡子……就会有蛋蛋的忧伤」",
     "why": "一般处境的自嘲式说明，不是这个世界的规则或约束；它只在 T5 的 cost 栏作为间接证据被用到。",
     "quotes": Q('q_no_money_woe')},
]

# ============================ themeReadings ============================
themeReadings = [
    {"id": "TH1", "perspective": "以「信息在谁手里」为轴读这一章：每一次关系的错位都来自某个人手里少一条消息。",
     "support": [
         {"what": "皇后以为魏渊知情不来，实际是他安插的暗子被拔除，且「不可能当众说出口」",
          "quotes": Q('q_empress_ask', 'q_ignorance', 'q_public_impossible')},
         {"what": "许七安以为否认就能了事，而怀庆手里已有「半罐」这条消息",
          "quotes": Q('q_xu_deny', 'q_half_jar', 'q_silence')}],
     "counter": [
         {"what": "反例一：本章真正被解决的事（皇后吃饭）不靠信息对称，靠的是味道本身；宫女、皇后都不需要知道鸡精从哪来。",
          "quotes": Q('q_soup', 'q_hungry')},
         {"what": "反例二：信息缺失并没有导致冲突爆发——两处错位都以「什么都没说」「沉默了」收场，"
                  "把它读成「信息差必然出事」是超出文本的。",
          "quotes": Q('q_empress_silent', 'q_silence')}],
     "basis": "inferred",
     "note": "这是解释层，不是事实层；两个反例都来自同一区间，且与支持项同等具体。"},
    {"id": "TH2", "perspective": "以「说不出口的关系如何表达」为轴：魏渊不能解释的事，改用一份吃的来表达。",
     "support": [
         {"what": "他不能说明暗子与误会（「不可能当众说出口」），却在告辞前叮嘱「皇后少喝些茶，对脾胃不好」；"
                  "他索取鸡精时的理由也全是皇后的身体。",
          "quotes": Q('q_public_impossible', 'q_tea_advice', 'q_wei_request')},
         {"what": "皇后那边的转折点是一句「听是魏渊的安排」——她是因为这份安排才动勺的。",
          "quotes": Q('q_hears_wei')}],
     "counter": [
         {"what": "反例一：魏渊的公开理由始终是差事口吻（奉命探望、皇后食欲不佳），"
                  "本区间没有一句写他这次是出于私情；把它读成情意是读者的投射。",
          "quotes": Q('q_meta_speech', 'q_wei_explain_hq')},
         {"what": "反例二：皇后当场问的是「是他让你来的？」——她把这趟探望归给皇帝，"
                  "而不是归给魏渊本人；她的迟疑也可以读成对「被差遣来的关心」的失望。",
          "quotes": Q('q_empress_ask')}],
     "basis": "inferred",
     "note": "两条主题并列写出，不合并成「唯一真相」；也可只把它们当作两种可选读法。"},
]

# ============================ speechVsNarration ============================
speechVsNarration = [
    {"id": "V1", "text": "「没了。」……「满满一罐都给了魏公」", "kind": "speech", "speaker": "许七安",
     "why": "人物话，且被叙述层部分否掉——「他其实是有的，还有一小瓶」。另：叙述层从未写罐子原来是满的。",
     "quotes": Q('q_xu_deny', 'q_he_has')},
    {"id": "V2", "text": "「可本宫听说，魏渊送到母后那里的...鸡精，是半罐。」", "kind": "speech", "speaker": "怀庆公主",
     "why": "「听说」自标转述，来源未写；不能当叙述事实（见 U3）。",
     "quotes": Q('q_half_jar')},
    {"id": "V3", "text": "「近来公务繁忙，不知皇后病了。」", "kind": "speech", "speaker": "魏渊",
     "why": "人物话；但叙述层另有「他确实不知道皇后生病了」与之方向一致——**这是少数被叙述层背书的否认**，"
            "与一般「人物话≠事实」的例子要区别对待；被否掉的是「公务繁忙」这一半，区间内没有它的证据。",
     "quotes": Q('q_wei_deny', 'q_ignorance')},
    {"id": "V4", "text": "「陛下说皇后近来食欲不佳，让微臣过来瞧瞧。」", "kind": "speech", "speaker": "魏渊",
     "why": "转述皇帝口信，区间内没有皇帝的正面确认；旁证是怀庆视角的叙述层说他「通常都是派人过来探望了事」。",
     "quotes": Q('q_meta_speech', 'q_emperor_habit')},
    {"id": "V5", "text": "「已经痊愈。」", "kind": "speech", "speaker": "皇后",
     "why": "自称痊愈；同一段叙述层仍写她「清减了许多」，随后又说她食欲不佳。两处并存，不能只取一句当病情结论。",
     "quotes": Q('q_empress_cured', 'q_empress_thin', 'q_hq_noappetite')},
    {"id": "V6", "text": "「都是宋师兄和采薇姑娘的功劳。」", "kind": "speech", "speaker": "许七安",
     "why": "人物话；叙述层写的是「褚采薇和宋卿的劳动成果都在这里了」，与「功劳」不完全是同一回事，故不写成事实。",
     "quotes": Q('q_xu_credit', 'q_reserved')},
    {"id": "V7", "text": "「吃的比以往都多，比身子好时还多。」", "kind": "speech", "speaker": "皇后宫里的公公",
     "why": "人物报告；它与 T7 的叙述层（喝完汤、要饭）方向一致，才被采信为结果证据之一。",
     "quotes": Q('q_eunuch_report', 'q_finish_soup')},
    {"id": "V8", "text": "「说不定毒是抹在筷子上的呢。」", "kind": "speech", "speaker": "许七安",
     "why": "玩笑话，被魏渊以「滚出去」回应；不构成任何事实主张。",
     "quotes": Q('q_xu_joke', 'q_wei_angry')},
    {"id": "V9", "text": "「皇后是怀庆的生母，怀庆托魏渊找我要鸡精....」", "kind": "thought", "speaker": "许七安（内心推断）",
     "why": "这是他的推断，不是叙述事实：本区间没有写怀庆托付过魏渊。",
     "quotes": Q('q_xu_realize')},
    {"id": "V12", "text": "「怀庆这么八卦的吗？这种小事也到处乱说....」", "kind": "thought", "speaker": "许七安（内心抱怨）",
     "why": "内心话，且带情绪判断（「八卦」「到处乱说」）。事实层只有「听怀庆说」这一句转述，"
            "传播范围与方式都没有写；不能据此认定怀庆在四处宣扬。",
     "quotes": Q('q_xu_gossip', 'q_wei_listen')},
    {"id": "V10", "text": "「到时候裱裱就会像打翻醋坛子的怨妇，把火气撒到许七安头上。」",
     "kind": "narration-of-thought", "speaker": "许七安（叙述层记录的心理预判）",
     "why": "以「到时候」标明**未发生**；它是对后果的预判，不是事件，也不能当作临安公主的性格事实。",
     "quotes": Q('q_prediction', 'q_biaobiao_noisy')},
    {"id": "V11", "text": "「她们已经试过了，味道与众不同，令人难忘。」", "kind": "narration", "speaker": "（叙述层）",
     "why": "这是叙述层写宫女的试吃与评价，是本区间里少数对「鸡精好吃」的**非人物台词**背书。",
     "quotes": Q('q_they_tasted', 'q_unprecedented')},
]

# ============================ sceneBeats ============================
sceneBeats = [
    {"id": "B1", "range": [627871, 627916], "what": "元景帝望着魏渊的背影，脸上没有任何表情（全章唯一一次写他）",
     "quotes": Q('q_emperor_face')},
    {"id": "B2", "range": [627918, 628028], "what": "背景：后宫二十四座宫殿、储秀宫多年不纳新人；魏渊通传后进入皇后寝殿",
     "quotes": Q('q_palace_24', 'q_arrive')},
    {"id": "B3", "range": [628030, 628283], "what": "皇后清减；她先问「魏公怎么来了」，魏渊问病、再传皇帝口信",
     "quotes": Q('q_empress_thin', 'q_empress_greet', 'q_wei_asks', 'q_meta_speech')},
    {"id": "B4", "range": [628285, 628357], "what": "皇后追问是否知情；魏渊犹豫后否认",
     "quotes": Q('q_empress_ask', 'q_wei_hesitate', 'q_wei_deny')},
    {"id": "B5", "range": [628359, 628471], "what": "皇后称乏；魏渊叮嘱少喝茶后告退；她喊住他，而他背对着没有回头",
     "quotes": Q('q_empress_tired', 'q_tea_advice', 'q_empress_calls', 'q_empress_stops', 'q_wei_no_turn')},
    {"id": "B6", "range": [628473, 628544], "what": "皇后欲言又止、什么都没说；千言万语魏渊看不到",
     "quotes": Q('q_empress_silent', 'q_eyes')},
    {"id": "B7", "range": [628546, 628654], "what": "魏渊离开宫殿；叙述层揭示：暗子被拔除所以魏渊真不知情，皇后不知此事，只能任由误会",
     "quotes": Q('q_leave_palace', 'q_ignorance', 'q_empress_unknowing', 'q_public_impossible')},
    {"id": "B8", "range": [628656, 629137], "what": "宫道上遇到怀庆公主：她施礼应了一声，魏渊作揖还礼并解释来意，魏渊愕然追问后她提出许七安的秘方",
     "quotes": Q('q_hq_approaches', 'q_hq_greet', 'q_hq_um', 'q_wei_salute', 'q_wei_explain_hq', 'q_hq_what', 'q_hq_recipe')},
    {"id": "B9", "range": [629150, 629373], "what": "许七安请同僚听曲；离开勾栏后被骑马的铜锣拦下传话，两位同僚告辞继续巡街",
     "quotes": Q('q_xu_treat', 'q_tongluo', 'q_boyi', 'q_others_leave')},
    {"id": "B10", "range": [629424, 629704], "what": "浩气楼：魏渊索取鸡精；许七安腹诽消息走漏、取出罐子，并说明留了一小瓶给褚采薇",
     "quotes": Q('q_wei_request', 'q_xu_modest', 'q_xu_gossip', 'q_xu_takes_jar', 'q_reserved')},
    {"id": "B11", "range": [629706, 629919], "what": "魏渊嗅后皱眉；许七安科普鸡精；魏渊让厨子煮面，许七安意会跟出去",
     "quotes": Q('q_wei_smell_frown', 'q_xu_science', 'q_wei_orders_noodle', 'q_xu_understands')},
    {"id": "B12", "range": [629940, 630165], "what": "面端来后先试毒；许七安用另一头吃了一口；玩笑与「滚出去」",
     "quotes": Q('q_noodle', 'q_taste_poison', 'q_xu_tasted', 'q_wei_angry')},
    {"id": "B13", "range": [630167, 630248], "what": "魏渊不再搭理、低头吃面；喝汤时眼睛亮起",
     "quotes": Q('q_guoran', 'q_eyes_light')},
    {"id": "B14", "range": [630250, 630470], "what": "许七安问「怎么样」；魏渊给出评价、分装、递还时没接，把瓷瓶留给许七安（「那才是我的」）",
     "quotes": Q('q_how', 'q_wei_praise', 'q_bottle', 'q_hand_back', 'q_yours')},
    {"id": "B15", "range": [630492, 630877], "what": "黄昏：宫女以多年试吃经验力荐，皇后抗拒后被劝动，喝完汤并要饭",
     "quotes": Q('q_court_food', 'q_porridge', 'q_years_tasting', 'q_hears_wei', 'q_finish_soup', 'q_hungry')},
    {"id": "B16", "range": [630879, 631111], "what": "次日：皇后宫送金银玉器；公公报告进食情况；魏渊由衷的笑了",
     "quotes": Q('q_next_day', 'q_eunuch_report', 'q_wei_smiles')},
    {"id": "B17", "range": [631113, 631364], "what": "午后：怀庆索要鸡精；许七安否认并称满满一罐都给了魏公",
     "quotes": Q('q_hq_summon', 'q_hq_yearn', 'q_xu_deny')},
    {"id": "B18", "range": [631366, 631471], "what": "叙述层写他其实还有一小瓶、要留给裱裱",
     "quotes": Q('q_he_has', 'q_prediction')},
    {"id": "B19", "range": [631473, 631655], "what": "怀庆抛出「半罐」；两人沉默（本单元收束）",
     "quotes": Q('q_half_jar', 'q_xu_startled', 'q_silence')},
]

# ============================ unknowns ============================
unknowns = [
    {"id": "U1", "what": "元景帝为什么拔掉魏渊安插在皇后宫附近的暗子",
     "detail": "区间内只给事实（被拔除）与后果（魏渊因此不知情），不给理由，也没有人物议论过动机。本候选不做推断。",
     "quotes": Q('q_ignorance')},
    {"id": "U2", "what": "「任由皇后误会」里的误会具体是什么",
     "detail": "她问的是「是他让你来的？魏公不知本宫病了吗」——可读作「你知情却不来」，也可读作「你只是奉命而来」。"
               "原文只写「误会」二字，没有写内容。", "quotes": Q('q_public_impossible', 'q_empress_ask')},
    {"id": "U3", "what": "怀庆听说的「半罐」从何而来",
     "detail": "可能的来源至少三种：魏渊一方分装、厨子试做消耗、或消息本身不准。「本宫听说」没有给来源；"
               "区间内唯一写明的减量动作是「从罐子里倒了些许进瓷瓶」，「些许」与「半罐」量级不符，不能当解释。",
     "quotes": Q('q_half_jar', 'q_bottle')},
    {"id": "U4", "what": "许七安说的「满满一罐」是否属实",
     "detail": "叙述层**从未**写过罐子是满的（首次出场只写「一个脑袋大小的罐子」）；这句是人物话，"
               "同段叙述层还否掉了他的一半说法（他其实还有一小瓶）。", "quotes": Q('q_xu_deny', 'q_xu_takes_jar', 'q_he_has')},
    {"id": "U5", "what": "罐子原来有多少、送到皇后处剩多少",
     "detail": "区间内没有数量描写，只有容器尺寸（脑袋大小）与「些许」这类模糊量词；因此 T4 的 cost 写 null。",
     "quotes": Q('q_xu_takes_jar', 'q_half_jar')},
    {"id": "U6", "what": "两处（乃至三处）「一小瓶」是不是同一瓶",
     "detail": "「他只给褚采薇留了一小瓶鸡精」与「他其实是有的，还有一小瓶，但不能给怀庆，他得给裱裱留着」"
               "归属对象不同，"
               "加上魏渊分装用的瓷瓶，共三处小容器；原文没有指明对应关系。见 R5。",
     "quotes": Q('q_reserved', 'q_he_has', 'q_bottle')},
    {"id": "U7", "what": "魏渊把整罐留下的用途",
     "detail": "他只说了归属（「那才是我的」），没有说拿它做什么：自用、留存、另送都无据。", "quotes": Q('q_yours')},
    {"id": "U8", "what": "元景帝那张「没有任何表情」的脸意味着什么",
     "detail": "全章唯一一次写他，没有后续呼应，也没有人物对此作出反应。本候选不赋予它情绪或动机。",
     "quotes": Q('q_emperor_face')},
    {"id": "U9", "what": "怀庆从「似乎并不担心」到次日追讨味道的转变原因",
     "detail": "原文没有解释；「似乎」本身标记了这是外部观察。已按状态变化登记（S6，inferred）而非因果（R2）。",
     "quotes": Q('q_hq_notworried', 'q_hq_yearn')},
    {"id": "U10", "what": "「安插在附近的暗子」是谁安插的",
     "detail": "原文省略施动者。读作魏渊的情报渠道，是从「他确实不知道皇后生病了，因为安插在附近的暗子，"
               "前段时间被元景帝拔除」这个解释关系推出来的，不是叙述明写；"
               "若它是别人的暗子，C1 就要改写。", "quotes": Q('q_ignorance')},
    {"id": "U11", "what": "魏渊那句「听说皇后病了？」的「听说」从哪来",
     "detail": "叙述层写他确实不知道她病了，皇帝口信里也只有「食欲不佳」；这句「听说」的来源没有交代，"
               "与叙述层的「确实不知道」之间存在措辞张力（原文未解释）。", "quotes": Q('q_wei_deny', 'q_meta_speech')},
    {"id": "U12", "what": "怀庆说的「你那配方似乎有所改良」指什么改动",
     "detail": "全章没有交代改动内容；许七安只把功劳归给宋卿与褚采薇，没说改了什么。",
     "quotes": Q('q_hq_improved', 'q_xu_credit')},
    {"id": "U13", "what": "「先让人试毒」是常制还是这一次的做法",
     "detail": "本区间有两个例子（这碗面、皇后宫的菜），但两个例子不足以确认普遍性；"
               "W9 按 executed 登记是因为有执行动作，不代表它是成文法。", "quotes": Q('q_taste_poison', 'q_they_tasted')},
    {"id": "U14", "what": "那批金银玉器是否被收下、是谁的意思",
     "detail": "原文只写「皇后宫里的太监带着一批金银玉器来到打更人衙门」与「魏渊在浩气楼接见了宦官」；"
               "礼物的去向、是否被接受、是否为皇后本人所派，都没有写。",
     "quotes": Q('q_next_day', 'q_eunuch_receive')},
    {"id": "U15", "what": "「小铜锣」指谁；「裱裱」与临安公主的对应",
     "detail": "「小铜锣」在本区间出现一次（试毒段），按上下文（面是他捧上来的）读作许七安；"
               "同章另有「一个骑马的铜锣」，同词两指。「裱裱」在本区间没有与「临安」同句直连"
               "（「临安公主」出现在后一段），把它读作许七安对临安公主的私下称呼属跨句推断。",
     "quotes": Q('q_wei_waits', 'q_linan_mab', 'q_linan')},
    {"id": "U16", "what": "本章时间标记之间的绝对关系",
     "detail": "「一刻钟的时间后」「黄昏。」「次日，卯时刚过」「午后刚过」都是相对标记；"
               "原文没有给绝对日期，也没有交代魏渊探病与怀庆在宫道相遇之间隔了多久。",
     "quotes": Q('q_dusk', 'q_next_day')},
    {"id": "U17", "what": "「鳝饿有鲍」「蛋蛋的忧伤」「把生命的传承工作给做完」的确切所指",
     "detail": "本区间有几处明显的谐音/双关，尺度与具体所指靠上下文推断；本候选不为它们补写情节内容，"
               "T5 的 result 只引叙述层的状态词「无比满足」。", "quotes": Q('q_left_satisfied', 'q_life_work')},
    {"id": "U19", "what": "怀庆是如何、向谁说起许七安配方的",
     "detail": "区间内只有魏渊一句「听怀庆说」与许七安一句内心抱怨「这种小事也到处乱说」；"
               "传播对象、场合、范围都没有写。本候选不据许七安的情绪话认定她「到处说」。",
     "quotes": Q('q_wei_listen', 'q_xu_gossip')},
    {"id": "U20", "what": "魏渊「久病之后，若在绝食，身体会落下病根」这句判断的依据",
     "detail": "这是他对怀庆说的推测（条件句「若在绝食」），不是诊断结论；"
               "皇后的实际病情、是否绝食，区间内只由宫女「没怎么吃东西」与她本人「已经痊愈」两句支撑。",
     "quotes": Q('q_wei_worry', 'q_hq_noappetite', 'q_empress_cured')},
    {"id": "U18", "what": "「叫**精」中被屏蔽的字",
     "detail": "原文该处是「**」，属文本自身的屏蔽；本候选按原文保留，不补字、不猜测。",
     "quotes": Q('q_three_meanings')},
]

# ============================ selfCritique ============================
selfCritique = [
    {"id": "SC1", "risk": "T1 的 objective 可能被读成「元景帝关心皇后」",
     "why": "原文对他只有一句「脸上没有任何表情」，正面动机完全没有写。我仍然这么判断，是因为"
            "「陛下说皇后近来食欲不佳，让微臣过来瞧瞧」加上怀庆视角的「通常都是派人过来探望了事」"
            "足以支撑「他派了人」这件事；但 objective 我只写到「把口信带到、当面探视」，没有写关心、没有写夫妻情分。"},
    {"id": "SC2", "risk": "T3 的 cost 与 T4 的 cost 都偏弱：一个是我对器物转移的归类，一个直接写 null",
     "why": "本区间没有金钱、人情或处罚性质的支出描写。我宁可让 T4 空着并在 costNote 里说明"
            "「罐子原有量未知所以不可量化」，也不编一个「付出了满满一罐」——那会把人物话当成账目。"},
    {"id": "SC3", "risk": "F1／F2 可能被读成「一次出现当伏笔」",
     "why": "两条都写明了铺设的构成（F1 是罐子出场＋分装＋数量说法；F2 是留瓶＋后果预判），"
            "并显式标了 unresolved 与「区间内没有回收」。若复核认为同章内的两处提法不足以称为伏笔，"
            "应把它们降为 notForeshadows，而不是补一个回收。"},
    {"id": "SC4", "risk": "T5 整条任务可能被读成无关的插科打诨",
     "why": "它在本章功能上确实与主线无因果（已写成 R3 拒绝连边），但五元组本身在原文里有直证"
            "（弥补、捐款五两、自掏腰包、无比满足），所以保留为独立任务，并且把 obstacle 老实写成 null。"},
    {"id": "SC5", "risk": "把 V3 单列为「被叙述层背书的否认」可能显得为人物开脱",
     "why": "判据是原文两句的直接对照：「他确实不知道皇后生病了」是叙述层，「近来公务繁忙，不知皇后病了」是人物话。"
            "我只主张后半句（公务繁忙）无据，而这句被我写进了 speechVsNarration 的 why 里，没有扩写。"},
]

# ============================ coverage ============================
all_quotes = []
def _collect(o):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            all_quotes.append((o["start"], o["end"]))
        for v in o.values():
            _collect(v)
    elif isinstance(o, list):
        for v in o:
            _collect(v)
_collect({"tasks": tasks, "causeEdges": causeEdges, "states": states, "knowledgeDiffs": knowledgeDiffs,
          "foreshadows": foreshadows, "notForeshadows": notForeshadows, "worldSettings": worldSettings,
          "notWorldSettings": notWorldSettings, "themeReadings": themeReadings,
          "speechVsNarration": speechVsNarration, "sceneBeats": sceneBeats, "unknowns": unknowns,
          "meta": [ANCHORS[k] for k in ANCHORS]})

para_spans = []  # 切片内非空段（相对切片偏移）
_c = 0
for _l in SEG.split('\n'):
    if _l.strip():
        para_spans.append((_c, _c + len(_l)))
    _c += len(_l) + 1

touched = set()
for a, b in all_quotes:
    ra, rb = a - S, b - S
    for i, (ps, pe) in enumerate(para_spans):
        if ra < pe and rb > ps:
            touched.add(i)
uncovered = [i for i in range(len(para_spans)) if i not in touched]
total_chars = sum(b - a for a, b in para_spans)
covered_chars = sum(b - a for i, (a, b) in enumerate(para_spans) if i in touched)

coverageDeclaration = {
    "nonEmptyParagraphs": len(para_spans),
    "paragraphsTouchedByAtLeastOneQuote": len(touched),
    "uncoveredParagraphs": uncovered,
    "paragraphCoverageRatio": round(len(touched) / len(para_spans), 4),
    "charCoverageRatio": round(covered_chars / total_chars, 4),
    "uncoveredItems": [
        "非空段 #0：标题行「第一百七十四章 鸡精」——单元标题，不属情节",
        "非空段 #34 / #70 / #82：场景分隔符「.....」——无内容的分场标记",
        "非空段 #103：结尾分隔线「------------」——排版分隔",
        "说明：本表分母把上述分隔行也算作「非空段」（它们 strip 后确实非空）；"
        "若只统计有内容的段，内容段覆盖为 99/99。作者附言「PS：...」那一段**已被引用**（NF7），不在未覆盖名单里。",
    ],
    "uncoveredParagraphTexts": [
        {"para": 0, "text": "第一百七十四章 鸡精", "why": "单元标题"},
        {"para": 34, "text": ".....", "why": "场景分隔符"},
        {"para": 70, "text": ".....", "why": "场景分隔符"},
        {"para": 82, "text": ".....", "why": "场景分隔符"},
        {"para": 103, "text": "------------", "why": "排版分隔线"},
    ],
    "note": "覆盖数是**引文触达的段数**，不是「读懂了多少」；引文定位正确也不等于语义已核验。"
            "分母为切片内 strip 后非空的 104 段。",
}

# ---- 组装 ----
out = {
    "schemaVersion": "castline-read-candidate/1",
    "task": "read:dafeng:L2:0174",
    "agent": "w-dafeng-0",
    "role": "READER（原文精读工作者）",
    "book": "dafeng",
    "bookTitle": "大奉打更人",
    "lane": 2,
    "unitIndex": 174,
    "unitHead": "第一百七十四章 鸡精",
    "source": {
        "path": DOCS,
        "sourceHash": SRC_HASH,
        "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
        "segmentSha256": seg_sha,
        "segmentSha256Scope": "docs[0].text[start:end] 的 UTF-8 字节 sha256（另起字段，未覆盖 sourceHash）",
        "range": [S, E],
        "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
        "sliceStartsWithUnitHead": True,
        "sliceChars": len(SEG),
        "nonEmptyParagraphs": len(para_spans),
        "docsJsonTopLevel": "list（不是 {'docs': [...]}）——本候选按实测结构取 docs[0].text",
        "note": "全部引文的 start/end 都是相对 docs[0].text 全文的绝对 codepoint 偏移，不是相对切片。"
                "自检：text[start:end] == quote 逐字成立，且落在区间内；构建期对每条引文都做了断言。",
    },
    "semanticReview": "not-performed",
    "semanticReviewNote": "本候选只做引文定位的机器可复算（逐字/偏移/区间/出现次数/首现位置/段号）"
                          "与本人通读后的语义判断；**不声称**任何 semanticReview 完成，也不声称独立复核。"
                          "引文定位正确 ≠ 语义已核验。",
    "basisLegend": BASIS,
    "quotePolicy": {
        "bracketConvention": "本候选里 **只有 quotes[] 里的 `quote` 字段被构建期断言为逐字原文**；"
                             "散文字段里的「」既可能是原文摘句、也可能是我给某个读法起的标签（如「表情=态度」）。"
                             "凡属后者，正文都用「可读作」「即」等词标明是我的归纳，不冒充原文。",
        "withinTaskUniqueness": "同一任务五栏（objective/obstacle/action/result/cost）的 quotes 互不重复，构建期脚本断言通过。",
        "acrossTasksReuse": "允许跨任务复引同一句作为不同断言的证据（同一事实可以同时是 A 的代价与 B 的结果）；"
                            "唯一的硬约束是任务内不复用。",
    },
    "tasks": tasks,
    "causeEdges": causeEdges,
    "rejectedEdges": rejectedEdges,
    "states": states,
    "knowledgeDiffs": knowledgeDiffs,
    "foreshadows": foreshadows,
    "notForeshadows": notForeshadows,
    "worldSettings": worldSettings,
    "notWorldSettings": notWorldSettings,
    "themeReadings": themeReadings,
    "speechVsNarration": speechVsNarration,
    "sceneBeats": sceneBeats,
    "unknowns": unknowns,
    "selfCritique": selfCritique,
    "coverageDeclaration": coverageDeclaration,
}

# 落盘前的最终断言：候选里每一条 quote 都必须在全文里逐字命中且落在区间内
def _final_check(o, path="root"):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o and "sourceHash" in o:
            q, a, b = o["quote"], o["start"], o["end"]
            assert T[a:b] == q, "引文不逐字成立 @%s: %r" % (path, q[:30])
            assert S <= a and b <= E, "引文越界 @%s" % path
            assert o["sourceHash"] == SRC_HASH, "引文 sourceHash 不符 @%s" % path
        for k, v in o.items():
            _final_check(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _final_check(v, "%s[%d]" % (path, i))
_final_check(out)

# worldSettings 每条必须有 kind/name/quote/explain，且 quote 是区间内逐字原文
for _w in worldSettings:
    for _f in ("kind", "name", "quote", "explain"):
        assert _f in _w and _w[_f], "worldSettings %s 缺 %s" % (_w.get("id"), _f)
    assert isinstance(_w["quote"], str), "worldSettings %s 的 quote 不是字符串" % _w["id"]
    _i = T.find(_w["quote"])
    assert _i >= 0 and S <= _i and _i + len(_w["quote"]) <= E, \
        "worldSettings %s 的 quote 不是区间内原文：%r" % (_w["id"], _w["quote"][:30])
    assert _w["kind"] in ("rule", "place", "item"), "worldSettings %s kind 非法" % _w["id"]
    if _w["kind"] == "place":
        assert _w.get("placeState") in ("arrived", "mentioned"), "place %s 缺 placeState" % _w["id"]
    if _w["kind"] == "item":
        assert _w.get("itemStates") and set(_w["itemStates"]) <= {"hold", "transfer", "use", "lose"}, \
            "item %s 的 itemStates 非法" % _w["id"]
    if _w["kind"] == "rule":
        assert _w.get("institution") in ("declared", "executed", "misunderstood"), \
            "rule %s 缺 institution" % _w["id"]

# themeReadings：每条必须三件齐全，最多 2 条
assert len(themeReadings) <= 2, "themeReadings 超过 2 条"
for _th in themeReadings:
    assert _th.get("perspective") and _th.get("support") and _th.get("counter"), \
        "themeReadings %s 缺 perspective/support/counter" % _th.get("id")

# 必需分区
for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    assert k in out, "缺分区 %s" % k

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("OK 引文锚点 %d 条；引文对象 %d 个；非空段 %d；被引文触达 %d；未触达段 %s" % (
    len(ANCHORS), len(all_quotes), len(para_spans), len(touched), uncovered))
print("segmentSha256 =", seg_sha)
print("wrote", OUT)
