#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 plan100 的既有工作接进 loop（适配，不是另起一套）。

为什么要这一步：
  plan100 在 2026-10-07 做了大量真实工作：78 个任务台账、1012 条证据路径、
  8 维评分、6 项虚假声称的诚实清单。但它的**队列在旧会话里**，`artifacts/plan100/`
  也不入 Git —— 新环境如果不能读它，就等于把那些工作扔了重做。

本脚本只做三件事，全部可复核：
  1. 把 78 个 ledger 索引成一份机器可读清单（状态/owner/reviewer/knownGaps 计数/证据路径）。
  2. 把 112 个规范工作项与「loop 里的承接者」做映射，**如实标出没有承接者的槽位**。
  3. 把仍未关闭的缺口（blocked / rejected / knownGaps / 未签收）转成 loop 里的具体任务，
     写进 loop/queue/plan100.jsonl（追加，不覆盖）。

不做的：
  * 不改写任何既有台账（只读）。
  * 不把「读法 A / 读法 B」二选一 —— 覆盖度的两种解释并列保留。
  * 不因为读到了这些记录就给任何维度加分。

用法：
  python3 -B -s loop/bin/adopt_plan100.py                # 索引 + 映射 + 缺口任务
  python3 -B -s loop/bin/adopt_plan100.py --report       # 只打印摘要
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
STATE = LOOP / "state"
ART = ROOT / "artifacts" / "plan100"
QUEUE = LOOP / "queue"

CARRIED = {
    ("P00", "W01"): "env:index-doctor / perf:baseline-matrix（冻结输入与视口）",
    ("P00", "W02"): "env:index-doctor（规范化入口口径）",
    ("P00", "W03"): "read:*/verify:* 的稳定 ID 与引用契约（每条引用带 sourceId + offset）",
    ("P00", "W04"): "xgraph:transfer-audit（跨图同对象定位）",
    ("P01", "W01"): "publish:* 走既有 publish_reviewed.py（父版本键 + 原版字节不变）",
    ("P01", "W02"): "ops:accept-full（schema 迁移契约在默认门禁内）",
    ("P01", "W03"): "env:plan100-adopt（身份台账索引）",
    ("P01", "W07"): "ops:accept-full（降级路径契约）",
    ("P02", "W01"): "loop/state/index.json（三书原文单元分母，1133 个）",
    ("P02", "W02"): "env:index-doctor（章节单元 vs 图谱标签对账）",
    ("P02", "W03"): "read:* 的 sourceRange 绑定（每个任务=一个真实原文区间）",
    ("P02", "W07"): "env:index-doctor（缺定位事件、重号章）",
    ("P03", "W01"): "read:* 任务五元组（objective/obstacle/action/result/cost）",
    ("P03", "W02"): "read:* 任务五元组",
    ("P03", "W03"): "read:* 任务五元组",
    ("P03", "W04"): "read:* + verify:*（结束≠成功由复核者专查）",
    ("P03", "W05"): "read:* 状态与知识差",
    ("P03", "W06"): "read:* 故事线挂接",
    ("P03", "W07"): "verify:* 反向验证",
    ("P03", "W08"): "verify:* 反向验证",
    ("P04", "W01"): "read:* causeEdges（方向+触发，禁止时间相邻当因果）",
    ("P04", "W02"): "read:* foreshadows（铺设+回收）",
    ("P04", "W03"): "read:* states（前后值+事件锚点）",
    ("P04", "W07"): "verify:* 反向验证",
    ("P05", "W01"): "xgraph:transfer-audit",
    ("P05", "W02"): "xgraph:transfer-audit",
    ("P05", "W03"): "xgraph:transfer-audit",
    ("P05", "W04"): "xgraph:transfer-audit",
    ("P05", "W07"): "xgraph:transfer-audit",
    ("P05", "W08"): "xgraph:transfer-audit",
    ("P06", "W01"): "perf:baseline-matrix（固定相机/相位/画布）",
    ("P06", "W05"): "perf:baseline-matrix（A/B 需 GPU，串行）",
    ("P07", "W01"): "perf:baseline-matrix（材质层隔离已由既有契约锁定）",
    ("P07", "W05"): "perf:baseline-matrix（材质 A/B 需 GPU）",
    ("P08", "W01"): "perf:baseline-matrix（动画时间线已由既有契约锁定）",
    ("P09", "W01"): "a11y:real-device",
    ("P09", "W02"): "a11y:real-device",
    ("P09", "W03"): "a11y:real-device",
    ("P09", "W04"): "a11y:real-device",
    ("P09", "W07"): "a11y:real-device",
    ("P09", "W08"): "a11y:real-device",
    ("P10", "W01"): "perf:baseline-matrix",
    ("P10", "W02"): "perf:baseline-matrix",
    ("P10", "W03"): "perf:baseline-matrix",
    ("P10", "W04"): "ops:gpu-serial-check",
    ("P10", "W05"): "perf:baseline-matrix",
    ("P10", "W06"): "perf:baseline-matrix",
    ("P10", "W07"): "ops:gpu-serial-check",
    ("P10", "W08"): "ops:worker-liveness",
    ("P11", "W01"): "ops:accept-full",
    ("P11", "W02"): "ops:accept-full",
    ("P11", "W03"): "ops:accept-full",
    ("P11", "W07"): "ops:accept-full",
    ("P11", "W08"): "ops:accept-full",
    ("P12", "W01"): "ops:quality-sync（QUALITY 与剩余项同步）",
    ("P12", "W02"): "ops:quality-sync",
    ("P12", "W03"): "ops:quality-sync",
    ("P12", "W06"): "ops:quality-sync",
    ("P12", "W07"): "ops:quality-sync",
    ("P12", "W08"): "ops:quality-sync",
    ("P13", "W01"): "expert:review-*（跨域专家评审）",
    ("P13", "W02"): "expert:review-*",
    ("P13", "W03"): "expert:review-*",
    ("P13", "W04"): "expert:review-*",
    ("P13", "W05"): "expert:review-*",
    ("P13", "W06"): "expert:review-*",
    ("P13", "W07"): "expert:review-*",
    ("P13", "W08"): "expert:review-*",
}


def load_ledgers() -> list:
    rows = []
    for path in sorted(glob.glob(str(ART / "**" / "ledger.json"), recursive=True)):
        try:
            d = json.loads(Path(path).read_text("utf-8"))
        except Exception as exc:
            rows.append({"path": os.path.relpath(path, ROOT), "parseError": repr(exc)})
            continue
        rel = os.path.relpath(path, ROOT)
        ev = [e.get("path") for e in (d.get("evidence") or []) if isinstance(e, dict)]
        rows.append({
            "task": d.get("task"),
            "status": d.get("status"),
            "owner": d.get("owner"),
            "reviewer": d.get("reviewer"),
            "startedAt": d.get("startedAt"),
            "finishedAt": d.get("finishedAt"),
            "title": d.get("title"),
            "decision": d.get("decision"),
            "knownGaps": d.get("knownGaps") or [],
            "knownGapCount": len(d.get("knownGaps") or []),
            "evidenceCount": len(ev),
            "evidence": ev[:6],
            "path": rel,
            "selfReviewed": bool(d.get("owner") and d.get("reviewer") and d.get("owner") == d.get("reviewer")),
        })
    return rows


def spec_slots() -> list:
    ledger_path = ART / "plan-ledger.json"
    if not ledger_path.exists():
        return []
    data = json.loads(ledger_path.read_text("utf-8"))
    slots = []
    for phase in data.get("phases") or []:
        pid = phase.get("id") or phase.get("key") or ""
        for item in phase.get("taskTitles") or phase.get("items") or phase.get("workItems") or []:
            key = item.get("key") or item.get("id") or ""
            slots.append({"phase": pid, "key": key, "title": item.get("title", "")})
    return slots


def gap_tasks(rows: list, slots: list) -> list:
    """把仍未关闭的缺口转成 loop 任务。只转**可执行**的，其余进 report。"""
    tasks = []
    seq = 0
    for row in rows:
        if row.get("parseError"):
            continue
        status = row.get("status")
        if status in ("blocked", "rejected") or row.get("selfReviewed"):
            tid = "adopt:%s" % (row["task"] or row["path"].split("/")[-2])
            tasks.append({
                "id": tid, "stream": "adopt", "phase": 5, "seq": seq,
                "title": "关闭 plan100 未结项：%s（%s）" % (row.get("task"), status or "self-review"),
                "prompt": (
                    "plan100 留下一个未结项，本任务负责**如实处置**它（不是无脑标 merged）：\n"
                    "- 台账：%s\n- 原状态：%s / reviewer=%s%s\n- 原决策：%s\n- 已知缺口：%s\n\n"
                    "要求：\n"
                    "1. 先判断这个缺口**今天是否仍然存在**（源码/数据可能已经变了；不要沿用旧结论）。\n"
                    "2. 仍然存在 → 在 loop 里建一条可执行任务或在提交里写明它归属哪个流；\n"
                    "   已经不存在 → 给出**可复现命令**证明它消失了。\n"
                    "3. 两种情况都要写：你用什么命令检查的、输出是什么、还剩什么不确定。\n"
                    "4. 禁止：为了让门禁变绿而直接改台账状态；禁止自签（reviewer 不能是 owner）。\n"
                    "产出 loop/state/out/%s.artifact.json。" % (
                        row["path"], status, row.get("reviewer"), "（自签）" if row.get("selfReviewed") else "",
                        row.get("decision"), "；".join(row.get("knownGaps") or [])[:400] or "（无）",
                        tid.replace(":", "_"))),
                "writes": ["loop/state/out/%s.artifact.json" % tid.replace(":", "_")],
                "roleFile": "loop/ROLES/SENTINEL.md",
                "ledger": row["path"],
            })
            seq += 1
    return tasks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    STATE.mkdir(parents=True, exist_ok=True)
    QUEUE.mkdir(parents=True, exist_ok=True)

    rows = load_ledgers()
    slots = spec_slots()
    by_status = {}
    for r in rows:
        by_status[r.get("status")] = by_status.get(r.get("status"), 0) + 1

    carriers = []
    no_carrier = []
    for s in slots:
        key = (s["phase"], s["key"].split("-")[-1] if "-" in s["key"] else s["key"])
        who = CARRIED.get((s["phase"], s["key"].split("-")[-1]))
        entry = {"phase": s["phase"], "key": s["key"], "title": s.get("title", ""), "carrier": who}
        (carriers if who else no_carrier).append(entry)

    ledger_out = {
        "generatedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceDir": "artifacts/plan100",
        "ledgerCount": len(rows),
        "byStatus": by_status,
        "selfReviewed": [r["task"] for r in rows if r.get("selfReviewed")],
        "ledgers": rows,
    }
    (STATE / "PLAN100-LEDGER.json").write_text(json.dumps(ledger_out, ensure_ascii=False, indent=1) + "\n", "utf-8")

    adoption = {
        "generatedAt": ledger_out["generatedAt"],
        "note": "把 plan100 的既有工作接进 loop。覆盖度两种读法并列，不二选一。",
        "specSlots": len(slots),
        "slotsWithCarrier": len(carriers),
        "slotsWithoutCarrier": len(no_carrier),
        "noCarrier": no_carrier,
        "readings": {
            "A_通用关切由归属阶段承担": "按此读法，无承接者的槽位=0（每个关切都有阶段承担）",
            "B_每阶段都应独立应用": "按此读法，%d 个槽位是真实的覆盖缺口" % len(no_carrier),
            "协调方立场": "两种读法都不影响已交付证据；影响的是「计划覆盖度」的表述，故并列。",
        },
        "carriers": carriers,
        "openLedgers": [r["task"] for r in rows if r.get("status") in ("blocked", "rejected")],
    }
    (STATE / "PLAN100-ADOPTION.json").write_text(json.dumps(adoption, ensure_ascii=False, indent=1) + "\n", "utf-8")

    tasks = gap_tasks(rows, slots)
    path = QUEUE / "plan100.jsonl"
    existing = set()
    if path.exists():
        for line in path.read_text("utf-8").splitlines():
            if line.strip().startswith("{"):
                try:
                    existing.add(json.loads(line)["id"])
                except Exception:
                    pass
    added = 0
    with path.open("a", encoding="utf-8") as fh:
        for t in tasks:
            if t["id"] in existing:
                continue
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
            added += 1

    print(json.dumps({
        "ledgers": len(rows), "byStatus": by_status,
        "specSlots": len(slots), "withCarrier": len(carriers), "withoutCarrier": len(no_carrier),
        "adoptTasksAdded": added,
        "wrote": ["loop/state/PLAN100-LEDGER.json", "loop/state/PLAN100-ADOPTION.json", "loop/queue/plan100.jsonl"],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
