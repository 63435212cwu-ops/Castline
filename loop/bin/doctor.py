#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""worker 存活探测：一个进程活着不等于它在干活。

为什么需要：worker 空转时进程照样在、CPU 照样有、日志照样写「启动」——
只看 `pgrep` 会把**卡死的流水线**读成「正常运行」。计划100 的方法论教训是
「机制存在、有产出，但不产生信息」，这里对应的是「进程存在、但不推进」。

判据（全部可复现）：
  * 该 worker 最近一次**任务级**日志行的时间（不是进程启动时间）；
  * 它当前持有租约的心跳（`loop/state/leases/<task>.d/lease.json`）；
  * 与它配对的 dsh agent 进程是否真的存在；
  * 这些是否已超过阈值。

用法：
  python3 -B -s loop/bin/doctor.py                 # 人读报告
  python3 -B -s loop/bin/doctor.py --json          # 机器读
  python3 -B -s loop/bin/doctor.py --stale 900     # 自定义「多久算卡住」（秒）
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
LOGS = LOOP / "state" / "logs"
RUNS = LOOP / "state" / "runs"

TS_RE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\]")

FAST_FAIL_SECONDS = 5.0
FAST_FAIL_ALERT = 2


def fast_fail_signature(window_seconds: int = 900) -> dict:
    """统计最近一段时间里「启动即失败」的任务，按 worker 聚合。

    真实事故（2026-10-09 12:28，本次停机）：`castline` profile 不在新会话的
    DSH_HOME 里 ⇒ **每个**任务都在 0.1–0.2 秒内死于
    `dsh: profile "castline" does not exist`。
    当时看板显示：13 个 worker 全部 `alive`、doctor 报「干活 3 / 空闲 10」、
    selftest 全绿、租约与心跳都正常 —— **产出为 0，而没有任何一处变红**。
    唯一异常是 `run-*.json` 里 `seconds≈0.1`；旧口径只把它读成
    `idle-or-starting`（"刚起来还没领到活"），于是「启动即失败」被当成了"空闲"。

    所以这里把「任务级瞬时失败」单独变成一个**可告警**的量：
    一个 worker 在窗口内失败 N 次、且每次耗时都远小于正常单章耗时（中位约 1800s），
    那它不是"在跑"，而是**环境坏了**。命中即告警，不再算空闲。
    """
    out: dict = {}
    if not RUNS.is_dir():
        return out
    now = time.time()
    for p in RUNS.glob("run-*.json"):
        try:
            d = json.loads(p.read_text("utf-8"))
        except Exception:
            continue
        secs = d.get("seconds")
        rc = d.get("rc")
        at = d.get("at")
        if rc == 0 or not isinstance(secs, (int, float)) or secs > FAST_FAIL_SECONDS or not at:
            continue
        try:
            ts = datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            continue
        if now - ts > window_seconds:
            continue
        e = out.setdefault(d.get("agent") or "?", {"fastFails": 0, "lastAt": at, "sampleTask": d.get("task")})
        e["fastFails"] += 1
        if at > e["lastAt"]:
            e["lastAt"], e["sampleTask"] = at, d.get("task")
    return out


def load_loop_module():
    spec = importlib.util.spec_from_file_location("loopmod_d", LOOP / "bin" / "loop.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


loopmod = load_loop_module()


_PROC_CACHE = {"at": 0.0, "rows": []}


def proc_table() -> list:
    nowt = time.time()
    if nowt - _PROC_CACHE["at"] < 1.0 and _PROC_CACHE["rows"]:
        return _PROC_CACHE["rows"]
    try:
        rows = subprocess.run(["ps", "-eo", "pid=,ppid=,etime=,command="], capture_output=True, text=True, timeout=20).stdout.splitlines()
    except Exception:
        rows = []
    _PROC_CACHE["at"] = nowt
    _PROC_CACHE["rows"] = rows
    return rows


def elapsed_seconds(text: str) -> float:
    """ps 的 etime：[[dd-]hh:]mm:ss"""
    text = text.strip()
    days = 0
    if "-" in text:
        d, text = text.split("-", 1)
        days = int(d)
    parts = [int(x) for x in text.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return days * 86400 + h * 3600 + m * 60 + s


def last_task_log_line(agent: str) -> dict:
    """worker 的关键日志行及其「多久以前」。

    坑（真实误报换来的）：daemon.log 的行首只有 `[HH:MM:SS]`，**没有日期**。
    第一版把它拼成「今天」再相减，于是任何一条昨天写的、或时间在未来的行
    都会算出巨大的 age，把**健康的 worker 报成卡住**。w-xiyou-1 就这样被误报过一次。
    正确做法：直接看**文件自身的 mtime** 与**租约心跳**，行首时间只用于展示。
    """
    daemon = LOGS / ("%s.daemon.log" % agent)
    plain = LOGS / ("%s.log" % agent)
    wstate = LOOP / "state" / "workers" / ("%s.json" % agent)
    target = daemon if daemon.exists() else plain
    if plain.exists() and (not daemon.exists() or plain.stat().st_mtime > daemon.stat().st_mtime):
        target = plain
    if not target.exists():
        return {"file": str(daemon.relative_to(ROOT)), "exists": False}
    lines = target.read_text("utf-8", errors="replace").splitlines()
    last = None
    for line in reversed(lines):
        if TS_RE.match(line) and ("→" in line or "结束" in line or "启动" in line or "空转" in line):
            last = {"line": line}
            break
    mtime = target.stat().st_mtime
    if wstate.exists():
        try:
            mtime = max(mtime, wstate.stat().st_mtime)
        except OSError:
            pass
    file_age = max(0.0, time.time() - mtime)
    return {"file": str(target.relative_to(ROOT)), "exists": True,
            "last": last, "fileSecondsAgo": round(file_age, 1)}


def _parse_proc_row(line: str):
    parts = line.strip().split(None, 3)
    if len(parts) == 4 and parts[0].isdigit() and parts[1].isdigit():
        return parts[0], int(parts[1]), parts[2], parts[3]
    parts3 = line.strip().split(None, 2)
    if len(parts3) == 3 and parts3[0].isdigit():
        return parts3[0], None, parts3[1], parts3[2]
    return None, None, "", ""


def agent_proc(agent: str) -> dict:
    """worker 进程本身，并顺带看它有没有活着的子进程（= 正在跑一次 dsh 调用）。

    只看 worker 进程会漏掉「领了任务、子 agent 正在读原文」这种**正常但无租约心跳之外迹象**的状态。
    单次 ps -eo pid=,ppid=,etime=,command= 直接在内存匹配父子关系，消除 O(W*N) 的 ps 子进程风暴。
    """
    rows = proc_table()
    for line in rows:
        if "worker.py" in line and ("--agent %s" % agent) in line and "sentinel" not in line:
            pid, _, etime, _ = _parse_proc_row(line)
            if not pid:
                continue
            target_ppid = int(pid)
            children = []
            for other in rows:
                opid, oppid, _, ocmd = _parse_proc_row(other)
                if not opid:
                    continue
                if oppid is None:
                    try:
                        oppid = int(subprocess.run(["ps", "-o", "ppid=", "-p", opid],
                                                   capture_output=True, text=True, timeout=5).stdout.strip() or 0)
                    except Exception:
                        oppid = 0
                if oppid == target_ppid:
                    children.append({"pid": opid, "command": ocmd[:80]})
            return {"pid": pid, "elapsed": etime, "elapsedSeconds": elapsed_seconds(etime),
                    "children": children}
    return {}


def active_dsh_count() -> int:
    n = 0
    for line in proc_table():
        if "dsh-profile" in line or ("dsh" in line and "castline" in line):
            n += 1
    return n


def diagnose(stale_seconds: int) -> dict:
    pol = loopmod.policy()
    leases = loopmod.active_leases()
    fastfails = fast_fail_signature()
    workers = []
    for w in pol.get("workers", []):
        name = w["name"]
        proc = agent_proc(name)
        mine = [t for t, info in leases.items() if info.get("agent") == name]
        lease = leases.get(mine[0]) if mine else None
        hb_age = None
        if lease and lease.get("heartbeatAt"):
            try:
                hb_age = time.time() - datetime.strptime(lease["heartbeatAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
            except Exception:
                hb_age = None
        entry = {
            "worker": name, "streams": w.get("streams"),
            "process": proc or None,
            "dshChild": bool(proc and proc.get("children")),
            "task": mine[0] if mine else None,
            "heartbeatSecondsAgo": round(hb_age, 1) if hb_age is not None else None,
            "log": last_task_log_line(name),
        }
        ff = fastfails.get(name)
        if ff and ff["fastFails"] >= FAST_FAIL_ALERT:
            entry["verdict"] = "broken(fast-fail)"
            entry["fastFails"] = ff["fastFails"]
            entry["fastFailSample"] = ff["sampleTask"]
            entry["fastFailLastAt"] = ff["lastAt"]
        elif not proc:
            entry["verdict"] = "down"
        elif mine and (hb_age is None or hb_age < stale_seconds):
            entry["verdict"] = "working"
        elif mine and hb_age is not None and hb_age >= stale_seconds:
            entry["verdict"] = "stalled(held-lease)"
        else:
            age = (entry["log"] or {}).get("fileSecondsAgo")
            has_agent = bool(entry.get("dshChild"))
            if has_agent:
                entry["verdict"] = "working"
            elif age is not None and age > stale_seconds:
                entry["verdict"] = "stalled(no-task-progress)"
            else:
                entry["verdict"] = "idle-or-starting"
        workers.append(entry)
    return {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "staleSeconds": stale_seconds,
        "dshAgentProcesses": active_dsh_count(),
        "workers": workers,
        "summary": {
            "working": sum(1 for w in workers if w["verdict"] == "working"),
            "stalled": sum(1 for w in workers if w["verdict"].startswith("stalled")),
            "down": sum(1 for w in workers if w["verdict"] == "down"),
            "idle": sum(1 for w in workers if w["verdict"] == "idle-or-starting"),
            "broken": sum(1 for w in workers if w["verdict"].startswith("broken")),
        },
        "fastFailWorkers": {k: v for k, v in fastfails.items() if v["fastFails"] >= FAST_FAIL_ALERT},
        "failureLedger": failure_ledger_split(),
        "accountOutage": account_outage(),
    }


OWN_MODE_MARKERS = ("「自有」档", "Own mode is on", "no account on this machine",
                    "MISSING_CREDENTIAL")


def account_outage(window_seconds: int = 1800, threshold: int = 3) -> dict:
    """最近的失败里，有多少是**账号/线路档位**造成的（而不是任务内容）。

    判据取自 agent 日志里的明确串（与 worker.classify_failure 同一来源口径），
    并给出「最近 N 秒内触发 ≥ threshold 次」⇒ 判为系统性停机。
    """
    runs = LOOP / "state" / "runs"
    nowt = time.time()
    hits = []
    for f in sorted(runs.glob("run-*.json")):
        try:
            if nowt - f.stat().st_mtime > window_seconds:
                continue
            d = loopmod.load_json(f, {}) or {}
        except Exception:
            continue
        if d.get("rc") in (0, None):
            continue
        log = d.get("log")
        if not log:
            continue
        lp = Path(log)
        if not lp.is_absolute():
            lp = ROOT / log
        try:
            txt = lp.read_text("utf-8", errors="replace")
        except Exception:
            continue
        if any(m in txt for m in OWN_MODE_MARKERS):
            hits.append({"task": d.get("task"), "at": d.get("at")})
    return {"detected": len(hits) >= threshold, "count": len(hits),
            "windowSeconds": window_seconds, "threshold": threshold,
            "samples": hits[:5],
            "meaning": ("账号/线路档位把每个新任务都挡回来了 —— 这是**用户侧设置**"
                        "（§4e H1），不是任务难；本环境改不了。")}


def failure_ledger_split() -> dict:
    """把 `FAILED-TASKS.json` 按**归因**拆开报出来（E31 的可读面）。

    为什么需要：E31 的问题不是"失败被记账"，而是账**把两种完全不同的失败写成一个数字**，
    于是人和后续 agent 会照它去查一个并不难的单元。分账写进台账只是前半；
    后半是**必须有人读它** —— 否则那一栏等于不存在（本项目的老形态：机制存在、
    有产出、但不产生信息，见 E1/E2/E14）。
    """
    led = loopmod.load_json(loopmod.STATE / "FAILED-TASKS.json", {}) or {}
    content, infra, unlabelled = [], [], []
    for tid, ent in led.items():
        if not isinstance(ent, dict):
            continue
        row = {"task": tid, "consecutive": ent.get("consecutive", 0),
               "infraConsecutive": ent.get("infraConsecutive", 0),
               "total": ent.get("total", 0),
               "lastInfraLabel": ent.get("lastInfraLabel"),
               "rcs": ent.get("rcs")}
        if "infraConsecutive" not in ent:
            unlabelled.append(row)
        elif ent.get("infraConsecutive"):
            infra.append(row)
        elif ent.get("consecutive"):
            content.append(row)
        else:
            unlabelled.append(row)
    content.sort(key=lambda r: -r["consecutive"])
    infra.sort(key=lambda r: -r["infraConsecutive"])
    return {
        "contentFailures": content,
        "infraFailures": infra,
        "unlabelled": unlabelled,
        "note": ("判据：键 `infraConsecutive` 是否存在 —— **不是**它的值。"
                 "分账之前（2026-10-09 23:xx 之前）的条目没有这个键，"
                 "它们的 `consecutive` 里混着基础设施失败，**不能**当「难任务」读；"
                 "实测 read:dafeng:L2:0110 的 consecutive=16，而它 18 份日志里 12 份带"
                 "基础设施错误串。新记录已按 worker.classify_failure() 分账。"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stale", type=int, default=900, help="多久没进展算卡住（秒）")
    args = ap.parse_args()
    rep = diagnose(args.stale)
    out = LOOP / "state" / "DOCTOR.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0
    s = rep["summary"]
    print("worker 诊断（%s，阈值 %ds）：干活 %d / 卡住 %d / 不在 %d / 空闲 %d / **坏掉 %d**；本机 dsh agent 进程 %d" % (
        rep["at"], args.stale, s["working"], s["stalled"], s["down"], s["idle"],
        s.get("broken", 0), rep["dshAgentProcesses"]))
    for w in rep["workers"]:
        age = (w["log"] or {}).get("fileSecondsAgo")
        print("  %-12s %-24s task=%-26s hb=%-7s log=%-8s child=%s" % (
            w["worker"], w["verdict"], w["task"] or "-",
            ("%.0fs" % w["heartbeatSecondsAgo"]) if w["heartbeatSecondsAgo"] is not None else "-",
            ("%.0fs前" % age) if age is not None else "-",
            "有" if w.get("dshChild") else "无"))
    broken = [w for w in rep["workers"] if w["verdict"].startswith("broken")]
    if broken:
        print("\n**启动即失败**的 worker：%s" % ", ".join(w["worker"] for w in broken))
        print("含义：进程活着、但每个任务在 %.0f 秒内就退出 ⇒ **产出为 0**，这不算空闲、算故障。"
              % FAST_FAIL_SECONDS)
        _ao_now = rep.get("accountOutage") or {}
        if _ao_now.get("detected"):
            print("  **最可能的原因（实测已命中）**：账号/线路档位把请求挡回"
                  "（%d 次 / 最近 %d 分钟）。" % (_ao_now.get("count"), _ao_now.get("windowSeconds", 0) // 60))
            print("  ⇒ 先处理这个：设置 › 线路/全局档位 切到「平台」，或为该 agent 登录自有账号"
                  "（见 PROJECT-STATE §4e H1b）。**profile/node 不是本次原因**，下面三条只用于排除。")
        print("先查这三件事（按历史事故频率排序）：")
        print("  1) `dsh --profile castline --help` 能不能跑 —— profile 不在本会话 DSH_HOME 里是最常见原因；")
        print("  2) `printf '%s' \"$DSH_HOME\"` 与 `ls $DSH_HOME/profiles/castline` 是否一致；")
        print("  3) `which node` 是否存在（node 升级后旧路径消失会让每个任务 rc=127）。")
    stalled = [w["worker"] for w in rep["workers"] if w["verdict"].startswith("stalled")]
    if stalled:
        print("\n卡住的 worker：%s" % ", ".join(stalled))
        print("处置建议：看 `loop/state/logs/<worker>-<task>-*.log` 末尾，判断是模型卡住、工具报错，还是任务本身太大。")
    ao = rep.get("accountOutage") or {}
    if ao.get("detected"):
        print("\n\u26a0 **账号/线路档位停机**（%d 次 / 最近 %d 分钟）：每个新任务都被挡回，"
              "**不是任务难**。实测样本：%s"
              % (ao.get("count"), ao.get("windowSeconds", 0) // 60,
                 ", ".join(s.get("task") or "?" for s in (ao.get("samples") or [])[:3])))
        print("  处置（**只能由用户做**，见 PROJECT-STATE §4e H1）：在 设置 › 线路/全局档位 切到「平台」，"
              "或为该 agent 登录一个自有账号（本机 agent_accounts=[] ）。")
    fl = rep.get("failureLedger") or {}
    infra = fl.get("infraFailures") or []
    unlab = fl.get("unlabelled") or []
    content = fl.get("contentFailures") or []
    if infra:
        print("\n**基础设施失败**（与任务内容无关，别当「这一章做不出来」读）：%d 条 —— %s" % (
            len(infra),
            ", ".join("%s(%s)" % (r["task"], r.get("lastInfraLabel") or "infra") for r in infra[:5])))
    if unlab:
        print("**分账之前的旧台账**（consecutive 里混着基础设施失败，不能当难任务读）：%d 条" % len(unlab))
    if content:
        print("真正的内容失败（需要看原文/换策略）：%d 条 —— %s" % (
            len(content), ", ".join("%s×%d" % (r["task"], r["consecutive"]) for r in content[:5])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
