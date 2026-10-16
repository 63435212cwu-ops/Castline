#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Castline 持续运行环境 · 任务领取 / 租约 / 证据提交。

设计约束（全部来自本工作区的真实事故，不是通用最佳实践）：

1. **状态即文件**：队列由 `loop/queue/*.jsonl` 推导，完成即 `loop/state/out/<id>.json`。
   没有可损坏的中央数据库；进程被 kill、机器重启都不需要恢复逻辑。
2. **原子租约**：用 `os.mkdir` 抢 `loop/state/leases/<id>.d`（POSIX 原子）。
   计划100 的真实事故：两个写入者并行改 `js/sky/sky-shell-player.js`，
   accept 读到"半个文件"，报出 `scrubDown is not defined` 这种**看起来像真缺陷**的假缺陷。
   因此租约必须在**文件级**成立，而不只是任务级。
3. **提交即校验**：`submit` 检查证据文件真实存在、sha256 与声明一致、改动路径分类正确。
   计划100 记下 6 次"虚假声称"（源码未改、契约未插、gaps 写空、数字对不上）。
   所以证据门必须是机器判的，不能靠报告里的措辞。
4. **共享树只读**：worker 一律在 `.workbuddy/wt-<agent>` 的 git worktree 里干活；
   写回共享树只有两条路——(a) **追加**新文件（证据/台账/内容候选），
   (b) 单独的 serialized 合并任务并在合并前加 `GATE.lock`。

用法（worker 视角）：
    python3 loop/bin/loop.py next   --agent w-1            # 看下一个任务（不占用）
    python3 loop/bin/loop.py claim  --task ID --agent w-1  # 原子抢租约
    python3 loop/bin/loop.py next   --agent w-1 --claim    # 一步到位
    python3 loop/bin/loop.py beat   --task ID --agent w-1  # 长任务心跳
    python3 loop/bin/loop.py submit --file out.json --agent w-1
    python3 loop/bin/loop.py reap                          # 回收死租约
    python3 loop/bin/loop.py stats
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
QUEUE = LOOP / "queue"
STATE = LOOP / "state"
LEASES = STATE / "leases"
OUT = STATE / "out"
RUNS = STATE / "runs"
WORKERS = STATE / "workers"
POLICY = STATE / "policy.json"
GATE_LOCK = LEASES / "GATE.lock"

APPEND_PREFIXES = ("loop/", "tests/fixtures/loop/", "content-candidate/")
ARTIFACT_PREFIXES = (
    "artifacts/",
    "reports/",
    "shots/",
)
GUARDED_PREFIXES = (
    "js/",
    "css/",
    "index.html",
    "serve.py",
    "narrative.py",
    "distill.py",
    "scripts/",
    "tests/",
    "tools/",
    "docs/",
    "data/",
    "artifacts/plan100/BRIEFING.md",
    "artifacts/plan100/FILE-OWNERSHIP.md",
)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
_HEADLESS_STRIP_EXACT = (
    "CODEBUDDY_SESSION_ID",
    "CLAUDE_SESSION_ID",
    "CODEBUDDY_CONVERSATION_MESSAGE_ID",
    "CODEBUDDY_NODE_BIN",
)
_HEADLESS_STRIP_PREFIX = ("CODEBUDDY_SAFE_DELETE",)


def sanitize_headless_env(env=None) -> list:
    """剥掉交互会话专属变量（默认改 os.environ），返回被剥掉的键名列表。"""
    target = os.environ if env is None else env
    removed = []
    for key in list(target.keys()):
        if key in _HEADLESS_STRIP_EXACT or key.startswith(_HEADLESS_STRIP_PREFIX):
            del target[key]
            removed.append(key)
    return removed


sanitize_headless_env()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch() -> float:
    return time.time()


_SHA256_CACHE_LIMIT = 8192
_SHA256_CACHE = OrderedDict()
_RECORD_META_CACHE = OrderedDict()
_RECORD_META_CACHE_LIMIT = 4096


def _hash_fingerprint(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _pid_alive(pid) -> bool:
    """POSIX 进程探活：EPERM 表示进程存在但当前沙盒/用户无权发信号，ESRCH 才是已消失。"""
    try:
        p = int(pid)
    except Exception:
        return False
    if p <= 0:
        return False
    try:
        os.kill(p, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        import errno as _errno
        return exc.errno == _errno.EPERM
    except Exception:
        return False


def _external_volume_inaccessible(cand: Path) -> bool:
    """外置卷路径或指向外置卷的符号链接在受限沙盒下触发 PermissionError 时不崩进程。"""
    try:
        cand.stat()
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def sha256_file(path: Path) -> str:
    path = Path(path).absolute()
    key = str(path)
    for _attempt in range(2):
        try:
            before = _hash_fingerprint(path.stat())
        except OSError:
            _SHA256_CACHE.pop(key, None)
            raise
        cached = _SHA256_CACHE.get(key)
        if cached is not None and cached[0] == before:
            _SHA256_CACHE.move_to_end(key)
            return cached[1]
        _SHA256_CACHE.pop(key, None)
        h = hashlib.sha256()
        with path.open("rb") as fh:
            opened = _hash_fingerprint(os.fstat(fh.fileno()))
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
            after_read = _hash_fingerprint(os.fstat(fh.fileno()))
        after_path = _hash_fingerprint(path.stat())
        if before == opened == after_read == after_path:
            digest = h.hexdigest()
            _SHA256_CACHE[key] = (after_path, digest)
            while len(_SHA256_CACHE) > _SHA256_CACHE_LIMIT:
                _SHA256_CACHE.popitem(last=False)
            return digest
    raise OSError("证据文件读取期间持续变化：%s" % path)


def lease_dir(tid: str) -> Path:
    """任务 id → 租约目录。唯一命名来源；claim/beat/release/reap 都用它。

    注意：这里**保留冒号**（历史租约就是这么建的），改动会让在跑的 worker 失联。
    真要改必须同时迁移所有现存租约目录。
    """
    return LEASES / (tid.replace("/", "__") + ".d")


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp-%d" % os.getpid())
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    os.replace(tmp, path)


def policy() -> dict:
    base = {
        "maxConcurrentLeases": 6,
        "maxGpuLeases": 1,
        "leaseTtlSeconds": 300,
        "gateLockTtlSeconds": 5400,
        "verifyEvery": 5,
        "guardEveryMinutes": 10,
    }
    base.update(load_json(POLICY, {}) or {})
    return base


# --------------------------------------------------------------------------- 队列

def queue_files():
    return sorted(QUEUE.glob("*.jsonl"))


def load_tasks() -> dict:
    """读全部队列。**必须容忍半写坏行**，否则一行坏数据会让整条通道空转。

    真实事故（2026-10-08 03:22，持续 40 秒、两个 worker 共 5198 次报错）：
    某个写入者用**非原子**方式追加 `queue/*.jsonl`，worker 正好读到写了一半的行。
    那一行是合法 JSON 但**不是对象**（例如 `[...]` 或 `"..."`），于是
    `item["id"]` / `item.setdefault(...)` 抛 `AttributeError("'list' object has no attribute 'get'")`。
    worker 的 `except` 把它当成「轮次异常」，而异常路径**不走空转退避** ⇒
    它以每秒上百轮的速度空转刷日志，且该通道在坏行被修好前一直领不到任何任务。
    修法：只要解析结果不是 dict 就跳过（连同缺 id 的行），并把坏行**报出来**，
    不能静默吞掉 —— 静默吞掉会让「队列少了任务」变成看不见的问题。
    """
    tasks = {}
    malformed = []
    for path in queue_files():
        for lineno, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                item = json.loads(line)
            except Exception:
                malformed.append({"file": path.name, "line": lineno, "why": "invalid-json"})
                continue
            if not isinstance(item, dict) or not item.get("id"):
                malformed.append({"file": path.name, "line": lineno,
                                  "why": "not-an-object" if not isinstance(item, dict) else "missing-id",
                                  "type": type(item).__name__})
                continue
            item.setdefault("queueFile", path.name)
            tasks[item["id"]] = item
    if malformed:
        try:
            write_json_atomic(STATE / "MALFORMED-QUEUE.json",
                              {"at": now(), "count": len(malformed), "items": malformed[:50]})
        except Exception:
            pass
    return tasks


def validated(rec: dict) -> bool:
    """一条记录算不算「做完」，由**机器校验**决定，不由文件是否存在决定。

    真实事故（2026-10-08）：任务模板把最终记录路径也放进了 `writes`，
    于是 agent 可以用写文件的方式**直接落一个 status=done 的记录**，
    完全绕过 `submit` 的校验器。审计发现 11 条记录里有 2 条是这样来的。
    修法：done 的定义收紧为「status 达标 **且** validation.problems 为空」。
    未过校验的记录不算完成，会被 worker 重新领取并**补过校验**。
    """
    if rec.get("status") not in ("done", "verified"):
        return False
    v = rec.get("validation")
    return isinstance(v, dict) and v.get("problems") == []


def validated_records() -> list:
    """**全部**校验通过的记录，随后再分「有效 / 证据失效 / 已被取代」。

    为什么必须先枚举再分类（DEL-05 实测缺陷）：
    `done_ids()` 先把 stale 剔掉，`stats` 又只扫描 `done` 集合 ⇒
    `staleEvidenceCount` **结构性地恒为 0**。也就是说，「证据漂移」这个
    真实存在的问题被统计口径隐藏了。共享树里实测能扫到失效记录，
    而看板报 0 —— 这不是数据没问题，是**尺子量不到**。
    """
    recs = []
    for path in record_files():
        rec = load_json(path, {}) or {}
        if validated(rec):
            recs.append(rec)
    return recs


def done_ids() -> dict:
    """真正算「做完」的任务：校验通过 **且证据现在仍然成立**。

    只看 validation 是不够的 —— 证据文件可能在提交之后被覆盖/删除。
    实测出现过一条记录 validation 通过、候选文件随后被重新生成 ⇒ 哈希对不上，
    但它一直算完成、worker 永远不重做。「曾经成立」≠「现在成立」。
    """
    done = {}
    for path in record_files():
        rec = load_json(path, {}) or {}
        if validated(rec) and not evidence_stale(rec):
            done[rec["task"]] = rec
    for tid in published_batches():
        done.setdefault(tid, {"task": tid, "status": "done", "agent": "(publish-ledger)",
                              "validation": {"problems": []},
                              "summary": "已发布（见 loop/state/PUBLISH-LEDGER.json）"})
    return done


def publish_state(done: dict = None, tasks: dict = None) -> dict:
    """把「任务处置完成」与「实际已发布」分开（DEL-01/DEL-06）。

    事故史：`stats` 的 publish done 计数与真实发布回执不是一回事 ——
    B002 的记录明确写 `publishedThisRound=false`、`publishKey=null`
    （**拒发**），却照样进 done 集合，于是看板显示"发布完成"。
    「审阅完成」不等于「发出去了」，更不等于「读者能看见」。

    判据：只有台账里有键、或记录里确有非空 publishKey 的批次，才算**已发布**。
    """
    led = published_batches()
    if done is None:
        done = done_ids()
    if tasks is None:
        tasks = load_tasks()
    published, audited_only, never = {}, [], []
    for t in tasks.values():
        if t.get("stream") != "publish":
            continue
        tid = t["id"]
        rec = (done.get(tid) or {})
        key = rec.get("publishKey")
        if tid in led:
            published[tid] = led[tid]
        elif key:
            published[tid] = key
        elif rec:
            audited_only.append(tid)
        else:
            never.append(tid)
    return {
        "publishedBatches": published,
        "publishedCount": len(published),
        "auditDoneButNotPublished": sorted(audited_only),
        "auditDoneButNotPublishedCount": len(audited_only),
        "neverRun": sorted(never),
        "note": ("publishedCount 是**唯一**可以对外称为「已发布」的数；"
                 "auditDoneButNotPublished 是审阅/尝试完成但**没有新版本键**的批次"
                 "（拒发是有价值的审阅结果，但不是已发布）。"),
    }


TRANSIENT_PREFIXES = ("loop/state/leases/", "loop/state/GUARD.lock",
                      "loop/state/workers/", "loop/state/runs/")
TRANSIENT_PREFIXES += ("/tmp/", "/var/folders/")


def is_transient(path: str) -> bool:
    p = str(path).replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if p.startswith(TRANSIENT_PREFIXES):
        return True
    root = str(ROOT).replace("\\", "/").rstrip("/")
    if root and p.startswith(root + "/"):
        return is_transient(p[len(root) + 1:])
    return False


EVOLVING_PREFIXES = ("loop/", "scripts/", "tests/", "tools/", "docs/")
MUTABLE_EXCEPTIONS = ("loop/state/out/",)

VOLATILE_INDEX_FILES = ("data/cache/index.json",)


def is_evolving(path: str) -> bool:
    p = path.lstrip("./")
    if p.startswith(MUTABLE_EXCEPTIONS):
        return False
    if p in VOLATILE_INDEX_FILES:
        return True
    return p.startswith(EVOLVING_PREFIXES)


def evidence_stale(rec: dict) -> list:
    """记录里的证据是否**已经不再成立**（文件消失或哈希不符）。

    为什么需要：`submit` 只在提交那一刻校验证据，之后文件可能被覆盖/重写。
    实测出现过：一条记录 validation 通过，但它的候选文件后来被重新生成，
    哈希对不上 —— 而 `done_ids()` 仍把它算作完成，worker 永远不会重做。
    「曾经成立」不等于「现在成立」。
    """
    bad = []
    for item in (rec.get("evidence") or []):
        if not isinstance(item, dict) or "path" not in item:
            continue
        if is_transient(item["path"]):
            continue
        cand = Path(item["path"])
        cand = cand if cand.is_absolute() else ROOT / cand
        if _external_volume_inaccessible(cand):
            continue
        if not cand.exists():
            bad.append({"path": item["path"], "why": "missing"})
        elif item.get("sha256") and sha256_file(cand) != item["sha256"]:
            if not is_evolving(item["path"]):
                bad.append({"path": item["path"], "why": "hash-changed"})
    return bad


def weak_evidence(rec: dict) -> list:
    """记录里**不可校验**的证据条目：文件在，但没声明 sha256。

    E32（2026-10-09 22:5x，由 teammate `evidence-auditor` 的独立审计查出 TP-1）：
    这类条目让 `evidence_stale()` 退化成「文件存在即成立」⇒ 证据此后被改坏永久隐身。
    新提交已由 `validate()` 直接拒绝；**存量**记录**不追溯判死**，只在这里列出来——
    理由见 validate() 里的说明：把历史宽松口径记成"今天集中失败"是 E15/E30 的错误。
    """
    out = []
    for item in (rec.get("evidence") or []):
        if not isinstance(item, dict) or "path" not in item:
            continue
        if item.get("sha256"):
            continue
        if is_transient(item["path"]):
            continue
        out.append({"path": item["path"]})
    return out


PUBLISH_LEDGER = STATE / "PUBLISH-LEDGER.json"


def published_batches() -> dict:
    """已发布的批次 → 发布键。

    为什么需要：图谱版本里没有反向索引能回答「这批发过没有」。没有这张表时，
    worker 会**反复重发同一批** —— 实测 `publish:dafeng:B000` 连试 3 次，
    每次烧 5–28 分钟，而看板上只是"又失败了一次"。
    """
    led = load_json(PUBLISH_LEDGER, {}) or {}
    out = {}
    for e in led.get("entries") or []:
        if isinstance(e, dict) and e.get("batch"):
            out[str(e["batch"])] = str(e.get("graphKey") or "")
    return out


def record_files() -> list:
    """只返回**规范命名的提交记录**：`<id 规范化>.json`。

    坑（实测）：agent 会顺手再写一份 `<id>.submit.json` / `<id>.verdict.json` 作为
    产物副本，它们没有 `validation` 字段。第一版扫描 `out/*.json` 全目录，于是把这些
    副本也当成"未过校验的记录"，导致：
      * `unvalidated_ids()` 永远非空（噪音，掩盖真问题）；
      * `doctor`/看板上出现无法消失的告警。
    判据：文件名必须**恰好等于** `output_name(task)`。
    """
    found = []
    for path in sorted(OUT.glob("*.json")):
        name = path.name
        if name.startswith("REJECTED__") or name.endswith((".candidate.json", ".artifact.json", ".verdict.json", ".submit.json", ".patch.json", ".snapshot.json")):
            continue
        key = str(path)
        try:
            fp = _hash_fingerprint(path.stat())
        except OSError:
            _RECORD_META_CACHE.pop(key, None)
            continue
        cached = _RECORD_META_CACHE.get(key)
        if cached is not None and cached[0] == fp:
            _RECORD_META_CACHE.move_to_end(key)
            if cached[1]:
                found.append(path)
            continue
        rec = load_json(path, {}) or {}
        is_rec = (
            isinstance(rec, dict)
            and bool(rec.get("task"))
            and rec.get("status") in ("done", "verified")
            and name == output_name(rec.get("task"))
        )
        _RECORD_META_CACHE[key] = (fp, is_rec)
        while len(_RECORD_META_CACHE) > _RECORD_META_CACHE_LIMIT:
            _RECORD_META_CACHE.popitem(last=False)
        if is_rec:
            found.append(path)
    return found


def unvalidated_ids() -> list:
    """存在**规范记录**但没过校验的任务 id（用于审计与重新领取）。

    ── 真实缺陷修复（2026-10-09）────────────────────────────────────────
    原实现对每个文件**读两次**：`record_files()` 里读一次（它要求 `task` 存在），
    这里再读一次。若两次读之间文件消失或被替换（worker 正常地重写自己的记录），
    第二次读到 `{}` ⇒ `validated({})` 为 False ⇒ `rec["task"]` 抛
    **`KeyError: 'task'`**，整个 `selftest` 当场崩掉。
    实测（第 15 轮）：selftest 偶发 `KeyError: 'task'` 中途退出，重跑就好 ——
    当时只重跑两次就放过，记成「worker 写产物时的读竞争」。本轮把根因追到这一行，
    并**忠实复现**：构造「record_files 时在、再读时没了」的窗口即抛同一个 KeyError。
    修法：这里用 `rec.get("task")`，取不到就跳过（那份记录已经不在磁盘上了，
    它不属于「存在规范记录但没过校验」的情况）。**不是**把 KeyError 吞掉：
    真的存在但缺 task 键的记录仍会被 `record_files()` 挡在外面。
    """
    out = []
    for path in record_files():
        rec = load_json(path, {}) or {}
        tid = rec.get("task")
        if not tid:
            continue
        if not validated(rec):
            out.append(tid)
    return out


def active_leases() -> dict:
    leases = {}
    for d in LEASES.glob("*.d"):
        info = load_json(d / "lease.json", {}) or {}
        if not info:
            continue
        info["_dir"] = str(d)
        leases[info.get("task", d.stem)] = info
    return leases


def lease_alive(info: dict, ttl_key: str = "leaseTtlSeconds") -> bool:
    """租约是否还新鲜。

    `ttl_key` 让 GATE.lock 用**自己的** TTL（见 policy 里的 gateLockTtlSeconds）：
    它与任务租约的寿命量级完全不同 —— 任务租约短是为了崩溃后快速回收，
    而 GATE.lock 守护的是"这一整段串行写入"，且**没有续期命令**。
    """
    hb = info.get("heartbeatAt") or info.get("startedAt")
    if not hb:
        return False
    try:
        t = datetime.strptime(hb, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return False
    return (epoch() - t) < policy().get(ttl_key, policy()["leaseTtlSeconds"])


def gate_held() -> bool:
    """GATE.lock 现在是否**真的**被人持有（唯一判据来源）。

    为什么要有这个函数（E34，2026-10-10）：门锁的"是否被占用"原先在**三处**各写各的
    （`pick` 的领取闸门、`reap` 的回收、`gate` 的接管），三处都用同一句话
    `lease_alive(load_json(GATE_LOCK, {}) or {}, "gateLockTtlSeconds")` 的**副本**。
    selftest 12u2 因此只能靠 grep 那句字面文本，逼着每一处都抄一遍长表达式 ——
    我一改成"死者立即可回收"，它就报红（检查抓对了：三处里有一处不再带那个常量）。
    真正的修法不是把常量抄得更勤，而是**把判据收敛到一处**：
      · 锁不存在 ⇒ 未被持有；
      · 持有者**确已死亡**（同宿主 + pid 消失）⇒ **未被持有**（可立即接管/回收），
        这正是 E8 给任务租约的那条更强的判据；
      · 否则按 gateLockTtlSeconds 判新鲜度。
    """
    if not GATE_LOCK.exists():
        return False
    info = load_json(GATE_LOCK, {}) or {}
    if _gate_is_dead(info):
        return False
    return lease_alive(info, "gateLockTtlSeconds")


def glob_overlap(a: str, b: str) -> bool:
    if a == b:
        return True
    a2, b2 = a.rstrip("*").rstrip("/"), b.rstrip("*").rstrip("/")
    return a2.startswith(b2 + "/") or b2.startswith(a2 + "/")


def conflicting(tasks, leases):
    taken = []
    for info in leases.values():
        taken.extend(info.get("writes") or [])
    return taken


def _build_dependents_index(tasks: dict, done: dict, leases: dict) -> dict:
    """预构建前置依赖反向索引（O(N) 替代每个任务 O(N^2) 全表扫描）。"""
    by_req = {}
    for other in tasks.values():
        oid = other.get("id")
        if not oid or oid in done or oid in leases:
            continue
        reqs = other.get("requires") or []
        if not reqs:
            continue
        total_missing = sum(1 for r in reqs if r not in done)
        for r in reqs:
            missing_without_r = total_missing - (1 if r not in done else 0)
            by_req.setdefault(r, []).append(missing_without_r)
    return by_req


def unblock_score(task: dict, tasks: dict, done: dict, leases: dict, _dependents: dict = None) -> int:
    """这个任务能**解锁**多少个下游任务（只差它一个的那种）。

    为什么需要（2026-10-08 实测出来的结构缺陷）：
      verify 任务的 seq 是「通道优先」排的 —— 大奉 4 条 lane 各 228 个单元，
      seq 0..227 全是 lane0、684..911 才是 lane3。而 `publish:dafeng:B000`
      要求该批 20 个单元**四条 lane 都复核完**。
      于是按 seq 顺序领活时，复核 worker 把 lane0 从头做到尾，lane3 一直排不上，
      第一个发布批要等 **约 68 小时**（684 个任务 × 1788 秒 ÷ 5 个 worker）——
      这不是产能问题，是排队顺序问题。

    修法：给「解锁下游」的任务更高的优先级。只差一两个前置就能开跑的任务优先做，
    让发布批尽早闭环，而不是让某条 lane 独自跑到天荒地老。
    """
    tid = task["id"]
    if _dependents is not None:
        score = sum(1.0 / (1 + m) for m in (_dependents.get(tid) or ()))
        return int(round(score * 1000))
    score = 0.0
    for other in tasks.values():
        reqs = other.get("requires") or []
        if tid not in reqs:
            continue
        if other["id"] in done or other["id"] in leases:
            continue
        missing = sum(1 for r in reqs if r != tid and r not in done)
        score += 1.0 / (1 + missing)
    return int(round(score * 1000))


def task_sort_key(task: dict, tasks: dict = None, done: dict = None, leases: dict = None, _dependents: dict = None):
    """排序键：先按阶段，再按「能解锁下游的数量」降序，最后才按 seq。

    保持 phase 优先（read → verify → publish 的依赖层次不变）；
    在同一阶段内，优先做能解锁发布批的那些，避免「一条 lane 跑到底」。
    """
    unlock = 0
    if tasks is not None and done is not None and leases is not None:
        unlock = unblock_score(task, tasks, done, leases, _dependents=_dependents)
    return (task.get("phase", 99), -unlock, task.get("seq", 0), task.get("id", ""))


def backoff_blocked() -> dict:
    """仍在**退避窗口**内的任务 → 记录（见 worker._note_failure 的实测事故）。

    为什么需要（真实事故，2026-10-09）：worker 的失败路径没有退避、也不区分失败类型，
    于是 `dsh` 启动即失败（rc=127）时会把**同一个**任务立刻领回来 —— 实测
    `read:dafeng:L0:0080` 被尝试 **1626 次**（其中 1510 次 rc=127）、
    `verify:dafeng:L3:0099` 1213 次。这是拒绝服务级的浪费：进程反复启动、零产出，
    而看板上它表现为『worker 很忙』。

    修法分两半，**缺一不可**：
      ① worker 侧按失败类型做**指数退避**并写 `retryAfter`（worker._note_failure）；
      ② 调度侧**真的跳过**还在窗口内的任务（本函数 + pick 里的 continue）——
         只做①而 pick 不跳过，任务下一轮照样被领回，退避形同虚设。

    为什么用「窗口」而不是「连续失败就永久暂停」：永久暂停只能靠跑成功来解除，
    而暂停后它永远不跑 ⇒ **永久锁死**，把热循环换成静默卡死而已。退避是自愈的。
    """
    led = load_json(STATE / "FAILED-TASKS.json", {}) or {}
    now_t = time.time()
    out = {}
    for tid, ent in led.items():
        if not isinstance(ent, dict):
            continue
        ra = ent.get("retryAfter")
        if isinstance(ra, (int, float)) and ra > now_t:
            out[tid] = ent
    return out


def pick(tasks: dict, agent: str, streams=None):
    pol = policy()
    done = done_ids()
    leases = active_leases()
    blocked = backoff_blocked()
    if len(leases) >= pol["maxConcurrentLeases"]:
        return None, "达到并发上限 %d（当前活跃 %d）" % (pol["maxConcurrentLeases"], len(leases))
    writes_taken = conflicting(tasks, leases)
    gpu_taken = any((i.get("gpu") for i in leases.values()))
    streams = set(streams) if streams else None
    deps_idx = _build_dependents_index(tasks, done, leases)
    for tid in sorted(tasks, key=lambda t: task_sort_key(tasks[t], tasks, done, leases, _dependents=deps_idx)):
        task = tasks[tid]
        if tid in done or tid in leases:
            continue
        if tid in blocked:
            continue
        if streams is not None and task.get("stream") not in streams:
            continue
        if task.get("agentFilter") and agent not in task["agentFilter"]:
            continue
        reqs = task.get("requires") or []
        if any(r not in done for r in reqs):
            continue
        if tid in {r for r in reqs}:
            continue
        if task.get("gpu") and gpu_taken and pol["maxGpuLeases"] <= 1:
            continue
        if task.get("gateLock") and gate_held():
            continue
        writes = task.get("writes") or []
        if any(glob_overlap(w, t) for w in writes for t in writes_taken):
            continue
        return task, None
    return None, "没有可领取的任务（全部完成/被前置阻塞/正被占用）"


def output_name(tid: str) -> str:
    """任务 id → 产出文件名。统一在这里定义，避免「agent 写 A、校验器找 B」这种分裂。"""
    return tid.replace("/", "__").replace(":", "_") + ".json"


def cmd_next(args):
    tasks = load_tasks()
    streams = args.stream.split(",") if args.stream else None
    task, why = pick(tasks, args.agent, streams)
    if not task:
        print(json.dumps({"task": None, "reason": why}, ensure_ascii=False))
        return 1 if args.strict else 0
    if args.claim:
        rc = claim(task, args.agent)
        if rc != 0:
            print(json.dumps({"task": None, "reason": "抢租约失败（已被占用）"}, ensure_ascii=False))
            return 1
    print(json.dumps(task, ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------------- 租约

def claim(task: dict, agent: str) -> int:
    tid = task["id"]
    out_rec_path = OUT / output_name(tid)
    if out_rec_path.exists():
        existing_rec = load_json(out_rec_path, {}) or {}
        if validated(existing_rec) and not evidence_stale(existing_rec):
            return 1
    d = lease_dir(tid)
    try:
        d.mkdir(parents=True)
    except FileExistsError:
        info = load_json(d / "lease.json", {}) or {}
        if lease_alive(info):
            return 1
        shutil.rmtree(d, ignore_errors=True)
        try:
            d.mkdir(parents=True)
        except FileExistsError:
            return 1
    work = ROOT / ".workbuddy" / ("wt-" + agent)
    info = {
        "task": task["id"],
        "agent": agent,
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "startedAt": now(),
        "heartbeatAt": now(),
        "gpu": bool(task.get("gpu")),
        "writes": task.get("writes") or [],
        "worktree": str(work),
        "branch": task.get("branch") or ("loop/" + task["id"].replace("/", "-")),
    }
    write_json_atomic(d / "lease.json", info)
    write_json_atomic(WORKERS / (agent + ".json"), {"agent": agent, "lastSeenAt": now(), "task": task["id"]})
    return 0


def cmd_claim(args):
    tasks = load_tasks()
    task = tasks.get(args.task)
    if not task:
        print("未知任务：%s" % args.task, file=sys.stderr)
        return 2
    rc = claim(task, args.agent)
    print("已占用" if rc == 0 else "占用失败（活跃租约存在）")
    return rc


def cmd_beat(args):
    d = lease_dir(args.task)
    info = load_json(d / "lease.json")
    if not info or info.get("agent") != args.agent:
        print("没有属于 %s 的租约：%s" % (args.agent, args.task), file=sys.stderr)
        return 2
    info["heartbeatAt"] = now()
    if args.note:
        info["note"] = args.note
    write_json_atomic(d / "lease.json", info)
    return 0


def cmd_release(args):
    d = lease_dir(args.task)
    info = load_json(d / "lease.json") or {}
    if info.get("agent") and args.agent and info["agent"] != args.agent and not args.force:
        print("租约属于 %s，拒绝释放" % info["agent"], file=sys.stderr)
        return 2
    shutil.rmtree(d, ignore_errors=True)
    return 0


def cmd_reap(args):
    """回收死租约。

    判据强度（顺序很重要）：**进程已死 > 心跳过期**。
    真实事故：诊断型 agent 自己调 `claim` 建了两条"幽灵租约"（agent 名 q-main、
    w-xiyou-L1-b，进程早已退出），因为心跳还新、TTL 未到，旧版 reap 会把它们
    当成活租约跳过；它们白占 2 个并发额度，把一个真实 worker 挡在门外
    （日志：`idle: 达到并发上限`）。进程死了就是死了，不该等 TTL。
    """
    killed, warned = [], []
    me = socket.gethostname()
    for d in sorted(LEASES.glob("*.d")):
        info = load_json(d / "lease.json", {}) or {}
        if not info:
            shutil.rmtree(d, ignore_errors=True)
            killed.append(d.stem + "(空壳)")
            continue
        pid_alive = None
        if info.get("host") == me and info.get("pid"):
            pid_alive = _pid_alive(info["pid"])
        if pid_alive is False:
            shutil.rmtree(d, ignore_errors=True)
            killed.append("%s(进程 %s 已死)" % (info.get("task", d.stem), info.get("pid")))
            continue
        if pid_alive is None and info.get("host") != me:
            if not lease_alive(info):
                shutil.rmtree(d, ignore_errors=True)
                killed.append("%s(异地租约且心跳过期)" % info.get("task", d.stem))
            continue
        if lease_alive(info):
            continue
        warned.append("%s(pid %s 活但心跳过期)" % (info.get("task", d.stem), info.get("pid")))
    for w in warned:
        print("[warn] 心跳过期但进程仍在，不回收：%s" % w, file=sys.stderr)
    if GATE_LOCK.exists() and not gate_held():
        ginfo = load_json(GATE_LOCK, {}) or {}
        why = ("持有者 pid %s 已消失" % ginfo.get("pid")) if _gate_is_dead(ginfo) else "陈旧"
        GATE_LOCK.unlink(missing_ok=True)
        killed.append("GATE.lock(%s)" % why)
    print(json.dumps({"reaped": killed, "at": now()}, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------- 证据

REQUIRED = ("task", "agent", "status", "summary", "evidence", "assertions", "remaining", "rollback")


def classify(path: str) -> str:
    p = path.lstrip("./")
    for pre in ARTIFACT_PREFIXES:
        if p.startswith(pre):
            return "artifact-only"
    for pre in APPEND_PREFIXES:
        if p.startswith(pre):
            return "append-only"
    for pre in GUARDED_PREFIXES:
        if p == pre or p.startswith(pre.rstrip("/") + "/"):
            return "guarded"
    return "unknown"


# ---------------------------------------------------------------------------
_SECTION_RE = re.compile(r"(?m)^\s*\d+[a-z]?\.\s+`([A-Za-z][A-Za-z0-9_]*)\[\]`")

_INLINE_RE = re.compile(r"`([A-Za-z][A-Za-z0-9_]*)\[\]`")


def required_sections(prompt: str) -> list:
    """从提示词里抽出**顶层**内容分区名。

    两种真实形态（都实测过）：
      · 行首编号：1. tasks[] / 4b. worldSettings[] / 4c. themeReadings[]
      · 内联列举：「产出写进 <路径>：verdict、counterExamples[]、…」

    关键区分：**不能**把任务条目里嵌套的 `quotes[]`（「每栏自带 quotes[]」）当顶层分区。
    行首编号形态天然排除嵌套；内联形态则限定在「产出写进」那一行内。
    """
    if not isinstance(prompt, str) or not prompt:
        return []
    out = []
    for m in _SECTION_RE.finditer(prompt):
        name = m.group(1)
        if name not in out:
            out.append(name)
    for m in re.finditer(r"产出(?:（)?写进[^\n]*?：", prompt):
        chunk = prompt[m.end():m.end() + 500]
        for stop in ("\n\n", "。\n", "。"):
            k = chunk.find(stop)
            if k >= 0:
                chunk = chunk[:k]
        for mm in _INLINE_RE.finditer(chunk):
            name = mm.group(1)
            if name not in out:
                out.append(name)
    return out


def _candidate_path(task: dict):
    """任务声明的写入物里，取那个「承载内容分区」的文件。"""
    for w in (task.get("writes") or []):
        if isinstance(w, str) and w.endswith((".json",)):
            return ROOT / w
    return None


def validate_sections(rec: dict, task: dict) -> list:
    """核对内容分区是否真的产出。

    缺失**不等于**任务失败 —— 提示词允许「本区间没有就写空数组」，
    所以判据是**分区键存在**（可为 `[]`），而不是非空。
    键完全不在 ⇒ 说明该分区根本没被处理，必须报出来。
    """
    want = required_sections(task.get("prompt") or "")
    if not want:
        return []
    path = _candidate_path(task)
    if path is None or not path.exists():
        return []
    cand = load_json(path, {}) or {}
    if not isinstance(cand, dict):
        return []
    missing = [k for k in want if k not in cand]
    if not missing:
        return []
    return ["内容分区未产出：%s（提示词要求 %d 个分区，候选只给了 %d 个；"
            "缺的分区即使本区间没有内容也应写成空数组）"
            % (", ".join(missing), len(want), len(want) - len(missing))]


def validate(rec: dict) -> list:
    problems = []
    for key in REQUIRED:
        if key not in rec:
            problems.append("缺字段 %s" % key)
    if problems:
        return problems
    if rec["status"] not in ("done", "failed", "rejected", "partial"):
        problems.append("status 非法：%r" % rec["status"])
    if not isinstance(rec["evidence"], list) or not rec["evidence"]:
        problems.append("evidence 必须是非空列表（没有证据就等于没做）")
    for ev in rec["evidence"] if isinstance(rec["evidence"], list) else []:
        if not isinstance(ev, dict) or "path" not in ev:
            problems.append("evidence 条目缺 path：%r" % (ev,))
            continue
        if is_transient(ev["path"]):
            problems.append("证据不能是瞬态路径（%s）：租约/心跳/锁/运行日志会按设计被回收，"
                            "/tmp 与 /var/folders 是 OS 临时空间（macOS 会清理）；"
                            "请改为引用留存产物" % ev["path"])
            continue
        p = Path(ev["path"])
        cand = p if p.is_absolute() else (ROOT / p)
        if not cand.exists():
            problems.append("证据文件不存在：%s" % ev["path"])
            continue
        if ev.get("sha256"):
            actual = sha256_file(cand)
            if actual != ev["sha256"]:
                problems.append("证据哈希不符：%s（声明 %s 实际 %s）" % (ev["path"], ev["sha256"][:12], actual[:12]))
        elif rec.get("status") == "done":
            problems.append("证据缺 sha256：%s（声明过的证据必须可复核；"
                            "补上真实哈希再提交）" % ev["path"])
    for ch in rec.get("changes") or []:
        kind = ch.get("kind") or classify(ch.get("path", ""))
        if kind == "guarded" and rec["status"] == "done":
            problems.append(
                "改动 %s 属受保护路径：worker 只能在 worktree 内改，"
                "共享树写回必须另开合并任务并持 GATE.lock" % ch.get("path")
            )
    if not rec.get("assertions"):
        problems.append("assertions 为空：至少写一条「我如何验证」")
    if rec["status"] == "done" and not rec.get("sourceHashes"):
        problems.append("sourceHashes 为空：done 必须记录动手前后源文件哈希（用于识别并行写入）")
    return problems


def cmd_submit(args):
    rec = load_json(Path(args.file))
    if not rec:
        print("无法解析提交文件：%s" % args.file, file=sys.stderr)
        return 2
    tid = rec.get("task")
    if not tid:
        print("提交缺 task 字段", file=sys.stderr)
        return 2
    task = load_tasks().get(tid, {})
    rec.setdefault("agent", args.agent)
    if rec.get("reworkOf") and not rec.get("reworkReason"):
        rec["reworkReasonNote"] = ("声明了 reworkOf 却没写 reworkReason —— "
                                   "计划要求记录返工原因，缺失会让工期外推失真")
    if not rec.get("assertions"):
        rec["assertions"] = [{"text": "（worker 未写明验证方式）", "result": "unknown"}]
    problems = validate(rec)
    problems = problems + validate_sections(rec, task)
    rec["submittedAt"] = now()
    if "wallClockSeconds" not in rec:
        _lease = load_json(lease_dir(tid) / "lease.json", {}) or {}
        _start = _lease.get("startedAt")
        if _start:
            try:
                _fmt = "%Y-%m-%dT%H:%M:%SZ"
                _a = datetime.strptime(_start, _fmt)
                _b = datetime.strptime(rec["submittedAt"], _fmt)
                rec["wallClockSeconds"] = int((_b - _a).total_seconds())
                rec["wallClockFrom"] = "lease.startedAt"
            except Exception as exc:
                rec["wallClockNote"] = "无法计算：%r" % (exc,)
        else:
            rec["wallClockNote"] = ("租约里没有 startedAt（任务可能由非 loop 路径提交，"
                                    "或租约已被回收）—— 留空而不估算")
    rec["validation"] = {"problems": problems, "at": now()}
    if problems:
        rec["status"] = "rejected" if rec.get("status") == "done" else rec.get("status", "rejected")
        path = OUT / ("REJECTED__" + output_name(tid))
        write_json_atomic(path, rec)
        for p in problems:
            print("[拒绝] %s" % p, file=sys.stderr)
        return 1
    rec["status"] = "done"
    if task.get("verifierRequired", True):
        rec["verifyState"] = "pending"
    write_json_atomic(OUT / output_name(tid), rec)
    cmd_release(argparse.Namespace(task=tid, agent=args.agent, force=False))
    print("已接收：%s" % tid)
    return 0


def cmd_verify(args):
    """独立复核提交：复核者不能是原 worker（自签不算复核）。"""
    path = OUT / output_name(args.task)
    rec = load_json(path)
    if not rec:
        print("找不到已提交记录：%s" % args.task, file=sys.stderr)
        return 2
    if rec.get("agent") == args.agent:
        print("拒绝自签：%s 是原提交者" % args.agent, file=sys.stderr)
        return 2
    verdict = load_json(Path(args.file))
    if not verdict or "verdict" not in verdict:
        print("复核文件需含 verdict 字段（pass/fail/partial）", file=sys.stderr)
        return 2
    task = load_tasks().get(args.task, {})
    section_problems = validate_sections(rec, task)
    if section_problems and verdict["verdict"] == "pass":
        verdict = dict(verdict)
        verdict["verdict"] = "partial"
        verdict["downgradedFrom"] = "pass"
        verdict["downgradedReason"] = "；".join(section_problems)
        print("[复核降级] pass → partial：%s" % "；".join(section_problems), file=sys.stderr)
    rec.setdefault("reviews", []).append(
        {"reviewer": args.agent, "at": now(), "verdict": verdict["verdict"],
         "notes": verdict.get("notes", ""), "counterExamples": verdict.get("counterExamples", []),
         "reverseChecks": verdict.get("reverseChecks", [])}
    )
    rec["verifyState"] = verdict["verdict"]
    if verdict["verdict"] == "fail":
        rec["status"] = "rejected"
    write_json_atomic(path, rec)
    print("复核已记录：%s → %s" % (args.task, verdict["verdict"]))
    return 0


def cmd_runlog(args):
    RUNS.mkdir(parents=True, exist_ok=True)
    line = {"at": now(), "agent": args.agent}
    if args.line:
        line["text"] = args.line
    if args.json:
        try:
            line.update(json.loads(args.json))
        except Exception:
            line["jsonError"] = args.json
    with (RUNS / (datetime.now().strftime("%Y%m%d") + ".jsonl")).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return 0


def open_rejections(done: dict = None, tasks: dict = None) -> list:
    """**当前仍然成立**的拒绝：任务至今没有通过校验的最终记录。

    真实事故（2026-10-08）：`REJECTED__*.json` 只在 `submit` 失败时写入，
    任务后来重做成功时**既不删除也不被计数排除**。实测 33 个拒绝文件里
    28 个的任务早已 `done`（例：`read:dafeng:L0:0040` 10:49 被拒、11:22 成功），
    看板与守护轮却一直报 33 —— 真实积压只有 5 条。
    判据：任务已在 `done_ids()` 里，或已有过校验的规范记录 ⇒ 旧失败已被取代。
    """
    if done is None:
        done = done_ids()
    if tasks is None:
        tasks = load_tasks()
    out = []
    for path in sorted(OUT.glob("REJECTED__*.json")):
        rec = load_json(path, {}) or {}
        tid = rec.get("task")
        if tid and tid in done:
            continue
        if tid and tid not in tasks:
            continue
        out.append({"task": tid, "file": path.name,
                    "summary": rec.get("summary", ""),
                    "infraFailure": rec.get("infraFailure") or None,
                    "problems": (rec.get("validation") or {}).get("problems") or [],
                    "at": rec.get("submittedAt")})
    return out


def cmd_stats(args):
    tasks = load_tasks()
    done = done_ids()
    leases = active_leases()
    per_stream = {}
    for t in tasks.values():
        per_stream.setdefault(t.get("stream", "?"), [0, 0])
        per_stream[t["stream"]][0] += 1
        if t["id"] in done:
            per_stream[t["stream"]][1] += 1
    open_rej = open_rejections(done=done, tasks=tasks)
    rejected = len(open_rej)
    pending_verify = sum(1 for r in done.values() if r.get("verifyState") == "pending")
    unvalidated = unvalidated_ids()
    all_valid = validated_records()
    stale_all = sorted(r.get("task") for r in all_valid if evidence_stale(r))
    stale_in_done = sorted(t for t, r in done.items() if evidence_stale(r))
    weak = sorted(({"task": r.get("task"), "paths": [w["path"] for w in weak_evidence(r)]}
                   for r in all_valid if weak_evidence(r)),
                  key=lambda x: x["task"] or "")
    pub = publish_state(done=done, tasks=tasks)
    report = {
        "at": now(),
        "tasks": len(tasks),
        "done": len(done),
        "unvalidated": unvalidated,
        "unvalidatedCount": len(unvalidated),
        "staleEvidence": stale_all,
        "staleEvidenceCount": len(stale_all),
        "staleEvidenceNote": ("在**全部校验通过记录**上重新扫描（DEL-05 修复）；"
                              "旧口径从 done 反查，结构性恒为 0。"),
        "staleEvidenceStillInDone": stale_in_done,
        "weakEvidence": weak[:20],
        "weakEvidenceCount": len(weak),
        "weakEvidenceNote": ("证据**不可校验**（条目没声明 sha256 ⇒ 时效检查对它不生效）。"
                             "新提交已被 validate() 直接拒绝；这些是**存量**，只报不追溯判死 ——"
                             "把历史宽松口径记成今天集中失败是 E15/E30 的错误。"),
        "rejected": rejected,
        "rejectedOpen": open_rej[:20],
        "rejectedOpenCount": rejected,
        "rejectedContentOnly": [r for r in open_rej if not r.get("infraFailure")],
        "rejectedContentCount": sum(1 for r in open_rej if not r.get("infraFailure")),
        "rejectedInfraCount": sum(1 for r in open_rej if r.get("infraFailure")),
        "rejectedSplitNote": ("rejectedOpenCount 含两类：真正做不出产物（rejectedContentCount）"
                             "与**根本没跑起来**（rejectedInfraCount，账号/网络/环境）。"
                             "只有前者才是「任务失败」；后者是环境故障（E31/E35 同形）。"),
        "pendingVerify": pending_verify,
        "activeLeases": {k: v.get("agent") for k, v in leases.items()},
        "gateLock": GATE_LOCK.exists(),
        "perStream": {k: {"tasks": v[0], "done": v[1]} for k, v in per_stream.items()},
        "publish": pub,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _gate_is_dead(info: dict) -> bool:
    """GATE.lock 的持有者是否**确已死亡**（同宿主且 pid 消失）。False = 无法判定或仍活着。

    真实缺陷（E34，2026-10-10 00:19 实测，直接卡住 `publish:sanguo:B000`）：
      `GATE.lock` 的回收**只有 TTL 一条判据**（90 分钟），而任务租约早就改成了
      「同宿主 + pid 确已消失 ⇒ 立即回收」（E8 的修复）。于是 agent 在持锁期间因
      **基础设施失败**退出（这次是 `dsh: SERVER: Error: Client network socket disconnected`），
      锁没人释放、也没有 pid 可判死 ⇒ 该任务**自己把自己挡住 90 分钟**。
      实测 `pick(w-publish)` 连续返回「没有可领取的任务（正被占用）」，
      而唯一占用者就是它自己上一轮的残留锁。**判据比现实弱一档**。

    修法两半：① `gate` 记下 host/pid；② 回收用与任务租约**同一套**判死逻辑。
    """
    if not info:
        return False
    if info.get("host") != socket.gethostname() or not info.get("pid"):
        return False
    return not _pid_alive(info["pid"])


def cmd_gatelock(args):
    if args.release:
        GATE_LOCK.unlink(missing_ok=True)
        print("GATE.lock 已释放")
        return 0
    if getattr(args, "renew", False):
        info = load_json(GATE_LOCK, {}) or {}
        if not info:
            print("GATE.lock 不存在，无法续期；请用 --agent 重新取得")
            return 1
        if info.get("agent") != args.agent:
            print("GATE.lock 属于 %s，不能由 %s 续期" % (info.get("agent"), args.agent))
            return 1
        info["heartbeatAt"] = now()
        info.setdefault("host", socket.gethostname())
        info.setdefault("pid", os.getpid())
        write_json_atomic(GATE_LOCK, info)
        print("GATE.lock 已续期（agent=%s）" % args.agent)
        return 0
    cur = load_json(GATE_LOCK, {}) or {}
    if gate_held():
        print("GATE.lock 被占用：%s" % json.dumps(cur, ensure_ascii=False))
        return 1
    if GATE_LOCK.exists() and _gate_is_dead(cur):
        print("[note] GATE.lock 持有者（pid %s）已消失，接管" % cur.get("pid"))
    write_json_atomic(GATE_LOCK, {"agent": args.agent, "reason": args.reason or "",
                                  "host": socket.gethostname(), "pid": os.getpid(),
                                  "startedAt": now(), "heartbeatAt": now()})
    ttl = policy().get("gateLockTtlSeconds", 5400)
    print("GATE.lock 已取得（共享树写入/重门禁串行）；TTL %ds，超时前可用 `gate --agent %s --renew` 续期" % (ttl, args.agent))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Castline 持续运行环境")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("next"); p.add_argument("--agent", required=True); p.add_argument("--stream", help="限定流，如 read / read-verify / ops / publish"); p.add_argument("--claim", action="store_true"); p.add_argument("--strict", action="store_true"); p.set_defaults(fn=cmd_next)
    p = sub.add_parser("claim"); p.add_argument("--task", required=True); p.add_argument("--agent", required=True); p.set_defaults(fn=cmd_claim)
    p = sub.add_parser("beat"); p.add_argument("--task", required=True); p.add_argument("--agent", required=True); p.add_argument("--note"); p.set_defaults(fn=cmd_beat)
    p = sub.add_parser("release"); p.add_argument("--task", required=True); p.add_argument("--agent", default=""); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_release)
    p = sub.add_parser("reap"); p.set_defaults(fn=cmd_reap)
    p = sub.add_parser("submit"); p.add_argument("--file", required=True); p.add_argument("--agent", required=True); p.set_defaults(fn=cmd_submit)
    p = sub.add_parser("verify"); p.add_argument("--task", required=True); p.add_argument("--file", required=True); p.add_argument("--agent", required=True); p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("runlog"); p.add_argument("--agent", required=True); p.add_argument("--line"); p.add_argument("--json"); p.set_defaults(fn=cmd_runlog)
    p = sub.add_parser("stats"); p.set_defaults(fn=cmd_stats)
    p = sub.add_parser("gate"); p.add_argument("--agent", required=True); p.add_argument("--reason"); p.add_argument("--release", action="store_true"); p.add_argument("--renew", action="store_true", help="续期（长工作段在 TTL 到期前调用）"); p.set_defaults(fn=cmd_gatelock)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
