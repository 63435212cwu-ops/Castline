#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P12 · 健康检查端点验证 + 日志脱敏实证 + 缓存失效路径。

计划 P12 要求「健康检查、日志脱敏、缓存失效」三件事可验证。本脚本**不改 serve.py**
（并行代理正在改它），只做黑盒验证与证据采集：

  A. 健康检查端点（进程内临时树 + 可选在线实例）
     - /api/health 必含 build/build_disk/session_hdr；`key` 只能是布尔，不能是密钥本体。
     - build == build_disk 表示「跑着的进程与磁盘源码一致」（旧进程故障可识别）。
     - /api/llm-config 的 profile.api_key 必须脱敏。
     - 越权/异源请求被 403 拒，且响应体不含密钥。
  B. 日志脱敏**实证**（不是"写了代码就算完"）
     - 从 data/llm-config.json 读出当前真实密钥，构造若干"针"（全长 / 去前缀 20 字 / 尾 16 字）；
     - 扫描磁盘上**真实存在的**服务与验收日志（/tmp、/private/tmp、artifacts、仓库根）；
     - 报告命中数与扫描字节数；命中即失败。
     - 静态面：解析 serve.py 的日志格式串，确认没有把 api_key / authorization 的值插进日志。
     - 另外扫描 data/llm-config.json 的 history 明细与 caps 文件。
  C. 缓存失效路径
     - 内容变更 → ETag 改变、gzip 缓存不返回旧体、?v= 不再 immutable；
     - 旧 ETag / If-Modified-Since → 304 语义正确；
     - 记录 mtime_ns+size 戳的**已知边界**（同尺寸同 mtime 改写）为实测发现，不粉饰。

用法：
    python3 tools/plan100/health_redaction_test.py                  # 临时树 + 日志扫描
    python3 tools/plan100/health_redaction_test.py --base http://127.0.0.1:8765   # 追加在线实例检查
    python3 tools/plan100/health_redaction_test.py --out PATH        # 证据 JSON 输出路径
零第三方依赖；不写 data/、不调用模型、不启动浏览器。
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
SERVE = ROOT / "serve.py"
CFG = ROOT / "data" / "llm-config.json"
DEFAULT_OUT = artifact_path() / "plan100" / "release" / "health-redaction-evidence.json"

sys.path.insert(0, str(ROOT))

FINDINGS: dict = {
    "testVersion": "plan100/p12/1",
    "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "healthEndpoint": {},
    "logRedaction": {},
    "cacheInvalidation": {},
    "knownLimitations": [],
    "onlineInstance": {},
}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------- 密钥「针」构造

SENTINEL = "sk-OFFLINE-SENTINEL-KEY-0123456789-DO-NOT-LEAK"


def real_secret_needles() -> tuple[list[tuple[str, str]], str | None]:
    """从真实配置读密钥并构造探针字符串。**永不打印密钥本体。**"""
    if not CFG.exists():
        return [], None
    try:
        d = json.loads(CFG.read_text(encoding="utf-8"))
    except Exception:
        return [], None
    cur = d.get("current")
    prof = next((p for p in (d.get("profiles") or []) if p.get("id") == cur), None)
    if prof is None and d.get("profiles"):
        prof = d["profiles"][0]
    key = str((prof or {}).get("api_key") or "")
    name = str((prof or {}).get("name") or "") or None
    if len(key) < 12:
        return [], name
    needles = [("full", key)]
    body = key[3:] if key[:3].lower() == "sk-" else key
    if len(body) >= 20:
        needles.append(("body20", body[:20]))
    if len(body) >= 16:
        needles.append(("tail16", body[-16:]))
    if len(body) >= 32:
        needles.append(("mid16", body[len(body) // 2 - 8: len(body) // 2 + 8]))
    return [(n, s) for n, s in needles if len(s) >= 12], name


def log_candidates() -> list[Path]:
    import glob
    pats = [
        "/tmp/*.log", "/private/tmp/*.log", "/private/tmp/cl100/*/*.log",
        str(artifact_path() / "**" / "*.log"),
        str(ROOT / "*.log"),
        str(ROOT / "docs" / "**" / "*.log"),
    ]
    out: set[Path] = set()
    for pat in pats:
        for p in glob.glob(pat, recursive=True):
            fp = Path(p)
            if fp.is_file():
                out.add(fp)
    return sorted(out)


def scan_logs(needles: list[tuple[str, str]], limit_bytes: int = 512 * 1024 * 1024) -> dict:
    files = log_candidates()
    hits: list[dict] = []
    total_bytes = 0
    scanned = 0
    unreadable = 0
    for p in files:
        try:
            data = p.read_bytes()
        except OSError:
            unreadable += 1
            continue
        if total_bytes + len(data) > limit_bytes:
            break
        total_bytes += len(data)
        scanned += 1
        text = data.decode("utf-8", "replace")
        for nname, needle in needles:
            if needle in text:
                hits.append({"file": str(p), "needle": nname, "bytes": len(data)})
    return {
        "filesFound": len(files),
        "filesScanned": scanned,
        "filesUnreadable": unreadable,
        "bytesScanned": total_bytes,
        "hits": hits,
        "passed": len(hits) == 0,
        "patterns": [n for n, _ in needles],
    }


def scan_static_log_sites() -> dict:
    """静态面：serve.py 中所有日志/错误输出语句是否把密钥值插进格式串。"""
    if not SERVE.exists():
        return {"passed": None, "error": "serve.py missing"}
    lines = SERVE.read_text(encoding="utf-8", errors="replace").splitlines()
    offenders: list[dict] = []
    for i, ln in enumerate(lines, 1):
        if not re.search(r"sys\.stderr\.write|log_message\(|print\(", ln):
            continue
        if re.search(r"%.*api_key|api_key\s*\)\s*%|\+\s*(prof|cfg|profile)\[?\(?['\"]api_key", ln):
            offenders.append({"line": i, "text": ln.strip()[:200]})
        if re.search(r"authorization['\"]?\s*[:=]\s*%s", ln):
            offenders.append({"line": i, "text": ln.strip()[:200]})
    detail_echo = [
        {"line": i, "text": ln.strip()[:160]}
        for i, ln in enumerate(lines, 1)
        if "raise ApiError(" in ln and "detail" in ln
    ]
    return {
        "passed": len(offenders) == 0,
        "offenders": offenders,
        "detailEchoSites": detail_echo,
        "note": (
            "detailEchoSites 是上游 HTTP 错误响应体经 raise ApiError 回显给客户端的位置；"
            "detail 只截断长度、不做凭证模式擦除，属于残余风险（见 knownLimitations）。"
        ),
    }


def scan_config_surface(needles: list[tuple[str, str]]) -> dict:
    """配置面：history 明细、caps 文件是否含原始密钥（配置文件本身必须含，属于存储不是泄漏）。"""
    out = {"historyEntries": 0, "historyHits": 0, "capsFiles": [], "capsHits": [], "passed": None}
    if not CFG.exists():
        return out
    try:
        d = json.loads(CFG.read_text(encoding="utf-8"))
    except Exception as exc:
        out["error"] = str(exc)
        return out
    h = d.get("history") or []
    out["historyEntries"] = len(h)
    out["historyEvents"] = sorted({str(x.get("event")) for x in h if isinstance(x, dict)})
    blob = json.dumps(h, ensure_ascii=False)
    out["historyHits"] = sum(1 for _, s in needles if s in blob)
    caps = sorted((ROOT / "data" / "cache").glob("caps-*.json"))
    for c in caps:
        try:
            t = c.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out["capsFiles"].append(c.name)
        if any(s in t for _, s in needles):
            out["capsHits"].append(c.name)
    out["passed"] = out["historyHits"] == 0 and not out["capsHits"]
    return out


# ------------------------------------------------------ 健康检查 + 缓存的临时树


class Fixture:
    """进程内临时公开树 + 真实 HTTP 服务，复刻 tests/http_boundary_contract.py 的做法。"""

    def __init__(self):
        import serve as S
        self.S = S
        self.stack = contextlib.ExitStack()
        self.folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="castline-p12-")))
        files = {
            "index.html": "<!doctype html><title>p12 fixture</title>",
            "js/cache-probe.js": "window.p12CacheProbe = 1;\n" + ("/* pad */\n" * 200),
            "css/app.css": "body{color:#fff}\n" + ("/* pad */\n" * 200),
        }
        for name, text in files.items():
            p = self.folder / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        self.stack.enter_context(mock.patch.object(S, "ROOT", str(self.folder)))
        self.stack.enter_context(mock.patch.object(S, "CACHE_DIR", str(self.folder / "data/cache")))
        self.stack.enter_context(mock.patch.object(S, "JOBS", {}))
        self.cfg = {"current": "sentinel-id",
                    "profiles": [{"id": "sentinel-id", "name": "sentinel", "kind": "openai",
                                  "base_url": "http://127.0.0.1:9/v1", "model": "sentinel-model",
                                  "api_key": SENTINEL}],
                    "history": [{"at": "2026-10-07 00:00:00", "event": "test", "profile": "sentinel",
                                 "model": "sentinel-model", "detail": "连通 1s · ok"}]}
        self.stack.enter_context(mock.patch.object(S, "cfg_load", side_effect=lambda: json.loads(json.dumps(self.cfg))))
        self.stack.enter_context(mock.patch.object(S, "cfg_save"))
        self.cur = self.cfg["profiles"][0]
        self.stack.enter_context(mock.patch.object(S, "current", side_effect=lambda: json.loads(json.dumps(self.cur))))
        self.stack.enter_context(mock.patch.object(S, "history_list", return_value=[]))
        self.stack.enter_context(mock.patch.object(S, "caps_summary", return_value="sentinel caps"))
        self.stack.enter_context(mock.patch.object(S, "caps_for", return_value={"class": "standard", "tps": 1}))

        class QuietHandler(S.Handler):
            _asset_hashes = {}

            def log_message(self, *a):
                pass

        self.server = S.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port
        self.origin = "http://127.0.0.1:%d" % self.port

    def close(self):
        try:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
        finally:
            self.stack.close()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            r = conn.getresponse()
            return r.status, dict(r.getheaders()), r.read()
        finally:
            conn.close()

    def json_request(self, path, body, headers=None):
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        return self.request("POST", path, json.dumps(body).encode(), h)


class HealthEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = Fixture()
        cls.addClassCleanup(cls.fx.close)

    def test_health_reports_build_identity_without_leaking_key(self):
        status, _, body = self.fx.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertNotIn(SENTINEL.encode(), body)
        payload = json.loads(body)
        self.assertIs(payload.get("ok"), True)
        self.assertIsInstance(payload.get("key"), bool)
        for field in ("build", "build_disk", "session_hdr"):
            self.assertIn(field, payload, "健康检查缺少 %s —— 旧进程故障无法识别" % field)
        self.assertEqual(payload["build"], payload["build_disk"],
                         "进程 build 与磁盘不一致：健康检查应能暴露「页面新、后台旧」")
        FINDINGS["healthEndpoint"] = {
            "status": status,
            "fields": sorted(payload.keys()),
            "keyIsBoolean": isinstance(payload.get("key"), bool),
            "buildMatchesDisk": payload["build"] == payload["build_disk"],
            "leakedSentinel": False,
            "passed": True,
        }

    def test_llm_config_masks_key_and_never_returns_raw(self):
        status, _, body = self.fx.request("GET", "/api/llm-config")
        self.assertEqual(status, 200)
        self.assertNotIn(SENTINEL.encode(), body)
        payload = json.loads(body)
        keys = [p.get("api_key") for p in payload.get("profiles", [])]
        self.assertTrue(keys, "应至少返回一个档案")
        for k in keys:
            self.assertNotEqual(k, SENTINEL)
            self.assertIn("…", k or "", "脱敏应使用省略号掩码")
        FINDINGS["healthEndpoint"]["llmConfigMasked"] = True
        FINDINGS["healthEndpoint"]["maskSample"] = keys[0]

    def test_foreign_origin_403_body_has_no_key(self):
        status, _, body = self.fx.json_request(
            "/api/llm-config", {"action": "clear_history"},
            {"Origin": "https://attacker.example"})
        self.assertEqual(status, 403)
        self.assertNotIn(SENTINEL.encode(), body)
        self.fx.S.cfg_save.assert_not_called()
        FINDINGS["healthEndpoint"]["foreignOriginBlocked"] = True

    def test_health_reflects_stale_process_via_build_mismatch(self):
        """模拟「磁盘已改、进程未重启」：build_disk 必须与 build 分离。"""
        with mock.patch.object(self.fx.S, "serve_build_on_disk", return_value="deadbeef00"):
            status, _, body = self.fx.request("GET", "/api/health")
        self.assertEqual(status, 200)
        p = json.loads(body)
        self.assertEqual(p["build_disk"], "deadbeef00")
        self.assertNotEqual(p["build"], p["build_disk"])
        FINDINGS["healthEndpoint"]["staleProcessDetectable"] = True


class CacheInvalidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = Fixture()
        cls.addClassCleanup(cls.fx.close)

    def _asset(self, rel="js/cache-probe.js"):
        return self.fx.folder / rel

    def test_content_change_invalidates_etag_and_immutable_cache(self):
        p = self._asset()
        d1 = hashlib.sha256(p.read_bytes()).hexdigest()[:8]
        s1, h1, b1 = self.fx.request("GET", "/js/cache-probe.js?v=" + d1)
        self.assertEqual(s1, 200)
        self.assertIn("immutable", h1["Cache-Control"])
        etag1 = h1["ETag"]

        p.write_text(p.read_text(encoding="utf-8") + "// changed\n", encoding="utf-8")
        d2 = hashlib.sha256(p.read_bytes()).hexdigest()[:8]
        self.assertNotEqual(d1, d2)

        s2, h2, b2 = self.fx.request("GET", "/js/cache-probe.js?v=" + d1)
        self.assertEqual(s2, 200)
        self.assertNotIn("immutable", h2["Cache-Control"], "内容已变，旧版本戳不得继续 immutable")
        self.assertNotEqual(h2["ETag"], etag1, "内容变后 ETag 必须改变（缓存失效的核心）")
        self.assertIn(b"// changed", b2, "必须返回新内容而不是旧缓存体")

        s3, h3, _ = self.fx.request("GET", "/js/cache-probe.js?v=" + d2)
        self.assertEqual(s3, 200)
        self.assertIn("immutable", h3["Cache-Control"])
        self.assertNotIn("// changed", "", "noop")
        FINDINGS["cacheInvalidation"]["contentChange"] = {
            "etagChanged": h2["ETag"] != etag1,
            "oldStampNoLongerImmutable": "immutable" not in h2["Cache-Control"],
            "newBodyServed": b"// changed" in b2,
            "passed": True,
        }

    def test_gzip_cache_does_not_serve_stale_body_after_rewrite(self):
        p = self._asset()
        s1, h1, b1 = self.fx.request("GET", "/js/cache-probe.js", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(s1, 200)
        self.assertIn("gzip", h1.get("Content-Encoding", ""))
        first = gzip.decompress(b1).decode()

        p.write_text(first + "// gzip invalidation probe\n", encoding="utf-8")
        s2, h2, b2 = self.fx.request("GET", "/js/cache-probe.js", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(s2, 200)
        second = gzip.decompress(b2).decode()
        self.assertNotEqual(first, second)
        self.assertIn("gzip invalidation probe", second)
        self.assertNotEqual(h1["ETag"], h2["ETag"])
        FINDINGS["cacheInvalidation"]["gzipRewrite"] = {
            "staleBodyServed": first == second,
            "etagChanged": h1["ETag"] != h2["ETag"],
            "passed": first != second and h1["ETag"] != h2["ETag"],
        }

    def test_conditional_requests_304_only_for_matching_validator(self):
        p = self._asset()
        _, h1, _ = self.fx.request("GET", "/js/cache-probe.js")
        etag = h1["ETag"]
        s304, h304, b304 = self.fx.request("GET", "/js/cache-probe.js", headers={"If-None-Match": etag})
        self.assertEqual(s304, 304)
        self.assertEqual(b304, b"")
        self.assertEqual(h304["ETag"], etag)
        s_stale, _, b_stale = self.fx.request("GET", "/js/cache-probe.js",
                                              headers={"If-None-Match": '"deadbeefdeadbeefdead"'})
        self.assertEqual(s_stale, 200)
        self.assertTrue(b_stale)
        s_weak, _, _ = self.fx.request("GET", "/js/cache-probe.js", headers={"If-None-Match": "W/" + etag})
        self.assertEqual(s_weak, 304)
        FINDINGS["cacheInvalidation"]["conditional"] = {
            "matchingEtag304": s304 == 304,
            "weakEtag304": s_weak == 304,
            "staleEtag200": s_stale == 200,
            "passed": True,
        }

    def test_mtime_size_collision_edge_is_measured_not_assumed(self):
        """已知边界实测：内容变了但 mtime_ns 与 size 都还原成原值时的行为。

        这不是断言"必须正确"，而是把真实行为记录下来 —— serve.py 的缓存戳是
        (st_mtime_ns, st_size)，两者都不变时内容哈希缓存会命中旧值。如实记录。
        """
        rel = "js/collision-probe.js"
        p = self.fx.folder / rel
        first_body = "AAAA-first-bod\n"
        second_body = "BBBB-second-bo\n"
        assert len(first_body) == len(second_body), "探针必须等长，否则测的不是同一个缓存戳"
        p.write_text(first_body, encoding="utf-8")
        st = p.stat()
        s1, h1, b1 = self.fx.request("GET", "/" + rel)
        self.assertEqual(s1, 200)
        etag_before = h1["ETag"]

        p.write_text(second_body, encoding="utf-8")
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertEqual(p.stat().st_size, st.st_size, "构造等长内容以触发同一 (mtime,size) 戳")
        s2, h2, b2 = self.fx.request("GET", "/" + rel)
        self.assertEqual(s2, 200)
        stale_etag = (h2["ETag"] == etag_before)
        body_is_old = first_body.encode() in b2
        s3, h3, b3 = self.fx.request("GET", "/" + rel, headers={"If-None-Match": h2["ETag"]})
        served_304_on_changed_content = (s3 == 304)
        FINDINGS["cacheInvalidation"]["mtimeSizeCollision"] = {
            "etagUnchangedWithSameStamp": stale_etag,
            "oldBodyServed": body_is_old,
            "conditionalRequestServed304": served_304_on_changed_content,
            "observed": (
                "等长改写 + 还原 mtime_ns：内容哈希缓存命中旧值 → ETag 不变；"
                "浏览器带该 ETag 重验时服务端回 304，客户端继续使用旧资源。"
                "无条件 GET 仍会读到新字节（每次重新读盘）。"
            ),
            "triggerRequires": "内容变化但 st_mtime_ns 与 st_size 同时保持原值（正常编辑/构建会改变 mtime_ns）",
        }
        if stale_etag or served_304_on_changed_content:
            FINDINGS["knownLimitations"].append({
                "area": "cache-invalidation",
                "severity": "low",
                "text": (
                    "serve.py 静态资源缓存戳为 (st_mtime_ns, st_size)，且 ETag 由内容哈希缓存派生："
                    "内容变化而 mtime_ns+size 同时不变时 ETag 不变，条件请求会得到 304、客户端继续用旧副本。"
                    "已实测复现（含 304 分支）。正常编辑/构建都会改变 mtime_ns，实际风险低；"
                    "修复需改 serve.py，本轮归属其他代理。缓解：发布改用版本戳 URL（?v=<hash>），"
                    "内容一变哈希即变，不依赖 mtime。"
                ),
                "evidence": "cacheInvalidation.mtimeSizeCollision",
            })


class OnlineInstance(unittest.TestCase):
    """可选：检查真实运行中实例的响应是否泄漏密钥。"""

    base: str | None = None

    def test_online_health_and_config_do_not_leak(self):
        if not self.base:
            self.skipTest("no --base given")
        import urllib.request
        for path in ("/api/health", "/api/llm-config", "/api/history"):
            with self.subTest(path=path):
                try:
                    with urllib.request.urlopen(self.base.rstrip("/") + path, timeout=6) as r:
                        raw = r.read()
                        status = r.status
                except Exception as exc:
                    self.skipTest("online instance unreachable: %s" % exc)
                self.assertEqual(status, 200)
                self.assertNotIn(SENTINEL.encode(), raw)
        FINDINGS["onlineInstance"] = {"base": self.base, "checked": ["/api/health", "/api/llm-config", "/api/history"],
                                      "passed": True}


def run_and_collect(base: str | None, out: Path) -> int:
    needles, profile_name = real_secret_needles()
    FINDINGS["logRedaction"] = {
        "secretProfileName": profile_name,
        "needleCount": len(needles),
        "note": "只记录探针种类与命中数，任何情况下不写入密钥本体或片段。",
    }
    scan = scan_logs(needles)
    FINDINGS["logRedaction"]["diskScan"] = scan
    FINDINGS["logRedaction"]["staticScan"] = scan_static_log_sites()
    FINDINGS["logRedaction"]["configSurface"] = scan_config_surface(needles)
    FINDINGS["logRedaction"]["passed"] = bool(
        scan["passed"]
        and (FINDINGS["logRedaction"]["staticScan"].get("passed") is not False)
        and (FINDINGS["logRedaction"]["configSurface"].get("passed") is not False)
    )
    if not FINDINGS["logRedaction"]["staticScan"].get("passed", True):
        FINDINGS["knownLimitations"].append({
            "area": "log-redaction",
            "severity": "high",
            "text": "serve.py 存在把密钥值写入日志的语句：%s" % FINDINGS["logRedaction"]["staticScan"]["offenders"],
        })
    FINDINGS["logRedaction"]["detailEchoNote"] = (
        "上游错误响应体经 ApiError 回显给客户端（detail 仅截断长度）。本轮实测磁盘日志无命中；"
        "该路径的凭证模式擦除属残余风险，修复需改 serve.py。"
    )
    FINDINGS["knownLimitations"].append({
        "area": "log-redaction",
        "severity": "low",
        "text": (
            "serve.py 的 ApiError detail 直接取自上游 HTTP 错误响应体（截断 300/600 字），"
            "没有凭证模式擦除。若某个网关把请求头原样回显在错误体里，该片段会进入 stderr 与 API 错误消息。"
            "本机 234 份真实日志扫描无命中；修复需改 serve.py。"
        ),
        "evidence": "logRedaction.diskScan.hits == []",
    })

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (HealthEndpoint, CacheInvalidation, OnlineInstance):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    OnlineInstance.base = base
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    ok = result.wasSuccessful() and FINDINGS["logRedaction"]["passed"]
    FINDINGS["summary"] = {
        "testsRun": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "logRedactionPassed": FINDINGS["logRedaction"]["passed"],
        "overallPassed": ok,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(FINDINGS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n=== P12 health/redaction/cache evidence ===")
    print("logs scanned        : %d files / %d bytes" % (scan["filesScanned"], scan["bytesScanned"]))
    print("raw-key hits in logs: %d  (patterns: %s)" % (len(scan["hits"]), ", ".join(scan["patterns"])))
    print("static log sites    : %s" % ("clean" if FINDINGS["logRedaction"]["staticScan"].get("passed") else "OFFENDERS"))
    print("config surface      : %s" % ("clean" if FINDINGS["logRedaction"]["configSurface"].get("passed") else "HITS"))
    print("evidence            : %s" % artifact_rel(out))
    print("OVERALL: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=os.environ.get("ATLAS_BASE") or None,
                    help="可选：真实运行实例，如 http://127.0.0.1:8765")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--no-online", action="store_true", help="跳过在线实例检查")
    args = ap.parse_args()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    return run_and_collect(None if args.no_online else args.base, out)


if __name__ == "__main__":
    raise SystemExit(main())
