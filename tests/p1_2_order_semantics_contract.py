#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1.2 三种顺序语义契约（docs/QUALITY.md P1.2）。

计划原文：
  「定义**原文出现顺序、故事发生时间、因果方向**三个独立含义。默认阅读可按原文出现顺序；
    倒叙、回忆、同时发生只有明确依据才另标。未知位置保留未知，
    不能因放在列表末尾就被称作结局。**图例、文案与播放器必须使用同一语义**。」

为什么需要它（第 39 轮只读审计的结论）：
  `tests/sky_chapter_axis_contract.js` 对 P1.2 的核心三点**零覆盖** ——
  计划点名的「原文出现顺序 / 故事发生时间 / 因果方向 / 图例 / 播放器」在该文件里
  **一次都没出现**（关键词命中仅 2 处，是「未知」「结局」）。
  也就是说：P1.2 最核心的「三种顺序不得混为一谈」这条，此前**没有契约守着**。

本契约的判据（避免把「缺失」与「混用」搞混）：
  P1.2 要求的是**三个独立含义**，所以有两个失败方向：
    A. **混用**：把三种语义套用同一个名字/同一个通道（例如把「章号大小」说成「故事时间」）；
    B. **缺失**：某种语义根本没定义，读者无从知道眼前的顺序是什么。
  只测 B 会漏掉 A，只测 A 会漏掉 B。两条都测。

实测现状（三国真实图 + 真实页面）：
  · 原文出现顺序：**落地** —— `order` / `rawOrder`
  · 因果方向：**落地** —— `causeEdges`（独立通道，三国 339 条）
  · 故事发生时间：**未落地** —— meta 无 `storyTime`，事件无时间字段；
    `atlas-source.js` 的 eventOrdering 自述 `basis: 'source_appearance_not_causality_or_story_time'`
  · 页面文案：轴只写 `unit: '回'` 与「113 回已解析 · 25 段其他材料」，
    **从不说这个顺序是「原文出现顺序」还是「故事时间」** —— 而计划要求
    「图例、文案与播放器必须使用同一语义」。

⇒ 本契约**如实报告三者的落地状态**，并把「未落地」记为已知缺口，
  同时把**可判定的部分**锁住（不得混用、未知不得称结局）。

用法：
  python3 -B -s tests/p1_2_order_semantics_contract.py
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SANGUO = "fe42d01f3826fe8096f86614"
ART = Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts"))
BASE = os.environ.get("CL_BASE", "http://127.0.0.1:8781")

passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append({"name": name, "detail": detail})
    print(("%s %s" % ("PASS" if ok else "FAIL", name)) + ("  · " + str(detail) if detail else ""), flush=True)


def node_exe():
    p = os.environ.get("ATLAS_NODE")
    if p and Path(p).is_file():
        return p
    from shutil import which
    w = which("node")
    if w:
        return w
    base = Path("/Users/carmen/.workbuddy/binaries/node/versions")
    if base.is_dir():
        cands = sorted([d for d in base.iterdir() if d.is_dir() and d.name[:1].isdigit()],
                       key=lambda d: [int(x) for x in d.name.split(".") if x.isdigit()] or [0])
        if cands and (cands[-1] / "bin" / "node").is_file():
            return str(cands[-1] / "bin" / "node")
    return "node"


PRELUDE = """
const fs=require('fs'),vm=require('vm');
const window={};const ctx=vm.createContext({window});
for(const f of ['js/atlas/atlas-source.js','js/tree/storylines.js','js/sky/sky-model.js','js/sky/sky-deck-model.js'])
  vm.runInContext(fs.readFileSync(f,'utf8'),ctx,{filename:f});
"""


def run_js(js):
    r = subprocess.run([node_exe(), "-e", js], cwd=str(ROOT), capture_output=True, text=True, timeout=240)
    for line in r.stdout.strip().splitlines():
        if line.strip().startswith("{"):
            return json.loads(line.strip()), None
    return None, (r.stderr.strip().splitlines() or [""])[-1][:160]


PAGE_READY_JS = "!!(document.readyState==='complete'&&window.CLApp&&CLApp.graph&&CLApp.graph()&&window.CLSky&&CLSky.enabled()&&CLSky.model()&&window.CLSkyChrome&&CLSkyChrome.enabled()&&document.querySelector('#loader.off')&&document.getElementById('skyLegend'))"
LEGEND_SNAPSHOT_JS = r"""
(function(){
  var label='阅读按原文出现顺序', legend=document.getElementById('skyLegend');
  function visibleRect(r, element){
    if(!r || r.width<=0 || r.height<=0 || r.left < -1 || r.top < -1 ||
       r.right > innerWidth+1 || r.bottom > innerHeight+1)return false;
    for(var p=element;p;p=p.parentElement){
      var s=getComputedStyle(p);
      if(p.hidden || p.getAttribute('aria-hidden')==='true' || s.display==='none' ||
         s.visibility==='hidden' || s.visibility==='collapse' || +s.opacity===0)return false;
      var box=p.getBoundingClientRect();
      if(/hidden|clip|scroll|auto/.test(s.overflowX) && (r.left<box.left-1 || r.right>box.right+1))return false;
      if(/hidden|clip|scroll|auto/.test(s.overflowY) && (r.top<box.top-1 || r.bottom>box.bottom+1))return false;
    }
    return true;
  }
  var present=!!legend, visible=present && visibleRect(legend.getBoundingClientRect(),legend), orderingVisible=false;
  if(present){
    var walker=document.createTreeWalker(legend,NodeFilter.SHOW_TEXT), node;
    while((node=walker.nextNode())){
      var start=(node.nodeValue||'').indexOf(label);
      if(start<0)continue;
      var range=document.createRange();range.setStart(node,start);range.setEnd(node,start+label.length);
      var rects=Array.from(range.getClientRects());
      if(rects.length && rects.every(function(r){return visibleRect(r,node.parentElement);})){orderingVisible=true;break;}
    }
  }
  return {present:present,visible:visible,orderingVisible:orderingVisible,label:label,
          text:legend ? legend.innerText : null};
})()
"""


def legend_selftest():
    js = r"""
const vm=require('vm');
const label='阅读按原文出现顺序', rows=[];
const cases=[
 {name:'visible actual legend label',text:label,expected:true},
 {name:'body-only mention cannot pass',text:'关系线',body:label,expected:false},
 {name:'hidden legend cannot pass',text:label,hidden:true,expected:false},
 {name:'transparent ancestor cannot pass',text:label,opacity:'0',expected:false},
 {name:'off-screen phrase cannot pass',text:label,outside:true,expected:false},
 {name:'different ordering cannot pass',text:'阅读按因果顺序',expected:false}
];
for(const c of cases){
 const box={left:20,top:810,right:900,bottom:850,width:880,height:40};
 const body={parentElement:null,hidden:false,getAttribute:()=>null,getBoundingClientRect:()=>({left:0,top:0,right:1440,bottom:900,width:1440,height:900}),innerText:c.body||''};
 const legend={parentElement:body,hidden:!!c.hidden,getAttribute:()=>null,getBoundingClientRect:()=>box,innerText:c.text};
 const span={parentElement:legend,hidden:false,getAttribute:()=>null,getBoundingClientRect:()=>box};
 const node={nodeValue:c.text,parentElement:span};
 const document={body:body,getElementById:id=>id==='skyLegend'?legend:null,
  createTreeWalker:()=>{let once=false;return {nextNode:()=>once?null:(once=true,node)};},
  createRange:()=>({setStart:()=>{},setEnd:()=>{},getClientRects:()=>[c.outside?{left:1450,top:815,right:1640,bottom:832,width:190,height:17}:{left:25,top:815,right:215,bottom:832,width:190,height:17}]})};
 const context={document,NodeFilter:{SHOW_TEXT:4},innerWidth:1440,innerHeight:900,
  getComputedStyle:element=>({display:'block',visibility:'visible',opacity:element===legend?(c.opacity||'1'):'1',overflowX:'visible',overflowY:'visible'})};
 const snap=vm.runInNewContext(SNAPSHOT,context);
 rows.push({name:c.name,expected:c.expected,actual:snap.orderingVisible,ok:snap.orderingVisible===c.expected});
}
console.log(JSON.stringify({ok:rows.every(x=>x.ok),checks:rows}));
""".replace("SNAPSHOT", json.dumps(LEGEND_SNAPSHOT_JS))
    result, error = run_js(js)
    if result is None:
        print("P1.2 LEGEND SELF-TEST FAIL · %s" % error)
        return 1
    for row in result["checks"]:
        print(("PASS " if row["ok"] else "FAIL ") + row["name"])
    return 0 if result.get("ok") else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ART / "p1-2"))
    ap.add_argument("--self-test", action="store_true", help="仅执行实际图例可见文字判据的CPU正反例")
    ap.add_argument("--ratchet", action="store_true",
                    help="门禁口径：把**已登记**的缺口（故事时间未落地、页面未声明语义）"
                         "从失败清单里移出，只对**恶化**报红")
    args = ap.parse_args()
    if args.self_test:
        return legend_selftest()

    js = PRELUDE + """
const g=window.CLAtlasSource.normalize(JSON.parse(fs.readFileSync('data/cache/%s.json','utf8')));
const m=window.CLSkyModel.build(g,window.CLStory.analyze(g));
const meta=g.meta||{};
const eo=meta.eventOrdering||{};
const e0=(g.events||[])[0]||{};
// 事件字段里出现过的「顺序/时间」类字段名
const orderish=Object.keys(e0).filter(function(k){return /order|time|seq|index|when|date/i.test(k);});
console.log(JSON.stringify({
  basis: eo.basis||null, version: eo.version||null, mode: eo.mode||null,
  orderishEventFields: orderish,
  hasStoryTimeMeta: ('storyTime' in meta) || ('storyTime' in eo),
  hasCausalMeta: ('causalOrder' in meta) || ('causalOrder' in eo),
  causeEdges: (g.causeEdges||[]).length,
  axisUnit: m.axis.unit, axisSummary: m.axis.summary, axisMode: m.axis.mode,
  lastChapterNo: (m.chapters.at(-1)||{}).no,
  // **字段选择修正**：`order` 才是阅读顺序（严格 1..n）；`rawOrder` 是
  // 「原文里的原始序号」，只有 434/1286 条有值，其余为 null。
  // 我第一版写 `Number(e.rawOrder)` —— `Number(null)` 与 `Number(undefined)` 都变 0，
  // 混进序列后制造出 155 次「回落」，**那是我算出来的假象，不是数据缺陷**。
  orderStrictSeq: (function(){
    var o=g.events.map(function(e){return Number(e.order);});
    return {n:o.length, strict: o.every(function(v,i){return v===i+1;})};
  })(),
  rawOrderCoverage: (function(){
    var withVal=g.events.filter(function(e){return e.rawOrder!=null;}).length;
    return {total:g.events.length, withValue:withVal, nulls:g.events.length-withVal};
  })(),
  rawOrderWithValueMonotonic: (function(){
    var r=g.events.map(function(e){return e.rawOrder;}).filter(function(x){return x!=null;}).map(Number);
    var drops=0; for(var i=1;i<r.length;i++){ if(r[i] < r[i-1]) drops++; }
    return {n:r.length, drops:drops};
  })()
}));
""" % SANGUO
    res, err = run_js(js)
    if res is None:
        check("P1.2 取真实图谱数据", False, "无法取数：%s" % err)
        return 1

    has_appearance = bool(res.get("orderishEventFields"))
    has_causal = (res.get("causeEdges") or 0) > 0 and bool(res.get("hasCausalMeta") or True)
    has_story_time = bool(res.get("hasStoryTimeMeta"))
    check("①a 原文出现顺序**已落地**（事件有 order/rawOrder 字段）",
          has_appearance, "字段：%s" % (res.get("orderishEventFields"),))
    check("①b 因果方向**已落地**（causeEdges 是独立通道）",
          (res.get("causeEdges") or 0) > 0,
          "三国 causeEdges=%s 条" % res.get("causeEdges"))
    check("①c 故事发生时间**尚未落地**（本契约锁住这个已知缺口，实现后应改此条）",
          not has_story_time,
          "meta 无 storyTime；代码自述 basis=%r" % res.get("basis"))

    check("②a 代码必须**自述**排序依据，而不是让读者猜（basis 字段存在）",
          bool(res.get("basis")),
          "eventOrdering.basis=%r" % res.get("basis"))
    check("②b 排序依据必须**排除**因果与故事时间（不得把三者混为一谈）",
          "not_causality" in str(res.get("basis") or "")
          and "story_time" in str(res.get("basis") or ""),
          "basis 显式排除因果与故事时间：%r" % res.get("basis"))
    check("②c 章号顺序不得冒充故事时间（axis 只声称单位是章回）",
          res.get("axisUnit") == "回",
          "axis.unit=%r，summary=%r" % (res.get("axisUnit"), res.get("axisSummary")))

    oseq = res.get("orderStrictSeq") or {}
    check("③a 阅读顺序 `order` 严格 1..n（顺序未被破坏）",
          bool(oseq.get("strict")),
          "n=%s，严格递增=%s" % (oseq.get("n"), oseq.get("strict")))
    cov = res.get("rawOrderCoverage") or {}
    rmono = res.get("rawOrderWithValueMonotonic") or {}
    check("③a2 `rawOrder` 覆盖率如实可查（有值 %s/%s，其余为 null）"
          % (cov.get("withValue"), cov.get("total")),
          (cov.get("withValue") or 0) > 0 and (cov.get("total") or 0) > 0,
          "有值 %s 条、null %s 条；同章内相邻对调 %s 次（**计划未禁止**，仅登记）"
          % (cov.get("withValue"), cov.get("nulls"), rmono.get("drops")))
    check("③b 末章号是真实回号 120，**不是**被当成结局的段数",
          res.get("lastChapterNo") == 120,
          "末章号=%s（若被排到末尾当成结局，此处会退化成别的数）" % res.get("lastChapterNo"))

    page = None
    try:
        sys.path.insert(0, str(ROOT / "tests"))
        import qa_cinema_wave02_capture as cap
        import time
        runner = cap.Wave2AuditRunner(1440, 900, 1)
        try:
            runner.start()
            runner.navigate(BASE.rstrip("/") + "/?sky=1&data=data/cache/%s.json" % SANGUO)
            end = time.time() + 120
            while time.time() < end:
                if runner.eval(PAGE_READY_JS) is True:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError('Complete page, graph, shell, chrome and legend readiness timed out')
            time.sleep(3)
            initial_legend = runner.eval(LEGEND_SNAPSHOT_JS)
            body = runner.eval(r"""
            (function(){
              var t=document.body.innerText||'';
              return {n:t.length,
                      saysStoryTime: /故事时间|故事发生时间/.test(t),
                      saysCausal: /因果方向|因果顺序/.test(t)};
            })()
            """, await_promise=False)
            target = runner.eval(r"""
            (function(){
              var button=document.getElementById('skyPlot'), r=button&&button.getBoundingClientRect();
              if(!r||r.width<=0||r.height<=0)return null;
              var x=r.left+r.width/2,y=r.top+r.height/2,hit=document.elementFromPoint(x,y);
              return hit&&(hit===button||button.contains(hit))?{x:x,y:y}:null;
            })()
            """)
            if not target:
                raise RuntimeError('Visible plot button is unavailable to native input')
            for event_type in ('mouseMoved', 'mousePressed', 'mouseReleased'):
                runner.ws.call('Input.dispatchMouseEvent', type=event_type, x=target['x'], y=target['y'],
                               button='left', clickCount=1)
            end = time.time() + 10
            while time.time() < end:
                if runner.eval("!!(window.CLSky&&CLSky.state().plot)") is True:
                    plot_legend = runner.eval(LEGEND_SNAPSHOT_JS)
                    if plot_legend and plot_legend.get('visible'):
                        break
                time.sleep(0.1)
            else:
                raise RuntimeError('Plot transition and visible legend readiness timed out')
            page = dict(body or {})
            page.update({'initialLegend': initial_legend, 'plotLegend': plot_legend,
                         'saysAppearance': bool(initial_legend and initial_legend.get('orderingVisible')
                                                and plot_legend and plot_legend.get('orderingVisible')),
                         'legend': (initial_legend or {}).get('text'),
                         'plotInput': 'native CDP mouse click'})
        finally:
            try:
                runner.close()
            except Exception:
                pass
    except Exception as exc:
        page = {"error": repr(exc)[:120]}

    if page and not page.get("error"):
        check("④a 初开与剧情图例必须可见声明原文出现顺序（与阅读语义一致）",
              bool(page.get("saysAppearance")),
              "初开图例=%s；剧情图例=%s"
              % (page.get("initialLegend"), page.get("plotLegend")))
        check("④b 页面不得声称用了「故事时间」（因为该语义尚未实现）",
              not page.get("saysStoryTime"),
              "页面含「故事时间」字样=%s —— 若为真则属**虚假声明**" % page.get("saysStoryTime"))
    else:
        check("④z 页面数据必须可取得（基础设施；取不到就是失败，不算已知缺口）", False,
              "无法取页面数据：%s" % (page or {}).get("error"))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "planRef": "docs/QUALITY.md P1.2",
        "why": "第 39 轮审计发现 `sky_chapter_axis_contract.js` 对 P1.2 核心三点**零覆盖**"
               "（『原文出现顺序/故事发生时间/因果方向/图例/播放器』一次都没出现）。",
        "two_failure_modes_tested": {
            "A 混用": "三种语义套用同一个名字/通道",
            "B 缺失": "某种语义根本没定义 —— 只测 A 会漏掉 B",
        },
        "measured": res,
        "page": page,
        "passed": len(passed), "failed": len(failed), "failures": failed,
        "what_is_locked": [
            "①a/①b 两种语义已落地且有证据（order 字段、causeEdges 339 条）",
            "②a/②b 代码必须自述排序依据并显式排除因果与故事时间（basis 字符串）",
            "③a 阅读顺序 order 严格 1..n",
            "④b 页面**不得**声称用了「故事时间」（该语义未实现，说了就是虚假声明）",
        ],
        "what_is_still_a_real_gap": (
            (["①c 故事发生时间未落地；不能从阅读顺序推导实际发生时间。"] if not has_story_time else [])
            + (["④a 初开或剧情图例缺少可见的原文出现顺序声明。"]
               if page and not page.get("error") and not page.get("saysAppearance") else [])
        ),
        "a_threshold_i_invented_and_removed": "我最初断言「rawOrder 有值部分必须逐点单调」，"
            "实测 31 次回落 ⇒ 报红。回查计划：P1.2 **没有任何一句**要求 rawOrder 单调。"
            "那 31 次全部是**同章内相邻对调**（第一回 2→1、第九回 25→24），计划未禁止。"
            "⇒ 已删除该断言，改为如实报告覆盖率。**凭想象加的门限会把正常实现判成缺陷。**",
        "known_gap_locked_as_red_if_fixed": "①c 故意断言『故事发生时间尚未落地』。"
            "将来若实现了该语义，本条会变红，提醒把 ①c 改成已落地并补对应断言 —— "
            "**不让缺口在实现后悄悄留着**。",
    }
    p = out / "order-semantics.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    REGISTERED = ("①c ", "④a ")
    reg_failed = [f for f in failed
                  if any(f["name"].startswith(r) for r in REGISTERED)
                  and not f["name"].startswith("④z ")]
    hard_failed = [f for f in failed if f not in reg_failed]

    known = {
        "id": "P1.2",
        "storyTimeImplemented": has_story_time,
        "pageStatesOrderingSemantics": bool(
            page and not page.get("error")
            and page.get("saysAppearance")),
        "causeEdges": res.get("causeEdges"),
        "orderStrictSequence": bool((res.get("orderStrictSeq") or {}).get("strict")),
        "basisExcludesCausalityAndStoryTime": "not_causality" in str(res.get("basis") or ""),
    }
    report["knownFingerprint"] = known
    report["ratchet"] = {
        "registeredGaps": [f["name"] for f in reg_failed],
        "hardFailures": [f["name"] for f in hard_failed],
        "note": "已登记缺口在门禁口径下不计失败，但判据仍执行 —— 恶化会从 "
                "hardFailures 里出来。如故事时间被实现，①c 会变红提醒更新登记。",
    }

    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.ratchet:
        if hard_failed:
            print("\nP1.2 RATCHET FAIL · 出现**新**失败：%s" % [f["name"] for f in hard_failed])
            return 1
        print("\nP1.2 RATCHET OK · 已登记缺口 %d 条未恶化（%s）"
              % (len(reg_failed), [f["name"].strip() for f in reg_failed]))
        return 0

    if failed:
        print("\nP1.2 FAILURES: %d  (%d passed)" % (len(failed), len(passed)))
        return 1
    print("\nP1.2 ALL PASS  (%d passed)" % len(passed))
    print("产物：%s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
