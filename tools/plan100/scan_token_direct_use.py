#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P05-W04B · 面板语义色「直接用法」扫描（补两条现有路径的盲区）。

为什么需要第三个工具
--------------------
修完 4 处冲突后，本轮又发现 **2 处同形状缺陷**（伏笔阶段徽记借用了
`--skd-mint` / `--skd-brass`），而它们对既有两条检查路径**都不可见**：

  1. `tools/plan100/channel_audit.js` 的登记表——手工登记，没登记就查不到；
  2. `tools/plan100/scan_channel_conflicts.py`——它的 `VAR_USE_RE` 是
     `--([a-z0-9-]+)\\s*:\\s*([^;}]+)`，**只匹配自定义属性声明** `--x: var(--tok)`，
     而伏笔徽记写的是直接用法 `color: var(--skd-mint)`，正则根本不匹配。

结论：**任何只扫 `--x: var(...)` 的检查都会漏掉直接用法**。本工具补这个洞：
它枚举面板作用域内**每一条** `prop: ... var(--tok) ...`，不管左边是不是自定义属性，
然后按「token → 语义词干集合」找跨族复用。

它比 scan_channel_conflicts.py 更严（覆盖直接用法），但也更粗（按类名词干聚类会误报）。
定位：**第三路交叉验证**，与前两条互为补充，任一条报警都要人工判读。

用法：
  python3 tools/plan100/scan_token_direct_use.py [--json <out>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT = artifact_path() / "plan100" / "projection" / "channel-direct-use.json"

CSS_FILES = ["css/sky-deep-hud.css", "css/sky-reading.css"]

RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
DECL_RE = re.compile(r"(?:^|;)\s*([a-zA-Z-]+)\s*:\s*([^;}]*)")
VAR_RE = re.compile(r"var\(\s*(--[a-z0-9-]+)")
CLASS_RE = re.compile(r"\.([a-zA-Z][\w-]*)")

SEMANTIC_RE = re.compile(r"^--(skd|sky|abyss)-(mint|cool|violet|brass|oppose|star|branch|cause|fore|ink-3|signal|camp)")

PANEL_SEL_RE = re.compile(r"^\s*\.sd-")

STEM_FAMILY = {
    "event": "evidence", "evidence": "evidence", "source": "evidence",
    "summary": "evidence", "derived": "evidence", "unknown": "evidence",
    "quote": "evidence", "meter": "evidence", "counts": "evidence",
    "cause": "causal-role", "causal": "causal-role",
    "branch": "topology",
    "fore": "foreshadow", "stage": "foreshadow",
    "key": "availability", "dormant": "availability",
}


def stem(cls: str) -> str:
    c = cls.lower()
    for pfx in ("is-", "has-", "sd-", "skc-", "cl-", "afb-", "sky-"):
        if c.startswith(pfx):
            c = c[len(pfx):]
            break
    return re.split(r"[-_]", c)[0] if c else cls.lower()


def family(cls: str) -> str:
    """返回类名承载的语义族；非语义类名返回自身词干（因此不会与数据族相撞）。"""
    return STEM_FAMILY.get(stem(cls), stem(cls))


def scan(path: Path) -> list[dict]:
    text = COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
    rows = []
    for sel, body in RULE_RE.findall(text):
        sel = " ".join(sel.split())
        if not PANEL_SEL_RE.match(sel):
            continue
        classes = CLASS_RE.findall(sel)
        if not classes:
            continue
        for prop, value in DECL_RE.findall(body + ";"):
            for tok in VAR_RE.findall(value):
                if not SEMANTIC_RE.match(tok):
                    continue
                rows.append({
                    "file": str(path.relative_to(ROOT)),
                    "selector": sel[:160],
                    "classes": classes,
                    "families": sorted({family(c) for c in classes}),
                    "prop": prop,
                    "isCustomPropDecl": prop.startswith("--"),
                    "token": tok,
                })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(artifact_rel(OUT)))
    args = ap.parse_args()

    rows: list[dict] = []
    for f in CSS_FILES:
        p = ROOT / f
        if p.exists():
            rows.extend(scan(p))

    by_token: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for fam in r["families"]:
            by_token[r["token"]][fam].append(r)

    suspects = []
    for tok, fams in sorted(by_token.items()):
        if len(fams) < 2:
            continue
        suspects.append({
            "token": tok,
            "distinctFamilies": len(fams),
            "families": {
                f: {
                    "count": len(v),
                    "selectors": sorted({x["selector"] for x in v})[:6],
                    "viaCustomPropDecl": any(x["isCustomPropDecl"] for x in v),
                    "viaDirectUse": any(not x["isCustomPropDecl"] for x in v),
                }
                for f, v in sorted(fams.items())
            },
        })
    suspects.sort(key=lambda x: -x["distinctFamilies"])

    report = {
        "tool": "tools/plan100/scan_token_direct_use.py",
        "purpose": ("补两条既有路径的盲区：登记表靠手工，scan_channel_conflicts.py 只匹配 "
                    "`--x: var(--tok)` 声明。本工具枚举**直接用法** `color: var(--tok)`，"
                    "按「token → 语义族集合」找跨族复用。"),
        "blindSpotClosed": ("scan_channel_conflicts.py 的 VAR_USE_RE 只匹配自定义属性声明；"
                            "伏笔徽记 `color: var(--skd-mint)` 这类直接用法它看不见。"),
        "filesScanned": [f for f in CSS_FILES if (ROOT / f).exists()],
        "assignmentsScanned": len(rows),
        "tokensSeen": len(by_token),
        "suspectTokens": len(suspects),
        "suspects": suspects,
        "interpretation": ("suspects 非空不等于一定有冲突（同族可能用了不同词干）。"
                           "判读：看 families 里是否真有**不同语义族**，且两者能否同屏共存。"),
    }
    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"扫描 {len(report['filesScanned'])} 个 CSS · {len(rows)} 条含语义令牌的声明"
          f"（其中直接用法 {sum(1 for r in rows if not r['isCustomPropDecl'])} 条）"
          f" · {len(by_token)} 个令牌")
    print(f"跨语义族复用令牌: {len(suspects)}")
    for s in suspects:
        fams = " | ".join(f"{k}({v['count']})" for k, v in s["families"].items())
        print(f"  {s['token']:34s} {s['distinctFamilies']} 族: {fams}")
    print(f"-> {artifact_rel(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
