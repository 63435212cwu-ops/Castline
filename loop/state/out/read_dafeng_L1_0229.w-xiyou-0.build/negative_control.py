# -*- coding: utf-8 -*-
"""阴性对照：把产物**故意改坏**，证明审计判据 A1–A16 真的会触发。

为什么需要这个文件：一个从不失败的检查器与一个没有检查器是一样的。
前一轮的教训是「判据在旧缺陷文本上必须触发、在当前文本上必须不触发」。
本脚本对每一种缺陷各造一份**内存中的**副本（不落盘、不覆盖产物），
在只读模式下跑审计的同一套判据函数，断言它确实返回失败。

退出码：全部缺陷都被抓到 → 0；有任何一种缺陷**没被抓到** → 1（说明判据给了假绿灯）。
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0229.candidate.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
QUOTE_KEYS = ("quotes", "supportQuotes", "counterQuotes")

text = json.loads(DOCS.read_bytes())[0]["text"]
BASE = json.loads(CAND.read_bytes())


def walk_quotes(node, path="root"):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in QUOTE_KEYS and isinstance(v, list):
                for i, q in enumerate(v):
                    yield "%s.%s[%d]" % (path, k, i), q
            else:
                yield from walk_quotes(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quotes(v, "%s[%d]" % (path, i))


def check(cand):
    """返回失败判据 id 的集合（是 audit_candidate.py 判据的只读镜像）。"""
    bad = set()
    S, E = cand["sourceRange"]
    slice_ = text[S:E]
    if cand.get("sourceHash") != SOURCE_HASH:
        bad.add("A1")
    if hashlib.sha256(slice_.encode()).hexdigest() != cand.get("sliceSha256"):
        bad.add("A2")
    starts = []
    for where, q in walk_quotes(cand):
        if not isinstance(q, dict) or "start" not in q:
            bad.add("A3")
            continue
        s, e, quote = q["start"], q["end"], q["quote"]
        if text[s:e] != quote:
            bad.add("A3")
            continue
        if s < S or e > E:
            bad.add("A6")
        if slice_.count(quote) != 1:
            bad.add("A4")
        if q.get("sourceHash") != SOURCE_HASH:
            bad.add("A5")
        starts.append((s, e))
    blob = json.dumps(cand, ensure_ascii=False)
    if re.search(r"\{q\d+\}", blob):
        bad.add("A7")
    if re.search(r"偏移\s*\d+", blob):
        nums = {int(m) for m in re.findall(r"偏移\s*(\d+)", blob)}
        if nums - {s for s, _ in starts}:
            bad.add("A7b")
    for t in (cand.get("tasks") or []):
        seen = []
        for f in ("objective", "obstacle", "action", "result", "cost"):
            cell = t.get(f)
            if not isinstance(cell, dict):
                continue
            for q in cell.get("quotes") or []:
                a, b = q["start"], q["end"]
                for a2, b2, f2 in seen:
                    if a < b2 and a2 < b:
                        bad.add("A8")
                seen.append((a, b, f))
    for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
        if not isinstance(cand.get(k), list):
            bad.add("A9")
    for t in (cand.get("tasks") or []):
        c = t.get("cost")
        if isinstance(c, dict):
            s = json.dumps(c, ensure_ascii=False)
            if any(x in s for x in ("待验证", "待核", "待确认")) or re.search(r"(法律规定|禁令)", s):
                bad.add("A10")
    if (cand.get("semanticReview") or {}).get("status") != "not_performed":
        bad.add("A11")
    paras, off = [], S
    for chunk in slice_.split("\n"):
        paras.append((off, off + len(chunk), chunk))
        off += len(chunk) + 1
    nonempty = [p for p in paras if p[2].strip()]
    spans = sorted(set(starts))
    touched = sum(1 for a, b, _ in nonempty if any(a < e and s < b for s, e in spans))
    cov = cand.get("coverage") or {}
    if cov.get("paragraphsTouchedByQuotes") != touched:
        bad.add("A12")
    for t in (cand.get("tasks") or []):
        for f in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(f) is None and not (t.get(f + "Note") or "").strip():
                bad.add("A13")
    for w in (cand.get("worldSettings") or []):
        if w.get("kind") == "place" and w.get("placeState") not in ("arrived", "mentioned"):
            bad.add("A14")
        if w.get("kind") == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
            bad.add("A14")
    for f in (cand.get("foreshadows") or []):
        if f.get("status") == "unresolved" and not f.get("payoffNote"):
            bad.add("A15")
        if f.get("status") == "resolved" and not f.get("payoff"):
            bad.add("A15")
    for e in (cand.get("causeEdges") or []):
        if not e.get("from") or not e.get("to") or len(e.get("mechanism") or "") <= 30:
            bad.add("A16")
    # A18：自述的 null 计数必须与正文实际一致
    nulls = sum(1 for t in (cand.get("tasks") or [])
                for f in ("objective", "obstacle", "action", "result", "cost") if t.get(f) is None)
    claims = re.findall(r"(\d+)\s*个(?:裸\s*)?null", cand.get("tasksNote") or "")
    if not claims or any(int(n) != nulls for n in claims):
        bad.add("A18")
    return bad


def first_q(cand):
    for _, q in walk_quotes(cand):
        return q
    raise SystemExit("no quotes")


MUTANTS = []


def mutant(mid, expect, fn):
    c = copy.deepcopy(BASE)
    fn(c)
    MUTANTS.append((mid, expect, c))


mutant("m1_start_off_by_one", "A3", lambda c: first_q(c).__setitem__("start", first_q(c)["start"] + 1))
mutant("m2_quote_mutated", "A3", lambda c: first_q(c).__setitem__("quote", first_q(c)["quote"] + "。"))
mutant("m3_sourcehash_wrong", "A5", lambda c: first_q(c).__setitem__("sourceHash", "0" * 64))
mutant("m4_range_out", "A6", lambda c: (first_q(c).__setitem__("start", 1), first_q(c).__setitem__("end", 2),
                                        first_q(c).__setitem__("quote", text[1:2])))
mutant("m5_placeholder_left", "A7",
       lambda c: c.__setitem__("tasksNote", (c.get("tasksNote") or "") + " 残留 {q0}"))
mutant("m6_fake_offset", "A7b", lambda c: c.__setitem__(
    "offsetCaliber", (c.get("offsetCaliber") or "") + " 见偏移 999999"))
mutant("m7_dup_quote_two_fields", "A8", lambda c: c["tasks"][0].__setitem__(
    "obstacle", {"text": "x", "basis": "explicit",
                 "quotes": [dict(c["tasks"][0]["objective"]["quotes"][0])]}))
mutant("m8_missing_section", "A9", lambda c: c.pop("worldSettings"))
mutant("m9_cost_hedge", "A10", lambda c: c["tasks"][2]["cost"].__setitem__(
    "text", (c["tasks"][2]["cost"]["text"] or "") + "（待核）"))
mutant("m10_cost_law", "A10", lambda c: c["tasks"][2]["cost"].__setitem__(
    "text", (c["tasks"][2]["cost"]["text"] or "") + " 法律规定应当罚俸"))
mutant("m11_semantic_done", "A11", lambda c: c["semanticReview"].__setitem__("status", "done"))
mutant("m12_coverage_lie", "A12", lambda c: c["coverage"].__setitem__(
    "paragraphsTouchedByQuotes", c["coverage"]["paragraphsTouchedByQuotes"] + 50))
mutant("m13_null_no_note", "A13", lambda c: c["tasks"][0].pop("costNote"))
mutant("m14_place_no_state", "A14", lambda c: [w.pop("placeState") for w in c["worldSettings"]
                                                if w.get("kind") == "place"])
mutant("m15_unresolved_no_note", "A15", lambda c: [f.pop("payoffNote", None) for f in c["foreshadows"]
                                                    if f.get("status") == "unresolved"])
mutant("m16_edge_no_mechanism", "A16", lambda c: c["causeEdges"][0].__setitem__("mechanism", "时间相邻"))
mutant("m17_selfcount_lie", "A18", lambda c: c.__setitem__(
    "tasksNote", (c.get("tasksNote") or "").replace("5 个裸 null", "8 个裸 null")))


def main():
    # 先证明未改坏的产物**不触发**任何判据（否则阴性对照没有意义）
    base_bad = check(BASE)
    if base_bad:
        print("[FAIL] 未改坏的原产物就触发了判据：%s（阴性对照失去意义）" % sorted(base_bad),
              file=sys.stderr)
        return 1
    print("基线：原产物不触发任何判据（%d 条引文实例）" % sum(1 for _ in walk_quotes(BASE)))

    missed = []
    for mid, expect, c in MUTANTS:
        got = check(c)
        hit = expect in got
        print("  %-24s 期望 %-4s → 实际命中 %-18s %s"
              % (mid, expect, sorted(got) or "（无）", "OK" if hit else "**没抓到**"))
        if not hit:
            missed.append(mid)
    if missed:
        print("\n阴性对照失败：%d 种缺陷没被抓到 → %s" % (len(missed), missed), file=sys.stderr)
        return 1
    print("\n阴性对照通过：%d 种故意缺陷全部被抓到，且原产物一个都不触发" % len(MUTANTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
