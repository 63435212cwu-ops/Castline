#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:dafeng:L1:0233 阴性对照。

问的问题不是「审计通过了吗」，而是「**审计真的会抓吗**」。
把产物故意改坏 N 种，断言 audit_candidate.py 每次都返回非 0；
并断言未改坏的基线返回 0。全程在临时目录里做，**不覆盖产物**。

为速度考虑，本脚本把产物复制到临时目录改坏，再用 `--cand` 参数指向它跑审计。
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAND = ROOT / "loop/state/out/read_dafeng_L1_0233.candidate.json"
AUDIT = HERE / "audit_candidate.py"

base_raw = CAND.read_bytes()
base_sha = hashlib.sha256(base_raw).hexdigest()
base = json.loads(base_raw.decode("utf-8"))


def run(cand_obj) -> int:
    """把改坏的候选写到临时文件，用环境变量告诉审计脚本读它。"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "cand.json"
        p.write_text(json.dumps(cand_obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
               "CL_AUDIT_CAND": str(p)}
        r = subprocess.run([sys.executable, "-B", "-s", str(AUDIT)],
                           capture_output=True, text=True, env=env)
        return r.returncode


def mutate(fn):
    c = copy.deepcopy(base)
    fn(c)
    return c


MUTATIONS = []

def m(name):
    def deco(fn):
        MUTATIONS.append((name, fn))
        return fn
    return deco


@m("偏移错 1 位")
def _(c): c["tasks"][0]["objective"]["quotes"][0]["start"] += 1

@m("引文改字")
def _(c): c["tasks"][0]["objective"]["quotes"][0]["quote"] = "希望朝廷为尔追封"

@m("sourceHash 改错")
def _(c): c["worldSettings"][0]["sourceHash"] = "0" * 64

@m("引文越界")
def _(c): c["tasks"][1]["objective"]["quotes"][0]["end"] = 99

@m("同任务两栏共用一句")
def _(c):
    q = c["tasks"][0]["objective"]["quotes"][0]
    c["tasks"][0]["action"]["quotes"] = [dict(q)]

@m("栏位裸 null 无 Note")
def _(c): c["tasks"][0].pop("costNote")

@m("costNote 含『待核』")
def _(c): c["tasks"][0]["costNote"] = "本区间未出现代价，待核。"

@m("cost 把法条当结果")
def _(c):
    c["tasks"][0]["cost"] = {"text": "法律规定不许追封。", "basis": "explicit",
                             "quotes": [dict(c["tasks"][0]["action"]["quotes"][0])]}

@m("semanticReview 写成 done")
def _(c): c["semanticReview"]["status"] = "done"

@m("缺 worldSettings 条目级引文")
def _(c): c["worldSettings"][0].pop("start")

@m("place 缺 placeState")
def _(c):
    for w in c["worldSettings"]:
        if w["kind"] == "place": w.pop("placeState"); break

@m("placeState 非法值")
def _(c):
    for w in c["worldSettings"]:
        if w["kind"] == "place": w["placeState"] = "visited"; break

@m("arrived 但没有到达依据")
def _(c):
    for w in c["worldSettings"]:
        if w["kind"] == "place" and w["placeState"] == "arrived":
            w.pop("arrivalEvidence"); break

@m("unresolved 缺 payoffNote")
def _(c):
    for f in c["foreshadows"]:
        if f["status"] == "unresolved": f.pop("payoffNote"); break

@m("无回收却标 resolved")
def _(c):
    for f in c["foreshadows"]:
        if f["status"] == "unresolved":
            f["status"] = "resolved"; f.pop("payoffNote", None); break

@m("自述 null 计数灌水（覆盖率）")
def _(c): c["coverage"]["zeroCoverageParagraphs"] = 3

@m("basis 非法值")
def _(c): c["tasks"][0]["objective"]["basis"] = "maybe"

@m("rule 缺 institution")
def _(c):
    for w in c["worldSettings"]:
        if w["kind"] == "rule": w.pop("institution"); break

@m("item 四态缺 stateEvidence")
def _(c):
    for w in c["worldSettings"]:
        if w["kind"] == "item": w.pop("stateEvidence"); break

@m("causeEdge 缺 mechanism")
def _(c): c["causeEdges"][0].pop("mechanism")

@m("causeEdge 缺 from/to")
def _(c): c["causeEdges"][1].pop("to")

@m("knowledge_gap 缺 knownBy")
def _(c):
    for s in c["states"]:
        if s["kind"] == "knowledge_gap": s.pop("knownBy"); break

@m("themeReading 缺 counter")
def _(c): c["themeReadings"][0].pop("counter")

@m("themeReadings 超过 2 条")
def _(c): c["themeReadings"].append(copy.deepcopy(c["themeReadings"][0]))

@m("自撰短语伪装引文（用「」）")
def _(c): c["tasks"][0]["costNote"] = "本区间没有「代价」描写。"

@m("跨分区复用未披露")
def _(c): c["crossSectionQuoteReuse"] = []

@m("话语层披露清空")
def _(c): c["speechLayerDisclosure"]["dispositionOfEach"] = []

@m("话语层条目定位不符")
def _(c): c["speechLayerDisclosure"]["dispositionOfEach"][0]["start"] += 5

@m("切片越界（sourceRange 改小）")
def _(c): c["sourceRange"] = [c["sourceRange"][0] + 1, c["sourceRange"][1]]

@m("零覆盖清单混入已覆盖段落")
def _(c):
    c["coverage"]["zeroCoverageList"] = [
        {"start": c["tasks"][0]["objective"]["quotes"][0]["start"],
         "end": c["tasks"][0]["objective"]["quotes"][0]["end"],
         "text": c["tasks"][0]["objective"]["quotes"][0]["quote"]}
    ]

@m("note 自报计数灌水（worldSettings 总数）")
def _(c): c["worldSettingsNote"] = c["worldSettingsNote"].replace("13 条设定", "99 条设定")

@m("note 自报 null 计数灌水")
def _(c): c["tasksNote"] = c["tasksNote"].replace("11 个裸 null", "3 个裸 null")

@m("mentioned 地点用肯定语气写成到达")
def _(c):
    for w in c["worldSettings"]:
        if w["kind"] == "place" and w["placeState"] == "mentioned":
            w["explain"] = "本区间有人抵达该地并驻守。"
            break


def main() -> int:
    # 基线：未改坏必须通过
    base_rc = run(base)
    if base_rc != 0:
        print(f"基线失败（未改坏的产物被判 fail，rc={base_rc}）—— 审计有误报", file=sys.stderr)
        return 2

    caught, missed = [], []
    for name, fn in MUTATIONS:
        rc = run(mutate(fn))
        (caught if rc != 0 else missed).append(name)

    print(f"阴性对照：命中 {len(caught)}/{len(MUTATIONS)}，基线误报 0")
    if missed:
        print("未被抓到的改坏形态：", file=sys.stderr)
        for n in missed:
            print("  - " + n, file=sys.stderr)

    after = hashlib.sha256(CAND.read_bytes()).hexdigest()
    if after != base_sha:
        print(f"产物被本脚本改动（{base_sha[:12]} → {after[:12]}）—— 违反只读约定", file=sys.stderr)
        return 3
    print(f"产物未被改动，sha256 仍为 {after}")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
