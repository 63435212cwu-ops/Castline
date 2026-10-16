# 跨会话持续运行的接续说明（给下一个会话 / 用户自己）

这不是「再开一个计划」，而是**把已经建好的环境接上排期**。
环境本体在 `loop/`，每次守护都是幂等的，重复跑不会重复开工。

---

## 零、先决条件：**先确认排期 agent 真的能跑**（2026-10-09 实测踩过）

> 这一节是拿一次真实事故换来的：排期**配好了、cron 到点也真的触发了、账本记 `status: ok`**，
> 但 agent 会话每次都立刻停在 `runState=incomplete`：
> **「当前是「自有」档，而本机没有这个智能体的账号，本轮已停止，没有任何请求发往平台。」**
> 也就是说 —— **排期账本的 `ok` 只证明「派发了」，不证明「干成了」**
> （与 E23「13 个 worker 全 alive、产出为 0」同形）。

**建排期之前先做这两步：**

1. **选一个本机真的可用的 agent**。线路档位取自 `agentRoutes[<agent>]`：
   `"direct"` = 自有（用你自己的账号）、`"relay"` = 平台（经平台，不耗你自己额度）。
   本机实测：`codex`（无账号，401/422）、`claude`（CLI 未登录）都走不通；
   **`dsh` 从命令行可用**，但经排期仍被「自有档无账号」挡住 ⇒ **必须先把线路切到「平台」**，
   或为该 agent 登录一个自有账号。界面原文：
   - 「平台：经由平台，不消耗你自己的账号额度」
   - 「本机没有可用的账号凭据，选「自有」会让请求直接停下」

2. **建好之后必须验证「有产出」，不能只看 `status: ok`**：

   ```sh
   python3 -c "import json,glob,os;rows=[(json.load(open(f)).get('updatedAt') or '',json.load(open(f)).get('agent'),(json.load(open(f)).get('runDetail') or '')[:110]) for f in glob.glob(os.path.expanduser('~/.mirasim/sessions/*/*/record.json')) if json.load(open(f)).get('workdir')=='/Users/carmen/Desktop/星系' and json.load(open(f)).get('runState')!='completed'];rows.sort(reverse=True);print(rows[0] if rows else '(无未完成排期会话 — 好现象)')"
   ```

   输出不是「(无未完成…)」而是带着 `runDetail` 的那一行 ⇒ **排期在空转**，先按第 1 步处理。
   守护轮自己也会报：`GUARD-REPORT.json` 的 `schedule.firesWithoutOutput` 与
   `GUARD-LOG.md` 的「**排期告警**」行（判据见 `selftest` 第 20a/20b 条）。

**另外记两条实测结论，免得后人重试**：`launchd` LaunchAgent 与 `cron` 都**读不到 `~/Desktop`**
（macOS TCC 限制；launchd 实测 `Operation not permitted`、`last exit code = 2`）。
所以本仓库（在 `~/Desktop` 下）**只能**靠 mirasim 排期或人工拉一次，没有第三种 OS 级兜底。

---

## 一、用 Mirasim 排期任务（推荐，服务端时钟，不依赖任何会话存活）

打开 Mirasim 的**定时任务**面板，新建一条：

- **名称**：`Castline 守护轮`
- **周期**：每 10 分钟（cron `*/10 * * * *`）
- **工作目录**：`/Users/carmen/Desktop/星系`
- **提示词**：把下面整段贴进去（它自带全部上下文，不依赖本会话）

```
你是 Castline 持续运行环境的守护轮。工作目录：/Users/carmen/Desktop/星系

执行（按顺序，全部用 bash）：

1. `cd /Users/carmen/Desktop/星系 && python3 -B -s loop/bin/sentinel.py --once --json`
   这一条会：回收死租约、把死掉的 worker 按 roster 拉起来（有当日重启上限）、
   统计真实进度、必要时补队列、做停滞检测、到点插入专家复核任务。

2. 读 `loop/state/GUARD-REPORT.json`，判断是否需要人工介入：
   - worker 显示 `dead(超出当日重启上限)` → 读 `loop/state/logs/<worker>.daemon.log` 末尾 50 行找原因；
   - `stall` 是停滞告警 → 读最近 3 个 `loop/state/out/REJECTED__*.json` 归纳拒绝原因；
   - `rejectedCount` 上升 → 有 agent 反复交不出合格证据，把原因写清楚。

3. 检查受保护文件是否被并行写入者改动：
   `git status --short | head -30` 与 `python3 tests/version_stamp.py --check`。
   注意：**漂移是常态**（本机历史上一直有第三方会话在改这些文件），
   不要回滚别人的代码，只如实记录。

4. 把本轮结论**追加**到 `loop/state/GUARD-LOG.md` 末尾，格式：
   `### <时间>` / `- 完成 x/y（拒绝 n）` / `- worker 状态` / `- 需要人看的` / `- 本轮判断`

纪律：
- 不要 `git checkout -- .` / `git reset --hard` / `git stash`。
- 不要杀别人的进程，不要为了让报告好看而放宽检查。
- 一切正常就简短报告「完成 x/y，worker n 个，无异常」——
  **不要为了显得在工作而编造发现**。

最后用一句话汇报：完成数、worker 数、有没有需要人处理的事。
```

排期建好后，**即使所有 worker 都死了、机器睡醒、本会话早已结束**，下一轮守护也会把它们拉回来。

## 二、不想建排期：常驻守护（已经起着了）

```sh
cd /Users/carmen/Desktop/星系
sh loop/run.sh watchdog      # 启动常驻守护（每 10 分钟一轮，后台，幂等）
sh loop/run.sh unwatch       # 停掉它
cat loop/state/WATCHDOG.json # 看它在不在、pid 是多少、什么时候起的
```

它用 `nohup` + 独立会话启动，**关掉终端也继续跑**；日志在 `loop/state/logs/watchdog.console.log`。
限制只有一个：机器重启、或系统清理后台进程之后它就没了 —— 这正是排期那条要补的位。

## 三、worker 会一直跑吗

会。worker 由 `sentinel.py` 用 `start_new_session=True` 拉起，是**独立会话进程**：

- 本会话结束 → worker 继续；
- 单个 worker 崩了 → 下一轮守护重新拉起（每 worker 每日重启上限 24 次，防止崩溃循环被掩盖）；
- 机器重启 / 全死光 → 排期任务那一轮会把 11 个 worker 全部拉回来。

## 四、停下来

```sh
cd /Users/carmen/Desktop/星系
sh loop/run.sh stop                      # 通知所有 worker 做完当前任务后退出
```
再到 Mirasim 定时任务面板暂停或删除 `Castline 守护轮`。

## 五、确认它真的在干活（不要只看进程）

```sh
sh loop/run.sh status                    # 队列/完成/租约/最近守护
ls -lt loop/state/out/ | head            # 真实产出（证据文件）
tail -f loop/state/logs/w-dafeng-0-read-*.log   # 某个 worker 正在读的原文
python3 loop/bin/loop.py stats           # done 数应该随时间长
```

**判断标准**：`done` 数在涨，且 `loop/state/out/` 里出现带 `sha256` 的提交。
进程活着但 `done` 不动 = 停滞，守护轮会在 3 轮后报停滞告警。
