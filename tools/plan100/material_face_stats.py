#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P07 · 晶体宽面「体积层次」量化审计（零依赖，复用 visual_metrics 的 PNG 解码器）。

审核扣分证据原文：
  「晶体仍像**均匀透明几何**」
  「**晶体宽面缺少体积层次**」
  「crystal 的青色上体和紫色下体拥有**大面积均匀透色**」

「缺少体积层次」原本是主观判断。本工具把它拆成四个**可复算**的量：

  1. 局部方差（local variance, 11×11 滑窗）
     均匀透色的宽面内部亮度几乎不变 -> 局部方差极低。
     真正的体积层次在宽面上留下弦长 / 法线 / 吸收换来的明暗起伏 -> 方差升高。
     -> 报告 p10 / p50 / p90 与「低于阈值的面积占比 flatShare」。

  2. 梯度幅值（Sobel，log1p 压缩）
     平坦宽面的 |∇L| 接近 0；晶面转折与内部光学层次在中频段抬高梯度。
     -> 报告 p50 / p90 与低梯度面积占比。

  3. 方向性（gradient orientation entropy）
     均匀透色 + 线性渐变的梯度方向高度集中（低熵）；
     多面体法线变化 + 内部层次的梯度方向分散（高熵，归一化到 [0,1]，1 = 各向同性）。

  4. 宽面采样域（facet mask）
     用**色度 + 亮度下限**先选出「晶体本体」像素（背景是低色度暗星云，实测
     chroma p50 = 10~23，晶体宽面 chroma p50 = 48~75，两者不重叠），
     再腐蚀掉轮廓与棱线（它们不是宽面），只在剩下的**内部宽面**上统计 ——
     否则棱刃的高对比会把结论拉偏。这是为了防止「用棱线亮度冒充体积层次」的伪完成。
     `facetMask.share` 同时是**结构信息保留**的读数：掩码占比塌到 0 说明晶体主体消失。

计划明令禁止「用全局提高亮度掩盖结构问题」，因此本工具**同时**输出全图平均亮度
（meanLuma / p50 / p90），供改动前后做 ±2% 对比。

用法：
  python3 -s tools/plan100/material_face_stats.py \
      --dir artifacts/plan100/20261007/P00-W01/baseline/four-view \
      --pattern '*-crystal.png' \
      --out artifacts/plan100/material/face-variance.json \
      --label p00-baseline
  # 也可直接给单个文件：
  python3 -s tools/plan100/material_face_stats.py --file a.png --file b.png --out out.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "plan100"))

import visual_metrics as vm

# ---------------------------------------------------------------- 参数（冻结）
WIN = 11
FLAT_VAR = 12.0
LOW_GRAD = 1.6
CHROMA_MIN = 35.0
LUMA_MIN = 18.0
ERODE = 9
MIN_FACET_SHARE = 0.02


# ---------------------------------------------------------------- 基础算子
def _luma(px):
    return [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px]


def _chroma(px):
    """色度 max-min。晶体宽面与低色度暗星云背景靠这一轴分开，比 HSV 饱和度稳。"""
    return [float(max(r, g, b) - min(r, g, b)) for r, g, b in px]


def _integral(a, w, h):
    """积分图（w+1 × h+1），用于 O(1) 滑窗和 / 平方和。"""
    s = [0.0] * ((w + 1) * (h + 1))
    ss = [0.0] * ((w + 1) * (h + 1))
    for y in range(h):
        rowsum = 0.0
        rowsq = 0.0
        base = y * w
        ib = (y + 1) * (w + 1)
        ip = y * (w + 1)
        for x in range(w):
            v = a[base + x]
            rowsum += v
            rowsq += v * v
            s[ib + x + 1] = s[ip + x + 1] + rowsum
            ss[ib + x + 1] = ss[ip + x + 1] + rowsq
    return s, ss


def _box(ii, w, x0, y0, x1, y1):
    """积分图矩形和，[x0,x1) × [y0,y1)。"""
    stride = w + 1
    return ii[(y1) * stride + x1] - ii[(y0) * stride + x1] - ii[(y1) * stride + x0] + ii[(y0) * stride + x0]


def local_variance(L, w, h, win=WIN):
    """返回逐像素局部方差（仅中心区域，边缘像素不参与统计 -> None）。"""
    s, ss = _integral(L, w, h)
    r = win // 2
    n = float(win * win)
    out = [None] * (w * h)
    for y in range(r, h - r):
        y0, y1 = y - r, y + r + 1
        base = y * w
        for x in range(r, w - r):
            x0, x1 = x - r, x + r + 1
            tot = _box(s, w, x0, y0, x1, y1)
            sq = _box(ss, w, x0, y0, x1, y1)
            out[base + x] = max(0.0, sq / n - (tot / n) ** 2)
    return out


def gradient(L, w, h):
    """Sobel 梯度幅值（log1p 压缩）与方向。"""
    mag = [0.0] * (w * h)
    ang = [0.0] * (w * h)
    for y in range(1, h - 1):
        b0, b1, b2 = (y - 1) * w, y * w, (y + 1) * w
        for x in range(1, w - 1):
            tl, tc, tr = L[b0 + x - 1], L[b0 + x], L[b0 + x + 1]
            ml, mr = L[b1 + x - 1], L[b1 + x + 1]
            bl, bc, br = L[b2 + x - 1], L[b2 + x], L[b2 + x + 1]
            gx = (tr + 2 * mr + br) - (tl + 2 * ml + bl)
            gy = (bl + 2 * bc + br) - (tl + 2 * tc + tr)
            m = math.sqrt(gx * gx + gy * gy) / 8.0
            mag[b1 + x] = math.log1p(m)
            ang[b1 + x] = math.atan2(gy, gx)
    return mag, ang


def _percentiles(values, ps):
    if not values:
        return {str(p): None for p in ps}
    sv = sorted(values)
    out = {}
    for p in ps:
        idx = (len(sv) - 1) * p / 100.0
        lo, hi = math.floor(idx), math.ceil(idx)
        out[str(p)] = round(sv[lo] if lo == hi else sv[lo] + (sv[hi] - sv[lo]) * (idx - lo), 4)
    return out


def _facet_mask(L, C, w, h, erode=ERODE):
    """晶体内部宽面掩码：色度+亮度筛本体，再腐蚀掉轮廓与棱线。"""
    body = bytearray(w * h)
    for i in range(w * h):
        if C[i] >= CHROMA_MIN and L[i] >= LUMA_MIN:
            body[i] = 1
    tmp = bytearray(w * h)
    k = erode
    for y in range(h):
        base = y * w
        run = 0
        for x in range(w):
            run = run + 1 if body[base + x] else 0
            if run >= 2 * k + 1:
                tmp[base + x - k] = 1
    out = bytearray(w * h)
    for x in range(w):
        run = 0
        for y in range(h):
            run = run + 1 if tmp[y * w + x] else 0
            if run >= 2 * k + 1:
                out[(y - k) * w + x] = 1
    return out


def _orient_entropy(ang, mask, w, h, bins=18):
    """梯度方向直方图 -> 归一化熵（1 = 各向同性，0 = 单一方向）。"""
    hist = [0] * bins
    n = 0
    for i in range(w * h):
        if not mask[i]:
            continue
        a = ang[i] % math.pi
        hist[min(bins - 1, int(a / math.pi * bins))] += 1
        n += 1
    if n == 0:
        return None, 0
    ent = 0.0
    for c in hist:
        if c:
            p = c / n
            ent -= p * math.log(p)
    return round(ent / math.log(bins), 4), n


# ---------------------------------------------------------------- 主分析
def analyse(path: Path, label: str | None = None) -> dict:
    t0 = time.time()
    w, h, px = vm.read_png_rgb(path)
    L = _luma(px)
    C = _chroma(px)
    rec = {
        "file": str(path.relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path),
        "label": label or path.stem,
        "width": w, "height": h,
        "params": {"win": WIN, "flatVar": FLAT_VAR, "lowGrad": LOW_GRAD,
                   "chromaMin": CHROMA_MIN, "lumaMin": LUMA_MIN, "erode": ERODE},
    }

    # ---- 全图亮度（±2% 门禁的分子）
    n = w * h
    rec["wholeImage"] = {
        "meanLuma": round(sum(L) / n, 4),
        "lumaPercentiles": _percentiles(L[::7], [10, 50, 90]),
    }

    # ---- 宽面域
    mask = _facet_mask(L, C, w, h)
    frac = sum(mask) / n
    rec["facetMask"] = {"pixels": sum(mask), "share": round(frac, 5)}
    if frac < MIN_FACET_SHARE:
        rec["blocked"] = (f"crystal facet mask share {frac:.5f} < {MIN_FACET_SHARE}; "
                          "the crystal body is not identifiable, refusing to fabricate statistics")
        rec["elapsedS"] = round(time.time() - t0, 1)
        return rec

    var = local_variance(L, w, h)
    mag, ang = gradient(L, w, h)

    fv, fg = [], []
    for i in range(n):
        if mask[i]:
            if var[i] is not None:
                fv.append(var[i])
            fg.append(mag[i])

    flat = sum(1 for v in fv if v < FLAT_VAR)
    low = sum(1 for v in fg if v < LOW_GRAD)
    ent, en = _orient_entropy(ang, mask, w, h)

    rec["facetStats"] = {
        "localVariance": _percentiles(fv, [10, 25, 50, 75, 90, 99]),
        "flatShare": round(flat / max(1, len(fv)), 4),
        "gradientLog1p": _percentiles(fg, [10, 25, 50, 75, 90, 99]),
        "lowGradShare": round(low / max(1, len(fg)), 4),
        "orientEntropy": ent,
        "orientSamples": en,
    }
    med_var = (rec["facetStats"]["localVariance"]["50"] or 0.0)
    med_grad = (rec["facetStats"]["gradientLog1p"]["50"] or 0.0)
    rec["volumeLayerIndex"] = round(
        (1.0 - rec["facetStats"]["flatShare"]) * 0.45
        + min(1.0, med_grad / 2.5) * 0.35
        + (ent or 0.0) * 0.20, 5)
    rec["facetStats"]["medianVariance"] = med_var
    rec["elapsedS"] = round(time.time() - t0, 1)
    return rec


def _discover(d: Path, pattern: str) -> list[Path]:
    return sorted(p for p in d.glob(pattern) if p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser(description="P07 crystal wide-facet volume-layer audit")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", action="append", default=[], help="单个 PNG（可重复）")
    src.add_argument("--dir", help="目录")
    ap.add_argument("--pattern", default="*-crystal.png", help="--dir 下的 glob（默认 %(default)s）")
    ap.add_argument("--label", default=None, help="报告标签（默认取目录名）")
    ap.add_argument("--baseline", default=None,
                    help="基线 face-variance.json；给了就同时算 ±2%% 亮度门禁与层次增益")
    ap.add_argument("--out", default=None, help="输出 JSON 路径")
    args = ap.parse_args()

    if not vm.shutil.which("sips") and args.dir:
        pass

    if args.dir:
        d = Path(args.dir)
        if not d.is_dir():
            print(f"BLOCKED: not a directory: {d}", file=sys.stderr)
            return 2
        files = _discover(d, args.pattern)
        label = args.label or d.name
    else:
        files = [Path(f) for f in args.file]
        label = args.label or "adhoc"

    if not files:
        print(f"BLOCKED: no files matched under {args.dir or args.file}", file=sys.stderr)
        return 2

    records = []
    for f in files:
        if not f.is_file():
            print(f"BLOCKED: missing {f}", file=sys.stderr)
            return 2
        stem = f.stem
        book = stem.split("-")[0] if "-" in stem else stem
        try:
            rec = analyse(f, label=stem)
        except Exception as exc:
            rec = {"file": str(f), "label": stem, "blocked": f"decode failed: {exc}"}
        rec["book"] = book
        records.append(rec)
        print(f"[{stem}] mean={rec.get('wholeImage',{}).get('meanLuma')} "
              f"flatShare={rec.get('facetStats',{}).get('flatShare')} "
              f"volIdx={rec.get('volumeLayerIndex')} "
              f"{'BLOCKED: '+rec['blocked'] if rec.get('blocked') else ''}", flush=True)

    ok = [r for r in records if not r.get("blocked")]
    doc = {
        "tool": "tools/plan100/material_face_stats.py",
        "purpose": "量化「晶体宽面缺少体积层次」：局部方差 / 梯度 / 方向熵 / 宽面域占比",
        "label": label,
        "params": {"win": WIN, "flatVar": FLAT_VAR, "lowGrad": LOW_GRAD,
                   "chromaMin": CHROMA_MIN, "lumaMin": LUMA_MIN, "erode": ERODE},
        "records": records,
        "summary": {
            "files": len(records), "analysed": len(ok), "blocked": len(records) - len(ok),
            "meanLuma": round(sum(r["wholeImage"]["meanLuma"] for r in ok) / len(ok), 4) if ok else None,
            "meanFlatShare": round(sum(r["facetStats"]["flatShare"] for r in ok) / len(ok), 4) if ok else None,
            "meanVolumeLayerIndex": round(sum(r["volumeLayerIndex"] for r in ok) / len(ok), 5) if ok else None,
        },
    }

    # ---- 亮度约束（计划明令：「不得用全局提高亮度掩盖结构问题」）
    if args.baseline:
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        bmap = {r["label"]: r for r in base.get("records", []) if not r.get("blocked")}
        checks, worst = [], 0.0
        for r in ok:
            b = bmap.get(r["label"])
            if not b:
                continue
            bm = b["wholeImage"]["meanLuma"]
            cm = r["wholeImage"]["meanLuma"]
            delta = (cm - bm) / bm * 100.0 if bm else 0.0
            worst = max(worst, abs(delta))
            checks.append({
                "label": r["label"], "baselineMeanLuma": bm, "candidateMeanLuma": cm,
                "deltaPct": round(delta, 4), "within2Pct": abs(delta) <= 2.0,
                "flatShareBefore": b["facetStats"]["flatShare"],
                "flatShareAfter": r["facetStats"]["flatShare"],
                "volumeIndexBefore": b["volumeLayerIndex"],
                "volumeIndexAfter": r["volumeLayerIndex"],
                "structureGainWithoutBrightening":
                    r["volumeLayerIndex"] > b["volumeLayerIndex"] and delta <= 2.0,
            })
        doc["brightnessGuard"] = {
            "rule": "全图平均亮度变化必须在 ±2% 以内（禁止用全局提亮掩盖结构问题）",
            "baselineFile": args.baseline,
            "tolerancePct": 2.0,
            "worstDeltaPct": round(worst, 4),
            "gate": "pass" if checks and worst <= 2.0 else ("fail" if checks else "blocked"),
            "checks": checks,
        }
        if not checks:
            doc["brightnessGuard"]["gate"] = "blocked"
            doc["brightnessGuard"]["note"] = "no matching labels between baseline and candidate; refusing to pass"

    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(text)
    return 0 if len(ok) == len(records) else 1


if __name__ == "__main__":
    sys.exit(main())
