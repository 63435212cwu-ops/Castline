#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/atlas_browser.py · U09 atlas-acceptance CDP 三视口验收
（mystic-refactor-plan/grand-atlas-plan/CONTRACT.md §2 · units/U09.md）

自建 CDP Chrome（不动 headless.py 里跑着的任何东西、不杀 :8000），三视口
1440x900 / 820x1180 / 390x844 各跑一条任务链：

  打开 sample-saga（?data=data/sample-saga.json&probe=1&pump=1）
  → CLPlot.toggle()（既有剧情星盘层）
  → CLAtlasStage.open()（U04 展卷控制器）
  → 断言 score 行数（+ aggregate）== model.conservation.rawThreads
  → 点第一条支线行头 → 断言线级阅读出现且含双长度文本（跨 N 章 · M 事）
  → 点一个事件刻度 → 事件聚焦/事件卡出现
  → Esc → CLAtlasStage.close()
  → 断言隐藏面板（#plotTextPanel / .cp-wrap）恢复、disc 焦点（CLPlotOrbit 的
    selectedEvent）未变
  → 断言页面级无横向溢出（documentElement.scrollWidth <= innerWidth+1，score 容器
    内部允许 overflow-x:auto 横滚）、score 容器确有内容（scrollWidth>=clientWidth）

U01(atlas-model)/U02(atlas-score)/U04(atlas-stage) 与本单元并行施工，落地顺序不定，
所以每一步先探测对应 window.CL* 是否存在：
  - 三者都在 → 走完整链路（上面全部步骤）。
  - CLAtlasStage 缺席但 CLAtlasModel + CLAtlasScore 都在 → 用
    tests/fixtures/atlas-browser-synth.js 的 small() 构造好的 tree 直接喂
    CLAtlasModel.build，把结果 mount 到临时 host，只跑「score 部分」（行数守恒 +
    双长度文本），不模拟 stage 的开合/锚点动画（那是 U04 的契约面）。
  - 连 CLAtlasModel 都不在 → 整个视口输出 SKIP（缺席清单写进 why），不产出假绿。

CONTRACT.md §2.1（2026-09-20 新增，主控冻结）固定了 DOM 选择器契约，本 runner 严格
照抄，不再自行猜测：
  - 数据行：`[role="row"][data-line-id]`（代次分组头 `.cl-score-genhead` 也带
    role=row 但不带 data-line-id，必须排除，否则会把分组头也数成线——2026-09-20
    实测踩过：22 线的 sample-saga 数出 27，多出的 5 正是分组头数）。
  - 聚合/折叠展开按钮：`[data-more]`。当前 atlas-score.js 里它只用在单行内的参与者
    「+N」溢出芯片（人数聚合，不是线聚合），所以扫描时排除嵌在某一行内部的
    data-more，只把不属于任何行的部分计入 aggregateExtra——现状恒为 0，是如实反映
    实现，不是我发明的数字，向前兼容「以后线级聚合也复用这个属性」的可能。
  - 事件刻度：`[data-event-idx]`（不是旧 plot-hud 的 `[data-ev]`，v1 曾用错这个属性名，
    在真实 stage 存在时会把「模块没问题」误判成「找不到刻度」的假 FAIL）。
  - Stage 根：`#atlasStage`。所有查询都限定在这个根节点内——不这样做会把旧
    plot-hud / orbit3d 里同样带 role=row / data-event-idx 的历史 DOM 一起算进来。
  - 「线级阅读出现」走文本模式探测（stage 内文案含「跨…章」「…事」双长度）；
    「事件聚焦/事件卡出现」用 U02 直接在 js/atlas/atlas-score.js:409-416/581-605 源码
    注释里点名给 U09 的选择器：容器 `.cl-score-eventcard`（隐藏态加 `.is-hidden`）、
    内容 `.cl-score-eventcard-body`、关闭按钮 `[data-eventcard-close]`；同时保留
    `.cl-score-tick[data-event-idx].is-focused` 的聚焦态判定做兜底，两者任一为真即通过。

另跑 3000 事件压力（run_stress）：注入 synth.stress()，量 mount 首绘 ms 与 30 次
step(ms) 的平均帧时；R10 只对 stress 场景要求「不崩、可滚动」，数字仅供参考。

用法：python3 -s tests/atlas_browser.py
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
OUT_DIR = os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'atlas')
sys.path.insert(0, HERE)
import headless  # noqa: E402
headless.reap_orphans = lambda: None

SYNTH_PATH = os.path.join(HERE, 'fixtures', 'atlas-browser-synth.js')
VIEWPORTS = ['1440x900', '820x1180', '390x844']
LARGE_SAMPLE_QUERY = 'data=data/cache/2ef47b2ecaa99a67352091d5.json&probe=1&pump=1'

REQUIRED_GLOBALS = ('CLAtlasModel', 'CLAtlasScore', 'CLAtlasStage')

# R2-G · 2026-09-20：`grep -n "is-focus\|focus" js/atlas/atlas-score.js` 核实——聚焦态类名
# 是 `is-focused`（不是任务书原文猜的 `is-focus`），行焦点（focusRow）与刻度焦点（focusEvent）
# 共用同一个类名，clearFocusClasses() 也按这个类名清除。此刻 R2-B（js/atlas/atlas-score.js 的
# owner）仍在并行施工 setFocus 的可见化（任务书 R2-B.md 第 3 条：目标行提亮 + 其余行
# opacity .45 + 平滑滚入），若类名改了以实际 DOM 为准，
# 到时候只需要改这一个常量。
FOCUS_CLASS = 'is-focused'
# R2-B.md 第 3 条原文「其余行 opacity .45」，CONTRACT/任务书泛指「< .6」，用后者做门槛更宽松、
# 不会因为 R2-B 最终调值到 .5 还是 .45 而误判。
DIM_OPACITY_MAX = 0.6


def _ensure_out_dir():
    os.makedirs(OUT_DIR, exist_ok=True)


class Session:
    """一个视口一条 Chrome 生命周期，参考 tests/plot_overview_browser.py 的 run()。"""

    def __init__(self, size):
        self.size = size
        w, h = map(int, size.split('x'))
        self.w, self.h = w, h
        self.ud = tempfile.mkdtemp(prefix='atlas-accept-')
        self.proc = None
        self.ws = None

    def start(self):
        cmd = [headless.CH, '--headless=new', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
               '--window-size=%s,%s' % (self.w, self.h), '--user-data-dir=' + self.ud,
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
            raise RuntimeError('devtools not reachable for ' + self.size)
        page = [t for t in tabs if t.get('type') == 'page'][0]
        self.ws = headless.WS(page['webSocketDebuggerUrl'], timeout=40)
        self.ws.call('Runtime.enable')
        self.ws.call('Page.enable')
        self.ws.call('Emulation.setDeviceMetricsOverride', width=self.w, height=self.h, deviceScaleFactor=1, mobile=False)

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
        # exceptionDetails 是「真的抛了」；result.type == 'undefined' 是「合法地求值成 undefined」
        # （IIFE 文件求值本就返回 undefined）——早期实现把两者都当错误，把正常注入误报成
        # inject_errors，2026-09-20 实测发现后改成只认 exceptionDetails。
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
        expr = "!!(window.__cl && window.__cl.graph && window.__cl.graph())"
        while time.time() - t0 < timeout:
            v = self.eval(expr)
            if v is True:
                return True
            time.sleep(0.25)
        return False

    def shot(self, name):
        _ensure_out_dir()
        path = os.path.join(OUT_DIR, 'accept-%s-%s.png' % (self.size, name))
        data = self.ws.call('Page.captureScreenshot', format='png')
        with open(path, 'wb') as f:
            f.write(base64.b64decode(data['data']))
        return path


DETECT_EXPR = """(function(){
  return { CLPlot: !!window.CLPlot, CLAtlasModel: !!window.CLAtlasModel,
    CLAtlasScore: !!window.CLAtlasScore, CLAtlasStage: !!window.CLAtlasStage,
    CLAtlasGlyphs: !!window.CLAtlasGlyphs,
    CLPlotOrbit: !!window.CLPlotOrbit, CLTest: !!window.__cl };
})()"""

# HOST（主控）尚未把 js/atlas/*.js 接进 index.html 前，纯走页面导航永远探测不到
# window.CLAtlas*——那是接线权限问题，不是模块本身的问题（见 CONTRACT §3：index.html
# 只归主控）。这里在探测到全局缺席、但对应文件已经落地时，直接把源码注入当前页面
# （只读文件、不改宿主），让 U01/U02/U04 一落地就能拿真模块跑真链路；一旦 HOST 真正
# 接线，注入会是幂等的空操作（重复定义同一个 window.CL* namespace，无副作用）。
INJECT_ORDER = [
    ('CLAtlasGlyphs', os.path.join(ROOT, 'js', 'atlas', 'atlas-glyphs.js')),
    ('CLAtlasModel', os.path.join(ROOT, 'js', 'atlas', 'atlas-model.js')),
    ('CLAtlasScore', os.path.join(ROOT, 'js', 'atlas', 'atlas-score.js')),
    ('CLAtlasStage', os.path.join(ROOT, 'js', 'atlas', 'atlas-stage.js')),
]


def inject_missing_modules(sess, detect):
    """把已落地但页面还没加载的 js/atlas/*.js 源码注入进当前页；返回 (detect2, injected:list, errors:list)。
    HOST 接线前的**唯一**变通手段——只读文件源码，不写宿主任何文件。"""
    injected, errors = [], []
    for gname, path in INJECT_ORDER:
        if detect.get(gname):
            continue
        if not os.path.isfile(path):
            continue
        src = open(path, encoding='utf-8').read()
        r = sess.eval(src)
        if isinstance(r, dict) and r.get('__evalError'):
            errors.append({'global': gname, 'file': os.path.basename(path), 'error': r.get('detail')})
        else:
            injected.append(gname)
    detect2 = sess.eval(DETECT_EXPR)
    return detect2, injected, errors


def run_full_chain(sess, screenshots, ce=None):
    """三模块齐全时的完整任务链。返回 (ok:bool, steps:list, why:str)。

    ce（counterexample，仅供 --ce 反例演示用，默认 None 不影响正常验收）：
      - 'rawthreads'：故意把「守恒真值」加一，证明 score-rows-conservation 真的会因为数字
        对不上而 FAIL，不是摆设。
      - 'missing-stage'：真值建好后立刻删掉 window.CLAtlasStage 再调 open()，证明当 U04 模块
        缺席/损坏时 stage-open 会如实 FAIL，不会因为前面探测到过它就假装后面还在。
      - 'hide-row'：点击支线行之前把该行节点从 DOM 里摘掉，证明 line-reading 断言找不到
        被隐藏的行时会如实 FAIL，不是靠 textContent 兜底蒙混过关。
    """
    steps = []

    def rec(name, ok, extra=None):
        steps.append({'step': name, 'ok': ok, 'extra': extra})
        return ok

    # 事先在页面里独立建一份 model（不依赖 stage 内部状态），作为「守恒真值」来源。
    model_expr = """(function(){
      try {
        var G = window.__cl.graph(); var tree = window.CLPlot.tree();
        if (!tree || !tree.ok) return {ok:false, why:'CLPlot.tree() 未就绪或 !ok'};
        var model = window.CLAtlasModel.build(tree, G);
        var branch = null;
        for (var i=0;i<(model.lines||[]).length;i++) if (model.lines[i].kind==='branch') { branch = model.lines[i]; break; }
        return {ok:true, rawThreads: model.conservation.rawThreads, linesLen: model.lines.length,
          branchId: branch ? branch.id : null, branchName: branch ? branch.name : null};
      } catch(e){ return {ok:false, why:'build 抛异常：'+String(e && e.stack || e)}; }
    })()"""
    ground = sess.eval(model_expr)
    if not isinstance(ground, dict) or not ground.get('ok'):
        rec('build-ground-truth-model', False, ground)
        return False, steps, 'CLAtlasModel.build(CLPlot.tree(), graph()) 失败：%s' % (ground if not isinstance(ground, dict) else ground.get('why'))
    rec('build-ground-truth-model', True, ground)

    if ce == 'rawthreads':
        # 反例①：故意把守恒真值改错，后面 score-rows-conservation 拿真实 DOM 行数去比这个错的
        # 数字，必须对不上而 FAIL——证明这条断言不是「永远绿」的摆设。
        ground = dict(ground)
        ground['rawThreads'] = (ground.get('rawThreads') or 0) + 1

    # focus before-open：disc 选中的事件（用于收卷后核对「disc 焦点未变」）
    focus_before = sess.eval("(function(){var o=window.CLPlotOrbit&&window.CLPlotOrbit.get&&window.CLPlotOrbit.get();return o?o.selectedEvent:null;})()")

    if ce == 'missing-stage':
        # 反例②：真值建好后立刻把 CLAtlasStage 删掉再开卷——模拟「本该在但不在/坏掉」，
        # open() 必须因为 window.CLAtlasStage 是 undefined 而抛异常，stage-open 步骤如实 FAIL。
        sess.eval("delete window.CLAtlasStage")

    open_r = sess.eval("(function(){ try { window.CLAtlasStage.open(); return {ok:true}; } catch(e){ return {ok:false, why:String(e&&e.stack||e)}; } })()")
    if not (isinstance(open_r, dict) and open_r.get('ok')):
        rec('stage-open', False, open_r)
        return False, steps, 'CLAtlasStage.open() 抛异常：%s' % open_r
    time.sleep(0.3)
    if screenshots:
        sess.shot('02-stage-open')
    rec('stage-open', True)

    # R7-G ③：旧剧情 HUD（#clPlot，plot-hud.js 运行时根；上面 plot-toggle 已把它打开）开着时
    # 开展卷必须把它藏起来——旧实现找的是全代码域不存在的 .cp-wrap，恒为 null，旧 HUD 全程可见
    # （R7-D 短板 4 实测）。#clPlot 的显隐靠 .on 类（css/plot.css 的 .cl-plot{display:flex} 会盖过
    # UA 的 [hidden] 默认样式），所以除了 hidden 属性还要核对 computed display:none（css/atlas-stage.css
    # 白名单的一条 !important 规则），两者齐了才算真的看不见。
    hud_hide_expr = """(function(){
      var w = document.getElementById('clPlot');
      if (!w) return {ok:true, skipped:'plot-hud 未挂载（该样本/视口下 #clPlot 不存在）'};
      var cs = getComputedStyle(w);
      return {ok: w.hidden === true && cs.display === 'none', hiddenAttr: w.hidden, display: cs.display, hasOnClass: w.classList.contains('on')};
    })()"""
    hud_hide_r = sess.eval(hud_hide_expr)
    rec('clPlot-hidden-while-stage-open (R7-G old HUD hide path)', isinstance(hud_hide_r, dict) and hud_hide_r.get('ok') is True, hud_hide_r)

    # 全部作用域限定在 #atlasStage 内——不这样做会把旧 plot-hud / orbit3d 里同样带
    # role=row / data-ev 的历史 DOM 一起算进来，产生假阳性（v1 实测踩过：event-card 那步
    # 点到了 stage 之外的陈旧 data-ev 节点）。
    diag_expr = "(function(){ return { hasWindowGraph: typeof window.graph !== 'undefined', stageExists: !!document.getElementById('atlasStage') }; })()"
    diag = sess.eval(diag_expr)
    # CONTRACT §2.1（2026-09-20 新增）：数据行选择器是 [role="row"][data-line-id]——代次分组头
    # （.cl-score-genhead）也带 role=row 但**不带** data-line-id，之前版本没过滤，22 线的
    # sample-saga 数出 27（22 行 + 5 个代次分组头），是我的选择器不精，不是模块的 bug。
    # [data-more] 是「聚合/折叠展开按钮」的契约选择器；当前 atlas-score.js 里它只用在单行内的
    # 参与者「+N」溢出芯片（cl-score-chip-more，语义是人数聚合，不是线聚合），所以扫描时排除
    # 「嵌在某一行 [role=row][data-line-id] 内部」的 data-more——这部分本就已经被那一行自己
    # 算进 lineRows 了，重复计数反而破坏守恒。只把**不属于任何行**的 data-more（未来若线级聚合
    # 也复用这个属性）累加为 aggregateExtra，向前兼容而不对现状发明数字。
    rows_expr = """(function(){
      var s = document.getElementById('atlasStage');
      if (!s) return { lineRows: 0, aggregateExtra: 0, total: 0, stageExists: false };
      var rows = s.querySelectorAll('[role="row"][data-line-id]');
      var mores = s.querySelectorAll('[data-more]'), extra = 0;
      for (var i=0;i<mores.length;i++){
        if (mores[i].closest && mores[i].closest('[role="row"][data-line-id]')) continue;
        var m = (mores[i].textContent||'').match(/\d+/);
        extra += m ? parseInt(m[0],10) : 1;
      }
      // R3-D：>40 行默认折叠的组首绘不建行 DOM，只吐 data-pending="N" 占位；守恒把待建行计入。
    var pendings = s.querySelectorAll('.cl-score-genrows[data-lazy="1"][data-pending]'), pendingExtra = 0;
    for (var j=0;j<pendings.length;j++){ pendingExtra += parseInt(pendings[j].getAttribute('data-pending'),10) || 0; }
    return { lineRows: rows.length, aggregateExtra: extra, pendingExtra: pendingExtra, total: rows.length + extra + pendingExtra, stageExists: true };
    })()"""
    rows = sess.eval(rows_expr)
    n_total = rows.get('total') if isinstance(rows, dict) else -1
    raw = ground.get('rawThreads')
    rows_ok = (n_total == raw)
    rec('score-rows-conservation', rows_ok, {'rows': rows, 'rawThreads': raw, 'diag': diag,
        'note': 'CONTRACT §2.1：[role="row"][data-line-id] 数分组头已排除；[data-more] 只在不属于任何行时'
                '计入聚合（当前 DOM 里 data-more 只用于行内人数「+N」溢出，故 aggregateExtra 现状恒为 0）'})

    # CONTRACT §2.1：score 容器允许内部横向滚动，横向溢出改判 documentElement（页面级不可整体
    # 横向溢出），并另外确认 score 容器本身确实渲染了内容（scrollWidth>=clientWidth，防止「容器空着
    # 所以两个数字都是 0，通过是假的」）。
    overflow_ok = sess.eval("document.documentElement.scrollWidth <= innerWidth + 1")
    rec('no-horizontal-overflow-after-open', bool(overflow_ok) is True)
    score_root_expr = """(function(){
      var s = document.getElementById('atlasStage'); var r = s ? s.querySelector('.cl-score-root') : null;
      if (!r) return { ok:false, why:'#atlasStage 内找不到 .cl-score-root' };
      return { ok:true, scrollWidth: r.scrollWidth, clientWidth: r.clientWidth };
    })()"""
    score_root = sess.eval(score_root_expr)
    has_content_ok = isinstance(score_root, dict) and score_root.get('ok') and score_root.get('scrollWidth', 0) >= score_root.get('clientWidth', 1)
    rec('score-container-has-content', bool(has_content_ok), score_root)

    # R2-G 新增：键盘 ↓ 换行——独立于鼠标点击（鼠标点行头只走 focusRow()，不更新 onKeydown
    # 自己维护的 curRowIdx；只有 ArrowDown/Up 自己或 setFocus() 会同步 curRowIdx），所以单独用
    # 两次连续 ArrowDown 验证「聚焦行确实换了」，不依赖前面点没点过行。keydown 监听挂在
    # `.atlas-stage-host`（真实宿主元素，参考 atlas-stage.js:147 的 DOM 结构），直接在它上面
    # 派发才会命中 host.addEventListener('keydown', onKeydown) 的委托。
    kb_expr = """(function(){
      var s = document.getElementById('atlasStage');
      var h = s ? s.querySelector('.atlas-stage-host') : null;
      if (!h) return {ok:false, why:'找不到 .atlas-stage-host'};
      function fire(key){ h.dispatchEvent(new KeyboardEvent('keydown', {key:key, bubbles:true, cancelable:true})); }
      function focusedLineId(){
        var rows = s.querySelectorAll('[role="row"][data-line-id].%s');
        return rows.length ? rows[0].getAttribute('data-line-id') : null;
      }
      var PM = window.CLPanelManager;
      var absorbBefore = PM && PM.shouldAbsorbKey ? PM.shouldAbsorbKey(new KeyboardEvent('keydown', {key:'ArrowDown'})) : null;
      fire('ArrowDown');
      var first = focusedLineId();
      var dockOpenAfterFirst = !!(document.getElementById('dock') && document.getElementById('dock').classList.contains('is-open'));
      var absorbAfterFirst = PM && PM.shouldAbsorbKey ? PM.shouldAbsorbKey(new KeyboardEvent('keydown', {key:'ArrowDown'})) : null;
      fire('ArrowDown');
      var second = focusedLineId();
      return { ok:true, first:first, second:second, changed: first != null && second != null && first !== second,
        diag: { absorbBefore: absorbBefore, absorbAfterFirst: absorbAfterFirst, dockOpenAfterFirst: dockOpenAfterFirst } };
    })()""" % FOCUS_CLASS
    kb_r = sess.eval(kb_expr)
    kb_ok = isinstance(kb_r, dict) and kb_r.get('ok') is True and kb_r.get('changed') is True
    # 2026-09-20 实测重大发现（不是测试本身的 bug，是真实跨模块回归）：第 1 次 ArrowDown 正常换行，
    # 但 atlas-score.js 的 onKeydown 只 preventDefault() 没有 stopPropagation()（js/atlas/atlas-score.js:
    # 812-856），事件继续冒泡到 document，被 app.js 的全局「下一位角色」快捷键（keys.js 里标注
    # `own:false` 的 J/K「也可用 ↑ ↓」）接住，副作用是打开了 `#dock` 角色资料坞——之后
    # `CLPanelManager.shouldAbsorbKey()` 因为 `p.id==='dock'` 无条件吸收全局按键（js/hud/
    # panel-manager.js:264-276），keys.js 的 window 捕获监听（js/keys.js:433-435）从此每次都
    # `stopPropagation()`，展卷键盘导航从第 2 次起彻底失效，直到用户手动关掉资料坞。用
    # Event.prototype.stopPropagation 打补丁验证过调用栈，见报告。这是 R2-B 的 atlas-score.js 需要
    # 补一行 `e.stopPropagation()`（在它自己处理的分支里，紧跟 e.preventDefault()）才能修的真实缺陷，
    # 不在 R2-G 独占文件范围内，这里只如实记录、不代为修改。
    rec('keyboard-arrowdown-changes-focused-row', kb_ok, kb_r)
    # 清理副作用：把测试过程中意外打开的角色资料坞关掉，避免污染后面的 Esc/close/disc-focus 断言
    # （不清理的话 shouldAbsorbKey 会一直吸收按键，后面的 esc-key-closes-stage 会跟着假 FAIL）。
    sess.eval("(function(){ try { window.CLPanelManager && window.CLPanelManager.close && window.CLPanelManager.close('dock'); } catch(e){} })()")
    time.sleep(0.15)

    line_reading_ok = False
    line_reading_extra = None
    focus_dim_ok = False
    focus_dim_extra = None
    if ground.get('branchId') is not None:
        if ce == 'hide-row':
            # 反例③：点击前先把目标支线行整个从 DOM 摘掉，证明「找不到行就如实报 FAIL」，
            # 不会因为别的地方还留着同名文字就蒙混通过。
            hide_expr = """(function(){
              var s = document.getElementById('atlasStage');
              var rows = s ? s.querySelectorAll('[role="row"][data-line-id]') : [];
              var wantId = %s;
              for (var i=0;i<rows.length;i++){ if (rows[i].getAttribute('data-line-id') === wantId) { rows[i].remove(); return {ok:true, removed:true}; } }
              return {ok:false, why:'反例演示：没找到要隐藏的行，wantId='+wantId};
            })()""" % json.dumps(ground.get('branchId'))
            sess.eval(hide_expr)
        click_expr = """(function(){
          var s = document.getElementById('atlasStage');
          if (!s) return {ok:false, why:'#atlasStage 不存在'};
          var target = null;
          var rows = s.querySelectorAll('[role="row"][data-line-id]');
          var wantId = %s, wantName = %s;
          for (var i=0;i<rows.length;i++){
            var r = rows[i];
            var idAttr = r.getAttribute('data-line-id') || r.getAttribute('data-line') || r.getAttribute('data-t') || '';
            if (idAttr === wantId || (r.textContent||'').indexOf(wantName) !== -1) { target = r; break; }
          }
          if (!target) return {ok:false, why:'#atlasStage 内找不到支线 '+wantId+'（'+wantName+'）对应的 row（stage 内 row 总数 '+rows.length+'）'};
          var before = s.innerText.length;
          // 2026-09-20 实测发现：atlas-score.js 的 onClick 委托只认
          // `.closest('.cl-score-rowhead[data-line-id]')`（js/atlas/atlas-score.js:792），
          // `.cl-score-rowhead` 是 `[role="row"][data-line-id]` 内部的**子元素**，不是同一个节点。
          // 之前版本的 U09/v2 报告直接 `target.click()` 点在外层 row 容器上，从未真正命中过
          // rowhead 分支——之所以 line-reading-double-length-text 那步一直显示 PASS，是因为
          // 「跨…章」「…事」文案本来就烘焙在行内静态 HTML 里，跟有没有真的被点击/聚焦无关，
          // 是一个假阳性。这里改成点击内部的 .cl-score-rowhead，才是命中真实点击处理链路。
          var rowhead = target.querySelector('.cl-score-rowhead[data-line-id]') || target;
          rowhead.click();
          return {ok:true, before: before, lineId: target.getAttribute('data-line-id')};
        })()""" % (json.dumps(ground.get('branchId')), json.dumps(ground.get('branchName') or ''))
        click_r = sess.eval(click_expr)
        if isinstance(click_r, dict) and click_r.get('ok'):
            time.sleep(0.25)
            if screenshots:
                sess.shot('03-line-click')
            text_check = sess.eval("""(function(){
              var s = document.getElementById('atlasStage');
              var t = s ? (s.innerText || '') : '';
              var hasSpan = /跨\\s*\\d+\\s*章/.test(t);
              var hasCount = /\\d+\\s*事/.test(t);
              return {hasSpan: hasSpan, hasCount: hasCount, sample: t.slice(0, 4000).length};
            })()""")
            if isinstance(text_check, dict):
                line_reading_ok = bool(text_check.get('hasSpan')) and bool(text_check.get('hasCount'))
                line_reading_extra = text_check

            # 任务书 R2-G 第 1 条：setFocus/点击后目标行有聚焦类，且**其它行 opacity < .6**
            # （R2-B.md 第 3 条原文写的是「其余行 opacity .45」，这里用契约泛指的 .6 门槛，不因
            # R2-B 最终调值细节而误判）。若 R2-B 尚未落地这个视觉降级，这里会如实 FAIL——不是
            # 断言写错，是功能还没做完，见报告「未完成/待复验」栏。
            focus_dim_expr = """(function(){
              var s = document.getElementById('atlasStage');
              var rows = s.querySelectorAll('[role="row"][data-line-id]');
              var wantId = %s, target = null, others = [];
              for (var i=0;i<rows.length;i++){
                if (rows[i].getAttribute('data-line-id') === wantId) target = rows[i]; else others.push(rows[i]);
              }
              if (!target) return {ok:false, why:'focus 断言时目标行已不在 DOM'};
              var hasFocusClass = target.classList.contains('%s');
              var dimmedCount = 0, sample = [];
              for (var j=0;j<others.length;j++){
                var op = parseFloat(getComputedStyle(others[j]).opacity);
                if (isNaN(op)) op = 1;
                sample.push(Math.round(op * 100) / 100);
                if (op < %s) dimmedCount++;
              }
              return { ok:true, hasFocusClass:hasFocusClass, othersCount:others.length, dimmedCount:dimmedCount,
                allDimmed: others.length > 0 && dimmedCount === others.length, sample: sample.slice(0, 6) };
            })()""" % (json.dumps(click_r.get('lineId')), FOCUS_CLASS, DIM_OPACITY_MAX)
            focus_dim_r = sess.eval(focus_dim_expr)
            focus_dim_ok = isinstance(focus_dim_r, dict) and focus_dim_r.get('ok') is True and focus_dim_r.get('hasFocusClass') is True and focus_dim_r.get('allDimmed') is True
            focus_dim_extra = focus_dim_r
        else:
            line_reading_extra = click_r
            focus_dim_extra = {'skipped': 'line click 失败，无法测 focus/dim'}
    rec('line-reading-double-length-text', line_reading_ok, line_reading_extra)
    rec('focus-class-and-other-rows-dimmed', focus_dim_ok, focus_dim_extra)

    # CONTRACT §2.1：事件刻度选择器是 [data-event-idx]（不是我 v1 猜的 [data-ev]，那是旧
    # plot-hud 的属性名——用错属性名在有真实 stage 时会稳定得到「找不到」的假 FAIL）。
    # R2-G 收紧：任务书原话「事件卡含标题与所属线」，不再用「聚焦即可」兜底——tick 点击后
    # atlas-score.js 的 openEvent() 必然调用 showEventCard()（js/atlas/atlas-score.js:598 一带），
    # 所以直接要求卡片真的出现且正文含「标题」「所属线」两个字段标签（源码 eventCardBodyHtml
    # 硬编码的 dt 文案，见 atlas-score.js:420-428）。
    event_card_ok = False
    event_card_extra = None
    tick_expr = """(function(){
      var s = document.getElementById('atlasStage');
      var cands = s ? s.querySelectorAll('[data-event-idx]') : [];
      if (!cands.length) return {ok:false, why:'#atlasStage 内找不到任何 [data-event-idx] 事件刻度'};
      var el = cands[0], ei = el.getAttribute('data-event-idx');
      // .cl-score-tick(-hit) 是 SVG <line>：部分引擎的 SVGElement 没有 .click()
      // （2026-09-20 实测：'el.click is not a function'），改用 dispatchEvent(MouseEvent)——
      // atlas-score.js 的点击处理是 host 上的委托监听（addEventListener('click', onClick)），
      // 冒泡事件与真实点击对它来说等价。
      el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      return {ok:true, ev: ei};
    })()"""
    tick_r = sess.eval(tick_expr)
    if isinstance(tick_r, dict) and tick_r.get('ok'):
        time.sleep(0.25)
        if screenshots:
            sess.shot('04-event-tick-click')
        # 事件卡容器/内容/关闭按钮选择器是 U02 最初写给 U09 的契约（.cl-score-eventcard /
        # .cl-score-eventcard-body / [data-eventcard-close]），2026-09-20 仍成立。但卡片内部结构
        # 已经被 R2-B 按 ROUND2.md 重新设计过（不再是 dt/dd 标签式的「标题」「所属线」文字对，
        # 改成层级卡片：标题是 <h3 class="cl-score-card-title">，所属线是 gen 色条 + 名字放在
        # <div class="cl-score-card-lines">，见 js/atlas/atlas-score.js:496-522 的 eventCardBodyHtml；
        # 找不到「标题」二字是设计升级，不是回归——这里改用真实存在的两个子选择器分别判「标题非空」
        # 「所属线非空」，不再依赖已经被替换掉的旧文案。
        focus_check_expr = """(function(){
          var s = document.getElementById('atlasStage');
          var ei = %s;
          var ticks = s ? s.querySelectorAll('.cl-score-tick[data-event-idx="' + ei + '"], .cl-score-tick-hit[data-event-idx="' + ei + '"]') : [];
          var anyFocused = false;
          for (var i=0;i<ticks.length;i++) if (ticks[i].classList.contains('%s')) anyFocused = true;
          var card = s ? s.querySelector('.cl-score-eventcard') : null;
          var cardShown = !!(card && !card.classList.contains('is-hidden'));
          var titleEl = cardShown ? card.querySelector('.cl-score-card-title') : null;
          var linesEl = cardShown ? card.querySelector('.cl-score-card-lines') : null;
          var cardBody = cardShown ? (card.querySelector('.cl-score-eventcard-body') || {}).textContent : null;
          return { focused: anyFocused, cardFound: !!card, cardShown: cardShown,
            titleText: titleEl ? titleEl.textContent : null, linesText: linesEl ? linesEl.textContent : null,
            cardBody: cardBody, ticksChecked: ticks.length };
        })()""" % (json.dumps(tick_r.get('ev')), FOCUS_CLASS)
        focus_r = sess.eval(focus_check_expr)
        if isinstance(focus_r, dict):
            has_title = bool((focus_r.get('titleText') or '').strip())
            has_line = bool((focus_r.get('linesText') or '').strip())
            event_card_ok = bool(focus_r.get('cardShown')) and has_title and has_line
            focus_r['hasNonEmptyTitle'] = has_title
            focus_r['hasNonEmptyLineInfo'] = has_line
            event_card_extra = focus_r
        else:
            event_card_extra = focus_r
    else:
        event_card_extra = tick_r
    rec('event-card-has-title-and-line', event_card_ok, event_card_extra)

    # R2-G 新增「Esc 关卡」：真实键盘旅程，不直接调 CLAtlasStage.close()。之前 v1/v2 的写法是
    # `document.dispatchEvent(...)` 后另外显式调 close()——但 keydown 事件只会往上冒泡，从
    # document 派发根本到不了挂在 `.atlas-stage-host` 上的委托监听（host 是 document 的后代，
    # 不是祖先），所以那一行 dispatchEvent 从来没有真正测过 Esc；真正让 stage 关闭的一直是紧跟着
    # 的显式 close() 调用。这里改成在 `.atlas-stage-host`（onKeydown 监听器所在元素）上直接派发
    # Escape。2026-09-20 实测：R2-B 已经把 Esc 做成两层——事件卡开着时第 1 次 Esc 只关卡片
    # （js/atlas/atlas-score.js:848-853 `if (isCardOpen()) { hideEventCard(); return; }`），第 2 次
    # 才转给 opts.onBack()（atlas-stage.js:238 接到 close()）。这里前面刚点过事件刻度、卡应该是
    # 开着的，所以按真实分层逐条断言：第 1 次 Esc 只关卡片、stage 仍开；第 2 次 Esc 才关 stage。
    esc_dispatch_expr = """(function(){
      var s = document.getElementById('atlasStage');
      var h = s ? s.querySelector('.atlas-stage-host') : null;
      if (!h) return {ok:false, why:'找不到 .atlas-stage-host，无法派发真实 Esc'};
      h.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true, cancelable:true}));
      return {ok:true};
    })()"""
    esc1_r = sess.eval(esc_dispatch_expr)
    time.sleep(0.25)
    after_esc1 = sess.eval("""(function(){
      var s = document.getElementById('atlasStage');
      var card = s ? s.querySelector('.cl-score-eventcard') : null;
      var cardHiddenNow = !!(card && card.classList.contains('is-hidden'));
      var stageOn = window.CLAtlasStage && window.CLAtlasStage.isOn ? window.CLAtlasStage.isOn() : null;
      return { cardHiddenNow: cardHiddenNow, stageOn: stageOn };
    })()""")
    esc1_ok = isinstance(after_esc1, dict) and after_esc1.get('cardHiddenNow') is True and after_esc1.get('stageOn') is True
    rec('esc-1st-closes-card-not-stage', esc1_ok, {'esc1_r': esc1_r, 'after': after_esc1})

    esc2_r = sess.eval(esc_dispatch_expr)
    time.sleep(0.3)
    if screenshots:
        sess.shot('05-stage-close')
    is_on_after_esc2 = sess.eval("(function(){ try { return window.CLAtlasStage.isOn(); } catch(e){ return null; } })()")
    esc2_closed_ok = is_on_after_esc2 is False
    rec('esc-2nd-closes-stage', esc2_closed_ok, {'esc2_r': esc2_r, 'isOnAfterEsc2': is_on_after_esc2})
    if not esc2_closed_ok:
        # 兜底：真实 Esc 没关成功不应发生，但为了不让后面 panels-restored/disc-focus 两步跟着级联
        # 误判，这里显式关一次——上面两条 esc-* 步骤已经如实记录了各自的真实结果，不会被这个兜底掩盖。
        sess.eval("(function(){ try { window.CLAtlasStage.close(); } catch(e){} })()")
        time.sleep(0.2)

    restore_expr = """(function(){
      var ptp = document.getElementById('plotTextPanel');
      var cpw = document.querySelector('.cp-wrap');
      // R7-G ③：#clPlot 是旧剧情 HUD 的真实运行时根（.cp-wrap 全代码域不存在，恒 null，保留旧
      // 口径只作历史记录），收卷后 hidden 必须恢复原值（false），且 computed display 回到非 none。
      var clw = document.getElementById('clPlot');
      return { ptpHiddenRestored: ptp ? !ptp.hidden : null, cpwHiddenRestored: cpw ? !cpw.hidden : null,
               clwHiddenRestored: clw ? (!clw.hidden && getComputedStyle(clw).display !== 'none') : null };
    })()"""
    restore_r = sess.eval(restore_expr)
    restore_ok = True
    if isinstance(restore_r, dict):
        if restore_r.get('ptpHiddenRestored') is False:
            restore_ok = False
        if restore_r.get('cpwHiddenRestored') is False:
            restore_ok = False
        if restore_r.get('clwHiddenRestored') is False:
            restore_ok = False
    rec('panels-restored-after-close', restore_ok, restore_r)

    focus_after = sess.eval("(function(){var o=window.CLPlotOrbit&&window.CLPlotOrbit.get&&window.CLPlotOrbit.get();return o?o.selectedEvent:null;})()")
    focus_ok = (focus_before == focus_after)
    rec('disc-focus-unchanged', focus_ok, {'before': focus_before, 'after': focus_after})

    all_ok = all(s['ok'] for s in steps)
    why = '' if all_ok else '；'.join(s['step'] for s in steps if not s['ok'])
    return all_ok, steps, why


def run_score_only_fallback(sess, screenshots):
    """CLAtlasStage 缺席、CLAtlasModel+CLAtlasScore 都在时的兜底：注入 synth.small()，
    直接 build+mount 到临时 host，只跑 score 部分的行数守恒 + 双长度文本。"""
    steps = []

    def rec(name, ok, extra=None):
        steps.append({'step': name, 'ok': ok, 'extra': extra})
        return ok

    synth_src = open(SYNTH_PATH, encoding='utf-8').read()
    sess.eval(synth_src)
    expr = """(function(){
      try {
        var tree = window.CLAtlasBrowserSynth.small();
        var G = window.CLAtlasBrowserSynth.graphOf(tree);
        var model = window.CLAtlasModel.build(tree, G);
        var host = document.createElement('div');
        host.id = 'u09TempHost'; host.style.position='fixed'; host.style.left='0'; host.style.top='0';
        host.style.width = (window.innerWidth) + 'px'; host.style.height = (window.innerHeight) + 'px';
        document.body.appendChild(host);
        var api = window.CLAtlasScore.mount(host, { model: model });
        // CONTRACT §2.1：只数 [role="row"][data-line-id]，排除代次分组头（同一属性但无
        // data-line-id）；data-more 只在不属于任何行时计入聚合（见 run_full_chain 里的注释）。
        var rows = host.querySelectorAll('[role="row"][data-line-id]');
        var mores = host.querySelectorAll('[data-more]'), extra = 0;
        for (var i=0;i<mores.length;i++){
          if (mores[i].closest && mores[i].closest('[role="row"][data-line-id]')) continue;
          var m = (mores[i].textContent||'').match(/\d+/);
          extra += m ? parseInt(m[0],10) : 1;
        }
        return { ok:true, rows: rows.length, aggregateExtra: extra, total: rows.length + extra,
          rawThreads: model.conservation.rawThreads, hasDispose: typeof api.dispose === 'function' };
      } catch(e) { return { ok:false, why: String(e && e.stack || e) }; }
    })()"""
    r = sess.eval(expr)
    if not (isinstance(r, dict) and r.get('ok')):
        rec('fallback-mount', False, r)
        return False, steps, 'score-only 兜底 mount 失败：%s' % r
    rec('fallback-mount', True, r)
    if screenshots:
        sess.shot('02-score-fallback-mount')
    rows_ok = r.get('total') == r.get('rawThreads')
    rec('fallback-rows-conservation', rows_ok, r)
    text_check = sess.eval("""(function(){
      var h = document.getElementById('u09TempHost'); var t = h ? h.innerText : '';
      return { hasSpan: /跨\\s*\\d+\\s*章/.test(t), hasCount: /\\d+\\s*事/.test(t) };
    })()""")
    dl_ok = isinstance(text_check, dict) and text_check.get('hasSpan') and text_check.get('hasCount')
    rec('fallback-double-length-text', bool(dl_ok), text_check)
    sess.eval("(function(){ var h=document.getElementById('u09TempHost'); if(h) h.remove(); })()")
    all_ok = all(s['ok'] for s in steps)
    return all_ok, steps, '' if all_ok else '；'.join(s['step'] for s in steps if not s['ok'])


def run_viewport(size, synth_src, ce=None):
    _ensure_out_dir()
    sess = Session(size)
    result = {'size': size}
    if ce:
        result['ce'] = ce
    try:
        sess.start()
        sess.navigate('http://127.0.0.1:8000/?data=data/sample-saga.json&probe=1&pump=1')
        ready = sess.wait_ready(60)
        result['ready'] = ready
        if not ready:
            jserr = sess.eval("document.body.dataset.jserr||''")
            result['status'] = 'FAIL'
            result['why'] = 'sample-saga 未就绪（60s 超时）；jserr=%s' % jserr
            return result
        sess.shot('00-loaded')
        detect = sess.eval(DETECT_EXPR)
        if not isinstance(detect, dict):
            result['status'] = 'FAIL'
            result['why'] = 'globals 探测求值失败：%s' % detect
            return result
        detect, injected, inject_errors = inject_missing_modules(sess, detect)
        result['detect'] = detect
        result['host_wired'] = not injected  # True = 页面自带这些全局（HOST 已接线或本就存在）
        if injected:
            result['injected'] = injected
        if inject_errors:
            result['inject_errors'] = inject_errors

        if detect.get('CLPlot'):
            toggle_r = sess.eval("(function(){ try { return {ok:true, on: window.CLPlot.toggle()}; } catch(e){ return {ok:false, why:String(e)}; } })()")
            result['plot_toggle'] = toggle_r
            time.sleep(0.3)
            sess.shot('01-plot-toggle')
        else:
            result['plot_toggle'] = {'ok': False, 'why': 'window.CLPlot 不存在（不应发生，属既有生产代码）'}

        missing = [k for k in REQUIRED_GLOBALS if not detect.get(k)]
        if not missing:
            ok, steps, why = run_full_chain(sess, screenshots=True, ce=ce)
            result['mode'] = 'full-chain'
            result['status'] = 'OK' if ok else 'FAIL'
            result['steps'] = steps
            result['why'] = why
        elif detect.get('CLAtlasModel') and detect.get('CLAtlasScore'):
            ok, steps, why = run_score_only_fallback(sess, screenshots=True)
            result['mode'] = 'score-only-fallback'
            result['status'] = 'OK' if ok else 'FAIL'
            result['steps'] = steps
            result['why'] = why + ('（CLAtlasStage 缺席，未测展卷开合/共享锚点/焦点保持，见 U09 报告未完成栏）' if why else '（CLAtlasStage 缺席，仅跑 score 部分；见 U09 报告未完成栏）')
        else:
            result['mode'] = 'skip'
            result['status'] = 'SKIP'
            result['why'] = '模块缺席：%s' % ', '.join(missing)
        return result
    except Exception as e:
        result['status'] = 'FAIL'
        result['why'] = 'runner 异常：%r' % (e,)
        return result
    finally:
        sess.close()


def run_stress(size='1440x900'):
    """R10 3000 事件压力：只要求不崩、可滚动；首绘/帧时仅供参考记录。"""
    sess = Session(size)
    result = {'size': size, 'kind': 'stress'}
    try:
        sess.start()
        sess.navigate('http://127.0.0.1:8000/?data=data/sample-saga.json&probe=1&pump=1')
        if not sess.wait_ready(60):
            result['status'] = 'FAIL'; result['why'] = '压力测试页面未就绪'
            return result
        detect = sess.eval(DETECT_EXPR)
        if isinstance(detect, dict):
            detect, injected, inject_errors = inject_missing_modules(sess, detect)
            if injected:
                result['injected'] = injected
            if inject_errors:
                result['inject_errors'] = inject_errors
        if not (isinstance(detect, dict) and detect.get('CLAtlasModel') and detect.get('CLAtlasScore')):
            result['status'] = 'SKIP'
            result['why'] = '压力测试需要 CLAtlasModel + CLAtlasScore，缺席：%s' % (
                ', '.join(k for k in ('CLAtlasModel', 'CLAtlasScore') if not (isinstance(detect, dict) and detect.get(k))))
            return result
        synth_src = open(SYNTH_PATH, encoding='utf-8').read()
        sess.eval(synth_src)
        build_expr = """(function(){
          try {
            var tree = window.CLAtlasBrowserSynth.stress();
            var t0 = performance.now();
            var model = window.CLAtlasModel.build(tree, {});
            var t1 = performance.now();
            window.__u09stress = { model: model, buildMs: t1 - t0 };
            return { ok:true, buildMs: t1-t0, threads: model.conservation.rawThreads, lines: model.lines.length };
          } catch(e) { return { ok:false, why: String(e && e.stack || e) }; }
        })()"""
        build_r = sess.eval(build_expr)
        if not (isinstance(build_r, dict) and build_r.get('ok')):
            result['status'] = 'FAIL'; result['why'] = 'stress model.build 失败：%s' % build_r
            return result
        mount_expr = """(function(){
          try {
            var host = document.createElement('div');
            host.id = 'u09StressHost'; host.style.position='fixed'; host.style.left='0'; host.style.top='0';
            host.style.width = window.innerWidth + 'px'; host.style.height = window.innerHeight + 'px';
            host.style.overflow = 'auto';
            document.body.appendChild(host);
            var t0 = performance.now();
            var api = window.CLAtlasScore.mount(host, { model: window.__u09stress.model });
            var t1 = performance.now();
            // 60 线 > MAX_FLAT_ROWS(40) 时 atlas-score.js 默认按代次分组折叠（is-collapsed），
            // 这是契约行为（「仍守恒，不截断」），不是缺陷——但折叠态下容器几乎没有渲染高度，
            // 会把「可滚动」断言测成假 FAIL。真实读者要看 3000 事件必然会展开，所以这里先模拟
            // 点开每个分组头（真实 click 事件，走 atlas-score.js 自己的 onClick 委托），再测
            // 展开后的可滚动性，这才是 R10「可滚动」真正要考验的状态。
            var heads = host.querySelectorAll('.cl-score-genhead[aria-expanded="false"]');
            for (var h = 0; h < heads.length; h++) heads[h].dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
            var frames = [];
            for (var i=0;i<30;i++){
              var f0 = performance.now();
              if (typeof api.step === 'function') api.step(16);
              host.scrollTop += 40;
              var f1 = performance.now();
              frames.push(f1-f0);
            }
            var avg = frames.reduce(function(a,b){return a+b;},0)/frames.length;
            var scrollable = host.scrollHeight > host.clientHeight;
            return { ok:true, firstPaintMs: t1-t0, avgFrameMs: avg, scrollable: scrollable,
              expandedGroups: heads.length,
              rows: host.querySelectorAll('[role="row"][data-line-id]').length };
          } catch(e) { return { ok:false, why: String(e && e.stack || e) }; }
        })()"""
        mount_r = sess.eval(mount_expr)
        result['build'] = build_r
        result['mount'] = mount_r
        if isinstance(mount_r, dict) and mount_r.get('ok'):
            result['status'] = 'OK' if mount_r.get('scrollable') or mount_r.get('rows', 0) <= 1 else 'FAIL'
            if not mount_r.get('scrollable') and mount_r.get('rows', 0) > 1:
                result['why'] = '3000 事件 fixture 渲染后不可滚动（host.scrollHeight <= clientHeight）'
            else:
                result['why'] = ''
        else:
            result['status'] = 'FAIL'
            result['why'] = 'stress mount 失败：%s' % mount_r
        sess.shot('stress-3000ev')
        return result
    except Exception as e:
        result['status'] = 'FAIL'
        result['why'] = 'runner 异常：%r' % (e,)
        return result
    finally:
        sess.close()


def run_large_sample(size='1440x900'):
    """R2-G 第 2 条：真实大样本任务链——`data/cache/2ef47b2ecaa99a67352091d5.json`（大奉打更人，
    2990 事件，storylines 为空走 CLStory 推导树，不是 sample-saga 那种小巧的手工 fixture）。
    步骤：CLPlot.toggle → CLAtlasStage.open → 行数+组折叠计数守恒 == CLPlot.atlas().conservation.
    rawThreads → 展开一组 → 点一刻度 → 卡出现；顺带记首绘/均帧（仅供参考，不是严格 R10 预算）。"""
    sess = Session(size)
    result = {'size': size, 'kind': 'large-sample-dafeng'}
    try:
        sess.start()
        sess.navigate('http://127.0.0.1:8000/?%s' % LARGE_SAMPLE_QUERY)
        if not sess.wait_ready(90):
            result['status'] = 'FAIL'
            result['why'] = '大奉打更人 fixture 未就绪（90s 超时）'
            return result
        detect = sess.eval(DETECT_EXPR)
        if not (isinstance(detect, dict) and detect.get('CLPlot') and detect.get('CLAtlasModel') and detect.get('CLAtlasStage')):
            result['status'] = 'SKIP'
            result['why'] = '大样本任务链需要 CLPlot+CLAtlasModel+CLAtlasStage，探测结果：%s' % detect
            return result

        steps = []

        def rec(name, ok, extra=None):
            steps.append({'step': name, 'ok': ok, 'extra': extra})
            return ok

        toggle_r = sess.eval("(function(){ try { return {ok:true, on: window.CLPlot.toggle()}; } catch(e){ return {ok:false, why:String(e)}; } })()")
        rec('plot-toggle', isinstance(toggle_r, dict) and toggle_r.get('ok') is True, toggle_r)
        time.sleep(0.4)

        # R3-E 修正：首绘只能量 open() 这一次同步调用本身（t0/t1 都在同一条 JS eval 里取，
        # 不跨 Python↔CDP 往返），旧写法把 t_open_start 放在 eval 外、t_open_end 放在
        # expand-one-group / tick-click / card-check 三步 sleep(0.3+0.3) 与两次 sess.shot()
        # 之后才取——测出来的「9.8s」里绝大部分是 Python 侧 time.sleep() 与截图 CDP 往返，
        # 不是 CLAtlasStage.open() 真实耗时（R2-B.md 已用同样手法测出真实值 29ms，此处独立复核）。
        open_r = sess.eval("(function(){ try { var t0 = performance.now(); window.CLAtlasStage.open(); "
                            "var t1 = performance.now(); return {ok:true, firstPaintMs: t1-t0}; } "
                            "catch(e){ return {ok:false, why:String(e&&e.stack||e)}; } })()")
        rec('stage-open', isinstance(open_r, dict) and open_r.get('ok') is True, open_r)
        first_paint_ms = open_r.get('firstPaintMs') if isinstance(open_r, dict) else None
        time.sleep(0.6)
        sess.shot('large-dafeng-01-stage-open')

        # 「守恒真值」：任务书原话是「== CLPlot.atlas().conservation.rawThreads」，先探测
        # window.CLPlot.atlas 是否存在（U04/U02 有的实现是转发到 CLPlot 命名空间下的缓存 model，
        # 有的没有），没有就退回和 run_full_chain 一致的手动 build 路径，两条路径算出来的
        # rawThreads 理论上应该一致（都是同一份 tree+G），如实记录用了哪条路径。
        ground_expr = """(function(){
          try {
            var viaCLPlotAtlas = (window.CLPlot && typeof window.CLPlot.atlas === 'function') ? window.CLPlot.atlas() : null;
            if (viaCLPlotAtlas && viaCLPlotAtlas.conservation) {
              return { ok:true, path:'CLPlot.atlas()', rawThreads: viaCLPlotAtlas.conservation.rawThreads,
                linesLen: (viaCLPlotAtlas.lines || []).length };
            }
            var G = window.__cl.graph(); var tree = window.CLPlot.tree();
            if (!tree || !tree.ok) return {ok:false, why:'CLPlot.tree() 未就绪或 !ok'};
            var model = window.CLAtlasModel.build(tree, G);
            return { ok:true, path:'CLAtlasModel.build(手动)', rawThreads: model.conservation.rawThreads,
              linesLen: model.lines.length };
          } catch(e){ return {ok:false, why:'build 抛异常：'+String(e && e.stack || e)}; }
        })()"""
        ground = sess.eval(ground_expr)
        rec('build-ground-truth-model', isinstance(ground, dict) and ground.get('ok') is True, ground)

        rows_expr = """(function(){
          var s = document.getElementById('atlasStage');
          if (!s) return { lineRows: 0, aggregateExtra: 0, total: 0, stageExists: false };
          var rows = s.querySelectorAll('[role="row"][data-line-id]');
          var mores = s.querySelectorAll('[data-more]'), extra = 0;
          for (var i=0;i<mores.length;i++){
            if (mores[i].closest && mores[i].closest('[role="row"][data-line-id]')) continue;
            var m = (mores[i].textContent||'').match(/\\d+/);
            extra += m ? parseInt(m[0],10) : 1;
          }
          // R3-D：>40 行默认折叠的组首绘不建行 DOM，只吐 data-pending="N" 占位；守恒把待建行计入。
    var pendings = s.querySelectorAll('.cl-score-genrows[data-lazy="1"][data-pending]'), pendingExtra = 0;
    for (var j=0;j<pendings.length;j++){ pendingExtra += parseInt(pendings[j].getAttribute('data-pending'),10) || 0; }
    return { lineRows: rows.length, aggregateExtra: extra, pendingExtra: pendingExtra, total: rows.length + extra + pendingExtra, stageExists: true };
        })()"""
        rows = sess.eval(rows_expr)
        raw = ground.get('rawThreads') if isinstance(ground, dict) else None
        n_total = rows.get('total') if isinstance(rows, dict) else -1
        rec('score-rows-conservation', isinstance(ground, dict) and ground.get('ok') is True and n_total == raw,
            {'rows': rows, 'rawThreads': raw})

        expand_expr = """(function(){
          var s = document.getElementById('atlasStage');
          var head = s ? s.querySelector('.cl-score-genhead[aria-expanded="false"]') : null;
          if (!head) return {ok:false, why:'没有可展开的折叠分组头（可能线数 <= MAX_FLAT_ROWS，本就未折叠）'};
          var gen = head.closest('.cl-score-gen');
          head.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
          return {ok:true, expandedGen: gen ? gen.getAttribute('data-gen') : null,
            nowExpanded: head.getAttribute('aria-expanded') === 'true'};
        })()"""
        expand_r = sess.eval(expand_expr)
        rec('expand-one-group', isinstance(expand_r, dict) and expand_r.get('ok') is True and expand_r.get('nowExpanded') is True, expand_r)
        time.sleep(0.3)
        sess.shot('large-dafeng-02-group-expanded')

        tick_expr = """(function(){
          var s = document.getElementById('atlasStage');
          var cands = s ? s.querySelectorAll('[data-event-idx]') : [];
          if (!cands.length) return {ok:false, why:'#atlasStage 内找不到任何 [data-event-idx] 事件刻度'};
          var el = cands[0], ei = el.getAttribute('data-event-idx');
          el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
          return {ok:true, ev: ei};
        })()"""
        tick_r = sess.eval(tick_expr)
        card_ok = False
        card_extra = tick_r
        if isinstance(tick_r, dict) and tick_r.get('ok'):
            time.sleep(0.3)
            sess.shot('large-dafeng-03-event-card')
            # 同 run_full_chain 的说明：卡片结构已由 R2-B 重设计，标题/所属线不再是 dt/dd 文字
            # 标签，改用 .cl-score-card-title / .cl-score-card-lines 两个真实子节点判非空。
            card_check_expr = """(function(){
              var s = document.getElementById('atlasStage');
              var card = s ? s.querySelector('.cl-score-eventcard') : null;
              var cardShown = !!(card && !card.classList.contains('is-hidden'));
              var titleEl = cardShown ? card.querySelector('.cl-score-card-title') : null;
              var linesEl = cardShown ? card.querySelector('.cl-score-card-lines') : null;
              return {cardShown: cardShown, titleText: titleEl ? titleEl.textContent : null,
                linesText: linesEl ? linesEl.textContent : null};
            })()"""
            card_r = sess.eval(card_check_expr)
            if isinstance(card_r, dict):
                has_title = bool((card_r.get('titleText') or '').strip())
                has_line = bool((card_r.get('linesText') or '').strip())
                card_ok = bool(card_r.get('cardShown')) and has_title and has_line
                card_extra = card_r
        rec('event-card-appears', card_ok, card_extra)

        frame_expr = """(function(){
          var s = document.getElementById('atlasStage');
          var host = s ? s.querySelector('.atlas-stage-host') : null;
          if (!host) return {ok:false, why:'找不到 .atlas-stage-host 做滚动测帧'};
          var frames = [];
          for (var i=0;i<30;i++){
            var f0 = performance.now();
            host.scrollTop += 40;
            var f1 = performance.now();
            frames.push(f1-f0);
          }
          var avg = frames.reduce(function(a,b){return a+b;},0)/frames.length;
          return {ok:true, avgFrameMs: avg, scrollable: host.scrollHeight > host.clientHeight};
        })()"""
        frame_r = sess.eval(frame_expr)
        rec('scroll-frame-timing', isinstance(frame_r, dict) and frame_r.get('ok') is True, frame_r)

        result['firstPaintMs（open()同步调用本身，t0/t1同一JS eval内取，剔除sleep/截图）'] = first_paint_ms
        result['avgFrameMs'] = frame_r.get('avgFrameMs') if isinstance(frame_r, dict) else None
        result['steps'] = steps
        all_ok = all(s['ok'] for s in steps)
        result['status'] = 'OK' if all_ok else 'FAIL'
        result['why'] = '' if all_ok else '；'.join(s['step'] for s in steps if not s['ok'])
        return result
    except Exception as e:
        result['status'] = 'FAIL'
        result['why'] = 'runner 异常：%r' % (e,)
        return result
    finally:
        sess.close()


def main():
    _ensure_out_dir()
    ce = None
    if '--ce' in sys.argv:
        ce = sys.argv[sys.argv.index('--ce') + 1]
        # 反例演示模式：只跑 1440x900 的 full-chain，打印完整 steps 后退出，不跑其余视口/压力/
        # 大样本——这不是正式验收路径，是给报告贴「失败输出」用的。
        synth_src = open(SYNTH_PATH, encoding='utf-8').read() if os.path.isfile(SYNTH_PATH) else ''
        r = run_viewport('1440x900', synth_src, ce=ce)
        print('=== COUNTEREXAMPLE ce=%s ===' % ce)
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        return 0 if r.get('status') == 'FAIL' else 1

    synth_src = open(SYNTH_PATH, encoding='utf-8').read() if os.path.isfile(SYNTH_PATH) else ''
    results = {}
    fail = []
    for size in VIEWPORTS:
        r = run_viewport(size, synth_src)
        results[size] = r
        print('--- %s : %s (%s) ---' % (size, r.get('status'), r.get('mode', r.get('why', ''))))
        if r.get('status') == 'FAIL':
            print('   why:', r.get('why'))
        if r.get('steps'):
            for s in r['steps']:
                print('   [%s] %s %s' % ('OK ' if s['ok'] else 'FAIL', s['step'], '' if s['ok'] else (s.get('extra') or '')))
        if r.get('status') == 'FAIL':
            fail.append(size)

    stress_r = run_stress()
    results['stress'] = stress_r
    print('--- stress(3000ev) : %s ---' % stress_r.get('status'))
    print('   ', {k: v for k, v in stress_r.items() if k not in ('build',)})
    if stress_r.get('status') == 'FAIL':
        fail.append('stress')

    large_r = run_large_sample()
    results['large-sample-dafeng'] = large_r
    print('--- large-sample(dafeng-2990ev) : %s ---' % large_r.get('status'))
    if large_r.get('steps'):
        for s in large_r['steps']:
            print('   [%s] %s %s' % ('OK ' if s['ok'] else 'FAIL', s['step'], '' if s['ok'] else (s.get('extra') or '')))
    else:
        print('   ', {k: v for k, v in large_r.items() if k not in ('steps',)})
    if large_r.get('status') == 'FAIL':
        fail.append('large-sample-dafeng')

    tag = 'FAIL' if fail else 'OK'
    print('ATLAS_BROWSER %s · %s' % (tag, json.dumps(results, ensure_ascii=False, default=str)))
    return 0 if not fail else 1


if __name__ == '__main__':
    sys.exit(main())
