/**
 * @role shell-load
 * @owns js/sky/sky-shell-load.js
 * 读取幕、宿主质量档位与预编译后揭幕。状态由 sky-shell 持有，X 是显式闭包桥；不创建帧循环。
 */
(function (g) {
  'use strict';
  function create(X) {
    var epoch = 0, layoutT = 0, compileT = 0;
    function cancelPending() {
      epoch++;
      if (layoutT) { clearTimeout(layoutT); layoutT = 0; }
      if (compileT) { clearTimeout(compileT); compileT = 0; }
      if (X.revealT) { clearTimeout(X.revealT); X.revealT = 0; }
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
    if (begin) { L.setTier(loaderTier()); L.show({ title: d.title || '', sub: '', instant: !X.G }); X.curtainAt = Date.now() + (X.G && !X.reduced() ? 400 : 0); }   /* 开机时直接不透明（不让旧外围从半透明的幕后面透出来）；换书时淡入，淡到不透明才开始重建 */
    else if (d.title) L.title(d.title);
    if (d.glyphs && L.glyphs) L.glyphs(d.glyphs);   /* 字符雨换上这部书自己的人名 / 回目 */
    L.stage(d.stage || 'fetch', d.frac != null ? d.frac : 0.06, d.detail || '');
  }
  function liftCurtain() {
    cancelPending();
    if (g.CLSkyDeep) CLSkyDeep.reveal();
    if (curtainOn()) X.loader.done();
  }
  function afterGraph() {
    cancelPending();
    var S = X.scene(), expected = epoch, graph = X.G, model = X.M, loader = X.loader;
    function current() { return epoch === expected && X.scene() === S && X.G === graph && X.M === model && X.loader === loader && curtainOn(); }
    /* 预编译（Q5.5）：主场景画进线性编码的目标，compileWarm 编的才是渲染时真正用的那份程序（空目标下编出的 sRGB 变体 22 个里 21 个从没用上）；
       顺带把晶冠的 13 个程序编进缓存（首开罗盘不再现场链接），那座晶冠停进停放槽备用 */
    function compile() {
      var undo = null;
      try { if (S && S.prewarmCrown) S.prewarmCrown(); } catch (eW) {}
      try { undo = g.CLSkyDeep && CLSkyDeep.prewarmCompass ? CLSkyDeep.prewarmCompass() : null; } catch (eP) {}   /* 一次性的罗盘星轨 / 卫星，随整场景一起编 */
      try { if (S && S.compileWarm) S.compileWarm(); else if (S && S.renderer && S.scene && S.camera) S.renderer.compile(S.scene, S.camera); } catch (eC) {}
      if (undo) undo();
    }
    if (!curtainOn()) { compile(); if (g.CLSkyDeep) CLSkyDeep.reveal(); return; }
    var info = S && S.skyInfo ? S.skyInfo() : null, U = g.CLSkyUtil;
    X.loader.stage('layout', 0.66, U.num(X.G.characters.length) + ' 颗星 · ' + X.M.mains.length + ' 段主线 · ' + X.M.lines.length + ' 条支线');
    /* 启动日志只写真实读数：关系 / 回目 / 分组 */
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
        /* 揭幕前等书名与日志打完（上限 1.4 s）：开篇读得完，但不为动画拖长读取 */
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
      afterGraph: afterGraph
    };
  }
  g.CLSkyShellLoad = { create: create };
})(window);
