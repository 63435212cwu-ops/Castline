# 数据契约、版本迁移与实体对齐

当前质量与执行顺序见 [QUALITY.md](QUALITY.md)。旧缓存必须可读，迁移双读、可回滚，不静默覆盖发布版本。

本文是 **schema 版本、可迁移字段清单、默认值、降级路径与回滚** 的权威说明。代码是
`js/atlas/atlas-source.js`（读边界）、`js/app.js`（`normalizeGraph` 渲染前归并）、
`serve.py`（服务端契约边界）、`narrative.py`（叙事层版本键）。

---

## 1. 版本谱系

| 版本 | 写入者 | 状态 |
|---|---|---|
| `castline/5` | 当前 `atlas-source.js` / `serve.py` | **当前写入版本** |
| `castline/4` | 上一版服务端（`data/cache/*.json` 现状） | 可读，迁移加性 |
| `castline/3` | 旧服务端 | 可读 |
| `v3-universal` | 更早服务端 | 可读 |
| `legacy`（无 `meta.schema`） | 最早缓存 | 可读 |

叙事层版本键：`narrative/8-context-conservative`（当前），`narrative/7-context-conservative`
（已发布缓存中的键，仍在 `narrative.READS_VERSIONS` 内可读）。

> 版本键**不使旧数据失效**。它的作用是阻止新构建**静默覆盖**已发布版本，而不是宣布旧版本不可读。

---

## 2. 双读（dual read）

新版本换了拼写时，**两种拼写都读**；两者不一致时**不按优先级择一**，而是记为待审冲突。

| 事实 | 新拼写 | 同义旧拼写 | 一致判定 |
|---|---|---|---|
| 实体 ID | `id` / `entityId` | 互为同义 | 值相等 |
| 章节标签 | `chapter` | `chapterLabel` | 值相等 |
| 引用端点 | `sourceRefs` | `sourceRef` / `evidenceRefs` / `quoteRef` | **同一定位**（sourceId + textHash + offsetUnit + start + end + quote） |

`meta.dualRead` 记录：`fields`（同义拼写表）、`conflicts[]`（不一致项，`resolution: "pending_review"`）、
`policy: "both_spellings_read_no_preference_order"`、`autoMerged: 0`。

**不列入双读的字段**：`storylines[].eventIds` 与 `storylines[].events` 不是同义拼写——
前者是事件 ID 列表，后者是事件序号列表。二者都必须能独立读取；
`eventIds`-only 的故事线曾经整条丢失事件表，现已按同一唯一性规则读入（见 §5）。

---

## 3. 可迁移字段清单、默认值与降级路径

### 3.1 加性新增（不迁移也能跑）

| 字段 | 位置 | 缺失时 |
|---|---|---|
| `meta.schemaCompat` | `meta` | 视为未知来源；`inspect()` 报 `unlisted-input-schema` 警告 |
| `meta.identity` | `meta` | 身份台账缺失；读者**不得**据此推断身份已对齐 |
| `meta.dualRead` | `meta` | 无双读记录；旧拼写仍照常读 |
| `characters[].chapterIds` | 人物 | `[]`，不推断所属章节 |
| `events[].ambiguousTokens` / `.attribution` | 事件 | 缺席即未评估；**不等于** `resolved` |
| `relations[].ambiguousTokens` / `.attribution` | 关系 | 同上 |
| `evidence[].id` | 证据 | 按内容寻址补 ID，不改引用语义 |

### 3.2 唯一一处**设计性重写**：`events[].order`

自 `castline/3` 起，事件序号被**重排为 `1..n`（按数组顺序）**。这不是本工作包引入的行为，
但它是迁移中唯一会改写旧值的动作，因此被显式登记：

- `meta.eventIndexMap.rawOrderToNormalized` 与每个事件的 `rawOrder` 保留原值；
- `applyMigration()` **逐事件验证** `rawOrder` 仍等于被改写的旧值，任何不可恢复的情况
  都会使迁移以 `migration_not_additive` 失败，而不是悄悄通过；
- `DOCUMENTED_REWRITES` 是对外可见的清单，`legacyFieldsPreserved` 只有在全部旧值
  （含该重写）仍可读时才为 `true`。

### 3.3 降级路径（缺失 → 显式 unknown / pending）

| 缺失事实 | 降级结果 | 明确**不**做的事 |
|---|---|---|
| 人物重要度 | `importance: null`，`importanceKnown: false` | 不填 0、不填 45 |
| 八维分值 | `score: null`，`pending: true`，原值进 `reportedScore` | 不生成默认分；不删原值 |
| 关系强度 | `strength: null`，`strengthKnown: false` | 不按 0.5 当结论 |
| 章节标签 | 计入 `chapters.unlabelledEvents` | 不插值、不按均分补章 |
| 可选层（`clues`/`causeEdges`/…） | `coverage[field].known: false` | 不把「没抽到」当「不存在」 |
| 原文证据 | `evidence: []`，证据状态停在 `unverified` | 不伪造引用、不用 summary 冒充原文 |
| 抽取完整性 | `extraction.complete: null`，`reason: "legacy_coverage_unknown"` | 不宣称全书完整 |
| 关系端点无法唯一解析 | `resolved: false`，原声明保留 | 不猜测端点、不删节点 |

台账字段 `meta.identity.unknown` / `.orphans` 给出上述各项的**实测计数**，
全部来自遍历，不存在估算值。

---

## 4. 稳定 ID

| 对象 | ID 来源 | 稳定性保证 |
|---|---|---|
| 章节 | `chp_<hash>`，对**折叠空白后的标签**寻址 | 与数组顺序无关；`第一章 起` 与 `第一章  起` 同 ID |
| 事件 | 既有 `id` 优先；否则 `ev_<hash>`（章节/标题/摘要/引文/rawOrder） | 重排、重载后不变 |
| 人物 | 既有 `id` 优先；否则 `ch_<hash>(name)` | 列表重排后不变 |
| 关系 | 既有 `id` 优先；否则 `rel_<hash>(端点对+kind+line)` | 同上 |
| 故事线 | 既有 `id` 优先；否则 `sl_<hash>(name+eventIds)` | 同上 |
| 证据 | `evd_<hash>`，对证据内容寻址 | 同一句话跨图层、跨重载同 ID |
| 源定位 | `loc_<hash>`，对 `(sourceId, textHash, offsetUnit, start, end, quote)` 寻址 | 不依赖任何存储的 `verified` 标志 |

章节 ID 是**唯一新引入的 ID 空间**：章节此前没有稳定身份，只有事件上的标签字符串。
本工作包**不推导章节号**——不相似的标签不会被合并，无标签的桶不会得到虚构序号。

---

## 5. 别名冲突与待审队列

**不得以角色名字符串相等作为唯一身份依据。** 冲突进待审队列，不自动归并。

判定：一个 token 被 **≥2 个节点**声明（既是某节点正名又是另一节点别名，或两个节点的共同别名）
即为冲突。这类 token 不参与合并，其所在的事件人物表与关系端点标记为
`attribution: "review_required"`，并保留**原始声明**。

`meta.identity.aliases.queue[]` 与 `meta.identity.reviewQueue[]` 记录：
`token`、`nodeIds`、`autoMerged: false`、`attribution`、`reason`。
`aliases.autoMerged` 恒为 `0`，是可断言的硬约束。

### 已确认的真实缺陷（不再被自动归并）

1. **`初代监正`（大奉打更人）**：既是独立节点 `ch_45b2bc1e3bbde2b4` 的正名，又是
   `许平峰`（`ch_d50998c6c5bc7460`）的别名。按名字相等归并会把 **105 个事件 + 29 条关系**
   记到错的人名下。现两者都不归属，全部进队列。
2. **`许玉春` / `李玉春`（大奉打更人）**：`reviewIssues` 已确认
   `identityStatus: canonical_name_conflict_in_reviewed_scope`。该节点八维分值
   **全部置为 `pending`**、原值留在 `reportedScore`，节点进 `reviewQueue`。
3. 三国演义 11 个冲突 token（`丞相` 同时是曹操与诸葛亮的别名等）、西游记 34 个、
   大奉 43 个 —— 全部只入队，不归并。

`js/app.js` 的 `normalizeGraph` 同步采用该规则，并在总览面板把「待人工区分」
与「已自动处理」**分成两个区块**显示，避免把「未归并的量」读成「已处理完」。

---

## 6. 迁移 API 与回滚

### 读路径（不落盘、不改字节）

```js
CLAtlasSource.normalize(raw)        // 纯函数：不修改入参
CLAtlasSource.inspect(g)            // 报告 readsDown / schemaCompat / identity / reviewQueue
CLAtlasSource.migrationPlan(raw)    // 只报告要走的跳数与是否允许原地升级
```

```python
S.migration_plan(graph)             # 同上（服务端）
```

### 写路径（唯一会产生升级后字节的入口）

```js
CLAtlasSource.applyMigration(raw)                      // 未发布版本：产出加性升级副本
CLAtlasSource.applyMigration(raw, {allowPublished:true})  // 显式覆盖已发布版本的拒绝
CLAtlasSource.rollbackMigration(migrated, snapshot)    // 回滚；有快照则逐字节还原
```

```python
S.apply_migration(graph, allow_published=False)
S.rollback_migration(snapshot)
```

**不静默覆盖发布版本**：`meta.revision` 存在即视为发布版本，默认拒绝原地升级
（`published_revision_not_migrated_in_place`）。发布版本的键机制沿用
`_publish_graph_revision`（`originalHash` / `outputHash` / `parentKey` / `originalPreserved`），
本工作包未改动它，只是把「schema 升级」也纳入同一把锁。

**可回滚**：旧字段从未被删除，所以回滚是**投影**而非重建——给出快照即逐字节还原；
不给快照则只摘掉契约字段并如实报告摘了哪些，**不重建任何旧值**。

### 加性判定

`applyMigration()` 逐字段比较原图与升级图（数组按实体身份比对，不按位置），
任何 `dropped` / `rewritten` 都会导致迁移失败并列出条目。
唯一白名单是 §3.2 的 `events[].order`，且逐事件验证可恢复性。

---

## 7. 证据与验证

| 断言 | 命令 |
|---|---|
| 旧缓存可读、迁移加性、可回滚、不覆盖发布版本 | `node tests/schema_migration_contract.js`（19 项） |
| 同上（服务端） | `python3 -B tests/schema_migration_contract.py`（14 项） |
| 无回归 | `sh scripts/accept.sh` |

契约测试直接读取 `data/cache/` 下三本真实 `castline/4` 缓存，并在读取前后比对字节，
证明「打开旧缓存不改字节」不是承诺而是实测结果。

---

## 8. 已知缺口

1. **章节ID只对标签稳定**：源文本章节边界与缓存事件章节标签不是同一分母；不能把904个事件标签直接当作原文标准章节数。当前实际解析覆盖见QUALITY，不插值补齐。
2. **迁移不认证原文**：schema迁移不会自动提升sourceRefs或语义可信度。原始缓存与后续审阅版的锚定率不同，应按实际版本统计，不能沿用早期“全部为0”的报告。
3. **别名队列只记录不裁决**：冲突数量随版本而变，需逐个回到原文区分；程序不能仅凭同名合并。
4. **人物chapterIds允许为空**：缺少明确章节归属时保持空，不把缺字段当作人物从未出场。
