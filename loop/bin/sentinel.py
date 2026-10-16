#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""守护轮（sentinel / watchdog）：让流水线在不被盯着的情况下持续跑几十小时。

每轮做七件事，顺序固定：
  1. 回收死租约（活进程的租约不动）。
  2. 检查 worker 存活；不足则按 roster 拉起（有重启上限，防止无限重启崩溃的 worker）。
  3. 统计真实进度（按流、按书、按 lane），写入 GUARD-REPORT.json 并追加 GUARD-LOG.md。
  4. 按完成情况补队列（稀疏索引 → 稠密生成：只补充需要的那一批）。
  5. 停滞检测：完成数在 N 轮内没有变化就升级告警（不是静默继续）。
  6. 定期插入专家复核任务（每完成 N 个发布批触发一次）。
  7. 单实例：用 loop/state/GUARD.lock 保证同时只有一个守护轮。

用法：
  python3 -B -s loop/bin/sentinel.py --once                  # 跑一轮（给排期调用）
  python3 -B -s loop/bin/sentinel.py --once --no-spawn       # 只观察，不拉起 worker
  python3 -B -s loop/bin/sentinel.py --once --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
STATE = LOOP / "state"
LOGS = STATE / "logs"
GUARD_LOCK = STATE / "GUARD.lock"
GUARD_REPORT = STATE / "GUARD-REPORT.json"
GUARD_LOG = STATE / "GUARD-LOG.md"
WORKER_BIN = LOOP / "bin" / "worker.py"


def load_loop_module():
    spec = importlib.util.spec_from_file_location("loopmod", LOOP / "bin" / "loop.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


loopmod = load_loop_module()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_policy() -> dict:
    return {
        "maxConcurrentLeases": 14,
        "maxGpuLeases": 1,
        "leaseTtlSeconds": 300,
        "taskTimeoutSeconds": 2700,
        "idleSleepSeconds": 120,
        "stallRoundsBeforeAlert": 3,
        "maxWorkerRestartsPerDay": 24,
        "expertReviewEveryPublishes": 3,
        "workers": [
            {"name": "w-dafeng-0", "streams": ["read"]},
            {"name": "w-dafeng-1", "streams": ["read"]},
            {"name": "w-dafeng-2", "streams": ["read"]},
            {"name": "w-dafeng-3", "streams": ["read"]},
            {"name": "w-xiyou-0", "streams": ["read"]},
            {"name": "w-xiyou-1", "streams": ["read"]},
            {"name": "w-sanguo-0", "streams": ["read"]},
            {"name": "w-sanguo-1", "streams": ["read"]},
            {"name": "w-verify-0", "streams": ["read-verify"]},
            {"name": "w-verify-1", "streams": ["read-verify"]},
            {"name": "w-ops", "streams": ["ops", "adopt", "expert", "env"]},
            {"name": "w-publish", "streams": ["publish"]},
            {"name": "w-gpu", "streams": ["xgraph", "perf", "a11y"]},
        ],
    }


def ensure_policy() -> dict:
    p = loopmod.policy()
    base = default_policy()
    base.update(p)
    if not loopmod.POLICY.exists():
        loopmod.write_json_atomic(loopmod.POLICY, base)
    return base


def single_instance() -> bool:
    if GUARD_LOCK.exists():
        info = loopmod.load_json(GUARD_LOCK, {}) or {}
        try:
            age = time.time() - datetime.strptime(info.get("at", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            age = 99999
        pid = info.get("pid")
        alive = False
        if pid:
            alive = loopmod._pid_alive(pid)
        if age < 900 and alive:
            return False
    loopmod.write_json_atomic(GUARD_LOCK, {"pid": os.getpid(), "at": now(), "host": os.uname().nodename})
    return True


def running_streams() -> dict:
    """在跑的 worker 名 → 它**实际**带的 --stream 集合（用于漂移检测）。"""
    try:
        ps = subprocess.run(["ps", "-eo", "pid=,command="], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return {}
    out = {}
    for line in ps.splitlines():
        if "worker.py" not in line or "--agent" not in line or "sentinel" in line:
            continue
        m = re.search(r"--agent (\S+)", line)
        if not m:
            continue
        s = re.search(r"--stream (\S+)", line)
        out[m.group(1)] = set((s.group(1).split(",") if s else []))
    return out


def worker_alive(name: str, want_streams=None) -> bool:
    """进程活着 **且** 通道与 roster 一致。

    名字活着不代表它在做对的事：实测 w-ops 以过期的 `--stream ops` 空转 1100 轮，
    而 roster 要求它同时承接 adopt/env/expert。只比对名字会让这种漂移永远不被发现，
    所以这里把 --stream 也纳入判据；不一致即视为需要重启。
    """
    alive = False
    for line in _ps_lines():
        if "worker.py" in line and ("--agent %s" % name) in line and "sentinel" not in line:
            alive = True
            break
    if not alive:
        return False
    if want_streams is None:
        return True
    have = running_streams().get(name, set())
    return have == set(want_streams)


def _ps_lines():
    try:
        return subprocess.run(["ps", "-eo", "pid=,command="], capture_output=True, text=True, timeout=20).stdout.splitlines()
    except Exception:
        return []


def worker_owns(name: str, task: dict) -> bool:
    streams = task_streams_for(name)
    return not streams or task.get("stream") in streams


def task_streams_for(name: str) -> list:
    for w in ensure_policy()["workers"]:
        if w["name"] == name:
            return w.get("streams", [])
    return []


def restart_budget_ok(name: str) -> bool:
    """每个 worker 每天的重启次数上限：崩溃循环不该被无限重启掩盖。"""
    p = STATE / "workers" / (name + ".restarts.json")
    rec = loopmod.load_json(p, {}) or {"day": "", "count": 0}
    day = datetime.now().strftime("%Y-%m-%d")
    if rec.get("day") != day:
        rec = {"day": day, "count": 0}
    limit = ensure_policy()["maxWorkerRestartsPerDay"]
    if rec["count"] >= limit:
        return False
    rec["count"] += 1
    loopmod.write_json_atomic(p, rec)
    return True


def _node_bin_dirs() -> list:
    """本机现存的 node bin 目录（按版本号新→旧）。"""
    base = Path.home() / ".workbuddy" / "binaries" / "node" / "versions"
    out = []
    if base.is_dir():
        for d in sorted(base.iterdir(), reverse=True):
            b = d / "bin"
            if (b / "node").exists():
                out.append(str(b))
    return out


def repair_path(path: str) -> tuple:
    """修掉 PATH 里**指向已删除目录**的条目，并把现存 node 放到最前。

    真实事故（2026-10-09 01:40）：workbuddy 自动把 node 从 22.22.2-3 升到
    22.22.2-6 并删掉旧目录，而常驻 sentinel 进程持有的是**升级前**的 PATH ⇒
    它拉起的 worker 找到的 `node` 已不存在 ⇒ 每个任务 0.0s 死于 `rc=127`
    （`env: node: No such file or directory`）⇒ worker 崩溃循环，每轮刷一条日志。
    看板上 13 个 worker 全部「活着」，实际**产出为 0**。
    这正是本项目反复出现的形态：**进程活着 ≠ 在干活**，而名字/数量全对。

    修法：拉 worker 之前把 PATH 里已消失的 node 目录剔除，再把现存 node 提前。
    常驻进程不必重启，node 升级也不再让整条流水线静默停摆。
    """
    parts = [p for p in (path or "").split(":") if p]
    bad = [p for p in parts if "binaries/node" in p and not Path(p).exists()]
    keep = [p for p in parts if p not in bad]
    good = [p for p in _node_bin_dirs() if p not in keep]
    return ":".join(good + keep), bad


CASTLINE_PACKAGE = """{
  "name": "dsh-profile-headless",
  "private": true,
  "dependencies": {},
  "dsh": {
    "profile": {
      "bundles": [
        "@deepseek-ai/dsh-base",
        "@deepseek-ai/dsh-headless"
      ]
    }
  }
}
"""

CASTLINE_PATCH = """# Castline 持续运行环境的专用 profile：
# 与 headless 相同的组成，只把默认模型固定下来，避免 worker 受交互会话的设置漂移影响。
# 模型走本机 mirasim relay（DEEPSEEK_BASE_URL / DEEPSEEK_API_KEY 由 worker.py 在启动时发现）。
- id: agent-default-model
  name: "@deepseek-ai/dsh-agent-default-model"
  config:
    provider: deepseek-official
    model: deepseek-flash
    reasoningEffort: max
"""

CASTLINE_CORDIS = """# dsh profile root — an empty entry list. The tree is composed as patches:
# each bundle in package.json's dsh.profile.bundles, then cordis.patch.yml, then any
# --patch overlays. Edit cordis.patch.yml, not this file.
[]
"""

CASTLINE_WORKSPACE = """packages:
  - .

nodeLinker: hoisted
autoInstallPeers: false
"""


def ensure_castline_profile(home) -> bool:
    """确保 `$home/profiles/castline` 存在；缺了就地按规范内容建出来。返回是否可用。

    真实事故（2026-10-09 12:28，本次停机的**直接**原因）：
      `castline` profile 原先只建在**某一个会话的** agent home 里
      （`~/.mirasim/agent-homes/dsh/<session>/profiles/castline`），而
      Mirasim 每次新会话都注入一个**新的** DSH_HOME。新 home 里没有这个 profile ⇒
      `discover_dsh_home()` 回落到新 home ⇒ worker 的每个任务都在 0.2 秒内死于
      `dsh: profile "castline" does not exist` ⇒ **13 个 worker 全部"活着"、
      selftest 全绿、看板上进程数一个不少，而产出为 0**。

    这正是本项目反复出现的形态（E1/E2/E14）：**列表对了、现实没对上**。
    所以修的不能只是"手工把 profile 拷进当前 home"——下一个会话又会踩同一个坑；
    要让它**自己长回来**：任何 home 缺 profile，拉起 worker 前就地补齐。
    """
    if not home:
        return False
    prof = Path(home) / "profiles" / "castline"
    if (prof / "package.json").is_file() and (prof / "cordis.patch.yml").is_file():
        return True
    try:
        prof.mkdir(parents=True, exist_ok=True)
        src = _find_existing_castline_profile(exclude=prof)
        if src and (src / "package.json").is_file():
            for f in ("package.json", "cordis.patch.yml", "cordis.yml", "pnpm-workspace.yaml"):
                if (src / f).is_file():
                    shutil.copy2(src / f, prof / f)
        if not (prof / "package.json").is_file():
            (prof / "package.json").write_text(CASTLINE_PACKAGE, encoding="utf-8")
            (prof / "cordis.patch.yml").write_text(CASTLINE_PATCH, encoding="utf-8")
            (prof / "cordis.yml").write_text(CASTLINE_CORDIS, encoding="utf-8")
            (prof / "pnpm-workspace.yaml").write_text(CASTLINE_WORKSPACE, encoding="utf-8")
        return (prof / "package.json").is_file() and (prof / "cordis.patch.yml").is_file()
    except Exception:
        return False


def _find_existing_castline_profile(exclude=None):
    """在已知的 agent home 里找一个现成的 castline profile 作为复制源。"""
    roots = [Path.home() / ".mirasim" / "agent-homes" / "dsh",
             Path.home() / ".dsh" / "profiles"]
    for root in roots:
        if not root.is_dir():
            continue
        for cand in [root] + sorted([p for p in root.iterdir() if p.is_dir()], reverse=True):
            p = cand / "profiles" / "castline" if (cand / "profiles").is_dir() or cand.name == "dsh" else cand / "castline"
            if exclude is not None and p == exclude:
                continue
            if (p / "package.json").is_file():
                return p
    return None


def discover_dsh_home(env: dict) -> str:
    """找到（并**就地修好**）带 `castline` profile 的 DSH_HOME。

    两个真实缺口（同一次事故）：
      ① worker 用 `dsh --profile castline` 起任务，profile 解析依赖 `DSH_HOME`
         （`profiles/<name>`）——手工重启的 sentinel 没有这个变量，于是 worker 报
         `profile "castline" does not exist`；
      ② 就算有 DSH_HOME，**新会话的 home 里也没有这个 profile**（见
         `ensure_castline_profile` 的事故说明）⇒ 同样是"看着在跑、其实全败"。

    所以这里不再"挑一个有 profile 的 home"了事（那会把 worker 绑在别的会话的
    home 上，且那个 home 随时会被回收）：**优先用本会话的 home，缺 profile 就补齐**；
    只有当本会话 home 不可写时，才退回到一个现成的 castline home。
    """
    def has_profile(h) -> bool:
        return bool(h) and (Path(h) / "profiles" / "castline" / "package.json").is_file()

    own = env.get("DSH_HOME", "")
    if own:
        if has_profile(own) or ensure_castline_profile(own):
            return own
    try:
        ps = subprocess.run(["ps", "-eo", "pid=,command="], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        ps = ""
    for line in ps.splitlines():
        if "dsh" not in line or " web" not in line or "grep" in line:
            continue
        pid = line.strip().split(None, 1)[0]
        if not pid.isdigit():
            continue
        try:
            raw = subprocess.run(["ps", "eww", "-p", pid], capture_output=True, text=True, timeout=20).stdout
        except Exception:
            continue
        for tok in raw.split():
            if tok.startswith("DSH_HOME="):
                cand = tok.split("=", 1)[1]
                if has_profile(cand) or ensure_castline_profile(cand):
                    return cand
    src = _find_existing_castline_profile()
    if src and ensure_castline_profile(src.parents[1]):
        return str(src.parents[1])
    return own


def spawn_worker(name: str, streams) -> str:
    LOGS.mkdir(parents=True, exist_ok=True)
    logf = LOGS / ("%s.daemon.log" % name)
    env = dict(os.environ)
    loopmod.sanitize_headless_env(env)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"], dropped = repair_path(env.get("PATH", ""))
    home = discover_dsh_home(env)
    if home:
        env["DSH_HOME"] = home
        env["DSH_PROFILE_DIR"] = str(Path(home) / "profiles" / "castline")
    cmd = [sys.executable, "-B", "-s", str(WORKER_BIN), "--agent", name, "--loop", "0",
           "--timeout", str(ensure_policy()["taskTimeoutSeconds"]),
           "--idle-sleep", str(ensure_policy()["idleSleepSeconds"])]
    if streams:
        cmd += ["--stream", ",".join(streams)]
    with logf.open("a", encoding="utf-8") as fh:
        fh.write("\n=== 拉起 %s at %s (streams=%s) ===\n" % (name, now(), ",".join(streams)))
        fh.write("env: DSH_HOME=%s node=%s dropped=%s\n"
                 % (env.get("DSH_HOME", "(none)"),
                    next((p for p in env["PATH"].split(":") if "binaries/node" in p), "(none)"),
                    dropped))
        fh.flush()
        subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT,
                         start_new_session=True)
    return str(logf.relative_to(ROOT))


def stop_worker(name: str) -> int:
    """让 worker 优雅退出：它会在当前任务结束后停下（不打断在跑的任务）。"""
    killed = 0
    try:
        ps = subprocess.run(["ps", "-eo", "pid=,command="], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return 0
    for line in ps.splitlines():
        if "worker.py" in line and ("--agent %s" % name) in line and "sentinel" not in line:
            pid = line.strip().split(None, 1)[0]
            if pid.isdigit():
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    killed += 1
                except Exception:
                    pass
    return killed


def progress() -> dict:
    tasks = loopmod.load_tasks()
    done = loopmod.done_ids()
    per_stream = {}
    per_book = {}
    for t in tasks.values():
        s = t.get("stream", "?")
        per_stream.setdefault(s, {"tasks": 0, "done": 0})
        per_stream[s]["tasks"] += 1
        if t["id"] in done:
            per_stream[s]["done"] += 1
        b = t.get("book")
        if b:
            per_book.setdefault(b, {"tasks": 0, "done": 0})
            per_book[b]["tasks"] += 1
            if t["id"] in done:
                per_book[b]["done"] += 1
    open_rej = loopmod.open_rejections(done=done, tasks=tasks)
    rejected = [r["file"] for r in open_rej]
    pending_verify = [r["task"] for r in done.values() if r.get("verifyState") == "pending"]
    return {
        "tasks": len(tasks), "done": len(done),
        "perStream": per_stream, "perBook": per_book,
        "rejected": rejected[:20], "rejectedCount": len(rejected),
        "pendingVerify": pending_verify[:20], "pendingVerifyCount": len(pending_verify),
    }


def top_up_queue(prog: dict) -> str:
    """按完成情况补队列：只补即将耗尽的那一批（不一次铺满，避免又一个 13MB 计划书）。"""
    p = prog if (isinstance(prog, dict) and "perStream" in prog) else progress()
    read_left = p["perStream"].get("read", {}).get("tasks", 0) - p["perStream"].get("read", {}).get("done", 0)
    if read_left > 120:
        return "队列充足（剩余 %d 条精读链）" % read_left
    existing = p["perStream"].get("read", {}).get("tasks", 0)
    batch = existing // (20 * 8) + 1
    try:
        out = subprocess.run([sys.executable, "-B", "-s", str(LOOP / "bin" / "build_plan.py"),
                              "--read-batch", str(batch)], cwd=str(ROOT), capture_output=True, text=True, timeout=600)
        return "补队列批 %d：%s" % (batch, (out.stdout or out.stderr).strip().splitlines()[-1] if (out.stdout or out.stderr).strip() else "无输出")
    except Exception as exc:
        return "补队列失败：%r" % (exc,)


def maybe_expert_review(prog: dict) -> str:
    pub = prog["perStream"].get("publish", {})
    done_pub = pub.get("done", 0)
    every = ensure_policy()["expertReviewEveryPublishes"]
    if done_pub == 0 or done_pub % every != 0:
        return "未到触发点（已发布 %d 批）" % done_pub
    tid = "expert:review-%d" % done_pub
    path = LOOP / "queue" / "expert.jsonl"
    exists = False
    if path.exists():
        exists = any(json.loads(l).get("id") == tid for l in path.read_text("utf-8").splitlines() if l.strip().startswith("{"))
    if exists:
        return "已存在 %s" % tid
    task = {
        "id": tid, "stream": "expert", "phase": 6, "seq": done_pub,
        "title": "跨域专家评审：前 %d 个发布批" % done_pub,
        "prompt": "按 loop/ROLES/EXPERT-REVIEW.md 评审最近 %d 个发布批：\n"
                  "1) 有哪些事实是原文里有、而之前任何版本都没有的（给出引证）；\n"
                  "2) 是否又出现「机制存在、有产出、但不产生信息」的同构失败；\n"
                  "3) 本批应归属八维中的哪一维，为什么不是其他维；\n"
                  "4) 有没有正在做、但不该继续做的事。\n"
                  "产出 loop/state/out/expert_review-%d.artifact.json。没有信息增量就如实写没有，不要编正面评价。" % (done_pub, done_pub),
        "writes": ["loop/state/out/expert_review-%d.artifact.json" % done_pub],
        "roleFile": "loop/ROLES/EXPERT-REVIEW.md", "verifierRequired": False,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(task, ensure_ascii=False) + "\n")
    return "已插入 %s" % tid


def stall_check(prog: dict, pol: dict, doctor: dict = None) -> str:
    """完成数没涨 = 停滞吗？**不全是** —— 必须先看有没有活在跑。

    真实误报（2026-10-09 14:11 实测）：`done` 连续 3 轮都是 341 就报「停滞告警」，
    而同一时间窗内 **40 分钟完成了 12 个任务、10 个租约在跑**。
    根因是**两个时间尺度不匹配**：单章精读中位 **1802s（约 30 分钟）**，
    而守护轮每 5–10 分钟就记一次 ⇒ "连续 3 轮同值"只等于"约 15–30 分钟没有新完成"，
    这正是**正常在做工**的样子。实测它已经误报 6 次。

    为什么必须修：一个经常误报的告警会**训练人忽略红色** ——
    与「会随机变红的自检」是同一个教训（见 selftest 12n 的复发记录）。
    但**不能靠放宽阈值来修**：那样真停滞也会被放过。

    正确判据：停滞 =「完成数没涨」**且**「没有任务在跑」。
    只有在既没有新完成、又没有活跃租约时，才是真的没在干活。
    （单个 worker 卡住由 `doctor.py` 的 `stalled(held-lease)` 单独负责，两者互补。）
    """
    hist_path = STATE / "GUARD-HISTORY.jsonl"
    hist = []
    if hist_path.exists():
        for line in hist_path.read_text("utf-8").splitlines()[-40:]:
            if line.strip().startswith("{"):
                try:
                    hist.append(json.loads(line))
                except Exception:
                    pass
    same = 0
    for rec in reversed(hist):
        if rec.get("done") == prog["done"]:
            same += 1
        else:
            break
    if same < pol["stallRoundsBeforeAlert"]:
        return "正常（连续同值 %d 轮）" % same
    dsum = (doctor or {}).get("summary") or {}
    working = dsum.get("working")
    stalled = dsum.get("stalled")
    if working is None:
        try:
            inflight = len(loopmod.active_leases())
        except Exception:
            inflight = 0
        if inflight:
            return ("无新增完成（连续 %d 轮同值 %d）但持有活跃租约 %d；doctor 无结论"
                    " ⇒ 暂不判停滞" % (same, prog["done"], inflight))
        return "停滞告警：连续 %d 轮完成数都是 %d，且没有活跃租约、doctor 无结论" % (same, prog["done"])
    broken = dsum.get("broken") or 0
    if (working or 0) > 0 and broken > (working or 0):
        return ("**停滞告警（多数通道坏掉）**：连续 %d 轮完成数都是 %d，"
                "而 doctor 显示 干活 %s / **坏掉 %s** ⇒ 在跑的任务正在**秒退**，"
                "不是「做得慢」。先看 doctor 的 fast-fail 指引与 GUARD-LOG 的账号停机行"
                % (same, prog["done"], working, broken))
    if (working or 0) > 0:
        return ("无新增完成（连续 %d 轮同值 %d）但**有 %s 个 worker 在干活**"
                " ⇒ 不算停滞——单章中位约 30 分钟，而守护轮每 5–10 分钟记一次"
                % (same, prog["done"], working))
    return ("停滞告警：连续 %d 轮完成数都是 %d，且**干活 %s / 卡住 %s**"
            " ⇒ 没有在推进" % (same, prog["done"], working, stalled))


def disk_guard(min_free_gb: float = 3.0) -> dict:
    """检查磁盘余量；不足则**报出来**（守护轮第 0 步）。

    真实事故（2026-10-09 11:40，本次停机的第二个原因）：
      磁盘被写满 ⇒ 每个任务的租约写入抛 `OSError(28, 'No space left on device')`
      ⇒ worker 走异常退避、重试、再失败；日志里成片是 ENOSPC，而
      `GUARD-LOG.md` 那一栏仍写着「worker：13/13 alive」。
      更早的一次（10-08 16:14）已经出现过同样的 ENOSPC —— 修了当次，没修判据，
      所以第二天原样复发。

    判据只需回答一件事：**现在还能不能写**。所以既看 `statvfs` 余量，
    也做一次真实的小文件写入（余量数字在 APFS 上会因 purgeable 而失真）。
    """
    out = {"checked": True, "minFreeGB": min_free_gb}
    try:
        import shutil as _sh
        total, used, free = _sh.disk_usage(str(STATE))
        out.update(totalGB=round(total / 1e9, 2), usedGB=round(used / 1e9, 2), freeGB=round(free / 1e9, 2))
        out["low"] = free < min_free_gb * 1e9
    except Exception as exc:
        out.update(low=None, error=repr(exc))
    probe = STATE / ".disk-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        out["writable"] = True
    except Exception as exc:
        out["writable"] = False
        out["writeError"] = repr(exc)
    out["ok"] = bool(out.get("writable")) and not out.get("low")
    return out


def schedule_health() -> dict:
    """跨会话排期是否**真的能用**（不只是"配了"）。

    真实事故（2026-10-09 13:22，我重建排期时当场撞上）：
      `.mirasim/schedules.json` 写对了、cron 到点真的触发了、`runs.jsonl` 记
      **`status: ok`** —— 而那一轮的 agent 会话以 **422** 结束：
      「当前是「自有」档，而本机没有这个智能体的账号，本轮已停止，没有任何请求发往平台。」
      即 **agent 选错了**。账本只证明"派发了"，不证明"干成了"。

    这与 E23（13 个 worker 全 alive、每个任务 0.2s 秒退、产出为 0）是**同一形态**，
    只是发生在排期这一层。所以判据不能看 `status`，要看**最近一次运行是否产出了东西**：
      · 本机有没有配排期（`<workspace>/.mirasim/schedules.json`）；
      · 排期声明的 agent 在**本机**是否可用（对已知不可用档位直接点名）；
      · 最近 N 次运行的 `status` 与 `error`。
    """
    out = {"configured": False, "schedules": [], "recentRuns": [], "warnings": []}
    path = ROOT / ".mirasim" / "schedules.json"
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        scheds = [s for s in (d.get("schedules") or [])
                  if isinstance(s, dict) and isinstance(s.get("id"), str)]
    except Exception as exc:
        out["error"] = repr(exc)
        return out
    out["configured"] = bool(scheds)
    for s in scheds:
        out["schedules"].append({"name": s.get("name"), "cron": s.get("cron"),
                                 "enabled": s.get("enabled"), "agent": s.get("agent")})
        if not s.get("enabled"):
            out["warnings"].append("排期 %s 未启用（enabled=false）" % s.get("name"))
    ids = {s.get("id") for s in scheds}
    ledger = Path.home() / ".mirasim" / "schedules" / "runs.jsonl"
    if ledger.exists():
        try:
            lines = ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
            runs = []
            for line in lines:
                if not line.strip().startswith("{"):
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("scheduleId") in ids:
                    runs.append(r)
            out["recentRuns"] = runs[-5:]
            bad = [r for r in out["recentRuns"] if r.get("status") != "ok" or r.get("error")]
            if bad:
                out["warnings"].append("最近 %d 次排期运行有失败（status/error）" % len(bad))
            no_output = []
            for r in out["recentRuns"]:
                sk = r.get("sessionKey") or ""
                if ":" not in sk:
                    continue
                agent, _, sid = sk.partition(":")
                rec = None
                for cand in (Path.home() / ".mirasim" / "sessions").glob("*/" + sid + "/record.json"):
                    try:
                        rec = json.loads(cand.read_text(encoding="utf-8"))
                    except Exception:
                        rec = None
                    break
                if rec is None:
                    no_output.append({"at": r.get("at"), "agent": agent, "state": "no-record"})
                    continue
                st = rec.get("runState")
                if st and st != "completed":
                    no_output.append({"at": r.get("at"), "agent": agent, "state": st,
                                      "detail": (rec.get("runDetail") or "")[:160]})
            out["firesWithoutOutput"] = no_output
            if no_output:
                out["firedButNoOutput"] = True
                newest = no_output[-1]
                out["warnings"].append(
                    "排期最近 %d 次触发**没有产出**（账本仍是 ok）：最近一次 %s agent=%s runState=%s%s"
                    % (len(no_output),
                       datetime.fromtimestamp((newest.get("at") or 0) / 1000).strftime("%H:%M:%S"),
                       newest.get("agent"), newest.get("state"),
                       ("：" + newest["detail"]) if newest.get("detail") else ""))
        except Exception as exc:
            out["ledgerError"] = repr(exc)
    if not out["configured"]:
        out["warnings"].append("本工作区没有跨会话排期：进程被清理后不会自愈（见 loop/SCHEDULE.md）")
    known_bad = {"codex": "本机无该智能体账号（实测 401/422）",
                 "claude": "CLI 未登录（实测 Not logged in）",
                 "dsh": "经排期仍被「自有档无账号」挡（实测 runState=incomplete）"}
    for s in out["schedules"]:
        a = s.get("agent")
        if a in known_bad:
            out["warnings"].append("排期 agent=%s 疑似不可用：%s" % (a, known_bad[a]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", action="store_true", help="常驻：每隔 --interval 秒跑一轮守护（本会话/终端存活期间有效）")
    ap.add_argument("--interval", type=int, default=600, help="--watch 的轮询间隔秒数（默认 600 = 10 分钟）")
    ap.add_argument("--no-spawn", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lookback-minutes", type=int, default=0,
                    help="只统计最近 N 分钟的活动（0=累计）")
    args = ap.parse_args()

    loopmod.sanitize_headless_env()
    if args.watch and not args.once:
        round_timeout = max(300, args.interval) + 600
        print("常驻守护启动：每 %d 秒一轮（单轮上限 %ds，pid=%d）。Ctrl-C 结束。"
              % (args.interval, round_timeout, os.getpid()), flush=True)
        loopmod.write_json_atomic(STATE / "WATCHDOG.json",
                                  {"pid": os.getpid(), "intervalSeconds": args.interval,
                                   "roundTimeoutSeconds": round_timeout,
                                   "startedAt": now(), "host": os.uname().nodename,
                                   "note": "本会话内常驻守护；跨会话持久化请用 Mirasim 排期（loop/SCHEDULE.md）"})
        while True:
            interrupted = False
            try:
                subprocess.run([sys.executable, "-B", "-s", str(Path(__file__).resolve()),
                                "--once", "--no-spawn" if args.no_spawn else "--json"],
                               cwd=str(ROOT), timeout=round_timeout)
            except Exception as exc:
                interrupted = True
                print("本轮守护异常：%r" % (exc,), file=sys.stderr, flush=True)
            time.sleep(60 if interrupted else max(30, args.interval))
        return 0

    if not single_instance():
        print(json.dumps({"skipped": "已有守护轮在跑（GUARD.lock 新鲜且进程存活）"}, ensure_ascii=False))
        return 0
    t0 = time.time()
    pol = ensure_policy()
    report = {"at": now(), "pid": os.getpid(), "policy": {k: pol[k] for k in
              ("maxConcurrentLeases", "leaseTtlSeconds", "taskTimeoutSeconds", "expertReviewEveryPublishes")}}

    report["disk"] = disk_guard()

    report["schedule"] = schedule_health()

    reaped = subprocess.run([sys.executable, "-B", "-s", str(LOOP / "bin" / "loop.py"), "reap"],
                            cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    try:
        _reap_line = next((l for l in reversed((reaped.stdout or "").splitlines()) if l.strip().startswith("{")), "{}")
        report["reaped"] = json.loads(_reap_line).get("reaped", [])
    except Exception:
        report["reaped"] = ["(reap 输出无法解析)"]

    roster = pol["workers"]
    roster_names = {w["name"] for w in roster}
    actions = []
    try:
        ps_txt = subprocess.run(["pgrep", "-fl", "worker.py --agent"], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        ps_txt = ""
    import re as _re
    running = {m for m in _re.findall(r"--agent (\S+)", ps_txt) if m.startswith("w-")}
    stray = sorted(running - roster_names)
    if stray:
        print("[warn] 有 worker 在跑但不在 roster（监控盲区）：%s" % ", ".join(stray), file=sys.stderr)
    for w in roster:
        name, streams = w["name"], w.get("streams", [])
        if worker_alive(name, streams):
            actions.append({"worker": name, "action": "alive"})
            continue
        _running_now = running_streams()
        drifted = worker_alive(name) and _running_now.get(name, set()) != set(streams)
        if drifted and not args.no_spawn and restart_budget_ok(name):
            had = sorted(_running_now.get(name, set()))
            stop_worker(name)
            for _ in range(20):
                if not worker_alive(name):
                    break
                time.sleep(0.5)
            if worker_alive(name):
                actions.append({"worker": name, "action": "restart-deferred(旧进程未退出，本轮不重复拉起)",
                                "had": had, "want": streams})
                continue
            logf = spawn_worker(name, streams)
            actions.append({"worker": name, "action": "restarted(stream-drift)",
                            "had": had, "want": streams, "log": logf})
            continue
        if args.no_spawn:
            actions.append({"worker": name, "action": "dead(未拉起：--no-spawn)"})
            continue
        if not restart_budget_ok(name):
            actions.append({"worker": name, "action": "dead(超出当日重启上限，需人工查看日志)"})
            continue
        logf = spawn_worker(name, streams)
        actions.append({"worker": name, "action": "spawned", "log": logf})
    report["workers"] = actions
    report["strayWorkers"] = stray

    prog = progress()
    report["progress"] = prog

    try:
        doc = subprocess.run([sys.executable, "-B", "-s", str(LOOP / "bin" / "doctor.py"), "--json"],
                             cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        report["doctor"] = json.loads(doc.stdout or "{}")
    except Exception as exc:
        report["doctor"] = {"error": repr(exc)}

    report["topUp"] = top_up_queue(prog)

    report["stall"] = stall_check(prog, pol, report.get("doctor"))

    _ao = (report.get("doctor") or {}).get("accountOutage") or {}
    if _ao.get("detected"):
        report["accountOutage"] = _ao

    report["expert"] = maybe_expert_review(prog)

    report["seconds"] = round(time.time() - t0, 1)
    loopmod.write_json_atomic(GUARD_REPORT, report)
    with (STATE / "GUARD-HISTORY.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": report["at"], "done": prog["done"], "tasks": prog["tasks"],
                             "rejected": prog["rejectedCount"], "pendingVerify": prog["pendingVerifyCount"],
                             "stall": report["stall"]}, ensure_ascii=False) + "\n")
    with GUARD_LOG.open("a", encoding="utf-8") as fh:
        fh.write("## %s\n\n" % report["at"])
        fh.write("- 完成 %d / %d（拒绝 %d，待复核 %d）\n" % (prog["done"], prog["tasks"], prog["rejectedCount"], prog["pendingVerifyCount"]))
        fh.write("- 按流：%s\n" % json.dumps(prog["perStream"], ensure_ascii=False))
        fh.write("- worker：%s\n" % ", ".join("%s=%s" % (a["worker"], a["action"]) for a in actions))
        sch = report.get("schedule") or {}
        if sch.get("configured"):
            ags = ",".join(str(x.get("agent")) for x in (sch.get("schedules") or []))
            fh.write("- 排期：已配置 %d 条（agent=%s）；最近运行 %s\n" % (
                len(sch.get("schedules") or []), ags or "-",
                ", ".join(str(r.get("status")) for r in (sch.get("recentRuns") or [])) or "无"))
            for w in (sch.get("warnings") or []):
                fh.write("- **排期告警**：%s\n" % w)
        else:
            fh.write("- **排期告警**：本工作区没有跨会话排期 —— 进程被清理后不会自愈（见 loop/SCHEDULE.md）\n")
        dk = report.get("disk") or {}
        if dk.get("ok") is False:
            fh.write("- **磁盘告警**：可写=%s，余量 %.2f GB（阈值 %.1f GB）—— 写满会让每个任务 OSError(28)，"
                     "先清理再看别的\n" % (dk.get("writable"), dk.get("freeGB") or -1, dk.get("minFreeGB") or 0))
        else:
            fh.write("- 磁盘：可写=%s 余量 %.2f GB\n" % (dk.get("writable"), dk.get("freeGB") or -1))
        _ao = report.get("accountOutage") or {}
        if _ao.get("detected"):
            fh.write("- **账号停机告警（需用户处理）**：最近 %d 分钟内 **%d 次**失败带"
                     "「自有档无账号」标记 —— **每个新任务都被挡回，流水线整体停摆**，"
                     "这不是任务难。处置：设置 › 线路/全局档位 切到「平台」，或为该 agent 登录自有账号"
                     "（本机 agent_accounts=[]）。见 PROJECT-STATE §4e H1。样本：%s\n"
                     % (_ao.get("windowSeconds", 0) // 60, _ao.get("count"),
                        ", ".join(s.get("task") or "?" for s in (_ao.get("samples") or [])[:3])))
        dsum = (report.get("doctor") or {}).get("summary") or {}
        if dsum:
            fh.write("- 活性：干活 %s / 卡住 %s / 不在 %s / 空闲 %s / **坏掉 %s**\n" % (
                dsum.get("working"), dsum.get("stalled"), dsum.get("down"), dsum.get("idle"),
                dsum.get("broken", 0)))
            stalled = [w["worker"] for w in (report["doctor"].get("workers") or []) if str(w.get("verdict","")).startswith("stalled")]
            if stalled:
                fh.write("- **卡住的 worker**：%s（看 loop/state/logs/<worker>-<task>-*.log 末尾）\n" % ", ".join(stalled))
            broken = [w["worker"] for w in (report["doctor"].get("workers") or []) if str(w.get("verdict","")).startswith("broken")]
            if broken:
                fh.write("- **启动即失败的 worker**：%s —— 进程活着但每个任务秒退，产出为 0；"
                         "先查 dsh profile castline 与 node 路径\n" % ", ".join(broken))
        fh.write("- 补队列：%s\n- 停滞：%s\n- 专家复核：%s\n\n" % (report["topUp"], report["stall"], report["expert"]))

    GUARD_LOCK.unlink(missing_ok=True)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _running_count = sum(1 for a in actions
                             if a["action"] in ("alive", "spawned", "restarted(stream-drift)"))
        print("守护轮完成：完成 %d/%d，worker %d 个，%s" % (
            prog["done"], prog["tasks"], _running_count, report["stall"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
