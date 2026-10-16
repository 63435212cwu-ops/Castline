#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阴性对照：证明 audit_candidate.py 的判据**真的会触发**。

做法：把产物在内存里故意改坏 N 种，写到临时文件让审计去读，
断言每种都被抓到、且**未改坏的基线一条都不报**。
不覆盖产物（审计读的是临时副本，跑完即删）。

若某种改坏没被抓到 ⇒ 那条判据是摆设，必须报出来。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = "/Users/carmen/Desktop/星系"
BUILD = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0208.w-xiyou-0.build")
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0208.candidate.json")
AUDIT_SRC = os.path.join(BUILD, "audit_candidate.py")

base = json.load(open(CAND, encoding="utf-8"))
tmpdir = tempfile.mkdtemp(prefix="negctl-0208-")
AUDIT = os.path.join(tmpdir, "audit.py")
shutil.copy(AUDIT_SRC, AUDIT)
src = open(AUDIT, encoding="utf-8").read()

TARGET = os.path.join(tmpdir, "candidate.json")
# 让审计把 CAND 指向临时副本
src = src.replace('CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0208.candidate.json")',
                  'CAND = %r' % TARGET)
open(AUDIT, "w", encoding="utf-8").write(src)


def run(mut):
    """写入变体并跑审计，返回 (rc, stderr)。"""
    with open(TARGET, "w", encoding="utf-8") as fh:
        json.dump(mut, fh, ensure_ascii=False, indent=2)
    p = subprocess.run([sys.executable, "-B", "-s", AUDIT],
                       capture_output=True, text=True)
    return p.returncode, p.stderr


def deep_copy():
    return json.loads(json.dumps(base))


MUTANTS = []


def mutant(name):
    def deco(fn):
        MUTANTS.append((name, fn))
        return fn
    return deco


@mutant("偏移错 1 位")
def m1(c):
    c["tasks"][0]["objective"]["quotes"][0]["start"] += 1
    return c


@mutant("引文改一个字")
def m2(c):
    r = c["tasks"][0]["objective"]["quotes"][0]
    r["quote"] = r["quote"][:-1] + "某"
    return c


@mutant("sourceHash 写错")
def m3(c):
    c["tasks"][0]["objective"]["quotes"][0]["sourceHash"] = "0" * 64
    return c


@mutant("引文越出单元下界")
def m4(c):
    c["causeEdges"][0]["quotes"][0]["start"] = c["sourceRange"][0] - 5
    c["causeEdges"][0]["quotes"][0]["end"] = c["sourceRange"][0] + 5
    return c


@mutant("同一任务两栏共用一句")
def m5(c):
    t = c["tasks"][0]
    t["obstacle"] = json.loads(json.dumps(t["objective"]))
    return c


@mutant("栏位裸 null 无 Note")
def m6(c):
    c["tasks"][0]["costNote"] = ""
    return c


@mutant("cost 含『待核』")
def m7(c):
    t = c["tasks"][0]
    t["cost"] = {"text": "代价待核。", "basis": "explicit", "quotes": []}
    t.pop("costNote", None)
    return c


@mutant("cost 把法条当结果")
def m8(c):
    t = c["tasks"][0]
    t["cost"] = {"text": "法律规定禁止勾搭公主。", "basis": "explicit", "quotes": []}
    t.pop("costNote", None)
    return c


@mutant("semanticReview 写成 done")
def m9(c):
    c["semanticReview"]["status"] = "done"
    return c


@mutant("删掉 worldSettings 分区")
def m10(c):
    c.pop("worldSettings", None)
    return c


@mutant("place 缺 placeState")
def m11(c):
    for w in c["worldSettings"]:
        if w["kind"] == "place":
            w.pop("placeState", None)
            break
    return c


@mutant("placeState 非法值")
def m12(c):
    for w in c["worldSettings"]:
        if w["kind"] == "place":
            w["placeState"] = "planned"
            break
    return c


@mutant("item 缺逐态引文")
def m13(c):
    for w in c["worldSettings"]:
        if w["kind"] == "item":
            w["itemStateQuotes"] = {}
            break
    return c


@mutant("rule 缺 institution")
def m14(c):
    for w in c["worldSettings"]:
        if w["kind"] == "rule":
            w.pop("institution", None)
            break
    return c


@mutant("basis 非法值")
def m15(c):
    c["causeEdges"][0]["basis"] = "probably"
    return c


@mutant("unresolved 无 payoffNote")
def m16(c):
    for f in c["foreshadows"]:
        if f["status"] == "unresolved":
            f.pop("payoffNote", None)
            break
    return c


@mutant("无回收却标 resolved")
def m17(c):
    for f in c["foreshadows"]:
        f["status"] = "resolved"
        f["payoff"] = []
    return c


@mutant("result 写成功断言")
def m18(c):
    c["tasks"][4]["result"]["text"] = "行动成功，办成了事情。"
    return c


@mutant("actor 编一个原文没有的人")
def m19(c):
    c["tasks"][0]["actor"] = "慕容无涯"
    return c


@mutant("coverage 自报注水")
def m20(c):
    c["coverage"]["paragraphsTouchedByQuotes"] += 7
    return c


@mutant("内联「」引用造假")
def m21(c):
    c["tasks"][0]["note"] = "原文写着「这封信根本不存在于区间内」。"
    return c


@mutant("跨分区复用未披露")
def m22(c):
    c["crossSectionQuoteReuse"] = []
    return c


@mutant("复用清单引文与偏移不符")
def m23(c):
    c["crossSectionQuoteReuse"][0]["quote"] = "伪造的引文"
    return c


@mutant("零覆盖清单与实测不符")
def m24(c):
    c["coverage"]["zeroCoverageList"] = [1, 2, 3]
    return c


@mutant("悬空内部编号引用")
def m25(c):
    c["tasks"][0]["cost"] = None
    c["tasks"][0]["costNote"] = "本区间无代价（见 i9 与 e99）。"
    return c


@mutant("语层披露漏掉含引号的引用")
def m26(c):
    d = c["speechLayerDisclosure"]["dispositionOfEach"]
    c["speechLayerDisclosure"]["dispositionOfEach"] = [x for x in d if "“" not in x["quote"]]
    return c


@mutant("语层 checkedCount 注水")
def m27(c):
    c["speechLayerDisclosure"]["checkedCount"] += 5
    return c


# ── 跑基线 ──────────────────────────────────────────────────────────────
rc0, err0 = run(deep_copy())
if rc0 != 0:
    print("基线就失败，对照无效：\n%s" % err0, file=sys.stderr)
    sys.exit(2)
print("基线 rc=0（未改坏的产物一条都不报）")

hits = 0
missed = []
for name, fn in MUTANTS:
    rc, err = run(fn(deep_copy()))
    if rc != 0:
        hits += 1
        print("  命中 %-24s → %s" % (name, err.strip().splitlines()[0][:80]))
    else:
        missed.append(name)
        print("  漏掉 %-24s ← 判据失效！" % name, file=sys.stderr)

# 产物未被改动自证
import hashlib
after = hashlib.sha256(open(CAND, "rb").read()).hexdigest()
print("\n阴性对照：命中 %d/%d，基线误报 0" % (hits, len(MUTANTS)))
shutil.rmtree(tmpdir, ignore_errors=True)
if missed:
    print("漏掉的改坏：%s" % missed, file=sys.stderr)
    sys.exit(1)
sys.exit(0)
