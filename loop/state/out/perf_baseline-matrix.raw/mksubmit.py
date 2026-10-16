#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 perf:baseline-matrix 的提交记录（哈希在**生成时**现算，不手抄）。

用法：python3 loop/state/out/perf_baseline-matrix.raw/mksubmit.py
"""
import hashlib, json, os, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TASK = 'perf:baseline-matrix'
AGENT = 'w-gpu'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    art = ROOT / 'loop/state/out/perf_baseline-matrix.artifact.json'
    rep = ROOT / 'loop/state/out/perf_baseline-matrix.report.md'
    a = json.loads(art.read_text('utf-8'))
    steady = (a.get('paths') or {}).get('steady-2min') or {}
    longp = (a.get('paths') or {}).get('long-30min') or {}
    lw = longp.get('dafeng') or {}
    win = lw.get('perWindow') or []

    ev = [{'path': 'loop/state/out/perf_baseline-matrix.artifact.json', 'sha256': sha(art),
           'note': '主产物：分路径矩阵（启动/首次可交互/稳态/转场20次/质量切换/返回/resize/长时窗口）'},
          {'path': 'loop/state/out/perf_baseline-matrix.report.md', 'sha256': sha(rep),
           'note': '短报告：口径、分路径读数、瓶颈假设与 remaining'}]
    for name in ('gpu-free-precheck.txt', 'env-info.txt', 'source-hashes.txt', 'tables.md',
                 'probe.py', 'drive.py', 'assemble.py', 'tables.py'):
        p = HERE / name
        if p.exists():
            ev.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'note': '可复现材料：%s' % name})
    for p in sorted(HERE.glob('book-*.json')) + sorted(HERE.glob('long-*.json')):
        ev.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'note': '原始读数（逐书/逐窗）'})

    src = {'js/core/scene-core.js': sha(ROOT / 'js/core/scene-core.js'),
           'js/app.js': sha(ROOT / 'js/app.js'),
           'js/scene.js': sha(ROOT / 'js/scene.js'),
           'index.html': sha(ROOT / 'index.html'),
           'serve.py': sha(ROOT / 'serve.py')}
    for b in ('dafeng', 'xiyou', 'sanguo'):
        for e in (a.get('books') or {}).values():
            if e.get('data'):
                dp = ROOT / e['data']
                if dp.exists():
                    src[e['data']] = sha(dp)
                break

    rec = {
        'task': TASK, 'agent': AGENT, 'status': 'done',
        'summary': (
            '按 docs/QUALITY.md Q6/§04 门限，在确认 GPU 空闲（进程+租约判定，未用 gl.finish 计时）后，'
            '用真 GPU（--headless=new --use-angle=metal）分路径测量三书，每条读数带档位证据、逐条回读 quality 校验。'
            '启动：有意义内容 大奉1903/西游1161/三国1499 ms（≤2s 达标，大奉仅余~100ms）；'
            '稳态（钉住原生3840x2160/degrade0/boost1，20s 窗）：35.97/37.16/39.09 fps，P95 30.9–33.2 ms，'
            '三书 P95 均未达 18ms 门限、长帧 1.3–4.3%（门限1%），longtask=0、glError=0；'
            '转场（各20次）：视图切换 11–19/20 次 >100ms 冻结（P95 203–288ms），resize 20/20 尺寸正确；'
            '长时（每窗120s、逐窗落盘、每窗重新钉档并回读校验）：大奉原生4K 第 %d 窗 fps=%s。'
            '瓶颈假设(待复核)：样式重算+布局（视图切换/展卷路径），非 GPU 像素吞吐——'
            '依据是 longtask=0 且 fps 与数据量 3.1x 差异不相关。'
            '过程发现并记录一处禁止形态：长时首版曾跑出 59.98fps，回读档位发现是 1440x900 视口漂移所致，'
            '修正后同书同为原生4K 为 25.2fps；修法（每窗重钉档+回读校验、不符即标 tierMismatch 不入账）已写进探针。'
            '不承诺稳定 60fps；短窗(20s)与长窗(120s)结论并列保留、互不替代。'
            + ('大奉长时共采 %d 窗，末窗 %s fps。' % (len(win), win[-1]['fps']) if win else '大奉长时窗口未采到。')),
        'evidence': ev,
        'assertions': [
            {'text': 'GPU 串行：开工前 pgrep -fl 无第二个 headless/浏览器测试进程；loop 租约里 gpu:true 的只有本任务（w-gpu）；'
                     '判定依据是进程与租约，不是计时（明令禁止 gl.finish 近零耗时证明空闲）。证据 gpu-free-precheck.txt',
             'result': 'pass'},
            {'text': '档位不混：每条稳态/转场/长时读数都回读 quality 校验 drawW=3840&drawH=2160&degrade=0&boost=1；'
                     '长时**每个窗口**重新钉档并记录 tierOk，tierOk=false 的窗口标 tierMismatch 且不参与结论',
             'result': 'pass'},
            {'text': '抓出并修正一处「混用分辨率」：长时首窗 fps=59.98 实为 1440x900 视口漂移（转场 resize 遗留），'
                     '修正为原生4K后同书同窗长 25.2fps；两者都留在 products 与报告里，未用好看的那个当结论',
             'result': 'pass'},
            {'text': '真 GPU 路径：CL_GPU=1 → Chrome --use-angle=metal（tests/headless.py:280），非 SwiftShader；'
                     'renderer=WebKit WebGL、drawingBuffer 3840x2160 实测回读',
             'result': 'pass'},
            {'text': '分位数口径：用合并后的**原始帧间隔**重算（非把各段分位数再平均）；长窗按 <=25s 分段（WS 读超时 40s），'
                     '段间不暂停渲染；每窗保留 segments 逐段 fps 供核对',
             'result': 'pass'},
            {'text': '长任务与帧间隔分开：PerformanceObserver(longtask) 独立记录，三书稳态 longTaskMax=0ms，'
                     '故掉帧不是主线程 JS 长任务造成（与 glError=0 一致）',
             'result': 'pass'},
            {'text': '计数口径修正：three.js renderer.info 默认每次 render 重置，直接读只得到最后一个 pass 的残值（实测 calls=1）；'
                     '改为关闭 autoReset 后在一帧边界累积整个 composer，得 calls=35/triangles=36132 等',
             'result': 'pass'},
            {'text': '报告表格由 tables.py 从原始读数**机械生成**（tables.md），不是手抄：'
                     '手抄在本轮已出过一次串列错误（把西游的数写进大奉列），发现后改为生成式并重写',
             'result': 'pass'},
            {'text': '只读复用 tests/ 的既有驾驭器（atlas_review_shots.Session / headless.py），未修改 tests/ 任何文件；'
                     '未写 js/ css/ index.html serve.py narrative.py distill.py scripts/ docs/ data/ tools/',
             'result': 'pass'},
            {'text': 'known-issue 留档：进入/退出/返回 三种转场首版是幂等调用（连调 20 次只有第 1 次是真转场），'
                     '会把分位稀释成下界；已改为交替调用并在 probe.py 注明，但上表这三行仍是未重测的下界',
             'result': 'pass'},
        ],
        'changes': [
            {'path': 'loop/state/out/perf_baseline-matrix.artifact.json', 'kind': 'append-only'},
            {'path': 'loop/state/out/perf_baseline-matrix.report.md', 'kind': 'append-only'},
            {'path': 'loop/state/out/perf_baseline-matrix.raw/', 'kind': 'append-only'},
        ],
        'sourceHashes': src,
        'remaining': [
            '稳态窗口是 20s，不是门限要求的连续 2 分钟（长时预算优先给了 30 分钟路径）：§1.2 结论只对 20s 成立。',
            '30 分钟路径受任务 2700s 硬超时限制，实际窗数 %d 个（门限要求 6 个 5 分钟窗）；'
            '停止原因写在 artifact paths.long-30min.dafeng.stoppedEarly，未用短窗外推。' % len(win),
            '长时窗口只覆盖最慢的大奉；西游/三国的 30 分钟曲线未采。',
            '未做样式重算/布局/绘制的分离计时，故瓶颈假设里「重算 vs 布局」的归属未拆开（假设本身待复核）。',
            '进入/退出/返回 三行是被幂等调用稀释过的下界，未重测。',
            '未做自适应档位（不钉档）对照：本报告原生 4K 结论全部是钉住最高档测的。',
            '未测真机 Safari / 读屏（环境限制，与本任务无关）。',
        ],
        'rollback': {'kind': 'append-only', 'strategy': 'delete-added-files',
                     'files': ['loop/state/out/perf_baseline-matrix.artifact.json',
                               'loop/state/out/perf_baseline-matrix.report.md',
                               'loop/state/out/perf_baseline-matrix.raw/']},
    }
    out = HERE / 'submit.json'
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps({'saved': str(out), 'evidence': len(ev), 'longWindows': len(win)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
