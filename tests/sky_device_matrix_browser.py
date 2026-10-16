#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仿真设备配置矩阵（EMULATED — NOT REAL-DEVICE EVIDENCE）。

审核缺口「真机矩阵未验」的本轮替代证据：真机不可用，这里用 Chrome DevTools
协议的设备仿真（Emulation.setDeviceMetricsOverride / setUserAgentOverride /
setTouchEmulationEnabled）把核心路径在多个仿真配置档下各跑一遍。

诚实的边界（写进每份报告与终端输出）：
  * 这是 Chromium Blink + V8 + Metal/SwiftShader 渲染路径，不是 iOS WebKit/Safari
    内核——Safari 特有行为（WebKit 触控语义、橡皮筋滚动、PWA 记时器节流等）
    本矩阵既不能验证也不能排除。
  * UA 与 dpr 只是字符串/像素比仿真；不能证明真机传感器、触控延迟、键盘遮挡、
    系统级缩放与本机字体渲染。
  * 桌面「高缩放」档只做 CSS 视口等效；更窄的 320×225/320×640 等效已由
    tests/sky_reading_reflow_browser.py 常驻覆盖。

为什么不是复用现有套件的编排调用：sky_interaction_access_browser 的视口写死在
脚本内部（1600×1000 / 390×844·dpr=1·无 UA），sky_reading_reflow 同样写死
（640×450 / 320×225 / 320×640），公共层 sky_chaos.Browser.size() 也硬编码
deviceScaleFactor=1、mobile=False，均无 UA 注入能力。因此对每个配置档本脚本
自建 Chrome 会话并注入仿真参数，检查动作沿用同一批真实 CDP 输入模式
（pointer/touch、elementFromPoint 占用校验、Input.insertText、真实 Escape）。

每档检查：仿真生效、应用健康加载、剧情按钮真实点按、证据层/因果/伏笔页签真实
点击可达、搜索 dialog 插入文本与 Esc 焦点往返、剧情播放阶段切换、移动端 44px
触控目标抽查、收尾零 JS/Promise/Shader 错误。

串行 GPU 槽位（CL_GPU=1）：与 tests/sky_chaos.py 一致，Metal 真 GPU；不设 CL_GPU=1 时拒绝运行。

用法：
  CL_GPU=1 python3 -s tests/sky_device_matrix_browser.py [--base http://127.0.0.1:8000]
                       [--out /tmp/castline-shots/sky-device-matrix] [--profiles iphone14,pixel8,ipad,desktop-highzoom]
未给 --base 时本脚本自行启动 serve.py 的临时实例（随机空端口），结束时回收。
"""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import sky_chaos as chaos

BANNER = 'EMULATED — NOT REAL-DEVICE EVIDENCE'
DISCLAIMER = (
    'Chromium Blink/V8 + 仿真 UA/dpr/触控，不代表 iOS Safari (WebKit) 或真机 Android 行为；'
    '仿真不能证明也不能排除真机特有的触控延迟、键盘遮挡、滚动链与字体渲染差异。'
)

PROFILES = [
    {
        'key': 'iphone14',
        'label': 'iPhone 14 级 · 390×844 · dpr 3 · iOS Safari UA',
        'w': 390, 'h': 844, 'dpr': 3.0, 'mobile': True, 'touch': True,
        'ua': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 '
              '(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
        'uaToken': 'iPhone',
    },
    {
        'key': 'pixel8',
        'label': 'Pixel 8 级 · 412×915 · dpr 2.625 · Android Chrome UA',
        'w': 412, 'h': 915, 'dpr': 2.625, 'mobile': True, 'touch': True,
        'ua': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
        'uaToken': 'Pixel 8',
    },
    {
        'key': 'ipad',
        'label': 'iPad 11 级 · 820×1180 · dpr 2 · iPadOS Safari UA',
        'w': 820, 'h': 1180, 'dpr': 2.0, 'mobile': True, 'touch': True,
        'ua': 'Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 '
              '(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
        'uaToken': 'iPad',
    },
    {
        'key': 'desktop-highzoom',
        'label': '桌面高缩放等效 · 390×844 CSS 视口 · dpr 1 · 无 UA 覆盖（Chromium 桌面）',
        'w': 390, 'h': 844, 'dpr': 1.0, 'mobile': False, 'touch': False,
        'ua': None,
        'uaToken': None,
        'note': '等效约 780×1688 物理像素 @200% 系统缩放。更窄等效（320×225 / 320×640）由 '
                'sky_reading_reflow_browser.py 常驻覆盖，本档只补 390×844 形状。',
    },
]

DATA = 'data/cache/c84e8657afff87043c11ae57.json'
PLAY_EVENT = 184
SEARCH_QUERY = '孙悟空'

READY = ("!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&"
         "CLSky.enabled()&&window.CLSkyDeep&&CLSkyDeep.enabled()&&"
         "CLSkyDeep.stats().stars.ignite>.99&&document.querySelector('#loader.off'))")
HEALTH_JS = ("(()=>{const h=window.__headlessHealth,S=CLApp.scene(),d=S.digest();"
             "return {jserr:h.jserr,jsrej:h.jsrej,shaderErrors:S.shaderErrors(),"
             "frameErrors:d.frameHooks&&d.frameHooks.errors||0}})()")


def run():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default=None, help='不给时自行升起 serve.py 临时实例')
    p.add_argument('--data', default=DATA)
    p.add_argument('--out', type=Path,
                   default=Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'sky-device-matrix')
    p.add_argument('--profiles', default=','.join(x['key'] for x in PROFILES))
    args = p.parse_args()

    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    wanted = [x.strip() for x in args.profiles.split(',') if x.strip()]
    profiles = [x for x in PROFILES if x['key'] in wanted]
    if not profiles:
        raise SystemExit('no matching profiles: ' + args.profiles)

    print('=== SKY DEVICE MATRIX === %s' % BANNER, flush=True)
    print(DISCLAIMER, flush=True)

    server = None
    base = args.base
    if not base:
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        server = subprocess.Popen([sys.executable, '-s', 'serve.py', str(port)],
                                  cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 40
        while True:
            try:
                if urllib.request.urlopen('http://127.0.0.1:%d/' % port, timeout=2).status == 200:
                    break
            except Exception:
                if time.monotonic() > deadline:
                    raise SystemExit('serve.py did not come up on port %d' % port)
                time.sleep(0.3)
        base = 'http://127.0.0.1:%d' % port
        print('server: %s (self-managed serve.py)' % base, flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        for prof in profiles:
            results.append(run_profile(base, args, prof))
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=5)
            except Exception:
                server.kill()

    ok = all(x['ok'] for x in results)
    report = {
        'ok': ok,
        'banner': BANNER,
        'emulated': True,
        'realDeviceEvidence': False,
        'disclaimer': DISCLAIMER,
        'base': base,
        'data': args.data,
        'boundary': ('真实 CDP 输入（pointer/touch/insertText/Escape），无 DOM 事件合成、无处理器替换、'
                     '无模型请求；每档全新 Chrome 档案、无 probe 参数。'),
        'knownEmulationLimits': [
            'Blink/V8 内核行为，不代表 Safari/WebKit；iOS 特有计时器节流、触控事件语义未覆盖。',
            'UA 只是字符串；navigator.platform、navigator.maxTouchPoints 等在部分档可能被 Chrome 如实上报而非仿机值。',
            '不具备真机的电池热节流、内存压力与系统手势（边缘返回、Home 指示条遮挡）。',
            'dpr 2.625 为 Chrome 接受的浮点仿真，真机 Pixel 8 的实际渲染管线不同。',
        ],
        'profiles': results,
        'finishedAt': datetime.now(timezone.utc).isoformat(),
    }
    out_file = args.out / 'result.json'
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('', flush=True)
    for row in results:
        bad = [c['name'] for c in row['checks'] if not c['ok']]
        print('%s %s · %d/%d checks' % ('PASS' if row['ok'] else 'FAIL', row['key'],
                                        sum(c['ok'] for c in row['checks']), len(row['checks'])), flush=True)
        for name in bad:
            print('    failing: %s' % name, flush=True)
    print('report: %s' % out_file, flush=True)
    print('SKY DEVICE MATRIX %s · %s' % ('PASS' if ok else 'FAIL', BANNER), flush=True)
    return 0 if ok else 1


def run_profile(base, args, prof):
    tag = prof['key']
    row = {'key': tag, 'label': prof['label'], 'banner': BANNER,
           'viewport': [prof['w'], prof['h']], 'dpr': prof['dpr'], 'mobile': prof['mobile'],
           'emulatedUserAgent': prof['ua'],
           'note': prof.get('note'), 'checks': []}
    checks = row['checks']
    print('--- profile %s · %s' % (tag, prof['label']), flush=True)

    def check(name, ok, detail=None):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('  PASS ' if ok else '  FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:600]), flush=True)

    def step(name, fn):
        try:
            ok, detail = fn()
            check(name, ok, detail)
        except Exception as exc:
            check(name, False, {'exception': str(exc)[:800]})

    b = chaos.Browser(prof['w'], prof['h'])
    try:
        b.start()
        b.ws.call('Emulation.setDeviceMetricsOverride', width=prof['w'], height=prof['h'],
                  deviceScaleFactor=prof['dpr'], mobile=prof['mobile'])
        if prof['ua']:
            b.ws.call('Emulation.setUserAgentOverride', userAgent=prof['ua'])
        if prof['touch']:
            b.ws.call('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=5)
        b.ws.call('Page.navigate', url=base.rstrip('/') + '/?sky=1&data=' + args.data)
        ready_ok = b.until(READY, 120)
        check('app reaches production readiness (no probe parameter)', ready_ok,
              {'ready': ready_ok})
        if not ready_ok:
            row['ok'] = False
            return row
        time.sleep(2.5)

        def point(selector):
            return b.ev(("(()=>{const e=document.querySelector(" + json.dumps(selector) + "),r=e&&e.getBoundingClientRect();"
                         "if(!r||r.width<=0||r.height<=0)return {missing:true};"
                         "const x=r.x+r.width/2,y=r.y+r.height/2,h=document.elementFromPoint(x,y);"
                         "return {x,y,owned:!!(h&&(h===e||e.contains(h))),hit:h&&(h.id||h.getAttribute('class')||h.tagName),rect:{w:+r.width.toFixed(1),h:+r.height.toFixed(1)}}})()"))

        def press(selector, expect_owned=True):
            pt = point(selector)
            if pt.get('missing') or (expect_owned and not pt['owned']):
                return {'ok': False, 'point': pt}
            return press_point(pt, selector)

        def press_point(pt, selector):
            if prof['touch']:
                b.ws.call('Input.dispatchTouchEvent', type='touchStart',
                          touchPoints=[{'x': pt['x'], 'y': pt['y'], 'id': 1, 'radiusX': 3, 'radiusY': 3, 'force': 1}])
                time.sleep(.06)
                b.ws.call('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])
            else:
                b.mouse('mouseMoved', pt['x'], pt['y'])
                b.mouse('mousePressed', pt['x'], pt['y'])
                b.mouse('mouseReleased', pt['x'], pt['y'])
            time.sleep(.5)
            return {'ok': True, 'point': pt}

        def key(k):
            codes = {'Escape': 27, 'Enter': 13, 'Tab': 9, ' ': 32}
            for typ in ('keyDown', 'keyUp'):
                data = {'type': typ, 'key': k, 'code': 'Space' if k == ' ' else k,
                        'windowsVirtualKeyCode': codes[k]}
                if typ == 'keyDown' and k in ('Enter', ' '):
                    data.update(text='\r' if k == 'Enter' else ' ', unmodifiedText='\r' if k == 'Enter' else ' ')
                b.ws.call('Input.dispatchKeyEvent', **data)
            time.sleep(.25)

        def emulation_applied():
            v = b.ev("({ua:navigator.userAgent,dpr:devicePixelRatio,w:innerWidth,h:innerHeight,"
                     "touch:'ontouchstart' in window||navigator.maxTouchPoints>0})")
            want = v['w'] == prof['w'] and v['h'] == prof['h'] and abs(v['dpr'] - prof['dpr']) < 0.01
            if prof['uaToken']:
                want = want and prof['uaToken'] in v['ua']
            if prof['touch']:
                want = want and v['touch'] is True
            return want, {'actual': v, 'expected': {'w': prof['w'], 'h': prof['h'], 'dpr': prof['dpr'], 'uaToken': prof['uaToken']}}
        step('emulated viewport/dpr/user-agent take effect', emulation_applied)

        def load_health():
            h = b.ev(HEALTH_JS)
            return not h['jserr'] and not h['jsrej'] and not h['shaderErrors'] and not h['frameErrors'], h
        step('load has no JS/Promise/shader/frame-hook errors', load_health)

        def plot_toggle():
            r = press('#skyPlot')
            if not r['ok']:
                return False, r
            on = b.until('CLSky.state().plot===true', 5)
            return on, {'press': r, 'plot': b.ev('CLSky.state().plot')}
        step('real press on #skyPlot opens the plot layer', plot_toggle)

        def decon_open():
            r = press('#skyDecode')
            if not r['ok']:
                return False, r
            opened = b.until("!document.getElementById('skyDeconPanel').hidden", 5)
            return opened, {'press': r}
        step('real press on #skyDecode opens the deconstruction panel', decon_open)

        def scroll_tab_into_view(tab):
            for _ in range(6):
                ptl = point(tab)
                if ptl.get('missing'):
                    return ptl
                if ptl['owned'] and 12 <= ptl['x'] <= prof['w'] - 12:
                    return ptl
                v = b.ev("(()=>{const r=document.querySelector('.sd-tabs'),rb=r.getBoundingClientRect();"
                         "return {x:rb.x+rb.width/2,y:rb.y+rb.height/2,sl:r.scrollLeft,sw:r.scrollWidth,cw:r.clientWidth}})()")
                if not v or v['sw'] <= v['cw'] + 2:
                    return ptl
                x, y = v['x'], v['y']
                if prof['touch']:
                    b.ws.call('Input.dispatchTouchEvent', type='touchStart',
                              touchPoints=[{'x': x, 'y': y, 'id': 1, 'radiusX': 3, 'radiusY': 3, 'force': 1}])
                    n = 5 if x - 200 >= prof['w'] / 2 else 12
                    for i in range(1, n + 1):
                        b.ws.call('Input.dispatchTouchEvent', type='touchMove',
                                  touchPoints=[{'x': max(8, x - 200 * i / n), 'y': y, 'id': 1}])
                        time.sleep(.03)
                    b.ws.call('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])
                else:
                    b.ws.call('Input.dispatchMouseEvent', type='mouseWheel', x=x, y=y, deltaX=300, deltaY=0)
                time.sleep(.5)
            return point(tab)

        for mode, marker, tab in (('evidence', '事件档案', '#skyDeconTabEvidence'),
                                  ('causal', '因果网络', '#skyDeconTabCausal'),
                                  ('foreshadow', '伏笔生命周期', '#skyDeconTabForeshadow')):
            def tab_check(mode=mode, marker=marker, tab=tab):
                ptl = point(tab)
                if ptl.get('missing'):
                    return False, ptl
                if not (ptl['owned'] and 12 <= ptl['x'] <= prof['w'] - 12):
                    ptl = scroll_tab_into_view(tab)
                if not (ptl.get('owned') and 12 <= ptl.get('x', -1) <= prof['w'] - 12):
                    return False, {'point': ptl}
                r = press_point(ptl, tab)
                body = b.ev("(()=>({mode:(window.CLSkyDeconstruction&&CLSkyDeconstruction.stats&&CLSkyDeconstruction.stats()||{}).mode,"
                            "text:document.getElementById('skyDeconBody').textContent.slice(0,400),"
                            "selected:document.querySelector(" + json.dumps(tab) + ").getAttribute('aria-selected')}))()")
                return marker in body['text'] or body['mode'] == mode, {'press': r, 'body': body}
            step('%s tab (%s) reachable by real press' % (mode, marker), tab_check)

        def decon_close():
            r = press('#skyDeconPanel .sd-close')
            if not r['ok']:
                return False, r
            closed = b.until("document.getElementById('skyDeconPanel').hidden", 5)
            return closed, {'press': r}
        step('deconstruction panel closes via its real close control', decon_close)

        def search_query():
            if prof['mobile'] or b.ev('innerWidth<=900'):
                r = press('#skySearchGo')
                if not r['ok']:
                    return False, r
                focused = b.until("document.activeElement&&document.activeElement.id==='skySearch'", 5)
                if not focused:
                    return False, {'press': r, 'active': b.ev('document.activeElement&&document.activeElement.id')}
            else:
                b.ev("document.getElementById('skySearch').focus()")
                time.sleep(.2)
            b.ws.call('Input.insertText', text=SEARCH_QUERY)
            time.sleep(.5)
            opened = b.until("!document.getElementById('skySearchPanel').hidden&&"
                             "document.querySelectorAll('#skySearchResults [role=option]').length>0", 8)
            stats = b.ev('CLSkySearch.stats()')
            return opened, {'stats': stats}
        step('search dialog opens with real typed query and real candidates', search_query)

        def search_escape():
            key('Escape')
            time.sleep(.3)
            state = b.ev("({hidden:document.getElementById('skySearchPanel').hidden,"
                         "active:document.activeElement&&document.activeElement.id})")
            return state['hidden'] and state['active'] == 'skySearch', state
        step('Escape closes search and returns focus to the original input', search_escape)

        def playback_stage():
            sought = b.ev('CLSky.seekEventAt(%d)' % PLAY_EVENT)
            if sought is not True:
                return False, {'seekEventAt': sought}
            time.sleep(.8)
            r = press('#skyPlay')
            if not r['ok']:
                return False, r
            before = b.until("CLSky.state().playing&&CLSky.playerState().stage==='before'&&CLSky.playerState().links>0", 6)
            if not before:
                return False, {'press': r, 'state': b.ev('CLSky.playerState()')}
            switched = b.until("CLSky.playerState().stage!=='before'", 20)
            stage = b.ev('CLSky.playerState().stage')
            ok = switched and stage in ('event', 'after')
            b.ev('CLSky.stop()')
            time.sleep(.4)
            return ok, {'stageAfterSwitch': stage, 'stopped': not b.ev('CLSky.state().playing')}
        step('story playback switches cause-stage before→event and stops', playback_stage)

        if prof['touch']:
            def touch_targets():
                b.ev("document.activeElement&&document.activeElement.blur&&document.activeElement.blur()")
                b.ev("document.getElementById('skySearchBox').classList.remove('is-open')")
                time.sleep(.6)
                sels = ['#skyPlot', '#skyDecode', '#skyTools', '#skySearchGo', '#skyPlay', '.skd-drawerbtn:not([hidden])']
                rows = b.ev(("(Array.from(document.querySelectorAll(" + json.dumps(','.join(sels)) + ")).map(e=>{"
                             "const r=e.getBoundingClientRect(),s=getComputedStyle(e);"
                             "return {id:e.id||e.className,w:+r.width.toFixed(1),h:+r.height.toFixed(1),"
                             "visible:r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};}).filter(x=>x.visible))"))
                below = [x for x in rows if min(x['w'], x['h']) + 0.5 < 44]
                return not below and bool(rows), {'measured': rows, 'below44': below}
            step('visible primary touch targets are >= 44px (spot check)', touch_targets)

        step('session ends with zero JS/Promise/shader/frame-hook errors', load_health)
    except Exception as exc:
        check('profile session completed', False, {'exception': str(exc)[:800]})
    finally:
        try:
            shot = b.ws.call('Page.captureScreenshot', format='png')['data']
            (args.out / (tag + '-final.png')).write_bytes(base64.b64decode(shot))
        except Exception:
            pass
        b.close()
    row['ok'] = bool(checks) and all(c['ok'] for c in checks)
    print('--- %s %s' % (tag, 'PASS' if row['ok'] else 'FAIL'), flush=True)
    return row


if __name__ == '__main__':
    raise SystemExit(run())
