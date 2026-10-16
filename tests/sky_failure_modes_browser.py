#!/usr/bin/env python3
"""失败模式审计（商业交付成熟度）：四类开书失败的真实注入与恢复路径验证。

四类失败（CDP 注入，全是真实网络层行为，不是伪造 JS 状态）：
  A. 主数据 JSON 404            —— Fetch 域 fulfillRequest(responseCode=404)
  B. 数据 200 但 JSON 损坏（截断）—— Fetch 域 fulfillRequest(200, 截断字节)
  C. 网络中断                   —— Fetch 域 failRequest(InternetDisconnected)，
                                  与浏览器 offline 走同一条 fetch 拒绝路径
  D. 服务端慢响应               —— Fetch 域扣住 requestPaused 不放行，10s / >15s 两档，
                                  观察 loading UI 在扣留期间的真实表现，再放行验证恢复

两种用法：
  --mode observe  只记录观测矩阵（修复前基线 / 审计取证），不因缺陷失败；
  --mode gate     把「诚实错误面 + 可恢复」当作硬门：错误态必须出现、重试必须真实可用、
                  一次重试成功后全功能回归、文案必须区分「数据损坏」与「可重试的网络错」。

与既有浏览器验收一致，不进 scripts/accept.sh 离线门（依赖常驻 server + CL_GPU=1 串行槽位）。
用法：CL_GPU=1 python3 -s tests/sky_failure_modes_browser.py --mode gate [--base http://127.0.0.1:8765]
"""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
sys.path.insert(0, str(ROOT / 'tests'))
import sky_chaos as chaos

DATA_URL = 'data/sample-saga.json'
PROBE_PATTERN = '*://*/data/sample-saga.json*'
PROBE_MATCH = '/data/sample-saga.json'


class GuardWS:
    """WS.call 的包装：响应等待途中读到的 CDP 事件全部进 events 队列，不再静默丢弃。

    Fetch.requestPaused 必须在任何时刻都不丢——丢了扣留的请求会永远悬挂。
    """

    def __init__(self, ws):
        self.ws = ws
        self.events = []

    def call(self, method, **params):
        if method == 'Page.navigate' or method.startswith('Input.dispatch'):
            self.call('Page.bringToFront')
        ws = self.ws
        ws.id += 1
        my = ws.id
        ws.send({'id': my, 'method': method, 'params': params})
        while True:
            m = ws.recv()
            if m.get('id') == my:
                if 'error' in m:
                    raise RuntimeError(m['error'])
                return m.get('result', {})
            self.events.append(m)

    def ev(self, expr, wait=True):
        r = self.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=wait)
        if r.get('exceptionDetails'):
            raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:500])
        return r.get('result', {}).get('value')

    def take_paused(self, url_substr, seen=()):
        """从事件队列里取一条尚未消费的 requestPaused（URL 含 url_substr）。"""
        for i, m in enumerate(self.events):
            if m.get('method') != 'Fetch.requestPaused':
                continue
            req = (m.get('params') or {}).get('request') or {}
            rid = (m.get('params') or {}).get('requestId')
            if url_substr in str(req.get('url', '')) and rid not in seen:
                self.events.pop(i)
                return m['params']
        return None

    def pump_paused(self, url_substr, timeout=30, seen=()):
        deadline = time.monotonic() + timeout
        old_timeout = self.ws.s.gettimeout()
        try:
            while time.monotonic() < deadline:
                hit = self.take_paused(url_substr, seen)
                if hit:
                    return hit
                self.continue_strays(url_substr)
                self.ws.s.settimeout(min(0.5, max(0.05, deadline - time.monotonic())))
                try:
                    self.events.append(self.ws.recv())
                except socket.timeout:
                    pass
        finally:
            self.ws.s.settimeout(old_timeout)
        return None

    def continue_strays(self, url_substr):
        keep = []
        for m in self.events:
            if m.get('method') == 'Fetch.requestPaused':
                req = (m.get('params') or {}).get('request') or {}
                if url_substr not in str(req.get('url', '')):
                    try:
                        self.call('Fetch.continueRequest', requestId=(m.get('params') or {}).get('requestId'))
                    except Exception:
                        pass
                    continue
            keep.append(m)
        self.events = keep

    def until(self, expr, timeout=10, step=0.25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.ev(expr):
                    return True
            except Exception:
                pass
            time.sleep(step)
        return False


OBSERVE_JS = r"""(()=>{
  const $=id=>document.getElementById(id);
  const vis=e=>{if(!e)return false;const r=e.getBoundingClientRect(),c=getComputedStyle(e);
    return !e.hidden&&r.width>0&&r.height>0&&c.display!=='none'&&c.visibility!=='hidden'&&+c.opacity>0;};
  const home=$('skyHome'), err=$('skyHomeError'), load=$('skyHomeLoading'), retry=$('skyHomeErrRetry');
  const tech=$('skyHomeErrorTech');
  return {
    mode: home ? home.dataset.mode||null : null,
    homeShown: vis(home),
    errorShown: vis(err),
    why: $('skyHomeErrorWhy') ? $('skyHomeErrorWhy').textContent : null,
    src: $('skyHomeErrorSrc') ? $('skyHomeErrorSrc').textContent : null,
    heading: $('skyHomeErrorH') ? $('skyHomeErrorH').textContent.trim() : null,
    techShown: vis(tech),
    techDetail: $('skyHomeErrorDetail') ? $('skyHomeErrorDetail').textContent : null,
    retry: retry ? {visible: vis(retry), disabled: !!retry.disabled, retryable: retry.dataset.retryable||null} : null,
    loadingShown: vis(load),
    loadingText: $('skyHomeLoadingT') ? $('skyHomeLoadingT').textContent : null,
    loaderOpen: (()=>{const l=$('loader'); return !!(l && !l.classList.contains('off'));})(),
    graphReady: !!(window.CLApp && CLApp.graph && CLApp.graph()),
    loadError: window.CLLoadError ? {kind: CLLoadError.kind, status: CLLoadError.status} : null,
    bodyText: (document.body.innerText||'').replace(/\s+/g,' ').slice(0, 220),
    health: (()=>{const h=window.__headlessHealth||{}; return {jserr:(h.jserr||[]).length, jsrej:(h.jsrej||[]).length};})()
  };
})()"""


def fulfill(g, paused, status, body_bytes, content_type='application/json'):
    g.call('Fetch.fulfillRequest', requestId=paused['requestId'], responseCode=status,
           responseHeaders=[{'name': 'content-type', 'value': content_type},
                            {'name': 'content-length', 'value': str(len(body_bytes))}],
           body=base64.b64encode(body_bytes).decode())


def wait_error(g, timeout=20):
    return g.until("(()=>{var e=document.getElementById('skyHomeError');"
                   "if(!e||e.hidden)return false;var r=e.getBoundingClientRect();"
                   "return getComputedStyle(e).display!=='none'&&r.width>0;})()", timeout)


def wait_ready(g, timeout=45):
    return g.until("!!(window.CLApp&&CLApp.graph()&&CLApp.graph().characters&&"
                   "CLApp.graph().characters.length>0&&window.CLSky&&CLSky.model())", timeout)


def full_function_check(g):
    """一次重试成功后全功能回归：图谱、星空模型、剧情开合、剧情线卡片。"""
    g.ev("CLSky.stop()")
    ok_plot = g.until("(()=>{CLSky.setPlot(true);return CLSky.state().plot===true;})()", 10)
    deck = g.until("!!(CLSky.deck()&&CLSky.deck().stats&&CLSky.deck().stats().cards>0)", 10)
    g.ev("CLSky.setPlot(false)")
    off = g.until("CLSky.state().plot===false", 10)
    health = g.ev("(()=>{const h=window.__headlessHealth,S=CLApp.scene();"
                  "return {jserr:h.jserr.length,jsrej:h.jsrej.length,"
                  "shader:S.shaderErrors?S.shaderErrors().length:0}})()")
    return {'plotOn': ok_plot, 'deckCards': deck, 'plotOff': off,
            'characters': g.ev("CLApp.graph().characters.length"),
            'events': g.ev("CLApp.graph().events.length"),
            'nCh': g.ev("CLSky.model().nCh"),
            'health': health}


def run_case(g, b, base, name, setup, shots):
    """通用骨架：导航→扣住数据请求→注入失败→观测→（可选）恢复→功能回归。"""
    out = {'case': name, 'observations': {}, 'steps': []}
    g.call('Fetch.enable', patterns=[{'urlPattern': PROBE_PATTERN}])
    g.call('Page.navigate', url=base + '/?sky=1&data=' + DATA_URL)
    paused = g.pump_paused(PROBE_MATCH, timeout=30)
    out['intercepted'] = bool(paused)
    if not paused:
        g.call('Fetch.disable')
        out['steps'].append({'step': 'intercept', 'error': 'requestPaused never arrived'})
        return out
    grab_t = time.monotonic()
    if setup.get('observe_hold_seconds'):
        time.sleep(setup['observe_hold_seconds'])
        out['observations']['duringHold'] = g.ev(OBSERVE_JS)
    if setup.get('fail'):
        g.call('Fetch.failRequest', requestId=paused['requestId'], errorReason=setup['fail'])
    else:
        fulfill(g, paused, setup.get('status', 200), setup['body'])
    out['holdSeconds'] = round(time.monotonic() - grab_t, 2)
    errored = wait_error(g)
    out['errorSurfaced'] = errored
    time.sleep(setup.get('settle_seconds', 0.5))
    out['observations']['afterFailure'] = g.ev(OBSERVE_JS)
    shot(b, name + '-failure', shots)
    recovery = None
    if setup.get('recover', True) and errored:
        g.call('Fetch.disable')
        clicked = g.ev("(()=>{var r=document.getElementById('skyHomeErrRetry');"
                       "if(!r)return false;r.click();return true})()")
        recovery = {'retryClicked': clicked,
                    'graphReady': wait_ready(g, 60)}
        if recovery['graphReady']:
            time.sleep(2.5)
            recovery['function'] = full_function_check(g)
            recovery['observations'] = g.ev(OBSERVE_JS)
        shot(b, name + '-recovered' if recovery['graphReady'] else name + '-no-recovery', shots)
    out['recovery'] = recovery
    return out


def shot(b, name, shots):
    try:
        raw = b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
        (shots / (name + '.png')).write_bytes(base64.b64decode(raw['data']))
    except Exception as exc:
        print('  shot %s failed: %s' % (name, exc), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--mode', choices=['observe', 'gate'], default='observe')
    ap.add_argument('--out', default=str(artifact_path() / 'failure_modes'))
    ap.add_argument('--slow-hold', type=float, default=10.0)
    ap.add_argument('--hang-hold', type=float, default=20.0)
    args = ap.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    shots = out_dir / ('shots-' + args.mode)
    shots.mkdir(exist_ok=True)
    valid = (ROOT / DATA_URL).read_bytes()
    truncated = valid[: int(len(valid) * 0.35)]

    report = {'mode': args.mode, 'base': args.base, 'data': DATA_URL,
              'startedAt': datetime.now(timezone.utc).isoformat(), 'cases': {}, 'checks': [],
              'boundary': ('CDP Fetch 域真实注入：404/损坏字节/网络层拒绝/扣留慢响应（字节级真实）；'
                           '重试点真实按钮走真实 reload；恢复档由常驻 serve.py 真 200 供数据。'
                           '整页 offline（浏览器错误页）超出应用错误面边界，C 档用网络层拒绝覆盖同一 fetch 拒绝路径。')}
    checks = report['checks']

    def check(name, ok, detail=None):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:600]), flush=True)
        return ok

    b = chaos.Browser(1440, 900)
    try:
        b.start()
        g = GuardWS(b.ws)

        print('\n[A] 数据 JSON 404', flush=True)
        a = run_case(g, b, args.base, 'A-404',
                     {'status': 404, 'body': b'Not Found'}, shots)
        report['cases']['A-404'] = a
        obs = a['observations'].get('afterFailure') or {}
        if args.mode == 'gate':
            check('a404: 错误面出现而非白屏/永久 loading',
                  a['errorSurfaced'] and obs.get('why') and not obs.get('loadingShown') and not obs.get('loaderOpen'), obs)
            check('a404: 文案说清文件找不到（不是笼统报错）',
                  obs.get('why') and '找不到' in obs['why'], obs.get('why'))
            check('a404: 重试钮真实存在且解除后一次重试全功能回归',
                  bool(a.get('recovery') and a['recovery']['retryClicked']
                       and a['recovery']['graphReady']
                       and a['recovery']['function']['plotOn']
                       and a['recovery']['function']['deckCards']
                       and a['recovery']['function']['plotOff']
                       and a['recovery']['function']['characters'] > 0
                       and not any(a['recovery']['function']['health'][k] for k in ('jserr', 'jsrej', 'shader'))),
                  a.get('recovery'))

        print("\n[A'] 真实服务器 404（无注入）", flush=True)
        g.call('Page.navigate', url=args.base + '/?sky=1&data=data/cache/__cl_no_such_book_zz__.json')
        real404 = wait_error(g, 25)
        obs_real = g.ev(OBSERVE_JS)
        report['cases']['A2-real-server-404'] = {'errorSurfaced': real404, 'observations': {'afterFailure': obs_real}}
        shot(b, 'A2-real-404', shots)
        if args.mode == 'gate':
            check("a': 真实服务器 404 同样落错误面且文案指认缺失",
                  real404 and obs_real.get('why') and '找不到' in obs_real['why'], obs_real)

        print('\n[B] 数据 200 但 JSON 截断损坏', flush=True)
        bcase = run_case(g, b, args.base, 'B-corrupt',
                         {'status': 200, 'body': truncated}, shots)
        report['cases']['B-corrupt'] = bcase
        obsb = bcase['observations'].get('afterFailure') or {}
        if args.mode == 'gate':
            check('b: 错误面出现（不是误导性空态）',
                  bcase['errorSurfaced'] and obsb.get('why') and not obsb.get('loadingShown'), obsb)
            check('b: 文案明说是数据损坏/不完整，而不是“没有数据”',
                  obsb.get('why') and ('损坏' in obsb['why'] or '不完整' in obsb['why']), obsb.get('why'))
            check('b: 数据错误与可重试网络错区分开（为什么行不假装重试能修好文件）',
                  bool(obsb.get('retry') and obsb['retry'].get('retryable') == 'false'
                       and obsb['retry']['visible']), obsb.get('retry'))
            check('b: 技术细节可展开（kind/status/地址），普通视图不泄露栈',
                  bool(obsb.get('techDetail')) and '.js:' not in (obsb.get('why') or '')
                  and '  at ' not in (obsb.get('why') or ''), obsb)
            retry_data = bcase.get('recovery') or {}
            check('b: 文件被修复后同一条重试路径全功能回归',
                  bool(retry_data.get('retryClicked') and retry_data.get('graphReady')
                       and retry_data.get('function', {}).get('characters', 0) > 0
                       and retry_data.get('function', {}).get('deckCards')),
                  retry_data.get('function'))

        print('\n[C] 网络中断（Fetch.failRequest / InternetDisconnected）', flush=True)
        c = run_case(g, b, args.base, 'C-offline',
                     {'fail': 'InternetDisconnected'}, shots)
        report['cases']['C-offline'] = c
        obsc = c['observations'].get('afterFailure') or {}
        if args.mode == 'gate':
            check('c: 网络中断落错误面，文案指认连接问题',
                  c['errorSurfaced'] and obsc.get('why') and obsc.get('loadError', {}).get('kind') == 'net'
                  and not obsc.get('loadingShown'), obsc)
            check('c: 可重试网络错：重试钮真实可用且解除后全功能回归',
                  bool(obsc.get('retry') and obsc['retry']['visible']
                       and c.get('recovery') and c['recovery']['graphReady']
                       and c['recovery']['function']['deckCards']
                       and not any(c['recovery']['function']['health'][k] for k in ('jserr', 'jsrej', 'shader'))),
                  c.get('recovery'))

        print('\n[D1] 服务端慢响应：扣留 %.0fs 期间观测，随后放行' % args.slow_hold, flush=True)
        d1 = run_case(g, b, args.base, 'D1-slow-10s',
                      {'status': 200, 'body': valid, 'observe_hold_seconds': args.slow_hold,
                       'recover': False}, shots)
        report['cases']['D1-slow-10s'] = d1
        obsd = (d1['observations'].get('duringHold') or {})
        ready_d1 = d1['graphReady'] = wait_ready(g, 45)
        if ready_d1:
            time.sleep(2)
        d1['finalObservations'] = g.ev(OBSERVE_JS)
        shot(b, 'D1-after-release', shots)
        if args.mode == 'gate':
            check('d1: 扣留期间 loading UI 不是卡死无反馈（home loading 可见且文案诚实）',
                  bool(obsd.get('mode') == 'loading' and obsd.get('loadingShown')
                       and obsd.get('loadingText')), obsd)
            check('d1: 慢响应放行为成功响应后图谱完整初始化',
                  ready_d1 and (d1['finalObservations'].get('graphReady')), d1.get('finalObservations'))

        print('\n[D2] 服务端挂起 >15s：观测 15s 界线两侧', flush=True)
        g.call('Fetch.enable', patterns=[{'urlPattern': PROBE_PATTERN}])
        g.call('Page.navigate', url=args.base + '/?sky=1&data=' + DATA_URL)
        paused2 = g.pump_paused(PROBE_MATCH, timeout=30)
        if not paused2:
            check('d2: 数据请求被扣住', False, None)
        else:
            time.sleep(args.hang_hold)
            d2_obs = g.ev(OBSERVE_JS)
            report['cases']['D2-hang'] = {'holdSeconds': args.hang_hold, 'observations': {'duringHang': d2_obs}}
            shot(b, 'D2-during-hang', shots)
            if args.mode == 'gate':
                check('d2: 超过 15s 无响应不得静默退回首页无任何说法——必须给出诚实错误面',
                      bool(d2_obs.get('errorShown') and d2_obs.get('why')), d2_obs)
                check('d2: 慢响应错误文案说清“读了很久没有返回”且提供重试',
                      bool(d2_obs.get('why') and ('久' in d2_obs['why'] or '返回' in d2_obs['why'])
                           and d2_obs.get('retry') and d2_obs['retry']['visible']), d2_obs)
            fulfill(g, paused2, 200, valid)
            g.call('Fetch.disable')
            d2_ready = wait_ready(g, 45)
            report['cases']['D2-hang']['graphReadyAfterRelease'] = d2_ready
            if args.mode == 'gate':
                check('d2: 挂起最终放行后图谱完整初始化（UI 曾报错不代表状态死锁）', d2_ready, None)

        print('\n[E] 空但合法的图谱：整体空态必须有可见说法', flush=True)
        empty_graph = json.dumps({'title': '空图', 'characters': [], 'events': [],
                                  'relations': [], 'storylines': [], 'meta': {}}).encode()
        g.call('Fetch.enable', patterns=[{'urlPattern': PROBE_PATTERN}])
        g.call('Page.navigate', url=args.base + '/?sky=1&data=' + DATA_URL)
        e_paused = g.pump_paused(PROBE_MATCH, timeout=30)
        e_obs = {}
        if not e_paused:
            check('e: 数据请求被扣住以注入空图', False, None)
        else:
            fulfil_e = e_paused if isinstance(e_paused, dict) else {'requestId': e_paused}
            fulfill(g, fulfil_e, 200, empty_graph)
            g.continue_strays(PROBE_MATCH)
            g.until("!!(window.CLApp&&CLApp.graph&&CLApp.graph())", timeout=30)
            time.sleep(2.5)
            e_obs = g.ev("""(function(){var e=document.getElementById('toast');if(!e)return {no:true};
              var st=getComputedStyle(e), r=e.getBoundingClientRect();
              var t=e.textContent||'';
              return {text:t.slice(0,140), visible:(st.display!=='none'&&st.visibility!=='hidden'&&parseFloat(st.opacity)>0.05&&r.width>0),
                      mentionsEmpty:/没有角色|没有事件|不会有可读/.test(t),
                      claimsError:/损坏|失败|找不到/.test(t),
                      graphReady:!!(window.CLApp&&CLApp.graph&&CLApp.graph()),
                      nc:((CLApp.graph()||{}).characters||[]).length,
                      ne:((CLApp.graph()||{}).events||[]).length};})()""")
        report['cases']['E-empty-graph'] = {'observations': e_obs}
        if args.mode == 'gate':
            check('e: 空图必须给出整体空态的可见说法（实测曾完全无提示）',
                  bool(e_obs.get('mentionsEmpty')), e_obs)
            check('e: 空图不得被冒充成错误（它是合法数据，不是失败）',
                  bool(e_obs.get('mentionsEmpty')) and not e_obs.get('claimsError'), e_obs)

        if args.mode == 'gate':
            health = g.ev("(()=>{const h=window.__headlessHealth||{};"
                          "return {jserr:(h.jserr||[]).length,jsrej:(h.jsrej||[]).length}})()")
            check('全流程收尾无未捕获 JS/未处理拒绝（仅剩失败注入自身留下的合理记录）',
                  health['jserr'] == 0, health)
    except Exception as exc:
        report['sessionError'] = str(exc)
        print('FAIL session: %s' % exc, flush=True)
        if args.mode == 'gate':
            check('session completed', False, str(exc))
    finally:
        try:
            g.call('Fetch.disable')
        except Exception:
            pass
        b.close()

    report['finishedAt'] = datetime.now(timezone.utc).isoformat()
    report['ok'] = (all(c['ok'] for c in checks) and bool(checks)) if args.mode == 'gate' else True
    (out_dir / ('failure-modes-%s.json' % args.mode)).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('\nFAILURE MODES %s · %d/%d · %s' % (
        ('OK' if report['ok'] else 'FAIL'), sum(c['ok'] for c in checks), len(checks),
        out_dir / ('failure-modes-%s.json' % args.mode)), flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
