#!/usr/bin/env python3
"""P10 · GPU 阶段一键执行器：把整个 GPU 窗口用一条命令跑完。

**为什么需要**：GPU 是串行队列里最稀缺的资源（计划明令禁止并发，否则污染帧率证据）。
手工分步跑意味着「起 Chrome → 发现少了一个参数 → 关掉 → 再来一遍」，
每次往返都浪费一个独占窗口。本脚本把 P10 需要的全部 GPU 证据
按**一次 Chrome 生命周期**跑完并落到 `artifacts/plan100/perf/raw/`。

## 它跑什么（按顺序，全部串行）

  1. **原生4K 能力与帧率分场景**（`tests/scene_native4k_perf_browser.py`）
     稳态 / 镜头转场 / 质量切换 / 返回 —— 拿真实帧间隔数组。
  2. **30 分钟长时**（`tools/plan100/perf_longrun_30min.py`）
     八项交互全覆盖，产出七场景分桶帧间隔 + 资源曲线。
     `--minutes 30` 是**真实墙钟**；本脚本不提供缩短开关。
  3. **像素级结构对比**（`tests/sky_reduced_structure_browser.py`，P09 已建）
     五档结构保留的**像素**证据（契约层已另有 `perf_structure_preservation.py`）。

跑完自动调用 `perf_report.py` 汇总成 `perf-report.json/md`。

## 前置检查（缺一即拒绝启动，不浪费窗口）

  * `pgrep -fl 'Google Chrome.*headless'` 必须为 **0**；
  * `artifacts/plan100/GPU-LOCK` 的 RUNNING 行必须是本代理（或已 IDLE）；
  * 服务 `--base` 必须返回 200。

## 诚实守则

  * **不缩短 30 分钟**。`--minutes` 下限就是 30；想冒烟请直接跑子脚本并自己标注。
  * 任一步失败**不中断后续步骤**（GPU 窗口宝贵），但失败会全部汇总在末尾并体现为 exit 1。
  * 每步的 stdout/stderr 落盘，原始报告落盘 —— 计划要求「失败候选也保留」。

用法（GPU 空闲时）：
  python3 tools/plan100/perf_gpu_stage.py --base http://127.0.0.1:8765 \\
      --agent P10-agent --out /tmp/castline-shots/perf-gpu-stage
  # 只跑其中一步：
  python3 tools/plan100/perf_gpu_stage.py --only native4k
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
PY = sys.executable


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def headless_chrome_count():
    """BSD pgrep 没有 -c：必须用 `pgrep -fl ... | wc -l`。"""
    try:
        r = subprocess.run(['pgrep', '-fl', 'Google Chrome.*headless'],
                           capture_output=True, text=True)
        return len([l for l in r.stdout.splitlines() if l.strip()])
    except Exception:
        return -1


def lock_running_owner():
    p = artifact_path('plan100/GPU-LOCK')
    if not p.is_file():
        return None
    for line in p.read_text(encoding='utf8').splitlines():
        if line.startswith('RUNNING'):
            parts = line.split()
            return parts[1] if len(parts) > 1 else '?'
    return None


def service_ok(base):
    try:
        with urllib.request.urlopen(base + '/', timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def run_step(name, cmd, logdir, timeout=None):
    """跑一步，stdout/stderr 落盘。返回 (ok, seconds, logpath)。"""
    log = logdir / ('%s.log' % name)
    t0 = time.monotonic()
    print('─' * 78)
    print('▶ %s' % name)
    print('  $ %s' % ' '.join(cmd))
    try:
        with log.open('w', encoding='utf8') as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT,
                               cwd=str(ROOT), timeout=timeout)
        ok = r.returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
        with log.open('a', encoding='utf8') as f:
            f.write('\n[TIMEOUT after %ss]\n' % timeout)
    dt = time.monotonic() - t0
    print('  %s · %.1fs · %s' % ('OK' if ok else 'FAIL', dt, log))
    return ok, dt, str(log)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default='http://127.0.0.1:8765')
    ap.add_argument('--agent', default='P10-agent')
    ap.add_argument('--out', default='/tmp/castline-shots/perf-gpu-stage')
    ap.add_argument('--minutes', type=float, default=30.0)
    ap.add_argument('--only', default=None,
                    choices=['native4k', 'longrun', 'structure', 'report'])
    ap.add_argument('--skip-preflight', action='store_true')
    args = ap.parse_args()

    if args.minutes < 30 and (args.only in (None, 'longrun')):
        print('拒绝：--minutes %.1f < 30。长时脚本至少 30 分钟是计划硬要求，'
              '本执行器不提供缩短开关。' % args.minutes, file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    logs = out / 'logs'
    logs.mkdir(exist_ok=True)
    raw = artifact_path('plan100/perf/raw')
    raw.mkdir(parents=True, exist_ok=True)

    stage = {'tool': 'tools/plan100/perf_gpu_stage.py', 'startedAt': now(),
             'agent': args.agent, 'base': args.base, 'out': str(out),
             'requestedMinutes': args.minutes, 'steps': [], 'failures': []}

    # ---------------------------------------------------------- 前置检查
    if not args.skip_preflight:
        print('=' * 78)
        print('前置检查')
        print('=' * 78)
        chrome = headless_chrome_count()
        owner = lock_running_owner()
        svc = service_ok(args.base)
        print('  headless Chrome 进程数 : %d %s' % (chrome, '（空闲）' if chrome == 0 else '（占用！）'))
        print('  GPU-LOCK RUNNING       : %s' % (owner or '（无 / IDLE）'))
        print('  服务 %s : %s' % (args.base, 'OK' if svc else '不可达'))
        stage['preflight'] = {'chrome': chrome, 'lockRunning': owner, 'serviceOk': svc}
        blockers = []
        if chrome != 0:
            blockers.append('仍有 %d 个 headless Chrome；并发会污染帧率证据' % chrome)
        if owner not in (None, 'IDLE', args.agent):
            blockers.append('GPU-LOCK 的 RUNNING 是 %s，不是本代理 %s' % (owner, args.agent))
        if not svc:
            blockers.append('服务 %s 不可达（先起 python3 -s serve.py 8765）' % args.base)
        if blockers:
            print()
            for b in blockers:
                print('  ✗ %s' % b)
            print()
            print('拒绝启动：前置条件不满足。GPU 是串行资源，带病启动只会浪费窗口。')
            stage['blocked'] = blockers
            (out / 'stage.json').write_text(json.dumps(stage, ensure_ascii=False, indent=2) + '\n')
            return 3
        print('  → 全部满足，开始执行')

    # ---------------------------------------------------------- 步骤定义
    steps = []

    if args.only in (None, 'native4k'):
        steps.append((
            '01-native4k-perf',
            [PY, '-s', 'tests/scene_native4k_perf_browser.py', '--base', args.base,
             '--out', str(out / 'native4k')],
            None,
            lambda: _collect(out / 'native4k', raw / 'native4k-perf.json', 'native4k')))

    if args.only in (None, 'longrun'):
        steps.append((
            '02-longrun-30min',
            [PY, 'tools/plan100/perf_longrun_30min.py', '--base', args.base,
             '--out', str(out / 'longrun'), '--minutes', str(args.minutes)],
            int(args.minutes * 60) + 900,
            lambda: _collect(out / 'longrun', raw / 'longrun-30min.json', 'longrun')))

    if args.only in (None, 'structure'):
        if (ROOT / 'tests/sky_reduced_structure_browser.py').is_file():
            steps.append((
                '03-structure-pixels',
                [PY, '-s', 'tests/sky_reduced_structure_browser.py', '--base', args.base,
                 '--out', str(out / 'structure')],
                None,
                lambda: _collect(out / 'structure', raw / 'structure-pixels.json',
                                 'structure')))
        else:
            stage['steps'].append({'name': '03-structure-pixels', 'skipped': True,
                                   'reason': 'tests/sky_reduced_structure_browser.py 不存在'})

    # ---------------------------------------------------------- 执行
    for name, cmd, timeout, collect in steps:
        ok, secs, log = run_step(name, cmd, logs, timeout)
        entry = {'name': name, 'ok': ok, 'seconds': round(secs, 1), 'log': log,
                 'command': ' '.join(cmd)}
        try:
            entry['collected'] = collect()
        except Exception as exc:
            entry['collectError'] = str(exc)[:300]
        stage['steps'].append(entry)
        if not ok:
            stage['failures'].append('%s 失败（rc≠0），日志 %s' % (name, log))

    # ---------------------------------------------------------- 汇总报告
    if args.only in (None, 'report'):
        report_ok, secs, log = run_step(
            '04-perf-report',
            [PY, 'tools/plan100/perf_report.py'],
            logs, None)
        stage['steps'].append({'name': '04-perf-report', 'ok': report_ok,
                               'seconds': round(secs, 1), 'log': log,
                               'command': '%s tools/plan100/perf_report.py' % PY})
        if not report_ok:
            stage['failures'].append(
                'perf_report.py 退出非零 —— 注意：**这通常是诚实结果而非 bug**，'
                '最常见原因是 longrun-duration-honest（长时未满 30 分钟）或'
                '仍有场景 not-measured。请读 perf-report.md 的交叉检查章节。')

    stage['finishedAt'] = now()
    stage['ok'] = not stage['failures']
    (out / 'stage.json').write_text(json.dumps(stage, ensure_ascii=False, indent=2) + '\n')

    print()
    print('=' * 78)
    print('GPU 阶段完成 · %s' % ('ALL OK' if stage['ok'] else '有失败'))
    for s in stage['steps']:
        if s.get('skipped'):
            print('  SKIP %s — %s' % (s['name'], s['reason']))
        else:
            print('  %-4s %-22s %6.1fs  %s'
                  % ('OK' if s.get('ok') else 'FAIL', s['name'], s.get('seconds', 0),
                     s.get('collected') or s.get('log', '')))
    if stage['failures']:
        print()
        for f in stage['failures']:
            print('  ✗ %s' % f)
    print()
    print('  stage.json : %s' % (out / 'stage.json'))
    print('  原始数据   : %s' % raw)
    print('  汇总报告   : artifacts/plan100/perf/perf-report.{json,md}')
    return 0 if stage['ok'] else 1


def _collect(src_dir, dst, label):
    """把子脚本产出的 report.json 复制到 perf/raw/ 供 perf_report.py 消费。"""
    if not src_dir.is_dir():
        return None
    cands = sorted(src_dir.rglob('*.json'))
    if not cands:
        return None
    best = max(cands, key=lambda p: p.stat().st_size)
    data = json.loads(best.read_text(encoding='utf8'))
    if isinstance(data, dict):
        data.setdefault('source', '%s（%s）' % (label, best.name))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                item.setdefault('source', '%s（%s）' % (label, best.name))
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return '%s ← %s（%d bytes）' % (dst.name, artifact_rel(best), dst.stat().st_size)


if __name__ == '__main__':
    raise SystemExit(main())
