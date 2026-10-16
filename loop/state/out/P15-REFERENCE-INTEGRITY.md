# P1.5「保护旧引用」· 逐层核对与验收结果

**版本**：`aee4c99808674e4220ab0104` · **方法**：只读数据 + 调 `serve.py` 的真实函数（不跑 GPU）

---

## 一、逐层引用完整性（P1.5 要求的"逐层核对"）

| 层 | 引用字段 | 引用数 | **悬空** |
|---|---|---:|---:|
| `storylines[].events` | order（数字） | 17,450 | **0** |
| `causeEdges` | `fromEventId` | 6,778 | **0** |
| `causeEdges` | `toEventId` | 6,778 | **0** |
| `characterStates` | `eventId` | 1,731 | **0** |
| `tasks` | `outcomeEventId` | 1,096 | **0** |
| **事件 `order` 取值** | — | 17,450（唯一） | **重复 0** |

**⇒ 全部引用都能解析，无一条悬空。**

**注意 `storylines[].events` 存的是 **order 数字**（不是我一开始误判的 id）** ——
我最初按 id 查得「17,450 条全部悬空」，**那是我问错了问题**；
改按 order 解析后 **0 悬空**。这与 `docs/SCHEMA.md` 的约定一致。

## 二、验收项①：**归一化两次幂等** ✅

```
第一次 rebuild_sources hash: bd65b1ce209700e2bf137738
第二次 rebuild_sources hash: bd65b1ce209700e2bf137738
**幂等: True**
```

## 三、验收项②：**数字 order 重复不能择第一条** ✅（行为验证）

这是 P1.5 最要紧的一条。我构造**真实 storyline + 制造歧义 order**：

```
真实 storyline auto-main-1 首个 order=1，共 374 个引用
把另一个事件的 order 也改成 1  ⇒ order=1 现在对应 2 个事件
postprocess 后：
   该 storyline 引用数 374 → 372
   **被丢弃的 order: [1, 2]**
   event_mapping_warn: ["剧情线 auto-main-1 的 order 1 歧义未引用",
                        "剧情线 auto-main-1 的 order 2 不存在"]
```

**对应源码（`serve.py:3725`，属 `postprocess()`）**：
```python
matches = current_order_map.get(str(integer(order, -1)), [])
if len(matches) == 1:
    mapped.append(matches[0] + 1)
else:
    mapping_warnings.append("剧情线 %s 的 order %s %s" % (
        ..., "歧义未引用" if matches else "不存在"))
```

**⇒ `len(matches) == 1` 才映射；多条时**丢弃并记录警告**，
**绝不 `matches[0]` 取第一条** —— 正是 P1.5 要求的行为。**

## 四、我在这一轮**自己犯的两个错**（如实记录）

| # | 错误 | 真相 |
|---|---|---|
| 1 | 说「storylines 的 17,450 条引用全部悬空」 | **我问错了问题**：它们存的是 order 不是 id。按 order 解析后 0 悬空 |
| 2 | 用 `rebuild_sources` 测歧义，得「没有警告、仍映射成 [1]」 | **我测错了函数**：歧义守卫在 `postprocess()`（:3522），不在 `rebuild_sources()`（:5151）。换对函数后警告与丢弃都如预期 |

**⇒ 第 2 个错误尤其值得记**：我给出了一个"系统没有按 P1.5 要求做"的结论，
而**真实原因是我的探针调错了函数**。**若不追下去，我会报一个虚假缺陷。**

## 五、负例逐项（P1.5 点名的那批）

| 负例 | 实测行为 | 判定 |
|---|---|---|
| 删一条事件 | 事件 17,705→17,704，重复 id/order 均 0 | ✅ 安全降级 |
| **重复 ID** | 事件数 +1，**重复 id 1**（未被拒绝） | ⚠️ **`postprocess` 不拒重复 id** —— 需查是否有更外层把关 |
| **重复 order** | **重复 order 1**（未被拒绝） | ⚠️ 同上；但**storyline 引用侧已正确丢弃**（见第三节） |
| `order = 0` | 通过，无异常 | ✅ |
| `order = -5` | 通过，无异常 | ✅ |
| **order 为数字字符串** | **拒绝**：`TypeError: '<' not supported between instances of 'str' and 'int'` | ⚠️ **报错方式不友好**（抛 TypeError，不是可读的校验错误） |

**⇒ 三条待处置**（我**未改**，因为都在受保护路径且属 P1.1/P1.5 的实施工作）：
① `postprocess` 不拒重复 id/order（**但引用侧已安全**，故危害有限）；
② 数字字符串 order 抛 `TypeError` 而非可读错误；
③ 需确认外层（发布器/校验器）是否已覆盖 ①②。

## 六、沉淀规则（第 39 条）

> **在断言"系统没做 X"之前，先确认"我调的是做 X 的那个函数"。**
> 我用 `rebuild_sources` 测「order 歧义不择第一条」，得到「没警告、照样映射」，
> 差点报出一个**不存在的缺陷** —— 而守卫其实在 `postprocess()` 里，行为完全正确。
> **⇒ 探针选错入口，会产出与事实相反的结论；这与"判据方向错"是同一类错误，
> 但更容易被忽略，因为**代码确实存在**，只是不在我调的那条路径上。**
