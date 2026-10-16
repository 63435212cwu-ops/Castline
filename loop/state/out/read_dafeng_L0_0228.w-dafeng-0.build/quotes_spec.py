# -*- coding: utf-8 -*-
"""引文锚串声明（本文件**不含任何数字偏移**）。

段落号 P### = `docs[0].text[start:end)` 切片按 "\\n" 切分后的**非空段**序号（从 1 起）。
op 在该段文本上切出引文：
  ("full",)               整段
  ("until", m)            段首到 m 之前
  ("from", m)             从 m 到段尾
  ("between", m1, m2)     从 m1 起点到 m2 终点（含）
锚串必须在该段内**恰好出现一次**，否则 gen_quotes.py 直接失败（不写盘）。

**一个字面量只登记一个键**。同一键可在多个分区被引用（同一条证据支持多处结论），
但同一条任务的五栏之间必须字面量两两不同（build_candidate.py H5 强制）。

layer 语层：narration 叙述 / speech 人物台词 / thought 人物内心 / letter 人物书信原文
"""

QUOTES = {
    # ══ t1 许七安确认自己身在何处 ═════════════════════════════════════════
    "q_t1_obj": {"para": 33, "op": ("between", "“我们这是在哪里？”", "“我们这是在哪里？”"), "layer": "speech"},
    "q_t1_obs": {"para": 3,  "op": ("full",), "layer": "narration"},
    "q_t1_act": {"para": 19, "op": ("between", "他没有立刻起身", "凝神细感应"), "layer": "narration"},
    "q_t1_res": {"para": 34, "op": ("between", "“回京的路上", "水上。”"), "layer": "speech"},

    # ══ t2 杨千幻潜入官船、守棺一旬等许七安复活 ═══════════════════════════
    "q_t2_obj":  {"para": 41, "op": ("between", "我便料定你没死", "还真就活过来了。”"), "layer": "speech"},
    "q_t2_obs":  {"para": 42, "op": ("between", "得知许七安战死的消息后", "永世不见天日了。"), "layer": "narration"},
    "q_t2_act":  {"para": 46, "op": ("until", "，没想到"), "layer": "narration"},
    "q_t2_res":  {"para": 30, "op": ("full",), "layer": "speech"},
    "q_t2_cost": {"para": 47, "op": ("full",), "layer": "narration"},

    # ══ t3 许七安拆阅四封回信 ═════════════════════════════════════════════
    "q_t3_obj":  {"para": 108, "op": ("full",), "layer": "thought"},
    "q_t3_obs":  {"para": 59,  "op": ("full",), "layer": "narration"},
    "q_t3_act1": {"para": 60,  "op": ("between", "许七安吐了个槽", "阅读起来。"), "layer": "narration"},
    "q_t3_act2": {"para": 81,  "op": ("full",), "layer": "narration"},
    "q_t3_act3": {"para": 107, "op": ("full",), "layer": "narration"},
    "q_t3_res":  {"para": 113, "op": ("full",), "layer": "narration"},
    "q_t3_cost": {"para": 126, "op": ("full",), "layer": "narration"},
    "q_t3_res2": {"para": 122, "op": ("between", "呵，许大人真是风流倜傥", "恰到好处。"), "layer": "letter"},
    "q_p69b":    {"para": 69,  "op": ("between", "她的手腕有浅浅的淤青", "硬拽下来的。"), "layer": "letter"},

    # ══ t4 怀庆写信提点许七安、并代采薇执笔 ═══════════════════════════════
    "q_t4_obj": {"para": 111, "op": ("between", "切记小心行事", "不给对方应对的时间。"), "layer": "letter"},
    "q_t4_obs": {"para": 112, "op": ("between", "我猜魏公暗中布局", "或许不知。"), "layer": "letter"},
    "q_t4_act": {"para": 121, "op": ("between", "我便与采薇说", "她欣然同意。"), "layer": "letter"},
    "q_t4_res": {"para": 117, "op": ("between", "怀庆真可怕啊", "很容易被抓。”"), "layer": "thought"},

    # ══ t5 许七安设套套出杨千幻偷看信件 ═══════════════════════════════════
    "q_t5_obj":  {"para": 139, "op": ("between", "许七安一下警惕起来", "你偷看我的信？”"), "layer": "speech"},
    "q_t5_obs":  {"para": 140, "op": ("between", "杨千幻冷笑道", "龌龊之事。”"), "layer": "speech"},
    "q_t5_act1": {"para": 141, "op": ("between", "许七安颔首", "她还.....”"), "layer": "speech"},
    "q_t5_act2": {"para": 144, "op": ("between", "许七安目光骤然犀利", "她告诉怀庆了？”"), "layer": "speech"},
    "q_t5_res":  {"para": 146, "op": ("full",), "layer": "narration"},
    "q_t5_cost": {"para": 148, "op": ("between", "“算了", "我也懒得计较。”"), "layer": "speech"},

    # ══ t6 魏渊为许七安筹办犀甲 ═══════════════════════════════════════════
    "q_t6_obj": {"para": 170, "op": ("between", "南宫倩柔知道魏渊的想法", "保驾护航。"), "layer": "narration"},
    "q_t6_obs": {"para": 168, "op": ("between", "若再请司天监的炼金术师和阵师出手", "炼制成法器。"), "layer": "narration"},
    "q_t6_act": {"para": 166, "op": ("between", "魏渊轻叹一声", "进展如何？”"), "layer": "speech"},
    "q_t6_res": {"para": 167, "op": ("between", "“材料已经收集完毕", "司天监炼制了。”"), "layer": "speech"},

    # ══ t7 临安为鸡精署名跑司天监闹事（她本人信中的自述）═════════════════
    "q_t7_obj":  {"para": 104, "op": ("between", "等你回来", "讨回公道。"), "layer": "letter"},
    "q_t7_obs":  {"para": 103, "op": ("between", "为什么外头都在传", "褚采薇发明的。"), "layer": "letter"},
    "q_t7_act":  {"para": 103, "op": ("between", "本宫气的要死", "闹了一场。"), "layer": "letter"},
    "q_t7_res":  {"para": 104, "op": ("between", "司天监的白衣不敢对我出手", "告状"), "layer": "letter"},
    "q_t7_cost": {"para": 104, "op": ("between", "本宫被父皇狠狠臭骂了一顿", "臭骂了一顿。"), "layer": "letter"},

    # ══ t8 婶婶为铃音被抢的玉镯子去找塾堂先生质问（玲月信中转述）═════════
    "q_t8_obs":  {"para": 71, "op": ("between", "春祭将近", "宿在外营"), "layer": "letter"},
    "q_t8_act":  {"para": 71, "op": ("between", "娘没敢告诉他", "塾堂先生质问"), "layer": "letter"},
    "q_t8_res":  {"para": 71, "op": ("between", "但先生推说不知道", "自己弄丢了。"), "layer": "letter"},
    "q_t8_cost": {"para": 71, "op": ("between", "娘气的浑身发抖", "但又无可奈何。"), "layer": "letter"},

    # ══ 因果边 ════════════════════════════════════════════════════════════
    "q_e1_a":  {"para": 16, "op": ("full",), "layer": "speech"},
    "q_e1_b":  {"para": 17, "op": ("between", "许七安心头一震", "忽然记起自己是谁了"), "layer": "narration"},
    "q_e2_a":  {"para": 17, "op": ("between", "也就是这个瞬间", "归于无边无际的黑暗。"), "layer": "narration"},
    "q_e4_a":  {"para": 51, "op": ("between", "恰好这时", "死而复生的？”"), "layer": "speech"},
    "q_e4_b":  {"para": 52, "op": ("full",), "layer": "narration"},
    "q_e4_c":  {"para": 53, "op": ("full",), "layer": "narration"},
    "q_e8_b":  {"para": 143, "op": ("between", "杨千幻赞同道", "才告诉怀庆公主的。"), "layer": "speech"},
    "q_e9_a":  {"para": 20, "op": ("full",), "layer": "narration"},
    "q_e9_b":  {"para": 21, "op": ("full",), "layer": "narration"},
    "q_e10_a": {"para": 62, "op": ("full",), "layer": "narration"},
    "q_e10_b": {"para": 61, "op": ("full",), "layer": "narration"},
    "q_e11_a": {"para": 164, "op": ("between", "八百里加急文书送进宫后", "召开了小朝会。"), "layer": "narration"},
    "q_e12_a": {"para": 101, "op": ("between", "我哄她说二叔为了供我习武", "日子过的艰难"), "layer": "thought"},
    "q_e12_b": {"para": 101, "op": ("between", "她竟然就当真了", "请继续保持啊。"), "layer": "thought"},

    # ══ 状态前值 / 后值 / 锚点 ════════════════════════════════════════════
    "q_s2_before": {"para": 44, "op": ("full",), "layer": "narration"},
    "q_s2_after":  {"para": 46, "op": ("between", "这小子身上的伤势", "是否极泰来的气象。"), "layer": "narration"},
    "q_s3_before": {"para": 114, "op": ("full",), "layer": "narration"},
    "q_s3_after":  {"para": 115, "op": ("full",), "layer": "narration"},
    "q_s5_after":  {"para": 153, "op": ("between", "他缓缓打了个冷战", "“你说什么？”"), "layer": "narration"},
    "q_s7_c":      {"para": 175, "op": ("full",), "layer": "narration"},

    # ══ 伏笔 ══════════════════════════════════════════════════════════════
    "q_f1_setup3": {"para": 72, "op": ("full",), "layer": "letter"},
    "q_f2_setup2": {"para": 70, "op": ("between", "问她是谁干的", "她也不说"), "layer": "letter"},
    "q_f4_evidence": {"para": 151, "op": ("full",), "layer": "speech"},
    "q_f6_setup2": {"para": 27, "op": ("full",), "layer": "narration"},
    "q_f6_setup3": {"para": 28, "op": ("between", "只是我为什么会梦到山海关战役？", "只是我为什么会梦到山海关战役？"), "layer": "thought"},

    # ══ notForeshadows / rejected ═════════════════════════════════════════
    "q_nf2_a":  {"para": 36, "op": ("between", "我死了一回", "有没有为我伤心"), "layer": "speech"},
    "q_nf3_a":  {"para": 37, "op": ("between", "最后还是没有把苏苏骗回家当纸片人老婆", "纸片人老婆"), "layer": "thought"},
    "q_nf4_a":  {"para": 105, "op": ("between", "其实鸡精还真是采薇做出来的", "我只是给个思路。"), "layer": "thought"},
    "q_nf5_a":  {"para": 76, "op": ("between", "娘说开春后", "她怎么不自己嫁。"), "layer": "letter"},
    "q_nf5_b":  {"para": 87, "op": ("between", "听说许郎在青州新作一首诗", "警示世人。"), "layer": "letter"},
    "q_p174":   {"para": 174, "op": ("full",), "layer": "narration"},
    "q_rj3_a":  {"para": 152, "op": ("full",), "layer": "narration"},
    "q_rt1_a":  {"para": 50, "op": ("full",), "layer": "speech"},
    "q_rt1_b":  {"para": 54, "op": ("full",), "layer": "speech"},
    "q_rt1_c":  {"para": 55, "op": ("full",), "layer": "speech"},
    "q_rt2_a":  {"para": 176, "op": ("full",), "layer": "speech"},
    "q_rt4_a":  {"para": 129, "op": ("between", "哦，我已经死了", "那没事了。"), "layer": "thought"},

    # ══ 世界设定 ══════════════════════════════════════════════════════════
    "q_w2_a":    {"para": 162, "op": ("between", "其中八百里加急的情报", "任何人不得经手。"), "layer": "narration"},
    "q_w2_b":    {"para": 163, "op": ("full",), "layer": "narration"},
    "q_w3_a":    {"para": 85,  "op": ("between", "然云州与京城相隔万里", "消息传递不易。"), "layer": "letter"},
    "q_w4_a":    {"para": 172, "op": ("full",), "layer": "narration"},
    "q_w4_b":    {"para": 159, "op": ("full",), "layer": "narration"},
    "q_w5_b":    {"para": 155, "op": ("full",), "layer": "narration"},
    "q_w8_a":    {"para": 57,  "op": ("between", "他忽然发现自己怀里揣着四份信函", "四份信函。"), "layer": "narration"},
    "q_w9_a":    {"para": 69,  "op": ("between", "娘给她买的玉镯子", "不见了踪影。"), "layer": "letter"},
    "q_w10_a":   {"para": 120, "op": ("between", "从青州寄了一片红莲花瓣给我", "红莲花瓣给我"), "layer": "letter"},
    "q_w11_a":   {"para": 168, "op": ("between", "犀甲是魏渊要送给许七安的礼物", "水火不侵。"), "layer": "narration"},
    "q_w_cloud": {"para": 110, "op": ("between", "云州环境复杂", "不小的势力。"), "layer": "letter"},
    "q_percept_cabin":   {"para": 19, "op": ("between", "他“看见”了黑暗的船舱", "黑暗的船舱"), "layer": "narration"},
    "q_percept_coffins": {"para": 19, "op": ("between", "看见了整齐排列的五口棺材", "五口棺材"), "layer": "narration"},
    "q_percept_ship":    {"para": 19, "op": ("between", "看见了缓速航行的官船", "缓速航行的官船"), "layer": "narration"},
    "q_percept_canal":   {"para": 19, "op": ("between", "看见了波光荡漾的运河", "波光荡漾的运河。"), "layer": "narration"},
    "q_s3_before2":      {"para": 40, "op": ("between", "恰好打更人送你们的尸骨回京", "我便偷偷溜上来。"), "layer": "speech"},

    # ══ 未知 / 主题 / 自评 / 排除项 ═══════════════════════════════════════
    "q_u_caiwei": {"para": 119, "op": ("between", "她说最近在烦恼怎么给你回信", "让你笑话。"), "layer": "letter"},
    "q_u10_a":    {"para": 105, "op": ("between", "她要利用鸡精", "与我知会过了。"), "layer": "thought"},
    "q_u14_a":    {"para": 73,  "op": ("between", "不过二哥最近很生气", "就不跟我们说话了。"), "layer": "letter"},
    "q_ex1_a":    {"para": 98,  "op": ("between", "你发明的五子棋", "发扬光大啦"), "layer": "letter"},
    "q_ex2_a":    {"para": 161, "op": ("full",), "layer": "narration"},
    "q_ex3_a":    {"para": 169, "op": ("full",), "layer": "narration"},
    "q_ex4_a":    {"para": 90,  "op": ("full",), "layer": "thought"},
    "q_ex5_a":    {"para": 156, "op": ("full",), "layer": "narration"},
}
