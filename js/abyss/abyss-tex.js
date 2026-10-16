(function (global) {
  'use strict';

  var cache = {};
  var enabled = true;

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  function createRng(seed) {
    var s = (seed || 1337) & 0xffffffff;
    return function () {
      s = (Math.imul(16807, s) + 0) | 0;
      return (s >>> 0) / 4294967296;
    };
  }

  function createCanvas(w, h) {
    var c;
    if (typeof document !== 'undefined' && document.createElement) {
      c = document.createElement('canvas');
      c.width = w;
      c.height = h;
    } else {
      c = { width: w, height: h, getContext: function () { return null; }, toDataURL: function () { return ''; } };
    }
    return c;
  }

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

        var intensity = 0.35 + (r * 4 + c) / 16 * 0.65;
        var hasSpikes = (r * 4 + c) % 2 === 1;

        var haloGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR);
        haloGrad.addColorStop(0, 'rgba(166, 136, 255, ' + (0.35 * intensity) + ')');
        haloGrad.addColorStop(0.35, 'rgba(122, 240, 200, ' + (0.18 * intensity) + ')');
        haloGrad.addColorStop(1, 'rgba(7, 6, 13, 0)');
        ctx.fillStyle = haloGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
        ctx.fill();

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

  function generateNebulaCanvas(w, h, seed) {
    w = w || 256;
    h = h || 256;
    var canvas = createCanvas(w, h);
    var ctx = canvas.getContext ? canvas.getContext('2d') : null;
    if (!ctx) return canvas;

    var rng = createRng(seed || 2026);
    ctx.clearRect(0, 0, w, h);

    var cloudCount = 7;
    for (var i = 0; i < cloudCount; i++) {
      var cx = rng() * w;
      var cy = rng() * h;
      var cr = (0.3 + rng() * 0.45) * w;
      var grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr);
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
