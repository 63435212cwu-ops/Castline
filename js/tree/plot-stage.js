/* Castline · plot-stage.js — v31 剧数图谱骨架（no-op）
 * 这是主会话先接线用的空壳：对外形状齐全、什么都不做。
 * 正式实现由 briefs/ 里对应的单元整文件覆盖。 */
(function () {
  'use strict';
  var API = {
    name: 'plot-stage',
    build: function () { return null; },
    update: function () {},
    dispose: function () {},
    setOn: function () {},
    setTree: function () {},
    show: function () {},
    visible: function () { return false; },
    compute: function () { return { ok: false, reason: 'skeleton', forks: [], warn: [], fp: '', stats: { forks: 0, born: 0, promoted: 0, ms: 0, fp: '', ok: false } }; },
    get: function () { return null; },
    enter: function () { return false; },
    exit: function () { return false; },
    toggle: function () { return false; },
    active: function () { return false; },
    stats: function () { return { ready: false, skeleton: true }; }
  };
  window.CLPlotStage = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
