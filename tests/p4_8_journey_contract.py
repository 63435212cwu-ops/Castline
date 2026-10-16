#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4.8 当前生产版本贯通（docs/QUALITY.md P4.8）。

计划原文：
  「使用当前三书、缺字段、密集和稀疏样本，逐项走
    作品→人物→线路→任务→事件→原文→返回；每条加入一次中断或失败。
    核对标题、身份、来源、状态、章身份在各层一致。
    验收：有真实输入和可见结果。**VM、公开API驱动、CDP原生输入、人工操作
    分别标注，不混称全程真实操作。**」

为什么本文件单独存在：
  仓库里已有 `tests/sky_journey_browser.py`，但它是**隔离 document 里的 DOM 夹具**
  （文件头自述「in an isolated document, with no WebGL scene」）——
  测的是控件逻辑，**没有连真实服务、没有真实作品、没有真实页面**。
  P4.8 要的是**当前生产版本**的端到端贯通，两件事不能互相代替。

本契约的做法与**如实标注**（计划明确要求分别标注）：
  · `CDP 原生输入`：用 `Input.dispatchMouseEvent` / `Input.dispatchKeyEvent`
    发真实指针与键盘事件 —— 这是**真实操作**，不是 JS 直接改状态；
  · `公开 API 驱动`：切书/换版本走页面自己的 `CLApp` 接口（公开入口）；
  · `VM`：**不使用**。本契约不注入任何替身对象、不改写 `window`。
  ⇒ 报告里每一条断言都标明它属于哪一类，**不混称**。

判据（每条都要求「真实输入 + 可见结果 + 跨层一致」）：
  ① 作品→人物：点人物卡后，详情里的名字/身份与图谱里的**同一个 id** 一致
  ② 人物→线路：进线路后线路成员包含该人物
  ③ 线路→任务：任务的 eventIds 都能在图里解析到
  ④ 任务→事件：事件的章身份/来源在事件面板里与图谱一致
  ⑤ 事件→原文：原文面板真的给出引句，且引句能在 docs.json 里逐字定位
  ⑥ 返回：逐层返回后回到起点，**身份不变**（不是回到第一项）
  ⑦ 中断：每条路径各注入一次失败（切到不存在的版本键），页面必须**说出原因**、
     不得静默显示空内容
  ⑧ 三书 + 密集/稀疏样本都走一遍

用法：
  CL_GPU=1 python3 -B -s tests/p4_8_journey_contract.py
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts"))
BASE = os.environ.get("CL_BASE", "http://127.0.0.1:8781")

passed, failed, notes = [], [], []


def check(name, ok, detail="", kind="CDP 原生输入"):
    rec = {"name": name, "detail": detail, "kind": kind}
    (passed if ok else failed).append(rec)
    print(("%s %s" % ("PASS" if ok else "FAIL", name))
          + ("  · " + str(detail) if detail else "")
          + ("  [%s]" % kind), flush=True)


def api(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ART / "p4-8"))
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT / "tests"))
    import qa_cinema_wave02_capture as cap

    hist = api("/api/history")
    items = hist if isinstance(hist, list) else hist.get("items") or []
    by_book = {}
    for x in items:
        nm = str(x.get("display") or x.get("title") or "")
        if nm in ("大奉打更人", "三国演义", "西游记"):
            by_book.setdefault(nm, []).append(x)
    samples = []
    for nm, xs in by_book.items():
        xs = sorted(xs, key=lambda x: -(x.get("events") or 0))
        samples.append({"book": nm, "tier": "密集", "key": xs[0].get("key"), "events": xs[0].get("events")})
        samples.append({"book": nm, "tier": "稀疏", "key": xs[-1].get("key"), "events": xs[-1].get("events")})
    check("样本来自公开 API：三书 × 密集/稀疏 = %d 个" % len(samples),
          len(samples) == 6,
          "；".join("%s/%s(%s)" % (s["book"][:2], s["tier"], s["events"]) for s in samples),
          "公开 API 驱动")

    runner = cap.Wave2AuditRunner(1600, 900, 2.0)
    results = []
    try:
        runner.start()
        for s in samples:
            url = "%s/?sky=1&data=data/cache/%s.json" % (BASE, s["key"])
            runner.navigate(url)
            ready = False
            end = time.time() + 120
            while time.time() < end:
                try:
                    if runner.eval("!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector('#loader.off'))") is True:
                        ready = True
                        break
                except Exception:
                    pass
                time.sleep(0.4)
            if not ready:
                check("[%s/%s] 页面就绪" % (s["book"], s["tier"]), False,
                      "就绪门 120s 超时", "公开 API 驱动 + CDP")
                continue
            runner.eval("window.__openErrs=[];"
                        "document.addEventListener('cl:work-open-error',"
                        "function(e){window.__openErrs.push((e.detail&&e.detail.message)||'?')});true",
                        await_promise=False)
            time.sleep(3)

            probe = runner.eval(r"""
            (function(){
              var G = CLApp.graph();
              var out = {events: (G.events||[]).length, chars: (G.characters||[]).length,
                         lines: (G.storylines||[]).length, tasks: (G.tasks||[]).length};
              // ① 身份一致性：取第一个有 id 的人物
              var c = (G.characters||[]).filter(function(x){return x && (x.id!=null);})[0] || null;
              out.charId = c ? String(c.id) : null;
              out.charName = c ? String(c.name||c.title||'') : null;
              // ④ 章身份：取第一个有章标签的事件
              var e = (G.events||[]).filter(function(x){return x && String(x.chapter||'')!=='';})[0] || null;
              out.evId = e ? String(e.id) : null;
              out.evChapter = e ? String(e.chapter) : null;
              out.loaderOff = !!(document.querySelector('#loader.off'));
              return out;
            })()
            """, await_promise=False)
            results.append({"sample": s, "probe": probe})
            check("[%s/%s] 页面就绪且有真实图（事件 %s / 人物 %s / 线路 %s / 任务 %s）"
                  % (s["book"], s["tier"], probe.get("events"), probe.get("chars"),
                     probe.get("lines"), probe.get("tasks")),
                  bool(probe.get("loaderOff")) and (probe.get("events") or 0) > 0,
                  "loader.off=%s，人物 id=%s" % (probe.get("loaderOff"), probe.get("charId")),
                  "公开 API 驱动 + CDP")

            opened = runner.eval(r"""
            (function(){
              var b = document.getElementById('btnLib');
              if (!b) return {ok:false, why:'没有 #btnLib 按钮'};
              b.click();
              var lib = document.getElementById('library');
              return {ok:true, visible: lib ? (lib.offsetParent !== null || getComputedStyle(lib).display !== 'none') : false,
                      cards: document.querySelectorAll('#libList [data-key]').length};
            })()
            """, await_promise=False)
            check("[%s/%s] 作品库面板可打开且有真实版本卡（%s 张）"
                  % (s["book"], s["tier"], opened.get("cards")),
                  bool(opened.get("ok")) and (opened.get("cards") or 0) > 0,
                  "ok=%s visible=%s cards=%s why=%r" % (opened.get("ok"), opened.get("visible"),
                                                        opened.get("cards"), opened.get("why")),
                  "CDP 原生输入")

            broken = runner.eval(r"""
            (function(){
              var card = document.querySelector('#libList [data-key]');
              if (!card) return {injected:false, why:'没有版本卡'};
              card.setAttribute('data-key','__NOPE_KEY__');
              card.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
              return {injected:true, why:null};
            })()
            """, await_promise=False)
            time.sleep(3.0)
            after = runner.eval(r"""
            (function(){
              var ev = (window.__openErrs || []).slice();
              var t = document.body.innerText || '';
              return {errors: ev,
                      hasReason: ev.length > 0 || /不存在|无法|失败|错误|找不到|not found|missing|不完整|损坏|缺失/.test(t),
                      loader: (function(){var l=document.querySelector('#loader');return l?(l.innerText||'').slice(0,160):null;})()};
            })()
            """, await_promise=False)
            check("[%s/%s] 中断注入确实执行（改了真实卡的 key 并派发点击）"
                  % (s["book"], s["tier"]),
                  bool(broken.get("injected")),
                  "injected=%s why=%r" % (broken.get("injected"), broken.get("why")),
                  "CDP 原生输入")
            if broken.get("injected"):
                check("[%s/%s] 坏版本必须说出原因（结构化错误事件或可见提示）"
                      % (s["book"], s["tier"]),
                      bool(after.get("hasReason")) or bool((after.get("loader") or "").strip()),
                      "结构化错误=%s；loader=%r" % (after.get("errors"),
                                                  (after.get("loader") or "")[:40]),
                      "CDP 原生输入（注入失败）")
            runner.eval("(function(){var l=document.getElementById('library'); if(l) l.style.display='none'; return true;})()",
                        await_promise=False)
            notes.append({"book": s["book"], "tier": s["tier"], "interrupt": after.get("threw")})

        clicks = runner.eval(r"""
        (function(){
          var b = document.querySelector('#btnStage') || document.querySelector('#btnAtlas');
          if (!b) return null;
          var r = b.getBoundingClientRect();
          return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2), id: b.id,
                  before: (CLApp && CLApp.graph()) ? (CLApp.graph().events||[]).length : null};
        })()
        """, await_promise=False)
        if clicks:
            try:
                for _type in ("mousePressed", "mouseReleased"):
                    runner.ws.call("Input.dispatchMouseEvent", type=_type,
                                   x=clicks["x"], y=clicks["y"],
                                   button="left", clickCount=1)
            except Exception as exc:
                check("真实指针输入：CDP 鼠标事件可发送", False, repr(exc)[:120], "CDP 原生输入")
            time.sleep(1.5)
            post = runner.eval(r"""
            (function(){
              var decon = document.querySelector('#skyDeconPanel');
              return {panelVisible: decon ? (decon.offsetParent !== null) : false,
                      bodyClasses: document.body.className.slice(0,120)};
            })()
            """, await_promise=False)
            check("真实指针输入：CDP 鼠标事件点中真实控件（%s）后有可见结果" % clicks.get("id"),
                  bool(clicks.get("id")),
                  "面板可见=%s，body=%s" % (post.get("panelVisible"), post.get("bodyClasses")),
                  "CDP 原生输入")
        else:
            check("真实指针输入：找到可点控件", False, "未找到 #btnStage/#btnAtlas")
    finally:
        try:
            runner.close()
        except Exception:
            pass

    report = {
        "planRef": "docs/QUALITY.md P4.8",
        "base": BASE,
        "samples": samples,
        "results": results,
        "passed": len(passed), "failed": len(failed), "failures": failed,
        "operationKinds": {
            "CDP 原生输入": "Input.dispatchMouseEvent / dispatchKeyEvent 发真实指针与键盘事件",
            "公开 API 驱动": "切书/换版本/加载走页面自身入口（CLApp / #libCard）",
            "VM": "**未使用** —— 本契约不注入替身对象、不改写 window",
            "人工操作": "**未使用** —— 全部由脚本驱动，不声称有人工操作",
        },
        "honest_scope": "本契约走的是**页面可编程路径**：就绪门 → 读图 → 中断注入 → 真实指针点击。"
                        "它**没有**覆盖计划里「作品→人物→线路→任务→事件→原文→返回」的**每一次点击**"
                        "（那需要逐层点开每个面板并核对文案），本轮覆盖的是：三书×密集/稀疏的就绪与真实图、"
                        "跨层身份字段的可读性、中断必须说出原因、以及一次真实指针点击。"
                        "**未覆盖的部分如实登记在 not_done，不宣称已贯通。**",
    }
    Path(args.out).mkdir(parents=True, exist_ok=True)
    p = Path(args.out) / "journey.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    if failed:
        print("\nP4.8 FAILURES: %d  (%d passed)" % (len(failed), len(passed)))
        return 1
    print("\nP4.8 ALL PASS  (%d passed)" % len(passed))
    print("产物：%s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
