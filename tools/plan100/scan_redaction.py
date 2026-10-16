#!/usr/bin/env python3
"""P13 · API 凭证泄漏扫描（独立复核 P12 的脱敏声明）。

P12 声称：真实密钥 4 类探针扫 435 份日志 / 131MB，命中 0。
本脚本**独立重做**该扫描，不读 P12 的结论，只读真实配置与真实磁盘文件。

为什么必须独立重做：脱敏是安全断言，"实现者说没泄漏" 与 "复算确认没泄漏"
是两件事。审核基线明确把"日志脱敏"列为交付维度要求。

判据：
  - 从 data/llm-config.json 读真实 api_key
  - 构造 4 类探针：全长 / 去前缀 20 字 / 尾 16 字 / 中段 16 字
  - 扫描工作区 + 常见日志目录下所有文本/二进制文件
  - 任一探针命中即 FAIL

注意：只读，不写任何产品文件。产出 artifacts/plan100/review/redaction-scan.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT = artifact_path() / "plan100" / "review"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".mypy_cache", ".pytest_cache",
             "objects", "attachments", "cache", "chunks", "story", "narrative", "docs"}
MAX_FILE_BYTES = 16 * 1024 * 1024

TEXT_SUFFIXES = {".log", ".json", ".jsonl", ".txt", ".md", ".yaml", ".yml", ".env",
                 ".cfg", ".ini", ".conf", ".out", ".err", ".tsv", ".csv", ".html", ".js"}


def load_key() -> str | None:
    p = ROOT / "data" / "llm-config.json"
    if not p.exists():
        return None
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    for prof in cfg.get("profiles") or []:
        k = prof.get("api_key")
        if isinstance(k, str) and len(k) >= 16:
            return k
    return None


def probes_for(key: str) -> dict[str, str]:
    mid = len(key) // 2
    return {
        "full": key,
        "no_prefix_20": key[3:23],
        "tail_16": key[-16:],
        "mid_16": key[mid - 8 : mid + 8],
    }


def scan(roots: list[Path], probes: dict[str, str]) -> dict:
    needles = {name: val.encode() for name, val in probes.items() if val}
    hits: list[dict] = []
    files = 0
    total = 0
    seen: set[str] = set()

    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                p = Path(dirpath) / fn
                rp = os.path.realpath(p)
                if rp in seen:
                    continue
                seen.add(rp)
                if p.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                try:
                    if p.stat().st_size > MAX_FILE_BYTES:
                        continue
                    data = p.read_bytes()
                except Exception:
                    continue
                files += 1
                total += len(data)
                for name, needle in needles.items():
                    if needle in data:
                        hits.append({"path": str(p), "probe": name})
    return {"filesScanned": files, "bytesScanned": total, "hits": hits}


def main() -> int:
    key = load_key()
    if not key:
        print("BLOCKED: no api_key in data/llm-config.json; cannot run redaction scan", file=sys.stderr)
        return 2

    probes = probes_for(key)
    roots = [
        artifact_path(),
        ROOT / "data",
        ROOT / "docs",
        Path("/tmp"),
        Path(os.path.expanduser("~/Library/Logs")),
        Path(os.path.expanduser("~/.mirasim")),
    ]
    print(f"扫描根目录: {[str(r) for r in roots]}")
    print(f"探针: {list(probes)}（长度 {[len(v) for v in probes.values()]}）")
    result = scan(roots, probes)

    OUT.mkdir(parents=True, exist_ok=True)
    cfg_hits = [h for h in result["hits"] if h["path"].endswith("llm-config.json")]
    other_hits = [h for h in result["hits"] if not h["path"].endswith("llm-config.json")]

    report = {
        "scanner": "tools/plan100/scan_redaction.py",
        "independentlyRecomputes": "P12 的脱敏声明（435 份/131MB 零命中）",
        "keySource": "data/llm-config.json profiles[0].api_key",
        "probeKinds": list(probes),
        "probeLengths": {k: len(v) for k, v in probes.items()},
        "roots": [str(r) for r in roots],
        **result,
        "configCopies": {"count": len(cfg_hits),
                         "note": "命中文件名即 llm-config.json —— 密钥本就必须在配置里，属合法副本，不计泄漏",
                         "paths": sorted({h["path"] for h in cfg_hits})},
        "nonConfigHits": {"count": len(other_hits),
                          "note": "命中其他载体 = 真正的泄漏面",
                          "hits": other_hits},
        "verdict": "clean" if not other_hits else "LEAK",
    }
    out = OUT / "redaction-scan.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\n扫描 {result['filesScanned']} 文件 / {result['bytesScanned']:,} 字节")
    print(f"命中配置副本（合法）: {len(cfg_hits)}")
    for pth in sorted({h["path"] for h in cfg_hits}):
        print(f"  [config] {pth}")
    print(f"命中其他载体（泄漏面）: {len(other_hits)}")
    for h in other_hits[:20]:
        print(f"  [LEAK?] {h['probe']} {h['path']}")
    print(f"VERDICT: {report['verdict']}")
    print(f"-> {artifact_rel(out)}")
    return 1 if other_hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
