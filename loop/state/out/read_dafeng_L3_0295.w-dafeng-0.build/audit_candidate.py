# -*- coding: utf-8 -*-
"""独立审计：**从磁盘重读候选**，不看构建期的内存状态，重新核每一条引文。

与 build_candidate.py 的区别（这是它存在的理由）：
  · build 用的是内存里的 payload；审计只读落盘的 JSON ——
    能抓到「写盘时被截断/串码/字段丢失」这类只在文件里才看得见的问题。
  · build 的定位用 quotes_0295.py 的键；审计**不再用键**，
    而是拿候选里每条 quote 的 (quote,start,end) 直接在原文上找，
    这样连「键解析错了」也能发现。
  · 审计复核内容层面的硬约束：栏位隔离、null 栏带理由、枚举合法、
    未回收伏笔标 unresolved、作者区域隔离。

用法：python3 loop/state/out/read_dafeng_L3_0295.w-dafeng-0.build/audit_candidate.py
退出码 0 = 全部通过。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
CAND = ROOT / "loop/state/out/read_dafeng_L3_0295.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"

S, E = 1286538, 1295556
problems = []
checks = 0


def ck(cond, msg):
    global checks
    checks += 1
    if not cond:
        problems.append(msg)
    return cond


def main():
    doc = json.loads(CAND.read_text(encoding="utf-8"))
    text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    src_hash = hashlib.sha256(DOCS.read_bytes()).hexdigest()

    # 1) 源哈希与偏移口径
    ck(doc["source"]["sourceHash"] == src_hash,
       "sourceHash 与 docs.json 实际 sha256 不符")
    ck(doc["source"]["range"] == [S, E], "range 与任务声明不符")
    ck(text[S:E].startswith("第六十六章 不跪"), "切片不以本单元标题开头")
    ck(len(text[S:E]) == E - S, "切片长度不符")
    ck(doc["source"]["boundaryHeadMatchesTitle"] is True, "boundaryHeadMatchesTitle 非 true")

    # 2) 收集全部引文对象
    objs = []

    def collect(o, path=""):
        if isinstance(o, dict):
            if {"quote", "start", "end", "sourceHash"} <= set(o):
                objs.append((path, o))
                return
            for k, v in o.items():
                collect(v, path + "." + str(k))
        elif isinstance(o, list):
            for i, x in enumerate(o):
                collect(x, path + "[%d]" % i)

    for key in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
                "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
                "themeReadings", "speechAsClueNotFact", "textualNotes",
                "authorRegionEvidence", "unknowns"):
        collect(doc.get(key), key)

    # 3) 逐条重定位：text[start:end] == quote 且 quote 能在全文 find 到
    bad_slice = bad_find = bad_hash = bad_range = bad_para = 0
    for path, o in objs:
        if text[o["start"]:o["end"]] != o["quote"]:
            bad_slice += 1
            problems.append("切片不符 %s: %r" % (path, o["quote"][:24]))
        if text.find(o["quote"]) < 0:
            bad_find += 1
            problems.append("全文 find 不到 %s: %r" % (path, o["quote"][:24]))
        if o["sourceHash"] != src_hash:
            bad_hash += 1
            problems.append("sourceHash 不符 %s" % path)
        if not (S <= o["start"] < o["end"] <= E):
            bad_range += 1
            problems.append("越界 %s: %s-%s" % (path, o["start"], o["end"]))
        if "\n" in o["quote"]:
            problems.append("引文跨段 %s" % path)
        # para 字段自洽：重新按 \n 数段落
        if o.get("para"):
            idx = int(o["para"][1:])
            off = S
            for i, para in enumerate(text[S:E].split("\n")):
                if i == idx:
                    ck(off <= o["start"] <= off + len(para),
                       "para 标注不符 %s：%s 不在 %s" % (path, o["start"], o["para"]))
                    break
                off += len(para) + 1
            else:
                bad_para += 1
                problems.append("para 越界 %s：%s" % (path, o["para"]))

    # 4) 作者区域隔离
    ar = [(a["start"], a["end"]) for a in doc["authorRegion"]]
    ar_keys = {q["anchorLabel"] for x in doc.get("authorRegionEvidence") or []
               for q in x["quotes"]}
    leaks = 0
    for path, o in objs:
        inside = any(a <= o["start"] and o["end"] <= b for a, b in ar)
        if inside and o.get("anchorLabel") not in ar_keys:
            leaks += 1
            problems.append("叙事引文落进作者区域 %s: %r" % (path, o["quote"][:20]))
    ck(leaks == 0, "authorRegionLeaks=%d" % leaks)

    # 5) 任务栏位隔离：同一任务五栏区间两两不重叠、不共用引文
    for t in doc["tasks"]:
        seen = {}
        for col in ("objective", "obstacle", "action", "result", "cost"):
            for q in t.get(col + "Quotes") or []:
                rng = (q["start"], q["end"])
                for pr, pc in seen.items():
                    if not (rng[1] <= pr[0] or rng[0] >= pr[1]):
                        problems.append("%s 栏位区间重叠 %s/%s" % (t["id"], col, pc))
                if rng in seen:
                    problems.append("%s 两栏共用引文 %s/%s" % (t["id"], col, seen[rng]))
                seen[rng] = col

    # 6) null 栏必须有理由；有值必须带 basis 与引文
    basis_ok = {"explicit", "inferred", "derived", "unverified"}
    for t in doc["tasks"]:
        for col in ("objective", "obstacle", "action", "result", "cost"):
            val, keys = t.get(col), t.get(col + "Quotes") or []
            if val is None:
                ck(bool(t.get(col + "Note")), "%s.%s 为 null 却没写理由" % (t["id"], col))
                ck(not keys, "%s.%s 为 null 却带引文" % (t["id"], col))
            else:
                ck(t.get(col + "Basis") in basis_ok, "%s.%s basis 非法" % (t["id"], col))
                ck(bool(keys), "%s.%s 有值却无引文" % (t["id"], col))

    # 7) 枚举合法性
    for w in doc["worldSettings"]:
        ck(w["kind"] in ("rule", "place", "item"), "%s kind 非法" % w["id"])
        if w["kind"] == "place":
            ck(w.get("placeState") in ("arrived", "mentioned"), "%s placeState" % w["id"])
        if w["kind"] == "item":
            ck(bool(w.get("itemStates")) and
               set(w["itemStates"]) <= {"hold", "transfer", "use", "lose"},
               "%s itemStates 非法" % w["id"])
        if w["kind"] == "rule":
            ck(w.get("institution") in ("declared", "executed", "misunderstood"),
               "%s institution 非法" % w["id"])

    # 8) 未回收伏笔要显式标 unresolved 且带 note
    for f in doc["foreshadows"]:
        if not f["resolved"]:
            ck(f.get("unresolved") is True, "%s 未回收却没标 unresolved" % f["id"])
            ck(bool(f.get("note")), "%s 未回收却没写 note" % f["id"])
        else:
            ck(bool(f.get("payoff")) and bool(f.get("payoffQuotes")), "%s 已回收却没写回收" % f["id"])

    # 9) 分区存在性（提示词要求的 6 个顶层分区）
    for key in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
                "themeReadings"):
        ck(isinstance(doc.get(key), list) and key in doc, "缺分区 %s" % key)

    # 10) 主题条目三件套
    for t in doc["themeReadings"]:
        ck(bool(t.get("perspective")) and bool(t.get("support")) and bool(t.get("counter")),
           "%s 主题三件套不全" % t["id"])

    # 11) 构建期自检声称的 problems 必须为空
    ck(doc["machineSelfCheck"]["problems"] == [],
       "machineSelfCheck.problems 非空：%r" % doc["machineSelfCheck"]["problems"][:3])

    # 12) 不得声称语义评审完成
    ck(doc["semanticReview"] == "not-performed", "semanticReview 必须如实为 not-performed")

    print("审计引文对象 %d 条（唯一区间 %d）"
          % (len(objs), len({(o["start"], o["end"]) for _, o in objs})))
    print("断言 %d 条，problems %d 条" % (checks, len(problems)))
    for p in problems[:40]:
        print("  [problem] %s" % p)
    print("分类计数：slice=%d find=%d hash=%d range=%d para=%d leaks=%d"
          % (bad_slice, bad_find, bad_hash, bad_range, bad_para, leaks))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
