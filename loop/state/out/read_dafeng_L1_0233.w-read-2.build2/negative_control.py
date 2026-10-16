#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阴性对照：证明 audit_candidate.py 的判据**真的能抓到缺陷**。

为什么必须做：一个从不报错的审计脚本和一个通过全部判据的产物，
在输出上长得一模一样。「审计通过」只有在审计**能失败**时才是有信息的。

做法：把产物复制到临时目录，逐项注入已知缺陷，每次都重新跑完整审计，
断言它**确实失败**（exit 1）且失败在**预期的那条判据**上。
注入的缺陷全部是本轮真实踩过或提示词点名禁止的形态。

用法：python3 -B -s loop/state/out/read_dafeng_L1_0233.w-read-2.build2/negative_control.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
CAND = ROOT / "loop/state/out/read_dafeng_L1_0233.candidate.json"
AUDIT = ROOT / "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/audit_candidate.py"

# 审计脚本里候选路径是硬编码的；用环境变量注入替身，避免改动真产物。
AUDIT_SRC = AUDIT.read_text(encoding="utf-8")
assert 'CAND = ROOT / "loop/state/out/read_dafeng_L1_0233.candidate.json"' in AUDIT_SRC


def run_audit_on(tmp_cand: Path, tmp_audit: Path):
    tmp_audit.write_text(
        AUDIT_SRC.replace(
            'CAND = ROOT / "loop/state/out/read_dafeng_L1_0233.candidate.json"',
            f'CAND = Path({str(tmp_cand)!r})',
        ),
        encoding="utf-8",
    )
    r = subprocess.run([sys.executable, "-B", "-s", str(tmp_audit)],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def mutate(fn):
    d = json.loads(CAND.read_text(encoding="utf-8"))
    fn(d)
    return d


# ── 注入器 ──────────────────────────────────────────────────────────────
def m_quote_off_by_one(d):
    q = d["tasks"][0]["objective"]["quotes"][0]
    q["start"] += 1


def m_quote_wrong_char(d):
    d["tasks"][0]["objective"]["quotes"][0]["quote"] = \
        d["tasks"][0]["objective"]["quotes"][0]["quote"].replace("追封", "追讨")


def m_source_hash(d):
    d["causeEdges"][0]["quotes"][0]["sourceHash"] = "0" * 64


def m_out_of_range(d):
    d["causeEdges"][0]["quotes"][0].update({"start": 100, "end": 110, "quote": d["causeEdges"][0]["quotes"][0]["quote"]})


def m_two_slots_same_quote(d):
    t = d["tasks"][0]
    t["obstacle"]["quotes"] = [dict(t["objective"]["quotes"][0])]


def m_bare_null_no_note(d):
    d["tasks"][0]["costNote"] = ""


def m_missing_section(d):
    d.pop("worldSettings", None)


def m_basis_illegal(d):
    d["causeEdges"][0]["basis"] = "maybe"


def m_semantic_done(d):
    d["semanticReview"] = {"status": "performed"}


def m_item_state_no_evidence(d):
    for w in d["worldSettings"]:
        if w["kind"] == "item":
            w["stateEvidence"].pop(w["itemStates"][0], None)
            break


def m_place_state_illegal(d):
    for w in d["worldSettings"]:
        if w["kind"] == "place":
            w["placeState"] = "visited"
            break


def m_resolved_no_payoff(d):
    for f in d["foreshadows"]:
        if f["status"] == "resolved":
            f["payoff"] = []
            break


def m_unresolved_no_note(d):
    for f in d["foreshadows"]:
        if f["status"] == "unresolved":
            f.pop("payoffNote", None)
            break


# ── 顺序类（本轮新增判据，最需要证明有效）──────────────────────────────
def m_edge_order_reversed(d):
    """把一条边机制改成声称先后，同时把引文顺序倒过来。"""
    e = d["causeEdges"][0]
    e["mechanism"] = "先发生甲，随后才发生乙（阴性对照注入）"
    e["quotes"] = list(reversed(e["quotes"]))


def m_task_action_after_result(d):
    t = d["tasks"][1]
    t["action"], t["result"] = t["result"], t["action"]


def m_state_anchor_outside(d):
    s = [x for x in d["states"] if x["kind"] == "change"][2]
    s["anchor"] = dict(s["after"])
    s["after"] = dict(s["before"])
    s.pop("narrationOrder", None)


def m_foreshadow_payoff_before_setup(d):
    f = [x for x in d["foreshadows"] if x.get("payoff")][0]
    f["setup"], f["payoff"] = f["payoff"], f["setup"]


def m_identity_token_absent(d):
    d["tasks"][0]["actor"] = "张行英（云州巡抚）"


def m_coverage_inflated(d):
    d["coverage"]["paragraphsTouchedByQuotes"] += 5
    d["coverage"]["zeroCoverageParagraphs"] -= 5


def m_theme_missing_counter(d):
    d["themeReadings"][0].pop("counter", None)


def m_selfcritique_two(d):
    d["selfCritique"] = d["selfCritique"][:2]


def m_slice_sha_wrong(d):
    d["sliceSha256"] = "f" * 64


CASES = [
    ("A4 偏移错 1 位", m_quote_off_by_one, "A4"),
    ("A4 引文改字", m_quote_wrong_char, "A4"),
    ("A7 sourceHash 错", m_source_hash, "A7"),
    ("A5 引文越界", m_out_of_range, "A5"),
    ("A8 五栏共用一句", m_two_slots_same_quote, "A8"),
    ("A9 裸 null 无 Note", m_bare_null_no_note, "A9"),
    ("A19 缺分区", m_missing_section, "A19"),
    ("A11 basis 非法", m_basis_illegal, "A11"),
    ("A18 semanticReview 越权", m_semantic_done, "A18"),
    ("A15 item 状态缺依据", m_item_state_no_evidence, "A15"),
    ("A15 placeState 非法", m_place_state_illegal, "A15"),
    ("A14 resolved 无回收", m_resolved_no_payoff, "A14"),
    ("A14 unresolved 无 note", m_unresolved_no_note, "A14"),
    ("A20 边机制与引文顺序相反", m_edge_order_reversed, "A20"),
    ("A20 task action 晚于 result", m_task_action_after_result, "A20"),
    ("A20 state 锚点越界", m_state_anchor_outside, "A20"),
    ("A20 伏笔回收早于铺设", m_foreshadow_payoff_before_setup, "A20"),
    ("A21 身份词不在切片内", m_identity_token_absent, "A21"),
    ("A22 覆盖率自述注水", m_coverage_inflated, "A22"),
    ("A16 theme 缺 counter", m_theme_missing_counter, "A16"),
    ("A17 selfCritique 不足 3 条", m_selfcritique_two, "A17"),
    ("A3 sliceSha256 自述错", m_slice_sha_wrong, "A3"),
]

tmp = Path(tempfile.mkdtemp(prefix="cl-negctl-"))
tmp_audit = tmp / "audit_variant.py"
results = []
try:
    for name, fn, expect in CASES:
        d = mutate(fn)
        c = tmp / "cand.json"
        c.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        rc, out = run_audit_on(c, tmp_audit)
        caught = f"[{expect}]" in out
        results.append((name, expect, rc != 0, caught))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"{'注入的缺陷':34} {'预期判据':7} {'审计报错':8} {'命中该判据'}")
print("-" * 72)
allok = True
for name, expect, failed, caught in results:
    flag = "" if (failed and caught) else "   <== 阴性对照失败"
    allok &= (failed and caught)
    print(f"{name:34} {expect:7} {str(failed):8} {str(caught):10}{flag}")

# 真产物必须通过（阳性对照）
_pos = subprocess.run([sys.executable, "-B", "-s", str(AUDIT)],
                      capture_output=True, text=True)
rc = _pos.returncode
pos = rc == 0
print("-" * 72)
print(f"阳性对照（未改动的真产物）：审计 exit={rc} {'通过' if pos else '失败'}")
allok &= pos

print()
if allok:
    print(f"阴性对照全部成立：{len(results)} 种注入缺陷全部被对应判据抓到，"
          f"且未改动的产物仍通过。")
else:
    print("阴性对照存在失败项（见上）")
    sys.exit(1)
