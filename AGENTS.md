# Castline 工作约定

- 唯一有效质量计划是 `docs/QUALITY.md`；技术数据契约见 `docs/SCHEMA.md`。不要恢复已移出的旧计划、评分副本或阶段报告。
- 测试运行产物、截图、一次性探针与回滚备份统一存入本机外置产物盘的回滚点目录；运行前用统一入口脚本（run-with-storage.py，路径由本机配置提供）设置 `CL_ARTIFACTS`、`CL_SHOTS`、`CL_ROLLBACK`。外置盘不可用则停止，不能回退源目录或 /tmp。正式测试源码、必要夹具保留。用户已明确保留另一个正在运行的任务；其现用 `artifacts/` 是运行依赖，结束前不得删除、搬迁或覆盖，且不入Git。
- 原文、已发布图谱版本和用户配置保留；新审阅内容通过既有发布工具生成新键。引用定位与语义正确性分别标注。
- 同一文件只设一个写入负责人；GPU测试串行。其他会话仍在运行时先协调，不能相互恢复目录或覆盖工作。
- 扩展现有责任测试；缺必要夹具须失败，不能静默跳过。新增测试脚本需说明现有测试无法承载的独立责任。
- JS/CSS变更后运行 `python3 -B -s tests/version_stamp.py --write`；完成相关真实页面路径及 `sh scripts/accept.sh`。测试通过数不换算成审美/内容评分。
- **持续运行环境在 `loop/`**：接手先读 `loop/PROJECT-STATE.md`（现在在哪）→ `loop/README.md`（怎么用）。
  并行任务用 `python3 -B -s loop/bin/loop.py next --agent <名字> --claim` 领取，**不要自己挑活**。
  守护轮用 `python3 -B -s loop/bin/sentinel.py --once`；环境自检 `python3 -B -s loop/bin/selftest.py`。
  worker 只做追加式写入（`loop/`、`artifacts/`）；`js/ css/ index.html serve.py narrative.py scripts/ tests/ docs/ data/`
  属受保护路径，只能在合并任务里改并持 `loop/state/leases/GATE.lock`。
