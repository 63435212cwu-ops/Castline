# Castline 持续运行环境（loop/）

这是一套「让计划在没人盯着的时候也能一直往前推」的环境。
它不是又一份计划书 —— 计划书已经证明过会退化成模板膨胀（13.6MB / 1694 条标题 / 实际只有 8 种）。
这里是**状态文件 + 队列 + 租约 + 守护轮**，所有状态都能用 `cat` 看、用 `git` 对账。

## 三十秒上手

```sh
cd /Users/carmen/Desktop/星系

sh loop/bin/run-supervisor.sh                        # ★先起监督者：保证守护主进程死了会自动回来
python3 -B -s loop/bin/loop.py stats                 # 现在有什么、做完多少
python3 -B -s loop/bin/loop.py next --agent me       # 下一个该做的任务（不占用）
python3 -B -s loop/bin/sentinel.py --once            # 跑一轮守护（回收死租约 + 拉起 worker + 补队列）
tail -f loop/state/logs/supervisor.log               # 监督者：有没有把守护主进程拉回来
tail -f loop/state/GUARD-LOG.md                      # 守护轮历史
tail -f loop/state/logs/<worker>.daemon.log          # 某个 worker 在干什么
```

## 为什么这么设计（每条都对应一次真实事故）

| 设计 | 换来的教训 |
|---|---|
| **状态即文件**，没有中央数据库 | 进程被 kill、机器重启都不需要恢复逻辑；`loop/state/` 直接可读可 diff |
| **文件级租约**（`os.mkdir` 原子抢锁） | 曾经两个 agent 并行改 `js/sky/sky-shell-player.js`，accept 读到半个文件，报出 `scrubDown is not defined` 这种**看起来像真缺陷**的假缺陷 |
| **通道（lane）串行、跨通道并行** | 并行度来自「不同原文区间」，不是「多叫几个 agent」。同一条线按原文顺序推进，保持阅读连续性 |
| **提交机器校验** | 计划100 记下 6 次虚假声称（源码未改/契约未插/gaps 写空/数字放大 3 倍）。所以证据必须存在、哈希必须对得上，人说的不算 |
| **复核者不能是原提交者** | 自签不算复核；脚本会拒绝 |
| **反向验证写进复核契约** | 只查「已写项对不对」结构性地发现不了遗漏；必须问「这一段里还漏了什么」 |
| **受保护路径不许在共享树改** | 工作树里有 700+ 行未提交的真实改动，又是多 agent 共用；写回只能走追加式 + 合并任务 + `GATE.lock` |
| **worker 不建 git worktree** | HEAD 是 10-04 的，worktree 里是**过时源码**；在过时代码上得出的结论和用户看到的页面不是一回事 |

## 目录

```
loop/
├── bin/
│   ├── loop.py       队列/租约/提交/复核/回收/统计（唯一状态写入者）
│   ├── build_plan.py 稀疏索引 → 稠密任务生成
│   ├── worker.py     常驻 worker：领任务 → 起 dsh agent → 校验提交 → 循环
│   ├── sentinel.py   守护轮：回收/拉起/补队列/停滞告警/专家复核触发
│   ├── supervisor.py 监督者：守护主进程死了就把它拉回来（E37）
│   └── run-supervisor.sh  幂等启动监督者（nohup + disown）
├── ROLES/            角色契约（agent 启动时读的第一份文件）
│   ├── READER.md         原文精读
│   ├── VERIFIER.md       独立反向复核
│   ├── PUBLISHER.md      发布（追加式写回）
│   ├── SENTINEL.md       运营/守护
│   ├── EXPERT-REVIEW.md  跨域专家评审
│   └── EDITOR.md         文档与交付
├── queue/*.jsonl     任务定义（read / publish / ops / env / expert）
└── state/            index.json（稀疏索引）、leases/、out/（证据）、logs/、policy.json
```

## 队列不是一次铺满的

`build_plan.py` 从**稀疏索引**（1133 个真实原文单元 / 608 万字 / 三本书的版本哈希）**按需生成**任务：

```sh
python3 -B -s loop/bin/build_plan.py --index          # 刷新索引（读真实缓存与 narrative.chapter_spans）
python3 -B -s loop/bin/build_plan.py --read-batch 3   # 只生成第 3 批精读链
python3 -B -s loop/bin/build_plan.py --ops            # 生成运营流
```

守护轮会在「精读链剩余 < 120 条」时自动补下一批。这样既不会一次生成几万条没人看的任务，
也不会跑到一半断粮。

## 一条精读链经过谁的手

```
read:<book>:L<lane>:<unit>          原文精读（READER）
   ↓ requires
verify:<book>:L<lane>:<unit>        独立反向复核（VERIFIER，必须换 agent）
   ↓ requires（整批 20 个单元）
publish:<book>:B<批次>              发布为新的审阅版本（PUBLISHER，持 GATE.lock，追加式写回）
   ↓ 每 3 批
expert:review-<n>                   跨域专家评审（EXPERT-REVIEW）
```

外加两条横切线：`ops:*`（全量门禁、GPU 串行核验、worker 存活、QUALITY 同步）
与 `env:*`（对账环境本身：漂移修复、plan100 台账接入、索引自检）。

## 提交格式（`loop.py submit` 会做机器校验）

```json
{
  "task": "read:dafeng:L0:0007",
  "agent": "w-dafeng-0",
  "status": "done",
  "summary": "一句话说清做了什么、覆盖哪一段",
  "evidence": [{"path": "loop/state/out/read_dafeng_L0_0007.candidate.json", "sha256": "…"}],
  "assertions": [{"text": "我如何验证的", "result": "pass"}],
  "changes": [{"path": "loop/state/out/…", "kind": "append-only"}],
  "sourceHashes": {"data/cache/9b67….json": "…"},
  "remaining": ["没做完的、没把握的"],
  "rollback": {"kind": "append-only", "strategy": "delete-added-files", "files": ["…"]}
}
```

会被拒绝的情况：证据文件不存在、哈希对不上、`changes` 里有受保护路径、没有 `assertions`、
`status=done` 却没有 `sourceHashes`。**被拒绝时去补真实证据，不要改校验规则。**

## 守护进程怎么持续跑几十小时

**三层，且第一层是必须的**（2026-10-10 实测更正：原先只写了两层，而第 2 层在本机是坏的）：

1. **本进程级监督者（必须）**：`sh loop/bin/run-supervisor.sh`
   它只做一件事——发现 `sentinel.py --watch` **主进程**不在跑就把它拉回来，
   每 120 秒检查一次。**这是唯一在本机真正有效的一层**（见下）。
   判活**只认 `--watch` 常驻主进程**：外挂驱动 `bash -c '... sentinel.py --once ...'`
   的命令行里也含 "sentinel.py"，早期版本把它算作「哨兵活着」，结果真主进程被
   `kill -9` 后监督者拒绝拉起（实验复现）。日志：`loop/state/logs/supervisor.log`。
2. **本会话内**：`python3 loop/bin/sentinel.py --once` 起 worker 后，worker 是**独立会话**
   （`start_new_session=True`），本会话结束它们也继续跑；有重启上限，不会变成崩溃循环。
   ⚠️ 但这正意味着 **sentinel 死了 worker 还活着、却没人补队列/回收租约**——
   2026-10-10 核对 `GUARD-HISTORY.jsonl` 发现 5 处 >15 分钟空洞，**最长 378 分钟**，
   空洞期间 184 个 worker 日志仍在写。这就是第 1 层存在的理由。
3. **跨会话（本机当前不可用）**：Mirasim 排期每 10 分钟跑一轮 `sentinel.py --once`。
   理论上机器睡醒、会话结束都能恢复，但本机经排期的 agent 被
   **「自有档而本机无该账号」**挡住（见 PROJECT-STATE §4e H1）——
   **需要用户在 设置 › 线路/全局档位 切到「平台」**，否则这层等于没有。

**OS 级兜底在本项目已被实测排除**，不要再试：`launchd`/`cron` 读 `~/Desktop` 会被
macOS TCC 拒绝。2026-10-10 实测（launchd 加载一个 plist 跑脚本）：

```
cat ~/Desktop/星系/loop/bin/sentinel.py  →  Operation not permitted
ls  ~/Desktop                            →  Operation not permitted   （写入反而成功）
```

所以本仓库（在 `~/Desktop` 下）**只能**靠第 1 层 + 第 2 层，没有第三种 OS 级兜底。

## 停止

```sh
# 停掉所有 worker（当前任务做完后退出，不打断）
for n in $(python3 -c "import json;print(' '.join(w['name'] for w in json.load(open('loop/state/policy.json'))['workers']))"); do
  pkill -f "worker.py --agent $n" || true
done
rm -f loop/state/GUARD.lock
```

排期任务在 Mirasim 的「定时任务」面板里暂停或删除（名字：Castline 守护轮）。

## 诚实边界

- 这套环境**不产生质量分**。它只保证：任务有真实的分母、产出有可核对的证据、
  错误归因不靠猜、并行不互相覆盖。八维评分仍按 `docs/QUALITY.md` 逐条判。
- 全书语义完成要求 1133 个原文单元全部有审阅处置，这是**数十小时量级**的工作，
  跑完不等于「理解了三本书」；每批仍要按覆盖率、锚点率、冲突率、人工复核来衡量。
- 真机、读屏、独立盲审这些缺口不会因为跑得久就消失，它们会一直出现在 `remaining` 里。
