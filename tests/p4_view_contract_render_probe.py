#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4.1 真实页面探针：**切图前读者能预期下一图解决什么问题**。

为什么不能只靠 tests/sky_view_contract.js：
  那个契约证明的是**登记语义**（唯一主问题、五项声明齐全、跨图含义冲突、
  旧入口隔离）。它证明不了「界面上真的把主问题告诉了读者」——
  而本包的核心验收恰恰是「切图前读者能预期下一图解决什么问题」。

判据：
  ① 视图按钮的 title 必须写明「这个问题：…」；
  ② aria-description 必须写明主问题（读屏用户同样要能预期）；
  ③ 不同视图的主问题必须不同（不得四个图同一句话）；
  ④ 旧入口按钮必须显式标「兼容入口」，且带 data-legacy-entry；
  ⑤ 关光/静止下这些属性仍在（它们是属性不是颜色，应不受影响）；
  ⑥ 登记表与页面不得出现两套说法（title 里的问题串必须来自登记表）。

用法：
  CL_GPU=1 python3 -B -s tests/p4_view_contract_render_probe.py --base http://127.0.0.1:8781
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from qa_cinema_wave02_capture import Wave2AuditRunner

BOOKS = {"dafeng": "1063b17ca65ec1b76f30e460"}

COLLECT = r"""(()=>{
  const out={};
  out.module=!!window.CLSkyViewContract;
  const ids=['btnStage','btnAtlas','btnDual','btnPreview'];
  out.views={};
  ids.forEach(function(id){
    const el=document.getElementById(id);
    if(!el){ out.views[id]=null; return; }
    out.views[id]={
      title: el.getAttribute('title')||'',
      ariaDesc: el.getAttribute('aria-description')||'',
      legacy: el.getAttribute('data-legacy-entry')||''
    };
  });
  // 登记表里的四个问题，用于比对
  out.registry = window.CLSkyViewContract
    ? Object.keys(window.CLSkyViewContract.VIEWS).map(function(k){
        return window.CLSkyViewContract.VIEWS[k].question; })
    : null;
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const el=document.getElementById('btnStage');
  return {title: el?(el.getAttribute('title')||''):'', ariaDesc: el?(el.getAttribute('aria-description')||''):''};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p4-view-contract"))
    ap.add_argument("--book", default="dafeng", choices=sorted(BOOKS))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    key = BOOKS[args.book]

    problems, checks = [], []
    runner = Wave2AuditRunner(width=1440, height=900, dpr=1)
    try:
        runner.start()
        runner.navigate("%s/?sky=1&data=data/cache/%s.json" % (args.base, key))
        end = time.time() + 150
        while time.time() < end:
            if runner.eval("!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector('#loader.off'))") is True:
                break
            time.sleep(0.4)
        time.sleep(4)
        got = runner.eval(COLLECT)
        if isinstance(got, dict) and got.get("__evalError"):
            got = {}
        time.sleep(0.8)
        dim = runner.eval(DIM)
        if isinstance(dim, dict) and dim.get("__evalError"):
            dim = {}
    finally:
        try:
            runner.close()
        except Exception:
            pass

    def check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            problems.append(name)
        print(("PASS " if ok else "FAIL ") + name + "  · " + str(detail), flush=True)

    views = got.get("views") or {}
    stage = views.get("btnStage") or {}
    dual = views.get("btnDual") or {}
    prev = views.get("btnPreview") or {}

    check("① 视图按钮 title 必须写明「这个问题：…」",
          "这个问题：" in (stage.get("title") or ""),
          repr((stage.get("title") or "")[:160]))
    check("② aria-description 必须写明主问题（读屏也要能预期）",
          bool((stage.get("ariaDesc") or "").strip()) and "？" in (stage.get("ariaDesc") or ""),
          repr((stage.get("ariaDesc") or "")[:120]))
    reg = got.get("registry") or []
    check("③ 登记表必须恰好四个主问题且互不相同",
          len(reg) == 4 and len(set(reg)) == 4,
          "registry=%s" % (reg,))
    check("④ 旧入口按钮必须标「兼容入口」并带 data-legacy-entry",
          "兼容入口" in (prev.get("title") or "") and bool(prev.get("legacy")),
          "legacy=%r title=%r" % (prev.get("legacy"), (prev.get("title") or "")[-70:]))
    check("⑤ 关光/静止下这些属性仍在（属性不依赖颜色）",
          "这个问题：" in (dim.get("title") or ""),
          repr((dim.get("title") or "")[:110]))
    check("⑥ 页面 title 里的问题串必须来自登记表（不得两套说法）",
          bool(reg) and any(q in (stage.get("title") or "") for q in reg),
          "stage title 含登记表问题：%s" % [q for q in reg if q in (stage.get("title") or "")])
    check("⑦ 不同视图不得显示同一个主问题",
          bool(dual.get("ariaDesc")) and dual.get("ariaDesc") != stage.get("ariaDesc"),
          "stage=%r dual=%r" % ((stage.get("ariaDesc") or "")[:40], (dual.get("ariaDesc") or "")[:40]))

    report = {"plan_ref": "docs/QUALITY.md P4.1", "book": args.book, "graphKey": key,
              "base": args.base, "collect": got, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
