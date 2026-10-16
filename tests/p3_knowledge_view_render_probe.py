#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.8 真实页面探针：知情面为空时必须说明**为什么**，而且面板必须真的能渲染。

为什么不能只靠 tests/sky_knowledge_view_contract.js：
  那个契约证明的是**判定语义**（六分、叙述者不得灌给人物、沉默不证明知情、
  时代错置）与两个**结构性缺口**的计数（管线 523 条 vs 已发布图谱 0 条）。
  它证明不了「面板真的能打开、且空的时候说清了原因」——
  而本包实测就发现 states 面板一打开就抛 `kb is not defined`（渲染直接失败），
  契约完全测不到这一类。

判据：
  ① states 模式必须能渲染（不抛错）—— 实测修前抛 `kb is not defined`；
  ② 面板出现 .sd-state-reading；
  ③ 知情面为空时必须有 .sd-knowledge-gap-note，且说明「尚未接线」而非「人物不知情」；
  ④ 该说明必须点出真实原因（管线已有结论 / 未进入当前图谱版本 / 模型读的字段不存在）；
  ⑤ 关光/低档下面板仍可渲染。

用法：
  CL_GPU=1 python3 -B -s tests/p3_knowledge_view_render_probe.py --base http://127.0.0.1:8781
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

OPEN = r"""(()=>{
  const out={};
  try{ if(window.CLSky&&CLSky.setDecon) CLSky.setDecon(true); }catch(e){ out.err=String(e); }
  try{
    CLSkyDeconstruction.open();
    CLSkyDeconstruction.setMode('states');
    out.modeOk=true;
  }catch(e){ out.modeOk=false; out.modeErr=String(e); }
  return out;
})()"""

COLLECT = r"""(()=>{
  const out={};
  out.panel=!!document.querySelector('#skyDeconPanel');
  out.stateReading=document.querySelectorAll('.sd-state-reading').length;
  out.stateRows=document.querySelectorAll('[data-state-nature]').length;
  const note=document.querySelector('.sd-knowledge-gap-note');
  out.notePresent=!!note;
  out.noteText=note?(note.textContent||'').slice(0,300):null;
  const stats=document.querySelector('.sd-state-reading .sd-stats');
  out.statsText=stats?(stats.textContent||'').replace(/\s+/g,' ').slice(0,120):null;
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const el=document.querySelector('.sd-state-reading');
  if(!el) return {rendered:false};
  const s=getComputedStyle(el);
  return {rendered:s.display!=='none'&&s.visibility!=='hidden'};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-knowledge-view"))
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

    check("① states 模式必须能渲染（不得抛错）",
          bool(opened.get("modeOk")), "modeOk=%s err=%s" % (opened.get("modeOk"), opened.get("modeErr")))
    check("② 面板出现 .sd-state-reading",
          (got.get("stateReading") or 0) >= 1,
          "stateReading=%s stateRows=%s stats=%r" % (got.get("stateReading"), got.get("stateRows"), got.get("statsText")))
    note = got.get("noteText") or ""
    check("③ 知情面为空时必须说明原因，且不得说成「人物不知情」",
          bool(got.get("notePresent")) and ("尚未接线" in note) and ("不代表人物没有知情差异" in note),
          repr(note[:150]))
    check("④ 说明必须点出真实原因（管线已有结论 / 未进入当前图谱版本 / 模型字段不存在）",
          ("knowledgeGaps" in note) and ("图谱版本" in note or "characters[].knowledge" in note),
          repr(note[:200]))
    check("⑤ 关光/低档下面板仍可渲染",
          bool((dim or {}).get("rendered")), "dim=%s" % (dim,))

    report = {"plan_ref": "docs/QUALITY.md P3.8", "book": args.book, "graphKey": key,
              "base": args.base, "open": opened, "collect": got, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
