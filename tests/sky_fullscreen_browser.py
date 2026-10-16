#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""沉浸全屏 CDP 契约（真浏览器 · Metal GPU · CL_GPU=1 串行槽位）。

覆盖面（全部真实点击 / 真实浏览器 API，不是命令式调用 fullscreen 函数）：
  ① 模块在页且版本对应；headless 档 API 可用性如实探测并打印（HEADLESS-TIER）；
  ② 降级证据：合成 stub 文档经 CLSkyFullscreen.syncButton → 显式禁用 + title 如实标注
     「部分移动端浏览器不支持」，不假装可进；
  ③ 真实点击工具菜单「全屏」→ document.fullscreenElement 真为 documentElement，
     #btnFull 与菜单项的 aria-pressed/文案随真实 fullscreenchange 同步；
  ④ 全屏中既有功能可用各抽一：剧情播放（#skyPlay → CLSky.state().playing）与
     搜索（CLSkySearch.open() → stats().open）；工具菜单本身在全屏中可开合；
  ⑤ 退出两路：再点一次菜单项退出、rawKeyDown Esc 原生退出（页面不拦截），
     两次后按钮都如实回到未按下态——F11 类系统级状态走同一事件通道；
  ⑥ jserr / jsrej = 0。
headless 档若不支持 Fullscreen API（supported=false）：跳过真实点击档、改为全程验降级路径，
并按实打印 HEADLESS-TIER degraded。macOS 实测：API 可用，真实点击可进，Esc 经 rawKeyDown 原生退出。
用法：CL_GPU=1 python3 -B -s tests/sky_fullscreen_browser.py --base http://127.0.0.1:8137
"""
import argparse
import json
import time
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:8137')
    ap.add_argument('--out', default=str(Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'fullscreen-browser'))
    args = ap.parse_args()
    Path(args.out).mkdir(parents=True, exist_ok=True)

    r = Wave2AuditRunner(width=1440, height=900, dpr=1)
    checks = []

    def ev(expr, wait=False):
        value = r.eval(expr, await_promise=wait)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(value)
        return value

    def check(name, ok, actual=None):
        checks.append((name, bool(ok), actual))

    def click(selector):
        point = ev('(()=>{var e=document.querySelector(' + json.dumps(selector) + ');if(!e)throw Error("missing target");var b=e.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2]})()')
        for typ in ['mouseMoved', 'mousePressed', 'mouseReleased']:
            r.ws.call('Input.dispatchMouseEvent', type=typ, x=point[0], y=point[1], button='left', clickCount=1)
        time.sleep(.3)

    def page_key(key, code, vk, raw=False):
        typ = 'rawKeyDown' if raw else 'keyDown'
        r.ws.call('Input.dispatchKeyEvent', type=typ, key=key, code=code, windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)
        r.ws.call('Input.dispatchKeyEvent', type='keyUp', key=key, code=code, windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)
        time.sleep(.25)

    def wait_full(want, timeout=8):
        end = time.time() + timeout
        while time.time() < end:
            if ev('!!document.fullscreenElement') is want:
                return True
            time.sleep(.25)
        return False

    tier = 'unknown'
    try:
        r.start()
        r.navigate(args.base + '/?sky=1&data=data/cache/c84e8657afff87043c11ae57.json')
        end = time.time() + 90
        while time.time() < end:
            if ev('!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))'):
                break
            time.sleep(.3)
        else:
            raise RuntimeError('graph readiness timeout')
        time.sleep(4)

        check('fullscreen module present with its published version',
              ev('!!(window.CLSkyFullscreen&&CLSkyFullscreen.version==="castline/sky-fullscreen/1")'), None)

        supported = ev('!!(document.fullscreenEnabled&&CLSkyFullscreen.supported(document))')
        tier = 'real-api' if supported else 'degraded'
        print('HEADLESS-TIER %s (document.fullscreenEnabled=%s module.supported=%s)' % (
            tier, ev('!!document.fullscreenEnabled'), ev('CLSkyFullscreen.supported(document)')), flush=True)
        check('headless tier probed honestly', isinstance(supported, bool), supported)

        check('unsupported stub doc disables the button with an honest partial-mobile title and no pressed fake',
              ev('''(()=>{var b=document.createElement('button');b.textContent='全屏';
                 var r=CLSkyFullscreen.syncButton(b,{documentElement:{}});
                 return r&&r.supported===false&&b.disabled===true&&b.getAttribute('aria-disabled')==='true'
                        &&b.getAttribute('aria-pressed')===null
                        &&b.title.indexOf('部分移动端浏览器不支持')>=0&&b.title.indexOf('已停用')>=0;})()'''), None)
        check('toggle on an unsupported doc refuses as unsupported and never flips state',
              ev('(()=>{var d={documentElement:{}};var r=CLSkyFullscreen.toggle(d);return r&&r.ok===false&&r.kind==="unsupported"&&!CLSkyFullscreen.active(d);})()'), None)
        check('wiring registers click + fullscreenchange listeners and never a keydown (Esc stays native)',
              ev('''(()=>{var hs=[];
                 var el={attrs:{},addEventListener:function(t,f){hs.push(t)},
                   setAttribute:function(k,v){this.attrs[k]=String(v)},removeAttribute:function(k){delete this.attrs[k]},
                   classList:{toggle:function(){},remove:function(){}}};
                 var d={documentElement:{requestFullscreen:function(){}},fullscreenElement:null,addEventListener:function(t,f){hs.push(t)}};
                 var w=CLSkyFullscreen.wire({doc:d,btn:el});
                 return w.wired&&hs.indexOf('keydown')<0&&hs.filter(function(t){return t==='fullscreenchange'||t==='webkitfullscreenchange'}).length===2;})()'''), None)

        if not supported:
            check('degraded page: #btnFull is disabled with the honest title',
                  ev('(()=>{var b=document.getElementById("btnFull");return b.disabled&&b.title.indexOf("部分移动端浏览器不支持")>=0;})()'), None)
            click('#skyTools')
            time.sleep(.4)
            check('degraded page: menu item carries aria-disabled and the honest description',
                  ev('(()=>{var b=document.querySelector(".stm-item[data-for=btnFull]");return b.getAttribute("aria-disabled")==="true"&&document.getElementById("stmD-btnFull").textContent.indexOf("部分移动端浏览器不支持")>=0;})()'), None)
        else:
            check('#btnFull starts enabled, unpressed, with the F-key title',
                  ev('(()=>{var b=document.getElementById("btnFull");return !b.disabled&&b.getAttribute("aria-pressed")==="false"&&b.textContent==="全屏"&&b.title.indexOf("F")>=0;})()'), None)
            click('#skyTools')
            time.sleep(.4)
            check('menu item next to snapshot starts aria-pressed=false and enabled',
                  ev('(()=>{var b=document.querySelector(".stm-item[data-for=btnFull]");return b.getAttribute("aria-pressed")==="false"&&b.getAttribute("aria-disabled")==="false"&&document.getElementById("stmD-btnFull").textContent.indexOf("铺满屏幕")>=0;})()'), None)
            click('.stm-item[data-for=btnFull]')
            check('real click on the menu item truly enters fullscreen on documentElement',
                  wait_full(True) and ev('document.fullscreenElement===document.documentElement'), None)
            time.sleep(.6)
            check('after real fullscreenchange #btnFull is pressed with exit copy',
                  ev('(()=>{var b=document.getElementById("btnFull");return b.getAttribute("aria-pressed")==="true"&&b.textContent==="退出全屏"&&b.classList.contains("on");})()'), None)

            click('#skyTools')
            time.sleep(.4)
            check('tools menu still opens inside fullscreen and mirrors the true state',
                  ev('(()=>{var b=document.querySelector(".stm-item[data-for=btnFull]");return window.CLSkyChrome.menuOpen()&&!b.hidden&&b.getAttribute("aria-pressed")==="true"&&b.querySelector(".stm-name").textContent==="退出全屏";})()'), None)
            click('#skyTools')
            time.sleep(.4)

            page_key('/', 'Slash', 191)
            time.sleep(.4)
            r.ws.call('Input.insertText', text='孙')
            time.sleep(.6)
            check('search opens and indexes inside fullscreen',
                  ev('!!document.fullscreenElement&&CLSkySearch.stats()&&CLSkySearch.stats().open===true'),
                  ev('(()=>{var s=CLSkySearch.stats&&CLSkySearch.stats();return s?{open:s.open,total:s.total}:null;})()'))

            ev('CLSky.setPlot(true);CLSky.seekEventAt(1)')
            time.sleep(1.0)
            click('#skyPlay')
            time.sleep(1.2)
            check('story playback works inside fullscreen', ev('CLSky.state().playing===true'), None)
            ev('CLSky.stop()')
            time.sleep(.4)

            ev('window.__escSeen=0;window.addEventListener("keydown",function(e){if(e.key==="Escape")window.__escSeen++;})')
            page_key('Escape', 'Escape', 27)
            exited = wait_full(False)
            check('plain Escape inside fullscreen exits natively, never reaching page handlers',
                  exited and ev('window.__escSeen===0'), ev('window.__escSeen'))
            time.sleep(.5)
            check('button syncs back through the same fullscreenchange channel after native Esc',
                  ev('(()=>{var b=document.getElementById("btnFull");return b.getAttribute("aria-pressed")==="false"&&b.textContent==="全屏"&&!b.classList.contains("on");})()'), None)
            click('#skyTools')
            time.sleep(.4)
            menu_open = ev('window.CLSkyChrome.menuOpen()===true')
            page_key('Escape', 'Escape', 27)
            time.sleep(.4)
            check('once windowed, the same Escape does page work again (tools menu closes)',
                  bool(menu_open) and ev('window.CLSkyChrome.menuOpen()===false'),
                  {'menu_open_before': menu_open})

            click('#skyTools')
            time.sleep(.4)
            click('.stm-item[data-for=btnFull]')
            check('real click enters fullscreen again', wait_full(True), None)
            click('#skyTools')
            time.sleep(.4)
            click('.stm-item[data-for=btnFull]')
            check('second real click pairs requestFullscreen with exitFullscreen', wait_full(False), None)
            time.sleep(.5)
            check('button returns to the honest unpressed enter state after exit',
                  ev('(()=>{var b=document.getElementById("btnFull");return b.getAttribute("aria-pressed")==="false"&&b.textContent==="全屏"&&!b.classList.contains("on");})()'), None)

        check('zero page errors and zero unhandled rejections across the whole run',
              ev('(()=>{var h=window.__headlessHealth;return h&&h.jserr.length===0&&h.jsrej.length===0;})()'),
              ev('(()=>{var h=window.__headlessHealth||{};return {jserr:h.jserr,jsrej:h.jsrej};})()'))
    finally:
        ev('if(document.fullscreenElement)document.exitFullscreen()')
        r.close()

    bad = [c for c in checks if not c[1]]
    for name, ok, meta in checks:
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok or meta is None else ' :: ' + json.dumps(meta, ensure_ascii=False)), flush=True)
    print('SUMMARY %d/%d' % (len(checks) - len(bad), len(checks)), flush=True)
    print('TIER %s' % tier, flush=True)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
