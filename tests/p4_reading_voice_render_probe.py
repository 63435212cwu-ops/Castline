#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4.7 真实页面探针：阅读面必须能表达五种状态，且未知状态不得弱化到看不见。

为什么不能只靠 tests/sky_reading_voice_contract.js：
  那个契约证明的是**纯函数语义**（五状态文案互异、层级次序固定、
  工程痕迹判红、弱化有下限）与源码级加锁（esc 五字符、阅读面 0 处工程痕迹）。
  它证明不了「**渲染出来的**文字里确实没有工程痕迹、且次级状态仍可见」。

判据：
  ① 模块在真实页面上可用；
  ② 面板渲染出的**全部可见文字**里不得有工程秒数/调试痕迹；
  ③ 未知/次级状态的元素仍满足可读下限（字号/不透明度）；
  ④ 五种状态的文案在模块里都能取到，且互不相同；
  ⑤ 关光/低档下面板仍可渲染。

用法：
  CL_GPU=1 python3 -B -s tests/p4_reading_voice_render_probe.py --base http://127.0.0.1:8781
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

BOOKS = {"sanguo": "fe42d01f3826fe8096f86614", "dafeng": "1063b17ca65ec1b76f30e460"}

OPEN = r"""(()=>{
  const out={};
  try{ if(window.CLSky&&CLSky.setDecon) CLSky.setDecon(true); }catch(e){ out.err=String(e); }
  try{ CLSkyDeconstruction.open(); CLSkyDeconstruction.setMode('mechanics'); out.openOk=true; }
  catch(e){ out.openOk=false; out.openErr=String(e); }
  return out;
})()"""

COLLECT = r"""(()=>{
  const out={};
  const RV=window.CLSkyReadingVoice;
  out.moduleLoaded=!!RV;
  if(!RV) return out;
  const panel=document.querySelector('#skyDeconPanel');
  out.panelPresent=!!panel;
  if(panel){
    const txt=(panel.innerText||panel.textContent||'');
    out.textLen=txt.length;
    // 工程痕迹：用模块自己的判据扫**渲染出来的文字**
    const pats=[/\b\d+(\.\d+)?\s*(ms|毫秒|秒|s)\b/g, /\b\d+\s*(KB|MB|GB|字节|bytes)\b/g,
                /@budget/g, /\bdrawcalls?\s*=/g, /\brtpx\s*=/g, /\bfps\b\s*[=:]?\s*\d/g,
                /console\.(log|warn|error)\s*\(/g];
    const leaks=[];
    for(const p of pats){ const m=txt.match(p); if(m) leaks.push(...m.slice(0,3)); }
    out.leaks=leaks;
  }
  // 次级/未知状态元素的可读下限
  const els=[...document.querySelectorAll('.sd-evidence-note, .sd-empty, .sd-detail-meta, .sd-key')];
  out.checked=els.length;
  out.below=[];
  for(const e of els.slice(0,40)){
    const s=getComputedStyle(e);
    const fs=parseFloat(s.fontSize)||0;
    const op=parseFloat(s.opacity);
    if(fs && fs < 11) out.below.push({cls:e.className.slice(0,30), why:'fontSize '+fs});
    if(isFinite(op) && op < 0.55) out.below.push({cls:e.className.slice(0,30), why:'opacity '+op});
  }
  // 五种状态文案必须互不相同且都取得到
  out.stateTexts=Object.keys(RV.STATES).map(k=>RV.STATES[k].text);
  out.uniqueTexts=new Set(out.stateTexts).size;
  out.stateCount=Object.keys(RV.STATES).length;
  out.minVisible=RV.MIN_VISIBLE;
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
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p4-reading-voice"))
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

    check("① P4.7 阅读状态模块在真实页面上可用",
          bool(got.get("moduleLoaded")) and bool(got.get("panelPresent")),
          "module=%s panel=%s err=%s" % (got.get("moduleLoaded"), got.get("panelPresent"), opened.get("openErr")))
    check("② 面板渲染出的文字里**不得有工程秒数/调试痕迹**",
          not (got.get("leaks") or []),
          "文字长度=%s 泄漏=%s" % (got.get("textLen"), got.get("leaks")))
    check("③ 次级/未知状态不得弱化到看不见（字号≥11、不透明度≥0.55）",
          not (got.get("below") or []),
          "检查 %s 个元素，越界 %s 个：%s" % (got.get("checked"), len(got.get("below") or []),
                                              (got.get("below") or [])[:3]))
    check("④ 五种状态文案必须互不相同且都取得到",
          (got.get("stateCount") or 0) >= 5 and (got.get("uniqueTexts") or 0) == (got.get("stateCount") or 0),
          "状态数=%s 去重后=%s" % (got.get("stateCount"), got.get("uniqueTexts")))
    check("⑤ 关光/低档下面板仍可渲染",
          bool((dim or {}).get("rendered")), "dim=%s" % (dim,))

    report = {"plan_ref": "docs/QUALITY.md P4.7", "book": args.book, "graphKey": key,
              "base": args.base, "open": opened, "collect": got, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / ("render-%s.json" % args.book)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
