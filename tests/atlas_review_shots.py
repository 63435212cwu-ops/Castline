#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/atlas_review_shots.py · R2-G 第 3 条：一键产出评审用真 GPU 截图
（mystic-refactor-plan/grand-atlas-plan/units/R2-G.md，R3-E 修正）

不是断言/门禁脚本——这个文件只负责「产出图」，供 R2-H（艺术总监评审）与主控终审用肉眼看。
参考 /tmp/v70_final.py 的写法（第一轮主控终审用过的同款截图器）：同一个页面会话里按顺序推进
六个状态，累计截图，不重复导航（导航一次，状态在同一份 DOM/3D 场景上滚动切换，跟真实用户的
操作路径一致，而不是各自从零加载的页面）：

  01 星座态（constellation）  —— 刚加载，星图默认视图，什么都没点
  02 剧情态（disc）           —— CLPlot.toggle() 打开剧情星盘（3D 圆盘 + 事件时间环）
  03 展卷态（score）          —— CLAtlasStage.open() 展开剧情线谱，并 setFocus 一条支线
                                  （复现 评分聚焦的标准取景，
                                  好让 R2-H 能对比 R2-B 这轮修的聚焦可见性）
  04 右坞态（dock）           —— 收卷回星盘，__cl.select() 选中一个角色，打开角色资料坞
  05 雷达独立态（radar）      —— 右坞滚到 #s-radar 顶部（R2-H §六 点名的缺口：雷达从未有
                                  独立全屏截图，只能从 dock 侧栏管窥）
  06 足迹独立态（line）       —— 右坞滚到 #s-line 顶部（CLAtlasFootprint 剧情线）

R3-E 对 R2-H §四·4.2 指出的问题的修正：首轮 constellation 只固定 sleep(1.2s) 就截图，实际
截到的是 js/hud/arcana.js 的入场符阵动画（`playSigil()`，1.75s 展开 + 0.9s 淡出才移除
`#clSigil`，其上的文案正是「CASTLINE · ARCANUM · 正在展开这部作品的星象」）而不是最终星座画面。
修正为动态等待：CLScene 就绪（`window.CLScene.current` 存在）+ 入场符阵已消失（`#clSigil`
不在 DOM 里）+ 阵营光晕徽记已出现（`.cl-camp-halo__badge`，CONTRACT §2.1 冻结类名，来源
js/core/scene-camp-halo.js），三者都满足才截图；5s 内不满足就按上限截（如实记录哪一项没等到，
不静默假装等到了）。

真 GPU：--use-angle=metal（本机上 swiftshader 软渲染看不见圆盘的镜面材质，之前 U09 用
swiftshader 是因为那边只做 DOM 断言、不需要看画面）；deviceScaleFactor=2 对齐 v70_final.py
的取景习惯（视网膜分辨率截图，细节更清楚）。

命名：/tmp/castline-shots/review/<态>-<视口>.png，如 /tmp/castline-shots/review/constellation-1440x900.png。
三视口 × 六态 = 18 张（12 张原有状态 + 6 张雷达/足迹独立截图，对齐任务书「12+6」）。
每张图额外写一行 JSON 元数据（状态/视口/等待方式/等待耗时/状态标记）到
/tmp/castline-shots/review/index.json（JSON Lines，一行一张图，覆盖重写，不追加旧的）。

用法：python3 -s tests/atlas_review_shots.py
"""
import base64
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'review')
INDEX_PATH = os.path.join(OUT_DIR, 'index.json')
sys.path.insert(0, HERE)
import headless  # noqa: E402
headless.reap_orphans = lambda: None

VIEWPORTS = [(1440, 900), (820, 1180), (390, 844)]
QUERY = 'data=data/sample-saga.json&probe=1&pump=1&warm=60'

# R3-E：星座态截图此前固定 sleep(1.2s) 截到的是入场符阵动画中间帧（js/hud/arcana.js 的
# `#clSigil`，文案「正在展开这部作品的星象」），不是最终画面——见文件头注。改为动态等待
# CLScene 就绪 + 符阵已消失 + 阵营光晕徽记出现，三者齐了才算「星座态真正就绪」。
CONSTELLATION_READY_EXPR = """(function(){
  try {
    var sceneReady = !!(window.CLScene && window.CLScene.current);
    var sigilGone = !document.getElementById('clSigil');
    var badge = !!document.querySelector('.cl-camp-halo__badge');
    return { ready: sceneReady && sigilGone && badge, sceneReady: sceneReady, sigilGone: sigilGone, badge: badge };
  } catch (e) { return { ready: false, why: String(e && e.stack || e) }; }
})()"""
CONSTELLATION_WAIT_TIMEOUT = 5.0

# 每一步：{'name', 'expr'（执行的 JS 表达式或 None）, 'wait'（'poll'|'fixed'）, ...}。
# None 表示不执行任何 JS，只是在当前状态截图。累计推进，后一步建立在前一步的 DOM 状态上。
STEPS = [
    {'name': 'constellation', 'expr': None, 'wait': 'poll',
     'poll_expr': CONSTELLATION_READY_EXPR, 'poll_timeout': CONSTELLATION_WAIT_TIMEOUT},
    {'name': 'disc', 'expr': "(function(){ try { return {ok:true, on: window.CLPlot.toggle()}; } "
                              "catch(e){ return {ok:false, why:String(e)}; } })()",
     'wait': 'fixed', 'wait_s': 1.8},
    {'name': 'score', 'expr': "(function(){ try { window.CLAtlasStage.open(); "
                               "if (window.CLAtlasStage.setFocus) window.CLAtlasStage.setFocus({lineId:'T5'}); "
                               "return {ok:true}; } catch(e){ return {ok:false, why:String(e&&e.stack||e)}; } })()",
     'wait': 'fixed', 'wait_s': 1.8},
    {'name': 'dock', 'expr': "(function(){ try { window.CLAtlasStage.close(); "
                              "if (window.__cl && typeof window.__cl.select === 'function') window.__cl.select('姜明肃'); "
                              "return {ok:true}; } catch(e){ return {ok:false, why:String(e&&e.stack||e)}; } })()",
     'wait': 'fixed', 'wait_s': 2.0},
    # R3-E 新增第 2 条：雷达独立截图——选中角色后滚右坞到 #s-radar 顶部
    # （CONTRACT §2.1 未冻结 dockToc 结构，但 js/app.js:2791 固定用 data-to="s-radar" 生成锚点；
    #   直接改 scrollTop 而不点 dockToc 的 <a>，避免依赖它默认 smooth 滚动的时长不确定）。
    {'name': 'radar', 'expr': "(function(){ try { "
                               "var body = document.getElementById('dockBody'), sec = document.getElementById('s-radar'); "
                               "if (!body || !sec) return {ok:false, why:'missing #dockBody or #s-radar'}; "
                               "body.style.scrollBehavior = 'auto'; body.scrollTop = Math.max(0, sec.offsetTop - 6); "
                               "return {ok:true}; } catch(e){ return {ok:false, why:String(e&&e.stack||e)}; } })()",
     'wait': 'fixed', 'wait_s': 0.6},
    # 再截 #s-line（足迹，CLAtlasFootprint）一张
    {'name': 'line', 'expr': "(function(){ try { "
                              "var body = document.getElementById('dockBody'), sec = document.getElementById('s-line'); "
                              "if (!body || !sec) return {ok:false, why:'missing #dockBody or #s-line'}; "
                              "body.style.scrollBehavior = 'auto'; body.scrollTop = Math.max(0, sec.offsetTop - 6); "
                              "return {ok:true}; } catch(e){ return {ok:false, why:String(e&&e.stack||e)}; } })()",
     'wait': 'fixed', 'wait_s': 0.6},
]


def _ensure_out_dir():
    os.makedirs(OUT_DIR, exist_ok=True)


class Session:
    """真 GPU（--use-angle=metal）截图会话，一个视口一条 Chrome 生命周期。"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ud = tempfile.mkdtemp(prefix='atlas-review-')
        self.proc = None
        self.ws = None

    def start(self):
        cmd = [headless.CH, '--headless=new', '--use-angle=metal',
               '--window-size=%d,%d' % (self.w, self.h), '--user-data-dir=' + self.ud,
               '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking', 'about:blank']
        self.proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      start_new_session=True)
        tabs = None
        for _ in range(120):
            try:
                port = int(open(os.path.join(self.ud, 'DevToolsActivePort')).read().splitlines()[0])
                tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2).read())
                break
            except Exception:
                time.sleep(0.1)
        if not tabs:
            raise RuntimeError('devtools not reachable for %dx%d' % (self.w, self.h))
        page = [t for t in tabs if t.get('type') == 'page'][0]
        self.ws = headless.WS(page['webSocketDebuggerUrl'], timeout=40)
        self.ws.call('Runtime.enable')
        self.ws.call('Page.enable')
        # deviceScaleFactor=2：对齐 /tmp/v70_final.py 的取景习惯，细节更清楚，供肉眼评审。
        self.ws.call('Emulation.setDeviceMetricsOverride', width=self.w, height=self.h, deviceScaleFactor=2, mobile=False)

    def close(self):
        try:
            if self.ws:
                self.ws.call('Browser.close')
        except Exception:
            pass
        try:
            if self.proc and self.proc.poll() is None:
                os.killpg(self.proc.pid, signal.SIGTERM)
        except Exception:
            pass
        shutil.rmtree(self.ud, ignore_errors=True)

    def eval(self, expr, await_promise=False):
        r = self.ws.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=await_promise)
        if r.get('exceptionDetails'):
            return {'__evalError': True, 'detail': str(r.get('exceptionDetails'))}
        res = r.get('result', {})
        if 'value' in res:
            return res['value']
        return None

    def navigate(self, url):
        self.ws.call('Page.navigate', url=url)

    def wait_ready(self, timeout=60):
        t0 = time.time()
        expr = "!!(window.__cl && window.CLPlot && window.CLPlot.tree && window.CLPlot.tree() && window.CLPlot.tree().ok)"
        while time.time() - t0 < timeout:
            v = self.eval(expr)
            if v is True:
                return True
            time.sleep(0.25)
        return False

    def wait_until(self, poll_expr, timeout_s, poll_interval=0.15):
        """轮询 poll_expr（须返回 {ready: bool, ...诊断字段}）直到 ready 或超时。
        返回 (ready, elapsed_s, last_value)：last_value 是最后一次轮询的完整返回值，
        超时时用它如实记录「等到哪一步」，不是笼统的 False。"""
        t0 = time.time()
        last = None
        while True:
            last = self.eval(poll_expr)
            if isinstance(last, dict) and last.get('ready'):
                return True, time.time() - t0, last
            elapsed = time.time() - t0
            if elapsed >= timeout_s:
                return False, elapsed, last
            time.sleep(poll_interval)

    def shot(self, path):
        data = self.ws.call('Page.captureScreenshot', format='png')
        with open(path, 'wb') as f:
            f.write(base64.b64decode(data['data']))
        return path

    def wait_final_frame(self, timeout=6):
        """Require two consecutive settled samples after the resize/fit handshake.

        A selected character intentionally keeps its group expanded. Record that
        exception explicitly; never rewrite the scene's raw settled flag.
        """
        start, stable, last = time.monotonic(), 0, None
        while time.monotonic() - start < timeout:
            last = self.eval("""(function(){
              if(!window.__cl || !__cl.scene || !__cl.scene.step || !__cl.scene.settleT)
                return {ready:false,why:'scene probe unavailable'};
              __cl.scene.step(10);
              var st=__cl.scene.settleT(), L=window.CLOrbit3DLayer;
              var f=L && L.framing ? L.framing() : null;
              var dock=!!document.body.classList.contains('focus');
              var expandedFocus=dock && st.nodeAnim===false && st.cam===false && st.crownSep===false;
              return {ready:!!(st.settled || expandedFocus) && !!f && f.animating===false,
                scene:st, focusExpansionException:!st.settled && expandedFocus,
                framing:f, scale:f ? f.s : null};
            })()""")
            stable = stable + 1 if isinstance(last, dict) and last.get('ready') else 0
            if stable >= 2:
                return True, last
            time.sleep(0.1)
        return False, last


def run_viewport(w, h):
    size_tag = '%dx%d' % (w, h)
    sess = Session(w, h)
    result = {'size': size_tag, 'steps': []}
    try:
        sess.start()
        sess.navigate('http://127.0.0.1:8000/?%s' % QUERY)
        ready = sess.wait_ready(60)
        result['ready'] = ready
        if not ready:
            result['status'] = 'FAIL'
            result['why'] = '页面未就绪（60s 超时），跳过这个视口的全部截图'
            return result
        detect = sess.eval("""(function(){
          return { CLPlot: !!window.CLPlot, CLAtlasStage: !!window.CLAtlasStage,
            CLAtlasModel: !!window.CLAtlasModel, CLAtlasScore: !!window.CLAtlasScore };
        })()""")
        result['detect'] = detect
        for step in STEPS:
            name, expr = step['name'], step.get('expr')
            step_r = {'state': name}
            if expr:
                r = sess.eval(expr)
                step_r['jsResult'] = r
                if isinstance(r, dict) and (r.get('__evalError') or r.get('ok') is False):
                    step_r['ok'] = False
                else:
                    step_r['ok'] = True
            else:
                step_r['ok'] = True
            if step['wait'] == 'poll':
                poll_ok, elapsed, last = sess.wait_until(step['poll_expr'], step['poll_timeout'])
                step_r['waitMode'] = 'poll'
                step_r['waitMs'] = round(elapsed * 1000)
                step_r['waitOk'] = poll_ok
                step_r['waitDetail'] = last
                if not poll_ok:
                    step_r['ok'] = False
                    step_r['why'] = ('等到 %ds 上限仍未就绪：%s' % (int(step['poll_timeout']), last))
            else:
                wait_s = step['wait_s']
                time.sleep(wait_s)
                step_r['waitMode'] = 'fixed'
                step_r['waitMs'] = round(wait_s * 1000)
            # 帧泵（R4-REV 修正 · 2026-09-20）：pump=1 时 app.js 用 `noRaf:true` 建场景，rAF 不自转，
            # HUD 状态机（plot-deck 的 tick 挂在 CLArcana.update 上、halo/overlay 同理）**只在帧上推进**。
            # 截图前必须真泵帧，否则牌阵断态条永远停在「首帧判定」上：实测 review 图里
            # 「〔部分未全 · 泳道溢出〕」恒现，而同一页面泵帧后 CLPlotDeck.stats().state
            # 立刻由 degraded 翻 ready、`.cl-degraded-tag` 全部消失（CLOrbit3DAtlas.conserved 本就 true）。
            #
            # 原实现的 `window.__cl.pump(30)` 是**空洞调用**：tests/app-probes.js 的 `window.__cl` api 表
            # 从未暴露 `pump` 键（只有 scene/graph/select/mount/state/... ），`try{}catch(e){}` 把它静默吞掉
            # ⇒ 这条「补泵」从落地起一次都没生效过，而注释却宣称它做了事（静默失效 + 写死的成功文案）。
            #
            # 现改用实测存在的 `__cl.scene.step(n)` 泵到**场景自报稳定**为止
            # （`__cl.scene.settleT().settled`，判据 = 节点动画/相机 tween/晶冠分离均已走完且群组展开 ≤0.5），
            # 而不是拍脑袋泵固定帧数 —— 否则构图会随「泵了几帧」漂移，跨轮不可比。
            # 「泵是否真跑到、是否真稳定」记进 step_r 与 index.json：泵不到或没稳定就判该步 ok=False（宁可变红，不许静默）。
            pump_frames, pump_err, pump_settled = 0, None, None
            for _p in range(4):
                _r = sess.eval(
                    "(function(){try{"
                    "if(!(window.__cl&&__cl.scene&&typeof __cl.scene.step==='function'))"
                    "return {frames:-1,why:'no __cl.scene.step'};"
                    "var n=0,st=null;"
                    "while(n<180){__cl.scene.step(10);n+=10;"
                    "try{st=__cl.scene.settleT();}catch(e){st=null;}"
                    "if(st&&st.settled)break;}"
                    "return {frames:n,settled:!!(st&&st.settled),"
                    "nodeAnim:(st&&st.nodeAnim),cam:(st&&st.cam),crownSep:(st&&st.crownSep),groupX:(st&&st.groupX),"
                    "sinceFocus:(st&&st.sinceFocus)||null};"
                    "}catch(e){return {frames:-1,why:String(e)};}})()")
                if isinstance(_r, dict) and (_r.get('frames') or 0) > 0:
                    pump_frames += int(_r['frames'])
                    pump_settled = bool(_r.get('settled'))
                    # settleT 的 `groupX <= 0.5` 一项目的是「群组展开动画是否还在跑」，但**聚焦/选中角色时
                    # 群组是故意保持展开的**（实测：dock 态三视口泵满 720 帧 groupX 仍 > 0.5 而
                    # nodeAnim/cam/crownSep 早已全 false）—— 故判据取「三项动画走完」，groupX 只记录不判死。
                    _anim_done = (_r.get('nodeAnim') is False and _r.get('cam') is False and _r.get('crownSep') is False)
                    if _anim_done:
                        pump_settled = True
                    if pump_settled:
                        break
                elif pump_err is None:
                    pump_err = _r
                time.sleep(0.15)
            # R5-F（主控 2026-09-21）：圆盘取景是 setTimeout 重试链 + 墙钟过渡，pump 模式下 rAF 不转，
            # 帧泵完成后再触发一次 resize（走 syncSafeArea→syncDiscFit），等过渡落定再泵帧让投影落到 DOM。
            try:
                _f = sess.eval(
                    "(function(){try{window.dispatchEvent(new Event('resize'));return true;}catch(e){return String(e);}})()")
                for _q in range(12):
                    time.sleep(0.25)
                    _f = sess.eval(
                        "(function(){try{var L=window.CLOrbit3DLayer;if(!L||!L.framing)return {na:true};"
                        "__cl.scene.step(6);var f=L.framing();return {has:!!f.last,anim:!!f.animating,s:f.s};}catch(e){return {err:String(e)};}})()")
                    if not isinstance(_f, dict) or _f.get('na') or _f.get('err'): break
                    if _f.get('has') and not _f.get('anim'):
                        sess.eval("(function(){try{__cl.scene.step(20);}catch(e){}})()"); break
                step_r['framing'] = _f
            except Exception as _e:
                step_r['framing'] = {'err': str(_e)}
            final_ok, final_frame = sess.wait_final_frame()
            step_r['finalFrame'] = final_frame
            step_r['finalSettled'] = final_ok
            step_r['scale'] = final_frame.get('scale') if isinstance(final_frame, dict) else None
            if not final_ok:
                step_r['ok'] = False
                step_r['why'] = '二次落定失败（6s）：%r' % (final_frame,)
            step_r['pumpFrames'] = pump_frames
            step_r['pumpSettled'] = pump_settled
            step_r['pumpErr'] = pump_err
            if pump_frames <= 0:
                step_r['ok'] = False
                step_r['why'] = '帧泵未生效（__cl.scene.step 不可用：%r）—— 本图为未推进帧的静止态，不可据以判态' % (pump_err,)
            elif not pump_settled:
                step_r['ok'] = False
                step_r['why'] = ('泵了 %d 帧后场景仍未自报稳定（settleT().settled=false，上限 720 帧）'
                                 '—— 本图为动画中途帧，构图不可跨轮比较' % (pump_frames,))
            path = os.path.join(OUT_DIR, '%s-%s.png' % (name, size_tag))
            sess.shot(path)
            step_r['path'] = path
            result['steps'].append(step_r)
        result['status'] = 'OK' if all(s.get('ok') for s in result['steps']) else 'PARTIAL'
        return result
    except Exception as e:
        result['status'] = 'FAIL'
        result['why'] = 'runner 异常：%r' % (e,)
        return result
    finally:
        sess.close()


def _write_index(results):
    """每张图一行 JSON 元数据（状态/视口/等待方式/等待耗时/是否就绪）到
    /tmp/castline-shots/review/index.json（JSON Lines，本次运行整份覆盖重写）。"""
    lines = []
    for r in results:
        size = r.get('size')
        for s in r.get('steps', []):
            lines.append(json.dumps({
                'state': s.get('state'),
                'viewport': size,
                'path': s.get('path'),
                'ok': bool(s.get('ok')),
                'waitMode': s.get('waitMode'),
                'waitMs': s.get('waitMs'),
                'waitOk': s.get('waitOk'),
                'pumpFrames': s.get('pumpFrames'),
                'pumpSettled': s.get('pumpSettled'),
                'pumpErr': s.get('pumpErr'),
                'framing': s.get('framing'),
                'scale': s.get('scale'),
                'finalSettled': s.get('finalSettled'),
                'finalFrame': s.get('finalFrame'),
                'why': s.get('why'),
            }, ensure_ascii=False))
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + ('\n' if lines else ''))
    return len(lines)


def main():
    _ensure_out_dir()
    results = []
    for (w, h) in VIEWPORTS:
        r = run_viewport(w, h)
        results.append(r)
        print('--- %s : %s ---' % (r.get('size'), r.get('status')))
        if r.get('why'):
            print('   why:', r.get('why'))
        for s in r.get('steps', []):
            flag = 'OK ' if s.get('ok') else 'ERR'
            wait_note = '' if s.get('waitMode') != 'poll' else (' waitMs=%s waitOk=%s' % (s.get('waitMs'), s.get('waitOk')))
            extra = '' if s.get('ok') else (' %s' % (s.get('why') or s.get('jsResult')))
            pump_note = ' pump=%s settled=%s' % (s.get('pumpFrames'), s.get('pumpSettled'))
            print('   [%s] %s -> %s%s%s%s' % (flag, s.get('state'), s.get('path'), wait_note, pump_note, extra))
    _pump_bad = [s for r in results for s in r.get('steps', []) if not (s.get('pumpFrames') or 0) > 0]
    if _pump_bad:
        print('[WARN] 有 %d 步未推进任何帧（pumpFrames<=0）—— 这些图是静止态，判态前必须查明原因'
              % (len(_pump_bad),))
    produced = [s.get('path') for r in results for s in r.get('steps', []) if s.get('path') and os.path.isfile(s.get('path'))]
    n_index = _write_index(results)
    print('ATLAS_REVIEW_SHOTS produced=%d index_lines=%d dir=%s' % (len(produced), n_index, OUT_DIR))
    fail = [r for r in results if r.get('status') != 'OK']
    return 1 if fail or len(produced) != 18 else 0


if __name__ == '__main__':
    sys.exit(main())
