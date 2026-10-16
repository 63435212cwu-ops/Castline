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
import headless
headless.reap_orphans = lambda: None

SYNTH_PATH = os.path.join(HERE, 'fixtures', 'atlas-browser-synth.js')
VIEWPORTS = ['1440x900', '820x1180', '390x844']
LARGE_SAMPLE_QUERY = 'data=data/cache/2ef47b2ecaa99a67352091d5.json&probe=1&pump=1'

REQUIRED_GLOBALS = ('CLAtlasModel', 'CLAtlasScore', 'CLAtlasStage')

FOCUS_CLASS = 'is-focused'
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
        ground = dict(ground)
        ground['rawThreads'] = (ground.get('rawThreads') or 0) + 1

    focus_before = sess.eval("(function(){var o=window.CLPlotOrbit&&window.CLPlotOrbit.get&&window.CLPlotOrbit.get();return o?o.selectedEvent:null;})()")

    if ce == 'missing-stage':
        sess.eval("delete window.CLAtlasStage")

    open_r = sess.eval("(function(){ try { window.CLAtlasStage.open(); return {ok:true}; } catch(e){ return {ok:false, why:String(e&&e.stack||e)}; } })()")
    if not (isinstance(open_r, dict) and open_r.get('ok')):
        rec('stage-open', False, open_r)
        return False, steps, 'CLAtlasStage.open() 抛异常：%s' % open_r
    time.sleep(0.3)
    if screenshots:
        sess.shot('02-stage-open')
    rec('stage-open', True)

    hud_hide_expr = """(function(){
      var w = document.getElementById('clPlot');
      if (!w) return {ok:true, skipped:'plot-hud 未挂载（该样本/视口下 #clPlot 不存在）'};
      var cs = getComputedStyle(w);
      return {ok: w.hidden === true && cs.display === 'none', hiddenAttr: w.hidden, display: cs.display, hasOnClass: w.classList.contains('on')};
    })()"""
    hud_hide_r = sess.eval(hud_hide_expr)
    rec('clPlot-hidden-while-stage-open (R7-G old HUD hide path)', isinstance(hud_hide_r, dict) and hud_hide_r.get('ok') is True, hud_hide_r)

    diag_expr = "(function(){ return { hasWindowGraph: typeof window.graph !== 'undefined', stageExists: !!document.getElementById('atlasStage') }; })()"
    diag = sess.eval(diag_expr)
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
    rec('keyboard-arrowdown-changes-focused-row', kb_ok, kb_r)
    sess.eval("(function(){ try { window.CLPanelManager && window.CLPanelManager.close && window.CLPanelManager.close('dock'); } catch(e){} })()")
    time.sleep(0.15)

    line_reading_ok = False
    line_reading_extra = None
    focus_dim_ok = False
    focus_dim_extra = None
    if ground.get('branchId') is not None:
        if ce == 'hide-row':
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
        result['host_wired'] = not injected
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
    2990 事件；e14f706 起缓存带 8 条 auto-main 来源线，CLStory 走严格来源路径（src=model，
    8 条主线），不是 sample-saga 那种小巧的手工 fixture；守恒断言对行数自适应，不钉线数）。
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

        open_r = sess.eval("(function(){ try { var t0 = performance.now(); window.CLAtlasStage.open(); "
                            "var t1 = performance.now(); return {ok:true, firstPaintMs: t1-t0}; } "
                            "catch(e){ return {ok:false, why:String(e&&e.stack||e)}; } })()")
        rec('stage-open', isinstance(open_r, dict) and open_r.get('ok') is True, open_r)
        first_paint_ms = open_r.get('firstPaintMs') if isinstance(open_r, dict) else None
        time.sleep(0.6)
        sess.shot('large-dafeng-01-stage-open')

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
