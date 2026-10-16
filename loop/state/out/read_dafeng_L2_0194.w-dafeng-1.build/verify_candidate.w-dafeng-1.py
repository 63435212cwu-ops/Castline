#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立校验 read:dafeng:L2:0194 候选。作者：w-dafeng-1。

**不复用构建期任何中间量**：段落索引在本脚本内另按换行重新切分并重新定位，
引文定位**用反向查找**（先按 start 从 docs[0].text 切出，再检查它等于声明的 quote，
最后检查全文首次出现位置是否就是该 start），而不是复用构建期的 find 结果。
构建期任一处算错，这里应当能独立抓到。

用法：python3 -B -s verify_candidate.w-dafeng-1.py   （退出码 0 = 全绿）
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0194.candidate.json"
S, E = 709317, 713835
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第一百九十三章 这里是府衙"

FAIL = []
N = 0


def check(label, ok, detail=""):
    global N
    N += 1
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, ("  | " + detail) if detail else ""))
    if not ok:
        FAIL.append(label)


raw = DOCS.read_bytes()
TEXT = json.loads(raw.decode("utf-8"))[0]["text"]
SEG = TEXT[S:E]
cand = json.loads(CAND.read_text(encoding="utf-8"))

# ── 判据 1：源哈希与切片边界 ─────────────────────────────────────────────
check("1a 源文件 sha256 == task.sourceHash",
      hashlib.sha256(raw).hexdigest() == SRC_HASH, hashlib.sha256(raw).hexdigest()[:16])
check("1b 切片以本单元标题开头", TEXT[S:S + len(UNIT_HEAD)] == UNIT_HEAD)
check("1c 切片 UTF-8 sha256 == candidate.source.segmentSha256",
      hashlib.sha256(SEG.encode("utf-8")).hexdigest() == cand["source"]["segmentSha256"])

# ── 判据 2：段落索引（本脚本内独立重算）──────────────────────────────────
PARAS = []
_cursor = S
for _line in SEG.split("\n"):
    if _line.strip():
        _i = TEXT.find(_line, _cursor)
        assert _i >= 0, _line[:20]
        PARAS.append((_i, _i + len(_line), _line.strip()))
        _cursor = _i + len(_line)
check("2a 非空段数 == candidate.source.nonEmptyParagraphs",
      len(PARAS) == cand["source"]["nonEmptyParagraphs"], "%d 段" % len(PARAS))

# ── 判据 3：引文反向定位（不复用构建期结果）────────────────────────────
def collect(o, out):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            out.append(o)
        for v in o.values():
            collect(v, out)
    elif isinstance(o, list):
        for v in o:
            collect(v, out)


QS = []
for key in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeDiffs",
            "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
            "themeReadings", "unknowns"):
    collect(cand[key], QS)

bad_slice, bad_first, bad_hash, bad_range, bad_label, bad_occ = [], [], [], [], [], []
for o in QS:
    q, a, b = o["quote"], o["start"], o["end"]
    # 反向：从声明的 start 切出来，必须逐字等于 quote
    if TEXT[a:b] != q:
        bad_slice.append((a, b, q[:24]))
    # 无偏移歧义的**正确**判据：声明的 start 必须正好是**区间内**那一次出现的位置。
    #
    # 我第一版这里写的是「a 必须等于 TEXT.find(q)（全文首次出现）」，那是错的：
    # 全书 476 万字符里 '嘭...' 这种短句出现 14 次，首次出现在 515091（本区间之外），
    # 按那条判据所有合法短引文都会被判失败 —— 这是判据错，不是候选错。
    # 真正要防的是「短句用 TEXT.find 取到了区间外的偏移」，所以判据落在区间内：
    # 区间内必须恰好出现一次，且它的位置就是 a。
    if SEG.find(q) != a - S:
        bad_first.append((a, S + SEG.find(q), q[:24]))
    if o.get("sourceHash") != SRC_HASH:
        bad_hash.append(q[:24])
    if not (S <= a and b <= E):
        bad_range.append(q[:24])
    # 段号必须与该引文所在段一致
    lab = None
    for i, (pa, pb, _t) in enumerate(PARAS, start=1):
        if pa <= a < pb:
            lab = "P%03d" % i
    if lab != o.get("paraLabel"):
        bad_label.append((q[:20], o.get("paraLabel"), lab))
    # 区间内出现次数须与声明一致
    if SEG.count(q) != o.get("occurrencesInRange"):
        bad_occ.append(q[:24])
    # 全文重复数须与声明一致（如实登记，不参与定位）
    if TEXT.count(q) != o.get("wholeTextOccurrences"):
        bad_occ.append("%s wholeTextOccurrences 声明 %s 实测 %d"
                       % (q[:20], o.get("wholeTextOccurrences"), TEXT.count(q)))

check("3a 引文对象数 == candidate.machineSelfCheck.quoteObjectsResolved",
      len(QS) == cand["machineSelfCheck"]["quoteObjectsResolved"], "%d 个" % len(QS))
check("3b 每条 text[start:end] == quote", not bad_slice, str(bad_slice[:3]))
check("3c 每条 start 就是**区间内**那次出现的位置（无区间内偏移歧义）",
      not bad_first, str(bad_first[:3]))
check("3d 每条 sourceHash 正确", not bad_hash, str(bad_hash[:3]))
check("3e 每条引文落在 [%d,%d) 内" % (S, E), not bad_range, str(bad_range[:3]))
check("3f 每条 paraLabel 与段索引一致", not bad_label, str(bad_label[:3]))
check("3g occurrencesInRange 与 wholeTextOccurrences 声明值均与实测一致",
      not bad_occ, str(bad_occ[:3]))

# ── 判据 4：区间内唯一（构建期硬要求）──────────────────────────────────
dup = [o["quote"][:24] for o in QS if SEG.count(o["quote"]) != 1]
check("4 每条引文在区间内唯一（occurrencesInRange==1）", not dup, str(dup[:3]))

# ── 判据 5：五栏独立性（句单元级 + 字符区间级，本脚本内重算）──────────
def sents():
    out = []
    for a, b, _t in PARAS:
        cur = a
        for m in re.finditer(r"[。！？…]+|\.{2,}", TEXT[a:b]):
            e = a + m.end()
            if e > cur:
                out.append((cur, e))
            cur = e
        if cur < b:
            out.append((cur, b))
    return out


SENTS = sents()


def sid(pos):
    for i, (a, b) in enumerate(SENTS, start=1):
        if a <= pos < b:
            return i
    return None


conf_s, conf_r = [], []
for t in cand["tasks"]:
    seen_s, seen_r = {}, []
    for f in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(f)
        if not isinstance(v, dict):
            continue
        for o in v["quotes"]:
            k = sid(o["start"])
            if k in seen_s:
                conf_s.append("%s %s/%s 共用句单元 %s" % (t["id"], f, seen_s[k], k))
            seen_s[k] = f
            for (ra, rb, rf) in seen_r:
                if not (o["end"] <= ra or o["start"] >= rb):
                    conf_r.append("%s %s/%s 区间重叠" % (t["id"], f, rf))
            seen_r.append((o["start"], o["end"], f))
check("5a 五栏无共用句单元", not conf_s, str(conf_s[:3]))
check("5b 五栏无字符区间重叠", not conf_r, str(conf_r[:3]))

# ── 判据 6：null 栏必须带同名 Note ──────────────────────────────────────
miss_note, nulls = [], []
for t in cand["tasks"]:
    for f in ("objective", "obstacle", "action", "result", "cost"):
        if t.get(f) is None:
            nulls.append("%s.%s" % (t["id"], f))
            if not (t.get(f + "Note") or "").strip():
                miss_note.append("%s.%s" % (t["id"], f))
check("6a 所有 null 栏都带同名 <栏位>Note", not miss_note, str(miss_note))
check("6b nullFieldDisposition 条数 == 实际 null 栏数",
      len(cand["nullFieldDisposition"]) == len(nulls), "%d 个 null" % len(nulls))

# ── 判据 7：sourceHash 未被切片哈希覆盖 ─────────────────────────────────
check("7 source.sourceHash 仍是整文件哈希（非切片）",
      cand["source"]["sourceHash"] == SRC_HASH
      and cand["source"]["segmentSha256"] != SRC_HASH)

# ── 判据 8：散文「…」逐字核验（构建期规则，独立重跑）──────────────────
prose = []
for t in cand["tasks"]:
    for k, v in t.items():
        if isinstance(v, str):
            prose.append(v)
        if isinstance(v, dict):
            prose.append(v.get("text", ""))
            if v.get("note"):
                prose.append(v["note"])
for key in ("causeEdges", "rejectedEdges", "states", "knowledgeDiffs", "foreshadows",
            "notForeshadows", "worldSettings", "notWorldSettings"):
    for it in cand[key]:
        for k, v in it.items():
            if isinstance(v, str) and k != "id":
                prose.append(v)
            if isinstance(v, list):
                for sub in v:
                    if isinstance(sub, dict):
                        prose.extend(x for x in sub.values() if isinstance(x, str))
                    elif isinstance(sub, str):
                        prose.append(sub)
for th in cand["themeReadings"]:
    prose.append(th["perspective"])
    for g in ("support", "counter"):
        for sub in th[g]:
            prose.append(sub["what"])
for u in cand["unknowns"]:
    prose.append(u["why"])

bad = []
for ps in prose:
    for m in re.finditer(r"「([^」]*)」", ps):
        if m.group(1) and m.group(1) not in TEXT:
            bad.append(m.group(1)[:36])
check("8 散文「…」全部是原文逐字子串（共 %d 段散文）" % len(prose), not bad, str(bad[:3]))

# ── 判据 9：段处置完整性（每个非空段都要有处置，不是留白）──────────────
disp = {z["para"] for z in cand["reverseValidation"]["zeroDisposition"]}
allp = {"P%03d" % i for i in range(1, len(PARAS) + 1)}
check("9a 每个非空段都有处置", not (allp - disp), str(sorted(allp - disp)[:5]))
check("9b 处置表无越界段号", not (disp - allp), str(sorted(disp - allp)[:5]))

# ── 判据 10：零覆盖集合与本脚本重算一致 ────────────────────────────────
touched = set()
for o in QS:
    for i, (pa, pb, _t) in enumerate(PARAS, start=1):
        if pa <= o["start"] < pb:
            touched.add("P%03d" % i)
zero = sorted(allp - touched, key=lambda x: int(x[1:]))
check("10a zeroCoveredParagraphs.count 与本脚本重算一致",
      cand["coverage"]["zeroCoveredParagraphs"]["count"] == len(zero),
      "声明 %s / 实测 %d" % (cand["coverage"]["zeroCoveredParagraphs"]["count"], len(zero)))
check("10b zeroCoveredParagraphs.paras 与本脚本重算一致",
      sorted(cand["coverage"]["zeroCoveredParagraphs"]["paras"], key=lambda x: int(x[1:])) == zero)
check("10c paragraphsTouchedByAtLeastOneQuote 一致",
      cand["coverage"]["paragraphsTouchedByAtLeastOneQuote"] == len(touched))
check("10d paragraphsWithDisposition == 非空段数",
      cand["coverage"]["paragraphsWithDisposition"] == len(PARAS))

# ── 判据 11：worldSettings 三套判别字段写进字段本身 ────────────────────
kind_bad = []
for w in cand["worldSettings"]:
    if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        kind_bad.append("%s placeState=%r" % (w["id"], w.get("placeState")))
    if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        kind_bad.append("%s institution=%r" % (w["id"], w.get("institution")))
    if w["kind"] == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            kind_bad.append("%s itemStates=%r" % (w["id"], st))
    if not w.get("explain"):
        kind_bad.append("%s 缺 explain" % w["id"])
check("11a worldSettings 三套判别字段取值合法且 explain 非空", not kind_bad, str(kind_bad[:3]))
check("11b worldSettings 每条都有引文", all(w.get("quotes") for w in cand["worldSettings"]))

# ── 判据 12：footer 一致性（不声称语义复核）────────────────────────────
check("12a semanticReview 未声称完成", cand["semanticReview"] == "not-performed")
check("12b machineSelfCheck 各布尔为真",
      all(v is True for k, v in cand["machineSelfCheck"].items() if isinstance(v, bool)),
      str({k: v for k, v in cand["machineSelfCheck"].items() if v is not True}))

# ── 判据 13：段处置里的「已并入 X」必须可核验 ──────────────────────────
# 为什么单列这条：处置表最容易退化成**无法证伪的记账**——写一句「已并入 W3」
# 就能让任意一段看起来被处理过。所以这里反过来查：被点名的条目 X 是否**真的**
# 在 P### 这一段里有引文（或有条目说明逐字提到段号）。查不出来就算失败。
# 第一版候选有 19 条这样的一厢情愿声明，就是被这条判据独立抓出来的。
by_id = {}
for key in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeDiffs",
            "foreshadows", "worldSettings"):
    for it in cand[key]:
        qq_ = []
        collect(it, qq_)
        by_id[it["id"]] = {"labels": {x["paraLabel"] for x in qq_},
                           "prose": json.dumps(it, ensure_ascii=False)}
for it in cand["unknowns"]:
    qq_ = []
    collect(it, qq_)
    by_id[it["id"]] = {"labels": {x["paraLabel"] for x in qq_},
                       "prose": json.dumps(it, ensure_ascii=False)}
for it in cand["themeReadings"]:
    qq_ = []
    collect(it, qq_)
    by_id[it["id"]] = {"labels": {x["paraLabel"] for x in qq_},
                       "prose": json.dumps(it, ensure_ascii=False)}

unverifiable, resolved = [], 0
for z in cand["reverseValidation"]["zeroDisposition"]:
    d, pid = z["disposition"], z["para"]
    if "已并入" not in d:
        continue
    resolved += 1
    refs = re.findall(r"\b(T\d+|C\d+|R\d+|S\d+|K\d+|F\d+|W\d+|U\d+|TH\d+)\b", d)
    hit = False
    for r in refs:
        e = by_id.get(r)
        if e and (pid in e["labels"] or pid in e["prose"]):
            hit = True
            break
    if not hit:
        unverifiable.append((pid, d[:46], refs))
check("13 处置里的『已并入 X』可核验（共 %d 条）" % resolved, not unverifiable,
      str(unverifiable[:3]))

print("\n%d 项判据，%d 项失败" % (N, len(FAIL)))
if FAIL:
    for f in FAIL:
        print("  FAILED: %s" % f)
    sys.exit(1)
print("全绿（exit 0）")
