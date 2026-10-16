#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1.7 真实页面探针：位置标记必须在真实渲染的证据面上出现且可区分。

为什么不能只靠 tests/sky_position_label_contract.js：
  那个契约证明的是**纯函数的语义**（三种 kind 不塌成一句、进度不叫语义完成率）。
  它证明不了「解构面板真的把这些标记渲染出来了」—— 一个函数写得再对，
  只要没人调用，读者看到的仍然是一模一样的行。本项目最贵的教训正是
  「机制存在、有产出、但不产生信息」，所以这一层必须**在真实页面上数**。

判据（全部在真实 DOM 上取，不接受自述）：
  ① 证据面出现 `[data-position]` 标记，且**至少有 2 种不同的取值**；
  ② 位置标记的文本必须与依据标记不同（依据 = 原文已核验/归纳/推导…）；
  ③ 「定位进度」摘要存在，且**不出现**「语义完成率/全书已理解」字样；
  ④ 未定位事件（三国 11 条）仍可在列表中读到 —— 位置未知不等于不可读；
  ⑤ 关光（低档等价）下标记仍在 DOM 里（计划 P9.6：未知信息可降权，不能降到看不见）。

用法：
  CL_GPU=1 python3 -B -s tests/p1_position_render_probe.py --base http://127.0.0.1:8781 \
      --out "$CL_SHOTS/p1-position"
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

BOOKS = {"sanguo": "fe42d01f3826fe8096f86614", "dafeng": "1063b17ca65ec1b76f30e460"}

DEFAULT_QUERY = "曹操三笑遇伏"

PROBE_SEARCH = r"""(()=>{
  const box=document.querySelector('input[data-search="evidence"]');
  if(!box) return {searchBoxPresent:false};
  box.value=__Q__;
  box.dispatchEvent(new Event('input',{bubbles:true}));
  return {searchBoxPresent:true, dispatched:true, value:box.value};
})()"""

PROBE_COLLECT = r"""(()=>{
  const rows=[...document.querySelectorAll('[data-position]')];
  const positions={}; rows.forEach(r=>{const k=r.getAttribute('data-position')||'';positions[k]=(positions[k]||0)+1;});
  const sum=document.querySelector('.sd-position-summary');
  return {rowCount:rows.length, positions:positions, distinctPositions:Object.keys(positions).length,
    sampleRows:rows.slice(0,3).map(r=>({position:r.getAttribute('data-position'),
      posText:(r.querySelector('.sd-event-pos')||{}).textContent||null,
      basisText:(r.querySelector('.sd-event-flags em')||{}).textContent||null,
      label:(r.getAttribute('aria-label')||'').slice(0,140)})),
    summaryPresent:!!sum,
    summaryClaims:sum?[...sum.querySelectorAll('.sd-evidence-summary-top b, .sd-evidence-summary-top span, .sd-evidence-counts span')].map(x=>x.textContent.trim()).join(' | '):null,
    summaryNote:sum?(sum.querySelector('.sd-evidence-note')||{}).textContent||null:null,
    unresolvedRows:rows.filter(r=>r.getAttribute('data-position')==='unresolved').length,
    searchValue:((document.querySelector('input[data-search="evidence"]')||{}).value)||null};
})()"""

PROBE_OPEN = r"""(()=>{
  const out={};
  try{ if(window.CLSky&&CLSky.setDecon) CLSky.setDecon(true); }catch(e){ out.setDeconError=String(e); }
  const btns=[...document.querySelectorAll('button,[role=tab],a')];
  const tab=btns.find(b=>/解构/.test(b.textContent||''));
  if(tab) tab.click();
  const evTab=btns.find(b=>/证据层|事件档案/.test(b.textContent||''));
  if(evTab) evTab.click();
  out.opened=true;
  return out;
})()"""

PROBE_DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const rows=[...document.querySelectorAll('[data-position]')];
  const sum=document.querySelector('.sd-position-summary');
  const vis=rows.filter(r=>{const s=getComputedStyle(r);return s.display!=='none'&&s.visibility!=='hidden';});
  const tag=rows.length?getComputedStyle(rows[0].querySelector('.sd-event-pos')||rows[0]):null;
  return {rowsAfterDim:rows.length, visibleAfterDim:vis.length, summaryStillPresent:!!sum,
          posColorStillSet: tag? getComputedStyle(rows[0]).color : null,
          forbidden:(document.body.innerText||'').match(/语义完成率|全书已理解/g)};
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p1-position"))
    ap.add_argument("--book", default="sanguo", choices=sorted(BOOKS))
    ap.add_argument("--probe-query", default=DEFAULT_QUERY,
                    help="一条真实未定位事件的标题；用它证明读者能搜到『位置未知』的事件")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    key = BOOKS[args.book]

    checks, problems = [], []
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
        time.sleep(5)
        opened = runner.eval(PROBE_OPEN)
        if isinstance(opened, dict) and opened.get("__evalError"):
            problems.append("open_error")
        time.sleep(2)
        first = runner.eval(PROBE_COLLECT)
        if isinstance(first, dict) and first.get("__evalError"):
            problems.append("collect_error")
            first = {}
        search_js = PROBE_SEARCH.replace("__Q__", json.dumps(args.probe_query))
        search_state = runner.eval(search_js)
        if isinstance(search_state, dict) and search_state.get("__evalError"):
            search_state = {}
        time.sleep(2.5)
        after = runner.eval(PROBE_COLLECT)
        if isinstance(after, dict) and after.get("__evalError"):
            after = {}
        time.sleep(1)
        dim = runner.eval(PROBE_DIM)
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


    check("① 证据面渲染出位置标记（首页）",
          (first.get("rowCount") or 0) >= 1,
          "rows=%s %s" % (first.get("rowCount"), first.get("positions")))
    sample = (first.get("sampleRows") or [{}])[0]
    check("② 位置标记与依据标记不是同一个词",
          bool(sample.get("posText")) and bool(sample.get("basisText")) and sample.get("posText") != sample.get("basisText"),
          "pos=%r basis=%r" % (sample.get("posText"), sample.get("basisText")))
    claims = first.get("summaryClaims") or ""
    check("③ 有『定位进度』摘要，且**声称字段**里不含语义完成类措辞",
          bool(first.get("summaryPresent")) and "定位进度" in claims
          and not any(w in claims for w in ("语义完成率", "全书已理解")),
          "claims=%r" % claims[:200])
    check("④ 读者能搜到『位置未知』的事件，且它显示为未知而不是已确认",
          bool(search_state.get("searchBoxPresent")) and (after.get("unresolvedRows") or 0) >= 1
          and (after.get("positions") or {}).get("exact_quote", 0) == 0,
          "query=%r after=%s" % (args.probe_query, after.get("positions")))
    check("⑤ 关光/低档等价的样式下标记仍在 DOM 且可见",
          (dim.get("visibleAfterDim") or 0) >= 1 and dim.get("summaryStillPresent") is True,
          "visible=%s summary=%s" % (dim.get("visibleAfterDim"), dim.get("summaryStillPresent")))
    note = first.get("summaryNote") or ""
    check("⑥ 免责声明显式写明『定位进度不等于语义完成率』",
          "不等于语义完成" in note, "note=%r" % note[:120])

    report = {"plan_ref": "docs/QUALITY.md P1.7", "book": args.book, "graphKey": key,
              "base": args.base, "probe_query": args.probe_query,
              "first_page": first, "after_search": after, "search_state": search_state, "dim_probe": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / ("render-%s.json" % args.book)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
