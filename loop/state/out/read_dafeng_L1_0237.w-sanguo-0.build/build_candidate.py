# -*- coding: utf-8 -*-
"""read:dafeng:L1:0237 构建脚本（w-sanguo-0）。

职责与纪律：
1. 从 docs[0].text 取 [943450,948891) 切片；**所有偏移由 str.find 现算**，绝不手写。
   手打的引文子串若不在原文 ⇒ 立刻 AssertionError 退出（宁可不产出，也不产出错引文）。
2. 强制「同一任务内五栏不得共用同一条引文」：任何任务里出现重复引文即失败。
3. 全树自检：docs[0].text[start:end] == quote、sourceHash 相符、区间落在本单元内。
4. 统计数字（引文条数、null 栏数、分区计数）**由数据算出**，不手写。
"""
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
OUT = os.path.join(ROOT, "loop/state/out/read_dafeng_L1_0237.candidate.json")
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 943450, 948891
TASK_ID = "read:dafeng:L1:0237"
AGENT = "w-sanguo-0"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content_core as C  # noqa: E402


def load():
    with open(DOCS, "r", encoding="utf-8") as fh:
        docs = json.load(fh)
    text = docs[0]["text"]
    file_hash = hashlib.sha256(open(DOCS, "rb").read()).hexdigest()
    return text, file_hash


def main():
    text, file_hash = load()
    assert file_hash == SOURCE_HASH, "docs.json 哈希与任务声明不符：%s" % file_hash
    slice_ = text[START:END]
    assert slice_.startswith("第八章 案发现场"), "区间不以标题开头：%r" % slice_[:40]
    slice_sha = hashlib.sha256(slice_.encode("utf-8")).hexdigest()

    # 段落表（用于把「第几段」换算成真实偏移，并做出现次数约束）
    paras = []
    pos = START
    for ln in slice_.split("\n"):
        if ln.strip():
            paras.append((pos, ln))
        pos += len(ln) + 1

    # ── 引文解析 ──────────────────────────────────────────────────────
    resolved = {}
    problems = []
    for key, spec in C.Q.items():
        pidx, sub = spec[0], spec[1]
        occ = spec[2] if len(spec) > 2 else 0
        pstart, pline = paras[pidx]
        hits = []
        at = pline.find(sub)
        while at >= 0:
            hits.append(at)
            at = pline.find(sub, at + 1)
        if len(hits) <= occ:
            problems.append("引文 %s：在第 %d 段里找不到第 %d 次出现的 %r"
                            % (key, pidx, occ, sub[:40]))
            continue
        off = hits[occ]
        # 反向校验：该段里出现次数要与声明的 occ 相容
        abs_start = pstart + off
        abs_end = abs_start + len(sub)
        if text[abs_start:abs_end] != sub:
            problems.append("引文 %s：切片回读不一致" % key)
            continue
        resolved[key] = {
            "quote": sub,
            "start": abs_start,
            "end": abs_end,
            "sourceHash": SOURCE_HASH,
            "paragraph": pidx,
            "occurrenceInParagraph": occ,
            "occurrencesInParagraph": len(hits),
        }
    if problems:
        for p in problems:
            print("[构建失败] " + p, file=sys.stderr)
        return 2

    # 硬性检查：每条引文必须落在本单元区间内
    for key, r in resolved.items():
        assert START <= r["start"] < r["end"] <= END, "%s 越界" % key

    quote_of = {k: resolved[k]["quote"] for k in resolved}
    # 引文不得重复（同一条原文句子被定义两次会掩盖复用）
    dup = [q for q, n in Counter(quote_of.values()).items() if n > 1]
    assert not dup, "引文表内部重复：%r" % dup[:3]

    def ref(key):
        r = resolved[key]
        return {"quote": r["quote"], "start": r["start"], "end": r["end"],
                "sourceHash": r["sourceHash"]}

    def refs(keys):
        return [ref(k) for k in keys]

    # ── 1. tasks[] ────────────────────────────────────────────────────
    tasks_out = []
    for t in C.TASKS:
        item = {"id": t["id"], "who": t["who"], "label": t["label"]}
        for field in ("objective", "obstacle", "action", "result", "cost"):
            val = t.get(field)
            if val is None:
                item[field] = None
            else:
                item[field] = {"text": val["text"], "basis": val["basis"],
                               "quotes": refs(val["quotes"])}
                if val.get("caution"):
                    item[field]["caution"] = val["caution"]
        for field in ("objective", "obstacle", "action", "result", "cost"):
            nk = field + "Note"
            if nk in t:
                item[nk] = t[nk]
        for extra in ("speechDriven", "actionIsFalseSpeech", "resultIsEmpty"):
            if t.get(extra):
                item[extra] = True
        if t.get("selfAssessment"):
            sa = t["selfAssessment"]
            item["selfAssessment"] = {"text": sa["text"], "basis": sa["basis"],
                                      "quotes": refs(sa["quotes"])}
        tasks_out.append(item)

    # 强制：同一任务五栏不得共用同一条引文
    for item in tasks_out:
        seen = defaultdict(list)
        for field in ("objective", "obstacle", "action", "result", "cost"):
            v = item.get(field)
            if isinstance(v, dict):
                for q in v["quotes"]:
                    seen[q["quote"]].append(field)
        clash = {q: fs for q, fs in seen.items() if len(fs) > 1}
        assert not clash, "任务 %s 五栏共用引文：%r" % (item["id"], clash)

    # null 栏必须有理由
    for item in tasks_out:
        for field in ("objective", "obstacle", "action", "result", "cost"):
            if item.get(field) is None:
                assert item.get(field + "Note"), "%s.%s 是 null 但没写理由" % (item["id"], field)

    # ── 2. causeEdges[] ───────────────────────────────────────────────
    edges_out = []
    for e in C.CAUSE_EDGES:
        edges_out.append({
            "id": e["id"], "from": e["from"], "to": e["to"],
            "direction": "%s → %s" % (e["from"], e["to"]),
            "trigger": e["trigger"], "mechanism": e["mechanism"],
            "basis": e["mechanism"] if e["mechanism"] in ("explicit", "inferred", "derived", "unverified") else "inferred",
            "quotes": refs(e["quotes"]), "note": e["note"],
        })
    rejected_out = [{"id": r["id"], "candidateEdge": r["candidateEdge"], "why": r["why"],
                     "quotes": refs(r["quotes"])} for r in C.REJECTED_EDGES]
    hyp_out = [{"id": h["id"], "from": h["from"], "to": h["to"],
                "direction": "%s → %s" % (h["from"], h["to"]),
                "mechanism": h["mechanism"], "basis": h["mechanism"],
                "quotes": refs(h["quotes"]), "status": h["status"]} for h in C.HYPOTHESIZED_EDGES]
    for e in edges_out:
        assert e["quotes"], "因果边 %s 没有引文" % e["id"]
        assert e["trigger"].strip(), "因果边 %s 没有触发" % e["id"]

    # 每条边不得与「时间相邻/同一场景」为由 —— 用断言保证 trigger 写了机制
    for e in edges_out:
        assert "时间相邻" not in e["trigger"] or "不是" in e["trigger"], e["id"]

    # ── 3. states[] ───────────────────────────────────────────────────
    states_out = []
    for s in C.STATES:
        item = {"id": s["id"], "kind": s["kind"]}
        if s["kind"] == "change":
            item["who"] = s["who"]
            item["what"] = s["what"]
            item["before"] = {"text": s["before"]["text"], "basis": s["before"]["basis"],
                              "quotes": refs(s["before"]["quotes"])}
            item["after"] = {"text": s["after"]["text"], "basis": s["after"]["basis"],
                             "quotes": refs(s["after"]["quotes"])}
            item["anchor"] = {"text": s["anchor"]["text"], "basis": s["anchor"]["basis"],
                              "quotes": refs(s["anchor"]["quotes"])}
        else:
            item["topic"] = s["topic"]
            item["knownBy"] = {"who": s["knownBy"]["who"], "basis": s["knownBy"]["basis"],
                               "quotes": refs(s["knownBy"]["quotes"])}
            item["unknownTo"] = {"who": s["unknownTo"]["who"], "basis": s["unknownTo"]["basis"],
                                 "quotes": refs(s["unknownTo"]["quotes"])}
        if s.get("note"):
            item["note"] = s["note"]
        states_out.append(item)

    # ── 4. foreshadows[] ──────────────────────────────────────────────
    fore_out = []
    for f in C.FORESHADOWS:
        item = {"id": f["id"], "name": f["name"],
                "setup": {"text": f["setup"]["text"], "basis": f["setup"]["basis"],
                          "quotes": refs(f["setup"]["quotes"])},
                "status": f["status"]}
        if f["payoff"] is None:
            item["payoff"] = None
            item["payoffNote"] = f["payoffNote"]
        else:
            item["payoff"] = {"text": f["payoff"]["text"], "basis": f["payoff"]["basis"],
                              "quotes": refs(f["payoff"]["quotes"])}
        if f.get("note"):
            item["note"] = f["note"]
        fore_out.append(item)
    for f in fore_out:
        if f["status"] == "unresolved":
            assert f.get("payoff") is None and f.get("payoffNote"), \
                "%s 标 unresolved 必须显式写明未回收" % f["id"]
    notfore_out = [{"id": n["id"], "item": n["item"], "why": n["why"],
                    "quotes": refs(n["quotes"])} for n in C.NOT_FORESHADOWS]

    # ── 4b. worldSettings[] ───────────────────────────────────────────
    ws_out = []
    for w in C.WORLD_SETTINGS:
        item = {"id": w["id"], "kind": w["kind"], "name": w["name"],
                "quote": ref(w["quote"])["quote"], "quoteRef": ref(w["quote"]),
                "explain": w["explain"], "basis": "explicit"}
        if w["kind"] == "rule":
            assert w["institution"] in ("declared", "executed", "misunderstood")
            item["institution"] = w["institution"]
        elif w["kind"] == "place":
            assert w["placeState"] in ("arrived", "mentioned")
            item["placeState"] = w["placeState"]
        elif w["kind"] == "item":
            for st in w["itemStates"]:
                assert st in ("hold", "transfer", "use", "lose"), st
            item["itemStates"] = list(w["itemStates"])
            item["stateEvidence"] = [
                {"state": se["state"], "note": se["note"], "quoteRef": ref(se["quote"])}
                for se in w["stateEvidence"]]
            got = {se["state"] for se in w["stateEvidence"]}
            assert got == set(w["itemStates"]), \
                "%s 声明的 itemStates 与 stateEvidence 不一致：%r vs %r" % (w["id"], w["itemStates"], got)
        if w.get("speechOrNarration"):
            item["speechOrNarration"] = w["speechOrNarration"]
        ws_out.append(item)
    assert [w for w in ws_out if w["kind"] == "place"], "place 分区为空要显式说明，不能静默"
    excl_out = [{"id": x["id"], "item": x["item"], "why": x["why"],
                 "quotes": refs(x["quotes"])} for x in C.EXCLUDED_SETTINGS]

    # ── 4c. themeReadings[] ───────────────────────────────────────────
    th_out = []
    for t in C.THEME_READINGS:
        item = {"id": t["id"], "perspective": t["perspective"], "basis": t["basis"]}
        item["support"] = [{"text": s["text"], "quotes": refs(s["quotes"])} for s in t["support"]]
        item["counter"] = [{"text": s["text"], "quotes": refs(s["quotes"])} for s in t["counter"]]
        assert item["support"] and item["counter"], "%s 缺 support 或 counter" % t["id"]
        item["note"] = t["note"]
        th_out.append(item)

    # ── 作者附言层（非叙事） ──────────────────────────────────────────
    an = C.AUTHOR_NOTE_LAYER
    author_note_out = {
        "present": an["present"], "range": an["range"], "what": an["what"],
        "disposition": an["disposition"], "whyItMatters": an["whyItMatters"],
        "quotes": refs(an["quotes"]),
        "segments": [{"label": s["label"], "quotes": refs(s["quotes"])} for s in an["segments"]],
    }

    # ── 5. unknowns / selfCritique ────────────────────────────────────
    unk_out = [{"id": u["id"], "topic": u["topic"], "why": u["why"],
                "quotes": refs(u["quotes"])} for u in C.UNKNOWNS]
    sc_out = [{"id": "sc%d" % (i + 1), "where": s["where"], "risk": s["risk"],
               "why_still": s["why_still"]} for i, s in enumerate(C.SELF_CRITIQUE)]

    # ── 人物话语层清单 ────────────────────────────────────────────────
    speech_out = [{"quoteRef": ref(k), "note": C.SPEECH_NOTES.get(k, "人物话语，不是叙述事实。")}
                  for k in C.SPEECH_KEYS]
    narr_eval = [{"quoteRef": ref(k), "note": n} for k, n in C.NARRATOR_EVALUATION]

    # ── 跨分区复用披露（由数据算出） ──────────────────────────────────
    usage = defaultdict(list)
    def scan(obj, path):
        if isinstance(obj, dict):
            if "quote" in obj and "start" in obj and "end" in obj and isinstance(obj["quote"], str):
                usage[obj["quote"]].append(path)
            for k, v in obj.items():
                scan(v, path + "/" + k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                scan(v, path + "[%d]" % i)

    body = {
        "tasks": tasks_out, "causeEdges": edges_out, "rejectedEdges": rejected_out,
        "hypothesizedEdges": hyp_out, "states": states_out, "foreshadows": fore_out,
        "notForeshadows": notfore_out, "worldSettings": ws_out,
        "excludedSettings": excl_out, "themeReadings": th_out,
        "unknowns": unk_out, "selfCritique": sc_out,
        "speechLayer": speech_out, "narratorEvaluation": narr_eval,
        "authorNoteLayer": author_note_out,
    }
    scan(body, "")
    reuse = [{"quote": q, "count": len(v), "paths": v} for q, v in usage.items() if len(v) > 1]
    reuse.sort(key=lambda x: -x["count"])

    # ── 覆盖率（由数据算出） ──────────────────────────────────────────
    touched = set()
    for q, paths in usage.items():
        r = next(r for k, r in resolved.items() if r["quote"] == q)
        touched.add(r["paragraph"])
    all_p = set(range(len(paras)))
    zero = sorted(all_p - touched)
    zero_list = [{"paragraph": i, "start": paras[i][0], "excerpt": paras[i][1][:50]}
                 for i in zero]

    cand = {
        "task": TASK_ID, "agent": AGENT, "role": "READER",
        "book": "dafeng", "lane": 1, "unitIndex": 237, "unitHead": "第八章 案发现场",
        "sourceRange": [START, END],
        "sourceHash": SOURCE_HASH,
        "sliceCodepoints": len(slice_),
        "sliceSha256": slice_sha,
        "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[%d:%d)" % (START, END),
        "offsetCaliber": "所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；自检式：text[start:end] == quote 逐字成立。",
        "sourceHashScope": "所有引用的 sourceHash 均为整个 docs.json 文件的 sha256（构建时实测复算一致），不是切片哈希。",
        "sliceSha256Scope": "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。",
        "graphCacheNotUsedAsEvidence": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.json",
            "note": "图谱缓存里的摘要不是原文证据，本候选没有从它取任何引文或结论；全部引文由构建脚本在 docs[0].text 里现定位、现切片。",
        },
        **body,
        "tasksNote": (
            "%d 条任务、%d 个栏位，其中 %d 个裸 null（%s），每个 null 都在同名的 <栏位>Note 里写明为什么没有依据。"
            "**同一任务内五栏共用同一条引文的情况为 0**（构建脚本断言，非手写计数）；"
            "跨任务的引文复用逐条列在 crossSectionQuoteReuse，没有隐藏。"
            % (len(tasks_out), len(tasks_out) * 5,
               sum(1 for i in tasks_out for f in ("objective", "obstacle", "action", "result", "cost")
                   if i.get(f) is None),
               "、".join("%s.%s" % (i["id"], f) for i in tasks_out
                        for f in ("objective", "obstacle", "action", "result", "cost")
                        if i.get(f) is None))
        ),
        "causeEdgesNote": (
            "%d 条边，每条都有 direction 与 trigger（A 导致 B 的机制），没有一条以时间相邻或同一场景为由连边。"
            "另有 %d 条被拒边（rejectedEdges，逐条写明堵点）与 %d 条显式标为推断的假设链（hypothesizedEdges，来自许七安的侧写，绝不混入 causeEdges）。"
            % (len(edges_out), len(rejected_out), len(hyp_out))
        ),
        "rejectedEdgesNote": (
            "%d 条被拒边，覆盖三类最容易被误连的关系：把人物推断当事实（r4）、把提问当结论（r3）、把叙述者评价当定罪依据（r6）；"
            "另外 r2 与原文相反、r5 是替相邻动作编动机、r7 与原文无任何挂钩。登记被拒边与登记因果边同样重要 —— 它说明我检查过这些诱人的连边。"
            % len(rejected_out)
        ),
        "statesNote": (
            "%d 条状态：%d 条 change（前值/后值/事件锚点各带引文）、%d 条 knowledge_gap（谁知/不知分列）。"
            "k4 的 knownBy 是**有依据的空集**（本区间没有任何人明确知道太子有罪），已在 note 里写明为什么空。"
            "k2 必须保留原文的「也许/可能」语气，不得替原文把「她不知道」定死。"
            % (len(states_out), sum(1 for s in states_out if s["kind"] == "change"),
               sum(1 for s in states_out if s["kind"] == "knowledge_gap"))
        ),
        "foreshadowsNote": (
            "%d 条伏笔：%d 条完整回收（f1 的铺设与回收都在本区间内）、%d 条显式标 unresolved（各带 payoffNote 写明未回收）。"
            "另立 %d 条 notForeshadows，逐条写明为什么只出现一次的东西不列入。判定口径见 foreshadows 各条的 note。"
            % (len(fore_out), sum(1 for f in fore_out if f["status"] == "resolved"),
               sum(1 for f in fore_out if f["status"] == "unresolved"), len(notfore_out))
        ),
        "worldSettingsNote": C.WORLD_SETTINGS_NOTE,
        "placesNote": C.PLACES_NOTE,
        "itemsNote": C.ITEMS_NOTE,
        "excludedSettingsNote": (
            "%d 条被排除项，逐条写明排除理由。其中 x1 与 x3 是本次辨别里最重要的两处："
            "x1 是一套在本区间**没有产生任何作用**的知识（主角自己承认它用不上），x3 是一个只有一次描写、没有代价与上限的能力名词。"
            "按计划「没有依据就不扩出地图、物品链或术语装饰层」，两者都只保留为其因果机制或人物素材，不升级成世界设定。"
            % len(excl_out)
        ),
        "themeReadingsNote": C.THEME_READINGS_NOTE,
        "unknownsNote": C.UNKNOWNS_NOTE,
        "selfCritiqueNote": C.SELF_CRITIQUE_NOTE,
        "semanticReview": {
            "status": "not_performed",
            "note": "本候选只做了引用定位与逐字核验（构建脚本断言 + 独立复算，命令与哈希见提交记录），没有做语义评审。"
                    "每条结论是否成立，必须由 read-verify 通道的独立复核者对着原文判断。引文定位正确不等于语义已核验。",
        },
        "citationConvention": {
            "verbatim": "所有逐字引文都放在各自条目下的 quotes / quote / quoteRef 字段里。",
            "ownWords": "分析文字里用 U+300C/U+300D 包住的片段一律是我的用语或转述（不是原文）；原文一律放在 quote 字段里。",
        },
        "crossSectionQuoteReuse": reuse,
        "crossSectionQuoteReuseNote": (
            "跨分区复用如实披露：同一句原文出现在两个以上分区时逐条列出（%d 条，**由构建脚本从数据生成**，不是手写计数）。"
            "判据是同一任务内五栏不得共用一句；跨分区复用说明同一句被用于不同用途，这类复用我没有隐藏，请复核者判断是否恰当。"
            % len(reuse)
        ),
        "coverage": {
            "nonEmptyParagraphs": len(paras),
            "paragraphsTouchedByQuotes": len(touched),
            "zeroCoverageParagraphs": len(zero),
            "zeroCoverageList": zero_list,
            "zeroCoverageListNote": "零引用段落逐条列出（含首句片段），便于反向验证时直接问「这些段里还漏了什么」。",
            "paragraphDisposition": [
                {"category": d["category"], "handling": d["handling"], "quotes": refs(d["quotes"])}
                for d in C.PARAGRAPH_DISPOSITION
            ],
            "paragraphDispositionNote": "零引用段落不是「未处置」：上表按类别写明每一类**为什么**不需要引文，各配一条取样引文供复核者核对判断是否成立。",
        },
        "countsAreGenerated": True,
    }

    # ── 全树终检 ──────────────────────────────────────────────────────
    total = 0
    bad = []
    def verify(obj, path):
        nonlocal total
        if isinstance(obj, dict):
            if isinstance(obj.get("quote"), str) and isinstance(obj.get("start"), int) and isinstance(obj.get("end"), int):
                total += 1
                if text[obj["start"]:obj["end"]] != obj["quote"]:
                    bad.append(path)
                if obj.get("sourceHash") != SOURCE_HASH:
                    bad.append(path + " (hash)")
                if not (START <= obj["start"] < obj["end"] <= END):
                    bad.append(path + " (range)")
            for k, v in obj.items():
                verify(v, path + "/" + k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                verify(v, path + "[%d]" % i)

    verify(cand, "")
    if bad:
        for b in bad[:10]:
            print("[构建失败] 终检不合格：" + b, file=sys.stderr)
        return 3

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(cand, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    print("引文总数（终检通过）：%d" % total)
    print("切片码点：%d  切片 sha256：%s" % (len(slice_), slice_sha))
    print("任务 %d / 因果边 %d / 被拒边 %d / 假设链 %d / 状态 %d / 伏笔 %d / 世界设定 %d / 主题 %d / unknowns %d"
          % (len(tasks_out), len(edges_out), len(rejected_out), len(hyp_out),
             len(states_out), len(fore_out), len(ws_out), len(th_out), len(unk_out)))
    print("零引用段落：%d / %d" % (len(zero), len(paras)))
    print("跨分区复用：%d 条" % len(reuse))
    print("写出：%s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
