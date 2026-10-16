(function () {
  'use strict';

  var qs = new URLSearchParams(location.search);
  var CTX = (window.CLApp && typeof window.CLApp.internal === 'function') ? window.CLApp.internal() : null;
  if (!CTX) return;

  var WANT_CL = qs.get('probe') === '1';
  var WANT_SCALE = /[?&](autotest|test)=/.test(location.search);
  var WANT_PLANTEST = qs.get('plantest') === '1';

  window.onerror = function (msg, url, line, col) {
    document.body.dataset.jserr = (document.body.dataset.jserr || '') + '|' + msg + ' at ' + url + ':' + line + ':' + col;
  };
  window.addEventListener('unhandledrejection', function (e) {
    document.body.dataset.jsrej = (document.body.dataset.jsrej || '') + '|' + (e.reason && e.reason.message || e.reason);
  });

  if (WANT_PLANTEST) {
    var files = ['角色设定.md', '第0卷 第一卷 星落.md', '第1卷 第二卷 迷航.md', '第2卷 第三卷 归港.md'];
    Promise.all(files.map(function (f) {
      return fetch('data/demo_src/星尘信使/' + encodeURIComponent(f))
        .then(function (r) { return r.text(); })
        .then(function (t) { return { file: new File([t], f, { type: 'text/markdown' }), path: '星尘信使/' + f }; });
    })).then(function (l) { CTX.ingestInto(l, '星尘信使'); });
  }

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
