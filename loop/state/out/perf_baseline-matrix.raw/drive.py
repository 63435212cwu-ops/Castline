#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按硬墙钟上限驱动三书实测：先跑完三书的短路径（首帧/可交互/稳态/转场/质量切换/返回），
再把剩余预算全部投给大奉的长时窗口（不混档位、不把短测当长测）。

用法：
  python3 loop/state/out/perf_baseline-matrix.raw/drive.py --budget-seconds 1200
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE / 'probe.py'
BOOKS = ['sanguo', 'xiyou', 'dafeng']          # 先小后大：保证三书都有短路径数据
LONG_BOOK = 'dafeng'                            # 63MB 的最慢作品，长时窗口投给它


def run(cmd, log):
    with log.open('a', encoding='utf-8') as fh:
        fh.write('\n$ ' + ' '.join(cmd) + '\n')
        fh.flush()
        return subprocess.call(cmd, cwd=str(HERE.parents[3]), stdout=fh, stderr=subprocess.STDOUT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--budget-seconds', type=float, default=1200)
    ap.add_argument('--steady-seconds', type=float, default=20)
    ap.add_argument('--reps', type=int, default=20)
    ap.add_argument('--long-seconds', type=float, default=120)
    ap.add_argument('--out', default=str(HERE))
    args = ap.parse_args()
    out = Path(args.out)
    deadline = time.time() + args.budget_seconds
    log = out / 'drive.log'
    env = dict(os.environ); env['CL_GPU'] = '1'
    summary = {'deadlineEpoch': deadline, 'startedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'phases': []}

    for book in BOOKS:
        if time.time() > deadline - 150:
            summary['phases'].append({'book': book, 'skipped': '剩余预算不足以跑完一条短路径'})
            break
        t0 = time.time()
        cmd = [sys.executable, '-B', '-s', str(PROBE), '--book', book, '--steady-seconds', str(args.steady_seconds),
               '--reps', str(args.reps), '--startup-timeout', '90', '--out', str(out)]
        rc = subprocess.call(cmd, cwd=str(HERE.parents[3]), env=env, stdout=log.open('a', encoding='utf-8'),
                             stderr=subprocess.STDOUT)
        summary['phases'].append({'book': book, 'kind': 'short-paths', 'rc': rc, 'seconds': round(time.time()-t0, 1)})
        print(json.dumps(summary['phases'][-1], ensure_ascii=False), flush=True)

    # 长时阶段：只在剩余预算内开新窗口，且每个窗口都单独记档
    remaining = deadline - time.time() - 40          # 留 40 s 收尾（写产物 + 提交）
    windows = int(remaining // (args.long_seconds + 15)) if remaining > args.long_seconds else 0
    if windows > 0:
        t0 = time.time()
        cmd = [sys.executable, '-B', '-s', str(PROBE), '--book', LONG_BOOK, '--steady-seconds', '15',
               '--reps', '5', '--long-windows', str(windows), '--long-seconds', str(args.long_seconds),
               '--deadline-epoch', str(deadline - 35), '--out', str(out)]
        rc = subprocess.call(cmd, cwd=str(HERE.parents[3]), env=env, stdout=log.open('a', encoding='utf-8'),
                             stderr=subprocess.STDOUT)
        summary['phases'].append({'book': LONG_BOOK, 'kind': 'long-windows', 'plannedWindows': windows,
                                  'windowSeconds': args.long_seconds, 'rc': rc, 'seconds': round(time.time()-t0, 1)})
        print(json.dumps(summary['phases'][-1], ensure_ascii=False), flush=True)
    else:
        summary['phases'].append({'kind': 'long-windows', 'skipped': '剩余预算放不下一个 %ss 窗口' % args.long_seconds})

    summary['finishedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    summary['wallSeconds'] = round(time.time() - (deadline - args.budget_seconds), 1)
    (out / 'drive-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps({'saved': str(out / 'drive-summary.json'), 'wallSeconds': summary['wallSeconds']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
