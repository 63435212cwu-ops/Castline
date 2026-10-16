# -*- coding: utf-8 -*-
"""构建 read:sanguo:L1:0095 候选 JSON。

写出前强制通过四组断言（任一失败即中止，不写出）：
  A 引文校验：每条 quoteRef 满足 text[start:end]==quote、text.find(quote)==start、
    落在区间内、sourceHash 相符。
  B 五栏复用校验：同一个 task 的 objective/obstacle/action/result/cost 五栏之间
    **不得共用同一引文区间**（提示词点名的 714/1664 缺陷）。
  C null 栏标注校验：任一栏为 null 时，必须存在同名的 <栏位>Note。
  D worldSettings 三态校验：place 必须有 placeState，item 必须有 itemStates 多选，
    rule 必须有 institution。
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from quotes import QuoteResolver, load_text, SRC, SRC_HASH, verify_quotes
import part1
import part2
import part3
import part4
import supplement
import unknowns as unk

S, E = 484338, 489034
TASK_ID = "read:sanguo:L1:0095"
AGENT = "w-dafeng-1"
OUT = "loop/state/out/read_sanguo_L1_0095.candidate.json"
BUILD = os.path.dirname(os.path.abspath(__file__))

COLS = ("objective", "obstacle", "action", "result", "cost")


def sha256_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def spans_of(col):
    return [(r["start"], r["end"]) for r in (col or {}).get("quotes", [])]


def check_five_column_reuse(tasks):
    """B 组：五栏之间不得共用同一引文区间。"""
    bad = []
    for t in tasks:
        seen = {}
        for c in COLS:
            col = t.get(c)
            if not col:
                continue
            for sp in spans_of(col):
                if sp in seen:
                    bad.append("%s: 栏位 %s 与 %s 共用引文区间 %s"
                               % (t["id"], c, seen[sp], sp))
                else:
                    seen[sp] = c
    return bad


def check_null_notes(tasks):
    """C 组：null 栏必须有同名 Note 说明为什么没有。"""
    bad = []
    for t in tasks:
        for c in COLS:
            if t.get(c) is None and not t.get(c + "Note"):
                bad.append("%s.%s 为 null 但没有 %sNote" % (t["id"], c, c))
    return bad


def check_world(world):
    """D 组：place/item/rule 三态字段必须显式。"""
    bad = []
    for w in world:
        k = w.get("kind")
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            bad.append("place %s 缺/错 placeState=%r" % (w.get("name"), w.get("placeState")))
        if k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st:
                bad.append("item %s 缺 itemStates" % w.get("name"))
            else:
                for x in st:
                    if x not in ("hold", "transfer", "use", "lose"):
                        bad.append("item %s 非法 itemState=%r" % (w.get("name"), x))
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            bad.append("rule %s 缺/错 institution=%r" % (w.get("name"), w.get("institution")))
        if k not in ("place", "item", "rule"):
            bad.append("worldSettings 非法 kind=%r" % k)
    return bad


def check_edge_order(edges):
    """因果边时序：因的引文不得晚于果的引文（允许同句，登记后单列）。"""
    problems = []
    for e in edges:
        cq = [r["start"] for r in e.get("causeQuotes") or []]
        eq = [r["start"] for r in e.get("effectQuotes") or []]
        if not cq or not eq:
            problems.append("%s: cause/effect 引文为空" % e["id"])
            continue
        if max(cq) > min(eq):
            problems.append("%s: 因(%d) 晚于 果(%d)" % (e["id"], max(cq), min(eq)))
    return problems


def main():
    text = load_text()
    assert len(text) == 607191, len(text)
    seg = text[S:E]
    assert seg.startswith("第九十六回"), repr(seg[:20])
    assert len(seg) == 4696, len(seg)

    R = QuoteResolver(text, S, E)

    tasks = part1.build(R) + part2.build(R)
    edges = part3.build_edges(R)
    rejected = part3.build_rejected(R)
    states = part3.build_states(R)
    gaps = part3.build_knowledge_gaps(R)
    fores = part4.build_foreshadows(R)
    not_fores = part4.build_not_foreshadows(R)
    world = part4.build_world(R)
    not_world = part4.build_not_world(R)
    themes = part4.build_themes(R)
    unknowns = unk.build_unknowns(R)
    self_critique = unk.build_self_critique(R)
    textual_notes = supplement.add_textual_notes()
    speech_clues = supplement.add_speech_clues(R)

    # ── 第二轮：反向覆盖补入（见 supplement.py 的说明）
    sup = supplement.EXTRA_QUOTES()
    index = {"tasks": tasks, "causeEdges": edges, "knowledgeGaps": gaps}
    missing = []
    applied = 0
    for (section, eid, col), items in sup.items():
        target = None
        for e in index[section]:
            if e.get("id") == eid:
                target = e
                break
        if target is None:
            missing.append("%s.%s 不存在" % (section, eid))
            continue
        # tasks 的栏位是对象（{text,basis,voice,quotes[]}），其余分区直接是列表
        holder = target.setdefault(col, {})
        if isinstance(holder, dict):
            bucket = holder.setdefault("quotes", [])
        else:
            bucket = holder
        existing = {(r["start"], r["end"]) for r in bucket}
        for quote, voice, nth in items:
            ref = R.ref(quote, nth=nth, voice=voice)
            if (ref["start"], ref["end"]) in existing:
                continue
            bucket.append(ref)
            existing.add((ref["start"], ref["end"]))
            applied += 1
    if missing:
        for m in missing:
            print("BUILD-BLOCKED(补入): %s" % m, file=sys.stderr)
        return 1
    print("补入引文 %d 条" % applied, file=sys.stderr)

    problems = []
    problems += check_five_column_reuse(tasks)
    problems += check_null_notes(tasks)
    problems += check_world(world)
    problems += check_edge_order(edges)
    for f in fores:
        if f["status"] == "resolved" and not f.get("payoffQuotes"):
            problems.append("%s: resolved 但没有 payoffQuotes" % f["id"])
        if f["status"] == "unresolved" and f.get("payoffQuotes"):
            problems.append("%s: unresolved 却给了 payoffQuotes" % f["id"])
    if problems:
        for p in problems:
            print("BUILD-BLOCKED: %s" % p, file=sys.stderr)
        return 1

    cand = {
        "schemaVersion": 31,
        "task": TASK_ID,
        "agent": AGENT,
        "role": "READER（原文精读工作者）",
        "book": "sanguo",
        "bookTitle": "三国演义",
        "lane": 1,
        "unitIndex": 95,
        "unitHead": "第九十六回　孔明挥泪斩马谡　周鲂断发赚曹休",
        "semanticReview": "not_performed",
        "semanticReviewNote": "本候选只做定位、抽取与自证；语义核验属 read-verify 通道，由另一位 agent 独立进行。引文定位正确 ≠ 语义已核验，不得据此认定 semanticReview 已完成。",
        "source": {
            "path": SRC,
            "docIndex": 0,
            "sourceHash": SRC_HASH,
            "sourceHashMeaning": "整个 docs.json 文件的 sha256（实测）",
            "measuredFileSha256": SRC_HASH,
            "textCodepoints": len(text),
            "textSha256": hashlib.sha256(text.encode()).hexdigest(),
            "range": [S, E],
            "rangeCodepoints": len(seg),
            "segmentSha256": hashlib.sha256(seg.encode()).hexdigest(),
            "segmentSha256Meaning": "docs[0].text[start:end] 切片自身的 sha256（另起字段，未覆盖 sourceHash）",
            "selfCheck": "docs[0].text[484338:489034] 以回目「第九十六回　孔明挥泪斩马谡　周鲂断发赚曹休」开头，长度 4696 == 任务声明的 4696 字；右端点即下一单元回目起点（docs[0].text[489034:489054] == 「第九十七回　讨魏国武侯再上表　破曹兵姜维诈献书」）。",
            "reproduce": "python3 -c \"import json,hashlib;raw=open('data/cache/fe42d01f3826fe8096f86614.docs.json','rb').read();print(hashlib.sha256(raw).hexdigest());t=json.loads(raw)[0]['text'];s=t[484338:489034];print(len(s),hashlib.sha256(s.encode()).hexdigest())\"",
        },
        "sourceHashDiscrepancy": {
            "taskJsonSourceHash": "2988ce6e36c80c4effc81f73a65221adf779631682da848bb67ef6f52a5a97ff",
            "promptBodySourceHash": SRC_HASH,
            "measuredFileHash": SRC_HASH,
            "finding": "任务 JSON 的 sourceHash（2988ce6e…）不等于提示词正文给出的、也不等于实测的 fe42d01f3826fe8096f86614.docs.json 文件哈希（8ab7298a…），但它**确实等于另一个真实存在的文件**：data/cache/152e2a6eed94f1075e7e7070.docs.json 的 sha256。两文件同大小 1814090 字节，docs[0].text 内容逐字相同（同为 607191 codepoint，text 的 sha256 同为 9d28638d…），差异只在 JSON 序列化。本区间在两侧文件里落在完全相同的偏移上。",
            "evidence": {
                "152e2a6eed94f1075e7e7070.docs.json": "2988ce6e36c80c4effc81f73a65221adf779631682da848bb67ef6f52a5a97ff",
                "fe42d01f3826fe8096f86614.docs.json": SRC_HASH,
                "textIdentical": True,
                "bytes": 1814090,
            },
            "handling": "按提示词明文指定的 sourceHash 与任务声明要读的文件（fe42d01f3826fe8096f86614.docs.json）用 8ab7298a… 作为全部 quoteRef 的 sourceHash；未修改任何校验规则或任务元数据。",
            "reproduce": "python3 -c \"import json,hashlib;a=open('data/cache/152e2a6eed94f1075e7e7070.docs.json','rb').read();b=open('data/cache/fe42d01f3826fe8096f86614.docs.json','rb').read();print(hashlib.sha256(a).hexdigest(),hashlib.sha256(b).hexdigest(),len(a),len(b),json.loads(a)[0]['text']==json.loads(b)[0]['text'])\"",
        },
        "basisLegend": {
            "explicit": "原文直述（叙述层或人物话语中明确写出的内容）",
            "inferred": "我的归纳（原文未直说，由若干处事实归纳得出）",
            "derived": "跨段推导（需组合本区间不同位置的信息才能得出）",
            "unverified": "存疑（原文有歧义或证据不足）",
        },
        "voiceLegend": {
            "narration": "叙述层语句",
            "character": "人物话语（含奏对、表文、书中语）",
            "mixed": "同栏内同时含叙述层与人物话语",
        },
        "quotationConvention": "全部 quote 为 docs[0].text 的逐字子串，start/end 为**全文 codepoint 偏移**（与本单元区间同一口径），满足 text[start:end]==quote 且 text.find(quote)==start。文言原字（如「掷」「掣」「匿」）照原文抄录，不改写成现代汉语。",
        "tasks": tasks,
        "causeEdges": edges,
        "rejectedCauseEdges": rejected,
        "states": states,
        "knowledgeGaps": gaps,
        "foreshadows": fores,
        "notForeshadows": not_fores,
        "worldSettings": world,
        "notWorldSettings": not_world,
        "themeReadings": themes,
        "speechAsClueNotFact": speech_clues,
        "unknowns": unknowns,
        "selfCritique": self_critique,
        "textualNotes": textual_notes,
        "provenanceNote": unk.PROVENANCE,
        "fieldCounts": {},
    }

    # ── 独立复核（从内存结构复算，写盘后还会对落盘文件再跑一次）
    stats, failures = verify_quotes(cand, text)
    if failures:
        for f in failures[:40]:
            print("QUOTE-FAIL: %s" % f, file=sys.stderr)
        print("共 %d 条失败" % len(failures), file=sys.stderr)
        return 1

    cand["fieldCounts"] = {
        "tasks": len(tasks),
        "causeEdges": len(edges),
        "rejectedCauseEdges": len(rejected),
        "states": len(states),
        "knowledgeGaps": len(gaps),
        "foreshadows": len(fores),
        "foreshadowsResolved": sum(1 for f in fores if f["status"] == "resolved"),
        "foreshadowsUnresolved": sum(1 for f in fores if f["status"] == "unresolved"),
        "notForeshadows": len(not_fores),
        "worldSettings": len(world),
        "worldSettingsByKind": {
            k: sum(1 for w in world if w["kind"] == k) for k in ("place", "item", "rule")
        },
        "placeStateCounts": {
            k: sum(1 for w in world if w.get("placeState") == k)
            for k in ("arrived", "mentioned")
        },
        "themeReadings": len(themes),
        "quoteRefs": stats["quoteRefs"],
    }

    if "--dry" in sys.argv:
        print(json.dumps(cand["fieldCounts"], ensure_ascii=False, indent=1))
        return 0

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cand, f, ensure_ascii=False, indent=1)
    print("已写出 %s" % OUT)
    print("quoteRefs=%d" % stats["quoteRefs"])
    print(json.dumps(cand["fieldCounts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
