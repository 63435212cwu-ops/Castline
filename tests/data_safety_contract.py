#!/usr/bin/env python3
"""P11-W07/W08 · 数据安全契约（HTTP 边界 / 路径穿越 / 畸形输入 / 超长字段 / 未授权 / SSRF）。

与已有的 `tests/http_boundary_contract.py` 互补而非重复：那一个覆盖静态文件白名单、
Host/Origin、Content-Length 与缓存头；本文件覆盖**它没有覆盖的**面：

  1. 缓存 key 边界：`cache_key()` 与各 API 路由对穿越/超长/空/NUL 的处置；
  2. 畸形 JSON：截断、非法 UTF-8、BOM、顶层非对象、重复键、NaN、孤立代理项；
  3. 超长字段：合法 body 内部的超长 name/title/quote（不是 body 总量限制）；
  4. 原型污染：`__proto__`/`constructor`/`prototype` 键不得污染进程内共享状态；
  5. 未授权：foreign Origin / 错误 Host / 方法混淆 / 绝对形式请求行一律拒绝；
  6. SSRF：模型地址规范化与 file:// scheme 的可达性；
  7. 空/稀疏输入必须明确降级，不得编造来源。

断言分三类：
  HARD      今天成立的不变量，退化即 fail。
  RATCHET   已知缺陷的**冻结签名**。缺陷仍在 → 复现并打印 KNOWN DEFECT 横幅；
            缺陷被修好 → skip 并提示收紧基线（不制造「修好反而变红」）；
            缺陷**恶化**（边界前移）→ fail。

所有失败都带原始输入、期望 vs 实际和最小复现命令。

用法：
  python3 tests/data_safety_contract.py
  python3 tests/data_safety_contract.py --report   # 只打印探测摘要与已知缺陷
"""
from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import serve as S

_REAL_URLOPEN = S.urllib.request.urlopen

SAFE_TEXT = "北辰推开古塔的门。他走了进去，风从背后追上来。"

KNOWN_DEFECTS = {
    "deep_nesting_crash_depth": 9990,
    "lone_surrogate_drops_connection": False,
    "ssrf_file_scheme_reachable": False,
}


def _fixture_files():
    return {
        "index.html": "<!doctype html><title>data safety fixture</title>",
        "js/app.js": "window.dataSafetyFixture = true;",
        "data/cache/index.json": "[]",
        "data/cache/1234abcd.json": json.dumps({"title": "fixture", "characters": [], "events": []}),
        "data/cache/1234abcd.docs.json": json.dumps(
            [{"kind": "正文", "name": "fixture", "path": "fixture.txt", "text": SAFE_TEXT}]),
        "data/llm-config.json": '{"profiles":[{"api_key":"DATA_SAFETY_SENTINEL"}]}',
        "serve.py": "internal source fixture",
        "README.md": "internal documentation fixture",
    }


class DataSafetyContract(unittest.TestCase):
    """进程内真实 HTTP 服务，零网络、零模型调用。"""

    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.folder = Path(cls.stack.enter_context(tempfile.TemporaryDirectory(prefix="castline-p11-safety-")))
        for name, text in _fixture_files().items():
            path = cls.folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        cls.cache_dir = cls.folder / "data/cache"

        cls.stack.enter_context(patch.object(S, "ROOT", str(cls.folder)))
        cls.stack.enter_context(patch.object(S, "CACHE_DIR", str(cls.cache_dir)))
        cls.stack.enter_context(patch.object(S, "HIST_PATH", str(cls.cache_dir / "index.json")))
        cls.stack.enter_context(patch.object(S, "JOBS", {}))
        cls.stack.enter_context(patch.object(S, "cfg_load", return_value={"profiles": [], "current": "", "history": []}))
        cls.cfg_save = cls.stack.enter_context(patch.object(S, "cfg_save"))
        cls.stack.enter_context(patch.object(S, "current", return_value=None))
        cls.stack.enter_context(patch.object(S, "cfg_history"))
        cls.stack.enter_context(patch.object(S, "history_list", return_value=[]))
        cls.stack.enter_context(patch.object(S, "run_job", side_effect=AssertionError("MODEL CALL FORBIDDEN")))
        cls.stack.enter_context(patch.object(S, "run_distill", side_effect=AssertionError("MODEL CALL FORBIDDEN")))
        cls.stack.enter_context(patch.object(S, "call_llm", side_effect=AssertionError("MODEL CALL FORBIDDEN")))
        cls.stack.enter_context(patch.object(S.urllib.request, "urlopen",
                                             side_effect=AssertionError("EXTERNAL NETWORK FORBIDDEN")))

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

    # ---------- 传输层工具 ----------

    def raw(self, method, path, body=b"", headers=(), timeout=15):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        self.addCleanup(conn.close)
        base = [("Host", "127.0.0.1:%d" % self.port)]
        try:
            conn.request(method, path, body=body, headers=dict(base + list(headers)))
            response = conn.getresponse()
            return response.status, response.read()
        except (http.client.HTTPException, OSError) as exc:
            return "TRANSPORT", repr(exc)

    def api(self, path, payload=None, headers=None, method="POST", raw_body=None):
        body = raw_body if raw_body is not None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        heads = [("Content-Type", "application/json")]
        heads.extend((headers or {}).items())
        return self.raw(method, path, body, heads)

    def json_api(self, path, payload, headers=None):
        status, body = self.api(path, payload, headers)
        self.assertNotEqual(status, "TRANSPORT", "请求在传输层就断了：%r" % (body,))
        try:
            return status, json.loads(body)
        except Exception:
            self.fail("响应不是 JSON：status=%r body=%r" % (status, body[:200]))

    @staticmethod
    def evidence(**kwargs):
        return "\n失败证据:\n" + json.dumps(kwargs, ensure_ascii=False, indent=2, sort_keys=True, default=repr)[:3500]

    @staticmethod
    def defect_banner(tag, title, detail, repro):
        sys.stderr.write("\n[已知缺陷 %s] %s\n  %s\n  最小复现: %s\n" % (tag, title, detail, repro))

    # ---------- 1 · 缓存 key 边界 ----------

    def test_cache_key_rejects_paths_outside_hex_identity(self):
        """cache_key() 是路径拼接的唯一入口，只接受 8-40 位十六进制。"""
        rejected = ["../llm-config", "..%2Fllm-config", "/etc/passwd", "", None, "   ",
                    "1234abcd\x00", "1234abcd/../1234abcd", "1234abcd.docs", "ABCDEFGH",
                    "123", "x" * 41, "../../data/cache/1234abcd", "0x1234abcd", "-1234abcd",
                    "1234abcd%00", "..", ".", "1234abcd/sub"]
        wrongly = [(value, S.cache_key(value)) for value in rejected if S.cache_key(value) != ""]
        self.assertEqual(
            wrongly, [],
            "cache_key 放行了非法 key——它们会被直接拼进缓存目录路径" + self.evidence(
                expectation="all rejected to ''", wrong=wrongly,
                minimalRepro="python3 -c \"import serve;print(repr(serve.cache_key('../llm-config')))\""))
        for value in ("1234abcd", "a" * 40, "0123456789abcdef0123456789abcdef01234567"):
            with self.subTest(key=value):
                self.assertEqual(S.cache_key(value), value.lower(),
                                 "合法十六进制 key 被误拒" + self.evidence(key=value, actual=S.cache_key(value)))
        for value, expected in (("1234abcd ", "1234abcd"), ("1234abcd\n", "1234abcd"),
                                (" 1234ABCD\t", "1234abcd")):
            with self.subTest(key=repr(value)):
                self.assertEqual(S.cache_key(value), expected,
                                 "key 的空白规范化行为变了" + self.evidence(input=value, expected=expected,
                                                                        actual=S.cache_key(value)))

    def test_key_bearing_routes_never_escape_the_cache_directory(self):
        """穿越 key 在真实路由上必须 400/404，且绝不返回缓存目录外的文件。"""
        hostile = ["../llm-config", "..%2Fllm-config", "../../data/llm-config", "/etc/passwd",
                   "1234abcd\x00", "A" * 200, "1234abcd/../../llm-config", "..", "1234abcd.docs"]
        leaks = []
        for key in hostile:
            for path, payload in (("/api/enrich/plan", {"key": key, "sourceOnly": True}),
                                  ("/api/enrich", {"key": key, "sourceOnly": True}),
                                  ("/api/source/rebuild", {"key": key})):
                status, body = self.api(path, payload)
                if status == 200 or b"DATA_SAFETY_SENTINEL" in body:
                    leaks.append({"path": path, "key": key, "status": status,
                                  "body": body[:160].decode("utf-8", "replace")})
            status, body = self.raw("GET", "/api/history/docs?key=" + key.replace(" ", "%20"))
            if status == 200 and b"DATA_SAFETY_SENTINEL" in body:
                leaks.append({"path": "/api/history/docs", "key": key, "status": status})
        self.assertEqual(leaks, [], "穿越 key 触达了缓存目录之外的内容" + self.evidence(
            hostileInputs=hostile, leaks=leaks,
            minimalRepro='curl -s "http://127.0.0.1:PORT/api/history/docs?key=../llm-config"'))

    def test_history_docs_serves_materials_only_for_valid_existing_keys(self):
        """该路由按「合法 key + 材料文件存在」判定；非法 key 或不存在的材料一律 404。"""
        status, body = self.raw("GET", "/api/history/docs?key=1234abcd")
        self.assertEqual(status, 200, "合法 key 且材料存在时应可取回" + self.evidence(
            actual=status, body=body[:160].decode("utf-8", "replace")))
        self.assertEqual(json.loads(body)[0]["text"], SAFE_TEXT)
        for key in ("deadbeef", "", "..", "../llm-config", "1234abcd%00", "1234abcd.docs"):
            with self.subTest(key=repr(key)):
                status, _ = self.raw("GET", "/api/history/docs?key=" + key.replace(" ", "%20"))
                self.assertEqual(status, 404, "非法或不存在的 key 未被判 404" + self.evidence(
                    key=key, expected=404, actual=status,
                    minimalRepro='curl -s -o /dev/null -w "%%{http_code}" "http://127.0.0.1:PORT/api/history/docs?key=%s"' % key))

    def test_config_save_rejects_non_string_fields_before_config_access(self):
        """畸形档案字段返回400；不得读/写配置或发出模型请求。"""
        with patch.object(S, "cfg_load", side_effect=AssertionError("CONFIG READ FORBIDDEN")) as read_config:
            self.cfg_save.reset_mock()
            for field in ("id", "name", "kind", "base_url", "model", "api_key"):
                for value in (12, False, [], {}):
                    with self.subTest(field=field, value=value):
                        status, body = self.json_api("/api/llm-config", {"action": "save", field: value})
                        self.assertEqual(status, 400)
                        self.assertIn(field, body["error"])
            read_config.assert_not_called()
            self.cfg_save.assert_not_called()

    def test_analysis_routes_reject_invalid_docs_before_planning_or_jobs(self):
        """三种分析入口在副作用前拒绝材料容器、条目与声明文本字段的错类型。"""
        cases = [(None, "docs"), ({}, "docs"), ("text", "docs"),
                 ([1], "docs[0]"), ([None], "docs[0]"), ([[]], "docs[0]")]
        cases.extend(([{field: 42}], "docs[0]." + field)
                     for field in ("text", "name", "path", "kind", "sourceText"))
        with patch.object(S, "cfg_load", side_effect=AssertionError("CONFIG READ FORBIDDEN")) as read_config, \
                patch.object(S, "make_plan", side_effect=AssertionError("PLAN FORBIDDEN")) as plan, \
                patch.object(S, "run_job", side_effect=AssertionError("JOB FORBIDDEN")) as run, \
                patch.object(S, "run_distill", side_effect=AssertionError("DISTILL FORBIDDEN")) as distill:
            self.cfg_save.reset_mock()
            for route in ("/api/plan", "/api/analyze", "/api/distill"):
                for docs, field in cases:
                    with self.subTest(route=route, docs=docs):
                        status, body = self.json_api(route, {"docs": docs})
                        self.assertEqual(status, 400)
                        self.assertIn(field, body["error"])
            for blocked in (read_config, plan, run, distill, self.cfg_save):
                blocked.assert_not_called()
            self.assertEqual(S.JOBS, {})

    def test_config_save_null_optional_fields_keep_existing_defaults(self):
        self.cfg_save.reset_mock()
        status, body = self.json_api("/api/llm-config", {
            "action": "save", "id": None, "name": None, "kind": None,
            "base_url": "http://127.0.0.1:9/v1", "model": "offline-model", "api_key": "offline-fixture"})
        self.assertEqual(status, 200)
        self.assertNotIn("error", body)
        self.cfg_save.assert_called_once()
        saved = self.cfg_save.call_args[0][0]["profiles"][0]
        self.assertTrue(saved["id"])
        self.assertEqual(saved["name"], "offline-model")
        self.assertEqual(saved["kind"], "openai")

    def test_analysis_routes_accept_optional_null_document_fields(self):
        """合法空值仍交给既有规划/作业语义；这里只用完成的离线作业夹具。"""
        docs = [{"text": SAFE_TEXT, "name": None, "path": None, "kind": None, "sourceText": None}]
        with patch.object(S, "make_plan", return_value={"files": 1}) as plan:
            status, body = self.json_api("/api/plan", {"docs": docs})
            self.assertEqual((status, body["files"]), (200, 1))
            self.assertEqual(plan.call_args[0][0], docs)
        for route, method in (("/api/analyze", "run_job"), ("/api/distill", "run_distill")):
            with self.subTest(route=route):
                job = S.Job("offline-input-fixture", profile={}, docs=docs)
                job.emit("done", {"graph": {"characters": [], "events": []}})
                with patch.object(S, method, return_value=(job, False)) as start:
                    status, body = self.api(route, {"docs": docs})
                    self.assertEqual(status, 200)
                    self.assertIn(b"event: done", body)
                    self.assertEqual(start.call_args[0][0], docs)
        with patch.object(S, "make_plan", return_value={"files": 0}) as plan:
            status, _ = self.json_api("/api/plan", {})
            self.assertEqual(status, 200)
            self.assertEqual(plan.call_args[0][0], [])

    # ---------- 2 · 畸形 JSON ----------

    def test_malformed_json_variants_are_rejected_with_a_client_error(self):
        """截断 / 非法 UTF-8 / 顶层非对象 / 空 body 一律 400 且带 error 字段。"""
        cases = [
            ("truncated", b'{"docs":[{"name":"a"'),
            ("invalid-utf8", b'{"a":"\xff\xfe"}'),
            ("top-level-list", b'[]'),
            ("top-level-null", b"null"),
            ("top-level-string", b'"string"'),
            ("top-level-number", b"42"),
            ("empty-body", b""),
            ("whitespace-only", b"   \n  "),
            ("trailing-garbage", b'{"docs":[]} trailing'),
            ("unclosed-string", b'{"a":"unterminated'),
        ]
        for name, body in cases:
            with self.subTest(case=name):
                status, response = self.api("/api/source", raw_body=body)
                self.assertNotEqual(
                    status, "TRANSPORT",
                    "畸形 body 让连接直接断开，客户端拿不到可诊断的错误" + self.evidence(
                        case=name, rawBytes=repr(body), transport=str(response)[:200]))
                self.assertEqual(status, 400, "畸形 JSON 未被判为 400" + self.evidence(
                    case=name, rawBytes=repr(body), expected=400, actual=status,
                    body=response[:200].decode("utf-8", "replace"),
                    minimalRepro=("printf %r | curl -s -X POST --data-binary @- "
                                  "-H 'Content-Type: application/json' http://127.0.0.1:PORT/api/source" % body)))
                self.assertIn("error", json.loads(response))

    def test_tolerated_json_edge_cases_are_explicitly_pinned(self):
        """Python json 会接受而严格解析器会拒绝的输入：显式固定行为，不假装它们被拒。

        这些**不是**缺陷（标准库语义），但必须被固定，否则将来换解析器时会静默改变。
        """
        status, _ = self.api("/api/source", raw_body=b'{"docs":[],"docs":[]}')
        self.assertEqual(status, 200, "重复键行为变了" + self.evidence(actual=status))
        status, _ = self.api("/api/source", raw_body=b'\xef\xbb\xbf{"docs":[]}')
        self.assertEqual(status, 400, "BOM 前缀行为变了" + self.evidence(actual=status))
        status, body = self.api("/api/source", raw_body=b'{"docs":[],"x":NaN,"y":Infinity}')
        self.assertEqual(status, 200, "NaN 字面量行为变了" + self.evidence(actual=status))
        self.assertNotIn(b"NaN", body, "非标准 NaN 被回写进响应体——下游解析器会炸"
                         + self.evidence(body=body[:200].decode("utf-8", "replace")))

    def test_non_json_content_types_are_rejected(self):
        for content_type in ("text/plain", "application/xml", "text/html", "application/x-www-form-urlencoded"):
            with self.subTest(content_type=content_type):
                status, _ = self.raw("POST", "/api/source", b"{}", [("Content-Type", content_type)])
                self.assertEqual(status, 415, "非 application/json 未被拒" + self.evidence(
                    contentType=content_type, expected=415, actual=status))
        status, _ = self.raw("POST", "/api/source", b"{}", [("Content-Type", "application/json, text/plain")])
        self.assertEqual(status, 415, "复合 Content-Type 未被拒")
        status, _ = self.raw("POST", "/api/source", b"{}")
        self.assertEqual(status, 415, "缺 Content-Type 未被拒")
        status, _ = self.raw("POST", "/api/source", b'{"docs":[]}', [("Content-Type", "application/json; charset=gbk")])
        self.assertIn(status, (200, 400, 415), "带 charset 参数时返回意外状态" + self.evidence(actual=status))

    # ---------- 3 · 超长字段 ----------

    def test_oversized_fields_inside_a_legal_body_are_not_truncated_silently(self):
        """body 总量合法，但内部字段极长——必须明确处理，不能崩、不能静默截断。"""
        long_name = "名" * 200000
        status, body = self.api("/api/source", {"docs": [{"name": long_name, "text": SAFE_TEXT}]})
        self.assertEqual(status, 200, "合法 body 内的超长 name 让请求失败" + self.evidence(
            fieldLength=len(long_name), expected=200, actual=status,
            body=body[:200].decode("utf-8", "replace")))
        payload = json.loads(body)
        self.assertTrue(payload["known"], "超长 name 的材料被静默丢弃" + self.evidence(response=payload))
        self.assertEqual(len(payload["sources"][0]["name"]), len(long_name),
                         "超长 name 被静默截断——下游会拿到与输入不符的材料标识")

    def test_extreme_title_and_quote_lengths_stay_bounded_and_verbatim(self):
        """超长 title 不应被截断；伪造引文必须明确判为未核验。"""
        huge_title = "标" * 50000
        status, body = self.json_api("/api/source/rebuild", {
            "graph": {"characters": [], "events": [
                {"id": "e-long", "order": 1, "title": huge_title, "quote": SAFE_TEXT}]},
            "docs": [{"name": "a", "text": SAFE_TEXT}]})
        self.assertEqual(status, 200, "超长 title 让来源重建失败" + self.evidence(actual=status, body=body))
        event = body["graph"]["events"][0]
        self.assertEqual(event["title"], huge_title, "超长 title 被静默截断")
        self.assertTrue(event["quoteRef"]["verified"], "短而真实的引文应被核验" + self.evidence(event=event))

        forged = "伪" * 30000
        status, body = self.json_api("/api/source/rebuild", {
            "graph": {"characters": [], "events": [
                {"id": "e-forged", "order": 1, "title": "伪造", "quote": forged}]},
            "docs": [{"name": "a", "text": SAFE_TEXT}]})
        self.assertEqual(status, 200)
        ref = body["graph"]["events"][0]["quoteRef"]
        self.assertFalse(ref["verified"], "不存在的超长引文被标成已核验——虚构证据" + self.evidence(
            quoteLength=len(forged), ref=ref, expected="verified=false"))
        self.assertIn(ref["match"], ("none", "unmatched", "ambiguous"),
                      "未命中引文的 match 取值不在预期集合内" + self.evidence(match=ref["match"]))

    def test_empty_documents_degrade_without_inventing_sources(self):
        """合法空材料降级为 known=false；错误 docs 容器在来源处理前返回 400。"""
        for name, docs in (("empty-list", []),
                           ("empty-text", [{"name": "a", "text": ""}]),
                           ("no-text-field", [{"name": "a"}]),
                           ("null-text", [{"name": "a", "text": None}])):
            with self.subTest(case=name):
                status, body = self.json_api("/api/source", {"docs": docs})
                self.assertEqual(status, 200, "合法空材料应明确降级而不是报错" + self.evidence(case=name, actual=status))
                self.assertFalse(body["known"], "空材料被当成已知来源" + self.evidence(case=name, response=body))
                self.assertEqual(body["sources"], [], "空材料编造出了来源" + self.evidence(case=name, response=body))
                self.assertEqual(body["quotes"], {"total": 0, "verified": 0, "unverified": 0})

        with patch.object(S, "source_specs", side_effect=AssertionError("SOURCE PROCESSING FORBIDDEN")) as process:
            for name, docs in (("docs-not-a-list", {"nope": True}), ("docs-null", None)):
                with self.subTest(case=name):
                    status, body = self.json_api("/api/source", {"docs": docs})
                    self.assertEqual(status, 400, "错误 docs 容器应在来源处理前返回 400" + self.evidence(
                        case=name, actual=status, response=body))
                    self.assertIn("error", body, "类型错误响应缺少 error 字段")
            process.assert_not_called()

    def test_whitespace_only_documents_never_produce_verified_quotes(self):
        """纯空白材料即使被登记为来源，也不得产生任何「已核验」引句。"""
        status, body = self.json_api("/api/source", {"docs": [{"name": "a", "text": "   \n\t  "}]})
        self.assertEqual(status, 200)
        self.assertEqual(body["quotes"]["total"], 0, "纯空白材料统计出了引句" + self.evidence(response=body))
        self.assertEqual(body["quotes"]["verified"], 0, "纯空白材料产生了已核验引句" + self.evidence(response=body))
        status, body = self.json_api("/api/source/rebuild", {
            "graph": {"characters": [], "events": [{"id": "e", "order": 1, "title": "t", "quote": "北辰"}]},
            "docs": [{"name": "a", "text": "   \n\t  "}]})
        self.assertFalse(body["graph"]["events"][0]["quoteRef"]["verified"],
                         "空白材料里的引文被标成已核验——虚构证据" + self.evidence(response=body["graph"]["events"][0]))

    # ---------- 4 · 原型污染 ----------

    def test_prototype_pollution_keys_never_reach_shared_state(self):
        """`__proto__`/`constructor`/`prototype` 不得污染模块级字典或缓存目录。"""
        sentinel = "P11_POLLUTION_SENTINEL"
        marker = {"polluted": sentinel}
        bodies = [
            {"docs": [], "__proto__": marker},
            {"docs": [], "constructor": {"prototype": marker}},
            {"docs": [], "prototype": marker},
            {"docs": [{"name": "a", "text": SAFE_TEXT, "__proto__": marker}], "__proto__": marker},
            {"docs": [], "graph": {"__proto__": marker, "events": []}},
            {"docs": [], "key": "__proto__"},
        ]
        for index, payload in enumerate(bodies):
            with self.subTest(case=index):
                status, _ = self.api("/api/source", payload)
                self.assertNotEqual(status, "TRANSPORT", "原型污染载荷让服务断开连接")
                self.assertIn(status, (200, 400), "原型污染载荷返回意外状态" + self.evidence(case=index, actual=status))

        polluted = [name for name in ("JOBS", "PRESETS", "CAPS_MEM")
                    if sentinel in json.dumps(getattr(S, name, None), ensure_ascii=False, default=repr)]
        self.assertEqual(polluted, [], "原型污染载荷污染了模块级共享状态" + self.evidence(
            polluted=polluted, sentinel=sentinel,
            minimalRepro=('curl -s -X POST -H "Content-Type: application/json" '
                          '-d \'{"__proto__":{"polluted":true}}\' http://127.0.0.1:PORT/api/source')))
        stray = [p.name for p in self.cache_dir.glob("*proto*")]
        self.assertEqual(stray, [], "污染载荷在缓存目录留下了文件" + self.evidence(stray=stray))

    # ---------- 5 · 未授权访问 ----------

    def test_every_write_route_denies_foreign_origin_and_bad_host(self):
        """所有写路由在 foreign Origin / 错误 Host 下必须 403，且不得触发状态写入。"""
        routes = [("/api/source", {"docs": []}),
                  ("/api/source/rebuild", {"docs": []}),
                  ("/api/enrich/plan", {"key": "1234abcd", "sourceOnly": True}),
                  ("/api/enrich", {"key": "1234abcd", "sourceOnly": True}),
                  ("/api/cancel", {"job": "x"}),
                  ("/api/llm-config", {"action": "clear_history"}),
                  ("/api/history", {"action": "sweep"}),
                  ("/api/plan", {"docs": []})]
        self.cfg_save.reset_mock()
        for path, payload in routes:
            with self.subTest(path=path, attack="foreign-origin"):
                status, _ = self.api(path, payload, {"Origin": "https://attacker.example"})
                self.assertEqual(status, 403, "foreign Origin 未被拒" + self.evidence(
                    path=path, expected=403, actual=status,
                    minimalRepro=("curl -s -o /dev/null -w '%%{http_code}' -X POST "
                                  "-H 'Content-Type: application/json' -H 'Origin: https://attacker.example' "
                                  "-d '%s' http://127.0.0.1:PORT%s" % (json.dumps(payload), path))))
            with self.subTest(path=path, attack="cross-site-fetch"):
                status, _ = self.api(path, payload, {"Sec-Fetch-Site": "cross-site"})
                self.assertEqual(status, 403, "cross-site 请求未被拒" + self.evidence(path=path, actual=status))
            with self.subTest(path=path, attack="foreign-host"):
                status, _ = self.api(path, payload, {"Host": "attacker.example"})
                self.assertEqual(status, 403, "错误 Host 未被拒（DNS rebinding）" + self.evidence(path=path, actual=status))
        self.cfg_save.assert_not_called()

    def test_unknown_api_routes_and_method_confusion_are_rejected(self):
        for path in ("/api/nope", "/api/source/unknown", "/api/enrich/extra", "/api/health/secret",
                     "/api/source/rebuild/extra", "/api/cancel/extra", "/api/source/anchor/extra"):
            with self.subTest(path=path):
                status, _ = self.api(path, {"docs": []})
                self.assertEqual(status, 404, "未知 API 未被判 404" + self.evidence(path=path, actual=status))
                status, _ = self.raw("GET", path)
                self.assertEqual(status, 404, "未知 GET API 未被判 404" + self.evidence(path=path, actual=status))
        for path in ("/api/source", "/api/enrich", "/api/cancel", "/api/llm-config", "/api/history"):
            with self.subTest(path=path, method="PUT"):
                status, _ = self.raw("PUT", path, b"{}", [("Content-Type", "application/json")])
                self.assertIn(status, (404, 405, 501), "未实现的 HTTP 方法未被拒" + self.evidence(
                    path=path, method="PUT", actual=status))

    def test_absolute_form_targets_and_private_files_are_denied(self):
        """绝对形式请求行与私有路径不得触达 API 或源码。"""
        for target in ("http://attacker.example/api/history", "http://127.0.0.1:%d/api/history" % self.port,
                       "//attacker.example/api/history", "http://attacker.example/serve.py",
                       "http://[invalid/api/history", "/serve.py", "/README.md", "/data/llm-config.json",
                       "/data/cache/index.json", "/data/cache/1234abcd.docs.json", "/data/", "/tests/",
                       "/.git/config"):
            with self.subTest(target=target):
                status, body = self.raw("GET", target)
                self.assertIn(status, (404, 400), "目标未被拒" + self.evidence(
                    target=target, expected="404/400", actual=status,
                    body=body[:160].decode("utf-8", "replace"),
                    minimalRepro=("printf 'GET %s HTTP/1.1\\r\\nHost: 127.0.0.1:PORT\\r\\n\\r\\n' | nc 127.0.0.1 PORT"
                                  % target)))
                self.assertNotIn(b"DATA_SAFETY_SENTINEL", body)
                self.assertNotIn(b"internal source fixture", body)

    # ---------- 6 · SSRF ----------

    def test_base_url_normalization_never_invents_a_scheme(self):
        """规范化只剥离已知后缀与补 /v1，不得凭空改写 scheme 或主机。"""
        self.assertEqual(S.normalize_base_url("http://127.0.0.1:9999/v1/chat/completions", "openai"),
                         "http://127.0.0.1:9999/v1")
        self.assertEqual(S.normalize_base_url("http://127.0.0.1:9999/v1", "anthropic"),
                         "http://127.0.0.1:9999")
        self.assertEqual(S.normalize_base_url("", "openai"), "")
        for hostile in ("file:///etc/passwd", "gopher://127.0.0.1:11211/_x", "javascript:alert(1)",
                        "ftp://example.com", "data:text/plain,hello"):
            with self.subTest(url=hostile):
                normalized = S.normalize_base_url(hostile, "openai")
                self.assertFalse(normalized.startswith(("http://", "https://")),
                                 "敌意 scheme 被规范化成了 http(s) 地址" + self.evidence(
                                     input=hostile, normalized=normalized))

    def test_model_routes_report_failure_without_a_usable_profile(self):
        """没有可用档案时，需要网络的模型路由必须失败，不得回落到默认地址。"""
        for payload in ({"action": "models", "id": "missing", "base_url": ""},
                        {"action": "test", "id": "missing"}):
            with self.subTest(payload=payload):
                status, body = self.api("/api/llm-config", payload, {"Origin": self.origin})
                self.assertIn(status, (200, 400, 404), "模型路由返回意外状态" + self.evidence(
                    payload=payload, actual=status, body=body[:200].decode("utf-8", "replace")))
                self.assertIsNot(json.loads(body).get("ok"), True,
                                 "无档案时模型路由报告成功——可能是回落到默认地址" + self.evidence(body=body[:300]))

    # ---------- 7 · 已知缺陷（冻结签名） ----------

    def test_known_defect_lone_surrogate_drops_the_connection(self):
        """已知缺陷 P11-DS-02：孤立代理项通过 json.loads，却在 sha256 时抛 UnicodeEncodeError。

        正确行为是 400；当前会直接断开连接。缺陷仍在 → 打印横幅；已修好 → skip 并提示收紧。
        """
        dropped = []
        for case, body in (("surrogate-in-name", b'{"docs":[{"name":"\\ud800bad","text":"abc"}]}'),
                           ("surrogate-in-text", b'{"docs":[{"name":"a","text":"\\ud800abc"}]}'),
                           ("surrogate-in-path", b'{"docs":[{"name":"a","text":"abc","path":"\\ud800"}]}')):
            status, detail = self.api("/api/source", raw_body=body)
            if status == "TRANSPORT":
                dropped.append({"case": case, "detail": str(detail)[:120]})
            else:
                self.assertIn(status, (200, 400), "孤立代理项返回意外状态" + self.evidence(
                    case=case, actual=status, rawBytes=repr(body)))
        if not KNOWN_DEFECTS["lone_surrogate_drops_connection"]:
            if dropped:
                self.fail("基线说该缺陷已修复，但仍能复现——基线过期" + self.evidence(reproduced=dropped))
            return
        if not dropped:
            self.skipTest("已知缺陷 P11-DS-02 已修复（孤立代理项不再断开连接）；"
                          "请更新 KNOWN_DEFECTS 与 ledger 的 knownGaps 收紧基线")
        self.defect_banner(
            "P11-DS-02", "孤立代理项让连接被直接关闭（应为 400 Invalid JSON）",
            "触发点：serve.py source_specs() 中 raw.encode('utf-8') / sha1(...).encode('utf-8')；"
            "json.loads 接受 \\ud800，随后 UnicodeEncodeError 未被捕获。复现用例：%s" % [d["case"] for d in dropped],
            "python3 tests/data_safety_contract.py -k lone_surrogate")
        self.assertEqual(len(dropped), 3, "缺陷面发生变化" + self.evidence(dropped=dropped))

    def test_known_defect_deep_nesting_boundary_does_not_regress(self):
        """已知缺陷 P11-DS-01：JSON 嵌套超过冻结深度时 RecursionError 断开连接。

        只允许「变好」（在更深的嵌套上仍返回 200）。边界**前移**即 fail。
        """
        frozen = KNOWN_DEFECTS["deep_nesting_crash_depth"]
        probe = frozen - 11
        status, _ = self.api("/api/source", raw_body=("{\"a\":" * probe + "1" + "}" * probe).encode())
        self.assertEqual(status, 200, "冻结阈值之内就崩了——缺陷恶化（边界前移）" + self.evidence(
            depth=probe, frozenCrashDepth=frozen, actual=status,
            minimalRepro=("python3 -c \"import json;print(json.loads('{\\\"a\\\":'*%d+'1'+'}'*%d))\""
                          % (probe, probe))))
        beyond = frozen + 5000
        status, detail = self.api("/api/source", raw_body=("{\"a\":" * beyond + "1" + "}" * beyond).encode())
        if status != "TRANSPORT":
            self.assertEqual(
                status, 400,
                "超深嵌套应返回 400 Invalid JSON（修复后不得断连、也不得其它码）"
                + self.evidence(depth=beyond, actual=status, detail=str(detail)[:200],
                                minimalRepro="删掉 serve.py 的 except RecursionError 应使本用例变红"))
            return
        if not KNOWN_DEFECTS.get("_deep_nesting_pin_active", False):
            self.fail(
                "基线声明 P11-DS-01 已修，但超深嵌套仍断开连接（status=%r）"
                "—— 修复被回退，或 KNOWN_DEFECTS 标志过期" % (status,)
                + self.evidence(depth=beyond, actual=status, detail=str(detail)[:200],
                                minimalRepro="检查 serve.py do_POST 是否仍有 except RecursionError"))
        self.defect_banner(
            "P11-DS-01", "深嵌套 JSON 触发 RecursionError 并断开连接（应为 400 Invalid JSON）",
            "实测崩溃边界约 %d 层；body 仅约 60KB，远小于 MAX_BODY_BYTES=64MB 的总量限制，"
            "因此总量门禁拦不住它。" % frozen,
            "curl -s -X POST --data-binary @deep.json -H 'Content-Type: application/json' http://127.0.0.1:PORT/api/source")

    def test_known_defect_ssrf_file_scheme_is_reachable(self):
        """已知缺陷 P11-DS-03：base_url 允许 file://，urlopen 会读本地文件并回传内容。

        这里用一个临时目录里的哨兵文件做**受控**复现：不触碰真实私有文件，
        只证明 scheme 未受限。缺陷仍在 → 打印横幅；已修好 → skip 并提示收紧。
        """
        if not KNOWN_DEFECTS["ssrf_file_scheme_reachable"]:
            import serve as _S
            for bad in ("file://" + str(self.folder), "ftp://x/y",
                        "data:text/plain,hi", "gopher://x", "dict://x"):
                with self.subTest(scheme=bad.split(":")[0]):
                    self.assertEqual(
                        _S.normalize_base_url(bad), "",
                        f"{bad!r} 应被 scheme 白名单拒绝（返回空串），"
                        f"否则 urlopen 会读本地文件（SSRF）")
            for good, want in (("https://api.openai.com", "https://api.openai.com/v1"),
                               ("http://127.0.0.1:8765/v1", "http://127.0.0.1:8765/v1")):
                with self.subTest(keep=good):
                    self.assertEqual(_S.normalize_base_url(good), want,
                                     "scheme 白名单不得误伤 http/https")
            leak_dir = self.folder / "leakdir"
            leak_dir.mkdir(exist_ok=True)
            sentinel = "SSRF_SENTINEL_P11"
            (leak_dir / "models").write_text(
                json.dumps({"data": [{"id": sentinel}]}), encoding="utf-8")
            profile = {"id": "p1", "name": "p", "kind": "openai",
                       "base_url": "file://" + str(leak_dir), "model": "m", "api_key": "k"}
            with contextlib.ExitStack() as inner:
                inner.enter_context(patch.object(S, "cfg_load",
                                                 return_value={"profiles": [profile],
                                                               "current": "p1", "history": []}))
                inner.enter_context(patch.object(S, "current", return_value=profile))
                inner.enter_context(patch.object(S.urllib.request, "urlopen",
                                                 side_effect=_REAL_URLOPEN))
                status, body = self.api("/api/llm-config",
                                        {"action": "models", "id": "p1"},
                                        {"Origin": self.origin})
            self.assertNotIn(sentinel, body.decode("utf-8", "replace"),
                             "SSRF 已修但端到端仍读到了哨兵 —— 修复未生效")
            return
        leak_dir = self.folder / "leakdir"
        leak_dir.mkdir(exist_ok=True)
        sentinel = "SSRF_SENTINEL_P11"
        (leak_dir / "models").write_text(json.dumps({"data": [{"id": sentinel}]}), encoding="utf-8")
        profile = {"id": "p1", "name": "p", "kind": "openai",
                   "base_url": "file://" + str(leak_dir), "model": "m", "api_key": "k"}
        with contextlib.ExitStack() as inner:
            inner.enter_context(patch.object(S, "cfg_load",
                                             return_value={"profiles": [profile], "current": "p1", "history": []}))
            inner.enter_context(patch.object(S, "current", return_value=profile))
            inner.enter_context(patch.object(S.urllib.request, "urlopen", side_effect=_REAL_URLOPEN))
            status, body = self.api("/api/llm-config", {"action": "models", "id": "p1"}, {"Origin": self.origin})
        text = body.decode("utf-8", "replace")
        if sentinel not in text:
            self.fail("受控 SSRF 复现既没有读到哨兵、也没有给出明确拒绝理由——"
                      "复现路径失效，无法判断缺陷是否仍在\n" + self.evidence(
                          status=status, response=text[:400], sentinel=sentinel,
                          minimalRepro="python3 tests/data_safety_contract.py -k ssrf_file_scheme"))
        self.defect_banner(
            "P11-DS-03", "模型接入地址允许 file:// scheme，可读取并回传本地文件",
            "normalize_base_url 只做后缀归一，不校验 scheme；list_models() 用 "
            "base + '/models' 直接 urlopen。受控复现：把 base_url 指向一个含 models 文件的目录，"
            "哨兵内容 %r 出现在 /api/llm-config 的响应里。" % sentinel,
            "python3 tests/data_safety_contract.py -k ssrf_file_scheme")
        self.assertEqual(status, 200)
        self.assertIn(sentinel, text, "缺陷复现方式失效，请更新本测试的受控复现")

    def test_server_survives_every_hostile_request_in_this_suite(self):
        """跑完整套敌意输入后，服务必须仍然可用（无不可恢复崩溃）。"""
        for body in (b"{broken", b"\xff\xfe", b"[" * 3000,
                     b'{"docs":[{"name":"\\ud800","text":"x"}]}',
                     ("{\"a\":" * 12000 + "1" + "}" * 12000).encode(),
                     json.dumps({"docs": [{"name": "x" * 100000, "text": "y"}]}).encode()):
            self.api("/api/source", raw_body=body)
        status, body = self.raw("GET", "/api/health")
        self.assertEqual(status, 200, "敌意输入后服务不可用——不可恢复崩溃" + self.evidence(
            actual=status, body=body[:200].decode("utf-8", "replace"),
            minimalRepro="python3 tests/data_safety_contract.py"))
        self.assertTrue(json.loads(body)["ok"])



class HistoryRetentionContract(unittest.TestCase):
    """Library cleanup must preserve completed versions and their original docs."""

    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.folder = Path(self.stack.enter_context(
            tempfile.TemporaryDirectory(prefix="castline-history-retention-")))
        self.hist = self.folder / "index.json"
        self.stack.enter_context(patch.object(S, "CACHE_DIR", str(self.folder)))
        self.stack.enter_context(patch.object(S, "HIST_PATH", str(self.hist)))

    def save_version(self, key, indexed=False):
        graph = {"title": "saved version", "characters": [], "events": [],
                 "meta": {"revision": {"parentKey": "1234abcd"}}}
        graph_path = self.folder / (key + ".json")
        docs_path = self.folder / (key + ".docs.json")
        graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        docs_path.write_text('[{"name":"original","text":"保留原文。"}]', encoding="utf-8")
        if indexed:
            S.history_add(key, graph, 5, 1)
        return {graph_path: graph_path.read_bytes(), docs_path: docs_path.read_bytes()}

    def test_more_than_eighty_versions_remain_in_the_persistent_library(self):
        oldest = self.save_version("00000000", indexed=True)
        S.history_patch("00000000", {"pinned": True, "note": "oldest user note"})
        S.history_open("00000000")
        for i in range(1, 81):
            self.save_version("%08x" % i, indexed=True)
        rows = S._hist_raw()
        self.assertEqual(len(rows), 81, "历史显示上限不能截断永久作品索引")
        row = next(x for x in rows if x["key"] == "00000000")
        self.assertTrue(row["pinned"])
        self.assertEqual(row["note"], "oldest user note")
        self.assertEqual(row["opens"], 1)
        self.assertEqual(len(S.history_list()), 81)
        self.assertEqual(S.history_sweep(), [])
        for path, raw in oldest.items():
            self.assertEqual(path.read_bytes(), raw, "第81版不能使最早图谱或原文丢失")

    def test_sweep_preserves_unindexed_published_graph_and_original_docs(self):
        kept = self.save_version("deadbeef", indexed=False)
        kept.update(self.save_version("faceb00c", indexed=True))
        index_before = self.hist.read_bytes()
        self.assertEqual(S.history_sweep(), [])
        self.assertEqual(self.hist.read_bytes(), index_before)
        for path, raw in kept.items():
            self.assertEqual(path.read_bytes(), raw, "索引缺失不能证明图谱或原文可删除")

    def test_sweep_removes_only_docs_without_a_graph_and_is_idempotent(self):
        kept = self.save_version("deadbeef", indexed=False)
        orphan = self.folder / "0000abcd.docs.json"
        orphan.write_text('[{"text":"orphan material"}]', encoding="utf-8")
        unrelated = self.folder / "analysis-notes.json"
        unrelated.write_text('{"keep":true}', encoding="utf-8")
        kept[unrelated] = unrelated.read_bytes()
        self.assertEqual(S.history_sweep(), [orphan.name])
        self.assertFalse(orphan.exists())
        self.assertEqual(S.history_sweep(), [])
        for path, raw in kept.items():
            self.assertEqual(path.read_bytes(), raw)

    def test_explicit_delete_still_removes_only_the_requested_version(self):
        deleted = self.save_version("deadbeef", indexed=True)
        kept = self.save_version("faceb00c", indexed=True)
        S.history_delete("deadbeef")
        self.assertTrue(all(not p.exists() for p in deleted))
        self.assertEqual([x["key"] for x in S._hist_raw()], ["faceb00c"])
        for path, raw in kept.items():
            self.assertEqual(path.read_bytes(), raw)

def print_report():
    """Print baseline status only; this mode does not execute runtime probes."""
    def state(flag_name):
        value = KNOWN_DEFECTS.get(flag_name)
        if value is None:
            return "待判（无布尔基线）"
        return "冻结缺口（flag=True）" if value else "已修（flag=False；本摘要未做运行时测量）"

    print("DATA SAFETY CONTRACT · 基线状态声明（--report 不执行运行时探测）")
    print("  cache_key 接受范围      : 8-40 位 [0-9a-f]，首尾空白先 strip")
    print("  私有路径白名单          : /serve.py /README.md /data/... /tests/ /.git/ 一律 404")
    print("  写路由未授权            : foreign Origin / bad Host / cross-site → 403")
    depth = KNOWN_DEFECTS.get("deep_nesting_crash_depth")
    if isinstance(depth, int):
        print("  P11-DS-01 深层 JSON     : 待判（冻结回归阈值 %d 层；需运行完整契约）" % depth)
    else:
        print("  P11-DS-01 深层 JSON     : 待判（缺少冻结阈值）")
    print("  P11-DS-02 孤立代理项    : %s" % state("lone_surrogate_drops_connection"))
    print("  P11-DS-03 file:// SSRF  : %s" % state("ssrf_file_scheme_reachable"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P11 数据安全契约")
    parser.add_argument("--report", action="store_true", help="只打印探测摘要与已知缺陷")
    args = parser.parse_args()
    if args.report:
        print_report()
    else:
        unit = unittest.main(verbosity=2, exit=False)
        sys.exit(0 if unit.result.wasSuccessful() else 1)
