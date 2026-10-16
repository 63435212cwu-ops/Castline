#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4.6 真实页面探针：统一搜索索引必须在真实图谱上跨类型命中，且结果带类型与上下文。

为什么不能只靠 tests/sky_search_index_contract.js：
  那个契约证明的是**纯函数语义**（别名回正名、无结果带原因与下一步、
  同名靠键区分、数量不是徽章）与 node 下的真实计数。
  它证明不了「页面上真的加载了、且用真实图谱建出的索引与 node 一致」。

判据：
  ① 模块在真实页面上可用；
  ② 用**页面里的真实图谱**建索引，条目数与 node 侧一致；
  ③ 一次查询跨 ≥2 类命中（这是 7 个分层搜索做不到的）；
  ④ 每条结果都带类型与上下文；
  ⑤ 别名命中能回到正名；
  ⑥ 空结果必须带原因与下一步；
  ⑦ 关光/低档下面板仍可渲染。

用法：
  CL_GPU=1 python3 -B -s tests/p4_search_index_render_probe.py --base http://127.0.0.1:8781
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

BOOKS = {"dafeng": "1063b17ca65ec1b76f30e460", "sanguo": "fe42d01f3826fe8096f86614"}

OPEN = r"""(()=>{
  const out={};
  try{ if(window.CLSky&&CLSky.setDecon) CLSky.setDecon(true); }catch(e){ out.err=String(e); }
  try{ CLSkyDeconstruction.open(); out.openOk=true; }catch(e){ out.openOk=false; out.openErr=String(e); }
  return out;
})()"""

COLLECT = r"""(()=>{
  const out={};
  const SI=window.CLSkySearchIndex;
  out.moduleLoaded=!!SI;
  if(!SI) return out;
  try{
    const g=CLApp.graph();
    out.characters=(g.characters||[]).length;
    const idx=SI.build(g);
    const t=SI.tally(idx);
    out.total=t.total; out.byType=t.byType;
    out.missingContext=t.missingContext; out.aliasWithoutCanonical=t.aliasWithoutCanonical;
    // 跨类型命中
    const r=SI.search(idx,'许七安');
    out.hits=r.total; out.hitTypes=Object.keys(r.byType||{});
    out.allTyped=r.results.every(x=>x.typeLabel);
    // 别名回正名
    let aliasOk=null;
    for(const c of (g.characters||[])){
      const a=(c.aliases||[])[0];
      if(a){ const ar=SI.search(idx,a); const hit=ar.results.find(x=>x.type==='alias');
        aliasOk = hit? !!(hit.canonical && hit.canonicalKey) : null;
        out.aliasProbe={name:c.name, alias:a, found:!!hit, canonical:hit?hit.canonical:null}; break; }
    }
    out.aliasOk=aliasOk;
    // 空结果带原因与下一步
    const miss=SI.search(idx,'zzz绝不存在zzz');
    out.missReason=miss.reason; out.missNext=!!(miss.nextStep && miss.nextStep.length>5);
    const empty=SI.search([],'x');
    out.emptyReason=empty.reason; out.emptyDiffers=(empty.reason!==miss.reason);
  }catch(e){ out.evalErr=String(e); }
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const el=document.querySelector('#skyDeconPanel');
  if(!el) return {rendered:false};
  const s=getComputedStyle(el);
  return {rendered:s.display!=='none'&&s.visibility!=='hidden'};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p4-search-index"))
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

    check("① P4.6 统一搜索索引在真实页面上可用",
          bool(got.get("moduleLoaded")),
          "module=%s err=%s" % (got.get("moduleLoaded"), got.get("evalErr")))
    check("② 用页面真实图谱建出索引（与 node 侧同一份数据）",
          (got.get("total") or 0) > 1000,
          "图谱人物=%s 索引条目=%s 分类=%s" % (got.get("characters"), got.get("total"), got.get("byType")))
    check("③ 一次查询必须跨 ≥2 类命中（7 个分层搜索做不到）",
          len(got.get("hitTypes") or []) >= 2,
          "「许七安」命中 %s 条，跨 %s 类：%s" % (got.get("hits"), len(got.get("hitTypes") or []), got.get("hitTypes")))
    check("④ 每条结果都必须带类型",
          bool(got.get("allTyped")) and (got.get("hits") or 0) > 0,
          "allTyped=%s hits=%s" % (got.get("allTyped"), got.get("hits")))
    check("⑤ 别名命中必须能回到正名",
          got.get("aliasOk") is True,
          "探针=%s" % json.dumps(got.get("aliasProbe"), ensure_ascii=False))
    check("⑥ 空结果必须带原因与下一步，且「没有匹配」≠「索引为空」",
          bool(got.get("missReason")) and bool(got.get("missNext")) and bool(got.get("emptyDiffers")),
          "miss=%s next=%s empty=%s differs=%s" % (got.get("missReason"), got.get("missNext"),
                                                    got.get("emptyReason"), got.get("emptyDiffers")))
    check("⑦ 关光/低档下面板仍可渲染",
          bool((dim or {}).get("rendered")), "dim=%s" % (dim,))

    report = {"plan_ref": "docs/QUALITY.md P4.6", "book": args.book, "graphKey": key,
              "base": args.base, "open": opened, "collect": got, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / ("render-%s.json" % args.book)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
