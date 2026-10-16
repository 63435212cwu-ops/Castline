# -*- coding: utf-8 -*-
"""构建 read:xiyou:L0:0024 候选。所有引文由本脚本机械解析偏移并断言逐字命中。"""
import json, hashlib, sys, datetime, io, os

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/df959d743e53206f56db2f92.docs.json")
GRAPH = os.path.join(ROOT, "data/cache/df959d743e53206f56db2f92.json")
OUT = os.path.join(ROOT, "loop/state/out/read_xiyou_L0_0024.candidate.json")
SOURCE_HASH = "c282cf39b2ae739a15a3efe4a0e83af546c525bcaad3bac6e21c9d6179a152a2"
START, END = 164172, 171564
TASK = "read:xiyou:L0:0024"
AGENT = "w-sanguo-1"
UNIT_HEAD = "第二十四回　万寿山大仙留故友　五庄观行者窃人参"

import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from quotes import QUOTES  # noqa

raw = open(DOCS, "rb").read()
assert hashlib.sha256(raw).hexdigest() == SOURCE_HASH, "sourceHash 不符"
TEXT = json.loads(raw)[0]["text"]
SEG = TEXT[START:END]
SEG_SHA = hashlib.sha256(SEG.encode("utf-8")).hexdigest()

# ---- 机械解析引文：全文唯一 + 落在区间内 ----
OFF = {}
for k, q in QUOTES.items():
    c = TEXT.count(q)
    assert c == 1, "引文非唯一 %s count=%d" % (k, c)
    i = TEXT.find(q)
    assert START <= i and i + len(q) <= END, "引文越界 %s %d" % (k, i)
    assert TEXT[i:i + len(q)] == q, "逐字不符 %s" % k
    OFF[k] = (i, i + len(q))

# ---- 机械判定 factStatus：以切片内 “ ” 配对区间为界 ----
pairs, stack = [], []
for idx, ch in enumerate(SEG):
    if ch == "\u201c":
        stack.append(idx)
    elif ch == "\u201d":
        assert stack, "引号不配对 @%d" % idx
        pairs.append((stack.pop() + START, idx + START))
assert not stack, "引号未闭合"
OPEN_PAIRS = len(pairs)

def fact_status(a, b):
    inside = any(pa <= a and b <= pb for pa, pb in pairs)
    if inside:
        return "utterance"
    crossed = any(a < pa and pb < b for pa, pb in pairs)
    return "mixed" if crossed else "narrated"

def Q(*keys):
    """构造引文节点列表。"""
    out = []
    for k in keys:
        a, b = OFF[k]
        out.append({"quote": QUOTES[k], "start": a, "end": b, "sourceHash": SOURCE_HASH,
                    "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（非切片相对偏移）",
                    "factStatus": fact_status(a, b)})
    return out

def F(text, basis, claim, keys):
    """构造一个五元组子字段。keys 为空 → None（原文确无此项）。"""
    if keys is None:
        return None
    return {"text": text, "basis": basis, "claimStatus": claim, "evidence": Q(*keys)}

B = "explicit"; I = "inferred"; D = "derived"; U = "unverified"
NAR = "narrator"; UTT = "dialogue"; MIX = "dialogue+narrator"; INF = "reader-inference"

# =============================== tasks ===============================
tasks = [
 {
  "id": "T1", "actor": "镇元子（原文：镇元大仙、大仙、观里一尊仙，道号镇元子，混名与世同君）",
  "label": "受元始天尊简帖赴弥罗宫听讲，同时把接待故人唐僧的事交代给留守二童",
  "objective": F("受元始天尊的简帖之邀，到上清天弥罗宫听讲混元道果；同时遵帖不违、不怠慢",
                 B, NAR, ["yuanshi", "leaves46"]),
  "obstacle": F("他去听讲与接待故人不能兼顾：只能留下两个绝小的徒弟看家；且他自陈果子「有数」"
                "（只许打两个），又要防唐僧手下人罗唣",
                B, MIX, ["leaves46", "no_more", "guard"]),
  "action": F("临行吩咐清风明月接待；交代故人身份（东土大唐驾下圣僧，道号三藏，今往西天拜佛求经）"
              "与缘由（金蝉子转生、五百年前兰盆会相识、亲手传茶）；叮咛只许打两个果子、"
              "「不可多费」、要防手下人罗唣；嘱咐完承众徒弟飞升上天",
              B, NAR, ["order_give", "who_sanzang", "jinchan", "no_more", "guard", "ascend"]),
  "result": F("安排已下达，他本人不在场执行结果：他带领四十六个上界去听讲，家里只剩清风、明月二童；"
              "至于接待是否办成，本单元写的是徒弟李代桃僵（见 T2/T3），他本人未回、未见到结果——"
              "不写 result=成功",
              B, NAR, ["leaves46", "ascend"]),
  "cost": None,
  "costNullReason": "原文没有写镇元子为这次赴会付出任何东西（徒弟数目、果子数目都只是交代与账目，"
                    "没有一处把它写成损失或代价）。不补一个听起来合理的值。",
 },
 {
  "id": "T2", "actor": "清风、明月（原文：两个绝小的看家、二童、二仙童、道童、小童儿）",
  "label": "遵师命接待唐僧并打两个人参果与他吃，同时防他手下人罗唣",
  "objective": F("遵师命办接待：问明来人是不是师父的故人、办茶、把人参果打两个与唐僧吃「权表旧日之情」",
                 B, MIX, ["order_give", "ask_who", "doubt", "go_get"]),
  "obstacle": F("三重：① 他们并不认识唐僧，得先问一句「莫要错了」；② 唐僧不认得人参果，"
                "把它当成三朝未满的孩童，「千推万阻不吃」；③ 果子本身「久放不得，若放多时即僵了」",
                B, MIX, ["doubt", "refuse1", "refuse2", "refuse3", "push", "rot"]),
  "action": F("问明身份、办茶奉献；到房中取金击子与丹盘（用丝帕垫盘底）到人参园敲下两个果子；"
              "捧到前殿说「土仪素果二枚，权为解渴」；被拒后转回本房；最后「一家一个，坐在床边上，只情吃起」",
              B, MIX, ["ask_id", "tools", "knock2", "offer", "push", "two_eat"]),
  "result": F("师命在唐僧那一头落空（果子一个也没送出去），两个果子由他们自己吃了；"
              "随后因金击子落地、园门开、树上少了果子而查园、算账、上殿指着唐僧乱骂——"
              "接待以对骂收场，不写成功",
              B, MIX, ["push", "two_eat", "hook_down", "gate_open", "count_now", "arith", "abuse"]),
  "cost": F("付出的是师父交代的那两个果子（「只许与他两个」，结果被他们自己吃掉），"
            "以及接待从此变成指控",
            B, MIX, ["no_more", "two_eat", "abuse"]),
 },
 {
  "id": "T3", "actor": "唐三藏（本单元原文称：三藏、唐僧、长老、老师父、师父、贫僧）",
  "label": "路过万寿山五庄观，歇息吃饭后继续西行",
  "objective": F("西行取经途中歇脚：他自述的安排是「各依执事，让我在此歇息歇息，饭毕就行」，"
                  "并明确不许惹事（「他师既是不在，搅扰他做甚？」）",
                 B, UTT, ["assign", "assign2", "xzang_stop"]),
  "obstacle": F("① 前路尚远（行者报「十万八千里，十停中还不曾走了一停」）；"
                "② 他自己的顾虑是「恐有妖魔作耗，侵害吾党」；"
                "③ 门下徒弟与道童当场起冲突，他怕「斗起祸来」；"
                "④ 末段被道童指控偷吃人参果",
                 B, MIX, ["shan_warn", "dist", "xzang_stop", "accuse_tc"]),
  "action": F("礼拜拈香、问供养之事；制止行者与道童争竞；给三个徒弟分派执事后自己歇息；"
              "面对道童奉献的人参果「千推万阻不吃」；被骂后问明缘由、发誓自己没吃、"
              "答应「等我问他们看。果若是偷了，教他赔你」；最后叫「徒弟，且都来」",
              B, MIX, ["ask_tiandi", "xzang_stop", "assign", "refuse1", "refuse2", "refuse3",
                        "ask_calm", "swear", "you_pay", "call_all"]),
  "result": F("本单元内没有结果：他本人确实没吃（「千推万阻不吃」），却背上「偷吃了人参果」的指控，"
              "只争取到「你且莫嚷，等我问他们看」；而三个徒弟已经商定「只是莫认」再上殿。"
              "回末以「毕竟不知怎么与他抵赖，且听下回分解」收束——不写成功，本单元未给结局",
              B, MIX, ["push", "accuse_tc", "swear", "you_pay", "xz_shame", "go_up", "tail"]),
  "cost": F("① 受辱：被道童「指着唐僧，秃前秃后，秽语污言不绝口的乱骂」；"
            "② 背书：他替徒弟许下赔偿/赔礼（「教他赔你」「教他陪你个礼」），"
            "而徒弟们正在商量赖掉",
            B, MIX, ["abuse", "you_pay", "renyi", "xz_shame"]),
 },
 {
  "id": "T4", "actor": "行者（本单元原文称：行者、大圣、悟净之师兄「哥哥」、老孙；回目作「行者」）",
  "label": "受八戒之托，到人参园偷果子来给兄弟三人尝新",
  "objective": F("接受八戒的请求去偷人参果（「我想你有些溜撒，去他那园子里偷几个来尝尝，如何？」），"
                  "并应承「这个容易，老孙去手到擒来」；他先前的自负是「那般儿不曾见？」",
                 B, MIX, ["ask_steal", "promise", "seen_all"]),
  "obstacle": F("① 他不认得人参果，原文写他「这个真不曾见」，只有「常闻得人说」的传闻；"
                "② 他不知道采摘规矩，第一次敲下的果子落地就「寂然不见」；"
                "③ 道童在防着他们，八戒特意叮嘱「须是干得停当，不可走露风声」",
                 B, MIX, ["admit", "heard_rumor", "warn_hook", "lost"]),
  "action": F("隐身进道房（趁二童不在）取下窗棂上挂的金击子；穿花园、菜园到人参树下；"
              "第一次敲下一个果子落地不见了，拘花园土地前来质问；听了土地讲的五行相畏后"
              "掣金箍棒筑地验证，认错放土地回去；改用锦布直裰的襟做兜子，「串枝分叶，敲了三个果」；"
              "回厨房分给八戒、沙僧，并叫上沙僧一份；最后「把一个金击子，瞒窗眼儿，丢进他道房里」",
              B, MIX, ["hide_in", "think_hook", "knock1", "lost", "summon", "accuse",
                        "test_soil", "admit_wrong", "plan", "knock3", "no_sneak", "throw_hook"]),
  "result": F("拿到三个果子、兄弟三人各吃一个（行动层面达成）；但没有脱身：他自己第一次敲落的那个"
              "果子谁也没吃到（遇土而入），道童随后发现金击子落地、园门开、树上少了四个，"
              "三人商量「只是莫认」上殿去——本单元内事情已经败露，不写成功",
              B, MIX, ["knock3", "all_three", "hook_down", "gate_open", "count_now", "xz_shame", "go_up"]),
  "cost": F("① 白丢一个果子（第一次敲下的那个「寂然不见」，他没得到）；"
            "② 因先前的错判得罪土地（他自陈「我却错怪了你了」）；"
            "③ 被卷进与道童的冲突，末了要「莫认」抵赖",
            B, MIX, ["lost", "admit_wrong", "xz_shame"]),
 },
 {
  "id": "T5", "actor": "八戒（本单元原文称：八戒、呆子、那呆子、长嘴和尚、老猪、二哥）",
  "label": "吃人参果尝新，吃了还想再吃",
  "objective": F("要吃人参果「尝新」（「怎得一个儿尝新！」）；吃到一个之后又升级为「再去弄个儿来，"
                  "老猪细细的吃吃」",
                 B, MIX, ["drool", "more"]),
  "obstacle": F("① 他自己动不了手：「自家身子又狼犺，不能彀得动，只等行者来，与他计较」；"
                "② 果子稀缺，行者明说「象这一万年只结得三十个…不等小可」；"
                "③ 他得先说服行者去偷，所以要先卖关子（「说与你，你不曾见；拿与你，你不认得」）",
                 B, MIX, ["body", "only30", "treasure"]),
  "action": F("在厨房隔墙偷听道房言语（「先前听见说取金击子，拿丹盘，他已在心；又听见他说唐僧"
              "不认得是人参果，即拿在房里自吃」）；在锅门前「更无心烧火，不时的伸头探脑」；"
              "招手叫行者来、告诉他观里有宝贝、激他去偷、并叮嘱「不可走露风声」；"
              "果子到手后「张开口，毂辘的囫囵吞咽下肚」；吞完又「白着眼胡赖」说不知味道、再讨一个；"
              "被行者拒绝后「只管絮絮叨叨的唧哝」；上了殿还「正是，正是，昧了罢」",
              B, MIX, ["bj_heard", "bj_heard2", "peek", "call", "treasure", "bj_tell", "bj_tell2",
                        "ask_steal", "warn_hook", "gulp", "ask_taste", "nocore", "more",
                        "mutter", "bj_agree"]),
  "result": F("只吃到一个人参果，而且是囫囵吞的——他自己承认「我也不知有核无核，就吞下去了」；"
              "再要一个被行者用「罢罢罢！彀了！」挡回。更要紧的是他的唧哝把事败露了："
              "「只听得八戒还嚷甚么『人参果吃得不快活，再得一个儿吃吃才好』」→ 清风起疑。"
              "本单元内他的目标只部分达成，不写成功",
              B, MIX, ["gulp", "nocore", "more", "only30", "tea_heard", "suspect"]),
  "cost": F("① 吃了一个却不知滋味（囫囵吞咽，连有没有核都不知道）；"
            "② 他的嘴把三人一起暴露：「人参果吃得不快活，再得一个儿吃吃才好」被取茶回来的道童听见，"
            "直接引出查园与对骂",
            B, MIX, ["nocore", "tea_heard", "suspect", "abuse"]),
 },
 {
  "id": "T6", "actor": "沙僧（原文：沙僧、悟净、兄弟、卷帘大将）",
  "label": "被八戒叫来分一个人参果",
  "objective": F("本单元内他没有主动谋取，先是被叫（「悟净，你来」），到场后提出「哥哥，可与我些儿尝尝？」；"
                  "他并自陈身份来路「旧时做卷帘大将」",
                 B, MIX, ["call_sha", "sha_story", "one_each"]),
  "obstacle": F("他自己说「虽不曾吃」过人参果；他本来的执事是守行李（「沙僧看守行李」），"
                "是被八戒招手叫进厨房的",
                 B, MIX, ["sha_story", "assign", "call_sha"]),
  "action": F("撇下行李进厨房；一见就认出「是人参果」；讲出旧时在蟠桃宴上「尝见海外诸仙将此果与王母上寿。"
              "见便曾见，却未曾吃」；开口要尝；随行者「兄弟们一家一个」分食",
              B, MIX, ["call_sha", "sha_recog", "sha_story", "one_each", "all_three"]),
  "result": F("吃到一个（「他三人将三个果各各受用」）；随后听见师父叫就断定事败（「不好了！决撒了！」），"
              "并跟着行者「只是莫认」——他也成了赖账的一方，不写成功",
              B, MIX, ["all_three", "sha_panic", "xz_shame"]),
  "cost": F("① 放下本职（行李）进厨房分果子；② 从此也背着偷嘴与「莫认」的约定",
            B, MIX, ["call_sha", "xz_shame"]),
 },
 {
  "id": "T7", "actor": "花园土地（原文：那花园土地、土地、小神）",
  "label": "被行者拘来质问，自证没有拿走落地的果子",
  "objective": F("应行者呼唤前来（「大圣，呼唤小神，有何吩咐？」）并自证清白："
                  "「这宝贝乃是地仙之物，小神是个鬼仙，怎么敢拿去？」",
                 B, MIX, ["summon", "land_deny"]),
  "obstacle": F("行者先入为主地咬定是他「抽了我的头分去了」，还说「怎么刚打下来，你就捞了去？」",
                B, UTT, ["accuse"]),
  "action": F("否认拿果子（「就是闻也无福闻闻」）；应行者追问讲出人参果的出处与「五行相畏」："
              "遇金而落、遇木而枯、遇水而化、遇火而焦、遇土而入；说明敲时必用金器、"
              "接果须用丝帕衬垫的盘、吃须用磁器清水化开；点出「遇土而入者，大圣方才打落地上，"
              "他即钻下土去了」；并主动提出验证法「大圣不信时，可把这地下打打儿看」",
              B, MIX, ["land_deny", "origin", "wuxing", "must_gold", "eat_cup", "earth_in", "test_soil"]),
  "result": F("行者用金箍棒筑地、土上果然无痕，随即认错「我却错怪了你了，你回去罢」，"
              "土地「即回本庙去讫」。他被冤枉又被放回。这是本单元里唯一一处**在单元内形成闭环**的"
              "目标：诬告被实测推翻、行者当面收回指控、他获准返回。"
              "我写它「达成」的依据是这两句原文（认错 + 放归），不是「这一回读完了」——"
              "单元结束本身不构成任何目标达成的证据。",
              B, MIX, ["test_soil", "admit_wrong"]),
  "cost": None,
  "costNullReason": "原文没有写土地为这次被拘付出任何东西（他被冤枉、被质问，但既未受罚也未失物，"
                    "「那土地即回本庙去讫」即结束）。不补一个听起来合理的值。",
 },
]
