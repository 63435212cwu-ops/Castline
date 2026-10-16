#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.11 真实页面探针：主题/张力解释层为空时必须说明**为什么**。

为什么不能只靠 tests/sky_theme_tension_contract.js：
  那个契约证明的是**判定语义**（密度/死亡数/时间中点必须判伪判据、
  解释层三件套、强制框架判红但提及不算）与**计数**（162 个管线产物主题字段 0 个；
  三书 52 条线级 theme 全缺三件套）。它证明不了"面板上真的把原因说出来了"。

判据：
  ① mechanics 面板能渲染且模块已加载；
  ② 主题为空时必须有 .sd-theme-gap-note；
  ③ 该说明必须点出根因（产出清单里此前没有要求）；
  ④ 必须分清"解释层 vs 事实层"，且不得宣称作品没有主题；
  ⑤ 世界设定与主题两个空态**各自独立**判断（不得共用条件）；
  ⑥ 关光/低档下该说明仍可见。

用法：
  CL_GPU=1 python3 -B -s tests/p3_theme_tension_render_probe.py --base http://127.0.0.1:8781
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
  out.moduleLoaded=!!window.CLSkyThemeTension;
  const t=document.querySelector('.sd-theme-gap-note');
  out.themeNotePresent=!!t;
  out.themeNoteText=t?(t.textContent||'').slice(0,320):null;
  const w=document.querySelector('.sd-world-gap-note');
  out.worldNotePresent=!!w;
  out.worldNoteText=w?(w.textContent||'').slice(0,200):null;
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const el=document.querySelector('.sd-theme-gap-note');
  if(!el) return {rendered:false};
  const s=getComputedStyle(el);
  return {rendered:s.display!=='none'&&s.visibility!=='hidden'};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-theme-tension"))
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
          bool(opened.get("modeOk")) and bool(got.get("moduleLoaded")),
          "modeOk=%s module=%s err=%s" % (opened.get("modeOk"), got.get("moduleLoaded"), opened.get("modeErr")))
    note = got.get("themeNoteText") or ""
    check("② 主题为空时必须有 .sd-theme-gap-note", bool(got.get("themeNotePresent")), repr(note[:130]))
    check("③ 说明必须点出根因：产出清单里此前没有要求",
          ("产出清单" in note) and ("没有要求" in note), repr(note[:200]))
    check("④ 必须分清解释层与事实层，且不得宣称作品没有主题",
          ("解释层" in note) and ("事实层" in note) and ("不由此判定" in note), repr(note[-140:]))
    check("⑤ 世界设定与主题两个空态各自独立出现（不得共用条件）",
          bool(got.get("worldNotePresent")) != bool(got.get("themeNotePresent")) or
          (bool(got.get("worldNotePresent")) and note != (got.get("worldNoteText") or "")),
          "world=%s theme=%s" % (got.get("worldNotePresent"), got.get("themeNotePresent")))
    check("⑥ 关光/低档下该说明仍可见",
          bool((dim or {}).get("rendered")), "dim=%s" % (dim,))

    report = {"plan_ref": "docs/QUALITY.md P3.11", "book": args.book, "graphKey": key,
              "base": args.base, "open": opened, "collect": got, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
