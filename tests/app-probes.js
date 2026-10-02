/* Castline · tests/app-probes.js — 生产入口之外的测试探针总成
 *
 * 来源：v5.0「澄明与雕光」M1「app.js 测试探针最终剥离」。
 * 由 `js/app.js` 尾部**唯一一处**入口判定条件注入（见那里「探针注入口」）：
 *
 *     if (TEST_ON) { <script src="tests/app-probes.js" async> }
 *
 * 因此本文件**不在默认加载链里** —— 普通访问（无 test 类参数）浏览器根本不会请求它。
 * 本文件与 `tests/app-scale.js`、`tests/headless.py` 同属测试侧资产，不参与 index.html 的 112 脚本审计。
 *
 * 迁入内容（原散落在 app.js 的 5 个位置）：
 *   1. DOM 错误采集（dataset.jserr / dataset.jsrej）
 *   2. `window.__cl` 探针 API（probe=1）
 *   3. `window.__CL_TEST_CTX__` 压测上下文 + `tests/app-scale.js` 注入（autotest/test）
 *   4. `plantest=1` 载入 demo_src 原始素材
 *
 * 与 app.js 的接线：app.js 暴露 `window.CLApp.internal()`，返回闭包内引用（含可变状态的取值器）。
 * 本文件**只读**该出口，不反向修改 app.js 的任何状态，除非某条探针本身就是为「代驱动 UI」而存在
 * （如 mount/select/setGraph，属 app-scale 压测的既有契约，逐条保留原语义）。
 */
(function () {
  'use strict';

  var qs = new URLSearchParams(location.search);
  var CTX = (window.CLApp && typeof window.CLApp.internal === 'function') ? window.CLApp.internal() : null;
  if (!CTX) return;   // app.js 未就绪 / 被裁剪：探针整体退化为 no-op，绝不抛异常污染页面

  var WANT_CL = qs.get('probe') === '1';
  var WANT_SCALE = /[?&](autotest|test)=/.test(location.search);
  var WANT_PLANTEST = qs.get('plantest') === '1';

  /* ---------------------------------------------------------------- 1. DOM 错误采集
   *
   * M1 顺带修掉的一处**真实缺陷**：原 app.js 在 :20 与 :3174 各装了一份采集器。
   * 其中 `window.onerror` 是**赋值**，后装者覆盖先装者（无害）；但
   * `unhandledrejection` 用的是 **addEventListener**，两份监听器会**同时存活** ——
   * 于是每一次 unhandled rejection 都会往 `dataset.jsrej` **追加两遍**同一段文本。
   * 凡是断言「零 rejection」的套件不受影响，但凡是想读文本内容的调用方都会拿到重复串。
   * 现在只有一份，语义从「两个监听器」收敛为「一个监听器」，**采集范围不变、内容不再重复**。
   */
  window.onerror = function (msg, url, line, col) {
    document.body.dataset.jserr = (document.body.dataset.jserr || '') + '|' + msg + ' at ' + url + ':' + line + ':' + col;
  };
  window.addEventListener('unhandledrejection', function (e) {
    document.body.dataset.jsrej = (document.body.dataset.jsrej || '') + '|' + (e.reason && e.reason.message || e.reason);
  });

  /* ---------------------------------------------------------------- 4. plantest=1
   * 载入 data/demo_src/灯下的人/ 的 4 份原始素材并送入托盘。
   * 位置前移说明：原实现在 app.js 的「启动」段（早于 demo 自动点击），迁出后变为异步注入，
   * 时序上晚于 `demo=1` 的自动点击。实测全仓**无任何套件使用 plantest**（grep 零命中），
   * 故此位移无测试语义影响；保留功能是为了不删掉这条人工调试路径。
   */
  if (WANT_PLANTEST) {
    var files = ['角色设定.md', '第0卷 第一卷 暗房.md', '第1卷 第二卷 显影.md', '第2卷 第三卷 定影.md'];
    Promise.all(files.map(function (f) {
      return fetch('data/demo_src/灯下的人/' + encodeURIComponent(f))
        .then(function (r) { return r.text(); })
        .then(function (t) { return { file: new File([t], f, { type: 'text/markdown' }), path: '灯下的人/' + f }; });
    })).then(function (l) { CTX.ingestInto(l, '灯下的人'); });
  }

  /* ---------------------------------------------------------------- 2. window.__cl（probe=1）
   * 契约：**原样保留既有键名与返回结构** —— tests/ 下有 20+ 个套件直接读 `__cl.*`，
   * 这里只搬位置，不改形状。
   */
  if (WANT_CL) {
    window.__cl = window.__cl || {};
    var api = {
      scene: CTX.scene,
      graph: function () { return CTX.G; },
      select: CTX.select, deselect: CTX.deselect, mount: CTX.mount,
      openApi: CTX.openApi, tray: CTX.CLTray,
      openLib: CTX.openLib, closeLib: CTX.closeLib, reanalyze: CTX.reanalyze,
      startRun: CTX.startRun, stopRun: CTX.stopRun, chooseBox: CTX.chooseBox, confirmBox: CTX.confirmBox,
      history: function () { return CTX.histItems; },
      timeline: function () { return CTX.TL; },
      renderTimeline: CTX.renderTimeline,
      chapterCard: CTX.chapterCard, attrCard: CTX.attrCard, hubCard: CTX.hubCard, campCard: CTX.campCard,
      selectCamp: CTX.selectCamp, openAxisEvidence: CTX.openAxisEvidence, peek: CTX.peek,
      showAxisRanking: CTX.showAxisRanking, rankingHTML: CTX.rankingHTML,
      story: function () { return CTX.story; }, plotToggle: CTX.plotToggle,
      peer: function () { return window.CLPeer ? window.CLPeer.stats() : null; },
      peerToggle: function () { return window.CLPeer ? window.CLPeer.toggle() : null; },
      plot: function () {
        var PT = CTX.story;
        return { ms: CTX.plotMs, ok: !!(PT && PT.ok), src: PT && PT.src || '', fp: PT && PT.fp || '',
          story: window.CLStory ? window.CLStory.stats() : null, tree: window.CLPlotTree ? window.CLPlotTree.stats() : null,
          nebula: window.CLNebula ? window.CLNebula.stats() : null, hud: window.CLPlotHud ? window.CLPlotHud.stats() : null,
          arcana: window.CLArcana ? window.CLArcana.plugins() : null };
      },
      // state() 全部走 internal() 的**实时取值器**：原实现读的是同一闭包变量，
      // 迁出后若在此处缓存快照就会让 tests 读到过期值，故一律现取。
      state: function () {
        var G = CTX.G;
        return { mode: CTX.scene.mode(), sel: CTX.sel, stats: CTX.scene.stats(), labels: CTX.scene.labelStats(),
          constellation: CTX.scene.constellation ? CTX.scene.constellation() : null,
          camps: G ? (G.camps || []).map(function (cp) { return cp.name + ':' + cp.stance + ':' + cp.members.length; }) : null,
          loader: !CTX.loader.classList.contains('off'), tray: CTX.CLTray.totals(), busy: CTX.busy,
          chapSel: CTX.scene.chapSel(), lib: CTX.$('library').classList.contains('on'),
          tl: CTX.TL.list.length,
          quality: G && (G.meta && (G.meta.ui_quality || G.meta.quality)) || null };
      }
    };
    for (var k in api) { if (Object.prototype.hasOwnProperty.call(api, k)) window.__cl[k] = api[k]; }
  }

  /* ---------------------------------------------------------------- 3. 压测上下文 + app-scale 注入
   * `__CL_TEST_CTX__` 的唯一消费方是 tests/app-scale.js（见其 :9），键名与可写性原样保留。
   */
  if (WANT_SCALE) {
    window.__CL_TEST_CTX__ = {
      scene: CTX.scene,
      get G() { return CTX.G; }, set G(v) { CTX.setGraph(v); },
      get GI() { return CTX.GI; }, get busy() { return CTX.busy; },
      mount: CTX.mount, select: CTX.select, deselect: CTX.deselect, stepChar: CTX.stepChar, selectCamp: CTX.selectCamp,
      campCard: CTX.campCard, hubCard: CTX.hubCard, chapterCard: CTX.chapterCard, attrCard: CTX.attrCard,
      openAxisEvidence: CTX.openAxisEvidence, openLib: CTX.openLib, closeLib: CTX.closeLib,
      renderTimeline: CTX.renderTimeline, renderIndex: CTX.renderIndex, requestPlan: CTX.requestPlan,
      loadHistory: CTX.loadHistory,
      eventsOf: CTX.eventsOf, relsOf: CTX.relsOf, tierOf: CTX.tierOf, HUD_SEL: CTX.HUD_SEL,
      $: CTX.$, peek: CTX.peek,
      NC: CTX.NC, CLTray: CTX.CLTray, CLAnalyze: CTX.CLAnalyze, qs: CTX.qs
    };
    var scr = document.createElement('script');
    scr.src = 'tests/app-scale.js';
    scr.async = true;
    document.head.appendChild(scr);
  }
})();
