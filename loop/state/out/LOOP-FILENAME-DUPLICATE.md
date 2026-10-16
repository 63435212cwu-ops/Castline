# 观察：`loop/state/out/` 存在**同任务的两种文件名**（冒号 vs 下划线）

**发现时刻**：第 60 轮 · **触发**：`ops:accept-full` 出现两条记录、状态不一致

---

## 一、事实

```
$ loop.py stats                                → 待复核 1
$ ls loop/state/out/ | grep accept-full
ops:accept-full.json        verifyState=pending  reviews=0     ← 冒号版
ops_accept-full.json        verifyState=pass     reviews=2     ← 下划线版（**规范名**）

$ python3 -c "... m.output_name('ops:accept-full')"
ops_accept-full.json                                          ← 规范名是**下划线**
```

**⇒ `loop/bin/loop.py` 的 `output_name()` 把 `:` 规范化为 `_`；
`ops_accept-full.json` 是**校验器实际读写**的文件（我的复核落到了它上面，现在 reviews=2、verifyState=pass）。**
**⇒ 冒号版 `ops:accept-full.json` 是**另一写入者**用未规范化的名字写的**孤儿副本**（reviews=0、永远 pending）。**

## 二、与既有记录的关系

`loop/PROJECT-STATE.md` 的第 4 条事故写着：

> **agent 写的产出名（`ops_accept-full.json`）与校验器找的名字（`ops:accept-full.json`）不一致**
> **已修（统一 `output_name()`）＋ 加自环检测**

**⇒ 那次修的是"统一 `output_name()`"；而本轮我观察到的现象表明：
历史上用**旧名（冒号）**写下的文件**仍然留在目录里**，
于是 `stats` 会把它们当作"未复核的提交"反复计数。**

**⇒ 这不是新 bug，而是**旧事故的残留物**未被清理。**

## 三、影响（如实评估，不夸大）

| 影响 | 说明 |
|---|---|
| `loop.py stats` 的 `pendingVerify` 计数**偏高 1** | 我把 `ops:accept-full` 复核后，冒号版仍显示 pending ⇒ 计数不会归零 |
| 对**门禁结果**无影响 | `accept.sh` 不读 `loop/state/out/`；规范名文件状态正确 |
| 对**任务归属**无影响 | 两条记录指向同一 `task` 与同一 `agent`（`w-smoke`） |

**⇒ 我**不删**那个冒号版文件** —— 它不是我写的（`agent=w-smoke`），
且**删除他人产物**属于"归属不明"的破坏性操作（规则明令保持原状）。

## 四、建议（交给 loop 工具维护者）

1. 写一个**一次性迁移**：把 `loop/state/out/` 下所有"含 `:` 的 `.json`"按 `output_name()` 重命名，
   若目标已存在则**比对 `task` 与 `agent`**，一致则合并 `reviews`、不一致则保留为 `.conflict.json`；
2. 在 `submit`/`verify` 里加**自环检测**（既有事故已提过"加自环检测"，可扩展到"文件名规范化检测"）；
3. `stats` 的 `pendingVerify` 可加一个**"疑似重复任务"**的旁路计数，避免因重复文件让计数永不归零。

## 五、沉淀规则（第 59 条）

> **修好一个工具后，要检查它**历史写下的产物**是否还留在原地。**
> `output_name()` 统一了**今后**的命名，但**过去**用旧名写的文件仍在，
> 并在 `stats` 里表现为"永不归零的待复核"。
>
> **⇒ 可执行做法：任何"命名/格式规范化"的修复，都应附一条**存量迁移**步骤
> （扫描 + 重命名/合并 + 冲突报告），否则残留物会在**计数/门禁**这类聚合视图里长期错报。**
> **⇒ 这与我第 52/57 条同源：规则改了不等于状态改了。**
