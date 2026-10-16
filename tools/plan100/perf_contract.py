#!/usr/bin/env python3
"""P10 · 性能与结构保留的离线契约（可进 accept.sh，不需要 GPU）。

**这个文件存在的理由**：P10 的核心交付物是几个 Python 工具
（`perf_report.py` / `perf_resource_audit.py` / `perf_structure_preservation.py`）。
如果它们只在「有人手动跑一次」时被验证，那么任何一次后续改动都可能悄悄
破坏「不得用降档帧率声称原生4K达标」这条硬规则，而没人发现。
本契约把 P10 的**全部 CPU 可判断言**固化成一个离线测试。

覆盖的断言（逐条对应计划原文）：

  A. 双字段分离（E 节「原生4K能力和达到60fps是两个字段」）
     —— 报告器必须为七个场景各输出两个独立字段，且不得合成单一分数。
  B. 降档不得冒充原生4K（E 节「不得用自适应降档后的帧率声称原生4K达标」）
     —— 用违规夹具证明会被标 achieved-at-reduced-tier / below-native-4k；
        用篡改夹доказать交叉检查会 FAIL。
  C. 未测即 null（BRIEFING §4.4「未测必须保持 null，禁止用估算分填充」）
  D. 长时 ≥30 分钟（E 节「长时脚本至少30分钟」）
     —— 报告器必须把 <1800s 判 FAIL；长时脚本必须硬拒 <30 分钟。
  E. 同尺寸RT不重复分配（每阶段验收断言）
     —— 自有 RT 分配点不得有 unresolved。
  F. dispose 配对（同上）
  G. 结构保留 × 5 档（硬性原则 4）
     —— 30/30 通过，且负向自检证明非空转。
  H. 八项必含动作（E 节长时脚本要求）

**不覆盖**（诚实标注）：任何需要 GPU 的像素/帧率实测。那些由
`tools/plan100/perf_longrun_30min.py`（30 分钟）与
`tests/scene_native4k_perf_browser.py` 在串行 GPU 阶段产出。

用法：python3 tools/plan100/perf_contract.py
      python3 tools/plan100/perf_contract.py --json <out>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
sys.path.insert(0, str(ROOT / 'tools' / 'plan100'))

RESULTS = []


def check(cid, name, cond, detail=''):
    RESULTS.append({'id': cid, 'name': name, 'pass': bool(cond), 'detail': detail})
    print('  [%s] %-6s %s%s' % ('PASS' if cond else 'FAIL', cid, name,
                                ('  — ' + str(detail)[:160]) if detail and not cond else ''))
    return bool(cond)


def run_tool(rel, *args):
    r = subprocess.run([sys.executable, str(ROOT / rel)] + list(args),
                       capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode, r.stdout, r.stderr


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json', default=str(artifact_path('plan100/perf/perf-contract.json')))
    ap.add_argument('--stdout', action='store_true')
    args = ap.parse_args()

    is_repo_test = str(ROOT / 'tools/plan100/perf_contract.py') == str(Path(__file__).resolve())

    print('=' * 84)
    print('P10 离线契约：性能报告框架 + 结构保留')
    print('=' * 84)

    import perf_report as PR
    import perf_longrun_30min as LR

    # ------------------------------------------------------------ A. 双字段
    print('\nA. 双字段分离（E 节）')
    rep = PR.build_report([])
    check('A1', '七场景齐全', len(rep['scenarios']) == 7, len(rep['scenarios']))
    check('A2', '每个场景都有 native4kCapability 与 achieves60fps',
          all('native4kCapability' in s and 'achieves60fps' in s for s in rep['scenarios']))
    check('A3', 'two-separate-fields 交叉检查通过',
          not [c for c in rep['crossChecks']
               if c['id'] == 'two-separate-fields' and not c['pass']])
    check('A4', 'verdict 不做综合性能分',
          'separation' in rep['verdict'] and 'overall' not in json.dumps(rep['verdict']))

    # ------------------------------------------------------------ B. 降档不冒充
    print('\nB. 降档不得冒充原生4K（E 节，审核扣分点）')
    q_ok = {'dpr': 1, 'boost': 1, 'degrade': 0, 'drawW': 3840, 'drawH': 2160,
            'sharedTier': {'tag': 'full', 'level': 0}}
    q_dg = {'dpr': 0.66, 'boost': 0, 'degrade': 2, 'drawW': 2534, 'drawH': 1426,
            'sharedTier': {'tag': 'low', 'level': 2}}

    def mk(scenario, quality, fps=61.0, **over):
        iv = [(1000.0 / fps) * (1.9 if i % 20 == 19 else 0.96) for i in range(240)]
        r = {'scenario': scenario, 'quality': quality, 'frameIntervalsMs': iv}
        r.update(over)
        return r

    import tempfile
    def build(items):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'f.json'
            p.write_text(json.dumps(items, ensure_ascii=False), encoding='utf8')
            return PR.build_report([str(p)])

    rep_dg = build([mk('steady', q_dg)])
    sc = next(s for s in rep_dg['scenarios'] if s['scenario'] == 'steady')
    st = sc['runs'][0]['achieves60fps']['status']
    check('B1', '降档记录不判 met-at-native-4k', st != 'met-at-native-4k', st)
    check('B2', '降档记录 native4kCapability.met 为 False',
          sc['native4kCapability']['met'] is False, sc['native4kCapability']['status'])
    check('B3', '场景级 atNative4k 为 False', sc['achieves60fps'].get('atNative4k') is False)
    check('B4', 'no-downscaled-fps 交叉检查在合规用法下不误报',
          not [c for c in rep_dg['crossChecks']
               if c['id'] == 'no-downscaled-fps-as-native-4k' and not c['pass']])
    fake = {'scenarios': [{'scenario': 'steady', 'status': 'measured', 'metrics': {},
                           'native4kCapability': {'status': 'met', 'met': True},
                           'achieves60fps': {'status': 'met-at-native-4k', 'met': True,
                                             'atNative4k': True},
                           'runs': [{'origin': 'forged', 'degraded': True,
                                     'degradeReasons': ['degrade=2'],
                                     'native4kCapability': {'met': True},
                                     'achieves60fps': {'met': True,
                                                       'status': 'met-at-native-4k',
                                                       'atNativeCanvas': False,
                                                       'degraded': True}}]}]}
    c = next(x for x in PR.cross_checks(fake['scenarios'], [])
             if x['id'] == 'no-downscaled-fps-as-native-4k')
    check('B5', '篡改夹具（降档标成原生4K达标）会被检出', c['pass'] is False)

    rep_54 = build([mk('longrun', q_ok, fps=54.5, actualSampledSeconds=1801.0)])
    sc54 = next(s for s in rep_54['scenarios'] if s['scenario'] == 'longrun')
    check('B6', '4K@54.5fps：原生4K能力 met', sc54['native4kCapability']['met'] is True)
    check('B7', '4K@54.5fps：60fps not-met', sc54['runs'][0]['achieves60fps']['status'] == 'not-met',
          sc54['runs'][0]['achieves60fps']['status'])

    rep_shot = build([{'scenario': 'first-entry', 'quality': q_ok, 'frameIntervalsMs': []}])
    scs = next(s for s in rep_shot['scenarios'] if s['scenario'] == 'first-entry')
    check('B8', '无帧率证据时不得签收原生4K能力',
          scs['native4kCapability']['met'] is False,
          scs['runs'][0]['native4kCapability']['status'])

    # ------------------------------------------------------------ C. 未测即 null
    print('\nC. 未测即 null（BRIEFING §4.4）')
    nm = [s for s in rep['scenarios'] if s['status'] == 'not-measured']
    check('C1', '无输入时六场景 not-measured', len(nm) >= 6, len(nm))
    check('C2', 'not-measured 场景所有指标为 null',
          all(v is None for s in nm for v in s['metrics'].values()))
    check('C3', 'unmeasured-stays-null 交叉检查通过',
          not [c for c in rep['crossChecks']
               if c['id'] == 'unmeasured-stays-null' and not c['pass']])

    # ------------------------------------------------------------ D. 长时 ≥30min
    print('\nD. 长时至少 30 分钟（E 节）')
    c = next(x for x in rep_54['crossChecks'] if x['id'] == 'longrun-duration-honest')
    check('D1', '1801s 判 PASS', c['pass'] is True, json.dumps(c, ensure_ascii=False)[:120])
    rep_6 = build([mk('longrun', q_ok, actualSampledSeconds=360.0)])
    c6 = next(x for x in rep_6['crossChecks'] if x['id'] == 'longrun-duration-honest')
    check('D2', '360s 判 FAIL', c6['pass'] is False)
    rc, so, se = run_tool('tools/plan100/perf_longrun_30min.py', '--minutes', '5',
                          '--out', '/tmp/p10-contract-guard')
    check('D3', '长时脚本硬拒 <30 分钟（exit 2）', rc == 2, 'rc=%d' % rc)

    # ------------------------------------------------------------ E/F. 资源审计
    print('\nE/F. 同尺寸RT不重复分配 + dispose 配对')
    rc, so, se = run_tool('tools/plan100/perf_resource_audit.py', '--stdout')
    check('E1', '资源审计可运行（rc=0）', rc == 0, 'rc=%d %s' % (rc, se[:120]))
    audit_path = artifact_path('plan100/perf/resource-audit.json')
    if audit_path.is_file():
        a = json.loads(audit_path.read_text(encoding='utf8'))
        rts = a['renderTargets']['own']
        check('E2', '自有 RT 分配点无 unresolved',
              not [x for x in rts if x['resolution'] == 'unresolved'],
              [x['file'] for x in rts if x['resolution'] == 'unresolved'])
        check('E3', '每个自有 RT 都有护栏或 dispose/流出证据',
              all(x['reuseGuards'] or x['disposeSites'] or x['returnedFromFunction']
                  or x['disposedInSameScope'] for x in rts))
        check('F1', 'setSize 同尺寸语义已从 vendor 源码核对',
              'setSizeSemantics' in a['renderTargets']
              and 'dispose()' in a['renderTargets']['setSizeSemantics']['code'])
        check('F2', '审计声明了诚实边界',
              len(a['method']['honestLimits']) >= 3)
    else:
        check('E2', 'resource-audit.json 存在', False, '未生成')

    # ------------------------------------------------------------ G. 结构保留
    print('\nG. 结构保留 × 5 档（硬性原则 4）')
    rc, so, se = run_tool('tools/plan100/perf_structure_preservation.py', '--stdout')
    check('G1', '结构保留验证可运行（rc=0）', rc == 0, 'rc=%d %s' % (rc, se[:120]))
    sp_path = artifact_path('plan100/perf/structure-preservation.json')
    if sp_path.is_file():
        sp = json.loads(sp_path.read_text(encoding='utf8'))
        check('G2', '五种模式全部保留结构信息',
              sp['summary']['modesPreserved'] == sp['summary']['modesChecked'] == 5,
              json.dumps(sp['summary'], ensure_ascii=False))
        check('G3', '无结构保留违例', sp['summary']['violations'] == 0)
        check('G4', '五档模式名与计划原文一致',
              {m['mode'] for m in sp['modes']} ==
              {'native-4k', 'auto-degrade', 'low-quality', 'reduced-motion', 'webgl-fallback'})
        check('G5', '声明了像素证据待跑（不冒充像素证据）',
              sp['pixelEvidencePending']['status'] == 'pending-gpu')
    else:
        check('G2', 'structure-preservation.json 存在', False, '未生成')
    rc, so, se = run_tool('tools/plan100/perf_structure_preservation_selftest.py')
    check('G6', '结构保留验证器非空转（变异测试通过）', rc == 0, 'rc=%d' % rc)

    # ------------------------------------------------------------ H. 八项动作
    print('\nH. 长时脚本八项必含动作（E 节）')
    check('H1', '七场景与报告器对齐', LR.SCENARIOS == PR.SCENARIO_IDS)
    check('H2', '三书齐全', len(LR.BOOKS) == 3)
    check('H3', '罗盘进出双向',
          'compass-enter' in LR.ACTIONS and 'compass-exit' in LR.ACTIONS)
    check('H4', '暂停恢复双向',
          'pause-resume' in LR.ACTIONS and 'pause-resume-back' in LR.ACTIONS)
    check('H5', '窗口改变含原生4K档',
          any(v[0] == 3840 and v[1] == 2160 for v in LR.VIEWPORTS))
    check('H6', '长任务用 PerformanceObserver',
          'PerformanceObserver' in (ROOT / 'tools/plan100/perf_longrun_30min.py')
          .read_text(encoding='utf8'))
    rc, so, se = run_tool('tools/plan100/perf_longrun_30min_selftest.py')
    check('H7', '长时脚本静态自检通过', rc == 0, 'rc=%d' % rc)
    rc, so, se = run_tool('tools/plan100/perf_report_selftest.py')
    check('H8', '报告器自检通过', rc == 0, 'rc=%d' % rc)
    rc, so, se = run_tool('tools/plan100/perf_gpu_stage.py', '--minutes', '5',
                          '--out', '/tmp/p10-contract-gpu')
    check('H9', 'GPU 执行器拒绝 <30 分钟（exit 2）', rc == 2, 'rc=%d' % rc)
    rc, so, se = run_tool('tools/plan100/perf_gpu_stage.py', '--base', 'http://127.0.0.1:1',
                          '--out', '/tmp/p10-contract-gpu2')
    check('H10', 'GPU 执行器前置检查失败时拒绝启动（exit 3）', rc == 3, 'rc=%d' % rc)
    check('H11', 'GPU 执行器先查 GPU 占用与锁归属',
          'headless_chrome_count' in (ROOT / 'tools/plan100/perf_gpu_stage.py').read_text(encoding='utf8')
          and 'lock_running_owner' in (ROOT / 'tools/plan100/perf_gpu_stage.py').read_text(encoding='utf8'))

    # ------------------------------------------------------------ 汇总
    passed = len([r for r in RESULTS if r['pass']])
    failed = [r for r in RESULTS if not r['pass']]
    out = {
        'tool': 'tools/plan100/perf_contract.py',
        'generatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'gpuRequired': False,
        'covers': ['双字段分离', '降档不冒充原生4K', '未测即null', '长时>=30min',
                   '同尺寸RT不重复分配', 'dispose配对', '结构保留x5档', '八项必含动作'],
        'notCovered': ['像素级结构对比（需 GPU）', '真实帧间隔与长时资源曲线（需 GPU）',
                       '真机设备证据（本仓库目前 0 条）'],
        'gpuStageRunner': 'tools/plan100/perf_gpu_stage.py（一条命令跑完整个 GPU 窗口）',
        'checks': RESULTS,
        'summary': {'total': len(RESULTS), 'passed': passed, 'failed': len(failed),
                    'failedIds': [r['id'] for r in failed]},
    }
    print()
    print('=' * 84)
    print('P10 离线契约：PASS %d / %d' % (passed, len(RESULTS)))
    if failed:
        for f in failed:
            print('  FAILED %s: %s — %s' % (f['id'], f['name'], str(f['detail'])[:140]))
    print('不覆盖（需 GPU）：%s' % '；'.join(out['notCovered']))

    if not args.stdout:
        p = ROOT / args.json
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print('已写：%s' % args.json)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
