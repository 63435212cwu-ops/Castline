#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L1:0221 候选构建器（w-read-3）。

设计原则：**偏移从不手写**。content_core 里每条引文只给字符串（Q("…")），
本脚本在**切片内** find 定位，再 +S 换算成相对 docs[0].text 全文的 codepoint 偏移。

任一判据不成立即 exit 1 且**不写盘**（避免留下半成品被后续 agent 误当产物）。

判据：
  1  源文件 sha256 == sourceHash；docs[0].text[S:E] 以 unitHead 开头；长度 == E-S
  2  引文：slice.find(quote) >= 0（唯一，重复即失败）；end<=len(slice)；start/end 全文口径；
     text[start:end] == quote 逐字
  3  五栏独立性：同一任务内 objective/obstacle/action/result/cost 的引文
     (a) 字符区间不重叠（同一 quote 不两用）(b) 句子单元不共用
  4  null 栏必须带同名 <栏位>Note；nullFieldDisposition 与实际 null 栏一致
  5  散文里的「」片段必须是切片内逐字子串（『』不检查）
  6  worldSettings：kind 合法；rule 必须有 institution；place 必须有 placeState；
     item 必须有 itemStates 且取值在 hold/transfer/use/lose 内；quote 与 quotes[0] 一致
  7  foreshadows：status ∈ {resolved, unresolved}；resolved 必须有 payoff；
     unresolved 必须有 payoffNote
  8  causeEdges：必须有 from/to/mechanism；每条 ≥1 引文
  9  themeReadings：必须有 perspective/support/counter 三件
 10  unknowns / selfCritique 非空且各有必需字段
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
S, E = 826801, 832785
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第两百二十章 安抚和翻脸（大章）"
OUT = ROOT / "loop/state/out/read_dafeng_L1_0221.candidate.json"
BUILD = ROOT / "loop/state/out/read_dafeng_L1_0221.w-read-3.build"

FAILS: list[str] = []
NOTES: list[str] = []


def ck(cond, msg: str, detail: str = "") -> bool:
    if not cond:
        FAILS.append(msg + (("  | " + detail) if detail else ""))
    return bool(cond)


def qdict(quote: str, sl: str, full: str) -> dict:
    """在切片内定位一次，换算全文偏移，返回引文字典。"""
    idx = sl.find(quote)
    ck(idx >= 0, "引文在切片内找不到", repr(quote[:60]))
    if idx < 0:
        return {"quote": quote, "start": None, "end": None, "sourceHash": SOURCE_HASH}
    ck(sl.find(quote, idx + 1) < 0,
       "引文在切片内出现多次（定位不唯一，不允许取第一次糊过去）", repr(quote[:60]))
    start, end = S + idx, S + idx + len(quote)
    ck(full[start:end] == quote, "text[start:end] != quote", repr(quote[:40]))
    return {"quote": quote, "start": start, "end": end,
            "docOccurrences": full.count(quote), "sliceOccurrences": sl.count(quote),
            "sourceHash": SOURCE_HASH}


# ── 句单元切分（用于判据 3b）─────────────────────────────────────────────
def sentence_units(sl: str) -> list[tuple[int, int]]:
    """先按段切、再段内按句末标点切。

    直接对全片切句会让中文引语收尾的 ” 落到下一单元，把相邻两句误判成共用
    （0217 的构建脚本第一版踩过，见其 assertions）。这里照做：按段切后再段内切。
    """
    units: list[tuple[int, int]] = []
    off = 0
    for para in sl.split("\n"):
        pstart = off
        off += len(para) + 1
        if not para.strip():
            continue
        cur = 0
        for m in re.finditer(r"[。！？；…]+[”』]?", para):
            if m.end() > cur:
                units.append((pstart + cur, pstart + m.end()))
                cur = m.end()
        if cur < len(para):
            units.append((pstart + cur, pstart + len(para)))
    return units


def unit_of(span: tuple[int, int], units: list[tuple[int, int]]) -> int | None:
    for i, (a, b) in enumerate(units):
        if a <= span[0] and span[1] <= b:
            return i
    return None


def load_core():
    path = BUILD / "content_core.py"
    spec = importlib.util.spec_from_file_location("content_core_0221_wread3", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build()


def main() -> int:
    # ── 判据 1：源与边界 ────────────────────────────────────────────────
    raw = DOCS.read_bytes()
    h = hashlib.sha256(raw).hexdigest()
    ck(h == SOURCE_HASH, "docs.json sha256 与 task.sourceHash 不符", h)
    full = json.loads(raw)[0]["text"]
    sl = full[S:E]
    ck(sl.startswith(UNIT_HEAD), "切片不以 unitHead 开头", repr(sl[:40]))
    ck(len(sl) == E - S, "切片长度 != E-S", "%d vs %d" % (len(sl), E - S))
    NOTES.append("判据1 源哈希=%s… 切片 %d codepoints，开头=%r" % (h[:16], len(sl), sl[:24]))

    core = load_core()
    cand = dict(core)

    # ── 判据 2 + 3：tasks 五栏 ─────────────────────────────────────────
    units = sentence_units(sl)
    nulls: list[dict] = []
    fields = ["objective", "obstacle", "action", "result", "cost"]
    for t in cand["tasks"]:
        spans: list[tuple[int, int]] = []
        uset: list[int] = []
        for f in fields:
            cell = t.get(f)
            note_key = f + "Note"
            if cell is None:
                ck(bool(t.get(note_key)),
                   "null 栏没有同名 Note：%s.%s" % (t["id"], f))
                nulls.append({"task": t["id"], "field": f, "note": t.get(note_key)})
                continue
            ck(isinstance(cell, dict) and cell.get("quotes"),
               "栏位缺 quotes：%s.%s" % (t["id"], f))
            qs = [qdict(q, sl, full) for q in cell["quotes"]]
            cell["quotes"] = qs
            for q in qs:
                if q["start"] is None:
                    continue
                span = (q["start"], q["end"])
                for s0, e0 in spans:
                    ck(not (span[0] < e0 and s0 < span[1]),
                       "五栏字符区间重叠：%s.%s" % (t["id"], f),
                       "%r 与已有区间 [%d,%d) 相交" % (q["quote"][:24], s0, e0))
                spans.append(span)
                u = unit_of(span, units)
                if u is not None:
                    ck(u not in uset, "五栏共用句单元：%s.%s" % (t["id"], f),
                       "句单元 #%d %r" % (u, sl[units[u][0] - S:units[u][1] - S][:30]))
                    uset.append(u)
        ck(bool(t.get("actor")), "任务缺 actor：%s" % t["id"])

    cand["nullFieldDisposition"] = nulls
    cand["tasksNote"] = (
        "%d 条任务的五栏各自带 quotes[]；同一任务内五栏的引文**字符区间不重叠、句单元不共用**"
        "（构建脚本判定，违规 0 条）。%d 个栏位里 %d 个 null（清单见 nullFieldDisposition，"
        "逐条带同名 <栏位>Note 写明为什么没有）。没有一条 cost 写『待验证』『待核』这类工作状态，"
        "也没有把『法律规定／禁令』当已执行结果；t3 的 result 明确留 None 就是因为杀令在本区间内"
        "**只有命令、没有执行**。" % (len(cand["tasks"]), len(cand["tasks"]) * 5, len(nulls)))
    NOTES.append("判据2/3 %d 条任务、%d 个引文对象、%d 个 null 栏"
                 % (len(cand["tasks"]),
                    sum(len(c.get("quotes", [])) for t in cand["tasks"] for c in
                        (t[f] for f in fields) if isinstance(c, dict)), len(nulls)))

    # ── 判据 5：散文「」逐字 ───────────────────────────────────────────
    def check_prose(obj, where: str):
        if isinstance(obj, str):
            for frag in re.findall(r"「([^」]*)」", obj):
                if frag:
                    ck(frag in sl, "散文「」片段不是切片逐字子串 @%s" % where, frag[:40])
        elif isinstance(obj, dict):
            for k, v in obj.items():
                check_prose(v, where + "." + str(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_prose(v, "%s[%d]" % (where, i))

    check_prose({k: v for k, v in cand.items() if k != "citationConvention"},
                "candidate")

    # ── 判据 6：worldSettings ──────────────────────────────────────────
    kinds = {"rule", "place", "item"}
    insts = {"declared", "executed", "misunderstood"}
    pstates = {"arrived", "mentioned"}
    istates = {"hold", "transfer", "use", "lose"}
    for w in cand["worldSettings"]:
        ck(w.get("kind") in kinds, "worldSettings.kind 非法：%s" % w.get("id"), str(w.get("kind")))
        ck(bool(w.get("explain")), "worldSettings 缺 explain：%s" % w.get("id"))
        q = qdict(w["quote"], sl, full)
        w["quote"] = q["quote"]
        w["start"], w["end"] = q["start"], q["end"]
        w["sourceHash"] = SOURCE_HASH
        if w.get("kind") == "rule":
            ck(w.get("institution") in insts,
               "rule 缺/非法 institution：%s" % w.get("id"), str(w.get("institution")))
        if w.get("kind") == "place":
            ck(w.get("placeState") in pstates,
               "place 缺/非法 placeState：%s" % w.get("id"), str(w.get("placeState")))
        if w.get("kind") == "item":
            st = w.get("itemStates")
            ck(isinstance(st, list) and st and set(st) <= istates,
               "item 缺/非法 itemStates：%s" % w.get("id"), str(st))
        if w.get("quotes"):
            w["quotes"] = [qdict(x, sl, full) for x in w["quotes"]]
            ck(any(x["quote"] == w["quote"] for x in w["quotes"]),
               "worldSettings.quote 未出现在自己的 quotes[] 里：%s" % w.get("id"))
    for x in cand.get("excludedSettings", []):
        ck(bool(x.get("why")), "excludedSettings 缺 why：%s" % x.get("id"))
        if isinstance(x.get("quote"), str):
            x["quote"] = qdict(x["quote"], sl, full)

    # ── 判据 7：foreshadows ────────────────────────────────────────────
    for f in cand["foreshadows"]:
        ck(f.get("status") in ("resolved", "unresolved"),
           "foreshadows.status 非法：%s" % f.get("id"), str(f.get("status")))
        if f.get("status") == "resolved":
            ck(bool(f.get("payoff")), "resolved 伏笔缺 payoff：%s" % f.get("id"))
        else:
            ck(bool(f.get("payoffNote")), "unresolved 伏笔缺 payoffNote：%s" % f.get("id"))
        ck(len(f.get("quotes") or []) >= 2,
           "伏笔铺设＋回收至少需 2 处引文：%s" % f.get("id"))
        f["quotes"] = [qdict(q, sl, full) for q in (f.get("quotes") or [])]
    for x in cand.get("notForeshadows", []):
        ck(bool(x.get("why")), "notForeshadows 缺 why：%s" % x.get("id"))
        x["quotes"] = [qdict(q, sl, full) for q in (x.get("quotes") or [])]

    # ── 判据 8：causeEdges ─────────────────────────────────────────────
    for c in cand["causeEdges"]:
        for k in ("from", "to", "mechanism"):
            ck(bool(c.get(k)), "causeEdges 缺 %s：%s" % (k, c.get("id")))
        ck(bool(c.get("quotes")), "causeEdges 缺引文：%s" % c.get("id"))
        c["quotes"] = [qdict(q, sl, full) for q in (c.get("quotes") or [])]
    for r in cand.get("rejectedEdges", []):
        r["quotes"] = [qdict(q, sl, full) for q in (r.get("quotes") or [])]

    # ── 判据 9：themeReadings ──────────────────────────────────────────
    for th in cand.get("themeReadings", []):
        for k in ("perspective", "support", "counter"):
            ck(bool(th.get(k)), "themeReadings 缺 %s：%s" % (k, th.get("id")))
        for fld in ("supportQuotes", "counterQuotes"):
            th[fld] = [qdict(q, sl, full) for q in (th.get(fld) or [])]
            ck(bool(th[fld]), "themeReadings.%s 为空：%s" % (fld, th.get("id")))

    # ── 判据 10：states / unknowns / selfCritique ──────────────────────
    for s in cand["states"]:
        for k in ("who", "before", "after", "anchor"):
            ck(bool(s.get(k)), "states 缺 %s：%s" % (k, s.get("id")))
        ck(len(s.get("quotes") or []) >= 2, "states 引文 <2：%s" % s.get("id"))
        s["quotes"] = [qdict(q, sl, full) for q in (s.get("quotes") or [])]
    for u in cand["unknowns"]:
        for k in ("what", "why"):
            ck(bool(u.get(k)), "unknowns 缺 %s：%s" % (k, u.get("id")))
    for sc in cand["selfCritique"]:
        for k in ("where", "risk", "why_still"):
            ck(bool(sc.get(k)), "selfCritique 缺 %s：%s" % (k, sc.get("id")))

    # states/causeEdges 等分区的引文统一补 sourceHash（qdict 已带）

    # ── coverage ───────────────────────────────────────────────────────
    paras = []
    off = S
    for para in sl.split("\n"):
        if para.strip():
            paras.append((off, off + len(para)))
        off += len(para) + 1
    # 口径必须与校验器一致：**逐个对象**计数（同一个 quote 在 worldSettings 顶层
    # 与 quotes[0] 各存一份 ⇒ 算两个对象），另给去重区间数。第一版这里只存 set，
    # 而校验器按对象计数 ⇒ 6f 报 89 vs 179，是**我的字段定义含糊**，不是数字错。
    quoted_objs: list[tuple[int, int]] = []

    def collect(o):
        if isinstance(o, dict):
            if isinstance(o.get("start"), int) and isinstance(o.get("end"), int) \
                    and isinstance(o.get("quote"), str):
                quoted_objs.append((o["start"], o["end"]))
            for v in o.values():
                collect(v)
        elif isinstance(o, list):
            for v in o:
                collect(v)

    collect(cand)
    touched = set()
    for ps, pe in quoted_objs:
        for i, (a, b) in enumerate(paras):
            if ps < b and a < pe:
                touched.add(i)
    zero = [{"start": paras[i][0], "end": paras[i][1],
             "text": sl[paras[i][0] - S:paras[i][1] - S]} for i in range(len(paras))
            if i not in touched]
    cand["coverage"] = {
        "nonEmptyParagraphs": len(paras),
        "paragraphsTouchedByQuotes": len(touched),
        "zeroCoverageParagraphs": len(zero),
        "zeroCoverageList": zero,
        "quoteObjects": len(quoted_objs),          # 带 start/end 的引文字典**对象个数**（含同一句的多份副本）
        "uniqueQuoteSpans": len(set(quoted_objs)),  # 其中互不相同的 [start,end) 区间数
        "quoteObjectsNote": "quoteObjects 按**对象**计数：worldSettings 的每条既在顶层存 quote/start/end、"
                            "又在 quotes[] 里存一份，因此同一句会被计两次；uniqueQuoteSpans 是去重后的区间数。"
                            "两个口径都给出，避免同名不同义。跨分区复用同一句不违规——prompt 禁止的是"
                            "**同一任务五栏**共用一句（判据 3a/3b）。",
        "method": "非空段＝按换行切分后 strip() 非空的段；某段被 quote 覆盖＝该段区间与任一 quote 的 [start,end) 相交。",
    }
    NOTES.append("coverage %d/%d 段被引文覆盖，零覆盖 %d 段；引文对象 %d 个（去重后 %d 个区间）"
                 % (len(touched), len(paras), len(zero), len(quoted_objs), len(set(quoted_objs))))

    # ── slice hash 与写盘 ──────────────────────────────────────────────
    cand["sliceCodepoints"] = len(sl)
    cand["sliceSha256"] = hashlib.sha256(sl.encode("utf-8")).hexdigest()

    if FAILS:
        print("构建失败，未写盘（%d 条）:" % len(FAILS), file=sys.stderr)
        for f in FAILS[:60]:
            print("  ✗ %s" % f, file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=2), encoding="utf-8")
    for n in NOTES:
        print("✓ %s" % n)
    print("✓ 已写 %s" % OUT.relative_to(ROOT))
    print("✓ sha256 %s" % hashlib.sha256(OUT.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
