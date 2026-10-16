# -*- coding: utf-8 -*-
"""独立校验 loop/state/out/read_dafeng_L3_0255.candidate.json。

用法：
    python3 -B -s loop/state/out/read_dafeng_L3_0255.w-read-2.build/verify_candidate.py

为什么要这个脚本（而不是只信 build_candidate.py 的自检）：
    build_candidate.py 的自检是**构建期**的，它验证的是"我写出去的字段等于我打算写的值"。
    它无法发现"我打算写的值本身与原文不符"，也无法发现"某个分区被整个漏掉"。
    本脚本只读**候选 JSON + 原文**，不 import content_0255.py，因此与构建期声明相互独立：
    它把每条引文拿回 docs[0].text 现场 find，把每个 para 号拿回现场重算段落表，
    并对提示词的每一条硬性要求各判一次。

判据（任一 fail ⇒ 退出码 1）：
  V01 源哈希 = task.sourceHash，且切片自检 text[S:E] 以单元标题开头
  V02 每条引文 text[start:end]==quote 逐字成立、落在 [S,E) 内、sourceHash 逐条一致
  V03 每个 quote 对象自带的 para 号与现场重算的段落表一致
  V04 tasks[]：五元组键齐全；非空栏必须有引文；null 栏必须有同名的 <栏>Note 且非空
  V05 tasks[]：同一任务内五栏引文区间两两不相交（提示词点名的 714/1664 缺陷）
  V06 causeEdges[]：每条有 from/to/mechanism/quotes，且 mechanism 非空
  V07 states[]：每条有 before/after/anchor 三段，且各有引文
  V08 foreshadows[]：有铺设+回收，或显式 status=unresolved（二者必居其一）
  V09 worldSettings[]：kind 专属字段（place→placeState / item→itemStates / rule→institution）
  V10 themeReadings[]：每条 perspective/support/counter 三件齐全（只列支持 = 论证不是解释）
  V11 不得声称 semanticReview 完成
  V12 提示词要求的 6 个顶层分区全部存在
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND = ROOT / "loop/state/out/read_dafeng_L3_0255.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L3_0255.json"
GRAPH = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"

FIELDS = ("objective", "obstacle", "action", "result", "cost")
SECTIONS = ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings")

results = []


def check(cid, ok, detail=""):
    results.append((cid, bool(ok), detail))
    return bool(ok)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_para_table(text, S, E):
    """与构建期**各写一遍**的段落表：[para(1起) -> (start, end, body)]。

    刻意不从 build_candidate.py import —— 那样两者会一起错。
    """
    table = {}
    off = S
    n = 0
    for raw in text[S:E].split("\n\n"):
        if raw.strip() == "":
            off += len(raw) + 2
            continue
        n += 1
        lead = len(raw) - len(raw.lstrip())
        st = off + lead
        body = raw.strip()
        table[n] = (st, st + len(body), body)
        off += len(raw) + 2
    return table, n


def walk_quotes(obj, path="root"):
    """产出 (path, quote_obj)；只认"同时有 quote/start/end"的 dict。"""
    if isinstance(obj, dict):
        if "quote" in obj and "start" in obj and "end" in obj:
            yield path, obj
            return
        for k, v in obj.items():
            yield from walk_quotes(v, "%s/%s" % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_quotes(v, "%s/%d" % (path, i))


def overlap(a, b):
    for s1, e1 in a:
        for s2, e2 in b:
            if s1 < e2 and s2 < e1:
                return (s1, e1, s2, e2)
    return None


def main():
    task = json.loads(TASK.read_text(encoding="utf-8"))
    S, E = task["sourceRange"]
    head = task["unitHead"]
    want_hash = task["sourceHash"]

    data = json.loads(DOCS.read_text(encoding="utf-8"))
    docs = data if isinstance(data, list) else data["docs"]
    text = docs[0]["text"]

    cand = json.loads(CAND.read_text(encoding="utf-8"))

    # ── V01 源哈希与切片边界 ─────────────────────────────────────────────
    actual_hash = sha256_file(DOCS)
    check("V01a 源哈希=task.sourceHash", actual_hash == want_hash,
          "实测 %s / 声明 %s" % (actual_hash[:16], want_hash[:16]))
    slice_text = text[S:E]
    check("V01b 切片以单元标题开头", slice_text.startswith(head),
          "切片头 %r / 标题 %r" % (slice_text[:24], head))
    check("V01c 切片长度=任务区间长度", len(slice_text) == E - S,
          "len=%d, E-S=%d" % (len(slice_text), E - S))
    declared_slice = (cand.get("source") or {}).get("sliceSha256")
    real_slice = hashlib.sha256(slice_text.encode("utf-8")).hexdigest()
    check("V01d 切片 sha256 与候选声明一致",
          declared_slice is None or declared_slice == real_slice,
          "实测 %s / 声明 %s" % (real_slice[:16], str(declared_slice)[:16]))
    check("V01e 候选 sourceHash 字段=task.sourceHash",
          (cand.get("source") or {}).get("sourceHash") == want_hash, "")

    paras, nparas = build_para_table(text, S, E)
    declared_np = (cand.get("source") or {}).get("nonEmptyParagraphs")
    check("V01f 非空段数与候选声明一致", declared_np in (None, nparas),
          "重算 %d / 声明 %s" % (nparas, declared_np))

    # ── V02/V03 逐条引文 ─────────────────────────────────────────────────
    refs = list(walk_quotes(cand))
    bad_text, bad_range, bad_hash, bad_para = [], [], [], []
    for path, q in refs:
        s, e, quote = q["start"], q["end"], q["quote"]
        if not (isinstance(s, int) and isinstance(e, int) and s < e):
            bad_text.append((path, "偏移非法", s, e))
            continue
        if text[s:e] != quote:
            bad_text.append((path, quote[:28], s, e, repr(text[s:e][:28])))
        if s < S or e > E:
            bad_range.append((path, quote[:28], s, e))
        if q.get("sourceHash") != want_hash:
            bad_hash.append((path, quote[:28], str(q.get("sourceHash"))[:16]))
        pn = q.get("para")
        if pn is not None:
            hit = paras.get(pn)
            if hit is None or not (hit[0] <= s < hit[1]):
                bad_para.append((path, "para=%s" % pn, s, hit[:2] if hit else None))

    check("V02a 引文逐字命中 text[start:end]==quote", not bad_text,
          "%d/%d 条不符；样例 %s" % (len(bad_text), len(refs), bad_text[:3]))
    check("V02b 引文全部落在任务区间内", not bad_range,
          "%d 条越界；样例 %s" % (len(bad_range), bad_range[:3]))
    check("V02c 每条引文 sourceHash 一致", not bad_hash,
          "%d 条不符；样例 %s" % (len(bad_hash), bad_hash[:3]))
    check("V03 引文 para 号与现场段落表一致", not bad_para,
          "%d 条不符；样例 %s" % (len(bad_para), bad_para[:3]))

    # 候选自报的引文计数是否属实
    msc = cand.get("machineSelfCheck") or {}
    uniq = len({(q["start"], q["end"]) for _, q in refs})
    check("V02d 引文对象数与自报一致", msc.get("quoteObjectsResolved") in (None, len(refs)),
          "实测 %d / 自报 %s" % (len(refs), msc.get("quoteObjectsResolved")))
    check("V02e 唯一区间数与自报一致", msc.get("uniqueQuoteIntervals") in (None, uniq),
          "实测 %d / 自报 %s" % (uniq, msc.get("uniqueQuoteIntervals")))

    # ── V04/V05 tasks ────────────────────────────────────────────────────
    tasks = cand.get("tasks")
    check("V04a tasks 是非空数组", isinstance(tasks, list) and bool(tasks),
          "type=%s" % type(tasks).__name__)
    miss_field, null_no_note, empty_nonnull, ov_problems = [], [], [], []
    null_count = 0
    for t in tasks or []:
        tid = t.get("id", "?")
        ivs = {}
        for f in FIELDS:
            if f not in t:
                miss_field.append((tid, f, "键缺失"))
                continue
            val = t[f]
            qs = t.get(f + "Quotes") or []
            ivs[f] = [(q["start"], q["end"]) for q in qs]
            if val is None:
                null_count += 1
                note = t.get(f + "Note")
                if not (isinstance(note, str) and note.strip()):
                    null_no_note.append((tid, f))
            else:
                if not qs:
                    empty_nonnull.append((tid, f))
        for i in range(len(FIELDS)):
            for j in range(i + 1, len(FIELDS)):
                a, b = FIELDS[i], FIELDS[j]
                if a in ivs and b in ivs:
                    ov = overlap(ivs[a], ivs[b])
                    if ov:
                        ov_problems.append((tid, a, b, ov))
    check("V04b 五元组键齐全", not miss_field, "缺 %s" % miss_field[:5])
    check("V04c 非空栏都有引文", not empty_nonnull, "空引文栏 %s" % empty_nonnull[:5])
    check("V04d null 栏都有非空 <栏>Note", not null_no_note,
          "%d 个未标注的 null：%s" % (len(null_no_note), null_no_note[:5]))
    check("V05 同一任务内五栏引文区间两两不相交", not ov_problems,
          "%d 处重叠；样例 %s" % (len(ov_problems), ov_problems[:3]))
    check("V04e null 栏数与自报一致", msc.get("nullFields") in (None, null_count),
          "实测 %d / 自报 %s" % (null_count, msc.get("nullFields")))
    check("V04f 自报 nullWithoutNote 与实测一致",
          msc.get("nullWithoutNote") in (None, len(null_no_note)),
          "实测 %d / 自报 %s" % (len(null_no_note), msc.get("nullWithoutNote")))
    ov_self = msc.get("taskFieldIntervalOverlap")
    check("V05b 自报五栏重叠数与实测一致", ov_self in (None, len(ov_problems)),
          "实测 %d / 自报 %s" % (len(ov_problems), ov_self))

    # ── V06 causeEdges ───────────────────────────────────────────────────
    bad_edge = []
    for e in cand.get("causeEdges") or []:
        eid = e.get("id", "?")
        for k in ("from", "to", "mechanism"):
            if not (isinstance(e.get(k), str) and e[k].strip()):
                bad_edge.append((eid, "缺/空 " + k))
        if not (e.get("quotes") or []):
            bad_edge.append((eid, "无引文"))
    check("V06 causeEdges 有方向+触发机制+引文", not bad_edge, "%s" % bad_edge[:5])
    check("V06b causeEdges 非空", bool(cand.get("causeEdges")),
          "len=%s" % len(cand.get("causeEdges") or []))

    # ── V07 states ───────────────────────────────────────────────────────
    bad_state = []
    for s in cand.get("states") or []:
        sid = s.get("id", "?")
        for part in ("before", "after", "anchor"):
            if not (isinstance(s.get(part), str) and s[part].strip()):
                bad_state.append((sid, "缺/空 " + part))
            if not (s.get(part + "Quotes") or []):
                bad_state.append((sid, part + " 无引文"))
    check("V07 states 有前值/后值/事件锚点且各有引文", not bad_state, "%s" % bad_state[:6])
    check("V07b states 非空", bool(cand.get("states")),
          "len=%s" % len(cand.get("states") or []))

    # ── V08 foreshadows ──────────────────────────────────────────────────
    bad_fs = []
    for f in cand.get("foreshadows") or []:
        fid = f.get("id", "?")
        setup, payoff, status = f.get("setup"), f.get("payoff"), f.get("status")
        if not (isinstance(setup, dict) and setup.get("quote")):
            bad_fs.append((fid, "无有效铺设引文"))
        if payoff is not None and not (isinstance(payoff, dict) and payoff.get("quote")):
            bad_fs.append((fid, "payoff 存在但无有效引文"))
        # 「未回收的要显式标 unresolved」：回收端缺失 ⇒ status 必须明说未回收，
        # 并写明未回收的到底是什么（只写 null 不算标注）。
        #
        # 注意此处**不**判「有 payoff 就不能是 unresolved」：回收端可以只是把问题
        # 推进到死路（本候选 F05 即此形态），status 仍应如实记 unresolved。
        # 该反向不变式在本仓库实测有 288 条例外（1672 条有 payoff 的伏笔里），
        # 所以它不是契约，只是我第一版写错的过度约束。
        if payoff is None and "unresolved" not in str(status or ""):
            bad_fs.append((fid, "payoff=null 但 status=%r（应显式标 unresolved）" % status))
        if "unresolved" in str(status or ""):
            if not (isinstance(f.get("unresolvedWhat"), str) and f["unresolvedWhat"].strip()):
                bad_fs.append((fid, "标了 unresolved 但未写 unresolvedWhat"))
    check("V08 foreshadows 有铺设，回收缺失时显式标 unresolved", not bad_fs, "%s" % bad_fs[:6])
    check("V08b foreshadows 非空", bool(cand.get("foreshadows")),
          "len=%s" % len(cand.get("foreshadows") or []))

    # ── V09 worldSettings 三态字段 ───────────────────────────────────────
    bad_ws = []
    kinds = {}
    for w in cand.get("worldSettings") or []:
        wid, kind = w.get("id", "?"), w.get("kind")
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind not in ("rule", "place", "item"):
            bad_ws.append((wid, "kind 非法 %r" % kind))
            continue
        if not (isinstance(w.get("name"), str) and w["name"].strip()):
            bad_ws.append((wid, "缺 name"))
        if not (isinstance(w.get("explain"), str) and w["explain"].strip()):
            bad_ws.append((wid, "缺 explain"))
        if not w.get("quote"):
            bad_ws.append((wid, "缺 quote"))
        if kind == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                bad_ws.append((wid, "placeState=%r" % w.get("placeState")))
        elif kind == "item":
            st = w.get("itemStates")
            if not (isinstance(st, list) and st and all(x in ("hold", "transfer", "use", "lose") for x in st)):
                bad_ws.append((wid, "itemStates=%r" % st))
        elif kind == "rule":
            if w.get("institution") not in ("declared", "executed", "misunderstood"):
                bad_ws.append((wid, "institution=%r" % w.get("institution")))
    check("V09 worldSettings 三态字段齐全且取值合法", not bad_ws, "%s" % bad_ws[:6])
    check("V09b worldSettings 非空（本区间确有设定）", bool(cand.get("worldSettings")),
          "kinds=%s" % kinds)

    # ── V10 themeReadings 三件套 ─────────────────────────────────────────
    bad_th = []
    ths = cand.get("themeReadings") or []
    for th in ths:
        tid = th.get("id", "?")
        if not (isinstance(th.get("perspective"), str) and th["perspective"].strip()):
            bad_th.append((tid, "缺 perspective"))
        sup = th.get("support") or []
        if not sup:
            bad_th.append((tid, "无 support"))
        else:
            for x in sup:
                if not (isinstance(x, dict) and x.get("quote")):
                    bad_th.append((tid, "support 条目缺引文"))
        if not (th.get("counter") or []):
            bad_th.append((tid, "无 counter（只列支持=论证，不是解释）"))
        else:
            for x in th["counter"]:
                if not (isinstance(x, dict) and x.get("quote")):
                    bad_th.append((tid, "counter 条目缺引文"))
    check("V10 themeReadings 三件套（perspective/support/counter）", not bad_th, "%s" % bad_th[:6])
    check("V10b themeReadings ≤2 条", len(ths) <= 2, "len=%d" % len(ths))

    # ── V11 不得声称语义评审完成 ─────────────────────────────────────────
    sr = cand.get("semanticReview")
    check("V11a semanticReview 未声称完成", sr not in ("done", "complete", "passed", "performed"),
          "semanticReview=%r" % sr)
    blob = json.dumps(cand, ensure_ascii=False)
    claims = [m.group(0) for m in re.finditer(r"语义(已)?(核验|评审)(完成|通过)", blob)]
    check("V11b 正文无「语义核验完成」类声称", not claims, "%s" % claims[:3])

    # ── V12 顶层分区齐全 ─────────────────────────────────────────────────
    missing = [k for k in SECTIONS if k not in cand]
    check("V12 提示词要求的 6 个顶层分区全部存在", not missing, "缺 %s" % missing)

    # ── V14 专名核对：agent 自己写的散文里不得出现原文没有的人名 ─────────
    # 这一条是本脚本第一版**漏掉**的缺陷类：候选在 U11 里写了「沈七安」，
    # 而这个名字在全篇 476 万字的原文里出现 **0 次**（正确的是「许七安」，区间内 44 次）。
    # 引文全部逐字命中并不能发现它 —— 因为错的是**引文之外**的叙述文字。
    # 判据：剥掉所有引文对象后，在剩余散文里找「姓+七安」形态的称谓，逐个回原文核对。
    def strip_quotes(obj):
        if isinstance(obj, dict):
            if "quote" in obj and "start" in obj:
                return ""
            return " ".join(strip_quotes(v) for v in obj.values())
        if isinstance(obj, list):
            return " ".join(strip_quotes(v) for v in obj)
        return obj if isinstance(obj, str) else ""

    prose = strip_quotes(cand)
    # 用**姓氏表**而不是 [\u4e00-\u9fa5]{1,2}：后者会把「京城里许七安」的
    # 「里许」也当成姓，报出假阳性（第一版实测踩到）。
    SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    invented = []
    for m in re.finditer(r"[%s]七安" % SURNAMES, prose):
        name = m.group(0)
        if name not in text:
            invented.append((name, text.count(name)))
    check("V14 散文里无原文不存在的人名（如「沈七安」）", not invented,
          "凭空人名 %s（原文出现次数 0）" % sorted({n for n, _ in invented}))

    # ── V13 图缓存只作对照，不作原文证据 ──────────────────────────────────
    check("V13 图缓存存在（仅对照用，未作证据）", GRAPH.exists(), str(GRAPH))

    # ── 汇总 ─────────────────────────────────────────────────────────────
    print("候选：%s" % CAND.relative_to(ROOT))
    print("引文对象 %d 个（唯一区间 %d）；非空段 %d；五元组 %d 条；null 栏 %d"
          % (len(refs), uniq, nparas, len(tasks or []), null_count))
    print("-" * 72)
    failed = 0
    for cid, ok, detail in results:
        print("%s %s%s" % ("PASS" if ok else "FAIL", cid, ("  — " + detail) if (detail and not ok) else ""))
        if not ok:
            failed += 1
    print("-" * 72)
    print("共 %d 项，FAIL %d 项" % (len(results), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
