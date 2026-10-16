#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立校验 read_dafeng_L2_0190.candidate.json —— **不复用构建期任何逻辑**。

为什么必须另写一份：构建脚本的断言与内容是同一个作者写的，
如果校验也调用同一批函数，它只能证明「我的代码与我的代码一致」。
本脚本自己重切段、自己重新 find 偏移、用**与切句规则无关**的判据重算五栏独立性、
自己重算零覆盖集合并与处置表比对。

判据：
  H1 整个 docs.json 的 sha256 == task.sourceHash
  H2 切片以 unitHead 开头、长度 == end-start
  H3 切片 utf-8 sha256 == 候选声明的 segmentSha256
  Q1 每条引文 text[start:end] == quote（自己 find，不信任候选的 start）
  Q2 每条引文落在 [S,E)
  Q3 每条引文在切片内 find 命中数 == 1，且 firstOccurrenceAt == 候选声明
  Q4 sourceHash 全等于 task.sourceHash
  C1 同任务五栏按**字符区间重叠**判零共用（与切句无关）
  N1 空栏全部带同名 Note，且理由非空
  B1 行内直角引号内容全部是切片内逐字子串
  P1 散文里的 P### 存在；P### 紧邻的引文确实在该段
  Z1 零覆盖段集合与处置表键集合**完全相等**（双向）
  M1 变异测试：篡改引文/偏移/段号/删 Note ⇒ 各自被判据抓到（证明判据非空转）

用法：python3 -B -s verify_candidate.py [候选路径]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
DEFAULT_CAND = ROOT / "loop/state/out/read_dafeng_L2_0190.candidate.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L2_0190.json"

fails = []
passes = []


def ok(name, cond, detail=""):
    (passes if cond else fails).append((name, detail))
    print("%s %s%s" % ("PASS" if cond else "FAIL", name, ("  " + detail) if detail else ""))
    return cond


def main() -> int:
    cand_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CAND
    task = json.loads(TASK.read_text(encoding="utf-8"))
    S, E = task["sourceRange"]
    cand = json.loads(cand_path.read_text(encoding="utf-8"))

    raw = DOCS.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    ok("H1 源哈希 == task.sourceHash", got == task["sourceHash"], got[:16])
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    seg = text[S:E]
    ok("H2 切片以 unitHead 开头且长度相符",
       seg.startswith(task["unitHead"]) and len(seg) == E - S, "%d chars" % len(seg))
    ok("H3 切片 sha256 == 候选声明",
       hashlib.sha256(seg.encode("utf-8")).hexdigest() == cand["source"]["segmentSha256"])

    # ── 自己重切段号（非空行 1-based），与候选的 P### 口径核对 ──
    lines = []
    pos = S
    ordinal = 0
    while pos < E:
        nl = text.find("\n", pos, E)
        end = E if nl == -1 else nl
        body = text[pos:end].strip()
        if body:
            ordinal += 1
            cs = pos + len(text[pos:end]) - len(text[pos:end].lstrip())
            lines.append((ordinal, cs, cs + len(body)))
        pos = end + 1
    pmap = {o: (a, b) for o, a, b in lines}

    # ── 收集全部引文对象 ──
    quotes = []

    def walk(o, path="root"):
        if isinstance(o, dict):
            if "quote" in o and "start" in o and "end" in o:
                quotes.append((path, o))
            for k, v in o.items():
                walk(v, path + "." + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, "%s[%d]" % (path, i))

    walk(cand)
    ok("Q0 引文对象数量 > 0", len(quotes) > 0, "%d 条" % len(quotes))

    bad_v = bad_r = bad_u = bad_h = bad_p = 0
    for path, q in quotes:
        if text[q["start"]:q["end"]] != q["quote"]:
            bad_v += 1
            print("   Q1 不逐字:", path, repr(q["quote"][:40]))
        if not (S <= q["start"] and q["end"] <= E):
            bad_r += 1
            print("   Q2 越界:", path)
        if seg.count(q["quote"]) != 1:
            bad_u += 1
            print("   Q3 切片内命中 %d 次:" % seg.count(q["quote"]), path)
        if q["sourceHash"] != task["sourceHash"]:
            bad_h += 1
        # 独立复算 firstOccurrenceAt（全文口径）
        if text.find(q["quote"]) != q["firstOccurrenceAt"]:
            bad_p += 1
            print("   Q3b firstOccurrenceAt 不符:", path)
    ok("Q1 全部逐字（text[start:end]==quote）", bad_v == 0, "fails=%d" % bad_v)
    ok("Q2 全部落在 [S,E)", bad_r == 0, "fails=%d" % bad_r)
    ok("Q3 切片内命中唯一", bad_u == 0, "fails=%d" % bad_u)
    ok("Q4 sourceHash 全等于 task.sourceHash", bad_h == 0, "fails=%d" % bad_h)
    ok("Q3b 全文首次出现位置可复算", bad_p == 0, "fails=%d" % bad_p)

    # ── C1：同任务五栏按字符区间重叠判零共用（与切句规则无关）──
    overlaps = []
    for t in cand["tasks"]:
        cols = [(c, t[c]) for c in ("objective", "obstacle", "action", "result", "cost") if t.get(c)]
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                (n1, c1), (n2, c2) = cols[i], cols[j]
                for q1 in c1["quotes"]:
                    for q2 in c2["quotes"]:
                        if q1["start"] < q2["end"] and q2["start"] < q1["end"]:
                            overlaps.append((t["id"], n1, n2, q1["start"], q1["end"]))
    ok("C1 同任务五栏引文零字符区间重叠", not overlaps, "overlaps=%r" % (overlaps[:3],))

    # ── N1：空栏必须有同名 Note 且理由非空 ──
    nulls = []
    for t in cand["tasks"]:
        for c in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(c) is None:
                note = t.get(c + "Note") or ""
                nulls.append((t["id"], c, len(note)))
                if len(note) < 10:
                    print("   N1 理由过短或缺失:", t["id"], c)
    ok("N1 空栏全部带非空理由", all(n[2] >= 10 for n in nulls), "%r" % (nulls,))
    reg = {(n["task"], n["field"]) for n in cand["nullFieldCandidates"]}
    ok("N1b nullFieldCandidates 与任务空栏一一对应",
       reg == {(t, c) for t, c, _ in nulls}, "登记=%r 实际=%r" % (sorted(reg), sorted((t, c) for t, c, _ in nulls)))

    # ── B1：行内直角引号内容逐字 ──
    bad_b = []

    def walk2(o, path="root"):
        if isinstance(o, (int, float, bool)) or o is None:
            return
        if isinstance(o, str):
            for frag in re.findall(r"「([^」]*)」", o):
                if frag.strip() and seg.count(frag) < 1:
                    bad_b.append((path, frag))
        elif isinstance(o, dict):
            for k, v in o.items():
                if k == "quote":
                    continue
                # 两个**描述约定本身**的元字段不在被扫范围内（它们要写出「…」这个符号
                # 才能说明约定是什么），其余分区一律在范围内。这一豁免写在注释里，
                # 而不是让判据静默通过。
                if k in ("quotePolicy", "note") and path.endswith("inlineQuoteAudit"):
                    continue
                walk2(v, path + "." + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk2(v, "%s[%d]" % (path, i))

    walk2(cand)
    ok("B1 行内直角引号全部是切片内逐字子串", not bad_b, "bad=%r" % (bad_b[:4],))

    # ── P1：散文里的段号与紧邻引文 ──
    bad_para = []
    pat = re.compile(r"P(\d{3})[」』]?[（(]?[^。；，、）)→\n]{0,4}?「([^」]+)」")
    counter = {"refs": 0}

    def walk3(o, path="root"):
        if isinstance(o, (int, float, bool)) or o is None:
            return
        if isinstance(o, str):
            for m in re.finditer(r"P(\d{3})", o):
                counter["refs"] += 1
                if int(m.group(1)) not in pmap:
                    bad_para.append((path, "P" + m.group(1), "not-exist"))
            for m in pat.finditer(o):
                pn, frag = int(m.group(1)), m.group(2)
                if pn not in pmap:
                    continue
                a, b = pmap[pn]
                if frag not in text[a:b]:
                    bad_para.append((path, "P%03d" % pn, frag[:24]))
        elif isinstance(o, dict):
            for k, v in o.items():
                walk3(v, path + "." + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk3(v, "%s[%d]" % (path, i))

    walk3(cand)
    ok("P1 散文段号存在且紧邻引文归属正确", not bad_para,
       "refs=%d bad=%r" % (counter["refs"], bad_para[:4]))

    # ── Z1：零覆盖集合与处置表双向一致（自己重算覆盖）──
    cov = set()
    for _, q in quotes:
        cov.update(range(q["start"], q["end"]))
    zero = {o for o, a, b in lines if not any(i in cov for i in range(a, b))}
    disp = set(cand["reverseValidation"]["zeroCoverageDisposition"])
    ok("Z1 零覆盖段集合 == 处置表键集合（双向）",
       zero == {int(k[1:]) for k in disp},
       "只有覆盖缺处置=%r 只有处置无覆盖=%r"
       % (sorted("P%03d" % z for z in zero - {int(k[1:]) for k in disp}),
          sorted(disp - {"P%03d" % z for z in zero})))

    # ── 覆盖统计复算 ──
    non_space = {i for i in range(S, E) if not text[i].isspace()}
    decl = cand["coverageDeclaration"]
    ok("M2 引文节点数与并集码点数可复算",
       decl["quoteNodes"] == len(quotes) and decl["quoteUnionCodepoints"] == len(cov),
       "nodes %d/%d union %d/%d" % (decl["quoteNodes"], len(quotes),
                                    decl["quoteUnionCodepoints"], len(cov)))
    ok("M3 非空白码点数可复算", decl["nonSpaceCodepoints"] == len(non_space),
       "%d/%d" % (decl["nonSpaceCodepoints"], len(non_space)))
    touched = sum(1 for o, a, b in lines if any(i in cov for i in range(a, b)))
    ok("M4 被引段数可复算", decl["paragraphsTouchedByAtLeastOneQuote"] == touched,
       "%d/%d" % (decl["paragraphsTouchedByAtLeastOneQuote"], touched))

    # ── 内容分区存在性 ──
    want = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
    ok("S1 任务要求的内容分区全部存在", all(k in cand for k in want),
       "缺=%r" % [k for k in want if k not in cand])

    # ── 世界设定的三态字段完整性 ──
    # 本区间用的 kind 值是 place / item / rule（见任务 prompt 的 P3.10 口径）。
    # 初版这条判据把 'place' 判成非法——是**判据自己写错**，不是候选错；
    # 记在这里，因为它正是「校验脚本也会撒谎」的实例。
    KINDS = {"place", "item", "rule"}
    STATES = {"hold", "transfer", "use", "lose"}
    INSTS = {"declared", "executed", "misunderstood"}
    bad_ws = []
    for w in cand["worldSettings"]:
        k = w["kind"]
        if k not in KINDS:
            bad_ws.append((w["id"], "kind 非法 %r" % (k,)))
            continue
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            bad_ws.append((w["id"], "placeState 非法 %r" % (w.get("placeState"),)))
        if k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(x not in STATES for x in st):
                bad_ws.append((w["id"], "itemStates 非法 %r" % (st,)))
        if k == "rule" and w.get("institution") not in INSTS:
            bad_ws.append((w["id"], "institution 非法 %r" % (w.get("institution"),)))
    ok("S2 世界设定 kind 与三态字段齐备", not bad_ws, "%r" % (bad_ws[:4],))
    # 反向：断言本区间确实产出过至少一条 place 与一条 rule（否则 S2 可能空转）
    kinds = {w["kind"] for w in cand["worldSettings"]}
    ok("S2b kind 覆盖面（place/item/rule 都出现过）", {"place", "item", "rule"} <= kinds, "%r" % (kinds,))
    insts = {w.get("institution") for w in cand["worldSettings"] if w["kind"] == "rule"}
    ok("S2c 规则三态至少出现过两种（否则三态字段是装饰）", len(insts) >= 2, "%r" % (insts,))

    # ── 伏笔：未回收必须写明原因 ──
    bad_f = [(f["id"], f["status"]) for f in cand["foreshadows"]
             if f["status"] != "resolved-in-range" and not f.get("unresolvedReason")]
    ok("S3 未回收伏笔全部写明原因", not bad_f, "%r" % (bad_f,))

    # ── 主题读法三件齐备 ──
    bad_th = [(t["id"], bool(t.get("support")), bool(t.get("counter")), bool(t.get("perspective")))
              for t in cand["themeReadings"] if not (t.get("support") and t.get("counter") and t.get("perspective"))]
    ok("S4 主题读法 perspective/support/counter 齐备", not bad_th, "%r" % (bad_th,))

    # ── 变异测试：证明判据不是空转 ──
    muts = []

    def mutate(fn):
        c = json.loads(json.dumps(cand))
        fn(c)
        return c

    def q1_mut(c):
        c["tasks"][0]["objective"]["quotes"][0]["start"] += 1

    def q3_mut(c):
        # 必须选一个**在切片里真的出现 ≥2 次**的串。初版改成的「夜色」在切片里只出现 1 次，
        # 于是「命中唯一」这条判据正确地没有报警——是变异体不合格，不是判据空转。
        assert seg.count("红莲") >= 2, "变异体前提不成立：红莲在切片里只出现 %d 次" % seg.count("红莲")
        c["tasks"][0]["objective"]["quotes"][0]["quote"] = "红莲"

    def c1_mut(c):
        src = c["tasks"][0]["obstacle"]["quotes"][0]
        c["tasks"][0]["cost"] = {"text": "x", "basis": "inferred",
                                 "quotes": [dict(src)], "note": "x"}

    def n1_mut(c):
        c["tasks"][0]["costNote"] = ""

    def z1_mut(c):
        k = sorted(c["reverseValidation"]["zeroCoverageDisposition"])[0]
        del c["reverseValidation"]["zeroCoverageDisposition"][k]

    def ws_mut(c):
        c["worldSettings"][0]["placeState"] = None

    for name, fn, checker in [
        ("MUT-Q1 偏移挪 1 位", q1_mut,
         lambda c: any(text[q["start"]:q["end"]] != q["quote"]
                       for _, q in _qs(c))),
        ("MUT-Q3 引文改成切片内出现≥2次的串", q3_mut,
         lambda c: any(seg.count(q["quote"]) != 1 for _, q in _qs(c))),
        ("MUT-C1 把 obstacle 的引文塞进 cost", c1_mut,
         lambda c: _has_overlap(c)),
        ("MUT-N1 删掉空栏理由", n1_mut,
         lambda c: any(t.get(x) is None and len(t.get(x + "Note") or "") < 10
                       for t in c["tasks"] for x in ("objective", "obstacle", "action", "result", "cost"))),
        ("MUT-Z1 从处置表删一项", z1_mut,
         lambda c: ({o for o, a, b in lines if not any(i in _cov(c) for i in range(a, b))}
                    != {int(k[1:]) for k in c["reverseValidation"]["zeroCoverageDisposition"]})),
        ("MUT-WS 清掉 placeState", ws_mut,
         lambda c: any(w["kind"] == "place" and not w.get("placeState") for w in c["worldSettings"])),
    ]:
        mutated = mutate(fn)
        caught = checker(mutated)
        muts.append((name, caught))
        print("%s %s（变异应被抓到）" % ("PASS" if caught else "FAIL", name))
    ok("M1 变异测试全部被抓到（判据非空转）", all(c for _, c in muts), "%r" % (muts,))

    print("\n通过 %d 项，失败 %d 项" % (len(passes), len(fails)))
    return 1 if fails else 0


def _qs(c):
    out = []

    def w(o):
        if isinstance(o, dict):
            if "quote" in o and "start" in o:
                out.append(("", o))
            for v in o.values():
                w(v)
        elif isinstance(o, list):
            for v in o:
                w(v)

    w(c)
    return out


def _cov(c):
    cov = set()
    for _, q in _qs(c):
        cov.update(range(q["start"], q["end"]))
    return cov


def _has_overlap(c):
    for t in c["tasks"]:
        cols = [(n, t[n]) for n in ("objective", "obstacle", "action", "result", "cost") if t.get(n)]
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                for q1 in cols[i][1]["quotes"]:
                    for q2 in cols[j][1]["quotes"]:
                        if q1["start"] < q2["end"] and q2["start"] < q1["end"]:
                            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
