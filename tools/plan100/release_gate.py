#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P12 · 发布门禁（计划第六节第 1 条）。

计划原文要求：
    读取所有任务台账，过滤 `status != merged`、`knownGaps` 为空但没有证据、
    或 `reviewer` 缺失的条目。

本脚本把这三条固化成可执行门禁，并**诚实报告**：
  * 任何未签收项都会出现在 `blockers` 里；
  * 只要 blockers 非空，进程 exit 非零 —— 不因为"大部分完成了"就放行。

额外守则（与 BRIEFING 硬性原则一致）：
  * `knownGaps` 为空**不等于**没问题：必须同时有非空 `evidence`。空 gaps + 空证据
    = "没发现问题"和"没检查"不可区分 → 拦截。
  * `reviewer` 不能等于 `owner`（自己给自己签收不算独立复核）→ 单独记为
    `self-review` 告警，默认也拦截（可用 --allow-self-review 降级为告警）。
  * `status == merged` 但仍出现在过滤结果里的条目（例如被人工改成 merged 却缺
    必填字段）同样拦截。
  * ledger 结构无法识别时**不跳过**，记 `unknownLedgerSchema` 并拦截。

用法：
    python3 tools/plan100/release_gate.py                     # 写 gate-report.json
    python3 tools/plan100/release_gate.py --json               # 同时打印报告
    python3 tools/plan100/release_gate.py --allow-self-review  # 自审降级为告警
    python3 tools/plan100/release_gate.py --quiet              # 只留 exit code
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
PLAN_DIR = artifact_path() / "plan100"
RELEASE_DIR = PLAN_DIR / "release"
DEFAULT_OUT = RELEASE_DIR / "gate-report.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence as ev

REQUIRED = list(ev.REQUIRED_SIGNOFF)
REQUIRED_WITHOUT_GAPS = [f for f in REQUIRED if f != "knownGaps"]

SKIP_DIRS = {"release"}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def discover_ledgers() -> list[Path]:
    out: list[Path] = []
    if not PLAN_DIR.exists():
        return out
    for date_dir in sorted(PLAN_DIR.iterdir()):
        if not date_dir.is_dir() or date_dir.name in SKIP_DIRS:
            continue
        for task_dir in sorted(date_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            lp = task_dir / "ledger.json"
            if lp.exists():
                out.append(lp)
    return out


def _nonempty(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (list, tuple, dict, set)):
        return len(v) > 0
    return True


def _evidence_is_real(ledger: dict, date_dir: Path, task_dir: Path) -> tuple[bool, list[str]]:
    """证据条目必须指向真实存在的文件，或指向 ledger 目录下的相对路径。

    "有证据"不能只是列表非空 —— 计划批评的正是"写了路径但文件不在"。
    """
    problems: list[str] = []
    ev_list = ledger.get("evidence") or []
    if not _nonempty(ev_list):
        return False, ["证据列表为空"]
    good = 0
    for e in ev_list:
        p = e.get("path") if isinstance(e, dict) else e
        if not isinstance(p, str) or not p.strip():
            problems.append("证据条目缺少 path")
            continue
        cand = [ROOT / p, task_dir / p, task_dir / "reports" / p, task_dir / "candidate" / p,
                task_dir / "baseline" / p, date_dir / p]
        if any(c.exists() for c in cand):
            good += 1
        else:
            problems.append("证据文件不存在：%s" % p)
    return good > 0, problems


def audit_ledger(lp: Path, allow_self_review: bool) -> dict:
    date_dir = lp.parent.parent
    task_dir = lp.parent
    rec = {
        "task": None,
        "path": _rel(lp),
        "status": None,
        "owner": None,
        "reviewer": None,
        "evidenceCount": 0,
        "knownGapCount": 0,
        "blockers": [],
        "warnings": [],
        "parseError": None,
    }
    try:
        data = json.loads(lp.read_text(encoding="utf-8"))
    except Exception as exc:
        rec["parseError"] = str(exc)
        rec["blockers"].append({"task": task_dir.name, "reason": "ledger.json 无法解析",
                                "detail": str(exc), "rule": "内部一致性", "kind": "p0"})
        return rec
    if not isinstance(data, dict):
        rec["parseError"] = "ledger 顶层不是对象 (got %s)" % type(data).__name__
        rec["blockers"].append({"task": task_dir.name, "reason": "ledger 结构无法识别",
                                "detail": "顶层类型 %s" % type(data).__name__, "rule": "无关卡", "kind": "p0"})
        return rec

    task = data.get("task") or task_dir.name
    rec["task"] = task
    rec["status"] = data.get("status")
    rec["owner"] = data.get("owner")
    rec["reviewer"] = data.get("reviewer")
    rec["evidenceCount"] = len(data.get("evidence") or [])
    rec["knownGapCount"] = len(data.get("knownGaps") or [])
    rec["decision"] = data.get("decision")

    def block(reason: str, rule: str, detail=None, kind: str = "plan-filter"):
        rec["blockers"].append({"task": task, "reason": reason, "rule": rule,
                                "kind": kind, "detail": detail})

    status = data.get("status")
    if status != "merged":
        block("status=%r（非 merged）" % (status,), "计划第六节 1 · status != merged")

    ev_real, ev_problems = _evidence_is_real(data, date_dir, task_dir)
    if not _nonempty(data.get("knownGaps")) and not ev_real:
        block("knownGaps 为空且没有可用证据（“没发现问题”与“没检查”不可区分）",
              "计划第六节 1 · knownGaps 为空但没有证据")
    elif ev_problems:
        rec["warnings"].append({"task": task, "reason": "部分证据路径不可达", "detail": ev_problems})

    if not _nonempty(data.get("reviewer")):
        block("reviewer 缺失（没有独立复核者不得写 merged）", "计划第六节 1 · reviewer 缺失")

    if status == "merged":
        missing = [f for f in REQUIRED_WITHOUT_GAPS if not _nonempty(data.get(f))]
        if missing:
            block("status=merged 但必填签收字段缺失：%s" % ", ".join(missing),
                  "签收字段完整性", kind="p0")

    if _nonempty(data.get("reviewer")) and data.get("reviewer") == data.get("owner"):
        item = {"task": task, "reason": "reviewer 与 owner 相同（自我签收，非独立复核）",
                "rule": "独立复核", "kind": "p0"}
        if allow_self_review:
            rec["warnings"].append(item)
        else:
            rec["blockers"].append(item)

    if status == "merged" and not _nonempty(data.get("decision")):
        rec["warnings"].append({"task": task, "reason": "status=merged 但 ledger.decision 为空",
                                "rule": "decision 记录"})
    if status == "merged":
        dm = task_dir / "decision.md"
        if not dm.exists():
            rec["warnings"].append({"task": task, "reason": "缺少 decision.md（计划要求手写）",
                                    "rule": "decision 记录"})
    return rec


def p0_count(records: list[dict]) -> int:
    """P0 计数：伪造/自签/结构不可识别这类致命项。

    规则 1（status != merged）与规则 2/3 只是"尚未完成"或"证据不足"，
    属于计划第六节的发布过滤条件，不是 P0。
    P0 = 会污染发布判断的致命项：必填字段缺失却写 merged、自我签收、
    ledger 结构无法识别。
    """
    return sum(1 for r in records for b in r["blockers"] if b.get("kind") == "p0")


def build(allow_self_review: bool) -> dict:
    ledgers = discover_ledgers()
    records = [audit_ledger(lp, allow_self_review) for lp in ledgers]
    blockers = [b for r in records for b in r["blockers"]]
    warnings = [w for r in records for w in r["warnings"]]
    merged = [r for r in records if r["status"] == "merged"]
    unmerged = [r for r in records if r["status"] != "merged"]
    by_rule: dict[str, int] = {}
    for b in blockers:
        by_rule[b.get("rule")] = by_rule.get(b.get("rule"), 0) + 1
    return {
        "reportVersion": "plan100/p12/1",
        "generatedAt": utcnow(),
        "rule": "计划第六节第 1 条：过滤 status != merged、knownGaps 为空但没有证据、reviewer 缺失的条目。",
        "scan": {
            "roots": [str(PLAN_DIR / "*" / "*" / "ledger.json")],
            "ledgerCount": len(ledgers),
        },
        "ok": len(blockers) == 0,
        "p0Count": p0_count(records),
        "mergedCount": len(merged),
        "unmergedCount": len(unmerged),
        "blockerCount": len(blockers),
        "blockersByRule": by_rule,
        "warningCount": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "tasks": records,
        "unknownLedgerSchema": any(b.get("rule") == "无关卡" for b in blockers),
        "honesty": {
            "note": (
                "blocker 非空即 exit 非零。`ok=true` 仅表示“所有已登记台账都签收完毕”，"
                "不等于“发布达到 100 分”——分数与门槛由 release-manifest.json 裁决。"
            ),
            "emptyMeansUntested": "knownGaps 为空但无证据 = 未检查，一律拦截。",
            "p0Definition": (
                "P0 = 必填签收字段缺失却写 merged / reviewer==owner 自签 / ledger 结构不可识别。"
                "status != merged 属于“尚未完成”，不计 P0。"
            ),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--json", dest="dump", action="store_true")
    ap.add_argument("--allow-self-review", action="store_true",
                    help="把 reviewer==owner 从拦截降级为告警")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    report = build(args.allow_self_review)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.quiet:
        print("release-gate: %s" % _rel(out))
        print("ledgers=%d merged=%d unmerged=%d blockers=%d warnings=%d p0=%d"
              % (report["scan"]["ledgerCount"], report["mergedCount"], report["unmergedCount"],
                 report["blockerCount"], report["warningCount"], report["p0Count"]))
        if report["blockers"]:
            print("\n未签收（发布门禁拦截）:")
            for b in report["blockers"]:
                print("  ✗ %-12s %s" % (b.get("task"), b.get("reason")))
                print("      rule: %s" % b.get("rule"))
        else:
            print("\n全部已登记台账通过过滤。")
        if report["warnings"]:
            print("\n告警:")
            for w in report["warnings"]:
                print("  ! %-12s %s" % (w.get("task"), w.get("reason")))
        print("\nGATE: %s" % ("PASS" if report["ok"] else "BLOCKED"))
        if args.dump:
            print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
