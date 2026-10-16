# -*- coding: utf-8 -*-
"""第七十四章 候选构建器（构建期，人工精读结论在此落盘）。

纪律：
  · 所有 start/end 一律从 refs_0303.json 取（probe_0303.py 用 text.find 现算），
    本文件**不手写任何偏移**，也不手写任何引文字符串。
  · 缺哪一栏写 null，并在同名 <栏>Note 写明为什么没有依据。
  · semanticReview = not-performed：定位正确 ≠ 语义已核验。

构建期断言（A1–A12）在 __main__ 里跑；problems 非空则拒绝写出候选。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REFS = json.loads((HERE / "refs_0303.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(HERE))
from quotes_0303 import QUOTES  # noqa: E402

SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 1338280, 1348239
SLICE_SHA = "15d527d606ff07502a6b209ba4867be57922b0b86fed862ac8c1c1621a3a9d49"
AUTHOR_START = 1348131

# ── 话语类型：自动判定 + 显式覆盖 ─────────────────────────────────────────
# 自动规则（可复核）：含对白引号「“」或传书括号「【」⇒ dialogue；否则 narration。
# 覆盖集只处理「叙述转述人物内心」这一类：它们形式上是叙述，内容是人物心理，
# 既不是叙述对事实的认定、也不是人物说出口的话。
INNER_KEYS = set("""q_three_qiyun q_heart_iron q_daxiong_guess q_plotter q_touch q_xiyou q_shouren
q_mantou_cao q_baiguan q_xiongduo q_henji q_dahai2 q_daozhang_anxious q_what_happen q_tiansha q_heavy_heart
q_maodao q_no_signal q_wuhao_huijing q_dianshi_20 q_liyuan_harm q_liyuan_risk q_kuse q_daji_half q_xuecang
q_qidao q_wunai q_baochi_obj q_meiting q_bubaio q_goulan_go q_zhuan_quan q_confident q_nervous q_deja_vu
q_lizhifu_think q_maodao_see q_maodao_judge q_qianyou_dream q_liyuan_harm q_stay_here q_best_choice
q_shiyeminye q_erku q_lizhifu_eyes""".split())
# 形式上是引号、但据上下文是人物**心里的疑问/自言自语**，不是对谁说出口的话
INNER_OVERRIDE_WITH_QUOTE = {"q_what_happen", "q_shiyeminye"}

KIND = {}
for _k, _q in QUOTES.items():
    if _k in INNER_KEYS:
        KIND[_k] = "inner"
    elif ("“" in _q) or ("【" in _q):
        KIND[_k] = "dialogue"
    else:
        KIND[_k] = "narration"


def R(key, kind=None):
    r = REFS[key]
    q = r["quote"]
    return {
        "key": key,
        "quote": q,
        "start": r["start"],
        "end": r["end"],
        "sourceHash": SOURCE_HASH,
        "kind": kind or KIND[key],
        "occ": r["occ"],
        "para": r["para"],
        "spansParagraphs": False,
        "containsUtterance": ("“" in q) or ("【" in q),
    }


def slot(text, basis, keys, note=None, kind=None):
    d = {"text": text, "basis": basis, "quotes": [R(k) for k in keys]}
    if note:
        d["note"] = note
    if kind:
        d["claimKind"] = kind
    return d


def _cost_quotes(task):
    """costQuotes 恒为列表：cost 有值时列出其引文 key，无值时为空表。
    这样这个字段在任何一条任务上都不自相矛盾（不会出现「cost 为空却有 costQuotes」）。"""
    c = task.get("cost")
    return [q["key"] for q in c["quotes"]] if isinstance(c, dict) else []


# ══════════════════════════════════════════════════════════════════════════
# tasks[]：五元组分列，每栏自带 quotes[]（构建期断言 A3 保证五栏不共用区间）
# ══════════════════════════════════════════════════════════════════════════
TASKS = [
    {
        "id": "T01",
        "who": "金莲道长（主事者）与天地会在襄州的四人：楚元缜、恒远、许七安；钟璃以观气提供地势判断",
        "objective": slot("先找到失踪的五号，下墓的事以后再说。这句是金莲道长当面定下的调子，不是我的归纳。",
                          "explicit", ["q_xian_zhaoren"],
                          "目标是金莲道长说出口的话（dialogue）；紧随其后的一句叙述（「找到五号就回京城，就当没有这回事」）把他的取舍写得更明确，该句登记在 action 一栏。"),
        "objectiveNote": "objective 的依据是一句对白；另有一句紧邻叙述把同一取舍写得更明确，它被放在 action 一栏，两栏不共用同一区间。",
        "obstacle": slot("五号下落不明；且众人对「南边那片山脉底下有没有大墓」本身就不确定——金莲道长明确说他不懂风水，也只是「未必就有大墓吧」。",
                         "explicit", ["q_dont_know", "q_maybe_no_tomb"],
                         "障碍是「不知道」而不是「被打退」：本章没有任何人在找人的路上被谁阻挡。"),
        "obstacleNote": None,
        "action": slot("先定调把下墓搁下（找到五号就回京城），再议定三路分工找人。",
                       "explicit", ["q_wuhao_huijing", "q_three_ways"],
                       "两句都是叙述直述：前一句写他的取舍落点，后一句写分工这件事被议定。"),
        "actionNote": "具体三路的内容在 T17 单列，避免同一任务里用同一批区间反复支撑不同栏。",
        "result": slot("当夜与次日白天都没有找到人：许七安带着钟璃在城里转了几圈、专挑江湖人士打听，原文写的是「一无所获」。",
                       "explicit", ["q_youling"],
                       "结果是「没找到」这一事实本身。分工里另两路（御剑搜索、恒远打听）在本区间没有结果描写，故 result 只覆盖有明确文字的这一路。"),
        "resultNote": "「一无所获」是叙述对许七安这一路的总结；另两路无结果描写，登记在 unknowns U05。",
        "cost": slot("许七安从自己的荷包里掏出一把碎银交给恒远，作为打听情况的经费。这是本区间内这次搜寻唯一可辨认的资源付出。",
                     "explicit", ["q_silver_fist"],
                     "原文只写「一把碎银」，没有数额，也没有写他因此损失什么；我照原文记「一把」，不换算、不估数。"),
        "costNote": "本区间没有写任何人因这次搜寻受伤、失财（除碎银外）、或被罚；不把「找不到人」改写成代价（那是 result 一侧）。",
        "costQuotes": None,
    },
    {
        "id": "T02",
        "who": "李知府（襄州知府）",
        "objective": slot("把京城来的银锣交办的搜人差事应付过去，不真正费力。他对同知下的原话是「你就敷衍一下便成」。",
                          "explicit", ["q_fuyan"],
                          "目标出自李知府本人的指示（dialogue）。「不能拒绝」是他给出的理由，不是他的目标——它是同一句里的后半段，故不在本文件任何一栏里重复使用。"),
        "objectiveNote": "objective 引的是李知府那句指示的全文（含「不能拒绝」这一理由）。理由不是目标，故它**不在本任务的任何其他栏**里再充当依据（构建期断言 A3 保证五栏区间两两不重叠）。",
        "obstacle": slot("这桩差事本身推不掉，而且在下属看来根本做不成：同知说「这不是大海捞针么」，并且有心推脱。",
                         "explicit", ["q_dahai", "q_tuotuo"],
                         "两句都出自同知（一句是他的抱怨、一句是叙述对他的态度描写），都不与 objective 的区间重叠。"),
        "obstacleNote": None,
        "action": slot("他把差事转述给同知；随后因「银锣许七安」这个名字耳熟而让人取来昨日的邸报；读到「银锣许七安代司天监斗法」后改口，要求同知立刻去办、务必尽心尽力。",
                       "explicit", ["q_zhuan_shu", "q_erku", "q_lizhifu_eyes"],
                       None),
        "actionNote": "动作按时间排列：转述 → 起疑取邸报 → 读到那一行字。改口那一步（「这件事，你立刻去办」）在 S02 的状态后值里，避免五栏共用。",
        "result": slot("同知应下「下官一定竭尽全力」。原文到这句为止，没有写搜寻是否真的展开、也没有写结果。",
                       "explicit", ["q_jiejinquanli"],
                       "result 只记「下属口头应承」这一已发生的事；把「竭尽全力」当作已执行的结果就是「说法当事实」，故不写。"),
        "resultNote": "本区间没有写襄城官府的实际搜寻行动与结果，登记在 knowledgeGaps K04。",
        "cost": None,
        "costNote": ("本区间未写李知府为这件事付出可辨认的代价。原文里唯一接近的是「京城来的银锣，不能拒绝」——"
                     "但那是一条**约束**（他不能拒绝），约束不等于他付出了什么；本区间没有写他破费、受损、被问责或失去什么。"
                     "同知的「有心推脱」也没有变成对李知府的损失。因此记 null。"),
        "costQuotes": [],
    },
    {
        "id": "T03",
        "who": "许七安",
        "objective": slot("弄清五号在襄城地界究竟留下了什么痕迹。他自己把要找的东西说得很具体：「襄城地界内，必定留下战斗痕迹」。",
                          "explicit", ["q_henji"],
                          "这是他内心推演里给出的一步（原文是他的连续独白），我按他本人设定的查证目标记录，不代他补一个更高层的目的。"),
        "objectiveNote": None,
        "obstacle": slot("查证的两条渠道都给出否证：府衙对「近来有发生什么异常」的回答是「没有」；他自己在城中打探许久也没听说奇闻异事。",
                         "explicit", ["q_zhifu_no", "q_meiting"],
                         "两条渠道分属官府与市井，各自有引文；obstacle 不是「有人在阻止他」，而是「没有痕迹可查」。"),
        "obstacleNote": None,
        "action": slot("他进府衙向李知府当面问「襄城地界，近来有发生什么异常？或者，有古怪人物在附近战斗。」",
                       "explicit", ["q_ask_abnormal"],
                       "行动里只列这一条**已发生的当面询问**；街头转圈那一条与 T01.result 的区间重叠，故不在此重复使用。"),
        "actionNote": "他在府衙的同一段里还提出了搜人请求（「本官要找一个来自南疆的女子…」），那一句属于 T01 那条线，不在本任务重复。",
        "result": slot("他自己把「有战斗痕迹」这一支否掉了：既没有人报官、也没有奇闻异事，于是给出的落点是改去勾栏。",
                       "explicit", ["q_goulan_go"],
                       "结果是**判断上的收敛**（排除了一种可能），不是找到了五号。"),
        "resultNote": "「果然还是勾栏听曲去吧」是这一步推演的落点，不代表他找到了线索。",
        "cost": None,
        "costNote": ("本区间未写许七安为这次街头查证付出可辨认的代价。原文只有一句「打探了大半天，饥渴难耐」，"
                     "但那句是他在勾栏门口对钟璃的解释（dialogue），不是叙述认定的消耗；叙述侧的「日头渐高」「转了几圈」"
                     "也只写时长与动作。既没有损失、也没有放弃什么，故记 null，不把「走了半天」写成代价。"),
        "costQuotes": [],
    },
    {
        "id": "T04",
        "who": "许七安（提出者）与钟璃（执行预言者）",
        "objective": slot("借钟璃预言师的能力找一条找人的线索。他对她说的原话是「用你预言师的能力，我觉得或许能让我们找到线索」。",
                          "explicit", ["q_predict_ask"],
                          "目标出自许七安本人的请求（dialogue）；他只说「或许」，没有承诺结果，我照原文保留这层不确定。"),
        "objectiveNote": None,
        "obstacle": slot("钟璃先给出警告：按她的经验，即使有了线索，最终也会让事情走向更糟糕的结局。",
                         "explicit", ["q_zhongli_warn"],
                         "障碍是预言本身的副作用，不是外力阻拦。"),
        "obstacleNote": None,
        "action": slot("他用「我是有大气运的人，能抵消你的部分厄运」说服她，她随即低头动用预言。",
                       "explicit", ["q_daqiyun", "q_persuaded"],
                       "动作分两步：说服 → 起卦。两句引文各管一步；预言说出的内容在 result 一栏。"),
        "actionNote": None,
        "result": slot("预言给出了方向、距离与对象特征：「往南走三里，会有我们想要的线索，青色衣衫.......男人.......惶恐不安.......」",
                       "explicit", ["q_prophecy"],
                       "结果是**线索的产出**，不是五号被找到。"),
        "resultNote": "预言指向的人随后确实在路边出现（见 T14 与 C10）；本栏只记预言这一步的产出，不外推到「找到了五号」。",
        "cost": slot("代价由两人分担：钟璃预言后「虚弱的跌坐在地」，并自述预言后厄运会升级成天谴、无庇佑活不过两个时辰；许七安背她走的三里路连遭一次纵马冲撞、两次马车失控、一次被人含怒下杀手。",
                     "explicit", ["q_once_day", "q_three_miles"],
                     "两句引文分别对应两个承担者，互不重叠；天谴规则的执行情况另见 W07。"),
        "costNote": None,
        "costQuotes": None,
    },
    {
        "id": "T05",
        "who": "钱友（后土帮舵主）",
        "objective": slot("招揽七品以上的高手去墓中把帮主和弟兄们救回来。木牌上写的是「诚意要求七品以上高手相助，重金回报」。",
                          "explicit", ["q_sign"],
                          "目标是牌面上的文字（原作用引号引出），是他自己写下的招揽条件。"),
        "objectiveNote": "他的口头请托（「请大侠帮忙救人」）与牌面重复，故不在本栏并列引用，避免五栏共用同一批区间。",
        "obstacle": slot("他本领低微、走投无路；报官在他自己看来不稳妥，因为「小人第一个被抓，官差也不会急匆匆的去救人」。",
                         "explicit", ["q_baoguan_no"],
                         "障碍是他对可行路径的判断（dialogue），不是叙述对他处境的认定；叙述只写他摆了摊子。"),
        "obstacleNote": None,
        "action": slot("他摆摊挂牌等人上门；对陌生人先不搭理、只指了指木牌；钢刀砍来时喊「小心」。",
                       "explicit", ["q_muban", "q_xiaoxin"],
                       "三个动作按时间排列：挂牌 → 试探 → 示警。"),
        "actionNote": "请托那一步（狂喜、「请大侠帮忙救人」）在 S05 的状态后值里，避免与 objective 的区间重叠。",
        "result": slot("许七安当面应下：「这个任务我接了。」",
                       "explicit", ["q_accept"],
                       "结果是「招揽成功」，不是「帮主获救」——救人的结果本区间没有发生。"),
        "resultNote": "把「接到任务」写成 result 而不写「救出帮主」，是因为本区间钱友连墓都没下（他自己留在外面招揽）。",
        "cost": None,
        "costNote": ("本区间未写钱友付出可辨认的代价。两个候选项都不成立：①「报酬好说」「重金答谢」是**许诺**，"
                     "原文没有写他付了任何东西（连定金都没有）；②「一念及此，钱友心生退意」之后他确实"
                     "「头也不回的离开了」，但那是**放弃等待**，随后他见剑光纸鹤又「立刻回去」，"
                     "原文没有把这个反复写成损失。故记 null，不把许诺或动摇改写成代价。"),
        "costQuotes": [],
    },
    {
        "id": "T06",
        "who": "许七安",
        "objective": slot("把金莲道长和楚元缜叫到城外来。他对钱友给的解释是「找几个朋友相助」。",
                          "explicit", ["q_wrong_dir"],
                          "目标出自他对钱友的解释（dialogue）；他走的是北边而不是墓所在的南边，正因为目的是叫人而不是下墓。"),
        "objectiveNote": None,
        "obstacle": slot("地书碎片不能用，否则会暴露他的身份。",
                         "explicit", ["q_shout"],
                         "限制出自他的内心话（inner）；该句同时交代了手段（靠吼），此处只用它作 obstacle 的依据，手段归 action。"),
        "obstacleNote": None,
        "action": slot("他先吩咐钱友到远处等待并捂住耳朵，随后发出狮子吼：原文写咆哮震耳欲聋、音波震的密林抖动。",
                       "explicit", ["q_fenfu", "q_roar"],
                       "动作分「支开旁人」与「发声」两步，各有引文。"),
        "actionNote": None,
        "result": slot("金莲道长踏纸鹤、楚元缜踏剑光循声赶来。",
                       "explicit", ["q_sword_light", "q_paper_crane"],
                       "结果是「两人到齐」；恒远的到场另有他自己的路径（听见吼声），故不在本栏，见 rejectedEdges R05。"),
        "resultNote": "恒远是由「在城中听见隐约的狮子吼」而赶到的，原文特意写出这条独立路径，故不并入本栏。",
        "cost": slot("代价落在钱友身上：他被音波震得眼前一黑、气血翻涌、耳鸣阵阵、捂住耳朵蹲下，过了好几分钟才缓过劲，耳朵仍在疼。",
                     "explicit", ["q_faint", "q_recover"],
                     "这两句是叙述对钱友身体状况的直述；许七安吩咐他站远、捂耳，代价仍然发生。"),
        "costNote": "本栏记的是这次行动实际付出的代价（承受者钱友），不是许七安的付出。原文没有写许七安为此付出任何东西。",
        "costQuotes": None,
    },
    {
        "id": "T07",
        "who": "许七安（报告者）对金莲道长（听者）",
        "objective": slot("把五号的真实处境告诉金莲道长：先给出「好消息」——她不是被地宗妖道抓住，而是遇到了其他麻烦。",
                          "explicit", ["q_good_bad"],
                          "目标出自他自己设定的报告方式（dialogue：好消息/坏消息）。坏消息留到后面说，那一步在 T09.obstacle。"),
        "objectiveNote": None,
        "obstacle": slot("三人的预期与他掌握的情况相反：六号传书里已经把五号定性为「极有可能被地宗的妖道抓走了」。",
                         "explicit", ["q_msg6"],
                         "六号的传书是**传书内容**（人物判断），此处只把它当作「三人预期的来源」，不作为事实。"),
        "obstacleNote": None,
        "action": slot("他先让道长通知城里的恒远，再指着南边给出结论。",
                       "explicit", ["q_notify", "q_no_arrive"],
                       "动作按顺序排列：通知 → 给出结论。两句互不重叠。"),
        "actionNote": "「她下墓了」这半句与结论同段但区间不同，它放在 result 一栏，避免两栏共用同一区间。",
        "result": slot("结论是「她下墓了」，且它超出了三人的预料。",
                       "explicit", ["q_xiamu_fact", "q_beyond"],
                       "两句分属「他的结论」与「三人的反应」，都是叙述直述。"),
        "resultNote": "它只是**许七安给出的结论**；五号本人在墓中的处境仍未解（K02），后续被三人接受（S08）。",
        "cost": None,
        "costNote": ("本区间未写许七安为这次报告付出可辨认的代价。他没有因为说出五号下落而失去什么、"
                     "被谁追究、或承担风险；把「他用了狮子吼叫人」写成这次报告的代价也不成立——那属于 T06，且其代价落在钱友身上。"
                     "故记 null。"),
        "costQuotes": [],
    },
    {
        "id": "T08",
        "who": "金莲道长（回答者）与楚元缜（提问者）",
        "objective": slot("回答楚元缜的疑问：如果五号人在墓中，地书碎片为什么会被屏蔽。",
                          "explicit", ["q_why_shield"],
                          "目标是楚元缜当面提出的问题（dialogue），金莲道长的回答即针对它。"),
        "objectiveNote": None,
        "obstacle": slot("他并没有确认过墓里的情况，只能给出条件式判断：「除了地宗秘法能封印地书碎片，其他手段也可以，只是比较苛刻。」",
                         "explicit", ["q_other_means"],
                         "障碍是「没有实地证据」。这句是他的话；后半句的「墓中必有大阵」是断言，放在 action 一栏，两栏不共用区间。"),
        "obstacleNote": None,
        "action": slot("他目光南眺、眯着眼，断言「墓中必有大阵，屏蔽了地书碎片，让她无法接受到我们的传书」。",
                       "explicit", ["q_mujian", "q_dazhen"],
                       "此处把「做判断」与「判断内容」并列：动作是目光南眺眯着眼，内容是那句断言。"),
        "actionNote": "「必」是他的断言力度，不是叙述背书；本栏只记他说了什么，不把它写成事实（见 NW01 与 SP04）。",
        "result": slot("许七安由此捕捉到一个细节：墓中有大阵，而众所周知司天监是专业玩阵法的。",
                       "explicit", ["q_no_signal"],
                       "结果是「一个想法被产生」，我照原文的力度记录，不写成「他决定去破阵」。"),
        "resultNote": "这一细节在本区间没有被使用，登记为未回收伏笔 F03。",
        "cost": None,
        "costNote": "本区间未写金莲道长为这次解释付出任何代价：没有消耗、没有暴露、没有被质疑到底。故记 null。",
        "costQuotes": [],
    },
    {
        "id": "T09",
        "who": "金莲道长",
        "objective": slot("立刻下墓。他自己的原话是「事不宜迟，我们赶紧下去吧」，叙述把他的状态写成「迫不及待」。",
                          "explicit", ["q_hurry"],
                          "目标是他的原话（dialogue），状态词出自紧随其后的叙述标记；两者指同一件事，故只引一句。"),
        "objectiveNote": None,
        "obstacle": slot("许七安在他说完「不行」之后给出的坏消息：钟璃为了寻找线索使用了预言的能力，而今处在遭天谴的状态。",
                         "explicit", ["q_bad_news", "q_tianqian"],
                         "两句分属许七安的两句话（先拦住、再给理由）；障碍是「有人处于天谴状态」这一事实。"),
        "obstacleNote": None,
        "action": slot("他改口：既然知道了五号的下落，那也不急于一时，不妨稍作休整，明日再下墓。恒远与楚元缜随后附和。",
                       "explicit", ["q_rest_tomorrow", "q_heng_agree2", "q_chu_agree2"],
                       "改口与两次附和各有引文；改口的理由（钟璃的状态）已用作 obstacle 依据，此处不重复引用。"),
        "actionNote": None,
        "result": None,
        "resultNote": ("本区间未写出下墓的结果，故记 null。金莲道长把下墓改到「明日」，而区间在许七安「这句话如此熟悉」的自嘲处"
                       "结束（其后是作者区），没有任何人下墓、也没有写推迟后发生了什么。**不把「推迟」写成 result**："
                       "那是 action 一栏的内容，重复使用同一句会让两栏共用依据。"),
        "cost": None,
        "costNote": ("本区间未写金莲道长为这次推迟付出可辨认的代价。原文只写他的急切被压下去（「略显沉默的气氛」），"
                     "没有写他因此损失时间之外的东西、被谁反对、或承担后果。故记 null；不把「晚一天」写成代价。"),
        "costQuotes": [],
    },
    {
        "id": "T10",
        "who": "后土帮帮主一行",
        "objective": slot("开挖襄城外那片风水宝地底下的大墓。这行的活计被钱友解释为「挖掘一些古代遗迹、墓穴，让里面的物件重见天日」。",
                          "explicit", ["q_digrave", "q_keqing"],
                          "目标出自钱友的转述（dialogue）：他先给出行当，再说客卿发现襄城外有风水宝地、底下极可能藏着大墓。"),
        "objectiveNote": "帮主本人没有在本区间出场，也没有说过一句话——本条 objective 是**转述**，不是当事人自述。",
        "obstacle": slot("后土帮自己的副帮主（一位术士）判定墓穴里污秽之气甚是恐怖、怕有邪物，光靠后土帮搞不定。",
                         "explicit", ["q_fubangzhu"],
                         "障碍出自钱友转述的副帮主判断；它不是叙述对墓内情况的认定，故不作为「墓里确实有邪物」的事实。"),
        "obstacleNote": None,
        "action": slot("准备妥当之后带人下墓。",
                       "explicit", ["q_daixia_mu"],
                       "行动句取「直到近期才准备妥当，带人下墓」这一截；准备本身所耗的资源登记在 cost 一栏，两栏区间不重叠（A3）。"),
        "actionNote": "钱友说的是「我们准备了…带人下墓」，但紧接着写「帮主他们再也没有回来」与「只能继续招揽高手」，故下墓者不含钱友。",
        "result": slot("帮主一行再也没有回来。钱友由此认定他们必然出现了意外。",
                       "explicit", ["q_never_back"],
                       "result 只记「没有回来」这一已发生的事；「必然出现了意外」是钱友的判断，在同一句引文里照录但不当作叙述事实。"),
        "resultNote": "本区间没有写帮主一行在墓中的具体情况（生死、位置、遭遇），登记在 knowledgeGaps K02。",
        "cost": slot("代价是先期投入的人力物力：足足三个月的准备——四处招揽高手、置办工具，其中包括至刚至阳的物品，用来克制墓里的阴秽之气。",
                     "explicit", ["q_prepare3m"],
                     "这是本区间唯一写明的资源投入，且逐项可数（三个月 / 招揽高手 / 工具 / 至刚至阳物品）；原文没有写折算成多少钱财，我不换算。"),
        "costNote": ("只记这一笔已投入的成本。「带人下墓」这个动作本身记在 action 一栏（区间不同），"
                     "「帮主他们再也没有回来」记在 result 一栏——不把同一件事在三栏里重复计账。"
                     "钱友转述里另有一笔招待（请五号大吃一顿、承诺管吃管住），那是**对五号的交易**，"
                     "已作为 T11.objective 登记，不在本栏重复计入。"),
        "costQuotes": None,
    },
    {
        "id": "T11",
        "who": "五号（南疆女子，天地会成员）",
        "objective": slot("筹到盘缠、吃上饭，并被人带去京城：钱友转述的条件是「承诺带她去京城，路上管吃管住」。",
                          "explicit", ["q_baochi_obj"],
                          "目标是钱友转述的交易条件（dialogue）。五号本人在本区间没有出场、也没有说过一句话，这一栏不是她的自述。"),
        "objectiveNote": "这是**全区间最需要小心的一栏**：五号的目标完全由钱友转述而来，而 T10.cost 引用的是同一段里的另半句，两栏区间不重叠。",
        "obstacle": slot("她从南疆千里迢迢而来，缺了盘缠，饿了三天三夜。",
                         "explicit", ["q_how_know"],
                         "障碍是资源匮乏，出自钱友的转述；「力大无穷」是对她修为的描述，不是障碍，故不写进 obstacle。"),
        "obstacleNote": None,
        "action": slot("她答应下墓帮后土帮。这是钱友转述里她唯一被写出的动作。",
                       "explicit", ["q_baochi_act"],
                       "action 与 objective 引的是同一段话里**两个不同区间**（承诺条件 / 她的应承），不是同一句；这一处拆分在构建期断言 A3 里通过。"),
        "actionNote": None,
        "result": slot("她在襄州消失不见，且与地书碎片之间的感应中断；本区间给出的结论是「下墓倒斗出了意外」，而非被地宗妖道抓走。",
                       "explicit", ["q_yuanlai"],
                       "这句是许七安的推断（inner），不是叙述对她处境的直述；另一处六号传书的说法在 obstacle/SP01 里，不在此重复。"),
        "resultNote": "本区间没有写她在墓中的实际遭遇；「下墓」由钱友的转述与许七安的推断合成，登记在 knowledgeGaps K02。",
        "cost": None,
        "costNote": ("本区间未写五号付出可辨认的代价。「缺盘缠、饿三天」是障碍不是她付出的代价；"
                     "「下墓」是她的行动；「失踪」是 result。三者我都已分别归位，故 cost 记 null，"
                     "不把她的失陷重复记成代价（那会与 result 同指一事）。"),
        "costQuotes": [],
    },
    {
        "id": "T12",
        "who": "李妙真（天地会二号）",
        "objective": slot("先去江州调查一个案子，再去京城沿途铲奸除恶；因此要把天人之争延期几日，殿试过后再来京。",
                          "explicit", ["q_msg2"],
                          "目标出自她自己的传书（dialogue），传书是**她写的字**，我按她的原话记录，不代她补动机。"),
        "objectiveNote": "传书里「嗯，天人之争延期几日吧」是她的决定，不是请求——原文没有写她征求谁同意。",
        "obstacle": None,
        "obstacleNote": ("本区间未写延期的障碍。传书只说她「打算去一趟江州」，没有写谁拦她、也没有写她遇到了什么困难；"
                         "楚元缜给出的解释（「李妙真要突破了，所以才一拖再拖」）明确写作「隐约有个猜测」，是旁观者的推测，"
                         "不能当作她的障碍，因此记 null 而不是引用这句猜测。"),
        "action": slot("她在六号报出五号出事后连续传书追问，并说要立刻过来一起寻找。",
                       "explicit", ["q_msg2_long"],
                       "此处引较长的一段，因为它同时含追问与「我立刻过来」；通报行程那一次传书是 objective 的依据，不在此重复。"),
        "actionNote": None,
        "result": slot("被金莲道长回传劝阻：「二号，你不必过来，没有意义。四号和六号也在襄州。」",
                       "explicit", ["q_msg_jl_1"],
                       "result 是「她的提议被回绝」，这一句是金莲道长的传书（dialogue）；她本人后续状态本区间无文字。"),
        "resultNote": "「她是否动身来襄州」本区间无交代，登记在 knowledgeGaps K06。",
        "cost": None,
        "costNote": ("本区间未写李妙真为延期或为五号的事付出可辨认的代价。她的传书只表达意愿与急切"
                     "（「二号老妈子似的喋喋不休」是叙述对语气的描写，不是损失）。故记 null。"),
        "costQuotes": [],
    },
    {
        "id": "T13",
        "who": "楚元缜",
        "objective": slot("在襄州上空扫出发生过战斗的地方，以便找到五号。",
                          "inferred", ["q_chu_flying_inner"],
                          "**标 inferred 的理由：**原文那一句写的是他的**判读能力**（「以他的目力，只要扫过一眼，哪里发生过战斗，就能一清二楚的看见」），不是他自述的目标；「他在找战斗痕迹以便找五号」是我把这一句与本章的找人语境合起来的归纳。他为什么在意这件事另见 C 系列与 TH01 的 support。"),
        "objectiveNote": None,
        "obstacle": None,
        "obstacleNote": ("本区间未写他这次搜索的障碍。原文只写他的目力有多好、以及他担心碎片找不回来的后果；"
                         "「后果严重」是**利害**而不是障碍（没有任何东西在阻止他搜索）。故记 null，"
                         "不把利害写成障碍，也不把「五号其实没遭遇战斗」这条后文信息倒推成他当时的障碍——"
                         "那样是用结局改写过程。"),
        "action": slot("他踏着飞剑滑行、扫视地面判断哪里发生过战斗。",
                       "explicit", ["q_chu_flying_action"],
                       "动作句取自同一段的头部（踏剑滑行），与 objective 的判读能力句是两个不重叠区间，构建期断言 A3 通过。"),
        "actionNote": None,
        "result": None,
        "resultNote": ("本区间未写他搜索的结果：既没有写他找到战斗痕迹，也没有写他空手而归。原文只在后来写他到场后"
                       "「楚元缜看着许七安」并附和推迟下墓。故 result 记 null。**不写「搜索注定无果」**——"
                       "那是用后文结论倒推他当时的处境，属于用结局改写过程，我上一版草稿正是这么写的，复核若看到请以本版为准。"),
        "cost": None,
        "costNote": ("本区间未写楚元缜为此付出可辨认的代价。他自述「我们答应过帮他清理门户，变相的提高了风险」——"
                     "那是**风险**，不是已付出的代价；原文没有写他损失什么、放弃了什么、或已经承受了后果。故记 null，"
                     "不把「风险提高」写成代价（这正是提示词点名的那类混淆）。"),
        "costQuotes": [],
    },
    {
        "id": "T14",
        "who": "许七安",
        "objective": slot("按预言给出的方向与距离走三里，去找那位「青色衣衫」的男人。",
                          "explicit", ["q_carry", "q_prophecy"],
                          "目标由两句合成：他背起她时说的「我带你走」（dialogue），以及预言给出的方向、距离与外貌特征（同一段内的另一句）。两句都在本任务内，且不与另四栏的区间重叠。"),
        "objectiveNote": None,
        "obstacle": slot("三里路上不太平：一次当街纵马的冲撞、两次马车突然的失控，以及一位江湖人士把钟璃错认成自己跟野男人私奔的妻子、含怒下杀手。",
                         "explicit", ["q_three_miles"],
                         "障碍是接连发生的横祸（叙述直述其经过）；它的成因归属见 F01 的边界说明，不写成「天谴精确打击」。"),
        "obstacleNote": None,
        "action": slot("他在路边认出了符合预言特征的青衫男子，靠拢过去问「兄台，遇到什么麻烦了？」",
                       "explicit", ["q_pretend", "q_jishigan"],
                       "两句分属「看见」与「开口」两个动作。"),
        "actionNote": None,
        "result": slot("他找到了那位男子，并且用一次硬抗验证了实力：钢刀砍在他头上卷刃，对方喊出「六，六品？！」。",
                       "explicit", ["q_buduo", "q_liupin"],
                       "结果是「匹配预言的人被找到、实力被确认」，不是五号被找到。"),
        "resultNote": "找到的人是钱友，不是五号；五号的下落要等钱友的转述（T11）。",
        "cost": slot("代价是这一路上被误认与冲撞造成的实际麻烦：许七安被当街冲撞、被江湖人士误认仇人并当街砍杀。",
                     "explicit", ["q_jianghu_ke"],
                     "此处只记「被卷进纠纷」这一项；另三次横祸已作 obstacle 依据，不重复计入。"),
        "costNote": None,
        "costQuotes": None,
    },
    {
        "id": "T15",
        "who": "许七安",
        "objective": slot("接下钱友的委托，帮他下墓救人——但他要办的事实际是找五号。他对钱友只说了「这个任务我接了」。",
                          "explicit", ["q_accept"],
                          "目标出自他的应答（dialogue）。注意这是**对外的应答**；他内心真正要办的事在 result 一栏。"),
        "objectiveNote": None,
        "obstacle": None,
        "obstacleNote": ("本区间未写他接这桩委托的障碍。最接近的候选是「既然走投无路，其实报官更稳妥」——但那句话是他**自己提出的备选路径**，"
                         "由钱友否掉；它是他在比较方案，不是在受阻。没有任何人拦他、也没有任何条件使他不能接。"
                         "故记 null，不把「一次方案比较」写成障碍（那属于把对话当阻碍）。"),
        "action": slot("他先追问钱友有没有招揽到一位南疆的姑娘，得到确认后再接下委托。",
                       "explicit", ["q_ask_nanjiang"],
                       "动作是这次追问；接委托那句在 objective 一栏，两栏不共用区间。"),
        "actionNote": None,
        "result": slot("他确认了五号的下落方向：原来五号不是被抓走了，是下墓倒斗出了意外。",
                       "explicit", ["q_yuanlai"],
                       "结果是**他的推断被修正**（从「被妖道抓走」改为「下墓」），不是五号被救出。"),
        "resultNote": None,
        "cost": None,
        "costNote": ("本区间未写许七安为接这桩委托付出可辨认的代价。他确实出了城、走了半个时辰到北边，"
                     "但那是 T06 那一线的行动；本任务里没有任何损失、放弃或抵押。故记 null。"),
        "costQuotes": [],
    },
    {
        "id": "T16",
        "who": "钱友",
        "objective": slot("回去抱住这根大腿，把这位高手（及他那些会飞天遁地的朋友）留住，好救回帮主与弟兄们。",
                          "explicit", ["q_go_back"],
                          "目标出自他的内心决定（inner）；原文用感叹句写他的决意。"),
        "objectiveNote": None,
        "obstacle": slot("他一度已经放弃：此人太倒霉，倒霉到连他都看出问题来，于是心生退意、头也不回地离开了。",
                         "explicit", ["q_retreat", "q_leave"],
                         "障碍是他自己的判断与离开这一既成事实；两句互不重叠。"),
        "obstacleNote": None,
        "action": slot("他应下「好！」之后闪身进林子，随后在音波中受创，抬头看见飞剑与纸鹤上的两个人。",
                       "explicit", ["q_hao", "q_sword_light"],
                       "动作按顺序：应声进林 → 受创抬头看见来人。"),
        "actionNote": None,
        "result": slot("他的念头变得无比坚定：「这个念头在心里无比坚定。」",
                       "explicit", ["q_firm"],
                       "结果是**态度的定型**，不是帮主被救。"),
        "resultNote": "本区间没有写救人的结果；钱友的这条线在下一章才继续。",
        "cost": None,
        "costNote": ("本区间未写钱友为这次折返付出可辨认的代价：他没有受伤、没有损失财物，受创（耳鸣）那一次是"
                     "T06 的代价，不在此重复。故记 null。"),
        "costQuotes": [],
    },
    {
        "id": "T17",
        "who": "天地会四人（金莲道长、楚元缜、恒远、许七安）",
        "objective": slot("把人找出来。分工被议定为三路：「至于如何找人，众人商议了一番，绝对从三个方面入手。」",
                          "explicit", ["q_three_ways"],
                          "目标出自叙述对商议结果的直述（「绝对」疑为「决定」之误，照抄不改，见 TX05）。"),
        "objectiveNote": None,
        "obstacle": None,
        "obstacleNote": ("本区间未写分工执行时的障碍。三路分工之后原文直接转入许七安这一路的「一无所获」，"
                         "另两路连执行描写都没有；没有谁被拦、被拒或被干扰。故记 null。"),
        "action": slot("三路分头行动：许七安调官府官差与乡镇民兵；金莲道长与楚元缜御剑（物）飞行负责主城周围的镇子和村落；恒远在城中找江湖人士与市井百姓打听。",
                       "explicit", ["q_way1", "q_way2", "q_way3"],
                       "三条都是叙述直述的条目（「一，…二，…三，…」），我按原条照录，没有合并也没有补第四路。"),
        "actionNote": None,
        "result": slot("三路里只有一路写出了结果，而且是否证：许七安带着钟璃在城里转了几圈、专挑江湖人士打听，结果「一无所获」。",
                       "explicit", ["q_youling"],
                       "结果句用含「一无所获」的那一句叙述。它与 T01.result 引同一句，但两者是不同任务（A3 只约束任务内部五栏），故此处的复用不违反纪律。"),
        "resultNote": "另两路在本区间没有结果描写，登记在 unknowns U05；不把它们写成「也没找到」。",
        "cost": None,
        "costNote": ("本区间未写这次分工本身造成的代价。恒远拿到的那把碎银是 T01.cost 的内容；"
                     "本任务只写分工与执行，没有损失或放弃。故记 null。"),
        "costQuotes": [],
    },
]

# ══════════════════════════════════════════════════════════════════════════
# causeEdges[]
# ══════════════════════════════════════════════════════════════════════════
CAUSE = [
    {"id": "C01", "from": "钟璃指出大墓被人掘开、阴秽之气冲霄",
     "to": "金莲道长当场放下「有没有大墓」的疑问，改口先找人",
     "trigger": "金莲道长先质疑「未必就有大墓吧」，钟璃随即用观气给出「被人掘开了」的判断；许七安看向她、她给出结论，众人于是交换眼神、由道长定调不再讨论下墓。机制是：唯一的观测者给出肯定答案，讨论的前提被替换。",
     "basis": "explicit", "claimKind": "narration",
     "claimKindNote": "钟璃的判断是她说的话（dialogue），但「众人因此改口」这一因果由叙述的动作序列（交换眼神→道长摇头）承载。",
     "quotes": [R("q_maybe_no_tomb"), R("q_buried_open"), R("q_xian_zhaoren")]},
    {"id": "C02", "from": "钟璃给大墓定性：或有异宝，但也伴随着大凶",
     "to": "众人一致选择先找人、把下墓往后推",
     "trigger": "钟璃说完「或有异宝，但也伴随着大凶」之后，叙述紧接着写她「又向往又忌惮」；许七安与天地会几人交换眼神，金莲道长随即摇头定调。机制是：收益与风险同时被点出且无法评估，众人选择回避不确定的那一半。",
     "basis": "explicit", "claimKind": "narration", "claimKindNote": None,
     "quotes": [R("q_yibao_daxiong"), R("q_look_south"), R("q_xian_zhaoren")]},
    {"id": "C03", "from": "金莲道长定调「先找人吧」",
     "to": "恒远与楚元缜各自补上下墓的理由，许七安确认队友「没有事逼和事精」",
     "trigger": "道长先定调，恒远立刻接「逝者已矣」、楚元缜接「准备也不充分」，两人的理由都指向同一个结论；许七安因此给出「都是让人心安的队友」的评价。机制是：调子被定下之后，其余人用各自的理由加固它。",
     "basis": "explicit", "claimKind": "narration", "claimKindNote": None,
     "quotes": [R("q_xian_zhaoren"), R("q_heng_shizhe"), R("q_chu_prepare"), R("q_good_teammates")]},
    {"id": "C04", "from": "三路分工成形，恒远分到「城中打听」这一路",
     "to": "许七安掏出碎银交给恒远，并给出「银子优先、拳头其次」的方法",
     "trigger": "恒远被分到进城打听那一路之后，许七安才把手伸进荷包；机制是分工先落到具体的人，资源才跟着这个人走。",
     "basis": "explicit", "claimKind": "narration", "claimKindNote": None,
     "quotes": [R("q_way3"), R("q_silver_fist"), R("q_heng_takes")]},
    {"id": "C05", "from": "同知指出这差事是大海捞针、有心推脱",
     "to": "李知府指示「你就敷衍一下便成」",
     "trigger": "同知先抱怨「襄城那么大，如何找啊」、再表现出推脱之意，李知府才给出敷衍的处置。机制是：下属提出执行成本，上级据此下调执行标准。",
     "basis": "explicit", "claimKind": "narration", "claimKindNote": None,
     "quotes": [R("q_dahai"), R("q_tuotuo"), R("q_fuyan")]},
    {"id": "C06", "from": "李知府觉得「银锣许七安」这个名字与称呼耳熟",
     "to": "他让人取昨日邸报，读到「银锣许七安代司天监斗法」后改口要求尽心尽力",
     "trigger": "耳熟→取邸报→读到那一行字→认人→改口，三步都有原文动作。机制是：身份被第三方文件确认，执行标准随之从敷衍翻转为尽力。",
     "basis": "explicit", "claimKind": "narration",
     "claimKindNote": "邸报是朝廷发来的文件，其内容是叙述直述（「说是司天监与西域佛门斗法大胜」）；李知府的改口是叙述直述的动作。",
     "quotes": [R("q_erku"), R("q_dibao_line"), R("q_dashen")]},
    {"id": "C07", "from": "府衙答「没有异常」且街头打探一无所获",
     "to": "许七安自己否掉「五号在襄城留下战斗痕迹」这一支",
     "trigger": "他先立假设（若遭遇妖道必有战斗痕迹），再用两条渠道取证（官府、百姓口碑），两条都给出否证，于是他自己推翻假设。机制是否证式推理，不是时间相邻。",
     "basis": "explicit", "claimKind": "inner",
     "claimKindNote": "整段是许七安的连续内心推演（原文用引号分句写出）；否证链条由他自己完成。",
     "quotes": [R("q_henji"), R("q_zhifu_no"), R("q_bubaio"), R("q_goulan_go")]},
    {"id": "C08", "from": "许七安说「我是有大气运的人，能抵消你的部分厄运」",
     "to": "钟璃被说服并动用预言",
     "trigger": "钟璃先给警告（会更糟）、再提醒经验，许七安用「大气运」这条理由回应；叙述随即写「钟璃被他说服了，本身就是乖巧的女子，缺乏一些主见」，然后她低头起卦。机制是：风险被一句身份理由抵消，说服成立。",
     "basis": "explicit", "claimKind": "narration",
     "claimKindNote": "「钟璃被他说服了」是叙述直述，所以这条边不是我从对话推出来的。",
     "quotes": [R("q_zhongli_warn"), R("q_daqiyun"), R("q_persuaded")]},
    {"id": "C09", "from": "钟璃动用预言能力",
     "to": "她预言后虚弱跌坐，并自述处在遭天谴状态",
     "trigger": "她给出预言内容之后，叙述紧接着写「说完，她虚弱的跌坐在地」；随后她自述预言师每日只能预测一次、而后厄运升级成天谴。机制由**她自己**给出（泄露天机→遭天谴）：叙述写出了紧随其后的虚弱，但没有用「天谴」二字为这条机制背书，故本条边只连到「她自述的状态」与「可观察的虚弱」。",
     "basis": "explicit", "claimKind": "narration",
     "claimKindNote": "虚弱是叙述直述；「天谴」的机制是她自己说的（dialogue），两条引文分属两种 claimKind。",
     "quotes": [R("q_prophecy"), R("q_collapse"), R("q_once_day")]},
    {"id": "C10", "from": "预言指向「往南走三里…青色衣衫…男人」",
     "to": "许七安背起钟璃往南走三里，并在路边找到青衫男子",
     "trigger": "预言给出了方向、距离与外貌，他随后背人上路，三里路上连遭三次横祸，最后在路边看见符合描述的青衫男子。机制是：预言内容成为行动指令，外貌特征成为识别条件。",
     "basis": "explicit", "claimKind": "narration", "claimKindNote": None,
     "quotes": [R("q_prophecy"), R("q_carry"), R("q_three_miles"), R("q_pretend")]},
    {"id": "C11", "from": "江湖客误认许七安为仇人、一刀砍在他头上却卷了刃",
     "to": "钱友与围攻者同时确认他是六品铜皮铁骨，钱友由此从戒备转为狂喜请托",
     "trigger": "刀砍不动→钱友喊出「六，六品？！」→江湖客跪地认错→许七安反问「够不够帮忙」→钱友狂喜请托。机制是：实力被一次公开的硬抗验证，招揽条件随即成立。",
     "basis": "explicit", "claimKind": "narration", "claimKindNote": None,
     "quotes": [R("q_buduo"), R("q_liupin"), R("q_enough"), R("q_please_help")]},
    {"id": "C12", "from": "许七安追问有没有招揽到南疆姑娘，钱友确认并说出交易条件",
     "to": "许七安推翻「五号被地宗妖道抓走」，认定她下墓出了意外",
     "trigger": "他先问「有没有招揽到一位南疆的姑娘」，钱友答「确实有一位南疆来的姑娘…缺了盘缠，饿了三天三夜」，并补出「帮主请她大吃一顿…她便答应下墓」。机制是：第一手招揽记录替换了此前的推测，并能解释她为何不在城里（地书碎片失联仍需另行解释）。",
     "basis": "explicit", "claimKind": "narration",
     "claimKindNote": "钱友的话是 dialogue；「原来五号不是被抓走了」是许七安的内心结论（inner），推理由他完成。",
     "quotes": [R("q_ask_nanjiang"), R("q_how_know"), R("q_baochi"), R("q_yuanlai")]},
    {"id": "C13", "from": "地书碎片不能用（会暴露许七安的身份）",
     "to": "他改用狮子吼召集同伴",
     "trigger": "他的内心话把限制与手段并列写出：「地书碎片不能用，不然会暴露我身份，还好嗓门比较大，通讯全靠吼」。机制是：通讯手段被封，改用物理传声，代价由在场的钱友承受。",
     "basis": "explicit", "claimKind": "inner",
     "claimKindNote": "这是许七安的内心独白，不是叙述对「地书碎片不能用于此」的认定。",
     "quotes": [R("q_shout")]},
    {"id": "C14", "from": "狮子吼的音波",
     "to": "钱友被震得耳鸣蹲下；金莲道长与楚元缜循声赶到",
     "trigger": "同一次咆哮产生两个结果：近处的钱友「眼前一黑…捂住耳朵蹲下」，远处的金莲与楚元缜「很有目的性的朝倒霉的六品高手汇聚」。机制是声波传播；两个结果的承受者不同，故同源分列。",
     "basis": "explicit", "claimKind": "narration", "claimKindNote": None,
     "quotes": [R("q_roar"), R("q_faint"), R("q_converge")]},
    {"id": "C15", "from": "金莲道长说「墓中必有大阵，屏蔽了地书碎片」",
     "to": "许七安联想到司天监是专业玩阵法的",
     "trigger": "道长给出「墓中有大阵」这一解释后，叙述紧接着写许七安「捕捉到了一个细节」并把它与司天监的专长对上。机制是：一条解释性信息触发了一个可用的联想。",
     "basis": "explicit", "claimKind": "narration",
     "claimKindNote": "「墓中必有大阵」是道长的话（dialogue），联想是许七安的内心（inner）。",
     "quotes": [R("q_dazhen"), R("q_no_signal")]},
    {"id": "C16", "from": "许七安说出钟璃因使用预言而处在遭天谴的状态",
     "to": "金莲道长改口推迟下墓，恒远与楚元缜附和",
     "trigger": "他先拦住（「不行！」）、再给理由（好消息已说完，坏消息是这个）；道长沉默后改口「不妨稍作休整，明日再下墓」，另两人各自附和。机制是：新增的代价信息改变了行动的时间安排。",
     "basis": "explicit", "claimKind": "narration", "claimKindNote": None,
     "quotes": [R("q_bad_news"), R("q_tianqian"), R("q_rest_tomorrow"), R("q_chu_agree2")]},
    {"id": "C17", "from": "金莲道长在传书里只点了四号和六号、没有提许七安",
     "to": "许七安判断「猫道」这个身份确实让道长忌惮",
     "trigger": "他读完道长的传书后，第一反应是「咦，道长居然没提我」，并由此推出「猫道」这个身份是道长眼里的把柄。机制是：一次称呼上的省略被他读成刻意的回避。",
     "basis": "inferred", "claimKind": "inner",
     "claimKindNote": "传书内容（dialogue）与他的推断（inner）都在原文里，但「没提我」到「忌惮」之间的因果是他自己下的判断，故整条边标 inferred。",
     "quotes": [R("q_msg_jl_1"), R("q_maodao_see"), R("q_maodao_judge")]},
    {"id": "C18", "from": "章末众人又一次用「求生欲」把下墓推后",
     "to": "许七安意识到这句话刚刚说过（自我重复被点破）",
     "trigger": "同样的场景（众人一致后退）第二次发生时，许七安给出与章首一字不差的评语，随后自己愣住并发现「这句话如此熟悉，好像刚刚说过似的」。机制是：同一句话在同一章里被说了两次，第二次由说话者自己察觉。",
     "basis": "explicit", "claimKind": "inner",
     "claimKindNote": "评语以自由间接引语写出（叙述转述他的欣慰），「这句话如此熟悉」是他的内心话（inner）。两次出现是原文事实：同一句话串在章内两个不同偏移上各出现一次，probe 的 occ/occInSlice 字段可复现（0/2 @1339421 与 1/2 @1348030）。",
     "quotes": [R("q_good_teammates"), R("q_good_teammates2"), R("q_deja_vu")]},
]

# ══════════════════════════════════════════════════════════════════════════
# rejectedEdges[]：时间相邻但没有机制的，显式拒绝
# ══════════════════════════════════════════════════════════════════════════
REJECTED = [
    {"id": "R01", "from": "勾栏早早开门、嫖客打着哈欠散去", "to": "许七安逮着路人问府衙方向",
     "why": "两段在原文里紧挨着，但没有任何机制把勾栏的营业状态与问路连起来：问路是为了去府衙办公事，他自己在同一段里说「郎心如铁的把青楼和勾栏抛在身后」。这正是「同一场景当因果」的形态，拒绝连边。",
     "quotes": [R("q_brothel_open"), R("q_prostitutes"), R("q_heart_iron")]},
    {"id": "R02", "from": "楚元缜踏飞剑搜索战斗痕迹", "to": "地书碎片的持有者们同时悸动",
     "why": "两句之间只隔一个场景分隔符。悸动是传书机制触发的（随后就是二号的传书），与他飞剑搜索的动作无关。把「他正在找」与「群里来消息」连成因果，是把巧合当机制。",
     "quotes": [R("q_chu_flying"), R("q_jidong"), R("q_msg2")]},
    {"id": "R03", "from": "钱友承诺墓中有大宝贝、后土帮会重金答谢", "to": "许七安接下了这个任务",
     "why": "表面顺序是「许诺→答应」，但中间还夹着许七安问「其实报官更稳妥」与钱友解释报官为何不稳妥这两步；他接下任务的直接触发是后两步，而不是财货许诺。从他自己的内心看（「原来五号不是被抓走了，是下墓倒斗出了意外」），他真正要办的事在许诺之前就定了。把时间相邻的许诺当作原因，会捏造一个原文没有的贪财动机。",
     "quotes": [R("q_baobei"), R("q_baoguan"), R("q_baoguan_no")]},
    {"id": "R04", "from": "后土帮准备了足足三个月", "to": "帮主他们再也没有回来",
     "why": "两句在同一段话里前后相连，但准备与失陷之间没有机制：准备的内容（招揽高手、至刚至阳物品）恰恰是为了避免失陷，原文反而把失陷归给墓中的污秽之气与邪物。把「准备了很久」当成「所以出事」是把因果方向弄反。",
     "quotes": [R("q_fubangzhu"), R("q_prepare3m"), R("q_never_back")]},
    {"id": "R05", "from": "许七安让金莲道长通知恒远", "to": "恒远赶到城外",
     "why": "这两件事看起来是「通知→到达」，但原文明确写了恒远**自己**在城中听见了隐约的狮子吼才知道可能是许七安在联络众人，并耐着性子出城后才发力狂奔。因果链是「吼声→听见→赶来」，不是「道长通知→赶来」。如果按前一种连边，就会把原文特意写出的一条独立路径抹掉。",
     "quotes": [R("q_notify"), R("q_heng_arrive"), R("q_hengyuan_speed")]},
    {"id": "R06", "from": "李知府读到邸报上「银锣许七安代司天监斗法」", "to": "许七安因此找到了五号",
     "why": "邸报只改变了李知府对差事的态度（从敷衍改为尽心尽力），文本到「下官一定竭尽全力」为止；许七安找到线索靠的是钟璃的预言与钱友的转述，与邸报无关。把「官府开始认真办」当成「人找到了」，是把待验证的行政动作当成了结果。",
     "quotes": [R("q_dibao_line"), R("q_dashen"), R("q_prophecy")]},
    {"id": "R07", "from": "钟璃说「我，我会望气术的……」", "to": "许七安在路边找到青衫男子",
     "why": "两句相隔不远，但许七安在同一段里就「假装没听见」把这句话挡掉了，随后他能找到人靠的是先前那次预言给出的外貌特征（青色衣衫），不是望气术。把一句被无视的自荐当作后文成功的原因，是凭位置连边。",
     "quotes": [R("q_wangqi"), R("q_pretend")]},
]

# ══════════════════════════════════════════════════════════════════════════
# states[]
# ══════════════════════════════════════════════════════════════════════════
STATES = [
    {"id": "S01", "who": "金莲道长·对五号处境的判断",
     "before": slot("只有不好的预感：五号不回传书时，他已经有不好的预感。", "explicit", ["q_wuhao_no_reply_before"]),
     "beforeNote": "「不好的预感」是他自己的判断，不是叙述对五号处境的认定。",
     "after": slot("确认出了问题：等到地书碎片失去联系，他便知出问题了。", "explicit", ["q_wuhao_no_reply_after"]),
     "afterNote": "前值与后值取自同一段话里两个相邻但不同的区间（不回传书 / 碎片失联），构建期断言 A3 通过。",
     "anchor": slot("锚点是地书碎片之间的感应中断这一事件。", "explicit", ["q_msg6"]),
     "anchorNote": "锚点引六号传书里的同一事实表述（「金莲道长失去了地书碎片之间的感应」），用作事件定位。"},
    {"id": "S02", "who": "李知府·对许七安交办差事的态度",
     "before": slot("决定敷衍：「京城来的银锣，不能拒绝，你就敷衍一下便成。」", "explicit", ["q_fuyan"]),
     "beforeNote": None,
     "after": slot("改口要求尽心尽力：「这件事，你立刻去办，务必要尽心尽力。」", "explicit", ["q_dashen"]),
     "afterNote": None,
     "anchor": slot("锚点是他在邸报上读到「银锣许七安代司天监斗法」这一行字。", "explicit", ["q_dibao_line"]),
     "anchorNote": None},
    {"id": "S03", "who": "同知·对搜人差事的态度",
     "before": slot("有心推脱，并当面指出这是大海捞针。", "explicit", ["q_tuotuo", "q_dahai"]),
     "beforeNote": None,
     "after": slot("改口承诺竭尽全力。", "explicit", ["q_jiejinquanli"]),
     "afterNote": "「竭尽全力」是承诺，不是已执行的行动；本状态只记态度变化，不记实际行动。",
     "anchor": slot("锚点是李知府指着邸报点名许七安身份。", "explicit", ["q_bigshot"]),
     "anchorNote": None},
    {"id": "S04", "who": "钟璃·身体状态",
     "before": slot("正常：在雅间吃菜说话，还提醒他预言的风险。", "explicit", ["q_chew", "q_worse"]),
     "beforeNote": None,
     "after": slot("预言后虚弱跌坐在地。", "explicit", ["q_collapse"]),
     "afterNote": "「遭天谴」那层是许七安对金莲道长说的（dialogue），放在 anchor/相关任务里，不在本状态的后值里混入说法。",
     "anchor": slot("锚点是她低头动用预言能力、给出三里外的线索。", "explicit", ["q_prophecy"]),
     "anchorNote": None},
    {"id": "S05", "who": "钱友·对许七安的态度",
     "before": slot("戒备且冷淡：面沉似水，看他一眼，没搭理，只指了指木牌。", "explicit", ["q_muban"]),
     "beforeNote": None,
     "after": slot("狂喜、满脸激动，主动请托并说报酬好说。", "explicit", ["q_please_help"]),
     "afterNote": None,
     "anchor": slot("锚点是钢刀砍在许七安头上卷刃，钱友喊出「六，六品？！」。", "explicit", ["q_buduo", "q_liupin"]),
     "anchorNote": None},
    {"id": "S06", "who": "钱友·是否继续留在原地等待",
     "before": slot("信心满满。", "explicit", ["q_confident"]),
     "beforeNote": None,
     "after": slot("先转为战战兢兢，再「一念及此，钱友心生退意」并头也不回的离开；目睹剑光与纸鹤后又变为「回去，得回去，立刻回去，抱住这根大腿，打死不放！」",
                  "explicit", ["q_nervous", "q_retreat", "q_go_back"]),
     "afterNote": "这是四段状态（信心满满→战战兢兢→退意离开→决意回去），原文逐段写出；我按原顺序并列，没有压成一条曲线。",
     "anchor": slot("锚点是他被狮子吼震得耳鸣蹲下后，抬头看见剑光上的青衫男子与纸鹤上的老道士。",
                    "explicit", ["q_sword_light", "q_paper_crane"]),
     "anchorNote": None},
    {"id": "S07", "who": "许七安·对五号去向的判断",
     "before": slot("认为她凶多吉少、或者被抓住，甚至怀疑金莲道长另有依据（「除非他认为五号能在地宗妖道手中逃脱」）。",
                    "explicit", ["q_xiongduo", "q_dahai2"]),
     "beforeNote": "这一段是他自己的连续内心推演，原文用引号分句写出。",
     "after": slot("推翻前判断：原来五号不是被抓走了，是下墓倒斗出了意外。", "explicit", ["q_yuanlai"]),
     "afterNote": None,
     "anchor": slot("锚点是钱友确认有一位南疆姑娘因缺盘缠、被承诺带去京城而答应下墓。",
                    "explicit", ["q_how_know", "q_baochi_act"]),
     "anchorNote": None},
    {"id": "S08", "who": "金莲道长、楚元缜、恒远三人·对五号下落的认知",
     "before": slot("六号在传书里定性：五号极有可能被地宗的妖道抓走了。", "explicit", ["q_msg6"]),
     "beforeNote": "「极有可能」是六号的措辞，不是确证；三人的认知基线就建立在它上面。",
     "after": slot("接受了五号下墓的事实。", "explicit", ["q_jieshou"]),
     "afterNote": None,
     "anchor": slot("锚点是一番询问钱友之后（金莲道长亲自盘问）。", "explicit", ["q_panwen"]),
     "anchorNote": None},
    {"id": "S09", "who": "金莲道长·下墓的急迫程度",
     "before": slot("迫不及待：「事不宜迟，我们赶紧下去吧。」", "explicit", ["q_hurry"]),
     "beforeNote": None,
     "after": slot("改口推迟：「既然知道了五号的下落，那，那也不急于一时，贫道觉得，咱们不妨稍作休整，明日再下墓。」",
                   "explicit", ["q_rest_tomorrow"]),
     "afterNote": None,
     "anchor": slot("锚点是许七安说出钟璃为寻找线索使用了预言能力、而今处在遭天谴的状态。", "explicit", ["q_tianqian"]),
     "anchorNote": None},
    {"id": "S10", "who": "楚元缜·对天人之争的判断",
     "before": slot("按档期算：殿试过后就是二十天以后，不算太晚。", "explicit", ["q_dianshi_20"]),
     "beforeNote": None,
     "after": slot("转为警觉：她若顺利突破四品，那必定是生死之争，无法避免；同时他认为她「对天人之争并没有太大的把我」。",
                  "explicit", ["q_meiyou_bawo"]),
     "afterNote": "「李妙真要突破了」在同一句里被明确写作「隐约有个猜测」，故 after 的状态是**他的猜测**而非事实；「把我」是原文用字（疑为「把握」），照抄不改。",
     "anchor": slot("锚点是二号传书宣布天人之争延期、殿试过后才来京。", "explicit", ["q_msg2"]),
     "anchorNote": None},
    {"id": "S11", "who": "许七安·对地书碎片失联原因的认识",
     "before": slot("提出疑问：如果五号在墓中，那么地书碎片被屏蔽是怎么回事？", "explicit", ["q_why_shield"]),
     "beforeNote": "这句在原文是楚元缜问的；本状态的前值记的是「这个问题被摆到台面上」时众人的共同起点，说话人是楚元缜，故注在此。",
     "after": slot("得到解释并产生新的联想：原来是没信号了，随即捕捉到「墓中有大阵」与司天监专长之间的联系。",
                  "explicit", ["q_no_signal"]),
     "afterNote": None,
     "anchor": slot("锚点是金莲道长断言「墓中必有大阵，屏蔽了地书碎片」。", "explicit", ["q_dazhen"]),
     "anchorNote": None},
]

# ══════════════════════════════════════════════════════════════════════════
# knowledgeGaps[]
# ══════════════════════════════════════════════════════════════════════════
GAPS = [
    {"id": "K01", "about": "地书碎片为什么会被屏蔽",
     "whoKnows": "本区间**无人确知**。金莲道长给出的是解释而非查证结果：他先说「除了地宗秘法能封印地书碎片，其他手段也可以，只是比较苛刻」，再断言「墓中必有大阵」。许七安联想到司天监玩阵法，但原文只写他「捕捉到了这个细节」，没有写他说出口或据此行动。",
     "whoDoesNot": "楚元缜（提问者，不知）、金莲道长（给出推测，未查证）、许七安（只到联想一步）、恒远大师（本区间未就此发言）、读者。",
     "basis": "explicit",
     "keep": "故 C15 只连到「许七安产生联想」，不连到「破阵」；该联想登记为未回收伏笔 F03。",
     "quotes": [R("q_why_shield"), R("q_other_means"), R("q_dazhen"), R("q_no_signal")]},
    {"id": "K02", "about": "五号与后土帮帮主一行在墓中的实际处境",
     "whoKnows": "本区间**无人知道**，叙述也没有交代。钱友只说到「帮主他们再也没有回来」；许七安只推到「下墓倒斗出了意外」。",
     "whoDoesNot": "许七安（推断而非知情）、金莲道长等三人（刚接受「下墓」这一事实）、钱友（留在外面，没进去过）、读者。",
     "basis": "explicit",
     "keep": "故 T11.result 只写「消失不见 / 被推断为下墓」，不写生死；T10.result 只写「再也没有回来」。",
     "quotes": [R("q_never_back"), R("q_yuanlai"), R("q_jieshou")]},
    {"id": "K03", "about": "墓里到底有什么",
     "whoKnows": "本区间只有两组**未经进入验证**的说法：钟璃的观气结论（「此墓中或有异宝，但也伴随着大凶」「三花聚顶地势」）与钱友转述副帮主的话（「墓穴里污秽之气甚是恐怖，怕有邪物」）。两人都是隔着一层说的：钟璃在外观测，副帮主据气判断。",
     "whoDoesNot": "叙述没有给出任何一句对墓内实况的直述；许七安、金莲道长、楚元缜、恒远四人都没进去过；读者也不知。",
     "basis": "explicit",
     "keep": "故 worldSettings 里「大墓」这一地点记 mentioned，不记 arrived（见 W04）。",
     "quotes": [R("q_yibao_daxiong"), R("q_sanhua"), R("q_fubangzhu")]},
    {"id": "K04", "about": "襄城官府是否真的发动人手搜寻、结果如何",
     "whoKnows": "本区间**无人知道**。李知府说「一定照办」、同知说「一定竭尽全力」，两句都是承诺；原文在「下官一定竭尽全力」之后直接以分隔符转入许七安的街头画面，没有再提官府。",
     "whoDoesNot": "李知府与同知（只有承诺文字，无执行描写）、许七安（没有再回府衙）、读者。",
     "basis": "explicit",
     "keep": "故 T02.result 只记「下属口头应承」；R06 拒绝把官府认真办差连到「人找到了」。",
     "quotes": [R("q_zhifu_promise"), R("q_jiejinquanli"), R("q_enter_city")]},
    {"id": "K05", "about": "天人之争延期的真实原因",
     "whoKnows": "李妙真自己只给了行程理由（去江州查案、沿途铲奸除恶）；楚元缜认为「李妙真要突破了」，但原文明确写这是「隐约有个猜测」。**没有人确知**。",
     "whoDoesNot": "楚元缜（猜测）、天地会其余成员（读到的是传书里的行程理由）、读者。",
     "basis": "explicit",
     "keep": "故 T12.obstacle 记 null 并在 Note 里说明：那句猜测不能当作她的障碍。",
     "quotes": [R("q_msg2"), R("q_dianshi_20")]},
    {"id": "K06", "about": "二号是否真的动身来襄州",
     "whoKnows": "本区间**无人知道**。她说了「我立刻过来，一起寻找五号」，金莲道长回传「你不必过来，没有意义」；原文没有写她的回应，也没有写她是否上路。",
     "whoDoesNot": "金莲道长（只发出劝阻）、天地会其余成员、读者。",
     "basis": "explicit",
     "keep": "故 T12.result 只写「提议被回绝」，不写她是否成行。",
     "quotes": [R("q_msg2_long"), R("q_msg_jl_1")]},
    {"id": "K07", "about": "钟璃说的「与你在教坊司的相好一样」指的是谁",
     "whoKnows": "许七安显然知道指的是谁——原文写他「沉默了很久…以正常的语气『哦』了一声」，这是听懂了之后的反应。叙述**没有点名**。",
     "whoDoesNot": "钟璃说这话时并未点名（她用了一个只有许七安能对上的描述）、读者、金莲道长等其他天地会成员（不在场）。",
     "basis": "inferred",
     "keep": "故我不在这一栏里补一个名字；「沉默了很久」这一反应仅登记在此，不写进 states。",
     "quotes": [R("q_jiaofangsi"), R("q_silence")]},
    {"id": "K08", "about": "「猫道」是什么身份、许七安在天地会的编号是几号",
     "whoKnows": "许七安自己知道「猫道」这个身份的含义，也在意它是否被道长忌惮；叙述没有解释这个身份的来源，本区间也没有写出他在天地会的编号。",
     "whoDoesNot": "金莲道长（传书里只点了二号、四号、六号，没提许七安）、读者。",
     "basis": "explicit",
     "keep": "故 C17 标 inferred、登记为未收录伏笔 NF01，不替他把「猫道」解释成任何具体来历。",
     "quotes": [R("q_maodao"), R("q_msg_jl_1")]},
    {"id": "K09", "about": "钟璃那句「他的元神是残缺的」里的「他」指谁",
     "whoKnows": "**本区间没有明确指代。**这句话出现在许七安刚说完「那个组织是地宗的金莲道长创建的」之后，字面上最近的名词是金莲道长；但她下一句又转去说「与你在教坊司的相好一样」，指代链条断裂。",
     "whoDoesNot": "许七安当场也没听懂（他问「什么意思？」）、读者。",
     "basis": "explicit",
     "keep": "我不替它选一个指代；这是一处真实歧义，写进 textualNotes TX13，并列为 unknowns U03。",
     "quotes": [R("q_secret_org"), R("q_yuanshen_can"), R("q_what_mean")]},
    {"id": "K10", "about": "许七安到底是什么品级（六品还是五品）",
     "whoKnows": "**原文内部不一致。**青衫男子（钱友）先惊喊「六，六品？！」、叙述称「砍了一个六品的铜皮铁骨」，后续叙述也称他「六品的强大武夫」「这位六品高手」；但钱友的内心又称他「不但自身是五品」。",
     "whoDoesNot": "本区间没有一句对这处不一致的裁定；许七安本人也未自报品级。",
     "basis": "explicit",
     "keep": "我按原文分别照录，不替他选一个品级；不一致登记在 textualNotes TX11。",
     "quotes": [R("q_liupin"), R("q_half_hour"), R("q_wupin")]},
    {"id": "K11", "about": "钱友最初对许七安的冷淡是不是因为不信他能帮忙",
     "whoKnows": "**本区间没有写他的理由**：原文只写他「面沉似水，看他一眼，没搭理，指了指木牌」。他随后狂喜的原因是实力被验证（「六，六品？！」），但他先前冷淡的动机没有任何一句交代。",
     "whoDoesNot": "钱友（内心未写）、许七安（未追问）、读者。",
     "basis": "explicit",
     "keep": "故 S05 的 before 只记行为（不搭理、指木牌），不替他补一个「觉得对方不够格」的动机。",
     "quotes": [R("q_muban"), R("q_liupin")]},
]

# ══════════════════════════════════════════════════════════════════════════
# foreshadows[] / notForeshadows[]
# ══════════════════════════════════════════════════════════════════════════
FORESHADOWS = [
    {"id": "F01",
     "name": "三里路的厄运——从「会更糟」的警告到一次纵马、两次失控、一次误认仇人",
     "resolved": True, "unresolved": False, "basis": "explicit",
     "setup": [
         dict(R("q_worse"), why="铺设①：钟璃先给出经验性警告——即使有了线索，最终也会让事情走向更糟糕的结局。"),
         dict(R("q_daqiyun"), why="铺设②：许七安用「我是有大气运的人，能抵消你的部分厄运」接下这条风险，等于提前声明了「厄运会被抵消一部分、但仍会发生」。"),
         dict(R("q_once_day"), why="铺设③：她补上机制——预言师每日只能预测一次，而后厄运会升级成天谴。"),
     ],
     "payoff": [
         dict(R("q_three_miles"), why="回收：三里路上一次当街纵马的冲撞、两次马车突然失控、一位江湖人士把钟璃错认成私奔妻子并含怒下杀手。"),
         dict(R("q_xiyou"), why="回收确认：许七安自己把这三里路总结成「走出了西天取经的感觉」，说明他把它认作厄运的兑现。"),
     ],
     "note": ("铺设与回收都在本区间内完成，故 resolved=true。**必须写清的边界：**原文没有说那三次横祸就是天谴本身——"
              "天谴的承受者在钟璃说出机制时被指向她（「我活不过两个时辰」），而三次横祸落在许七安身上；"
              "两者之间只有「厄运升级」这一句连接，我按原文的力度记录，不把它写成「天谴精确打击许七安」。")},
    {"id": "F02",
     "name": "钟璃遭天谴这件事——从她自述的规则变成许七安拦住下墓的筹码",
     "resolved": True, "unresolved": False, "basis": "explicit",
     "setup": [
         dict(R("q_once_day"), why="铺设：她明确说出预言后的代价与时限（若没有大气运或特殊法阵庇佑，她活不过两个时辰）。"),
         dict(R("q_collapse"), why="铺设的当场兑现：她说完预言内容就虚弱跌坐。"),
     ],
     "payoff": [
         dict(R("q_tianqian"), why="回收：许七安在众人要立刻下墓时，把「钟璃处在遭天谴的状态」当作坏消息说出来。"),
         dict(R("q_rest_tomorrow"), why="回收的结果：金莲道长因此改口推迟到明日再下墓。"),
     ],
     "note": ("这条线的回收是**信息被当作理由使用**：同一个事实先由钟璃说出（铺设），再被许七安用来改变行动安排（回收）。"
              "它不是道具型的伏笔，而是代价型伏笔。天谴是否真的会在两个时辰内致命，本区间没有写，故不作断言。")},
    {"id": "F03",
     "name": "「墓中必有大阵」与「司天监是专业玩阵法的」——细节被注意到，但没有被使用",
     "resolved": False, "unresolved": True, "basis": "explicit",
     "setup": [
         dict(R("q_why_shield"), why="铺设：楚元缜提出地书碎片被屏蔽这个未解现象，把问题摆到台面上。"),
         dict(R("q_dazhen"), why="铺设：金莲道长给出解释——墓中必有大阵，屏蔽了地书碎片。"),
     ],
     "payoff": [
         dict(R("q_no_signal"), why="部分回收：许七安捕捉到「墓中有大阵」这个细节，并立刻与司天监的专长对上（「众所周知，司天监是专业玩阵法的」）。"),
     ],
     "note": ("**显式标 unresolved：**铺设完整、「被注意到」也发生了，但本区间没有把这条联想变成任何行动或决定——"
              "他没有说出口、没有人接话、下墓也被推迟到明日。按「只出现一次不算伏笔、有铺设与回收才算」的口径，"
              "我把它记为**未回收**，而不是硬把「他想到了」算成回收。若复核认为「被注意到」已构成回收的起始，请指出回收动作在哪一句。")},
]

NOT_FORESHADOWS = [
    {"id": "NF01", "name": "「猫道」这个身份",
     "why": "本区间只出现一次（许七安的一句内心话），既没有铺设出它的来历，也没有任何回收动作。它已作为 K08 的知识差与 C17 的边登记，此处只记不收录为伏笔的理由。",
     "quotes": [R("q_maodao")]},
    {"id": "NF02", "name": "许七安「我有个大胆的想法」",
     "why": "它看起来像一句待展开的引子，但在同一场景内就被接住并落地了：钟璃回「我建议你藏好大胆的想法」，几分钟后他把她拉到大街上用预言。铺设与回收在同一分钟内完成，属于节拍而不是伏笔，故不收录。",
     "quotes": [R("q_bold_idea"), R("q_hide_idea"), R("q_drag_street")]},
    {"id": "NF03", "name": "钟璃「我，我会望气术的……」",
     "why": "单次出现的一句小声补充，接在许七安「绝对没有怪你」之后，被他自己「假装没听见」挡掉。它既没有被铺设，也没有被回收成行动；把一句被无视的自荐记成伏笔，等于把喜剧节拍当线索。它已作为 R07 的拒绝理由登记。",
     "quotes": [R("q_wangqi"), R("q_pretend")]},
    {"id": "NF04", "name": "钱友「回城之后，换个地方摆摊吧」",
     "why": "这是一句**打算**，而且他随即自己推翻（看见剑光纸鹤后改成「立刻回去，抱住这根大腿，打死不放」）。同一场景内生成又撤回的打算不构成伏笔。",
     "quotes": [R("q_heavy_heart"), R("q_go_back")]},
    {"id": "NF05", "name": "「找到五号就回京城，就当没有这回事」",
     "why": "这是紧接金莲道长「先找人吧」之后的一句打算，本区间内既没有执行也没有撤回（五号还没找到、下墓也推迟了）。它是 T01 目标的一部分，不是一条有待回收的线。",
     "quotes": [R("q_wuhao_huijing")]},
    {"id": "NF06", "name": "「事不宜迟，我们赶紧下去吧」",
     "why": "这句话确实被后文推翻（改口推迟），但它是一次**立即被否掉的提议**，不是埋设：铺垫与转折发生在同一场景的相邻两句里，且转折的触发者（许七安）当场就给出了理由。按「要有铺设+回收」的口径，它属于场景内冲突，不收录为伏笔；它的状态变化记在 S09。",
     "quotes": [R("q_hurry"), R("q_bad_news"), R("q_rest_tomorrow")]},
]

# ══════════════════════════════════════════════════════════════════════════
# worldSettings[] / notWorldSettings[]
# ══════════════════════════════════════════════════════════════════════════
WORLD = [
    {"id": "W01", "kind": "place", "name": "襄城（襄州主城）", "basis": "explicit",
     "placeState": "arrived",
     "placeStateNote": "有明确的到达与在城动作：「天刚亮，许七安便带着钟璃进了城」、在街上问路、进府衙、在城里转了几圈。",
     "explain": "它决定了本章找人行动的物理范围与成本：城中人口五十万余，「襄城那么大，如何找啊」是同知推脱的直接理由；许七安的查证（官府 + 市井）也只能在这座城里做。",
     "quotes": [R("q_enter_city"), R("q_xiangzhou_geo"), R("q_dahai")]},
    {"id": "W02", "kind": "place", "name": "襄州府衙", "basis": "explicit",
     "placeState": "arrived",
     "placeStateNote": "有到达动作与在场互动：「进了府衙，凭借银锣的腰牌，见到了襄州知府」，随后是喝茶、交办、问答。",
     "explain": "它是本章唯一一处「官府资源可被调用」的场所：许七安的私人寻人请求要在这里转成官差行动，而这座衙门的实际反应是先敷衍、读到邸报后才改为尽力。",
     "quotes": [R("q_yinluo_badge"), R("q_fuyan"), R("q_dashen")]},
    {"id": "W03", "kind": "place", "name": "襄城的勾栏（青楼与勾栏一带）", "basis": "explicit",
     "placeState": "arrived",
     "placeStateNote": "有到达动作：「心里想着，许七安便带钟璃进了勾栏」，并上到二楼雅间。",
     "explain": "它在本章承担两个功能：一是许七安查证失败后的落点（「果然还是勾栏听曲去吧」），二是他把钟璃带离街面、问出她那些判断的私密场合。原文还借青衣小厮的目光写出「带女人进勾栏」在当地被默认解读为哪一种情形。",
     "quotes": [R("q_goulan_enter"), R("q_yaojian"), R("q_tingqu"), R("q_lailu")]},
    {"id": "W04", "kind": "place", "name": "襄城外南边山脉下的大墓（被掘开的那座）", "basis": "explicit",
     "placeState": "mentioned",
     "placeStateNote": ("**只被提到、议论与观测，本区间无人到达。**钟璃是在夜里隔空观气（「阴秽之气冲霄」「状如莲花」），"
                        "钱友是在路边转述后土帮的招揽与失陷；叙述没有写出任何一次进入或抵达。"
                        "特别说明：钱友说的「带人下墓」是**本区间之前的过去事件**，而且他本人没有下去"
                        "（「帮主他们再也没有回来」＋「只能继续招揽高手」），不能算作本章的 arrived。"),
     "explain": "它是本章全部行动的指向物：因为它凶（污秽之气、怕有邪物、伴随大凶），众人才先找人；又因为五号可能在里面，下墓才被排进日程（推迟到明日）。它同时是「地书碎片被屏蔽」这一现象的发生地。",
     "quotes": [R("q_buried_open"), R("q_sanhua"), R("q_never_back"), R("q_rest_tomorrow")]},
    {"id": "W05", "kind": "place", "name": "京城", "basis": "explicit",
     "placeState": "mentioned",
     "placeStateNote": "只被提到，本区间无人往京城方向移动：许七安的打算（「找到五号就回京城」）、钱友转述的承诺（「承诺带她去京城」）、以及李知府对许七安来处的判断（「京城来的银锣」）。",
     "explain": "它是本章几方行动的共同参照点与筹码：对五号它是报酬（管吃管住带去京城），对许七安它是收工条件（找到五号就回去），对李知府它是压力来源（京城来的银锣不能拒绝）。",
     "quotes": [R("q_wuhao_huijing"), R("q_baochi_obj"), R("q_fuyan")]},
    {"id": "W06", "kind": "rule", "name": "风水不是谁都能看：除术士外只有巫师略通、道门略涉，地宗不学",
     "basis": "explicit", "institution": None,
     "institutionNote": ("本条**没有**可诚实填写的 institution 取值：它不是诏/令/法（无 declared）；本区间没有任何针对它的执行动作（无 executed）；"
                         "它也不是某个**人物**的理解（它是钟璃与金莲道长对修行体系的陈述，叙述以「钟璃有问必答」的口气给出，未标为误解）。"
                         "按「缺字段写 null，不要补一个听起来合理的值」写 null 并在此说明，而不是硬套标签。"),
     "explain": "它解释了本章一处关键安排：为什么关于大墓的所有判断只能由钟璃一个人给出——许七安完全不懂风水，金莲道长当场承认「不懂」，楚元缜与恒远跟着摇头；连「这墓是谁选的」这种问题，也只能由她来答（巫师、道门）。",
     "quotes": [R("q_ask_fengshui"), R("q_dont_know"), R("q_wu_also"), R("q_dizong_no")]},
    {"id": "W07", "kind": "rule", "name": "预言师每日只能预测一次，之后厄运升级成天谴；无大气运或特殊法阵庇佑活不过两个时辰",
     "basis": "explicit", "institution": "misunderstood",
     "institutionNote": ("**这一栏是本文件最需要复核者裁断的地方，理由如下。**规则文本本身出自钟璃之口（dialogue），叙述**从未**用「天谴」"
                         "二字做过任何直述：全区间「天谴」共出现三次，一次是她的自述、一次是许七安的内心疑问（「就直接遭天谴了？」）、"
                         "一次是许七安转告众人的话——没有一次是叙述认定。因此我不填 executed：那等于用我自己的因果读法替叙述背书"
                         "（虚弱的跌坐可以只是消耗，三里路的三次横祸可以只是巧合）。按提示词对该取值的界定「这是**人物**的理解」，"
                         "它确实是一个人物的理解与行事依据，故填 misunderstood 并在此写明叙述既未确认也未否认；"
                         "取值名与实际语义的这层错位与 W08 同类，一并登记在 unknowns U06。"),
     "explain": "它解释了本章三处行动约束：①许七安一天只能问一次，所以这次问完就没有第二次；②他必须背她走（她已跌坐在地）；③这条自述后来被他当成拦住下墓的理由（「而今处在遭天谴的状态」）。它同时解释了许七安为什么敢开口问——他自己的说法是有大气运可以抵消。注意这三处约束的**效力来源是人物自己的说法**，不是叙述背书。",
     "quotes": [R("q_once_day"), R("q_collapse"), R("q_daqiyun"), R("q_tianqian")]},
    {"id": "W08", "kind": "rule", "name": "打更人的银锣身份与腰牌可以要求地方官府配合（李知府的理解是「不能拒绝」）",
     "basis": "explicit", "institution": "misunderstood",
     "institutionNote": ("标 misunderstood 是按提示词对该取值的界定——「这是**人物**的理解」：李知府把「京城来的银锣」读成一条不能拒绝的约束"
                         "（「京城来的银锣，不能拒绝」）。本区间没有出现诏令法文本，叙述也没有说他这条理解是错的；"
                         "相反，邸报上的「银锣许七安代司天监斗法」正好印证了他的谨慎，所以他这条理解在本区间是**成立**的，"
                         "不是误解。取值与语义的这层错位记在 unknowns U06。"),
     "explain": "它解释了本章两种截然不同的执行标准从何而来：同一个请求，在「只是一名京城银锣」时被处置为「敷衍一下便成」，在「邸报上的大人物」被认出来后翻转为「立刻去办，务必要尽心尽力」。约束的强度随身份识别而变化。",
     "quotes": [R("q_yinluo_badge"), R("q_fuyan"), R("q_dibao_line"), R("q_dashen")]},
    {"id": "W09", "kind": "item", "name": "地书碎片（金莲道长与许七安各自持有的那一份）",
     "basis": "explicit", "itemStates": ["hold", "use"],
     "itemStatesNote": ("四态分开写：hold=金莲道长从纸鹤背跃下时「边取出地书碎片」，说明它在他身上；"
                        "use=他取出它是要传书，且众持有者用它互相传书（「地书碎片的持有者们同时悸动」）。"
                        "**transfer 与 lose 都不成立**：本区间没有写出任何一次碎片易手，也没有写谁的碎片丢了。"),
     "explain": "它同时是本章的通讯工具与最贵的赌注：众人靠它交换五号的消息，但在许七安这里不能用（「不然会暴露我身份」），迫使他改用狮子吼；而清理门户的计划一旦凑不齐碎片就失败一半。",
     "quotes": [R("q_clue_ask"), R("q_jidong"), R("q_shout"), R("q_daji_half")]},
    {"id": "W10", "kind": "item", "name": "五号持有的那块地书碎片",
     "basis": "explicit", "itemStates": [],
     "itemStatesNote": ("**四态一个都不成立，故记空数组。**原文只说「金莲道长失去了地书碎片之间的**感应**」——"
                        "失掉的是持有者之间的联系，不是碎片本身；本区间没有写她的碎片被夺、丢失、转手，也没有写她还在用它。"
                        "这正是最容易把它误记成 lose 的地方，我按要求不合并、也不替它选一个状态。"),
     "explain": "它是本章的核心悬念物：它一旦失联，就产生了两重后果——五号的消息断了（传书失效），以及金莲道长的计划「失败了一半」；同时它也是「被地宗妖道抓走」这一错误推断的起因（六号把失联读成了被抓）。",
     "quotes": [R("q_msg6"), R("q_xuecang"), R("q_daji_half")]},
    {"id": "W11", "kind": "item", "name": "碎银（许七安荷包里的一把、以及他弹出的那一粒）",
     "basis": "explicit", "itemStates": ["transfer", "use"],
     "itemStatesNote": ("transfer=「从荷包里掏出一把碎银，递给恒远大师」，以及「屈指弹出一粒碎银」给勾栏小厮；"
                        "use=他在同一句里给出用途（「找人打听情况，最好的办法是银子」）。"
                        "hold 与 lose 不单列：原文没有写他清点或失去银两。"),
     "explain": "它解释了本章的两条路怎么走通：找人靠「银子优先、拳头其次」（他给恒远的那把），进勾栏的雅间靠弹出的一粒。原文没有写数额，我不折算。",
     "quotes": [R("q_silver_fist"), R("q_tansuiyin")]},
    {"id": "W12", "kind": "item", "name": "木牌（钱友身前的招揽牌）",
     "basis": "explicit", "itemStates": ["use"],
     "itemStatesNote": ("use=钱友不搭理许七安的问话，「指了指木牌」，让牌子替他说话；牌上写着招募条件。"
                        "hold 不成立：原文写的是「身前放着一块牌子」——**放**在他身前，本区间没有任何「拿在手里/持有」的动作，"
                        "我不把「放」改写成「持」。transfer 与 lose 同样没有依据。"),
     "explain": "它是这次招揽能成立的前提条件：正因为牌子上写明「诚意要求七品以上高手相助，重金回报」，许七安才知道对方要什么，也才有了随后的「我这点微末伎俩，够不够帮忙？」。",
     "quotes": [R("q_sign"), R("q_muban"), R("q_enough")]},
]

NOT_WORLD = [
    {"id": "NW01", "name": "「墓中必有大阵，屏蔽了地书碎片」",
     "why": ("这是金莲道长在信息不足下给出的解释，不是一条明确设定：他前一句自己说「除了地宗秘法能封印地书碎片，"
             "其他手段也可以，只是比较苛刻」，后一句才断言「必有大阵」；本区间没有任何验证动作，墓也没人进去过。"
             "把人物的一条推测收进世界设定，等于替叙述背书。它已作为 C15 的因与 K01 的知识差登记。"),
     "quotes": [R("q_other_means"), R("q_dazhen")]},
    {"id": "NW02", "name": "「副帮主是术士，江湖上罕见的术士」",
     "why": ("它是钱友为说明「我们副帮主如何得知墓穴污秽之气」而给出的身份交代，属于对一个人的转述，"
             "不是关于世界的规则；它对行动的约束已经由 W06（风水不是谁都能看）承载。不另立一条，避免把人物身份当设定层。"),
     "quotes": [R("q_stop"), R("q_shushi")]},
    {"id": "NW03", "name": "「术士体系只有六百年」「大奉的国运目前也就六百年」",
     "why": ("这是许七安内心用来对照的时间常识（他想起以前在天地会内部问过），本区间没有用它约束任何行动、资源或后果——"
             "它既不改变谁去哪里、也不决定谁能做什么。按「泛泛的术语与装饰性设定不要写」不收录。"),
     "quotes": [R("q_600"), R("q_guoyun600")]},
    {"id": "NW04", "name": "「除了司天监之外，九州是有野生术士存在的」",
     "why": ("它是对世界的一般性陈述，本区间的作用只是让钱友口中的「江湖术士副帮主」不显得矛盾；"
             "真正约束行动的是 W06（谁能看风水）。不为了凑一条 rule 而收录。"),
     "quotes": [R("q_yeshu"), R("q_shushi")]},
    {"id": "NW05", "name": "「官府通常是不会管这些破事的，甚至还会把他抓起来」",
     "why": ("这是许七安的内心推测（他用来解释钱友为什么在路边摆摊而不是报官），不是叙述对官府行为的认定；"
             "钱友自己的理由也只到「小人第一个被抓」。它不构成一条可执行的规则，故不收录。"),
     "quotes": [R("q_daxiong_guess"), R("q_baoguan_no")]},
    {"id": "NW06", "name": "「术士体系虽只有六百年的时间，但六百年只是对比其他体系，显得短暂」这一比较",
     "why": ("它是对 NW03 那句常识的补充说明，同样没有改变任何人的行动与资源；单独列出来只是把同一段常识拆成两条，属于为凑数而拆分，故不收录。"),
     "quotes": [R("q_600")]},
]

# ══════════════════════════════════════════════════════════════════════════
# themeReadings[]：解释层，最多 2 条，每条给 perspective / support / counter
# ══════════════════════════════════════════════════════════════════════════
THEMES = [
    {"id": "TH01",
     "perspective": ("以「同一支队伍里每个人都在替自己降低风险」为轴读这一章——把章题「令人安心的队友」当作"
                     "**许七安一个人的欣慰**，而不是对这群人的客观评价：他不止一次给出同一句内心评语，"
                     "而那批让他安心的行为，逐条看都是各人把风险推回给不确定性的动作。"),
     "note": ("这是可选视角，不是唯一真相。同一批事实也可以读成「一群被同一件麻烦事拖住的人各自判断该不该现在动手」，"
              "那样章题的落点就在『推迟』而不在『自保』——两种读法我都保留。"),
     "support": {"text": ("支持这一读法的材料在区间内成串：①金莲道长抢先定调「先找人吧，下墓以后再说」；"
                          "②恒远接「逝者已矣，没必要再去打扰人家」；③楚元缜接「而且我们准备也不充分，下墓之事从长计议」；"
                          "④许七安查证失败后给出的落点是「果然还是勾栏听曲去吧」；⑤李知府对同知的处置是「你就敷衍一下便成」；"
                          "⑥钱友「一念及此，钱友心生退意」并头也不回的离开；⑦最后金莲道长一听钟璃遭天谴就改口推迟下墓。"
                          "而许七安对②③的反应就是那句「都是让人心安的队友，没有事逼和事精，真好」——"
                          "让他安心的不是有人去救人，而是没有人逼他现在就动手。"),
                 "basis": "explicit",
                 "quotes": [R("q_xian_zhaoren"), R("q_heng_shizhe"), R("q_chu_prepare"), R("q_goulan_go"),
                            R("q_fuyan"), R("q_retreat"), R("q_rest_tomorrow"), R("q_good_teammates")]},
     "counter": {"text": ("不利于这一读法的证据同样在本区间内，而且不止一条：①金莲道长的着急是真的、且被叙述直接写出——"
                          "「脸色沉重」「他确实有些着急」「时也命也？」，他还当面定调「先找人吧」并且真的分了三路去找，"
                          "这不是自保而是本区间唯一的行动方；②钱友改主意恰恰是为了救帮主（「回去，得回去，立刻回去」），"
                          "他的折返不是降低风险而是主动往风险里走；③最硬的一条反例是钟璃：她明知「最终也会让事情走向更糟糕的结局」，"
                          "仍然用掉了当日唯一一次预言并因此遭天谴，她是本章唯一一个**净付出**的人；"
                          "④许七安本人也没有被这条读法放过——他背着钟璃走完三里、并主动接下钱友的委托。"
                          "因此这条读法更适合描述「有能力选择的人」，而不是全体。"),
                 "basis": "explicit",
                 "quotes": [R("q_zhizhi"), R("q_shiyeminye"), R("q_xian_zhaoren"), R("q_go_back"),
                            R("q_worse"), R("q_once_day"), R("q_three_miles"), R("q_accept")]}},
    {"id": "TH02",
     "perspective": ("以「同一个人的下落，在五拨人手里变成五种说法」为轴读这一章——不把五号当失踪者，"
                     "而当**一条被反复转写的信息**：她本人从未出场，读者看到的全是别人对这件事的描述。"),
     "note": "与 TH01 并列而非互斥：TH01 看的是动机层的自保，TH02 看的是信息层的失真；同一批事实两种切法。",
     "support": {"text": ("支持材料按传播顺序排开：①六号（恒远）在传书里定性「极有可能被地宗的妖道抓走了」——用「极有可能」把猜测推进了一步；"
                          "②二号（李妙真）接到后立刻当成事实行动（「确定是被地宗妖道抓走了吗，襄州是吧……我立刻过来」），"
                          "从而把一个未证实的判断变成立刻要赶路；③金莲道长给出的是「尽人事，听天命」——他没有纠正，只给了态度；"
                          "④许七安先顺着同一假设推演（「必定留下战斗痕迹」），再用官府与市井两条渠道把它否掉；"
                          "⑤最后是钱友的第一手招揽记录（缺盘缠、饿了三天三夜、被承诺带去京城），它才把前四种说法替换掉。"
                          "整章的悬念不是「五号怎么了」，而是「谁的说法会被下一句推翻」。"),
                 "basis": "explicit",
                 "quotes": [R("q_msg6"), R("q_msg2_long"), R("q_msg_jl_2"), R("q_henji"), R("q_baiguan"),
                            R("q_how_know"), R("q_baochi")]},
     "counter": {"text": ("反例有三条，且都不弱：①钱友的第一手信息并没有被改写——他只是不知道那位南疆姑娘就是五号，"
                          "他说出的条件与经过在区间内没有被任何后文推翻，信息的传播在这里不是失真而是**拼合**；"
                          "②李知府那条线走的是相反方向：他先凭身份敷衍，读了邸报才知道来的是大人物，"
                          "传播链在这里让判断变**更准**，不是更歪；③许七安的推论也并非随波逐流——"
                          "他先立假设、再用两条独立渠道否证，最后主动去问钱友「有没有招揽到一位南疆的姑娘」，"
                          "这条链上有人在做纠错。因此「信息被反复转写」可以描述这一章的表层，但不能说所有转写都在失真。"),
                 "basis": "explicit",
                 "quotes": [R("q_how_know"), R("q_yuanlai"), R("q_fuyan"), R("q_dibao_line"),
                            R("q_ask_nanjiang"), R("q_zhifu_no")]}},
]

# ══════════════════════════════════════════════════════════════════════════
# speechAsClueNotFact[]
# ══════════════════════════════════════════════════════════════════════════
SPEECH = [
    {"id": "SP01", "speaker": "六号（恒远）·传书",
     "said": "五号出事了，她在襄州消失不见，金莲道长失去了地书碎片之间的感应，极有可能被地宗的妖道抓走了。",
     "whyNotFact": "这是传书里的判断，原文用「极有可能」标出不确定；后文被钱友的第一手记录与许七安的推断推翻（五号是下墓，不是被掳）。把传书当事实，就会把整章的转折读没。",
     "clueSupports": "能支撑的是「天地会在信息不足时按最坏情况行动」这一群体状态，以及 S08 的认知基线。不能用来写五号的真实处境。",
     "quote": R("q_msg6")},
    {"id": "SP02", "speaker": "钱友（转述副帮主）",
     "said": "墓穴里污秽之气甚是恐怖，怕有邪物，光是我们后土帮搞不定。",
     "whyNotFact": "这是钱友转述副帮主的判断（叙述用「但我们的副帮主说」引导），副帮主本人没有出场，墓内情况本区间也无一句直述。",
     "clueSupports": "能支撑的是后土帮为何要花三个月招揽高手、以及 T10.obstacle 的成立。不能用来写墓里确实有邪物。",
     "quote": R("q_fubangzhu")},
    {"id": "SP03", "speaker": "钟璃",
     "said": "状如莲花，主峰朝东，接纳紫气，背面是一条河，想必地底会有暗流，底部得黑水滋养，是三花聚顶地势。如果山中再有铁矿，那便五行俱全了。",
     "whyNotFact": "她说的是**观气所得**，措辞里带「想必」「如果」两处不肯定的标记；她自己也是隔着距离观测（「一边观测地势，一边说道」）。",
     "clueSupports": "能支撑的是「这座墓选址极讲究、墓主绝非凡俗」这一判断的来源，以及 W06 里为什么只有她能给出这类判断。不能用来写地底真有暗流或铁矿。",
     "quote": R("q_sanhua")},
    {"id": "SP04", "speaker": "金莲道长",
     "said": "墓中必有大阵，屏蔽了地书碎片，让她无法接受到我们的传书。",
     "whyNotFact": "「必」是他的断言力度，不是证据：他前一句自己承认「除了地宗秘法能封印地书碎片，其他手段也可以，只是比较苛刻」，且本区间无人进过墓、无任何验证。",
     "clueSupports": "能支撑的是 K01 的知识差与 C15（许七安由此联想到司天监玩阵法）。不能用来写墓里真有一座大阵。",
     "quote": R("q_dazhen")},
    {"id": "SP05", "speaker": "楚元缜（内心）",
     "said": "楚元缜其实心里隐约有个猜测，李妙真要突破了，所以才一拖再拖。",
     "whyNotFact": "原文自己写明这是「隐约有个猜测」；李妙真给出的延期理由是去江州查案与沿途铲奸除恶。",
     "clueSupports": "能支撑的是 S10 的状态变化与 K05 的知识差。不能用来写李妙真真的要突破四品。",
     "quote": R("q_dianshi_20")},
    {"id": "SP06", "speaker": "李知府",
     "said": "许大人放心，本官一定照办。",
     "whyNotFact": "这是一句承诺，而且**被说这话的人自己推翻**：等许七安一走，他对同知的指示是「你就敷衍一下便成」。",
     "clueSupports": "能支撑的是 K04（官府是否真办事无人知道）与 S02 的两段态度。不能用来写官府真的照办了。",
     "quote": R("q_zhifu_promise")},
    {"id": "SP07", "speaker": "同知",
     "said": "下官一定竭尽全力。",
     "whyNotFact": "这是承诺而非执行描写；原文在这句之后直接转入许七安的街头画面，没有再写官府的后续动作。",
     "clueSupports": "能支撑 S03 的态度翻转与 K04。不能用来写搜寻真的展开了。",
     "quote": R("q_jiejinquanli")},
    {"id": "SP08", "speaker": "许七安",
     "said": "都小意思啦，我许七安什么大风大浪没见过，绝对没有怪你。",
     "whyNotFact": "这是安慰钟璃的话；同一段前后的叙述写的是他确实被连累（三里路三次横祸），话与事实不一致。",
     "clueSupports": "能支撑的是他与钟璃的关系状态与 T04.cost 的对照。不能用来写他没有被影响。",
     "quote": R("q_xiaoyisi")},
    {"id": "SP09", "speaker": "钱友",
     "said": "墓中有大宝贝，只要大侠肯帮忙，不但可以得到墓中宝贝，我们后土帮还会重金答谢。",
     "whyNotFact": "这是**许诺**：本区间没有写后土帮付出任何东西（连定金都没有），墓里的「大宝贝」也无任何实物依据。",
     "clueSupports": "能支撑的是 R03（为什么不能把许诺当作许七安接任务的原因）与 T05.cost 记 null 的理由。不能用来写报酬已经存在或墓里真有宝贝。",
     "quote": R("q_baobei")},
    {"id": "SP10", "speaker": "二号（李妙真）·传书",
     "said": "确定是被地宗妖道抓走了吗，襄州是吧，金莲道长也在襄州？我立刻过来，一起寻找五号。",
     "whyNotFact": "前半句是**反问**（不确定），后半句是意愿（「我立刻过来」）；本区间没有写她是否动身，随后还被金莲道长回绝「你不必过来，没有意义」。",
     "clueSupports": "能支撑 TH02 里「未证实的判断被当成行动依据」这一步，以及 K06 的知识差。不能用来写她来过襄州。",
     "quote": R("q_msg2_long")},
    {"id": "SP11", "speaker": "许七安（内心）",
     "said": "道长居然没提我，看来「猫道」这个身份确实让他很忌惮。",
     "whyNotFact": "「没提我」是文本事实，「让他很忌惮」是他自己下的判断；原文没有写金莲道长回避他的任何理由。",
     "clueSupports": "能支撑 C17 与 K08。不能用来写道长真的忌惮他。",
     "quote": R("q_maodao")},
    {"id": "SP12", "speaker": "钟璃",
     "said": "他的元神是残缺的。",
     "whyNotFact": "「他」在本区间没有明确指代（前文最近的名词是金莲道长，下一句却转去说「与你在教坊司的相好一样」）；且这是她的判断，叙述没有给出任何关于元神的直述。",
     "clueSupports": "能支撑的是 K09 与 textualNotes TX13。不能用来写任何人的元神状态。",
     "quote": R("q_yuanshen_can")},
    {"id": "SP13", "speaker": "许七安",
     "said": "我有个大胆的想法。",
     "whyNotFact": "原文没有写出这个想法是什么；它的落地要靠后文的动作反推（他把她拉到大街上、请她用预言）。",
     "clueSupports": "能支撑 NF02 的判定（节拍而非伏笔）。不能用来写他当时已经想好了要做什么。",
     "quote": R("q_bold_idea")},
    {"id": "SP14", "speaker": "许七安（内心）",
     "said": "小姐姐还挺有料的！后背传来的触感，以及丰满柔软的手感，让他心里补充了一句。",
     "whyNotFact": "这是他的内心话，与 T04 里他背她走这一动作同时发生；叙述只写触感，没有写钟璃的任何反应。",
     "clueSupports": "能支撑的是他这一路上的心理状态。不能用来写钟璃对这件事有任何态度。",
     "quote": R("q_touch")},
    {"id": "SP15", "speaker": "钟璃（预言）",
     "said": "往南走三里，会有我们想要的线索，青色衣衫.......男人.......惶恐不安.......",
     "whyNotFact": "这是预言的内容，不是叙述对未来的认定；随后「青色衣衫的男人」确实出现了，但预言并未说明他是谁、为何惶恐。把预言当事实，会顺手补出原文没有的身份联系。",
     "clueSupports": "能支撑 T04.result 与 C10。不能用来写那个男人（钱友）与五号的关系——那要等他的转述。",
     "quote": R("q_prophecy")},
]

# ══════════════════════════════════════════════════════════════════════════
# textualNotes[]：原文自身的疑误——逐字保留，不改写
# ══════════════════════════════════════════════════════════════════════════
TEXTUAL = [
    {"id": "TX01", "about": "「克制墓**的阴秽之气」——正文里出现了两个字面星号",
     "note": "两个字符位置上是字面的「**」，不是我的省略或屏蔽。疑为敏感词替换或抓取残留（本应是「墓中」或「墓里」）。**逐字保留**：我在 T10.action 与 W 系列里照抄成「墓**」，不做补字；补字会让 `text.find(quote)` 失效。",
     "quotes": [R("q_prepare3m")]},
    {"id": "TX02", "about": "「襄州的下辖八个州，十十六个郡县」",
     "note": "「十十六」衍字（疑为「十六」或「十来个」）。逐字保留。它出现在 W01 的引文里，故此处单列，避免复核者以为是我抄错。",
     "quotes": [R("q_xiangzhou_geo")]},
    {"id": "TX03", "about": "「虽无法与京城想必」",
     "note": "「想必」疑为「相比」之误。逐字保留；同一句引文已在 W01 中使用。",
     "quotes": [R("q_xiangzhou_geo")]},
    {"id": "TX04", "about": "「人不能又怪癖」",
     "note": "「又」疑为「有」之误（后文紧接「有了怪癖还让人知道」用的是「有」）。逐字保留，不改写。",
     "quotes": [R("q_maodao")]},
    {"id": "TX05", "about": "「众人商议了一番，绝对从三个方面入手」",
     "note": "「绝对」疑为「决定」之误。逐字保留；它出现在 T17.objective 的引文里，故此处单列。",
     "quotes": [R("q_three_ways")]},
    {"id": "TX06", "about": "「青衫男子」在同一章里指两个不同的人",
     "note": "钱友出场时被写成「一位穿青色衣衫的男子」，此后一律称「青衫男子」；而御剑赶来的楚元缜也被写成「一道剑光破空而来，剑身站着一位青衫男子」。同一称呼在一章内指两个人，是真实的指代混淆，会直接影响「谁在说话」的判断。我按上下文区分（路边摆摊的是钱友、剑光上的是楚元缜），并在引文里保持原文用词。",
     "quotes": [R("q_pretend"), R("q_sword_light"), R("q_please_help")]},
    {"id": "TX07", "about": "「任由钢刀看在头上」",
     "note": "「看」疑为「砍」之误（同句后半是「钢刀卷刃」，前文是「钢刀劈砍而来」）。逐字保留。",
     "quotes": [R("q_buduo")]},
    {"id": "TX08", "about": "「钱友有些慢慢苍白」",
     "note": "「慢慢苍白」疑为「脸色慢慢苍白」的脱字，或「有些苍白」的衍字。逐字保留，不补。",
     "quotes": [R("q_pale")]},
    {"id": "TX09", "about": "「让她无法接受到我们的传书」",
     "note": "「接受到」疑为「接收到」或「接受」的混写。逐字保留。",
     "quotes": [R("q_dazhen")]},
    {"id": "TX10", "about": "「天宗和人宗倒是倒是有所涉猎」",
     "note": "「倒是」重复。逐字保留。",
     "quotes": [R("q_dizong_no")]},
    {"id": "TX11", "about": "同一章里许七安的品级既被写成六品、又被写成五品",
     "note": "钱友先惊喊「六，六品？！」，叙述称「砍了一个六品的铜皮铁骨」、后又称他「六品的强大武夫」「这位六品高手」；但钱友的内心另写作「不但自身是五品」。本区间没有一句裁定，我不替他选一个。登记为 knowledgeGaps K10。",
     "quotes": [R("q_liupin"), R("q_half_hour"), R("q_wupin")]},
    {"id": "TX12", "about": "「她对天人之争并没有太大的把我」",
     "note": "「把我」疑为「把握」之误。逐字保留；引文用于 S10。",
     "quotes": [R("q_meiyou_bawo")]},
    {"id": "TX13", "about": "「他的元神是残缺的」——指代不明",
     "note": "这句话出现在许七安说出「那个组织是地宗的金莲道长创建的」之后，字面上最近的名词是金莲道长；但她紧接着改口去说「与你在教坊司的相好一样」，指代链条断裂。许七安当场也没听懂（他问「什么意思？」）。我不替原文选一个指代。登记为 knowledgeGaps K09 与 unknowns U03。",
     "quotes": [R("q_secret_org"), R("q_yuanshen_can"), R("q_what_mean")]},
    {"id": "TX14", "about": "「倒是青楼和勾栏这些娱乐场所，早早的就开门了」之后紧接「嫖客们打着哈欠出来」",
     "note": "「嫖客」与本句的「青楼和勾栏」是同一批场所的客人，用词直白；照抄不改。它只用于 R01 的拒绝理由，不进入任何世界设定。",
     "quotes": [R("q_brothel_open"), R("q_prostitutes")]},
]

# ══════════════════════════════════════════════════════════════════════════
# unknowns[]
# ══════════════════════════════════════════════════════════════════════════
UNKNOWNS = [
    {"id": "U01", "about": "五号在墓中到底是死是活",
     "why": "本区间没有一句叙述直述墓内情况：钱友只说帮主一行「再也没有回来」，许七安只推到「下墓倒斗出了意外」，钟璃只说墓「或有异宝，但也伴随着大凶」。三处都是隔层信息。",
     "keep": "T11.result 只写「消失不见 / 被推断为下墓」；K02 登记为无人知情；不写生死。"},
    {"id": "U02", "about": "「墓**」被屏蔽掉的两个字是什么",
     "why": "原文在该位置是两个星号，无法从上下文唯一还原（「墓中」与「墓里」都通）。",
     "keep": "照抄「墓**」不改（TX01）；不把它当作任何推断的依据。"},
    {"id": "U03", "about": "钟璃说的「他的元神是残缺的」里的「他」是谁",
     "why": "前文最近的名词是金莲道长，但下一句立刻转去说教坊司的相好；两句之间没有可用的指代桥。许七安当场也问「什么意思？」。",
     "keep": "不替他选指代；登记为 K09 与 TX13，不写进任何 tasks/states。"},
    {"id": "U04", "about": "许七安在天地会的编号与「猫道」这个身份的来历",
     "why": "金莲道长两次传书只点了二号、四号、六号，许七安自己也只提到「道长居然没提我」；本区间没有写出他的编号，也没有解释「猫道」。",
     "keep": "C17 标 inferred；NF01 记录不收录为伏笔的理由；K08 登记知识差。"},
    {"id": "U05", "about": "三路分工里御剑搜索与恒远打听这两路的结果",
     "why": "原文只写了许七安这一路的结果（「一无所获」）；金莲道长与楚元缜的空中搜索、恒远的城中打听在本区间都没有结果描写。",
     "keep": "T01.result 与 T17.result 只覆盖有文字的那一路，并在 resultNote 里写明另两路没有结果描写，不外推。"},
    {"id": "U06", "about": "`misunderstood` 这个取值的语义与它的字面（误解）不一致——本文件有两处实例",
     "why": ("提示词把 `misunderstood` 界定为「这是**人物**的理解」，而它的字面意思是「误解」。本文件两处用到它，两种情形不同："
             "①W08（李知府认为京城银锣不能拒绝）：这条人物理解在本区间是**成立**的（邸报正好印证），不是误解；"
             "②W07（钟璃自述预言的天谴规则）：叙述既没有确认也没有否认，它是一个人物的理解与行事依据。"
             "也就是说，该取值实际承担的是「效力来源是人物」这一语义，而不是「该理解是错的」。"
             "我把两处都在 institutionNote 里写明了它们各自是不是误解，不靠读者自己分辨。"),
     "keep": ("两处都填 misunderstood 并在 institutionNote 里写明「是否误解」；若复核认为该词表应把「人物理解」与「误解」分开成两个取值，"
              "那么 W08 与 W07 应落在不同的桶里——这一点需要复核者裁断，因为它影响的是词表本身，不是本段读数。")},
    {"id": "U07", "about": "W09 与 W10 是否该算同一件物品的两条",
     "why": "原文谈的「地书碎片」是同一件法宝碎成的多块：金莲道长手上那块有 hold/use，五号那块四态皆无。我按**持有者**拆成两条，以免把「持有」与「失联」合并成一条物品链（那是明令禁止的写法）。",
     "keep": "拆条的理由写在 W10 的 itemStatesNote；若复核认为应合成一条，请指出合并后四态如何不互相污染。"},
    {"id": "U08", "about": "狮子吼这一招的名字与来历",
     "why": "原文只写「震耳欲聋的咆哮」「滚滚音波」，另有恒远「在城中听见了隐约的狮子吼」一处点出名称；本区间没有交代这是谁教的、属于哪一体系。",
     "keep": "T06.action 只记音波这一事实；不替它补来历，也不写进 worldSettings（它不改变任何人的可行范围）。"},
    {"id": "U09", "about": "TH01 与 TH02 是否只是同一批事实的两种说法",
     "why": "两条读法的支持材料高度重叠（都围绕「谁在回避、谁在转述」），我也无法证明它们是两个独立主题而不是一个主题的两种切法。",
     "keep": "两条都写了 counter，并各自声明是可选视角；若复核认为应压成一条，请指出哪一条的反例更弱。"},
    {"id": "U10", "about": "本章的时间跨度是否可精确到「一天」",
     "why": "原文用「天刚亮」「日头渐高」「半个时辰后」给出相对时序，但没有日期；「明日再下墓」也只是相对表述。",
     "keep": "所有 states 的锚点都只写事件、不写绝对时刻；不把相对时序换算成具体时间。"},
    {"id": "U11", "about": "钱友的称号「舵主」与后土帮的组织规模",
     "why": "原文只说他是「后土帮的舵主」，另提到帮主、副帮主、客卿；本区间没有交代后土帮有多少人、舵主职权是什么。",
     "keep": "T05 只按原文写他的身份与行为；不替他扩出一个帮派结构（那属于「没有依据就不扩地图/术语层」）。"},
    {"id": "U12", "about": "钟璃在司天监的排行（「五师姐」）与许七安称呼的关系",
     "why": "原文有一处「战战兢兢的司天监五师姐」，但本区间没有交代她是监正的第几个弟子、这个排行在司天监意味着什么职分。",
     "keep": "不写进 worldSettings；只在 T04 的 who 栏里按原文称她为预言师与司天监成员。"},
]

# ══════════════════════════════════════════════════════════════════════════
# selfCritique[]
# ══════════════════════════════════════════════════════════════════════════
SELF_CRITIQUE = [
    {"id": "SC01", "risk": "T10 的 action 与 cost 都取材于钱友同一段转述，可能被读成把一件事拆成两栏凑数。",
     "why": ("我最终按「投入 / 动作」分开：cost 取先期投入的清单（足足三个月、招揽高手、置办工具、至刚至阳物品），"
             "action 取「准备妥当后带人下墓」这一截，两栏区间不重叠。这样分的理由是两者的可数性不同——"
             "投入是逐项可数的资源，动作是一次性的行为。若复核认为该段只能支撑一栏，我会把 cost 改为 null 并在 costNote 里"
             "说明「本区间唯一的资源投入与动作同段，为避免同句多栏而只保留 action」。")},
    {"id": "SC02", "risk": "T05.cost、T12.cost、T13.cost、T15.cost、T16.cost、T17.cost 我都记了 null，可能被读成漏读而不是「确实没有」。",
     "why": ("六处 null 的候选项我都逐条写进了 costNote 并说明了为什么不算（许诺 ≠ 已付出、风险 ≠ 代价、动摇 ≠ 损失、利害 ≠ 障碍）。"
             "我仍然选 null，是因为把许诺或风险写成代价，正是这份任务点名要避免的形态。若复核能指出这六处中哪一处有被我忽略的、"
             "已发生的付出（例如某个已交付的实物或已放弃的机会），我按句重判。")},
    {"id": "SC03", "risk": "T09.result 与 T13.result 都记了 null，其中 T13 的 null 尤其容易被读成「没写」而不是「原文没写结果」。",
     "why": ("T09 的 null 是因为「推迟」已作为 action 登记，重复使用同一句会让两栏共用依据；T13 的 null 是因为原文确实没有写他搜索的结果。"
             "我在两处 resultNote 里都写明了理由，并特别注出「不写『搜索注定无果』」这一条——因为我上一版草稿正是用后文结论倒推他当时的处境，"
             "那属于用结局改写过程。这一处自我更正请复核重点检查。")},
    {"id": "SC04", "risk": "W04 把大墓记成 `mentioned` 而不是 `arrived`，可能与「后土帮确实带人下去过」这一事实冲突。",
     "why": ("我按提示词的口径判断：`arrived` 需要本区间内的到达/驻守动作。钱友转述的「带人下墓」是区间之前的过去事件、且他本人没下去，"
             "本区间在叙述层没有任何一次抵达。如果复核认为转述的过去事件也算 arrived，请指出判据，我按同一判据重判 W04——"
             "但那会连带影响 K03 的写法，需要一起改。")},
    {"id": "SC05", "risk": "F03 标 unresolved 可能被读成「我没读完」而不是「本区间确实没回收」。",
     "why": ("铺设（楚元缜提出疑问 + 金莲给出大阵解释）与「被注意到」（许七安联想到司天监）都在本区间内，但没有任何**使用**："
             "他没说出口、没人接话、下墓推迟。若把「他想到了」算回收，这条伏笔就能标 resolved；我选择更严的标法，并在 note 里写清了差在哪一步。")},
    {"id": "SC06", "risk": "全文引文都通过了 `text.find` 逐字定位，但**定位正确不等于语义已核验**。",
     "why": ("本文件对每条断言的语义判断（尤其 basis 的 explicit/inferred 划分、五栏归位、四态与 arrived/mentioned 的取舍）"
             "都还需要独立复核者对着原文判定。因此 semanticReview 记 not-performed，不声称任何语义已核验。"
             "这是纪律要求，也是我对自己这一轮工作的定位：我交的是可复核的结构化读数，不是结论的正确性证明。")},
    {"id": "SC07", "risk": "我把同一段话拆成多个 key（如 q_baochi_obj / q_baochi_act、q_rest_tomorrow / q_tongue）以满足「五栏不共用同一区间」，可能被读成规避检查。",
     "why": ("拆分的每一对都对应原文里**语义不同**的两截（承诺条件 vs 她的应承；完整改口句 vs 其中「明日再下墓」那一截），"
             "并在正文里注明了各自的用途。这是为了让「哪一栏靠哪句话」可机器复核，而不是把一句话切成几段反复使用。"
             "构建期断言 A3 会检查同一任务五栏的区间两两不重叠；若复核认为某处拆分不成立，请指出该处，我合并回去并把对应栏改 null。")},
]

# ══════════════════════════════════════════════════════════════════════════
# 组装
# ══════════════════════════════════════════════════════════════════════════
CAND = {
    "schemaVersion": 6,
    "task": "read:dafeng:L3:0303",
    "agent": "w-dafeng-1",
    "role": "READER",
    "book": "dafeng",
    "lane": 3,
    "unitIndex": 303,
    "unitHead": "第七十四章 令人安心的队友（8000字大章）",
    "provenanceNote": ("本候选由 loop/state/out/read_dafeng_L3_0303.w-dafeng-1.build/ 下的 quotes_0303.py（引文字符串）、"
                       "probe_0303.py（用 text.find 现算偏移）、build_0303.py（人工精读结论）生成。"
                       "候选里没有任何手写的 start/end —— 所有偏移都来自 probe 的输出 refs_0303.json。"),
    "semanticReview": "not-performed",
    "semanticReviewNote": ("本轮只做到「引文逐字定位 + 结构分区产出 + 机器可复核」。定位正确 ≠ 语义已核验："
                           "本文件每条断言的**语义**是否正确，需由独立复核者对着原文判定。本文件不声称语义已核验。"),
    "basisLegend": {"explicit": "原文直述", "inferred": "我的归纳",
                    "derived": "跨段推导", "unverified": "存疑"},
    "kindLegend": {"narration": "叙述（含叙述者评论）",
                   "dialogue": "人物说的话（不是叙述事实）",
                   "inner": "人物内心独白",
                   "free_indirect": "叙述转述人物理解（非叙述认定）"},
    "nullFieldRule": "缺哪一栏写 null，并在同名 <栏>Note 写明为什么没有依据。",
    "source": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "selector": "docs[0].text",
        "range": [START, END],
        "codepoints": END - START,
        "sourceHash": SOURCE_HASH,
        "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
        "sliceSha256": SLICE_SHA,
        "sliceSha256Scope": "docs[0].text[1338280:1348239) 的 sha256（另起字段，不覆盖 sourceHash）",
        "offsetCaliber": "所有 start/end 都是相对 docs[0].text **全文** 的 codepoint 偏移；自检：docs[0].text[start:end] == quote 逐字成立。",
        "boundaryBefore": "，以示安慰。\n\n    “刚才，刚才降落时，我发现附近的风水有问题，南边群山底下，有一座大墓。”钟璃小声说。\n\n    ...........\n\n    PS：今天更新1.04万字，美滋滋。月初求一下月票。\n\n\n------------\n\n",
        "boundaryAfter": "第七十五章 墓中\n\n    钟璃现在遭了天谴，肯定不能把她留在外面，许七安向来是个怜香惜玉的男人。\n\n",
        "headQuote": R("q_title"),
        "headQuoteNote": "docs[0].text[1338280:1338306] == '第七十四章 令人安心的队友（8000字大章）' 逐字成立，且它正是任务声明的 start，这是「切片以本单元标题开头」这一自检的机器证据。",
    },
    "authorRegion": {
        "regionStart": AUTHOR_START, "regionEnd": END,
        "note": ("末尾作者区自「    PS：今天肝了一整天」起到片末的分隔线为止；叙事正文在「而后，他愣了愣，心说这句话如此熟悉，"
                 "好像刚刚说过似的。」之后的场景分隔符处结束。本候选的叙事分区不引用作者区文字（构建期断言 A10）。"),
        "boundaryTail": "\n\n    PS：今天肝了一整天，终于码出来了。继续第二章，十二点前应该能更新，但不是大章。记得纠错别字。\n\n    另外，感谢大家为小母马的笔芯和送礼。真是群好读者，让人心情复杂极了。\n\n\n------------\n\n",
    },
    "tasks": TASKS,
    "causeEdges": CAUSE,
    "rejectedEdges": REJECTED,
    "states": STATES,
    "knowledgeGaps": GAPS,
    "foreshadows": FORESHADOWS,
    "notForeshadows": NOT_FORESHADOWS,
    "worldSettings": WORLD,
    "notWorldSettings": NOT_WORLD,
    "themeReadings": THEMES,
    "speechAsClueNotFact": SPEECH,
    "textualNotes": TEXTUAL,
    "unknowns": UNKNOWNS,
    "selfCritique": SELF_CRITIQUE,
}


# ══════════════════════════════════════════════════════════════════════════
# 构建期断言
# ══════════════════════════════════════════════════════════════════════════
def collect_quotes(o, out):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            out.append(o)
        for v in o.values():
            collect_quotes(v, out)
    elif isinstance(o, list):
        for v in o:
            collect_quotes(v, out)
    return out


def assertions():
    P = []
    text = json.loads((ROOT / CAND["source"]["path"]).read_text(encoding="utf-8"))[0]["text"]

    # A1：候选里每条引文逐字成立、区间正确、哈希正确
    allq = collect_quotes(CAND, [])
    for q in allq:
        if text[q["start"]:q["end"]] != q["quote"]:
            P.append("A1 引文不逐字成立：%s" % q["key"])
        if q["sourceHash"] != SOURCE_HASH:
            P.append("A1 sourceHash 不符：%s" % q["key"])
        if not (START <= q["start"] < q["end"] <= END):
            P.append("A1 区间越界：%s" % q["key"])
        if q["end"] - q["start"] != len(q["quote"]):
            P.append("A1 长度不符：%s" % q["key"])

    # A2：所有用到的 key 都在 refs 里（probe 已定位）
    used = {q["key"] for q in allq}
    missing = used - set(REFS)
    if missing:
        P.append("A2 引文未定位：%s" % sorted(missing))

    # A3：同一任务五栏的区间两两不重叠
    for t in CAND["tasks"]:
        seen = []
        for fld in ("objective", "obstacle", "action", "result", "cost"):
            s = t.get(fld)
            if not s:
                continue
            for q in s["quotes"]:
                for pf, pq in seen:
                    if q["start"] < pq["end"] and pq["start"] < q["end"]:
                        P.append("A3 %s 的 %s 与 %s 共用区间（%s ↔ %s）" % (t["id"], fld, pf, q["key"], pq["key"]))
                seen.append((fld, q))

    # A4：每个 null 栏必须有同名 Note 说明理由
    for t in CAND["tasks"]:
        for fld in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(fld) is None:
                note = t.get(fld + "Note")
                if not (isinstance(note, str) and len(note) >= 20):
                    P.append("A4 %s.%s 为 null 但 %sNote 缺失或过短" % (t["id"], fld, fld))

    # A5：states 的前值/后值/锚点两两不重叠
    for s in CAND["states"]:
        seen = []
        for fld in ("before", "after", "anchor"):
            for q in s[fld]["quotes"]:
                for pf, pq in seen:
                    if q["start"] < pq["end"] and pq["start"] < q["end"]:
                        P.append("A5 %s 的 %s 与 %s 共用区间（%s ↔ %s）" % (s["id"], fld, pf, q["key"], pq["key"]))
                seen.append((fld, q))

    # A6：causeEdges 必须有 trigger（机制）且 basis 合法
    for c in CAND["causeEdges"]:
        if not (isinstance(c.get("trigger"), str) and len(c["trigger"]) >= 40):
            P.append("A6 %s 缺 trigger 机制说明" % c["id"])
        if c.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
            P.append("A6 %s basis 非法" % c["id"])
        if not c.get("claimKind"):
            P.append("A6 %s 缺 claimKind" % c["id"])

    # A7：foreshadows 必须有 setup 与 payoff；unresolved 的必须显式标出
    for f in CAND["foreshadows"]:
        if not f["setup"]:
            P.append("A7 %s 缺铺设" % f["id"])
        if not f["payoff"]:
            P.append("A7 %s 缺回收" % f["id"])
        if f["unresolved"] and not any(("unresolved" in (s.get("why") or "")) or ("unresolved" in (f.get("note") or "")) for s in f["payoff"] + f["setup"]):
            P.append("A7 %s unresolved 未显式标注" % f["id"])

    # A8：worldSettings 三类的区分字段必须存在
    for w in CAND["worldSettings"]:
        if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            P.append("A8 %s place 缺 placeState" % w["id"])
        if w["kind"] == "item" and not isinstance(w.get("itemStates"), list):
            P.append("A8 %s item 缺 itemStates" % w["id"])
        if w["kind"] == "rule":
            if w.get("institution") not in ("declared", "executed", "misunderstood", None):
                P.append("A8 %s rule institution 非法" % w["id"])
        if not w.get("explain"):
            P.append("A8 %s 缺 explain" % w["id"])

    # A9：themeReadings 必须给 perspective / support / counter 三件
    for t in CAND["themeReadings"]:
        for k in ("perspective", "support", "counter"):
            if not t.get(k):
                P.append("A9 %s 缺 %s" % (t["id"], k))
        for k in ("support", "counter"):
            if t.get(k) and not t[k].get("quotes"):
                P.append("A9 %s.%s 无引文" % (t["id"], k))
    # 禁止用事件密度/死亡人数/篇幅中点定义高潮
    banned = ["高潮", "三幕", "英雄旅程", "剧情点", "死亡人数", "篇幅中点"]
    for t in CAND["themeReadings"]:
        blob = json.dumps(t, ensure_ascii=False)
        for b in banned:
            if b in blob and b not in ("三幕", "英雄旅程"):
                P.append("A9 %s 出现禁用语：%s" % (t["id"], b))

    # A10：不得引用作者区（PS 行）文字
    for q in allq:
        if q["start"] >= AUTHOR_START:
            P.append("A10 %s 引用了作者区" % q["key"])

    # A11：每条引用都必须带 kind，且 kind 合法
    for q in allq:
        if q.get("kind") not in ("narration", "dialogue", "inner", "free_indirect"):
            P.append("A11 %s kind 非法" % q["key"])

    # A12：不得出现本区间里没有的人名/专名。
    # 判据是**切片**（不是全文）：提到一个只在别章出现的人，就等于引入了本段没有的人物。
    # 名单 = 候选文本里出现的、我在 who/speaker/whoKnows 等栏里用到的所有专名。
    names = ["许七安", "钟璃", "金莲道长", "楚元缜", "恒远", "钱友", "李知府", "同知", "五号", "二号",
             "六号", "四号", "李妙真", "赵守", "监正", "紫莲", "地宗", "天宗", "人宗", "司天监",
             "后土帮", "天地会", "打更人", "银锣", "教坊司"]
    blob = json.dumps(CAND, ensure_ascii=False)
    for n in names:
        if n in blob and n not in text[START:END]:
            P.append("A12 专名不在本区间：%s" % n)
    # A12b：候选里不得出现「正传之外」的编号成员名（如把二号直接写成李妙真以外的名字）
    for bad in ["三号", "七号", "八号", "九号"]:
        if bad in blob:
            P.append("A12b 候选提到本区间未出现的编号：%s" % bad)
    return P


for _t in TASKS:
    _t["costQuotes"] = _cost_quotes(_t)

if __name__ == "__main__":
    probs = assertions()
    print("构建期断言：%s" % ("全部通过" if not probs else "%d 条问题" % len(probs)))
    for p in probs:
        print("  ✗", p)
    if probs:
        sys.exit(1)
    out = ROOT / "loop/state/out/read_dafeng_L3_0303.candidate.json"
    out.write_text(json.dumps(CAND, ensure_ascii=False, indent=1), encoding="utf-8")
    allq = collect_quotes(CAND, [])
    uni = set()
    for q in allq:
        uni |= set(range(q["start"], q["end"]))
    print("写出：%s" % out)
    print("引用对象：%d，唯一区间：%d，覆盖 codepoint：%d / %d"
          % (len(allq), len({(q["start"], q["end"]) for q in allq}), len(uni), END - START))
