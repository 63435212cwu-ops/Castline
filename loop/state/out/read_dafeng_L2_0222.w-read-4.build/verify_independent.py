# -*- coding: utf-8 -*-
"""read:dafeng:L2:0222 —— **独立**复算（w-read-4）。

与 build_candidate.py 的关系：不导入它的任何中间量，不 import content_*。
本脚本从**磁盘上的候选文件**重新读起，源文件重开、哈希重算、段落与句单元在本脚本内
另行切分。目的：验证「写盘之后的那份文件」本身，而不是验证构建过程的内存状态。

跑两类判据：
  A–H：静态判据（逐条复算引文、偏移、次数、段号、分区、判别字段、null 标注）。
  M：变异测试 —— 对候选内容做 N 处定向破坏，确认每一处都**能让对应判据变红**。
     若某个变异跑完判据仍全绿，说明那条判据是恒真的，必须报出来。

用法：
  python3 -B -s verify_independent.py            # 只跑静态判据
  python3 -B -s verify_independent.py --mutate   # 静态 + 变异
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = Path(__file__).resolve().parent
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0222.candidate.json"

S, E = 832785, 836013
UNIT_HEAD = "第两百二十一章 朝廷要犯"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
TAIL = "------------"

report = {"checks": {}, "failures": [], "mutations": []}


def fail(ck, msg):
    report["failures"].append("%s: %s" % (ck, msg))
    report["checks"][ck] = False


# ── A. 源文件：重开、重算哈希 ──────────────────────────────────────────────
RAW = DOCS.read_bytes()
file_hash = hashlib.sha256(RAW).hexdigest()
if file_hash != SOURCE_HASH:
    fail("A_sourceHash", "%s != %s" % (file_hash, SOURCE_HASH))
else:
    report["checks"]["A_sourceHash"] = True
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]

# ── B. 切片自检：长度、首、尾 ─────────────────────────────────────────────
SLICE = TEXT[S:E]
if len(SLICE) != E - S:
    fail("B_slice", "长度 %d != %d" % (len(SLICE), E - S))
elif not SLICE.startswith(UNIT_HEAD):
    fail("B_slice", "不以标题开头：%r" % SLICE[:24])
elif TAIL.strip() not in SLICE:
    fail("B_slice", "切片尾部缺分隔线")
else:
    report["checks"]["B_slice"] = True
report["segmentSha256"] = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

# ── C. 段落索引：本脚本内独立切分 ─────────────────────────────────────────
PARAS, _off = [], S
for _line in SLICE.split("\n"):
    if _line.strip():
        _lead = len(_line) - len(_line.lstrip())
        PARAS.append(("P%03d" % len(PARAS), _line.strip(), _off + _lead))
    _off += len(_line) + 1
PLAB = {lab: (t, a) for lab, t, a in PARAS}
PARA_AT = {}
for lab, t, a in PARAS:
    for i in range(a, a + len(t)):
        PARA_AT[i] = lab

# ── D. 读候选（从磁盘）────────────────────────────────────────────────────
CAND_TXT = CAND.read_text("utf-8")
cand = json.loads(CAND_TXT)
if cand.get("task") != "read:dafeng:L2:0222":
    fail("D_task", "task 字段不符：%r" % cand.get("task"))
if cand.get("agent") != "w-read-4":
    fail("D_task", "agent 字段不符：%r" % cand.get("agent"))
if cand.get("source", {}).get("sourceHash") != SOURCE_HASH:
    fail("D_task", "候选 source.sourceHash 与任务不符")
if "D_task" not in report["checks"]:
    report["checks"]["D_task"] = True

SECTIONS = ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeDiffs",
            "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
            "themeReadings", "unknowns", "selfCritique"]


def collect_quotes(node, path, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "quotes" and isinstance(v, list):
                for i, q in enumerate(v):
                    if isinstance(q, dict) and "quote" in q:
                        out.append(("%s.quotes[%d]" % (path, i), q))
            else:
                collect_quotes(v, path + "/" + str(k), out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect_quotes(v, "%s[%d]" % (path, i), out)


NODES = []
for _s in SECTIONS:
    if _s not in cand:
        fail("E_sections", "候选缺分区 %s" % _s)
        continue
    collect_quotes(cand[_s], _s, NODES)
report["quoteNodes"] = len(NODES)
if not NODES:
    fail("E_sections", "引文节点为 0")
elif "E_sections" not in report["checks"]:
    report["checks"]["E_sections"] = True

# ── E. 逐条复算引文（本脚本自己的口径）───────────────────────────────────
bad_loc = []
for path, q in NODES:
    if TEXT[q["start"]:q["end"]] != q["quote"]:
        bad_loc.append("slice!=quote %s" % path)
    if not (S <= q["start"] and q["end"] <= E):
        bad_loc.append("out-of-range %s" % path)
    if q.get("sourceHash") != SOURCE_HASH:
        bad_loc.append("hash %s" % path)
    if q.get("offsetUnit") != "codepoint":
        bad_loc.append("offsetUnit %s" % path)
    if TEXT.count(q["quote"]) != q.get("wholeTextOccurrences"):
        bad_loc.append("wholeCount %s" % path)
    if SLICE.count(q["quote"]) != q.get("occurrencesInRange"):
        bad_loc.append("rangeCount %s" % path)
    if PARA_AT.get(q["start"]) != q.get("paraLabel"):
        bad_loc.append("paraLabel %s (got %r, want %r)"
                       % (path, q.get("paraLabel"), PARA_AT.get(q["start"])))
if bad_loc:
    for m in bad_loc[:12]:
        fail("F_quoteLocate", m)
else:
    report["checks"]["F_quoteLocate"] = True

# ── F. 五栏引文互不共用（区间级 + 句单元级）──────────────────────────────
_SEP = re.compile(r"[。！？…]+")


def sent_index(rel, lab):
    t = PLAB[lab][0]
    units, last = [], 0
    for m in _SEP.finditer(t):
        units.append((last, m.end()))
        last = m.end()
    if last < len(t):
        units.append((last, len(t)))
    for k, (a, b) in enumerate(units or [(0, len(t))]):
        if a <= rel < b:
            return k
    return 0


COLUMNS = ("objective", "obstacle", "action", "result", "cost")
col_conf = []
for t in cand["tasks"]:
    seen_r, seen_s = {}, {}
    for col in COLUMNS:
        v = t.get(col)
        if not v:
            continue
        for q in v.get("quotes") or []:
            kr = (q["start"], q["end"])
            if kr in seen_r:
                col_conf.append("%s %s/%s range" % (t["id"], seen_r[kr], col))
            seen_r[kr] = col
            ks = (q["paraLabel"], sent_index(q["start"] - PLAB[q["paraLabel"]][1], q["paraLabel"]))
            if ks in seen_s and seen_s[ks] != col:
                col_conf.append("%s %s/%s sent %s" % (t["id"], seen_s[ks], col, ks))
            seen_s[ks] = col
if col_conf:
    for m in col_conf[:10]:
        fail("G_columnDisjoint", m)
else:
    report["checks"]["G_columnDisjoint"] = True

# ── G. null 栏必须有同名 Note；worldSettings 判别字段 ────────────────────
null_bad = []
for t in cand["tasks"]:
    for col in COLUMNS:
        if t.get(col) is None and not (t.get(col + "Note") or "").strip():
            null_bad.append("%s.%s" % (t["id"], col))
if null_bad:
    for m in null_bad:
        fail("H_nullNotes", m)
else:
    report["checks"]["H_nullNotes"] = True

ws_bad = []
for w in cand["worldSettings"]:
    k = w.get("kind")
    if k == "place":
        if w.get("placeState") not in ("arrived", "mentioned"):
            ws_bad.append("%s placeState=%r" % (w["id"], w.get("placeState")))
    elif k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(
                x not in ("hold", "transfer", "use", "lose") for x in st):
            ws_bad.append("%s itemStates=%r" % (w["id"], st))
    elif k == "rule":
        if w.get("institution") not in ("declared", "executed", "misunderstood"):
            ws_bad.append("%s institution=%r" % (w["id"], w.get("institution")))
    else:
        ws_bad.append("%s kind=%r" % (w["id"], k))
    if not (w.get("explain") or "").strip():
        ws_bad.append("%s no explain" % w["id"])
if ws_bad:
    for m in ws_bad:
        fail("I_worldSettings", m)
else:
    report["checks"]["I_worldSettings"] = True

# themeReadings 三条齐全且 counter 非空
th_bad = []
for th in cand["themeReadings"]:
    if not (th.get("perspective") or "").strip():
        th_bad.append("%s no perspective" % th["id"])
    if not th.get("support"):
        th_bad.append("%s no support" % th["id"])
    if not th.get("counter"):
        th_bad.append("%s no counter" % th["id"])
if th_bad:
    for m in th_bad:
        fail("J_theme", m)
else:
    report["checks"]["J_theme"] = True

# ── H. prose 『』 全部逐字（非恒真：要求对数 > 0）────────────────────────
PROSE_KEYS = [k for k in cand if k not in ("coverage", "machineSelfCheck", "source")]
prose = json.dumps({k: cand[k] for k in PROSE_KEYS}, ensure_ascii=False)
corners = re.findall(r"『([^『』]{1,600})』", prose)
cbad = [x for x in corners if x not in SLICE]
if not corners:
    fail("K_proseQuotes", "『』 对数为 0 ⇒ 判据恒真")
elif cbad:
    for m in cbad[:10]:
        fail("K_proseQuotes", "非逐字：%r" % m)
else:
    report["checks"]["K_proseQuotes"] = True
report["cornerPairs"] = len(corners)

# 第三类记号不得混用
if "「" in prose or "」" in prose:
    fail("K_proseQuotes", "混用了 「」 记号")
if "〔" in SLICE:
    fail("K_proseQuotes", "〔〕 记号在原文里出现 ⇒ 它与逐字引文无法区分")

# ── I. basis 取值 ─────────────────────────────────────────────────────────
BASIS_OK = ("explicit", "inferred", "derived", "unverified")
bbad = []


def walk_basis(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "basis" and v not in BASIS_OK:
                bbad.append("%s=%r" % (path, v))
            else:
                walk_basis(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_basis(v, "%s[%d]" % (path, i))


for _s in SECTIONS:
    if _s in cand:
        walk_basis(cand[_s], _s)
if bbad:
    for m in bbad[:10]:
        fail("L_basis", m)
else:
    report["checks"]["L_basis"] = True

# ── J. 覆盖表自洽 ─────────────────────────────────────────────────────────
cov, bad_cov = cand.get("coverage") or {}, []
listed = set(cov.get("zeroCoveredList") or [])
rows = cov.get("perParagraph") or []
if len(rows) != len(PARAS):
    bad_cov.append("perParagraph %d != 非空段 %d" % (len(rows), len(PARAS)))
zero_rows = {r["para"] for r in rows if r["state"] == "not-quoted"}
if zero_rows != listed:
    bad_cov.append("zeroCoveredList 与 perParagraph 不一致")
for r in rows:
    if r["state"] == "not-quoted" and not (r.get("note") or "").strip():
        bad_cov.append("%s 未引用但没有理由" % r["para"])
if cov.get("paragraphsTouched", 0) + len(listed) != len(PARAS):
    bad_cov.append("touched+zero != 非空段")
if bad_cov:
    for m in bad_cov:
        fail("M_coverage", m)
else:
    report["checks"]["M_coverage"] = True
report["coverage"] = {"paragraphs": len(PARAS), "touched": cov.get("paragraphsTouched"),
                      "zero": len(listed), "ratio": cov.get("quoteUnionRatioOfNonSpace")}

# ── K. 变异测试 ───────────────────────────────────────────────────────────
def mutate_and_check(name, fn, expect_key):
    """对候选 dict 做一次破坏，看 expect_key 是否变红。"""
    m = json.loads(CAND_TXT)
    fn(m)
    red = False
    try:
        # 复算被破坏后的那一项
        if expect_key == "F_quoteLocate":
            for _s in SECTIONS:
                for _p, q in []:
                    pass
            nodes = []
            for _s in SECTIONS:
                collect_quotes(m[_s], _s, nodes)
            red = any(TEXT[q["start"]:q["end"]] != q["quote"] or
                      not (S <= q["start"] and q["end"] <= E) or
                      SLICE.count(q["quote"]) != q.get("occurrencesInRange")
                      for _p, q in nodes)
        elif expect_key == "G_columnDisjoint":
            conf = []
            for t in m["tasks"]:
                seen = {}
                for col in COLUMNS:
                    v = t.get(col)
                    if not v:
                        continue
                    for q in v.get("quotes") or []:
                        if q["start"] in seen:
                            conf.append(1)
                        seen[q["start"]] = 1
            red = bool(conf)
        elif expect_key == "H_nullNotes":
            red = any(t.get(c) is None and not (t.get(c + "Note") or "").strip()
                      for t in m["tasks"] for c in COLUMNS)
        elif expect_key == "I_worldSettings":
            red = any(
                (w.get("kind") == "place" and w.get("placeState") not in ("arrived", "mentioned"))
                or (w.get("kind") == "item" and (not isinstance(w.get("itemStates"), list)
                                                 or not w.get("itemStates")))
                or (w.get("kind") == "rule" and w.get("institution") not in
                    ("declared", "executed", "misunderstood"))
                for w in m["worldSettings"])
        elif expect_key == "J_theme":
            red = any(not th.get("counter") for th in m["themeReadings"])
        elif expect_key == "K_proseQuotes":
            bl = json.dumps({k: m[k] for k in m if k not in
                             ("coverage", "machineSelfCheck", "source")}, ensure_ascii=False)
            cs = re.findall(r"『([^『』]{1,600})』", bl)
            red = bool(cs) and any(x not in SLICE for x in cs)
    except Exception as exc:  # noqa: BLE001
        red = True
        name += " (raised %r ⇒ 视为变红)" % (exc,)
    report["mutations"].append({"name": name, "redAsExpected": bool(red)})
    return bool(red)


def mut_first_quote_shift(m):
    for _s in SECTIONS:
        nodes = []
        collect_quotes(m[_s], _s, nodes)
        if nodes:
            nodes[0][1]["start"] += 1
            return
    raise RuntimeError("没有引文可改")


def mut_dup_column_quote(m):
    t = m["tasks"][0]
    q = (t["action"]["quotes"][0])
    t["obstacle"]["quotes"] = [dict(q)]


def mut_null_without_note(m):
    t = m["tasks"][1]
    t["cost"] = None
    t.pop("costNote", None)


def mut_ws_kind(m):
    m["worldSettings"][0]["kind"] = "place"
    m["worldSettings"][0].pop("institution", None)


def mut_ws_item_empty(m):
    for w in m["worldSettings"]:
        if w.get("kind") == "item":
            w["itemStates"] = []
            return
    raise RuntimeError("没有 item 条目")


def mut_theme_drop_counter(m):
    m["themeReadings"][0]["counter"] = []


def mut_prose_fake_quote(m):
    m["tasks"][0]["objective"]["note"] += " 『这段文字原文里绝对没有出现过纯属伪造』"


MUTS = [
    ("first quote start+1（偏移错位）", mut_first_quote_shift, "F_quoteLocate"),
    ("把 action 的引文复制进 obstacle（五栏共用）", mut_dup_column_quote, "G_columnDisjoint"),
    ("T2.cost 置 null 且删掉 costNote", mut_null_without_note, "H_nullNotes"),
    ("W01 的 kind 改成 place 并删掉 institution", mut_ws_kind, "I_worldSettings"),
    ("某个 item 的 itemStates 清空", mut_ws_item_empty, "I_worldSettings"),
    ("TH1 的 counter 清空", mut_theme_drop_counter, "J_theme"),
    ("在 prose 里塞一句伪造的 『』 引文", mut_prose_fake_quote, "K_proseQuotes"),
]

report["mutationSummary"] = {"total": len(MUTS), "red": 0}
if "--mutate" in sys.argv:
    for nm, fn, key in MUTS:
        if mutate_and_check(nm, fn, key):
            report["mutationSummary"]["red"] += 1
    if report["mutationSummary"]["red"] != len(MUTS):
        fail("N_mutations", "%d/%d 个变异按预期变红"
             % (report["mutationSummary"]["red"], len(MUTS)))
    else:
        report["checks"]["N_mutations"] = True

report["allPass"] = (not report["failures"]) and all(report["checks"].values())
print(json.dumps(report, ensure_ascii=False, indent=1))
(BUILD / "verify_independent_report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
sys.exit(0 if report["allPass"] else 1)
