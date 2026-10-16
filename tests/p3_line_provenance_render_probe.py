#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.4 真实页面探针：机械等分线必须与真实结构线**可分辨**。

为什么不能只靠 tests/sky_line_provenance_contract.js：
  那个契约证明的是**判定语义**（缺来源不默认成审阅、机械线不算结构、
  不均匀的线不误判等分）。它证明不了「界面上真的把它们分开了」——
  修之前解构面板把两者都写成「推导」一个词，读者分不清
  「分析出的主线」与「按事件数切的八段」，而这正是计划 P3.4 要的区分。

判据：
  ① 剧情线行出现 [data-line-source]，取值来自真实数据；
  ② 来源标记与「依据」不是同一个词（两件事必须可分辨）；
  ③ 大奉（机械等分）与三国（逐条审阅）**取值必须不同**；
  ④ 机械线的 aria-label 必须写明「只当导航，不计故事结构」——
     读屏用户同样不能被误导成「这是故事结构」；
  ⑤ 关光/低档下标记仍在 DOM 且可见。

用法：
  CL_GPU=1 python3 -B -s tests/p3_line_provenance_render_probe.py --base http://127.0.0.1:8781
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
  const btns=[...document.querySelectorAll('button,[role=tab],a')];
  const tab=btns.find(b=>/解构/.test(b.textContent||''));
  if(tab) tab.click();
  // 切到「故事骨架」（lines）——剧情线只在这一页渲染
  // 用公开 API 切模式（点按钮走的是事件委托，探针里不一定生效；
  // 第一版就是点了按钮却没换页 ⇒ 数出 0 行）
  try{ if(window.CLSkyDeconstruction&&CLSkyDeconstruction.setMode) CLSkyDeconstruction.setMode('lines'); out.linesTab=true; }catch(e){ out.modeErr=String(e); }
  // 剧情树必须先建立，否则 .sd-lines 是空的（第一版漏了这步 ⇒ 数出 0 行）
  try{ if(window.CLSky&&CLSky.setPlot) CLSky.setPlot(true); }catch(e){ out.plotErr=String(e); }
  // 展开「自动分段」details（机械线收在这里）
  const det=[...document.querySelectorAll('details.sd-auto-lines')];
  det.forEach(d=>{ d.open=true; });
  out.detailsOpened=det.length;
  out.opened=true; return out;
})()"""

COLLECT = r"""(()=>{
  const rows=[...document.querySelectorAll('[data-line-source]')];
  const kinds={}; rows.forEach(r=>{const k=r.getAttribute('data-line-source')||'';kinds[k]=(kinds[k]||0)+1;});
  const first=rows[0];
  return {
    rowCount: rows.length, kinds: kinds, distinct: Object.keys(kinds).length,
    firstCode: first?first.getAttribute('data-line-source'):null,
    sourceText: first?((first.querySelector('.sd-line-source')||{}).textContent||null):null,
    basisText: first?((first.querySelector('.sd-line-basis')||{}).textContent||null):null,
    aria: first?(first.getAttribute('aria-label')||'').slice(0,220):null,
    title: first?(first.getAttribute('title')||'').slice(0,220):null
  };
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const els=[...document.querySelectorAll('.sd-line-source')];
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
        runner.eval(OPEN)
        time.sleep(2.5)
        got = runner.eval(COLLECT)
        if isinstance(got, dict) and got.get("__evalError"):
            got = {}
        time.sleep(0.8)
        dim = runner.eval(DIM)
        if isinstance(dim, dict) and dim.get("__evalError"):
            dim = {}
        return got, dim
    finally:
        try:
            runner.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-line-provenance"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    problems, checks = [], []
    def check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            problems.append(name)
        print(("PASS " if ok else "FAIL ") + name + "  · " + str(detail), flush=True)

    dafeng, dim = probe(args.base, BOOKS["dafeng"])
    check("① 剧情线行渲染出来源标记 [data-line-source]",
          (dafeng.get("rowCount") or 0) >= 1,
          "rows=%s kinds=%s" % (dafeng.get("rowCount"), dafeng.get("kinds")))
    check("② 来源标记与「依据」是两件事，不得同词",
          bool(dafeng.get("sourceText")) and bool(dafeng.get("basisText"))
          and dafeng.get("sourceText") != dafeng.get("basisText"),
          "source=%r basis=%r" % (dafeng.get("sourceText"), dafeng.get("basisText")))
    check("③ 大奉必须被标成机械等分（实测 8 条段大小 374×7+372）",
          dafeng.get("firstCode") == "mechanical",
          "code=%s kinds=%s" % (dafeng.get("firstCode"), dafeng.get("kinds")))
    aria = (dafeng.get("aria") or "") + (dafeng.get("title") or "")
    check("④ 机械线的 aria-label/title 必须写明「只当导航，不计故事结构」",
          ("只当导航" in aria) or ("不计故事结构" in aria),
          repr(aria[-120:]))

    sanguo, _ = probe(args.base, BOOKS["sanguo"])
    check("⑤ 三国（逐条审阅）与大奉（机械）取值必须不同",
          sanguo.get("firstCode") == "reviewed" and sanguo.get("firstCode") != dafeng.get("firstCode"),
          "sanguo=%s kinds=%s" % (sanguo.get("firstCode"), sanguo.get("kinds")))
    check("⑥ 关光/低档下来源标记仍在 DOM 且可见",
          (dim.get("visible") or 0) >= 1, "tags=%s visible=%s" % (dim.get("tags"), dim.get("visible")))

    report = {"plan_ref": "docs/QUALITY.md P3.4", "base": args.base,
              "dafeng": dafeng, "sanguo": sanguo, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
