/*!
 * @role tugfx
 * @owns js/sky/sky-tug-fx.js
 * @budget drawcalls=1 points=0 vertices=94 rtpx=0 passes=0 fps=60
 * @contract deep-sky/3
 * 牵引光效（Q1.4 · Q8.4）：听 CLSkyTug.on（grab → release → sleep），S.group 下一张网格（layer 0，1 draw call）：家位幽环（回弹随距离收拢）·
 * 牵引丝（冷青 → 张力色，回弹驻波按 SPRING.back 包络）· 抓取 / 归位涟漪 · 笔尖彗星。一跳网络点亮走悬停同一路径（S.setHover + CLSkyDeep），松手复原。
 * 逐帧只读节点（星 = n.g.position，家 = 星 − n.tugO），零 new；无事即 visible = false 并摘钩子。减弱动效：只留静态幽环与丝；low 档：不画。
 * 着色器在 sky-tug-fx-glsl.js；探针 stats() · _hold(on)。
 */
(function (g) {
  'use strict';
  var doc = g.document;
  /* 秒 · CSS px · 峰值亮度；环半径以悬停静环为 1 */
  var FX = { lost: 3, end: 0.45, ghost: 0.38, tether: [0.46, 0.34], sig: [0.62, 0.44], wave: { px: [2.2, 5.6], hk: 2, h2: 0.35 },
    comet: { every: 0.9, first: 0.36, run: 0.52, tail: 0.2, kill: 0.12 }, grab: { dur: 0.46, grow: 20, a: 0.85 }, settle: { dur: 0.56, grow: 15, a: 0.42, r: 0.7 } };
  var S = null, TK = null, mesh = null, U = null, unhook = null, tug = null, heard = null, G0 = null, qd = false;
  var ph = 'idle', key = null, name = null, node = null, lit = null, prev = null, ls = null, ring = false, red = false, hold = false, deg = 0, Rm = 1;
  var tA = 0, tRel = 0, tSl = -1, gAge = -1, cT = 0, cAge = -1, cKill = -1, nCom = 0, relTen = 0, ten = 0, e1 = 1, COOL = 0, WARM = 0;

  function sst(a, b, x) { var t = (x - a) / (b - a); t = t < 0 ? 0 : t > 1 ? 1 : t; return t * t * (3 - 2 * t); }
  function sky() { return !!(g.CLSky && CLSky.enabled && CLSky.enabled()); }
  function deep() { var D = g.CLSkyDeep; return D && D.enabled && D.enabled() && D.hoverStar ? D : null; }
  function graph() { var A = g.CLApp; return A && A.graph ? A.graph() : null; }
  function cur() { return g.CLScene ? CLScene.current : null; }

  function build() {
    var T = g.THREE, GL = g.CLSkyTugFxGLSL, C = TK.C, P = [], I = [], N = 40, i, b, geo = new T.BufferGeometry();
    for (i = 0; i <= N; i++) P.push(i / N, -1, 0, i / N, 1, 0);
    for (i = 0; i < N; i++) { b = i * 2; I.push(b, b + 1, b + 2, b + 1, b + 3, b + 2); }
    for (i = 1; i <= 3; i++) { b = P.length / 3; P.push(-1, -1, i, 1, -1, i, 1, 1, i, -1, 1, i); I.push(b, b + 1, b + 2, b, b + 2, b + 3); }
    geo.setAttribute('position', new T.Float32BufferAttribute(P, 3)); geo.setIndex(I);
    function v(x) { return { value: x }; }
    COOL = TK.mix(C.MINT, C.STAR_COOL, 0.3); WARM = C.BRASS_HOT;
    U = { uA: v(new T.Vector3()), uB: v(new T.Vector3()), uRes: v(new T.Vector2(1, 1)), uDpr: v(1), uTA: v(0), uSz: v(1), uEnd: v(1), uSig: v(0.6), uWave: v(new T.Vector2()),
      uCom: v(new T.Vector3()), uR1: v(new T.Vector4(0, 0, 0, 0)), uR2: v(new T.Vector4(0, 0, 0, 0)), uR3: v(new T.Vector4(0, 0, 0, 0)), uCol: v(new T.Color(COOL)), uColG: v(new T.Color(COOL)),
      uColR: v(new T.Color(TK.mix(WARM, C.STAR_WHITE, 0.45))), uColS: v(new T.Color(TK.mix(COOL, C.STAR_WHITE, 0.3))) };
    mesh = new T.Mesh(geo, new T.ShaderMaterial({ uniforms: U, vertexShader: GL.VS, fragmentShader: GL.FS, transparent: true, depthWrite: false, depthTest: false,
      blending: T.AdditiveBlending, premultipliedAlpha: true, side: T.DoubleSide }));
    mesh.name = 'sky-tug-fx'; mesh.frustumCulled = false; mesh.renderOrder = 4; mesh.visible = false;
    S.group.add(mesh);
  }
  function free() {
    drop();
    if (mesh) { if (mesh.parent) mesh.parent.remove(mesh); mesh.geometry.dispose(); mesh.material.dispose(); }
    mesh = U = null;
  }
  function ensure() {
    var s = cur(), t = g.CLSkyTug;
    TK = g.CLSkyTokens;
    if (!t || typeof t.on !== 'function' || !sky() || !s || !s.group || !s.registerFrameHook || !g.THREE || !TK || !TK.SPRING || !TK.TUG || !g.CLSkyTugFxGLSL) return false;
    if (s !== S || !mesh) { free(); S = s; build(); }
    if (heard !== S && S.on) { heard = S; S.on('hover', onHover); }
    if (t !== tug) { tug = t; t.on(onEv); }
    return true;
  }
  function hook(on) {
    if (on && !unhook && S) unhook = S.registerFrameHook(frame);
    else if (!on && unhook) { var u = unhook; unhook = null; u(); }
  }

  /* 一跳 = skyView 关系（同 sky-deep 悬停）∪ n1；add = n1 新增数 */
  function hopOf(n1) {
    var A = g.CLApp, V = A && A.atlas && A.atlas.skyView ? A.atlas.skyView() : graph(), rel = (V && V.relations) || [], set = {}, out = [name], add = 0, i, x, r;
    set[name] = 1;
    for (i = 0; i < rel.length; i++) { r = rel[i]; x = r.a === name ? r.b : r.b === name ? r.a : null; if (x && !set[x]) { set[x] = 1; out.push(x); } }
    for (i = 0; n1 && i < n1.length; i++) { x = String(n1[i]).replace(/^c:/, ''); if (!set[x]) { set[x] = 1; out.push(x); add++; } }
    return { list: out, add: add };
  }
  /* 有 quiet 版 hoverStar（不弹星卡）就用；否则：抓前已悬停这颗 → 原样；未悬停（触屏）→ 不碰星卡（会弹在旧指针处），只点亮集。re = 锁回 */
  function quiet(D) { return !!D && D.hoverStar.length > 1; }
  function paint(re) {
    var D = deep();
    if (S.hoverName() !== lit) S.setHover(lit);
    if (!D) return;
    if (quiet(D)) D.hoverStar(lit, true); else if (re) D.hoverStar(ring ? lit : null);
    if (ls.add || !ring) D.light(ls.list);
  }
  function light(st) {
    if (!name || lit === name || !S.setHover) return;
    prev = S.hoverName(); lit = name; ls = hopOf(st && st.n1);
    ring = quiet(deep()) || prev === lit; e1 = U.uEnd.value = ring ? 1 : FX.end;
    paint(0);
  }
  /* silent：换书 / 重建，旧名不写回（光层点亮集清掉）；同一颗星静默复原（不闪回星卡） */
  function unlight(silent) {
    var was = lit, h = silent ? null : prev, D = deep(), chg = !!ls && (quiet(D) || !ring || ls.add > 0);
    lit = prev = ls = null;
    if (!was || !S) return;
    if (!silent && S.hoverName() !== h) S.setHover(h);
    if (D && chg) D.hoverStar(h, !!h && h === was);
  }
  function relock() { qd = false; if (ph === 'drag' && lit) paint(1); }
  /* 拖动中悬停被换走：本轮分发完再锁回；回弹中只改丝的星端 */
  function onHover(e) {
    if (ph === 'back') { e1 = e && e.name === name ? 1 : FX.end; return; }
    if (ph !== 'drag' || !lit || qd || (e && e.name === lit)) return;
    qd = true;
    g.Promise.resolve().then(relock);
  }

  function onEv(e) {
    try {
      if (!e || !mesh || !S) return;
      var k = e.key || (e.name ? 'c:' + e.name : null);
      if (e.type === 'grab') grab(k, e.name);
      else if (k !== key) return;
      else if (S.nodeOf(k) !== node || graph() !== G0) drop();   /* 硬收：静默 */
      else if (e.type === 'release' && ph === 'drag') back();
      else if (e.type === 'sleep' && ph !== 'idle') settle();
    } catch (err) { warn(err); }
  }
  function grab(k, nm) {
    var st = null, info = S.skyInfo();
    if (!k) return;
    if (ph === 'idle' || k !== key) tA = 0;   /* 回弹中又抓同一颗：丝不重淡入 */
    if (key && k !== key) unlight();
    try { st = tug.state(); } catch (x) {}
    key = k; name = nm || k.slice(2); node = S.nodeOf(k); G0 = graph(); Rm = TK.TUG.maxR * ((info && info.R) || 380);
    ph = 'drag'; red = !!TK.reduced(); tRel = 0; tSl = -1; gAge = red ? -1 : 0; cT = FX.comet.every - FX.comet.first; cAge = cKill = -1;
    if (!node) return done();
    light(st); hook(true); frame(0, 0, 0, false, deg);
  }
  function back() { ph = 'back'; tRel = 0; relTen = ten; red = !!TK.reduced(); if (cAge >= 0) cKill = 0; e1 = prev === name ? 1 : FX.end; unlight(); }
  function settle() { if (ph === 'drag') back(); ph = 'idle'; tSl = red ? -1 : 0; cAge = -1; unlight(); }
  function done() { ph = 'idle'; tSl = gAge = cAge = -1; key = name = node = G0 = null; if (mesh) mesh.visible = false; hook(false); }
  function drop() { unlight(true); done(); }

  /* 只在拖动 / 回弹 / 涟漪未完时挂着 */
  function frame(dt, tAcc, tAnim, calm, degrade) {
    if (!mesh || !S) return;
    deg = degrade | 0;
    var d = hold ? 0 : Math.min(0.05, Math.max(0, dt || 0)), u = U, bc = doc.body.classList, o, q, e, k, fin, live, dpr, B, wd, env, A0;
    if (!node || cur() !== S || S.nodeOf(key) !== node || graph() !== G0) return drop();
    if (ph !== 'idle') { tA += d; if (ph === 'back' && (tRel += d) > FX.lost) settle(); }
    if (tSl >= 0 && (tSl += d) >= FX.settle.dur) tSl = -1;
    if (gAge >= 0 && (gAge += d) >= FX.grab.dur) gAge = -1;
    if (ph === 'idle' && tSl < 0) return done();
    if (TK.tierOf(degrade) === 'low' || bc.contains('sky-plot-on') || bc.contains('sky-compass-on') || !sky()) { mesh.visible = false; return; }
    o = node.tugO; live = ph !== 'idle';
    u.uB.value.copy(node.g.position); u.uA.value.copy(u.uB.value); if (o) u.uA.value.sub(o);
    ten = o && live ? Math.min(1, o.length() / Rm) : 0;
    if (node.size > 0) u.uSz.value = node.size;
    dpr = S.renderer.getPixelRatio() || 1; S.renderer.getDrawingBufferSize(u.uRes.value); u.uDpr.value = dpr;
    k = sst(0.08, 0.92, ten); fin = red ? 1 : sst(0, TK.DUR.flick, tA);
    u.uCol.value.setHex(TK.mix(COOL, WARM, k)); u.uColG.value.setHex(TK.mix(COOL, WARM, k * 0.3));
    u.uTA.value = live ? (FX.tether[0] + FX.tether[1] * ten) * fin : 0;
    u.uEnd.value += (e1 - u.uEnd.value) * (red ? 1 : 1 - Math.exp(-d / 0.045));
    u.uSig.value = (FX.sig[0] + (FX.sig[1] - FX.sig[0]) * ten) * dpr;
    u.uR1.value.set(1, 0, 0.55 * dpr, live ? FX.ghost * fin * (0.8 + 0.2 * ten) : 0);
    /* 驻波：包络 e^(−ζωt)，弦频 = 阻尼频率 × hk */
    if (ph === 'back' && !red) {
      B = TK.SPRING.back; wd = B.w * Math.sqrt(1 - B.z * B.z) * FX.wave.hk; env = Math.exp(-B.z * B.w * tRel); A0 = (FX.wave.px[0] + (FX.wave.px[1] - FX.wave.px[0]) * relTen) * dpr;
      u.uWave.value.set(A0 * env * Math.sin(wd * tRel), FX.wave.h2 * A0 * env * env * Math.sin(2 * wd * tRel));
    } else u.uWave.value.set(0, 0);
    /* 彗星：离家 > 1.3 星径才发；松手 kill 秒内熄 */
    if (ph === 'drag' && !red && (cT += d) >= FX.comet.every && cAge < 0 && u.uA.value.distanceTo(u.uB.value) > 1.3 * u.uSz.value) { cAge = 0; cT = 0; nCom++; }
    if (cAge >= 0) {
      cAge += d; q = cAge / FX.comet.run; if (cKill >= 0) cKill += d;
      if (q >= 1 || red || cKill >= FX.comet.kill) { cAge = cKill = -1; u.uCom.value.y = 0; }
      else u.uCom.value.set(Math.pow(q, 1.25), sst(0, 0.1, q) * (1 - sst(0.86, 1, q)) * (cKill >= 0 ? 1 - cKill / FX.comet.kill : 1), FX.comet.tail);
    } else u.uCom.value.y = 0;
    /* 涟漪：grab @星，sleep @家 */
    if (gAge >= 0 && !red) { q = gAge / FX.grab.dur; e = 1 - Math.pow(1 - q, 3); u.uR2.value.set(1, e * FX.grab.grow * dpr, (0.55 + 0.6 * e) * dpr, FX.grab.a * Math.pow(1 - q, 1.6) * sst(0, 0.05, gAge)); }
    else u.uR2.value.w = 0;
    if (tSl >= 0) { q = tSl / FX.settle.dur; e = 1 - Math.pow(1 - q, 3); u.uR3.value.set(FX.settle.r, e * FX.settle.grow * dpr, (0.5 + 0.4 * e) * dpr, FX.settle.a * Math.pow(1 - q, 1.6) * sst(0, 0.04, tSl)); }
    else u.uR3.value.w = 0;
    mesh.visible = true;
  }

  /* 换书：网格留着，状态静默清零 */
  function warn(e) { if (g.console) console.warn('[sky-tug-fx]', e); }
  function reset() { try { drop(); ensure(); } catch (e) { warn(e); } }
  doc.addEventListener('cl:graph-loading', drop, false);
  doc.addEventListener('cl:graph-ready', reset, false);

  function r3(x) { return Math.round(x * 1e3) / 1e3; }
  g.CLSkyTugFx = {
    stats: function () {
      var u = U;
      if (!u) return { installed: false, tug: !!tug };
      return { installed: true, visible: mesh.visible, hooked: !!unhook, tug: !!tug, phase: ph, key: key, lit: lit, ring: ring, tension: r3(ten), tether: r3(u.uTA.value),
        end: r3(u.uEnd.value), ghost: r3(u.uR1.value.w), wave: [r3(u.uWave.value.x), r3(u.uWave.value.y)], comet: { n: nCom, on: cAge >= 0, s: r3(u.uCom.value.x), a: r3(u.uCom.value.y) },
        ripple: { grab: r3(u.uR2.value.w), settle: r3(u.uR3.value.w) }, reduced: red, low: TK.tierOf(deg) === 'low' };
    },
    _hold: function (on) { hold = !!on; return hold; },
    refresh: function () { return ensure(); },
    dispose: free
  };
})(window);
