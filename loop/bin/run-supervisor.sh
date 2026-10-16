#!/bin/bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1

LOG="$ROOT/loop/state/logs/supervisor.console.log"
mkdir -p "$(dirname "$LOG")"

if pgrep -f "loop/bin/supervisor.py" >/dev/null 2>&1; then
  echo "监督者已在运行，跳过。"
  exit 0
fi

nohup python3 -B -s "$ROOT/loop/bin/supervisor.py" \
  >>"$LOG" 2>&1 &
disown 2>/dev/null || true
sleep 2
if pgrep -f "loop/bin/supervisor.py" >/dev/null 2>&1; then
  echo "监督者已启动（pid $(pgrep -f 'loop/bin/supervisor.py' | head -1)），日志 $LOG"
else
  echo "监督者启动失败，请查看 $LOG"
  exit 1
fi
