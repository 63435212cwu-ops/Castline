(function (g) {
  'use strict';
  var doc = g.document, MO = g.MutationObserver;
  if (!doc || !doc.body || !MO) return;
  if (/[?&]cine=0(?:&|$)/.test(g.location && g.location.search || '')) return;

  var IDS = ['skyDeconPanel', 'skyStoryPanel', 'skySearchPanel', 'skyEnrichPanel'];
  var STAT_IDS = ['stChar', 'stChap', 'stFib', 'stEv', 'stTh', 'cmCount', 'skySub', 'idxCount'];
  var IN_MS = 1500, SWAP_MS = 760, DETAIL_MS = 460, WARP_MS = 1160, LOCK_MS = 640, ROWS = 18;
  var ROW_SEL = [
    '.sd-person', '.sd-line', '.sd-event', '.sd-evidence-summary', '.sd-evidence-detail',
    '.sd-arc', '.sd-attribute', '.sd-mechanics-card', '.sd-structure-link', '.sd-coverage-layer',
    '.sd-citation-card', '.sd-position-boundary', '.sd-review-note',
    '.ssp-section', '.sks-option', '.m86-slot', '.m89-card',
    '.sd-section > ul > li', '.sd-section > ol > li',
    '.rel', '.xc', '.mc', '.arc > li', '.tl > li', '.rd-bar'
  ].join(', ');
  var TAB_SEL = '.sd-tabs > button, .sd-mechanics-tabs > button, .sd-structure-layers > button, .sd-coverage-layers > button, .ssp-beat-rail > span, #dockToc > a';
  var DETAIL_SEL = '.sd-person-detail, .sd-shared-citation, .sd-position-explanation, .sks-detail';
  var SPOT_SEL = '#skyDeconPanel, #skyStoryPanel, #skySearchPanel, #skyEnrichPanel';

  var BC = doc.body.classList;
  var st = {
    opens: 0, swaps: 0, skipped: 0, warps: 0, locks: 0,
    cards: 0, unfolds: 0, pulses: 0, details: 0, spots: 0
  };
  var watched = {}, detailSigs = {}, statSigs = {};
  var stageEl = null, reticleEl = null, warpT = 0, lockT = 0;
  var prevPlot = BC.contains('sky-plot-on'), prevCompass = BC.contains('sky-compass-on');
  var spotHost = null, spotRect = null;

  function still() {
    var T = g.CLSkyTokens;
    if (T && T.reduced && T.reduced()) return true;
    if (g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches) return true;
    if (BC.contains('skylab-still')) return true;
    var d = doc.querySelector('.skd-loader') || doc.body;
    return (d.getAttribute && d.getAttribute('data-tier') === 'low') ||
      doc.body.getAttribute('data-tier') === 'low' ||
      (doc.documentElement && doc.documentElement.getAttribute('data-tier') === 'low');
  }

  function shown(p) {
    return !!(p && !p.hidden && p.getAttribute('aria-hidden') !== 'true' &&
      !p.classList.contains('skd-pm-out') && !p.classList.contains('is-hidden'));
  }

  function transientClass(el, cls, ms, key) {
    if (!el) return;
    if (still()) { st.skipped++; return; }
    var k = key || ('__cineT_' + cls);
    if (el[k]) g.clearTimeout(el[k]);
    var had = el.classList.contains(cls);
    el.classList.remove(cls);
    if (had) void el.offsetWidth;
    el.classList.add(cls);
    el[k] = g.setTimeout(function () {
      el[k] = 0;
      el.classList.remove(cls);
    }, ms);
  }

  function setStagger(nodes, limit) {
    var i, n = nodes ? nodes.length : 0, max = limit || 16;
    for (i = 0; i < n; i++) {
      nodes[i].style.setProperty('--ci', String(i < max ? i : max));
    }
  }

  function ensureStage() {
    if (stageEl && stageEl.parentNode) return stageEl;
    stageEl = doc.getElementById('skyCinemaStage');
    if (!stageEl) {
      stageEl = doc.createElement('div');
      stageEl.id = 'skyCinemaStage';
      stageEl.className = 'skd-cine-stage';
      stageEl.setAttribute('aria-hidden', 'true');
      var parts = ['iris', 'flare', 'rings', 'beams', 'scan', 'frame', 'reticle'], i, ch;
      for (i = 0; i < parts.length; i++) {
        ch = doc.createElement('div');
        ch.className = 'skd-cine-stage__' + parts[i];
        if (parts[i] === 'reticle') reticleEl = ch;
        stageEl.appendChild(ch);
      }
      doc.body.appendChild(stageEl);
    } else {
      reticleEl = stageEl.querySelector('.skd-cine-stage__reticle');
    }
    return stageEl;
  }

  function setStageOrigin(x, y) {
    var s = ensureStage();
    var vw = Math.max(1, g.innerWidth || 1440), vh = Math.max(1, g.innerHeight || 900);
    var rx = typeof x === 'number' && isFinite(x) ? ((x / vw) * 100).toFixed(1) + '%' : '50%';
    var ry = typeof y === 'number' && isFinite(y) ? ((y / vh) * 100).toFixed(1) + '%' : '50%';
    s.style.setProperty('--cine-rx', rx);
    s.style.setProperty('--cine-ry', ry);
  }

  var WARP_CLASSES = ['is-warp-intro', 'is-warp-plot', 'is-warp-compass', 'is-warp-return', 'is-warp-regroup', 'is-pulse-panel'];
  function triggerWarp(kind, x, y) {
    if (still()) { st.skipped++; return; }
    var s = ensureStage();
    var cls = 'is-' + (kind || 'warp-plot');
    setStageOrigin(x, y);
    if (warpT) g.clearTimeout(warpT);
    var running = false, i;
    for (i = 0; i < WARP_CLASSES.length; i++) {
      if (s.classList.contains(WARP_CLASSES[i])) {
        running = true;
        s.classList.remove(WARP_CLASSES[i]);
      }
    }
    if (running) void s.offsetWidth;
    s.classList.add(cls);
    st.warps++;
    warpT = g.setTimeout(function () {
      warpT = 0;
      s.classList.remove(cls);
    }, WARP_MS);
  }

  function lockReticle(x, y) {
    if (still()) { st.skipped++; return; }
    var s = ensureStage();
    if (!reticleEl) return;
    setStageOrigin(x, y);
    if (lockT) g.clearTimeout(lockT);
    var running = reticleEl.classList.contains('is-lock');
    reticleEl.classList.remove('is-lock');
    s.classList.add('is-lock-active');
    if (running) void reticleEl.offsetWidth;
    reticleEl.classList.add('is-lock');
    st.locks++;
    lockT = g.setTimeout(function () {
      lockT = 0;
      reticleEl.classList.remove('is-lock');
      s.classList.remove('is-lock-active');
    }, LOCK_MS);
  }

  function sig(p) {
    var t = p.querySelector('.sd-tabs .is-on, .sd-mechanics-tabs .is-on, #dockToc .on');
    var h = p.querySelector('.sd-section-head b, .sd-section-head, .ssp-head h2, #dockHead h2, h2, h3');
    var d = p.querySelector('.sd-person-detail [data-person-name], .sd-person-detail b, .ssp-head small');
    return [(t && t.textContent) || '', (h && h.textContent) || '', (d && d.textContent) || ''].join('|');
  }

  function index(p) {
    var i, kids = p.children;
    for (i = 0; i < kids.length; i++) kids[i].style.setProperty('--ci', String(i));
    var tabs = p.querySelectorAll(TAB_SEL);
    for (i = 0; i < tabs.length; i++) tabs[i].style.setProperty('--ci', String(i));
    var rows = p.querySelectorAll(ROW_SEL);
    for (i = 0; i < rows.length; i++) {
      if (i < ROWS) {
        rows[i].style.setProperty('--ci', String(i));
        rows[i].classList.add('skd-cine-row');
      } else {
        rows[i].classList.remove('skd-cine-row');
      }
    }
  }

  function clearRows(p) {
    var rows = p.querySelectorAll('.skd-cine-row');
    for (var i = 0; i < rows.length; i++) rows[i].classList.remove('skd-cine-row');
  }

  function checkDetails(p) {
    if (still()) return;
    var ds = p.querySelectorAll(DETAIL_SEL), i, d, key, s;
    for (i = 0; i < ds.length; i++) {
      d = ds[i];
      if (d.hidden) continue;
      key = (p.id || 'p') + ':' + i + ':' + (d.className || '');
      s = (d.textContent || '').slice(0, 80);
      if (detailSigs[key] !== s) {
        detailSigs[key] = s;
        st.details++;
        transientClass(d, 'skd-cine-detail-in', DETAIL_MS);
      }
    }
  }

  function play(p, kind) {
    var w = watched[p.id];
    if (!w) return;
    if (still()) { st.skipped++; return; }
    g.clearTimeout(w.timer);
    var running = p.classList.contains('skd-cine-in') || p.classList.contains('skd-cine-swap');
    p.classList.remove('skd-cine-in', 'skd-cine-swap');
    index(p);
    if (running) void p.offsetWidth;
    p.classList.add(kind);
    if (kind === 'skd-cine-in') {
      st.opens++;
      triggerWarp('pulse-panel');
    } else {
      st.swaps++;
    }
    checkDetails(p);
    w.timer = g.setTimeout(function () {
      p.classList.remove(kind);
      clearRows(p);
    }, kind === 'skd-cine-in' ? IN_MS : SWAP_MS);
  }

  function watch(p) {
    if (!p || !p.id || watched[p.id]) return;
    var w = watched[p.id] = { open: shown(p), sig: shown(p) ? sig(p) : '', timer: 0 };
    new MO(function () {
      var now = shown(p);
      if (now && !w.open) {
        w.open = true;
        w.sig = sig(p);
        play(p, 'skd-cine-in');
        return;
      }
      if (!now) {
        w.open = false;
        return;
      }
      var s = sig(p);
      if (s !== w.sig) {
        w.sig = s;
        if (!p.classList.contains('skd-cine-in')) play(p, 'skd-cine-swap');
      } else {
        checkDetails(p);
      }
    }).observe(p, { attributes: true, attributeFilter: ['hidden', 'class', 'aria-hidden'], childList: true, subtree: true });
  }

  var cardWired = null, cardSig = '';
  function wireHoverCard() {
    var c = doc.getElementById('skyCard');
    if (!c || c === cardWired) return;
    cardWired = c;
    new MO(function () {
      if (c.hidden) { cardSig = ''; return; }
      var t = c.querySelector('.skd-card__title');
      var ns = (t ? t.textContent : c.textContent || '').slice(0, 48);
      if (ns && ns !== cardSig) {
        cardSig = ns;
        if (still()) { st.skipped++; return; }
        var chips = c.querySelectorAll('.skd-cast__chip');
        setStagger(chips, 12);
        st.cards++;
        transientClass(c, 'skd-cine-card-in', 560);
      }
    }).observe(c, { attributes: true, attributeFilter: ['hidden'], childList: true, subtree: true });
  }

  var pickWired = null;
  function wirePickPanel() {
    var pk = doc.getElementById('skyPickPanel');
    if (!pk || pk === pickWired) return;
    pickWired = pk;
    new MO(function () {
      if (pk.hidden) return;
      if (still()) { st.skipped++; return; }
      var items = pk.querySelectorAll('[data-pick-index]');
      setStagger(items, 12);
      transientClass(pk, 'skd-cine-pick-in', 520);
    }).observe(pk, { attributes: true, attributeFilter: ['hidden'], childList: true });
  }

  var deckHosts = [];
  function wireDecks() {
    var hs = doc.querySelectorAll('.skd-deck, .skg-deck'), i;
    for (i = 0; i < hs.length; i++) {
      if (deckHosts.indexOf(hs[i]) >= 0) continue;
      deckHosts.push(hs[i]);
      new MO(function (recs) {
        var a, b, n;
        for (a = 0; a < recs.length; a++) {
          for (b = 0; b < recs[a].addedNodes.length; b++) {
            n = recs[a].addedNodes[b];
            if (n.nodeType === 1 && (n.classList.contains('skd-card__body') || n.classList.contains('skg-card__body'))) {
              if (still()) { st.skipped++; continue; }
              st.unfolds++;
              transientClass(n, 'skd-cine-unfold', 620);
            }
          }
        }
      }).observe(hs[i], { childList: true, subtree: true });
    }
  }

  var crumbWired = null, playerWired = null, captionWired = null, captionSig = '';
  function wireHudControls() {
    var crumb = doc.getElementById('skyCrumb');
    if (crumb && crumb !== crumbWired) {
      crumbWired = crumb;
      new MO(function () {
        if (!crumb.hidden) transientClass(crumb, 'skd-cine-crumb-in', 560);
      }).observe(crumb, { attributes: true, attributeFilter: ['hidden'] });
    }
    var player = doc.getElementById('skyPlayer');
    if (player && player !== playerWired) {
      playerWired = player;
      new MO(function () {
        if (!player.hidden) transientClass(player, 'skd-cine-player-in', 520);
      }).observe(player, { attributes: true, attributeFilter: ['hidden'] });
    }
    var cap = doc.getElementById('skyCaption');
    if (cap && cap !== captionWired) {
      captionWired = cap;
      new MO(function () {
        var s = cap.textContent || '';
        if (s && s !== captionSig) {
          captionSig = s;
          transientClass(cap, 'skd-cine-caption-flip', 340);
        }
      }).observe(cap, { childList: true, characterData: true, subtree: true });
    }

    var i, id, statEl;
    for (i = 0; i < STAT_IDS.length; i++) {
      id = STAT_IDS[i];
      statEl = doc.getElementById(id);
      if (statEl && !statEl.__cineStatWired) {
        statEl.__cineStatWired = 1;
        statSigs[id] = statEl.textContent || '';
        (function (el, key) {
          new MO(function () {
            var s = el.textContent || '';
            if (s && s !== statSigs[key]) {
              statSigs[key] = s;
              st.pulses++;
              transientClass(el, 'skd-cine-stat-pulse', 540);
            }
          }).observe(el, { childList: true, characterData: true, subtree: true });
        })(statEl, id);
      }
    }
  }

  var iaWired = null, iaOpen = false, dualWired = null, dualOpen = false, aphWired = null, aphOpen = false, libWired = null, dockWired = null, dockSig = '';
  function wireAuxStages() {
    var ia = doc.getElementById('infoArchitecture');
    if (ia && ia !== iaWired) {
      iaWired = ia;
      iaOpen = shown(ia);
      new MO(function () {
        var now = shown(ia);
        if (now && !iaOpen) {
          iaOpen = true;
          setStagger(ia.querySelectorAll('#iaKpis > *'), 8);
          setStagger(ia.querySelectorAll('.ia-card'), 8);
          st.opens++;
          transientClass(ia, 'skd-cine-ia-in', 1100);
          triggerWarp('pulse-panel');
        } else if (!now) {
          iaOpen = false;
        }
      }).observe(ia, { attributes: true, attributeFilter: ['aria-hidden', 'class', 'hidden'] });
    }

    var dual = doc.getElementById('dualStage');
    if (dual && dual !== dualWired) {
      dualWired = dual;
      dualOpen = dual.classList.contains('is-open');
      new MO(function () {
        var now = dual.classList.contains('is-open');
        if (now && !dualOpen) {
          dualOpen = true;
          setStagger(dual.querySelectorAll('.dual-telemetry-cell'), 6);
          setStagger(dual.querySelectorAll('.dual-panel'), 4);
          setStagger(dual.querySelectorAll('.compass-float, .resonance-label'), 8);
          setStagger(dual.querySelectorAll('.dual-bar'), 12);
          st.opens++;
          transientClass(dual, 'skd-cine-dual-in', 1200);
          triggerWarp('warp-compass');
        } else if (!now) {
          dualOpen = false;
        }
      }).observe(dual, { attributes: true, attributeFilter: ['class', 'aria-hidden'] });
    }

    var aph = doc.getElementById('atlasPreviewHUD');
    if (aph && aph !== aphWired) {
      aphWired = aph;
      aphOpen = shown(aph);
      new MO(function () {
        var now = shown(aph);
        if (now && !aphOpen) {
          aphOpen = true;
          setStagger(aph.querySelectorAll('.aph-badge'), 6);
          st.opens++;
          transientClass(aph, 'skd-cine-aph-in', 820);
        } else if (!now) {
          aphOpen = false;
        }
      }).observe(aph, { attributes: true, attributeFilter: ['aria-hidden', 'class', 'hidden'] });
    }

    var lib = doc.getElementById('library');
    if (lib && lib !== libWired) {
      libWired = lib;
      new MO(function () {
        if (lib.classList.contains('on') || (!lib.hidden && lib.getAttribute('aria-hidden') !== 'true')) {
          var cards = lib.querySelectorAll('.lbc, .hist');
          for (var i = 0; i < Math.min(cards.length, 16); i++) {
            cards[i].style.setProperty('--ci', String(i));
            transientClass(cards[i], 'skd-cine-row', 700);
          }
        }
      }).observe(lib, { attributes: true, attributeFilter: ['class', 'hidden', 'aria-hidden'], childList: true, subtree: true });
    }

    var dock = doc.getElementById('dock');
    if (dock && dock !== dockWired) {
      dockWired = dock;
      var panel = dock.querySelector('.panel') || dock;
      new MO(function () {
        var isOn = dock.classList.contains('on');
        if (!isOn) { dockSig = ''; return; }
        var h = dock.querySelector('#dockHead h2');
        var ns = (h && h.textContent) || 'on';
        if (ns !== dockSig) {
          var first = !dockSig;
          dockSig = ns;
          index(panel);
          transientClass(panel, first ? 'skd-cine-in' : 'skd-cine-swap', first ? IN_MS : SWAP_MS);
        }
      }).observe(dock, { attributes: true, attributeFilter: ['class'], childList: true, subtree: true });
    }
  }

  /* ── 6. 全局视图跃迁、指针光学追光与交互准星事件接线 ────────────────── */
  function clearSpot() {
    if (!spotHost) return;
    spotHost.classList.remove('skd-cine-spot');
    spotHost.style.removeProperty('--cine-mx');
    spotHost.style.removeProperty('--cine-my');
    spotHost = null;
    spotRect = null;
  }

  function onPointerMove(e) {
    if (still() || !e || !e.target || !e.target.closest) {
      if (spotHost) clearSpot();
      return;
    }
    var host = e.target.closest(SPOT_SEL);
    if (!host) {
      if (spotHost) clearSpot();
      return;
    }
    if (host !== spotHost) {
      if (spotHost) clearSpot();
      spotHost = host;
      spotRect = host.getBoundingClientRect();
      host.classList.add('skd-cine-spot');
      st.spots++;
    }
    if (spotRect && spotRect.width > 0 && spotRect.height > 0) {
      var mx = Math.max(0, Math.min(100, ((e.clientX - spotRect.left) / spotRect.width) * 100));
      var my = Math.max(0, Math.min(100, ((e.clientY - spotRect.top) / spotRect.height) * 100));
      host.style.setProperty('--cine-mx', mx.toFixed(1) + '%');
      host.style.setProperty('--cine-my', my.toFixed(1) + '%');
    }
  }

  function onBodyMutate() {
    var plotNow = BC.contains('sky-plot-on');
    var compNow = BC.contains('sky-compass-on');
    if (compNow !== prevCompass) {
      prevCompass = compNow;
      triggerWarp(compNow ? 'warp-compass' : 'warp-return');
    } else if (plotNow !== prevPlot) {
      prevPlot = plotNow;
      triggerWarp('warp-plot');
    }
    scan();
  }

  function wireInteractions() {
    doc.addEventListener('pointerdown', function (e) {
      if (still() || !e || !e.target || !e.target.closest) return;
      var btn = e.target.closest('.sky-plot, .sky-icon, .sky-speed, .sky-group button, .skd-view, .aph-badge, .aph-gbtn, .btn, .sd-tabs button, [data-pick-index]');
      if (btn) transientClass(btn, 'skd-cine-press', 360);
      var lockTarget = e.target.closest('#labels .cl-lab, .sky-disc .sd-label, .sky-compass .skc-sat, .sky-compass .skc-ev, .sky-field .sf-name, [data-pick-index], .sks-option, .sd-person, .sd-event, .sd-line');
      if (lockTarget && isFinite(e.clientX) && isFinite(e.clientY)) {
        lockReticle(e.clientX, e.clientY);
      }
      if (e.target.closest('[data-group], #skyFace, #faceBtn, #aphFace')) {
        triggerWarp('warp-regroup', e.clientX, e.clientY);
      }
    }, true);

    doc.addEventListener('pointermove', onPointerMove, { passive: true });
    g.addEventListener('resize', function () { spotRect = null; }, { passive: true });

    doc.addEventListener('cl:sky-compass', function () {
      triggerWarp('warp-compass');
    });

    doc.addEventListener('cl:sky-intro', function (e) {
      if (e && e.detail && e.detail.phase === 'start') {
        triggerWarp('warp-intro');
      }
    });
  }

  function scan() {
    IDS.forEach(function (id) {
      var p = doc.getElementById(id);
      if (p) watch(p);
    });
    wireHoverCard();
    wirePickPanel();
    wireDecks();
    wireHudControls();
    wireAuxStages();
  }

  scan();
  wireInteractions();
  new MO(onBodyMutate).observe(doc.body, {
    attributes: true,
    attributeFilter: ['class'],
    childList: true
  });
  var hudRoot = doc.getElementById('skyHud');
  if (hudRoot) {
    new MO(scan).observe(hudRoot, { childList: true });
  }

  g.CLSkyCinemaUI = {
    stats: function () {
      return {
        opens: st.opens,
        swaps: st.swaps,
        skipped: st.skipped,
        watched: Object.keys(watched).length,
        warps: st.warps,
        locks: st.locks,
        cards: st.cards,
        unfolds: st.unfolds,
        pulses: st.pulses,
        details: st.details,
        spots: st.spots
      };
    },
    triggerWarp: triggerWarp,
    lockReticle: lockReticle
  };
})(window);
