#!/usr/bin/env python3
"""层序守卫探针（z-order guardian）—— 大关弹层链上下关系逐对裁决。

背景：2026-10-04 R4 将全库 40 条野生 z-index 收编 A5 音阶。迁移期在交付会话做过
elementFromPoint 逐对同胜者零翻转（当时未沉淀脚本）。本套件把该裁决固化成
持久可复跑探针：对每个 (above, below) 元素对，在真实页面状态中取 above 命中点，
断言 elementFromPoint 命中 above 自身链内，且 computed z-index 关系不逆（弹层
> tooltip > 读数 > HUD > 画布）。above 缺失/不可见（隐藏、互斥景）按 skip 计，
不静默 PASS。

场景：S1 底态 → S2 开作品库 → S3 确认框盖库；T 为静态音阶对照（toast/tooltip 注入探针件）。
退出码：有 FAIL → 1；全 PASS/skip → 0。
用法：CL_GPU=1 python3 -s tests/design_stack_probe.py [--base http://127.0.0.1:8123] [--out DIR]
"""
import argparse, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
from atlas_score_keys_browser import Session
import headless

PAIRS = [
    {'scene': 'S1', 'above': '#skyTools', 'below': '#gl', 'name': 'S1 顶栏工具钮在画布之上'},
    {'scene': 'S1', 'above': '#skyLegend', 'below': '#gl', 'name': 'S1 底栏图例在画布之上'},
    {'scene': 'S2', 'above': '#library', 'below': '#skyTools', 'name': 'S2 作品库模态压过顶栏行'},
    {'scene': 'S3', 'above': '#confirm', 'below': '#library', 'name': 'S3 确认框盖作品库'},
    {'scene': 'T', 'above': '#toastProbe', 'below': '#library', 'name': 'T ritual/toast 音阶 ≥ modal'},
    {'scene': 'T', 'above': '.cl-tooltip-probe', 'below': '#skyTools', 'name': 'T tooltip 音阶 ≥ HUD'},
]

SETUPS = {
    'S1': "true",
    'S2': "CLApp.internal().openLib(); await new Promise(r=>setTimeout(r,900)); true",
    'S3': "CLApp.internal().openLib(); await new Promise(r=>setTimeout(r,500));"
          "if(CLApp.internal().confirmBox){CLApp.internal().confirmBox({title:'层序守卫',body:'probe'});}"
          "else if(window.CLApp && CLApp.confirmBox){CLApp.confirmBox({title:'层序守卫',body:'probe'});}"
          "await new Promise(r=>setTimeout(r,400)); true",
    'T': "(function(){"
         "function mk(id, cls, css){var old=document.getElementById(id);if(old)old.remove();var d=document.createElement('div');"
         "d.id=id;d.className=cls;d.textContent='probe';d.style.cssText=css;document.body.appendChild(d);}"
         "mk('toastProbe','cl-toast','position:fixed;right:24px;bottom:96px;width:180px;height:48px;z-index:var(--z-ritual)');"
         "mk('tipProbe','cl-tooltip-probe','position:fixed;left:24px;top:120px;width:180px;height:44px;z-index:var(--z-tooltip)');"
         "return true;})()",
}

JUDGE = r"""(function(pl){
  function q(sel){ var es=document.querySelectorAll(sel); return es.length?es[0]:null; }
  function vis(e){ if(!e) return false; var cs=getComputedStyle(e); var r=e.getBoundingClientRect();
    return cs.display!=='none'&&cs.visibility!=='hidden'&&r.width>1&&r.height>1; }
  function zi(e){ if(!e) return null; var v=getComputedStyle(e).zIndex; return v==='auto'?0:+v; }
  var out=[];
  pl.forEach(function(p){
    var a=q(p.above), b=q(p.below);
    if(!a){ out.push({name:p.name, ok:null, why:'above missing: '+p.above}); return; }
    if(!vis(a)){ out.push({name:p.name, ok:null, why:'above not visible: '+p.above}); return; }
    var r=a.getBoundingClientRect();
    var x=r.x+Math.min(r.width/2, 48), y=r.y+Math.min(r.height/2, 14);
    var hit=document.elementFromPoint(x,y);
    var own = hit && (hit===a || a.contains(hit) || (hit.closest && hit.closest(p.above)));
    var zok = (zi(a)===null || zi(b)===null) ? true : zi(a) >= zi(b);
    out.push({name:p.name, ok: !!(own && zok), point:[Math.round(x),Math.round(y)],
              hit:String(hit&&(hit.id||hit.className||hit.tagName)).slice(0,64), zA:zi(a), zB:zi(b),
              requireBelow: !!p.requireBelow, belowSeen: !!b});
  });
  return out;
})"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:8123')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'design-stack'))
    args = ap.parse_args()

    s = Session('1440x900')
    checks = []
    try:
        s.start()
        s.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        s.navigate(args.base.rstrip('/') + '/?demo=1&sky=1&probe=1&pump=1&warm=60')
        t0 = time.time()
        while time.time() - t0 < 60:
            if s.eval("!!(window.CLApp && CLApp.graph && CLApp.graph())") is True:
                break
            time.sleep(0.3)
        time.sleep(2.0)

        for sc in ('S1', 'S2', 'S3', 'T'):
            if sc == 'T':
                for _ in range(3):
                    s.real_key('Escape', 'Escape', 27)
                    time.sleep(0.25)
                s.eval(SETUPS[sc])
            elif sc != 'S1':
                s.eval("(async()=>{" + SETUPS[sc] + "})()")
            time.sleep(1.0)
            pl = [p for p in PAIRS if p['scene'] == sc]
            if not pl:
                continue
            res = s.eval(JUDGE + "(" + json.dumps(pl, ensure_ascii=False) + ")")
            if isinstance(res, dict) and res.get('__evalError'):
                raise RuntimeError(res)
            for item in res:
                item['scene'] = sc
            checks.extend(res)

        os.makedirs(args.out, exist_ok=True)
        payload = {
            'base': args.base,
            'passed': sum(1 for c in checks if c['ok'] is True),
            'skipped': sum(1 for c in checks if c['ok'] is None),
            'failed': sum(1 for c in checks if c['ok'] is False),
            'checks': checks,
        }
        with open(os.path.join(args.out, 'result.json'), 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        for c in checks:
            tag = 'PASS' if c['ok'] is True else 'SKIP' if c['ok'] is None else 'FAIL'
            print('%s %s %s' % (tag, c['name'], c), flush=True)
        print(json.dumps({'passed': payload['passed'], 'skipped': payload['skipped'],
                          'failed': payload['failed']}), flush=True)
        return 1 if payload['failed'] else 0
    finally:
        s.close()


if __name__ == '__main__':
    raise SystemExit(main())
