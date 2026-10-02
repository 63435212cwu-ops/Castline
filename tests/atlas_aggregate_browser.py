#!/usr/bin/env python3
"""Dense novel: preserve every line, budget geometry, resolve any aggregated star."""
import argparse
import json
import time
from atlas_score_keys_browser import Session
import headless


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:8000')
    p.add_argument('--data', default='data/cache/2ef47b2ecaa99a67352091d5.json')
    args = p.parse_args()
    s = Session('1440x900'); checks = []
    try:
        s.start(); s.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        s.navigate(args.base.rstrip('/') + '/?data=' + args.data + '&plot=1&probe=1&pump=1&warm=30')
        if not s.wait_ready(100):
            raise RuntimeError('not ready')
        result = s.eval("""(function(){
          var out=[],source=JSON.stringify(CLApp.graph()),tree=CLApp.story(),B=CLPlot.annulusBudget();
          function check(name,ok){out.push({name:name,ok:!!ok});}
          check('full-derived-lines-are-retained',tree.threads.length>64);
          check('visible-plus-aggregate-exactly-conserves-lines',B.raw===tree.threads.length&&B.visible+B.aggregated===B.raw&&B.visible<=64);
          check('bounded-real-svg-not-hidden-duplicates',CLAnnulusSVG.stats().arcs<=64&&CLAnnulusSVG.stats().aggregatedLines===B.aggregated);
          check('aggregate-has-graph-entry',!document.getElementById('atlasAggregate').hidden&&document.getElementById('atlasAggregateCount').textContent==='+'+B.aggregated);
          CLAtlasPreview.expandLines();
          check('every-aggregate-member-accessible-in-graph',CLAtlasLocalGraph.stats().count===B.aggregated&&CLAtlasLocalGraph.stats().visible<=12);
          var target=B.ids[B.ids.length-1];CLAtlasPreview.chooseLine(target);CLApp.scene().step(2);
          check('arbitrary-hidden-line-promoted-into-real-annulus',CLAnnulusSVG.ctx().A.rings.some(function(r){return r.id===target;})&&CLAnnulusSVG.stats().focus===target);
          B=CLPlot.annulusBudget();check('reselection-still-conserves-all-lines',B.visible+B.aggregated===tree.threads.length);
          check('graph-unmodified',JSON.stringify(CLApp.graph())===source);
          return {checks:out,raw:tree.threads.length,budget:B,dom:CLAnnulusSVG.stats().domNodes};
        })()""")
        checks = result['checks']
        health = s.ws.call('Runtime.evaluate', expression=headless.POST_HEALTH_JS, returnByValue=True, awaitPromise=True)['result']['value']
        checks.append({'name': 'health', 'ok': health['jserr'] == 'none' and health['jsrej'] == 'none' and health['shaderErrors'] == []})
        result['budget'].pop('ids', None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        s.close()
    return 0 if checks and all(x['ok'] for x in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
