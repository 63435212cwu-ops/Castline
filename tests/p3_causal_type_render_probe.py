#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.5 真实页面探针：因果**类型**必须显示，且「不应保留的边」必须被标出来。

为什么不能只靠 tests/sky_causal_type_contract.js：
  那个契约证明的是**分类语义**（缺字段不默认触发、随后≠因果、
  归功不得留在因果网络、反事实不是事实）。它证明不了「因果面板真的显示了类型」——
  修之前面板只显示依据（原文明确声明/事件推导/材料归纳），
  读者看不到「这条边其实是归功/评价」这类判断，而计划明令
  「不能给明显错方向边降置信度后继续保留」。

判据：
  ① 因果边行出现 [data-causal-type]，取值来自真实数据；
  ② 类型标记与「依据」不是同一个词（两件事可分辨）；
  ③ 计划点名的 `cx_luoyang_to_credit`（归功于羊祜）必须出现在页面上**且判为归功**；
  ④ 该边的 aria-label 必须写明它不应作为因果边保留；
  ⑤ 关光/低档下标记仍在 DOM 且可见。

用法：
  CL_GPU=1 python3 -B -s tests/p3_causal_type_render_probe.py --base http://127.0.0.1:8781
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
  try{ if(window.CLSkyDeconstruction&&CLSkyDeconstruction.setMode) CLSkyDeconstruction.setMode('causal'); out.causalTab=true; }catch(e){ out.modeErr=String(e); }
  return out;
})()"""

COLLECT = r"""(()=>{
  const out={};
  const rows=[...document.querySelectorAll('[data-causal-type]')];
  out.rowCount=rows.length;
  const kinds={}; rows.forEach(r=>{const k=r.getAttribute('data-causal-type')||'';kinds[k]=(kinds[k]||0)+1;});
  out.kinds=kinds;
  const first=rows[0];
  if(first){
    out.firstCode=first.getAttribute('data-causal-type');
    out.typeText=(first.querySelector('.sd-causal-type')||{}).textContent||null;
    out.basisText=(first.querySelector('.sd-causal-basis')||{}).textContent||null;
  }
  // 找目标边（归功于羊祜）
  const target=rows.find(r=>/归功于羊祜/.test(r.textContent||''));
  out.targetFound=!!target;
  if(target){
    out.targetCode=target.getAttribute('data-causal-type');
    out.targetAria=(target.getAttribute('aria-label')||'').slice(0,240);
    out.targetType=(target.querySelector('.sd-causal-type')||{}).textContent||null;
  }
  out.pager=(document.querySelector('.sd-pagination')||{}).textContent||null;
  return out;
})()"""

NEXT_PAGE = r"""(()=>{
  const b=document.querySelector('[data-action="page-next"]');
  if(!b||b.disabled) return {moved:false};
  b.click(); return {moved:true};
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const els=[...document.querySelectorAll('.sd-causal-type')];
  const vis=els.filter(e=>{const s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden';});
  return {tags:els.length, visible:vis.length};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-causal-type"))
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
        time.sleep(2.5)
        first = runner.eval(COLLECT)
        if isinstance(first, dict) and first.get("__evalError"):
            problems.append("collect_error")
            first = {}
        target = {}
        sq = runner.eval("(()=>{const b=document.querySelector('input[data-search=\"causal\"]');"
                         "if(!b) return {searchBoxPresent:false};"
                         "b.value=__Q__;b.dispatchEvent(new Event('input',{bubbles:true}));"
                         "return {searchBoxPresent:true};})()".replace("__Q__", json.dumps("归功于羊祜")))
        if isinstance(sq, dict) and sq.get("__evalError"):
            sq = {}
        time.sleep(2.5)
        got = runner.eval(COLLECT)
        if isinstance(got, dict) and got.get("targetFound"):
            target = got
        for _ in range(8):
            if (target or {}).get("targetFound"):
                break
            mv = runner.eval(NEXT_PAGE)
            if not (isinstance(mv, dict) and mv.get("moved")):
                break
            time.sleep(1.2)
            got = runner.eval(COLLECT)
            if isinstance(got, dict) and got.get("targetFound"):
                target = got
                break
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

    check("① 因果边行渲染出类型标记 [data-causal-type]",
          (first.get("rowCount") or 0) >= 1,
          "rows=%s kinds=%s" % (first.get("rowCount"), first.get("kinds")))
    check("② 类型标记与「依据」是两个不同的词",
          bool(first.get("typeText")) and bool(first.get("basisText"))
          and first.get("typeText") != first.get("basisText"),
          "type=%r basis=%r" % (first.get("typeText"), first.get("basisText")))
    check("③ 计划点名的『归功于羊祜』边必须出现在页面上且判为归功",
          bool(target.get("targetFound")) and target.get("targetCode") == "attribution",
          "found=%s code=%s type=%r" % (target.get("targetFound"), target.get("targetCode"), target.get("targetType")))
    aria = target.get("targetAria") or ""
    check("④ 该边的 aria-label 必须写明它不应作为因果边保留",
          ("不是因果机制" in aria) or ("不得当作因果边保留" in aria),
          repr(aria[-140:]))
    check("⑤ 关光/低档下类型标记仍在 DOM 且可见",
          (dim.get("visible") or 0) >= 1, "tags=%s visible=%s" % (dim.get("tags"), dim.get("visible")))

    report = {"plan_ref": "docs/QUALITY.md P3.5", "book": args.book, "graphKey": key,
              "base": args.base, "open": opened, "search": sq, "first": first, "target": target, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
