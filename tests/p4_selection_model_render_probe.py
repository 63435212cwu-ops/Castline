#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4.5 真实页面探针：人物选中必须按**稳定 ID**，且不得跨书按同名映射。

为什么不能只靠 tests/sky_selection_model_contract.js：
  那个契约证明的是**纯函数语义**（四态独立、跨图拒名字键、换书清引用、
  重绘不回落第一条）与**真实同名数据**（大奉∩三国「赵广」、大奉∩西游「刘洪」）。
  它证明不了「页面上真的改用稳定 ID 了」—— 而本包的核心缺陷正是
  `personDetail === p.name` 这类**按名字存选中**。

判据：
  ① 模块在真实页面上可用；
  ② 人物行的 `data-person-detail` 必须是**稳定 ID**（形如 ch_…），**不得**是名字；
  ③ 名字必须另有出口（`data-person-name`），不是被丢掉；
  ④ 点选一个人物后，选中键仍是稳定 ID（不是被回写成名字）；
  ⑤ 关光/低档下选中态仍可见。

用法：
  CL_GPU=1 python3 -B -s tests/p4_selection_model_render_probe.py --base http://127.0.0.1:8781
"""
import argparse
import base64
import json
import os
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
  try{
    CLSkyDeconstruction.open();
    CLSkyDeconstruction.setMode('people');
    out.modeOk=true;
  }catch(e){ out.modeOk=false; out.modeErr=String(e); }
  return out;
})()"""

COLLECT = r"""(()=>{
  const out={};
  out.moduleLoaded=!!window.CLSkySelectionModel;
  const btns=[...document.querySelectorAll('[data-person-detail]')];
  out.rows=btns.length;
  const keys=btns.map(b=>b.getAttribute('data-person-detail')||'');
  const names=btns.map(b=>b.getAttribute('data-person-name')||'');
  out.keySample=keys.slice(0,4);
  // 稳定 ID 判据：形如 ch_xxx 且不等于该行的名字
  out.stableKeys=keys.filter(k=>/^ch_/.test(k)).length;
  out.nameLikeKeys=keys.filter(k=>k && !/^ch_/.test(k)).length;
  out.withNameAttr=names.filter(n=>n.trim()).length;
  // 键是否恰好等于名字（那就是按名字存）
  out.keyEqualsName=keys.filter((k,i)=>k && k===names[i]).length;
  return out;
})()"""

CLICK = r"""(()=>{
  const b=document.querySelector('[data-person-detail]');
  if(!b) return {clicked:false};
  const before=b.getAttribute('data-person-detail');
  b.click();
  return {clicked:true, before:before};
})()"""

AFTER = r"""(()=>{
  const out={};
  const focus=[...document.querySelectorAll('[data-person-detail].is-focus')];
  out.focused=focus.length;
  out.focusedKey=focus.length?focus[0].getAttribute('data-person-detail'):null;
  out.focusedName=focus.length?focus[0].getAttribute('data-person-name'):null;
  const sel=document.querySelector('[aria-current="true"][data-person-detail]');
  out.selectedKey=sel?sel.getAttribute('data-person-detail'):null;
  out.selectedIsStable=sel?/^ch_/.test(sel.getAttribute('data-person-detail')||''):null;
  return out;
})()"""

DIM = r"""(()=>{
  document.documentElement.classList.add('no-bloom','is-dim','reduce-motion');
  const els=[...document.querySelectorAll('.sd-person.is-focus')];
  const vis=els.filter(e=>{const s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden';});
  return {tags:els.length, visible:vis.length};
})()"""

PICK_OVERLAP = r"""(()=>{
  const S=CLApp&&CLApp.scene&&CLApp.scene(),graph=CLApp&&CLApp.graph&&CLApp.graph(),canvas=document.querySelector('#gl'),TH=window.THREE;
  if(!S||!S.nodeOf||!S.camera||!S.pickCandidatesAt||!graph||!canvas||!TH)return {found:false,reason:'scene_projection_api_missing'};
  const rect=canvas.getBoundingClientRect(),v=new TH.Vector3(),worldScale=new TH.Vector3(),right=new TH.Vector3(),up=new TH.Vector3(),rows=[];
  S.camera.updateMatrixWorld(true);
  right.setFromMatrixColumn(S.camera.matrixWorld,0);up.setFromMatrixColumn(S.camera.matrixWorld,1);
  (graph.characters||[]).forEach(c=>{
    const n=S.nodeOf('c:'+c.name);if(!n||!n.render||!n.g||!n.g.visible||!n.sp||n.alpha<=.3)return;
    n.sp.getWorldPosition(v);const world=v.clone();n.sp.getWorldScale(worldScale);v.project(S.camera);
    const x=rect.left+(v.x+1)*rect.width/2,y=rect.top+(-v.y+1)*rect.height/2;
    if(x<rect.left||x>rect.right||y<rect.top||y>rect.bottom)return;
    const box={left:Infinity,right:-Infinity,top:Infinity,bottom:-Infinity};
    [-1,1].forEach(sx=>[-1,1].forEach(sy=>{
      const corner=world.clone().addScaledVector(right,sx*worldScale.x/2).addScaledVector(up,sy*worldScale.y/2).project(S.camera);
      const px=rect.left+(corner.x+1)*rect.width/2,py=rect.top+(-corner.y+1)*rect.height/2;
      box.left=Math.min(box.left,px);box.right=Math.max(box.right,px);box.top=Math.min(box.top,py);box.bottom=Math.max(box.bottom,py);
    }));
    rows.push({node:n,x,y,box,id:String(c.id!=null?c.id:c.entityId),name:c.name});
  });
  const pairs=[];
  for(let i=0;i<rows.length;i++)for(let j=i+1;j<rows.length;j++){
    const a=rows[i],b=rows[j],left=Math.max(a.box.left,b.box.left),right=Math.min(a.box.right,b.box.right),top=Math.max(a.box.top,b.box.top),bottom=Math.min(a.box.bottom,b.box.bottom);
    if(left<=right&&top<=bottom){const d=Math.hypot(a.x-b.x,a.y-b.y);pairs.push({a,b,d,x:(left+right)/2,y:(top+bottom)/2});}
  }
  pairs.sort((a,b)=>a.d-b.d);const candidates=[];
  for(const pair of pairs){
    const target=document.elementFromPoint(pair.x,pair.y);
    if(!target||!(target===canvas||(target.closest&&target.closest('#labels'))))continue;
    if(target.closest&&target.closest('button,a,input,select,textarea,[contenteditable="true"],[data-ev],[data-name],[data-line-id],.cl-o3-legend-item,.cl-orbit__card,.seg button,.btn'))continue;
    const q=S.pickCandidatesAt(pair.x,pair.y);
    if(!q||q.source!=='sprites'||!q.nodes.includes(pair.a.node)||!q.nodes.includes(pair.b.node))continue;
    candidates.push({x:pair.x,y:pair.y,projected:[pair.a.name,pair.b.name],distance:pair.d});
    if(candidates.length>=64)break;
  }
  return candidates.length?{found:true,candidates}:{found:false,reason:'no_projected_sprite_overlap',projected:rows.length,pairs:pairs.length,width:innerWidth,height:innerHeight};
})()"""

PICK_AT = r"""(()=>{
  const S=CLApp&&CLApp.scene&&CLApp.scene();if(!S||!S.pickCandidatesAt)return {count:0,reason:'picker_missing'};
  const q=S.pickCandidatesAt(%(x)s,%(y)s),rows=q&&q.nodes||[];
  const canvas=document.querySelector('#gl'),target=document.elementFromPoint(%(x)s,%(y)s),interactive=target&&target.closest&&target.closest('button,a,input,select,textarea,[contenteditable="true"],[data-ev],[data-name],[data-line-id],.cl-o3-legend-item,.cl-orbit__card,.seg button,.btn');
  return {source:q&&q.source,count:rows.length,targetValid:!!(canvas&&target&&!interactive&&(target===canvas||(target.closest&&target.closest('#labels')))),
    rows:rows.filter(n=>n&&n.kind==='char'&&n.data).map(n=>({id:String(n.data.id!=null?n.data.id:n.data.entityId),name:n.data.name}))};
})()"""

PICK_STATE = r"""(()=>{
  const panel=document.querySelector('#skyPickPanel'),rows=[...(panel?.querySelectorAll('[data-pick-ref]')||[])].filter(b=>b.getAttribute('data-pick-ref')&&!b.disabled);
  if(!panel)return {opened:false,count:rows.length};
  const back=document.querySelector('#skyBack'),style=back&&getComputedStyle(back),focused=document.activeElement;
  const box=panel.getBoundingClientRect(),cancel=panel.querySelector('[data-pick-cancel]');
  return {opened:!panel.hidden,count:rows.length,ids:rows.map(b=>b.getAttribute('data-pick-ref')),menuClosed:panel.hidden,
    calm:CLApp.scene().calm(),current:CLSky.interactionState().current,
    panelBounds:{left:box.left,top:box.top,right:box.right,bottom:box.bottom},cancelVisible:!!(cancel&&cancel.getClientRects().length),
    mode:CLSky.state().mode,focusVisible:!!(focused&&focused.getClientRects().length&&getComputedStyle(focused).visibility!=='hidden'),
    backVisible:!!(back&&!back.hidden&&style.visibility!=='hidden'),...CLSky.interactionState()};
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
        time.sleep(2.5)
        got = runner.eval(COLLECT)
        if isinstance(got, dict) and got.get("__evalError"):
            got = {}
        clicked = runner.eval(CLICK)
        if isinstance(clicked, dict) and clicked.get("__evalError"):
            clicked = {}
        time.sleep(2.0)
        after = runner.eval(AFTER)
        if isinstance(after, dict) and after.get("__evalError"):
            after = {}
        time.sleep(0.8)
        dim = runner.eval(DIM)
        if isinstance(dim, dict) and dim.get("__evalError"):
            dim = {}
        return opened, got, clicked, after, dim
    finally:
        try:
            runner.close()
        except Exception:
            pass


def probe_interaction(base, out, width=1440, height=900, reduced=False, activation="Enter"):
    runner = Wave2AuditRunner(width=width, height=height, dpr=1)
    key = "ed3dc1255ca08fbdaae30bbd"
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + str(time.time_ns())
    screenshots = []
    try:
        runner.start()
        if reduced:
            runner.ws.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"}])
        runner.navigate("%s/?sky=1&data=data/cache/%s.json" % (base, key))
        end = time.time() + 150
        while time.time() < end:
            if runner.eval("!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector('#loader.off'))") is True:
                break
            time.sleep(0.4)
        time.sleep(3)
        overlap_attempts=[]
        def capture(name):
            data = runner.ws.call("Page.captureScreenshot", format="png").get("data")
            if data:
                path = out / (run_id + "-" + name)
                path.write_bytes(base64.b64decode(data))
                screenshots.append(str(path))
        stable, rejected, overlap = None, [], {"found": False, "reason": "not_scanned"}
        for projection_attempt in range(3):
            sample=runner.eval(PICK_OVERLAP)
            overlap_attempts.append(sample)
            if isinstance(sample, dict) and sample.get("found"):
                for candidate in sample.get("candidates", []):
                    x, y = candidate["x"], candidate["y"]
                    runner.ws.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
                    time.sleep(0.2)
                    actual = runner.eval(PICK_AT % {"x": repr(x), "y": repr(y)})
                    if isinstance(actual, dict) and actual.get("targetValid") and actual.get("count", 0) > 1 and len({r.get("id") for r in actual.get("rows", [])}) > 1:
                        stable = {"x": x, "y": y, "projected": candidate.get("projected"), "actual": actual,
                                  "projectionAttempt": projection_attempt + 1}
                        overlap=sample
                        break
                    rejected.append({"attempt": projection_attempt + 1, "projected": candidate.get("projected"), "actual": actual})
            if stable:
                break
            if projection_attempt < 2:
                runner.ws.call("Input.dispatchKeyEvent", type="keyDown", key="ArrowRight", code="ArrowRight", windowsVirtualKeyCode=39)
                runner.ws.call("Input.dispatchKeyEvent", type="keyUp", key="ArrowRight", code="ArrowRight", windowsVirtualKeyCode=39)
                time.sleep(0.35)
        if stable:
            x, y = stable["x"], stable["y"]
            runner.ws.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", buttons=1, clickCount=1)
            runner.ws.call("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", buttons=0, clickCount=1)
            time.sleep(0.3)
            before_cancel = runner.eval("({choice:CLSky.interactionState().choice,selection:CLSky.interactionState().selection,calm:CLApp.scene().calm()})")
            capture("candidate-opened.png")
            runner.ws.call("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
            runner.ws.call("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape", windowsVirtualKeyCode=27)
            time.sleep(0.2)
            after_cancel = runner.eval("({choice:CLSky.interactionState().choice,selection:CLSky.interactionState().selection,calm:CLApp.scene().calm()})")
            runner.ws.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
            time.sleep(0.2)
            reopened_hit = runner.eval(PICK_AT % {"x": repr(x), "y": repr(y)})
            if not isinstance(reopened_hit, dict) or not reopened_hit.get("targetValid") or reopened_hit.get("count", 0) < 2:
                stable = None
            if stable:
                runner.ws.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", buttons=1, clickCount=1)
                runner.ws.call("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", buttons=0, clickCount=1)
                time.sleep(0.2)
                opened = runner.eval(PICK_STATE)
                capture("candidate-reopened.png")
                runner.ws.call("Input.dispatchKeyEvent", type="keyDown", key="ArrowDown", code="ArrowDown", windowsVirtualKeyCode=40)
                runner.ws.call("Input.dispatchKeyEvent", type="keyUp", key="ArrowDown", code="ArrowDown", windowsVirtualKeyCode=40)
                focused = runner.eval("({ref:document.activeElement&&document.activeElement.getAttribute('data-pick-ref'),choice:CLSky.interactionState().choice,current:CLSky.interactionState().current})")
                capture("candidate-focused.png")
            else:
                opened, focused = {"opened": False, "reason": "hit_changed_after_cancel"}, {}
                capture("candidate-interaction-failed.png")
            if stable:
                activation_key = " " if activation == "Space" else "Enter"
                activation_code = "Space" if activation == "Space" else "Enter"
                activation_vk = 32 if activation == "Space" else 13
                runner.ws.call("Input.dispatchKeyEvent", type="keyDown", key=activation_key, code=activation_code, windowsVirtualKeyCode=activation_vk)
                runner.ws.call("Input.dispatchKeyEvent", type="keyUp", key=activation_key, code=activation_code, windowsVirtualKeyCode=activation_vk)
                time.sleep(0.4)
                confirm = runner.eval(PICK_STATE)
                capture("candidate-confirmed.png")
            else:
                confirm = {}
            result = {"bookKey": key, "viewport": [width, height], "reducedMotion": reduced, "activation": activation,
                      "dynamicOverlap": overlap, "projectionAttempts": overlap_attempts,
                      "stableAfterHover": stable, "rejectedAfterHover": rejected,
                      "cancelBefore": before_cancel, "cancelAfter": after_cancel, "opened": opened,
                      "focusedBeforeActivation": focused, "confirmation": confirm}
        else:
            result = {"bookKey": key, "viewport": [width, height], "dynamicOverlap": overlap, "projectionAttempts": overlap_attempts,
                      "stableAfterHover": None, "rejectedAfterHover": rejected, "confirmation": {"opened": False}}
            capture("candidate-interaction-failed.png")
        health = runner.eval("(()=>{const h=window.__headlessHealth,S=CLApp.scene(),d=S.digest(),sh=S.shaderErrors(),f=d&&d.frameHooks;return {errors:h&&Array.isArray(h.jserr)?h.jserr:null,rejections:h&&Array.isArray(h.jsrej)?h.jsrej:null,shaderErrors:Array.isArray(sh)?sh:null,frameErrors:f&&typeof f.errors==='number'?f.errors:null}})()")
        result["health"] = health
        health_ok = bool(isinstance(health, dict) and not health.get("__evalError")
                         and health.get("errors") == [] and health.get("rejections") == []
                         and health.get("shaderErrors") == [] and health.get("frameErrors") == 0)
        result["screenshots"] = screenshots
        report_path = out / ("interaction-" + run_id + ".json")
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        confirm = result["confirmation"]
        cancel_ok = bool(result.get("cancelBefore", {}).get("choice") and not result.get("cancelAfter", {}).get("choice")
                         and result.get("cancelAfter", {}).get("selection") == result.get("cancelBefore", {}).get("selection"))
        selected=result.get("confirmation", {}).get("selection")
        expected=result.get("focusedBeforeActivation", {}).get("ref")
        ok = bool(result.get("stableAfterHover") and cancel_ok and result.get("opened", {}).get("opened")
                  and not result.get("opened", {}).get("menuClosed") and confirm.get("menuClosed")
                  and confirm.get("mode") in ("compass", "constellation") and confirm.get("focusVisible")
                  and result.get("opened", {}).get("cancelVisible")
                  and result.get("opened", {}).get("panelBounds", {}).get("left", -1) >= 0
                  and result.get("opened", {}).get("panelBounds", {}).get("top", -1) >= 0
                  and result.get("opened", {}).get("panelBounds", {}).get("right", width + 1) <= width
                  and result.get("opened", {}).get("panelBounds", {}).get("bottom", height + 1) <= height
                  and selected == expected and selected and confirm.get("current") == result.get("focusedBeforeActivation", {}).get("current")
                  and confirm.get("calm") == result.get("cancelAfter", {}).get("calm")
                  and health_ok)
        print(json.dumps({"ok": ok, "result": str(report_path), "interaction": result}, ensure_ascii=False))
        return 0 if ok else 1
    finally:
        try:
            runner.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_SHOTS", "/tmp/castline-shots")) / "p4-selection-model"))
    ap.add_argument("--interaction", action="store_true", help="动态扫描西游真射线重叠并回放候选原生 Enter/Space确认；需串行真实浏览器")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--reduced", action="store_true", help="模拟 prefers-reduced-motion: reduce")
    ap.add_argument("--activation", choices=("Enter", "Space"), default="Enter")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.interaction:
        return probe_interaction(args.base, out, args.width, args.height, args.reduced, args.activation)

    problems, checks = [], []
    def check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            problems.append(name)
        print(("PASS " if ok else "FAIL ") + name + "  · " + str(detail), flush=True)

    results = {}
    for tag in ("sanguo", "dafeng"):
        opened, got, clicked, after, dim = probe(args.base, BOOKS[tag])
        results[tag] = {"open": opened, "collect": got, "clicked": clicked, "after": after, "dim": dim}

    g1 = results["sanguo"]["collect"]
    check("① P4.5 选择模型在真实页面上可用",
          bool(g1.get("moduleLoaded")) and bool(results["sanguo"]["open"].get("modeOk")),
          "module=%s rows=%s err=%s" % (g1.get("moduleLoaded"), g1.get("rows"),
                                        results["sanguo"]["open"].get("modeErr")))
    check("② 人物行的选中键必须是**稳定 ID**（形如 ch_…）",
          (g1.get("stableKeys") or 0) >= 1 and (g1.get("nameLikeKeys") or 0) == 0,
          "stable=%s nameLike=%s sample=%s" % (g1.get("stableKeys"), g1.get("nameLikeKeys"), g1.get("keySample")))
    check("③ 名字必须另有出口（不得被丢掉）",
          (g1.get("withNameAttr") or 0) >= (g1.get("rows") or 1),
          "带 data-person-name 的 %s / %s" % (g1.get("withNameAttr"), g1.get("rows")))
    check("④ 选中键**不得**等于名字（按名字存就是本包要修的缺陷）",
          (g1.get("keyEqualsName") or 0) == 0,
          "键等于名字的 %s 个" % g1.get("keyEqualsName"))
    a1 = results["sanguo"]["after"]
    check("⑤ 点选后选中态仍按稳定 ID 记录",
          bool(a1.get("selectedIsStable")) or (a1.get("focused") or 0) >= 1,
          "selectedKey=%s stable=%s focused=%s" % (a1.get("selectedKey"), a1.get("selectedIsStable"), a1.get("focused")))
    check("⑥ 关光/低档下选中态仍可见",
          (results["sanguo"]["dim"].get("visible") or 0) >= 1,
          "dim=%s" % results["sanguo"]["dim"].get("visible"))
    g2 = results["dafeng"]["collect"]
    check("⑦ 跨书键不得混淆（同名人物在两书里必须是不同的键）",
          set(g1.get("keySample") or []) != set(g2.get("keySample") or []),
          "三国=%s 大奉=%s" % (g1.get("keySample"), g2.get("keySample")))

    report = {"plan_ref": "docs/QUALITY.md P4.5", "base": args.base, "books": results,
              "checks": checks, "problems": problems, "ok": not problems}
    p = out / "render.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems, "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
