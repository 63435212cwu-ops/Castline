#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P07 · 材质层清单生成器（可复现）。

把 `js/core/material-layers.js` 的 `CLLayerRegistry` 导出成
`tests/fixtures/contracts/material/layer-inventory.json`，并**逐条核实**每层记录的
`代码位置 file:line` 真的指向含有该 uniform 的那一行 —— 行号漂移必须当场失败，
不允许台账里留着对不上的坐标。

用法：
  python3 -s tools/plan100/material_layer_inventory.py            # 生成到系统临时目录（显式 --out 才覆盖指定路径）
  python3 -s tools/plan100/material_layer_inventory.py --check     # 只校验，不写（CI/accept 用）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path
REGISTRY = ROOT / "js/core/material-layers.js"
SHADERS = {
    "js/core/scene-mats.js": ROOT / "js/core/scene-mats.js",
    "js/sky/sky-rings-glsl.js": ROOT / "js/sky/sky-rings-glsl.js",
}
OUT = artifact_path("plan100/material/layer-inventory.json")
BASELINE = ROOT / "tests/fixtures/contracts/material/layer-inventory.json"

NODE_CANDIDATES = [
    "node",
]


def node_bin() -> str:
    """找 node。**不写死版本号**，且不依赖 PATH 上是否还有效。

    实测事故（2026-10-09）：workbuddy 把 Node 从 `22.22.2-3` 换成 `22.22.2-6`
    并删掉旧目录，而 PATH 里仍留着那个**已删除的路径** ⇒ 原先只查
    `shutil.which('node')` 会失败，报 `BLOCKED: node not found`，
    看起来像功能缺失，实际是工具链解析。
    解析顺序：ATLAS_NODE → NODE_CANDIDATES → versions/ 下最高版本。
    """
    import shutil
    env = os.environ.get("ATLAS_NODE")
    if env and Path(env).is_file():
        return env
    for c in NODE_CANDIDATES:
        p = shutil.which(c) if "/" not in c else (c if Path(c).is_file() else None)
        if p:
            return p
    base = Path("/Users/carmen/.workbuddy/binaries/node/versions")
    if base.is_dir():
        cands = sorted([d for d in base.iterdir() if d.is_dir() and d.name[:1].isdigit()],
                       key=lambda d: [int(x) for x in d.name.split(".") if x.isdigit()] or [0])
        if cands and (cands[-1] / "bin" / "node").is_file():
            return str(cands[-1] / "bin" / "node")
    raise SystemExit("BLOCKED: node not found; cannot evaluate the layer registry")


def load_registry() -> dict:
    """在 node 里执行注册表（它是 IIFE，挂在 window 上），拿到结构化导出。"""
    js = (
        "const fs=require('fs');"
        f"const src=fs.readFileSync({json.dumps(str(REGISTRY))},'utf8');"
        "const sb={navigator:{hardwareConcurrency:8}};"
        "const R=new Function('window','navigator',src+'\\nreturn window.CLLayerRegistry;')(sb,sb.navigator);"
        "process.stdout.write(JSON.stringify({"
        "layers:R.inventory().map(L=>({id:L.id,label:L.label,shader:L.shader,uniform:L.uniform,"
        "on:L.on,off:L.off,structure:L.structure,anchor:L.anchor,baseline:L.baseline,"
        "effect:L.effect,metric:L.metric,note:L.note||null}))}));"
    )
    out = subprocess.run([node_bin(), "-e", js], capture_output=True, text=True, cwd=ROOT)
    if out.returncode != 0:
        raise SystemExit(f"BLOCKED: registry evaluation failed:\n{out.stderr}")
    return json.loads(out.stdout)


def line_of(src: str, needle: str) -> int | None:
    i = src.find(needle)
    return None if i < 0 else src[:i].count("\n") + 1


def build() -> dict:
    reg = load_registry()
    srcs = {k: v.read_text(encoding="utf-8") for k, v in SHADERS.items()}
    rows, problems = [], []
    for L in reg["layers"]:
        host = "js/sky/sky-rings-glsl.js" if L["shader"] == "RF" else "js/core/scene-mats.js"
        src = srcs[host]
        line = line_of(src, L["anchor"])
        if line is None:
            problems.append(f"{L['id']}: anchor not found in {host}")
            line = 0
        else:
            text = src.split("\n")[line - 1]
            if L["uniform"] not in text:
                problems.append(f"{L['id']}: line {line} of {host} does not contain {L['uniform']}")
        rows.append({
            "layer": L["id"], "label": L["label"], "shader": L["shader"],
            "codeLocation": f"{host}:{line}",
            "uniform": L["uniform"],
            "defaultValue": L["on"], "offValue": L["off"],
            "independentlyToggleable": True,
            "switchMechanism": "ShaderMaterial uniform (float 0/1)",
            "wiredAt": f"{host}:{line}",
            "currentContribution": L["effect"],
            "measurableEffect": L["metric"],
            "structureCritical": L["structure"],
            "rollbackBaseline": L["baseline"],
            "note": L["note"],
        })
    ring = [r for r in rows if r["shader"] == "RF"]
    return {
        "tool": "tools/plan100/material_layer_inventory.py",
        "contract": "tests/material_layers_contract.js",
        "registry": "js/core/material-layers.js (window.CLLayerRegistry)",
        "planRef": "plan100 P07「隔离晶体体积/表面/透射/反射/加性层和星盘光环截面，逐项同帧 A/B」",
        "requirement6": "每个候选必须有：基线、单变量补丁、A/B 截图或逐帧记录、CPU 契约、GPU 记录、回滚说明",
        "requirement4": "原生4K、自动降档、低画质、减弱动态、WebGL fallback 均保留结构信息",
        "isolationPrinciple": ("每个开关 = 一条贡献路径。off 只削弱该层自己的算式，不重算任何其他层的数值"
                               "（单变量性）。默认值 = 当前生产行为（可回滚）。"),
        "entryPoints": {
            "registry": "window.CLLayerRegistry (js/core/material-layers.js)",
            "crystalAssembly": ("CLSceneMats.LAYER_SWITCHES（单点默认值表）-> CLSceneMats.gemMat -> "
                                "uniforms uLyrVolume/uLyrBackAtt/uLyrSurface/uLyrRough/uLyrTrans/uLyrInner/uLyrRefl/uLyrAdd"),
            "ringAssembly": "js/sky/sky-rings.js create() -> u.uLyrDome/u.uLyrConc/u.uLyrAstro/u.uLyrFloor",
        },
        "layerCount": len(rows),
        "layers": rows,
        "summary": {
            "crystalLayers": len(rows) - len(ring),
            "ringLayers": len(ring),
            "independentlyToggleable": len(rows),
            "structureCritical": [r["layer"] for r in rows if r["structureCritical"]],
            "defaultEqualsProduction": all(r["defaultValue"] == 1 for r in rows),
        },
        "codeLocationCheck": {"ok": not problems, "problems": problems},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="只校验（行号必须对得上），不写文件")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    doc = build()
    if doc["codeLocationCheck"]["problems"]:
        print("FAIL: recorded code locations do not match the source:", file=sys.stderr)
        for p in doc["codeLocationCheck"]["problems"]:
            print("  " + p, file=sys.stderr)
        return 1

    if args.check:
        if not BASELINE.is_file():
            print(f"FAIL: required material fixture missing: {BASELINE}", file=sys.stderr)
            return 2
        cur = json.loads(BASELINE.read_text(encoding="utf-8"))
        if json.dumps(cur.get("layers"), ensure_ascii=False, sort_keys=True) != \
           json.dumps(doc["layers"], ensure_ascii=False, sort_keys=True):
            print("FAIL: layer-inventory.json is stale; review changes before updating the fixture", file=sys.stderr)
            return 1
        print(f"LAYER INVENTORY OK · {doc['layerCount']} layers · "
              f"{doc['summary']['crystalLayers']} crystal + {doc['summary']['ringLayers']} ring · "
              f"all code locations verified")
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} · {doc['layerCount']} layers "
          f"({doc['summary']['crystalLayers']} crystal + {doc['summary']['ringLayers']} ring)")
    for r in doc["layers"]:
        print(f"  {r['layer']:14s} {r['codeLocation']:34s} {r['uniform']:12s} "
              f"default={r['defaultValue']} off={r['offValue']}"
              f"{'  [structure]' if r['structureCritical'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
