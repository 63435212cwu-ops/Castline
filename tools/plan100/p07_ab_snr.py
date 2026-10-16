#!/usr/bin/env python3
"""P07 材质 A/B 判读：每层的「信号」是否高于「噪声底」。

关键问题：同一状态两次出图（baseline vs rollback）就有 57% 通道不同 ——
那么「关掉某层」造成的差异，有多少是**该层的贡献**、多少是**渲染噪声**？

判据：
  · 噪声底 = baseline↔rollback 的平均绝对差（同状态重渲）
  · 每层信号 = baseline↔<layer>-off 的平均绝对差
  · 信噪比 = 信号 / 噪声底；>3 视为该层**可分辨**
只读 PNG，不写文件。

    python3 tools/plan100/p07_ab_snr.py <ab-dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_png_pixels import read_png_rgb


def mean_abs_diff(a: Path, b: Path) -> float:
    wa, ha, pa = read_png_rgb(a)
    wb, hb, pb = read_png_rgb(b)
    if (wa, ha) != (wb, hb):
        return float("nan")
    n = len(pa)
    return sum(abs(pa[i] - pb[i]) for i in range(n)) / n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    args = ap.parse_args()
    d = Path(args.dir)
    base = d / "baseline-full.png"
    roll = d / "rollback-full.png"
    if not base.exists():
        print(f"缺 {base}")
        return 1

    noise = mean_abs_diff(base, roll) if roll.exists() else float("nan")
    print(f"噪声底（baseline↔rollback 同状态重渲）: {noise:.4f}")
    print()
    print(f"{'层':22s} {'平均绝对差':>10s} {'信噪比':>8s}  判定")
    rows = []
    for p in sorted(d.glob('*-off-full.png')):
        layer = p.name[:-len('-off-full.png')]
        sig = mean_abs_diff(base, p)
        snr = sig / noise if noise and noise > 0 else float('nan')
        verdict = ("✅ 可分辨" if snr >= 3 else
                   "⚠️ 弱（接近噪声）" if snr >= 1.5 else "❌ 淹没在噪声里")
        print(f"{layer:22s} {sig:10.4f} {snr:8.2f}  {verdict}")
        rows.append({"layer": layer, "signal": round(sig, 5),
                     "snr": round(snr, 3), "verdict": verdict})
    if rows:
        ok = sum(1 for r in rows if r["snr"] >= 3)
        print(f"\n可分辨 {ok}/{len(rows)} 层")
        print("\n注：本判据只说明「该层可被像素区分」，**不代表该层视觉正确**。")
    out = d / "snr.json"
    out.write_text(json.dumps({"noiseFloor": round(noise, 5), "layers": rows},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
