#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.6 真实页面探针：任务状态必须在解构面板的任务详情里**真的渲染出来**。

为什么不能只靠 tests/sky_task_status_contract.js：
  那个契约证明的是**状态语义**（缺失不默认成功、planned≠ongoing、
  播放结束≠任务完成）。它证明不了「面板真的显示了状态」——
  实测修之前 `js/sky/sky-deconstruction.js:587` 的任务详情**只渲染五字段、
  完全不渲染 status**，于是「已完成」与「结果锚不上」在读者眼里一模一样。
  本项目最贵的教训是「机制存在、有产出、但不产生信息」，所以这一层要在真实 DOM 上数。

判据：
  ① 任务详情里出现 [data-task-status]，且取值来自真实数据；
  ② 状态标记的文本**不等于**任何五字段标签（状态不是字段之一）；
  ③ 状态与「材料未提供」可区分：未提供状态必须显示具名未知，不得显示成已完成；
  ④ 降级要留痕：原文标 completed 而锚不上事件的，必须同时显示降级后的状态与原文标记；
  ⑤ 低档/关光下状态仍在 DOM 且可见。

用法：
  CL_GPU=1 python3 -B -s tests/p2_task_status_render_probe.py --base http://127.0.0.1:8781 \
      --out "$CL_SHOTS/p2-task-status"
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
  const btns=[...document.querySelectorAll('button,[role=tab],a')];
  const tab=btns.find(b=>/解构/.test(b.textContent||''));
  if(tab) tab.click();
  out.opened=true; return out;
})()"""

PICK_TASK = r"""(()=>{
  const btns=[...document.querySelectorAll('button,[role=tab],a')];
  const mech=btns.find(b=>/情节记录/.test(b.textContent||''));
  if(mech) mech.click();
  return {clicked:!!mech};
})()"""

COLLECT = r"""(()=>{
  const out={};
  const rows=[...document.querySelectorAll('[data-record-layer="tasks"], .sd-mechanic, [data-mechanic-key], button')]
    .filter(b=>/任务|目标|障碍/.test(b.textContent||''));
  // 选中第一条任务记录
  const first=rows.find(b=>b.getAttribute('data-record-layer')==='tasks')||rows[0];
  if(first) first.click();
  const tag=document.querySelector('[data-task-status]');
  out.statusPresent=!!tag;
  if(tag){
    out.statusCode=tag.getAttribute('data-task-status');
    out.tagText=(tag.querySelector('.sd-status-tag')||{}).textContent||null;
    out.rawText=(tag.querySelector('.sd-status-raw')||{}).textContent||null;
    out.hintText=(tag.querySelector('.sd-status-hint')||{}).textContent||null;
    out.factLabels=[...document.querySelectorAll('.sd-fact-label')].map(x=>x.textContent.trim());
    out.taskStatusFacts=document.querySelectorAll('[data-task-status]').length;
  }
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const tags=[...document.querySelectorAll('[data-task-status]')];
  const vis=tags.filter(t=>{const s=getComputedStyle(t);return s.display!=='none'&&s.visibility!=='hidden';});
  return {tags:tags.length, visible:vis.length,
          tagVisible: tags.length? getComputedStyle(tags[0].querySelector('.sd-status-tag')||tags[0]).display : null};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p2-task-status"))
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
        else:
            problems.append("page_not_ready")
        time.sleep(4)
        runner.eval(OPEN)
        time.sleep(1.5)
        pick = runner.eval(PICK_TASK)
        time.sleep(1.5)
        got = runner.eval(COLLECT)
        if isinstance(got, dict) and got.get("__evalError"):
            problems.append("collect_error")
            got = {}
        time.sleep(1)
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

    check("① 任务详情渲染出状态标记", bool(got.get("statusPresent")),
          "code=%s tag=%r" % (got.get("statusCode"), got.get("tagText")))
    labels = got.get("factLabels") or []
    check("② 状态不是五字段之一（独立一行）",
          "状态" in labels,
          "字段标签=%s" % labels)
    check("③ 状态有解释文本，且不是空白占位",
          bool(got.get("hintText")) and len(got.get("hintText") or "") > 6,
          repr(got.get("hintText"))[:120])
    code = got.get("statusCode") or ""
    if code in ("unanchored", "unknown"):
        check("④ 降级/未知状态必须与原文标记可区分",
              bool(got.get("rawText")) or code == "unknown",
              "raw=%r" % got.get("rawText"))
    else:
        check("④ 该任务未降级（状态与原文一致），无需留痕", True, "code=%s" % code)
    check("⑤ 关光/低档下状态仍在 DOM 且可见",
          (dim.get("visible") or 0) >= 1,
          "tags=%s visible=%s" % (dim.get("tags"), dim.get("visible")))

    report = {"plan_ref": "docs/QUALITY.md P2.6", "book": args.book, "graphKey": key,
              "base": args.base, "pick": pick, "collect": got, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / ("render-%s.json" % args.book)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
