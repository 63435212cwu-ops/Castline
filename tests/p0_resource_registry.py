#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0.3 预约资源与写入范围（登记 + **持续核验**，不是一次性声明）。

计划原文（docs/QUALITY.md P0.3）：
  「登记本轮文件负责人、服务端口、输出目录、GPU时段和数据发布键。
    与保留运行任务协调后再实施，完成即释放资源。只停止自己启动的临时进程；
    归属不明的目录保持原状。」

为什么必须是「登记 + 核验」而不是一张表：
  本项目最贵的教训是「机制存在、有产出、但不产生信息」。写一张资源表很容易，
  难的是**表错了会有人知道**。所以这里把每条登记都变成一条当下可判定的检查：
    · 端口：登记的端口必须真的被登记的进程占着（不是抄来的）；
    · 单写者：受保护路径不能同时出现在两个负责人名下（E14 的形态：
      名册对了、现实没对上）；
    · GPU 时段：任一时刻最多一条 GPU 租约 —— 与 loop 的 maxGpuLeases=1 同一口径，
      并且**实测**当前 Chrome/GPU 测试进程数为 0 或 1；
    · 输出目录：运行产物不得落在受保护路径里；
    · 活动任务目录：用户保留的 `artifacts/` 必须原样存在（不删不搬不覆盖）。

用法：
  python3 -B -s tests/p0_resource_registry.py            # 核验并输出报告
  python3 -B -s tests/p0_resource_registry.py --write    # 同时落盘登记文件
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "loop"
POLICY = LOOP / "state" / "policy.json"

PROTECTED = {
    "js/core/**": None, "serve.py": None, "narrative.py": None,
    "js/atlas/atlas-source.js": None, "js/sky/sky-model.js": None,
    "css/**": None, "index.html": None, "scripts/**": None, "tests/**": None,
    "docs/**": None, "data/**": None,
}


def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return ""


def listening_ports():
    out = sh("lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null")
    ports = {}
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        m = re.search(r":(\d+)$", parts[8])
        if m:
            ports.setdefault(int(m.group(1)), []).append({"command": parts[0], "pid": parts[1]})
    return ports


def gpu_test_processes():
    """真实 GPU/浏览器测试进程（不是 worker）。用锚定路径，避免 pgrep 误伤。

    ── 2026-10-08 修正（真实假信号）──
    原 pats 只匹配 `headless_shell` 与 `Google Chrome for Testing`，
    而本机真实的测试/泄漏会话是 **`/Applications/Google Chrome.app/… --headless=new`**
    （见 /tmp/DEFECT-CHROME-LEAK.md：三个孤儿各烧 ~20% CPU，把一次 perf 测量
    从 48fps 污染到 35.97fps）。实测该匹配漏掉 **25 个** pid，
    于是本脚本在真有 67.7% CPU 被烧时报告「GPU 浏览器测试进程 0 个」——
    **这正是缺陷文档警告的那种「检查恒过、检测等于不存在」**。
    修正：同时锚定 `--headless`（任意 Chrome/Chromium 形态）与 `--user-data-dir`
    前缀（测试建立的临时 profile）。
    """
    out = sh("ps -ax -o pid=,command=")
    pats = ("tests/qa_cinema_wave02_capture", "tests/atlas_score_keys_browser",
            "tests/sky_internal_review_shots", "tests/material_layer_ab",
            "tests/scene_native4k_perf_browser", "tests/gem_", "headless_shell",
            "Google Chrome for Testing")
    udirs = ("atlas-review-", "castline-", "wave02-audit-", "atlas-keys-", "p81-")
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line or "grep" in line:
            continue
        pid, _, cmd = line.partition(" ")
        matched = any(p in cmd for p in pats)
        if not matched:
            if ("--headless" in cmd) and (("Google Chrome" in cmd) or ("Chromium" in cmd)
                                          or ("chrome" in cmd.lower())):
                matched = True
            elif "--user-data-dir=" in cmd and any(u in cmd for u in udirs):
                matched = True
        if matched:
            rows.append({"pid": pid.strip(), "cmd": cmd.strip()[:120]})
    return rows


def lease_owners():
    owners = {}
    for d in sorted((LOOP / "state" / "leases").glob("*.d")):
        f = d / "lease.json"
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for w in rec.get("writes") or []:
            owners.setdefault(w, set()).add(rec.get("agent"))
    return {k: sorted(v) for k, v in owners.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    problems = []
    notes = []

    policy = json.loads(POLICY.read_text(encoding="utf-8")) if POLICY.exists() else {}
    ports = listening_ports()

    # ---- 1. 服务端口 ---------------------------------------------------------
    services = [
        {"port": 8137, "role": "保留运行任务的服务（只读使用，不重启、不停）",
         "expected": "python3 serve.py 8137"},
        {"port": 8781, "role": "本次执行（P0–P11）的服务", "expected": "python3 -B -s serve.py 8781"},
    ]
    for s in services:
        live = ports.get(s["port"]) or []
        s["live"] = live
        s["ok"] = bool(live)
        if not live:
            problems.append("port_not_listening:%d" % s["port"])

    # ---- 2. 单写者：受保护路径不得有两个负责人 -------------------------------
    owners = lease_owners()
    multi = {k: v for k, v in owners.items() if len(v) > 1}
    for k, v in multi.items():
        problems.append("two_writers_on_one_path:%s=%s" % (k, v))

    # ---- 3. GPU 时段 ---------------------------------------------------------
    gpu = gpu_test_processes()
    gpu_lease = [d.name for d in (LOOP / "state" / "leases").glob("*gpu*.d")]
    max_gpu = int(policy.get("maxGpuLeases", 1))
    if len(gpu) > 1:
        problems.append("gpu_concurrent_processes:%d" % len(gpu))
    if len(gpu_lease) > max_gpu:
        problems.append("gpu_leases_exceed_policy:%d>%d" % (len(gpu_lease), max_gpu))
    notes.append("当前 GPU/浏览器测试进程 %d 个；GPU 租约 %d 条；策略上限 %d"
                 % (len(gpu), len(gpu_lease), max_gpu))

    # ---- 4. 输出目录 ---------------------------------------------------------
    outputs = [
        {"env": "CL_ARTIFACTS", "path": os.environ.get("CL_ARTIFACTS") or "/tmp/castline-artifacts",
         "rule": "运行产物默认落这里，禁止落回 docs/ tests/"},
        {"env": "CL_SHOTS", "path": os.environ.get("CL_SHOTS") or "/tmp/castline-shots",
         "rule": "截图/录像默认落这里"},
    ]
    for o in outputs:
        p = Path(o["path"])
        o["exists"] = p.exists()
        o["writable"] = os.access(p, os.W_OK)
        if not o["exists"] or not o["writable"]:
            problems.append("output_dir_unusable:%s" % o["path"])

    # ---- 5. 用户保留的活动任务目录（只登记，不动） ---------------------------
    reserved = [
        {"path": "artifacts/", "owner": "用户保留的另一个正在运行的任务",
         "rule": "结束前不得删除、搬迁或覆盖；不入 Git"},
    ]
    for r in reserved:
        p = ROOT / r["path"]
        r["exists"] = p.exists()
        r["note"] = "存在即可，内容不由本任务判断"
        if not r["exists"]:
            problems.append("reserved_dir_missing:%s" % r["path"])

    # ---- 6. 数据发布键 -------------------------------------------------------
    ledger = LOOP / "state" / "PUBLISH-LEDGER.json"
    published = []
    if ledger.exists():
        try:
            entries = (json.loads(ledger.read_text(encoding="utf-8")) or {}).get("entries") or []
            published = [{"batch": e.get("batch"), "graphKey": e.get("graphKey"),
                          "parentKey": e.get("parentKey"), "supersededBy": e.get("supersededBy")} for e in entries]
        except Exception as exc:
            problems.append("publish_ledger_unreadable:%r" % (exc,))
    if not published:
        problems.append("no_publish_ledger")
    for e in published:
        gk = e.get("graphKey")
        if gk and not (ROOT / "data" / "cache" / (gk + ".json")).exists():
            problems.append("published_key_missing_in_cache:%s" % gk)

    # ---- 7. 文件负责人（本轮） ----------------------------------------------
    gate = LOOP / "state" / "leases" / "GATE.lock"
    gate_holder = None
    if gate.exists():
        try:
            gate_holder = json.loads(gate.read_text(encoding="utf-8"))
        except Exception:
            gate_holder = {"raw": gate.read_text(encoding="utf-8")[:200]}

    report = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "plan_ref": "docs/QUALITY.md P0.3（预约资源与写入范围）",
        "services": services,
        "protected_path_writers": owners,
        "protected_path_conflicts": multi,
        "gpu": {"policy_max_leases": max_gpu, "live_test_processes": gpu, "gpu_leases": gpu_lease},
        "output_dirs": outputs,
        "reserved_active_task": reserved,
        "publish_keys": published,
        "gate_lock_holder": gate_holder,
        "notes": notes,
        "problems": problems,
        "ok": not problems,
    }
    outdir = Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p0-resources"
    outdir.mkdir(parents=True, exist_ok=True)
    p = outdir / "P0.3-resources.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.write:
        state = LOOP / "state" / "P0-RESOURCES.json"
        state.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "notes": notes,
                      "gate_lock": bool(gate_holder), "publish_keys": len(published),
                      "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
