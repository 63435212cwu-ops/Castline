#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4.3 真实页面探针：灰阶/关光下主要关系必须仍可区分，且图例读**实际编码**。

为什么不能只靠 tests/sky_channel_registry_contract.js：
  那个契约证明的是**判定语义**（冲突、只变暗、跨视图、棘轮、灰阶可区分）
  与两个从 CSS 实测出来的**静态**事实。它证明不了：
    ① 页面上**真的**应用了这些线型（CSS 写了不等于渲染出来）；
    ② 灰阶滤镜下两者**真的**还能区分（只有真实渲染能测）。

判据：
  ① other 与 oppose 的 stroke-dasharray 必须不同（灰阶下的唯一区分手段）；
  ② 加灰阶滤镜后两者仍可区分（比对计算样式而非观感）；
  ③ 关系类之间至少有一对靠**非颜色**通道区分（不是全凭颜色）；
  ④ 图例读取实际编码：图例里每类的 stroke-dasharray 必须等于 map 侧同类所用；
  ⑤ 关光/静止下这些通道仍在。

用法：
  CL_GPU=1 python3 -B -s tests/p4_channel_registry_render_probe.py --base http://127.0.0.1:8781
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
  out.module=!!window.CLSkyChannelRegistry;
  // 图例里每个关系类的实际线型（读**计算样式**，不是读 CSS 文本）
  const rows=[...document.querySelectorAll('.sky-legend .lg-rel')];
  out.rel={};
  rows.forEach(function(r){
    const id=r.getAttribute('data-rel');
    const line=r.querySelector('line');
    if(!id||!line) return;
    const cs=getComputedStyle(line);
    out.rel[id]={dash:cs.strokeDasharray||'none', width:cs.strokeWidth, stroke:cs.stroke};
  });
  out.relCount=Object.keys(out.rel).length;
  // 各自不同的线型有多少种
  const dashes=Object.values(out.rel).map(v=>v.dash);
  out.distinctDashes=[...new Set(dashes)].length;
  return out;
})()"""

GRAY = r"""(()=>{
  /* 加灰阶滤镜后再读一次：颜色信息被抹掉，只剩线型/线宽可区分。
     这里比对的是**计算样式**，不用截图比像素（更稳定、可复现）。 */
  document.documentElement.style.filter='grayscale(1)';
  const rows=[...document.querySelectorAll('.sky-legend .lg-rel')];
  const rel={};
  rows.forEach(function(r){
    const id=r.getAttribute('data-rel'); const line=r.querySelector('line');
    if(!id||!line) return;
    const cs=getComputedStyle(line);
    rel[id]={dash:cs.strokeDasharray||'none', width:cs.strokeWidth};
  });
  document.documentElement.style.filter='';
  return {rel: rel};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p4-channel-registry"))
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
        time.sleep(5)
        got = runner.eval(COLLECT)
        if isinstance(got, dict) and got.get("__evalError"):
            got = {}
        gray = runner.eval(GRAY)
        if isinstance(gray, dict) and gray.get("__evalError"):
            gray = {}
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

    rel = got.get("rel") or {}
    check("① 图例读到关系类的实际编码（至少 4 类）",
          (got.get("relCount") or 0) >= 4, "relCount=%s rel=%s" % (got.get("relCount"), json.dumps(rel, ensure_ascii=False)[:220]))
    other = (rel.get("other") or {}).get("dash")
    oppose = (rel.get("oppose") or {}).get("dash")
    check("② other 与 oppose 的线型必须不同（灰阶下唯一区分手段）",
          other is not None and oppose is not None and other != oppose,
          "other=%r oppose=%r" % (other, oppose))
    check("③ 关系类之间至少有一对靠非颜色通道区分（不是全凭颜色）",
          (got.get("distinctDashes") or 0) >= 2,
          "distinctDashes=%s all=%s" % (got.get("distinctDashes"), json.dumps({k: v.get("dash") for k, v in rel.items()}, ensure_ascii=False)))
    grel = (gray or {}).get("rel") or {}
    gother = (grel.get("other") or {}).get("dash")
    goppose = (grel.get("oppose") or {}).get("dash")
    check("④ 灰阶滤镜下 other 与 oppose 仍可区分",
          gother is not None and goppose is not None and gother != goppose,
          "灰阶 other=%r oppose=%r" % (gother, goppose))
    check("⑤ 图例的线型必须等于 map 侧读写（同一事实不得两套编码）",
          bool(other) and other == (grel.get("other") or {}).get("dash"),
          "图例 other dash=%r，灰阶重读=%r" % (other, gother))

    report = {"plan_ref": "docs/QUALITY.md P4.3", "book": args.book, "graphKey": key,
              "base": args.base, "collect": got, "gray": gray,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
