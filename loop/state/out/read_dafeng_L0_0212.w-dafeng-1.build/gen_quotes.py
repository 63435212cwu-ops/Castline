#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从原文**生成** quotes.py 的引文字面量（避免手打引文出错）。

为什么要有这一步（对应提示词里的一条红线）：
  引文必须能在 `docs[0].text` 里逐字 `find` 到。手打引文时，任何一个全角/半角
  标点、省略号的点数（原文里 `...` 与 `....` 都存在）都会让 H1 失败，而失败信息
  只能告诉你「对不上」，不能告诉你「你应该打什么」。
  所以本脚本按 **(段号, 起锚串, 止锚串)** 从原文里**切**出引文，
  锚串本身也是原文子串 —— 不存在「我以为是这个字」的空间。

用法：
  python3 -B -s gen_quotes.py            # 打印 quotes.py 内容
  python3 -B -s gen_quotes.py --check    # 只做自检（唯一性/落区间），不打印

判据（任一不成立即 exit 1）：
  G1  段落号存在，且段内能找到起锚串与止锚串，且起锚串在止锚串之前
  G2  切出的引文在本单元切片 [START,END) 内**恰好出现一次**
  G3  引文非空、不含换行
  G4  引文不跨越本单元边界
  G5  key 不重复
  G6  登记的 key 集合与 content_core.py 实际引用的 key 集合**完全一致**
      （少一个 ⇒ 构建时 KeyError；多一个 ⇒ 登记表里塞了没人用的条目）
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")

SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 787905, 791966
UNIT_HEAD = "第两百一十一章 缉拿人犯"
TASK_ID = "read:dafeng:L0:0212"

QA = "“"
QD = "”"

# ── 引文登记表：(key, 段号, 起锚串, 止锚串) ──────────────────────────────
# 段号按「非空行」从 1 开始编（与 coverage 分区的段落地图同一口径）。
SPEC = [
    # ── t1 张巡抚：把周旻案追到底 → 连夜缉拿杨川南 ────────────────────
    ("q_t1_obj", 4, "所以他做好了打持久战的准备", "也要把案子追查到底。"),
    ("q_t1_obs", 61, "杨川南府上的侍卫都是军中好手", "操着刀与御刀卫死斗。"),
    ("q_t1_act", 54, "张巡抚把缉拿行动留在夜里", "不给对方应对的时间。"),
    ("q_t1_res", 85, "当即就有虎贲卫上前", "押着他往府外走。"),
    # ── t2 杨川南：保住手下 → 自己被带走 ─────────────────────────────
    ("q_t2_obj", 84, "他不想手底下的人白白送死。", "他不想手底下的人白白送死。"),
    ("q_t2_obs", 74, "府上的侍卫们目眦欲裂", "玉石俱焚。"),
    ("q_t2_act", 65, "喝声传来的同时", "救下了几位侍卫的姓名。"),
    ("q_t2_act2", 75, QA, "身形摇摇欲坠。"),
    ("q_t2_res", 83, "侍卫们齐齐上前一步", "但被杨川南呵斥回去。"),
    ("q_t2_cost", 70, "这位金锣一拳击中横飞过来的杨川南胸口", "下一刻溃散成碎光。"),
    ("q_t2_cost2", 72, "杨川南吐着血横飞出去。", "杨川南吐着血横飞出去。"),
    # ── t3 宋廷风、朱广孝：领功 → 被当面追问 ─────────────────────────
    ("q_t3_obj", 37, "宋廷风和朱广孝立刻望向许七安", "为他们请功。"),
    ("q_t3_obs", 44, "张巡抚赞许的颔首", "可有此事？" + QD),
    ("q_t3_act1", 49, QA + "巡抚大人，卑职不是不想", "记不起细节了。" + QD),
    ("q_t3_act2", 50, "两人动作很默契", "记不起来了...." + QD),
    # ── t4 李妙真：弄清巡抚抓人的理由 ────────────────────────────────
    ("q_t4_obj", 106, "既然不是许七安得到了", "理由和目的何在？"),
    ("q_t4_obs", 103, QA + "我只负责盯着许七安", "其他打更人我没注意呀。" + QD),
    ("q_t4_act", 113, "接着，她看向苏苏", "我要去拜访巡抚。" + QD),
    # ── t5 许七安：汇报并把同僚写进功劳 ──────────────────────────────
    ("q_t5_obj", 25, QA + "这个就厉害了，" + QD, "不忘给两个社会性死亡的同僚请功："),
    ("q_t5_act1", 26, QA + "宋廷风和朱广孝也起到了重要作用", "令人感动。" + QD),
    ("q_t5_act2", 28, QA + "是的，昨日出行时", "许七安语气诚恳。"),
    ("q_t5_res1", 27, QA + "以身饲鬼？" + QD + "巡抚大人吃了一惊。", QD + "巡抚大人吃了一惊。"),
    ("q_t5_res2", 29, QA + "巫神教擅长养鬼驭鬼", "姜律中眉头一挑。"),
    ("q_t5_res3", 30, "许七安点点头", "觉得巫神教背锅是合情合理的"),
    # ── t6 苏苏：提议出兵 → 被反将 → 缩回律法 ────────────────────────
    ("q_t6_obj", 93, QA + "主人，伦家建议点齐三千人马", "吊在白帝城城头上。" + QD),
    ("q_t6_obs", 94, "渐渐冷静下来的李妙真斜她一眼", "就委任苏苏为冲锋营先锋。" + QD),
    ("q_t6_act", 95, "苏苏脑袋一缩", "我们还是按照大奉律法来做事吧。" + QD),
    ("q_t6_res1", 96, QA + "滚远点。" + QD, QA + "滚远点。" + QD),
    ("q_t6_res2", 98, QA + "回来！" + QD + "李妙真喊道。", QA + "回来！" + QD + "李妙真喊道。"),
    ("q_t6_cost", 97, QA + "噢。" + QD + "苏苏噘着嘴", "离开帐篷。"),
    # ── rejectedTasks 的引文 ─────────────────────────────────────────
    ("q_rt1", 37, "宋廷风和朱广孝立刻望向许七安", "为他们请功。"),
    ("q_rt2", 10, "对于案件进展，姜律中只觉得欣慰", "没有太大的情绪反应。"),
    ("q_rt4", 5, "可是，万万没想到持久战还没开始", "意味着云州之行接近尾声。"),
    # ── causeEdges ───────────────────────────────────────────────────
    ("q_e1_a", 2, "暗号解开了？！", "暗号解开了？！"),
    ("q_e1_b", 6, "意味着杨川南完了。", "意味着杨川南完了。"),
    ("q_e1_c", 5, "证据就拿到手了", "意味着云州之行接近尾声。"),
    ("q_e2_a", 70, "这位金锣一拳击中横飞过来的杨川南胸口", "下一刻溃散成碎光。"),
    ("q_e2_b", 71, "铜皮铁骨破了。", "铜皮铁骨破了。"),
    ("q_e2_c", 84, "杨川南一点都不怀疑打更人的杀伐果断", "更不怀疑金锣的战力"),
    ("q_e3_a", 77, QA + "本官好歹是二品大员", "有什么理由？" + QD),
    ("q_e3_b", 79, QA + "周旻的账簿，本官已经拿到手了。" + QD, "本官已经拿到手了。" + QD),
    ("q_e3_c", 80, "杨川南瞬间瞪大眼睛", "不可能！" + QD),
    ("q_e4_a", 36, QA + "听宁宴说", "作出巨大贡献。" + QD),
    ("q_e5_a", 35, "席上，食不言的张巡抚吃过午饭", "巡抚大人温和道："),
    ("q_e5_b", 37, "显而易见", "为他们请功。"),
    ("q_e6_a", 48, "张巡抚摇摇头，温和道", "届时论功行赏。" + QD),
    ("q_e8_a", 90, "李妙真吃惊的站起身", "一个黑衣鬼魂。"),
    ("q_e8_b", 89, QA + "什么？打更人夜闯杨府", "带走了都指挥使大人？" + QD),
    ("q_e9_a", 91, "毕竟时间长了", "会灰飞烟灭的。"),
    ("q_e9_b", 90, "这是她留在杨川南府中的眼线", "每三天替换一个。"),
    ("q_e10_a", 59, "厚重的大门瞬间撕裂", "破碎的木片激射。"),
    ("q_e10_b", 60, "打更人们率领御刀卫冲进府邸", "阻拦者杀无赦！" + QD),
    ("q_e12_a", 101, QA + "没有没有。" + QD + "苏苏连忙摇头", "裙摆飘飘。"),
    ("q_e12_b", 106, "既然不是许七安得到了", "理由和目的何在？"),
    # ── rejectedEdges ────────────────────────────────────────────────
    ("q_re2a", 33, "话锋一转，又道：", "不急，吃完饭再说。" + QD),
    ("q_re3a", 67, "始终观战的姜律中跨步而出", "朝着杨川南张开五指"),
    ("q_re4a", 100, QA + "你确定那许七安真的没有暗中调查？", "李妙真狐疑的盯着苏苏。"),
    ("q_re2b", 52, "晚饭后，姜律中和张巡抚带队", "朝着都指挥使的府邸行去。"),
    ("q_re5a", 55, "沿途遇到两拨巡城守卫", "以更强势的态度摆平"),
    # ── states ───────────────────────────────────────────────────────
    ("q_s1_before", 4, "在巡抚大人的规划中", "查起来困难重重"),
    ("q_s1_after", 5, "可是，万万没想到持久战还没开始", "意味着云州之行接近尾声。"),
    ("q_s2_before", 8, "不得不承认，还是小觑了这个年轻的铜锣", "终究还是不够了解啊。"),
    ("q_s2_after", 9, "此子必成大器。", "此子必成大器。"),
    ("q_s2_anchor", 7, "张巡抚深吸一口气", "像是第一次认识他。"),
    ("q_s3_before", 11, "许七安有金锣之资啊。", "许七安有金锣之资啊。"),
    ("q_s3_after", 12, "准确的说，他的金锣之资更加稳固了。", "现在就是七三了。"),
    ("q_s3_anchor", 10, "大概是有十五天的爆肝壮举做铺垫", "没有太大的情绪反应。"),
    ("q_s4_before", 37, "宋廷风和朱广孝立刻望向许七安", "为他们请功。"),
    ("q_s5_before", 65, "喝声传来的同时", "救下了几位侍卫的姓名。"),
    ("q_s5_after", 71, "铜皮铁骨破了。", "铜皮铁骨破了。"),
    ("q_s6_anchor", 81, "张巡抚冷笑", "自然就知晓了。" + QD),
    ("q_s8_before", 104, "李妙真点点头", "这并不重要。"),
    ("q_s8_after", 107, "试图暴力解决，屈打成招？", "试图暴力解决，屈打成招？"),
    ("q_s8_anchor", 100, QA + "你确定那许七安真的没有暗中调查？", "李妙真狐疑的盯着苏苏。"),
    ("q_s9_after", 111, QA + "点齐人马，破晓时入城。" + QD, "破晓时入城。" + QD),
    ("q_s10_a", 99, QA + "好哒，主人。" + QD + "苏苏美艳绝伦的脸蛋", "绽放甜美笑容。"),
    ("q_s10_b", 18, "许七安从怀里掏出账簿", "递了过去。"),
    ("q_s10_c", 24, "张巡抚郑重的把账簿收好", "你是怎么解开暗号的。" + QD),
    ("q_s10_d", 80, "杨川南瞬间瞪大眼睛", "不可能！" + QD),
    # ── foreshadows ──────────────────────────────────────────────────
    # ── notForeshadows ───────────────────────────────────────────────
    ("q_nf1", 53, "甚至还配备了火铳", "甚至还配备了火铳"),
    ("q_nf2", 85, "取出枷锁给杨川南套上", "取出枷锁给杨川南套上"),
    ("q_nf3", 10, "大概是有十五天的爆肝壮举做铺垫", "大概是有十五天的爆肝壮举做铺垫"),
    ("q_nf4", 8, "因为魏公的赏识和许七安表现出的能力", "因为魏公的赏识和许七安表现出的能力"),
    ("q_nf5", 21, "如此庞大的数额是多少数额？", "如此庞大的数额是多少数额？"),
    # ── worldSettings ────────────────────────────────────────────────
    ("q_w1", 14, "率先撇下众人", "上楼回到自己房间。"),
    ("q_w2", 55, "铁甲铿锵声中", "缉拿队伍来到杨川南的府邸。"),
    ("q_w3", 88, "白帝城外，军帐。", "白帝城外，军帐。"),
    ("q_w3b", 110, "军帐外值夜的侍卫应声进来。", "军帐外值夜的侍卫应声进来。"),
    ("q_w4a", 29, "看来有巫神教的家伙隐藏在白帝城中。", "隐藏在白帝城中。"),
    ("q_w4b", 92, "虽然他现在是白帝城最大的官", "竟敢动杨大人。"),
    ("q_w4c", 111, QA + "点齐人马，破晓时入城。" + QD, "破晓时入城。" + QD),
    ("q_w5", 93, "把那个姓许的铜锣吊在白帝城城头上。", "吊在白帝城城头上。" + QD),
    ("q_w7", 85, "取出枷锁给杨川南套上", "押着他往府外走。"),
    ("q_w8", 53, "刀枪弓弩等装备一应俱全", "负隅顽抗的准备。"),
    ("q_w10", 83, "阻扰巡抚办案", "是死罪。"),
    ("q_w10b", 60, "阻拦者杀无赦！" + QD, "阻拦者杀无赦！" + QD),
    ("q_w11", 38, "功勋是个好东西", "给予一定的赏银。"),
    ("q_i1_transfer", 18, "许七安从怀里掏出账簿", "递了过去。"),
    ("q_i1_use", 19, "张巡抚迫不及待的接过", "这才开始阅读账簿。"),
    ("q_i1_hold", 24, "张巡抚郑重的把账簿收好", "你是怎么解开暗号的。" + QD),
    # ── themeReadings ────────────────────────────────────────────────
    ("q_th1_counter1", 44, "张巡抚赞许的颔首", "可有此事？" + QD),
    ("q_th1_counter2", 25, "不忘给两个社会性死亡的同僚请功：", "不忘给两个社会性死亡的同僚请功："),
    ("q_th1_counter3", 50, "两人动作很默契", "记不起来了...." + QD),
    ("q_th2_s1", 79, QA + "周旻的账簿，本官已经拿到手了。" + QD, "本官已经拿到手了。" + QD),
    ("q_th2_s2", 21, "如此庞大的数额是多少数额？", "如此庞大的数额是多少数额？"),
    ("q_th2_counter1", 15, "除了许七安和姜律中，其他人都没有跟上。", "其他人都没有跟上。"),
    ("q_th2_counter2", 84, "杨川南一点都不怀疑打更人的杀伐果断", "更不怀疑金锣的战力"),
]


def load():
    raw = open(DOCS, "rb").read()
    fh = hashlib.sha256(raw).hexdigest()
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    return fh, text, text[START:END]


def paragraphs(sl):
    """非空行清单：[(段号, 行起点绝对偏移, 行文本)]，段号从 1 开始。"""
    out = []
    off = START
    for ln in sl.split("\n"):
        if ln.strip():
            out.append((len(out) + 1, off, ln))
        off += len(ln) + 1
    return out


def referenced_keys():
    """从 content_core.py 的**数据结构**里取实际引用的 key（不靠正则猜）。"""
    import importlib.util
    p = os.path.join(HERE, "content_core.py")
    spec = importlib.util.spec_from_file_location("_cc_g", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules["_cc_g"] = m
    spec.loader.exec_module(m)
    used = set()

    def walk(o):
        if isinstance(o, dict):
            if "__q__" in o:
                used.add(o["__q__"])
            for k, v in o.items():
                # `quoteKeys` 是「这个条目的依据引文」的登记位，
                # 里面放的是**纯 key 字符串**而不是 Q() 标记。
                # 早期版本没认这个字段，于是这些 key 被报成「无人引用」，
                # 而真正写错的 key（拼错的）同时又溜过了检查 —— 两个方向都瞎。
                if k == "quoteKeys" and isinstance(v, list):
                    for s in v:
                        if isinstance(s, str):
                            used.add(s)
                    continue
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for name in dir(m):
        if name.startswith("_"):
            continue
        v = getattr(m, name)
        if name in ("Q", "T"):
            continue
        if isinstance(v, (list, dict)):
            walk(v)
    used |= set(m.SPEECH_LAYER)
    return used


def main():
    check_only = "--check" in sys.argv
    fh, text, sl = load()
    probs = []
    if fh != SOURCE_HASH:
        probs.append("G0 docs.json sha256 不符：%s" % fh)
    if not sl.startswith(UNIT_HEAD):
        probs.append("G0 切片不以单元标题开头")
    paras = paragraphs(sl)
    by_no = {n: (o, s) for n, o, s in paras}

    Q, where, seen = {}, {}, set()
    for key, pno, a, b in SPEC:
        if key in seen:
            probs.append("G5 重复的 key：%s" % key)
        seen.add(key)
        if pno not in by_no:
            probs.append("G1 %s 段号不存在：%d" % (key, pno))
            continue
        poff, ptxt = by_no[pno]
        ia = ptxt.find(a)
        if ia < 0:
            probs.append("G1 %s 段 %d 找不到起锚串：%r" % (key, pno, a))
            continue
        ib = ptxt.find(b, ia)
        if ib < 0:
            probs.append("G1 %s 段 %d 从起锚串之后找不到止锚串：%r" % (key, pno, b))
            continue
        q = ptxt[ia:ib + len(b)]
        if not q or "\n" in q:
            probs.append("G3 %s 引文为空或含换行：%r" % (key, q))
            continue
        abs_start = poff + ia
        abs_end = abs_start + len(q)
        if abs_start < START or abs_end > END:
            probs.append("G4 %s 引文越出本单元：%d-%d" % (key, abs_start, abs_end))
            continue
        if sl.count(q) != 1:
            probs.append("G2 %s 引文在本单元出现 %d 次（要求恰好 1 次）：%r"
                         % (key, sl.count(q), q[:44]))
            continue
        Q[key] = q
        where[key] = (abs_start, abs_end)

    # ── G6：登记表与实际引用双向核对 ─────────────────────────────────
    try:
        used = referenced_keys()
    except Exception as exc:  # content_core 有语法错时如实报出来
        probs.append("G6 无法载入 content_core.py 取引用集合：%r" % (exc,))
        used = set()
    missing = sorted(used - set(Q))
    extra = sorted(set(Q) - used)
    if missing:
        probs.append("G6 有引用但未登记（构建时会 KeyError）：%s" % ", ".join(missing))
    if extra:
        probs.append("G6 已登记但无人引用（登记表塞了无用条目）：%s" % ", ".join(extra))

    if probs:
        for p in probs:
            print("[FAIL] %s" % p, file=sys.stderr)
        return 1

    if check_only:
        print("gen_quotes --check OK：%d 条引文全部逐字切自原文、段内唯一、"
              "落在 [%d,%d) 内；登记表与 content_core 引用集合完全一致（G6）"
              % (len(Q), START, END))
        return 0

    L = ['# -*- coding: utf-8 -*-',
         '"""引文字面量表 —— 由 gen_quotes.py 从原文**切**出，不要手改。',
         '',
         '每个值都是 docs[0].text 的逐字子串（构建脚本 H1 会重新定位核验），',
         '来源是 gen_quotes.py 的 SPEC（段号 + 起锚串 + 止锚串）。',
         '本文件不含任何手写偏移：偏移一律在构建时算。',
         '"""',
         '',
         'SOURCE_HASH = %r' % SOURCE_HASH,
         'START = %d' % START,
         'END = %d' % END,
         'UNIT_HEAD = %r' % UNIT_HEAD,
         'TASK_ID = %r' % TASK_ID,
         'DOCS_PATH = "data/cache/1063b17ca65ec1b76f30e460.docs.json"',
         '',
         'Q = {']
    for key, _p, _a, _b in SPEC:
        L.append('    %r: %r,' % (key, Q[key]))
    L += ['}', '', '# 切出的绝对偏移（仅供人读；构建与审计都自己重算，不读这里）',
          'WHERE = {']
    for key, _p, _a, _b in SPEC:
        L.append('    %r: (%d, %d),' % (key, where[key][0], where[key][1]))
    L += ['}', '']
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
