#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性派生脚本：superset_spec.py（前轮 147 键，已逐条 find 验证）→ quotes_spec.py。

为什么不直接改 superset_spec.py：它是**前轮尝试的中间态**。本轮的引文登记表要有自己的、
可用一条命令复现的来源。派生脚本把「本轮相对前轮改了什么」写成代码，连同两个文件一起
进 evidence；复核者只跑本脚本即可复现 quotes_spec.py。

── 一个必须写下来的教训（本脚本第一次写的时候就踩了）────────────────────
第一版用 `A.update({...})` 往 superset 的字典里加键，其中 `q_t2_obj` 与
`q_t2_revive` 与前轮的既有键**同名**，dict.update 会**静默覆盖**——引文指向被换掉，
而 gen_quotes.py 只会报「ok」。所以本文件末尾有 `assert not clobbered`：
凡本轮新增/改名的键必须与前轮键集**不相交**，否则直接退出。
命名口径：前轮按「第几条任务」编号（它把读信编成 t2、设套编成 t3），本轮改用**语义名**，
避免两套编号混在一起。

三类改动：

  A. 拆句（防「一句话同时当多栏依据」—— 计划实测 714/1664 条任务五栏共用一句）
     · q_yqh_heal  整句含「观察伤势 / 判断没死 / 等一旬 / 活过来」四件事，拆成
       q_t2_heal、q_yqh_verify、q_t2_wait、q_yqh_revive。
     · q_la_scolded 含「白衣告状（结果）/ 被父皇臭骂（代价）/ 讨回公道（目标）」三件事，
       拆成 q_t7_res、q_t7_cost、q_t7_obj。
     · q_xu_lied   含「他怎么骗的 / 她怎么信的」两件事，拆成 q_lie_told、q_lie_effect。
     · q_remember_collapse 含「记起自己 / 梦境崩溃」两件事，拆成 q_remember_self、
       q_dream_collapse（e2 要的正是后半句）。
     · q_springsac 替换 q_uncle_busy：后者从「爹每日」起，把同句里的因（「春祭将近」）
       切掉了，留下的只是两个相邻事实。

  B. 改名（语义化，避免与前轮编号混淆；改名即删除旧键 + 新增新键，两边都登记）
     q_t2_obj→q_backup_goal、q_t2_act1→q_read_pick、q_t2_act2→q_read_last、
     q_t2_res→q_read_last_is_hq、q_t2_cost→q_read_shame、
     q_t2_heal→q_yqh_wound（"t2" 在前轮指读信、在本轮指守棺，同名会误导复核者）

  C. 补锚（原文里存在、前轮没有任何引文键指向的段落）
     梦境 P006/P007/P010–P015、棺中三栏、二郎情绪 P073、浮香信开头 P083 前半、
     许七安「怀庆看不到其余三封信」的两条理由 P131/P132、作者附言 P178/P182、
     临安 P099 的自相矛盾句、怀庆信里「采薇怕写得不好被笑话」（代笔的因）、
     八百里加急→小朝会的机制句 P164 前半。

锚串两两之间不得重复、不得互相包含；每条必须在全文与切片内各命中一次（gen_quotes.py 强制）。
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("ss", HERE / "superset_spec.py")
SS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SS)
A = dict(SS.ANCHORS)
BEFORE = set(A)

# ── A. 拆句 / 替换：删掉被拆或被替换的原锚串 ───────────────────────────────
DROP = ("q_yqh_heal", "q_la_scolded", "q_xu_lied", "q_remember_collapse",
        "q_uncle_busy",
        # B·改名的旧键：删掉才能让新名生效。**不能只 update** —— 旧键留着就是
        # 两个键指向同一字面量，gen_quotes.py 的「锚串重复」判据会拦下来
        # （这条判据就是为「假多样性」写的，本轮实测命中 5 处）。
        "q_t2_obj", "q_t2_act1", "q_t2_act2", "q_t2_res", "q_t2_cost")
for k in DROP:
    assert k in A, "被拆/被替换的键不存在：%s" % k
    del A[k]

# ── B+C. 新增（拆出的碎片 / 改名 / 补锚）──────────────────────────────────
ADD = {
    # A·拆 q_yqh_heal
    "q_yqh_wound":   ("narration", "随后，我就发现你身上的刀伤箭孔，竟诡异的修复"),
    "q_yqh_verify":  ("speech",    "我便料定你没死"),
    "q_t2_wait":     ("speech",    "等了一旬"),
    "q_yqh_revive":  ("speech",    "还真就活过来了。”"),
    # A·拆 q_la_scolded
    "q_t7_obj":      ("letter",    "等你回来，本宫再带你去讨回公道。"),
    "q_t7_res":      ("letter",    "司天监的白衣不敢对我出手，竟跑去父皇那里告状"),
    "q_t7_cost":     ("letter",    "本宫被父皇狠狠臭骂了一顿。"),
    # A·拆 q_xu_lied
    "q_lie_told":    ("inner",     "我哄她说二叔为了供我习武，四处举债，日子过的艰难"),
    "q_lie_effect":  ("inner",     "她竟然就当真了，变着法子送我银子"),
    # A·拆 q_remember_collapse
    "q_remember_self":  ("narration", "许七安心头一震，忽然记起自己是谁了"),
    "q_dream_collapse": ("narration", "也就是这个瞬间，战场画面崩溃，归于无边无际的黑暗。"),
    # A·替换 q_uncle_busy（含因的同句）
    "q_springsac":   ("letter",    "春祭将近，爹每日都归家都很晚，要么就宿在外营，没时间管理家里的事。"),
    # B·改名
    "q_backup_goal":     ("inner", "许七安有些生气，心说谁没给我回信？是我养胎技术不够好，还是本海王的钢叉，插的不够准？"),
    "q_read_pick":       ("narration", "他随便选了一封信，展开阅读："),
    "q_read_last":       ("narration", "他把临安的信塞回信封，深吸一口气，打开了最后一封信。"),
    "q_read_last_is_hq": ("narration", "信是怀庆的啊。"),
    "q_read_shame":      ("narration", "许七安臊的面红耳赤。"),
    # C·补锚：梦境
    "q_dream_sounds":  ("narration", "许七安听见了号角声，擂鼓声。渐渐的，他听见了其他声音，排山倒海的喊杀声，沉雄又杂乱的马蹄声，以及爆炸声，刀刃碰撞的锐响声。"),
    "q_dream_picture": ("narration", "各种各样的声音交织在一起，于许七安脑海构成一幅清晰的画面。"),
    "q_dream_army":    ("narration", "黑压压的大军冲杀，宛如密密麻麻的蚂蚁，高品武夫在战场中肆虐，就如同人类踩踏蚂蚁窝。"),
    "q_dream_beasts":  ("narration", "这个战场里不是只有人类，还有两层楼高的巨兽，几十米长的大蛇，盘绕在天空猛禽...."),
    "q_dream_troops":  ("narration", "有盘坐在高空诵经的高僧；有力拔山兮气盖世的蛮族；有悍不畏死的死尸大军；有成排成排的火炮军；有骑乘凶兽的骁勇骑兵....."),
    "q_dream_wield":   ("narration", "一袭青衣傲立在兽头，背负双手，漠然的俯瞰着厮杀正酣的战场。"),
    "q_dream_what":    ("speech",    "“这是什么战场？太夸张了吧，死的人太多了吧。”许七安茫然的想。"),
    # C·补锚：棺中醒来（问「这是在哪里」这条任务缺三栏依据）
    "q_t1_obj":    ("speech",    "“我们这是在哪里？”"),
    "q_t1_obs":    ("narration", "许七安睁开眼，看见的还是黑暗。"),
    "q_t1_stuffy": ("inner",     "我去，好闷....."),
    "q_t1_act":    ("narration", "他没有立刻起身，而是凝神细感应"),
    "q_t1_open":   ("narration", "许七安心里想着，推开了棺材盖。"),
    "q_t1_res":    ("speech",    "“回京的路上，哦不，水上。”"),
    # C·补锚：杨千幻
    "q_yqh_corpse": ("speech", "恰好打更人送你们的尸骨回京，我便偷偷溜上来。"),
    # C·补锚：设套一场的过渡段与许七安的情绪起点
    "q_pos_reopen": ("narration", "见许七安终于看完，杨千幻又打开了话匣子。"),
    "q_pos_sigh":   ("narration", "许七安长叹一声。"),
    "q_pos_dots":   ("speech",    "“......”杨千幻。"),
    "q_xu_smile":   ("narration", "不由的翘起嘴角，继续阅读。"),
    # C·补锚：怀庆信（采薇怕被笑话 = 代笔的因）
    "q_hq_caiwei_shy": ("letter", "她说最近在烦恼怎么给你回信，因为她不爱读书，怕写的不好让你笑话。"),
    # C·补锚：临安信的自相矛盾句
    "q_la_cover": ("letter", "“但是这种事情她肯定不会承认的啦，我随口告诉你一声，你也别记在心里，怀庆毕竟是公主，留她几分薄面。"),
    # C·补锚：玲月信里的二郎与反事实
    "q_erlang_angry": ("letter", "不过二哥最近很生气，听爹说，他在寒风里冻了半宿，第二天回家拿钱粮时，就不跟我们说话了。"),
    "q_lingyue_counterfactual": ("letter", "“如果大哥在家里，肯定不会发生这种事吧。如果二哥在家，肯定骂的先生无地自容。"),
    # C·补锚：浮香信开头
    "q_huakui_miss": ("letter", "与君一别，已是两旬，思君之情，如烈火烹油，愈发炽烈。"),
    # C·补锚：许七安「怀庆看不到其余三封信」的两条理由
    "q_xu_hidden2": ("inner", "后两者不用说，与怀庆没有交集，裱裱虽是她姐妹，但两人势如水火，不可能分享这种闺房密信。"),
    "q_xu_hidden3": ("inner", "炫耀就更不可能了，裱裱再天真无邪（婊里婊气），她也是皇家出生的公主，不会傻到把这种信拿出来到处说。"),
    # C·补锚：作者附言（结尾披露要能引到附言原句）
    "q_author_note2": ("narration", "这章六千字其中三千字是正常更新，另外三千字是盟主加更。"),
    "q_author_note3": ("narration", "今天更新晚一点，下班之后又做了会儿大纲，感觉更新要挺晚了。可能十二点以后，但不会太晚。"),
    # C·补锚：八百里加急 → 小朝会 的机制句（原锚串从「陛下就在」起，切掉了「送进宫后，没多久」）
    "q_e11_cause": ("narration", "八百里加急文书送进宫后，没多久"),
}

clobbered = sorted(set(ADD) & BEFORE)
assert not clobbered, "新增键与前轮键同名（会静默覆盖）：%s" % clobbered
A.update(ADD)
AFTER = len(A)

lines = ['''# -*- coding: utf-8 -*-
"""引文锚串声明（本文件**不含任何数字偏移**），由 derive_spec.py 派生，请勿手改。

来源：superset_spec.py（前轮 147 键）。本轮改动（拆句 / 改名 / 补锚）及其理由
逐条写在 derive_spec.py 的模块文档串里，那份文档串同时是一份**踩坑记录**
（第一版静默覆盖了同名键，故现在有 clobber 断言）。

语层 layer：
  narration 叙述 / speech 人物台词（含四封信的引号原文） / inner 叙述转述的人物内心
  letter 明确以「信」为单位转述的内容（回信正文、信中转述的他人之言）
信件与台词同属**他人之言**：只承担「信上/嘴上这样写」，不得当叙述事实。

锚串两两之间不得重复、不得互相包含；每条须在全文与切片内各命中一次（gen_quotes.py 强制）。
"""

ANCHORS = {
''']
for k, v in A.items():
    lines.append("    %r: (%r, %r),\n" % (k, v[0], v[1]))
lines.append("}\n")
(HERE / "quotes_spec.py").write_text("".join(lines), encoding="utf-8")
print("superset %d → quotes_spec %d 键（删 %d / 增 %d，无覆盖）"
      % (len(BEFORE), AFTER, len(DROP), len(ADD)))
