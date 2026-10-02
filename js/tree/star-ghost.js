/* @role particle · @owns js/star-ghost.js · @budget dom_nodes=0 points=27 drawcalls=1 · @contract v41 */
(function () {
  'use strict';

  var FALLBACK = '#8fb8ff'; // 唯一允许的裸 hex：node.color 缺失/不可解析时的兜底色（契约 v42.1 明确放行）
  var SZ_MIN = 3, SZ_MAX = 5; // px：v45 单位规格收紧为「size 上限 5px」，故裸 px 属契约放行例外
  var OP_HI = 0.07, OP_LOW = 0.04;   // v45：剧情线态已有真实星点作前景，虚影星压到很淡（高档 0.07 / 低档 0.04）
  var FLOOR = 0.004, STEP = 0.08, POLL_MS = 100, POLL_MAX = 150;

  var ready = false, on = true, built = false, tier = 'high';
  var opacity = 0, count = 0, state = 'stars', first = [0, 0, 0];
  var geo = null, mat = null, pts = null, parent = null;
  var rafId = 0, pollId = 0, tries = 0, sizeHi = SZ_MAX;
  var texSprite = null;

  function lowPower() {
    try {
      if (document.documentElement.dataset.tier === 'low') return true;
      return (navigator.hardwareConcurrency || 8) <= 4;
    } catch (e) { return false; }
  }
  function reduced() {
    try { return matchMedia('(prefers-reduced-motion: reduce)').matches; }
    catch (e) { return false; }
  }
  function movement() {
    var m = window.CLStarMigrate;
    if (!m || typeof m.stats !== 'function') return { state: 'stars', k: 0 };
    var s = m.stats() || {};
    return { state: s.state || 'stars', k: (typeof s.k === 'number' ? s.k : 0) };
  }

  function colorOf(node) {
    var c = new THREE.Color(FALLBACK), v = node && node.color;
    if (v && v.isColor) { c.setRGB(v.r, v.g, v.b); return c; }
    if (typeof v === 'string' || typeof v === 'number') {
      try { c.set(v); } catch (e) { c.set(FALLBACK); }
    }
    return c;
  }

  function applySize() {
    if (mat) mat.size = (tier === 'low') ? sizeHi * 0.5 : sizeHi;
  }

  /* v45：64x64 圆形径向 alpha 贴图。过去 PointsMaterial 不带 map，每个点是一个方口
   *  —— 加性混合下方形边缘会在亮点外围留下一圈硬拐角，压暗后尤其像"脏点"。
   *  贴图让虚影星变成柔和圆斑；透明处 alpha=0，不会再多染一圈。 */
  function makeSprite() {
    try {
      var c = document.createElement('canvas');
      c.width = 64; c.height = 64;
      var g = c.getContext('2d');
      if (!g) return null;
      var grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
      grad.addColorStop(0.0, 'rgba(255,255,255,1)');
      grad.addColorStop(0.5, 'rgba(255,255,255,0.55)');
      grad.addColorStop(1.0, 'rgba(255,255,255,0)');
      g.fillStyle = grad;
      g.fillRect(0, 0, 64, 64);
      var tx = new THREE.CanvasTexture(c);
      tx.needsUpdate = true;
      return tx;
    } catch (e) { return null; }
  }

  function build() {
    if (built || !ready || !window.THREE) return;
    var sc = window.__cl && window.__cl.scene;
    /* 主控修（契约勘误）：constellation().list 是阵营标签串（"曜庭王枢:主角方:8"），不是名单。
     * 角色名唯一可靠源是 scene.camps()[i].members；兜底 CLStory.get().cast 的键。 */
    var names = [], i, j, g, camps = null, cast = null;
    try { camps = sc && sc.camps ? sc.camps() : null; } catch (e1) { camps = null; }
    if (camps && camps.length) {
      for (i = 0; i < camps.length; i++) {
        g = camps[i] && camps[i].members;
        if (g && g.length) for (j = 0; j < g.length; j++) names.push(String(g[j]));
      }
    }
    if (!names.length) {
      try { cast = window.CLStory && CLStory.get ? CLStory.get().cast : null; } catch (e2) { cast = null; }
      if (cast) for (var k in cast) if (Object.prototype.hasOwnProperty.call(cast, k)) names.push(k);
    }
    if (!names.length) return;
    var pos = [], col = [], wsum = 0, m = 0, node, cc, w;
    for (i = 0; i < names.length; i++) {
      node = null;
      try { node = sc.nodeOf('c:' + names[i]); } catch (e) { node = null; }
      if (!node || !node.atlas) continue;
      pos.push(+node.atlas.x || 0, +node.atlas.y || 0, +node.atlas.z || 0);
      cc = colorOf(node);
      col.push(cc.r, cc.g, cc.b);
      /* 主控修（契约勘误）：node.w 实为 importance 0–100，不是 0–1；>1 就按百分制归一，再硬夹 —— 否则点被算成 200px，加性+Bloom 直接糊白整屏 */
      w = (typeof node.w === 'number' && isFinite(node.w)) ? node.w : 0.5;
      if (w > 1) w = w / 100;
      wsum += Math.max(0, Math.min(1, w));
      m++;
    }
    if (!m) return;
    count = m;
    sizeHi = SZ_MIN + (wsum / m) * (SZ_MAX - SZ_MIN);
    if (!(sizeHi >= SZ_MIN && sizeHi <= SZ_MAX)) sizeHi = SZ_MIN;   /* 双保险：任何异常都回最小尺寸 */
    geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    mat = new THREE.PointsMaterial({
      vertexColors: true, transparent: true, opacity: 0,
      depthWrite: false, sizeAttenuation: false,
      blending: THREE.AdditiveBlending, size: sizeHi
    });
    texSprite = makeSprite();
    if (texSprite) { mat.map = texSprite; mat.needsUpdate = true; }
    pts = new THREE.Points(geo, mat);
    pts.raycast = function () {};
    pts.renderOrder = -40;
    pts.visible = false;
    pts.frustumCulled = false;
    try { parent = window.CLTreeAnchor.root().parent; } catch (e) { parent = null; }
    if (!parent) { geo.dispose(); mat.dispose(); if (texSprite) { texSprite.dispose(); texSprite = null; } geo = mat = pts = null; return; }
    parent.add(pts);
    first = [pos[0], pos[1], pos[2]];
    built = true;
    applySize();
    loop();
  }

  function update() {
    /* 主控修：同步推帧（无头 pump）时 setInterval 不触发，靠 update() 自己补一次 build，避免永远 ready:false */
    if (!ready) { try { tryReady(); } catch (e0) {} if (!ready) return; }
    if (!ready || !built || !mat || !pts) return;
    var st = movement();
    state = st.state;
    var want = (state !== 'stars') ? (tier === 'low' ? OP_LOW : OP_HI) * (st.k || 0) : 0;
    if (reduced() || lowPower()) {
      opacity = want;
    } else if (opacity < want) {
      opacity = Math.min(want, opacity + STEP);
    } else if (opacity > want) {
      opacity = Math.max(want, opacity - STEP);
    }
    mat.opacity = opacity;
    pts.visible = opacity > FLOOR;
  }

  function loop() {
    if (rafId) return;
    var tick = function () {
      rafId = 0;
      if (on) update();
      rafId = window.requestAnimationFrame(tick);
    };
    rafId = window.requestAnimationFrame(tick);
  }

  function tryReady() {
    var cl = window.__cl, A = window.CLTreeAnchor;
    if (window.THREE && A && typeof A.ready === 'function' && A.ready() &&
        cl && cl.scene && typeof cl.scene.nodeOf === 'function') {
      ready = true;
      build();
      return true;
    }
    return false;
  }

  pollId = window.setInterval(function () {
    tries++;
    /* 星空壳里树锚点永不就绪：第一拍就停，不再 10 Hz 空轮询 15 s */
    if (tryReady() || tries >= POLL_MAX || (window.CLSky && CLSky.enabled && CLSky.enabled())) {
      window.clearInterval(pollId);
      pollId = 0;
    }
  }, POLL_MS);

  function setOn(b) {
    on = !!b;
    if (on && built) loop();
  }
  function setTier(t) {
    tier = (t === 'low') ? 'low' : 'high';
    applySize();
  }
  function dispose() {
    if (rafId) { window.cancelAnimationFrame(rafId); rafId = 0; }
    if (pollId) { window.clearInterval(pollId); pollId = 0; }
    if (pts && parent) parent.remove(pts);
    if (geo) geo.dispose();
    if (mat) mat.dispose();
    if (texSprite) { texSprite.dispose(); texSprite = null; }
    geo = mat = pts = parent = null;
    built = false; ready = false; opacity = 0;
  }
  function stats() {
    if (!ready) { try { tryReady(); } catch (e0) {} }   /* 主控修：星座态下被问到就先就绪（pump 模式没有 setInterval） */
    return {
      ready: ready, on: on, count: count, opacity: opacity,
      visible: !!(pts && pts.visible), tier: tier, state: state,
      texture: !!texSprite,
      first: first.slice ? first.slice() : [first[0], first[1], first[2]]
    };
  }

  window.CLStarGhost = {
    name: 'star-ghost',
    build: build,
    update: update,
    setOn: setOn,
    setTier: setTier,
    dispose: dispose,
    stats: stats
  };
})();
