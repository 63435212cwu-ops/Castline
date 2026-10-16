#!/usr/bin/env python3
"""监督者（supervisor）：保证「守护轮」这个主进程本身不会静默死亡。

## 为什么需要它

本项目的形态反复是**「进程活着 ≠ 在干活」**，但反过来也真发生过：
**主进程死了没人知道，整条流水线停摆。**

实测证据（2026-10-10 核对 `loop/state/GUARD-HISTORY.jsonl`，325 条记录）：
守护轮存在 5 处 >15 分钟的空洞，最长 **378 分钟（6.3 小时）**：

    10-08 20:59 → 21:50   51 分钟
    10-08 21:50 → 22:10   19 分钟
    10-08 22:10 → 10-09 04:28  378 分钟   ← 最长
    10-09 04:28 → 04:48   20 分钟
    10-09 13:11 → 14:16   65 分钟

空洞期间 worker 日志**仍在更新**（最长那次有 184 个日志在写），说明
worker 因 `start_new_session=True` 脱离了 sentinel，sentinel 死了它们还活着——
**但没有任何进程会把 sentinel 拉回来**，于是：不再补队列、不再回收死租约、
不再检测停滞、不再到点插专家复核。完成数就此冻结，直到有人手工再起。

而 OS 级兜底在这个项目上**已被实测排除**：
- `launchd` / `cron` 读 `~/Desktop` 被 macOS TCC 拒绝（本项目在 `~/Desktop` 下）。
  2026-10-10 实测：launchd 启动的进程 `cat ~/Desktop/星系/loop/bin/sentinel.py`
  → `Operation not permitted`；`ls ~/Desktop` → 同样被拒（写入反而成功，
  属 TCC 对「读」的拦截），故「读脚本再跑」这条路走不通。
- Mirasim 排期是唯一服务端时钟的跨会话机制，但本机经排期的 agent 被
  「自有档无账号」挡住（见 PROJECT-STATE §4e H1），需用户处理。

所以需要一个**本进程级**的监督者：它自己极简、只做一件事——
**发现守护轮不在跑（或心跳过期），就把它拉起来**。它由谁拉起？
由 `run-supervisor.sh`（nohup + setsid）拉起一次即可，之后自我维持。

## 判活口径（复用现有事实，不发明新状态）

优先看 `WATCHDOG.json` 的 pid 是否存活且是否新鲜；同时用 `ps` 兜底
（pid 可能被复用，且 WATCHDOG.json 可能过期）。**两个口径任一为「活」即算活**，
避免误杀正在跑的守护轮。

## 与 sentinel 的职责边界

- `sentinel.py`：干活（回收租约、拉起 worker、补队列、停滞检测、专家复核）。
- `supervisor.py`：**只看 sentinel 活着没有**，不碰 worker、不碰队列、不改状态。

纪律：本文件只做「拉起」这一个副作用，且所有动作追加写入自己的日志。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
STATE = LOOP / "state"
LOGS = STATE / "logs"
WATCHDOG = STATE / "WATCHDOG.json"
SUP_LOG = LOGS / "supervisor.log"
SENTINEL = LOOP / "bin" / "sentinel.py"

STALE_AFTER_SECONDS = 2100

_HEADLESS_STRIP_EXACT = (
    "CODEBUDDY_SESSION_ID",
    "CLAUDE_SESSION_ID",
    "CODEBUDDY_CONVERSATION_MESSAGE_ID",
    "CODEBUDDY_NODE_BIN",
)


def _strip_headless_env(env: dict) -> list:
    removed = []
    for key in list(env.keys()):
        if key in _HEADLESS_STRIP_EXACT or key.startswith("CODEBUDDY_SAFE_DELETE"):
            del env[key]
            removed.append(key)
    return removed


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = "[%s] %s" % (now(), msg)
    print(line, flush=True)
    try:
        with SUP_LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def sentinel_pids(watch_only: bool = True) -> list:
    """从 ps 找真正的守护轮进程。

    必须排除两类**假阳性**（实测踩过）：
    - `supervisor.py` 自己（命令行里也可能提到 sentinel.py）；
    - 形如 `bash -c '... sentinel.py --once ...'` 的**外挂驱动脚本**——
      它的命令行含 "sentinel.py" 字符串，但它本身不是守护主进程，
      把它算作「哨兵活着」会让监督者永远不动作（真正的守护死了也不管）。

    判据：`ps -eo pid=,command=` 的每一行是 `<pid> <argv0> <args...>`，
    要求 argv0（去掉路径后）以 `python` 开头，才算解释器直接跑的本体。

    `watch_only=True` 时只认 `--watch`（常驻守护主进程）。
    这一点是实测教训：外挂驱动每 420s 跑一次 `--once`，它会把
    `GUARD-HISTORY` 刷"新"，于是**用心跳新鲜度判断会让监督者永不复活**
    （2026-10-10 实验：杀掉 39125 后，心跳 124s「新鲜」⇒ 拒绝拉起，
    实测哨兵确实没回来）。要守的是**常驻主进程**，不是那些一次性调用。
    """
    try:
        ps = subprocess.run(["ps", "-eo", "pid=,command="], capture_output=True,
                            text=True, timeout=20).stdout
    except Exception:
        return []
    out = []
    for line in ps.splitlines():
        if "sentinel.py" not in line or "grep" in line:
            continue
        if watch_only and "--watch" not in line:
            continue
        parts = line.strip().split(None, 1)
        if len(parts) < 2:
            continue
        pid, cmd = parts[0], parts[1]
        argv0 = os.path.basename(cmd.split()[0]) if cmd.split() else ""
        if not argv0.startswith("python"):
            continue
        if "supervisor.py" in cmd:
            continue
        if pid.isdigit():
            out.append(int(pid))
    return out


def watchdog_health() -> dict:
    """读 WATCHDOG.json：pid 是否活、心跳多旧。"""
    info = {}
    try:
        info = json.loads(WATCHDOG.read_text(encoding="utf-8")) or {}
    except Exception:
        return {"present": False, "alive": False, "ageSeconds": None, "pid": None}
    pid = info.get("pid")
    age = None
    try:
        t = dt.datetime.strptime(info.get("startedAt", ""), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc).timestamp()
        age = time.time() - t
    except Exception:
        age = None
    return {"present": True, "pid": pid, "alive": pid_alive(pid) if pid else False,
            "ageSeconds": age, "raw": info}


def sentinel_running() -> tuple:
    """(是否在跑, 说明)。两个口径任一为活即算活。"""
    pids = sentinel_pids()
    if pids:
        return True, "ps 找到 sentinel pid=%s" % (pids,)
    wh = watchdog_health()
    if wh["present"] and wh["alive"]:
        return True, "WATCHDOG.json pid=%s 存活" % (wh["pid"],)
    return False, "ps 无 sentinel；WATCHDOG.json present=%s alive=%s age=%s" % (
        wh.get("present"), wh.get("alive"),
        ("%.0fs" % wh["ageSeconds"]) if wh.get("ageSeconds") is not None else "?")


def last_guard_age() -> float | None:
    """最近一次守护轮记录距今多少秒（GUARD-HISTORY.jsonl 末行）。"""
    p = STATE / "GUARD-HISTORY.jsonl"
    try:
        with p.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 4096))
            tail = fh.read().decode("utf-8", errors="replace").strip().splitlines()
        rec = json.loads(tail[-1])
        t = dt.datetime.strptime(rec["at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc).timestamp()
        return time.time() - t
    except Exception:
        return None


def spawn_sentinel(interval: int) -> str:
    """脱离本进程启动常驻守护轮（setsid，本进程死了它仍活）。"""
    LOGS.mkdir(parents=True, exist_ok=True)
    console = LOGS / "watchdog.console.log"
    env = dict(os.environ)
    _strip_headless_env(env)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [sys.executable, "-B", "-s", str(SENTINEL), "--watch", "--interval", str(interval)]
    with console.open("a", encoding="utf-8") as fh:
        fh.write("\n=== supervisor 拉起守护轮 at %s ===\n" % now())
        fh.flush()
        subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT,
                         start_new_session=True)
    return str(console)


def supervisor_pids() -> list:
    try:
        ps = subprocess.run(["ps", "-eo", "pid=,command="], capture_output=True,
                            text=True, timeout=20).stdout
    except Exception:
        return []
    out = []
    for line in ps.splitlines():
        if "supervisor.py" in line and "grep" not in line:
            pid = line.strip().split(None, 1)[0]
            if pid.isdigit():
                out.append(int(pid))
    return out


def single_instance() -> bool:
    """同一时刻只允许一个监督者（否则会重复拉起 sentinel）。"""
    me = os.getpid()
    others = [p for p in supervisor_pids() if p != me]
    if others:
        return False
    return True


def once(interval: int, stale_after: int) -> dict:
    """检查一次。

    **判活只认 `--watch` 常驻主进程**（见 sentinel_pids 的说明）。
    早先版本还看「心跳是否新鲜」，但外挂驱动每 420s 跑一次 `--once`
    会刷新 GUARD-HISTORY，于是杀掉主进程后心跳仍"新鲜"⇒ 拒绝复活
    ⇒ 主进程再也不回来（2026-10-10 实验实测）。故这里**不再用心跳放宽**，
    心跳只作为报告字段，供人判断「主进程死了多久」。
    """
    pids = sentinel_pids(watch_only=True)
    age = last_guard_age()
    out = {"at": now(), "sentinelRunning": bool(pids), "sentinelPids": pids,
           "lastGuardSecondsAgo": round(age, 1) if age is not None else None,
           "action": None}
    if pids:
        out["action"] = "none(守护主进程在跑 pid=%s)" % (pids,)
        return out
    console = spawn_sentinel(interval)
    out["action"] = "respawned"
    out["console"] = console
    log("守护主进程不在跑（最近守护记录 %.0fs 前）⇒ 已重新拉起"
        % (age if age is not None else -1))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="守护轮监督者：保证主进程不会静默死亡")
    ap.add_argument("--once", action="store_true", help="只检查一次（适合被排期/cron 调用）")
    ap.add_argument("--interval", type=int, default=None,
                    help="守护轮自身的轮询秒数（默认读 policy.guardEveryMinutes×60）")
    ap.add_argument("--check-every", type=int, default=120, help="监督者多久检查一次（秒）")
    ap.add_argument("--stale-after", type=int, default=STALE_AFTER_SECONDS,
                    help="心跳多久算过期（秒）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    _strip_headless_env(os.environ)
    if args.interval is None:
        try:
            import json as _json
            pol = _json.loads((STATE / "policy.json").read_text(encoding="utf-8"))
            args.interval = int(pol.get("guardEveryMinutes", 10)) * 60
        except Exception:
            args.interval = 600

    if args.once:
        out = once(args.interval, args.stale_after)
        print(json.dumps(out, ensure_ascii=False))
        return 0

    if not single_instance():
        log("已有监督者在跑，本进程退出（避免重复拉起）")
        return 0

    log("监督者启动：每 %ds 检查一次（pid=%d，stale=%ds）"
        % (args.check_every, os.getpid(), args.stale_after))
    try:
        while True:
            try:
                once(args.interval, args.stale_after)
            except Exception as exc:
                log("检查异常：%r" % (exc,))
            time.sleep(max(20, args.check_every))
    except KeyboardInterrupt:
        log("监督者收到 Ctrl-C，退出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
