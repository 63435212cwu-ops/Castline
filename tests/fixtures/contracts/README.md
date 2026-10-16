# 必要契约夹具

这些 32 份 JSON 是既有门禁直接读取的三书数据快照，来自 2026-10-07 的实际离线构建。它们不包含原文全文、图片、日志或评分文件。旧审查产物已移到项目外；门禁不得依赖该归档，也不得因夹具缺失静默跳过。

| 目录 | 生成来源（tools/plan100/ 下） | 当前读者 |
| --- | --- | --- |
| source-index（3 份） | build_source_index.py | source_index_contract.py；任务/叙事构建器的章节定位 |
| coverage（3 份） | build_source_index.py | source_index_contract.py |
| narrative（19 份） | build_task_state_machines.py、build_narrative_layers.py、storyline_diagnosis.py | task_state_machine_contract.py、narrative_layers_contract.py、journey_timeline_contract.js |
| animation（1 份） | build_journey_timeline.py | journey_timeline_contract.js |
| visual（3 份） | dna_census.py | dna_census_contract.py |
| projection（2 份） | projection_probe.js、channel_audit.js | sky_identity_projection_contract.js、sky_channel_semantics_contract.js |
| material（1 份） | material_layer_inventory.py | material_layers_contract.js；material_layer_inventory.py --check |

生成器的历史编号仅用于保持可重放来源；它们不代表当前待办或完成度。JSON 内历史 provenance 路径保留为当时记录，测试通过上表中的当前路径读取。

更新条件：对应真实图谱、原文版本、定位算法、叙事投影、播放器停点或材质注册表发生变化时，先通过项目统一外置存储入口运行生成器，在本次 `CL_ARTIFACTS` 中重建候选，核对原文偏移/语义差异及文件摘要，再更新受影响夹具。不得为消除失败直接放宽断言或自动重置基线。门禁仍独立读取当前 data/cache 原文和图谱；夹具不能代替当前数据的校验，也不能证明全文解析或审美达标。

`sh scripts/accept.sh` 验证这些夹具及实际源码；默认只做 CPU 验证，不写此目录。执行生成器前使用 `python3 -B /Volumes/资源库/我的资源/回滚点/工具/run-with-storage.py --project /Users/carmen/Desktop/星系 -- <生成命令>` 设置本次 `CL_ARTIFACTS`、`CL_SHOTS` 与 `CL_ROLLBACK`；外置盘不可用时停止。显式 `--out`、`--json` 也必须指定本次外置目录。报告与截图保存在对应外置目录。新增夹具必须有明确读者；不再被测试读取时，连同来源说明移到项目外归档。
