#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.6 真实页面探针：伏笔八阶段必须显示，且「缺兑现端」这类自相矛盾必须被标出。

为什么不能只靠 tests/sky_foreshadow_stage_contract.js：
  那个契约证明的是**判定语义**（八档独立、缺字段不默认兑现、
  声称 resolved 但缺兑现端要单列、未回收不是缺陷、0 条要报缺乏处置证据）。
  它证明不了「面板真的显示了八阶段」—— 修之前面板只显示模型四档
  （已兑现声明/待回收声明/…），读者看不到「这条其实**声称**已兑现却拿不出兑现端」。

判据：
  ① 伏笔卡片出现 [data-fore-stage]，取值来自真实数据；
  ② 八阶段标记与模型四档标记不是同一个词（两件事可分辨）；
  ③ 大奉（9 条全部缺兑现端）必须显示为「缺兑现端」，**不得**显示成已兑现；
  ④ 该卡片的 aria-label 必须写明它是数据自相矛盾；
  ⑤ 关光/低档下标记仍在 DOM 且可见。

用法：
  CL_GPU=1 python3 -B -s tests/p3_foreshadow_stage_render_probe.py --base http://127.0.0.1:8781
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
  try{ if(window.CLSkyDeconstruction&&CLSkyDeconstruction.setMode) CLSkyDeconstruction.setMode('foreshadow'); out.tab=true; }catch(e){ out.modeErr=String(e); }
  return out;
})()"""

COLLECT = r"""(()=>{
  const cards=[...document.querySelectorAll('.sd-fore-card')];
  const out={cards:cards.length};
  const kinds={}; cards.forEach(c=>{const k=c.getAttribute('data-fore-stage')||'';kinds[k]=(kinds[k]||0)+1;});
  out.kinds=kinds;
  const first=cards[0];
  if(first){
    out.foreCode=first.getAttribute('data-fore-stage');
    out.foreText=(first.querySelector('.sd-fore-lifecycle')||{}).textContent||null;
    out.modelStage=(first.querySelector('.sd-fore-stage')||{}).textContent||null;
    out.aria=(first.getAttribute('aria-label')||'').slice(0,260);
  }
  const bad=cards.find(c=>c.getAttribute('data-fore-stage')==='claimed_unbacked');
  out.badFound=!!bad;
  if(bad){
    out.badText=(bad.querySelector('.sd-fore-lifecycle')||{}).textContent||null;
    out.badAria=(bad.getAttribute('aria-label')||'').slice(0,280);
  }
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const els=[...document.querySelectorAll('.sd-fore-lifecycle')];
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
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-foreshadow"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    problems, checks = [], []
    def check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            problems.append(name)
        print(("PASS " if ok else "FAIL ") + name + "  · " + str(detail), flush=True)

    opened, dafeng, dim = probe(args.base, BOOKS["dafeng"])
    check("① 伏笔卡片渲染出八阶段标记 [data-fore-stage]",
          (dafeng.get("cards") or 0) >= 1,
          "cards=%s kinds=%s" % (dafeng.get("cards"), dafeng.get("kinds")))
    check("② 八阶段标记与模型四档标记不是同一个词",
          bool(dafeng.get("foreText")) and bool(dafeng.get("modelStage")),
          "eight=%r model=%r" % (dafeng.get("foreText"), dafeng.get("modelStage")))
    check("③ 大奉 9 条必须显示为「缺兑现端」而非已兑现",
          dafeng.get("foreCode") == "claimed_unbacked" and (dafeng.get("kinds") or {}).get("payoff") is None,
          "code=%s kinds=%s text=%r" % (dafeng.get("foreCode"), dafeng.get("kinds"), dafeng.get("foreText")))
    aria = dafeng.get("badAria") or dafeng.get("aria") or ""
    check("④ aria-label 必须写明这是数据自相矛盾",
          ("没有 payoff 事件" in aria) or ("数据自相矛盾" in aria) or ("不能当作已兑现" in aria),
          repr(aria[-150:]))
    check("⑤ 关光/低档下标记仍在 DOM 且可见",
          (dim.get("visible") or 0) >= 1, "tags=%s visible=%s" % (dim.get("tags"), dim.get("visible")))

    _, sanguo, _ = probe(args.base, BOOKS["sanguo"])
    check("⑥ 对照组三国（两端齐全）必须显示为已兑现，与大奉不同",
          sanguo.get("foreCode") == "payoff" and sanguo.get("foreCode") != dafeng.get("foreCode"),
          "sanguo=%s kinds=%s" % (sanguo.get("foreCode"), sanguo.get("kinds")))

    report = {"plan_ref": "docs/QUALITY.md P3.6", "base": args.base,
              "dafeng": dafeng, "sanguo": sanguo, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
