#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反向复核：read:dafeng:L0_0224 —— 「这一段里还漏了什么」。

复核契约要求反向验证：只查「已写项对不对」结构性地发现不了遗漏。
所以本脚本走另一条路 —— 先自己读原文切片，把**每一条独立事实/动作/约束**列成探针，
再逐条问：候选里有没有任何引文**触及**它？有没有任何结论文本**提到**它？

判据（两条分开，不混）：
  · coveredByQuote：该探针的字符区间与候选某条引文的区间有交集
    （引文触及 ≠ 语义已核验，这里只回答「有没有被引到」）；
  · mentionedInText：候选的结论文本（text/explain/why/note…）里出现该探针的关键词。

**未覆盖 ≠ 漏读**：过场动作、与已覆盖事实同一件事的复述、作者附言都不算漏。
所以脚本对每条未覆盖探针只输出「候选自己的说法」（若它已在 zeroCoverageList 里
登记过理由，就把它抄出来），把判断留给复核者，不自动判 fail。

用法：
    python3 -B -s .../reverse_check.py [--json]
exit 0：脚本跑通（未覆盖清单是**结果**，不是错误）。
"""

import json
import os
import re
import sys

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0224.candidate.json")
START, END = 841448, 845385

# 探针 = 我读完切片后自己列的「这一段里有什么」。
# key：便于阅读的标签；probe：**逐字**原文子串；why：这条为什么值得单独问一句。
PROBES = [
    ("p011_danger_conclusion", "基于这个推测，那么巡抚大人就危险了。",
     "从推测到结论的那一步：他凭什么把『尸体可能是假的』推到『巡抚危险』"),
    ("p019_xu_stays_behind", "许宁宴，你就守在驿站吧。",
     "把许七安留在驿站的那个命令本身"),
    ("p020_xu_unfit_for_combat", "许七安的状态大伙都知道，不适合高强度作战，去了也发挥不出太出众的战力。",
     "留他在驿站的理由（叙述给出的，不是台词的）"),
    ("p025_gong_rank_no_secrets", "他的铜锣身份是接触不到案件机密的",
     "铜锣职级与知情权限的绑定（s2 的 before）"),
    ("p041_heart_sinks", "许七安无声的望着他，一颗心倏地沉入谷底。",
     "得知城门关闭后的情绪落点"),
    ("p047_jianghu_deep", "当然，江湖水深，可能藏着一两位千年老王八。",
     "对『四品可以在江湖横着走』的反向保留"),
    ("p055_send_word_conscript", "一定要想办法把信息传出去，调动卫所的军队。",
     "宋廷风提出的对策（与许七安的地书方案并列的另一条路）"),
    ("p056_cancelled_plan_to_kill", "巡抚大人原本计划今夜派姜金锣杀了徐虎臣等一干将领",
     "已取消的杀人计划（候选把这条放进 rejectedTasks）"),
    ("p058_laosong_is_right", "老宋有一句话说的对，要把消息传递出去。",
     "许七安对宋廷风提议的采纳"),
    ("p059_yunzhou_not_songs", "云州终究不是姓宋",
     "他对『宋布政使尚未一手遮天』的判断"),
    ("p060_frame_yang_to_purge", "宋布政使陷害杨川南，未必就没有铲除异己的想法",
     "他对陷害动机的反推（带『未必』的不确定标记）"),
    ("p061_yang_cannot_leave", "重伤在身的老杨也不可能出城去。",
     "杨川南这条资源为何不可用"),
    ("p064_guangxiao_only_option", "这条路很危险，但他只能想到这个办法。",
     "朱广孝提议的局限（他只有这一个办法）"),
    ("p066_city_troops_well_armed", "城防军不是乌合之众，装备精良，有弓有火铳。",
     "杀出城这条路的战力对比细节"),
    ("p067_too_late_after_return", "恐怕白帝城内的动乱都已经结束了。",
     "否决杀出城的时延理由"),
    ("p074_crowds_unaware", "街上人流如织，百姓们照常活动，完全没有意识到一场剧变即将拉开序幕。",
     "百姓不知情（与标题的『剧变』形成反差）"),
    ("p075_common_folk_indifferent", "云州不管换不换主人，他们照常生活。",
     "叙述对百姓与政权更迭关系的判断"),
    ("p083_why_so_mysterious", "三号有什么事找二号，这么神秘？",
     "围观者的反应（s5 的 before 侧）"),
    ("p087_this_art_is_annoying", "这种秘术真让人火大啊...",
     "被屏蔽者的直接反应（南疆小蛮妞）"),
    ("p088_mirror_slammed_into_ground", "玉石小镜嵌入地底",
     "小蛮妞摔镜子的后果（i2 只记 use，把这一摔写进 note）"),
    ("p093_womens_sixth_sense", "凭借女人的第六感",
     "李妙真推断的凭据（候选把『第六感』拒绝作为机制）"),
    ("p095_need_me_to_withdraw", "【九：需要我退避吗？】",
     "金莲道长的第三次发言（一处独立的礼貌性动作）"),
    ("p097_jinlian_wont_tell", "放心，贫道不会外传的。",
     "金莲道长的承诺（t2.cost 依赖它）"),
    ("p098_face_stiff", "许七安脸庞呆滞。",
     "他被道长那两句话噎住的反应"),
]


def main():
    docs = json.load(open(DOCS, encoding="utf-8"))
    text = docs[0]["text"]
    slice_ = text[START:END]
    cand = json.load(open(CAND, encoding="utf-8"))

    # 候选里所有引文对象（含 start/end）
    quotes = []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("quote"), str) and "start" in o and "end" in o:
                quotes.append((o["quote"], o["start"], o["end"]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(cand)

    # 候选结论文本：把所有字符串值拼起来（排除 quote 字面量本身，避免自证）
    texty = []

    def walk_text(o, in_quote=False):
        if isinstance(o, dict):
            for k, v in o.items():
                walk_text(v, in_quote or k == "quote")
        elif isinstance(o, list):
            for v in o:
                walk_text(v, in_quote)
        elif isinstance(o, str) and not in_quote:
            texty.append(o)

    walk_text(cand)
    blob = "\n".join(texty)

    zero_listed = {z["text"].strip(): z["para"]
                   for z in (cand.get("coverage", {}) or {}).get("zeroCoverageList", [])}

    results = []
    for key, probe, why in PROBES:
        idx = slice_.find(probe)
        if idx < 0:
            results.append({"key": key, "probe": probe, "foundInSlice": False,
                            "note": "探针不在切片内 —— 我记错了原文，如实登记而不是删掉"})
            continue
        ps, pe = START + idx, START + idx + len(probe)
        hit = [q for q in quotes if q[1] < pe and q[2] > ps]
        # 关键词命中：取探针里的 6 字滑窗做检查。
        #
        # ⚠️ 初版这里用 `sorted({...})` 从 **set** 出发 ⇒ 同一次输入两次运行的顺序不同，
        #    报告因此**不确定**（实测两次运行 sha256 不同、diff 176 行）。
        #    「脚本输出可复现」是这份取证的前提，所以改成从 list 去重 + 固定排序。
        seen_frags, frags = set(), []
        for i in range(0, max(1, len(probe) - 5)):
            f = probe[i:i + 6]
            if f not in seen_frags:
                seen_frags.add(f)
                frags.append(f)
        frags = frags[:4]
        mentioned = [f for f in frags if f in blob]
        # 候选是否已把整段登记进 zeroCoverageList
        zp = None
        for zt, pno in zero_listed.items():
            if zt and (zt in probe or probe in zt):
                zp = pno
                break
        results.append({
            "key": key, "probe": probe, "whyAsk": why, "foundInSlice": True,
            "start": ps, "end": pe,
            "coveredByQuote": len(hit) > 0,
            "coveringQuotes": [{"quote": h[0][:70], "start": h[1], "end": h[2]} for h in hit[:4]],
            "mentionedInConclusionText": mentioned,
            "listedInCandidateZeroCoverage": zp,
        })

    uncov = [r for r in results if r.get("foundInSlice") and not r["coveredByQuote"]]
    uncov_also_unmentioned = [r for r in uncov if not r["mentionedInConclusionText"]]
    out = {
        "method": "自己读切片 → 列 24 条独立探针 → 逐条问『候选有没有引文触及 / 结论文本提到』",
        "probeCount": len(PROBES),
        "foundInSlice": sum(1 for r in results if r.get("foundInSlice")),
        "coveredByQuote": sum(1 for r in results if r.get("coveredByQuote")),
        "notCoveredByQuote": len(uncov),
        "notCoveredAndNotMentioned": len(uncov_also_unmentioned),
        "caveat": ("未覆盖 ≠ 漏读。过场动作、与已覆盖事实同一件事的复述、作者附言都不算漏。"
                   "本清单只回答『有没有被引到』，不回答『该不该被引到』——"
                   "后者留给独立复核者判。"),
        "results": results,
    }
    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("探针 %d 条；切片内命中 %d；被引文触及 %d；未被触及 %d（其中结论文本也未提及 %d）\n"
              % (out["probeCount"], out["foundInSlice"], out["coveredByQuote"],
                 out["notCoveredByQuote"], out["notCoveredAndNotMentioned"]))
        for r in results:
            if not r.get("foundInSlice"):
                print("[!] %-34s 不在切片内（我记错了原文）" % r["key"])
                continue
            mark = "OK " if r["coveredByQuote"] else ("~~ " if r["mentionedInConclusionText"] else "[ ]")
            extra = ""
            if not r["coveredByQuote"]:
                extra = "  ← 未被引文触及"
                if r["mentionedInConclusionText"]:
                    extra += "；结论文本提到：%s" % r["mentionedInConclusionText"][0]
                if r["listedInCandidateZeroCoverage"]:
                    extra += "；候选已在 zeroCoverageList 登记为 P%03d" % r["listedInCandidateZeroCoverage"]
            print("%s%-34s %s%s" % (mark, r["key"], r["probe"][:44], extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
