# -*- coding: utf-8 -*-
"""read:dafeng:L2:0218 —— 独立复核探针（不复用构建脚本的任何中间量）。

设计原则：**从磁盘候选重新读起**，源文件重开、哈希重算、段落与句单元在本脚本内
另行切分。构建脚本里的 PARAS / SENT / touched 等中间量一律不导入 —— 否则
「同一份代码自我确认」是零信息量的。

判据分三组：
  A–F  定位类：源哈希、切片口径、逐条引文（逐字/偏移/区间/次数/段号/句单元）、
       词级引文（『』 与 〔〕 两种记号）、越界与 sourceHash 一致性；
  G–I  结构类：必需分区、枚举取值、伏笔与 null 的必填理由；
  J    覆盖类：逐段覆盖表与区间外不发散；
  M    变异自检：14 个变异必须按预期变红（含「把合法值改成另一种合法值」这种
       第一版踩过的坑 —— 那种变异不会变红，因为目标仍合法）。

用法：
  python3 -B -s verify_independent.py                # 只验
  python3 -B -s verify_independent.py --mutate        # 验 + 跑全部变异
"""
import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND = ROOT / "loop/state/out/read_dafeng_L2_0218.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 813350, 817425
UNIT_HEAD = "第两百一十七章 许七安：我爽了"

SECTIONS = ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeDiffs",
            "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
            "themeReadings", "unknowns", "selfCritique"]
REQUIRED = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
BASIS_OK = ("explicit", "inferred", "derived", "unverified")
COLUMNS = ("objective", "obstacle", "action", "result", "cost")

fails = []
notes = []


def ck(cond, name, detail=""):
    if not cond:
        fails.append("%s %s" % (name, detail))
    return cond


# ── A/B 源与切片（独立重算）──────────────────────────────────────────────
RAW = DOCS.read_bytes()
FILE_HASH = hashlib.sha256(RAW).hexdigest()
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[S:E]
ck(FILE_HASH == SOURCE_HASH, "A_sourceHash", FILE_HASH)
ck(SLICE.startswith(UNIT_HEAD), "B_unitHead", repr(SLICE[:20]))
ck(len(SLICE) == E - S, "B_sliceLen", len(SLICE))

# 段落索引：本脚本自行切分（不复用构建脚本）
PARAS = []
_off = S
for _line in SLICE.split("\n"):
    if _line.strip():
        PARAS.append(("P%03d" % len(PARAS), _line.strip(), _off + (len(_line) - len(_line.lstrip()))))
    _off += len(_line) + 1
SEP = re.compile(r"[。！？…]+")


def sents(t):
    o, last = [], 0
    for m in SEP.finditer(t):
        o.append((last, m.end())); last = m.end()
    if last < len(t):
        o.append((last, len(t)))
    return o or [(0, len(t))]


SENT = {l: sents(t) for l, t, _a in PARAS}
PBASE = {l: a for l, _t, a in PARAS}


def para_of(pos):
    for l, t, a in PARAS:
        if a <= pos < a + len(t):
            return l


def sent_of(pos):
    l = para_of(pos)
    if l is None:
        return None
    rel = pos - PBASE[l]
    for k, (a, b) in enumerate(SENT[l]):
        if a <= rel < b:
            return k
    return 0


cand = json.loads(CAND.read_text("utf-8"))

# ── C/D 逐条引文（独立复算）──────────────────────────────────────────────
nodes = []


def collect(o, path=""):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            nodes.append((path, o))
        for k, v in o.items():
            collect(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            collect(v, "%s[%d]" % (path, i))


for name in SECTIONS:
    collect(cand.get(name), name)

bad = []
for path, q in nodes:
    if TEXT[q["start"]:q["end"]] != q["quote"]:
        bad.append("slice!=quote %s" % path)
    if not (S <= q["start"] and q["end"] <= E):
        bad.append("range %s" % path)
    if q.get("sourceHash") != SOURCE_HASH:
        bad.append("sourceHash %s" % path)
    if q.get("wholeTextOccurrences") != TEXT.count(q["quote"]):
        bad.append("nFull %s" % path)
    if q.get("occurrencesInRange") != SLICE.count(q["quote"]):
        bad.append("nRange %s" % path)
    if para_of(q["start"]) != q.get("paraLabel"):
        bad.append("para %s (decl=%s actual=%s)" % (path, q.get("paraLabel"), para_of(q["start"])))
    if sent_of(q["start"]) != q.get("sentUnit"):
        bad.append("sent %s" % path)
ck(not bad, "C_quotes", "; ".join(bad[:6]))

# ── E 三种记号（独立扫；本脚本不导入构建脚本）────────────────────────────
blob = json.dumps({k: cand.get(k) for k in SECTIONS}, ensure_ascii=False)
corner = re.findall(r"『([^『』]{1,600})』", blob)
corner_bad = [x for x in corner if x not in SLICE]
ck(corner_bad == [], "E_corner", str(corner_bad[:4]))
ck(len(corner) > 0, "E_cornerNonVacuous", "扫到 0 对 ⇒ 恒真，判据无意义")
cjk = re.findall(r"[「」]", blob)
ck(cjk == [], "E_noThirdMarker", "仍在使用 「」 %d 处" % len(cjk))
# 〔〕 是「非引用」记号：它**不应该**逐字（否则应写成 『』）
# 这里只确认它没被误用成引文记号：若某个 〔…〕 逐字命中原文，提示应改用 『』
suspicious = [x for x in re.findall(r"〔([^〔〕]{1,600})〕", blob) if x in SLICE]
notes.append("〔〕 里逐字命中原文的（提示可改用 『』，非错误）：%d 处 %s"
             % (len(suspicious), suspicious[:5]))

# ── F 五栏不共用（两套口径，独立重算）────────────────────────────────────
conf = []
for t in cand.get("tasks") or []:
    r, s2 = {}, {}
    for col in COLUMNS:
        v = t.get(col)
        if not v:
            continue
        for q in v.get("quotes") or []:
            k = (q["start"], q["end"])
            if k in r:
                conf.append("%s %s/%s range" % (t["id"], r[k], col))
            r[k] = col
            k2 = (q["paraLabel"], q["sentUnit"])
            if k2 in s2 and s2[k2] != col:
                conf.append("%s %s/%s sent %s" % (t["id"], s2[k2], col, k2))
            s2[k2] = col
ck(not conf, "F_columns", "; ".join(conf[:6]))

# ── G 必需分区 ────────────────────────────────────────────────────────────
missing = [k for k in REQUIRED if k not in cand]
ck(not missing, "G_sections", str(missing))

# ── H 枚举取值 + 必填理由 ────────────────────────────────────────────────
enum_bad = []


def chk_basis(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "basis" and v not in BASIS_OK:
                enum_bad.append("basis %s=%r" % (path, v))
            else:
                chk_basis(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            chk_basis(v, "%s[%d]" % (path, i))


for name in SECTIONS:
    chk_basis(cand.get(name), name)

null_bad = []
for t in cand.get("tasks") or []:
    for col in COLUMNS:
        if t.get(col) is None and not (t.get(col + "Note") or "").strip():
            null_bad.append("%s.%s" % (t["id"], col))

ws_bad = []
for w in cand.get("worldSettings") or []:
    k = w.get("kind")
    if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        ws_bad.append("%s placeState" % w.get("id"))
    if k == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(
                x not in ("hold", "transfer", "use", "lose") for x in st):
            ws_bad.append("%s itemStates=%r" % (w.get("id"), st))
    if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        ws_bad.append("%s institution" % w.get("id"))
    if k not in ("place", "item", "rule"):
        ws_bad.append("%s kind=%r" % (w.get("id"), k))
    if not (w.get("explain") or "").strip():
        ws_bad.append("%s explain" % w.get("id"))
ck(not enum_bad and not null_bad and not ws_bad, "H_enums",
   "; ".join((enum_bad + null_bad + ws_bad)[:6]))

# ── I 伏笔与主题的必填项 ─────────────────────────────────────────────────
fs_bad = []
for f in cand.get("foreshadows") or []:
    if f.get("status") not in ("resolved", "unresolved", "partially-resolved"):
        fs_bad.append("%s status=%r" % (f.get("id"), f.get("status")))
    if f.get("status") != "resolved" and not (f.get("unresolvedReason") or "").strip():
        fs_bad.append("%s 缺 unresolvedReason" % f.get("id"))
    if len(f.get("quotes") or []) < 2:
        fs_bad.append("%s 引文 <2（铺设+回收各需一处）" % f.get("id"))
    if not f.get("setupInRange"):
        fs_bad.append("%s setupInRange 非 true" % f.get("id"))
th_bad = []
for t in cand.get("themeReadings") or []:
    if not (t.get("perspective") or "").strip():
        th_bad.append("%s perspective" % t.get("id"))
    if not (t.get("support") or []):
        th_bad.append("%s support" % t.get("id"))
    if not (t.get("counter") or []):
        th_bad.append("%s counter（缺 counter 就只是论证不是解释）" % t.get("id"))
ck(not fs_bad and not th_bad, "I_foreshadowTheme", "; ".join((fs_bad + th_bad)[:6]))

# ── J 覆盖表：逐段对账 + 区间外不发散 ───────────────────────────────────
cov = cand.get("coverage") or {}
per = {r["para"]: r for r in (cov.get("perParagraph") or [])}
ck(len(per) == len(PARAS), "J_paraCount", "%d vs %d" % (len(per), len(PARAS)))
touched = {}
for path, q in nodes:
    touched.setdefault(q["paraLabel"], set()).add(path.split("/")[0].split("[")[0])
mism = []
for l, t, a in PARAS:
    row = per.get(l)
    if not row:
        mism.append("%s 缺行" % l); continue
    actual = sorted(touched.get(l, []))
    if row.get("state") == "quoted" and sorted(row.get("sections") or []) != actual:
        mism.append("%s sections %s vs %s" % (l, row.get("sections"), actual))
    if row.get("state") == "not-quoted" and actual:
        mism.append("%s 标未引用但实际被引用" % l)
    if row.get("state") == "not-quoted" and not (row.get("note") or "").strip():
        mism.append("%s 未引用但没写理由（未标注的未知）" % l)
ck(not mism, "J_coverage", "; ".join(mism[:6]))
ck(cov.get("nonEmptyParagraphs") == len(PARAS), "J_paraField",
   "%r vs %d" % (cov.get("nonEmptyParagraphs"), len(PARAS)))

out_of_range = [q["quote"][:20] for _p, q in nodes if q["start"] < S or q["end"] > E]
ck(not out_of_range, "J_dontLeak", str(out_of_range[:3]))

# 汇总
result = {"quoteNodes": len(nodes), "paragraphs": len(PARAS),
          "fails": fails, "notes": notes}
print(json.dumps(result, ensure_ascii=False, indent=1))
if fails:
    print("独立复核未过：%d 条" % len(fails))
    sys.exit(1)
print("独立复核全部通过（%d 条引文 / %d 段 / %d 对 『』）"
      % (len(nodes), len(PARAS), len(corner)))

# ── M 变异自检 ────────────────────────────────────────────────────────────
if not (len(sys.argv) > 1 and sys.argv[1] == "--mutate"):
    sys.exit(0)


def run_checks(c):
    """把上面的判据压成一个纯函数，供变异使用（只支持会变红的那些）。"""
    out = []
    b = json.dumps({k: c.get(k) for k in SECTIONS}, ensure_ascii=False)
    if [x for x in re.findall(r"『([^『』]{1,600})』", b) if x not in SLICE]:
        out.append("corner")
    if re.findall(r"[「」]", b):
        out.append("thirdMarker")
    ns = []

    def col(o, p=""):
        if isinstance(o, dict):
            if "quote" in o and "start" in o and "end" in o:
                ns.append((p, o))
            for k, v in o.items():
                col(v, p + "/" + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                col(v, "%s[%d]" % (p, i))
    for name in SECTIONS:
        col(c.get(name), name)
    for p, q in ns:
        if TEXT[q["start"]:q["end"]] != q["quote"]:
            out.append("quote")
        if not (S <= q["start"] and q["end"] <= E):
            out.append("range")
        if q.get("sourceHash") != SOURCE_HASH:
            out.append("hash")
        if para_of(q["start"]) != q.get("paraLabel"):
            out.append("para")
        if sent_of(q["start"]) != q.get("sentUnit"):
            out.append("sent")
    if len(ns) == 0:
        out.append("noQuotes")
    cf = []
    for t in c.get("tasks") or []:
        r = {}
        for cc in COLUMNS:
            v = t.get(cc)
            if not v:
                continue
            for q in v.get("quotes") or []:
                k = (q["start"], q["end"])
                if k in r and r[k] != cc:
                    cf.append(1)
                r[k] = cc
    if cf:
        out.append("colConflict")
    for w in c.get("worldSettings") or []:
        if w.get("kind") == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            out.append("placeState")
        if w.get("kind") == "item" and (not w.get("itemStates") or any(
                x not in ("hold", "transfer", "use", "lose") for x in w.get("itemStates") or [])):
            out.append("itemStates")
        if w.get("kind") == "rule" and w.get("institution") not in (
                "declared", "executed", "misunderstood"):
            out.append("institution")
        if w.get("kind") not in ("place", "item", "rule"):
            out.append("kind")
    for t in c.get("tasks") or []:
        for cc in COLUMNS:
            if t.get(cc) is None and not (t.get(cc + "Note") or "").strip():
                out.append("nullNote")
    for f in c.get("foreshadows") or []:
        if f.get("status") != "resolved" and not (f.get("unresolvedReason") or "").strip():
            out.append("unresolvedReason")
        if len(f.get("quotes") or []) < 2:
            out.append("fsQuotes")
    for t in c.get("themeReadings") or []:
        if not (t.get("counter") or []):
            out.append("counter")
    pb = {r["para"]: r for r in (c.get("coverage") or {}).get("perParagraph") or []}
    for l, t, a in PARAS:
        row = pb.get(l)
        if row is None:
            out.append("covMissing"); continue
        act = sorted(touched.get(l, []))
        if row.get("state") == "quoted" and sorted(row.get("sections") or []) != act:
            out.append("covSections")
        if row.get("state") == "not-quoted" and not (row.get("note") or "").strip():
            out.append("covNote")
    return set(out)


base = run_checks(cand)
if base:
    print("基线不干净，变异无意义：%s" % sorted(base))
    sys.exit(1)

MUTS = []


def mut(name, fn, expect):
    c = copy.deepcopy(cand)
    fn(c)
    got = run_checks(c)
    MUTS.append({"name": name, "expect": expect, "got": sorted(got),
                 "redAsExpected": expect in got})


def _bump_quote(c):
    q = c["tasks"][0]["objective"]["quotes"][0]
    q["quote"] = q["quote"] + "【伪造】"


def _offset_shift(c):
    c["tasks"][0]["objective"]["quotes"][0]["start"] += 1


def _hash_swap(c):
    c["tasks"][0]["objective"]["quotes"][0]["sourceHash"] = "0" * 64


def _para_swap(c):
    c["tasks"][0]["objective"]["quotes"][0]["paraLabel"] = "P097"


def _sent_swap(c):
    c["tasks"][0]["objective"]["quotes"][0]["sentUnit"] = 99


def _range_leak(c):
    q = c["tasks"][0]["objective"]["quotes"][0]
    q["start"] = S - 1
    q["quote"] = TEXT[q["start"]:q["end"]]


def _corner_fake(c):
    c["states"][0]["before"] = c["states"][0]["before"] + "『原文里绝对没有这句伪造串』"


def _third_marker(c):
    c["states"][0]["before"] = c["states"][0]["before"] + "「伪造的第三类记号」"


def _col_conflict(c):
    # 把 obstacle 的引文换成与 objective 相同的一处 —— 真实冲突
    c["tasks"][0]["obstacle"]["quotes"] = [copy.deepcopy(c["tasks"][0]["objective"]["quotes"][0])]


def _place_bad(c):
    for w in c["worldSettings"]:
        if w.get("kind") == "place":
            w["placeState"] = "planned"   # 非法档位
            return
    raise AssertionError("没有 place 条目，变异无意义")


def _item_bad(c):
    for w in c["worldSettings"]:
        if w.get("kind") == "item":
            w["itemStates"] = ["hold", "obtain"]   # obtain 不在四态里
            return
    raise AssertionError("没有 item 条目，变异无意义")


def _inst_bad(c):
    for w in c["worldSettings"]:
        if w.get("kind") == "rule":
            w["institution"] = "customary"   # 非法档位
            return
    raise AssertionError("没有 rule 条目，变异无意义")


def _kind_bad(c):
    c["worldSettings"][0]["kind"] = "concept"


def _null_note_strip(c):
    for t in c["tasks"]:
        if t.get("cost") is None:
            t.pop("costNote", None)
            return
    raise AssertionError("没有 null cost，变异无意义")


def _fs_reason_strip(c):
    for f in c["foreshadows"]:
        if f.get("status") != "resolved":
            f.pop("unresolvedReason", None)
            return
    raise AssertionError("没有未回收伏笔，变异无意义")


def _counter_strip(c):
    c["themeReadings"][0].pop("counter", None)


def _cov_sections(c):
    for r in c["coverage"]["perParagraph"]:
        if r["state"] == "quoted":
            r["sections"] = []
            return
    raise AssertionError("没有 quoted 段")


def _cov_note_strip(c):
    for r in c["coverage"]["perParagraph"]:
        if r["state"] == "not-quoted":
            r["note"] = ""
            return
    raise AssertionError("没有 not-quoted 段")


mut("quote 尾部加伪造串 ⇒ 逐字判据变红", _bump_quote, "quote")
mut("start 偏移 +1 ⇒ 逐字判据变红", _offset_shift, "quote")
mut("sourceHash 换成全 0 ⇒ 哈希判据变红", _hash_swap, "hash")
mut("paraLabel 改成别的段 ⇒ 段号判据变红", _para_swap, "para")
mut("sentUnit 改成 99 ⇒ 句单元判据变红", _sent_swap, "sent")
mut("引文越过区间左界 ⇒ 越界判据变红", _range_leak, "range")
mut("『』 里塞伪造串 ⇒ 记号判据变红", _corner_fake, "corner")
mut("使用 「」 第三类记号 ⇒ 记号判据变红", _third_marker, "thirdMarker")
mut("两栏共用同一处引文 ⇒ 五栏独立判据变红", _col_conflict, "colConflict")
mut("placeState 改成非法档位 ⇒ 枚举判据变红", _place_bad, "placeState")
mut("itemStates 加非法态 ⇒ 枚举判据变红", _item_bad, "itemStates")
mut("institution 改成非法档位 ⇒ 枚举判据变红", _inst_bad, "institution")
mut("kind 改成非法值 ⇒ 枚举判据变红", _kind_bad, "kind")
mut("去掉 costNote ⇒ null 须带理由判据变红", _null_note_strip, "nullNote")
mut("去掉 unresolvedReason ⇒ 伏笔判据变红", _fs_reason_strip, "unresolvedReason")
mut("去掉 themeReadings.counter ⇒ 主题判据变红", _counter_strip, "counter")
mut("coverage.sections 清空 ⇒ 覆盖表判据变红", _cov_sections, "covSections")
mut("未引用段理由清空 ⇒ 覆盖表判据变红", _cov_note_strip, "covNote")

red = [m for m in MUTS if m["redAsExpected"]]
green = [m for m in MUTS if not m["redAsExpected"]]
print(json.dumps({"mutations": len(MUTS), "red": len(red),
                  "stayedGreen": [m["name"] for m in green]},
                 ensure_ascii=False, indent=1))
for m in green:
    print("  未按预期变红：%s（期望 %s，实际 %s）" % (m["name"], m["expect"], m["got"]))
(MUT := Path(__file__).resolve().parent / "mutations_0218.json").write_text(
    json.dumps(MUTS, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("变异明细已写出 %s" % MUT)
sys.exit(0 if not green else 1)
