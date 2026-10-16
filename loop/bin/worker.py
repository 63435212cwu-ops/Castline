#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Castline 常驻 worker：领取任务 → 起一个 dsh headless agent → 校验提交 → 循环。

一个 worker 只服务一条通道（lane），所以：
  * 同一原文区间不会被两个 agent 同时精读；
  * 每个 worker 是独立进程，崩掉不影响别人（watchdog 会重拉）。

为什么不给 worker 开 git worktree（重要取舍，写下来免得后人重犯）：
  本仓工作树有 700+ 行**未提交**的真实改动（HEAD 是 10-04 的），
  `git worktree add` 拿到的是 HEAD 版本 —— worker 会在**过时的源码**上工作，
  得出的结论和用户看到的页面不是一回事。宁可让 worker 在共享树里干活，
  用「只追加写入 + 受保护路径进合并任务 + 提交时机器校验」来保证安全。

用法：
  python3 -B -s loop/bin/worker.py --agent w-lane0            # 跑一轮
  python3 -B -s loop/bin/worker.py --agent w-lane0 --loop 4   # 连续跑 4 轮
  python3 -B -s loop/bin/worker.py --agent w-lane0 --dry-run  # 只打印将要执行的命令
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
STATE = LOOP / "state"
LOGS = STATE / "logs"
RUNS = STATE / "runs"


def load_loop_module():
    spec = importlib.util.spec_from_file_location("loopmod", LOOP / "bin" / "loop.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


loopmod = load_loop_module()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_rel(p: Path) -> str:
    """相对 ROOT 的路径；不在 ROOT 之下时退回绝对路径（不抛异常）。

    事故（2026-10-15 实测）：loop 运行时迁到外置存储后（storage-external-20261011），
    worker 日志写进外置 guard-logs 目录，`logf.relative_to(ROOT)` 抛
    `ValueError: ... is not in the subpath of ...` ⇒ **每轮任务结束后记录 run 时崩溃**、
    租约丢失、任务被反复重领，整条流水线停摆（done 冻结、每个任务 ~150s 后 TRANSPORT 失败）。
    sentinel.py 的同一处由外置壳在加载时打过补丁，worker.py 这处没有 —— 外置壳只替换
    sentinel 的 return 表达式，不过 worker 的记录构造。这里从根上修：日志在 ROOT 外
    是合法部署（外置存储），记录必须能写下去。
    """
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def log(agent: str, msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = "[%s] %s\n" % (datetime.now().strftime("%H:%M:%S"), msg)
    with (LOGS / ("%s.log" % agent)).open("a", encoding="utf-8") as fh:
        fh.write(line)
    sys.stdout.write(line)
    sys.stdout.flush()


# --------------------------------------------------------------------------- 凭据

_RELAY_CACHE = {"at": 0.0, "env": {}}
_PROBE_CACHE: dict = {}
RELAY_PROBE_TIMEOUT = 1.0
_RELAY_CACHE_TTL = 60


def _url_alive(url: str, timeout: float = RELAY_PROBE_TIMEOUT) -> bool:
    """这个 relay base URL 现在还有人在监听吗（TCP 连接，不猜）。

    为什么必须**实际连一下**：见 `discover_runtime_env` 的事故说明 ——
    本机同时残留多个已退出会话的 `dsh web` 进程，它们的命令行环境里**照样**带着
    一个 base URL，但那个端口早已随会话关闭。只读环境变量无法区分"活着"和"残留"。
    """
    nowt = time.time()
    hit = _PROBE_CACHE.get(url)
    if hit and nowt - hit[0] < _RELAY_CACHE_TTL:
        return hit[1]
    alive = False
    try:
        parts = urlsplit(url)
        host, port = parts.hostname, parts.port
        if host and port:
            s = socket.socket()
            s.settimeout(timeout)
            try:
                s.connect((host, port))
                alive = True
            finally:
                s.close()
    except Exception:
        alive = False
    _PROBE_CACHE[url] = (nowt, alive)
    return alive


def _relay_candidates() -> list:
    """所有 `dsh web` 进程各自携带的 (URL, KEY, DSH_HOME)，按 URL 去重。

    **URL 与 KEY 必须取自同一个进程**：它们是配对的（一个 relay 只认自己那把 key），
    跨进程拼起来会得到 401 而不是"活着"。
    """
    want = {"DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DSH_PERMISSION_MODE", "DSH_HOME"}
    try:
        ps = subprocess.run(["ps", "-eo", "pid=,command="], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return []
    out, seen = [], set()
    for line in ps.splitlines():
        if "dsh" not in line or " web" not in line or "grep" in line:
            continue
        pid = line.strip().split(None, 1)[0]
        if not pid.isdigit():
            continue
        try:
            env_raw = subprocess.run(["ps", "eww", "-p", pid], capture_output=True, text=True, timeout=20).stdout
        except Exception:
            continue
        env = {}
        for tok in env_raw.split():
            if "=" in tok:
                k, _, v = tok.partition("=")
                if k in want:
                    env[k] = v
        url, key = env.get("DEEPSEEK_BASE_URL"), env.get("DEEPSEEK_API_KEY")
        if url and key and url not in seen:
            seen.add(url)
            out.append({"url": url, "key": key, "home": env.get("DSH_HOME", ""),
                        "permission": env.get("DSH_PERMISSION_MODE", ""), "pid": pid})
    return out


def discover_runtime_env() -> dict:
    """从正在运行的 dsh web 进程里取模型凭据，**只挑现在还活着的那个 relay**。

    本机模型流量走 mirasim 的本地 relay，base URL 是**每次会话随机**的
    （http://127.0.0.1:<port>/<随机路径>），不能写死。所以每次启动时重新发现：
    找 `dsh web` 进程 → 读它的环境 → 取 DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL。
    这样 Mirasim 会话重启后 worker 也能自愈，不需要有人手动改配置。

    ── 事故：**残留会话的 relay 让整条流水线停摆**（2026-10-10 16:10 实测，E38）──
    旧版取的是"**看到的第一个**带凭据的 `dsh web` 进程"，**从不探活**。
    实测本机同时残留 **9 个** `dsh web` 进程，其中只有 **1 个** relay 还在监听：

        pid     home      relay 端口  监听   探活
        3302    8964a6e2      56049   False  URLError     ← 旧版挑中的就是它
        28740   6e35a1f3      55256   True   HTTP 200
        28260   b7bb4e17      54448   False  URLError
        （其余 6 个同类）

    `ps` 的输出顺序决定了挑中谁，于是 worker 拿到一个**早已关闭的端口**，
    每个任务都在 ~16 秒内以 `dsh: TRANSPORT: DeepSeek Messages transport failed` 失败。
    对照实验（同一 DSH_HOME、同一 key、只换 base URL）：

        死 relay  → rc=1  16.3s  TRANSPORT: DeepSeek Messages transport failed
        活 relay  → rc=0   4.8s  正常返回

    这正是 E23/E28/E31/H1b 的同一形态：**环境整体停摆，却被读成"最近很多任务很难"**。
    它与账号档位问题（H1b，真实存在但已不是当前主因）**可区分**：
    账号档位报 `dsh: AUTH: 当前是「自有」档…`，残留 relay 报 `dsh: TRANSPORT:`。

    修法：枚举全部候选 → 用本会话 home 优先 → **实际 TCP 连一下**，只返回活得下来的那个。
    """
    if time.time() - _RELAY_CACHE["at"] < _RELAY_CACHE_TTL and _RELAY_CACHE["env"]:
        return dict(_RELAY_CACHE["env"])

    own_home = os.environ.get("DSH_HOME", "")
    cands = _relay_candidates()
    cands.sort(key=lambda c: 0 if (own_home and c["home"] == own_home) else 1)
    found = next((c for c in cands if _url_alive(c["url"])), None)

    if found is None and os.environ.get("DEEPSEEK_BASE_URL") \
            and _url_alive(os.environ["DEEPSEEK_BASE_URL"]):
        found = {"url": os.environ["DEEPSEEK_BASE_URL"],
                 "key": os.environ.get("DEEPSEEK_API_KEY", ""),
                 "permission": os.environ.get("DSH_PERMISSION_MODE", "")}

    if found is None and cands:
        sys.stderr.write(
            "[worker] 警告：发现 %d 个 dsh web 进程，但**没有一个 relay 在监听**"
            "（最近一次探测全部失败）。任务会失败到熔断，直到有会话重新起来。\n" % len(cands))

    out = {
        "DEEPSEEK_API_KEY": (found or {}).get("key") or os.environ.get("DEEPSEEK_API_KEY", ""),
        "DEEPSEEK_BASE_URL": (found or {}).get("url") or os.environ.get("DEEPSEEK_BASE_URL", ""),
        "DSH_PERMISSION_MODE": (found or {}).get("permission")
                              or os.environ.get("DSH_PERMISSION_MODE", "danger-full-access"),
    }
    _RELAY_CACHE.update(at=time.time(), env=out)
    return dict(out)


# --------------------------------------------------------------------------- 心跳

class Heartbeat(threading.Thread):
    def __init__(self, task_id: str, agent: str, interval: int = 60):
        super().__init__(daemon=True)
        self.task_id, self.agent, self.interval = task_id, agent, interval
        self.stop_flag = threading.Event()
        self.note = "启动"

    def run(self):
        while not self.stop_flag.wait(self.interval):
            d = loopmod.lease_dir(self.task_id)
            info = loopmod.load_json(d / "lease.json")
            if not info:
                info = {"task": self.task_id, "agent": self.agent, "host": socket.gethostname(),
                        "pid": os.getpid(), "startedAt": now()}
            info["heartbeatAt"] = now()
            info["note"] = self.note
            loopmod.write_json_atomic(d / "lease.json", info)
            loopmod.write_json_atomic(loopmod.WORKERS / (self.agent + ".json"),
                                      {"agent": self.agent, "task": self.task_id, "lastSeenAt": now(), "note": self.note})

    def stop(self):
        self.stop_flag.set()


# --------------------------------------------------------------------------- 主流程

def build_prompt(task: dict, task_file: Path) -> str:
    role = task.get("roleFile") or "loop/ROLES/READER.md"
    return (
        "你是 Castline（小说星图）持续运行环境里的一个 agent，名字由你的启动脚本分配。\n"
        "第一步：读 `{role}`（这是你的角色契约，硬性纪律都在里面）。\n"
        "第二步：读 `{tf}`（这是本轮任务的完整定义：目标、要写哪个文件、原文区间、验收方式）。\n"
        "第三步：严格执行该任务。工作目录是仓库根 `{root}`。\n\n"
        "通用纪律（与 AGENTS.md 一致，违反会被独立复核判 fail）：\n"
        "- 只在任务 `writes` 指定的路径写文件；不要改 `js/` `css/` `index.html` `serve.py` `narrative.py` "
        "`scripts/` `tests/` `docs/` `data/`（这些是受保护路径，只能在合并任务里改）。\n"
        "- 不许 `git checkout -- .` / `git reset --hard` / `git stash`（会抹掉并行 agent 的未提交工作）。\n"
        "- 不许跑 GPU/浏览器测试，除非任务自己声明要跑（GPU 全局串行）。\n"
        "- 结论必须有证据：文件路径 + 可复现命令 + 哈希。没做的事写进 remaining，不要编。\n"
        "- 完成后按角色契约里的格式提交：`python3 loop/bin/loop.py submit --file <你的提交文件> --agent <你的名字>`。\n"
        "  提交会被机器校验（证据文件必须存在、哈希要对得上、受保护路径不许动）。被拒绝就去补真实证据，别改校验。\n"
    ).format(role=role, tf=str(task_file), root=str(ROOT))


def run_agent(task: dict, agent: str, timeout: int, dry_run: bool) -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    task_file = RUNS / ("task-%s.json" % task["id"].replace("/", "__").replace(":", "_"))
    loopmod.write_json_atomic(task_file, task)
    prompt = build_prompt(task, task_file)
    env = dict(os.environ)
    loopmod.sanitize_headless_env(env)
    env.update({k: v for k, v in discover_runtime_env().items() if v})
    env["DSH_PERMISSION_MODE"] = env.get("DSH_PERMISSION_MODE", "danger-full-access")
    cmd = ["dsh", "--profile", "castline", prompt]
    if dry_run:
        print("cwd:", ROOT)
        print("cmd:", " ".join(cmd[:3]), "<prompt %d chars>" % len(prompt))
        print("task:", task["id"], "|", task["title"])
        print("role:", task.get("roleFile"))
        print("writes:", task.get("writes"))
        print("creds:", "yes" if env.get("DEEPSEEK_BASE_URL") else "NO（会失败，需要 Mirasim 会话在跑）")
        return 0
    logf = LOGS / ("%s-%s-%s.log" % (agent, task["id"].replace("/", "_").replace(":", "-"), stamp()))
    t0 = time.time()
    try:
        with logf.open("w", encoding="utf-8") as fh:
            fh.write("CMD: dsh --profile castline <prompt %d chars>\nTASK: %s\n\n" % (len(prompt), task["id"]))
            fh.flush()
            proc = subprocess.run(cmd, cwd=str(ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        rc = 124
        log(agent, "任务 %s 超时（%ds），日志 %s" % (task["id"], timeout, logf))
    except Exception as exc:
        rc = 125
        log(agent, "任务 %s 启动失败：%r" % (task["id"], exc))
    dur = round(time.time() - t0, 1)
    log(agent, "任务 %s 结束 rc=%s 用时 %ss 日志 %s" % (task["id"], rc, dur, logf.name))
    infra = classify_failure(logf) if rc != 0 else None
    rec = {"task": task["id"], "agent": agent, "rc": rc, "seconds": dur,
           "log": safe_rel(logf), "at": now()}
    if infra:
        rec["infraFailure"] = infra
        log(agent, "任务 %s 失败归因为**基础设施**（%s）：不计入「这一章做不出来」的连错记录"
                   % (task["id"], infra))
    loopmod.write_json_atomic(RUNS / ("run-%s.json" % task["id"].replace("/", "__").replace(":", "_")), rec)
    return rc


def submit_if_needed(task: dict, agent: str, rc=None) -> str:
    """agent 自己提交过就用它的；没提交但产物合法就代为提交；否则记失败。

    `rc` 是 agent 进程的退出码（见 one_round）。**代提交必须看它**：
    真实缺陷（2026-10-09 实测）：代提交原先只看「writes 路径存在 + 哈希一致」，
    于是**被超时杀掉的中间态**（rc=124）与**报错退出**（rc=1/127）的产物
    照样被登记成 `done`，与正常完成（rc=0）在记录里长得一模一样。
    实测分母：45 条代提交里 rc=0 的 19 条（合法：agent 做完忘了 submit）、
    rc=124 的 18 条、rc=1 的 7 条、rc=127 的 1 条。
    「文件在、哈希对」只证明**产物可复现**，不证明**agent 认为自己做完了**。
    """
    tid = task["id"]
    out_path = loopmod.OUT / loopmod.output_name(tid)
    if out_path.exists():
        rec = loopmod.load_json(out_path, {}) or {}
        if loopmod.validated(rec) and not loopmod.evidence_stale(rec):
            return "already-submitted"
        if loopmod.validated(rec) and loopmod.evidence_stale(rec):
            return "stale-evidence（需重做，本轮不覆盖记录）"
        rc = loopmod.cmd_submit(argparse.Namespace(file=str(out_path), agent=agent))
        return "revalidated" if rc == 0 else "revalidate-rejected"
    writes = task.get("writes") or []
    primary = None
    for w in writes:
        cand = ROOT / w
        if cand.exists():
            primary = cand
    if not primary:
        _infra = _run_infra_label(tid)
        if _infra:
            reject = {
                "task": tid, "agent": agent, "status": "rejected",
                "summary": ("**未执行**：agent 因基础设施问题退出（%s），本轮没有任何产出 —— "
                            "这不是任务失败，也不是 agent 交不出证据。" % _infra),
                "evidence": [], "assertions": [{"text": "读本轮 agent 日志判定失败归因", "result": "fail"}],
                "remaining": ["环境恢复后自动重试；不需要换策略、也不需要缩小任务范围"],
                "infraFailure": _infra,
                "autoSubmitted": False,
                "rollback": {"kind": "none"},
            }
            for w in writes:
                reject["evidence"].append({"path": w, "missing": True})
            p = loopmod.OUT / ("REJECTED__" + loopmod.output_name(tid))
            loopmod.write_json_atomic(p, reject)
            return "no-output-infra(%s)" % _infra
        reject = {
            "task": tid, "agent": agent, "status": "rejected",
            "summary": "agent 未产出任务要求的文件，且未提交。",
            "evidence": [], "assertions": [{"text": "检查了 writes 路径是否产生文件", "result": "fail"}],
            "remaining": ["本轮无产出；下一轮应换策略或缩小任务范围"],
            "rollback": {"kind": "none"},
        }
        for w in writes:
            reject["evidence"].append({"path": w, "missing": True})
        p = loopmod.OUT / ("REJECTED__" + loopmod.output_name(tid))
        loopmod.write_json_atomic(p, reject)
        return "no-output(rejected)"
    ev = []
    for w in writes:
        cand = ROOT / w
        if cand.exists():
            ev.append({"path": w, "sha256": loopmod.sha256_file(cand), "kind": "worker-output"})
    if not ev:
        reject = {
            "task": tid, "agent": agent, "status": "rejected",
            "summary": "worker 代提交前复查：writes 路径在提交时刻已不存在（agent 未留下产物）。",
            "evidence": [{"path": w, "missing": True} for w in writes],
            "assertions": [{"text": "提交前逐一复查 writes 路径是否存在", "result": "fail"}],
            "remaining": ["本轮无有效产物；下一轮应换策略或缩小任务范围"],
            "rollback": {"kind": "none"},
        }
        p = loopmod.OUT / ("REJECTED__" + loopmod.output_name(tid))
        loopmod.write_json_atomic(p, reject)
        return "no-output-at-submit(rejected)"
    if rc is not None and rc != 0:
        why = {124: "agent 被超时杀掉（%ds）" % task.get("_timeout", 0) if task.get("_timeout") else "agent 被超时杀掉",
               127: "agent 命令启动失败（命令不存在）",
               125: "agent 启动异常"}.get(rc, "agent 以非零码退出")
        reject = {
            "task": tid, "agent": agent, "status": "partial",
            "summary": ("worker 未代提交为 done：%s（rc=%s）。产物虽在磁盘上，"
                        "但它是不完整/未确认的中间态，不能当完成。" % (why, rc)),
            "evidence": ev or [{"path": w, "missing": True} for w in writes],
            "assertions": [{"text": "代提交前置：agent 必须以 rc=0 正常结束", "result": "fail"}],
            "remaining": ["本单元需重做；若长期超时，应缩小单元或提高超时上限（见审计记录）"],
            "agentExitRc": rc,
            "autoSubmitted": False,
            "rollback": {"kind": "append-only", "strategy": "delete-added-files", "files": list(writes)},
        }
        p = loopmod.OUT / ("REJECTED__" + loopmod.output_name(tid))
        loopmod.write_json_atomic(p, reject)
        return "agent-rc%s-not-done(partial)" % rc
    src = {}
    book = task.get("book")
    if book:
        b = (loopmod.load_json(loopmod.STATE / "index.json", {}) or {}).get("books", {}).get(book) or {}
        gk = b.get("graphKey")
        if gk:
            for rel in ("data/cache/%s.json" % gk, "data/cache/%s.docs.json" % gk):
                fp = ROOT / rel
                if fp.exists():
                    src[rel] = loopmod.sha256_file(fp)
    if task.get("sourceHash") and book:
        b = (loopmod.load_json(loopmod.STATE / "index.json", {}) or {}).get("books", {}).get(book) or {}
        if b.get("graphKey"):
            src["data/cache/%s.docs.json" % b["graphKey"]] = task["sourceHash"]
    rec = {
        "task": tid, "agent": agent, "status": "done",
        "summary": "worker 代为登记产物（agent 未自行提交）。",
        "evidence": ev,
        "assertions": [{"text": "逐条检查 writes 路径是否真实存在并记录哈希", "result": "pass"}],
        "changes": [{"path": w, "kind": "append-only"} for w in writes if (ROOT / w).exists()],
        "sourceHashes": src,
        "remaining": ["由 worker 代提交，agent 未写自述；复核时优先看产物本身"],
        "autoSubmitted": True,
        "agentExitRc": rc,
        "rollback": {"kind": "append-only", "strategy": "delete-added-files", "files": [w for w in writes]},
    }
    rc = loopmod.cmd_submit(argparse.Namespace(file=str(_dump_tmp(rec)), agent=agent))
    return "auto-submitted" if rc == 0 else "auto-submit-rejected"


def _dump_tmp(rec: dict) -> Path:
    p = RUNS / ("submit-%s.json" % rec["task"].replace("/", "__").replace(":", "_"))
    loopmod.write_json_atomic(p, rec)
    return p


def install_signal_handlers() -> None:
    """把 SIGTERM 变成「跑完当前任务再退出」，而不是当场被杀。

    `sentinel.stop_worker()` 的契约是**优雅退出**（docstring 原话：「它会在当前任务结束后
    停下（不打断在跑的任务）」），但 worker 原先没有装任何 handler ⇒ SIGTERM 直接终止进程，
    而 `dsh` 是它的**子进程**：实测 worker 29744 挂着子进程 56891（dsh --profile castline）。
    父进程被杀后子 agent 会变成孤儿继续跑，既占着租约又让提交无人接管。
    所以这里不是「加个保险」，是让已有契约真的成立。
    """
    def _graceful(signum, _frame):
        global STOP_REQUESTED
        STOP_REQUESTED = True
        log(os.environ.get("DSH_LOOP_AGENT", "worker"),
            "收到信号 %s：当前任务结束后退出（不再领新任务）" % signum)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _graceful)
        except Exception:
            pass


STOP_REQUESTED = False


def _backoff(seconds: int) -> None:
    """分片睡：收到 SIGTERM 后最多 1s 就退出，不让守护轮的重启等满一个退避周期。"""
    for _ in range(int(seconds)):
        if STOP_REQUESTED:
            break
        time.sleep(1)


def effective_streams(agent: str, cli_streams):
    """解析本 worker 本轮应领哪些流。**roster 是唯一来源**，每轮重新读取。

    真实事故（2026-10-08）：policy.json 把 w-ops 扩成 `ops,adopt,expert,env` 之后
    没有重启它，于是它以启动时的 `--stream ops` 继续空转了 1100 轮
    （`w-ops.daemon.log` 第 1100 轮仍 idle），`adopt`(6) / `env`(3) / `expert`(1)
    共 10 条任务**永远无人领取** —— 而 selftest 第 12f 条只比对 worker **名字**集合，
    所以整个过程中一直全绿。

    修法：通道归属以 roster 为唯一来源并按轮读取，policy 扩容后无需重启即可生效；
    `--stream` 只在 worker 不在 roster 时作为回退（临时手工起的诊断 worker）。
    """
    for w in loopmod.policy().get("workers", []):
        if w.get("name") == agent:
            declared = [s for s in (w.get("streams") or []) if s]
            return declared or None
    return cli_streams


def one_round(agent: str, timeout: int, dry_run: bool, streams=None) -> str:
    if not dry_run and outage_circuit_open():
        return "idle: 全局熔断（跨任务基础设施失败过多 ⇒ 环境停摆，本轮不领任务）"
    tasks = loopmod.load_tasks()
    task, why = loopmod.pick(tasks, agent, streams)
    if not task:
        return "idle: " + str(why)
    if dry_run:
        run_agent(task, agent, timeout, True)
        return "dry-run"
    if loopmod.claim(task, agent) != 0:
        return "lease-lost"
    hb = Heartbeat(task["id"], agent)
    hb.start()
    try:
        rc = run_agent(task, agent, timeout, False)
        result = submit_if_needed(task, agent, rc=rc)
        if rc == 0:
            _clear_failure(task["id"])
        else:
            wait = _note_failure(task["id"], rc, agent)
            log(agent, "任务 %s 失败 rc=%s ⇒ 该任务退避 %ds 后再试"
                       "（指数退避，见 loop/state/FAILED-TASKS.json）" % (task["id"], rc, wait))
            _backoff(min(wait, 300))
    finally:
        hb.stop()
        loopmod.cmd_release(argparse.Namespace(task=task["id"], agent=agent, force=False))
    loopmod.cmd_runlog(argparse.Namespace(agent=agent, line=None,
                                          json=json.dumps({"task": task["id"], "rc": rc, "result": result})))
    return "%s rc=%s %s" % (task["id"], rc, result)


BACKOFF_BASE = {125: 60, 127: 60}
BACKOFF_CAP = {125: 3600, 127: 3600}
BACKOFF_DEFAULT = (30, 900)

_DIAG_LINE = re.compile(r"^(?:Error: )?dsh:\s*([A-Z_]{3,})\s*:")
INFRA_LINE_HINTS = (
    ("PROFILE", ('profile "castline" does not exist',)),
    ("AUTH", ("AUTH", "not logged in", "Not logged in", "invalid user token")),
    ("RATE_LIMIT", ("RATE_LIMIT",)),
    ("TRANSPORT", ("TRANSPORT", "transport failed")),
    ("SERVER", ("SERVER", "socket disconnected", "502 Bad Gateway", "503 Service Unavailable")),
    ("NETWORK", ("ECONNRESET", "ETIMEDOUT", "ENOTFOUND", "socket hang up")),
)


def classify_failure(logf) -> str:
    """从 agent 日志判定这次失败是否属**基础设施**（与任务内容无关）。返回标签或 None。

    判据（第二版，见上方复核事故说明）：
      · 只认 **dsh 自己的诊断行**（行首 `dsh: <TAG>:` / `Error: dsh: profile ...`）；
      · 扫**全文**，不用尾部窗口（实测错误行可能出现在 offset 2881）；
      · 认不出来返回 None（=按内容失败记账）——**宁可漏判成"难任务"，
        也不能把真做不出来的单元洗成"网络问题"**（后者是 E31 的反向形态）。
    """
    try:
        txt = Path(logf).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    if not txt:
        return None
    for line in txt.splitlines():
        m = _DIAG_LINE.match(line.strip())
        if not m and 'profile "castline" does not exist' in line:
            return "PROFILE"
        if not m:
            continue
        tag = m.group(1)
        for label, hints in INFRA_LINE_HINTS:
            if any(h in line for h in hints):
                return label
        if tag in ("AUTH", "RATE_LIMIT", "TRANSPORT", "SERVER", "NETWORK", "PROFILE"):
            return tag
    return None


def _run_infra_label(tid: str) -> str:
    """读回 run_agent 写下的归因（run-*.json 的 infraFailure）。"""
    p = RUNS / ("run-%s.json" % tid.replace("/", "__").replace(":", "_"))
    try:
        return (loopmod.load_json(p, {}) or {}).get("infraFailure") or ""
    except Exception:
        return ""


FAIL_LEDGER = loopmod.STATE / "FAILED-TASKS.json"

OUTAGE_WINDOW_SECONDS = 600
OUTAGE_DISTINCT_TASKS = 4


def outage_circuit_open(window: int = OUTAGE_WINDOW_SECONDS,
                        threshold: int = OUTAGE_DISTINCT_TASKS) -> bool:
    """最近 window 秒内，是否有 ≥ threshold 个**不同任务**因基础设施失败？

    只读 `run-*.json`（其中 infraFailure 由 run_agent 写下，来源唯一），不猜、不扫日志全文。
    """
    try:
        nowt = time.time()
        seen = set()
        for f in RUNS.glob("run-*.json"):
            try:
                if nowt - f.stat().st_mtime > window:
                    continue
                d = loopmod.load_json(f, {}) or {}
            except Exception:
                continue
            if d.get("infraFailure") and d.get("task"):
                seen.add(d["task"])
        return len(seen) >= threshold
    except Exception:
        return False


def _backoff_plan(rc):
    if rc in BACKOFF_BASE:
        return BACKOFF_BASE[rc], BACKOFF_CAP[rc]
    return BACKOFF_DEFAULT


def _note_failure(tid: str, rc, agent: str) -> int:
    """登记一次失败并返回**下次可领前的等待秒数**（指数退避，有上限）。

    基础设施失败（E31）另记 `infraConsecutive`，**不**污染 `consecutive` ——
    见 `classify_failure` 的事故说明。无论如何 `retryAfter` 都会设置，所以
    重试机会与退避节奏一字未变。
    """
    try:
        led = loopmod.load_json(FAIL_LEDGER, {}) or {}
    except Exception:
        led = {}
    ent = led.get(tid) or {"consecutive": 0, "total": 0, "rcs": {}}
    ent["total"] = int(ent.get("total", 0)) + 1
    ent.setdefault("rcs", {})[str(rc)] = int(ent["rcs"].get(str(rc), 0)) + 1
    infra = _run_infra_label(tid)
    if infra:
        ent["infraConsecutive"] = int(ent.get("infraConsecutive", 0)) + 1
        labels = ent.setdefault("infraLabels", {})
        labels[infra] = int(labels.get(infra, 0)) + 1
        ent["lastInfraLabel"] = infra
    else:
        ent["consecutive"] = int(ent.get("consecutive", 0)) + 1
    base, cap = _backoff_plan(rc)
    wait = min(base * (2 ** (ent["total"] - 1)), cap)
    ent["retryAfter"] = time.time() + wait
    ent["retryAfterSeconds"] = wait
    ent["lastAt"] = loopmod.now()
    ent["lastAgent"] = agent
    ent["lastRc"] = rc
    led[tid] = ent
    try:
        loopmod.write_json_atomic(FAIL_LEDGER, led)
    except Exception:
        pass
    return wait


def _clear_failure(tid: str) -> None:
    try:
        led = loopmod.load_json(FAIL_LEDGER, {}) or {}
        if tid in led:
            led.pop(tid)
            loopmod.write_json_atomic(FAIL_LEDGER, led)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--loop", type=int, default=1, help="连续跑几轮（0=无限）")
    ap.add_argument("--timeout", type=int, default=0, help="单任务墙钟上限秒（默认取 policy.taskTimeoutSeconds）")
    ap.add_argument("--idle-sleep", type=int, default=120, help="无任务时等待秒数")
    ap.add_argument("--stream", default="", help="限定流（逗号分隔），如 read / read-verify / ops")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    loopmod.sanitize_headless_env()
    pol = loopmod.policy()
    timeout = args.timeout or pol.get("taskTimeoutSeconds", 3600)
    LOGS.mkdir(parents=True, exist_ok=True)
    os.environ["DSH_LOOP_AGENT"] = args.agent
    install_signal_handlers()
    log(args.agent, "启动（loop=%s timeout=%ss stream=%s dry_run=%s）" % (args.loop, timeout, args.stream or "auto", args.dry_run))

    rounds = 0
    consecutive_idle = 0
    while (args.loop == 0 or rounds < args.loop) and not STOP_REQUESTED:
        rounds += 1
        try:
            streams = effective_streams(args.agent, [x for x in args.stream.split(",") if x] or None)
            outcome = one_round(args.agent, timeout, args.dry_run, streams)
        except Exception as exc:
            outcome = "error: %r" % (exc,)
            log(args.agent, "轮次异常：" + outcome)
        log(args.agent, "第 %d 轮 → %s" % (rounds, outcome))
        if args.dry_run:
            break
        if outcome.startswith("error"):
            consecutive_idle += 1
            wait = min(30 * consecutive_idle, 300)
            log(args.agent, "异常退避第 %d 次，等 %ds" % (consecutive_idle, wait))
            _backoff(wait)
            continue
        if outcome.startswith("idle"):
            if args.loop == 0:
                consecutive_idle += 1
                wait = min(args.idle_sleep * consecutive_idle, 300)
                log(args.agent, "空转第 %d 次，等 %ds" % (consecutive_idle, wait))
                _backoff(wait)
                continue
            break
        consecutive_idle = 0
        loopmod.write_json_atomic(loopmod.WORKERS / (args.agent + ".json"),
                                  {"agent": args.agent, "state": "idle", "lastSeenAt": now(), "rounds": rounds})
    log(args.agent, "退出（共 %d 轮）" % rounds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
