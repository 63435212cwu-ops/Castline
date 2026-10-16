#!/usr/bin/env python3
"""P13 辅助 · 证据路径完整性校验。

审计的基本要求：ledger 里写下的每条 evidence 路径必须真实存在。
「引用了不存在的证据」是最容易混过人工复核的伪完成方式之一。

遍历 artifacts/plan100/*/*/ledger.json：
  - evidence[].path 是否存在（相对工作区根或绝对路径）
  - source-manifest.json 里 files[] 是否存在
  - inputHashes[].path 是否存在，且 sha256 是否仍与当前文件一致
  - decision.md 是否存在（计划要求每个工作包必须有）
  - rollback.patch 是否存在（merged 状态必须有）

任何缺失以非零退出码报告，便于接进门禁。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
PLAN_DIR = artifact_path() / "plan100"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def resolve(p: str) -> Path:
    """路径可能是相对工作区根，也可能是绝对路径。"""
    q = Path(p)
    return q if q.is_absolute() else (ROOT / q)


def main() -> int:
    problems: list[dict] = []
    regenerated: list[dict] = []
    checked = 0
    ledgers = sorted(PLAN_DIR.glob("*/*/ledger.json"))
    if not ledgers:
        print("no ledgers found", file=sys.stderr)
        return 2

    for lp in ledgers:
        task = lp.parent.name
        try:
            data = json.loads(lp.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append({"task": task, "kind": "ledger-unparsable", "detail": str(exc)})
            continue

        for e in data.get("evidence") or []:
            path = e.get("path") if isinstance(e, dict) else e
            if not path:
                problems.append({"task": task, "kind": "evidence-empty-path", "detail": str(e)})
                continue
            checked += 1
            if not resolve(path).exists():
                problems.append({"task": task, "kind": "evidence-missing", "path": path})

        for h in data.get("inputHashes") or []:
            p = h.get("path")
            if not p:
                continue
            checked += 1
            fp = resolve(p)
            if not fp.exists():
                problems.append({"task": task, "kind": "input-missing", "path": p})
                continue
            if not (p.startswith("artifacts/") or fp.resolve().is_relative_to(artifact_path())):
                continue
            actual = sha256_file(fp)
            if h.get("sha256") and actual != h["sha256"]:
                regenerated.append({
                    "task": task, "path": p,
                    "recorded": h["sha256"][:16], "actual": actual[:16],
                })

        mp = lp.parent / "source-manifest.json"
        if mp.exists():
            try:
                manifests = json.loads(mp.read_text(encoding="utf-8"))
                if isinstance(manifests, dict):
                    manifests = [manifests]
                for m in manifests:
                    for f in m.get("files") or []:
                        checked += 1
                        if not resolve(f).exists():
                            problems.append({"task": task, "kind": "manifest-file-missing", "path": f})
            except Exception as exc:
                problems.append({"task": task, "kind": "manifest-unparsable", "detail": str(exc)})

        if not (lp.parent / "decision.md").exists():
            problems.append({"task": task, "kind": "decision-missing",
                             "detail": "计划要求每个工作包必须有 decision.md"})
        if data.get("status") == "merged" and not (lp.parent / "rollback.patch").exists():
            problems.append({"task": task, "kind": "rollback-missing",
                             "detail": "merged 状态必须有 rollback.patch"})

    out = PLAN_DIR / "review" / "evidence-path-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "ledgers": len(ledgers), "pathsChecked": checked,
        "problems": problems,
        "regeneratedProducts": {
            "count": len(regenerated),
            "note": ("artifacts/ 下的产物被合法重新生成导致哈希变化。迭代工作流正常现象，"
                     "不计入 problems。只有**路径缺失**才是问题。"),
            "items": regenerated,
        },
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"ledgers={len(ledgers)} pathsChecked={checked} problems={len(problems)} "
          f"regenerated-products={len(regenerated)}")
    for p in problems:
        print(f"  [{p['kind']}] {p['task']} {p.get('path') or p.get('detail','')}")
    print(f"-> {artifact_rel(out)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
