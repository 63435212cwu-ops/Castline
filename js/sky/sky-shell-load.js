(function (g) {
  'use strict';
  function create(X) {
    var epoch = 0, layoutT = 0, compileT = 0;
    function cancelPending() {
      epoch++;
      if (layoutT) { clearTimeout(layoutT); layoutT = 0; }
      if (compileT) { clearTimeout(compileT); compileT = 0; }
      if (X.revealT) { clearTimeout(X.revealT); X.revealT = 0; }
      introEnd();
    }
    var introT = 0, introOn = false, INTRO_MS = 3400;
    function introFire(phase) { try { X.doc.dispatchEvent(new CustomEvent('cl:sky-intro', { detail: { phase: phase } })); } catch (eE) {} }
    function introEnd(skipped) {
      if (introT) { clearTimeout(introT); introT = 0; }
      if (!introOn) return;
      introOn = false;
      g.removeEventListener('pointerdown', introSkip, true); g.removeEventListener('keydown', introSkip, true);
      X.doc.body.classList.remove('skd-intro');
      introFire(skipped ? 'skip' : 'end');
    }
    function introSkip() {
      var s = X.loader ? X.loader.stats() : null;
      if (s && s.shown && s.stage === 'done') X.loader.hide();
      introEnd(true);
    }
    function introStart() {
      introEnd();
      var D = g.CLSkyDeep && CLSkyDeep.stats ? CLSkyDeep.stats() : null;
      if (X.reduced() || !(D && D.reveal && D.reveal.staged)) return false;
      introOn = true;
      X.doc.body.classList.add('skd-intro');
      g.addEventListener('pointerdown', introSkip, true); g.addEventListener('keydown', introSkip, true);
      introT = setTimeout(function () { introT = 0; introEnd(); }, INTRO_MS);
      introFire('start');
      return true;
    }
  function loaderTier() { var S = X.scene(), c = S && S.core ? S.core() : null, K = g.CLSkyTokens; return K && K.tierOf ? K.tierOf(c && c.getDegrade ? c.getDegrade() : 0) : 'high'; }
  function ensureLoader() {
    if (!X.loader && g.CLSkyLoader) {
      X.loader = CLSkyLoader.create({ host: X.doc.body, onSkip: function (e) { if (e && e.type === 'click') { e.preventDefault(); e.stopPropagation(); } liftCurtain(); } });
      var S0 = X.scene(); if (S0 && S0.on) S0.on('degrade', function () { if (X.loader) X.loader.setTier(loaderTier()); });
    }
    return X.loader;
  }
  function curtainOn() { var s = X.loader ? X.loader.stats() : null; return !!(s && s.shown && s.stage !== 'done'); }
  function onLoading(e) {
    if (!X.ENABLED) return;
    var d = (e && e.detail) || {}, L = ensureLoader(); if (!L) return;
    if (d.stage === 'error') { cancelPending(); L.hide(); if (g.CLSkyDeep) CLSkyDeep.reveal(); return; }
    var st = L.stats(), begin = !d.stage || d.stage === 'fetch' || !st.shown || st.stage === 'done';
    if (begin) cancelPending();
    if (begin) { L.setTier(loaderTier()); L.show({ title: d.title || '', sub: '', instant: !X.G }); X.curtainAt = Date.now() + (X.G && !X.reduced() ? 400 : 0); }
    else if (d.title) L.title(d.title);
    if (d.glyphs && L.glyphs) L.glyphs(d.glyphs);
    L.stage(d.stage || 'fetch', d.frac != null ? d.frac : 0.06, d.detail || '');
  }
  function liftCurtain() {
    cancelPending();
    var lifted = g.CLSkyDeep ? CLSkyDeep.reveal() : false;
    if (curtainOn()) { X.loader.done(); if (lifted) introStart(); }
  }
  function afterGraph() {
    cancelPending();
    var S = X.scene(), expected = epoch, graph = X.G, model = X.M, loader = X.loader;
    function current() { return epoch === expected && X.scene() === S && X.G === graph && X.M === model && X.loader === loader && curtainOn(); }
    function compile() {
      var undo = null;
      try { if (S && S.prewarmCrown) S.prewarmCrown(); } catch (eW) {}
      try { undo = g.CLSkyDeep && CLSkyDeep.prewarmCompass ? CLSkyDeep.prewarmCompass() : null; } catch (eP) {}
      try { if (S && S.compileWarm) S.compileWarm(); else if (S && S.renderer && S.scene && S.camera) S.renderer.compile(S.scene, S.camera); } catch (eC) {}
      if (undo) undo();
    }
    if (!curtainOn()) { compile(); if (g.CLSkyDeep) CLSkyDeep.reveal(); return; }
    var info = S && S.skyInfo ? S.skyInfo() : null, U = g.CLSkyUtil;
    X.loader.stage('layout', 0.66, U.num(X.G.characters.length) + ' 颗星 · ' + X.M.mains.length + ' 段主线 · ' + X.M.lines.length + ' 条支线');
    if (X.loader.counts) X.loader.counts({ chars: X.G.characters.length, chapters: X.M.nCh });
    if (X.loader.log) X.loader.log('关系 ' + U.num((X.G.relations || []).length) + ' · ' + U.num(X.M.nCh) + ' 回 · ' + (info && info.sectors ? info.sectors.length : 0) + ' 组');
    layoutT = setTimeout(function () {
      layoutT = 0; if (!current()) return;
      X.loader.stage('compile', 0.84, '预编译着色器');
      compileT = setTimeout(function () {
        compileT = 0; if (!current()) return;
        compile();
        if (X.loader.log && S && S.renderer) X.loader.log('着色器程序 ' + S.renderer.info.programs.length);
        X.loader.stage('reveal', 1, '');
        var hold = X.loader.holdLeft ? Math.round(X.loader.holdLeft() * 1000) + 120 : 0;
        X.revealT = setTimeout(function () { if (current()) liftCurtain(); }, X.reduced() ? 0 : Math.max(420, Math.min(1400, hold)));
      }, 34);
    }, 34);
  }
    return {
      loaderTier: loaderTier,
      ensureLoader: ensureLoader,
      curtainOn: curtainOn,
      onLoading: onLoading,
      liftCurtain: liftCurtain,
      afterGraph: afterGraph,
      introOn: function () { return introOn; },
      finishIntro: introSkip
    };
  }
  g.CLSkyShellLoad = { create: create };
})(window);
