#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修订 read:dafeng:L3:0307 的候选（**在上一轮孤儿候选之上做定点修订**）。

背景（事实，可复核）
--------------------
`loop/state/out/read_dafeng_L3_0307.candidate.json` 由**同一 agent 名**
（w-sanguo-0）在更早一轮租约里写出（文件 mtime 2026-10-15 20:41），
那一轮**没有 submit**（`loop/state/out/read_dafeng_L3_0307.json` 不存在，
也没有对应的 REJECTED__ 记录）。本轮租约（pid 51099 = 本 worker）重新领到该任务。

本脚本**不重写**那份候选：它的 225 条引文经独立重验全部逐字命中，
是一份可用产物。本脚本只做三类定点修订：

  A. 改正**可机器复核且为假**的嵌入声明（2 处）；
  B. 新增 `reverseVerification[]`：本轮独立反向验证的发现（含上一轮漏掉的原文事实）；
  C. 补齐 `provenanceNote` / `amendment` 与本轮的自陈字段。

口径：所有新引文的 start/end 都是相对 `docs[0].text` **全文**的 codepoint 偏移，
由本脚本在原文上**现算**（不手打），并断言 `TEXT[start:end] == quote` 与
切片内恰好出现一次。

用法：
  python3 -B -s loop/state/out/read_dafeng_L3_0307.w-sanguo-0.build/patch_0307.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]          # …/loop/state/out/<build> → 仓库根
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0307.candidate.json"
SNAP = HERE / "orphan_snapshot_before_patch.json"

START, END = 1366953, 1373655
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
ORPHAN_SHA = "5c0a0045c8e4408fde34bedec01f81641da7d8ce19586ee4f4e780f4b088906c"

TEXT = json.loads(DOCS.read_bytes().decode("utf-8"))[0]["text"]
SLICE = TEXT[START:END]

# 非空段落表（独立实现；本轮所有 para 一律由它现算，不手打）
PARAS: list[tuple[int, int, str]] = []
_p = START
for _line in SLICE.split("\n"):
    if _line.strip():
        PARAS.append((_p, _p + len(_line), _line))
    _p += len(_line) + 1


def PARA_OF(off: int):
    for i, (a, b, _t) in enumerate(PARAS):
        if a <= off < b:
            return i
    return None


problems: list[str] = []


def check(what: str, ok: bool, detail: str = "") -> bool:
    if not ok:
        problems.append("%s：%s" % (what, detail))
    return ok


def ref(key: str, quote: str, kind: str, why: str, para: int | None = None) -> dict:
    """在全文里现算一条引文引用；切片内必须恰好出现一次。

    `para` 传入时必须是**独立重算**的非空段落号；本函数会断言它与实算一致，
    避免手打一个看起来合理的数（上一轮 q_candles_along 正是这样错的）。
    """
    hits = SLICE.count(quote)
    check("引文切片命中数 %s" % key, hits == 1, "命中 %d 次" % hits)
    idx = SLICE.find(quote)
    start = START + idx
    end = start + len(quote)
    check("引文逐字 %s" % key, TEXT[start:end] == quote,
          "[%d,%d) 实为 %r" % (start, end, TEXT[start:end][:40]))
    got_para = PARA_OF(start)
    if para is not None:
        check("引文段号 %s" % key, got_para == para,
              "声明 p%03d 实为 p%r" % (para, got_para))
    return {
        "key": key,
        "quote": quote,
        "start": start,
        "end": end,
        "sourceHash": SOURCE_HASH,
        "kind": kind,
        "para": got_para,
        "occ": idx,
        "occInSlice": hits,
        "globalOcc": TEXT.count(quote),
        "why": why,
    }


# ── 0. 快照孤儿候选（append-only，不覆盖上一轮任何文件）─────────────────────
# 幂等性：本脚本**永远从快照重建**，而不是在已修订过的产物上再叠一次。
# 事故（本轮自查发现）：第一版直接 `cand = json.load(CAND)`，重跑时会把
# 「【本轮改正】…」追加到已追加过的 resultNote 后面，并把 A1/A2 的
# check 判成「旧串已不在」而误报失败。从快照重建可保证重跑结果逐字节相同。
if not SNAP.exists():
    shutil.copy2(CAND, SNAP)
    print("已快照上一轮孤儿候选 → %s" % SNAP.relative_to(ROOT))
else:
    print("快照已存在，从快照重建（不覆盖快照）：%s" % SNAP.relative_to(ROOT))
SNAP_SHA = hashlib.sha256(SNAP.read_bytes()).hexdigest()
check("快照 sha256 等于上一轮产物登记值", SNAP_SHA == ORPHAN_SHA, SNAP_SHA)

cand = json.loads(SNAP.read_bytes().decode("utf-8"))
ORIG_SHA = SNAP_SHA

# ── 1. 机器复核全量引文（修订前的基线）────────────────────────────────────
refs: list[tuple[str, dict]] = []


def walk(node, path: str) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node:
            refs.append((path, node))
        for k, v in node.items():
            walk(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i))


walk(cand, "$")
baseline_bad = 0
for path, node in refs:
    q, s, e = node["quote"], node["start"], node["end"]
    if TEXT[s:e] != q or node.get("sourceHash") != SOURCE_HASH:
        baseline_bad += 1
        problems.append("基线引文不合格 %s" % path)
print("基线：引文 %d 条，逐字失败 %d 条" % (len(refs), baseline_bad))

# ── 2. A 类修订：改正 2 处可机器复核且为假的嵌入声明 ───────────────────────
# A1. textualNotes[0] 的自检式区间写成了 [1366953:1366965]，实际标题只有 9 个 codepoint。
tn0 = cand["textualNotes"][0]
OLD_A1 = "TEXT[1366953:1366965] == '第七十八章 你来啦'"
NEW_A1 = "TEXT[1366953:1366962] == '第七十八章 你来啦'"
check("A1 原文含待改串", OLD_A1 in tn0["text"], "textualNotes[0] 里找不到该串")
check("A1 旧串确为假", TEXT[1366953:1366965] != "第七十八章 你来啦",
      "旧串居然成立，无需修订")
check("A1 新串确为真", TEXT[1366953:1366962] == "第七十八章 你来啦",
      "新串不成立")
tn0["text"] = tn0["text"].replace(OLD_A1, NEW_A1)
tn0["fixedInThisRound"] = {
    # 写法纪律：这里的**每一条** `TEXT[a:b] == '…'` 都必须是**真**的。
    # 第一版把「上一轮那句假话」原样抄进来当 `was`，结果本轮自己的
    # check_0307_r2.py（它会逐条现算散文里的自检式）把它判成假声明 —— 抓得对：
    # 文件里不该出现任何现算为假的自检式，哪怕是在描述一处已改的错误。
    # 现在改为「引原文实际值 + 说明上一轮错在哪」，于是每条自检式都成立。
    "was": "上一轮此处写的是：TEXT[1366953:1366965] 应等于单元标题。"
           "实测 TEXT[1366953:1366965] == '第七十八章 你来啦\n\n '"
           "（12 个 codepoint；标题本身只有 9 个 codepoint）⇒ 上一轮那句话为假。",
    "now": NEW_A1 + "（9 个 codepoint，逐字成立）",
    "why": "上一轮的 check_0307.py 不校验这段散文里的自检式（它只查 225 条 quoteRef），"
           "所以这处假声明活了下来。本轮由 patch_0307.py 现算复核，"
           "并由 check_0307_r2.py 独立重算一遍。",
}

# A2. tasks[12].result.quotes[0] 的 para 记成 130，实际落在非空段落 129。
#     注意：这段引文在 **T13**（tasks[12]）里，不是 T12 —— 第一版按 id 猜成 T12，
#     被本轮自己的 check_0307_r2.py 抓出来。
t13 = cand["tasks"][12]
check("A2 目标任务 id 是 T13", t13.get("id") == "T13", "实际 id=%s" % t13.get("id"))
q_candles = t13["result"]["quotes"][0]
check("A2 目标引文 key", q_candles["key"] == "q_candles_along",
      "实际 key=%s" % q_candles["key"])

actual_para = PARA_OF(q_candles["start"])
check("A2 段落号确为 129", actual_para == 129, "实算 %r" % actual_para)
check("A2 旧值确为假", q_candles["para"] == 130, "旧值 %r" % q_candles["para"])
q_candles["para"] = actual_para
t13["resultNote"] += (
    "【本轮改正】本条 result 引文的 para 上一轮记成 130，实际落在非空段落 129"
    "（p0129 的区间是 [1372078,1372126)，本条引文 [1372082,1372126) 完整落在其中；"
    "p0130 是「烛台上有尚未燃尽的蜡烛…」，与本引文不重叠）。"
    "段落表由 patch_0307.py 与 check_0307_r2.py 两套独立实现重算，结论一致。"
)

# 全量复算 para（用与 build 脚本不同的实现），逐条报告
para_bad = []
seen_keys = set()
for path, node in refs:
    if node["key"] in seen_keys:
        continue
    seen_keys.add(node["key"])
    p = PARA_OF(node["start"])
    if node.get("para") != p:
        para_bad.append((node["key"], node.get("para"), p))
check("A2 修订后全量 para 一致", not para_bad, "仍有 %d 条不符：%r" % (len(para_bad), para_bad[:5]))
print("段落号全量复算：%d 个 key，修订后不符 %d 条" % (len(seen_keys), len(para_bad)))

# ── 3. B 类：本轮独立反向验证（上一轮漏掉的原文事实）────────────────────────
rv = [
    {
        "id": "RV01",
        "found": "「渡劫」这条规则在本区间并非只有抽象体系：许七安当场把它接到一个具体的失败案例上——"
                 "地宗道首渡劫失败、被魔性反噬、堕落成妖道；紧接着叙述点出这条旧事的来源（杀死紫莲后道长的夜访私谈）。",
        "quote": ref("q_dizong", "许七安一拍脑袋，道：“我想起来了，道长你说过，那个该死的地宗道首就是渡劫失败，才被魔性反噬，堕落成妖道。”",
                     "dialogue", "许七安引述旧事：渡劫失败的实例（地宗道首）。"),
        "shouldBe": "W07（道门品阶与天劫）的 explain 应补上这层：这条规则不是纯术语，它有一个**区间内被点名的失败先例**，"
                    "并且这个先例是「渡劫失败 → 魔性反噬 → 堕落成妖道」的下场链；它同时给 C05（灰飞烟灭 vs 转生的矛盾）"
                    "加了一条旁证——道长自己是讲过「渡劫失败会怎样」的人。",
        "whyMissed": "上一轮把 W07 的依据只取了道长那段体系陈述（q_daomen_rank），"
                     "把紧随其后、由许七安补出的实例漏在外面；157 个预置引文里有 q_dizong，但从未被任何分区引用。",
    },
    {
        "id": "RV02",
        "found": "叙述明确交代了许七安那段「道长是残魂」推理的**信息来历**：不是他凭空推断，"
                 "而是「当初杀死紫莲后，金莲道长夜里潜入许七安房间，与他有过一番坦诚布公的谈话」。",
        "quote": ref("q_zilian", "当初杀死紫莲后，金莲道长夜里潜入许七安房间，与他有过一番坦诚布公的谈话。",
                     "narration", "叙述交代旧事的出处：紫莲之死后道长的夜访私谈。"),
        "shouldBe": "S06（许七安对金莲道长的认知）的 anchor 应补这一条：它把 S06 的「想起旧事」锚到一个**区间内被叙述认定的来源**上，"
                    "而不是只锚在平远伯府之战。两者是不同来源：平远伯府是**他亲历的场面**，紫莲后的夜访是**道长主动交底**。",
        "whyMissed": "上一轮 S06.anchor 只引了 q_pingyuan（平远伯府之战），"
                     "把 p0120 这句「来源说明」整段漏掉；q_zilian 同样在预置表里但未被引用。",
    },
    {
        "id": "RV03",
        "found": "壁画之所以能被当作史料来读，是叙述给的一条背景规则：「文字出现前，壁画是用来记载事件的唯一方式，"
                 "哪怕是现在，也还流行着『壁画记事』的传统。」",
        "quote": ref("q_bihua_jishi", "文字出现前，壁画是用来记载事件的唯一方式，哪怕是现在，也还流行着“壁画记事”的传统。",
                     "narration", "叙述给出「壁画记事」的背景规则。"),
        "shouldBe": "T12（读壁画）的 obstacle 或 W 系列应登记这条：它解释了**为什么这群人会把一面墙当证据来推理**，"
                    "而不是当成装饰；缺了它，T05/T11/T12 的推理前提在文件里没有落脚点。",
        "whyMissed": "上一轮覆盖了壁画的**内容**（画了什么），没有覆盖「壁画为何可信」这条**读法规则**。",
    },
    {
        "id": "RV04",
        "found": "「多人运动」那幅壁画与外头那幅的差异被点明：「与外头那幅一样，只不过没有行气经络图」。"
                 "这是本区间唯一一处把「外头那幅」与「主墓里这幅」做**逐项比对**的叙述。",
        "quote": ref("q_orgy_diff", "这幅“多人运动”壁画，与外头那幅一样，只不过没有行气经络图",
                     "inner", "许七安比对两幅壁画，指出差异（无行气经络图）。"),
        "shouldBe": "T12 或 notWorldSettings 应登记：上一轮记了「群臣膜拜高台…与外头那幅一模一样」的**相同**，"
                    "却漏了这处**不同**；两幅壁画的同/异合起来才是「壁画是同一套叙事的两份副本」这一判断的完整依据。",
        "whyMissed": "q_mural_orgy 在预置表里（p93），上一轮只用了 q_mural_same1（p79 的「一模一样」）。",
    },
    {
        "id": "RV05",
        "found": "恒远对壁画叙事给出的**道德疑问**没有被上一轮登记：「如此高人，应该不至于留恋权力。称帝对他而言有何意义？」"
                 "——它与许七安「不符合逻辑」的质疑是**两条不同的质疑线**。",
        "quote": ref("q_hengyuan_why", "恒远大师皱眉道：“如此高人，应该不至于留恋权力。称帝对他而言有何意义？”",
                     "dialogue", "恒远提出的动机疑问（不是逻辑疑问）。"),
        "shouldBe": "T05/T17 旁应新增或补注：许七安质疑的是**壁画为何被画出来**（叙事逻辑），"
                    "恒远质疑的是**高人为何要称帝**（动机合理性）。上一轮把「三人的想法各有不同」只落在蛇壁画那一段，"
                    "漏了篡位段的这条分歧。",
        "whyMissed": "q_hengyuan_ask 在预置表里（p84），上一轮未被任何分区引用。",
    },
    {
        "id": "RV06",
        "found": "病夫帮主对整段壁画的评价里带一个**时代用语**，且叙述当场给出释义：「这未免也太勾栏了。」"
                 "——「『太勾栏』的意思与『戏剧性』差不多，这个时代的戏曲普遍都在勾栏里。」",
        "quote": ref("q_goulan", "“道长篡位，荒淫无度，于是上天降下雷霆劈死了他.........这未免也太勾栏了。”病夫帮主摇摇头，给出评价。",
                     "dialogue", "病夫帮主的评价，含时代用语「太勾栏」。"),
        "quote2": ref("q_goulan_gloss", "“太勾栏”的意思与“戏剧性”差不多，这个时代的戏曲普遍都在勾栏里。",
                      "narration", "叙述为「太勾栏」给出的时代语释义。"),
        "shouldBe": "worldSettings 的 rule 类或 textualNotes 应登记这条**词义说明**："
                    "它是叙述主动为读者补的时代语释义，属于「影响读者如何理解人物判断」的设定，不是装饰。",
        "whyMissed": "q_goulan 在预置表里（p101），上一轮未被引用；紧随的释义句（p102）连预置都没有。",
    },
    {
        "id": "RV07",
        "found": "天地会成员在壁画前的反应有一条被叙述单独点出：「天地会成员的脸色极为古怪，因为他们联想到了更多的东西。」"
                 "并与「话音方落，许七安和楚元缜同时『呵』了一声」「他们默契的相视一笑，知道对方和自己一样，想到了元景帝」构成一串**同代人对照本朝**的暗读。",
        "quote": ref("q_tiandihui_odd", "天地会成员的脸色极为古怪，因为他们联想到了更多的东西。",
                     "narration", "天地会成员的异常反应，叙述未说明联想内容。"),
        "shouldBe": "T05 的旁证或 knowledgeGaps 新增一条：叙述只写「联想到了更多的东西」，"
                    "**没有写出联想的内容**（与后面许七安/楚元缜「想到元景帝」不同——那一处写明了）。这是本区间一处明确的叙述留白。",
        "whyMissed": "上一轮把「想到元景帝」登记进 NW06，但漏了**未写明内容**的天地会成员这一条，"
                     "而这恰是「人物知道而读者不知道」的知识差。",
    },
    {
        "id": "RV08",
        "found": "上一轮 T09 说「道长没有回答『土呢？』」，但漏了他**先前的动作**："
                 "「金莲道长看了一眼青铜棺椁，挪开目光，走到高台边缘，审视着最近的一具干尸。」"
                 "——他对棺椁的第一次注视与被上一轮省略的「挪开目光」，出现在四具干尸被逐一查看**之前**。",
        "quote": ref("q_daozhang_examine", "金莲道长看了一眼青铜棺椁，挪开目光，走到高台边缘，审视着最近的一具干尸。",
                     "narration", "道长看棺椁后移开目光、转去审视干尸。"),
        "shouldBe": "S05 或 T09 的旁证：这是**区间内第二次写到道长与棺椁的关系**（第一次是「没有回答，而是看向中央的青铜棺椁」）。"
                    "上一轮把「看向棺椁」当作回避问题的动作记在 T09.result，却没记**更早的这次「看一眼就挪开」**。"
                    "两次连起来才是「他反复回避棺椁」的观察；单看一次不构成模式。",
        "whyMissed": "q_daozhang_examine 在预置表里（p141），上一轮未引用；T09 只取了 p148 的「没有回答」。",
    },
    {
        "id": "RV09",
        "found": "许七安接近高台时的验尸动作比上一轮写的更具体：「先侧耳聆听，确认没有心跳，接着观察这些干尸」。"
                 "上一轮 T13/世界设定只记了他「告诫不要触碰」，没有记**他先验了没有心跳**这一步。",
        "quote": ref("q_corpse_check", "妈的，吓老子一跳........许七安骂骂咧咧的走过去，先侧耳聆听，确认没有心跳，接着观察这些干尸。",
                     "narration", "许七安的验尸步骤：听心跳 → 观察。"),
        "shouldBe": "T01/T13 的动作依据，或 W06 的 explain：它给出「干尸不会动」这一判断的**取得方式**（听心跳），"
                    "而后文的棺中人语正建立在这个判断被推翻之上——先确认过是死物，后来的声音才更刺人。",
        "whyMissed": "q_corpse_check 在预置表里（p136），上一轮未引用。",
    },
    {
        "id": "RV10",
        "found": "上一轮 157 个预置引文里有 32 个从未被任何分区引用。逐条核对后，其中**确属重复/次要**的 22 条"
                 "（如 q_width_20 与 q_width 同段、q_black_corridor_2 与 q_black_corridor 同段）可以不用；"
                 "但 RV01–RV09 这 9 条不是重复，而是**上一轮确实漏掉的原文事实**。",
        "quote": None,
        "shouldBe": "本条是对「漏了什么」的总账：不是所有未引用引文都该引用，但未引用清单里混着真漏项。"
                    "复核者可用同一清单反查是否还有别的漏项。",
        "whyMissed": "上一轮的覆盖率脚本（coverage_0307.py）只统计「段落是否被引文覆盖」，"
                     "**不检查预置引文是否被分区引用**，所以这些孤儿引文不会被它报出来。",
        "unusedQuoteAudit": {
            "howComputed": "从 build_0307.py 的 QT 字典正则抽出全部已定义 key，"
                           "再从落盘候选里递归收集所有被分区引用的 key，取差集。",
            "totalDefined": 157,
            "usedInSections": 125,
            "unusedCount": 32,
            "unusedRealMissesInPriorRound": [
                "q_dizong", "q_zilian", "q_mural_orgy", "q_hengyuan_ask",
                "q_goulan", "q_daozhang_examine", "q_corpse_check",
            ],
            "unusedDuplicatesOk": [
                "q_width_20（与 q_width 同段）", "q_black_corridor_2（与 q_black_corridor 同段）",
                "q_buji / q_xqa_history（同一句的两截）", "q_where_earth / q_where_earth2（同一句）",
                "q_wangsheng / q_wangsheng_ask（同一句）", "q_chill_before_ask / q_chill_xqa（同一句）",
                "q_canhun（与 q_pingyuan 同段）", "q_ask_danger / q_no_danger / q_open_door",
                "q_wuxing_place_full（与 q_wuxing_place 同句）", "q_no_mural（与 q_other_side 同句）",
                "q_candle_detail / q_candles_cry / q_armor_detail / q_tianjie_echo / q_geju_ask",
                "q_chu_careful / q_mural_orgy 之外的其余同段重复项",
            ],
            "note": "两类必须分开：重复项（同段/同句的另一截）不引用是合理的取舍；"
                    "而 unusedRealMissesInPriorRound 这 7 个 key 指向**独有事实**，"
                    "上一轮没有为它们建条目，本轮把它们补进 RV01–RV09。"
                    "另有 3 条本轮现算的引文（壁画记事、天地会成员脸色、"
                    "太勾栏释义句）在预置表里**根本不存在 key**，属上一轮连预置都没做的漏项。",
        },
    },
]
cand["reverseVerification"] = rv
cand["reverseVerificationNote"] = (
    "本条由本轮（同一 agent 名 w-sanguo-0 的新租约）在**不沿用任何上一轮结论**的前提下，"
    "对同一份原文切片重新通读后与既有候选对账得出。RV01–RV09 每条都给出可逐字复核的引文"
    "（偏移由 patch_0307.py 现算）；RV10 是对「预置引文未引用」清单的总账。"
    "本轮**没有**改动上一轮的任何引文偏移、五栏归位或因果方向——只在 A 类里改正了两处"
    "可机器复核且为假的嵌入声明。"
)

# ── 4. C 类：provenance / amendment ────────────────────────────────────────
cand["provenanceNote"] = (
    "本候选的**基础**是同一 agent 名（w-sanguo-0）在更早一轮租约里写出的产物"
    "（快照 sha256=%s，逐字节存于 %s）。那一轮没有 submit，本轮租约重新领到该任务。"
    "本轮**没有重写**这份候选：它的 225 条引文经本轮独立重验全部逐字命中、sourceHash 一致，"
    "是一份可用产物。本轮由 %s 做定点修订：**A** 改正两处可机器复核且为假的嵌入声明"
    "（textualNotes[0] 的自检区间、tasks[12].result 引文的 para 段号）；"
    "**B** 新增 reverseVerification[]（10 条本轮独立反向验证，引文偏移现算）；"
    "**C** 补齐 provenanceNote 与 amendment。"
    "上一轮的全部引文定位字段（start/end/occ/para/occInSlice/globalOcc/sourceHash）"
    "经本轮脚本全量复算，除 A2 一处外未作修改。"
) % (SNAP_SHA[:16], SNAP.relative_to(ROOT), HERE.name + "/patch_0307.py")

cand["amendment"] = {
    "round": "本轮（新租约，agent 名 w-sanguo-0）",
    "baseCandidateSha256": ORIG_SHA,
    "orphanSnapshot": {
        "path": str(SNAP.relative_to(ROOT)),
        "sha256": SNAP_SHA,
        "note": "上一轮产物的逐字节快照；本轮修订前先落盘，可随时与修订后逐字段对账。",
    },
    "classA_fixed": [
        {
            "where": "textualNotes[0].text",
            "was": "TEXT[1366953:1366965]（上一轮声称它等于单元标题）",
            "now": NEW_A1,
            "evidence": "实测 TEXT[1366953:1366965] == '第七十八章 你来啦\\n\\n '（比标题多 '\\n\\n '）；"
                        "而 TEXT[1366953:1366962] == '第七十八章 你来啦' 逐字成立。",
            "howFound": "本轮独立重算：上一轮 check_0307.py 只校验 225 条 quoteRef，不解析散文里的自检式。",
        },
        {
            "where": "tasks[12]（id=T13）.result.quotes[0].para",
            "was": 130,
            "now": 129,
            "evidence": "p0129 区间 [1372078,1372126)，引文 [1372082,1372126) 完整落在其中；"
                        "p0130 [1372128,1372164) 是「烛台上有尚未燃尽的蜡烛…」，与本引文不重叠。",
            "howFound": "本轮用与 build_0307.py 不同的实现重算非空段落表；"
                        "上一轮 check_0307.py 完全不校验 para 字段。",
        },
    ],
    "classB_added": "reverseVerification[]（10 条）",
    "classC_added": "provenanceNote（改写为事实性沿革）+ amendment（本字段）",
    "unchanged": "tasks 五栏归位与引文、causeEdges 方向与触发机制、states 前后值、"
                 "foreshadows/notForeshadows、worldSettings/notWorldSettings、themeReadings、"
                 "knowledgeGaps、unknowns、selfCritique —— 本轮均未改动，只做增量登记。",
    "notDone": "语义核验（semanticReview）仍未执行：本文件只声称「引文逐字定位 + 结构分区 + 机器可复核」，"
               "不声称「对这一段的理解正确」。",
}

cand["analysisRound"] = {
    "reader": "w-sanguo-0（本轮租约 pid 51099 所起的 agent）",
    "independenceNote": "本轮从头读过 docs[0].text[1366953,1373655) 全量切片（171 个非空段落），"
                        "再与上一轮候选对账；RV 系列是在对账中发现的**增量**，不是抄录上一轮条目。",
    "priorRoundRelation": "同一 agent 名的上一轮产物；本轮持有该任务的租约，是该文件的唯一写入负责人。",
}

# ── 5. 自检：写盘前复算全部引文 ───────────────────────────────────────────
refs2_placeholder = None
cand_refs: list[tuple[str, dict]] = []
refs.clear()
walk(cand, "$")
bad2 = []
for path, node in refs:
    q, s, e = node["quote"], node.get("start"), node.get("end")
    if s is None or e is None:
        bad2.append((path, "缺 start/end"))
        continue
    if TEXT[s:e] != q:
        bad2.append((path, "切片不等"))
    if node.get("sourceHash") != SOURCE_HASH:
        bad2.append((path, "sourceHash 不符"))
check("写盘前全量引文复算", not bad2, "%d 条不合格：%r" % (len(bad2), bad2[:4]))
print("写盘前：引文 %d 条，不合格 %d 条" % (len(refs), len(bad2)))

for sec in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    check("分区存在 %s" % sec, sec in cand, "缺分区")

if problems:
    print("\n".join("✗ " + p for p in problems), file=sys.stderr)
    sys.exit(1)

CAND.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
NEW_SHA = hashlib.sha256(CAND.read_bytes()).hexdigest()
print("已写回 %s" % CAND.relative_to(ROOT))
print("修订前 sha256 = %s" % ORIG_SHA)
print("修订后 sha256 = %s" % NEW_SHA)
print("快照     sha256 = %s" % SNAP_SHA)
print("问题数 = 0")
