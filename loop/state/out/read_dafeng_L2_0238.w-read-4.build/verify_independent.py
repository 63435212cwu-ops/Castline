#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L2:0238 候选的**独立重算**（w-read-4，与构建器互不 import）。

独立性的具体做法（不是声明，是结构）：
  · 本脚本**不 import** build_candidate.py，也**不 import** content_spec_a/b；
    它从磁盘上的候选 JSON 重新开始，源文件重新打开、源哈希重算。
  · 段与句单元在本脚本内**另行切分**（不共用构建器的切段函数）。
  · 259 条引文逐条重新 text.find / text[start:end] 比对，偏移与段锚一律重算。
  · 判据 C07 是**变异测试**：把一条引文的末字符改坏、把另一条的 start +1，
    两次都必须让 C04 报红 —— 用来证明这套判据不是恒真。

可复现：
  python3 -B -s loop/state/out/read_dafeng_L2_0238.w-read-4.build/verify_independent.py
"""
import hashlib
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAND = ROOT / "loop/state/out/read_dafeng_L2_0238.candidate.json"
SOURCE = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
RANGE = (948891, 956444)
UNIT_HEAD = "第九章 案件有了重大突破"

results = []


def check(cid, name, ok, detail=""):
    results.append((cid, name, bool(ok), detail))
    return ok


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def walk_quotes(node, path=""):
    if isinstance(node, dict):
        if isinstance(node.get("quotes"), list):
            for i, q in enumerate(node["quotes"]):
                if isinstance(q, dict) and "quote" in q:
                    yield path + "/quotes[%d]" % i, q
        for k, v in node.items():
            if k != "quotes":
                yield from walk_quotes(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quotes(v, path + "[%d]" % i)


def main():
    doc = json.loads(SOURCE.read_text(encoding="utf-8"))
    text = doc[0]["text"]
    seg = text[RANGE[0]:RANGE[1]]
    cand = json.loads(CAND.read_text(encoding="utf-8"))

    # ── C01 源哈希（重算，不信候选里的值）────────────────────────────────
    real = sha256_file(SOURCE)
    check("C01", "源文件 sha256 == 任务声明 == 候选声明",
          real == SOURCE_HASH == cand["source"]["sourceHash"], real[:16])

    # ── C02 切片以单元标题开头 + 切片哈希自算 ─────────────────────────────
    check("C02", "docs[0].text[start:end] 以单元标题开头", seg.startswith(UNIT_HEAD), repr(seg[:24]))
    check("C02b", "切片 sha256（本脚本自算）与候选一致",
          hashlib.sha256(seg.encode("utf-8")).hexdigest() == cand["source"]["segmentSha256"])

    # ── C03 段与句单元**独立重切**（不用构建器的函数）────────────────────
    paras = {}
    for i, m in enumerate(re.finditer(r"[^\n]+", seg)):
        paras["P%03d" % i] = (RANGE[0] + m.start(), RANGE[0] + m.end())
    check("C03", "独立重切段数 == 候选声明段数",
          len(paras) == cand["source"]["nonEmptyParagraphs"] == 195, str(len(paras)))

    # ── C04 全量引文：逐字 / 偏移 / 区间 / 哈希 / 次数 / 段锚 ───────────────
    quotes = list(walk_quotes(cand))
    bad = []
    for path, q in quotes:
        if text[q["start"]:q["end"]] != q["quote"]:
            bad.append((path, "slice!=quote"))
        if q["quote"] not in text:
            bad.append((path, "find 失败"))
        if not (RANGE[0] <= q["start"] and q["end"] <= RANGE[1]):
            bad.append((path, "越界"))
        if q["sourceHash"] != SOURCE_HASH:
            bad.append((path, "hash"))
        if q["occurrencesInRange"] != seg.count(q["quote"]):
            bad.append((path, "区间次数"))
        if q["wholeTextOccurrences"] != text.count(q["quote"]):
            bad.append((path, "全文次数"))
        p = paras.get(q["paraLabel"])
        if p is None or not (p[0] <= q["start"] and q["end"] <= p[1]):
            bad.append((path, "段锚错位"))
    check("C04", "全量引文逐字且偏移/段锚/次数全对（%d 条）" % len(quotes), not bad, str(bad[:4]))

    # ── C05 固定种子抽样，人工可复核 ─────────────────────────────────────
    rnd = random.Random(20261015)
    sample = rnd.sample(quotes, 5)
    s_ok = all(text[q["start"]:q["end"]] == q["quote"] for _, q in sample)
    check("C05", "seed=20261015 抽 5 条全部逐字且偏移一致", s_ok,
          "; ".join("%s@%d" % (p.split("/")[1] if "/" in p else p, q["start"]) for p, q in sample))

    # ── C06 任务五栏互不共用引文（字符串级 + 跨度级）──────────────────────
    conf = []
    for t in cand["tasks"]:
        cols = ["objective", "obstacle", "action", "result", "cost"]
        seen = {}
        for c in cols:
            col = t.get(c)
            for q in (col.get("quotes", []) if isinstance(col, dict) else []):
                if q["quote"] in seen:
                    conf.append((t["id"], seen[q["quote"]], c))
                seen[q["quote"]] = c
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                a = t[cols[i]].get("quotes", []) if isinstance(t.get(cols[i]), dict) else []
                b = t[cols[j]].get("quotes", []) if isinstance(t.get(cols[j]), dict) else []
                for x in a:
                    for y in b:
                        if x["start"] < y["end"] and y["start"] < x["end"]:
                            conf.append((t["id"], cols[i], cols[j], "跨度重叠"))
    check("C06", "任务五栏引文互不共用（字符串级 + 跨度级）", not conf, str(conf[:3]))

    # ── C07 变异测试：判据不是恒真 ───────────────────────────────────────
    probe = dict(quotes[0][1])
    m1 = dict(probe)
    m1["quote"] = m1["quote"][:-1] + ("X" if not m1["quote"].endswith("X") else "Y")
    red1 = text[m1["start"]:m1["end"]] != m1["quote"]
    m2 = dict(probe)
    m2["start"] = m2["start"] + 1
    red2 = text[m2["start"]:m2["end"]] != m2["quote"]
    check("C07", "变异测试：改坏末字符 / start+1 都让 C04 形态报红", red1 and red2,
          "末字符=%s 偏移=%s" % (red1, red2))

    # ── C08 null 栏必须有同名 Note（逐条非空）────────────────────────────
    np_ = [(t["id"], c) for t in cand["tasks"]
           for c in ("objective", "obstacle", "action", "result", "cost")
           if t.get(c) is None and not (t.get(c + "Note") or "").strip()]
    check("C08", "每个 null 栏都有非空同名 Note（不写理由的 null 不算已确认）", not np_, str(np_))

    # ── C09 worldSettings 判别字段 ───────────────────────────────────────
    wbad = []
    for w in cand["worldSettings"]:
        k = w.get("kind")
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            wbad.append((w["id"], "institution"))
        elif k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            wbad.append((w["id"], "placeState"))
        elif k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(
                    s not in ("hold", "transfer", "use", "lose") for s in st):
                wbad.append((w["id"], "itemStates"))
        elif k not in ("rule", "place", "item"):
            wbad.append((w["id"], "kind"))
    kinds = {}
    for w in cand["worldSettings"]:
        kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
    check("C09", "worldSettings 判别字段合法（%s）" % kinds, not wbad, str(wbad))

    # ── C10 内容分区齐全 + 分区计数与 coverage 自述一致 ───────────────────
    need = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
    miss = [k for k in need if k not in cand]
    cov = cand.get("coverage", {})
    mismatch = [k for k in need if isinstance(cand.get(k), list) and cov.get(k) != len(cand[k])]
    check("C10", "六个必需分区齐全且 coverage 计数与实际长度一致", not miss and not mismatch,
          "miss=%s mismatch=%s" % (miss, mismatch))

    # ── C11 主题读法三件套 ───────────────────────────────────────────────
    tbad = [(t["id"], k) for t in cand["themeReadings"]
            for k in ("perspective", "support", "counter") if not t.get(k)]
    check("C11", "主题读法每条都有 perspective/support/counter（%d 条）" % len(cand["themeReadings"]),
          not tbad and len(cand["themeReadings"]) <= 2, str(tbad))

    # ── C12 伏笔：resolved 必须有 payoff，unresolved 必须写明原因 ─────────
    fbad = []
    for f in cand["foreshadows"]:
        if f.get("resolved") is True and not f.get("payoff"):
            fbad.append((f["id"], "resolved 缺 payoff"))
        if f.get("resolved") is False and not f.get("unresolvedNote"):
            fbad.append((f["id"], "unresolved 缺说明"))
    check("C12", "伏笔 resolved/unresolved 与 setup/payoff 自洽", not fbad, str(fbad))

    # ── C13 角标（切片口径）+ 每条『』跨度逐字 ────────────────────────────
    def prose(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k not in ("quote", "quotes"):
                    yield from prose(v)
        elif isinstance(node, list):
            for v in node:
                yield from prose(v)
        elif isinstance(node, str):
            yield node

    nv, mw = [], []
    for s in prose(cand):
        for m in re.finditer(r"[『「]([^『』「」\n]{1,120})[』」]", s):
            if m.group(1) not in seg:
                nv.append(m.group(1)[:30])
        for m in re.finditer(r"〔([^〔〕\n]{1,120})〕", s):
            if m.group(1) in seg:
                mw.append(m.group(1)[:30])
    check("C13", "角标纪律（切片口径）：『』全逐字、〔〕全非逐字", not nv and not mw,
          "非逐字『』=%s 逐字〔〕=%s" % (nv[:3], mw[:3]))

    # ── C14 语义层未越权：semanticReview 不得写成完成 ────────────────────
    sr = cand.get("semanticReview")
    check("C14", "semanticReview 如实写 not-performed（引文定位正确 ≠ 语义已核验）",
          sr == "not-performed", str(sr))

    # ── C15 段覆盖率（反向验证的输入，不是通过/失败判据）─────────────────
    cited = {q["paraLabel"] for _, q in quotes}
    uncited = sorted(set(paras) - cited)
    check("C15", "段覆盖：%d/%d 段被引用（未引用 %d 段，见报告清单）"
          % (len(cited), len(paras), len(uncited)), True, ",".join(uncited))

    # ── C16 因果边：from/to/机制齐全，引文成对，且方向已交代 ──────────────
    ebad = []
    for e in cand["causeEdges"]:
        if not e.get("frm") or not e.get("to") or not e.get("mechanism") or len(e["quotes"]) < 2:
            ebad.append((e["id"], "结构不全"))
        starts = [q["start"] for q in e["quotes"]]
        if starts != sorted(starts) and not e.get("directionNote"):
            ebad.append((e["id"], "顺序倒置且无 directionNote"))
    check("C16", "因果边结构完整、引文按原文顺序或已写明方向理由（%d 条）" % len(cand["causeEdges"]),
          not ebad, str(ebad))

    # ── C17 未被引用的段里有没有明显该被覆盖的内容（反向验证探针）────────
    probes = [
        ("P096", "福妃坠楼当日"), ("P097", "心甘情愿的私通"), ("P103", "贤者时间"),
        ("P126", "老嬷嬷有些犹豫"), ("P161", "今天先到此为止"), ("P166", "至少证明太子是无辜的"),
        ("P177", "第一顺位继承人"), ("P180", "宫斗其实很简单粗暴"), ("P184", "父皇的心思谁都猜不准"),
    ]
    still_missing = [(p, k) for p, k in probes if p not in cited and k in paras.get(p, ("", ""))[0:0] + (paras[p][0], paras[p][1]) and False]
    still_missing = [(p, k) for p, k in probes if p not in cited and k in seg[paras[p][0] - RANGE[0]:paras[p][1] - RANGE[0]]]
    check("C17", "反向验证探针：上一轮补进去的 %d 处高价值事实都已被引用" % len(probes),
          not still_missing, str(still_missing))

    # ── 输出 ─────────────────────────────────────────────────────────────
    print("read:dafeng:L2:0238 独立重算报告")
    print("候选：%s" % CAND.relative_to(ROOT))
    print("候选 sha256：%s" % sha256_file(CAND))
    print("源哈希（自算）：%s" % real)
    print("引文节点：%d 条" % len(quotes))
    print("-" * 78)
    fails = 0
    for cid, name, ok, detail in results:
        print("%-5s %-4s %s" % (cid, "PASS" if ok else "FAIL", name))
        if detail:
            print("            %s" % detail[:400])
        if not ok:
            fails += 1
    print("-" * 78)
    print("小结：%d 项判据，%d 项 FAIL" % (len(results), fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
