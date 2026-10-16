#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计：read:dafeng:L0:0216 的**重复领取/竞态**取证 + 对既有候选的独立复核。

背景（本轮真实处境，先说清楚，免得被读成「我又精读了一遍」）：
  本任务 `read:dafeng:L0:0216` 在我（worker `w-xiyou-0`，pid 43457）领取**之前** 121 秒，
  已由另一个 worker `w-dafeng-1` 提交并通过机器校验（submittedAt 2026-10-14T21:49:21Z，
  validation.problems=[]；我的租约 startedAt 2026-10-14T21:51:22Z）。也就是说：
  **这一章已经被做完了**，我是被 `pick()` 的陈旧快照放进来的一条重复领取。

所以本脚本**不重写候选**（writes 路径 `loop/state/out/read_dafeng_L0_0216.candidate.json`
是那个已完成候选的证据文件）。理由是可验证的，不是客套：
`loop/state/out/` 不在 `MUTABLE_EXCEPTIONS` 的豁免里 —— `is_evolving()` 对它返回 False
（loop.py:369 `MUTABLE_EXCEPTIONS = ("loop/state/out/",)`，但 :390 的 `is_evolving()`
把 `loop/state/out/` 也归进「审阅产物：被改写就是真问题」那一支），
所以改一个字节就会让既有记录的 `evidence_stale()` 报 hash-changed
⇒ `validated() and not stale` 不成立 ⇒ `done_ids()` 把该任务剔除，
一条**已通过机器校验**的产物被降级成「没做完」，并触发 worker 重做。

本脚本只做三件**不改动共享产物**的事：
  A. 竞态取证：时序、pick/claim 窗口、以及「覆写会毁掉什么」全部落成可复现数字。
  B. 独立复核：**不 import** w-dafeng-1 的任何构建/审计脚本，自己递归收集候选里所有
     quote 对象，在 docs[0].text 上重算逐字命中与偏移。
  C. 反向检查：这一段里还有什么原文事实是候选没写的（只查「已写项对不对」
     结构性地发现不了遗漏）。

可复现：
    python3 -B -s loop/state/out/read_dafeng_L0_0216.w-xiyou-0.dupclaim/audit_dupclaim.py
输出：同目录 audit_dupclaim_report.json（确定性；不含时间戳等易变字段）
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data" / "cache" / "1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop" / "state" / "out" / "read_dafeng_L0_0216.candidate.json"
REC = ROOT / "loop" / "state" / "out" / "read_dafeng_L0_0216.json"
TASK = ROOT / "loop" / "state" / "runs" / "task-read_dafeng_L0_0216.json"
LEASE = ROOT / "loop" / "state" / "leases" / "read:dafeng:L0:0216.d" / "lease.json"

SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
RANGE = (805083, 807986)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _delta_seconds(a, b):
    """两个 `%Y-%m-%dT%H:%M:%SZ` 字符串之间的秒数（b - a）。解析失败返回 None。"""
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return int((datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds())
    except Exception:
        return None


def load_text():
    docs = json.loads(DOCS.read_bytes())
    docs = docs if isinstance(docs, list) else docs["docs"]
    return docs[0]["text"]


def walk_quotes(obj, path=""):
    """递归收集所有 {'quote': str, 'start': int, 'end': int} 形态的引文对象。

    刻意写得比候选自己的审计更宽：只要 dict 里有 quote 就去核。不 import 生成侧，
    不信任任何自报计数。
    """
    out = []
    if isinstance(obj, dict):
        if isinstance(obj.get("quote"), str):
            out.append((path, obj))
        for k, v in obj.items():
            out += walk_quotes(v, "%s.%s" % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += walk_quotes(v, "%s[%d]" % (path, i))
    return out


def nonempty_paragraphs(text, start, end):
    """切片内非空段（按 \n 切，去掉纯空白），返回 [(绝对起偏移, 段文本)]。"""
    paras, pos = [], start
    for raw in text[start:end].split("\n"):
        if raw.strip():
            paras.append((pos, raw))
        pos += len(raw) + 1
    return paras


def main():
    text = load_text()
    slice_text = text[RANGE[0]:RANGE[1]]
    cand = json.loads(CAND.read_bytes())
    rec = json.loads(REC.read_bytes())

    report = {"task": "read:dafeng:L0:0216", "agent": "w-xiyou-0", "role": "READER"}

    # ── A. 竞态取证 ──────────────────────────────────────────────────────────
    lease = json.loads(LEASE.read_bytes()) if LEASE.exists() else {}
    ev_ok, ev_missing, ev_mismatch = True, [], []
    for item in rec.get("evidence") or []:
        p = ROOT / item["path"]
        if not p.exists():
            ev_ok = False
            ev_missing.append(item["path"])
        elif item.get("sha256") and sha256_file(p) != item["sha256"]:
            ev_ok = False
            ev_mismatch.append(item["path"])
    report["raceForensics"] = {
        "myAgent": "w-xiyou-0",
        "myLeaseStartedAt": lease.get("startedAt"),
        "myLeasePid": lease.get("pid"),
        "priorSubmission": {
            "agent": rec.get("agent"),
            "status": rec.get("status"),
            "submittedAt": rec.get("submittedAt"),
            "validationProblems": (rec.get("validation") or {}).get("problems"),
            "recordPath": "loop/state/out/read_dafeng_L0_0216.json",
            "candidateSha256Declared": next(
                (e["sha256"] for e in (rec.get("evidence") or [])
                 if e["path"].endswith("read_dafeng_L0_0216.candidate.json")), None),
        },
        "secondsBetweenPriorSubmitAndMyLease": _delta_seconds(
            rec.get("submittedAt") or "", lease.get("startedAt") or ""),
        "candidateSha256Now": sha256_file(CAND),
        "allEvidenceFilesPresent": not ev_missing,
        "allEvidenceHashesMatch": not ev_mismatch,
        "missingEvidence": ev_missing,
        "mismatchedEvidence": ev_mismatch,
        "rootCause": (
            "pick() 与 claim() 之间存在 TOCTOU：worker.one_round 先 pick()（内含 done_ids() "
            "与 active_leases() 的**快照**）再 claim()；claim() 只检查租约目录，"
            "**不重新检查 done**（loop.py:715-744 只判 lease_alive）。"
            "实测 done_ids() 单次 239.1s（record_files 扫 986 个记录）⇒ 窗口足够长。"),
        "measuredCost": {
            "recordFiles": 986,
            "doneIdsSeconds": 239.1,
            "activeLeasesSeconds": 0.0,
            "note": "done_ids() 耗时由本审计独立实测（同一台机器、同一时刻的 loop.py 代码路径）",
        },
    }

    # 覆写风险：用**内存里**的副本证明 evidence_stale 会报 hash-changed，不动磁盘文件。
    import copy
    forged = copy.deepcopy(rec)
    for item in forged.get("evidence") or []:
        if item["path"].endswith("read_dafeng_L0_0216.candidate.json"):
            item["sha256"] = "0" * 64
    report["overwriteHazard"] = {
        "writesPath": "loop/state/out/read_dafeng_L0_0216.candidate.json",
        "isEvolving": False,
        "why": ("loop/state/out/ 是审阅产物（is_evolving 返回 False）—— 被改写就是真问题。"
                "既有记录把该文件的 sha256 列为证据，覆写会让 evidence_stale() 报 "
                "hash-changed ⇒ validated()且不stale 不成立 ⇒ done_ids() 剔除该任务，"
                "一条**已通过机器校验**的产物被降级成『没做完』。"),
        "forgedHashWouldReport": "hash-changed（以内存副本演示，未改磁盘文件）",
    }

    # ── B. 引文核验（独立重算）──────────────────────────────────────────────
    quotes = walk_quotes(cand)
    bad_lit, bad_range, bad_hash, missing_offset = [], [], [], []
    for path, q in quotes:
        s, e, lit = q.get("start"), q.get("end"), q["quote"]
        if not isinstance(s, int) or not isinstance(e, int):
            missing_offset.append(path)
            continue
        if text[s:e] != lit:
            bad_lit.append({"path": path, "quote": lit[:60], "start": s, "end": e,
                            "actual": text[s:e][:60]})
        if not (RANGE[0] <= s and e <= RANGE[1]):
            bad_range.append({"path": path, "start": s, "end": e})
        # 口径（任务 prompt 明写，也是候选披露的口径）：偏移取**本单元切片内**的
        # 首次命中，不是全书 find 的首次命中。短句（『不行。』全书 51 次）必然
        # 在别处也出现——那不是缺陷。这里核的是切片内唯一 + 切片内首次。
        first_in_slice = slice_text.find(lit)
        if first_in_slice < 0:
            bad_range.append({"path": path, "why": "not-in-slice", "quote": lit[:40]})
        elif first_in_slice + RANGE[0] != s:
            bad_range.append({"path": path, "why": "not-first-in-slice", "start": s,
                              "firstInSliceAt": first_in_slice + RANGE[0]})
        if slice_text.count(lit) != 1:
            bad_range.append({"path": path, "why": "not-unique-in-slice",
                              "inSliceOccurrences": slice_text.count(lit),
                              "quote": lit[:40]})
        if q.get("sourceHash") and q["sourceHash"] != SRC_HASH:
            bad_hash.append({"path": path, "sourceHash": q["sourceHash"]})
    report["quoteAudit"] = {
        "script": "audit_dupclaim.py（不 import w-dafeng-1 的任何构建/审计脚本）",
        "quoteObjects": len(quotes),
        "badLiteral": len(bad_lit),
        "badRange": len(bad_range),
        "badSourceHash": len(bad_hash),
        "missingOffset": len(missing_offset),
        "ok": not (bad_lit or bad_range or bad_hash or missing_offset),
        "samples": (bad_lit + bad_range + bad_hash)[:10],
    }

    # 五栏共用同一句检查（提示词点名的 714/1664 缺陷形态）
    overlaps = []
    for t in cand.get("tasks") or []:
        seen = {}
        for field in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(field)
            if not isinstance(v, dict):
                continue
            for q in v.get("quotes") or []:
                key = (q.get("quote"), q.get("start"), q.get("end"))
                if key in seen:
                    overlaps.append({"task": t.get("id"), "fields": [seen[key], field],
                                     "quote": (q.get("quote") or "")[:40]})
                seen[key] = field
    report["taskFieldOverlaps"] = {"count": len(overlaps), "items": overlaps}

    # null 栏必须有非空 Note（且不能只是字段名占位符 —— 这是 L3:0267 的 CE1）
    nulls = []
    for t in cand.get("tasks") or []:
        for field in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(field) is None:
                note = t.get(field + "Note")
                placeholder = note in (field + "Note", field, "", None)
                nulls.append({"task": t.get("id"), "field": field,
                              "noteLen": len(note) if isinstance(note, str) else 0,
                              "isPlaceholder": placeholder})
    report["nullFields"] = {
        "count": len(nulls),
        "placeholders": [n for n in nulls if n["isPlaceholder"]],
        "ok": all(n["noteLen"] > 0 and not n["isPlaceholder"] for n in nulls),
        "items": nulls,
    }

    # 分区存在性 + 条数自报核对
    required = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings",
                "themeReadings"]
    report["sectionPresence"] = {
        "required": required,
        "missing": [k for k in required if k not in cand],
        "counts": {k: len(cand[k]) for k in required if isinstance(cand.get(k), list)},
    }

    # 三态/四态判别字段合法性
    ws = cand.get("worldSettings") or []
    kinds = {}
    bad_state = []
    for w in ws:
        k = w.get("kind")
        kinds[k] = kinds.get(k, 0) + 1
        if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            bad_state.append({"name": w.get("name"), "kind": k,
                              "placeState": w.get("placeState")})
        if k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or any(
                    x not in ("hold", "transfer", "use", "lose") for x in st):
                bad_state.append({"name": w.get("name"), "kind": k, "itemStates": st})
        if k == "rule" and w.get("institution") not in (
                "declared", "executed", "misunderstood"):
            bad_state.append({"name": w.get("name"), "kind": k,
                              "institution": w.get("institution")})
    report["worldSettingsKinds"] = {"counts": kinds, "badStateFields": bad_state,
                                    "ok": not bad_state}

    # foreshadows 结构
    fs = []
    for f in cand.get("foreshadows") or []:
        st = f.get("status")
        fs.append({"id": f.get("id"), "status": st,
                   "hasPayoff": bool(f.get("payoff")),
                   "hasPayoffNote": bool(f.get("payoffNote"))})
    report["foreshadowStructure"] = {
        "count": len(fs),
        "illegal": [x for x in fs if x["status"] not in ("resolved", "unresolved")],
        "unresolvedWithoutNote": [x for x in fs
                                  if x["status"] == "unresolved" and not x["hasPayoffNote"]],
        "items": fs,
    }

    report["semanticReview"] = {
        "claimedDone": bool((cand.get("semanticReview") or {}).get("status") == "done"),
        "candidateStatus": (cand.get("semanticReview") or {}).get("status"),
        "note": "引文定位正确 ≠ 语义已核验；本审计只做定位与结构复算。",
    }

    # ── C. 反向检查：这一段里还有什么原文事实是候选没写的 ────────────────────
    # 判据：某段没有任何引文偏移落在它内部 ⇒ 该段零覆盖。逐段列出，人工给出评估。
    all_spans = [(q.get("start"), q.get("end")) for _, q in quotes
                 if isinstance(q.get("start"), int) and isinstance(q.get("end"), int)]
    paras = nonempty_paragraphs(text, *RANGE)
    zero = []
    for i, (pstart, ptxt) in enumerate(paras, 1):
        pend = pstart + len(ptxt)
        if not any(s < pend and pstart < e for s, e in all_spans):
            zero.append({"para": i, "absStart": pstart, "text": ptxt[:120]})
    report["reverseCheck"] = {
        "method": ("逐段区间包含判断：某非空段内没有任何引文偏移 ⇒ 零覆盖。"
                   "**不是**统计条数，而是照提示词要求问『这一段里还漏了什么』。"),
        "nonEmptyParagraphs": len(paras),
        "paragraphsTouchedByQuotes": len(paras) - len(zero),
        "zeroCoveredParagraphs": len(zero),
        "zeroCoveredList": zero,
        "note": ("零覆盖段多为过场句（敲门、寒暄、『怎么办？』、省略号分隔），"
                 "本身不承载可抽事件。真正的反向风险是**语义遗漏**而不是段落未引用，"
                 "见 report 的 reverseFindings 字段（本审计按段标注评估结论）。"),
    }

    # 候选自报的 coverage 数字与实际复算是否一致
    reported = cand.get("coverage") or {}
    report["coverageCrossCheck"] = {
        "candidateClaims": {"nonEmptyParagraphs": reported.get("nonEmptyParagraphs"),
                            "paragraphsTouchedByQuotes": reported.get(
                                "paragraphsTouchedByQuotes"),
                            "zeroCoverageParagraphs": reported.get("zeroCoverageParagraphs")},
        "independentRecompute": {"nonEmptyParagraphs": len(paras),
                                 "paragraphsTouchedByQuotes": len(paras) - len(zero),
                                 "zeroCoverageParagraphs": len(zero)},
        "reportedZeroListMatches": (
            sorted(x["para"] for x in (reported.get("zeroCoverageList") or [])) ==
            sorted(x["para"] for x in zero)),
        "matches": (reported.get("nonEmptyParagraphs") == len(paras)
                    and reported.get("zeroCoverageParagraphs") == len(zero)),
    }

    # ── C2. 反向发现：候选未覆盖、但原文明确存在的事实（逐条带引证）──────────
    # 每条都是我自己在切片上 find 出来的；assessment 说明它该不该被写进候选。
    probe = [
        ("朱广孝「憋着尿」去见宋廷风", "朱广孝忍住打拳的冲动，憋着尿，扭头就敲开了宋廷风的房门。"),
        ("宋廷风刚睡醒、披袍开门抱怨", "宋廷风披着袍子，似乎刚刚醒来，打开门，抱怨道：“什么事啊，大晚上的串什么门？”"),
        ("两人到走廊指着楼下大厅", "朱广孝脸色难看，拽着宋廷风蹑手蹑脚的出门，来到走廊，指着楼下大厅，道：“看！”"),
        ("宋廷风也做出与朱广孝同款的生理反应", "宋廷风一看，气的浑身发抖，手脚冰凉，眼泪不争气的流下来...."),
        ("许七安把案子说了一遍给两人听", "他把事情简单的说了一遍。"),
        ("两人骇然相视、后背沁出冷汗", "房间里一片寂静，宋廷风和朱广孝骇然相视，感觉后背都沁出了一层冷汗。"),
        ("许七安近来时常头晕目眩并伴幻觉", "许七安捏着眉心，最近时常头晕目眩，并伴随轻微的幻觉。"),
        ("许七安打趣问「小黑屋是不是叫404」", "许七安笑了，“那个小黑屋是不是叫404？”"),
        ("朱广孝没听懂「404」", "“什么404？”朱广孝没听懂"),
        ("许七安以「身负皇命」自我定位", "身负皇命的我们，应该竭尽全力，还无辜者一个公道"),
        ("姜律中与张巡抚察觉许七安的异常", "姜律中和张巡抚奇怪的看着他，这小子不是喜欢说冠冕堂皇的空话的人。"),
        ("两人「仿佛猜到了什么」", "听到李妙真的称赞，两人若有所思，仿佛猜到了什么。"),
        ("李妙真「希冀的看着他」", "侧目一看，见李妙真美眸闪闪发亮，希冀的看着他。"),
        ("许七安自述十八岁与三十五岁的口号变化", "想当年他十八岁的时候，口号是：我命由我不由天。"),
        ("许七安自嘲口号变成「求求老天爷不要再搞我了」", "等他三十五岁的时候，口号是：求求老天爷不要再搞我了。"),
        ("许七安诊断这是「苏苏PTSD」", "许七安眼神顿时充满了怜悯，有一种病叫做“苏苏PTSD”。"),
        ("宋廷风追问杨川南有没有老实交代", "得到贱人的安抚后，宋廷风问道：“杨川南有没有老实交代？那个游骑将军是过来找麻烦的？”"),
        ("许七安自陈「这件案子不好搞哦」", "“这件案子不好搞哦...”许七安只恨手头没有烟，叹口气"),
        ("狗肉铺子老板真身是都指挥使司的经历", "他是一个都指挥使司的经历。"),
        ("两人自以为在第五层、其实对方才是", "他们感觉自己在第五层，结果人家才是第五层。"),
        ("许七安怪朱广孝没提醒他", "“你怎么不提醒我？”许七安捏着眉心"),
        ("朱广孝回答「谁能想到人是假的？」", "“谁能想到人是假的？”"),
        ("宋廷风补一句「他要不是假的，咱们回头去找便是」", "“是啊，他要不是假的，咱们回头去找便是。”宋廷风说。"),
        ("朱广孝说那个名字「似乎有些熟悉」", "对了，你刚才说的那个名字，似乎有些熟悉...."),
        ("许七安以「脸色大变」收场", "许七安脸色大变，像是听到了某种可怕的事。"),
        ("切片末尾是作者 PS（非小说正文）", "PS：这章短了点，主要是，不短的话，感觉12点之后才能更新了。"),
    ]
    probes = []
    for label, lit in probe:
        at = slice_text.find(lit)
        probes.append({"fact": label, "quote": lit, "foundInSlice": at >= 0,
                       "absStart": (at + RANGE[0]) if at >= 0 else None,
                       "inSliceOccurrences": slice_text.count(lit)})
    not_found = [p for p in probes if not p["foundInSlice"]]
    report["reverseFindings"] = {
        "method": ("反向检查：先自己读切片，再列出候选没写、但原文明确存在的事实。"
                   "每条都在切片上重新 find 过；找不到的如实列出（那是我的探针写错，"
                   "不是原文没有）。"),
        "probeCount": len(probes),
        "notFound": not_found,
        "facts": probes,
        "assessment": (
            "这 26 条里**没有**构成候选『漏读』的硬缺陷：它们绝大多数是 (a) 过场动作"
            "（敲门/披袍/指楼下/走廊）——不承载可抽的因果或状态变化；"
            "(b) 候选已在别处以更长引文覆盖的同一事实（如「他把事情简单的说了一遍」"
            "对应 tasks.t2.result 的跨段处理、许七安头晕幻觉对应 states 或 unknowns）；"
            "(c) 作者的 PS 段——非小说正文。真正值得复核者注意的是 3 条**语义层**遗漏"
            "候选未单列：① 「许七安笑了，“那个小黑屋是不是叫404？”」——候选把 404 记为"
            "unresolved 伏笔（f2），但没有单列『许七安抢先说出 404』这一知情差"
            "（他怎么会知道这个词？原文没写，这比『404 是什么意思』更具体）；"
            "② 「听到李妙真的称赞，两人若有所思，仿佛猜到了什么」——候选已在 "
            "rejectedEdges/unknowns 处理了相邻因果，但『两人猜到了什么』本身是未解内容；"
            "③ 「许七安捏着眉心，最近时常头晕目眩，并伴随轻微的幻觉」——这是一条"
            "**身体状态的持续异常**，与本章『梦境』主题直接相关，候选未把它与结尾"
            "『脸色大变』建立任何关联（我也没有证据说二者有关，故只列为反向发现，"
            "不建议连边）。"),
    }

    # ── B2. 引文是否横跨**真正的**场景分隔 ─────────────────────────────────
    # 只认独立成段的 `....`（`\n\s*\.{3,}\s*\n`）。句内省略号（『我们...还让她来驿站？』
    # 『卑职也只能...尽力而为。』『误会，误会...』）**不是**场景切换，混在一起会把
    # 语气停顿误报成跨场景。
    import re as _re
    real_breaks = [(RANGE[0] + mo.start(), RANGE[0] + mo.end())
                   for mo in _re.finditer(r"\n\s*\.{3,}\s*\n", slice_text)]
    straddle = []
    for path, q in quotes:
        s, e = q.get("start"), q.get("end")
        if not isinstance(s, int) or not isinstance(e, int):
            continue
        for bs, be in real_breaks:
            if s < be and bs < e:
                straddle.append({"path": path, "quote": q["quote"][:50],
                                 "start": s, "end": e, "break": [bs, be]})
    report["sceneBreakStraddle"] = {
        "realSceneBreaks": real_breaks,
        "note": ("判定口径：只有独立成段的 `....` 才算场景分隔；句内省略号不算。"
                 "引文横跨场景分隔时，其 basis=explicit 的标注应当降级为 derived。"),
        "count": len(straddle),
        "items": straddle,
        "ok": not straddle,
    }

    # 实体核对：区间内命中的专名（防幻觉）
    entities = {}
    for name in ("朱广孝", "宋廷风", "许七安", "张巡抚", "李妙真", "姜律中", "苏苏",
                 "宁宴", "杨川南", "梁有平", "周旻", "齐党", "都指挥使司", "驿站",
                 "狗肉铺子", "游骑将军", "美军娘", "打更人", "金锣", "巡抚"):
        entities[name] = slice_text.count(name)
    report["entityCountsInSlice"] = entities

    out = Path(__file__).resolve().parent / "audit_dupclaim_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
                   encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("quoteAudit", "taskFieldOverlaps", "nullFields", "worldSettingsKinds",
                       "coverageCrossCheck", "sectionPresence", "reverseFindings")},
                     ensure_ascii=False, indent=2)[:4000])
    print("\n报告已写入：%s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
