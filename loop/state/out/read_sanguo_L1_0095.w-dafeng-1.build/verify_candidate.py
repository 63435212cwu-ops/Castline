# -*- coding: utf-8 -*-
"""落盘后的独立复核：从**文件**重新解析，不采信构建期内存。

检查项（任一失败即非零退出）：
  1. 区间自检：切片以回目开头、长度 4696、右端点即下一单元回目。
  2. 全部 quoteRef 逐条：text[start:end]==quote、text.find(quote)==start、
     落在 [484338,489034)、sourceHash 相符、globalOccurrences 相符。
  3. 五栏复用：同一 task 的五栏之间不得共用同一引文区间。
  4. null 栏标注：null 栏必须有同名 <栏位>Note。
  5. worldSettings 三态字段：place.placeState / item.itemStates / rule.institution。
  6. 因果边方向与时序。
  7. 伏笔 status 与 payoffQuotes 的一致性。
  8. 顶层内容分区齐全（tasks/causeEdges/states/foreshadows/worldSettings/themeReadings）。
"""

import hashlib
import json
import sys

DOCS = "data/cache/fe42d01f3826fe8096f86614.docs.json"
CAND = "loop/state/out/read_sanguo_L1_0095.candidate.json"
S, E = 484338, 489034
SRC_HASH = "8ab7298a6960c6fec50e26338092abf2693e2cb39f1547f1a99ee2701ef29ec2"
COLS = ("objective", "obstacle", "action", "result", "cost")


def main():
    text = json.load(open(DOCS))[0]["text"]
    cand = json.load(open(CAND))
    fails = []

    # 1 ── 区间
    seg = text[S:E]
    if not seg.startswith("第九十六回"):
        fails.append("切片不以回目开头：%r" % seg[:20])
    if len(seg) != 4696:
        fails.append("切片长度 %d != 4696" % len(seg))
    if not text[E:E + 30].startswith("第九十七回　讨魏国武侯再上表"):
        fails.append("右端点不是下一单元回目：%r" % text[E:E + 30])
    if hashlib.sha256(open(DOCS, "rb").read()).hexdigest() != SRC_HASH:
        fails.append("源文件哈希与声明的 sourceHash 不符")

    # 2 ── 引文
    refs = []
    problems = []

    def walk(n, path):
        if isinstance(n, dict):
            if "quote" in n and "start" in n and "end" in n:
                refs.append((path, n))
            for k, v in n.items():
                walk(v, "%s.%s" % (path, k))
        elif isinstance(n, list):
            for i, v in enumerate(n):
                walk(v, "%s[%d]" % (path, i))

    walk(cand, "$")
    for path, r in refs:
        qq, s, e = r["quote"], r["start"], r["end"]
        if text[s:e] != qq:
            problems.append("%s: text[%d:%d] != quote" % (path, s, e))
        if text.find(qq) != s:
            problems.append("%s: find=%d != start=%d" % (path, text.find(qq), s))
        if r.get("sourceHash") != SRC_HASH:
            problems.append("%s: sourceHash 不符" % path)
        if not (S <= s and e <= E):
            problems.append("%s: 越界 [%d,%d)" % (path, s, e))
        cnt = text.count(qq)
        if r.get("globalOccurrences") != cnt:
            problems.append("%s: globalOccurrences %s != %d"
                            % (path, r.get("globalOccurrences"), cnt))
    if problems:
        fails.extend(problems[:30])
        fails.append("引文失败共 %d 条" % len(problems))

    # 3 ── 五栏复用
    reuse = 0
    for t in cand["tasks"]:
        seen = {}
        for c in COLS:
            col = t.get(c)
            if not col:
                continue
            for r in col.get("quotes", []):
                k = (r["start"], r["end"])
                if k in seen:
                    fails.append("%s: 五栏复用引文 %s（%s vs %s）"
                                 % (t["id"], k, seen[k], c))
                    reuse += 1
                else:
                    seen[k] = c

    # 4 ── null 栏标注
    for t in cand["tasks"]:
        for c in COLS:
            if t.get(c) is None and not t.get(c + "Note"):
                fails.append("%s.%s 为 null 却无 %sNote" % (t["id"], c, c))

    # 5 ── worldSettings 三态
    for w in cand["worldSettings"]:
        k = w.get("kind")
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            fails.append("place %s placeState=%r" % (w.get("name"), w.get("placeState")))
        if k == "item":
            st = w.get("itemStates")
            if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                fails.append("item %s itemStates=%r" % (w.get("name"), st))
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            fails.append("rule %s institution=%r" % (w.get("name"), w.get("institution")))

    # 6 ── 因果边
    for e in cand["causeEdges"]:
        cq = [r["start"] for r in e.get("causeQuotes") or []]
        eq = [r["start"] for r in e.get("effectQuotes") or []]
        if not cq or not eq:
            fails.append("%s: 缺 cause/effect 引文" % e["id"])
        elif max(cq) > min(eq):
            fails.append("%s: 因(%d) 晚于 果(%d)" % (e["id"], max(cq), min(eq)))

    # 7 ── 伏笔
    for f in cand["foreshadows"]:
        if f["status"] == "resolved" and not f.get("payoffQuotes"):
            fails.append("%s resolved 无 payoffQuotes" % f["id"])
        if f["status"] == "unresolved" and f.get("payoffQuotes"):
            fails.append("%s unresolved 却有 payoffQuotes" % f["id"])

    # 8 ── 顶层分区
    for key in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
                "themeReadings"):
        if key not in cand:
            fails.append("缺顶层分区 %s" % key)

    # 9 ── 主题解读三件套
    for th in cand["themeReadings"]:
        for k in ("perspective", "support", "counter"):
            if not th.get(k):
                fails.append("%s 缺 %s" % (th.get("id"), k))

    print("引文条数 = %d" % len(refs))
    print("五栏复用 = %d" % reuse)
    print("causeEdges = %d" % len(cand["causeEdges"]))
    print("foreshadows = %d (resolved %d / unresolved %d)"
          % (len(cand["foreshadows"]),
             sum(1 for f in cand["foreshadows"] if f["status"] == "resolved"),
             sum(1 for f in cand["foreshadows"] if f["status"] == "unresolved")))
    print("worldSettings = %d" % len(cand["worldSettings"]))
    print("themeReadings = %d" % len(cand["themeReadings"]))
    print("candidate sha256 = %s" % hashlib.sha256(open(CAND, "rb").read()).hexdigest())
    if fails:
        print()
        for f in fails:
            print("FAIL: %s" % f)
        return 1
    print()
    print("全部检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
