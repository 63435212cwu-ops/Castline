#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核本候选的引文与分区（不导入构建期任何中间量）。

判据（每条都必须能在 stdout 看到 PASS/FAIL）：
  C1 源文件 sha256 == 候选声明的 sourceHash
  C2 每条 quote 满足 text[start:end] == quote（全文 codepoint 偏移口径）
  C3 每条 quote 落在本区间 [994884,1001227) 内
  C4 每条 quote 在区间内**唯一**命中（find 计数 == 1）
  C5 tasks 五栏之间不共用同一句引文；单栏内部也不重复
  C6 每栏 null 必须配同名 `<栏位>Note`（缺理由的 null 视为未标注未知）
  C7 提示词要求的 6 个顶层分区键都存在
  C8 worldSettings 的 placeState / institution / itemStates 取值合法
  C9 foreshadows 每条都有 setup 引文 + status；unresolved 必须带 payoffNote
  C10 themeReadings 每条必须有 perspective / support / counter 三件，counter 非空
  C11 候选的 sliceSha256 == 切片 UTF-8 sha256
  C12 全文任意位置检索：候选引用的每一句都真的能在源文件里 find 到

用法：python3 verify_independent.py [--mutate]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0245.candidate.json"
S, E = 994884, 1001227
WANT_SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]

results = []


def check(cid, ok, msg):
    results.append((cid, bool(ok), msg))
    print("%-4s %s  %s" % (cid, "PASS" if ok else "FAIL", msg))


def walk_quotes(o, path="$"):
    if isinstance(o, dict):
        if isinstance(o.get("quote"), str) and "start" in o and "end" in o:
            yield path, o
        for k, v in o.items():
            yield from walk_quotes(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_quotes(v, path + "[%d]" % i)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutate", action="store_true", help="对候选做变异，确认判据真的会失败")
    args = ap.parse_args()

    raw = DOCS.read_bytes()
    H = hashlib.sha256(raw).hexdigest()
    T = json.loads(raw)[0]["text"]
    cand = json.loads(CAND.read_text(encoding="utf-8"))

    if args.mutate:
        # 变异 1：把一条 quote 的第 0 个字符改掉（定位判据应当失败）
        t0 = cand["tasks"][0]["objective"]["quotes"][0]
        t0["quote"] = "X" + t0["quote"][1:]
        print("[mutate] 已破坏 tasks[0].objective 的首字，预期 C2/C12 失败\n")

    # C1
    check("C1", cand.get("sourceHash") == H,
          "源文件 sha256 = %s…（候选声明 %s…）" % (H[:12], str(cand.get("sourceHash"))[:12]))

    # C2/C3/C4/C12
    n = 0
    bad_slice, bad_range, bad_uniq, bad_find = [], [], [], []
    for path, q in walk_quotes(cand):
        n += 1
        s, e, text = q["start"], q["end"], q["quote"]
        if T[s:e] != text:
            bad_slice.append((path, text[:24]))
        if not (S <= s and e <= E):
            bad_range.append((path, text[:24]))
        hits, i = [], T.find(text)
        while i >= 0:
            hits.append(i)
            i = T.find(text, i + 1)
        if len([h for h in hits if S <= h and h + len(text) <= E]) != 1:
            bad_uniq.append((path, text[:24], len(hits)))
        if not hits:
            bad_find.append((path, text[:24]))
    check("C2", not bad_slice, "共 %d 条 quote，text[start:end]==quote 全部成立（失败 %d：%s）"
          % (n, len(bad_slice), bad_slice[:2]))
    check("C3", not bad_range, "全部 quote 落在区间 [%d,%d) 内（越界 %d）" % (S, E, len(bad_range)))
    check("C4", not bad_uniq, "全部 quote 在区间内唯一命中（失败 %d：%s）" % (len(bad_uniq), bad_uniq[:2]))
    check("C12", not bad_find, "全部 quote 能在源文件中 find 到（找不到 %d：%s）" % (len(bad_find), bad_find[:2]))

    # C5：五栏不共用引文
    shared = []
    for t in cand.get("tasks", []):
        seen = {}
        for f in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(f)
            if not isinstance(v, dict):
                continue
            lst = [q["quote"] for q in v.get("quotes", [])]
            if len(lst) != len(set(lst)):
                shared.append((t["id"], f, "inner-dup"))
            for qq in lst:
                seen.setdefault(qq, []).append(f)
        for qq, fs in seen.items():
            if len(fs) > 1:
                shared.append((t["id"], tuple(fs), qq[:24]))
    check("C5", not shared, "tasks 五栏之间/栏内无共用引文（违例 %d：%s）" % (len(shared), shared[:2]))

    # C6：null 必须带 Note
    missing_note = []
    for t in cand.get("tasks", []):
        for f in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(f) is None:
                key = f + "Note"
                if not (isinstance(t.get(key), str) and t[key].strip()):
                    missing_note.append((t["id"], f))
    check("C6", not missing_note, "每处 null 都带同名 <栏位>Note 说明理由（缺失 %d：%s）"
          % (len(missing_note), missing_note[:3]))

    # C7：分区齐备
    missing = [k for k in WANT_SECTIONS if k not in cand]
    check("C7", not missing, "提示词要求的 6 个顶层分区键都在（缺 %s）" % (missing or "无"))

    # C8：判别字段取值
    illegal = []
    for w in cand.get("worldSettings", []):
        k = w.get("kind")
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            illegal.append((w.get("id"), "placeState", w.get("placeState")))
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            illegal.append((w.get("id"), "institution", w.get("institution")))
        if k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                illegal.append((w.get("id"), "itemStates", st))
    check("C8", not illegal, "placeState/institution/itemStates 取值合法（违例 %d：%s）" % (len(illegal), illegal[:3]))

    # C9：伏笔必须有铺设 + status；unresolved 必须有 payoffNote
    fs_bad = []
    for f in cand.get("foreshadows", []):
        setup = f.get("setup")
        if not isinstance(setup, dict) or not setup.get("quotes"):
            fs_bad.append((f.get("id"), "no-setup"))
        if f.get("status") not in ("resolved", "unresolved", "partial"):
            fs_bad.append((f.get("id"), "bad-status", f.get("status")))
        if f.get("status") == "unresolved" and not (f.get("payoffNote") or f.get("unresolvedReason")):
            fs_bad.append((f.get("id"), "unresolved-without-note"))
    check("C9", not fs_bad, "伏笔均有铺设引文与 status，未回收者带说明（违例 %d：%s）" % (len(fs_bad), fs_bad[:3]))

    # C10：主题三件
    th_bad = []
    for t in cand.get("themeReadings", []):
        if not t.get("perspective"):
            th_bad.append((t.get("id"), "no-perspective"))
        sup = t.get("support")
        if not isinstance(sup, list) or not sup or not any(x.get("quotes") for x in sup):
            th_bad.append((t.get("id"), "no-support-quote"))
        if not isinstance(t.get("counter"), list) or not t["counter"]:
            th_bad.append((t.get("id"), "no-counter"))
    check("C10", not th_bad, "themeReadings 三件齐备且 counter 非空（违例 %d：%s）" % (len(th_bad), th_bad[:3]))

    # C11：切片哈希
    sl = T[S:E]
    got = hashlib.sha256(sl.encode("utf-8")).hexdigest()
    check("C11", cand.get("sliceSha256") == got and cand.get("sliceCodepoints") == len(sl),
          "切片 sha256 = %s…（%d 码点）与候选声明一致" % (got[:12], len(sl)))

    ok = all(r[1] for r in results)
    print("\n=== %s：%d/%d 条判据通过 ===" % ("全部通过" if ok else "存在失败", sum(1 for r in results if r[1]), len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
