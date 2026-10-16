#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓「打开后操作不了」的元凶：主线程不终止的计算循环。

思路（沿用项目 E 类教训）：
  1) 起受控 Chrome（默认真 GPU —— 与 accept.sh 浏览器段同路径。
     拿 SwiftShader 的耗时判「产品卡死」是范式错误，见 2026-10-16 记录）
  2) 导航后周期性 Runtime.evaluate('1') 探活：主线程若陷在同步循环里，它**不返回**
  3) 探活超时 ⇒ 立刻 Debugger.pause 中断 V8，读 Debugger.paused 的 callFrames
     ⇒ 直接给出「卡在哪个函数的哪一行」，而不是继续猜
  4) 全程 try/finally 收割 Chrome；**不用外层 alarm 硬砍**（会漏孤儿 → load 顶高 → 后续结论全被带偏）

用法：
  CL_GPU=1 python3 -B -s tools/diag_main_thread.py --url http://127.0.0.1:8000/
  CL_GPU=1 python3 -B -s tools/diag_main_thread.py --url "http://127.0.0.1:8000/?demo=1"
可选：--trigger "CLSky.setPlot(true)"  在探活若干轮后主动触发（把「加载」与「触发」解耦）
     --budget 90（总秒数）· --windowed（不开 headless）
"""
import sys, os, json, time, socket, subprocess, tempfile, shutil, urllib.request, argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tests'))
import headless as H  # 复用 CH / BROWSER_PROFILE_FLAGS / WS / reap_orphans，不重造


def launch(gpu=True, windowed=False):
    port = 9400 + os.getpid() % 500
    ud = os.path.join(tempfile.gettempdir(), 'castline-cdp-%d' % os.getpid())
    w, h = '1440', '900'
    gl = (['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization']
          if gpu else ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    head = [] if windowed else ['--headless=new']
    cmd = [H.CH] + head + gl + H.BROWSER_PROFILE_FLAGS + [
        '--hide-scrollbars', '--window-size=%s,%s' % (w, h),
        '--user-data-dir=' + ud, '--remote-debugging-port=%d' % port,
        '--no-first-run', '--disable-background-networking', 'about:blank']
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tabs = None
    for _ in range(200):
        try:
            tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2).read())
            break
        except Exception:
            if proc.poll() is not None:
                raise SystemExit('chrome exited early')
            time.sleep(0.15)
    if not tabs:
        raise SystemExit('chrome devtools not reachable')
    page = [t for t in tabs if t.get('type') == 'page'][0]
    ws = H.WS(page['webSocketDebuggerUrl'], timeout=8)
    return proc, ws, ud


def probe_alive(ws):
    """探活：主线程空闲 ⇒ 立刻返回；陷在同步循环 ⇒ 不返回，直到 socket 超时。"""
    ws.s.settimeout(3.0)
    try:
        ws.call('Runtime.evaluate', expression='1', returnByValue=True)
        return True
    except Exception:
        return False


def grab_stack(ws, seconds=20.0):
    """阻塞时中断 V8 并读调用栈。Debugger.pause 不要求主线程空闲。"""
    ws.s.settimeout(10.0)
    try:
        ws.call('Debugger.enable')
    except Exception as e:
        print('  Debugger.enable 失败：%r' % (e,))
    ws.send({'id': 90001, 'method': 'Debugger.pause'})
    deadline = time.time() + seconds
    while time.time() < deadline:
        ws.s.settimeout(5.0)
        try:
            m = ws.recv()
        except Exception:
            break
        if m.get('method') == 'Debugger.paused':
            return m.get('params', {}).get('callFrames') or []
    return None


def describe(frames, limit=25):
    out = []
    for f in (frames or [])[:limit]:
        loc = f.get('location') or {}
        out.append({
            'fn': f.get('functionName') or '(anonymous)',
            'url': (f.get('url') or '').split('/')[-1],
            'line': loc.get('lineNumber'),
            'col': loc.get('columnNumber'),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default='http://127.0.0.1:8000/')
    ap.add_argument('--trigger', default='', help='探活若干轮后执行的触发表达式')
    ap.add_argument('--trigger-after', type=int, default=6)
    ap.add_argument('--budget', type=float, default=90.0)
    ap.add_argument('--windowed', action='store_true')
    ap.add_argument('--no-gpu', action='store_true')
    a = ap.parse_args()

    H.reap_orphans()
    proc, ws, ud = launch(gpu=not a.no_gpu, windowed=a.windowed)
    t0 = time.time()
    verdict = {'url': a.url, 'blocked': False, 'stack': None, 'elapsed': None,
               'note': None, 'aliveProbes': 0}
    try:
        ws.call('Page.enable')
        ws.call('Runtime.enable')
        try:
            ws.call('Debugger.enable')
        except Exception:
            pass
        ws.call('Page.navigate', url=a.url)
        print('navigated -> %s' % a.url, flush=True)

        triggered = False
        i = 0
        while time.time() - t0 < a.budget:
            i += 1
            alive = probe_alive(ws)
            el = time.time() - t0
            if not alive:
                verdict['blocked'] = True
                verdict['elapsed'] = round(el, 1)
                verdict['triggered'] = triggered
                print('BLOCKED at %.1fs（探活 %d 次后）· 抓栈中…' % (el, verdict['aliveProbes']), flush=True)
                frames = grab_stack(ws)
                verdict['stack'] = describe(frames)
                if not frames:
                    verdict['note'] = 'Debugger.pause 未返回 callFrames（可能是加载阶段就绪即停摆）'
                break
            verdict['aliveProbes'] += 1
            if i % 4 == 0:
                print('  alive %.1fs（探活 %d）' % (el, verdict['aliveProbes']), flush=True)
            if a.trigger and not triggered and i >= a.trigger_after:
                print('  trigger: %s' % a.trigger, flush=True)
                ws.s.settimeout(5.0)
                try:
                    ws.call('Runtime.evaluate', expression=a.trigger, returnByValue=True)
                except Exception as e:
                    print('  trigger 异常（可能已卡）：%r' % (e,))
                triggered = True
            time.sleep(0.4)
        else:
            verdict['note'] = '预算内未阻塞（%d 次探活全部返回）' % verdict['aliveProbes']
        print(json.dumps(verdict, ensure_ascii=False, indent=1), flush=True)
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        shutil.rmtree(ud, ignore_errors=True)
        print('cleaned: chrome killed, %s removed' % ud, flush=True)


if __name__ == '__main__':
    main()
