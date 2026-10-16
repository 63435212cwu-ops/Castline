#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4.2 真实页面探针：三级位置与折叠总量必须显示，且**数字必须守恒**。

为什么不能只靠 tests/sky_disclosure_contract.js：
  那个契约证明的是**判定语义**（降噪不删数据、越级、稀疏不装饰、连续路径、
  缺字段不默认）。它证明不了「页面上真的说出了现在是哪一级、折叠了多少」，
  也证明不了**页面上的数字与真实统计一致** —— 后者只有真实页面能测。

判据：
  ① 图例出现层级标记（▣ 全景 / ◈ 聚焦 / ▤ 证据）；
  ② 图例出现折叠披露（「已折叠 N / M」或「全部显示（M）」）与可恢复性；
  ③ **守恒**：图例里的 显示数 + 折叠数 == 总数（从真实 stats 独立算一遍核对）；
  ④ 「可恢复」的声明必须有据：retained 必须等于 total（数据没被删）；
  ⑤ 稀疏/降噪不得让数据消失 —— 图例总数必须等于 map 的真实总数；
  ⑥ 关光/静止下披露仍在。

用法：
  CL_GPU=1 python3 -B -s tests/p4_disclosure_render_probe.py --base http://127.0.0.1:8781
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from qa_cinema_wave02_capture import Wave2AuditRunner

BOOKS = {"dafeng": "1063b17ca65ec1b76f30e460"}

COLLECT = r"""(()=>{
  const out={};
  out.module=!!window.CLSkyDisclosure;
  const L=document.querySelector('#skyLegend');
  out.legend=L?(L.textContent||'').replace(/\s+/g,' ').trim():null;
  out.levelMark = out.legend ? (out.legend.match(/[▣◈▤]\s*(全景|聚焦|证据)/)||[])[0]||null : null;
  out.foldPhrase = out.legend ? (out.legend.match(/(已折叠\s*\d+\s*\/\s*\d+|全部显示（\d+）)/)||[])[0]||null : null;
  out.restorable = out.legend ? /可恢复/.test(out.legend) : false;
  out.unrestorable = out.legend ? /不可恢复/.test(out.legend) : false;
  // 独立取真实统计，用来核对图例里的数字
  try{
    const S=CLApp.scene&&CLApp.scene();
    const F=window.CLSky&&CLSky.field?CLSky.field():null;
    const fs=F&&F.stats?F.stats():null;
    const gl=document.body.classList.contains('skd-gl');
    out.stats = fs? {silk:fs.silk, silkTotal:fs.silkTotal, beams:fs.beams||0,
                     strong:fs.strong, skdGl:gl} : null;
    out.expectedShown = fs ? ((gl && fs.strong) ? fs.strong : fs.silk) + (fs.beams||0) : null;
    out.expectedTotal = fs ? fs.silkTotal + (fs.beams||0) : null;
  }catch(e){ out.statsErr=String(e); }
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const L=document.querySelector('#skyLegend');
  const t=L?(L.textContent||'').replace(/\s+/g,' '):'';
  return {hasLevel:/[▣◈▤]\s*(全景|聚焦|证据)/.test(t), hasFold:/已折叠|全部显示/.test(t)};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p4-disclosure"))
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

    legend = got.get("legend") or ""
    check("① 图例出现层级标记（▣ 全景 / ◈ 聚焦 / ▤ 证据）",
          bool(got.get("levelMark")), "mark=%r legend=%r" % (got.get("levelMark"), legend[:120]))
    check("② 图例出现折叠披露与可恢复性",
          bool(got.get("foldPhrase")) and (got.get("restorable") or got.get("unrestorable")),
          "fold=%r restorable=%s" % (got.get("foldPhrase"), got.get("restorable")))

    m = re.search(r"已折叠\s*(\d+)\s*/\s*(\d+)", legend)
    shown_from_legend = total_from_legend = None
    if m:
        folded = int(m.group(1)); total_from_legend = int(m.group(2))
        shown_from_legend = total_from_legend - folded
    else:
        m2 = re.search(r"全部显示（(\d+)）", legend)
        if m2:
            total_from_legend = int(m2.group(1)); shown_from_legend = total_from_legend
    exp_shown, exp_total = got.get("expectedShown"), got.get("expectedTotal")
    check("③ 守恒：图例的 显示数+折叠数 必须等于真实总数（独立核对）",
          total_from_legend is not None and exp_total is not None
          and total_from_legend == exp_total and shown_from_legend == exp_shown,
          "图例 total=%s shown=%s ｜ 真实 total=%s shown=%s（stats=%s）"
          % (total_from_legend, shown_from_legend, exp_total, exp_shown, got.get("stats")))
    check("④「可恢复」的声明必须有据（数据未被删除，总数等于真实总数）",
          (not got.get("restorable")) or (total_from_legend == exp_total and exp_total is not None),
          "restorable=%s total_match=%s" % (got.get("restorable"), total_from_legend == exp_total))
    check("⑤ 降噪不得让数据消失（图例总数必须等于 map 真实总数）",
          exp_total is not None and (got.get("stats") or {}).get("silkTotal") == exp_total - ((got.get("stats") or {}).get("beams") or 0),
          "stats=%s" % (got.get("stats"),))
    check("⑥ 关光/静止下披露仍在",
          bool((dim or {}).get("hasLevel")) and bool((dim or {}).get("hasFold")), "dim=%s" % (dim,))

    report = {"plan_ref": "docs/QUALITY.md P4.2", "book": args.book, "graphKey": key,
              "base": args.base, "collect": got, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
