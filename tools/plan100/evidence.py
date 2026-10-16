#!/usr/bin/env python3
"""P00 证据基础设施：source-manifest、task ledger 与 scorecard 写入器。

计划要求每个工作包产出：
  artifacts/plan100/YYYYMMDD/<task-id>/
    baseline/ candidate/ reports/
    source-manifest.json  rollback.patch  decision.md

并要求签收字段 status/owner/startedAt/finishedAt/inputHashes/commands/
evidence/assertions/knownGaps/rollback/reviewer —— 缺任一字段不得标记 merged。

本模块把这些要求固化成可调用 API，供各子代理统一写入，避免各自发明格式。

CLI:
  python3 tools/plan100/evidence.py init    --task P02-W03 [--date YYYYMMDD]
  python3 tools/plan100/evidence.py hash    --task P02-W03 FILE [FILE...]
  python3 tools/plan100/evidence.py manifest --task P02-W03 --file X --command Y
  python3 tools/plan100/evidence.py status  --task P02-W03 --set cpu-verified --owner X
  python3 tools/plan100/evidence.py signoff --task P02-W03 --reviewer X
  python3 tools/plan100/evidence.py score   --dim narrative --score 18 --evidence PATH
  python3 tools/plan100/evidence.py report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def artifact_path(*parts: str) -> Path:
    """Shared output root; explicit CLI paths remain caller-controlled.

    CL_ARTIFACTS selects a persistent external location. Without it, generated
    reports stay under the system temporary directory, never the source tree.
    """
    configured = os.environ.get("CL_ARTIFACTS")
    base = Path(configured).expanduser() if configured else Path(tempfile.gettempdir()) / "castline-artifacts"
    return base.resolve().joinpath(*parts)


PLAN_DIR = artifact_path("plan100")

STATES = [
    "planned",
    "baseline-captured",
    "implementing",
    "cpu-verified",
    "gpu-verified",
    "art-reviewed",
    "merged",
    "rejected",
    "blocked",
]

REQUIRED_SIGNOFF = [
    "status",
    "owner",
    "startedAt",
    "inputHashes",
    "commands",
    "evidence",
    "assertions",
    "knownGaps",
    "rollback",
    "reviewer",
]

DIMENSIONS = {
    "visual": 12,
    "rendering": 12,
    "animation": 10,
    "interaction": 14,
    "readability": 14,
    "narrative": 22,
    "evidence": 10,
    "delivery": 6,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.now().strftime("%Y%m%d")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def workspace_hash() -> str:
    """工作树指纹：HEAD 提交 + 已跟踪文件的内容哈希。"""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        diff = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
        h = hashlib.sha256((head + diff).encode()).hexdigest()
        return f"sha256:{h[:32]}@{head[:12]}"
    except Exception:
        return "sha256:unavailable"


def task_dir(task: str, date: str | None = None) -> Path:
    return PLAN_DIR / (date or today()) / task


def init_task(task: str, date: str | None = None) -> Path:
    d = task_dir(task, date)
    for sub in ("baseline", "candidate", "reports"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    ledger_path = d / "ledger.json"
    if not ledger_path.exists():
        ledger_path.write_text(
            json.dumps(
                {
                    "task": task,
                    "status": "planned",
                    "owner": None,
                    "reviewer": None,
                    "startedAt": utcnow(),
                    "finishedAt": None,
                    "inputHashes": [],
                    "commands": [],
                    "evidence": [],
                    "assertions": [],
                    "knownGaps": [],
                    "rollback": None,
                    "decision": None,
                    "notes": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return d


def load_ledger(task: str, date: str | None = None) -> tuple[Path, dict]:
    d = init_task(task, date)
    p = d / "ledger.json"
    return p, json.loads(p.read_text(encoding="utf-8"))


def save_ledger(p: Path, data: dict) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def device_info() -> dict:
    gpu = "unknown"
    try:
        out = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True, timeout=20
        ).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Chipset Model:"):
                gpu = line.split(":", 1)[1].strip()
                break
    except Exception:
        pass
    return {
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "python": platform.python_version(),
        "gpu": gpu,
    }


# ---------------------------------------------------------------- subcommands


def cmd_init(args) -> int:
    d = init_task(args.task, args.date)
    print(rel(d))
    return 0


def cmd_hash(args) -> int:
    p, data = load_ledger(args.task, args.date)
    for f in args.files:
        fp = Path(f)
        if not fp.exists():
            print(f"missing: {f}", file=sys.stderr)
            continue
        entry = {"path": rel(fp), "sha256": sha256_file(fp), "bytes": fp.stat().st_size}
        data["inputHashes"] = [e for e in data["inputHashes"] if e["path"] != entry["path"]]
        data["inputHashes"].append(entry)
        print(f"{entry['sha256'][:16]}  {entry['path']}")
    save_ledger(p, data)
    return 0


def cmd_manifest(args) -> int:
    p, data = load_ledger(args.task, args.date)
    d = p.parent
    entry = {
        "at": utcnow(),
        "files": args.file or [],
        "command": args.command or [],
        "device": device_info(),
        "workspaceHash": workspace_hash(),
        "serverBuild": os.environ.get("ATLAS_BASE", ""),
    }
    mpath = d / "source-manifest.json"
    existing = []
    if mpath.exists():
        try:
            existing = json.loads(mpath.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                existing = [existing]
        except Exception:
            existing = []
    existing.append(entry)
    mpath.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for f in args.file or []:
        fp = Path(f)
        if fp.exists():
            he = {"path": rel(fp), "sha256": sha256_file(fp), "bytes": fp.stat().st_size}
            data["inputHashes"] = [e for e in data["inputHashes"] if e["path"] != he["path"]]
            data["inputHashes"].append(he)
    for c in args.command or []:
        data["commands"].append({"at": utcnow(), "cmd": c})
    save_ledger(p, data)
    print(rel(mpath))
    return 0


def cmd_status(args) -> int:
    if args.set not in STATES:
        print(f"invalid status {args.set}; one of {STATES}", file=sys.stderr)
        return 2
    p, data = load_ledger(args.task, args.date)
    data["status"] = args.set
    if args.owner:
        data["owner"] = args.owner
    if args.set in ("merged", "rejected", "blocked", "art-reviewed"):
        data["finishedAt"] = data["finishedAt"] or utcnow()
    save_ledger(p, data)
    print(f"{args.task}: {args.set}")
    return 0


def cmd_evidence(args) -> int:
    p, data = load_ledger(args.task, args.date)
    for e in args.path:
        data["evidence"].append({"path": e, "at": utcnow(), "kind": args.kind or "artifact"})
    for a in args.assertion or []:
        data["assertions"].append({"text": a, "at": utcnow(), "result": args.result or "pass"})
    for g in args.gap or []:
        data["knownGaps"].append(g)
    save_ledger(p, data)
    print(f"{args.task}: evidence={len(data['evidence'])} assertions={len(data['assertions'])}")
    return 0


def cmd_rollback(args) -> int:
    p, data = load_ledger(args.task, args.date)
    d = p.parent
    out = d / "rollback.patch"

    files: list[str] = list(getattr(args, "files", None) or [])
    for h in data.get("inputHashes") or []:
        fp = h.get("path")
        if fp and fp not in files:
            files.append(fp)
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "--", *files] if files else ["git", "ls-files"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.split()
    except Exception:
        tracked = []
    targets = [f for f in files if f in set(tracked)]

    if targets:
        r = subprocess.run(
            ["git", "diff", "--binary", "--", *targets],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        patch_text = r.stdout
    else:
        patch_text = ""

    untracked = [f for f in files if f not in set(tracked)]
    header = [
        f"# rollback.patch · task={args.task}",
        f"# 生成时间: {utcnow()}",
        "# 范围: 仅本任务登记的文件（非全树）。用法: git apply -R <此文件>",
        f"# 纳入 diff 的已跟踪文件 ({len(targets)}):",
        *[f"#   {t}" for t in targets],
    ]
    if untracked:
        header += [
            f"# 未跟踪文件（git diff 不含，需手工删除）({len(untracked)}):",
            *[f"#   {u}" for u in untracked],
        ]
    if not files:
        header.append("# 警告: ledger 未登记任何文件，补丁为空。请先跑 `manifest --file ...`")

    out.write_text("\n".join(header) + "\n" + patch_text, encoding="utf-8")
    data["rollback"] = {
        "patch": rel(out),
        "bytes": len(patch_text),
        "scope": "task-files-only",
        "trackedFiles": targets,
        "untrackedFiles": untracked,
        "headAtCapture": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip(),
        "at": utcnow(),
    }
    save_ledger(p, data)
    print(f"{rel(out)}  ({len(patch_text)} bytes, {len(targets)} tracked, {len(untracked)} untracked)")
    return 0


def cmd_signoff(args) -> int:
    p, data = load_ledger(args.task, args.date)
    if args.reviewer:
        data["reviewer"] = args.reviewer
    if args.owner:
        data["owner"] = args.owner
    if args.decision:
        data["decision"] = args.decision
    missing = [f for f in REQUIRED_SIGNOFF if not data.get(f)]
    if data.get("status") == "merged" and missing:
        print(f"REFUSE merged: missing signoff fields {missing}", file=sys.stderr)
        return 3
    save_ledger(p, data)
    print(f"{args.task}: status={data['status']} missing={missing or 'none'}")
    return 0


def scorecard_path() -> Path:
    return PLAN_DIR / "scorecard.json"


def load_scorecard() -> dict:
    p = scorecard_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    base = {}
    return {
        "project": "Castline · 小说星图",
        "baselineScore": base.get("overall"),
        "baselineDate": base.get("auditedAt"),
        "method": "每项必须写入 score/evidence/reviewer/testedAt/knownGaps；未测写 null",
        "dimensions": [
            {
                "id": d["id"],
                "name": d["name"],
                "max": d["max"],
                "baseline": next(
                    (x.get("score") for x in base.get("dimensions", []) if x.get("id") == d["id"]),
                    None,
                ),
                "score": None,
                "evidence": [],
                "reviewer": None,
                "testedAt": None,
                "knownGaps": [],
            }
            for d in base.get("dimensions", [])
            or [{"id": k, "name": k, "max": v} for k, v in DIMENSIONS.items()]
        ],
    }


def cmd_score(args) -> int:
    sc = load_scorecard()
    dim = next((d for d in sc["dimensions"] if d["id"] == args.dim), None)
    if dim is None:
        print(f"unknown dimension {args.dim}", file=sys.stderr)
        return 2
    if args.score is not None:
        if not 0 <= args.score <= dim["max"]:
            print(f"score must be 0..{dim['max']}", file=sys.stderr)
            return 2
        dim["score"] = args.score
    for e in args.evidence or []:
        dim["evidence"].append(e)
    for g in args.gap or []:
        dim["knownGaps"].append(g)
    if args.reviewer:
        dim["reviewer"] = args.reviewer
    dim["testedAt"] = utcnow()
    sc["updatedAt"] = utcnow()
    scored = [d for d in sc["dimensions"] if d["score"] is not None]
    sc["overall"] = sum(d["score"] for d in scored) if len(scored) == len(sc["dimensions"]) else None
    scorecard_path().write_text(json.dumps(sc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.dim}: {dim['score']}/{dim['max']}  overall={sc['overall']}")
    return 0


def cmd_report(args) -> int:
    rows = []
    for date_dir in sorted(PLAN_DIR.iterdir()) if PLAN_DIR.exists() else []:
        if not date_dir.is_dir():
            continue
        for td in sorted(date_dir.iterdir()):
            lp = td / "ledger.json"
            if not lp.exists():
                continue
            data = json.loads(lp.read_text(encoding="utf-8"))
            missing = [f for f in REQUIRED_SIGNOFF if not data.get(f)]
            rows.append((data["task"], data["status"], len(data["evidence"]), missing))
    print(f"{'task':14s} {'status':18s} {'ev':>3s}  missing-signoff")
    for t, s, n, m in rows:
        print(f"{t:14s} {s:18s} {n:3d}  {','.join(m) if m else '-'}")
    print(f"\ntotal tasks: {len(rows)}")
    by = {}
    for _, s, _, _ in rows:
        by[s] = by.get(s, 0) + 1
    print("by status:", json.dumps(by, ensure_ascii=False))
    sc = load_scorecard()
    for d in sc["dimensions"]:
        got = d["score"] if d["score"] is not None else f"未测(基线{d['baseline']})"
        print(f"  {d['id']:12s} {str(got):>10s} / {d['max']}")
    print(f"  overall: {sc.get('overall')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=None, help="CL_ARTIFACTS 产物根内的日期目录，默认今天")
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--date", default=None)

    p = sub.add_parser("init", parents=[common]); p.add_argument("--task", required=True); p.set_defaults(fn=cmd_init)

    p = sub.add_parser("hash", parents=[common]); p.add_argument("--task", required=True)
    p.add_argument("files", nargs="+"); p.set_defaults(fn=cmd_hash)

    p = sub.add_parser("manifest", parents=[common]); p.add_argument("--task", required=True)
    p.add_argument("--file", action="append"); p.add_argument("--command", action="append")
    p.set_defaults(fn=cmd_manifest)

    p = sub.add_parser("status", parents=[common]); p.add_argument("--task", required=True)
    p.add_argument("--set", required=True); p.add_argument("--owner")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("evidence", parents=[common]); p.add_argument("--task", required=True)
    p.add_argument("--path", action="append"); p.add_argument("--kind")
    p.add_argument("--assertion", action="append"); p.add_argument("--result")
    p.add_argument("--gap", action="append")
    p.set_defaults(fn=cmd_evidence)

    p = sub.add_parser("rollback", parents=[common]); p.add_argument("--task", required=True)
    p.add_argument("--files", nargs="*", default=[])
    p.set_defaults(fn=cmd_rollback)

    p = sub.add_parser("signoff", parents=[common]); p.add_argument("--task", required=True)
    p.add_argument("--reviewer"); p.add_argument("--owner"); p.add_argument("--decision")
    p.set_defaults(fn=cmd_signoff)

    p = sub.add_parser("score", parents=[common]); p.add_argument("--dim", required=True)
    p.add_argument("--score", type=int); p.add_argument("--evidence", action="append")
    p.add_argument("--gap", action="append"); p.add_argument("--reviewer")
    p.set_defaults(fn=cmd_score)

    p = sub.add_parser("report", parents=[common]); p.set_defaults(fn=cmd_report)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
