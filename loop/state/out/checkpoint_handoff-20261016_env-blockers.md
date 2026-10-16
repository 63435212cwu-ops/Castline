# 交接检查点 · 2026-10-16 接手发现（环境阻塞）

记录时间：2026-10-16 13:00–14:10 CST（Asia/Shanghai）。作者：主线程（本次会话）。
本文件是**排查记录**，不是质量签收；不提任何分数。

## 一句话

视觉链（`merge:rsi-*`）整条停摆有三个独立原因，**其中两个已修，一个卡在产品回归、一个卡在用户侧凭据**。

## 关键路径（客观事实）

```
merge:rsi-motion-response:20261012   ← 前置全绿、唯一 OPEN 的阻塞点
   ↓
merge:rsi-event-compare:20261013
   ↓
merge:rsi-state-parallel:20261013
   ↓
merge:rsi-order-direction:20261013
   ↓
merge:rsi-state-range:20261013
```

下游四张卡的 `build:*` 全部 DONE（`visual-build` 22/22），只等上游合入。
`merge:rsi-motion-response:20261012` 的代码**已在工作树里**：
- `js/sky/sky-shell.js` = `3fc33770…`（与检查点一致）
- `js/sky/sky-shell-player.js` = `70cd21701…`（一致）
- `js/sky/sky-chrome.js` / `index.html` 已被更晚的改动推进过

## 原因 1 · 所有预览服务都死了（**已修**）

接手机器上 `8765/8000/8781/8002` **全无监听**。已恢复：

```sh
nohup python3 -s serve.py 8765 > loop/state/logs/serve-8765.console.log 2>&1 < /dev/null & disown
```

注意 **macOS 没有 `setsid`**（`nohup setsid …` 会直接报错）。接手先做：

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/
```

否则会把「服务没起」误读成产品缺陷（本轮的 readiness 超时就是这么来的）。

## 原因 2 · dsh agent 缺凭据（**未修，需用户动作**）

worker 能领到任务，agent **11 秒 rc=1 秒退**，任务进 900s 指数退避。逐字错误：

```
dsh: MISSING_CREDENTIAL: llm-deepseek: no API key for provider route "deepseek-official";
store DEEPSEEK_API_KEY through the credentials service (the web Models page writes it),
or export DEEPSEEK_API_KEY in the launching environment
```

- 环境变量里**确实没有** `DEEPSEEK_API_KEY`（有 `ANTHROPIC_API_KEY`/`SU8_API_KEY`，不是这条路由要的）。
- 排期侧同因：GUARD-LOG 记「排期 agent=dsh 疑似不可用：经排期仍被『自有档无账号』挡」。
- **需要用户**：设置 › 线路/全局档位 切到「平台」，或把 key 写进凭据服务／导出到启动环境。

## 原因 3 · 应用自身把浏览器主线程卡死（**真回归，未定位到行**）

这是本轮最重要的发现。判据链（每一步都可复跑）：

| 假设 | 实验 | 结果 |
|---|---|---|
| 是数据问题 | 三书 `?sky=1&data=…` | 全部阻塞 ⇒ 否 |
| 是服务问题 | `curl` 首页/资源/`/api/*` | 全部 200、0.001s ⇒ 否 |
| 是 CPU 争用 | 停掉 19 个 worker（load 9.0→4.5）| 仍阻塞 ⇒ 否 |
| 只是慢 | `--timeout 240` | 240.9s 无返回 ⇒ 否 |
| 是无头浏览器坏了 | 加载 `data:text/html,<h1>` 空白页 | 正常（30.3s 就绪轮询正常返回）⇒ 否 |
| 是 WebGL / Metal | 极小 WebGL2 页面 | 正常，无 CDP-BUSY ⇒ 否 |
| **是应用脚本** | 旧壳 `shell=atlas`、首页、`demo=1` | **全部阻塞** ⇒ **是** |

- 表现：`CDP-BUSY · 页面主线程仍被同步阻塞`；`documentState` 已是 `complete`，即文档加载完了、是脚本卡住。
- 最早一次可控观察：13:01 的 `sky_story_browser.py --motion-e1` **成功加载了西游并渲染出星盘**
  （有 PNG 证据 `e1-01-entity.png` / `e1-02-structure.png`），三条 check 通过后，
  卡在 `e1-02-structure` 之后那次 `dwell()`（`await_promise` 永不返回）。此后连冷加载也一起卡。
- Chrome 版本 **155.0.8059.82**，启动时报 `CVDisplayLinkCreateWithCGDisplay failed (-6670)`。

**嫌疑范围**：**10-15 18:46–18:54** 改动的 cinema 栈 ——
`js/sky/sky-chrome.js`、`js/atlas/atlas-cinema.js`、`js/atlas/mystic-ritual.js`、
`js/atlas/atlas-motion-polish.js`、`css/cinema-depth.css`、`css/atlas-fallback.css`、`index.html`。
（`nativeSky()`/`active()` 跳过重复模糊层的守卫**仍在**，尚未证伪其充分性；
`cinema-depth.css` 有 `filter: blur(30px)`、`atlas-fallback.css` 有 `backdrop-filter: blur(20px)` 的全屏层。）
这与接手记录里「冷加载环境原因尚未签定」是同一件事。

**建议下一步**：在浏览器里对该栈逐层禁用做二分，或先 `git diff a008cb8 -- js/atlas js/sky/sky-chrome.js css/cinema-depth.css index.html`。
在此之前，**任何「原生 sign-off」都不可信**——仪器不通，结论不通。

## 本轮已跑通的门禁

- `sh scripts/accept.sh`（经外置盘 wrapper）→ **133/133 PASS**。
  日志：`/Volumes/资源库/我的资源/回滚点/项目/星系-ac256e2134/20261016-125203-543829-11962/`

## 副作用与清理

`sky_story_browser.py` 的 `Page.startScreencast(everyNthFrame=1)` **无帧数上限**：
卡住期间仍按 ~16–50fps 写 JPEG，26 分钟写满 **78,218 帧 / 8.9GB**。
已删除该 frames 目录（仅此次运行）。**后续跑该测试务必设外层墙钟上限**。

## 当前环境状态（本文件写下时）

- `serve.py 8765` **在跑**（可手工看图）。
- worker / supervisor / sentinel **已停**（无凭据时只会空转并饿死浏览器验证）。
  恢复：`sh loop/bin/run-supervisor.sh`（先补凭据，否则无意义）。

## 与用户原始诉求的关系

用户要的是三大图谱的电影级观感（前一轮审计给 71/100，7 项差距）。
本轮**没有**推进观感改动：在浏览器验证不可用、且自动化流水线无凭据的前提下，
盲改 shader 只会产生无法验证的改动 —— 这与 PLAN 的「不以静态门代替艺术验收」相冲突。
先把上面两条打通，视觉线才能真正往前跑。

---

# 更正 · 2026-10-16 14:10–14:30（同作者）

上面「原因 3 · 应用自身把浏览器主线程卡死（真回归）」**结论错误**，已用分层实验证伪。
原文保留作审计痕迹。**产品没有冻结，也没有 cinema 栈回归。**

## 决定性事实表（同机、同服务、逐个消变量）

| 配置 | 实测 |
|---|---|
| `CL_GPU=1`（Metal）裸页 `/`，冷启 | **READY 44.2s**，`jserr/jsrej: none`、`shaderErrors: []` |
| `CL_GPU=1`（Metal）真实书 `?sky=1&data=ed3dc…` | **READY 3.9s**，零错误 |
| 默认 **SwiftShader** 裸页 | `CDP-BUSY` 112.2s / 271.6s（单次 CDP 调用 >100s） |
| `CL_GPU=1` `--motion-e1` | **加载成功、连过 4 项 check**、写出 `e1-01/e1-02` PNG |

⇒ 原先那张「实验表」里最后一行的归因（旧壳/首页/demo 全部阻塞 ⇒ 是应用脚本）**不成立**：
那些实验**全部是在 SwiftShader 下跑的**。`scripts/accept.sh` 的浏览器段本来就有
`export CL_GPU="${CL_GPU:-1}"`（第 481 行），只有我手工直调 `tests/headless.py` 时漏了 `CL_GPU=1`，
退回软件渲染，于是把「软件渲染下编译着色器 >100s」读成了「主线程冻结」。
`headless.py` 的报错文本自己就写着成因与解法：「（聚焦态 + pump/warm 常见），不是页面崩溃。抬高 --timeout」。

## 真正的根因：孤儿 Chrome 泄漏（已定位并修）

接手时 `load average 22.76`，两只孤儿 Chrome：
`…/20261016-140642-310342-41310/临时/castline-cdp-41310`（属主已死）与 `…/T/castline-cdp-43661`，
合计 **~850% CPU**。它们是把运行 `perl alarm` 砍掉后 `finally` 没跑到留下的。

**为什么 `reap_orphans()` 收不到 —— 这是本仓一个结构性前提错误**：
它只 glob **自己**的 `tempfile.gettempdir()`，而经 `run-with-storage.py` 运行时
**每次运行都换一个 TMPDIR**（`<回滚点>/项目/<proj>/<ts>-<pid>/临时/`）。
⇒ 上一次运行的孤儿**永远不在**下一次运行的扫描范围内。判据（属主已死才收）没错，**错的是发现渠道**。

已修：改为从**进程表**发现（`ps -Aww` + `--user-data-dir=(\S*?/castline-cdp-(\d+))`），判据不变。
扩测 `tests/headless_health_contract.py::ProfileReaping`（两个不同运行根、活属主/无权限/自己/
非数字后缀/无关 profile 共 7 例），`headless_health_contract` **38/38 通过**。

## 另外两个已修缺陷

1. **无上限录制**（`sky_story_browser.py` 的 `RecordingWS`）：`everyNthFrame=1` 无帧数上限，
   26 分钟 78,218 帧 / 8.9GB。已加 **600 帧上限**，到顶**帧时间线仍全记**（`path=None` 只留时间戳）
   并主动 `stopScreencast`。实测：**600 帧 / 74MB**（降 120×），`recording.json` 里
   `frameCap/savedFrames/timelineOnlyFrames` 三项自证。
2. **`ready()` 90s 预算硬编码、超时无诊断**：已加 `CL_READY_TIMEOUT` 覆盖 + **逐项报出缺哪一项**。

## 仍未解决（下一步，有明确证据）

- `CL_GPU=1 --motion-e1` 走到 `openCompass("孙悟空")` 之后的 `dwell()` 时，
  **单次 CDP 调用超过 `Wave2AuditRunner` 硬编码的 60s 上限**（`qa_cinema_wave02_capture.py:66`）。
  已把该超时改为 `CL_CDP_TIMEOUT` 可覆盖（默认仍 60）。**下一次以 `CL_CDP_TIMEOUT=240` 复跑**，
  用以区分两种可能：(a) 真实罗盘路径的主线程同步占用确实很长（性能问题，值得单独立卡）；
  (b) 仍在受机器争用影响。**在区分出来之前，不要断言是哪一种。**
- dsh 凭据（原因 2）不变，仍需用户动作。

- 断言修正：本文件第 88 行「任何『原生 sign-off』都不可信——仪器不通，结论不通」**撤销**。
  仪器是通的（见上表）；不通的是**我一开始用错了渲染路径**。
