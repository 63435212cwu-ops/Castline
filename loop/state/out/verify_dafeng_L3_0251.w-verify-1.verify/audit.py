#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify:dafeng:L3:0251 的独立复核脚本（复核者 w-verify-1 自写）。

纪律：
  * 不 import 候选的 build_candidate.py / verify_candidate.py / content_*.py；
  * 不读候选的任何中间变量，只读最终候选 JSON 与原文 docs.json；
  * 自己重切段落、自己 find 偏移、自己算覆盖。

用法：python3 -B -s <此文件> [--json 输出路径]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0251.candidate.json"
SRC_RANGE = (1032194, 1038254)
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

problems: list[str] = []
report: dict = {}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def walk_quotes(node, path="$"):
    """产出候选里**所有**带 quote/start/end 的对象（含嵌套）。"""
    if isinstance(node, dict):
        if "quote" in node and isinstance(node["quote"], str) and "start" in node:
            yield path, node
        for k, v in node.items():
            yield from walk_quotes(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quotes(v, "%s[%d]" % (path, i))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()

    text = json.loads(DOCS.read_text("utf-8"))[0]["text"]
    cand = json.loads(CAND.read_text("utf-8"))
    start, end = SRC_RANGE
    sl = text[start:end]

    report["sourceFileSha256"] = sha256_file(DOCS)
    report["candidateSha256"] = sha256_file(CAND)
    report["sliceCodepoints"] = len(sl)
    report["sliceSha256"] = hashlib.sha256(sl.encode()).hexdigest()
    if report["sourceFileSha256"] != SRC_HASH:
        problems.append("源文件哈希与 task.sourceHash 不符")
    if not sl.startswith(cand["source"]["boundaryHead"]):
        problems.append("切片不以 unitHead 开头")

    # ── ① 引文层：逐条 text[start:end]==quote / find / 哈希 / 区间内次数 ────
    qs = list(walk_quotes(cand))
    report["quoteObjects"] = len(qs)
    bad_slice = bad_range = bad_hash = bad_find = 0
    nonunique = []
    for path, q in qs:
        s, e = q["start"], q["end"]
        if not (start <= s < e <= end):
            bad_range += 1
            problems.append("越界 %s" % path)
            continue
        if text[s:e] != q["quote"]:
            bad_slice += 1
            problems.append("切片≠引文 %s" % path)
        if q.get("sourceHash") != SRC_HASH:
            bad_hash += 1
            problems.append("哈希不符 %s" % path)
        f = text.find(q["quote"])
        if f != s:
            bad_find += 1
        # 区间内出现次数独立复算
        cnt = sl.count(q["quote"])
        if q.get("occurrencesInRange") is not None and q["occurrencesInRange"] != cnt:
            problems.append("区间内次数不符 %s：声明 %s 实测 %d"
                            % (path, q["occurrencesInRange"], cnt))
        tot = text.count(q["quote"])
        if q.get("wholeTextOccurrences") is not None and q["wholeTextOccurrences"] != tot:
            problems.append("全文次数不符 %s：声明 %s 实测 %d"
                            % (path, q["wholeTextOccurrences"], tot))
        if tot > 1:
            nonunique.append({"path": path, "n": tot, "declared": q.get("startIsFirstOccurrence"),
                              "firstAt": q.get("firstOccurrenceAt"),
                              "firstOk": (q.get("firstOccurrenceAt") is not None
                                          and text[q["firstOccurrenceAt"]:
                                                   q["firstOccurrenceAt"] + len(q["quote"])] == q["quote"])})
    report["quoteLayer"] = {"sliceMismatch": bad_slice, "outOfRange": bad_range,
                            "hashMismatch": bad_hash, "findNeStart": bad_find,
                            "nonUniqueStrings": len(nonunique), "nonUnique": nonunique}

    # ── ② 段落表独立重建（正则另写），核对 declaredPara ────────────────────
    paras = []          # (idx1based, abspos, raw)
    for m in re.finditer(r"[^\n]+", sl):
        raw = m.group(0)
        if not raw.strip():
            continue
        paras.append((len(paras) + 1, start + m.start(), raw))
    report["nonEmptyParagraphs"] = len(paras)
    if len(paras) != cand["source"]["nonEmptyParagraphs"]:
        problems.append("非空段数不符：候选 %s 实测 %d"
                        % (cand["source"]["nonEmptyParagraphs"], len(paras)))
    para_bad = 0
    for path, q in qs:
        dp = q.get("declaredPara")
        if dp is None:
            continue
        hit = [p for p, (i, a, r) in enumerate(paras) if a <= q["start"] < a + len(r)]
        if not hit or paras[hit[0]][0] != dp:
            para_bad += 1
            problems.append("declaredPara 不符 %s：声明 %s" % (path, dp))
    report["declaredParaMismatch"] = para_bad

    # ── ③ 五栏独立性：tasks 五栏 + 各栏 quotes 字符区间两两求交 ─────────────
    fields = ("objective", "obstacle", "action", "result", "cost")
    overlap = 0
    shared_strings = 0
    for ti, t in enumerate(cand["tasks"]):
        ivs = {}
        for f in fields:
            ivs[f] = [(q["start"], q["end"]) for q in (t.get(f + "Quotes") or [])]
        for i, fa in enumerate(fields):
            for fb in fields[i + 1:]:
                for (a1, b1) in ivs[fa]:
                    for (a2, b2) in ivs[fb]:
                        if a1 < b2 and a2 < b1:
                            overlap += 1
                            problems.append("五栏区间重叠 tasks[%d] %s×%s" % (ti, fa, fb))
        # 跨栏共用同一句（同一 quote 字符串）
        for i, fa in enumerate(fields):
            for fb in fields[i + 1:]:
                sa = {q["quote"] for q in (t.get(fa + "Quotes") or [])}
                sb = {q["quote"] for q in (t.get(fb + "Quotes") or [])}
                if sa & sb:
                    shared_strings += 1
    report["taskFieldIntervalOverlap"] = overlap
    report["taskFieldSharedStrings"] = shared_strings

    # ── ④ coverage 独立复算（区间并集）────────────────────────────────────
    ivs = sorted({(q["start"], q["end"]) for _, q in qs if start <= q["start"] < q["end"] <= end})
    merged = []
    for a, b in ivs:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    union = sum(b - a for a, b in merged)
    nonspace = sum(1 for ch in sl if not ch.isspace())
    # 口径说明（我自己踩过）：候选 coverage.quoteIntervals=278 = **引文对象个数**，
    # 不是去重后的区间个数（我去重后 191）。第一版拿 191 去比 278 报了假问题，
    # 已在输出里把三个数分开列，避免「口径不同 = 缺陷」这种误判。
    report["coverage"] = {
        "quoteObjectCount": len(qs), "uniqueIntervalCount": len(ivs),
        "unionCodepoints": union,
        "sliceCodepoints": len(sl), "nonSpaceCodepoints": nonspace,
        "ratioSlice": round(union / len(sl), 4),
        "ratioNonSpace": round(union / nonspace, 4),
        "declared": {k: cand["coverage"].get(k) for k in
                     ("quoteUnionCodepoints", "nonSpaceCodepoints", "quoteIntervals",
                      "quoteUnionRatioOfSlice", "quoteUnionRatioOfNonSpace")},
    }
    if union != cand["coverage"]["quoteUnionCodepoints"]:
        problems.append("coverage 并集码点数不符：候选 %s 实测 %d"
                        % (cand["coverage"]["quoteUnionCodepoints"], union))
    if nonspace != cand["coverage"]["nonSpaceCodepoints"]:
        problems.append("非空格码点数不符：候选 %s 实测 %d"
                        % (cand["coverage"]["nonSpaceCodepoints"], nonspace))
    if len(qs) != cand["coverage"]["quoteIntervals"]:
        problems.append("quoteIntervals（引文对象个数）不符：候选 %s 实测 %d"
                        % (cand["coverage"]["quoteIntervals"], len(qs)))

    # 段落级零覆盖（独立复算）
    zero = []
    for i, a, r in paras:
        if not any(a < b and c < a + len(r) for c, b in merged):
            zero.append(i)
    report["zeroCoveredParagraphs"] = {"mine": zero, "declared": cand["coverage"]["zeroCoveredParagraphs"]}
    if zero != cand["coverage"]["zeroCoveredParagraphs"]:
        problems.append("zeroCoveredParagraphs 不符：候选 %s 实测 %s"
                        % (cand["coverage"]["zeroCoveredParagraphs"], zero))

    # ── ⑤ **句子级**零覆盖（反向验证用；候选只做段落级）────────────────────
    sent_zero = []
    for i, a, r in paras:
        for sm in re.finditer(r"[^。！？]*[。！？]", r):
            s_ = sm.group(0)
            core = s_.strip()
            if len(re.sub(r"\s", "", core)) < 12:
                continue
            gs, ge = a + sm.start(), a + sm.end()
            if any(gs < b and c < ge for c, b in merged):
                continue
            sent_zero.append({"para": i, "start": gs, "end": ge, "text": core})
    report["sentenceLevelZeroCovered"] = {"count": len(sent_zero), "items": sent_zero}

    # ── ⑥ 内部 id 交叉引用（零填充 + 单数字两种写法都扫）─────────────────
    ids = set()
    for sec in ("worldSettings", "tasks", "causeEdges", "rejectedEdges", "states",
                "knowledgeGaps", "foreshadows", "notForeshadows", "notWorldSettings",
                "themeReadings", "unknowns", "textualNotes", "selfCritique",
                "speechAsClueNotFact"):
        for e in cand.get(sec) or []:
            if isinstance(e, dict) and e.get("id"):
                ids.add(e["id"])
    blob = json.dumps(cand, ensure_ascii=False)
    refs = sorted(set(re.findall(r"\b([A-Z]{1,3}\d{1,2})\b", blob)))
    padded = {i for i in ids}
    dangling = []
    for r in refs:
        if r in padded:
            continue
        m = re.fullmatch(r"([A-Z]{1,3})0*(\d{1,2})", r)
        guess = "%s%02d" % (m.group(1), int(m.group(2))) if m else None
        dangling.append({"ref": r, "zeroPaddedGuess": guess,
                         "resolvesTo": guess if guess in padded else None})
    report["idRefs"] = {"defined": sorted(ids), "referenced": refs, "dangling": dangling}

    # ── ⑦ 「标签字段」引文必须能在原文命中（防自造标签）──────────────────
    label_bad = []
    for path, q in qs:
        if not q.get("quote"):
            continue
        if text.find(q["quote"]) < 0:
            label_bad.append(path)
    report["quotesNotInSource"] = label_bad

    # ── ⑧ 幻觉扫描：候选自由文本里的实体名是否出现在原文 ──────────────────
    # 只看**不在引文里**的自由文本，扫人名样式（连续 2-4 个 CJK 且带姓氏特征）过于粗糙，
    # 改为：对候选里出现的《》「」外的专名候选做「原文含否」检查。
    prose = []
    def collect_prose(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("quote", "quotes", "sourceHash"):
                    continue
                collect_prose(v)
        elif isinstance(node, list):
            for v in node:
                collect_prose(v)
        elif isinstance(node, str):
            prose.append(node)
    collect_prose(cand)
    free = "\n".join(prose)
    report["freeTextChars"] = len(free)
    # 已知实体词表（我自读原文时记下的），检查候选是否编造
    entities = ["许七安", "怀庆", "国舅", "皇后", "黄小柔", "元景帝", "魏渊", "上官青",
                "荷儿", "小宦官", "四皇子", "太子", "福妃", "上官皇后", "长公主",
                "上官家", "魏家", "凤栖宫", "打更人", "教坊司", "御药房", "东宫",
                "冰窖", "国舅府", "上官氏祖宅", "小母马", "佩刀", "黄绸料子",
                "望气术", "福尔摩斯", "华生", "元景", "太子", "殿下", "本宫"]
    ent_report = {}
    for e in entities:
        ent_report[e] = {"inSource": text.count(e), "inCandidateFreeText": free.count(e)}
    report["entityScan"] = ent_report
    for e, d in ent_report.items():
        if d["inSource"] == 0 and d["inCandidateFreeText"] > 0:
            problems.append("候选自由文本出现原文没有的实体：%s（%d 次）"
                            % (e, d["inCandidateFreeText"]))

    report["problems"] = problems
    report["ok"] = not problems
    out = json.dumps(report, ensure_ascii=False, indent=1)
    if args.json:
        Path(args.json).write_text(out, "utf-8")
    print(out if not args.json else "written %s" % args.json)
    print("\nPROBLEMS: %d" % len(problems), file=sys.stderr)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
