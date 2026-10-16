# -*- coding: utf-8 -*-
"""read:dafeng:L1:0241 候选的**独立**审计。

独立性的具体含义（否则「审计」只是把生成脚本再跑一遍）：
  · 自己读 data/cache/*.docs.json，不 import build_candidate / content_core，
    不复用它们的任何函数或常量；
  · 自己用显式栈遍历候选 JSON（不写死分区路径），凡是形如
    {quote,start,end,sourceHash} 的对象一律检查；
  · 自己重算 docs.json 与切片的 sha256；
  · 附**负控**：故意构造 5 类已知坏输入，确认本审计真的会报错
    （负控不通过的审计等于没有审计）。

退出码 0 = 全部通过；1 = 有失败；2 = 负控自身失败。
"""
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DOCS = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop", "state", "out", "read_dafeng_L1_0241.candidate.json")
EXPECT_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 967253, 977104

fails = []
checks = [0]


def ck(cond, msg):
    checks[0] += 1
    if not cond:
        fails.append(msg)
    return cond


def walk_refs(node, path, sink, bare=None):
    """不写死分区：任何「引用对象」都收集起来。

    两种真实形态必须分开，否则审计自己会造假阳性（第一版实测过）：
      · 引用对象：{quote, start, end, sourceHash} —— worldSettings 之外各处用它；
      · worldSettings 条目：顶层是**提示词要求的字符串字段** quote（无偏移），
        真正的引用在同级 quoteRef 里。
    区分判据是「有没有 start/end/sourceHash」，不是「有没有 quote」。
    """
    if isinstance(node, dict):
        if "quote" in node and isinstance(node["quote"], str):
            if any(k in node for k in ("start", "end", "sourceHash")):
                sink.append((path, node))
            elif bare is not None:
                bare.append((path, node))
        for k, v in node.items():
            walk_refs(v, "%s.%s" % (path, k), sink, bare)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_refs(v, "%s[%d]" % (path, i), sink, bare)


def audit_refs(text, cand):
    """返回 (引用对象数, 去重子串数, 问题列表)。独立于生成脚本的判据。"""
    refs = []
    bare = []
    walk_refs(cand, "$", refs, bare)
    probs = []
    uniq = set()
    for path, r in refs:
        q = r["quote"]
        st, en, sh = r.get("start"), r.get("end"), r.get("sourceHash")
        if not isinstance(st, int) or not isinstance(en, int):
            probs.append("%s start/end 不是整数：%r %r" % (path, st, en))
            continue
        if en - st != len(q):
            probs.append("%s end-start=%d 与 quote 长度 %d 不符" % (path, en - st, len(q)))
        if text[st:en] != q:
            probs.append("%s text[start:end] != quote：%r" % (path, text[st:en][:30]))
        if sh != EXPECT_HASH:
            probs.append("%s sourceHash 不符：%r" % (path, sh))
        # 区间内唯一命中（去重后同一 quote 只算一次）
        if q not in uniq:
            uniq.add(q)
            hits = []
            i = text.find(q)
            while i >= 0:
                hits.append(i)
                i = text.find(q, i + 1)
            inside = [h for h in hits if S <= h and h + len(q) <= E]
            if len(inside) != 1:
                probs.append("%s 区间内命中 %d 次：%r" % (path, len(inside), q[:30]))
            elif inside[0] != st:
                probs.append("%s 偏移不是首次命中：声明 %d 实际 %d" % (path, st, inside[0]))
        # 不得越出本区间
        if not (S <= st and en <= E):
            probs.append("%s 越出区间 [%d,%d)：[%d,%d)" % (path, S, E, st, en))
    return len(refs), len(uniq), probs


def audit_bare_quotes(cand, text):
    """带裸 quote 字符串（无偏移）的节点，必须另有一个真实 quoteRef 与之逐字相同。

    worldSettings 的提示词格式是 `quote` + `explain`，偏移不在 quote 上；
    如果只检查「quote 字段存在」，一个抄错的 quote 就能骗过审计。
    """
    refs, bare = [], []
    walk_refs(cand, "$", refs, bare)
    # 裸 quote 节点的 path 就是**它所属的那一条**（walk_refs 在 dict 自己身上登记），
    # 因此同级引用是 path + ".quoteRef"。第一版误用 rsplit 砍掉一层，
    # 于是合法的裸 quote 被误报 —— 负控里的「正控」正是用来抓这种自伤的。
    ref_by_path = {p: r for p, r in refs if p.endswith(".quoteRef")}
    probs = []
    for path, node in bare:
        ref = ref_by_path.get(path + ".quoteRef")
        if ref is None:
            probs.append("%s 有裸 quote 却没有同级 quoteRef（引用不可校验）" % path)
            continue
        if ref["quote"] != node["quote"]:
            probs.append("%s 的 quote 与 quoteRef.quote 不一致：%r vs %r"
                         % (path, node["quote"][:30], ref["quote"][:30]))
    return len(bare), probs


def negative_controls(text):
    """5 类已知坏输入，必须全部被抓出来。"""
    base = {"quote": "许七安", "start": 0, "end": 3, "sourceHash": EXPECT_HASH}
    q = "“大锅！”"
    good_start = text.find(q, S, E)
    cases = [
        ("错偏移", {"quote": q, "start": good_start + 1, "end": good_start + 1 + len(q), "sourceHash": EXPECT_HASH}),
        ("错哈希", {"quote": q, "start": good_start, "end": good_start + len(q), "sourceHash": "0" * 64}),
        ("长度不符", {"quote": q, "start": good_start, "end": good_start + len(q) + 2, "sourceHash": EXPECT_HASH}),
        ("越界引用", {"quote": text[E:E + 10], "start": E, "end": E + 10, "sourceHash": EXPECT_HASH}),
        ("区间外命中", {"quote": text[965371:965371 + 12], "start": 965371, "end": 965371 + 12, "sourceHash": EXPECT_HASH}),
    ]
    ok = True
    for name, ref in cases:
        _, _, probs = audit_refs(text, {"x": ref})
        if not probs:
            print("  负控失败：%s 没有被抓出来 %r" % (name, ref["quote"][:20]))
            ok = False
        else:
            print("  负控 OK：%s 被抓出 %d 条" % (name, len(probs)))
    # 正控：合法引用必须零问题
    _, _, probs = audit_refs(text, {"x": {"quote": q, "start": good_start, "end": good_start + len(q),
                                          "sourceHash": EXPECT_HASH}})
    if probs:
        print("  正控失败：合法引用被误报 %r" % probs)
        ok = False
    else:
        print("  正控 OK：合法引用零问题")

    # 裸 quote 的负控：抄错的 quote / 缺 quoteRef 都必须被抓出来
    goodref = {"quote": q, "start": good_start, "end": good_start + len(q), "sourceHash": EXPECT_HASH}
    bare_cases = [
        ("裸quote抄错", {"quote": q + "错", "quoteRef": goodref}),
        ("裸quote缺quoteRef", {"quote": q}),
        ("裸quote与quoteRef不一致", {"quote": text[S:S + 6], "quoteRef": goodref}),
    ]
    for name, node in bare_cases:
        _, bprobs = audit_bare_quotes({"w": node}, text)
        if not bprobs:
            print("  负控失败：%s 没有被抓出来" % name)
            ok = False
        else:
            print("  负控 OK：%s 被抓出 %d 条" % (name, len(bprobs)))
    _, bprobs = audit_bare_quotes({"w": {"quote": q, "quoteRef": goodref}}, text)
    if bprobs:
        print("  正控失败：合法的裸 quote + quoteRef 被误报 %r" % bprobs)
        ok = False
    else:
        print("  正控 OK：裸 quote + quoteRef 零问题")
    return ok


def main():
    print("== 1. 独立复算哈希")
    raw = open(DOCS, "rb").read()
    h = hashlib.sha256(raw).hexdigest()
    ck(h == EXPECT_HASH, "docs.json sha256 不符：%s" % h)
    docs = json.loads(raw.decode("utf-8"))
    text = docs[0]["text"]
    print("  docs.json sha256 = %s" % h)
    print("  全文码点 = %d" % len(text))
    slice_text = text[S:E]
    slice_hash = hashlib.sha256(slice_text.encode("utf-8")).hexdigest()
    ck(slice_text.startswith("第十二章 许铃音"), "切片没有以本单元标题开头")
    ck(len(slice_text) == E - S, "切片长度异常")
    print("  切片 sha256 = %s" % slice_hash)

    print("\n== 2. 读候选（不 import 生成脚本）")
    cand = json.load(open(CAND, encoding="utf-8"))
    for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
        ck(k in cand, "缺顶层分区 %s" % k)
    ck(cand.get("sourceHash") == EXPECT_HASH, "候选 sourceHash 不符")
    ck(cand.get("sliceSha256") == slice_hash, "候选 sliceSha256 与独立复算不符")
    ck(cand.get("sliceCodepoints") == len(slice_text), "候选 sliceCodepoints 不符")

    print("\n== 3. 逐条引用核验（区间内唯一命中 + 逐字 + 偏移一致）")
    n_ref, n_uniq, probs = audit_refs(text, cand)
    for p in probs:
        fails.append(p)
    checks[0] += 1
    print("  引用对象 %d 个（去重 %d 条原文子串），问题 %d 条" % (n_ref, n_uniq, len(probs)))

    print("\n== 3b. 裸 quote 字段（worldSettings 的 quote）必须与同级 quoteRef 一致")
    n_bare, bprobs = audit_bare_quotes(cand, text)
    for p in bprobs:
        fails.append(p)
    checks[0] += 1
    print("  裸 quote 节点 %d 个，问题 %d 条" % (n_bare, len(bprobs)))

    print("\n== 4. tasks 五栏一证（不得同栏共用引文）")
    shared = 0
    for t in cand["tasks"]:
        used = {}
        for nm in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(nm)
            if not v:
                continue
            for r in v["quotes"]:
                if r["quote"] in used:
                    shared += 1
                    fails.append("%s 的 %s 与 %s 共用引文" % (t["id"], nm, used[r["quote"]]))
                used[r["quote"]] = nm
        # 裸 null 必须有 note
        for nm in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(nm) is None:
                ck(bool(t.get(nm + "Note")), "%s.%s 裸 null 无 Note" % (t["id"], nm))
    checks[0] += 1
    print("  共用引文处数 = %d（要求 0）" % shared)

    print("\n== 5. states / worldSettings 的枚举字段")
    for s in cand["states"]:
        ck(s["kind"] in ("change", "knowledge_gap"), "%s kind 非法" % s["id"])
        if s["kind"] == "change":
            for nm in ("before", "after", "anchor"):
                ck(bool(s.get(nm)), "%s 缺 %s" % (s["id"], nm))
        else:
            ck("knownBy" in s and "unknownTo" in s, "%s 知识差缺 knownBy/unknownTo" % s["id"])
    for w in cand["worldSettings"]:
        if w["kind"] == "rule":
            ck(w["institution"] in ("declared", "executed", "misunderstood"), "%s institution 非法" % w["id"])
            ck(bool(w.get("explain")), "%s 缺 explain" % w["id"])
            ck("placeState" not in w and "itemStates" not in w, "%s rule 混入 place/item 字段" % w["id"])
        elif w["kind"] == "place":
            ck(w["placeState"] in ("arrived", "mentioned"), "%s placeState 非法" % w["id"])
        elif w["kind"] == "item":
            ck(bool(w["itemStates"]), "%s itemStates 为空" % w["id"])
            ck(all(x in ("hold", "transfer", "use", "lose") for x in w["itemStates"]), "%s itemStates 非法" % w["id"])
    # 计数对照
    kinds = {}
    for w in cand["worldSettings"]:
        kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
    places = {}
    for w in cand["worldSettings"]:
        if w["kind"] == "place":
            places[w["placeState"]] = places.get(w["placeState"], 0) + 1
    print("  世界设定 kind 分布 = %r；place 状态分布 = %r" % (kinds, places))

    print("\n== 6. foreshadows 的 resolved / unresolved 标注")
    for f in cand["foreshadows"]:
        ck(f["status"] in ("resolved", "unresolved"), "%s status 非法" % f["id"])
        ck(bool(f.get("setup")), "%s 缺 setup" % f["id"])
        if f["status"] == "unresolved":
            ck(f.get("payoff") is None, "%s 标 unresolved 却有 payoff" % f["id"])
            ck(bool(f.get("payoffNote")), "%s 标 unresolved 却无 payoffNote" % f["id"])
        else:
            ck(bool(f.get("payoff")), "%s 标 resolved 却无 payoff" % f["id"])
    print("  %d 条伏笔" % len(cand["foreshadows"]))

    print("\n== 7. themeReadings 必须带 counter")
    for t in cand["themeReadings"]:
        ck(bool(t.get("perspective")), "%s 缺 perspective" % t["id"])
        ck(bool(t.get("support")), "%s 缺 support" % t["id"])
        ck(bool(t.get("counter")), "%s 缺 counter（只列支持不叫解释）" % t["id"])
    for bad in ("高潮", "三幕", "英雄旅程"):
        # 只检查是否用它来**定义**高潮（允许出现在否定说明里）
        for t in cand["themeReadings"]:
            note = (t.get("note") or "")
            if bad in note and "没有用" not in note and "不是" not in note:
                fails.append("%s 的 note 疑似用禁用判据定义高潮：%s" % (t["id"], bad))
    checks[0] += 1

    print("\n== 8. 负控（审计自身有效性）")
    if not negative_controls(text):
        print("\n负控失败：审计不可信。")
        return 2

    print("\n== 9. 汇总")
    print("  检查项 %d，失败 %d" % (checks[0], len(fails)))
    if fails:
        for f in fails[:40]:
            print("  FAIL " + f)
        return 1
    print("  全部通过。引用对象 %d 个 / 原文子串 %d 条，区间内唯一命中、逐字一致、"
          "sourceHash 一致、无越界。" % (n_ref, n_uniq))
    return 0


if __name__ == "__main__":
    sys.exit(main())
