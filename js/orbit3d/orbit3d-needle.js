/* @role webgl · @owns js/orbit3d/orbit3d-needle.js · @budget drawcalls=1 verts=27 particles=0 fps=60 shader=yes js_ms=0.05 · @contract v47+v50+v52+v53+v90
 * v90 F2「年轮清线」：年轮态（body.is-ann，CLAnnulusSVG 已挂）不再画从盘心斜穿全部星弧、伸出盘外的
 * 长读针与盘心红宝石针帽（盘心交给 F1 星核）。改为「盘缘刻标」：主线带外侧一枚短菱形刻标
 * （RIM_IN..RIM_OUT）+ 向内 ≤0.08R 的发丝短指针；角度 = 当前游标/焦点事件的 desc().angleOf
 * （与 annulus-model 同源）；只在 focusEv 有效时出现，默认全书态（只有读头巡航 pulse）不出现。
 * 游标移动按 --cl-atlas-dur-1 缓动过渡；reduced / 低档直接到位。同一 27 顶点缓冲、同一 1 次绘制，
 * 针帽 9 顶点在刻标态退化为零面积。非年轮态（经典星盘）保持 v53 钟表读针原样。 */
(function (g) {
  'use strict';
  var NAME = 'orbit3d-needle', VERSION = '90', TWO = Math.PI * 2;
  /* v90 刻标几何（单位 R）：主线带在 0.965R，表圈环自 1.06R 起 */
  var RIM_IN = 1.0, RIM_OUT = 1.056, RIM_W = 0.034, PTR_LEN = 0.075;

  var NEEDLE_VS = [
    'attribute float aA;',
    'attribute float aS;',
    'attribute float aPart;',
    'varying float vS;',
    'varying float vA;',
    'varying float vPart;',
    'void main(){',
    '  vS = aS;',
    '  vA = aA;',
    '  vPart = aPart;',
    '  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);',
    '}'
  ].join('\n');

  var NEEDLE_FS = [
    'uniform vec3 uCol;',
    'uniform float uFade;',
    'uniform float uK;',
    'varying float vS;',
    'varying float vA;',
    'varying float vPart;',
    'void main(){',
    '  float absS = abs(vS);',
    '  float a = 0.0;',
    '  vec3 col = uCol;',
    '  if (vPart < 0.5) {',
    '    // 钟表剑身：立体双斜面 + 极亮白金中脊线',
    '    float facet = (vS <= 0.0) ? 0.96 : 0.66;',
    '    float spine = exp(-absS * 20.0) * 0.98;',
    '    float edge = 1.0 - smoothstep(0.85, 1.0, absS);',
    '    a = (edge * facet + spine) * vA * uFade * uK;',
    '  } else if (vPart < 1.5) {',
    '    // 钟表宝石轴承（Jeweled Pivot Bearing）：精密金圈包镶 + 晶莹红宝石轴心 + 焦散折射 + 中心耀斑',
    '    vec3 goldSetting = vec3(1.0, 0.84, 0.48);',
    '    vec3 rubyJewel = vec3(0.96, 0.16, 0.32);',
    '    if (absS > 0.72) {',
    '      // 外圈金属包镶嵌圈 (Collet Setting Ring)',
    '      float rim = smoothstep(0.72, 0.85, absS) * (1.0 - smoothstep(0.95, 1.0, absS));',
    '      col = goldSetting * (0.85 + 0.45 * rim);',
    '      a = (0.85 + 0.35 * rim) * vA * uFade * uK;',
    '    } else {',
    '      // 内部折射深红宝石 (Cabochon Ruby Jewel)',
    '      float dome = 1.0 - (absS / 0.72);',
    '      float ringCaustic = exp(-pow((absS - 0.42) * 8.0, 2.0)) * 0.45;',
    '      float glint = exp(-pow(absS * 9.0, 2.0)) * 0.98;',
    '      vec3 gem = mix(rubyJewel, vec3(1.0, 0.82, 0.88), glint * 0.80 + ringCaustic * 0.30);',
    '      col = gem * (0.82 + 0.48 * dome);',
    '      a = (0.95 + 0.25 * glint) * vA * uFade * uK;',
    '    }',
    '  } else if (vPart < 2.5) {',
    '    // 钟表配重尾（Counterweight Tail）：流线形柳叶金属',
    '    float facet = (vS <= 0.0) ? 0.88 : 0.58;',
    '    float spine = exp(-absS * 14.0) * 0.85;',
    '    float edge = 1.0 - smoothstep(0.80, 1.0, absS);',
    '    col = uCol * facet;',
    '    a = (edge * facet + spine) * vA * uFade * uK;',
    '  } else {',
    '    // 聚焦光柱（Pillar）',
    '    float c = exp(-absS * absS * 5.0);',
    '    a = c * vA * uFade * uK;',
    '  }',
    '  gl_FragColor = vec4(col * a, a);',
    '}'
  ].join('\n');

  var T, geom, mat, mesh, pos, posAttr, ready = false, updates = 0, lastT = -1,
    angDraw = 0, angleVal = null, visibleNow = false, pillarNow = false, focusNow = -1;
  /* v90 刻标态：rimNow = 本帧是否处于年轮刻标态；tw = 游标过渡 { from, to, t0, dur }；rimR = 最近一帧的 R */
  var rimNow = false, rimShown = false, tw = null, rimR = 1, rimTarget = null, colNeedle = null, colRim = null;
  var RM = g.matchMedia ? g.matchMedia('(prefers-reduced-motion: reduce)') : null;

  function reduced() { return !!(RM && RM.matches); }
  function annulusOn() { try { var b = g.document && g.document.body; return !!(b && b.classList && b.classList.contains('is-ann')); } catch (e) { return false; } }
  function lowTier() { try { if (g.CLOrbit3DTier && g.CLOrbit3DTier.get && g.CLOrbit3DTier.get() === 'low') return true; } catch (e) {} return tierVal() === 2; }
  /* --cl-atlas-dur-1（220ms 令牌）→ 秒；读不到时按令牌值兜底 */
  function dur1() {
    var s = cssVar('--cl-atlas-dur-1', ''), v = parseFloat(s);
    if (!finite(v) || v <= 0) return 0.22;
    return /ms\s*$/.test(s) ? v / 1000 : (/s\s*$/.test(s) ? v : v / 1000);
  }
  function easeOut(k) { var u = 1 - k; return 1 - u * u * u; }
  function wrapPi(d) { while (d > Math.PI) d -= TWO; while (d < -Math.PI) d += TWO; return d; }
  function finite(v) { return typeof v === 'number' && isFinite(v); }
  function r4(v) { return Math.round(v * 10000) / 10000; }
  function layerStats() { try { return (g.CLOrbit3DLayer && g.CLOrbit3DLayer.stats) ? g.CLOrbit3DLayer.stats() : null; } catch (e) { return null; } }
  function tierVal() { var s = layerStats(); return (s && finite(s.tier)) ? s.tier : 0; }
  function cssVar(n, fb) { try { if (!g.document || !g.getComputedStyle) return fb; var v = g.getComputedStyle(g.document.documentElement).getPropertyValue(n); v = v ? v.replace(/^\s+|\s+$/g, '') : ''; return v || fb; } catch (e) { return fb; } }
  /* v90：刻标取信号金（--cl-ann-signal，金/琥珀 = 信号），经典读针仍取 --warm */
  function resolveRimCol(TH) { var s = cssVar('--cl-ann-signal', null) || cssVar('--cl-atlas-signal', null); if (!s) return null; try { return new TH.Color(s); } catch (e) { return null; } }
  function resolveCol(TH) { var s = cssVar('--warm', null); if (!s) { try { if (g.CLPalette && g.CLPalette.mainColor) s = g.CLPalette.mainColor(4); } catch (e) {} } try { return new TH.Color(s || 'white'); } catch (e2) { return new TH.Color('white'); } }

  function setP(i, x, y, z) { var b = i * 3; pos[b] = x; pos[b + 1] = y; pos[b + 2] = z; }

  /* 精密钟表时针几何放置 · 宝石轴承微缩至 0.030R */
  function placeNeedle(ang, R) {
    var c = Math.cos(ang), sn = Math.sin(ang);
    var tx = -sn, ty = c, z = 1.5;

    // 1. 配重尾部（Counterweight Tail，指向后方负轴）
    // 尾尖 r=-0.16R, 尾腹 r=-0.10R, 尾根 r=-0.026R (无缝接宝石包座圈)
    setP(0, -0.16 * R * c, -0.16 * R * sn, z);
    setP(1, -0.10 * R * c - 0.011 * R * tx, -0.10 * R * sn - 0.011 * R * ty, z);
    setP(2, -0.10 * R * c + 0.011 * R * tx, -0.10 * R * sn + 0.011 * R * ty, z);
    setP(3, -0.026 * R * c, -0.026 * R * sn, z);

    // 2. 中心宝石轴承（Jeweled Bearing，缩小至 0.030R）
    var rhub = 0.030 * R;
    for (var k = 0; k < 8; k++) {
      var th = k * (Math.PI / 4);
      var rx = rhub * Math.cos(th), ry = rhub * Math.sin(th);
      setP(4 + k, rx * c - ry * tx, rx * sn - ry * ty, z + 0.05);
    }
    setP(12, 0, 0, z + 0.16); // 宝石凸起弧面顶点 (Cabochon Peak)

    // 3. 渐细剑形针身（Lance Body）与针尖（Tip）
    // 断面 0 (根部紧扣宝石座圈 r=0.030R)
    setP(13, 0.030 * R * c - 0.0055 * R * tx, 0.030 * R * sn - 0.0055 * R * ty, z);
    setP(14, 0.030 * R * c, 0.030 * R * sn, z + 0.08); // 中脊凸起
    setP(15, 0.030 * R * c + 0.0055 * R * tx, 0.030 * R * sn + 0.0055 * R * ty, z);

    // 断面 1 (中腰 r=0.65R)
    setP(16, 0.65 * R * c - 0.0050 * R * tx, 0.65 * R * sn - 0.0050 * R * ty, z);
    setP(17, 0.65 * R * c, 0.65 * R * sn, z + 0.06);
    setP(18, 0.65 * R * c + 0.0050 * R * tx, 0.65 * R * sn + 0.0050 * R * ty, z);

    // 断面 2 (剑身肩部 r=1.08R)
    setP(19, 1.08 * R * c - 0.0075 * R * tx, 1.08 * R * sn - 0.0075 * R * ty, z);
    setP(20, 1.08 * R * c, 1.08 * R * sn, z + 0.04);
    setP(21, 1.08 * R * c + 0.0075 * R * tx, 1.08 * R * sn + 0.0075 * R * ty, z);

    // 截面 3 (精细针尖，精准抵近 1.185R 刻度环)
    setP(22, 1.185 * R * c, 1.185 * R * sn, z + 0.02);
  }

  /* 聚焦光柱（Pillar） */
  function placePillar(ang, rb, zb, R, on) {
    if (!on) {
      setP(23, 0, 0, 0); setP(24, 0, 0, 0); setP(25, 0, 0, 0); setP(26, 0, 0, 0);
      return;
    }
    var c = Math.cos(ang), sn = Math.sin(ang), w = R * 0.003, top = zb + R * 0.06,
      ax = (rb - w) * c, ay = (rb - w) * sn, bx = (rb + w) * c, by = (rb + w) * sn;
    setP(23, ax, ay, zb); setP(24, bx, by, zb); setP(25, bx, by, top); setP(26, ax, ay, top);
  }

  /* v90 盘缘刻标：同一 27 顶点缓冲改摆——
   * 0..3（配重尾片段）= 主线带外侧的短菱形刻标：外尖 RIM_OUT、内尖 RIM_IN，指向盘心；
   * 4..12（针帽）= 退化到刻标外尖一点（零面积，盘心不再有任何图元）；
   * 13..22（剑身片段）= 自 RIM_IN 向内 PTR_LEN 的发丝短指针（≤0.08R）。 */
  function placeRim(ang, R) {
    var c = Math.cos(ang), sn = Math.sin(ang), tx = -sn, ty = c, z = 1.5;
    function at(i, r, w, dz) { setP(i, r * R * c + w * R * tx, r * R * sn + w * R * ty, z + (dz || 0)); }
    var rMid = RIM_IN + (RIM_OUT - RIM_IN) * 0.62, rTip = RIM_IN - PTR_LEN;
    at(0, RIM_OUT, 0); at(1, rMid, -RIM_W * 0.5); at(2, rMid, RIM_W * 0.5); at(3, RIM_IN, 0);
    for (var k = 4; k <= 12; k++) at(k, RIM_OUT, 0, 0.02);
    at(13, RIM_IN, -0.0035); at(14, RIM_IN, 0, 0.02); at(15, RIM_IN, 0.0035);
    at(16, RIM_IN - PTR_LEN * 0.45, -0.0028); at(17, RIM_IN - PTR_LEN * 0.45, 0, 0.015); at(18, RIM_IN - PTR_LEN * 0.45, 0.0028);
    at(19, RIM_IN - PTR_LEN * 0.8, -0.0018); at(20, RIM_IN - PTR_LEN * 0.8, 0, 0.01); at(21, RIM_IN - PTR_LEN * 0.8, 0.0018);
    at(22, rTip, 0, 0.005);
  }

  /* 从真实顶点缓冲量刻标几何（供验收断言，不信任常量）：单位 R */
  function rimGeom() {
    if (!pos || !(rimR > 0)) return null;
    function rad(i) { var b = i * 3; return Math.sqrt(pos[b] * pos[b] + pos[b + 1] * pos[b + 1]) / rimR; }
    var bx = (pos[13 * 3] + pos[15 * 3]) / 2, by = (pos[13 * 3 + 1] + pos[15 * 3 + 1]) / 2,
      dx = pos[22 * 3] - bx, dy = pos[22 * 3 + 1] - by, minR = Infinity, maxR = 0, i, r;
    for (i = 0; i <= 22; i++) { r = rad(i); if (r < minR) minR = r; if (r > maxR) maxR = r; }
    return { pointerLen: r4(Math.sqrt(dx * dx + dy * dy) / rimR), tickIn: r4(rad(3)), tickOut: r4(rad(0)), minR: r4(minR), maxR: r4(maxR), hubR: r4(rad(12)) };
  }

  function beadFor(desc, ev) {
    var arr = (desc && desc.beads) ? desc.beads : [], best = null, i, b, m;
    for (i = 0; i < arr.length; i++) {
      b = arr[i];
      m = (b.evIdx != null && b.evIdx === ev) || (b.i != null && b.i === ev) || (b.order != null && b.order === ev) || (b.ev != null && b.ev === ev);
      if (m && (!best || (finite(b.r) ? b.r : 0) > (finite(best.r) ? best.r : 0))) best = b;
    }
    return best;
  }

  function spectral(v) { try { var sp = g.CLOrbit3DSpectral; if (sp && sp.setRead) sp.setRead(v); } catch (e) {} }

  function approach(cur, target, k) {
    var d = target - cur;
    while (d > Math.PI) d -= TWO;
    while (d < -Math.PI) d += TWO;
    return k >= 1 ? target : cur + d * k;
  }

  function build(o) {
    try {
      T = o && o.T;
      var layer = g.CLOrbit3DLayer;
      if (!T || !layer || !layer.spinObject) return;
      var spin = layer.spinObject();
      if (!spin) return;

      var V_COUNT = 27;
      pos = new Float32Array(V_COUNT * 3);
      var aArr = new Float32Array(V_COUNT), sArr = new Float32Array(V_COUNT), pArr = new Float32Array(V_COUNT);

      // 配重尾 (0..3)
      aArr[0] = 0.5; sArr[0] = 0.0; pArr[0] = 2.0;
      aArr[1] = 0.85; sArr[1] = -1.0; pArr[1] = 2.0;
      aArr[2] = 0.85; sArr[2] = 1.0; pArr[2] = 2.0;
      aArr[3] = 0.95; sArr[3] = 0.0; pArr[3] = 2.0;

      // 轴盘 (4..12)
      for (var k = 0; k < 8; k++) {
        aArr[4 + k] = 0.95;
        sArr[4 + k] = 1.0;
        pArr[4 + k] = 1.0;
      }
      aArr[12] = 1.0; sArr[12] = 0.0; pArr[12] = 1.0;

      // 剑身与针尖 (13..22)
      aArr[13] = 0.95; sArr[13] = -1.0; pArr[13] = 0.0;
      aArr[14] = 1.00; sArr[14] = 0.0; pArr[14] = 0.0;
      aArr[15] = 0.95; sArr[15] = 1.0; pArr[15] = 0.0;

      aArr[16] = 0.90; sArr[16] = -1.0; pArr[16] = 0.0;
      aArr[17] = 1.00; sArr[17] = 0.0; pArr[17] = 0.0;
      aArr[18] = 0.90; sArr[18] = 1.0; pArr[18] = 0.0;

      aArr[19] = 0.95; sArr[19] = -1.0; pArr[19] = 0.0;
      aArr[20] = 1.00; sArr[20] = 0.0; pArr[20] = 0.0;
      aArr[21] = 0.95; sArr[21] = 1.0; pArr[21] = 0.0;

      aArr[22] = 1.00; sArr[22] = 0.0; pArr[22] = 0.0;

      // 光柱 Pillar (23..26)
      aArr[23] = 0.9; aArr[24] = 0.9; aArr[25] = 0.0; aArr[26] = 0.0;
      sArr[23] = -1.0; sArr[24] = 1.0; sArr[25] = 1.0; sArr[26] = -1.0;
      pArr[23] = 3.0; pArr[24] = 3.0; pArr[25] = 3.0; pArr[26] = 3.0;

      geom = new T.BufferGeometry();
      posAttr = new T.BufferAttribute(pos, 3);
      geom.setAttribute('position', posAttr);
      geom.setAttribute('aA', new T.BufferAttribute(aArr, 1));
      geom.setAttribute('aS', new T.BufferAttribute(sArr, 1));
      geom.setAttribute('aPart', new T.BufferAttribute(pArr, 1));

      var indices = [
        // 尾部 2 个三角形
        0, 1, 3,  0, 3, 2,
        // 轴盘 8 个扇形三角形
        12, 4, 5,   12, 5, 6,   12, 6, 7,   12, 7, 8,
        12, 8, 9,   12, 9, 10,  12, 10, 11, 12, 11, 4,
        // 针身 根部到中腰
        13, 16, 17,  13, 17, 14,
        14, 17, 18,  14, 18, 15,
        // 针身 中腰到肩部
        16, 19, 20,  16, 20, 17,
        17, 20, 21,  17, 21, 18,
        // 针身 肩部到针尖
        19, 22, 20,  20, 22, 21,
        // 光柱 2 个三角形
        23, 24, 25,  23, 25, 26
      ];
      geom.setIndex(new T.BufferAttribute(new Uint16Array(indices), 1));

      mat = new T.ShaderMaterial({
        uniforms: { uCol: { value: resolveCol(T) }, uFade: { value: 1 }, uK: { value: 1 } },
        vertexShader: NEEDLE_VS, fragmentShader: NEEDLE_FS,
        transparent: true, blending: T.AdditiveBlending, depthTest: false, depthWrite: false, side: T.DoubleSide
      });
      colNeedle = mat.uniforms.uCol.value.clone();
      colRim = resolveRimCol(T) || colNeedle.clone();
      mesh = new T.Mesh(geom, mat);
      mesh.renderOrder = -19; mesh.frustumCulled = false; mesh.raycast = function () {};
      spin.add(mesh);
      placeNeedle(0, 1); placePillar(0, 0, 0, 1, false);
      posAttr.needsUpdate = true;
      ready = true;
    } catch (e) { ready = false; }
  }

  /* v90 年轮刻标态：只认游标/焦点事件（focusEv），不跟读头巡航 pulse；无焦点 = 整件不画 */
  function updateRim(V, st, sel, t, R, fade) {
    var desc = null, target = null, rb = R, zb = 1.4;
    if (sel) {
      try { desc = V.desc ? V.desc() : null; } catch (e) {}
      if (desc) {
        if ((!R || R === 1) && finite(desc.R) && desc.R) R = desc.R;
        var a = desc.angleOf ? desc.angleOf[st.focusEv] : null;
        if (finite(a)) target = a;
        var b = beadFor(desc, st.focusEv);
        if (b && finite(b.r)) rb = b.r;
      }
      var ev = null;
      try { ev = V.eventAt ? V.eventAt(st.focusEv) : null; } catch (e2) {}
      var w = (ev && finite(ev.w)) ? ev.w : 0;
      zb = 1.4 + w * 6.5 + w * 0.012 * R;
    }
    rimR = R;
    if (target === null) {
      mesh.visible = false; visibleNow = false; angleVal = null; rimShown = false; tw = null; rimTarget = null; focusNow = -1; pillarNow = false;
      spectral(null); return;
    }
    var snap = reduced() || lowTier();
    if (!rimShown || snap) { tw = null; angDraw = target; }
    else if (rimTarget === null || Math.abs(wrapPi(target - rimTarget)) > 1e-6) {
      tw = { from: angDraw, to: target, t0: t, dur: dur1() };
    }
    rimTarget = target;
    if (tw) {
      var k = tw.dur > 0 ? (t - tw.t0) / tw.dur : 1;
      if (!finite(k) || k >= 1 || k < 0) { angDraw = tw.to; tw = null; }
      else angDraw = tw.from + wrapPi(tw.to - tw.from) * easeOut(k);
    }
    placeRim(angDraw, R);
    placePillar(angDraw, rb, zb, R, true);
    posAttr.needsUpdate = true;
    if (colRim) mat.uniforms.uCol.value.copy(colRim);
    mat.uniforms.uFade.value = fade;
    mat.uniforms.uK.value = 1;
    mesh.visible = true; visibleNow = true; rimShown = true; pillarNow = true; focusNow = st.focusEv;
    angleVal = r4(angDraw);
    spectral(angDraw);
  }

  function update(s) {
    if (!ready || !mesh) { build({ T: T || g.THREE }); if (!ready || !mesh) return; }
    try {
      var sp2 = g.CLOrbit3DLayer && g.CLOrbit3DLayer.spinObject ? g.CLOrbit3DLayer.spinObject() : null;
      if (sp2 && mesh.parent !== sp2) sp2.add(mesh);
    } catch (e0) {}
    updates++;
    var t = (s && finite(s.t)) ? s.t : 0, dt = lastT < 0 ? 0 : t - lastT;
    lastT = t;
    if (!finite(dt) || dt < 0) dt = 0;
    if (dt > 0.1) dt = 0.1;
    var ls = layerStats(), fade = (ls && finite(ls.fade)) ? ls.fade : 1, R = (ls && ls.R) ? ls.R : 1;
    var V = g.CLPlotOrbitView, vis = false;
    if (V && V.visible) { try { vis = !!V.visible(); } catch (e) { vis = false; } }
    rimNow = annulusOn();
    if (!vis) { mesh.visible = false; visibleNow = false; angleVal = null; rimShown = false; tw = null; spectral(null); return; }
    var st = null, ms = null;
    try { st = V.state ? V.state() : null; } catch (e) {}
    try { ms = V.motion ? V.motion().state() : null; } catch (e) {}
    var sel = !!(st && finite(st.focusEv) && st.focusEv >= 0), target = null, rb = R, zb = 1.4;
    if (rimNow) { updateRim(V, st, sel, t, R, fade); return; }
    rimShown = false; tw = null;
    if (colNeedle) mat.uniforms.uCol.value.copy(colNeedle);
    if (sel) {
      var desc = null;
      try { desc = V.desc ? V.desc() : null; } catch (e) {}
      if (desc) {
        if ((!R || R === 1) && finite(desc.R) && desc.R) R = desc.R;
        var a = desc.angleOf ? desc.angleOf[st.focusEv] : null;
        if (finite(a)) target = a;
        var b = beadFor(desc, st.focusEv);
        if (b && finite(b.r)) rb = b.r;
      }
      var ev = null;
      try { ev = V.eventAt ? V.eventAt(st.focusEv) : null; } catch (e) {}
      var w = (ev && finite(ev.w)) ? ev.w : 0;
      zb = 1.4 + w * 6.5 + w * 0.012 * R;
    } else if (ms && ms.pulse && finite(ms.pulse.a)) { target = ms.pulse.a; }
    if (target === null) { mesh.visible = false; visibleNow = false; angleVal = null; spectral(null); return; }
    var motionOn = (reduced() || tierVal() === 2) ? 0 : 1;
    if (!sel && motionOn) {
      // 读头光点巡航：时针与光点严格同相位对齐，消除稳态滞后
      var diff = target - angDraw;
      while (diff > Math.PI) diff -= TWO;
      while (diff < -Math.PI) diff += TWO;
      if (Math.abs(diff) > 0.08) {
        angDraw += diff * Math.min(1, dt * 16);
      } else {
        angDraw = target;
      }
    } else {
      angDraw = approach(angDraw, target, motionOn ? Math.min(1, dt * 8) : 1);
    }
    placeNeedle(angDraw, R);
    placePillar(angDraw, rb, zb, R, sel);
    posAttr.needsUpdate = true;
    mat.uniforms.uFade.value = fade;
    mat.uniforms.uK.value = sel ? 1 : 0.85;
    mesh.visible = true; visibleNow = true; pillarNow = sel; focusNow = sel ? st.focusEv : -1;
    angleVal = r4(angDraw);
    spectral(sel ? angDraw : null);
  }

  function stats() {
    var rim = (rimNow && visibleNow) ? rimGeom() : null;
    return { name: NAME, version: VERSION, ready: ready, visible: visibleNow, angle: visibleNow ? angleVal : null,
      pillar: pillarNow, focusEv: focusNow, motion: (reduced() || tierVal() === 2) ? 0 : 1, reduced: reduced(), updates: updates,
      /* v90：mode = 'rim'（年轮盘缘刻标）| 'needle'（经典钟表读针）；hub = 盘心针帽是否在画；rim = 实测顶点几何（单位 R） */
      mode: rimNow ? 'rim' : 'needle', hub: visibleNow && !rimNow, tweening: !!tw, target: rimTarget === null ? null : r4(rimTarget),
      rim: rim };
  }

  function dispose() {
    try {
      if (mesh && mesh.parent) mesh.parent.remove(mesh);
      if (geom && geom.dispose) geom.dispose();
      if (mat && mat.dispose) mat.dispose();
    } catch (e) {}
    mesh = null; geom = null; mat = null; pos = null; posAttr = null; ready = false; visibleNow = false; angleVal = null;
  }

  function skip() {
    try { var q = (g.location && g.location.search) ? g.location.search : ''; return q.indexOf('tree=1') >= 0 || q.indexOf('treestage=1') >= 0; } catch (e) { return false; }
  }

  g.CLOrbit3DNeedle = { name: NAME, version: VERSION, stats: stats, dispose: dispose };
  if (!skip() && g.CLArcana && g.CLArcana.register) {
    try { g.CLArcana.register({ name: NAME, build: build, update: update }); } catch (e) {}
  }
})(window);
