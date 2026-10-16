#!/usr/bin/env python3
"""读取 P07 A/B report，只输出结论（不要 print 整个 report、不要打印图片数组）。

用法：
    python3 tools/plan100/p07_ab_summary.py [--report <path>]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
DEFAULT = artifact_path() / "plan100" / "material" / "ab-gpu" / "report.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(DEFAULT))
    args = ap.parse_args()

    p = Path(args.report)
    if not p.exists():
        print(f"缺报告：{p}")
        return 1
    d = json.loads(p.read_text(encoding="utf-8"))

    def brief(v, n=110):
        """任何值都压成一行短摘要 —— 大数组只报条数（本项目已因此刷屏 5 次）。"""
        if isinstance(v, list):
            return f"[{len(v)} 条]"
        if isinstance(v, dict):
            return "{" + ", ".join(f"{k}={brief(x, 30)}" for k, x in list(v.items())[:6]) + "}"
        s2 = str(v)
        return s2 if len(s2) <= n else s2[:n] + "…"

    print("=== 顶层结论 ===")
    for k, v in d.items():
        if k in ("pairs", "samples", "actions"):
            continue
        print(f"  {k} = {brief(v)}")

    pairs = d.get("pairs")
    if isinstance(pairs, list):
        print(f"\n=== 逐层（{len(pairs)} 对）===")
        for L in pairs:
            name = L.get("layer") or L.get("name")
            flags = " ".join(f"{k}={'Y' if L[k] else 'N'}"
                             for k in ("isolated", "switchTookEffect", "sameAnimationPhase", "sameCamera")
                             if k in L)
            print(f"  {str(name):14s} {flags}  ring={'Y' if L.get('ring') else 'N'}")

    print("\n=== 固定量（单变量性的前提）===")
    fix = d.get("fixed") or d.get("freeze") or {}
    for k, v in fix.items():
        s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
        print(f"  {k} = {s[:90]}")

    print("\n=== 逐层 ===")
    layers = d.get("layers") or d.get("results") or []
    if isinstance(layers, dict):
        layers = [dict(name=k, **(v if isinstance(v, dict) else {})) for k, v in layers.items()]
    for L in layers:
        name = L.get("layer") or L.get("name")
        flags = []
        for k in ("isolated", "switchTookEffect", "samePhase", "sameCam"):
            if k in L:
                flags.append(f"{k}={'Y' if L[k] else 'N'}")
        metric = None
        for k in ("changedShare", "diffShare", "meanAbsDiff", "pixelDiff", "changed"):
            if k in L:
                metric = f"{k}={L[k]}"
                break
        print(f"  {str(name):14s} {' '.join(flags)}" + (f"  {metric}" if metric else ""))

    print("\n=== rollback ===")
    rb = d.get("rollback") or {}
    if isinstance(rb, dict):
        for k, v in rb.items():
            s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
            print(f"  {k} = {s[:120]}")
    else:
        print(f"  {json.dumps(rb, ensure_ascii=False)[:200]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
