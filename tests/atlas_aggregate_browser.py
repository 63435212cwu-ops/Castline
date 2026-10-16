#!/usr/bin/env python3
"""Dense novel: preserve every line, budget geometry, resolve any aggregated star.

两相断言，对应两类现行数据契约（2026-10-04 数据语义收口）：

1) dense 相（--dense，默认 data/sample-large.json，420 事件、无 graph.storylines）：
   CLStory.analyze 走确定性推导路径（src=derived），产出 >64 条线。最初的九项语义
   在此相原样保留：每条推导线都保留（threads>64 且全部计入预算）、可见+聚合精确守恒、
   SVG 只画 ≤64 条真实弧（其余走聚合星，不是隐藏副本）、聚合星在列表里有入口且每个
   成员都能在局部图里展开、任意一条被聚合的线都能提升回真实年轮聚焦、改选后仍守恒、
   图形预算不改图谱本体。

2) strict 相（--data，默认 data/cache/2ef47b2ecaa99a67352091d5.json，大奉打更人）：
   v41 严格来源结构以 graph.storylines 为权威。e14f706 给该缓存写入 8 条 auto-main
   占位来源线（三国/西游两本缓存同构，均为 8 段机械均分），现行产线行为因此是
   threads=8、aggregated=0 —— 这是数据事实，不是代码退化（d7313df 时这三本缓存
   storylines=[]，走推导路径产出 >64 条，本套件最初围绕那个状态设计）。此相钉住现行
   契约：来源线全部保留（threads 数 === graph.storylines 数、每条 src=model、事件被
   来源线全覆盖且只属一条线）、全部线都画成真实弧（aggregated===0 时聚合钮隐藏才是
   对的产品行为）、任意可见线可选中聚焦、改选后预算守恒、图谱本体零改动。

   缓存归用户数据域；离线环境无法重跑 LLM 分析改写数据，故密集语义由 dense 相在
   无来源线的数据上继续端到端覆盖，不在引擎里给占位来源线编造细分（那会违反
   严格来源结构的线归属/换手不变量）。
"""
import argparse
import json
from atlas_score_keys_browser import Session
import headless


DENSE_JS = """(function(){
  var out=[],source=JSON.stringify(CLApp.graph()),tree=CLApp.story(),B=CLPlot.annulusBudget();
  function check(name,ok){out.push({name:name,ok:!!ok});}
  check('full-derived-lines-are-retained',tree.src==='derived'&&tree.threads.length>64);
  check('visible-plus-aggregate-exactly-conserves-lines',B.raw===tree.threads.length&&B.visible+B.aggregated===B.raw&&B.visible<=64&&B.aggregated>0);
  check('bounded-real-svg-not-hidden-duplicates',CLAnnulusSVG.stats().arcs<=64&&CLAnnulusSVG.stats().aggregatedLines===B.aggregated);
  check('aggregate-has-graph-entry',!document.getElementById('atlasAggregate').hidden&&document.getElementById('atlasAggregateCount').textContent==='+'+B.aggregated);
  CLAtlasPreview.expandLines();
  check('every-aggregate-member-accessible-in-graph',CLAtlasLocalGraph.stats().count===B.aggregated&&CLAtlasLocalGraph.stats().visible<=12);
  var target=B.ids[B.ids.length-1];CLAtlasPreview.chooseLine(target);CLApp.scene().step(2);
  check('arbitrary-hidden-line-promoted-into-real-annulus',CLAnnulusSVG.ctx().A.rings.some(function(r){return r.id===target;})&&CLAnnulusSVG.stats().focus===target);
  B=CLPlot.annulusBudget();check('reselection-still-conserves-all-lines',B.visible+B.aggregated===tree.threads.length);
  check('graph-unmodified',JSON.stringify(CLApp.graph())===source);
  var b2=Object.assign({},B);delete b2.ids;
  return {checks:out,raw:tree.threads.length,src:tree.src,budget:b2,dom:CLAnnulusSVG.stats().domNodes};
})()"""

STRICT_JS = """(function(){
  var out=[],source=JSON.stringify(CLApp.graph()),tree=CLApp.story(),B=CLPlot.annulusBudget();
  function check(name,ok){out.push({name:name,ok:!!ok});}
  var sl=(CLApp.graph().storylines||[]);
  check('strict-source-lines-all-retained',tree.src==='model'&&tree.strictTopology===true&&sl.length>0&&tree.threads.length===sl.length&&tree.threads.every(function(t){return t.src==='model';}));
  var sum=0,seen={},cover=0;
  tree.threads.forEach(function(t){sum+=t.events.length;t.events.forEach(function(i){if(!seen[i]){seen[i]=1;cover++;}});});
  check('strict-events-covered-once-by-source-lines',cover===tree.events.length&&sum===cover);
  check('strict-all-lines-drawn-as-real-arcs',B.raw===tree.threads.length&&B.visible===B.raw&&B.aggregated===0&&CLAnnulusSVG.stats().arcs===B.visible&&CLAnnulusSVG.stats().aggregatedLines===0);
  check('strict-no-aggregate-entry-when-nothing-hidden',document.getElementById('atlasAggregate').hidden===true);
  var rings=CLAnnulusSVG.ctx().A.rings,target=rings.length?rings[rings.length-1].id:null;
  CLAtlasPreview.chooseLine(target);CLApp.scene().step(2);
  check('strict-arbitrary-line-selectable-and-focused',!!target&&CLAnnulusSVG.ctx().A.rings.some(function(r){return r.id===target;})&&CLAnnulusSVG.stats().focus===target);
  B=CLPlot.annulusBudget();
  check('strict-reselection-still-conserves-all-lines',B.raw===tree.threads.length&&B.visible+B.aggregated===B.raw);
  check('graph-unmodified',JSON.stringify(CLApp.graph())===source);
  var b2=Object.assign({},B);delete b2.ids;
  return {checks:out,raw:tree.threads.length,src:tree.src,sourceLines:sl.length,budget:b2,dom:CLAnnulusSVG.stats().domNodes};
})()"""


def run_phase(s, base, data, js):
    s.navigate(base.rstrip('/') + '/?data=' + data + '&plot=1&probe=1&pump=1&warm=30')
    if not s.wait_ready(100):
        raise RuntimeError('not ready: ' + data)
    result = s.eval(js)
    if not isinstance(result, dict) or 'checks' not in result:
        raise RuntimeError('phase eval failed: ' + json.dumps(result, ensure_ascii=False)[:400])
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:8000')
    p.add_argument('--data', default='data/cache/2ef47b2ecaa99a67352091d5.json',
                   help='strict 相：带 graph.storylines 来源线的书（默认大奉缓存）')
    p.add_argument('--dense', default='data/sample-large.json',
                   help='dense 相：无 storylines、走推导路径产出 >64 条线的密书')
    args = p.parse_args()
    s = Session('1440x900'); checks = []
    out = {}
    try:
        s.start(); s.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        out['dense'] = run_phase(s, args.base, args.dense, DENSE_JS)
        out['strict'] = run_phase(s, args.base, args.data, STRICT_JS)
        checks = out['dense']['checks'] + out['strict']['checks']
        health = s.ws.call('Runtime.evaluate', expression=headless.POST_HEALTH_JS, returnByValue=True, awaitPromise=True)['result']['value']
        checks.append({'name': 'health', 'ok': health['jserr'] == 'none' and health['jsrej'] == 'none' and health['shaderErrors'] == []})
        print(json.dumps(out, ensure_ascii=False, indent=2))
    finally:
        s.close()
    return 0 if checks and all(x['ok'] for x in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
