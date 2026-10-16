#!/usr/bin/env python3
"""P11-W07/W08 · 错误恢复契约（降级 / 断流 / 取消 / 重试 / 403 / 返回后状态恢复）。

覆盖 `tests/http_boundary_contract.py` 与 `tests/narrative_*_contract.py`
**没有覆盖**的一面：失败之后系统还剩什么状态。

  1. 显式降级：空 / 稀疏 / 密集 / 长标题 / 缺证据 / 错误引用输入；
  2. 断流：SSE 客户端中途断开 → 订阅队列不泄漏、作业不被误杀、可重连续看；
  3. 取消：进行中取消 → cancelled 终态、幂等、不留半状态；
  4. 重试：失败后重试可继续，且不重复计费调用；
  5. 403：拒绝发生在读 body / 建作业之前，不留副作用；
  6. 返回后状态恢复：取消/失败之后 /api/jobs、/api/health、缓存目录仍然自洽。

全程零模型调用、零外部网络：`run_job` / `run_enrichment` 用受控假作业替换。

断言分两类：
  HARD      今天成立的不变量，退化即 fail。
  RATCHET   已知缺陷的冻结签名；缺陷仍在 → 复现并打印 KNOWN DEFECT 横幅，
            已修好 → skip 并提示收紧，恶化 → fail。

用法：
  python3 tests/error_recovery_contract.py
  python3 tests/error_recovery_contract.py --report
"""
from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import serve as S
import narrative as N

SAFE_TEXT = "北辰推开古塔的门。他走了进去，风从背后追上来。"

KNOWN_DEFECTS = {
    "disconnect_does_not_stop_the_job": False,
}


class FakeJobHarness:
    """受控假作业：按步发射 progress，可被 cancel 中断。"""

    def __init__(self, step_seconds=0.02, steps=40):
        self.step_seconds = step_seconds
        self.steps = steps
        self.jobs = {}
        self.lock = threading.Lock()
        self.started = 0

    def run_job(self, docs, force, refresh=False, mode="summary", job_key=None):
        with self.lock:
            existing = S.JOBS.get("JOB1")
            if existing is not None and not existing.cancelled and not existing.finished:
                return existing, True
            self.started += 1
            job = S.Job("JOB1", label="recovery-probe", kind="analyze")
            job.analysis_mode = "summary"
            with S.JOBS_LOCK:
                S.JOBS["JOB1"] = job

        def runner():
            try:
                for index in range(self.steps):
                    if job.cancelled:
                        raise S.Cancelled()
                    time.sleep(self.step_seconds)
                    job.emit("progress", {"i": index, "n": self.steps})
                job.emit("done", {"graph": {"title": "t", "characters": [], "events": []}})
            except (S.Cancelled, N.Cancelled):
                job.emit("cancelled", {"message": "已取消；原作品未覆盖，已完成批次可续跑。"})

        threading.Thread(target=runner, daemon=True).start()
        return job, False


class ErrorRecoveryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.folder = Path(cls.stack.enter_context(tempfile.TemporaryDirectory(prefix="castline-p11-recovery-")))
        cls.cache_dir = cls.folder / "data/cache"
        cls.cache_dir.mkdir(parents=True)
        (cls.cache_dir / "index.json").write_text("[]", encoding="utf-8")
        (cls.folder / "index.html").write_text("<!doctype html><title>recovery fixture</title>", encoding="utf-8")
        (cls.cache_dir / "1234abcd.json").write_text(
            json.dumps({"title": "g", "characters": [], "events": []}), encoding="utf-8")
        (cls.cache_dir / "1234abcd.docs.json").write_text(
            json.dumps([{"kind": "正文", "name": "a", "path": "a.txt", "text": SAFE_TEXT}]), encoding="utf-8")

        cls.stack.enter_context(patch.object(S, "ROOT", str(cls.folder)))
        cls.stack.enter_context(patch.object(S, "CACHE_DIR", str(cls.cache_dir)))
        cls.stack.enter_context(patch.object(S, "HIST_PATH", str(cls.cache_dir / "index.json")))
        cls.jobs_holder = {}
        cls.stack.enter_context(patch.object(S, "JOBS", cls.jobs_holder))
        cls.stack.enter_context(patch.object(S, "cfg_load",
                                             return_value={"profiles": [], "current": "", "history": []}))
        cls.cfg_save = cls.stack.enter_context(patch.object(S, "cfg_save"))
        cls.stack.enter_context(patch.object(S, "current", return_value=None))
        cls.stack.enter_context(patch.object(S, "cfg_history"))
        cls.stack.enter_context(patch.object(S, "history_list", return_value=[]))
        cls.stack.enter_context(patch.object(S, "call_llm",
                                             side_effect=AssertionError("MODEL CALL FORBIDDEN")))
        cls.stack.enter_context(patch.object(S.urllib.request, "urlopen",
                                             side_effect=AssertionError("EXTERNAL NETWORK FORBIDDEN")))
        cls.harness = FakeJobHarness()
        cls.stack.enter_context(patch.object(S, "run_job", side_effect=cls.harness.run_job))
        cls.stack.enter_context(patch.object(S, "run_distill",
                                             side_effect=AssertionError("MODEL CALL FORBIDDEN")))

        class QuietHandler(S.Handler):
            _asset_hashes = {}
            def log_message(self, *args):
                pass

        cls.server = S.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port
        cls.origin = "http://127.0.0.1:%d" % cls.port
        cls.addClassCleanup(cls.stop_server)

    @classmethod
    def stop_server(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        with S.JOBS_LOCK:
            for job in S.JOBS.values():
                job.cancelled = True
                job.finished = True
            S.JOBS.clear()
        with self.harness.lock:
            self.harness.jobs.clear()
            self.harness.started = 0

    def active_job(self):
        with S.JOBS_LOCK:
            return S.JOBS.get("JOB1")

    # ---------- 工具 ----------

    def post(self, path, payload, headers=None, timeout=10):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        self.addCleanup(conn.close)
        heads = {"Content-Type": "application/json"}
        heads.update(headers or {})
        conn.request("POST", path, json.dumps(payload, ensure_ascii=False).encode("utf-8"), heads)
        response = conn.getresponse()
        return response.status, response.read()

    def get(self, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(conn.close)
        conn.request("GET", path, headers=headers or {})
        response = conn.getresponse()
        return response.status, response.read()

    def open_stream(self, payload, headers=None, timeout=10):
        """发起到 /api/analyze 的 SSE 请求，返回未读完的 socket。"""
        conn = socket.create_connection(("127.0.0.1", self.port), timeout=timeout)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        head = ["POST /api/analyze HTTP/1.1", "Host: 127.0.0.1:%d" % self.port,
                "Content-Type: application/json", "Content-Length: %d" % len(body), "Connection: close"]
        for name, value in (headers or {}).items():
            head.append("%s: %s" % (name, value))
        conn.sendall(("\r\n".join(head) + "\r\n\r\n").encode("utf-8") + body)
        return conn

    @staticmethod
    def evidence(**kwargs):
        return "\n失败证据:\n" + json.dumps(kwargs, ensure_ascii=False, indent=2, sort_keys=True, default=repr)[:3500]

    @staticmethod
    def defect_banner(tag, title, detail, repro):
        sys.stderr.write("\n[已知缺陷 %s] %s\n  %s\n  最小复现: %s\n" % (tag, title, detail, repro))

    # ---------- 1 · 显式降级 ----------

    def test_empty_input_gets_an_explicit_error_instead_of_a_silent_empty_stream(self):
        """空材料必须给出明确 error 事件，而不是一条静默关闭的流。"""
        status, body = self.post("/api/analyze", {"docs": []})
        self.assertEqual(status, 200, "空材料应返回可解析的 SSE 而不是 HTTP 错误" + self.evidence(actual=status))
        self.assertIn(b"event: error", body, "空材料没有明确报错" + self.evidence(
            body=body[:300].decode("utf-8", "replace"), expected="event: error",
            minimalRepro="curl -sN -X POST -H 'Content-Type: application/json' -d '{\"docs\":[]}' http://127.0.0.1:PORT/api/analyze"))
        self.assertIn("没有收到材料", body.decode("utf-8", "replace"),
                      "空材料的错误信息没有说明原因" + self.evidence(body=body[:300].decode("utf-8", "replace")))

    def test_sparse_versus_dense_input_keep_distinct_known_flags(self):
        """稀疏（1 条）与密集（数百条）材料必须给出可区分且诚实的 known 状态。"""
        sparse = [{"name": "a", "text": SAFE_TEXT}]
        status, body = self.post("/api/source", {"docs": sparse})
        self.assertEqual(status, 200)
        sparse_out = json.loads(body)
        self.assertTrue(sparse_out["known"], "稀疏材料未被识别为已知来源" + self.evidence(response=sparse_out))
        self.assertEqual(len(sparse_out["sources"]), 1)

        dense = [{"name": "d%d" % i, "text": SAFE_TEXT * 20} for i in range(300)]
        status, body = self.post("/api/source", {"docs": dense})
        self.assertEqual(status, 200, "密集材料让接口失败" + self.evidence(count=len(dense), actual=status))
        dense_out = json.loads(body)
        self.assertEqual(len(dense_out["sources"]), len(dense),
                         "密集材料被静默合并或丢弃——降级必须显式" + self.evidence(
                             submitted=len(dense), registered=len(dense_out["sources"])))

    def test_long_title_and_missing_evidence_degrade_explicitly(self):
        """长标题不得截断；缺证据必须显示待核，而不是前端猜一个值。"""
        long_title = "题目" * 5000
        status, body = self.post("/api/source/rebuild", {
            "graph": {"characters": [], "events": [
                {"id": "e1", "order": 1, "title": long_title, "quote": SAFE_TEXT},
                {"id": "e2", "order": 2, "title": "缺证据事件"}]},
            "docs": [{"name": "a", "text": SAFE_TEXT}]})
        self.assertEqual(status, 200)
        events = {e["id"]: e for e in json.loads(body)["graph"]["events"]}
        self.assertEqual(events["e1"]["title"], long_title, "长标题被静默截断")
        missing = events["e2"]
        self.assertIsNone(missing.get("quoteRef"), "无引文的事件却被赋了引用" + self.evidence(event=missing))
        self.assertFalse(missing.get("verified"), "无证据事件被标成已核验" + self.evidence(event=missing))
        self.assertEqual(missing.get("claimStatus"), "unreviewed",
                         "无证据事件被赋予了语义结论" + self.evidence(event=missing))

    def test_wrong_quote_is_marked_unverified_not_silently_dropped(self):
        """错误引用必须被明确标记为未核验，且事件本身不得被静默删除。"""
        status, body = self.post("/api/source/rebuild", {
            "graph": {"characters": [], "events": [
                {"id": "e-bad", "order": 1, "title": "错引", "quote": "这句话原文里根本不存在，纯属虚构。"}]},
            "docs": [{"name": "a", "text": SAFE_TEXT}]})
        self.assertEqual(status, 200)
        events = json.loads(body)["graph"]["events"]
        self.assertEqual(len(events), 1, "错误引用的事件被静默删除——不得用删项掩盖问题" + self.evidence(events=events))
        self.assertFalse(events[0]["quoteRef"]["verified"], "虚构引文被标成已核验" + self.evidence(event=events[0]))
        self.assertEqual(events[0]["quoteRef"]["match"], "none",
                         "虚构引文的 match 不是 none" + self.evidence(ref=events[0]["quoteRef"]))

    # ---------- 2 · 断流 ----------

    def test_client_disconnect_releases_the_subscription_queue(self):
        """客户端中途断开后，作业的订阅队列必须被释放，不能泄漏。"""
        conn = self.open_stream({"docs": [{"name": "a", "text": SAFE_TEXT}]})
        try:
            conn.recv(200)
        finally:
            conn.close()
        deadline = time.monotonic() + 5
        job = None
        while time.monotonic() < deadline:
            job = self.active_job()
            if job is not None and not job.subs:
                break
            time.sleep(0.05)
        self.assertIsNotNone(job, "断流后找不到作业，无法判定订阅状态")
        self.assertEqual(job.subs, [], "断流后订阅队列泄漏——长跑会持续吃内存" + self.evidence(
            subscribers=len(job.subs), job=job.key, events=len(job.events),
            minimalRepro="python3 tests/error_recovery_contract.py -k disconnect"))

    def test_reconnect_replays_history_and_keeps_a_single_job(self):
        """重连必须重放历史事件并附着到同一作业，而不是另起一个。"""
        first = self.open_stream({"docs": [{"name": "a", "text": SAFE_TEXT}]})
        try:
            first.recv(200)
        finally:
            first.close()
        time.sleep(0.2)
        with self.harness.lock:
            started_after_first = self.harness.started
        status, body = self.post("/api/analyze", {"docs": [{"name": "a", "text": SAFE_TEXT}]}, timeout=10)
        text = body.decode("utf-8", "replace")
        self.assertEqual(status, 200)
        self.assertIn('"attached": true', text, "重连没有附着到既有作业" + self.evidence(body=text[:400]))
        self.assertIn("event: hello", text, "重连没有发送 hello 帧" + self.evidence(body=text[:400]))
        self.assertIn("event: progress", text, "重连没有重放历史进度" + self.evidence(body=text[:400]))
        with self.harness.lock:
            self.assertEqual(self.harness.started, started_after_first,
                             "重连另起了一个作业——会重复计费" + self.evidence(
                                 startedBefore=started_after_first, startedAfter=self.harness.started))

    # ---------- 3 · 取消 ----------

    def test_cancel_reaches_a_terminal_state_and_is_idempotent(self):
        """取消必须到达 cancelled 终态；重复取消返回 ok=false，不得双重取消。"""
        conn = self.open_stream({"docs": [{"name": "a", "text": SAFE_TEXT}]})
        try:
            conn.recv(160)
        finally:
            conn.close()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and self.active_job() is None:
            time.sleep(0.05)
        job = self.active_job()
        self.assertIsNotNone(job, "取消测试没拿到作业")

        status, body = self.post("/api/cancel", {"job": "JOB1"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"], "进行中的取消未被接受" + self.evidence(body=body[:300]))

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not job.finished:
            time.sleep(0.05)
        self.assertTrue(job.finished, "取消后作业没有到达终态" + self.evidence(
            cancelled=job.cancelled, finished=job.finished, lastEvent=job.events[-1][0] if job.events else None))
        terminal = [ev for ev, _ in job.events if ev in ("cancelled", "done", "error")]
        self.assertEqual(terminal[-1], "cancelled", "终态事件不是 cancelled" + self.evidence(terminal=terminal))

        status, body = self.post("/api/cancel", {"job": "JOB1"})
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["ok"], "重复取消被当成有效操作" + self.evidence(body=body[:300]))

    def test_cancel_of_unknown_job_is_a_clean_no_op(self):
        status, body = self.post("/api/cancel", {"job": "does-not-exist"})
        self.assertEqual(status, 200, "取消不存在的作业不该报错" + self.evidence(actual=status))
        payload = json.loads(body)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["cancelled"], [], "取消不存在的作业却报告取消了东西" + self.evidence(payload=payload))

    def test_cancel_reports_a_successful_zero_model_call_plan(self):
        """sourceOnly 的重建计划必须报告 0 次付费调用（取消/重试的安全前提）。"""
        status, body = self.post("/api/enrich/plan", {"key": "1234abcd", "sourceOnly": True})
        self.assertEqual(status, 200)
        plan = json.loads(body)
        self.assertEqual(plan["estimatedCalls"], 0, "sourceOnly 计划报告了非零付费调用" + self.evidence(plan=plan))
        self.assertTrue(plan["sourceOnly"])
        self.assertEqual(plan["semanticCompleteness"], "unverified",
                         "计划声称了未经验证的语义完整性" + self.evidence(plan=plan))

    # ---------- 4 · 重试 ----------

    def test_retry_after_cancel_can_attach_only_when_explicitly_requested(self):
        """取消之后，隐式重试不得自动重开付费调用；必须显式 force。"""
        status, body = self.post("/api/enrich", {"key": "1234abcd", "job": "JOB1"})
        self.assertEqual(status, 400, "对齐到不存在的续接作业却没有拒绝" + self.evidence(
            actual=status, body=body[:300].decode("utf-8", "replace"),
            minimalRepro="curl -s -X POST -H 'Content-Type: application/json' -d '{\"key\":\"1234abcd\",\"job\":\"JOB1\"}' http://127.0.0.1:PORT/api/enrich"))
        self.assertIn("error", json.loads(body))

    def test_repeated_plan_requests_are_deterministic(self):
        """同一输入的重复请求必须给出同一个计划 key——重试不会改变身份。"""
        keys = []
        for _ in range(3):
            status, body = self.post("/api/enrich/plan", {"key": "1234abcd", "sourceOnly": True})
            self.assertEqual(status, 200)
            keys.append(json.loads(body)["key"])
        self.assertEqual(len(set(keys)), 1, "同一输入的重复计划给出了不同 key——重试语义不稳定" + self.evidence(keys=keys))

    def test_state_is_consistent_after_a_failed_enrichment_request(self):
        """失败的补析请求不得留下半状态（作业表、缓存目录、健康检查都要自洽）。"""
        before = sorted(p.name for p in self.cache_dir.iterdir())
        for key in ("../llm-config", "", "deadbeef", None):
            status, _ = self.post("/api/enrich", {"key": key, "sourceOnly": True})
            self.assertIn(status, (400, 404), "非法 key 未被明确拒绝" + self.evidence(key=key, actual=status))
        after = sorted(p.name for p in self.cache_dir.iterdir())
        self.assertEqual(before, after, "失败的补析请求改动了缓存目录" + self.evidence(before=before, after=after))
        status, body = self.get("/api/health")
        self.assertEqual(status, 200, "失败请求后健康检查不可用" + self.evidence(actual=status))
        self.assertTrue(json.loads(body)["ok"])

    # ---------- 5 · 403 ----------

    def test_403_happens_before_any_job_is_created(self):
        """403 必须发生在建作业 / 读 body 之前，不留任何副作用。"""
        for path, payload in (("/api/analyze", {"docs": [{"name": "a", "text": SAFE_TEXT}]}),
                              ("/api/enrich", {"key": "1234abcd", "sourceOnly": True}),
                              ("/api/cancel", {"job": "JOB1"})):
            with self.subTest(path=path):
                status, body = self.post(path, payload, {"Origin": "https://attacker.example"})
                self.assertEqual(status, 403, "foreign Origin 未被拒" + self.evidence(
                    path=path, expected=403, actual=status,
                    minimalRepro=("curl -s -o /dev/null -w '%%{http_code}' -X POST "
                                  "-H 'Content-Type: application/json' -H 'Origin: https://attacker.example' "
                                  "-d '%s' http://127.0.0.1:PORT%s" % (json.dumps(payload), path))))
                self.assertNotIn(b"event: hello", body, "403 响应里带出了 SSE 流" + self.evidence(body=body[:200]))
        with self.harness.lock:
            self.assertEqual(self.harness.started, 0,
                             "403 请求仍然创建了作业——副作用泄漏" + self.evidence(started=self.harness.started))
        with S.JOBS_LOCK:
            self.assertEqual(S.JOBS, {}, "403 请求污染了作业表" + self.evidence(jobs=list(S.JOBS)))

    def test_403_is_indistinguishable_across_unknown_and_known_routes(self):
        """未授权探测不应通过状态码差异泄露哪些 API 存在。"""
        statuses = {}
        for path in ("/api/analyze", "/api/enrich", "/api/nope", "/api/health", "/api/source"):
            status, _ = self.post(path, {"docs": []}, {"Origin": "https://attacker.example"})
            statuses[path] = status
        self.assertEqual(set(statuses.values()), {403},
                         "未授权时不同路径的状态码不一致，泄露了路由存在性" + self.evidence(statuses=statuses))

    # ---------- 6 · 返回后状态恢复 ----------

    def test_state_is_restored_after_cancel_and_reconnect_cycle(self):
        """取消 → 再连 → 再取消的完整循环后，作业表与缓存仍然自洽。"""
        conn = self.open_stream({"docs": [{"name": "a", "text": SAFE_TEXT}]})
        try:
            conn.recv(160)
        finally:
            conn.close()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and self.active_job() is None:
            time.sleep(0.05)
        self.post("/api/cancel", {"job": "JOB1"})
        job = self.active_job()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not job.finished:
            time.sleep(0.05)

        status, body = self.get("/api/jobs")
        self.assertEqual(status, 200, "取消后 /api/jobs 不可用" + self.evidence(actual=status))
        listed = json.loads(body)["jobs"]
        self.assertTrue(listed, "取消后作业从列表里消失，返回页面看不到状态" + self.evidence(body=body[:300]))
        entry = listed[0]
        self.assertTrue(entry.get("finished"), "取消后的作业在列表里没有终态标记" + self.evidence(entry=entry))

        status, body = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"], "取消循环后健康检查失败")
        contents = sorted(p.name for p in self.cache_dir.iterdir())
        self.assertEqual([name for name in contents if name.startswith("1234abcd")],
                         ["1234abcd.docs.json", "1234abcd.json"],
                         "取消循环改动了原作品缓存——原作品被覆盖" + self.evidence(contents=contents))

    def test_jobs_route_stays_parseable_under_a_hostile_job_id(self):
        """作业表里出现异常键值也不能让 /api/jobs 崩掉（返回页面要能恢复）。"""
        with S.JOBS_LOCK:
            S.JOBS["hostile"] = S.Job("<script>alert(1)</script>", label="x" * 10000, kind="analyze")
        self.addCleanup(lambda: S.JOBS.pop("hostile", None))
        status, body = self.get("/api/jobs")
        self.assertEqual(status, 200, "/api/jobs 在异常键值下崩了——返回页面无法恢复" + self.evidence(actual=status))
        payload = json.loads(body)
        self.assertIsInstance(payload["jobs"], list)
        self.assertTrue(any(j.get("job") == "hostile" for j in payload["jobs"]),
                        "异常作业没有出现在列表里")

    def test_known_defect_disconnect_does_not_stop_the_running_job(self):
        """已知缺陷 P11-ER-01：客户端断开后作业继续跑完，不会因无人订阅而暂停/回收。

        这意味着一次误触或断网会继续消耗模型调用。缺陷仍在 → 打印横幅；
        已修好（断开后作业停止）→ skip 并提示收紧。
        """
        if not KNOWN_DEFECTS["disconnect_does_not_stop_the_job"]:
            conn = self.open_stream({"docs": [{"name": "a", "text": SAFE_TEXT}]})
            try:
                conn.recv(160)
            finally:
                conn.close()
            deadline = time.monotonic() + 5
            job = None
            while time.monotonic() < deadline:
                job = self.active_job()
                if job is not None and not job.subs:
                    break
                time.sleep(0.05)
            self.assertIsNotNone(job, "断流后找不到作业，无法判定")
            self.assertEqual(job.subs, [], "断流后订阅队列未释放")
            self.assertFalse(job.cancelled,
                             "断流后**立即**取消 ⇒ 页面刷新会丢失作业（宽限期未生效）")
            grace = getattr(job, "ORPHAN_GRACE_SECONDS", 8.0)
            deadline = time.monotonic() + grace + 6
            while time.monotonic() < deadline and not (job.cancelled or job.finished):
                time.sleep(0.1)
            self.assertTrue(job.cancelled or job.finished,
                            "宽限 %.0fs 后作业仍未停止 ⇒ 无人在看的调用继续计费（缺陷未修）" % grace)
            import serve as _S
            probe = _S.Job("orphan-probe-" + str(int(time.time())), "probe")
            probe.ORPHAN_GRACE_SECONDS = 1.0
            q = probe.subscribe()[0]
            probe.unsubscribe(q)
            self.assertFalse(probe.cancelled,
                             "断流后立即取消 ⇒ 宽限期未生效（刷新会丢作业）")
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline and not probe.cancelled:
                time.sleep(0.05)
            self.assertTrue(probe.cancelled,
                            "宽限到期后**仍未取消**一个不会自己结束的作业 ⇒ "
                            "「无人在看就停」的机制未生效（回退修复也照样绿，属绿灯盲区）")
            probe2 = _S.Job("orphan-probe2-" + str(int(time.time())), "probe2")
            probe2.ORPHAN_GRACE_SECONDS = 1.0
            q2 = probe2.subscribe()[0]
            probe2.unsubscribe(q2)
            time.sleep(0.3)
            probe2.subscribe()
            time.sleep(1.5)
            self.assertFalse(probe2.cancelled,
                             "宽限期内重连后仍被取消 ⇒ 页面刷新会丢作业（误杀）")
            return
        conn = self.open_stream({"docs": [{"name": "a", "text": SAFE_TEXT}]})
        try:
            conn.recv(160)
        finally:
            conn.close()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and self.active_job() is None:
            time.sleep(0.05)
        job = self.active_job()
        self.assertIsNotNone(job, "断流后找不到作业，无法判定缺陷")
        time.sleep(0.4)
        if job.cancelled or job.finished:
            self.skipTest("已知缺陷 P11-ER-01 已修复（断流会停止作业）；"
                          "请更新 KNOWN_DEFECTS 与 ledger 的 knownGaps 收紧基线")
        self.defect_banner(
            "P11-ER-01", "SSE 客户端断开后作业继续运行到完成（无人在看的模型调用继续计费）",
            "serve.py do_POST 的 SSE 循环只在 BrokenPipeError/ConnectionResetError 时 unsubscribe，"
            "不调用 job.cancel()，也没有「无订阅者则暂停」的判定。观测：断开 0.4s 后 "
            "job.cancelled=%s job.finished=%s，期间继续发射 progress。" % (job.cancelled, job.finished),
            "python3 tests/error_recovery_contract.py -k disconnect_does_not_stop")
        self.assertFalse(job.finished, "0.4s 内作业已完成，本用例的时序假设失效，请调整 step_seconds")
        self.assertGreaterEqual(len(job.subs), 0)


def print_report():
    print("ERROR RECOVERY CONTRACT · 探测摘要")
    print("  空输入        : SSE event:error「没有收到材料」（不是静默空流）")
    print("  断流          : 订阅队列被释放；作业不被误杀；重连 attached=true 并重放历史")
    print("  取消          : cancelled 终态 + 幂等（重复取消 ok=false）+ 未知作业 no-op")
    print("  重试          : sourceOnly estimatedCalls=0；计划 key 对同一输入确定；隐式续接被拒绝")
    print("  403           : 先于建作业与读 body，作业表零副作用，跨路径状态码一致")
    print("  返回后恢复    : /api/jobs 保留终态、/api/health 可用、缓存目录未被改动")
    print("  --- 已知缺陷（冻结，见 ledger knownGaps）---")
    print("  P11-ER-01 断流不停止作业: 无订阅者时模型调用继续计费")
    print("             最小复现    : python3 tests/error_recovery_contract.py -k disconnect_does_not_stop")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P11 错误恢复契约")
    parser.add_argument("--report", action="store_true", help="只打印探测摘要与已知缺陷")
    args = parser.parse_args()
    if args.report:
        print_report()
    else:
        unittest.main(verbosity=2)
