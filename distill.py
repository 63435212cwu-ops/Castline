#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Castline · distill.py — 文风蒸馏引擎（样本浸泡法）

把一部作品的原文蒸馏成「另一个写作者可以逐条执行」的巨型提示词，同时产出原著样本浸泡文档。

设计原则（针对「模型不可控、但提示词必须可控」）：
  1. 凡是能算的，绝不问模型。句长、段长、对白占比、标点频次、四字短句率、对话标签偏好、
     感官密度、高频词、人称分布 —— 全部由本模块用确定性算法算出。模型只解释这些数字造成的读感，
     不得改写数字。这样即使用户接的是弱模型，提示词里的硬骨架依然准确。
  2. 凡是要问模型的，必须挂原文引证。每条结论都要求 quote 逐字引自给定样本，事后由本模块
     逐条回查原文（verify_quotes），改写 / 拼接 / 臆造的引证一律剔除并计入 dropped。
  3. 结论必须可执行。禁止「生动 / 细腻 / 优美」一类无法执行的形容词结论，一律要求写成
     「写什么 · 放在哪 · 用什么句式 · 多长 · 接什么」，并配一条反例（这位作者不会怎样写）。
  4. 最终文档由 Python 拼装，不交给模型整段生成 —— 一万五千字的提示词交给模型输出必然截断。
  5. 构思与文风分开取材。文风能从 1800 字的窗口里看出来，构思不能：「一章从哪起到哪停」
     「伏笔埋多远才兑现」「新麻烦怎么被造出来」只在序列上可见。所以 arch 阶段的输入不是样本窗口，
     而是全书章节钩子分型（确定性）+ 图谱抽出的有序剧情点（连续取段，不取散点）。
     结构结论没有原文句子可引，改用 fact 字段核验它是否指认得出真实的章 / 剧情点。
  6. 自己的效果自己测。fidelity 阶段让同一个模型分别在【带这份提示词】和【不带】两种条件下
     写同一个场景，再用统计原著的同一套算法逐维比对 —— 有对照组，才知道这份提示词是真起作用
     还是只是很长。测不了的东西（立意、人物魅力、长跨度结构）明说测不了，不打分。

对外只有一个入口：
    run(docs, names, emit, call, cancel=None, force=False, cache_dir=None, title="")
`call(prompt, schema, max_tokens, think, system)` 由 serve.py 注入，便于用假模型做端到端测试。
"""
import hashlib
import json
import os
import re
import threading
import time

# d3：换行感知的断句。d2 把没有句末标点的段落粘进下一句，句长均值虚高七成
# （实测 30.7 vs 真实 17.8、长句占比 23.9% vs 真实 7.1%）——按 d2 的数字去模仿会写歪，
# 所以必须换版本号让旧缓存失效，而不是让它继续被读出来。
# d4：新增构思引擎（arch）与保真回测（fidelity）；章末的作者行外话（求票 / 更新说明）
# 从章节收尾句里剔除 —— 它把「作者怎么收手」整体掩盖了（断言收尾 82.8% → 65.4%，
# 对白收尾 8.4% → 19.3%）。这几项都会改变文档内容，必须换版本号。
# d5：章节标题的兜底识别 + 抓取导航剔除。网页抓取的正文把导航文字粘在回目前面
# （「…整理校对后一页前一页回目录回首页第二回　张翼德怒鞭督邮」），^ 锚定的正则只认得第一回，
# 实测三国演义 120 回被算成 2 章：章节体量失真、附录 B 退化为全篇首尾、钩子分型全废。
# 修好后 120 回全部识别，且真实回末句（「毕竟董卓性命如何，且听下文分解。」）不再被
# 「…回目录回首页」顶掉 —— 此前那一栏一直在展示抓取导航而不是作者的收手方式。
# d6：不带引号的说话（「赵曰：不知。」）计入对白。旧版只认引号，于是模型照着文言口吻
# 写出来的整段对白被算成「零对白」——保真回测里对白占比 / 台词均长 / 裸引号率 / 标签偏好
# 四项同时归零，恰恰把它模仿得最像的地方判成了完全没做到（实测试写样本 0.0% → 41.1%，
# 作者 42.6%）。作者口径几乎不动（三国 42.3→42.6、大奉 21.6→21.7），所以不是靠放宽换来的。
# 这会改变文档里的数字与结论，必须换版本号让旧缓存失效。
VERSION = "d6"


class Cancelled(Exception):
    """用户取消。serve.py 捕获后转成它自己的 Cancelled，走同一套「已完成部分保留」的收尾。"""

# ---------------------------------------------------------------------------
# 语言学工具：句 / 段 / 引号 / 章节
# ---------------------------------------------------------------------------
SENT_SPLIT = re.compile(r"(?<=[。！？…?!])(?=[^”」』）\)])")
CJK = re.compile(r"[一-鿿]")
# 引号：必须认直引号 "…"。转换自 EPUB / 网页的材料大量使用直引号，只认弯引号时
# 对白占比、台词长度、标签偏好、裸引号率会整片归零 —— 整个对白一节的结论随之作废。
# 实测：模型按提示词写出的稿子对白占 45.0%（原著 42.3%，几乎命中），旧正则报的是 0.0%。
# 内容不跨行：直引号没有方向，不排除换行的话一个落单的 " 会把后面整段吞掉。
# 代价是弯引号里的跨行台词不再匹配，实测 4.6 万处只少 63 处（0.13%），换得直引号材料可用。
QUOTE_RE = re.compile(r"[“「『\"]([^“”「」『』\"\n]{1,600})[”」』\"]")
# 不带引号的说话：「赵曰：不知。」「他道：走吧。」——文言 / 半文言里是常态，网文里也不少。
# 旧版只认引号，于是模型照着文言口吻写出的整段对白被算成「零对白」：保真回测里
# 对白占比 / 台词均长 / 裸引号率 / 标签偏好四项同时归零 —— 恰恰把它模仿得最像的地方判成完全没做到。
# 实测（d6 之前 → 之后）：三国演义 42.3% → 42.6%、大奉打更人 21.6% → 21.7%
# （作者口径几乎不动，说明不是靠放宽换来的），而按文言写出的试写样本 0.0% → 41.1%（作者 42.6%）。
# 首字直接排除引号与空白：否则 \s* 会回溯，把「道： “……」这种带引号的也吃进来。
# 「云」单独一支：兵法云 / 圣人云 / 古人云 是引经据典，不是有人在说话。
BARE_SPEECH = re.compile(
    r"(?:(?<![知味难街霸赛便公孔王胡地跑水诗词歌赞论表书檄叹笑])[曰问答道]"
    r"|(?<![法人古今诗词])云)"
    r"[：:]"
    r"([^\s“”\"「」『』‘’\n。！？…][^\n。！？…]{0,119}[。！？…]?)")
CH_HEAD = re.compile(r"^[\t 　]*(第[一二三四五六七八九十百千零〇两\d]+[章节回幕卷部集][^\n]{0,40}|Chapter\s*\d+[^\n]{0,40}|#{1,3}\s+[^\n]{1,40})\s*$", re.M)
FILE_HEAD = re.compile(r"^【文件：([^】]*)】.*$", re.M)

# 对话标签：作者偏爱哪个「说」字，是极强的文风指纹
SAY_TAGS = ["说道", "说", "道", "问道", "问", "答道", "答", "喊道", "喊", "叫道", "叫", "吼道", "吼",
            "笑道", "冷笑", "苦笑", "叹道", "叹", "骂道", "骂", "低声道", "轻声", "开口", "嘟囔", "自语", "回道", "应道"]
SENSE = {
    "视": "看见望瞧瞥盯扫视凝注目睹眺瞄",
    "听": "听闻响声音吵静寂喧噪嗡",
    "嗅": "闻嗅香臭腥膻馊霉气味",
    "味": "尝甜酸苦辣咸涩腻鲜",
    "触": "摸碰触疼痛凉冷热烫湿黏糙滑硬软麻痒",
}
ONOMAT = re.compile(r"[咔嗒砰哗嘎咚呼嘶滴叮咣哐噗嗤呲啪唰轰嘭咯吱簌沙铮][啦嗒嚓当当啦]?")
PRONOUN = ["我们", "我", "你们", "你", "他们", "她们", "它们", "他", "她", "它", "咱", "自己"]
PUNCT = ["，", "。", "！", "？", "…", "—", "、", "；", "：", "“", "”", "‘", "’", "（", "《", "·", "「", "」"]
# 单字功能词：整串都由这些字组成的 n-gram 一律不是「偏爱词」
FUNC_CH = set("的了是在有和就不都一上也很到要去会着没这那个们我他她它把被给对从而与之其如但还又只已"
              "能可自所为以于或过来下里后前中大小多少好再才")
# 词级停用词：「的时候」「自己的」这类高频但零信息的组合，靠单字规则挡不住。
# 刻意保留 忽然 / 似乎 / 仿佛 / 眼睛 / 心里 一类：它们本身就是极强的文风指纹
# （某作者每千字用五次「仿佛」，这正是模仿者必须知道、也是 AI 最容易滥用的东西）。
# 首尾禁用字：黏着性最强的虚字。n-gram 以它开头或结尾，说明窗口切在词中间。
# 刻意不含 着（看着 / 想着 是真实用词）、不 / 没（不敢 / 没料 有信息量）。
EDGE_BAN = set("的了是在和就都个们之而与把被给其也又只已所于对从这那一有很再更被将把")
STOP_W = set(("自己 自己的 的时候 时候 知道 现在 什么 怎么 这样 那样 一个 一些 已经 因为 所以 然后 但是 如果 虽然 虽说 "
              "起来 出来 过去 下来 上去 一下 一点 有些 只是 还是 就是 不是 没有 这个 那个 这些 那些 他们 我们 你们 "
              "可以 应该 或者 而且 不过 于是 这才 才是 也是 都是 就要 东西 事情 地方 样子 一样 一般 "
              "之后 之前 之中 之间 里面 外面 上面 下面 因此 并且 以及 什么的").split())
TIME_MARK = re.compile(r"(第二天|次日|翌日|入夜|天亮|黄昏|傍晚|清晨|半夜|三天后|一个月后|多年后|许久|片刻|不久|良久|与此同时|后来|从此|那天|当晚|次晨)")
# 内心 / 动作标记：原表只收现代白话词，在文言与半文言材料上整体归零
# （实测三国演义风格的稿子里「暗思」「寻思」「举锤」「拱手」一个都不算），
# 于是内心密度与动作密度对这类作品失去意义。补上文言常用形，两侧同时受益，比对仍然公平。
THOUGHT = re.compile(r"(心里|心中|想到|想着|以为|念头|明白|意识到|忽然懂|才知道|暗自|自问|后悔|似乎觉得|说不清"
                     r"|暗思|寻思|暗想|自思|窃思|暗忖|忖度|心下|寻思道)")
MOTION = re.compile(r"(转身|抬手|伸手|迈步|扑|拽|掀|踹|踢|挥|扣|拔|冲|窜|翻|滚|砸|撞|拧|摔|抓|按|掐|扯|跃|蹲|跪|奔|逃"
                    r"|拔剑|挥刀|举锤|举刀|上马|下马|策马|拍案|拱手|作揖|叩首|跪拜|疾走|飞奔|回身|欠身|起身)")
EMO_MARK = re.compile(r"[！？]|……")


def _sentences(t):
    """句：先按行断，再按句末标点断。

    只按标点断是错的：网文里大量段落没有句末标点（章节标题、`“嗯……”`、破折号收尾），
    这些段落会被粘到下一段的句子里，导致 sentences 少于 paras、句长均值虚高、
    one_sent_ratio 虚高 —— 实测 176 万字的书上 paras(1675) 反而多于 sentences(1014)。
    换行在中文行文里就是硬断句，必须先切。
    """
    out = []
    for line in t.split("\n"):
        line = line.strip()
        if not line:
            continue
        for raw in SENT_SPLIT.split(line):
            s = raw.strip()
            if s and CJK.search(s):
                out.append(s)
    return out


def _paras(t):
    return [p.strip() for p in re.split(r"\n+", t) if p.strip()]


def _cjk_len(s):
    return len(CJK.findall(s))


def _pct(a, b, nd=1):
    return round(100.0 * a / b, nd) if b else 0.0


def _quantile(sorted_vals, q):
    if not sorted_vals:
        return 0
    i = max(0, min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def strip_heads(text):
    """去掉 assemble() 加的【文件：…】行，蒸馏只看作者真正写的字"""
    return FILE_HEAD.sub("", text)


# ---------------------------------------------------------------------------
# 一、硬性度量：确定性统计，模型不得改写
# ---------------------------------------------------------------------------
def metrics(text, names=None):
    names = [n for n in (names or []) if n and len(n) >= 2][:400]
    t = strip_heads(text)
    n_all = len(t)
    n_cjk = _cjk_len(t)
    sents = _sentences(t)
    paras = _paras(t)
    slens = sorted(_cjk_len(s) for s in sents)
    plens = sorted(_cjk_len(p) for p in paras)
    psent = sorted(len(_sentences(p)) for p in paras)

    quotes = QUOTE_RE.findall(t)
    # 不带引号的说话也是说话（见 BARE_SPEECH 的说明）。两者合并统计，
    # 但分别留计数，文档里要能说清这位作者到底用不用引号。
    bare_sp = [x for x in BARE_SPEECH.findall(t) if _cjk_len(x) >= 2]
    speech = quotes + bare_sp
    qchars = sum(_cjk_len(q) for q in speech)
    qlens = sorted(_cjk_len(q) for q in speech)

    # 对话标签偏好：长标签优先匹配，避免「说道」被算成「说」
    tag_hits = {}
    for m in QUOTE_RE.finditer(t):
        win = t[max(0, m.start() - 14):m.start()] + t[m.end():m.end() + 14]
        for tag in SAY_TAGS:
            if tag in win:
                tag_hits[tag] = tag_hits.get(tag, 0) + 1
                break
    for m in BARE_SPEECH.finditer(t):
        if _cjk_len(m.group(1)) < 2:
            continue
        # 不带引号的说话，动词本身就是标签（曰 / 道 / 问 / 答 / 云），不必再去左右找
        v = t[m.start()]
        tag_hits[v] = tag_hits.get(v, 0) + 1

    # 四字短句：逗号/句读之间正好四个汉字 —— 中文节奏的硬指标
    clauses = [c for c in re.split(r"[，。！？；：、…—\n“”「」]", t) if c.strip()]
    cl_cjk = [_cjk_len(c) for c in clauses]
    four = sum(1 for c in cl_cjk if c == 4)

    sense = {}
    for k, chars in SENSE.items():
        sense[k] = sum(t.count(c) for c in chars)
    sense_total = sum(sense.values())

    pron = dict((p, 0) for p in PRONOUN)
    rest = t
    for p in PRONOUN:            # 长词先数并挖掉，「我们」不会被重复计入「我」
        c = rest.count(p)
        pron[p] = c
        if c:
            rest = rest.replace(p, "\x00" * len(p))

    punct = dict((p, t.count(p)) for p in PUNCT)

    chaps = chapters(t)
    ch_lens = sorted(_cjk_len(c["text"]) for c in chaps) if chaps else []

    per10k = lambda v: round(10000.0 * v / max(1, n_cjk), 1)
    return {
        "chars": n_all, "cjk": n_cjk,
        "sentences": len(sents), "paras": len(paras), "chapters": len(chaps),
        "sent_len": {"mean": round(sum(slens) / max(1, len(slens)), 1), "p10": _quantile(slens, .10),
                     "median": _quantile(slens, .50), "p90": _quantile(slens, .90), "max": slens[-1] if slens else 0,
                     "short_ratio": _pct(sum(1 for x in slens if x <= 8), len(slens)),
                     "long_ratio": _pct(sum(1 for x in slens if x >= 40), len(slens))},
        "para_len": {"mean": round(sum(plens) / max(1, len(plens)), 1), "median": _quantile(plens, .50),
                     "p90": _quantile(plens, .90),
                     "sent_per_para": round(sum(psent) / max(1, len(psent)), 1),
                     "one_sent_ratio": _pct(sum(1 for x in psent if x <= 1), len(psent))},
        "dialogue": {"ratio": _pct(qchars, n_cjk), "count": len(speech),
                     "quoted": len(quotes), "unquoted": len(bare_sp),
                     "unquoted_ratio": _pct(len(bare_sp), len(speech)),
                     "mean_len": round(sum(qlens) / max(1, len(qlens)), 1), "median_len": _quantile(qlens, .50),
                     "p90_len": _quantile(qlens, .90),
                     "tags": sorted(tag_hits.items(), key=lambda kv: -kv[1])[:10],
                     # 裸引号率 = 一句说话前后找不到任何说话动词的比例（作者省不省「他说」）。
                     # 不带引号的那些天生带动词，所以分子只可能来自带引号的那一批。
                     "bare_ratio": _pct(max(0, len(quotes) - sum(tag_hits.values()) + len(bare_sp)), len(speech))},
        "clause": {"mean": round(sum(cl_cjk) / max(1, len(cl_cjk)), 1), "four_ratio": _pct(four, len(cl_cjk)),
                   "count": len(cl_cjk)},
        "sense": dict((k, per10k(v)) for k, v in sense.items()),
        "sense_total_per10k": per10k(sense_total),
        "onomat_per10k": per10k(len(ONOMAT.findall(t))),
        "pronoun": dict((k, per10k(v)) for k, v in pron.items() if v),
        "punct_per10k": dict((k, per10k(v)) for k, v in punct.items() if v),
        "time_mark_per10k": per10k(len(TIME_MARK.findall(t))),
        "thought_per10k": per10k(len(THOUGHT.findall(t))),
        "motion_per10k": per10k(len(MOTION.findall(t))),
        "chapter_len": {"mean": round(sum(ch_lens) / max(1, len(ch_lens)), 0) if ch_lens else 0,
                        "median": _quantile(ch_lens, .50), "min": ch_lens[0] if ch_lens else 0,
                        "max": ch_lens[-1] if ch_lens else 0},
        "ngrams": ngrams(t, names),
        "sent_openers": openers(sents, names),
        "warnings": [],
    }


def prose_warnings(m):
    """材料不是叙事正文时，度量会失真 —— 与其悄悄产出一份错的提示词，不如当面说清。
    典型来源：细纲、设定表、人物档案、纯列表 markdown。"""
    w = []
    s, d = m["sent_len"], m["dialogue"]
    if s["mean"] > 90:
        w.append("句长均值 %s 字，远超叙事正文的常态（20-40 字）：材料里很可能大量缺少句末标点，"
                 "或者是列表 / 表格 / 细纲，不是正文。句法与节奏两节的结论会失真。" % s["mean"])
    if d["ratio"] < 3 and m["cjk"] > 20000:
        w.append("对白只占 %s%%：若这部作品本该有对话，说明材料是大纲 / 设定 / 梗概而不是正文，"
                 "声纹一节会取不到台词。" % d["ratio"])
    if m["chapters"] <= 1 and m["cjk"] > 60000:
        w.append("没有识别到章节标题：附录 B（章节开篇 / 收尾句）会退化为全篇首尾。")
    if m["para_len"]["mean"] > 400:
        w.append("段落均 %s 字：材料可能是没有分段的整块文本，段落律的结论不可用。" % m["para_len"]["mean"])
    return w


def name_index(names):
    """(名字集合, 名字的全部 2-4 字片段集合)。全书统计要在几十万候选上过滤角色名，
    只能靠集合查找 —— 对名单做线性扫描会把大部头卡死。"""
    nameset = set(n for n in (names or []) if n and len(n) >= 2)
    frag = set()
    for nm in nameset:
        for n in (2, 3, 4):
            for i in range(len(nm) - n + 1):
                frag.add(nm[i:i + n])
    return nameset, frag


def ngrams(t, names=None, top=44):
    """高频 2-4 字组合：作者的偏爱词。角色名、名字构件与纯功能词组合会被剔除。"""
    names = set(n for n in (names or []) if n)
    nameset, frag = name_index(names)
    counts = {}
    for run in re.findall(r"[一-鿿]{2,}", t):
        L = len(run)
        for n in (2, 3, 4):
            for i in range(L - n + 1):
                g = run[i:i + n]
                counts[g] = counts.get(g, 0) + 1

    def bad(g):
        if g in STOP_W or g in frag:
            return True
        if all(ch in FUNC_CH for ch in g):
            return True
        # 字级滑窗会跨词边界，切出「的时」「己的」「秋水的」「出了」这类碎片。
        # 判据：首尾若是黏着性极强的虚字，这个 n-gram 就是切歪的，不是作者的用词。
        if g[0] in EDGE_BAN or g[-1] in EDGE_BAN:
            return True
        # g 蹭到了名字（「着宁秋」「秋水又来」「宁秋水的」）：查 g 的每个两字窗口
        # 是否命中名字片段集。只查「是否等于完整名字」不够 ——「秋水又来」的任何
        # 三字子串都不是「宁秋水」，却明显是名字带出来的碎片。
        for i in range(len(g) - 1):
            if g[i:i + 2] in frag:
                return True
        return g in nameset

    cand = [(g, c) for g, c in counts.items() if c >= 4 and not bad(g)]
    # 先按词频截到一个小窗口再去重。去重是 O(候选 × 已留)，不截断的话大部头有
    # 五万个候选，就是十几亿次子串比较 —— v1 实测把 176 万字的书跑成分钟级。
    # 取 top 的 12 倍足够产出稳定的榜单：被挤掉的都是词频远低于榜尾的。
    cand.sort(key=lambda kv: -kv[1])
    cand = cand[:max(400, top * 12)]
    # 再先长后短：滑窗产生的「灯影旧照 / 影旧照片 / 旧照片钟」都是同一个短语的位移，
    # 只保留最长且计数相当的那一个，否则前 20 名会被同一个词组刷满。
    cand.sort(key=lambda kv: (-len(kv[0]), -kv[1]))
    kept = []
    for g, c in cand:
        covered = False
        for kg, kc in kept:
            if g in kg and c <= kc * 1.6:       # 短词几乎只出现在长词里 → 冗余
                covered = True
                break
            if kg in g and kc <= c * 1.6:       # 反向：长词是短词的主要载体，留长的
                covered = True
                break
        if not covered:
            kept.append((g, c))
    kept.sort(key=lambda kv: -kv[1])
    return [{"w": g, "n": c} for g, c in kept[:top]]


def openers(sents, names=None, top=18):
    """句首两字的偏好：作者从哪里起句。角色名开头不算风格，剔除。"""
    _, frag = name_index(names)
    c = {}
    for s in sents:
        k = "".join(CJK.findall(s)[:2])
        if len(k) != 2 or k in STOP_W or k in frag:
            continue
        c[k] = c.get(k, 0) + 1
    return [{"w": k, "n": v} for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:top] if v >= 3]


# ---------------------------------------------------------------------------
# 二、章节 / 开篇句 / 收尾句
# ---------------------------------------------------------------------------
CH_LOOSE = re.compile(r"(第([一二三四五六七八九十百千零〇两]+|\d+)[章节回幕卷部集])[ \t　]{0,4}([^\n]{0,40})")
_CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_int(s):
    """中文数字转整数：一 / 十一 / 二十 / 一百二十 / 两百五十八。解析不了返回 None。"""
    s = str(s or "").strip()
    if s.isdigit():
        return int(s)
    section, digit = 0, 0
    for ch in s:
        if ch in _CN_DIGIT:
            digit = _CN_DIGIT[ch]
        elif ch in ("十", "百", "千"):
            section += (digit or 1) * {"十": 10, "百": 100, "千": 1000}[ch]
            digit = 0
        else:
            return None
    return (section + digit) or None


def _loose_marks(t):
    """行首锚定失败时的兜底：从正文中间捞回章节标题。

    真实材料里网页抓取的正文经常把导航文字粘在标题前面
    （「…整理校对后一页前一页回目录回首页第二回　张翼德怒鞭督邮」），于是 ^ 锚定的正则
    只认得第一回，一部一百二十回的书被算成 2 章 —— 章节体量、附录 B、钩子分型全部失效。
    判据用「回数必须单调递增」：正文里顺口提一句「第三回说过」不会形成递增长链，
    所以这条兜底不会把行文中的引用误当标题。
    """
    cands = []
    for m in CH_LOOSE.finditer(t):
        n = _cn_int(m.group(2))
        if n:
            cands.append((m.start(), m.group(1).strip() + ("　" + m.group(3).strip() if m.group(3).strip() else ""), n))
    if len(cands) < 4:
        return []
    # 取最长的单调递增子序列（贪心即可：标题在书里本来就是顺序出现的）
    keep, last = [], 0
    for pos, title, n in cands:
        if n > last:
            keep.append((pos, title))
            last = n
    return keep if len(keep) >= 4 else []


def chapters(t):
    marks = [(m.start(), m.group(1).strip()) for m in CH_HEAD.finditer(t)]
    if len(marks) < 4:
        loose = _loose_marks(t)
        if len(loose) > len(marks):
            marks = loose
    if not marks:
        return [{"title": "全篇", "at": 0, "text": t}]
    out = []
    for i, (pos, title) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(t)
        body = t[pos + len(title):end]
        if _cjk_len(body) >= 60:
            out.append({"title": title, "at": pos, "text": body})
    return out


# 作者的话 / 求票 / 请假通知：网文章末的行外话。它不是正文，却正好落在「章节收尾句」的位置上，
# 不剔掉的话钩子统计会被它带偏（实测某作品 82.8% 判成「断言收尾」，真正的章末句被挤到前一句）。
AUTHOR_NOTE = re.compile(
    r"(^\s*(PS|P\.S|ps|Ps)[：:.、]|推荐票|月票|打赏|求收藏|求订阅|求推荐|书评区|章说|请假|存稿|断更|加更|卷尾|"
    r"感谢.{0,8}(打赏|投喂|礼物|票|支持)|字数.{0,4}奉上|爆肝|奥利给|爱你们|小可爱|老爷们|各位老爷|"
    r"(本章|这一?章|下一?章|上一?章|明天|今天|昨天|今晚|明早|晚上|中午|下午|凌晨).{0,10}"
    r"(更新|一更|两更|三更|大章|补|码|写完|发出|奉上|没了|例外|字)|"
    r"(更新|码字|错字|先更后改|回笼觉|大扫除|下班|白写)|"
    r"[一二三四五六七八九十两\d]+更|"
    r"我(尽量|会|先|尽力|可能|争取).{0,12}(更|写|码|发|改|补|看一遍)|"
    r"(希望|祝).{0,6}(这本书|你们|大家)|"
    r"^\s*(继续下一章|尽力了|先更后改|睡了|晚安|抱歉|鞠躬)\s*[。！…]?\s*$)")
# 作者行外话的形态特征：短、第一人称、谈的是「写和发」而不是故事里的事。
# 只在章末从后往前剥，且最多剥 14 句 —— 万一判错也不会把整章正文吃掉。
NOTE_MAX_POP = 14


# 网页抓取残留：目录导航、扫校署名、站点广告。这些与「作者的话」不同 —— 它们连人话都不是，
# 判据毫无歧义（没有一句正文会写「回目录回首页」），所以不受长度与引号的限制。
# 实测三国演义：全部 120 回的收尾句都是「…整理校对后一页前一页回目录回首页」，
# 也就是说附录 B 里「作者怎么收手」这一栏此前一直在展示抓取导航。
SCRAPE_NAV = re.compile(r"(回目录|回首页|后一页|前一页|上一页|下一页|整理校对|扫校|校对|本书由|免费下载|"
                        r"电子书|阅读网|书城|txt|TXT|www\.|\.com|\.net|转载请|请访问|更多好书)")


def _is_note(s, nameset=None):
    if SCRAPE_NAV.search(s):
        return True
    if AUTHOR_NOTE.search(s):
        return True
    if re.search(r"[“「『]", s):        # 引号内是人物台词，不是行外话
        return False
    # 兜底一：短句 + 第一人称 + 写作发布类名词
    if _cjk_len(s) <= 40 and re.search(r"(我|你们|大家)", s) and re.search(r"(章|更|字|书|票|码|发|存稿|评论)", s):
        return True
    # 兜底二：短句 + 第一人称 + 通篇没有一个角色名。作者跟读者说话时不会提到自己笔下的人物，
    # 而正文里的第一人称叙述几乎总会带上某个人名 —— 所以这条对第一人称小说也是安全的。
    if nameset and _cjk_len(s) <= 26 and re.search(r"(我|你们|大家|咱们)", s) \
            and not any(nm in s for nm in nameset):
        return True
    return False


def prose_sents(text, nameset=None):
    """正文句序列：剔掉章末的作者行外话（「作者的话」「求票」「今天没了，就三章」）。

    这不是洁癖 —— 行外话正好落在「章节收尾句」的位置上，不剔掉的话钩子统计会被它带偏。
    实测某作品：剔掉前「断言收尾」82.8%，剔掉后 60.7%，对白收尾 8.4% → 19.5%，
    也就是说作者真实的收手方式被行外话整体掩盖了。
    刻意不剔以【】开头的行：这部书里【】是地书传讯，属于正文台词。
    """
    ss = _sentences(text)
    popped = 0
    while ss and popped < NOTE_MAX_POP and (_cjk_len(ss[-1]) < 4 or _is_note(ss[-1], nameset)):
        ss.pop()
        popped += 1
    return ss


def edge_lines(chaps, limit=30, names=None):
    """章节开篇句 / 收尾句集 —— 作者「怎么进场、怎么收手」的最集中证据"""
    if not chaps:
        return [], []
    nameset = set(n for n in (names or []) if n and 2 <= len(n) <= 6)
    step = max(1, len(chaps) // limit)
    picks = chaps[::step][:limit]
    heads, tails = [], []
    for c in picks:
        ss = prose_sents(c["text"], nameset)
        if not ss:
            continue
        h = ss[0][:90]
        tl = ss[-1][:90]
        if _cjk_len(h) >= 4:
            heads.append({"chapter": c["title"], "text": h})
        if _cjk_len(tl) >= 4:
            tails.append({"chapter": c["title"], "text": tl})
    return heads, tails


# ---------------------------------------------------------------------------
# 二·B、构思架构：确定性结构度量
#
#   文风能从 1800 字的窗口里看出来，构思不能。「一章从哪起到哪停」「伏笔埋多远才兑现」
#   「新麻烦是怎么被造出来的」只在【序列】上可见 —— 八个互不相邻的窗口里根本没有情节架构。
#   所以这一节的输入不是样本窗口，而是全书章节头尾表 + 图谱抽出的有序剧情点。
#   与文风同一条纪律：凡能算的绝不问模型，模型只能解释这些数字，不得改写。
# ---------------------------------------------------------------------------
HOOK_TAIL = ["疑问收尾", "悬停收尾", "感叹收尾", "对白收尾", "动作收尾", "断言收尾"]
HOOK_HEAD = ["时间开场", "对白开场", "人物开场", "场景开场"]
_CH_NUM = re.compile(r"第([0-9]+|[一二三四五六七八九十百千零〇两]+)[章节回幕卷部集]")


def _tail_kind(s):
    t = s.strip()
    if not t:
        return "断言收尾"
    if t.endswith(("？", "?", "？”", "？」", "?”")):
        return "疑问收尾"
    if t.endswith(("…", "……", "—", "——", "…”", "……”", "……」")):
        return "悬停收尾"
    if t.endswith(("！", "!", "！”", "！」", "!”")):
        return "感叹收尾"
    if t.endswith(("”", "」", "』")):
        return "对白收尾"
    if MOTION.search(t):
        return "动作收尾"
    return "断言收尾"


def _head_kind(s, nameset):
    t = s.strip()
    if t[:1] in ("“", "「", "『"):
        return "对白开场"
    if TIME_MARK.search(t[:14]):
        return "时间开场"
    lead = t[:6]
    if lead[:1] in ("他", "她", "我", "它") or any(nm and t.startswith(nm) for nm in nameset):
        return "人物开场"
    return "场景开场"


def hook_stats(chaps, names=None, limit=400):
    """章首 / 章末的确定性分型 —— 作者「怎么进场、怎么收手」的硬指标。

    这一步不问模型：钩子类型可以由句末标点与句首成分直接判定，而模型在这里最容易
    凭印象说「善用悬念」。有了这张表，构思阶段的结论就必须与它对齐，说不通就是说错了。
    """
    nameset = set(n for n in (names or []) if n and 2 <= len(n) <= 6)
    if not chaps or (len(chaps) == 1 and chaps[0].get("title") == "全篇"):
        return {}
    picks = chaps[:limit] if len(chaps) <= limit else chaps[::max(1, len(chaps) // limit)][:limit]
    tails, heads = {}, {}
    ex_t, ex_h = {}, {}
    for c in picks:
        ss = prose_sents(c["text"], nameset)
        if not ss:
            continue
        h, tl = ss[0], ss[-1]
        if _cjk_len(tl) >= 4:
            k = _tail_kind(tl)
            tails[k] = tails.get(k, 0) + 1
            ex_t.setdefault(k, []).append({"chapter": c["title"], "text": tl[:80]})
        if _cjk_len(h) >= 4:
            k = _head_kind(h, nameset)
            heads[k] = heads.get(k, 0) + 1
            ex_h.setdefault(k, []).append({"chapter": c["title"], "text": h[:80]})
    nt, nh = sum(tails.values()), sum(heads.values())
    return {
        "sampled": len(picks),
        "tail": [{"kind": k, "n": tails.get(k, 0), "pct": _pct(tails.get(k, 0), nt)}
                 for k in HOOK_TAIL if tails.get(k)],
        "head": [{"kind": k, "n": heads.get(k, 0), "pct": _pct(heads.get(k, 0), nh)}
                 for k in HOOK_HEAD if heads.get(k)],
        "tail_ex": dict((k, v[:3]) for k, v in ex_t.items()),
        "head_ex": dict((k, v[:3]) for k, v in ex_h.items()),
    }


def _ev_list(graph):
    """图谱剧情点的书序序列。抽取是按块顺序推进的，所以 list 序就是书序；
    章内再按 order 稳定排一次，避免同章两点颠倒。"""
    ev = [e for e in ((graph or {}).get("events") or []) if isinstance(e, dict) and (e.get("title") or e.get("summary"))]
    if not ev:
        return []
    seen, chapter_at = [], {}
    for i, e in enumerate(ev):
        ch = str(e.get("chapter") or "未分章")
        if ch not in chapter_at:
            chapter_at[ch] = len(chapter_at)
        seen.append((chapter_at[ch], _num_or(e.get("order"), i), i, e))
    seen.sort(key=lambda x: (x[0], x[1], x[2]))
    return [x[3] for x in seen]


def _num_or(v, d=0):
    try:
        return int(v)
    except Exception:
        return d


def arch_metrics(graph, names=None, bands=10):
    """从有序剧情点算出构思硬指标。没有图谱就返回 {} —— 构思阶段随之退化为只看章节头尾，
    并在文档里明说这一节的证据基础较弱，而不是让模型凭空编一套情节法。"""
    ev = _ev_list(graph)
    if not ev:
        return {}
    n = len(ev)
    kinds = [str(e.get("kind") or "其他") for e in ev]
    dist = {}
    for k in kinds:
        dist[k] = dist.get(k, 0) + 1
    # 类型转移：作者推进情节的语法 —— 冲突之后接转折还是接日常，是可复用的构思规则
    bi = {}
    for a, b in zip(kinds, kinds[1:]):
        bi[(a, b)] = bi.get((a, b), 0) + 1

    per_ch = {}
    for e in ev:
        c = str(e.get("chapter") or "未分章")
        per_ch[c] = per_ch.get(c, 0) + 1
    dens = sorted(per_ch.values())

    csize = sorted(len([x for x in (e.get("characters") or []) if x]) for e in ev)
    solo = sum(1 for x in csize if x <= 1)
    crowd = sum(1 for x in csize if x >= 3)

    # 分带节奏曲线：把全书切成等宽段，看每段的类型配比 —— 升级阶梯是否真的递增
    curve = []
    step = max(1, n // bands)
    for b in range(bands):
        lo, hi = b * step, (b + 1) * step if b < bands - 1 else n
        seg = kinds[lo:hi]
        if not seg:
            continue
        sd = {}
        for k in seg:
            sd[k] = sd.get(k, 0) + 1
        curve.append({"band": "%d-%d%%" % (round(100.0 * lo / n), round(100.0 * hi / n)), "n": len(seg),
                      "top": sorted(sd.items(), key=lambda kv: -kv[1])[:3]})

    chars = [c for c in ((graph or {}).get("characters") or []) if isinstance(c, dict) and c.get("name")]
    imp = dict((c["name"], _num_or(c.get("importance"), 0)) for c in chars)
    majors = [nm for nm, v in imp.items() if v >= 60]
    first_at = {}
    for i, e in enumerate(ev):
        for nm in (e.get("characters") or []):
            if nm in imp and nm not in first_at:
                first_at[nm] = i
    intro = []
    for q in (10, 25, 50):
        c = sum(1 for nm in majors if first_at.get(nm, n) < n * q / 100.0)
        intro.append({"by": "%d%%" % q, "majors": c, "pct": _pct(c, len(majors))})

    lead = max(imp.items(), key=lambda kv: kv[1])[0] if imp else ""
    lead_on = sum(1 for e in ev if lead and lead in (e.get("characters") or []))

    rels = [r for r in ((graph or {}).get("relations") or []) if isinstance(r, dict)]
    hidden = sum(1 for r in rels if str(r.get("line") or "") == "暗线")
    rk = {}
    for r in rels:
        k = str(r.get("kind") or "其他")
        rk[k] = rk.get(k, 0) + 1

    camps = [c for c in ((graph or {}).get("camps") or []) if isinstance(c, dict)]
    st = {}
    for c in camps:
        s = str(c.get("stance") or "其他")
        st[s] = st.get(s, 0) + 1

    return {
        "events": n, "chapters_with_events": len(per_ch),
        "kind_dist": sorted(dist.items(), key=lambda kv: -kv[1]),
        "kind_bigrams": [{"from": a, "to": b, "n": v, "pct": _pct(v, max(1, n - 1))}
                         for (a, b), v in sorted(bi.items(), key=lambda kv: -kv[1])[:14]],
        "per_chapter": {"mean": round(1.0 * n / max(1, len(per_ch)), 2), "median": _quantile(dens, .50),
                        "p90": _quantile(dens, .90), "max": dens[-1] if dens else 0},
        "cast_per_event": {"mean": round(sum(csize) / max(1, len(csize)), 2),
                           "solo_ratio": _pct(solo, len(csize)), "crowd_ratio": _pct(crowd, len(csize))},
        "curve": curve,
        "cast": {"total": len(chars), "majors": len(majors), "intro": intro,
                 "lead": lead, "lead_on_stage": _pct(lead_on, n)},
        "relations": {"total": len(rels), "hidden": hidden, "hidden_ratio": _pct(hidden, len(rels)),
                      "kinds": sorted(rk.items(), key=lambda kv: -kv[1])[:10]},
        "camps": {"total": len(camps), "stance": sorted(st.items(), key=lambda kv: -kv[1])},
    }


def event_track(graph, windows=13, run=8):
    """按位置分带取【连续】的剧情点段落。

    刻意不取散点：升级、伏笔兑现、反转都只在相邻若干点之间可见，
    散着取一百个点只能看出「这本书有冲突也有转折」，看不出它是怎么被推起来的。
    """
    ev = _ev_list(graph)
    if not ev:
        return []
    n = len(ev)
    run = max(3, min(run, max(3, n // max(1, windows))))
    out, used = [], set()
    for w in range(windows):
        lo = int(round(1.0 * w * max(0, n - run) / max(1, windows - 1))) if windows > 1 else 0
        lo = max(0, min(lo, max(0, n - run)))
        if lo in used:
            continue
        used.add(lo)
        seg = ev[lo:lo + run]
        out.append({"pos": "%d%%" % round(100.0 * lo / max(1, n)),
                    "chapter": str(seg[0].get("chapter") or ""),
                    "items": [{"kind": str(e.get("kind") or ""), "title": str(e.get("title") or "")[:40],
                               "summary": str(e.get("summary") or "")[:120],
                               "cast": [x for x in (e.get("characters") or [])][:5]} for e in seg]})
    return out


def arch_titles(graph, chaps):
    """构思阶段允许引用的结构事实白名单：真实章节名 + 真实剧情点名。
    结构结论没有「原文句子」可引，但也不能因此免于核验 —— 它必须指认得出真实的章或点。"""
    ok = set()
    for c in (chaps or []):
        t = str(c.get("title") or "").strip()
        if t:
            ok.add(_norm(t))
    for e in _ev_list(graph):
        for f in ("title", "chapter"):
            t = str(e.get(f) or "").strip()
            if t:
                ok.add(_norm(t))
    return ok


# ---------------------------------------------------------------------------
# 三、样本浸泡取样：按场景类型挑真实原文
# ---------------------------------------------------------------------------
SOAK_KINDS = ["开篇", "对白场", "动作场", "描写场", "内心场", "情绪高点", "转场", "收束"]


def _win_score(kind, w, m):
    """给定窗口对某类场景的贴合度。全部基于本地可算特征，不猜。"""
    q = m["qratio"]
    if kind == "对白场":
        return q * 2.0 + min(1.0, m["qcount"] / 12.0)
    if kind == "动作场":
        return m["motion"] * 1.6 + m["short"] * 1.2 - q * 1.4
    if kind == "描写场":
        return m["long"] * 1.5 + m["sense"] * 1.2 - q * 2.0
    if kind == "内心场":
        return m["thought"] * 2.2 - q * 1.0
    if kind == "情绪高点":
        return m["emo"] * 1.8 + q * 0.5
    if kind == "转场":
        return m["time"] * 2.4 - q * 0.6
    return 0.0


def _win_metrics(w):
    n = max(1, _cjk_len(w))
    qs = QUOTE_RE.findall(w)
    ss = _sentences(w)
    sl = [_cjk_len(s) for s in ss] or [0]
    return {
        "qratio": min(1.0, sum(_cjk_len(x) for x in qs) / float(n)),
        "qcount": len(qs),
        "short": sum(1 for x in sl if x <= 8) / float(len(sl)),
        "long": sum(1 for x in sl if x >= 34) / float(len(sl)),
        "sense": min(1.0, sum(w.count(c) for chars in SENSE.values() for c in chars) / (n / 90.0 + 1)),
        "thought": min(1.0, len(THOUGHT.findall(w)) / (n / 420.0 + 1)),
        "motion": min(1.0, len(MOTION.findall(w)) / (n / 220.0 + 1)),
        "emo": min(1.0, len(EMO_MARK.findall(w)) / (n / 110.0 + 1)),
        "time": min(1.0, len(TIME_MARK.findall(w)) / (n / 700.0 + 1)),
    }


def sample_count(n_cjk):
    if n_cjk < 30000:
        return 6
    if n_cjk < 200000:
        return 10
    if n_cjk < 900000:
        return 14
    return 18


def samples(text, want=None, size=1800):
    """挑 want 段真实原文，覆盖 SOAK_KINDS 各类场景，并在全书位置上分散。"""
    t = strip_heads(text)
    n = _cjk_len(t)
    want = want or sample_count(n)
    chaps = chapters(t)

    # 段落对齐的窗口，步长半窗，避免切在句子中间
    wins = []
    paras = _paras(t)
    buf, start_i = [], 0
    acc = 0
    for i, p in enumerate(paras):
        buf.append(p)
        acc += _cjk_len(p)
        if acc >= size:
            wins.append({"i": start_i, "text": "\n".join(buf)})
            half, k = acc // 2, 0
            while buf and k < half:
                k += _cjk_len(buf[0]); buf.pop(0); start_i += 1
            acc = sum(_cjk_len(x) for x in buf)
    if buf and _cjk_len("\n".join(buf)) >= size * 0.5:
        wins.append({"i": start_i, "text": "\n".join(buf)})
    if not wins:
        wins = [{"i": 0, "text": t[:size]}]

    total_p = max(1, len(paras))
    for w in wins:
        w["pos"] = _pct(w["i"], total_p, 0)
        w["m"] = _win_metrics(w["text"])
        w["chapter"] = _chapter_of(chaps, t, w["text"])

    picked, used = [], set()

    def take(kind, w):
        if not w or w["i"] in used:
            return False
        used.add(w["i"])
        picked.append({"kind": kind, "pos": w["pos"], "chapter": w["chapter"], "text": w["text"].strip()})
        return True

    # 位置分带取样：把全书切成 want 条等宽位置带，每带出一段。
    # 早期版本用「离已选样本越远越加分」的软惩罚，实测在 176 万字的书上仍会把
    # 三段挤在 86-99%（末尾的高分窗口把中段挤掉了）。分带是硬约束，位置覆盖不会再塌。
    take("开篇", wins[0])
    tail = wins[-1] if len(wins) > 1 else None
    mid_bands = max(1, want - (2 if tail else 1))
    kinds = [k for k in SOAK_KINDS if k not in ("开篇", "收束")]
    used_kind = {}
    lo_i, hi_i = (1, len(wins) - 1) if tail else (1, len(wins))
    span = max(1, hi_i - lo_i)
    for b in range(mid_bands):
        a = lo_i + int(round(span * b / float(mid_bands)))
        z = lo_i + int(round(span * (b + 1) / float(mid_bands)))
        band = [w for w in wins[a:max(z, a + 1)] if w["i"] not in used]
        if not band:
            continue
        best, bk, bs = None, None, -9e9
        for kind in kinds:
            # 未用过的类型给一档加分：保证类型覆盖，但不牺牲位置覆盖
            bonus = 0.6 if not used_kind.get(kind) else -0.34 * used_kind[kind]
            for w in band:
                s = _win_score(kind, w["text"], w["m"]) + bonus
                if s > bs:
                    best, bk, bs = w, kind, s
        if take(bk, best):
            used_kind[bk] = used_kind.get(bk, 0) + 1
    if tail:
        take("收束", tail)
    picked.sort(key=lambda x: x["pos"])
    for i, p in enumerate(picked):
        p["id"] = "S%d" % (i + 1)
    return picked


def _chapter_of(chaps, t, frag):
    head = frag.strip()[:40]
    at = t.find(head)
    if at < 0:
        return chaps[0]["title"] if chaps else "未分章"
    cur = chaps[0]["title"] if chaps else "未分章"
    for c in chaps:
        if c["at"] <= at:
            cur = c["title"]
        else:
            break
    return cur


# ---------------------------------------------------------------------------
# 四、角色对白抽取（声纹的原始素材）
# ---------------------------------------------------------------------------
def dialogue_by_role(text, names, per=14, roles=14):
    t = strip_heads(text)
    names = [n for n in (names or []) if n and len(n) >= 2]
    if not names:
        names = _guess_names(t)
    bag = dict((n, []) for n in names)
    tally = {}
    # 名字并成一个正则，一次扫过窗口即可定位说话人。
    # 对每条引文遍历名单是 O(引文×名单)：3.5 万条 × 365 名 实测把大部头卡住。
    order = sorted(names, key=lambda x: -len(x))        # 长名优先，避免「张三」被「张」抢走
    NAME_RE = re.compile("|".join(re.escape(n) for n in order)) if order else None
    if not NAME_RE:
        return []
    for m in QUOTE_RE.finditer(t):
        line = m.group(1).strip()
        if _cjk_len(line) < 3 or _cjk_len(line) > 80:
            continue
        before = t[max(0, m.start() - 34):m.start()]
        after = t[m.end():m.end() + 34]
        best, bd = None, 99
        hits = list(NAME_RE.finditer(before))
        if hits:                                        # 引号前最靠近的名字
            h = hits[-1]
            best, bd = h.group(0), len(before) - h.start()
        h2 = NAME_RE.search(after)                      # 引号后第一个名字（「……」张三说）
        if h2 and (h2.start() + 1) < bd:
            best, bd = h2.group(0), h2.start() + 1
        if not best:
            continue
        # 总量单独计：bag 只留到上限，若拿 len(bag) 当「全书台词数」，
        # 所有角色都会显示成同一个上限值（42），那个数字就成了假的
        tally[best] = tally.get(best, 0) + 1
        if len(bag[best]) < per * 4:
            bag[best].append(line)
    out = []
    for n in sorted(bag, key=lambda k: -tally.get(k, 0)):
        if tally.get(n, 0) >= 3:
            # 取长度分布上分散的样本，而不是连续的前 N 句
            ls = sorted(bag[n], key=_cjk_len)
            step = max(1, len(ls) // per)
            out.append({"name": n, "n": tally[n], "lines": ls[::step][:per]})
        if len(out) >= roles:
            break
    return out


def _guess_names(t, top=14):
    """没有图谱时的兜底：找「X说 / X道」里反复出现的 2-3 字人名候选"""
    c = {}
    for m in re.finditer(r"([一-鿿]{2,3})(说道|说|道|问道|问|喊道|笑道|叹道)", t):
        w = m.group(1)
        if w in STOP_W or any(ch in FUNC_CH for ch in w):
            continue
        c[w] = c.get(w, 0) + 1
    return [w for w, n in sorted(c.items(), key=lambda kv: -kv[1])[:top] if n >= 4]


# ---------------------------------------------------------------------------
# 五、提示词（本引擎的核心资产）
# ---------------------------------------------------------------------------
DISTILL_SYSTEM = (
    "你是文风蒸馏引擎。你面前是一位作者的真实作品原文。"
    "你的任务不是评论、不是赞美、不是概括情节，而是把这位作者的写法拆成【另一个写作者可以逐条执行的指令】。\n"
    "铁律：\n"
    "1) 只依据给定原文。不假设作者的生平、性别、流派、年代、其他作品，也不套用任何题材套话；\n"
    "2) 每条结论必须挂一句原文逐字引证（可截断，不可改写、不可拼接、不可翻译、不可补字）。找不到原句就不要这条结论；\n"
    "3) 禁止把无法执行的形容词当结论：生动、细腻、优美、深刻、大气、有张力、引人入胜、节奏明快、笔触老练——"
    "这类词出现即视为未完成任务。结论必须写成动作指令：写什么 · 放在哪 · 用什么句式 · 多长 · 后面接什么；\n"
    "4) 每条结论都要能被反证：同时写出这位作者【不会这样写】的具体反例，反例要具体到句式，不是「不会写得很差」；\n"
    "5) 宁少勿滥。材料不支持的维度输出空数组，不要凑数、不要泛泛而谈；\n"
    "6) 硬数字由程序统计给出（句长、标点、对白占比、四字短句率等）。你不得改写这些数字，"
    "只能解释它们造成的读感，以及要复现这些数字该怎么写；\n"
    "7) 蒸馏的是【写法】，不是【内容】。不要把这部作品的人名、地名、专有设定写进通用规则里"
    "（声纹表除外，那里本来就按角色分条）。\n"
    "输出中文。"
)

SOAK_PROMPT = (
    "下面是这位作者原文中的 {k} 段真实样本，已标注编号 / 场景类型 / 全书位置 / 所属章节。\n"
    "请对【每一段】做样本浸泡式拆解——不要概括情节，逐句看这一段是【怎么被写出来的】。\n\n"
    "每段输出：\n"
    "· id：照抄样本编号；\n"
    "· moves：4-7 条这一段用到的具体写法。每条 = do（做法，写到可执行的粒度）+ where（放在段落/句子的什么位置）"
    "+ effect（对读者造成什么）+ quote（原文逐字引证）。\n"
    "  合格示例：do=「对白前不写『他说』，先给一个手部小动作，再直接进引号」；"
    "do=「情绪最高点不写情绪词，改写一个物件的特写」；do=「长句连铺三层后用一个四字短句砸停」；"
    "do=「转场只给时间词加一个天气细节，不交代人物移动过程」。\n"
    "  不合格示例：do=「描写细腻」「节奏很好」「人物刻画到位」——这些不是做法。\n"
    "· syntax：这一段的句法特征（句长起伏方式、并列还是从属、语序倒装、省略主语、标点如何断气），附 quote；\n"
    "· diction：用词层级（书面 / 口语 / 方言 / 行话 / 粗俗 / 混用）与本段的偏爱词，附 quote；\n"
    "· sensory：动用了哪些感官、以什么比例、有没有刻意不用的感官，附 quote；\n"
    "· avoid：这一段能证明作者【不会】做的 1-3 件事，具体到句式；\n"
    "· imitable：1-2 条可直接搬用的句式模板。把具体名词换成占位符，"
    "如「<角色>把<物件>放回<位置>，没有看<对方>」「<时间词>，<地点>还是<状态>」。\n\n"
    "=== 样本开始 ===\n{samples}\n=== 样本结束 ==="
)

CODEX_PROMPT = (
    "以下是（A）程序对这部作品全文的硬性统计，（B）多段真实样本的浸泡拆解结果，（C）章节开篇句与收尾句集。\n"
    "请归纳出这位作者的【文风 · 语感 · 风格】总法典。要求每条都能被另一个写作者直接执行，且与硬统计不矛盾。\n\n"
    "输出：\n"
    "· voice_summary：一句话总纲（≤60 字），写清「这位作者写东西时最核心的一个选择是什么」，不要形容词堆砌；\n"
    "· prose：6-12 条句法律。rule 写成可执行指令（含长度、位置、句式），why 说明它造成什么读感，quote 原文引证。"
    "必须至少覆盖：长短句如何交替、什么时候断句、修饰语放前还是放后、主语省略的条件；\n"
    "· rhythm：5-10 条语感与节奏律。要能解释硬统计里的句长分布与四字短句率是怎么写出来的；\n"
    "· diction：{{register 语域一句话, prefer 偏爱的 8-16 个词/词族并说明使用场合, avoid 这位作者明显不用的 6-12 类词}}；\n"
    "· imagery：4-10 个反复出现的意象/母题。motif 是具体物象或场景，meaning 是它在文中承担什么，附 quote；\n"
    "· pov：{{person 人称, tense 时间处理, distance 叙述距离（贴着人物想 / 冷眼旁观 / 全知）, note 一句该怎么保持, quote}}；\n"
    "· scene：5-10 条场景处理律：怎么进场、怎么给环境、怎么出场、怎么转场、一场戏多长；\n"
    "· dialogue：5-10 条对白律：对话标签怎么用（要与统计里的标签偏好一致）、"
    "有没有动作插入、对白平均多长、允不允许长篇发言、怎么写沉默与打断；\n"
    "· templates：8-16 条可直接搬用的句式模板（含占位符）；\n"
    "· counter：8-16 条【这位作者不会这样写】的具体反例。\n\n"
    "=== A 硬性统计 ===\n{metrics}\n\n=== B 样本浸泡拆解 ===\n{soak}\n\n=== C 章节开篇 / 收尾句 ===\n{edges}\n=== 结束 ==="
)

MIND_PROMPT = (
    "以下是这部作品的真实样本浸泡拆解、结构数据（章节数 / 剧情点类型分布 / 阵营 / 角色重要度）与文风法典。\n"
    "请蒸馏这位作者的【思维方式 · 喜好 · 禁忌】——即「他在动笔前是怎么想的」，不是「他写了什么故事」。\n"
    "每条都要挂证据（原文引句或可指认的结构事实），不许写星座运势式的空话。\n\n"
    "输出：\n"
    "· worldview：4-8 条作者关于人 / 世界的隐含判断（他默认什么是真的）。claim + evidence；\n"
    "· causality：3-6 条因果观：在这部书里事情【为什么】会发生（性格 / 制度 / 巧合 / 报应 / 无因）。"
    "这决定了模仿者该怎么安排情节；\n"
    "· structure：4-8 条结构偏好：一章从哪起到哪停、悬念放在哪、多少章一个大转折、单元剧还是长线；\n"
    "· information：4-8 条信息投放律：伏笔怎么埋、什么时候揭、读者比人物知道得多还是少、"
    "有没有故意不解释的东西；\n"
    "· morals：3-6 条道德立场：谁会被作者惩罚、谁被容忍、什么行为在这部书里是不可饶恕的；\n"
    "· likes：6-14 条明显偏爱（反复写的场景 / 人物类型 / 器物 / 天气 / 身体细节 / 名字取法）；\n"
    "· taboos：4-10 条明显回避（不写什么、写到就绕开、绝不直写的东西）。这一条对模仿最关键；\n"
    "· obsessions：3-8 条执念：反复回到的问题或画面，作者好像在跟它较劲；\n"
    "· decisions：4-8 条【岔路口决策倾向】——这是作者思维最可执行的形态。"
    "写成「遇到 X 局面时，这位作者会选 Y，而不是 Z」。"
    "合格示例：「主角吃亏时，他选当场记下、事后借第三方还手，而不是当场翻脸」；"
    "「秘密快藏不住时，他选主动交出一半，而不是死守到被揭穿」；"
    "「配角犯错时，他选让配角自己承担后果，而不是主角赶来救场」。"
    "每条 = claim（含 X / Y / Z 三段）+ evidence；\n"
    "· reader_contract：一段话（≤120 字）写清作者与读者的默契：读者被许诺了什么，又被禁止期待什么。\n\n"
    "=== 结构数据 ===\n{struct}\n\n=== 文风法典 ===\n{codex}\n\n=== 样本浸泡拆解 ===\n{soak}\n=== 结束 ==="
)

ARCH_PROMPT = (
    "以下是（A）程序对这部作品【结构】的硬性度量，（B）章节收尾 / 开篇的分型统计与真实例句，"
    "（C）按全书位置分带取出的【连续】剧情点序列，（D）文风法典摘要。\n"
    "请蒸馏这位作者的【构思能力】——不是他写了什么故事，而是【他是怎么把故事造出来的】："
    "麻烦从哪来、怎么把小事做大、伏笔埋多远、一章从哪起到哪停、反转靠什么支撑。\n"
    "唯一的验收标准：另一个写作者拿到你这份东西，能用自己的题材、自己的人物，"
    "造出一条这位作者会造的情节线。所以每条都必须是【可执行的动作】，不是评语。\n\n"
    "铁律（违反即视为未完成）：\n"
    "· 不许出现「情节紧凑」「层层递进」「引人入胜」「节奏张弛有度」这类无法执行的评语；\n"
    "· 每条都要挂 fact：指认真实的章名或剧情点名（照抄 C / B 里给的名字，不要自己编）。"
    "指认不出来就不要写这条；\n"
    "· 结论必须与 A 的数字一致。若 A 显示每章平均 3.3 个剧情点，你就不能说「一章只推进一件事」；"
    "若 B 显示 65% 的章节是断言收尾，你就不能说「每章都留悬念」；\n"
    "· 蒸馏机制，不是复述剧情。不要把这部书的人名、地名、金手指写进通用规则里，"
    "写成「<主角>」「<对手>」「<禁忌之物>」这样的占位符。\n\n"
    "输出：\n"
    "· engine：3-6 条【情节生成引擎】——这位作者的新麻烦是怎么被造出来的"
    "（外部势力找上门 / 主角主动伸手 / 旧账到期 / 信息泄露 / 制度逼迫 / 亲人牵连…）。"
    "每条 = rule（可执行：什么时候用、怎么起手、第一步写什么）+ why + fact。"
    "这是模仿者能不能【自己造情节】的关键，写得最具体；\n"
    "· escalation：4-8 条【升级阶梯】——小事怎么被做大。要写清每一级换了什么（对手级别 / "
    "牵连范围 / 代价 / 时限），以及一级大概占多少章；\n"
    "· setups：3-6 条【伏笔与兑现】——什么东西会被提前埋、埋的时候写多少字、隔多远兑现、"
    "兑现时怎么回扣（明说还是不提）；\n"
    "· hooks：5-10 条【章节钩子谱】——必须与 B 的分型比例一致：哪种收尾占大头、"
    "什么情形下才用疑问 / 悬停收尾、开篇怎么接上一章的尾；\n"
    "· reversal：3-6 条【反转机制】——反转靠什么成立（早埋的信息 / 视角盲区 / 对手也有计划 / "
    "读者被误导），以及反转前一定要先做的铺垫动作；\n"
    "· suspense：3-6 条【信息差管理】——读者比人物多知道还是少知道、什么时候故意让读者先知道、"
    "有没有从不解释的东西；\n"
    "· subplot：3-6 条【副线编织】——副线什么时候插入、插多长、怎么并回主线；\n"
    "· cast_use：3-6 条【角色调度】——要与 A 里的群戏率 / 主角在场率 / 主要角色引入速度一致："
    "一场戏摆几个人、配角什么时候被换下、新角色在什么节点才允许出场；\n"
    "· chapter_build：8-14 步【章节施工单】。这是整份文档最重要的一节："
    "从「我有一个点子」到「一章成稿」的可执行流程，按顺序写，每步 = step（做什么，含大致字数 / "
    "位置）+ why + fact。要能被照着做，而不是被读一遍；\n"
    "· arc_build：5-10 步【长线施工单】——一个单元（十来章）怎么搭：从哪起、中段放什么、"
    "怎么收、收完留什么给下一个单元；\n"
    "· open_end：{{opening 全书 / 单元开头法（第一页必须交代什么、绝不交代什么）, "
    "ending 收束法（怎么落幕、留不留余味）}}；\n"
    "· pace_curve：一句话（≤80 字）写清全书的节奏纲，要能解释 A 的分带曲线。\n\n"
    "=== A 结构硬度量 ===\n{arch}\n\n=== B 章节收尾 / 开篇分型 ===\n{hooks}\n\n"
    "=== C 连续剧情点序列 ===\n{track}\n\n=== D 文风法典摘要 ===\n{codex}\n=== 结束 ==="
)

# 保真回测：让模型分别在【有蒸馏提示词】和【无提示词】两种条件下写同一个场景，
# 再用同一套确定性度量去比。这是本引擎里唯一能回答「到底蒸出来了没有」的东西 ——
# 其余一切都只是「看起来像」。场景刻意与原著无关，防止模型直接背诵原文蒙分。
FID_SCENES = (
    "场景一（叙述 / 描写为主，700 字以上）：一个人在夜里回到空着的住处，"
    "发现桌上多了一件不属于自己的东西。写他从进门到确认这件东西的全过程。\n"
    "场景二（对白为主，700 字以上）：两个人在下雨的屋檐下谈一桩旧事，"
    "其中一方在隐瞒。写这段对话。\n"
    "两段都要写够字数 —— 太短的话密度类指标没法统计，这次回测就白跑了。"
)
FID_PROMPT = (
    "你现在是一位写作者。下面是一份【文风指令书】，它蒸馏自某位作者的真实作品。\n"
    "请严格按它写两段中文小说。不要解释、不要说明、不要写标题，只交小说正文。\n"
    "不要使用指令书里出现过的人名地名，用你自己的普通人物。\n\n{brief}\n\n"
    "=== 文风指令书开始 ===\n{book}\n=== 文风指令书结束 ==="
)
FID_CTRL_PROMPT = (
    "请写两段中文小说。不要解释、不要说明、不要写标题，只交小说正文。\n\n{brief}"
)

VOICE_PROMPT = (
    "以下是（A）叙述部分的真实样本，（B）按角色归好的真实对白台词（每句都逐字来自原文）。\n"
    "请蒸馏【声纹】——让模仿者写出的每句台词都能被认出是谁在说。\n"
    "禁止用「幽默」「毒舌」「温柔」一类标签交差；声纹必须是可执行的语言特征。\n\n"
    "输出：\n"
    "· narrator：叙述者声纹 {{stance 站位（贴谁 / 不贴谁）, lexicon 用词层级, "
    "tells 3-6 条可辨识的语言习惯（句式、口气、评论介入程度）, quote 引证}}；\n"
    "· characters：每个角色一条 {{name（与输入逐字一致）, register 语域（文白 / 粗俗 / 行话 / 方言色彩）, "
    "sentence 句长与句式习惯（含平均多少字、爱不爱用问句 / 短句 / 长辩）, "
    "tells 3-6 条口头标记（口头禅、称呼别人的方式、语气词、爱用的动词、回避的话题）, "
    "address 他怎么称呼别人 / 别人怎么称呼他, taboo 他不会说的话（很重要）, "
    "quotes 2-4 句最能代表他的原文台词（逐字照抄输入）}}。\n"
    "输入里给了多少角色就输出多少个，一个不漏，不要合并。\n\n"
    "=== A 叙述样本 ===\n{narr}\n\n=== B 角色台词 ===\n{lines}\n=== 结束 ==="
)

GUARD_PROMPT = (
    "以下是这位作者的硬性统计、文风法典与禁忌表。现在换一个身份：你是审稿人。\n"
    "一个通用大模型被要求「模仿这位作者写一段」，它几乎必然会写歪。请预先列出它会怎么歪，以及怎么掰回来。\n"
    "要针对【这一位作者的具体数字与禁忌】，不要写放之四海皆准的 AI 写作通病。\n\n"
    "输出：\n"
    "· pitfalls：10-18 条。ai_habit = 通用模型会不自觉做的事（要具体，如「每段都以人物情绪结句」"
    "「凡对白必配『他缓缓说道』」「把四字成语当高级感堆在描写里」）；why_wrong = 为什么违背这位作者"
    "（要引用统计数字或法典条目，如「本作对白标签 87% 是单字『道』，几乎不用『缓缓说道』」）；"
    "fix = 改成什么（可执行）；\n"
    "· checklist：8-16 条交付前自检项，每条都是可判定的是非题，写成命令句"
    "（如「数一遍：这一段里有没有出现『仿佛』『似乎』超过 1 次？超过就删」）。\n\n"
    "=== 硬性统计 ===\n{metrics}\n\n=== 文风法典 ===\n{codex}\n\n=== 禁忌与偏爱 ===\n{mind}\n=== 结束 ==="
)

# ---------------------------------------------------------------------------
# 六、Schema
# ---------------------------------------------------------------------------
def _arr(item, req=None):
    return {"type": "array", "items": item}


def _obj(props, req=None):
    return {"type": "object", "properties": props, "required": req or list(props.keys()), "additionalProperties": False}


S = {"type": "string"}
SA = {"type": "array", "items": S}

SOAK_SCHEMA = _obj({"samples": _arr(_obj({
    "id": S,
    "moves": _arr(_obj({"do": S, "where": S, "effect": S, "quote": S})),
    "syntax": S, "diction": S, "sensory": S,
    "avoid": SA, "imitable": SA,
}))}, ["samples"])

RULE = _obj({"rule": S, "why": S, "quote": S})
CODEX_SCHEMA = _obj({
    "voice_summary": S,
    "prose": _arr(RULE), "rhythm": _arr(RULE), "scene": _arr(RULE), "dialogue": _arr(RULE),
    "diction": _obj({"register": S, "prefer": SA, "avoid": SA}),
    "imagery": _arr(_obj({"motif": S, "meaning": S, "quote": S})),
    "pov": _obj({"person": S, "tense": S, "distance": S, "note": S, "quote": S}),
    "templates": SA, "counter": SA,
})

CLAIM = _obj({"claim": S, "evidence": S})
ITEM = _obj({"item": S, "note": S})
MIND_SCHEMA = _obj({
    "worldview": _arr(CLAIM), "causality": _arr(CLAIM), "structure": _arr(CLAIM), "information": _arr(CLAIM),
    "morals": _arr(CLAIM), "likes": _arr(ITEM), "taboos": _arr(ITEM), "obsessions": _arr(ITEM),
    "decisions": _arr(CLAIM), "reader_contract": S,
})

# 构思：结构结论没有「原文句子」可引，但也不能免于核验 —— 它必须指认得出真实的章或剧情点，
# 所以这里的证据字段叫 fact（对白名单核验），与 quote / evidence（逐字核验）分开。
ARULE = _obj({"rule": S, "why": S, "fact": S})
ASTEP = _obj({"step": S, "why": S, "fact": S})
ARCH_SCHEMA = _obj({
    "engine": _arr(ARULE), "escalation": _arr(ARULE), "setups": _arr(ARULE), "hooks": _arr(ARULE),
    "reversal": _arr(ARULE), "suspense": _arr(ARULE), "subplot": _arr(ARULE), "cast_use": _arr(ARULE),
    "chapter_build": _arr(ASTEP), "arc_build": _arr(ASTEP),
    "open_end": _obj({"opening": S, "ending": S}),
    "pace_curve": S,
})

FID_SCHEMA = _obj({"narration": S, "dialogue": S})

VOICE_SCHEMA = _obj({
    "narrator": _obj({"stance": S, "lexicon": S, "tells": SA, "quote": S}),
    "characters": _arr(_obj({"name": S, "register": S, "sentence": S, "tells": SA,
                             "address": S, "taboo": S, "quotes": SA})),
})

GUARD_SCHEMA = _obj({
    "pitfalls": _arr(_obj({"ai_habit": S, "why_wrong": S, "fix": S})),
    "checklist": SA,
})


# ---------------------------------------------------------------------------
# 七、引证回查：模型改写过的「原文」一律剔除
# ---------------------------------------------------------------------------
def _norm(s):
    return re.sub(r"[\s　“”「」『』‘’\"']", "", str(s or ""))


class Corpus(object):
    def __init__(self, text):
        self.flat = _norm(strip_heads(text))

    def has(self, q, min_len=4):
        q = _norm(q)
        if len(q) < min_len:
            return False
        if q in self.flat:
            return True
        # 允许模型截断到省略号：取前后各一段分别核查
        for part in re.split(r"[…\.]{2,}", q):
            p = part.strip()
            if len(p) >= 8 and p in self.flat:
                return True
        return False


def verify_quotes(node, corpus, stats, path="$"):
    """递归清洗：quote / quotes / evidence 字段若不是逐字原文就清空并计数。
    结论本身保留（它可能仍然对），但会被标记为无引证，最终文档里会显示为「未核验」。"""
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if k in ("quote", "evidence") and isinstance(v, str):
                stats["checked"] += 1
                if v and not corpus.has(v):
                    stats["dropped"] += 1
                    node[k] = ""
            elif k == "quotes" and isinstance(v, list):
                keep = []
                for x in v:
                    stats["checked"] += 1
                    if isinstance(x, str) and corpus.has(x):
                        keep.append(x)
                    else:
                        stats["dropped"] += 1
                node[k] = keep
            else:
                verify_quotes(v, corpus, stats, path + "." + str(k))
    elif isinstance(node, list):
        for x in node:
            verify_quotes(x, corpus, stats, path + "[]")
    return node


def verify_facts(node, titles, stats):
    """构思结论的核验：fact 字段必须指认到一个真实的章名 / 剧情点名。

    与 verify_quotes 同一条纪律，只是核验对象不同 —— 结构没有句子可引，但「第几章发生了什么」
    是可以对账的。指认不到就清空并计数，条目本身保留但在文档里显示为未核验。
    没有图谱时 titles 为空，这一节整体标为未核验，而不是假装通过。
    """
    if not titles:
        return node
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if k == "fact" and isinstance(v, str):
                stats["checked"] += 1
                nv = _norm(v)
                if not (nv and any(t in nv for t in titles if len(t) >= 3)):
                    stats["dropped"] += 1
                    node[k] = ""
            else:
                verify_facts(v, titles, stats)
    elif isinstance(node, list):
        for x in node:
            verify_facts(x, titles, stats)
    return node


# ---------------------------------------------------------------------------
# 七·B、保真回测：唯一能回答「到底蒸出来了没有」的东西
#
#   让同一个模型分别在【带这份提示词】和【不带】两种条件下写同一个场景，再用与统计原著
#   完全相同的算法去量两份稿子，逐维比对原著。有提示词一侧更接近，才算蒸馏真的起作用了；
#   否则这份提示词只是看起来很长。
#   诚实边界：这测的是「照着这份提示词写，能不能复现作者的可测特征」，
#   测不了立意、人物魅力、结构长跨度 —— 那些没有客观标尺，本引擎不假装能打分。
# ---------------------------------------------------------------------------
FID_DIMS = [
    ("句长均值", lambda m: m["sent_len"]["mean"], "rel", 0.35),
    ("短句占比", lambda m: m["sent_len"]["short_ratio"], "pp", 14.0),
    ("长句占比", lambda m: m["sent_len"]["long_ratio"], "pp", 10.0),
    ("段落均长", lambda m: m["para_len"]["mean"], "rel", 0.50),
    ("单句成段率", lambda m: m["para_len"]["one_sent_ratio"], "pp", 22.0),
    ("对白占比", lambda m: m["dialogue"]["ratio"], "pp", 16.0),
    ("对白句均长", lambda m: m["dialogue"]["mean_len"], "rel", 0.45),
    ("裸引号率", lambda m: m["dialogue"]["bare_ratio"], "pp", 26.0),
    ("四字短句率", lambda m: m["clause"]["four_ratio"], "pp", 8.0),
    ("逗号间字数", lambda m: m["clause"]["mean"], "rel", 0.30),
    ("感官密度", lambda m: m["sense_total_per10k"], "rel", 0.55),
    ("动作密度", lambda m: m["motion_per10k"], "rel", 0.70),
    ("内心密度", lambda m: m["thought_per10k"], "rel", 0.70),
]


def _dev(kind, a, b):
    """偏离度：归一到 0（完全一致）～1+（超出容差）。a 为原著，b 为待测。"""
    a, b = float(a or 0), float(b or 0)
    if kind == "pp":
        return abs(a - b)
    if a <= 0:
        return 0.0 if b <= 0 else 1.0
    return abs(a - b) / a


def fidelity_report(author_m, with_m, ctrl_m=None):
    """逐维比对。返回可直接渲染的表 + 总分 + 结论。"""
    rows, sw, sc, nw = [], 0.0, 0.0, 0
    for label, get, kind, tol in FID_DIMS:
        try:
            av, wv = get(author_m), get(with_m)
        except Exception:
            continue
        cv = None
        if ctrl_m:
            try:
                cv = get(ctrl_m)
            except Exception:
                cv = None
        dw = _dev(kind, av, wv)
        dc = _dev(kind, av, cv) if cv is not None else None
        # 命中率：容差之内算命中，按线性衰减给分，超出容差记 0
        hw = max(0.0, 1.0 - dw / tol)
        hc = max(0.0, 1.0 - dc / tol) if dc is not None else None
        rows.append({"dim": label, "author": av, "with": wv, "ctrl": cv,
                     "dev_with": round(dw, 3), "dev_ctrl": (round(dc, 3) if dc is not None else None),
                     "hit_with": round(100 * hw), "hit_ctrl": (round(100 * hc) if hc is not None else None),
                     "better": (None if hc is None else (hw > hc + 0.02))})
        sw += hw
        if hc is not None:
            sc += hc
        nw += 1
    score_w = round(100.0 * sw / max(1, nw))
    score_c = round(100.0 * sc / max(1, nw)) if ctrl_m else None
    # 对话标签偏好：分类维度，单独比
    top = lambda m: (m["dialogue"]["tags"][0][0] if m["dialogue"]["tags"] else "")
    tag = {"author": top(author_m), "with": top(with_m), "ctrl": (top(ctrl_m) if ctrl_m else None)}
    wins = sum(1 for r in rows if r["better"]) if ctrl_m else 0
    if score_c is None:
        verdict = "无对照组，只报绝对贴合度 %d 分。" % score_w
    elif score_w >= score_c + 12:
        verdict = "有提示词 %d 分 vs 无提示词 %d 分，%d/%d 维更贴近原著 —— 这份提示词在可测维度上确实起作用。" \
                  % (score_w, score_c, wins, len(rows))
    elif score_w >= score_c + 4:
        verdict = "有提示词 %d 分 vs 无提示词 %d 分，%d/%d 维更贴近 —— 起作用，但幅度有限，" \
                  "多半是模型没吃下全部指令（可换用完整版提示词或更强的模型）。" % (score_w, score_c, wins, len(rows))
    else:
        verdict = "有提示词 %d 分 vs 无提示词 %d 分 —— 在这个模型上没测出明显差异。" \
                  "常见原因：模型忽略长提示词、或采样量太小。请换模型或加长回测样本再判。" % (score_w, score_c)
    return {"rows": rows, "score_with": score_w, "score_ctrl": score_c, "tag": tag,
            "verdict": verdict, "dims": len(rows)}


# 无法执行的形容词结论：出现即降级标注，让用户看得见哪些条目是水词
VAGUE = re.compile(r"(生动|细腻|优美|深刻|大气|张力十足|引人入胜|扣人心弦|笔触老练|栩栩如生|入木三分|行文流畅|文笔(好|优美)|节奏明快|感染力强)")


def vague_count(node):
    n = 0
    if isinstance(node, dict):
        for v in node.values():
            n += vague_count(v)
    elif isinstance(node, list):
        for v in node:
            n += vague_count(v)
    elif isinstance(node, str):
        n += len(VAGUE.findall(node))
    return n


# ---------------------------------------------------------------------------
# 八、文档拼装（Python 拼，不交给模型整段生成）
# ---------------------------------------------------------------------------
def _tag(q):
    return ("　　> %s" % q.strip()) if q and str(q).strip() else "　　> ⚠ 无逐字引证（已核验剔除）"


def _fact(q):
    return ("　　> 结构依据：%s" % q.strip()) if q and str(q).strip() else "　　> ⚠ 未指认到真实章节 / 剧情点（已核验剔除）"


def arch_digest(am, hs, struct=None):
    """结构硬度量的文本化 —— 同时喂给 mind 与 arch 两个阶段。

    旧版 struct 只有 {files, kinds, cast}，而 MIND_PROMPT 却声称给了「章节数 / 剧情点类型分布 /
    阵营 / 角色重要度」。模型于是被追问一件它手上没有材料的事，只能凭文风样本猜情节架构 ——
    这是构思一节此前最弱的一环，也是这一版要修的第一个东西。
    """
    L = []
    st = struct or {}
    if st.get("files"):
        L.append("材料：%d 个文件 · 建档角色 %d 人" % (st["files"], st.get("cast") or 0))
    if not am:
        L.append("⚠ 这部作品还没有分析出图谱，所以没有剧情点序列可用。"
                 "构思一节只能依据章节收尾 / 开篇分型，长跨度结论（伏笔间隔 / 升级阶梯 / 副线）证据不足，"
                 "宁可少写也不要编。")
        return "\n".join(L)
    L.append("剧情点：%d 个 · 覆盖 %d 章 · 每章均 %s 个（中位 %s，九十分位 %s，最密一章 %s）"
             % (am["events"], am["chapters_with_events"], am["per_chapter"]["mean"], am["per_chapter"]["median"],
                am["per_chapter"]["p90"], am["per_chapter"]["max"]))
    L.append("剧情点类型分布：" + "、".join("%s %d" % (k, v) for k, v in am["kind_dist"][:10]))
    L.append("类型转移（作者推进情节的语法，前 10）：" +
             "、".join("%s→%s %s%%" % (b["from"], b["to"], b["pct"]) for b in am["kind_bigrams"][:10]))
    c = am["cast_per_event"]
    L.append("一场戏的人数：均 %s 人 · 独角戏 %s%% · 三人以上群戏 %s%%" % (c["mean"], c["solo_ratio"], c["crowd_ratio"]))
    ca = am["cast"]
    L.append("角色调度：全书 %d 人，主要角色（重要度≥60）%d 人；主角「%s」在场率 %s%%；"
             "主要角色引入速度 —— " % (ca["total"], ca["majors"], ca["lead"], ca["lead_on_stage"])
             + "、".join("前 %s 已引入 %s%%" % (x["by"], x["pct"]) for x in ca["intro"]))
    r = am["relations"]
    L.append("关系网：%d 条 · 暗线 %d 条（%s%%）· 主要类型 %s"
             % (r["total"], r["hidden"], r["hidden_ratio"], "、".join("%s %d" % (k, v) for k, v in r["kinds"][:6])))
    L.append("阵营：%d 个 · 立场分布 %s"
             % (am["camps"]["total"], "、".join("%s %d" % (k, v) for k, v in am["camps"]["stance"])))
    L.append("分带节奏曲线（全书十等分，每段最多的三类）：")
    for b in am["curve"]:
        L.append("　%s（%d 点）：%s" % (b["band"], b["n"], "、".join("%s %d" % (k, v) for k, v in b["top"])))
    if hs:
        L.append("章节收尾分型（抽样 %d 章）：%s"
                 % (hs["sampled"], "、".join("%s %s%%" % (x["kind"], x["pct"]) for x in hs["tail"])))
        L.append("章节开篇分型：" + "、".join("%s %s%%" % (x["kind"], x["pct"]) for x in hs["head"]))
    return "\n".join(L)


def hooks_digest(hs):
    """章节钩子分型 + 真实例句 —— 构思阶段的 B 段材料"""
    if not hs:
        return "（材料里没有识别到章节，钩子分型不可用）"
    L = ["【收尾分型 · 抽样 %d 章】" % hs["sampled"]]
    for x in hs["tail"]:
        L.append("· %s %s%%（%d 章）" % (x["kind"], x["pct"], x["n"]))
        for e in (hs["tail_ex"].get(x["kind"]) or [])[:2]:
            L.append("　　例〔%s〕%s" % (e["chapter"], e["text"]))
    L.append("【开篇分型】")
    for x in hs["head"]:
        L.append("· %s %s%%（%d 章）" % (x["kind"], x["pct"], x["n"]))
        for e in (hs["head_ex"].get(x["kind"]) or [])[:2]:
            L.append("　　例〔%s〕%s" % (e["chapter"], e["text"]))
    return "\n".join(L)


def track_digest(track):
    if not track:
        return "（没有图谱剧情点序列可用）"
    L = []
    for w in track:
        L.append("〔全书 %s · 起于「%s」〕" % (w["pos"], w["chapter"]))
        for it in w["items"]:
            L.append("　%s｜%s｜%s｜出场：%s"
                     % (it["kind"] or "—", it["title"], it["summary"], "、".join(it["cast"]) or "—"))
    return "\n".join(L)


def _mtable(m):
    d, s, p, c = m["dialogue"], m["sent_len"], m["para_len"], m["clause"]
    tags = "、".join("%s %d 次" % (k, v) for k, v in d["tags"][:5]) or "—"
    top_p = "、".join("%s %s" % (k, v) for k, v in sorted(m["punct_per10k"].items(), key=lambda kv: -kv[1])[:8])
    pron = "、".join("%s %s" % (k, v) for k, v in sorted(m["pronoun"].items(), key=lambda kv: -kv[1])[:6])
    sense = "、".join("%s %s" % (k, v) for k, v in sorted(m["sense"].items(), key=lambda kv: -kv[1]))
    return [
        ("规模", "%s 字 · %s 句 · %s 段 · %s 章" % (f"{m['cjk']:,}", f"{m['sentences']:,}", f"{m['paras']:,}", m["chapters"])),
        ("句长", "均 %s 字 · 中位 %s · 十分位 %s / 九十分位 %s · 最长 %s" % (s["mean"], s["median"], s["p10"], s["p90"], s["max"])),
        ("句长构成", "≤8 字短句占 %s%% · ≥40 字长句占 %s%%" % (s["short_ratio"], s["long_ratio"])),
        ("段落", "均 %s 字 · 中位 %s · 九十分位 %s · 每段 %s 句 · 单句成段占 %s%%" % (p["mean"], p["median"], p["p90"], p["sent_per_para"], p["one_sent_ratio"])),
        ("对白", "占正文 %s%% · %s 处 · 每句均 %s 字（中位 %s，九十分位 %s）" % (d["ratio"], f"{d['count']:,}", d["mean_len"], d["median_len"], d["p90_len"])),
        ("对话标签", "%s · 裸引号（无标签）约 %s%%" % (tags, d["bare_ratio"])),
        ("分句节奏", "逗号间均 %s 字 · 四字短句占 %s%%" % (c["mean"], c["four_ratio"])),
        ("感官配比", "每万字：%s · 合计 %s" % (sense, m["sense_total_per10k"])),
        ("动作 / 内心 / 时间标记", "每万字 %s / %s / %s" % (m["motion_per10k"], m["thought_per10k"], m["time_mark_per10k"])),
        ("拟声词", "每万字 %s" % m["onomat_per10k"]),
        ("人称", "每万字：%s" % (pron or "—")),
        ("标点", "每万字：%s" % (top_p or "—")),
        ("章节体量", "均 %s 字 · 中位 %s · 最短 %s · 最长 %s" % (int(m["chapter_len"]["mean"]), m["chapter_len"]["median"], m["chapter_len"]["min"], m["chapter_len"]["max"])),
    ]


def build_prompt_md(title, m, codex, mind, voice, guard, soak, edges, samples_, meta, core=False,
                    arch=None, am=None, hs=None, fid=None):
    L = []
    W = L.append
    heads, tails = edges
    arch = arch or {}
    W("# 《%s》文风蒸馏提示词" % (title or "未命名"))
    W("")
    W("> **用法**：整段贴进系统提示词 / 自定义指令 / Project Instructions，再给出你要写的情节。")
    if core:
        W("> **这是精简版**：只保留可执行规则，三个附录（真实样本区 / 章节头尾句 / 高频词全表）已切掉，")
        W("> 便于塞进上下文紧张的模型。附录里的真实原文是浸泡法生效的关键 —— 只要装得下，请优先用完整版。")
    else:
        W("> 附录 A 是原著真实样本，**不要删** —— 样本浸泡是这份提示词生效的关键：模型先被真实文字浸透，")
        W("> 再照规则写，才不会退回通用 AI 腔。若上下文吃紧，优先删附录 C，其次附录 B，附录 A 最后删。")
    W("")
    W("> 蒸馏自 %s 字原文 · %d 段浸泡样本 · %d 章 · 引擎 %s · %s"
      % (f"{m['cjk']:,}", len(samples_), m["chapters"], VERSION, meta.get("at", "")))
    W("")
    if meta.get("degraded"):
        # 有节没跑出来还照常交付，是对的（其余部分仍然可用）；但绝不能不声不响 ——
        # 用户必须知道手上这份提示词缺了哪一块，而不是以为它是完整的。
        W("> ⚠ **本次有 %d 节未能生成**：%s。这几节的位置在下文中是空的，"
          "其余部分照常可用。重跑一次蒸馏即可补齐（已完成的阶段会从存盘直接取回，不重复花钱）。"
          % (len(meta["degraded"]), "、".join(meta["degraded"])))
        W("")
    W("---")
    W("")
    W("## 1 · 身份与总纲")
    W("")
    W("你现在以这位作者的身法写作。**不是介绍他，是成为他。**")
    W("")
    if codex.get("voice_summary"):
        W("**核心选择**：%s" % codex["voice_summary"])
        W("")
    if mind.get("reader_contract"):
        W("**与读者的默契**：%s" % mind["reader_contract"])
        W("")
    W("三条压倒一切的铁律：")
    W("")
    W("1. **数字优先于感觉。** 第 2 节的统计是这位作者的体检报告，写完必须回头对数。句长、对白占比、"
      "四字短句率对不上，就是没写像，不管读起来多顺。")
    W("2. **禁忌优先于技巧。** 第 8 节「回避清单」里的东西，一个都不许出现。作者不写的，比他写的更能定义他。")
    if arch.get("chapter_build"):
        W("")
        W("> **要动手写，从第 7.5 节的〈章节施工单〉开始。** 前面几节是「怎么写句子」，"
          "7.5 是「怎么造情节」—— 拿到一个点子先按施工单走一遍，再回来对 2 节的数字。")
    if core:
        W("3. **引证优先于想象。** 每条规则后面的引文就是口径标准。拿不准某句该怎么写，"
          "照最接近的那条引文的写法走；需要成段的真实样本，去看完整版的附录 A。")
    else:
        W("3. **引证优先于想象。** 附录 A 的样本是唯一的口径标准。拿不准某句该怎么写，回去看样本里同类场景怎么写的。")
    W("")
    W("## 2 · 硬性度量（程序统计全文得出 · 不可协商）")
    W("")
    W("| 维度 | 实测 |")
    W("|---|---|")
    for k, v in _mtable(m):
        W("| **%s** | %s |" % (k, v))
    W("")
    if m.get("warnings"):
        # 材料不是叙事正文时，这一节的数字不可信 —— 必须写在文档里，
        # 而不是只在界面上提示一句然后让用户拿着一份错的提示词去用
        W("> ⚠ **这些数字需要打折看**：")
        for x in m["warnings"]:
            W("> - %s" % x)
        W("")
    W("**执行含义**：")
    s, d, p, c = m["sent_len"], m["dialogue"], m["para_len"], m["clause"]
    W("- 写完一段，数句长：均值要落在 **%s±4 字**，且必须有 %s%% 左右的 ≤8 字短句 —— 短句是这位作者的呼吸点，"
      "缺了就会变成 AI 那种一路匀速的长句流。" % (s["mean"], s["short_ratio"]))
    W("- 段落均 **%s 字 / %s 句**；单句成段占 %s%%。%s"
      % (p["mean"], p["sent_per_para"], p["one_sent_ratio"],
         "允许并且应该用单句段落砸节奏。" if p["one_sent_ratio"] >= 12 else "不要滥用单句成段，这位作者很少这么干。"))
    W("- 对白占 **%s%%**。%s" % (d["ratio"],
      "这是一部靠对话推进的作品，写场景时先想「他们要说什么」。" if d["ratio"] >= 28 else
      ("对白偏克制，叙述与描写承担主要重量，不要写成剧本。" if d["ratio"] <= 14 else "对白与叙述大致均衡，两者交替推进。")))
    W("- 台词均 **%s 字**（九十分位 %s 字）。超过九十分位的长篇发言属于例外，一场戏最多一次。"
      % (d["mean_len"], d["p90_len"]))
    if d["tags"]:
        W("- 对话标签只用 **%s**，按这个频次比例分配；裸引号（不带任何标签）约 **%s%%**，"
          "对话连续往来时就该裸着走，别每句都挂标签。" % ("、".join(k for k, _ in d["tags"][:4]), d["bare_ratio"]))
    W("- 四字短句占分句的 **%s%%**。%s" % (c["four_ratio"],
      "这是一副四字骨架，铺陈到位就该用四字砸停。" if c["four_ratio"] >= 8 else "四字短句用得少，不要为了「有文采」硬塞成语。"))
    top_sense = sorted(m["sense"].items(), key=lambda kv: -kv[1])
    if top_sense:
        W("- 感官以 **%s** 为主（每万字 %s），最弱的是 **%s**（%s）。写描写时按这个配比调，"
          "不要五感平均用力 —— 平均用力是 AI 的标志。"
          % (top_sense[0][0], top_sense[0][1], top_sense[-1][0], top_sense[-1][1]))
    W("")
    if m["ngrams"]:
        W("**全书高频词（前 20 · 已剔除人名与功能词）**：%s"
          % "、".join("%s(%d)" % (x["w"], x["n"]) for x in m["ngrams"][:20]))
        W("")
    if m["sent_openers"]:
        W("**高频句首**：%s —— 起句方式也是指纹，别全用「他」「然后」开头。"
          % "、".join("%s(%d)" % (x["w"], x["n"]) for x in m["sent_openers"][:12]))
        W("")

    def rules(title_, key, src, fields=("rule", "why", "quote")):
        items = src.get(key) or []
        if not items:
            return
        W("## %s" % title_)
        W("")
        for i, r in enumerate(items, 1):
            W("**%d. %s**" % (i, r.get(fields[0]) or ""))
            if r.get(fields[1]):
                W("　　*为什么*：%s" % r[fields[1]])
            W(_tag(r.get(fields[2])))
            W("")

    rules("3 · 句法律 · SYNTAX", "prose", codex)
    rules("4 · 语感与节奏 · RHYTHM", "rhythm", codex)

    dic = codex.get("diction") or {}
    if dic:
        W("## 5 · 用词与语域 · DICTION")
        W("")
        if dic.get("register"):
            W("**语域**：%s" % dic["register"])
            W("")
        if dic.get("prefer"):
            W("**该用**：")
            for x in dic["prefer"]:
                W("- %s" % x)
            W("")
        if dic.get("avoid"):
            W("**不该用**：")
            for x in dic["avoid"]:
                W("- %s" % x)
            W("")
    if codex.get("imagery"):
        W("### 意象库 · MOTIFS")
        W("")
        W("这些是作者反复回到的物象。写新情节时从这里取物，而不是自己发明一套象征。")
        W("")
        for x in codex["imagery"]:
            W("- **%s** —— %s" % (x.get("motif") or "", x.get("meaning") or ""))
            W(_tag(x.get("quote")))
        W("")
    pov = codex.get("pov") or {}
    if pov:
        W("## 6 · 视角与时空 · POV")
        W("")
        W("| 项 | 定法 |")
        W("|---|---|")
        W("| 人称 | %s |" % (pov.get("person") or "—"))
        W("| 时间处理 | %s |" % (pov.get("tense") or "—"))
        W("| 叙述距离 | %s |" % (pov.get("distance") or "—"))
        W("")
        if pov.get("note"):
            W("**怎么保持**：%s" % pov["note"])
            W("")
        W(_tag(pov.get("quote")))
        W("")
    rules("6.1 · 场景处理 · SCENE", "scene", codex)
    rules("6.2 · 对白处理 · DIALOGUE", "dialogue", codex)

    W("## 7 · 作者思维模型 · MIND")
    W("")
    W("这一节决定**情节该怎么发生**。写之前先用这套因果观推一遍，再落笔。")
    W("")
    for label, key in (("世界观默认值", "worldview"), ("因果观", "causality"),
                       ("结构偏好", "structure"), ("信息投放", "information"), ("道德判决", "morals")):
        items = mind.get(key) or []
        if not items:
            continue
        W("### %s" % label)
        W("")
        for i, x in enumerate(items, 1):
            W("%d. **%s**" % (i, x.get("claim") or ""))
            W(_tag(x.get("evidence")))
        W("")
    if mind.get("decisions"):
        # 作者思维最可执行的形态：不是「他相信什么」，而是「岔路口他往哪边拐」
        W("### 7.1 岔路口决策倾向（写到卡住时看这一节）")
        W("")
        W("每条都是「遇到 X，他选 Y 而不是 Z」。你写到不知道该让人物怎么反应时，来这里查。")
        W("")
        for i, x in enumerate(mind["decisions"], 1):
            W("%d. **%s**" % (i, x.get("claim") or ""))
            W(_tag(x.get("evidence")))
        W("")

    # ---- 7.5 构思引擎：这一节回答「怎么造情节」，与前面「怎么写句子」分开
    if arch:
        W("## 7.5 · 构思引擎 · ARCHITECTURE")
        W("")
        W("**这一节不是讲这部书的剧情，是讲这位作者造情节的机械原理。**"
          "用你自己的题材、人物代入占位符即可。")
        W("")
        if not meta.get("has_graph"):
            W("> ⚠ 这部作品尚未生成剧情图谱，本节只依据章节收尾 / 开篇分型推得，"
              "长跨度结论（伏笔间隔 · 升级阶梯 · 副线）证据基础较弱。"
              "先在主界面跑一次分析，再重跑蒸馏，这一节会结实得多。")
            W("")
        if am:
            W("| 结构维度 | 实测 |")
            W("|---|---|")
            W("| 剧情点密度 | 每章均 %s 个（中位 %s · 最密 %s） |"
              % (am["per_chapter"]["mean"], am["per_chapter"]["median"], am["per_chapter"]["max"]))
            W("| 剧情点类型 | %s |" % "、".join("%s %d" % (k, v) for k, v in am["kind_dist"][:8]))
            W("| 推进语法（类型转移前 5） | %s |"
              % "、".join("%s→%s %s%%" % (b["from"], b["to"], b["pct"]) for b in am["kind_bigrams"][:5]))
            W("| 一场戏的人数 | 均 %s 人 · 独角戏 %s%% · 三人以上群戏 %s%% |"
              % (am["cast_per_event"]["mean"], am["cast_per_event"]["solo_ratio"], am["cast_per_event"]["crowd_ratio"]))
            W("| 主角在场率 | %s%%（全书 %d 人，主要角色 %d 人） |"
              % (am["cast"]["lead_on_stage"], am["cast"]["total"], am["cast"]["majors"]))
            W("| 主要角色引入速度 | %s |"
              % "、".join("前 %s 已引入 %s%%" % (x["by"], x["pct"]) for x in am["cast"]["intro"]))
            W("| 暗线关系占比 | %s%%（%d / %d 条） |"
              % (am["relations"]["hidden_ratio"], am["relations"]["hidden"], am["relations"]["total"]))
            W("")
            W("**执行含义**：一章平均要推 **%s 个**剧情点 —— 少于这个数就是水章，多于最密值就是赶进度；"
              "一场戏默认摆 **%s 个人**（群戏占 %s%%，%s）；"
              "主角必须出现在约 **%s%%** 的剧情点里，%s"
              % (am["per_chapter"]["mean"], int(round(am["cast_per_event"]["mean"])),
                 am["cast_per_event"]["crowd_ratio"],
                 "不要写成两人对谈剧" if am["cast_per_event"]["crowd_ratio"] >= 40 else "不要动辄拉一堆人上场",
                 am["cast"]["lead_on_stage"],
                 "余下的篇幅可以放心给配角独立线。" if am["cast"]["lead_on_stage"] <= 75
                 else "几乎所有戏都要贴着主角走，别开无主角的支线。"))
            W("")
        if hs and hs.get("tail"):
            W("**章节收尾配比（抽样 %d 章 · 必须照这个比例分配）**：%s"
              % (hs["sampled"], "、".join("%s %s%%" % (x["kind"], x["pct"]) for x in hs["tail"])))
            W("")
            W("**章节开篇配比**：%s" % "、".join("%s %s%%" % (x["kind"], x["pct"]) for x in hs["head"]))
            W("")
            dom = max(hs["tail"], key=lambda x: x["pct"])
            W("> 大头是 **%s（%s%%）** —— 说明这位作者%s。"
              "AI 最爱每章都吊悬念，那不是这位作者的习惯，照做就会失真。"
              % (dom["kind"], dom["pct"],
                 "多数章节是把一段落到实处再收手，悬念靠情节本身而不是靠断句"
                 if dom["kind"] == "断言收尾" else "习惯用「%s」的方式把读者推向下一章" % dom["kind"]))
            W("")

        def arules(label, key, note=""):
            items = arch.get(key) or []
            if not items:
                return
            W("### %s" % label)
            W("")
            if note:
                W(note)
                W("")
            for i, r in enumerate(items, 1):
                W("**%d. %s**" % (i, r.get("rule") or ""))
                if r.get("why"):
                    W("　　*为什么*：%s" % r["why"])
                W(_fact(r.get("fact")))
                W("")

        arules("7.5.1 情节生成引擎（新麻烦从哪来）", "engine",
               "**这是能不能自己造情节的关键。** 写不出下一章时，从这里挑一台引擎起手。")
        arules("7.5.2 升级阶梯（小事怎么做大）", "escalation")
        arules("7.5.3 伏笔与兑现", "setups")
        arules("7.5.4 章节钩子谱", "hooks",
               "与上面的收尾配比对齐使用：先按比例定这一章用哪种收尾，再倒推最后一段怎么写。")
        arules("7.5.5 反转机制", "reversal")
        arules("7.5.6 信息差管理", "suspense")
        arules("7.5.7 副线编织", "subplot")
        arules("7.5.8 角色调度", "cast_use")

        def asteps(label, key, note=""):
            items = arch.get(key) or []
            if not items:
                return
            W("### %s" % label)
            W("")
            if note:
                W(note)
                W("")
            for i, r in enumerate(items, 1):
                W("**第 %d 步 · %s**" % (i, r.get("step") or ""))
                if r.get("why"):
                    W("　　*为什么*：%s" % r["why"])
                W(_fact(r.get("fact")))
                W("")

        asteps("7.5.9 章节施工单（从一个点子到一章成稿）", "chapter_build",
               "**照着做，不是读一遍。** 每写一章走一遍这张单子，写完回第 2 节对数字。")
        asteps("7.5.10 长线施工单（一个单元十来章怎么搭）", "arc_build")
        oe = arch.get("open_end") or {}
        if oe.get("opening") or oe.get("ending"):
            W("### 7.5.11 开头法与收束法")
            W("")
            if oe.get("opening"):
                W("**开头**：%s" % oe["opening"])
                W("")
            if oe.get("ending"):
                W("**收束**：%s" % oe["ending"])
                W("")
        if arch.get("pace_curve"):
            W("**全书节奏纲**：%s" % arch["pace_curve"])
            W("")
        if am and am.get("curve"):
            W("**分带节奏曲线（全书十等分 · 每段最多的三类剧情点）**")
            W("")
            W("| 位置 | 主导类型 |")
            W("|---|---|")
            for b in am["curve"]:
                W("| %s | %s |" % (b["band"], "、".join("%s %d" % (k, v) for k, v in b["top"])))
            W("")

    W("## 8 · 偏爱与禁忌 · TASTE")
    W("")
    for label, key, note in (("偏爱清单（可以放心多写）", "likes", ""),
                             ("执念（作者一直在跟它较劲，写到就往深里写）", "obsessions", ""),
                             ("回避清单（一条都不许出现）", "taboos", "**这是本节最硬的部分。**")):
        items = mind.get(key) or []
        if not items:
            continue
        W("### %s" % label)
        W("")
        if note:
            W(note)
            W("")
        for x in items:
            W("- **%s** —— %s" % (x.get("item") or "", x.get("note") or ""))
        W("")
    W("## 9 · 声纹表 · VOICE PRINTS")
    W("")
    nar = voice.get("narrator") or {}
    if nar:
        W("### 9.0 叙述者")
        W("")
        W("- **站位**：%s" % (nar.get("stance") or "—"))
        W("- **用词层级**：%s" % (nar.get("lexicon") or "—"))
        for x in (nar.get("tells") or []):
            W("- %s" % x)
        W(_tag(nar.get("quote")))
        W("")
    for i, ch in enumerate(voice.get("characters") or [], 1):
        W("### 9.%d %s" % (i, ch.get("name") or "—"))
        W("")
        W("| 项 | 定法 |")
        W("|---|---|")
        W("| 语域 | %s |" % (ch.get("register") or "—"))
        W("| 句式 | %s |" % (ch.get("sentence") or "—"))
        W("| 称呼 | %s |" % (ch.get("address") or "—"))
        W("| **不会说** | %s |" % (ch.get("taboo") or "—"))
        W("")
        for x in (ch.get("tells") or []):
            W("- %s" % x)
        for q in (ch.get("quotes") or []):
            W(_tag(q))
        W("")
    if codex.get("templates"):
        W("## 10 · 可搬用句式模板 · TEMPLATES")
        W("")
        W("占位符换成你的内容即可。不要每句都用模板，按第 3、4 节的节奏铺开。")
        W("")
        for i, x in enumerate(codex["templates"], 1):
            W("%d. `%s`" % (i, x))
        W("")
    if codex.get("counter"):
        W("## 11 · 反例：这位作者不会这样写")
        W("")
        for x in codex["counter"]:
            W("- ✗ %s" % x)
        W("")
    if guard.get("pitfalls"):
        W("## 12 · AI 病灶对照表（针对本文风）")
        W("")
        W("通用模型模仿这位作者时最常犯的错，以及改法。**写完逐条过一遍。**")
        W("")
        W("| 通用模型会这样干 | 为什么违背这位作者 | 改成 |")
        W("|---|---|---|")
        for x in guard["pitfalls"]:
            W("| %s | %s | %s |" % (str(x.get("ai_habit") or "").replace("|", "／"),
                                    str(x.get("why_wrong") or "").replace("|", "／"),
                                    str(x.get("fix") or "").replace("|", "／")))
        W("")
    W("## 13 · 交付前自检")
    W("")
    W("写完不要直接交。逐条判定，任何一条不过就改到过。")
    W("")
    W("1. **对数**：句长均值 %s±4？≤8 字短句 ≈%s%%？对白占比 ≈%s%%？四字短句 ≈%s%%？"
      % (s["mean"], s["short_ratio"], d["ratio"], c["four_ratio"]))
    if d["tags"]:
        W("2. **对话标签**：只用了 %s 这几个？有没有混进「缓缓说道」「淡淡地说」这类不属于本作的标签？"
          % "、".join(k for k, _ in d["tags"][:4]))
    else:
        W("2. **对话标签**：与原作一致？")
    W("3. **禁忌**：第 8 节回避清单逐条查，一条都没犯？")
    W("4. **感官**：配比是否偏向 %s，而不是五感平均？" % (top_sense[0][0] if top_sense else "—"))
    W("5. **声纹**：把台词遮住名字，还能认出是谁在说？认不出就重写。")
    for i, x in enumerate(guard.get("checklist") or [], 6):
        W("%d. %s" % (i, x))
    W("")
    if core:
        W("---")
        W("")
        W("*Castline 文风蒸馏 · %s · 精简版（附录已切）· 引证核验 %d 条，剔除 %d 条改写引文*"
          % (VERSION, meta.get("quotes_checked", 0), meta.get("quotes_dropped", 0)))
        return "\n".join(L)

    if fid:
        # 这一节是本文档唯一的「体检报告」：它不吹这份提示词有多好，只报测出来的数
        W("## 14 · 保真回测（本引擎对这份提示词的自测结果）")
        W("")
        W("做法：让**同一个模型**分别在【拿到这份提示词的精简版】和【什么都不给】两种条件下，"
          "写同样两个与原著无关的场景，再用统计原著的同一套算法去量两份稿子，逐维比原著。"
          "有提示词一侧更接近，才算这份提示词真的起了作用。")
        W("")
        W("**结论**：%s" % fid["verdict"])
        W("")
        W("| 维度 | 原著 | 有提示词 | 无提示词 | 贴合度（有→无） |")
        W("|---|---|---|---|---|")
        for r in fid["rows"]:
            W("| %s | %s | %s | %s | %s%% → %s%%%s |"
              % (r["dim"], r["author"], r["with"], "—" if r["ctrl"] is None else r["ctrl"],
                 r["hit_with"], "—" if r["hit_ctrl"] is None else r["hit_ctrl"],
                 "　✓" if r.get("better") else ""))
        W("")
        W("总分：**有提示词 %s** / 无提示词 %s（%d 个可测维度的平均贴合度）"
          % (fid["score_with"], fid["score_ctrl"] if fid["score_ctrl"] is not None else "—", fid["dims"]))
        if fid.get("tag"):
            t = fid["tag"]
            W("")
            W("对话标签首选：原著 **%s** · 有提示词 **%s** · 无提示词 **%s**"
              % (t.get("author") or "—", t.get("with") or "—", t.get("ctrl") or "—"))
        W("")
        W("> **这份分数测的是什么、测不了什么。** 测的是可量化的笔法特征：句长分布、段落形态、"
          "对白比重与标签偏好、四字短句率、感官与动作密度。测不了立意、人物魅力、"
          "长跨度结构与情感重量 —— 那些没有客观标尺，本引擎不假装能打分。"
          "另外回测样本只有 %s 字，密度类指标本身有波动，看趋势不看小数。"
          % (fid.get("sample", {}).get("with_cjk", "—")))
        W("")

    W("---")
    W("")
    W("## 附录 A · 样本浸泡区（原著真实原文）")
    W("")
    W("**读完再写。** 这些是作者亲手写的字，是全篇最高的口径。规则若与样本冲突，以样本为准。")
    W("")
    for sp in samples_:
        W("### A%s · %s · 全书 %s%% · %s" % (sp["id"][1:], sp["kind"], sp["pos"], sp["chapter"]))
        W("")
        W("```")
        W(sp["text"])
        W("```")
        W("")
        obs = soak.get(sp["id"]) or {}
        if obs.get("moves"):
            W("**这一段的做法**：")
            for mv in obs["moves"]:
                W("- **%s**（%s）→ %s" % (mv.get("do") or "", mv.get("where") or "", mv.get("effect") or ""))
            W("")
        if obs.get("imitable"):
            W("**可搬用**：%s" % " ／ ".join("`%s`" % x for x in obs["imitable"]))
            W("")
    if heads:
        W("## 附录 B · 章节开篇句 / 收尾句")
        W("")
        W("作者怎么进场、怎么收手，看这两组句子最快。你的章节头尾要落在同一口气上。")
        W("")
        W("**开篇句**")
        W("")
        for x in heads:
            W("- 〔%s〕%s" % (x["chapter"], x["text"]))
        W("")
        if tails:
            W("**收尾句**")
            W("")
            for x in tails:
                W("- 〔%s〕%s" % (x["chapter"], x["text"]))
            W("")
    if m["ngrams"]:
        W("## 附录 C · 高频词全表")
        W("")
        W(" · ".join("%s(%d)" % (x["w"], x["n"]) for x in m["ngrams"]))
        W("")
    W("---")
    W("")
    W("*Castline 文风蒸馏 · %s · 引证核验 %d 条，剔除 %d 条改写引文 · 水词计数 %d*"
      % (VERSION, meta.get("quotes_checked", 0), meta.get("quotes_dropped", 0), meta.get("vague", 0)))
    return "\n".join(L)


def build_soak_md(title, m, samples_, soak, edges, lines, meta, arch=None, am=None, hs=None):
    L = []
    W = L.append
    heads, tails = edges
    arch = arch or {}
    W("# 《%s》样本浸泡文档" % (title or "未命名"))
    W("")
    W("> **浸泡法怎么用**：先原文，再拆解，不要跳过原文直接看结论。")
    W("> 一段样本读三遍：第一遍当读者读，第二遍数句子怎么断，第三遍看拆解对不对。")
    W("> 读完 %d 段，你手上就有这位作者的口径了。" % len(samples_))
    W("")
    W("> 原文 %s 字 · %d 章 · 取样 %d 段（共 %s 字）· %s"
      % (f"{m['cjk']:,}", m["chapters"], len(samples_),
         f"{sum(_cjk_len(s['text']) for s in samples_):,}", meta.get("at", "")))
    W("")
    W("---")
    W("")
    W("## 度量卡")
    W("")
    W("| 维度 | 实测 |")
    W("|---|---|")
    for k, v in _mtable(m):
        W("| **%s** | %s |" % (k, v))
    W("")
    W("**取样口径**：按场景类型（开篇 / 对白 / 动作 / 描写 / 内心 / 情绪高点 / 转场 / 收束）")
    W("在全书位置上分散取窗，窗口对齐段落边界，不切断句子。类型判定由程序按对白密度、句长分布、")
    W("感官词密度、动作词、心理词、时间标记等本地特征算出，不经模型猜测。")
    W("")
    W("---")
    W("")
    for sp in samples_:
        W("## %s · %s" % (sp["id"], sp["kind"]))
        W("")
        W("`全书 %s%%` `%s` `%s 字`" % (sp["pos"], sp["chapter"], _cjk_len(sp["text"])))
        W("")
        W("### 原文")
        W("")
        for para in _paras(sp["text"]):
            W("> %s" % para)
            W(">")
        W("")
        obs = soak.get(sp["id"])
        if not obs:
            W("*（本段未取到拆解）*")
            W("")
            continue
        W("### 拆解")
        W("")
        if obs.get("moves"):
            W("**做法**")
            W("")
            for i, mv in enumerate(obs["moves"], 1):
                W("%d. **%s**" % (i, mv.get("do") or ""))
                W("　　位置：%s" % (mv.get("where") or "—"))
                W("　　效果：%s" % (mv.get("effect") or "—"))
                W(_tag(mv.get("quote")))
            W("")
        for label, key in (("句法", "syntax"), ("用词", "diction"), ("感官", "sensory")):
            if obs.get(key):
                W("**%s**：%s" % (label, obs[key]))
                W("")
        if obs.get("avoid"):
            W("**这一段证明作者不会**")
            W("")
            for x in obs["avoid"]:
                W("- ✗ %s" % x)
            W("")
        if obs.get("imitable"):
            W("**可搬用模板**")
            W("")
            for x in obs["imitable"]:
                W("- `%s`" % x)
            W("")
        W("---")
        W("")
    if heads:
        W("## 章节开篇句 %d 例" % len(heads))
        W("")
        for x in heads:
            W("- 〔%s〕%s" % (x["chapter"], x["text"]))
        W("")
    if tails:
        W("## 章节收尾句 %d 例" % len(tails))
        W("")
        for x in tails:
            W("- 〔%s〕%s" % (x["chapter"], x["text"]))
        W("")
    if lines:
        W("## 角色台词样本（逐字原文）")
        W("")
        W("遮住名字读一遍：认不出是谁，就说明这个角色在原作里也没有声纹，别硬编。")
        W("")
        for r in lines:
            W("### %s　`全书 %d 句台词`" % (r["name"], r["n"]))
            W("")
            for x in r["lines"]:
                W("- 「%s」" % x)
            W("")
    if am or hs:
        W("---")
        W("")
        W("## 结构证据（给人读的部分：这部书是怎么被搭起来的）")
        W("")
        if am:
            W("- 剧情点 **%d 个**，覆盖 **%d 章**，每章均 %s 个（中位 %s，最密一章 %s 个）"
              % (am["events"], am["chapters_with_events"], am["per_chapter"]["mean"],
                 am["per_chapter"]["median"], am["per_chapter"]["max"]))
            W("- 类型分布：%s" % "、".join("%s %d" % (k, v) for k, v in am["kind_dist"]))
            W("- 推进语法（一个剧情点之后最常接什么）：%s"
              % "、".join("**%s→%s** %s%%" % (b["from"], b["to"], b["pct"]) for b in am["kind_bigrams"][:8]))
            W("- 一场戏均 %s 人：独角戏 %s%%，三人以上群戏 %s%%"
              % (am["cast_per_event"]["mean"], am["cast_per_event"]["solo_ratio"], am["cast_per_event"]["crowd_ratio"]))
            W("- 主角「%s」在场率 %s%%；主要角色引入：%s"
              % (am["cast"]["lead"], am["cast"]["lead_on_stage"],
                 "、".join("前 %s 已引入 %s%%" % (x["by"], x["pct"]) for x in am["cast"]["intro"])))
            W("- 关系 %d 条，其中暗线 %d 条（%s%%）"
              % (am["relations"]["total"], am["relations"]["hidden"], am["relations"]["hidden_ratio"]))
            W("")
            W("**分带节奏曲线**")
            W("")
            W("| 全书位置 | 主导剧情点类型 |")
            W("|---|---|")
            for b in am["curve"]:
                W("| %s | %s |" % (b["band"], "、".join("%s %d" % (k, v) for k, v in b["top"])))
            W("")
        if hs and hs.get("tail"):
            W("**章节收尾 / 开篇分型（抽样 %d 章 · 已剔除章末的作者行外话）**" % hs["sampled"])
            W("")
            for x in hs["tail"]:
                W("- 收尾 · **%s** %s%%（%d 章）" % (x["kind"], x["pct"], x["n"]))
                for e in (hs["tail_ex"].get(x["kind"]) or [])[:2]:
                    W("　　〔%s〕%s" % (e["chapter"], e["text"]))
            for x in hs["head"]:
                W("- 开篇 · **%s** %s%%（%d 章）" % (x["kind"], x["pct"], x["n"]))
                for e in (hs["head_ex"].get(x["kind"]) or [])[:2]:
                    W("　　〔%s〕%s" % (e["chapter"], e["text"]))
            W("")
        if arch.get("pace_curve"):
            W("**节奏纲**：%s" % arch["pace_curve"])
            W("")
    W("---")
    W("")
    W("*Castline 文风蒸馏 · 样本浸泡文档 · %s*" % VERSION)
    return "\n".join(L)


# ---------------------------------------------------------------------------
# 九、主流程
# ---------------------------------------------------------------------------
def graph_sig(graph):
    """图谱指纹 —— 只取「构思」一节真正会用到的结构事实。

    蒸馏可以先于分析被点，此时构思一节降级（没有剧情点序列可读）。问题在于旧版的缓存键
    只由 (正文, 版本, 模型) 决定，**不含图谱**：于是「先蒸馏 → 再分析出图谱 → 再点蒸馏」
    会稳稳命中那份降级结果，用户永远拿不到构思一节，面板还显示「已缓存」。
    把结构事实并入键，图谱一出现（或结构变了）就自然重算，无图谱时返回空串 ——
    这样从没分析过的作品，键与旧版一致，已有缓存不会被无谓地作废。
    """
    if not isinstance(graph, dict) or not graph:
        return ""
    ch = graph.get("characters") or []
    ev = _ev_list(graph)
    rel = graph.get("relations") or graph.get("links") or []
    camps = set()
    for c in ch:
        if isinstance(c, dict) and c.get("camp"):
            camps.add(str(c["camp"]))
    # 计数 + 剧情点标题序列的指纹：改了名字或顺序都会变，仅仅重跑一次分析而结构不变则不变
    h = hashlib.sha1()
    h.update(("%d|%d|%d|%d|" % (len(ch), len(ev), len(rel), len(camps))).encode("utf-8"))
    for e in ev[:400]:
        if isinstance(e, dict):
            h.update((str(e.get("title") or e.get("name") or "")[:40] + "\x00").encode("utf-8"))
    return h.hexdigest()[:8]


def key_for(text, model_key="", gsig=""):
    h = hashlib.sha1()
    h.update(strip_heads(text).encode("utf-8"))
    h.update(("|" + VERSION + "|" + str(model_key or "")).encode("utf-8"))
    if gsig:
        h.update(("|g" + str(gsig)).encode("utf-8"))
    return h.hexdigest()[:16]


def cache_path(cache_dir, key):
    return os.path.join(cache_dir, key + ".distill.json")


def stage_path(cache_dir, key):
    return os.path.join(cache_dir, key + ".dstage.json")


class Ledger(object):
    """阶段级存盘。

    蒸馏是一条八段的线性流水线，跑满一部大书要十几到二十分钟。旧版只在**全部跑完**才落盘，
    于是第七段撞上一次网关抖动，前面十几分钟的模型产出连同已经核验过的引证一起蒸发，
    重跑得从第一段开始 —— 这与分析引擎当初「建档是唯一没有兜底的阶段」是同一个病。

    每段一做完就按「这一段实际发出去的提示词的指纹」存盘。重跑时指纹一致就直接取回，
    不再问模型；输入变了（换了样本、换了图谱、改了提示词）指纹自然不同，那一段照常重算。
    """

    def __init__(self, path, atomic, on_warn=None):
        self.path = path
        self.atomic = atomic
        self.on_warn = on_warn
        self.lock = threading.Lock()
        self.d = {}
        self.dirty = False
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict) and raw.get("version") == VERSION:
                    self.d = raw.get("stages") or {}
            except Exception:
                self.d = {}

    def resumable(self):
        return len(self.d)

    def get(self, stage, sig):
        with self.lock:
            rec = self.d.get(stage)
        if isinstance(rec, dict) and rec.get("sig") == sig:
            return rec.get("val")
        return None

    def put(self, stage, sig, val):
        if not self.path:
            return
        err = None
        # 整段写盘都在锁内：浸泡是并发的，两个线程同时写这里会出两种真事故 ——
        #   1) snap 若持有 self.d 的引用（而不是副本），另一个线程在 json.dump 期间插入新段，
        #      直接 RuntimeError: dictionary changed size during iteration；
        #   2) _atomic 用的是同一个 <path>.tmp，两个线程互相踩，os.replace 搬走的是半个文件。
        # 一次写 ~150KB，串行化的代价是毫秒级，换掉一个只在并发下偶发的存盘损坏，值。
        with self.lock:
            self.d[stage] = {"sig": sig, "val": val, "at": int(time.time())}
            snap = {"version": VERSION, "stages": dict(self.d)}
            try:
                self.atomic(self.path, snap)
            except Exception as e:  # noqa
                err = e
        if err is not None and self.on_warn and not self.dirty:
            # 存盘失败要说出来：默默吞掉的话，用户以为进度存住了，下次崩溃仍要从头跑二十分钟
            self.dirty = True
            self.on_warn("阶段存盘失败（%r）—— 本次中断将无法续跑" % err)

    def drop(self):
        self.d = {}
        if self.path and os.path.exists(self.path):
            try:
                os.remove(self.path)
            except Exception:
                pass


def load(cache_dir, key):
    p = cache_path(cache_dir, key)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if d.get("version") == VERSION else None
    except Exception:
        return None


def _parallel(items, fn, par, ck):
    """把 fn 铺到最多 par 条线程上跑；返回第一个异常（取消优先），全部成功则返回 None。
    异常不在工作线程里抛 —— 那样只会打印到 stderr，主流程照常往下走，最后交出一份残缺的结果。"""
    if not items:
        return None
    if par <= 1 or len(items) == 1:
        for i, it in enumerate(items):
            try:
                ck()
                fn(i, it)
            except BaseException as e:  # noqa
                return e
        return None
    box, lock, idx = [], threading.Lock(), [0]

    def worker():
        while True:
            with lock:
                if box or idx[0] >= len(items):
                    return
                i = idx[0]
                idx[0] += 1
            try:
                ck()
                fn(i, items[i])
            except BaseException as e:  # noqa
                with lock:
                    box.append(e)
                return

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(min(par, len(items)))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    # 取消优先于其它异常：用户点了取消，报「网关 500」是误导
    for e in box:
        if isinstance(e, Cancelled):
            return e
    return box[0] if box else None


SOAK_PAR = 3        # 样本浸泡的并发批数。上限由 serve.py 的 Governor 再兜一层，不会抢死分析的槛位
STAGE_RETRY = 1     # 每段模型调用在 call_llm 自身的退避之外，再给一次整段重试


def run(text, names, emit, call, cancel=None, title="", struct=None, cache_dir=None,
        model_key="", force=False, atomic=None, gsig="", snapshot=None, par=None):
    """text 已由调用方 assemble 好；call(prompt, schema, max_tokens, think) → dict。
    emit(ev, data) 与 analyze() 同协议，前端复用同一条进度条。
    snapshot() 由 serve.py 注入（WAITS.snapshot），用来发「模型正在吐字 / 已等多久」的心跳。"""
    def ck():
        if cancel and cancel():
            raise Cancelled()

    def nap(sec):
        # 退避也要能被取消：否则点了取消还要干等一次退避
        end = time.time() + sec
        while time.time() < end:
            ck()
            time.sleep(0.2)

    t0 = time.time()
    key = key_for(text, model_key, gsig)
    if cache_dir and not force:
        hit = load(cache_dir, key)
        if hit:
            emit("stage", {"stage": "cache", "phase": "cache", "text": "命中蒸馏缓存"})
            emit("done", {"distill": hit, "cached": True, "key": key})
            return hit

    # ---- 阶段级存盘：中断后续跑的唯一依据（详见 Ledger 的说明）
    led = Ledger(stage_path(cache_dir, key) if cache_dir else None, atomic or _atomic,
                 on_warn=lambda t: emit("stage", {"stage": "read", "phase": "measure", "text": "⚠ " + t}))
    if force:
        led.drop()
    degraded = []
    resumed = [0]

    def stage_call(name, label, phase, prompt, schema, max_tokens=24000, think=True,
                   required=True, stage_id="merge", note=True):
        """一段模型调用 = 存盘命中 → 直接取回；否则调用，成功即存盘；失败重试，
        仍失败则按 required 决定「整次中止（下次可续跑）」还是「本节降级为空，其余照常交付」。"""
        sig = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:16]
        hit = led.get(name, sig)
        if hit is not None:
            resumed[0] += 1
            emit("stage", {"stage": stage_id, "phase": phase, "text": "%s · 从存盘恢复（不重复调用模型）" % label})
            return hit
        last = None
        for attempt in range(STAGE_RETRY + 1):
            ck()
            try:
                r = call(prompt, schema, max_tokens, think)
                led.put(name, sig, r)
                return r
            except Cancelled:
                raise
            except Exception as e:  # noqa
                last = e
                if attempt < STAGE_RETRY:
                    emit("stage", {"stage": stage_id, "phase": phase,
                                   "text": "⚠ %s 失败（%r），4 秒后重试一次" % (label, e)})
                    nap(4)
        if required:
            # 必须是 `raise last`：裸 raise 在 except 块之外会变成
            # RuntimeError: No active exception to re-raise，把真正的网关错误吃掉
            raise last if last is not None else RuntimeError("%s 失败" % label)
        if note:
            degraded.append(label)
        emit("stage", {"stage": stage_id, "phase": phase,
                       "text": "⚠ %s 两次都没成（%r）—— 本节留空，其余照常交付；重跑可补齐" % (label, last)})
        return {}

    # ---- 心跳：八段里每一段都是一次几十到几百秒的深度调用，期间旧版一个事件都不发，
    #      进度条静止得和卡死没有区别。每 3s 把「等了多久 / 吐了多少字 / 是否在思考」推上去。
    hb_stop = threading.Event()

    def _beat():
        while not hb_stop.wait(3.0):
            d = {"beat": "distill", "elapsed": round(time.time() - t0), "heartbeat": True}
            try:
                if snapshot:
                    d.update(snapshot() or {})
                emit("progress", d)
            except Exception:
                return

    threading.Thread(target=_beat, daemon=True).start()
    try:
        return _run(text, names, emit, call, ck, nap, t0, key, title, struct, cache_dir,
                    model_key, atomic, led, degraded, resumed, stage_call,
                    max(1, int(par or SOAK_PAR)), gsig)
    finally:
        hb_stop.set()


def _run(text, names, emit, call, ck, nap, t0, key, title, struct, cache_dir,
         model_key, atomic, led, degraded, resumed, stage_call, par, gsig):
    body = strip_heads(text)
    if _cjk_len(body) < 800:
        raise ValueError("材料太少（不足 800 汉字），蒸馏文风需要足够的原文样本")

    if led.resumable():
        emit("stage", {"stage": "read", "phase": "measure",
                       "text": "发现上次中断的存盘（%d 段已完成）—— 这次只补没跑完的部分" % led.resumable()})

    emit("stage", {"stage": "read", "phase": "measure", "text": "统计全文硬性度量…"})
    ck()
    m = metrics(body, names)
    m["warnings"] = prose_warnings(m)
    emit("stage", {"stage": "read", "phase": "measure",
                   "text": "度量完成 · %s 字 · %s 句 · 对白 %s%% · 句长均 %s"
                           % (f"{m['cjk']:,}", f"{m['sentences']:,}", m["dialogue"]["ratio"], m["sent_len"]["mean"]),
                   "warnings": m["warnings"]})
    for w in m["warnings"]:
        # 材料不是叙事正文时当场说清，别等跑完 15 分钟才让用户发现拿到的是一份失真的提示词
        emit("stage", {"stage": "read", "phase": "measure", "text": "⚠ " + w})

    emit("stage", {"stage": "extract", "phase": "sample", "text": "按场景类型取浸泡样本…"})
    ck()
    sps = samples(body)
    chaps = chapters(body)
    edges = edge_lines(chaps, names=names)
    lines = dialogue_by_role(body, names)
    # 构思材料：章节钩子分型（确定性）+ 图谱剧情点序列。前者只要有章节就能算，
    # 后者要求这部作品已经分析过图谱；没有就退化，并在文档里说明证据基础较弱。
    graph = (struct or {}).get("graph") or {}
    hs = hook_stats(chaps, names)
    am = arch_metrics(graph, names)
    track = event_track(graph)
    emit("stage", {"stage": "extract", "phase": "sample",
                   "text": "取样 %d 段（%s）· 章节头尾 %d 例 · 角色台词 %d 人 · 结构%s"
                           % (len(sps), "、".join(sorted(set(s["kind"] for s in sps))), len(edges[0]), len(lines),
                              ("剧情点 %d 个 / %d 章" % (am["events"], am["chapters_with_events"]) if am
                               else "：无图谱，构思一节证据受限"))})

    corpus = Corpus(body)
    qstats = {"checked": 0, "dropped": 0}

    # ---- 阶段一：样本浸泡。批与批之间没有依赖，旧版却顺序跑（当时的理由是「进度可读、
    #      不抢分析的并发槛位」）——但并发槛位本来就由 Governor 统一管，顺序跑白白把
    #      整个流水线里最长的一段拖成 N 倍。改成小并发，进度按「完成计数」报，一样可读。
    batches = [sps[i:i + 3] for i in range(0, len(sps), 3)]
    soak = {}
    slock = threading.Lock()
    done_n = [0]
    failed = []

    def _soak_one(bi, b):
        blob = "\n\n".join(
            "〔%s · %s · 全书 %s%% · %s〕\n%s" % (x["id"], x["kind"], x["pos"], x["chapter"], x["text"]) for x in b)
        # 单批失败不该拖垮整次蒸馏：少几段标注，法典照样能归纳（全军覆没另行判死，见下）
        r = stage_call("soak:%d" % bi, "样本浸泡 %d/%d 批" % (bi + 1, len(batches)), "soak",
                       SOAK_PROMPT.format(k=len(b), samples=blob), SOAK_SCHEMA, 16000, True,
                       required=False, stage_id="extract")
        with slock:
            done_n[0] += 1
            if not r:
                failed.append(bi + 1)
            for it in (r.get("samples") or []):
                if it.get("id"):
                    soak[str(it["id"]).strip()] = it
            emit("stage", {"stage": "extract", "phase": "soak", "i": done_n[0], "n": len(batches),
                           "text": "样本浸泡 %d/%d 批完成（%s）" % (done_n[0], len(batches), "、".join(x["kind"] for x in b))})

    emit("stage", {"stage": "extract", "phase": "soak", "i": 0, "n": len(batches),
                   "text": "样本浸泡 %d 批 · %d 路并行…" % (len(batches), min(par, len(batches)) or 1)})
    err = _parallel(batches, _soak_one, par, ck)
    if err:
        raise err
    if batches and not soak:
        # 所有批都失败 = 没有任何带标注的样本，后面几段全都建立在它上面，这时候硬着头皮跑
        # 只会产出一份看着很长、其实没有原文依据的提示词。宁可失败，且存盘已在，可以续跑。
        raise RuntimeError("样本浸泡全部失败（%d 批），没有可用的标注样本；已存盘，重跑会接着这里继续" % len(batches))
    if failed:
        degraded.append("样本浸泡第 %s 批" % "、".join(map(str, failed)))
    verify_quotes(soak, corpus, qstats)

    soak_blob = json.dumps([dict(soak[s["id"]], kind=s["kind"], pos=s["pos"]) for s in sps if s["id"] in soak],
                           ensure_ascii=False)[:60000]
    edges_blob = json.dumps({"heads": edges[0][:24], "tails": edges[1][:24]}, ensure_ascii=False)
    m_blob = json.dumps(dict((k, v) for k, v in m.items() if k != "ngrams"), ensure_ascii=False)
    m_blob += "\n高频词：" + "、".join("%s(%d)" % (x["w"], x["n"]) for x in m["ngrams"][:30])

    # ---- 阶段二：文风法典
    ck()
    emit("stage", {"stage": "merge", "phase": "codex", "text": "归纳文风法典（句法 · 语感 · 视角 · 场景 · 对白）…"})
    # 法典是整份提示词的骨架，后面 mind / guard 都拿它当输入 —— 这一段没有降级空间，
    # 失败就中止（存盘还在，下次续跑直接从这里接上，前面的浸泡不会重跑）。
    codex = stage_call("codex", "文风法典", "codex",
                       CODEX_PROMPT.format(metrics=m_blob, soak=soak_blob, edges=edges_blob),
                       CODEX_SCHEMA, 24000, True, required=True)
    verify_quotes(codex, corpus, qstats)

    # ---- 阶段三：作者思维
    ck()
    emit("stage", {"stage": "merge", "phase": "mind", "text": "蒸馏作者思维 · 决策倾向 · 喜好 · 禁忌…"})
    st = arch_digest(am, hs, struct)[:12000]
    mind = stage_call("mind", "作者思维", "mind",
                      MIND_PROMPT.format(struct=st, codex=json.dumps(codex, ensure_ascii=False)[:30000],
                                         soak=soak_blob[:30000]),
                      MIND_SCHEMA, 24000, True, required=False)
    verify_quotes(mind, corpus, qstats)

    # ---- 阶段三·B：构思引擎（情节生成 · 升级 · 伏笔 · 钩子 · 章节施工单）
    #      这一节的输入刻意不是文风样本窗口 —— 构思只在序列上可见。
    ck()
    emit("stage", {"stage": "merge", "phase": "arch",
                   "text": "蒸馏构思引擎 · 情节生成 · 升级阶梯 · 伏笔 · 章节施工单…"})
    fstats = {"checked": 0, "dropped": 0}
    arch = stage_call("arch", "构思引擎", "arch",
                      ARCH_PROMPT.format(arch=st, hooks=hooks_digest(hs)[:16000], track=track_digest(track)[:30000],
                                         codex=json.dumps({"voice_summary": codex.get("voice_summary"),
                                                           "scene": codex.get("scene"), "pov": codex.get("pov")},
                                                          ensure_ascii=False)[:8000]),
                      ARCH_SCHEMA, 24000, True, required=False)
    verify_facts(arch, arch_titles(graph, chaps), fstats)

    # ---- 阶段四：声纹
    ck()
    emit("stage", {"stage": "merge", "phase": "voice",
                   "text": "提取声纹 · 叙述者 + %d 位角色…" % len(lines)})
    narr = "\n\n".join(x["text"] for x in sps if x["kind"] in ("描写场", "内心场", "转场", "开篇"))[:14000]
    if not narr:
        narr = "\n\n".join(x["text"] for x in sps[:3])[:14000]
    lb = "\n\n".join("【%s · 全书 %d 句】\n%s" % (r["name"], r["n"], "\n".join("「%s」" % x for x in r["lines"]))
                     for r in lines)[:20000]
    voice = stage_call("voice", "声纹", "voice",
                       VOICE_PROMPT.format(narr=narr, lines=lb or "（材料中没有可归属的对白）"),
                       VOICE_SCHEMA, 24000, True, required=False) if (lines or narr) else {}
    verify_quotes(voice, corpus, qstats)

    # ---- 阶段五：AI 病灶对照
    ck()
    emit("stage", {"stage": "build", "phase": "guard", "text": "生成 AI 病灶对照表与自检清单…"})
    guard = stage_call("guard", "AI 病灶对照表", "guard",
                       GUARD_PROMPT.format(metrics=m_blob,
                                           codex=json.dumps(codex, ensure_ascii=False)[:24000],
                                           mind=json.dumps({"taboos": mind.get("taboos"), "likes": mind.get("likes"),
                                                            "obsessions": mind.get("obsessions")},
                                                           ensure_ascii=False)[:8000]),
                       GUARD_SCHEMA, 16000, True, required=False, stage_id="build")

    # ---- 拼装
    ck()
    emit("stage", {"stage": "build", "phase": "assemble", "text": "拼装蒸馏提示词与样本浸泡文档…"})
    vg = vague_count(codex) + vague_count(mind) + vague_count(voice) + vague_count(arch)
    meta = {"at": time.strftime("%Y-%m-%d %H:%M"), "quotes_checked": qstats["checked"],
            "quotes_dropped": qstats["dropped"], "facts_checked": fstats["checked"],
            "facts_dropped": fstats["dropped"], "vague": vg, "secs": round(time.time() - t0),
            "model_key": model_key, "has_graph": bool(am), "graph_sig": gsig or "",
            "degraded": list(degraded), "resumed": resumed[0]}
    soak_md = build_soak_md(title, m, sps, soak, edges, lines, meta, arch=arch, am=am, hs=hs)
    # 精简版走同一个构建器（core=True），不做事后字符串切割：
    # 正则切出来的版本开头还在教读者「不要删附录 A」，而那份文档里根本没有附录。
    core_md = build_prompt_md(title, m, codex, mind, voice, guard, soak, edges, sps, meta,
                              core=True, arch=arch, am=am, hs=hs)

    # ---- 阶段六：保真回测。用刚做出来的精简版去让模型写两段，再用同一套度量逐维比原著，
    #      并且带一个「不给提示词」的对照组。这一步失败不影响交付 —— 它是体检，不是产线。
    fid = None
    try:
        ck()
        emit("stage", {"stage": "build", "phase": "fidelity", "text": "保真回测 · 按这份提示词试写…"})
        w = stage_call("fid:with", "保真回测 · 试写", "fidelity",
                       FID_PROMPT.format(brief=FID_SCENES, book=core_md[:90000]),
                       FID_SCHEMA, 12000, False, required=True, stage_id="build", note=False)
        ck()
        emit("stage", {"stage": "build", "phase": "fidelity", "text": "保真回测 · 对照组（不给提示词）试写…"})
        c = stage_call("fid:ctrl", "保真回测 · 对照组", "fidelity",
                       FID_CTRL_PROMPT.format(brief=FID_SCENES),
                       FID_SCHEMA, 12000, False, required=True, stage_id="build", note=False)
        jw = ("%s\n\n%s" % (w.get("narration") or "", w.get("dialogue") or "")).strip()
        jc = ("%s\n\n%s" % (c.get("narration") or "", c.get("dialogue") or "")).strip()
        if _cjk_len(jw) >= 400 and _cjk_len(jc) >= 400:
            fid = fidelity_report(m, metrics(jw), metrics(jc))
            fid["sample"] = {"with_cjk": _cjk_len(jw), "ctrl_cjk": _cjk_len(jc),
                             "with_text": jw[:1200], "ctrl_text": jc[:1200]}
            emit("stage", {"stage": "build", "phase": "fidelity",
                           "text": "回测完成 · 有提示词 %s 分 / 无提示词 %s 分"
                                   % (fid["score_with"], fid["score_ctrl"])})
        else:
            emit("stage", {"stage": "build", "phase": "fidelity",
                           "text": "⚠ 回测样本太短（%d / %d 字），本次不出保真分" % (_cjk_len(jw), _cjk_len(jc))})
    except Cancelled:
        raise
    except Exception as e:  # noqa
        emit("stage", {"stage": "build", "phase": "fidelity", "text": "⚠ 保真回测未完成（%r），提示词照常交付" % e})

    # 完整版带回测结论；精简版刻意不带 —— 上面的回测就是拿这份精简版原样测的，
    # 事后往里塞一段体检报告，交付的就不再是被测过的那份文档了。
    prompt_md = build_prompt_md(title, m, codex, mind, voice, guard, soak, edges, sps, meta,
                                arch=arch, am=am, hs=hs, fid=fid)

    out = {"version": VERSION, "key": key, "title": title, "metrics": m, "codex": codex, "mind": mind,
           "arch": arch, "arch_metrics": am, "hooks": hs, "fidelity": fid,
           "voice": voice, "guard": guard, "soak": soak, "samples": sps, "edges": {"heads": edges[0], "tails": edges[1]},
           "lines": lines, "prompt_md": prompt_md, "soak_md": soak_md, "core_md": core_md, "meta": meta,
           "counts": {"prompt_chars": len(prompt_md), "soak_chars": len(soak_md), "core_chars": len(core_md),
                      "samples": len(sps), "roles": len(lines),
                      "rules": sum(len(codex.get(k) or []) for k in ("prose", "rhythm", "scene", "dialogue")),
                      "pitfalls": len(guard.get("pitfalls") or []),
                      "taboos": len(mind.get("taboos") or []),
                      "arch_rules": sum(len(arch.get(k) or []) for k in
                                        ("engine", "escalation", "setups", "hooks", "reversal", "suspense",
                                         "subplot", "cast_use")),
                      "build_steps": len(arch.get("chapter_build") or []) + len(arch.get("arc_build") or []),
                      "fid_with": (fid or {}).get("score_with"), "fid_ctrl": (fid or {}).get("score_ctrl")}}
    if cache_dir:
        p = cache_path(cache_dir, key)
        try:
            (atomic or _atomic)(p, out)
            # 全量结果已经落盘，阶段存盘的使命结束 —— 留着只会白占磁盘，
            # 且下次 force 重跑时还得先删它
            led.drop()
        except Exception as e:  # noqa
            # 旧版这里是 except: pass。写不进去却不吭声，用户以为存住了，
            # 下次打开面板看到「未蒸馏」，又要再等二十分钟
            emit("stage", {"stage": "build", "phase": "assemble",
                           "text": "⚠ 结果写入缓存失败（%r）—— 这次的产出仍然完整，但下次打开需要重跑" % e})
    emit("done", {"distill": out, "cached": False, "key": key, "secs": meta["secs"]})
    return out


def _atomic(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)
    os.replace(tmp, path)
