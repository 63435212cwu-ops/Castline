#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构造 read:dafeng:L2:0246（第十七章 心剑）候选。

纪律（与 loop/ROLES/READER.md 一致）：
  · 引文偏移**从不手写**：本文件只给 (段号, 段内子串)，脚本从 docs[0].text 现算
    start/end/wholeTextOccurrences/occurrencesInRange/paraLabel/contentAnchor/sentUnit。
  · 写盘前现算 C1–C17 判据，任一为假即非零码退出、**不写盘**。
  · 每条断言带 basis；每条引用带 sourceHash（整个 docs.json 文件的 sha256）。

用法：
  python3 build_candidate.py --list     # 只解析引文并打印未引用段，不写盘
  python3 build_candidate.py            # 跑全部判据并写候选
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
GRAPH = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"
OUT = ROOT / "loop/state/out/read_dafeng_L2_0246.candidate.json"

TASK_ID = "read:dafeng:L2:0246"
AGENT = "w-dafeng-1"
BOOK = "dafeng"
LANE = 2
UNIT_INDEX = 246
UNIT_HEAD = "第十七章 心剑"
S_START, S_END = 1001227, 1009273
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
# 固定读毕时刻（不取 now()）：否则每次重跑都会因时间戳而改变候选字节，
# 提交记录里声明的 sha256 就**不可复现**。构造脚本必须可复算到同一颗字节。
READ_AT = "2026-10-15T11:14:00Z"
OFFSET_BASE = "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）"

SRC = json.loads(DOCS.read_text(encoding="utf-8"))
TEXT = SRC[0]["text"]
SLICE = TEXT[S_START:S_END]

# ── 段落索引（非空行；段号 P001 起，含标题行）──────────────────────────────
PARAS = []          # [(no, abs_start, text)]
_pos = S_START
_n = 0
for _line in SLICE.split("\n"):
    if _line.strip():
        _n += 1
        PARAS.append((_n, _pos, _line))
    _pos += len(_line) + 1
PARA_BY_NO = {p[0]: p for p in PARAS}
TOTAL_PARAS = len(PARAS)

# ── 引文登记表：id -> (段号, 段内子串 or None 表示整段)──────────────────────
# 只写逐字字符串；偏移由 resolve() 现算。子串必须能在该段内 find 到。
QSPEC = {
    # 第一段：御药房册子线
    "ask_her":            (2, None),
    "nar_ask":            (3, None),
    "read_books":         (5, None),
    "books_complaint":    (6, None),
    "toilet":             (7, None),
    "toilet_answer":      (8, None),
    "earth_book":         (9, None),
    "tear_page":          (10, None),
    "eye_light":          (11, None),
    "confront":           (12, None),
    "old_eunuch_tanran":  (13, None),
    "ask_year32":         (14, None),
    "old_eunuch_forget":  (15, None),
    "no_lie_1":           (16, "没说谎....."),
    "ask_gap":            (16, "查验册子时，本官发现当年二月十日，和二月二十日的收支记录是空缺的，这几日没有丹药送来？"),
    "old_eunuch_forget2": (17, None),
    "no_lie_2":           (18, "还是没说谎，一个老太监不至于有屏蔽气数的法器.......年纪大了就是不中用，忘性大......"),
    "return_books":       (18, "许七安把册子还给老太监，吩咐道："),
    "demand_5days":       (19, None),
    "help_means_watch":   (20, None),
    "eunuch_spy":         (21, None),
    "linan_whisper":      (22, None),
    "fingerprint":        (23, None),
    "linan_praise":       (25, None),
    "eunuch_hesitate":    (26, None),
    "send_old_away":      (27, None),
    "eunuch_glance":      (28, None),
    "linan_angry":        (29, None),
    "xu_says_say":        (30, "许七安皱眉道：“说吧。”"),
    "eunuch_report":      (31, None),
    "dead_silence":       (32, None),
    "xu_infer_huaiqing":  (33, "荷儿是皇后宫里的人，难怪怀庆听见荷儿的名字，情绪就变的不对劲了......."),
    "xu_infer_grace":     (33, "也就是说，当初救下黄小柔的人是皇后娘娘.......换而言之，黄小柔受过皇后大恩。"),
    "xu_infer_role":      (34, "而她在这个案子里充当的角色是谋害福妃子，诬陷太子的急先锋.......皇后有麻烦了。"),
    "heavy_breath":       (35, None),
    "linan_breath":       (36, None),
    "about_to_be_bad":    (37, None),
    "linan_go":           (38, None),
    "linan_rise":         (39, None),
    "xu_grab":            (40, None),
    "linan_reason":       (41, None),
    "linan_jealous":      (42, None),
    "xu_inner_oh":        (44, None),
    "xu_warn1":           (45, None),
    "xu_warn2":           (46, None),
    "linan_stubborn":     (47, None),
    "xu_glare":           (48, None),
    "linan_yield":        (49, None),
    "narr_docile":        (50, None),
    "xu_continue":        (51, None),
    "linan_hmph2":        (52, None),
    "xu_order_report":    (53, None),
    "xu_inner_omit":      (54, None),
    "eunuch_moved":       (55, None),
    "eunuch_promise":     (56, None),
    "xu_shangdao":        (57, "这小公公很上道吗......"),
    "xu_order_list":      (57, "待会儿你去找管理御药房的公公，从他那里要一份名单，五天之内出入御药房的名单。然后，你偷偷的找守卫核对。"),
    "mingbai":            (58, None),
    "leave_pharmacy":     (59, None),
    "xiaoshanfang":       (60, None),
    "someone_calls":      (61, None),
    # 第二段：灵宝观
    "daoist_found":       (62, None),
    "daoist_waited":      (63, None),
    "palace_access":      (64, "能出入皇宫的，必定是灵宝观的道士了。"),
    "daoist_invite":      (65, None),
    "xu_hesitate":        (66, None),
    "luo_is_emperor_woman": (67, None),
    "shenshu_worry":      (68, "另外，洛玉衡是二品强者，许七安不想和关系不熟的顶级强者走的太近，万一突然给人家发现神殊和尚的存在......."),
    "sangbo_joke":        (69, None),
    "five_hundred_years": (70, None),
    "daoist_urge":        (71, None),
    "xu_agrees":          (72, None),
    "luo_tempting":       (73, None),
    "second_visit":       (75, None),
    "daoshou_favor":      (76, None),
    "quiet_room":         (77, None),
    "simple_room":        (78, None),
    "zhai_food":          (79, None),
    "daotong":            (80, None),
    "two_bowls":          (81, None),
    "alone_would_leave":  (82, None),
    "door_squeak":        (83, None),
    "luo_enters":         (84, None),
    "luo_zhusha":         (85, None),
    "xu_greet":           (86, None),
    "luo_gesture":        (87, None),
    "xu_shan":            (88, None),
    "both_eat":           (89, None),
    "xu_unsure":          (90, None),
    "age_illusion1":      (91, None),
    "age_illusion2":      (92, None),
    "age_illusion3":      (93, None),
    "dao_or_yao":         (94, None),
    "renzong_method":     (95, None),
    "three_zong":         (96, None),
    "tian_zong":          (97, None),
    "tian_wuqing":        (98, None),
    "tianren_heyi":       (99, None),
    "luo_asks_pill":      (100, None),
    "xu_startled":        (101, None),
    "luo_asks_blood":     (102, None),
    "xu_silent":          (103, None),
    "blood_uses":         (104, None),
    "zhu_sha":            (105, None),
    "luo_jinlian_advice": (106, None),
    "xu_confirm":         (107, None),
    "luo_nod":            (108, None),
    "xu_takes_earth":     (109, None),
    "luo_he_is_here":     (110, None),
    "cat_on_threshold":   (111, None),
    "xu_asks_cat":        (112, None),
    "cat_jumps":          (113, None),
    "xu_slap_cat":        (114, None),
    "cat_says_access":    (115, None),
    "xu_estimates":       (116, None),
    "not_wufu":           (117, None),
    "wufu_cannot_sneak":  (118, None),
    "yipin_wufu":         (119, None),
    "xu_blood_hesitate":  (120, None),
    "harddisk_joke":      (121, None),
    "jinlian_explains1":  (122, None),
    "jinlian_explains2":  (123, None),
    "xu_bold":            (124, None),
    "xu_would_not_dare":  (125, None),
    "zhongshengxiang":    (126, None),
    "cat_what_did_you_see": (127, None),
    "luo_looks_up":       (128, None),
    "xu_freezes":         (129, None),
    "jinlian_presses":    (130, None),
    "xu_inner_color":     (131, None),
    "xu_agrees_blood":    (132, None),
    "luo_offer_pill":     (133, None),
    "jinlian_no_hurry":   (134, None),
    "luo_glances_cat":    (135, None),
    # 第三段：景秀宫
    "jingxiu_palace":     (137, None),
    "linan_arrives":      (138, None),
    "chen_crying":        (139, None),
    "linan_quiet":        (140, None),
    "linan_comfort":      (141, None),
    "her_mood":           (142, None),
    "as_daughter":        (143, None),
    "maid_report1":       (144, None),
    "maid_report2":       (145, None),
    "linan_rage":         (146, None),
    "calls_uncles_dogs":  (147, None),
    "chen_bitter":        (148, None),
    "linan_knows_whom":   (149, None),
    "dagongnv_sigh":      (150, None),
    "case_is_secret":     (151, None),
    "linan_blurts":       (152, None),
    "chen_eyes_light":    (153, None),
    "chen_grips":         (154, None),
    "hurts_me":           (155, None),
    "linan_accuses":      (156, None),
    "chen_shocked":       (157, None),
    "linan_evidence":     (158, None),
    "tells_everything":   (159, None),
    "chen_outburst":      (160, None),
    "chen_continue":      (161, None),
    "thunder":            (162, None),
    "what_did_she_hear":  (163, None),
    "queen_unchaste":     (164, None),
    "when_was_this":      (165, None),
    "linan_disbelief":    (166, None),
    "details_explained":  (167, None),
    "details_examples":   (168, None),
    "linan_asks_who":     (169, None),
    "anger_justified":    (170, None),
    "chen_seals":         (171, None),
    # 第四段：回到静室
    "luo_no_debt":        (173, None),
    "auntie_joke":        (174, None),
    "xu_no_idea":         (175, None),
    "cat_suggests_sword": (176, None),
    "yuanshen_output":    (199, "控制技能有了，物理伤害有了，现在最缺的是元神领域的输出。"),
    "backyard":           (8, "老太监回答：“后院。”"),
    "xu_agree_no_idea":   (51, "“继续查呗，公主静观其变就是了。”"),
    "linan_praises_him":  (24, None),
    "thin_books":         (181, "洛玉衡抬手，在桌面轻轻抹过，三本薄薄的册子出现。"),
    "xu_uses_saber":      (177, None),
    "cat_rebuts":         (178, None),
    "xu_agrees_core":     (179, None),
    "xu_nods":            (180, None),
    "three_books":        (181, None),
    "luo_lists":          (182, None),
    "xinjian_props":      (183, "心剑需辅以元神修炼，以精神力为磨剑石，日日不辍的磨剑。它无法斩肉身，专斩元神。"),
    "xu_looks_cat":       (184, None),
    "cat_claws":          (185, None),
    "xu_retracts":        (186, None),
    "qijian_props":       (187, None),
    "xu_poem":            (188, None),
    "luo_praises":        (189, None),
    "not_mine":           (190, None),
    "yujian_demo":        (191, None),
    "fast_as_thunder":    (192, None),
    "xu_picks_xinjian":   (193, None),
    "luo_stunned":        (194, None),
    "why_xinjian":        (195, None),
    "saber_art":          (196, None),
    "therefore":          (197, None),
    "lion_roar":          (198, None),
    "lacks_yuanshen":     (199, None),
    "luo_gives_book":     (200, None),
    "xu_thanks":          (201, None),
    "jade_bowl":          (202, None),
    "bowl_small":         (203, None),
    "blood_taken":        (204, None),
    "only_cat_left":      (205, None),
    "xu_wants_private":   (206, None),
    "tell_erhao":         (207, None),
    "jinlian_hehe":       (208, None),
    "xu_asks_problem":    (209, None),
    "jinlian_reason":     (210, None),
    "jinlian_secret":     (211, None),
    "xu_okay":            (212, None),
    # 尾部
    "ps":                 (214, None),
    "sep_line":           (215, None),
    # 单次出现/未归类登记用
    "title":              (1, None),
    "eunuch_obedient":    (4, None),
    "linan_refers_jump":  (43, None),
    "sep1":               (74, None),
    "sep2":               (136, None),
    "sep3":               (172, None),
    "sep4":               (213, None),
}

PARA_TO_IDS = {}
for _qid, (_no, _sub) in QSPEC.items():
    PARA_TO_IDS.setdefault(_no, []).append(_qid)


def _sent_unit(para_text: str, rel: int) -> int:
    """引文起点落在该段第几个句子里（0-based），句末标点按 。！？ 与连续点号切。"""
    n = 0
    i = 0
    while i < rel:
        ch = para_text[i]
        if ch in "。！？":
            n += 1
        elif ch == ".":
            j = i
            while j < len(para_text) and para_text[j] == ".":
                j += 1
            if j - i >= 2:
                n += 1
            i = j - 1
        i += 1
    return n


_RESOLVED = {}


def resolve(qid: str) -> dict:
    """把 (段号, 子串) 变成带全文绝对偏移的引文条目。偏移现算，不手写。"""
    if qid in _RESOLVED:
        return dict(_RESOLVED[qid])
    if qid not in QSPEC:
        raise KeyError("未登记的引文 id：%s" % qid)
    no, sub = QSPEC[qid]
    if no not in PARA_BY_NO:
        raise AssertionError("段号不存在：%s" % no)
    pno, pstart, ptext = PARA_BY_NO[no]
    if sub is None:
        lead = len(ptext) - len(ptext.lstrip())
        body = ptext.strip()
        rel = ptext.index(body)
    else:
        body = sub
        if sub not in ptext:
            raise AssertionError("引文不在段 P%03d 内：%r" % (no, sub))
        rel = ptext.index(sub)
    start = pstart + rel
    end = start + len(body)
    if not (S_START <= start and end <= S_END):
        raise AssertionError("引文越界：%s -> [%d,%d)" % (qid, start, end))
    if TEXT[start:end] != body:
        raise AssertionError("逐字不符：%s" % qid)
    occ_all = [m.start() for m in re.finditer(re.escape(body), TEXT)]
    occ_in = [p for p in occ_all if S_START <= p and p + len(body) <= S_END]
    assert occ_in, "区间内无命中：%s" % qid
    rec = {
        "quote": body,
        "start": start,
        "end": end,
        "sourceHash": SOURCE_HASH,
        "offsetUnit": "codepoint",
        "offsetBase": OFFSET_BASE,
        "match": "exact",
        "wholeTextOccurrences": len(occ_all),
        "occurrencesInRange": len(occ_in),
        "paraLabel": "P%03d" % no,
        "contentAnchor": "P%03d[%d:%d]" % (no, rel, rel + len(body)),
        "sentUnit": _sent_unit(ptext, rel),
    }
    _RESOLVED[qid] = rec
    return dict(rec)


def Q(*qids) -> list:
    return [resolve(q) for q in qids]


# ── 内容分区 ────────────────────────────────────────────────────────────────
# 每条任务：objective / obstacle / action / result / cost 各自独立引证。
TASKS = [
    {
        "id": "T1",
        "who": "许七安（打更人铜锣，奉旨查福妃案；本区间前段在皇宫御药房偏厅翻账册）",
        "label": "从御药房的册子里查出记录缺失是谁造成的",
        "objective": {
            "text": "他要把「册子有问题」这件事落到可核对的范围上：先当面点出元景三十二年二月十日、二月二十日的收支记录空缺，再把取证范围限定为「五天之内御药房的进出记录」。",
            "basis": "explicit",
            "quotes": Q("ask_gap", "demand_5days"),
            "note": "判 explicit：两句都是他当面对老太监说的话，且都指向同一件事（查册子）。**边界**：这两句只证明他要什么，不证明他要到了什么 —— 索取与拿到是两回事（见 result 与 U1）。",
        },
        "obstacle": {
            "text": "管事老太监对两处缺失都答「记不清」「忘了」，而许七安用望气术两次判定他确实没说谎，所以继续问口供这条路没有信息增益。",
            "basis": "explicit",
            "quotes": Q("old_eunuch_forget", "old_eunuch_forget2", "no_lie_2"),
            "note": "判 explicit：三句都在原文里直述（两句老太监的台词、一句许七安的判断句）。**边界**：老太监的话只到「记不清/忘了」；「他是不是真的不知道」原文没写，我也没替他补 —— 「没说谎」是许七安对气数的读数，不是叙述层对事实的确认（见 U14）。",
        },
        "action": {
            "text": "他先把整年的收支记录逐页看完（用了一个小时），再借去茅厕的由头取出地书碎片与儒家版魔法书，给自己刷上望气术，然后回偏厅不动声色地逐句问话。",
            "basis": "explicit",
            "quotes": Q("read_books", "earth_book", "confront"),
            "note": "判 explicit：翻册子、取书施术、当面点出问题都是叙述层直述。**边界**：action 只写他做了什么；望气术与判谎之间的因果另立 E3，本条不重复承担；「解释」这个要求本身也是他施压的方式，但结果栏不记老太监是否真给了解释（他给的是「记不清」）。",
        },
        "result": {
            "text": "他实际拿到的是一条他自己给出的物证判断：老太监找册子时封面有明显积灰，上面几个指印是新的，他据此断定「不超过五天」——这也是他把取证窗口定成五天的由来。",
            "basis": "explicit",
            "quotes": Q("fingerprint"),
            "note": "判 explicit：这段是许七安对临安说的原话，引文逐字。**边界（重要）**：积灰与指印**只有他这一句话**在支撑，叙述层没有独立描写过封面；所以 result 记的是「他向临安给出这条判断」，不是「册子封面确实有新指印」这一叙述事实。完整链条见 E4。",
        },
        "cost": {
            "text": "他付出的是一页消耗品：撕下儒家版魔法书里的一页望气术并燃尽。",
            "basis": "inferred",
            "quotes": Q("tear_page"),
            "note": "判 inferred：撕下／燃尽的动作是原文直述（explicit），但「这是一项代价」是我的归纳 —— 原文没有写这页纸珍贵、稀有或不可再生。我拒绝把「用了一个小时」的耗时或「去茅厕」的麻烦充作代价。",
        },
    },
    {
        "id": "T2",
        "who": "许七安（委托方）；小宦官（元景帝派来监督他的眼线，受托方）",
        "label": "派小宦官查宫女「荷儿」是谁的人",
        "objective": {
            "text": "他要查清宫女「荷儿」的底细；被派去的正是元景帝派来监督他的那个小宦官。",
            "basis": "explicit",
            "quotes": Q("ask_her", "nar_ask"),
            "note": "判 explicit：吩咐句是台词，另一句是叙述层直述被吩咐者的身份。**边界**：他要的是「查一查」，没有说明要查到什么程度；荷儿与案子的关联在委托时并未写出。",
        },
        "obstacle": {
            "text": "小宦官带回消息时脸色很难看、欲言又止；因为临安在场，他迟迟不敢开口。",
            "basis": "explicit",
            "quotes": Q("eunuch_hesitate", "eunuch_glance"),
            "note": "判 explicit：两句都是叙述层对他神态与动作的直述。**边界**：原文没写他在怕什么 —— 是怕公主、还是怕这条消息本身，我按「不敢当着临安说」这一层写，不替他补动机。",
        },
        "action": {
            "text": "许七安先把管御药房的老太监打发走，再在临安发怒之后直接命小宦官「说吧」。",
            "basis": "explicit",
            "quotes": Q("send_old_away", "xu_says_say"),
            "note": "判 explicit：支开老太监是叙述层直述，命他说是台词。**边界**：镜头的清场动作不等于他已经知道消息的分量（第 32 段的死寂出现在回报之后）。",
        },
        "result": {
            "text": "他拿到的是小宦官的一句回报「荷儿是皇后娘娘殿里的人」，随后偏厅陷入死寂。",
            "basis": "explicit",
            "quotes": Q("eunuch_report", "dead_silence"),
            "note": "判 explicit：回报与场面反应都在原文。**边界（重要）**：荷儿的归属**只有这个小宦官的一句话**，叙述层没有独立确认；结果栏因此记「他拿到这句回报」，而不是「荷儿确系皇后殿里的人」这一叙述事实（见 U4）。",
        },
        "cost": None,
        "costNote": "本区间未出现许七安为这条查询付出的代价：他没有为此失去任何东西、没有被罚、也没有交出任何资源；被派去的人本身就是元景帝派来监督他的（P003/P021），不是他付出的对价。我把「欠小宦官一个人情」这类读法排除 —— 原文只写小宦官自己感动（P055），而许七安的真实动机是「我和临安的互动也喜欢你能省略」（P054）。",
    },
    {
        "id": "T3",
        "who": "临安（二公主，太子胞妹）；许七安（拦她的人）",
        "label": "临安要立刻去找父皇告发皇后",
        "objective": {
            "text": "她要立刻去见父皇，把杀福妃、害太子的罪名加到皇后身上 —— 依据是她自己串起来的动机链（荷儿是皇后的人、黄小柔受过皇后大恩）。",
            "basis": "explicit",
            "quotes": Q("linan_go", "linan_reason"),
            "note": "判 explicit：「我去找父皇」是台词；动机链也是她自己的话。**边界**：这条链是**她的推理**，不是叙述层的定罪 —— 她说的三件事里，「荷儿是皇后的人」来自小宦官，「黄小柔受过皇后大恩」来自许七安的推断（P033），本区间没有任何一处叙述层确认皇后有罪（见 U5）。",
        },
        "obstacle": {
            "text": "许七安拽住她的手，先给时间上的判断「现在下定论为时过早」，再抛出反证「倘若事后发现皇后是冤枉的呢」。",
            "basis": "explicit",
            "quotes": Q("xu_grab", "xu_warn1", "xu_warn2"),
            "note": "判 explicit：拦的动作是叙述层直述，反证是台词。**边界**：他的话只到「可能冤枉」这一步，没有提供任何证据证明皇后无罪；我也不把它读成「他知道真相」。",
        },
        "action": {
            "text": "临安咬牙切齿地丢下一句、豁然起身朝外走；被拽住后仍坚持立场（我不管我不管，太子是我胞兄），直到许七安瞪她一眼、加重语气。",
            "basis": "explicit",
            "quotes": Q("linan_rise", "linan_stubborn", "xu_glare"),
            "note": "判 explicit：起身、顶嘴、被瞪三处都是原文直述。**边界**：action 记的是双方的动作往来，不含结果（结果栏只到「她收敛」）。",
        },
        "result": {
            "text": "她没有去成：先是「哼」一声收敛了性子，反问「那你说怎么办」；叙述层还补了一句对比 —— 刁蛮任性的二公主在一个小铜锣面前居然这么乖巧。",
            "basis": "explicit",
            "quotes": Q("linan_yield", "narr_docile"),
            "note": "判 explicit：收敛与反问是原文直述。**边界**：结束≠成功 —— 这条任务的目标（去找父皇）**没有达成**，达成的是「被拦下来」；我没有把「她没闹成」写成她的胜利，也没有写她从此被说服（第 52 段她仍「显然对这个结果并不满意」）。",
        },
        "cost": None,
        "costNote": "本区间未出现她为这次被拦付出的东西：没有失宠、没有被罚、没有交换条件，也没有任何东西被拿走；P052 的「不忿/并不满意」是情绪，不是代价，我拒绝把它充作 cost。她把告发冲动换了个出口（对母妃说出案情，见 F5/T6），但那是**另一件事的动作**，不是这次被拦的支出。",
    },
    {
        "id": "T4",
        "who": "洛玉衡（人宗道首、国师，二品）；许七安（被借血的人）；金莲道长（中间人，橘猫形态）",
        "label": "洛玉衡向许七安借一碗精血做药引",
        "objective": {
            "text": "她要借他「一碗精血」做药引，用来炼制丹药、缓解身体顽疾，并特意补一句这是金莲道长的建议。",
            "basis": "explicit",
            "quotes": Q("luo_asks_blood", "luo_jinlian_advice"),
            "note": "判 explicit：两句都是她本人的台词。**边界**：顽疾是什么、精血怎么用，她本人一个字都没解释；「借」这个动词是原文用词，我没有改写成「取」（实际交付见 result）。",
        },
        "obstacle": {
            "text": "许七安不表态，心里在措辞怎么拒绝；他对血液的用途有具体戒心（想到巫神教的咒杀术），并要求先核实。",
            "basis": "explicit",
            "quotes": Q("xu_silent", "zhu_sha", "xu_confirm"),
            "note": "判 explicit：三处都是叙述层对他心理与言语的直述。**边界**：他的戒心来源是叙述层给的类比与记忆，不是他当面说的；我只写到「他在措辞拒绝」，没有写他当场拒绝（他最后答应了）。",
        },
        "action": {
            "text": "他当着她的面取出地书碎片准备传书核实，随即想起自己现在是死人、不能开口；随后金莲道长（橘猫）到场，把缘由讲清 —— 借的是血里脱胎丸的药性，而洛道首每月受业火烧灼，脱胎丸可暂时缓解。",
            "basis": "explicit",
            "quotes": Q("xu_takes_earth", "jinlian_explains1", "jinlian_explains2"),
            "note": "判 explicit：取碎片、想起身份、中间人解释三处都是原文直述（最后一句是金莲道长的台词）。**边界**：中间人的解释是**人物说法**，本区间没有任何叙述层或第三方验证它（见 U12）；我按「他把这套说法当作可接受的理由」写 action。",
        },
        "result": {
            "text": "他口头答应「尽绵薄之力」；洛玉衡取出一口玉碗推到面前，得到鲜血后趁热跑去炼丹。",
            "basis": "explicit",
            "quotes": Q("xu_agrees_blood", "jade_bowl", "blood_taken"),
            "note": "判 explicit：答应的话、玉碗、取血炼丹都是原文直述。**边界**：结果只到「血被取走、她离开去炼丹」；丹药是否炼成、有没有效，本区间没有（见 U13）。",
        },
        "cost": {
            "text": "他付出的是「一碗精血」；量的口径由叙述层给出 —— 玉碗不大，约茶杯的三倍。",
            "basis": "inferred",
            "quotes": Q("bowl_small"),
            "note": "判 inferred：碗的尺寸是原文直述（explicit），但「这是代价」由我按交易结构归纳。**边界**：原文没有写失血对他的影响（虚弱/损耗都没有写），我也没有替他补；「碗不大」紧接着的是他自己「心里安定了些」，那是他的观感，不是损耗数据。",
        },
    },
    {
        "id": "T5",
        "who": "许七安（挑剑术的人）；洛玉衡（要给补偿的人）；金莲道长（替他拿主意的中间人）",
        "label": "在《心剑》《气剑》《御剑》里选一篇",
        "objective": {
            "text": "他要的是能补上自身短板的东西 —— 他自己盘过一遍：控制有了、物理伤害有了，最缺的是元神领域的输出；洛玉衡那边则摆出三篇剑术让他挑。",
            "basis": "explicit",
            "quotes": Q("yuanshen_output", "luo_lists"),
            "note": "判 explicit：短板自述是他的内心话，三篇剑术的名目是洛玉衡的台词。**边界**：两句分属两侧（他要什么 / 她给什么），我把它们并列为同一栏的依据；「元神输出」是他自己的判断，本区间没有第三方测评（另见 U6 与 T5 result 的能力结论）。",
        },
        "obstacle": {
            "text": "挡在中间的是两件事：他用的是刀而不是剑，所以面对的是「剑术」这一整类；而摆出来的三篇里，另外两篇的说明分别是「一等一的攻杀之道」与当场演示的御剑术（他看完称之为仙人手段）。",
            "basis": "explicit",
            "quotes": Q("xu_uses_saber", "qijian_props"),
            "note": "判 explicit：两句都是台词/场面直述。**边界**：原文只给这三篇的属性，**没有**给出任何「哪一篇对他更有用」的比较结论 —— 「都不是他缺的那一块」是我的归纳，因此我把它从 obstacle 正文里拿掉，只保留属性本身；他的适配判断另记在 action 与 E7，而「剑术能不能用刀使」这一层的解法由金莲道长给出（P178）。",
        },
        "action": {
            "text": "他先向橘猫征求意见（自己没想好要什么），看完洛玉衡当场演示御剑术之后，仍然开口选《心剑》。",
            "basis": "explicit",
            "quotes": Q("xu_no_idea", "cat_suggests_sword", "yujian_demo", "xu_picks_xinjian"),
            "note": "判 explicit：四处都是原文直述（含演示的场面、猫的建议与他的选择台词）。**边界**：顺序上他是先问猫（P175）、猫建议赠剑术（P176）、再看演示（P191）、再选（P193）；选的理由不在 action，而在 why_xinjian。",
        },
        "result": {
            "text": "他实际拿到的是《心剑》剑谱，外加洛玉衡一句口头承诺：有不解之处可去灵宝观寻她，她可以为他解惑三次。",
            "basis": "explicit",
            "quotes": Q("luo_gives_book", "xu_thanks"),
            "note": "判 explicit：给书与承诺都在原文。**边界**：结果里没有任何「他已练成」或「心剑有效」的字样 —— 他拿到的是一本册子与一句承诺；「三次解惑」在本区间一次都没被用掉（见 F4，unresolved）。",
        },
        "cost": None,
        "costNote": "本区间**没有出现「挑一篇剑术」这一步本身的代价**：三篇摆出来让他挑，挑完他就拿到了。这笔交易真正的支出是那碗精血，我已登记在 T4 的 cost 上，不在这里重复计一次（同一笔支出记两条任务是虚增）。特别说明我**拒绝**的一种写法：洛玉衡说的是「你有什么想要的丹药，可以尽管开口，当做是精血的补偿」（P133）—— 那句话给的补偿名目是**丹药**；剑术是她另一次开口时由金莲道长点名要来的（P173/P176），把剑术直接说成「精血的补偿」是替原文接线，我因此不写。",
    },
    {
        "id": "T6",
        "who": "临安（泄密的人）；陈贵妃（她的母亲，听的人）",
        "label": "临安把保密中的案情告诉母妃",
        "objective": {
            "text": "她要让母亲别再哭：开口就是「太子哥哥会没事的，清者自清」，叙述层给的动机是看着母亲郁郁寡欢、日日垂泪而心里不好过。",
            "basis": "explicit",
            "quotes": Q("linan_comfort", "as_daughter"),
            "note": "判 explicit：安慰是台词，动机是叙述层直述。**边界**：她要的是「让母亲安心」，不是「把案情说出去」—— 泄密是她在压力下走出来的手段（见 action），我不用后见之明把目标写成泄密。",
        },
        "obstacle": {
            "text": "挡在前面的是保密要求本身（许七安几次三番对两位公主强调过），以及大宫女那句「这么多天了，一直没进展」所代表的压力。",
            "basis": "explicit",
            "quotes": Q("case_is_secret", "dagongnv_sigh"),
            "note": "判 explicit：保密要求是叙述层直述，没进展是大宫女的台词。**边界**：大宫女那句是**她的叹息**，不是叙述层对办案进度的判定；我把它当压力源，不当事实结论。",
        },
        "action": {
            "text": "她先大声说「谁说没进展的，许七安已经把案子查的差不多了」，再直接给出结论「是皇后陷害的太子，一定就是她」，最后把案情经过原原本本告之陈贵妃。",
            "basis": "explicit",
            "quotes": Q("linan_blurts", "linan_accuses", "tells_everything"),
            "note": "判 explicit：三句都是原文直述（两句台词、一句叙述）。**边界**：她没有告诉母妃「这是秘密」；泄密的动作就是这三步，我没有替她补动机（如「她以为母亲需要知道」）。",
        },
        "result": {
            "text": "她听到的是母亲大哭之下的旧事：皇后当年不守妇道、被陛下打入冷宫，陛下念旧情没有废她；她追问「那个男人是谁」，母亲自知失言、含泪封口 ——「此事是陛下的禁忌，莫要外传」。",
            "basis": "explicit",
            "quotes": Q("chen_outburst", "chen_seals"),
            "note": "判 explicit：两句都是陈贵妃的台词。**边界（重要）**：这条结果**内容是陈贵妃的说法**，本区间没有任何叙述层证据；「皇后不守妇道」既不是叙述事实，也不是临安查出来的，我把这一点同时写进 U5/U6。",
        },
        "cost": None,
        "costNote": "本区间未写出她为泄密付出的代价：没有受罚、没有失去什么、也没有向许七安交代；P162「像是一道惊雷」是**她受到的冲击**，属于后果而非支出。特别说明：她违背保密要求这件事本身是 action 栏的内容（P151/P152/P159），若把它再抄一遍当 cost，就是同一批句子兼两栏 —— 正是提示词禁止的形态。若复核认为「违背承诺」本身即代价，这条应改为 basis=derived 并另取 P151 作引，我在此显式留出这个改法而不是自己先填上。",
    },
]

CAUSE_EDGES = [
    {
        "id": "E1",
        "frm": "小宦官回报「荷儿是皇后娘娘殿里的人」",
        "to": "临安丢下「我去找父皇」，豁然起身朝外走",
        "mechanism": "触发是**情报把嫌疑人指到皇后头上**：临安自己把三段串起来（荷儿是皇后的人 → 黄小柔受过皇后大恩 → 皇后有动机），加上太子是她胞兄，于是从「听消息」直接跳到「去见父皇」。方向是〔情报〕→〔告发行动〕，机制由她本人的话给出。",
        "basis": "explicit",
        "notMereAdjacency": True,
        "quotes": Q("eunuch_report", "xu_infer_huaiqing", "xu_infer_grace", "xu_infer_role", "linan_reason", "linan_rise"),
        "note": "**边界**：她的三段推理是**她自己的说法**，原文没有一处叙述层确认皇后有罪；这条边只主张〔这句情报触发了她的行动〕，不主张〔皇后真有罪〕。",
    },
    {
        "id": "E2",
        "frm": "许七安拽住她的手，说「现在下定论为时过早」并抛出「倘若事后发现皇后是冤枉的呢」",
        "to": "临安收敛了性子，反问「那你说怎么办」",
        "mechanism": "触发是**反证**：他没有否认真相、只提出「事后发现是冤枉」的可能，把一个已经在她心里定案的结论重新变成未决；紧接着的叙述层对比（「刁蛮任性的二公主……居然这么乖巧」）说明这次收手在她身上是反常的，所以归因不是「她本来就听话」。",
        "basis": "inferred",
        "notMereAdjacency": True,
        "quotes": Q("xu_grab", "xu_warn2", "linan_yield", "narr_docile"),
        "note": "判 inferred：两句拦阻与她的收敛都在原文，但**叙述层没有写「因为她被说服」**；原文另给了一种可能的解释（P050 的对比句是旁人视角的评价，不是因果陈述）。我按「反证 + 她对他的信任」给出机制，并把替代解释写在这里供复核推翻。",
    },
    {
        "id": "E3",
        "frm": "他撕下一页望气术燃尽、眼里射出两道清光之后回偏厅问话",
        "to": "他两次判定老太监「没说谎」",
        "mechanism": "触发是**术法的作用域**：望气术让他能读气数，所以他的问话不再是「听口供」而是「看口供真假」；原文把顺序写得很清楚（先施术、再返回偏厅、再逐句问），并且两次把判断句紧接在对方回答之后。",
        "basis": "explicit",
        "notMereAdjacency": True,
        "quotes": Q("earth_book", "tear_page", "eye_light", "no_lie_1", "no_lie_2"),
        "note": "**边界**：望气术能验谎这件事本身，原文只通过许七安的判断句体现，没有旁白解释原理；他自己的括注（「一个老太监不至于有屏蔽气数的法器」）反而说明他认为存在能屏蔽的存在（见 U14）。",
    },
    {
        "id": "E4",
        "frm": "封面上的指印是新的、他断定不超过五天",
        "to": "他把取证范围定成「五天之内御药房的进出记录」，并要求拿名单去找守卫核对",
        "mechanism": "触发是**物证把时间窗压到五天**：既然动过册子的人只在近五日留下指印，需要核对的就是近五日出入御药房的人；他先索取记录（P019），随后把核对方式落到守卫这一侧（P057），两处都写「五天」。",
        "basis": "inferred",
        "notMereAdjacency": True,
        "quotes": Q("fingerprint", "demand_5days", "xu_order_list"),
        "note": "判 inferred，且**必须披露一处顺序倒置**：索取五日记录（P019）在文本上出现在指印解释（P023）**之前**。所以这条边不是按叙述顺序推的，而是由他本人在 P023 补出的理由链支撑 —— 也就是说，它更像是「他当时已有这个判断，事后才对临安说明」，若复核认为顺序倒置足以否掉这条边，删掉即可，不影响 T1 的其它栏。",
    },
    {
        "id": "E5",
        "frm": "陈贵妃失言说出「当年她不守妇道，陛下岂会将她打入冷宫」",
        "to": "临安把以往没注意的细节通通重新解释（皇后深居简出、从不笑、对怀庆和四皇子冷淡）",
        "mechanism": "机制由叙述层直接给出：「当接受了这个惊天大消息后，很多以往没注意的细节，通通有了解释」—— 触发是新信息，作用方式是**旧细节被重新赋义**，随后举三例。方向是〔新消息〕→〔旧细节重新解释〕，不是「细节证明消息」。",
        "basis": "explicit",
        "notMereAdjacency": True,
        "quotes": Q("chen_outburst", "details_explained", "details_examples"),
        "note": "**边界**：被重新解释的三条细节原文都只是「有了解释」，没有一条能反过来证明皇后有罪；叙述层紧接着写的仍是临安「打心底里不相信她是个不守妇道的女人」（P166），两种读法同时存在。",
    },
    {
        "id": "E6",
        "frm": "金莲道长到场并解释「借你血液里脱胎丸的药性」与人宗业火之苦",
        "to": "许七安答应「愿意尽绵薄之力」",
        "mechanism": "触发是**中间人担保 + 用途说明**：他先前的迟疑来自「血能做什么」这一未知（巫神教咒杀术的记忆），金莲道长把用途限定到脱胎丸药性上；他自己的成交句也点明理由是「既然金莲道长做中间人」。",
        "basis": "explicit",
        "notMereAdjacency": True,
        "quotes": Q("jinlian_explains1", "jinlian_explains2", "xu_agrees_blood", "xu_blood_hesitate"),
        "note": "**边界**：金莲道长给的解释是**人物说法**，本区间没有被验证；另需注意他对洛玉衡「先看了一眼」才继续说（P122），说明这套说法是当着她的面讲的。",
    },
    {
        "id": "E7",
        "frm": "洛玉衡说明「心剑……无法斩肉身，专斩元神」",
        "to": "许七安下意识看向橘猫 → 橘猫弹出利爪警告 → 他立刻收回目光",
        "mechanism": "触发是**属性与听众的错配**：这条剑术的属性针对元神，而橘猫正是一个非肉身的听众；许七安的目光把这条属性指向了它，橘猫自己把这读成挑衅（「许大人莫要挑衅啊」），于是弹出利爪，他随即收回。方向是〔属性说明〕→〔目光〕→〔警告〕→〔收回〕，三步都有原文动作。",
        "basis": "explicit",
        "notMereAdjacency": True,
        "quotes": Q("xinjian_props", "xu_looks_cat", "cat_claws", "xu_retracts"),
        "note": "**边界**：橘猫为什么对「专斩元神」敏感，原文没有解释（金莲道长的形态与元神的关系不在本区间交代）；我只写到它自己的措辞与动作。",
    },
    {
        "id": "E8",
        "frm": "洛玉衡望向门口，说「他在这里」",
        "to": "许七安扭头看见橘猫蹲在门槛上",
        "mechanism": "触发是**提示**：她先察觉到来者（望向门口这个动作在说话之前），出言点破，他才知道要往门口看。方向是〔她的察觉与提示〕→〔他的发现〕。",
        "basis": "inferred",
        "notMereAdjacency": True,
        "quotes": Q("luo_he_is_here", "cat_on_threshold"),
        "note": "判 inferred：提示与看见都是直述，但**她怎么知道门外有猫，原文一个字都没写**（二品强者的感知？未说明），所以「她先察觉」这一层是我按动作顺序的归纳，见 U18。",
    },
    {
        "id": "E9",
        "frm": "金莲道长以「呵呵」回应私聊请求，并给出理由（李妙真开春后来京、不必急于一时）",
        "to": "许七安说「也对！」并作罢",
        "mechanism": "触发是**表面理由成立 + 隐含动机未说**：他给的理由是时间上不必急（李妙真不久就来），许七安接受了；同一段的叙述层却给出他没说出口的动机 —— 他等着李妙真知道许七安复活后愤怒地找他拼命，以此搅乱局面、缓解天人两宗杰出弟子的矛盾。方向是〔拒绝 + 理由〕→〔放弃〕，而真实的推动者是叙述层披露的那条私心。",
        "basis": "explicit",
        "notMereAdjacency": True,
        "quotes": Q("jinlian_hehe", "jinlian_reason", "jinlian_secret", "xu_okay"),
        "note": "**边界**：这段是本区间最干净的一处「读者知道、当事人不知道」—— 许七安只听到理由，原文没写他是否察觉私心（见 U11）。这条边因此有两个层次：他以为的机制（不急）与叙述层给出的机制（私心），我都写进 mechanism 而不合并成一个。",
    },
    {
        "id": "E10",
        "frm": "临安大声说出「许七安已经把案子查的差不多了」",
        "to": "陈贵妃眼睛一亮、直勾勾追问，并用力握紧女儿的手",
        "mechanism": "触发是**她关心的事出现了进展**：陈贵妃此前正在偷偷抹眼泪、连着两天没怎么吃饭（P139/P145），这句话把她从「等消息」推到「追问细节」，激动到把女儿捏疼。方向是〔女儿报进展〕→〔母亲追问并抓紧〕。",
        "basis": "explicit",
        "notMereAdjacency": True,
        "quotes": Q("linan_blurts", "chen_eyes_light", "chen_grips"),
        "note": "**边界**：陈贵妃此前哭泣、不吃饭由贴身宫女转述（P144/P145），我把它作为前情使用而非独立边；「握紧手」的直接后果由女儿一句「母妃你捏疼我了」确认（P155）。",
    },
    {
        "id": "E11",
        "frm": "临安说「是皇后陷害的太子，一定就是她」并把案情经过原原本本告之",
        "to": "陈贵妃脸色大变制止，随后大哭说出皇后当年的旧事",
        "mechanism": "触发是**指控对象被点名**：先说结论时她立刻制止（「不得胡言」），等听完完整经过后情绪转向，从制止变成大哭并说出自己知道的旧事；方向的转折点就在「把经过讲完」这一步。",
        "basis": "explicit",
        "notMereAdjacency": True,
        "quotes": Q("linan_accuses", "chen_shocked", "tells_everything", "chen_outburst"),
        "note": "**边界**：她的「果真是她」是**她自己的判断**，不是叙述层定论；「脸色大变」在前、「大哭」在后，两个反应方向不同（一个压、一个放），所以我把它们都写在 to 里而不是压成一个「情绪变化」。",
    },
]

NOT_CAUSE_EDGES = [
    {
        "id": "R1",
        "pair": "洛玉衡说「他在这里」/ 橘猫到场（P110–P111）→ 许七安答应借血（P132）",
        "why": "两件事在同一场戏里相邻，但借血成交的机制是 P122–P123 的用途说明与 P132 他本人给出的理由（「既然金莲道长做中间人」）；猫到场只是让解释者出现。把「猫来了 → 他答应了」连边，会漏掉真正的触发条件，也会把洛玉衡先前的开口（P102）当成无效动作。",
        "quotes": Q("luo_he_is_here", "jinlian_explains1", "xu_agrees_blood"),
    },
    {
        "id": "R2",
        "pair": "临安被许七安拦下（P040/P049）→ 她到景秀宫见母妃（P138）",
        "why": "顺序上确实先拦人（P040–P049）、后到景秀宫（P138），但**触发不成立**：她去母妃那里是同一场戏里自己说出的安排「临安说自己要去母妃那里用膳」（P059），原文给的理由是用膳，不是被拦之后的举动；而且两者之间隔着整段灵宝观戏（P061–P136），原文没有一个字把它们连起来。这条边若成立，就等于把「她憋着的气」替原文补成她去看母亲的原因 —— 这正是把相邻当因果。",
        "quotes": Q("leave_pharmacy", "linan_yield", "linan_arrives"),
    },
    {
        "id": "R3",
        "pair": "许七安选定《心剑》（P193/P200）→ 洛玉衡取玉碗取血（P202/P204）",
        "why": "两笔条款在同一场谈判里相邻，但取血是 P102 就提出的既定交换，选剑走的是另一条理由链（他对自身短板的判断，P196–P199）。把后者当作前者的结果，是把同一场戏的相邻当因果。",
        "quotes": Q("xu_picks_xinjian", "luo_asks_blood", "therefore"),
    },
    {
        "id": "R4",
        "pair": "小宦官是元景帝的眼线（P021）→ 他查出荷儿是皇后殿里的人（P031）",
        "why": "眼线身份说明他会上报，但不解释他凭什么能查到荷儿的归属；原文没有写他的渠道（是问人、翻档、还是听来的），所以这条相邻不构成可写的机制 —— 能力与动机都不等于方法。",
        "quotes": Q("eunuch_spy", "eunuch_report"),
    },
    {
        "id": "R5",
        "pair": "陈贵妃说出「皇后不守妇道」（P160）→ 临安此后去查「那个男人是谁」",
        "why": "临安确实追问了（P169），但原文**没有**写她随后去查，也没有写这条线索在区间内有任何后续；把追问当成一条因果链的开端，等于替原文安排了一个它没有写的行动。",
        "quotes": Q("chen_outburst", "linan_asks_who"),
    },
    {
        "id": "R6",
        "pair": "作者 PS（P214）→ 正文任何事件",
        "why": "PS 是作者留言（码字进度与捉虫请求），不是叙事内容，不与正文连边。",
        "quotes": Q("ps"),
    },
]

STATES = [
    {
        "id": "S1",
        "who": "临安",
        "aspect": "对许七安的服从度：刁蛮脾气在他面前收不收得住",
        "before": {
            "text": "她在同一场戏里对小宦官发过火 —— 一句「本宫也不能听？」眉毛就飞扬起来，叙述层把这种脾气写成她的常态。",
            "basis": "explicit",
            "quotes": Q("linan_angry"),
        },
        "after": {
            "text": "被许七安拦下后她只剩一声「哼」，反问「那你说怎么办」；叙述层专门指出，熟悉她性格的人要是在场会大吃一惊。",
            "basis": "explicit",
            "quotes": Q("linan_yield", "narr_docile"),
        },
        "anchor": {
            "text": "事件锚点：许七安拽住她的手、说「现在下定论为时过早」，再抛出「倘若事后发现皇后是冤枉的呢」；她顶了一句「我不管我不管」，被他瞪了一眼加重语气。",
            "basis": "explicit",
            "quotes": Q("xu_grab", "xu_warn2", "xu_glare"),
        },
        "note": "**边界**：after 只写这一次收手，不写「她的脾气从此改了」—— 第 52 段她仍「又哼了一声，显然对这个结果并不满意」。",
    },
    {
        "id": "S2",
        "who": "许七安",
        "aspect": "对「借精血」这件事的态度",
        "before": {
            "text": "他没有当场表态，心里在措辞怎么拒绝；面对洛玉衡时仍然迟疑，理由是信任金莲道长却仍不放心血的用途。",
            "basis": "explicit",
            "quotes": Q("xu_silent", "xu_blood_hesitate"),
        },
        "after": {
            "text": "他松口答应「既然金莲道长做中间人，在下自然愿意尽绵薄之力的」。",
            "basis": "explicit",
            "quotes": Q("xu_agrees_blood"),
        },
        "anchor": {
            "text": "事件锚点：他先取出地书碎片要核实（发现自己不能开口），随后金莲道长到场解释「借你血液里脱胎丸的药性」与人宗业火之苦。",
            "basis": "explicit",
            "quotes": Q("xu_takes_earth", "jinlian_explains1", "jinlian_explains2"),
        },
        "note": "**边界**：after 是口头答应，不是「他放心了」—— 原文没有写他的戒心消失。",
    },
    {
        "id": "S3",
        "who": "临安",
        "aspect": "对皇后的认知（从「温和但缺笑」到「被指控不守妇道」的被解释状态）",
        "before": {
            "text": "她心里那位皇后性子温和、缺乏笑容；即便正在为构陷太子而愤恨，她也打心底里不相信对方是不守妇道的女人。",
            "basis": "explicit",
            "quotes": Q("linan_disbelief"),
        },
        "after": {
            "text": "听到母亲那句话之后，她把以往没注意的细节通通重新解释了一遍（深居简出、从不笑、对怀庆和四皇子冷淡）。",
            "basis": "explicit",
            "quotes": Q("details_explained", "details_examples"),
        },
        "anchor": {
            "text": "事件锚点：陈贵妃大哭之下的那句「当年，要不是她不守妇道，陛下岂会将她打入冷宫」。",
            "basis": "explicit",
            "quotes": Q("chen_outburst"),
        },
        "note": "**边界**：after 是「她开始用另一种解释看旧细节」，**不是**「她相信皇后有罪」—— 同段还写她打心底不信；两条并存，我不合并（见 unknowns）。",
    },
    {
        "id": "S4",
        "who": "陈贵妃",
        "aspect": "情绪：从独处垂泪到听到案情有进展",
        "before": {
            "text": "她在屋里偷偷抹眼泪，见女儿跑进来连忙别过脸擦拭泪痕；贴身宫女补充：听了另立太子的话后大哭一场，连着两天都没怎么吃饭。",
            "basis": "explicit",
            "quotes": Q("chen_crying", "maid_report2"),
        },
        "after": {
            "text": "听到「许七安已经把案子查的差不多了」，她眼睛一亮、直勾勾追问，激动到把女儿的手握疼。",
            "basis": "explicit",
            "quotes": Q("chen_eyes_light", "chen_grips"),
        },
        "anchor": {
            "text": "事件锚点：临安忍不住大声说出案情有进展（「谁说没进展的……」）。",
            "basis": "explicit",
            "quotes": Q("linan_blurts"),
        },
        "note": "**边界**：这是本区间她情绪曲线的**上行一段**；紧接着她还会脸色大变、大哭（S5），两条分开写，不压成一条「情绪波动」。",
    },
    {
        "id": "S5",
        "who": "陈贵妃",
        "aspect": "情绪：从追问进展到制止、再到自己说出旧事",
        "before": {
            "text": "她正在追问「那个许七安真的快查出来了？」，情绪是激动。",
            "basis": "explicit",
            "quotes": Q("chen_eyes_light"),
        },
        "after": {
            "text": "先脸色大变制止女儿（「临安，不得胡言」），听完完整经过后大哭起来，说出皇后当年被指不守妇道、被打入冷宫、陛下念旧情没有废她。",
            "basis": "explicit",
            "quotes": Q("chen_shocked", "chen_outburst"),
        },
        "anchor": {
            "text": "事件锚点：临安说「是皇后陷害的太子」并把案情经过原原本本告之。",
            "basis": "explicit",
            "quotes": Q("linan_accuses", "tells_everything"),
        },
        "note": "**边界**：before 与 S4 的 after 引同一句（跨分区复用，允许）；本条的 after 只写「她说了什么」，不写「她说的是真的」（见 U5/U6）。",
    },
    {
        "id": "S6",
        "who": "许七安",
        "aspect": "福妃案的取证状态：从「册子有缺页但问不出来」到「有了时间窗与取证安排」",
        "before": {
            "text": "他手上只有一本记录有缺页的册子：二月十日与二月二十日的收支记录空缺，而管事老太监两次以「记不清/忘了」回应。",
            "basis": "explicit",
            "quotes": Q("ask_gap", "old_eunuch_forget2"),
        },
        "after": {
            "text": "他把指印的新鲜度换成一个可执行的时间窗（五天），据此索取五日出入记录，并把核对交给小宦官去偷偷找守卫办。",
            "basis": "explicit",
            "quotes": Q("fingerprint", "xu_order_list"),
        },
        "anchor": {
            "text": "事件锚点：他向临安说明封面指印不超过五天，随后吩咐小宦官去要名单并核对。",
            "basis": "explicit",
            "quotes": Q("fingerprint"),
        },
        "note": "**边界**：after 是「安排下去了」，**不是**「名单到手」或「案子有突破」—— 名单与核对结果本区间都没有出现（见 F3，unresolved）。",
    },
    {
        "id": "S7",
        "who": "小宦官（元景帝派来监督许七安的眼线）",
        "aspect": "对许七安的态度：从不敢说到感动应承",
        "before": {
            "text": "他回来报信时脸色很不好看、欲言又止，还小心翼翼地看临安一眼，迟迟不开口。",
            "basis": "explicit",
            "quotes": Q("eunuch_hesitate", "eunuch_glance"),
        },
        "after": {
            "text": "听完许七安那句「只说案子，不说其他」之后，他想起干爹的警告，心里无比感动（觉得许大人还知道为他这种小人物担忧），大声应下「奴才只说案子，不会多嘴」。",
            "basis": "explicit",
            "quotes": Q("eunuch_moved", "xu_shangdao", "eunuch_promise"),
        },
        "anchor": {
            "text": "事件锚点：许七安当着他的面交代如何向陛下汇报 ——「一五一十的告诉陛下……切记要说的简单，只说案子，不说其他」。",
            "basis": "explicit",
            "quotes": Q("xu_order_report"),
        },
        "note": "**边界**：after 里的「感动」是**他的心理**（叙述层直述），不是许七安的善意被验证；叙述层同时写许七安的真实动机是「我和临安的互动也喜欢你能省略」（P054）。",
    },
    {
        "id": "S8",
        "who": "洛玉衡与许七安之间的人情状态",
        "aspect": "从「她开口借精血、未获答复」到「血已取、剑谱已付」",
        "before": {
            "text": "她提出借一碗精血做药引，并补一句这是金莲道长的建议；对方没有表态。",
            "basis": "explicit",
            "quotes": Q("luo_asks_blood", "luo_jinlian_advice"),
        },
        "after": {
            "text": "她取走鲜血后趁热去炼丹，并把《心剑》剑谱给他，附带三次解惑的承诺；她本人把这定性为「精血的补偿」。",
            "basis": "explicit",
            "quotes": Q("blood_taken", "luo_gives_book", "luo_offer_pill"),
        },
        "anchor": {
            "text": "事件锚点：金莲道长出面把用途讲清、许七安答应「尽绵薄之力」，随后玉碗取血。",
            "basis": "explicit",
            "quotes": Q("jinlian_explains1", "xu_agrees_blood", "jade_bowl"),
        },
        "note": "**边界**：after 只到「交易的两端都已交付」；丹药是否炼成、人情是否就此结清，原文没写（U13）。",
    },
]

KNOWLEDGE_GAPS = [
    {
        "id": "K1",
        "subject": "「荷儿是谁的人」",
        "knows": "小宦官：查到了并在偏厅回报「荷儿是皇后娘娘殿里的人」。",
        "doesNotKnow": "许七安：此前不知道，所以才派他去查；临安此前也不知道，是听完回报才有反应。",
        "basis": "explicit",
        "quotes": Q("ask_her", "eunuch_report", "xu_infer_grace"),
        "note": "**边界**：知道这条信息的是小宦官（且他还要转报给元景帝，P021）；许七安随后据此推断怀庆当初情绪异常的原因（P033），但那是**他的归纳**，不是叙述确认怀庆知情。",
    },
    {
        "id": "K2",
        "subject": "「是谁动过御药房的册子」",
        "knows": "无人知道：老太监两次答「记不清/忘了」，许七安的望气术判定他没说谎。",
        "doesNotKnow": "许七安：他手上只有「指印是新的、不超过五天」这一条判断，撕册子的人是谁本区间没有答案。",
        "basis": "explicit",
        "quotes": Q("old_eunuch_forget", "no_lie_2", "fingerprint"),
        "note": "**边界**：「指印是新的」这句只有许七安对临安说的一次（P023），叙述层没有独立描写过封面；所以本条的知/不知两侧都建立在人物说法上。",
    },
    {
        "id": "K3",
        "subject": "「皇后的旧事：不守妇道、被打入冷宫、没有废后」",
        "knows": "陈贵妃：她说得出这三件事，并称「此事是陛下的禁忌」；按她的说法，陛下也知道。",
        "doesNotKnow": "临安：她此前完全不知道（「这都是什么时候的事，她怎么不知道」），听完后追问「那个男人是谁」，陈贵妃以「别，别问了」拒绝回答。",
        "basis": "explicit",
        "quotes": Q("chen_outburst", "when_was_this", "chen_seals"),
        "note": "**边界**：这三件事**只有陈贵妃一个人的说法**，本区间没有任何叙述层或第三方佐证；我在 knows 里写「她说得出」，不写「事实如此」。",
    },
    {
        "id": "K4",
        "subject": "「许七安复活」这条消息要不要现在告诉李妙真」",
        "knows": "金莲道长：他知道许七安活着，并且知道李妙真开春后来京；叙述层还写明他等着李妙真知道后愤怒地找许七安拼命，以此搅乱局面、缓解天人两宗杰出弟子的矛盾。",
        "doesNotKnow": "李妙真：本区间不在场，不知道许七安复活。许七安：也不知道金莲道长拦他的真实动机 —— 他听到的只是「不必急于一时」，并答「也对！」。",
        "basis": "explicit",
        "quotes": Q("jinlian_reason", "jinlian_secret", "xu_okay"),
        "note": "这是本区间最干净的一处「读者知道、当事人不知道」：私心由叙述层直接给出（P211），而许七安只接收到表面理由。**边界**：他是否察觉，原文没写（U11）。",
    },
    {
        "id": "K5",
        "subject": "「金莲道长现在能进哪里」与他的实力",
        "knows": "金莲道长：他自己说「伤势好了之后，可以随意出入皇城了，不过皇宫依旧进不去」。",
        "doesNotKnow": "许七安：他不知道具体品级，只能按「无声无息潜入皇城少说得四品」估算，并补充武夫体系不在此列。",
        "basis": "explicit",
        "quotes": Q("cat_says_access", "xu_estimates", "wufu_cannot_sneak"),
        "note": "**边界**：「少说得四品」是许七安按自己的知识估的，不是叙述层给的实力标注；「伤势」是什么伤、何时好的，原文没写（U9/U10）。",
    },
    {
        "id": "K6",
        "subject": "「临安把案情告诉了陈贵妃」这件事",
        "knows": "临安与陈贵妃：两人在场；贴身宫女与「大宫女」也在场（她们一直接话）。",
        "doesNotKnow": "许七安：他在灵宝观，不在景秀宫；本区间没有写他知道或事后得知 —— 而案情保密正是他几次三番强调过的。",
        "basis": "derived",
        "quotes": Q("case_is_secret", "tells_everything"),
        "note": "判 derived：保密要求（P151）与泄密动作（P159）都在原文，但「许七安不知情」是靠**场景不重叠 + 区间内无告知**推出的，不是原文直述。",
    },
]

FORESHADOWS = [
    {
        "id": "F1",
        "name": "「荷儿」这个名字：先委托去查，后回报归属",
        "status": "resolved-in-range",
        "setup": {
            "text": "铺设：许七安把「荷儿」交给元景帝派来的小宦官去查，此时只说查一查这个宫女是谁。",
            "basis": "explicit",
            "quotes": Q("ask_her"),
        },
        "payoff": {
            "text": "回收：小宦官回报「荷儿是皇后娘娘殿里的人」—— 这个名字把案子引向皇后，直接触发临安要去找父皇（E1）。",
            "basis": "explicit",
            "quotes": Q("eunuch_report"),
        },
        "note": "铺设与回收都在本区间内，是同一件事的两端。**边界**：回收只到「回报了归属」，遗传学式的确认没有 —— 叙述层从未独立证实荷儿的身份（U4）。",
    },
    {
        "id": "F2",
        "name": "神殊和尚的存在会被顶级强者发现",
        "status": "unresolved",
        "setup": {
            "text": "铺设：他不想和关系不熟的顶级强者走得太近，理由之一是「万一突然给人家发现神殊和尚的存在」；紧接着的内心戏把这个担忧展开成五百年封禁的玩笑。",
            "basis": "explicit",
            "quotes": Q("shenshu_worry", "sangbo_joke", "five_hundred_years"),
        },
        "payoff": {
            "text": None,
            "basis": None,
            "quotes": [],
            "payoffNote": "本区间**没有回收**：他和洛玉衡整场会面中，对方从未提及或察觉神殊和尚；这条担忧在区间内没有兑现，也没有被排除。",
        },
        "note": "铺设端出现两处（担忧 + 展开的玩笑），且都是**他自己的内心话**；「会被发现」不是叙述层的事实判断。因无回收，显式标 unresolved。",
    },
    {
        "id": "F3",
        "name": "五天之内出入御药房的名单 + 偷偷找守卫核对",
        "status": "unresolved",
        "setup": {
            "text": "铺设：许七安安排小宦官去管理御药房的公公处要一份五天内的出入名单，然后偷偷找守卫核对。",
            "basis": "explicit",
            "quotes": Q("xu_order_list"),
        },
        "payoff": {
            "text": None,
            "basis": None,
            "quotes": [],
            "payoffNote": "本区间**没有回收**：名单没到手、核对没有做、也没有写出核对结果；后续场景直接切到灵宝观。",
        },
        "note": "铺设端是一句具体的行动指令（不是泛泛的提及），且带时间窗与核对方式，所以它是被放下的钩子而不是装饰；因无回收显式标 unresolved。",
    },
    {
        "id": "F4",
        "name": "「我可以为你解惑三次」",
        "status": "unresolved",
        "setup": {
            "text": "铺设：洛玉衡交出《心剑》时附了一句承诺 —— 有不解之处可来灵宝观寻她，她可以解惑三次。",
            "basis": "explicit",
            "quotes": Q("luo_gives_book"),
        },
        "payoff": {
            "text": None,
            "basis": None,
            "quotes": [],
            "payoffNote": "本区间**没有回收**：许七安只回了「多谢国师」，三次解惑一次都没用掉，也没有写他日后去问。",
        },
        "note": "**边界**：这是一句「额度」式承诺（次数被明确写死为三次），本区间只出现一次、且明确指向未来，所以按未回收伏笔登记，而不是按单次提及排除。次数在原文里是「三次」，我照抄不改。",
    },
    {
        "id": "F5",
        "name": "被拦下的告发冲动换了个出口：从「去找父皇」到「告诉母妃」",
        "status": "resolved-in-range",
        "setup": {
            "text": "铺设：临安听到荷儿的归属后要立刻去找父皇，被许七安拽住并劝下；她当时只剩一声「哼」和一句「那你说怎么办」。",
            "basis": "explicit",
            "quotes": Q("linan_go", "linan_yield"),
        },
        "payoff": {
            "text": "回收：到了景秀宫，她本来只是安慰母亲，但听完大宫女的叹息后忍不住，把「许七安已经把案子查的差不多了」和「是皇后陷害的太子」都说了出来，最后把案情经过原原本本告之 —— 同一股冲动从母亲这条渠道泄了出去。",
            "basis": "explicit",
            "quotes": Q("linan_blurts", "linan_accuses", "tells_everything"),
        },
        "note": "**边界（须披露）**：这是**我的读法**（把两处的「说出去」读成同一条行为线的铺设与回收），不是叙述层点明的伏笔；原文没有说她把对父皇说的话改去对母亲说。support 是两处的动作同形（都是「把案子说出去」），counter 是：她去景秀宫早在离开御药房时就定了（P059），且第一次要说的对象是父皇、第二次是母亲，两者动机（告发 / 安慰）并不相同。我把它登记为伏笔是因为两端都有原文动作，若复核认为这是过度连线，降级为 notCauseEdges 即可。",
    },
    {
        "id": "F6",
        "name": "金莲道长等着李妙真来找许七安拼命（他自己的布局）",
        "status": "unresolved",
        "setup": {
            "text": "铺设：叙述层写明他拦下私聊的真实动机 —— 他还等着李妙真知道许七安复活后愤怒地找他拼命，以此来搅乱局面、缓解天人两宗杰出弟子的矛盾。",
            "basis": "explicit",
            "quotes": Q("jinlian_secret"),
        },
        "payoff": {
            "text": None,
            "basis": None,
            "quotes": [],
            "payoffNote": "本区间**没有回收**：李妙真不在场，开春未到，这条布局没有任何后续动作。",
        },
        "note": "**边界**：这条只出现一次，但它不是装饰性提及 —— 原文明确写成他「还等着」的将来事件，且是他拒绝私聊的真实动机；因此按「已铺设、未回收」登记并显式标 unresolved，而不放进单次出现清单。",
    },
]

SINGLE_APPEARANCE_NOT_FORESHADOW = [
    {
        "item": "「桑泊」与五百年封禁（P069–P070）",
        "why": "这是许七安内心戏里对神殊和尚处境的一次玩笑式展开，本区间只在同一段内心话里出现，没有任何事件回扣它；它是 F2（神殊之忧）的组成部分，本身不单独构成伏笔。",
        "inRangeCount": 2,
        "quotes": Q("sangbo_joke", "five_hundred_years"),
    },
    {
        "item": "「许铃音吃饭用的大碗」（P203）",
        "why": "单次出现的笑点，用来给玉碗的体积做参照；本区间没有第二处提及，也没有任何回收。",
        "inRangeCount": 1,
        "quotes": Q("bowl_small"),
    },
    {
        "item": "《气剑》（P182、P200）",
        "why": "出现两次（列名一次、被收回一次），但它没有承担任何后续 —— 许七安没练、没提、也没后悔；两处出现是同一场交易的首尾，不构成铺设与回收。",
        "inRangeCount": 2,
        "quotes": Q("luo_lists", "luo_gives_book"),
    },
    {
        "item": "「元景帝看上的女人」这条顾虑（P067）",
        "why": "单次出现，用来解释许七安为什么踌躇；他随后还是答应了（P072），这条顾虑既没有兑现也没有被排除 —— 但它只在区间内出现一次、且没有任何具体事件与之呼应，所以按单次提及登记而非未回收伏笔。",
        "inRangeCount": 1,
        "quotes": Q("luo_is_emperor_woman"),
    },
    {
        "item": "四皇子（P168）",
        "why": "整段只出现一次，是皇后「对怀庆和四皇子都是冷冷淡淡的」这条例证里的一个名字；没有任何动作或后续。",
        "inRangeCount": 1,
        "quotes": Q("details_examples"),
    },
    {
        "item": "「剑气纵横三千里，一剑光寒十九州」这句诗（P188–P190）",
        "why": "他念了一句、洛玉衡夸了一句、他在心里否认了一句：三处都在同一段对话里，是一个即时笑点，没有任何后续引用或回收。",
        "inRangeCount": 3,
        "quotes": Q("xu_poem", "luo_praises", "not_mine"),
    },
    {
        "item": "「元景三十二年每天都有丹药入库」这个前提（P014）",
        "why": "这是许七安拿来试探老太监的问句，而被问者答「时隔四年记不清」；原文从未确认这条前提，也没有第二处呼应 —— 它是一条未验证的提问，不是伏笔。",
        "inRangeCount": 1,
        "quotes": Q("ask_year32"),
    },
]

WORLD_SETTINGS = [
    {
        "id": "W1",
        "kind": "rule",
        "name": "人宗修行的代价与「精血换药性」：每月受业火烧灼，脱胎丸可暂时缓解",
        "institution": "executed",
        "quote": Q("jinlian_explains2")[0],
        "explain": "判 executed：这条设定在本区间被**执行**了 —— 洛玉衡借血的用途就是炼这种丹药（P102），血被取走后她立刻趁热去炼丹（P204）。它解释了人物能做什么与不能做什么：脱胎丸能在别人身上留下的药性可以当药引（这是许七安身上被借的东西），而业火之苦解释了洛玉衡为什么要欠这个人情。**来源标注**：内容是金莲道长的说法，我在条目里保留他的措辞（「可以暂时缓解症状」）。",
        "basis": "explicit",
        "corroboratingQuotes": Q("luo_asks_blood", "blood_taken", "luo_offer_pill"),
        "caveat": "顽疾是否只有业火一项、丹药最终是否炼成，本区间都没写（U12/U13）。",
    },
    {
        "id": "W2",
        "kind": "rule",
        "name": "人宗道法修到高深处具备「众生相」：会让观者看见自己内心最渴望的那一面",
        "institution": "misunderstood",
        "quote": Q("zhongshengxiang")[0],
        "explain": "判 misunderstood：这是**金莲道长这位人物**给出的解释，不是诏令也不是叙述层的规则条款；它的作用是把许七安此前一系列主观感受（觉得对方忽而是二十岁、忽而是少妇、忽而是美熟女）归因到功法上，从而解释他「看见了什么」。它同时约束了人物的判断：许七安自己就用这条解释安抚自己「肯定不是他的原因」，并且在被问「你见到了什么」时表情凝固（P129）。",
        "basis": "explicit",
        "corroboratingQuotes": Q("renzong_method", "age_illusion1", "age_illusion2", "age_illusion3", "cat_what_did_you_see"),
        "caveat": "同一条解释在本区间**没有被任何第三人验证**；他看见的具体内容原文只写了他的内心戏（P131），没有明说。",
    },
    {
        "id": "W3",
        "kind": "rule",
        "name": "皇宫与皇城的准入：能出入皇宫的是灵宝观的道士；能无声无息潜入皇城「少说得四品」，武夫体系不在此列",
        "institution": "misunderstood",
        "quote": Q("palace_access")[0],
        "explain": "判 misunderstood：这一条由**人物的推断与自述**拼成 —— 「能出入皇宫的，必定是灵宝观的道士了」是许七安的推断，「可以随意出入皇城了，不过皇宫依旧进不去」是金莲道长对自己现状的说明，「少说得四品」是许七安按修为估的。它直接解释了人物能出现在哪里：道士能进皇宫把他请走，而金莲道长只能出现在皇城的灵宝观、进不了皇宫 —— 这也解释了他为什么是在静室而不是在御药房找到许七安。",
        "basis": "explicit",
        "corroboratingQuotes": Q("cat_says_access", "xu_estimates"),
        "caveat": "本区间没有任何诏令或明文条目写这套准入；四品这个数字是许七安的估价（U10）。",
    },
    {
        "id": "W4",
        "kind": "rule",
        "name": "武夫体系的特点：即使一品也无法无声无息潜进皇城，但一品武夫「差不多可以单刷大奉京城」",
        "institution": "misunderstood",
        "quote": Q("wufu_cannot_sneak")[0],
        "explain": "判 misunderstood：这是许七安拿来当尺子的**体系常识**（他的理解），用来反推金莲道长不是武夫、且实力在他想象之上。它约束了人物判断：正因为武夫体系做不到无声潜入，他才能把「随意出入皇城」当成修为证据；后半句一品武夫的战力估价则给出了这个世界的武力上限印象。",
        "basis": "explicit",
        "corroboratingQuotes": Q("not_wufu", "yipin_wufu"),
        "caveat": "「单刷大奉京城这个副本」是叙述层的游戏化旁白措辞，我照原文引；本区间没有武夫实战验证。",
    },
    {
        "id": "W5",
        "kind": "rule",
        "name": "皇后旧事是「陛下的禁忌」：陈贵妃称莫要外传",
        "institution": "misunderstood",
        "quote": Q("chen_seals")[0],
        "explain": "判 misunderstood：这不是诏令，而是**陈贵妃这位人物**在失言之后给出的禁令说法，但它有实际约束力地解释了人物能做什么、不能做什么：临安刚要追问「那个男人是谁」，这句话直接把问题关掉（她说「别，别问了」），并且给女儿加上了一条不能外传的限制。它也说明这条信息在后宫是**不能公开谈的**。",
        "basis": "explicit",
        "corroboratingQuotes": Q("chen_continue", "linan_asks_who"),
        "caveat": "「禁忌」的范围与罚则原文没写；本区间也没有任何执行动作（既没人因此受罚，也没人遵守或违反的记录），所以只能记成人物理解，不能记成已执行的制度。",
    },
    {
        "id": "W15",
        "kind": "rule",
        "name": "「人情」在这个圈子里的分量：道首不喜欢欠人情，而她的人情不是一般人能得的",
        "institution": "misunderstood",
        "quote": Q("luo_no_debt")[0],
        "explain": "判 misunderstood：这是**两个人物各自的理解**，不是诏令也不是叙述层条款 —— 洛玉衡说她「不喜欢欠人情」所以让他直接开口，金莲道长则接过话说「人宗道首的人情不是一般人能得的」，劝他别急着用。它直接解释了人物能做什么与不能做什么：正因为她不肯欠，许七安才在借出精血之后拿到一份**由她定价**的补偿；也正因为这份人情分量特殊，金莲道长才会抢在他之前替他拿主意（P134）—— 这条约束塑造的是交易的另一半（T5），而不只是背景。",
        "basis": "explicit",
        "corroboratingQuotes": Q("jinlian_no_hurry", "luo_asks_blood"),
        "caveat": "「人情」如何计价、能不能转赠，原文没写；本区间也没有出现兑现或偿还的动作（见 U13）。",
    },
    {
        "id": "W6",
        "kind": "place",
        "name": "御药房与偏厅（皇宫内，许七安查账册的地方）",
        "placeState": "arrived",
        "explain": "判 arrived：有明确的驻留与离开动作 —— 他在偏厅翻完整年册子、当面问老太监、去后院茅厕、回偏厅继续问话，最后「离开御药房，时间是午时初（11:00）」。它是本区间前三分之一所有戏的舞台：查册、验谎、荷儿回报、临安要告发都在这里发生。",
        "basis": "explicit",
        "corroboratingQuotes": Q("read_books", "return_books", "toilet"),
        "quote": Q("leave_pharmacy")[0],
    },
    {
        "id": "W7",
        "kind": "place",
        "name": "灵宝观·静室（两个蒲团、一张桌案、小火炉、墙上一幅「道」字）",
        "placeState": "arrived",
        "explain": "判 arrived：有完整的到达与陈设描写 —— 他被直接带进静室、道童搬来斋饭、洛玉衡推门进来、两人用膳、取血、最后只剩他与橘猫。静室的结构还直接决定了事件：格子门能被重新推开（洛玉衡入场）、有门槛可供橘猫蹲坐。",
        "basis": "explicit",
        "corroboratingQuotes": Q("simple_room", "zhai_food", "luo_enters"),
        "quote": Q("quiet_room")[0],
    },
    {
        "id": "W8",
        "kind": "place",
        "name": "景秀宫（陈贵妃的住处）",
        "placeState": "arrived",
        "explain": "判 arrived：临安带着侍卫抵达、小跑进屋，屋内陈贵妃在抹泪，贴身宫女与「大宫女」在侧接话。它是本区间第三段戏的舞台，也是**保密被打破的地方** —— 泄密与皇后旧事都发生在这间屋子里。",
        "basis": "explicit",
        "corroboratingQuotes": Q("chen_crying", "maid_report1", "linan_quiet"),
        "quote": Q("linan_arrives")[0],
    },
    {
        "id": "W9",
        "kind": "place",
        "name": "小膳房（太监与宫女们的食堂；御膳房做主子们的伙食）",
        "placeState": "mentioned",
        "explain": "判 mentioned：本区间**无人到达** —— 许七安在「行到一半」时被蓝袍道士叫住，随后去了灵宝观；小膳房只在叙述里被介绍（太监和宫女们的食堂叫小膳房），以及道士据以判断他必经此路（P063）。按「提及≠到达」登记。",
        "basis": "explicit",
        "corroboratingQuotes": Q("daoist_waited", "someone_calls"),
        "quote": Q("xiaoshanfang")[0],
    },
    {
        "id": "W10",
        "kind": "item",
        "name": "地书碎片（许七安持有；本区间两次取出、均未完成传书）",
        "itemStates": ["hold", "use"],
        "explain": "判 hold + use（两态分开写、同时成立）：他先借去茅厕的机会取出它拿儒家版魔法书（P009），后在洛玉衡面前当面取出、刚想传书询问就想起自己现在是死人、不能开口（P109）。原文动词是「取出」，两次都没有写成传书成功 —— 这条物件在本区间的作用是**受限的资源**：能拿出来，但用不了。",
        "basis": "explicit",
        "corroboratingQuotes": Q("earth_book"),
        "quote": Q("xu_takes_earth")[0],
        "caveat": "「刚想传书询问」到「想起不能开口」之间没有传书动作，所以 itemStates 里没有 transfer。",
    },
    {
        "id": "W11",
        "kind": "item",
        "name": "儒家版魔法书（大儒们所赠）与其中的「望气术」一页",
        "itemStates": ["use", "lose"],
        "explain": "判 use + lose：原文用「找出」（取出）写使用，用「撕下一页望气术，燃尽」写失去 —— 一页被撕下并烧掉，此后本区间不再出现这本册子。它解释了人物能做什么：他随身带着可消耗的儒家术法页，可以在皇宫里随时给自己刷一个验谎手段；也解释了 T1 的代价栏。",
        "basis": "explicit",
        "quote": Q("earth_book")[0],
        "caveat": "「撕下」「燃尽」照原文写，没有改写成现代汉语动词；这本册子还剩多少页、可否补充，原文没写。",
    },
    {
        "id": "W12",
        "kind": "item",
        "name": "御药房的册子（账册，记录有缺页）",
        "itemStates": ["hold", "transfer"],
        "explain": "判 hold + transfer：他先持有并逐页看完（P005），问完话后「把册子还给老太监」（P018），随后另索取五天内的进出记录（P019）—— 也就是说，这本册子在区间内换了手：从管事老太监处来、又回到他手里。它决定了取证方式：因为册子缺页且口供问不出来，他才转向要名单与守卫核对。",
        "basis": "explicit",
        "corroboratingQuotes": Q("ask_gap", "fingerprint", "demand_5days"),
        "quote": Q("return_books")[0],
        "caveat": "册子是他向老太监要来的（P023 提到「老太监找册子的时候」），但交付这个动作本身在本区间之前，未写。",
    },
    {
        "id": "W13",
        "kind": "item",
        "name": "三本剑术册子：《心剑》《气剑》《御剑》（洛玉衡当场取出）",
        "itemStates": ["transfer", "hold"],
        "explain": "判 transfer + hold（两态分开写）：她抬手在桌面抹过、三本薄册子出现（P181），随后推《心剑》给他、收回另外两本（P200），他一并得到三次解惑的口头承诺。它解释了人物的选择空间：三篇同时摆在桌上，才使「挑哪一篇」成为一个真实的选择（T5）；也解释了资源的流向 —— 两本回到她手里、一本进他手里。",
        "basis": "explicit",
        "corroboratingQuotes": Q("thin_books", "luo_lists", "xu_picks_xinjian"),
        "quote": Q("luo_gives_book")[0],
        "caveat": "《心剑》此后的去向（他何时开始练、练成与否）本区间没有。",
    },
    {
        "id": "W14",
        "kind": "item",
        "name": "玉碗与一碗精血（取血用）",
        "itemStates": ["transfer", "use"],
        "explain": "判 transfer + use：她「从袖中取出一口玉碗」并推到许七安面前（P202 的取出与推），随后「得到鲜血」（P204）—— 血从许七安身上交到她手里，碗是这笔交付的容器。它解释了 T4 的交易形态：不是抽象的许诺，而是当场取血；量的口径由 P203 给出（碗不大，约茶杯的三倍）。",
        "basis": "explicit",
        "corroboratingQuotes": Q("bowl_small", "blood_taken"),
        "quote": Q("jade_bowl")[0],
        "caveat": "玉碗此后的去向、血的最终用途（丹药是否炼成）本区间都没写。",
    },
]

THEME_READINGS = [
    {
        "id": "TH1",
        "perspective": "以**许七安这一章的办案手段**为轴读：他推这条线用的不是权力也不是武力，而是三样东西 —— 一份能验谎的术（望气术）、一个由物证压出来的时间窗（五天）、以及一个本属于皇帝的眼线（小宦官）。视角落在他「怎么把不可问的东西变成可核对的清单」。",
        "basis": "inferred",
        "basisNote": "判 inferred：这是我的读法，不是原文的主题声明。支撑三处都出自原文动作，但「这一章在写取证方式」这一层是我的归纳。",
        "support": [
            {
                "text": "手段一：先给自己刷上验谎的术，再回偏厅问话，两次据气数下判断。",
                "quotes": Q("earth_book", "no_lie_1"),
            },
            {
                "text": "手段二：把封面指印的新鲜度换成一个可执行的时间窗（五天），并要清单 + 找守卫核对。",
                "quotes": Q("fingerprint", "xu_order_list"),
            },
            {
                "text": "手段三：把皇帝派来监督他的眼线当成助手用（所谓协助就是监督老太监），并当面交代如何向陛下汇报。",
                "quotes": Q("help_means_watch", "xu_order_report"),
            },
        ],
        "counter": [
            {
                "text": "反证一：这条线上他什么也没查实 —— 老太监经他的术判定确实不知情，动册子的人没找到，名单也还没拿到。",
                "quotes": Q("no_lie_2", "demand_5days"),
            },
            {
                "text": "反证二：真正推动案子的两条情报都不是他查出来的 —— 「荷儿」的归属是小宦官带回来的，「皇后旧事」是临安泄密后由陈贵妃说出来的。",
                "quotes": Q("eunuch_report", "chen_outburst"),
            },
        ],
        "note": "两组证据都成立：他确实有一套取证方法论（support），但这一章里它的产出为零（counter）。我因此把结论写成「他在铺设取证」，而不是「他破了案」。",
    },
    {
        "id": "TH2",
        "perspective": "以**临安的信息处置**为轴读：这一章里她两次要把事情捅出去（找父皇、告诉母妃），而两次都不是被外人挡住的 —— 第一次被许七安一句话拦下，第二次她自己在母亲面前没忍住。视角落在「亲近的人受威胁时，信息是怎么流出去的」。",
        "basis": "inferred",
        "basisNote": "判 inferred：两次「说出去」都在原文，但把它们并成一条线是我的读法（同样写在 F5 的边界里）。",
        "support": [
            {
                "text": "第一次：听到荷儿的归属就要去找父皇，被拽住后只剩一声「哼」。",
                "quotes": Q("linan_go", "linan_yield"),
            },
            {
                "text": "第二次：在大宫女的叹息与母亲的追问之间，她忍不住把「案子查的差不多了」和「是皇后陷害的太子」都说了出来，并把经过讲完。",
                "quotes": Q("linan_blurts", "tells_everything"),
            },
        ],
        "counter": [
            {
                "text": "反证一：泄密在这章里同时是**推进器** —— 皇后旧事正是被这次泄密逼出来的，所以「她把事说出去」不能被单向读成破坏。",
                "quotes": Q("chen_outburst"),
            },
            {
                "text": "反证二：许七安本人并不反对上报，他主动让小宦官把当日收获报给陛下，只要求「只说案子，不说其他」；可见这条线反对的是失控的信息，不是信息的流动。",
                "quotes": Q("xu_order_report"),
            },
        ],
        "note": "**未使用**任何以事件密度、死亡人数或篇幅中点定义「高潮」的说法，也未套三幕结构；这是两个可选视角，同一批事实另有别的读法。",
    },
]

UNKNOWNS = [
    {
        "id": "U1",
        "text": "是谁动过御药房的册子、以及二月十日/二月二十日的记录为什么会空缺（被撕掉、还是从未记）—— 本区间没有答案：老太监两次答「记不清/忘了」，而许七安的望气术判定他确实没说谎；他手上只有「指印是新的」这一条，而对「有人撕毁了册子」这个说法，许七安**始终没有正面确认过**（P022 是临安的提问，他紧接着回答的是封面指印）。我不替它补一个嫌疑人。",
        "basis": "explicit",
        "quotes": Q("old_eunuch_forget", "no_lie_2"),
    },
    {
        "id": "U2",
        "text": "「元景三十二年，应该是每天都有丹药入库吧？」是许七安的**问句**，老太监以「时隔四年记不清」回应，叙述层从未确认这条前提；我因此没有把它写成世界设定。",
        "basis": "unverified",
        "quotes": Q("ask_year32", "old_eunuch_forget"),
    },
    {
        "id": "U3",
        "text": "封面上的积灰与指印是谁的、指印有几个、位置在哪 —— 原文只给出许七安对临安的那一句话，叙述层没有独立描写过封面，也没有第二个人看过。",
        "basis": "unverified",
        "quotes": Q("fingerprint"),
    },
    {
        "id": "U4",
        "text": "「荷儿是皇后娘娘殿里的人」只有小宦官的一句回报，叙述层没有独立确认；荷儿在这个案子里到底做了什么（若有），本区间也没有写。",
        "basis": "unverified",
        "quotes": Q("eunuch_report"),
    },
    {
        "id": "U5",
        "text": "皇后是否真有罪 —— 本区间有两种相反的材料却都没有定论：临安的动机链（P041）与陈贵妃的「果真是她」（P160）指向有罪；临安自己「打心底里不相信她是个不守妇道的女人」（P166）指向相反。叙述层没有给出答案。",
        "basis": "unverified",
        "quotes": Q("linan_reason", "linan_disbelief"),
    },
    {
        "id": "U6",
        "text": "临安追问的「那个男人是谁」—— 陈贵妃以「别，别问了」拒绝回答，并称此事是陛下的禁忌；原文没有给出这个人是谁，也没有任何线索。",
        "basis": "explicit",
        "quotes": Q("linan_asks_who", "chen_seals"),
    },
    {
        "id": "U7",
        "text": "来见陈贵妃的「宗室的亲王」与「外边的大臣们」具体是谁 —— 这是贴身宫女的转述，原文没有点名任何人，也没有写他们商议的场合。",
        "basis": "unverified",
        "quotes": Q("maid_report1"),
    },
    {
        "id": "U8",
        "text": "许七安是否知道临安把案情告诉了陈贵妃 —— 本区间他在灵宝观，原文没有写他事后得知；「他不知情」是我按场景不重叠推出的（K6 已标 derived）。",
        "basis": "unverified",
        "quotes": Q("case_is_secret", "tells_everything"),
    },
    {
        "id": "U9",
        "text": "金莲道长的「伤势」是什么伤、什么时候好的 —— 他只说「伤势好了之后，可以随意出入皇城了」，原文没有交代伤情，也没有说与他橘猫形态的关系。",
        "basis": "explicit",
        "quotes": Q("cat_says_access"),
    },
    {
        "id": "U10",
        "text": "金莲道长的具体实力品级 —— 只有许七安「少说得四品」的估价，以及「道长的实力比我想象中的还强啊」的感叹；叙述层没有给品级。",
        "basis": "unverified",
        "quotes": Q("xu_estimates"),
    },
    {
        "id": "U11",
        "text": "许七安是否察觉金莲道长拦他私聊的真实动机 —— 叙述层把私心（等李妙真来闹）直接告诉了读者，但他本人只回应「也对！」；原文一个字都没写他起疑。",
        "basis": "explicit",
        "quotes": Q("jinlian_secret", "xu_okay"),
    },
    {
        "id": "U12",
        "text": "洛玉衡的「顽疾」具体是什么、是否只有业火一项 —— 金莲道长说是「每月会受业火烧灼，饱受七情六欲之苦」，这是人物说法；许七安是否全信，原文没写。",
        "basis": "explicit",
        "quotes": Q("jinlian_explains2"),
    },
    {
        "id": "U13",
        "text": "精血之约的后续：丹药有没有炼成、有没有效果、三次解惑有没有被用掉 —— 本区间只到「得到鲜血后，洛玉衡趁热，跑去炼丹了」与一句承诺。",
        "basis": "explicit",
        "quotes": Q("blood_taken", "luo_gives_book"),
    },
    {
        "id": "U14",
        "text": "望气术的判谎是否绝对可靠 —— 许七安自己的括注「一个老太监不至于有屏蔽气数的法器」说明他认为存在能屏蔽气数的法器/存在；本区间没有遇到，也没有验证。",
        "basis": "explicit",
        "quotes": Q("no_lie_2"),
    },
    {
        "id": "U15",
        "text": "「国师请用鳝」的「鳝」是否为「膳」之误 —— 原文如此，我照原文引用，不改字。",
        "basis": "explicit",
        "quotes": Q("xu_shan"),
    },
    {
        "id": "U16",
        "text": "「吃饭呢，主意猫毛」的「主意」是否为「注意」之误 —— 原文如此，照原文引用，不改字。",
        "basis": "explicit",
        "quotes": Q("xu_slap_cat"),
    },
    {
        "id": "U17",
        "text": "景秀宫里「侍立在一侧的贴身宫女」与后文叹息的「大宫女」是不是同一个人 —— 原文用了两个称呼，中间没有交代；我按两个称呼分别引用，不合并成一个人。",
        "basis": "unverified",
        "quotes": Q("maid_report1", "dagongnv_sigh"),
    },
    {
        "id": "U18",
        "text": "洛玉衡是怎么知道金莲道长已到门口的 —— 她只是「目光望向门口，淡淡道：他在这里」，原文没有写她的感知方式；E8 因此只标 inferred。",
        "basis": "unverified",
        "quotes": Q("luo_he_is_here"),
    },
    {
        "id": "U19",
        "text": "许七安选择《心剑》是否与「心剑专斩元神」能克制某类存在有关 —— 他给的理由只有自身短板（缺元神输出）与天地一刀斩的路线，原文没有写他对付谁的盘算；看向橘猫那一下是他的下意识动作，动机未写。",
        "basis": "unverified",
        "quotes": Q("why_xinjian", "xu_looks_cat"),
    },
    {
        "id": "U20",
        "text": "许七安「现在是死人」这个身份状态在本区间如何维持 —— 他取出地书碎片时想起「自己现在是个死人，不能开口说话」，但原文没有解释这条限制的来源与范围。",
        "basis": "explicit",
        "quotes": Q("xu_takes_earth"),
    },
]

NOT_CATEGORIZED = {
    "note": "读到了、但按本次六类抽取（任务五元组／因果边／状态／知识差／伏笔／世界设定）不构成独立断言，或已被上面某条吸收的段落，登记在此供反向复核对账。每条只给原文事实与位置，不给结论。",
    "items": [
        {"what": "章标题本身（本单元的界标）", "quotes": Q("title")},
        {"what": "小宦官「顺从的离开」（对 T2 委托的即时反应，无阻力）", "quotes": Q("eunuch_obedient")},
        {"what": "许七安对古代账册的吐槽（字少笔画多、看的眼睛疼），以及他用了整整一个小时才看完", "quotes": Q("books_complaint")},
        {"what": "他借「茅厕在哪」离开偏厅、老太监答「后院」", "quotes": Q("toilet", "toilet_answer", "backyard")},
        {"what": "他眼里的两道清光「继而缓缓收敛」（施术的收束动作）", "quotes": Q("eye_light")},
        {"what": "老太监「坦然」回答「大人请说」（被问时的姿态，未被望气术判为异常）", "quotes": Q("old_eunuch_tanran")},
        {"what": "所谓「协助」的实质就是监督老太监，人选是元景帝派来的小宦官", "quotes": Q("help_means_watch")},
        {"what": "临安凑到耳边低声问「你是怀疑有人撕毁了册子？」—— 这是**她的提问**，许七安没有正面回答，他回答的是封面指印（P023）；「册子被撕」因此在本区间始终只是一条未被确认的猜测", "quotes": Q("linan_whisper", "fingerprint")},
        {"what": "「厉害！」与二殿下心里夸赞、对许七安越来越有信心（旁观评价，无后续动作）", "quotes": Q("linan_praise", "linan_praises_him")},
        {"what": "临安发怒那句「本宫也不能听？」与眉毛飞扬（已作为 S1 的前值使用，此处登记完整句）", "quotes": Q("linan_angry")},
        {"what": "许七安听见临安粗重的呼吸声、心里叫糟（霍儿的回报之后、她起身之前的一拍）", "quotes": Q("linan_breath")},
        {"what": "他怀疑临安那句「是不是心里还有怀庆」会传到元景帝耳里招来杀身之祸（内心戏，未发生）", "quotes": Q("linan_jealous", "xu_inner_oh")},
        {"what": "他决定「继续查呗，公主静观其变就是了」（对临安的安抚性回答，已入 T3 的交涉结果）", "quotes": Q("xu_agree_no_idea", "xu_continue")},
        {"what": "「呼呼.....」——他听见身边临安粗重的呼吸声（E1 之后、她起身之前的一拍，无独立主张）", "quotes": Q("heavy_breath")},
        {"what": "「要糟.....」——他自己的内心惊呼（同上，过渡拍）", "quotes": Q("about_to_be_bad")},
        {"what": "临安第二次「哼」一声、对结果并不满意（情绪余波，未构成状态变化的端点）", "quotes": Q("linan_hmph2")},
        {"what": "许七安心里希望小宦官省略他和临安的互动（与 P053 的交代互为表里）", "quotes": Q("xu_inner_omit")},
        {"what": "小宦官应下「明白」", "quotes": Q("mingbai")},
        {"what": "「行到一半，忽然听见身后有人喊：许大人.......」（转场句）", "quotes": Q("someone_calls")},
        {"what": "道士「特意在附近转悠，果然给他逮住了」（他自己的判断，说明他等的确定性）", "quotes": Q("daoist_waited")},
        {"what": "道士的邀请：「许公子，道首有请。」与许七安先前的踌躇「这个......」", "quotes": Q("daoist_invite", "xu_hesitate")},
        {"what": "他决定去赴约时点明「主要是洛玉衡这个女人......她，她太诱人了」（内心戏，动机之一）", "quotes": Q("luo_tempting", "xu_agrees")},
        {"what": "「灵宝观许七安是第二次光临」及上次为金莲道长求丹药的旧事（前情交代）", "quotes": Q("second_visit")},
        {"what": "叙述层说这位人宗道首似乎很青睐他、上次说过一句暗示性十足的话（前情，未展开）", "quotes": Q("daoshou_favor")},
        {"what": "静室「简单至极的陈设，没有多余的东西了」（陈设描写，已作为 W7 的地点依据）", "quotes": Q("simple_room")},
        {"what": "道童搬来的斋饭内容（黑米、玉米、小米与三叠素菜）与他的「请慢用，道首马上过来」", "quotes": Q("zhai_food", "daotong")},
        {"what": "桌上两只碗两双筷让他「满意点头」，以及他心里的底线：如果是一个人吃就打道回宫", "quotes": Q("two_bowls", "alone_would_leave")},
        {"what": "格子门「吱~」被推开（转场音效句）", "quotes": Q("door_squeak")},
        {"what": "洛玉衡入场的服饰与朱砂描写（玄色道袍、拂尘、道簪、眉心朱砂）", "quotes": Q("luo_enters", "luo_zhusha")},
        {"what": "两人见礼与「国师请用鳝」的口误（口误已单列 U15）", "quotes": Q("xu_greet", "luo_gesture", "xu_shan")},
        {"what": "两人入座吃饭、他摸不准她的意图而斟酌不开口（吃饭戏的场面）", "quotes": Q("both_eat", "xu_unsure")},
        {"what": "关于她外貌年龄的三段错觉描写（已作为 W2 众生相的作用对象，此处登记原文）", "quotes": Q("age_illusion1", "age_illusion2", "age_illusion3")},
        {"what": "他怀疑「这女人修的是道，还是妖法？」（疑问句，未获回答）", "quotes": Q("dao_or_yao")},
        {"what": "「天地人三宗没一个正常的」那段评述（地宗受功德所累会成魔、天宗的道本身是最大的问题、天无情才能亘古长存）—— 与本区间具体行动无直接关系，故不入世界设定", "quotes": Q("three_zong", "tian_zong", "tian_wuqing", "tianren_heyi")},
        {"what": "「听金莲道长说，许公子在云州服用过脱胎丸？」与他的错愕「金莲道长和你说这个干嘛.......」", "quotes": Q("luo_asks_pill", "xu_startled")},
        {"what": "他对血液用途的类比（前世只能验血型、这个世界能玩出很多操作）", "quotes": Q("blood_uses")},
        {"what": "洛玉衡颔首两次（一次是他说要确认，一次是她默认）", "quotes": Q("luo_nod")},
        {"what": "橘猫「竖着尾巴，踩着柔软无声的猫步，跃向桌面」与他「轻轻一巴掌拍开」（动作细节，未连边）", "quotes": Q("cat_jumps", "xu_slap_cat")},
        {"what": "「当然，这里不包括武夫」这一句单独的转折（已并入 W3/W4）", "quotes": Q("not_wufu")},
        {"what": "他用电脑与硬盘作类比解释自己为什么迟疑（喜剧类比）", "quotes": Q("harddisk_joke")},
        {"what": "他大胆说出的那句「难怪我觉得国师有着非同一般的魅力」，以及「如果金莲道长不在这里，这话他是断然不敢说的」", "quotes": Q("xu_bold", "xu_would_not_dare")},
        {"what": "洛玉衡没什么表情地抬头看了一眼他、他的表情「倏然凝固」（反应镜头）", "quotes": Q("luo_looks_up", "xu_freezes")},
        {"what": "金莲道长一愣之后来了兴趣追问他「你似乎感触很深」，以及他心里的自我吐槽（黑丝控/御姐控……最后只是单纯的好色）", "quotes": Q("jinlian_presses", "xu_inner_color")},
        {"what": "「金莲道长抢在他之前开口」与洛玉衡瞥橘猫一眼（前者已作为 W15 的佐证，后者是未连边的反应镜头）", "quotes": Q("jinlian_no_hurry", "luo_glances_cat")},
        {"what": "「景秀宫。」这一行场景标记", "quotes": Q("jingxiu_palace")},
        {"what": "临安进门时的嚷嚷「母妃母妃.....」与红裙翻飞", "quotes": Q("linan_arrives")},
        {"what": "「诈呼呼的临安一下子安静了」这一段动作描写（她的情绪切换，已作为 S4 前值的场景）", "quotes": Q("linan_quiet")},
        {"what": "她前阵子情绪糟糕的两半原因（许七安殉职与太子遭遇）—— 前情交代", "quotes": Q("her_mood")},
        {"what": "临安骂叔叔们是「没远见的狗东西」以及叙述补的「她气的骂叔叔们是狗东西」", "quotes": Q("linan_rage", "calls_uncles_dogs")},
        {"what": "陈贵妃那句「你太子哥哥是庶出……废了也好，母妃也不用成日提心吊胆」以及临安听出她指的是「那位虎视眈眈的后宫之主」", "quotes": Q("chen_bitter", "linan_knows_whom")},
        {"what": "「母妃你捏疼我了」这句（E10 的直接后果）", "quotes": Q("hurts_me")},
        {"what": "「母妃别急，临安有确凿证据的......」（她要出示证据的话头，随即转入讲经过）", "quotes": Q("linan_evidence")},
        {"what": "陈贵妃把话接下去的那句「陛下宅心仁厚，念着旧情没有废她，她倒好，时隔多年，又起了争太子之位的心思」", "quotes": Q("chen_continue")},
        {"what": "「陈贵妃的话，像是一道惊雷响在临安耳畔」「她都听到了什么？」「皇后不守妇道？父皇要废后？」三句冲击镜头", "quotes": Q("thunder", "what_did_she_hear", "queen_unchaste")},
        {"what": "「作为父皇最疼爱的女儿，她听到这个消息，愤怒是理所应当。」（叙述层对她情绪合理性的评价）", "quotes": Q("anger_justified")},
        {"what": "洛玉衡那句「本座不喜欢欠人情，许大人直接说吧，想要什么」，以及叙述层点明她「不打算成全金莲道长的如意算盘」（**已升格**为 W15 的规则依据，此处登记完整句以便对账）", "quotes": Q("luo_no_debt")},
        {"what": "「阿姨，我不想奋斗了.......」这句内心狂呼", "quotes": Q("auntie_joke")},
        {"what": "金莲道长「谁说剑术不能用刀使的？」的反问与许七安自己接的「提取核心精华运用到刀法里」的领会", "quotes": Q("cat_rebuts", "xu_agrees_core")},
        {"what": "他缓缓点头、三本册子出现（此处只登记点头动作，册子已入 W13）", "quotes": Q("xu_nods", "thin_books")},
        {"what": "御剑术演示的场面描写「疾如雷霆，敏如游鱼」", "quotes": Q("fast_as_thunder")},
        {"what": "洛玉衡听完他选择后的「愕然片刻，颔首道：好。」", "quotes": Q("luo_stunned")},
        {"what": "他解释为什么心剑更适合自己的那两句（天地一刀斩是极偏激的刀法；考虑的是完善它而非增加手段），以及狮子吼之后念头更稳固", "quotes": Q("saber_art", "lion_roar")},
        {"what": "「静室里，只剩下橘猫和许七安」与他的私聊请求「道长，你帮我屏蔽一下其他人，我要私聊李妙真」", "quotes": Q("only_cat_left", "xu_wants_private")},
        {"what": "他打算告诉「二号」自己复活的消息（这条消息的收件人身份由 P206 的李妙真点明）", "quotes": Q("tell_erhao")},
        {"what": "他皱眉追问「有什么问题？」", "quotes": Q("xu_asks_problem")},
        {"what": "临安那句「是不是心里还有怀庆？」的所指：叙述层说明「她指的是『跳槽』这回事，毕竟许七安是她从怀庆那里抢过来了的」", "quotes": Q("linan_refers_jump")},
        {"what": "道士在路上截住他的方式（他知道许七安肯定要去小膳房用膳，特意在附近转悠，果然给他逮住了）与他催促的「国师等着你呢，想邀您一同用膳」", "quotes": Q("daoist_found", "daoist_urge")},
        {"what": "他问橘猫「道长，你怎么来了.....等等，你不是进不了皇城吗？」（提问本身已由金莲道长的回答承接）", "quotes": Q("xu_asks_cat")},
        {"what": "许七安对一品武夫战力上限的估价「差不多可以单刷『大奉京城』这个副本了」（已并入 W4 的引用范围）", "quotes": Q("yipin_wufu")},
        {"what": "金莲道长追问「你见到了什么？」（把众生相那条解释落到他头上的一问，已并入 W2 的佐证）", "quotes": Q("cat_what_did_you_see")},
        {"what": "三段场景分隔符与文末分隔线「........」/「..........」/「.........」/「------------」", "quotes": Q("sep1", "sep2", "sep3", "sep4", "sep_line")},
        {"what": "作者 PS 留言（码下一章、约 12 点前、请读者捉虫）", "quotes": Q("ps")},
    ],
}

SELF_CRITIQUE = [
    {
        "n": 1,
        "what": "T1 的 result 可能被读成把「人物台词」当地物证：那条「封面有明显的积灰，上面有几个指印」只有许七安对临安说过一次。",
        "why": "我仍然把它写进 result，是因为五元组问的是「他实际得到什么」，而他实际拿到的确实就是这条判断（没有第二个人看过封面）；为了不越界，我在 result 的 note 里写明这是他的话、叙述层没有独立描写，并把「指印是谁的」整条放进 U3。如果复核认为台词不能充当 result，这条应降级为「他的说法」并移出 result。",
    },
    {
        "n": 2,
        "what": "F5（被拦下的告发冲动换出口）可能是我把两件事硬连成一条伏笔线。",
        "why": "两端都有原文动作（P038–P049 与 P152–P159），但原文没有说她把对父皇要说的话改去对母亲说，而且她去景秀宫是早定的日程（P059）。我仍然登记，是因为「同一个人在同一章里两次要把同一件事说出去、第一次被拦、第二次说成了」这个形态在原文里是完整的；我把反例（对象不同、动机不同）直接写进 F5 的 note 与 TH2 的 counter，而不是只在心里知道。",
    },
    {
        "n": 3,
        "what": "我把「代价」栏收得很紧：六条任务里四条写 null，另外两条（T1/T4）也只写了物质性的一项（一页纸、一碗血）。",
        "why": "真实的代价可能存在于我没收的地方 —— 例如许七安把「自己是死人、不能开口」这条底细在洛玉衡面前暴露了动作（P109 他当面取出地书碎片），或者临安泄密之后要承担的风险。我仍然这么判断，因为本区间**没有写出任何一项被兑现的代价**：没有罚、没有失、没有后患被提及。按契约「缺字段写 null 并写明为什么没有」，我给四条 null 都写了 costNote，并点名我拒绝把哪些东西充作代价（耗时、情绪、口头承诺、规定本身）。",
    },
    {
        "n": 4,
        "what": "E4 这条因果边存在**文本顺序倒置**：索取五日记录（P019）出现在指印解释（P023）之前。",
        "why": "我仍然写这条边，是因为它由他本人补出的理由链支撑（两处都精确到「五天」这个数字，不是泛泛的「最近」），而且如果删掉它，T1 的取证动作就失去解释。为了不让复核替我发现这一点，我把「顺序倒置」直接写在 E4 的 note 里，并给出删除这条边的处置方式。",
    },
]

RED_LINES = {
    "noFabrication": "所有人物、事件、器物都出自区间内逐字引文；本候选**没有引用任何区间外的句子**，也没有引入原文没有的人物或结局。区间内出现的人物名单见 charactersInRange；被谈论而未出场的（皇后、荷儿、黄小柔、福妃子、太子、李妙真、神殊和尚、宗室亲王、大臣们）一律标为 mentioned-only。",
    "speechNotFact": "台词、内心话、转述统一标为「谁说的」：老太监的「记不清/忘了」、小宦官的回报、临安的推理、陈贵妃的旧事、洛玉衡的借血与承诺、金莲道长的解释都按台词处理；「荷儿是皇后娘娘殿里的人」「皇后不守妇道」「精血能缓解顽疾」均未被写成叙述事实，各自的存疑条目见 U4/U5/U6/U12。",
    "endNotSuccess": "T3 显式标 notSuccess：临安的目标（去找父皇）**没有达成**，达成的只是「被拦下来」，且她仍然不满意（P052）。T5 的 result 只到「拿到剑谱 + 一句承诺」，不含任何练成或有效的字样。T1 的 result 只到「他给出判断」，动册子的人没找到。T2 的 result 只到「他拿到一句回报」，且这条回报未经叙述层确认。",
    "noAdjacencyCausality": "11 条 causeEdges 全部带 mechanism 与 notMereAdjacency=true，并逐条注明边界；另设 6 条 notCauseEdges（R1–R6）明示拒绝相邻边，其中 R2 的顺序实际相反、R6 拒绝把作者 PS 与正文连边。E4 的文本顺序倒置已自行披露。",
    "noSingleAppearanceForeshadow": "伏笔只收「有铺设 + 有回收」或「铺设明确指向未来且显式标 unresolved」的 6 条；7 条单次/重复但无回收的项单列 singleAppearanceNotForeshadow，逐条写明为什么不叫伏笔（含「同一诗句出现三次」与「同一本被收回的册子出现两次」两种形态）。",
    "noUnknownAsDefault": "缺栏位写 null 并在同名的 costNote 里写明原因（T2/T3/T5/T6 四条）；没有用 0 / 0.5 / 「未提及」以外的编造值填空；读不出来或存在矛盾的地方统一进 unknowns（20 条）。",
    "mentionNotArrival": "worldSettings 的地点分 arrived（御药房与偏厅、灵宝观静室、景秀宫，都有到达或驻留动作）与 mentioned（小膳房 —— 他在半路被道士叫走，没人到达）两态，逐条给依据。**已实测的判据边界（不是猜测）**：本候选的独立复核脚本能机器抓到引文改字/偏移挪格/段号写错/命中次数虚报/五栏共用/null 栏缺 Note/伏笔谎称回收/覆盖对账造假等 12 类缺陷（见 verify_independent_report.txt 的 M1–M12），但**抓不到**「把 mentioned 写成 arrived」这类**取值合法、语义错**的篡改（M13/M14 实测 rc=0）—— 因为两者都是合法枚举值，机器无法判断某段原文到底算到达还是图谋。这一层的正确性只能靠人读引文判断，我在此显式登记，不把它算进「机器已核验」。",
    "itemStatesSeparated": "五件器物分开写各自的多选态：地书碎片 hold+use、儒家版魔法书 use+lose、御药房册子 hold+transfer、三本剑术册子 transfer+hold、玉碗与一碗精血 transfer+use；没有合成一条「物品链」，动词照原文写（取出／撕下／燃尽／还给／推给／得到）。",
    "noForcedTheme": "themeReadings 只写 2 条，各带 perspective / support / counter 三件，counter 全部带引文；没有用事件密度、死亡人数或篇幅中点定义「高潮」，也没有套三幕或英雄旅程。",
    "offsetCaliber": "start/end 一律为 docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）；所有引文偏移由构造脚本 resolve() 现算并当场断言 TEXT[start:end] == quote，从不手写。",
}

COVERAGE_HOW_READ = (
    "从 docs[0].text 取 [1001227,1009273) 切片（%d codepoints / %d 个非空段，含标题行、四个场景分隔符、"
    "文末分隔线与作者 PS）逐段通读；未使用图谱缓存摘要代替原文，图谱缓存只用于对照既有结论（该章在缓存里只有 5 条 events，"
    "无 tasks/characterStates/causeEdges）。"
) % (len(SLICE), TOTAL_PARAS)


# ── 未引用段理由（key 必须与实测未引用集合完全一致，脚本会断言）────────────
UNQUOTED_REASONS = {}   # 由 --list 跑出实测集合后填写


def build() -> dict:
    cand = {
        "task": TASK_ID,
        "agent": AGENT,
        "book": BOOK,
        "lane": LANE,
        "unitIndex": UNIT_INDEX,
        "unitHead": UNIT_HEAD,
        "unitHeadQuote": resolve("title"),
        "sourcePath": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "sourceRange": [S_START, S_END],
        "sourceSliceCodepoints": len(SLICE),
        "sourceHash": SOURCE_HASH,
        "sourceHashScope": "sha256(整个 data/cache/1063b17ca65ec1b76f30e460.docs.json 文件字节)；与任务 sourceHash 逐字一致（构造时断言）",
        "docsTextSha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
        "docsTextSha256Scope": "sha256(docs[0].text.encode('utf-8'))，全文（%d codepoints）" % len(TEXT),
        "sliceSha256": hashlib.sha256(SLICE.encode("utf-8")).hexdigest(),
        "sliceSha256Scope": "sha256(docs[0].text[%d:%d].encode('utf-8'))，仅本单元切片；另起字段，不覆盖 sourceHash" % (S_START, S_END),
        "graphCacheSha256": hashlib.sha256(GRAPH.read_bytes()).hexdigest(),
        "graphCacheRole": "data/cache/1063b17ca65ec1b76f30e460.json（图谱缓存）仅用于对照既有结论；其摘要不算原文证据，本候选的每条引文都取自 docs.json 的 docs[0].text。",
        "offsetUnit": "codepoint",
        "offsetCaliber": "start/end 一律为 docs[0].text **全文绝对** codepoint 偏移（0-based，左闭右开），不是相对切片的偏移。自检：docs[0].text[%d:%d] 以「%s」开头（构造时断言）。所有引文偏移由脚本对全文 find 现算，择优取区间内的命中，不手写。" % (S_START, S_END, UNIT_HEAD),
        "quoteMethod": "每条 quote 用 python re.finditer(re.escape(quote), docs[0].text) 在**全文**扫描，取落在 [%d,%d) 内的首次命中作为 start/end，并当场断言 TEXT[start:end] == quote；同时记录 wholeTextOccurrences（全文命中次数）与 occurrencesInRange（区间内命中次数）。" % (S_START, S_END),
        "semanticReview": "not-performed",
        "semanticReviewNote": "本候选只做**引文定位的机器可复算**（逐字／偏移／全文与区间内命中次数／段号／段内相对区间／句序号）与本人逐段通读 %d 个非空段后的语义判断。**不声称**任何 semanticReview 完成，也不声称独立复核。引文定位正确 ≠ 语义已核验。" % TOTAL_PARAS,
        "readAt": READ_AT,
        "charactersInRange": CHARACTERS,
        "tasks": TASKS,
        "causeEdges": CAUSE_EDGES,
        "notCauseEdges": NOT_CAUSE_EDGES,
        "states": STATES,
        "knowledgeGaps": KNOWLEDGE_GAPS,
        "foreshadows": FORESHADOWS,
        "singleAppearanceNotForeshadow": SINGLE_APPEARANCE_NOT_FORESHADOW,
        "worldSettings": WORLD_SETTINGS,
        "themeReadings": THEME_READINGS,
        "unknowns": UNKNOWNS,
        "notCategorizedFacts": NOT_CATEGORIZED,
        "selfCritique": SELF_CRITIQUE,
        "redLines": RED_LINES,
    }
    # 覆盖对账
    quoted = set()
    for rec in _RESOLVED.values():
        quoted.add(int(rec["paraLabel"][1:]))
    allp = set(range(1, TOTAL_PARAS + 1))
    unq = sorted(allp - quoted)
    cand["coverageNote"] = {
        "readAll": True,
        "howRead": COVERAGE_HOW_READ,
        "paragraphIndex": "按 \\n 行扫描切段（只计非空行），段号 P001–P%03d，段号与段内相对区间由脚本现算。" % TOTAL_PARAS,
        "quotedParagraphs": len(quoted),
        "totalParagraphs": TOTAL_PARAS,
        "unquotedParagraphs": ["P%03d" % p for p in unq],
        "unquotedNote": "__UNQUOTED__",
        "crossCheck": "写完各分区后做过一次反向扫描：把「读到了但没进任何分区」的段落逐条回原文 find，补入 notCategorizedFacts（作者 PS、分隔线、外貌与场面描写、内心戏、前情交代等）与 singleAppearanceNotForeshadow（7 条）。",
    }
    return cand


CHARACTERS = [
    {"name": "许七安", "role": "本区间主视角。打更人铜锣；在御药房查册、在灵宝观借血选剑", "appears": "全区间"},
    {"name": "小宦官", "role": "元景帝派来监督许七安的眼线；受托去查荷儿，回报其归属；被交代如何向陛下汇报", "appears": "P002–P058"},
    {"name": "老太监（管理御药房）", "role": "管事者；对册子缺页两次答「记不清/忘了」，被望气术判为没说谎；随后被打发走", "appears": "P007–P027"},
    {"name": "临安（二公主，裱裱）", "role": "在场听见荷儿的归属后要去找父皇，被拦下；到景秀宫探母并把案情说了出去", "appears": "P022–P059, P138–P171"},
    {"name": "洛玉衡（人宗道首、国师）", "role": "二品强者；借精血、赠《心剑》、许三次解惑，取血后去炼丹", "appears": "P084–P135, P173–P204"},
    {"name": "金莲道长（橘猫形态）", "role": "中间人；到场解释借血的用途，替许七安拿主意要剑术，拒绝他私聊李妙真", "appears": "P111–P135, P176–P178, P205–P212"},
    {"name": "陈贵妃（临安之母）", "role": "在景秀宫独处垂泪；听女儿说出案情后大哭，说出皇后旧事，随即封口", "appears": "P139–P171"},
    {"name": "蓝袍道士", "role": "灵宝观道士；在去小膳房路上截住许七安，传「道首有请」", "appears": "P061–P071"},
    {"name": "道童", "role": "搬来斋饭并请许七安慢用，随后恭敬退下", "appears": "P079–P080"},
    {"name": "贴身宫女（P144 转述者）", "role": "告诉临安：宗室亲王来见、外臣在商议另立太子，娘娘大哭两天没吃饭", "appears": "P144–P145"},
    {"name": "大宫女（P150 叹息者）", "role": "叹息案子这么多天没进展（原文用另一个称呼，是否同一人未写，见 U17）", "appears": "P150"},
    {"name": "元景帝（陛下、父皇）", "role": "未出场。本区间只作为：派小宦官监督、被小宦官汇报的对象、临安要去找的人、皇后旧事里的当事人", "appears": "mentioned-only（P003/P021/P038/P053/P067/P160–P161/P164/P171）"},
    {"name": "皇后", "role": "未出场。被小宦官指为荷儿的主子；被临安推断为构陷太子的主使；被陈贵妃说成当年不守妇道、被打入冷宫", "appears": "mentioned-only（P031/P033–P034/P041/P045–P046/P160–P161/P166–P168）"},
    {"name": "荷儿", "role": "未出场。宫女；被查出是皇后娘娘殿里的人", "appears": "mentioned-only（P002/P031/P033）"},
    {"name": "怀庆", "role": "未出场。被提到两次：听见荷儿的名字情绪不对劲（许七安的推断）、皇后对她冷淡", "appears": "mentioned-only（P033/P042–P043/P168）"},
    {"name": "黄小柔", "role": "未出场。被许七安推断曾受皇后大恩，在本案里充当谋害福妃、诬陷太子的急先锋", "appears": "mentioned-only（P033–P034/P041）"},
    {"name": "福妃子", "role": "未出场。本案的被害者（许七安与临安的表述里出现）", "appears": "mentioned-only（P034/P041/P045）"},
    {"name": "太子", "role": "未出场。临安的胞兄、陈贵妃之子；本案被诬陷的一方", "appears": "mentioned-only（P041/P045/P047/P141–P142/P148/P156）"},
    {"name": "李妙真（二号）", "role": "未出场。许七安想私聊告知复活消息的人；开春之后会来京城", "appears": "mentioned-only（P206–P211）"},
    {"name": "神殊和尚", "role": "未出场。许七安担心被洛玉衡发现的秘密；他内心戏里的五百年封禁玩笑", "appears": "mentioned-only（P068–P070）"},
    {"name": "宗室亲王 / 外臣", "role": "未出场。被贴身宫女转述为来见陈贵妃、并在商议另立太子", "appears": "mentioned-only（P144）"},
    {"name": "四皇子", "role": "未出场。出现在皇后「对怀庆和四皇子都是冷冷淡淡的」这条例证里", "appears": "mentioned-only（P168）"},
]


# ── 判据 ────────────────────────────────────────────────────────────────────
def run_checks(cand: dict) -> list:
    fails = []

    def ck(name, ok, detail=""):
        if not ok:
            fails.append("%s: %s" % (name, detail))

    # C1 源哈希三方一致
    real = hashlib.sha256(DOCS.read_bytes()).hexdigest()
    ck("C1", real == SOURCE_HASH == cand["sourceHash"], "文件哈希 %s" % real)

    # C2 切片口径
    ck("C2", TEXT[S_START:S_END].startswith(UNIT_HEAD), "切片不以标题开头")
    ck("C2b", len(SLICE) == S_END - S_START, "切片长度异常")

    # C3 每条引文逐字 + 区间内 + 哈希
    bad = []
    for qid in QSPEC:
        r = resolve(qid)
        if TEXT[r["start"]:r["end"]] != r["quote"]:
            bad.append(qid)
        if not (S_START <= r["start"] and r["end"] <= S_END):
            bad.append(qid + "(越界)")
        if r["sourceHash"] != SOURCE_HASH:
            bad.append(qid + "(哈希)")
        if r["occurrencesInRange"] < 1:
            bad.append(qid + "(区间内无命中)")
    ck("C3", not bad, "引文异常：%s" % bad)

    # C4 覆盖对账：被引段 ∪ 未引用段 == 全部段，且两集合不相交
    quoted = set()
    for qid in QSPEC:
        quoted.add(int(resolve(qid)["paraLabel"][1:]))
    unq = set(int(x[1:]) for x in cand["coverageNote"]["unquotedParagraphs"])
    ck("C4a", quoted | unq == set(range(1, TOTAL_PARAS + 1)), "覆盖不全")
    ck("C4b", not (quoted & unq), "被引段与未引用段相交")
    ck("C4c", cand["coverageNote"]["quotedParagraphs"] == len(quoted), "被引段计数不符")
    ck("C4d", cand["coverageNote"]["totalParagraphs"] == TOTAL_PARAS, "总段数不符")

    # C4e 未引用段理由必须逐段给全
    missing_reason = [p for p in sorted(unq) if p not in UNQUOTED_REASONS]
    extra_reason = [p for p in sorted(UNQUOTED_REASONS) if p not in unq]
    ck("C4e", not missing_reason, "未给理由的未引用段：%s" % ["P%03d" % p for p in missing_reason])
    ck("C4f", not extra_reason, "理由表里有非未引用段：%s" % ["P%03d" % p for p in extra_reason])
    if not missing_reason and not extra_reason:
        lines = ["未引用段共 %d 个，逐段说明：" % len(unq)]
        for p in sorted(unq):
            lines.append("P%03d「%s」——%s" % (p, PARA_BY_NO[p][2].strip(), UNQUOTED_REASONS[p]))
        cand["coverageNote"]["unquotedNote"] = "".join(lines)

    # C5 任务五栏：引文不得跨栏重复（字符串与区间）
    for t in cand["tasks"]:
        cols = ["objective", "obstacle", "action", "result", "cost"]
        seen = {}
        for c in cols:
            if t.get(c) is None:
                continue
            for q in t[c]["quotes"]:
                key = q["quote"]
                if key in seen:
                    fails.append("C5a: %s 的 %s 与 %s 共用同一句引文" % (t["id"], c, seen[key]))
                seen[key] = c
        ivs = []
        for c in cols:
            if t.get(c) is None:
                continue
            for q in t[c]["quotes"]:
                ivs.append((q["start"], q["end"], c))
        ivs.sort()
        for i in range(1, len(ivs)):
            if ivs[i][0] < ivs[i - 1][1]:
                fails.append("C5b: %s 的 %s 与 %s 引文区间重叠" % (t["id"], ivs[i][2], ivs[i - 1][2]))

    # C6 缺栏 null 必须带任务级同名 <col>Note；非 null 栏必须有 text + 引文 + 合法 basis
    for t in cand["tasks"]:
        for c in ["objective", "obstacle", "action", "result", "cost"]:
            col = t.get(c)
            note_key = c + "Note"
            note = (t.get(note_key) or "").strip()
            if col is None:
                if not note:
                    fails.append("C6a: %s.%s 为 null 但没有任务级 %s" % (t["id"], c, note_key))
                if note_key in t and not note:
                    fails.append("C6a2: %s.%s 的 %s 为空串" % (t["id"], c, note_key))
            else:
                if not isinstance(col, dict):
                    fails.append("C6b: %s.%s 类型非法" % (t["id"], c))
                    continue
                if not (col.get("text") or "").strip():
                    fails.append("C6c: %s.%s 非 null 但 text 为空" % (t["id"], c))
                if not col.get("quotes"):
                    fails.append("C6d: %s.%s 有 text 但无引文" % (t["id"], c))
                if col.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
                    fails.append("C6e: %s.%s basis 非法：%r" % (t["id"], c, col.get("basis")))
                if note:
                    fails.append("C6f: %s.%s 非 null 却带了任务级 %s" % (t["id"], c, note_key))
            for k, v in col.items() if isinstance(col, dict) else []:
                if isinstance(v, dict) and "quote" in v and v.get("sourceHash") != SOURCE_HASH:
                    fails.append("C6g: %s.%s.%s 源哈希不符" % (t["id"], c, k))

    # C7 因果边
    for e in cand["causeEdges"]:
        if not (e.get("mechanism") or "").strip():
            fails.append("C7a: %s 缺 mechanism" % e["id"])
        if e.get("notMereAdjacency") is not True:
            fails.append("C7b: %s 未声明 notMereAdjacency" % e["id"])
        if not e.get("quotes"):
            fails.append("C7c: %s 无引文" % e["id"])
        if e.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
            fails.append("C7d: %s basis 非法" % e["id"])
    for e in cand["notCauseEdges"]:
        if not (e.get("why") or "").strip() or not e.get("quotes"):
            fails.append("C7e: %s 缺 why 或引文" % e["id"])

    # C8 状态与知识差
    for s in cand["states"]:
        for k in ("before", "after", "anchor"):
            if not s.get(k, {}).get("quotes"):
                fails.append("C8a: %s.%s 无引文" % (s["id"], k))
        if not (s.get("aspect") or "").strip():
            fails.append("C8b: %s 缺 aspect" % s["id"])
    for k in cand["knowledgeGaps"]:
        for f in ("knows", "doesNotKnow", "subject"):
            if not (k.get(f) or "").strip():
                fails.append("C8c: %s 缺 %s" % (k["id"], f))
        if not k.get("quotes"):
            fails.append("C8d: %s 无引文" % k["id"])

    # C9 伏笔
    for f in cand["foreshadows"]:
        if not f.get("setup", {}).get("quotes"):
            fails.append("C9a: %s 无铺设引文" % f["id"])
        if f["status"] == "unresolved":
            if f.get("payoff", {}).get("text") is not None:
                fails.append("C9b: %s 标 unresolved 却有 payoff" % f["id"])
            if not (f.get("payoff", {}).get("payoffNote") or "").strip():
                fails.append("C9c: %s 标 unresolved 但没有 payoffNote" % f["id"])
        elif f["status"] == "resolved-in-range":
            if not f.get("payoff", {}).get("quotes"):
                fails.append("C9d: %s 标 resolved 但无回收引文" % f["id"])
        else:
            fails.append("C9e: %s status 非法：%r" % (f["id"], f["status"]))
    for s in cand["singleAppearanceNotForeshadow"]:
        if not (s.get("why") or "").strip() or not s.get("quotes"):
            fails.append("C9f: 单次出现条目缺 why 或引文：%r" % s.get("item"))

    # C10 worldSettings 三态字段
    for w in cand["worldSettings"]:
        if w["kind"] == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                fails.append("C10a: %s placeState 非法" % w["id"])
        elif w["kind"] == "item":
            st = w.get("itemStates") or []
            if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                fails.append("C10b: %s itemStates 非法：%r" % (w["id"], st))
        elif w["kind"] == "rule":
            if w.get("institution") not in ("declared", "executed", "misunderstood"):
                fails.append("C10c: %s institution 非法" % w["id"])
        else:
            fails.append("C10d: %s kind 非法" % w["id"])
        if not (w.get("explain") or "").strip():
            fails.append("C10e: %s 缺 explain" % w["id"])
        if not w.get("quote", {}).get("quote"):
            fails.append("C10f: %s 缺 quote" % w["id"])
        if w.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
            fails.append("C10g: %s basis 非法" % w["id"])

    # C11 主题解释
    ck("C11a", len(cand["themeReadings"]) <= 2, "themeReadings 超过 2 条")
    for t in cand["themeReadings"]:
        for f in ("perspective", "support", "counter"):
            if not t.get(f):
                fails.append("C11b: %s 缺 %s" % (t["id"], f))
        for grp in ("support", "counter"):
            for item in t[grp]:
                if not item.get("quotes"):
                    fails.append("C11c: %s.%s 有条目无引文" % (t["id"], grp))

    # C12 semanticReview 不得声称完成
    ck("C12", cand["semanticReview"] == "not-performed", "semanticReview 必须为 not-performed")

    # C13 变异测试：判据不是恒绿
    probe = resolve("eunuch_report")["quote"]
    mutated = probe[:-1] + ("X" if probe[-1] != "X" else "Y")
    hits_before = TEXT.find(probe)
    hits_after = TEXT.find(mutated)
    ck("C13", hits_before >= 0 and hits_after == -1,
       "变异测试失败：原文=%s 变异=%s" % (hits_before, hits_after))
    r2 = resolve("eunuch_report")
    ck("C13b", TEXT.find(mutated, r2["start"], r2["end"]) == -1, "变异串仍在原区间命中")

    # C14 每条断言 basis 合法
    allowed = ("explicit", "inferred", "derived", "unverified")
    for name, items in (("causeEdges", cand["causeEdges"]), ("unknowns", cand["unknowns"]),
                        ("themeReadings", cand["themeReadings"]), ("worldSettings", cand["worldSettings"]),
                        ("knowledgeGaps", cand["knowledgeGaps"])):
        for it in items:
            if it.get("basis") not in allowed:
                fails.append("C14: %s.%s basis 非法：%r" % (name, it.get("id"), it.get("basis")))
    for s in cand["states"]:
        for k in ("before", "after", "anchor"):
            if s[k].get("basis") not in allowed:
                fails.append("C14: %s.%s basis 非法" % (s["id"], k))

    # C15 引文登记统计
    qs = [resolve(q)["quote"] for q in QSPEC]
    cand["quoteCount"] = sum(
        len(t[c]["quotes"]) for t in cand["tasks"] for c in ("objective", "obstacle", "action", "result", "cost")
        if t.get(c) is not None
    ) + sum(len(e["quotes"]) for e in cand["causeEdges"]) + sum(len(e["quotes"]) for e in cand["notCauseEdges"]) \
      + sum(len(s[k]["quotes"]) for s in cand["states"] for k in ("before", "after", "anchor")) \
      + sum(len(k["quotes"]) for k in cand["knowledgeGaps"]) \
      + sum(len(f["setup"]["quotes"]) + len(f["payoff"]["quotes"]) for f in cand["foreshadows"]) \
      + sum(len(s["quotes"]) for s in cand["singleAppearanceNotForeshadow"]) \
      + len(cand["worldSettings"]) + sum(len(i["quotes"]) for i in cand["notCategorizedFacts"]["items"]) \
      + sum(len(t[g][i]["quotes"]) for t in cand["themeReadings"] for g in ("support", "counter") for i in range(len(t[g]))) \
      + sum(len(u["quotes"]) for u in cand["unknowns"])
    cand["quotesRegistered"] = len(set(qs))
    cand["quotesInRangeRegistered"] = len(QSPEC)
    cand["quoteRegistryNote"] = (
        "quoteCount 是引文条目总数（同一句在不同分区被再次引用会各计一次）；quotesRegistered 是登记表中不同引文串数"
        "（%d 个 id 对应 %d 个不同字符串）；所有条目都由脚本断言 TEXT[start:end] == quote 且落在区间内。"
        % (len(QSPEC), len(set(qs)))
    )

    # C16 跨分区复用披露
    use = {}
    def _walk(node, path):
        if isinstance(node, dict):
            if "quote" in node and isinstance(node["quote"], str) and "start" in node:
                use.setdefault(node["quote"], set()).add(path)
            for k, v in node.items():
                _walk(v, path)
        elif isinstance(node, list):
            for v in node:
                _walk(v, path)
    for key in ("tasks", "causeEdges", "notCauseEdges", "states", "knowledgeGaps", "foreshadows",
                "singleAppearanceNotForeshadow", "worldSettings", "themeReadings", "unknowns",
                "notCategorizedFacts"):
        _walk(cand[key], key)
    multi = {k: sorted(v) for k, v in use.items() if len(v) > 1}
    top = sorted(multi.items(), key=lambda kv: -len(kv[1]))[:5]
    cand["quoteReuseDisclosure"] = {
        "rule": "任务红线禁的是「**同一任务的五栏**共用同一句」。本候选对六条任务逐条做了两层机器判据：①引文字符串在五栏间不得重复；②任意两栏的引文区间不得重叠。构造脚本遇 violation 即非零退出且不写盘。",
        "crossSectionReuse": "**跨分区**（如 causeEdges 与 states 引用同一句台词）是允许的、也是有意为之：因果边要引触发条件，状态要引前值/后值。为免被误读成「共用依据」，此处如实登记：%d 个不同引文中，有 %d 句出现在一个以上分区。"
                             % (len(set(qs)), len(multi)),
        "topReused": [{"quote": k, "usedIn": v} for k, v in top],
        "note": "同一句在多处出现时，各自承担的语义不同（例如 P031 既是 T2 的 result，也是 E1 的触发、S-相关状态与 K1 的知识差证据）。",
    }
    return fails


def main():
    if "--list" in sys.argv:
        quoted = set(int(resolve(q)["paraLabel"][1:]) for q in QSPEC)
        unq = sorted(set(range(1, TOTAL_PARAS + 1)) - quoted)
        print("段总数 %d，被引段 %d，未引用段 %d" % (TOTAL_PARAS, len(quoted), len(unq)))
        for p in unq:
            print("P%03d  %s" % (p, PARA_BY_NO[p][2].strip()))
        print("引文 id %d，不同字符串 %d" % (len(QSPEC), len(set(resolve(q)["quote"] for q in QSPEC))))
        return 0
    cand = build()
    fails = run_checks(cand)
    if fails:
        for f in fails:
            print("[判据失败] %s" % f, file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已写 %s" % OUT)
    print("sha256 %s" % hashlib.sha256(OUT.read_bytes()).hexdigest())
    print("tasks=%d causeEdges=%d notCauseEdges=%d states=%d knowledgeGaps=%d foreshadows=%d "
          "singleAppearance=%d worldSettings=%d themeReadings=%d unknowns=%d notCategorized=%d"
          % (len(cand["tasks"]), len(cand["causeEdges"]), len(cand["notCauseEdges"]), len(cand["states"]),
             len(cand["knowledgeGaps"]), len(cand["foreshadows"]), len(cand["singleAppearanceNotForeshadow"]),
             len(cand["worldSettings"]), len(cand["themeReadings"]), len(cand["unknowns"]),
             len(cand["notCategorizedFacts"]["items"])))
    print("quoteCount=%d quotesRegistered=%d" % (cand["quoteCount"], cand["quotesRegistered"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
