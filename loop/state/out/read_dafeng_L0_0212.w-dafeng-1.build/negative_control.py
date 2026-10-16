#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阴性对照：把产物故意改坏，断言独立审计确实会触发。

为什么必须有这一步：
  「审计通过」本身不构成证据 —— 一个永远返回 0 的审计脚本也会「通过」。
  唯一能把「通过」变成信息量的方法，是证明**同一个审计**在产物坏掉时会失败，
  而且要坏得足够多样：偏移错位、引文改字、哈希造假、分区缺失、
  五栏共用一句、裸 null 无 Note、cost 把法条当代价、place 缺 placeState、
  语层漏登记、覆盖率注水、跨分区复用清单造假、悬空编号……
  每一条都对应提示词里的一条红线。

纪律：
  · 只写**临时副本**，绝不覆盖真产物（跑完复算真产物哈希并断言未变）。
  · 用例是「改坏」而不是「改好」：任何一个用例如果审计没报错，就是审计的漏洞。
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0212.candidate.json")
AUDIT = os.path.join(HERE, "audit_candidate.py")


def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


BASE = sha(CAND)
ORIG = json.load(open(CAND, encoding="utf-8"))


def run_audit_on(mutate):
    """把产物改坏后写进临时副本，让审计脚本跑它，返回 (是否被抓, 结果)。

    关键：审计脚本以**参数**接收产物路径，脚本本身留在原地运行
    （这样它的 __file__ 仍然指向本目录，ROOT 算得对）。
    早期做法是把审计脚本复制到临时目录 —— 那样审计在读取阶段就崩，
    所有用例都"被抓到"，但那是崩溃不是判据；下面的基线断言专门堵这个洞。
    """
    d = json.loads(json.dumps(ORIG, ensure_ascii=False))
    mutate(d)
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="nc_", dir=HERE)
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)
        r = subprocess.run([sys.executable, "-B", "-s", AUDIT, tmp],
                           capture_output=True, text=True, cwd=ROOT)
        return r.returncode != 0, r
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


CASES = []


def case(tag):
    def deco(fn):
        CASES.append((tag, fn))
        return fn
    return deco


def first_ref(d):
    """取产物里第一个引用对象（深拷贝里的）。"""
    def walk(o):
        if isinstance(o, dict):
            if set(o.keys()) >= {"quote", "start", "end"} and "sourceHash" in o:
                return o
            for v in o.values():
                r = walk(v)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = walk(v)
                if r:
                    return r
        return None
    return walk(d)


@case("偏移错 1 位")
def c1(d):
    first_ref(d)["start"] += 1


@case("引文改字")
def c2(d):
    r = first_ref(d)
    r["quote"] = r["quote"][:-1] + "错"


@case("sourceHash 造假")
def c3(d):
    first_ref(d)["sourceHash"] = "0" * 64


@case("引文越出本单元")
def c4(d):
    r = first_ref(d)
    r["start"], r["end"] = 100, 140
    r["quote"] = "x" * 40


@case("缺顶层分区 tasks")
def c5(d):
    d.pop("tasks")


@case("同一任务两栏共用一句")
def c6(d):
    t = d["tasks"][0]
    src = t["objective"]["quotes"][0]
    t["action"]["quotes"] = [dict(src)]


@case("裸 null 无 Note")
def c7(d):
    for t in d["tasks"]:
        if t.get("cost") is None:
            t.pop("costNote", None)
            return
    raise AssertionError("找不到 cost=null 的任务")


@case("cost 把死罪当已付代价")
def c8(d):
    for t in d["tasks"]:
        if t.get("cost") is None:
            t["cost"] = {"text": "触犯阻扰办案是死罪", "basis": "explicit",
                         "quotes": []}
            return
    raise AssertionError("找不到 cost=null 的任务")


@case("place 缺 placeState")
def c9(d):
    for w in d["worldSettings"]:
        if w.get("kind") == "place":
            w.pop("placeState", None)
            return
    raise AssertionError("找不到 place")


@case("item 非法 itemStates 值")
def c10(d):
    for w in d["worldSettings"]:
        if w.get("kind") == "item":
            w["itemStates"] = ["melted"]
            return
    raise AssertionError("找不到 item")


@case("rule 缺 institution")
def c11(d):
    for w in d["worldSettings"]:
        if w.get("kind") == "rule":
            w.pop("institution", None)
            return
    raise AssertionError("找不到 rule")


@case("foreshadow resolved 无 payoff")
def c12(d):
    for f in d["foreshadows"]:
        if f.get("status") == "resolved":
            f.pop("payoff", None)
            return
    raise AssertionError("找不到 resolved")


@case("foreshadow unresolved 无 payoffNote")
def c13(d):
    for f in d["foreshadows"]:
        if f.get("status") == "unresolved":
            f.pop("payoffNote", None)
            return
    raise AssertionError("找不到 unresolved")


@case("basis 非法")
def c14(d):
    d["tasks"][0]["objective"]["basis"] = "probably"


@case("内联引用查不到")
def c15(d):
    d["tasks"][0]["note"] = "他引了一句「这句话在原文里根本不存在啊」"


@case("内联引用含省略号")
def c16(d):
    d["tasks"][0]["note"] = "他引了「暗号解开了……等等」"


@case("semanticReview 写成 done")
def c17(d):
    d["semanticReview"]["status"] = "done"


@case("覆盖率自报注水")
def c18(d):
    d["coverage"]["paragraphsTouchedByQuotes"] = 999


@case("零覆盖清单不符")
def c19(d):
    d["coverage"]["zeroCoverageList"] = [1, 2, 3]


@case("跨分区复用清单造假")
def c20(d):
    d["crossSectionQuoteReuse"] = []


@case("跨分区复用清单多一条")
def c21(d):
    d["crossSectionQuoteReuse"] = list(d["crossSectionQuoteReuse"]) + [{
        "quote": "无中生有", "start": 787905, "end": 787909,
        "sourceHash": d["sourceHash"], "sections": ["tasks"], "note": "-"}]


@case("语层披露条数注水")
def c22(d):
    d["speechLayerDisclosure"]["checkedCount"] = 999


@case("引文在切片内不唯一")
def c23(d):
    # 「铜皮铁骨破了。」在切片内唯一；换成切片里出现两次的短串
    r = first_ref(d)
    sl_start, sl_end = d["sourceRange"]
    doc = json.load(open(os.path.join(
        ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json"), encoding="utf-8"))[0]["text"]
    sl = doc[sl_start:sl_end]
    # 找一个在切片内出现 >=2 次的 6 字串
    for n in range(6, 14):
        for i in range(0, len(sl) - n, 7):
            frag = sl[i:i + n]
            if sl.count(frag) >= 2 and "\n" not in frag:
                r["quote"] = frag
                r["start"] = sl_start + sl.find(frag)
                r["end"] = r["start"] + len(frag)
                return
    raise AssertionError("找不到重复片段")


@case("悬空内部编号引用")
def c25(d):
    d["tasks"][0]["note"] = "详见 e99 与 s88 的说明"


@case("顶层数组被换成字符串")
def c26(d):
    d["states"] = "很多状态"


@case("place 把图谋写成到达")
def c27(d):
    for w in d["worldSettings"]:
        if w.get("kind") == "place" and w.get("placeState") == "mentioned":
            w["placeState"] = "arrived"
            return
    raise AssertionError("找不到 mentioned 的 place")


def main():
    # ── 装置自检（必须先过）─────────────────────────────────────────────
    # 未改坏的产物跑审计必须 rc=0。若这里就失败，说明测试装置本身坏了
    # （例如路径算错、脚本崩溃），此后所有「抓到」都不算数。
    caught0, r0 = run_audit_on(lambda d: None)
    print("基线（未改坏）审计 rc=%d —— 期望 0" % r0.returncode)
    if caught0:
        print("[FAIL] 基线就失败：测试装置坏了，后续命中数无意义", file=sys.stderr)
        print(r0.stderr[-800:], file=sys.stderr)
        return 1

    hits, misses, broken = 0, [], []
    for tag, fn in CASES:
        try:
            caught, r = run_audit_on(fn)
        except AssertionError as exc:
            broken.append("%s（用例自身失效：%s）" % (tag, exc))
            continue
        # 只认「审计自己报出的 FAIL」，不认崩溃：
        # 崩溃（traceback）说明用例把产物改成了审计读不了的东西，
        # 那是装置问题，不是判据生效。
        crashed = "Traceback (most recent call last)" in (r.stderr or "")
        reported = "[FAIL]" in (r.stderr or "")
        if crashed:
            broken.append("%s（审计崩溃而非报 FAIL）" % tag)
        elif caught and reported:
            hits += 1
        else:
            misses.append(tag)

    after = sha(CAND)
    print("阴性对照：%d/%d 个改坏用例被审计判据抓到" % (hits, len(CASES)))
    if broken:
        print("用例/装置问题（不计入命中）：", file=sys.stderr)
        for b in broken:
            print("   - %s" % b, file=sys.stderr)
    if misses:
        print("未被抓到（审计漏洞）：", file=sys.stderr)
        for m in misses:
            print("   - %s" % m, file=sys.stderr)
    print("  真产物哈希未变：%s" % (after == BASE))
    if after != BASE:
        print("[FAIL] 阴性对照动了真产物！", file=sys.stderr)
        return 1
    if misses or broken or hits != len(CASES):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
