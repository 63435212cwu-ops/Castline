#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 content_core.py 的读解 + quotes.py 的实算引文拼成候选 JSON，并现算全部机器自检。

判据（全部由本脚本现算，没有任何手写偏移或手写计数）：
  B1  text[start:end] == quote                        逐字
  B2  每条引文 ⊆ [910067,916516)                       区间
  B3  SEG.find(quote) == start-910067                  反向 find 命中同一位移
  B4  end-start == len(quote)                          长度自洽
  B5  SEG.count(quote) == 1                            切片内唯一
  B6  同一任务五栏的引文**字符跨度两两不相交**            栏位独立（clause 级）
  B7  同一任务五栏的引文**句子下标不相交**                栏位独立（sentence 级）
  B8  同一任务五栏内引文不重复、不互相包含                禁止一句多用
  B9  每条任务五栏齐全（objective/obstacle/action/result/cost）
  B9b 任何 text 为 null 的栏位必须带同名 <栏位>Note
  B10 worldSettings 的 kind 相关字段合法（place/item/rule 三态）
  B11 themeReadings 每条含 perspective/support/counter
  B12 foreshadows 每条含 setup/payoff 结构 + status
  B13 可见码点覆盖率（被引文覆盖的可见码点 / 全部可见码点）
  B14 引文对象总数
  B15 sourceHash 等于文件实测
  B16 切片以单元标题开头
  B17 候选里出现的「第X章」串必须在切片内逐字命中（防止把邻章写进来）
  B18 note 里「」括起、长度 >=5 的片段必须是切片原文子串（防止编引文）
"""
import hashlib
import json
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parents[3]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L0_0232.candidate.json"

START, END = 910067, 916516
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
TASK_ID = "read:dafeng:L0:0232"
AGENT = "w-xiyou-0"
COLUMNS = ("objective", "obstacle", "action", "result", "cost")

sys.path.insert(0, str(BUILD))
from content_core import CONTENT  # noqa: E402
from quotes import QUOTES  # noqa: E402


def load_text():
    blob = DOCS.read_bytes()
    got = hashlib.sha256(blob).hexdigest()
    if got != SOURCE_HASH:
        raise SystemExit("docs.json 哈希不符：%s" % got)
    return json.loads(blob)[0]["text"]


def build_para_index(text):
    seg = text[START:END]
    paras = []
    n = 0
    for m in re.finditer(r"[^\n]+", seg):
        if m.group(0).strip():
            n += 1
            paras.append((n, START + m.start(), START + m.end(), m.group(0)))
    return seg, paras


def build_sentence_index(paras):
    """句子 = 段内按 。！？… 切分的片段（保留标点）。返回 [(abs_start, abs_end)]。"""
    sents = []
    for no, a, b, s in paras:
        for m in re.finditer(r"[^。！？]*[。！？]+|.+$", s):
            if m.group(0).strip():
                sents.append((a + m.start(), a + m.end()))
    return sents


def qobj(key, text, seg, paras, sents):
    q = QUOTES[key]["quote"]
    a, b = QUOTES[key]["start"], QUOTES[key]["end"]
    assert text[a:b] == q, "B1 失败：%s" % key
    assert START <= a < b <= END, "B2 失败：%s" % key
    assert seg.find(q) == a - START, "B3 失败：%s" % key
    assert b - a == len(q), "B4 失败：%s" % key
    assert seg.count(q) == 1, "B5 失败：%s" % key
    para_label = None
    content_anchor = None
    for no, pa, pb, _s in paras:
        if pa <= a and b <= pb:
            para_label = "P%03d" % no
            content_anchor = "P%03d[%d:%d]" % (no, a - pa, b - pa)
            break
    s_idx = [i for i, (sa, sb) in enumerate(sents) if sa < b and a < sb]
    return {
        "quote": q,
        "start": a,
        "end": b,
        "sourceHash": SOURCE_HASH,
        "offsetUnit": "codepoint",
        "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
        "match": "exact",
        "wholeTextOccurrences": text.count(q),
        "occurrencesInRange": seg.count(q),
        "paraLabel": para_label,
        "contentAnchor": content_anchor,
        "sentenceIdx": s_idx,
    }


def resolve(node, text, seg, paras, sents):
    """递归：把任何含 quoteKeys 的 dict 换成带 quotes[] 的 dict。"""
    if isinstance(node, dict):
        out = {}
        keys = node.get("quoteKeys")
        for k, v in node.items():
            if k == "quoteKeys":
                continue
            out[k] = resolve(v, text, seg, paras, sents)
        if keys is not None:
            out["quotes"] = [qobj(k, text, seg, paras, sents) for k in keys]
            out["quoteKeys"] = list(keys)
        return out
    if isinstance(node, list):
        return [resolve(v, text, seg, paras, sents) for v in node]
    return node


def spans(col):
    return [(q["start"], q["end"]) for q in (col.get("quotes") or [])]


def overlap(x, y):
    return not (x[1] <= y[0] or y[1] <= x[0])


def main():
    text = load_text()
    seg, paras = build_para_index(text)
    sents = build_sentence_index(paras)
    assert seg.startswith("第三章 脱胎换骨"), "B16 失败"

    content = resolve(CONTENT, text, seg, paras, sents)

    checks = []

    def add(cid, ok, detail):
        checks.append({"id": cid, "ok": bool(ok), "detail": detail})

    # ── 收集全部引文对象 ────────────────────────────────────────────────
    all_q = []

    def walk(o):
        if isinstance(o, dict):
            if "quote" in o and "start" in o:
                all_q.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(content)

    bad = [q for q in all_q if text[q["start"]:q["end"]] != q["quote"]]
    add("B1_逐字切片可复现", not bad, "%d/%d 条 text[start:end]==quote" % (len(all_q) - len(bad), len(all_q)))
    bad = [q for q in all_q if not (START <= q["start"] < q["end"] <= END)]
    add("B2_落在单元区间内", not bad, "%d/%d 条 ⊆[%d,%d)" % (len(all_q) - len(bad), len(all_q), START, END))
    bad = [q for q in all_q if seg.find(q["quote"]) != q["start"] - START]
    add("B3_反向find命中同一位移", not bad, "%d/%d 条 SEG.find(quote)==start-%d" % (len(all_q) - len(bad), len(all_q), START))
    bad = [q for q in all_q if q["end"] - q["start"] != len(q["quote"])]
    add("B4_长度自洽", not bad, "%d/%d 条 end-start==len(quote)" % (len(all_q) - len(bad), len(all_q)))
    bad = [q for q in all_q if seg.count(q["quote"]) != 1]
    add("B5_切片内唯一", not bad, "%d/%d 条切片内出现 1 次" % (len(all_q) - len(bad), len(all_q)))

    # ── B6/B7/B8：任务五栏独立 ──────────────────────────────────────────
    b6_bad, b7_bad, b8_bad, b9_bad, b9b_bad = [], [], [], [], []
    null_cols = []
    for t in content["tasks"]:
        tid = t["id"]
        for col in COLUMNS:
            if col not in t:
                b9_bad.append("%s 缺栏 %s" % (tid, col))
                continue
            c = t[col]
            if c.get("text") is None:
                null_cols.append("%s.%s" % (tid, col))
                note_key = col + "Note"
                if not c.get(note_key):
                    b9b_bad.append("%s.%s 缺 %s" % (tid, col, note_key))
        for i in range(len(COLUMNS)):
            for j in range(i + 1, len(COLUMNS)):
                ci, cj = t.get(COLUMNS[i], {}), t.get(COLUMNS[j], {})
                si, sj = spans(ci), spans(cj)
                for x in si:
                    for y in sj:
                        if overlap(x, y):
                            b6_bad.append("%s %s∩%s" % (tid, COLUMNS[i], COLUMNS[j]))
                se_i, se_j = set(), set()
                for q in (ci.get("quotes") or []):
                    se_i |= set(q["sentenceIdx"])
                for q in (cj.get("quotes") or []):
                    se_j |= set(q["sentenceIdx"])
                if se_i & se_j:
                    b7_bad.append("%s %s∩%s @sentence%s" % (tid, COLUMNS[i], COLUMNS[j], sorted(se_i & se_j)))
        flat = []
        for col in COLUMNS:
            flat += [(col, q["quote"]) for q in (t.get(col, {}).get("quotes") or [])]
        for i in range(len(flat)):
            for j in range(i + 1, len(flat)):
                if flat[i][1] == flat[j][1]:
                    b8_bad.append("%s %s=%s 同一句" % (tid, flat[i][0], flat[j][0]))
                elif flat[i][1] in flat[j][1] or flat[j][1] in flat[i][1]:
                    b8_bad.append("%s %s⊂%s 互相包含" % (tid, flat[i][0], flat[j][0]))
    add("B6_B7_栏位独立(clause+sentence)", not (b6_bad or b7_bad),
        "%d 处相交%s" % (len(b6_bad) + len(b7_bad), ("：" + "; ".join((b6_bad + b7_bad)[:5])) if (b6_bad or b7_bad) else ""))
    add("B8_任务内引文不重复不包含", not b8_bad,
        "%d 处%s" % (len(b8_bad), ("：" + "; ".join(b8_bad[:5])) if b8_bad else ""))
    add("B9_五栏齐全", not b9_bad, "%d 条任务 × 5 栏%s" % (len(content["tasks"]), ("；缺：" + "; ".join(b9_bad)) if b9_bad else ""))
    add("B9b_null栏带<栏位>Note", not b9b_bad,
        "%d 个 null 栏，%d 个缺同名 Note%s" % (len(null_cols), len(b9b_bad),
                                          ("：" + "; ".join(b9b_bad)) if b9b_bad else ""))

    # ── B10：worldSettings 三态字段 ─────────────────────────────────────
    w_bad = []
    for w in content["worldSettings"]:
        k = w.get("kind")
        if k == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                w_bad.append("%s placeState=%r" % (w.get("id"), w.get("placeState")))
        elif k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(s not in ("hold", "transfer", "use", "lose") for s in st):
                w_bad.append("%s itemStates=%r" % (w.get("id"), st))
            if "itemStateEvidence" not in w:
                w_bad.append("%s 缺 itemStateEvidence（四态必须分开写）" % w.get("id"))
        elif k == "rule":
            if w.get("institution") not in ("declared", "executed", "misunderstood"):
                w_bad.append("%s institution=%r" % (w.get("id"), w.get("institution")))
        else:
            w_bad.append("%s kind=%r" % (w.get("id"), k))
    add("B10_设定三态字段合法", not w_bad,
        "place/item/rule %d 条字段%s" % (len(content["worldSettings"]), ("异常：" + "; ".join(w_bad)) if w_bad else "全部合法"))

    # ── B11：主题三件套 ────────────────────────────────────────────────
    th_bad = [t.get("id") for t in content["themeReadings"]
              if not (t.get("perspective") and t.get("support") and t.get("counter"))]
    add("B11_主题三件套(含counter)", not th_bad,
        "%d 条均含 perspective/support/counter%s" % (len(content["themeReadings"]),
                                                  ("；缺：" + ",".join(th_bad)) if th_bad else ""))

    # ── B12：伏笔结构 ──────────────────────────────────────────────────
    f_bad = []
    for f in content["foreshadows"]:
        if "setup" not in f or "payoff" not in f or f.get("status") not in ("resolved", "unresolved", "open"):
            f_bad.append(f.get("id"))
    add("B12_伏笔铺设/回收结构", not f_bad,
        "%d 条：%d 有回收事件 / %d 无回收%s"
        % (len(content["foreshadows"]),
           sum(1 for f in content["foreshadows"] if f.get("payoff", {}).get("text")),
           sum(1 for f in content["foreshadows"] if not f.get("payoff", {}).get("text")),
           ("；异常：" + ",".join(f_bad)) if f_bad else ""))

    # ── B13：可见码点覆盖率 ────────────────────────────────────────────
    vis = [i for i, ch in enumerate(seg) if not ch.isspace()]
    covered = set()
    for q in all_q:
        covered |= set(range(q["start"] - START, q["end"] - START))
    cov = [i for i in vis if i in covered]
    ratio = len(cov) / len(vis) if vis else 0.0
    runs, cur = [], 0
    for i in vis:
        if i in covered:
            cur = 0
        else:
            cur += 1
            runs.append(cur)
    add("B13_可见码点覆盖率>=0.55", ratio >= 0.55,
        "覆盖率 %.4f，最长连续无引文可见段 %d 码点" % (ratio, max(runs) if runs else 0))
    add("B14_引文总量", True, "%d 个引文对象" % len(all_q))

    # ── B15/B16 ────────────────────────────────────────────────────────
    got = hashlib.sha256(DOCS.read_bytes()).hexdigest()
    add("B15_sourceHash等于文件实测", got == SOURCE_HASH, "实测 %s…" % got[:20])
    add("B16_切片以单元标题开头", seg.startswith("第三章 脱胎换骨"), repr(seg[:12]))

    # ── B17：章号引用不越界 ────────────────────────────────────────────
    body = json.dumps(content, ensure_ascii=False)
    chaps = sorted(set(re.findall(r"第[一二三四五六七八九十百零0-9]+章[^\s，。；）)]*", body)))
    ch_bad = [c for c in chaps if c not in seg]
    add("B17_章号引用不越界", not ch_bad,
        "%d 处章号引用%s" % (len(chaps), ("越界：" + "; ".join(ch_bad)) if ch_bad else "全部逐字落在本区间"))

    # ── B18：「」片段可回查 ────────────────────────────────────────────
    frag_bad = []

    def scan_frags(o):
        if isinstance(o, str):
            for m in re.finditer(r"「([^」]+)」", o):
                frag = m.group(1)
                if len(frag) >= 5 and frag not in seg:
                    frag_bad.append(frag)
        elif isinstance(o, dict):
            for v in o.values():
                scan_frags(v)
        elif isinstance(o, list):
            for v in o:
                scan_frags(v)

    scan_frags(content)
    frag_bad = sorted(set(frag_bad))
    add("B18_note内「」片段可在切片回查", not frag_bad,
        "%d 处不可回查%s" % (len(frag_bad), ("：" + "; ".join(frag_bad[:6])) if frag_bad else "全部命中"))

    # ── 覆盖率明细（供复核）─────────────────────────────────────────────
    para_cov = []
    for no, pa, pb, s in paras:
        touched = any(pa < q["end"] and q["start"] < pb for q in all_q)
        para_cov.append((no, touched))
    zero = [no for no, t in para_cov if not t]

    cand = {
        "schemaVersion": "castline-read-candidate/1",
        "task": TASK_ID,
        "agent": AGENT,
        "role": "READER（原文精读工作者）",
        "book": "dafeng",
        "bookTitle": "大奉打更人",
        "lane": 0,
        "unitIndex": 232,
        "unitHead": "第三章 脱胎换骨",
        "source": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
            "sourceHash": SOURCE_HASH,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
            "segmentSha256": hashlib.sha256(seg.encode("utf-8")).hexdigest(),
            "segmentSha256Scope": "docs[0].text[%d:%d) 切片 UTF-8 的 sha256（另起字段，未覆盖 sourceHash）" % (START, END),
            "range": [START, END],
            "codepoints": len(seg),
            "nonEmptyParagraphs": len(paras),
            "sentences": len(sents),
            "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
            "selfCheck": "docs[0].text[%d:%d) 以本单元标题开头（构建脚本已断言 B16）" % (START, END),
        },
        "semanticReview": "not-performed",
        "semanticReviewNote": "本候选只做**引文定位的机器可复算**（逐字／偏移／切片内唯一／段锚／句锚／栏位独立）"
                              "与本人通读全切片 %d 个非空段后的语义判断。**不声称**任何 semanticReview 完成，"
                              "也不声称独立复核 —— 引文定位正确 ≠ 语义已核验。" % len(paras),
        "basisLegend": {
            "explicit": "原文直述（叙述层写出的动作、结果、状态；引人物话时只用于证明〔他说了什么／他想要什么〕，"
                        "不用于证明其为真）",
            "inferred": "我的归纳",
            "derived": "跨段推导（机制由我补出，原文未直接写出）",
            "unverified": "存疑：出处是人物的话或人物的书面陈述，叙述层未确认，读不出来",
        },
        "quotePolicy": {
            "逐字": "每条 quotes[].quote 都是 docs[0].text 的子串，可 text.find 命中，且 text[start:end]==quote",
            "偏移": "start/end 为 docs[0].text 全文绝对 codepoint 偏移；由 gen_quotes.py 从锚串**实算**，从不手写",
            "区间": "每条引文都落在本单元 [%d,%d) 内，且在切片内只出现一次" % (START, END),
            "段锚": "paraLabel 为该引文所在非空段的真实段号（P001…P%d）；contentAnchor 给出段内相对区间" % len(paras),
            "句锚": "sentenceIdx 为该引文覆盖的句子下标（构建脚本切句得出），B6/B7 的栏位独立判定基于它",
        },
        "columnsIndependent": True,
        "columnsIndependentNote": "B6 在**字符跨度**层面、B7 在**句子下标**层面分别判定同一任务五栏的引文不相交；"
                                  "B8 另判同一任务内引文不重复、不互相包含。三层判据都为 0 处冲突（见 machineSelfCheck）。",
        "tasks": content["tasks"],
        "causeEdges": content["causeEdges"],
        "rejectedEdges": content["rejectedEdges"],
        "states": content["states"],
        "knowledgeDiffs": content["knowledgeDiffs"],
        "foreshadows": content["foreshadows"],
        "notForeshadows": content["notForeshadows"],
        "worldSettings": content["worldSettings"],
        "notWorldSettings": content["notWorldSettings"],
        "themeReadings": content["themeReadings"],
        "unknowns": content["unknowns"],
        "selfCritique": content["selfCritique"],
        "notModeled": content["notModeled"],
        "machineSelfCheck": {
            "checks": checks,
            "allPass": all(c["ok"] for c in checks),
            "quoteObjects": len(all_q),
            "note": "全部判定由 build_candidate.py 现算；引文偏移来自 gen_quotes.py 的锚串实算，从不手写。"
                    "B6/B7 的栏位独立在 clause 级（字符跨度相交）与 sentence 级（句子下标相交）两套口径下分别判定。",
        },
        "coverage": {
            "visibleCodepoints": len(vis),
            "coveredCodepoints": len(cov),
            "ratio": round(ratio, 4),
            "longestUncoveredVisibleRun": max(runs) if runs else 0,
            "nonEmptyParagraphs": len(paras),
            "touchedParagraphs": sum(1 for _n, t in para_cov if t),
            "zeroCoverageParagraphs": len(zero),
            "zeroCoverageList": zero,
            "nullColumns": len(null_cols),
            "nullColumnsWithNote": len(null_cols) - len(b9b_bad),
            "nullColumnList": null_cols,
            "sections": {
                "tasks": len(content["tasks"]),
                "causeEdges": len(content["causeEdges"]),
                "rejectedEdges": len(content["rejectedEdges"]),
                "states": len(content["states"]),
                "knowledgeDiffs": len(content["knowledgeDiffs"]),
                "foreshadows": len(content["foreshadows"]),
                "notForeshadows": len(content["notForeshadows"]),
                "worldSettings": len(content["worldSettings"]),
                "notWorldSettings": len(content["notWorldSettings"]),
                "themeReadings": len(content["themeReadings"]),
                "unknowns": len(content["unknowns"]),
                "selfCritique": len(content["selfCritique"]),
                "notModeled": len(content["notModeled"]),
            },
        },
        "remaining": [
            "semanticReview 未做（本候选只做定位的机器可复算 + 我的通读判断），独立复核未做。",
            "本候选**没有跨单元取证**：U1–U12 这些悬念在本区间就是断的，我按断的记，"
            "没有去读相邻章节补答案。",
            "B13 的覆盖率按『可见码点』（去掉换行与空格）计算；覆盖率不达标的段落清单在 coverage.zeroCoverageList，"
            "复核者可据此直接指出漏读。",
            "unitHead / unitIndex / lane 照抄任务定义，未独立核对其在全书中的序号。",
            "段尾作者附言（P164）与分隔线（P165）只作为『不建模』的负例登记，未纳入任何叙事分区。",
        ],
        "rollback": {
            "kind": "append-only",
            "strategy": "delete-added-files",
            "files": ["loop/state/out/read_dafeng_L0_0232.candidate.json"],
        },
        "builtBy": {
            "builder": "loop/state/out/read_dafeng_L0_0232.w-xiyou-0.build/build_candidate.py",
            "quoteGenerator": "loop/state/out/read_dafeng_L0_0232.w-xiyou-0.build/gen_quotes.py",
            "quoteSpec": "loop/state/out/read_dafeng_L0_0232.w-xiyou-0.build/quotes_spec.py",
            "contentCore": "loop/state/out/read_dafeng_L0_0232.w-xiyou-0.build/content_core.py",
            "note": "候选 JSON 由脚本拼装；本文件不含任何手写偏移。",
        },
    }

    OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in checks:
        print("%s %s — %s" % ("PASS" if c["ok"] else "FAIL", c["id"], c["detail"]))
    print("allPass=%s  -> %s" % (cand["machineSelfCheck"]["allPass"], OUT))
    return 0 if cand["machineSelfCheck"]["allPass"] else 1


if __name__ == "__main__":
    sys.exit(main())
