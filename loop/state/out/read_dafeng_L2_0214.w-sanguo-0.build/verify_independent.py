# -*- coding: utf-8 -*-
"""read:dafeng:L2:0214 独立复核探针（w-sanguo-0，本轮）。

与构建脚本的关系：**不复用它的任何中间量** —— 本文件自己重新打开源文件、自己重算
sha256、自己重新切段落与句单元、自己从磁盘上的候选文件读回每一条 quote 并逐条
TEXT[start:end]==quote 复算。

判据（每条都带反例/变异，避免「扫了 0 个所以恒真」）：
  A 源哈希 = 任务 sourceHash
  B docs[0].text[S:E] 以单元标题开头、长度 3390
  C 切片 sha256 与候选 source.segmentSha256 一致
  D 逐条引文：逐字 / 区间内 / sourceHash / 双次数 / 段号 / 句单元
  E 同一任务五栏引文不共用（字符区间级 + 句单元级）
  F cost=null 必须带 costNote
  G 必需分区存在（可为空数组）
  H 枚举合法（placeState / institution / itemStates）+ basis 合法
  I 伏笔未回收必须给理由
  J 主题三件（perspective/support/counter）齐、≤2 条
  K 逐段处置覆盖全部非空段
  L 记号约定：『』 全部逐字（且对数 > 0）；〔〕不做逐字要求
  M 变异：伪造一处 『』、删一处 costNote、改一处偏移、删一个分区 —— 对应判据必须变红
用法：python3 -B -s verify_independent.py [--mutate]
"""
import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0214.candidate.json"
S, E = 796142, 799532
SH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
REQ = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]

RAW = DOCS.read_bytes()
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[S:E]
PARAS = []
_off = S
for _line in SLICE.split("\n"):
    if _line.strip():
        PARAS.append((_line.strip(), _off + (len(_line) - len(_line.lstrip()))))
    _off += len(_line) + 1
_SEP = re.compile(r"[。！？…]+")


def sent_units(t):
    o, last = [], 0
    for m in _SEP.finditer(t):
        o.append((last, m.end()))
        last = m.end()
    if last < len(t):
        o.append((last, len(t)))
    return o or [(0, len(t))]


SENT = {i: sent_units(t) for i, (t, _a) in enumerate(PARAS)}


def locate(pos):
    for i, (t, a) in enumerate(PARAS):
        if a <= pos < a + len(t):
            rel = pos - a
            for k, (x, y) in enumerate(SENT[i]):
                if x <= rel < y:
                    return "P%03d" % i, k
            return "P%03d" % i, 0
    return None, None


def run(cand, raw_text):
    fails = []

    def need(cond, label):
        if not cond:
            fails.append(label)

    need(hashlib.sha256(RAW).hexdigest() == SH, "A 源哈希")
    need(SLICE.startswith("第两百一十三章 惊愕") and len(SLICE) == E - S, "B 切片口径")
    seg = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()
    need(cand["source"]["segmentSha256"] == seg, "C 切片 sha256")

    nodes = []

    def collect(o, path=""):
        if isinstance(o, dict):
            if "quote" in o and "start" in o and "end" in o:
                nodes.append((path, o))
            for k, v in o.items():
                collect(v, path + "/" + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                collect(v, path + "[%d]" % i)

    for k in REQ + ["rejectedEdges", "knowledgeDiffs", "notForeshadows",
                    "notWorldSettings", "themeReadings", "unknowns", "selfCritique"]:
        collect(cand.get(k), k)

    for path, q in nodes:
        if TEXT[q["start"]:q["end"]] != q["quote"]:
            fails.append("D 偏移 %s" % path)
        if not (S <= q["start"] and q["end"] <= E):
            fails.append("D 越界 %s" % path)
        if q.get("sourceHash") != SH:
            fails.append("D sourceHash %s" % path)
        if q.get("wholeTextOccurrences") != TEXT.count(q["quote"]):
            fails.append("D 全文次数 %s" % path)
        if q.get("occurrencesInRange") != SLICE.count(q["quote"]):
            fails.append("D 区间次数 %s" % path)
        p, s = locate(q["start"])
        if q.get("paraLabel") != p:
            fails.append("D 段号 %s" % path)
        if q.get("sentUnit") != s:
            fails.append("D 句单元 %s" % path)

    # E 五栏不共用
    for t in cand.get("tasks", []):
        s1, s2 = {}, {}
        for col in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(col)
            if not v:
                continue
            for q in v.get("quotes", []):
                k = (q["start"], q["end"])
                if k in s1 and s1[k] != col:
                    fails.append("E 区间共用 %s %s/%s" % (t["id"], s1[k], col))
                s1[k] = col
                kk = locate(q["start"])
                if kk in s2 and s2[kk] != col:
                    fails.append("E 句单元共用 %s %s/%s %s" % (t["id"], s2[kk], col, kk))
                s2[kk] = col
    # F cost
    for t in cand.get("tasks", []):
        if t.get("cost") is None and not t.get("costNote"):
            fails.append("F %s.cost 无 Note" % t["id"])
    # G
    for k in REQ:
        need(k in cand, "G 分区缺失 %s" % k)
    # H
    LEGAL = {"explicit", "inferred", "derived", "unverified"}
    for w in cand.get("worldSettings", []):
        if w["kind"] == "place":
            need(w.get("placeState") in ("arrived", "mentioned"), "H place %s" % w["id"])
        if w["kind"] == "rule":
            need(w.get("institution") in ("declared", "executed", "misunderstood"),
                 "H rule %s" % w["id"])
        if w["kind"] == "item":
            st = w.get("itemStates")
            need(isinstance(st, list) and st and all(
                x in ("hold", "transfer", "use", "lose") for x in st), "H item %s" % w["id"])
        need(w.get("basis") in LEGAL, "H basis %s" % w["id"])
    # I
    for f in cand.get("foreshadows", []):
        if f.get("status") == "unresolved":
            need(bool(f.get("unresolvedReason")), "I %s 未回收无理由" % f["id"])
        need(len(f.get("quotes") or []) >= 2, "I %s 引文<2" % f["id"])
    # J
    need(len(cand.get("themeReadings", [])) <= 2, "J 主题>2")
    for t in cand.get("themeReadings", []):
        need(bool(t.get("perspective")) and bool(t.get("support")) and bool(t.get("counter")),
             "J 主题三件 %s" % t.get("id"))
    # K
    disp = {d["para"]: d for d in cand.get("coverage", {}).get("perParagraph", [])}
    covered = set()
    for _p, q in nodes:
        pp, _s = locate(q["start"])
        if pp:
            covered.add(pp)
    for i in range(len(PARAS)):
        lab = "P%03d" % i
        if lab in covered:
            need(disp.get(lab, {}).get("state") == "quoted", "K %s 应标 quoted" % lab)
        else:
            d = disp.get(lab)
            need(d is not None and d.get("state") == "not-quoted" and bool(d.get("note")),
                 "K %s 未处置或缺理由" % lab)
    # L 记号
    blob = json.dumps({k: cand.get(k) for k in REQ + ["rejectedEdges", "knowledgeDiffs",
                                                      "notForeshadows", "notWorldSettings",
                                                      "unknowns", "selfCritique"]},
                      ensure_ascii=False)
    corner = re.findall(r"『([^『』]{1,400})』", blob)
    nonverbatim = [x for x in corner if x not in SLICE]
    need(len(corner) > 0, "L 『』 对数 0 ⇒ 判据恒真")
    need(not nonverbatim, "L 『』 非逐字 %s" % nonverbatim[:3])
    return fails, len(nodes), len(corner), nonverbatim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutate", action="store_true")
    args = ap.parse_args()
    cand = json.loads(CAND.read_text("utf-8"))
    fails, n, ncorner, nonverb = run(cand, None)
    print("引文节点 %d；『』 对数 %d；非逐字 %d" % (n, ncorner, len(nonverb)))
    print("判据失败：%d" % len(fails))
    for f in fails[:20]:
        print("  -", f)
    print("总判：%s" % ("ALL PASS" if not fails else "FAIL"))
    if not args.mutate:
        return 0 if not fails else 1

    print("\n=== 变异自检（只在内存副本上做，真候选哈希不变）===")
    muts = []
    m = copy.deepcopy(cand)
    m["tasks"][0]["objective"]["quotes"][0]["quote"] = "这段文字原文里绝对没有出现过纯属伪造"
    muts.append(("伪造引文字符串", m, "D 偏移"))
    m = copy.deepcopy(cand)
    m["tasks"][0]["objective"]["quotes"][0]["start"] += 1
    muts.append(("偏移 +1", m, "D 偏移"))
    m = copy.deepcopy(cand)
    for t in m["tasks"]:
        t.pop("costNote", None)
    muts.append(("删除 costNote", m, "F"))
    m = copy.deepcopy(cand)
    m["tasks"][0]["obstacle"]["quotes"] = copy.deepcopy(m["tasks"][0]["objective"]["quotes"])
    muts.append(("两栏共用同一引文", m, "E"))
    m = copy.deepcopy(cand)
    m.pop("foreshadows")
    muts.append(("删除分区 foreshadows", m, "G"))
    m = copy.deepcopy(cand)
    # 第一版变异写成「把 rule 改成 place + arrived」——那**仍是一个合法对象**，
    # 所以判据 H 合理地不变红；这是变异本身写错了，不是判据失效。
    # 改成真正的非法枚举值：placeState 用了计划明令禁止的「图谋」档。
    m["worldSettings"][0].update({"kind": "place", "placeState": "planned"})
    m["worldSettings"][0]["id"] = "MUT"
    muts.append(("placeState 用非法档位", m, "H"))
    m = copy.deepcopy(cand)
    for f in m["foreshadows"]:
        f.pop("unresolvedReason", None)
    muts.append(("删伏笔未回收理由", m, "I"))
    m = copy.deepcopy(cand)
    m["themeReadings"][0].pop("counter")
    muts.append(("删主题反例", m, "J"))
    m = copy.deepcopy(cand)
    m["coverage"]["perParagraph"][3]["note"] = ""
    muts.append(("清空零覆盖段理由", m, "K"))
    m = copy.deepcopy(cand)
    blob = json.dumps(m, ensure_ascii=False).replace("『果然还是纸做的』",
                                                     "『原文里绝对没有的伪造串』", 1)
    m = json.loads(blob)
    muts.append(("伪造 『』 非逐字串", m, "L"))
    ok = True
    for name, mm, expect in muts:
        f2, _a, _b, _c = run(mm, None)
        red = any(x.startswith(expect) for x in f2)
        print("  [%s] %s ⇒ %s" % ("变红✓" if red else "未变红✗", name, expect))
        ok = ok and red
    # 真文件哈希前后不变
    after = hashlib.sha256(CAND.read_bytes()).hexdigest()
    print("真候选哈希（变异后重算）：%s" % after[:16])
    print("变异自检：%s" % ("全部按预期变红" if ok else "有变异未变红"))
    return 0 if (ok and not fails) else 1


if __name__ == "__main__":
    sys.exit(main())
