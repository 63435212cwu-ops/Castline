#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L2:0234 独立重算（w-xiyou-0）。

独立性声明（这是它存在的理由）：
  · **不 import** build_candidate.py，也不 import content_a/content_b ——
    从磁盘上的候选 JSON 重新读起，源文件重新打开，哈希重算；
  · 段落与句单元在本脚本内**另行切分**一遍，不使用候选里的 paraLabel 作为输入；
  · 264 条引文逐条重新 find + 现算偏移 + 现算全文/区间次数；
  · 判据 C14 用**变异测试**证明引文判据真的会红（把一条引文的末尾字符改坏、
    把另一条的 start 偏移 +1，两条都必须让 C04 报红），
    否则「全 PASS」可能只是因为判据从没生效过。

用法：
  python3 -B -s verify_independent.py            # 重算并打印报告
  python3 -B -s verify_independent.py --write    # 同时写 verify_independent_report.txt
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAND = ROOT / "loop/state/out/read_dafeng_L2_0234.candidate.json"
SOURCE = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L2_0234.json"

VERBATIM_RE = re.compile(r"[『「]([^『』「」\n]{1,120})[』」]")
MYWORD_RE = re.compile(r"〔([^〔〕\n]{1,120})〕")
META_MARKERS = ("『…』", "〔…〕")


def sha256_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sent_units_here(t):
    """本脚本独立实现的句单元切分（不复用构建脚本的任何代码）。"""
    out, buf = [], ""
    for ch in t:
        buf += ch
        if ch in "。！？”…":
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return out


def paras_here(text, start, end):
    seg = text[start:end]
    out = []
    for i, m in enumerate(re.finditer(r"[^\n]+", seg)):
        out.append(("P%03d" % i, start + m.start(), start + m.end(), m.group(0)))
    return out


def walk_quotes(node, path=""):
    if isinstance(node, dict):
        if isinstance(node.get("quotes"), list):
            for j, q in enumerate(node["quotes"]):
                if isinstance(q, dict) and "quote" in q:
                    yield path + "/quotes[%d]" % j, q
        for k, v in node.items():
            if k == "quotes":
                continue
            yield from walk_quotes(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quotes(v, path + "[%d]" % i)


def walk_strings(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("quote", "quotes"):
                continue
            yield from walk_strings(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, path + "[%d]" % i)
    elif isinstance(node, str):
        yield path, node


def check_quotes(cand, text, lo, hi):
    """返回 (失败列表, 引文总数, 每条引文的检查记录)。"""
    bad = []
    n = 0
    records = []
    for path, q in walk_quotes(cand):
        n += 1
        s, e, qt = q.get("start"), q.get("end"), q.get("quote")
        if not isinstance(s, int) or not isinstance(e, int):
            bad.append((path, "偏移缺失"))
            continue
        if text[s:e] != qt:
            bad.append((path, "TEXT[start:end] != quote"))
        if not (lo <= s and e <= hi):
            bad.append((path, "越出区间"))
        if q.get("sourceHash") != cand["source"]["sourceHash"]:
            bad.append((path, "sourceHash 不等"))
        if q.get("wholeTextOccurrences") != text.count(qt):
            bad.append((path, "全文次数不符"))
        if q.get("occurrencesInRange") != text[lo:hi].count(qt):
            bad.append((path, "区间次数不符"))
        records.append((path, s, e, qt))
    return bad, n, records


def main():
    write = "--write" in sys.argv
    lines = []

    def say(s=""):
        lines.append(s)
        print(s)

    cand = json.loads(CAND.read_text(encoding="utf-8"))
    task = json.loads(TASK.read_text(encoding="utf-8"))
    raw = SOURCE.read_bytes()
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    lo, hi = task["sourceRange"]
    results = []

    def rec(name, ok, detail):
        results.append((name, ok, detail))
        say("  %-34s %s   %s" % (name, "PASS" if ok else "FAIL", detail))

    say("=" * 72)
    say("%s 独立重算（本脚本自行切分段落/句单元，未 import 构建脚本）" % cand["task"])
    say("=" * 72)

    # C01 三方哈希
    h_file = hashlib.sha256(raw).hexdigest()
    rec("C01_sourceHash", h_file == task["sourceHash"] == cand["source"]["sourceHash"],
        "源文件/候选/任务三方哈希一致" if h_file == task["sourceHash"] == cand["source"]["sourceHash"]
        else "不一致：file=%s task=%s cand=%s" % (h_file[:12], task["sourceHash"][:12],
                                              cand["source"]["sourceHash"][:12]))

    # C02 切片以标题开头 + 切片哈希
    seg = text[lo:hi]
    seg_ok = seg.startswith(task["unitHead"])
    seg_h = hashlib.sha256(seg.encode("utf-8")).hexdigest()
    rec("C02_sliceStartsWithUnitHead", seg_ok and seg_h == cand["source"]["segmentSha256"],
        "以标题开头且切片哈希一致" if seg_ok else "切片不以标题开头")

    # C03 range 与任务一致
    rec("C03_rangeMatchesTask", cand["source"]["range"] == list(task["sourceRange"])
        and cand["source"]["codepoints"] == hi - lo,
        "range/codepoints 与任务一致")

    # C04 引文逐字 + 区间内 + 哈希 + 次数
    bad, n_quotes, records = check_quotes(cand, text, lo, hi)
    rec("C04_quotesVerbatim", not bad, "%d 条引文逐字成立（本脚本重新 find）" % n_quotes
        if not bad else "失败 %d 处：%r" % (len(bad), bad[:3]))

    # C05 段号与句单元（本脚本独立切分）
    my_paras = {lab: (a, b, t) for lab, a, b, t in paras_here(text, lo, hi)}
    my_sent = {lab: sent_units_here(t) for lab, (_a, _b, t) in my_paras.items()}
    mismatch = []
    for path, s, e, qt in records:
        hit = None
        for lab, (a, b, t) in my_paras.items():
            if a <= s and e <= b:
                hit = lab
                break
        if hit is None:
            mismatch.append((path, "不在任何段内"))
            continue
        units = my_sent[hit]
        off = s - my_paras[hit][0]
        acc, ui = 0, 0
        for i, u in enumerate(units):
            if acc <= off < acc + len(u):
                ui = i
                break
            acc += len(u)
        cand_q = None
        for pp, q in walk_quotes(cand):
            if pp == path:
                cand_q = q
                break
        if cand_q and (cand_q.get("paraLabel") != hit or cand_q.get("sentUnit") != ui):
            mismatch.append((path, cand_q.get("paraLabel"), hit, cand_q.get("sentUnit"), ui))
    rec("C05_paragraphAndSentUnit", not mismatch,
        "段号与句单元由本脚本独立切分判定（%d 段）" % len(my_paras)
        if not mismatch else "不符 %d 处：%r" % (len(mismatch), mismatch[:3]))

    # C06 任务五栏零共用（字符串级 + 跨度级）
    conf = []
    for t in cand["tasks"]:
        cols = ["objective", "obstacle", "action", "result", "cost"]
        seen = {}
        for c in cols:
            col = t.get(c)
            if not isinstance(col, dict):
                continue
            for q in col.get("quotes", []):
                if q["quote"] in seen:
                    conf.append((t["id"], seen[q["quote"]], c, q["quote"][:25]))
                seen[q["quote"]] = c
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                a, b = t.get(cols[i]), t.get(cols[j])
                if not isinstance(a, dict) or not isinstance(b, dict):
                    continue
                for qa in a.get("quotes", []):
                    for qb in b.get("quotes", []):
                        if qa["start"] < qb["end"] and qb["start"] < qa["end"]:
                            conf.append((t["id"], cols[i], cols[j], "跨度重叠"))
    rec("C06_taskColumnsDisjoint", not conf, "五元组五栏零共用（字符串级+跨度级）"
        if not conf else "共用 %d 处：%r" % (len(conf), conf[:3]))

    # C07 worldSettings 各条依据独立
    seen_w, wconf = {}, []
    for w in cand["worldSettings"]:
        for q in w.get("quotes", []):
            if q["quote"] in seen_w:
                wconf.append((seen_w[q["quote"]], w["id"], q["quote"][:25]))
            seen_w[q["quote"]] = w["id"]
    for i in range(len(cand["worldSettings"])):
        for j in range(i + 1, len(cand["worldSettings"])):
            for qa in cand["worldSettings"][i].get("quotes", []):
                for qb in cand["worldSettings"][j].get("quotes", []):
                    if qa["start"] < qb["end"] and qb["start"] < qa["end"]:
                        wconf.append((cand["worldSettings"][i]["id"],
                                      cand["worldSettings"][j]["id"], "跨度重叠"))
    rec("C07_worldSettingsDisjoint", not wconf, "各条设定依据独立"
        if not wconf else "复用 %d 处：%r" % (len(wconf), wconf[:3]))

    # C08 null 栏均带理由
    nbad = []
    for t in cand["tasks"]:
        for c in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(c) is None and not t.get(c + "Note"):
                nbad.append((t["id"], c))
            if t.get(c) is not None and t.get(c + "Note"):
                nbad.append((t["id"], c, "非 null 却带 Note"))
    rec("C08_nullColumnsHaveNote", not nbad, "null 栏均带理由" if not nbad else "问题：%r" % (nbad[:3],))

    # C09 判别字段合法
    dbad = []
    for w in cand["worldSettings"]:
        k = w.get("kind")
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            dbad.append((w["id"], "institution"))
        elif k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            dbad.append((w["id"], "placeState"))
        elif k == "item":
            st = w.get("itemStates")
            if (not isinstance(st, list) or not st
                    or any(s not in ("hold", "transfer", "use", "lose") for s in st)):
                dbad.append((w["id"], "itemStates"))
        elif k not in ("rule", "place", "item"):
            dbad.append((w["id"], "kind"))
    rec("C09_worldSettingDiscriminants", not dbad,
        "kind/placeState/itemStates/institution 四级判别字段合法" if not dbad else "非法：%r" % (dbad[:3],))

    # C10 必需分区
    need = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
    miss = [k for k in need if k not in cand]
    rec("C10_requiredSections", not miss, "六个必需分区存在" if not miss else "缺：%r" % (miss,))

    # C11 basis 合法
    legal = ("explicit", "inferred", "derived", "unverified")
    bbad = []

    def scan_basis(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "basis" and v not in legal:
                    bbad.append(v)
                else:
                    scan_basis(v)
        elif isinstance(node, list):
            for v in node:
                scan_basis(v)
    scan_basis(cand)
    rec("C11_basisValuesLegal", not bbad, "basis 取值合法" if not bbad else "非法：%r" % (bbad[:3],))

    # C12 『』/「」跨度全部逐字
    nv = []
    for path, s in walk_strings(cand):
        for m in VERBATIM_RE.finditer(s):
            if m.group(1) not in text:
                nv.append((path, m.group(1)[:30]))
    rec("C12_cornerSpansVerbatim", not nv,
        "『』/「」跨度全部逐字命中" if not nv else "非逐字 %d 处：%r" % (len(nv), nv[:3]))

    # C13 〔〕全部是原文里没有的措辞
    mw = []
    for path, s in walk_strings(cand):
        for m in MYWORD_RE.finditer(s):
            if m.group(1) in text:
                mw.append((path, m.group(1)[:30]))
    rec("C13_myWordNotInSource", not mw,
        "〔〕全部是原文里没有的措辞" if not mw else "误标 %d 处：%r" % (len(mw), mw[:3]))

    # C14 变异测试：改坏引文 / 挪偏移，C04 必须报红
    mut_q = json.loads(json.dumps(cand))
    first = next(walk_quotes(mut_q))[1]
    first["quote"] = first["quote"][:-1] + ("X" if not first["quote"].endswith("X") else "Y")
    bad_a, _n, _r = check_quotes(mut_q, text, lo, hi)
    mut_q2 = json.loads(json.dumps(cand))
    second = list(walk_quotes(mut_q2))[1][1]
    second["start"] = second["start"] + 1
    bad_b, _n, _r = check_quotes(mut_q2, text, lo, hi)
    rec("C14_mutationMakesItRed", bool(bad_a) and bool(bad_b),
        "改坏引文/偏移后 C04 判据如期报红（%d 处 / %d 处）" % (len(bad_a), len(bad_b)))

    # C15 未声称 semanticReview 完成
    rec("C15_semanticReviewNotClaimed", cand.get("semanticReview") == "not-performed",
        "semanticReview='not-performed'（未声称完成）")

    n_fail = sum(1 for _n, ok, _d in results if not ok)
    say("")
    say("总结论：%s" % ("全部 PASS" if n_fail == 0 else "有 %d 项 FAIL" % n_fail))
    say("引文节点：%d；非空段：%d（本脚本独立切分）" % (n_quotes, len(my_paras)))
    if write:
        (HERE / "verify_independent_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("已写 %s" % (HERE / "verify_independent_report.txt"))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
