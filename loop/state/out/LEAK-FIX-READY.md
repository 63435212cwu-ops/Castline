# 泄漏修复：**已备好 patch，但按纪律不直接改共享树**

**目标文件**：`tests/atlas_review_shots.py`（**受保护路径**）
**我的状态**：**未持 `GATE.lock`** ⇒ 不直接改，交 patch

---

## 一、泄漏点（已定位到行）

| 位置 | 内容 |
|---|---|
| `:120` | `self.ud = tempfile.mkdtemp(prefix='atlas-review-')` ← **孤儿目录的前缀来源** |
| `:147` | `Session.close()`：`Browser.close` → `killpg(SIGTERM)` → `rmtree` |
| `:359` | `run_viewport()` 的 `finally: sess.close()` |

**⇒ 清理逻辑存在，但 **SIGTERM/SIGKILL 会绕过 `finally`**。**
实测**三次泄漏、三个不同临时目录** ⇒ 不是偶发。

## 二、patch 的内容（`loop/state/out/q_atlas-review-leak.patch`，64 行）

1. **`_LIVE_SESSIONS` 注册表** + `_reap_all_sessions()`
2. **`_install_reapers()`**：`atexit.register(...)` + 为 `SIGTERM`/`SIGINT` 装处理器
   - 处理器先回收会话，再转交原有 handler
   - `signal.signal` 抛 `ValueError/OSError`（非主线程等）时**静默跳过**，不改既有行为
3. `run_viewport()` 里 `sess` 加入注册表，`finally` 中移除
4. `main()` 开头调用 `_install_reapers()`
5. **需新增 `import atexit`**（文件已有 `import signal`）

**⇒ patch 是**加性**的：不改既有逻辑，只在异常退出路径上补回收。**

## 三、验收判据（可机械执行）

| # | 判据 | 命令 |
|---|---|---|
| 1 | 跑完脚本后 Chrome 数回到跑之前 | `python3 /tmp/reap_leaked_chrome.py`（应报 0 个可回收） |
| 2 | **中断**后也不留孤儿 | 运行中 `kill -TERM <pid>`，再跑上面那条 |
| 3 | 既有行为不变 | `CL_GPU=1 python3 -B -s tests/atlas_review_shots.py --out /tmp/x` 仍返回 OK |

**反例（必须验）**：
- `kill -9` 仍会留孤儿（**SIGKILL 不可捕获**）⇒ 判据只能覆盖 SIGTERM/SIGINT；
  **⇒ 这正是 `/tmp/reap_leaked_chrome.py` 需要长期存在的原因** ——
  它覆盖"不可捕获的退出"这一类。

## 四、为什么我**不**自己应用这个 patch

| 理由 | 说明 |
|---|---|
| **`tests/` 是受保护路径** | AGENTS.md：只能在合并任务里改并持 `GATE.lock` |
| **我未持锁** | 我这一轮没有取锁，也不该为了改别人的测试文件去取 |
| **改动虽小但影响他人** | 该脚本是 GPU 槽的公共工具；改它需要归属者知情 |
| **但我把 patch 与验收判据都备好了** | 归属者可直接 `git apply`，或据此判断是否采纳 |

**⇒ 这正是第 15 条规则的应用：「定位到缺陷」≠「有权修它」；
但「有权修」也不等于「备好了 patch 就不管」—— 我把**定位 + patch + 判据 + 反例**四件都交出去。**

## 五、补充：不可捕获的退出只能靠**外部回收**

`kill -9` / 崩溃 / 断电留下的孤儿**无法由脚本自己清理**（没有代码在运行）。
**⇒ 两道防线缺一不可**：
1. **脚本内**（本 patch）：覆盖 SIGTERM/SIGINT/atexit
2. **脚本外**（`reap_leaked_chrome.py`）：覆盖 SIGKILL/崩溃，由**下一位取锁者**在取锁时执行

**⇒ 所以我在第 44 轮的建议要收紧为：
取锁时不仅"看有没有 Chrome"，而是**跑一次回收器并记录结果**。**
