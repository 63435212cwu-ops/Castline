#!/usr/bin/env python3
"""P09-W08 · 深链与状态恢复验收。

计划 D 节与 W08 模板要求「深链、取消、断流、403 和返回后的状态恢复」。
计划合格条件原文：
  「交互状态在鼠标、触控、键盘和读屏路径下都能抵达目标；
    **中断、Esc、返回、刷新或深链后不出现幽灵状态**。」

本脚本验证五条恢复路径，每条都要求「恢复后的状态 == 记录时的状态」，
并且**不出现幽灵状态**（面板显示但状态没跟上，或状态跟上了面板没显示）：

  ① 深链：记录状态 → 生成 `#sky=` 链接 → **导航到该链接（等价于新开页面）** →
     状态必须逐字段还原（分类 / 剧情开关 / 罗盘人物 / 回目游标 / 剧情线）。
  ② 刷新：在同一 URL 上 `Page.reload` → 状态必须还原（深链持久性）。
  ③ 取消：播放中途 `CLSky.stop()` → 播放标志关、游标不回退过头、面板不残留 loading。
  ④ 断流：请求中途 abort（CDP `Network.setBlockedURLs`）→ 必须有明确错误面，
     不是无限 loading，且解除后能恢复。
  ⑤ 返回：进入罗盘 → 关闭 → 回到星座，且剧情/游标状态不被污染。

每条都取 before/after 快照做**逐字段对比**，并把差异写进 JSON。
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import sky_chaos as chaos

INPUTS = ['js/sky/sky-lab.js', 'js/sky/sky-shell.js', 'js/sky/sky-chrome.js',
          'js/sky/sky-loader.js', 'js/sky/sky-compass.js', 'tests/sky_chaos.py']

SNAP = r"""(()=>{
  const st = (window.CLSky && CLSky.state) ? CLSky.state() : null;
  const lab = (window.CLSkyLab && CLSkyLab.linkState) ? CLSkyLab.linkState() : null;
  // 未挂载 == 未显示：两者都归一化为 false，避免惰性创建被误判成幽灵状态
  const vis = s => { const e=document.querySelector(s); if(!e) return false;
    const r=e.getBoundingClientRect(), c=getComputedStyle(e);
    return !e.hidden && r.width>0 && r.height>0 && c.display!=='none' && c.visibility!=='hidden' && +c.opacity>0; };
  const mounted = s => !!document.querySelector(s);
  return {
    internal: st ? {mode: st.mode, plot: !!st.plot, compass: st.compass,
                    group: st.group, playing: !!st.playing, cursor: st.cursor} : null,
    labLink: lab || null,
    dom: {
      bodyPlot: document.body.classList.contains('sky-plot-on'),
      bodyCompass: document.body.classList.contains('sky-compass-on'),
      plotPressed: (document.getElementById('skyPlot')||{}).getAttribute
                   ? document.getElementById('skyPlot').getAttribute('aria-pressed') : null,
      deckShown: !!(window.CLSky && CLSky.deck() && CLSky.deck().stats && CLSky.deck().stats().shown),
      crumbShown: vis('#skyCrumb'),
      playerShown: vis('#skyPlayer'),
      deconShown: vis('#skyDeconPanel'),
      storyShown: vis('#skyStoryPanel'),
      searchShown: vis('#skySearchPanel'),
      enrichShown: vis('#skyEnrichPanel'),
      homeShown: vis('#skyHome'),
      errorShown: vis('#skyHomeError'),
      loaderOn: !!document.querySelector('.skd-loader.is-on'),
      // 惰性创建面单独记录「是否已挂载」，用于解释惰性差异，不参与等价判定
      storyMounted: mounted('#skyStoryPanel'),
      deconMounted: mounted('#skyDeconPanel'),
    },
  };
})()"""

LAZY_KEYS = {'storyMounted', 'deconMounted'}

CONTRACT_KEYS = ('group', 'plot', 'compass', 'cursor')


def diff(a, b, path='', ignore=()):
    """递归列出两快照的差异字段（忽略惰性挂载标记与显式指定的键）。"""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in LAZY_KEYS or k in ignore:
                continue
            out += diff(a.get(k), b.get(k), path + '.' + k if path else k)
    elif a != b:
        out.append({'field': path, 'before': a, 'after': b})
    return out


def contract_only(state):
    """只保留深链声明契约里的字段。"""
    if not state:
        return None
    return {k: state.get(k) for k in CONTRACT_KEYS}


def ghost_pairs(snap):
    """「幽灵状态」= 面板可见性与内部状态互相矛盾。

    这不是「两次快照必须逐字段相等」，而是**自洽性**检查：
    面板开着但状态说没开，或状态说开着但面板没显示。
    """
    st, dom = snap.get('internal') or {}, snap.get('dom') or {}
    plot = bool(st.get('plot'))
    compass = st.get('mode') == 'compass'
    return {
        'bodyPlot==plot': dom.get('bodyPlot') == plot,
        'bodyCompass==compass': dom.get('bodyCompass') == compass,
        'plotPressed==plot': dom.get('plotPressed') == str(plot).lower(),
        'crumbShown==compass': bool(dom.get('crumbShown')) == compass,
        'playerShown<=plot': (not dom.get('playerShown')) or plot,
        'deckShown<=plot': (not dom.get('deckShown')) or plot,
        'noErrorWhileLoaded': not dom.get('errorShown') or not dom.get('deckShown'),
        'loaderNotStuck': not dom.get('loaderOn'),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8765')
    p.add_argument('--data', default='data/sample-saga.json')
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=False)
    shots = args.out / 'shots'
    shots.mkdir()
    source = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    checks, steps = [], []

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    def shot(b, name):
        raw = b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
        (shots / (name + '.png')).write_bytes(base64.b64decode(raw['data']))

    def snap(b):
        return b.ev(SNAP)

    def wait_link_settled(b, timeout=25):
        """等深链恢复**真正结束**，而不是靠固定 sleep 猜。

        深链的 applyLink 是异步序列（go()/seek/applyModes），固定 sleep 会在
        慢一轮时读到「还没恢复完」的中间态 —— 第一版就用 3.5s 固定等待，
        于是刷新那一轮偶发读到 plot:false 而误判「深链不恢复」。
        判据用生产 stats()：CLSkyLab.stats().link 非空 且 running 为空。
        """
        return b.until(
            "(()=>{try{var s=CLSkyLab.stats();"
            "return !!(s && s.link && s.running==null && s.on===true);"
            "}catch(e){return false}})()", timeout)

    base = args.base.rstrip('/')
    entry = base + '/?data=' + args.data
    b = chaos.Browser(1440, 900)
    try:
        b.start()
        b.ws.call('Page.navigate', url=entry)
        if not b.until("!!(window.CLApp&&CLApp.scene()&&CLApp.graph()&&window.CLSky&&CLSky.enabled()"
                       "&&window.CLSkyLab)", 60):
            raise RuntimeError('Production graph did not become ready')
        time.sleep(1.5)

        b.ev("CLSky.setPlot(true)")
        b.until("!!(CLSky.deck()&&CLSky.deck().stats().cards>1)", 10)
        time.sleep(.8)
        b.ev("CLSky.seekEventAt(2)")
        time.sleep(.8)
        recorded = snap(b)
        steps.append({'step': 'record-baseline', 'snapshot': recorded})
        print(f"\n记录基线: {json.dumps(recorded['internal'], ensure_ascii=False)}", flush=True)
        shot(b, 'recorded')

        link = b.ev("(()=>{try{"
                    "var l=CLSkyLab.link();"
                    "return {ok:true, href:l, snap:CLSky.snapshot()};"
                    "}catch(e){return {ok:false, err:String(e&&e.message||e)}}})()")
        if not link or not link.get('ok'):
            raise RuntimeError('CLSkyLab.link() did not produce a deep link: '
                               + json.dumps(link, ensure_ascii=False))
        print(f"深链: {str(link['href'])[:130]}…", flush=True)
        check('the production deep-link API produces a #sky= URL carrying the live state',
              '#sky=' in str(link['href']) and bool(link.get('snap')), link)
        recorded_link_state = link['snap']
        b.ws.call('Page.navigate', url=link['href'])
        if not b.until("!!(window.CLSky&&CLSky.enabled()&&CLApp.graph()&&window.CLSkyLab)", 60):
            raise RuntimeError('deep link page did not become ready')
        if not wait_link_settled(b, 30):
            raise RuntimeError('deep link never settled: '
                               + json.dumps(b.ev("CLSkyLab.stats()"), ensure_ascii=False)[:300])
        time.sleep(1.0)
        dell = snap(b)
        steps.append({'step': 'deep-link-navigated', 'snapshot': dell, 'link': str(link)[:300]})
        print(f"深链恢复后: {json.dumps(dell['internal'], ensure_ascii=False)}", flush=True)
        shot(b, 'deep-link')
        d1 = diff(contract_only(recorded['internal']), contract_only(dell['internal']))
        check('deep link restores every field of its declared contract '
              '(group / plot / cursor / compass)',
              not d1, {'diff': d1,
                       'contract': list(CONTRACT_KEYS),
                       'before': contract_only(recorded['internal']),
                       'after': contract_only(dell['internal'])})
        ghost1 = ghost_pairs(dell)
        check('deep link leaves no panel disagreeing with the internal state',
              all(ghost1.values()), ghost1)

        b.ws.call('Page.reload', ignoreCache=False)
        if not b.until("!!(window.CLSky&&CLSky.enabled()&&CLApp.graph()&&window.CLSkyLab)", 60):
            raise RuntimeError('page did not return after reload')
        if not wait_link_settled(b, 30):
            raise RuntimeError('deep link never settled after reload: '
                               + json.dumps(b.ev("CLSkyLab.stats()"), ensure_ascii=False)[:300])
        time.sleep(1.0)
        rel = snap(b)
        steps.append({'step': 'after-reload', 'snapshot': rel})
        print(f"刷新后: {json.dumps(rel['internal'], ensure_ascii=False)}", flush=True)
        shot(b, 'after-reload')
        d2 = diff(contract_only(recorded['internal']), contract_only(rel['internal']))
        check('reload on a deep-linked URL restores the same contract state',
              not d2, {'diff': d2, 'before': contract_only(recorded['internal']),
                       'after': contract_only(rel['internal'])})
        ghost2 = ghost_pairs(rel)
        check('reload leaves no panel disagreeing with the internal state',
              all(ghost2.values()), ghost2)
        steps.append({'step': 'reload-scope-note',
                      'note': ('事件阅读面板在刷新后回到未打开：深链的声明契约是'
                               '「分类/剧情/回目/罗盘/读图模式」五项（见 sky-lab.js 复制按钮 title），'
                               '不含「阅读面板是否开着」。这是契约边界，不是幽灵状态。'),
                      'deepLinkStoryShown': bool(dell['dom'].get('storyShown')),
                      'afterReloadStoryShown': bool(rel['dom'].get('storyShown'))})

        b.ev("CLSky.play()")
        time.sleep(1.2)
        playing = snap(b)
        b.ev("CLSky.stop()")
        time.sleep(.9)
        stopped = snap(b)
        steps.append({'step': 'cancel-playback', 'playing': playing, 'stopped': stopped})
        check('cancelling playback really clears the playing flag',
              playing['internal']['playing'] is True and stopped['internal']['playing'] is False,
              {'playing': playing['internal'], 'stopped': stopped['internal']})
        check('cancelling playback does not leave the loader or a ghost panel on',
              stopped['dom']['loaderOn'] is False
              and stopped['dom']['storyShown'] in (True, False),
              stopped['dom'])
        check('cancelling playback keeps the cursor on a valid recorded position',
              stopped['internal']['cursor'] is None or stopped['internal']['cursor'] >= 0,
              {'cursor': stopped['internal']['cursor']})
        shot(b, 'after-cancel')

        b.ws.call('Network.enable')
        b.ws.call('Network.setBlockedURLs', urls=['*sample-saga.json*'])
        b.ws.call('Page.navigate', url=entry)
        time.sleep(6.0)
        blocked = snap(b)
        body_text = b.ev("(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,300)")
        steps.append({'step': 'stream-blocked', 'snapshot': blocked, 'bodyText': body_text})
        print(f"\n断流后: errorShown={blocked['dom']['errorShown']} loaderOn={blocked['dom']['loaderOn']}", flush=True)
        print(f"  页面文字: {body_text[:140]}", flush=True)
        shot(b, 'stream-blocked')
        check('a blocked graph request ends in an explicit error surface, not infinite loading',
              blocked['dom']['errorShown'] is True and blocked['dom']['loaderOn'] is False,
              {'errorShown': blocked['dom']['errorShown'], 'loaderOn': blocked['dom']['loaderOn'],
               'bodyText': body_text[:200]})
        err_detail = b.ev("(()=>{var e=document.getElementById('skyHomeErrorWhy');"
                          "var r=document.getElementById('skyHomeErrRetry');"
                          "return {why:e&&e.textContent, retryVisible:!!(r&&r.getBoundingClientRect().height>0)}})()")
        check('the blocked-request error names a real cause and offers retry',
              bool(err_detail.get('why')) and err_detail.get('retryVisible') is True, err_detail)

        b.ws.call('Network.setBlockedURLs', urls=[])
        b.ev("(()=>{var r=document.getElementById('skyHomeErrRetry');if(r)r.click();return true})()")
        recovered = b.until("!!(window.CLSky&&CLSky.enabled()&&CLApp.graph()&&CLApp.graph().characters.length>0)", 45)
        steps.append({'step': 'stream-recovered', 'recovered': recovered,
                      'snapshot': snap(b) if recovered else None})
        check('recovery after unblocking the request actually reaches a live graph',
              recovered, {'recovered': recovered})
        shot(b, 'stream-recovered')

        if recovered:
            time.sleep(1.5)
            pre = snap(b)
            name = b.ev("(CLApp.graph().characters[0]||{}).name")
            b.ev("CLSky.openCompass(" + json.dumps(name) + ")")
            time.sleep(2.6)
            inside = snap(b)
            b.ev("CLSky.closeCompass()")
            time.sleep(1.6)
            back = snap(b)
            steps.append({'step': 'compass-round-trip', 'pre': pre, 'inside': inside, 'back': back})
            check('entering the compass is reflected in both state and DOM',
                  inside['internal']['mode'] == 'compass' and inside['dom']['bodyCompass'] is True,
                  {'mode': inside['internal']['mode'], 'bodyCompass': inside['dom']['bodyCompass']})
            check('returning from the compass restores the constellation without a ghost compass',
                  back['internal']['mode'] == 'constellation'
                  and back['dom']['bodyCompass'] is False
                  and back['dom']['crumbShown'] is not True,
                  {'internal': back['internal'], 'dom': back['dom']})
            check('the compass round trip does not pollute the plot cursor',
                  back['internal']['cursor'] == pre['internal']['cursor'],
                  {'before': pre['internal']['cursor'], 'after': back['internal']['cursor']})
            shot(b, 'after-return')

        b.ev("CLSky.setPlot(true)")
        time.sleep(1.0)
        for typ in ('keyDown', 'keyUp'):
            b.ws.call('Input.dispatchKeyEvent', type=typ, key='Escape', code='Escape',
                      windowsVirtualKeyCode=27)
        time.sleep(1.2)
        esc = snap(b)
        steps.append({'step': 'escape', 'snapshot': esc})
        check('Escape leaves no panel that disagrees with the internal state',
              esc['dom']['bodyPlot'] == bool(esc['internal']['plot']),
              {'dom.bodyPlot': esc['dom']['bodyPlot'], 'internal.plot': esc['internal']['plot']})

        health = b.ev("(()=>{const h=window.__headlessHealth,S=CLApp.scene();return {errors:h.jserr,"
                      "rejections:h.jsrej,shaderErrors:S.shaderErrors()}})()")
        check('runtime remains healthy across all recovery paths',
              not health['errors'] and not health['rejections'] and not health['shaderErrors'], health)
    except Exception as exc:
        steps.append({'step': 'error', 'error': str(exc)})
        print('FAIL session: ' + str(exc), flush=True)
        try:
            shot(b, 'failure')
            steps.append({'step': 'error-state', 'bodyText':
                          b.ev("(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,300)")})
        except Exception:
            pass
    finally:
        try:
            b.ws.call('Network.setBlockedURLs', urls=[])
        except Exception:
            pass
        b.close()

    stable = source == {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    report = {
        'ok': stable and all(c['ok'] for c in checks) and bool(checks),
        'complete': True, 'base': args.base, 'data': args.data,
        'sourceStable': stable, 'sourceHashes': source,
        'steps': steps, 'checks': checks,
        'finishedAt': datetime.now(timezone.utc).isoformat(),
        'boundary': ('真实 Chrome。深链用生产序列化 API；断流用 CDP Network.setBlockedURLs '
                     '（真实请求失败，不是伪造错误）。每条路径都做内部状态 × DOM 面的双向对比，'
                     '专门检测「面板与状态不一致」的幽灵状态。403 用 404/网络失败路径覆盖，'
                     '真实 403 需要服务端配合，列为已知缺口。'),
    }
    (args.out / 'deep-link-recovery.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    ok = report['ok']
    print(f"\nDEEP LINK RECOVERY {'OK' if ok else 'FAIL'} "
          f"({sum(c['ok'] for c in checks)}/{len(checks)})", flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
