#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计 read_dafeng_L0_0224.candidate.json（A1–A14）。

与构建侧**完全隔离**：本脚本不 import quotes.py / content_core.py / build_candidate.py，
只读**产物 JSON** 与**原文**，自己重新定位每条引文。为什么必须这样：如果审计复用
生成侧的模块，生成侧的 bug 会被同一个 bug 再确认一遍（同源复算 ≠ 独立复核）。

A1  源文件 sha256 == 产物 sourceHash == 任务 sourceHash；切片以标题开头
A2  递归遍历产物，每条引用满足 text[start:end] == quote
A3  TEXT.find(quote) == start（偏移不是碰巧切对）
A4  每条引文落在 [sourceRange) 内，且在切片内唯一
A5  引文之间无重复字面量、无互相包含
A6  同一任务五栏无共用引文（字面量 + 偏移）
A7  裸 null 栏位都有同名 <栏位>Note
A8  worldSettings 判别字段合法且与 kind 一致；地点态用「到达动词 vs 朝向动词」反查
A9  foreshadows：resolved 有 payoff；unresolved 有 payoffNote 且 payoff 为 None
A10 themeReadings 齐备三件，counter 有引文
A11 basis 全部合法；basisDistribution 自报 == 实际
A12 coverage 段落恒等式；zeroCoverageList 完整
A13 citationIntegrity 恒等式；sectionCounts 自报 == 实际
A14 语层披露：产物里所有 speech/book/thought 引文都能在 disclosure 里找到（双向）
A15 结尾不得出现「到达/成功」类断言被当作结果
"""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L0_0224.json"
CAND = ROOT / "loop/state/out/read_dafeng_L0_0224.candidate.json"

BASES = ("explicit", "inferred", "derived", "unverified")
COLUMNS = ("objective", "obstacle", "action", "result", "cost")
ARRIVE = ("到达", "抵达", "赶到", "进入", "冲进", "走进", "来到", "回到",
          "驻守", "留守", "进了")
APPROACH = ("奔向", "赶往", "奔赴", "走出", "前往", "赶去")

P = []


def bad(m):
    P.append(m)


def main():
    task = json.loads(TASK.read_text(encoding="utf-8"))
    raw = DOCS.read_bytes()
    fh = hashlib.sha256(raw).hexdigest()
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    s, e = task["sourceRange"]
    sl = text[s:e]
    cand = json.loads(CAND.read_text(encoding="utf-8"))

    # ── A1 ──────────────────────────────────────────────────────────────
    if fh != task["sourceHash"]:
        bad("[A1] 文件 sha256 与任务不符")
    if cand["sourceHash"] != fh:
        bad("[A1] 产物 sourceHash 与文件 sha256 不符")
    if not sl.startswith(task["unitHead"]):
        bad("[A1] 切片不以标题开头")
    if cand["sourceRange"] != [s, e]:
        bad("[A1] 产物 sourceRange 与任务不符")
    if hashlib.sha256(sl.encode()).hexdigest() != cand["sliceSha256"]:
        bad("[A1] sliceSha256 与实算不符")

    # ── 收集全部引用对象（递归）──────────────────────────────────────────
    refs = []

    def walk(node, path):
        if isinstance(node, dict):
            if all(k in node for k in ("quote", "start", "end")):
                refs.append((path, node))
            for k, v in node.items():
                walk(v, "%s/%s" % (path, k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s/%d" % (path, i))

    walk(cand, "")

    seen_lit = {}
    for _p, _r in refs:
        seen_lit.setdefault(_r["quote"], _p)
    for path, r in refs:
        q, st, en = r["quote"], r["start"], r["end"]
        # A2
        if text[st:en] != q:
            bad("[A2] %s: text[%d:%d] != quote" % (path, st, en))
        # A3
        if text.find(q) != st:
            bad("[A3] %s: find=%d != start=%d" % (path, text.find(q), st))
        # A4
        if not (s <= st and en <= e):
            bad("[A4] %s: 偏移落在区间外" % path)
        elif sl.count(q) != 1:
            bad("[A4] %s: 切片内命中 %d 次" % (path, sl.count(q)))
        if r.get("sourceHash") != fh:
            bad("[A4] %s: sourceHash 不是全文件哈希" % path)

    # ── A5 引文唯一性 ───────────────────────────────────────────────────
    # **口径**（第一版把这里写错过，会报出 100+ 处假缺陷）：提示词禁止的是
    #  ① 同一个任务五栏共用一句（由 A6 专管）；
    #  ② 把一句话切成两条登记充数（假多样性）。
    # **不禁止**不同分区复用同一句：一句原文可以既是某条状态的锚点、又是某条因果边的
    # 依据 —— 那是交叉引用，不是重复计数。所以这里只在**同一个 quotes[] 数组内部**
    # 查重复与包含（防同一栏塞两条同义引文凑数）。
    def check_local(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "quotes" and isinstance(v, list):
                    lits = [r["quote"] for r in v
                            if isinstance(r, dict) and "quote" in r]
                    if len(lits) != len(set(lits)):
                        bad("[A5] %s/quotes 内部有重复引文" % path)
                    for i, a in enumerate(lits):
                        for b in lits[i + 1:]:
                            if a in b or b in a:
                                bad("[A5] %s/quotes 内部引文互相包含：%r / %r"
                                    % (path, a[:20], b[:20]))
                check_local(v, "%s/%s" % (path, k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                check_local(v, "%s/%d" % (path, i))

    check_local(cand, "")

    # ── A6 五栏互异 ─────────────────────────────────────────────────────
    for t in cand["tasks"]:
        lit, span = {}, {}
        for col in COLUMNS:
            cell = t.get(col)
            if not isinstance(cell, dict):
                continue
            for r in cell.get("quotes") or []:
                if r["quote"] in lit:
                    bad("[A6] %s: %s 与 %s 共用引文" % (t["id"], col, lit[r["quote"]]))
                lit[r["quote"]] = col
                sp = (r["start"], r["end"])
                if sp in span:
                    bad("[A6] %s: %s 与 %s 共用偏移" % (t["id"], col, span[sp]))
                span[sp] = col

    # ── A7 裸 null 必须有 Note ──────────────────────────────────────────
    for t in cand["tasks"]:
        for col in COLUMNS:
            if t.get(col) is None and not t.get(col + "Note"):
                bad("[A7] %s.%s 是 null 但没有 %s" % (t["id"], col, col + "Note"))
    for f in cand["foreshadows"]:
        if f["status"] == "unresolved" and not f.get("payoffNote"):
            bad("[A8] foreshadows.%s unresolved 但没有 payoffNote" % f["id"])

    # ── A8 worldSettings ───────────────────────────────────────────────
    for w in cand["worldSettings"]:
        k = w.get("kind")
        if k == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                bad("[A8] %s placeState 非法" % w["id"])
            q = "".join(r["quote"] for r in w.get("quotes") or [])
            ha = any(v in q for v in ARRIVE)
            hp = any(v in q for v in APPROACH)
            if w["placeState"] == "arrived" and not ha:
                bad("[A8] %s 标 arrived 但无到达动词（提及≠到达）" % w["id"])
            if w["placeState"] == "mentioned" and ha:
                bad("[A8] %s 标 mentioned 但含到达动词" % w["id"])
            if w["placeState"] == "mentioned" and hp and ha:
                bad("[A8] %s 到达/朝向动词混用，态不明" % w["id"])
        elif k == "item":
            sts = w.get("itemStates") or []
            if not sts or any(x not in ("hold", "transfer", "use", "lose") for x in sts):
                bad("[A8] %s itemStates 非法：%r" % (w["id"], sts))
        elif k == "rule":
            if w.get("institution") not in ("declared", "executed", "misunderstood"):
                bad("[A8] %s institution 非法" % w["id"])
            if not w.get("explain"):
                bad("[A8] %s 缺 explain" % w["id"])
        else:
            bad("[A8] %s kind 非法" % w["id"])

    # ── A9 foreshadows ─────────────────────────────────────────────────
    for f in cand["foreshadows"]:
        if f["status"] == "resolved" and not isinstance(f.get("payoff"), dict):
            bad("[A9] %s resolved 但无 payoff" % f["id"])
        if f["status"] == "unresolved" and f.get("payoff") is not None:
            bad("[A9] %s unresolved 但给了 payoff" % f["id"])

    # ── A10 themeReadings ──────────────────────────────────────────────
    for t in cand["themeReadings"]:
        for f in ("perspective", "support", "counter"):
            if not t.get(f):
                bad("[A10] %s 缺 %s" % (t["id"], f))
        if not (t.get("counter") or {}).get("quotes"):
            bad("[A10] %s 的 counter 无引文" % t["id"])

    # ── A11 basis ──────────────────────────────────────────────────────
    actual = Counter()

    def cb(node):
        if isinstance(node, dict):
            if "basis" in node:
                b = node["basis"]
                if b not in BASES:
                    bad("[A11] basis 非法：%r" % b)
                else:
                    actual[b] += 1
            for v in node.values():
                cb(v)
        elif isinstance(node, list):
            for v in node:
                cb(v)

    cb(cand)
    rep = cand["basisDistribution"]
    if rep["total"] != sum(actual.values()):
        bad("[A11] basis 总数自报 %d != 实际 %d" % (rep["total"], sum(actual.values())))
    for b in BASES:
        if rep.get(b) != actual.get(b, 0):
            bad("[A11] basis %s 自报 %r != 实际 %d" % (b, rep.get(b), actual.get(b, 0)))

    # ── A12 coverage ───────────────────────────────────────────────────
    paras, pos = [], 0
    for m in list(re.finditer(r"\n\s*\n", sl)) + [None]:
        end = m.start() if m else len(sl)
        if sl[pos:end].strip():
            paras.append({"para": len(paras) + 1, "start": s + pos, "end": s + end})
        if m is None:
            break
        pos = m.end()
    touched = set()
    for p in paras:
        for _, r in refs:
            if r["start"] < p["end"] and r["end"] > p["start"]:
                touched.add(p["para"])
                break
    cov = cand["coverage"]
    if cov["nonEmptyParagraphs"] != len(paras):
        bad("[A12] 非空段数自报 %d != 实算 %d" % (cov["nonEmptyParagraphs"], len(paras)))
    if cov["paragraphsTouchedByQuotes"] != len(touched):
        bad("[A12] 触及段数自报 %d != 实算 %d"
            % (cov["paragraphsTouchedByQuotes"], len(touched)))
    zero = [p["para"] for p in paras if p["para"] not in touched]
    if cov["zeroCoverageParagraphs"] != len(zero):
        bad("[A12] 零覆盖数自报 %d != 实算 %d" % (cov["zeroCoverageParagraphs"], len(zero)))
    listed = [z["para"] for z in cov["zeroCoverageList"]]
    if listed != zero:
        bad("[A12] 零覆盖清单与实算不符：缺 %s / 多 %s"
            % (sorted(set(zero) - set(listed)), sorted(set(listed) - set(zero))))
    if len(touched) + len(zero) != len(paras):
        bad("[A12] 段落恒等式不成立")

    # ── A13 citationIntegrity + sectionCounts ──────────────────────────
    ci = cand["citationIntegrity"]
    if ci["contentSectionRefs"] + ci["disclosureSectionRefs"] != ci["totalRefsInDoc"]:
        bad("[A13] 恒等式不成立")
    if ci["totalRefsInDoc"] != len(refs):
        bad("[A13] totalRefs 自报 %d != 实算 %d" % (ci["totalRefsInDoc"], len(refs)))
    sc = cand["sectionCounts"]
    checks = {
        "tasks": len(cand["tasks"]), "rejectedTasks": len(cand["rejectedTasks"]),
        "causeEdges": len(cand["causeEdges"]), "rejectedEdges": len(cand["rejectedEdges"]),
        "states": len(cand["states"]), "foreshadows": len(cand["foreshadows"]),
        "notForeshadows": len(cand["notForeshadows"]),
        "worldSettings": len(cand["worldSettings"]),
        "excludedSettings": len(cand["excludedSettings"]),
        "themeReadings": len(cand["themeReadings"]), "unknowns": len(cand["unknowns"]),
        "selfCritique": len(cand["selfCritique"]),
    }
    for k, v in checks.items():
        if sc.get(k) != v:
            bad("[A13] sectionCounts.%s 自报 %r != 实际 %d" % (k, sc.get(k), v))
    nulls = sum(1 for t in cand["tasks"] for c in COLUMNS if t.get(c) is None)
    if sc.get("tasksWithNullColumn") != nulls:
        bad("[A13] tasksWithNullColumn 自报 %r != 实际 %d"
            % (sc.get("tasksWithNullColumn"), nulls))

    # ── A14 语层双向 ───────────────────────────────────────────────────
    disc = {d["key"]: d for d in cand["speechLayerDisclosure"]["dispositionOfEach"]}
    if cand["speechLayerDisclosure"]["checkedCount"] != len(disc):
        bad("[A14] checkedCount 与条目数不符")
    # 每个披露条目必须自带可复算的引文
    for k, d in disc.items():
        if text[d["start"]:d["end"]] != d["quote"]:
            bad("[A14] 披露条目 %s 的引文复算失败" % k)
    # 产物里出现的每条引文，若其原文属于台词层，必须被披露覆盖 ——
    # 判据：引文内含地书括号【】或以引号起止，即视为台词层，必须出现在披露里
    disc_lits = {d["quote"] for d in disc.values()}
    for lit, path in seen_lit.items():
        is_speechish = ("【" in lit) or (lit.strip().startswith("“") and lit.strip().endswith("”"))
        if is_speechish and lit not in disc_lits:
            bad("[A14] 台词层引文未登记披露：%s（%s）" % (lit[:30], path))

    # ── A15 结尾反查 ───────────────────────────────────────────────────
    tail = sl[-260:]
    for w in ("抵达", "成功", "得手"):
        if w in tail:
            bad("[A15] 区间末尾出现 %r" % w)
    ed = cand["endingDisclosure"]
    if not ed.get("whatIsNotThere"):
        bad("[A15] endingDisclosure.whatIsNotThere 为空")

    # ── A16 不得有「声明了 quoteKeys 却没展开成 quotes」的悬空依据 ────────
    # 这是 H12 的**软形态**，本轮真实踩到过：states.s8 的 extraEvidence 带了
    # quoteKeys，但构建脚本不认识这个字段，于是产物里留下一段没有任何引文的
    # 「依据」—— 它看起来像证据、实际不可核验。硬形态（键名写错）会被 H12 抓住，
    # 软形态只能靠这条判据。
    def check_dangling(node, path):
        if isinstance(node, dict):
            ks = node.get("quoteKeys")
            if isinstance(ks, list) and ks and not node.get("quotes"):
                bad("[A16] %s 声明了 %d 个 quoteKeys 但没有展开出 quotes（悬空依据）"
                    % (path, len(ks)))
            for k, v in node.items():
                check_dangling(v, "%s/%s" % (path, k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                check_dangling(v, "%s/%d" % (path, i))

    check_dangling(cand, "")

    # ── A17 有 basis 的对象必须能落到引文（否则是无据断言）────────────────
    # **口径**（第一版写错过，会报出 11 处假缺陷）：states/foreshadows 这类**容器**
    # 把引文放在嵌套的 before/after/anchor、setup/payoff 里，父对象自己当然没有
    # quotes[]。所以判据是「本对象或其后代里存在引文」，而不是「本对象自带 quotes」。
    def has_quote_descendant(node):
        if isinstance(node, dict):
            if node.get("quote") and "start" in node and "end" in node:
                return True
            return any(has_quote_descendant(v) for v in node.values())
        if isinstance(node, list):
            return any(has_quote_descendant(v) for v in node)
        return False

    def check_evidenced(node, path):
        if isinstance(node, dict):
            b = node.get("basis")
            if b in BASES and b != "unverified" and not has_quote_descendant(node):
                bad("[A17] %s 有 basis=%s 但整棵子树里没有任何引文" % (path, b))
            for k, v in node.items():
                check_evidenced(v, "%s/%s" % (path, k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                check_evidenced(v, "%s/%d" % (path, i))

    check_evidenced(cand, "")

    # ── 报告 ───────────────────────────────────────────────────────────
    print("审计对象：%s" % CAND.relative_to(ROOT))
    print("  引用对象 %d 个 / 互异引文 %d 条" % (len(refs), len(seen_lit)))
    print("  任务 %d 条（五栏互异：%s）"
          % (len(cand["tasks"]),
             ", ".join("%s=%d" % (r["task"].split("_")[0],
                                  r["distinctQuotesAcrossFiveColumns"])
                       for r in cand["fiveColumnQuoteReuse"])))
    print("  覆盖：%d/%d 段被引文触及，零覆盖 %d 段"
          % (cov["paragraphsTouchedByQuotes"], cov["nonEmptyParagraphs"],
             cov["zeroCoverageParagraphs"]))
    if P:
        print("\n审计失败：%d 处" % len(P), file=sys.stderr)
        for x in P:
            print("  - " + x, file=sys.stderr)
        return 1
    print("\nA1–A17 全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
