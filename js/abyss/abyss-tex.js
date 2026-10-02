/**
 * Castline · abyss-tex.js — 噪声与星尘纹理库（CORE · S5）
 * ============================================================================
 * 来源：mystic-grand-refactor-plan「深渊星典」§4 S5 噪声与星尘纹理库。
 * 定位：三图（雷达 / 角色星座场 / 星盘剧情树）共用的程序化微纹理发生器。
 *       FBM 星云、4×4 星尘 sprite 图集、细颗粒噪声、扫描线条纹，
 *       纯客户端 Canvas 程序化生成并缓存，零网络开销，内存总重 < 400KB。
 *
 * ES5 IIFE · 零外部强依赖 · UMD 全局暴露 window.CLAbyssTex。
 * ============================================================================
 */
(function (global) {
  'use strict';

  var cache = {};
  var enabled = true;

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  /**
   * 简单确定性伪随机发生器 (PRNG)
   */
  function createRng(seed) {
    var s = (seed || 1337) & 0xffffffff;
    return function () {
      s = (Math.imul(16807, s) + 0) | 0;
      return (s >>> 0) / 4294967296;
    };
  }

  /**
   * 创建离屏 Canvas
   */
  function createCanvas(w, h) {
    var c;
    if (typeof document !== 'undefined' && document.createElement) {
      c = document.createElement('canvas');
      c.width = w;
      c.height = h;
    } else {
      // 垫片环境
      c = { width: w, height: h, getContext: function () { return null; }, toDataURL: function () { return ''; } };
    }
    return c;
  }

  /**
   * 1. 细颗粒噪声发生器 (Fine Grain Noise)
   */
  function generateNoiseCanvas(w, h, alpha, seed) {
    w = w || 128;
    h = h || 128;
    alpha = alpha != null ? alpha : 0.08;
    var rng = createRng(seed || 42);
    var canvas = createCanvas(w, h);
    var ctx = canvas.getContext ? canvas.getContext('2d') : null;
    if (!ctx) return canvas;

    var img = ctx.createImageData(w, h);
    var d = img.data;
    var n = w * h * 4;
    for (var i = 0; i < n; i += 4) {
      var v = Math.floor(rng() * 255);
      d[i] = v;
      d[i + 1] = v;
      d[i + 2] = v;
      d[i + 3] = Math.floor(rng() * alpha * 255);
    }
    ctx.putImageData(img, 0, 0);
    return canvas;
  }

  /**
   * 2. 4×4 星尘 Sprite 图集 (Stardust Sprite Atlas)
   * 包含 16 枚不同亮度、光芒衍射瓣和光晕层次的星尘
   */
  function generateStardustAtlas(cellSize, seed) {
    cellSize = cellSize || 64;
    var cols = 4, rows = 4;
    var totalW = cellSize * cols;
    var totalH = cellSize * rows;
    var canvas = createCanvas(totalW, totalH);
    var ctx = canvas.getContext ? canvas.getContext('2d') : null;
    if (!ctx) return canvas;

    var rng = createRng(seed || 108);
    ctx.clearRect(0, 0, totalW, totalH);

    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        var cx = c * cellSize + cellSize / 2;
        var cy = r * cellSize + cellSize / 2;
        var maxR = cellSize * 0.44;

        // 依据行列控制光强与色相
        var intensity = 0.35 + (r * 4 + c) / 16 * 0.65;
        var hasSpikes = (r * 4 + c) % 2 === 1;

        // 1. 广域光晕
        var haloGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR);
        haloGrad.addColorStop(0, 'rgba(166, 136, 255, ' + (0.35 * intensity) + ')');
        haloGrad.addColorStop(0.35, 'rgba(122, 240, 200, ' + (0.18 * intensity) + ')');
        haloGrad.addColorStop(1, 'rgba(7, 6, 13, 0)');
        ctx.fillStyle = haloGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
        ctx.fill();

        // 2. 十字衍射芒（若有）
        if (hasSpikes) {
          ctx.strokeStyle = 'rgba(255, 245, 230, ' + (0.42 * intensity) + ')';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(cx - maxR * 0.8, cy);
          ctx.lineTo(cx + maxR * 0.8, cy);
          ctx.moveTo(cx, cy - maxR * 0.8);
          ctx.lineTo(cx, cy + maxR * 0.8);
          ctx.stroke();
        }

        // 3. 核心亮核
        var coreR = maxR * (0.12 + 0.15 * intensity);
        var coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
        coreGrad.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
        coreGrad.addColorStop(0.5, 'rgba(255, 240, 200, ' + (0.85 * intensity) + ')');
        coreGrad.addColorStop(1, 'rgba(255, 180, 92, 0)');
        ctx.fillStyle = coreGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    return canvas;
  }

  /**
   * 3. FBM 星云多重八度平铺图 (FBM Nebula Tile)
   */
  function generateNebulaCanvas(w, h, seed) {
    w = w || 256;
    h = h || 256;
    var canvas = createCanvas(w, h);
    var ctx = canvas.getContext ? canvas.getContext('2d') : null;
    if (!ctx) return canvas;

    var rng = createRng(seed || 2026);
    ctx.clearRect(0, 0, w, h);

    // 多层柔和渐变叠加模拟分形布朗云雾
    var cloudCount = 7;
    for (var i = 0; i < cloudCount; i++) {
      var cx = rng() * w;
      var cy = rng() * h;
      var cr = (0.3 + rng() * 0.45) * w;
      var grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr);
      // 深渊紫 / 薄荷翡翠 / 太阳琥珀
      var palette = [
        'rgba(166, 136, 255, 0.12)',
        'rgba(122, 240, 200, 0.08)',
        'rgba(255, 180, 92, 0.07)',
        'rgba(26, 17, 48, 0.22)'
      ];
      var col = palette[i % palette.length];
      grad.addColorStop(0, col);
      grad.addColorStop(1, 'rgba(7, 6, 13, 0)');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, cr, 0, Math.PI * 2);
      ctx.fill();
    }

    return canvas;
  }

  /**
   * 4. 扫描线条纹 (Scanlines)
   */
  function generateScanlineCanvas(pitch, opacity) {
    pitch = pitch || 4;
    opacity = opacity != null ? opacity : 0.15;
    var canvas = createCanvas(pitch, pitch);
    var ctx = canvas.getContext ? canvas.getContext('2d') : null;
    if (!ctx) return canvas;

    ctx.clearRect(0, 0, pitch, pitch);
    ctx.fillStyle = 'rgba(233, 228, 244, ' + opacity + ')';
    ctx.fillRect(0, 0, pitch, 1);
    return canvas;
  }

  /**
   * 缓存管理器
   */
  function getTexture(type, opts) {
    opts = opts || {};
    var key = type + ':' + JSON.stringify(opts);
    if (cache[key]) return cache[key];

    var canvas;
    if (type === 'noise') {
      canvas = generateNoiseCanvas(opts.w, opts.h, opts.alpha, opts.seed);
    } else if (type === 'stardust') {
      canvas = generateStardustAtlas(opts.cellSize, opts.seed);
    } else if (type === 'nebula') {
      canvas = generateNebulaCanvas(opts.w, opts.h, opts.seed);
    } else if (type === 'scanlines') {
      canvas = generateScanlineCanvas(opts.pitch, opts.opacity);
    } else {
      canvas = createCanvas(32, 32);
    }

    cache[key] = canvas;
    return canvas;
  }

  /**
   * 生成供 SVG Defs 注入的 Pattern
   */
  function getSVGPattern(uid, type, opts) {
    var canvas = getTexture(type, opts);
    var dataUrl = '';
    try {
      if (canvas && canvas.toDataURL) dataUrl = canvas.toDataURL('image/png');
    } catch (e) {
      dataUrl = '';
    }
    var w = canvas.width || 64, h = canvas.height || 64;
    return (
      '<pattern id="' + uid + '" patternUnits="userSpaceOnUse" width="' + w + '" height="' + h + '">' +
      (dataUrl ? '<image href="' + dataUrl + '" width="' + w + '" height="' + h + '"/>' : '') +
      '</pattern>'
    );
  }

  /**
   * 生成 Three.js CanvasTexture 封装
   */
  function createThreeTexture(type, THREE, opts) {
    if (!THREE || !THREE.CanvasTexture) return null;
    var canvas = getTexture(type, opts);
    var tex = new THREE.CanvasTexture(canvas);
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.RepeatWrapping;
    tex.needsUpdate = true;
    return tex;
  }

  function clearCache() {
    cache = {};
  }

  function setEnabled(b) {
    enabled = !!b;
    return enabled;
  }

  var CLAbyssTex = {
    name: 'abyss-tex',
    version: '1',
    getTexture: getTexture,
    getSVGPattern: getSVGPattern,
    createThreeTexture: createThreeTexture,
    generateNoiseCanvas: generateNoiseCanvas,
    generateStardustAtlas: generateStardustAtlas,
    generateNebulaCanvas: generateNebulaCanvas,
    generateScanlineCanvas: generateScanlineCanvas,
    clearCache: clearCache,
    setEnabled: setEnabled,
    isEnabled: function () { return enabled; },
    audit: function () {
      return {
        name: 'abyss-tex',
        version: '1',
        enabled: enabled,
        cachedCount: Object.keys(cache).length
      };
    }
  };

  global.CLAbyssTex = CLAbyssTex;
})(typeof window !== 'undefined' ? window : this);
