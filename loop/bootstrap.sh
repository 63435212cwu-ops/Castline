#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}

echo "[1/6] 检查依赖"
command -v "$PY" >/dev/null || { echo "缺 python3" >&2; exit 1; }
command -v dsh  >/dev/null || { echo "缺 dsh（DeepSeek Harness CLI）" >&2; exit 1; }
dsh --profile castline --help >/dev/null 2>&1 || {
  echo "缺 dsh profile 'castline'。创建方式："
  echo "  cp -R \"\$DSH_HOME/profiles/headless\" \"\$DSH_HOME/profiles/castline\""
  echo "  再把 agent-default-model 写进 \$DSH_HOME/profiles/castline/cordis.patch.yml"
  exit 1
}

echo "[2/6] 构建稀疏索引（1133 个原文单元）"
$PY -B -s loop/bin/build_plan.py --index

echo "[3/6] 生成任务队列（已存在的不重复添加）"
$PY -B -s loop/bin/build_plan.py --all-batches --ops

echo "[4/6] 接入 plan100 既有工作"
$PY -B -s loop/bin/adopt_plan100.py

echo "[5/6] 回收陈旧租约"
$PY -B -s loop/bin/loop.py reap

echo "[6/6] 跑一轮守护（拉起 worker）"
$PY -B -s loop/bin/sentinel.py --once

echo
echo "完成。常用命令："
echo "  sh loop/run.sh status     # 看进度"
echo "  sh loop/run.sh stop       # 停 worker"
echo "  tail -f loop/state/GUARD-LOG.md"
