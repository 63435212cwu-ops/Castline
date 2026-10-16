#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate an exact release input manifest without running browsers or models.

Use --book TITLE=CACHEKEY to freeze actual graph/source versions, and --evidence
FILE for current sourceDigest-bound run receipts. No receipt means no claimed
commands/logs. Scores remain null unless --scores supplies independent reviews
bound to this source digest; historical scorecards never become current scores.
All generated output belongs in verified external CL_ARTIFACTS storage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence as ev
from evidence import artifact_path, rel as artifact_rel
PLAN_DIR = artifact_path() / "plan100"
RELEASE_DIR = PLAN_DIR / "release"
DEFAULT_OUT = RELEASE_DIR / "release-manifest.json"
SOURCE_DIRS = ("js", "css", "scripts", "tools", "tests", "loop/bin", "loop/ROLES")
SOURCE_FILES = ("index.html", "serve.py", "distill.py", "narrative.py", "README.md",
                "AGENTS.md", ".gitignore", "loop/README.md")
SOURCE_TEST_GLOBS = ("tests/**/*",)
SOURCE_EXCLUDE_PARTS = ("__pycache__", ".pytest_cache", ".ruff_cache", "node_modules")
SOURCE_EXCLUDE_FILES = {".DS_Store", ".coverage"}
DOCS_DIR = ROOT / "docs"
DOCS_FILES = ("docs/QUALITY.md", "docs/SCHEMA.md")
DATA_META_FILES = ("data/cache/index.json",)
KEY_RE = re.compile(r"[0-9a-fA-F]{8,40}\Z")
HASH_RE = re.compile(r"[0-9a-fA-F]{64}\Z")
STORAGE_MOUNT = Path("/Volumes/资源库")
STORAGE_ROOT = STORAGE_MOUNT / "我的资源/回滚点"
PRIVATE_PARTS = {".git", ".mirasim", ".claude", ".agents", ".workbuddy"}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def _rel(p: Path) -> str:
    try:
        return str(p.absolute().relative_to(ROOT.absolute()))
    except ValueError:
        return str(p)


def _entry(path: Path) -> dict:
    if _private_source(path):
        raise ValueError("private configuration cannot be a release snapshot input")
    exists = path.is_file()
    return {"path": _rel(path), "exists": exists,
            "bytes": path.stat().st_size if exists else None,
            "sha256": sha256_file(path) if exists else None}


def _group_digest(entries: list[dict]) -> str:
    h = hashlib.sha256()
    for e in sorted(entries, key=lambda x: x["path"]):
        h.update(("%s\0%s\0" % (e["path"], e.get("sha256") or "MISSING")).encode())
    return h.hexdigest()


def _private_source(p: Path) -> bool:
    try:
        parts = p.absolute().relative_to(ROOT.absolute()).parts
    except ValueError:
        parts = ()
    target = p.resolve()
    private_targets = {(ROOT / "data/llm-config.json").resolve(),
                       (Path.home() / ".nest-drama/api-config.json").resolve()}
    fixture = parts[:2] == ("tests", "fixtures")
    return (target in private_targets or any(part in PRIVATE_PARTS for part in parts)
            or (not fixture and (p.name == ".env" or p.name.startswith(".env."))))


def _source_file(p: Path) -> bool:
    parts = p.relative_to(ROOT).parts
    return (p.is_file() and not _private_source(p) and not any(part in SOURCE_EXCLUDE_PARTS for part in parts)
            and p.name not in SOURCE_EXCLUDE_FILES and not p.name.startswith("._")
            and str(p.relative_to(ROOT)) != "tests/contrast_report.json"
            and not p.name.endswith((".pyc", ".pyo", ".bak", ".tmp", ".swp", ".swo", "~"))
            and not (parts[0] == "tests" and len(parts) > 1 and parts[1] in {"outputs", "artifacts", "logs", "shots"}))


def git_tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [ROOT / line for line in out.splitlines() if line.strip()]
    except Exception:
        return []


def source_hashes() -> dict:
    src = [ROOT / name for name in SOURCE_FILES]
    for name in SOURCE_DIRS:
        src.extend(p for p in (ROOT / name).rglob("*") if _source_file(p))
    entries = [_entry(p) for p in sorted(set(src))]
    dirty = head = ""
    git_known = False
    try:
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
        git_known = True
    except Exception:
        pass
    return {"algorithm": "sha256", "digest": _group_digest(entries), "fileCount": len(entries),
            "missingFiles": [e["path"] for e in entries if not e["exists"] or not e["sha256"]],
            "gitHead": head or None, "workingTreeClean": not dirty.strip() if git_known else None,
            "workingTreeDirtyLines": len(dirty.splitlines()) if git_known else None,
            "note": "Exact current disk inputs include all formal tests/fixtures/baselines and handoff code; Git HEAD is context, not a backup of the dirty worktree.",
            "files": entries}


def parse_book(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or "=" not in value:
        raise ValueError("book must be TITLE=CACHEKEY")
    title, key = value.rsplit("=", 1)
    title = title.strip()
    if not title or not KEY_RE.fullmatch(key):
        raise ValueError("book needs a nonempty title and an 8-40 hex cache key")
    return title, key.lower()


def _books(books=None):
    selection = "explicit" if books is not None else "library-index-first-per-title"
    if books is None:
        try:
            index = json.loads((ROOT / "data/cache/index.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("library index unavailable: %s" % exc) from exc
        if not isinstance(index, list):
            raise ValueError("library index must be an array")
        books, seen = [], set()
        for row in index:
            if not isinstance(row, dict) or not isinstance(row.get("title"), str) or not row["title"].strip():
                raise ValueError("library index row requires title")
            title = row["title"].strip()
            if title not in seen:
                books.append((title, row.get("key")))
                seen.add(title)
    if isinstance(books, dict):
        books = list(books.items())
    if not isinstance(books, (list, tuple)) or not books:
        raise ValueError("at least one book is required")
    normalized, titles, keys = [], set(), set()
    for row in books:
        if isinstance(row, str):
            title, key = parse_book(row)
        else:
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                raise ValueError("book must contain title and key")
            title, key = row
            if not isinstance(title, str) or not title.strip() or not isinstance(key, str) or not KEY_RE.fullmatch(key):
                raise ValueError("invalid book title/key")
            title, key = title.strip(), key.lower()
        if title in titles or key in keys:
            raise ValueError("duplicate book title or cache key")
        titles.add(title); keys.add(key); normalized.append((title, key))
    return normalized, selection


def data_hashes(books=None) -> dict:
    selected, selection = _books(books)
    graphs, docs, rows = [], [], []
    for title, key in selected:
        gp = ROOT / "data/cache" / (key + ".json")
        dp = ROOT / "data/cache" / (key + ".docs.json")
        for p in (gp, dp):
            if not p.is_file() or not p.stat().st_size:
                raise ValueError("required graph/source input missing: %s" % _rel(p))
        try:
            graph = json.loads(gp.read_text(encoding="utf-8"))
            source = json.loads(dp.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("invalid graph/source JSON: %s" % exc) from exc
        if not isinstance(graph, dict) or graph.get("title") != title or not isinstance(source, list):
            raise ValueError("graph title/source shape mismatch: %s" % key)
        g, d = _entry(gp), _entry(dp)
        graphs.append(g); docs.append(d)
        rows.append({"title": title, "cacheKey": key, "graph": g, "docs": d, "match": True})
    doc_entries = [_entry(ROOT / f) for f in DOCS_FILES]
    meta_entries = [dict(_entry(ROOT / f), mutable=True, role="library-state-at-generation",
                         excludedFromFrozenInputDigest=True) for f in DATA_META_FILES]
    if any(not e["exists"] for e in doc_entries + meta_entries):
        raise ValueError("required schema/quality/library input missing")
    fixture_entries = [_entry(p) for p in sorted((ROOT / "tests/fixtures").rglob("*")) if _source_file(p)]
    frozen_entries = graphs + docs + doc_entries
    return {"algorithm": "sha256", "frozenInputs": frozen_entries,
            "frozenInputDigest": _group_digest(frozen_entries),
            "selection": {"mode": selection,
            "note": "Explicit title/key inputs are frozen; default selects the first current library-index entry for each title without historical hardcoded keys."},
            "books": rows, "graphDigest": _group_digest(graphs), "docsDigest": _group_digest(docs),
            "docsCorpus": doc_entries, "docsCorpusDigest": _group_digest(doc_entries),
            "cacheMeta": meta_entries, "contractFixtures": fixture_entries,
            "contractFixtureDigest": _group_digest(fixture_entries),
            "note": "Read-only graph/source inputs; original source hash identifies quote/offset material. This is no whole-book semantic completion claim."}


def schema_versions() -> dict:
    """从 serve.py 解析 schema 常量（不 import serve.py，避免启动副作用）。"""
    text = ""
    try:
        text = (ROOT / "serve.py").read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass

    def grab(name: str) -> str | None:
        m = re.search(r'^%s\s*=\s*"([^"]+)"' % re.escape(name), text, re.M)
        return m.group(1) if m else None

    return {
        "graphSchema": grab("GRAPH_SCHEMA_VERSION"),
        "attrSchema": grab("ATTR_SCHEMA_VERSION"),
        "source": "serve.py (regex parse, no import)",
    }


def asset_stamp() -> dict:
    """资源版本戳：index.html 中每个 ?v= 内容哈希 + 组合摘要 + 静态门禁结果。"""
    index = ROOT / "index.html"
    tags: list[dict] = []
    try:
        html = index.read_text(encoding="utf-8", errors="replace")
    except OSError:
        html = ""
    for m in re.finditer(r'(?:src|href)="((?:js|css)/[^"?]+)\?v=([^"]*)"', html):
        tags.append({"asset": m.group(1), "stamp": m.group(2)})
    stamped = len(tags)
    untagged = len(re.findall(r'(?:src|href)="(?:js|css)/[^"?]+"', html))
    h = hashlib.sha256()
    for t in sorted(tags, key=lambda x: x["asset"]):
        h.update(("%s\0%s\0" % (t["asset"], t["stamp"])).encode())
    check = {"command": "python3 tests/version_stamp.py --check", "exitCode": None, "ok": None}
    try:
        r = subprocess.run(
            [sys.executable, "tests/version_stamp.py", "--check"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
        check["exitCode"] = r.returncode
        check["ok"] = r.returncode == 0
        check["stdoutTail"] = (r.stdout or "").strip().splitlines()[-3:]
    except Exception as exc:
        check["error"] = str(exc)
    return {
        "indexHtml": _entry(index),
        "stampedTags": stamped,
        "untaggedTags": untagged,
        "digest": h.hexdigest(),
        "stamps": tags,
        "staticCheck": check,
        "note": "?v= 为每个 js/css 内容哈希前 8 位；digest 为全部 (asset,stamp) 排序摘要。",
    }


# ------------------------------------------------------------ 环境：浏览器/GPU


def browser_and_gpu() -> dict:
    """浏览器与 GPU：真实探测。未跑过的浏览器套件一律 false。"""
    chrome_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    version = None
    if chrome_path.exists():
        try:
            r = subprocess.run([str(chrome_path), "--version"], capture_output=True, text=True, timeout=20)
            version = (r.stdout or r.stderr or "").strip() or None
        except Exception:
            version = None
    gpu = {}
    try:
        out = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True, timeout=30
        ).stdout
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("Chipset Model:"):
                gpu["chipset"] = s.split(":", 1)[1].strip()
            elif s.startswith("Metal Support:"):
                gpu["metal"] = s.split(":", 1)[1].strip()
            elif s.startswith("Total Number of Cores:"):
                gpu.setdefault("cores", s.split(":", 1)[1].strip())
    except Exception:
        pass
    return {
        "browser": {
            "name": "Google Chrome",
            "version": version,
            "path": str(chrome_path),
            "installed": chrome_path.exists(),
            "note": "真实安装版本的字符串；本清单不声称任何浏览器套件已跑（见 browserSuitesRun）。",
        },
        "gpu": gpu or {"chipset": None},
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "runtime": {
            "python": platform.python_version(),
            "node": _node_version(),
        },
        "browserSuitesRun": False,
        "gpuLoadPolicy": "串行（计划禁止并发 GPU）；本清单生成过程未启动任何浏览器。",
    }


def _node_version() -> str | None:
    for cmd in ("node",):
        try:
            r = subprocess.run([cmd, "-v"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return (r.stdout or "").strip()
        except Exception:
            continue
    return None


def _json_input(value, label: str):
    if value is None or isinstance(value, dict):
        return value
    try:
        data = json.loads(Path(value).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("invalid %s input: %s" % (label, exc)) from exc
    if not isinstance(data, dict):
        raise ValueError("%s must be an object" % label)
    return data


def _proof(item: dict, label: str) -> dict:
    if not isinstance(item, dict) or not isinstance(item.get("log"), str) or not isinstance(item.get("sha256"), str):
        raise ValueError("%s requires log and sha256" % label)
    p = Path(item["log"])
    if not p.is_absolute() or not p.is_file() or not HASH_RE.fullmatch(item["sha256"]):
        raise ValueError("%s log must be an existing absolute file with sha256" % label)
    actual = sha256_file(p)
    if actual != item["sha256"].lower():
        raise ValueError("%s log hash mismatch" % label)
    return {"path": str(p), "exists": True, "bytes": p.stat().st_size, "sha256": actual}


def _input_hashes(declared, expected=None) -> dict:
    """Verify every declared input; frozen graph/source/schema coverage is explicit.

    Library history remains mutable metadata and cannot supply frozen coverage.
    """
    if declared is None:
        return {"inputHashes": {}, "dataCoverage": False, "coverage": "source-only", "mutableInputs": []}
    if isinstance(declared, dict):
        rows = list(declared.items())
    elif isinstance(declared, list):
        if not all(isinstance(row, dict) and set(row) >= {"path", "sha256"} for row in declared):
            raise ValueError("inputHashes entries require path and sha256")
        rows = [(row["path"], row["sha256"]) for row in declared]
    else:
        raise ValueError("inputHashes must be a path/hash object or entry array")
    if not rows:
        raise ValueError("inputHashes cannot be empty")
    hashes = {}
    for raw, digest in rows:
        if not isinstance(raw, str) or not raw or ".." in Path(raw).parts:
            raise ValueError("inputHash path cannot traverse project boundaries")
        path = Path(raw); path = path if path.is_absolute() else ROOT / path
        try:
            name = str(path.absolute().relative_to(ROOT.absolute()))
        except ValueError as exc:
            raise ValueError("inputHash path must belong to project") from exc
        if name in hashes or _private_source(path):
            raise ValueError("duplicate/private inputHash path")
        if not isinstance(digest, str) or not HASH_RE.fullmatch(digest) or not path.is_file() or sha256_file(path) != digest.lower():
            raise ValueError("inputHash file missing or hash mismatch: %s" % name)
        hashes[name] = digest.lower()
    expected = expected or {}
    if expected and any(hashes.get(path) != digest for path, digest in expected.items()):
        raise ValueError("inputHashes do not cover current frozen graph/source/QUALITY/SCHEMA inputs")
    return {"inputHashes": hashes, "dataCoverage": bool(expected),
            "coverage": "source-and-frozen-data" if expected else "source-and-declared-inputs",
            "mutableInputs": sorted(set(hashes) & set(DATA_META_FILES))}


def commands_and_logs(extra: dict | None = None, source_digest: str | None = None, data_inputs=None) -> dict:
    receipt = _json_input(extra, "evidence")
    if receipt is None:
        return {"commands": [], "logs": {}, "runs": [], "remaining": [], "browserSuitesRun": False,
                **_input_hashes(None),
                "receiptProvided": False, "note": "No current receipt; no previous logs or planned commands are inferred."}
    digest = source_digest or source_hashes()["digest"]
    if receipt.get("sourceDigest") != digest:
        raise ValueError("evidence sourceDigest does not match current source inputs")
    inputs = _input_hashes(receipt.get("inputHashes"), data_inputs)
    if not isinstance(receipt.get("runs"), list) or not isinstance(receipt.get("remaining"), list) or not all(isinstance(x, str) for x in receipt["remaining"]):
        raise ValueError("evidence requires runs array and remaining text array")
    commands, logs, runs = [], {}, []
    browser = False
    for row in receipt["runs"]:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"].strip() or row["name"] in logs:
            raise ValueError("run requires a unique nonempty name")
        command = row.get("command")
        if isinstance(command, str):
            if not command.strip():
                raise ValueError("run command is empty")
            try:
                argv = shlex.split(command)
            except ValueError as exc:
                raise ValueError("invalid run command") from exc
        elif isinstance(command, list) and command and all(isinstance(x, str) and x for x in command):
            argv = command
        else:
            raise ValueError("run command must be text or a nonempty argument list")
        if type(row.get("rc")) is not int:
            raise ValueError("run rc must be an integer")
        log = _proof(row, row["name"])
        logs[row["name"]] = log
        commands.append(command)
        runs.append({"name": row["name"], "command": command, "rc": row["rc"], "log": log["path"], "sha256": log["sha256"]})
        browser |= ("--browser" in argv and any(x.endswith("scripts/accept.sh") for x in argv)) or any(re.search(r"(?:^|/)tests/[^/]*_browser\.py$", x) for x in argv)
    gate = receipt.get("gate")
    if gate is not None and (not isinstance(gate, dict) or type(gate.get("ok")) is not bool or type(gate.get("p0Count")) is not int or gate["p0Count"] < 0):
        raise ValueError("current gate requires boolean ok and nonnegative integer p0Count")
    return {"commands": commands, "logs": logs, "runs": runs, "remaining": receipt["remaining"],
            "receiptProvided": True, "sourceDigest": digest, "browserSuitesRun": bool(browser), **inputs,
            "gate": gate, "note": "Only verified current source-bound run receipts are listed; rc is preserved even on failure."}


def load_thresholds() -> dict:
    return dict(ev.DIMENSIONS)


def scores(score_input=None, source_digest: str | None = None, data_inputs=None) -> dict:
    supplied = _json_input(score_input, "scores")
    inputs = _input_hashes(supplied.get("inputHashes") if supplied else None, data_inputs)
    dims = [{"id": k, "name": k, "max": v, "score": None, "baseline": None,
             "evidence": [], "reviewer": None, "testedAt": None, "knownGaps": []}
            for k, v in ev.DIMENSIONS.items()]
    if supplied is not None:
        if supplied.get("sourceDigest") != (source_digest or source_hashes()["digest"]):
            raise ValueError("scores sourceDigest does not match current source inputs")
        rows = supplied.get("dimensions")
        if not isinstance(rows, list) or len(rows) != len(dims) or {r.get("id") for r in rows if isinstance(r, dict)} != set(ev.DIMENSIONS):
            raise ValueError("scores require each current dimension exactly once")
        by_id = {r["id"]: r for r in rows}
        for d in dims:
            row = by_id[d["id"]]
            score = row.get("score")
            if type(score) is not int or not 0 <= score <= d["max"]:
                raise ValueError("score must be an integer within the dimension maximum")
            owner, reviewer = row.get("owner"), row.get("reviewer")
            if not isinstance(owner, str) or not owner.strip() or not isinstance(reviewer, str) or not reviewer.strip() or owner.strip() == reviewer.strip() or not isinstance(row.get("testedAt"), str) or not row["testedAt"].strip():
                raise ValueError("scores require independent owner/reviewer and testedAt")
            proofs = row.get("evidence")
            if not isinstance(proofs, list) or not proofs:
                raise ValueError("scores require current hashed review evidence")
            gaps = row.get("knownGaps")
            if not isinstance(gaps, list) or not all(isinstance(x, str) for x in gaps):
                raise ValueError("score knownGaps must be a text array")
            d.update(score=score, reviewer=reviewer.strip(), owner=owner.strip(), testedAt=row["testedAt"],
                     evidence=[_proof(e, "score review") for e in proofs], knownGaps=gaps)
    untested = [d["id"] for d in dims if d["score"] is None]
    total = sum(d["score"] for d in dims) if not untested else None
    return {"source": "explicit-current-independent-reviews" if supplied else None,
            "sourceDigest": supplied.get("sourceDigest") if supplied else None,
            **inputs,
            "sourceExists": supplied is not None, "baselineScore": None, "baselineDate": None,
            "dimensions": dims, "overall": total, "maxTotal": sum(ev.DIMENSIONS.values()),
            "verifiedTotal": total, "untestedDimensions": untested,
            "belowThreshold": [{"id": d["id"], "score": d["score"], "threshold": d["max"], "max": d["max"]} for d in dims if d["score"] is not None and d["score"] < d["max"]],
            "thresholds": load_thresholds(), "independentlyVerified": supplied is not None,
            "note": "Only explicit independent reviews bound to current source are current scores; historical scorecards are never imported."}


def known_risks(scores_obj=None, source_obj=None, receipt=None) -> list[dict]:
    sc, src = scores_obj or scores(), source_obj or source_hashes()
    risks = [{"kind": "untested-dimension", "dimension": d, "text": "%s not independently signed; score=null" % d} for d in sc["untestedDimensions"]]
    for d in sc["dimensions"]:
        risks.extend({"kind": "score-gap", "dimension": d["id"], "text": g} for g in d["knownGaps"])
    if src["workingTreeClean"] is not True:
        risks.append({"kind": "vcs", "text": "Current disk digest is the frozen input; Git HEAD does not capture uncommitted edits."})
    if receipt:
        risks.extend({"kind": "remaining", "text": x} for x in receipt["remaining"])
        risks.extend({"kind": "failed-run", "text": "%s exited %s" % (r["name"], r["rc"])} for r in receipt["runs"] if r["rc"] != 0)
    return risks


def verdict(scores_obj: dict, gate: dict | None, receipt=None) -> dict:
    reasons = []
    dimensions = scores_obj.get("dimensions", [])
    full_dimensions = (isinstance(dimensions, list) and len(dimensions) == len(ev.DIMENSIONS)
                       and {d.get("id") for d in dimensions if isinstance(d, dict)} == set(ev.DIMENSIONS)
                       and all(d.get("max") == ev.DIMENSIONS[d["id"]]
                               and type(d.get("score")) is int and d["score"] == d["max"]
                               and not d.get("knownGaps") for d in dimensions))
    if scores_obj.get("untestedDimensions"):
        reasons.append("未测维度：%s" % ", ".join(scores_obj["untestedDimensions"]))
    if (scores_obj.get("independentlyVerified") is not True or receipt is None
            or scores_obj.get("sourceDigest") != receipt.get("sourceDigest")):
        reasons.append("缺当前独立评分签收")
    if not full_dimensions or scores_obj.get("belowThreshold") or scores_obj.get("verifiedTotal") != sum(ev.DIMENSIONS.values()) or scores_obj.get("maxTotal") != sum(ev.DIMENSIONS.values()):
        reasons.append("全部维度须达到各自满分且无已知缺口")
    if gate is None or gate.get("ok") is not True or type(gate.get("p0Count")) is not int or gate["p0Count"] != 0:
        reasons.append("缺同版门禁放行与P0=0证据")
    if receipt is None or not receipt.get("receiptProvided") or not receipt.get("runs") or any(r["rc"] != 0 for r in receipt["runs"]):
        reasons.append("缺同版通过的运行收据")
    if receipt and receipt.get("remaining"):
        reasons.append("仍有未完成项")
    if not receipt or not receipt.get("dataCoverage") or not scores_obj.get("dataCoverage"):
        reasons.append("缺当前作品/原文/QUALITY/SCHEMA的固定输入覆盖；仅源码证据不能替代数据验收")
    return {"label": "未签收" if reasons else "100分候选", "reasons": reasons,
            "rule": "All dimensions require full independent current scores, current gate P0=0 and passed source-bound receipts; historical scores or old logs cannot promote a release."}


def p0_summary(receipt=None) -> dict:
    gate = (receipt or {}).get("gate")
    return {"count": gate.get("p0Count") if gate else None,
            "note": "Current validated receipt gate only; missing is unknown, not zero."}


def rollback_info() -> dict:
    return {"commit": None, "commitShort": None, "rollbackCommit": None,
            "procedure": ["Before each important edit, copy only owned files to verified CL_ROLLBACK and record original SHA256 plus the input manifest.",
                          "To restore, first match current owned paths against the expected candidate hashes, then restore only those files from that exact backup and verify original SHA256.",
                          "Preserve other tasks, original materials, published keys and user configuration; run related contracts, resource stamps and required acceptance checks after restore."],
            "drillPatch": None, "drillEvidence": None, "drill": None,
            "note": "A Git HEAD commit is not a backup of this dirty worktree. Use the release-owned external backup manifest and its verified hashes."}


def build(books=None, evidence=None, score_input=None) -> dict:
    src = source_hashes()
    if src["missingFiles"]:
        raise ValueError("required source inputs missing: %s" % ", ".join(src["missingFiles"]))
    data = data_hashes(books)
    data_inputs = {entry["path"]: entry["sha256"] for entry in data["frozenInputs"]}
    cmdlog = commands_and_logs(evidence, src["digest"], data_inputs)
    sc = scores(score_input, src["digest"], data_inputs)
    environment = browser_and_gpu()
    environment["browserSuitesRun"] = cmdlog["browserSuitesRun"]
    gate = cmdlog.get("gate")
    return {"manifestVersion": "castline/release/2", "generatedAt": utcnow(), "project": "Castline · 小说星图",
            "plan": {"path": "docs/QUALITY.md", "section": "P10/P11 and §19", "phase": "exact current release inputs and receipts"},
            "sourceHashes": src, "dataHashes": data, "schemaVersions": schema_versions(),
            "assetStamp": asset_stamp(), "environment": environment,
            "commands": cmdlog["commands"], "logs": cmdlog["logs"], "receipt": cmdlog,
            "scores": sc, "historicalScores": None, "p0": p0_summary(cmdlog),
            "knownRisks": known_risks(sc, src, cmdlog), "rollback": rollback_info(),
            "verdict": verdict(sc, gate, cmdlog),
            "gate": {"path": None, "exists": gate is not None, "ok": (gate or {}).get("ok"), "p0Count": (gate or {}).get("p0Count")},
            "honesty": {"estimatedScoresUsed": False, "realDeviceEvidence": False,
                        "browserSuitesRun": cmdlog["browserSuitesRun"],
                        "note": "Hardware detection is not test evidence; no receipt means no executed-suite claim. Full-book, art and real-device signoff remain separate."}}


def _output_path(value: str) -> Path:
    path = Path(value); path = path if path.is_absolute() else ROOT / path
    path = path.resolve()
    if path == ROOT.resolve() or ROOT.resolve() in path.parents:
        raise ValueError("generated release output cannot be written into the source tree")
    if (not os.path.ismount(STORAGE_MOUNT) or not STORAGE_ROOT.is_dir()
            or not os.access(STORAGE_ROOT, os.W_OK)
            or STORAGE_ROOT.resolve() not in path.parents):
        raise ValueError("release output requires mounted writable external rollback storage; use run-with-storage.py")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--book", action="append", help="repeat TITLE=8-40hex to freeze actual graph/source inputs")
    ap.add_argument("--evidence", help="sourceDigest-bound current run receipt JSON")
    ap.add_argument("--scores", help="current independent dimension review JSON; omitted means all null")
    ap.add_argument("--print", dest="do_print", action="store_true")
    ap.add_argument("--verdict", action="store_true", help="nonzero unless full signoff conditions hold")
    args = ap.parse_args()
    try:
        out = _output_path(args.out)
        books = [parse_book(x) for x in args.book] if args.book is not None else None
        m = build(books=books, evidence=args.evidence, score_input=args.scores)
    except (ValueError, OSError) as exc:
        print("release-manifest: invalid inputs: %s" % exc, file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("release-manifest: %s" % _rel(out))
    print("source.digest %s (%d files, clean=%s)" % (m["sourceHashes"]["digest"][:16], m["sourceHashes"]["fileCount"], m["sourceHashes"]["workingTreeClean"]))
    print("data.graphDigest %s (%s)" % (m["dataHashes"]["graphDigest"][:16], m["dataHashes"]["selection"]["mode"]))
    print("VERDICT: %s" % m["verdict"]["label"])
    for reason in m["verdict"]["reasons"]:
        print("  - %s" % reason)
    if args.do_print:
        print(json.dumps(m, ensure_ascii=False, indent=2))
    return (0 if m["verdict"]["label"] == "100分候选" else 1) if args.verdict else 0


if __name__ == "__main__":
    raise SystemExit(main())
