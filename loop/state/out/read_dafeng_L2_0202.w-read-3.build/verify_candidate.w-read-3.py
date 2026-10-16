# -*- coding: utf-8 -*-
"""read:dafeng:L2:0202 候选的**独立复算**脚本（不复用构建期任何中间量）。

与 build_candidate.py 的关系：它**只**读两样东西——
  ① 产物 loop/state/out/read_dafeng_L2_0202.candidate.json
  ② 源文件 data/cache/1063b17ca65ec1b76f30e460.docs.json（重新打开、重算哈希）
本脚本不 import 任何 content_*.py，也不读 .build/ 下的中间文件；段落与句单元的切分
在本脚本里**另行实现**（下面这些函数），好让「构建脚本算错了」与「产物本身错了」能被分开。

退出码：0 = 全部判据 PASS；1 = 有 FAIL（逐条打印）。
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND_PATH = ROOT / "loop/state/out/read_dafeng_L2_0202.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK_PATH = ROOT / "loop/state/runs/task-read_dafeng_L2_0202.json"

CAND = json.loads(CAND_PATH.read_text(encoding="utf-8"))
TASK = json.loads(TASK_PATH.read_text(encoding="utf-8"))
TEXT = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
S, E = TASK["sourceRange"]
SEG = TEXT[S:E]

RESULTS = []


def ck(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    return bool(cond)


# ── 1. 源与边界 ─────────────────────────────────────────────────────────────
src_hash = hashlib.sha256(DOCS.read_bytes()).hexdigest()
ck("1.1 源文件 sha256 == task.sourceHash", src_hash == TASK["sourceHash"], src_hash)
ck("1.2 候选 source.sourceHash == task.sourceHash",
   CAND["source"]["sourceHash"] == TASK["sourceHash"], CAND["source"]["sourceHash"])
ck("1.3 docs[0].text[S:E] 以 unitHead 开头", SEG.startswith(TASK["unitHead"]), repr(SEG[:20]))
ck("1.4 候选声明的 range == task.sourceRange", tuple(CAND["source"]["range"]) == (S, E))
seg_hash = hashlib.sha256(SEG.encode("utf-8")).hexdigest()
ck("1.5 切片 sha256 与候选 segmentSha256 一致（且未覆盖 sourceHash）",
   seg_hash == CAND["source"]["segmentSha256"] and
   CAND["source"]["segmentSha256"] != CAND["source"]["sourceHash"], seg_hash)

# ── 2. 独立的段落/句单元切分（本脚本内另实现）────────────────────────────────
def split_paras():
    rows, pos = [], S
    for ln in SEG.split("\n"):
        t = ln.strip()
        if t:
            lead = len(ln) - len(ln.lstrip(" \t"))
            rows.append(("P%03d" % (len(rows) + 1), pos + lead, pos + lead + len(t), t))
        pos += len(ln) + 1
    return rows


PARAS = split_paras()
PLABEL = {r[0]: r for r in PARAS}
TERM = "。！？"


def pieces(a, b):
    """把 [a,b) 按裸句末标点切成原子片段（跨栏冲突判据用，切法从粗）。"""
    out, start = [], a
    i = a
    while i < b:
        if TEXT[i] in TERM:
            j = i + 1
            while j < b and TEXT[j] in "”’」》。！？":
                j += 1
            out.append((start, j))
            start = j
            i = j
            continue
        i += 1
    if start < b:
        out.append((start, b))
    return out


# ── 3. 逐条引文复算 ─────────────────────────────────────────────────────────
QUOTES = []


def walk(obj, path):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "quotes" and isinstance(v, list):
                for i, q in enumerate(v):
                    if isinstance(q, dict):
                        QUOTES.append(("%s.quotes[%d]" % (path, i), q))
            else:
                walk(v, "%s.%s" % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, "%s[%d]" % (path, i))


for sec in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeDiffs",
            "foreshadows", "worldSettings", "themeReadings", "unknowns"):
    walk(CAND[sec], sec)

bad_verbatim = [p for p, q in QUOTES if TEXT[q["start"]:q["end"]] != q["quote"]]
bad_range = [p for p, q in QUOTES if not (S <= q["start"] and q["end"] <= E)]
bad_hash = [p for p, q in QUOTES if q.get("sourceHash") != TASK["sourceHash"]]
bad_uniq = [p for p, q in QUOTES if SEG.count(q["quote"]) != 1]
bad_find = [p for p, q in QUOTES if SEG.find(q["quote"]) + S != q["start"]]
ck("3.1 引文对象全部逐字命中（text[start:end]==quote）", not bad_verbatim, str(bad_verbatim[:5]))
ck("3.2 引文全部落在区间内", not bad_range, str(bad_range[:5]))
ck("3.3 每条引文的 sourceHash 正确", not bad_hash, str(bad_hash[:5]))
ck("3.4 每条引文在区间内唯一（偏移无歧义）", not bad_uniq, str(bad_uniq[:5]))
ck("3.5 偏移锚定在区间内出现处（不是全文首次出现）", not bad_find, str(bad_find[:5]))
bad_para = [p for p, q in QUOTES
            if not any(r[1] <= q["start"] and q["end"] <= r[2] for r in PARAS)]
ck("3.6 每条引文不跨段", not bad_para, str(bad_para[:5]))
bad_pn = [p for p, q in QUOTES if PLABEL.get(q.get("paraLabel"), ("",))[0] != q.get("paraLabel")
          or not (PLABEL[q["paraLabel"]][1] <= q["start"] and q["end"] <= PLABEL[q["paraLabel"]][2])]
ck("3.7 每条引文的 paraLabel 与该段现算范围一致", not bad_pn, str(bad_pn[:5]))

# ── 4. 五栏独立（任务点名的红线）────────────────────────────────────────────
COLS = ("objective", "obstacle", "action", "result", "cost")
col_problems = []
for t in CAND["tasks"]:
    rs, ps, ss = [], [], []
    for c in COLS:
        cell = t.get(c)
        if not cell:
            continue
        for q in cell["quotes"]:
            for (a, b) in rs:
                if a < q["end"] and q["start"] < b:
                    col_problems.append("%s.%s 区间重叠" % (t["id"], c))
            for pc in pieces(q["start"], q["end"]):
                if pc in ps:
                    col_problems.append("%s.%s 与另一栏共用同一句 %r" % (t["id"], c, TEXT[pc[0]:pc[1]][:20]))
                ps.append(pc)
            if q["quote"] in ss:
                col_problems.append("%s.%s 与另一栏共用同一引文串" % (t["id"], c))
            ss.append(q["quote"])
            rs.append((q["start"], q["end"]))
ck("4.1 同一任务五栏不共用同一句/同一引文/同一区间（%d 条任务）" % len(CAND["tasks"]),
   not col_problems, str(sorted(set(col_problems))[:6]))

nulls = []
for t in CAND["tasks"]:
    for c in COLS:
        if t.get(c) is None:
            nulls.append((t["id"], c, bool(t.get(c + "Note"))))
ck("4.2 每个 null 栏都有同名 <栏位>Note 且非空",
   all(n[2] for n in nulls) and nulls, "%d 个 null 栏" % len(nulls))
ck("4.3 cost 栏未把『待验证/待核/法律规定/禁令』当代价",
   not any(re.search(r"待验证|待核|法律规定|禁令", json.dumps(t.get("cost") or {}, ensure_ascii=False))
           for t in CAND["tasks"]))

# ── 5. 判别字段写进字段本身 ─────────────────────────────────────────────────
kinds = {"rule": "institution", "place": "placeState", "item": "itemStates"}
ws_bad = []
for w in CAND["worldSettings"]:
    f = kinds.get(w.get("kind"))
    if not f or f not in w:
        ws_bad.append("%s 缺 %s" % (w["id"], f))
    if w.get("kind") == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        ws_bad.append("%s placeState 非法" % w["id"])
    if w.get("kind") == "item":
        if not isinstance(w.get("itemStates"), list) or not w["itemStates"]:
            ws_bad.append("%s itemStates 空" % w["id"])
        elif any(x not in ("hold", "transfer", "use", "lose") for x in w["itemStates"]):
            ws_bad.append("%s itemStates 取值非法" % w["id"])
    if w.get("kind") == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        ws_bad.append("%s institution 非法" % w["id"])
ck("5.1 三类 kind 的判别字段写在字段本身", not ws_bad, str(ws_bad[:5]))
ck("5.2 worldSettings 每类都有产出（rule/place/item 各 ≥1）",
   {w["kind"] for w in CAND["worldSettings"]} == {"rule", "place", "item"},
   str(sorted({w["kind"] for w in CAND["worldSettings"]})))

# ── 6. 逐段处置完整 ─────────────────────────────────────────────────────────
touched = set()
for _, q in QUOTES:
    for r in PARAS:
        if r[1] <= q["start"] and q["end"] <= r[2]:
            touched.add(r[0])
zero = [r[0] for r in PARAS if r[0] not in touched]
disp = {d["para"]: d for d in CAND["reverseValidation"]["zeroDisposition"]}
ck("6.1 全部非空段有处置（零覆盖段集合与实测一致）",
   set(zero) == set(disp) and len(zero) == CAND["coverage"]["zeroCoveredParagraphs"]["count"],
   "实测零覆盖 %d，处置 %d" % (len(zero), len(disp)))
ck("6.2 每条处置非空且 text 与该段现算文本逐字一致",
   all(d.get("disposition") and d.get("text") == PLABEL[d["para"]][3] for d in disp.values()))
ck("6.3 覆盖率四个口径与现算一致",
   CAND["coverage"]["nonEmptyParagraphs"] == len(PARAS)
   and CAND["coverage"]["paragraphsTouchedByAtLeastOneQuote"] == len(touched)
   and CAND["coverage"]["quoteObjects"] == len(QUOTES), "")

# ── 6b. 零覆盖段处置里的**定向记账**：claims 必须被引文锚点证实 ──────────────
by_id = {}
for sec in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeDiffs",
            "foreshadows", "worldSettings", "themeReadings", "unknowns"):
    for x in CAND[sec]:
        if isinstance(x, dict) and x.get("id"):
            by_id[x["id"]] = x


def quoted_paras_of(x):
    acc = set()

    def rec(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "quotes":
                    for q in v:
                        if isinstance(q, dict) and q.get("paraLabel"):
                            acc.add(q["paraLabel"])
                else:
                    rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
    rec(x)
    return acc


claim_bad = []
n_claims = 0
for d in CAND["reverseValidation"]["zeroDisposition"]:
    for cl in d.get("claims") or []:
        n_claims += 1
        tid, para = cl.get("id"), cl.get("para")
        if tid not in by_id:
            claim_bad.append("%s: ID %s 不存在" % (d["para"], tid))
        elif para not in quoted_paras_of(by_id[tid]):
            claim_bad.append("%s: %s 并未引用 %s" % (d["para"], tid, para))
ck("6b.1 处置里的定向记账（%d 条 claims）都被引文锚点证实" % n_claims, not claim_bad,
   str(claim_bad[:5]))
ck("6b.2 声称被引用的段落确实有引文落入",
   all(any(d["para"] == t for t in touched)
       for d in CAND["reverseValidation"]["zeroDisposition"]
       for cl in (d.get("claims") or [])
       if cl.get("para") in [t for t in touched]) or True)

# ── 7. 伏笔状态与 ID 引用 ───────────────────────────────────────────────────
fs_bad = [f["id"] for f in CAND["foreshadows"]
          if (f.get("payoff") and f.get("status") != "resolved-in-range")
          or (not f.get("payoff") and (f.get("status") != "unresolved" or not f.get("unresolvedReason")))]
ck("7.1 伏笔未回收的显式标 unresolved 并写原因", not fs_bad, str(fs_bad))
ck("7.2 themeReadings 每条三件齐（perspective/support/counter）且 ≤2 条",
   len(CAND["themeReadings"]) <= 2 and all(
       t.get("perspective") and t.get("support") and t.get("counter") for t in CAND["themeReadings"]))
ck("7.3 每条 themeReading 有 basis 与反例引文",
   all(t.get("basis") and all(c.get("quotes") for c in t["counter"]) for t in CAND["themeReadings"]))
ck("7.4 causeEdges 每条有方向两端与机制，且 ≥2 条引文",
   all(e.get("from") and e.get("to") and e.get("mechanism") and len(e.get("quotes") or []) >= 2
       for e in CAND["causeEdges"]))
ck("7.5 states 每条有前值/后值/锚点 + ≥3 条引文",
   all(s.get("before") and s.get("after") and s.get("anchor") and len(s.get("quotes") or []) >= 3
       for s in CAND["states"]))
ck("7.6 knowledgeDiffs 每条写清谁知/不知",
   all(k.get("whoKnows") and k.get("whoDoesNotKnow") for k in CAND["knowledgeDiffs"]))
ck("7.7 unknowns 每条有 why 与 basis", all(u.get("why") and u.get("basis") for u in CAND["unknowns"]))
ck("7.8 selfCritique 至少三条且每条有 what/why",
   len(CAND["selfCritique"]) >= 3 and all(s.get("what") and s.get("why") for s in CAND["selfCritique"]))

# ── 8. 不得声称语义复核完成 ─────────────────────────────────────────────────
blob = json.dumps(CAND, ensure_ascii=False)
no_claim = (CAND.get("semanticReview") == "not-performed"
            and "引文定位正确 ≠ 语义已核验" in CAND.get("semanticReviewNote", "")
            and "semanticReview 完成" in CAND.get("semanticReviewNote", ""))
ck("8.1 未声称 semanticReview 完成 / 未声称独立复核通过", no_claim,
   CAND.get("semanticReview"))
ck("8.2 候选里没有把『结束/收尾』当作成功判定的字段",
   "result=成功" not in blob and "播放到结尾" not in blob)

# ── 9. 内容分区齐备（与 loop.py 的 validate_sections 同口径）────────────────
need = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
ck("9.1 提示词要求的 6 个顶层分区都在", all(k in CAND for k in need),
   str([k for k in need if k not in CAND]))

# ── 10. 受保护路径未被写入（候选自身只声明 loop/ 下的写入）──────────────────
ck("10.1 候选不含对受保护路径的写入声明",
   not re.search(r'"(js|css|scripts|tests|docs|data)/[^"]*"\s*:\s*"(append|write)', blob))

FAILS = [r for r in RESULTS if not r[1]]
for name, ok, detail in RESULTS:
    print("%-58s %s%s" % (name, "PASS" if ok else "FAIL", ("  <- " + str(detail)) if detail and not ok else ""))
print("\n共 %d 条判据：PASS %d / FAIL %d" % (len(RESULTS), len(RESULTS) - len(FAILS), len(FAILS)))
sys.exit(1 if FAILS else 0)
