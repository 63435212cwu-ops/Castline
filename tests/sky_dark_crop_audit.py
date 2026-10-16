#!/usr/bin/env python3
"""暗部审查裁块 + banding 阶梯分析（内部自审配套，观察型工具非门禁）。

从旋转审查 4K 帧里裁 1:1 原生像素暗部块（星云稀薄区 / 星盘外缘 / HUD 玻璃底 / plot 暗底），
每块输出：
  <name>.png        1:1 裁块（原样）
  <name>.gain.png   暗部增益版（围绕块内 p50 中值 ×6 拉伸，便于肉眼判 8bit 台阶）
  统计（stdout/--json）：块内行均值阶梯检测——沿梯度主轴把行/列均值量化到 8bit，
  找「常值平台长度 ≥24px 且相邻平台差 ≤2 LSB」的台阶段；并给出块内噪声 std（区分抖动噪声
  与真 banding：噪声 std ≥0.6 LSB 时台阶不可见，判阴性）。

用法：python3 tests/sky_dark_crop_audit.py --dir /tmp/castline-shots/rotation-review-2026-10-07 [--json]
"""
import argparse, json, os, sys

import numpy as np
from PIL import Image

CROPS = [
    ('dafeng-rot-overview-p2.png', 2850, 500, 800, 500, 'df-sparse'),
    ('xiyou-rot-overview-p6.png', 2750, 450, 800, 500, 'xy-sparse'),
    ('sanguo-rot-overview-p6.png', 2750, 500, 800, 500, 'sg-sparse'),
    ('dafeng-rot-plot.png', 600, 150, 900, 500, 'df-plot-cloud-edge'),
    ('sanguo-rot-plot.png', 2500, 900, 900, 550, 'sg-plot-violet'),
    ('dafeng-rot-overview-p6.png', 1150, 1550, 640, 420, 'df-disk-rim'),
    ('xiyou-rot-overview-p7.png', 1050, 1450, 640, 420, 'xy-disk-rim'),
    ('sanguo-rot-overview-p6.png', 1150, 1500, 640, 420, 'sg-disk-rim'),
    ('dafeng-rot-overview-p2.png', 8, 55, 470, 690, 'df-dock'),
    ('xiyou-rot-overview-p2.png', 8, 55, 470, 690, 'xy-dock'),
    ('sanguo-rot-overview-p2.png', 8, 55, 470, 690, 'sg-dock'),
    ('dafeng-rot-overview-p2.png', 1150, 2065, 1500, 85, 'df-legend'),
    ('dafeng-rot-plot.png', 1260, 2075, 1300, 70, 'df-player'),
    ('xiyou-rot-plot.png', 1260, 2075, 1300, 70, 'xy-player'),
    ('sanguo-rot-plot.png', 1260, 2075, 1300, 70, 'sg-player'),
    ('dafeng-rot-overview-p5.png', 2800, 150, 700, 450, 'df-cream-wash'),
    ('sanguo-rot-overview-p5.png', 2560, 320, 700, 450, 'sg-cream-wash'),
]

STEP_MIN_RUN = 24
STEP_MAX_DELTA = 2


def step_runs(axis_means):
    """对 1D 行/列均值序列找常值平台段（8bit 台阶候选）。返回 [(start,end,value), ...]"""
    q = np.round(axis_means).astype(int)
    runs = []
    i, n = 0, len(q)
    while i < n:
        j = i + 1
        while j < n and q[j] == q[i]:
            j += 1
        if j - i >= STEP_MIN_RUN:
            runs.append((i, j - 1, int(q[i])))
        i = j
    out = []
    prev = None
    for r in runs:
        if prev is None or abs(r[2] - prev) <= STEP_MAX_DELTA:
            out.append(r)
        prev = r[2]
    return out


def audit(img, label):
    a = np.asarray(img.convert('RGB'), dtype=np.float32)
    lum = a[..., 0] * .299 + a[..., 1] * .587 + a[..., 2] * .114
    col_means = lum.mean(axis=0)
    row_means = lum.mean(axis=1)
    axis, scan = ('x', col_means) if np.var(np.diff(col_means)) > np.var(np.diff(row_means)) or True else ('y', row_means)
    steps_x = step_runs(col_means)
    steps_y = step_runs(row_means)
    dark = lum < 40
    dark_frac = float(dark.sum()) / lum.size
    black_frac = float((lum < 4).sum()) / lum.size
    sub = lum[lum.shape[0] // 4:lum.shape[0] // 2, lum.shape[1] // 4:lum.shape[1] // 2]
    noise_std = float(np.std(np.diff(sub, axis=1))) / 2 ** .5
    med = float(np.median(lum))
    return {'label': label, 'median': round(med, 2),
            'dark(lum<40)frac': round(dark_frac, 3), 'black(lum<4)frac': round(black_frac, 3),
            'noiseStdLSB': round(noise_std, 3),
            'stepRunsX': steps_x, 'stepRunsY': steps_y,
            'bandingSuspect': bool(steps_x or steps_y) and noise_std < 0.7}


def gain_img(img):
    a = np.asarray(img.convert('RGB'), dtype=np.float32)
    lum = a.mean(axis=2)
    med = np.median(lum)
    lo = max(0.0, med - 26.0)
    g = np.clip((a - lo) * 6.0, 0, 255).astype(np.uint8)
    return Image.fromarray(g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    outdir = os.path.join(a.dir, 'dark-crops')
    os.makedirs(outdir, exist_ok=True)
    results = []
    for src, x, y, w, h, name in CROPS:
        path = os.path.join(a.dir, src)
        if not os.path.exists(path):
            print('MISSING %s' % path)
            continue
        img = Image.open(path).crop((x, y, x + w, y + h))
        img.save(os.path.join(outdir, name + '.png'))
        gain_img(img).save(os.path.join(outdir, name + '.gain.png'))
        r = audit(img, name)
        r['src'] = '%s @(%d,%d %dx%d)' % (src, x, y, w, h)
        results.append(r)
        print('%-20s med=%6.2f dark=%.3f black=%.3f noise=%.2f stepsX=%d stepsY=%d %s' %
              (name, r['median'], r['dark(lum<40)frac'], r['black(lum<4)frac'], r['noiseStdLSB'],
               len(r['stepRunsX']), len(r['stepRunsY']), 'BANDING?' if r['bandingSuspect'] else '—'))
    if a.json:
        j = os.path.join(outdir, 'dark-audit.json')
        with open(j, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
        print('DARK-AUDIT %s' % j)
    return 0


if __name__ == '__main__':
    sys.exit(main())
