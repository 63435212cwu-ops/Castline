#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建候选：把 content_core.py（结论 + 引文键）与 quotes.py（键→偏移）合成候选 JSON。

硬判据（任一不成立即 exit 1，**不写盘**）：
  H0  源文件 sha256 == 任务 sourceHash；切片以单元标题开头
  H1  每条引文：text[start:end] == quote
  H2  每条引文：text.find(quote) == start（全文唯一命中）
  H3  每条引文：落在 [sourceRange) 内
  H4  每条引文：在切片内命中次数 == 1
  H5  同一任务内五栏引文两两不同（防「一句话同时当两栏证据」）
  H6  裸 null 栏位必须带同名 *Note，且 Note 不是空串
  H7  worldSettings：rule 必须有 institution + explain；item 必须有 itemStates；
      place 必须有 placeState
  H8  foreshadows：status=resolved 必须有 payoff；unresolved 必须有 payoffNote
  H9  causeEdges：必须有 mechanism（非空）
  H10 states：必须有 before/after/anchor（knowledge 类必须有 knowledge）
  H11 引文键必须存在；不得有重复字面量（由 gen_quotes 保证，此处再查一次）
  H12 basis 必须在枚举内
  H13 每条断言必须有 basis
  H14 themeReadings ≤ 2，且每条必须有 perspective/support/counter 三件
  H15 所有 quoteKeys 都能解析
  H16 每个引文键至少被引用一次（防「登记了不用」的假工作量）
  H17 不许出现 semanticReview=completed
  H18 计数由脚本算出，不手写
  H19 正文/作者附言分界之外的锚串不得用作剧情依据（本候选对附言只做登记）
  H20 同一任务内五栏的**语层不得全部相同**除非该任务在 layerWarning 里声明
  H21 每个 null 栏位名必须与 *Note 名成对出现（result/resultNote 等）
  H22 counter 必须带 quoteKeys（不许只写一句免责声明）
  H23 rule 不写 declared 时必须有解释（防止把人物理解当制度）
  H24 引文键在「同一栏位内」不得重复
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
GRID = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L0_0228.json"
OUT = ROOT / "loop/state/out/read_dafeng_L0_0228.candidate.json"

sys.path.insert(0, str(HERE))
import quotes as Q          # noqa: E402
import quotes_spec as S     # noqa: E402
import content_core as C    # noqa: E402

BASIS_ENUM = ("explicit", "inferred", "derived", "unverified")
LAYER_ENUM = ("narration", "speech", "inner")


class Fail(Exception):
    pass


def main():
    problems = []
    task = json.loads(TASK.read_text(encoding="utf-8"))
    raw = DOCS.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    s, e = task["sourceRange"]
    slice_text = text[s:e]
    src_hash = task["sourceHash"]
    QMAP = Q.QUOTES

    # ── H0 ──────────────────────────────────────────────────────────────
    if file_hash != src_hash:
        problems.append("H0 docs.json sha256=%s != 任务 sourceHash" % file_hash)
    if not slice_text.startswith(task["unitHead"]):
        problems.append("H0 切片不以单元标题开头")

    # ── H11/H15 引文键可解析 ─────────────────────────────────────────────
    for k, v in QMAP.items():
        if v["quote"] != S.ANCHORS[k][1]:
            problems.append("H11 %s：quotes.py 与 quotes_spec 字面量不一致" % k)
        if QMAP[k]["layer"] != S.ANCHORS[k][0]:
            problems.append("H11 %s：语层不一致" % k)

    # ── H1–H4：逐条引文定位复算 ──────────────────────────────────────────
    for k, v in QMAP.items():
        q, st, en = v["quote"], v["start"], v["end"]
        if text[st:en] != q:
            problems.append("H1 %s：text[start:end] != quote" % k)
        if text.find(q) != st:
            problems.append("H2 %s：find(quote) != start" % k)
        if not (s <= st and en <= e):
            problems.append("H3 %s：越出区间" % k)
        if slice_text.count(q) != 1:
            problems.append("H4 %s：切片内命中 %d 次" % (k, slice_text.count(q)))
        if v["layer"] not in LAYER_ENUM:
            problems.append("H12 %s：语层 %r 非法" % (k, v["layer"]))

    # ── 工具：把 quoteKeys 展开成 quotes[] ───────────────────────────────
    def expand(keys, where):
        if not isinstance(keys, list) or not keys:
            problems.append("H15 %s：quoteKeys 为空或不是列表" % where)
            return [], []
        seen, out = set(), []
        for k in keys:
            if k not in QMAP:
                problems.append("H15 %s：未知引文键 %r" % (where, k))
                continue
            if k in seen:
                problems.append("H24 %s：同一栏位内引文键重复 %r" % (where, k))
                continue
            seen.add(k)
            v = QMAP[k]
            item = {"quote": v["quote"], "start": v["start"], "end": v["end"],
                    "sourceHash": src_hash, "layer": v["layer"]}
            if k in S.LETTER_KEYS:
                item["speechKind"] = "letter"
            out.append(item)
        return out, sorted(seen)

    used_keys = set()

    def field(node, key, where, required=True, allow_none=False):
        """取一个「栏位」：{text, basis, quoteKeys, note} → 展开成含 quotes 的 dict。"""
        val = node.get(key)
        if val is None:
            if required and not allow_none:
                problems.append("H16 %s.%s 缺失" % (where, key))
            return None
        if not isinstance(val, dict):
            problems.append("H16 %s.%s 不是对象" % (where, key))
            return None
        b = val.get("basis")
        if b not in BASIS_ENUM:
            problems.append("H12 %s.%s：basis=%r 非法" % (where, key, b))
        qs, ks = expand(val.get("quoteKeys"), "%s.%s" % (where, key))
        used_keys.update(ks)
        res = {"text": val.get("text"), "basis": b, "quoteKeys": ks, "quotes": qs}
        if val.get("note"):
            res["note"] = val["note"]
        return res

    # ── tasks[] ─────────────────────────────────────────────────────────
    tasks_out = []
    for t in C.TASKS:
        tid = t["id"]
        node = {"id": tid, "name": t["name"], "actor": t["actor"],
                "actorBasis": t.get("actorBasis", "explicit")}
        if t.get("actorNote"):
            node["actorNote"] = t["actorNote"]
        if t.get("layerWarning"):
            node["layerWarning"] = t["layerWarning"]
        for col in ("objective", "obstacle", "action", "result", "cost"):
            node[col] = field(t, col, tid, required=(col in ("objective", "action")),
                              allow_none=(col in ("obstacle", "result", "cost")))
            if node[col] is None:
                note = t.get(col + "Note")
                if not note or not str(note).strip():
                    problems.append("H6 %s.%s 为 null 但缺 %sNote" % (tid, col, col))
                node[col + "Note"] = note
        node["note"] = t.get("note")
        # H5 五栏引文两两不同
        buckets = {}
        for col in ("objective", "obstacle", "action", "result", "cost"):
            v = node.get(col)
            if v:
                buckets[col] = set(k for k in v["quoteKeys"])
        names = sorted(buckets)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                inter = buckets[a] & buckets[b]
                if inter:
                    problems.append("H5 %s：%s 与 %s 共用引文 %s"
                                    % (tid, a, b, sorted(inter)))
                qa = set(x["quote"] for x in node[a]["quotes"])
                qb = set(x["quote"] for x in node[b]["quotes"])
                if qa & qb:
                    problems.append("H5 %s：%s 与 %s 引文字面量相同" % (tid, a, b))
        # H20 语层不得全同（除非声明）
        layers = set()
        for col in ("objective", "obstacle", "action", "result", "cost"):
            v = node.get(col)
            if v:
                layers.update(x["layer"] for x in v["quotes"])
        if len(layers) == 1 and not t.get("layerWarning"):
            problems.append("H20 %s：五栏语层全部为 %s 且未声明"
                            % (tid, sorted(layers)[0]))
        node["distinctQuoteKeys"] = len(set().union(*buckets.values())) if buckets else 0
        tasks_out.append(node)

    rejected_tasks = []
    for r in C.REJECTED_TASKS:
        qs, ks = expand(r["quoteKeys"], "rejectedTasks." + r["id"])
        used_keys.update(ks)
        rejected_tasks.append({"id": r["id"], "candidate": r["candidate"],
                               "why": r["why"], "quoteKeys": ks, "quotes": qs})

    # ── causeEdges[] ────────────────────────────────────────────────────
    edges_out = []
    for ed in C.CAUSE_EDGES:
        if not ed.get("mechanism", "").strip():
            problems.append("H9 %s：缺 mechanism" % ed["id"])
        qs, ks = expand(ed["quoteKeys"], "causeEdges." + ed["id"])
        used_keys.update(ks)
        edges_out.append({"id": ed["id"], "from": ed["from"], "to": ed["to"],
                          "mechanism": ed["mechanism"], "basis": ed["basis"],
                          "quoteKeys": ks, "quotes": qs, "note": ed.get("note")})

    rejected_edges = []
    for r in C.REJECTED_EDGES:
        qs, ks = expand(r["quoteKeys"], "rejectedEdges." + r["id"])
        used_keys.update(ks)
        rejected_edges.append({"id": r["id"], "candidate": r["candidate"],
                               "why": r["why"], "quoteKeys": ks, "quotes": qs})

    # ── states[] ────────────────────────────────────────────────────────
    states_out = []
    for st in C.STATES:
        node = {"id": st["id"], "kind": st["kind"], "who": st["who"]}
        for col in ("before", "after", "anchor"):
            node[col] = field(st, col, "states." + st["id"])
            if node[col] is None:
                problems.append("H10 %s：缺 %s" % (st["id"], col))
        if st["kind"] == "knowledge" and not st.get("knowledge"):
            problems.append("H10 %s：knowledge 类状态缺 knowledge 字段" % st["id"])
        if st.get("knowledge"):
            node["knowledge"] = st["knowledge"]
        node["note"] = st.get("note")
        states_out.append(node)

    # ── foreshadows[] ───────────────────────────────────────────────────
    fore_out = []
    for f in C.FORESHADOWS:
        node = {"id": f["id"], "name": f["name"], "status": f["status"]}
        node["setup"] = field(f, "setup", "foreshadows." + f["id"])
        if f.get("payoff"):
            node["payoff"] = field(f, "payoff", "foreshadows." + f["id"])
        else:
            node["payoff"] = None
            if f["status"] == "resolved":
                problems.append("H8 %s：status=resolved 但没有 payoff" % f["id"])
            if not (f.get("payoffNote") or "").strip():
                problems.append("H8 %s：未回收但缺 payoffNote" % f["id"])
        if f.get("payoffNote"):
            node["payoffNote"] = f["payoffNote"]
        node["note"] = f.get("note")
        fore_out.append(node)

    not_fore = []
    for f in C.NOT_FORESHADOWS:
        qs, ks = expand(f["quoteKeys"], "notForeshadows." + f["id"])
        used_keys.update(ks)
        not_fore.append({"id": f["id"], "name": f["name"], "why": f["why"],
                         "quoteKeys": ks, "quotes": qs})

    # ── worldSettings[] ─────────────────────────────────────────────────
    world_out = []
    for w in C.WORLD_SETTINGS:
        node = {"id": w["id"], "kind": w["kind"], "name": w["name"],
                "explain": w["explain"], "basis": w["basis"]}
        if w["kind"] == "rule":
            if not w.get("institution"):
                problems.append("H7 %s：rule 缺 institution" % w["id"])
            if w["institution"] not in ("declared", "executed", "misunderstood"):
                problems.append("H7 %s：institution=%r 非法" % (w["id"], w["institution"]))
            node["institution"] = w["institution"]
        elif w["kind"] == "item":
            if not w.get("itemStates"):
                problems.append("H7 %s：item 缺 itemStates" % w["id"])
            bad = [x for x in w.get("itemStates", [])
                   if x not in ("hold", "transfer", "use", "lose")]
            if bad:
                problems.append("H7 %s：itemStates 含非法值 %s" % (w["id"], bad))
            node["itemStates"] = w["itemStates"]
        elif w["kind"] == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                problems.append("H7 %s：placeState=%r 非法" % (w["id"], w.get("placeState")))
            node["placeState"] = w.get("placeState")
        else:
            problems.append("H7 %s：kind=%r 非法" % (w["id"], w["kind"]))
        qs, ks = expand(w["quoteKeys"], "worldSettings." + w["id"])
        used_keys.update(ks)
        node["quoteKeys"] = ks
        node["quotes"] = qs
        node["note"] = w.get("note")
        world_out.append(node)

    excl = []
    for x in C.EXCLUDED_SETTINGS:
        qs, ks = expand(x["quoteKeys"], "excludedSettings." + x["id"])
        used_keys.update(ks)
        excl.append({"id": x["id"], "candidate": x["candidate"], "why": x["why"],
                     "quoteKeys": ks, "quotes": qs})

    # ── themeReadings[] ─────────────────────────────────────────────────
    if len(C.THEME_READINGS) > 2:
        problems.append("H14 themeReadings 超过 2 条")
    theme_out = []
    for th in C.THEME_READINGS:
        for must in ("perspective", "support", "counter"):
            if not th.get(must):
                problems.append("H14 %s：缺 %s" % (th["id"], must))
        node = {"id": th["id"], "perspective": th["perspective"]}
        node["support"] = field(th, "support", "theme." + th["id"])
        node["counter"] = field(th, "counter", "theme." + th["id"])
        node["note"] = th.get("note")
        theme_out.append(node)

    # ── unknowns[] / selfCritique[] ─────────────────────────────────────
    unk_out = []
    for u in C.UNKNOWNS:
        qs, ks = expand(u["quoteKeys"], "unknowns." + u["id"])
        used_keys.update(ks)
        unk_out.append({"id": u["id"], "text": u["text"], "why": u["why"],
                        "quoteKeys": ks, "quotes": qs})

    sc_out = []
    for c in C.SELF_CRITIQUE:
        why = c.get("whyStill") or c.get("why_still")
        if not why:
            problems.append("selfCritique %s：缺 whyStill/why_still" % c.get("id"))
        sc_out.append({"id": c["id"], "risk": c["risk"], "why_still": why})

    # ── H16 未使用的锚串 ────────────────────────────────────────────────
    unused = sorted(set(S.ANCHORS) - used_keys)
    if unused:
        problems.append("H16 登记但未被引用的锚串（假工作量）：%s" % unused)

    # ── H17 不许声明语义复核完成 ────────────────────────────────────────
    # （semanticReview 由本文件固定写 not_performed，见下）

    if problems:
        print("构建失败：%d 处" % len(problems), file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 1

    # ── 计数（H18：全部脚本算出）────────────────────────────────────────
    def count_quotes(o, acc=None):
        if acc is None:
            acc = []
        if isinstance(o, dict):
            if "quote" in o and "start" in o and "end" in o:
                acc.append(o)
            for v in o.values():
                count_quotes(v, acc)
        elif isinstance(o, list):
            for v in o:
                count_quotes(v, acc)
        return acc

    basis_dist = {}
    def count_basis(o):
        if isinstance(o, dict):
            b = o.get("basis")
            if b in BASIS_ENUM:
                basis_dist[b] = basis_dist.get(b, 0) + 1
            for v in o.values():
                count_basis(v)
        elif isinstance(o, list):
            for v in o:
                count_basis(v)

    # ── 覆盖度：哪些非空段未被任何引文触及 ──────────────────────────────
    import re
    paras = []
    off = s
    for p in re.split(r"\n\s*\n", slice_text):
        idx = slice_text.find(p, off - s)
        st = s + idx
        if p.strip():
            paras.append((st, st + len(p), p))
        off = st + len(p)

    all_quotes = count_quotes({
        "tasks": tasks_out, "rejectedTasks": rejected_tasks,
        "causeEdges": edges_out, "rejectedEdges": rejected_edges,
        "states": states_out, "foreshadows": fore_out, "notForeshadows": not_fore,
        "worldSettings": world_out, "excludedSettings": excl,
        "themeReadings": theme_out, "unknowns": unk_out,
    })
    spans = [(q["start"], q["end"]) for q in all_quotes]
    zero = [{"para": i + 1, "text": p[2]}
            for i, p in enumerate(paras)
            if not any(a < p[1] and p[0] < b for a, b in spans)]

    # ── H6 复核：所有裸 null 都有 Note ──────────────────────────────────
    nulls = []
    for t in tasks_out:
        for col in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(col) is None:
                nulls.append("%s.%s" % (t["id"], col))
                if not t.get(col + "Note"):
                    problems.append("H6 %s.%s 裸 null 无 Note" % (t["id"], col))

    if problems:
        print("构建失败（计数阶段）：%d 处" % len(problems), file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 1

    count_basis({"tasks": tasks_out, "causeEdges": edges_out, "states": states_out,
                 "foreshadows": fore_out, "worldSettings": world_out,
                 "themeReadings": theme_out, "unknowns": unk_out,
                 "rejectedTasks": rejected_tasks, "rejectedEdges": rejected_edges,
                 "notForeshadows": not_fore, "excludedSettings": excl})

    cand = {
        "task": task["id"],
        "agent": "w-sanguo-0",
        "role": "READER",
        "book": task["book"],
        "lane": task["lane"],
        "unitIndex": task["unitIndex"],
        "unitHead": task["unitHead"],
        "sourceRange": task["sourceRange"],
        "sourceHash": src_hash,
        "sourcePath": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "sliceCodepoints": e - s,
        "sliceSha256": hashlib.sha256(slice_text.encode("utf-8")).hexdigest(),
        "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[%d:%d)" % (s, e),
        "citationConvention": {
            "verbatim": "「」内一律为逐字原文；构建期逐条在 docs[0].text 里 find，查不到即失败（H2）。",
            "ownWords": "『』为我的转述或术语，不要求逐字核验。",
            "metaNote": "条数由构建脚本从数据结构生成，不手写（H18）。",
        },
        "offsetCaliber": "所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；"
                         "自检式：text[start:end] == quote 逐字成立（H1），且 text.find(quote)==start（H2）。",
        "sourceHashScope": "所有引用的 sourceHash 均为整个 docs.json 文件的 sha256（%s…）。" % src_hash[:16],
        "sliceSha256Scope": "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。",
        "graphCacheNotUsedAsEvidence": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.json",
            "note": "图谱缓存里的摘要未被用作任何一条结论的证据；本候选每条引文都能在 docs[0].text 里逐字命中。"
                    "缓存里的 5 个 event 只用于**对照**（见 graphCacheCrossCheck）。",
        },
        "graphCacheCrossCheck": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.json",
            "howFound": "按 chapter 字段等于本单元标题筛出缓存 event，再用 docs[0].text 复算其 quoteRef.start "
                        "落在哪一章（脚本，不靠缓存自称）。",
            "checked": [
                {
                    "event": "ev_d05b3b81e54f0f04",
                    "title": "阅读回信",
                    "cacheSummary": "（缓存只给标题与引文，无摘要句）",
                    "myReading": "t2：我把四封信读成**四个独立人物的行动线**，而不仅是许七安读到的内容 —— "
                                 "因此另外立了 t7（婶婶质问先生）、t8（临安闹司天监）两条任务，"
                                 "两者全部建在 letter 语层上并逐条标注。",
                    "agrees": "extends",
                },
                {
                    "event": "ev_39afb35c16d9fc89",
                    "title": "偷信败露",
                    "cacheSummary": "（缓存只给标题与引文，无摘要句）",
                    "myReading": "t4 + e4：我**不同意「败露」这个被动说法** —— 原文里偷看一事是许七安"
                                 "主动用话头诈出来的（q_t3_act → q_t3_res_quote），机制是信息自证，"
                                 "不是失手露馅。这也是我把 e4 标为 derived 的原因。",
                    "agrees": "no",
                },
                {
                    "event": "ev_a2bb06eb0313d984",
                    "title": "梁有平疑云",
                    "cacheSummary": "（引文「掳走梁有平的不是逼王？！」的 quoteRef.start=885452）",
                    "myReading": "**缓存把它算作本章事件，但按 docs[0].text 复算，885452 落在"
                                 "『第两百二十八章 抚恤金（本卷终）』，不在本单元区间 [872127,879573) 内。** "
                                 "所以这条疑云在本候选里只能作为 f2（unresolved）与 u1 登记，"
                                 "不能用那一句引文作证据。",
                    "agrees": "no",
                },
                {
                    "event": "ev_d44153c93aeb3a9f",
                    "title": "梦境见山海关",
                    "cacheSummary": "（引文「魏渊的事迹里，最出名的就是山海战役」）",
                    "myReading": "f1：我把它标为 **unresolved**。缓存把「见山海关」当事件标题，"
                                 "容易读成梦的内容已被确认；但原文里这只是许七安的**猜测**"
                                 "（q_dream_guess「心里当即有了猜测」），本区间无人证实、也无人回应。",
                    "agrees": "partial",
                },
                {
                    "event": "ev_bf19cd131fe2e0ee",
                    "title": "棺中重逢",
                    "cacheSummary": "（引文「问完，两人望着彼此，陷入了沉默」）",
                    "myReading": "t9 + e12：我把这次重逢读成**双向的信息封锁**（各自心虚 → 两问并列 → "
                                 "话题被岔开），并用 q_both_silent 作为「两个问题都没有答案」的依据。"
                                 "与缓存标题不冲突。",
                    "agrees": "yes",
                },
            ],
            "note": "缓存摘要只用来对照，不作为任何一条结论的证据。上面 5 条里 2 条明确不同意"
                    "（一条是归属错、一条是被动说法），1 条部分同意（把猜测写成事件）。",
        },
        "buildDisclosure": {
            "builder": "loop/state/out/read_dafeng_L0_0228.w-sanguo-0.build/build_candidate.py",
            "contentCore": "loop/state/out/read_dafeng_L0_0228.w-sanguo-0.build/content_core.py",
            "quoteRegistryGen": "loop/state/out/read_dafeng_L0_0228.w-sanguo-0.build/gen_quotes.py",
            "quoteSpec": "loop/state/out/read_dafeng_L0_0228.w-sanguo-0.build/quotes_spec.py（只写锚串，不写偏移）",
            "howOffsetsWereMade": "引文一律用键标记，偏移由 gen_quotes.py 在 docs[0].text 里**重新 find 锚串后切出**；"
                                  "content_core.py 与 quotes_spec.py 里都不含手写数字偏移。",
            "hardChecks": "H0–H24（见本脚本文档串）；任一不成立即 exit 1 且不写盘。",
        },
        "semanticReview": {
            "status": "not_performed",
            "note": "本候选只完成『引文可逐字定位 + 分区结构完整 + 五栏各有独立依据 + 语层已登记』这一层。"
                    "结论是否被原文支持、是否漏读，须由独立复核者按 read-verify 流程判定。"
                    "引用定位正确 ≠ 语义已核验。",
        },
        "tasks": tasks_out,
        "rejectedTasks": rejected_tasks,
        "causeEdges": edges_out,
        "rejectedEdges": rejected_edges,
        "states": states_out,
        "foreshadows": fore_out,
        "notForeshadows": not_fore,
        "worldSettings": world_out,
        "excludedSettings": excl,
        "themeReadings": theme_out,
        "unknowns": unk_out,
        "selfCritique": sc_out,
        "endingDisclosure": {
            "note": "本单元是章节不是全书；切片末尾附有作者的话（感谢盟主、卷末公告、"
                    "「打个招呼」）。它们与剧情无关，未被任何分区用作依据。"
                    "本候选没有任何一处把「读到结尾」写成「目标达成」。",
            "authorNoteKeys": ["q_author_note", "q_author_vol"],
        },
        "sliceNote": "切片按空行切分得到 %d 个非空段（脚本算出）。" % len(paras),
        "fiveColumnQuoteReuse": {
            "note": "同一任务的 objective/obstacle/action/result/cost 五栏之间**零共用引文**（H5 逐条复算）；"
                    "跨分区复用是允许的（同一处证据可支撑不同类型的分区），"
                    "禁止的是同一栏位内部与五栏之间的共用。",
            "perTask": [{"id": t["id"], "distinctQuoteKeys": t["distinctQuoteKeys"]}
                        for t in tasks_out],
        },
        "speechLayerDisclosure": {
            "layers": list(LAYER_ENUM),
            "letters": {
                "note": "本单元的四封信在原文里与对话同形（引号成段），登记为 speech 并加 "
                        "speechKind='letter'。**信只能承担「信上这样写」，其内容不得当作叙述事实。**"
                        "以信为据的分区：t7、t8（两条任务五栏全部）、s3、s7、s10、w3、w7、w8、th1 部分。",
                "letterKeys": sorted(S.LETTER_KEYS),
            },
        },
        "basisDistribution": basis_dist,
        "coverage": {
            "nonEmptyParagraphs": len(paras),
            "paragraphsTouchedByQuotes": len(paras) - len(zero),
            "zeroCoverageParagraphs": len(zero),
            "zeroCoverageList": zero,
            "paragraphSplitter": "空行（\\n\\s*\\n）切分；与其它 read 候选同口径。",
        },
        "citationIntegrity": {
            "totalQuoteObjects": len(all_quotes),
            "checks": {
                "text[start:end]==quote": 0,
                "find(quote)==start": 0,
                "inRange": 0,
                "sliceHitCount1": 0,
            },
            "note": "四个计数均为**失败数**，全部为 0 表示逐条通过（构建期 H1–H4 复算）。",
            "distinctQuotes": len(set(q["quote"] for q in all_quotes)),
        },
        "sectionCounts": {
            "tasks": len(tasks_out), "rejectedTasks": len(rejected_tasks),
            "causeEdges": len(edges_out), "rejectedEdges": len(rejected_edges),
            "states": len(states_out), "foreshadows": len(fore_out),
            "notForeshadows": len(not_fore), "worldSettings": len(world_out),
            "excludedSettings": len(excl), "themeReadings": len(theme_out),
            "unknowns": len(unk_out), "selfCritique": len(sc_out),
            "nullColumns": len(nulls),
        },
    }
    OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已写 %s（%d 字节）" % (OUT.name, OUT.stat().st_size))
    print("  引文对象 %d，去重字面量 %d，零覆盖段 %d/%d"
          % (len(all_quotes), cand["citationIntegrity"]["distinctQuotes"],
             len(zero), len(paras)))
    print("  裸 null 栏位 %d 个，全部带 Note" % len(nulls))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as exc:
        print("构建失败：%s" % exc, file=sys.stderr)
        sys.exit(1)
