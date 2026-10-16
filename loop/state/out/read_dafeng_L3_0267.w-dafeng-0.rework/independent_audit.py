#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计 read_dafeng_L3_0267.candidate.json（不 import build_candidate.py）。

审计目标（每条对应一次真实事故或本轮复核的判决）：
  A 引文层：每个含 quote+start+end 的对象，docs[0].text[start:end] == quote 逐字成立；
    且整段落在 [1119820,1125007) 内；sourceHash 必须等于任务声明的哈希。
  B 解析层：不依赖候选自报的偏移，重新在全文里 find(quote)，
    要求「全文命中集合 ∩ 本区间」只有 1 个且等于候选给的 start。
  C 五栏分列：tasks 的五栏不得共用同一句引文（复核实测旧图谱 714/1664 共用）。
  D null 栏：值必须为 null，且 <栏>Note 必须是**理由**——
    不是字段名占位符（上一轮 CE1/CE5 的缺陷形态），长度 >= 20 字，
    且不得等于 "<栏>Note" 本身。
  E 标题/边界：source.boundaryHead 是切片开头；boundaryTail 必须逐字等于切片真实尾部
    （上一轮 CE4：自述 10 个破折号，实际 12 个）。
  F 分区键：任务 prompt 要求的 6 个顶层分区必须存在（可为空数组）。
  G 台词纪律：speechAsClueNotFact 里的每条 quote 都能逐字 find。
  H T10.result 的回复条数与名单：用 `【X：` 正则独立枚举，不采信候选自报。
  I worldSettings 三态字段：place 必须有 placeState ∈ {arrived, mentioned}；
    item 必须有非空 itemStates ⊆ {hold,transfer,use,lose}；
    rule 必须有 institution ∈ {declared,executed,misunderstood}，且 explain 非空。
  J 覆盖率：统计引文并集、未覆盖段，与服务端无关，纯本地复算。

只读，不写。退出码 0 = 全绿；非 0 = 有问题（逐条打印）。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0267.candidate.json"
S, E = 1119820, 1125007
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
WANT_SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]

problems = []
stats = {}


def bad(msg):
    problems.append(msg)


def _has_ref(cand, dotted):
    """按点分路径取值，判断它是否是合法的引用对象（含 quote+start+end）。"""
    cur = cand
    for part in dotted.split(".")[1:]:      # 跳过 'cand'
        m = re.match(r"^([^\[\]]+)((?:\[\d+\])*)$", part)
        if not m:
            return False
        name, idxs = m.group(1), m.group(2)
        if not isinstance(cur, dict) or name not in cur:
            return False
        cur = cur[name]
        for i in re.findall(r"\[(\d+)\]", idxs):
            if not isinstance(cur, list) or int(i) >= len(cur):
                return False
            cur = cur[int(i)]
    if isinstance(cur, dict):
        return all(k in cur for k in ("quote", "start", "end"))
    if isinstance(cur, list):
        return bool(cur) and all(isinstance(x, dict) and "start" in x and "end" in x for x in cur)
    return False


def _get(cand, dotted):
    cur = cand
    for part in dotted.split(".")[1:]:
        m = re.match(r"^([^\[\]]+)((?:\[\d+\])*)$", part)
        if not m or not isinstance(cur, dict) or m.group(1) not in cur:
            return None
        cur = cur[m.group(1)]
        for i in re.findall(r"\[(\d+)\]", m.group(2)):
            if not isinstance(cur, list) or int(i) >= len(cur):
                return None
            cur = cur[int(i)]
    return cur


def _ref_matches(cand, head, quotepath):
    """裸串 <field> 与其 <field>Ref.quote 必须逐字相同。"""
    node = _get(cand, head)
    if not isinstance(node, dict):
        return False
    raw = node.get("quote")
    r = node.get("quoteRef") or {}
    return isinstance(raw, str) and raw == r.get("quote")


def walk_quotes(obj, path="cand"):
    """递归找出所有含 quote+start+end 的对象。"""
    if isinstance(obj, dict):
        if "quote" in obj and "start" in obj and "end" in obj and isinstance(obj.get("quote"), str):
            yield path, obj
        for k, v in obj.items():
            yield from walk_quotes(v, "%s.%s" % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_quotes(v, "%s[%d]" % (path, i))


def main():
    T = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    SLICE = T[S:E]
    cand = json.loads(CAND.read_text(encoding="utf-8"))

    # 源哈希（独立重算）
    file_hash = hashlib.sha256(DOCS.read_bytes()).hexdigest()
    stats["docsJsonSha256"] = file_hash
    if file_hash != SOURCE_HASH:
        bad("A0 docs.json 哈希与任务声明不符：%s" % file_hash)
    if len(SLICE) != 5187:
        bad("A0b 切片长度 %d != 5187" % len(SLICE))

    # ── A + B 引文层
    n_q = 0
    fails_a, fails_b, fails_hash, fails_range = [], [], [], []
    for path, o in walk_quotes(cand):
        n_q += 1
        st, en, q = o["start"], o["end"], o["quote"]
        if not (isinstance(st, int) and isinstance(en, int)):
            fails_a.append((path, "start/end 非整数"))
            continue
        if T[st:en] != q:
            fails_a.append((path, repr(T[st:en])[:60], repr(q)[:60]))
        if not (S <= st and en <= E):
            fails_range.append((path, st, en))
        if o.get("sourceHash") != SOURCE_HASH:
            fails_hash.append((path, o.get("sourceHash")))
        # B 独立重解析
        hits = [m.start() for m in re.finditer(re.escape(q), T)]
        ins = [h for h in hits if S <= h and h + len(q) <= E]
        if len(ins) != 1 or ins[0] != st:
            fails_b.append((path, ins, st))
    stats["quoteObjects"] = n_q
    if fails_a:
        bad("A 逐字失配 %d 处，例：%r" % (len(fails_a), fails_a[:3]))
    if fails_range:
        bad("A 越界 %d 处，例：%r" % (len(fails_range), fails_range[:3]))
    if fails_hash:
        bad("A sourceHash 不符 %d 处，例：%r" % (len(fails_hash), fails_hash[:3]))
    if fails_b:
        bad("B 独立重解析不一致 %d 处，例：%r" % (len(fails_b), fails_b[:3]))
    stats["resolveFailures"] = len(fails_a) + len(fails_b) + len(fails_range) + len(fails_hash)

    # ── C 五栏分列（禁止同一句同时充当多栏依据）
    # 判据比「start/end 相等」更严：**任意区间相交**都算复用。
    # 理由：把 A 栏的依据做成 B 栏依据的真子串（例如整句 vs 半句），
    # 在「同一句话」的语义下仍然是复用，只查相等会放过它。
    FIELDS = ("objective", "obstacle", "action", "result", "cost")

    def intervals(refs):
        return [(r["start"], r["end"]) for r in (refs or [])]

    def overlap(a, b):
        return not (a[1] <= b[0] or b[1] <= a[0])

    overlaps = []
    for t in cand["tasks"]:
        byfield = {f: intervals(t.get(f + "Quotes")) for f in FIELDS}
        for i, f1 in enumerate(FIELDS):
            for f2 in FIELDS[i + 1:]:
                for a in byfield[f1]:
                    for b in byfield[f2]:
                        if overlap(a, b):
                            overlaps.append((t["id"], f1, f2, a, b))
    stats["taskFieldOverlaps"] = len(overlaps)
    if overlaps:
        bad("C 同一引文跨栏复用（任意相交）%d 处：%r" % (len(overlaps), overlaps[:5]))
    # 栏内自相交（同一栏引了互相嵌套的两段）只报数，不判失败
    inner = 0
    for t in cand["tasks"]:
        for f in FIELDS:
            iv = intervals(t.get(f + "Quotes"))
            for i in range(len(iv)):
                for j in range(i + 1, len(iv)):
                    if overlap(iv[i], iv[j]):
                        inner += 1
    stats["intraFieldNestedPairs"] = inner

    # 跨任务复用：同一区间被多于 2 个任务引用（1 个不算问题，同一事实可被两条任务共享）
    cross = {}
    for t in cand["tasks"]:
        for f in FIELDS:
            for r in (t.get(f + "Quotes") or []):
                cross.setdefault((r["start"], r["end"]), set()).add(t["id"])
    dup_across = {k: sorted(v) for k, v in cross.items() if len(v) > 2}
    stats["intervalUsedByMoreThan2Tasks"] = len(dup_across)

    # ── D null 栏
    nulls = []
    for t in cand["tasks"]:
        for f in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(f) is None:
                note = t.get(f + "Note")
                nulls.append((t["id"], f, note))
                if not isinstance(note, str) or not note.strip():
                    bad("D %s.%s 为 null 但无 Note" % (t["id"], f))
                elif note.strip() == f + "Note":
                    bad("D %s.%s 的 Note 是字段名占位符（上一轮 CE1/CE5 的缺陷）" % (t["id"], f))
                elif len(note.strip()) < 20:
                    bad("D %s.%s 的 Note 过短（%d 字），疑似占位符：%r"
                        % (t["id"], f, len(note.strip()), note))
            else:
                if not (t.get(f + "Quotes") or []):
                    bad("D %s.%s 非 null 但无引文依据（禁止无据断言）" % (t["id"], f))
    stats["nullFields"] = len(nulls)
    stats["nullFieldList"] = ["%s.%s" % (a, b) for a, b, _ in nulls]
    stats["nullNoteLens"] = {("%s.%s" % (a, b)): len((c or "").strip()) for a, b, c in nulls}

    # ── E 标题 / 边界
    src = cand["source"]
    if not SLICE.startswith(src["boundaryHead"]):
        bad("E boundaryHead 不是切片开头：%r" % src["boundaryHead"])
    if not src.get("boundaryHeadMatchesTitle"):
        bad("E boundaryHeadMatchesTitle 为假")
    if src["boundaryTail"] != SLICE[-len(src["boundaryTail"]):]:
        bad("E boundaryTail 不等于切片真实尾部：声明 %r 实际 %r"
            % (src["boundaryTail"], SLICE[-len(src["boundaryTail"]):]))
    real_dashes = len(SLICE.rstrip("\n")) - len(SLICE.rstrip("\n").rstrip("-"))
    if src.get("boundaryTailDashes") != real_dashes:
        bad("E boundaryTailDashes 声明 %r 实际 %d" % (src.get("boundaryTailDashes"), real_dashes))
    stats["boundaryTail"] = src["boundaryTail"]
    stats["boundaryTailDashes"] = real_dashes
    stats["sliceSha256"] = hashlib.sha256(SLICE.encode()).hexdigest()
    if src.get("sliceSha256") != stats["sliceSha256"]:
        bad("E sliceSha256 不符")

    # ── F 分区键
    missing = [k for k in WANT_SECTIONS if k not in cand]
    if missing:
        bad("F 缺顶层分区：%r" % missing)
    stats["sections"] = {k: (len(cand[k]) if isinstance(cand.get(k), list) else "n/a")
                         for k in WANT_SECTIONS}

    # ── G 台词纪律
    sp_bad = []
    for x in cand.get("speechAsClueNotFact") or []:
        r = x.get("quoteRef") or {}
        if T[r.get("start", -1):r.get("end", -1)] != x["quote"]:
            sp_bad.append(x.get("id"))
    if sp_bad:
        bad("G speechAsClueNotFact 引文失配：%r" % sp_bad)
    stats["speechEntries"] = len(cand.get("speechAsClueNotFact") or [])

    # ── G2 「引文字符串但没带 start/end」的漏网对象（未被 walk_quotes 覆盖的）
    # 这条是上一版审计的真实盲点：worldSettings[].quote 曾被写成裸字符串，
    # walk_quotes 只找「quote+start+end」齐全的对象，于是它整条没被检查，
    # 而审计仍报「全绿」。凡是键名以 Quote/quote 结尾、值是 str 的，都必须被引用化。
    loose = []

    def walk_loose(obj, path="cand"):
        if isinstance(obj, dict):
            # 这个 dict 本身是不是一个合法的引用对象？是则它内部的 quote 已被覆盖。
            is_ref = all(k in obj for k in ("quote", "start", "end"))
            for k, v in obj.items():
                p = "%s.%s" % (path, k)
                if isinstance(v, str) and k.lower().endswith("quote"):
                    if not is_ref:
                        loose.append((p, v[:40]))
                elif isinstance(v, list) and v and all(isinstance(z, str) for z in v) \
                        and k.lower().endswith("quotes"):
                    loose.append((p + "[]", v[0][:40]))
                else:
                    walk_loose(v, p)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk_loose(v, "%s[%d]" % (path, i))

    walk_loose(cand)
    # 例外：成对出现 <field> 与 <field>Ref 的写法（quote/quoteRef）——
    # 裸字符串本身是给人读的冗余副本，只要同级的 Ref 是合法引用对象就不算漏网。
    # 审计要求的是「每一处引文都有可核验的偏移」，不是「每一处引文只能出现一次」。
    real_loose = []
    for p, s in loose:
        head = p.rsplit(".", 1)[0]
        if p.endswith(".quote"):
            # 形如 <field> 与 <field>Ref 成对：裸串是给人读的副本，
            # 只要同级 Ref 是合法引用、且两者指向同一段文字，就算已被覆盖。
            if _has_ref(cand, head + ".quoteRef"):
                if not _ref_matches(cand, head, p):
                    bad("G2 %s 的裸串与其 quoteRef 不一致" % p)
                continue
        if p.endswith("Quotes[]") and _has_ref(cand, head):
            continue
        real_loose.append((p, s))
    stats["looseQuoteStrings"] = len(loose)
    stats["looseQuoteStringsUnbacked"] = len(real_loose)
    if real_loose:
        bad("G2 存在未引用化的引文字符串（缺 start/end，审计不到）%d 处，例：%r"
            % (len(real_loose), real_loose[:5]))

    # ── H T10.result 回复条数（独立枚举，不采信自报）
    senders = re.findall(r"【([^：】]+)：", SLICE)
    replies = [x for x in senders if x != "五"]
    stats["senders"] = senders
    stats["replyCount"] = len(replies)
    t10 = [t for t in cand["tasks"] if t["id"] == "T10"][0]
    m = re.search(r"收到(\S+?)条回复", t10["result"])
    if not m:
        bad("H T10.result 未写明回复条数：%r" % t10["result"][:60])
    else:
        num = m.group(1)
        zh = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        got = zh.get(num[-1]) if num[-1] in zh else None
        if got != len(replies):
            bad("H T10.result 声明 %s 条，独立枚举为 %d 条（%r）" % (num, len(replies), replies))
    for s in replies:
        if "【%s】" % s not in t10["result"]:
            bad("H T10.result 名单漏掉【%s】" % s)
    # resultQuotes 必须覆盖每个回复者：按**实际消息区间**归属，
    # 而不是「引文串里是否出现 【X：」——后者会被跨消息的长引文骗过。
    # 做法：把切片里每条传书按 `【X：…】` 切成区间，再看候选引文落在谁的区间内。
    msg_spans = []
    for m in re.finditer(r"【([^：】]+)：(.+?)】", SLICE, re.S):
        msg_spans.append((m.group(1), S + m.start(), S + m.end()))
    covered = set()
    for r in t10["resultQuotes"]:
        a, b = r["start"], r["end"]
        for s, ma, mb in msg_spans:
            if not (b <= ma or a >= mb):        # 与某条消息相交
                covered.add(s)
    covered.discard("五")
    stats["T10resultQuotesCoverSenders"] = sorted(covered)
    for s in replies:
        if s not in covered:
            bad("H T10.resultQuotes 未覆盖【%s】的传书原文（按消息区间归属）" % s)

    # ── I worldSettings 三态字段
    for w in cand["worldSettings"]:
        k = w.get("kind")
        if k not in ("rule", "place", "item"):
            bad("I %s kind 非法：%r" % (w.get("id"), k))
            continue
        if not w.get("explain"):
            bad("I %s 缺 explain" % w.get("id"))
        if k == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                bad("I %s placeState 非法/缺失：%r" % (w["id"], w.get("placeState")))
            if not w.get("placeStateWhy"):
                bad("I %s 缺 placeStateWhy（三态区分必须写进字段）" % w["id"])
        elif k == "item":
            states = w.get("itemStates")
            if not isinstance(states, list) or not states or any(
                    s not in ("hold", "transfer", "use", "lose") for s in states):
                bad("I %s itemStates 非法/缺失：%r" % (w["id"], states))
            if not w.get("itemStatesWhy"):
                bad("I %s 缺 itemStatesWhy" % w["id"])
        elif k == "rule":
            if w.get("institution") not in ("declared", "executed", "misunderstood"):
                bad("I %s institution 非法/缺失：%r" % (w["id"], w.get("institution")))
            if not w.get("institutionNote"):
                bad("I %s 缺 institutionNote" % w["id"])
    stats["worldSettingsKinds"] = {}
    for w in cand["worldSettings"]:
        stats["worldSettingsKinds"][w["kind"]] = stats["worldSettingsKinds"].get(w["kind"], 0) + 1
    stats["placeStates"] = {w["id"]: w.get("placeState") for w in cand["worldSettings"] if w["kind"] == "place"}
    stats["itemStates"] = {w["id"]: w.get("itemStates") for w in cand["worldSettings"] if w["kind"] == "item"}
    stats["institutions"] = {w["id"]: w.get("institution") for w in cand["worldSettings"] if w["kind"] == "rule"}

    # ── J 覆盖率（本地复算）
    ivs = sorted(set((o["start"], o["end"]) for _, o in walk_quotes(cand)))
    merged = []
    for a, b in ivs:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    union = sum(b - a for a, b in merged)
    stats["uniqueQuoteIntervals"] = len(ivs)
    stats["quoteUnionCodepoints"] = union
    stats["quoteUnionRatioOfSlice"] = round(union / len(SLICE), 4)
    stats["nonSpaceCodepoints"] = sum(1 for c in SLICE if not c.isspace())
    stats["quoteUnionRatioOfNonSpace"] = round(union / stats["nonSpaceCodepoints"], 4)

    # 未覆盖段
    paras, i, idx = [], 0, 0
    for part in SLICE.split("\n"):
        st = S + i
        if part.strip():
            paras.append((idx, st, st + len(part), part))
            idx += 1
        i += len(part) + 1
    stats["paragraphs"] = len(paras)
    zero = []
    for pid, a, b, txt in paras:
        if not any(not (y <= a or x >= b) for x, y in merged):
            zero.append(pid)
    stats["zeroCoveredParagraphs"] = zero
    stats["zeroCoveredCount"] = len(zero)
    stats["paragraphsTouched"] = len(paras) - len(zero)

    # ── K 每条 tasks 的 basis 合法性
    for t in cand["tasks"]:
        for f in ("objective", "obstacle", "action", "result", "cost"):
            b = t.get(f + "Basis")
            if t.get(f) is None:
                continue
            if b not in ("explicit", "inferred", "derived", "unverified"):
                bad("K %s.%sBasis 非法：%r" % (t["id"], f, b))

    # ── L 伏笔：未回收必须显式标 unresolved
    for f in cand["foreshadows"]:
        if f.get("payoff") is None and f.get("status") != "unresolved":
            bad("L %s 无 payoff 但 status != unresolved（%r）" % (f.get("id"), f.get("status")))
        if not f.get("setupQuotes"):
            bad("L %s 无 setup 引文" % f.get("id"))
        if not f.get("unresolvedWhat"):
            bad("L %s 缺 unresolvedWhat" % f.get("id"))
    stats["foreshadowStatus"] = {f["id"]: f.get("status") for f in cand["foreshadows"]}

    # ── M themeReadings：必须有 perspective/support/counter 三件
    for x in cand["themeReadings"]:
        for k in ("perspective", "support", "counter"):
            if not x.get(k):
                bad("M %s 缺 %s（三件缺一就不该写）" % (x.get("id"), k))
    stats["themeReadings"] = len(cand["themeReadings"])
    if len(cand["themeReadings"]) > 2:
        bad("M themeReadings 超过 2 条")

    # ── N 候选合计（供提交记录引用）
    stats["tasksWithNullCount"] = sum(1 for t in cand["tasks"] if t["nullFields"])
    stats["semanticReview"] = cand.get("semanticReview")

    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print()
    if problems:
        print("审计不通过，共 %d 条：" % len(problems))
        for p in problems:
            print("  ✗ %s" % p)
        return 1
    print("审计通过：引文 %d 个对象全部逐字命中且偏移自洽；null 栏 %d 个均有理由；"
          "五栏零复用；边界/标题/哈希一致。" % (n_q, len(nulls)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
