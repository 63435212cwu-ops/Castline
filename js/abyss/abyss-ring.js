/**
 * Castline · abyss-ring.js — 刻度环 · 铭文环共用件（CORE · S4）
 * ============================================================================
 * 来源：mystic-grand-refactor-plan「深渊星典」§4 S4 刻度环 · 铭文环共用件。
 * 定位：三图（雷达 / 角色星座场 / 星盘剧情树）共用的环状几何与神圣符文生成器。
 *       统一 24/48 刻度、双层反向铭文、走针落格规则与 Three.js/SVG 双通道输出。
 *
 * ES5 IIFE · 零外部强依赖 · UMD 全局暴露 window.CLAbyssRing。
 * ============================================================================
 */
(function (global) {
  'use strict';

  /* 24 枚神圣禁忌符文标准字形（矢量笔画集） */
  var RUNES = [
    'M2 8L5 2L8 8M3 6H7',
    'M2 2H8V8H2ZM2 5H8M5 2V8',
    'M5 2L2 5L5 8L8 5Z',
    'M2 2L8 8M8 2L2 8M5 2V8',
    'M2 3H8M5 3V8M3 8H7',
    'M2 2V8L5 5L8 8V2',
    'M2 2H8L5 5H8V8H2',
    'M5 2L2 8H8ZM5 4V6',
    'M2 2H8V5H2V8H8',
    'M2 5C2 3 4 2 5 2C7 2 8 3 8 5C8 7 6 8 5 8M5 5H8',
    'M2 2L8 5L2 8ZM4 3.5V6.5',
    'M2 2V8H8M2 5H6',
    'M2 8V2L5 6L8 2V8',
    'M5 2V8M2 5H8M3 3L7 7',
    'M2 2H8V8H5L2 5Z',
    'M3 2H7L8 5L7 8H3L2 5Z',
    'M2 2L5 8L8 2M3.5 5H6.5',
    'M2 8L8 2M2 2L5 5M8 8L5 5',
    'M2 5H8M5 2C3 2 2 3 2 5C2 7 3 8 5 8C7 8 8 7 8 5',
    'M2 2H5C7 2 8 3 8 5C8 7 7 8 5 8H2Z',
    'M5 2L8 5L5 8M2 5H8',
    'M2 3L5 2L8 3V6L5 8L2 6Z',
    'M2 2H8L5 8ZM4 3.5H6',
    'M3 2H7V4H3ZM2 4H8V8H2ZM4 6H6V8H4Z'
  ];

  function round(v) {
    return Math.round(v * 100) / 100;
  }

  /**
   * 生成 SVG 刻度表圈 (Bezel)
   * 包含宽底带 + 细刻 dasharray + 分刻 + 外沿亮线 + 径向主刻度线
   */
  function createSVGBézél(opts) {
    opts = opts || {};
    var cx = opts.cx != null ? opts.cx : 0;
    var cy = opts.cy != null ? opts.cy : 0;
    var r = opts.r != null ? opts.r : 100;
    var tickCount = opts.tickCount || 48;
    var majorCount = opts.majorCount || 8;
    var peakIndex = opts.peakIndex != null ? opts.peakIndex : -1;
    var squash = opts.squash != null ? opts.squash : 1.0;
    var cls = opts.className || 'abyss-bezel';
    var uid = opts.uid ? opts.uid + '-' : '';

    var out = ['<g class="' + cls + '">'];

    // 1. 底环带与高精度 dasharray 刻度圈
    out.push('<circle class="abyss-bezel-band" cx="' + cx + '" cy="' + cy + '" r="' + round(r + 2.6) + '"/>');
    out.push('<circle class="abyss-bezel-fine" cx="' + cx + '" cy="' + cy + '" r="' + round(r + 1.2) + '" pathLength="360"/>');
    out.push('<circle class="abyss-bezel-min" cx="' + cx + '" cy="' + cy + '" r="' + round(r + 2.4) + '" pathLength="60"/>');
    out.push('<circle class="abyss-bezel-edge" cx="' + cx + '" cy="' + cy + '" r="' + round(r + 6.2) + '"/>');
    out.push('<circle class="abyss-bezel-edge inner" cx="' + cx + '" cy="' + cy + '" r="' + round(r - 1.4) + '"/>');

    // 2. 径向刻度线（长/短刻度）
    for (var i = 0; i < tickCount; i++) {
      var isMajor = (i % Math.round(tickCount / majorCount)) === 0;
      var angle = -Math.PI / 2 + i * (2 * Math.PI / tickCount);
      var r0 = r - (isMajor ? 2.5 : 0.8);
      var r1 = r + (isMajor ? 5.8 : 3.2);

      var x0 = round(cx + Math.cos(angle) * r0);
      var y0 = round(cy + Math.sin(angle) * r0 * squash);
      var x1 = round(cx + Math.cos(angle) * r1);
      var y1 = round(cy + Math.sin(angle) * r1 * squash);

      var lineCls = 'abyss-tick-line' + (isMajor ? ' major' : ' minor') + (isMajor && i === 0 ? ' twelve' : '');
      out.push('<line class="' + lineCls + '" x1="' + x0 + '" y1="' + y0 + '" x2="' + x1 + '" y2="' + y1 + '" data-tick="' + i + '"/>');
    }

    // 3. 峰值指示标 (Peak Indicator)
    if (peakIndex >= 0 && peakIndex < majorCount) {
      var pAngle = -Math.PI / 2 + peakIndex * (2 * Math.PI / majorCount);
      var pr0 = r + 7.5, pr1 = r + 13.5, pw = 3.8;
      var tipX = round(cx + Math.cos(pAngle) * pr0);
      var tipY = round(cy + Math.sin(pAngle) * pr0 * squash);
      var baseX = cx + Math.cos(pAngle) * pr1;
      var baseY = cy + Math.sin(pAngle) * pr1 * squash;
      var nx = -Math.sin(pAngle) * pw;
      var ny = Math.cos(pAngle) * pw * squash;
      var b1X = round(baseX + nx), b1Y = round(baseY + ny);
      var b2X = round(baseX - nx), b2Y = round(baseY - ny);
      out.push('<polygon class="abyss-peak-mark" points="' + tipX + ',' + tipY + ' ' + b1X + ',' + b1Y + ' ' + b2X + ',' + b2Y + '"/>');
    }

    out.push('</g>');
    return out.join('');
  }

  /**
   * 生成 SVG 铭文环 (Rune Ring)
   * 支持单层与双层反向联动模式（转速比 1 : -0.618）
   */
  function createSVGRuneRing(opts) {
    opts = opts || {};
    var cx = opts.cx != null ? opts.cx : 0;
    var cy = opts.cy != null ? opts.cy : 0;
    var r = opts.r != null ? opts.r : 130;
    var runes = opts.runes || RUNES;

    // Mini 树年轮盘模式 (tree-marks.js)
    if (opts.mini) {
      var mr = opts.r != null ? opts.r : 9.5;
      var mcx = opts.cx != null ? opts.cx : 11;
      var mcy = opts.cy != null ? opts.cy : 11;
      var mw = opts.width || 16;
      var mh = opts.height || 16;
      var mvb = opts.viewBox || '0 0 22 22';
      return '<svg class="' + (opts.className || 'tree-annual-ring-svg') + '" width="' + mw + '" height="' + mh + '" viewBox="' + mvb + '">' +
        '<circle class="ring-outer-dots" cx="' + mcx + '" cy="' + mcy + '" r="' + mr + '" fill="none" stroke="currentColor" stroke-width="0.8" stroke-dasharray="1.5 2.5"/>' +
        '<circle class="ring-inner-numeral" cx="' + mcx + '" cy="' + mcy + '" r="' + round(mr * 0.63) + '" fill="none" stroke="currentColor" stroke-width="0.6" stroke-dasharray="2 1.5"/>' +
        '</svg>';
    }

    var squash = opts.squash != null ? opts.squash : 1.0;

    // 雷达双层符文环模式 (radar.js / radar-ritual.js)
    if (opts.forRadar) {
      var n = opts.dimCount || 8;
      var runeROuter = opts.rOuter != null ? opts.rOuter : round(r * 1.09);
      var rn = [], rnOuter = [];
      for (var i = 0; i < 24; i++) {
        var ra = -Math.PI / 2 + i * (Math.PI * 2 / 24);
        var rx = round(cx + Math.cos(ra) * r), ry = round(cy + Math.sin(ra) * r * squash);
        var rdeg = round(ra * 180 / Math.PI + 90), rflip = i % 3 === 1 ? ' scale(-1,1)' : '';
        var dimIdx = Math.floor(i / 3) % n;
        rn.push('<g class="rd-rune abyss-rune" data-i="' + i + '" data-dim="' + dimIdx + '" transform="translate(' + rx + ' ' + ry + ') rotate(' + rdeg + ') scale(1.42)' + rflip + '">' +
          '<path d="' + runes[(i * 5 + (i >> 2)) % runes.length] + '" transform="translate(-5 -5)"/></g>');
      }
      for (var oi = 0; oi < 48; oi++) {
        var ora = -Math.PI / 2 + oi * (Math.PI * 2 / 48);
        var orx = round(cx + Math.cos(ora) * runeROuter), ory = round(cy + Math.sin(ora) * runeROuter * squash);
        var ordeg = round(ora * 180 / Math.PI + 90), orflip = oi % 2 === 1 ? ' scale(-1,1)' : '';
        var odimIdx = Math.floor(oi / 6) % n;
        rnOuter.push('<g class="rd-rune-outer abyss-rune" data-outer-i="' + oi + '" data-dim="' + odimIdx + '" transform="translate(' + orx + ' ' + ory + ') rotate(' + ordeg + ') scale(1.18)' + orflip + '">' +
          '<path d="' + runes[(oi * 7 + 3) % runes.length] + '" transform="translate(-5 -5)"/></g>');
      }
      return '<g class="rd-runes-outer abyss-rune-tier outer" aria-hidden="true" data-speed="1.0">' + rnOuter.join('') + '</g>' +
             '<g class="rd-runes abyss-rune-tier inner" aria-hidden="true" data-speed="-0.618">' + rn.join('') + '</g>';
    }

    var dual = !!opts.dual;
    var count = opts.count || (dual ? 48 : 24);
    var activeIndices = opts.activeIndices || [];
    var cls = opts.className || 'abyss-rune-ring';

    var activeMap = {};
    for (var a = 0; a < activeIndices.length; a++) {
      activeMap[activeIndices[a]] = true;
    }

    var out = ['<g class="' + cls + ' abyss-inscription">'];

    function buildRing(ringR, n, isInner, speedK) {
      var subCls = 'abyss-rune-tier' + (isInner ? ' inner' : ' outer');
      out.push('<g class="' + subCls + '" data-speed="' + speedK + '">');
      for (var i = 0; i < n; i++) {
        var angle = -Math.PI / 2 + (isInner ? -1 : 1) * i * (Math.PI * 2 / n);
        var rx = round(cx + Math.cos(angle) * ringR);
        var ry = round(cy + Math.sin(angle) * ringR * squash);
        var deg = round(angle * 180 / Math.PI + 90);
        var runeIdx = (i * 5 + (i >> 2)) % runes.length;
        var strokePath = runes[runeIdx];
        var isActive = !isInner && activeMap[i];
        var rCls = 'abyss-rune' + (isActive ? ' active' : '') + (isInner ? ' rune-subtle' : '');

        out.push(
          '<g class="' + rCls + '" data-i="' + i + '" transform="translate(' + rx + ' ' + ry + ') rotate(' + deg + ') scale(' + (isInner ? 1.05 : 1.35) + ')">' +
          '<path d="' + strokePath + '" transform="translate(-5 -5)" fill="none" stroke="currentColor" stroke-width="1.2"/>' +
          '</g>'
        );
      }
      out.push('</g>');
    }

    if (dual) {
      // 外层 48 铭文（速度比 1.0）+ 内层 24 铭文（反向，速度比 -0.618）
      buildRing(r, 48, false, 1.0);
      buildRing(round(r * 0.82), 24, true, -0.618);
    } else {
      buildRing(r, count, false, 1.0);
    }

    out.push('</g>');
    return out.join('');
  }

  /**
   * 生成 Three.js 空间刻度几何顶点数据
   */
  function createThreeRingData(opts) {
    opts = opts || {};
    var r = opts.r != null ? opts.r : 100;
    var tickCount = opts.tickCount || 48;
    var segments = opts.segments || 128;

    // 1. 圆环圆周顶点
    var circlePts = [];
    for (var i = 0; i <= segments; i++) {
      var theta = (i / segments) * Math.PI * 2;
      circlePts.push(Math.cos(theta) * r, 0, Math.sin(theta) * r);
    }

    // 2. 径向刻度线段顶点
    var tickPts = [];
    for (var j = 0; j < tickCount; j++) {
      var isMajor = (j % 6) === 0;
      var a = (j / tickCount) * Math.PI * 2;
      var r0 = r - (isMajor ? 4.0 : 1.8);
      var r1 = r + (isMajor ? 5.0 : 2.2);
      tickPts.push(Math.cos(a) * r0, 0, Math.sin(a) * r0);
      tickPts.push(Math.cos(a) * r1, 0, Math.sin(a) * r1);
    }

    // 3. 符文空间定位锚点
    var runeAnchors = [];
    var runeCount = opts.runeCount || 24;
    for (var k = 0; k < runeCount; k++) {
      var ra = (k / runeCount) * Math.PI * 2;
      runeAnchors.push({
        index: k,
        angle: ra,
        pos: [Math.cos(ra) * (r + 8.0), 0, Math.sin(ra) * (r + 8.0)]
      });
    }

    return {
      radius: r,
      tickCount: tickCount,
      circleVertices: new Float32Array(circlePts),
      tickVertices: new Float32Array(tickPts),
      runeAnchors: runeAnchors
    };
  }

  /**
   * 计算受 S3 呼吸总线时钟统领的旋转角度
   */
  function computeRotation(t, speedK) {
    t = +t || 0;
    speedK = speedK != null ? speedK : 1.0;
    // 基准 72s 一周
    var basePeriod = 72.0;
    var angleRad = (t * speedK / basePeriod * 2 * Math.PI) % (2 * Math.PI);
    var angleDeg = (angleRad * 180 / Math.PI) % 360;
    return {
      rad: angleRad,
      deg: round(angleDeg),
      ratio: (angleDeg / 360)
    };
  }

  var CLAbyssRing = {
    name: 'abyss-ring',
    version: '1',
    RUNES: RUNES,
    createSVGBézél: createSVGBézél,
    createSVGRuneRing: createSVGRuneRing,
    createThreeRingData: createThreeRingData,
    computeRotation: computeRotation,
    audit: function () {
      return {
        name: 'abyss-ring',
        version: '1',
        runeCount: RUNES.length,
        hasSvgBezel: typeof createSVGBézél === 'function',
        hasSvgRuneRing: typeof createSVGRuneRing === 'function',
        hasThreeRing: typeof createThreeRingData === 'function'
      };
    }
  };

  global.CLAbyssRing = CLAbyssRing;
})(typeof window !== 'undefined' ? window : this);
