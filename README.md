# Castline · 小说星图

---

## 中文

### 它是什么

一部小说写完，人物散在几十万字里，谁和谁结过盟、哪句伏笔没接住，翻回去找要半天。Castline 把这本书挂到夜空上：每个人是一颗星，剧情卷成一枚指环，点开谁就落到谁的罗盘里。

它是本地跑的——`serve.py` 起个服务，浏览器打开就能看。Python 标准库足够，不装第三方包；不配 API 也能直接浏览自带的图谱。

### 怎么跑

```bash
git clone <仓库地址> Castline && cd Castline
python3 serve.py 8000
# 打开 http://127.0.0.1:8000
```

克隆下来就能看，不用接模型、不用重新分析。仓库自带：

- 《西游记》《三国演义》——公版经典，图谱在 `data/cache/`；
- 《大奉打更人》——经权利确认后随仓库分发的分析图谱，只有结构化数据和原文引句锚点，不含正文；
- 《星尘信使》——完全虚构的合成微小说，原文在 `data/demo_src/星尘信使/`，用来演示从原文到图谱的完整链路。想换成自己的书，把材料拖进托盘就行。

要分析新材料时，从「工具 → API」接入任何 OpenAI 兼容或 Anthropic 协议的端点，配置只存在本地 `data/llm-config.json`（已在 `.gitignore` 里）。

### 三张图

- **星座**：默认视图。主角团在盘心，各势力占一个扇区，咖位越高星越亮，势力范围就是那团星云。悬停一颗星，它牵连的关系会亮起来。
- **星盘**：顶栏「剧情」或按 `P`。整条故事卷成一枚指环，从 12 点顺时针转一圈，就是从第一回读到最后一回。底部有播放条，可以逐回推进。
- **罗盘**：点任意一颗星，或搜索人名。镜头落到这个人身上：中间是八维性格晶体，外圈三道轨道走的是亲近、对抗和其他关系，下弧是他一路走来的因果链。

### 打开方式

```
http://127.0.0.1:8000/?data=data/demo.json          # 星座
http://127.0.0.1:8000/?data=data/demo.json&plot=1   # 星盘
# 罗盘：打开上面任一地址后，点一颗星（例如主角「沈曜」）或用搜索进入
```

其他样例：`data/sample-focus.json`（单人聚焦）、`sample-mid.json`、`sample-large.json`、`sample-saga.json`（超长篇压测）。

### 数据

短材料一次读完；长材料按章节切块并行抽取，再归并候选、合并别名、分批建档、整理关系。中途断流会自动重连到同一个作业，跑完的块留在 `data/cache/chunks/`，续跑不会重复计费。

图谱结构（完整约定见 [docs/SCHEMA.md](docs/SCHEMA.md)）：

```text
title, synopsis,
characters[{name, aliases[], role, importance, identity, brief, traits[], camp, stance,
            attrs{智谋|实力|意志|魅力|情感|野心|权势|道义: {score, evidence[], basis, low}},
            arc[{phase,text}], judgments[{kind,text,chapter}]}],
camps[{name, stance, brief}],
events[{order, chapter, title, summary, characters[], kind, quote}],
relations[{a, b, kind, strength, desc, line:明线|暗线}],
causeEdges[{id, fromEventId, toEventId, basis, description, quote, sourceRefs[], resolved}],
clues[{id, seedEventId, payoffEventId, status, basis, sourceRefs[]}],
characterStates[{id, characterId, character, eventId, chapter, summary, attributes[],
                 quote, sourceRefs[], transition{before,after}}],
storylines[{id, name, kind:主线|支线|末梢, parent, attach_order, events[order], lead,
           cast[], theme, resolution:收束|悬置|未定, handoff_from, handoff_reason}]  # 可选
```

### 接口

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/plan` | 规划：分块、耗时预估、缓存复用（不调模型） |
| POST | `/api/analyze` | SSE 分析流 `{docs, force, refresh}` |
| POST | `/api/cancel` | 取消作业（已完成的块保留） |
| GET | `/api/jobs` · `/api/history`（+`/detail` `/docs`） | 作业与作品库 |
| POST | `/api/history` | `delete` `open` `rename` `pin` `note` `sweep` |
| GET/POST | `/api/llm-config` | 端点配置与连通测试 |
| GET | `/api/health` | 服务与构建状态 |

### 验收

```bash
sh scripts/accept.sh                                              # 离线契约与静态门
CL_GPU=1 ATLAS_BASE=http://127.0.0.1:8000 sh scripts/accept.sh --browser   # 浏览器门（真 GPU，串行）
python3 -B -s tests/sky_shell.py --base http://127.0.0.1:8000       # 单跑星空壳
```

入口脚本会跑完所有检查，单项失败不中断，最后用非零退出码汇总失败项。浏览器验收使用 `tests/headless.py`（CDP，零依赖）；`CL_GPU=1` 走真 GPU，另有 `CL_TIMEOUT` / `CL_CDP_TIMEOUT` / `CL_READY_TIMEOUT` 可调。测试不调用模型，也不改动 `data/`。

### 目录

```
serve.py        本地服务 + 分析管线（Python 3 标准库）
narrative.py    叙事结构、引文定位与上下文
distill.py      文风蒸馏
index.html      单页入口（脚本顺序由 tests/script_manifest.json 约束）
js/sky/         星空界面：读层（SVG/DOM）+ 光层（WebGL）
js/scene.js · js/core/   three.js 场景（星体、星座线、晶体、标签避让）
js/app.js       数据规范化、视图图谱、作品库与分析流程接线
data/           示例与作品缓存
docs/           质量计划 QUALITY.md 与数据契约 SCHEMA.md
tools/          示例图谱生成与审阅发布工具
loop/           持续运行环境与审阅证据（先读 PROJECT-STATE.md）
tests/ · scripts/accept.sh   验收
```

---

## English

### What it is

When a novel is finished, its characters are scattered across hundreds of thousands of words. Who allied with whom, which planted hint never paid off — finding any of it again takes forever. Castline puts the book in the night sky: each character is a star, the plot coils into a ring, and clicking one person lands you inside their personal compass.

It runs locally. Start `serve.py`, open the browser, you're in. The Python standard library is all it needs — no third-party packages, and the bundled graphs are browsable without connecting any model.

### Run it

```bash
git clone <repo-url> Castline && cd Castline
python3 serve.py 8000
# open http://127.0.0.1:8000
```

It works straight out of the box — no API setup, no re-analysis. The repo ships with:

- Journey to the West and Romance of the Three Kingdoms, two public-domain classics (graphs in `data/cache/`);
- Guardian of the Great Feng, an analysis graph distributed with the repository after rights confirmation — structured data and verbatim quote anchors only, no prose;
- The Stardust Courier, a fully fictional synthetic novella (source in `data/demo_src/星尘信使/`) that demonstrates the full path from raw text to graph. To use your own book, drop the material onto the tray.

To analyze new material, connect any OpenAI-compatible or Anthropic endpoint under「工具 → API」. Credentials stay in the local `data/llm-config.json`, which is gitignored.

### The three views

- **Constellation**: the default view. Protagonists sit at the hub, each faction occupies a sector, and the bigger the role the brighter the star; a faction's reach is the nebula around it. Hover a star and everything it touches lights up.
- **Plot Disc**: toolbar「剧情」or press `P`. The whole story coils into a ring — one clockwise turn from chapter one to the last. A playback bar at the bottom steps through chapter by chapter.
- **Compass**: click any star, or search a name. The camera lands on one person: an eight-axis personality crystal at the center, three orbit rings carrying close, opposed and other relations, and the causal chain that made them along the lower arc.

### URLs to try

```
http://127.0.0.1:8000/?data=data/demo.json          # Constellation
http://127.0.0.1:8000/?data=data/demo.json&plot=1   # Plot Disc
# Compass: open either URL, then click a star (e.g. the protagonist 沈曜) or use search
```

More samples: `data/sample-focus.json` (single-character focus), `sample-mid.json`, `sample-large.json`, and `sample-saga.json` (long-form stress test).

### How the analysis runs

Short texts are read in one pass. Long texts are cut at chapter boundaries, extracted in parallel, then merged: candidates combined, aliases unified, profiles built in batches, relations resolved. A dropped stream reconnects to the same job, and finished chunks stay in `data/cache/chunks/`, so a rerun never pays for them twice.

Graph shape (full contract in [docs/SCHEMA.md](docs/SCHEMA.md)):

```text
title, synopsis,
characters[{name, aliases[], role, importance, identity, brief, traits[], camp, stance,
            attrs{wisdom|strength|will|charm|feeling|ambition|power|morality:
                  {score, evidence[], basis, low}},
            arc[{phase,text}], judgments[{kind,text,chapter}]}],
camps[{name, stance, brief}],
events[{order, chapter, title, summary, characters[], kind, quote}],
relations[{a, b, kind, strength, desc, line:explicit|implicit}],
causeEdges[{id, fromEventId, toEventId, basis, description, quote, sourceRefs[], resolved}],
clues[{id, seedEventId, payoffEventId, status, basis, sourceRefs[]}],
characterStates[{id, characterId, character, eventId, chapter, summary, attributes[],
                 quote, sourceRefs[], transition{before,after}}],
storylines[{id, name, kind:main|branch|twig, parent, attach_order, events[order], lead,
           cast[], theme, resolution:closed|open|undecided, handoff_from, handoff_reason}]
```

### API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/plan` | Plan chunks, ETA, cache reuse (no model calls) |
| POST | `/api/analyze` | SSE analysis stream `{docs, force, refresh}` |
| POST | `/api/cancel` | Cancel a job (finished chunks kept) |
| GET | `/api/jobs` · `/api/history`(+`/detail` `/docs`) | Jobs and library |
| POST | `/api/history` | `delete` `open` `rename` `pin` `note` `sweep` |
| GET/POST | `/api/llm-config` | Endpoint profiles and connectivity test |
| GET | `/api/health` | Service and build status |

### URL parameters

| Param | Purpose |
|---|---|
| `?data=data/cache/<key>.json` | Open a specific work |
| `?demo=1` | Open the bundled example (`data/demo.json`) |
| `?plot=1` | Wake the plot disc on load |
| `?layout=road` | Legacy road layout for the constellation |
| `?shell=atlas` | Legacy workspace UI (regression) |
| `?probe=1&sky=1` | Automation probe `window.__cl` |

### Verification

```bash
sh scripts/accept.sh                                                      # offline contracts & static gates
CL_GPU=1 ATLAS_BASE=http://127.0.0.1:8000 sh scripts/accept.sh --browser  # browser gates (real GPU, serial)
python3 -B -s tests/sky_shell.py --base http://127.0.0.1:8000              # single sky-shell run
```

The entry script runs every check, keeps going past individual failures, and exits non-zero with a summary. Browser checks use `tests/headless.py` (CDP, no dependencies); `CL_GPU=1` selects the real GPU, with `CL_TIMEOUT`, `CL_CDP_TIMEOUT` and `CL_READY_TIMEOUT` available. Tests never call the model and never modify `data/`.

### Layout

```
serve.py        local service + analysis pipeline (Python 3 stdlib)
narrative.py    narrative structure, quote grounding and context
distill.py      style distillation
index.html      single-page entry (script order enforced by tests/script_manifest.json)
js/sky/         sky UI: read layer (SVG/DOM) + light layer (WebGL)
js/scene.js · js/core/   three.js scene (stars, constellation lines, crystal, label avoidance)
js/app.js      data normalization, view graph, library and analysis wiring
data/          samples and work cache
docs/          quality plan QUALITY.md and data contract SCHEMA.md
tools/          example-graph generator and review publishing helpers
loop/           continuous-run harness and review evidence (start with PROJECT-STATE.md)
tests/ · scripts/accept.sh   verification
```

---

## 质量与边界

评分、已完成的改造和剩余缺口都在 [docs/QUALITY.md](docs/QUALITY.md)。有一点说在前面：**图谱能浏览，不代表全书已经审完**——解析覆盖和证据状态以每部作品内的标注为准；由同场次数推导出来的关系，图例里会明写「同场 · 推导」。

See [docs/QUALITY.md](docs/QUALITY.md) for the current scorecard. One caveat worth stating up front: **a browsable graph is not a fully audited analysis** — coverage and evidence status are annotated inside each work, and relations derived from co-occurrence are labeled「同场 · 推导」(derived, co-occurrence) in the legend.
