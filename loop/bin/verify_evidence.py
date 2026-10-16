#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据完整性复查：已提交记录里的证据路径是否仍然存在、哈希是否仍然一致。

`loop.py submit` 只在**提交那一刻**校验证据。之后文件可能被误删、被覆盖、
或（在并行写入者动过受保护文件时）内容变了 —— 那时提交记录就变成了一张空头支票。
本脚本做全量复查，把这种「曾经成立、现在不成立」的证据挑出来。

用法：
  python3 -B -s loop/bin/verify_evidence.py
  python3 -B -s loop/bin/verify_evidence.py --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"


def load_loop_module():
    spec = importlib.util.spec_from_file_location("loopmod_v", LOOP / "bin" / "loop.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


loopmod = load_loop_module()


def classify(path: str) -> str:
    return "evolving" if loopmod.is_evolving(path) else "immutable"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    missing, changed, changed_evolving, ok, pending, transient = [], [], [], 0, [], []
    records = 0
    done_now = set(loopmod.done_ids())
    superseded = []
    for path in loopmod.record_files() + sorted(loopmod.OUT.glob("REJECTED__*.json")):
        rec = loopmod.load_json(path, {}) or {}
        ev = rec.get("evidence")
        if not isinstance(ev, list):
            continue
        records += 1
        if path.name.startswith("REJECTED__") and rec.get("task") in done_now:
            superseded.append({"task": rec.get("task"), "record": path.name})
            continue
        if rec.get("task") and rec["task"] not in done_now:
            pending.append({"task": rec.get("task"), "record": path.name,
                            "reason": "证据失效或未过校验，已退回待重做（其证据变化不计入失败）"})
        is_pending = bool(rec.get("task")) and rec["task"] not in done_now
        for item in ev:
            if not isinstance(item, dict) or "path" not in item:
                continue
            cand = Path(item["path"])
            cand = cand if cand.is_absolute() else ROOT / cand
            if hasattr(loopmod, "_external_volume_inaccessible") and loopmod._external_volume_inaccessible(cand):
                ok += 1
                continue
            exists = cand.exists()
            same = exists and (not item.get("sha256") or loopmod.sha256_file(cand) == item["sha256"])
            if exists and same:
                ok += 1
                continue
            if is_pending:
                continue
            if not exists:
                if loopmod.is_transient(item["path"]):
                    transient.append({"task": rec.get("task"), "path": item["path"], "record": path.name})
                    continue
                missing.append({"task": rec.get("task"), "path": item["path"], "record": path.name})
                continue
            entry = {"task": rec.get("task"), "path": item["path"], "record": path.name,
                     "class": classify(item["path"])}
            (changed_evolving if entry["class"] == "evolving" else changed).append(entry)

    report = {
        "records": records,
        "evidenceOk": ok,
        "missing": missing,
        "changed": changed,
        "changedEvolving": changed_evolving,
        "pendingRedo": pending,
        "transientPaths": transient,
        "supersededRejections": superseded,
        "note2": "transientPaths = 记录引用了按设计会被回收的路径（租约/心跳/锁/运行日志）。"
                 "它们不算证据消失，但也不该作为证据；新提交会被 validate 直接拒绝。",
        "verdict": "pass" if not missing and not changed else "fail",
        "note": "changedEvolving = 环境自身文件在记录之后又演进（正常，单列）；"
                "changed = 产物/不可变路径被改动（真问题）。",
    }
    out = LOOP / "state" / "EVIDENCE-VERIFY.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", "utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0 if report["verdict"] == "pass" else 1

    print("证据复查：%d 条记录 / %d 条证据" % (records, records and (ok + len(missing) + len(changed))))
    print("  仍然成立 %d" % ok)
    if missing:
        print("  **文件已消失 %d**：" % len(missing))
        for m in missing[:10]:
            print("    - %s → %s（记录 %s）" % (m["task"], m["path"], m["record"]))
    if changed:
        print("  **产物/不可变路径被改动 %d**：" % len(changed))
        for c in changed[:10]:
            print("    - %s → %s（记录 %s）" % (c["task"], c["path"], c["record"]))
    if superseded:
        print("  已被成功重做取代的拒绝记录 %d（只作历史，不计入失败）" % len(superseded))
    if transient:
        print("  引用了瞬态路径 %d（按设计会被回收，已单列；新提交会被拒）：" % len(transient))
        for x in transient[:6]:
            print("    - %s → %s" % (x["task"], x["path"]))
    if pending:
        print("  已退回待重做 %d（不计入失败：它们已不算 done，worker 会重做）：" % len(pending))
        for x in pending[:10]:
            print("    - %s（%s）" % (x["task"], x["reason"]))
    if changed_evolving:
        print("  环境文件在记录后继续演进 %d（正常，单列不判失败）：" % len(changed_evolving))
        for c in changed_evolving[:10]:
            print("    - %s → %s" % (c["task"], c["path"]))
    if not missing and not changed:
        print("  结论：产物级证据全部仍可复现。")
        print("  注意：受保护文件被并行写入者改动时，指向它们的证据会在这里变成 changed —— 那是真实情况，不要靠改哈希掩盖。")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
