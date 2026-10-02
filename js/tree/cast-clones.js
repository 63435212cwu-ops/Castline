/* cast-clones.js —— 支线分身层：剧情线模式下本体星飞去权重最大的线，
 * 该角色在其余线的出场就没了。本层补画 dupIdx>=1 的分身星，并各用一根
 * 本体端更暗的细线连回本体。整层仅 Points+LineSegments=2 个 draw call。 */
(function () {
  'use strict';
  var T = (typeof window !== 'undefined' && window.THREE) || null;
  var A = (typeof window !== 'undefined' && window.CLTreeAnchor) || null;
  var GOLD = [1, 0.706, 0.361]; // 0xffb45c 预拆分量，混色循环里直接用
  var MAX_STD = 600, MAX_BIG = 300, FADE = 0.9;
  var group = null, points = null, lines = null;
  var pGeo = null, lGeo = null, pMat = null, lMat = null, tex = null;
  var on = false, force = null, level = 0, target = 0, built = false;
  var tick = 0, degrade = 0, big = false, bound = false, lastT = -1;
  var st = { clones: 0, lines: 0, dupNames: 0, maxPerName: 0 };

  /* ---- v36 摇曳：本体位缓存 + 逐点重投 ----
   * 本层与 ghost 的差别不是「要不要逐点」，而是**为什么**要逐点：
   * 这里的点位是 build 时烘进 Float32Array 的、每点高度都不同，给 group 挂一个旋转
   * 只能让整层整体倾斜，连线端点会从 star-migrate 画的星上脱开。
   * 存一份单位空间原位（baseP/baseL），每帧从它重投（不在上一帧结果上叠，叠会累积漂移）。
   * 点数百级、每帧几千次乘加，可忽略。 */
  var baseP = null, baseL = null, revSeen = -1, swScratch = [0, 0, 0];

  /** 逐点套用 CLTreeSway 的姿态，写回 position 缓冲。
   *  按**姿态版本号**（rev）跳过：姿态没变（静止 / 降低动效 / low 档）时一次 GPU 上传都不产生。 */
  function refreshSway() {
    var SW = (typeof window !== 'undefined') ? window.CLTreeSway : null;
    if (!SW || typeof SW.bendInto !== 'function' || typeof SW.rev !== 'function') return;
    var r = SW.rev();
    if (r === revSeen) return;
    revSeen = r;
    var a, i;
    if (points && baseP && pGeo && pGeo.attributes && pGeo.attributes.position) {
      a = pGeo.attributes.position.array;
      for (i = 0; i < baseP.length; i += 3) {
        SW.bendInto(baseP[i], baseP[i + 1], baseP[i + 2], swScratch);
        a[i] = swScratch[0]; a[i + 1] = swScratch[1]; a[i + 2] = swScratch[2];
      }
      pGeo.attributes.position.needsUpdate = true;
    }
    if (lines && baseL && lGeo && lGeo.attributes && lGeo.attributes.position) {
      a = lGeo.attributes.position.array;
      for (i = 0; i < baseL.length; i += 3) {
        SW.bendInto(baseL[i], baseL[i + 1], baseL[i + 2], swScratch);
        a[i] = swScratch[0]; a[i + 1] = swScratch[1]; a[i + 2] = swScratch[2];
      }
      lGeo.attributes.position.needsUpdate = true;
    }
  }

  function reduced() { // 实时查：中途可开「减弱动态」，缓存会失真
    try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }
    catch (e) { return false; }
  }

  /** entry 取值规范化：非负有限数才算有效，其余一律 -1（"没有时序信息"，排在最后）。 */
  function numE(v) { return (typeof v === 'number' && isFinite(v) && v >= 0) ? v : -1; }

  function hex2rgb(h) { // color 可能是 0xRRGGBB 数字或 '#rgb' 串；非法给白，守空不抛
    var v;
    if (typeof h === 'number' && isFinite(h) && h >= 0) v = h;
    else if (typeof h === 'string') {
      var s = h.charAt(0) === '#' ? h.slice(1) : h;
      if (s.length === 3) s = s.charAt(0) + s.charAt(0) + s.charAt(1) + s.charAt(1) + s.charAt(2) + s.charAt(2);
      v = parseInt(s, 16);
      if (!isFinite(v) || v < 0) v = 0xffffff;
    } else v = 0xffffff;
    return [((v >> 16) & 255) / 255, ((v >> 8) & 255) / 255, (v & 255) / 255];
  }

  function makeTex() { // 程序化软点：64px 径向渐变，免外置图；白图靠 vertexColors 染色
    var cv = document.createElement('canvas');
    cv.width = cv.height = 64;
    var g = cv.getContext ? cv.getContext('2d') : null;
    if (g && g.createRadialGradient) {
      var gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
      gr.addColorStop(0, 'rgba(255,255,255,1)');
      gr.addColorStop(0.3, 'rgba(255,255,255,0.5)');
      gr.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
    }
    return new T.CanvasTexture(cv);
  }

  function ensureMounted() {
    A = window.CLTreeAnchor || A;
    if (!group) group = new T.Group();
    if (!group.parent) {
      var root = (A && A.root) ? A.root() : null;
      if (root && root.add) root.add(group);
    }
    return !!(group && group.parent);
  }

  function killGeo() {
    if (group) {
      if (points) { group.remove(points); points = null; }
      if (lines) { group.remove(lines); lines = null; }
    }
    if (pGeo) { pGeo.dispose(); pGeo = null; }
    if (lGeo) { lGeo.dispose(); lGeo = null; }
    if (pMat) { pMat.dispose(); pMat = null; }
    if (lMat) { lMat.dispose(); lMat = null; }
    st.clones = st.lines = st.dupNames = st.maxPerName = 0;
  }

  function rebuild() {
    T = (typeof window !== 'undefined' && window.THREE) || T;
    if (!T) return false;
    A = window.CLTreeAnchor || A;
    // 守空取数：规范化守卫，消灭静默 return，记录显式状态
    var tree = (window.CLStory && CLStory.get) ? CLStory.get() : null;
    var shape = (window.CLTreeShape && tree) ? CLTreeShape.build(tree) : null;
    var res = (window.CLTreeLeaf && shape && shape.ok) ? CLTreeLeaf.assign(shape, tree) : null;
    if (!res || !res.leaves || !res.leaves.length) {
      st.state = 'empty';
      st.reason = 'no-leaves';
      if (group) group.visible = false;
      return false;
    }
    if (!A || !A.root || (A.ready && !A.ready()) || !ensureMounted()) {
      st.state = 'waiting-anchor';
      st.reason = 'anchor-not-ready';
      return false;
    }

    var cap = (big || degrade >= 1) ? MAX_BIG : MAX_STD;
    var leaves = res.leaves, cand = [], i, lf;
    for (i = 0; i < leaves.length; i++) {
      lf = leaves[i];
      if (lf && lf.dupIdx >= 1 && lf.pos && lf.pos.length >= 3) cand.push(lf);
    }
    if (cand.length === 0) {
      st.state = 'empty';
      st.reason = 'zero-clones';
    } else {
      st.state = 'ready';
      st.reason = 'ok';
    }
    // 截断**按权重**（重的优先保留：宁可少画几个轻的，也不能把主线人物丢掉），
    // 截断**之后**再按出场时序重排。顺序决定连线在缓冲里的排布 ——
    // 时间上相邻的分身挨在一起，配合下面的 entry 加权，整层读起来才是一条时间轴而不是一堆散点。
    cand.sort(function (a, b) {
      return (b.w || 0) - (a.w || 0) || (String(a.name) < String(b.name) ? -1 : 1);
    });
    if (cand.length > cap) cand.length = cap;
    cand.sort(function (a, b) {
      var ea = numE(a.entry), eb = numE(b.entry);
      if (ea < 0 && eb >= 0) return 1;
      if (eb < 0 && ea >= 0) return -1;
      if (ea !== eb) return ea - eb;
      return (b.w || 0) - (a.w || 0) || (String(a.name) < String(b.name) ? -1 : 1);
    });

    // 出场时间跨度：连线亮度的归一化基准。用全体叶（不只是候选）算，跨作品可比。
    var eMax = 0, eMin = 1e9, ei, ev2;
    for (ei = 0; ei < leaves.length; ei++) {
      ev2 = numE(leaves[ei] && leaves[ei].entry);
      if (ev2 >= 0) { if (ev2 > eMax) eMax = ev2; if (ev2 < eMin) eMin = ev2; }
    }
    var eSpan = Math.max(1, eMax >= eMin ? eMax - eMin : 0);

    var n = cand.length, wSum = 0, w, c, nm;
    var pp = new Float32Array(n * 3), pc = new Float32Array(n * 3);
    var perName = Object.create ? Object.create(null) : {};
    for (i = 0; i < n; i++) {
      lf = cand[i];
      w = (typeof lf.w === 'number' && isFinite(lf.w)) ? lf.w : 0;
      if (w < 0) w = 0; else if (w > 1) w = 1;
      wSum += w;
      pp[i * 3] = lf.pos[0]; pp[i * 3 + 1] = lf.pos[1]; pp[i * 3 + 2] = lf.pos[2];
      // camp 色混金 40% 标记「这是分身」；亮度 0.45+0.55w 跟权重走，轻出场退背景
      c = hex2rgb(lf.color);
      var lum = 0.45 + 0.55 * w;
      pc[i * 3] = (c[0] * 0.6 + GOLD[0] * 0.4) * lum;
      pc[i * 3 + 1] = (c[1] * 0.6 + GOLD[1] * 0.4) * lum;
      pc[i * 3 + 2] = (c[2] * 0.6 + GOLD[2] * 0.4) * lum;
      nm = String(lf.name == null ? '?' : lf.name);
      perName[nm] = (perName[nm] || 0) + 1;
    }

    killGeo();

    /* 单位空间原位：摇曳每帧**从这里重投**，基准永远是「没摇的那棵树」。
     * 不在上一帧的结果上继续叠（叠会累积漂移，且与 star-migrate 的解析式再也对不上）。 */
    baseP = pp.slice(); revSeen = -1;

    pGeo = new T.BufferGeometry();
    pGeo.setAttribute('position', new T.BufferAttribute(pp, 3));
    pGeo.setAttribute('color', new T.BufferAttribute(pc, 3));
    if (!tex) tex = makeTex();
    pMat = new T.PointsMaterial({
      map: tex, vertexColors: true, transparent: true, opacity: 0,
      blending: T.AdditiveBlending, depthWrite: false, sizeAttenuation: true
    });
    // PointsMaterial 无逐点 size（那要 ShaderMaterial，仓内禁）：均权近似，明暗仍逐点
    pMat.size = 0.006 + 0.010 * (n ? wSum / n : 0);
    points = new T.Points(pGeo, pMat);
    points.raycast = function () {}; // 分身不可点，不挡本体拾取
    points.userData = { clPickable: false, clLayer: 'tree-clones', clTree: true };
    points.frustumCulled = false;    // 局部包围球不代表 root 变换后范围，防误剔除
    group.add(points);

    var lCount = 0;
    if (degrade < 1 && n > 0) { // degrade>=1 只保星省线，归属感由金味颜色兜底
      var lp = new Float32Array(n * 6), lc = new Float32Array(n * 6);
      for (i = 0; i < n; i++) {
        lf = cand[i];
        var src = (typeof lf.dupOf === 'number') ? leaves[lf.dupOf] : null;
        if (!src || !src.pos || src.pos.length < 3) continue; // 本体叶缺 → 星照画、线跳过
        var o = lCount * 6, cc = hex2rgb(lf.color);
        lp[o] = lf.pos[0]; lp[o + 1] = lf.pos[1]; lp[o + 2] = lf.pos[2];
        lp[o + 3] = src.pos[0]; lp[o + 4] = src.pos[1]; lp[o + 5] = src.pos[2];
        // 分身端 55% → 本体端 12%：从本体那头淡出去，均亮线几百根会糊成网
        // 再叠一层「相邻加权」：分身与本体的出场时刻挨得越近，这根线越亮 ——
        // 读作「这是我在这条线上的同一时段」；隔得越远（跨了一整场戏）线越淡。
        var eA = numE(lf.entry), eB = numE(src.entry), wLine = 1;
        if (eA >= 0 && eB >= 0) wLine = 0.50 + 0.50 * (1 - Math.min(1, Math.abs(eA - eB) / eSpan));
        var hd = 0.55 * wLine, tl = 0.12 * wLine;
        lc[o] = cc[0] * hd; lc[o + 1] = cc[1] * hd; lc[o + 2] = cc[2] * hd;
        lc[o + 3] = cc[0] * tl; lc[o + 4] = cc[1] * tl; lc[o + 5] = cc[2] * tl;
        lCount++;
      }
      baseL = lp.slice(); revSeen = -1;
      lGeo = new T.BufferGeometry();
      lGeo.setAttribute('position', new T.BufferAttribute(lp, 3));
      lGeo.setAttribute('color', new T.BufferAttribute(lc, 3));
      if (lGeo.setDrawRange) lGeo.setDrawRange(0, lCount * 2); // 尾部空位不进管线
      lMat = new T.LineBasicMaterial({
        vertexColors: true, transparent: true, opacity: 0,
        blending: T.AdditiveBlending, depthWrite: false
      });
      lines = new T.LineSegments(lGeo, lMat);
      lines.raycast = function () {};
      lines.userData = { clPickable: false, clLayer: 'tree-clone-links', clTree: true };
      lines.frustumCulled = false;
      group.add(lines);
    } else { baseL = null; }

    st.clones = n; st.lines = lCount; st.dupNames = 0; st.maxPerName = 0;
    for (var k in perName) {
      st.dupNames++;
      if (perName[k] > st.maxPerName) st.maxPerName = perName[k];
    }
    built = true;
    return true;
  }

  function setOn(v) { on = v === true; }
  function show(v) { force = (v == null) ? null : !!v; } // 调试总开关，优先于事件；null 解除
  function visible() { return !!(group && group.visible); }

  function onPlotline(e) { setOn(e && e.detail ? e.detail.on === true : false); }
  function bind() {
    if (bound) return;
    document.addEventListener('cl:tree-plotline', onPlotline);
    bound = true;
  }
  function unbind() {
    if (!bound) return;
    document.removeEventListener('cl:tree-plotline', onPlotline);
    bound = false;
  }

  function build(o) {
    o = o || {};
    big = !!o.big;
    if (o.degrade != null) degrade = o.degrade | 0;
    bind();
    return rebuild();
  }

  function update(s) {
    s = s || {};
    if (!built && ++tick >= 30) { tick = 0; rebuild(); } // 数据晚到重试，成功即停
    if (s.degrade != null && (s.degrade | 0) !== degrade) {
      degrade = s.degrade | 0;
      if (built) rebuild(); // 降级档同时改上限与线开关，整层重建一次
    }
    // 显 = 剧情线开 × 迁移态 plot/flying × 非聚焦(s.on!==0) × degrade<2
    var mig = (window.CLStarMigrate && CLStarMigrate.state) ? CLStarMigrate.state() : null;
    var want = (force != null ? force : on) && built &&
      (!mig || mig === 'plot' || mig === 'flying') && s.on !== 0 && degrade < 2;
    target = want ? 1 : 0;

    // dt：优先 s.dt，退回 s.t 差值，再退 1/60
    var dt = 1 / 60, d;
    if (typeof s.dt === 'number' && isFinite(s.dt) && s.dt > 0 && s.dt < 0.5) dt = s.dt;
    else if (typeof s.t === 'number' && isFinite(s.t) && lastT >= 0 &&
             (d = s.t - lastT) > 0 && d < 0.5) dt = d;
    if (typeof s.t === 'number' && isFinite(s.t)) lastT = s.t;

    if (level < target) { level += dt / FADE; if (level > target) level = target; }
    else if (level > target) { level -= dt / FADE; if (level < target) level = target; }

    if (!group) return;
    /* v36：逐点跟上摇曳。放在可见性判断之前 —— 否则「刚被点开的那一帧」会先亮出
     * 上一姿态的旧点位，下一帧才追上（一闪）。 */
    refreshSway();
    var breath = 1; // 呼吸乘子；reduced-motion 时不做（恒 1）
    if (!reduced()) {
      var beat = (typeof s.beat === 'number' && isFinite(s.beat)) ? s.beat
        : 0.5 + 0.5 * Math.sin((typeof s.t === 'number' && isFinite(s.t) ? s.t : 0) * 0.3);
      breath = 0.82 + 0.18 * beat;
    }
    if (pMat) pMat.opacity = level * breath;
    // 归属线一多就糊成蛛网（sample-saga 上 165 根实测如此）。按根数把整层压下去：
    // 60 根以内保持 0.16，之后按平方根衰减，600 根时只剩 0.05。
    if (lMat) lMat.opacity = 0.16 * Math.min(1, Math.sqrt(60 / Math.max(1, lCount))) * level * breath;
    group.visible = level > 0.002; // 淡尽即真隐藏，省掉整层 draw call
  }

  function dispose() {
    unbind();
    killGeo();
    if (group) {
      if (group.parent && group.parent.remove) group.parent.remove(group);
      group = null;
    }
    if (tex) { tex.dispose(); tex = null; }
    built = on = false; force = null;
    level = target = tick = 0; lastT = -1;
  }

  function state() {
    return st.state || (built ? (st.clones > 0 ? 'ready' : 'empty') : 'empty');
  }

  function stats() {
    return {
      ready: built, state: state(), reason: st.reason || '', on: level, clones: st.clones, lines: st.lines,
      dupNames: st.dupNames, maxPerName: st.maxPerName,
      drawcalls: built ? (st.clones > 0 ? 1 : 0) + (st.lines > 0 && degrade < 1 ? 1 : 0) : 0,
      degrade: degrade, muted: reduced()
    };
  }

  var API = {
    name: 'cast-clones', build: build, update: update, dispose: dispose,
    setOn: setOn, rebuild: rebuild, show: show, visible: visible, state: state, stats: stats
  };

  bind(); // 顶层即挂：事件可能早于 build 到达，错过会停在星座态

  window.CLCastClones = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
