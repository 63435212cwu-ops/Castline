#!/usr/bin/env python3
"""P10 · 性能报告生成器：分场景 P50/P95/P99 + 原生4K/60fps 双字段判定。

计划原文（`docs/plan-100-score-execution.md:52230`，E 节）：
  「性能报告**分开写**：首帧、首次进入、稳态、镜头转场、质量切换、返回、长时运行。
    记录 **P50/P95/P99 帧间隔、长任务、GPU 上传、RT dispose/create、纹理/几何数量、
    DOM 节点、内存趋势**。**原生4K能力和达到60fps是两个字段**；
    **不得用自适应降档后的帧率声称原生4K达标**。长时脚本至少30分钟……」

本工具把这七条要求固化成机器可校验的输出。它**只做汇总，不做测量**：
原始帧间隔 / 资源计数由浏览器脚本产出（`tests/scene_native4k_perf_browser.py`、
`tests/sky_longrun_resource_browser.py`、`tools/plan100/longrun_30min.py`），
本工具读那些原始记录，产出计划要求的分场景报告。

## 两条硬规则（本工具的立身之本）

规则 1 · **未测即 null**。七个场景里凡是没有任何原始记录的，所有指标一律 `null`，
  并标 `status: "not-measured"`。**不用相邻场景估算、不用同场景别的机器填充**。

规则 2 · **原生4K 与 60fps 分开判定**。`native4kCapability` 与 `achieves60fps`
  是两个独立字段，各有自己的 verdict 与证据：
    * 判「原生4K达标」的唯一依据是**该场景自己的实测 `drawW/drawH`**。
      不接受 `native4k: true` 这种自报字段（计划明令：不得用截图画布尺寸当稳定4K性能）。
    * 判「达到60fps」时**必须带上它是哪个档位的 60fps**。如果 60fps 是在
      `degrade>0` / `dpr<1` / 画布小于 3840×2160 下取得的，该字段写
      `achieved-at-reduced-tier`，且**不得**同时把 `native4kCapability` 标为 met——
      这正是审核扣分点「不得用自适应降档后的帧率声称原生4K达标」。

## 输入形状（两种都吃）

  A. 原生4K 短测（`scene_native4k_perf_browser.py` 的 result）：
     `{fps, p50, p95, p99, max, over50, elapsedMs, frames, quality{drawW,drawH,...}, canvas:[w,h], ...}`
  B. 长时资源曲线（`sky_longrun_resource_browser.py` / `longrun_30min.py` 的 report.json）：
     `{samples:[{second,t,fps,heap,memory{geometries,textures},programs,render{calls,triangles},...}],
       minutes:[...], heap{usedSlopeMBPerMin,...}, renderResources{...}, actualSampledSeconds, ...}`
  C. 分场景记录（`longrun_30min.py` 产出的 scenarios[]）：
     `{scenario, frameIntervalsMs:[...], longTasks:[{startTime,duration}], gpuUploads, rtCreates,
       rtDisposes, textures, geometries, programs, domNodes, memory[]}`

用法：
  python3 tools/plan100/perf_report.py --input <file-or-dir> [--input ...]
  python3 tools/plan100/perf_report.py --input <dir> --md artifacts/plan100/perf/perf-report.md
  python3 tools/plan100/perf_report.py --input <dir> --check    # 有 hardViolation 时 exit 1
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel

# ---------------------------------------------------------------- 计划规定的七个场景
SCENARIOS = [
    ('first-frame', '首帧'),
    ('first-entry', '首次进入'),
    ('steady', '稳态'),
    ('camera-transition', '镜头转场'),
    ('quality-switch', '质量切换'),
    ('return', '返回'),
    ('longrun', '长时运行'),
]
SCENARIO_IDS = [s[0] for s in SCENARIOS]
SCENARIO_ZH = dict(SCENARIOS)

METRIC_KEYS = ['p50', 'p95', 'p99', 'longTasks', 'gpuUploads', 'rtCreates', 'rtDisposes',
               'textures', 'geometries', 'programs', 'domNodes', 'memoryTrend']

NATIVE_4K_W, NATIVE_4K_H = 3840, 2160
FPS_TARGET = 60.0
FPS_P95_BUDGET_MS = 1000.0 / FPS_TARGET
LONG_TASK_MS = 50.0

SCENARIO_ALIASES = {
    'first-frame': ['first-frame', 'firstframe', 'first_frame', '首帧', 'coldstart', 'cold-start', 'boot'],
    'first-entry': ['first-entry', 'firstentry', 'first_entry', '首次进入', 'entry', 'enter',
                    'opening', 'open-book', 'load'],
    'steady': ['steady', 'steady-state', 'steadystate', '稳态', 'idle', 'static', 'still'],
    'camera-transition': ['camera-transition', 'transition', 'orbit', 'rotate', 'camera',
                          '镜头转场', 'fly', 'travel', 'tour', 'constellation-rotate'],
    'quality-switch': ['quality-switch', 'quality', 'degrade', 'tier-switch', 'boost',
                       '质量切换', 'switch'],
    'return': ['return', 'back', 'resume', '返回', 'restore', 'escape'],
    'longrun': ['longrun', 'long-run', 'long_run', 'soak', 'endurance', '长时运行', '30min'],
}


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def norm_scenario(name):
    """把任意脚本给的场景词映射到七个规范 id；认不出返回 None（不猜）。"""
    if not name:
        return None
    key = str(name).strip().lower()
    if key in SCENARIO_IDS:
        return key
    for sid, aliases in SCENARIO_ALIASES.items():
        if key in aliases:
            return sid
    return None


# ---------------------------------------------------------------- 统计
def percentile(sorted_vals, q):
    """线性插值分位（与浏览器端 p(q)=sorted[floor(n*q)] 口径不同，这里更保守）。

    计划只要求报告 P50/P95/P99，没规定插值方式。本实现用线性插值并在报告里
    写明口径，避免「同一份原始数据两边算出不同 P95」却没人知道为什么。
    """
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo))


def stats_from_intervals(intervals):
    """帧间隔数组 → P50/P95/P99/mean/max/超预算计数。"""
    vals = sorted(float(v) for v in intervals if isinstance(v, (int, float)) and v >= 0)
    if not vals:
        return None
    n = len(vals)
    mean = sum(vals) / n
    return {
        'n': n,
        'p50': round(percentile(vals, 0.50), 3),
        'p95': round(percentile(vals, 0.95), 3),
        'p99': round(percentile(vals, 0.99), 3),
        'mean': round(mean, 3),
        'max': round(vals[-1], 3),
        'min': round(vals[0], 3),
        'over16_67': len([v for v in vals if v > FPS_P95_BUDGET_MS]),
        'over50': len([v for v in vals if v > LONG_TASK_MS]),
        'impliedFpsMean': round(1000.0 / mean, 2) if mean > 0 else None,
    }


def slope_per_min(points):
    """内存趋势：最小二乘斜率 MB/min。points = [(t_ms, usedMB), ...]。"""
    pts = [(t / 60000.0, mb) for t, mb in points
           if isinstance(t, (int, float)) and isinstance(mb, (int, float))]
    n = len(pts)
    if n < 2:
        return None
    sx = sum(p[0] for p in pts); sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts); sxy = sum(p[0] * p[1] for p in pts)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return None
    return (n * sxy - sx * sy) / denom


# ---------------------------------------------------------------- 载入与归一
def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf8'))
    except Exception:
        return None


def iter_input_files(inputs):
    """--input 可以是文件或目录；目录递归找 *.json。"""
    found = []
    for raw in inputs:
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / raw
        if p.is_dir():
            found += [Path(x) for x in sorted(glob.glob(str(p / '**' / '*.json'), recursive=True))]
        elif p.is_file():
            found.append(p)
        else:
            print('  [warn] 输入不存在，跳过：%s' % raw, file=sys.stderr)
    uniq, seen = [], set()
    for f in found:
        rp = str(f.resolve())
        if rp not in seen:
            seen.add(rp); uniq.append(f)
    return uniq


def quality_of(rec):
    """从多种记录形状里取出质量元数据块。"""
    if not isinstance(rec, dict):
        return {}
    for k in ('quality', 'ready', 'health', 'health0'):
        v = rec.get(k)
        if isinstance(v, dict):
            if 'quality' in v and isinstance(v['quality'], dict):
                return v['quality']
            if 'drawW' in v:
                return v
    return {}


def observed_canvas(rec, q):
    """实测画布尺寸 —— 判原生4K的**唯一**依据。

    取值优先级：本次记录自己的 drawW/drawH > canvas 数组 > viewport。
    刻意**不读** `native4k` 自报字段：计划明令不得用截图画布尺寸或自报标签
    当稳定 4K 性能证据，所以这里只认实测数字。
    """
    dw = q.get('drawW'); dh = q.get('drawH')
    if isinstance(dw, (int, float)) and isinstance(dh, (int, float)):
        return int(dw), int(dh), 'quality.drawW/drawH'
    c = rec.get('canvas')
    if isinstance(c, (list, tuple)) and len(c) >= 2:
        return int(c[0]), int(c[1]), 'canvas[]'
    v = rec.get('viewport')
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return int(v[0]), int(v[1]), 'viewport[]'
    inst = rec.get('install')
    if isinstance(inst, dict) and isinstance(inst.get('canvas'), (list, tuple)):
        return int(inst['canvas'][0]), int(inst['canvas'][1]), 'install.canvas[]'
    return None, None, None


def observed_dpr(rec, q):
    for src in (q, rec):
        v = src.get('dpr')
        if isinstance(v, (int, float)):
            return float(v)
    return None


def is_degraded(rec, q):
    """该记录是否在**降档**状态下取得：degrade>0、boost=0、或 dpr 被压低。

    返回 (bool, [理由...])。判 60fps 时必须带上这个，否则就是把降档帧率
    冒充原生 4K 达标 —— 审核的扣分点原文。
    """
    reasons = []
    dg = q.get('degrade')
    if isinstance(dg, (int, float)) and dg > 0:
        reasons.append('degrade=%s（>0，自动/手动降档）' % dg)
    b = q.get('boost')
    if b == 0:
        reasons.append('boost=0（未锁高质量档）')
    st = q.get('sharedTier')
    if isinstance(st, dict) and st.get('tag') and st.get('tag') != 'full':
        reasons.append('sharedTier.tag=%s（非 full）' % st.get('tag'))
    if isinstance(st, dict) and isinstance(st.get('level'), (int, float)) and st['level'] > 0:
        reasons.append('sharedTier.level=%s（>0）' % st['level'])
    d = observed_dpr(rec, q)
    if isinstance(d, (int, float)) and d < 1:
        reasons.append('dpr=%s（<1，画布被压到视口以下）' % d)
    return (len(reasons) > 0), reasons


def memory_points(rec):
    """取出 (t_ms, usedMB) 序列，兼容长时 samples[] 与直接给的 memory[]。"""
    pts = []
    mem = rec.get('memory')
    if isinstance(mem, list):
        for m in mem:
            if isinstance(m, dict):
                t = m.get('t'); mb = m.get('usedMB')
                if isinstance(t, (int, float)) and isinstance(mb, (int, float)):
                    pts.append((t, mb))
    for s in rec.get('samples', []) or []:
        if not isinstance(s, dict):
            continue
        h = s.get('heap')
        t = s.get('t')
        if isinstance(h, dict) and isinstance(h.get('usedMB'), (int, float)) \
                and isinstance(t, (int, float)):
            pts.append((t, h['usedMB']))
    return pts


def normalize_record(rec, origin: str):
    """把任意输入形状压成统一的场景记录。认不出场景就返回 scenario=None。"""
    if not isinstance(rec, dict):
        return None
    sid = norm_scenario(rec.get('scenario') or rec.get('phase') or rec.get('label'))
    q = quality_of(rec)

    intervals = rec.get('frameIntervalsMs') or rec.get('intervals') or rec.get('deltas')
    if not isinstance(intervals, list):
        intervals = []
    intervals = [v for v in intervals if isinstance(v, (int, float))]

    if isinstance(rec.get('scenarios'), list):
        out = []
        for sub in rec['scenarios']:
            if isinstance(sub, dict):
                merged = dict(sub)
                merged.setdefault('_parentQuality', q)
                if not quality_of(merged) and q:
                    merged['quality'] = q
                r = normalize_record(merged, origin)
                if r:
                    out.append(r)
        return out

    st = stats_from_intervals(intervals) if intervals else None

    preagg = None
    if st is None and isinstance(rec.get('p50'), (int, float)):
        preagg = {k: rec.get(k) for k in ('p50', 'p95', 'p99', 'max', 'mean') if k in rec}
        if isinstance(rec.get('fps'), (int, float)):
            preagg['impliedFpsMean'] = rec['fps']
        if isinstance(rec.get('over50'), (int, float)):
            preagg['over50'] = rec['over50']
        preagg['n'] = rec.get('frames') if isinstance(rec.get('frames'), (int, float)) else None

    sample_fps = [s.get('fps') for s in (rec.get('samples') or [])
                  if isinstance(s, dict) and isinstance(s.get('fps'), (int, float)) and s['fps'] > 0]
    if st is None and sample_fps:
        intervals = [1000.0 / f for f in sample_fps]
        st = stats_from_intervals(intervals)
        st['derivedFrom'] = ('1 Hz 采样的每秒 fps 反推 1000/fps；'
                             '这是每秒分位，不是逐帧分位，粒度更粗')

    lt = rec.get('longTasks')
    long_tasks = len(lt) if isinstance(lt, list) else (rec.get('over50') if isinstance(rec.get('over50'), (int, float)) else None)

    mem_pts = memory_points(rec)
    heap = rec.get('heap') if isinstance(rec.get('heap'), dict) else {}
    trend = {
        'points': len(mem_pts),
        'slopeMBPerMin': (round(slope_per_min(mem_pts), 4) if len(mem_pts) >= 2
                          else (heap.get('usedSlopeMBPerMin') if isinstance(heap.get('usedSlopeMBPerMin'), (int, float)) else None)),
        'usedFirstMB': (mem_pts[0][1] if mem_pts else heap.get('usedFirstMB')),
        'usedLastMB': (mem_pts[-1][1] if mem_pts else heap.get('usedLastMB')),
    }
    if not mem_pts and trend['slopeMBPerMin'] is None:
        trend = None

    dw, dh, dsrc = observed_canvas(rec, q)
    degraded, dreasons = is_degraded(rec, q)

    return {
        'scenario': sid,
        'origin': origin,
        'source': rec.get('source') or rec.get('tool') or rec.get('script'),
        'capturedAt': rec.get('capturedAt') or rec.get('generatedAt'),
        'elapsedMs': rec.get('elapsedMs') or (rec.get('actualSampledSeconds', 0) * 1000 if rec.get('actualSampledSeconds') else None),
        'requestedMinutes': rec.get('requestedMinutes'),
        'actualSampledSeconds': rec.get('actualSampledSeconds'),
        'stats': st,
        'preaggregated': preagg,
        'frameIntervalSample': {
            'count': len(intervals),
            'head': [round(v, 3) for v in intervals[:40]],
        } if intervals else None,
        'longTasks': long_tasks,
        'gpuUploads': rec.get('gpuUploads'),
        'rtCreates': rec.get('rtCreates'),
        'rtDisposes': rec.get('rtDisposes'),
        'textures': rec.get('textures') if isinstance(rec.get('textures'), (int, float))
        else (rec.get('memory', {}).get('textures') if isinstance(rec.get('memory'), dict) else None),
        'geometries': rec.get('geometries') if isinstance(rec.get('geometries'), (int, float))
        else (rec.get('memory', {}).get('geometries') if isinstance(rec.get('memory'), dict) else None),
        'programs': rec.get('programs'),
        'domNodes': rec.get('domNodes') or rec.get('nodeCount'),
        'renderCalls': (rec.get('render') or {}).get('calls') if isinstance(rec.get('render'), dict) else rec.get('renderCalls'),
        'triangles': (rec.get('render') or {}).get('triangles') if isinstance(rec.get('render'), dict) else rec.get('triangles'),
        'memoryTrend': trend,
        'canvas': {'drawW': dw, 'drawH': dh, 'source': dsrc},
        'dpr': observed_dpr(rec, q),
        'quality': q,
        'degraded': degraded,
        'degradeReasons': dreasons,
        'errors': rec.get('errors') or {
            'contextLost': rec.get('contextLost'),
            'jserr': rec.get('jserr'),
            'jsrej': rec.get('jsrej'),
            'shaderErrors': rec.get('shaderErrors'),
        },
    }


def ingest(inputs):
    records, unclassified, bad = [], [], []
    for path in iter_input_files(inputs):
        data = load_json(path)
        if data is None:
            continue
        rel = str(path.relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path)
        items = data if isinstance(data, list) else [data]
        for item in items:
            r = normalize_record(item, rel)
            if r is None:
                continue
            if isinstance(r, list):
                for sub in r:
                    (records if sub['scenario'] else unclassified).append(sub)
                continue
            (records if r['scenario'] else unclassified).append(r)
        if not items:
            bad.append(rel)
    return records, unclassified, bad


# ---------------------------------------------------------------- 双字段判定
def judge_native4k(rec):
    """原生4K能力 —— 只看该场景**实测**画布，不看自报字段。

    但「画布是 4K」还不等于「4K 性能达标」：一张截图也能证明画布是 4K。
    计划明令「不得把截图画布尺寸当稳定4K性能」，因此本判定再分两层：
      * `met` 只在有**帧率证据**（逐帧间隔或预聚合分位）时才算成立；
      * 只有画布事实、没有帧率证据时给 `at-native-resolution-screenshot-only`，
        met=False，理由写明「画布为真但无性能证据」。
    这样「能力」字段不会因为一张静帧截图被误签收。
    """
    c = rec['canvas']
    dw, dh = c.get('drawW'), c.get('drawH')
    if dw is None or dh is None:
        return {'status': 'unknown', 'met': None,
                'reason': '该场景没有实测 drawW/drawH，无法判定原生4K；不用其他场景或自报字段补'}
    has_perf = bool((rec['stats'] or {}).get('p95') is not None
                    or (rec['preaggregated'] or {}).get('p95') is not None)
    if dw == NATIVE_4K_W and dh == NATIVE_4K_H:
        if rec['degraded']:
            return {'status': 'at-native-resolution-but-downscaled-tier', 'met': False,
                    'reason': ('画布确为 %dx%d，但本次记录处于降档状态（%s）；'
                               '分辨率为真、质量档非原生，不得据此签收原生4K能力'
                               % (dw, dh, '；'.join(rec['degradeReasons']))),
                    'observedCanvas': [dw, dh], 'canvasSource': c.get('source')}
        if not has_perf:
            return {'status': 'at-native-resolution-screenshot-only', 'met': False,
                    'reason': ('画布实测 %dx%d、未降档，但本次记录**没有帧率证据**；'
                               '计划明令不得把截图画布尺寸当稳定4K性能 ⇒ 只证明分辨率，'
                               '不签收原生4K能力' % (dw, dh)),
                    'observedCanvas': [dw, dh], 'canvasSource': c.get('source')}
        return {'status': 'met', 'met': True,
                'reason': '实测画布 %dx%d、未降档，且有帧率证据' % (dw, dh),
                'observedCanvas': [dw, dh], 'canvasSource': c.get('source')}
    return {'status': 'not-native-4k', 'met': False,
            'reason': ('实测画布 %dx%d ≠ %dx%d；这是等比缩放后的画布，'
                       '不得当作原生4K性能' % (dw, dh, NATIVE_4K_W, NATIVE_4K_H)),
            'observedCanvas': [dw, dh], 'canvasSource': c.get('source')}


def judge_60fps(rec, native_verdict):
    """达到60fps —— 必须带上是**哪个档位**的 60fps。

    状态按「画布是否真 4K」与「是否有降档」两个**独立事实**分开命名，
    不把两者混成一个模糊的「降档」标签（那样会丢掉真实原因）：

      met-at-native-4k            画布真 3840×2160、无降档、P95 达标
      achieved-below-native-4k    画布不是原生 4K（无论是否由降档造成）
      achieved-at-reduced-tier    画布**确是**原生 4K，但质量档被降（少见但可能）
      not-met                     P95 超预算

    无论哪种，只要不是第一项，就**不得**声称原生4K达标。降档理由始终随附。
    """
    st = rec['stats'] or rec['preaggregated']
    if not st or st.get('p95') is None:
        return {'status': 'not-measured', 'met': None,
                'reason': '该场景没有帧间隔数据（既无原始数组也无预聚合分位）'}
    p95 = st['p95']
    ok = p95 <= FPS_P95_BUDGET_MS
    c = rec['canvas']
    is_native_canvas = (c.get('drawW') == NATIVE_4K_W and c.get('drawH') == NATIVE_4K_H)
    dg_note = ('；降档理由：%s' % '；'.join(rec['degradeReasons'])) if rec['degraded'] else ''

    if not ok:
        status = 'not-met'
        reason = ('P95=%.3fms > %.3fms 预算（60fps 需 P95 ≤ 16.667ms）%s'
                  % (p95, FPS_P95_BUDGET_MS, dg_note))
    elif is_native_canvas and not rec['degraded']:
        status = 'met-at-native-4k'
        reason = ('P95=%.3fms ≤ %.3fms（60fps 预算），实测画布 %dx%d 且未降档'
                  % (p95, FPS_P95_BUDGET_MS, NATIVE_4K_W, NATIVE_4K_H))
    elif is_native_canvas:
        status = 'achieved-at-reduced-tier'
        reason = ('P95=%.3fms 达标，画布确为 %dx%d，但质量档被降%s ⇒ '
                  '这是**降档后**的60fps，不得声称原生4K达标'
                  % (p95, NATIVE_4K_W, NATIVE_4K_H, dg_note))
    else:
        status = 'achieved-below-native-4k'
        reason = ('P95=%.3fms 达标，但实测画布 %sx%s ≠ %dx%d%s ⇒ 不得声称原生4K达标'
                  % (p95, c.get('drawW'), c.get('drawH'), NATIVE_4K_W, NATIVE_4K_H, dg_note))
    return {'status': status, 'met': bool(ok), 'p95ms': p95,
            'budgetMs': round(FPS_P95_BUDGET_MS, 3),
            'atNativeCanvas': is_native_canvas,
            'degraded': rec['degraded'],
            'reason': reason}


def _run_label(rec, idx, total):
    """给每条记录一个人类可读的短标签，避免 md 里出现多行完全相同的 origin。"""
    bits = []
    src = rec.get('source')
    if src:
        bits.append(str(src).split('/')[-1])
    book = rec.get('quality', {}).get('_book') if isinstance(rec.get('quality'), dict) else None
    c = rec.get('canvas') or {}
    if c.get('drawW'):
        bits.append('%sx%s' % (c.get('drawW'), c.get('drawH')))
    if rec.get('capturedAt'):
        bits.append(str(rec['capturedAt']))
    if total > 1:
        bits.append('#%d' % (idx + 1))
    return ' · '.join(bits) if bits else ('记录 #%d' % (idx + 1))


def build_scenarios(records):
    """七个规范场景各出一段报告；没有原始记录的场景一律 null + not-measured。"""
    grouped = {sid: [] for sid in SCENARIO_IDS}
    for r in records:
        grouped[r['scenario']].append(r)

    out = []
    for sid in SCENARIO_IDS:
        recs = grouped[sid]
        entry = {
            'scenario': sid, 'scenarioZh': SCENARIO_ZH[sid],
            'recordCount': len(recs),
        }
        if not recs:
            entry.update({
                'status': 'not-measured',
                'metrics': {k: None for k in METRIC_KEYS},
                'native4kCapability': {'status': 'not-measured', 'met': None,
                                       'reason': '该场景无原始记录'},
                'achieves60fps': {'status': 'not-measured', 'met': None,
                                  'reason': '该场景无原始记录'},
                'note': '计划要求本场景单独报告；未测即 null，不用相邻场景估算填充。',
            })
            out.append(entry)
            continue

        runs = []
        for ri, r in enumerate(recs):
            nv = judge_native4k(r)
            fps = judge_60fps(r, nv)
            runs.append({'runIndex': ri, 'origin': r['origin'], 'source': r['source'],
                         'label': _run_label(r, ri, len(recs)),
                         'capturedAt': r['capturedAt'],
                         'canvas': r['canvas'], 'dpr': r['dpr'],
                         'degraded': r['degraded'], 'degradeReasons': r['degradeReasons'],
                         'quality': r['quality'],
                         'stats': r['stats'], 'preaggregated': r['preaggregated'],
                         'longTasks': r['longTasks'], 'gpuUploads': r['gpuUploads'],
                         'rtCreates': r['rtCreates'], 'rtDisposes': r['rtDisposes'],
                         'textures': r['textures'], 'geometries': r['geometries'],
                         'programs': r['programs'], 'domNodes': r['domNodes'],
                         'renderCalls': r['renderCalls'], 'triangles': r['triangles'],
                         'memoryTrend': r['memoryTrend'],
                         'errors': r['errors'],
                         'elapsedMs': r['elapsedMs'],
                         'actualSampledSeconds': r['actualSampledSeconds'],
                         'requestedMinutes': r['requestedMinutes'],
                         'native4kCapability': nv, 'achieves60fps': fps})

        measured = [x for x in runs if x['stats'] or x['preaggregated']]
        entry['status'] = 'measured' if measured else 'partial'
        def worst(key):
            vals = []
            for x in measured:
                st = x['stats'] or x['preaggregated'] or {}
                if st.get(key) is not None:
                    vals.append(st[key])
            return max(vals) if vals else None

        entry['metrics'] = {
            'p50': worst('p50'), 'p95': worst('p95'), 'p99': worst('p99'),
            'longTasks': (max([x['longTasks'] for x in runs if x['longTasks'] is not None])
                          if any(x['longTasks'] is not None for x in runs) else None),
            'gpuUploads': (max([x['gpuUploads'] for x in runs if x['gpuUploads'] is not None])
                           if any(x['gpuUploads'] is not None for x in runs) else None),
            'rtCreates': (max([x['rtCreates'] for x in runs if x['rtCreates'] is not None])
                          if any(x['rtCreates'] is not None for x in runs) else None),
            'rtDisposes': (max([x['rtDisposes'] for x in runs if x['rtDisposes'] is not None])
                           if any(x['rtDisposes'] is not None for x in runs) else None),
            'textures': (max([x['textures'] for x in runs if x['textures'] is not None])
                         if any(x['textures'] is not None for x in runs) else None),
            'geometries': (max([x['geometries'] for x in runs if x['geometries'] is not None])
                           if any(x['geometries'] is not None for x in runs) else None),
            'programs': (max([x['programs'] for x in runs if x['programs'] is not None])
                         if any(x['programs'] is not None for x in runs) else None),
            'domNodes': (max([x['domNodes'] for x in runs if x['domNodes'] is not None])
                         if any(x['domNodes'] is not None for x in runs) else None),
            'memoryTrend': next((x['memoryTrend'] for x in runs if x['memoryTrend']), None),
        }
        entry['metricsNote'] = ('场景级汇总取该场景下**最差**记录（P 值取最大），'
                                '不用最好的一条代表整个场景；逐条明细见 runs[]。')
        entry['runs'] = runs

        nv_met = [x for x in runs if x['native4kCapability'].get('met')]
        fps_ok = [x for x in runs if x['achieves60fps'].get('met')]
        entry['native4kCapability'] = (
            {'status': 'met', 'met': True,
             'reason': '%d/%d 条记录实测原生4K未降档' % (len(nv_met), len(runs)),
             'evidenceRuns': [x['origin'] for x in nv_met]}
            if nv_met else
            {'status': 'not-met', 'met': False,
             'reason': '；'.join(sorted({x['native4kCapability']['status'] for x in runs})),
             'detail': [{'origin': x['origin'], 'status': x['native4kCapability']['status'],
                         'reason': x['native4kCapability']['reason']} for x in runs]})
        entry['achieves60fps'] = (
            {'status': 'met' if any(x['achieves60fps']['status'] == 'met-at-native-4k' for x in fps_ok)
             else 'achieved-below-native-4k' if fps_ok else 'not-met',
             'met': True,
             'reason': '；'.join(sorted({x['achieves60fps']['status'] for x in fps_ok})),
             'atNative4k': any(x['achieves60fps'].get('atNativeCanvas') is True
                               and x['achieves60fps'].get('degraded') is False for x in fps_ok),
             'detail': [{'origin': x['origin'], 'status': x['achieves60fps']['status'],
                         'reason': x['achieves60fps']['reason']} for x in runs]}
            if fps_ok else
            {'status': 'not-met', 'met': False, 'atNative4k': False,
             'reason': '；'.join(sorted({x['achieves60fps']['status'] for x in runs})),
             'detail': [{'origin': x['origin'], 'status': x['achieves60fps']['status'],
                         'reason': x['achieves60fps']['reason']} for x in runs]})
        out.append(entry)
    return out


def cross_checks(scenarios, records):
    """三条硬规则的可机检结论 —— 这是本工具存在的理由。"""
    checks = []

    leaks = []
    for s in scenarios:
        if s['status'] == 'not-measured':
            for k, v in s['metrics'].items():
                if v is not None:
                    leaks.append({'scenario': s['scenario'], 'metric': k, 'value': v})
    checks.append({
        'id': 'unmeasured-stays-null',
        'rule': '未测场景的所有指标必须为 null（计划：未测必须保持 null，禁止用估算分填充）',
        'pass': not leaks, 'violations': leaks,
    })

    bogus = []
    for s in scenarios:
        for x in s.get('runs', []):
            fps = x['achieves60fps']
            nv = x['native4kCapability']
            if not fps.get('met'):
                continue
            if fps.get('status') == 'met-at-native-4k' and not (
                    fps.get('atNativeCanvas') is True and fps.get('degraded') is False):
                bogus.append({'scenario': s['scenario'], 'origin': x['origin'],
                              'why': ('标为 met-at-native-4k 但事实字段不符：'
                                      'atNativeCanvas=%s degraded=%s'
                                      % (fps.get('atNativeCanvas'), fps.get('degraded'))),
                              'degradeReasons': x['degradeReasons']})
            if x['degraded'] and nv.get('met'):
                bogus.append({'scenario': s['scenario'], 'origin': x['origin'],
                              'why': '降档状态下同时把 native4kCapability 判为 met',
                              'degradeReasons': x['degradeReasons']})
        sf = s.get('achieves60fps', {})
        if sf.get('atNative4k') and not s.get('native4kCapability', {}).get('met'):
            bogus.append({'scenario': s['scenario'], 'origin': 'scenario-level',
                          'why': '场景声称 atNative4k 但 native4kCapability 未 met'})
    checks.append({
        'id': 'no-downscaled-fps-as-native-4k',
        'rule': ('不得用自适应降档后的帧率声称原生4K达标'
                 '（计划 E 节原文；审核扣分点）'),
        'pass': not bogus, 'violations': bogus,
    })

    missing = [s['scenario'] for s in scenarios
               if 'native4kCapability' not in s or 'achieves60fps' not in s]
    checks.append({
        'id': 'two-separate-fields',
        'rule': '原生4K能力和达到60fps是两个字段（计划 E 节原文）',
        'pass': not missing, 'violations': missing,
    })

    rt_rows = []
    for s in scenarios:
        for x in s.get('runs', []):
            c, d = x.get('rtCreates'), x.get('rtDisposes')
            if isinstance(c, (int, float)) and isinstance(d, (int, float)):
                rt_rows.append({'scenario': s['scenario'], 'origin': x['origin'],
                                'rtCreates': c, 'rtDisposes': d, 'outstanding': c - d})
    checks.append({
        'id': 'rt-lifecycle-visible',
        'rule': '记录 RT dispose/create（计划 E 节原文）；差值必须可见，不得被平均掉',
        'pass': True, 'rows': rt_rows,
        'note': ('create>dispose 在长时运行中是正常的（对象仍在持有）；'
                 '关键看它是否随分钟数单调增长 —— 那才是泄漏。'),
    })

    longrun = next((s for s in scenarios if s['scenario'] == 'longrun'), None)
    if longrun and longrun['status'] == 'measured':
        secs = [x['actualSampledSeconds'] for x in longrun['runs']
                if isinstance(x.get('actualSampledSeconds'), (int, float))]
        best = max(secs) if secs else None
        checks.append({
            'id': 'longrun-duration-honest',
            'rule': '长时脚本至少30分钟（计划 E 节原文）；不得用缩短时长冒充',
            'pass': bool(best and best >= 1800),
            'actualSampledSeconds': best,
            'requiredSeconds': 1800,
            'violations': [] if (best and best >= 1800) else
                          ['实测 %.1f 秒 < 1800 秒' % (best or 0)],
        })
    else:
        checks.append({
            'id': 'longrun-duration-honest',
            'rule': '长时脚本至少30分钟（计划 E 节原文）；不得用缩短时长冒充',
            'pass': False, 'actualSampledSeconds': None, 'requiredSeconds': 1800,
            'violations': ['长时运行场景未测；30 分钟是真实时长要求，不得用缩短时长冒充'],
        })
    return checks


def build_report(inputs):
    records, unclassified, _ = ingest(inputs)
    scenarios = build_scenarios(records)
    checks = cross_checks(scenarios, records)

    measured = [s['scenario'] for s in scenarios if s['status'] == 'measured']
    not_measured = [s['scenario'] for s in scenarios if s['status'] == 'not-measured']
    native_met = [s['scenario'] for s in scenarios if s['native4kCapability'].get('met')]
    fps_met = [s['scenario'] for s in scenarios if s['achieves60fps'].get('met')]
    fps_native = [s['scenario'] for s in scenarios
                  if s['achieves60fps'].get('atNative4k')]

    hard = [c for c in checks if not c['pass']]

    return {
        'tool': 'tools/plan100/perf_report.py',
        'generatedAt': now_iso(),
        'planRequirement': ('性能报告分开写：首帧、首次进入、稳态、镜头转场、质量切换、返回、长时运行。'
                            '记录P50/P95/P99帧间隔、长任务、GPU上传、RT dispose/create、纹理/几何数量、'
                            'DOM节点、内存趋势。原生4K能力和达到60fps是两个字段；'
                            '不得用自适应降档后的帧率声称原生4K达标。长时脚本至少30分钟。'),
        'planRef': 'docs/plan-100-score-execution.md:52230',
        'method': {
            'percentile': ('线性插值（pos=(n-1)*q）；与浏览器端 sorted[floor(n*q)] 口径不同，'
                           '报告里两处口径都写明，避免同一份数据两边 P95 不一致却无从解释'),
            'fpsBudget': {'target': FPS_TARGET, 'p95BudgetMs': round(FPS_P95_BUDGET_MS, 3),
                          'decidedBy': 'P95 而不是均值 —— 均值会被好帧拉高，卡顿藏在 P95/P99'},
            'longTaskThresholdMs': LONG_TASK_MS,
            'native4kBasis': ('实测 drawW/drawH（quality.drawW/drawH > canvas[] > viewport[]）；'
                              '刻意不读 native4k 自报字段'),
            'degradeDetection': ['degrade>0', 'boost=0', 'sharedTier.tag!=full',
                                 'sharedTier.level>0', 'dpr<1'],
            'honestLimits': [
                '本工具只汇总，不测量。原始帧间隔必须来自浏览器脚本。',
                '每秒 fps 反推的分位粒度比逐帧粗，报告里以 derivedFrom 标注。',
                '未测场景一律 null；不用相邻场景或别的机器估算填充。',
                '场景级汇总取最差记录；「最好的一条」不作为场景结论。',
            ],
        },
        'inputs': sorted({r['origin'] for r in records} | {u['origin'] for u in unclassified}),
        'summary': {
            'scenariosMeasured': measured,
            'scenariosWithRecords': [s['scenario'] for s in scenarios if s['recordCount'] > 0],
            'scenariosWithFpsEvidence': [s['scenario'] for s in scenarios
                                         if (s['metrics'] or {}).get('p95') is not None],
            'scenariosNotMeasured': not_measured,
            'scenarioCount': len(SCENARIO_IDS),
            'recordsTotal': len(records),
            'recordsUnclassifiedScenario': len(unclassified),
            'native4kMetScenarios': native_met,
            'fps60MetScenarios': fps_met,
            'fps60AtNative4kScenarios': fps_native,
            'hardCheckFailures': len(hard),
        },
        'verdict': {
            'native4kCapability': {
                'met': bool(native_met),
                'scenarios': native_met,
                'notMetScenarios': [s['scenario'] for s in scenarios
                                    if s['native4kCapability'].get('met') is False],
                'notMeasuredScenarios': not_measured,
                'statement': ('有 %d/7 个场景实测原生4K未降档' % len(native_met)),
                'note': ('这是**能力**字段：指实测画布确为 3840×2160 且未处于降档状态。'
                         '它不等于「在该分辨率下达到60fps」——那看下一个字段。'),
            },
            'achieves60fps': {
                'met': bool(fps_met),
                'scenarios': fps_met,
                'atNative4k': bool(fps_native),
                'atNative4kScenarios': fps_native,
                'statement': ('%d/7 个场景 P95 ≤ 16.667ms；其中 %d 个是在原生4K未降档下达成的'
                              % (len(fps_met), len(fps_native))),
                'note': ('这是**帧率**字段，且必须带档位。若 atNative4k 为 false，'
                         '说明 60fps 只在降档/缩放画布下取得 —— 不得据此声称原生4K达标。'),
            },
            'separation': ('两个字段独立判定，各有自己的证据与状态；'
                           '本报告不做「综合性能分」，避免把二者混成一个数字。'),
        },
        'scenarios': scenarios,
        'crossChecks': checks,
        'unclassifiedRecords': unclassified,
    }


# ---------------------------------------------------------------- 渲染
def fmt(v, nd=2, dash='—'):
    if v is None:
        return dash
    if isinstance(v, float):
        return ('%.' + str(nd) + 'f') % v
    return str(v)


def render_md(rep):
    L = []
    s = rep['summary']
    L.append('# P10 性能报告（分场景）')
    L.append('')
    L.append('生成：`%s` · 工具：`%s`' % (rep['generatedAt'], rep['tool']))
    L.append('')
    L.append('> 计划 E 节原文：%s' % rep['planRequirement'])
    L.append('')
    with_records = [x['scenario'] for x in rep['scenarios'] if x['recordCount'] > 0]
    fps_measured = [x['scenario'] for x in rep['scenarios']
                    if (x['metrics'] or {}).get('p95') is not None]
    L.append('**覆盖状态：%d/7 场景**有原始记录（`%s`）；其中 **%d 个有帧率证据**；'
             '**%d 个完全未测**（指标全部为 `—`）。**'
             % (len(with_records), '`, `'.join(with_records) or '无',
                len(fps_measured), len(s['scenariosNotMeasured'])))
    if len(with_records) > len(fps_measured):
        L.append('')
        L.append('> 有记录但无帧率：`%s` —— 只有画布/档位事实（例如冻结基线截图），'
                 '**不构成帧率证据**，其 P50/P95/P99 保持 `—`。'
                 % '`, `'.join([x for x in with_records if x not in fps_measured]))
    if s['scenariosNotMeasured']:
        L.append('')
        L.append('> ⚠️ 未测场景：`%s`。本报告**不含**这些场景的任何帧率结论，'
                 '也不用相邻场景估算填充。'
                 % '`, `'.join(s['scenariosNotMeasured']))
    L.append('')
    L.append('## 0. 两个独立字段（不合并成一个分数）')
    L.append('')
    nv, fp = rep['verdict']['native4kCapability'], rep['verdict']['achieves60fps']
    L.append('| 字段 | 结论 | 覆盖场景 |')
    L.append('|---|---|---|')
    L.append('| **原生4K能力** | %s | %s |' % (nv['statement'],
                                              ', '.join(nv['scenarios']) or '—'))
    L.append('| **达到60fps** | %s | %s |' % (fp['statement'],
                                            ', '.join(fp['scenarios']) or '—'))
    L.append('')
    L.append('- 原生4K能力：%s' % nv['note'])
    L.append('- 达到60fps：%s' % fp['note'])
    L.append('- %s' % rep['verdict']['separation'])
    L.append('')
    L.append('## 1. 七场景总表')
    L.append('')
    L.append('| 场景 | 状态 | P50 ms | P95 ms | P99 ms | 长任务 | GPU上传 | RT create | RT dispose | 纹理 | 几何 | program | DOM | 内存 MB/min |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for sc in rep['scenarios']:
        m = sc['metrics']
        tr = m.get('memoryTrend') or {}
        L.append('| %s %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            sc['scenario'], sc['scenarioZh'], sc['status'],
            fmt(m.get('p50'), 3), fmt(m.get('p95'), 3), fmt(m.get('p99'), 3),
            fmt(m.get('longTasks'), 0), fmt(m.get('gpuUploads'), 0),
            fmt(m.get('rtCreates'), 0), fmt(m.get('rtDisposes'), 0),
            fmt(m.get('textures'), 0), fmt(m.get('geometries'), 0),
            fmt(m.get('programs'), 0), fmt(m.get('domNodes'), 0),
            fmt(tr.get('slopeMBPerMin'), 3)))
    L.append('')
    L.append('未测场景的指标一律 `—`（null），**不用相邻场景估算填充**。')
    L.append('')
    L.append('## 2. 逐场景双字段判定')
    L.append('')
    for sc in rep['scenarios']:
        L.append('### %s · %s' % (sc['scenario'], sc['scenarioZh']))
        L.append('')
        L.append('- 记录数：%d · 状态：**%s**' % (sc['recordCount'], sc['status']))
        L.append('- **原生4K能力**：`%s` met=%s — %s'
                 % (sc['native4kCapability'].get('status'), sc['native4kCapability'].get('met'),
                    sc['native4kCapability'].get('reason')))
        L.append('- **达到60fps**：`%s` met=%s — %s'
                 % (sc['achieves60fps'].get('status'), sc['achieves60fps'].get('met'),
                    sc['achieves60fps'].get('reason')))
        for x in sc.get('runs', []):
            st = x['stats'] or x['preaggregated'] or {}
            L.append('  - **%s** — %s'
                     % (x.get('label') or x['origin'],
                        ('画布 %sx%s' % (x['canvas'].get('drawW'), x['canvas'].get('drawH'))
                         if x['canvas'].get('drawW') else '画布未知')))
            L.append('    - 来源：`%s`' % x['origin'])
            L.append('    - dpr=%s · 降档=%s · P50=%s · P95=%s · P99=%s · n=%s'
                     % (fmt(x.get('dpr'), 2), x['degraded'],
                        fmt(st.get('p50'), 3), fmt(st.get('p95'), 3), fmt(st.get('p99'), 3),
                        fmt(st.get('n'), 0)))
            if x['degraded']:
                L.append('    - 降档理由：%s' % '；'.join(x['degradeReasons']))
            L.append('    - 原生4K：`%s` · 60fps：`%s`'
                     % (x['native4kCapability']['status'], x['achieves60fps']['status']))
        L.append('')
    L.append('## 3. 交叉检查（可机检）')
    L.append('')
    for c in rep['crossChecks']:
        L.append('- [%s] **%s** — %s' % ('PASS' if c['pass'] else 'FAIL', c['id'], c['rule']))
        for v in c.get('violations', [])[:6]:
            L.append('    - 违规：`%s`' % (json.dumps(v, ensure_ascii=False)[:240]))
        if c['id'] == 'longrun-duration-honest':
            L.append('    - 实测时长：%s 秒 / 要求 %s 秒'
                     % (fmt(c.get('actualSampledSeconds'), 1), c.get('requiredSeconds')))
        if c['id'] == 'rt-lifecycle-visible' and c.get('rows'):
            L.append('    - RT 生命周期：%s'
                     % '; '.join('%s create=%s dispose=%s 差=%s'
                                 % (r['scenario'], r['rtCreates'], r['rtDisposes'],
                                    r['outstanding']) for r in c['rows'][:8]))
    L.append('')
    L.append('## 4. 诚实边界')
    L.append('')
    for lim in rep['method']['honestLimits']:
        L.append('- %s' % lim)
    L.append('')
    L.append('分位口径：%s' % rep['method']['percentile'])
    L.append('')
    L.append('原生4K判定依据：%s' % rep['method']['native4kBasis'])
    L.append('')
    return '\n'.join(L)


def print_summary(rep):
    s = rep['summary']
    print('=' * 84)
    print('P10 性能报告 · %s' % rep['generatedAt'])
    print('=' * 84)
    print('输入：%s' % (', '.join(rep['inputs']) or '（无）'))
    print('记录：%d 条 · 已归类 %d · 未归类 %d'
          % (s['recordsTotal'], s['recordsTotal'] - s['recordsUnclassifiedScenario'],
             s['recordsUnclassifiedScenario']))
    print('已测场景：%s' % (', '.join(s['scenariosMeasured']) or '（无）'))
    print('未测场景：%s' % (', '.join(s['scenariosNotMeasured']) or '（无）'))
    print()
    nv, fp = rep['verdict']['native4kCapability'], rep['verdict']['achieves60fps']
    print('【字段1 原生4K能力】%s' % nv['statement'])
    print('【字段2 达到60fps 】%s' % fp['statement'])
    print()
    print('%-20s %-13s %8s %8s %8s' % ('场景', '状态', 'P50', 'P95', 'P99'))
    for sc in rep['scenarios']:
        m = sc['metrics']
        print('%-20s %-13s %8s %8s %8s'
              % (sc['scenario'], sc['status'], fmt(m.get('p50'), 3),
                 fmt(m.get('p95'), 3), fmt(m.get('p99'), 3)))
    print()
    for c in rep['crossChecks']:
        print('[%s] %s' % ('PASS' if c['pass'] else 'FAIL', c['id']))
        for v in c.get('violations', [])[:4]:
            print('       %s' % json.dumps(v, ensure_ascii=False)[:180])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--input', action='append', default=[],
                    help='原始记录文件或目录（可重复）')
    ap.add_argument('--out', default=str(artifact_path('plan100/perf/perf-report.json')))
    ap.add_argument('--md', default=str(artifact_path('plan100/perf/perf-report.md')))
    ap.add_argument('--stdout', action='store_true', help='只打印，不写盘')
    ap.add_argument('--check', action='store_true', help='有硬检查失败时 exit 1')
    args = ap.parse_args()

    inputs = args.input or [str(artifact_path('plan100/perf/raw'))]
    rep = build_report(inputs)
    print_summary(rep)

    if not args.stdout:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        md = ROOT / args.md
        md.write_text(render_md(rep), encoding='utf8')
        print()
        print('已写：%s' % args.out)
        print('已写：%s' % args.md)

    if args.check and rep['summary']['hardCheckFailures']:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
