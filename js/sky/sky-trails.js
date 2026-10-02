/*! @role webgl (unit: trails) · @owns js/sky/sky-trails.js · @budget drawcalls=1 points=5600 vertices=5600 rtpx=0 passes=0 · @contract deep-sky/1 */
/* 星迁彗尾 trails：换分组时星在世界空间移动，身后拖一道渐隐光尾；静止时完全不可见。
   ES5 · three r128 · 无自有 rAF（宿主每帧 update）· 单 draw call（一个 Points）。
   降级路径 1：CLSkyTokens.reduced() 为真 → 所有 aA=0、不记历史。
   降级路径 2：setTier('low') → Points.visible=false、不记历史（非"少一点"，整体无光尾）。
   颜色不写字面量：一律取 setStars 传入的组色 hex（0xRRGGBB 数字）。 */

(function (g) {
  'use strict';

  var MAX = 350;   // 最多追踪星数（按咖位取前 350；K × MAX ≤ 点预算）
  var K = 16;      // 每星尾点数（点距小于光斑直径，连成一道而不是一串珠——串珠会被读成点线关系）
  var WIN = 0.4;   // 尾迹时间窗（秒）
  var HIST = 48;   // 每星历史样本上限（环形）
  var SPAN_MIN = 0.05;
  var A_PEAK = 0.34;
  var A_FADE = 8;
  var SPEED_LO = 0.05;
  var SPEED_SPAN = 0.25;

  var _s = { x: 0, y: 0, z: 0 };

  function clamp01(v) { return v < 0 ? 0 : (v > 1 ? 1 : v); }

  /* ---- 环形历史缓冲：head 为最老样本下标，n 为有效样本数 ---- */
  function hNew() { return { t: [], x: [], y: [], z: [], head: 0, n: 0 }; }
  function hClear(h) { h.n = 0; h.head = 0; }
  function hAt(h, k) { return (h.head + k) % HIST; }
  function hPush(h, t, x, y, z) {
    var i;
    if (h.n < HIST) { i = (h.head + h.n) % HIST; h.n++; }   /* 新样本接在队尾（head 被 hTrim 推进过，不能写在 n 号位） */
    else { i = h.head; h.head = (h.head + 1) % HIST; }
    h.t[i] = t; h.x[i] = x; h.y[i] = y; h.z[i] = z;
  }
  /* 丢掉比 cut 更老的样本，但恰好保留一个更老的样本供插值 */
  function hTrim(h, cut) {
    var k = 0;
    while (k < h.n - 1 && h.t[hAt(h, k)] < cut) k++;
    if (k > 0) { h.head = hAt(h, k - 1); h.n -= (k - 1); }
  }
  /* 按时间线性插值取样；比最老样本还早 → 用最老样本。返回共享对象 _s 或 null */
  function hSample(h, t) {
    var newest, k, i, j, ta, tb, w;
    if (h.n === 0) return null;
    if (h.n === 1) { i = h.head; _s.x = h.x[i]; _s.y = h.y[i]; _s.z = h.z[i]; return _s; }
    if (t <= h.t[h.head]) {
      i = h.head; _s.x = h.x[i]; _s.y = h.y[i]; _s.z = h.z[i]; return _s;
    }
    newest = (h.head + h.n - 1) % HIST;
    if (t >= h.t[newest]) { _s.x = h.x[newest]; _s.y = h.y[newest]; _s.z = h.z[newest]; return _s; }
    for (k = 0; k < h.n - 1; k++) {
      i = hAt(h, k); j = hAt(h, k + 1);
      ta = h.t[i]; tb = h.t[j];
      if (t >= ta && t <= tb) {
        w = tb > ta ? (t - ta) / (tb - ta) : 0;
        _s.x = h.x[i] + (h.x[j] - h.x[i]) * w;
        _s.y = h.y[i] + (h.y[j] - h.y[i]) * w;
        _s.z = h.z[i] + (h.z[j] - h.z[i]) * w;
        return _s;
      }
    }
    _s.x = h.x[newest]; _s.y = h.y[newest]; _s.z = h.z[newest];
    return _s;
  }

  var VS = 'attribute float aA;attribute float aSize;attribute vec3 aCol;'
    + 'uniform float uDpr;varying float vA;varying vec3 vCol;'
    + 'void main(){vA=aA;vCol=aCol;'
    + 'gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);'
    + 'gl_PointSize=aSize*uDpr;}';

  var FS = 'varying float vA;varying vec3 vCol;uniform float uAlpha;'
    + 'void main(){vec2 d=gl_PointCoord-0.5;float r2=dot(d,d)*4.0;if(r2>1.0)discard;'
    + 'float a=exp(-r2*3.4)*vA*uAlpha;gl_FragColor=vec4(vCol*a,a);}';

  g.CLSkyTrails = {
    create: function (opts) {
      var S = opts.scene;
      var THREE = g.THREE;
      var v3 = new THREE.Vector3(), tv = new THREE.Vector3();

      var stars = [];
      var geo = null, mat = null, pts = null;
      var posAttr = null, aAttr = null;
      var posArr = null, aArr = null;
      var count = 0, total = 0, moving = 0;
      var state = 'hidden', target = 0, alpha = 0;
      var tier = 'high', R = 1, clock = 0;

      function reducedNow() {
        var T = g.CLSkyTokens;
        return !!(T && T.reduced && T.reduced());
      }

      function teardown() {
        if (pts) { if (pts.parent) pts.parent.remove(pts); pts = null; }
        if (geo) { geo.dispose(); geo = null; }
        if (mat) { mat.dispose(); mat = null; }
      }

      function setStars(list, rad) {
        teardown();
        posArr = null; aArr = null; posAttr = null; aAttr = null;
        stars.length = 0;
        moving = 0;
        R = rad > 0 ? rad : 1;
        var n = 0;
        if (list && list.length) n = list.length < MAX ? list.length : MAX;
        count = n; total = n * K;
        if (!n) return;

        var pos = new Float32Array(total * 3);
        var aA = new Float32Array(total);
        var size = new Float32Array(total);
        var col = new Float32Array(total * 3);
        var i, j, idx, st, hex, cr, cg, cb;
        for (i = 0; i < n; i++) {
          st = list[i];
          hex = st.hex | 0;
          cr = ((hex >> 16) & 255) / 255;
          cg = ((hex >> 8) & 255) / 255;
          cb = (hex & 255) / 255;
          stars.push({ key: st.key, h: hNew() });
          for (j = 0; j < K; j++) {
            idx = i * K + j;
            size[idx] = 19 * (1 - 0.6 * j / K);
            col[idx * 3] = cr; col[idx * 3 + 1] = cg; col[idx * 3 + 2] = cb;
          }
        }
        posArr = pos; aArr = aA;

        geo = new THREE.BufferGeometry();
        posAttr = new THREE.BufferAttribute(pos, 3);
        posAttr.setUsage(THREE.DynamicDrawUsage);
        aAttr = new THREE.BufferAttribute(aA, 1);
        aAttr.setUsage(THREE.DynamicDrawUsage);
        geo.setAttribute('position', posAttr);
        geo.setAttribute('aA', aAttr);
        geo.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
        geo.setAttribute('aCol', new THREE.BufferAttribute(col, 3));

        mat = new THREE.ShaderMaterial({
          uniforms: { uDpr: { value: 1 }, uAlpha: { value: alpha } },
          vertexShader: VS,
          fragmentShader: FS,
          transparent: true,
          depthWrite: false,
          depthTest: false,
          blending: THREE.AdditiveBlending,
          premultipliedAlpha: true
        });

        pts = new THREE.Points(geo, mat);
        pts.frustumCulled = false;
        pts.renderOrder = 3;
        pts.visible = tier !== 'low';
        S.scene.add(pts);
      }

      function update(dt, tAnim) {
        var d = (typeof dt === 'number' && dt > 0) ? (dt > 0.1 ? 0.1 : dt) : 0;
        clock += d;

        var reducedMotion = reducedNow();
        if (reducedMotion) alpha = target;
        else {
          alpha += (target - alpha) * (1 - Math.exp(-A_FADE * d));
          if (Math.abs(target - alpha) < 0.001) alpha = target;
        }
        if (!mat || !posArr) { moving = 0; return; }

        var dpr = 1;
        if (S.renderer && S.renderer.getPixelRatio) dpr = S.renderer.getPixelRatio() || 1;
        mat.uniforms.uDpr.value = dpr;
        mat.uniforms.uAlpha.value = alpha;

        var on = tier !== 'low';
        pts.visible = on;
        var frozen = reducedMotion || !on;
        var cut = clock - WIN;
        var i, j, f, base, st, nd, h, qx, qy, qz, span, sm, sp, fade, w, idx, p, dx, dy, dz, tw;

        moving = 0;
        for (i = 0; i < count; i++) {
          base = i * K;
          st = stars[i];
          if (frozen) {
            for (j = 0; j < K; j++) aArr[base + j] = 0;
            hClear(st.h);
            continue;
          }
          nd = S.nodeOf(st.key);
          if (!nd || !nd.g || !nd.g.visible) {
            for (f = 0; f < K; f++) aArr[base + f] = 0;
            hClear(st.h);
            continue;
          }
          nd.g.getWorldPosition(v3);
          /* 牵引位移（Q1.3）：历史记在家位系——拖星 / 回弹不生彗尾（那是 sky-tug-fx 的牵引丝）；已有的尾随星整段平移，不脱节 */
          tw = nd.tugS > 0 && S.tugWorld ? S.tugWorld(nd, tv) : null;
          if (tw) v3.sub(tw);
          h = st.h;
          hPush(h, clock, v3.x, v3.y, v3.z);
          hTrim(h, cut);

          if (h.t[h.head] <= cut) {
            sm = hSample(h, cut);
            qx = sm.x; qy = sm.y; qz = sm.z; span = WIN;
          } else {
            qx = h.x[h.head]; qy = h.y[h.head]; qz = h.z[h.head];
            span = clock - h.t[h.head];
          }
          sp = 0;
          if (span >= SPAN_MIN) {
            dx = v3.x - qx; dy = v3.y - qy; dz = v3.z - qz;
            sp = Math.sqrt(dx * dx + dy * dy + dz * dz) / span;
          }
          fade = clamp01((sp / R - SPEED_LO) / SPEED_SPAN);
          /* 静止的星不插值尾点（绝大多数帧、绝大多数星都走这条） */
          if (fade <= 0.01) { for (j = 0; j < K; j++) aArr[base + j] = 0; continue; }
          moving++;

          for (j = 0; j < K; j++) {
            idx = base + j;
            p = hSample(h, clock - WIN * (j + 1) / K);
            if (!p) { aArr[idx] = 0; continue; }
            posArr[idx * 3] = tw ? p.x + tw.x : p.x;
            posArr[idx * 3 + 1] = tw ? p.y + tw.y : p.y;
            posArr[idx * 3 + 2] = tw ? p.z + tw.z : p.z;
            w = 1 - j / K;
            aArr[idx] = fade * w * w * A_PEAK;
          }
        }
        posAttr.needsUpdate = true;
        aAttr.needsUpdate = true;
      }

      function setState(s) {
        state = s === 'show' ? 'show' : (s === 'dim' ? 'dim' : 'hidden');
        target = state === 'show' ? 1 : (state === 'dim' ? 0.3 : 0);
        if (reducedNow()) alpha = target;
        if (mat) mat.uniforms.uAlpha.value = alpha;
      }

      function setTier(t) {
        tier = t === 'low' ? 'low' : (t === 'mid' ? 'mid' : 'high');
        if (pts) pts.visible = tier !== 'low';
      }

      function stats() {
        return { stars: count, points: total, moving: moving, state: state, tier: tier };
      }

      function dispose() {
        teardown();
        stars.length = 0;
        posArr = null; aArr = null; posAttr = null; aAttr = null;
        count = 0; total = 0; moving = 0;
      }

      return {
        setStars: setStars,
        update: update,
        setState: setState,
        setTier: setTier,
        stats: stats,
        dispose: dispose
      };
    }
  };
})(window);
