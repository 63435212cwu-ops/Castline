#!/usr/bin/env python3
"""比较两张 PNG 的实际像素差异（P07 A/B 回滚一致性判定）。

背景：P07 的 A/B report 给出 `rollbackIdenticalPng=False`，但
`baselineFrame == rollbackFrame`（相机/相位/裁剪/边界全同）。
需要区分两种可能：
  (a) 渲染**真不确定**（同状态两次出图不同）→ 严重，A/B 的前提不成立
  (b) 仅 PNG 编码字节不同、像素几乎相同 → 可接受，判据过严
本脚本用**独立解码**（zlib + 逐行 unfilter，零第三方依赖）量算：
  · 逐像素最大/平均差、不同像素占比
  · 分位差（p50/p95/p99/max）
只读，不写任何文件。

    python3 tools/plan100/compare_png_pixels.py <a.png> <b.png> [--tolerance 2]
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path


def read_png_rgb(path: Path):
    """极简 PNG 解码：支持 8-bit RGB/RGBA、非隔行。返回 (w, h, bytearray RGB)。"""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path.name}: 不是 PNG")
    pos, idat, w = 8, bytearray(), None
    h = bitdepth = colortype = None
    while pos < len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bitdepth, colortype, comp, filt, inter = struct.unpack(">IIBBBBB", chunk)
            if inter:
                raise ValueError("不支持隔行 PNG")
            if bitdepth != 8:
                raise ValueError(f"只支持 8-bit，实为 {bitdepth}")
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
        pos += 12 + ln
    raw = zlib.decompress(bytes(idat))
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[colortype]
    stride = w * ch
    out = bytearray(w * h * 3)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        o = y * w * 3
        for x in range(w):
            s = x * ch
            out[o + x * 3] = line[s]
            out[o + x * 3 + 1] = line[s + 1] if ch >= 3 else line[s]
            out[o + x * 3 + 2] = line[s + 2] if ch >= 3 else line[s]
        prev = line
    return w, h, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--tolerance", type=int, default=2,
                    help="逐通道差值 <= 该值视为相同像素（默认 2）")
    args = ap.parse_args()
    A, B = Path(args.a), Path(args.b)

    wa, ha, pa = read_png_rgb(A)
    wb, hb, pb = read_png_rgb(B)
    print(f"A {A.name}: {wa}x{ha}")
    print(f"B {B.name}: {wb}x{hb}")
    if (wa, ha) != (wb, hb):
        print("尺寸不同 —— 无法逐像素比较")
        return 2
    if len(pa) != len(pb):
        print("像素缓冲长度不同")
        return 2

    n = len(pa)
    diffs = []
    over = 0
    for i in range(n):
        d = abs(pa[i] - pb[i])
        if d:
            diffs.append(d)
            if d > args.tolerance:
                over += 1
    diffs.sort()
    frac_any = len(diffs) / n
    frac_over = over / n
    def q(p):
        return diffs[min(len(diffs) - 1, int(len(diffs) * p))] if diffs else 0
    print(f"\n通道总数        : {n}")
    print(f"有差异的通道    : {len(diffs)} ({frac_any*100:.4f}%)")
    print(f"超过容差 {args.tolerance} 的通道: {over} ({frac_over*100:.4f}%)")
    print(f"差值分位 p50={q(.5)} p95={q(.95)} p99={q(.99)} max={diffs[-1] if diffs else 0}")
    print(f"平均绝对差      : {sum(diffs)/n:.6f}")
    verdict = "像素级相同（仅编码字节不同）" if frac_over == 0 else \
              ("几乎相同（差异 < 0.1% 通道）" if frac_over < 0.001 else "存在实质像素差异")
    print(f"\n结论: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
