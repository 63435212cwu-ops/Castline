#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.10 真实页面探针：世界设定面为空时必须说明**为什么**。

为什么不能只靠 tests/sky_world_object_contract.js：
  那个契约证明的是**判定语义**（提及≠到达、物件四态、制度三态、无约束不算能解释行动、
  0 条须说"从未被要求过"）与**计数**（3 图谱 + 160+ 管线产物世界设定 0 条；
  荆州 420 次提及 / 95 次到达式）。它证明不了"面板上真的把原因说出来了" ——
  实测本类的根因是提示词产出清单里从未要求，若不写明，
  读者会把「没有世界规则」当成作品的属性。

判据：
  ① states/mechanics 面板必须能渲染（不抛错）；
  ② 世界设定为空时必须有 .sd-world-gap-note；
  ③ 该说明必须点出根因（产出清单里没有要求提取）；
  ④ 必须明说「这不是作品没有设定」，不得让读者误解；
  ⑤ 关光/低档下该说明仍可见。

用法：
  CL_GPU=1 python3 -B -s tests/p3_world_object_render_probe.py --base http://127.0.0.1:8781
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

BOOKS = {"sanguo": "fe42d01f3826fe8096f86614"}

OPEN = r"""(()=>{
  const out={};
  try{ if(window.CLSky&&CLSky.setDecon) CLSky.setDecon(true); }catch(e){ out.err=String(e); }
  try{
    CLSkyDeconstruction.open();
    CLSkyDeconstruction.setMode('mechanics');
    out.modeOk=true;
  }catch(e){ out.modeOk=false; out.modeErr=String(e); }
  return out;
})()"""

COLLECT = r"""(()=>{
  const out={};
  out.panel=!!document.querySelector('#skyDeconPanel');
  out.mechanics=document.querySelectorAll('.sd-mechanics').length;
  const note=document.querySelector('.sd-world-gap-note');
  out.notePresent=!!note;
  out.noteText=note?(note.textContent||'').slice(0,320):null;
  // 模块必须在页面上可用
  out.moduleLoaded=!!window.CLSkyWorldObject;
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const el=document.querySelector('.sd-world-gap-note');
  if(!el) return {rendered:false};
  const s=getComputedStyle(el);
  return {rendered:s.display!=='none'&&s.visibility!=='hidden'};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-world-object"))
    ap.add_argument("--book", default="sanguo", choices=sorted(BOOKS))
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
        opened = runner.eval(OPEN)
        if isinstance(opened, dict) and opened.get("__evalError"):
            opened = {}
        time.sleep(2.5)
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

    check("① mechanics 面板能渲染且模块已加载",
          bool(opened.get("modeOk")) and bool(got.get("moduleLoaded")) and (got.get("mechanics") or 0) >= 1,
          "modeOk=%s module=%s mechanics=%s err=%s" % (opened.get("modeOk"), got.get("moduleLoaded"),
                                                       got.get("mechanics"), opened.get("modeErr")))
    note = got.get("noteText") or ""
    check("② 世界设定为空时必须有 .sd-world-gap-note",
          bool(got.get("notePresent")), repr(note[:150]))
    check("③ 说明必须点出根因：产出清单里没有要求提取",
          ("产出清单" in note) and ("没有要求" in note), repr(note[:200]))
    check("④ 必须明说「这不是作品没有设定」，不得让读者误解",
          "不是「作品没有设定」" in note or "这不是作品没有设定" in note, repr(note[-120:]))
    check("⑤ 关光/低档下该说明仍可见",
          bool((dim or {}).get("rendered")), "dim=%s" % (dim,))

    report = {"plan_ref": "docs/QUALITY.md P3.10", "book": args.book, "graphKey": key,
              "base": args.base, "open": opened, "collect": got, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
