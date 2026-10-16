# -*- coding: utf-8 -*-
"""sceneAnchors（覆盖未锚定段落）+ claimLedger（说法 vs 事实）+ 段落覆盖"""
from build import (B, I, D, U, NAR, UTT, MIX, INF, Q, F, OFF, QUOTES, SOURCE_HASH, TEXT, SEG, START, END)

# 补充引文（仅用于场景锚定与说法台账，不新增人物/事件断言）
EXTRA = {
 "tied": "只见那呆子绷在树上，声声叫喊，痛苦难禁",
 "untie": "沙僧见了老大不忍，放下行李，上前解了绳索救下",
 "xijiangyue": "色乃伤身之剑，贪之必定遭殃",
 "pray": "那八戒撮土焚香，望空礼拜",
 "dressfull": "骨清神爽容颜丽，顶结丫髻短发鬅。道服自然襟绕雾，羽衣偏是袖飘风。环绦紧束龙头结，芒履轻缠蚕口绒。丰采异常非俗辈，正是那清风明月二仙童。",
 "bow": "那童子控背躬身，出来迎接道：“老师父，失迎，请坐。”",
 "hall": "原来是向南的五间大殿，都是上明下暗的雕花格子",
 "mount_verse": "高山峻极，大势峥嵘。根接昆仑脉，顶摩霄汉中。",
 "garden1": "流杯亭外，一弯绿柳似拖烟；赏月台前，数簇乔松如泼靛。红拂拂，锦巢榴；绿依依，绣墩草。青茸茸，碧砂兰；攸荡荡，临溪水。",
 "garden2": "丹桂映金井梧桐，锦槐傍朱栏玉砌。有或红或白千叶桃，有或香或黄九秋菊。荼蘼架，映着牡丹亭；木槿台，相连芍药圃。看不尽傲霜君子竹，欺雪大夫松。更有那鹤庄鹿宅，方沼圆池；泉流碎玉，地萼堆金。朔风触绽梅花白，春来点破海棠红。诚所谓人间第一仙景，西方魁首花丛。",
 "veg3": "蔓菁萝卜羊头埋，红苋青菘紫芥。",
 "veg_verse2": "笋薯瓜瓠茭白，葱蒜芫荽韭薤。窝蕖童蒿苦荬，葫芦茄子须栽。",
 "veg_verse": "布种四时蔬菜，菠芹莙荙姜苔。",
 "fruit_verse": "真个是青枝馥郁，绿叶阴森，那叶儿却似芭蕉模样",
}
EXTRA_OFF = {}
for k, q in EXTRA.items():
    c = TEXT.count(q)
    assert c == 1, "补充引文非唯一 %s %d" % (k, c)
    i = TEXT.find(q)
    assert START <= i and i + len(q) <= END, "补充引文越界 %s" % k
    assert TEXT[i:i + len(q)] == q
    EXTRA_OFF[k] = (i, i + len(q))

def X(*keys):
    out = []
    for k in keys:
        if k in EXTRA:
            a, b = EXTRA_OFF[k]; q = EXTRA[k]
        else:
            a, b = OFF[k]; q = QUOTES[k]
        from build import fact_status  # noqa
        out.append({"quote": q, "start": a, "end": b, "sourceHash": SOURCE_HASH,
                    "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（非切片相对偏移）",
                    "factStatus": fact_status(a, b)})
    return out

sceneAnchors = [
 {"id": "A1", "paragraph": "回初八戒仍被吊在树上、沙僧解绳救下（[164197,164443)）",
  "kind": "narrative-scene", "whatItDoes": "承接上一回的惩戒场景并收尾：八戒被吊、被行者抢白、"
     "沙僧解绳、八戒撮土焚香礼拜，最后三藏一句「既如此说才是」认可他的悔过话。"
     "本段不含任何对后文的承诺，只作场景交代。",
  "basis": B, "claimStatus": MIX, "evidence": X("tied", "untie", "xijiangyue", "pray")},
 {"id": "A2", "paragraph": "上山前对山景的韵文与师徒问答（[164445,165340) 内）",
  "kind": "verse+scene", "whatItDoes": "以韵文写「高山峻极…根接昆仑脉，顶摩霄汉中」的山势，"
     "并交代本单元的地理前提：三藏勒马提醒「恐有妖魔作耗」、行者宽慰、以及路程问答"
     "（「十万八千里，十停中还不曾走了一停」）。韵文本身不构成事件断言。",
  "basis": B, "claimStatus": MIX, "evidence": X("mount_verse", "shan_warn", "dist", "lingshan")},
 {"id": "A3", "paragraph": "五庄观内殿的形制与二童出场打扮（[166512,166742)）",
  "kind": "description+verse", "whatItDoes": "两道童出场：「急急忙忙，走出两个小童儿来」；"
     "韵文写二人打扮；「控背躬身，出来迎接」；随后写正殿形制「向南的五间大殿…雕花格子」，"
     "壁上挂「天地」二字。纯场景与形制描写，不构成事件断言；"
     "它说明接待是在正殿进行的（与后文末段「径来殿上」同一地点）。",
  "basis": B, "claimStatus": MIX, "evidence": X("dressfull", "bow", "hall")},
 {"id": "A4", "paragraph": "入园前花园的三段韵文（[168811,169066)）",
  "kind": "verse", "whatItDoes": "行者推开两扇门后所见的花园：流杯亭、赏月台、各类花木与"
     "「鹤庄鹿宅，方沼圆池」，结句「诚所谓人间第一仙景，西方魁首花丛」。"
     "纯景物韵文；随后接菜园韵文（菠芹莙荙、笋薯瓜瓠、蔓菁萝卜等）。"
     "两者共同交代了从道房到人参园之间的路径层次（花园→菜园→又一层门），"
     "这一路径在末段二童查园时被逐门复述（见 C25）。",
  "basis": B, "claimStatus": NAR, "evidence": X("garden1", "garden2", "veg_verse", "veg_verse2", "veg3")},
 {"id": "A5", "paragraph": "「果然罕见！果然罕见！」与上树（[169264,169290)）",
  "kind": "narrative-scene", "whatItDoes": "行者在树下赞叹后「倚着树，飕的一声，撺将上去」——"
     "这是本单元里他第一次上树，紧接着就是第一次敲果（C14）。"
     "该句是动作交代，不是对果子功效的判断。",
  "basis": B, "claimStatus": NAR, "evidence": X("rare2", "climb")},
]

claimLedger = [
 {"id": "L1", "speaker": "清风、明月", "claim": "「定是那伙恶人偷了」／「莫敢是他偷了我们宝贝么？」",
  "status": "claim-not-fact", "why": "二童没有目击偷果过程。他们掌握的证据是金击子落地、"
    "两道门开着、树上少四个。原文用「莫敢是」「定是」的都是二童口中。"
    "注意区分：叙述者确有一次直述用「偷」，但说的是行者习性——「那猴子原来第一会爬树偷果子」——"
    "并非对本次事件「他们偷了」的认定（见 unknowns U9，我先前写错此处、已改）。"
    "二童那句「定是那伙恶人偷了」仍不得当叙述事实引用。",
  "evidence": X("suspect", "thief", "hook_down", "gate_open", "count_now")},
 {"id": "L2", "speaker": "清风", "claim": "「你偷吃了人参果，怎么不容我说」",
  "status": "claim-not-fact", "why": "指控对象是唐僧，而唐僧恰恰是唯一拒食的人（L3）。"
    "这句是二童在骂人时说的话，与原文写出的事实相反。",
  "evidence": X("accuse_tc", "refuse1", "push")},
 {"id": "L3", "speaker": "唐三藏", "claim": "「就是害了馋痞，也不敢干这贼事」",
  "status": "claim-consistent-with-narration", "why": "他的话与叙述者写的事实一致"
    "（「千推万阻不吃」「只得拿着盘子，转回本房」），故可作为他的立场引用；"
    "但「一致」仍不等于叙述者直述他未吃——他未吃是叙述者写的，他不承认是他说的话。",
  "evidence": X("swear", "refuse3", "push")},
 {"id": "L4", "speaker": "猪八戒", "claim": "「我也不知有核无核，就吞下去了」／「吃的忙了些…尝出些滋味」",
  "status": "claim-about-self", "why": "关于自己吃相的自述，与叙述者写的「毂辘的囫囵吞咽下肚」一致。"
    "可作他的自陈引用。",
  "evidence": X("nocore", "gulp", "more")},
 {"id": "L5", "speaker": "花园土地", "claim": "「这宝贝乃是地仙之物，小神是个鬼仙，怎么敢拿去？」",
  "status": "claim-about-self", "why": "自辩之词。他的清白在本单元内由行者的试验**间接**支持"
    "（土上无痕说明果子确实入土），但「小神不敢拿」这句本身仍是他的自陈。",
  "evidence": X("land_deny", "test_soil", "admit_wrong")},
 {"id": "L6", "speaker": "花园土地", "claim": "人参果「遇金而落，遇木而枯，遇水而化，遇火而焦，遇土而入」",
  "status": "explanation-verified-in-part", "why": "这段规则里只有「遇土而入」在本单元内被实测"
    "（筑地无痕）；「遇木而枯」「遇水而化」「遇火而焦」本单元没有任何验证。"
    "故我把整段记为土地的说明，只有「遇土而入」与实测相连（C14/C17/C18）。",
  "evidence": X("wuxing", "test_soil", "earth_in")},
 {"id": "L7", "speaker": "猪八戒", "claim": "「他就瞒着我们，才自在这隔壁房里，一家一个，啯啅啯啅的吃了出去」",
  "status": "claim-consistent-with-narration", "why": "与叙述者写的事实一致"
    "（二童「一家一个，坐在床边上，只情吃起」）。但他加上了「瞒着我们」这一评价，"
    "而叙述者的写法是「只得拿着盘子，转回本房」——「瞒」是他的解读，不是叙述事实。",
  "evidence": X("bj_tell2", "two_eat", "push")},
 {"id": "L8", "speaker": "孙悟空", "claim": "「你不知老孙是盖天下有名的贼头」",
  "status": "self-characterization", "why": "自称，且是为质问土地而说的修辞。"
    "不得读成叙述者对这个角色的定性。",
  "evidence": X("accuse")},
 {"id": "L9", "speaker": "沙僧", "claim": "「不好了！决撒了！…不是旧话儿走了风，却是甚的？」",
  "status": "inference-by-character", "why": "反问形式，是他从「师父叫」+「道童骂」两个信号推出的判断，"
    "不是叙述者宣布事已败露。见 C30（该边我记 basis=inferred）。",
  "evidence": X("sha_panic", "call_all")},
 {"id": "L10", "speaker": "孙悟空", "claim": "「若说出来，就是我们偷嘴了，只是莫认」",
  "status": "plan-not-outcome", "why": "这是他们在厨房里定下的对策；本单元在他们上殿时结束，"
    "没有写对策是否奏效。不得把「商量抵赖」写成「抵赖成功」。见 F9、O1。",
  "evidence": X("xz_shame", "bj_agree", "go_up", "tail")},
 {"id": "L12", "speaker": "清风（内心）", "claim": "「这和尚在那口舌场中，是非海里，弄得眼肉胎凡，不识我仙家异宝」",
  "status": "character-inner-thought", "why": "叙述者转述的清风的心里话（原文作「清风暗道」），"
    "是他对唐僧拒食的评价，不是叙述者对唐僧的判断。它同时解释了二童此后为何不再解释、"
    "直接把果子拿回房自己吃（见 C07/C08）。",
  "evidence": X("qf_inner", "push", "two_eat")},
 {"id": "L11", "speaker": "明月", "claim": "「果子原是三十个…如今止剩得二十二个，却不少了四个？」",
  "status": "arithmetic-consistent", "why": "这笔账在数字上自洽（30−2−2=26，26−22=4），"
    "是本单元内可机械复核的一处；但「四个都是那伙恶人偷了」是他随后的推断（L1），"
    "账目正确不等于推断正确（其中一个落地入土，见 K2）。",
  "evidence": X("arith", "count_now", "thief")},
]
