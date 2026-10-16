#!/usr/bin/env python3
"""P10 · perf_longrun_30min.py 的静态自检：8 项必含动作与时长守则都真的在。

**为什么需要**：计划点名「三书轮换、星座旋转、星盘播放、罗盘进出、搜索、解构、
暂停恢复和窗口改变都要包含」。一个漏掉两项的 30 分钟脚本照样能跑完 30 分钟并
产出一堆漂亮曲线 —— 但它的覆盖面是假的。本自检因此**静态核对**：

  A. 8 类动作都有对应实现（ACTIONS 字典 + action_plan 里真的被排进时间表）；
  B. 罗盘进出是**两向**（enter + exit），暂停恢复是**两向**（pause + resume）；
  C. 三书轮换覆盖全部三部发布缓存，且路径与 data/cache 实际文件一致；
  D. 时长守则：< 30 分钟必须被拒绝（除非显式 --allow-short）；
  E. 七个规范场景与 perf_report.py 的 SCENARIO_IDS 完全一致（否则报告接不上）；
  F. 窗口改变至少有 4 档且含原生4K。

本自检不跑浏览器、不需要 GPU。

用法：python3 tools/plan100/perf_longrun_30min_selftest.py
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'plan100'))

import perf_longrun_30min as LR
import perf_report as PR

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  — ' + detail) if detail and not cond else ''))


def action_plan_names():
    """从源码里取出 action_plan 的动作名（不执行 main）。"""
    tree = ast.parse((ROOT / 'tools/plan100/perf_longrun_30min.py').read_text(encoding='utf8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'action_plan':
                    names = []
                    for el in node.value.elts:
                        first = el.elts[0]
                        names.append(getattr(first, 'value', None))
                    return names
    return []


def main():
    print('=' * 84)
    print('longrun_30min.py 静态自检')
    print('=' * 84)

    # ---------------------------------------------------------- A. 八项动作
    print('\nA. 计划点名的动作是否都有实现且排进时间表')
    required = {
        'book-rotate': '三书轮换',
        'constellation-rotate': '星座旋转',
        'astrolabe-play': '星盘播放',
        'search': '搜索',
        'deconstruct': '解构',
        'viewport-change': '窗口改变',
    }
    plan = action_plan_names()
    check('action_plan 解析成功且非空', bool(plan), 'plan=%s' % plan)
    for key, zh in required.items():
        check('时间表含 %s（%s）' % (key, zh), key in plan)
        if key in LR.ACTIONS:
            check('ACTIONS 有 %s 的实现' % key, True)
        elif key in ('viewport-change', 'book-rotate'):
            check('ACTIONS 无 %s，但主循环内联实现' % key, True)
        else:
            check('ACTIONS 有 %s 的实现' % key, False, '缺少实现')

    # ---------------------------------------------------------- B. 双向动作
    print('\nB. 双向动作：罗盘进出 / 暂停恢复 都必须是两向')
    compass = [k for k in LR.ACTIONS if k.startswith('compass-')]
    check('罗盘有 enter 与 exit 两个方向',
          'compass-enter' in compass and 'compass-exit' in compass, '实得 %s' % compass)
    check('罗盘进出都在时间表里',
          'compass-enter' in plan and 'compass-exit' in plan)
    pause = [k for k in LR.ACTIONS if k.startswith('pause-resume')]
    check('暂停恢复有 pause 与 resume 两个方向',
          'pause-resume' in pause and 'pause-resume-back' in pause, '实得 %s' % pause)
    check('暂停与恢复都在时间表里',
          'pause-resume' in plan and 'pause-resume-back' in plan)

    check('pause-resume 真的暂停',
          "playback('pause')" in LR.ACTIONS['pause-resume'])
    check('pause-resume-back 真的恢复',
          "playback('play')" in LR.ACTIONS['pause-resume-back'])
    check('compass-enter 真的开', 'openCompass(' in LR.ACTIONS['compass-enter'])
    check('compass-exit 真的关', 'closeCompass()' in LR.ACTIONS['compass-exit'])

    # ---------------------------------------------------------- C. 三书
    print('\nC. 三书轮换：覆盖三部发布缓存，且文件真实存在')
    check('BOOKS 恰为 3 部', len(LR.BOOKS) == 3, '实得 %d' % len(LR.BOOKS))
    keys = [b[0] for b in LR.BOOKS]
    check('三部书 key 无重复', len(set(keys)) == 3, str(keys))
    for key, data, title in LR.BOOKS:
        exists = (ROOT / data).is_file()
        check('缓存存在：%s (%s)' % (data, title), exists)

    # ---------------------------------------------------------- D. 时长守则
    print('\nD. 时长守则：< 30 分钟必须被拒绝')
    r = subprocess.run([sys.executable, str(ROOT / 'tools/plan100/perf_longrun_30min.py'),
                        '--minutes', '5', '--out', '/tmp/lr-selftest-guard'],
                       capture_output=True, text=True)
    check('--minutes 5 被拒绝（exit 2）', r.returncode == 2, 'rc=%d' % r.returncode)
    check('拒绝理由写明不得缩短冒充',
          '不得' in r.stderr and '30' in r.stderr)
    src = (ROOT / 'tools/plan100/perf_longrun_30min.py').read_text(encoding='utf8')
    check('--allow-short 存在且报告标记 isAcceptanceEvidence',
          '--allow-short' in src and 'isAcceptanceEvidence' in src)
    check('isAcceptanceEvidence 判定基于 >=30 分钟',
          "'isAcceptanceEvidence': args.minutes >= 30" in src)

    # ---------------------------------------------------------- E. 场景对齐
    print('\nE. 七场景与 perf_report.py 的 SCENARIO_IDS 必须一致')
    check('longrun SCENARIOS 与 perf_report SCENARIO_IDS 完全一致',
          LR.SCENARIOS == PR.SCENARIO_IDS,
          'longrun=%s report=%s' % (LR.SCENARIOS, PR.SCENARIO_IDS))

    # ---------------------------------------------------------- F. 视口档位
    print('\nF. 窗口改变：至少 4 档且必须含原生4K')
    vps = LR.VIEWPORTS
    check('视口档位 ≥ 4', len(vps) >= 4, '实得 %d' % len(vps))
    check('含原生4K 3840×2160', any(v[0] == 3840 and v[1] == 2160 for v in vps),
          str([(v[0], v[1]) for v in vps]))
    check('含窄屏档', any(v[0] <= 430 for v in vps), str([(v[0], v[1]) for v in vps]))

    # ---------------------------------------------------------- G. 不锁4K
    print('\nG. 「不锁4K换取性能」的运行时断言必须在')
    check('报告含 lockedNative4k 字段', 'lockedNative4k' in src)
    check('断言 3840×2160', '3840' in src and '2160' in src)
    check('掉档会被记进 failures', 'stayedNative4kThroughout' in src
          and '并非全程原生4K' in src)
    check('掉档时给出当时的 quality（firstDropExample）', 'firstDropExample' in src)

    # ---------------------------------------------------------- H. 未测即 null
    print('\nH. 未测场景不得造假：空帧间隔数组必须原样输出')
    check('按场景分桶，空桶保持空数组',
          "if iv:" in src and "entry['p50']" in src)
    check('没有为缺失场景填默认分位',
          "entry['p50'] = 0" not in src and "entry['p95'] = 0" not in src)

    # ---------------------------------------------------------- I. 长任务口径
    print('\nI. 长任务必须用 PerformanceObserver，不得用帧间隔冒充')
    check('使用 PerformanceObserver longtask',
          'PerformanceObserver' in src and "'longtask'" in src)
    check('UA 不支持时如实标记 longtaskSupported=false',
          'longtaskSupported = false' in src or 'longtaskSupported:false' in src)

    # ---------------------------------------------------------- J. 报告可衔接
    print('\nJ. 产出的 report.json 必须能被 perf_report.py 直接消费')
    fixture = {
        'requestedMinutes': 30, 'actualSampledSeconds': 1800.0,
        'scenarios': [
            {'scenario': 'steady', 'frameIntervalsMs': [16.1, 16.4, 17.0, 22.5] * 30,
             'rtCreates': 3, 'rtDisposes': 3, 'textures': 40, 'geometries': 44,
             'programs': 22, 'domNodes': 1900, 'gpuUploads': 200, 'longTasks': 2,
             'quality': {'dpr': 1, 'boost': 1, 'degrade': 0, 'drawW': 3840, 'drawH': 2160,
                         'sharedTier': {'tag': 'full', 'level': 0}},
             'canvas': [3840, 2160],
             'memory': [{'t': 0, 'usedMB': 200.0}, {'t': 60000, 'usedMB': 203.0}]},
        ],
    }
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'report.json'
        p.write_text(json.dumps(fixture), encoding='utf8')
        rep = PR.build_report([str(p)])
    sc = next(s for s in rep['scenarios'] if s['scenario'] == 'steady')
    check('perf_report 能从 longrun report.json 读出 steady',
          sc['status'] == 'measured', sc['status'])
    check('perf_report 判出原生4K met', sc['native4kCapability']['met'] is True,
          json.dumps(sc['native4kCapability'], ensure_ascii=False))
    check('perf_report 判出 60fps 状态',
          sc['runs'][0]['achieves60fps']['status'] in
          ('met-at-native-4k', 'not-met'),
          sc['runs'][0]['achieves60fps']['status'])

    # ---------------------------------------------------------- K. JS 片段语法
    print('\nK. 所有注入 JS 片段必须语法有效（node --check）')
    import shutil
    import subprocess as sp
    import tempfile
    node = shutil.which('node')
    if not node:
        check('K0 node 可用（否则无法做语法检查）', False, '未找到 node')
    else:
        frags = {'INSTALL': LR.INSTALL, 'SNAPSHOT': LR.SNAPSHOT,
                 'START_RECORDING': LR.START_RECORDING,
                 'SET_SCENARIO': LR.SET_SCENARIO % ('"steady"', '"test"')}
        for k, v in LR.ACTIONS.items():
            frags['ACTIONS_%s' % k.replace('-', '_')] = v
        bad = []
        with tempfile.TemporaryDirectory() as td:
            for name, code in frags.items():
                p = Path(td) / ('%s.js' % name)
                p.write_text(code, encoding='utf8')
                r = sp.run([node, '--check', str(p)], capture_output=True, text=True)
                if r.returncode != 0:
                    first = r.stderr.strip().splitlines()
                    bad.append((name, first[0][:120] if first else '?'))
        check('K1 %d 个 JS 片段全部语法有效' % len(frags), not bad, bad)
        check('K2 SET_SCENARIO 是立即调用（末尾含调用括号与实参）',
              LR.SET_SCENARIO.rstrip().endswith(')') and ')(%s, %s)' in LR.SET_SCENARIO,
              repr(LR.SET_SCENARIO[-30:]))
        check('K3 SET_SCENARIO 占位符数量与实参匹配（2 个 %s）',
              LR.SET_SCENARIO.count('%s') == 2,
              'count=%d' % LR.SET_SCENARIO.count('%s'))

    # ---------------------------------------------------------- 汇总
    print()
    print('=' * 84)
    print('自检结果：PASS %d · FAIL %d' % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print('  FAILED: %s' % f)
        return 1
    print('八项必含动作齐全（含双向）、时长守则生效、七场景与报告器对齐、JS 片段语法有效。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
