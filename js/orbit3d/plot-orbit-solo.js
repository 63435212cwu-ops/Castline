(function (global) {
  'use strict';

  var VERSION = '46.1.0';
  var POLL = 250;
  var STYLE_ID = 'clOrbitSoloCss';
  var STYLE_CSS = '#clTreeGate,#clTreeLegend,#clTreeRead,#clTreeEventCard,#clTreeMarks,#clTreeTimeline,#clTwigTip,#clNarrate,#clPlotCastLab,.cl-pcst{display:none!important}';

  var stats = {
    hiddenRoot: 0,
    exits: 0,
    wrapped: [],
    blockedPlotline: 0
  };

  var disabled = (global.location && global.location.search || '').indexOf('tree=1') !== -1 || (global.location && global.location.search || '').indexOf('treestage=1') !== -1;

  function snapshot() {
    var o = {
      hiddenRoot: stats.hiddenRoot,
      exits: stats.exits,
      wrapped: stats.wrapped.slice(0),
      blockedPlotline: stats.blockedPlotline
    };
    if (disabled) { o.disabled = true; }
    return o;
  }

  if (disabled) {
    global.CLPlotOrbitSolo = { stats: snapshot, version: VERSION };
    return;
  }

  var doc = global.document;
  var mark = {};
  var styleDone = false;

  function isObj(v) { return typeof v !== 'undefined' && v !== null; }

  function note(tag) {
    if (!mark[tag]) { mark[tag] = true; stats.wrapped.push(tag); }
  }

  function wrapSetOnFalse(obj, tag) {
    if (mark[tag]) return;
    if (!isObj(obj) || typeof obj.setOn !== 'function') return;
    note(tag);
    var orig = obj.setOn;
    obj.setOn = function () { return orig.call(this, false); };
  }

  function wrapMigrateSetOn(obj, tag) {
    if (mark[tag]) return;
    if (!isObj(obj) || typeof obj.setOn !== 'function') return;
    note(tag);
    var orig = obj.setOn;
    obj.setOn = function (v) {
      if (v) return;
      return orig.apply(this, arguments);
    };
  }

  function wrapNoopFalse(obj, key, tag) {
    if (mark[tag]) return;
    if (!isObj(obj) || typeof obj[key] !== 'function') return;
    note(tag);
    obj[key] = function () { return false; };
  }

  function wrapGate(obj) {
    if (!isObj(obj)) return;
    if (!mark.clTreeGateShowFalse) {
      mark.clTreeGateShowFalse = true;
      if (typeof obj.show === 'function') {
        try { obj.show(false); } catch (e) {  }
      }
    }
    if (!mark.clTreeGateShow) {
      if (typeof obj.show === 'function') {
        note('CLTreeGate.show');
        obj.show = function () { return false; };
      }
    }
  }

  function injectStyle() {
    if (styleDone || !doc || !doc.head) return;
    if (doc.getElementById(STYLE_ID)) { styleDone = true; return; }
    var s = doc.createElement('style');
    s.id = STYLE_ID;
    s.textContent = STYLE_CSS;
    doc.head.appendChild(s);
    styleDone = true;
  }

  function stepAnchor() {
    var A = global.CLTreeAnchor;
    if (!isObj(A)) return;
    wrapSetOnFalse(A, 'CLTreeAnchor.setOn');
    if (typeof A.root !== 'function') return;
    var root = A.root();
    if (root && root.visible !== false) {
      root.visible = false;
      stats.hiddenRoot++;
    }
  }

  function stepStage() {
    var S = global.CLTreeStage;
    var quoted = !!(doc && doc.body && doc.body.classList && doc.body.classList.contains('cl-treestage'));
    var active = false;
    if (isObj(S) && typeof S.active === 'function') {
      try { active = !!S.active(); } catch (e) { active = false; }
    }
    if (!active && !quoted) return;
    if (isObj(S) && typeof S.exit === 'function') {
      try { S.exit(); stats.exits++; } catch (e2) {  }
    }
  }

  function stepUI() {
    injectStyle();
    wrapNoopFalse(global.CLPlotTree, 'show', 'CLPlotTree.show');
    wrapNoopFalse(global.CLPlotHud, 'toggle', 'CLPlotHud.toggle');
    wrapNoopFalse(global.CLPlotHud, 'show', 'CLPlotHud.show');
    wrapGate(global.CLTreeGate);
  }

  function stepStars() {
    wrapSetOnFalse(global.CLStarGhost, 'CLStarGhost.setOn');
    wrapMigrateSetOn(global.CLStarMigrate, 'CLStarMigrate.setOn');
  }

  function tick() {
    try {
      stepAnchor();
      stepStage();
      stepUI();
      stepStars();
    } catch (e) {  }
  }

  if (doc && doc.addEventListener) {
    doc.addEventListener('cl:tree-plotline', function (e) {
      try {
        if (e && typeof e.stopImmediatePropagation === 'function') {
          e.stopImmediatePropagation();
        }
      } catch (err) {  }
      stats.blockedPlotline++;
      try {
        if (global.CLPlot && typeof global.CLPlot.toggle === 'function') {
          global.CLPlot.toggle();
        }
      } catch (err2) {  }
    }, true);
  }

  global.CLPlotOrbitSolo = { stats: snapshot, version: VERSION };

  tick();

  if (typeof global.requestAnimationFrame === 'function') {
    (function loop() {
      if (global.CLSky && global.CLSky.enabled && global.CLSky.enabled()) return;
      tick();
      global.requestAnimationFrame(loop);
    })();
  } else {
    global.setInterval(tick, POLL);
  }
})(typeof window !== 'undefined' ? window : this);
