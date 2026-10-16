#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反向验证：不复用 independent_audit.py 的任何函数，独立重写一遍关键判据。

为什么要有第二个脚本（角色契约要求「反向验证」，只查已写项发现不了遗漏）：
  · independent_audit.py 与 build_candidate.py 都出自我手，可能共享同一个盲点
    ——上一轮的教训就是「机器全绿而语义有 5 处硬错」。所以这里换一套写法重查。
  · 重点不是重复「已写项对不对」，而是问「这一段里还漏了什么」：
    对每个 CE/RC 逐条给可复现命令，证明修好了 / 或证明我漏了。

输出：JSON + 人类可读摘要，退出码 0 = 反向验证通过。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0267.candidate.json"
PRIOR = ROOT / "loop/state/out/read_dafeng_L3_0267.w-dafeng-0.rework/prior_candidate.before_rework.json"
S, E = 1119820, 1125007
HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

fails = []
report = {}


def check(cond, msg):
    if not cond:
        fails.append(msg)
    return cond


def main():
    T = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    SL = T[S:E]
    cand = json.loads(CAND.read_text(encoding="utf-8"))
    out = {}

    # ── 0 源哈希独立复算（用 hashlib 直接读字节，不经 json）
    out["docsSha256"] = hashlib.sha256(DOCS.read_bytes()).hexdigest()
    check(out["docsSha256"] == HASH, "源哈希不符")

    # ── 1 用 **最朴素** 的写法重查引文：不用 walk，手工列出已知的引用容器
    def all_refs():
        for t in cand["tasks"]:
            for f in ("objective", "obstacle", "action", "result", "cost"):
                for r in (t.get(f + "Quotes") or []):
                    yield r
            check(len(t.get("nullFields") or []) ==
                  sum(1 for f in ("objective", "obstacle", "action", "result", "cost") if t.get(f) is None),
                  "%s 的 nullFields 与实际 null 栏不一致" % t["id"])
        for c_ in cand["causeEdges"]:
            for r in c_["quotes"]:
                yield r
            yield c_["triggerRef"]
        for c_ in cand["rejectedEdges"]:
            for r in c_["quotes"]:
                yield r
        for s_ in cand["states"]:
            for k in ("beforeQuotes", "afterQuotes", "anchorQuotes"):
                for r in s_[k]:
                    yield r
        for g in cand["knowledgeGaps"]:
            for r in g["quoteRefs"]:
                yield r
        for f_ in cand["foreshadows"]:
            for r in f_["setupQuotes"] + f_["payoffQuotes"]:
                yield r
        for f_ in cand["notForeshadows"]:
            for r in f_["quotes"]:
                yield r
        for w in cand["worldSettings"]:
            yield w["quote"]
            for r in w["extraQuotes"]:
                yield r
        for w in cand["notWorldSettings"]:
            for r in w["quotes"]:
                yield r
        for t_ in cand["textualNotes"]:
            yield t_["quoteRef"]
            for r in t_["extraQuotes"]:
                yield r
        for u in cand["unknowns"]:
            for r in u["quoteRefs"]:
                yield r
        for sp in cand["speechAsClueNotFact"]:
            yield sp["quoteRef"]

    n, mismatch, outrange, badhash, notfound = 0, [], [], [], []
    for r in all_refs():
        if not isinstance(r, dict) or "quote" not in r:
            notfound.append(repr(r)[:60])
            continue
        n += 1
        q, a, b = r["quote"], r.get("start"), r.get("end")
        if T[a:b] != q:
            mismatch.append((q[:30], a, b))
        if not (S <= a and b <= E):
            outrange.append((q[:30], a, b))
        if r.get("sourceHash") != HASH:
            badhash.append(q[:30])
        # 朴素重查：全文 find 的所有位置里，必须有且仅有 a 落在区间内
        pos = []
        i = T.find(q)
        while i != -1:
            pos.append(i)
            i = T.find(q, i + 1)
        ins = [p for p in pos if S <= p and p + len(q) <= E]
        if not (len(ins) == 1 and ins[0] == a):
            notfound.append((q[:30], len(ins), a))
    out["quoteObjects"] = n
    check(not mismatch, "逐字失配：%r" % mismatch[:3])
    check(not outrange, "越界：%r" % outrange[:3])
    check(not badhash, "sourceHash 不符：%r" % badhash[:3])
    check(not notfound, "朴素重查未唯一命中：%r" % notfound[:3])
    out["resolveFailures"] = len(mismatch) + len(outrange) + len(badhash) + len(notfound)

    # ── 2 CE1：确认候选不再声称存在第二处「假山」写法
    blob = json.dumps(cand, ensure_ascii=False)
    # 先确认候选正文里确实引了假山，且**只在** P022 那一处
    jia = "楚元缜脚下的假山"
    out["jiaShanWholeTextCount"] = T.count(jia)
    out["jiaShanSliceCount"] = T.count(jia, S, E)
    check(T.count(jia) == 1, "「楚元缜脚下的假山」在全书不是唯一一次")
    # 候选里不得把 P049 与假山绑在一起
    for t_ in cand["textualNotes"]:
        pass
    claims = re.findall(r"P0\d\d[^。]{0,40}假山|假山[^。]{0,40}P0\d\d", blob)
    out["p049LikeClaims"] = claims
    # 允许出现的唯一一处 P022 断言
    check(all("P022" in c or "P049" not in c for c in claims) if claims else True,
          "仍有把假山与错误段号绑定的表述：%r" % claims)
    # worldSettings 里解释假山的条目：若引文含**可区分的整串**「楚元缜脚下的假山」，
    # 该串的绝对位置必须正好是 1120637（复核 CE1 认定的唯一位置）。
    # 注意「假山」二字本身在 1120643（整串内偏移 6），拿它当锚点会算错——
    # 这正是上一版检查的假阳性来源。
    ws_jia = [w for w in cand["worldSettings"] if "假山" in json.dumps(w, ensure_ascii=False)]
    for w in ws_jia:
        for r in [w["quote"]] + w["extraQuotes"]:
            k = r["quote"].find("楚元缜脚下的假山")
            if k >= 0:
                check(r["start"] + k == 1120637,
                      "%s 的「楚元缜脚下的假山」落在 %d，应为 1120637" % (w["id"], r["start"] + k))
    out["worldSettingsMentioningJiaShan"] = [w["id"] for w in ws_jia]
    out["jiaShanAnchor"] = 1120637
    out["jiaShanSubstringAnchor"] = T.find("假山", 1120637)
    check("复述版本" not in blob.replace(cand["reworkReason"], ""),
          "候选正文仍出现「复述版本」")

    # ── 3 CE2：T10 回复条数与名单，独立用正则枚举
    senders = re.findall(r"【([^：】]+)：", SL)
    replies = [x for x in senders if x != "五"]
    out["senders"] = senders
    out["replies"] = replies
    t10 = [t for t in cand["tasks"] if t["id"] == "T10"][0]
    zh = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    m = re.search(r"收到(.)条回复", t10["result"])
    check(bool(m), "T10.result 未写条数")
    if m:
        check(zh.get(m.group(1)) == len(replies),
              "T10.result 条数 %s != 实际 %d" % (m.group(1), len(replies)))
    for s in replies:
        check("【%s】" % s in t10["result"], "T10.result 漏【%s】" % s)
    # 逐条回复者是否都有 resultQuotes 落在其消息区间
    spans = [(mm.group(1), S + mm.start(), S + mm.end())
             for mm in re.finditer(r"【([^：】]+)：(.+?)】", SL, re.S)]
    cov = set()
    for r in t10["resultQuotes"]:
        for s, a, b in spans:
            if not (r["end"] <= a or r["start"] >= b):
                cov.add(s)
    cov.discard("五")
    out["t10CoveredSenders"] = sorted(cov)
    for s in replies:
        check(s in cov, "T10.resultQuotes 未覆盖【%s】" % s)

    # ── 4 CE3：RE04 不得把叙述层当台词
    re04 = [r for r in cand["rejectedEdges"] if r["id"] == "RE04"][0]
    # 判据是「有没有把它**肯定地**说成台词」。说「不是元景帝的台词」是正确的否定，
    # 上一版用 `"台词" not in whyNot` 把否定句也判失败，是假阳性。
    affirmative = re.findall(r"[^不非]是[^，。]{0,12}台词|台词[里中]", re04["whyNot"])
    check(not [a for a in affirmative if "不是" not in a and "台词里" not in
               re04["whyNot"].replace("不是元景帝的台词", "")],
          "RE04 仍把叙述肯定地说成台词：%r" % affirmative)
    check("不是元景帝的台词" in re04["whyNot"] or "叙述层" in re04["whyNot"],
          "RE04 未纠正层级归属：%s" % re04["whyNot"][:80])
    # 该句在原文里的位置必须在引号开启之前
    q = "元景帝和洛玉衡只好顿足"
    p = T.find(q)
    upto = T[p:p + 60]
    check("“" not in upto.split("点着头道：")[0], "该句之后、台词开启之前的文本里出现了引号")

    # ── 5 CE4：boundaryTail 与切片真实尾部
    tail = SL[-14:]
    check(cand["source"]["boundaryTail"] == tail,
          "boundaryTail %r != %r" % (cand["source"]["boundaryTail"], tail))
    dashes = len(SL.rstrip("\n")) - len(SL.rstrip("\n").rstrip("-"))
    check(cand["source"]["boundaryTailDashes"] == dashes,
          "dashes %r != %d" % (cand["source"]["boundaryTailDashes"], dashes))
    out["boundaryTail"], out["dashes"] = tail, dashes

    # ── 6 CE5：null 栏理由（与 build 侧不同的写法：查占位符模式 + 信息量）
    nulls = []
    for t in cand["tasks"]:
        for f in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(f) is None:
                note = (t.get(f + "Note") or "").strip()
                nulls.append((t["id"], f, len(note)))
                check(note != f + "Note", "%s.%s Note 是字段名" % (t["id"], f))
                check(len(note) >= 30, "%s.%s Note 过短(%d)" % (t["id"], f, len(note)))
                # 必须解释「为什么没有」，而不是复述栏位名
                check(any(k in note for k in ("未出现", "没有", "无", "不")),
                      "%s.%s Note 未说明为什么没有" % (t["id"], f))
    out["nullFields"] = ["%s.%s(len=%d)" % x for x in nulls]
    check(len(nulls) >= 1, "一个 null 栏都没有，可疑（任务允许 null）")

    # ── 7 反向：候选**漏了什么**？逐条对照两条复核的 RC
    rc_probes = {
        "RC1/RC3 喜剧节拍（喷茶/手帕/拒绝回答）": ["一口茶", "手帕", "您继续说"],
        "RC2 许七安当场反驳（妖族/混血）": ["妖族", "混血", "沉吟许久"],
        "RC3 顿足链": ["顿足", "卑职参加陛下"],
        "RC4 许二郎": ["许二郎"],
        "RC5 人口对比": ["百万人口", "千万人口", "心头之患"],
        "RC6 表情链": ["皱眉不解", "展眉微笑"],
        "RC7 甘拜下风主客归属": ["许某甘拜下风"],
    }
    rc_cov = {}
    for label, probes in rc_probes.items():
        hit = [p for p in probes if p in blob]
        rc_cov[label] = "%d/%d %r" % (len(hit), len(probes), hit)
        check(len(hit) == len(probes), "RC 覆盖不全 %s -> %s" % (label, rc_cov[label]))
    out["reverseCheckCoverage"] = rc_cov

    # ── 8 反向：与上一轮候选相比，哪些上一轮有而本轮没有的**实质内容**？
    # 只做信息性对比，不判失败（本轮换了结构，条目名不同）。
    if PRIOR.exists():
        prior = json.loads(PRIOR.read_text(encoding="utf-8"))
        pb = json.dumps(prior, ensure_ascii=False)
        out["priorQuoteObjects"] = len(re.findall(r'"sourceHash"', pb))
        out["thisQuoteObjects"] = len(re.findall(r'"sourceHash"', blob))
        # 上一轮引过、本轮没引的原文子串（抽样：按引文区间取原文片段）
        prior_ivs = set()
        for mm in re.finditer(r'"start":\s*(\d+),\s*"end":\s*(\d+)', pb):
            prior_ivs.add((int(mm.group(1)), int(mm.group(2))))
        now_ivs = set()
        for mm in re.finditer(r'"start":\s*(\d+),\s*"end":\s*(\d+)', blob):
            now_ivs.add((int(mm.group(1)), int(mm.group(2))))
        dropped = sorted(prior_ivs - now_ivs)
        out["priorIntervals"] = len(prior_ivs)
        out["thisIntervals"] = len(now_ivs)
        out["droppedIntervalCount"] = len(dropped)
        out["droppedSample"] = [T[a:b][:26] for a, b in dropped[:12]]

    # ── 9 反向：本区间是否还有**零引用**的实质段落（不是省略号/单字感叹）
    ivs = sorted(now_ivs if PRIOR.exists() else set())
    merged = []
    for a, b in ivs:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    paras, i, idx = [], 0, 0
    for part in SL.split("\n"):
        st = S + i
        if part.strip():
            paras.append((idx, st, st + len(part), part.strip()))
            idx += 1
        i += len(part) + 1
    zero = [(p, x) for p, a, b, x in paras
            if not any(not (y <= a or x2 >= b) for x2, y in merged)]
    # 只把「长度 >= 20 且不是纯省略号/标点」的算作实质遗漏
    subst = [(p, x) for p, x in zero
             if len(x) >= 20 and re.search(r"[\u4e00-\u9fff]", x)
             and not re.fullmatch(r"[.\s]+", x)]
    out["zeroCoveredCount"] = len(zero)
    out["zeroCoveredSubstantive"] = ["P%03d %s" % (p, x[:34]) for p, x in subst]
    check(len(subst) <= 12,
          "零引用的实质段落偏多（%d 段），可能有整段遗漏：%r"
          % (len(subst), out["zeroCoveredSubstantive"][:8]))

    # ── 10 分区键
    for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
        check(k in cand, "缺分区 %s" % k)
    out["sections"] = {k: len(cand.get(k) or []) for k in
                       ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
                        "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
                        "themeReadings", "textualNotes", "unknowns", "selfCritique")}

    # ── 11 semanticReview 不得写成完成
    check(cand.get("semanticReview") != "completed" and
          cand.get("semanticReview") != "done", "semanticReview 被写成完成")
    out["semanticReview"] = cand.get("semanticReview")

    print(json.dumps(out, ensure_ascii=False, indent=1))
    print()
    if fails:
        print("反向验证不通过，共 %d 条：" % len(fails))
        for f in fails:
            print("  ✗ %s" % f)
        return 1
    print("反向验证通过：%d 个引文对象朴素重查全部唯一命中；5 条 CE 逐条复现已修；"
          "7 组 RC 全部覆盖；零引用实质段落 %d 段。" % (n, len(subst)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
