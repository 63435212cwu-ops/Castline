#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P12 · 发布门禁负向对照（自检）。

门禁只有在**该拦的时候真的拦**才有意义。本脚本用临时台账跑负向对照，
证明 release_gate 的每一条规则都不是装饰：

  1. 完全合规的台账                → 必须 PASS
  2. status != merged              → 必须拦
  3. knownGaps 为空且无证据        → 必须拦（"没发现问题" "没检查" 不可区分）
  4. reviewer 缺失                 → 必须拦
  5. reviewer == owner（自我签收） → 必须拦，且计 P0
  6. status=merged 但字段缺失      → 必须拦，且计 P0
  7. ledger 结构不可识别           → 必须拦（不跳过），且计 P0
  8. 证据路径指向不存在的文件      → 必须拦

临时台账写在 tempdir 里，**不触碰** artifacts/plan100 下的真实台账。
用法：python3 tools/plan100/release_gate_selftest.py
退出码：0 = 全部符合预期；1 = 门禁行为与文档不符。
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import contextlib
import copy
import io
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_gate as G
import release_manifest as M


def good_ledger() -> dict:
    return {
        "task": "SYN-W01",
        "status": "merged",
        "owner": "alice",
        "reviewer": "bob",
        "startedAt": "2026-10-07T00:00:00Z",
        "finishedAt": "2026-10-07T01:00:00Z",
        "inputHashes": [{"path": "f", "sha256": "x"}],
        "commands": [{"cmd": "true"}],
        "evidence": [{"path": "reports/ok.txt"}],
        "assertions": [{"text": "a", "result": "pass"}],
        "knownGaps": [],
        "rollback": {"patch": "p"},
        "decision": "merged",
    }


def build_case(root: Path, name: str, mutate, evidence_file: bool = True) -> Path:
    d = root / "20261007" / name
    (d / "reports").mkdir(parents=True, exist_ok=True)
    if evidence_file:
        (d / "reports" / "ok.txt").write_text("evidence", encoding="utf-8")
    led = good_ledger()
    mutate(led)
    (d / "ledger.json").write_text(json.dumps(led, ensure_ascii=False, indent=2), encoding="utf-8")
    return d / "ledger.json"


def audit(lp: Path, allow_self_review: bool = False) -> dict:
    return G.audit_ledger(lp, allow_self_review)


def has_blocker(rec: dict, needle: str) -> bool:
    return any(needle in (b.get("reason") or "") or needle in (b.get("rule") or "")
               for b in rec["blockers"])


CASES = []


def case(name, expect_blocked: bool, needle: str, mutate, evidence_file: bool = True,
         allow_self_review: bool = False, expect_p0: bool = False):
    CASES.append(dict(name=name, expect_blocked=expect_blocked, needle=needle,
                      mutate=mutate, evidence_file=evidence_file,
                      allow_self_review=allow_self_review, expect_p0=expect_p0))


case("合规台账必须放行", False, "", lambda d: None)
case("status != merged 必拦", True, "非 merged", lambda d: d.update(status="cpu-verified"))
case("knownGaps 空且无证据必拦", True, "没有可用证据",
     lambda d: d.update(evidence=[], knownGaps=[]))
case("reviewer 缺失必拦", True, "reviewer 缺失", lambda d: d.update(reviewer=None))
case("自我签收必拦且记 P0", True, "reviewer 与 owner 相同",
     lambda d: d.update(reviewer="alice"), expect_p0=True)
case("merged 但字段缺失必拦且记 P0", True, "必填签收字段缺失",
     lambda d: d.update(assertions=[]), expect_p0=True)
case("证据文件不存在必拦", True, "没有可用证据",
     lambda d: d.update(evidence=[{"path": "reports/does-not-exist.txt"}]), evidence_file=False)
case("--allow-self-review 下降级为告警", False, "reviewer 与 owner 相同",
     lambda d: d.update(reviewer="alice"), allow_self_review=True, expect_p0=False)


def manifest_cases(tmp: Path) -> list:
    """Release inputs/receipts own a distinct boundary in the existing selftest.

    Uses only synthetic files in verified TMPDIR; no browser/model/service run.
    """
    base = tmp / "manifest-inputs"
    base.mkdir()
    for name in M.SOURCE_FILES:
        p = base / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("fixture")
    for name in ("tests/fixtures/sample.json", "tests/fixtures/sample.html", "tests/fixtures/sample.py",
                 "tests/p2_baseline.json", "tools/build_saga.py", "loop/bin/loop.py", "loop/ROLES/EDITOR.md"):
        p = base / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("fixture")
    for name in M.DOCS_FILES:
        p = base / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("schema fixture")
    cache = base / "data/cache"; cache.mkdir(parents=True)
    key, second = "a123456789abcdef", "b123456789abcdef"
    (cache / "index.json").write_text(json.dumps([{"title": "当前作品", "key": second}, {"title": "当前作品", "key": key}]))
    for k in (key, second):
        (cache / (k + ".json")).write_text(json.dumps({"title": "当前作品", "characters": [], "events": []}))
        (cache / (k + ".docs.json")).write_text(json.dumps([{"text": "当前原文"}]))
    log = tmp / "current-run.log"; log.write_text("real test output")
    results = []

    def require(condition, message):
        if not condition: raise AssertionError(message)

    def rejects(fn):
        try: fn()
        except ValueError: return
        raise AssertionError("invalid input accepted")

    def check(name, fn):
        try: fn(); results.append((name, None))
        except Exception as exc: results.append((name, repr(exc)))

    with patch.object(M, "ROOT", base):
        def fingerprint():
            initial = M.source_hashes(); paths = {e["path"] for e in initial["files"]}
            for name in ("tests/fixtures/sample.json", "tests/fixtures/sample.html", "tests/fixtures/sample.py", "tests/p2_baseline.json"):
                require(name in paths, "necessary non-JS fixture/baseline missing")
                p = base / name; old = p.read_text(); before = M.source_hashes()["digest"]
                p.write_text(old + " changed")
                require(M.source_hashes()["digest"] != before, "fixture mutation did not affect fingerprint")
                p.write_text(old)
            require({"tools/build_saga.py", "loop/bin/loop.py", "loop/ROLES/EDITOR.md", "README.md", "AGENTS.md", "loop/README.md"} <= paths, "handoff/tool source missing")
            before = M.source_hashes()["digest"]
            p = base / "tests/outputs/run.log"; p.parent.mkdir(); p.write_text("runtime")
            p = base / "tests/__pycache__/junk.pyc"; p.parent.mkdir(); p.write_text("cache")
            p = base / "loop/state/out/live.json"; p.parent.mkdir(parents=True); p.write_text("live state")
            p = base / "data/llm-config.json"; p.write_text("private fixture")
            p = base / "tools/.env.local"; p.write_text("private fixture")
            require(M.source_hashes()["digest"] == before, "runtime/cache polluted source fingerprint")
            p = base / "tools/private-link.json"; p.symlink_to(base / "data/llm-config.json")
            require(M.source_hashes()["digest"] == before, "configuration symlink polluted source snapshot")
        check("完整源码与非JS夹具/基线指纹反例", fingerprint)

        def selected_books():
            data = M.data_hashes([("当前作品", key)])
            require(data["books"][0]["cacheKey"] == key and data["selection"]["mode"] == "explicit", "explicit current key lost")
            require({e["path"] for e in data["docsCorpus"]} == set(M.DOCS_FILES), "SCHEMA not hashed")
            automatic = M.data_hashes()
            require(automatic["books"][0]["cacheKey"] == second and automatic["selection"]["mode"] == "library-index-first-per-title", "library current selection not recorded")
            for value in ("=12345678", "title=../../12345678", "title=xyz", "title=123"):
                rejects(lambda v=value: M.parse_book(v))
            rejects(lambda: M.data_hashes([("当前作品", key), ("当前作品", second)]))
            rejects(lambda: M.data_hashes([("当前作品", key), ("另一本", key)]))
            rejects(lambda: M.data_hashes([]))
            old_index = (cache / "index.json").read_text()
            (cache / "index.json").write_text(old_index + " ")
            try:
                after = M.data_hashes([("当前作品", key)])
                require(after["frozenInputDigest"] == data["frozenInputDigest"], "mutable index affected frozen published inputs")
                require(after["cacheMeta"][0]["sha256"] != data["cacheMeta"][0]["sha256"] and after["cacheMeta"][0]["mutable"], "library metadata not explicitly mutable")
            finally:
                (cache / "index.json").write_text(old_index)
        check("显式新书键/当前索引及重复穿越边界", selected_books)

        def required_data():
            for suffix in (".json", ".docs.json"):
                p = cache / (key + suffix); original = p.read_text(); p.unlink()
                try: rejects(lambda: M.data_hashes([("当前作品", key)]))
                finally: p.write_text(original)
            p = cache / (key + ".json"); original = p.read_text(); p.write_text("[]")
            try: rejects(lambda: M.data_hashes([("当前作品", key)]))
            finally: p.write_text(original)
        check("必需图谱/原文缺失及错误形状必须失败", required_data)

        digest = M.source_hashes()["digest"]
        receipt = {"sourceDigest": digest, "runs": [{"name": "offline", "command": ["sh", "scripts/accept.sh"], "rc": 0,
                   "log": str(log), "sha256": M.sha256_file(log)}], "remaining": []}
        data_inputs = {entry["path"]: entry["sha256"] for entry in M.data_hashes([("当前作品", key)])["frozenInputs"]}
        bound_receipt = dict(receipt, inputHashes=data_inputs)

        def actual_receipts():
            validated = M.commands_and_logs(receipt, digest)
            require(validated["commands"] == [receipt["runs"][0]["command"]] and validated["runs"][0]["rc"] == 0, "actual receipt was replaced")
            require(not validated["browserSuitesRun"], "offline receipt claimed browser")
            require(not validated["dataCoverage"] and validated["coverage"] == "source-only", "source-only compatibility claimed data coverage")
            covered = M.commands_and_logs(bound_receipt, digest, data_inputs)
            require(covered["dataCoverage"] and covered["inputHashes"] == data_inputs, "explicit frozen inputs not bound")
            browser = copy.deepcopy(receipt); browser["runs"][0].update(command="python3 tests/sky_story_browser.py --base http://example", rc=1)
            got = M.commands_and_logs(browser, digest)
            require(got["browserSuitesRun"] and got["runs"][0]["rc"] == 1, "browser failed receipt must remain a failed executed run")
        check("真实收据命令/退出码/浏览器范围保持", actual_receipts)

        def corrupt_receipts():
            changed = log.read_text(); log.write_text("tampered")
            try: rejects(lambda: M.commands_and_logs(receipt, digest))
            finally: log.write_text(changed)
            cases = []
            missing = copy.deepcopy(receipt); missing["runs"][0]["log"] = str(tmp / "missing.log"); cases.append(missing)
            wrong = copy.deepcopy(receipt); wrong["runs"][0]["sha256"] = "0" * 64; cases.append(wrong)
            stale = copy.deepcopy(receipt); stale["sourceDigest"] = "0" * 64; cases.append(stale)
            relative = copy.deepcopy(receipt); relative["runs"][0]["log"] = "relative.log"; cases.append(relative)
            bool_rc = copy.deepcopy(receipt); bool_rc["runs"][0]["rc"] = True; cases.append(bool_rc)
            duplicate = copy.deepcopy(receipt); duplicate["runs"].append(duplicate["runs"][0]); cases.append(duplicate)
            empty_cmd = copy.deepcopy(receipt); empty_cmd["runs"][0]["command"] = []; cases.append(empty_cmd)
            for item in cases: rejects(lambda x=item: M.commands_and_logs(x, digest))
            missing_inputs = dict(bound_receipt, inputHashes={"docs/SCHEMA.md": data_inputs["docs/SCHEMA.md"]})
            rejects(lambda: M.commands_and_logs(missing_inputs, digest, data_inputs))
            wrong_book = M.data_hashes([("当前作品", second)])["frozenInputs"]
            wrong_inputs = dict(bound_receipt, inputHashes={e["path"]: e["sha256"] for e in wrong_book})
            rejects(lambda: M.commands_and_logs(wrong_inputs, digest, data_inputs))
            source_json = cache / (key + ".docs.json"); original = source_json.read_text(); source_json.write_text(original + " ")
            try: rejects(lambda: M.commands_and_logs(bound_receipt, digest, data_inputs))
            finally: source_json.write_text(original)
            schema = base / "docs/SCHEMA.md"; original = schema.read_text(); schema.write_text(original + " changed")
            try: rejects(lambda: M.commands_and_logs(bound_receipt, digest, data_inputs))
            finally: schema.write_text(original)
        check("缺失/篡改日志、错误hash及陈旧源码收据拒绝", corrupt_receipts)

        def no_receipt():
            old = tmp / "old-release"; old.mkdir(); (old / "gate-report.json").write_text(json.dumps({"ok": True, "p0Count": 0}))
            with patch.object(M, "RELEASE_DIR", old), patch.object(M.ev, "load_scorecard", return_value={"overall": 100}), patch.object(M, "asset_stamp", return_value={}), patch.object(M, "browser_and_gpu", return_value={"browserSuitesRun": False}):
                built = M.build(books=[("当前作品", key)])
            require(built["commands"] == [] and built["logs"] == {} and not built["honesty"]["browserSuitesRun"], "no receipt inferred old runs")
            require(all(d["score"] is None for d in built["scores"]["dimensions"]) and built["scores"]["overall"] is None, "old scorecard became current scores")
            require(built["verdict"]["label"] == "未签收" and built["p0"]["count"] is None, "no receipt became signed/zero P0")
        check("无收据/旧评分旧门禁不冒充当前签收", no_receipt)

        def independent_scores():
            reviews = {"sourceDigest": digest, "inputHashes": data_inputs, "dimensions": [{"id": k, "score": v, "owner": "builder", "reviewer": "independent",
                "testedAt": "2026-10-13T00:00:00Z", "knownGaps": [], "evidence": [{"log": str(log), "sha256": M.sha256_file(log)}]} for k, v in M.ev.DIMENSIONS.items()]}
            independent = M.scores(reviews, digest, data_inputs)
            current = copy.deepcopy(bound_receipt); current["gate"] = {"ok": True, "p0Count": 0}
            runs = M.commands_and_logs(current, digest, data_inputs)
            require(M.verdict(independent, runs["gate"], runs)["label"] == "100分候选", "synthetic full independent score+zero P0 should reach candidate")
            old80 = copy.deepcopy(reviews)
            for d in old80["dimensions"]: d["score"] = int(M.ev.DIMENSIONS[d["id"]] * .8)
            require(M.verdict(M.scores(old80, digest, data_inputs), runs["gate"], runs)["label"] == "未签收", "80% historical threshold still promotes candidate")
            source_only = M.commands_and_logs(receipt, digest, data_inputs)
            require(M.verdict(independent, runs["gate"], source_only)["label"] == "未签收", "source-only receipt promoted data signoff")
            self_signed = copy.deepcopy(reviews); self_signed["dimensions"][0]["reviewer"] = "builder"
            rejects(lambda: M.scores(self_signed, digest))
            require(M.verdict(independent, {"ok": True, "p0Count": 1}, runs)["label"] == "未签收", "nonzero P0 promoted")
            require(M.verdict(dict(independent, dimensions=[]), runs["gate"], runs)["label"] == "未签收", "empty dimensions promoted")
        check("满分独立评分/P0=0严门且80%不得放行", independent_scores)

        def cli_boundary():
            path = tmp / "receipt.json"; path.write_text(json.dumps(receipt))
            output = tmp / "manifest.json"
            with patch.object(M, "asset_stamp", return_value={}), patch.object(M, "browser_and_gpu", return_value={"browserSuitesRun": False}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with patch.object(sys, "argv", ["manifest", "--book", "当前作品=" + key, "--evidence", str(path), "--out", str(output)]):
                    require(M.main() == 0, "valid explicit CLI failed")
                require(output.is_file() and json.loads(output.read_text())["dataHashes"]["books"][0]["cacheKey"] == key, "CLI explicit input not preserved")
                with patch.object(sys, "argv", ["manifest", "--book", "当前作品=" + key, "--out", str(output), "--verdict"]):
                    require(M.main() == 1, "no score/receipt CLI verdict returned green")
                with patch.object(sys, "argv", ["manifest", "--book", "当前作品=" + key, "--evidence", str(tmp / "absent.json"), "--out", str(tmp / "should-not-exist.json")]):
                    require(M.main() == 2, "missing evidence CLI not rejected")
                require(not (tmp / "should-not-exist.json").exists(), "invalid receipt wrote manifest")
                for path in (base / "source-output.json", Path("/tmp") / "castline-forbidden-release.json"):
                    with patch.object(sys, "argv", ["manifest", "--book", "当前作品=" + key, "--out", str(path)]):
                        require(M.main() == 2, "source/system-temp output accepted")
                    require(not path.exists(), "forbidden output was written")
        check("CLI实际书键/收据生成及无签收退出语义", cli_boundary)
    return results


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="castline-gate-selftest-"))
    fails = []
    manifest_results = []
    try:
        print("%-34s %-10s %-10s %s" % ("对照用例", "期望", "实际", "结论"))
        for c in CASES:
            lp = build_case(tmp, c["name"].split(" ")[0].replace("/", "_") + str(abs(hash(c["name"])) % 9999),
                            c["mutate"], c["evidence_file"])
            rec = audit(lp, c["allow_self_review"])
            got_blocked = len(rec["blockers"]) > 0
            ok = got_blocked == c["expect_blocked"]
            if ok and c["expect_blocked"] and c["needle"]:
                ok = has_blocker(rec, c["needle"])
            if ok and c["expect_p0"]:
                ok = rec["blockers"] and all(b.get("kind") == "p0" for b in rec["blockers"])
            if ok and not c["expect_p0"] and c["expect_blocked"] and c["name"] != "自我签收必拦且记 P0":
                pass
            if not ok and c["name"] == "合规台账必须放行":
                ok = not got_blocked
            print("%-34s %-10s %-10s %s" % (
                c["name"], "拦" if c["expect_blocked"] else "放行",
                "拦" if got_blocked else "放行", "OK" if ok else "**不符**"))
            if not ok:
                fails.append((c["name"], [b.get("reason") for b in rec["blockers"]]))

        bad_dir = tmp / "20261007" / "BROKEN"
        bad_dir.mkdir(parents=True, exist_ok=True)
        (bad_dir / "ledger.json").write_text("[1,2,3]", encoding="utf-8")
        rec = audit(bad_dir / "ledger.json")
        ok = len(rec["blockers"]) > 0 and rec["blockers"][0].get("kind") == "p0"
        print("%-34s %-10s %-10s %s" % ("结构不可识别必须拦且记 P0", "拦", "拦" if rec["blockers"] else "放行",
                                        "OK" if ok else "**不符**"))
        if not ok:
            fails.append(("结构不可识别", rec.get("parseError")))

        bad2 = tmp / "20261007" / "BADJSON"
        bad2.mkdir(parents=True, exist_ok=True)
        (bad2 / "ledger.json").write_text("{ not json", encoding="utf-8")
        rec = audit(bad2 / "ledger.json")
        ok = len(rec["blockers"]) > 0 and rec["blockers"][0].get("kind") == "p0"
        print("%-34s %-10s %-10s %s" % ("JSON 无法解析必须拦且记 P0", "拦", "拦" if rec["blockers"] else "放行",
                                        "OK" if ok else "**不符**"))
        if not ok:
            fails.append(("JSON 无法解析", rec.get("parseError")))
        manifest_results = manifest_cases(tmp)
        for name, error in manifest_results:
            print("%-34s %s" % (name, "OK" if error is None else "**不符** " + error))
            if error is not None:
                fails.append((name, error))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fails:
        print("SELFTEST FAILED (%d):" % len(fails))
        for n, d in fails:
            print("  - %s → %s" % (n, d))
        return 1
    print("SELFTEST OK · %d 项负向对照全部符合文档行为" % (len(CASES) + 2 + len(manifest_results)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
