# 交接检查点 · 2026-10-16 · 主线程间歇性停摆（产品侧）

作者：主线程（本次会话）。时间：2026-10-16 14:10–15:00 CST。
**本文件是排查记录，不是质量签收，不提任何分数。** 与 `checkpoint_handoff-20261016_env-blockers.md`
同一批次；那份的「原因 3」结论已被本文件取代（该文件末尾有更正段）。

## 一句话

`--motion-e1` 与默认 story 路径都会**间歇性**卡住，成因是**页面主线程进入一个不终止的计算循环**
（不是崩溃、不是遮挡节流、不是服务、不是软件渲染、不是 headless 特有）。**本次未定位到具体行。**

## 先说清楚：本次**修好**的是什么（这些是确定的）

| # | 缺陷 | 证据 | 状态 |
|---|---|---|---|
| 1 | `sky_story_browser.py` 的 `RecordingWS` 无上限落盘 | 失控时 26 分钟 **78,218 帧 / 8.9 GB** | **已修** → 600 帧上限；实测 **600 帧 / 74 MB**（降 120×），到顶自动 `stopScreencast`；`recording.json` 自证 `frameCap/savedFrames/timelineOnlyFrames` |
| 2 | `headless.py::reap_orphans` 只扫**自己**的 `TMPDIR` | `run-with-storage.py` 每次运行轮换 TMPDIR（`<回滚点>/项目/…/<ts>-<pid>/临时/`），历史孤儿永不被收。实测漏下 **2 只、~850% CPU、load 22.8** | **已修** → 改为从 `ps -Aww` 发现；判据（属主已死才收）不变；`headless_health_contract` **38/38 通过** |
| 3 | `ready()` 90s 硬编码且超时无诊断 | 超时只抛一句 `graph readiness timeout`，逼下一轮重新二分 | **已修** → `CL_READY_TIMEOUT` 可覆盖 + 逐项报出缺哪一项 |
| 4 | `qa_cinema_wave02_capture.py:66` 的 CDP 超时硬编码 60s | 罗盘/晶冠的同步占用可超过它 | **已改** → `CL_CDP_TIMEOUT` 可覆盖（默认仍 60，不放宽） |

以上第 1–4 项都在受保护路径（`tests/`），**已持 GATE.lock** 修改，契约测试通过。

## 已证伪的假设（每条都有实验，别再重跑）

| 假设 | 实验 | 结论 |
|---|---|---|
| 产品在软件渲染下卡死 | 同一页面 `CL_GPU=1`（Metal）vs 默认 SwiftShader | **SwiftShader 下必然 >100s**，Metal 下多数秒级就绪 ⇒ 用 SwiftShader 的耗时判产品是**范式错误** |
| headless 特有 | `CL_WINDOWED=1` 弹真窗口 + Metal | **同样 CDP-BUSY 181.0s** ⇒ 不是 headless 特有 |
| 页面被遮挡/后台节流 | 探针读 `document.visibilityState` | `visible` / `hidden=false` 期间依然无响应 ⇒ 不是节流 |
| 服务慢 | `curl` 首页/JS/书籍 JSON | **0.001s / 200**，`serve.py` 是 `ThreadingHTTPServer` ⇒ 不是服务 |
| 外置盘慢到拖死 | `dd` 256MB 顺序写 | **111 MB/s**；小块写 1.3 ms/次 ⇒ 不是磁盘 |
| 录制端 I/O 拖慢通道 | 录制时间线 | 600 帧 / 10.60 s，**中位间隔 16.7 ms（60fps）**，零个 >250ms 间隔 ⇒ 录制端没有跟不上 |
| 先前的「渲染进程已死」猜想 | 卡死后**新开 WS 连接**求值 | 新连接同样超时 ⇒ 不是**旧连接**的问题，是页面/渲染进程本身 |

## 决定性证据（原始读数）

用 `/Volumes/资源库/我的资源/回滚点/临时/diag-thread-liveness.py` 采集
（独立 watchdog 线程每 5 s **新开一条 WS** 去求值，与超时那条连接无关）：

```
+  20.5s READY
+  20.7s watchdog 新连接求值 0.00s -> {'vs': 'visible', 'hid': False}
+  26.7s 即将触发： CLSky.setPlot(true)
+  26.7s 触发调用返回，耗时 0.03s          ← 触发本身不阻塞
+  34.7s watchdog 新连接求值 4.00s -> ERR:TimeoutError:timed out
+  43.7s … 4.00s -> ERR:TimeoutError
+  52.7s … 4.00s -> ERR:TimeoutError
+  61.7s … 4.00s -> ERR:TimeoutError
+  70.7s … 4.00s -> ERR:TimeoutError
```

要点：
- **`CLSky.setPlot(true)` 单独调用即可触发**（不依赖 `seekEventAt`）。观察 4 次，4 次都卡。
- 触发调用 **0.03 s 返回** ⇒ 肇事者是它**派生出去**的东西（rAF 循环 / 大 bake / 标签布局），不是这行本身。
- 卡住期间**新连接也进不去** ⇒ 主线程被占死或渲染进程 wedge。
- 测试进程被杀后，那只 Chrome **仍在烧满一个核**（实测 ~100–145% CPU） ⇒ 是**不终止的计算循环**，不是死锁。

另有一类同源现象：**启动阶段**本身也会偶发停摆（就绪探针 60 s / 150 s / 201 s 无返回）。
统计到现在：**快速就绪 4 次（3.9 s / 20.5 s / 23.9 s / 44.2 s 冷启），停摆 4 次**。⇒ 高度偶发。

## 复现方式（给下一轮）

```sh
# 裸页只测就绪（对照组，多数时候会过）
CL_GPU=1 python3 -B -s tests/headless.py '' --timeout 180 --url http://127.0.0.1:8765/

# 卡死 + 新连接存活性（关键工具；触发表达式可换）
python3 -B /Volumes/资源库/我的资源/回滚点/工具/run-with-storage.py --project /Users/carmen/Desktop/星系 -- \
  env CL_GPU=1 CL_BASE=http://127.0.0.1:8765 CL_DIAG_WAIT=120 \
  python3 -u -B /Volumes/资源库/我的资源/回滚点/临时/diag-thread-liveness.py 'CLSky.setPlot(true)'

# 抓主线程调用栈（已写好但**尚未拿到有效栈**：就绪阶段先卡住了，见下）
… python3 -u -B /Volumes/资源库/我的资源/回滚点/临时/diag-wedge-stack.py 'CLSky.setPlot(true)'
```

**跑之前务必先收割孤儿**（否则 load 会像 14:20 那次顶到 22.8，把结论带偏）：

```sh
for t in $(ps aux | grep -i "Google Chrome" | grep -v grep | grep -oE "castline-cdp-[0-9]+" | sort -u); do
  p=${t#castline-cdp-}; kill -0 $p 2>/dev/null || { d=$(ps aux|grep -i "Google Chrome"|grep -v grep|grep -oE "--user-data-dir=\S*$t"|head -1|sed 's/--user-data-dir=//'); pkill -9 -f -- "--user-data-dir=$d"; }
done
```

## 未完成的下一步（按优先级）

1. **拿到主线程栈**：`diag-wedge-stack.py` 已经写好，但三次尝试都因为**就绪阶段先卡住**而没走到抓栈那一步。
   下一步要么给就绪阶段更高的预算重试，要么**先加载好页面、再单独触发**（把抓栈与启动解耦）。
   拿到栈就能一击定位；拿不到就只能二分。
2. 有了栈之后，按栈定位到行，再判断是「本机性能问题」还是「真实逻辑缺陷」。
3. **不要**在没有栈的情况下盲改 shader / 动效代码 —— 会变成无法验证的改动。

## 工具位置（**尚未进 `tests/`**，避免再扩大受保护路径的改动面）

- `/Volumes/资源库/我的资源/回滚点/临时/diag-thread-liveness.py` —— 卡死探测（新连接存活性）
- `/Volumes/资源库/我的资源/回滚点/临时/diag-wedge-stack.py` —— 抓主线程栈 + CPU 采样
- `/Volumes/资源库/我的资源/回滚点/临时/run-stamped.sh` —— 给测试输出逐行打时间戳
- `/Volumes/资源库/我的资源/回滚点/临时/probe-*.log`、`diag-*.log` —— 本轮全部原始读数

这三个工具若被证明长期有用，应在**合并任务 + GATE.lock** 下正式落到 `tests/`，并各自补契约测试。

## 与用户诉求的关系

用户要的是三大图谱的电影级观感。**这次没推进观感改动**：
星盘（`setPlot(true)`）与启动路径都还会偶发停摆，此时改画面等于在动不了仪器的前提下施工。
但本轮把**仪器本身**从「看起来坏了」修到「能用，且能区分三种失败」——
并且给出了一个此前一直没被识别的**产品侧**问题。
