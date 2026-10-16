#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L2:0230 独立重算（w-xiyou-0）。

独立性声明（这是它存在的理由）：
  · **不 import** build_candidate.py，也不 import content_a/content_b ——
    从磁盘上的候选 JSON 重新读起，源文件重新打开，哈希重算；
  · 段落与句单元在本脚本内**另行切分**一遍，不使用候选里的 paraLabel 作为输入；
  · 240 条引文逐条重新 find + 现算偏移 + 现算全文/区间次数；
  · 判据 7b 用**变异测试**证明引文判据真的会红（把一条引文改坏 ⇒ 必须报 FAIL），
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
CAND = ROOT / "loop/state/out/read_dafeng_L2_0230.candidate.json"
SOURCE = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L2_0230.json"

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
    ps_bad = []
    for path, s, e, qt in records:
        # 找到包含该引文的段（本脚本的切分）
        hit = None
        for lab, (a, b, t) in my_paras.items():
            if a <= s and e <= b:
                hit = lab
                break
        if hit is None:
            ps_bad.append((path, "不在任何段内"))
            continue
        units = my_sent[hit]
        acc, ui = 0, 0
        off = s - my_paras[hit][0]
        for i, u in enumerate(units):
            if acc <= off < acc + len(u):
                ui = i
                break
            acc += len(u)
        ps_bad.append((path, hit, ui))
    mismatch = []
    for (path, s, e, qt), (p2, lab, ui) in zip(records, ps_bad):
        cand_q = None
        for pp, q in walk_quotes(cand):
            if pp == path:
                cand_q = q
                break
        if cand_q and (cand_q.get("paraLabel") != lab or cand_q.get("sentUnit") != ui):
            mismatch.append((path, cand_q.get("paraLabel"), lab, cand_q.get("sentUnit"), ui))
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
                seen.setdefault(q["quote"], []).append(c)
        for qt, cs in seen.items():
            if len(cs) > 1:
                conf.append((t["id"], cs, qt[:30]))
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                a_, b_ = t.get(cols[i]), t.get(cols[j])
                if not isinstance(a_, dict) or not isinstance(b_, dict):
                    continue
                for x in a_.get("quotes", []):
                    for y in b_.get("quotes", []):
                        if x["start"] < y["end"] and y["start"] < x["end"]:
                            conf.append((t["id"], cols[i], cols[j], "跨度重叠"))
    rec("C06_taskColumnsDisjoint", not conf,
        "五元组五栏零共用（字符串级+跨度级）" if not conf else "冲突：%r" % (conf[:3],))

    # C07 worldSettings 引文零复用
    seen_w = {}
    for w in cand["worldSettings"]:
        for q in w.get("quotes", []):
            seen_w.setdefault(q["quote"], []).append(w["id"])
    wconf = [(v, k[:30]) for k, v in seen_w.items() if len(v) > 1]
    rec("C07_worldSettingsDisjoint", not wconf,
        "各条设定依据独立" if not wconf else "复用：%r" % (wconf[:3],))

    # C08 null 栏均有同名 Note
    np_ = []
    for t in cand["tasks"]:
        for c in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(c) is None and not t.get(c + "Note"):
                np_.append((t["id"], c))
            if t.get(c) is not None and t.get(c + "Note"):
                np_.append((t["id"], c, "非 null 却带 Note"))
    rec("C08_nullColumnsHaveNote", not np_, "null 栏均带理由" if not np_ else "问题：%r" % (np_,))

    # C09 判别字段合法
    ws_bad = []
    for w in cand["worldSettings"]:
        k = w.get("kind")
        if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            ws_bad.append((w["id"], "institution"))
        elif k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            ws_bad.append((w["id"], "placeState"))
        elif k == "item":
            st = w.get("itemStates")
            if (not isinstance(st, list) or not st
                    or any(x not in ("hold", "transfer", "use", "lose") for x in st)):
                ws_bad.append((w["id"], "itemStates"))
        elif k not in ("rule", "place", "item"):
            ws_bad.append((w["id"], "kind"))
    rec("C09_worldSettingDiscriminants", not ws_bad,
        "kind/placeState/itemStates/institution 四级判别字段合法" if not ws_bad
        else "非法：%r" % (ws_bad,))

    # C10 必需分区存在
    need = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
    miss = [k for k in need if k not in cand]
    rec("C10_requiredSections", not miss, "六个必需分区存在" if not miss else "缺：%r" % (miss,))

    # C11 basis 合法
    legal = ("explicit", "inferred", "derived", "unverified")
    b_bad = []

    def scan_basis(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "basis" and v not in legal:
                    b_bad.append((path, v))
                else:
                    scan_basis(v, path + "/" + str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                scan_basis(v, path + "[%d]" % i)
    scan_basis(cand)
    rec("C11_basisValuesLegal", not b_bad, "basis 取值合法" if not b_bad else "非法：%r" % (b_bad[:3],))

    # C12 角标：『』/「」必须逐字（跳过约定说明行）
    nonverbatim = []
    for p, s in walk_strings(cand):
        if any(mk in s for mk in META_MARKERS):
            continue
        for m in VERBATIM_RE.finditer(s):
            if m.group(1) not in text:
                nonverbatim.append((p, m.group(1)[:30]))
    rec("C12_cornerSpansVerbatim", not nonverbatim,
        "『』/「」跨度全部逐字命中" if not nonverbatim
        else "非逐字 %d 处：%r" % (len(nonverbatim), nonverbatim[:3]))

    # C13 〔〕必须是原文里没有的串（否则应写成逐字跨度）
    myword = []
    for p, s in walk_strings(cand):
        if any(mk in s for mk in META_MARKERS):
            continue
        for m in MYWORD_RE.finditer(s):
            if m.group(1) in text:
                myword.append((p, m.group(1)[:30]))
    rec("C13_myWordNotInSource", not myword,
        "〔〕全部是原文里没有的措辞" if not myword else "误标：%r" % (myword[:3],))

    # C14 变异测试：把引文改坏后，C04 必须变红（证明判据真的会报）
    mutated = json.loads(json.dumps(cand))
    q0 = next(walk_quotes(mutated))[1]
    q0["quote"] = q0["quote"][:-1] + ("X" if q0["quote"][-1] != "X" else "Y")
    m_bad, _n, _r = check_quotes(mutated, text, lo, hi)
    off_mut = json.loads(json.dumps(cand))
    q1 = next(walk_quotes(off_mut))[1]
    q1["start"] = q1["start"] + 1
    m_bad2, _n2, _r2 = check_quotes(off_mut, text, lo, hi)
    ok_mut = bool(m_bad) and bool(m_bad2)
    rec("C14_mutationMakesItRed", ok_mut,
        "改坏引文/偏移后 C04 判据如期报红（%d 处 / %d 处）" % (len(m_bad), len(m_bad2))
        if ok_mut else "变异未被发现 —— 判据形同不存在")

    # C15 语义自陈：不得声称 semanticReview 完成
    rec("C15_semanticReviewNotClaimed", cand.get("semanticReview") == "not-performed",
        "semanticReview=%r（未声称完成）" % cand.get("semanticReview"))

    fails = [r for r in results if not r[1]]
    say("")
    say("总结论：%s" % ("全部 PASS" if not fails else "存在 FAIL，见上（%d 项）" % len(fails)))
    say("引文节点：%d；非空段：%d（本脚本独立切分）" % (n_quotes, len(my_paras)))
    out = "\n".join(lines) + "\n"
    if write:
        (HERE / "verify_independent_report.txt").write_text(out, encoding="utf-8")
        say("已写报告：verify_independent_report.txt")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
