#!/bin/sh
set -eu

cd "$(dirname "$0")/../.."
ROOT="$(pwd)"
TARGET="${1:-tests/version_stamp.py}"
OUT="$(python3 -B -c 'import sys; sys.path.insert(0, "tools/plan100"); from evidence import artifact_path; print(artifact_path("plan100/release/rollback-drill"))')"
mkdir -p "$OUT/original"
LOG="$OUT/drill.log"
: > "$LOG"

say() { printf '%s\n' "$*" | tee -a "$LOG"; }
step() { say ""; say "=== $* ==="; }

CONTRACT_A="python3 -m py_compile $TARGET"
CONTRACT_B="${3:-python3 tests/type_lint.py}"
[ -n "${2:-}" ] && CONTRACT_A="$2"

FAILED=0
WARNED=0
fail() { say "FAIL: $*"; FAILED=1; }
warn() { say "WARN: $*"; WARNED=1; }

sha() { python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1"; }

RC=0
run_contract() { # $1=标签 $2=命令
  label="$1"; cmd="$2"
  clog="$OUT/contract-$(echo "$label" | tr ' /' '__').log"
  started=$(date +%s)
  sh -c "$cmd" > "$clog" 2>&1 && RC=0 || RC=$?
  if [ "$RC" = 0 ]; then
    say "$label: PASS · $(($(date +%s) - started))s · $(wc -l < "$clog" | tr -d ' ') lines → ${clog#$ROOT/}"
  else
    say "$label: FAIL · exit $RC · $(($(date +%s) - started))s → ${clog#$ROOT/}"
    tail -20 "$clog" | tee -a "$LOG" > /dev/null
    tail -20 "$clog"
  fi
  return $RC
}

step "0. 环境与工作树"
HEAD="$(git rev-parse HEAD)"
say "workspace   : $ROOT"
say "utc         : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
say "HEAD        : $HEAD"
say "target      : $TARGET"
say "contractA   : $CONTRACT_A"
say "contractB   : $CONTRACT_B"
DIRTY="$(git status --porcelain | wc -l | tr -d ' ')"
CLEAN="false"; [ "$DIRTY" = "0" ] && CLEAN="true"
say "working tree: clean=$CLEAN dirty_lines=$DIRTY"
if [ "$CLEAN" != "true" ]; then
  say "NOTE: 工作树非空（并行代理有未提交改动）。本演练只用定向补丁，绝不 reset --hard。"
fi
git status --porcelain > "$OUT/worktree-before.txt"
say "worktree snapshot → ${OUT#$ROOT/}/worktree-before.txt"

if [ ! -f "$TARGET" ]; then fail "目标文件不存在：$TARGET"; exit 2; fi
if ! git ls-files --error-unmatch "$TARGET" > /dev/null 2>&1; then
  fail "目标文件未被 git 跟踪，无法用定向补丁回滚：$TARGET"; exit 2
fi
if ! git diff --quiet -- "$TARGET"; then
  fail "目标文件已有未提交改动（可能其他代理正在改）；拒绝演练以免覆盖他人工作：$TARGET"
  exit 2
fi
say "precheck    : 目标文件干净且被跟踪 ✓"

ORIG_SHA="$(sha "$TARGET")"
cp "$TARGET" "$OUT/original/$(basename "$TARGET")"
say "sha256 before: $ORIG_SHA"
say "original copy → ${OUT#$ROOT/}/original/$(basename "$TARGET")"

step "1. 基准对照：未改动状态跑契约"
BASE_A=0; BASE_B=0
run_contract "baseline-contract-A" "$CONTRACT_A" || BASE_A=$RC
run_contract "baseline-contract-B" "$CONTRACT_B" || BASE_B=$RC
say "baseline exit: A=${BASE_A} B=${BASE_B} (0=PASS)"

step "2. 应用最小改动"
MARK="plan100-p12-rollback-drill-marker"
if grep -q "$MARK" "$TARGET"; then
  fail "目标文件已含演练标记，上一次演练未清理；请先人工检查"
  exit 2
fi
printf '\n# %s %s\n' "$MARK" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$TARGET"
NEW_SHA="$(sha "$TARGET")"
say "sha256 after : $NEW_SHA"
if [ "$ORIG_SHA" = "$NEW_SHA" ]; then fail "改动未生效（哈希相同）"; else say "改动生效 ✓ (hash 变化)"; fi

git diff -- "$TARGET" > "$OUT/drill.patch"
PATCH_BYTES="$(wc -c < "$OUT/drill.patch" | tr -d ' ')"
say "patch       : ${OUT#$ROOT/}/drill.patch · ${PATCH_BYTES} bytes"
if [ "$PATCH_BYTES" -lt 1 ]; then fail "补丁为空，无法回滚"; exit 2; fi
if ! git apply --check -R "$OUT/drill.patch" 2>>"$LOG"; then
  fail "补丁无法反向应用（dry-run 失败）"
  exit 2
fi
say "reverse-apply dry-run ✓"
if ! grep -q "$MARK" "$TARGET"; then fail "标记未出现在文件中"; exit 2; fi

step "3. 验证：改动在位时跑契约"
DIRTY_A=0; DIRTY_B=0
run_contract "dirty-contract-A" "$CONTRACT_A" || DIRTY_A=$RC
run_contract "dirty-contract-B" "$CONTRACT_B" || DIRTY_B=$RC

step "4. 回滚（定向反向补丁）"
CUR_SHA="$(sha "$TARGET")"
if [ "$CUR_SHA" != "$NEW_SHA" ]; then
  fail "目标文件被并发改动（期望 $NEW_SHA，实际 $CUR_SHA）；中止回滚，不触碰该文件"
  exit 2
fi
say "concurrency check: 文件仍为本轮写入内容 ✓"
if git apply -R "$OUT/drill.patch"; then
  say "git apply -R ✓"
else
  fail "git apply -R 失败"
fi

ROLLED_SHA="$(sha "$TARGET")"
say "sha256 rolled: $ROLLED_SHA"
if [ "$ROLLED_SHA" = "$ORIG_SHA" ]; then
  say "逐字节还原 ✓"
else
  fail "回滚后哈希与原始不一致（期望 $ORIG_SHA，实际 $ROLLED_SHA）"
fi
if git diff --quiet -- "$TARGET"; then
  say "git diff 干净 ✓"
else
  fail "回滚后目标文件仍有 diff"
  git diff -- "$TARGET" >> "$LOG"
fi
if grep -q "$MARK" "$TARGET"; then fail "回滚后标记仍在文件中"; else say "标记已消失 ✓"; fi

step "5. 回滚后重跑同一批契约"
ROLL_A=0; ROLL_B=0
run_contract "rolledback-contract-A" "$CONTRACT_A" || ROLL_A=$RC
run_contract "rolledback-contract-B" "$CONTRACT_B" || ROLL_B=$RC

step "6. 契约对照判定（区分「本演练引入」与「预先存在」）"
judge() { # $1=名字 $2=baseline $3=dirty $4=rolled
  name="$1"; b="$2"; d="$3"; r="$4"
  if [ "$b" = 0 ] && [ "$r" != 0 ]; then
    fail "${name}：基准 PASS、回滚后 FAIL → 本演练确实破坏了契约"
  elif [ "$b" != 0 ] && [ "$r" != 0 ]; then
    warn "${name}：基准即 FAIL、回滚后仍 FAIL → 预先存在/并行改动导致，非本演练引入"
  elif [ "$b" = 0 ] && [ "$r" = 0 ] && [ "$d" != 0 ]; then
    warn "${name}：改动在位时 FAIL、回滚后恢复 PASS → 契约确实对本次改动敏感（回滚有效）"
  else
    say "${name}：基准 PASS · 改动在位 PASS · 回滚后 PASS ✓"
  fi
}
judge "contract-A（目标文件编译）" "$BASE_A" "$DIRTY_A" "$ROLL_A"
judge "contract-B（全树静态门）" "$BASE_B" "$DIRTY_B" "$ROLL_B"

step "7. 其他代理的工作未被触碰"
git status --porcelain > "$OUT/worktree-after.txt"
if diff -u "$OUT/worktree-before.txt" "$OUT/worktree-after.txt" > "$OUT/worktree-diff.txt" 2>&1; then
  say "工作树其它部分与演练前一致 ✓"
else
  if grep -v -- "$TARGET" "$OUT/worktree-diff.txt" | grep -qE '^[-+][^-+]'; then
    fail "演练期间有其他文件变化（见 worktree-diff.txt）"
    cat "$OUT/worktree-diff.txt" >> "$LOG"
  else
    say "仅目标文件行出现差异（已还原）✓"
  fi
fi

RESULT="passed"; [ "$FAILED" -ne 0 ] && RESULT="failed"
[ "$FAILED" -eq 0 ] && [ "$WARNED" -ne 0 ] && RESULT="passed-with-warnings"

python3 - "$OUT" "$RESULT" "$HEAD" "$TARGET" "$ORIG_SHA" "$NEW_SHA" "$ROLLED_SHA" \
         "$CLEAN" "$DIRTY" "$BASE_A" "$BASE_B" "$DIRTY_A" "$DIRTY_B" "$ROLL_A" "$ROLL_B" \
         "$CONTRACT_A" "$CONTRACT_B" <<'PY'
import json, sys, datetime
(a, result, head, target, o, n, r, clean, dirty,
 bA, bB, dA, dB, rA, rB, cA, cB) = sys.argv[1:18]
data = {
    "drillVersion": "plan100/p12/2",
    "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "result": result,
    "head": head,
    "target": target,
    "sha256Before": o,
    "sha256AfterChange": n,
    "sha256AfterRollback": r,
    "byteIdenticalAfterRollback": (o == r),
    "workingTreeCleanAtStart": clean == "true",
    "workingTreeDirtyLinesAtStart": int(dirty),
    "contracts": {
        "A": {"command": cA, "baselineExit": int(bA), "dirtyExit": int(dA), "rolledBackExit": int(rA)},
        "B": {"command": cB, "baselineExit": int(bB), "dirtyExit": int(dB), "rolledBackExit": int(rB)},
    },
    "verdictRule": {
        "baselinePass+rolledBackFail": "本演练破坏了契约 → failed",
        "baselineFail+rolledBackFail": "预先存在/并行改动导致 → warning",
        "baselinePass+rolledBackPass": "通过",
    },
    "steps": ["record HEAD", "baseline control run", "apply minimal change",
              "verify (contracts with change in place)", "rollback via git apply -R",
              "re-run same contracts", "confirm no collateral change"],
    "prohibited": ["git reset --hard", "git checkout -- .", "git stash"],
    "log": a + "/drill.log",
}
open(a + "/latest.json", "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
print("latest.json written")
PY

step "结论"
say "ROLLBACK DRILL: $RESULT"
say "逐字节还原: $([ "$ORIG_SHA" = "$ROLLED_SHA" ] && echo yes || echo NO)"
say "log: ${OUT#$ROOT/}/drill.log"
[ "$FAILED" -eq 0 ] || exit 1
exit 0
