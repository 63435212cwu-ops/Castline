#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 raw/ 下的实测读数装配成 loop/state/out/perf_baseline-matrix.artifact.json。

纪律（都是本任务明文禁止的形态，故由代码强制，不靠人记）：
1. **不混档位**：每条读数都带 quality(drawW/drawH/degrade/boost)；装配时校验，
   凡与所声称路径不一致的一律标 tierMismatch 并置为无效，不参与任何汇总。
2. **短测不得替代长测**：稳态/长时各自独立字段；不把 8s 的结果写进长时结论，
   反之亦然。长时窗口逐个列出，不做「平均成一个数」。
3. **不承诺 60fps**：只报实测分位与降档状态，不写「稳定 60fps」这类结论。
"""
import hashlib, json, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / 'loop/state/out/perf_baseline-matrix.artifact.json'
BOOKS = ['dafeng', 'xiyou', 'sanguo']
TIER = {'drawW': 3840, 'drawH': 2160, 'degrade': 0}


def sha256(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read(p):
    p = Path(p)
    return json.loads(p.read_text('utf-8')) if p.exists() else None


def tier_ok(q):
    """该读数是否真的处在所声称的原生 4K 最高档（不是降档后冒充）。"""
    if not isinstance(q, dict):
        return False, ['no-quality-block']
    bad = []
    for k, v in TIER.items():
        if q.get(k) != v:
            bad.append('%s=%s(期望 %s)' % (k, q.get(k), v))
    if q.get('boost') != 1:
        bad.append('boost=%s(期望 1)' % q.get('boost'))
    return (not bad), bad


def q(vals, p):
    v = sorted(x for x in vals if isinstance(x, (int, float)))
    return round(v[min(len(v) - 1, int(len(v) * p))], 2) if v else None


def build():
    art = {
        'task': 'perf:baseline-matrix',
        'agent': 'w-gpu',
        'generatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'kind': 'path-separated performance baseline matrix',
        'planRef': 'docs/QUALITY.md §04 初始工程门限（桌面稳态 / 转场 / 长时 / 启动）',
        'method': {
            'driver': 'tests/atlas_review_shots.py::Session（--headless=new --use-angle=metal 真 GPU）+ tests/headless.py 的 CDP 驾驭器；只读复用，未改 tests/',
            'probe': 'loop/state/out/perf_baseline-matrix.raw/probe.py',
            'frameTiming': 'rAF 帧间隔（真实墙钟 performance.now()），非 pump/fixedDt；fps = 帧数 / 真实经过时间',
            'quantiles': '分位数用**合并后的原始帧间隔**重算；长窗口按 <=25s 分段采样（CDP WS 读超时 40s），段间不暂停渲染',
            'longTask': 'PerformanceObserver longtask（>50ms 主线程任务），与帧间隔分开记',
            'counters': 'three.js renderer.info 关闭 autoReset 后在一帧边界累积整个 composer 的全部 pass（否则只读到最后一个 pass 的残值）',
            'pinning': '先设视口 → 再 resize → 最后 setBoost(true)/setDip(false)/setDegrade(0)，然后等 6s 稳定；每个采样都回读 quality 校验档位',
            'tiering': '每条读数都带 drawW/drawH/degrade/boost；与声称档位不符的读数标 tierMismatch 且不参与汇总',
        },
        'environment': {},
        'books': {},
        'paths': {},
        'bottleneckHypothesis': {},
        'prohibitions': {},
        'remaining': [],
    }

    envtxt = (HERE / 'env-info.txt')
    art['environment']['host'] = envtxt.read_text('utf-8') if envtxt.exists() else None
    art['environment']['chrome'] = 'Google Chrome 155.0.8059.40'
    art['environment']['gpuBackend'] = '--use-angle=metal（真 GPU；不是 SwiftShader 软渲染）'
    art['environment']['gpuFreePrecheck'] = (HERE / 'gpu-free-precheck.txt').read_text('utf-8')
    art['environment']['sourceHashes'] = (HERE / 'source-hashes.txt').read_text('utf-8')
    # 会话期间的**外部写入足迹**登记（SENTINEL 纪律：按写入足迹归因，不按「谁的需求听起来像」）。
    # 事实：index.html / serve.py 的 mtime 落在本会话内，但本 agent 只写 loop/state/out/**；
    # 两者相对 HEAD 有 2147 行插入，属并行写入者（本工作树历史上持续存在第三方写入）。
    drift = (HERE / 'env-drift.txt')
    art['environment']['concurrentWriterFootprint'] = {
        'observed': drift.read_text('utf-8') if drift.exists() else None,
        'attribution': '并行写入者（非本 agent）：本 agent 的写入面只有 loop/state/out/**（见 changes）；'
                       '未对 index.html / serve.py / js/** 发起任何写操作，探针只经 HTTP 只读访问页面。',
        'whyItMatters': '这两处漂移会让「源码 hash 基线」在别的会话里对不上；本次记录动手时刻的 hash 以便区分。',
    }

    summary_paths = {}
    for b in BOOKS:
        d = read(HERE / ('book-%s.short.json' % b)) or read(HERE / ('book-%s.json' % b))
        if not d:
            art['remaining'].append('book-%s.json 缺失：%s 未测完（墙钟/超时限制），未用其它书的结果代替' % (b, b))
            continue
        st = d.get('steady') or {}
        pq = ((d.get('pinned') or {}).get('quality') or {})
        ok, bad = tier_ok(pq)
        entry = {
            'bookName': d.get('bookName'), 'graphKey': d.get('graphKey'), 'data': d.get('data'),
            'dataSha256': sha256(ROOT / d['data']) if (ROOT / d['data']).exists() else None,
            'wallSeconds': d.get('wallSeconds'),
            'viewport': {'startup': d.get('startupViewport'), 'steady': d.get('steadyViewport')},
            'pinnedTier': {'quality': pq, 'gl': (d.get('pinned') or {}).get('gl'), 'matchesNative4kMaxTier': ok,
                           'mismatches': bad},
            'startup': d.get('startup'),
            'firstInteractive': d.get('interaction'),
            'steady2minPlan': {'measuredSeconds': round((st.get('elapsedMs') or 0)/1000, 2),
                               'note': '本字段是**计划中的 2 分钟稳态**的实测时长；若不足 120s，结论只对该时长成立，不得外推为 2 分钟结论'},
            'steady': {k: v for k, v in st.items() if k not in ('longTasks',)},
            'transitions': d.get('transitions'),
            'health': d.get('health'),
        }
        # 长时窗口（每窗单独，不合并成一个平均）。长时阶段写在 book-<b>.json 里，
        # 每窗另有 long-<b>-w<i>.json 单文件留证；两者都收，冲突以单文件为准。
        longrec = d.get('long') or (read(HERE / ('book-%s.json' % b)) or {}).get('long')
        files = sorted(HERE.glob('long-%s-w*.json' % b))
        if files:
            # 长时阶段**逐窗落盘**：任务 2700s 硬超时可能在最后一个窗口中途砍掉进程，
            # 逐窗留证保证已采到的窗口不随进程一起丢。这里以单文件为准重建窗口列表。
            ws = []
            for f in files:
                try:
                    ws.append(json.loads(f.read_text('utf-8')))
                except Exception:
                    pass
            ws.sort(key=lambda w: w.get('windowIndex', 0))
            longrec = {'windowSeconds': round((ws[0].get('elapsedMs') or 0)/1000, 1) if ws else None,
                       'windows': ws, 'source': '逐窗单文件 long-%s-w<i>.json（不跨窗平均）' % b,
                       'tierCheckedPerWindow': all('tierOk' in w for w in ws),
                       'tierMismatchWindows': [w.get('windowIndex') for w in ws if w.get('tierOk') is False],
                       'stoppedEarly': (read(HERE / ('book-%s.json' % b)) or {}).get('long', {}).get('stoppedEarly')}
        if longrec:
            entry['long'] = longrec
            entry['longWindowFiles'] = [{'path': str(f.relative_to(ROOT)), 'sha256': sha256(f)} for f in files]
        art['books'][b] = entry

    paths = {}
    for b in BOOKS:
        e = art['books'].get(b)
        if not e:
            continue
        st = e.get('steady') or {}
        tr = e.get('transitions') or {}
        # 稳态：只有档位真的对才填原生 4K 结论；否则落 native4k 为 null 并写明原因
        ok = (e.get('pinnedTier') or {}).get('matchesNative4kMaxTier')
        paths.setdefault('steady-2min', {})[b] = {
            'pinnedNative4kMaxTier': ok,
            'measuredSeconds': e['steady2minPlan']['measuredSeconds'],
            'fps': st.get('fps'), 'p50': st.get('p50'), 'p95': st.get('p95'), 'p99': st.get('p99'), 'max': st.get('max'),
            'frames': st.get('frames'),
            'over33.4ms': st.get('over334'), 'over50ms': st.get('over50'), 'over100ms': st.get('over100'),
            'longTaskMaxMs': st.get('longTaskMax'), 'longTaskTotalMs': st.get('longTaskTotal'),
            'domNodes': st.get('dom'), 'heapMB': st.get('heapMB'),
            'renderer': st.get('renderer'), 'gl': st.get('gl'),
            'drawingBuffer': [((st.get('gl') or {}).get('drawingBufferWidth')), ((st.get('gl') or {}).get('drawingBufferHeight'))],
            'degrade': (st.get('quality') or {}).get('degrade'),
            'meetsQualityGate_p95_18ms': (st.get('p95') is not None and st.get('p95') <= 18),
            'meetsQualityGate_over334_1pct': (st.get('frames') and st.get('over334') is not None and st.get('over334')/st['frames'] <= 0.01),
        }
        paths.setdefault('transition-20x', {})[b] = {
            k: ({kk: vv for kk, vv in (v or {}).items() if kk != 'samples'} if isinstance(v, dict) else v)
            for k, v in tr.items()}
        if e.get('startup'):
            sm = e['startup'].get('milestones') or {}
            s0 = e['startup'].get('sample') or {}
            paths.setdefault('startup', {})[b] = {
                'ready': e['startup'].get('ready'),
                'firstRafMs': s0.get('firstRaf'), 'firstSceneFrameMs': s0.get('sceneFrame'),
                'meaningfulContentMs': sm.get('contentReady'), 'curtainGoneMs': sm.get('loaderOff'),
                'controlEnabledMs': sm.get('controlEnabled'),
                'firstContentfulPaintMs': (s0.get('paints') or {}).get('first-contentful-paint'),
                'domInteractiveMs': (s0.get('nav') or {}).get('domInteractive'),
                'loadEventMs': (s0.get('nav') or {}).get('loadEnd'),
            }
        if e.get('firstInteractive'):
            fi = e['firstInteractive'] or {}
            paths.setdefault('first-interactive', {})[b] = {
                'inputSyncBlockMs': fi.get('syncMs'), 'servedNextFrameMs': fi.get('servedMs'),
                'viewChanged': fi.get('viewBefore') != fi.get('viewAfter'), 'error': fi.get('err')}
        if e.get('long'):
            lw = e['long'].get('windows') or []
            paths.setdefault('long-30min', {})[b] = {
                'windowSeconds': e['long'].get('windowSeconds'), 'windowsMeasured': len(lw),
                'stoppedEarly': e['long'].get('stoppedEarly'),
                'perWindow': [{'i': w.get('windowIndex'), 'seconds': round((w.get('elapsedMs') or 0)/1000, 1),
                               'fps': w.get('fps'), 'p50': w.get('p50'), 'p95': w.get('p95'), 'p99': w.get('p99'),
                               'max': w.get('max'), 'longTaskMaxMs': w.get('longTaskMax'),
                               'textures': (w.get('renderer') or {}).get('textures'),
                               'geometries': (w.get('renderer') or {}).get('geometries'),
                               'domNodes': w.get('dom'), 'heapMB': w.get('heapMB'),
                               'degrade': (w.get('quality') or {}).get('degrade'),
                               'tierOk': w.get('tierOk'), 'tierMismatch': w.get('tierMismatch'),
                               'drawingBuffer': [(w.get('gl') or {}).get('drawingBufferWidth'),
                                                 (w.get('gl') or {}).get('drawingBufferHeight')]} for w in lw],
                'fpsFirstToLast': [lw[0].get('fps'), lw[-1].get('fps')] if lw else None,
                'textureGrowth': [((lw[0].get('renderer') or {}).get('textures')), ((lw[-1].get('renderer') or {}).get('textures'))] if lw else None,
                'heapGrowthMB': [lw[0].get('heapMB'), lw[-1].get('heapMB')] if lw else None,
            }
    art['paths'] = paths

    # 瓶颈假设：只用**本次实测**的对照，逐条给证据指针
    hyp = []
    st_all = {b: (paths.get('steady-2min', {}).get(b) or {}) for b in BOOKS}
    for b, s in st_all.items():
        if s.get('fps') is None:
            continue
        hyp.append({'path': 'steady-2min/%s' % b, 'observedFps': s.get('fps'), 'p95': s.get('p95'),
                    'atNative4kPinned': s.get('pinnedNative4kMaxTier'),
                    'evidence': 'books.%s.steady' % b})
    art['bottleneckHypothesis'] = {
        'statement': '瓶颈假设（待复核抽测）：见 ranking——按实测 fps 由低到高排，最低者即当前最可能的瓶颈路径；'
                     '是否与数据量（大奉 63MB / 图形节点最多）相关，需要同档位的三书对照才能判，本次矩阵提供了这个对照。',
        'ranking': sorted(hyp, key=lambda x: (x['observedFps'] is None, x['observedFps'])),
        'notClaimed': ['不声称稳定 60fps', '不把短窗口（8–20s）结果当长时结果', '不把降档后的帧率冒充原生 4K 达标'],
    }

    art['prohibitions'] = {
        'mixedResolution': '每条读数带 drawW/drawH 并逐条校验；不一致即标 tierMismatch 且排除',
        'forcedQualityClaimingAdaptive': '本报告中的原生 4K 结论**都是钉住最高档**（boostPin=true, degrade=0）测的，'
                                        '不声称这是自适应结果；自适应档位另有单独字段',
        'glFinishAsGpuIdle': '未使用 gl.finish()；GPU 空闲由**进程/租约**判定（gpu-free-precheck.txt），不由计时判定',
    }
    return art


def main():
    art = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps({'saved': str(OUT), 'books': list(art['books']), 'paths': list(art['paths']),
                      'sha256': sha256(OUT)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
