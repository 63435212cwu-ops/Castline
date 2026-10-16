(function (g) {
  'use strict';
  var doc = g.document;
  if (!doc || !doc.body) return;

  var BC = doc.body.classList, U = null, plotOn = false, cardHost = null, cardObs = null;
  var compOn = false, rain = null, rainHost = null, pend = 0, flowed = false, hooked = null;
  var st = { plots: 0, nums: 0, titles: 0, cards: 0, skipped: 0, comps: 0, flows: 0, axes: 0, unfolds: 0 };

  function util() { return U || (U = g.CLSkyUtil); }
  function TK() { return g.CLSkyTokens; }
  function still() {
    var T = TK();
    if (T && T.reduced && T.reduced()) return true;
    var d = doc.querySelector('.skd-loader') || doc.body;
    if (BC.contains('skylab-still')) return true;
    return d.getAttribute && d.getAttribute('data-tier') === 'low';
  }

  function discSvg() { return doc.querySelector('svg.sky-disc'); }

  function typeNums(svg) {
    var ns = svg.querySelectorAll('.sd-num'), i;
    for (i = 0; i < ns.length; i++) {
      ns[i].style.setProperty('--i', i);
      ns[i].classList.add('is-typing');
    }
    st.nums += ns.length;
  }

  function clearDisc(svg) {
    var all = svg.querySelectorAll('.is-typing'), i;
    for (i = 0; i < all.length; i++) { all[i].classList.remove('is-typing'); }
  }

  function onPlot(on) {
    var svg;
    if (on === plotOn) return;
    plotOn = on;
    svg = discSvg();
    if (!svg) return;
    if (!on) { clearDisc(svg); return; }
    if (still()) { st.skipped++; return; }
    st.plots++;
    typeNums(svg);
  }

  function flowItems(who) {
    var G = g.CLApp && CLApp.graph && CLApp.graph(), out = [], seen = {}, rs, i, r, o, ev;
    if (!G || !who) return out;
    rs = G.relations || [];
    for (i = 0; i < rs.length && out.length < 14; i++) {
      r = rs[i]; o = r.a === who ? r.b : r.b === who ? r.a : null;
      if (!o || seen[o]) continue;
      seen[o] = 1; out.push(o);
    }
    ev = G.events || [];
    for (i = 0; i < ev.length && out.length < 22; i++) {
      if (!ev[i] || !ev[i].title || !ev[i].characters) continue;
      if (ev[i].characters.indexOf(who) >= 0) out.push(ev[i].title);
    }
    return out;
  }

  function crownCenter() {
    var S = g.CLApp && CLApp.scene && CLApp.scene(), b = S && S.crownScreenBounds ? S.crownScreenBounds() : null;
    if (!b || !(b.right > b.left) || !(b.bottom > b.top)) return null;
    return [(b.left + b.right) / 2, (b.top + b.bottom) / 2];
  }

  function typeAxes() {
    var ls = doc.querySelectorAll('#labels .cl-lab.gem-slot .ln'), u = util(), i, t;
    if (!u || !u.type || !ls.length) return false;
    for (i = 0; i < ls.length; i++) {
      t = ls[i];
      if (t.__fused || !t.textContent) continue;
      t.__fused = 1;
      t.style.setProperty('--type-d0', (i * 0.035).toFixed(3) + 's');
      u.type(t, t.textContent, { caret: false });
      st.axes++;
    }
    return true;
  }

  function tryCompass() {
    var c, items, who, done = true;
    if (!typeAxes()) done = false;
    who = g.CLSky && CLSky.state ? CLSky.state().compass : null;
    c = crownCenter();
    items = flowItems(who);
    if (c && items.length && g.CLSkyRain) {
      if (!rain) {
        rainHost = doc.querySelector('.sky-shell') || doc.body;
        rain = g.CLSkyRain.mount(rainHost, { cls: 'is-compass' });
      }
      if (rain && !flowed) { flowed = true; st.flows += rain.converge(items, c[0], c[1]) || 0; }
    } else { done = false; }
    return done;
  }

  function tick(dt) {
    if (pend <= 0) return;
    pend -= (dt > 0 && dt < 1) ? dt : 0.016;
    if (!compOn) { pend = 0; return; }
    tryCompass();
  }

  function hookScene() {
    var sc = g.CLScene && CLScene.current;
    if (!sc || !sc.registerFrameHook || sc === hooked) return;
    hooked = sc; sc.registerFrameHook(tick);
  }

  function onCompass(on) {
    if (on === compOn) return;
    compOn = on;
    if (!on) { pend = 0; flowed = false; if (rain) rain.clear(); return; }
    if (still()) { st.skipped++; return; }
    st.comps++;
    flowed = false;
    hookScene();
    pend = 4;
    tryCompass();
  }

  function dressCard(card) {
    var t, u;
    if (!card || card.__fused) return;
    card.__fused = 1;
    if (still()) { st.skipped++; return; }
    card.classList.add('is-fused');
    st.cards++;
    t = card.querySelector('.skd-card__title');
    u = util();
    if (t && u && u.type && t.textContent && !t.children.length) {
      u.type(t, t.textContent, { caret: false });
      t.classList.add('is-glint');
      st.titles++;
    }
  }

  function scanCards(root) {
    var cs = root.querySelectorAll ? root.querySelectorAll('.skd-card') : [], i;
    if (root.classList && root.classList.contains('skd-card')) dressCard(root);
    for (i = 0; i < cs.length; i++) dressCard(cs[i]);
  }

  /* ── 接线：body 类变化认星盘开关；卡片宿主认新卡 ───────────── */
  function wireCards() {
    var host = doc.getElementById('skyCard');
    if (!host || host === cardHost) return;
    cardHost = host;
    if (cardObs) cardObs.disconnect();
    cardObs = new MutationObserver(function (recs) {
      var i, j, n;
      for (i = 0; i < recs.length; i++) {
        for (j = 0; j < recs[i].addedNodes.length; j++) {
          n = recs[i].addedNodes[j];
          if (n.nodeType === 1) scanCards(n);
        }
      }
    });
    cardObs.observe(cardHost, { childList: true, subtree: true });
    scanCards(cardHost);
  }

  var decks = [];
  function onUnfold(bd) {
    var c = bd.parentNode, nm = c && c.querySelector('.skd-card__name'), u = util(), t, tt;
    if (!nm || !(t = nm.textContent)) return;
    if (still() || !u || !u.type) { st.skipped++; return; }
    tt = u.type(nm, t, { cps: 36 });
    nm.classList.add('is-glint'); c.classList.add('is-unfold');
    st.unfolds++;
    setTimeout(function () {
      if (nm.textContent === t) { nm.textContent = t; nm.classList.remove('skd-type', 'is-glint'); }
      c.classList.remove('is-unfold');
    }, Math.round(tt * 1000) + 900);
  }
  function wireDecks() {
    var hs = doc.querySelectorAll('.skd-deck, .skg-deck'), i;
    for (i = 0; i < hs.length; i++) {
      if (decks.indexOf(hs[i]) >= 0) continue;
      decks.push(hs[i]);
      new MutationObserver(function (recs) {
        var a, b, n;
        for (a = 0; a < recs.length; a++) for (b = 0; b < recs[a].addedNodes.length; b++) {
          n = recs[a].addedNodes[b];
          if (n.nodeType === 1 && (n.classList.contains('skd-card__body') || n.classList.contains('skg-card__body'))) onUnfold(n);
        }
      }).observe(hs[i], { childList: true, subtree: true });
    }
  }

  new MutationObserver(function () {
    onPlot(BC.contains('sky-plot-on'));
    onCompass(BC.contains('sky-compass-on'));
    wireCards(); wireDecks(); wireHud();
  }).observe(doc.body, { attributes: true, attributeFilter: ['class'], childList: true });
  var hudEl = null;
  function wireHud() {
    var h = doc.getElementById('skyHud');
    if (!h || h === hudEl) return;
    hudEl = h;
    new MutationObserver(function () { wireCards(); wireDecks(); }).observe(h, { childList: true });
  }
  wireHud();

  wireCards(); wireDecks();
  onPlot(BC.contains('sky-plot-on'));
  onCompass(BC.contains('sky-compass-on'));

  g.CLSkyOpenFuse = {
    stats: function () { var o = {}, k; for (k in st) o[k] = st[k]; o.plotOn = plotOn; o.compOn = compOn; o.rain = !!rain; o.cardHost = !!cardHost; o.glRings = BC.contains('skd-gl'); return o; },
    rescan: function () { plotOn = false; wireCards(); wireDecks(); onPlot(BC.contains('sky-plot-on')); return this.stats(); }
  };
})(window);
