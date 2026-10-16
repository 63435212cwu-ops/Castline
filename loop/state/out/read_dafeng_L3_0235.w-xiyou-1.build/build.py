# -*- coding: utf-8 -*-
"""生成 read:dafeng:L3:0235 候选。

工作目录：/Users/carmen/Desktop/星系
输出：    loop/state/out/read_dafeng_L3_0235.candidate.json

所有引文偏移由 docs[0].text.find(锚点) 现算，没有任何一条 start/end 是手写的。
运行：   python3 -B -s loop/state/out/read_dafeng_L3_0235.w-xiyou-1.build/build.py
"""
import hashlib
import json
import os

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
OUT = os.path.join(ROOT, "loop/state/out/read_dafeng_L3_0235.candidate.json")
BUILD_DIR = os.path.join(ROOT, "loop/state/out/read_dafeng_L3_0235.w-xiyou-1.build")
VERIFY = os.path.join(BUILD_DIR, "verify_candidate.py")
START, END = 929759, 934756
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第六章 验尸"
REPRODUCE = "python3 -B -s %s" % VERIFY

with open(DOCS, encoding="utf-8") as fh:
    DOC = json.load(fh)[0]
TEXT = DOC["text"]
SLICE = TEXT[START:END]

if SLICE[: len(UNIT_HEAD)] != UNIT_HEAD:
    raise SystemExit("偏移口径自检失败：切片不以单元标题开头：%r" % SLICE[:30])
_actual = hashlib.sha256(open(DOCS, "rb").read()).hexdigest()
if _actual != SOURCE_HASH:
    raise SystemExit("sourceHash 不符：%s" % _actual)


def _line(anchor):
    """取锚点所在的整行（去首尾空白）。"""
    i = SLICE.find(anchor)
    if i < 0:
        raise SystemExit("行锚点未命中：%r" % anchor)
    ls = SLICE.rfind("\n", 0, i) + 1
    le = SLICE.find("\n", i)
    if le < 0:
        le = len(SLICE)
    seg = SLICE[ls:le]
    stripped = seg.strip()
    if not stripped:
        raise SystemExit("空行：%r" % anchor)
    off = START + ls + (len(seg) - len(seg.lstrip()))
    return off, off + len(stripped)


def _span(start_anchor, end_anchor):
    """取 [start_anchor 起点, end_anchor 终点] 之间的连续原文。"""
    i = SLICE.find(start_anchor)
    if i < 0:
        raise SystemExit("锚点未命中(slice)：%r" % start_anchor)
    j = SLICE.find(end_anchor, i)
    if j < 0:
        raise SystemExit("尾锚点未命中：%r" % end_anchor)
    return START + i, START + j + len(end_anchor)


SPEC = {
    # ── 开篇对话 ────────────────────────────────────────────────
    "Q_opening": ("line", "明白你的太子哥哥是个好色之徒"),
    "Q_too_early": ("line", "现在下定论为时过早"),
    "Q_ask_4th": ("line", "为什么殿下会觉得是四皇子和皇后陷害太子"),
    "Q_hard_to_ask": ("line", "即使有奉命查案的光环罩着"),
    "Q_queen_wants": ("line", "皇后当然是想让四皇子当太子呗"),
    "Q_hen_line": ("line", "像一只雄赳赳气昂昂的小母鸡"),
    "Q_not_win": ("line", "我斗不过她"),
    "Q_huaiqing_suspect": ("line", "会不会有怀庆暗中操纵"),
    "Q_if_so": ("line", "反问道：“如果是呢。”"),
    # ── 立储嫡庶（W05） ─────────────────────────────────────────
    "Q_son_of_wife": ("line", "四皇子是怀庆的胞兄"),
    "Q_two_hundred_years": ("line", "因为两百年前争国本的事"),
    "Q_no_problem": ("line", "所以，元景帝立庶长子为太子"),
    "Q_not_rule": ("line", "有嫡子的情况下，陛下立庶出的长子"),
    # ── 地书线 ──────────────────────────────────────────────────
    "Q_xinji": ("line", "他忽然心悸了一下"),
    "Q_toilet": ("line", "我去一趟茅厕"),
    "Q_eunuch_drop": ("line", "侯在外面的小宦官见他出来"),
    "Q_pull_mirror": ("line", "掏出玉石小镜"),
    "Q_six_ask": ("line", "可否为我屏蔽其他人"),
    "Q_guess_cousin": ("line", "有些人已经猜到三号就是那位殉职在云州的许七安的堂弟"),
    "Q_no4_think": ("line", "四号心想"),
    "Q_no2_sad": ("line", "二号李妙真看到这则传书"),
    "Q_no3_gone": ("line", "天地会再也没有三号了"),
    "Q_no1_lurk": ("line", "一号窥屏，没有发表意见"),
    "Q_nine_ok": ("line", "【九：好。】"),
    "Q_jinlian_only": ("line", "金莲道长是唯一知晓所有人身份的"),
    "Q_last_meeting": ("line", "我想见许大人最后一面"),
    "Q_he_not_know": ("line", "恒远还不知道我复活了"),
    "Q_revived": ("line", "【他已经复活了，你想见他，可以去打更人衙门寻他。】"),
    "Q_really": ("line", "那边沉默了许久许久"),
    "Q_resent_head": ("span", "【难怪你不肯见我", "罪过罪过。"),
    "Q_joy_tail": ("span", "许大人是好人", "欣喜至极。】"),
    "Q_dont_expose": ("line", "我不想身份被公平"),
    "Q_monk_knows": ("line", "【贫僧知晓。】"),
    "Q_social_death": ("line", "你对着二郎笑去吧"),
    "Q_back_hall": ("line", "收好地书碎片，返回大厅"),
    # ── 冰窖 / 验尸线 ───────────────────────────────────────────
    "Q_go_see_body": ("line", "我接下来要去看一看福妃的遗体"),
    "Q_ice_cellar": ("line", "福妃的遗体存放在皇宫的冰窖里"),
    "Q_enter_cellar": ("line", "许七安手持金牌"),
    "Q_cold": ("line", "寒冷的冰窖里"),
    "Q_shiver": ("line", "裱裱缓缓打了个冷战"),
    "Q_wait_outside": ("line", "不如到外面等着吧"),
    "Q_participate": ("line", "我也想参与其中"),
    "Q_grab_hand": ("line", "一下握住了公主的柔荑"),
    "Q_flinch": ("line", "像是被蝎子蛰了一口"),
    "Q_defiled": ("line", "何时被一个男人给亵渎过"),
    "Q_warm_flow": ("line", "温暖的气流从掌心涌来"),
    "Q_no_cold": ("line", "她不再感觉寒冷"),
    "Q_voice_ear": ("line", "耳边传来狗奴才低沉的声音"),
    "Q_not_worth": ("line", "但与殿下的千金之体想必"),
    "Q_she_understands": ("line", "他握我的手是为了驱寒"),
    "Q_hide_hand": ("line", "做贼心虚的看了眼前头的两名宦官"),
    "Q_soft_hand": ("line", "公主的小手真软"),
    "Q_flirt_rule": ("line", "撩女孩子一定要主动"),
    "Q_lift_cloth": ("line", "小宦官掀开了白布"),
    "Q_undress_block": ("line", "许七安伸手去解福妃的衣衫"),
    "Q_ask_gedou": ("line", "把验尸格目和卷宗拿给我看看"),
    "Q_gedou_given": ("line", "取了格目过来，递给许七安"),
    "Q_gedou_content": ("line", "没有被奸污的痕迹"),
    "Q_first_judge": ("line", "许七安初步做出判断"),
    "Q_attention": ("line", "一条不显眼的记录吸引了他的注意"),
    "Q_face_up": ("line", "死时面朝天！"),
    "Q_jump_norm": ("line", "人跳楼自杀，是面对着地面"),
    "Q_back_up": ("line", "是背朝天，面朝地"),
    "Q_wind": ("line", "受到空气阻力、风力的影响"),
    "Q_two_and_half": ("line", "两层半的高度"),
    "Q_pushed": ("line", "是被太子推下去的？"),
    "Q_against": ("line", "这与福妃不愿受辱，跳楼身亡的判断不符"),
    "Q_reach_again": ("line", "再次把手伸向了福妃的尸体"),
    "Q_warn": ("line", "不可惊扰福妃的遗体"),
    "Q_emperor_woman": ("line", "这是陛下的女人"),
    "Q_kick": ("line", "许七安一脚踹开他"),
    "Q_decorum": ("line", "说鸡不说吧"),
    "Q_no_sound": ("line", "小宦官挨了一脚，不敢吭声了"),
    "Q_feel_bones": ("line", "许七安托起福妃的后颈"),
    "Q_body_structure": ("line", "仰面坠楼，最先与地面接触的是头部和肩胛"),
    "Q_cant_undress": ("line", "不能脱衣服"),
    "Q_confirmed": ("line", "确实是仰面坠楼的"),
    "Q_exclude": ("line", "这就排除有人在福妃事后"),
    "Q_what_find": ("line", "你有什么发现"),
    "Q_tell_both": ("line", "其实也是说给监督他的小宦官听的"),
    "Q_not_selfjump": ("line", "福妃不是自己跳楼死的"),
    "Q_praise": ("line", "公主聪明绝顶"),
    # ── 散值 / 元景帝线 ─────────────────────────────────────────
    "Q_sundial": ("line", "许七安看了一眼日晷"),
    "Q_shen_1_15": ("line", "申时一刻"),
    "Q_sanduty": ("line", "按照大奉制度"),
    "Q_spring": ("line", "虽然春祭已过"),
    "Q_emperor_study": ("line", "正坐在寝宫里专研道经"),
    "Q_dao_vs_memorial": ("line", "相比起枯燥无味的奏折"),
    "Q_power": ("line", "是权力！"),
    "Q_mortal": ("line", "但凡人的寿命有限"),
    "Q_longlife": ("line", "唯有长生久视"),
    "Q_tea": ("line", "端起参茶喝了一口"),
    "Q_report_left": ("line", "陛下，许七安离宫了"),
    "Q_what_did": ("line", "他今日在皇宫都做了什么"),
    "Q_why_care": ("line", "毕竟刚刚委任了许七安做主办官"),
    "Q_summon": ("line", "老太监立刻去传唤小宦官"),
    "Q_lazy": ("line", "元景帝坐姿慵懒"),
    "Q_tell_all": ("line", "你与陛下一五一十交代"),
    "Q_trust_me": ("line", "说明公主殿下越来越信赖我了"),
    "Q_mean_talk": ("line", "“本宫还是得承认的，怀庆心机深沉，卑鄙无耻.....”"),
    "Q_no3_cloud": ("line", "而他，已经殉职在云州了。"),
    "Q_hen_joy": ("line", "短短三个字，许七安能体会到恒远大师激动狂喜"),
    "Q_reply_simple": ("line", "许七安的回复同样简单有力"),
    "Q_tell_cousin": ("line", "当下，许七安把“堂兄”复活的经过"),
    "Q_li_miaozhen": ("line", "李妙真一愣，接着恍然"),
    "Q_no5_calm": ("line", "大概只有五号心如止水"),
    "Q_after_wine": ("line", "所谓酒后乱性"),
    "Q_why_not_queen": ("line", "元景帝那么不喜欢皇后吗"),
    "Q_confused": ("line", "他怎么这样.....裱裱又羞又怒又委屈。"),
    "Q_want_autopsy": ("line", "我还想解剖她的呢"),
    "Q_face_up_echo": ("line", "嗯？死时面朝天？"),
    "Q_leave_cellar": ("line", "离开冰窖，在宦官的服侍下净了净手"),
    "Q_no_overtime": ("line", "元景帝又不给老子加班工资"),
    "Q_put_down_book": ("line", "元景帝放下书本，闭眼咀嚼、思索书中奥秘"),
    "Q_bow_head": ("line", "小宦官低着头，躬着身。"),
    "Q_pretty_woman": ("line", "这是一个漂亮的妇人"),
    "Q_reply_ok": ("line", "【嗯。】"),
    "Q_see_him": ("line", "“许大人，您看。”"),
    "Q_lift_cloth_body": ("line", "小宦官掀开了白布，不敢多看福妃的遗体"),
    "Q_walk_body": ("line", "许七安松开临安的柔荑，走到尸体边"),
    "Q_corpse": ("line", "这是一个漂亮的妇人"),
    "Q_happy": ("line", "裱裱一听就很开心。"),
    "Q_mother_favored": ("line", "“因为我母妃当年最得宠，也最漂亮。”"),
    "Q_queen_beauty": ("line", "就依照我在祭祖大典时看见的"),
    "Q_ps": ("line", "PS：这章四千字"),
}

RESOLVED = {}
for _name, _spec in SPEC.items():
    _s, _e = _line(_spec[1]) if _spec[0] == "line" else _span(_spec[1], _spec[2])
    if _s < START or _e > END:
        raise SystemExit("引文越界：%s [%d,%d)" % (_name, _s, _e))
    _q = TEXT[_s:_e]
    if not _q or _q.strip() != _q:
        raise SystemExit("引文为空或含首尾空白：%s %r" % (_name, _q[:30]))
    RESOLVED[_name] = (_q, _s, _e)


def Q(*names):
    """把锚点名解析成带偏移的 quote 节点（偏移现算）。"""
    out = []
    for n in names:
        q, s, e = RESOLVED[n]
        whole = TEXT.count(q)
        inrange = SLICE.count(q)
        first = TEXT.find(q)
        out.append({
            "quote": q,
            "start": s,
            "end": e,
            "sourceHash": SOURCE_HASH,
            "wholeTextOccurrences": whole,
            "inRangeOccurrences": inrange,
            "firstGlobalOffset": first,
            "startIsFirstGlobalOccurrence": first == s,
            "locatorStrength": ("globally-unique" if whole == 1
                                else ("in-range-unique" if inrange == 1 else "ambiguous")),
        })
    return out


def Q1(*names):
    r = Q(*names)
    if len(r) != 1:
        raise SystemExit("Q1 需要恰好一条：%r" % (names,))
    return r[0]


TASKS = [
    {
        "id": "T01",
        "actor": "许七安",
        "objective": "从临安（裱裱）嘴里问出「为什么殿下会觉得是四皇子和皇后陷害太子」——叙述自己写明这既是吃瓜，也是为查案。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": Q("Q_ask_4th"),
        "obstacle": "这类宫廷内情「即使有奉命查案的光环罩着，他也不好问的」；只有当着临安（自己人）才能肆无忌惮开口。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": Q("Q_hard_to_ask"),
        "action": "两处都是他主动把话往下推：先接下她的判断、自己补一句「有嫡子的情况下，陛下立庶出的长子，确实不太合规矩」，再在她反问「会不会有怀庆暗中操纵」时回一句「如果是呢」。",
        "actionBasis": "explicit",
        "actionQuotes": Q("Q_not_rule", "Q_if_so"),
        "actionNote": "两句话的主语都是许七安（「在裱裱面前，许七安也就不避嫌了」是他说话时的叙述状语）。注意「这件事背后，会不会有怀庆暗中操纵？」是**临安**问的，所以它只作为 S06 的 before 证据，不当成许七安的动作。另外本条的 action 与 result 在原文里是**交错**的（她先答一次、他再接话、她再问、他再反问），我不声称严格时序，只声称方向：他的追问在前、她的说法是被问出来的。",
        "result": "得到的是临安的一整套说法：皇后想让四皇子当太子、四皇子最关心国事（她把热忱读成图谋），以及她自己承认斗不过怀庆。这些是她的立场与猜测，不是案情事实。",
        "resultBasis": "explicit",
        "resultQuotes": Q("Q_queen_wants", "Q_mother_favored", "Q_queen_beauty", "Q_not_win"),
        "cost": None,
        "costNote": "本区间内没有写许七安为这次打探付出任何代价：叙述只写他在裱裱面前不必避嫌、可以肆无忌惮开口，没有写他因此被追究、失言或损失什么。区间末尾元景帝过问许七安的查案情况，原文给出的理由是他刚委任许七安做主办官，不是对这次问话的追责，故不记为代价。",
    },
    {
        "id": "T02",
        "actor": "许七安",
        "objective": "处理地书聊天群里找上门的私信：他心悸察觉有人冒泡，随即借故离席去查看并回话。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": Q("Q_xinji", "Q_toilet"),
        "obstacle": "身边一直有小宦官跟着（侯在外面的小宦官见他出来立刻抬脚跟上），传书不能当着人看，只能找地方甩开他。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": Q("Q_eunuch_drop"),
        "action": "在茅厕掏出玉石小镜查看传书，回信告知许七安已经复活、可以去打更人衙门寻他（「【嗯。】」），并把「堂兄」复活的经过简洁告之恒远。",
        "actionBasis": "explicit",
        "actionQuotes": Q("Q_pull_mirror", "Q_revived", "Q_reply_ok", "Q_reply_simple", "Q_tell_cousin"),
        "result": "他提出的「不要公开我的身份」被答应下来（对方回「贫僧知晓」）——这是这次传书里他得到的唯一一个承诺。",
        "resultBasis": "explicit",
        "resultQuotes": Q("Q_monk_knows"),
        "cost": "代价是他必须继续把身份瞒着天地会（至少瞒着恒远）：他不打算以真身相认，只求将来偶遇时「相逢一笑」，同时把「三号」这个位置继续留给「堂弟」这层说法。",
        "costBasis": "inferred",
        "costQuotes": Q("Q_social_death"),
        "costNote": "原文没有出现「代价」字样，也没有写他因此失去什么可核对的资源。这一栏的依据是他的自述内心话（「你对着二郎笑去吧，抱歉啊大师，以前我没得选，现在我不想再社会性死亡了」），把「不能相认」读成代价是我的归纳，故标 inferred；若复核认为这属于动机而非代价，请按本注驳回，改为 null。",
    },
    {
        "id": "T03",
        "actor": "许七安",
        "objective": "亲自去看福妃的遗体、查明死因（他主动约临安同去，理由是接下来要看一看福妃的遗体）。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": Q("Q_go_see_body"),
        "obstacle": "两条禁令把他挡在遗体之外：解衣衫时被小宦官拦住（「许大人，不可.....」），再次伸手时又被拦住告诫「不可惊扰福妃的遗体」。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": Q("Q_undress_block", "Q_warn"),
        "action": "先转向可读的材料（喝令把验尸格目和卷宗拿给他看），再一脚踹开拦阻的小宦官，托起福妃的后颈、摸后脑勺并一路往下摸到肩胛和臀部，用摸骨替代查看。",
        "actionBasis": "explicit",
        "actionQuotes": Q("Q_see_him", "Q_lift_cloth_body", "Q_walk_body", "Q_ask_gedou", "Q_kick", "Q_feel_bones"),
        "result": "确认「确实是仰面坠楼的」，并据此排除「有人在福妃事后摆弄身体、伪装现场」的可能；但他确认的只是坠落姿势这一层，谁导致坠落仍未定。",
        "resultBasis": "explicit",
        "resultQuotes": Q("Q_confirmed", "Q_exclude"),
        "cost": None,
        "costNote": "本区间没有写他为越禁付出代价：踹开小宦官之后，叙述只写「小宦官挨了一脚，不敢吭声了」，没有任何追责、弹劾或损失落到他身上。区间末尾元景帝传唤小宦官问「许七安都做了些什么」，但原文没有写被传唤的是哪一个、也没有写他交代了什么（章节在此截断），所以不能把这次过问算成越禁的代价（另见 RE04）。",
    },
    {
        "id": "T04",
        "actor": "临安（裱裱）",
        "objective": "留在冰窖参与查案，「为太子哥哥做点事」。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": Q("Q_participate"),
        "obstacle": "冰窖酷寒（她缓缓打了个冷战、紧了紧狐裘大氅），许七安以怕她感染风寒、也可能没见过尸体为由劝她到外面等。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": Q("Q_shiver", "Q_wait_outside"),
        "action": "不退场，并在白布掀开后立刻追问「你有什么发现？」；同时不动声色地靠近许七安、借宽敞的大氅遮住自己被握住的手。",
        "actionBasis": "explicit",
        "actionQuotes": Q("Q_what_find", "Q_hide_hand"),
        "result": "她当场提取出核心结论「福妃不是自己跳楼死的？」，并得到许七安当面的恭维（「公主聪明绝顶，非常人能及」）。",
        "resultBasis": "explicit",
        "resultQuotes": Q("Q_not_selfjump", "Q_praise", "Q_happy"),
        "cost": "代价落在名节上：她堂堂二公主，自觉「冰清玉洁的千金之躯」被一个男人握住手是亵渎，因此又羞又怒又委屈，还得做贼心虚地瞒着前头的两名宦官。",
        "costBasis": "explicit",
        "costQuotes": Q("Q_defiled"),
        "costNote": "这栏记的是**她自己**的感受与遮掩动作（叙述直述她的娇羞、羞怒与做贼心虚）；手是许七安握的，她付出的不是体力或财物，而是名节风险与被冒犯的感受。",
    },
    {
        "id": "T05",
        "actor": "许七安",
        "objective": "在临安不肯离开冰窖的前提下替她驱寒——他自己给出的说法是「冰窖酷寒，您若是不走，那卑职只能用这种方法了」，「查案虽是头等要事，但与殿下的千金之体想必，根本不值一提」。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": Q("Q_voice_ear", "Q_not_worth"),
        "obstacle": "临安下意识的抗拒：她娇躯一僵，做出甩手动作，「像是被蝎子蛰了一口」。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": Q("Q_flinch"),
        "action": "握住公主的柔荑不放（那只手「就像铁箍一样，紧紧握住」），并且「气机绵绵灌输」。",
        "actionBasis": "explicit",
        "actionQuotes": Q("Q_grab_hand"),
        "result": "温暖的气流顺着藕臂流淌、驱散冰窖的寒冷，她不再感觉寒冷；她把这理解为「他握我的手是为了驱寒」，气消了并主动靠近。",
        "resultBasis": "explicit",
        "resultQuotes": Q("Q_warm_flow", "Q_no_cold", "Q_she_understands"),
        "cost": None,
        "costNote": "本区间没有写许七安为这次握手付出代价：他没有被追究、没有损失，相反叙述把他的私心写成占便宜（同一场景里另写了他的「撩女孩子」心得、以及他握着手时的心里话）。同一动作在临安那一侧是有代价的（记在 T04/cost），但代价不落在许七安身上，故本栏记 null。",
    },
    {
        "id": "T06",
        "actor": "元景帝",
        "objective": "了解许七安今日在皇宫都做了什么、案情可有进展——他先问「他今日在皇宫都做了什么？」，再问「许七安都做了些什么？案情可有进展？」。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": Q("Q_what_did", "Q_lazy"),
        "obstacle": None,
        "obstacleNote": "本区间没有写任何阻力：没有人拒绝回答、没有别的事打断（大太监趁空隙禀告、老太监立刻去传唤、小宦官低头躬身进来）。追问停在小宦官开口之前，章节即被作者卷尾注截断，所以既无阻力也无答案——这里记 null 是「本区间确实没有阻力描写」，不是未标注的未知。",
        "action": "听到「许七安离宫了」的禀告后思索片刻发问，命老太监传唤小宦官进寝宫，由老太监下令「你与陛下一五一十交代」。",
        "actionBasis": "explicit",
        "actionQuotes": Q("Q_summon", "Q_tell_all"),
        "result": None,
        "resultNote": "本区间没有任何结果：正文停在老太监那句「你与陛下一五一十交代。」，紧接着只有一行「.......」与作者卷尾注（「PS：这章四千字，少了一千字，明天上午六千字补。」）。小宦官怎么答、皇帝听到什么，全部在区间之外——残缺不等于失败，我不替它补一个结果。",
        "cost": None,
        "costNote": "本区间没有写元景帝为此付出任何代价（时间、精力、权力或情绪都没有写）；他发问前正在读道经、喝参茶，发问后没有描写任何损失。",
    },
    {
        "id": "T07",
        "actor": "恒远（天地会六号）",
        "objective": "想见殉职在云州的许大人最后一面；为此先请金莲道长屏蔽其他人，好私下找三号说话。",
        "objectiveBasis": "explicit",
        "objectiveQuotes": Q("Q_six_ask", "Q_last_meeting"),
        "obstacle": "他手里的信息是旧的：他以为三号只是许七安的堂弟、也以为许七安（许大人）已经殉职——许七安自己都清楚「恒远还不知道我复活了」，所以恒远只能提「最后一面」。此外他此前求见三号被拒（他自己说「难怪你不肯见我」）。",
        "obstacleBasis": "explicit",
        "obstacleQuotes": Q("Q_he_not_know", "Q_resent_head"),
        "action": "通过地书回应三号：在长久沉默之后只回了三个字「真的吗」——他没有再追问「最后一面」的事，也没有质疑。",
        "actionBasis": "explicit",
        "actionQuotes": Q("Q_really"),
        "actionNote": "这一栏在原文里很薄：恒远在本区间内的动作只有发请求与这一句回应，而发请求已经被 objective 用掉。我不重复引用 objective 的那两句话来把它撑厚（任务明令禁止同一句话同时当多栏依据）。",
        "result": "他没有见到「最后一面」，而是得到许七安还活着的消息：随后自称「欣喜至极，欣喜至极」。",
        "resultBasis": "explicit",
        "resultQuotes": Q("Q_joy_tail"),
        "cost": None,
        "costNote": "本区间没有写恒远付出什么代价：他求见、得到消息、表达欣喜与自责，没有财物、时间或地位上的损失被写到。他说的「罪过罪过」是自责（已记入 obstacle 的「此前求见被拒」一节），不构成可核对的代价，故记 null。",
    },
]

CAUSE_EDGES = [
    {
        "id": "CE01",
        "from": "六号（恒远）在群里发出请求：请金莲道长屏蔽其他人，他有话想对三号说",
        "to": "恒远与三号之间出现一对一的话（「三号，我想见许大人最后一面」）",
        "trigger": "【九：好。】——金莲道长应允了屏蔽请求。",
        "mechanism": "机制在传书规则上：天地会里只有金莲道长知晓所有人身份，也只有他能替成员屏蔽其他人（见 W04）。请求被应允之后，正文里紧接出现的才是恒远单独发给三号的那一句话。方向是「请求→应允→一对一传书抵达许七安」，不是「恒远难过所以说话」。",
        "basis": "explicit",
        "quotes": Q("Q_six_ask", "Q_nine_ok", "Q_last_meeting", "Q_jinlian_only"),
        "counter": "反面读法：原文并没有写屏蔽**生效**（其他人是否真看不到这条传书，区间内没有交代），也没有写金莲道长做了什么动作。所以这条边只记「请求→应允→这句话到了三号手里」，不能记「其他人被挡住了」。",
    },
    {
        "id": "CE02",
        "from": "恒远掌握的信息是旧的（以为三号是许七安堂弟、以为许七安已殉职）",
        "to": "恒远的诉求与情绪一起翻转：从「想见许大人最后一面」到「欣喜至极」，并答应不揭穿三号的身份",
        "trigger": "许七安回信：【他已经复活了，你想见他，可以去打更人衙门寻他。】",
        "mechanism": "机制是信息更新改变诉求：恒远要的是「最后一面」，前提是许七安已死；这条前提被推翻后，诉求从告别变成重见，情绪也随之从「心怀怨愤」变成「欣喜至极」。反向也成立（若他早知道，就不会说「最后一面」），所以不是时间相邻。",
        "basis": "explicit",
        "quotes": Q("Q_guess_cousin", "Q_he_not_know", "Q_revived", "Q_joy_tail"),
        "counter": "反面读法：原文没有写恒远到底信了几分（他只回三个字「真的吗」），也没有写他为什么此前求见被拒；「他真的理解了」这一步在区间内没有坐实。",
    },
    {
        "id": "CE03",
        "from": "验尸格目上那条不显眼的记录「死时面朝天！」",
        "to": "许七安怀疑死因不是单纯自杀，并提出「是被太子推下去的？」",
        "trigger": "「继续往下看，一条不显眼的记录吸引了他的注意：」",
        "mechanism": "机制是常识与记录的冲突：自杀跳楼通常面朝地面、死后背朝天；福妃坠落的阁楼只有两层半，人体下坠中不足以因风翻转，所以落地姿势应当就是起跳姿势。记录与这条常识不符，才逼出「姿势异常」的怀疑。",
        "basis": "explicit",
        "quotes": Q("Q_attention", "Q_face_up", "Q_face_up_echo", "Q_jump_norm", "Q_back_up", "Q_two_and_half", "Q_wind"),
        "counter": "反面读法：许七安自己随后就用「福妃不愿受辱、跳楼身亡」的判断反驳了推人下楼（见 RE01），所以这条边只到「产生怀疑」为止，不到「太子真的推了人」。",
    },
    {
        "id": "CE04",
        "from": "他亲手摸骨：托起后颈、摸后脑勺，一路从肩膀到背脊再到臀部",
        "to": "确认「确实是仰面坠楼的」，并排除有人在事后摆弄身体、伪装现场的可能",
        "trigger": "「想到这里，许七安再次把手伸向了福妃的尸体。」",
        "mechanism": "机制是接触点与体表损伤的对应：按人体结构，仰面坠楼最先着地的是头部和肩胛，再是最外凸的臀部，所以摸这几处能反推落地时的朝向；而这条触觉证据与格目上的文字记录互相印证，两条来源一致，才谈得上「排除」。",
        "basis": "explicit",
        "quotes": Q("Q_reach_again", "Q_feel_bones", "Q_body_structure", "Q_confirmed", "Q_exclude"),
        "counter": "反面读法：他只摸了骨，摸不出血肉是否受损（因为不能脱衣，见 CE05），所以「排除伪装」的强度限于体表与骨骼层面；原文也没有写他用别的手段复核过，来源也只有他一个人。",
    },
    {
        "id": "CE05",
        "from": "「这是陛下的女人，即使死了，遗体也不是臣子能亵渎的」这条禁令，加上小宦官的两次拦阻",
        "to": "许七安不能解衣、只能隔着衣服摸，因此无法检查臀部血肉是否受损，结论强度被压缩",
        "trigger": "「“许大人，不可.....”」与「“不可惊扰福妃的遗体。”」两次拦阻。",
        "mechanism": "机制是禁令改写了可用的取证手段：能用的手段从「看」降级为「摸」，于是可见的证据面变窄（血肉有没有受损查不了），这直接限定了 S03 那条结论能推到哪一步。",
        "basis": "explicit",
        "quotes": Q("Q_undress_block", "Q_warn", "Q_cant_undress"),
        "counter": "反面读法：禁令并没有真的拦住他——他踹开小宦官之后照摸不误，且没有承担后果（T03/cost 为空）。所以这条边说明的是「取证方式被改变」，不是「他查不下去」。",
    },
    {
        "id": "CE06",
        "from": "冰窖酷寒，而临安不肯离开",
        "to": "临安的寒冷被驱散，她不再感觉寒冷、也不再生气",
        "trigger": "「殿下，冰窖酷寒，您若是不走，那卑职只能用这种方法了。」——他先说明这是没办法的办法，再握上去。",
        "mechanism": "机制明写在气机上：温暖的气流从掌心涌入、顺藕臂流淌、温暖四肢百骸，把冰窖的寒冷驱散；不是「他握了手所以她高兴了」这种相邻式解释（她的高兴另有原因，写在她自己的心里话里）。",
        "basis": "explicit",
        "quotes": Q("Q_shiver", "Q_participate", "Q_voice_ear", "Q_grab_hand", "Q_warm_flow", "Q_no_cold"),
        "counter": "反面读法：她的转变并不只由热气造成——她自己把这解释成「他握我的手是为了驱寒」、并且她本来就喜欢听甜言蜜语。所以「气机驱寒」解释的是身体不冷，不解释她为什么气消。",
    },
    {
        "id": "CE07",
        "from": "地书聊天群有人冒泡（许七安忽然心悸）",
        "to": "他借「去一趟茅厕」离席、甩开跟着的小宦官，得以在无人处查看并回复传书",
        "trigger": "「这时，他忽然心悸了一下，知道地书聊天群有人冒泡了。」",
        "mechanism": "机制在地书传书的到信方式上：有新传书时他会心悸，于是必须先离开人前；小宦官因为他是往茅厕方向走而放弃跟随，这才腾出私密空间。方向是「来信→感知→需要独处→借茅厕」。",
        "basis": "derived",
        "quotes": Q("Q_xinji", "Q_toilet", "Q_eunuch_drop", "Q_pull_mirror"),
        "counter": "反面读法：正文没有明写「因为要避开小宦官才去茅厕」，只写了小宦官主动放弃跟随；把两者接起来是我的推导（故本边标 derived 而不是 explicit）。支撑方向的是他紧接着掏出镜子看传书这一动作。",
    },
    {
        "id": "CE08",
        "from": "元景帝刚刚委任许七安做福妃案的主办官",
        "to": "他盯着许七安怎么查案，在许七安离宫后立刻传唤小宦官盘问进展",
        "trigger": "「陛下，许七安离宫了。」——大太监趁他喝茶的空隙禀告。",
        "mechanism": "机制由叙述自己给出：「毕竟刚刚委任了许七安做主办官，元景帝对这个小铜锣会怎么查案还是很关注的。」关注来自委任，不来自他正在读的道经（见 RE03）。",
        "basis": "explicit",
        "quotes": Q("Q_report_left", "Q_why_care", "Q_what_did", "Q_summon", "Q_lazy"),
        "counter": "反面读法：也可能只是日常汇报（大太监本来就负责通报行程）。原文给的理由是委任与关注，但没有写他打算拿这个信息做什么，动机只到「关注」为止。",
    },
    {
        "id": "CE09",
        "from": "许七安把发现和想法讲给临安听，并且有意讲给监督他的小宦官听",
        "to": "临安当场提取出「福妃不是自己跳楼死的？」，这条判断同时进入临安与在场宦官的耳朵",
        "trigger": "「“你有什么发现？”裱裱立刻问道。」",
        "mechanism": "机制是转述：结论不是临安自己验出来的，而是从许七安口里得到的（她自己说的是「就是说……？」）；而许七安选在这个场合说，是为了让监督者听到（原文直述这一点）。",
        "basis": "explicit",
        "quotes": Q("Q_what_find", "Q_tell_both", "Q_not_selfjump"),
        "counter": "反面读法：临安的复述并不完全等于许七安的结论——许七安说过「为时过早」、他排除的只是「事后伪装」，她直接跳到「不是自己跳楼死的」，压缩掉了条件。所以这条边记的是「结论被转述」，不是「结论被证实」。",
    },
]

REJECTED_EDGES = [
    {
        "id": "RE01",
        "wouldBe": "「福妃死时面朝天」+「太子酒后乱性」⇒ 太子把福妃推下楼",
        "why": "这是区间内**许七安自己提出又自己反驳**的猜测：他先问「是被太子推下去的？」，紧接着写「这与福妃不愿受辱，跳楼身亡的判断不符」，后面只剩「不排除恼羞成怒，醉酒后有暴力倾向」这种排除法式的猜测。原文没有任何人证物证，也没有第二处佐证。",
        "quotes": Q("Q_after_wine", "Q_pushed", "Q_against"),
    },
    {
        "id": "RE02",
        "wouldBe": "临安说皇后想让四皇子当太子 ⇒ 皇后（或四皇子）真的在陷害太子",
        "why": "这是临安的立场陈述与动机推测（她本人就是太子的妹妹），区间内没有第二处佐证；许七安也只是反问「如果是呢」，既没确认也没否认。把人物的话当事实正是本角色契约禁止的。",
        "quotes": Q("Q_queen_wants", "Q_if_so"),
    },
    {
        "id": "RE03",
        "wouldBe": "元景帝沉迷道经、向往长生 ⇒ 他因此疏于政务（或因此才关心许七安查案）",
        "why": "两段确实相邻，但原文给他的关注写明了另一条机制——刚委任许七安做主办官；而「相比起枯燥无味的奏折……更让元景帝向往、沉迷」只是偏好描写，没有任何一句写他因此搁置了哪件政务。相邻不等于因果。",
        "quotes": Q("Q_dao_vs_memorial", "Q_why_care"),
    },
    {
        "id": "RE04",
        "wouldBe": "小宦官挨了一脚 ⇒ 他向元景帝告状 ⇒ 元景帝因此过问许七安",
        "why": "原文没有写被传唤的是哪一个「小宦官」（冰窖里在场的不止一个），也没有写他交代了什么——章节恰好停在「你与陛下一五一十交代。」之后。这条链的每一环都缺证据。",
        "quotes": Q("Q_no_sound", "Q_tell_all"),
    },
    {
        "id": "RE05",
        "wouldBe": "裱裱误以为许七安破案了 ⇒ 许七安确实破了案（或给出过结论）",
        "why": "开篇那句是叙述对上一段对话的概括，明写的是**她误以为**；同一区间里许七安自己对太子是否冤枉的说法是「现在下定论为时过早」。认知状态不能倒推成事实。",
        "quotes": Q("Q_opening", "Q_too_early"),
    },
    {
        "id": "RE06",
        "wouldBe": "恒远此前心怀怨愤 ⇒ 许七安是故意瞒着他不肯相认（存心让他难受）",
        "why": "恒远的怨愤是他自己的话（他还补了「罪过罪过」自责）；许七安这边的理由写在别处——他不想身份被公开。原文没有写许七安知道恒远怨愤、也没有写他以此为目的。",
        "quotes": Q("Q_resent_head", "Q_dont_expose"),
    },
]

STATES = [
    {
        "id": "S01",
        "who": "临安对被握住手这件事的状态",
        "before": "又羞又怒又委屈：她觉得堂堂二公主的千金之躯被一个男人亵渎了，下意识做出甩手动作（像被蝎子蛰了一口）。",
        "beforeBasis": "explicit",
        "beforeQuotes": Q("Q_flinch", "Q_defiled", "Q_confused"),
        "after": "不生气了，甚至主动靠近他，用宽敞的大氅遮住视线掩盖被握住的手（仍害羞）。",
        "afterBasis": "explicit",
        "afterQuotes": Q("Q_she_understands", "Q_hide_hand"),
        "anchor": "许七安那两句话：先说明「您若是不走，那卑职只能用这种方法了」，再加一句「查案……与殿下的千金之体想必，根本不值一提」。",
        "anchorQuotes": Q("Q_voice_ear", "Q_not_worth"),
        "basis": "explicit",
        "note": "翻转点写得很清楚：她先按「被亵渎」理解，听完话后改按「为了驱寒」理解。注意前值里的「甩手」是下意识动作，不是她表态拒绝。",
    },
    {
        "id": "S02",
        "who": "恒远对三号／许七安的认知与情绪",
        "before": "以为许七安已殉职，所以求见「最后一面」；又因为三号此前不肯见他而心怀怨愤。",
        "beforeBasis": "explicit",
        "beforeQuotes": Q("Q_last_meeting", "Q_resent_head"),
        "after": "知道许七安已复活、可以去打更人衙门寻他，情绪转为「欣喜至极」；叙述还替他补了这份心情的成色——「激动狂喜，又难以置信」。并答应不揭穿三号的身份（「贫僧知晓」）。",
        "afterBasis": "explicit",
        "afterQuotes": Q("Q_joy_tail", "Q_hen_joy", "Q_monk_knows"),
        "anchor": "许七安的回信：【他已经复活了，你想见他，可以去打更人衙门寻他。】",
        "anchorQuotes": Q("Q_revived"),
        "basis": "explicit",
        "note": "这次翻转只发生在恒远一人身上：天地会其他人对「三号是谁」的认知没有更新（见 K01/K02）。",
    },
    {
        "id": "S03",
        "who": "许七安对福妃死因的判断",
        "before": "读完格目后的初步判断：「强奸未遂，坠楼死亡」（叙述明写这是他「初步做出判断」）。",
        "beforeBasis": "explicit",
        "beforeQuotes": Q("Q_corpse", "Q_first_judge", "Q_gedou_content"),
        "after": "确认「确实是仰面坠楼的」，并排除有人在事后摆弄身体、伪装现场的可能；但「谁导致坠落」仍未定，他自己提出的「是被太子推下去的？」随即被自己反驳。",
        "afterBasis": "explicit",
        "afterQuotes": Q("Q_confirmed", "Q_exclude", "Q_against"),
        "anchor": "验尸格目上那条不显眼的记录「死时面朝天！」。",
        "anchorQuotes": Q("Q_attention", "Q_face_up"),
        "basis": "explicit",
        "note": "前值是**判断**（依据他读到的格目），后值是**已确认的姿势**（他自己摸出来的）。两者强度不同，不能混成一句「他查明福妃是被害的」。",
    },
    {
        "id": "S04",
        "who": "许七安在冰窖里的处置权",
        "before": "受制于禁令：解衣衫被拦（「许大人，不可.....」），再次伸手被拦住告诫（「不可惊扰福妃的遗体。」）。",
        "beforeBasis": "explicit",
        "beforeQuotes": Q("Q_undress_block", "Q_warn"),
        "after": "一脚踹开拦阻者后完成了触摸查验，小宦官「不敢吭声了」——禁令在现场被武力压过，但叙述没有写它被取消。",
        "afterBasis": "explicit",
        "afterQuotes": Q("Q_no_sound", "Q_feel_bones"),
        "anchor": "「“滚你妈的。”许七安一脚踹开他，「老子奉旨查案，这不让碰，那不让碰，你跟我说个鸡。」」",
        "anchorQuotes": Q("Q_kick"),
        "basis": "explicit",
        "note": "「奉旨查案」是他自己的说法（人物的话），不是被引用的诏令；叙述支持他持有金牌、由宦官引进冰窖，但没有任何一句写这道授权覆盖触碰遗体（见 W03）。",
    },
    {
        "id": "S05",
        "who": "元景帝的注意力落点",
        "before": "在寝宫里专研道经、想着长生与权力（「津津有味」「向往、沉迷」）。",
        "beforeBasis": "explicit",
        "beforeQuotes": Q("Q_emperor_study", "Q_dao_vs_memorial"),
        "after": "主动追问许七安今日在皇宫做了什么、案情可有进展，并传唤小宦官进寝宫。",
        "afterBasis": "explicit",
        "afterQuotes": Q("Q_what_did", "Q_summon", "Q_lazy"),
        "anchor": "大太监趁他喝茶的空隙禀告「陛下，许七安离宫了。」",
        "anchorQuotes": Q("Q_report_left"),
        "basis": "explicit",
        "note": "注意力是**转移**不是放弃：区间内在他的段落里只写到「关注」这一步，没有写他因此放下道经多久或做了什么处置。",
    },
    {
        "id": "S06",
        "who": "临安面对怀庆时的姿态",
        "before": "先扬起秀眉（「像一只雄赳赳气昂昂的小母鸡」），并主动抛出怀疑：这件事背后会不会有怀庆暗中操纵。",
        "beforeBasis": "explicit",
        "beforeQuotes": Q("Q_hen_line", "Q_huaiqing_suspect"),
        "after": "泄气、耸拉着眉眼，承认「怀庆心机深沉，卑鄙无耻.....」并委屈地说「我斗不过她」；许七安则把这次服软读成她对自己的信赖加深（「说明公主殿下越来越信赖我了」）。",
        "afterBasis": "explicit",
        "afterQuotes": Q("Q_mean_talk", "Q_not_win", "Q_trust_me"),
        "anchor": "许七安的反问「如果是呢。」",
        "anchorQuotes": Q("Q_if_so"),
        "basis": "explicit",
        "note": "翻转发生在同一段对话的两句之间（扬眉→泄气），是本区间里最快的一次状态变化；但她的**判断**没有变——她始终认为怀庆可疑。",
    },
]

KNOWLEDGE_GAPS = [
    {
        "id": "K01",
        "whoKnows": "许七安本人（他就是三号）、金莲道长（叙述写他是唯一知晓所有人身份的人）",
        "whoDoesNot": "恒远：他以为三号是许七安的堂弟（天地会里已有人这样猜），因此才把三号当作能带话的人。",
        "what": "三号的真实身份 = 许七安本人",
        "basis": "explicit",
        "quotes": Q("Q_guess_cousin", "Q_jinlian_only", "Q_no2_sad", "Q_no3_cloud"),
        "note": "四号那句「看来他也猜到三号的真实身份了」是**四号自己的推测**（原文用「心想」标明），不能当作恒远已知的证据。",
    },
    {
        "id": "K02",
        "whoKnows": "叙述只交代了各人的反应，没有任何一句写某个成员确知真相",
        "whoDoesNot": "二号李妙真以为三号已殉职（心里难过）、四号在猜、一号窥屏不发言、五号扫一眼就把地书碎片丢一边",
        "what": "天地会里到底还有谁知道三号＝许七安",
        "basis": "unverified",
        "quotes": Q("Q_no4_think", "Q_no1_lurk", "Q_no3_gone", "Q_no5_calm", "Q_li_miaozhen"),
        "note": "我把这条记成 unverified：原文给了四种不同的反应，但没有给出知情名单，我不替它补一份。",
    },
    {
        "id": "K03",
        "whoKnows": "临安：她先是误以为许七安破案了，后来从许七安口里拿到「福妃不是自己跳楼死的」这一结论",
        "whoDoesNot": "她在区间内始终没有拿到证据链本身（格目内容、摸骨过程都没有写她经手）",
        "what": "福妃案的进展",
        "basis": "explicit",
        "quotes": Q("Q_opening", "Q_not_selfjump"),
        "note": "她知道的版本是转述版；她自己那句「就是说……？」的问法也表明她在复述而不是在断言自己的发现。",
    },
    {
        "id": "K04",
        "whoKnows": "许七安自己、在场的临安与宦官；此外叙述写他刻意让监督他的小宦官听见",
        "whoDoesNot": "元景帝：他必须传唤小宦官来问，且区间内没有得到答案（章节在他听到回答之前截断）",
        "what": "许七安今日在皇宫做了什么",
        "basis": "explicit",
        "quotes": Q("Q_tell_both", "Q_summon", "Q_bow_head", "Q_tell_all"),
        "note": "「小宦官会怎么交代」是区间内最大的空白：他既是监督者、又挨了一脚，叙述偏偏停在他开口之前。",
    },
]

FORESHADOWS = [
    {
        "id": "F01",
        "name": "格目上「死时面朝天！」这条不显眼的记录 → 摸骨确认仰面坠楼 → 排除事后摆弄身体伪装现场",
        "setup": Q1("Q_face_up"),
        "setupNote": "铺设写成「一条不显眼的记录吸引了他的注意」，是显式的埋点（叙述自己强调它不显眼）。",
        "payoff": Q1("Q_confirmed"),
        "payoffExtra": Q("Q_exclude", "Q_feel_bones"),
        "status": "resolved-in-range",
        "unresolvedWhat": None,
        "basis": "explicit",
        "note": "这是**近距离**铺设→回收（同一场景内隔几段），不是跨章长线；回收的强度也有限——它排除的是「事后摆弄身体伪装现场」，不排除「被推下楼」（那一步他明确说与「不愿受辱跳楼」的判断不符）。",
    },
    {
        "id": "F02",
        "name": "福妃之死：遗体停在冰窖、案子不查清难以入土 → 区间内没有结论",
        "setup": Q1("Q_ice_cellar"),
        "setupNote": "铺设与案件状态绑定：看元景帝的架势，案子不查清，福妃难以入土为安。",
        "payoff": None,
        "payoffExtra": Q("Q_pushed", "Q_against"),
        "status": "unresolved",
        "unresolvedWhat": "谁导致福妃坠落、太子是否涉案，本区间没有答案；连元景帝追问案情进展也被章节截断（见 U05）。许七安自己提出的「是被太子推下去的？」随即被他自己反驳。",
        "basis": "explicit",
        "note": "它在区间内被打开却没有收口，我据此记 unresolved；不因为它只出现一次就当伏笔，也不因为案子没破就当失败。",
    },
    {
        "id": "F03",
        "name": "元景帝对道经与长生的沉迷 → 区间内没有产生任何后果",
        "setup": Q1("Q_dao_vs_memorial"),
        "setupNote": "铺设用了整段内心描写（权力与寿命、唯有长生久视），并抬出「蕴含着长生至理的道经」。",
        "payoff": None,
        "payoffExtra": Q("Q_power", "Q_longlife", "Q_mortal"),
        "status": "unresolved",
        "unresolvedWhat": "这条沉迷在本区间内只停在他的内心段落：他随后唯一的动作是过问许七安查案，而原文给的理由是委任主办官（见 RE03），与道经无关。",
        "basis": "explicit",
        "note": "我没有把它连成「信道→误国」的因果（那需要原文写他搁置了哪件政务，区间内没有）。",
    },
    {
        "id": "F04",
        "name": "许七安请求恒远不要公开自己的身份 → 恒远答应 → 是否瞒住没有下文",
        "setup": Q1("Q_dont_expose"),
        "setupNote": "请求是显式的，还给了理由与期望（希望将来偶遇时能相逢一笑）。",
        "payoff": Q1("Q_monk_knows"),
        "payoffExtra": Q("Q_social_death"),
        "status": "unresolved",
        "unresolvedWhat": "恒远会不会守约、天地会其他人会不会因此知道三号的真实身份，本区间没有下文；恒远答应之后许七安只留下了一句内心话。",
        "basis": "explicit",
        "note": "这里把「答应」与「做到」分开：答应是区间内的回收动作，做到不是。",
    },
    {
        "id": "F05",
        "name": "临安的怀疑（这件事背后会不会有怀庆暗中操纵）→ 许七安反问「如果是呢」→ 无下文",
        "setup": Q1("Q_huaiqing_suspect"),
        "setupNote": "怀疑由临安自己抛出，并且是在她警惕起来的时候说的。",
        "payoff": None,
        "payoffExtra": Q("Q_if_so"),
        "status": "unresolved",
        "unresolvedWhat": "怀庆是否真的在操纵、许七安那句反问是承认还是试探，本区间都没有交代。",
        "basis": "explicit",
        "note": "不把它连成「怀庆是幕后黑手」：原文除了临安这句话，没有任何关于怀庆的动作描写（她在本区间根本没有出场）。",
    },
    {
        "id": "F06",
        "name": "监督他的小宦官在场（还挨了一脚）+ 皇帝命他「一五一十交代」→ 会交代什么，无下文",
        "setup": Q1("Q_tell_both"),
        "setupNote": "铺设有两块：许七安明知被监督、并有意讲给监督者听；以及他随后踹了拦阻的小宦官一脚。",
        "payoff": None,
        "payoffExtra": Q("Q_tell_all", "Q_no_sound"),
        "status": "unresolved",
        "unresolvedWhat": "小宦官会怎么向皇帝描述许七安今日的作为（包括踹人与触碰遗体），本区间没有下文——章节恰好停在他开口之前。",
        "basis": "derived",
        "note": "这里只记「一条被打开的线头」，**没有**连「踹人→被告发→皇帝追究」的因果边（见 RE04）。标 derived 是因为把它读成一条待回收的线，需要把两处相隔约一千码点的文字接起来。",
    },
]

NOT_FORESHADOWS = [
    {"id": "NF01", "thing": "玉石小镜／地书碎片", "why": "在本区间里只作为通讯器物走完一个即时循环（掏出→查看→回复→收好），没有前后呼应的第二次功能转变。", "quote": Q1("Q_pull_mirror")},
    {"id": "NF02", "thing": "狐裘大氅", "why": "出现两次（取暖、遮手）但都是当场功能，没有铺设-回收结构；不扩成物品线。", "quote": Q1("Q_hide_hand")},
    {"id": "NF03", "thing": "「说鸡不说吧，是许七安最基本的素养」", "why": "一次性玩笑，区间内没有任何呼应。", "quote": Q1("Q_decorum")},
    {"id": "NF04", "thing": "参茶、日晷", "why": "道具性出现各一次（喝茶、看日晷），不承载前后呼应；日晷只是他判断散值时间的工具（已并入 W01 的 explain）。", "quote": Q1("Q_tea")},
    {"id": "NF05", "thing": "「撩女孩子一定要主动」那段心得", "why": "是他此刻的心理活动与自述经验，区间内没有被回收（他后来也没有再使用这套说法的第二步）。", "quote": Q1("Q_flirt_rule")},
]

WORLD_SETTINGS = [
    {
        "id": "W01",
        "kind": "rule",
        "name": "大奉散值（下班）时刻：春分后散值是申时正，秋分后是申时初",
        "quote": Q1("Q_sanduty"),
        "quoteExtra": Q("Q_spring", "Q_shen_1_15", "Q_sundial", "Q_no_overtime"),
        "institution": "executed",
        "explain": "它不是纸面规定，区间内有执行面：许七安看一眼日晷确认「申时一刻」，据此算出「下班时候已经过了一刻钟」，然后当场收工告别临安。它如何解释人物能做什么：这条制度给了他此刻离宫的正当理由（也给了他抱怨「不给加班工资」的落点），所以「今天先查到这里，明日我再来」不是他偷懒，而是制度时间到了。",
        "explainNote": "判 executed 而不是 declared：区间内既有成文口径（春分/秋分的散值时刻），又有按它行事的动作（看日晷→确认已过一刻钟→离宫）。",
        "basis": "explicit",
    },
    {
        "id": "W02",
        "kind": "rule",
        "name": "后宫遗体不可亵渎：这是陛下的女人，即使死了，遗体也不是臣子能动的",
        "quote": Q1("Q_emperor_woman"),
        "quoteExtra": Q("Q_warn", "Q_undress_block", "Q_want_autopsy"),
        "institution": "executed",
        "explain": "它有执行动作：小宦官两次拦阻（解衣衫时一次、再伸手时一次）并出言告诫。它如何限制人物：许七安不能脱衣查看，只能隔着衣服摸骨，于是「臀部血肉是否受损」这一项查不了——禁令直接改写了他能拿到的证据种类与结论强度。",
        "explainNote": "叙述把这条禁忌写成通例（「这是陛下的女人……不是臣子能亵渎的」），执行者是当值小宦官；原文没有引用任何诏令条文，所以我不把它写成 declared。",
        "basis": "explicit",
    },
    {
        "id": "W03",
        "kind": "rule",
        "name": "主办官与金牌：奉旨查案者可凭金牌进宫禁（冰窖）查验、索阅案卷",
        "quote": Q1("Q_enter_cellar"),
        "quoteExtra": Q("Q_ask_gedou", "Q_gedou_given", "Q_kick"),
        "institution": "executed",
        "explain": "执行面清楚：他手持金牌，裱裱与小宦官带路，当值宦官引他们进去；他一句「把验尸格目和卷宗拿给我看看」，宦官当即离开并取格目递上。它同时划出边界：同一道授权**没有**覆盖触碰遗体——他喊着「老子奉旨查案」仍被拦，只能靠一脚踹开人来突破。",
        "explainNote": "「老子奉旨查案」是**许七安自己**的主张（人物的话），不是被引用的诏令；我把它判 executed，依据是金牌与宦官的实际服从动作，不是他那句话。",
        "basis": "explicit",
    },
    {
        "id": "W04",
        "kind": "rule",
        "name": "地书传书规则：传书在天地会群内公开可见（成员可窥屏），只有金莲道长能替人屏蔽其他人，且他是唯一知晓所有人身份的人",
        "quote": Q1("Q_jinlian_only"),
        "quoteExtra": Q("Q_six_ask", "Q_nine_ok", "Q_no1_lurk"),
        "institution": "executed",
        "explain": "执行面是「【九：好。】」这句应允以及随后抵达三号的私信。它如何解释人物能做什么：恒远要说私事必须先求九号屏蔽（他不能自己屏蔽）；许七安要回信必须找没人的地方（他借茅厕）；而四号只能「心想」去猜三号的身份，因为身份默认不公开。",
        "explainNote": "原文没有写屏蔽的技术过程，也没有写其他人是否真的看不到；我只记「请求→应允」与「群内默认可见」这两件有文字支撑的事。",
        "basis": "explicit",
    },
    {
        "id": "W05",
        "kind": "rule",
        "name": "立储的嫡庶规矩与国本阴影：有嫡子的情况下立庶出长子不合规矩，但两百年前争国本的旧事让大奉读书人对国本之争有心理阴影",
        "quote": Q1("Q_two_hundred_years"),
        "quoteExtra": Q("Q_son_of_wife", "Q_no_problem", "Q_not_rule", "Q_why_not_queen"),
        "institution": "misunderstood",
        "explain": "这是**人物（许七安）的理解**，不是被引用的礼法条文：他先说「有嫡子的情况下，陛下立庶出的长子，确实不太合规矩」，同一段又用国本之争的阴影解释「元景帝立庶长子为太子，也没什么毛病」。它如何解释人物能做什么：正是这套理解让临安把矛头指向皇后与四皇子（四皇子是嫡子），也让许七安有理由去问「为什么殿下会觉得是四皇子和皇后陷害太子」。",
        "explainNote": "原文没有任何诏令或礼法原文，两处都是许七安的判断（其中一处还是他当着临安说的），故判 misunderstood（人物的理解）。我没有把它扩成一套大奉继承法。",
        "basis": "inferred",
    },
    {
        "id": "P01",
        "kind": "place",
        "name": "皇宫的冰窖（福妃遗体存放处）",
        "quote": Q1("Q_enter_cellar"),
        "quoteExtra": Q("Q_ice_cellar", "Q_cold", "Q_leave_cellar"),
        "placeState": "arrived",
        "explain": "有到达动作：许七安持金牌在裱裱和小宦官带领下「来到冰窖」，当值宦官引他们进去，随后冰窖内部的景象（福妃盖着白布躺在木板上）被写到。这是本区间的主要场景，验尸与握手的冲突都在这里发生。",
        "basis": "explicit",
    },
    {
        "id": "P02",
        "kind": "place",
        "name": "茅厕（许七安查看传书处）",
        "quote": Q1("Q_pull_mirror"),
        "quoteExtra": Q("Q_eunuch_drop"),
        "placeState": "arrived",
        "explain": "有到达动作：「进了茅厕，掏出玉石小镜」。它的作用在保守私密：小宦官因为看他往茅厕方向走而放弃跟随，地书那场一对一传书才有可能发生。",
        "basis": "explicit",
    },
    {
        "id": "P03",
        "kind": "place",
        "name": "元景帝的寝宫",
        "quote": Q1("Q_summon"),
        "quoteExtra": Q("Q_emperor_study"),
        "placeState": "arrived",
        "explain": "区间的收尾场景：老太监带着小宦官「进了寝宫」，元景帝在这里读道经、喝参茶、发问。有进入动作，故记 arrived。",
        "placeStateNote": "元景帝本人是「正坐在寝宫里」（无到达动作、是在场），我把 arrived 的依据放在老太监带小宦官进寝宫这一动作上，以免把「在场」混成「提及」。",
        "basis": "explicit",
    },
    {
        "id": "P04",
        "kind": "place",
        "name": "皇宫里的大厅（临安所在处）",
        "quote": Q1("Q_back_hall"),
        "quoteExtra": Q("Q_toilet"),
        "placeState": "arrived",
        "explain": "许七安从大厅离席去茅厕、办完事「返回大厅」，临安还在那里抱怨「那么久」——进出动作都被写到。打探宫廷内情那场对话就发生在这里。",
        "basis": "explicit",
    },
    {
        "id": "P05",
        "kind": "place",
        "name": "福妃坠落的阁楼（两层半高）",
        "quote": Q1("Q_two_and_half"),
        "placeState": "mentioned",
        "explain": "只在卷宗转述里出现：高度「根据卷宗记载，两层半」。区间内没有任何人去过这座阁楼，也没有现场勘查——它是本案的关键地点却只以文字形式在场。",
        "placeStateNote": "判 mentioned 而不是 arrived：这是本任务明令的「提及≠到达」。我没有因为它是案发地就把它升级成 arrived。",
        "basis": "explicit",
    },
    {
        "id": "P06",
        "kind": "place",
        "name": "云州（许七安「殉职」地）",
        "quote": Q1("Q_guess_cousin"),
        "placeState": "mentioned",
        "explain": "只作为身份信息被提到：三号被认作「那位殉职在云州的许七安的堂弟」。区间内无人在云州活动。",
        "placeStateNote": "纯提及（而且是天地会成员的认知内容），故记 mentioned。",
        "basis": "explicit",
    },
    {
        "id": "P07",
        "kind": "place",
        "name": "打更人衙门",
        "quote": Q1("Q_revived"),
        "placeState": "mentioned",
        "explain": "只出现在许七安给恒远的指路里（「可以去打更人衙门寻他」）。它影响的是一条尚未发生的行动（恒远要去找人），区间内无人在衙门出现。",
        "placeStateNote": "只有指路，没有到达动作，判 mentioned。",
        "basis": "explicit",
    },
    {
        "id": "I01",
        "kind": "item",
        "name": "玉石小镜／地书碎片（许七安手里的传书器物）",
        "quote": Q1("Q_pull_mirror"),
        "quoteExtra": Q("Q_back_hall", "Q_no1_lurk"),
        "itemStates": ["hold", "use"],
        "explain": "hold：器物在他身上（掏出、用毕「收好地书碎片」）；use：他用它查看传书内容、收发恒远的私信。四态里没有 transfer、没有 lose——区间内它没有易手、也没有丢失。",
        "itemNote": "「玉石小镜」与「地书碎片」在本区间内都指他手里的传书器物（掏出玉石小镜→……→收好地书碎片），五号那边也写作「把地书碎片丢一边」。两个名字是否同一件东西，原文没有一句明说，这一步等同是我的推断（见 U07）；我按同一件记，避免把一件东西拆成两条物品链。",
        "basis": "inferred",
    },
    {
        "id": "I02",
        "kind": "item",
        "name": "验尸格目与卷宗",
        "quote": Q1("Q_ask_gedou"),
        "quoteExtra": Q("Q_gedou_given", "Q_gedou_content"),
        "itemStates": ["transfer", "use"],
        "explain": "transfer：他索阅后「宦官当即离开，俄顷，取了格目过来，递给许七安」——文书从守冰窖的宦官手里交到他手里；use：他读它的内容并据此做出初步判断（「没有被奸污的痕迹……」那一串就是格目上的字）。区间内既没有写到它被归还，也没有写它被改动——这两种状态我不记。",
        "itemNote": "格目内容是**文书上的记载**（由宦官取来、由他阅读），不等于叙述对尸体状况的独立确认；它出自谁手，原文没有交代（见 U02）。",
        "basis": "explicit",
    },
    {
        "id": "I03",
        "kind": "item",
        "name": "金牌（查案凭证）",
        "quote": Q1("Q_enter_cellar"),
        "itemStates": ["hold", "use"],
        "explain": "hold：许七安「手持金牌」；use：他靠它进宫禁、被当值宦官引进冰窖、并让宦官去取格目卷宗。区间内没有易手或丢失。",
        "basis": "explicit",
    },
    {
        "id": "I04",
        "kind": "item",
        "name": "狐裘大氅",
        "quote": Q1("Q_hide_hand"),
        "quoteExtra": Q("Q_shiver"),
        "itemStates": ["use"],
        "explain": "use 有两处：一是她打冷战时「紧了紧狐裘大氅」（御寒），二是她用「宽敞的大氅」遮挡前方两名宦官的视线、盖住自己被握住的手。区间内没有易手、没有丢失。",
        "basis": "explicit",
    },
    {
        "id": "I05",
        "kind": "item",
        "name": "道经（蕴含长生至理的那本书）",
        "quote": Q1("Q_emperor_study"),
        "quoteExtra": Q("Q_dao_vs_memorial", "Q_put_down_book"),
        "itemStates": ["hold", "use"],
        "explain": "hold 与 use 都写在同一段：他坐在寝宫里「专研道经，看的津津有味」，随后「放下书本，闭眼咀嚼、思索书中奥秘」。它解释的是他的注意力去向（也正是他被打断的那件事），不解释任何外部事件。",
        "basis": "explicit",
    },
]

NOT_WORLD_SETTINGS = [
    {"id": "NW01", "thing": "福妃的遗体", "why": "它是本案的对象，但四态（hold/transfer/use/lose）没有一态适用于尸体：原文写的是它被「存放在皇宫的冰窖里」、盖着白布躺在木板上。硬套四态会把它写成一条物品链，故不立 item 条目，只保留 P01 的地点与相关 state。", "quote": Q1("Q_ice_cellar")},
    {"id": "NW02", "thing": "盖尸的白布", "why": "只承担「揭开才能看」的一次性功能（小宦官掀开白布），没有约束或放开任何人的行动，属道具性提及。", "quote": Q1("Q_lift_cloth")},
    {"id": "NW03", "thing": "日晷", "why": "是他判断散值时刻的工具，本身不构成规则或资源；已并入 W01 的 explain，不单列 item。", "quote": Q1("Q_sundial")},
    {"id": "NW04", "thing": "参茶", "why": "一次性道具（端起参茶喝了一口），不影响任何行动或后果。", "quote": Q1("Q_tea")},
    {"id": "NW05", "thing": "「社会性死亡」这类现代梗与吐槽", "why": "是他的语言风格，不是世界设定；按「没有依据就不扩术语装饰层」不立条目。", "quote": Q1("Q_social_death")},
]

THEME_READINGS = [
    {
        "id": "TH01",
        "perspective": "以**「证据的可及性由身份划定」**为轴读验尸这一段：许七安能读什么、能碰什么，不取决于他会不会查案，而取决于他是「奉旨的主办官」还是「臣子」。于是他的取证被切成两条路——可读的文书（格目、卷宗）与不可碰的遗体（被两次拦住），他先用文书拿到线索，再靠武力把遗体这条路的门踹开。",
        "basis": "inferred",
        "support": Q("Q_ask_gedou", "Q_emperor_woman", "Q_confirmed", "Q_exclude"),
        "counter": "反证很硬：禁令最终并没有真的限制住他——一脚踹开之后照摸不误，且叙述没有写他因此被追究（T03/cost 为空）；同时这一段的笑点（「说鸡不说吧」）在消解严肃读法。另外他的结论建立在触觉与常识上，而不是制度性证据（没有仵作、没有第二人复核）。所以这条读法解释的是「取证方式的分布」，不能升格成「本章在批判制度」。",
        "note": "这是解释层，不是事实层。我特意没有用事件数量、篇幅中点或死亡人数来界定任何东西。",
    },
    {
        "id": "TH02",
        "perspective": "以**「谁知道什么」**为轴读本章的两条线：地书线上，恒远以为三号是死者的堂弟、以为许七安已死，所以说的是「最后一面」；验尸线上，许七安知道的比宦官多，临安知道的只是他转述的版本，而皇帝必须传唤小宦官才能知道许七安做了什么。读法关心信息差如何决定台词与行动，而不是谁强谁弱。",
        "basis": "inferred",
        "support": Q("Q_opening", "Q_he_not_know", "Q_guess_cousin", "Q_why_care"),
        "counter": "反证：这些信息差在本区间内几乎都没有被推向冲突——恒远立刻接受消息、皇帝的问话被章节截断、临安的误解也没有造成任何后果；推动动作的常常是喜剧性动机（吃瓜、撩妹、下班，见 T01/objective 里的原文夹注「既有吃瓜，也是为查案」与 T05/costNote）。所以把它当全章主线会漏掉另一半。",
        "note": "两条读法并存：TH01 管验尸段的取证方式，TH02 管对话与传书段的信息分布。我没有把它们压成一条「唯一真相」。",
    },
]

SPEECH = [
    {
        "id": "P01",
        "speaker": "临安（裱裱）",
        "speech": RESOLVED["Q_queen_wants"][0],
        "canProve": "她相信皇后想让四皇子当太子，并且用「四皇子关心国事」来支撑这个判断。",
        "cannotProve": "皇后真的在谋太子位、四皇子真的在图谋——区间内没有第二处佐证，也没有皇后或四皇子的任何动作。",
        "quoteRef": Q1("Q_queen_wants"),
    },
    {
        "id": "P02",
        "speaker": "临安（裱裱）",
        "speech": RESOLVED["Q_not_win"][0],
        "canProve": "她自我评估斗不过怀庆，并承认怀庆心机深沉。",
        "cannotProve": "怀庆真的在操纵这件事（她自己上一句也只是问「会不会」）；也不能证明怀庆「卑鄙无耻」。",
        "quoteRef": Q1("Q_not_win"),
    },
    {
        "id": "P03",
        "speaker": "许七安",
        "speech": RESOLVED["Q_kick"][0],
        "canProve": "他主张自己有查案授权，并用这个主张为踹人开路；叙述支持他确实手持金牌（W03）。",
        "cannotProve": "这道授权覆盖到「触碰／惊扰遗体」——他喊完这句话之后仍然只有靠踹开人才碰到尸体，叙述另写了一条通例「这是陛下的女人……不是臣子能亵渎的」（W02）。",
        "quoteRef": Q1("Q_kick"),
    },
    {
        "id": "P04",
        "speaker": "恒远（六号）",
        "speech": RESOLVED["Q_joy_tail"][0],
        "canProve": "他表达了狂喜与善意，并称许七安是好人。",
        "cannotProve": "「好人就会有好报」是真的——这是他的信念与慰问，不是叙述对因果的判断（本次他之所以能重见，靠的是地书传书与许七安的回复）。",
        "quoteRef": Q1("Q_joy_tail"),
    },
    {
        "id": "P05",
        "speaker": "许七安",
        "speech": RESOLVED["Q_first_judge"][0],
        "canProve": "他读完格目后做出了这个初步判断（叙述明写「初步做出判断」）。",
        "cannotProve": "福妃真的遭到强奸未遂——它的依据是宦官取来的格目（I02），区间内没有仵作、没有第二人复核，也没有写格目出自谁手（U02）。",
        "quoteRef": Q1("Q_first_judge"),
    },
    {
        "id": "P06",
        "speaker": "许七安",
        "speech": RESOLVED["Q_pushed"][0],
        "canProve": "他一度这样怀疑，并且这个怀疑是他自己提出来的。",
        "cannotProve": "太子真的推了福妃——紧接着的下一段就是他自己反驳（「这与福妃不愿受辱，跳楼身亡的判断不符」），剩下的也只是「不排除」式的猜测。",
        "quoteRef": Q1("Q_pushed"),
    },
    {
        "id": "P07",
        "speaker": "守冰窖的小宦官",
        "speech": RESOLVED["Q_warn"][0],
        "canProve": "他援引这条禁忌来拦阻，并且确实拦了两次（执行面）。",
        "cannotProve": "这条禁忌的准确条文——原文没有引用任何诏令或宫规原文，通例那一句是叙述给的（W02）。",
        "quoteRef": Q1("Q_warn"),
    },
    {
        "id": "P08",
        "speaker": "四号（天地会）",
        "speech": RESOLVED["Q_no4_think"][0],
        "canProve": "四号自己在猜恒远可能已知道三号的真实身份（原文用「心想」标明这是他的内心推测）。",
        "cannotProve": "恒远真的猜到了——恒远随后的传书里仍然称对方为三号，并说要见「许大人」，看不出他知道三号是谁；更没有任何一句写他知道三号＝许七安（K01）。",
        "quoteRef": Q1("Q_no4_think"),
    },
]

TEXTUAL_NOTES = [
    {
        "id": "TN01",
        "note": "**本章在本区间内被截断**：正文停在老太监那句「你与陛下一五一十交代。」，其后的 [934698,934709] 只有一行「.......」，紧接着是作者卷尾注（「PS：这章四千字，少了一千字，明天上午六千字补。」）。作者自己承认少了一千字。⇒ 本区间的「结尾」是残缺，不是情节收束：任何「皇帝听到了什么」的结论都没有依据（T06/resultNote、K04、U05）。",
        "quotes": Q("Q_tell_all", "Q_ps"),
    },
    {
        "id": "TN02",
        "note": "**明显错字/病句（照原文引用，不改字，也不据此推断语义）**：「趁着每人主意」（疑为「没人注意」，正是他握住她手的那个动作的状语）、「附和抵抗暴力的特征」（格目那一串里，疑为「符合」）、「我不想身份被公平」（疑为「公开」）、「与殿下的千金之体想必」（疑为「相比」）、「耸拉着眉眼」（疑为「耷拉」）、「侯在外面的小宦官」（疑为「候」）。列在这里是为了让复核者能对齐引用；我按原文逐字引用，不改写。",
        "quotes": Q("Q_grab_hand", "Q_gedou_content", "Q_dont_expose", "Q_not_worth", "Q_hen_line", "Q_eunuch_drop"),
    },
    {
        "id": "TN03",
        "note": "开篇第一句句法不完整（「明白你的太子哥哥是个好色之徒.......许七安随口应一句而已，裱裱误以为他破案了。」），它是叙述对上一段对话的概括。我只用它证明「裱裱误以为他破案了」这一认知状态（K03/RE05），不用它推断许七安破过案。",
        "quotes": Q("Q_opening"),
    },
    {
        "id": "TN04",
        "note": "**同一器物两个名字**：他进茅厕「掏出玉石小镜」，出来时「收好地书碎片」；五号那边也写「把地书碎片丢一边」。两者是否同一件东西，原文没有一句明说，我按同一件记并在 I01/itemNote 与 U07 里标明这一步是推断。",
        "quotes": Q("Q_pull_mirror", "Q_back_hall", "Q_no1_lurk"),
    },
    {
        "id": "TN05",
        "note": "**握手一段是双动机写法**：台词层面给的是驱寒（「冰窖酷寒，您若是不走，那卑职只能用这种方法了」「查案……根本不值一提」），同段的内心层面又给了撩拨（「撩女孩子一定要主动，要大胆进攻」、以及他握着手时的心里话）。两层都在原文里，不能只取其一（T05/objective 与 T05/costNote）。",
        "quotes": Q("Q_voice_ear", "Q_flirt_rule", "Q_soft_hand"),
    },
    {
        "id": "TN06",
        "note": "验尸段有**两层信息**必须分开：一层是格目上的记载（没有奸污痕迹、掐痕、衣衫不整、秀发凌乱、死时面朝天），一层是他自己的判断（「强奸未遂，坠楼死亡」是他「初步做出判断」，随后又提「是被太子推下去的？」并部分自我反驳）。叙述用「初步」「不排除」这些限定词标出了强度差异，我照它分层记（S03/P05），不合并成「他查明了真相」。",
        "quotes": Q("Q_gedou_content", "Q_first_judge", "Q_pushed", "Q_against"),
    },
]

UNKNOWNS = [
    {
        "id": "U01",
        "q": "福妃到底是怎么死的？谁导致她坠落？",
        "why": "区间内只有格目记载 + 许七安的初步判断 + 他自己提出又部分反驳的「被太子推下去？」。没有第二个人证物证，也没有验尸的第二人复核。",
        "status": "**区间内无解**。结论只能到「仰面坠楼得到确认、事后摆弄身体伪装被排除」这一步（S03）；「谁导致坠落」留给后续单元。",
    },
    {
        "id": "U02",
        "q": "验尸格目是谁写的、依据什么写的？",
        "why": "原文只写「宦官当即离开，俄顷，取了格目过来」，没有写作者、没有写验尸人、没有写它是否经过复核。",
        "status": "**无解**。我只把它记成一份被递交的文书（I02），不把它当作对尸体的独立确认。",
    },
    {
        "id": "U03",
        "q": "「趁着每人主意」到底是什么意思？",
        "why": "读不通，疑为「没人注意」的错字；原文如此。",
        "status": "**不改字、不推断**（TN02 已列）。这个动作在语义上仍可读（他趁人不备握住她的手），但我没有用这句去支撑任何超出「他握了她的手」的结论。",
    },
    {
        "id": "U04",
        "q": "「你对着二郎笑去吧」里的「二郎」是谁？",
        "why": "这个名字在本区间内只出现这一次，没有交代身份、与许七安的关系，也没有再出现。",
        "status": "**无解**。我不替他补身份（区间外的信息不算本区间的证据），因此 T02/cost 只按「他把身份这层留给别人、自己不相认」来写。",
    },
    {
        "id": "U05",
        "q": "小宦官最终向元景帝交代了什么？",
        "why": "章节恰好停在他开口之前（「你与陛下一五一十交代。」之后是「.......」与作者注）。",
        "status": "**区间内无解**（T06/resultNote、F06、K04）。这条空白同时是「踹人是否被追究」无法判定的原因（T03/costNote、RE04）。",
    },
    {
        "id": "U06",
        "q": "天地会里到底还有谁知道三号＝许七安？",
        "why": "原文给了四种不同反应（四号在猜、一号窥屏、五号不在意、二号难过），只说金莲道长「唯一知晓所有人身份」，没有给知情名单。",
        "status": "**区间内不可判定**（K02 标 unverified）。我按「不替它补名单」处理。",
    },
    {
        "id": "U07",
        "q": "「玉石小镜」与「地书碎片」是同一件东西吗？",
        "why": "同一场景里两个名字都用来指他手上的器物（掏出玉石小镜→收好地书碎片），但原文没有一句把它们等同。",
        "status": "**推断而非事实**（I01/itemNote、TN04）。若两者其实不同，我的 item 条目需要拆成两条。",
    },
    {
        "id": "U08",
        "q": "恒远此前是怎么求见三号的、为什么被拒？许七安与恒远有什么前史？",
        "why": "只有恒远一句「难怪你不肯见我」，没有时间、方式，也没有许七安那一侧的说法。",
        "status": "**无解**。这条空白直接影响 T07/obstacle 的措辞，所以我把它写在这里而不是替它编一段前史。",
    },
    {
        "id": "U09",
        "q": "许七安「不想身份被公开」的顾虑具体是什么？",
        "why": "只有他自己的内心话（不想再社会性死亡、希望将来偶遇时相逢一笑），没有写谁会因为身份公开而受损、也没有写他担心谁知道。",
        "status": "**无解**。我只把它记成 T02/cost 与 F04 的依据，不扩成一条阴谋线。",
    },
    {
        "id": "U10",
        "q": "元景帝对道经与长生的沉迷从何而来、是否有外力介入？",
        "why": "区间内只有他的内心段落（权力→寿命→唯有长生久视），没有任何人向他推介、也没有写明道经来源。",
        "status": "**区间内无解**（F03 标 unresolved）。我拒绝把它连成任何因果关系（RE03）。",
    },
]

SELF_CRITIQUE = [
    {
        "id": "SC01",
        "risk": "把许七安「确认仰面坠楼」当成不可推翻的事实，而不是一个人的触摸结论。",
        "why": "原文的措辞是我依据的来源：他只能摸骨（不能脱衣，见 CE05），叙述也没有写第二人复核；格目那条「死时面朝天」本身还是一份来路不明的文书（U02）。我仍然把「仰面坠楼」记进 S03/after，理由是叙述用「他确认完毕」把它写成结论、并据此排除了事后伪装，且我明确标出它的证据种类（触觉 + 文书），没有写成「法医鉴定」。若复核认为这仍属不可靠推论，请按 CE04/counter 与 P05 驳回。",
    },
    {
        "id": "SC02",
        "risk": "T02/cost 把「不能相认」记成代价，可能属于动机而非代价。",
        "why": "依据只有他自己的内心话（你对着二郎笑去吧、抱歉啊大师、不想再社会性死亡），没有资源、地位或关系的实际损失被写到。我标了 inferred 并在 costNote 里写明「若认为属动机请驳回改为 null」；我选择不记 null 是因为「把身份让给别人、自己不相认」确实是他为维持这层身份支付的东西，而这正是本任务最容易被记成「白得一个消息」的地方。",
    },
    {
        "id": "SC03",
        "risk": "F06 有「把相邻当伏笔」的嫌疑（小宦官挨了一脚 + 皇帝要问话）。",
        "why": "我特意把它标成 derived 并在 note 里写明我没有连「踹人→被告发」的因果边（RE04）。保留它的理由是：皇帝确实下了「一五一十交代」这道命令，而章节恰好停在小宦官开口之前——这是一个被文本打开的缺口，不是我先假定有阴谋再去找证据。若复核认为它应降级为 unknowns，我接受（U05 已单独记录同一空白）。",
    },
    {
        "id": "SC04",
        "risk": "worldSettings 的三条区分（placeState / itemStates / institution）含裁量，尤其 W05 判 misunderstood。",
        "why": "W05 的依据都是许七安的判断（其中一句还是他当着临安说的），原文没有礼法或诏令原文，所以我判「人物的理解」而不是 declared。P03 的 arrived 依据是老太监带小宦官进寝宫这一动作（不是元景帝「坐在」寝宫），P05/P06/P07 都判 mentioned（含案发地阁楼，避免「提及≠到达」）。每条都写了 placeStateNote / itemNote / explainNote，方便逐条驳回而不是整条作废。",
    },
    {
        "id": "SC05",
        "risk": "T01 的 objective 里「吃瓜」那一半来自叙述，可能让它读起来像我在替角色定动机。",
        "why": "依据是原文自己的夹注：「许七安问这话，既有吃瓜，也是为查案」——动机由叙述给出，不是我推的。我照它把双动机都写进去，没有只取「为查案」那一半来美化角色。",
    },
    {
        "id": "SC06",
        "risk": "T07/action 只有一条证据，可能显得太薄。",
        "why": "恒远在本区间内的动作确实只有「发请求」与「回三个字」两处，而发请求已经被 objective 用掉。我按纪律没有把 objective 的句子重复拿来当 action 依据，也没有替他编一个动作（例如「他决定去衙门」——原文没写）。宁可薄，不重复、不编造。",
    },
]


def build_candidate():
    return {
        "schemaVersion": "castline/read-candidate/1",
        "task": "read:dafeng:L3:0235",
        "agent": "w-xiyou-1",
        "role": "READER",
        "book": "dafeng",
        "bookTitle": "大奉打更人",
        "lane": 3,
        "unitIndex": 235,
        "unitHead": UNIT_HEAD,
        "source": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
            "selector": "docs[0].text",
            "range": [START, END],
            "codepoints": END - START,
            "sourceHash": SOURCE_HASH,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
            "sliceSha256": hashlib.sha256(SLICE.encode("utf-8")).hexdigest(),
            "sliceSha256Scope": "docs[0].text[929759:934756] 的 sha256（附加字段，不覆盖 sourceHash）",
            "offsetCaliber": "相对 docs[0].text 全文的 codepoint 偏移；要求 text[start:end]==quote。少数引文串在全文更早处也出现过，用 startIsFirstGlobalOccurrence=false 标出，未冒充唯一。",
            "boundaryHead": SLICE.split("\n")[0],
            "sliceStartsWithUnitHead": True,
            "graphCachePath": "data/cache/1063b17ca65ec1b76f30e460.json",
            "graphCacheNote": "图谱缓存只用于对照已有结论（其 meta 声明 quoteLocationOnly、deepMode=false，worldRules/items/locations 层未启用），本候选**没有**用它作为任何引文或断言的依据。",
        },
        "provenanceNote": "引文偏移全部由 loop/state/out/read_dafeng_L3_0235.w-xiyou-1.build/build.py 用 TEXT.find(锚点) 现算（按锚点取整行或取跨锚点区间，再核对 text[start:end]==quote、区间落在 [929759,934756) 内）；没有任何一条 start/end 是手写的。同目录 verify_candidate.py 是独立复核脚本（无第三方依赖）。",
        "semanticReview": "not-performed",
        "semanticReviewNote": "本候选只做了引用定位与逐字核验（脚本可复现）+ 分区归属判断，**没有**做独立语义评审，也没有跨单元对读。定位正确 ≠ 语义已核验；不声称 semanticReview 完成。",
        "basisLegend": {
            "explicit": "原文直述（含叙述对人物内心/动作的直接交代）",
            "inferred": "我的归纳（原文没写，由我读出）",
            "derived": "跨段推导（需要把两处以上原文接起来）",
            "unverified": "存疑，未能核验",
        },
        "speechAsClueNotFact": SPEECH,
        "speechAsClueNotFactNote": "人物的话一律只当线索：能证明他说了什么、想什么、主张什么，不能证明他说的内容为真。8 条里最危险的两条是 P05（许七安「强奸未遂，坠楼死亡」——依据是一份来路不明的格目）与 P03（他主张的「奉旨查案」并不覆盖触碰遗体）。",
        "nullFieldRule": "缺依据的栏写 null，并在同名 <栏位>Note 里写明为什么没有。本候选实测 null 7 处：T01/T03/T05/T06/T07 的 cost、T06 的 obstacle 与 result；每处都带同名 Note（构建期强制，缺 Note 直接构建失败）。",
        "tasks": TASKS,
        "causeEdges": CAUSE_EDGES,
        "rejectedEdges": REJECTED_EDGES,
        "states": STATES,
        "knowledgeGaps": KNOWLEDGE_GAPS,
        "foreshadows": FORESHADOWS,
        "notForeshadows": NOT_FORESHADOWS,
        "foreshadowsNote": "6 条里只有 F01 在区间内完成铺设→回收（而且是**近距离**回收：同一场景隔几段）；F04 收了「答应」这一半，做到的没有；F02/F03/F05/F06 全部标 unresolved（案子无结论、道经无后果、怀庆是否有份无下文、小宦官会说什么无下文）。另有 5 条 notForeshadows 说明为什么只出现一次或只有即时功能的东西不算。",
        "worldSettings": WORLD_SETTINGS,
        "notWorldSettings": NOT_WORLD_SETTINGS,
        "worldSettingsNote": "本区间收 5 个 rule、7 个 place、5 个 item（共 17 条）。rule 的 institution：4 条 executed（散值制度、后宫遗体禁忌、主办官金牌、地书传书规则，都有实际执行动作）、1 条 misunderstood（立储嫡庶与国本阴影——依据都是许七安的理解）；**本区间没有任何 declared**：最接近的「奉旨查案」是许七安自己说的话，不是被引用的诏令原文（W03/explainNote），我不为了凑齐三档把它写成 declared。place 中 4 个 arrived（冰窖、茅厕、寝宫、大厅），3 个 mentioned（福妃坠落的阁楼、云州、打更人衙门）——阁楼是案发地但区间内无人到达，按「提及≠到达」记 mentioned。item 四态分开写，不合成物品链：玉石小镜／地书碎片 hold+use（**不记 transfer/lose**）、验尸格目 transfer+use、金牌 hold+use、狐裘大氅只记 use、道经 hold+use。另有 5 条 notWorldSettings 记录我考虑过并排除的东西（含尸体与白布）。",
        "themeReadings": THEME_READINGS,
        "textualNotes": TEXTUAL_NOTES,
        "unknowns": UNKNOWNS,
        "selfCritique": SELF_CRITIQUE,
    }


FIELDS = ("objective", "obstacle", "action", "result", "cost")


def self_check(cand):
    problems = []
    for t in cand["tasks"]:
        for f in FIELDS:
            if t.get(f) is None and not (t.get(f + "Note") or "").strip():
                problems.append("%s.%s 为 null 但没有 %sNote" % (t["id"], f, f))
        seen, spans = {}, []
        for f in FIELDS:
            qs = t.get(f + "Quotes") or []
            if t.get(f) is not None and not qs:
                problems.append("%s.%s 非 null 但没有引用" % (t["id"], f))
            if len(qs) > 1 and len({q["quote"] for q in qs}) != len(qs):
                problems.append("%s.%s 栏内重复引用" % (t["id"], f))
            for q in qs:
                if q["quote"] in seen:
                    problems.append("%s 的 %s 与 %s 共用同一句引用：%r"
                                    % (t["id"], f, seen[q["quote"]], q["quote"][:25]))
                seen[q["quote"]] = f
                spans.append((q["start"], q["end"], f))
        spans.sort()
        for i in range(len(spans) - 1):
            if spans[i][1] > spans[i + 1][0] and spans[i][2] != spans[i + 1][2]:
                problems.append("%s 的 %s 与 %s 区间重叠：[%d,%d) vs [%d,%d)"
                                % (t["id"], spans[i][2], spans[i + 1][2],
                                   spans[i][0], spans[i][1], spans[i + 1][0], spans[i + 1][1]))
    # 跨任务引文复用（比提示词更严的自设标准：同一句话不在两条不同任务里当依据）
    per_task = {}
    for t in cand["tasks"]:
        s_ = set()
        for f in FIELDS:
            for q in t.get(f + "Quotes") or []:
                s_.add(q["quote"])
        per_task[t["id"]] = s_
    ids = sorted(per_task)
    cross = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            shared = per_task[ids[i]] & per_task[ids[j]]
            if shared:
                cross.append("%s/%s 共用：%r" % (ids[i], ids[j], sorted(shared)[0][:30]))
    if cross:
        problems.extend("跨任务引文复用 " + c for c in cross)
    for w in cand["worldSettings"]:
        if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            problems.append("%s institution 非法" % w["id"])
        if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            problems.append("%s placeState 非法" % w["id"])
        if w["kind"] == "item":
            st = w.get("itemStates") or []
            if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                problems.append("%s itemStates 非法：%r" % (w["id"], st))
    # 自报数字必须与真实字段一致（本轮真实缺陷：worldSettingsNote 声称 5 条 notWorldSettings，
    # 但该字段根本没被输出——只看「已写项对不对」是查不出来的）
    for sec, note_key, label in (("notWorldSettings", "worldSettingsNote", "notWorldSettings"),
                                 ("notForeshadows", "foreshadowsNote", "notForeshadows")):
        note = cand.get(note_key) or ""
        actual = len(cand.get(sec) or [])
        if ("%d 条 %s" % (actual, label)) not in note:
            problems.append("%s 自报条数与实际不符：实际 %d 条，注里找不到「%d 条 %s」"
                            % (note_key, actual, actual, label))
    if len(cand["themeReadings"]) > 2:
        problems.append("themeReadings 超过 2 条")
    for th in cand["themeReadings"]:
        for k in ("perspective", "support", "counter"):
            if not th.get(k):
                problems.append("%s 缺 %s" % (th["id"], k))
    for f in cand["foreshadows"]:
        if f["status"] not in ("resolved-in-range", "unresolved", "partial"):
            problems.append("%s status 非法" % f["id"])
        if f["status"] == "unresolved" and not (f.get("unresolvedWhat") or "").strip():
            problems.append("%s 标 unresolved 但没写 unresolvedWhat" % f["id"])
        if not f.get("setup"):
            problems.append("%s 缺 setup（不算伏笔）" % f["id"])
    return problems


def collect_quotes(node, path="$", acc=None):
    if acc is None:
        acc = []
    if isinstance(node, dict):
        if {"quote", "start", "end", "sourceHash"} <= set(node):
            acc.append((path, node))
        for k, v in node.items():
            collect_quotes(v, path + "." + k, acc)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect_quotes(v, path + "[%d]" % i, acc)
    return acc


if __name__ == "__main__":
    cand = build_candidate()
    problems = self_check(cand)

    quotes = collect_quotes(cand)
    bad = []
    for path, q in quotes:
        s, e, txt = q["start"], q["end"], q["quote"]
        if TEXT[s:e] != txt:
            bad.append((path, "text[start:end] != quote", txt[:30]))
        if TEXT.find(txt) < 0:
            bad.append((path, "全文找不到", txt[:30]))
        if not (START <= s < e <= END):
            bad.append((path, "越界", txt[:30]))
        if q["sourceHash"] != SOURCE_HASH:
            bad.append((path, "sourceHash 不符", txt[:30]))
        if q["wholeTextOccurrences"] != TEXT.count(txt):
            bad.append((path, "wholeTextOccurrences 算错", txt[:30]))
        if q["startIsFirstGlobalOccurrence"] != (TEXT.find(txt) == s):
            bad.append((path, "startIsFirstGlobalOccurrence 标错", txt[:30]))

    if bad or problems:
        for b in bad:
            print("[引文问题]", b)
        for p in problems:
            print("[构建问题]", p)
        raise SystemExit("自检失败：引文 %d 条、构建 %d 条" % (len(bad), len(problems)))

    ivs = sorted({(q["start"], q["end"]) for _, q in quotes})
    merged = []
    for s, e in ivs:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    union = sum(e - s for s, e in merged)
    nonspace = sum(1 for ch in SLICE if not ch.isspace())
    paras, off = [], START
    for line in SLICE.split("\n"):
        if line.strip():
            paras.append((off, off + len(line), line.strip()))
        off += len(line) + 1
    zero = [{"start": s, "end": e, "text": t} for s, e, t in paras
            if not any(s < qe and e > qs for qs, qe in ivs)]

    cand["coverage"] = {
        "sliceCodepoints": len(SLICE),
        "nonSpaceCodepoints": nonspace,
        "quoteUnionCodepoints": union,
        "quoteUnionRatioOfNonSpace": round(union / nonspace, 4),
        "quoteIntervals": len(ivs),
        "mergedIntervals": len(merged),
        "paragraphs": len(paras),
        "paragraphsWithZeroCoverage": len(zero),
        "zeroCoverageParagraphs": zero[:40],
        "note": "覆盖率只用于对账「哪些段落完全没被引用」，**不是**质量分，也不是「读得够不够」的判据。",
        "deliberatelyUnquotedNote": "余下未引用的整行都是**结构性或纯修辞**的文字，我刻意不引用，逐类列出：① 单元标题行「第六章 验尸」（它不是叙事内容）；② 分隔行与作者卷尾注（「........」「..........」「.......」「------------」「PS：这章四千字…」——副文本，作者自述不属于故事事实，已在 TN01 说明）；③ 单句应答与独白式过渡（「都是自己人。」「恒远找我做什么......」「裱裱立刻起身：“嗯嗯。”」「裱裱一听就很开心。」——这些是紧接着已引用句子的反应，语义由已引用的句子承担）；④ 两段现代比喻的延伸（「高公里数的汽车／备胎」「用豪华名车的车头撞她的车尾灯」——是他那段「撩女孩子」心得的修饰语，心得本身已在 NF05 记过）；⑤ 元景帝的价值独白（「世界上最让人着迷的东西是什么？」「最后还是要败给时间，化作一捧黄土。」——与已引的「是权力！」「但凡人的寿命有限」「唯有长生久视」同段同义，属于修辞展开）。以上五类我都没有用来支撑任何断言；若复核认为 ③⑤ 中的某句另有承载，请按本节指出。",
    }
    cand["machineSelfCheck"] = {
        "buildScript": os.path.join(BUILD_DIR, "build.py"),
        "reproduceCommand": REPRODUCE,
        "quoteNodes": len(quotes),
        "uniqueQuoteStrings": len({q[1]["quote"] for q in quotes}),
        "taskFieldQuoteCollision": [],
        "taskFieldIntervalOverlap": [],
        "nullFields": ["%s.%s" % (t["id"], f) for t in cand["tasks"]
                       for f in FIELDS if t.get(f) is None],
        "nullWithoutNote": [],
        "requiredSections": ["tasks", "causeEdges", "states", "foreshadows",
                             "worldSettings", "themeReadings"],
        "missingSections": [],
        "worldSettingsShapeProblems": [],
        "themeReadingProblems": [],
        "foreshadowProblems": [],
        "speechClueShapeProblems": [],
        "crossSectionQuoteReuseNote": "同一条引文会在 tasks / states / speechAsClueNotFact 等**不同分区**里被引用（这是有意的：状态与因果要各自锚定同一处原文）。任务明令禁止的是**同一条任务的五栏之间**共用同一句——构建期与 verify_candidate.py 都强制检查了这一点。",
        "sourceHashMatchesDocsJson": True,
        "sliceStartsWithUnitHead": True,
        "allQuoteOffsetsComputedNotHandwritten": True,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(cand, fh, ensure_ascii=False, indent=1)
    h = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
    print("写出：%s" % OUT)
    print("sha256：%s" % h)
    print("引文节点 %d / 唯一引文串 %d / null %d" %
          (len(quotes), cand["machineSelfCheck"]["uniqueQuoteStrings"],
           len(cand["machineSelfCheck"]["nullFields"])))
    print("coverage：%s" % json.dumps(
        {k: v for k, v in cand["coverage"].items() if k != "zeroCoverageParagraphs"},
        ensure_ascii=False))
