#!/usr/bin/env python3
"""Real HTTP boundaries, temporary public tree, no user data or model calls."""
import contextlib
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve as S


class HttpBoundaryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.folder = Path(cls.stack.enter_context(tempfile.TemporaryDirectory(prefix="castline-http-")))
        files = {
            "index.html": "<!doctype html><title>offline fixture</title>",
            "js/app.js": "window.offlineFixture = true;",
            "css/app.css": "body { color: white; }",
            "assets/icon.svg": "<svg xmlns='http://www.w3.org/2000/svg'/>",
            "fonts/body.woff2": "offline font fixture",
            "tests/app-probes.js": "window.offlineProbe = true;",
            "tests/app-scale.js": "window.offlineScale = true;",
            "tests/atlas_fallback_harness.html": "<!doctype html><title>fixture</title>",
            "tests/secret_contract.py": "internal source fixture",
            "serve.py": "internal source fixture",
            "README.md": "internal documentation fixture",
            ".git/config": "private fixture",
            "data/llm-config.json": '{"profiles":[{"api_key":"OFFLINE_SENTINEL"}]}',
            "data/cache/index.json": "[]",
            "data/cache/1234abcd.docs.json": '[{"text":"private prose fixture"}]',
            "data/cache/chunks/1234abcd.json": '{"private":"intermediate"}',
            "data/cache/89abcdef.json": '{"private":"not a graph"}',
            "docs/reports/private.log": "internal log fixture",
            "js/private.map": "internal source map fixture",
            "data/demo_src/星尘信使/角色设定.md": "public authored sample fixture",
        }
        graph = json.dumps({"title": "Offline graph", "characters": [], "events": []})
        files.update({"data/demo.json": graph, "data/sample-saga.json": graph,
                      "data/cache/1234abcd.json": graph})
        for name, text in files.items():
            path = cls.folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        (cls.folder / "js/private.js").symlink_to(cls.folder / "data/llm-config.json")
        cls.stack.enter_context(patch.object(S, "ROOT", str(cls.folder)))
        cls.stack.enter_context(patch.object(S, "CACHE_DIR", str(cls.folder / "data/cache")))
        cls.stack.enter_context(patch.object(S, "HIST_PATH", str(cls.folder / "data/cache/index.json")))
        cls.stack.enter_context(patch.object(S, "JOBS", {}))
        cls.stack.enter_context(patch.object(S, "cfg_load", return_value={"profiles": [], "current": "", "history": []}))
        cls.cfg_save = cls.stack.enter_context(patch.object(S, "cfg_save"))
        cls.stack.enter_context(patch.object(S, "current", return_value=None))
        cls.stack.enter_context(patch.object(S, "cfg_history"))
        cls.stack.enter_context(patch.object(S, "history_list", return_value=[]))
        cls.stack.enter_context(patch.object(S, "run_job", side_effect=AssertionError("MODEL CALL FORBIDDEN")))
        cls.stack.enter_context(patch.object(S, "run_distill", side_effect=AssertionError("MODEL CALL FORBIDDEN")))
        cls.stack.enter_context(patch.object(S.urllib.request, "urlopen", side_effect=AssertionError("EXTERNAL NETWORK FORBIDDEN")))

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

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        self.addCleanup(conn.close)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()

    def raw_request(self, method, path, headers, body=b""):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        self.addCleanup(conn.close)
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for name, value in headers:
            conn.putheader(name, value)
        conn.endheaders(body)
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()

    def json_request(self, path="/api/source", body=None, headers=None):
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        return self.request("POST", path, json.dumps(body or {"docs": []}).encode(), h)

    def test_private_files_and_directories_are_not_public(self):
        for path in ("/data/llm-config.json", "/data/cache/index.json", "/data/cache/1234abcd.docs.json",
                     "/data/cache/chunks/1234abcd.json", "/docs/reports/private.log", "/serve.py",
                     "/README.md", "/.git/config", "/js/private.map", "/tests/secret_contract.py",
                     "/data/", "/data/cache/", "/js/", "/tests/"):
            with self.subTest(path=path):
                status, _, body = self.request("GET", path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"OFFLINE_SENTINEL", body)

    def test_graph_samples_and_completed_cache_graphs_remain_readable(self):
        for path in ("/data/demo.json", "/data/sample-saga.json", "/data/cache/1234abcd.json"):
            with self.subTest(path=path):
                status, headers, body = self.request("GET", path)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["title"], "Offline graph")
                self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.request("GET", "/data/cache/89abcdef.json")[0], 404)

    def test_encoded_traversal_and_symlink_aliases_are_denied(self):
        for path in ("/js/../serve.py", "/js/%2e%2e/serve.py", "/js/%2E%2E%2Fdata/llm-config.json",
                     "/js/%5c../serve.py", "/js/app.js%00", "/js/%ff.js", "/js/%nothex.js", "/js/private.js"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 404)

    def test_exact_browser_regression_assets_and_authored_sample_are_available(self):
        for path in ("/tests/app-probes.js", "/tests/app-scale.js", "/tests/atlas_fallback_harness.html",
                     "/assets/icon.svg", "/fonts/body.woff2"):
            self.assertEqual(self.request("GET", path)[0], 200, path)
        from urllib.parse import quote
        self.assertEqual(self.request("GET", quote("/data/demo_src/星尘信使/角色设定.md"))[0], 200)

    def test_head_has_the_same_static_boundary_and_no_response_body(self):
        for path, expected in (("/data/llm-config.json", 404), ("/js/private.js", 404),
                               ("/data/cache/1234abcd.json", 200), ("/index.html", 200)):
            status, _, body = self.request("HEAD", path)
            self.assertEqual(status, expected)
            self.assertEqual(body, b"")
        status, _, body = self.request("HEAD", "/index.html", headers={"Host": "attacker.example"})
        self.assertEqual(status, 403)
        self.assertEqual(body, b"")

    def test_only_correct_content_hash_assets_are_cached_immutably(self):
        digest = hashlib.sha256((self.folder / "js/app.js").read_bytes()).hexdigest()[:8]
        for path, immutable in (("/js/app.js?v=" + digest, True), ("/js/app.js?v=deadbeef", False),
                                ("/js/app.js", False), ("/css/app.css?v=no-hash", False)):
            status, headers, _ = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertEqual("immutable" in headers["Cache-Control"], immutable)
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        for path in ("/", "/index.html?v=" + digest, "/api/history"):
            self.assertEqual(self.request("GET", path)[1]["Cache-Control"], "no-store")

    def test_changed_asset_does_not_reuse_old_hash_cache(self):
        path = self.folder / "js/update.js"
        path.write_text("first", encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        self.assertIn("immutable", self.request("GET", "/js/update.js?v=" + digest)[1]["Cache-Control"])
        path.write_text("a changed fixture", encoding="utf-8")
        self.assertNotIn("immutable", self.request("GET", "/js/update.js?v=" + digest)[1]["Cache-Control"])

    def test_loopback_host_and_exact_listener_port_are_required(self):
        for host in ("attacker.example:%d" % self.port, "127.0.0.1:1", "localhost.evil:%d" % self.port,
                     "user@127.0.0.1:%d" % self.port, "127.0.0.1:%d/path" % self.port):
            with self.subTest(host=host):
                self.assertEqual(self.request("GET", "/api/history", headers={"Host": host})[0], 403)
        for host in ("localhost:%d" % self.port, "127.0.0.1:%d" % self.port, "[::1]:%d" % self.port):
            self.assertEqual(self.request("GET", "/", headers={"Host": host})[0], 200)
        self.assertEqual(self.raw_request("GET", "/", [])[0], 403)
        self.assertEqual(self.raw_request("GET", "/", [("Host", "127.0.0.1:%d" % self.port),
                                                      ("Host", "attacker.example")])[0], 403)

    def test_same_origin_browser_and_originless_cli_requests_work(self):
        for headers in ({}, {"Origin": self.origin, "Sec-Fetch-Site": "same-origin"},
                        {"Origin": "http://localhost:%d" % self.port, "Host": "localhost:%d" % self.port}):
            status, response_headers, body = self.json_request(headers=headers)
            self.assertEqual(status, 200)
            self.assertIn("application/json", response_headers["Content-Type"])
            self.assertIsInstance(json.loads(body), dict)

    def test_llm_config_actions_reject_bad_types_before_config_or_network_access(self):
        good = {"id": "offline-profile", "name": "offline", "kind": "openai",
                "base_url": "http://127.0.0.1:9/v1", "model": "offline-model", "api_key": "offline-key"}
        cases = []
        for action in ("test", "models"):
            bad_url = dict(good, action=action, base_url={"bad": 1})
            bad_key = dict(good, action=action, api_key=7)
            cases.extend(((action + " object base_url", bad_url), (action + " integer api_key", bad_key)))
        cases.append(("object action", dict(good, action={"bad": 1})))
        for field in ("id", "name", "kind", "base_url", "model", "api_key"):
            cases.append(("non-string " + field, dict(good, action="test", **{field: ["bad"]})))

        with patch.object(S, "cfg_load", side_effect=AssertionError("CONFIG READ FORBIDDEN")) as cfg_load, \
                patch.object(S, "list_models", side_effect=AssertionError("MODEL LIST NETWORK FORBIDDEN")) as list_models, \
                patch.object(S, "llm_test", side_effect=AssertionError("LLM TEST FORBIDDEN")) as llm_test:
            self.cfg_save.reset_mock()
            for label, body in cases:
                with self.subTest(case=label):
                    status, headers, response = self.json_request("/api/llm-config", body)
                    self.assertEqual(status, 400, label)
                    self.assertIn("application/json", headers["Content-Type"])
                    self.assertIn("error", json.loads(response))
            cfg_load.assert_not_called()
            list_models.assert_not_called()
            llm_test.assert_not_called()
            self.cfg_save.assert_not_called()

    def test_valid_llm_config_test_and_models_actions_keep_their_mocked_paths(self):
        payload = {"base_url": "http://127.0.0.1:9/v1", "model": "offline-model", "api_key": "offline-key"}
        with patch.object(S, "list_models", return_value={"ok": True, "models": ["offline-model"]}) as list_models, \
                patch.object(S, "llm_test", return_value={"ok": True, "reply": "OK"}) as llm_test:
            status, _, response = self.json_request("/api/llm-config", dict(payload, action="models"))
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(response)["models"], ["offline-model"])
            list_models.assert_called_once()
            llm_test.assert_not_called()

            list_models.reset_mock()
            llm_test.reset_mock()
            status, _, response = self.json_request("/api/llm-config", dict(payload, action="test"))
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(response), {"ok": True, "reply": "OK"})
            llm_test.assert_called_once()
            list_models.assert_not_called()
        self.cfg_save.assert_not_called()

    def test_foreign_origin_and_cross_site_requests_cannot_reach_writes(self):
        self.cfg_save.reset_mock()
        for headers in ({"Origin": "https://attacker.example"}, {"Origin": "null"},
                        {"Origin": "http://127.0.0.1:1"}, {"Origin": self.origin + "/path"},
                        {"Origin": "http://localhost:%d" % self.port},
                        {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.json_request("/api/llm-config", {"action": "clear_history"}, headers)[0], 403)
        self.cfg_save.assert_not_called()
        self.assertEqual(self.json_request("/api/llm-config", {"action": "clear_history"}, {"Origin": self.origin})[0], 200)
        self.cfg_save.assert_called_once()

    def test_non_json_bodies_and_api_prefix_lookalikes_are_rejected(self):
        for content_type in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
            self.assertEqual(self.request("POST", "/api/source", b"{}", {"Content-Type": content_type})[0], 415)
        self.assertEqual(self.request("POST", "/api/source", b"{}")[0], 415)
        for path in ("/api/llm-config-extra", "/api/source/unknown", "/api/analyze-extra"):
            self.assertEqual(self.json_request(path)[0], 404)
        self.assertEqual(self.request("GET", "/api/llm-config-extra")[0], 404)
        for path in ("http://attacker.example/api/history", "http://[invalid/api/history"):
            headers = {"Host": "127.0.0.1:%d" % self.port}
            self.assertEqual(self.request("GET", path, headers=headers)[0], 404)
            self.assertEqual(self.json_request(path, headers=headers)[0], 404)

    def test_invalid_framing_and_oversized_body_rejected_before_read(self):
        base = [("Host", "127.0.0.1:%d" % self.port), ("Content-Type", "application/json")]
        cases = [([], 411), ([("Content-Length", "-1")], 400), ([("Content-Length", "abc")], 400),
                 ([("Content-Length", "2"), ("Content-Length", "2")], 400),
                 ([("Content-Length", "9999999999999999999999999")], 400),
                 ([("Content-Length", str(S.Handler.MAX_BODY_BYTES + 1))], 413),
                 ([("Content-Length", "2"), ("Transfer-Encoding", "chunked")], 400)]
        for extra, expected in cases:
            with self.subTest(extra=extra):
                self.assertEqual(self.raw_request("POST", "/api/source", base + extra)[0], expected)
        for path, limit in (("/api/llm-config", 256 * 1024), ("/api/history", 64 * 1024), ("/api/cancel", 64 * 1024)):
            self.assertEqual(self.raw_request("POST", path, base + [("Content-Length", str(limit + 1))])[0], 413)

    def test_malformed_json_and_non_object_json_have_clear_errors(self):
        for body in (b"{broken", b"\xff", b"[]", b"null", b'"string"'):
            status, headers, response = self.request("POST", "/api/source", body, {"Content-Type": "application/json"})
            self.assertEqual(status, 400)
            self.assertIn("application/json", headers["Content-Type"])
            self.assertIn("error", json.loads(response))

    def test_new_source_rebuild_and_enrichment_plan_are_zero_model_http_routes(self):
        graph = {"characters": [], "events": [{"id": "event-fixed", "order": 1,
                  "quote": "北辰推开古塔的门。", "title": "推门", "summary": "进入古塔"}]}
        docs = [{"name": "原文", "text": "北辰推开古塔的门。"}]
        status, _, body = self.json_request("/api/source/rebuild", {"graph": graph, "docs": docs})
        self.assertEqual(status, 200)
        value = json.loads(body)
        self.assertEqual(value["calls"], 0)
        self.assertFalse(value["persisted"])
        self.assertTrue(value["graph"]["events"][0]["quoteRef"]["verified"])
        status, _, body = self.json_request("/api/enrich/plan", {"key": "1234abcd", "sourceOnly": True})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["estimatedCalls"], 0)
        self.assertEqual(self.json_request("/api/enrich/plan", {"key": "../llm-config"})[0], 400)
        self.assertEqual(self.json_request("/api/enrich", {"key": "../llm-config"})[0], 400)
        self.assertEqual(self.json_request("/api/enrich", {"key": "1234abcd"}, {"Origin": "https://attacker.example"})[0], 403)

    def test_source_only_enrichment_uses_real_sse_and_preserves_original(self):
        original = (self.folder / "data/cache/1234abcd.json").read_bytes()
        with patch.object(S, "call_llm", side_effect=AssertionError("MODEL FORBIDDEN")) as model:
            status, headers, body = self.json_request("/api/enrich", {"key": "1234abcd", "sourceOnly": True})
        self.assertEqual(status, 200)
        self.assertIn("text/event-stream", headers["Content-Type"])
        self.assertIn(b"event: hello", body)
        self.assertIn(b"event: done", body)
        self.assertNotIn(b"event: error", body)
        self.assertEqual((self.folder / "data/cache/1234abcd.json").read_bytes(), original)
        model.assert_not_called()
        self.assertEqual(self.request("GET", "/data/cache/narrative/revisions/")[0], 404)


    def test_history_field_shapes_are_rejected_before_any_library_write(self):
        cases = [
            {"action": "rename", "key": "1234abcd", "title": ["bad"]},
            {"action": "rename", "key": "1234abcd", "title": False},
            {"action": "note", "key": "1234abcd", "note": {"bad": 1}},
            {"action": "pin", "key": "1234abcd", "pinned": "false"},
            {"action": ["delete"], "key": "1234abcd"},
            {"action": "delete", "key": {"bad": 1}},
        ]
        with patch.object(S, "history_patch") as write, patch.object(S, "history_delete") as delete:
            for body in cases:
                with self.subTest(body=body):
                    status, _, raw = self.json_request("/api/history", body)
                    self.assertEqual(status, 400)
                    self.assertIn("error", json.loads(raw))
            write.assert_not_called()
            delete.assert_not_called()
            self.assertEqual(self.json_request("/api/history", {"action": "rename", "key": "1234abcd", "title": "新标题"})[0], 200)
            self.assertEqual(self.json_request("/api/history", {"action": "note", "key": "1234abcd", "note": "注释"})[0], 200)
            self.assertEqual(self.json_request("/api/history", {"action": "pin", "key": "1234abcd", "pinned": False})[0], 200)
            self.assertEqual(write.call_count, 3)

    def test_source_routes_never_turn_invalid_json_field_shapes_into_prose(self):
        cases = [
            ("/api/source", {"docs": None}),
            ("/api/source", {"docs": {"text": "abc"}}),
            ("/api/source", {"docs": ["abc"]}),
            ("/api/source", {"docs": [{"text": {"bad": 1}}]}),
            ("/api/source", {"docs": [{"name": ["bad"], "text": "abc"}]}),
            ("/api/source", {"graph": []}),
            ("/api/source/anchor", {"quote": {"bad": 1}, "text": "abc"}),
            ("/api/source/anchor", {"quote": "a", "text": ["abc"]}),
            ("/api/source/anchor", {"quote": "a", "text": "abc", "sourceId": []}),
            ("/api/source/rebuild", {"key": "1234abcd", "graph": ["bad"]}),
            ("/api/source/rebuild", {"key": ["1234abcd"]}),
        ]
        with patch.object(S, "source_specs", wraps=S.source_specs) as specs, patch.object(S, "source_anchor", wraps=S.source_anchor) as anchor, patch.object(S, "_enrichment_inputs", wraps=S._enrichment_inputs) as read_saved:
            for path, body in cases:
                with self.subTest(path=path, body=body):
                    status, _, raw = self.json_request(path, body)
                    self.assertEqual(status, 400)
                    self.assertIn("error", json.loads(raw))
            specs.assert_not_called()
            anchor.assert_not_called()
            read_saved.assert_not_called()
        status, _, raw = self.json_request("/api/source/anchor", {"text": "甲乙丙丁戊己庚辛", "quote": "乙丙丁戊己庚"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw)["verified"])
        status, _, raw = self.json_request("/api/source", {"docs": [{"name": "原文", "text": "abc"}]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["chars"], 3)

    def test_invalid_cancel_identifier_cannot_mean_cancel_every_running_job(self):
        from unittest.mock import Mock
        first, other = Mock(), Mock()
        for key, job in (("safe-first", first), ("safe-other", other)):
            job.key, job.finished, job.cancelled = key, False, False
            job.cancel.return_value = True
        with patch.object(S, "JOBS", {"safe-first": first, "safe-other": other}), patch.object(S, "jobs_list", return_value=[]):
            for value in ([], {}, False, 0, ["safe-first"]):
                with self.subTest(value=value):
                    status, _, raw = self.json_request("/api/cancel", {"job": value})
                    self.assertEqual(status, 400)
                    self.assertIn("error", json.loads(raw))
            first.cancel.assert_not_called()
            other.cancel.assert_not_called()
            status, _, raw = self.json_request("/api/cancel", {"job": "safe-first"})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)["cancelled"], ["safe-first"])
            first.cancel.assert_called_once()
            other.cancel.assert_not_called()
            first.reset_mock()
            status, _, raw = self.json_request("/api/cancel", {"job": ""})
            self.assertEqual(status, 200)
            self.assertEqual(set(json.loads(raw)["cancelled"]), {"safe-first", "safe-other"})
            first.cancel.assert_called_once()
            other.cancel.assert_called_once()

    def test_security_summary_does_not_present_fixed_boundaries_as_current_exploits(self):
        import data_safety_contract as data_safety
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            data_safety.print_report()
        text = buf.getvalue()
        self.assertIn("声明", text)
        self.assertIn("P11-DS-01", text)
        self.assertIn("P11-DS-02", text)
        self.assertIn("P11-DS-03", text)
        if not data_safety.KNOWN_DEFECTS["lone_surrogate_drops_connection"]:
            self.assertNotIn("encode('utf-8') 抛 UnicodeEncodeError → 连接断开", text)
        if not data_safety.KNOWN_DEFECTS["ssrf_file_scheme_reachable"]:
            self.assertNotIn("base_url 允许 file://", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
