/*!
 * sky-orrery-sats · 罗盘关系星轨（orbsats）
 * @role orbsats
 * @owns js/sky/sky-orrery-sats.js
 * @budget drawcalls=3 points=216 vertices=216 rtpx=0 passes=0
 * @contract deep-sky/1
 *
 * 联系对象按关系类型分到三道轨，按关系色着色，与罗盘卫星同步点亮；每颗星身后拖一道沿轨渐隐的彗尾（16 粒，约 20°，指明公转方向）。
 * 依赖 window.THREE(r128 UMD) + window.CLSkyTokens。ES5 经典脚本，无自有 rAF。
 */
(function (g) {
  'use strict';

  var TAU = Math.PI * 2;
  var W = [0.05, -0.034, 0.027];   /* rad/s，三轨角速度 */
  var P = [0.4, 2.1, 4.0];         /* 三轨起始相位 */
  var MAX_SATS = 12;
  var TL = 16, TD = 0.022;          /* 彗尾：粒数 · 相邻两粒的轨道角距（rad） */
  var PER = 2 + TL;

  function clamp01(v) {
    if (!(v > 0)) { return 0; }
    return v > 1 ? 1 : v;
  }

  function toRGB(hex) {
    return [((hex >> 16) & 255) / 255, ((hex >> 8) & 255) / 255, (hex & 255) / 255];
  }

  function makeMat() {
    var m = new g.THREE.ShaderMaterial({
      uniforms: {
        uDpr: { value: 1 },
        uAlpha: { value: 0 },
        uAny: { value: 0 }
      },
      vertexShader:
        'attribute float aK; attribute float aSize; attribute vec3 aCol; attribute float aHot; ' +
        'uniform float uDpr; varying float vK; varying vec3 vCol; varying float vHot; void main() { ' +
        'vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_Position = projectionMatrix * mv; ' +
        'gl_PointSize = aSize * uDpr * (1.0 + 0.8 * aHot); vK = aK; vCol = aCol; vHot = aHot; }',
      fragmentShader:
        'uniform float uAlpha; uniform float uAny; varying float vK; varying vec3 vCol; varying float vHot; ' +
        'void main() { vec2 d = gl_PointCoord - 0.5; float r2 = dot(d, d) * 4.0; if (r2 > 1.0) { discard; } ' +
        'float f = vK < 0.5 ? exp(-r2 * 14.0) * 1.3 : (vK < 1.5 ? exp(-r2 * 3.2) * 0.32 : exp(-r2 * 5.0) * 0.34 * pow(1.0 - (vK - 2.0), 1.6)); ' +
        'float dim = uAny > 0.5 ? mix(0.28, 1.0, vHot) : 1.0; float a = f * uAlpha * dim; ' +
        'gl_FragColor = vec4(vCol * a, a); }',
      blending: g.THREE.AdditiveBlending,
      premultipliedAlpha: true,
      transparent: true,
      depthTest: false,
      depthWrite: false
    });
    m.renderOrder = 5;
    return m;
  }

  g.CLSkyOrrerySats = {
    create: function (opts) {
      opts = opts || {};
      var T = g.CLSkyTokens;
      var THREE = g.THREE;
      var renderer = opts.scene ? opts.scene.renderer : null;
      var reducedMotion = !!(T && T.reduced && T.reduced());

      var tier = 'high';
      var rig = null;
      var norm = [];              /* 归一后的 list，保留下标对齐 setHot */
      var hot = [];
      var hotCount = 0;
      var built = [null, null, null];
      var sats = 0;
      var clock = 0;
      var dead = false;

      function clearBuilt() {
        for (var r = 0; r < 3; r++) {
          var rec = built[r];
          if (rec) {
            if (rec.pts && rec.pts.parent) { rec.pts.parent.remove(rec.pts); }
            if (rec.geo) { rec.geo.dispose(); }
            if (rec.mat) { rec.mat.dispose(); }
            built[r] = null;
          }
          var rg = rig && rig[r];
          if (rg && rg.orb) { rg.orb.visible = true; }
        }
        sats = 0;
      }

      function applyHot() {
        var any = hotCount > 0 ? 1 : 0;
        for (var r = 0; r < 3; r++) {
          var rec = built[r];
          if (!rec) { continue; }
          var arr = rec.aHot;
          for (var j = 0; j < rec.idx.length; j++) {
            var h = hot[rec.idx[j]] ? 1 : 0;
            for (var q = 0; q < PER; q++) { arr[j * PER + q] = h; }
          }
          rec.geo.attributes.aHot.needsUpdate = true;
          rec.mat.uniforms.uAny.value = any;
        }
      }

      function build() {
        clearBuilt();
        if (dead || !rig || rig.length < 3 || tier === 'low') { return; }
        for (var r = 0; r < 3; r++) {
          var ids = [];
          for (var i = 0; i < norm.length; i++) {
            if (norm[i].ring === r) { ids.push(i); }
          }
          var slot = rig[r];
          if (!ids.length || !slot || !slot.grp) { continue; }

          var m = ids.length;
          var n = m * PER;
          var pos = new Float32Array(n * 3);
          var aK = new Float32Array(n);
          var aSize = new Float32Array(n);
          var aCol = new Float32Array(n * 3);
          var aHot = new Float32Array(n);

          for (var j = 0; j < m; j++) {
            var it = norm[ids[j]];
            var k = clamp01(it.k);
            var coreHex = (T && T.mix) ? T.mix(it.hex, T.C.STAR_WHITE, 0.45) : it.hex;
            var cr = toRGB(coreHex);
            var gr = toRGB(it.hex);
            var p0 = j * PER;
            var p1 = p0 + 1;
            aK[p0] = 0; aK[p1] = 1;
            aSize[p0] = 5 + 5 * k;
            aSize[p1] = 16 + 14 * k;
            aCol[p0 * 3] = cr[0]; aCol[p0 * 3 + 1] = cr[1]; aCol[p0 * 3 + 2] = cr[2];
            aCol[p1 * 3] = gr[0]; aCol[p1 * 3 + 1] = gr[1]; aCol[p1 * 3 + 2] = gr[2];
            aHot[p0] = hot[ids[j]] ? 1 : 0;
            aHot[p1] = aHot[p0];
            /* 彗尾：芯色向组色过渡、越往后越小越淡（aK = 2 + t 带进片元做衰减） */
            for (var q = 1; q <= TL; q++) {
              var pt = p1 + q, t = q / (TL + 1), tc = (T && T.mix) ? toRGB(T.mix(coreHex, it.hex, t)) : gr;
              aK[pt] = 2 + t; aSize[pt] = (5 + 6 * k) * (1.3 - 0.85 * t);
              aCol[pt * 3] = tc[0]; aCol[pt * 3 + 1] = tc[1]; aCol[pt * 3 + 2] = tc[2];
              aHot[pt] = aHot[p0];
            }
          }

          var geo = new THREE.BufferGeometry();
          /* 动态属性用 BufferAttribute 直接包住数组（Float32BufferAttribute 会拷贝，之后改 pos / aHot 就写不到 GPU） */
          geo.setAttribute('position', new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
          geo.setAttribute('aK', new THREE.Float32BufferAttribute(aK, 1));
          geo.setAttribute('aSize', new THREE.Float32BufferAttribute(aSize, 1));
          geo.setAttribute('aCol', new THREE.Float32BufferAttribute(aCol, 3));
          geo.setAttribute('aHot', new THREE.BufferAttribute(aHot, 1).setUsage(THREE.DynamicDrawUsage));

          var mat = makeMat();
          var pts = new THREE.Points(geo, mat);
          pts.frustumCulled = false;
          pts.renderOrder = 5;
          slot.grp.add(pts);
          if (slot.orb) { slot.orb.visible = false; }

          built[r] = { pts: pts, geo: geo, mat: mat, idx: ids, pos: pos, aHot: aHot };
          sats += m;
        }
        applyHot();
      }

      function set(rigIn, listIn) {
        if (dead) { return; }
        rig = rigIn || null;
        norm = [];
        hot = [];
        hotCount = 0;
        var src = listIn || [];
        var n = src.length > MAX_SATS ? MAX_SATS : src.length;
        for (var i = 0; i < n; i++) {
          var o = src[i] || {};
          var r = o.ring | 0;
          if (!(r >= 0 && r < 3)) { r = -1; }
          norm.push({ ring: r, hex: o.hex | 0, k: clamp01(o.k) });
          hot.push(0);
        }
        build();
      }

      function setHot(idx) {
        if (dead) { return; }
        var i;
        for (i = 0; i < hot.length; i++) { hot[i] = 0; }
        hotCount = 0;
        if (idx && idx.length) {
          for (i = 0; i < idx.length; i++) {
            var v = idx[i] | 0;
            if (v >= 0 && v < hot.length) { hot[v] = 1; hotCount++; }
          }
        }
        applyHot();
      }

      function setTier(t) {
        if (dead) { return; }
        tier = (t === 'low' || t === 'mid' || t === 'high') ? t : 'mid';
        if (tier === 'low') { clearBuilt(); } else { build(); }
      }

      function update(dt, tAnim, alpha) {
        if (dead) { return; }
        reducedMotion = !!(T && T.reduced && T.reduced());
        var d = (typeof dt === 'number' && dt > 0) ? (dt > 0.25 ? 0.25 : dt) : 0;
        if (!reducedMotion && tier !== 'low') { clock += d; }
        var dpr = (renderer && renderer.getPixelRatio) ? renderer.getPixelRatio() : 1;
        var al = clamp01(alpha);
        for (var r = 0; r < 3; r++) {
          var rec = built[r];
          if (!rec) { continue; }
          var base = W[r] * clock + P[r], back = W[r] > 0 ? -TD : TD;   /* 尾巴拖在公转方向的反侧 */
          var m = rec.idx.length;
          var pos = rec.pos;
          for (var j = 0; j < m; j++) {
            var a = base + TAU * j / m;
            for (var q = 0; q < PER; q++) {
              var aq = q < 2 ? a : a + back * (q - 1), o0 = (j * PER + q) * 3;
              pos[o0] = Math.cos(aq); pos[o0 + 1] = Math.sin(aq); pos[o0 + 2] = 0;
            }
          }
          rec.geo.attributes.position.needsUpdate = true;
          rec.mat.uniforms.uDpr.value = dpr;
          rec.mat.uniforms.uAlpha.value = al;
        }
      }

      function stats() {
        var out = [0, 0, 0], pts = 0;
        for (var r = 0; r < 3; r++) { out[r] = built[r] ? built[r].idx.length : 0; pts += built[r] ? built[r].geo.attributes.position.count : 0; }
        return { sats: sats, hot: hotCount, rings: out, points: pts };
      }

      function dispose() {
        clearBuilt();
        rig = null;
        norm = [];
        hot = [];
        hotCount = 0;
        sats = 0;
        renderer = null;
        dead = true;
      }

      return {
        set: set,
        setHot: setHot,
        update: update,
        setTier: setTier,
        stats: stats,
        dispose: dispose
      };
    }
  };
})(window);
