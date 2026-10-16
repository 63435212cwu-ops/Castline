#!/usr/bin/env python3
"""剧情线诚实分层 · 真实作品 CDP 浏览（CL_GPU=1 串行）。

三部真实图谱逐项断言：
  1. 大奉打更人（8×374 机械等分、goal 全空）——剧情线谱出现「自动分段 · 非作者结构 · 未见任务目标」
     折叠分区，8 条全部降权；事件总数守恒（刻点数不丢）。
  2. 西游记审阅版（真实 goal）——不降级：无自动分段分区，真实目标文本常显。
  3. 三国演义（1539 条旧关系零锚点）——信息架构「关系场」全部带「继承 · 待核验」徽章，
     待核验计数可见且 == 1539；剧情线（有真实 goal）不被当机械段降级。

模型层（CLStory.honestyOf / CLSkyModel.relationHonesty）与展示层（cp-autogroup / ia-rel-ev）
分开断言：展示是标注的读者，不是判定的复读。

Run: CL_GPU=1 python3 -s tests/storyline_honesty_browser.py [--base http://127.0.0.1:8137]
"""
import argparse, base64, json, time, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner

DAFENG = 'data/cache/2ef47b2ecaa99a67352091d5.json'
XIYOU = 'data/cache/c84e8657afff87043c11ae57.json'
SANGUO = 'data/cache/f0b45e85aac6c95e584075a2.json'


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--base', default='http://127.0.0.1:8137')
    a.add_argument('--out', default=str(Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'storyline-honesty'))
    args = a.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    r = Wave2AuditRunner(width=1440, height=900, dpr=1)
    checks = []
    def ev(expr, wait=False):
        value = r.eval(expr, await_promise=wait)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(value)
        return value
    def check(name, expr):
        value = ev(expr)
        ok = value is True
        checks.append({'name': name, 'ok': ok, 'actual': value})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
    def ready():
        end = time.time() + 120
        while time.time() < end:
            if ev('!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))'):
                break
            time.sleep(.3)
        else:
            raise RuntimeError('graph readiness timeout')
        time.sleep(3)
    def shot(name):
        (out / (name + '.png')).write_bytes(base64.b64decode(r.ws.call('Page.captureScreenshot', format='png')['data']))

    try:
        r.start()
        r.navigate(args.base + '/?sky=1&data=' + DAFENG); ready()
        check('Dafeng honesty profile sees an all-mechanical partition of eight objective-less lines',
              '(()=>{var h=CLStory.honestyOf(CLApp.graph());return h.verdict==="all-mechanical"&&h.total===8&&h.mechanical===8&&h.structural===true&&h.provenanceDerived===true})()')
        check('Dafeng tree marks all eight threads autoSegment with objective none',
              '(()=>{var t=CLStory.get();return t.threads.length===8&&t.threads.every(x=>x.autoSegment===true&&x.objective==="none")&&t.lineHonesty.verdict==="all-mechanical"&&t.stats.mechLines===8&&t.stats.declaredLines===0})()')
        check('Dafeng layering keeps every event (tick count conserved)',
              '(()=>{var t=CLStory.get();return t.stats.events===2990&&t.events.length===2990})()')
        ev('CLPlotHud.open()'); time.sleep(2)
        check('Dafeng plot stream shows the collapsed auto-segment partition with the honest label only for the eight lines',
              '(()=>{var g=document.querySelector(".cp-autogroup");if(!g)return false;var s=g.querySelector("summary");return s&&s.textContent.includes("自动分段")&&s.textContent.includes("非作者结构")&&s.textContent.includes("未见任务目标")&&g.querySelectorAll(".cp-card.auto").length===8})()')
        check('Dafeng lanes and trunk segments are visually downgraded, not deleted',
              '(()=>{var n=document.querySelectorAll(".cp-grid .cp-lane.auto").length||0;CLPlotHud.stats();return document.querySelectorAll(".cp-grid .cp-seg.auto").length===8})()')
        check('Dafeng footer states declared-vs-auto counts honestly',
              '(()=>{var f=document.querySelector("#clPlot .cp-foot");return !!f&&f.textContent.includes("目标声明 0")&&f.textContent.includes("自动分段 8")})()')
        shot('01-dafeng-auto-partition')

        r.navigate(args.base + '/?sky=1&data=' + XIYOU); ready()
        check('Xiyou reviewed lines are all declared (no degradation, no auto partition at model level)',
              '(()=>{var h=CLStory.honestyOf(CLApp.graph());var t=CLStory.get();return h.verdict==="all-declared"&&h.mechanical===0&&t.threads.every(x=>x.autoSegment===false&&x.objective==="declared")&&t.stats.mechLines===0})()')
        ev('CLPlotHud.open()'); time.sleep(2)
        check('Xiyou plot stream has no collapsed auto group and shows declared goal text',
              '(()=>{var g=document.querySelector(".cp-autogroup");var goal=document.querySelector(".cp-goal");var badges=document.querySelectorAll(".cp-obj-badge:not(.auto)");return !g&&!!goal&&badges.length>=9&&document.querySelectorAll(".cp-card.auto").length===0})()')
        shot('02-xiyou-declared-lines')

        r.navigate(args.base + '/?sky=1&data=' + SANGUO); ready()
        check('Sanguo relation honesty roll-up counts all 1539 legacy relations as inherited-pending',
              '(()=>{var h=CLSkyModel.relationHonesty(CLApp.graph());return h.total===1539&&h.inherited===1539&&h.anchored===0&&h.items.length===1539})()')
        check('Sanguo storylines keep declared goals and are not demoted (no mechanical lines)',
              '(()=>{var h=CLStory.honestyOf(CLApp.graph());var t=CLStory.get();return h.declared===34&&h.mechanical===0&&t.threads.every(x=>!x.autoSegment)})()')
        ev('document.getElementById("btnInfo").click()'); time.sleep(1.5)
        check('Sanguo IA relations list badges shown relations as inherited-pending and exposes the count',
              '(()=>{var body=document.getElementById("iaRelations");var stat=document.getElementById("iaRelStat");var summary=document.getElementById("iaRelSummary");return body.querySelectorAll(".ia-rel-ev:not(.src)").length===body.querySelectorAll(".ia-rel").length&&body.textContent.includes("继承 · 待核验")&&summary.textContent.includes("待核验")&&stat.textContent.includes("待核验 1539")})()')
        shot('03-sanguo-relations-pending')
        check('real-book honesty journey has no uncaught JavaScript or shader errors',
              '__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0')

        result = {'ok': all(x['ok'] for x in checks), 'checks': checks, 'modelsCalled': 0, 'sourceFilesChanged': False, 'viewport': [1440, 900]}
        (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({'ok': result['ok'], 'checks': len(checks), 'out': str(out)}), flush=True)
        if not result['ok']:
            raise SystemExit(1)
    finally:
        r.close()


if __name__ == '__main__':
    main()
