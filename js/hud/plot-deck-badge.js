/* @role component · @owns js/plot-deck-badge.js · @budget dom_nodes=2 js_ms=0.03 · @contract v47+v51 */
(function (g, d) {
  'use strict';

  var NAME = 'plot-deck-badge';
  var VERSION = '51';
  var SEL_DECK = '.cl-o3-deck';
  var SEL_TOP = '.cl-o3-deck__top';
  var CLS = 'cl-o3-deck__badge';
  var MAX_SHORT = 7;
  var LOW_CORES = 4;

  var el = null;
  var node = null;
  var curKind = null;
  var curTier = null;
  var curText = null;
  var lineId = null;
  var changes = 0;
  var lastReduced = null;
  var hookedView = null;
  var registeredArcana = false;

  function isReduced() {
    var L = g.CLOrbit3DLayer;
    if (L && typeof L.stats === 'function') {
      var s = L.stats();
      if (s && typeof s.reduced === 'boolean') return s.reduced;
    }
    var low = false;
    var mq = false;
    try { low = !!(g.navigator && g.navigator.hardwareConcurrency && g.navigator.hardwareConcurrency <= LOW_CORES); } catch (e) {}
    try { mq = !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e2) {}
    return !!(low || mq);
  }

  function escaped() {
    try {
      if (g.CLBadgeEscape === true) return true;
      var q = g.location && g.location.search;
      if (typeof q === 'string' && /[?&]clbadge=off(?:&|$)/.test(q)) return true;
    } catch (e) {}
    return false;
  }

  function computeTier(t, n) {
    if (!t) return 'low';
    if (t.tier) return t.tier;
    if (t.kind === 'main') {
      return (n === 1) ? 'legend' : 'hi';
    }
    var len = (typeof t.len === 'number' && t.len > 0) ? t.len : ((t.events && t.events.length) || 0);
    if (len >= 10) return 'hi';
    if (len >= 6) return 'up';
    if (len >= 3) return 'mid';
    return 'low';
  }

  function ensure() {
    if (el && el.parentNode) return true;
    var deck = d.querySelector(SEL_DECK);
    if (!deck) return false;
    el = d.createElement('div');
    el.className = CLS;
    el.setAttribute('data-kind', 'none');
    el.setAttribute('data-tier', 'low');
    node = d.createElement('b');
    el.appendChild(node);
    var top = deck.querySelector(SEL_TOP);
    if (top && top.parentNode === deck) deck.insertBefore(el, top);
    else deck.insertBefore(el, deck.firstChild);
    curKind = null;
    curTier = null;
    curText = null;
    return true;
  }

  function set(kind, text, id, tier) {
    lineId = id || null;
    var changed = false;
    if (kind !== curKind) {
      curKind = kind;
      if (el) el.setAttribute('data-kind', kind);
      changed = true;
    }
    var targetTier = tier || (kind === 'main' ? 'legend' : (kind === 'branch' ? 'mid' : 'low'));
    if (targetTier !== curTier) {
      curTier = targetTier;
      if (el) el.setAttribute('data-tier', targetTier);
      changed = true;
    }
    if (text !== curText) {
      curText = text;
      if (node) node.textContent = text;
      changed = true;
    }
    if (changed) changes++;
  }

  function short(t) {
    var title = (t && (t.title || t.lead || t.id)) || '';
    var lead = (t && t.lead) || '';
    if (lead && title.indexOf(lead + ' · ') === 0) title = title.slice(lead.length + 3);
    if (typeof title.trim === 'function') title = title.trim();
    if (!title) title = (t && (t.lead || t.id)) || (t && t.kind === 'main' ? '主线' : '支线');
    if (title.length > MAX_SHORT) title = title.slice(0, MAX_SHORT) + '…';
    return title;
  }

  function mainPos(V, id) {
    var lay = (V && typeof V.layout === 'function') ? V.layout() : null;
    var list = lay && lay.threads;
    if (!list || !list.length) return 0;
    var mains = [];
    var i;
    for (i = 0; i < list.length; i++) {
      if (list[i] && list[i].kind === 'main') mains.push(list[i]);
    }
    mains.sort(function (a, b) {
      if (typeof b.aStart === 'number' && typeof a.aStart === 'number' && b.aStart !== a.aStart) {
        return b.aStart - a.aStart;
      }
      var aSeg = typeof a.seg === 'number' ? a.seg : 0;
      var bSeg = typeof b.seg === 'number' ? b.seg : 0;
      return aSeg - bSeg;
    });
    for (i = 0; i < mains.length; i++) {
      if (mains[i].id === id) return i + 1;
    }
    return 0;
  }

  function hookView(V) {
    if (!V || hookedView === V || typeof V.on !== 'function') return;
    hookedView = V;
    try {
      V.on('focus', function () { frame(); });
      V.on('thread', function () { frame(); });
      V.on('mode', function () { frame(); });
      V.on('frame', function () { frame(); });
    } catch (e) {}
  }

  function hookArcana() {
    if (registeredArcana) return;
    var A = g.CLArcana;
    if (A && typeof A.register === 'function') {
      try {
        A.register({
          name: NAME,
          version: VERSION,
          build: function () { frame(); },
          update: function () { frame(); }
        });
        registeredArcana = true;
      } catch (e) {}
    }
  }

  function frame() {
    if (escaped()) {
      if (el && el.parentNode) {
        el.parentNode.removeChild(el);
        el = null;
        node = null;
      }
      return;
    }
    if (!ensure()) return;

    var reduced = isReduced();
    if (reduced !== lastReduced) {
      lastReduced = reduced;
      if (el) el.setAttribute('data-motion', reduced ? 'off' : 'on');
    }

    var V = g.CLPlotOrbitView;
    var D = g.CLPlotDeck;
    if (!V) { set('none', '', null); return; }

    hookView(V);
    hookArcana();

    var ds = (D && typeof D.stats === 'function') ? D.stats() : null;
    var st = (typeof V.state === 'function') ? V.state() : null;

    var id = null;

    // 1. 优先从当前事件焦点推导所属线（事件态 / 讲述态高优）
    var ev = null;
    if (st && typeof st.focusEv === 'number' && st.focusEv >= 0) {
      ev = st.focusEv;
    } else if (ds && typeof ds.ev === 'number' && ds.ev >= 0) {
      ev = ds.ev;
    }

    if (ev !== null && typeof V.eventAt === 'function') {
      var e = V.eventAt(ev);
      if (e) id = e.lineId || (e.lineIds && e.lineIds[0]);
    }

    // 2. 若无事件焦点，检查线聚焦状态（支线 / 主线聚焦态）
    if (!id && st && st.thread) {
      id = st.thread;
    }

    // 3. 讲述态兜底：若仍无选中，由当前讲述事件或首个序位事件推导，保证讲述态下徽记始终有效
    if (!id) {
      var fallbackEv = (ds && typeof ds.ev === 'number' && ds.ev >= 0) ? ds.ev : null;
      if (fallbackEv === null && typeof V.orderList === 'function') {
        var ord = V.orderList();
        if (ord && ord.length) fallbackEv = ord[0];
      }
      if (fallbackEv !== null && typeof V.eventAt === 'function') {
        var fe = V.eventAt(fallbackEv);
        if (fe) id = fe.lineId || (fe.lineIds && fe.lineIds[0]);
      }
    }

    // 4. 根据当前所属线更新徽记文本与 data-kind / data-tier
    if (id && typeof V.threadAt === 'function') {
      var t = V.threadAt(id);
      if (t) {
        if (t.kind === 'main') {
          var n = mainPos(V, id) || ((typeof t.seg === 'number' && t.seg >= 0) ? (t.seg + 1) : 1);
          var mainTier = computeTier(t, n);
          set('main', '主线 · 第 ' + n + ' 段 · ' + short(t), id, mainTier);
          return;
        } else {
          var len = (typeof t.len === 'number' && t.len > 0) ? t.len : ((t.events && t.events.length) || 0);
          var branchTier = computeTier(t, 0);
          set('branch', '支线 · ' + short(t) + ' · ' + len + ' 事件', id, branchTier);
          return;
        }
      }
    }

    // 5. 兜底回退：若从 layout 中存在主线，默认呈现首段主线徽记
    if (typeof V.layout === 'function') {
      var lay = V.layout();
      var ths = lay && lay.threads;
      if (ths && ths.length) {
        var firstMain = null;
        for (var mi = 0; mi < ths.length; mi++) {
          if (ths[mi] && ths[mi].kind === 'main') { firstMain = ths[mi]; break; }
        }
        if (firstMain) {
          set('main', '主线 · 第 1 段 · ' + short(firstMain), firstMain.id, 'legend');
          return;
        }
      }
    }

    set('none', '', null, 'low');
  }

  function refresh() {
    if (ensure()) frame();
    return stats();
  }

  function stats() {
    return {
      name: NAME,
      version: VERSION,
      ready: !!(el && el.parentNode),
      kind: curKind || 'none',
      tier: curTier || 'low',
      text: curText || '',
      lineId: lineId,
      changes: changes,
      reduced: lastReduced === null ? isReduced() : lastReduced
    };
  }

  g.CLPlotDeckBadge = { name: NAME, version: VERSION, refresh: refresh, stats: stats };

  function boot() {
    if (escaped()) return;
    hookArcana();
    if (g.CLPlotOrbitView) hookView(g.CLPlotOrbitView);
    frame();
    if (typeof g.requestAnimationFrame === 'function') {
      var pollCount = 0;
      var poll = function () {
        frame();
        pollCount++;
        if (pollCount < 60) g.requestAnimationFrame(poll);
      };
      g.requestAnimationFrame(poll);
    }
  }

  if (d.readyState === 'loading') {
    d.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
}(typeof window !== 'undefined' ? window : this, typeof document !== 'undefined' ? document : {}));
