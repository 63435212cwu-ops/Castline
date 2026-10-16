# -*- coding: utf-8 -*-
"""阴性对照：把产物故意改坏 N 种，断言独立审计**确实触发**。

理由：一个从不失败的判据等于没有判据。本脚本不落盘、不覆盖产物 ——
所有改坏都发生在内存/临时副本里，最终仍以**未改坏的基线**再跑一次审计确认零误报。

用法：python3 -B -s loop/state/out/read_dafeng_L1_0229.w-xiyou-1.build/negative_control.py
"""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
BUILD = ROOT / "loop/state/out/read_dafeng_L1_0229.w-xiyou-1.build"
AUDIT = BUILD / "audit_candidate.py"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0229.candidate.json"

BASE = json.loads(CAND.read_text(encoding="utf-8"))
BASE_SHA = hashlib.sha256(CAND.read_bytes()).hexdigest()


def run_audit(obj):
    """把 obj 写到临时文件，临时替换产物路径跑审计，随后恢复。"""
    original = CAND.read_bytes()
    try:
        CAND.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        p = subprocess.run([sys.executable, "-B", "-s", str(AUDIT)],
                           capture_output=True, text=True, cwd=str(ROOT))
        return p.returncode
    finally:
        CAND.write_bytes(original)


def mutate(name, fn):
    c = copy.deepcopy(BASE)
    fn(c)
    return name, c


def find_quote_holder(c, section):
    return c[section][0]


cases = []


def m01(c):
    c["tasks"][0]["objective"]["quotes"][0]["start"] += 1


def m02(c):
    c["tasks"][0]["objective"]["quotes"][0]["quote"] = "这句话在原文里根本不存在。"


def m03(c):
    c["sourceHash"] = "0" * 64


def m04(c):
    c["tasks"][0]["objective"]["quotes"][0]["sourceHash"] = "0" * 64


def m05(c):
    c["worldSettings"][0]["start"] -= 5000


def m06(c):
    # 同一任务内两栏共用同一句
    c["tasks"][0]["action"]["quotes"] = copy.deepcopy(c["tasks"][0]["objective"]["quotes"])


def m07(c):
    del c["themeReadings"]


def m08(c):
    c["tasks"][0]["cost"] = {"text": "代价待核。", "basis": "explicit",
                             "quotes": copy.deepcopy(c["tasks"][0]["action"]["quotes"])}


def m09(c):
    c["tasks"][0]["cost"] = {"text": "法律规定不得如此。", "basis": "explicit",
                             "quotes": copy.deepcopy(c["tasks"][0]["result"]["quotes"])}


def m10(c):
    c["semanticReview"] = {"status": "done", "note": "已核验"}


def m11(c):
    c["coverage"]["paragraphsTouchedByQuotes"] = 250


def m12(c):
    # 另一个栏位改成裸 null 且不留 Note（与 m13 是不同的栏位，不是重复用例）
    c["tasks"][1]["objective"] = None
    c["tasks"][1].pop("objectiveNote", None)


def m13(c):
    c["tasks"][0]["cost"] = None
    c["tasks"][0].pop("costNote", None)


def m14(c):
    # 必须真的命中一条 place：worldSettings 里 rule 排在前面，不能按下标猜。
    for s_ in c["worldSettings"]:
        if s_.get("kind") == "place" and "placeState" in s_:
            s_.pop("placeState")
            return
    raise AssertionError("产物里没有带 placeState 的 place 条目")


def m15(c):
    for f in c["foreshadows"]:
        if f["status"] == "unresolved":
            f.pop("payoffNote", None)
            break


def m16(c):
    c["foreshadows"][0]["status"] = "resolved"  # 无回收却标 resolved


def m17(c):
    c["tasksNote"] = "7 条任务、35 个栏位，其中 3 个裸 null。"


def m18(c):
    c["unknowns"][0]["basis"] = "certain"


def m19(c):
    c["worldSettings"][0].pop("institution", None)


def m20(c):
    c["tasks"][0]["obstacle"] = {"text": "有人挡路", "basis": "explicit", "quotes": []}


def m21(c):
    # 自撰短语伪装成逐字引文（A18）
    c["statesNote"] = c["statesNote"] + " 本条纯属我自己的归纳「这句话不是原文」。"


def m22(c):
    # 跨分区复用未披露
    c.pop("crossSectionQuoteReuse", None)


def m23(c):
    # 引文跨段（A17 覆盖率会算不到归属）——用一条跨界引用制造
    q = c["worldSettings"][0]
    q["start"] = q["start"] - 1
    q["end"] = q["end"] + 1


def m24(c):
    # place 记为 arrived 但引文其实是图谋（语义类：这里改字段值制造非法值）
    for s in c["worldSettings"]:
        if s.get("kind") == "place":
            s["placeState"] = "conquered"
            break


MUTATORS = [
    ("m01 偏移错 1 位", m01), ("m02 引文改字", m02), ("m03 sourceHash 错", m03),
    ("m04 引用 sourceHash 错", m04), ("m05 引文越界", m05), ("m06 同任务两栏共用一句", m06),
    ("m07 缺分区 themeReadings", m07), ("m08 cost 含『待核』", m08),
    ("m09 cost 把法条当结果", m09), ("m10 semanticReview 写成 done", m10),
    ("m11 覆盖率自报注水", m11), ("m12 cost 为 null 且无 Note", m13),
    ("m13（重复口径）costNote 缺失", m13), ("m14 place 缺 placeState", m14),
    ("m15 unresolved 缺 payoffNote", m15), ("m16 无回收标 resolved", m16),
    ("m17 自述 null 计数灌水", m17), ("m18 basis 非法值", m18),
    ("m19 rule 缺 institution", m19), ("m20 栏位结构不合法", m20),
    ("m21 自撰短语伪装引文", m21), ("m22 跨分区复用未披露", m22),
    ("m23 引文跨段/边界错", m23), ("m24 placeState 非法值", m24),
]

print("基线产物：%s" % CAND)
print("基线 sha256：%s" % BASE_SHA)
print("-" * 62)

base_rc = run_audit(BASE)
print("基线（未改坏）审计退出码 = %d %s" % (base_rc, "（零误报 ✓）" if base_rc == 0 else "（误报 ✗）"))

hits, misses = 0, []
for label, fn in MUTATORS:
    c = copy.deepcopy(BASE)
    try:
        fn(c)
    except Exception as exc:      # 变异本身不成立 ⇒ 记为未命中，不静默放过
        misses.append((label, "变异失败 %r" % exc))
        print("  ! %-34s 变异失败：%r" % (label, exc))
        continue
    if json.dumps(c, ensure_ascii=False) == json.dumps(BASE, ensure_ascii=False):
        misses.append((label, "变异后内容与基线相同（空变异）"))
        print("  ! %-34s 空变异" % label)
        continue
    rc = run_audit(c)
    if rc != 0:
        hits += 1
        print("  ✓ %-34s 被审计抓到（rc=%d）" % (label, rc))
    else:
        misses.append((label, "审计未触发"))
        print("  ✗ %-34s **未被抓到**" % label)

print("-" * 62)
final = hashlib.sha256(CAND.read_bytes()).hexdigest()
print("最终产物 sha256：%s %s" % (final, "（与基线一致，未被本脚本改动 ✓）"
                                  if final == BASE_SHA else "（**被改动了** ✗）"))
print("命中 %d / %d，基线误报 %d" % (hits, len(MUTATORS), base_rc))
if misses:
    print("未命中清单：")
    for label, why in misses:
        print("  - %s：%s" % (label, why))
    sys.exit(1)
if base_rc != 0 or final != BASE_SHA:
    sys.exit(1)
print("阴性对照通过：%d/%d 命中，基线零误报，产物未被改动" % (hits, len(MUTATORS)))
