# 缺陷：**3 个泄漏的 Chrome 会话**持续占用 ~70% CPU，污染了 GPU 串行槽

**发现时刻**：2026-10-08 20:36Z（本机 03:36 前后，见时间线）
**方法**：锚定路径 `pgrep` + 逐个 `ps -o ppid=` 回溯 + CPU 采样（**未杀任何进程**）

---

## 一、事实（可复现）

```
$ pgrep -f 'Google Chrome.app/Contents/MacOS/Google Chrome --headless'
3 个

$ ps -o pid,ppid,etime,lstart -p 3487
 3487  1  01:13:48  Thu Oct  8 03:22:30 2026      ← PPID=1（孤儿）

逐进程：
  pid 3487  启动 03:22:30  user-data-dir=.../atlas-review-oxgd6a8y    CDP 客户端 0
  pid 14524 启动 03:26:05  user-data-dir=.../atlas-review-aqi3s23q    CDP 客户端 0
  pid 18278 启动 03:29:37  user-data-dir=.../atlas-review-fkrfn7ib    CDP 客户端 0

CPU 采样（各自的 GPU 子进程）：
  3492  → 23.0 / 24.2 / 22.1 %   （三次采样，持续空烧）
  14528 → 23.7 %   14536 → 20.0 %
  18310 → 21.0 %   18320 → 29.4 %
```

**⇒ 三个孤儿合计持续占用 **~70% CPU**，页面都是 `about:blank`，
**没有任何 CDP 客户端连它们**（`lsof -p <pid> | grep -c ESTABLISHED` = 0）。**

## 二、来源已定位到具体代码行

`user-data-dir` 的前缀是 `atlas-review-`，与 `tests/atlas_review_shots.py:120` 完全一致：

```python
self.ud = tempfile.mkdtemp(prefix='atlas-review-')
```

**该脚本第 147–156 行有 `close()`**（`Browser.close` → `killpg(SIGTERM)` → `rmtree`），
且第 359–360 行有 `finally: sess.close()`。

**⇒ 泄漏发生在这条清理路径**没有生效的情形**（进程崩溃 / 被 kill / `Browser.close` 未等到退出）。
三次泄漏、三个不同目录 ⇒ **不是偶发一次**。**

## 三、时间线：它**正好覆盖了** `w-gpu` 的 perf 运行

```
02:33:36   w-gpu 提交 ops:gpu-serial-check → 结论「实测 0 个 Chrome」  ← 那时确实干净
03:22:30   孤儿 #1 启动
03:26:05   孤儿 #2 启动
03:28:35   w-gpu 的 perf drive.log 开始写
03:29:37   孤儿 #3 启动
03:36:38   w-gpu 的 run-long.log
03:42:44   w-gpu 的 perf artifact 落盘（大奉稳态 35.97fps）
```

**⇒ `gpu-serial-check` 在 02:33 测到 0 个是**对的**；
但它**之后**自己（或同批脚本）泄漏了 3 个，而**没有任何后续检查**发现这件事。**

**⇒ 这解释了第 37 轮那个「同代码同档位差 35%」**：
- 我 00:12 / 00:21 测得 **48.48 / 52.18**（孤儿尚未启动）
- 它 03:28 测得 **35.97**（三个孤儿正在烧 ~70% CPU）

**⇒ 我第 37 轮的结论「不可复现」修正为**更准确的表述**：
**「其中一次测量被 **3 个泄漏浏览器（~70% CPU）** 污染」。**

## 四、为什么我**不杀**它们

| 理由 | 依据 |
|---|---|
| PPID=1 ⇒ **归属不明** | `artifacts/plan100/GPU-LOCK` 与 AGENTS.md 均明令「归属不明的目录/进程保持原状」 |
| 可能是 `w-gpu` 正在用的会话 | 虽然 CDP 客户端为 0，但我不掌握它的运行状态 |
| 杀进程是**不可逆**操作 | 若判断错，会破坏别人的测量 |

**⇒ 我的处置是：记录 + 定位到代码行 + 给出可复现的检测命令，交由协调方/GPU 租约持有者清理。**

## 五、给 GPU 槽的可执行建议（写进证据，不改 loop 工具）

1. **取锁前后各测一次 Chrome 数**（现在是只测一次）；
2. **测完对比**：若取锁前 N 个、测完仍 N 个以上 ⇒ 判定为泄漏并**报告 pid 与 user-data-dir**；
3. **锚定 `user-data-dir` 前缀**（`atlas-review-*`）比锚定 `--headless` 更准 ——
   因为泄漏的进程一定是某个具体脚本创建的。

**⇒ 判据应当是「跑完我自己的脚本后，Chrome 数是否回到跑之前」，而不是「跑之前有没有 Chrome」。**
**后者只能发现"别人占着"，发现不了"我自己泄漏了"。**

## 六、沉淀规则（第 37 条）

> **「测量前检查环境」不够，必须**测量后**再检查一次，并与测前对比。**
> `gpu-serial-check` 在 02:33 测得 0 个 Chrome —— **那一刻是对的**。
> 但它**之后**泄漏了 3 个，而**没有任何检查**发现。
> **⇒ 环境检查的正确形式是「前后差分」**：
> 「跑完我自己的脚本后，机器是否回到跑之前的状态」。
> **只测一次只能证明"我进场时干净"，证明不了"我退场时也干净"——而后者才是泄漏的定义。**

---

# 七、为什么最终**没有**执行回收（我做了检测器，但没扣扳机）

我写好了检测器 `/tmp/reap_leaked_chrome.py`（三条判据同时满足才回收），**它确认 3 个都可回收**：

```
pid 3487  ppid=1  CDP客户端=0  **可回收**
pid 14524 ppid=1  CDP客户端=0  **可回收**
pid 18278 ppid=1  CDP客户端=0  **可回收**
```

**但我查了一件事之后决定不执行**：

```
$ pgrep -fl 'worker.py --agent w-gpu'
86938  python3 … worker.py --agent w-gpu --loop 0 --timeout 2700 --idle-sleep 120 \
       --stream xgraph,perf,a11y
```

**⇒ `w-gpu` **仍然存活**，且它负责的正是 `perf` 与 `a11y` 两个流。
那 3 个 Chrome 的 `user-data-dir` 前缀（`atlas-review-`）正对应于它跑的性能/截图脚本。**

**⇒ 结论链**：
- 那 3 个**确实是孤儿**（PPID=1、无 CDP 客户端）—— **技术判据成立**；
- 但**它们的归属者是活着的** `w-gpu`，而它**可能仍在使用或即将复用**这些会话；
- **「可回收」是我的机器判据，而「该不该回收」是归属问题** —— 后者我无权单方面判定。

**⇒ 我停在这里，把检测器与证据交出去。** 这与本会话第 15 条规则一致：
*「定位到缺陷」≠「有权修它」* —— 在多会话共享的树上，
**输出可复现的定位 + 验收判据，而不是替别人做决定。**

## 八、交接内容（给 `w-gpu` 或协调方）

| 项 | 内容 |
|---|---|
| **检测命令** | `python3 /tmp/reap_leaked_chrome.py`（只报告） |
| **回收命令** | `python3 /tmp/reap_leaked_chrome.py --kill`（需归属者确认） |
| **三条判据** | ① `--headless` + `user-data-dir` 属已知前缀 ② `PPID==1` ③ **无 CDP 客户端** |
| **泄漏点** | `tests/atlas_review_shots.py:120`（`tempfile.mkdtemp(prefix='atlas-review-')`）；其 `close()` 在 :147，`finally` 在 :359 —— **脚本被 SIGKILL/超时时两者都不执行** |
| **影响** | 3 个孤儿合计 ~70% CPU ⇒ 直接压低 4K 帧率（35.97 vs 48.48/52.18） |
| **建议** | ① 跑完补一次 Chrome 计数并**与跑前对比**；② 锚定 `user-data-dir` 前缀而非 `--headless` |
