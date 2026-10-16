
(function (global) {
  'use strict';

  // ---- 共享约定与主题色彩谱系 ----------------------------------------------
  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = {
    '智谋': 'MIND',
    '实力': 'FORCE',
    '意志': 'WILL',
    '魅力': 'CHARM',
    '情感': 'HEART',
    '野心': 'DRIVE',
    '权势': 'REACH',
    '道义': 'CODE'
  };

  var THEME = {
    obsidian: '#07060d',
    mint: '#7af0c8',
    amber: '#ffb45c',
    violet: '#a688ff',
    crimson: '#ff5c7c',
    cyan: '#58d5ff',
    crystalGold: '#ffe599',
    whiteCore: '#ffffff'
  };

  // ---- 安全兜底与工具函数 ----------------------------------------------------
  function sanitizeUid(uid) {
    if (uid == null || uid === '') return 'cl-vfx';
    var safe = String(uid).replace(/[^a-zA-Z0-9_\-]/g, '_');
    return safe || 'cl-vfx';
  }

  function safeNum(val, fallback) {
    var n = Number(val);
    return isFinite(n) && !isNaN(n) ? n : (fallback || 0);
  }

  function isReducedMotion(opt) {
    if (opt && typeof opt.reducedMotion === 'boolean') {
      return opt.reducedMotion;
    }
    try {
      if (typeof window !== 'undefined' && window.matchMedia) {
        return !!window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      }
    } catch (e) {
    }
    return false;
  }

  function getIds(uid) {
    var prefix = sanitizeUid(uid);
    return {
      prismGrad: prefix + '-prism',
      prism: prefix + '-prism',
      iridescent: prefix + '-prism',
      thinFilmGrad: prefix + '-thin-film',
      thinFilm: prefix + '-thin-film',
      crystalGrad: prefix + '-prism',

      ghostGlowFilter: prefix + '-ghost-glow',
      ghostGlow: prefix + '-ghost-glow',
      ghost: prefix + '-ghost-glow',

      vertexBloomFilter: prefix + '-vertex-bloom',
      vertexBloom: prefix + '-vertex-bloom',
      bloom: prefix + '-vertex-bloom',

      scanGridPattern: prefix + '-scan-grid',
      scanGrid: prefix + '-scan-grid',
      cyberPattern: prefix + '-scan-grid'
    };
  }

  // ---- ① 棱镜色散与薄膜干涉彩虹晶体渐变 ----------------------------------------
  function renderPrismGradient(uid, opt) {
    var ids = getIds(uid);
    var prismAngle = (opt && opt.prismAngle) || 'diag';
    var x1 = '0%', y1 = '0%', x2 = '100%', y2 = '100%';
    if (prismAngle === 'h') { x1 = '0%'; y1 = '0%'; x2 = '100%'; y2 = '0%'; }
    else if (prismAngle === 'v') { x1 = '0%'; y1 = '0%'; x2 = '0%'; y2 = '100%'; }

    var prismGrad = [
      '<linearGradient id="' + ids.prism + '" x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '">',
      '  <stop offset="0%" stop-color="' + THEME.violet + '" stop-opacity="0.84" />',
      '  <stop offset="18%" stop-color="' + THEME.cyan + '" stop-opacity="0.90" />',
      '  <stop offset="38%" stop-color="' + THEME.mint + '" stop-opacity="0.96" />',
      '  <stop offset="62%" stop-color="' + THEME.crystalGold + '" stop-opacity="0.88" />',
      '  <stop offset="82%" stop-color="' + THEME.amber + '" stop-opacity="0.92" />',
      '  <stop offset="100%" stop-color="' + THEME.crimson + '" stop-opacity="0.85" />',
      '</linearGradient>'
    ].join('\n');

    var thinFilmGrad = [
      '<linearGradient id="' + ids.thinFilm + '" x1="100%" y1="0%" x2="0%" y2="100%">',
      '  <stop offset="0%" stop-color="' + THEME.mint + '" stop-opacity="0.76" />',
      '  <stop offset="25%" stop-color="' + THEME.cyan + '" stop-opacity="0.68" />',
      '  <stop offset="52%" stop-color="' + THEME.violet + '" stop-opacity="0.82" />',
      '  <stop offset="78%" stop-color="' + THEME.crimson + '" stop-opacity="0.72" />',
      '  <stop offset="100%" stop-color="' + THEME.amber + '" stop-opacity="0.86" />',
      '</linearGradient>'
    ].join('\n');

    return prismGrad + '\n' + thinFilmGrad;
  }

  // ---- ② 幽灵基准多边形专用发光脉冲滤镜 ----------------------------------------
  function renderGhostGlowFilter(uid, opt) {
    var ids = getIds(uid);
    var reduced = isReducedMotion(opt);
    var degrade = opt && safeNum(opt.degrade, 0);
    var animDisabled = reduced || degrade >= 1 || (opt && opt.pulse === false);

    var stdDev = '3.6';
    var animateTag = animDisabled ? '' : [
      '    <animate attributeName="stdDeviation"',
      '             values="2.6;4.8;2.6"',
      '             dur="4.6s"',
      '             repeatCount="indefinite" />'
    ].join('\n');

    var filterLines = [
      '<filter id="' + ids.ghostGlow + '" x="-50%" y="-50%" width="200%" height="200%" color-interpolation-filters="sRGB">',
      '  <feGaussianBlur in="SourceGraphic" stdDeviation="' + stdDev + '" result="ghost_blur">',
      animateTag ? animateTag + '\n  </feGaussianBlur>' : '  </feGaussianBlur>',
      '  <feColorMatrix in="ghost_blur" type="matrix" values="',
      '    0 0 0 0 0.65',
      '    0 0 0 0 0.53',
      '    0 0 0 0 1.00',
      '    0 0 0 0.68 0" result="ghost_glow" />',
      '  <feMerge>',
      '    <feMergeNode in="ghost_glow" />',
      '    <feMergeNode in="SourceGraphic" />',
      '  </feMerge>',
      '</filter>'
    ];

    return filterLines.join('\n');
  }

  // ---- ③ 顶点信标的高斯柔光与色散通道 ----------------------------------------
  function renderVertexBloomFilter(uid, opt) {
    var ids = getIds(uid);
    var reduced = isReducedMotion(opt);
    var degrade = opt && safeNum(opt.degrade, 0);

    if (reduced || degrade >= 1) {
      return [
        '<filter id="' + ids.vertexBloom + '" x="-45%" y="-45%" width="190%" height="190%" color-interpolation-filters="sRGB">',
        '  <feGaussianBlur in="SourceGraphic" stdDeviation="3.2" result="bloom_blur" />',
        '  <feColorMatrix in="bloom_blur" type="matrix" values="',
        '    0 0 0 0 1.00',
        '    0 0 0 0 0.72',
        '    0 0 0 0 0.42',
        '    0 0 0 0.75 0" result="bloom_tint" />',
        '  <feMerge>',
        '    <feMergeNode in="bloom_tint" />',
        '    <feMergeNode in="SourceGraphic" />',
        '  </feMerge>',
        '</filter>'
      ].join('\n');
    }

    return [
      '<filter id="' + ids.vertexBloom + '" x="-60%" y="-60%" width="220%" height="220%" color-interpolation-filters="sRGB">',
      '  <!-- 色散通道分离 (Chromatic Aberration) -->',
      '  <feOffset in="SourceGraphic" dx="1.2" dy="0" result="offset_red" />',
      '  <feColorMatrix in="offset_red" type="matrix" values="',
      '    1 0 0 0 0',
      '    0 0 0 0 0',
      '    0 0 0 0 0',
      '    0 0 0 0.88 0" result="chroma_r" />',
      '  <feOffset in="SourceGraphic" dx="-1.2" dy="0" result="offset_blue" />',
      '  <feColorMatrix in="offset_blue" type="matrix" values="',
      '    0 0 0 0 0',
      '    0 0 0 0 0',
      '    0 0 1 0 0',
      '    0 0 0 0.88 0" result="chroma_b" />',
      '  <feColorMatrix in="SourceGraphic" type="matrix" values="',
      '    0 0 0 0 0',
      '    0 1 0 0 0',
      '    0 0 0 0 0',
      '    0 0 0 0.92 0" result="chroma_g" />',
      '  <feBlend mode="screen" in="chroma_r" in2="chroma_g" result="blend_rg" />',
      '  <feBlend mode="screen" in="blend_rg" in2="chroma_b" result="chroma_base" />',
      '  <!-- 双重高斯柔光绽放 (Dual Stage Bloom) -->',
      '  <feGaussianBlur in="chroma_base" stdDeviation="2.2" result="bloom_core" />',
      '  <feGaussianBlur in="chroma_base" stdDeviation="5.4" result="bloom_wide" />',
      '  <feColorMatrix in="bloom_wide" type="matrix" values="',
      '    0 0 0 0 1.00',
      '    0 0 0 0 0.70',
      '    0 0 0 0 0.36',
      '    0 0 0 0.58 0" result="bloom_aura" />',
      '  <feMerge>',
      '    <feMergeNode in="bloom_aura" />',
      '    <feMergeNode in="bloom_core" />',
      '    <feMergeNode in="SourceGraphic" />',
      '  </feMerge>',
      '</filter>'
    ].join('\n');
  }

  // ---- ④ 全息扫描网格微纹理 pattern -------------------------------------------
  function renderScanGridPattern(uid, opt) {
    var ids = getIds(uid);
    var size = (opt && safeNum(opt.gridSize, 16)) || 16;

    return [
      '<pattern id="' + ids.scanGrid + '" patternUnits="userSpaceOnUse" width="' + size + '" height="' + size + '">',
      '  <line x1="0" y1="0" x2="' + size + '" y2="0" stroke="rgba(122,240,200,0.09)" stroke-width="0.75" />',
      '  <line x1="0" y1="0" x2="0" y2="' + size + '" stroke="rgba(166,136,255,0.07)" stroke-width="0.75" />',
      '  <circle cx="0" cy="0" r="0.8" fill="rgba(255,180,92,0.40)" />',
      '  <circle cx="' + size + '" cy="' + size + '" r="0.8" fill="rgba(255,180,92,0.40)" />',
      '  <rect x="0" y="' + Math.round(size / 2) + '" width="' + size + '" height="1" fill="rgba(122,240,200,0.04)" />',
      '</pattern>'
    ].join('\n');
  }

  // ---- 1. renderDefs(uid, opt) 主入口 -----------------------------------------
  function renderDefs(uid, opt) {
    var safeId = sanitizeUid(uid);
    var options = opt || {};

    var parts = [
      renderPrismGradient(safeId, options),
      renderGhostGlowFilter(safeId, options),
      renderVertexBloomFilter(safeId, options),
      renderScanGridPattern(safeId, options)
    ];

    var innerContent = parts.join('\n');

    if (options.innerOnly === true || options.raw === true) {
      return innerContent;
    }

    return '<defs class="cl-radar-visual-defs">\n' + innerContent + '\n</defs>';
  }

  // ---- 2. getPeakAuraStyle(score, isPeak, opt) -------------------------------
  function getPeakAuraStyle(score, isPeak, opt) {
    var s = safeNum(score, 0);
    var peak = Boolean(isPeak);
    var isValOnly = opt === 'value' || (opt && (opt.valueOnly === true || opt.propertyOnly === true));

    var shadows = [];

    if (peak) {
      if (s >= 96) {
        shadows.push('drop-shadow(0 0 3px rgba(255, 241, 218, 0.95))');
        shadows.push('drop-shadow(0 0 7px rgba(255, 92, 124, 0.85))');
        shadows.push('drop-shadow(0 0 14px rgba(166, 136, 255, 0.65))');
      } else if (s >= 85) {
        shadows.push('drop-shadow(0 0 3px rgba(255, 214, 150, 0.92))');
        shadows.push('drop-shadow(0 0 8px rgba(255, 180, 92, 0.78))');
        shadows.push('drop-shadow(0 0 12px rgba(122, 240, 200, 0.48))');
      } else if (s >= 70) {
        shadows.push('drop-shadow(0 0 3px rgba(122, 240, 200, 0.88))');
        shadows.push('drop-shadow(0 0 7px rgba(255, 180, 92, 0.62))');
      } else {
        shadows.push('drop-shadow(0 0 3px rgba(122, 240, 200, 0.78))');
        shadows.push('drop-shadow(0 0 6px rgba(166, 136, 255, 0.42))');
      }
    } else {
      if (s >= 96) {
        shadows.push('drop-shadow(0 0 3px rgba(255, 214, 150, 0.85))');
        shadows.push('drop-shadow(0 0 8px rgba(255, 92, 124, 0.58))');
      } else if (s >= 85) {
        shadows.push('drop-shadow(0 0 3px rgba(122, 240, 200, 0.72))');
        shadows.push('drop-shadow(0 0 6px rgba(122, 240, 200, 0.38))');
      } else if (s >= 70) {
        shadows.push('drop-shadow(0 0 2px rgba(166, 136, 255, 0.48))');
      } else if (s >= 40) {
        shadows.push('drop-shadow(0 0 1.5px rgba(166, 136, 255, 0.26))');
      } else {
        shadows.push('drop-shadow(0 0 1px rgba(150, 140, 180, 0.18))');
      }
    }

    var valueString = shadows.join(' ');
    if (isValOnly) {
      return valueString;
    }
    return 'filter: ' + valueString + ';';
  }

  function getPeakAuraFilterValue(score, isPeak) {
    return getPeakAuraStyle(score, isPeak, { valueOnly: true });
  }

  // ---- 模块导出对象 ----------------------------------------------------------
  var CLRadarVisualFX = {
    renderDefs: renderDefs,
    getPeakAuraStyle: getPeakAuraStyle,
    getPeakAuraFilterValue: getPeakAuraFilterValue,

    getIds: getIds,
    renderPrismGradient: renderPrismGradient,
    renderGhostGlowFilter: renderGhostGlowFilter,
    renderVertexBloomFilter: renderVertexBloomFilter,
    renderScanGridPattern: renderScanGridPattern,

    THEME: THEME,
    KEYS: KEYS,
    EN: EN,
    isReducedMotion: isReducedMotion,
    sanitizeUid: sanitizeUid,

    version: '1.0.0'
  };

  if (typeof global !== 'undefined') {
    global.CLRadarVisualFX = CLRadarVisualFX;
  }

})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
