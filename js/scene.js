/* Castline · scene.js — 场景主外观门面与组装层 (H1 / G1-1)
 * 组装 scene-core, scene-mats, scene-lod-labels, scene-stage 四件套，
 * 保留 window.CLScene 与 window.__cl.scene 完整的 98+ 项 API 与全部既有行为。
 * 遵循 ES5 与严格模式；Gem 主舞台复用同一场景帧和 CLGemModel。
 */
(function () {
  'use strict';
  var T = window.THREE;
  var Mats = window.CLSceneMats || {};
  var Labels = window.CLSceneLodLabels || {};
  var Stage = window.CLSceneStage || {};
  var Core = window.CLSceneCore || {};

  var TONE = Mats.TONE, GEM_MATS = Mats.GEM_MATS, gemSpec = Mats.gemSpec, tone = Mats.tone;
  var gemMat = Mats.gemMat, ghostMat = Mats.ghostMat, motesMat = Mats.motesMat, ringMat = Mats.ringMat, hand = Mats.hand, texDais = Mats.texDais;
  var CROWN_VS = Mats.CROWN_VS, CROWN_FS = Mats.CROWN_FS, CROWN_BASE_FS = Mats.CROWN_BASE_FS;
  var CAUST_FS = Mats.CAUST_FS, CRL_VS = Mats.CRL_VS, CRL_FS = Mats.CRL_FS;
  var RING_VS = Mats.RING_VS, RING_FS = Mats.RING_FS, SWEEP_FS = Mats.SWEEP_FS;
  var ATTR_KEYS = Mats.ATTR_KEYS, ATTR_EN = Mats.ATTR_EN, META_KEYS = Mats.META_KEYS, META_EN = Mats.META_EN, META_DEF = Mats.META_DEF, KIND_COL = Mats.KIND_COL, CN = Mats.CN, escH = Mats.escH;
  var SEG = Mats.SEG || 22, COL_X = Mats.COL_X || 300, FOCUS_X = Mats.FOCUS_X || 270, lerp = Mats.lerp, settle = Mats.settle, clamp = Mats.clamp, hash = Mats.hash, rnd = Mats.rnd;
  var easeOut = Mats.easeOut, easeInOut = Mats.easeInOut, easeOutBack = Mats.easeOutBack, laneLayout = Mats.laneLayout, laneSway = Mats.laneSway, laneIndent = Mats.laneIndent, centerOutOrder = Mats.centerOutOrder, glowTexture = Mats.glowTexture, ribbon = Mats.ribbon;
  var LAYOUT_PARAM = (function () { try { return new URLSearchParams(location.search).get('layout') || ''; } catch (e) { return ''; } })();
  /* 星空壳默认用平面天球布局（扇区 = 分组）；旧壳仍是星路。?layout= 显式指定优先 */
  function layoutMode() { if (LAYOUT_PARAM) return LAYOUT_PARAM; try { if (window.CLSky && CLSky.enabled && CLSky.enabled()) return 'sky'; } catch (e) {} return 'road'; }
  var BAYER = ['α', 'β', 'γ', 'δ', 'ε', 'ζ', 'η', 'θ', 'ι', 'κ', 'λ', 'μ', 'ν', 'ξ', 'ο', 'π', 'ρ', 'σ', 'τ', 'υ', 'φ', 'χ', 'ψ', 'ω'];
  var STANCE_EN = { 主角方: 'PROTAGONIST', 盟友: 'ALLY', 中立: 'NEUTRAL', 摇摆: 'WAVERING', 对立: 'OPPOSITION', '': 'UNALIGNED' };

  function create(canvas, labelLayer, opts) {
    opts = opts || {};
    var S = {};
    var coreOpts = {};
    for (var k in opts) coreOpts[k] = opts[k];
    coreOpts.getGrow = function () { return grow; };
    coreOpts.getMode = function () { return mode; };
    coreOpts.getFocusName = function () { return focusName; };
    coreOpts.getHoverName = function () { return hoverName; };
    coreOpts.getCampSel = function () { return campSel; };
    coreOpts.getCampHover = function () { return campHover; };
    coreOpts.getLodStat = function () { return (labels && labels.getLodStat) ? labels.getLodStat() : {}; };
    coreOpts.getGraph = function () { return graph; };
    var core = Core.create(canvas, labelLayer, coreOpts);
    var renderer = core.renderer, scene = core.scene, group = core.group, camera = core.camera;
    var controls = core.controls, nodes = core.nodes, nodeByKey = core.nodeByKey, fibers = core.fibers;
    var isGL2 = renderer.capabilities.isWebGL2;
    var dpr = core.getDpr();
    var W = core.getW(), H = core.getH();

    var texNode = Mats.glowTexture(256, 0.08, 0.75), texStar = Mats.createStarTexture ? Mats.createStarTexture() : null;
    var texSoft = Mats.glowTexture(256, 0.02, 0.28), texTick = Mats.createTickTexture ? Mats.createTickTexture() : null;
    var graph = null, mode = 'atlas', focusName = null, hoverName = null, graphPinKey = '', labelRevision = 0;
    var REL_WEB_MAX = 64, relWeb = { total: 0, shown: 0, pruned: false };   // v90 F7 关系网密度纪律
    var bloomBase = 0.48, glowK = 1, densityBloom = 1;   // v90 F3（F6 host P1）：glowK = 公开泛光系数；densityBloom 由样本密度分级
    var focusHeat = 0, focusMeta = null, crownHl2 = -1, campSel = null, campHover = null, castDim = 0, groupXTo = 0, colX = COL_X, dirty = true, bucketMap = {};
    var chapSel = null, dialHover = null;
    var layoutInfo = null, campIndex = {}, campOfName = {}, hubList = [], bookStats = null;
    /* 邻接表（悬停巡礼用）：relations 是扁平数组，按跳数泛洪每次都要全表扫；这里按人名索引一次，悬停只走自己的边 */
    var adjMap = null, adjKey = '';
    var parallax = new T.Vector2(0, 0), parallaxTo = new T.Vector2(0, 0), grow = 0, growTarget = 1, growStart = 0, animStart = 0, animDur = 1.0, idle = false, _cm = new T.Vector3();

    var stage = Stage.create({
      camera: camera,
      controls: controls,
      labelLayer: labelLayer,
      group: group,
      getNodes: function () { return nodes; },
      getNodeByKey: function () { return nodeByKey; },
      getCampSel: function () { return campSel; },
      campFiberFn: core.campFiberFn,
      setFiberHl: core.setFiberHl,
      spawnIris: core.spawnIris,
      sendSignal: core.sendSignal,
      setBurst: function (v) { if (core.setBurst) core.setBurst(v); },
      markLodDirty: function () { if (labels && labels.markLodDirty) labels.markLodDirty(); },
      markDirty: function () { dirty = true; },
      getBucketMap: function () { return core.getBucketMap ? core.getBucketMap() : {}; },
      atlasDist: function () { return atlasDist(); },
      focus: focus,
      getMode: function () { return mode; },
      getFocusName: function () { return focusName; },
      parallaxTo: parallaxTo,
      getSpines: core.getSpines,
      getStarField: core.getStarField,
      getGlyphLine: core.getGlyphLine,
      getRoadBand: core.getRoadBand,
      getRoadRim: core.getRoadRim
    });

    var labels = Labels.create({
      canvas: canvas,
      labelLayer: labelLayer,
      getCamera: function () { return camera; },
      getControls: function () { return controls; },
      getGroup: function () { return group; },
      getW: function () { return core.getW(); },
      getH: function () { return core.getH(); },
      getNodes: function () { return nodes; },
      getNodeByKey: function () { return nodeByKey; },
      getMode: function () { return mode; },
      getGrow: function () { return grow; },
      getFocusName: function () { return focusName; },
      getHoverName: function () { return hoverName; },
      getFace: function () { return face; },
      getCrown: function () { return crown; },
      /* v90 F3 · 双晶主舞台轴签排版：舞台矩形 + 是否同屏两面（桌面 > 900） */
      getGemStage: function () { return gemStageOn && gemStageArea ? { area: gemStageArea, dual: gemDualLabels(), face: face } : null; },
      getStarField: core.getStarField,
      crownProj: function (x, y, z) { return crownProj(x, y, z); },
      isCalm: function () { return calm; },
      getNCharCount: function () { return nodes.filter(function (n) { return n.kind === 'char'; }).length; },
      getGraphPinKey: function () { return graphPinKey; },
      fire: core.fire,
      markDirty: function () { dirty = true; },
      wallMs: core.wallMs
    });

    var buildFiberMesh = core.buildFiberMesh, buildGlyphLines = core.buildGlyphLines, disposeGlyphLines = core.disposeGlyphLines;
    var buildStarField = core.buildStarField, disposeStarField = core.disposeStarField, buildRoadBand = core.buildRoadBand;
    var disposeRoadBand = core.disposeRoadBand, buildRoadRim = core.buildRoadRim, disposeRoadRim = core.disposeRoadRim;
    var buildAtlasSpines = core.buildAtlasSpines, buildSpines = core.buildSpines, disposeSpines = core.disposeSpines, disposeChapRail = core.disposeChapRail || core.disposeSpines, buildNebulae = core.buildNebulae, disposeNebulae = core.disposeNebulae;
    var campFitR = core.campFitR, chapterBuckets = core.chapterBuckets, chapterList = core.chapterList, addFiber = core.addFiber, trimFibers = core.trimFibers;
    var relColor = core.relColor, roleColor = core.roleColor, haloOf = core.haloOf, stanceHalo = core.stanceHalo, opposed = core.opposed;
    var fire = core.fire, stats = core.stats, rawMeta = core.computeMeta;
    var focusGem = null, gemBench = null, gemStageOn = false, gemStageSaved = null;
    var gemStageArea = null, gemPeer = null, gemScope = 'book', gemChapter = null;
    var setFiberHl = core.setFiberHl, campFiberFn = core.campFiberFn;
    var lineComp = core.lineComp || function () { return 1; };
    var C_FIBER = new T.Color(0x7a5cff), C_ATTR = new T.Color(0x3fd6a8), C_REL = new T.Color(0xffb45c), C_REL_HOT = new T.Color(0xff5d73), C_REL_COLD = new T.Color(0xf6dfa4);
    var tAcc = 0, tAnim = 0, calm = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches), lodDirty = true, pinned = {}, tailShow = false, searchSet = null, pendingBuild = null;
    var safe = { left: 0, right: 0, top: 0, bottom: 0 };
    var _v = new T.Vector3();
    var flyTo = stage.flyTo;
    var measureLabels = labels.measureLabels, attachLabel = labels.attachLabel, detachLabel = labels.detachLabel;

    function attrScore(c, key) {
      var a = c && c.attrs ? c.attrs[key] : null;
      if (window.CLRadar && window.CLRadar.scoreOf) return window.CLRadar.scoreOf(a);
      var raw = a && typeof a === 'object' ? (a.pending ? null : a.score) : a;
      if (raw === null || raw === undefined || (typeof raw !== 'number' && typeof raw !== 'string') || (typeof raw === 'string' && !raw.trim())) return null;
      return isFinite(Number(raw)) ? clamp(Number(raw), 0, 100) : null;
    }
    function computeMeta(c) {
      var m = rawMeta(c), morality = attrScore(c, '道义'), ambition = attrScore(c, '野心');
      m.known = {};
      META_KEYS.forEach(function (key) { m.known[key] = m.score[key] != null && isFinite(m.score[key]); });
      /* Core's legacy morality fallback treated a real zero as 50. Derived
         light/dark axes are only stated when their source axes are known. */
      var rels = (graph && graph.relations || []).filter(function (r) { return r.a === c.name || r.b === c.name; });
      var friendly = rels.filter(function (r) { return /师|徒|友|盟|同|亲|父|母|子|女|兄|弟|姐|妹|家|恋|爱|夫|妻|情|眷|婚/.test(r.kind || ''); }).length;
      var hostile = rels.filter(function (r) { return /宿敌|仇|敌|对立|背叛|追杀|利用|冲突|猜忌|陷害|反目|算计/.test(r.kind || ''); }).length;
      m.known['光明面'] = morality !== null;
      m.known['暗黑面'] = morality !== null && ambition !== null;
      m.v['光明面'] = morality === null ? null : clamp(0.55 * morality / 100 + 0.30 * (rels.length ? friendly / rels.length : 0.3) + (c.role === '主角' ? 0.15 : c.role === '反派' ? -0.2 : 0), 0, 1);
      m.v['暗黑面'] = !m.known['暗黑面'] ? null : clamp(0.45 * (1 - morality / 100) + 0.30 * (rels.length ? hostile / rels.length : 0.15) + 0.15 * ambition / 100 + (c.role === '反派' ? 0.2 : c.role === '主角' ? -0.1 : 0), 0, 1);
      ['光明面', '暗黑面'].forEach(function (key) {
        m.score[key] = m.known[key] ? Math.round(m.v[key] * 100) : null;
        if (!m.known[key]) m.sub[key] = '来源属性待建档 · 不推定分值';
      });
      if (m.known['光明面']) m.sub['光明面'] = '道义 ' + morality + ' · 正向关系 ' + friendly + ' · 全书推导';
      if (m.known['暗黑面']) m.sub['暗黑面'] = '道义 ' + morality + ' · 野心 ' + ambition + ' · 敌对关系 ' + hostile + ' · 全书推导';
      var imp = c.importance;
      var impKnown = imp != null && (typeof imp === 'number' || (typeof imp === 'string' && imp.trim() !== '')) && isFinite(Number(imp));
      var bases = { 主角: 0.92, 核心配角: 0.74, 反派: 0.74, 配角: 0.46, 功能性: 0.18 };
      m.known['咖位'] = !!bases[c.role] && impKnown;
      m.v['咖位'] = m.known['咖位'] ? clamp(0.55 * bases[c.role] + 0.45 * clamp(Number(imp) / 100, 0, 1), 0, 1) : null;
      m.score['咖位'] = m.known['咖位'] ? Math.round(m.v['咖位'] * 100) : null;
      m.sub['咖位'] = m.known['咖位'] ? c.role + ' · 重要度 ' + Number(imp) : '角色定位或重要度待建档';
      return m;
    }
    function sceneMetaOf(name) {
      var n = nodeByKey['c:' + name];
      return n && n.data ? computeMeta(n.data) : null;
    }
    function buildGemModel(c, peer) {
      if (!window.CLGemModel || !graph) return null;
      if (window.CLRadarBenchmark) gemBench = window.CLRadarBenchmark.computeBenchmark(graph.characters || []);
      var atlas = null;
      try { atlas = window.CLPlot && window.CLPlot.atlas ? window.CLPlot.atlas() : null; } catch (e) {}
      return window.CLGemModel.build(c, graph, { metaOf: sceneMetaOf, bench: gemBench, atlas: atlas, peerName: peer || null, chapter: gemStageOn ? gemChapter : null });
    }

    function roman(n) { var v = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1], r = ['M', 'CM', 'D', 'CD', 'C', 'XC', 'L', 'XL', 'X', 'IX', 'V', 'IV', 'I'], o = ''; for (var i = 0; i < v.length; i++) while (n >= v[i]) { o += r[i]; n -= v[i]; } return o; }

    function mkNode(key, kind, label, sub, attach) {
      var sp = new T.Sprite(new T.SpriteMaterial({ map: texNode, transparent: true, depthWrite: false, blending: T.AdditiveBlending, color: 0xffffff }));
      var halo = new T.Sprite(new T.SpriteMaterial({ map: texSoft, transparent: true, depthWrite: false, blending: T.AdditiveBlending, color: 0xffa860 }));
      var g = new T.Group(); g.add(halo); g.add(sp);
      var el = document.createElement('div'); el.className = 'cl-lab ' + kind;
      el.innerHTML = '<span class="ln"></span><span class="ls mono"></span><span class="lx"></span>';
      el.children[0].textContent = label || ''; el.children[1].textContent = sub || '';
      el.style.setProperty('--tx', '0px'); el.style.setProperty('--ty', '0px');
      el.classList.add('d0');
      if (attach !== false) labelLayer.appendChild(el);
      var n = { key: key, kind: kind, label: label, sub: sub, g: g, sp: sp, halo: halo, el: el,
        pos: new T.Vector3(), from: new T.Vector3(), to: new T.Vector3(), size: 10, sizeTo: 10, alpha: 1, alphaTo: 1, color: new T.Color(0x9fd8ff), data: null,
        flash: 0, delay: 0, tier: 0, w: 0, ec: 0, rc: 0, haloK: 3.2, baseAlpha: 1, ox: 0, oy: 0,
        labelX: 0, labelY: 0, rail: false, forceType: '', render: true, labelAttached: attach !== false, _flip: false, vis: false, forced: false,
        prio: 0, sx: 0, sy: 0, sz: 0, _d: 0, moved: false, _lp: new T.Vector3(), recalc: false, seq: 0, fseq: -1 };
      sp.userData.node = n;
      group.add(g); nodes.push(n); nodeByKey[key] = n;
      return n;
    }

    /* 真销毁一座晶冠：几何 / 纹理 / 表盘读数节点（材质 dispose 在 scene-core 里有意置空：着色器程序常驻） */
    function crownFree(cr) {
      if (cr.grp.parent) cr.grp.parent.remove(cr.grp);
      cr.grp.traverse(function (obj) {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) obj.material.dispose();
      });
      if (cr.segmentTexture) cr.segmentTexture.dispose();
      if (cr.clockEl && cr.clockEl.parentNode) cr.clockEl.parentNode.removeChild(cr.clockEl);
    }
    /* park = true：当前这座摘下停进停放槽（见 crownStow）；否则连停放槽一起真销毁（换图 / 销毁场景） */
    function crownDispose(park) {
      if (park !== true && crownParked) { crownFree(crownParked.c); crownParked = null; }
      if (!crown) return;
      if (park === true) crownStow(crown); else crownFree(crown);
      crown = null; crownHl = -1; crownHold = 0;
      syncGemLegend();
    }
    /* Q5.5 · 晶冠单槽停放（A）：消散完 / 被换下的晶冠摘出场景图但不销毁（GPU 缓冲留着）；同一角色、同一组分值再进，
       原样挂回、只把入场时钟与走针状态归零——入场动画与新建的一帧不差。槽里只放一座：停进新的，旧的真销毁（跨角色不累积） */
    var crownParked = null;
    function crownStow(cr) {
      if (crownParked && crownParked.c !== cr) crownFree(crownParked.c);
      if (cr.grp.parent) cr.grp.parent.remove(cr.grp);
      crownParked = { c: cr, sig: cr.sig };
    }
    /* 晶冠几何只由这 16 个分值决定（顶面八维 + 底面叙事八维，与 buildCrown 同一取法）；章节表圈随图固定，换图时停放槽已清 */
    function crownSig(cn, c, model, meta) {
      var a = [], i, d, s;
      for (i = 0; i < 8; i++) { d = model && model.attr[i]; s = d ? d.score : attrScore(c, ATTR_KEYS[i]); a.push(s == null ? 'n' : clamp(s / 100, 0, 1)); }
      for (i = 0; i < 8; i++) { d = model && model.meta && model.meta[i]; s = d ? d.score : meta.score[META_KEYS[i]]; a.push(s == null ? 'n' : clamp(s / 100, 0, 1)); }
      return cn.key + '|' + a.join(',');
    }
    function crownReuse(cn, model, sig) {
      var cr = crown && crown.sig === sig ? crown : crownParked && crownParked.sig === sig ? crownParked.c : null;
      if (!cr) return false;
      if (cr !== crown) { crownParked = null; if (crown) crownStow(crown); }
      cr._prewarmOnly = false;
      crown = cr; crownHl = -1; crownHold = 0;
      if (!cr.grp.parent) group.add(cr.grp);
      cr.model = model; cr.host = cn;
      cr.born = tAcc; cr.dying = 0; cr.ang = 0; cr.vel = CR_SPIN; cr.phase = 0; cr.sep = 0; cr.tension = 0;
      cr.storyPos = 0; cr.storyIdx = Math.max(0, cr.lastIdx); cr.lastSec = null; cr.readSec = null; cr.readIdx = -1; cr.clockText = ''; cr.hourAng = 0; cr.hourInit = false; cr.tickK = -1;
      /* 只在入场走完后才逐帧写的几件（扫描环 / 反向扫描面）回到初建值；其余每帧都由 updateCrown 按入场时钟重写 */
      cr.scan.position.y = 0; cr.scanRing.material.uniforms.uOn.value = 0; cr.scanDisc.material.opacity = 0;
      cr.scan2.position.y = 0; cr.scan2.scale.set(1, 1, 1); cr.scan2.material.uniforms.uOn.value = 0;
      var lc = lineComp();   /* 线宽补偿随视口：停放期间视口可能变过 */
      [cr.lines, cr.strings, cr.bridge, cr.lines2].forEach(function (o) { if (o && o.material.uniforms.uLine) o.material.uniforms.uLine.value = lc; });
      updateGemOverlays();
      updateCrown(0);
      syncGemLegend();
      return true;
    }

    /* 悬停巡礼的邻接表：每次换图重建一次（人名 → 相邻人名数组）。
       relation 是 {a,b} 无向边，同一对可能有多条不同 kind，去重后再入表。 */
    function buildAdj() {
      var key = graphPinKey || 'default';
      if (adjMap && adjKey === key) return adjMap;
      var rels = (graph && graph.relations) || [], map = {}, seen = {};
      for (var i = 0; i < rels.length; i++) {
        var r = rels[i], a = r && r.a, b = r && r.b;
        if (!a || !b || a === b) continue;
        var tag = a < b ? a + '|' + b : b + '|' + a;
        if (seen[tag]) continue;
        seen[tag] = 1;
        (map[a] || (map[a] = [])).push(b);
        (map[b] || (map[b] = [])).push(a);
      }
      adjMap = map; adjKey = key;
      return map;
    }

    function clearAll() {
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        group.remove(n.g);
        if (n.sp && n.sp.material) n.sp.material.dispose();
        if (n.halo && n.halo.material) n.halo.material.dispose();
        if (n.el && n.el.parentNode) n.el.parentNode.removeChild(n.el);
      }
      disposeStarField && disposeStarField(); disposeRoadBand && disposeRoadBand(); disposeRoadRim && disposeRoadRim(); disposeSpines && disposeSpines();
      if (window.CLArcana) window.CLArcana.dispose();
      nodes.length = 0; for (var k in nodeByKey) if (nodeByKey.hasOwnProperty(k)) delete nodeByKey[k];
      fibers.length = 0;
      disposeGlyphLines && disposeGlyphLines();
      crownDispose(); disposeNebulae && disposeNebulae();
    }

    function setGraph(g, opts) {
      labelRevision++;
      opts = opts || {};
      /* 换分类飞行：同一部书重建视图时（opts.morph），记下每颗星的当前位置与大小，重建后从旧位置飞到新扇区，镜头不重演入场 */
      var morphFrom = null;
      if (opts.morph && graph && g && nodes.length) { morphFrom = {}; nodes.forEach(function (n) { if (n.kind === 'char') morphFrom[n.key] = { p: n.pos.clone(), s: n.size }; }); }
      if (gemStageSaved) restoreCameraView(gemStageSaved.view);
      else if (previewCamera) restoreCameraView(previewCamera.view);
      clearAll(); relFocus = null; graph = g; adjMap = null; adjKey = ''; if (core && core.setGraph) core.setGraph(g); idle = !g; mode = 'atlas'; focusName = null; hoverName = null;
      gemBench = null; focusGem = null; gemStageOn = false; gemStageSaved = null; gemStageArea = null; gemPeer = null; gemChapter = null; gemScope = 'book';
      if (window.CLGemModel && window.CLGemModel.invalidate) window.CLGemModel.invalidate();
      if (!g) { buildIdle(); return; }
      var chars = g.characters || [], evs = g.events || [], rels = g.relations || [];
      graphPinKey = String(g.meta && (g.meta.source_hash || g.meta.graph_key) || g.title || 'default');
      try {
        var savedPins = JSON.parse(localStorage.getItem('castline.pins.' + graphPinKey) || '[]');
        if (Array.isArray(savedPins)) savedPins.forEach(function (name) { pinned[name] = 1; });
      } catch (e) {}
      var chapters = chapterList(g), buckets = chapterBuckets(chapters), bucketOf = {}, bucketEventCount = {};
      buckets.forEach(function (b) { b.members.forEach(function (m) { bucketOf[m] = b.label; }); });
      bucketMap = bucketOf;
      big = chars.length * chapters.length > 3000 || evs.length > 1500;

      // ---- 戏份统计 → 角色分级（tier）与权重（w）
      // 实测长尾极重（三国：585 人中 492 人零剧情点），分级是后面所有取舍的依据
      var evCount = {}, relCount = {};
      evs.forEach(function (e) {
        var eb = bucketOf[e.chapter || '未分章']; bucketEventCount[eb] = (bucketEventCount[eb] || 0) + 1;
        (e.characters || []).forEach(function (nm) { evCount[nm] = (evCount[nm] || 0) + 1; });
      });
      rels.forEach(function (r) { if (r.derived) return; relCount[r.a] = (relCount[r.a] || 0) + 1; relCount[r.b] = (relCount[r.b] || 0) + 1; });   // 推导的「同场」不计入「N 关系」与咖位
      // 全书统计：底面八维（戏份 / 张力 / 弧光 / 暗线）用对数刻度相对全书最高者
      var strifeCount = {}, turnCount = {}, darkCount = {};
      evs.forEach(function (e) {
        var st = /冲突|抉择|转折|高燃/.test(e.kind || ''), tu = /转折|领悟|抉择/.test(e.kind || '');
        (e.characters || []).forEach(function (nm) { if (st) strifeCount[nm] = (strifeCount[nm] || 0) + 1; if (tu) turnCount[nm] = (turnCount[nm] || 0) + 1; });
      });
      rels.forEach(function (r) { if (r.line === '暗线') { darkCount[r.a] = (darkCount[r.a] || 0) + 1; darkCount[r.b] = (darkCount[r.b] || 0) + 1; } });
      function maxOf(o) { var m = 0; for (var kk in o) if (o[kk] > m) m = o[kk]; return m; }
      var chapIndex = {}; chapters.forEach(function (ch, ci) { chapIndex[ch] = ci; });
      bookStats = { maxEc: maxOf(evCount), maxRc: maxOf(relCount), maxStrife: maxOf(strifeCount), maxTurn: maxOf(turnCount), maxDark: maxOf(darkCount), chapters: chapters, chapIndex: chapIndex };
      focusMeta = null;
      function tierOf(c) {
        var role = c.role || '', imp = c.importance || 0, ec = evCount[c.name] || 0, rc = relCount[c.name] || 0;
        if (role === '主角' || imp >= 78) return 0;                       // 核心
        if (role === '反派' || role === '核心配角' || imp >= 55) return 1; // 主要
        if (role === '配角' || imp >= 30 || ec >= 2 || rc >= 2) return 2;  // 次要
        if (ec >= 1 || rc >= 1) return 3;                                  // 边缘（有一次戏份）
        return 4;                                                          // 长尾：零戏份
      }
      function weightOf(c) {
        return (c.importance || 0) + (evCount[c.name] || 0) * 9 + (relCount[c.name] || 0) * 6 +
          (c.role === '主角' ? 70 : (c.role === '反派' || c.role === '核心配角') ? 34 : c.role === '配角' ? 12 : 0);
      }

      // 中列 → 星座天球（v17.15）：星座 = 阵营 · 方位 = 立场（主角方居中 / 盟友左弧 / 中立上弧 / 摇摆下弧 / 对立右弧）· 星等 = 咖位
      var nC = chars.length, big2 = nC > 26;
      // v19.1 默认星链布局（全员一条连续长链）；?layout=camps 回到阵营椭圆布局
      var LM = layoutMode();
      var lay = (LM === 'sky' && CN.layoutSky ? CN.layoutSky : LM === 'camps' ? CN.layoutCamps : LM === 'chain' ? CN.layoutChain : CN.layoutRoad)(chars, rels, g.camps || [], tierOf, weightOf);
      var road = lay.mode === 'chain' || lay.mode === 'road', skyL = lay.mode === 'sky';   /* skyL：平面天球——旧装饰层（章节列 / 功能枢 / 尘带 / 沿环 / 秘仪）一律不建 */
      layoutInfo = lay; campIndex = {}; campOfName = {};
      lay.camps.forEach(function (cp) {
        cp.names = cp.members.map(function (q) { return chars[q].name; }); cp.leadName = cp.lead != null ? chars[cp.lead].name : '';
        campIndex[cp.name] = cp; cp.names.forEach(function (m) { campOfName[m] = cp.name; });
      });
      core.setLayoutInfo(lay);
      core.setBig(big2);
      var halfW = lay.halfW, posOf = lay.pos;
      nTail = big2 ? chars.filter(function (c) { return tierOf(c) >= 4; }).length : 0;
      core.setNTail(nTail);
      chars.forEach(function (c, i) {
        var ec = evCount[c.name] || 0, rc = relCount[c.name] || 0, tr = tierOf(c);
        var cp = campIndex[campOfName[c.name]] || null, isField = !cp || cp.name === CN.FIELD;
        var sub = (c.role || '') + (ec ? ' · ' + ec + ' 剧情点' : '') + (rc ? ' · ' + rc + ' 关系' : (ec ? '' : ' · 无戏份'));
        // 超过 1600 角色时，长尾姓名不占 DOM；数据仍在 node/graph 中，attachLabel 会在搜索、悬停、锁定或聚焦时按需恢复。
        var n = mkNode('c:' + c.name, 'char', c.name, sub, nC <= 1600 || tr < 4);
        n.data = c; n.color = roleColor(c.role);
        n.sp.material.color.copy(n.color); n.halo.material.color.set(stanceHalo(isField ? '' : (CN.normStance(c.stance) || cp.stance || ''), c.role));
        // v19 星体：0/1 等星带衍射芒；主星（各座 lead）加星等环；每星独立微闪相位
        if (!big2 && tr <= 1) n.sp.material.map = texStar;
        n.isLead = !!(cp && cp.leadName === c.name && !isField && cp.names.length >= 2);
        n.twPh = rnd(i * 9.17) * 6.283; n.twAmp = tr <= 1 ? 0.03 : tr === 2 ? 0.06 : 0.09;
        if (n.isLead && !big2 && !skyL) {
          var ringCol = cp.color || CN.COLOR[cp.stance] || 0xcbbcf0;
          var lr = ribbon(0.66, 0.72, 96, { mode: 2, ticks: 36, base: 0.9, ca: ringCol, cb: 0xfff1da, hot: 0xfff1da });
          lr.rotation.x = Math.PI / 2; lr.renderOrder = 3; n.g.add(lr); n.ring = lr;
        }
        n.tier = tr; n.w = weightOf(c); n.ec = ec; n.rc = rc; n.camp = isField ? '' : cp.name;
        n.seq = i;   // 建档次序（重要度降序）；星路布局下面会改写为「座序 × 1000 + 座内星等」，让点名一座一座地走
        var imp = clamp((c.importance || 30) / 100, 0.1, 1);
        // 群像层刻意做小做暗：几百个 halo 叠加会把天球烧成一片白
        n.sizeTo = !big2 ? (14 + imp * 30) * (road ? 0.68 : skyL ? 0.6 : 1) : (road || skyL) ? (tr >= 4 ? 4.8 + imp * 2.8 : 12.5 + (3 - tr) * 4.8 + imp * 9) : tr >= 4 ? 3.4 + imp * 2.2 : (7 + (3 - tr) * 3.6 + imp * 10);
        n.size = 0;
        n.haloK = !big2 ? 3.2 : tr >= 4 ? 1.25 : tr <= 1 ? 2.55 : 2.0;
        n.baseAlpha = (big2 && tr >= 4) ? 0.20 : (big2 && tr === 3 ? 0.62 : 1);
        n.render = !(nC > 1600 && tr >= 4 && !tailShow && !pinned[c.name]); n.g.visible = n.render;
        n.alpha = n.alphaTo = n.baseAlpha;
        var s0 = posOf[i];
        n.to.set(s0.x, s0.y, s0.z); n.pos.copy(n.to); n.from.copy(n.to);
        n.atlas = n.to.clone();
        // 星路：退入深空的外圈略暗（大气透视），前景座更亮
        if (lay.mode === 'road') { var dk = clamp(1 + s0.z / 1500, 0.62, 1.04); n.baseAlpha *= dk; n.alpha = n.alphaTo = n.baseAlpha; }
        n.el.classList.add('t' + tr);
        if (tr >= 3) n.el.classList.add('minor');
        // 星图排版：同座成员按亮度得希腊字母星名（α β γ …），主星 = α
        if (cp && !isField && cp.names.length >= 2) { var bi = cp.names.indexOf(c.name); if (bi >= 0 && bi < BAYER.length) { n.el.children[0].dataset.b = BAYER[bi]; n.bayer = BAYER[bi]; } }
        if (pinned[c.name]) { n.el.classList.add('pin'); n.render = true; n.g.visible = true; attachLabel(n); }
      });
      // 星路：每一座的 α 星（该座最亮者）是这座星座的名字，绕过标签预算（仍走避让）；小图谱给它衍射芒
      (lay.knots || []).forEach(function (kn, ki) { kn.members.forEach(function (q, qi) { var mn = nodeByKey['c:' + chars[q].name]; if (mn) { mn.roadSeq = kn.seq == null ? ki : kn.seq; mn.seq = mn.roadSeq * 1000 + qi; } }); if (kn.tail || !kn.members.length) return; var an = nodeByKey['c:' + chars[kn.members[0]].name]; if (!an) return; an.knotAlpha = true; if (!big2 && an.tier <= 2) an.sp.material.map = texStar; });
      Object.keys(pinned).forEach(function (name) { if (!nodeByKey['c:' + name]) delete pinned[name]; });
      // 星座名标：每个阵营一枚（散星不标），锚在星座左上；副行 = 立场 · 人数；第三行 = 阵营简介 / 主星；可悬停 / 点击
      lay.camps.forEach(function (cp, cpi) {
        if (skyL) return;   // 平面天球：团名由星域层（CLSkyField）写在扇区外缘
        if (cp.name === CN.FIELD || cp.names.length < 2) return;   // 单星不立座名：角色标签第三行已带阵营 · 立场
        var n = mkNode('g:' + cp.name, 'camp', cp.name, (cp.stance || '立场未定') + ' · ' + cp.names.length + ' 人 · ' + (cp.figure ? cp.figure.zh + '座 ' + cp.figure.en + ' · ' : (STANCE_EN[cp.stance || ''] || 'UNALIGNED') + ' · ') + roman(cp.names.length) + ' STARS');
        n.data = { camp: cp.name, stance: cp.stance || '', brief: cp.brief || '', members: cp.names, lead: cp.leadName, size: cp.names.length };
        n.seq = cpi;   // 座名按阵营固有次序点亮（同一序列每秒往前推，不再随机取样）
        var col = cp.color || CN.COLOR[cp.stance] || 0xd9b8ff;
        n.color = new T.Color(col); n.sp.material.color.copy(n.color); n.halo.material.color.set(col);
        n.sizeTo = 4.5; n.size = 0; n.haloK = 5.5; n.baseAlpha = 0.85; n.alpha = n.alphaTo = 0.85;
        var fitR = campFitR(cp, lay);
        // 座名挂在椭圆顶缘外侧偏左，避开常落在左上的 α 星，也不压住轨道丝带；星链模式挂在段首 α 星左上
        if (road) n.to.set(cp.labelX, cp.labelY, cp.labelZ || 10); else n.to.set(cp.cx - fitR * 0.52, cp.cy + cp.fitRy + 46, cp.cz + 10); n.pos.copy(n.to); n.from.copy(n.to); n.atlas = n.to.clone();
        n.el.dataset.st = cp.stance || '';
        n.el.children[2].innerHTML = cp.brief ? escH(cp.brief) : ('主星 <b>' + escH(cp.leadName) + '</b>');
        n.el.style.pointerEvents = 'auto';
        n.el.addEventListener('pointerenter', function () { S.hoverCamp(cp.name); fire('hoverCamp', n); });
        n.el.addEventListener('pointerleave', function () { S.hoverCamp(null); fire('hoverCamp', null); });
        n.el.addEventListener('click', function (e) { e.stopPropagation(); fire('selectNode', n); });
      });
      // v19：外围信息列贴近一些，星座本体在全景里占更大画幅（右列功能枢仍在星座椭圆之外）
      colX = Math.max(COL_X, halfW + (road ? 118 : 196)); nCharCount = nC;   // 星路：外围两列再贴近，星座本体占更大画幅
      // 左列：章节桶（时间自上而下）
      // 章节标签有三行（名 / 剧情点 / 主导角色），行距要足够，否则相邻章节标签互相压字
      var nCh = buckets.length, spanH = clamp(nCh * (nCh <= 18 ? 46 : 30), 300, 900);
      var chapLane = laneLayout(nCh, spanH, nCh >= 12 ? 4 : 3);
      if (!skyL) buckets.forEach(function (b, i) {
        var cnt = bucketEventCount[b.label] || 0;
        var lab = b.label.length > 14 ? b.label.slice(0, 14) + '…' : b.label;
        var n = mkNode('h:' + b.label, 'chap', lab, cnt + ' 剧情点' + (b.members.length > 1 ? ' · ' + b.members.length + ' 章' : ''));
        n.data = { chapter: b.label, members: b.members, count: cnt }; n.color = new T.Color(0xd8ccff); n.sp.material.color.copy(n.color); n.sp.material.map = texTick; n.halo.material.color.set(haloOf('chap')); n.haloK = 1.5;
        n.sizeTo = (7 + Math.min(cnt, 8) * 1.1) * (road ? 0.62 : 1); n.size = 0;
        if (road) { n.baseAlpha = 0.55; n.alpha = n.alphaTo = 0.55; }   // 星路：章节列退为外围信息轨道，不与星座争亮
        // v25 · 时间脊：分节呼吸的行距 + 低频摆动的边缘 + 反相的纵深，替代等距一条直线
        var sw = laneSway(nCh === 1 ? 0 : i / (nCh - 1), road ? 22 : 34, road ? 40 : 66);
        n.seq = i;
        n.to.set(-colX + sw.x - laneIndent(i, nCh >= 12 ? 4 : 3, 16), chapLane[i], sw.z + (rnd(i * 4.1) - 0.5) * 18);
        n.pos.copy(n.to); n.atlas = n.to.clone();
      });
      // 右列：叙事功能枢（v17.15）—— 剧情点类型的汇聚点（高燃 / 转折 / 抉择 / 冲突 / 关系 / 领悟 / 日常）；
      // 角色 → 枢的纤维 = 该角色在该类剧情点中的参与量。这是雷达图里没有、但在全景里最值得看的信息：谁扛冲突、谁承转折
      hubList = CN.hubs(evs, chars);
      var nH = hubList.length, hubSpan = clamp(nH * 78, 300, 560), hubLane = laneLayout(nH, hubSpan, 3);
      if (!skyL) hubList.forEach(function (hb, i) {
        var n = mkNode('k:' + hb.kind, 'hub', hb.kind, hb.en + ' · ' + hb.count + ' 点');
        n.data = { hub: hb.kind, en: hb.en, count: hb.count, share: hb.share, top: hb.top, who: hb.who };
        var col = KIND_COL[hb.kind] || 0xffd166;
        n.color = new T.Color(col); n.sp.material.color.copy(n.color); n.halo.material.color.set(col);
        n.sizeTo = 8 + Math.min(1, hb.share * 3) * 9; n.size = 0; n.haloK = 2.8;
        var swH = laneSway(nH === 1 ? 0 : i / (nH - 1), 26, 52);
        n.seq = i;
        n.to.set(colX - swH.x + laneIndent(i, 3, 18), hubLane[i], swH.z); n.pos.copy(n.to); n.atlas = n.to.clone();
        n.el.children[2].innerHTML = hb.top.slice(0, 3).map(function (t, ti) { return (ti ? escH(t.name) : '<b>' + escH(t.name) + '</b>') + ' ' + t.n; }).join(' · ');
      });
      // 八维属性节点：全景不再占一列（属性只属于聚焦晶冠）；节点保留但隐藏，聚焦时从角色星体涌出并吸附到晶冠顶点
      ATTR_KEYS.forEach(function (k, i) {
        var n = mkNode('a:' + k, 'attr', k, ATTR_EN[i], false);
        n.el.style.pointerEvents = 'auto'; n.el.addEventListener('click', function (e) { e.stopPropagation(); fire('selectNode', n); });   // v21：点属性标签 = 右坞该维全书排名
        n.el.setAttribute('role', 'button'); n.el.setAttribute('tabindex', '0');
        n.el.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); fire('selectNode', n); } });
        n.data = { attr: k }; n.seq = i; n.color = new T.Color(0x8af2d0); n.sp.material.color.copy(n.color); n.halo.material.color.set(haloOf('attr'));
        n.sizeTo = 0; n.size = 0; n.alpha = n.alphaTo = 0; n.baseAlpha = 0; n.render = false; n.g.visible = false;
        n.to.set(0, 0, 0); n.pos.copy(n.to); n.atlas = n.to.clone();
      });
      // 底面八维节点：全景态不渲染、不占标签；聚焦时从角色星体涌出并吸附到底面晶锥顶点
      META_KEYS.forEach(function (k, i) {
        var n = mkNode('m:' + k, 'meta', k, META_EN[i], false);
        n.el.style.pointerEvents = 'auto'; n.el.setAttribute('role', 'button'); n.el.setAttribute('tabindex', '0');
        n.el.addEventListener('click', function (e) { e.stopPropagation(); fire('selectNode', n); });
        n.el.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); fire('selectNode', n); } });
        n.data = { meta: k }; n.seq = i; n.color = new T.Color(0xf0e6ff); n.sp.material.color.copy(n.color); n.halo.material.color.set(0xb98cff);
        n.sizeTo = 0; n.size = 0; n.alpha = n.alphaTo = 0; n.render = false; n.g.visible = false; n.haloK = 2.6;
        n.to.set(0, 0, 0); n.pos.copy(n.to); n.atlas = n.to.clone();
      });
      // 点位交错核实：默认全景机位下屏幕空间松弛，可见节点两两 ≥ 15px
      if (!skyL) relaxAtlas();   // 平面天球的星距由蓝噪声铺点保证；屏幕松弛会把星推过扇区界线
      var seed = 1;
      // 纤维：章节桶→角色，按 (桶,角色) 聚合成束，束内股数随剧情点数与权重
      var pairs = {};
      evs.forEach(function (e) {
        var hk = 'h:' + bucketOf[e.chapter || '未分章'];
        (e.characters || []).forEach(function (nm) {
          var ck = 'c:' + nm; if (!nodeByKey[ck] || !nodeByKey[hk]) return;
          var p = pairs[hk + '|' + ck] || (pairs[hk + '|' + ck] = { h: nodeByKey[hk], c: nodeByKey[ck], n: 0, hot: 0 });
          p.n++; if (e.kind === '高燃' || e.kind === '转折' || e.kind === '抉择') p.hot++;
        });
      });
      Object.keys(pairs).forEach(function (k) {
        var p = pairs[k], imp = clamp((p.c.data.importance || 30) / 100, 0, 1);
        // 出场纤维是外围证据轨道，不再与星座关系线争夺前景亮度；信息仍保留，
        // 仅把线束压成有方向的背景层，悬停 / 聚焦时仍会由高亮通道恢复。
        var w = clamp(0.22 + Math.log2(1 + p.n) * 0.15 + p.hot * 0.05 + imp * 0.10, 0.22, 0.62);
        var strands = big ? 1 : clamp(Math.round(1 + p.n * 0.62 + p.hot * 0.30), 1, 4);
        for (var s_ = 0; s_ < strands; s_++) { addFiber(p.h, p.c, w * (s_ === 0 ? 1 : 0.46), C_FIBER, 'ev', seed++, false, 0.34); if (road && big) fibers[fibers.length - 1].quiet = true; }   // 大图谱星路：出场纤维默认静默，悬停章节 / 角色时亮
      });
      // 纤维：章节链（时间连续性，细股）
      for (var i = 0; i + 1 < buckets.length && !skyL; i++) {
        var a = nodeByKey['h:' + buckets[i].label], b = nodeByKey['h:' + buckets[i + 1].label];
        addFiber(a, b, 0.22, C_FIBER, 'chain', seed++);
        if (!big) addFiber(a, b, 0.16, C_FIBER, 'chain', seed++);
      }
      // 纤维：角色 → 叙事功能枢（参与 ≥1 次；粗细 = 参与量对数）
      var hubBy = {}; hubList.forEach(function (hb) { hubBy[hb.kind] = hb; });
      var partN = {};
      evs.forEach(function (e) { var kd = hubBy[e.kind] ? e.kind : (hubBy['日常'] ? '日常' : null); if (!kd) return; (e.characters || []).forEach(function (nm) { partN[nm + '|' + kd] = (partN[nm + '|' + kd] || 0) + 1; }); });
      Object.keys(partN).forEach(function (pk) {
        var sp = pk.lastIndexOf('|'), cn = nodeByKey['c:' + pk.slice(0, sp)], kd = pk.slice(sp + 1), hn = nodeByKey['k:' + kd];
        if (!cn || !hn) return;
        // 大规模：只给核心 / 主要角色连功能枢，否则数百条长线把右半屏刷成一片亮
        if (big && cn.tier >= (nCharCount > 200 ? 2 : 3)) return;
        var cnt = partN[pk], w = clamp(0.18 + Math.log2(1 + cnt) * 0.16, 0.18, 0.58);
        addFiber(cn, hn, w, new T.Color(KIND_COL[kd] || 0xffd166), 'hub', seed++, false, 0.46);
        if (road) fibers[fibers.length - 1].quiet = true;   // 星链 / 星路：外围纤维默认静默，悬停 / 聚焦才亮
      });
      // 纤维：星座引导线（孤星接到本星座最近的亮星，保证每个星座图形连通；细、暗、近直）
      (lay.guides || []).forEach(function (gd) {
        var a = nodeByKey['c:' + chars[gd[0]].name], b = nodeByKey['c:' + chars[gd[1]].name]; if (!a || !b) return;
        addFiber(a, b, 0.14, new T.Color(0x8d84a8), 'guide', seed++, true, 0.12);
      });
      // 星座字形线：只补足没有真实关系的骨架，作为低亮度视觉结构；真实关系仍走下方的关系线。
      // 星座字形：清晰直线由 glyphLine 叠加层绘制（星图风格）；这里只给没有真实关系的骨架一条极淡的直纤维作光晕。
      (lay.glyphEdges || []).forEach(function (ge) {
        var a = nodeByKey['c:' + chars[ge.a].name], b = nodeByKey['c:' + chars[ge.b].name]; if (!a || !b) return;
        if (!ge.rel) addFiber(a, b, 0.16, new T.Color(ge.color || 0xcbbcf0), 'glyph', seed++, false, 0);
      });
      buildGlyphLines(lay, chars);
      if (lay.mode === 'road') buildStarField(lay, chars); else disposeStarField();
      if (!skyL) { buildRoadBand(lay); buildRoadRim(lay); buildAtlasSpines(); }
      // 秘仪层（js/arcana.js）：深渊涡 / 符文卷环 / 低语微尘。缺文件也不影响主图，故整段守空。
      // v30：载荷补上剧情流层要的四样（graph / chars / pos / lay）。剧情树要按角色落点拉引线、
      // 按章节序放分叉点，这些只有布局阶段知道；插件位一次给全，免得每加一层就来改这行。
      if (window.CLArcana && !skyL) window.CLArcana.build({ T: T, group: group, rimR: lay.rimR || 0, rimV: lay.rimV || 0, pitch: lay.pitch || 0, big: big, knots: lay.knots || [],
        graph: g, chars: chars, pos: lay.pos || [], lay: lay, mode: lay.mode || '' });
      // v90 F7 · 关系网密度纪律（规格 D0「默认不是满屏蛛网」）：关系超过 REL_WEB_MAX 条时，关系镜头全景只画
      // 两端都重要的前 REL_WEB_MAX 条（按 min(两端权重) + 0.2·强度 排序，确定性）；其余不删数据，悬停/选中角色时照常显现。
      var relRank = rels.map(function (r, i) {
        var na = nodeByKey['c:' + r.a], nb = nodeByKey['c:' + r.b];
        return { i: i, s: na && nb ? Math.min(na.w || 0, nb.w || 0) + 0.2 * (isFinite(r.strength) ? r.strength : 0.5) : -1 };
      }).filter(function (x) { return x.s >= 0; }).sort(function (x, y) { return y.s - x.s || x.i - y.i; });
      var relKeep = {}, relPruned = relRank.length > REL_WEB_MAX;
      relRank.slice(0, REL_WEB_MAX).forEach(function (x) { relKeep[x.i] = 1; });
      relWeb = { total: relRank.length, shown: relPruned ? REL_WEB_MAX : relRank.length, pruned: relPruned };
      // 纤维：角色↔角色 —— 阵营内 = 星座连线（低弧贴天球，明线实 / 暗线虚）；跨阵营 = 高弧；对立立场之间用绯红
      rels.forEach(function (r, ri) {
        var a = nodeByKey['c:' + r.a], b = nodeByKey['c:' + r.b]; if (!a || !b) return;
        // v90 F4：关系类别唯一归一（js/domains/domains-model.js relClass：合作/亲缘/情感/对立/暗线/其他），
        // 色与线型（dash 0 实 / 1 虚 / 2 点 / 3 点划）与星域图例同一张表；不再按立场推断「对立」色。
        var rc = window.CLDomainsModel && CLDomainsModel.relClass ? CLDomainsModel.relClass(r) : null;
        var dark = rc ? rc.id === 'dark' : r.line === '暗线', intra = !!a.camp && a.camp === b.camp, st = big ? (intra ? 1 : 2) : (dark ? 2 : 3);
        if ((road || skyL) && intra) st = 1;   // 星路：座内关系只留一股细线，选中阵营时是「关系脉络」而不是一把亮扇
        if (rc && rc.dash) st = 1;   // 虚 / 点 / 点划只画一股：多股错位会把线型糊成实线
        var col = rc ? new T.Color(rc.hex) : (dark ? new T.Color(0x9a7cff) : ((!intra && opposed(CN.normStance(a.data.stance), CN.normStance(b.data.stance))) ? C_REL_HOT : relColor(r.kind)));
        for (var k = 0; k < st; k++) { addFiber(a, b, ((dark ? 0.3 : 0.4) + (r.strength || 0.5) * 0.6) * ((road || skyL) && intra ? 0.42 : 1), col, 'rel', seed++, rc ? rc.dash : dark, intra ? 0.10 : skyL ? 0.36 : 0.9); if (intra || road || skyL) fibers[fibers.length - 1].quiet = true; fibers[fibers.length - 1].relKind = r.kind || null; fibers[fibers.length - 1].relClass = rc ? rc.id : ''; fibers[fibers.length - 1].webCore = skyL ? intra : (!relPruned || !!relKeep[ri]); }   /* 平面天球里跨组关系由星域层的束丝表达，关系层只画组内短线 */   // relKind：v90 F3 focusRelation 按类型点亮 · relClass：v90 F4 类别
      });
      // 视觉预算按规模分档；原始关系仍在 graph 中，只有绘制层做裁剪。段数同理：小图 36 段圆润，大图 22 段省顶点。
      SEG = big2 ? 22 : 36;
      var fLimit = nC > 5000 ? 1800 : nC > 2000 ? 2400 : nC > 800 ? 3200 : nC > 300 ? 4400 : 6500;
      fiberRaw = fibers.length;
      trimFibers(fLimit);
      buildFiberMesh();
      // 纤维越多越压暗：加性混合下 1000+ 条会糊成一片
      var fiberMat = core.getFiberMat ? core.getFiberMat() : null;
      if (fiberMat) {
        fiberMat.uniforms.uScale.value = big2 ? clamp(0.72 - fibers.length / 5200, 0.38, 0.68) : clamp(1.15 - fibers.length / 2600, 0.42, 1);
        // 角色星座是主视觉：外围出场 / 枢纤维只保留结构读数，不盖过轨道、主星与关系骨架。
        fiberMat.uniforms.uBase.value = big2 ? 0.13 : 0.205;
        fiberMat.uniforms.uDim.value = big2 ? 0.036 : 0.058;
        if (fiberMat.uniforms.uTypeK) fiberMat.uniforms.uTypeK.value = clamp(Math.sqrt(48 / Math.max(1, relWeb.shown || rels.length)), 0.3, 1) * (relWeb.pruned ? 0.8 : 1);   // v90 F4 · F7：按全景实际画出的条数
      }
      /* 样本密度分级：按实际可见角色 / 已绘制纤维 / 星座数量连续降能量。
         旧版只按 big2 二档调 bloom，大样本中每颗星的 halo 与星云仍会在
         additive 合成后相互叠加成白雾。小样本的三项均低于门槛，profile=1，
         所以原有颜色与亮度不发生变化。 */
      var visibleChars = nodes.reduce(function (n, x) { return n + (x.kind === 'char' && x.render ? 1 : 0); }, 0);
      /* 42 颗以内视为小图：不因关系线数量偶发偏高而改变既有色彩。 */
      var sizeGate = clamp((visibleChars - 42) / 100, 0, 1);
      var dn = clamp((visibleChars - 42) / 260, 0, 1) * sizeGate;
      var df = clamp((fibers.length - 160) / 3200, 0, 1) * sizeGate;
      var dk = clamp(((lay.knots || []).length - 10) / 48, 0, 1) * sizeGate;
      var densityK = clamp(1 - dn * 0.46 - df * 0.26 - dk * 0.10, 0.34, 1);
      var densityProfile = { k: densityK, star: 0.56 + densityK * 0.44, nebula: 0.42 + densityK * 0.58,
        bloom: 0.42 + densityK * 0.58, threshold: 0.85 + (1 - densityK) * 0.07,
        nodes: visibleChars, fibers: fibers.length, knots: (lay.knots || []).length };
      if (core.setDensityProfile) core.setDensityProfile(densityProfile);
      densityBloom = densityProfile.bloom;
      // 大图谱保持深海底色和线条层次；小图谱才允许更强的电影级泛光。
      var bloom = core.getBloom ? core.getBloom() : core.bloom;   // v90 F7：活 getter，大图 0.30 / 小图 0.48 自此真正生效
      if (bloom) { bloomBase = big2 ? 0.30 : 0.48; bloom.strength = bloomBase * glowK * densityBloom; }
      // 入场编排：中列角色先亮（按重要度），左列章节自上而下推进，右列属性最后收口
      var iC = 0, iH = 0;
      nodes.forEach(function (n) {
        if (n.kind === 'char') n.delay = (n.roadSeq != null) ? Math.min(0.62, 0.04 + n.roadSeq * 0.05) : Math.min(0.42, iC++ * 0.022);   // 星路：沿路序依次点亮
        else if (n.kind === 'chap') n.delay = 0.10 + Math.min(0.50, iH++ * 0.012);
        else if (n.kind === 'attr') n.delay = 0.44 + ATTR_KEYS.indexOf(n.data.attr) * 0.03;
        else if (n.kind === 'hub') n.delay = 0.40 + Math.min(0.24, iH * 0.02);
        else if (n.kind === 'camp') n.delay = 0.28;
        n.sizeAtlas = n.sizeTo;   // 全景尺寸记下来：返回全景时按此恢复（大图谱不再退回小图谱的尺寸公式）
        var mf = morphFrom && morphFrom[n.key];
        if (mf) { n.from.copy(mf.p); n.pos.copy(mf.p); n.size = mf.s; n.delay = Math.min(0.28, (n.roadSeq || 0) * 0.03); }
      });
      buildNebulae(lay);
      if (morphFrom) {
        grow = 1; growStart = tAcc - 10; animStart = tAcc; animDur = calm ? 0.01 : 1.25; dirty = true; lodDirty = true;
        groupXTo = atlasShift();
        /* 调用方在同一任务补全标签后统一量盒；其它 setGraph 路径照旧就地量。 */
        if (opts.deferMeasure !== true) measureLabels();
        fire('stats', stats());
        return;
      }
      grow = 0; growStart = tAcc; animStart = tAcc; animDur = 1.6; dirty = true; lodDirty = true;
      groupXTo = atlasShift(); group.position.x = groupXTo;
      // 镜头语言 · 全景入场：低角度远景升起并推近，三列像从雾中浮出
      camera.position.set(-150, -170, atlasDist() * 1.55); controls.target.set(0, -50, 0);
      flyTo(new T.Vector3(0, 30, atlasDist()), new T.Vector3(0, 0, 0), 2.6);
      measureLabels();
      fire('stats', stats());
    }
    var big = false, nCharCount = 0, nTail = 0, fiberBudget = 0, fiberTrimmed = 0, fiberRaw = 0;
    // 全景取景：按「三列的实际横向跨度」算距离，而不是按节点总数。
    // 用节点数算会为了把 447 个群像层微点全塞进画面而把相机拉得过远，主阵反而缩成一团。
    function atlasDist() {
      if (layoutInfo && layoutInfo.mode === 'sky') {
        // 平面天球：整张星域（含团名带）占舞台高度约 84%、宽度约 80%；顶栏与底栏各让出一截
        /* 团名写在圆外：纵向算到 1.12R（上下团名），横向算到 1.30R（左右团名朝外横排） */
        var Rk = (layoutInfo.rimR || 400), pk = layoutInfo.pitch || 0, vfk = Math.tan(camera.fov * Math.PI / 360), hfk = vfk * Math.max(0.2, camera.aspect);
        var vh = Math.max(200, core.getH()), fracH = Math.max(0.5, (vh - 140) / vh) * 0.94;
        var dVk = (Rk * 1.12 * Math.cos(pk) + 20) / (vfk * fracH), dHk = Rk * 1.30 / (hfk * 0.94);
        return clamp(Math.max(dVk, dHk), 500, 6000);
      }
      var halfSpan = colX + 84;
      var viewW = core.getW();
      var hfov = Math.atan(Math.tan(camera.fov * Math.PI / 360) * Math.max(0.2, camera.aspect)), vfov = camera.fov * Math.PI / 360;
      var safeW = Math.max(240, viewW - safe.left - safe.right);
      // 只做部分退让：完全塞进安全带会把整张图缩得太小；
      // 真正压着面板的标签由 HUD 占位负责剔除，这里只需把重心让开一点。
      // v21：星路允许伸到玻璃面板之下（标签仍避让面板），取景只做轻微退让，星座本体占满宽屏
      var corr = layoutInfo && layoutInfo.mode === 'road' ? clamp(1 + (viewW / safeW - 1) * 0.22, 1, 1.12) : clamp(1 + (viewW / safeW - 1) * 0.62, 1, 1.3);
      var dH = halfSpan / Math.max(0.2, Math.tan(hfov)) * 1.06 * corr;
      // 星座天球有纵向跨度（上弧中立 / 下弧摇摆），取景同时满足横向与纵向
      var dV = layoutInfo ? (layoutInfo.halfH + 110) / Math.max(0.2, Math.tan(vfov)) * 1.04 : 0;
      return clamp(Math.max(dH, dV), 900, 3000);
    }
    // 世界坐标 / 屏幕像素 的换算（用于把三列居中到安全带里）
    function worldPerPx(d) {
      var hfov = Math.atan(Math.tan(camera.fov * Math.PI / 360) * Math.max(0.2, camera.aspect));
      return (2 * d * Math.tan(hfov)) / Math.max(1, core.getW());
    }
    function atlasShift() { return ((safe.left - safe.right) / 2) * worldPerPx(atlasDist()); }

    // 默认全景机位下的屏幕空间松弛：投影全部可见点位，两两距离 < MINPX 的沿连线推开。
    // 只有角色列可位移（累计 ≤ CAP 单位），章节/属性两列保持直线；结果写回 atlas。
    function relaxAtlas() {
      var dist = atlasDist(), cam = new T.PerspectiveCamera(camera.fov, Math.max(0.2, W / H), 1, 6000);
      cam.position.set(0, 30, dist); cam.lookAt(0, 0, 0); cam.updateMatrixWorld(true); cam.updateProjectionMatrix();
      var gx = atlasShift(), hw = W / 2, hh = H / 2, wpp = worldPerPx(dist), MINPX = 15, CAP = 46, CAPC = 12, moved = 0;
      var list = nodes.filter(function (n) { return n.kind !== 'idle' && n.kind !== 'camp' && n.kind !== 'attr' && n.render && !(n.kind === 'char' && n.tier >= 4); });
      if (list.length < 2 || W < 200) return 0;
      list.forEach(function (n) { n._rx = 0; n._ry = 0; });
      for (var it = 0; it < 12; it++) {
        var i, j, any = 0;
        for (i = 0; i < list.length; i++) { var n = list[i]; _v.copy(n.atlas); _v.x += gx; _v.project(cam); n.sx = _v.x * hw + hw; n.sy = -_v.y * hh + hh; }
        list.sort(function (a, b) { return a.sx - b.sx; });
        for (i = 0; i < list.length; i++) {
          var a = list[i];
          for (j = i + 1; j < list.length; j++) {
            var b = list[j], dx = b.sx - a.sx; if (dx >= MINPX) break;
            var dy = b.sy - a.sy; if (Math.abs(dy) >= MINPX) continue;
            var am = a.kind === 'char', bm = b.kind === 'char';
            var d = Math.sqrt(dx * dx + dy * dy), ux, uy;
            if (d < 0.01) { ux = 0.7; uy = 0.7; d = 0.01; } else { ux = dx / d; uy = dy / d; }
            var push = (MINPX - d) * 0.5 * wpp * 1.1;
            if (am !== bm) push *= 1.6;
            // 角色可全向位移；章节 / 属性只沿列方向（y）微调，列的直线感保留
            if (am) { if (Math.hypot(a._rx, a._ry) < CAP) { a.atlas.x -= ux * push; a.atlas.y += uy * push; a._rx -= ux * push; a._ry += uy * push; any++; } }
            else if (Math.abs(a._ry) < CAPC) { var ay = (uy || 0.7) * push * 0.6; a.atlas.y += ay; a._ry += ay; any++; }
            if (bm) { if (Math.hypot(b._rx, b._ry) < CAP) { b.atlas.x += ux * push; b.atlas.y -= uy * push; b._rx += ux * push; b._ry -= uy * push; any++; } }
            else if (Math.abs(b._ry) < CAPC) { var by = (uy || 0.7) * push * 0.6; b.atlas.y -= by; b._ry -= by; any++; }
          }
        }
        moved += any; if (!any) break;
      }
      list.forEach(function (n) { n.to.copy(n.atlas); n.pos.copy(n.atlas); n.from.copy(n.atlas); });
      relaxMoved = moved;
      return moved;
    }
    var relaxMoved = 0;

    function buildIdle() {
      // 加载中的抽象神经网：无标签
      var N = 26;
      for (var i = 0; i < N; i++) {
        var n = mkNode('i:' + i, 'idle', '', '');
        var col = i % 3; n.to.set((col - 1) * colX * 0.9, (rnd(i * 3.3) - 0.5) * 640, (rnd(i * 1.9) - 0.5) * 200);
        n.pos.copy(n.to); n.sizeTo = 6 + rnd(i) * 10; n.size = 0; n.color = new T.Color(0x9a86ff); n.sp.material.color.copy(n.color); n.halo.material.color.set(haloOf('idle'));
        n.el.style.display = 'none';
      }
      var seed = 100;
      for (var k = 0; k < 90; k++) {
        var a = nodes[Math.floor(rnd(k * 2.1) * N)], b = nodes[Math.floor(rnd(k * 4.7) * N)];
        if (a !== b) addFiber(a, b, 0.3 + rnd(k) * 0.6, C_FIBER, 'ev', seed++);
      }
      buildFiberMesh(); grow = 0; growStart = tAcc; dirty = true;
      flyTo(new T.Vector3(0, 30, 1200), new T.Vector3(0, 0, 0), 2.5);
    }

    // ---------------------------------------------------------- focus mode
    function focus(name) {
      if (!graph) return;
      if (!name) { toAtlas(); return; }
      var cn = nodeByKey['c:' + name]; if (!cn) return;
      releaseGemPresentation();
      if (!gemStageOn && previewCamera) restoreCameraView(previewCamera.view);
      previewCamera = null;
      var prevFocus = focusName;
      var prevNode = prevFocus ? nodeByKey['c:' + prevFocus] : null;
      var isJump = (mode === 'focus' && prevFocus && prevFocus !== name);
      mode = 'focus'; focusName = name;
      var c = cn.data;
      var myEvents = (graph.events || []).filter(function (e) { return (e.characters || []).indexOf(name) >= 0; });
      var myRels = (graph.relations || []).filter(function (r) { return r.a === name || r.b === name; })
        .sort(function (x, y) { return (y.strength || 0) - (x.strength || 0); });
      focusHeat = clamp(myRels.reduce(function (sum, r) { return sum + (+r.strength || 0); }, 0) / Math.max(1, myRels.length * 0.72), 0, 1);
      focusMeta = computeMeta(c);
      focusGem = buildGemModel(c, gemPeer);
      var partners = {}; myRels.forEach(function (r) { partners[r.a === name ? r.b : r.a] = r; });
      var myChapters = {}; nodes.forEach(function (n) { if (n.kind === 'chap' && n.data.members.some(function (m) { return myEvents.some(function (e) { return (e.chapter || '未分章') === m; }); })) myChapters[n.data.chapter] = true; });
      // 目标位：中心 = 角色星体（悬于晶冠之上）；左 = 其章节沿弧线；右 = 关系角色（>16 人自动 2–3 列错层）；
      // 八维节点吸附到 3D 晶冠顶点（由 updateCrown 每帧写 to）
      var plist = Object.keys(partners), pidx = {}, pm = plist.length;
      plist.forEach(function (k, i) { pidx[k] = i; });
      // v25 · 关系场：不再排方阵（等距的行 × 列没有主次，只有整齐）。改为按关系强弱分三层壳，
      // 从主角向外张开：核心壳贴近主角、更大、更靠近相机；外壳更远更小更暗。壳内再做两件事：
      //   ① 中心向外派位 —— 最强的那个落在视线高度，越弱越往上下两端散（重要度 = 离光心的距离）；
      //   ② 分节呼吸的行距 + 低频摆动的边缘 —— 右侧于是读成一片有厚度的关系场，而不是一张表。
      var SHELL = [
        // span 是世界单位的纵向铺展：聚焦机位下超过 ~560 就会被上下裁出画面，标签跟着读不到
        { top: 8, x: FOCUS_X - 116, span: 296, z: 104, sz: 1.00, al: 1.00, mea: 3, ax: 30, az: 44 },
        { top: 24, x: FOCUS_X + 22, span: 424, z: -54, sz: 0.82, al: 0.92, mea: 4, ax: 40, az: 66 },
        { top: 1e9, x: FOCUS_X + 132, span: 540, z: -226, sz: 0.62, al: 0.74, mea: 5, ax: 52, az: 86 }
      ];
      var pShell = [], pSlot = [], shellN = [0, 0, 0];
      plist.forEach(function (k, i) { var s = i < SHELL[0].top ? 0 : i < SHELL[1].top ? 1 : 2; pShell[i] = s; pSlot[i] = shellN[s]++; });
      var shellLane = SHELL.map(function (sh, si) { return laneLayout(shellN[si], Math.min(sh.span, Math.max(150, shellN[si] * 40)), sh.mea); });
      var shellOrder = SHELL.map(function (sh, si) { return centerOutOrder(shellN[si]); });
      var clist = Object.keys(myChapters), cidx = {}, cm = clist.length, cspan = clamp(cm * 20, 520, 640);
      clist.forEach(function (k, i) { cidx[k] = i; });
      var chapLaneF = laneLayout(cm, cspan, cm >= 14 ? 4 : 3);
      nodes.forEach(function (n) {
        n.from.copy(n.pos); n.alphaTo = 0.08; n.delay = 0.18; n.fseq = -1; n.el.classList.remove('lift', 'dim');
        if (n.shell != null) { n.shell = null; n.el.classList.remove('sh0', 'sh1', 'sh2'); n._box = null; }   // 上一次聚焦的壳位必须清掉，否则旧壳会混进这次的关系脊
        if (n === cn) { n.render = true; n.g.visible = true; attachLabel(n); n.to.set(0, 0, 60); n.alphaTo = 1; n.sizeTo = 44; n.delay = 0; n.el.classList.add('lift'); return; }
        if (n.kind === 'char') {
          var r = partners[n.key.slice(2)];
          if (r) {
            n.render = true; n.g.visible = true; attachLabel(n);
            var i = pidx[n.key.slice(2)], si = pShell[i], sh = SHELL[si], slot = shellOrder[si][pSlot[i]];
            var swp = laneSway(shellN[si] <= 1 ? 0 : slot / (shellN[si] - 1), sh.ax, sh.az);
            n.to.set(sh.x + swp.x + laneIndent(slot, sh.mea, 20), shellLane[si][slot] || 0, sh.z + swp.z);
            n.alphaTo = sh.al; n.sizeTo = (10 + (r.strength || 0.5) * 14) * sh.sz;   // v22：关系列星体收敛，光晕不再互相吞没
            n.shell = si; n.fseq = i;   // 顺序节拍：关系按强弱名次逐秒往下走
            // 版面层级：近壳大字给全三行，中壳给两行，远壳只留名字 —— 信息量随距离递减，眼睛自己就分出了主次
            n.el.classList.remove('sh0', 'sh1', 'sh2'); n.el.classList.add('sh' + si); n._box = null;
            n.delay = 0.035 + Math.min(0.176, si * 0.059 + pSlot[i] * 0.008); n.el.classList.add('lift');
          } else { n.to.copy(n.pos); n.alphaTo = 0.06; if (!big) n.el.classList.add('dim'); }   // 无关节点原地淡出（v31）：from==to → 整个过渡不动，其纤维免重算
        } else if (n.kind === 'chap') {
          if (myChapters[n.data.chapter]) {
            var j = cidx[n.data.chapter];
            var yy = chapLaneF[j] || 0;
            var ang = (yy / 330) * 0.9, swc = laneSway(cm <= 1 ? 0 : j / (cm - 1), 36, 64);
            // 左列 = 时间脊：弧线（原有）+ 分节呼吸的行距 + 低频摆动的左缘 + 反相纵深
            n.to.set(-FOCUS_X - 6 + (1 - Math.cos(ang)) * 48 - Math.abs(swc.x) - laneIndent(j, cm >= 14 ? 4 : 3, 18), yy, Math.sin(ang * 1.4) * 40 + swc.z);
            n.alphaTo = 1; n.fseq = j;   // 顺序节拍：章节按章序逐秒往下走
            n.delay = 0.059 + Math.min(0.176, j * 0.013); n.el.classList.add('lift');
          } else { n.to.copy(n.pos); n.alphaTo = 0.05; if (!big) n.el.classList.add('dim'); }
        } else if (n.kind === 'hub' || n.kind === 'camp') {
          n.to.copy(n.pos); n.alphaTo = 0.05; if (!big) n.el.classList.add('dim');
        } else if (n.kind === 'attr') {
          // 八维节点只在聚焦态存在：从角色星体涌出，吸附到晶冠顶点（updateCrown 每帧写 to）
          var ai = ATTR_KEYS.indexOf(n.data.attr), ad = focusGem && focusGem.attr[ai];
          var ascore = ad ? ad.score : attrScore(c, n.data.attr), sc = ascore === null ? null : ascore / 100;
          n.render = true; n.g.visible = true; attachLabel(n);
          n.from.set(0, 0, 60); n.pos.copy(n.from);
          n.alphaTo = sc === null ? 0.60 : 0.95; n.sizeTo = sc === null ? 5 : 7 + sc * 11; n.delay = 0.094 + ai * 0.016;
          n.el.setAttribute('data-known', sc !== null ? 'true' : 'false');
          n.el.children[1].textContent = ATTR_EN[ai] + ' ' + (sc === null ? '— 待建档' : Math.round(ascore));
          n.el.children[2].textContent = ad && ad.rank != null ? '#' + ad.rank + ' / ' + ad.n : '';
          n._box = null;
          n.el.classList.add('lift');
        } else if (n.kind === 'meta') {
          var mi = META_KEYS.indexOf(n.data.meta), md = focusGem && focusGem.meta && focusGem.meta[mi];
          var mscore = md ? md.score : focusMeta.score[n.data.meta], mv = mscore == null ? null : mscore / 100;
          n.render = true; n.g.visible = true; attachLabel(n);
          n.from.set(0, 0, 60); n.pos.copy(n.from);
          n.alphaTo = 0.30; n.sizeTo = mv === null ? 5 : 6 + mv * 10; n.delay = 0.21 + mi * 0.018;   // 顶面只作微光锚点，翻到底面才 1.0
          n.el.setAttribute('data-known', mv !== null ? 'true' : 'false');
          n.sub = META_EN[mi] + ' ' + (mscore == null ? '— 待建档' : Math.round(mscore)); n.el.children[1].textContent = n.sub;
          n.el.children[2].textContent = focusMeta.sub[n.data.meta] || ''; n._box = null;
          n.el.classList.add('lift');
        }
      });
      // 纤维高亮：涉及该角色的 1，其余 -1；该角色的属性纤维交给晶冠的"弦"绘制（-2 = 隐藏），随自旋实时跟随
      setFiberHl(function (f) { if (f.kind === 'guide') return -2; if (f.kind === 'attr' && (f.a === cn || f.b === cn)) return -2; return (f.a === cn || f.b === cn) ? 1 : -1; });
      buildCrown(cn, c);
      if (core.setBurst) core.setBurst(1);
      if (core.spawnIris) core.spawnIris(cn);
      if (core.sendSignal) core.sendSignal(cn);
      if (typeof spawnDiffusionJump === 'function') spawnDiffusionJump(prevNode ? prevNode.pos : null, cn.to, partners[prevFocus] || partners[name]);
      // v25 · 信息脊：左列章节串成时间脊，右侧三层关系壳各串一条 —— 都是会波动的丝带（见 buildSpines）
      // v31 · 延后一帧建：点击那一帧不再同时付「建晶冠 + 建信息脊」两笔同步几何开销；
      // 回调里核对 mode / focusName，连点两次时不会把脊建到错的角色上。
      // v31.1 · 延后必须挂在**场景自己的下一帧**上，不能用 requestAnimationFrame：
      // 本工程的验收全走 `probe=1&pump=1` + `S.step(n)`，那是在**一个 JS 任务里同步泵 n 帧**，
      // 单线程下 rAF 回调整段跑不进来；无头页面不可见时 rAF 又被节流到 ~1 帧/秒。
      // 于是脊在所有 pump 验收里永远建不出来（截图左列的时间脊整条消失，而 S.spines() 还在报
      // 上一次的旧几何 visible:true —— 探针说在、画面没有，这种探针比没有更糟）。
      // 真实浏览器里也一样：后台标签页的 rAF 被暂停，脊会拖到用户切回来才出现。
      // 改挂 pendingBuild，由 frame() 在下一帧开头消费：pump 与真 rAF 两条路径行为完全一致。
      var spineName = name;
      pendingBuild = function () {
        if (mode !== 'focus' || focusName !== spineName) return;
        var chains = [];
        var chapsN = nodes.filter(function (n) { return n.kind === 'chap' && myChapters[n.data.chapter]; }).sort(function (a, b) { return b.to.y - a.to.y; });
        if (chapsN.length >= 2) chains.push({ pts: chapsN.map(function (n) { return n.to.clone(); }), col: 0xb9a6ff, head: 1, amp: 1.25, wide: 1.15 });
        [0, 1, 2].forEach(function (si) {
          var mem = nodes.filter(function (n) { return n.kind === 'char' && n.shell === si; }).sort(function (a, b) { return b.to.y - a.to.y; });
          if (mem.length >= 2) chains.push({ pts: mem.map(function (n) { return n.to.clone(); }), col: si === 0 ? 0xffcf8a : si === 1 ? 0xffab7a : 0xd7a8ff, head: 0, amp: 1 - si * 0.16, wide: 1 - si * 0.2 });
        });
        buildSpines(chains);
      };
      // v31 · dirty 不再置位：激活集合变化已由 setFiberHl 的逐纤维 recalc 覆盖；
      // 这里若再强制一次全量，聚焦过渡的第一帧就会白白上传全部 20 万顶点。
      animStart = tAcc; animDur = 0.85; lodDirty = true;
      groupXTo = -130;
      // 镜头语言 · 聚焦：抬高到 3/4 机位揭示晶冠的厚度，之后进入缓慢轨道漂移
      // 底面晶锥向下延伸很深：取景重心下移并略拉远，顶冠与底锥同时入画；每次聚焦都从顶面开始
      face = 'top';
      flyTo(FOCUS_CAM.clone(), FOCUS_TGT.clone(), 1.05);
      fire('focus', name);
      if (isJump) fire('jump', { from: prevFocus, to: name, rel: partners[prevFocus] || partners[name] });
      syncGemDimensionLabels();
      if (gemStageOn) { groupXTo = 0; group.position.x = 0; maskGemPresentation(); }
    }
    function toAtlas() {
      releaseGemPresentation();
      if (gemStageSaved) restoreCameraView(gemStageSaved.view);
      else if (previewCamera) restoreCameraView(previewCamera.view);
      previewCamera = null;
      gemStageOn = false; gemStageSaved = null; gemStageArea = null; gemPeer = null; gemChapter = null;
      disposeChapRail();
      var host = focusName ? nodeByKey['c:' + focusName] : null;
      mode = 'atlas'; focusName = null; chapSel = null; focusHeat = 0; crownHl2 = -1; face = 'top'; dialHover = null;
      var order = nodes.slice().sort(function (a, b) { return (b.kind === 'char' ? (b.data.importance || 0) : -1) - (a.kind === 'char' ? (a.data.importance || 0) : -1); });
      order.forEach(function (n, i) {
        var backName = n.key.slice(2);
        n.render = !(nCharCount > 1600 && n.kind === 'char' && n.tier >= 4 && !tailShow && !pinned[backName] && backName !== hoverName && backName !== focusName && !(searchSet && searchSet[backName])); n.g.visible = n.render;
        if (!n.render && n.kind === 'char' && !pinned[n.key.slice(2)] && n.key.slice(2) !== hoverName && n.key.slice(2) !== focusName && !(searchSet && searchSet[n.key.slice(2)])) detachLabel(n);
        n.from.copy(n.pos); n.to.copy(n.atlas); n.alphaTo = (n.baseAlpha === undefined ? 1 : n.baseAlpha);
        n.fseq = -1;   // 回全景：顺序节拍改读固有次序（座序 / 章序）
        if (n.shell != null) { n.shell = null; n.el.classList.remove('sh0', 'sh1', 'sh2'); n._box = null; }
        if (n.kind === 'meta' || n.kind === 'attr') { if (host) n.to.copy(host.atlas); n.alphaTo = 0; }
        if (n.kind === 'char') n.alphaTo = stage.charAtlasAlpha ? stage.charAtlasAlpha(n) : (n.baseAlpha === undefined ? 1 : n.baseAlpha);
        n.delay = Math.min(0.34, i * 0.006);
        n.el.classList.remove('lift', 'dim');
        if (n.sizeAtlas != null) n.sizeTo = n.sizeAtlas;
        else if (n.kind === 'char') n.sizeTo = 14 + clamp((n.data.importance || 30) / 100, 0.1, 1) * 30;
        else if (n.kind === 'chap') n.sizeTo = 7 + Math.min(n.data.count, 8) * 1.1;
        else n.sizeTo = 11;
      });
      setFiberHl(campSel ? campFiberFn(campSel) : function () { return 0; });
      if (core.getFiberMat && core.getFiberMat()) core.getFiberMat().uniforms.uSigOn.value = 0;
      if (crown && !crown.dying) crown.dying = tAcc;
      crownHl = -1; crownHold = 0; syncGemLegend();
      animStart = tAcc; animDur = 1.25; dirty = true; lodDirty = true;
      groupXTo = atlasShift();
      buildAtlasSpines();
      // 镜头语言 · 返回：拉远回落到正视全景
      flyTo(new T.Vector3(0, 30, atlasDist()), new T.Vector3(0, 0, 0), 1.8);
      fire('focus', null);
    }
    var animStart = -10;
    // ---------------------------------------------------------- 3D 属性晶冠（聚焦态）
    // 八维分值同时编码为顶点半径与高度：顶面晶面 + 外壁 + 底面组成封闭宝石体；
    // 台座网格 / 支柱 / 轨道环 / 扫描盘 / 上升微粒分层入场；八维节点每帧吸附到顶点，标签随之。
    var CR_R0 = 30, CR_R1 = 58, CR_H = 42, CR_TILT = 0.52, CR_DROP = 60, CR_SPIN = 0.085;
    // 底面晶锥：半径略小于顶冠，深度 CR_H2 远大于顶面高度（约 4×），轴向与顶面错开 22.5°，标签在圆周上交错
    // 底层比顶面更宽并隔开一段"颈部"（CR_GAP）：底面顶点与标签落在顶面标签环之外、之下，两面信息不再交叠
    var CR_R2_0 = 94, CR_R2_1 = 46, CR_H2 = 150, CR_GAP = 34, GEM_NECK = 0.52;
    // v24.4 · 对置双谱的相对运动：上冠与下锥不再是一整块，各自挂在 upper / lower 两个子组上，
    // 沿 y 反相起伏（颈距在 ~30 与 ~88 之间呼吸）、绕 y 反向自转（陀螺仪读法），颈部由张力桥连住。
    // CR_LIFT = 上冠常态悬空高度（亭部尖端才有下探空间）；AMP = 各自的半振幅；PER = 一个呼吸周期（s）
    var CR_LIFT = 40, CR_UP_AMP = 13, CR_LO_AMP = 13, CR_SEP_PER = 7.4, CR_COUNTER = 1.35;
    var FOCUS_CAM = new T.Vector3(150, 96, 900), FOCUS_TGT = new T.Vector3(0, -66, 45);
    var crown = null, crownHl = -1, crownHold = 0, crownRing = null;
    function crownAxisAngle(i) { return Math.PI + Math.PI / 8 + i * Math.PI / 4; }
    // v24.4 · 晶体着色：顶点携带重心坐标 aBary（棱线刃光用 fwidth 求出，与三角形大小无关）与
    // 局部坐标 vL（火彩锚在晶体身上而不是屏幕像素上，旧版一转动就露出纱窗状的固定网格）
    /* warm = true：只造不挂（着色器预热用，见 S.prewarmCrown），返回这座晶冠，不动当前晶冠 / 图例 / 八维节点 */
    /* 把入场线框相写进晶冠的各层晶体材质（只写有这枚 uniform 的，别的层没有就跳过） */
    function crownWire(cr, v) {
      var ms = [cr.gem, cr.gemBase, cr.core, cr.gem2, cr.gem2Base], i, u;
      for (i = 0; i < ms.length; i++) {
        u = ms[i] && ms[i].material && ms[i].material.uniforms;
        if (u && u.uWire) u.uWire.value = v;
      }
    }

    function buildCrown(cn, c, warm) {
      var model = warm ? buildGemModel(c, null) : (focusGem || buildGemModel(c, gemPeer));
      var meta = warm ? computeMeta(c) : (focusMeta || computeMeta(c)), sig = crownSig(cn, c, model, meta);
      if (!warm && crownReuse(cn, model, sig)) return crown;
      if (!warm) crownDispose(true);
      var grp = new T.Group(), spin = new T.Group(), fx = new T.Group();
      // upper / lower：两谱各自的运动框架（反相升降 + 反向自转），表盘与台座仍留在 spin / fx 上不动
      var upper = new T.Group(), lower = new T.Group();
      spin.add(upper); spin.add(lower);
      upper.position.y = CR_LIFT;
      grp.add(spin); grp.add(fx); grp.rotation.x = CR_TILT;
      grp.position.copy(cn.to).add(new T.Vector3(0, -CR_DROP, 0));
      var sc = [], verts = [], floor = [], i, j, scored = 0, scoreSum = 0;
      for (i = 0; i < 8; i++) {
        var d = model && model.attr[i], s = d ? d.score : attrScore(c, ATTR_KEYS[i]);
        var v = s == null ? null : clamp(s / 100, 0, 1); sc.push(v);
        if (v !== null) { scored++; scoreSum += v; }
        /* An unknown axis is an open mark on the reference perimeter, never
           a low-scoring filled facet. Real zero retains its exact geometry. */
        var th = crownAxisAngle(i), r = v === null ? CR_R0 + CR_R1 + 8 : CR_R0 + CR_R1 * v, h = v === null ? CR_H * 0.48 : CR_H * v;
        verts.push(new T.Vector3(Math.sin(th) * r, h, Math.cos(th) * r));
        floor.push(new T.Vector3(Math.sin(th) * r, 0, Math.cos(th) * r));
      }
      var avg = scored ? scoreSum / scored : 0, hMax = 0;
      for (i = 0; i < 8; i++) if (sc[i] !== null) hMax = Math.max(hMax, CR_H * sc[i]);
      /* v90 F3 · 台面必须是冠部最高处：旧台面（avg × 0.55H）低于高分顶点，冠顶是一口下凹的碗，
         配上直上直下的外壁就读成盒子。台面改为比最高已知顶点再高一截，冠部星面 / 风筝面由此向外下倾。
         顶点（半径 + 高度 = 分值）与台面比例都只由已知分值决定；没有已知轴时台面贴底。 */
      var apex = new T.Vector3(0, scored ? hMax + 10 + 10 * avg : 4, 0);
      // v24.4 · 明亮式切工（brilliant cut）：台面 → 星面 / 风筝面 → 腰棱 → 亭部两段 → 底尖。
      // 腰棱（girdle）那道横向棱线是「切割宝石」最强的识别线索，旧版的垂直外壁读起来只是一块玻璃柱。
      // aBary 分量 k 恰好在「与顶点 k 相对」的那条边上为 0 —— 于是 hide 位把该分量整体 +1，
      // 就能永久抹掉那条边。四边形晶面必须这样抹掉自己的对角线，否则棱刃会把整块宝石画成线框球。
      var P = [], AH = [], AF = [], AA = [], AB = [], AFC = [], nTri = 0;
      function tri(a, b, d, face, axis, hide) {
        hide = hide || 0;
        var q = [a, b, d], fv = rnd(nTri++ * 1.73 + 0.31);
        for (var w = 0; w < 3; w++) {
          P.push(q[w].x, q[w].y, q[w].z); AH.push(q[w].y / CR_H); AF.push(face); AA.push(axis); AFC.push(fv);
          AB.push((w === 0 ? 1 : 0) + (hide & 1 ? 1 : 0), (w === 1 ? 1 : 0) + (hide & 2 ? 1 : 0), (w === 2 ? 1 : 0) + (hide & 4 ? 1 : 0));
        }
      }
      // 四边形晶面 = 两个三角 + 抹掉共用对角线（a–c）
      function quad(a, b, d, e, face, axis) { tri(a, b, d, face, axis, 2); tri(a, d, e, face, axis, 4); }
      // 三道新增环：台面环（冠部内圈）· 腰棱（外凸 5.5%）· 亭部中环（底面不再是一张平盘）
      var tbl = [], gir = [], pav = [];
      for (i = 0; i < 8; i++) {
        var thg = crownAxisAngle(i), rg = CR_R0 + CR_R1 * sc[i], hg = CR_H * Math.max(0.04, sc[i]);
        tbl.push(new T.Vector3(Math.sin(thg) * rg * 0.42, apex.y - (apex.y - hg) * 0.25, Math.cos(thg) * rg * 0.42));
        gir.push(new T.Vector3(Math.sin(thg) * rg * 1.055, hg * 0.64, Math.cos(thg) * rg * 1.055));
        pav.push(new T.Vector3(Math.sin(thg) * rg * 0.46, -CR_H * 0.13 * (0.45 + 0.55 * sc[i]), Math.cos(thg) * rg * 0.46));
      }
      var pavTip = new T.Vector3(0, -CR_H * 0.22, 0);
      for (i = 0; i < 8; i++) {
        j = (i + 1) % 8;
        if (sc[i] === null || sc[j] === null) continue;
        tri(apex, tbl[i], tbl[j], 0, i);                                 // 台面星面
        quad(tbl[i], verts[i], verts[j], tbl[j], 0, i);                   // 风筝面
        quad(verts[i], gir[i], gir[j], verts[j], 3, i);                   // 腰棱斜切带（aFace 3 = 磨砂）
        quad(gir[i], floor[i], floor[j], gir[j], 1, i);                   // 亭部上段
        quad(floor[i], pav[i], pav[j], floor[j], 2, i);                   // 亭部下段
        tri(pav[i], pavTip, pav[j], 2, i);                                // 底尖
      }
      // v90 F3 · 竖刃：楔面只在「相邻两轴都已知」时存在，连续缺档时孤立 / 边缘的已知轴会一面不剩。
      // 凡已知轴有一侧邻轴未知，就沿该轴补一片径向剖面（台面顶 → 冠 → 腰棱 → 亭部 → 底尖），
      // 每个点都取自该轴自己的分值，材质与楔面同一套（aAxis = i）；未知轴依旧不产生任何填充面。
      for (i = 0; i < 8; i++) crownBlade(sc, i, [apex, tbl[i], verts[i], gir[i], floor[i], pav[i], pavTip], [0, 0, 3, 1, 2, 2], tri);
      var gg = new T.BufferGeometry();
      gg.setAttribute('position', new T.Float32BufferAttribute(P, 3));
      gg.setAttribute('aH', new T.Float32BufferAttribute(AH, 1));
      gg.setAttribute('aFace', new T.Float32BufferAttribute(AF, 1));
      gg.setAttribute('aAxis', new T.Float32BufferAttribute(AA, 1));
      gg.setAttribute('aBary', new T.Float32BufferAttribute(AB, 3));
      gg.setAttribute('aFacet', new T.Float32BufferAttribute(AFC, 1));
      gg.computeVertexNormals();
      var gem = new T.Mesh(gg, gemMat(CROWN_FS, gemSpec('berylFire')));
      gem.frustumCulled = false; gem.renderOrder = 2; upper.add(gem);
      // 暗玻璃基底（正常混合，先画）+ 内核宝石（缩小 0.52、更暖更亮、色散更猛）+ 台座焦散
      var gemBase = new T.Mesh(gg, gemMat(CROWN_BASE_FS, gemSpec('beryl', { blend: T.NormalBlending,
        cen: new T.Vector3(0, (apex.y - CR_H * 0.22) * 0.5, 0), rad: new T.Vector3(CR_R0 + CR_R1 + 4, (apex.y + CR_H * 0.22) * 0.5 + 6, CR_R0 + CR_R1 + 4), thk: 1 / (2 * (CR_R0 + CR_R1 + 4)) })));
      gemBase.frustumCulled = false; gemBase.renderOrder = 1; upper.add(gemBase);
      var core = new T.Mesh(gg, gemMat(CROWN_FS, gemSpec('coreFire')));
      core.scale.set(0.52, 0.62, 0.52); core.position.y = CR_H * 0.12; core.frustumCulled = false; core.renderOrder = 3; upper.add(core);
      // 色散重影 ×2：外扩一片偏暖红、内收一片偏冷青，轮廓因此裂成棱镜边
      var ghostA = new T.Mesh(gg, ghostMat(0xff4a2a, 7.5)), ghostB = new T.Mesh(gg, ghostMat(0x2ad8ff, 7.5));
      ghostA.scale.setScalar(1.014); ghostB.scale.setScalar(0.986);
      ghostA.frustumCulled = ghostB.frustumCulled = false; ghostA.renderOrder = ghostB.renderOrder = 4;
      upper.add(ghostA); upper.add(ghostB);
      var caustG = new T.CircleGeometry(CR_R0 + CR_R1 + 6, 96); caustG.rotateX(-Math.PI / 2);
      var caust = new T.Mesh(caustG, new T.ShaderMaterial({ vertexShader: RING_VS, fragmentShader: CAUST_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uR: { value: CR_R0 + CR_R1 + 6 }, uCa: { value: tone('mint').clone() }, uCb: { value: tone('gold').clone() }, uAxes: { value: sc.map(function (v) { return v === null ? 0 : v; }) } } }));
      caust.position.y = -0.6; caust.frustumCulled = false; fx.add(caust);
      // 支柱（k=0，六段，脉冲上行）· 顶缘（k=1）· 底缘（k=2）
      var LP = [], LT = [], LK = [], LA = [];
      function seg(a, b, ta, tb, k, ax) { LP.push(a.x, a.y, a.z, b.x, b.y, b.z); LT.push(ta, tb); LK.push(k, k); LA.push(ax, ax); }
      for (i = 0; i < 8; i++) {
        j = (i + 1) % 8;
        if (sc[i] === null) continue;
        for (var q = 0; q < 6; q++) seg(floor[i].clone().lerp(verts[i], q / 6), floor[i].clone().lerp(verts[i], (q + 1) / 6), q / 6, (q + 1) / 6, 0, i);
        if (sc[j] !== null) {
          seg(verts[i], verts[j], 1, 1, 1, i);
          seg(gir[i], gir[j], 1, 1, 1, i);        // v24.4 · 腰棱环：切工的横向棱线，与顶缘同亮
          seg(floor[i], floor[j], 0, 0, 2, i);
        }
        // k=4 信标：顶点向上的数据光柱，高度随分值
        var bt = verts[i].clone(); bt.y += 10 + 30 * sc[i];
        for (var bq = 0; bq < 6; bq++) seg(verts[i].clone().lerp(bt, bq / 6), verts[i].clone().lerp(bt, (bq + 1) / 6), bq / 6, (bq + 1) / 6, 4, i);
      }
      var lg = new T.BufferGeometry();
      lg.setAttribute('position', new T.Float32BufferAttribute(LP, 3));
      lg.setAttribute('t', new T.Float32BufferAttribute(LT, 1));
      lg.setAttribute('k', new T.Float32BufferAttribute(LK, 1));
      lg.setAttribute('ax', new T.Float32BufferAttribute(LA, 1));
      var lines = new T.LineSegments(lg, new T.ShaderMaterial({ vertexShader: CRL_VS, fragmentShader: CRL_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uGrow: { value: 0 }, uHl: { value: -1 }, uLamp: { value: 0 }, uLampK: { value: 1 }, uLine: { value: lineComp() }, uCol: { value: new T.Color(0x7af0c8) }, uHot: { value: new T.Color(0xfff6e8) } } }));
      lines.frustumCulled = false; upper.add(lines);
      // 弦：角色星体 → 八个顶点（k=3，八段，脉冲自星体流向顶点），每帧在 upper 局部坐标重算
      var SSUB = 8, SP = new Float32Array(8 * SSUB * 2 * 3), ST = [], SK = [], SA = [];
      for (i = 0; i < 8; i++) for (var sq = 0; sq < SSUB; sq++) { ST.push(sq / SSUB, (sq + 1) / SSUB); SK.push(3, 3); SA.push(i, i); }
      var sg = new T.BufferGeometry();
      sg.setAttribute('position', new T.BufferAttribute(SP, 3));
      sg.setAttribute('t', new T.Float32BufferAttribute(ST, 1));
      sg.setAttribute('k', new T.Float32BufferAttribute(SK, 1));
      sg.setAttribute('ax', new T.Float32BufferAttribute(SA, 1));
      var strings = new T.LineSegments(sg, new T.ShaderMaterial({ vertexShader: CRL_VS, fragmentShader: CRL_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uGrow: { value: 1 }, uHl: { value: -1 }, uLamp: { value: 0 }, uLampK: { value: 1 }, uLine: { value: lineComp() }, uCol: { value: new T.Color(0x9af5d2) }, uHot: { value: new T.Color(0xffe2b0) } } }));
      strings.frustumCulled = false; upper.add(strings);
      // v24.4 · 张力桥（k=5）：上冠底缘 ↔ 下锥腰环之间的八股光丝，每帧在 spin 局部重算。
      // 两谱反相升降时颈距在 ~30 与 ~88 之间伸缩，光丝被拉长即变细变亮 —— 相对运动因此读成「张力」而不是「各自乱飘」。
      var BSUB = 6, BP = new Float32Array(8 * BSUB * 2 * 3), BT = [], BK = [], BA = [];
      for (i = 0; i < 8; i++) for (var bs = 0; bs < BSUB; bs++) { BT.push(bs / BSUB, (bs + 1) / BSUB); BK.push(5, 5); BA.push(i, i); }
      var bgm = new T.BufferGeometry();
      bgm.setAttribute('position', new T.BufferAttribute(BP, 3));
      bgm.setAttribute('t', new T.Float32BufferAttribute(BT, 1));
      bgm.setAttribute('k', new T.Float32BufferAttribute(BK, 1));
      bgm.setAttribute('ax', new T.Float32BufferAttribute(BA, 1));
      var bridge = new T.LineSegments(bgm, new T.ShaderMaterial({ vertexShader: CRL_VS, fragmentShader: CRL_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uGrow: { value: 1 }, uHl: { value: -1 }, uTension: { value: 0 }, uLine: { value: lineComp() }, uCol: { value: new T.Color(0xbb9cff) }, uHot: { value: new T.Color(0xfff6e8) } } }));
      bridge.frustumCulled = false; spin.add(bridge);
      // ======== 表盘 · 底层（钟表式）：径向刻线随晶冠自旋；层级环 / 章节表圈 / 表圈刻度 / 走针都是有像素质感的丝带，不再是 1px 线 ========
      var Rd = CR_R0 + CR_R1;
      var GP = [];
      for (i = 0; i < 8; i++) { var ta = crownAxisAngle(i); GP.push(Math.sin(ta) * CR_R0, 0, Math.cos(ta) * CR_R0, Math.sin(ta) * Rd, 0, Math.cos(ta) * Rd); }
      var grid = new T.LineSegments(new T.BufferGeometry().setAttribute('position', new T.Float32BufferAttribute(GP, 3)),
        new T.LineBasicMaterial({ color: 0x8a78c8, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false }));
      grid.frustumCulled = false; spin.add(grid);
      // 层级环 ×5：细丝带 + 微点阵，越外越亮
      var levels = [];
      for (var g = 0; g <= 4; g++) { var lr = CR_R0 + CR_R1 * g / 4, lv = ribbon(lr - 0.45, lr + 0.45, 192, { mode: 2, base: g === 4 ? 0.9 : 0.5, ticks: 96 + g * 32, ca: 0x7a68b8, cb: 0xc9b8ff }); lv.position.y = 0.25; fx.add(lv); levels.push(lv); }
      // 章节表圈：全书章节按角度分段（12 点为第一章，顺时针），角色出场的章亮为琥珀，当前章脉动；时针指向它
      var chapList = (bookStats && bookStats.chapters) || [], CLH = Math.max(1, chapList.length), SEGN = Math.min(CLH, 96);
      var segData = new Uint8Array(SEGN * 4), mine = {}, lastIdx = -1;
      (graph && graph.events || []).forEach(function (e) { if ((e.characters || []).indexOf(cn.key.slice(2)) >= 0) mine[e.chapter || '未分章'] = 1; });
      var mineIdx = [];
      for (i = 0; i < CLH; i++) { var si = Math.floor(i / CLH * SEGN); if (mine[chapList[i]]) { segData[si * 4] = 255; lastIdx = i; mineIdx.push(i); } segData[si * 4 + 3] = 255; }
      var segTex = new T.DataTexture(segData, SEGN, 1, T.RGBAFormat); segTex.magFilter = segTex.minFilter = T.NearestFilter; segTex.needsUpdate = true;
      var dial = ribbon(Rd + 6, Rd + 13, 256, { mode: 1, segs: SEGN, segTex: segTex, ca: 0x4a3690, cb: 0x8a6cd8, hot: 0xffb45c }); dial.position.y = 0.35; fx.add(dial);
      // 表圈：360 细刻 + 60 分刻 + 8 轴向主标（随自旋，与晶面轴对齐）+ 秒针落格脉冲；外沿一圈亮线
      var bezel = ribbon(Rd + 16, Rd + 28, 320, { mode: 0, base: 0.22, ticks: 360, major: 60, axes: 8, axisOff: crownAxisAngle(0), ca: 0x6a58b0, cb: 0xc9b8ff, hot: 0xfff1da }); bezel.position.y = 0.3; spin.add(bezel);
      var rimOut = ribbon(Rd + 28.6, Rd + 30.2, 256, { mode: 2, base: 1.1, ticks: 0, ca: 0xc9b8ff, cb: 0xfff1da }); rimOut.position.y = 0.3; fx.add(rimOut);
      var disc = new T.Mesh(new T.CircleGeometry(Rd + 12, 64), new T.MeshBasicMaterial({ map: texDais, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide }));
      disc.rotation.x = -Math.PI / 2; disc.position.y = -0.8; fx.add(disc);
      // 走针：秒针跳格（机械擒纵式，带轻微回弹）· 分针匀速 · 时针指向章节表圈上的当前章
      var hands = new T.Group(); hands.position.y = 0.6; fx.add(hands);
      var secHand = hand(Rd + 11, 16, 1.4, 0.35, 0x9af5d2, 0xfff6e8), minHand = hand(Rd - 2, 12, 2.2, 0.7, 0xc9b8ff, 0xffffff), hourHand = hand(Rd * 0.62, 9, 3.2, 1.2, 0xffb45c, 0xfff1da);
      hands.add(secHand); hands.add(minHand); hands.add(hourHand);
      // 剧情针（v17.14）：骑在章节表圈上的短琥珀标，指向「当前章」；三根时间针让给本机时钟
      var storyHand = hand(Rd + 15.5, -(Rd + 3.5), 2.6, 1.0, 0xffb45c, 0xfff1da); hands.add(storyHand);
      // 表盘读数：本机时间 / 日期 / 当前章，HTML 贴在标签层，锚在表盘 6 点方向外侧
      var clockEl = null;   // v22：表盘数字读数取消（用户：时间显示没必要）；三针保留为机芯
      var tipDot = new T.Sprite(new T.SpriteMaterial({ map: texNode, transparent: true, depthWrite: false, blending: T.AdditiveBlending, color: 0xffd9a0, opacity: 0 })); tipDot.scale.set(7, 7, 1); hands.add(tipDot);
      var cap = ribbon(2.2, 4.6, 48, { mode: 2, base: 1.2, ticks: 0, ca: 0xfff1da, cb: 0xffb45c }); cap.position.y = 0.7; fx.add(cap);
      // 秒针余晖：贴在表盘上的短拖尾（取代原雷达扫描扇面）
      var Rs = Rd + 4;
      var swg = new T.CircleGeometry(Rs, 96); swg.rotateX(-Math.PI / 2);
      var sweep = new T.Mesh(swg, new T.ShaderMaterial({ vertexShader: RING_VS, fragmentShader: SWEEP_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uAng: { value: 0 }, uOn: { value: 0 }, uR: { value: Rs }, uDir: { value: -1 }, uCol: { value: new T.Color(0x7af0c8) }, uHot: { value: new T.Color(0xffd9a0) } } }));
      sweep.position.y = 0.5; sweep.frustumCulled = false; fx.add(sweep);
      // 扫描环（薄荷）：在晶冠高度内上下往复，改为带点阵质感的丝带
      var scan = new T.Group(); fx.add(scan);
      var scanRing = ribbon(Rs - 1.0, Rs + 0.2, 192, { mode: 2, base: 0.8, ticks: 240, ca: 0x7af0c8, cb: 0xbfffe8 }); scan.add(scanRing);
      var scanDisc = new T.Mesh(new T.CircleGeometry(Rs, 64), new T.MeshBasicMaterial({ color: 0x7af0c8, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide }));
      scanDisc.rotation.x = -Math.PI / 2; scan.add(scanDisc);
      // 落成冲击波：两道由台座向外扩散的细环（薄荷 → 琥珀）
      var shocks = [];
      for (i = 0; i < 2; i++) {
        var skg = new T.RingGeometry(0.986, 1.0, 128); skg.rotateX(-Math.PI / 2);
        var sk = new T.Mesh(skg, new T.MeshBasicMaterial({ color: i ? 0xffb45c : 0x9af5d2, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide }));
        sk.position.y = 0.3; sk.frustumCulled = false; fx.add(sk); shocks.push(sk);
      }
      // 上升数据微粒
      var MN = 150, mp = new Float32Array(MN * 3), mph = new Float32Array(MN), msz = new Float32Array(MN);
      for (i = 0; i < MN; i++) { var mr = Math.sqrt(rnd(i * 1.7 + 0.3)) * (CR_R0 + CR_R1 * 0.9), ma = rnd(i * 2.9 + 0.7) * Math.PI * 2; mp[i * 3] = Math.sin(ma) * mr; mp[i * 3 + 1] = rnd(i * 4.3) * CR_H * 1.35; mp[i * 3 + 2] = Math.cos(ma) * mr; mph[i] = rnd(i * 6.1); msz[i] = 2.2 + rnd(i * 8.3) * 3.6; }
      var mg = new T.BufferGeometry(); mg.setAttribute('position', new T.BufferAttribute(mp, 3)); mg.setAttribute('ph', new T.BufferAttribute(mph, 1)); mg.setAttribute('sz', new T.BufferAttribute(msz, 1));
      var motes = new T.Points(mg, motesMat(CR_H * 1.35, 1, 0x9effdb, 0xffe09e));
      motes.frustumCulled = false; upper.add(motes);

      // ================= 底面 · 叙事位置层：向下延伸的长晶锥 =================
      // 八项由图谱数据算出（咖位 / 戏份 / 跨度 / 弧光 / 张力 / 暗线 / 光明面 / 暗黑面），
      // 顶点半径 + 下探深度双编码，锥尖深度约为顶冠高度的 4 倍。
      var sc2 = [], verts2 = [], rim2 = [], sum2 = 0, known2 = 0;
      for (i = 0; i < 8; i++) {
        var md = model && model.meta && model.meta[i], ms = md ? md.score : meta.score[META_KEYS[i]];
        var v2 = ms == null ? null : clamp(ms / 100, 0, 1); sc2.push(v2);
        if (v2 !== null) { sum2 += v2; known2++; }
        var th2 = crownAxisAngle(i) + Math.PI / 8, r2 = v2 === null ? CR_R2_0 + CR_R2_1 + 8 : CR_R2_0 + CR_R2_1 * v2;
        var d2 = v2 === null ? CR_GAP + 12 : CR_GAP + 12 + CR_H2 * 0.5 * v2;
        verts2.push(new T.Vector3(Math.sin(th2) * r2, -d2, Math.cos(th2) * r2));
        // v90 F3 · 颈口收窄：顶盖半径 = 该轴半径 × GEM_NECK，外壁由颈口向数据顶点外斜（倒置的冠部），
        // 不再是一圈直上直下的八棱柱侧墙；数据顶点（半径 + 下探深度）不变
        rim2.push(new T.Vector3(Math.sin(th2) * r2 * GEM_NECK, -CR_GAP, Math.cos(th2) * r2 * GEM_NECK));
      }
      var avg2 = known2 ? sum2 / known2 : 0;
      var nadir2 = new T.Vector3(0, -(CR_GAP + CR_H2 + 16 + 30 * avg2), 0), cap2 = new T.Vector3(0, -CR_GAP, 0), HN2 = CR_GAP + CR_H2 + 46;
      var P2 = [], AH2 = [], AF2 = [], AA2 = [], AB2 = [], AFC2 = [], nTri2 = 0;
      function tri2(a, b, d, face, axis, hide) {
        hide = hide || 0;
        var q = [a, b, d], fv2 = rnd(nTri2++ * 2.19 + 0.77);
        for (var w = 0; w < 3; w++) {
          P2.push(q[w].x, q[w].y, q[w].z); AH2.push(-q[w].y / HN2); AF2.push(face); AA2.push(axis); AFC2.push(fv2);
          AB2.push((w === 0 ? 1 : 0) + (hide & 1 ? 1 : 0), (w === 1 ? 1 : 0) + (hide & 2 ? 1 : 0), (w === 2 ? 1 : 0) + (hide & 4 ? 1 : 0));
        }
      }
      function quad2(a, b, d, e, face, axis) { tri2(a, b, d, face, axis, 2); tri2(a, d, e, face, axis, 4); }
      // v24.4 · 长锥也按切工分段：顶盖 → 外壁 → 腰棱斜切 → 亭部三段（半径 0.62 / 0.26 微内凹）→ 锥尖。
      // 亭部内凹让长锥不再是一根平滑的圆锥筒，折射在腰下堆出一层可读的明暗。
      var gir2 = [], pv2 = [], pv3 = [];
      for (i = 0; i < 8; i++) {
        var t2g = crownAxisAngle(i) + Math.PI / 8, r2g = CR_R2_0 + CR_R2_1 * sc2[i], d2g = CR_GAP + 12 + CR_H2 * 0.5 * sc2[i];
        gir2.push(new T.Vector3(Math.sin(t2g) * r2g * 1.05, lerp(-d2g, nadir2.y, 0.10), Math.cos(t2g) * r2g * 1.05));
        pv2.push(new T.Vector3(Math.sin(t2g) * r2g * 0.62, lerp(-d2g, nadir2.y, 0.44), Math.cos(t2g) * r2g * 0.62));
        pv3.push(new T.Vector3(Math.sin(t2g) * r2g * 0.26, lerp(-d2g, nadir2.y, 0.76), Math.cos(t2g) * r2g * 0.26));
      }
      for (i = 0; i < 8; i++) {
        j = (i + 1) % 8;
        if (sc2[i] === null || sc2[j] === null) continue;
        tri2(cap2, rim2[j], rim2[i], 2, i);                              // 顶盖：贴在台座下方
        quad2(rim2[i], verts2[i], verts2[j], rim2[j], 1, i);              // 外壁上段
        quad2(verts2[i], gir2[i], gir2[j], verts2[j], 3, i);              // 腰棱斜切带（aFace 3 = 磨砂）
        quad2(gir2[i], pv2[i], pv2[j], gir2[j], 0, i);                    // 亭部上段
        quad2(pv2[i], pv3[i], pv3[j], pv2[j], 0, i);                      // 亭部下段
        tri2(pv3[i], nadir2, pv3[j], 0, i);                               // 锥尖
      }
      for (i = 0; i < 8; i++) crownBlade(sc2, i, [cap2, rim2[i], verts2[i], gir2[i], pv2[i], pv3[i], nadir2], [2, 1, 3, 0, 0, 0], tri2);
      var gg2 = new T.BufferGeometry();
      gg2.setAttribute('position', new T.Float32BufferAttribute(P2, 3));
      gg2.setAttribute('aH', new T.Float32BufferAttribute(AH2, 1));
      gg2.setAttribute('aFace', new T.Float32BufferAttribute(AF2, 1));
      gg2.setAttribute('aAxis', new T.Float32BufferAttribute(AA2, 1));
      gg2.setAttribute('aBary', new T.Float32BufferAttribute(AB2, 3));
      gg2.setAttribute('aFacet', new T.Float32BufferAttribute(AFC2, 1));
      gg2.computeVertexNormals();
      // 底谱走紫晶：更高的 IOR / 更强的色散与吸收，越深越浓 —— 与上谱的薄荷-琥珀成一冷一热的对峙
      var gem2 = new T.Mesh(gg2, gemMat(CROWN_FS, gemSpec('amethystFire')));
      gem2.frustumCulled = false; lower.add(gem2);
      var gem2Base = new T.Mesh(gg2, gemMat(CROWN_BASE_FS, gemSpec('amethyst', { blend: T.NormalBlending,
        cen: new T.Vector3(0, (-CR_GAP + nadir2.y) * 0.5, 0), rad: new T.Vector3(CR_R2_0 + CR_R2_1 + 6, (CR_GAP + Math.abs(nadir2.y)) * 0.52, CR_R2_0 + CR_R2_1 + 6), thk: 1 / (2 * (CR_R2_0 + CR_R2_1 + 6)) })));
      gem2Base.frustumCulled = false; gem2Base.renderOrder = 1; lower.add(gem2Base);
      var ghost2A = new T.Mesh(gg2, ghostMat(0xff2ab4, 7.0)), ghost2B = new T.Mesh(gg2, ghostMat(0x5a3aff, 7.0));
      ghost2A.scale.setScalar(1.012); ghost2B.scale.setScalar(0.988);
      ghost2A.frustumCulled = ghost2B.frustumCulled = false; ghost2A.renderOrder = ghost2B.renderOrder = 4;
      lower.add(ghost2A); lower.add(ghost2B);
      // 反向扫描面：上谱的扫描环向上走，这一片在长锥内向下走 —— 两谱的「扫描方向」也是相对的
      var scan2 = ribbon(CR_R2_0 * 0.30, CR_R2_0 * 0.92, 192, { mode: 2, base: 0.62, ticks: 200, ca: 0xd873ff, cb: 0xfff1da });
      scan2.frustumCulled = false; lower.add(scan2);
      // 底面线框：悬垂支柱（脉冲向下）· 顶点环 · 边缘环 · 向下的信标 · 汇入锥尖的棱线
      var LP2 = [], LT2 = [], LK2 = [], LA2 = [];
      function seg2(a, b, ta, tb, k, ax) { LP2.push(a.x, a.y, a.z, b.x, b.y, b.z); LT2.push(ta, tb); LK2.push(k, k); LA2.push(ax, ax); }
      for (i = 0; i < 8; i++) {
        j = (i + 1) % 8;
        if (sc2[i] === null) continue;
        for (var q2 = 0; q2 < 6; q2++) seg2(rim2[i].clone().lerp(verts2[i], q2 / 6), rim2[i].clone().lerp(verts2[i], (q2 + 1) / 6), q2 / 6, (q2 + 1) / 6, 0, i);
        for (var q3 = 0; q3 < 8; q3++) seg2(verts2[i].clone().lerp(nadir2, q3 / 8), verts2[i].clone().lerp(nadir2, (q3 + 1) / 8), q3 / 8, (q3 + 1) / 8, 0, i);
        if (sc2[j] !== null) {
          seg2(verts2[i], verts2[j], 1, 1, 1, i);
          seg2(gir2[i], gir2[j], 1, 1, 1, i);     // v24.4 · 腰棱环
          seg2(rim2[i], rim2[j], 0, 0, 2, i);
        }
        var bt2 = verts2[i].clone(); bt2.y -= 10 + 30 * sc2[i];
        for (var bq2 = 0; bq2 < 6; bq2++) seg2(verts2[i].clone().lerp(bt2, bq2 / 6), verts2[i].clone().lerp(bt2, (bq2 + 1) / 6), bq2 / 6, (bq2 + 1) / 6, 4, i);
      }
      var lg2 = new T.BufferGeometry();
      lg2.setAttribute('position', new T.Float32BufferAttribute(LP2, 3));
      lg2.setAttribute('t', new T.Float32BufferAttribute(LT2, 1));
      lg2.setAttribute('k', new T.Float32BufferAttribute(LK2, 1));
      lg2.setAttribute('ax', new T.Float32BufferAttribute(LA2, 1));
      var lines2 = new T.LineSegments(lg2, new T.ShaderMaterial({ vertexShader: CRL_VS, fragmentShader: CRL_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uGrow: { value: 0 }, uHl: { value: -1 }, uLamp: { value: 0 }, uLampK: { value: 1 }, uLine: { value: lineComp() }, uCol: { value: new T.Color(0xb98cff) }, uHot: { value: new T.Color(0xf4e2ff) } } }));
      lines2.frustumCulled = false; lower.add(lines2);
      // 下沉微粒：从台座落向锥尖
      var MN2 = 120, mp2 = new Float32Array(MN2 * 3), mph2 = new Float32Array(MN2), msz2 = new Float32Array(MN2), H2 = CR_H2 + 20;
      for (i = 0; i < MN2; i++) { var mr2 = Math.sqrt(rnd(i * 1.9 + 0.5)) * (CR_R2_0 + CR_R2_1 * 0.8) * (0.35 + 0.65 * rnd(i * 3.3)), ma2 = rnd(i * 2.3 + 0.9) * Math.PI * 2; mp2[i * 3] = Math.sin(ma2) * mr2; mp2[i * 3 + 1] = rnd(i * 4.7) * H2; mp2[i * 3 + 2] = Math.cos(ma2) * mr2; mph2[i] = rnd(i * 6.7); msz2[i] = 2.0 + rnd(i * 8.9) * 3.4; }
      var mg2 = new T.BufferGeometry(); mg2.setAttribute('position', new T.BufferAttribute(mp2, 3)); mg2.setAttribute('ph', new T.BufferAttribute(mph2, 1)); mg2.setAttribute('sz', new T.BufferAttribute(msz2, 1));
      var motes2 = new T.Points(mg2, motesMat(H2, -1, 0xd873ff, 0xc9b8ff));
      motes2.position.y = -H2; motes2.frustumCulled = false; lower.add(motes2);
      // 锥尖深光（随下谱升降，挂在 lower 上）
      var glow2 = new T.Sprite(new T.SpriteMaterial({ map: texSoft, transparent: true, depthWrite: false, blending: T.AdditiveBlending, color: 0x9a55ff, opacity: 0 }));
      glow2.scale.set(150, 150, 1); glow2.position.copy(nadir2); lower.add(glow2);
      // 轴心与下表圈：一根穿过表盘中心的轴把两层连起来（相对运动时它跟着拉伸）；下层一圈细丝带作为底面的参考环
      var axle = hand(CR_GAP + 2, 2, 1.1, 1.1, 0xc9b8ff, 0xffffff); axle.rotation.x = Math.PI / 2; axle.position.y = 0.4; fx.add(axle);
      var lowRing = ribbon(CR_R2_0 - 4.5, CR_R2_0 - 3.0, 256, { mode: 2, base: 0.7, ticks: 180, ca: 0x6a4fd6, cb: 0xd9a6ff }); lowRing.position.y = -CR_GAP + 0.3; lower.add(lowRing);
      // 地面光晕
      var glow = new T.Sprite(new T.SpriteMaterial({ map: texSoft, transparent: true, depthWrite: false, blending: T.AdditiveBlending, color: 0x3fd6a8, opacity: 0 }));
      glow.scale.set(190, 190, 1); glow.position.y = -6; fx.add(glow);
      if (!warm) group.add(grp);
      var cr = { grp: grp, spin: spin, upper: upper, lower: lower, bridge: bridge, floor: floor, rim2: rim2, sep: 0, tension: 0, sig: sig,
        model: model, known: sc.map(function (v) { return v !== null; }), known2: sc2.map(function (v) { return v !== null; }), scored: scored,
        unknownTop: unknownAxes(sc, verts, upper, 0x8a9cbe), unknownBottom: unknownAxes(sc2, verts2, lower, 0x9988c0),
        refTop: crownReference(sc, verts, false, upper, apex), refBottom: crownReference(sc2, verts2, true, lower, nadir2),
        ghosts: [ghostA, ghostB, ghost2A, ghost2B], scan2: scan2,
        fx: fx, gem: gem, lines: lines, grid: grid, disc: disc, levels: levels, dial: dial, bezel: bezel, rimOut: rimOut,
        hands: hands, secHand: secHand, minHand: minHand, hourHand: hourHand, storyHand: storyHand, tipDot: tipDot, cap: cap, sweep: sweep, axle: axle, lowRing: lowRing, clockEl: clockEl, gemBase: gemBase, core: core, caust: caust, gem2Base: gem2Base,
        segN: SEGN, segmentTexture: segTex, nCh: CLH, lastIdx: lastIdx, mineIdx: mineIdx, storyPos: 0, storyIdx: Math.max(0, lastIdx), lastSec: null, readSec: null, readIdx: -1, clockText: '', hourAng: 0, hourInit: false, tickK: -1, shocks: shocks,
        gem2: gem2, lines2: lines2, motes2: motes2, glow2: glow2, verts2: verts2, scores2: sc2, avg2: avg2, nadir: nadir2.y,
        scan: scan, scanRing: scanRing, scanDisc: scanDisc, motes: motes, glow: glow, strings: strings, verts: verts, scores: sc, avg: avg, host: cn, born: tAcc, dying: 0, ang: crownAxisAngle(0) * 0 , vel: CR_SPIN, phase: 0 };
      cr._prewarmOnly = !!warm;
      /* Stable names expose the actual rendered meshes to geometry audits. */
      grp.name = 'gem-crown'; gem.name = 'gem-attributes'; gem2.name = 'gem-narrative';
      cr.unknownTop.name = 'gem-attributes-unknown'; cr.unknownBottom.name = 'gem-narrative-unknown';
      if (cr.refTop) cr.refTop.name = 'gem-reference-outline';
      if (cr.refBottom) cr.refBottom.name = 'gem-reference-outline-narrative';
      if (warm) return cr;
      crown = cr;
      updateGemOverlays();
      updateCrown(0);
      syncGemLegend();
      return crown;
    }
    /* v90 F3 · 竖刃：径向剖面 prof[0] 与 prof[末] 在轴心上，其余点都在该轴的径向平面内。
       以轴心中点为扇心逐段成三角；扇心两条内边抹掉（hide 6），只留剖面外轮廓的棱刃。 */
    function crownBlade(values, i, prof, faces, tf) {
      if (values[i] === null || (values[(i + 7) % 8] !== null && values[(i + 1) % 8] !== null)) return;
      var c = new T.Vector3(0, (prof[0].y + prof[prof.length - 1].y) / 2, 0);
      for (var b = 0; b < prof.length - 1; b++) tf(c, prof[b], prof[b + 1], faces[b], i, 6);
    }
    /* v90 F3 · 缺档扇区参考轮廓（非数据）：只画未知轴所在扇区——floor → 参考 50 分顶点的竖线，
       参考顶点连到左右邻轴（邻轴已知 → 连它的真实顶点；邻轴未知 → 连它的参考顶点，每条只画一次）。
       细点线（dash 1 / gap 2.5）与对照人物虚线（dash 3 / gap 2）一眼可分；无填充，不写入任何分值。 */
    var GEM_REF_SCORE = 50, GEM_REF_ALPHA = 0.8;
    function crownRefVertex(i, under) {
      var v = GEM_REF_SCORE / 100, a = crownAxisAngle(i) + (under ? Math.PI / 8 : 0);
      var r = under ? CR_R2_0 + CR_R2_1 * v : CR_R0 + CR_R1 * v;
      var y = under ? -(CR_GAP + 12 + CR_H2 * 0.5 * v) : CR_H * v;
      return new T.Vector3(Math.sin(a) * r, y, Math.cos(a) * r);
    }
    function crownReference(values, verts, under, parent, tip) {
      var pts = [], axes = [], i;
      for (i = 0; i < 8; i++) {
        if (values[i] !== null) continue;
        axes.push(i);
        var p = crownRefVertex(i, under), prev = (i + 7) % 8, next = (i + 1) % 8;
        // 「竖线」= 该扇区的结构棱：上冠 floor → 参考顶点；下锥颈口（半径 × GEM_NECK）→ 参考顶点，与真实扇区同构
        pts.push(under ? new T.Vector3(p.x * GEM_NECK, -CR_GAP, p.z * GEM_NECK) : new T.Vector3(p.x, 0, p.z), p);
        // 冠脊：参考顶点 → 台面顶（下锥为锥尖），缺档扇区因此补出一道宝石剪影，而不是几根孤立的桩
        if (tip) pts.push(p, tip.clone());
        if (values[prev] !== null) pts.push(p, verts[prev].clone());
        if (values[next] !== null) pts.push(p, verts[next].clone());
        else pts.push(p, crownRefVertex(next, under));
      }
      if (!pts.length) return null;
      var line = new T.LineSegments(new T.BufferGeometry().setFromPoints(pts), new T.LineDashedMaterial({ color: 0xc2b4ee, transparent: true, opacity: 0, dashSize: 1, gapSize: 2.5, depthWrite: false, blending: T.AdditiveBlending }));
      line.computeLineDistances();
      line.userData.gemReference = { axes: axes, under: !!under, score: GEM_REF_SCORE, data: false };
      line.frustumCulled = false; line.renderOrder = 5; parent.add(line); return line;
    }
    function unknownAxes(values, verts, parent, col) {
      var pts = [], count = 0;
      for (var i = 0; i < 8; i++) {
        if (values[i] !== null) continue;
        count++;
        var p = verts[i], j;
        /* v90 F3 · 旧版在这里另画一根竖虚线；扇区结构线已由参考轮廓（gem-reference-outline）承担，
           这里只保留轴位上的空心八面标记。
           Open octahedra remain visible edge-on. They denote missing data,
           never a fabricated zero score or an opaque placeholder facet. */
        var d = 4, top = new T.Vector3(p.x, p.y + d, p.z), bottom = new T.Vector3(p.x, p.y - d, p.z);
        var rim = [new T.Vector3(p.x + d, p.y, p.z), new T.Vector3(p.x, p.y, p.z + d), new T.Vector3(p.x - d, p.y, p.z), new T.Vector3(p.x, p.y, p.z - d)];
        for (j = 0; j < 4; j++) pts.push(top, rim[j], bottom, rim[j], rim[j], rim[(j + 1) % 4]);
      }
      var line = new T.LineSegments(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, depthWrite: false, blending: T.AdditiveBlending }));
      line.userData.unknownCount = count; line.frustumCulled = false; parent.add(line); return line;
    }
    function ghostContour(values, under, col, parent) {
      var verts = [], pts = [], i;
      for (i = 0; i < 8; i++) {
        var raw = values && values[i], v = raw == null ? null : clamp(raw / 100, 0, 1);
        var a = crownAxisAngle(i) + (under ? Math.PI / 8 : 0);
        var r = under ? CR_R2_0 + CR_R2_1 * v : CR_R0 + CR_R1 * v;
        var y = under ? -(CR_GAP + 12 + CR_H2 * 0.5 * v) : CR_H * v;
        verts.push(v === null ? null : new T.Vector3(Math.sin(a) * r, y, Math.cos(a) * r));
      }
      for (i = 0; i < 8; i++) {
        var j = (i + 1) % 8;
        if (verts[i] && verts[j]) pts.push(verts[i], verts[j]);
        if (verts[i]) pts.push(under ? new T.Vector3(verts[i].x * GEM_NECK, -CR_GAP, verts[i].z * GEM_NECK) : new T.Vector3(verts[i].x, 0, verts[i].z), verts[i]);
      }
      var line = new T.LineSegments(new T.BufferGeometry().setFromPoints(pts), new T.LineDashedMaterial({ color: col, transparent: true, opacity: 0, dashSize: 3, gapSize: 2, depthWrite: false, blending: T.AdditiveBlending }));
      line.userData.gemUnder = !!under;
      line.computeLineDistances(); line.frustumCulled = false; parent.add(line); return line;
    }
    function updateGemOverlays() {
      if (!crown || !crown.model) return;
      (crown.overlays || []).forEach(function (line) { line.parent.remove(line); line.geometry.dispose(); line.material.dispose(); });
      crown.overlays = [];
      var m = crown.model, baseline = gemScope === 'camp' && m.ghost.camp ? m.ghost.camp : m.ghost.book;
      crown.overlays.push(ghostContour(baseline, false, 0x668cac, crown.upper));
      crown.overlays[0].name = 'gem-benchmark-attributes';
      if (m.peer) {
        crown.overlays.push(ghostContour(m.peer.attr, false, 0xffc88b, crown.upper));
        crown.overlays[crown.overlays.length - 1].name = 'gem-peer-attributes';
        var pn = nodeByKey['c:' + m.peer.name], pm = pn ? buildGemModel(pn.data) : null;
        if (pm && pm.meta) {
          crown.overlays.push(ghostContour(pm.meta.map(function (d) { return d.known ? d.score : null; }), true, 0xffc88b, crown.lower));
          crown.overlays[crown.overlays.length - 1].name = 'gem-peer-narrative';
        }
        /* v90 F3 · 对照轮廓画在暗玻璃基底（renderOrder 1）之后：否则落在晶体内部的那段被基底盖暗，
           截图里看不见对照人，也就无法与缺档参考点线（dash 1 / gap 2.5）对照区分 */
        crown.overlays.forEach(function (line) { if (/^gem-peer-/.test(line.name)) line.renderOrder = 5; });
      }
    }
    // 晶冠局部坐标 → 屏幕像素（含漂浮矩阵与视差平移）；标签避让与辐射环都以它为准
    var _cp = new T.Vector3();
    function crownProj(x, y, z) {
      crown.grp.updateWorldMatrix(true, false);
      _cp.set(x, y, z).applyMatrix4(crown.grp.matrixWorld).project(camera);
      return [_cp.x * core.getW() / 2 + core.getW() / 2, -_cp.y * core.getH() / 2 + core.getH() / 2];
    }
    function smooth01(t, a, b) { return clamp((t - a) / (b - a), 0, 1); }
    var _cm = new T.Vector3(), _cmi = new T.Matrix4(), _cmj = new T.Matrix4(), _cbu = new T.Vector3(), _cbl = new T.Vector3();
    // v26.1 · 厚度着色要在晶体的局部坐标里求视线弦长，所以每帧把相机位置换算进去。
    // 两块基底各一次矩阵求逆，代价可忽略；换来的是正面看下去最深、腰棱一圈透亮的真宝石光学
    // —— 旧版拿菲涅尔当厚度替身，明暗恰好和真宝石相反。
    var _gmi = new T.Matrix4();
    function camToLocal(mesh) {
      if (!mesh || !mesh.material || !mesh.material.uniforms || !mesh.material.uniforms.uCamL) return;
      mesh.updateWorldMatrix(true, false);
      _gmi.copy(mesh.matrixWorld).invert();
      mesh.material.uniforms.uCamL.value.copy(camera.position).applyMatrix4(_gmi);
    }
    var TICK_SETTLE = 0.34;
    function pad2(n) { return (n < 10 ? '0' : '') + n; }
    function wallClock() {
      var d = new Date(core.wallMs ? core.wallMs() : Date.now()), ms = d.getMilliseconds(), s = d.getSeconds(), m = d.getMinutes(), h = d.getHours();
      var sec = s + ms / 1000, min = m + sec / 60;
      return { d: d, s: s, m: m, h: h, frac: ms / 1000, sec: sec, min: min, hr: (h % 12) + min / 60, epoch: Math.floor(d.getTime() / 1000) };
    }
    function dialLocked() { return !!(gemStageOn || dialHover || (stage && stage.chapSel ? stage.chapSel() : chapSel)); }
    function dialIndex(cr) {
      var chs = (bookStats && bookStats.chapters) || [], idx = -1;
      if (gemStageOn && gemChapter !== null) {
        var exact = typeof gemChapter === 'number' ? gemChapter : chs.indexOf(gemChapter);
        if (exact >= 0 && exact < chs.length) return exact;
      }
      var bMap = (core && core.getBucketMap ? core.getBucketMap() : bucketMap) || {};
      function firstOfBucket(label) { for (var i = 0; i < chs.length; i++) if ((bMap[chs[i]] || chs[i]) === label) return i; return -1; }
      if (dialHover) idx = firstOfBucket(dialHover);
      var cs = stage && stage.chapSel ? stage.chapSel() : chapSel;
      if (idx < 0 && cs) idx = firstOfBucket(cs);
      if (idx < 0 && cr) idx = cr.lastIdx;
      return idx < 0 ? 0 : idx;
    }
    var WEEK = '日一二三四五六';
    function updateDialReadout(wc, hIdx, on) {
      var el = crown.clockEl; if (!el) return;
      if (crown.readSec !== wc.epoch || crown.readIdx !== hIdx) {
        crown.readSec = wc.epoch; crown.readIdx = hIdx;
        var chs = (bookStats && bookStats.chapters) || [], ch = chs[hIdx];
        crown.clockText = pad2(wc.h) + ':' + pad2(wc.m) + ':' + pad2(wc.s);
        el.children[0].textContent = crown.clockText;
        el.children[1].textContent = 'LOCAL · ' + wc.d.getFullYear() + '-' + pad2(wc.d.getMonth() + 1) + '-' + pad2(wc.d.getDate()) + ' · 周' + WEEK[wc.d.getDay()];
        el.children[2].textContent = ch ? String(ch) : '—';
        el.children[3].textContent = (dialLocked() ? '锁定' : '每秒一章') + ' · ' + (hIdx + 1) + ' / ' + crown.nCh + (crown.mineIdx.length ? ' · 出场 ' + crown.mineIdx.length + ' 章' : '');
        crown.dialH = el.offsetHeight || 78;
      }
      el.classList.toggle('tick', wc.frac < 0.18);
      // 锚点：表盘 6 点方向外侧（grp 局部 +z），随晶冠漂浮与视差一起投影
      crown.grp.updateWorldMatrix(true, false);
      _cm.set(0, 0.6, CR_R0 + CR_R1 + 46).applyMatrix4(crown.grp.matrixWorld).project(camera);
      var x = _cm.x * W / 2 + W / 2, y = -_cm.y * H / 2 + H / 2;
      el.style.transform = 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px)';
      el.style.opacity = (on * (face === 'under' ? 0.55 : 1)).toFixed(3);
      // 给标签避让用的屏幕盒（与 CSS 的 margin-left:-92px / margin-top:8px / width:184px 对应）
      crown.dialBox = { x: x - 92, y: y + 8, w: 184, h: crown.dialH || 78 };
    }
    function updateCrown(dt) {
      if (!crown) return;
      var t = tAcc - crown.born, k = 1;
      if (crown.dying) { k = 1 - clamp((tAcc - crown.dying) / 0.38, 0, 1); if (k <= 0) { crownDispose(true); return; } }   /* 消散完停进停放槽（Q5.5），不销毁 */
      // 自旋：悬停某一轴时缓停，方便点击；鼠标视差叠加一点方位与俯仰
      // v42：静止档**必须停转**（vel → 0 且 ang 不再累加）。原来 calm 下取 CR_SPIN*0.35
      // 是「慢速自转」，但 crown.ang += vel*dt 是积分器：慢速也意味着每帧都在挪，
      // 同态两拍的三维仪器方位就对不上（实测该处 maxΔ=226，是全画面最大的单点差）。
      crown.vel = settle(crown.vel, crownHold ? 0 : (calm ? 0 : CR_SPIN), 0.08, calm);
      crown.ang += crown.vel * dt;
      crown.spin.rotation.y = crown.ang + parallax.x * 0.35;
      // 漂浮：整座晶冠随缓慢起伏与进动摆动，像悬停在角色星体之下的仪器
      var fl = calm ? 0 : 1;
      crown.grp.rotation.x = CR_TILT + parallax.y * 0.12 + Math.sin(t * 0.31) * 0.05 * fl;
      crown.grp.rotation.z = Math.cos(t * 0.23) * 0.04 * fl;
      if (crown.host) crown.grp.position.copy(crown.host.pos).add(_cm.set(0, -CR_DROP + Math.sin(t * 0.7) * 2.6 * fl, 0));
      // ---- v24.4 · 对置双谱的相对运动 ----------------------------------------------------
      // 一条相位驱动三件事：反相升降（颈距呼吸）· 反向自转（陀螺仪）· 反向进动（点头）。
      // 三者共用同一相位，所以画面读到的不是"两个东西各自乱动"，而是一副互相角力的仪器。
      // 入场时 sep 从 0 缓入，落成动画不被抢戏；calm 模式只保留常态间距，不做运动。
      var sepIn = easeInOut(smooth01(t, 0.55, 1.32)) * fl;
      crown.sepIn = sepIn;   // 探针 settleT 读这里：入场包络是否已走完
      var sepPh = t * (Math.PI * 2 / CR_SEP_PER);
      var sepS = Math.sin(sepPh) * sepIn;                       // -1 … 1
      crown.sep = sepS;
      crown.tension = clamp(0.5 + 0.5 * sepS, 0, 1);            // 0 = 颈距最短 · 1 = 拉到最长
      crown.upper.position.y = CR_LIFT + CR_UP_AMP * sepS;
      crown.lower.position.y = -CR_LO_AMP * sepS;
      // 反向自转：上冠随 spin 再多走 0.35ω，下锥反着走 1.35ω → 相对角速度约 1.7ω，两谱的棱线永远在错开
      crown.upper.rotation.y = crown.ang * 0.35 * fl;
      crown.lower.rotation.y = -crown.ang * CR_COUNTER * fl;
      // 反向进动：拉开时两谱各自向外倒一点，靠拢时收回 —— 让升降不只是平移
      crown.upper.rotation.x = 0.030 * sepS; crown.upper.rotation.z = -0.024 * Math.cos(sepPh) * sepIn;
      crown.lower.rotation.x = -0.026 * sepS; crown.lower.rotation.z = 0.020 * Math.cos(sepPh) * sepIn;
      // 呼吸缩放：拉开时上冠微涨、下锥微缩（反相），幅度只有 2%，靠它把「相对」写进体积而不只是位置
      var bs = 1 + 0.020 * sepS; crown.upper.scale.set(bs, 1, bs); crown.lower.scale.set(2 - bs, 1, 2 - bs);
      crown.grp.updateMatrix(); crown.spin.updateMatrix(); crown.upper.updateMatrix(); crown.lower.updateMatrix();
      var eIn = smooth01(t, 0, 0.55), grid = crown.grid, gemOn = smooth01(t, 0.55, 1.25), lnOn = smooth01(t, 0.15, 0.5), grow = easeOut(smooth01(t, 0.25, 0.95));
      crown.unknownTop.material.opacity = 0.74 * gemOn * k;
      crown.unknownBottom.material.opacity = 0.74 * gemOn * k;
      if (crown.refTop) crown.refTop.material.opacity = GEM_REF_ALPHA * gemOn * k;
      (crown.overlays || []).forEach(function (line, i) { line.material.opacity = (i ? 0.72 : 0.30) * gemOn * k; });
      grid.material.opacity = 0.26 * eIn * k; crown.disc.material.opacity = 0.9 * eIn * k;
      var gs = 0.72 + 0.28 * easeOut(eIn); crown.grid.scale.set(gs, 1, gs); crown.disc.scale.set(gs, gs, 1);
      // v26.0 · 轮流呼吸灯：相位取自 radar.js（同一只挂钟、同一条公式），所以右坞的雷达与这座晶冠
      // 永远在读同一维。CLRadar 没加载时退回本地时钟，晶冠照亮，只是两边不同步。
      // v42：radar.js 的 lampPhase 读 performance.now()，那是**绕过 scene 挂钟**的第二只钟 ——
      // 静止档里它照走不误，每 2.62 s 把「点亮哪一维」整格切换一次。这正是「同态两拍忽大忽小」
      // 里那条**离散跳变**：跨格的那一拍 diff 15%，没跨的那一拍 0.2%。静止档一律改吃 tAnim（已冻结）。
      var lampPh = calm ? (tAnim / 2.62) % 8
        : (window.CLRadar && window.CLRadar.lampPhase) ? window.CLRadar.lampPhase() : (tAcc / 2.62) % 8;
      var lampK = calm ? 0.35 : 1;
      crown.lines.material.uniforms.uOn.value = lnOn * k; crown.lines.material.uniforms.uGrow.value = grow; crown.lines.material.uniforms.uTime.value = tAnim; crown.lines.material.uniforms.uHl.value = crownHl;
      crown.lines.material.uniforms.uLamp.value = lampPh; crown.lines.material.uniforms.uLampK.value = lampK;
      if (crown.strings.material.uniforms.uLamp) { crown.strings.material.uniforms.uLamp.value = lampPh; crown.strings.material.uniforms.uLampK.value = lampK * 0.7; }
      if (crown.lines2.material.uniforms.uLamp) { crown.lines2.material.uniforms.uLamp.value = (lampPh + 4) % 8; crown.lines2.material.uniforms.uLampK.value = lampK * 0.85; }
      crown.gem.material.uniforms.uOn.value = gemOn * k; crown.gem.material.uniforms.uTime.value = tAnim; crown.gem.material.uniforms.uHl.value = crownHl;
      crown.gem.scale.y = 0.15 + 0.85 * easeOutBack(smooth01(t, 0.5, 1.2));
      /* Q8.4 入场：线框 → 实体。t 是晶冠建好以来的秒数（长起来那条同款时钟），
         uWire 在 0.35–1.15 s 之间从 1 退到 0：先只见棱线，再把面里的火彩 / 焦散补进来。
         减弱动效直接给 0（一帧就是实体）。材质默认 uWire = 0，没进罗盘的路径逐位不变。 */
      var wireK = calm ? 0 : 1 - smooth01(t, 0.35, 1.15);   /* calm = prefers-reduced-motion（本文件顶上就是这个判断） */
      crownWire(crown, wireK);
      crown.gemBase.scale.y = crown.gem.scale.y; crown.gemBase.material.uniforms.uOn.value = gemOn * k; crown.gemBase.material.uniforms.uTime.value = tAnim; crown.gemBase.material.uniforms.uHl.value = crownHl;
      crown.lines.scale.y = crown.gem.scale.y;
      crown.unknownTop.scale.y = crown.gem.scale.y;
      if (crown.refTop) crown.refTop.scale.y = crown.gem.scale.y;
      crown.core.material.uniforms.uOn.value = 0.85 * smooth01(t, 0.75, 1.4) * k * (0.9 + 0.1 * Math.sin(tAnim * 1.3)); crown.core.material.uniforms.uTime.value = tAnim; crown.core.material.uniforms.uHl.value = crownHl;
      crown.core.rotation.y = -crown.ang * 0.35;
      // v71 修复：QSPEC 的 caust 档从未被消费——L2 下台座焦散必须真的关闭（视觉契约 W9）
      crown.caust.visible = (core.qspec ? core.qspec().caust : 1) > 0;
      crown.caust.material.uniforms.uOn.value = 0.22 * smooth01(t, 0.6, 1.5) * k; crown.caust.material.uniforms.uTime.value = tAnim;
      // ---- 表盘（钟表式）：层级环错峰亮起，章节表圈与表圈随后，走针最后伸出
      var dialOn = smooth01(t, 0.1, 0.8) * k, handsOn = smooth01(t, 0.45, 1.1) * k;
      for (var li = 0; li < crown.levels.length; li++) { var lm = crown.levels[li].material.uniforms; lm.uOn.value = (0.55 + 0.1 * li) * smooth01(t, 0.05 + li * 0.07, 0.5 + li * 0.07) * k; lm.uTime.value = tAnim; crown.levels[li].scale.set(gs, 1, gs); }
      crown.dial.material.uniforms.uOn.value = dialOn; crown.dial.material.uniforms.uTime.value = tAnim;
      crown.bezel.material.uniforms.uOn.value = dialOn; crown.bezel.material.uniforms.uTime.value = tAnim;
      crown.rimOut.material.uniforms.uOn.value = dialOn; crown.rimOut.material.uniforms.uTime.value = tAnim;
      crown.lowRing.material.uniforms.uOn.value = smooth01(t, 0.9, 1.5) * k; crown.lowRing.material.uniforms.uTime.value = tAnim;
      crown.cap.material.uniforms.uOn.value = handsOn; crown.cap.material.uniforms.uTime.value = tAnim;
      // ---- 走针 = 本机时钟（v17.14）：秒针 1 Hz 擒纵跳格（落格前 0.34 s 回弹），分针 / 时针按真实速率连续走；
      //      章节表圈的「当前章」由剧情针指示：无悬停 / 选中时随每一次秒跳前进一章（与时钟同拍），有悬停 / 选中时锁定
      var wc = wallClock(), tf = wc.frac, te = tf < TICK_SETTLE ? easeOutBack(tf / TICK_SETTLE) : 1;
      var thetaS = calm ? (wc.sec / 60) * Math.PI * 2 : ((wc.s - 1) + te) * (Math.PI * 2 / 60);
      var thetaM = (wc.min / 60) * Math.PI * 2, thetaH = (wc.hr / 12) * Math.PI * 2;
      if (crown.lastSec !== wc.epoch) {
        var stepped = crown.lastSec != null; crown.lastSec = wc.epoch;
        if (stepped && !dialLocked() && crown.mineIdx.length) crown.storyPos = (crown.storyPos + 1) % crown.mineIdx.length;
      }
      var hIdx = dialLocked() ? dialIndex(crown) : (crown.mineIdx.length ? crown.mineIdx[crown.storyPos] : Math.max(0, crown.lastIdx));
      var thetaSt = ((hIdx + 0.5) / Math.max(1, crown.nCh)) * Math.PI * 2;
      if (!crown.hourInit) { crown.hourAng = thetaSt; crown.hourInit = true; }
      var dH = thetaSt - crown.hourAng; dH -= Math.round(dH / (Math.PI * 2)) * Math.PI * 2; crown.hourAng += dH * (calm ? 0.22 : 0.14);
      var hsc = 0.15 + 0.85 * easeOutBack(smooth01(t, 0.45, 1.15));
      crown.secHand.rotation.y = Math.PI - thetaS; crown.minHand.rotation.y = Math.PI - thetaM; crown.hourHand.rotation.y = Math.PI - thetaH; crown.storyHand.rotation.y = Math.PI - crown.hourAng;
      crown.secHand.scale.z = crown.minHand.scale.z = crown.hourHand.scale.z = crown.storyHand.scale.z = hsc;
      crown.secHand.material.uniforms.uOn.value = handsOn; crown.minHand.material.uniforms.uOn.value = 0.85 * handsOn; crown.hourHand.material.uniforms.uOn.value = handsOn;
      crown.storyHand.material.uniforms.uOn.value = dialOn * (0.75 + 0.45 * Math.exp(-tf * 4.0));
      var Rtip = (CR_R0 + CR_R1 + 11) * hsc;
      crown.tipDot.position.set(Math.sin(Math.PI - thetaS) * Rtip, 0.2, Math.cos(Math.PI - thetaS) * Rtip); crown.tipDot.material.opacity = handsOn * (0.5 + 0.5 * Math.exp(-tf * 5));
      // 表圈脉冲：秒针落格的一瞬，对应刻度亮起并衰减（表圈随自旋，换算到自旋局部角）
      crown.tickK = wc.s; crown.storyIdx = hIdx;
      crown.bezel.material.uniforms.uTick.value = (Math.PI - wc.s * (Math.PI * 2 / 60)) - crown.spin.rotation.y; crown.bezel.material.uniforms.uPulse.value = calm ? 0 : Math.exp(-tf * 5.0) * handsOn;
      // 余晖跟着秒针；章节表圈的当前章 = 剧情针所指，心跳与秒跳同拍
      crown.sweep.material.uniforms.uAng.value = Math.PI - thetaS; crown.sweep.material.uniforms.uOn.value = handsOn;
      crown.dial.material.uniforms.uCur.value = Math.floor(hIdx / Math.max(1, crown.nCh) * crown.segN);
      crown.dial.material.uniforms.uPulse.value = calm ? 0.6 : Math.exp(-tf * 3.0);
      updateDialReadout(wc, hIdx, handsOn * k);
      for (var wi = 0; wi < crown.shocks.length; wi++) {
        var wu = smooth01(t, 0.55 + wi * 0.22, 1.45 + wi * 0.22), wsk = crown.shocks[wi], Rsw = CR_R0 + CR_R1 + 4;
        var wr = Rsw * (0.3 + 1.45 * easeOut(wu)); wsk.scale.set(wr, 1, wr);
        wsk.material.opacity = (wu > 0 && wu < 1) ? Math.pow(1 - wu, 1.6) * 0.5 * k : 0;
      }
      var st = t - 1.2;
      if (st > 0) { var sy = CR_H * 1.1 * (0.5 - 0.5 * Math.cos(st * 0.9)); crown.scan.position.y = sy; var sOn = smooth01(st, 0, 0.5) * k; crown.scanRing.material.uniforms.uOn.value = 0.5 * sOn; crown.scanRing.material.uniforms.uTime.value = tAnim; crown.scanDisc.material.opacity = 0.04 * sOn; }
      crown.motes.material.uniforms.uTime.value = tAnim; crown.motes.material.uniforms.uOn.value = smooth01(t, 0.8, 1.6) * k;
      crown.glow.material.opacity = 0.19 * smooth01(t, 0, 0.7) * k;
      // 底面晶锥：顶冠落成后向下生长（scale.y 以台座为原点），支柱脉冲下行、微粒下沉、锥尖深光渐亮
      var g2On = smooth01(t, 0.85, 1.6) * k, l2On = smooth01(t, 0.7, 1.25) * k;
      crown.gem2.material.uniforms.uOn.value = g2On; crown.gem2.material.uniforms.uTime.value = tAnim; crown.gem2.material.uniforms.uHl.value = crownHl2;
      crown.gem2.scale.y = 0.08 + 0.92 * easeOutBack(smooth01(t, 0.85, 1.95));
      crown.gem2Base.scale.y = crown.gem2.scale.y; crown.gem2Base.material.uniforms.uOn.value = g2On * 0.8; crown.gem2Base.material.uniforms.uTime.value = tAnim; crown.gem2Base.material.uniforms.uHl.value = crownHl2;
      crown.lines2.material.uniforms.uOn.value = l2On * 0.62; crown.lines2.material.uniforms.uGrow.value = easeOut(smooth01(t, 0.8, 1.8)); crown.lines2.material.uniforms.uTime.value = tAnim; crown.lines2.material.uniforms.uHl.value = crownHl2;
      crown.lines2.scale.y = crown.gem2.scale.y;
      crown.unknownBottom.scale.y = crown.gem2.scale.y;
      if (crown.refBottom) { crown.refBottom.scale.y = crown.gem2.scale.y; crown.refBottom.material.opacity = GEM_REF_ALPHA * g2On; }
      (crown.overlays || []).forEach(function (line) { line.scale.y = line.userData.gemUnder ? crown.gem2.scale.y : crown.gem.scale.y; });
      /* Camera-space optics and comparison contours consume this frame's
         complete transform, including the entrance scale of both crystals. */
      camToLocal(crown.gemBase); camToLocal(crown.gem2Base);
      crown.motes2.material.uniforms.uTime.value = tAnim; crown.motes2.material.uniforms.uOn.value = smooth01(t, 1.3, 2.1) * k;
      crown.glow2.material.opacity = (0.22 + 0.10 * crown.tension) * smooth01(t, 1.1, 1.9) * k;
      crown.glow2.position.y = crown.nadir * crown.gem2.scale.y;
      // 色散重影：偏移量随分离度呼吸（拉开时棱镜边更宽），两谱的偏移方向相反
      // v71 修复：QSPEC 的 ghost 档从未被消费——L1/L2 下重影必须真的隐藏（视觉契约 W9）
      var ghAllow = (core.qspec ? core.qspec().ghost : 1) > 0;
      var ghOn = smooth01(t, 1.2, 2.2) * k * (calm ? 0.5 : 1), ghK = 0.010 + 0.006 * crown.sep;
      var ghS = [1 + ghK, 1 - ghK, 1 - ghK, 1 + ghK];   // 两谱的红 / 青偏移方向相反
      for (var gi = 0; gi < 4; gi++) {
        var gh = crown.ghosts[gi], gm = gh.material.uniforms, gy = gi < 2 ? crown.gem.scale.y : crown.gem2.scale.y;
        gh.visible = ghAllow;
        gh.scale.set(ghS[gi], ghS[gi] * gy, ghS[gi]);    // y 要跟着各自的入场生长，否则落成时重影会露在本体外
        gm.uOn.value = (gi < 2 ? gemOn : g2On) * ghOn * 0.42; gm.uTime.value = tAnim;
      }
      // 反向扫描面：在长锥腰下向锥尖走，与上谱扫描环反向（相对运动的第三层读数）
      var s2t = t - 1.9;
      if (s2t > 0) {
        var s2p = 0.5 - 0.5 * Math.cos(s2t * 0.72);
        crown.scan2.position.y = lerp(-CR_GAP - 10, crown.nadir * crown.gem2.scale.y + 14, s2p);
        var s2s = 1 - 0.72 * s2p; crown.scan2.scale.set(s2s, 1, s2s);
        var s2u = crown.scan2.material.uniforms;
        s2u.uOn.value = 0.44 * smooth01(s2t, 0, 0.6) * k; s2u.uTime.value = tAnim;
      }
      // 轴心随颈距拉伸：一端咬住上冠亭尖、一端咬住下锥腰环，拉开时变长变亮 —— 相对运动的第一读数
      var neckTop = crown.upper.position.y - CR_H * 0.22, neckBot = crown.lower.position.y - CR_GAP;
      crown.axle.position.y = neckTop;
      crown.axle.scale.z = Math.max(0.2, (neckTop - neckBot) / (CR_GAP + 2));
      crown.axle.material.uniforms.uOn.value = (0.55 + 0.45 * crown.tension) * smooth01(t, 0.8, 1.3) * k;
      // ---- 张力桥：上冠底缘 ↔ 下锥腰环，每帧在 spin 局部重算（96 个顶点，上传可忽略）
      if (crown.bridge) {
        var bp = crown.bridge.geometry.attributes.position, ba = bp.array, BS = 6, bo = 0, _bu = _cbu, _bl = _cbl;
        for (var bi = 0; bi < 8; bi++) {
          _bu.copy(crown.floor[bi]).multiplyScalar(0.86).applyMatrix4(crown.upper.matrix);
          _bl.copy(crown.rim2[bi]); _bl.y *= crown.gem2.scale.y; _bl.applyMatrix4(crown.lower.matrix);
          if (!crown.known[bi] || !crown.known2[bi]) { _bu.set(0, 0, 0); _bl.set(0, 0, 0); }
          for (var bq = 0; bq < BS; bq++) {
            var b0 = bq / BS, b1 = (bq + 1) / BS;
            // 中段向轴心微收：拉开时收得更紧，光丝读成绷起来的弦而不是直棍
            var w0 = 1 - 0.16 * Math.sin(b0 * Math.PI) * (0.4 + 0.6 * crown.tension), w1 = 1 - 0.16 * Math.sin(b1 * Math.PI) * (0.4 + 0.6 * crown.tension);
            ba[bo++] = lerp(_bu.x, _bl.x, b0) * w0; ba[bo++] = lerp(_bu.y, _bl.y, b0); ba[bo++] = lerp(_bu.z, _bl.z, b0) * w0;
            ba[bo++] = lerp(_bu.x, _bl.x, b1) * w1; ba[bo++] = lerp(_bu.y, _bl.y, b1); ba[bo++] = lerp(_bu.z, _bl.z, b1) * w1;
          }
        }
        bp.needsUpdate = true;
        var bu = crown.bridge.material.uniforms;
        bu.uOn.value = smooth01(t, 1.5, 2.4) * k; bu.uTime.value = tAnim; bu.uTension.value = crown.tension;
      }
      // 八维节点吸附到顶点（组坐标）；晶冠消散时不再接管 to，让 toAtlas 的目标生效
      if (!crown.dying) for (var i = 0; i < 8; i++) {
        var n = nodeByKey['a:' + ATTR_KEYS[i]]; if (!n) continue;
        _cm.copy(crown.verts[i]); _cm.y *= crown.gem.scale.y;
        _cm.applyMatrix4(crown.upper.matrix).applyMatrix4(crown.spin.matrix).applyMatrix4(crown.grp.matrix);
        n.to.copy(_cm); n.pos.copy(_cm); n.g.position.copy(_cm);
        var n2 = nodeByKey['m:' + META_KEYS[i]]; if (!n2) continue;
        _cm.copy(crown.verts2[i]); _cm.y *= crown.gem2.scale.y; _cm.applyMatrix4(crown.lower.matrix).applyMatrix4(crown.spin.matrix).applyMatrix4(crown.grp.matrix);
        n2.to.copy(_cm); n2.pos.copy(_cm); n2.g.position.copy(_cm);
      }
      // 弦：把星体位置换到 upper 局部坐标，八条线段组随自旋实时重算（48 个顶点，上传可忽略）
      if (crown.host) {
        _cmi.copy(crown.grp.matrix).multiply(crown.spin.matrix).multiply(crown.upper.matrix).invert();
        _cm.copy(crown.host.pos).applyMatrix4(_cmi);
        var sp = crown.strings.geometry.attributes.position, arr = sp.array, SS = 8, o = 0;
        for (var si = 0; si < 8; si++) { var vv = crown.known[si] ? crown.verts[si] : _cm, vy = crown.known[si] ? vv.y * crown.gem.scale.y : vv.y; for (var sq = 0; sq < SS; sq++) { var ta = sq / SS, tb = (sq + 1) / SS;
          arr[o++] = _cm.x + (vv.x - _cm.x) * ta; arr[o++] = _cm.y + (vy - _cm.y) * ta; arr[o++] = _cm.z + (vv.z - _cm.z) * ta;
          arr[o++] = _cm.x + (vv.x - _cm.x) * tb; arr[o++] = _cm.y + (vy - _cm.y) * tb; arr[o++] = _cm.z + (vv.z - _cm.z) * tb; } }
        sp.needsUpdate = true;
        crown.strings.material.uniforms.uOn.value = smooth01(t, 0.35, 0.9) * k; crown.strings.material.uniforms.uTime.value = tAnim; crown.strings.material.uniforms.uHl.value = crownHl;
      }
    }
    // ---------------------------------------------------------- 星座星云 / 阵营交互（v18.2）
    // 角色区不是“按重要度排成一列”：每个阵营是一座可读的 3D 星座。
    // frame = 轨道 / 极轴 / 刻度；spokes = 主星到成员的星座骨架；glow = 立场色星云。
    // 章节与叙事枢仍保留在左右外围，角色关系因此成为画面第一主语。
    function constellationFrame(cp, lay, col, ci) {
      var R = Math.max(62, cp.r * 1.16), sy = 0.74, N = 96, P = [], i;
      for (i = 0; i < N; i++) {
        var a = Math.PI * 2 * i / N;
        P.push(Math.cos(a) * R, Math.sin(a) * R * sy, 0);
      }
      var gg = new T.Group();
      gg.position.set(cp.cx, cp.cy, cp.cz - 12);
      // 每座轨道拥有独立的轻微俯仰 / 偏航：同一平面上的圆环会像 UI 装饰，
      // 倾角让角色区在 three.js 里读成有厚度的天球，而不是平面框。
      gg.rotation.x = (rnd(hash(cp.name) * 0.19) - 0.5) * 0.28;
      gg.rotation.y = (rnd(hash(cp.name) * 0.31) - 0.5) * 0.34;
      gg.rotation.z = (rnd(hash(cp.name) * 0.37) - 0.5) * 0.16;
      gg.renderOrder = -8;
      var mat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var ring = new T.LineLoop(new T.BufferGeometry().setFromPoints(P.map(function (v, q) { return new T.Vector3(P[q * 3], P[q * 3 + 1], P[q * 3 + 2]); })), mat);
      gg.add(ring);
      // 第二道细轨道只在大于一人的星座出现；单人阵营保留一枚定位十字。
      var R2 = R * 1.19, P2 = [];
      for (i = 0; i < N; i++) { var a2 = Math.PI * 2 * i / N + 0.035; P2.push(new T.Vector3(Math.cos(a2) * R2, Math.sin(a2) * R2 * sy, 3)); }
      var outerMat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var outer = new T.LineLoop(new T.BufferGeometry().setFromPoints(P2), outerMat); gg.add(outer);
      // 极轴与 12 个刻度，把“这一团人”读成一个稳定的天体，而不是装饰光圈。
      var ticks = [];
      for (i = 0; i < 12; i++) {
        var at = Math.PI * 2 * i / 12, ca = Math.cos(at), sa = Math.sin(at);
        ticks.push(new T.Vector3(ca * R * 1.01, sa * R * sy * 1.01, 4), new T.Vector3(ca * R * (i % 3 ? 1.045 : 1.085), sa * R * sy * (i % 3 ? 1.045 : 1.085), 4));
      }
      var tickMat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var tickLine = new T.LineSegments(new T.BufferGeometry().setFromPoints(ticks), tickMat); gg.add(tickLine);
      var axes = [new T.Vector3(-R * 1.04, 0, 2), new T.Vector3(R * 1.04, 0, 2), new T.Vector3(0, -R * sy * 1.04, 2), new T.Vector3(0, R * sy * 1.04, 2)];
      var axisMat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var axisLine = new T.LineSegments(new T.BufferGeometry().setFromPoints(axes), axisMat); gg.add(axisLine);
      // 不再绘制“中心主星 → 全员”的太阳放射线；星座骨架由 layout.glyphEdges
      // 按折线 / 三角 / 勺形等字形连接，避免把阵营误读成神经放射束。
      var spokeMat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var spokeLine = new T.LineSegments(new T.BufferGeometry(), spokeMat); gg.add(spokeLine);
      group.add(gg);
      return { group: gg, ring: ring, outer: outer, ticks: tickLine, axes: axisLine, spokes: spokeLine, R: R, col: col, baseRot: gg.rotation.z, born: tAcc + 0.26 + ci * 0.08, k: 0 };
    }

    var infoLayer = 'overview';
    S.setInfoLayer = function (layer) {
      infoLayer = ['overview', 'evidence', 'relations', 'arc', 'story'].indexOf(layer) >= 0 ? layer : 'overview';
      var layerHl = function (f) {
        if (infoLayer === 'relations') return f.kind === 'rel' ? (f.webCore === false ? -2 : 2) : -0.72;   // v90 F7：大关系网全景只画核心关系   // v90 F4：2 = 类型强调档（FIBER_FS 保留类别色、稳定亮度、不洗白）
        if (infoLayer === 'evidence') return f.kind === 'chain' ? 1 : (f.kind === 'rel' ? 0.25 : -0.35);
        if (infoLayer === 'arc') return f.kind === 'chain' ? 0.9 : (f.kind === 'rel' ? -0.15 : -0.35);
        /* v71 W4 · 剧情线层：章节链最亮（剧情沿时间流动），出场纤维次之，关系退到背景 */
        if (infoLayer === 'story') return f.kind === 'chain' ? 1 : (f.kind === 'rel' ? 0.2 : 0.4);
        return 0;
      };
      // v90 F4：本层明暗登记为纤维底色——其他高亮结束（返回 0）时回落到本层，而不是熄灭
      if (core.setFiberBase) core.setFiberBase(infoLayer === 'overview' ? null : layerHl);
      if (core.getFiberMesh && core.getFiberMesh()) setFiberHl(layerHl);
      dirty = true;
      return infoLayer;
    };
    S.infoLayer = function () { return infoLayer; };
    S.hoverAttr = function (key) {
      var idx = key ? ATTR_KEYS.indexOf(key) : -1;
      crownHl = idx; crownHold = idx >= 0 ? 1 : 0; if (idx >= 0) crownHl2 = -1;
      if (idx >= 0) { var n = nodeByKey['a:' + key]; if (n) n.flash = Math.max(n.flash || 0, 0.55); }
      return idx;
    };
    // ---- 观察面：顶面 = 人物内在八维；底面 = 叙事位置八维。翻到底面时镜头下潜到台座之下仰视，顶面标签退隐，两面各自完整可读
    var face = 'top', previewCamera = null;
    function captureCameraView() {
      var view = camera.view, saved = null;
      if (view && view.enabled) { saved = {}; Object.keys(view).forEach(function (key) { saved[key] = view[key]; }); }
      return saved;
    }
    function restoreCameraView(view) {
      if (view && view.enabled) camera.setViewOffset(view.fullWidth, view.fullHeight, view.offsetX, view.offsetY, view.width, view.height);
      else camera.clearViewOffset();
    }
    function crownGeometryObjects() {
      if (!crown) return [];
      return [crown.gem, crown.gem2, crown.lines, crown.lines2, crown.unknownTop, crown.unknownBottom,
        crown.dial, crown.bezel, crown.rimOut, crown.lowRing].concat(crown.overlays || [], [crown.refTop, crown.refBottom].filter(Boolean));
    }
    function eachCrownVertex(visit) {
      crown.grp.updateWorldMatrix(true, true);   /* 只更新晶冠这一支（Q5.5）：整组 updateMatrixWorld 要把近千个星节点一并重算，罗盘态每帧两次 */
      var p = new T.Vector3();
      crownGeometryObjects().forEach(function (obj) {
        var attr = obj.geometry && obj.geometry.attributes.position;
        if (!attr) return;
        for (var i = 0; i < attr.count; i++) {
          p.fromBufferAttribute(attr, i).applyMatrix4(obj.matrixWorld);
          visit(p, obj);
        }
      });
    }
    function crownBox() {
      if (!crown) return null;
      var box = new T.Box3();
      eachCrownVertex(function (p) { box.expandByPoint(p); });
      return box;
    }
    function crownDestinationSphere(sweep) {
      if (!crown) return null;
      /* At selection time host.pos still belongs to the old constellation.
         Bound the complete data instrument, including comparison contours,
         missing-axis marks and the chapter ring, at its final destination. */
      var pos = crown.grp.position.clone(), upY = crown.upper.position.y, loY = crown.lower.position.y;
      var objects = crownGeometryObjects(), scales = objects.map(function (obj) { return obj.scale.y; });
      crown.grp.position.copy(crown.host.to).add(new T.Vector3(0, -CR_DROP, 0));
      crown.upper.position.y = CR_LIFT; crown.lower.position.y = 0;
      objects.forEach(function (obj) { obj.scale.y = 1; });
      crown.grp.updateWorldMatrix(true, true);
      var inverse = new T.Matrix4().copy(crown.grp.matrixWorld).invert(), points = [], box = new T.Box3();
      eachCrownVertex(function (p) { var local = p.clone().applyMatrix4(inverse); points.push(local); box.expandByPoint(local); });
      /* A rotationally invariant sphere about the crown axis keeps the full
         instrument in frame under every yaw, pitch and counter-rotation. */
      var center = new T.Vector3(0, (box.min.y + box.max.y) / 2, 0), radius = 0;
      points.forEach(function (p) { radius = Math.max(radius, p.distanceTo(center)); });
      var sphere = new T.Sphere(center, radius + Math.max(CR_UP_AMP, CR_LO_AMP) + 9).applyMatrix4(crown.grp.matrixWorld);
      /* v90 F3 · 取景用的晶体扫掠点：上冠 / 下锥每个顶点绕各自自旋轴 16 等分（世界坐标，落位后） */
      if (sweep) [crown.gem, crown.gem2].forEach(function (mesh) {
        var a = mesh.geometry.attributes.position, seen = {};
        for (var i = 0; i < a.count; i++) {
          var px = a.getX(i), py = a.getY(i), pz = a.getZ(i), rho = Math.sqrt(px * px + pz * pz) / Math.cos(Math.PI / 16), key = Math.round(rho) + ':' + Math.round(py);
          if (seen[key]) continue;
          seen[key] = 1;
          for (var q = 0; q < 16; q++) sweep.push(new T.Vector3(Math.cos(q * Math.PI / 8) * rho, py, Math.sin(q * Math.PI / 8) * rho).applyMatrix4(mesh.matrixWorld));
        }
      });
      crown.grp.position.copy(pos); crown.upper.position.y = upY; crown.lower.position.y = loY;
      objects.forEach(function (obj, i) { obj.scale.y = scales[i]; });
      crown.grp.updateWorldMatrix(true, true);
      return sphere;
    }
    function releaseGemPresentation() {
      nodes.forEach(function (n) {
        if (!n._gemPresentation) return;
        n.render = n._gemPresentation.render;
        n.g.visible = n.render;
        n.el.style.visibility = n._gemPresentation.visibility;
        n._gemPresentation = null;
      });
    }
    function maskGemPresentation() {
      if (!gemStageOn) return;
      nodes.forEach(function (n) {
        if (n.kind === 'attr' || n.kind === 'meta' || n.key === 'c:' + focusName) return;
        if (!n._gemPresentation) n._gemPresentation = { render: n.render, visibility: n.el.style.visibility };
        n.render = false; n.g.visible = false;
        n.el.style.visibility = 'hidden'; n.el.classList.remove('on');
      });
      labels.markLodDirty();
    }
    /* v90 F3 · 主舞台取景参数：包围球余量 · 顶面观察方向 · 轴签预留。
       两条约束取更远者：① 整座仪器的自旋不变包围球落在舞台矩形内（任意轨道姿态不出画）；
       ② 两块晶体的扫掠包围落在「扣掉轴签栏位 / 签带」的矩形内（签不压晶体主体）。
       宽屏（> 480）左右各留一栏给轴签；窄屏上下各留一条两行签带，左右只留 16px 页边。 */
    function gemHullDistance(points, target, dir, fit, vw, vh, vf) {
      var right = new T.Vector3().crossVectors(camera.up, dir).normalize(), up = new T.Vector3().crossVectors(dir, right).normalize();
      var tx = vf * camera.aspect * fit.width / vw, ty = vf * fit.height / vh, d = 0, q = new T.Vector3();
      points.forEach(function (p) {
        q.copy(p).sub(target);
        var depth = q.dot(dir);
        d = Math.max(d, depth + Math.abs(q.dot(right)) / tx, depth + Math.abs(q.dot(up)) / ty);
      });
      return d * 1.02;
    }
    /* 顶面观察方向按「相对晶冠赤道面的仰角」给：旧机位约 40° 俯视，下锥锥尖整个藏在台身背后，
       晶体读成一只八棱盒；压到约 22° 时锥尖露出，上冠 / 腰棱 / 长锥连成一颗宝石的剪影。 */
    function gemViewDir(elev, az) {
      var ax = new T.Vector3(0, Math.cos(CR_TILT), Math.sin(CR_TILT));
      var h = new T.Vector3(Math.sin(az), -Math.sin(CR_TILT) * Math.cos(az), Math.cos(CR_TILT) * Math.cos(az));
      return h.multiplyScalar(Math.cos(elev)).addScaledVector(ax, Math.sin(elev)).normalize();
    }
    var GEM_FIT_MARGIN = 1.04, GEM_TOP_DIR = gemViewDir(22 * Math.PI / 180, 14 * Math.PI / 180);
    function gemFitRect(area) {
      var vw = core.getW();
      if (vw <= 480) {
        var band = Math.round(Math.min(104, area.height * 0.25));
        var left = Math.max(area.left, 16), right = Math.min(area.left + area.width, vw - 16);
        return { left: left, top: area.top + band, width: Math.max(80, right - left), height: Math.max(120, area.height - band * 2) };
      }
      var side = Math.round(clamp(vw * 0.13, 136, 200)), width = Math.max(160, area.width - side * 2);
      return { left: area.left + (area.width - width) / 2, top: area.top, width: width, height: area.height };
    }
    /* Fit the actual dual crystal, not the character's old desktop offset.
       UI passes an unobstructed pixel rectangle; geometry stays in this layer. */
    S.previewCrown = function (area) {
      if (!area) {
        if (previewCamera && mode === 'focus') {
          restoreCameraView(previewCamera.view);
          camera.quaternion.copy(previewCamera.rotation);
          flyTo(previewCamera.pos, previewCamera.target, 0.3);
        }
        previewCamera = null;
        return;
      }
      if (mode !== 'focus' || !crown) return;
      /* 主舞台的舞台矩形只有一个真相（gemStage 登记的 area）：翻面等二次调用不得换一块矩形取景 */
      if (gemStageOn && gemStageArea) area = gemStageArea;
      if (!previewCamera) previewCamera = { pos: camera.position.clone(), target: controls.target.clone(), rotation: camera.quaternion.clone(), view: captureCameraView() };
      var sweep = gemStageOn ? [] : null;
      var sphere = gemStageOn ? crownDestinationSphere(sweep) : crownBox().getBoundingSphere(new T.Sphere());
      var vw = core.getW(), vh = core.getH(), vf = Math.tan(camera.fov * Math.PI / 360);
      var half = Math.min(vf * area.height / vh, vf * camera.aspect * area.width / vw);
      var distance = sphere.radius * (gemStageOn ? GEM_FIT_MARGIN : 1.16) * Math.sqrt(1 + 1 / Math.max(0.01, half * half));
      var dir = face === 'under' ? new T.Vector3(110, -210, 660) : gemStageOn ? GEM_TOP_DIR.clone() : FOCUS_CAM.clone().sub(FOCUS_TGT);
      dir.normalize();
      /* v90 F3 · 主舞台取景（旧版 1.16 倍余量、不留签位 → 晶体约占舞台 1/3，下锥签无处可放） */
      if (gemStageOn && sweep.length) distance = Math.max(distance, gemHullDistance(sweep, sphere.center, dir, gemFitRect(area), vw, vh, vf));
      /* Lens shift moves the projection, not the orbit pivot. The old shifted
         target made the crystal orbit an empty point and leave the viewport. */
      camera.setViewOffset(vw, vh, vw / 2 - area.left - area.width / 2, vh / 2 - area.top - area.height / 2, vw, vh);
      var target = sphere.center.clone();
      var quiet = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      flyTo(target.clone().addScaledVector(dir, distance), target, quiet ? 0.001 : 0.6);
    };
    /* Main-stage adapter. Repeated calls update real selection/peer/chapter
       state without registering another render loop or resetting the camera. */
    S.gemStage = function (options) {
      options = options || {};
      if (options.on === false) {
        var previous = gemStageSaved;
        releaseGemPresentation();
        if (previous) restoreCameraView(previous.view);
        else if (previewCamera) restoreCameraView(previewCamera.view);
        gemStageOn = false; gemStageSaved = null; gemStageArea = null;
        gemPeer = null; gemChapter = null; previewCamera = null;
        if (previous && options.restore !== false) {
          /* 同一角色回到聚焦态：focus() 里的 buildCrown 走停放复用（同一组分值 → 不再白建一座，只把入场时钟归零），
             关罗盘的观感与旧版逐帧一致——晶冠当即收起、八维星收回星体、虹膜环点一下（Q5.5 试过让晶冠平滑淡出：巨晶压在回拉的星座上，更脏，已撤） */
          if (previous.name) focus(previous.name); else if (mode === 'focus') toAtlas();
          stage.selectChapter(previous.chapter, true);
          if (mode === 'focus') face = previous.face;
          group.position.copy(previous.groupPosition);
          /* 晶体舞台期间视口 / 留边可能变了（窄屏 ↔ 宽屏）：星座的横移按此刻的留边重算，别落回进场前的旧值 */
          groupXTo = mode === 'atlas' ? atlasShift() : previous.groupX;
          flyTo(previous.pos, previous.target, calm ? 0.001 : 0.35);
          camera.quaternion.copy(previous.rotation);
        } else if (crown && crown.model) {
          crown.model.peer = null; updateGemOverlays();
        }
        syncGemLegend(); syncGemDimensionLabels();
        return S.gemStageState();
      }
      var name = options.name || focusName;
      if (!name || !nodeByKey['c:' + name]) return { on: false, reason: 'character-required' };
      var wasOn = gemStageOn, beforeName = focusName, beforeChapter = gemChapter;
      if (!wasOn) {
        gemStageSaved = { name: focusName, face: face, chapter: stage.chapSel(), groupX: groupXTo, groupPosition: group.position.clone(),
          pos: camera.position.clone(), target: controls.target.clone(), rotation: camera.quaternion.clone(), view: captureCameraView() };
      }
      gemStageOn = true;
      groupXTo = 0; group.position.x = 0;
      var peerChanged = Object.prototype.hasOwnProperty.call(options, 'peer') && gemPeer !== (options.peer || null);
      if (Object.prototype.hasOwnProperty.call(options, 'peer')) gemPeer = options.peer && options.peer !== name && nodeByKey['c:' + options.peer] ? options.peer : null;
      if (gemPeer === name) gemPeer = null;
      if (options.scope === 'book' || options.scope === 'camp') gemScope = options.scope;
      if (Object.prototype.hasOwnProperty.call(options, 'chapter')) {
        gemChapter = options.chapter == null ? null : options.chapter;
        var chs = (bookStats && bookStats.chapters) || [];
        var ch = typeof gemChapter === 'number' ? chs[gemChapter] : gemChapter;
        stage.selectChapter(ch ? stage.bucketOf(ch) : null, true);
      }
      if (mode !== 'focus' || focusName !== name || !crown) focus(name);
      else if (peerChanged || options.scope || beforeChapter !== gemChapter) {
        var oldValues = focusGem ? focusGem.attr.map(function (d) { return d.score; }).join('|') : '';
        focusGem = buildGemModel(nodeByKey['c:' + name].data, gemPeer);
        var newValues = focusGem ? focusGem.attr.map(function (d) { return d.score; }).join('|') : '';
        if (newValues !== oldValues) {
          var savedMotion = { born: crown.born, ang: crown.ang, vel: crown.vel };
          buildCrown(nodeByKey['c:' + name], nodeByKey['c:' + name].data);
          crown.born = savedMotion.born; crown.ang = savedMotion.ang; crown.vel = savedMotion.vel;
          syncGemDimensionLabels(); updateCrown(0);
        } else { crown.model = focusGem; updateGemOverlays(); }
      }
      var next = options.area || gemStageArea || { left: safe.left + 24, top: safe.top + 34, width: Math.max(160, core.getW() - safe.left - safe.right - 48), height: Math.max(180, core.getH() - safe.top - safe.bottom - 68) };
      var areaChanged = !gemStageArea || ['left', 'top', 'width', 'height'].some(function (key) { return gemStageArea[key] !== next[key]; });
      gemStageArea = { left: next.left, top: next.top, width: next.width, height: next.height };
      if (!wasOn || beforeName !== name || areaChanged || !previewCamera) {
        S.previewCrown(gemStageArea);
      }
      maskGemPresentation();
      syncGemDimensionLabels(); syncGemLegend();
      dirty = true; lodDirty = true; labels.markLodDirty();
      return S.gemStageState();
    };
    S.gemStageState = function () {
      var state = crown && crown.model ? crown.model.stage : null;
      return { on: gemStageOn, name: focusName, peer: crown && crown.model && crown.model.peer ? crown.model.peer.name : null,
        chapter: gemChapter, scope: gemScope, area: gemStageArea, stageFacts: !!(state && state.id), chapterChangesScores: !!(state && state.hasQuantified),
        state: state, narrativeScope: 'book' };
    };
    S.gemModel = function () { return crown ? crown.model : null; };
    /* v90 F3（F6 host P1）· WebGL 泛光公开开关：k ∈ [0,1] 乘在当前 bloomBase 上（大图 0.30 / 小图 0.48），
       setGraph 重设 bloomBase 时保留 glowK。读图模式「关光」→ setGlow(0)，退出 → setGlow(1)。 */
    function glowPass() { return (core.getBloom && core.getBloom()) || core.bloom || null; }
    function glowBase() { return bloomBase; }
    S.setGlow = function (k) { glowK = clamp(+k || 0, 0, 1); var p = glowPass(); if (p) p.strength = glowBase() * glowK * densityBloom; dirty = true; return glowK; };
    S.glow = function () { return glowK; };
    /* v90 F3（F6 host P2）· 单条关系聚焦：只点亮 a↔b 之间（给了 kind 则只点该类型）的关系纤维，其余经
       既有 setFiberHl 退暗；focusRelation(null) 按当前模式恢复（聚焦人物 / 信息图层 / 章节 / 阵营 / 默认）。
       没有匹配纤维时不改画面、返回 0，调用方可自行兜底。返回点亮的纤维数。 */
    var relFocus = null;
    function relFiberFn(a, b, kind) {
      return function (f) {
        if (f.kind !== 'rel' || !f.a || !f.b) return -1;
        var hit = (f.a.key === 'c:' + a && f.b.key === 'c:' + b) || (f.a.key === 'c:' + b && f.b.key === 'c:' + a);
        return hit && (!kind || f.relKind === kind) ? 1 : -1;
      };
    }
    function restoreFiberHl() {
      if (mode === 'focus' && focusName && nodeByKey['c:' + focusName]) {
        var cn = nodeByKey['c:' + focusName];
        setFiberHl(function (f) { if (f.kind === 'guide') return -2; if (f.kind === 'attr' && (f.a === cn || f.b === cn)) return -2; return (f.a === cn || f.b === cn) ? 1 : -1; });
      } else if (infoLayer !== 'overview') S.setInfoLayer(infoLayer);
      else if (stage.chapSel && stage.chapSel()) stage.selectChapter(stage.chapSel(), true);
      else setFiberHl(campSel ? campFiberFn(campSel) : function () { return 0; });
      dirty = true;
    }
    S.focusRelation = function (a, b, kind) {
      if (a == null || b == null || !graph) { if (relFocus) { relFocus = null; restoreFiberHl(); } return 0; }
      a = String(a); b = String(b); kind = kind == null || kind === '' ? null : String(kind);
      var fn = relFiberFn(a, b, kind), lit = 0;
      for (var i = 0; i < fibers.length; i++) if (fn(fibers[i]) > 0) lit++;
      if (!lit) return 0;
      relFocus = { a: a, b: b, kind: kind, lit: lit };
      setFiberHl(fn); dirty = true;
      return lit;
    };
    /** 探针：从真实上传的 hl 顶点属性读出哪些纤维被点亮（不是回放 focusRelation 的记账） */
    S.relationFocus = function () {
      var mesh = core.getFiberMesh ? core.getFiberMesh() : null, hl = mesh && mesh.geometry.attributes.hl, out = { focus: relFocus, lit: [], dimmed: 0, total: fibers.length };
      if (!hl || !fibers.length) return out;
      var stride = hl.array.length / fibers.length;
      for (var i = 0; i < fibers.length; i++) {
        var f = fibers[i];
        if (hl.array[i * stride] > 0.5) out.lit.push({ a: f.a && f.a.key, b: f.b && f.b.key, kind: f.kind, relKind: f.relKind || null }); else out.dimmed++;
      }
      return out;
    };
    /* v90 F3 · 双晶主舞台图例（标签层内、舞台左下角）：只在该人有缺档、画出参考轮廓时出现，
       明说点线不是数据。标签排版把它当作禁区（.cl-gem-legend），轴签不会压上去。 */
    var gemLegendEl = null;
    function syncGemLegend() {
      var show = !!(gemStageOn && gemStageArea && crown && !crown.dying && (crown.refTop || crown.refBottom));
      if (!show) { if (gemLegendEl && !gemLegendEl.hidden) { gemLegendEl.hidden = true; if (labels.markLodDirty) labels.markLodDirty(); } return; }
      if (!gemLegendEl) {
        gemLegendEl = document.createElement('div');
        gemLegendEl.className = 'cl-gem-legend';
        gemLegendEl.setAttribute('role', 'note');
        gemLegendEl.innerHTML = '<i class="cl-gem-legend__dots" aria-hidden="true"></i><span class="cl-gem-legend__txt">点线 = 未建档参考轮廓（非数据）</span>';
        labelLayer.appendChild(gemLegendEl);
      }
      var wasHidden = gemLegendEl.hidden;
      gemLegendEl.hidden = false;
      var x = Math.max(12, gemStageArea.left + 8), y = gemStageArea.top + gemStageArea.height - 24;
      gemLegendEl.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
      if (wasHidden && labels.markLodDirty) labels.markLodDirty();
    }
    S.gemLegend = function () {
      if (!gemLegendEl || gemLegendEl.hidden) return { on: false };
      var r = gemLegendEl.getBoundingClientRect();
      return { on: true, text: gemLegendEl.textContent, box: { x: r.left, y: r.top, w: r.width, h: r.height } };
    };
    /* v90 F3 · 桌面主舞台（视口 > 900）同屏两面 16 签：当前观察面满格、另一面略暗；≤900 只留当前面。 */
    function gemDualLabels() { return !!(gemStageOn && core.getW() > 900); }
    /* 轴签副行：已知 = 「英文 值」（值单独成 span，紧凑行只露「名 值」）；未知统一「英文 — 待建档」 */
    function gemAxisSub(el, en, d) {
      var ls = el.children[1];
      if (!d.known) { ls.textContent = en + ' — 待建档'; return; }
      ls.textContent = '';
      var e = document.createElement('span'); e.className = 'le'; e.textContent = en;
      var v = document.createElement('b'); v.className = 'lv'; v.textContent = String(Math.round(d.score));
      ls.appendChild(e); ls.appendChild(document.createTextNode(' ')); ls.appendChild(v);
    }
    function syncGemDimensionLabels() {
      if (!focusGem || mode !== 'focus') return;
      var dual = gemDualLabels();
      focusGem.attr.forEach(function (d, i) {
        var n = nodeByKey['a:' + d.key]; if (!n) return;
        n.sizeTo = d.known ? 7 + d.score * 0.11 : 5;
        n.alphaTo = face === 'under' ? (dual ? 0.66 : 0.14) : !d.known ? 0.60 : d.conf === 'low' ? 0.62 : 0.95;
        n.el.setAttribute('data-known', d.known ? 'true' : 'false');
        n.el.setAttribute('data-confidence', d.conf);
        n.el.setAttribute('aria-label', d.key + (d.known ? ' ' + d.score : ' 待建档') + '，查看依据');
        if (d.known) n.el.setAttribute('data-score', String(d.score)); else n.el.removeAttribute('data-score');
        gemAxisSub(n.el, ATTR_EN[i], d);
        var rank = d.known && d.rank != null ? '#' + d.rank + ' / ' + d.n : '';
        n.el.children[2].textContent = rank + (d.known && focusGem.stage && focusGem.stage.hasQuantified && !focusGem.stage.verified ? ' · 阶段未核验' : '');
        n.sub = n.el.children[1].textContent;
        n._box = null; n._gemFmt = null;
      });
      (focusGem.meta || []).forEach(function (d, i) {
        var n = nodeByKey['m:' + d.key]; if (!n) return;
        n.alphaTo = face === 'under' ? 1 : (dual ? 0.66 : 0.30);
        n.el.setAttribute('data-known', d.known ? 'true' : 'false');
        n.el.setAttribute('aria-label', d.key + (d.known ? ' ' + d.score : ' 待建档') + '，全书叙事位置');
        if (d.known) n.el.setAttribute('data-score', String(d.score)); else n.el.removeAttribute('data-score');
        gemAxisSub(n.el, META_EN[i], d);
        n.el.children[2].textContent = d.known && d.rank != null ? '#' + d.rank + ' / ' + d.n + ' · 全书' : '';
        n.sub = n.el.children[1].textContent;
        n._box = null; n._gemFmt = null;
      });
      labels.markLodDirty();
    }
    S.crownScreenBounds = function () {
      if (!crown) return null;
      camera.updateMatrixWorld(true);
      var left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity, clipped = 0, vertices = 0;
      eachCrownVertex(function (p) {
        p.project(camera); vertices++;
        if (p.z < -1 || p.z > 1) clipped++;
        var x = (p.x + 1) * core.getW() / 2, y = (1 - p.y) * core.getH() / 2;
        left = Math.min(left, x); right = Math.max(right, x); top = Math.min(top, y); bottom = Math.max(bottom, y);
      });
      return { left: left, right: right, top: top, bottom: bottom, clipped: clipped, vertices: vertices };
    };
    /* Q5.5 · 着色器预热（C）：主场景画进线性编码的多重采样目标，程序缓存键里带着输出编码；
       空渲染目标下 compile 得到的是 sRGB 变体，渲染时一个也用不上。这里在 1×1 的线性目标下编译，编的就是真正要用的那一份 */
    function compileWarm(sc) {
      var prev = renderer.getRenderTarget(), rt = new T.WebGLRenderTarget(1, 1);
      renderer.setRenderTarget(rt);
      try { renderer.compile(sc, camera); } finally { renderer.setRenderTarget(prev); rt.dispose(); }
    }
    S.compileWarm = function (sc) { compileWarm(sc || scene); return renderer.info.programs.length; };
    /* 读取幕「预编译着色器」那一步：造一座不上屏的晶冠（默认重要度最高的人）放进临时场景编译，大奉首开罗盘少链接 13 个程序（~25 ms）；
       编完停进停放槽——先点开的正是这个人就原样挂回，一个几何也不用再造 */
    S.prewarmCrown = function (name) {
      if (!graph || crown || crownParked) return null;
      var cn = name ? nodeByKey['c:' + name] : null;
      if (!cn) nodes.forEach(function (n) { if (n.kind === 'char' && n.data && (!cn || (n.data.importance || 0) > (cn.data.importance || 0))) cn = n; });
      if (!cn || !cn.data) return null;
      var cr = buildCrown(cn, cn.data, true), tmp = new T.Scene();
      tmp.add(cr.grp);
      var ref = ghostContour([50, 50, 50, 50, 50, 50, 50, 50], false, 0x668cac, cr.upper);   /* 对照 / 缺档虚线同一张虚线材质，一并编进 */
      /* 聚焦态信息脊（scene-core buildSpines，进罗盘下一帧建）：同一对着色器、同样的材质开关 → 同一个程序 */
      var spine = Mats.SPINE_VS && Mats.SPINE_FS ? new T.Mesh(new T.BufferGeometry(), new T.ShaderMaterial({ vertexShader: Mats.SPINE_VS, fragmentShader: Mats.SPINE_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
        uniforms: { uRes: { value: new T.Vector2(1, 1) }, uWidth: { value: 1 }, uTime: { value: 0 }, uHead: { value: -1 }, uD0: { value: 900 }, uOn: { value: 0 }, uAmp: { value: 1 } } })) : null;
      if (spine) tmp.add(spine);
      try { compileWarm(tmp); } finally {
        cr.upper.remove(ref); ref.geometry.dispose();
        tmp.remove(cr.grp);
        if (spine) {
          tmp.remove(spine);
          /* The temporary spine exists only to link its shader program into
             the compile pass. Removing it from the temp scene is not enough:
             without disposing its empty geometry/material every prewarm
             round adds one renderer geometry to the long-run ledger. */
          if (spine.geometry) spine.geometry.dispose();
          if (spine.material) spine.material.dispose();
        }
      }
      crownParked = { c: cr, sig: cr.sig };
      return cn.key.slice(2);
    };
    S.setFace = function (f) {
      f = f === 'under' ? 'under' : 'top';
      if (mode !== 'focus') { face = 'top'; return face; }
      if (f === face) return face;
      face = f;
      nodes.forEach(function (n) {
        if (n.kind === 'attr') n.alphaTo = f === 'under' ? 0.14 : 0.95;
        else if (n.kind === 'meta') n.alphaTo = f === 'under' ? 1 : 0.30;
      });
      if (f === 'under') flyTo(new T.Vector3(110, -330, 700), new T.Vector3(0, -120, 40), 1.6);
      else flyTo(FOCUS_CAM.clone(), FOCUS_TGT.clone(), 1.6);
      if (gemStageOn && gemStageArea) S.previewCrown(gemStageArea);
      syncGemDimensionLabels();
      labels.markLodDirty(); lodDirty = true; dirty = true; fire('face', face);
      return face;
    };
    S.face = function () { return face; };
    /** 悬停底面某一轴：高亮该轴晶面与支柱并暂停自旋 */
    S.hoverMeta = function (key) {
      var idx = key ? META_KEYS.indexOf(key) : -1;
      crownHl2 = idx; crownHold = idx >= 0 ? 1 : (crownHl >= 0 ? 1 : 0);
      if (idx >= 0) { var n = nodeByKey['m:' + key]; if (n) n.flash = Math.max(n.flash || 0, 0.55); }
      return idx;
    };
    /** 底面八维（叙事位置层）：按角色名计算，含 0..1 值、整数分、依据副行 */
    S.metaOf = sceneMetaOf;
    S.crown = function () {
      if (!crown) return { on: false };
      return { on: true, verts: crown.verts.length, tris: crown.gem.geometry.attributes.position.count / 3, lines: crown.lines.geometry.attributes.position.count / 2,
        spin: +crown.ang.toFixed(3), tilt: +crown.grp.rotation.x.toFixed(2), hl: crownHl, avg: crown.scored ? +crown.avg.toFixed(2) : null, gemOn: +crown.gem.material.uniforms.uOn.value.toFixed(2),
        scores: crown.scores.map(function (x) { return x === null ? null : Math.round(x * 100); }), known: crown.known.slice(0), known2: crown.known2.slice(0),
        unknown: crown.unknownTop.userData.unknownCount, unknown2: crown.unknownBottom.userData.unknownCount,
        modelSource: crown.model ? 'CLGemModel' : 'legacy', stage: gemStageOn, peer: crown.model && crown.model.peer ? crown.model.peer.name : null,
        tick: crown.tickK, hourIdx: dialIndex(crown), segs: crown.segN, face: face, clock: crown.clockText, wallSec: crown.tickK, story: crown.storyIdx, storyAuto: !dialLocked(), storyN: crown.mineIdx.length, dialOn: +crown.dial.material.uniforms.uOn.value.toFixed(2), floatY: +(crown.grp.position.y - (crown.host ? crown.host.pos.y - CR_DROP : 0)).toFixed(2),
        verts2: crown.verts2.length, tris2: crown.gem2.geometry.attributes.position.count / 3, lines2: crown.lines2.geometry.attributes.position.count / 2,
        gem2On: +crown.gem2.material.uniforms.uOn.value.toFixed(2), depth2: +(-crown.nadir).toFixed(1), topH: CR_H, hl2: crownHl2, scores2: crown.scores2.map(function (x) { return x === null ? null : Math.round(x * 100); }),
        // v24.4 · 相对运动探针：sep = 相位（-1…1）· neck = 当帧颈距 · upY / loY = 两谱各自位移 · spinRel = 相对角速度倍数
        sep: +crown.sep.toFixed(3), tension: +crown.tension.toFixed(3), upY: +crown.upper.position.y.toFixed(2), loY: +crown.lower.position.y.toFixed(2),
        neck: +(CR_GAP + crown.upper.position.y - CR_H * 0.22 - crown.lower.position.y).toFixed(2), spinRel: +(0.35 + CR_COUNTER).toFixed(2),
        upRotY: +crown.upper.rotation.y.toFixed(3), loRotY: +crown.lower.rotation.y.toFixed(3), bridgeOn: +crown.bridge.material.uniforms.uOn.value.toFixed(2),
        grow: +crown.lines.material.uniforms.uGrow.value.toFixed(2), scanY: +crown.scan.position.y.toFixed(1), dying: !!crown.dying, motes: crown.motes.geometry.attributes.position.count };
    };
    /* Read-only cache ownership. IDs/topology are diagnostics, never leak-baseline keys. */
    S.crownCacheInfo = function (includeIds) {
      function describe(cr) {
        if (!cr) return null;
        var seen = {}, ids = [], topology = [], meshes = 0, shared = 0;
        cr.grp.traverse(function (o) {
          if (!o.geometry) return;
          meshes++;
          var geo = o.geometry, key = geo.uuid || String(geo.id), p = geo.attributes && geo.attributes.position;
          if (seen[key]) { shared++; return; }
          seen[key] = true; ids.push(geo.id);
          topology.push({ name: o.name || '', type: o.type || '', vertices: p ? p.count : 0,
            indices: geo.index ? geo.index.count : 0, attributes: Object.keys(geo.attributes || {}).sort() });
        });
        var out = { semantic: { signature: cr.sig, name: cr.host && cr.host.key ? cr.host.key.slice(2) : null,
          peer: cr.model && cr.model.peer ? cr.model.peer.name : null, prewarmOnly: !!cr._prewarmOnly },
          attached: !!cr.grp.parent, dying: !!cr.dying, geometryCount: ids.length,
          geometryUses: meshes, sharedGeometryUses: shared, topology: topology,
          ownedTextureCount: cr.segmentTexture ? 1 : 0 };
        if (includeIds) { out.geometryIds = ids; out.ownedTextureIds = cr.segmentTexture ? [cr.segmentTexture.id] : []; }
        return out;
      }
      var a = describe(crown), p = describe(crownParked && crownParked.c);
      return { active: a, parked: p, slots: (a ? 1 : 0) + (p ? 1 : 0), limit: 2,
        stage: gemStageOn, sceneMode: mode, chapter: gemChapter, scope: gemScope,
        memory: { g: renderer.info.memory.geometries, t: renderer.info.memory.textures },
        note: 'prewarmOnly means never activated after compile; false is not evidence of a full GPU render' };
    };
    S.nodeOf = function (key) { return nodeByKey[key] || null; };

    // ---------------------------------------------------------- hover
    function setHover(name) {
      if (name === hoverName) return;
      var oldHover = hoverName;
      hoverName = name; lodDirty = true;
      if (name) { var hn = nodeByKey['c:' + name]; if (hn) { hn.render = true; hn.g.visible = true; attachLabel(hn); } }
      if (!name && oldHover) {
        var oh = nodeByKey['c:' + oldHover];
        if (oh && nCharCount > 1600 && oh.tier >= 4 && !tailShow && !pinned[oldHover] && !(searchSet && searchSet[oldHover]) && oldHover !== focusName) { oh.render = false; oh.g.visible = false; detachLabel(oh); }
      }
      nodes.forEach(function (n) { n.el.classList.toggle('hover', !!name && n.kind === 'char' && n.key === 'c:' + name); });
      if (mode !== 'atlas') return;
      if (!name) {
        S._pilgrimage = null;
        if (chapSel) S.selectChapter(chapSel, true);
        else if (campSel) setFiberHl(campFiberFn(campSel));
        else setFiberHl(function () { return 0; });
      } else {
        // C5 · 信号巡礼（BFS 全链路按跳数衰减点亮：1跳 100%、2跳 45%、3跳 18%）
        var pilgrimageDist = {};
        if (graph && graph.relations) {
          var adj = buildAdj();
          var maxDepth = layoutInfo && layoutInfo.mode === 'sky' ? 1 : 3;
          var q = [{ name: name, dist: 0 }];
          pilgrimageDist[name] = 0;
          while (q.length > 0) {
            var curr = q.shift();
            if (curr.dist >= maxDepth) continue;
            var mine = adj[curr.name];
            if (!mine) continue;
            for (var ri = 0; ri < mine.length; ri++) {
              var neighbor = mine[ri];
              if (neighbor && pilgrimageDist[neighbor] === undefined) {
                pilgrimageDist[neighbor] = curr.dist + 1;
                q.push({ name: neighbor, dist: curr.dist + 1 });
              }
            }
          }
        }
        S._pilgrimage = pilgrimageDist;
        var cn = nodeByKey['c:' + name];
        setFiberHl(function (f) {
          var an = f.a && f.a.key && f.a.key.slice(2);
          var bn = f.b && f.b.key && f.b.key.slice(2);
          var da = pilgrimageDist[an], db = pilgrimageDist[bn];
          if (da !== undefined && db !== undefined) {
            var maxD = Math.max(da, db);
            return maxD === 1 ? (infoLayer === 'relations' && f.kind === 'rel' ? 2 : 1.0) : maxDepth > 1 && maxD === 2 ? 0.45 : maxDepth > 2 && maxD === 3 ? 0.18 : -1;   // v90 F4
          }
          return (f.a === cn || f.b === cn) ? 1 : -1;
        });
      }
    }
    S.setHover = setHover;
    S.hoverName = function () { return hoverName || null; };
    S.labelRevision = function () { return labelRevision; };   // 节点/角色文案版本，供读层按真实变化同步ARIA
    S.setLabelExtra = function (key, html) { var n = nodeByKey[key]; if (n) { n.el.children[2].innerHTML = html || ''; n._box = null; if (n.kind === 'char') labelRevision++; } };
    S.setLabelSub = function (key, text) { var n = nodeByKey[key]; if (n) { n.sub = text || ''; n.el.children[1].textContent = n.sub; n._box = null; if (n.kind === 'char') labelRevision++; lodDirty = true; } };

    var isDraggingWorld = false, dragStartX = 0, dragStartY = 0;
    var dragMoved = false, dragSuppressClick = false;

    function isInteractiveTarget(target) {
      if (!target) return false;
      var t = target;
      if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable) return true;
      if (t.closest && t.closest('button, a, input, select, textarea, [data-ev], [data-name], [data-line-id], .cl-o3-legend-item, .cl-orbit__card, .seg button, .btn')) {
        return true;
      }
      return false;
    }

    window.addEventListener('pointerdown', function (e) {
      dragMoved = false;
      if (isInteractiveTarget(e.target)) return;
      if (e.target !== canvas && e.target !== labelLayer && !(e.target.closest && e.target.closest('#labels'))) return;
      /* OrbitControls is the sole camera gesture owner. This observer only
         distinguishes clicks from drags, for every mouse button and touch. */
      if (e.button >= 0 || e.pointerType === 'touch') {
        isDraggingWorld = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
      }
    }, { passive: true });

    window.addEventListener('pointermove', function (e) {
      if (!isDraggingWorld) return;
      if (!dragMoved && Math.hypot(e.clientX - dragStartX, e.clientY - dragStartY) > 5) {
        dragMoved = true;
        dragSuppressClick = true;
      }
    }, { passive: true });

    function onPointerEnd(e) {
      if (isDraggingWorld) {
        isDraggingWorld = false;
        if (dragMoved) {
          setTimeout(function () { dragSuppressClick = false; }, 80);
        }
        dragMoved = false;
      }
    }
    window.addEventListener('pointerup', onPointerEnd, { passive: true });
    window.addEventListener('pointercancel', onPointerEnd, { passive: true });

    window.addEventListener('click', function (e) {
      if (dragSuppressClick || dragMoved) {
        e.stopImmediatePropagation();
        e.preventDefault();
      }
    }, true);

    window.addEventListener('selectstart', function (e) {
      var t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable || (t.closest && t.closest('.selectable')))) return;
      e.preventDefault();
    });

    /* v71 W4 修复：9/17 拆包把星场拾取交互弄丢了——core.pick 存在但没有任何指针事件接它，
     * 于是「悬停星点出 peek + 信号巡礼」「点星聚焦」「点空处取消」全部失效。
     * 这里恢复：悬停 25Hz 节流射线拾取 + pointerup 点选（拖动手势豁免）。
     * 事件语义与 app.js 的监听对齐：char → 'hover'/'select'；其它节点 → 'hoverNode'/'selectNode'；空处 → 'background'。 */
    var pickLastKey = null, pickLastMove = 0;
    function pickEventTargetOk(t) {
      if (!t) return false;
      if (document.body.classList.contains('atlas-workspace') && document.body.getAttribute('data-atlas-view') === 'annulus') return false;
      if (t === canvas || t === labelLayer) return true;
      if (t.closest && t.closest('#labels')) return true;   // 标签层空白处视为星场
      return false;
    }
    window.addEventListener('pointermove', function (e) {
      if (isDraggingWorld) return;
      if (isInteractiveTarget(e.target) || !pickEventTargetOk(e.target)) {
        if (pickLastKey) { pickLastKey = null; setHover(null); fire('hover', null); fire('hoverNode', null); }
        return;
      }
      var now = performance.now();
      if (now - pickLastMove < 40) return;
      pickLastMove = now;
      var n = core.pick(e.clientX, e.clientY);
      var key = n ? n.key : null;
      if (key === pickLastKey) return;
      pickLastKey = key;
      if (n && n.kind === 'char') { setHover(n.key.slice(2)); fire('hover', { name: n.key.slice(2) }); }
      else { if (hoverName) setHover(null); fire('hover', null); fire('hoverNode', n); }
    }, { passive: true });
    window.addEventListener('pointerup', function (e) {
      if (dragSuppressClick || dragMoved) return;
      if (e.button !== 0 && e.pointerType !== 'touch') return;
      if (isInteractiveTarget(e.target) || !pickEventTargetOk(e.target)) return;
      var n = core.pick(e.clientX, e.clientY);
      if (!n) { fire('background'); return; }
      if (n.kind === 'char') fire('select', { name: n.key.slice(2) });
      else fire('selectNode', n);
    }, { passive: true });

    /* ── Q1.3 · 牵引位移同源（tughost）──────────────────────────────────────
       CLSkyTug 每帧积分后调 S.setTug(map)：map = { 'c:名': {x, y, z} }（S.group 局部位移；普通对象或 Vector3，只读 x / y / z），睡眠后调一次 null。
       位移在节点循环（入场插值 / 漂移 / 星图插值）之后叠进 n.g.position 与 n.pos：星点（sky-stars）、星名（LOD 标签读 n.g.matrixWorld）、
       星座线与关系纤维（读 n.g.position）、命中（S.pick 的射线打 n.g 下的精灵）于是同一帧、同一个数。星云 / 深空不读逐帧节点位置，不跟。
       只在全景态（mode = atlas）生效；聚焦（罗盘）态一律忽略、就地归位。
       开销：无位移时帧钩子里一次判空（不遍历节点、不上传）；有位移时只动 map 里那几十颗，S.tugDirty() 给出本帧位移变了的星（含刚归零的），
       束丝等下游按它增量重算；S.tugInfo().uploads = 这些层本帧实际上传的字节（by 分层列出）。 */
    var tugMap = null, tugOn = [], tugDirtyK = [], tugGraph = null, tugSeq = 0, tugLive = false, tugMax = 0, tugNotes = {}, tugM3 = new T.Matrix3();
    function tugApply() {
      var prev = tugOn, next = [], k, o, n, x, y, z, i, p, d2, mx = 0;
      var sf = core.getStarField(), sfA = sf ? sf.geometry.attributes.position.array : null;
      tugDirtyK.length = 0; tugSeq++; tugNotes = {};
      if (graph !== tugGraph) { prev = []; tugGraph = graph; }   /* 换书：旧节点已随场景销毁，无从归位 */
      if (tugMap && mode === 'atlas') {
        for (k in tugMap) {
          if (!Object.prototype.hasOwnProperty.call(tugMap, k)) continue;
          o = tugMap[k]; n = o ? nodeByKey[k] : null;
          if (!n || !n.render) continue;
          x = +o.x || 0; y = +o.y || 0; z = +o.z || 0;
          if (!x && !y && !z) continue;
          if (!n.tugO) { n.tugO = new T.Vector3(); n.tugH = new T.Vector3(); n.tugS = -1; }
          if (n.tugS !== tugSeq - 1 || n.tugO.x !== x || n.tugO.y !== y || n.tugO.z !== z) tugDirtyK.push(k);
          n.tugO.set(x, y, z); n.tugS = tugSeq; n.tugH.copy(n.g.position);   /* tugH = 本帧家位原值（纤维缓冲按它比对：(p + o) − o 有舍入，比不上） */
          n.g.position.x += x; n.g.position.y += y; n.g.position.z += z; n.pos.copy(n.g.position);
          if (sfA && n.sf != null) { p = n.sf * 3; sfA[p] = n.g.position.x; sfA[p + 1] = n.g.position.y; sfA[p + 2] = n.g.position.z; }
          next.push(n); d2 = x * x + y * y + z * z; if (d2 > mx) mx = d2;
        }
      }
      for (i = 0; i < prev.length; i++) { n = prev[i]; if (n.tugS !== tugSeq) { n.tugS = -1; n.tugO.set(0, 0, 0); tugDirtyK.push(n.key); } }
      tugOn = next; tugMax = Math.sqrt(mx);
      tugLive = next.length > 0 || tugDirtyK.length > 0;   /* 归位那一帧之后再跑一帧把读数清零，之后整段跳过 */
      if (core.fiberTug) core.fiberTug(tugDirtyK, next.length > 0);   /* 纤维的位移在顶点着色器里加（scene-core fiberTugVS）：只把变了的星写进偏移纹理 */
    }
    S.setTug = function (map) { tugMap = map && typeof map === 'object' ? map : null; };
    S.tugDirty = function () { return tugDirtyK; };   /* 只读：本帧位移变了的星键（'c:名'）；无则空数组 */
    S.tugNote = function (layer, bytes) { if (tugLive && layer) tugNotes[layer] = (tugNotes[layer] || 0) + (+bytes || 0); };   /* 下游层报本帧增量上传 */
    /* 这颗星当前牵引位移的世界系向量（S.group 的线性部分作用于局部位移）；没被牵引返回 null。彗尾按它把历史换回家位系 */
    S.tugWorld = function (n, out) {
      if (typeof n === 'string') n = nodeByKey[n];
      if (!n || !n.tugO || n.tugS !== tugSeq || !out) return null;
      return out.copy(n.tugO).applyMatrix3(tugM3.setFromMatrix4(group.matrixWorld));
    };
    S.tugInfo = function () {
      var by = {}, up = 0, k, fs, gu;
      if (tugOn.length || tugDirtyK.length) {
        fs = core.fiberStats ? core.fiberStats() : null; gu = core.glyphUpload ? core.glyphUpload() : null;
        by.fibers = fs ? fs.lastUploadBytes + (fs.tugTexBytes || 0) : 0; by.glyph = gu ? gu.bytes : 0;
      }
      for (k in tugNotes) by[k] = tugNotes[k];
      for (k in by) up += by[k];
      return { on: !!tugMap, keys: tugOn.length, maxOff: +tugMax.toFixed(3), uploads: up, by: by, dirty: tugDirtyK.length, seq: tugSeq, frame: core.getFrames ? core.getFrames() : 0 };
    };

    // 注册核心帧循环钩子
    core.registerFrameHook(function (dt, _tAcc, _tAnim, _calm, degrade) {
      tAcc = _tAcc;
      tAnim = _tAnim;
      calm = _calm;
      if (pendingBuild) { var _pb = pendingBuild; pendingBuild = null; _pb(); }
      var gt = clamp((tAcc - growStart) / 2.4, 0, 1);
      grow = easeOut(gt);
      // v90 F4：纤维材质的 uGrow 此前无人写入（恒 0），关系纤维在任何视图都画不出来。只在「关系」信息层的全景态点亮。
      var fiberMatNow = core.getFiberMat ? core.getFiberMat() : null;
      if (fiberMatNow) fiberMatNow.uniforms.uGrow.value = infoLayer === 'relations' && mode === 'atlas' ? grow : 0;
      var raw = (tAcc - animStart) / animDur;
      var anyMove = raw < 1.10;
      // Safe-area/focus changes update the destination; consume it during the
      // real frame loop as well as in the diagnostic settle() helper.
      if (Math.abs(group.position.x - groupXTo) > 0.001) {
        group.position.x = calm ? groupXTo : lerp(group.position.x, groupXTo, 1 - Math.exp(-dt * 9));
      } else group.position.x = groupXTo;
      core.updateKnotFloat();
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        if (!n.render) {
          n.g.visible = false;
          if (core.getStarField() && n.sf != null) core.sfWrite(n, 0, 0);
          continue;
        }
        n.g.visible = !(stage.sideHidden() && (n.kind === 'chap' || n.kind === 'hub'));
        if (anyMove) {
          var t2 = clamp((raw - (calm ? 0 : n.delay)) / Math.max(0.05, 1 - (calm ? 0 : n.delay)), 0, 1);
          n.pos.lerpVectors(n.from, n.to, easeOutBack(t2));
        } else n.pos.copy(n.to);
        if (raw >= n.delay) n.size = lerp(n.size, n.sizeTo, 0.08);
        n.alpha = lerp(n.alpha, n.alphaTo, 0.08);
        if ((n.kind === 'meta' || n.kind === 'attr') && mode !== 'focus' && n.alpha < 0.02) {
          n.render = false; n.g.visible = false; labels.detachLabel(n); continue;
        }
        if (n.flash > 0) n.flash = Math.max(0, n.flash - dt * 2.1);
        var breathe = calm ? 1 : 1 + Math.sin(tAcc * 1.6 + i) * 0.045;
        var tw = n.twinkle != null ? (calm ? 1 : (1 + 0.12 * Math.sin(tAcc * 3.8 + n.twinkle))) : 1;
        var nCoc = (n.kind === 'meta' || n.kind === 'attr') ? 1.0 : (mode === 'focus' ? (n.coc || 1.0) : 1.0);
        var nDim = (n.kind === 'char') ? (1 - stage.castDim() * (1 - (n.focus || 0.4))) : 1.0;
        var sz = n.size * breathe;
        var hk = 2.4;
        if (n.kind === 'chap') {
          sz = n.size;
          hk = 1.0;
        } else if (n.kind === 'hub') {
          sz = n.size * (calm ? 1 : 1 + Math.sin(tAcc * 1.2 + i) * 0.03);
          hk = 1.6;
        }
        n.sp.scale.set(sz * nCoc, sz * nCoc, 1);
        n.halo.scale.set(sz * hk * nCoc, sz * hk * nCoc, 1);
        n.sp.material.opacity = Math.min(1, (n.alpha * tw + n.flash * 0.5) * nDim);
        n.halo.material.opacity = n.alpha * (0.55 + n.flash * 0.8) * (0.85 + 0.15 * tw) * nDim;
        if (core.getStarField() && n.sf != null) {
          // Points already draw the complete star nucleus, halo and spikes.
          // Transparent legacy sprites still cost a WebGL draw each; hundreds
          // of duplicate halos also wash out the data's constellation edges.
          var workspaceStars = document.body.classList.contains('atlas-workspace');
          n.sp.visible = !workspaceStars;
          n.halo.visible = !workspaceStars;
          n.sp.material.opacity = 0; n.halo.material.opacity *= 0.24;
        }
        n.g.position.copy(n.pos);

        if (mode === 'atlas' && !anyMove && core.getKnotDrift() > 0.002 && n.knI >= 0 && core.getKnotFloat()[n.knI]) {
          n._kd = true;
          var kf = core.getKnotFloat()[n.knI];
          var kox = n.pos.x - kf.cx, koy = n.pos.y - kf.cy, koz = n.pos.z - kf.cz;
          var krx = kf.ty * koz - kf.tz * koy, kry = kf.tz * kox - kf.tx * koz, krz = kf.tx * koy - kf.ty * kox;
          n.g.position.set(kf.cx + (kox + krx) * kf.s, kf.cy + (koy + kry) * kf.s, kf.cz + (koz + krz) * kf.s);
          var jk = (core.getBig() ? 3.4 : 7.5) * core.getKnotDrift();
          n.g.position.x += Math.sin(tAcc * 0.56 + i * 1.3) * jk;
          n.g.position.y += Math.cos(tAcc * 0.43 + i * 0.7) * jk * 1.1;
          n.g.position.z += Math.sin(tAcc * 0.34 + i * 0.5) * jk * 0.8;
          n.pos.copy(n.g.position);
        } else if (mode === 'atlas' && !anyMove && !core.getBig() && !calm && degrade === 0) {
          n.g.position.x += Math.sin(tAcc * 0.5 + i * 1.3) * 3.0;
          n.g.position.y += Math.cos(tAcc * 0.37 + i * 0.7) * 3.4;
          n.g.position.z += Math.sin(tAcc * 0.27 + i * 0.5) * 2.0;
          n.pos.copy(n.g.position);
        } else if (mode === 'focus' && !anyMove && !core.getBig() && !calm && degrade < 2 && n.kind !== 'attr' && n.alphaTo > 0.5) {
          var hostK = n.key === 'c:' + focusName;
          n.g.position.y += hostK ? Math.sin(tAcc * 0.75) * 3.2 : Math.cos(tAcc * 0.41 + i * 0.9) * 2.2;
          n.g.position.x += hostK ? Math.sin(tAcc * 0.33) * 1.2 : Math.sin(tAcc * 0.47 + i * 1.7) * 1.8;
          n.g.position.z += hostK ? 0 : Math.sin(tAcc * 0.29 + i * 0.6) * 1.4;
          n.pos.copy(n.g.position);
        }

        if (stage.getStarK() > 0 && n.kind === 'char' && stage.getStarMap()) {
          var stt = stage.getStarMap()[n.key];
          if (stt) { n.g.position.lerp(stt, stage.getStarK()); n.pos.copy(n.g.position); }
        }
        // The batched Points mesh is the actual character star. Updating only
        // n.g leaves its GPU size/alpha at zero and renders labels without stars.
        if (core.getStarField() && n.sf != null) {
          core.sfWrite(n, sz * grow, Math.min(1, (n.alpha * tw + n.flash * 0.5) * nDim));
        }
      }
      if (tugMap || tugOn.length || tugLive) tugApply();   /* Q1.3 牵引位移：漂移之后、写星场 / 纤维 / 星座线 / 标签 / 命中之前 */

      core.updateStarField();
      stage.updateCamera(dt, calm);
      if (previewCamera) { camera.lookAt(controls.target); camera.updateMatrixWorld(true); }

      if (crown) updateCrown(dt);

      core.refreshFibers();
      core.updateGlyphLines();
      core.updateDiffusionWaves();
      core.updateRoadRim();
      core.updateMeteor(dt);
      core.renderSky();

      if (window.CLArcana) {
        window.CLArcana.update({
          t: tAnim,
          beat: core.bgMat ? core.bgMat.uniforms.uBeat.value : 0.5,
          on: mode === 'atlas' && grow > 0.05,
          calm: calm,
          degrade: degrade,
          scale: (H * dpr * 0.5) / Math.tan(camera.fov * Math.PI / 360)
        });
      }

      // Apply the stage mask after raw star/line/rim updates, so those updates
      // cannot re-enable a hidden constellation in the annulus or unfold view.
      stage.applyStage();
      var annulusWorkspace = document.body.classList.contains('atlas-workspace') && document.body.getAttribute('data-atlas-view') === 'annulus';
      // Annulus owns its own factual rails and participant stars. The old
      // constellation is not a second, faint diagram behind that instrument.
      if (core.getStarField()) core.getStarField().visible = !annulusWorkspace;
      if (core.getFiberMesh()) core.getFiberMesh().visible = !annulusWorkspace;
      if (annulusWorkspace) {
        if (core.getGlyphLine()) core.getGlyphLine().visible = false;
        if (core.getRoadRim()) core.getRoadRim().group.visible = false;
        if (core.getRoadBand()) core.getRoadBand().visible = false;
      }
      labels.updateLabels(dt);
    });

    // 探针与动效过渡 API
    S.settleT = function () {
      var raw = (core.getTAcc() - animStart) / animDur;
      var nodeAnim = raw < 1.10, cam = stage.hasCamGoal(), crownSep = !!(crown && crown.sepIn < 1);
      var groupX = +Math.abs(group.position.x - groupXTo).toFixed(2);
      return { sinceFocus: +(core.getTAcc() - animStart).toFixed(2), nodeAnim: nodeAnim, cam: cam, crownSep: crownSep, groupX: groupX,
        settled: !nodeAnim && !cam && !crownSep && groupX <= 0.5 };
    };
    function cinematicFrame(worldPos, dist, dur) {
      if (!worldPos) return;
      var d = dist || 780;
      var camPos = new T.Vector3(worldPos.x + d * 0.28, worldPos.y - d * 0.38, (worldPos.z || 0) + d * 0.88);
      var tgtPos = new T.Vector3(worldPos.x, worldPos.y, worldPos.z || 0);
      stage.flyTo(camPos, tgtPos, dur || 1.35);
    }
    S.cinematicFrame = cinematicFrame;
    S.settle = function () {
      grow = 1; growStart = core.getTAcc() - 10; animStart = core.getTAcc() - 10;
      if (crown) { crown.born = core.getTAcc() - 10; updateCrown(0.016); }
      stage.settleCamera && stage.settleCamera();
      group.position.x = groupXTo;
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        n.pos.copy(n.to); n.g.position.copy(n.pos); n.alpha = n.alphaTo; n.size = n.sizeTo;
      }
      camera.updateMatrixWorld(true); camera.updateProjectionMatrix();
      core.setFiberFull(true); core.refreshFibers();
      labels.markLodDirty(); labels.updateLabels(0.016);
    };
    S.pulse = function (name) { var n = nodeByKey['c:' + name]; if (n) n.flash = 1; };
    S.buckets = function () { return nodes.filter(function (n) { return n.kind === 'chap'; }).map(function (n) { return { label: n.data.chapter, members: n.data.members, count: n.data.count }; }); };
    S.hoverChapter = function (label) {
      dialHover = label || null;
      var hn = label && nodeByKey['h:' + label];
      nodes.forEach(function (n) { n.el.classList.toggle('hover', n.kind === 'chap' && !!hn && n === hn); });
      if (mode !== 'atlas') return;
      if (!hn) {
        if (stage.chapSel()) stage.selectChapter(stage.chapSel(), true);
        else if (campSel) core.setFiberHl(core.campFiberFn(campSel));
        else core.setFiberHl(function () { return 0; });
        return;
      }
      hn.flash = Math.max(hn.flash, 0.5);
      core.setFiberHl(function (f) { return (f.a === hn || f.b === hn) ? 1 : -1; });
    };

    // 指纹表 API
    S.digest = function () {
      var r6 = function (v) { return Math.round((+v || 0) * 1e6) / 1e6; };
      var crVal = crown ? [r6(crown.vel), r6(crown.ang), r6(crown.tension), crown.levels ? r6(crown.levels[0].material.uniforms.uTime.value) : 0,
                          r6(crown.core.material.uniforms.uOn.value), r6(crown.core.material.uniforms.uTime.value),
                          r6(crown.lines.material.uniforms.uLamp.value), r6(crown.lines.material.uniforms.uOn.value)] : null;
      var crSep = crown ? r6(crown.sepIn) : -1;
      return core.digest({ crown: crVal, crownSep: crSep, lod: labels.labelStats ? labels.labelStats() : null });
    };
    S.digestAll = core.digestAll;

    S.renderer = renderer; S.camera = camera; S.controls = controls; S.scene = scene;
    S.group = group;   // 星盘：剧情盘投影到星座所在的组坐标（随 atlasShift 平移、随镜头 3D 转动）
    S.core = function () { return core; };   /* 光层后期（sky-post）要拿 composer 与背景材质 */
    S.crownAnchor = function () { return crown && crown.grp ? crown.grp : null; };   /* 罗盘星仪围绕晶体组 */
    S.skyInfo = function () { var l = core.getLayoutInfo ? core.getLayoutInfo() : null; if (!(l && l.mode === 'sky' && l.sky)) return null; l.sky.pitch = l.pitch; return l.sky; };   /* 星域层读扇区几何 */
    S.rimInfo = function () { var l = core.getLayoutInfo ? core.getLayoutInfo() : null; return l ? { R: +l.rimR || 0, V: +l.rimV || 0, pitch: +l.pitch || 0, mode: l.mode || '', halfW: +l.halfW || 0, halfH: +l.halfH || 0 } : null; };
    if (window.CLAbyssLOD && typeof window.CLAbyssLOD.attachCamera === 'function') window.CLAbyssLOD.attachCamera(camera, controls);
    S.on = core.on; S.step = core.step; S.resize = core.resize; S.setCalm = core.setCalm;
    S.calm = core.isCalm; S.setClock = core.setClock; S.setDegrade = core.setDegrade; S.setBoost = core.setBoost; S.replayGlyphs = core.replayGlyphs;
    S.shaderErrors = core.shaderErrors; S.perf = core.perf; S.quality = core.quality; S.lightBudget = core.lightBudget;
    S.camInfo = function () { return core.camInfo({ atlasDist: atlasDist(), colX: COL_X, halfW: core.getLayoutInfo() ? core.getLayoutInfo().halfW : 0, halfH: core.getLayoutInfo() ? core.getLayoutInfo().halfH : 0, safe: safe, fov: camera.fov }); };
    S.registerFrameHook = core.registerFrameHook;   /* v80 W4/W5：星域壳/灯挂进场景帧（pump 下 step() 也会驱动，rAF 被掐时不断帧） */
    S.snapshot = core.snapshot;
    S.dispose = function () { gemStageOn = false; gemStageSaved = null; gemStageArea = null; crownDispose(); if (stage.dispose) stage.dispose(); core.dispose(); };
    S.skyBench = core.skyBench; S.bg = core.bg; S.nodeOf = core.nodeOf; S.pick = core.pick;
    S.stats = core.stats; S.fiberStats = core.fiberStats;

    // Stage 委托
    S.selectChapter = stage.selectChapter; S.chapSel = stage.chapSel; S.bucketOf = stage.bucketOf;
    S.setStage = stage.setStage; S.stage = stage.stage; S.zoom = stage.zoom; S.home = stage.home;
    S.fitCamera = stage.fitCamera; S.flyTo = stage.flyTo; S.aim = stage.aim; S.aimInfo = stage.aimInfo;
    S.setOrbitLock = stage.setOrbitLock; S.orbitLockInfo = stage.orbitLockInfo;
    S.setOrbitCone = stage.setOrbitCone; S.coneInfo = stage.coneInfo;
    S.setStarTargets = stage.setStarTargets; S.starTargets = stage.starTargets;
    S.setCastDim = stage.setCastDim; S.castDim = stage.castDim;

    // Labels 委托
    S.auditLabels = labels.auditLabels; S.labelStats = labels.labelStats; S.updateLabels = labels.updateLabels;
    S.invalidateLabels = labels.markLodDirty;
    S.setNameThreshold = labels.setNameThreshold; S.nameThreshold = labels.nameThreshold;
    S.setTailShow = labels.setTailShow; S.tailShow = labels.tailShow;
    S.setLabelMode = labels.setLabelMode; S.labelMode = labels.labelMode; S.setLitOnly = labels.setLitOnly;
    S.setSafeArea = function (a) {
      safe = { left: (a && a.left) || 0, right: (a && a.right) || 0, top: (a && a.top) || 0, bottom: (a && a.bottom) || 0 };
      if (labels && labels.setSafeArea) labels.setSafeArea(a);
      if (mode === 'atlas') groupXTo = atlasShift();
      dirty = true;
    };
    S.setHudSelector = labels.setHudSelector;
    S.setSearchSet = labels.setSearchSet; S.searchNames = labels.searchNames; S.setPin = labels.setPin; S.togglePin = labels.togglePin;
    S.isPinned = labels.isPinned; S.pinned = labels.pinned; S.why = labels.why;
    S.beat = labels.beat; S.spines = labels.spines; S.leads = labels.leads;
    S.measureLabels = labels.measureLabels; S.lod = labels.lod;

    // 场景状态 API
    S.hoverCamp = function (name) {
      name = name && (core.getCampIndex ? core.getCampIndex()[name] : null) ? name : null;
      if (name === campHover) return campHover;
      campHover = name;
      nodes.forEach(function (n) { if (n.kind === 'camp') n.el.classList.toggle('hover', !!name && n.data.camp === name); });
      if (mode !== 'atlas' || campSel) return campHover;
      if (name) core.setFiberHl(core.campFiberFn(name)); else if (stage.chapSel()) stage.selectChapter(stage.chapSel(), true); else core.setFiberHl(function () { return 0; });
      dirty = true;
      return campHover;
    };
    S.selectCamp = function (name) {
      campSel = name && (core.getCampIndex ? core.getCampIndex()[name] : null) && name !== campSel ? name : null;
      nodes.forEach(function (n) {
        if (n.kind === 'camp') n.el.classList.toggle('sel', !!campSel && n.data.camp === campSel);
        if (n.kind === 'char' && mode === 'atlas') n.alphaTo = stage.charAtlasAlpha(n);
      });
      if (mode === 'atlas') {
        if (campSel) {
          core.setFiberHl(core.campFiberFn(campSel));
          var cp = core.getCampIndex ? core.getCampIndex()[campSel] : null;
          var ln = cp ? nodeByKey['c:' + cp.leadName] : null;
          if (ln) { core.spawnIris(ln); core.sendSignal(ln); if (core.setBurst) core.setBurst(0.6); }
        } else if (stage.chapSel()) stage.selectChapter(stage.chapSel(), true);
        else core.setFiberHl(function () { return 0; });
      }
      labels.markLodDirty(); dirty = true;
      return campSel;
    };
    S.campSel = function () { return campSel; };
    S.camps = function () { return core.getLayoutInfo() ? core.getLayoutInfo().camps.map(function (c) { return { name: c.name, count: c.members.length, color: c.color, lead: c.leadName, members: c.names }; }) : []; };
    S.campOf = function (name) { return core.getCampOfName()[name] || ''; };
    S.hubs = function () { return core.getHubList(); };
    S.constellation = core.constellation || function () { return { on: false }; };
    S.starField = function () { return core.getStarField() ? { stars: core.getStarList().length, dust: core.getDustList().length, scale: +core.starScale().toFixed(1) } : null; };
    S.density = core.getDensityProfile || function () { return null; };
    S.darkMatter = function () { return { filaments: core.getDarkMatterFilaments().length, dust: core.getDarkMatterDust().length }; };
    S.breath = function () { return { breath: +(core.getTAcc() % 3.92).toFixed(3), amp: 0.045, f: 1.6 }; };
    S.roadRim = function () { return core.getRoadRim() ? { R: +core.getRoadRim().rib.material.uniforms.uRout.value.toFixed(1), k: +core.getRoadRim().k.toFixed(3) } : null; };
    S.relationWeb = function () { return { total: relWeb.total, shown: relWeb.shown, pruned: relWeb.pruned, max: REL_WEB_MAX }; };
    S.meteor = function () { var m = core.getMeteor && core.getMeteor(); return { visible: !!(m && m.visible) }; };   // v90 F7：meteorT/meteorWait 在 scene-core 闭包内，旧写法调用即 ReferenceError
    S.roadBand = function () { return core.getRoadBand() ? { segs: core.getRoadBand().geometry.attributes.position.count / 2, width: 34 } : null; };
    S.glyphDebug = function () { return { count: core.getGlyphSegs().length, segs: core.getGlyphSegs().slice(0, 10) }; };
    S.glyph = function () { return { segs: core.getGlyphSegs().length, t: core.getGlyphLine() ? +core.getGlyphLine().material.uniforms.uOn.value.toFixed(2) : 0 }; };
    S.road = function () { var L = core.getLayoutInfo() || {}; return { mode: L.mode || 'camps', chainCount: L.chain ? L.chain.length : 0 }; };
    S.stats = core.stats;
    S.fiberStats = core.fiberStats;
    S.mode = function () { return mode; };
    S.focusName = function () { return focusName; };
    S.bucketMap = function () { return core.getBucketMap(); };
    S.fx = core.fx;

    // 门面控制与探针
    S.setGraph = setGraph;
    S.focus = focus;
    S.toAtlas = toAtlas;
    S.v28 = function () {
      var q = core.qspec ? core.qspec() : Core.QSPEC, cr = crown;
      var gb = cr && cr.gemBase ? cr.gemBase.material.uniforms : null;
      var g2 = cr && cr.gem2Base ? cr.gem2Base.material.uniforms : null;
      var CD = core.conductor ? core.conductor() : { bar: 0, half: 0, third: 0, beat8: 0, lamp: 0, slot: 0 };
      var R = window.CLRadar;
      var dof = typeof core.dofState === 'function' ? core.dofState() : (core.dofState || { d: 0, r: 0, k: 0, n: 0 });
      return {
        dof: { d: +dof.d.toFixed(1), r: +dof.r.toFixed(1), k: +dof.k.toFixed(3), targets: dof.n,
               inShader: !!(core.getStarField() && core.getStarField().material.uniforms.uFocD) },
        gem: cr && gb && g2 ? { steps: gb.uSteps.value, steps2: g2.uSteps.value, cosmos: +gb.uCosmos.value.toFixed(2),
                    ior: gb.uIor.value, disp: gb.uDisp.value, abs: gb.uAbs.value,
                    matA: cr.gemBase.material.userData.gemName, matB: cr.gem2Base.material.userData.gemName } : null,
        caust: cr && cr.caust ? { axes: cr.caust.material.uniforms.uAxes.value.map(function (x) { return +x.toFixed(2); }), on: cr.caust.visible } : null,
        mats: Object.keys(GEM_MATS || {}),
        tone: Object.keys(TONE || {}),
        beat: { bar: +((CD.bar || 0)).toFixed(3), half: +((CD.half || 0)).toFixed(3), third: +((CD.third || 0)).toFixed(3), beat8: +((CD.beat8 || 0)).toFixed(3),
                lamp: +((CD.lamp || 0)).toFixed(3), slot: CD.slot || 0, barSec: Core.BAR_SEC || 20.96,
                radarLamp: R && R.lampPhase ? +R.lampPhase().toFixed(3) : null,
                sync: R && R.lampPhase ? +Math.abs(R.lampPhase() - (CD.lamp || 0)).toFixed(4) : null },
        ladder: { degrade: core.digest ? core.digest().degrade : 0, spec: q, ghostsVisible: cr ? cr.ghosts.filter(function (g) { return g.visible; }).length : -1 }
      };
    };

    core.resize();
    setGraph(null);
    core.frame();

    window.CLScene.current = S;
    return S;
  }

  window.CLScene = {
    create: create,
    mats: Mats,
    labels: Labels,
    stage: Stage,
    core: Core,
    ATTR_KEYS: Mats.ATTR_KEYS,
    ATTR_EN: Mats.ATTR_EN,
    META_KEYS: Mats.META_KEYS,
    META_EN: Mats.META_EN,
    META_DEF: Mats.META_DEF,
    KIND_COL: Mats.KIND_COL
  };
})();
