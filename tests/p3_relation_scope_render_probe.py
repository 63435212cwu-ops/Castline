#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.9 真实页面探针：关系层必须显示**证据状态**与**范围**，并给出总账。

为什么不能只靠 tests/sky_relation_scope_contract.js：
  那个契约证明的是**判定语义**（七类识别、同场不算关系、无锚点须标出、
  全书汇总不默认成某时刻、strength 不是证据）与三书的计数（2106/1539 零锚点、
  西游 20 全锚点）。它证明不了「面板真的把这些显示出来了」——
  而本包的核心缺陷正是：`relationHonesty` 早已算出 anchored=0，
  却**只被 sky-export.js 消费**，解构面板渲染 2106 条时从不读它。

判据：
  ① 关系行出现 [data-rel-evidence]，取值来自真实数据；
  ② 关系行出现范围标记（限定时段 / 全书汇总）—— 计划「不能混淆」；
  ③ 大奉（2106 条零锚点）必须**每一行**都标「继承 · 待核验」，不得出现「原文锚点」；
  ④ 必须给出总账 .sd-rel-ledger，写明「没有任何一条有已核验的原文锚点」；
  ⑤ aria-label 必须写明证据与范围（读屏同样要能分辨）；
  ⑥ 关光/低档下标记仍可见。

用法：
  CL_GPU=1 python3 -B -s tests/p3_relation_scope_render_probe.py --base http://127.0.0.1:8781
"""
import argparse
import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from qa_cinema_wave02_capture import Wave2AuditRunner

BOOKS = {"dafeng": "1063b17ca65ec1b76f30e460", "xiyou": "a065244455cfb2221bcda94a"}
NEIGHBOR_BOOK = "ed3dc1255ca08fbdaae30bbd"
NEIGHBOR_GRAPH_SHA256 = "3005a49ae29146d3a7b78bc35767c0407bd265f459b7aed715306c51309b8eb5"
PAGE_HEALTH_JS = "(()=>{const h=window.__headlessHealth,A=window.CLApp,S=A&&A.scene(),G=A&&A.graph(),d=S&&S.digest&&S.digest(),sh=S&&S.shaderErrors&&S.shaderErrors();return {listener:!!h,jserr:h&&Array.isArray(h.jserr)?h.jserr:null,jsrej:h&&Array.isArray(h.jsrej)?h.jsrej:null,app:!!A,graph:!!G,graphKey:A&&A.key&&A.key(),scene:!!S,digest:!!d,frameHooks:d&&d.frameHooks||null,shaderErrors:Array.isArray(sh)?sh:null};})()"

OPEN = r"""(()=>{
  const out={};
  try{ if(window.CLSky&&CLSky.setDecon) CLSky.setDecon(true); }catch(e){ out.err=String(e); }
  try{
    CLSkyDeconstruction.open();
    CLSkyDeconstruction.setMode('mechanics');
    // 切到「人物关系」层 —— **必须限定在解构面板内**：
    // `#vbLayer`（视轨 HUD）也用 data-layer，且它先出现在 DOM 里，
    // 不限定范围会点到 HUD 上，面板永远停在「任务」层（实测踩过：数出 0 行）。
    const scope=document.querySelector('#skyDeconPanel')||document;
    const btns=[...scope.querySelectorAll('button[data-layer]')];
    out.layerButtons=btns.map(x=>x.getAttribute('data-layer'));
    const b=btns.find(x=>x.getAttribute('data-layer')==='relations');
    if(b) b.click();
    out.clicked=!!b;
  }catch(e){ out.modeErr=String(e); }
  return out;
})()"""

COLLECT = r"""(()=>{
  const out={};
  const rows=[...document.querySelectorAll('[data-rel-evidence]')];
  out.rowCount=rows.length;
  const ev={}, sc={}, kd={};
  rows.forEach(r=>{
    ev[r.getAttribute('data-rel-evidence')||'']=(ev[r.getAttribute('data-rel-evidence')||'']||0)+1;
    sc[r.getAttribute('data-rel-scope')||'']=(sc[r.getAttribute('data-rel-scope')||'']||0)+1;
    kd[r.getAttribute('data-rel-kind')||'']=(kd[r.getAttribute('data-rel-kind')||'']||0)+1;
  });
  out.evidence=ev; out.scope=sc; out.kinds=kd;
  const first=rows[0];
  if(first){
    out.firstEvidence=first.getAttribute('data-rel-evidence');
    out.firstScope=first.getAttribute('data-rel-scope');
    out.evidenceText=(first.querySelector('.sd-rel-evidence')||{}).textContent||null;
    out.scopeText=(first.querySelector('.sd-rel-scope')||{}).textContent||null;
    out.aria=(first.getAttribute('aria-label')||'').slice(0,260);
  }
  const led=document.querySelector('.sd-rel-ledger');
  out.ledgerPresent=!!led;
  out.ledgerText=led?(led.textContent||'').slice(0,300):null;
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const els=[...document.querySelectorAll('.sd-rel-evidence, .sd-rel-ledger')];
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
        opened = runner.eval(OPEN)
        if isinstance(opened, dict) and opened.get("__evalError"):
            opened = {}
        time.sleep(2.0)
        for _ in range(3):
            st = runner.eval("(()=>{const b=[...document.querySelectorAll('#skyDeconPanel button[data-layer]')]"
                             ".find(x=>x.getAttribute('data-layer')==='relations');"
                             "return {pressed: b? b.getAttribute('aria-pressed'):null,"
                             " rows: document.querySelectorAll('[data-rel-evidence]').length};})()")
            if isinstance(st, dict) and (st.get("rows") or 0) >= 1:
                break
            runner.eval("(()=>{const b=[...document.querySelectorAll('#skyDeconPanel button[data-layer]')]"
                        ".find(x=>x.getAttribute('data-layer')==='relations'); if(b) b.click(); return true;})()")
            time.sleep(1.5)
        got = runner.eval(COLLECT)
        if isinstance(got, dict) and got.get("__evalError"):
            got = {}
        time.sleep(0.8)
        dim = runner.eval(DIM)
        if isinstance(dim, dict) and dim.get("__evalError"):
            dim = {}
        return opened, got, dim
    finally:
        try:
            runner.close()
        except Exception:
            pass


def _native_click(runner, selector):
    """Click a visible control using CDP mouse input, never HTMLElement.click()."""
    point = runner.eval("(()=>{const e=document.querySelector(%s);if(!e)return null;e.scrollIntoView({block:'center',inline:'nearest'});const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,t=document.elementFromPoint(x,y);return {x:x,y:y,visible:!!(r.width&&r.height&&getComputedStyle(e).visibility!=='hidden'),disabled:!!e.disabled,hit:!!(t&&(t===e||e.contains(t))),target:t&&t.tagName};})()" % json.dumps(selector))
    if not isinstance(point, dict) or not point.get("visible") or point.get("disabled") or not point.get("hit"):
        raise RuntimeError("native click target unavailable: %s (%r)" % (selector, point))
    runner.ws.call("Input.dispatchMouseEvent", type="mouseMoved", x=point["x"], y=point["y"])
    runner.ws.call("Input.dispatchMouseEvent", type="mousePressed", x=point["x"], y=point["y"], button="left", clickCount=1)
    runner.ws.call("Input.dispatchMouseEvent", type="mouseReleased", x=point["x"], y=point["y"], button="left", clickCount=1)


def _wait_value(runner, expression, timeout=12, interval=0.05):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = runner.eval(expression)
        if last is True:
            return True
        time.sleep(interval)
    return last


def _native_typeahead(runner, text):
    for char in text:
        runner.ws.call("Input.dispatchKeyEvent", type="char", key=char, text=char, unmodifiedText=char)


def probe_neighbors(base, width, height, reduced, mobile):
    """Real C1 path. A is fixture setup through the public showPerson API; all user controls use CDP input."""
    runner = Wave2AuditRunner(width=width, height=height, dpr=1)
    graph_path = ROOT / "data" / "cache" / (NEIGHBOR_BOOK + ".json")
    graph_sha = hashlib.sha256(graph_path.read_bytes()).hexdigest()
    report = {"book": NEIGHBOR_BOOK, "graphSha256": graph_sha,
              "viewport": {"width": width, "height": height, "mobile": mobile},
              "reducedMotion": reduced, "input": "CDP trusted mouse + native select typeahead"}
    report["checks"] = {"fixed_graph_hash": graph_sha == NEIGHBOR_GRAPH_SHA256}
    if graph_sha != NEIGHBOR_GRAPH_SHA256:
        report["fatal"] = "fixed C1 graph hash changed; refusing silent fixture substitution"
        report["ok"] = False
        return report
    try:
        runner.start()
        runner.ws.call("Emulation.setDeviceMetricsOverride", width=width, height=height,
                       deviceScaleFactor=1, mobile=mobile)
        runner.ws.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion",
                                                                  "value": "reduce" if reduced else "no-preference"}])
        runner.navigate("%s/?sky=1&data=data/cache/%s.json" % (base, NEIGHBOR_BOOK))
        deadline = time.time() + 150
        while time.time() < deadline:
            if runner.eval("!!(window.CLApp&&CLApp.graph()&&CLApp.key()==='%s'&&window.CLSky&&document.querySelector('#loader.off'))" % NEIGHBOR_BOOK) is True:
                break
            time.sleep(0.4)
        else:
            raise RuntimeError("fixed Xiyou graph did not finish loading")
        setup = runner.eval("(()=>{CLSkyDeconstruction.setMode('people');return CLSkyDeconstruction.showPerson('孙悟空');})()")
        report["public_a_setup"] = {"method": "CLSkyDeconstruction.showPerson", "name": "孙悟空", "ok": setup is True}
        if setup is not True:
            raise RuntimeError("public A setup did not find 孙悟空")
        panel_ready = _wait_value(runner, "!!(window.CLSkyDeconstruction&&CLSkyDeconstruction.ready()&&document.querySelector('#skyDeconPanel .sd-person-actions [data-action=neighbor-open]'))")
        if panel_ready is not True:
            raise RuntimeError("A person action row did not settle after public showPerson setup: %r" % panel_ready)
        runner.eval("(()=>{const e=document.querySelector('#skyDeconPanel .sd-person-actions [data-action=neighbor-open]');if(e)e.scrollIntoView({block:'center',inline:'nearest'});return !!e})()")
        click_ready = _wait_value(runner, "(()=>{const e=document.querySelector('#skyDeconPanel .sd-person-actions [data-action=neighbor-open]');if(!e)return false;const r=e.getBoundingClientRect(),t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return !!(r.width&&r.height&&t&&(t===e||e.contains(t)))})()")
        if click_ready is not True:
            raise RuntimeError("neighbor-open target did not become hittable after scrolling")
        a_identity = runner.eval("(()=>{const p=document.querySelector('#skyDeconPanel .sd-person.is-focus');return p&&p.getAttribute('data-person-detail')})()")
        report["A_stable_id"] = a_identity
        report["checks"]["A_uses_frozen_stable_id"] = a_identity == "ch_25537390c961aa39"
        _native_click(runner, "#skyDeconPanel .sd-person-actions [data-action=neighbor-open]")
        b_ready = _wait_value(runner, "!!document.querySelector('#skyDeconPanel select[data-neighbor-person=b]')")
        if b_ready is not True:
            raise RuntimeError("B select did not render after native open action")
        focus = runner.eval("(()=>{window.__c1NativeChange=[];document.addEventListener('change',e=>{if(e.target.matches&&e.target.matches('select[data-neighbor-person=b],select[data-neighbor-kind=filter]'))window.__c1NativeChange.push({trusted:e.isTrusted,attr:e.target.getAttribute('data-neighbor-person')?'person':'kind',value:e.target.value});},true);const s=document.querySelector('#skyDeconPanel select[data-neighbor-person=b]');if(s)s.focus();return !!s&&document.activeElement===s;})()")
        if focus is not True:
            raise RuntimeError("B selector did not receive focus before native typeahead")
        _native_typeahead(runner, "猪")
        initial = runner.eval("new Promise(resolve=>requestAnimationFrame(()=>resolve({lines:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-line').length,nodes:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-node').length,owners:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-owner').length})))", await_promise=True)
        report["first_frame"] = initial
        time.sleep(0.75)
        state = runner.eval("(()=>{const s=document.querySelector('#skyDeconPanel select[data-neighbor-person=b]'),n=document.querySelector('#skyDeconPanel .sd-neighbor');if(!s||!n)return null;const tabs=[...n.querySelectorAll('[data-neighbor-tab]')];return {b:s.value,events:window.__c1NativeChange||[],tabs:tabs.map(x=>({id:x.getAttribute('data-neighbor-tab'),text:x.textContent,pressed:x.getAttribute('aria-pressed')})),groups:[...n.querySelectorAll('.sd-neighbor-person')].map(x=>x.getAttribute('data-neighbor-id')),note:(n.querySelector('.sd-neighbor-note')||{}).textContent||'',aLabel:(n.querySelector('.sd-neighbor-head')||{}).textContent||'',fiberCount:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-line').length,nodeCount:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-node').length,ownerLabels:[...document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-owner-label')].map(x=>({text:x.textContent,box:(()=>{const r=x.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}})()}))};})()")
        if not isinstance(state, dict):
            raise RuntimeError("native B typeahead did not open comparison")
        report["after_typeahead"] = state
        if state.get("b") != "ch_1dee9e1be8a97b5f" or not any(e.get("trusted") for e in state.get("events", [])):
            raise RuntimeError("native B selection was not trusted or did not resolve to 猪八戒")
        def tab_count(tab_id):
            _native_click(runner, "#skyDeconPanel [data-action=neighbor-tab][data-neighbor-tab=%s]" % tab_id)
            time.sleep(0.18)
            return runner.eval("(()=>{const n=document.querySelector('#skyDeconPanel .sd-neighbor'),b=n&&n.querySelector('[data-neighbor-tab=%s]');return {pressed:b&&b.getAttribute('aria-pressed'),count:n&&n.querySelectorAll('.sd-neighbor-person').length,ids:n?[...n.querySelectorAll('.sd-neighbor-person')].map(x=>x.getAttribute('data-neighbor-id')):[],lines:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-line').length};})()" % json.dumps(tab_id))
        groups = {key: tab_count(key) for key in ("common", "onlyA", "onlyB")}
        report["groups"] = groups
        report["checks"].update({
            "common_exact": groups["common"].get("count") == 1 and groups["common"].get("ids") == ["ch_0ebf2655f1fb3db3"],
            "only_a_exact": groups["onlyA"].get("count") == 6,
            "only_b_empty": groups["onlyB"].get("count") == 0,
            "native_change_trusted": any(e.get("trusted") for e in state.get("events", [])),
            "line_budget": 0 <= state.get("fiberCount", 999) <= 8,
            "demo_counts_match_scene_overlay": state.get("nodeCount") == 7 and state.get("fiberCount") == 8 and "当前组原位演示 1 / 1 人" in state.get("note", "") and "所有分组合计演示 7 人、8 条关系线" in state.get("note", ""),
            "owner_labels_visible_in_viewport": len(state.get("ownerLabels", [])) == 2 and all(0 <= x["box"]["left"] and x["box"]["right"] <= width and 0 <= x["box"]["top"] and x["box"]["bottom"] <= height for x in state.get("ownerLabels", [])),
        })
        shot_dir = Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-relation-neighbors"
        shot_dir.mkdir(parents=True, exist_ok=True)
        screenshot = runner.ws.call("Page.captureScreenshot", format="png")
        shot = shot_dir / ("%s-%s-compare-%s.png" % ("mobile" if mobile else "desktop", "reduced" if reduced else "motion", int(time.time())))
        shot.write_bytes(base64.b64decode(screenshot["data"]))
        report["screenshot_comparison"] = str(shot)
        responsive = runner.eval("(()=>{const n=document.querySelector('#skyDeconPanel .sd-neighbor'),s=n&&n.querySelector('select[data-neighbor-person=b]'),tabs=n&&n.querySelector('.sd-neighbor-tabs'),r=n&&n.getBoundingClientRect();return {width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,selectHeight:s&&s.getBoundingClientRect().height,tabsDirection:tabs&&getComputedStyle(tabs).flexDirection,panelWidth:r&&r.width};})()")
        report["responsive"] = responsive
        if mobile:
            report["checks"]["mobile_vertical_and_no_horizontal_overflow"] = bool(responsive.get("tabsDirection") == "column" and responsive.get("scrollWidth") <= responsive.get("clientWidth") + 1 and responsive.get("selectHeight") >= 44)
        else:
            report["checks"]["desktop_layout_fits_viewport"] = bool(responsive.get("scrollWidth") <= responsive.get("clientWidth") + 1)
        tab_count("onlyA")
        _native_click(runner, "#skyDeconPanel .sd-neighbor-person [data-action=neighbor-basis]")
        time.sleep(0.3)
        relation = runner.eval("(()=>({open:!!document.querySelector('#skyDeconPanel .sd-mechanics-card'),back:!!document.querySelector('#skyDeconPanel [data-action=neighbor-return]')}))()")
        report["basis"] = relation
        _native_click(runner, "#skyDeconPanel [data-action=neighbor-return]")
        time.sleep(0.2)
        returned = runner.eval("(()=>{const n=document.querySelector('#skyDeconPanel .sd-neighbor'),s=n&&n.querySelector('select[data-neighbor-person=b]'),r=s&&s.getBoundingClientRect(),body=document.querySelector('#skyDeconBody'),br=body&&body.getBoundingClientRect();return {visible:!!n,b:s&&s.value,tab:n&&[...n.querySelectorAll('[data-neighbor-tab]')].filter(x=>x.getAttribute('aria-pressed')==='true').map(x=>x.getAttribute('data-neighbor-tab')),scroll:body&&body.scrollTop,focus:document.activeElement===s,selectorVisible:!!(r&&br&&r.top>=br.top&&r.bottom<=br.bottom)};})()")
        report["returned"] = returned
        report["checks"]["basis_roundtrip_keeps_b_tab_focus_and_scroll"] = bool(relation.get("open") and relation.get("back") and returned.get("visible") and returned.get("b") == "ch_1dee9e1be8a97b5f" and returned.get("tab") == ["onlyA"] and returned.get("focus") and returned.get("selectorVisible"))
        kind_focus = runner.eval("(()=>{const s=document.querySelector('#skyDeconPanel select[data-neighbor-kind=filter]');if(s)s.focus();return !!s&&document.activeElement===s})()")
        if not kind_focus:
            raise RuntimeError("relation-type selector did not receive focus")
        _native_typeahead(runner, "师徒")
        time.sleep(0.4)
        filtered = runner.eval("(()=>{const n=document.querySelector('#skyDeconPanel .sd-neighbor'),s=n&&n.querySelector('select[data-neighbor-kind=filter]');return {kind:s&&s.value,active:n&&[...n.querySelectorAll('[data-neighbor-tab]')].filter(x=>x.getAttribute('aria-pressed')==='true').map(x=>x.getAttribute('data-neighbor-tab')),common:n&&n.querySelectorAll('.sd-neighbor-person').length,recordLabels:n?[...n.querySelectorAll('.sd-neighbor-record')].map(x=>x.textContent):[],trusted:window.__c1NativeChange.filter(x=>x.attr==='kind').map(x=>x.trusted)};})()")
        report["native_type_filter"] = filtered
        report["checks"]["native_type_filter_recalculates_list"] = bool(filtered.get("kind") == "mentorship" and filtered.get("active") == ["common"] and filtered.get("common") == 1 and len(filtered.get("recordLabels", [])) == 2 and all("师徒" in x for x in filtered.get("recordLabels", [])) and any(filtered.get("trusted", [])))
        _native_click(runner, "#skyDeconPanel .sd-neighbor-clear")
        time.sleep(0.2)
        single = runner.eval("(()=>{const n=document.querySelector('#skyDeconPanel .sd-neighbor'),s=n&&n.querySelector('select[data-neighbor-person=b]');return {b:s&&s.value,groups:[...n.querySelectorAll('[data-neighbor-tab]')].map(x=>x.textContent),a:(n.querySelector('.sd-neighbor-head')||{}).textContent||'',lines:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-line').length};})()")
        report["after_clear_b"] = single
        report["checks"]["clear_b_restores_single_person"] = bool(single.get("b") == "" and any("A的一度联系人" in x for x in single.get("groups", [])))
        _native_click(runner, "#skyDeconPanel [role=tab][data-mode=overview]")
        time.sleep(0.15)
        mode_clear = runner.eval("(()=>({mode:document.querySelector('#skyDeconPanel [role=tab][data-mode=overview]')?.getAttribute('aria-selected'),lines:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-line').length,nodes:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-node').length}))()")
        report["after_mode_change"] = mode_clear
        report["checks"]["leaving_comparison_clears_overlay"] = bool(mode_clear.get("lines") == 0 and mode_clear.get("nodes") == 0)
        _native_click(runner, "#skyDeconPanel .sd-close")
        close_overlay = runner.eval("(()=>({lines:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-line').length,nodes:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-node').length}))()")
        close_end = _wait_value(runner, "!!(document.querySelector('#skyDeconPanel')&&document.querySelector('#skyDeconPanel').hidden)", timeout=2)
        closed = runner.eval("(()=>({hidden:document.querySelector('#skyDeconPanel')?.hidden,lines:document.querySelectorAll('#skyRelationNeighborMarks .sky-neighbor-line').length}))()")
        report["after_close"] = {"overlayAtClose": close_overlay, "settled": close_end, "panel": closed}
        report["checks"]["close_clears_overlay"] = bool(close_overlay.get("lines") == 0 and close_overlay.get("nodes") == 0 and close_end is True and closed.get("hidden"))
        report["checks"]["reduced_motion_first_frame_is_final"] = (not reduced or (isinstance(initial, dict) and initial.get("lines") == 8 and initial.get("nodes") == 7 and initial.get("owners") == 2))
        shot_dir = Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-relation-neighbors"
        shot_dir.mkdir(parents=True, exist_ok=True)
        screenshot = runner.ws.call("Page.captureScreenshot", format="png")
        shot = shot_dir / ("%s-%s-%s.png" % ("mobile" if mobile else "desktop", "reduced" if reduced else "motion", int(time.time())))
        shot.write_bytes(base64.b64decode(screenshot["data"]))
        report["screenshot"] = str(shot)
        health = runner.eval(PAGE_HEALTH_JS)
        report["health"] = health
        ordinary = health
        report["ordinary_health"] = ordinary
        report["checks"]["CLApp_scene_health_fields_present"] = bool(isinstance(ordinary, dict) and isinstance(ordinary.get("jserr"), list) and isinstance(ordinary.get("jsrej"), list) and ordinary.get("app") and ordinary.get("graph") and ordinary.get("graphKey") == NEIGHBOR_BOOK and ordinary.get("scene") and ordinary.get("digest") and isinstance(ordinary.get("frameHooks"), dict) and isinstance(ordinary["frameHooks"].get("errors"), (int, float)) and isinstance(ordinary.get("shaderErrors"), list))
        frame_hooks = health.get("frameHooks") if isinstance(health, dict) else None
        report["checks"]["page_health_present_and_clean"] = bool(isinstance(health, dict) and health.get("jserr") == [] and health.get("jsrej") == [] and isinstance(frame_hooks, dict) and frame_hooks.get("errors") == 0 and health.get("shaderErrors") == [])
        report["ok"] = all(report["checks"].values())
        return report
    except Exception as error:
        report["fatal"] = str(error)
        report["ok"] = False
        try:
            failure_dir = Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-relation-neighbors"
            failure_dir.mkdir(parents=True, exist_ok=True)
            if runner.ws:
                report["failure_state"] = runner.eval("(()=>({active:document.activeElement&&document.activeElement.outerHTML,openButton:!!document.querySelector('#skyDeconPanel .sd-person-actions [data-action=neighbor-open]'),bSelect:!!document.querySelector('#skyDeconPanel select[data-neighbor-person=b]'),panelReady:window.CLSkyDeconstruction&&CLSkyDeconstruction.ready&&CLSkyDeconstruction.ready()}))()")
                shot = runner.ws.call("Page.captureScreenshot", format="png")
                failure_path = failure_dir / ("failure-%s.png" % int(time.time()))
                failure_path.write_bytes(base64.b64decode(shot["data"]))
                report["failure_screenshot"] = str(failure_path)
        except Exception as capture_error:
            report["failure_capture_error"] = str(capture_error)
        try:
            report["health"] = runner.eval(PAGE_HEALTH_JS)
        except Exception as health_error:
            report["health_error"] = str(health_error)
        return report
    finally:
        try:
            runner.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p3-relation-scope"))
    ap.add_argument("--neighbors", action="store_true", help="运行C1/M97固定西游双人关系页面路径，使用CDP原生输入")
    viewport = ap.add_mutually_exclusive_group()
    viewport.add_argument("--neighbors-desktop", dest="neighbors_mobile", action="store_false", help="C1路径使用1440×900桌面模拟（默认）")
    viewport.add_argument("--neighbors-mobile", dest="neighbors_mobile", action="store_true", help="C1路径使用390×844窄屏模拟")
    ap.set_defaults(neighbors_mobile=False)
    ap.add_argument("--reduced-motion", action="store_true", help="C1路径模拟prefers-reduced-motion: reduce")
    ap.add_argument("--neighbors-out", default=str(Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p3-relation-neighbors"))
    args = ap.parse_args()
    if args.neighbors:
        width, height = (390, 844) if args.neighbors_mobile else (1440, 900)
        result = probe_neighbors(args.base, width, height, args.reduced_motion, args.neighbors_mobile)
        out = Path(args.neighbors_out)
        out.mkdir(parents=True, exist_ok=True)
        variant = ("mobile" if args.neighbors_mobile else "desktop") + ("-reduced" if args.reduced_motion else "-motion")
        report_path = out / ("%s-%s.json" % (variant, int(time.time())))
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"ok": result.get("ok", False), "checks": result.get("checks"), "fatal": result.get("fatal"),
                          "report": str(report_path), "screenshot": result.get("screenshot")}, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    problems, checks = [], []
    def check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            problems.append(name)
        print(("PASS " if ok else "FAIL ") + name + "  · " + str(detail), flush=True)

    opened, dafeng, dim = probe(args.base, BOOKS["dafeng"])
    check("① 关系行渲染出证据标记 [data-rel-evidence]",
          (dafeng.get("rowCount") or 0) >= 1,
          "rows=%s evidence=%s kinds=%s" % (dafeng.get("rowCount"), dafeng.get("evidence"), dafeng.get("kinds")))
    check("② 关系行渲染出范围标记（限定时段/全书汇总），两件事可分辨",
          bool(dafeng.get("scope")) and bool(dafeng.get("scopeText")),
          "scope=%s text=%r" % (dafeng.get("scope"), dafeng.get("scopeText")))
    ev = dafeng.get("evidence") or {}
    check("③ 大奉每一行都必须是「继承 · 待核验」，不得出现「原文锚点」",
          ev.get("inherited-pending", 0) >= 1 and not ev.get("anchored"),
          "evidence=%s" % ev)
    ledger = dafeng.get("ledgerText") or ""
    check("④ 必须给出关系证据总账，写明没有任何一条有已核验锚点",
          bool(dafeng.get("ledgerPresent")) and ("没有任何一条有已核验的原文锚点" in ledger),
          repr(ledger[:170]))
    aria = dafeng.get("aria") or ""
    check("⑤ aria-label 必须写明证据与范围",
          ("继承" in aria) and ("全书汇总" in aria or "限定时段" in aria),
          repr(aria[:180]))
    check("⑥ 关光/低档下证据标记与总账仍可见",
          (dim.get("visible") or 0) >= 1, "tags=%s visible=%s" % (dim.get("tags"), dim.get("visible")))

    _, xiyou, _ = probe(args.base, BOOKS["xiyou"])
    xev = xiyou.get("evidence") or {}
    check("⑦ 对照组西游（20 条全锚点）必须显示「原文锚点」，与大奉不同",
          xev.get("anchored", 0) >= 1 and not xev.get("inherited-pending"),
          "xiyou evidence=%s kinds=%s" % (xev, xiyou.get("kinds")))

    report = {"plan_ref": "docs/QUALITY.md P3.9", "base": args.base,
              "dafeng": dafeng, "xiyou": xiyou, "dim": dim,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
