#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}

case "${1:-status}" in
  status)
    $PY -B -s loop/bin/loop.py stats
    echo
    echo "--- worker 进程 ---"
    pgrep -fl "worker.py --agent" | sed -E 's/^([0-9]+) .*(--agent [^ ]+).*/\1 \2/' || echo "（没有 worker 在跑）"
    echo
    echo "--- worker 活性 ---"
    $PY -B -s loop/bin/doctor.py 2>/dev/null | head -3 || true
    echo
    echo "--- 常驻守护 ---"
    if [ -f loop/state/WATCHDOG.json ]; then cat loop/state/WATCHDOG.json; else echo "（未启动；sh loop/run.sh watchdog 可起）"; fi
    echo
    echo "--- 最近一轮守护 ---"
    tail -n 20 loop/state/GUARD-LOG.md 2>/dev/null || echo "（还没有守护记录）"
    ;;
  guard)
    $PY -B -s loop/bin/sentinel.py --once
    ;;
  watchdog)
    mkdir -p loop/state/logs
    if pgrep -f "sentinel.py --watch" >/dev/null 2>&1; then
      echo "已有常驻守护在跑：$(pgrep -fl 'sentinel.py --watch' | head -1)"
      exit 0
    fi
    nohup $PY -B -s loop/bin/sentinel.py --watch --interval "${2:-600}" \
      > loop/state/logs/watchdog.console.log 2>&1 &
    sleep 3
    echo "常驻守护已启动（每 ${2:-600} 秒一轮）：$(pgrep -fl 'sentinel.py --watch' | head -1)"
    echo "日志：loop/state/logs/watchdog.console.log    状态：loop/state/WATCHDOG.json"
    echo "跨会话持久化仍需 Mirasim 排期（见 loop/SCHEDULE.md）——本守护只在机器醒着且进程未被清理时有效。"
    ;;
  unwatch)
    pkill -f "sentinel.py --watch" && echo "常驻守护已停" || echo "没有常驻守护在跑"
    rm -f loop/state/WATCHDOG.json loop/state/GUARD.lock
    ;;
  stop)
    names=$($PY -c "import json;print(' '.join(w['name'] for w in json.load(open('loop/state/policy.json'))['workers']))")
    for n in $names; do
      if pkill -f "worker.py --agent $n" 2>/dev/null; then
        echo "已通知退出：$n（当前任务结束后停止）"
      fi
    done
    rm -f loop/state/GUARD.lock
    ;;
  task)
    $PY -B -s loop/bin/loop.py next --agent "${2:-me}"
    ;;
  doctor)
    $PY -B -s loop/bin/doctor.py
    ;;
  logs)
    ls -t loop/state/logs/*.log 2>/dev/null | head -5 | while read -r f; do
      echo "=== $f"
      tail -n 15 "$f"
    done
    ;;
  *)
    echo "用法：sh loop/run.sh [status|guard|watchdog|unwatch|stop|task|logs|doctor]" >&2
    exit 2
    ;;
esac
