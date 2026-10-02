/**
 * @role shell
 * @owns js/sky/sky-shell.js
 * 一片星空、三种图谱：星座是主体（默认、常驻）；星盘是星座的背景（默认虚化，「剧情」开关唤醒）；罗盘 = 点一颗星进入的单人视图。
 * 状态机与公共接口留在本文件；取景 / HUD / 浮卡 / 播放 / 卡片叠 / 读取幕各有独立单元。接线：CLApp.atlas（视图 / 分类 / 罗盘）、scene（压暗 / 点亮 / 镜头）、CLSkyDisc（星盘）、CLSkyCompass（罗盘外圈）。
 * 旧三页签工作区只在 ?shell=atlas 下启用。
 */
(function (g) {
  'use strict';
  var doc = document, $ = function (id) { return doc.getElementById(id); };
  /* 产品默认 = 星空壳。旧三页签工作区：?shell=atlas。
   * 回归约定：旧版浏览器套件都带 probe=1 且按旧工作区写断言——带 probe=1 而没带 sky=1 时视为旧壳回归，照旧运行；星空壳套件显式带 sky=1。 */
  var ENABLED = (function () { try { var q = new URLSearchParams(location.search); if (q.get('shell') === 'atlas') return false; if (q.get('shell') === 'sky' || q.get('sky')) return true; return q.get('probe') !== '1'; } catch (e) { return true; } })();
  var app = function () { return g.CLApp; }, scene = function () { return app() && app().scene(); };
  var M = null, G = null, disc = null, field = null, hookOff = null, applying = false, camBeforeCompass = null, lastPlotCam = null, lastFit = null, refitT = 0;
  /* 星盘态里视口变了（拖窗口 / 转屏）：剧情前机位换成新视口的星座取景，再按新盘面外接盒重新后拉 */
  function refitPlot() { return cameraUnit.refitPlot(); }
  var mode = 'constellation', plot = false, compassName = null, groupKey = 'camp', savedCam = null, plotBeforeCompass = false;
  var playing = false, playT = null, speed = 1, hoverInfo = null, selInfo = null;
  var hud = null, el = {};
  var PLOT_DIM = 0.62, layerBefore = null, inset = { right: 0, bottom: 0 };

  var esc = g.CLSkyUtil.esc, reduced = g.CLSkyUtil.mediaReduced;
  function narrow() { return (g.innerWidth || 1200) <= 900; }

  /* ── 字形 ──────────────────────────────────────────── */
  var GLYPH = g.CLSkyShellHud.glyph;

  /* ── HUD ───────────────────────────────────────────── */
  function buildHud() { return hudUnit.buildHud(); }
  function renderBrand() { return hudUnit.renderBrand(); }
  function unit() { return (M && M.axis && M.axis.unit) || '回'; }
  function currentGrouping() { return (M && M.groupings || []).filter(function (x) { return x.key === groupKey; })[0] || null; }
  function renderGroups() { return hudUnit.renderGroups(); }
  function renderLegend() { return hudUnit.renderLegend(); }

  /* ── 分类 ──────────────────────────────────────────── */
  function regroup(key) {
    if (!M || key === groupKey) return;
    var gp = (M.groupings || []).filter(function (x) { return x.key === key; })[0]; if (!gp) return;
    groupKey = key;
    var map = null;
    if (key !== 'camp') {
      map = {};
      var valueOf = key === 'stance' ? function (c) { return c.stance; } : key === 'role' ? function (c) { return c.role; } :
        key.indexOf('field:') === 0 ? function (c) { return c[key.slice(6)]; } : null;
      if (key === 'phase') {
        var cnt = {};
        G.events.forEach(function (e) { var ci = M.chapters.map(function (c) { return c.name; }).indexOf(e.chapter), m = M.mains.filter(function (x) { return ci >= x.c0 && ci <= x.c1; })[0]; if (!m) return; (e.characters || []).forEach(function (n) { var o = cnt[n] = cnt[n] || {}; o[m.label] = (o[m.label] || 0) + 1; }); });
        valueOf = function (c) { var o = cnt[c.name] || {}, best = '', bn = 0; Object.keys(o).forEach(function (k) { if (o[k] > bn) { bn = o[k]; best = k; } }); return best; };
      }
      G.characters.forEach(function (c) { var v = valueOf ? valueOf(c) : ''; map[c.name] = typeof v === 'string' ? v.trim() : ''; });
    }
    applying = true;
    try { app().atlas.regroup(map, key, gp.label); } finally { applying = false; }
    if (disc) disc.relayout();
    if (field) field.live(3500);
    if (g.CLSkyDeep) CLSkyDeep.regroup();
    lastFit = null;   /* 分组变了星域半径也变，盘面后拉倍数要重量 */
    if (plot) scene().setCastDim(PLOT_DIM);
    renderGroups(); renderBrand(); if (!plot) renderLegend();
  }

  /* ── 剧情开关 ──────────────────────────────────────── */
  /* 存下的机位只对存下时的视口有效：视口变过（窄屏 ↔ 宽屏、拖窗口）就改用此刻视口下的星座取景，不落回旧机位 */
  function vpKey() { return cameraUnit.vpKey(); }
  function fresh(cam) { return cameraUnit.fresh(cam); }
  /* 剧情态取景：沿 base 的视线按盘面外接盒后拉；reuse = 复用同一视口上次落定时量得的倍数（镜头还在飞时量不准） */
  /* 后拉倍数相对 base 量：镜头临时摆到 base 量完再放回（同一帧内，不会画出来）——从罗盘回来时镜头还在晶体近景里飞，直接量会得出巨大的倍数 */
  function plotFrame(base, reuse) { return cameraUnit.plotFrame(base, reuse); }
  function setPlot(on, o) {
    on = !!on; o = o || {}; if (!disc || mode === 'compass' && on) return;
    /* 幂等：已在该状态就只刷新读数——不能把后拉后的机位当成「剧情前机位」再存一次 */
    if (on === plot && disc.state() === (on ? 'plot' : 'backdrop')) { renderLegend(); renderBrand(); return; }
    plot = on;
    el.skyPlot.setAttribute('aria-pressed', String(on));
    doc.body.classList.toggle('sky-plot-on', on);
    el.skyPlayer.hidden = !on;
    deckSync();
    var S = scene();
    if (on) {
      disc.setState('plot'); if (field) field.setState('dim');
      S.setCastDim(PLOT_DIM);
      layerBefore = app().atlas.layer(); app().atlas.layer('overview');   /* 剧情态收起关系网：盘心只留星与团名，联系改由悬停时的连线表达 */
      /* 剧情态星名只给「被点亮的人」（悬停线的参与者 / 本回在场者）：其余名字收起，免得小星座的名字被避让推到盘上 */
      if (S.setLitOnly) S.setLitOnly(true);
      try { if (g.CLSceneCampHalo && CLSceneCampHalo.setDim) CLSceneCampHalo.setDim(0.18); } catch (e) {}
      if (S.camera && S.controls && S.flyTo && g.THREE) {
        /* o.from：调用方给出的「剧情前机位」（从罗盘返回时镜头还在飞，不能读当前位置）；视口变过就换成此刻的星座取景 */
        var base = fresh(o.from) || { p: S.camera.position.clone(), t: S.controls.target.clone(), vp: vpKey() };
        savedCam = { p: base.p.clone(), t: base.t.clone(), maxD: S.controls.maxDistance, far: S.camera.far, vp: base.vp || vpKey() };
        /* 从罗盘返回时镜头还在晶体近景里飞，此刻量盘面会得出巨大的后拉倍数：同一视口下复用上次落定时量得的倍数 */
        plotFrame(base, !!o.from);
      }
    } else {
      hoverInfo = selInfo = deckInfo = null; deckHotSent = null;
      if (deck) {
        var wasBusy = deckBusy; deckBusy = true;
        try { deck.open(null); deck.hot(null); } finally { deckBusy = wasBusy; }
      }
      stopPlay(); clearCursor();
      disc.setState('backdrop'); if (field) field.setState('show');
      S.setCastDim(0); S.setSearchSet(null);
      app().atlas.layer(layerBefore || 'relations');
      if (S.setLitOnly) S.setLitOnly(false);
      try { if (g.CLSceneCampHalo && CLSceneCampHalo.setDim) CLSceneCampHalo.setDim(1); } catch (e) {}
      var sc = fresh(savedCam);
      if (sc && S.flyTo) {
        S.flyTo(sc.p, sc.t, reduced() || o.instant ? 0.01 : 0.9);
        setTimeout(function () { if (plot || !S.controls) return; if (sc.maxD) S.controls.maxDistance = sc.maxD; if (sc.far && S.camera.far !== sc.far) { S.camera.far = sc.far; S.camera.updateProjectionMatrix(); } }, reduced() || o.instant ? 30 : 1000);
      }
      lastPlotCam = sc; savedCam = null; hideCard();
    }
    renderLegend(); renderBrand();
    if (g.CLSkyDeep) CLSkyDeep.setMode(on ? 'plot' : 'constellation');
    doc.dispatchEvent(new CustomEvent('cl:sky-plot', { detail: { on: on } }));
  }
  function clearCursor() { return playerUnit.clearCursor(); }

  /* ── 悬停卡 / 参与者 ───────────────────────────────── */
  function placeCard(x, y) { return cardsUnit.placeCard(x, y); }
  function hideCard() { return cardsUnit.hideCard(); }
  function light(names) { return cardsUnit.light(names); }
  var deckHotSent = null;
  function onDiscHover(p) { return cardsUnit.onDiscHover(p); }
  function onDiscSelect(info) { return cardsUnit.onDiscSelect(info); }

  /* ── 剧情卡片叠（星盘态左侧：层叠只露标题、按时间序；点开看全部；主线 / 支线 / 细支三种卡） ── */
  var deck = null, deckKeyOf = {}, deckInfo = null, deckBusy = false, evChOf = null;
  function deckOn() { return deckUnit.deckOn(); }
  function deckRect() { return deckUnit.deckRect(); }
  function deckSync() { return deckUnit.deckSync(); }
  /* 展开卡里列的事件：关键事件优先，其余沿跨度均匀取，按时间排 */
  function deckData() { return deckUnit.deckData(); }
  function ensureDeck() { return deckUnit.ensureDeck(); }
  /* 星的屏幕坐标：同一节点的世界坐标经同一台相机投影（与 WebGL 星点逐帧一致） */
  function starScreen(name) { return cameraUnit.starScreen(name); }
  function starScreens(names) { return cameraUnit.starScreens(names); }

  /* ── 播放 ──────────────────────────────────────────── */
  function caption(c) { return playerUnit.caption(c); }
  function seek(c) { return playerUnit.seek(c); }
  function startTimer() { return playerUnit.startTimer(); }
  function stopTimer() { return playerUnit.stopTimer(); }
  function togglePlay() { return playerUnit.togglePlay(); }
  function stopPlay() { return playerUnit.stopPlay(); }

  /* ── 罗盘 ──────────────────────────────────────────── */
  function openCompass(name) {
    if (!G || !app()) return false;
    stopPlay();
    var S0 = scene();
    if (mode !== 'compass') {
      plotBeforeCompass = plot;   /* 罗盘里跳到另一个人时保留「进罗盘前」的剧情状态 */
      /* 进罗盘前的星座机位：剧情态用剧情前存下的那一台（当前镜头是后拉的），否则取当前镜头；返回时原样落回 */
      camBeforeCompass = plot && savedCam ? { p: savedCam.p.clone(), t: savedCam.t.clone(), vp: savedCam.vp } : (S0 && S0.camera ? { p: S0.camera.position.clone(), t: S0.controls.target.clone(), vp: vpKey() } : null);
    }
    if (plot) setPlot(false, { instant: true });   /* 立即复原机位 / 图层 / 远裁剪面（不飞），再进罗盘 */
    disc.setState('hidden'); if (field) field.setState('hidden'); hideCard(); scene().setSearchSet(null); scene().setCastDim(0);
    applying = true;
    var ok = false;
    try { ok = app().atlas.view('gem', name, compassArea()); } finally { applying = false; }
    if (!ok) { disc.setState('backdrop'); if (field) field.setState('show'); return false; }
    mode = 'compass'; compassName = name;
    if (doc.body.dataset.atlasView !== 'gem') doc.body.dataset.atlasView = 'gem';
    doc.body.classList.add('sky-compass-on');
    el.skyCrumb.hidden = false; el.skyCrumbName.textContent = name;
    var ch = G.characters.filter(function (c) { return c.name === name; })[0] || {}, evN = G.events.filter(function (e) { return (e.characters || []).indexOf(name) >= 0; }).length;
    el.skyCrumbMeta.innerHTML = (ch.camp ? '<b>' + esc(ch.camp) + '</b> · ' : '') + esc(ch.role || '') + (ch.stance ? ' · ' + esc(ch.stance) : '') + ' · ' + evN + ' 事件' + (ch.identity ? ' · ' + esc(String(ch.identity).slice(0, 28)) + (String(ch.identity).length > 28 ? '…' : '') : '');
    if (g.CLSkyCompass) CLSkyCompass.open(name, { model: M, graph: G, view: app().atlas.skyView(), scene: scene(), inset: inset, onPick: function (n) { openCompass(n); } });
    if (g.CLSkyDeep) CLSkyDeep.setMode('compass', name);
    applyCamLimits();
    renderLegend();
    /* 所有换态写都做完了：就地同步星名的视图状态并重量（Q5.5，整页样式落在这次点击里，首帧只剩增量；罗盘内换人视图未变则不量） */
    try { if (app().atlas.syncLabels) app().atlas.syncLabels(); } catch (eL) {}
    doc.dispatchEvent(new CustomEvent('cl:sky-compass', { detail: { name: name } }));
    return true;
  }
  /* 镜头限位：星座 / 星盘态用盘面法线的 70° 圆锥（上下左右都能转出立体感，但转不到盘背）；罗盘态晶体本身是立体的，放开水平 360°、俯仰 20°–160° */
  function applyCamLimits() { return cameraUnit.applyCamLimits(); }

  function compassArea() { return cameraUnit.compassArea(); }
  function closeCompass() {
    if (mode !== 'compass') return;
    if (g.CLSkyCompass) CLSkyCompass.close();
    /* 整页级的换态写（罗盘类 / 面包屑）先于 atlas.view 里的第一次读框（Q5.5）：同一任务只排一次整页样式——
       旧顺序把它们写在撤坞还焦 / 取景读框之后，大奉关罗盘那一下排了三次整页（各 ~11 ms） */
    doc.body.classList.remove('sky-compass-on'); el.skyCrumb.hidden = true;
    applying = true;
    try { app().atlas.view('domains'); if (app().atlas.layer) app().atlas.layer('overview'); } finally { applying = false; }
    mode = 'constellation'; compassName = null;
    if (doc.body.dataset.atlasView !== 'domains') doc.body.dataset.atlasView = 'domains';
    disc.setState('backdrop'); if (field) field.setState('show');
    if (g.CLSkyDeep) CLSkyDeep.setMode('constellation');
    applyCamLimits();
    var S1 = scene(), cam0 = fresh(camBeforeCompass); camBeforeCompass = null;
    if (cam0 && S1 && S1.flyTo) S1.flyTo(cam0.p, cam0.t, reduced() ? 0.01 : 0.6);   /* 落回进罗盘前的星座机位（覆盖晶体舞台自己的回程） */
    if (plotBeforeCompass) setPlot(true, { from: cam0 });
    renderLegend();
  }

  /* 从罗盘直接进星盘：镜头此刻还在晶体近景（回程刚起飞），剧情前机位必须用进罗盘前存下的那一台，否则星盘会以晶体为中心取景、复位也回不到盘心 */
  function compassToPlot() {
    var c0 = camBeforeCompass ? { p: camBeforeCompass.p.clone(), t: camBeforeCompass.t.clone(), vp: camBeforeCompass.vp } : null;
    closeCompass();
    if (!plot) setPlot(true, c0 ? { from: c0 } : {});
  }

  /* ── 搜索 ──────────────────────────────────────────── */
  function search(q) {
    q = String(q || '').trim(); if (!q || !G) return;
    var c = G.characters.filter(function (x) { return x.name === q || (x.aliases || []).indexOf(q) >= 0; })[0] || G.characters.filter(function (x) { return x.name.indexOf(q) >= 0; })[0];
    if (c) { openCompass(c.name); return; }
    var ln = (M.mains.concat(M.lines)).filter(function (l) { return l.label.indexOf(q) >= 0 || (l.keyEvent || '').indexOf(q) >= 0 || (l.title || '').indexOf(q) >= 0; })[0];
    if (ln) {
      if (mode === 'compass') compassToPlot(); else setPlot(true);
      var graphAtSearch = G, modelAtSearch = M, discAtSearch = disc;
      setTimeout(function () {
        if (G !== graphAtSearch || M !== modelAtSearch || disc !== discAtSearch || !plot || mode === 'compass') return;
        disc.focus(String(ln.id));
      }, reduced() ? 0 : 900);
      return;
    }
    if (app().toast) app().toast('没有找到「' + q + '」');
  }

  /* ── 键盘（keys.js 让行，见 handlesKey） ───────────── */
  function typing(e) { var t = e.target || {}, tag = (t.tagName || '').toUpperCase(); return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable; }
  function handlesKey(e) {
    if (!ENABLED || !M || typing(e) || e.ctrlKey || e.metaKey || e.altKey) return false;
    var k = e.key;
    if (k === 'p' || k === 'P' || k === '/') return true;
    if ((k === 'r' || k === 'R') && mode !== 'compass') return true;   /* 全局复位用当前图谱的家；卡片有焦点时也不能落进旧壳原点机位 */
    if (e.target && e.target.closest && e.target.closest('.skd-deck, .skg-deck')) return false;   /* 卡片叠里的键（方向 / 回车 / 空格 / Esc）归卡片叠自己 */
    if (k === 'Escape') return !(g.CLSkyChrome && CLSkyChrome.menuOpen && CLSkyChrome.menuOpen()) && (mode === 'compass' || plot);   /* 工具菜单开着时 Esc 只关菜单 */
    if (plot && k === ' ') return true;
    /* 方向键 = 上下左右旋转（图谱不动、镜头绕中心转）；星盘态 ← → 仍是逐回，Shift + ← → 旋转 */
    if (/^Arrow(Left|Right|Up|Down)$/.test(k)) return true;
    return false;
  }
  var ROT_AZ = Math.PI / 12, ROT_POL = Math.PI / 18;
  function rotateKey(k) {
    if (!g.CLSkyDeep || !CLSkyDeep.nudge) return;
    if (k === 'ArrowLeft') CLSkyDeep.nudge(-ROT_AZ, 0); else if (k === 'ArrowRight') CLSkyDeep.nudge(ROT_AZ, 0);
    else if (k === 'ArrowUp') CLSkyDeep.nudge(0, -ROT_POL); else if (k === 'ArrowDown') CLSkyDeep.nudge(0, ROT_POL);
  }
  function onKey(e) {
    if (!handlesKey(e)) return;
    var k = e.key;
    e.preventDefault(); e.stopPropagation();
    if (k === 'p' || k === 'P') { if (mode === 'compass') compassToPlot(); else setPlot(!plot); }
    else if (k === '/') { el.skySearchBox.classList.add('is-open'); el.skySearch.focus(); }
    else if (k === 'r' || k === 'R') { if (g.CLSkyDeep) CLSkyDeep.resetView(); }
    else if (k === 'Escape') { if (mode === 'compass') closeCompass(); else if (disc.focused()) disc.focus(null); else if (playing) stopPlay(); else setPlot(false); }
    else if (k === ' ') togglePlay();
    else if (plot && !e.shiftKey && (k === 'ArrowLeft' || k === 'ArrowRight')) { stopPlay(); var c = disc.cursor(); seek(c == null ? 0 : c + (k === 'ArrowRight' ? 1 : -1)); }
    else rotateKey(k);
  }

  /* ── 读取幕（开书：读取材料 → 推演剧情线 → 排布星座 → 点亮光层 → 揭幕）：app 每一步发 cl:graph-loading，这里推进；
       幕离场的同一刻星开始点亮、光环展开（CLSkyDeep.reveal），镜头落定后深空浮现 ── */
  var loader = null, revealT = 0, curtainAt = 0;
  /* 读取幕跟宿主档位（O7：low 档不下雨、不跑彗星，只留清单与日志）：开幕时读一次，之后跟 scene 的 degrade 事件 */
  function curtainOn() { return loadUnit.curtainOn(); }
  function onLoading(e) { return loadUnit.onLoading(e); }
  /* onGraph 收尾：幕开着就按真实完成的步骤推进（排布 → 预编译着色器 → 揭幕），每步之间让出一帧；没开幕直接点火 */
  function afterGraph() { return loadUnit.afterGraph(); }

  /* ── 接线 ──────────────────────────────────────────── */
  function onGraph() {
    if (!ENABLED || !app() || !scene()) return;
    G = app().graph(); if (!G) return;
    var T = app().story();
    var K = narrow() ? ((g.innerWidth || 1200) <= 480 ? 6 : 10) : 16;
    M = g.CLSkyModel.build(G, T, { named: K, namedLanes: narrow() ? 5 : 7 });
    buildHud();
    doc.body.classList.add('atlas-workspace', 'sky-shell');
    doc.body.dataset.atlasView = 'domains'; doc.body.dataset.atlasLens = 'camps';
    try { if (scene().setHudSelector) scene().setHudSelector('.sky-top,.sky-crumb:not([hidden]),.sky-bottom > *:not([hidden]),.sky-lab:not([hidden]),.cl-dom-legend:not([hidden]),.skd-views:not([hidden]),.skg-deck.is-on:not(.is-folded)'); } catch (eH) {}   /* 星名避开顶栏、底栏、实验室栏与视角栏；团名反过来让星名（sky-field layoutNames） */
    groupKey = 'camp'; mode = 'constellation'; plot = false; compassName = null; stopPlay(); hoverInfo = selInfo = null; lastFit = null; camBeforeCompass = null;
    doc.body.classList.remove('sky-plot-on', 'sky-compass-on'); el.skyCrumb.hidden = true; el.skyPlayer.hidden = true; el.skyPlot.setAttribute('aria-pressed', 'false');
    if (g.CLSkyCompass) CLSkyCompass.close();
    applying = true;
    try { app().atlas.view('domains'); if (app().atlas.layer) app().atlas.layer('overview'); } finally { applying = false; }
    if (!disc) {
      disc = g.CLSkyDisc.create({ scene: scene(), stage: $('stage'), starScreen: starScreen, starScreens: starScreens });
      disc.on('hover', onDiscHover); disc.on('select', onDiscSelect);
      disc.on('hovermove', function (p) { if (hoverInfo) placeCard(p.x, p.y); });
      if (g.CLSkyField) field = CLSkyField.create({ scene: scene(), app: app(), stage: $('stage') });
      hookOff = scene().registerFrameHook(function (dt, tAcc, tAnim, calm, degrade) { disc.frame(); if (field) field.frame(); if (g.CLSkyCompass && mode === 'compass') CLSkyCompass.frame(); if (g.CLSkyDeep) CLSkyDeep.frame(dt, tAnim, degrade); });
    }
    /* 图谱恒在画面中心：禁平移、右键 / 双指改成旋转，轨道目标跟着每次飞行的落点走（星座 / 星盘 = 盘心，罗盘 = 晶体） */
    try { if (scene().setOrbitLock) { scene().setOrbitLock(true); applyCamLimits(); } } catch (eL) {}
    if (field) { field.rebuild(); field.setState('show'); }
    disc.setModel(M); disc.setState('backdrop'); disc.setCursor(null);
    /* 光层（WebGL）：星体光学 / 势力星云 / 组间束 / 星盘光环 / 罗盘星轨 / 后期虚化；须在星盘锚点建好（setModel）之后接入；不可用时 SVG 读层照常工作 */
    if (g.CLSkyDeep && !CLSkyDeep.enabled()) CLSkyDeep.init({ scene: scene(), disc: disc, field: field, app: app(), card: el.skyCard, hud: hud });
    el.skyScrub.max = String(Math.max(0, M.nCh - 1)); el.skyScrub.value = '0'; caption(null);
    if (g.CLSkyDeep) CLSkyDeep.onGraph(M, G, el.skyPlayer);
    evChOf = null; deckInfo = null;
    if (ensureDeck()) { var dd = deckData(); deck.setData(dd.cards, dd.meta); deckHotSent = null; deckSync(); }
    renderGroups(); renderBrand(); renderLegend();
    afterGraph();
    var q = new URLSearchParams(location.search);
    if (q.get('plot') === '1' || q.get('sky') === 'plot') setTimeout(function () { setPlot(true); }, 60);
  }
  /* 单一状态归 shell：单元读写显式桥，不复制机位 / 模型 / 选择，也不添加帧循环。 */
  var shellContext = {
    $: $,
    app: app,
    closeCompass: closeCompass,
    compassToPlot: compassToPlot,
    currentGrouping: currentGrouping,
    deckOn: deckOn,
    deckRect: deckRect,
    doc: doc,
    esc: esc,
    light: light,
    narrow: narrow,
    reduced: reduced,
    regroup: regroup,
    scene: scene,
    search: search,
    seek: seek,
    setPlot: setPlot,
    startTimer: startTimer,
    stopPlay: stopPlay,
    stopTimer: stopTimer,
    togglePlay: togglePlay,
    unit: unit
  };
  Object.defineProperties(shellContext, {
    hud: { get: function () { return hud; }, set: function (v) { hud = v; } },
    el: { get: function () { return el; } },
    G: { get: function () { return G; } },
    M: { get: function () { return M; } },
    mode: { get: function () { return mode; } },
    plot: { get: function () { return plot; } },
    PLOT_DIM: { get: function () { return PLOT_DIM; } },
    savedCam: { get: function () { return savedCam; } },
    inset: { get: function () { return inset; } },
    lastFit: { get: function () { return lastFit; }, set: function (v) { lastFit = v; } },
    speed: { get: function () { return speed; }, set: function (v) { speed = v; } },
    playing: { get: function () { return playing; }, set: function (v) { playing = v; } },
    playT: { get: function () { return playT; }, set: function (v) { playT = v; } },
    GLYPH: { get: function () { return GLYPH; } },
    groupKey: { get: function () { return groupKey; } },
    deck: { get: function () { return deck; }, set: function (v) { deck = v; } },
    evChOf: { get: function () { return evChOf; }, set: function (v) { evChOf = v; } },
    deckKeyOf: { get: function () { return deckKeyOf; }, set: function (v) { deckKeyOf = v; } },
    deckInfo: { get: function () { return deckInfo; }, set: function (v) { deckInfo = v; } },
    disc: { get: function () { return disc; } },
    hoverInfo: { get: function () { return hoverInfo; }, set: function (v) { hoverInfo = v; } },
    selInfo: { get: function () { return selInfo; }, set: function (v) { selInfo = v; } },
    deckHotSent: { get: function () { return deckHotSent; }, set: function (v) { deckHotSent = v; } },
    deckBusy: { get: function () { return deckBusy; }, set: function (v) { deckBusy = v; } },
    loader: { get: function () { return loader; }, set: function (v) { loader = v; } },
    revealT: { get: function () { return revealT; }, set: function (v) { revealT = v; } },
    curtainAt: { get: function () { return curtainAt; }, set: function (v) { curtainAt = v; } },
    ENABLED: { get: function () { return ENABLED; } }
  });
  var cameraUnit = g.CLSkyShellCamera.create(shellContext),
      hudUnit = g.CLSkyShellHud.create(shellContext),
      cardsUnit = g.CLSkyShellCards.create(shellContext),
      playerUnit = g.CLSkyShellPlayer.create(shellContext),
      deckUnit = g.CLSkyShellDeck.create(shellContext),
      loadUnit = g.CLSkyShellLoad.create(shellContext);

  /* index.html 的 <html> 默认带 sky-shell-boot（首帧就不画旧外围）；旧壳在这里摘掉 */
  if (!ENABLED) doc.documentElement.classList.remove('sky-shell-boot');
  if (ENABLED) {
    doc.documentElement.classList.add('sky-shell-boot');
    doc.addEventListener('cl:graph-ready', onGraph);
    doc.addEventListener('cl:graph-loading', onLoading);
    if (g.CLLoadStage) onLoading({ detail: g.CLLoadStage });
    g.addEventListener('keydown', onKey, true);
    g.addEventListener('resize', function () { var S = scene(); if (S && S.resize) S.resize(); if (disc) disc.relayout(); deckSync(); clearTimeout(refitT); refitT = setTimeout(refitPlot, 220); });   /* 画布跟着视口重设尺寸（否则只是 CSS 拉伸、发虚） */
  }

  g.CLSky = {
    enabled: function () { return ENABLED; }, isApplying: function () { return applying; }, handlesKey: handlesKey,
    setPlot: setPlot, plot: function () { return plot; }, field: function () { return field; }, compassArea: compassArea, openCompass: openCompass, closeCompass: closeCompass, regroup: regroup, seek: seek, play: togglePlay, stop: stopPlay,
    focusLine: function (id) { return disc && disc.focus(id); }, hoverLine: function (id) { if (!disc) return false; var ok = disc.hoverLine(id), p = ok ? disc.lineScreen(String(id)) : null; onDiscHover(ok ? { info: disc.lineInfo(String(id)), x: p ? p[0] : g.innerWidth / 2, y: p ? p[1] : g.innerHeight / 2 } : null); return ok; },
    clearCursor: clearCursor,
    setInset: function (o) { inset = { right: Math.max(0, +(o && o.right) || 0), bottom: Math.max(0, +(o && o.bottom) || 0) }; if (mode === 'compass' && compassName && g.CLSkyCompass) { var S = scene(); if (S && S.gemStage && S.gemStageState && S.gemStageState().on) S.gemStage({ on: true, name: compassName, area: compassArea() }); CLSkyCompass.setInset(inset); } else if (disc) disc.relayout(); return inset; },
    model: function () { return M; }, disc: function () { return disc; }, deck: function () { return deck; },
    /* 可序列化状态（预演深链用）：只存 id / 名字，不存数组下标 */
    snapshot: function () { return { v: 1, group: groupKey, plot: plot, compass: compassName, cursor: disc ? disc.cursor() : null, line: disc ? disc.focused() : null }; },
    apply: function (s2) {
      if (!s2 || !M) return false;
      if (s2.compass && !G.characters.some(function (c) { return c.name === s2.compass; })) return false;
      if (mode === 'compass' && !s2.compass) closeCompass();
      if (s2.group && s2.group !== groupKey) regroup(s2.group);
      if (s2.compass) return openCompass(s2.compass);
      setPlot(!!s2.plot);
      if (s2.plot && s2.cursor != null) seek(s2.cursor); else clearCursor();
      if (s2.plot && disc) disc.focus(s2.line != null ? String(s2.line) : null);
      return true;
    },
    setCalm: function (v) { if (disc) disc.setCalm(v); },
    curtainWait: function () { return curtainOn() ? Math.max(0, curtainAt - Date.now()) : 0; },
    state: function () { return { mode: mode, plot: plot, compass: compassName, group: groupKey, playing: playing, cursor: disc ? disc.cursor() : null, disc: disc ? disc.stats() : null }; }
  };
})(window);
