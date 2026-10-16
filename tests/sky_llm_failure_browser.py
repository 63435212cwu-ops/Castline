#!/usr/bin/env python3
"""LLM 数据面失败模式审计（接第十六轮遗留的未审面）：四类失败的真实注入与用户可见反馈验证。

消费三面（全是真实 UI 入口，不走内部函数直达）：
  ① API 面板    —— GET /api/llm-config（点 #btnApi 打开面板即读档）
  ② 蒸馏面板    —— POST /api/distill（点 #btnDistill 打开面板即探针；「开始蒸馏」是 SSE 入口）
  ③ 结构补析面板 —— POST /api/enrich/plan（工具菜单 → 结构补析 → 「查看方案」）

四类失败（CDP Fetch 域，全是真实网络层行为，不是伪造 JS 状态）：
  A. 403 接入被拒 —— fulfillRequest(403, 'Forbidden')
  B. 500 服务故障 —— fulfillRequest(500, 'Internal Server Error')
  C. 200 但非 JSON —— fulfillRequest(200, '<html>…')，损坏响应必须明说「返回内容不是预期的数据格式」
  D. 挂起 15s+   —— 扣住 requestPaused 不放行，观测 15s 慢门两侧的 UI 诚实反馈，再放行验证恢复

两种用法：
  --mode observe  只记录观测矩阵（修复前基线 / 审计取证），不因缺陷失败；
  --mode gate     把「诚实错误文案 + 可重试/不可重试区分 + 真实恢复路径」当硬门。

骨架与 GuardWS 复用 tests/sky_failure_modes_browser.py；同样不进 scripts/accept.sh 离线门。
用法：CL_GPU=1 python3 -s tests/sky_llm_failure_browser.py --mode gate [--base http://127.0.0.1:8765]
"""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
sys.path.insert(0, str(ROOT / 'tests'))
import sky_chaos as chaos
from sky_failure_modes_browser import GuardWS, fulfill, shot

BOOK_KEY = 'f0b45e85aac6c95e584075a2'
BOOK_URL = 'data/cache/%s.json' % BOOK_KEY

PAT_LLM = '*://*/api/llm-config*'
PAT_DISTILL = '*://*/api/distill*'
PAT_PLAN = '*://*/api/enrich/plan*'

SLOW_WAIT = 16.5

HEALTH_JS = "(()=>{const h=window.__headlessHealth||{};return {jserr:(h.jserr||[]).length,jsrej:(h.jsrej||[]).length};})()"

OBS_API_JS = r"""(()=>{
  const $=id=>document.getElementById(id);
  const panel=$('apiPanel'), msg=$('apiMsg'), list=$('apiList');
  return {
    panelOn: !!(panel && panel.classList.contains('on')),
    msg: msg ? msg.textContent : null,
    listText: list ? list.textContent.replace(/\s+/g,' ').slice(0,200) : null,
    emptyClaim: !!(list && /还没有档案/.test(list.textContent)),
    profiles: list ? list.querySelectorAll('.apf').length : 0,
    count: $('apiCount') ? $('apiCount').textContent : null,
    health: %s
  };
})()""" % HEALTH_JS

OBS_DISTILL_JS = r"""(()=>{
  const $=id=>document.getElementById(id);
  const panel=$('dsPanel');
  if (!panel) return {panel:false};
  const warn=$('dsWarn');
  return {
    panel: panel.classList.contains('on'),
    plan: $('dsPlan') ? $('dsPlan').textContent.replace(/\s+/g,' ').slice(0,240) : null,
    note: $('dsNote') ? $('dsNote').textContent : null,
    warn: (!warn || warn.classList.contains('is-hidden')) ? null : warn.textContent.replace(/\s+/g,' ').slice(0,200),
    startDisabled: $('dsStart') ? $('dsStart').disabled : null,
    startText: $('dsStart') ? $('dsStart').textContent : null,
    err: $('dsErr') ? $('dsErr').textContent.replace(/\s+/g,' ').slice(0,240) : null,
    health: %s
  };
})()""" % HEALTH_JS

OBS_ENRICH_JS = r"""(()=>{
  const root=document.getElementById('skyEnrichPanel');
  if (!root) return {panel:false};
  const q=s=>root.querySelector(s);
  const e=q('.ske-error'), st=q('.ske-status'), lb=q('[data-action=local]'), sb=q('[data-action=start]');
  return {
    panel: !root.hidden,
    status: st ? st.textContent : null,
    error: e ? e.textContent : null,
    errorTitle: e ? e.title : null,
    planInfo: q('.ske-plan') ? q('.ske-plan').textContent.replace(/\s+/g,' ').slice(0,200) : null,
    localBtnVisible: lb ? !lb.hidden : null,
    startDisabled: sb ? sb.disabled : null,
    state: (window.CLSkyEnrich && CLSkyEnrich.state) ? CLSkyEnrich.state() : null,
    health: %s
  };
})()""" % HEALTH_JS


def wait_ready(g, timeout=60):
    return g.until("!!(window.CLApp&&CLApp.graph()&&CLApp.graph().characters&&"
                   "CLApp.graph().characters.length>0&&window.CLSky&&CLSky.model())", timeout)


def valid_llm_config(base):
    return urllib.request.urlopen(base + '/api/llm-config', timeout=5).read()


def run_case(g, b, name, pattern, match, trigger, observe_js, setup, recover, shots):
    """通用骨架：拦截目标端点 → 真实 UI 触发 → 注入失败 → 观测 →（可选）真实恢复。"""
    out = {'case': name, 'observations': {}}
    g.call('Fetch.enable', patterns=[{'urlPattern': pattern}])
    g.ev(trigger)
    paused = g.pump_paused(match, timeout=40)
    out['intercepted'] = bool(paused)
    if not paused:
        g.call('Fetch.disable')
        out['error'] = 'requestPaused never arrived'
        return out
    if setup.get('hold_seconds'):
        time.sleep(setup['hold_seconds'])
        out['observations']['duringHold'] = g.ev(observe_js)
        if setup.get('release_body') is not None:
            fulfill(g, paused, 200, setup['release_body'])
        else:
            try:
                g.call('Fetch.failRequest', requestId=paused['requestId'], errorReason='Aborted')
            except Exception:
                pass
    elif setup.get('fail'):
        g.call('Fetch.failRequest', requestId=paused['requestId'], errorReason=setup['fail'])
    else:
        fulfill(g, paused, setup.get('status', 200), setup['body'],
                setup.get('content_type', 'text/plain'))
    g.call('Fetch.disable')
    time.sleep(setup.get('settle_seconds', 1.0))
    out['observations']['afterFailure'] = g.ev(observe_js)
    shot(b, name + '-failure', shots)
    if recover:
        g.ev(recover['trigger'])
        ready = g.until(recover['ready'], recover.get('timeout', 25))
        out['recovery'] = {'ready': ready, 'observations': g.ev(observe_js)}
        shot(b, name + ('-recovered' if ready else '-no-recovery'), shots)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--mode', choices=['observe', 'gate'], default='observe')
    ap.add_argument('--out', default=str(artifact_path() / 'llm_failure_modes'))
    args = ap.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    gate = args.mode == 'gate'
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    shots = out_dir / ('shots-' + args.mode)
    shots.mkdir(exist_ok=True)

    report = {'mode': args.mode, 'base': args.base, 'book': BOOK_URL,
              'startedAt': datetime.now(timezone.utc).isoformat(), 'cases': {}, 'checks': [],
              'boundary': ('CDP Fetch 域真实注入：403/500/200 非 JSON/扣留 15s+（字节级与传输级真实）；'
                           '触发全是真实 UI 入口（#btnApi / #btnDistill / 补析「查看方案」/「开始蒸馏」按钮）；'
                           '恢复由常驻 serve.py 真 200 供数据。serve.py LLM 网关行为本身不在审改范围。')}
    checks = report['checks']

    def check(name, ok, detail=None):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:600]), flush=True)
        return ok

    def put(case_name, result):
        report['cases'][case_name] = result
        return result

    b = chaos.Browser(1440, 900)
    try:
        b.start()
        g = GuardWS(b.ws)
        g.call('Page.navigate', url=args.base + '/?sky=1&data=' + BOOK_URL)
        if not wait_ready(g):
            raise RuntimeError('book page never became ready')
        baseline_profiles = g.ev("fetch('/api/llm-config').then(r=>r.json()).then(d=>(d.profiles||[]).length)")
        llm_body = valid_llm_config(args.base)
        g.ev("document.getElementById('btnApi').click()")
        g.until("document.querySelectorAll('#apiList .apf').length>0", 15)
        g.ev("document.getElementById('apiClose').click()")

        API_RECOVER = {'trigger': "document.getElementById('apiClose').click();document.getElementById('btnApi').click()",
                       'ready': "document.querySelectorAll('#apiList .apf').length>0"}
        API_TRIGGER = "document.getElementById('btnApi').click()"
        DISTILL_RECOVER = {'trigger': "window.__cldistill.close();window.__cldistill.open()",
                           'ready': "/材料/.test(document.getElementById('dsPlan').textContent)", 'timeout': 60}
        def distill_open():
            return "document.getElementById('btnDistill').click()"

        print('\n[1A] GET /api/llm-config 403', flush=True)
        a = put('llmconfig-403', run_case(g, b, 'L1a-403', PAT_LLM, '/api/llm-config', API_TRIGGER, OBS_API_JS,
                                          {'status': 403, 'body': b'Forbidden'}, API_RECOVER, shots))
        o = a['observations'].get('afterFailure') or {}
        if gate:
            check('1a: 403 落诚实文案而非误报「本地服务未启动」',
                  bool(o.get('msg')) and '未启动' not in o['msg'] and ('拒绝' in o['msg'] or '403' in o['msg']), o)
            check('1a: 403 不得摆成「还没有档案」的误导空态', not o.get('emptyClaim'), o)
            check('1a: 解除后重新打开面板真实恢复出档案列表',
                  bool(a.get('recovery') and a['recovery']['ready']), a.get('recovery'))

        print('\n[1B] GET /api/llm-config 500', flush=True)
        bcase = put('llmconfig-500', run_case(g, b, 'L1b-500', PAT_LLM, '/api/llm-config', API_TRIGGER, OBS_API_JS,
                                              {'status': 500, 'body': b'Internal Server Error'}, API_RECOVER, shots))
        o = bcase['observations'].get('afterFailure') or {}
        if gate:
            check('1b: 500 文案指认服务暂时故障且说明可重试',
                  bool(o.get('msg')) and '500' in o['msg'] and '重试' in o['msg'], o)
            check('1b: 500 不得摆成误导空态', not o.get('emptyClaim'), o)
            check('1b: 解除后重新打开面板真实恢复', bool(bcase.get('recovery') and bcase['recovery']['ready']), bcase.get('recovery'))

        print('\n[1C] GET /api/llm-config 200 但非 JSON', flush=True)
        c = put('llmconfig-corrupt', run_case(g, b, 'L1c-corrupt', PAT_LLM, '/api/llm-config', API_TRIGGER, OBS_API_JS,
                                              {'status': 200, 'body': b'<html><body>Service Unavailable</body></html>',
                                               'content_type': 'text/html'}, API_RECOVER, shots))
        o = c['observations'].get('afterFailure') or {}
        if gate:
            check('1c: 损坏响应明说「返回内容不是预期的数据格式」',
                  bool(o.get('msg')) and '返回内容不是预期的数据格式' in o['msg'], o)
            check('1c: 损坏响应不得摆成「还没有档案」', not o.get('emptyClaim'), o)
            check('1c: 解除后重新打开面板真实恢复', bool(c.get('recovery') and c['recovery']['ready']), c.get('recovery'))

        print('\n[1D] GET /api/llm-config 挂起 15s+', flush=True)
        d = put('llmconfig-slow', run_case(g, b, 'L1d-slow', PAT_LLM, '/api/llm-config', API_TRIGGER, OBS_API_JS,
                                           {'hold_seconds': SLOW_WAIT, 'release_body': llm_body, 'settle_seconds': 1.5},
                                           None, shots))
        oh = d['observations'].get('duringHold') or {}
        oa = d['observations'].get('afterFailure') or {}
        if gate:
            check('1d: 挂起超过 15s 必须给出慢响应反馈（点名等待时长），不得静默',
                  bool(oh.get('msg')) and '15' in oh['msg'] and ('返回' in oh['msg'] or '等待' in oh['msg']), oh)
            check('1d: 挂起期间不得摆成「还没有档案」', not oh.get('emptyClaim'), oh)
            check('1d: 放行真实载荷后档案列表真实渲染',
                  bool(oa.get('profiles') == baseline_profiles), {'obs': oa, 'baseline': baseline_profiles})
        g.ev("document.getElementById('apiClose').click()")

        def distill_case(tag, status=None, body=None, slow=False):
            setup = {'hold_seconds': SLOW_WAIT, 'settle_seconds': 1.5} if slow else {'status': status, 'body': body}
            return run_case(g, b, tag, PAT_DISTILL, '/api/distill', distill_open(), OBS_DISTILL_JS, setup,
                            DISTILL_RECOVER, shots)

        print('\n[2A] POST /api/distill 探针 403', flush=True)
        a2 = put('distill-probe-403', distill_case('L2a-403', 403, b'Forbidden'))
        o = a2['observations'].get('afterFailure') or {}
        if gate:
            check('2a: 探针 403 落诚实文案（拒绝/403），不得怪材料',
                  bool(o.get('plan')) and ('拒绝' in o['plan'] or '403' in o['plan'])
                  and (not o.get('note') or '更换材料' not in o['note']), o)
            check('2a: 解除后重开面板探针真实跑通',
                  bool(a2.get('recovery') and a2['recovery']['ready']), a2.get('recovery'))

        print('\n[2B] POST /api/distill 探针 500', flush=True)
        b2 = put('distill-probe-500', distill_case('L2b-500', 500, b'Internal Server Error'))
        o = b2['observations'].get('afterFailure') or {}
        if gate:
            check('2b: 探针 500 文案指认服务故障且说明可重试',
                  bool(o.get('plan')) and '500' in o['plan'] and '重试' in o['plan'], o)
            check('2b: 解除后重开面板探针真实跑通',
                  bool(b2.get('recovery') and b2['recovery']['ready']), b2.get('recovery'))

        print('\n[2C] POST /api/distill 探针 200 但非 JSON', flush=True)
        c2 = put('distill-probe-corrupt', distill_case('L2c-corrupt', 200, b'<html>Service Unavailable</html>'))
        o = c2['observations'].get('afterFailure') or {}
        if gate:
            check('2c: 探针损坏响应明说「返回内容不是预期的数据格式」，不得泄原始解析异常',
                  bool(o.get('plan')) and '返回内容不是预期的数据格式' in o['plan']
                  and 'token' not in o['plan'], o)
            check('2c: 解除后重开面板探针真实跑通',
                  bool(c2.get('recovery') and c2['recovery']['ready']), c2.get('recovery'))

        print('\n[2D] POST /api/distill 探针挂起 15s+', flush=True)
        d2 = put('distill-probe-slow', distill_case('L2d-slow', slow=True))
        oh = d2['observations'].get('duringHold') or {}
        if gate:
            check('2d: 探针超过 15s 无返回必须给出慢响应反馈，不得永远停在「读取材料」',
                  bool(oh.get('plan')) and '15' in oh['plan'] and '读取材料' not in oh['plan'], oh)
            check('2d: 慢响应反馈不得怪材料（不是「蒸馏需要原文」）',
                  not oh.get('note') or '蒸馏需要原文' not in oh['note'], oh)
            check('2d: 解除后重开面板探针真实跑通',
                  bool(d2.get('recovery') and d2['recovery']['ready']), d2.get('recovery'))

        print('\n[2E] POST /api/distill 开始蒸馏（SSE 入口）403', flush=True)
        a3 = put('distill-run-403', run_case(
            g, b, 'L2e-run-403', PAT_DISTILL, '/api/distill',
            "window.__cldistill.start(true)",
            OBS_DISTILL_JS, {'status': 403, 'body': b'Forbidden'},
            {'trigger': "document.getElementById('dsBack').click()",
             'ready': "/材料/.test(document.getElementById('dsPlan').textContent)", 'timeout': 60}, shots))
        o = a3['observations'].get('afterFailure') or {}
        if gate:
            check('2e: 蒸馏 SSE 入口 403 落诚实文案（拒绝/403），不得谎报「需要新版 serve.py」',
                  bool(o.get('err')) and ('拒绝' in o['err'] or '403' in o['err']) and '新版 serve.py' not in o['err'], o)
            check('2e: 返回方案后探针真实恢复',
                  bool(a3.get('recovery') and a3['recovery']['ready']), a3.get('recovery'))
        g.ev("window.__cldistill.close()")

        g.ev("CLSkyEnrich.open()")
        plan_ready = g.until("!!document.querySelector('#skyEnrichPanel [data-action=plan]')", 10)
        g.ev("(()=>{const s=document.querySelector('#skyEnrichPanel select');s.value='semantic';"
             "s.dispatchEvent(new Event('change'));return s.value})()")
        if not plan_ready:
            check('3: 补析面板可打开且有「查看方案」按钮', False, None)
        PLAN_TRIGGER = "document.querySelector('#skyEnrichPanel [data-action=plan]').click()"
        PLAN_RECOVER = {'trigger': PLAN_TRIGGER,
                        'ready': "(()=>{const s=document.querySelector('#skyEnrichPanel .ske-status');"
                                 "return !!(s && /方案已就绪/.test(s.textContent));})()", 'timeout': 60}

        def enrich_case(tag, status=None, body=None, slow=False):
            setup = {'hold_seconds': SLOW_WAIT, 'settle_seconds': 1.5} if slow else {'status': status, 'body': body}
            return run_case(g, b, tag, PAT_PLAN, '/api/enrich/plan', PLAN_TRIGGER, OBS_ENRICH_JS, setup,
                            PLAN_RECOVER, shots)

        print('\n[3A] POST /api/enrich/plan 403', flush=True)
        a4 = put('enrich-plan-403', enrich_case('L3a-403', 403, b'Forbidden'))
        o = a4['observations'].get('afterFailure') or {}
        if gate:
            check('3a: 方案 403 按接入被拒处理，给出「无需 API」的真实退路',
                  bool(o.get('error')) and '接入不可用' in o['error'] and o.get('localBtnVisible') is True, o)
            check('3a: 解除后重新查看方案真实就绪',
                  bool(a4.get('recovery') and a4['recovery']['ready']), a4.get('recovery'))

        print('\n[3B] POST /api/enrich/plan 500', flush=True)
        b4 = put('enrich-plan-500', enrich_case('L3b-500', 500, b'Internal Server Error'))
        o = b4['observations'].get('afterFailure') or {}
        if gate:
            check('3b: 方案 500 文案指认服务故障且说明可重试',
                  bool(o.get('error')) and '500' in o['error'] and '重试' in o['error'], o)
            check('3b: 解除后重新查看方案真实就绪',
                  bool(b4.get('recovery') and b4['recovery']['ready']), b4.get('recovery'))

        print('\n[3C] POST /api/enrich/plan 200 但非 JSON', flush=True)
        c4 = put('enrich-plan-corrupt', enrich_case('L3c-corrupt', 200, b'<html>Service Unavailable</html>'))
        o = c4['observations'].get('afterFailure') or {}
        if gate:
            check('3c: 方案损坏响应明说「返回内容不是预期的数据格式」，不得泄原始解析异常',
                  bool(o.get('error')) and '返回内容不是预期的数据格式' in o['error']
                  and 'token' not in o['error'], o)
            check('3c: 解除后重新查看方案真实就绪',
                  bool(c4.get('recovery') and c4['recovery']['ready']), c4.get('recovery'))

        print('\n[3D] POST /api/enrich/plan 挂起 15s+', flush=True)
        d4 = put('enrich-plan-slow', enrich_case('L3d-slow', slow=True))
        oh = d4['observations'].get('duringHold') or {}
        if gate:
            check('3d: 方案超过 15s 无返回必须给出慢响应反馈，不得永远停在「正在查看方案」',
                  bool(oh.get('error')) and '15' in oh['error']
                  and (not oh.get('status') or '正在查看方案' not in oh['status']), oh)
            check('3d: 慢响应反馈不误判为鉴权阻断', not (oh.get('state') or {}).get('authBlock'), oh)
            check('3d: 解除后重新查看方案真实就绪',
                  bool(d4.get('recovery') and d4['recovery']['ready']), d4.get('recovery'))

        if gate:
            health = g.ev(HEALTH_JS)
            check('全流程收尾无未捕获 JS 错误 / 未处理拒绝', health['jserr'] == 0 and health['jsrej'] == 0, health)
    except Exception as exc:
        report['sessionError'] = str(exc)
        print('FAIL session: %s' % exc, flush=True)
        if gate:
            check('session completed', False, str(exc))
    finally:
        try:
            g.call('Fetch.disable')
        except Exception:
            pass
        b.close()

    report['finishedAt'] = datetime.now(timezone.utc).isoformat()
    report['ok'] = (all(c['ok'] for c in checks) and bool(checks)) if gate else True
    (out_dir / ('llm-failure-modes-%s.json' % args.mode)).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('\nLLM FAILURE MODES %s · %d/%d · %s' % (
        ('OK' if report['ok'] else 'FAIL'), sum(c['ok'] for c in checks), len(checks),
        out_dir / ('llm-failure-modes-%s.json' % args.mode)), flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
