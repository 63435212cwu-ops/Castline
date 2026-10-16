#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

FAILED=0
run() {
  _name="$1"; shift
  printf '[%s] %s\n' "$_name" "$*"
  if "$@"; then
    printf '  PASS\n'
  else
    _code=$?
    printf '  FAIL · exit %s\n' "$_code"
    FAILED=$((FAILED + 1))
  fi
}

run selftest  $PY -B -s loop/bin/selftest.py
run doctor    $PY -B -s loop/bin/doctor.py
run stats     $PY -B -s loop/bin/loop.py stats

if [ "$QUICK" -eq 0 ]; then
  run evidence $PY -B -s loop/bin/verify_evidence.py
fi

if [ "$FAILED" -ne 0 ]; then
  echo "LOOP ACCEPT: $FAILED 项失败"
  exit 1
fi
echo "LOOP ACCEPT: 全部通过（这是环境自身的门，不等于产品验收）"
