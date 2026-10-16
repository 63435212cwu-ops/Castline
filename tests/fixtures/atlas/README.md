# atlas 契约测试 fixture

每个 `.json` = `{ graph, tree }`：`graph` 是最小化的 G（characters/events/relations/storylines），
`tree` 是手写（或程序生成）的 `CLStory.analyze(G)` 输出形状，字段对齐
`js/tree/storylines.js` 的 `out`（`threads[].{id,kind,title,lead,cast,events,len,span,parent,attach,depth,
resolved,suspended,resolution,completionKnown,sourceId,src}` / `events[]` / `chapters[]` / `handoffs[]`）。
`saga-tree.json` 是唯一的例外：它是用 jsc 真跑 `CLStory.analyze(data/sample-saga.json)` 落盘的**真数据**
（`graph` = 完整 `data/sample-saga.json`，`tree` = 真实分析结果，27 人/81 事件/22 线）。

## 各 fixture 考验什么

- **s1-single**：单主线、6 事件、3 章。最简情形——build 不该在这里出任何 warning，
  span/order/status/lead 全部 known，验证「正常路径」的地基不歪。
- **s2-parallel**：两条主线（甲线/丙线）用交错 order（1,3,5,7,9 / 2,4,6,8,10）制造真实的时间重叠。
  验证 gen 按 order.first 排序编号（0/1），以及 `lanes()` 在无容量约束时一线一道、
  容量收紧到 1 时正确溢出进 aggregate 且计数守恒。
- **s3-handoff3**：三条主线两次接棒（M0→M1→M2，tree.handoffs 显式给出 at/from/to/reason）。
  验证 gen 0/1/2 依次编号、每条线的 `handoff` 字段只在真正接手的那条线上出现（M0 无 incoming
  handoff）、中段主线 resolved=false 且 suspended=false 时状态是 `open` 而不是 `unknown`
  （两个布尔字段都在场，就是确定信息，不是缺失）。
- **s4-dense-twigs**：1 主线 + 1 支线 + 26 条 ≤3 事件的末梢，全部挂在同一支线上。
  验证 gen 沿 twig→branch→main 链正确传染、极小 eventCount 下 core 门槛
  `max(2, ceil(0.3*n))` 让几乎所有小线的普通角色落在 minor（只有 lead 例外）、
  `lanes({maxLanes:5})` 在 28 条线里按 main>branch>twig 优先级只留 5 条独立车道、
  其余 23 条落入 aggregate 且计数守恒、以及 search 能穿透 aggregate 命中被吞掉的线。
- **s5-sparse-long**：1 主线（25 章、25 事件）+ 1 支线仅 4 事，散布在第 1/9/17/25 章。
  验证 span.known=true 时「跨 25 章」与「4 事」两个数字互不覆盖 —— chapCount 只数支线
  自己占的 4 个不同章，不会被主干的 25 章带偏；footprint 的 entryChap/exitChap 对应
  首尾事件的真实章序（0 与 24）。
- **s6-unfinished**：故意堆问题——
  - `id: 0`（数字零）的主线：验证 `!= null` 判断不把合法的 0 id 当成缺失，search 与
    直接按 id 查找都能命中；
  - `B1` 缺 parent（`null`）且完全不给 resolved/suspended/resolution/completion：
    验证 gen 落 null、status 落 `unknown`（真正的「一个信号都没有」才是 unknown，
    这条同时覆盖任务书点名的「缺 resolution」）；
  - `B2` 的 `events` 数组里混了空槽（`null`）和非法下标（`999`），且 `parent: 0`
    （引用那条 id=0 的主线）：验证空槽/非法下标只进 warnings 不崩、只保留合法下标 4、
    parent=0 不被 `||` 误判成 falsy、gen 正确继承主线的 0；同时 `B2` 与 `B1` 都在自己的
    `events` 里字面写了下标 4 → 触发 crossings（仅共享事件，不是推断出的亲和关系）；
  - `Td` 无 lead 字段、无 resolved/suspended/resolution，但给了
    `completionKnown:true, completion:'悬置'`：验证 completion 兜底档位生效、
    lead.known=false 时不瞎猜名字；
  - `B3` 的 parent 指向一个不存在的 id（`'ZZZ-missing'`）：验证「parent 有值但找不到」
    与「parent 就是 null」一样都落到 gen=null，不报错、不崩溃；
  - 事件 3 缺 `chapIdx`、事件 7 缺 `order`：验证局部缺字段不会污染其他线的 span/order 判定
    （id=0 主线自己的 3 个事件都齐全，它的 span.known 仍然是 true）。
- **s7-stress**：3000 事件、60 线（6 条主线依次接棒 + 54 条支线，程序生成、事件下标严格分区
  不重叠）。只验证规模：build 不崩、`totals.events===3000`、`conservation.lines===60`、
  build 耗时 ≤200ms（jsc 实测 best-of-5 约 1ms，SwiftShader/浏览器环境会更慢但仍有充裕余量），
  以及 `lanes({maxLanes:12})` 在 60 线下正确溢出且计数守恒。

## 已知与真实系统的差异（如实记录，不是缺陷）

- `js/tree/storylines.js` 默认「严格来源结构」下产出的 `tree.junctions` 是**亲和度/共同角色**
  推断出的关系（两条线在邻近章节共享重要角色），不是「字面共享同一个事件下标」。
  atlas-model 的 `crossings` 字段按契约字面「仅共享事件；不生成因果」定义为**后者**。
  实测发现这两者都不罕见：真数据 `saga-tree.json`（22 线 81 事件）里字面重叠事件下标
  有 70 个、算出 90 组 crossings 对——严格来源结构下主干与支线各自的 `events` 是作者在
  `graph.storylines` 里独立声明的，同一场戏被两条线同时列入是常态，`tree.threads` 最终
  保留了这种重叠，不是分区去重后的产物。s6 fixture 里 `B1`/`B2` 共享下标 4 只是最小化的
  单一样例，不是「唯一会出现 crossings 的场景」。
