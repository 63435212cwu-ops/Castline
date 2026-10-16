#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 loop/state/out/perf_baseline-matrix.report.md。

叙述部分与表格部分**分开**：表格一律由 tables.build_tables() 从原始读数生成后嵌入，
人写的只有叙述。理由是本轮真实发生过一次手抄串列（把西游的数写进大奉列），
生成式可以从结构上消灭这一类错误。
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tables  # noqa: E402
import io, contextlib

OUT = HERE.parent / 'perf_baseline-matrix.report.md'   # HERE.parent = loop/state/out

HEAD = """# 性能基线矩阵 · 实测短报告（perf:baseline-matrix）

**产物**：`loop/state/out/perf_baseline-matrix.artifact.json`
**执行者**：`w-gpu`（唯一 GPU 租约持有者，`policy.json maxGpuLeases=1`）
**口径**：`docs/QUALITY.md` §04「初始工程门限」（桌面稳态 / 转场 / 长时 / 启动）

> §1 全部表格由 `loop/state/out/perf_baseline-matrix.raw/tables.py` 从原始读数**机械生成**
> （本文件由 `report.py` 装配），不是手抄 —— 手抄在本轮已出过一次串列错误。

---

## 0. 这次测了什么、用什么测的

| 项 | 值 |
|---|---|
| 真 GPU | `--headless=new --use-angle=metal`（`CL_GPU=1`），**不是** SwiftShader 软渲染 |
| 浏览器 | Google Chrome 155.0.8059.40 |
| 机器 | Mac16,10 · Apple M4（10 核 GPU，Metal 4）· macOS 26.2 · AC 供电 |
| 帧时口径 | rAF 帧间隔（真实墙钟 `performance.now()`），非 pump / 非 fixedDt |
| 分位数 | **合并后的原始帧间隔**重算；长窗口按 ≤25 s 分段（CDP WS 读超时 40 s），**段间不暂停渲染** |
| 长任务 | `PerformanceObserver('longtask')`，与帧间隔**分开**记 |
| 计数 | `renderer.info` 关 `autoReset`、在**一帧边界**累积整个 composer 的全部 pass |
| 档位 | 每阶段（含**每个长时窗口**）重新钉：视口 → `resize()` → `setBoost(true)/setDip(false)/setDegrade(0)` → 静置 → **回读 `quality` 校验**；不符即标 `tierMismatch` 且不参与结论 |
| 三书数据 | 真实缓存 sha256 见 artifact `books.*.dataSha256`（大奉 `9b676d70…` 10.3 MB / 西游 `df959d74…` 3.3 MB / 三国 `152e2a6e…` 5.6 MB） |
| 源码 | `js/core/scene-core.js 92d82dc7…`、`js/app.js 3342e65e…`、`index.html 079547a3…`（全文见 artifact `environment.sourceHashes`） |

**GPU 空闲判定用的是进程与租约，不是计时**（明令禁止用 `gl.finish()` 近零耗时证明空闲）：
`gpu-free-precheck.txt` 记录开工前 `pgrep -fl` 无第二个 headless/浏览器测试进程、
无第二份 `gpu:true` 租约，热与电源状态一并留档。

---

## 1. 分路径结果（**不混档位**；每格都带 drawingBuffer / degrade）

"""

TAIL = """
---

## 2. 瓶颈假设（本轮要回答的问题）

**假设 A（主）：瓶颈在「视图切换 / 展卷」这条样式重算与布局路径，不在 GPU 像素吞吐。**

1. 稳态 `longtask` = **0**、`gl.getError()` = **0**，但 P95 稳定落在 30–33 ms ——
   正好是 60 Hz 的**两帧**（33.3 ms）附近。这形态是**掉一帧/等 vsync**，不是 JS 卡死。
2. 稳态 fps 三书几乎相同（35.97 / 37.16 / 39.09），**与数据量 3.1× 的差异不相关**；
   而视图切换的冻结次数在三国最高（19/20）。「数据量变 3 倍 fps 不变」⇒ 瓶颈不由绘制量驱动。
3. 转场里最贵的是**视图切换**（P95 203–288 ms）与**剧情星盘**（P95 109–216 ms），
   两者都写 `body.dataset.atlasView`；`js/app.js` 自己的注释写明该属性
   「让 body 整棵子树失效（大奉整页样式 ~11 ms）」。断点落在**样式重算 + 布局**，
   与 `resize` 的 ~110–124 ms 量级一致。

**假设 B（次）：启动余量只对最大数据（大奉 1.9 s vs 门限 2 s）紧张。**

**明确不成立的**：不是「GPU 算力不够」——若是，三书 fps 应随数据量分层，实测没有；
也不是「主线程被长任务阻塞」——`longtask` 为 0。

> 假设 A 是**待复核的假设**，不是已证结论。建议复核抽测：同一本书上只改视图切换路径，
> 或用 `performance.measure` 把样式重算/布局/绘制**分离计时**，看 203–288 ms 是否随之下降。
> 本次**未做**该分离计时（属未验证）。

---

## 3. 与已知旧结论的关系（**不得互相替代**）

| 口径 | 实测 | 说明 |
|---|---|---|
| 长时原生 4K（**120 s 窗**，大奉，多窗） | **$LONGFPS fps**（P95 $LONGP95 ms） | 与旧结论「长时原生 4K 约 29 fps」**同量级、互相支持**；本次是 2 分钟窗，仍**不是** 30 分钟结论 |
| 20 s 稳态原生 4K | 35.97 / 37.16 / 39.09 fps | 短窗，**不得**替代长时结论 |
| **误把档位漂移当成绩**（本轮踩到并记录） | **59.98 fps** | 见下 |

⚠️ **本轮最重要的过程发现**：长时阶段首版跑出 **59.98 fps**，看似「长时也达标」——
回读档位才发现该窗跑在 **1440×900**（转场阶段最后一次 resize 把视口留在 1440×900）。
修正后同一本书、同一窗长、真正钉在 3840×2160 时是 **25.2 fps**。
这正是任务禁止的「混用分辨率」形态，而且它**只表现为一个好看的数字**。
修法已写进探针：每个长时窗口前重新钉档并回读校验，`tierOk=false` 的窗口带 `tierMismatch` 留档、不入账。

**因此本次不承诺稳定 60 fps**：原生 4K 长窗 $LONGFPS fps、20 s 短窗 36–39 fps，两者并列保留、互不替代。

---

## 4. 长时窗口（30 分钟路径）

按门限「30 分钟，每 5 分钟均值 ≥58 fps，无无界资源增长」：先跑完三书全部短路径，
再把剩余墙钟预算全部投给**最慢的大奉**，**每窗单独落盘**（`long-dafeng-w<i>.json`，逐窗 sha256 见 artifact
`books.dafeng.longWindowFiles`），**不做跨窗平均**。每窗 fps/P95/纹理/几何/DOM/heap 与
**档位校验列**见 §1.5 与 artifact `paths.long-30min`。

**资源趋势**：$RESOURCE

受任务 2700 s 硬超时限制，实际窗数**少于**门限要求的 6 个 5 分钟窗；
`long.stoppedEarly` 会如实写明「差几个窗、为什么停」，**不用短窗外推**。

---

## 5. remaining（没做/没把握的，不编）

1. **稳态窗口是 20 s，不是门限要求的连续 2 分钟**（长时预算优先给了 30 分钟路径）。
2. **30 分钟路径跑不满 6 个 5 分钟窗**（2700 s 硬超时）：实际窗数见 §1.5，停止原因见 `long.stoppedEarly`。
3. 长时窗口**只覆盖最慢的大奉**；西游/三国的 30 分钟曲线未采。
4. 未做**样式重算/布局/绘制的分离计时**，假设 A 的归属未拆开（假设本身待复核）。
5. `进入/退出/返回` 三行是被幂等调用稀释过的**下界**，未重测。
6. 未做**自适应档位（不钉档）**对照：本报告原生 4K 结论**全部是钉住最高档**测的。
7. 未测真机 Safari / 读屏（环境限制，与本任务无关）。

---

## 6. 会话期间的外部写入足迹（归因，不是猜测）

测量期间观察到 `index.html`（03:33:36）与 `serve.py`（03:33:30）的 mtime 落在本会话时间窗内。
**按写入足迹归因，本 agent 不是写入者**：

- 本 agent 的写入面只有 `loop/state/out/**`（提交记录的 `changes` 三项，全为 append-only）；
- 探针对页面只做 **HTTP 只读**访问（`Page.navigate` + `Runtime.evaluate`），不写仓库文件；
- 这两个文件相对 HEAD 有 **2147 行插入**（`git diff --stat`），属本工作树历史上持续存在的
  并行写入者范围 —— 与本任务无关，但会让「源码 hash 基线」在别的会话里对不上，
  故把动手时刻的 hash 记进 artifact `environment.sourceHashes` 以便区分。
"""


def build_tables():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        tables.main()
    return buf.getvalue()


def main():
    t = build_tables()
    # 长时资源趋势：只用实测窗口，词句由数据决定
    longp = json.loads((HERE.parent / 'perf_baseline-matrix.artifact.json').read_text('utf-8'))
    lw = ((longp.get('paths') or {}).get('long-30min') or {}).get('dafeng') or {}
    win = lw.get('perWindow') or []
    if win:
        f0, f1 = win[0].get('fps'), win[-1].get('fps')
        tex = [w.get('textures') for w in win]
        geo = [w.get('geometries') for w in win]
        heap = [w.get('heapMB') for w in win]
        res = ('%d 个窗口内 纹理 %s→%s、几何 %s→%s、heap %s→%s MB、fps %s→%s；'
               '本段时长不足以支撑「无无界资源增长」的结论，只能说明**在该时长内未见增长**。'
               % (len(win), tex[0], tex[-1], geo[0], geo[-1], heap[0], heap[-1], f0, f1))
        longfps = '%.1f' % f1 if f1 else 'n/a'
        longp95 = win[-1].get('p95')
    else:
        res = '本次未采到长时窗口。'
        longfps, longp95 = 'n/a', 'n/a'
    body = HEAD + t + TAIL.replace('$LONGFPS', longfps).replace('$LONGP95', str(longp95)).replace('$RESOURCE', res)
    OUT.write_text(body, 'utf-8')
    print(json.dumps({'saved': str(OUT), 'longWindows': len(win), 'longFps': longfps}, ensure_ascii=False))


if __name__ == '__main__':
    main()
