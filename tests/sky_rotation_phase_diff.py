#!/usr/bin/env python3
"""旋转序列相邻相位差分直方图（tests/sky_rotation_review_shots.py 的配套分析，观察型工具非门禁）。

对每个 <别名>-{rot-overview|rot-nebula}-p{0..N-1}.png 序列：
  1. 逐像素 |差|（RGB 各通道取 max）直方图：p50/p95/p99/max、>16 与 >64 的像素占比；
  2. 突变定位：8×4 网格 tiles 的 mean|diff|，标出 top-3 突变块（找 LOD snap / popping 的空间源）；
  3. 全局占比对比：相邻相位 diff>64 占比若出现数量级跳变，标为 SUSPECT（构图崩坏/群体出画候选）。

注意：相位间差分天然含动画噪声（星云漂移、星点闪烁、boost 后处理抖动），
本脚本只负责把统计异常帧对和突变区域指出来，是否真缺陷由人工看图判定。

用法：python3 tests/sky_rotation_phase_diff.py --dir /tmp/castline-shots/rotation-review-2026-10-07 [--json]
"""
import argparse, json, os, re, sys

import numpy as np
from PIL import Image


def seq_files(d, alias, tag, phases):
    return [os.path.join(d, '%s-%s-p%d.png' % (alias, tag, i)) for i in range(phases)]


def diff_stats(pa, pb, gtiles=8, vtiles=4):
    a = np.asarray(Image.open(pa).convert('RGB'), dtype=np.int16)
    b = np.asarray(Image.open(pb).convert('RGB'), dtype=np.int16)
    d = np.abs(a - b).max(axis=2)
    flat = d.ravel()
    hist, _ = np.histogram(flat, bins=np.arange(0, 258))
    frac = lambda t: float((flat > t).sum()) / flat.size
    tiles = []
    h, w = d.shape
    for gy in range(vtiles):
        for gx in range(gtiles):
            t = d[gy * h // vtiles:(gy + 1) * h // vtiles, gx * w // gtiles:(gx + 1) * w // gtiles]
            tiles.append({'tile': [gx, gy], 'mean': round(float(t.mean()), 3),
                          'hi64': round(float((t > 64).sum()) / t.size, 5)})
    tiles.sort(key=lambda t: -t['mean'])
    return {'p50': int(np.percentile(flat, 50)),
            'p95': int(np.percentile(flat, 95)),
            'p99': int(np.percentile(flat, 99)),
            'max': int(flat.max()),
            'frac>16': round(frac(16), 4),
            'frac>64': round(frac(64), 5),
            'hist_nonzero_bins': int((hist > 0).sum()),
            'topTiles': tiles[:3]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--books', default='dafeng,xiyou,sanguo')
    ap.add_argument('--phases', type=int, default=8)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    out = {}
    for alias in a.books.split(','):
        for tag in ('rot-overview', 'rot-nebula'):
            files = seq_files(a.dir, alias, tag, a.phases)
            missing = [f for f in files if not os.path.exists(f)]
            if missing:
                out['%s/%s' % (alias, tag)] = {'error': 'missing %s' % missing[0]}
                continue
            pairs = []
            worst_ratio, worst_pair = 0.0, None
            for i in range(len(files) - 1):
                s = diff_stats(files[i], files[i + 1])
                s['pair'] = 'p%d→p%d' % (i, i + 1)
                pairs.append(s)
                r = (s['frac>64'] + 1e-6)
                if r > worst_ratio:
                    worst_ratio, worst_pair = r, s['pair']
            baseline = float(np.median([p['frac>64'] for p in pairs])) + 1e-6
            suspects = [p['pair'] for p in pairs if p['frac>64'] > max(4 * baseline, 0.01)]
            out['%s/%s' % (alias, tag)] = {'pairs': pairs, 'baseline_frac>64': round(baseline, 6),
                                           'suspects': suspects}
            print('%-9s %-12s baseline frac>64=%.5f  suspects=%s' %
                  (alias, tag, baseline, suspects or '—'), flush=True)
            for p in pairs:
                print('  %s  p50=%3d p95=%3d p99=%3d max=%3d  >16=%.4f  >64=%.5f  topTiles=%s' %
                      (p['pair'], p['p50'], p['p95'], p['p99'], p['max'], p['frac>16'],
                       p['frac>64'], [(t['tile'], t['mean'], t['hi64']) for t in p['topTiles']]), flush=True)
    if a.json:
        jpath = os.path.join(a.dir, 'phase-diff.json')
        with open(jpath, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('PHASE-DIFF written %s' % jpath)
    return 0


if __name__ == '__main__':
    sys.exit(main())
