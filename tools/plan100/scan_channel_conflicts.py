#!/usr/bin/env python3
"""P13 · 独立通道冲突扫描（不信登记表，直接扫 CSS 源码）。

为什么需要这个工具
------------------
`tools/plan100/channel_audit.js` 的结论建立在**手工登记表** `ASSIGNMENTS` 上：
它从源码里抽出「通道 → class → 语义」三元组，按「视图 × 通道 × 取值」分组找冲突。
登记表每条都带 `evidence` 字面量并由 `assertEvidence()` 核对 —— 设计是好的。

**但仍有残余风险**：如果某个语义**从未被登记**，它造成的冲突就不会出现在
`conflicts` 里。也就是说「conflicts 降到 0」可能来自「真的没复用了」，也可能来自
「那一族没被登记」。两者在 JSON 上长得一样。

本工具从**另一条路径**独立验证：不读任何登记表，只做机械扫描 ——
  对每个 CSS 文件，收集「同一视图作用域内，同一自定义属性（token）被用在
  ≥2 个**不同语义前缀**的 class 上」的情况。
语义前缀由 class 名的词干推断（如 `is-derived` / `is-source` / `is-branch`），
这是**粗粒度**的，会误报（同一语义用不同类名），但**不会漏报**（同一 token 被
多个不同类名复用一定会被抓到）。

定位：这是**交叉验证**工具，不是替代品。
  - channel_audit.js 说「0 冲突」+ 本工具说「N 处 token 复用」 ⇒ **需要人工判读**
  - 两者都说 0 ⇒ 强证据
产出 artifacts/plan100/projection/channel-css-independent.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT = artifact_path() / "plan100" / "projection"

CSS_GLOBS = [
    "css/sky-deep-hud.css",
    "css/sky-compass.css",
    "css/sky.css",
    "css/sky-reading.css",
    "css/annulus.css",
    "css/atlas-score.css",
    "css/atlas-workspace.css",
    "css/atlas-fallback.css",
    "css/domains-read.css",
    "css/constellation-reading.css",
    "css/information-architecture.css",
]

RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
VAR_USE_RE = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;}]+)")
CLASS_RE = re.compile(r"\.([a-zA-Z][\w-]*)")


def semantic_stem(cls: str) -> str:
    """把类名归到「语义词干」，用于判断两种用法是否属于不同语义。"""
    c = cls.lower()
    for pfx in ("is-", "has-", "sd-", "skc-", "cl-", "afb-", "cp-", "clr-", "aph-"):
        if c.startswith(pfx):
            c = c[len(pfx):]
            break
    return re.split(r"[-_]", c)[0] if c else cls.lower()


def token_of(value: str) -> str | None:
    """从一个取值里抽出它引用的**令牌**（var(--x) → --x）；字面量返回 None。"""
    m = re.search(r"var\(\s*(--[a-z0-9-]+)", value)
    return m.group(1) if m else None


def scan_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    rows = []
    for sel, body in RULE_RE.findall(text):
        sel = " ".join(sel.split())
        classes = CLASS_RE.findall(sel)
        if not classes:
            continue
        for prop, value in VAR_USE_RE.findall(body):
            tok = token_of(value)
            if not tok:
                continue
            for cls in classes:
                rows.append({
                    "file": str(path.relative_to(ROOT)),
                    "selector": sel[:160],
                    "cls": cls,
                    "stem": semantic_stem(cls),
                    "declProp": "--" + prop,
                    "token": tok,
                })
    return rows


def main() -> int:
    all_rows: list[dict] = []
    for g in CSS_GLOBS:
        p = ROOT / g
        if p.exists():
            all_rows.extend(scan_file(p))

    by_token: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in all_rows:
        by_token[r["token"]][r["stem"]].append(r)

    suspects = []
    for token, stems in sorted(by_token.items()):
        if len(stems) < 2:
            continue
        stems_sorted = sorted(stems)
        suspects.append({
            "token": token,
            "distinctSemanticStems": len(stems_sorted),
            "stems": {
                s: {
                    "count": len(stems[s]),
                    "classes": sorted({x["cls"] for x in stems[s]})[:8],
                    "files": sorted({x["file"] for x in stems[s]}),
                    "sampleSelector": stems[s][0]["selector"],
                }
                for s in stems_sorted
            },
        })

    suspects.sort(key=lambda x: -x["distinctSemanticStems"])
    report = {
        "tool": "tools/plan100/scan_channel_conflicts.py",
        "purpose": ("独立于 channel_audit.js 的登记表，直接扫 CSS 源码找「同一令牌被多个语义词干复用」。"
                    "粗粒度、会误报，但不会漏报 —— 用于交叉验证「conflicts=0」是否可信。"),
        "cssFilesScanned": [g for g in CSS_GLOBS if (ROOT / g).exists()],
        "assignmentsScanned": len(all_rows),
        "tokensSeen": len(by_token),
        "suspectTokens": len(suspects),
        "suspects": suspects,
        "interpretation": (
            "suspects 非空 **不等于** 一定有冲突：同一语义可能用了不同类名词干（误报）。"
            "判读方法：对每个 suspect，去看它的 stems 是否真的承载不同语义族；"
            "若 channel_audit.js 报 0 冲突而本工具仍列出该 token，必须逐条人工确认后才能签收。"
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "channel-css-independent.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"扫描 {len(report['cssFilesScanned'])} 个 CSS · {len(all_rows)} 条赋值 · "
          f"{len(by_token)} 个令牌")
    print(f"可疑复用令牌（≥2 个语义词干）: {len(suspects)}")
    for s in suspects[:15]:
        stems = " | ".join(f"{k}({v['count']})" for k, v in list(s["stems"].items())[:5])
        print(f"  {s['token']:34s} {s['distinctSemanticStems']} 族: {stems}")
    print(f"-> {artifact_rel(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
