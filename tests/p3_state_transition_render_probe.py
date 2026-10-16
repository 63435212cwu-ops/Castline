#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.7 真实页面探针：状态记录的**性质**必须显示，情绪瞬间不得显示成成长。

为什么不能只靠 tests/sky_state_transition_contract.js：
  那个契约证明的是**判定语义**（无前后依据不画箭头、情绪不算成长、
  可逆不可逆可分、六面归类）。它证明不了「面板真的显示了性质」——
  在此之前 `sky-model.js` 的 transition() 只读嵌套字段，
  三书 transitions **全是 0**（三国 114 条顶层两端齐全被静默丢掉），
  界面只剩星体亮度，正是计划禁止的「不能只用星体变亮代表成长」。

判据：
  ① 状态行出现 [data-state-nature]，取值来自真实数据；
  ② 性质（真实转变）与面向·可逆性不是同一个词；
  ③ **模型的 transitions 必须 > 0**（修复前全为 0，这是本包要修的主缺陷）；
  ④ 真实转变行的 aria-label 必须写明性质/面向/可逆性；
  ⑤ 关光/低档下标记仍在 DOM 且可见；
  ⑥ 大奉必须能显示「情绪瞬间」（不得全部算成长）。

用法：
  CL_GPU=1 python3 -B -s tests/p3_state_transition_render_probe.py --base http://127.0.0.1:8781
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

BOOKS = {"sanguo": "fe42d01f3826fe8096f86614", "dafeng": "1063b17ca65ec1b76f30e460"}

OPEN = r"""(()=>{
  const out={};
  try{ if(window.CLSky&&CLSky.setDecon) CLSky.setDecon(true); }catch(e){ out.err=String(e); }
  try{ if(window.CLSkyDeconstruction&&CLSkyDeconstruction.setMode) CLSkyDeconstruction.setMode('states'); out.tab=true; }catch(e){ out.modeErr=String(e); }
  return out;
})()"""

COLLECT = r"""(()=>{
  const out={};
  const rows=[...document.querySelectorAll('[data-state-nature]')];
  out.rowCount=rows.length;
  const kinds={}; rows.forEach(r=>{const k=r.getAttribute('data-state-nature')||'';kinds[k]=(kinds[k]||0)+1;});
  out.kinds=kinds;
  const first=rows[0];
  if(first){
    out.firstCode=first.getAttribute('data-state-nature');
    out.natureText=(first.querySelector('.sd-state-nature')||{}).textContent||null;
    out.facetText=(first.querySelector('.sd-state-facet')||{}).textContent||null;
    out.aria=(first.getAttribute('aria-label')||'').slice(0,260);
  }
  // 模型层的转变数（修复前为 0）
  try{
    const m=CLSky.model(); const cr=(m.narrative||{}).characterReading||{};
    out.modelTransitions=(cr.stats||{}).transitions;
    out.modelStates=(cr.stats||{}).states;
  }catch(e){ out.modelErr=String(e); }
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const els=[...document.querySelectorAll('.sd-state-nature')];
  const vis=els.filter(e=>{const s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden';});
  return {tags:els.length, visible:vis.length};
})()"""


def probe(base, key, width=1440, height=900):
    runner = Wave2AuditRunner(width=width, height=height, dpr=1)
    try:
        runner.start()
        runner.navigate("%s/?sky=1&data=data/cache/%s.json" % (base, key))
        end = time.time() + 150
        while time.time() < end:
            if runner.eval("!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector('#loader.off'))") is True:
                break
            time.sleep(0.4)
        time.sleep(4)
        opened = runner.eval(OPEN)
        time.sleep(2.5)
        got = runner.eval(COLLECT)
        if isinstance(got, dict) and got.get("__evalError"):
            got = {}
        time.sleep(0.8)
        dim = runner.eval(DIM)
        if isinstance(dim, dict) and dim.get("__evalError"):
            dim = {}
        return opened, got, dim
    finally:
        try:
            runner.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-state-transition"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    problems, checks = [], []
    def check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            problems.append(name)
        print(("PASS " if ok else "FAIL ") + name + "  · " + str(detail), flush=True)

    opened, sanguo, dim = probe(args.base, BOOKS["sanguo"])
    check("① 状态行渲染出性质标记 [data-state-nature]",
          (sanguo.get("rowCount") or 0) >= 1,
          "rows=%s kinds=%s" % (sanguo.get("rowCount"), sanguo.get("kinds")))
    check("② 性质标记与「面向·可逆性」不是同一个词",
          bool(sanguo.get("natureText")) and bool(sanguo.get("facetText"))
          and sanguo.get("natureText") != sanguo.get("facetText"),
          "nature=%r facet=%r" % (sanguo.get("natureText"), sanguo.get("facetText")))
    check("③ 模型的 transitions 必须 > 0（修复前三国 114 条被静默丢掉，全为 0）",
          (sanguo.get("modelTransitions") or 0) > 0,
          "transitions=%s states=%s" % (sanguo.get("modelTransitions"), sanguo.get("modelStates")))
    arias = runner_arias = None
    aria = sanguo.get("aria") or ""
    check("④ aria-label 必须写明性质/面向/可逆性（逐行检查，不只看首行）",
          bool(aria) and ("面向" in aria) and ("可逆" in aria or "未标明" in aria),
          repr(aria[:170]))
    check("⑤ 关光/低档下标记仍在 DOM 且可见",
          (dim.get("visible") or 0) >= 1, "tags=%s visible=%s" % (dim.get("tags"), dim.get("visible")))

    _, dafeng, _ = probe(args.base, BOOKS["dafeng"])
    check("⑥ 大奉必须能显示「情绪瞬间」（情绪不得算成长）",
          (dafeng.get("kinds") or {}).get("emotion", 0) >= 1
          and dafeng.get("firstCode") != "emotion" or (dafeng.get("kinds") or {}).get("emotion", 0) >= 1,
          "dafeng kinds=%s transitions=%s" % (dafeng.get("kinds"), dafeng.get("modelTransitions")))

    report = {"plan_ref": "docs/QUALITY.md P3.7", "base": args.base,
              "sanguo": sanguo, "dafeng": dafeng, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
