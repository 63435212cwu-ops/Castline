#!/usr/bin/env python3
"""P10 · perf_report.py 自检：用合成夹具证明「双字段分离」规则真的会拦人。

**为什么需要这个自检**：`perf_report.py` 存在的唯一理由是拦住审核的扣分点
「不得用自适应降档后的帧率声称原生4K达标」。一个只会把数字抄进表格的报告器
也能跑通，但拦不住任何人。这里用**故意违规的夹具**证明它确实会 FAIL，
再用**合规夹具**证明它不会误伤 —— 两边都测，避免「永远 PASS 的假检查」。

夹具（全部合成，不冒充实测）：
  F1  合规原生4K + 60fps       → native4k met, 60fps met-at-native-4k
  F2  **违规**：降档下的 60fps  → 必须 FAIL `no-downscaled-fps-as-native-4k`
  F3  缩放画布（1920×1080）的 60fps → 60fps met 但 native4k 不 met（不算违规，但不得混淆）
  F4  原生4K 但只 54.5fps      → native4k met, 60fps not-met（对应审核的 54.5fps 实测）
  F5  未测场景                 → 所有指标必须 null
  F6  长时 6 分钟（< 30 分钟）  → 必须 FAIL `longrun-duration-honest`
  F7  长时 30 分钟             → PASS

用法：python3 tools/plan100/perf_report_selftest.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'plan100'))

import perf_report as PR

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name, ('  — ' + detail) if detail and not cond else ''))


# ------------------------------------------------------------------ 夹具构造
def native4k_quality(**over):
    q = {'dpr': 1, 'deviceDpr': 1, 'boost': 1, 'boostPin': True, 'samples': 2,
         'degrade': 0, 'drawW': 3840, 'drawH': 2160, 'gl2': True,
         'sharedTier': {'tag': 'full', 'level': 0, 'glow': 12, 'labels': 'd2',
                        'particles': 1, 'animation': 1}}
    q.update(over)
    return q


def intervals_for_fps(fps, n=240):
    """n 帧的间隔数组，均值 = 1000/fps，加轻微抖动让 P95>均值（更接近真实）。"""
    base = 1000.0 / fps
    out = []
    for i in range(n):
        out.append(base * (1.9 if i % 20 == 19 else 0.96))
    return out


def rec(scenario, quality, fps, **over):
    r = {
        'scenario': scenario,
        'capturedAt': '2026-10-07T00:00:00Z',
        'source': 'selftest-fixture',
        'quality': quality,
        'frameIntervalsMs': intervals_for_fps(fps),
        'longTasks': [16.3, 31.4],
        'gpuUploads': 128,
        'rtCreates': 4,
        'rtDisposes': 2,
        'textures': 37,
        'geometries': 41,
        'programs': 22,
        'domNodes': 1840,
        'memory': [{'t': 0, 'usedMB': 220.0}, {'t': 60000, 'usedMB': 224.0},
                   {'t': 120000, 'usedMB': 227.5}],
        'errors': {'contextLost': 0, 'jserr': 0, 'jsrej': 0, 'shaderErrors': 0},
    }
    r.update(over)
    return r


def run(report, label):
    """把夹具喂进 build_report（走真实路径，不 mock）。"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'fixture.json'
        p.write_text(json.dumps(report, ensure_ascii=False), encoding='utf8')
        return PR.build_report([str(p)])


def scenario_of(rep, sid):
    return next(s for s in rep['scenarios'] if s['scenario'] == sid)


def check_failed(rep, cid):
    c = next((x for x in rep['crossChecks'] if x['id'] == cid), None)
    return c is not None and not c['pass']


def main():
    print('=' * 84)
    print('perf_report.py 自检 · 双字段分离规则')
    print('=' * 84)

    # ---------------------------------------------------------- F1 合规
    print('\nF1 合规：原生4K + 60fps（逐帧间隔）')
    rep = run([rec('steady', native4k_quality(), 62)], 'F1')
    sc = scenario_of(rep, 'steady')
    check('F1 native4k met', sc['native4kCapability']['met'] is True,
          json.dumps(sc['native4kCapability'], ensure_ascii=False))
    check('F1 60fps met-at-native-4k',
          sc['runs'][0]['achieves60fps']['status'] == 'met-at-native-4k',
          json.dumps(sc['runs'][0]['achieves60fps'], ensure_ascii=False))
    check('F1 无硬检查失败', rep['summary']['hardCheckFailures'] == 0
          or all(c['id'] == 'longrun-duration-honest'
                 for c in rep['crossChecks'] if not c['pass']),
          json.dumps([c['id'] for c in rep['crossChecks'] if not c['pass']]))

    # ---------------------------------------------------------- F2 违规核心
    print('\nF2 违规：降档（degrade=2, boost=0, dpr=0.66）下 60fps —— 必须被拦住')
    bad_q = native4k_quality(degrade=2, boost=0, dpr=0.66, drawW=2534, drawH=1426,
                             sharedTier={'tag': 'low', 'level': 2, 'glow': 4,
                                         'labels': 'd0', 'particles': 0.5, 'animation': 0.5})
    rep = run([rec('quality-switch', bad_q, 61)], 'F2')
    sc = scenario_of(rep, 'quality-switch')
    check('F2 native4k 不 met（降档）', sc['native4kCapability']['met'] is False,
          json.dumps(sc['native4kCapability'], ensure_ascii=False))
    check('F2 60fps 标为 achieved-below-native-4k（画布非4K）',
          sc['runs'][0]['achieves60fps']['status'] == 'achieved-below-native-4k',
          json.dumps(sc['runs'][0]['achieves60fps'], ensure_ascii=False))
    check('F2 事实字段 atNativeCanvas=False / degraded=True',
          sc['runs'][0]['achieves60fps'].get('atNativeCanvas') is False
          and sc['runs'][0]['achieves60fps'].get('degraded') is True,
          json.dumps(sc['runs'][0]['achieves60fps'], ensure_ascii=False))
    check('F2 场景级 atNative4k 为 false',
          sc['achieves60fps'].get('atNative4k') is False,
          json.dumps(sc['achieves60fps'], ensure_ascii=False))
    check('F2 违规检查 no-downscaled-fps 保持 PASS（因为没把它标成原生4K达标）',
          not check_failed(rep, 'no-downscaled-fps-as-native-4k'))

    print('\nF2a 画布仍 3840×2160 但 boost=0/degrade=1 → achieved-at-reduced-tier')
    dg_q = native4k_quality(degrade=1, boost=0,
                            sharedTier={'tag': 'mid', 'level': 1, 'glow': 8,
                                        'labels': 'd1', 'particles': 1, 'animation': 1})
    rep = run([rec('steady', dg_q, 61)], 'F2a')
    sc = scenario_of(rep, 'steady')
    check('F2a native4k 不 met（档位被降）', sc['native4kCapability']['met'] is False,
          json.dumps(sc['native4kCapability'], ensure_ascii=False))
    check('F2a 60fps 标为 achieved-at-reduced-tier',
          sc['runs'][0]['achieves60fps']['status'] == 'achieved-at-reduced-tier',
          json.dumps(sc['runs'][0]['achieves60fps'], ensure_ascii=False))
    check('F2a 事实字段 atNativeCanvas=True / degraded=True',
          sc['runs'][0]['achieves60fps'].get('atNativeCanvas') is True
          and sc['runs'][0]['achieves60fps'].get('degraded') is True)

    print('\nF2b 篡改：伪造 quality.drawW=3840 但 degrade=2 —— 检查必须 FAIL')
    forged = native4k_quality(degrade=2, boost=0, dpr=0.66)
    rep = run([rec('steady', forged, 61)], 'F2b')
    sc = scenario_of(rep, 'steady')
    check('F2b 降档下 native4k 仍判 False（degraded 优先于分辨率）',
          sc['native4kCapability']['met'] is False,
          json.dumps(sc['native4kCapability'], ensure_ascii=False))
    check('F2b 60fps 不得标 met-at-native-4k',
          sc['runs'][0]['achieves60fps']['status'] != 'met-at-native-4k',
          sc['runs'][0]['achieves60fps']['status'])

    print('\nF2c 交叉检查单元测试：人为制造 met+degraded 矛盾')
    fake_rep = {
        'scenarios': [{
            'scenario': 'steady', 'status': 'measured',
            'metrics': {}, 'native4kCapability': {'status': 'met', 'met': True},
            'achieves60fps': {'status': 'met-at-native-4k', 'met': True, 'atNative4k': True},
            'runs': [{'origin': 'forged', 'degraded': True,
                      'degradeReasons': ['degrade=2'],
                      'native4kCapability': {'met': True},
                      'achieves60fps': {'met': True}}],
        }],
    }
    checks = PR.cross_checks(fake_rep['scenarios'], [])
    c = next(x for x in checks if x['id'] == 'no-downscaled-fps-as-native-4k')
    check('F2c 矛盾被检出（pass=False）', c['pass'] is False,
          json.dumps(c, ensure_ascii=False))
    check('F2c 违规条目指向 steady/forged',
          any(v.get('scenario') == 'steady' for v in c['violations']))

    # ---------------------------------------------------------- F3 缩放画布
    print('\nF3 缩放画布 1920×1080 下的 60fps —— met 但不得混淆为原生4K')
    q = native4k_quality(drawW=1920, drawH=1080, boost=0)
    rep = run([rec('steady', q, 63)], 'F3')
    sc = scenario_of(rep, 'steady')
    check('F3 native4k not-native-4k',
          sc['runs'][0]['native4kCapability']['status'] == 'not-native-4k',
          sc['runs'][0]['native4kCapability']['status'])
    check('F3 60fps achieved-below-native-4k',
          sc['runs'][0]['achieves60fps']['status'] == 'achieved-below-native-4k',
          sc['runs'][0]['achieves60fps']['status'])

    # ---------------------------------------------------------- F4 审核实测场景
    print('\nF4 原生4K + 54.5fps（审核实测的三国短测）—— native4k met / 60fps not-met')
    rep = run([rec('longrun', native4k_quality(), 54.5)], 'F4')
    sc = scenario_of(rep, 'longrun')
    check('F4 native4k met（画布确实 3840×2160 未降档）',
          sc['native4kCapability']['met'] is True)
    check('F4 60fps not-met（P95 超预算）',
          sc['runs'][0]['achieves60fps']['status'] == 'not-met',
          json.dumps(sc['runs'][0]['achieves60fps'], ensure_ascii=False))
    check('F4 场景级硬检查不含双字段违规',
          not check_failed(rep, 'no-downscaled-fps-as-native-4k'))
    check('F4 长时场景时长不足被检出（夹具只有 240 帧）',
          check_failed(rep, 'longrun-duration-honest'))

    # ---------------------------------------------------------- F5 未测
    print('\nF5 未测场景 —— 指标必须全 null')
    rep = run([rec('steady', native4k_quality(), 60)], 'F5')
    nm = [s for s in rep['scenarios'] if s['status'] == 'not-measured']
    check('F5 有 6 个场景未测', len(nm) == 6, '实际 %d' % len(nm))
    all_null = all(v is None for s in nm for v in s['metrics'].values())
    check('F5 未测场景所有指标为 null', all_null)
    check('F5 未测场景双字段都 not-measured',
          all(s['native4kCapability']['status'] == 'not-measured'
              and s['achieves60fps']['status'] == 'not-measured' for s in nm))
    check('F5 unmeasured-stays-null 检查 PASS',
          not check_failed(rep, 'unmeasured-stays-null'))

    # ---------------------------------------------------------- F6 长时时长
    print('\nF6 长时 6 分钟（< 30 分钟）—— 必须 FAIL 时长检查')
    long6 = rec('longrun', native4k_quality(), 60,
                actualSampledSeconds=360.0, requestedMinutes=6)
    rep = run([long6], 'F6')
    c = next(x for x in rep['crossChecks'] if x['id'] == 'longrun-duration-honest')
    check('F6 时长检查 FAIL', c['pass'] is False, json.dumps(c, ensure_ascii=False))
    check('F6 记录了实测秒数 360', c.get('actualSampledSeconds') == 360.0)

    print('\nF7 长时 30 分钟 —— 时长检查 PASS')
    long30 = rec('longrun', native4k_quality(), 60,
                 actualSampledSeconds=1801.5, requestedMinutes=30)
    rep = run([long30], 'F7')
    c = next(x for x in rep['crossChecks'] if x['id'] == 'longrun-duration-honest')
    check('F7 时长检查 PASS', c['pass'] is True, json.dumps(c, ensure_ascii=False))

    # ---------------------------------------------------------- F8 双字段存在性
    print('\nF8 双字段结构：每个场景都必须同时有两个字段')
    rep = run([rec('steady', native4k_quality(), 60)], 'F8')
    check('F8 two-separate-fields PASS',
          not check_failed(rep, 'two-separate-fields'))
    check('F8 全部 7 场景都有两个字段',
          all('native4kCapability' in s and 'achieves60fps' in s for s in rep['scenarios']))
    check('F8 总表列齐七场景', len(rep['scenarios']) == 7)

    # ---------------------------------------------------------- F9 长时分场景展开
    print('\nF9 longrun 的 scenarios[] 展开为独立场景记录')
    wrapped = {'requestedMinutes': 30, 'actualSampledSeconds': 1810.0,
               'quality': native4k_quality(),
               'scenarios': [
                   rec('steady', native4k_quality(), 61),
                   rec('camera-transition', native4k_quality(), 58),
                   rec('quality-switch', native4k_quality(), 57),
               ]}
    rep = run([wrapped], 'F9')
    check('F9 steady 被展开', scenario_of(rep, 'steady')['status'] == 'measured')
    check('F9 camera-transition 被展开',
          scenario_of(rep, 'camera-transition')['status'] == 'measured')
    check('F9 未在 scenarios[] 里的场景仍未测',
          scenario_of(rep, 'first-frame')['status'] == 'not-measured')

    # ---------------------------------------------------------- F10 无输入
    print('\nF10 零输入 —— 必须不崩，且七场景全 not-measured')
    rep = PR.build_report([])
    check('F10 不崩且七场景全 not-measured',
          len(rep['scenarios']) == 7
          and all(s['status'] == 'not-measured' for s in rep['scenarios']))
    check('F10 字段1 met=false', rep['verdict']['native4kCapability']['met'] is False)
    check('F10 字段2 met=false', rep['verdict']['achieves60fps']['met'] is False)

    # ---------------------------------------------------------- F11 CLI
    print('\nF11 CLI：--check 在有硬失败时 exit 1')
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'f.json'
        p.write_text(json.dumps([rec('steady', native4k_quality(), 60)]), encoding='utf8')
        r = subprocess.run([sys.executable, str(ROOT / 'tools/plan100/perf_report.py'),
                            '--input', str(p), '--stdout', '--check'],
                           capture_output=True, text=True)
        check('F11 缺长时 ⇒ exit 1', r.returncode == 1, 'rc=%d' % r.returncode)
        check('F11 stdout 有字段1/字段2', '原生4K能力' in r.stdout and '达到60fps' in r.stdout)

    # ---------------------------------------------------------- F12 md 渲染
    print('\nF12 Markdown 渲染含双字段与七场景表')
    rep = run([rec('steady', native4k_quality(), 62)], 'F12')
    md = PR.render_md(rep)
    check('F12 md 含「原生4K能力」', '原生4K能力' in md)
    check('F12 md 含「达到60fps」', '达到60fps' in md)
    check('F12 md 七场景齐全', all(s[1] in md for s in PR.SCENARIOS))
    check('F12 md 含交叉检查章节', '交叉检查' in md)
    check('F12 md 含诚实边界', '诚实边界' in md)

    # ---------------------------------------------------------- F13 截图-only
    print('\nF13 只有画布事实、无帧率证据 —— 不得签收原生4K能力（截图画布≠4K性能）')
    shot_only = {
        'scenario': 'first-entry',
        'source': 'selftest-fixture-screenshot-only',
        'quality': native4k_quality(),
        'frameIntervalsMs': [],
        'errors': {'jserr': 0, 'jsrej': 0, 'shaderErrors': 0},
    }
    rep = run([shot_only], 'F13')
    sc = scenario_of(rep, 'first-entry')
    check('F13 native4k status = at-native-resolution-screenshot-only',
          sc['runs'][0]['native4kCapability']['status'] == 'at-native-resolution-screenshot-only',
          json.dumps(sc['runs'][0]['native4kCapability'], ensure_ascii=False))
    check('F13 native4k met 必须为 False', sc['native4kCapability']['met'] is False,
          json.dumps(sc['native4kCapability'], ensure_ascii=False))
    check('F13 理由提到截图画布不作为性能证据',
          '截图' in sc['runs'][0]['native4kCapability']['reason'])
    check('F13 60fps not-measured（无帧率数据）',
          sc['runs'][0]['achieves60fps']['status'] == 'not-measured')

    # ---------------------------------------------------------- 汇总
    print()
    print('=' * 84)
    print('自检结果：PASS %d · FAIL %d' % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print('  FAILED: %s' % f)
        return 1
    print('全部通过：双字段分离规则在违规夹具上确实会拦人，在合规夹具上不误伤。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
