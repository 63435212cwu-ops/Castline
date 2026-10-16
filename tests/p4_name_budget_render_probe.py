#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4.4 真实页面探针：长名/单字名/混合字符名的标签必须**非空且全文可取**。

为什么不能只靠 tests/sky_name_budget_contract.js：
  那个契约证明的是**判定语义**（未知名占位非空、缩写保留全文、超预算判红、
  命中区同源）与**真实边界测量**（最长名 14 字、单字名 2 个、章名 29 字）。
  它证明不了「界面上真的这么显示了」—— 而 P4.4 的验收原文是
  「当前标签稳定」「未知名称不是空白」「完整证据不会因省略号失去入口」，
  三条都只能在真实 DOM 上量。

判据：
  ① 模块在真实页面上可用；
  ② 人物列表里**不得出现空标签**（计划：未知名称不是空白）；
  ③ 最长名的标签必须带 `title` 全文 —— 完整证据不因缩写失去入口；
  ④ 标签文本不得比全文更长（缩写确实发生）；
  ⑤ 关光/低档下标签仍可见。

用法：
  CL_GPU=1 python3 -B -s tests/p4_name_budget_render_probe.py --base http://127.0.0.1:8781
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

BOOKS = {"xiyou": "a065244455cfb2221bcda94a", "sanguo": "fe42d01f3826fe8096f86614"}

OPEN = r"""(()=>{
  const out={};
  try{ if(window.CLSky&&CLSky.setDecon) CLSky.setDecon(true); }catch(e){ out.err=String(e); }
  try{
    CLSkyDeconstruction.open();
    CLSkyDeconstruction.setMode('people');
    out.modeOk=true;
  }catch(e){ out.modeOk=false; out.modeErr=String(e); }
  return out;
})()"""

COLLECT = r"""(()=>{
  const out={};
  out.moduleLoaded=!!window.CLSkyNameBudget;
  const btns=[...document.querySelectorAll('.sd-person')];
  out.personCount=btns.length;
  const labels=btns.map(b=>{const s=b.querySelector('.sd-person-head b');return s?{t:(s.textContent||''),title:(s.getAttribute('title')||'')}:null;}).filter(Boolean);
  out.labelCount=labels.length;
  out.emptyLabels=labels.filter(x=>!x.t.trim()).length;
  // 带 title 的比例（全文入口）
  out.withTitle=labels.filter(x=>x.title.trim()).length;
  // title 不短于可见文本（全文 >= 缩写）
  out.titleShorter=labels.filter(x=>x.title.trim() && x.title.trim().length < x.t.trim().length).length;
  const longest=labels.slice().sort((a,b)=>b.title.length-a.title.length)[0]||null;
  out.longest=longest;
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const els=[...document.querySelectorAll('.sd-person-head b')];
  const vis=els.filter(e=>{const s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden';});
  return {tags:els.length, visible:vis.length};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p4-name-budget"))
    ap.add_argument("--book", default="xiyou", choices=sorted(BOOKS))
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

    check("① P4.4 名称预算模块在真实页面上可用",
          bool(got.get("moduleLoaded")) and bool(opened.get("modeOk")),
          "module=%s modeOk=%s err=%s" % (got.get("moduleLoaded"), opened.get("modeOk"), opened.get("modeErr")))
    check("② 人物列表渲染出标签", (got.get("personCount") or 0) >= 1,
          "person=%s labels=%s" % (got.get("personCount"), got.get("labelCount")))
    check("③ **不得出现空标签**（计划：未知名称不是空白）",
          (got.get("emptyLabels") or 0) == 0,
          "空标签 %s 个 / 共 %s" % (got.get("emptyLabels"), got.get("labelCount")))
    check("④ 标签必须带 title 全文（完整证据不因缩写失去入口）",
          (got.get("withTitle") or 0) >= (got.get("labelCount") or 1),
          "带 title %s / %s" % (got.get("withTitle"), got.get("labelCount")))
    check("⑤ title 不得短于可见文本（全文 >= 缩写）",
          (got.get("titleShorter") or 0) == 0,
          "title 更短的有 %s 个" % got.get("titleShorter"))
    check("⑥ 关光/低档下标签仍可见",
          (dim.get("visible") or 0) >= 1, "tags=%s visible=%s" % (dim.get("tags"), dim.get("visible")))

    report = {"plan_ref": "docs/QUALITY.md P4.4", "book": args.book, "graphKey": key,
              "base": args.base, "open": opened, "collect": got, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / ("render-%s.json" % args.book)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    if got.get("longest"):
        print("最长名标签:", json.dumps(got["longest"], ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
