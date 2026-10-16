# read:dafeng:L0:0224 重复领取取证 + 独立复核（w-xiyou-0）

**结论：NOT SUBMITTED（本轮不提交）。** 本任务在我领取**之前 59 秒**已由 `w-sanguo-0`
提交并通过机器校验；`writes` 指向的正是那份已完成记录的证据文件，覆写它会把一条
**已通过机器校验**的产物降级成「没做完」。本轮改为留下**不改动共享产物**的竞态取证
+ 对既有候选的独立复核，并报告我在复核中发现的两处**真实缺陷**。

这与同环境既有先例同形（`read_dafeng_L0_0216.w-xiyou-0.dupclaim/`、
`read_dafeng_L3_0267.w-dafeng-0.dupclaim/`，两者结论同为 NOT SUBMITTED）。

---

## 1. 事实（都可复现）

| 事实 | 值 | 复现命令 |
|---|---|---|
| 我的租约 | `agent=w-xiyou-0`, `pid=43457`, `startedAt=2026-10-15T01:06:05Z` | `cat 'loop/state/leases/read:dafeng:L0:0224.d/lease.json'` |
| 先前提交 | `agent=w-sanguo-0`, `submittedAt=2026-10-15T01:05:06Z`, `validation.problems=[]` | `python3 -B -c "import json;d=json.load(open('loop/state/out/read_dafeng_L0_0224.json'));print(d['agent'],d['submittedAt'],d['validation'])"` |
| **提交早于我的租约** | **+59 秒** | 上两条的时间差 |
| 该任务是否算 done | **是**（`'read:dafeng:L0:0224' in done_ids() == True`） | `python3 -B -s loop/state/out/read_dafeng_L0_0224.w-xiyou-0.dupclaim/audit_dupclaim.py` |
| 7 个证据文件 | 全部存在且哈希逐一相符 | 同上（`raceForensics.evidence`） |
| docs.json sha256 | `fdde5558…39839`（== 任务 `sourceHash`） | `shasum -a 256 data/cache/1063b17ca65ec1b76f30e460.docs.json` |
| 切片 | 3937 codepoint，以「第两百二十三章 许七安的无奈之举」开头 | 同上 |
| 无被拒记录 | 没有 `REJECTED__*0224*` | `ls loop/state/out/REJECTED__*0224*` |

## 2. 为什么不能提交 —— 危害已在内存中复现

`loop/state/out/` 属 `MUTABLE_EXCEPTIONS`，`loop.py: is_evolving()` 对它返回 **False**
（审阅产物被改写就是真问题）。因此覆写候选 ⇒ `evidence_stale()` 报 `hash-changed`
⇒ `validated() 且不 stale` 不成立 ⇒ `done_ids()` 剔除该任务。

`audit_dupclaim.py` 用 `copy.deepcopy` 在**内存里**复现（未改磁盘上任何既有文件）：

```
stale BEFORE                    : []
stale AFTER simulated overwrite : [{'path': '…0224.candidate.json', 'why': 'hash-changed'}]
=> done_ids() would drop it     : True
```

**本轮不提交是安全的**（已核 `worker.submit_if_needed()` 的第一个分支：
`out_path` 存在 且 `validated(rec)` 且 `evidence_stale(rec)==[]` ⇒ 返回
`already-submitted`，既不覆盖也不写 `REJECTED__`）。实测该分支条件对 0224 成立。

### 2.1 而且 `submit` 本身也会覆盖掉别人的记录

两条路都通向破坏，方向不同：

| 动作 | 写向哪里 | 后果 |
|---|---|---|
| 按 `writes` 写候选 | `loop/state/out/read_dafeng_L0_0224.candidate.json` | 该文件是 `w-sanguo-0` 记录的**证据** ⇒ `evidence_stale()` 报 hash-changed ⇒ 任务被剔出 `done_ids()` |
| 跑 `loop.py submit` | `OUT/output_name(tid)` = `loop/state/out/read_dafeng_L0_0224.json` | **正是 `w-sanguo-0` 那条已通过机器校验的记录本身** ⇒ 直接覆盖掉它的 summary／15 条 assertions／7 条 evidence／10 条 remaining |

第二行不是推测：`cmd_submit()` 在校验通过后无条件 `write_json_atomic(OUT / output_name(tid), rec)`，
而 `output_name('read:dafeng:L0:0224') == 'read_dafeng_L0_0224.json'` ——
与 `w-sanguo-0` 的记录路径**逐字相同**（两者都已实测，见 §7）。

所以「不提交」不是偷懒：**提交这个动作在本轮能做的只有破坏**。
它与同环境两次先例一致（`read_dafeng_L0_0216.w-xiyou-0.dupclaim/`、
`read_dafeng_L3_0267.w-dafeng-0.dupclaim/` 的 `outcome` 均为 `NOT SUBMITTED`，
且事后核对：那两条被保护的记录 `agent`/`submittedAt` 一字未变）。

## 3. 根因：pick()→claim() 的 TOCTOU

| 位置 | 事实 |
|---|---|
| `loop/bin/loop.py:651` `pick()` | `:653 done = done_ids()` 是**一次性快照** |
| `loop/bin/loop.py:715` `claim()` | 只判 `lease_alive()`／`mkdir`，**不重查 done** |
| `loop/bin/worker.py:519` `one_round()` | `pick()` → `claim()` 两步不原子 |

本次实测 `done_ids()` 单次 **47.7 秒**（1017 个记录文件、999 条 done；同机同时刻实测）。
快照与 `claim()` 之间隔了数十秒，任何在这段窗口里被提交的任务都会留下重复领取。
本任务落在窗口内：提交 01:05:06Z，我的租约 01:06:05Z。

**这不是我的任务特有的**：`leases_on_done_tasks.py` 当场实测
（`2026-10-15T01:38:01Z`，`done_ids()` **41.2 秒** / 1002 条 done / 15 条活跃租约）
有 **2 条活跃租约落在已 done 的任务上**，且两条都不是提交者自己：

| 任务 | 租约持有者 | 已完成者 | 租约晚于提交 | 同一人? |
|---|---|---|---|---|
| `read:dafeng:L0:0224` | `w-xiyou-0` | `w-sanguo-0` | +59 s | 否 |
| `verify:dafeng:L0:0220` | `w-dafeng-3` | `w-verify-3` | +65 s | 否 |

第二条是**独立于我的**样本：它在我的取证期间由另一对 worker 产生，形态完全相同
（租约比提交晚 1 分钟左右，正是 `done_ids()` 一轮的耗时量级）。
先例 `read_dafeng_L0_0216` 那份取证在同形态枚举里也各记了一条 read 与一条 read-verify。

## 4. 独立复核既有候选（不 import 对方任何脚本）

`audit_dupclaim.py` 只借 `loop.py` 的判据，**不 import** `w-sanguo-0` 的
`build_candidate.py`/`gen_quotes.py`/`audit_candidate.py` 中任何一个，自己读
`docs.json` 与产物 JSON，自行重新定位每一条引文、自行重算每一条覆盖率断言。

| 项目 | 结果 |
|---|---|
| 引文对象总数 | 198（与候选自报一致） |
| `text[start:end] == quote` 逐字成立 | **198/198** |
| 偏移落在区间 `[841448,845385)` 内 | 198/198 |
| `sourceHash` 正确 | 198/198 |
| 切片内唯一命中（`slice.count(lit)==1`） | 198/198 |
| 五栏共用同一句话 | **0**（任务明令禁止的形态） |
| 裸 `null` 栏缺 `*Note` | **0**（7 个 null 全带理由） |
| `worldSettings` 判别字段（placeState/itemStates/institution） | 0 处缺失或非法 |
| 伏笔 status 合法、unresolved 有说明 | 0 处违规 |
| `themeReadings` 三条（perspective/support/counter）齐全 | 0 处缺失 |
| 覆盖率复算（104 / 77 / 27） | **与候选自报逐项相同** |
| 零覆盖清单**身份**（不只比数量） | 27/27 逐条文本相等 |

**反向复核**（复核契约要求「这一段里还漏了什么」）：我自己读切片后立 **24 条独立探针**
（`reverse_check.py`），逐条问「候选有没有引文触及 / 结论文本提到」：

- 切片内命中 **24/24**（没有一条是我记错原文）
- 被引文触及 **17**；未被触及 **7**
- 这 7 条**全部**已被候选自己登记在 `coverage.zeroCoverageList` 里（P047/P058/P060/P066/P075/P083/P087）
- 「未被引文触及 且 结论文本也未提及」 = **0**

即：我没有找到构成「漏读」的硬缺陷。**未覆盖 ≠ 漏读** —— 这份清单只回答
「有没有被引到」，不回答「该不该被引到」。

## 5. 我发现的两处真实缺陷（既有候选里，不是我的产物）

### 5.1 P### 段落编号两套口径混用（差 1）— `check_para_numbering_targeted.py`

同一份候选里两套编号：

| 用法 | 实测口径 | 命中 |
|---|---|---|
| 结论文本内联 `P###`（note/mechanism/why/actorNote…） | **正文起算**（标题不算 P001） | 7/7 |
| `coverage.zeroCoverageList[].para` | **标题算 P001** | 27/27 |

判据（对每条自带内容描述的内联引用，逐条在切片里定位它指的那段原文）：
`P065 对城防军装备的交代` → 实际是 body-counted P065 / title-counted P066；
`P045 对四品稀缺的交代`、`P017`、`P064`、`P020`、`P009`、`sliceNote` 的 `P001–P040` 同理。
候选**全文没有一处定义 P### 的编号口径**。

后果：复核者照内联 `P###` 去查 `zeroCoverageList` 会**错开一段**；反之亦然。
这只是文档内部一致性缺陷，**不影响**引文逐字定位（那 198 条已独立复算通过）。

> 附带坦白：我这个脚本的初版有两个缺陷，都已修掉并把教训留在代码注释里 ——
> ① 只扫 `text` 字段 ⇒ 内联引用命中 0 条，险些据此写下「证据不足」的假结论；
> ② 判定分支漏了「inline 用正文口径、zeroCoverage 用标题口径」这一支，
> 而实测恰好就是这一支，于是它掉进 `else` 打出「证据不足」。**结论与数据不符
> 不是数据的问题，是判据没覆盖到。**
>
> 另有一处**我自己脚本的**缺陷（不在候选里）：`reverse_check.py` 初版用
> `sorted({...})` 从 **set** 出发取关键词片段 ⇒ 两次运行的片段顺序不同，
> 报告**不可复现**（实测两次 `--json` 输出 diff 176 行、sha256 不同）。
> 「输出可复现」是这份取证的前提，已改成从 list 去重 + 固定顺序；
> 现在五个脚本里四个的输出**逐字节可复现**（已各跑两次核对）。

### 5.2 `sliceNote` 的场景切分与原文的分隔符不一致 — 同一脚本 + 原文核读

`sliceNote` 自称三个连续场景：`P001–P040` / `P041–P072` / `P073–P103`。

原文里**独立成段**的作者分隔符（整段只有点号）实测只有 3 处（body 编号）：
`P021 "....."`、`P101 "...."`、`P103 "------------"`。

- 作者分隔符 `P021` 落在候选自称的第一场 `P001–P040` **内部** —— 若按作者的分隔符读，
  第一场在 P021 就断了，而 P022 起是**同一地点（驿站）的下一场**。
- 候选把 `P040|P041` 当场景边界，但这两段之间**没有**任何分隔符：P040 是叙述
  （「一颗心倏地沉入谷底」），P041 紧接人物台词（「我感觉要出事了」），同属驿站内连续动作。

即：`sliceNote` 的场景划分是候选**自己**的归纳（可以成立），但它的编号口径与
5.1 一样没有声明，且与原文的分隔符不对齐。这不影响任何一条 `quotes[]`，
但会误导按段号回查场景的人。

## 6. 我**没有**做的事（写进 remaining，不编）

- 没有做语义核验、没有声称做过：候选 `semanticReview.status = "not_performed"`，
  我这一轮**也没有**把它升格。我复算的是「引文能否逐字定位 + 分区结构 + 五栏互异
  + 覆盖率」，**引文定位正确 ≠ 语义已核验**。
- 没有跑 GPU／浏览器测试（任务未声明）。
- 没有改 `loop/state/out/read_dafeng_L0_0224.candidate.json` 或任何共享产物（只**读**）。
- 没有替 `w-sanguo-0` 的 15 条 causeEdges 判对错 —— 那是 `verify:dafeng:L0:0224`
  的职责（`verifyState=pending`），不是我。

## 7. 复现

```sh
cd /Users/carmen/Desktop/星系
D=loop/state/out/read_dafeng_L0_0224.w-xiyou-0.dupclaim
python3 -B -s $D/audit_dupclaim.py                    # 竞态取证 + 独立复核（ok=true / exit 0）
python3 -B -s $D/reverse_check.py                     # 24 条反向探针
python3 -B -s $D/verify_zero_and_entities.py          # 零覆盖身份 + 实体覆盖 + 语层取证
python3 -B -s $D/check_para_numbering_targeted.py     # 5.1 编号口径（verdict 可复核）
python3 -B -s $D/leases_on_done_tasks.py              # 时变读数：活跃租约 ∩ 已 done
```

前**四**个脚本的输出是**确定性的**（同一输入给同一结果，已各跑两次逐字节核对）；
第五个 `leases_on_done_tasks.py` 例外 —— 它读的是**时变**的租约表，数字随运行时刻变化，
所以报告里引用它时一律附上运行时刻。

## 8. 建议（给运营侧，不是我能自己修的）

1. **`pick()`→`claim()` 的 TOCTOU 是真缺陷**，且 `done_ids()` 实测 47.7 秒让窗口
   足够大。修法方向：`claim()` 内重查一次 done（或让 worker 在 claim 后、起 agent 前
   再核一次 `validated() 且不 stale`，命中则直接跳过并释放租约）。这是 `loop/` 的改动，
   按纪律只能在合并任务里改并持 `GATE.lock`，我不动。
2. **`zeroCoverageList[].para` 与内联 `P###` 的口径应统一**并在候选里声明。
   建议统一为「标题算 P001」（与 `zeroCoverageList` 及兄弟候选 0216/0220 一致），
   或反过来统一为正文起算 —— 关键是**写进字段**，不能靠读者自己分辨。
3. 5.2 的场景划分建议改为按作者分隔符，或在 `sliceNote` 里显式声明「场景是归纳」。
