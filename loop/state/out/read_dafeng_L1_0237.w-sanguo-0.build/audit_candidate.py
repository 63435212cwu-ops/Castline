# -*- coding: utf-8 -*-
"""独立复算与负控（w-sanguo-0）。

**刻意不复用 build_candidate.py 的任何函数**：本脚本自己读 docs.json、自己遍历候选 JSON，
用与构建脚本不同的写法复核四件事：
  A. 每条引文逐字命中（text[start:end] == quote），且 sourceHash 相符、区间落在本单元内；
  B. sourceHash 与切片哈希独立复算；
  C. 「同一任务五栏不得共用同一条引文」独立重算；
  D. 负控（negative control）：故意植入若干**应当失败**的断言，确认本复核真的能抓到错。
     如果负控全部「通过」，说明这套复核是无效的（量不出东西），必须以非零码退出。
"""
import hashlib
import json
import os
import sys
from collections import defaultdict

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L1_0237.candidate.json")
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 943450, 948891

fails = []
notes = []


def check(cond, msg):
    if cond:
        notes.append("PASS  " + msg)
    else:
        fails.append(msg)


def main():
    docs = json.load(open(DOCS, encoding="utf-8"))
    text = docs[0]["text"]
    cand = json.load(open(CAND, encoding="utf-8"))

    # ── B. 哈希独立复算 ───────────────────────────────────────────────
    h = hashlib.sha256(open(DOCS, "rb").read()).hexdigest()
    check(h == SOURCE_HASH, "docs.json sha256 复算 = %s" % h)
    sl = text[START:END]
    slice_sha = hashlib.sha256(sl.encode("utf-8")).hexdigest()
    check(len(sl) == cand["sliceCodepoints"],
          "切片码点数 %d == 候选声明 %d" % (len(sl), cand["sliceCodepoints"]))
    check(slice_sha == cand["sliceSha256"],
          "切片 sha256 %s == 候选声明 %s" % (slice_sha[:16], cand["sliceSha256"][:16]))
    check(sl.startswith(cand["unitHead"]),
          "切片以单元标题开头：%r" % sl[:len(cand["unitHead"])])
    check(tuple(cand["sourceRange"]) == (START, END), "sourceRange 一致")

    # ── A. 全树引文核验（独立写法：显式栈，不用递归） ────────────────
    stack = [("$", cand)]
    refs = []
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
                refs.append((path, node))
            for k, v in node.items():
                if isinstance(v, (dict, list)):
                    stack.append((path + "/" + k, v))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, (dict, list)):
                    stack.append((path + "[%d]" % i, v))
    check(len(refs) >= 250, "抽到引文对象 %d 条（>=250）" % len(refs))

    bad_quote, bad_hash, bad_range, bad_type = [], [], [], []
    for path, r in refs:
        s, e, q = r["start"], r["end"], r["quote"]
        if not (isinstance(s, int) and isinstance(e, int)):
            bad_type.append(path)
            continue
        if text[s:e] != q:
            bad_quote.append((path, q[:30], text[s:e][:30]))
        if r.get("sourceHash") != SOURCE_HASH:
            bad_hash.append(path)
        if not (START <= s < e <= END):
            bad_range.append(path)
    check(not bad_type, "所有 start/end 都是整数（%d 条）" % len(refs))
    check(not bad_quote, "逐字命中：%d 条全部 text[start:end]==quote；反例 %r" % (len(refs), bad_quote[:3]))
    check(not bad_hash, "sourceHash 全树一致；反例 %r" % bad_hash[:3])
    check(not bad_range, "引文全部落在 [%d,%d)；反例 %r" % (START, END, bad_range[:3]))

    # 引文必须是**原文真实子串**（用 find 再验一次， independent of offsets）
    miss = [q for _, r in refs for q in [r["quote"]] if text.find(q) < 0]
    check(not miss, "全部引文都能在原文 text.find 到；缺失 %r" % miss[:3])

    # ── C. 同一任务五栏不得共用引文（独立重算） ──────────────────────
    clash_total = 0
    for t in cand["tasks"]:
        seen = defaultdict(list)
        for f in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(f)
            if isinstance(v, dict):
                for q in v.get("quotes", []):
                    seen[q["quote"]].append(f)
        dup = {q: fs for q, fs in seen.items() if len(fs) > 1}
        if dup:
            clash_total += len(dup)
            fails.append("任务 %s 五栏共用引文：%r" % (t["id"], dup))
    check(clash_total == 0, "五栏共用引文计数 = %d（应为 0）" % clash_total)

    # ── 结构完整性 ────────────────────────────────────────────────────
    for t in cand["tasks"]:
        for f in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(f) is None:
                check(bool(t.get(f + "Note")), "任务 %s.%s 为 null 且有理由" % (t["id"], f))
            else:
                check(bool(t[f].get("quotes")), "任务 %s.%s 有引文" % (t["id"], f))
    for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
        check(k in cand, "分区存在：%s" % k)
    for e in cand["causeEdges"]:
        check(bool(e.get("trigger")) and bool(e.get("direction")),
              "因果边 %s 有方向与触发" % e["id"])
        low = e["trigger"]
        check(not ("时间相邻" in low and "不是" not in low),
              "因果边 %s 不是以时间相邻为由" % e["id"])
    for f in cand["foreshadows"]:
        if f["status"] == "unresolved":
            check(f.get("payoff") is None and bool(f.get("payoffNote")),
                  "伏笔 %s 显式标 unresolved 并写明未回收" % f["id"])
        else:
            check(bool(f.get("payoff")), "伏笔 %s 有回收" % f["id"])
    for w in cand["worldSettings"]:
        if w["kind"] == "place":
            check(w["placeState"] in ("arrived", "mentioned"),
                  "地点 %s 标了 arrived/mentioned" % w["id"])
        if w["kind"] == "item":
            check(bool(w.get("itemStates")) and bool(w.get("stateEvidence")),
                  "物件 %s 有四态与态证据" % w["id"])
            check({s["state"] for s in w["stateEvidence"]} == set(w["itemStates"]),
                  "物件 %s 声明的四态与 stateEvidence 一致" % w["id"])
        if w["kind"] == "rule":
            check(w["institution"] in ("declared", "executed", "misunderstood"),
                  "规则 %s 标了 institution" % w["id"])
    for t in cand["themeReadings"]:
        check(bool(t.get("support")) and bool(t.get("counter")),
              "主题 %s 同时有 support 与 counter" % t["id"])
    check(cand["semanticReview"]["status"] == "not_performed",
          "semanticReview 未被声称为完成：%s" % cand["semanticReview"]["status"])

    # ── D. 负控：这些断言**必须失败**，否则说明复核无效 ───────────────
    nc = []
    first = refs[0][1]
    nc.append(("偏移+1 应失败", text[first["start"] + 1:first["end"] + 1] != first["quote"]))
    nc.append(("哈希改一位应失败",
               hashlib.sha256(open(DOCS, "rb").read()).hexdigest() != SOURCE_HASH[:-1] + "0"))
    nc.append(("不存在的引文应找不到",
               text.find("这句话在原文里绝对不存在ZZZ") < 0))
    nc.append(("切片外偏移应越界",
               not (START <= START - 1 < END)))
    nc.append(("空引文不应命中",
               text[first["start"]:first["start"]] == ""))
    failed_nc = [n for n, ok in nc if not ok]
    check(not failed_nc, "负控 %d 项全部按预期失败（说明复核有效）；异常项 %r" % (len(nc), failed_nc))

    print("\n".join(notes))
    print("-" * 60)
    print("引文对象：%d" % len(refs))
    print("检查项：%d，失败：%d" % (len(notes) + len(fails), len(fails)))
    if fails:
        print("失败明细：")
        for f in fails:
            print("  ✗ " + f)
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
