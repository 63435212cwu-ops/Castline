#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.2 真实页面探针：事件的认识论类型（发生/主张/推理/欺瞒/未标明）必须真的显示。

为什么不能只靠 tests/sky_event_claim_contract.js：
  那个契约证明的是**分类语义**（缺字段不默认成发生、欺骗≠主张、推理≠发生）。
  它证明不了「解构面板真的把它渲染出来了」—— 计划 P3.2 禁止
  「把人物说的话当成叙述事实」，而如果界面上不显示这层区分，
  下游读者仍然会把「诈供成功」里的免死承诺读成事实。
  本项目最贵的教训是「机制存在、有产出、但不产生信息」，所以这一层在真实 DOM 上数。

判据：
  ① 事件行出现 [data-claim]，且取值来自真实数据；
  ② 认识论标记与「依据」「位置」两者都不是同一个词（三件事必须可分辨）；
  ③ 欺瞒类必须出现在 aria-label 里 —— 读屏用户同样不能被误导；
  ④ 详情面有 [data-claim] 行，且带解释文本；
  ⑤ 关光/低档下标记仍在 DOM 且可见。

用法：
  CL_GPU=1 python3 -B -s tests/p3_event_claim_render_probe.py --base http://127.0.0.1:8781 \
      --out "$CL_SHOTS/p3-event-claim"
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
  const ev=btns.find(b=>/证据层|事件档案/.test(b.textContent||''));
  if(ev) ev.click();
  out.opened=true; return out;
})()"""

SEARCH = r"""(()=>{
  const box=document.querySelector('input[data-search="evidence"]');
  if(!box) return {searchBoxPresent:false};
  box.value=__Q__;
  box.dispatchEvent(new Event('input',{bubbles:true}));
  return {searchBoxPresent:true};
})()"""

COLLECT = r"""(()=>{
  const out={};
  const rows=[...document.querySelectorAll('[data-claim]')];
  out.rowCount=rows.length;
  const kinds={}; rows.forEach(r=>{const k=r.getAttribute('data-claim')||'';kinds[k]=(kinds[k]||0)+1;});
  out.kinds=kinds;
  out.distinct=Object.keys(kinds).length;
  const first=rows[0];
  if(first){
    out.firstCode=first.getAttribute('data-claim');
    out.claimText=(first.querySelector('.sd-event-claim')||{}).textContent||null;
    out.posText=(first.querySelector('.sd-event-pos')||{}).textContent||null;
    out.basisText=(first.querySelector('.sd-event-flags em')||{}).textContent||null;
    out.aria=(first.getAttribute('aria-label')||'').slice(0,180);
  }
  // 详情面
  const detail=document.querySelector('.sd-claim-line');
  out.detailPresent=!!detail;
  if(detail){
    out.detailCode=detail.getAttribute('data-claim');
    out.detailText=(detail.textContent||'').replace(/\s+/g,' ').trim().slice(0,200);
  }
  // 计数汇总
  const sum=document.querySelector('.sd-evidence-counts');
  out.countsText=sum?(sum.textContent||'').replace(/\s+/g,' ').trim().slice(0,160):null;
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const tags=[...document.querySelectorAll('.sd-event-claim, .sd-claim-line')];
  const vis=tags.filter(t=>{const s=getComputedStyle(t);return s.display!=='none'&&s.visibility!=='hidden';});
  return {tags:tags.length, visible:vis.length};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-event-claim"))
    ap.add_argument("--book", default="dafeng", choices=sorted(BOOKS))
    ap.add_argument("--probe-query", default="诈供成功", help="一条真实的欺瞒类事件标题")
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
        time.sleep(2)
        first = runner.eval(COLLECT)
        if isinstance(first, dict) and first.get("__evalError"):
            problems.append("collect_error")
            first = {}
        search = runner.eval(SEARCH.replace("__Q__", json.dumps(args.probe_query)))
        if isinstance(search, dict) and search.get("__evalError"):
            search = {}
        time.sleep(2.5)
        after = runner.eval(COLLECT)
        if isinstance(after, dict) and after.get("__evalError"):
            after = {}
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

    check("① 事件行渲染出认识论类型标记 [data-claim]",
          (first.get("rowCount") or 0) >= 1,
          "rows=%s kinds=%s" % (first.get("rowCount"), first.get("kinds")))
    check("② 认识论标记与「依据」「位置」是三个不同的词",
          bool(first.get("claimText")) and bool(first.get("basisText")) and bool(first.get("posText"))
          and len({first.get("claimText"), first.get("basisText"), first.get("posText")}) == 3,
          "claim=%r basis=%r pos=%r" % (first.get("claimText"), first.get("basisText"), first.get("posText")))
    check("③ 欺瞒类必须写进 aria-label（读屏同样不能被误导）",
          bool(search.get("searchBoxPresent")) and (after.get("firstCode") == "deception")
          and ("明知虚假" in (after.get("aria") or "") or "欺瞒" in (after.get("aria") or "")),
          "query=%r code=%s aria=%r" % (args.probe_query, after.get("firstCode"), (after.get("aria") or "")[:90]))
    check("④ 详情面有独立的类型行并带解释",
          bool(first.get("detailPresent")) and bool(first.get("detailText")) and len(first.get("detailText") or "") > 8,
          repr(first.get("detailText"))[:130])
    check("⑤ 关光/低档下标记仍在 DOM 且可见",
          (dim.get("visible") or 0) >= 1, "tags=%s visible=%s" % (dim.get("tags"), dim.get("visible")))

    report = {"plan_ref": "docs/QUALITY.md P3.2", "book": args.book, "graphKey": key,
              "base": args.base, "probe_query": args.probe_query,
              "first": first, "after_search": after, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / ("render-%s.json" % args.book)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
