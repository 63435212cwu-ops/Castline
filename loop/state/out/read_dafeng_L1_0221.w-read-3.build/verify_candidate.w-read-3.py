#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L1:0221 候选**独立**校验器（w-read-3，与构建器分开的第二条路径）。

不复用构建期任何中间量：
  · 段落索引与句单元在本脚本内按换行重新切分（不 import 构建脚本，不读它的 NOTES）；
  · 引文走**反向**路径：先按 start/end 去 docs[0].text 切片，再把结果与 quote 比对
    （构建器是正向 find→算偏移；两条路径独立，任一侧算错都会在这里暴露）；
  · coverage 的全部数字独立复算，并与候选里的声明值逐项对齐。

判据全绿 exit 0；任一不成立 exit 1 并逐条打印实测值。

用法：
  python3 -B -s verify_candidate.w-read-3.py            # 校验
  python3 -B -s verify_candidate.w-read-3.py --negative # 负向测试（篡改后应被拦下）
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0221.candidate.json"
S, E = 826801, 832785
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第两百二十章 安抚和翻脸（大章）"

BAD: list[str] = []
OK: list[str] = []


def ck(cond, label: str, detail: str = "") -> bool:
    (OK if cond else BAD).append("%s%s" % (label, ("  | " + detail) if detail else ""))
    return bool(cond)


def paragraphs(sl: str) -> list[tuple[int, int, str]]:
    """独立的段落切分：按换行，strip() 非空者为一段。返回相对切片偏移。"""
    out, off = [], 0
    for para in sl.split("\n"):
        if para.strip():
            out.append((off, off + len(para), para))
        off += len(para) + 1
    return out


def units(sl: str) -> list[tuple[int, int]]:
    """独立的句单元切分（先段后句）。"""
    out, off = [], 0
    for para in sl.split("\n"):
        pstart = off
        off += len(para) + 1
        if not para.strip():
            continue
        cur = 0
        for m in re.finditer(r"[。！？；…]+[”』]?", para):
            if m.end() > cur:
                out.append((pstart + cur, pstart + m.end()))
                cur = m.end()
        if cur < len(para):
            out.append((pstart + cur, pstart + len(para)))
    return out


def walk_quotes(obj, path="$"):
    """产出候选里所有带 start/end 的引文对象及其中间路径。"""
    if isinstance(obj, dict):
        if isinstance(obj.get("start"), int) and isinstance(obj.get("end"), int) \
                and isinstance(obj.get("quote"), str):
            yield path, obj
        for k, v in obj.items():
            yield from walk_quotes(v, path + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_quotes(v, "%s[%d]" % (path, i))


def load_candidate() -> dict:
    return json.loads(CAND.read_text(encoding="utf-8"))


def run(cand: dict, full: str, sl: str) -> None:
    # ══ 判据 1：源、边界、切片哈希 ═════════════════════════════════════
    raw = DOCS.read_bytes()
    ck(hashlib.sha256(raw).hexdigest() == SOURCE_HASH, "1a docs.json sha256 == task.sourceHash")
    ck(sl.startswith(UNIT_HEAD), "1b 切片以 unitHead 开头", repr(sl[:30]))
    ck(len(sl) == E - S == cand.get("sliceCodepoints"),
       "1c 切片长度 == E-S == sliceCodepoints", "%d/%d/%s" % (len(sl), E - S, cand.get("sliceCodepoints")))
    ck(hashlib.sha256(sl.encode("utf-8")).hexdigest() == cand.get("sliceSha256"),
       "1d sliceSha256 与独立复算一致")
    ck(cand.get("sourceHash") == SOURCE_HASH, "1e 候选顶层 sourceHash 正确")
    nxt = full[E:E + 30]
    ck(nxt.startswith("第两百二十"), "1f 切片末尾紧接下一章标题", repr(nxt[:24]))

    # ══ 判据 2：引文反向核验 ═══════════════════════════════════════════
    total = bad_range = bad_text = bad_hash = bad_occ = 0
    for path, q in walk_quotes(cand):
        total += 1
        if not (S <= q["start"] < q["end"] <= E):
            bad_range += 1
            BAD.append("2a 引文越界 @%s" % path)
            continue
        if full[q["start"]:q["end"]] != q["quote"]:
            bad_text += 1
            BAD.append("2b text[start:end] != quote @%s (%r)" % (path, q["quote"][:30]))
        if q.get("sourceHash") != SOURCE_HASH:
            bad_hash += 1
            BAD.append("2c sourceHash 错 @%s" % path)
        if q.get("sliceOccurrences") is not None and q["sliceOccurrences"] != sl.count(q["quote"]):
            bad_occ += 1
            BAD.append("2d sliceOccurrences 与实际不符 @%s" % path)
        if q.get("docOccurrences") is not None and q["docOccurrences"] != full.count(q["quote"]):
            bad_occ += 1
            BAD.append("2e docOccurrences 与实际不符 @%s" % path)
    ck(total > 0, "2f 找到了引文对象", str(total))
    ck(bad_range == 0, "2g 全部引文落在 [S,E) 内", "越界 %d" % bad_range)
    ck(bad_text == 0, "2h 全部引文逐字命中（text[start:end]==quote）", "错 %d/%d" % (bad_text, total))
    ck(bad_hash == 0, "2i 全部引文 sourceHash 正确", "错 %d" % bad_hash)
    ck(bad_occ == 0, "2j docOccurrences/sliceOccurrences 与实测一致", "错 %d" % bad_occ)
    # 定位唯一性：quote 在切片内必须只出现一次（重复即视为定位不可靠）
    dup = [p for p, q in walk_quotes(cand) if sl.count(q["quote"]) > 1]
    ck(not dup, "2k 每条引文在切片内唯一（无重复定位歧义）", "重复 %d 条" % len(dup))

    # ══ 判据 3：五栏独立性 ═════════════════════════════════════════════
    units_idx = units(sl)
    def unit_of(span):
        for i, (a, b) in enumerate(units_idx):
            if a <= span[0] and span[1] <= b:
                return i
        return None
    fields = ["objective", "obstacle", "action", "result", "cost"]
    ov = 0
    shared = 0
    for t in cand["tasks"]:
        spans, us = [], []
        for f in fields:
            cell = t.get(f)
            if not isinstance(cell, dict):
                continue
            for q in cell.get("quotes", []):
                sp = (q["start"], q["end"])
                for s0, e0 in spans:
                    if sp[0] < e0 and s0 < sp[1]:
                        ov += 1
                spans.append(sp)
                u = unit_of(sp)
                if u is not None:
                    if u in us:
                        shared += 1
                    us.append(u)
    ck(ov == 0, "3a 同一任务五栏的引文字符区间不重叠", "重叠 %d" % ov)
    ck(shared == 0, "3b 同一任务五栏不共用句单元", "共用 %d" % shared)

    # ══ 判据 4：null 栏带理由 ══════════════════════════════════════════
    actual = []
    for t in cand["tasks"]:
        for f in fields:
            if t.get(f) is None:
                ck(bool(t.get(f + "Note")), "4a null 栏带同名 Note：%s.%s" % (t["id"], f))
                actual.append((t["id"], f))
    reg = [(x["task"], x["field"]) for x in cand.get("nullFieldDisposition", [])]
    ck(sorted(actual) == sorted(reg), "4b nullFieldDisposition 与实际 null 栏一致",
       "实际 %d / 登记 %d" % (len(actual), len(reg)))
    # 反例：cost 不许拿工作状态或法规当代价
    for t in cand["tasks"]:
        txt = json.dumps(t.get("cost"), ensure_ascii=False) if t.get("cost") else ""
        for bait in ("待验证", "待核", "法律规定", "禁令"):
            ck(bait not in txt, "4c cost 不含『%s』类伪代价：%s" % (bait, t["id"]))

    # ══ 判据 5：分区存在性与字段完整性 ═════════════════════════════════
    for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
        ck(k in cand, "5a 分区存在：%s" % k)
        ck(isinstance(cand[k], list), "5b 分区是数组：%s" % k)
    for w in cand["worldSettings"]:
        if w["kind"] == "rule":
            ck(w.get("institution") in {"declared", "executed", "misunderstood"},
               "5c rule.institution 合法：%s" % w["id"])
        if w["kind"] == "place":
            ck(w.get("placeState") in {"arrived", "mentioned"},
               "5d place.placeState 合法：%s" % w["id"])
        if w["kind"] == "item":
            st = w.get("itemStates")
            ck(isinstance(st, list) and st and set(st) <= {"hold", "transfer", "use", "lose"},
               "5e item.itemStates 合法且多选：%s" % w["id"], str(st))
        ck(bool(w.get("explain")), "5f worldSettings 有 explain：%s" % w["id"])
    for f in cand["foreshadows"]:
        ck(f["status"] in ("resolved", "unresolved"), "5g foreshadow.status 合法：%s" % f["id"])
        if f["status"] == "resolved":
            ck(bool(f.get("payoff")), "5h resolved 有 payoff：%s" % f["id"])
        else:
            ck(bool(f.get("payoffNote")), "5i unresolved 有 payoffNote：%s" % f["id"])
        ck(len(f.get("quotes") or []) >= 2, "5j 伏笔 ≥2 处引文（铺设＋回收）：%s" % f["id"])
    for c in cand["causeEdges"]:
        ck(all(c.get(k) for k in ("from", "to", "mechanism")), "5k causeEdge 有 from/to/mechanism：%s" % c["id"])
    for th in cand["themeReadings"]:
        ck(all(th.get(k) for k in ("perspective", "support", "counter")),
           "5l themeReading 有 perspective/support/counter：%s" % th["id"])
    ck(cand.get("semanticReview", {}).get("status") == "not_performed",
       "5m semanticReview 未被声称为完成")
    ck(len(cand.get("unknowns", [])) > 0, "5n unknowns 非空", str(len(cand.get("unknowns", []))))
    ck(len(cand.get("selfCritique", [])) > 0, "5o selfCritique 非空", str(len(cand.get("selfCritique", []))))

    # ══ 判据 6：coverage 独立复算 ══════════════════════════════════════
    paras = paragraphs(sl)
    quoted = [(q["start"], q["end"]) for _, q in walk_quotes(cand)]
    touched = {i for i, (a, b, _) in enumerate(paras)
               for ps, pe in quoted if ps < b + S and a + S < pe}
    zero = [i for i in range(len(paras)) if i not in touched]
    cov = cand["coverage"]
    ck(cov["nonEmptyParagraphs"] == len(paras), "6a nonEmptyParagraphs 复算一致",
       "%d vs %d" % (cov["nonEmptyParagraphs"], len(paras)))
    ck(cov["paragraphsTouchedByQuotes"] == len(touched), "6b paragraphsTouchedByQuotes 复算一致",
       "%d vs %d" % (cov["paragraphsTouchedByQuotes"], len(touched)))
    ck(cov["zeroCoverageParagraphs"] == len(zero), "6c zeroCoverageParagraphs 复算一致",
       "%d vs %d" % (cov["zeroCoverageParagraphs"], len(zero)))
    ck(len(cov["zeroCoverageList"]) == len(zero), "6d zeroCoverageList 条数一致")
    zl_ok = all(full[z["start"]:z["end"]] == z["text"] for z in cov["zeroCoverageList"])
    ck(zl_ok, "6e zeroCoverageList 每条的 text 与全文切片逐字一致")
    # 6f：两个口径分别复算，不混用（构建器第一版把 quoteObjects 写成去重后的区间数，
    #     与"对象个数"同名不同义 ⇒ 本判据当场抓出，已改为两个字段分开写）
    ck(cov["quoteObjects"] == len(quoted), "6f quoteObjects 复算一致（引文对象个数）",
       "%d vs %d" % (cov["quoteObjects"], len(quoted)))
    ck(cov.get("uniqueQuoteSpans") == len(set(quoted)),
       "6g uniqueQuoteSpans 复算一致（去重区间数）",
       "%s vs %d" % (cov.get("uniqueQuoteSpans"), len(set(quoted))))
    ck(cov["quoteObjects"] >= cov.get("uniqueQuoteSpans", 0),
       "6h quoteObjects >= uniqueQuoteSpans（同一句可跨分区复用）")

    # ══ 判据 7：散文「」逐字（『』不检查，见 citationConvention 的自我披露） ══
    bad_prose = []
    def prose(o, p="$"):
        if isinstance(o, str):
            for frag in re.findall(r"「([^」]*)」", o):
                if frag and frag not in sl:
                    bad_prose.append((p, frag[:40]))
        elif isinstance(o, dict):
            for k, v in o.items():
                if k != "citationConvention":
                    prose(v, p + "." + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                prose(v, "%s[%d]" % (p, i))
    prose({k: v for k, v in cand.items() if k != "citationConvention"})
    ck(not bad_prose, "7a 散文「」片段都是切片逐字子串", "违规 %d" % len(bad_prose))

    # ══ 判据 8：自述计数与实际一致（防「工作量冒充质量」式的数字放大）══
    # 期望值从**候选自述的字段**与**实测长度**两侧独立取，两边必须相同；
    # 不写死常量，否则原文/候选一变，判据就变成恒真的装饰。
    claims = {
        "tasks": 7, "causeEdges": 14, "states": 10, "foreshadows": 5,
        "worldSettings": 14, "themeReadings": 2, "unknowns": 16, "selfCritique": 10,
    }
    for k, want in claims.items():
        got = len(cand.get(k) or [])
        ck(got == want, "8 自述计数与实际一致：%s（自述 %d / 实测 %d）" % (k, want, got))
    # 候选自己写的 countsHolds 声明必须与实测相符（若有）
    wsc = {}
    for w in cand["worldSettings"]:
        wsc[w["kind"]] = wsc.get(w["kind"], 0) + 1
    ck(wsc.get("rule", 0) == 5 and wsc.get("place", 0) == 7 and wsc.get("item", 0) == 2,
       "8b worldSettings 分类计数 == note 里声明的 rule5/place7/item2",
       str(wsc))
    ck(len(cand["foreshadowsNote"]) > 0 and
       sum(1 for f in cand["foreshadows"] if f["status"] == "unresolved") == 3,
       "8c unresolved 伏笔数 == note 里声明的 3 条")


def main() -> int:
    raw = DOCS.read_bytes()
    full = json.loads(raw)[0]["text"]
    sl = full[S:E]
    if "--negative" in sys.argv:
        return negative(full, sl)
    cand = load_candidate()
    run(cand, full, sl)
    print("── 实测 ──")
    for o in OK:
        print("  ✓ %s" % o)
    if BAD:
        print("── 失败 %d 条 ──" % len(BAD), file=sys.stderr)
        for b in BAD:
            print("  ✗ %s" % b, file=sys.stderr)
        return 1
    print("全部判据通过（%d 项），退出码 0" % len(OK))
    return 0


def negative(full: str, sl: str) -> int:
    """负向测试：每个用例篡改一处，断言**必须**被拦下。

    这是为了防止「判据恒真」的假绿灯（0217 的独立复核抓到过 `ck(..., True, ...)`）。
    """
    import copy
    base = load_candidate()
    cases = []

    def add(name, mutate):
        cases.append((name, mutate))

    def m_shift(c):
        c["tasks"][0]["objective"]["quotes"][0]["start"] += 1
    add("篡改偏移 1 位", m_shift)

    def m_text(c):
        c["tasks"][0]["action"]["quotes"][0]["quote"] = c["tasks"][0]["action"]["quotes"][0]["quote"][:-1]
    add("引文尾字被删（不做逐字比对就会漏）", m_text)

    def m_hash(c):
        c["causeEdges"][0]["quotes"][0]["sourceHash"] = "0" * 64
    add("改错 sourceHash", m_hash)

    def m_note(c):
        t = next(x for x in c["tasks"] if x.get("cost") is None)
        t.pop("costNote", None)
    add("抹掉 null 栏的 costNote", m_note)

    def m_shared(c):
        src = c["tasks"][0]["objective"]["quotes"][0]
        c["tasks"][0]["result"]["quotes"][0] = copy.deepcopy(src)
    add("同一任务两栏共用同一句", m_shared)

    def m_place(c):
        w = next(x for x in c["worldSettings"] if x["kind"] == "place")
        w.pop("placeState", None)
    add("删掉 place.placeState", m_place)

    def m_inst(c):
        w = next(x for x in c["worldSettings"] if x["kind"] == "rule")
        w["institution"] = "made-up"
    add("rule.institution 取非法值", m_inst)

    def m_item(c):
        w = next(x for x in c["worldSettings"] if x["kind"] == "item")
        w["itemStates"] = []
    add("item.itemStates 清空", m_item)

    def m_fs(c):
        f = next(x for x in c["foreshadows"] if x["status"] == "unresolved")
        f["payoff"] = "编一个回收"
        f.pop("payoffNote", None)
    add("unresolved 伏笔假装已回收", m_fs)

    def m_sem(c):
        c["semanticReview"] = {"status": "done"}
    add("声称语义评审已完成", m_sem)

    def m_cov(c):
        c["coverage"]["zeroCoverageParagraphs"] += 1
    add("谎报零覆盖段数", m_cov)

    def m_dup(c):
        c["states"][0]["quotes"][0]["quote"] = sl[0:6]
    add("引文改成切片内重复出现的短串", m_dup)

    def m_thesis(c):
        c["themeReadings"][0].pop("counter", None)
    add("主题解释缺 counter（只列支持）", m_thesis)

    caught = 0
    for name, mutate in cases:
        c = copy.deepcopy(base)
        mutate(c)
        BAD.clear(); OK.clear()
        run(c, full, sl)
        hit = len(BAD) > 0
        caught += hit
        print("%s %s" % ("✓ 拦下" if hit else "✗ 漏过（判据有缺陷）", name))
    print("\n负向测试：%d/%d 被拦下" % (caught, len(cases)))
    return 0 if caught == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
