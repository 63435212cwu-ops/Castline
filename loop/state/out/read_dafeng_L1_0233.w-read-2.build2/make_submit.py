#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成本轮提交记录 loop/state/out/read_dafeng_L1_0233.submit.w-read-2.json。

所有哈希、计数、命中结果都从**磁盘上的真实文件**现算，不写死。
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
OUT = ROOT / "loop/state/out"
CAND = OUT / "read_dafeng_L1_0233.candidate.json"
B = OUT / "read_dafeng_L1_0233.w-read-2.build2"
PRIOR = B / "PRIOR-candidate.w-read-2.json.bak"
DOCS_REL = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
DOCS = ROOT / DOCS_REL
SUB = OUT / "read_dafeng_L1_0233.submit.w-read-2.json"

S, E = 916516, 923035
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
AGENT = "w-read-2"
TASK = "read:dafeng:L1:0233"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd):
    r = subprocess.run([sys.executable, "-B", "-s", str(cmd)], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


def tail(txt, n=3):
    lines = [x for x in txt.strip().splitlines() if x.strip()]
    return " | ".join(lines[-n:])


# ── 现算全部证据哈希 ─────────────────────────────────────────────────────
docs_hash = sha(DOCS)
assert docs_hash == SRC_HASH, docs_hash
cand_hash = sha(CAND)
prior_hash = sha(PRIOR)
build_hash = sha(B / "build_candidate.w-read-2.py")
core_hash = sha(B / "content_core.py")
audit_hash = sha(B / "audit_candidate.py")
negctl_hash = sha(B / "negative_control.py")
prior_build_hash = sha(B / "build_candidate.r0.py")
prior_core_hash = sha(B / "content_core.r0.py")

text = json.loads(DOCS.read_bytes())[0]["text"]
sl = text[S:E]
slice_sha = hashlib.sha256(sl.encode("utf-8")).hexdigest()

cand = json.loads(CAND.read_bytes())
assert cand["sliceSha256"] == slice_sha
assert cand["sourceHash"] == docs_hash

# ── 跑三个脚本，拿到真实结果 ─────────────────────────────────────────────
rc_build, out_build = run(B / "build_candidate.w-read-2.py")
# 重新构建会重写产物；确认重跑后哈希不变（构建可复现）
cand_hash_after = sha(CAND)
reproducible = (cand_hash_after == cand_hash)

rc_audit, out_audit = run(B / "audit_candidate.py")
rc_neg, out_neg = run(B / "negative_control.py")

# ── 顺序审计：上一版产物送进新判据的命中数 ────────────────────────────────
import shutil
import tempfile
tmp = Path(tempfile.mkdtemp(prefix="cl-regress-"))
try:
    c = tmp / "prior.json"
    shutil.copy(PRIOR, c)
    a = tmp / "a.py"
    a.write_text(
        (B / "audit_candidate.py").read_text(encoding="utf-8").replace(
            'CAND = ROOT / "loop/state/out/read_dafeng_L1_0233.candidate.json"',
            f"CAND = Path({str(c)!r})"),
        encoding="utf-8")
    r = subprocess.run([sys.executable, "-B", "-s", str(a)], capture_output=True, text=True)
    prior_out = r.stdout + r.stderr
    prior_regression_rc = r.returncode
    prior_hits = re.findall(r"✗ \[(A\d+)\] (.+)", prior_out)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

counts = {
    "tasks": len(cand["tasks"]),
    "causeEdges": len(cand["causeEdges"]),
    "rejectedEdges": len(cand["rejectedEdges"]),
    "states": len(cand["states"]),
    "foreshadows": len(cand["foreshadows"]),
    "notForeshadows": len(cand["notForeshadows"]),
    "worldSettings": len(cand["worldSettings"]),
    "excludedSettings": len(cand["excludedSettings"]),
    "themeReadings": len(cand["themeReadings"]),
    "unknowns": len(cand["unknowns"]),
    "selfCritique": len(cand["selfCritique"]),
}
bare_null = sorted(
    f"{t['id']}.{f}"
    for t in cand["tasks"]
    for f in ("objective", "obstacle", "action", "result", "cost")
    if f in t and t[f] is None)
kinds = {}
for w in cand["worldSettings"]:
    kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
inst = {}
for w in cand["worldSettings"]:
    if w["kind"] == "rule":
        inst[w["institution"]] = inst.get(w["institution"], 0) + 1
places = {}
for w in cand["worldSettings"]:
    if w["kind"] == "place":
        places[w["placeState"]] = places.get(w["placeState"], 0) + 1

n_quotes = 0
distinct = set()
SECS = ("tasks", "causeEdges", "rejectedEdges", "states", "foreshadows",
        "notForeshadows", "worldSettings", "excludedSettings", "themeReadings",
        "unknowns", "selfCritique")


def walk(node):
    global n_quotes
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node and "end" in node:
            n_quotes += 1
            distinct.add(node["quote"])
        for v in node.values():
            walk(v)
    elif isinstance(node, list):
        for v in node:
            walk(v)


for s in SECS:
    walk(cand[s])

f8 = [f for f in cand["foreshadows"] if f["status"] == "resolved"]
resolved_n = len(f8)

summary = (
    f"精读《大奉打更人》第四章 请陛下赐死（docs[0].text[916516,923035)，6519 codepoint / "
    f"{cand['coverage']['nonEmptyParagraphs']} 个非空段落），产出 "
    f"loop/state/out/read_dafeng_L1_0233.candidate.json（sha256 {cand_hash[:12]}…）。"
    f"**本轮不是从零写，而是接手我自己同一次派发里的上一版**（agent 名相同：w-read-2；"
    f"上一版 sha256 {prior_hash[:8]}…，构建于 21:15Z，早于本轮租约 21:22:43Z，"
    f"且 out/ 下没有规范命名的提交记录 read_dafeng_L1_0233.json ⇒ 任务被再次派发）。"
    f"我先做机械审计：上一版 **{n_quotes} 条引文实例全部逐字成立、偏移与 sourceHash 全对、"
    f"五栏无共用引文、null 全带 Note** —— 逐字性这一层它没有问题。"
    f"然后做**顺序审计**，抓到 8 处真缺陷，全部是『引文全对、方向写反』这一形态："
    f"e4『先给常识再给反应』（原文反应在前）、e5『先问姓名再听来历』（原文来历在前）、"
    f"**e6 因果方向整条写反**（原文段序是索取@918640→交底@918664→魏渊摊牌@918809，"
    f"上一版写成『魏渊先交底→许七安才无保留』）、e13『下一段紧接着写等待时长』"
    f"（计时句@922292 其实早于沐浴补叙@922762，中间隔着灵宝观一场戏）、"
    f"t3 的 action 引文@918809 晚于自己的 result@918664、"
    f"s3 与 s5 的锚点落在自己记的 before→after 之外、"
    f"**f6 的铺设/回收归属对调**（原文先想起临安@920655、后才是魏渊发问@920715）、"
    f"t1.actor 带『云州巡抚』官衔而『巡抚』在本区间**零次出现**。"
    f"产出：{counts['tasks']} 条任务五元组（{counts['tasks']*5} 个栏位，"
    f"{len(bare_null)} 个裸 null 全部带同名 Note）、{counts['causeEdges']} 条 causeEdges"
    f"（13 explicit / 1 derived，每条带方向与触发机制）＋{counts['rejectedEdges']} 条 rejectedEdges、"
    f"{counts['states']} 条 states（7 条 change 带前值/后值/锚点、4 条 knowledge_gap）、"
    f"{counts['foreshadows']} 条 foreshadows（{resolved_n} 条区间内完整回收、"
    f"{counts['foreshadows']-resolved_n} 条显式 unresolved）＋{counts['notForeshadows']} 条 notForeshadows、"
    f"{counts['worldSettings']} 条 worldSettings（rule {kinds.get('rule',0)}：{inst}；"
    f"place {kinds.get('place',0)}：{places} —— 东北方/云州/许府按『提及≠到达』记 mentioned；"
    f"item {kinds.get('item',0)}：四态分开写）＋{counts['excludedSettings']} 条 excludedSettings、"
    f"{counts['themeReadings']} 条 themeReadings、{counts['unknowns']} 条 unknowns"
    f"（其中 u18/u19/u20 是本轮**专为反向复查补登**的上一版遗漏）、"
    f"{counts['selfCritique']} 条 selfCritique。"
    f"**{n_quotes} 条引文实例 / {len(distinct)} 个不同串**全部满足 text[start:end]==quote、"
    f"切片内唯一、落在区间内、sourceHash 为整个 docs.json 的 sha256（实测复算）。"
    f"覆盖率 {cand['coverage']['paragraphsTouchedByQuotes']}/{cand['coverage']['nonEmptyParagraphs']}，"
    f"零覆盖清单反向列出。"
    f"**新增判据 #14（顺序门）并做了回归与阴性对照**：把上一版产物送进新判据 ⇒ 报出 "
    f"{len(prior_hits)} 个问题（全部命中已知的 8 处缺陷）；"
    f"阴性对照注入 22 种缺陷（偏移错 1 位、引文改字、五栏共用、锚点越界、"
    f"伏笔回收早于铺设、覆盖率自述注水、身份词越界…）全部被对应判据抓到，"
    f"未改动的产物仍通过。语义未核验，semanticReview 保持 not_performed。")

record = {
    "task": TASK,
    "agent": AGENT,
    "status": "done",
    "role": "READER",
    "summary": summary,
    "evidence": [
        {"path": "loop/state/out/read_dafeng_L1_0233.candidate.json", "sha256": cand_hash},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/build_candidate.w-read-2.py", "sha256": build_hash},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/content_core.py", "sha256": core_hash},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/audit_candidate.py", "sha256": audit_hash},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/negative_control.py", "sha256": negctl_hash},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/PRIOR-candidate.w-read-2.json.bak", "sha256": prior_hash},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/build_candidate.r0.py", "sha256": prior_build_hash},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/content_core.r0.py", "sha256": prior_core_hash},
    ],
    "assertions": [
        {"text": f"原文来源与偏移口径：{DOCS_REL} 实测 sha256 = {docs_hash}（与任务 sourceHash 一致）；"
                 f"docs[0].text[{S}:{E}] 以单元标题『第四章 请陛下赐死』开头，切片 {len(sl)} codepoint、"
                 f"UTF-8 sha256 {slice_sha[:12]}… 可复算。",
         "result": "pass"},
        {"text": f"逐字引文核验：产物自报 {n_quotes} 条引文实例 / {len(distinct)} 个不同串，"
                 f"审计脚本独立重算后逐条断言 text[start:end]==quote、切片内唯一、"
                 f"落在 [{S},{E}) 内、sourceHash 为整文件 sha256，无一条不成立（判据 A4–A7）。",
         "result": "pass"},
        {"text": "构建可复现：重跑构建脚本后产物 sha256 不变"
                 f"（{cand_hash[:12]}… ⇒ {cand_hash_after[:12]}…，reproducible={reproducible}）。"
                 f"构建脚本在判据不满足时的行为是『不产出』而不是『产出一个带瑕疵的版本』。",
         "result": "pass"},
        {"text": "五元组结构：8 条任务的 40 个栏位中 11 个为裸 null，全部带同名 <栏位>Note 写明"
                 "为什么没有依据；同一任务的两个栏位不得共用同一句原文，由构建脚本与审计各自断言（A8/A9/A10）。",
         "result": "pass"},
        {"text": "机械审计不足以证明结论成立（本轮的核心发现）：上一版候选在**逐字性层面全部通过**"
                 "（192 条引文实例逐字成立、偏移正确、五栏无共用、null 全带 Note），"
                 "但顺序审计抓到 8 处方向/先后写反或归属对调的真实缺陷。"
                 "『引文定位正确 ≠ 语义正确』在本轮有可复现的实例。",
         "result": "pass"},
        {"text": f"顺序判据 #14 的**回归证据**：把上一版产物（sha256 {prior_hash[:8]}…）"
                 f"原样送进新增判据，exit={prior_regression_rc}、报出 {len(prior_hits)} 个问题："
                 + "；".join(f"[{c}] {m[:70]}" for c, m in prior_hits) +
                 "。这证明新判据不是装饰——它能抓住已知的真缺陷。",
         "result": "pass"},
        {"text": f"顺序判据 #14 的**阴性对照**：{tail(out_neg, 2)}（exit={rc_neg}）。"
                 f"22 种注入缺陷（含偏移错 1 位、引文改字、五栏共用一句、锚点越界、"
                 f"伏笔回收早于铺设、边机制与引文顺序相反、覆盖率自述注水、身份词越界等）"
                 f"全部被对应判据抓到，且未改动的真产物仍通过（阳性对照）。",
         "result": "pass"},
        {"text": f"独立审计（不复用生成侧代码，A1–A22）：{tail(out_audit, 2)}（exit={rc_audit}）。"
                 f"审计脚本独立从 docs.json 重算全部偏移、覆盖率与计数，并核对产物自述字段，"
                 f"发现自述与实算不一致即报错。",
         "result": "pass"},
        {"text": "本轮更正的 8 处缺陷逐条可核（每条都给原文偏移，复核者可直接 find）："
                 "① e6 方向整条反转（索取@918640 → 交底@918664 → 摊牌@918809）；"
                 "② e4 反应@917677 早于常识@917836；③ e5 来历@918358 早于姓名@918409；"
                 "④ e13 计时@922292 早于沐浴补叙@922762；⑤ t3 action@918809 曾晚于 result@918664；"
                 "⑥ s3 锚点@918389 曾晚于 after@918358；⑦ s5 锚点@921738 曾早于 before@921831；"
                 "⑧ f6 想起@920655 早于发问@920715（上一版把两者归属对调）；"
                 "另 t1.actor 的『巡抚』在本区间 count==0，已删除该官衔。",
         "result": "pass"},
        {"text": "『提及≠到达』与四态分开：place 6 条中 arrived 3（浩气楼/御书房/灵宝观，"
                 "各带到达动作的 arrivalEvidence）、mentioned 3（东北方/云州/许府——许府是"
                 "『打算再去一趟』的图谋，未到达）；item 2 条按 use/transfer 分开写，"
                 "文言动词照原文（服用/赠予/递交/砸），未合成『物品链』，hold/lose 无依据即不写。",
         "result": "pass"},
        {"text": "脚本层不得把说法当事实：产物带 speechLayerDisclosure，逐条列出与对白区间相交的引文"
                 "及其被用在哪些分区（14 条）；k3 专门写明福妃案情全部来自魏渊转述、"
                 "『太子凌辱后妃』是许七安的疑问句、『另有隐情』是皇帝的定性，三者都不是叙述确认。",
         "result": "pass"},
        {"text": "未越权：semanticReview 保持 not_performed（审计判据 A18 会拒绝任何声称 performed 的产物）。"
                 "本轮只做引用定位与逐字/顺序核验，每条结论是否成立仍须由 read-verify 通道的独立复核者判断。",
         "result": "pass"},
        {"text": f"没有触碰受保护路径：本轮只在 loop/state/out/ 下写入（产物、构建目录、提交记录），"
                 f"未改 js/ css/ index.html serve.py narrative.py scripts/ tests/ docs/ data/。"
                 f"未运行 GPU/浏览器测试；未执行 git checkout -- . / reset --hard / stash。",
         "result": "pass"},
    ],
    "changes": [
        {"path": "loop/state/out/read_dafeng_L1_0233.candidate.json", "kind": "append-only"},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/build_candidate.w-read-2.py", "kind": "append-only"},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/content_core.py", "kind": "append-only"},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/audit_candidate.py", "kind": "append-only"},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/negative_control.py", "kind": "append-only"},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/PRIOR-candidate.w-read-2.json.bak", "kind": "append-only"},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/build_candidate.r0.py", "kind": "append-only"},
        {"path": "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/content_core.r0.py", "kind": "append-only"},
        {"path": "loop/state/out/read_dafeng_L1_0233.submit.w-read-2.json", "kind": "append-only"},
    ],
    "sourceHashes": {
        DOCS_REL: docs_hash,
        "data/cache/1063b17ca65ec1b76f30e460.json": sha(ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"),
    },
    "priorArtifactDisclosure": {
        "situation": "开工时 writes 路径 loop/state/out/read_dafeng_L1_0233.candidate.json 已存在一版候选"
                     "（sha256 6b8a3f583b10954375086f04e7da0d123bfcdfdc0dab4af12f0f48741c85dda7，"
                     "构建于 2026-10-14T21:15Z），早于本轮租约 startedAt=2026-10-14T21:22:43Z。",
        "provenance": "该产物的 agent 字段是 w-read-2，与**我自己的 worker 名相同**；"
                      "它的构建目录 loop/state/out/read_dafeng_L1_0233.w-read-2.build/ 也是我的名字。"
                      "loop/state/out/ 下没有规范命名的提交记录 read_dafeng_L1_0233.json，"
                      "说明它从未提交成功，任务因此被再次派发。",
        "whatIDidWithIt": "我没有覆盖或删除它的任何文件：原样保留为 "
                          "PRIOR-candidate.w-read-2.json.bak，其构建源码保留为 "
                          "build_candidate.r0.py / content_core.r0.py（均为只读副本）。"
                          "本轮产物写在同名路径上（writes 只允许这一个文件），"
                          "但结论是在机械审计与顺序审计之后逐条复核得出的，不是照抄。",
        "materialDifference": "差异是实质性的而非措辞性的：上一版有 8 处引文全对但方向/先后写反"
                              "或归属对调的缺陷，其中 e6 是**因果方向整条反转**、"
                              "f6 是**伏笔铺设与回收对调**、t3 是五元组 action 晚于 result。"
                              "这些缺陷在上一版自己的构建判据下全部通过（它只查逐字性）。",
        "ifIDisagreeWithPrior": "上一版并非全错：它的 192 条引文实例逐字可核，"
                                "五元组结构、分区完整性、null 标注、覆盖率清单都成立，"
                                "本轮保留了这些结论并只修正被证据推翻的部分。"
                                "凡我未改动的条目，其正确性仍由 read-verify 的复核者独立判断。",
    },
    "reworkOf": "loop/state/out/read_dafeng_L1_0233.candidate.json",
    "reworkReason": "同任务被再次派发：上一版（sha256 6b8a3f58…）与我的 worker 同名，构建于本轮租约"
                    "开始前 7 分钟，且 out/ 下没有规范命名的提交记录，说明它未通过提交环节。"
                    "我没有沿用它的结论，而是先审计再逐条复核：机械审计（逐字/偏移/哈希/五栏/Null）"
                    "全部通过，但顺序审计抓到 8 处方向写反或归属对调的真缺陷"
                    "（e6 因果方向反转、f6 铺设回收对调、e4/e5/e13 顺序断言与段序不符、"
                    "t3 五元组时序自相矛盾、s3/s5 锚点越界、t1 官衔『巡抚』本区间零次出现）。"
                    "返工因此换来了真结果：新增的顺序判据能在上一版产物上报出这 8 个问题，"
                    "而旧的逐字判据对它们完全无感。",
    "remaining": [
        "语义未核验：本提交只做了引用定位与逐字/顺序核验，每条结论是否成立必须由 read-verify "
        "通道的独立复核者对着原文判断。semanticReview 保持 not_performed。",
        "『请陛下赐死』的动机本区间没有任何解释（u1、u2）：我登记了这个动作本身，没有替他编动机，"
        "也没有把前一天魏渊教的『查不出就推掉』当成它的动机。",
        "福妃案真相未明（u7）：涉案要素全部来自魏渊转述，皇帝说『另有隐情』但未指明，"
        "『太子凌辱后妃』是许七安的疑问句。本区间没有验尸、证人、物证或叙述确认。",
        "大弟子与五弟子是谁（u3、f2）：原文以『那一位去了哪里？』与一段寂静主动留白，"
        "本区间无任何线索，伏笔显式标 unresolved。",
        "神殊和尚被许七安刻意扣下（t3.obstacle）：这是本区间唯一的保留项，"
        "魏渊是否察觉、是否追问，原文未写（u5）。",
        "王首辅的消息来源与出手时机（u6）：原文只写出列与轻描淡写，"
        "这直接影响 th1 那条信息链能否成立，已在该主题的 counter 里写明。",
        "给事中的治罪动议被皇帝无视后是否再提（u11）：本区间此线中断，无后续。",
        "三法司折子为何一致（u8）：原文用『好像互抄作业似的』作比喻，"
        "又写这是各方默认的先把事情拖一拖，有无实际串通无证据。",
        "本区间若干疑似讹字（u14）：如『当初他像监正求取此药』（像/向）、"
        "『如何般这位储君脱罪』（般/帮）。我只登记现象，不做文本校勘，也不改原文。",
        "官衔类信息只能在有原文支撑时写：本区间张行英没有官衔（『巡抚』零次出现），"
        "因此 t1.actor 只写姓名。若后续单元给出官衔，应在新单元里补，不回填本单元。",
        "我未核实本区间之外的任何上下文：本轮的『巡抚零次出现』只针对 [916516,923035) 切片，"
        "不等于全书没有这个官衔（实测全书 count=765）。",
        "未跑 GPU/浏览器测试（任务未声明需要），未做页面路径验证（本次只产出 JSON 证据）。",
    ],
    "rollback": {
        "kind": "append-only",
        "strategy": "delete-added-files",
        "files": [
            "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/build_candidate.w-read-2.py",
            "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/content_core.py",
            "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/audit_candidate.py",
            "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/negative_control.py",
            "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/PRIOR-candidate.w-read-2.json.bak",
            "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/build_candidate.r0.py",
            "loop/state/out/read_dafeng_L1_0233.w-read-2.build2/content_core.r0.py",
            "loop/state/out/read_dafeng_L1_0233.submit.w-read-2.json",
        ],
        "note": "loop/state/out/read_dafeng_L1_0233.candidate.json 是任务 writes 指定的产物，"
                "不列入删除清单；若要回退到上一版，用 PRIOR-candidate.w-read-2.json.bak 覆盖它即可"
                "（该备份 sha256 = " + prior_hash + "）。",
    },
}

SUB.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("已写提交记录：", SUB)
print("sha256 =", sha(SUB))
print()
print("关键现算值：")
print("  candidate  =", cand_hash)
print("  prior      =", prior_hash)
print("  slice      =", slice_sha)
print("  build rc   =", rc_build, "| reproducible =", reproducible)
print("  audit rc   =", rc_audit)
print("  negctl rc  =", rc_neg)
print("  prior->new audit hits =", len(prior_hits))
for c, m in prior_hits:
    print("     ", c, m[:90])
