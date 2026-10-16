#!/usr/bin/env python3
"""量测三书视觉差异：把「三部作品结构语法高度相似」变成可复算的数字。

审核原话（扣分依据）：
  「大奉、西游、三国的 overview 和 crystal 采用同一主要构图与晶体形体，只在颜色、
    成员密度和标签内容上变化。统一设计系统成立，但作品自身的叙事 DNA 还没有进入
    空间形态、材质和运动节奏。」

「叙事 DNA 有没有进入空间形态」原本是主观判断。本工具把它拆成三个**可测量**的轴：

  1. 结构相似度（shape similarity）
     先降采样、再转灰度、再做边缘/亮度分布，然后在**去掉颜色**的前提下比较。
     如果三书只在色相上不同，去色后应当高度相似（汉明距离小）。
     -> 用 dHash（差分哈希）+ 亮度直方图交叠来量。

  2. 色彩差异（color difference）
     保留颜色，比较色相直方图。这一轴**本来就应该**有差异（作品配色不同），
     用来证明「差异确实存在，但只在颜色上」。

  3. 构图差异（composition difference）
     比较亮度的空间分布（把图切成 N×M 网格，比较每格的平均亮度向量）。
     这一轴反映「主结构落在哪里、背景占比多少」。趋同的构图会得到很小的距离。

判读方法：
  - 结构相似度高 + 颜色差异大  =>  审核说的「只换颜色」（当前状态）
  - 结构相似度低 + 颜色差异大  =>  真正的叙事 DNA 进入了空间形态（目标状态）

依赖：只读 PNG 尺寸与像素。Python 标准库没有 PNG 解码器，因此这里用
macOS 自带的 `sips` 做降采样转 BMP/PNG，再用零依赖方式解析。
若 `sips` 不可用则明确报 blocked，不产出假数字。
"""
from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT = artifact_path() / "plan100" / "visual-metrics"

BOOKS = ["dafeng", "xiyou", "sanguo"]
DEFAULT_VIEWS = ["overview", "nebula", "crystal", "plot"]
VIEWS = list(DEFAULT_VIEWS)


# ---------------------------------------------------------------- PNG 解码
def read_png_rgb(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    """零依赖 PNG 解码（8-bit RGB/RGBA，非隔行）。返回 (w, h, pixels)。"""
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")

    pos = 8
    width = height = None
    bit_depth = color_type = None
    idat = bytearray()

    while pos < len(raw):
        (length,) = struct.unpack(">I", raw[pos : pos + 4])
        ctype = raw[pos + 4 : pos + 8]
        data = raw[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", data)
            if interlace:
                raise ValueError("interlaced PNG unsupported")
            if bit_depth != 8:
                raise ValueError(f"bit depth {bit_depth} unsupported")
        elif ctype == b"IDAT":
            idat += data
        elif ctype == b"IEND":
            break

    if width is None:
        raise ValueError("no IHDR")

    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError(f"color type {color_type} unsupported")

    decoded = zlib.decompress(bytes(idat))
    stride = width * channels
    out: list[tuple[int, int, int]] = []
    prev = bytearray(stride)

    p = 0
    for _ in range(height):
        ftype = decoded[p]
        p += 1
        line = bytearray(decoded[p : p + stride])
        p += stride
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            x = line[i]
            if ftype == 1:
                x = (x + a) & 0xFF
            elif ftype == 2:
                x = (x + b) & 0xFF
            elif ftype == 3:
                x = (x + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                x = (x + pr) & 0xFF
            line[i] = x
        for i in range(0, stride, channels):
            if channels >= 3:
                out.append((line[i], line[i + 1], line[i + 2]))
            else:
                g = line[i]
                out.append((g, g, g))
        prev = line

    return width, height, out


def downscale(path: Path, w: int, h: int, tmp: Path) -> Path:
    """用 macOS sips 降采样（保留 PNG 无压缩伪影）。"""
    dst = tmp / f"{path.stem}-{w}x{h}.png"
    subprocess.run(
        ["sips", "-z", str(h), str(w), str(path), "--out", str(dst)],
        check=True, capture_output=True,
    )
    return dst


# ---------------------------------------------------------------- 度量
def dhash(pixels: list[tuple[int, int, int]], w: int, h: int) -> int:
    """差分哈希（去色）：比较相邻像素亮度大小，得到结构指纹。"""
    gray = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels]
    bits = 0
    idx = 0
    for y in range(h):
        row = gray[y * w : (y + 1) * w]
        for x in range(w - 1):
            bits = (bits << 1) | (1 if row[x] < row[x + 1] else 0)
            idx += 1
    return bits


def hamming(a: int, b: int, nbits: int) -> int:
    return bin(a ^ b).count("1")


def luma_hist(pixels: list[tuple[int, int, int]], bins: int = 32) -> list[float]:
    h = [0] * bins
    for r, g, b in pixels:
        v = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        h[min(bins - 1, int(v * bins))] += 1
    n = max(1, len(pixels))
    return [c / n for c in h]


def hist_intersection(a: list[float], b: list[float]) -> float:
    return sum(min(x, y) for x, y in zip(a, b))


def hue_hist(pixels: list[tuple[int, int, int]], bins: int = 24) -> list[float]:
    h = [0] * bins
    used = 0
    for r, g, b in pixels:
        mx, mn = max(r, g, b), min(r, g, b)
        if mx == mn:
            continue
        d = mx - mn
        if mx == r:
            hue = 60 * (((g - b) / d) % 6)
        elif mx == g:
            hue = 60 * ((b - r) / d + 2)
        else:
            hue = 60 * ((r - g) / d + 4)
        h[min(bins - 1, int(hue / 360 * bins))] += 1
        used += 1
    return [c / used for c in h] if used else [0.0] * bins


def grid_luma(pixels: list[tuple[int, int, int]], w: int, h: int, gx: int = 8, gy: int = 6) -> list[float]:
    """把图切成 gx×gy 网格，取每格平均亮度 —— 反映主结构落在哪、背景占比多少。"""
    acc = [0.0] * (gx * gy)
    cnt = [0] * (gx * gy)
    for y in range(h):
        cy = min(gy - 1, y * gy // h)
        base = y * w
        for x in range(w):
            cx = min(gx - 1, x * gx // w)
            r, g, b = pixels[base + x]
            acc[cy * gx + cx] += 0.299 * r + 0.587 * g + 0.114 * b
            cnt[cy * gx + cx] += 1
    return [acc[i] / cnt[i] / 255.0 if cnt[i] else 0.0 for i in range(gx * gy)]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def distance(a: list[float], b: list[float]) -> float:
    """归一化 L1 距离。"""
    return sum(abs(x - y) for x, y in zip(a, b)) / max(1, len(a))


# ---------------------------------------------------------------- 主流程
def main() -> int:
    if not shutil.which("sips"):
        print("BLOCKED: sips not available; refusing to fabricate metrics", file=sys.stderr)
        return 2

    import argparse

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="含 <book>-<view>.png 的目录")
    ap.add_argument("--label", default=None, help="本次量测的标签（如 baseline / p06-candidate）")
    ap.add_argument("--size", type=int, default=256, help="结构分析用的正方形边长")
    ap.add_argument("--views", default=None,
                    help=f"逗号分隔的视角名（默认 {DEFAULT_VIEWS}）")
    args = ap.parse_args()

    src = Path(args.dir)
    if not src.is_absolute():
        src = ROOT / src
    if not src.is_dir():
        print(f"missing dir: {src}", file=sys.stderr)
        return 2

    global VIEWS
    if args.views:
        VIEWS = [v.strip() for v in args.views.split(",") if v.strip()]
    label = args.label or src.name
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="cl-visual-metrics-"))

    feats: dict[str, dict] = {}
    for book in BOOKS:
        for view in VIEWS:
            p = src / f"{book}-{view}.png"
            if not p.exists():
                continue
            small = downscale(p, args.size, args.size, tmp)
            w, h, px = read_png_rgb(small)
            feats[f"{book}-{view}"] = {
                "w": w, "h": h,
                "dhash": dhash(px, w, h),
                "luma": luma_hist(px),
                "hue": hue_hist(px),
                "grid": grid_luma(px, w, h),
                "nbits": (w - 1) * h,
            }

    if not feats:
        pairs = {}
        for p in sorted(src.glob("*-baseline.png")):
            name = p.name[: -len("-baseline.png")]
            cand = src / f"{name}-candidate.png"
            if cand.exists():
                pairs[name] = (p, cand)
        if not pairs:
            print(f"no <book>-<view>.png nor <name>-baseline/candidate.png found in {src}", file=sys.stderr)
            return 2
        for name, (bp, cp) in pairs.items():
            for tag, p in (("baseline", bp), ("candidate", cp)):
                small = downscale(p, args.size, args.size, tmp)
                w, h, px = read_png_rgb(small)
                feats[f"{name}:{tag}"] = {
                    "w": w, "h": h,
                    "dhash": dhash(px, w, h),
                    "luma": luma_hist(px),
                    "hue": hue_hist(px),
                    "grid": grid_luma(px, w, h),
                    "nbits": (w - 1) * h,
                }
        comparisons = []
        for name in pairs:
            a, b = feats[f"{name}:baseline"], feats[f"{name}:candidate"]
            comparisons.append({
                "view": name,
                "pair": [f"{name}:baseline", f"{name}:candidate"],
                "structureSimilarity_dhash": round(
                    1 - hamming(a["dhash"], b["dhash"], a["nbits"]) / a["nbits"], 4),
                "structureSimilarity_luma": round(hist_intersection(a["luma"], b["luma"]), 4),
                "compositionCosine": round(cosine(a["grid"], b["grid"]), 4),
                "compositionDistance": round(distance(a["grid"], b["grid"]), 4),
                "colorSimilarity_hue": round(hist_intersection(a["hue"], b["hue"]), 4),
                "noMeasurableDifference": (
                    a["dhash"] == b["dhash"] and a["luma"] == b["luma"]
                    and a["hue"] == b["hue"] and a["grid"] == b["grid"]
                ),
            })
        no_diff = [c["view"] for c in comparisons if c["noMeasurableDifference"]]
        summary = {
            "label": label,
            "mode": "pairwise-ab",
            "sourceDir": str(src.relative_to(ROOT)) if str(src).startswith(str(ROOT)) else str(src),
            "imagesMeasured": len(feats),
            "pairwiseComparisons": len(comparisons),
            "averages": {
                "structureSimilarity_dhash": round(
                    sum(c["structureSimilarity_dhash"] for c in comparisons) / len(comparisons), 4),
                "structureSimilarity_luma": round(
                    sum(c["structureSimilarity_luma"] for c in comparisons) / len(comparisons), 4),
                "compositionCosine": round(
                    sum(c["compositionCosine"] for c in comparisons) / len(comparisons), 4),
                "compositionDistance": round(
                    sum(c["compositionDistance"] for c in comparisons) / len(comparisons), 4),
                "colorSimilarity_hue": round(
                    sum(c["colorSimilarity_hue"] for c in comparisons) / len(comparisons), 4),
            },
            "pairsWithoutMeasurableDifference": no_diff,
            "hasMeasurableSignal": not no_diff,
            "interpretation": (
                "成对 A/B 模式。structureSimilarity 越低 = 候选相对基线的结构改变越大（这才是"
                "「叙事DNA进入空间形态」的证据）。pairsWithoutMeasurableDifference 非空 = 该对"
                "候选与基线无**可测**差异 —— 既不能证明改善，也不能证明无改善，必须由人工判读"
                "「视觉等价」还是「开关未生效」，不得直接当改善证据。"
            ),
            "comparisons": comparisons,
        }
        out = OUT / f"{label}.json"
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        a_ = summary["averages"]
        print(f"=== {label} · 成对 A/B · {len(comparisons)} 对 ===")
        for c in comparisons:
            flag = "  <== 无可测差异(需人工判读)" if c["noMeasurableDifference"] else ""
            print(f"  {c['view']:22s} struct_dHash={c['structureSimilarity_dhash']:.4f} "
                  f"compCos={c['compositionCosine']:.4f} hue={c['colorSimilarity_hue']:.4f}{flag}")
        print(f"  平均: struct_dHash={a_['structureSimilarity_dhash']} "
              f"compCos={a_['compositionCosine']} hue={a_['colorSimilarity_hue']}")
        if no_diff:
            print(f"  [NO-SIGNAL] {len(no_diff)} 对候选与基线无可测差异 —— 不得当改善证据；"
                  f"需人工判读是视觉等价还是开关未生效")
        print(f"-> {artifact_rel(out)}")
        shutil.rmtree(tmp, ignore_errors=True)
        return 0

    comparisons = []
    for view in VIEWS:
        keys = [f"{b}-{view}" for b in BOOKS if f"{b}-{view}" in feats]
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = feats[keys[i]], feats[keys[j]]
                comparisons.append({
                    "view": view,
                    "pair": [keys[i], keys[j]],
                    "structureSimilarity_dhash": round(
                        1 - hamming(a["dhash"], b["dhash"], a["nbits"]) / a["nbits"], 4),
                    "structureSimilarity_luma": round(hist_intersection(a["luma"], b["luma"]), 4),
                    "compositionCosine": round(cosine(a["grid"], b["grid"]), 4),
                    "compositionDistance": round(distance(a["grid"], b["grid"]), 4),
                    "colorSimilarity_hue": round(hist_intersection(a["hue"], b["hue"]), 4),
                })

    def avg(key: str) -> float:
        v = [c[key] for c in comparisons]
        return round(sum(v) / len(v), 4) if v else 0.0

    summary = {
        "label": label,
        "sourceDir": str(src.relative_to(ROOT)) if str(src).startswith(str(ROOT)) else str(src),
        "imagesMeasured": len(feats),
        "pairwiseComparisons": len(comparisons),
        "averages": {
            "structureSimilarity_dhash": avg("structureSimilarity_dhash"),
            "structureSimilarity_luma": avg("structureSimilarity_luma"),
            "compositionCosine": avg("compositionCosine"),
            "compositionDistance": avg("compositionDistance"),
            "colorSimilarity_hue": avg("colorSimilarity_hue"),
        },
        "interpretation": (
            "structureSimilarity_* 高 且 colorSimilarity_hue 低 => 只在换颜色（审核扣分状态）；"
            "structureSimilarity_* 低 => 叙事DNA进入了空间形态（目标状态）"
        ),
        "comparisons": comparisons,
    }
    out = OUT / f"{label}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    a = summary["averages"]
    print(f"=== {label} · {len(feats)} 图 · {len(comparisons)} 组跨书对比 ===")
    print(f"  结构相似度 dHash      : {a['structureSimilarity_dhash']}  (越高越像)")
    print(f"  结构相似度 亮度直方图 : {a['structureSimilarity_luma']}  (越高越像)")
    print(f"  构图余弦相似          : {a['compositionCosine']}  (越高越像)")
    print(f"  构图 L1 距离          : {a['compositionDistance']}  (越高差异越大)")
    print(f"  色相相似度            : {a['colorSimilarity_hue']}  (越低说明配色差异越大)")
    print(f"-> {artifact_rel(out)}")

    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
