#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P12 · 客户验收包索引（package-index.json）。

README 里写了「你可以自己跑这些命令」——本脚本**真的去跑**其中可离线执行的命令，
把退出码与输出摘要写进 package-index.json。README 的承诺因此可被机器核对，
而不是一段手写的话。

不跑：`--browser`（GPU 串行，需人工排期）、真机相关（无设备）。
不写：data/ 下任何文件。

用法：
    python3 tools/plan100/acceptance_package.py                # 跑命令 + 写索引
    python3 tools/plan100/acceptance_package.py --no-run       # 只索引不跑
    python3 tools/plan100/acceptance_package.py --base URL     # 指定在线实例
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
PKG = artifact_path() / "plan100" / "release" / "acceptance-package"
RELEASE = artifact_path() / "plan100" / "release"

CHECKS = [
    {
        "id": "offline-accept",
        "cmd": ["sh", "scripts/accept.sh"],
        "timeout": 900,
        "claim": "离线验收门禁 62 项全通过",
        "expectZeroExit": True,
        "note": "并行代理正在改业务代码时可能短暂失败；失败不代表本包流水线有问题。",
    },
    {
        "id": "release-gate",
        "cmd": [sys.executable, "tools/plan100/release_gate.py", "--quiet"],
        "timeout": 120,
        "claim": "存在未签收项时门禁必须拦截（exit 非零）",
        "expectZeroExit": False,
        "note": "预期非零：当前台账仍有未签收项。变绿而未签收项还在才是 bug。",
    },
    {
        "id": "release-manifest",
        "cmd": [sys.executable, "tools/plan100/release_manifest.py"],
        "timeout": 300,
        "claim": "一条命令生成含计划全部字段的发布清单",
        "expectZeroExit": True,
    },
    {
        "id": "manifest-verdict",
        "cmd": [sys.executable, "tools/plan100/release_manifest.py", "--verdict"],
        "timeout": 300,
        "claim": "裁决行输出：未签收（不谎称 100 分候选）",
        "expectZeroExit": False,
        "note": "预期非零：未达门槛/未测维度存在。",
    },
    {
        "id": "health-redaction",
        "cmd": [sys.executable, "tools/plan100/health_redaction_test.py"],
        "timeout": 300,
        "claim": "健康检查 / 日志脱敏实证 / 缓存失效 9 项通过",
        "expectZeroExit": True,
    },
    {
        "id": "rollback-drill",
        "cmd": ["sh", "tools/plan100/rollback_drill.sh"],
        "timeout": 300,
        "claim": "回滚演练：逐字节还原 + 相邻契约复跑通过",
        "expectZeroExit": True,
    },
    {
        "id": "device-matrix-honesty",
        "cmd": [sys.executable, "tools/plan100/device_matrix_status.py", "--check"],
        "timeout": 120,
        "claim": "设备矩阵诚实化：仿真不写成真机签收",
        "expectZeroExit": True,
    },
    {
        "id": "version-stamp",
        "cmd": [sys.executable, "tests/version_stamp.py", "--check"],
        "timeout": 180,
        "claim": "资源版本戳与内容哈希一致，0 漂移",
        "expectZeroExit": True,
    },
]

NOT_RUN = [
    {"id": "browser-accept", "cmd": "ATLAS_BASE=... sh scripts/accept.sh --browser",
     "reason": "GPU 串行；计划禁止并发 GPU。需人工排期，且须在干净工作树上跑。"},
    {"id": "real-device", "cmd": "iPhone Safari / Android Chrome / VoiceOver / TalkBack",
     "reason": "本机无物理设备、无 adb、无 simctl；safaridriver 未授权。真机未签收。"},
    {"id": "blind-review", "cmd": "三书固定九视图与连续旅程独立盲审",
     "reason": "需独立审阅者，不在 P12 执行范围。"},
]


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(p: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with p.open("rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                digest.update(b)
        return digest.hexdigest()
    except OSError:
        return None


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def run_check(c: dict) -> dict:
    rec = {"id": c["id"], "cmd": " ".join(c["cmd"]), "claim": c["claim"],
           "expectZeroExit": c["expectZeroExit"], "note": c.get("note")}
    try:
        r = subprocess.run(c["cmd"], cwd=ROOT, capture_output=True, text=True, timeout=c["timeout"])
    except subprocess.TimeoutExpired:
        rec.update({"exit": None, "timeout": True, "ok": False,
                    "detail": "超时 %ss" % c["timeout"]})
        return rec
    except Exception as exc:
        rec.update({"exit": None, "ok": False, "detail": str(exc)})
        return rec
    out = (r.stdout or "") + (("\n" + r.stderr) if (r.stderr or "").strip() else "")
    tail = [ln for ln in out.strip().splitlines() if ln.strip()][-8:]
    rec.update({"exit": r.returncode, "tail": tail,
                "ok": (r.returncode == 0) == bool(c["expectZeroExit"])})
    return rec


def package_files() -> list[dict]:
    out = []
    if PKG.exists():
        for p in sorted(PKG.rglob("*")):
            if p.is_file():
                out.append({"path": rel(p), "bytes": p.stat().st_size, "sha256": sha256_file(p)})
    return out


def evidence_refs() -> list[dict]:
    names = [
        "release-manifest.json", "gate-report.json", "device-matrix-status.md",
        "device-matrix-status.json", "health-redaction-evidence.json",
        "rollback-drill/latest.json", "rollback-drill/drill.log", "rollback-drill/drill.patch",
    ]
    out = []
    for n in names:
        p = RELEASE / n
        out.append({"path": rel(p), "exists": p.exists(),
                    "bytes": p.stat().st_size if p.exists() else None,
                    "sha256": sha256_file(p) if p.exists() else None})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-run", action="store_true", help="只写索引，不执行验证命令")
    ap.add_argument("--base", default=None, help="在线实例，如 http://127.0.0.1:8765")
    args = ap.parse_args()

    checks: list[dict] = []
    if args.no_run:
        for c in CHECKS:
            checks.append({"id": c["id"], "cmd": " ".join(c["cmd"]), "claim": c["claim"],
                           "expectZeroExit": c["expectZeroExit"], "ran": False})
    else:
        for c in CHECKS:
            cmd = list(c["cmd"])
            if c["id"] == "health-redaction" and args.base:
                cmd += ["--base", args.base]
            c2 = dict(c); c2["cmd"] = cmd
            print("[run] %s" % " ".join(cmd), flush=True)
            rec = run_check(c2)
            rec["ran"] = True
            print("      exit=%s ok=%s" % (rec.get("exit"), rec.get("ok")), flush=True)
            checks.append(rec)

    ran = [c for c in checks if c.get("ran")]
    idx = {
        "packageVersion": "plan100/p12/1",
        "generatedAt": utcnow(),
        "project": "Castline · 小说星图",
        "rollbackCommit": _head(),
        "readme": rel(PKG / "README.md"),
        "boundary": (
            "本包分「已实现」与「未签收」两部分。已实现项可由本文件的 checks[] 机器核对；"
            "未签收项（真机矩阵、读屏认证、真机缩放旅程、独立盲审、评分）一律不计入交付。"
        ),
        "checks": checks,
        "checksRan": len(ran),
        "checksOk": len([c for c in ran if c.get("ok")]),
        "notRun": NOT_RUN,
        "packageFiles": package_files(),
        "evidenceRefs": evidence_refs(),
        "honesty": {
            "estimatedScoresUsed": False,
            "realDeviceEvidence": False,
            "browserSuiteRun": False,
            "note": "未测维度保持 null；真机证据为 0 条；本包不运行浏览器套件。",
        },
    }
    PKG.mkdir(parents=True, exist_ok=True)
    out = PKG / "package-index.json"
    out.write_text(json.dumps(idx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nwrote %s" % rel(out))
    print("checks: %d/%d ok" % (idx["checksOk"], idx["checksRan"]))
    for c in ran:
        if not c.get("ok"):
            print("  ✗ %-22s exit=%s  %s" % (c["id"], c.get("exit"), (c.get("tail") or [""])[-1][:90]))
    return 0


def _head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=20).stdout.strip() or None
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
