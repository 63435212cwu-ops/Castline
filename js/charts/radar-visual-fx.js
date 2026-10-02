/**
 * Castline · radar-visual-fx.js — 雷达材质着色与光影滤镜增强模块
 * 独占单元：U04 · 图形与视效工程师
 * 
 * 核心功能：
 * 1. renderDefs(uid, opt): 输出高级 SVG <defs> 片段，包含：
 *    ① 棱镜色散与薄膜干涉彩虹晶体渐变 (iridescent prism linearGradient)
 *    ② 幽灵基准多边形专用发光脉冲滤镜 (benchmark ghost glow filter)
 *    ③ 顶点信标的高斯柔光与色散通道 (vertex bloom filter)
 *    ④ 全息扫描网格微纹理 pattern (cyberpunk scan grid pattern)
 * 2. getPeakAuraStyle(score, isPeak, opt): 为最高维和极值顶点提供动态 CSS filter/drop-shadow 样式串
 * 
 * 安全与契约：
 * - 挂载至 window.CLRadarVisualFX
 * - 全量输入防御性校验，杜绝 NaN 与非法 SVG 属性
 * - 遵循 prefers-reduced-motion: reduce 与画质降级阶梯
 * - 继承 Castline 语义色彩令牌（黑曜石/薄荷翠/太阳琥珀/虚空秘紫/炽烈绯红）
 */

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
    obsidian: '#07060d',       // 黑曜石底色
    mint: '#7af0c8',           // 核心薄荷翠（智慧/科技）
    amber: '#ffb45c',          // 太阳琥珀（高光/信号）
    violet: '#a688ff',         // 虚空秘紫（神秘/基准）
    crimson: '#ff5c7c',        // 炽烈绯红（极值/巅峰）
    cyan: '#58d5ff',           // 棱镜青光（色散过渡）
    crystalGold: '#ffe599',    // 晶体高光金
    whiteCore: '#ffffff'       // 顶点信标纯白核心
  };

  // ---- 安全兜底与工具函数 ----------------------------------------------------
  /** 安全清洗 UID，保证其只包含安全字符且非空 */
  function sanitizeUid(uid) {
    if (uid == null || uid === '') return 'cl-vfx';
    var safe = String(uid).replace(/[^a-zA-Z0-9_\-]/g, '_');
    return safe || 'cl-vfx';
  }

  /** 安全转换数值，防止输出 NaN 或非有限数 */
  function safeNum(val, fallback) {
    var n = Number(val);
    return isFinite(n) && !isNaN(n) ? n : (fallback || 0);
  }

  /** 检查是否开启降级或减弱动效 */
  function isReducedMotion(opt) {
    if (opt && typeof opt.reducedMotion === 'boolean') {
      return opt.reducedMotion;
    }
    try {
      if (typeof window !== 'undefined' && window.matchMedia) {
        return !!window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      }
    } catch (e) {
      // 忽略无 window 或 matchMedia 异常
    }
    return false;
  }

  /** 获取对应 UID 的所有子资产标准 ID 映射表 */
  function getIds(uid) {
    var prefix = sanitizeUid(uid);
    return {
      // ① 棱镜色散与薄膜干涉彩虹晶体渐变
      prismGrad: prefix + '-prism',
      prism: prefix + '-prism',
      iridescent: prefix + '-prism',
      thinFilmGrad: prefix + '-thin-film',
      thinFilm: prefix + '-thin-film',
      crystalGrad: prefix + '-prism',

      // ② 幽灵基准多边形专用发光脉冲滤镜
      ghostGlowFilter: prefix + '-ghost-glow',
      ghostGlow: prefix + '-ghost-glow',
      ghost: prefix + '-ghost-glow',

      // ③ 顶点信标的高斯柔光与色散通道滤镜
      vertexBloomFilter: prefix + '-vertex-bloom',
      vertexBloom: prefix + '-vertex-bloom',
      bloom: prefix + '-vertex-bloom',

      // ④ 全息扫描网格微纹理 pattern
      scanGridPattern: prefix + '-scan-grid',
      scanGrid: prefix + '-scan-grid',
      cyberPattern: prefix + '-scan-grid'
    };
  }

  // ---- ① 棱镜色散与薄膜干涉彩虹晶体渐变 ----------------------------------------
  /**
   * 生成棱镜色散与薄膜干涉彩虹晶体线性渐变片段
   */
  function renderPrismGradient(uid, opt) {
    var ids = getIds(uid);
    var prismAngle = (opt && opt.prismAngle) || 'diag'; // 'diag' | 'h' | 'v'
    var x1 = '0%', y1 = '0%', x2 = '100%', y2 = '100%';
    if (prismAngle === 'h') { x1 = '0%'; y1 = '0%'; x2 = '100%'; y2 = '0%'; }
    else if (prismAngle === 'v') { x1 = '0%'; y1 = '0%'; x2 = '0%'; y2 = '100%'; }

    // 主棱镜色散渐变 (Prism Dispersion Rainbow Gradient)
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

    // 薄膜干涉互补渐变 (Thin-Film Interference Gradient)
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
  /**
   * 生成幽灵基准多边形专用发光脉冲滤镜
   * 采用虚空秘紫与深层幽光矩阵，在正常模式下支持细微光学脉冲，在 reduced-motion 或降级下平滑保真
   */
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
  /**
   * 生成顶点信标的高斯柔光与色散通道滤镜 (Vertex Bloom + Chromatic Aberration)
   * 通过 RGB 通道偏置 offset 与 screen 叠加模拟光学色散，双重 feGaussianBlur 达成核心柔光
   */
  function renderVertexBloomFilter(uid, opt) {
    var ids = getIds(uid);
    var reduced = isReducedMotion(opt);
    var degrade = opt && safeNum(opt.degrade, 0);

    // 降级分支：若不支持复杂滤镜或处于降级/减弱动画状态，使用高效柔光合并
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

    // 全功能分支：色散通道分离与多阶高斯绽放
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
  /**
   * 生成全息扫描网格微纹理 pattern (Cyberpunk Scan Grid Pattern)
   */
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
  /**
   * 输出高级 SVG <defs> 片段
   * @param {string} uid 唯一 ID 前缀
   * @param {object} [opt] 可选配置
   *   - reducedMotion: boolean
   *   - degrade: number (0|1|2)
   *   - innerOnly / raw: boolean (若为 true 则不包含外层 <defs> 标签)
   *   - pulse: boolean
   *   - gridSize: number
   *   - prismAngle: string ('diag'|'h'|'v')
   * @returns {string} 合法 SVG XML 字符串
   */
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
  /**
   * 为最高维和极值顶点提供动态 CSS filter/drop-shadow 样式串
   * @param {number|*} score 分值 (0-100)
   * @param {boolean|*} isPeak 是否最高维
   * @param {object|string} [opt] 选项或格式模式
   *   - valueOnly: 若为 true，仅返回 drop-shadow(...) 属性值，不带 'filter: ...;'
   *   - inline: 若为 true，返回内联 CSS 属性声明形式 'filter: ...;' (默认)
   * @returns {string} CSS filter/drop-shadow 样式串
   */
  function getPeakAuraStyle(score, isPeak, opt) {
    var s = safeNum(score, 0);
    var peak = Boolean(isPeak);
    var isValOnly = opt === 'value' || (opt && (opt.valueOnly === true || opt.propertyOnly === true));

    var shadows = [];

    if (peak) {
      if (s >= 96) {
        // 传说级极值最高维：高能白金微核 + 炽烈绯红光冕 + 虚空秘紫超空间弥散
        shadows.push('drop-shadow(0 0 3px rgba(255, 241, 218, 0.95))');
        shadows.push('drop-shadow(0 0 7px rgba(255, 92, 124, 0.85))');
        shadows.push('drop-shadow(0 0 14px rgba(166, 136, 255, 0.65))');
      } else if (s >= 85) {
        // 一方之最高维：太阳琥珀纯亮光晕 + 薄荷科技发散
        shadows.push('drop-shadow(0 0 3px rgba(255, 214, 150, 0.92))');
        shadows.push('drop-shadow(0 0 8px rgba(255, 180, 92, 0.78))');
        shadows.push('drop-shadow(0 0 12px rgba(122, 240, 200, 0.48))');
      } else if (s >= 70) {
        // 圈内出色最高维：薄荷核心光 + 太阳琥珀扩散
        shadows.push('drop-shadow(0 0 3px rgba(122, 240, 200, 0.88))');
        shadows.push('drop-shadow(0 0 7px rgba(255, 180, 92, 0.62))');
      } else {
        // 常规最高维：薄荷微光 + 虚空柔晕
        shadows.push('drop-shadow(0 0 3px rgba(122, 240, 200, 0.78))');
        shadows.push('drop-shadow(0 0 6px rgba(166, 136, 255, 0.42))');
      }
    } else {
      // 非最高维，但可能为绝对高分/极值
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

  /** 便捷方法：仅获取 CSS drop-shadow 属性值（无 'filter: ...;' 前缀） */
  function getPeakAuraFilterValue(score, isPeak) {
    return getPeakAuraStyle(score, isPeak, { valueOnly: true });
  }

  // ---- 模块导出对象 ----------------------------------------------------------
  var CLRadarVisualFX = {
    // 核心契约方法
    renderDefs: renderDefs,
    getPeakAuraStyle: getPeakAuraStyle,
    getPeakAuraFilterValue: getPeakAuraFilterValue,

    // 子组件与辅助方法
    getIds: getIds,
    renderPrismGradient: renderPrismGradient,
    renderGhostGlowFilter: renderGhostGlowFilter,
    renderVertexBloomFilter: renderVertexBloomFilter,
    renderScanGridPattern: renderScanGridPattern,

    // 常量与状态工具
    THEME: THEME,
    KEYS: KEYS,
    EN: EN,
    isReducedMotion: isReducedMotion,
    sanitizeUid: sanitizeUid,

    // 版本
    version: '1.0.0'
  };

  // 挂载至全局命名空间
  if (typeof global !== 'undefined') {
    global.CLRadarVisualFX = CLRadarVisualFX;
  }

})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
