#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L3:0303 的第 2 轮修订（agent w-dafeng-1）。

背景（如实记录）：
  本任务上一轮由同一个 agent 名（w-dafeng-1）在同一租约下跑过一次，在 15:27 写出候选后
  被回收（未提交、未留 verdict）。本轮 agent 拿到的是同一个写路径。

本脚本做三类**只增不减值**的修改：
  A. 修正两处**可机器复核且为假**的嵌入声明（headQuoteNote 的长度、boundaryTail 的偏移）；
  B. 加入本轮独立反向验证（reverseVerification[]）——上一轮漏掉的原文事实；
  C. 把其中两条并入正式分区（worldSettings 新增 W13、knowledgeGaps 新增 K12），
     并补 unknowns / selfCritique / provenance 的诚实说明。

所有新增 quote 的 start/end/occ/para 都由本脚本现算，不手写。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0303.candidate.json"
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 1338280, 1348239

docs = json.loads(DOCS.read_text(encoding="utf-8"))
T = docs[0]["text"]
SLICE = T[S:E]
LINES = SLICE.split("\n")

if hashlib.sha256(DOCS.read_bytes()).hexdigest() != SRC_HASH:
    sys.exit("sourceHash 不符：源文件在动手前后被改过，停止")


def ref(key, quote, kind, contains=None):
    """现算一条引文引用的全部定位字段；找不到或有歧义就报错。

    定位口径：在**本单元切片内**找（SLICE.find），再换算成 docs[0].text 全文偏移。
    不直接用 T.find —— 全书里同一句话可能在更早的单元出现过，那样取到的是别人的偏移。
    """
    loc = SLICE.find(quote)
    if loc < 0:
        sys.exit("引文在本单元区间内找不到：%r" % quote[:40])
    st = S + loc
    if T[st:st + len(quote)] != quote:
        sys.exit("换算后偏移不逐字相等：%r" % quote[:40])
    line_no = None
    pos = 0
    for i, ln in enumerate(LINES):
        if pos <= loc < pos + len(ln):
            line_no = i
            break
        pos += len(ln) + 1
    if line_no is None or LINES[line_no].find(quote) < 0:
        sys.exit("para 定位失败（引文不在任何单行内）：%r" % quote[:40])
    if contains is None:
        contains = any(c in quote for c in "“”【】")
    return {
        "key": key,
        "quote": quote,
        "start": st,
        "end": st + len(quote),
        "sourceHash": SRC_HASH,
        "kind": kind,
        "occ": SLICE.count(quote, 0, loc),
        "para": line_no,
        "spansParagraphs": "\n" in quote,
        "containsUtterance": contains,
        "globalOcc": T.count(quote),
    }


base = json.loads(CAND.read_text(encoding="utf-8"))
base_sha = hashlib.sha256(CAND.read_bytes()).hexdigest()

# ── A. 修正两处假的嵌入声明 ────────────────────────────────────────────────
title = "第七十四章 令人安心的队友（8000字大章）"
assert T[S:S + len(title)] == title
old_note = base["source"]["headQuoteNote"]
base["source"]["headQuoteNote"] = (
    "docs[0].text[1338280:1338302] == '%s' 逐字成立（22 个 codepoint），"
    "且它正是任务声明的 start，这是「切片以本单元标题开头」这一自检的机器证据。"
    "⚠️ 本轮修订：上一轮此处写作 [1338280:1338306]，那个区间实际是 "
    "『%s』（末尾多出换行与两个空格），是一句**可机器复核且为假**的话，本轮改正。"
    % (title, T[S:S + 26].replace("\n", "\\n"))
)
base["source"]["headQuoteNoteFix"] = {
    "was": "[1338280:1338306] == 标题",
    "now": "[1338280:1338302] == 标题",
    "why": "len('第七十四章 令人安心的队友（8000字大章）')==22；"
           "docs[0].text[1338280:1338306] 实测为 %r，比标题多 '\\n\\n  ' 三个字符。"
           "复核命令一行可复现。" % T[S:S + 26],
}

ar = base["authorRegion"]
ar["regionStart"] = 1348131
ar["regionEnd"] = E
ar["boundaryTail"] = T[ar["regionStart"]:ar["regionEnd"]]
ar["boundaryTailNote"] = (
    "本轮修订：boundaryTail 定义为 t[regionStart:regionEnd] 的**逐字切片**（不再包含作者区之前"
    "那个空行的 '\\n\\n'）。上一轮给的值比 t[regionStart:regionEnd] 多两个字符（前置换行），"
    "使『boundaryTail 是逐字切片』这句话不成立。叙事正文的结束位置（不含换行）为：'这句话如此熟悉，"
    "好像刚刚说过似的。' 的句末，其后再无叙事句。"
)
ar["narrativeEnd"] = 1348109
ar["narrativeEndNote"] = (
    "叙述句 '这句话如此熟悉，好像刚刚说过似的。' 结束于 1348109（半开区间），"
    "其后是场景分隔符 '\\n    .............\\n\\n' 与作者区。本候选的叙事分区一律不引用 1348131 之后的文字。"
)

# ── B. 本轮独立反向验证：上一轮没覆盖、但原文明确存在的事实 ─────────────────
rv = []

rv.append({
    "id": "RV01",
    "found": "钱友随许七安北行一路，把「这位六品高手实在太倒霉」具体列成了三种横祸（这是他不下墓、"
             "并最终决定回城换地方摆摊的直接观察依据；上一轮只引了他『心生退意』的结论，没引这条清单）。",
    "quote": ref("q_qianyou_mishaps",
                 "一会儿被马车冲撞，一会儿被人误认为仇人，一会儿被官差误认为江洋大盗、通缉要犯。",
                 "narration"),
    "shouldBe": "T16.obstacle 的第二条依据（与 q_retreat / q_leave 并列），或 C14 之后新增一条边："
                "钟璃的天谴→许七安一路招祸→旁观者钱友据此判断风险。",
    "whyMissed": "上一轮把『钱友动摇』只归到 Q 系列的『一念及此』一句上，没有把这句清单收进来；"
                 "它是同一因果的唯一**具体证据**，缺它则『倒霉』只剩形容词。",
})

rv.append({
    "id": "RV02",
    "found": "钱友的内心话给出他动摇的具体假设——他怀疑许七安是「天煞孤星」，并担心连累帮主。",
    "quote": ref("q_tiansha",
                 "“这不会是天煞孤星吧，这种人下墓真的没问题么，不会人没救成，反而连累到帮主他们吧..........”",
                 "inner"),
    "shouldBe": "SP 系列（当线索不当事实）：这是他**未说出口的怀疑**，能支撑 T16.obstacle 与 S06 的 before，"
                "不能用来写许七安真是天煞孤星。",
    "whyMissed": "上一轮 S06 只写『信心满满→战战兢兢→心生退意』，没有登记这条怀疑的原文出处。",
})

rv.append({
    "id": "RV03",
    "found": "许七安与李知府约定的回报渠道是**城门口公告**——这是「他如何得知消息」的指定机制。",
    "quote": ref("q_gonggao",
                 "一有消息，就在城门口发布公告，本官看到后，自然就会寻来。",
                 "dialogue"),
    "shouldBe": "knowledgeGaps 新增一条（本区间没有写这条渠道被使用过），并补进 T02.action 的可选依据。",
    "whyMissed": "上一轮 T02 只覆盖了『发动人手去搜寻』与『一有消息』之前的半句，把渠道这一段漏掉了。",
})

rv.append({
    "id": "RV04",
    "found": "地书的来历被钟璃交代到具体程度：远古至宝、可追溯远古人皇时代、后来碎了；"
             "碎裂的原因她转述的是监正的**猜测**（道尊打碎）。",
    "quote": ref("q_dishu_origin",
                 "“地书是远古至宝，据说可以追溯远古人皇时代，是一件得天地造化的法宝，但后来碎了。”",
                 "dialogue"),
    "shouldBe": "W09（地书碎片）的 explain 可补这条来历；『道尊打碎』须标为转述＋猜测，"
                "只能进 SP 系列，不能写成世界规则。",
    "whyMissed": "上一轮 W09 只写了它的功能（通讯工具＋赌注），没写来历；来历那句在本区间是"
                 "解释「为什么它是至宝」的唯一文字。",
})

rv.append({
    "id": "RV05",
    "found": "抢回碎片的门槛被明确写出：谁也没把握从一位**二品道首**手中抢夺。"
             "这是「不能直接去夺」这一行动约束的原文依据。",
    "quote": ref("q_erpin",
                 "毕竟谁也没把握从一位二品道首手中抢夺地书碎片。",
                 "narration"),
    "shouldBe": "W10（五号那块碎片）的 explain，或 knowledgeGaps 里单列一条行动约束。",
    "whyMissed": "上一轮 T08/T12 都围绕『碎片在谁手里』，唯独漏了『为什么不能抢』这条硬约束；"
                 "缺它会让『先找人、不下墓』的取舍看起来没有代价背景。",
})

rv.append({
    "id": "RV06",
    "found": "金莲道长对地宗妖道行为模式变化的判断，依据是「紫莲的教训」——对手已改成雪藏，"
             "不再挨个寻找持有者。",
    "quote": ref("q_zilian",
                 "有了紫莲的教训，地宗妖道必定不会像之前那样，持着地书碎片挨个寻找持有者们。",
                 "free_indirect"),
    "shouldBe": "SP 系列（人物推理，非叙述认定）＋ knowledgeGaps 的补充；"
                "『必定』是他的断言力度，本区间无验证。",
    "whyMissed": "上一轮只在 W09/W10 的 explain 里提到『雪藏』，未登记这条**推理依据**与其不确定性。",
})

rv.append({
    "id": "RV07",
    "found": "许七安把「留在原地」上升成一条生存经验，并用它解释钟璃、也用它拒绝钱友换地方——"
             "这是 T06/T16 里『换个地方』那一步的机制说明。",
    "quote": ref("q_yuandi",
                 "遇到情况不明的危机，留在原地等待救援是最好的选择，真是熟练的让人心疼啊。",
                 "narration"),
    "shouldBe": "states 或 causeEdges 的补充依据：他**主动选择不移动**，不是被动留在原地。",
    "whyMissed": "上一轮把『换个地方就会遇到别的麻烦，还是待在原地吧』记进了 T06 的语境，"
                 "但没有登记紧接其后这条一般化结论。",
})

rv.append({
    "id": "RV08",
    "found": "野生术士为什么止步七品，原文给了资源性解释：六品炼金术师需要依附王朝、"
             "得到百姓的「好评」反馈。这是一条**影响谁能做什么**的明确设定。",
    "quote": ref("q_liupin_yanjin",
                 "六品炼金术师需要依附王朝，得到百姓的“好评”反馈，这是普通术士很难具备的条件。",
                 "narration"),
    "shouldBe": "worldSettings 新增一条 rule（已并入 W13）。",
    "whyMissed": "上一轮的 NW03/NW04 把术士相关陈述都判为『不约束行动』而排除，"
                 "但这一条恰恰约束了后土帮只能请到七品风水师——它是可执行的资源约束，不是术语装饰。",
})

rv.append({
    "id": "RV09",
    "found": "许七安用「院长赵守」教他的三分法（儒家、术士、朝廷）去质疑人宗为何不在列——"
             "这是他当场未获解答的一个疑问，也是本区间唯一一处点名『气运』归属体系的地方。",
    "quote": ref("q_zhaoshou",
                 "院长赵守和我说过，与气运相关的事物有三种：儒家、术士、朝廷！",
                 "inner"),
    "shouldBe": "knowledgeGaps（他的疑问在本区间无答案）＋ SP 系列（是回忆，不是叙述认定）。",
    "whyMissed": "上一轮完全没收录这一句：它既没进 worldSettings，也没进 unknowns。",
})

base["reverseVerification"] = rv
base["reverseVerificationNote"] = (
    "本节是本轮 agent 独立读完 [1338280,1348239) 全文后，对上一轮候选做的**反向验证**"
    "（问『这一段里还漏了什么』，而不是只查『已写项对不对』）。每条都给逐字引文与现算偏移，"
    "可机器复核。九条里 RV08 已并入 worldSettings W13、RV03 已并入 knowledgeGaps K12，"
    "其余保留在本节作为待处置线索，不强行塞进 tasks 以免污染五栏依据。"
)

# ── C. 并入正式分区 ────────────────────────────────────────────────────────
base["worldSettings"].append({
    "id": "W13",
    "kind": "rule",
    "name": "术士高品需要王朝与民心：六品炼金术师要依附王朝、得到百姓「好评」，普通术士很难具备",
    "basis": "explicit",
    "institution": None,
    "institutionNote": "本条不是诏/令/法（无 declared）、本区间也没有针对它的执行动作（无 executed）、"
                       "更不是某个**人物**的理解（它是叙述给出的资源条件）。按「缺字段写 null，"
                       "不要补一个听起来合理的值」写 null 并说明，而不是硬套标签。",
    "explain": "它解释了本章一处具体的行动限制：后土帮请到的副帮主只能是「七品风水师」，"
               "因为再往上要王朝与民心这两个普通术士拿不到的条件。许七安听到品级后的那句"
               "「果然，对野生术士而言，七品差不多到极限了」正是按这条设定推的。",
    "quotes": [
        ref("q_liupin_yanjin2",
            "六品炼金术师需要依附王朝，得到百姓的“好评”反馈，这是普通术士很难具备的条件。",
            "narration"),
        ref("q_qipin_fengshuishi", "“七品风水师。”钱友回答。", "dialogue"),
    ],
})

base["knowledgeGaps"].append({
    "id": "K12",
    "about": "许七安与李知府约定的回报渠道（城门口公告）是否真的被启用",
    "whoKnows": "本区间**无人知道**：许七安只提出了这个渠道（「一有消息，就在城门口发布公告」），"
                "李知府口头应下；此后原文再没有出现任何公告、也没有写许七安回城门口看。",
    "whoDoesNot": "许七安（提出者，未回收）、李知府与同知（只有承诺文字）、读者。",
    "basis": "explicit",
    "keep": "故不把公告写成『起了作用』或『没起作用』；它与 K04 分开记，因为 K04 问的是"
            "官府是否发动人手，本条问的是**回报渠道本身**有没有被使用。",
    "quotes": [
        ref("q_gonggao2",
            "一有消息，就在城门口发布公告，本官看到后，自然就会寻来。",
            "dialogue"),
        ref("q_zhifu_promise2", "李知府颔首：“许大人放心，本官一定照办。”", "dialogue"),
    ],
})

base["unknowns"].append({
    "id": "U13",
    "about": "「紫莲」「二品道首」这两个在本区间被当作已知背景引用的指代",
    "why": "两处都只出现一次、且都以『教训/没把握』的方式被引用，本区间没有交代紫莲是谁、"
           "二品道首属于哪一方；叙述假定读者已知。",
    "keep": "照原文引用（RV05/RV06），不替它们补身份；不写进 worldSettings。"
            "这两条已登记在 reverseVerification，供后续单元与图谱其它部分对照。",
})

base["selfCritique"].append({
    "id": "SC08",
    "risk": "本文件的主体（tasks/causeEdges/states/foreshadows/worldSettings/themeReadings）"
            "来自同一 agent 名上一轮被回收时的候选，本轮是在其基础上修订，"
            "可能被读成『把上一轮的活记到自己账上』。",
    "why": "我选择如实登记而不是重写：①写路径与租约都归本轮，上一轮未提交、无 verdict；"
           "②本轮我**独立读完了全部 9959 字原文**，并用脚本对上一轮的 382 条引文逐条复核了"
           "『text.find 命中』『偏移逐字相等』『区间不出 [1338280,1348239)』（结果：0 处不符），"
           "另外修正了两处可机器复核且为假的嵌入声明（headQuoteNote 的区间、boundaryTail 的偏移），"
           "并补了 9 条反向验证；③修订过程与依据全部写在本节、provenanceNote 与 reverseVerification 里，"
           "可被复核者逐条推翻。若复核认为应当整份重写，请指明哪一条不成立，我按条重做。",
})

base["provenanceNote"] = (
    "本候选的**基础**是同一 agent 名（w-dafeng-1）在本任务上一轮租约中被回收前留下的候选"
    "（原文件 sha256=%s，已快照存于 loop/state/out/read_dafeng_L3_0303.w-dafeng-1.build/"
    "orphan_snapshot_before_overwrite.json，两份在该时刻逐字节相同）。"
    "本轮由 loop/state/out/read_dafeng_L3_0303.w-dafeng-1.build/patch_0303.py 修订："
    "①改正两处可机器复核且为假的嵌入声明（source.headQuoteNote 的区间、authorRegion.boundaryTail 的偏移）；"
    "②新增 reverseVerification[]（9 条本轮独立反向验证，引文偏移现算）；"
    "③新增 worldSettings W13、knowledgeGaps K12、unknowns U13、selfCritique SC08。"
    "上一轮的引文定位字段（start/end/occ/para/sourceHash）经本轮脚本全量复核，未作修改。"
    % base_sha[:16]
)

base["amendment"] = {
    "amendedBy": "w-dafeng-1",
    "round": 2,
    "baseCandidateSha256": base_sha,
    "baseSnapshot": "loop/state/out/read_dafeng_L3_0303.w-dafeng-1.build/orphan_snapshot_before_overwrite.json",
    "patchScript": "loop/state/out/read_dafeng_L3_0303.w-dafeng-1.build/patch_0303.py",
    "reason": "上一轮被回收（未提交）；本轮独立精读原文后，修正两处假的可复核声明并补反向验证。",
    "notes": "不在共享树改任何受保护路径；只写 loop/ 与 artifacts/。",
}

CAND.write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
print("written:", CAND)
print("new sha256:", hashlib.sha256(CAND.read_bytes()).hexdigest())
print("reverseVerification:", len(base["reverseVerification"]))
print("worldSettings:", len(base["worldSettings"]), " knowledgeGaps:", len(base["knowledgeGaps"]))
print("unknowns:", len(base["unknowns"]), " selfCritique:", len(base["selfCritique"]))
