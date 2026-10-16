#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 raw 读数生成报告的**表格部分**（机械生成，杜绝手抄串行）。

用法：python3 loop/state/out/perf_baseline-matrix.raw/tables.py > /tmp/tables.md
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOOKS = [('dafeng', '大奉打更人'), ('xiyou', '西游记'), ('sanguo', '三国演义')]


def load(b):
    for name in ('book-%s.short.json' % b, 'book-%s.json' % b):
        p = HERE / name
        if p.exists():
            return json.loads(p.read_text('utf-8'))
    return None


def main():
    data = {b: load(b) for b, _ in BOOKS}
    print('### 1.1 启动（1440×900 dsf=1，冷启动一次导航）\n')
    print('| 书 | 首次 rAF | 场景首帧 | 有意义内容 | 幕布消失 | 控件可用 | FCP |')
    print('|---|---|---|---|---|---|---|')
    for b, zh in BOOKS:
        d = data[b]
        if not d:
            print('| %s | 未测 | | | | | |' % zh); continue
        s = (d['startup'].get('milestones') or {})
        s0 = d['startup'].get('sample') or {}
        f = lambda v: ('%d ms' % round(v)) if isinstance(v, (int, float)) else 'null'
        print('| %s | %s | %s | **%s** | %s | %s | %s |' % (
            zh, f(s0.get('firstRaf')), f(s0.get('sceneFrame')), f(s.get('contentReady')),
            f(s.get('loaderOff')), f(s.get('controlEnabled')),
            f((s0.get('paints') or {}).get('first-contentful-paint'))))

    print('\n### 1.2 稳态（钉住原生 3840×2160、degrade 0、boost 1）\n')
    print('| 书 | 窗口 | fps | P50 | P95 | P99 | max | >33.4 ms | 长任务 max | DOM | heap | 纹理/几何/程序 |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|')
    for b, zh in BOOKS:
        d = data[b]
        if not d:
            print('| %s | 未测 | | | | | | | | | | |' % zh); continue
        st = d.get('steady') or {}
        r = st.get('renderer') or {}
        sec = '%.0f s' % round((st.get('elapsedMs') or 0)/1000)
        print('| %s | %s | **%.2f** | %s | %s | %s | %s | %d/%d (%.1f%%) | %s ms | %s | %s MB | %s / %s / %s |' % (
            zh, sec, st.get('fps') or 0, st.get('p50'), st.get('p95'), st.get('p99'), st.get('max'),
            st.get('over334') or 0, st.get('frames') or 0,
            100.0*(st.get('over334') or 0)/max(1, st.get('frames') or 1),
            st.get('longTaskMax'), st.get('dom'), st.get('heapMB'),
            r.get('textures'), r.get('geometries'), r.get('programs')))

    print('\n### 1.3 转场 20 次（同 4K 档位）\n')
    print('| 路径 | ' + ' | '.join('%s sync P95 / 下帧 P95 / >100 ms' % zh for _, zh in BOOKS) + ' |')
    print('|---|' + '---|'*len(BOOKS))
    kinds = ['enter', 'exit', 'view', 'plot', 'quality', 'return']
    labels = {'enter': '进入展卷', 'exit': '退出展卷', 'view': '视图切换', 'plot': '剧情星盘',
              'quality': '质量切换', 'return': '返回'}
    for k in kinds:
        cells = []
        for b, _ in BOOKS:
            d = data[b]
            v = ((d or {}).get('transitions') or {}).get(k) if d else None
            if not v or not v.get('nextFrameMs'):
                cells.append('未测'); continue
            cells.append('%s / **%s** / %s' % (v['syncMs']['p95'], v['nextFrameMs']['p95'], v['freezesOver100']))
        print('| %s | %s |' % (labels[k], ' | '.join(cells)))
    cells = []
    for b, _ in BOOKS:
        d = data[b]
        v = ((d or {}).get('transitions') or {}).get('resize') if d else None
        cells.append('%s mean / %d wrong' % (v['wallMs']['mean'], len(v['wrongSize'])) if v else '未测')
    print('| resize（CDP） | %s |' % ' | '.join(cells))

    print('\n### 1.4 每书转场明细（原始读数，供复核直读）\n')
    for b, zh in BOOKS:
        d = data[b]
        if not d: continue
        print('**%s**\n' % zh)
        print('| 路径 | reps | sync P50/P95/max | 下帧 P50/P95/max | >100 ms | 错误 |')
        print('|---|---|---|---|---|---|')
        for k in kinds + ['resize']:
            v = (d.get('transitions') or {}).get(k) or {}
            if k == 'resize':
                w = v.get('wallMs') or {}
                print('| resize | %s | %s/%s/%s | — | — | %d |' % (v.get('reps'), w.get('p50'), w.get('p95'), w.get('max'), len(v.get('glErrors') or [])))
                continue
            sm, nf = v.get('syncMs') or {}, v.get('nextFrameMs') or {}
            print('| %s | %s | %s/%s/%s | %s/%s/%s | %s | %s |' % (
                labels[k], v.get('reps'), sm.get('p50'), sm.get('p95'), sm.get('max'),
                nf.get('p50'), nf.get('p95'), nf.get('max'), v.get('freezesOver100'), (v.get('errors') or [])))

    print('\n### 1.5 长时窗口（每窗单独，不做跨窗平均）\n')
    for b, zh in BOOKS:
        d = data[b]
        lg = (d or {}).get('long') if d else None
        # 长时阶段是**逐窗落盘**的（long-<book>-w<i>.json），因为任务 2700s 硬超时可能
        # 在最后一个窗口中途砍掉：逐窗留证保证已采到的窗口不随进程一起丢。
        files = sorted(HERE.glob('long-%s-w*.json' % b))
        if files:
            ws = [json.loads(f.read_text('utf-8')) for f in files]
            lg = lg or {'windowSeconds': ws[0].get('elapsedMs', 0)/1000, 'windows': ws}
            lg = dict(lg); lg['windows'] = ws
        if not lg:
            print('- **%s**：本次未采到长时窗口。' % zh); continue
        ws = lg.get('windows') or []
        print('**%s**（窗口 %ss，实测 %d 窗）\n' % (zh, lg.get('windowSeconds'), len(ws)))
        print('| 窗 | 秒 | 档位校验 | drawingBuffer | fps | P50 | P95 | P99 | max | >33.4 ms | 长任务 max | 纹理 | 几何 | DOM | heap MB |')
        print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
        for w in ws:
            r = w.get('renderer') or {}
            gl = w.get('gl') or {}
            pt = (w.get('pinnedTier') or {}).get('quality') or {}
            tier = ('✅ 4K/deg0/boost1' if w.get('tierOk') else
                    ('❌ ' + json.dumps(w.get('tierMismatch'), ensure_ascii=False) if w.get('tierMismatch')
                     else '未校验(drawW=%s,degrade=%s,boost=%s)' % (pt.get('drawW'), pt.get('degrade'), pt.get('boost'))))
            print('| %s | %.0f | %s | %sx%s | %s | %s | %s | %s | %s | %s/%s | %s | %s | %s | %s | %s |' % (
                w.get('windowIndex'), (w.get('elapsedMs') or 0)/1000, tier,
                gl.get('drawingBufferWidth') or pt.get('drawW'), gl.get('drawingBufferHeight') or pt.get('drawH'),
                w.get('fps'), w.get('p50'), w.get('p95'), w.get('p99'), w.get('max'),
                w.get('over334'), w.get('frames'), w.get('longTaskMax'), r.get('textures'), r.get('geometries'),
                w.get('dom'), w.get('heapMB')))
        if lg.get('stoppedEarly'):
            print('\n停止原因：%s' % json.dumps(lg['stoppedEarly'], ensure_ascii=False))


if __name__ == '__main__':
    main()
